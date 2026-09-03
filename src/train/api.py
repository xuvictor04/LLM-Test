"""RUN -- the frozen public surface. Signatures only; P4 writes the bodies.

RUN owns the SHAPE OF THE RUN and nothing else: how long it lasts (epochs), what root of
randomness it starts from (seed), what machine and arithmetic every package inherits (device,
tf32, amp), and which half of the program executes (bench, profile). It serves GOAL B because a
continual-learning claim is a claim about what survives a SECOND PASS, and in the old tree EPOCHS
set the run length AND the cosine horizon (:6016-6028), so every retention number ever produced
was confounded with an unrequested schedule change. It serves GOAL A because `seed` is the number
every paired comparison turns on, and compare.py::main records that it was absent from the _EFF
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
  Process   device, autocast, tf32_applied, torch_seed,
            amp_state ("off" | "active" | "declined"), amp_reason
  RunMode   bench, profile, timing
  Tick      step, epoch, flush_due, rolled, finished
  Timing    span(name) -> a context manager; spans() -> {name: seconds}
"""
import contextlib
import dataclasses
import time

import torch

from spine.lever import Config
from spine import rng as _rng
from spine import units as U


# ==================================================================================================
# THE ONE FIXED CADENCE IN THIS PACKAGE, AND WHY IT IS NOT A LEVER
# ==================================================================================================

PROGRESS_WINDOWS = U.Windows(100)
"""How often the progress/ETA line and the profiler dump are emitted. NOT A KNOB (Q-RUN-1, RESOLVED
2026-09-02: option (b)). A DEFAULT WITH NO ENVIRONMENT NAME -- there is nothing to turn off.

WHY IT EXISTS AT ALL. Three statements in the tree disagreed about who owns this cadence:
eval/levers.py and .rework/CENSUS.md both said "a separate RUN-owned log CADENCE", eval/api.py said
"RUN's own fixed CONSTANT", and `grep -i progress` over src/ returned nothing -- neither a lever nor
a constant existed. A cadence and a constant are different objects with different obligations (a
census row, an environment name, a Cadences.ledger key, cadence_audit coverage), so it was a live
fork and not a wording difference. This is the constant, and the other two statements now name it.

WHY IT IS NOT A LEVER, WHICH IS THIS PACKAGE'S OWN RULE. levers.py opens with "nothing here is a
cadence, a threshold or a weight" and lists the seven numbers RUN owns; a module constant is not a
lever and does not break that sentence, while an eighth `RUN_PROGRESS_EVERY` would. It also needs no
census row: the ancestor is RATE_EVERY, whose census verdict is `rename` to EVAL_CURVE_EVERY, and
the SPLIT this constant implements is written into that row already. And the split's whole purpose
argues against a knob: RATE_EVERY drove five things at once, so setting RATE_EVERY=100000 to quieten
a smoke run SUPPRESSED THE CURVE TABLE ENTIRELY and the curve fix went unverified for a round. A log
cadence that can be turned up is a log cadence that silently disables things. If it ever must be
tunable, that is one census row and one lever, added deliberately.

WHY 100 WINDOWS, STATED BECAUSE IT IS A DEFAULT AND DEFAULTS ARE THE OWNER'S. It has to be sane at
BOTH ends of the range because nothing can move it. At the shipped defaults a run is at most 937
windows and about 506 at the project's measured 1.85 bytes/token, so 100 fires ~5 times: the old
default of 2000 would fire ZERO times and put this line straight onto the ISSUES P1-C11 list, which is
the one cadence where being unreachable is a pure loss -- no measurement is confounded by a progress
line, and a meter that never prints is not a meter. It is also the shortest cadence already declared
in the tree (DOM.manage_every = 100), so it can never be the reason a report has nothing in it. On a
long run (94 MB, ~400k windows) it is ~4000 lines over hours, which is what an ETA meter is for.

WHY units.Windows AND NOT A BARE int. Cadences.due states "period MUST be units.Windows. An int
raises", and Config hands back a bare int for all 35 levers that declare a Clock unit -- ISSUES P1-H51,
three of five gates were handed bare ints until 2026-08-30. The accessors (EVAL.curve_period and its
three siblings) exist to re-attach the kind a lever declares and drops. A module constant has no
Config to drop it, so it is written typed at its definition and needs no accessor and no new entry
point. THIS IS A CONSTRUCTION, NOT A CONVERSION: it re-attaches a kind, it does not cross one.

IT GOES THROUGH _periods AND THEREFORE THROUGH Cadences. compose.py states the rule -- "Every
PERIODIC gate goes through Cadences.due(key, period, clock) with a period its OWNING package
supplied, so the modulo form that fired zero times at every BATCH_W > 1 is not writable at a call
site" -- and a progress line evaluated as `step % PROGRESS_WINDOWS == 0` below the batch early-out
is that defect exactly. new_cadences adds the other half: "THE KEYS ARE THE ROOT'S", so the key must
come from the root's mapping rather than be invented at the call site. Hence `_periods`' sixth key,
'progress'. IT HAS NO LOOP_ORDER ROW and cannot have one: rows are entry-point calls and no entry
point prints this line -- the loop driver does. Its DID IT FIRE is Cadences.ledger()['progress'],
and cadence_audit covers it like the other five.
"""


