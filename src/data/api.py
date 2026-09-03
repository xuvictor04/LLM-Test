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
  Areas   names, bodies, holdout, holdout_bytes, bytes_present, bytes_taken, cursors, rng_holdout
  Plan    protocol, schedule, phase_bounds, per_area_draw, exposure, gates, counters
  Stream  bytes, labels, splice_starts, area_changes, phase_bounds, area_names, per_area_drawn,
          epoch, stream_id, draws
"""
import dataclasses
import os
import re
import weakref

from spine.lever import Config
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
    """
    names: tuple
    bodies: dict
    holdout: dict
    holdout_bytes: dict
    bytes_present: dict
    bytes_taken: dict
    cursors: dict
    rng_holdout: dict


def _holdout_key(label):
    """The rng subsystem name for one area's held-out stream: the label, normalised.

    spine/rng.py refuses uppercase (so "Fabric" and "fabric" cannot become two streams for one
    subsystem) and refuses "/" (its seed separator). Area labels are directory names and may carry
    both -- "code_OOD" today, and "continual/01_rust" under the slash rule. So the key is the label
    lowercased with everything outside [a-z0-9_] replaced by "_", and two areas whose KEYS collide
    are the same startup refusal as two whose labels collide. That is exactly the objection rng.py
    raises, answered at startup rather than papered over.
    """
    return re.sub(r"[^a-z0-9_]", "_", str(label).lower())




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
    15-symbol alphabets (self_organize.py:1084-1099, :1314-1315), seeded from
    rng_for("data.synth", seed) so that two run seeds are two different synthetic corpora. Today
    they are not: make_proc is seeded by the PROCESS INDEX, so `DATA_SOURCE=synthetic` measures a
    between-seed spread with the data held constant (DEFECT D-A13). Holds nothing out.

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
    no new RNG_SUBSYSTEMS entry -- "data.holdout" stays the declared parent.

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
                 time)
    WIRES READ: none
    DID IT FIRE: data.area_open (one per area; unreachable on source=synthetic),
                 data.area_nested (one per areas entry containing "/" -- 0 is the shipped default
                 and means every area came from train/, which is a STATEMENT and not silence),
                 data.area_path_refused, data.area_label_collision (both exit at startup, so N>0
                 is never seen in a completed run; declared so the refusal is a named mechanism
                 rather than an assertion),
                 data.corpus_cap_trip (fired N / armed but 0, prints taken vs present per area),
                 data.holdout_block (prints offset+size AND the rng key per area),
                 data.holdout_seam (one per area -- removing a MIDDLE block leaves exactly one
                 manufactured discontinuity in a body seg_contig=True reads in order, and
                 data/levers.py::DATALevers claims the only boundaries left are the text's own; one
                 seam per area against the thousands seg_from manufactures is a good trade, but it
                 is a PRINTED NUMBER and not an assumption. Unreachable when a block lands at
                 offset 0 or at the tail, which is the state it must say rather than read 0),
                 data.holdout_overlap (a READING, not a lever and not a gate: the fraction of
                 held-out bytes that also occur verbatim in the training body at a fixed n-gram
                 length, per area, printed once at startup. It costs no lever, no wire and no
                 default, and it answers the one question the split rule CANNOT: Lee et al.
                 arXiv:2107.06499 measures models "underestimate perplexity on evaluation documents
                 with near duplicates" and says benchmarks "should actively remove contaminated
                 training data, rather than just partitioning held out splits by documents", so
                 NEITHER the tail nor the random block is safe on its own), data.val_cap_trip,
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
    by_label, by_key = {}, {}
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
        by_label[label] = entry
        by_key[key] = (label, entry)

    raw = {}                       # label -> bytes, before the held-out block is removed
    present, taken, sources = {}, {}, {}

    if str(dat.source) == "synthetic":
        raw, present, taken, sources = _synthetic_areas(dat, seed, entries, labels)
    else:
        for entry, label in zip(entries, labels):
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
            rel = entry if "/" in entry else os.path.join("train", entry)
            path = os.path.join(str(dat.dir), rel)
            body, n_present = _read_area(path, int(dat.corpus_cap))
            if not body:
                raise CorpusError(
                    f"area {label!r} at {path!r} holds no usable bytes. Refused rather than "
                    f"dropped: dropping an area desynchronises the label list from the corpus list "
                    f"and the next run reports one corpus's loss under another's name "
                    f"(ISSUES P3-C19).")
            raw[label], present[label], taken[label], sources[label] = body, n_present, len(body), path

    names = tuple(raw)
    bodies, holdout, holdout_bytes, rng_holdout, cursors = {}, {}, {}, {}, {}
    for label in names:
        blob = raw[label]
        # THE FLOOR IS CHECKED ON THE USABLE BODY, i.e. after the held-out block comes out, which is
        # why the arithmetic is done before the refusal rather than after.
        n_hold = min(int(len(blob) * float(dat.holdout_frac)), int(dat.val_cap))
        if str(dat.source) == "synthetic":
            n_hold = 0             # the synthetic path holds nothing out
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
            if not interior_seam:
                rng_holdout[label]["why"] = (
                    "block landed at the body's own leading edge (offset 0): no text precedes it, "
                    "so removing it manufactures no discontinuity" if start == 0 else
                    "block landed at the body's own tail: no text follows it, so removing it "
                    "manufactures no discontinuity")
        else:
            if str(dat.source) != "synthetic":
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
                raise CorpusError(
                    f"area {label!r} computed a 0-byte held-out block: min(int({len(blob)} * "
                    f"{float(dat.holdout_frac)}), {int(dat.val_cap)}) == 0 from DATA_HOLDOUT_FRAC="
                    f"{dat.holdout_frac} and DATA_VAL_CAP={int(dat.val_cap)} against a "
                    f"{len(blob)}-byte body. Refused rather than trained on with no held-out block "
                    f"at all: raise DATA_HOLDOUT_FRAC or DATA_VAL_CAP.")
            holdout[label] = b""
            bodies[label] = blob
            rng_holdout[label] = {"key": None, "offset": 0, "size": 0, "seam_at": None,
                                  "why": "source=synthetic holds nothing out"}
        holdout_bytes[label] = len(holdout[label])
        cursors[label] = 0

    return Areas(names=names, bodies=bodies, holdout=holdout, holdout_bytes=holdout_bytes,
                 bytes_present=present, bytes_taken=taken, cursors=cursors,
                 rng_holdout=rng_holdout)


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


