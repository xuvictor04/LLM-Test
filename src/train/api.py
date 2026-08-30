"""RUN -- the frozen public surface. Signatures only; P4 writes the bodies.

RUN owns the SHAPE OF THE RUN and nothing else: how long it lasts (epochs), what root of
randomness it starts from (seed), what machine and arithmetic every package inherits (device,
tf32, amp), and which half of the program executes (bench, profile). It serves GOAL B because a
continual-learning claim is a claim about what survives a SECOND PASS, and in the old tree EPOCHS
set the run length AND the cosine horizon (:6016-6028), so every retention number ever produced
was confounded with an unrequested schedule change. It serves GOAL A because `seed` is the number
every paired comparison turns on, and compare.py:251 records that it was absent from the _EFF
banner it pairs runs from.

RUN DECLARES NO CADENCE AND NO THRESHOLD. The loop's cadences belong to the mechanisms they fire;
`Cadences` EVALUATES a period another package owns. That is a claim a later reader can test by
grepping this package for `%` and for a threshold literal. What RUN contributes mechanically is
one thing: EXACTLY ONE PLACE IN THE TREE WHERE A COUNTER ADVANCES, and exactly one kind attached
to each counter. The old tree wrote `i += WIN; step += 1` in TWO places (:6796 in the early-out and
:7708 at the flush tail), 900 lines apart, and every argument in this project about which clock a
gate compares against is downstream of that duplication.

NAMING NOTE, VERIFIED: the directory is src/train/, the class is RUNLevers, PREFIX = "RUN". Two
stale `TRAIN.*` strings survive inside spine/assemble.py's NOT_WIRES prose; the live table names
no TRAIN package and `build(environ={})` resolves without one.

RECORD TYPES RETURNED (P4 defines them):
  Process   device, autocast, tf32_applied, amp_state ("off" | "active" | "declined"), amp_reason
  RunMode   bench, profile, timing
  Tick      step, epoch, flush_due, rolled, finished
  Timing    span(name) -> a context manager; spans() -> {name: seconds}
"""
from spine.lever import Config


def process_setup(run: Config):
    """Apply the process-wide arithmetic settings ONCE, before any package is built.

    Returns Process(device, autocast, tf32_applied, amp_state, amp_reason). `autocast` is a
    zero-argument callable returning a context manager -- torch.autocast when device == "cuda" and
    amp == "bf16", otherwise contextlib.nullcontext. amp_state "declined" is THE LEGAL-AND-INERT
    CASE (RUN_AMP=bf16 on CPU) and amp_reason carries the sentence, because that is G4's
    armed-but-inert state and must be reportable rather than silent -- :5719-5725 printed it once,
    at step 0, in a line no grid ever read, and it covered every spelling but "fp16": RUN_AMP=
    bfloat16 on an H100 trained the whole run in fp32 having been asked for bf16. `choices=`
    refuses the spelling now; the "ignored on device" state survives as a reading.

    TF32 IS ASSIGNED, NOT GUARDED. The old form `if TF32: allow_tf32 = True` (:1057-1062) means
    RUN_TF32=0 declines to turn matmul TF32 ON while cuDNN's own default is ALREADY True, so a run
    launched to rule matmul precision out of a determinism question still ran cuDNN in TF32 and the
    config line said the knob was off. Both attributes take the resolved boolean, and
    Process.tf32_applied records THE PAIR OF VALUES ACTUALLY WRITTEN, not the requested flag. This
    matters more than it looks: tf32 moves the float noise floor, which is the quantity G2 measures
    and G3's isolation sweep is read against.

    A CORRECTION TO THE CENSUS, recorded here because it changes what the port must carry:
    CENSUS.md:398 says the old fp16 refusal was "a SystemExit reachable only on CUDA". It is not --
    `if AMP == "fp16": raise SystemExit(...)` sits at MODULE SCOPE (:1075-1081) and fires at import
    on any box. The census was misled by the source's own comment three lines above, which is true
    of the autocast branch and false of the refusal later placed over it.

    LEVERS READ: device, tf32, amp
    WIRES READ: none
    DID IT FIRE: Process.tf32_applied, Process.amp_state
    """
    run = run.owned_by("RUN")
    raise NotImplementedError(
        "RUN.process_setup: P4 (train) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section RUN.")


def mode(run: Config):
    """Which half of the program runs, and whether the step is instrumented.

    Returns RunMode(bench, profile, timing) where `timing` is a Timing whose span() is a SINGLE
    SHARED NO-OP context when profile is False, so the instrumentation can live in the hot path
    with no second code path to rot (:5743-5745). THE COMPOSITION ROOT branches on .bench to decide
    whether to run the eval battery; nothing in this package knows what a battery is.

    prompt.py's `os.environ["BENCH"]="1"` import trick (prompt.py:41) does not port -- from_env is
    called once, in build(), and a module mutating the environment to steer a later import works
    only by accident of ordering. "Do not run the report" is the ENTRY POINT choosing which half to
    run, not a lever; see FOR THE OWNER Q-RUN-7.

    LEVERS READ: bench, profile
    WIRES READ: none
    DID IT FIRE: RunMode.bench, RunMode.profile, Timing.spans() -- an EMPTY dict when profile is
                 off, and an empty dict and an absent one are different statements
    """
    run = run.owned_by("RUN")
    raise NotImplementedError(
        "RUN.mode: P4 (train) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section RUN.")