# ==================================================================================================
# THE RECORDS THIS PACKAGE RETURNS
# ==================================================================================================
#
# FROZEN, because a caller that can write to one of these can move a counter. RUN's whole mechanical
# contribution is "exactly one place in the tree where a counter advances", and a mutable Tick handed
# to thirteen packages is thirteen places again. `frozen=True` is the cheapest form of that promise
# and it is checked by the language rather than by a comment.


@dataclasses.dataclass(frozen=True)
class Process:
    """What the process-wide settings RESOLVED to, not what was asked for.

    `tf32_applied` is the PAIR actually written to torch -- (matmul, cudnn) -- and not the requested
    flag, because the defect this record answers is a knob that reported itself off while cuDNN ran
    TF32 anyway from its own default. `amp_state` carries the third state: "declined" is bf16 asked
    for on a device that has no autocast for it, which is legal, inert, and must be readable.

    `torch_seed` is the seed torch's PROCESS-GLOBAL default generator IS ACTUALLY RUNNING ON, read
    back out of torch after it was written, and it is here for the same reason `tf32_applied` is:
    both are process-wide state this function mutates, and a mutation nobody can read back is
    indistinguishable from one that never happened. It is what makes seeding that generator a
    DECLARED setting rather than a silent global side effect -- process_setup names it on its own
    DID IT FIRE line, and a reader checks it against torch.initial_seed() directly.
    """
    device: str
    autocast: object
    tf32_applied: tuple
    amp_state: str
    amp_reason: str
    torch_seed: int


@dataclasses.dataclass(frozen=True)
class RunMode:
    bench: bool
    profile: bool
    timing: object


class Timing:
    """Wall-clock attribution for the training step, and a single shared no-op when it is off.

    ONE CODE PATH, WHICH IS THE POINT. `span()` returns a context manager either way, so the
    instrumentation sits in the hot path unconditionally and there is no second, uninstrumented
    branch to rot. The old tree had the branch and it drifted.

    `spans()` returns {} when profiling is off. An EMPTY dict and an ABSENT one are different
    statements -- "measured nothing" versus "did not measure" -- and RunMode always carries a
    Timing so the caller can tell them apart.
    """

    __slots__ = ("_on", "_spans")

    def __init__(self, on):
        self._on = bool(on)
        self._spans = {}

    @contextlib.contextmanager
    def _timed(self, name):
        t0 = time.perf_counter()
        try:
            yield
        finally:
            self._spans[name] = self._spans.get(name, 0.0) + (time.perf_counter() - t0)

    def span(self, name):
        return self._timed(name) if self._on else contextlib.nullcontext()

    def spans(self):
        return dict(self._spans)


