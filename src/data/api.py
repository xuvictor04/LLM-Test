"""DATA -- the frozen public surface. Signatures only; P4 writes the bodies.

DATA owns the only bytes the system ever sees and the only split it is honestly measured on.
Goal A needs the held-out number to measure generalisation rather than repetition, which is
`holdout_frac`, `val_cap` and the two exposure guards. Goal B needs a NON-STATIONARY stream,
because a stationary i.i.d. splice of N corpora does not require continual learning at all --
so `phase_sched` is not a parameter of the continual-learning experiment, it IS the experiment.

WHAT LEAVES THIS PACKAGE: a byte stream, one area label per byte, the splice positions AND the
subset of them that are real area changes, the phase bounds, and one held-out block per area.
Nothing else in the tree may decide any of that.

INTERNAL MODULE SPLIT IS P4's BUSINESS. The contract is this file. P4 may put `Areas` in
corpus.py, the Markov processes in synth.py, the split in split.py, the schedule in
schedule.py, the draw in stream.py and the gates in plan.py -- as the survey slice proposed --
provided every name below keeps this signature. The signatures are what ten independent
implementation agents share; nothing else about the layout is load-bearing.

RECORD TYPES RETURNED (P4 defines them; they are DATA's objects and other packages receive
them as arguments, which is not an import and O10 does not refuse it):
  Areas   names, bodies, holdout, holdout_bytes, bytes_present, bytes_taken, cursors, rng_holdout,
          counters, gates, parent_names, drawn
  Plan    protocol, schedule, phase_bounds, per_area_draw, exposure, gates, counters, faded,
          parent_faded, shares, replay_faded
  Stream  bytes, labels, splice_starts, area_changes, phase_bounds, area_names, per_area_drawn,
          epoch, stream_id, draws, counters, gates
"""
import dataclasses
import hashlib
import math
import os
import weakref
from fractions import Fraction

from spine.lever import Config, LeverError
from spine import rng as _rng
from spine.gate import Gate


class CorpusError(ValueError):
    """A corpus configuration that cannot produce a comparable measurement, refused at startup.

    REFUSED AND NOT DROPPED, which is the whole point. Dropping a short corpus desynchronised the
    domain-name list from the corpus list, so report_holdout labelled the Python corpus 'eng' and
    the next run compared that against the previous run's English and reported the difference as
    FORGETTING (ISSUES P3-C19). A silent drop in this package is a wrong number in goal B's
    headline experiment, arriving with nothing in the log.
    """


# THE FLOOR IS DERIVED, NOT THE OLD LITERAL 5000. At rerun.sh's SEG_MIN=8000 the literal admitted
# corpora that no segment could be drawn from, and `randint(0, SEG_LEN - L - 1)` then raised on a
# negative bound (ISSUES P1-L75). An area must hold at least one maximum-length segment plus a byte.
MIN_AREA_BYTES = 5000


@dataclasses.dataclass(frozen=True)
class Areas:
    """Every area's training body and held-out block, with the arithmetic that produced them.

    `bytes_present` BESIDE `bytes_taken` is the corpus cap's DID IT FIRE: the old tree warned about
    its own default instead of printing what the cap actually cost, so an operator could not tell a
    2 MB corpus from a 40 MB corpus truncated to 2 MB.

    `holdout` IS PHYSICALLY REMOVED from `bodies`. Not masked, not skipped -- removed, so no
    sampling rule anywhere can reach it and no length any caller can read includes it
    (ISSUES P1-M81).

    `counters` AND `gates` CARRY THE DID IT FIRE SURFACE open_areas DECLARES, and the split between
    them is decided by ONE question: is there a configuration on which the mechanism CANNOT run? A
    name with such an arm is a `spine.gate.Gate` in `gates`, because Gate is the only record in this
    tree that can say UNREACHABLE and carry the reason; a name that is always evaluable is a reading
    in `counters`, because wrapping a reading in a Gate prints "armed, did not fire" for a number
    that never had a condition to meet. Every declared name lands in exactly one of the two, so a
    report greps both and finds each name once. Until this field existed, every one of those names
    was computed nowhere and DATA's armed-but-0 and UNREACHABLE states were the same silence --
    which is the one distinction spine/gate.py::Gate exists to preserve.

    `parent_names` IS THE AREA LIST THE RESUMED CHECKPOINT RECORDED, in its order, FILLED IN PLACE by
    restore_stream_state (2026-09-27, Q-DATA-9) -- every area the parent DECLARED, beside `names`,
    which is this run's. Empty on a fresh run. A list and not a tuple for the reason `cursors` is a
    dict: the record is frozen and its restore mutates the value, not the field.

    `drawn` IS EVERY AREA THIS LINEAGE'S STREAMS HAVE DRAWN A BYTE FROM, in the order first drawn
    (2026-09-28, Q-FAB-18's review): restore_stream_state fills it in place from the record, and
    draw_stream appends each area its draw took a byte from and the list does not hold yet;
    stream_state records it. A declared area is not a trained one -- a run over "eng,py" that
    schedules eng alone never draws py -- and Plan.parent_faded is read off this list, not
    parent_names. Empty on a fresh run until its first draw.
    """
    names: tuple
    bodies: dict
    holdout: dict
    holdout_bytes: dict
    bytes_present: dict
    bytes_taken: dict
    cursors: dict
    rng_holdout: dict
    counters: dict = dataclasses.field(default_factory=dict)
    gates: tuple = ()
    parent_names: list = dataclasses.field(default_factory=list)
    drawn: list = dataclasses.field(default_factory=list)


def _holdout_key(label):
    """The rng subsystem name for one area's held-out stream: the label, normalised.

    spine/rng.py refuses uppercase (so "Fabric" and "fabric" cannot become two streams for one
    subsystem) and refuses "/" (its seed separator). Area labels are directory names and may carry
    both -- "code_OOD" today, and "continual/01_rust" under the slash rule. So the key is the label
    lowercased with everything outside [a-z0-9_] replaced by "_", and two areas whose KEYS collide
    are the same startup refusal as two whose labels collide. That is exactly the objection rng.py
    raises, answered at startup rather than papered over.

    THE RULE IS spine/derive.py::stream_key AND THIS DELEGATES TO IT (2026-09-27, Q-DATA-9). SR0's
    pinned probe keys its windows by the same area names in another package, and two copies of the
    normalisation would be two answers to "which stream is this area's".
    """
    from spine import derive as _derive
    return _derive.stream_key(label)