# The five 15-symbol alphabets, from the old tree's synthetic generator.
_ALPHABETS = ("abcdefghijklmno", "pqrstuvwxyzABCD", "EFGHIJKLMNOPQRS",
              "TUVWXYZ0123456", "789!?.,;:'\"-()")


def _synthetic_areas(dat, seed, entries, labels):
    """`dat.n_processes` order-2 Markov generators, one area each. Holds nothing out.

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
    believes it has its own. The per-child form fixes that and buys the property Q-DATA-6 argues
    for on the other stream: an area's text stops being a function of how many areas were generated
    before it, so inserting one entry no longer moves every later area's corpus. The parent keeps
    its RNG_SUBSYSTEMS row and reports zero draws, which is the honest reading -- declared, never
    drawn -- and is what `data.holdout` already does.
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
    # Enough text that the floor is clearable and a 120,000-byte stream can be drawn without the
    # sampler wrapping: the areas are generated, so there is no corpus to be short. `n` is now known
    # >= 1 (refused above), so this no longer needs the max(1, n) clamp the LEVERS READ docstring
    # line and the audit both named: DATA_N_PROCESSES=0 is a startup refusal, not a divide-by-zero
    # guard wearing a clamp's clothes.
    per_area = max(int(dat.seg_max) + 1, MIN_AREA_BYTES, int(dat.stream_bytes) // n) * 2
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
    """
    protocol: str
    schedule: tuple
    phase_bounds: tuple
    per_area_draw: dict
    exposure: dict
    gates: tuple
    counters: dict = dataclasses.field(default_factory=dict)


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

    RECEIVES: epochs <- RUN.epochs; win_tokens <- LM.ctx; bytes_per_token <- TOK, measured by
    derive.bytes_per_token after build_vocabulary. All three are arguments: bytes_per_token cannot
    be a wire (measured after freeze, the reason assemble.NOT_WIRES gives for the SIG width).
    RETURNS: Plan.

    LEVERS READ: phase_sched, phases, phase_live, stream_bytes, seg_min, seg_max, exposure_max,
                 exposure_skew, draw
    WIRES READ: none
    DID IT FIRE: data.phase_resolved, data.protocol_named (the recognised protocol, printed by
                 name -- one of the four, never blank), data.phase_name_resolved (entries given as
                 a NAME rather than an index; 0 means every entry was an index, which is the
                 shipped spelling and a statement rather than silence),
                 Gate data.exposure_max, Gate data.exposure_skew -- EXACT under the shipped
                 DATA_DRAW="planned" and a PREDICTION under "uniform", where the run trains on a
                 random draw from the scheduled split that deviated by up to 47.9% per area over
                 eight seeds. The caveat rides on the gate's `reason` and not on its name, so a
                 report can be grepped across both arms (ISSUES P1-H58, ruled),
                 Gate data.splice_window
    """
    dat = dat.owned_by("DATA")
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

    per_area_draw = {n: 0 for n in names}
    for (lo, hi), live in zip(bounds, schedule):
        span = hi - lo
        for j, idx in enumerate(live):
            # The phase's bytes split evenly among its live areas, with the remainder on the first
            # so the per-area totals sum to the phase span exactly.
            share = span // len(live) + (1 if j < span % len(live) else 0)
            per_area_draw[names[idx]] += share

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
    # ONE GATE NAME UNDER BOTH LAWS. A report whose keys change with the configuration cannot be
    # grepped across arms, which costs more than the caveat it would save, so the caveat rides on
    # the gate's own `reason` -- which spine/gate.py prints on every arm for exactly this case.
    law = str(dat.draw)
    caveat = "" if law == "planned" else (
        "DATA_DRAW=uniform: this is the SCHEDULED split and the run trains on a random draw from "
        "it (measured deviation up to 47.9% per area), so read it as a prediction and read "
        "Stream.per_area_drawn for what happened.")
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
    # corroborated by inspecting the actual Stream draw rather than trusted alone.
    splice_caveat = (
        "data.splice_window is a STARTUP PREDICTION from the declared seg_min/seg_max mean, never "
        "measured from the actual draw (data_plan runs before a single byte is drawn). Under "
        "DATA_DRAW=planned (the shipped default) draw_stream additionally truncates segments to "
        "each area's remaining per-phase budget, so the realized mean segment length runs "
        "measurably below this estimate -- measured over an 8-seed sweep at the shipped defaults, "
        "'armed, did not fire' here read true on 8/8 seeds while the realized windows-per-segment "
        "was already below 8.0 on all 8; the gap widens with phase count. A reading near the "
        "threshold should be corroborated against the actual Stream draw, not trusted alone.")
    gates.append(Gate("data.splice_window", windows_per_segment < 8.0,
                      round(windows_per_segment, 3), 8.0, reason=splice_caveat))

    # PHASE_NAME_RESOLVED, CARRIED OUT RATHER THAN COMPUTED AND DISCARDED (audit finding, confirmed
    # live: n_by_name was incremented above and never read again anywhere in this file -- Plan had
    # no field for it and DATA declares no counters() entry point, so the docstring's declared
    # data.phase_name_resolved row had no value anywhere to report). 0 is the shipped, honest
    # reading -- "every entry was an index" -- and it can now actually be printed as that statement
    # rather than silence.
    counters = {"data.phase_resolved": len(schedule), "data.protocol_named": protocol,
                "data.phase_name_resolved": n_by_name}

    return Plan(protocol=protocol, schedule=schedule, phase_bounds=bounds,
                per_area_draw=per_area_draw, exposure=exposure, gates=tuple(gates),
                counters=counters)


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
        randint(seg_min, seg_max). This is the law every recorded result was taken under. dat.seg_contig=False seeks to a random offset inside
    the area body each segment; True reads the body in order from a cursor that PERSISTS ACROSS
    EPOCHS, so an English-only run has only the text's own boundaries rather than discontinuities
    we manufacture every 8-20 KB (self_organize.py:1291-1298 -- eng_only reported 71 domains partly
    by counting our own seek points). The default is False and is a LITERAL, not a computed
    default: the shipped `1 if NP == 1 else 0` resolved to 0 on both shipped configurations.

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

    RETURNS: Stream.

    LEVERS READ: stream_bytes, seg_min, seg_max, seg_contig, resample, draw
    WIRES READ: none
    DID IT FIRE: data.stream_draw, data.segment, data.contig_wrap (unreachable at seg_contig=False,
                 with the gate arithmetic), data.resample (unreachable at resample=False -- the
                 "every epoch is a byte-identical replay" state, STATED rather than warned about),
                 data.phase_entered (must equal len(schedule) per epoch or the fill is drifting),
                 Stream.draws (0 draws = armed-but-inert; NOT rng.issued()["data.stream.e<n>"].draws
                 -- issued() returns (derived seed, run seed) tuples with no .draws attribute, so
                 that expression is an AttributeError and Stream carries the real reading instead;
                 audit finding, confirmed live)
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
            return dataclasses.replace(entry[1], epoch=int(epoch))

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

    # WHICH LAW ALLOCATES THE BYTES (DATA_DRAW; P1-H58, ruled by the owner 2026-09-02).
    #   planned -- the shipped default -- gives each live area its SCHEDULED SHARE of the phase and
    #     randomises only which order the segments come in and where in the body each is read from.
    #     `Plan.per_area_draw` is then what the run actually trains on, so data_plan's exposure gates
    #     are exact rather than predictive.
    #   uniform picks an area independently per segment. That is the law every recorded result in
    #     this project was taken under, and it is kept for exactly that reason -- but under it the
    #     realized split is a DRAW from the scheduled one, and the worst per-area deviation measured
    #     over eight seeds at the shipped defaults was 47.9%.
    law = str(dat.draw)
    for (lo, hi), live in zip(plan.phase_bounds, plan.schedule):
        # THE PLANNED LAW'S REMAINING BUDGET, per area, in the same shares data_plan computed. It is
        # recomputed here from the phase span rather than read off Plan.per_area_draw because that
        # field is the WHOLE-RUN total across every phase an area appears in; taking a phase's share
        # out of a whole-run total is the kind of arithmetic that silently drifts. Both use the same
        # rule -- floor division with the remainder on the first live areas -- so the two agree by
        # construction and not by coincidence.
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
        while len(out) < hi:
            if law == "planned":
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
            if law == "planned":
                # AND TRUNCATED TO THIS AREA'S REMAINING SHARE, which is what makes the realized
                # split equal the scheduled one. A segment that overran its area's budget would put
                # the difference on whichever area happened to be drawn next.
                want = min(want, budget[idx])
            if contig:
                # THE CURSOR PERSISTS ACROSS EPOCHS, so an English-only run has only the text's own
                # boundaries rather than discontinuities we manufacture every 8-20 KB. eng_only
                # reported 71 domains partly by counting our own seek points. (This is now a REAL
                # persistence, into the same dict object areas.cursors holds -- see the comment
                # above `cursors = areas.cursors` -- rather than a value nothing ever reads back.)
                start = cursors[label] % len(body)
                chunk = body[start:start + want]
                if len(chunk) < want:
                    chunk = chunk + body[:want - len(chunk)]      # data.contig_wrap
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
            if law == "planned":
                budget[idx] -= len(chunk)

    st = Stream(bytes=bytes(out), labels=labels, splice_starts=tuple(splice),
                area_changes=tuple(changes), phase_bounds=tuple(plan.phase_bounds),
                area_names=tuple(names), per_area_drawn=per_area, epoch=int(epoch),
                # MEM CAN INVALIDATE OR RE-BASE PROVENANCE rather than silently carrying byte
                # offsets into a stream that no longer exists (ISSUES P1-M83).
                stream_id=f"s{seed}.e{int(epoch)}.{len(out)}",
                # THE DRAW COUNT, CARRIED OUT because rng.issued() cannot answer it (see Stream's
                # docstring) -- read off the local Rng before it goes out of scope.
                draws=stream.draws)
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
    index of the last draw, the holdout block offsets and sizes, and the counter vector.

    The cursors are LOAD-BEARING: without them a resume re-reads the head of every area under
    seg_contig and silently trains a second time on material the parent already used. The counter
    vector is checkpointed because a DID-IT-FIRE count that resets on resume counts the wrong thing.
    The cached Stream at resample=False is NOT checkpointed -- it is rebuilt from (seed, epoch).

    RETURNS: dict, handed to CKPT.save as part of the opaque payload.

    LEVERS READ: none (accounting only)
    WIRES READ: none
    DID IT FIRE: data.state_written
    """
    dat = dat.owned_by("DATA")
    raise NotImplementedError(
        "DATA.stream_state: P4 (data) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section DATA.")