def process_setup(run: Config):
    """Apply the process-wide arithmetic settings ONCE, before any package is built.

    Returns Process(device, autocast, tf32_applied, amp_state, amp_reason, torch_seed). `autocast`
    is a zero-argument callable returning a context manager -- torch.autocast when device == "cuda"
    and amp == "bf16", otherwise contextlib.nullcontext. amp_state "declined" is THE LEGAL-AND-INERT
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

    TORCH'S PROCESS-GLOBAL GENERATOR IS ONE OF THESE SETTINGS AND IT WAS THE ONE NOBODY SET
    (2026-09-03). Every explicit torch random op in src/ already passes `generator=` a per-subsystem
    stream -- src/lm/api.py::build_model, src/sig/api.py::build, src/fabric/api.py::build and
    src/world/api.py::build all do -- but `nn.Dropout` and `nn.TransformerEncoderLayer`'s internal
    attention and residual dropout take NO `generator=` argument at the installed torch, so they
    draw from the global default generator, which torch seeds from OS entropy at import. That is a
    torch API gap and not an oversight in this tree: checked at torch 2.13.0+cu130 against
    inspect.signature of nn.Dropout.forward, nn.TransformerEncoderLayer.forward and
    torch.nn.functional.dropout, and none of the three has a generator parameter to receive one.
    MEASURED BEFORE FIXING, on this machine: two fresh CPU processes at RUN_SEED=0, LM_DROPOUT=0.2
    reported torch.initial_seed() of 3695151007048800332 and 4263715014176632393, and LM.encode()
    over an identical zero batch summed to 3.682344 against 4.750506 on the gru arm (-106.479309
    against -212.809799 on the transformer arm at LM_LAYERS=2), while the SAME pair of processes at
    LM_DROPOUT=0.0 agreed exactly (5.071722 twice) and every model parameter agreed on every run
    (-19.315695), because initialisation was already on a named stream. G2's determinism floor is
    measured from two identical seeded runs, so at LM_DROPOUT>0 an entirely different dropout mask
    was being absorbed into a number this project reports as float noise.

    WHY THIS FUNCTION OWNS IT, AND WHAT WAS REJECTED. The first line of this docstring already
    claims the process-wide settings ONCE, before any package is built, and a generator seeded from
    OS entropy is a process-wide setting in exactly the sense tf32 is: nothing about WHAT is
    computed, everything about whether two runs of it agree. It has to be applied before any build,
    because the first consumer to draw from an unseeded global takes OS entropy and no later call
    can put that back. No package can own it -- src/lm/api.py::build_model runs after other packages
    may already have drawn, and its own contract declares it reads no lever -- and
    src/spine/rng.py::rng_for cannot reach the consumer at all, since its whole discipline is a
    stream handed down as an argument and nn.Dropout has nowhere to receive one. Declaring a
    "torch.global" entry in src/spine/compose.py::RNG_SUBSYSTEMS was considered and rejected on two
    counts: that tuple is minted into a map the root SUBSCRIPTS to hand each package its own stream,
    so an entry no package holds would put a non-subsystem into a register whose documented three
    states (drew / armed-but-inert / never asked) are statements about packages; and it is a spine
    edit this package has no standing to make.

    WHAT IT DOES NOT BUY, SAID PLAINLY: REPRODUCIBILITY IS NOT ISOLATION. nn.Dropout still draws
    from one shared stream, so torch DRAW ORDER remains a channel between packages that no wire
    declares -- a lever that changes how many masks LM draws still shifts every mask drawn after it,
    which is the exact confound src/spine/rng.py's module docstring exists to remove for the streams
    it does cover. Seeding gives every run at one seed the same sequence; it does not give each
    package its own. Closing that needs generator-aware dropout replacing both nn.Dropout and
    nn.TransformerEncoderLayer's internals, which is LM's arithmetic to change and is not written.
    Named here so a reader of the L3 sweep knows which channel the per-subsystem register does not
    cover, rather than inferring from its silence that there is none.

    "torch.global" IS A DERIVATION LABEL, NOT A MINTED STREAM, and this sentence exists because the
    opposite mistake has already been made once in this tree (a docstring naming rng.issued()["lm"]
    as its own firing surface when the draw had moved to a child). It will NEVER appear in
    src/spine/rng.py::issued() and nobody should grep for it there: src/spine/rng.py::derive_seed is
    a pure blake2b of (run seed, name) that mints nothing, so this function stays callable twice in
    one process, which rng_for would not be. The distinct name rather than the bare run seed is
    src/spine/rng.py::Rng.torch_generator's own stated rule -- one integer standing beside two
    different generators in every log is a thing no reader can check. The firing surface is
    Process.torch_seed, read back out of torch.

    LEVERS READ: device, tf32, amp, seed (new on 2026-09-03; the process-global torch generator is
                 seeded from it through spine/rng.py::derive_seed, and the three paragraphs above
                 say why this function and not a package is the site)
    WIRES READ: none
    DID IT FIRE: Process.tf32_applied, Process.amp_state, Process.torch_seed -- the last one read
                 back with torch.initial_seed() AFTER the write, so it is what torch is running on
                 and not what this function asked for. It equals derive_seed("torch.global", seed)
                 on every process at that RUN_SEED and differs at a different one; two runs whose
                 reported torch_seed matches and whose LM.encode output does not have a
                 non-determinism that is NOT this one.
    """
    run = run.owned_by("RUN")
    device = str(run.device)
    tf32 = bool(run.tf32)
    seed = int(run.seed)

    # SEEDED HERE AND NOWHERE ELSE, AND BEFORE THE tf32 WRITES BELOW -- not because tf32 draws, but
    # because "before any package is built" is only true if it is the first thing this function
    # does. derive_seed MINTS NOTHING (pure blake2b of the pair), which is what keeps this callable
    # twice in one process; rng_for("torch.global", seed) would raise on the second call, and a
    # process-wide settings applier that fails the second time it is asked is a new failure mode
    # with nothing to do with its job. The name is a derivation label, not a stream -- see above.
    torch.manual_seed(_rng.derive_seed("torch.global", seed))
    # READ BACK, NOT ASSUMED, exactly like tf32_applied below: the record carries the seed torch is
    # RUNNING ON. A number this function merely passed to a setter is the same class of claim as the
    # knob that reported itself off while cuDNN ran TF32 from its own default.
    torch_seed = int(torch.initial_seed())

    # ASSIGNED, NOT GUARDED, on BOTH attributes -- the docstring above says why. `if tf32:` would
    # leave cudnn.allow_tf32 at its own default of True on a run launched with RUN_TF32=0 to rule
    # matmul precision out of a determinism question.
    torch.backends.cuda.matmul.allow_tf32 = tf32
    torch.backends.cudnn.allow_tf32 = tf32
    applied = (bool(torch.backends.cuda.matmul.allow_tf32),
               bool(torch.backends.cudnn.allow_tf32))

    # THE THREE STATES, AND "declined" IS THE ONE THAT MATTERS. `choices=` already refused every
    # spelling but "off"/"bf16", so what is left is the case the old tree lost silently: bf16 asked
    # for on a device with no autocast for it. It is not an error and it is not "active".
    amp = str(run.amp)
    if amp == "off":
        state, reason = "off", "RUN_AMP=off: the step runs in fp32."
        cast = contextlib.nullcontext
    elif device.startswith("cuda"):
        state = "active"
        reason = f"RUN_AMP={amp} on {device}: the LM step runs under torch.autocast."
        cast = lambda: torch.autocast(device_type="cuda", dtype=torch.bfloat16)
    else:
        state = "declined"
        reason = (f"RUN_AMP={amp} was requested and DECLINED: device is {device!r}, which has no "
                  f"bf16 autocast here, so the step runs in fp32. This is the armed-but-inert "
                  f"state, reported rather than silent -- the old tree ran fp32 having been asked "
                  f"for bf16 and said so once, at step 0, in a line no grid read.")
        cast = contextlib.nullcontext

    return Process(device=device, autocast=cast, tf32_applied=applied,
                   amp_state=state, amp_reason=reason, torch_seed=torch_seed)


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
    return RunMode(bench=bool(run.bench), profile=bool(run.profile),
                   timing=Timing(bool(run.profile)))


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
    seed = int(run.seed)
    # MINTED HERE, ALL OF THEM, AND THAT IS WHY rng.issued() IS A REGISTER RATHER THAN A SAMPLE. A
    # subsystem that mints its own stream later is absent from issued() until it does, so "never
    # asked" and "not built yet" would be the same reading. Minting every declared name up front
    # makes the ledger complete at step 0 and leaves `.draws == 0` to carry armed-but-inert.
    return {name: _rng.rng_for(name, seed) for name in subsystems}


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
        `steps = STREAM_LEN // WIN` at :4317: `stream_bytes // ctx` overstates the step count by
        the compression ratio (~2.5x at a grown vocabulary).

        THE OLD CLAIM ATTACHED TO THIS SENTENCE WAS WRONG AND IS CORRECTED (Q-DATA-8, 2026-09-02).
        The LR horizon and the runtime ETA were NOT computed from the byte form: `_project` uses
        `len(stream) // WIN` over the TOKEN stream (:6236, :6339). The byte form survives in the
        pre-run [probe] banner (:4317) and in one cadence period (:7319). The horizon's real defect
        is the shrinkage projection at :6338-6362 -- Q-OPT-5, and OPT's -- and sending an
        implementer here to look for it is how one bug gets fixed twice, differently.
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
        """The five typed counters plus the batch flush count, as the DID IT FIRE surface.

        `step` -- the WINDOW total -- IS THE OBSERVED SIDE OF THE HORIZON COMPARISON (Q-OPT-5).
        OPT's schedule horizon is resolved ONCE at build() from epoch 0's length times RUN.epochs,
        while this clock re-measures every epoch through begin_epoch(); minting merges bytes into
        tokens, so every later epoch is SHORTER and the run ends BELOW the projection with the
        cosine incomplete -- an under-anneal of unmeasured size. Both quantities are declared
        surfaces on two packages that may not read each other, so the COMPOSITION ROOT joins them
        in the report: derive.opt_steps_from_windows(Windows(step), d_effective_batch_windows)
        against st.horizon.run_steps, two units.Steps, so the residual is a subtraction. RUN does
        not compute the comparison and does not name OPT's horizon; it publishes the observed side.
        """
        raise NotImplementedError("RUN.RunClock.counters: P4 (train) fills this in.")


