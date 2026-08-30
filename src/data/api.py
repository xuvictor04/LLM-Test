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

    On dat.source == "real": reads dat.dir + "/train/<area>/*", skipping basenames starting with
    "_" and any .json -- fetch manifests were being spliced into the corpus and trained on as if
    they were English (datastream.py:69-71). Each area is read up to dat.corpus_cap bytes, and
    BYTES PRESENT IS RECORDED BESIDE BYTES TAKEN so the cap's bite is a printed number rather
    than a program warning about its own default (self_organize.py:5616-5618).

    On dat.source == "synthetic": builds dat.n_processes order-2 Markov generators over the five
    15-symbol alphabets (self_organize.py:1084-1099, :1314-1315), seeded from
    rng_for("data.synth", seed) so that two run seeds are two different synthetic corpora. Today
    they are not: make_proc is seeded by the PROCESS INDEX, so `DATA_SOURCE=synthetic` measures a
    between-seed spread with the data held constant (DEFECT D-A13). Holds nothing out.

    THE HELD-OUT BLOCK IS A SEEDED RANDOM CONTIGUOUS BLOCK PER AREA, from
    rng_for("data.holdout", seed), of size min(holdout_frac * present, val_cap) -- NOT the tail.
    The tail is a sample only if the corpus was written in no particular order, and the measured
    cost of assuming it was is py held out at 5.061 +/- 0.560 against 2.922 in-stream while eng
    (shuffled upstream) was 2.273 against 2.303 (self_organize.py:1173-1198). val_cap applies on
    BOTH paths; it applied only under DISK_STREAM before (ISSUES M82). The block is physically
    removed from the training body, so no sampling rule anywhere can reach it and there is no
    length any caller can read that includes it (ISSUES M81).

    An area whose usable body is below max(dat.seg_max + 1, MIN_AREA_BYTES) is a STARTUP REFUSAL,
    not a silent drop: dropping desynchronised CORP from DN and made report_holdout label the
    Python corpus 'eng', which the next run compared against last run's English and reported as
    forgetting (self_organize.py:1142-1160, ISSUES:1421). The floor is DERIVED from seg_max rather
    than the old literal 5000, which raised on rerun.sh's SEG_MIN=8000 (ISSUES L75).

    RECEIVES: seed <- RUN.seed, as an argument. DATA calls rng_for itself; assemble.NOT_WIRES
    rejects a d_seed by name.
    RETURNS: Areas.

    LEVERS READ: source, dir, areas, n_processes, corpus_cap, holdout_frac, val_cap, seg_max
    WIRES READ: none
    DID IT FIRE: data.area_open (one per area; unreachable on source=synthetic),
                 data.corpus_cap_trip (fired N / armed but 0, prints taken vs present per area),
                 data.holdout_block (prints offset+size per area), data.val_cap_trip,
                 data.area_refused (a refusal exits at startup, so N>0 is never seen in a
                 completed run), rng.issued()["data.synth"], rng.issued()["data.holdout"]
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
    areas is [[0,1],[1,2],[1,2],[2,3]] -- a REHEARSED sliding window, not pure add. D2 lands HERE,
    in the resolver, because there is no literal string meaning "the added area alone" independent
    of the area count. Plan.protocol records which of explicit / generated / stationary / pure_add
    ran; a schedule of one all-active phase is named "stationary" so the merged PHASED=0 arm still
    exists. dat.phases is floored at 2 AT THIS READ SITE: one phase cannot have anything fade and
    `faded` is read off the last phase, so PHASES=1 makes the unlearn test skip itself as vacuous.

    THE EXPOSURE ARITHMETIC, per area: draw = stream_bytes distributed by the schedule;
    exposure = draw * epochs / body_bytes. It is a WHOLE-RUN quantity: 60 MB of English beside
    8 MB of Python draws 2.00 MB/epoch from each -- quiet -- while over 8 epochs the added area is
    seen 2.1x and the original is 28% sampled, and "adding py cost eng X bits/byte" is then
    confounded with "py was memorised and eng was skimmed" (ISSUES:1620).

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
    DID IT FIRE: data.phase_resolved, Gate data.exposure_max, Gate data.exposure_skew,
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
    """Put the cursors and holdout offsets back. REFUSES LOUDLY if the recorded area names, holdout
    offsets or holdout sizes disagree with what open_areas just produced: a resume whose held-out
    block moved is a resume whose ACROSS THE RUN BOUNDARY number compares two different texts, and
    that is the one number goal B rests on.

    LEVERS READ: none
    WIRES READ: none
    DID IT FIRE: data.state_restored, data.state_refused
    """
    dat = dat.owned_by("DATA")
    raise NotImplementedError(
        "DATA.restore_stream_state: P4 (data) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section DATA.")