def restore_stream_state(dat: Config, areas, state):
    """Put the cursors and holdout offsets back. REFUSES LOUDLY if any area the parent RECORDED
    comes back with a different holdout offset or size: a resume whose held-out block moved is a
    resume whose ACROSS THE RUN BOUNDARY number compares two different texts, and that is the one
    number goal B rests on.

    WHICH READING OF THE NAME CHECK IS NORMATIVE (ruled 2026-09-02, with Q-DATA-4). NOT
    set-equality. An add-an-area run is BY DEFINITION a resume whose area list gained a name --
    longrun.sh:938 runs DOMAINS="eng,$NAME" against a parent trained on eng -- so a set-equality
    reading refuses goal B's headline experiment at startup, and this row runs unconditionally
    whenever "DATA" is in the snapshot (the `restore` row, compose.py::ASSEMBLY_ORDER, and the call at
    compose.py::compose). The rule is:

      * every area name PRESENT IN THE RECORD must be present now, with the same holdout offset,
        the same holdout size and the same rng key -> restore its cursor. A disagreement on any of
        the four is the loud refusal, and it names which area and which field moved.
      * a name present NOW and absent from the record is ADMITTED, its cursor starts at 0, and one
        data.area_added line is PRINTED naming it. That is the add-an-area run.
      * a name present in the RECORD and absent now is the loud refusal, not a silent drop: the
        parent trained on text this run cannot score, so its ACROSS THE RUN BOUNDARY number has no
        counterpart. It is a separate counter because "an area arrived" and "an area vanished" are
        two different statements and only one of them is an experiment.

    This reading still catches everything the refusal's own stated reason is about -- a moved block
    for a carried-over area -- and it is the reading the per-area holdout streams in open_areas
    make TRUE rather than merely permitted: keyed by label, adding an area cannot move any other
    area's block, so an honest add-an-area resume can no longer be refused by accident.

    LEVERS READ: none
    WIRES READ: none
    DID IT FIRE: data.state_restored, data.state_refused (with the area and the field that moved),
                 data.area_added (the arriving area, PRINTED; 0 on an ordinary resume, which is the
                 statement "this resume added nothing"), data.area_vanished
    """
    dat = dat.owned_by("DATA")
    raise NotImplementedError(
        "DATA.restore_stream_state: P4 (data) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section DATA.")