def open_areas(dat: Config, *, seed: int):
    """Open every area named by `dat.areas` and split each into a training body and a held-out block.

    On dat.source == "real": reads one directory per entry in dat.areas, skipping basenames
    starting with "_" and any .json -- fetch manifests were being spliced into the corpus and
    trained on as if they were English (datastream.py:69-71). Each area is read up to
    dat.corpus_cap bytes, and BYTES PRESENT IS RECORDED BESIDE BYTES TAKEN so the cap's bite is a
    printed number rather than a program warning about its own default (self_organize.py:5616-5618).

    THE PATH RULE, RESOLVED (Q-DATA-4, ruled 2026-09-02). An entry containing "/" is joined under
    dat.dir VERBATIM; an entry with no "/" keeps "train/" as the implicit prefix:

        "eng"                -> dat.dir + "/train/eng/*"          (unchanged, the shipped meaning)
        "continual/01_rust"  -> dat.dir + "/continual/01_rust/*"

    datastream.py:72 hardcoded {data_dir}/train/{d}/*, so data/continual/{01_rust,02_sawyer,
    03_dracula,04_num2} (1.5 MB) and data/ood/{code_OOD,eng_OOD} (764 KB) -- THE MATERIAL THE
    ADD-AN-AREA BENCHMARK EXISTS FOR, and goal B's headline experiment with it -- were reachable
    only by moving files on disk, which is a configuration change no Sample can record. No lever is
    minted for this and no default moves; what changes is what one declared lever's STRING may say,
    which is why it is the owner's ruling and not a repair. A subdirectory lever (DATA_SPLIT="train")
    was refused: it cannot mix train/eng with continual/01_rust in ONE run, which IS the experiment,
    and it has no census ancestor, so N2 has no row for it and DEPARTURES -- keyed by (family,
    old_name) -- has no key to write.

    TWO STARTUP REFUSALS COME WITH THE SLASH, and neither is optional:
      * an entry that is absolute or contains ".." is REFUSED. Without it `areas` is an
        arbitrary-path read -- a corpus lever that can open /etc -- and the refusal must name the
        entry and the resolved path (data.area_path_refused). Scoped to dat.source == "real": a
        synthetic entry never becomes a filesystem path, so refusing it for looking like one would be
        refusing a label rather than a path.
      * the area LABEL is the basename ("continual/01_rust" labels as "01_rust"), and two entries
        resolving to the same label are REFUSED, with both DATA_AREAS entries printed
        (data.area_label_collision). The label is what every per-area score, the holdout stream key
        below and ACROSS THE RUN BOUNDARY look up by name, and a run whose report prints one label
        for two corpora reproduces the desynchronised-DN defect this package exists to end
        (ISSUES P3-C19). THIS CHECK, AND THE BASENAME RULE ABOVE IT, RUN ONCE FOR BOTH SOURCES,
        BEFORE THE SOURCE BRANCH (audit finding, confirmed live: they used to live only in the
        real-corpus branch, so on source=synthetic the label space was the RAW entry text, slash
        included, and a collision surfaced as spine.rng.RngError naming an RNG subsystem instead of
        this CorpusError naming DATA_AREAS and the two colliding entries). Neither check touches
        disk, so running them before the branch changes nothing about what they refuse -- it only
        stops the synthetic arm from reaching a per-area rng_for call unchecked.

    On dat.source == "synthetic": builds dat.n_processes order-2 Markov generators over the five
    alphabets, three of 15 symbols and two of 14 (self_organize.py:1084-1099, :1314-1315), seeded from
    rng_for("data.synth", seed) so that two run seeds are two different synthetic corpora. Today
    they are not: make_proc is seeded by the PROCESS INDEX, so `DATA_SOURCE=synthetic` measures a
    between-seed spread with the data held constant (DEFECT D-A13). WHETHER IT HOLDS ANYTHING OUT IS
    dat.synth_holdout's to say (2026-09-27, Q-DATA-9; 04-Q5 rules it ON, and it is built OFF until
    the flip lands). At True each generated body goes through the real sources' held-out law below,
    VERBATIM -- the same size, the same per-area child stream, the same removal, seam, overlap, val-cap
    tally and 0-byte refusal -- because two holdout laws for two sources would make a synthetic
    block a different kind of sample from a real one. At False nothing is held out: every body is the
    whole generated text, no data.holdout.<key> child is minted, and data.holdout_block and
    data.val_cap_trip read UNREACHABLE naming DATA_SYNTH_HOLDOUT=0. ONE LAW, BUT THE BODY IT RUNS ON
    IS GENERATED (2026-09-27, Q-DATA-9's review): its length is _synthetic_length, max(DATA_SEG_MAX +
    1, MIN_AREA_BYTES, DATA_STREAM_BYTES // DATA_N_PROCESSES) x 2, and its text is the alphabet the
    area's POSITION picks, so at True a synthetic block is keyed by its label only within one
    generated length and one area order. A real area's body is its own directory, so adding an area
    there moves no other area's block; here it moves every block unless DATA_STREAM_BYTES rises with
    DATA_N_PROCESSES and the new area is appended, and restore_stream_state refuses a resume across
    either move by name.

    DATA_AREAS NAMING FEWER ENTRIES THAN DATA_N_PROCESSES IS A STARTUP REFUSAL, not a license to
    invent labels (audit finding, confirmed live). `DATA_SOURCE=synthetic DATA_AREAS=eng
    DATA_N_PROCESSES=4` used to silently discard "eng" and generate four areas named p0..p3 --
    reproduced live, `areas.names == ('p0','p1','p2','p3')`, with the operator's one requested area
    appearing nowhere and no error, warning or refusal at any point. Every per-area score, the
    holdout rng keys and DATA_PHASE_SCHED's by-name lookup are keyed by the DECLARED name, so this
    was the desynchronised-label failure (ISSUES P3-C19) reached through the synthetic arm's own
    fallback rather than through a dropped corpus. Refused instead, naming DATA_AREAS and
    DATA_N_PROCESSES with both counts; DATA_N_PROCESSES < 1 is refused the same way rather than
    silently clamped to 1 (the old `max(1, n)` produced a stream from zero areas with nothing in the
    log to say so).

    THE HELD-OUT BLOCK IS A SEEDED RANDOM CONTIGUOUS BLOCK PER AREA, from
    rng_for("data.holdout." + key, seed) -- ONE CHILD STREAM PER AREA, KEYED BY THE AREA'S LABEL
    (normalised; the exact rule is three paragraphs down and it is the KEY, not the raw label, that
    is spliced in) AND NOT BY DRAW ORDER -- of size min(holdout_frac * present, val_cap) -- NOT the
    tail.
    The tail is a sample only if the corpus was written in no particular order, and the measured
    cost of assuming it was is py held out at 5.061 +/- 0.560 against 2.922 in-stream while eng
    (shuffled upstream) was 2.273 against 2.303 (self_organize.py:1173-1198). val_cap applies on
    BOTH paths; it applied only under DISK_STREAM before (ISSUES P1-M82). The block is physically
    removed from the training body, so no sampling rule anywhere can reach it and there is no
    length any caller can read that includes it (ISSUES P1-M81).

    ONE STREAM PER AREA IS THE RULING, NOT A DETAIL (Q-DATA-6, 2026-09-02). A single
    "data.holdout" stream draws the areas in list order, so every area's block position is a
    function of HOW MANY AREAS WERE DRAWN BEFORE IT: insert or reorder one entry and every later
    area's held-out text moves. Three things break at once when it does -- restore_stream_state
    below refuses the resume by its own stated reason, ACROSS THE RUN BOUNDARY compares two
    different texts, and EVAL's held-out window (eval/levers.py::EVALLevers) already DECLARES the
    opposite property in as many words: "KEYED BY DOMAIN NAME, not by index, so adding a domain
    does not shift the comparison. That property is part of the lever's meaning and has to survive
    the port." DATA is the half that produces the text EVAL then windows, so the two must key the
    same way or the paired add-an-area comparison is destroyed on the one run type it exists to
    measure. spine/rng.py::_check_name declares dotted child streams ("fabric.cull") as the supported
    shape, and DATA already derives per-epoch child names ("data.stream.e0") itself, so this needs
    no new RNG_SUBSYSTEMS entry -- "data.holdout" stays the declared parent. THE STREAM IS PER AREA ON
    BOTH SOURCES; THE BODY IS PER AREA ON A REAL ONE ONLY (2026-09-27, Q-DATA-9's review): a synthetic
    body's length and text are shared or positional, as the synthetic paragraph above says, so the
    property this paragraph argues for holds there only at one generated length and one area order.

    THE KEY IS THE LABEL, NORMALISED, AND THE COLLISION REFUSAL IS WHAT MAKES THAT SAFE.
    spine/rng.py refuses uppercase in a subsystem name on purpose ("Fabric" and "fabric" would be
    two streams for one subsystem), and area labels are directory names that may carry uppercase
    ("code_OOD") or, under the slash rule above, a "/" (which rng.py refuses because it is the
    seed separator). So the key is the label lowercased with every character outside [a-z0-9_]
    replaced by "_", and TWO AREAS WHOSE KEYS COLLIDE ARE THE SAME STARTUP REFUSAL as the label
    collision above -- which is exactly the objection rng.py raises, answered at startup rather
    than papered over. The key each area drew from is printed beside its offset and size.

    An area whose usable body is below max(dat.seg_max + 1, MIN_AREA_BYTES) is a STARTUP REFUSAL,
    not a silent drop: dropping desynchronised CORP from DN and made report_holdout label the
    Python corpus 'eng', which the next run compared against last run's English and reported as
    forgetting (self_organize.py:1142-1160, ISSUES P3-C19 -- CITED BY ID, NOT BY LINE: this was
    ISSUES:1421 in four places across this package and that line has held three different defects
    across three commits; today it is L15, an LR_DECAY default in a research note). The floor is
    DERIVED from seg_max rather
    than the old literal 5000, which raised on rerun.sh's SEG_MIN=8000 (ISSUES P1-L75).

    RECEIVES: seed <- RUN.seed, as an argument. DATA calls rng_for itself; assemble.NOT_WIRES
    rejects a d_seed by name.
    RETURNS: Areas.

    LEVERS READ: source, dir, areas, n_processes, corpus_cap, holdout_frac, val_cap, seg_max,
                 stream_bytes (audit finding, confirmed live: on the DEFAULT source=synthetic arm,
                 _synthetic_areas sizes every generated corpus from DATA_STREAM_BYTES, so the shipped
                 configuration's build sample, merge table and measured bytes_per_token all move with
                 a lever this line used to omit; declared here rather than silently left off a second
                 time), synth_holdout (the synthetic arm's held-out law, Q-DATA-9)
    WIRES READ: none
    DID IT FIRE: EVERY NAME BELOW IS CARRIED OUT ON THE RETURNED `Areas`, exactly once, and which
                 field it lands in follows the rule stated on the record: a name with a
                 configuration on which the mechanism CANNOT run is a `Gate` in `Areas.gates`,
                 because Gate is the only record here that can say UNREACHABLE and carry the reason;
                 a name that is always evaluable is a reading in `Areas.counters`. `data.holdout_seam`
                 is ONE GATE PER AREA (its name suffixed with the label) because its unreachable arm
                 is a property of THAT AREA'S DRAW -- a block that landed at the body's leading edge
                 or its tail -- and not of the configuration, so a single aggregate record would have
                 to pick one of the three states for a run whose areas genuinely disagree, which is
                 the collapse the record exists to refuse. The alternative -- ONE aggregate gate,
                 with the per-area edge reason left in `rng_holdout[label]["why"]` -- was rejected
                 because an aggregate would have to pick one of the three states for a set of areas
                 that need not share one: the edge draw is per area, so a run in which one area's
                 block lands at its leading edge while the others sit interior is REACHABLE. It is
                 rare -- the draw range is the usable body, whose floor is
                 max(DATA_SEG_MAX + 1, MIN_AREA_BYTES), so an edge is at most a two-in-floor
                 outcome per area -- and rarity is the wrong reason to collapse two states, since
                 the whole cost of this record is paid on the runs nobody expected.
                 data.area_open (one per area; unreachable on source=synthetic),
                 data.area_nested (one per areas entry containing "/" -- 0 is the shipped default
                 and means every area came from train/, which is a STATEMENT and not silence),
                 data.area_path_refused, data.area_label_collision, data.area_id_collision (two
                 labels on one spine/derive.py::area_id, the key FAB's area books and MEM's area
                 column book by, 2026-09-28; all three exit at startup, so N>0 is never seen in a
                 completed run; declared so the refusal is a named mechanism rather than an
                 assertion),
                 data.corpus_cap_trip (fired N / armed but 0, prints taken vs present per area),
                 data.holdout_block (prints offset+size AND the rng key per area; UNREACHABLE on
                 source=synthetic at DATA_SYNTH_HOLDOUT=0, and the real arm's gate at 1),
                 data.holdout_seam (one per area -- removing a MIDDLE block leaves exactly one
                 manufactured discontinuity in a body seg_contig=True reads in order, and
                 data/levers.py::DATALevers claims the only boundaries left are the text's own; one
                 seam per area against the thousands seg_from manufactures is a good trade, but it
                 is a PRINTED NUMBER and not an assumption. Unreachable when a block lands at
                 offset 0 or at the tail, which is the state it must say rather than read 0),
                 data.holdout_overlap (a READING, not a lever and not a gate: the fraction of
                 held-out bytes that also occur verbatim in the training body at a fixed n-gram
                 length, per area, computed once at startup -- and printed in the R report's
                 DATA(areas.counters) row since 2026-09-27; no row printed it before. It costs no
                 lever, no wire and no default, and it answers the one question the split rule
                 CANNOT: Lee et al. arXiv:2107.06499 measures models "underestimate perplexity on
                 evaluation documents with near duplicates" and says benchmarks "should actively
                 remove contaminated training data, rather than just partitioning held out splits
                 by documents", so NEITHER the tail nor the random block is safe on its own. It is
                 a reading of THIS run's blocks, so restore_stream_state never overwrites it with
                 the parent's), data.val_cap_trip (UNREACHABLE on source=synthetic at
                 DATA_SYNTH_HOLDOUT=0, like data.holdout_block),
                 data.area_refused (a refusal exits at startup, so N>0 is never seen in a
                 completed run), rng.issued()["data.synth"],
                 rng.issued()["data.holdout.<key>"] -- ONE PER AREA, and the PARENT NAME
                 "data.holdout" is never itself drawn from, so it appears in RNG_SUBSYSTEMS as the
                 declared parent and in issued() only through its children. An area whose child
                 stream is absent from issued() never asked for a block, which is a different
                 statement from a block of size 0 and G4 requires the report to make both
    """
    dat = dat.owned_by("DATA")
    entries = [e.strip() for e in str(dat.areas).split(",") if e.strip()]
    if not entries:
        raise CorpusError("DATA_AREAS is empty: there is nothing to train on.")

    floor = max(int(dat.seg_max) + 1, MIN_AREA_BYTES)

    # THE LABEL SPACE IS COMPUTED ONCE, FOR BOTH SOURCES, BEFORE THE SOURCE BRANCH (audit finding,
    # confirmed live). It used to be computed twice and differently: the real branch took
    # os.path.basename(entry) here, while the synthetic branch (inside _synthetic_areas) took the
    # RAW entry text verbatim, slash included. Reproduced: DATA_AREAS="continual/01_rust,eng" gave
    # areas.names == ('01_rust', 'eng') on DATA_SOURCE=real and ('continual/01_rust', 'eng') on
    # DATA_SOURCE=synthetic -- one lever value, two label spaces, with nothing declaring the split.
    # Every per-area score, DATA_PHASE_SCHED's by-name lookup and the across-the-run-boundary
    # comparison are keyed off this label, so a run that only changed DATA_SOURCE could silently
    # change what its own report calls the same area. This computes the basename once and the same
    # way for every entry, on either source.
    labels = [os.path.basename(entry.rstrip("/")) for entry in entries]

    # THE LABEL AND KEY COLLISION REFUSALS, NOW RUN REGARDLESS OF SOURCE (audit finding, confirmed
    # live). This loop used to sit only inside the real-corpus branch below, so
    # `DATA_SOURCE=synthetic DATA_AREAS="rustA,rusta,x,y"` reached _synthetic_areas's per-area
    # rng_for call unchecked, and the collision surfaced as spine.rng.RngError ("stream
    # 'data.synth.rusta' was already issued for seed 0") -- a message about generator identity,
    # naming neither DATA_AREAS nor which two entries collided, for what this package's own rule
    # says must be a startup refusal naming the lever. Neither check below touches disk, so hoisting
    # them above the branch changes nothing about what they refuse, only which arm can reach an
    # unchecked rng_for call.
    by_label, by_key, by_id = {}, {}, {}
    from spine import derive as _derive
    for entry, label in zip(entries, labels):
        if label in by_label:
            raise CorpusError(
                f"two DATA_AREAS entries resolve to the label {label!r}: {by_label[label]!r} "
                f"and {entry!r}. Every per-area score and the across-the-run-boundary comparison "
                f"look up by label, so one label over two corpora reports one corpus's loss as "
                f"the other's.")
        key = _holdout_key(label)
        if key in by_key:
            raise CorpusError(
                f"labels {by_key[key][0]!r} and {label!r} both normalise to the rng key "
                f"{key!r}, so they would draw their held-out (or, on DATA_SOURCE=synthetic, their "
                f"generator) blocks from ONE stream. Rename one DATA_AREAS entry.")
        # THE AREA ID IS THE THIRD NAME A LABEL IS LOOKED UP UNDER, AND ITS COLLISION IS THE SAME
        # REFUSAL (2026-09-28, register §8 3.1; docs/04_CONTRACT.md Q-FAB-18). FAB's per-expert area
        # books and MEM's per-entry `area` column key each area by spine/derive.py::area_id -- crc32
        # of the label, 31 bits -- because neither package may see a name and both books cross a
        # resume. Two labels on one id would be booked as one area: the faded-area counts and the
        # occupancy rows would file one corpus's experts and entries under the other's name. A
        # crc32 collision between two real labels is rare, and rarity is the wrong reason to let a
        # report merge two areas in silence.
        aid = _derive.area_id(label)
        if aid in by_id:
            raise CorpusError(
                f"labels {by_id[aid][0]!r} and {label!r} both hash to the area id {aid} "
                f"(spine/derive.py::area_id, crc32 of the label masked to 31 bits), so FAB's area "
                f"books and MEM's area column would book them as ONE area "
                f"(data.area_id_collision). Rename one DATA_AREAS entry.")
        by_label[label] = entry
        by_key[key] = (label, entry)
        by_id[aid] = (label, entry)

    raw = {}                       # label -> bytes, before the held-out block is removed
    present, taken, sources = {}, {}, {}
    # THE DID IT FIRE TALLIES, INCREMENTED AT THE DECISION POINT THAT OWNS EACH ONE rather than
    # reconstructed from the returned dicts afterwards. The difference is not cosmetic: `n_open`
    # counts directories this function actually opened, which on the synthetic arm is a number that
    # does not exist rather than a zero, and reconstructing it from `len(taken)` would manufacture
    # the zero this whole surface exists to distinguish from silence.
    n_open, n_nested, n_path_checked, n_cap_trip = 0, 0, 0, 0
    n_block, n_val_cap = 0, 0
    frac_bytes = {}                # label -> int(body * HOLDOUT_FRAC), the val cap's other term

    if str(dat.source) == "synthetic":
        raw, present, taken, sources = _synthetic_areas(dat, seed, entries, labels)
    else:
        for entry, label in zip(entries, labels):
            # COUNTED BEFORE THE REFUSAL, because data.area_path_refused's threshold is what the
            # refusal LOOKED AT: "0 refused of 4 checked" is a reading and "0" alone is not.
            n_path_checked += 1
            # THE PATH REFUSAL, because without it `areas` is an arbitrary-path read -- a corpus
            # lever that can open /etc -- and the message must name both the entry and what it
            # resolved to, or an operator cannot see which of the two is wrong. Scoped to this
            # branch deliberately: a synthetic entry never becomes a filesystem path, so refusing it
            # for looking like one would be refusing a label, not a path.
            if os.path.isabs(entry) or ".." in entry.split("/"):
                raise CorpusError(
                    f"DATA_AREAS entry {entry!r} is absolute or contains '..'. Refused: an area "
                    f"entry is joined under DATA_DIR and may not escape it, or this lever is an "
                    f"arbitrary-path read.")
            # THE SLASH RULE (Q-DATA-4). No slash keeps "train/" as the implicit prefix, which is
            # the shipped meaning and does not move; a slash is joined verbatim, which is what makes
            # data/continual/* and data/ood/* reachable without moving files on disk -- the material
            # goal B's add-an-area experiment exists for.
            if "/" in entry:
                # data.area_nested, COUNTED AT THE BRANCH THAT MAKES IT TRUE. This is the only line
                # in the tree where an entry is joined under DATA_DIR verbatim instead of under
                # train/, so it is the only honest place to count one.
                n_nested += 1
                rel = entry
            else:
                rel = os.path.join("train", entry)
            path = os.path.join(str(dat.dir), rel)
            body, n_present = _read_area(path, int(dat.corpus_cap))
            if not body:
                raise CorpusError(
                    f"area {label!r} at {path!r} holds no usable bytes. Refused rather than "
                    f"dropped: dropping an area desynchronises the label list from the corpus list "
                    f"and the next run reports one corpus's loss under another's name "
                    f"(ISSUES P3-C19).")
            raw[label], present[label], taken[label], sources[label] = body, n_present, len(body), path
            n_open += 1
            if len(body) < n_present:
                # data.corpus_cap_trip: the cap BIT for this area. `_read_area` counts `present`
                # past the cap on purpose, so this comparison is the cap's cost and not a guess.
                n_cap_trip += 1

    names = tuple(raw)
    bodies, holdout, holdout_bytes, rng_holdout, cursors = {}, {}, {}, {}, {}
    # THE ONE ARM THAT HOLDS NOTHING OUT (2026-09-27, Q-DATA-9): the synthetic source at
    # DATA_SYNTH_HOLDOUT=0. Everywhere else -- a real source, or the synthetic one at 1 -- the loop
    # below runs the real sources' law VERBATIM, because one held-out law for both sources is what
    # makes a synthetic block the same kind of sample as a real one (04-Q5). On this arm the loop runs
    # the statements it ran before the lever existed, in order, and mints no data.holdout.<key> child.
    synth_off = str(dat.source) == "synthetic" and not bool(dat.synth_holdout)
    for label in names:
        blob = raw[label]
        # THE FLOOR IS CHECKED ON THE USABLE BODY, i.e. after the held-out block comes out, which is
        # why the arithmetic is done before the refusal rather than after.
        # THE VAL CAP'S DID IT FIRE IS THIS min(), and nowhere else: DATA_VAL_CAP tripped for this
        # area exactly when the cap, and not the fraction, was the binding term. Both numbers are
        # kept per area because the gate below prints the arithmetic rather than a verdict.
        frac_bytes[label] = int(len(blob) * float(dat.holdout_frac))
        n_hold = min(frac_bytes[label], int(dat.val_cap))
        if synth_off:
            n_hold = 0             # the synthetic path at DATA_SYNTH_HOLDOUT=0 holds nothing out
        elif frac_bytes[label] > int(dat.val_cap):
            n_val_cap += 1
        if len(blob) - n_hold < floor:
            raise CorpusError(
                f"area {label!r} has {len(blob) - n_hold} usable byte(s) after a {n_hold}-byte "
                f"held-out block, below the floor of {floor} (max(DATA_SEG_MAX + 1, "
                f"{MIN_AREA_BYTES})). Refused, not dropped. The floor is DERIVED from seg_max: the "
                f"old literal 5000 admitted corpora no segment could be drawn from and the sampler "
                f"then raised on a negative bound (ISSUES P1-L75).")

        if n_hold > 0:
            # ONE CHILD STREAM PER AREA, KEYED BY THE AREA'S NAME AND NOT BY DRAW ORDER (Q-DATA-6).
            # A single stream drawn in list order makes every area's block position a function of
            # how many areas preceded it, so inserting one entry moves every later area's held-out
            # text -- and the across-the-boundary comparison then compares two different texts on
            # the one run type it exists to measure. EVAL's window already declares the opposite
            # property; the two halves have to key the same way.
            key = _holdout_key(label)
            stream = _rng.rng_for(f"data.holdout.{key}", seed)
            # A SEEDED RANDOM CONTIGUOUS BLOCK, NOT THE TAIL. The tail is a sample only if the
            # corpus was written in no particular order; measured, py held out at 5.061 +/- 0.560
            # against 2.922 in-stream, while eng (shuffled upstream) was 2.273 against 2.303.
            start = stream.randint(0, len(blob) - n_hold)
            holdout[label] = blob[start:start + n_hold]
            # REMOVED, NOT MASKED. One manufactured seam per area is the cost, and it is a good
            # trade against the thousands seg_from manufactures -- but it is stated, not hidden.
            bodies[label] = blob[:start] + blob[start + n_hold:]
            # SEAM_AT IS THE MANUFACTURED-DISCONTINUITY POSITION, NOT THE BLOCK OFFSET (audit
            # finding, confirmed live). Removing a MIDDLE block leaves one seam; removing a PREFIX
            # (start == 0) or a SUFFIX (start + n_hold == len(blob)) leaves none, because there is no
            # text on the missing side to be discontinuous with. The old line recorded `start`
            # unconditionally, so a block at offset 0 read seam_at: 0 -- a position -- in exactly the
            # two cases the docstring's own DID IT FIRE contract says must read UNREACHABLE instead
            # (reproduced by forcing start=0 via a patched Rng.randint: rng_holdout['eng']['seam_at']
            # came back 0, not None, on a run with no interior seam at all).
            interior_seam = 0 < start and start + n_hold < len(blob)
            rng_holdout[label] = {
                "key": f"data.holdout.{key}", "offset": start, "size": n_hold,
                "seam_at": start if interior_seam else None,
                # THE ONE INSTRUMENT FOR NEAR-DUPLICATE CONTAMINATION (audit finding, confirmed live:
                # declared in the DID IT FIRE list, never computed anywhere -- `grep -n
                # holdout_overlap src/data/api.py` returned only the docstring line itself). See
                # _holdout_overlap for what it measures and why the split rule alone cannot answer
                # this question (Lee et al. arXiv:2107.06499).
                "overlap": _holdout_overlap(holdout[label], bodies[label]),
            }
            n_block += 1
            if not interior_seam:
                rng_holdout[label]["why"] = (
                    "block landed at the body's own leading edge (offset 0): no text precedes it, "
                    "so removing it manufactures no discontinuity" if start == 0 else
                    "block landed at the body's own tail: no text follows it, so removing it "
                    "manufactures no discontinuity")
        else:
            if not synth_off:
                # A REAL AREA'S HOLDOUT ROUNDING TO ZERO IS A REFUSAL, NOT A SILENT SKIP (audit
                # finding, confirmed live). The `else` branch below is written for exactly one
                # reason -- "source=synthetic holds nothing out" -- and used to run unconditionally,
                # so a real corpus with DATA_VAL_CAP=0 (or a DATA_HOLDOUT_FRAC too small to clear one
                # byte) got that SAME false reason string stamped on a real disk area: reproduced,
                # DATA_SOURCE=real DATA_AREAS=eng,py DATA_VAL_CAP=0 came back with
                # rng_holdout['eng']['why'] == 'source=synthetic holds nothing out' on real text, no
                # refusal, no error. Goal A's one generalisation number and every
                # across-the-run-boundary comparison for this area would then have nothing held out
                # to be computed against, silently. Refused instead, naming both levers and the
                # arithmetic that zeroed the block.
                # AND A SYNTHETIC AREA AT DATA_SYNTH_HOLDOUT=1 IS REFUSED THE SAME WAY (2026-09-27,
                # Q-DATA-9): it runs the real sources' law, so a block that rounds to nothing is the
                # same failure there, and the OFF record below would stamp "holds nothing out" on a
                # run that asked for a block. Its message also names the lever that asked.
                raise CorpusError(
                    f"area {label!r} computed a 0-byte held-out block: min(int({len(blob)} * "
                    f"{float(dat.holdout_frac)}), {int(dat.val_cap)}) == 0 from DATA_HOLDOUT_FRAC="
                    f"{dat.holdout_frac} and DATA_VAL_CAP={int(dat.val_cap)} against a "
                    f"{len(blob)}-byte body. Refused rather than trained on with no held-out block "
                    f"at all: raise DATA_HOLDOUT_FRAC or DATA_VAL_CAP."
                    + (" DATA_SOURCE=synthetic at DATA_SYNTH_HOLDOUT=1 carves under the real "
                       "sources' law and is refused the same way; DATA_SYNTH_HOLDOUT=0 is the "
                       "synthetic arm that holds nothing out." if str(dat.source) == "synthetic"
                       else ""))
            holdout[label] = b""
            bodies[label] = blob
            # THE OFF RECORD NAMES THE LEVER THAT MADE IT (2026-09-27, Q-DATA-9): since the synthetic
            # source can hold a block out, "source=synthetic holds nothing out" is no longer a
            # property of the source but of DATA_SYNTH_HOLDOUT=0 on it. The key, offset, size and
            # seam are unchanged, and they are what restore_stream_state compares.
            rng_holdout[label] = {"key": None, "offset": 0, "size": 0, "seam_at": None,
                                  "why": "DATA_SYNTH_HOLDOUT=0 holds nothing out on this source"}
        holdout_bytes[label] = len(holdout[label])
        cursors[label] = 0

    # ---- THE DID IT FIRE SURFACE THIS FUNCTION DECLARES ------------------------------------------
    # Built here, at the end, from tallies taken at the decision points above -- so a name whose
    # branch never ran reads as a measured 0 and a name whose mechanism CANNOT run on this
    # configuration reads as UNREACHABLE with the lever and value that made it so. Before this block
    # existed, both read as nothing at all, and a reader could not tell "the cap never bit" from
    # "there is no cap on this arm" from "nobody wrote the counter".
    synthetic = str(dat.source) == "synthetic"
    n_entries = len(entries)
    counters = {
        # A READING, NOT A GATE, AND THE DOCSTRING SAYS SO IN AS MANY WORDS: the near-duplicate
        # fraction per area (Lee et al. arXiv:2107.06499). It is read back out of `rng_holdout`
        # rather than recomputed here, so there is ONE measurement with two places to find it and
        # not two measurements that can disagree.
        #
        # THREE STATES IN A READING THAT CANNOT BE A Gate. A float is the measured fraction. `None`
        # is the UNDEFINED reading _holdout_overlap returns when the block is shorter than one
        # n-gram window -- not a measured 0.0. An area that HAS NO BLOCK AT ALL is a third thing
        # again, and returning None for it too would collapse "undefined on the block we drew" into
        # "there was no block", so that arm carries its own sentence instead. This is the same
        # three-way distinction Gate makes, spelled into the value because the contract above
        # declares this row a reading and not a gate, and contradicting that would be worse.
        "data.holdout_overlap": {
            label: (rng_holdout[label]["overlap"] if "overlap" in rng_holdout[label]
                    else f"no block to measure -- {rng_holdout[label].get('why', 'none drawn')}")
            for label in names},
    }

    gates = []
    if synthetic:
        gates.append(Gate(
            "data.area_open", False, None, n_entries, reachable=False,
            reason="DATA_SOURCE=synthetic: no directory is opened at all -- every area is generated "
                   "by data/api.py::_synthetic_areas -- so 'areas opened from disk' has no value to "
                   "read here rather than a value of zero"))
        gates.append(Gate(
            "data.area_nested", False, None, n_entries, reachable=False,
            reason="DATA_SOURCE=synthetic: a DATA_AREAS entry never becomes a filesystem path on "
                   "this arm, so nothing is joined under DATA_DIR and 'nested' is not a property "
                   "this configuration has"))
        gates.append(Gate(
            "data.area_path_refused", False, None, n_entries, reachable=False,
            reason="DATA_SOURCE=synthetic: the absolute-or-'..' refusal is scoped to the real-corpus "
                   "branch on purpose, because refusing an entry that never becomes a path would be "
                   "refusing a LABEL rather than a path -- so there is no check here to have "
                   "refused nothing"))
        gates.append(Gate(
            "data.corpus_cap_trip", False, None, int(dat.corpus_cap), reachable=False,
            reason=f"DATA_SOURCE=synthetic: each area is generated to the size the sampler needs and "
                   f"nothing is read off disk, so DATA_CORPUS_CAP={int(dat.corpus_cap)} truncates "
                   f"nothing and bytes_present == bytes_taken by construction, not by measurement"))
        if synth_off:
            # THE HELD-OUT PAIR IS UNREACHABLE ON THIS ARM ONLY AT DATA_SYNTH_HOLDOUT=0 (2026-09-27,
            # Q-DATA-9), and the reason now names that lever and not the source: at 1 the synthetic
            # source carves under the real sources' law, and both gates take the real arm below.
            gates.append(Gate(
                "data.holdout_block", False, None, n_entries, reachable=False,
                reason="DATA_SOURCE=synthetic at DATA_SYNTH_HOLDOUT=0: this arm holds nothing out, so "
                       "no block is drawn and no data.holdout.<key> child stream is minted for any "
                       "area -- an area with no child in rng.issued() never asked for a block, which "
                       "is a different statement from a block of size zero. DATA_SYNTH_HOLDOUT=1 "
                       "carves one per area under the real sources' law"))
            gates.append(Gate(
                "data.val_cap_trip", False, None, int(dat.val_cap), reachable=False,
                reason=f"DATA_SOURCE=synthetic at DATA_SYNTH_HOLDOUT=0: with nothing held out there "
                       f"is no block for DATA_VAL_CAP={int(dat.val_cap)} to bind, so the cap is not "
                       f"armed-and-inert here -- it has nothing to be armed against"))
    else:
        gates.append(Gate(
            "data.area_open", n_open > 0, n_open, n_entries,
            reason="an entry that produced no usable bytes is REFUSED above rather than dropped, so "
                   "on this source the count reaches the entry count or startup did not finish"))
        gates.append(Gate(
            "data.area_nested", n_nested > 0, n_nested, n_entries,
            reason="a zero here is the STATEMENT 'every area came from DATA_DIR/train/', which is "
                   "the shipped default; a nonzero count is the entries joined under DATA_DIR "
                   "verbatim by the slash rule (Q-DATA-4), which is what makes data/continual/* and "
                   "data/ood/* reachable without moving files on disk"))
        gates.append(Gate(
            "data.area_path_refused", False, 0, n_path_checked,
            reason="a refused entry raises CorpusError and exits at startup, so this row reads zero "
                   "in every Areas that exists; it is declared so the arbitrary-path refusal is a "
                   "NAMED mechanism rather than an unnamed assertion, and the threshold is how many "
                   "entries it looked at"))
        cap_detail = "; ".join(f"{label}: {taken[label]} taken of {present[label]} present"
                               for label in names)
        gates.append(Gate(
            "data.corpus_cap_trip", n_cap_trip > 0, n_cap_trip, len(names),
            reason=f"DATA_CORPUS_CAP={int(dat.corpus_cap)}, and the cap's bite is a PRINTED NUMBER "
                   f"per area rather than a warning about a default -- {cap_detail}"))
    if not synth_off:
        # THE HELD-OUT PAIR'S REAL ARM, taken by a real source and, since 2026-09-27, by the
        # synthetic one at DATA_SYNTH_HOLDOUT=1 (Q-DATA-9): the same law, so the same two gates.
        block_detail = "; ".join(
            f"{label}: {rng_holdout[label]['key']} offset {rng_holdout[label]['offset']} "
            f"size {rng_holdout[label]['size']}" for label in names)
        gates.append(Gate(
            "data.holdout_block", n_block > 0, n_block, len(names),
            reason=f"one CHILD stream per area, keyed by the area's label and not by draw order "
                   f"(Q-DATA-6) -- {block_detail}"))
        cap_arith = "; ".join(
            f"{label}: min({frac_bytes[label]}, {int(dat.val_cap)}) = {holdout_bytes[label]}"
            for label in names)
        gates.append(Gate(
            "data.val_cap_trip", n_val_cap > 0, n_val_cap, len(names),
            reason=f"DATA_VAL_CAP={int(dat.val_cap)} against int(body * "
                   f"DATA_HOLDOUT_FRAC={float(dat.holdout_frac)}) per area; the cap TRIPPED for an "
                   f"area exactly when it, and not the fraction, was the binding term -- "
                   f"{cap_arith}"))

    # RUNS FOR BOTH SOURCES, because the label and rng-key collision checks do: they were hoisted
    # above the source branch precisely so the synthetic arm could not reach an unchecked rng_for,
    # so declaring this gate unreachable on that arm would contradict the code above it.
    gates.append(Gate(
        "data.area_label_collision", False, 0, n_entries,
        reason="the label and rng-key collision checks run for BOTH sources, before the source "
               "branch; a collision raises CorpusError and exits, so this row reads zero in every "
               "Areas that exists and its threshold is the number of entries it compared"))
    # THE AREA-ID REFUSAL'S OWN ROW (2026-09-28, Q-FAB-18's review). The refusal landed with the id
    # and its name was declared above and nowhere written: no Gate, no counter, and neither the
    # message nor data.area_refused's reason named it, so the declared mechanism had no row in any
    # report. Its sibling's shape, for its sibling's reason.
    gates.append(Gate(
        "data.area_id_collision", False, 0, n_entries,
        reason="the area-id collision check (two labels on one spine/derive.py::area_id, the key "
               "FAB's area books and MEM's area column share) runs for BOTH sources, in the same "
               "loop as the label and rng-key checks; a collision raises CorpusError and exits, so "
               "this row reads zero in every Areas that exists and its threshold is the number of "
               "entries it compared"))
    gates.append(Gate(
        "data.area_refused", False, 0, n_entries,
        reason="every refusal in this function raises CorpusError and exits at startup -- an empty "
               "DATA_AREAS, a label, rng-key or area-id collision, an entry that escapes DATA_DIR, "
               "an area with no usable bytes, a body under the derived floor, an area whose "
               "held-out block rounded to zero (a real one, or a synthetic one at "
               "DATA_SYNTH_HOLDOUT=1), or DATA_N_PROCESSES out of range -- so this row reads zero "
               "in every Areas that exists. It is declared so a refusal is a named mechanism and "
               "not an assertion nobody counts"))

    # ONE SEAM GATE PER AREA, because the unreachable arm is a property of THAT AREA'S DRAW and not
    # of the configuration: a block that landed at the body's leading edge or at its tail manufactures
    # no discontinuity, which is not the same statement as "this area's removal left no seam". An
    # aggregate would have to choose one of the three states for a run whose areas disagree.
    for label in names:
        rh = rng_holdout[label]
        body_len = len(bodies[label])
        if rh["seam_at"] is not None:
            gates.append(Gate(
                f"data.holdout_seam[{label}]", True, rh["seam_at"], body_len,
                reason="removing a MIDDLE block leaves exactly one manufactured discontinuity in a "
                       "body DATA_SEG_CONTIG=1 reads in order; the value is where it is and the "
                       "threshold is the body it is in"))
        else:
            why = rh.get("why") or "no held-out block was drawn for this area"
            gates.append(Gate(
                f"data.holdout_seam[{label}]", False,
                # THE ARITHMETIC SURVIVES THE UNREACHABLE ARM where there IS one: an edge draw has a
                # real offset to print against the body length (leading edge reads 0, a tail read
                # reads the body's own length). An area with no block at all has no offset that
                # means anything, so it prints none rather than a zero that looks like a position.
                rh["offset"] if rh["size"] else None, body_len, reachable=False,
                reason=(f"DATA_SOURCE={dat.source}: {why}" if rh["size"] == 0
                        else f"the block's own drawn position, not a lever: {why}")))

    return Areas(names=names, bodies=bodies, holdout=holdout, holdout_bytes=holdout_bytes,
                 bytes_present=present, bytes_taken=taken, cursors=cursors,
                 rng_holdout=rng_holdout, counters=counters, gates=tuple(gates))