def streams(run: Config, subsystems):
    """One independent, name-keyed RNG stream per named subsystem, built from the run seed.

    Returns {name: spine.rng.Rng}. THE SEED VALUE DOES NOT TRAVEL: assemble.NOT_WIRES refuses a
    d_seed wire, and what a package receives is its own stream. derive_seed is blake2b of
    (seed, name), explicitly NOT seed+index -- the offset form COLLIDES ACROSS RUNS (subsystem #1
    at seed=1 and subsystem #0 at seed=2 both get 2), which makes two "independent" replicates
    share streams pairwise and understates the between-seed spread every comparison in this project
    is read against.

    LEVERS READ: seed
    WIRES READ: none
    DID IT FIRE: spine.rng.issued() -- a subsystem present with ZERO DRAWS is armed-but-inert; a
                 subsystem ABSENT never asked. Both statements must be printable (G4).
    """
    run = run.owned_by("RUN")
    raise NotImplementedError(
        "RUN.streams: P4 (train) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section RUN.")


def new_clock(run: Config, *, batch_windows, accum, resume_step=0, resume_epoch=0):
    """The run's counters, TYPED, and the ONLY object in the tree that increments any of them.

    batch_windows and accum are OPT's and arrive as plain ints. resume_step/resume_epoch come from
    a CKPT Snapshot. Returns RunClock with:
        .step        units.Windows    -- what `step` counted at :6796 and :7708
        .flushes     units.Flushes    -- what `_nbwd` counted; the loop body's own clock
        .backwards   units.Backwards  -- what accumulation must count (derive.accum_due)
        .opt_steps   units.Steps      -- optimizer steps; the ONLY Steps clock the loop owns
        .epoch       units.Epochs
        .batch_len   int              -- windows queued in the accumulator

    BACKWARDS AND FLUSHES ARE DISTINCT KINDS AND MUST NOT BE ONE VARIABLE. `_nbwd` was
    simultaneously the backward counter used by the accumulation gate at :7193 AND the FLUSH
    counter used by six management cadences (:6819, :6836, :6961, :6988, :7077, :7325). The two
    coincide only because there is exactly one backward per flush; if a flush ever ran more than
    one -- microbatching inside a flush, the obvious next optimisation -- every management cadence
    would silently change period and nothing would say so. Clock._same raises across kinds, so the
    two cannot be one variable.

    LEVERS READ: epochs (via RunClock.finished)
    WIRES READ: none
    DID IT FIRE: RunClock.counters() -- the five typed counters plus the batch flush count.
                 flushes == 0 with step > 0 means the batch never filled.
    """
    run = run.owned_by("RUN")
    raise NotImplementedError(
        "RUN.new_clock: P4 (train) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section RUN.")


class RunClock:
    """The run's typed counters. Constructed by new_clock(); never instantiated by a package."""

    def begin_epoch(self, windows_in_epoch):
        """Declare how many WINDOWS this epoch's stream holds.

        Called once at start and again after every roll, because a resampling stream is a
        different length each epoch. THE LENGTH ARRIVES AS A COUNT OF WINDOWS -- never as a byte
        budget divided by a token window, which is the live byte/token confusion behind
        `steps = STREAM_LEN // WIN` at :4317 and :4719: `stream_bytes // ctx` overstates the step
        count by the compression ratio (~2.5x at a grown vocabulary), and the LR horizon and every
        ETA were computed from it. See FOR THE OWNER Q-DATA-8.
        """
        raise NotImplementedError("RUN.RunClock.begin_epoch: P4 (train) fills this in.")

    def advance(self):
        """Advance one window. Returns Tick(step, epoch, flush_due, rolled, finished).

        `flush_due` is True when the accumulator has reached batch_windows; the caller runs the
        flush body and then calls note_backward(). `rolled` means the stream was exhausted and the
        epoch incremented -- the caller must supply a fresh stream and call begin_epoch(); THE
        PARTIAL BATCH IS DROPPED HERE, as at :6533, because it holds (bpos, i) indexing the OLD
        token stream and carrying it across a resample writes memory entries whose provenance
        points at unrelated text. `finished` is True when epoch >= run.epochs.

        ONE ADVANCE, NOT TWO: the early-out and the flush tail converge here.
        """
        raise NotImplementedError("RUN.RunClock.advance: P4 (train) fills this in.")

    def note_backward(self):
        """Record one backward pass and answer whether an optimizer step is due.

        Returns derive.accum_due(self.backwards, accum). The old gate was `_nbwd % ACCUM == 0`
        (:7193) on a counter that HAPPENED to be Backwards, so it was accidentally right; the gate
        before it was on `step`, and two real runs one line apart measured 55 optimizer steps where
        13 were due. Passing a Windows clock here raises UnitError.
        """
        raise NotImplementedError("RUN.RunClock.note_backward: P4 (train) fills this in.")

    def counters(self):
        """The five typed counters plus the batch flush count, as the DID IT FIRE surface."""
        raise NotImplementedError("RUN.RunClock.counters: P4 (train) fills this in.")