def new_cadences(run: Config, *, periods):
    """The gate ledger. ONE object; every periodic gate in the run goes through it.

    Reads NONE of RUN's levers. EVERY PERIOD IS AN ARGUMENT -- `periods` is {key: units.Windows},
    each supplied by the package that OWNS the threshold. RUN evaluates; RUN does not own a single
    threshold THAT DECIDES ANYTHING THE MODEL COMPUTES. The narrowing is 2026-09-02's and is exact:
    one of the six periods, 'progress', is RUN's own PROGRESS_WINDOWS -- a log cadence, a module
    constant, NOT a lever, and the exception is stated here rather than smuggled past a sentence
    that would otherwise be false (Q-RUN-1). `Reads NONE of RUN's levers` is unaffected: a module
    constant is not a lever and this function still reads no Config.

    THE SIGNATURE SAID Config AND NOTHING ELSE UNTIL 2026-08-30, while this docstring said every
    period is an argument. There was no parameter to pass one through, so the sentence describing
    the package's whole design was unimplementable -- and a reviewer found it by reading the two
    against each other. It is now a real parameter.

    THE SIX PERIODS THIS DOCSTRING USED TO NAME WERE THREE WRONG. It listed CKPT.every,
    EVAL.curve_every, FAB.manage_every, TOK.retok_every, DOM.manage_every and MEM.probe_every. Five
    gates exist in the order tables -- 'curve', 'dom.manage', 'fab.manage', 'dom.rekey' and 'ckpt'
    -- so TOK.retok_every and MEM.probe_every were named here while being evaluated INSIDE their own
    packages (TOK.on_window's four cadences, MEM.maintain's internal comparison against a Windows
    `now`), and MEM.rekey_every, which drives the 'dom.rekey' gate, was not named at all. A ledger
    that lists gates it does not evaluate and omits one it does is worse than no ledger:
    Cadences.ledger() is the DID IT FIRE surface, and every key missing from it is a mechanism whose
    "0 fires" nobody can read.

    A SIXTH KEY, 'progress', ARRIVES WITH NO ROW, AND THAT IS CORRECT RATHER THAN AN OMISSION
    (Q-RUN-1, RESOLVED 2026-09-02). Its period is PROGRESS_WINDOWS at the top of this file -- this
    package's ONE fixed cadence, a module constant and not a lever. It has no LOOP_ORDER row because
    rows are entry-point calls and NO ENTRY POINT PRINTS THE PROGRESS LINE: the loop driver does,
    the way it owns the window cut compose.py names _window_bounds. It is in the mapping anyway,
    because the alternative is `step % PROGRESS_WINDOWS == 0` at a call site -- the modulo form that
    fired 999 times at BATCH_W=1 and ZERO times at every BATCH_W in {2, 8, 15, 16, 32} -- and
    because a gate outside the ledger has no readable "0 fires" and no cadence_audit coverage. So
    six keys, five of them rowed.

    THE KEYS ARE THE ROOT'S, NOT THIS FUNCTION'S. compose.py's cadence table is the authority on
    which key maps to which owner's period, and docs/04_CONTRACT.md prints it. This function
    accepts the mapping and records against it.

    LEVERS READ: none
    WIRES READ: none
    DID IT FIRE: Cadences.ledger() -> {key: (checks, fires, last_fired_step, period)}. A key with
                 checks > 0 and fires == 0 is armed-but-inert with its own arithmetic attached; a
                 key ABSENT was never wired, which is a different statement and G4 needs both.
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

    bytes_per_window ARRIVES AS AN ARGUMENT and must be the LIVE value. ISSUES P1-L42: `_bpw` was
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

    THE NOT-REFUSED CASE IN (3) NAMES device AND amp BUT READS NEITHER, AND THE LEVERS READ LINE
    USED TO CLAIM IT DID. (3) is prose ABOUT the pair -- it explains why no code below checks
    them -- not a read of either: process_setup (this package's OWN entry point) already declares
    both in its own LEVERS READ and already returns the third state, Process.amp_state ==
    "declined", with amp_reason carrying the sentence. Adding a read here would duplicate that
    declaration rather than complete it -- two packages, or even two entry points in the same
    package, computing one verdict twice is the exact defect the coupling table exists to prevent
    (see FAB.build's d_operating_population cross-check for the general case). Trimmed to what
    this function's body actually reads.

    LEVERS READ: epochs
    WIRES READ: none
    DID IT FIRE: the returned list; an empty list is a positive result and is printed as one
    """
    run = run.owned_by("RUN")
    out = []
    epochs = int(run.epochs)
    if epochs < 1:
        # REFUSED, NOT REPAIRED. `EPOCHS = max(1, _i(...))` rewrote a 0 to a 1 and then printed 1 in
        # the banner, so an operator who asked for zero passes got one and the log agreed with the
        # operator rather than with the run. A coercion at read time that makes a printed number a
        # lie is the FAB_MIN_STEPS shape and this package refuses it by name.
        out.append(f"RUN_EPOCHS={epochs}: the loop would make no passes. Set it to 1 or more. This "
                   f"is refused rather than clamped to 1, because a clamp makes the banner print a "
                   f"number the run did not use.")
    if epochs > 1 and not disk_stream:
        # THE TWO-PACKAGE GUARD, and the reason this function takes an argument at all. It cannot
        # live in either levers.py: RUN owns the length, DATA owns the resample flag, and neither
        # may read the other's lever.
        out.append(f"RUN_EPOCHS={epochs} with resampling off replays byte-identical text every "
                   f"epoch, so a continual-learning result taken this way is a MEMORISATION "
                   f"result. Turn DATA resampling on, or run one epoch.")
    # amp on a device with no autocast for it is NOT refused. It is legal and inert, and
    # Process.amp_state says "declined" with the sentence -- that is the reportable third state,
    # and refusing it here would make a legal configuration unrunnable.
    return out