def _read_area(path, cap):
    """Every usable file under `path`, concatenated, up to `cap` bytes. Returns (bytes, present).

    SKIPS basenames starting with "_" and anything ending .json: fetch manifests were being spliced
    into the corpus and trained on as if they were English. `present` is the total the directory
    HOLDS, counted even past the cap, because the cap's bite has to be a printed number rather than
    a warning about a default.
    """
    if not os.path.isdir(path):
        return b"", 0
    out, present = bytearray(), 0
    for name in sorted(os.listdir(path)):
        if name.startswith("_") or name.endswith(".json"):
            continue
        f = os.path.join(path, name)
        if not os.path.isfile(f):
            continue
        n = os.path.getsize(f)
        present += n
        if len(out) < cap:
            with open(f, "rb") as fh:
                out += fh.read(cap - len(out))
    return bytes(out), present


def _holdout_overlap(holdout_bytes, body_bytes, n=50):
    """The fraction of `holdout_bytes`' n-gram windows (fixed length `n`) that also occur verbatim
    somewhere in `body_bytes` -- the near-duplicate-contamination reading open_areas' docstring
    declares as `data.holdout_overlap` and which, until this fix, was never computed anywhere in this
    file (audit finding, confirmed live: `grep -n holdout_overlap src/data/api.py` matched only the
    docstring's own declaration; no field anywhere carried a value).

    WHY THIS IS A DIFFERENT QUESTION FROM THE SPLIT RULE, which is the docstring's own citation and
    worth repeating here because it is the reason this function exists rather than a second use of
    the offset/size pair: Lee et al. (arXiv:2107.06499) measures that models "underestimate
    perplexity on evaluation documents with near duplicates" and that a benchmark "should actively
    remove contaminated training data, rather than just partitioning held out splits by documents".
    A held-out block can be a clean, non-overlapping byte range of ONE area and still be
    near-duplicated by material that reached the training body through some other channel (a mirrored
    file, a second copy under a different name) -- the split rule cannot see that, because it only
    ever looks at where bytes came from inside this one area.

    COST, STATED RATHER THAN DISCOVERED AT SCALE: building the body's n-gram set is one pass over
    `body_bytes` (measured: ~0.85s for a 2,000,000-byte body, the shipped DATA_CORPUS_CAP, on the
    machine this was written on); checking the holdout is then one pass over `holdout_bytes` against
    an O(1) membership test per window. A caller that raises DATA_CORPUS_CAP far past the shipped
    default pays proportionally more at startup for it, once, which is the same trade this package
    already makes for reading the corpus off disk in the first place.

    Returns None when the held-out block is too short to hold one n-gram -- an UNREACHABLE reading,
    not a 0.0: the fraction is undefined on fewer than `n` bytes, not measured-and-empty. Otherwise a
    float in [0, 1].
    """
    if len(holdout_bytes) < n:
        return None
    if len(body_bytes) < n:
        return 0.0
    windows = {body_bytes[i:i + n] for i in range(len(body_bytes) - n + 1)}
    total = len(holdout_bytes) - n + 1
    hits = sum(1 for i in range(total) if holdout_bytes[i:i + n] in windows)
    return hits / total


# The five alphabets from the old tree's synthetic generator: three of 15 symbols and two of 14 (it
# said "15-symbol" for all five until 2026-09-27). An area takes the one at its POSITION in the area
# list, mod five, as the old make_proc took ALPHA[s % len(ALPHA)] (_synthetic_areas).
_ALPHABETS = ("abcdefghijklmno", "pqrstuvwxyzABCD", "EFGHIJKLMNOPQRS",
              "TUVWXYZ0123456", "789!?.,;:'\"-()")