def new_cadences(run: Config):
    """The gate ledger. ONE object; every periodic gate in the run goes through it.

    Reads NONE of RUN's levers. EVERY PERIOD IS AN ARGUMENT -- a units.Windows supplied by the
    package that owns the threshold (CKPT.every, EVAL.curve_every, FAB.manage_every,
    TOK.retok_every, DOM.manage_every, MEM.probe_every). RUN evaluates; RUN does not own a single
    threshold.

    LEVERS READ: none
    WIRES READ: none
    DID IT FIRE: Cadences.ledger() -> {key: (checks, fires, last_fired_step, period)}. A key with
                 checks > 0 and fires == 0 is armed-but-inert with its own arithmetic attached.
    """
    run = run.owned_by("RUN")
    raise NotImplementedError(
        "RUN.new_cadences: P4 (train) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section RUN.")


class Cadences:
    """The one cadence primitive in the tree. Constructed by new_cadences()."""

    def due(self, key, period, clock):
        """True at most once per `period` WINDOWS elapsed since this key last fired.

        ELAPSED-SINCE-LAST-FIRE, NOT MODULO, and this is the load-bearing repair in the package.
        `step % N == 0` evaluated BELOW the batch early-out asks for a simultaneous solution to two
        congruences that usually has none: simulated over 200,000 windows the mint fired 999 times
        at BATCH_W=1 and ZERO times at BATCH_W in {2, 8, 15, 16, 32}, odd ones included. CKPT_EVERY
        sat in that block, so a long run would never have checkpointed. Elapsed-since-last-fire is
        PHASE-INDEPENDENT, so a gate may be evaluated per window or per flush and mean the same
        thing -- which is what lets CKPT.every stay Windows while its gate runs at the flush tail,
        and what makes MEM's Windows cadences need no Windows->Flushes conversion.

        `period` MUST be units.Windows. An int raises; a Flushes raises. _fired[key] seeds at the
        RESUMED step, not 0 (:5281-5282 already did this), so the first post-resume evaluation does
        not bank the whole resume step count.
        """
        raise NotImplementedError("RUN.Cadences.due: P4 (train) fills this in.")

    def ledger(self):
        """{key: (checks, fires, last_fired_step, period)} -- the DID IT FIRE surface for every
        periodic gate in the run, in one place, whoever owns the threshold."""
        raise NotImplementedError("RUN.Cadences.ledger: P4 (train) fills this in.")


def bench_summary(run: Config, clock, *, elapsed_s, bytes_per_window, n_params, timing=None):
    """Throughput, printed INSTEAD of the eval battery. Returns the lines, or None when bench is
    off.

    bytes_per_window ARRIVES AS AN ARGUMENT and must be the LIVE value. ISSUES L42: `_bpw` was
    initialised at the SEED vocabulary (:6237) and refreshed only inside the RATE_EVERY tick
    (:6493), so a short BENCH run that never reached a tick quoted kB/s and GB/day at the seed
    vocabulary. Note what makes that structural: a RUN-owned throughput number whose correctness
    depended on an INSTRUMENT's cadence.

    LEVERS READ: bench
    WIRES READ: none
    DID IT FIRE: the returned record carries clock.opt_steps, clock.step and whether timing spans
                 were available (bench prints the per-component breakdown only when profile is on)
    """
    run = run.owned_by("RUN")
    raise NotImplementedError(
        "RUN.bench_summary: P4 (train) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section RUN.")


def startup_refusals(run: Config, *, disk_stream):
    """The guards a Lever declaration cannot express. Returns a list of refusal strings; the entry
    point raises on a non-empty list BEFORE ANY TENSOR IS ALLOCATED.

    (1) RUN_EPOCHS=0 resolves to 0 and the loop would run no passes. `EPOCHS = max(1, _i(...))` at
        :5467 SILENTLY REWROTE IT; a coercion at read time that makes a printed number a lie is the
        FAB_MIN_STEPS shape, so this is a refusal naming the lever, not a repair.
    (2) epochs > 1 with `disk_stream` false replays byte-identical text every epoch (:5470-5472),
        because _resample ran only under DISK_STREAM. A continual-learning result taken that way is
        a MEMORISATION result. THIS IS A TWO-PACKAGE GUARD -- RUN's length against DATA's resample
        flag -- and it can live in neither levers.py, so disk_stream arrives as a plain bool from
        the composition root.
    (3) amp != "off" with device == "cpu" is NOT refused: it is legal and inert, and
        Process.amp_state says so.

    LEVERS READ: epochs, device, amp
    WIRES READ: none
    DID IT FIRE: the returned list; an empty list is a positive result and is printed as one
    """
    run = run.owned_by("RUN")
    raise NotImplementedError(
        "RUN.startup_refusals: P4 (train) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section RUN.")