def cadence_audit(run: Config, *, run_windows, periods):
    """Which gates cannot fire, given how long this run actually is. Returns a list of strings.

    STATED AT STARTUP, NOT RAISED, and the distinction is the whole design. A short run is a
    legitimate thing to ask for -- a smoke test is supposed to be short. What is not legitimate is a
    report that cannot separate "the mechanism ran and did nothing" from "the mechanism was never
    reached". So this returns the sentences and the caller prints them before the first window.

    THE MEASUREMENT THAT MADE IT NECESSARY (ISSUES P1-C11, confirmed 2026-08-30). At the shipped
    defaults DATA.stream_bytes=120000, LM.ctx=128 and RUN.epochs=1 give AT MOST 937 windows, about
    506 at the project's own measured 1.85 bytes/token -- and TEN cadence-shaped defaults are longer
    than that:

        CAP.pin_windows       20000   the capacity valve never lifts either cap
        MEM.use_decay_every   20000   usage decay never runs
        FAB.ponder_warm        8000   ponder never arms
        FAB.bal_warm           4000   the load-balance term never arms
        EVAL.verify_fit_steps  3000   the verification fit never runs
        TOK.retok_every        3000   the vocabulary is never re-segmented
        EVAL.curve_every       2000   THE LEARNING CURVE IS NEVER PROBED
        TOK.cand_window        1024   the candidate window never fills
        OPT.lr_warmup          1000   the run ends INSIDE warm-up
        SIG.warmup              800   the encoder warm-up never completes

    Every cadence carries the OLD system's value, tuned against STREAM_LEN=94000000 and 60k-step
    runs; stream_bytes carries a smoke-test value. Neither is wrong alone; together they describe a
    run in which almost nothing happens. PLAN's P3 exit criterion is "empty environment, 200 steps,
    reaches the end" -- so without this, a green P3 certifies a system in which every cadenced
    mechanism fired zero times.

    WHY IT COULD NOT BE A LEVER REFUSAL OR A BUILD-TIME WIRE. `run_windows` is not knowable when
    build() freezes: it needs bytes_per_token, MEASURED on a corpus the tokenizer has not seen. That
    is the same reason SIG's signature width is derive-and-keep rather than a coupling, and it is why
    this is an entry point placed after DATA.data_plan rather than a startup_refusal.

    `run_windows` is units.Windows and every period is units.Windows; derive.cadences_that_cannot_fire
    refuses any other kind at both ends.

    IT COVERS SIX GATES, NOT FIVE, SINCE 2026-09-02. The sixth is 'progress', whose period is this
    module's PROGRESS_WINDOWS constant (Q-RUN-1). It is deliberately 100 Windows so that it FIRES at
    the shipped defaults and never joins the list above: a progress/ETA meter that prints zero times
    is a pure loss -- no measurement is confounded by it -- and the old RATE_EVERY default of 2000
    would have made this the eleventh entry. That is a choice this audit can now check rather than a
    claim, which is the whole reason the constant is in the mapping.

    LEVERS READ: none
    WIRES READ: none
    DID IT FIRE: the returned list is the record. An EMPTY list is a real result and must be printed
                 as one -- "every declared gate can fire at this run length" -- because silence here
                 is indistinguishable from the audit not having run.
    """
    run = run.owned_by("RUN")
    raise NotImplementedError(
        "RUN.cadence_audit: P4 (train) fills this in -- it is one call to "
        "derive.cadences_that_cannot_fire plus the sentences. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section RUN.")