def _synthetic_length(seg_max, stream_bytes, n_processes):
    """One synthetic area's generated length, in bytes: max(DATA_SEG_MAX + 1, MIN_AREA_BYTES,
    DATA_STREAM_BYTES // DATA_N_PROCESSES) x 2.

    Enough text that the floor is clearable and a DATA_STREAM_BYTES stream can be drawn without the
    sampler wrapping: the areas are generated, so there is no corpus to be short. DATA_N_PROCESSES is
    known >= 1 wherever this runs (_synthetic_areas refuses 0 first), so it needs no max(1, n) clamp:
    DATA_N_PROCESSES=0 is a startup refusal, not a divide-by-zero guard wearing a clamp's clothes.

    ONE FORMULA FOR ITS TWO READERS (2026-09-27, Q-DATA-9's review). _synthetic_areas generates every
    area to this length, and restore_stream_state prints it when a synthetic block moved. At
    DATA_SYNTH_HOLDOUT=1 the block is carved out of a body of this length -- its size is a fraction of
    it and its offset is drawn over it -- so these three levers move EVERY synthetic area's block
    together: adding a fifth area at DATA_STREAM_BYTES 120000 takes each body from 60,000 bytes to
    48,000 and each block from 3,000 to 2,400. Pure arithmetic on the values passed; it reads no
    lever itself.

    UNIT IN: seg_max = bytes, stream_bytes = bytes, n_processes = count. UNIT OUT: bytes.
    """
    return max(int(seg_max) + 1, MIN_AREA_BYTES, int(stream_bytes) // int(n_processes)) * 2


def _synthetic_areas(dat, seed, entries, labels):
    """`dat.n_processes` order-2 Markov generators, one area each. Holds nothing out ITSELF: what it
    returns is each area's whole generated text, and open_areas carves the held-out block from it
    under the real sources' law when DATA_SYNTH_HOLDOUT asks for one (2026-09-27, Q-DATA-9).

    `labels` ARRIVES PRE-VALIDATED, computed once by open_areas for both sources (basename applied,
    checked against every OTHER entry for a label or rng-key collision) rather than derived twice and
    differently in here -- see open_areas' docstring for why that used to desynchronise the label
    space between the two source arms.

    SEEDED FROM THE RUN SEED, NOT FROM THE PROCESS INDEX. The old make_proc was seeded by the index
    alone, so `DATA_SOURCE=synthetic` measured a between-seed spread with the DATA HELD CONSTANT --
    every replicate saw byte-identical text and the spread it reported was the model's
    initialisation alone (DEFECT D-A13). Two run seeds are now two different corpora.

    ONE CHILD STREAM PER PROCESS, `data.synth.<label>`, AND `data.synth` IS A PARENT NOTHING DRAWS
    FROM -- the same shape Q-DATA-6 ruled for `data.holdout`, adopted here because the collision
    guard in spine/rng.py found the conflict: RUN.streams mints every name in RNG_SUBSYSTEMS so
    rng.issued() is a complete register at step 0, and this function drawing on `data.synth`
    directly is a SECOND generator for one name -- two call sites replaying one sequence while each
    believes it has its own. The per-child form fixes that and buys HALF the property Q-DATA-6 argues
    for on the other stream: an area's DRAWS stop being a function of how many areas were generated
    before it. Its ALPHABET does not, and this docstring said the whole property held until
    2026-09-27 (Q-DATA-9's review): the alphabet is _ALPHABETS[i % 5] by the area's position i, so
    inserting an entry, or reordering the list, still moves every later area's text -- relabelled
    where the two alphabets are the same size, drawn afresh where they are not. Driven: DATA_AREAS
    "eng,rust,py,num,c" against "eng,py,num,c" gives py, num and c other text. Keyed by position it
    stays, because the shipped four areas' text is keyed so and every synthetic run pairs with it;
    where a held-out block rides on the text, restore_stream_state refuses the move by name. The
    parent keeps its RNG_SUBSYSTEMS row and reports zero draws, which is the honest reading --
    declared, never drawn -- and is what `data.holdout` already does.
    """
    n = int(dat.n_processes)
    if n < 1:
        # REFUSED, NOT CLAMPED (audit finding, confirmed live). The old `max(1, n)` inside the
        # per_area arithmetic below let DATA_N_PROCESSES=0 through silently: reproduced,
        # `areas.names == ()` with no error, warning or refusal anywhere -- a run that would then
        # try to plan and draw a stream from zero areas. A clamp here would also make the banner
        # print a process count the run did not use, which this project's refusal rule forbids.
        raise CorpusError(
            f"DATA_N_PROCESSES={n}: at least one synthetic process is required to produce a "
            f"stream. Refused rather than silently returning zero areas.")
    if len(entries) < n:
        # REFUSED, NOT PAPERED OVER WITH INVENTED NAMES (audit finding, confirmed live). This used
        # to silently generate p0..p{n-1} whenever DATA_AREAS named fewer entries than
        # DATA_N_PROCESSES -- reproduced, `DATA_SOURCE=synthetic DATA_AREAS=eng
        # DATA_N_PROCESSES=4` gave `areas.names == ('p0','p1','p2','p3')` with the operator's one
        # requested area appearing nowhere and nothing in the log to say so. Every per-area score,
        # the holdout rng keys and DATA_PHASE_SCHED's by-name lookup are keyed by the DECLARED
        # name, so this was the desynchronised-label failure (ISSUES P3-C19) reached through this
        # arm's own fallback rather than through a dropped corpus.
        raise CorpusError(
            f"DATA_AREAS names {len(entries)} area(s) {tuple(entries)} but DATA_N_PROCESSES={n} "
            f"synthetic processes were requested. Refused rather than generating p0..p{n - 1} for "
            f"the areas nobody named: name at least {n} area(s) in DATA_AREAS, or lower "
            f"DATA_N_PROCESSES.")
    labels = labels[:n]
    # Enough text that the floor is clearable and the stream can be drawn without the sampler
    # wrapping; the arithmetic, and why it needs no max(1, n) clamp now that `n` >= 1 is refused
    # above, is _synthetic_length's, the one formula restore_stream_state prints as well.
    per_area = _synthetic_length(dat.seg_max, dat.stream_bytes, n)
    raw, present, taken, sources = {}, {}, {}, {}
    for i, label in enumerate(labels):
        stream = _rng.rng_for(f"data.synth.{_holdout_key(label)}", seed)
        alpha = _ALPHABETS[i % len(_ALPHABETS)]
        # ORDER 2: the next symbol is a function of the previous two, so the process has structure a
        # unigram model cannot reach and a domain router has something to separate.
        table = {}
        prev = (alpha[0], alpha[0])
        out = bytearray()
        while len(out) < per_area:
            row = table.get(prev)
            if row is None:
                row = table[prev] = [alpha[stream.randrange(len(alpha))] for _ in range(3)]
            ch = row[stream.randrange(len(row))]
            out += ch.encode("ascii")
            prev = (prev[1], ch)
        raw[label] = bytes(out)
        present[label] = len(out)
        taken[label] = len(out)
        sources[label] = f"synthetic:order2:{i}"
    return raw, present, taken, sources


@dataclasses.dataclass(frozen=True)
class Plan:
    """What this configuration will expose the model to, computed before a single step runs.

    `protocol` is RECOGNISED from the resolved schedule, never generated, and it is printed by name
    on every run -- one of four, never blank. That is the half D2 actually needed: the launcher
    writes pure-add as a schedule of names, and the report says which protocol ran.

    `counters` CARRIES THE DID IT FIRE READINGS THIS FUNCTION COMPUTES BUT ISN'T A Gate: how many
    phases the schedule resolved to (data.phase_resolved), the recognised protocol by name again
    under its counter key (data.protocol_named, for a report that greps counters rather than fields),
    and how many DATA_PHASE_SCHED entries were given as an area NAME rather than an index
    (data.phase_name_resolved -- 0 is the honest statement "every entry was an index", not silence).
    Added because the audit found the last of these computed and then discarded with no field to
    land in (n_by_name was incremented and never read again anywhere in this file).

    `faded` AND `parent_faded` ARE THE SCHEDULE'S STATEMENT OF WHICH AREAS HAVE FADED (2026-09-28,
    register §8 3.1, NEW-10 and C37; docs/04_CONTRACT.md Q-FAB-18), in the same index space as
    `schedule`. `faded[k]` is every area live in some phase before k and not live in phase k -- at
    derive.phase_schedule(4) over four areas, [(), (0,), (0,), (0, 1)] -- sorted by index, which is
    Plan order. `parent_faded` is every area this run declares that the resumed lineage's streams
    DREW from (Areas.drawn, as the record carried it) and that is live in NO phase of this run's
    schedule: the areas a child inherits the training of and never trains, faded from its first
    window -- () on a fresh run, whenever the child schedules every area the lineage drew, and on a
    continuing resume, whose schedule is its parent's. An area the parent declared and never drew
    is not in it (Q-FAB-18's review: it was read off Areas.parent_names, every DECLARED area, so a
    run over "eng,py" that scheduled eng alone handed its continuing child's passes py as faded
    where the uninterrupted run handed them nothing). Both are known at startup because the
    schedule is, and both are READINGS OF THE SCHEDULE WITHIN ONE EPOCH: an area only a previous
    epoch's later phases trained is not in phase 0's set when the schedule restarts, and a parent
    area the child schedules later is not faded before its phase -- Q-FAB-18 records both as what
    the rule does not see. FAB.manage is handed the union at each pass, as area ids.

    `shares` IS THE SPLIT THE DRAW LAYS, PER PHASE, UNDER EVERY LAW (2026-09-28, register §8 3.3;
    docs/04_CONTRACT.md Q-DATA-10): one tuple per phase of (area index, bytes) pairs in Plan order,
    each phase's summing to its span. Under 'planned' and 'uniform', and in every phase 'replay'
    does not lay, it is the scheduled split -- the phase's bytes over its live areas, the remainder
    on the first live areas -- which draw_stream's planned budget recomputes by the same rule; under
    'replay', a phase with a faded area carries the replay law's targets. `per_area_draw` is its sum
    over the phases, and draw_stream prints it beside what each phase drew (the share gauges).
    `replay_faded` is, per phase, the areas the 'replay' law gives DATA_REPLAY_SHARE to: `faded[k]`,
    plus `parent_faded` at DATA_REHEARSE_PARENT=1 -- () in every phase under 'planned' and 'uniform',
    and a phase whose tuple is empty is laid by the planned law. Both are known at startup, move no
    byte by themselves and are not checkpointed: a resume recomputes them from the same schedule and
    record.
    """
    protocol: str
    schedule: tuple
    phase_bounds: tuple
    per_area_draw: dict
    exposure: dict
    gates: tuple
    counters: dict = dataclasses.field(default_factory=dict)
    faded: tuple = ()
    parent_faded: tuple = ()
    shares: tuple = ()
    replay_faded: tuple = ()


@dataclasses.dataclass(frozen=True)
class Stream:
    """One epoch's bytes, with both boundary lists and the provenance MEM needs.

    BOTH LISTS LEAVE THIS PACKAGE so no consumer has to guess which one it wanted. `splice_starts`
    is every segment start; `area_changes` is the subset where the area actually changed. Scoring
    boundary precision against the first made all ~96 "true switches" artefacts on a one-area run.

    `draws` IS THE STREAM'S OWN DRAW COUNT (audit finding, confirmed live), carried out because the
    docstring's declared DID IT FIRE row -- `rng.issued()["data.stream.e0"].draws` -- cannot actually
    be evaluated: `rng.issued()` returns name -> (derived seed, run seed) TUPLES (spine/rng.py's own
    diagnostic register, deliberately not the live Rng, so nothing there can move a number the run
    produces), and the one Rng object with a real `.draws` was local to draw_stream and discarded on
    return. Reproduced: `rng.issued()['data.stream.e0'].draws` raised `AttributeError: 'tuple' object
    has no attribute 'draws'`. This field is what the docstring's claim now actually reads.

    `counters` AND `gates` CARRY THE DID IT FIRE SURFACE draw_stream DECLARES, split by the SAME one
    question `Areas` states: is there a configuration on which the mechanism CANNOT run? Every
    draw-time name here has one, and it is not hypothetical -- at DATA_RESAMPLE=0 every epoch past
    the first performs NO DRAW AT ALL, it returns this record again -- so `data.stream_draw`,
    `data.contig_wrap`, `data.resample` and `data.phase_entered` are `spine.gate.Gate`s, the only
    record in this tree that can say UNREACHABLE and carry the reason. `data.segment` is a reading in
    `counters` instead: it counts the segments THESE BYTES are spliced from, which is as true of a
    replayed Stream as of the draw that produced it, and wrapping a reading in a Gate prints "armed,
    did not fire" for a number that never had a condition to meet. So are SR0's per-phase share
    gauges (2026-09-28, register §8 3.3; docs/04_CONTRACT.md Q-DATA-10), under every law:
    `data.share.p<k>.<area>.planned` and `.realised`, the area's bytes in phase k as Plan.shares
    planned them and as these bytes hold them, each in permille of the phase's span.

    A REPLAY RE-STATES THE GATES AND KEEPS THE COUNTERS, and that split is the whole point of having
    both fields. The bytes are the first draw's and so is every reading about them; but "did THIS
    epoch draw" is a question about this call, and its answer is UNREACHABLE -- not the FIRED the
    first draw earned and not a measured zero either. See data/api.py::_replay_gates.
    """
    bytes: bytes
    labels: list
    splice_starts: tuple
    area_changes: tuple
    phase_bounds: tuple
    area_names: tuple
    per_area_drawn: dict
    epoch: int
    stream_id: str
    draws: int = 0
    counters: dict = dataclasses.field(default_factory=dict)
    gates: tuple = ()


def data_plan(dat: Config, areas, *, epochs: int, win_tokens: int, bytes_per_token: float):
    """Resolve the phase schedule and compute, BEFORE A SINGLE STEP RUNS, what this configuration
    will actually expose the model to.

    THE SCHEDULE. dat.phase_sched non-empty is parsed here and refused loudly at startup on an
    empty phase or an out-of-range area id (self_organize.py:1355-1366) -- validation lives at the
    parse site only, with no `[a for a in act if a < NP] or list(range(NP))` fallback, which was
    unreachable dead code that would have quietly re-enabled every area in a phase (ISSUES P1-L18).
    Empty generates derive.phase_schedule(n_areas, dat.phases, dat.phase_live), which at four
    areas is [[0,1],[1,2],[1,2],[2,3]] -- a REHEARSED sliding window, not pure add. dat.phases is
    floored at 2 AT THIS READ SITE: one phase cannot have anything fade and `faded` is read off the
    last phase, so PHASES=1 makes the unlearn test skip itself as vacuous.

    AN ENTRY MAY BE AN AREA NAME AS WELL AS AN INDEX (ruled 2026-09-02 with Q-DATA-7), resolved
    against Areas.names at this parse site and REFUSED loudly on a name no area carries, beside the
    existing refusal on an out-of-range index. "eng|eng|rust|rust" and "0|0|1|1" are the same
    schedule at DATA_AREAS="eng,rust". This is what closes D2 as a RESOLVER ruling rather than as a
    lever default: data/levers.py::DATALevers says "there is no literal string that means the added area
    alone independent of how many areas there are", and a name IS that string -- "rust|rust|rust|rust"
    is pure-add at any area count and does not silently become a different experiment when the area
    ORDER changes. It also ends the defect the harness carries in the open: longrun.sh:930-932
    hand-types _AI=1 under a comment claiming it is computed from the DOMAINS order, and nothing
    reads DOMAINS (ISSUES P1-L2).

    PLAN.PROTOCOL IS RECOGNISED, NOT GENERATED, and the four predicates are written out here so two
    P4 authors cannot disagree about them:
        phase_sched empty                                             -> "generated"
        explicit, ONE phase, every area live                          -> "stationary"
        explicit, n_areas > 1, every phase is the SAME single area    -> "pure_add"
        explicit, anything else                                       -> "explicit"
    Recognition costs no lever, no argument, no signature and no change to derive.phase_schedule,
    which is oracle-pinned (tests/test_derive.py, _phases 60 cases) and is the spine's, not this
    package's, to re-point. Generating pure-add from the area ORDER was refused: it makes position
    load-bearing with nothing stating it, and phase_sched="" already means "generate the rehearsed
    sliding window", so empty cannot mean both.

    THE DEFAULT, STATED BECAUSE IT IS THE OWNER'S RULING AND ITS SCOPE MATTERS. Pure-add is KEPT as
    the protocol of the add-an-area experiment (D2; the PHASE_SCHED census row names PURE_ADD in its
    couples_with and calls the rehearsed [[0],[0],[1],[1]] arm "the named comparison arm"). What is
    NOT done is flipping phase_sched="" to generate pure-add for every run: at the shipped
    DATA_AREAS="eng,py,num,c" the pure-add schedule streams ONE area and three declared corpora
    would never be trained on, silently -- an n-dependent default whose shape changes between n=2
    and n=4 is the M18 defect (a declared parent that is not the actual one) reproduced on the
    protocol. So the default of phase_sched is unchanged (empty = the rehearsed generator), pure-add
    is written by the launcher as a schedule of names, and Plan.protocol prints which one ran on
    every run -- which is the half D2 actually needed and the half that did not exist.
    WHAT WOULD SETTLE THE ARM: the two protocols disagreed 10x on the same toy (+0.046 HELD
    rehearsed vs +0.444 WORSE pure, data/levers.py::DATALevers). The run that retires the question is
    one pair at fixed seed and fixed DATA_AREAS="eng,<new>": arm R with PHASE_SCHED="eng|eng|<new>|<new>",
    arm P with PHASE_SCHED="<new>|<new>|<new>|<new>", reading ACROSS THE RUN BOUNDARY on eng's
    held-out block at the end of each. Rehearsal keeps eng trained, so only arm P measures what the
    fabric PRESERVES; if arm R's eng retention is not materially better than arm P's, rehearsal is
    buying nothing and pure-add is the honest default everywhere.

    THE EXPOSURE ARITHMETIC, per area: draw = stream_bytes distributed by the schedule;
    exposure = draw * epochs / body_bytes. It is a WHOLE-RUN quantity: 60 MB of English beside
    8 MB of Python draws 2.00 MB/epoch from each -- quiet -- while over 8 epochs the added area is
    seen 2.1x and the original is 28% sampled, and "adding py cost eng X bits/byte" is then
    confounded with "py was memorised and eng was skimmed" (ISSUES P3-H22).

    TWO OF THE THREE GATES' BOUNDS ARE REFUSED AT nan AND AT +inf, BEFORE THE SCHEDULE IS PARSED.
    At either value `max(vals) > bound` and `skew > bound` are False for every possible exposure, so
    the gate CANNOT fire while spine/gate.py::Gate's default reachable=True renders it as the middle
    state -- measured, "Gate data.exposure_max: armed, did not fire (0.75 vs nan)". That is the
    three-state collapse spine/gate.py exists to refuse, on the two guards D8 made exact. 0 and -inf
    are NOT refused: on both, the gate genuinely FIRES and the printed word is true. The refusal
    closes two values per lever and claims nothing beyond them -- a finite bound no exposure can
    reach (1e26) passes it and is exactly as uncrossable. See the block itself.

    THREE DECLARED GATES, each printing its own arithmetic so "did not fire" is distinguishable
    from "could not fire":
      data.exposure_max     max(exposure) > dat.exposure_max. COMPUTED AT ONE AREA TOO: both reads
                            sat inside `if DATA_MODE == "real" and NP > 1`, so the check was
                            unavailable on exactly the single-area goal-A configuration where
                            accidental repetition is easiest to reach (ISSUES P1-L21).
      data.exposure_skew    max/min > dat.exposure_skew. Declared UNREACHABLE at n_areas == 1 with
                            the reason printed -- a max/min ratio over one area is undefined.
      data.splice_window    mean_segment_bytes / (win_tokens * bytes_per_token) < 8. The one place
                            the byte/token boundary is crossed, and it is crossed with the MEASURED
                            bytes/token handed in, never with an estimate (ISSUES P1-H16).

    THE FADED SETS (2026-09-28, register §8 3.1, NEW-10 and C37; docs/04_CONTRACT.md Q-FAB-18).
    Plan.faded[k] is every area live in a phase before k and not live in phase k; Plan.parent_faded
    is every area the resumed lineage's streams drew from (Areas.drawn, filled by
    restore_stream_state before this call; since Q-FAB-18's review, and not Areas.parent_names,
    every area the parent merely declared) that no phase of this schedule makes live. Both are
    index tuples in Plan order, computed here because the schedule is; the root hands their union to
    FAB.manage at each pass as area ids. Neither moves a byte of the stream.

    THE SPLIT EACH PHASE IS LAID IN, Plan.shares, UNDER EVERY LAW (2026-09-28, register §8 3.3;
    docs/04_CONTRACT.md Q-DATA-10): per phase, (area index, bytes) pairs summing to the phase's
    span. Under 'planned' and 'uniform' it is the scheduled split above, per phase, and
    Plan.per_area_draw is its sum over the phases, exactly as before it existed.
    THE 'replay' LAW (Proposal 04 §1 item 2; register 04-Q1, 04-Q4, O9, O16), BUILT OFF. A phase k
    with a faded area -- Plan.faded[k], plus Plan.parent_faded from window 0 at dat.rehearse_parent,
    the pair in Plan.replay_faded[k] -- gives round(dat.replay_share x span) bytes to its faded
    areas, split evenly; at dat.replay_newest > 0 the newest-arrived live area (the latest first
    live phase, ties to the last in Plan order) takes round((replay_share + replay_newest) x span)
    minus that; the other live areas split the rest evenly. Every rounding is half to even on the
    DECIMAL the lever holds (Fraction(repr(value)): 0.07 of a 150-byte phase is 10.5 and rounds to
    10, where the float product 10.500000000000002 rounds to 11) and every remainder falls on the
    first areas in Plan order, so the targets are integers that sum to the span and a hand can
    recompute them. A phase with no faded area is 'planned' and reads neither share. replay_share +
    replay_newest above 1 is refused by name: no phase can give away more bytes than it has.
    Plan.per_area_draw is then the replay targets' sum, and because draw_stream truncates every
    segment to its area's target, the two exposure gates stay EXACT under 'replay' (04 §1 item 2) --
    the caveat names it so. A faded phase whose only live area is the newest gives it the whole live
    remainder: the boost has no other live area to take bytes from. dat.rehearse_parent has NO
    EFFECT under 'planned' or 'uniform' (04-Q4), and Plan.parent_faded is the same reading either
    way: FAB's count reads it whatever the law.

    RECEIVES: epochs <- RUN.epochs; win_tokens <- LM.ctx; bytes_per_token <- TOK, measured by
    derive.bytes_per_token after build_vocabulary. All three are arguments: bytes_per_token cannot
    be a wire (measured after freeze, the reason assemble.NOT_WIRES gives for the SIG width).
    RETURNS: Plan.

    LEVERS READ: phase_sched, phases, phase_live, stream_bytes, seg_min, seg_max, exposure_max,
                 exposure_skew, draw, replay_share, replay_newest (both only under 'replay'),
                 rehearse_parent (under every law, for its Gate's reason; it moves bytes only under
                 'replay')
    WIRES READ: none
    DID IT FIRE: data.phase_resolved, data.protocol_named (the recognised protocol, printed by
                 name -- one of the four, never blank), data.phase_name_resolved (entries given as
                 a NAME rather than an index; 0 means every entry was an index, which is the
                 shipped spelling and a statement rather than silence), data.phase_faded (a
                 READING: per phase, the names of the areas faded in it -- [[], ['eng'], ['eng'],
                 ['eng', 'py']] at the shipped four areas), data.parent_faded (a READING, present
                 only where a parent record was restored and ABSENT on a fresh run: the areas the
                 lineage drew that no phase of this run makes live),
                 Gate data.exposure_max, Gate data.exposure_skew -- EXACT under the shipped
                 DATA_DRAW="planned" and under "replay" (2026-09-28), and a PREDICTION under
                 "uniform", where the run trains on a random draw from the scheduled split that
                 deviated by up to 47.9% per area over eight seeds. The caveat rides on the gate's
                 `reason` and not on its name, so a report can be grepped across every arm (ISSUES
                 P1-H58, ruled),
                 Gate data.splice_window,
                 data.replay.fixed_phases (the phases the 'replay' law lays: a faded area and a
                 nonzero span), data.replay.bytes (the bytes per epoch it gives faded areas) --
                 both ABSENT unless DATA_DRAW=replay, and 0 there when no phase has a faded area --
                 and data.replay.newest_boosted (the faded phases whose newest-arrived live area took
                 DATA_REPLAY_NEWEST beside another live area; ABSENT unless DATA_DRAW=replay with
                 DATA_REPLAY_NEWEST above 0, where the boost is armed), Gate data.replay
                 (UNREACHABLE naming DATA_DRAW under 'planned' and 'uniform'; its value the fixed
                 phases, against the phase count), data.rehearse_parent.areas (the parent areas the
                 draw rehearses from window 0; ABSENT unless DATA_DRAW=replay at
                 DATA_REHEARSE_PARENT=1 on a resume, the one configuration that arms it), Gate
                 data.rehearse_parent (UNREACHABLE at DATA_REHEARSE_PARENT=0, under 'planned' or
                 'uniform' where it has no effect, and on a fresh run, which has no parent record;
                 its value the rehearsed areas, against the lineage's drawn areas this run declares)
                 -- all six added 2026-09-28 (Q-DATA-10), and both Gates printed at R in the
                 root's DATA(plan.gates) row
    """
    dat = dat.owned_by("DATA")

    # ==============================================================================================
    # THE TWO EXPOSURE BOUNDS, REFUSED AT nan AND AT +inf, BEFORE THE SCHEDULE IS PARSED
    # ==============================================================================================
    # WHY THIS IS A REFUSAL AND NOT A GATE `reason`. Both bounds are read exactly once each, at the
    # two Gate constructions below, as `max(vals) > float(dat.exposure_max)` and
    # `skew > float(dat.exposure_skew)`. spine/gate.py::Gate's own docstring fixes what the three
    # states mean: "fired=False, reachable=True means the mechanism ran and its condition was not met
    # -- a measurement. reachable=False means the condition CANNOT be met on this configuration,
    # which is not a measurement at all." At a nan bound EVERY comparison is False, for every
    # possible exposure, and at a +inf bound no finite exposure can exceed it -- so on both values
    # the gate CANNOT fire and the default reachable=True renders it as the middle state. MEASURED on
    # this tree at the shipped DATA_AREAS="eng,py,num,c", before this refusal landed:
    #     DATA_EXPOSURE_MAX=nan   -> Gate data.exposure_max: armed, did not fire (0.75 vs nan)
    #     DATA_EXPOSURE_MAX=inf   -> Gate data.exposure_max: armed, did not fire (0.75 vs inf)
    #     DATA_EXPOSURE_SKEW=nan  -> Gate data.exposure_skew: armed, did not fire (3.0 vs nan)
    #     DATA_EXPOSURE_SKEW=inf  -> Gate data.exposure_skew: armed, did not fire (3.0 vs inf)
    # Four confident verdicts over a guard that refused nothing and could refuse nothing. A `reason`
    # would not fix it -- the caveat two paragraphs down already rides on `reason`, and it is a
    # sentence beside a verdict that is still printed. Nor is reachable=False the honest repair: the
    # skew gate's own unreachable arm at n_areas == 1 is STRUCTURAL (a max/min ratio over one area is
    # undefined and no lever can change that), while this is an out-of-range value the operator
    # typed, and this tree refuses those by name at the first read.
    #
    # AND THESE TWO GATES SPECIFICALLY, BECAUSE OF WHAT D8 BOUGHT. ISSUES P1-H58 is the record of
    # these gates testing the SCHEDULED per-area split while the run trained on a random draw from
    # it, deviating up to 47.9% per area over eight seeds. DATA_DRAW was minted to close that, and
    # data/levers.py::DATALevers says why "planned" is the default in as many words: "It is the only
    # value under which the startup gate is EXACT, and a startup gate is the only thing that can
    # refuse a bad configuration BEFORE it spends the GPU time." A bound that no value can cross
    # gives back exactly what D8 paid for -- the gate becomes untestable again, and this time the
    # report says "armed" rather than carrying a caveat. (Since 2026-09-28 'replay' is exact the same
    # way, Q-DATA-10, so the refusal protects it too; it is built OFF, and 'planned' stays the
    # default by D8 and register O16.)
    #
    # WHAT IS NOT REFUSED, AND IT IS MEASURED RATHER THAN ASSUMED. -inf AND 0 ARE LEFT ALONE ON BOTH
    # LEVERS. They are the "flag every plan" configuration, and on both the arithmetic and the
    # printed word are true:
    #     DATA_EXPOSURE_MAX=-inf  -> Gate data.exposure_max: FIRED (0.75 vs -inf)
    #     DATA_EXPOSURE_MAX=0     -> Gate data.exposure_max: FIRED (0.75 vs 0.0)
    #     DATA_EXPOSURE_SKEW=-inf -> Gate data.exposure_skew: FIRED (3.0 vs -inf)
    #     DATA_EXPOSURE_SKEW=0    -> Gate data.exposure_skew: FIRED (3.0 vs 0.0)
    # Neither 0 nor -inf is a DECLARED sentinel -- data/levers.py::DATALevers says only "above which
    # the data plan is flagged" -- and this refusal does not mint one for them. It refuses the two
    # values on which the gate prints a verdict its own arithmetic contradicts, and leaves the two on
    # which it does not. Refusing -inf as well would remove a configuration that today behaves
    # correctly and reports correctly, which is the untrippable-guard class inverted.
    #
    # NO SWITCH. ckpt/api.py::REFUSE_NEGATIVE_PERIOD states that a range refusal getting a switch "is
    # NOT a precedent" and names lm/api.py::resolve, opt/api.py::build and capacity/api.py::new_valve
    # as refusing out-of-range lever values with none. This is one of those.
    #
    # WHAT THIS REFUSAL DOES NOT CLAIM, AND THE MEASUREMENT THAT BOUNDS IT. It closes two values per
    # lever. It does NOT make either bound safe, validated or in range: a FINITE value does the same
    # damage. DATA_EXPOSURE_MAX=1e26 is finite, passes this check, and no exposure this package can
    # compute will ever reach it, so the gate is exactly as unreachable as it is at +inf while the
    # printed threshold looks like an ordinary number -- and the same measurement one package over is
    # what the ruling turns on (FAB_ALPHA=1e26: aux 0.5150710, composed 2.943258, 15 of 23
    # gradient-carrying tensors already non-finite, an ordinary-looking loss pair over a poisoned
    # population, WORSE than +inf). A declared per-lever domain is the general answer to that and it
    # is the owner's open question, not this function's. What is closed here is four cells.
    #
    # THE OTHER DATA FLOAT IS NOT IN THIS SWEEP AND IS NOT EXEMPT: DATA_HOLDOUT_FRAC at nan and at
    # +/-inf raises out of data/api.py::open_areas -- `int(len(blob) * float(dat.holdout_frac))` --
    # which runs BEFORE this function and refuses badly, with a bare ValueError/OverflowError naming
    # no lever. That is a defect in open_areas and it is filed, not fixed here; putting a second
    # check for it in data_plan would be an untrippable guard, because open_areas has already raised.
    _bad = []
    for _field in ("exposure_max", "exposure_skew"):
        _v = float(getattr(dat, _field))
        if math.isnan(_v) or _v == math.inf:
            _bad.append((dat.lever(_field).env_name, _v))
    if _bad:
        raise LeverError(
            f"DATA: unusable exposure bound(s) "
            f"{', '.join(f'{k}={v}' for k, v in _bad)}. An exposure bound is the value a measured "
            f"exposure is compared AGAINST, and neither a nan nor a positive infinity is a value any "
            f"exposure can cross: `max(vals) > nan` and `skew > nan` are False for every possible "
            f"reading, and no finite exposure exceeds +inf. The gate is therefore UNREACHABLE and "
            f"spine/gate.py::Gate is handed the default reachable=True, so it prints the middle "
            f"state -- measured on this tree at the shipped four areas: "
            f"'Gate data.exposure_max: armed, did not fire (0.75 vs nan)' and "
            f"'Gate data.exposure_skew: armed, did not fire (3.0 vs inf)'. That is a verdict its own "
            f"arithmetic contradicts, in the one instrument that stands between goal B's "
            f"add-an-area experiment and ISSUES P3-H22, where an added area seen 2.1x while the "
            f"original was 28% sampled made 'adding py cost eng X b/B' indistinguishable from 'py "
            f"was memorised and eng was skimmed'. THESE TWO GATES ARE ALSO WHAT DECISION D8 BOUGHT: "
            f"DATA_DRAW defaults to 'planned' because, in data/levers.py::DATALevers's own words, "
            f"that 'is the only value under which the startup gate is EXACT, and a startup gate is "
            f"the only thing that can refuse a bad configuration BEFORE it spends the GPU time' -- a "
            f"bound nothing can cross hands that back ('replay', built OFF on 2026-09-28, is exact "
            f"the same way, and the bound guards it too). NEITHER LEVER DECLARES A NON-FINITE MEANING: "
            f"data/levers.py::DATALevers says only 'above which the data plan is flagged' for "
            f"exposure_max and 'above which the data plan is flagged as imbalanced' for "
            f"exposure_skew, and there is no inf branch anywhere in this file. WHAT IS STILL "
            f"ACCEPTED, so the refusal is not read as wider than it is: 0 and -inf both make the "
            f"gate FIRE on every plan, and both print the truth while doing it -- measured, "
            f"'Gate data.exposure_max: FIRED (0.75 vs 0.0)' and 'FIRED (0.75 vs -inf)'. That "
            f"configuration is left exactly as it was. WHAT THIS REFUSAL DOES NOT CLAIM: it closes "
            f"two values per lever and leaves the bound otherwise unbounded. DATA_EXPOSURE_MAX=1e26 "
            f"is finite, passes this check, and is just as uncrossable as +inf while printing as an "
            f"ordinary number. A declared per-lever domain is the general answer and it is open. Set "
            f"the lever to a finite bound the exposure can actually reach -- the shipped values are "
            f"DATA_EXPOSURE_MAX=2.0 and DATA_EXPOSURE_SKEW=3.0 -- or to 0 to flag every plan. WHAT "
            f"THE ENVIRONMENT SUPPLIED: "
            + ", ".join(f"{k}={v!r}" for k, v in sorted(dat.given().items())
                        if k in ("exposure_max", "exposure_skew")) + ".")

    from spine import derive as _derive
    names = list(areas.names)
    n_areas = len(names)
    by_name = {n: i for i, n in enumerate(names)}

    raw = str(dat.phase_sched).strip()
    n_by_name = 0
    if raw:
        # VALIDATION LIVES AT THE PARSE SITE ONLY. The old `[a for a in act if a < NP] or
        # list(range(NP))` fallback was unreachable dead code that would have quietly re-enabled
        # EVERY area in a phase if it ever ran (ISSUES P1-L18) -- a silent widening of the
        # experiment, in the one lever that decides what the experiment is.
        schedule = []
        for k, part in enumerate(raw.split("|")):
            live = []
            for tokstr in part.split(","):
                tokstr = tokstr.strip()
                if not tokstr:
                    continue
                # AN ENTRY MAY BE A NAME AS WELL AS AN INDEX (Q-DATA-7). A name IS the string that
                # means "the added area alone" at any area count: "rust|rust|rust|rust" is pure-add
                # whether there are two areas or four, and it does not silently become a different
                # experiment when the area ORDER changes -- which is the failure the harness carries
                # in the open, hand-typing _AI=1 under a comment claiming it reads DOMAINS.
                if tokstr in by_name:
                    live.append(by_name[tokstr])
                    n_by_name += 1
                elif tokstr.lstrip("-").isdigit():
                    idx = int(tokstr)
                    if not 0 <= idx < n_areas:
                        raise CorpusError(
                            f"DATA_PHASE_SCHED phase {k} names area index {idx}, and there are "
                            f"{n_areas} area(s): {names}. Refused at the parse site.")
                    live.append(idx)
                else:
                    raise CorpusError(
                        f"DATA_PHASE_SCHED phase {k} names {tokstr!r}, which is neither an area "
                        f"index nor one of {names}. Refused at the parse site.")
            if not live:
                raise CorpusError(
                    f"DATA_PHASE_SCHED phase {k} is empty. A phase with no live area streams "
                    f"nothing; refused rather than skipped.")
            schedule.append(tuple(dict.fromkeys(live)))
        schedule = tuple(schedule)
    else:
        # FLOORED AT 2 AT THIS READ SITE. One phase cannot have anything FADE, and `faded` is read
        # off the last phase, so PHASES=1 makes the unlearn test skip itself as vacuous while every
        # report line still prints.
        schedule = tuple(tuple(p) for p in _derive.phase_schedule(
            n_areas, max(2, int(dat.phases)), int(dat.phase_live) or None))

    # RECOGNISED, NOT GENERATED. The four predicates are written out because two P4 authors reading
    # the same paragraph must not disagree about them.
    if not raw:
        protocol = "generated"
    elif len(schedule) == 1 and len(schedule[0]) == n_areas:
        protocol = "stationary"
    elif n_areas > 1 and len({p for p in schedule}) == 1 and len(schedule[0]) == 1:
        protocol = "pure_add"
    else:
        protocol = "explicit"

    # THE PHASE FILL IS EXACT: phase k covers [round(k*B/P), round((k+1)*B/P)).
    total = int(dat.stream_bytes)
    n_phases = len(schedule)
    bounds = tuple((round(k * total / n_phases), round((k + 1) * total / n_phases))
                   for k in range(n_phases))

    # THE FADED SETS, READ OFF THE SCHEDULE AT STARTUP (2026-09-28, register §8 3.1, NEW-10 and C37;
    # docs/04_CONTRACT.md Q-FAB-18). An area has FADED in phase k when some phase before k had it
    # live and phase k does not: the set FAB.manage counts culls and merges of experts against, and
    # the set §8 3.3's 'replay' draw gives its share to (below). Accumulated phase by phase, so an
    # area that fades, returns and fades again is faded exactly in the phases it is absent from after
    # it was first live. Sorted by index, which is Plan order, so no reader iterates a set. (Computed
    # before the split since 2026-09-28, Q-DATA-10: the 'replay' targets are cut from it.)
    _seen, _faded = set(), []
    for live in schedule:
        _faded.append(tuple(sorted(_seen - set(live))))
        _seen |= set(live)
    faded = tuple(_faded)
    # AND THE LINEAGE'S: an area this run declares, which the resumed lineage's streams DREW from
    # (Areas.drawn, filled by restore_stream_state one row above this one), and which NO phase of
    # this schedule makes live -- a pure-add child's parent areas, faded from its first window. A
    # DECLARED AREA IS NOT A DRAWN ONE (Q-FAB-18's review): this read Areas.parent_names, every area
    # the record declares, so a parent over "eng,py" that scheduled eng alone left py faded in its
    # continuing child -- whose schedule is the parent's -- and that child's passes were handed a
    # set the uninterrupted run's never were. This run's own draws come after this call, and each is
    # of an area some phase of this schedule makes live, so they could not enter it either way. A
    # recorded area this run does not declare cannot reach here: restore_stream_state refuses it.
    _parent = {str(n) for n in (getattr(areas, "drawn", None) or ())}
    parent_faded = tuple(i for i, n in enumerate(names) if n in _parent and i not in _seen)

    # THE SPLIT EACH PHASE IS LAID IN, Plan.shares, UNDER EVERY LAW (2026-09-28, register §8 3.3;
    # docs/04_CONTRACT.md Q-DATA-10). The scheduled split first, phase by phase, by the one rule
    # draw_stream's planned budget recomputes: the phase's bytes split evenly among its live areas,
    # with the remainder on the first, so the per-area bytes sum to the phase span exactly. It was
    # summed straight into per_area_draw until this date; per_area_draw is now its sum over the
    # phases, the same numbers in the same key order, so under 'planned' and 'uniform' nothing
    # this function returns moved.
    law = str(dat.draw)
    cuts = []
    for (lo, hi), live in zip(bounds, schedule):
        span = hi - lo
        cut = {}
        for j, idx in enumerate(live):
            cut[idx] = cut.get(idx, 0) + span // len(live) + (1 if j < span % len(live) else 0)
        cuts.append(cut)

    # THE 'replay' LAW (Proposal 04 §1 item 2; register 04-Q1, 04-Q4, O9, O16), BUILT OFF. Each
    # phase with a faded area -- Plan.faded[k], and Plan.parent_faded from window 0 at
    # DATA_REHEARSE_PARENT=1 -- is re-cut: DATA_REPLAY_SHARE of its bytes to those areas, split
    # evenly, DATA_REPLAY_NEWEST to the newest-arrived live area where set, the rest evenly over the
    # other live areas (_replay_cut). A phase with no faded area keeps the scheduled split above and
    # draw_stream lays it by the planned law, verbatim. THE TWO SHARES ARE READ ONLY UNDER 'replay'
    # -- here, and by its caveat and Gate below -- so under 'planned' and 'uniform' neither is read
    # and the cut above is the whole of the split.
    # rehearse_parent is read under every law, for its Gate below: it has NO EFFECT but under
    # 'replay' (04-Q4), and Plan.parent_faded is the same reading either way, because FAB's
    # faded-area count reads it whatever the law.
    rehearse = bool(dat.rehearse_parent)
    replay_faded = tuple(() for _ in schedule)
    n_fixed = n_boosted = faded_bytes = 0
    if law == "replay":
        share, newest_share = _exact_share(dat.replay_share), _exact_share(dat.replay_newest)
        if share + newest_share > 1:
            # REFUSED BY NAME, BEFORE A BYTE IS CUT. A phase cannot give its faded areas and its
            # newest area more than all of its bytes, and a clamp would lay a split nobody asked for
            # while the banner printed the one they did.
            raise LeverError(
                f"DATA: DATA_REPLAY_SHARE={float(dat.replay_share)} and "
                f"DATA_REPLAY_NEWEST={float(dat.replay_newest)} sum to {float(share + newest_share)}, "
                f"above 1. Under DATA_DRAW=replay each phase with a faded area gives the first to its "
                f"faded areas and the second to its newest-arrived live area, and the other live "
                f"areas split what is left, so the two together are at most the whole phase. Lower "
                f"one of them (04 section 1 item 2's control is 0.27 with 0.34, leaving 0.39 for the "
                f"other live areas).")
        # PARENT AREAS ARE FADED FROM WINDOW 0 at DATA_REHEARSE_PARENT=1 (04-Q4, O9). They are live in
        # no phase, so no phase's own faded set holds them and the two never overlap.
        from_parent = parent_faded if rehearse else ()
        replay_faded = tuple(tuple(sorted(set(f) | set(from_parent))) for f in faded)
        # WHO ARRIVED LAST: each area's first live phase, read off this run's schedule. Ties go to the
        # last area in Plan order -- an add-an-area run appends its new area (Q-DATA-9) -- and
        # max() over the phase's live TUPLE with an explicit key is the whole rule: no set, no dict
        # order.
        first = {}
        for k, live in enumerate(schedule):
            for i in live:
                first.setdefault(i, k)
        for k, ((lo, hi), live) in enumerate(zip(bounds, schedule)):
            if not replay_faded[k]:
                continue
            span = hi - lo
            newest = max(live, key=lambda i: (first[i], i))
            # THE BOOST NEEDS ANOTHER LIVE AREA TO TAKE BYTES FROM. A phase whose only live area is
            # the newest gives it the whole live remainder, 1 - DATA_REPLAY_SHARE, whatever the boost.
            boost = newest_share > 0 and len(live) > 1
            cuts[k] = _replay_cut(span, replay_faded[k], live, newest if boost else None, share,
                                  newest_share)
            faded_bytes += sum(cuts[k][i] for i in replay_faded[k])
            if span > 0:
                n_fixed += 1
                n_boosted += 1 if boost else 0
    # (area index, bytes) pairs in Plan order, per phase: the record's form, which a reader walks in
    # one order whatever order the cut was built in.
    shares = tuple(tuple(sorted(cut.items())) for cut in cuts)

    per_area_draw = {n: 0 for n in names}
    for cut in shares:
        for idx, n_bytes in cut:
            per_area_draw[names[idx]] += n_bytes

    # A WHOLE-RUN QUANTITY, WHICH IS THE POINT. 60 MB of English beside 8 MB of Python draws 2 MB
    # from each per epoch -- quiet -- while over 8 epochs the added area is seen 2.1x and the
    # original is 28% sampled, and "adding py cost eng X b/B" is then confounded with "py was
    # memorised and eng was skimmed".
    exposure = {n: (per_area_draw[n] * int(epochs) / max(1, len(areas.bodies[n]))) for n in names}

    gates = []
    vals = [exposure[n] for n in names]
    # WHICH LAW ALLOCATES THE BYTES DECIDES WHETHER THESE GATES ARE EXACT (P1-H58, ruled by the
    # owner 2026-09-02: it became DATA_DRAW, and "planned" is the default).
    #   planned -> draw_stream gives every area its scheduled share, so `per_area_draw` IS what the
    #              run trains on and the gate below is a MEASUREMENT.
    #   uniform -> draw_stream picks an area independently per segment, so the run trains on a DRAW
    #              from this distribution and the gate is a PREDICTION. Measured over eight seeds at
    #              the shipped defaults the worst per-area deviation was 47.9%, and a gate reading
    #              "armed, did not fire" on a split the run did not train on is a true sentence
    #              about the wrong number -- in the guard against P3-H22, where an added area seen
    #              2.1x while the original was 28% sampled made "adding py cost eng X b/B"
    #              indistinguishable from "py was memorised and eng was skimmed".
    #   replay  -> (2026-09-28, Q-DATA-10) draw_stream truncates every segment to its area's replay
    #              target, so `per_area_draw` -- the targets' sum -- IS what the run trains on, and the
    #              gate is a MEASUREMENT again, as 04 section 1 item 2 requires.
    # ONE GATE NAME UNDER EVERY LAW. A report whose keys change with the configuration cannot be
    # grepped across arms, which costs more than the caveat it would save, so the caveat rides on
    # the gate's own `reason` -- which spine/gate.py prints on every arm for exactly this case.
    if law == "planned":
        caveat = ""
    elif law == "uniform":
        caveat = (
            "DATA_DRAW=uniform: this is the SCHEDULED split and the run trains on a random draw from "
            "it (measured deviation up to 47.9% per area), so read it as a prediction and read "
            "Stream.per_area_drawn for what happened.")
    else:
        caveat = (
            f"DATA_DRAW=replay: this split is EXACT, as under 'planned' -- the replay law's per-phase "
            f"targets (Plan.shares), DATA_REPLAY_SHARE={float(dat.replay_share)} of each phase with "
            f"a faded area to its faded areas, and draw_stream truncates every segment to its "
            f"area's target, so Stream.per_area_drawn equals it byte for byte.")
    # COMPUTED AT ONE AREA TOO. Both old reads sat inside `if DATA_MODE == "real" and NP > 1`, so
    # the check was unavailable on exactly the single-area goal-A configuration where accidental
    # repetition is easiest to reach (ISSUES P1-L21).
    gates.append(Gate("data.exposure_max", max(vals) > float(dat.exposure_max),
                      round(max(vals), 4), float(dat.exposure_max), reason=caveat))
    if n_areas == 1:
        gates.append(Gate("data.exposure_skew", False, None, float(dat.exposure_skew),
                          reachable=False,
                          reason="a max/min ratio over ONE area is undefined; this gate cannot "
                                 "fire on a single-area run and says so rather than reading 0"))
    else:
        skew = max(vals) / min(vals) if min(vals) > 0 else float("inf")
        gates.append(Gate("data.exposure_skew", skew > float(dat.exposure_skew),
                          round(skew, 4), float(dat.exposure_skew), reason=caveat))
    mean_seg = (int(dat.seg_min) + int(dat.seg_max)) / 2.0
    # THE ONE PLACE THE BYTE/TOKEN BOUNDARY IS CROSSED, and it is crossed with the MEASURED
    # bytes/token handed in, never with an estimate (ISSUES P1-H16).
    windows_per_segment = mean_seg / (int(win_tokens) * float(bytes_per_token))
    # A STARTUP PREDICTION, NEVER A MEASUREMENT, AND MORE OPTIMISTIC THAN THE REALIZED DRAW UNDER
    # THE SHIPPED LAW (audit finding, confirmed by an 8-seed, 4-phase-count sweep at pure defaults).
    # mean_seg above is the NAIVE (seg_min+seg_max)/2, computed here because data_plan runs BEFORE a
    # single byte is drawn -- draw_stream does not exist to measure from yet, so this cannot become
    # "measured, not estimated" the way bytes_per_token above already is (ISSUES P1-H16) without
    # moving the check to after the draw, which would make it a report line instead of a startup
    # gate. Under DATA_DRAW="planned" (the shipped default) draw_stream truncates a segment to BOTH
    # the phase bound (as "uniform" already did) AND the drawing area's remaining per-phase budget
    # (new in this law), so the realized mean segment length runs measurably below this naive mean
    # more often than under "uniform": at DATA_AREAS=eng,py,num,c / LM_CTX=128 / a measured
    # bytes/token near 1.213, this gate read "armed, did not fire" at every one of 8 tested seeds
    # while the REALIZED windows-per-segment (from the actual draw) was below the 8.0 threshold at
    # all 8 -- a false-negative pattern that pre-existed "planned" (6/8 seeds under "uniform" on the
    # same sweep) but that this default measurably worsens (8/8), and the gap widens with phase
    # count (7.6%/10.4%/17.7%/32.3% mean relative gap under "planned" at 8/10/20/40 phases, against
    # 3.7%/4.9%/10.0%/17.9% under "uniform" at the same phase counts -- roughly double, throughout).
    # Stated here rather than left implicit, the way exposure_max/exposure_skew's `caveat` already
    # states the same law's effect on THOSE two gates: a "did not fire" reading near 8.0 is
    # optimistic under either law and MORE optimistic under the shipped one, and should be
    # corroborated by inspecting the actual Stream draw rather than trusted alone. UNDER 'replay'
    # (2026-09-28) the same truncation runs to each area's replay target, and a faded area's
    # smaller target cuts its segments shorter still, so the sentence is added there.
    splice_caveat = (
        "data.splice_window is a STARTUP PREDICTION from the declared seg_min/seg_max mean, never "
        "measured from the actual draw (data_plan runs before a single byte is drawn). Under "
        "DATA_DRAW=planned (the shipped default) draw_stream additionally truncates segments to "
        "each area's remaining per-phase budget, so the realized mean segment length runs "
        "measurably below this estimate -- measured over an 8-seed sweep at the shipped defaults, "
        "'armed, did not fire' here read true on 8/8 seeds while the realized windows-per-segment "
        "was already below 8.0 on all 8; the gap widens with phase count. A reading near the "
        "threshold should be corroborated against the actual Stream draw, not trusted alone.")
    if law == "replay":
        splice_caveat += (
            " DATA_DRAW=replay truncates the same way, each segment to its area's replay target, and "
            "a faded area's smaller target cuts its segments shorter still.")
    gates.append(Gate("data.splice_window", windows_per_segment < 8.0,
                      round(windows_per_segment, 3), 8.0, reason=splice_caveat))

    # THE 'replay' LAW'S OWN GATE (2026-09-28, Q-DATA-10). UNREACHABLE under the two laws that lay
    # no fixed rehearsal share, naming the lever; under 'replay' its value is the phases the law
    # lays against the phase count, and armed-but-zero is the schedule with no faded phase, which
    # 'replay' lays as 'planned' throughout.
    if law != "replay":
        gates.append(Gate(
            "data.replay", False, None, n_phases, reachable=False,
            reason=f"DATA_DRAW={law}: the fixed-rehearsal law lays no phase on this configuration, so "
                   f"'phases laid under it' is not a number this run has; DATA_DRAW=replay gives each "
                   f"phase with a faded area a fixed DATA_REPLAY_SHARE of its bytes for its faded "
                   f"areas (Proposal 04 section 1 item 2, built OFF)"))
    else:
        laid = "; ".join(
            f"phase {k}: {', '.join(names[i] for i in replay_faded[k])} "
            f"{sum(cuts[k][i] for i in replay_faded[k])} of {bounds[k][1] - bounds[k][0]} bytes"
            for k in range(n_phases) if replay_faded[k])
        boosted = (f", DATA_REPLAY_NEWEST={float(dat.replay_newest)} to its newest-arrived live area "
                   f"in {n_boosted} of them" if float(dat.replay_newest) > 0 else "")
        gates.append(Gate(
            "data.replay", n_fixed > 0, n_fixed, n_phases,
            reason=(f"DATA_REPLAY_SHARE={float(dat.replay_share)} of each phase with a faded area goes "
                    f"to its faded areas{boosted}, laid by deficit and truncated to each area's "
                    f"target -- {laid}" if n_fixed else
                    "no phase of this schedule has a faded area (every area live in an earlier "
                    "phase is live again, and no parent area is rehearsed), so every phase is laid "
                    "by the planned law, byte for byte as DATA_DRAW=planned lays it")))

    # THE PARENT'S AREAS (2026-09-28, register 04-Q4 and O9; Q-DATA-10). Three arms cannot rehearse
    # one, each its own sentence: the lever off (every training and measurement run), a law with no
    # rehearsal share (04-Q4: no effect under 'planned'), and a fresh run, which has no parent record.
    # Armed, the value is the areas made faded from window 0 against the lineage's drawn areas this
    # run declares, and armed-but-zero is a child that schedules every one of them.
    lineage = [i for i, n in enumerate(names) if n in _parent]
    has_parent = bool(getattr(areas, "parent_names", None))
    if not rehearse:
        gates.append(Gate(
            "data.rehearse_parent", False, None, len(lineage), reachable=False,
            reason="DATA_REHEARSE_PARENT=0 (the shipped value, and the value of every training and "
                   "measurement run, register O9): no area of a resumed lineage is made faded from "
                   "window 0, so none is rehearsed; at 1 with DATA_DRAW=replay the lineage's drawn "
                   "areas this schedule never makes live share each phase's DATA_REPLAY_SHARE"))
    elif law != "replay":
        gates.append(Gate(
            "data.rehearse_parent", False, None, len(lineage), reachable=False,
            reason=f"DATA_REHEARSE_PARENT=1 has no effect under DATA_DRAW={law} (register 04-Q4): "
                   f"only the 'replay' law gives faded areas a share of a phase, so a parent area "
                   f"this schedule never makes live draws no byte; DATA_DRAW=replay rehearses it"))
    elif not has_parent:
        gates.append(Gate(
            "data.rehearse_parent", False, None, len(lineage), reachable=False,
            reason="no parent record: a fresh run, whose areas carry no lineage, so there is no "
                   "parent area to rehearse; a run resumed from a checkpoint (CKPT_RESUME) reads "
                   "the areas its lineage drew off the record"))
    else:
        gates.append(Gate(
            "data.rehearse_parent", len(parent_faded) > 0, len(parent_faded), len(lineage),
            reason=(f"DATA_DRAW=replay at DATA_REHEARSE_PARENT=1: "
                    f"{', '.join(names[i] for i in parent_faded)} -- drawn by the lineage and live in "
                    f"no phase of this schedule -- faded from window 0, sharing "
                    f"DATA_REPLAY_SHARE={float(dat.replay_share)} of every phase" if parent_faded else
                    f"every area the lineage drew that this run declares "
                    f"({', '.join(names[i] for i in lineage) or 'none'}) is live in some phase of "
                    f"this schedule, so none is faded from window 0")))

    # PHASE_NAME_RESOLVED, CARRIED OUT RATHER THAN COMPUTED AND DISCARDED (audit finding, confirmed
    # live: n_by_name was incremented above and never read again anywhere in this file -- Plan had
    # no field for it and DATA declares no counters() entry point, so the docstring's declared
    # data.phase_name_resolved row had no value anywhere to report). 0 is the shipped, honest
    # reading -- "every entry was an index" -- and it can now actually be printed as that statement
    # rather than silence.
    counters = {"data.phase_resolved": len(schedule), "data.protocol_named": protocol,
                "data.phase_name_resolved": n_by_name}

    # BOTH FADED SETS ARE PRINTED BY NAME, as READINGS. data.phase_faded on every run (phase 0's is
    # always empty, and a stationary or pure-add schedule's are all empty, which is a statement about
    # the schedule and not silence); data.parent_faded only where there is a parent record to read,
    # so a fresh run leaves it ABSENT rather than printing an empty list that would read "a parent
    # was checked and nothing it trained was left out".
    counters["data.phase_faded"] = [[names[i] for i in f] for f in faded]
    if getattr(areas, "parent_names", None):
        counters["data.parent_faded"] = [names[i] for i in parent_faded]
    # THE 'replay' LAW'S COUNTS, ABSENT WHERE IT CANNOT RUN (2026-09-28, Q-DATA-10). The phases it
    # lays and the bytes per epoch it gives faded areas are PRESENT at DATA_DRAW=replay -- 0 where no
    # phase has a faded area -- and ABSENT under 'planned' and 'uniform'. The newest-area boost is
    # armed only at DATA_REPLAY_NEWEST above 0 (04's table: OFF at 0), so its count is ABSENT at 0 as
    # well, and 0 where it is armed and no faded phase had another live area to take bytes from.
    if law == "replay":
        counters["data.replay.fixed_phases"] = n_fixed
        counters["data.replay.bytes"] = faded_bytes
        if float(dat.replay_newest) > 0:
            counters["data.replay.newest_boosted"] = n_boosted
        # THE PARENT'S COUNT, armed only on a resume at DATA_REHEARSE_PARENT=1 -- the configuration
        # its Gate reads reachable on -- and ABSENT everywhere else.
        if rehearse and has_parent:
            counters["data.rehearse_parent.areas"] = len(parent_faded)

    return Plan(protocol=protocol, schedule=schedule, phase_bounds=bounds,
                per_area_draw=per_area_draw, exposure=exposure, gates=tuple(gates),
                counters=counters, faded=faded, parent_faded=parent_faded, shares=shares,
                replay_faded=replay_faded)


def _exact_share(value):
    """A DATA share lever as the exact DECIMAL it was written as: Fraction(repr(float(value))).

    UNIT: fraction in, Fraction out. WHY NOT THE FLOAT (2026-09-28, Q-DATA-10): the 'replay' targets
    are round(share x span) bytes, rounded half to even, and a float's last bit decides a tie --
    0.07 of a 150-byte phase is 10.5, which rounds to 10, while the float product
    10.500000000000002 rounds to 11. repr() is the shortest decimal that round-trips, so it is the
    value the operator wrote (DATA_REPLAY_SHARE=0.27 is 27/100), and every target is then a number a
    hand can recompute. The lever's domain (0.0, 1.0) has already refused nan and the infinities.
    """
    return Fraction(repr(float(value)))


def _replay_cut(span, faded, live, newest, share, newest_share):
    """One faded phase's targets under 'replay': {area index: bytes}, summing to `span` exactly.

    UNIT: span = bytes; share, newest_share = exact fractions of the span (_exact_share); out =
    bytes per area. The faded areas get round(share x span), split evenly with the remainder on the
    first in `faded`'s order (Plan order); `newest`, when given, gets round((share + newest_share) x
    span) minus that; the other live areas, in Plan order, split what is left evenly the same way.
    `newest` is None when the boost is off or has no other live area to take bytes from, and then
    every live area splits the live remainder. Rounding is monotone and share + newest_share is at
    most 1 (data_plan refuses above), so no target is negative and the three parts are the span.
    """
    cut = {}
    to_faded = round(share * span)
    for j, i in enumerate(faded):
        cut[i] = to_faded // len(faded) + (1 if j < to_faded % len(faded) else 0)
    rest = sorted(live)
    to_live = span - to_faded
    if newest is not None:
        to_newest = round((share + newest_share) * span) - to_faded
        cut[newest] = to_newest
        rest = [i for i in rest if i != newest]
        to_live -= to_newest
    for j, i in enumerate(rest):
        cut[i] = to_live // len(rest) + (1 if j < to_live % len(rest) else 0)
    return cut


def draw_stream(dat: Config, areas, plan, *, epoch: int, seed: int):
    """Build one epoch's stream. Called once per epoch by the composition root, UNCONDITIONALLY --
    dat.resample is read HERE, not by the caller. At resample=False the same Stream object is
    returned for every epoch after the first (a byte-identical replay, which the old tree also did
    but only said so in a warning), and data.resample counts the redraws.

    Segments of _rng.randint(dat.seg_min, dat.seg_max) bytes are drawn from an area chosen
    according to dat.draw (P1-H58):
      "planned" (the shipped default) -- uniformly among the phase's live areas THAT STILL HAVE
        REMAINING BUDGET, and the segment is truncated to that budget as well as to the phase bound.
        So the realized per-area split equals Plan.per_area_draw exactly, and TWO consequences
        follow that the uniform law does not have: the area distribution shifts through a phase as
        areas exhaust their share, and a minority of segments come out SHORTER than seg_min (at the
        shipped defaults, about 4% of them, down to ~171 bytes). Both are the price of the realized
        split matching the scheduled one, and they are stated here rather than discovered.
      "uniform" -- uniformly among all the phase's live areas, every segment a full
        randint(seg_min, seg_max). This is the law every recorded result was taken under.
      "replay" (2026-09-28, register §8 3.3; docs/04_CONTRACT.md Q-DATA-10; built OFF) -- a phase
        whose Plan.replay_faded entry is EMPTY is laid by the planned law above, verbatim, so a
        schedule with no faded phase draws exactly what "planned" draws and phase 0 of any schedule
        without parent rehearsal is byte-identical to it. A phase with a faded area is laid by
        DEFICIT against its Plan.shares targets (Proposal 04 section 1 item 2): each segment goes to
        the area with the largest target x (phase bytes laid so far) - span x (its bytes laid so
        far) -- the scaled form of "target share x phase bytes so far - realised", in integers --
        among the areas with target left, the first in Plan order on a tie, and it is truncated to
        that area's remaining target as "planned" truncates to its budget. So the realised split
        is the planned one byte for byte, the rehearsal bytes are spread through the phase rather
        than front-loaded (the uniform-among-budgets pick of "planned" would lay a small faded
        budget early), and the choice takes no draw: segment lengths and offsets come from the
        same data.stream.e<epoch> stream and nothing iterates a set or a dict's hash order, so
        the stream is the same under every PYTHONHASHSEED (04's minor m1).
    dat.seg_contig=False seeks to a random offset inside the area body each segment; True reads the
    body in order from a cursor that PERSISTS ACROSS EPOCHS, so an English-only run has only the
    text's own boundaries rather than discontinuities we manufacture every 8-20 KB
    (self_organize.py:1291-1298 -- eng_only reported 71 domains partly by counting our own seek
    points). The default is False and is a LITERAL, not a computed default: the shipped
    `1 if NP == 1 else 0` resolved to 0 on both shipped configurations.

    THE PHASE FILL IS EXACT: phase k covers [round(k*B/P), round((k+1)*B/P)) and the final segment
    of a phase is TRUNCATED to the bound rather than overshooting it by a whole 700-1800 byte
    segment, so phase bounds do not drift and len(Stream.bytes) == dat.stream_bytes exactly
    (ISSUES P1-L22).

    The generator is rng_for(f"data.stream.e{epoch}", seed): what text a run trains on depends on
    the seed and the epoch and nothing else, so two arms differing in one unrelated knob still read
    the same text at epoch 2, and a resume at epoch 5 reads what an uninterrupted run read at
    epoch 5. The old form read SEED out of os.environ from INSIDE the stream builder
    (self_organize.py:1375-1392), which is the L2 violation this replaces.

    `area_changes` is the subset of splice starts where the area actually CHANGED. The old tree
    scored boundary precision/recall against every splice start including consecutive segments from
    the same area, so on a one-area run all ~96 'true switches' were artefacts (ISSUES P1-H10). BOTH
    lists leave this package so no consumer has to guess which one it wanted.

    Stream carries an `epoch` and a `stream_id` so MEM can invalidate or re-base provenance rather
    than silently carrying byte offsets into a stream that no longer exists (ISSUES P1-M83).

    EVERY AREA A DRAW TAKES A BYTE FROM IS APPENDED TO Areas.drawn, in place, where the list does not
    hold it yet (2026-09-28, Q-FAB-18's review): the lineage's record of what it drew, which
    stream_state carries and a child's Plan.parent_faded is read off.

    RETURNS: Stream.

    LEVERS READ: stream_bytes, seg_min, seg_max, seg_contig, resample, draw
    WIRES READ: none
    DID IT FIRE: EVERY NAME BELOW IS CARRIED OUT ON THE RETURNED `Stream`, exactly once, and which
                 field it lands in follows the rule the Areas record states: a name with a
                 configuration on which the mechanism CANNOT run is a Gate in `Stream.gates`,
                 because Gate is the only record here that can say UNREACHABLE and carry the reason;
                 a name that is always evaluable is a reading in `Stream.counters`.
                 Gate data.stream_draw (the bytes THIS call drew, against DATA_STREAM_BYTES;
                 a measured 0 is a draw that was armed and drew nothing, which the replay arm below
                 is not),
                 data.segment (a READING in `counters`: how many segments these bytes are spliced
                 from -- as true of a replayed Stream as of the draw that made it, so it is not a
                 gate),
                 data.share.p<k>.<area>.planned and .realised (READINGS in `counters`, under every
                 law, 2026-09-28, Q-DATA-10: SR0's per-phase share gauges, the area's bytes in phase
                 k as Plan.shares planned them and as these bytes hold them, in permille of the
                 phase's span, rounded half up, for every area the phase makes live, gives a target
                 or drew from; a phase of no bytes has no share to read and prints none. Equal under
                 "planned" and "replay" by construction, and under "uniform" the difference is the
                 draw's error bar, per phase. A reading about the bytes, so the resample-off
                 replay below carries them over with data.segment),
                 Gate data.contig_wrap (unreachable at seg_contig=False, with the gate arithmetic:
                 a random-offset seek is bounded by the body it reads and there is no cursor to
                 wrap, so 0 there is not a count),
                 Gate data.resample (unreachable at resample=False -- the "every epoch is a
                 byte-identical replay" state, STATED rather than warned about),
                 Gate data.phase_entered (must equal len(schedule) per epoch or the fill is
                 drifting),
                 Stream.draws (0 draws = armed-but-inert; NOT rng.issued()["data.stream.e<n>"].draws
                 -- issued() returns (derived seed, run seed) tuples with no .draws attribute, so
                 that expression is an AttributeError and Stream carries the real reading instead;
                 audit finding, confirmed live)
                 THE REPLAY ARM IS THE UNREACHABLE ONE, and it is a shipped configuration rather
                 than a hypothetical: at DATA_RESAMPLE=0 (the default) every epoch past the first
                 returns the first draw's Stream, so all four gates are RE-STATED unreachable
                 naming the lever and the epoch (data/api.py::_replay_gates) instead of being
                 carried over reading FIRED for a draw this epoch did not perform.
    """
    dat = dat.owned_by("DATA")
    # RESAMPLE IS READ HERE, NOT BY THE CALLER. The composition root calls this once per epoch
    # UNCONDITIONALLY, so "every epoch is a byte-identical replay" is a statement this function
    # makes rather than a branch the root takes -- and RUN.startup_refusals already refuses
    # epochs > 1 with resampling off, because a continual-learning result taken that way is a
    # memorisation result.
    if int(epoch) > 0 and not bool(dat.resample):
        # ID-KEYED, SO THE HIT MUST BE CONFIRMED AGAINST A LIVE REFERENCE, NOT JUST THE ADDRESS.
        # CPython reuses a freed object's id, and a plain `_REPLAY.get(id(areas))` cannot tell this
        # run's Areas from a PRIOR run's Areas that happened to land on the same address -- measured:
        # freeing one Areas and building a fresh one reused the id within single-digit allocations in
        # this process. `ref() is areas` is the check that turns "same address" back into "same
        # object" before the stale run's bytes could be handed to this one.
        entry = _REPLAY.get(id(areas))
        if entry is not None and entry[0]() is areas:
            # THE REPLAY'S DID IT FIRE IS NOT THE DRAW'S, and letting `dataclasses.replace` carry
            # the draw's over would be the exact collapse spine/gate.py::Gate exists to refuse --
            # worse than it, in fact. `replace` copies every field, so without this line the
            # returned Stream would hand the report "Gate data.stream_draw: FIRED (120000 vs
            # 120000)" for an epoch that drew nothing at all: not two states printed as one, but a
            # positive reading for a mechanism that did not run. `counters` is deliberately carried
            # over UNCHANGED, because data.segment is a reading about the BYTES -- how many segments
            # they are spliced from -- and these are the same bytes.
            return dataclasses.replace(
                entry[1], epoch=int(epoch),
                gates=_replay_gates(dat, plan, entry[1], int(epoch)))

    names = list(areas.names)
    seg_min, seg_max = int(dat.seg_min), int(dat.seg_max)
    if seg_min < 1 or seg_max < seg_min:
        # REFUSED AT THE TOP, NAMING BOTH NUMBERS. DATA_SEG_MIN=DATA_SEG_MAX=0 hung the draw
        # forever, and DATA_SEG_MIN > DATA_SEG_MAX passed every startup gate and then died inside
        # the loop with a bare ValueError from randint naming no lever. A segment of no bytes is not
        # a small segment, it is a stream that cannot advance.
        raise CorpusError(
            f"DATA_SEG_MIN={seg_min} and DATA_SEG_MAX={seg_max}: a segment must be at least one "
            f"byte and the minimum may not exceed the maximum. Refused here rather than clamped, "
            f"because a clamp would make the banner print a segment length the run did not use.")
    # WHAT TEXT A RUN TRAINS ON DEPENDS ON THE SEED AND THE EPOCH AND NOTHING ELSE. Two arms
    # differing in one unrelated knob still read the same text at epoch 2, and a resume at epoch 5
    # reads what an uninterrupted run read at epoch 5. The old form read SEED out of os.environ
    # from INSIDE the stream builder, which is the L2 violation this replaces.
    #
    # NO again=True HERE, AND THAT WAS THE BUG (audit finding, confirmed live). This call used to pass
    # again=True unconditionally, with no rebuild in sight to justify it -- "data.stream" is not in
    # compose.RNG_SUBSYSTEMS, nothing pre-mints "data.stream.e<n>", so there was no pre-existing
    # registration to work around, only the ordinary rng.py guard against two call sites sharing one
    # sequence. Reproduced: calling draw_stream(epoch=0, seed=0) twice in one process with again=True
    # returned two Rng objects whose .bytes came back byte-IDENTICAL, silently -- no RngError, no sign
    # anywhere that the "second" epoch-0 draw was a replay of the first rather than an independent one.
    # This function's own docstring says it is "Called once per epoch by the composition root,
    # UNCONDITIONALLY", so under correct usage the guard would never have tripped anyway; what
    # again=True bought was permission for a caller BUG (a retry after a downstream exception, a
    # duplicate call in a loop) to pass silently instead of raising the RngError this project relies
    # on everywhere else to catch exactly this two-call-sites-one-sequence shape (three prior instances
    # -- lm.init, tok.dropout.mint, data.synth.<label> -- were already repaired with a child stream;
    # this was the site that still had the guard itself switched off rather than a genuine rebuild
    # path). If a real rebuild ever needs it (a resume that redraws the epoch it was interrupted in,
    # inside the SAME process rather than a fresh one), pass again=True only on that path and say so
    # at the call site -- not unconditionally on every draw.
    stream = _rng.rng_for(f"data.stream.e{int(epoch)}", seed)

    out = bytearray()
    labels, splice, changes = [], [], []
    per_area = {n: 0 for n in names}
    # MUTATE areas.cursors IN PLACE -- NOT A COPY (audit finding, rated critical, confirmed live).
    # `cursors = dict(areas.cursors)` used to take a COPY here; the copy was advanced below but never
    # written back anywhere, and Stream never carried it out either, so every subsequent call to
    # draw_stream re-read the SAME all-zero areas.cursors open_areas produced. Reproduced at
    # DATA_SOURCE=real DATA_AREAS=eng DATA_SEG_CONTIG=1 DATA_RESAMPLE=1 DATA_STREAM_BYTES=40000
    # RUN_EPOCHS=8: epoch-0 and epoch-1 Stream.bytes came back byte-IDENTICAL in full, and
    # areas.cursors stayed {'eng': 0} after both calls -- an 8-epoch run under this configuration
    # sees the same ~40,000-byte prefix of the body on every epoch and never reaches the other
    # ~150,000 bytes, exactly the P3-H22-shaped repetition data.exposure_max_planned exists to catch,
    # while that gate itself reads a WHOLE-RUN quantity computed from stream_bytes and never sees the
    # realized collapse to one 40,000-byte prefix. `Areas` is a frozen DATACLASS but `cursors` is an
    # ordinary mutable dict VALUE -- frozen only refuses reassigning the `cursors` ATTRIBUTE, not
    # mutating the dict it points to -- which is why the field is a dict and not a tuple: binding the
    # SAME dict object here (not copying it) means every write below lands on the one `areas.cursors`
    # the composition root holds across every epoch's call, which is what "PERSISTS ACROSS EPOCHS"
    # (this function's own docstring) and stream_state's "LOAD-BEARING... without them a resume
    # re-reads the head of every area" (stream_state's docstring) both require.
    cursors = areas.cursors
    last_area = None
    contig = bool(dat.seg_contig)
    # THE DID IT FIRE TALLIES, TAKEN AT THE DECISION POINT THAT OWNS EACH ONE rather than
    # reconstructed from the returned Stream afterwards -- the same rule open_areas' surface follows
    # and for the same reason: `n_phase_entered` counts phases this loop actually entered, which is
    # a different number from len(plan.schedule) exactly when the fill is drifting, and
    # reconstructing it from the schedule would manufacture the agreement the gate exists to check.
    n_wrap, n_phase_entered = 0, 0

    # WHICH LAW ALLOCATES THE BYTES (DATA_DRAW; P1-H58, ruled by the owner 2026-09-02).
    #   planned -- the shipped default -- gives each live area its SCHEDULED SHARE of the phase and
    #     randomises only which order the segments come in and where in the body each is read from.
    #     `Plan.per_area_draw` is then what the run actually trains on, so data_plan's exposure gates
    #     are exact rather than predictive.
    #   uniform picks an area independently per segment. That is the law every recorded result in
    #     this project was taken under, and it is kept for exactly that reason -- but under it the
    #     realized split is a DRAW from the scheduled one, and the worst per-area deviation measured
    #     over eight seeds at the shipped defaults was 47.9%.
    #   replay (2026-09-28, Q-DATA-10; built OFF) lays each phase Plan.replay_faded names by DEFICIT
    #     against the phase's Plan.shares targets, and every other phase by the planned law,
    #     verbatim. Each phase is laid by ONE of three branches, its `mode`; 'planned' and 'uniform'
    #     name their own mode in every phase, so the two laws run the statements, and take the
    #     draws, they took before 'replay' existed.
    law = str(dat.draw)
    fixed_by_phase = tuple(plan.replay_faded) if law == "replay" else ()
    # SR0's SHARE GAUGES (2026-09-28, Q-DATA-10), under every law: per phase, per area, the bytes
    # Plan.shares planned beside the bytes these segments laid, in permille of the phase. Readings
    # tallied from the chunks below; nothing here draws, and no branch reads them.
    gauges = {}
    for k, ((lo, hi), live) in enumerate(zip(plan.phase_bounds, plan.schedule)):
        # THE PLANNED LAW'S REMAINING BUDGET, per area, in the same shares data_plan computed. It is
        # recomputed here from the phase span rather than read off Plan.per_area_draw because that
        # field is the WHOLE-RUN total across every phase an area appears in; taking a phase's share
        # out of a whole-run total is the kind of arithmetic that silently drifts. Both use the same
        # rule -- floor division with the remainder on the first live areas -- so the two agree by
        # construction and not by coincidence. (Since 2026-09-28 Plan.shares states each phase's
        # split directly, by that rule; the budget is still recomputed here, so the planned law runs
        # the statements it ran before, and tests/test_draw.py holds the two equal.)
        #
        # ACCUMULATED, NOT ASSIGNED, AND THE FIRST VERSION ASSIGNED (found by the H58 review). A phase
        # whose live list repeats an index -- schedule ((2, 0, 0, 1),) -- gave area 0 two shares in
        # data_plan, which accumulates, and ONE in this loop, which overwrote. Measured on that
        # schedule: data_plan said eng 60,000 / num 30,000 and the draw produced eng 30,000 /
        # num 60,000, so 25% of the run went to the wrong area -- the exact per-area exposure
        # corruption H58 exists to catch, committed by H58's own repair. The comment above claimed
        # the two "agree by construction", which is what made it worth checking.
        span = hi - lo
        budget = {}
        for j, idx in enumerate(live):
            budget[idx] = budget.get(idx, 0) + span // len(live) + (1 if j < span % len(live) else 0)
        # THE PHASE'S LAW. Under 'replay', a phase with a faded area is laid by deficit and every
        # other phase by the planned law; the other two laws are their own mode in every phase.
        fixed = fixed_by_phase[k] if k < len(fixed_by_phase) else ()
        mode = "deficit" if fixed else ("planned" if law == "replay" else law)
        # THE PLANNED BYTES, per area, as Plan.shares states them -- the deficit law's targets, and
        # every law's gauge. A Plan built without shares (none is: data_plan fills them under every
        # law) falls back to this phase's scheduled budget, the same rule, taken before the loop
        # spends it.
        target = dict(plan.shares[k]) if k < len(plan.shares) else dict(budget)
        got = {}
        if len(out) < hi:
            # data.phase_entered, COUNTED AT THE ONE LINE THAT DECIDES IT. The `while` below runs
            # its body if and only if this is true, so this is the phase's entry and not a proxy for
            # it: a phase whose span rounded to zero bytes is NOT entered, and that is precisely the
            # drift the gate below is armed against (ISSUES P1-L22).
            n_phase_entered += 1
        while len(out) < hi:
            if mode == "planned":
                # Uniform among the areas that still have budget, so the ORDER is random and the
                # SHARES are not. An area drops out of the choice when its budget is spent.
                avail = [i for i in live if budget[i] > 0]
                if not avail:
                    # Rounding can leave the phase a byte or two short of its bound with every
                    # budget spent. Give the remainder to the first live area rather than leaving
                    # the stream short, because len(bytes) == stream_bytes EXACTLY is P1-L22.
                    avail = list(live)
                    budget[avail[0]] = hi - len(out)
                idx = avail[stream.randrange(len(avail))] if len(avail) > 1 else avail[0]
            elif mode == "deficit":
                # THE AREA FURTHEST BEHIND ITS TARGET SHARE OF THE BYTES LAID SO FAR (04 section 1
                # item 2): target x laid - span x got is span x (target share x phase bytes so far -
                # realised), kept in integers so no float decides an order. Only an area with target
                # left may be chosen -- a spent area's deficit is negative, and an area whose target
                # rounded to 0 would tie at 0 and be handed a zero-byte segment. Ties go to the
                # first in Plan order, the order Plan.shares walks, and no rng draw is taken.
                laid = len(out) - lo
                idx, best = None, None
                for i, t in plan.shares[k]:
                    g = got.get(i, 0)
                    if g >= t:
                        continue
                    lag = t * laid - span * g
                    if best is None or lag > best:
                        idx, best = i, lag
                if idx is None:
                    # UNREACHABLE BY CONSTRUCTION, and a refusal rather than a hang: data_plan's
                    # targets sum to the phase span, so while the phase is short some area has
                    # target left. A Plan whose shares do not is a Plan this draw cannot lay.
                    raise CorpusError(
                        f"DATA_DRAW=replay: phase {k} holds {len(out) - lo} of its {span} bytes and "
                        f"no area has target left in Plan.shares {plan.shares[k]!r}, whose targets "
                        f"must sum to the phase span. The Plan was not built by data_plan for this "
                        f"configuration.")
            else:
                idx = live[stream.randrange(len(live))] if len(live) > 1 else live[0]
            label = names[idx]
            body = areas.bodies[label]
            want = stream.randint(seg_min, seg_max)
            # TRUNCATED TO THE PHASE BOUND rather than overshooting it by a whole segment, so phase
            # bounds do not drift and len(bytes) == stream_bytes EXACTLY (ISSUES P1-L22).
            want = min(want, hi - len(out))
            # AND FLOORED AT ONE BYTE, or the loop cannot terminate. At DATA_SEG_MIN=DATA_SEG_MAX=0
            # every draw was zero-length, `out` never grew, and `while len(out) < hi` spun forever
            # with no error, no traceback and no clock -- a hang is the one failure a report cannot
            # describe. The floor is not a silent clamp of the operator's number: seg_min is refused
            # at startup below, and this line only guarantees progress for a bound that got here.
            want = max(1, want)
            if mode == "planned":
                # AND TRUNCATED TO THIS AREA'S REMAINING SHARE, which is what makes the realized
                # split equal the scheduled one. A segment that overran its area's budget would put
                # the difference on whichever area happened to be drawn next.
                want = min(want, budget[idx])
            elif mode == "deficit":
                # THE SAME TRUNCATION, TO THE AREA'S REMAINING REPLAY TARGET (the critic's finding on
                # the draft: a deficit rule that truncated only at the phase bound realised each
                # area's bytes to within a segment, and the startup gates were exact no longer).
                want = min(want, target[idx] - got.get(idx, 0))
            if contig:
                # THE CURSOR PERSISTS ACROSS EPOCHS, so an English-only run has only the text's own
                # boundaries rather than discontinuities we manufacture every 8-20 KB. eng_only
                # reported 71 domains partly by counting our own seek points. (This is now a REAL
                # persistence, into the same dict object areas.cursors holds -- see the comment
                # above `cursors = areas.cursors` -- rather than a value nothing ever reads back.)
                start = cursors[label] % len(body)
                chunk = body[start:start + want]
                if len(chunk) < want:
                    chunk = chunk + body[:want - len(chunk)]
                    # data.contig_wrap, COUNTED HERE BECAUSE THIS LINE IS THE WRAP. The read ran off
                    # the end of the body and was completed from its head; there is no other line in
                    # this function where that happens, and counting it anywhere else would be
                    # counting a condition rather than the event.
                    n_wrap += 1
                # STORED ALREADY REDUCED MOD len(body), not the raw running total. A raw
                # `start + want` accumulates without bound over many segments and epochs -- not
                # incorrect (the `% len(body)` above still reads it back correctly), but an
                # unbounded int is a worse number to put in a checkpoint than the equivalent bounded
                # offset stream_state hands to CKPT, so it is normalised at the one place it is
                # written rather than left to grow.
                cursors[label] = (start + want) % len(body)
            else:
                start = stream.randint(0, max(0, len(body) - want))
                chunk = body[start:start + want]
            splice.append(len(out))
            if last_area is not None and label != last_area:
                # THE SUBSET WHERE THE AREA ACTUALLY CHANGED. Scoring boundary precision against
                # every splice start made all ~96 "true switches" artefacts on a one-area run.
                changes.append(len(out))
            last_area = label
            out += chunk
            labels.extend([label] * len(chunk))
            per_area[label] += len(chunk)
            got[idx] = got.get(idx, 0) + len(chunk)
            if mode == "planned":
                budget[idx] -= len(chunk)
        # THE PHASE'S GAUGES, in Plan order, for every area the phase makes live, gives a target or
        # drew from. Permille of the span, rounded half up in integers; a phase of no bytes has no
        # share to read and prints none, which is not a 0.
        if span > 0:
            for i, name in enumerate(names):
                if i in live or target.get(i, 0) or got.get(i, 0):
                    gauges[f"data.share.p{k}.{name}.planned"] = _permille(target.get(i, 0), span)
                    gauges[f"data.share.p{k}.{name}.realised"] = _permille(got.get(i, 0), span)

    # THE LINEAGE'S DRAWN AREAS, IN PLACE (2026-09-28, Q-FAB-18's review): every area this draw took
    # a byte from, appended in Plan order where Areas.drawn does not hold it yet. stream_state
    # records the list, and a child's Plan.parent_faded is read off it -- the areas the lineage
    # actually drew, which a declared area this schedule never makes live is not. The replay arm
    # above draws nothing and appends nothing: its bytes are the first draw's, already here.
    for label in names:
        if per_area[label] > 0 and label not in areas.drawn:
            areas.drawn.append(label)

    # ---- THE DID IT FIRE SURFACE THIS FUNCTION DECLARES ------------------------------------------
    # Built here, at the end, from tallies taken at the decision points above -- so a name whose
    # branch never ran reads as a MEASURED 0 and a name whose mechanism CANNOT run on this
    # configuration reads as UNREACHABLE with the lever and the value that made it so. Before this
    # block existed, every one of these names was declared in the docstring above and computed
    # nowhere, so the two states were the same silence.
    n_seg = len(splice)
    n_phases = len(plan.schedule)
    naive_mean = (seg_min + seg_max) / 2.0

    # A READING, NOT A GATE, and the docstring above says so in as many words: how many segments
    # these bytes are spliced from. It is a property of the BYTES, so it is still true when this
    # Stream is handed back for a later epoch under DATA_RESAMPLE=0 -- which is why the replay arm
    # carries `counters` over unchanged and re-states only the gates. The share gauges are readings
    # about the same bytes (2026-09-28, Q-DATA-10) and ride with it.
    counters = {"data.segment": n_seg}
    counters.update(gauges)

    gates = []
    if n_seg:
        draw_reason = (
            f"the value is the BYTES this call drew against DATA_STREAM_BYTES, from the child "
            f"stream data.stream.e{int(epoch)} in {stream.draws} rng draw(s) (Stream.draws) under "
            f"DATA_DRAW={law}: {n_seg} segment(s), realized mean {len(out) / n_seg:.1f} bytes "
            f"against the naive ({seg_min}+{seg_max})/2 = {naive_mean:.1f} that data_plan's "
            f"data.splice_window predicts from. That gate's own reason asks for exactly this "
            f"corroboration -- 'a reading near the threshold should be corroborated against the "
            f"actual Stream draw' -- and this is the number to do it with")
    else:
        draw_reason = (
            f"DATA_STREAM_BYTES={int(dat.stream_bytes)}: no phase had a byte to fill, so the draw "
            f"loop never ran a body and this call drew nothing in {stream.draws} rng draw(s). It is "
            f"a MEASURED zero -- the draw was armed and drew nothing -- and NOT the replay arm's "
            f"'no draw happened on this epoch at all'")
    gates.append(Gate("data.stream_draw", len(out) > 0, len(out), int(dat.stream_bytes),
                      reason=draw_reason))

    if contig:
        gates.append(Gate(
            "data.contig_wrap", n_wrap > 0, n_wrap, n_seg,
            reason="DATA_SEG_CONTIG=1: each area is read in order from a cursor that PERSISTS "
                   "ACROSS EPOCHS, and a read that runs off the end of a body is completed from its "
                   "head -- the value is how many of this epoch's segments wrapped and the "
                   "threshold is how many were read"))
    else:
        gates.append(Gate(
            "data.contig_wrap", False, None, n_seg, reachable=False,
            reason="DATA_SEG_CONTIG=0 (the shipped default, and a LITERAL rather than a computed "
                   "one): every segment seeks to randint(0, len(body) - want) and is cut to fit, so "
                   "no read can run off the end of a body and there is no cursor to wrap. Wrapping "
                   "is not something this configuration did zero times -- it is something it cannot "
                   "do, and the threshold is the segments that were read the other way"))

    if bool(dat.resample):
        gates.append(Gate(
            "data.resample", int(epoch) > 0, int(epoch), 0,
            reason=f"DATA_RESAMPLE=1: every epoch draws a fresh stream, so this call is redraw "
                   f"number {int(epoch)}. The threshold is the epoch index past which every call is "
                   f"a redraw, which is why epoch 0 reads armed-and-did-not-fire rather than "
                   f"unreachable: the mechanism is on, and a FIRST draw is not a redraw"))
    else:
        gates.append(Gate(
            "data.resample", False, None, 0, reachable=False,
            reason=f"DATA_RESAMPLE=0: every epoch after the first returns the byte-identical replay "
                   f"of this draw instead of redrawing (the arm at the top of this function), so "
                   f"'redraws so far' is not a number this configuration has. This call is the "
                   f"FIRST draw for this Areas in this process and it happened; what cannot happen "
                   f"here is a redraw. train/api.py::startup_refusals refuses RUN_EPOCHS>1 under "
                   f"this lever for the same reason -- a continual-learning result taken on "
                   f"replayed text is a memorisation result"))

    phase_reason = (
        f"the phase fill is EXACT -- phase k covers [round(k*B/P), round((k+1)*B/P)) at "
        f"B=DATA_STREAM_BYTES={int(dat.stream_bytes)} and P={n_phases} -- so every declared phase "
        f"must be entered on every epoch or the fill is drifting (ISSUES P1-L22)")
    if n_phase_entered != n_phases:
        phase_reason += (
            f"; MISMATCH: {n_phases - n_phase_entered} phase(s) were never entered because their "
            f"span rounded to zero bytes at this DATA_STREAM_BYTES, so the {len(out)} byte(s) drawn "
            f"came from fewer phases than the schedule declares")
    gates.append(Gate("data.phase_entered", n_phase_entered == n_phases, n_phase_entered, n_phases,
                      reason=phase_reason))

    st = Stream(bytes=bytes(out), labels=labels, splice_starts=tuple(splice),
                area_changes=tuple(changes), phase_bounds=tuple(plan.phase_bounds),
                area_names=tuple(names), per_area_drawn=per_area, epoch=int(epoch),
                # MEM CAN INVALIDATE OR RE-BASE PROVENANCE rather than silently carrying byte
                # offsets into a stream that no longer exists (ISSUES P1-M83).
                stream_id=f"s{seed}.e{int(epoch)}.{len(out)}",
                # THE DRAW COUNT, CARRIED OUT because rng.issued() cannot answer it (see Stream's
                # docstring) -- read off the local Rng before it goes out of scope.
                draws=stream.draws, counters=counters, gates=tuple(gates))
    if not bool(dat.resample):
        # THE WEAKREF'S CALLBACK IS THE EVICTION, not a periodic sweep: when this Areas is collected,
        # the callback fires and pops exactly this id() entry, which is what lets the cached Stream
        # (bytes plus a per-byte labels list -- the largest object this package produces) be freed
        # instead of retained in _REPLAY for the rest of the process, and what stops a LATER Areas
        # landing on the freed id from ever seeing this entry (the `is areas` check above would fail
        # anyway, but a dead entry with no path back to `st` also means `st` itself is reclaimable).
        key = id(areas)
        _REPLAY[key] = (weakref.ref(areas, lambda _ref, key=key: _REPLAY.pop(key, None)), st)
    return st


def _permille(part, whole):
    """`part` bytes of a `whole`-byte phase in permille, rounded half up, in integers: the unit of
    draw_stream's share gauges (2026-09-28, Q-DATA-10). UNIT: bytes, bytes -> permille. `whole` is
    a phase's span and is above 0 wherever this is called: a phase of no bytes prints no gauge."""
    return (2000 * int(part) + int(whole)) // (2 * int(whole))


def _replay_gates(dat, plan, cached, epoch):
    """draw_stream's four draw-time gates, re-stated UNREACHABLE for an epoch that performed NO draw.

    THIS IS THE THIRD STATE, ARRIVING THROUGH THE ONE PATH THAT CAN PRODUCE IT ON EVERY NAME AT ONCE.
    At DATA_RESAMPLE=0 -- the shipped default -- draw_stream returns the first draw's Stream for
    every later epoch, so on those epochs no byte is drawn, no segment is read, no cursor moves and
    no phase is entered. Carrying the first draw's gates out with `dataclasses.replace` would print
    FIRED for all four, which is not the armed-but-inert/unreachable collapse spine/gate.py::Gate
    exists to refuse but something worse: a positive reading for a mechanism that did not run.

    WHAT IS NOT RE-STATED IS `Stream.counters`, and the asymmetry is the point. data.segment counts
    the segments THESE BYTES are spliced from; the replay hands back the same bytes, so the reading
    is still true and re-stating it as unreachable would be its own small lie. A gate answers "did
    this call fire", a counter answers "what are these bytes" -- one of those questions changes on a
    replay and the other does not.

    `epoch` is named in every reason because the unreachable state is a property of THIS CALL and
    not of the run: epoch 0 under the same lever drew normally and its gates say so.
    """
    ep = int(epoch)
    n_seg = len(cached.splice_starts)
    n_phases = len(plan.schedule)
    where = (f"DATA_RESAMPLE=0 at epoch {ep}: draw_stream performs NO draw on this epoch -- it "
             f"returns the byte-identical replay of the first draw ({cached.stream_id})")
    return (
        Gate("data.stream_draw", False, None, int(dat.stream_bytes), reachable=False,
             reason=where + ", so 'how many bytes did THIS call draw' has no value to read here "
                            "rather than a value of zero. The bytes are the first draw's and their "
                            "reading is data.segment in Stream.counters, which this replay carries "
                            "over unchanged"),
        Gate("data.contig_wrap", False, None, n_seg, reachable=False,
             reason=where + f", so no segment is read on this epoch, no cursor advances and nothing "
                            f"can wrap. Whether a wrap is possible AT ALL is "
                            f"DATA_SEG_CONTIG={int(bool(dat.seg_contig))}'s question and this epoch "
                            f"never gets to ask it; the threshold is the segments the replayed "
                            f"bytes were spliced from"),
        Gate("data.resample", False, None, 0, reachable=False,
             reason=where + ", which IS this row's unreachable state rather than a consequence of "
                            "it: with resampling off no epoch ever redraws, so 'redraws so far' is "
                            "not a number this configuration has. train/api.py::startup_refusals "
                            "refuses RUN_EPOCHS>1 under this lever for that reason -- a "
                            "continual-learning result taken on replayed text is a memorisation "
                            "result"),
        Gate("data.phase_entered", False, None, n_phases, reachable=False,
             reason=where + f", so the phase loop does not run and no phase is entered on this "
                            f"epoch. The {n_phases} phase(s) were entered by the draw this record "
                            f"is a replay of, and that draw's own gate is where the count reads"),
    )


# The byte-identical replay at resample=False. Keyed by id(areas) -- Areas itself cannot be the dict
# KEY because it carries dict fields (bodies, holdout, ...) and is therefore unhashable -- but the
# VALUE is (weakref.ref(areas, evict), Stream), and the weakref's callback pops its own id() entry
# the moment that Areas is actually collected. THIS WAS A LIVE COLLISION, NOT A THEORETICAL ONE: a
# small repro (free one Areas, build a fresh one) landed the new object on the freed id within single
# digits of allocations in this same interpreter, and a plain id-keyed dict has no way to tell "the
# same run's Areas, still alive" from "a different run's Areas that happens to share an address" --
# exactly the isolation-sweep scenario this comment used to warn about while doing nothing to prevent
# it. Storing the weakref alongside the Stream and checking `ref() is areas` before trusting a hit
# closes that hole, and the eviction callback is what stops every resample=False Stream (bytes plus a
# per-byte labels list) from being retained for the life of the process: the entry -- and the big
# object it points to -- is freed the moment its Areas is, instead of sitting in this dict forever.
_REPLAY = {}


def stream_state(dat: Config, areas):
    """The mutable state that must survive into a checkpoint: the per-area read cursors, the epoch
    index of the last draw, the holdout block offsets and sizes (and, since 2026-09-27, a digest of
    each block's bytes: Q-DATA-9's review), the areas the lineage has drawn from (Areas.drawn, since
    2026-09-28: Q-FAB-18's review), and the counter vector.

    The cursors are LOAD-BEARING: without them a resume re-reads the head of every area under
    seg_contig and silently trains a second time on material the parent already used. The counter
    vector is checkpointed because a DID-IT-FIRE count that resets on resume counts the wrong thing.
    The cached Stream at resample=False is NOT checkpointed -- it is rebuilt from (seed, epoch).

    RETURNS: dict, handed to CKPT.save as part of the opaque payload.

    LEVERS READ: none (accounting only)
    WIRES READ: none
    DID IT FIRE: data.state_written (LINEAGE, and it counts the save that writes it),
                 data.state_written_here (THIS PROCESS's; restore_stream_state never restores it;
                 ABSENT until this process saves). Both are printed in the R report's
                 DATA(areas.counters) row since 2026-09-27 (Q-DATA-9), under the root's
                 _SAVE_COUNTS rule like every other package's pair; before that no row printed
                 them and they were read in the blob
    """
    dat = dat.owned_by("DATA")
    # BUMPED BEFORE THE COUNTERS ARE COPIED, SO A BLOB COUNTS ITSELF, with a process twin the
    # restore skips (2026-09-27, register LOW-RESUME-SAVED-COUNTERS; lm/api.py::state_dict says
    # what the old order cost). The R report's DATA(areas.counters) row prints the pair (Q-DATA-9),
    # one save short of the final blob, as every package's pair is.
    areas.counters["data.state_written"] = areas.counters.get("data.state_written", 0) + 1
    areas.counters["data.state_written_here"] = areas.counters.get("data.state_written_here",
                                                                   0) + 1
    out = {
        # THE PER-AREA READ CURSORS, WHICH ARE THE LOAD-BEARING PART. Without them a resume
        # re-reads the head of every area under seg_contig and silently trains a SECOND time on
        # material the parent already used -- which does not look like a bug in any report, it
        # looks like a model that learned that text unusually well.
        "cursors": {k: int(v) for k, v in areas.cursors.items()},
        # THE HOLDOUT BLOCK, OFFSET AND SIZE, PER AREA, so restore_stream_state can refuse a resume
        # whose held-out block MOVED. That refusal is the one goal B rests on: an ACROSS THE RUN
        # BOUNDARY number computed over a different block than the parent's compares two different
        # texts and reports the difference as forgetting.
        # AND WHAT THE BLOCK HOLDS, beside where it sits (2026-09-27, Q-DATA-9's review): offset,
        # size and key say where a block is, and two DIFFERENT texts can agree on all three -- a
        # synthetic area moved to another position in DATA_AREAS, or a real block and a synthetic
        # one of the same length, which draw their offset from the same keyed stream over the same
        # range. _block_digest is the block's bytes, so the restore can compare the texts
        # themselves. A record written before it carries none, and the restore then compares the
        # three fields alone, as it did.
        "holdout": {k: {"offset": int((areas.rng_holdout.get(k) or {}).get("offset", 0)),
                        "size": int(areas.holdout_bytes.get(k, 0)),
                        "key": (areas.rng_holdout.get(k) or {}).get("key"),
                        "digest": _block_digest(areas.holdout.get(k, b""))}
                    for k in areas.names},
        "bytes_present": {k: int(v) for k, v in areas.bytes_present.items()},
        "bytes_taken": {k: int(v) for k, v in areas.bytes_taken.items()},
        # THE AREAS THIS LINEAGE HAS DRAWN FROM, in the order first drawn (2026-09-28, Q-FAB-18's
        # review): Areas.drawn, the record's list plus this run's draws. A child reads its
        # Plan.parent_faded off this, and not off the `holdout` keys above, which are every area the
        # parent DECLARED -- drawn or not.
        "drawn": [str(n) for n in areas.drawn],
        # THE COUNTER VECTOR, because a DID-IT-FIRE count that resets on resume counts the wrong
        # thing -- it counts "since the last checkpoint" while being read as "this run".
        "counters": dict(areas.counters),
    }
    # THE CACHED Stream AT resample=False IS NOT CHECKPOINTED and that is deliberate: it is rebuilt
    # from (seed, epoch), so saving it would put a second copy of a derivable thing in the payload
    # and let the two disagree.
    return out


def restore_stream_state(dat: Config, areas, state):
    """Put the cursors and holdout offsets back. REFUSES LOUDLY if any area the parent RECORDED
    comes back with a different holdout offset or size -- or, where the record carries the block's
    digest (since 2026-09-27, Q-DATA-9's review), a different text at the same offset and size: a
    resume whose held-out block moved is a resume whose ACROSS THE RUN BOUNDARY number compares two
    different texts, and that is the one number goal B rests on.

    WHICH READING OF THE NAME CHECK IS NORMATIVE (ruled 2026-09-02, with Q-DATA-4). NOT
    set-equality. An add-an-area run is BY DEFINITION a resume whose area list gained a name --
    longrun.sh:938 runs DOMAINS="eng,$NAME" against a parent trained on eng -- so a set-equality
    reading refuses goal B's headline experiment at startup, and this row runs unconditionally
    whenever "DATA" is in the snapshot (the `restore` row, compose.py::ASSEMBLY_ORDER, and the call at
    compose.py::compose). The rule is:

      * every area name PRESENT IN THE RECORD must be present now, with the same holdout offset,
        the same holdout size and the same rng key -> restore its cursor. A disagreement on any of
        the four is the loud refusal, and it names which area and which field moved. Where the
        record carries the block's digest (_block_digest), the block's bytes must agree too, and
        a text that moved under agreeing fields is the same refusal, naming the digests.
      * a name present NOW and absent from the record is ADMITTED, its cursor starts at 0, and one
        data.area_added line is PRINTED naming it. That is the add-an-area run.
      * a name present in the RECORD and absent now is the loud refusal, not a silent drop: the
        parent trained on text this run cannot score, so its ACROSS THE RUN BOUNDARY number has no
        counterpart. It is a separate counter because "an area arrived" and "an area vanished" are
        two different statements and only one of them is an experiment.

    This reading still catches everything the refusal's own stated reason is about -- a moved block
    for a carried-over area -- and ON A REAL SOURCE it is the reading the per-area holdout streams in
    open_areas make TRUE rather than merely permitted: keyed by label, adding an area cannot move any
    other area's block there, so an honest add-an-area resume can no longer be refused by accident.
    ON THE SYNTHETIC SOURCE AT DATA_SYNTH_HOLDOUT=1 IT CAN, AND THE REFUSAL SAYS WHY (2026-09-27,
    Q-DATA-9's review; this paragraph claimed both sources until then). The block is carved from the
    area's GENERATED body, whose length is _synthetic_length -- max(DATA_SEG_MAX + 1, MIN_AREA_BYTES,
    DATA_STREAM_BYTES // DATA_N_PROCESSES) x 2 -- and whose text is the alphabet the area's POSITION
    picks (_synthetic_areas). Driven: a fifth area at DATA_STREAM_BYTES 120000 took every body from
    60,000 bytes to 48,000 and every block from 3,000 to 2,400, and the resume was refused naming
    only the size that moved. So on this arm a moved block is refused naming those three levers with
    this run's values, the parent's recorded length beside this run's, the DATA_STREAM_BYTES that
    generates the parent's length where one does (150000 there), and DATA_SOURCE=real, which writes
    the same fields. And a carried area whose position changed -- an entry inserted before it, or
    the list reordered -- keeps its block's offset, size and key but not its text, which the field
    comparison cannot see: driven, "eng,rust,py,num,c" at DATA_STREAM_BYTES 150000 was admitted over
    a parent at "eng,py,num,c" with py's, num's and c's blocks other bytes. That is refused naming
    DATA_AREAS. And since the fields cannot see a text at all, the record now carries each block's
    digest and the restore compares it, which catches the rest: driven, a real parent over eng
    resumed here at the matching length (DATA_STREAM_BYTES 400000 against DATA_CORPUS_CAP 200000)
    drew the same offset and size and was admitted with its English block replaced by generated
    text. On this arm an add-an-area resume appends the area and keeps the parent's length.

    THE ONE ADMISSION (2026-09-27, Q-DATA-9; register 04-Q5, SR0). A record of key None AND size 0
    for an area -- what the synthetic source writes at DATA_SYNTH_HOLDOUT=0, where it holds nothing
    out -- against a block NOW on the synthetic source (DATA_SYNTH_HOLDOUT=1) is ADMITTED: all three
    fields move, and nothing is lost, because the parent had no held-out block and so no number
    across the run boundary reads one. The same record against a REAL block is a change of source
    under the same area names, and it is refused as it was before the ruling. Each admitted AREA
    counts one in data.holdout_admitted -- the unit is the area, so a four-area parent admits 4 --
    and is named in data.holdout_admitted_names. THE PARENT TRAINED ON THOSE BYTES: an admitted
    block is text the lineage has seen, not a clean held-out sample, and the root says so in the
    warning it prints. Its read cursor, which indexed the WHOLE body, is mapped
    onto the carved one (_carved_cursor): below the block it stays, past it it moves down by the
    block's size, and inside it -- text now held out -- it moves to the block's offset, the first
    byte after the block in the carved body. ALL OF THAT HOLDS ONLY WHERE THIS RUN GENERATES THE
    PARENT'S TEXT FOR THE AREA, so the admission checks it first (Q-DATA-9's review): the same
    position, so the same alphabet, and the same length as the record's bytes_taken. Driven before
    the check: a child at DATA_STREAM_BYTES 400000 carved all four blocks past the 60,000 bytes its
    parent had, and one with DATA_AREAS reordered carved eng's and py's out of other text, and both
    were admitted under a warning that the parent trained on those bytes. Either is refused naming
    what moved, with DATA_SYNTH_HOLDOUT=0 as the resume that continues as before. THE REVERSE IS
    REFUSED: a block in the record and none now would train on the text the parent held out. The
    record does not say which source wrote the block, so the refusal names both that write one --
    DATA_SOURCE=real, and DATA_SOURCE=synthetic at DATA_SYNTH_HOLDOUT=1 (Q-DATA-9's review: it named
    the second alone, and a real parent resumed at the shipped synthetic source, told to set it, was
    refused again for an offset that moved). Every other move of a recorded block is the loud
    refusal above, unchanged.

    `Areas.parent_names` IS FILLED HERE: the record's area names, in its order -- the areas the
    parent declared, whatever this run's list says (Q-DATA-9). It said "the areas the parent trained
    on" until 2026-09-28 (Q-FAB-18's review), and a declared area need not have been drawn: a run
    over "eng,py" that schedules eng alone records py and never trains it.

    `Areas.drawn` IS FILLED HERE TOO (2026-09-28, Q-FAB-18's review): the record's list of the areas
    the lineage's streams drew from, which Plan.parent_faded is read off. A record written before
    stream_state carried it has none, and then every area it declares is ASSUMED drawn and named
    in data.drawn_assumed -- over-counting only a declared area no phase ever drew, which a record
    cannot tell apart.

    THE COUNTERS THE RECORD DOES NOT OVERWRITE are this resume's own statements and this run's own
    readings: the restore and refusal tallies, data.area_added and its names, the process twin
    data.state_written_here, the admission pair, data.drawn_assumed (this resume's assumption, not
    the parent's), and data.holdout_overlap -- a reading of THIS run's blocks, which open_areas
    computed a moment ago. Copying the parent's over it would read "no block to measure" beside an
    admitted block, and it dropped a newly added area's reading from the add-an-area run: driven at
    ae70638, the tree before this ruling, a real-source child over eng,py resumed from a parent over
    eng read {'eng': 0.0741} where its own was {'eng': 0.0741, 'py': 0.1142}
    (DATA_CORPUS_CAP=200000).

    LEVERS READ: source (the admission and the synthetic refusals are the synthetic source's,
                 Q-DATA-9), synth_holdout (arms the admission, and is named in the reverse
                 refusal), n_processes, stream_bytes, seg_max (the generated body's length, printed
                 with their values when a synthetic block moved or an admission's length is not
                 the parent's; this line said "none" until 2026-09-27, Q-DATA-9's review, though the
                 admission and its reverse read the first two from the day they landed)
    WIRES READ: none
    DID IT FIRE: data.state_restored, data.state_refused (with the area and the field that moved --
                 or, since Q-DATA-9's review, the synthetic position, length or block digest),
                 data.area_added (the arriving area, PRINTED in the R report's DATA(areas.counters)
                 row; 0 on an ordinary resume, which is the statement "this resume added nothing"
                 -- seeded at 0 since 2026-09-27, when that row made the missing key visible),
                 data.area_vanished, data.holdout_admitted and data.holdout_admitted_names (0 and
                 [] on a resume on DATA_SOURCE=synthetic at DATA_SYNTH_HOLDOUT=1, the one arm the
                 admission can fire on; ABSENT on a fresh run and on every other arm, which is
                 UNREACHABLE and not "armed, none admitted": at 0 no synthetic block exists to
                 admit, and a real one is never admitted -- Q-DATA-9's review, where they read 0 on
                 every resume), data.drawn_assumed (a READING, 2026-09-28, Q-FAB-18's review: the
                 areas this resume ASSUMED the lineage drew because the record carries no list of
                 them -- every area it declares -- and [] on a resume whose record carries one;
                 ABSENT on a fresh run)
    """
    dat = dat.owned_by("DATA")
    if not state:
        return areas

    def _refuse(reason):
        areas.counters["data.state_refused"] = areas.counters.get("data.state_refused", 0) + 1
        raise CorpusError(reason)

    recorded = dict(state.get("holdout") or {})
    cursors = dict(state.get("cursors") or {})
    # THE PARENT'S LENGTH PER AREA, which stream_state has recorded as bytes_taken since DATA's resume
    # state existed. On the synthetic source it is the generated body a block is carved from, so the
    # synthetic refusals below compare it with this run's and print both (Q-DATA-9's review).
    lengths = dict(state.get("bytes_taken") or {})
    live = set(areas.names)
    # THE PARENT'S AREA LIST, IN ITS ORDER, ON THE RECORD (Q-DATA-9): every area the parent
    # declared.
    areas.parent_names[:] = list(recorded)
    # AND THE AREAS THE LINEAGE DREW FROM (2026-09-28, Q-FAB-18's review), which a declared area
    # need not be: the list Plan.parent_faded is read off. A record written before it carries none,
    # and then every area it declared is ASSUMED drawn -- the reading the faded sets took of every
    # record until this date -- and data.drawn_assumed names them; [] where the record carried its
    # list. This run's draws are appended by draw_stream.
    if state.get("drawn") is not None:
        areas.drawn[:] = [str(n) for n in state["drawn"]]
        areas.counters["data.drawn_assumed"] = []
    else:
        areas.drawn[:] = list(recorded)
        areas.counters["data.drawn_assumed"] = list(recorded)
    # THE ONE ARM THE ADMISSION CAN FIRE ON: the synthetic source at DATA_SYNTH_HOLDOUT=1. At 0 every
    # live synthetic block has size 0, so there is nothing to admit, and a real block is never
    # admitted (a change of source, below).
    carves = str(dat.source) == "synthetic" and bool(dat.synth_holdout)
    # THE RESUME'S OWN STATEMENTS, SEEDED BEFORE THE COMPARISON SO THAT 0 READS "ARMED, NONE" -- and
    # seeded only where they are armed (2026-09-27, Q-DATA-9's review; G4). The admission pair was
    # seeded on every resume, so the default arm and every real-source resume printed "armed, did not
    # fire" for a mechanism that cannot run there; ABSENT is how this tree says UNREACHABLE, as
    # fab.ind_applied's arm does. data.area_added is armed everywhere: an area can arrive on either
    # source, and an ordinary resume says it added none, where a fresh run has no key.
    if carves:
        areas.counters["data.holdout_admitted"] = 0
        areas.counters["data.holdout_admitted_names"] = []
    areas.counters["data.area_added"] = 0

    # NOT SET-EQUALITY, AND THE RULING IS 2026-09-02's (Q-DATA-4). An add-an-area run is BY
    # DEFINITION a resume whose area list gained a name -- longrun.sh:938 runs DOMAINS="eng,$NAME"
    # against a parent trained on eng -- so a set-equality reading would refuse goal B's headline
    # experiment at startup, on a row that runs unconditionally whenever "DATA" is in the snapshot.
    for name in recorded:
        if name not in live:
            # AN AREA THAT VANISHED IS A LOUD REFUSAL, NOT A SILENT DROP. The parent trained on text
            # this run cannot score, so its ACROSS THE RUN BOUNDARY number has no counterpart. It is
            # counted separately from an arrival because "an area arrived" and "an area vanished"
            # are two different statements and only one of them is an experiment.
            # AND IT STAYS REFUSED UNDER PARENT REHEARSAL (2026-09-28, register 04-Q4 and NEW-06;
            # Q-DATA-10). DATA_REHEARSE_PARENT draws a parent area from its body, which this run
            # reads only for an area it declares; the route that would carry one without its corpus
            # -- NEW-06's replay reservoir in the checkpoint, register §8 4.5 -- is not built, and
            # the message says so, so the operator is not left to look for it.
            areas.counters["data.area_vanished"] = areas.counters.get("data.area_vanished", 0) + 1
            _refuse(f"DATA: the checkpoint recorded area {name!r} and this run does not have it. "
                    f"The parent trained on text this run cannot score, so its across-the-boundary "
                    f"number has no counterpart. Restore the area, or start a new run. A parent "
                    f"area is rehearsed (DATA_REHEARSE_PARENT, DATA_DRAW=replay) only from a body "
                    f"this run reads, so declare it in DATA_AREAS with its corpus in place: the "
                    f"replay reservoir that would carry it in the checkpoint when the corpus is gone "
                    f"(register NEW-06, Proposal 05 section 8 row 4.5) is not built in this tree.")
        was, now = recorded[name], {
            "offset": int((areas.rng_holdout.get(name) or {}).get("offset", 0)),
            "size": int(areas.holdout_bytes.get(name, 0)),
            "key": (areas.rng_holdout.get(name) or {}).get("key"),
        }
        if carves and was.get("key") is None and was.get("size") == 0 and now["size"] > 0:
            # THE ONE ADMISSION (Q-DATA-9, 04-Q5): the parent held nothing out of this area and this
            # run holds a block out of it. No across-the-boundary number reads a parent block that
            # does not exist, so moving all three fields breaks no comparison. The parent trained on
            # the block's bytes, which the root's warning says; the cursor is mapped, not copied,
            # because it indexed the whole body.
            # ON THE SYNTHETIC SOURCE ONLY, which is the move 04-Q5 rules on: DATA_SYNTH_HOLDOUT
            # 0 -> 1. Only a synthetic run at 0 writes key None and size 0 (a real area's empty
            # block is refused in open_areas), so the same record against a REAL block is a change
            # of source under the same area names, and it stays the refusal it was before this
            # ruling -- driven at ae70638, the field loop below refuses it naming the moved offset.
            # ITS PREMISE FIRST (Q-DATA-9's review): this body must be the parent's text -- the
            # alphabet its position picks, and the parent's length -- or "a block shorter than the
            # parent's", "text the parent trained on" and the cursor map are all false. The record's
            # one writer is a synthetic run at 0, whose text follows the same two rules, so the
            # refusal can say which of them moved.
            moved = []
            at = _alphabet_moved(name, recorded, areas.names)
            if at is not None:
                moved.append(
                    f"It is at position {at[1]} of this run's areas ({', '.join(areas.names)}) and "
                    f"was at {at[0]} of the checkpoint's ({', '.join(recorded)}), and a synthetic "
                    f"area's text is the alphabet its position picks (_ALPHABETS[position % "
                    f"{len(_ALPHABETS)}], data/api.py::_synthetic_areas): this body is other text, "
                    f"and the parent never trained on the block this run would carve from it. Keep "
                    f"the parent's areas at their positions in DATA_AREAS and add new ones after "
                    f"them.")
            if name in lengths and int(lengths[name]) != int(areas.bytes_taken.get(name, 0)):
                arith, back = _synthetic_body(dat, int(lengths[name]))
                moved.append(
                    f"The parent generated {int(lengths[name])} bytes of it and this run generates "
                    f"{arith}: at another length this body is not the parent's a block shorter, "
                    f"and past the parent's length the block is not text the parent trained on. "
                    f"Generate the parent's length"
                    + (f" (DATA_STREAM_BYTES={back} at DATA_N_PROCESSES={int(dat.n_processes)} "
                       f"does)." if back is not None else "."))
            if moved:
                _refuse(
                    f"DATA: the checkpoint held nothing out of area {name!r} (key None, size 0, as "
                    f"DATA_SOURCE=synthetic writes at DATA_SYNTH_HOLDOUT=0), and the one admission "
                    f"(Q-DATA-9) holds only where this run generates the parent's text for the "
                    f"area. " + " ".join(moved) + " Or resume at DATA_SYNTH_HOLDOUT=0, which "
                    f"continues as before.")
            areas.counters["data.holdout_admitted"] += 1
            areas.counters["data.holdout_admitted_names"].append(name)
            if name in cursors:
                areas.cursors[name] = _carved_cursor(int(cursors[name]), now["offset"],
                                                     now["size"], len(areas.bodies[name]))
            continue
        if (was.get("size") or 0) > 0 and now["size"] == 0:
            # THE REVERSE IS REFUSED, AND BY THE SETTINGS THAT WRITE A BLOCK (Q-DATA-9). A live size
            # of 0 is only reachable on the synthetic source at DATA_SYNTH_HOLDOUT=0 -- a real area's
            # 0-byte block is refused in open_areas -- so the field loop's "size moved" would name
            # the symptom and not the setting. WHICH setting wrote the record's block it cannot
            # say: a real source and the synthetic one at 1 record the same key, offset and size, so
            # the message names both (Q-DATA-9's review). It named DATA_SYNTH_HOLDOUT=1 alone, and a
            # real parent resumed at the shipped DATA_SOURCE, told to set it, was refused a second
            # time for an offset that moved, never told that DATA_SOURCE=real was the resume.
            _refuse(
                f"DATA: area {name!r} had a {was.get('size')}-byte held-out block in the "
                f"checkpoint (key {was.get('key')!r}, offset {was.get('offset')!r}) and has none "
                f"now: DATA_SOURCE={dat.source} at DATA_SYNTH_HOLDOUT="
                f"{int(bool(dat.synth_holdout))} holds nothing out. This run would train on the "
                f"text the parent held out, and its across-the-boundary number would have no block "
                f"to be read on. The record does not say which source wrote the block, and two "
                f"do: DATA_SOURCE=real, which carves one out of every area, and "
                f"DATA_SOURCE=synthetic at DATA_SYNTH_HOLDOUT=1. Resume with the one that wrote "
                f"it. Only the other direction is admitted: a block where the checkpoint held none "
                f"(key None, size 0), counted in data.holdout_admitted.")
        for field in ("offset", "size", "key"):
            if was.get(field) != now[field]:
                # ON THE SYNTHETIC SOURCE AT 1 THE REFUSAL ALSO SAYS WHAT THE BLOCK RIDES ON
                # (Q-DATA-9's review): the generated body's length, from three levers every area
                # shares, so the one move an add-an-area resume makes by default moved every block
                # and was refused naming only the field.
                note = ""
                if carves:
                    then = int(lengths[name]) if name in lengths else None
                    arith, back = _synthetic_body(dat, then)
                    here = int(areas.bytes_taken.get(name, 0))
                    note = (f" On DATA_SOURCE=synthetic at DATA_SYNTH_HOLDOUT=1 the block is carved "
                            f"out of the area's generated body, {arith} on this run")
                    if then is None:
                        note += "; the checkpoint records no length for this area to compare."
                    elif then != here:
                        note += (f", where the checkpoint recorded {then}: every area's block moves "
                                 f"with that length, so a resume that keeps the parent's blocks -- "
                                 f"one that adds an area included -- generates the parent's length"
                                 + (f" (DATA_STREAM_BYTES={back} at DATA_N_PROCESSES="
                                    f"{int(dat.n_processes)} does)." if back is not None
                                    else "."))
                    else:
                        note += (", the length the checkpoint recorded, so those three levers did "
                                 "not move it: at one length a block moves with DATA_HOLDOUT_FRAC, "
                                 "DATA_VAL_CAP or RUN_SEED.")
                    note += (" A checkpoint written on DATA_SOURCE=real records the same fields: if "
                             "the parent read this area from disk, resume with DATA_SOURCE=real.")
                _refuse(
                    f"DATA: area {name!r} had holdout {field}={was.get(field)!r} in the checkpoint "
                    f"and {now[field]!r} now. A resume whose held-out block moved compares two "
                    f"different texts across the run boundary, and that is the one number goal B "
                    f"rests on. Named here rather than discovered in the eval." + note)
        if carves:
            # THE BLOCK'S FIELDS AGREE AND ITS TEXT NEED NOT (Q-DATA-9's review). The field loop
            # compares where a block sits, not what it holds, and on the synthetic source what it
            # holds is the alphabet the area's position picks: an entry inserted before this one,
            # or the list reordered, keeps its offset, size and key and moves its bytes -- the
            # across-the-boundary number over two different texts, admitted in silence.
            at = _alphabet_moved(name, recorded, areas.names)
            if at is not None:
                _refuse(
                    f"DATA: area {name!r} is at position {at[1]} of this run's areas "
                    f"({', '.join(areas.names)}) and was at {at[0]} of the checkpoint's "
                    f"({', '.join(recorded)}). A synthetic area's text is the alphabet its "
                    f"position picks (_ALPHABETS[position % {len(_ALPHABETS)}], "
                    f"data/api.py::_synthetic_areas), so this area's text is not the parent's and "
                    f"neither is its held-out block, though the block's offset, size and key "
                    f"agree: its across-the-boundary number would compare two different texts, "
                    f"and that is the one number goal B rests on. Keep the parent's areas at their "
                    f"positions in DATA_AREAS and add new ones after them (Q-DATA-9).")
        if was.get("digest") is not None:
            # AND THE TEXT ITSELF, WHERE THE RECORD CARRIES IT (Q-DATA-9's review; _block_digest).
            # The three fields agree and the position did not move the alphabet, so what is left is
            # a text the fields cannot see: a real block and a synthetic one of the same length, a
            # corpus changed on disk, a generator that changed. A record written before the digest
            # carries none and is compared on the fields alone, as it was.
            have = _block_digest(areas.holdout.get(name, b""))
            if have != was.get("digest"):
                _refuse(
                    f"DATA: area {name!r} has the checkpoint's holdout offset, size and key "
                    f"({now['offset']}, {now['size']}, {now['key']!r}) and another text in them: the "
                    f"block's blake2b is {have} now and {was.get('digest')} in the checkpoint "
                    f"(data/api.py::_block_digest). A resume whose held-out block moved compares two "
                    f"different texts across the run boundary, and that is the one number goal B "
                    f"rests on. The fields cannot say which source wrote the block: DATA_SOURCE=real "
                    f"and DATA_SOURCE=synthetic at DATA_SYNTH_HOLDOUT=1 record the same three for a "
                    f"body of the same length. This run is DATA_SOURCE={dat.source}"
                    + (": if the parent read this area from disk, resume with DATA_SOURCE=real; if "
                       "it was synthetic, the generator's text moved."
                       if str(dat.source) == "synthetic" else
                       ": if the parent was DATA_SOURCE=synthetic at DATA_SYNTH_HOLDOUT=1, resume with "
                       "that; if it read this area from disk, the corpus under DATA_DIR changed."))
        if name in cursors:
            areas.cursors[name] = int(cursors[name])

    for name in areas.names:
        if name not in recorded:
            # THE ADD-AN-AREA RUN. Admitted, cursor at 0, and PRINTED -- the count is 0 on an
            # ordinary resume, which is itself the statement "this resume added nothing".
            areas.cursors[name] = 0
            areas.counters["data.area_added"] = areas.counters.get("data.area_added", 0) + 1
            areas.counters.setdefault("data.areas_added_names", []).append(name)
    if state.get("counters"):
        for k, v in state["counters"].items():
            # data.holdout_overlap IS THIS RUN'S READING (Q-DATA-9): skipped with the resume's own
            # statements, so the parent's reading of its own blocks never stands in for this one.
            if k not in ("data.state_restored", "data.state_refused", "data.area_added",
                         "data.area_vanished", "data.areas_added_names",
                         "data.state_written_here", "data.holdout_admitted",
                         "data.holdout_admitted_names", "data.holdout_overlap",
                         "data.drawn_assumed"):
                areas.counters[k] = v
    areas.counters["data.state_restored"] = areas.counters.get("data.state_restored", 0) + 1
    return areas


def _carved_cursor(cursor, offset, size, body_len):
    """Where a read cursor over a WHOLE body lands once [offset, offset + size) is carved out of it.

    UNIT: bytes in, bytes out. An admitted area's parent read its body whole (Q-DATA-9), so its
    DATA_SEG_CONTIG cursor indexes text that now includes a held-out block. Below the block the two
    bodies agree byte for byte and the cursor stays; past it every byte sits `size` earlier and so
    does the cursor; INSIDE it the cursor pointed at text this run holds out, and the next byte the
    parent would have read that this run still trains on is the first byte after the block, which in
    the carved body is at `offset`. Reduced mod the carved body's length, the form draw_stream stores,
    so a block at the tail sends a cursor inside it to the head, where the whole body's read would
    have wrapped.
    """
    if cursor < offset:
        at = cursor
    elif cursor >= offset + size:
        at = cursor - size
    else:
        at = offset
    return at % body_len if body_len > 0 else 0


def _block_digest(block):
    """blake2b of one area's held-out block: what the block HOLDS, which stream_state records beside
    where it sits and restore_stream_state compares (2026-09-27, Q-DATA-9's review).

    WHY THE THREE FIELDS WERE NOT ENOUGH. The offset is drawn from rng_for("data.holdout.<key>",
    seed) over len(body) - size, and the size is a fraction of len(body), so two bodies of one length
    under one label get the same three fields whatever they hold. Driven: a real parent over eng
    (DATA_CORPUS_CAP=200000: offset 166367, size 10000) resumed on the synthetic source at
    DATA_SYNTH_HOLDOUT=1 and DATA_STREAM_BYTES=400000 (a 200,000-byte generated body) drew the same
    offset and size, and was admitted -- as an add-an-area run over py, num and c -- with English
    held out in the checkpoint and generated text held out now. An area whose synthetic alphabet
    moved agrees on all three the same way. Hashing the bytes compares the texts themselves.

    Under its own `person`, like spine/compose.py::_stream_digest, so it cannot collide with the
    tree's other blake2b uses. Hashing the empty block of an area that holds nothing out is harmless:
    the admission, the one move that changes it, never reads the recorded digest.
    """
    return hashlib.blake2b(bytes(block), digest_size=16, person=b"data.holdout").hexdigest()


def _alphabet_moved(name, order, names):
    """(its position in the record, its position now) for an area whose synthetic ALPHABET moved
    between the checkpoint's area list `order` and this run's `names`; None where it did not.

    _synthetic_areas gives the area at position i the alphabet _ALPHABETS[i % 5], so two positions
    five apart are the same alphabet and the same text, and any other move is other text -- the
    same draws relabelled where the two alphabets are the same size, other draws where they are not.
    Positions count from 0, as the generator's `i` does. Called on the synthetic source only: a real
    area's text is its directory, whatever its position (2026-09-27, Q-DATA-9's review).
    """
    then, now = list(order).index(name), list(names).index(name)
    return None if then % len(_ALPHABETS) == now % len(_ALPHABETS) else (then, now)


def _synthetic_body(dat, then):
    """(the sentence, the DATA_STREAM_BYTES) a synthetic refusal in restore_stream_state prints: this
    run's _synthetic_length spelled out with the three levers' values, and the DATA_STREAM_BYTES that
    generates the parent's `then` bytes at this run's DATA_N_PROCESSES and DATA_SEG_MAX -- None when
    `then` is None, or when no value does, because the parent's length was held by another term of
    the max (2026-09-27, Q-DATA-9's review).

    WHY THE SECOND NUMBER IS WORTH PRINTING: the move an add-an-area resume makes by default --
    DATA_N_PROCESSES up by one, DATA_STREAM_BYTES left alone -- shortens every synthetic body, and
    the one lever that gives the parent's length back is DATA_STREAM_BYTES, raised in proportion
    (120000 -> 150000 for a fifth area). It is CHECKED, not assumed: the value is kept only if the
    one formula, run on it, returns `then`.
    """
    seg_max, stream_bytes, n = int(dat.seg_max), int(dat.stream_bytes), int(dat.n_processes)
    text = (f"max(DATA_SEG_MAX + 1 = {seg_max + 1}, {MIN_AREA_BYTES}, DATA_STREAM_BYTES="
            f"{stream_bytes} // DATA_N_PROCESSES={n}) x 2 = "
            f"{_synthetic_length(seg_max, stream_bytes, n)} bytes")
    back = None
    if then is not None and int(then) > 0:
        guess = (int(then) // 2) * n
        if _synthetic_length(seg_max, guess, n) == int(then):
            back = guess
    return text, back
