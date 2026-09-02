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
  Plan    protocol, schedule, phase_bounds, per_area_draw, exposure, gates
  Stream  bytes, labels, splice_starts, area_changes, phase_bounds, area_names, per_area_drawn,
          epoch, stream_id
"""
from spine.lever import Config


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
        entry and the resolved path (data.area_path_refused).
      * the area LABEL is the basename ("continual/01_rust" labels as "01_rust"), and two entries
        resolving to the same label are REFUSED with BOTH source paths printed
        (data.area_label_collision). The label is what every per-area score, the holdout stream key
        below and ACROSS THE RUN BOUNDARY look up by name, and a run whose report prints one label
        for two corpora reproduces the desynchronised-DN defect this package exists to end
        (ISSUES C19).

    On dat.source == "synthetic": builds dat.n_processes order-2 Markov generators over the five
    15-symbol alphabets (self_organize.py:1084-1099, :1314-1315), seeded from
    rng_for("data.synth", seed) so that two run seeds are two different synthetic corpora. Today
    they are not: make_proc is seeded by the PROCESS INDEX, so `DATA_SOURCE=synthetic` measures a
    between-seed spread with the data held constant (DEFECT D-A13). Holds nothing out.

    THE HELD-OUT BLOCK IS A SEEDED RANDOM CONTIGUOUS BLOCK PER AREA, from
    rng_for("data.holdout." + key, seed) -- ONE CHILD STREAM PER AREA, KEYED BY THE AREA'S LABEL
    (normalised; the exact rule is three paragraphs down and it is the KEY, not the raw label, that
    is spliced in) AND NOT BY DRAW ORDER -- of size min(holdout_frac * present, val_cap) -- NOT the
    tail.
    The tail is a sample only if the corpus was written in no particular order, and the measured
    cost of assuming it was is py held out at 5.061 +/- 0.560 against 2.922 in-stream while eng
    (shuffled upstream) was 2.273 against 2.303 (self_organize.py:1173-1198). val_cap applies on
    BOTH paths; it applied only under DISK_STREAM before (ISSUES M82). The block is physically
    removed from the training body, so no sampling rule anywhere can reach it and there is no
    length any caller can read that includes it (ISSUES M81).

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
    forgetting (self_organize.py:1142-1160, ISSUES C19 -- CITED BY ID, NOT BY LINE: this was
    ISSUES:1421 in four places across this package and that line has held three different defects
    across three commits; today it is L15, an LR_DECAY default in a research note). The floor is
    DERIVED from seg_max rather
    than the old literal 5000, which raised on rerun.sh's SEG_MIN=8000 (ISSUES L75).

    RECEIVES: seed <- RUN.seed, as an argument. DATA calls rng_for itself; assemble.NOT_WIRES
    rejects a d_seed by name.
    RETURNS: Areas.

    LEVERS READ: source, dir, areas, n_processes, corpus_cap, holdout_frac, val_cap, seg_max
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
    raise NotImplementedError(
        "DATA.open_areas: P4 (data) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section DATA.")


def data_plan(dat: Config, areas, *, epochs: int, win_tokens: int, bytes_per_token: float):
    """Resolve the phase schedule and compute, BEFORE A SINGLE STEP RUNS, what this configuration
    will actually expose the model to.

    THE SCHEDULE. dat.phase_sched non-empty is parsed here and refused loudly at startup on an
    empty phase or an out-of-range area id (self_organize.py:1355-1366) -- validation lives at the
    parse site only, with no `[a for a in act if a < NP] or list(range(NP))` fallback, which was
    unreachable dead code that would have quietly re-enabled every area in a phase (ISSUES L18).
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
    reads DOMAINS (ISSUES L2).

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
    confounded with "py was memorised and eng was skimmed" (ISSUES H22).

    THREE DECLARED GATES, each printing its own arithmetic so "did not fire" is distinguishable
    from "could not fire":
      data.exposure_max     max(exposure) > dat.exposure_max. COMPUTED AT ONE AREA TOO: both reads
                            sat inside `if DATA_MODE == "real" and NP > 1`, so the check was
                            unavailable on exactly the single-area goal-A configuration where
                            accidental repetition is easiest to reach (ISSUES L21).
      data.exposure_skew    max/min > dat.exposure_skew. Declared UNREACHABLE at n_areas == 1 with
                            the reason printed -- a max/min ratio over one area is undefined.
      data.splice_window    mean_segment_bytes / (win_tokens * bytes_per_token) < 8. The one place
                            the byte/token boundary is crossed, and it is crossed with the MEASURED
                            bytes/token handed in, never with an estimate (ISSUES H16).

    RECEIVES: epochs <- RUN.epochs; win_tokens <- LM.ctx; bytes_per_token <- TOK, measured by
    derive.bytes_per_token after build_vocabulary. All three are arguments: bytes_per_token cannot
    be a wire (measured after freeze, the reason assemble.NOT_WIRES gives for the SIG width).
    RETURNS: Plan.

    LEVERS READ: phase_sched, phases, phase_live, stream_bytes, seg_min, seg_max, exposure_max,
                 exposure_skew
    WIRES READ: none
    DID IT FIRE: data.phase_resolved, data.protocol_named (the recognised protocol, printed by
                 name -- one of the four, never blank), data.phase_name_resolved (entries given as
                 a NAME rather than an index; 0 means every entry was an index, which is the
                 shipped spelling and a statement rather than silence),
                 Gate data.exposure_max, Gate data.exposure_skew,
                 Gate data.splice_window
    """
    dat = dat.owned_by("DATA")
    raise NotImplementedError(
        "DATA.data_plan: P4 (data) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section DATA.")


def draw_stream(dat: Config, areas, plan, *, epoch: int, seed: int):
    """Build one epoch's stream. Called once per epoch by the composition root, UNCONDITIONALLY --
    dat.resample is read HERE, not by the caller. At resample=False the same Stream object is
    returned for every epoch after the first (a byte-identical replay, which the old tree also did
    but only said so in a warning), and data.resample counts the redraws.

    Segments of _rng.randint(dat.seg_min, dat.seg_max) bytes are drawn from an area chosen
    uniformly among the phase's live areas. dat.seg_contig=False seeks to a random offset inside
    the area body each segment; True reads the body in order from a cursor that PERSISTS ACROSS
    EPOCHS, so an English-only run has only the text's own boundaries rather than discontinuities
    we manufacture every 8-20 KB (self_organize.py:1291-1298 -- eng_only reported 71 domains partly
    by counting our own seek points). The default is False and is a LITERAL, not a computed
    default: the shipped `1 if NP == 1 else 0` resolved to 0 on both shipped configurations.

    THE PHASE FILL IS EXACT: phase k covers [round(k*B/P), round((k+1)*B/P)) and the final segment
    of a phase is TRUNCATED to the bound rather than overshooting it by a whole 700-1800 byte
    segment, so phase bounds do not drift and len(Stream.bytes) == dat.stream_bytes exactly
    (ISSUES L22).

    The generator is rng_for(f"data.stream.e{epoch}", seed): what text a run trains on depends on
    the seed and the epoch and nothing else, so two arms differing in one unrelated knob still read
    the same text at epoch 2, and a resume at epoch 5 reads what an uninterrupted run read at
    epoch 5. The old form read SEED out of os.environ from INSIDE the stream builder
    (self_organize.py:1375-1392), which is the L2 violation this replaces.

    `area_changes` is the subset of splice starts where the area actually CHANGED. The old tree
    scored boundary precision/recall against every splice start including consecutive segments from
    the same area, so on a one-area run all ~96 'true switches' were artefacts (ISSUES H10). BOTH
    lists leave this package so no consumer has to guess which one it wanted.

    Stream carries an `epoch` and a `stream_id` so MEM can invalidate or re-base provenance rather
    than silently carrying byte offsets into a stream that no longer exists (ISSUES M83).

    RETURNS: Stream.

    LEVERS READ: stream_bytes, seg_min, seg_max, seg_contig, resample
    WIRES READ: none
    DID IT FIRE: data.stream_draw, data.segment, data.contig_wrap (unreachable at seg_contig=False,
                 with the gate arithmetic), data.resample (unreachable at resample=False -- the
                 "every epoch is a byte-identical replay" state, STATED rather than warned about),
                 data.phase_entered (must equal len(schedule) per epoch or the fill is drifting),
                 rng.issued()["data.stream.e0"].draws (0 draws = armed-but-inert)
    """
    dat = dat.owned_by("DATA")
    raise NotImplementedError(
        "DATA.draw_stream: P4 (data) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section DATA.")


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
