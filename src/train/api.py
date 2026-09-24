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
from spine import derive as _derive
from spine import gate as _gate
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

    `torch_seed` is the seed torch's PROCESS-GLOBAL default generator WAS RUNNING ON WHEN THIS
    RECORD WAS MADE, read back out of torch after it was written, and it is here for the same reason
    `tf32_applied` is: both are process-wide state this function mutates, and a mutation nobody can
    read back is indistinguishable from one that never happened.

    IT MAKES SEEDING DECLARABLE, NOT YET DECLARED, AND THE DIFFERENCE IS MEASURED (2026-09-04). An
    earlier wording of this paragraph said the field "is what makes seeding that generator a DECLARED
    setting rather than a silent global side effect". A field is a PLACE TO PUT a declaration; the
    declaration happens when something says it out loud, and nothing in this tree does yet.
    `grep -rn torch_seed src/ tests/ docs/ tools/` returns hits ONLY inside this file, plus one prose
    line in .rework/DECISIONS.md -- no check, no banner, no other package reads it. ITS TWO SIBLINGS
    ON THIS RECORD STAND IN EXACTLY THE SAME PLACE, which is what keeps this a narrowing and not a
    hole: the same grep for `tf32_applied` and for `amp_state` outside this file returns NOTHING. So
    it is the P5 reporting layer not existing yet, uniformly, and not something peculiar to the seed
    -- and it becomes a real defect the day a banner prints tf32_applied and amp_state and leaves
    torch_seed out.

    AND BEING A SNAPSHOT OF THE WRITE, IT CAN GO STALE WITH NOTHING NOTICING. process_setup()
    followed by a later torch.manual_seed(999) leaves this field reporting the derived seed while
    torch.initial_seed() reports 999: no gate fires, no warning prints, nothing raises. That is the
    CORRECT semantics for a record of what was WRITTEN -- a property that re-read torch on every
    access would always agree with reality, but would report a number THIS FUNCTION NEVER SET and
    attribute a later write to it, which is a different lie in the same family as the tf32 knob that
    reported the request instead of the write -- and it is why process_setup's DID IT FIRE line
    states the comparison as something A READER DOES rather than as something this field guarantees. Whoever reads it checks it against
    torch.initial_seed() AT THE MOMENT OF READING, and a disagreement means something reseeded the
    global after this function ran.
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


@dataclasses.dataclass(frozen=True)
class Tick:
    """What one window's advance decided. FROZEN, for the reason the block above this class gives.

    `step` is units.Windows and `epoch` is units.Epochs -- the counters themselves, handed over with
    their kinds attached rather than unwrapped to bare ints, because the whole of this package's
    mechanical contribution is that the loop cannot compare one clock against another by accident.
    The three flags are plain bools: they are ANSWERS about this window, not counts of anything, and
    there is no kind for them to carry.

    THE ACCUMULATOR IS NOT HERE, AND THAT IS spine/compose.py::LOOP_ORDER's ruling rather than an
    omission -- "THE ACCUMULATOR IS WHERE THE FLUSH BATCH COMES FROM and Tick does not carry it --
    the cut is named once, at _flush_bounds". This record says a flush is DUE; the batch itself is
    the loop driver's, cut where that file names the cut.

    PRECEDENCE, restated from the same row because it is the caller's obligation and not this
    record's: `finished` is tested BEFORE `rolled`. Both can be True on one advance -- at the
    shipped RUN_EPOCHS=1 the only roll a run ever takes is exactly that one -- and a caller that
    tests `rolled` first re-enters the stage-E rows to draw a stream for an epoch the run has
    already finished.
    """
    step: object
    epoch: object
    flush_due: bool
    rolled: bool
    finished: bool


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
    from one shared stream, so torch DRAW ORDER is a channel that no wire declares -- a lever that
    changes how many masks LM draws shifts every draw taken FROM THE GLOBAL after it, which is the
    exact confound src/spine/rng.py's module docstring exists to remove for the streams it does
    cover. Seeding gives every run at one seed the same sequence; it does not give each package its
    own. Closing that needs generator-aware dropout replacing both nn.Dropout and
    nn.TransformerEncoderLayer's internals, which is LM's arithmetic to change and is not written.

    HOW BIG THAT CHANNEL ACTUALLY IS, MEASURED RATHER THAN ASSERTED, BECAUSE THE FIRST STATEMENT OF
    IT OVERREACHED (2026-09-04). This paragraph, and .rework/DECISIONS.md D12 with it, first said
    that adding a package which draws from the global, or reordering two that do, "still moves the
    numbers of every package downstream of it". At HEAD that is WIDER THAN THE TREE, and both halves
    of it were checked by running them rather than by reasoning about them.

    THE BUILD-TIME HALF IS INERT. Injecting 1 or 3 extra GLOBAL draws (torch.rand(n), no
    `generator=`) immediately after src/lm/api.py::build_model returns -- exactly what n extra
    dropout masks would consume -- leaves ALL 363 values a compose() builds byte-identical (digest
    34acff0aeb14dd4b in all three runs) while moving LM.encode's output every time
    (26905f117c4d32e7 -> 773820fb538ba090 -> 0b850362297af161). The real-lever form agrees: LM_LAYERS
    2 vs 4, which changes how many draws nn.TransformerEncoderLayer's constructors take from the
    global by a large amount, moves NO value outside LM. The only non-LM keys that differ are
    geometry.layers, geometry.param_estimate and the manifest row for lm.layers -- the lever's OWN
    DECLARED value, not drift. The reason is structural rather than luck: every package that
    constructs an nn.Module then overwrites every parameter FROM ITS OWN NAMED STREAM --
    src/lm/api.py::build_model's named_parameters loop, src/sig/api.py::_Encoder,
    src/fabric/api.py::build's pop.modules loop, src/world/api.py::build's encoder/world_proj/qproj
    loop. A constructor's global draws are consumed and then thrown away.

    THE RUNTIME HALF IS SINGLE-ENDED. Every explicit RNG-consuming torch call in src/ passes
    `generator=` a named stream -- twelve of them, across src/fabric/api.py, src/sig/api.py,
    src/world/api.py and src/lm/api.py -- and TOK's segmentation dropout draws from its own Rng
    (`stream.random()` in src/tok/api.py::_segment), not from torch at all. The only implicit
    consumers left are nn.Dropout and nn.TransformerEncoderLayer's internals, and both are
    constructed ONLY in src/lm/api.py. So at HEAD LM IS THE ONLY PACKAGE THAT DRAWS FROM THE GLOBAL
    GENERATOR AT RUNTIME, and the channel has one end: exhibiting it at all needs a probe on the far
    side. With the global reset to a fixed position before the forward, LM_LAYERS 2 vs 4 at
    LM_DROPOUT=0.2 moves a downstream nn.Linear(4, 4) (weights digest 5f87be0f2321e508 vs
    36dc18c1f2e82308) and the torch.rand(3) after it ([0.18013722, 0.73333818, 0.01200253] vs
    [0.62094098, 0.40641177, 0.740619]); the LM_DROPOUT=0.0 CONTROL makes the same two depths
    IDENTICAL (31a48739b3d15e14, [0.41499043, 0.43999398, 0.09452492]), so what moved is the dropout
    draw COUNT and nothing else about depth.

    SO THE HONEST SENTENCE IS: the channel is REAL and LIVE, and today it has EXACTLY ONE DRAWER. It
    ARMS -- and the wide claim above becomes true -- the moment a SECOND package draws from the
    global at runtime, or any package is constructed LAZILY, after a forward has already run. Named
    here so a reader of the L3 sweep knows which channel the per-subsystem register does not cover
    AND how large it is, rather than inferring from its silence that there is none, or from its first
    statement that it is bigger than it is.

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
                 seeded from it through spine/rng.py::derive_seed, and the WHY THIS FUNCTION OWNS IT
                 paragraph above says why this function and not a package is the site. A COUNT OF
                 PARAGRAPHS IS NOT A CITATION: this line said "the three paragraphs above" and the
                 2026-09-04 narrowing grew one of the three into five, which is the prose form of the
                 stale line number O12 exists to refuse)
    WIRES READ: none
    DID IT FIRE: Process.tf32_applied, Process.amp_state, Process.torch_seed -- the last one read
                 back with torch.initial_seed() AFTER the write, so it is what torch WAS running on
                 when this function returned and not what the function asked for. It equals
                 derive_seed("torch.global", seed) on every process at that RUN_SEED and differs at
                 a different one. Two runs that report the SAME torch_seed and still disagree on
                 LM.encode have some OTHER non-determinism, and this field is what lets a reader
                 rule this one out. ALL THREE ARE DECLARED AND, AT HEAD, UNREAD: nothing in src/,
                 tests/ or docs/ consumes any of them, so they are a surface P5's banner has still
                 to turn into a reading -- the Process docstring above measures that and says what
                 would make it a defect. And each is a SNAPSHOT: reseeding, or writing the tf32
                 attributes, after this call leaves the record saying what was true then, which is
                 why the comparison against torch.initial_seed() is an act a reader performs and not
                 a property the field keeps.
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


def new_clock(run: Config, *, batch_windows, accum, resume_step=0, resume_epoch=0,
              resume_backwards=0, resume_opt_steps=0):
    """The run's counters, TYPED, and the ONLY object in the tree that increments any of them.

    batch_windows and accum are OPT's and arrive as plain ints. resume_step/resume_epoch come from
    a CKPT Snapshot; resume_backwards/resume_opt_steps come from OPT's RESTORED OptState
    (n_backward, opt_step), which is 0/0 on a fresh run. Returns RunClock with:
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

    A MID-EPOCH RESUME REPLAYS THE EPOCH IT WAS INTERRUPTED IN, AND THIS IS THE SHARPEST EDGE OF
    THE SAME LIMITATION. `_in_epoch` -- how far into the CURRENT stream the loop has read -- is not
    among the two things a Snapshot hands back, so a clock resumed 400 windows into a 1000-window
    epoch begins that epoch at 0 and rolls 1000 windows later instead of 600. The run then trains
    1400 windows in an epoch declared to hold 1000, and the epoch boundary -- which is where DATA
    draws a fresh stream and where a continual-learning result takes its measurement -- lands in a
    place no lever asked for. Unlike the counters below this is not a reporting error: it changes
    WHERE the roll happens, so it changes what the model sees. It is stated here because the frozen
    signature cannot carry the number, and because a resume taken at an epoch boundary has none of
    this problem -- which is the configuration every result in this project has been taken under so
    far, and the reason it has not yet been paid for.
    TWO THINGS CHANGED ON 2026-09-24 AND THE REPLAY ITSELF DID NOT. The replay is now ANNOUNCED:
    spine/loop.py::_payload checkpoints counters()' in_epoch, and spine/compose.py warns on a
    mid-epoch resume with the windows replayed and the optimizer step it will end near against the
    OPT horizon (Q-RUN-10, which also says why the cursor is not restored). And the boundary resume
    this paragraph calls safe WAS NOT until then: compose drew epoch 0's stream whatever epoch the
    clock resumed in, so under DATA_RESAMPLE=1 an epoch-1 child trained on epoch 0's draw (Q-RUN-11).

    FOUR COUNTERS RESUME AND TWO START AT ZERO (2026-09-24; Q-RUN-9). `step` and `epoch` come off
    the Snapshot; `backwards` and `opt_steps` come off OPT's restored OptState, through the two
    DEFAULTED keywords, so `flushes` and `dropped_windows` are the only counters that begin at 0 and
    both are THIS PROCESS's. THE PARAGRAPH THAT STOOD HERE SAID ONLY TWO RESUMED AND CALLED THE COST
    A REPORTING ONE; IT WAS A TRAINING OUTAGE. note_backward decides a step with
    derive.accum_due(self.backwards, accum) and OPT.maybe_step re-decides it with
    accum_due(st.n_backward, accum); with this clock restarting at 0 and OPT's count restored, a
    parent saved partway through an accumulation put the two out of phase for the rest of the run.
    Driven at OPT_ACCUM=4: a 30-window parent (backward=30, step=7) resumed to 60 took ZERO
    optimizer steps in 30 backward passes -- every call the clock let through was one OPT found
    not due -- and then raised at OPT.counters, before the final save, so the child's weights were
    lost. Seeded from OPT's own count the two gates evaluate the same number and cannot disagree;
    spine/loop.py::_flush also compares them every flush and raises if they ever do. The earlier
    claim that the other counters could not resume without a contract change was true, and the
    contract change is the two keywords.
    WHAT THE SEEDING ALSO MENDS: counters() is "the OBSERVED SIDE OF THE HORIZON COMPARISON", and
    with opt_steps counted since the resume while `step` counted since the run began, the residual
    an owner read off that pair was the under-anneal PLUS the resume. Both are run totals now.
    `flushes` stays per-process, so a resumed run's report prints windows and optimizer steps as run
    totals beside a flush count that is this process's; run.py's banner says which is which.

    LEVERS READ: epochs (via RunClock._finished, published on every Tick as Tick.finished)
    WIRES READ: none
    DID IT FIRE: RunClock.counters() -- the five typed counters plus the batch flush count.
                 flushes == 0 with step > 0 means the batch never filled.
    """
    run = run.owned_by("RUN")
    # epochs IS READ HERE AND NOT IN advance(), which is what "LEVERS READ: epochs (via
    # RunClock.finished)" means. The Config is frozen and the clock outlives this call, so reading
    # it once and carrying the int keeps the lever out of the loop body entirely -- there is no
    # window at which a second read could disagree with the first.
    # A Clock IS REFUSED AT BOTH RESUME ARGUMENTS, because `int()` on one SUCCEEDS SILENTLY. That
    # is the exact sentence spine/derive.py uses to refuse a Clock in three places ("int() on a
    # Clock succeeds, so..."), and without it a Snapshot handing back Flushes(5) as `resume_step`
    # would seed a WINDOW counter from a FLUSH count and every later comparison would be off by the
    # batch width with nothing raising. The kinds are put on INSIDE the clock; what arrives here is
    # a plain count, and this refusal is what keeps "plain" from meaning "anything int() accepts".
    for _label, _v in (("resume_step", resume_step), ("resume_epoch", resume_epoch),
                       ("resume_backwards", resume_backwards),
                       ("resume_opt_steps", resume_opt_steps)):
        if isinstance(_v, U.Clock):
            raise U.UnitError(
                f"RUN.new_clock: {_label}={_v!r} is a Clock. It arrives from a CKPT Snapshot as a "
                f"plain count and the kind is attached here; int() on a Clock succeeds silently, so "
                f"a wrong-kind clock would seed the counter and raise nothing.")
    return RunClock(epochs=int(run.epochs),
                    batch_windows=int(batch_windows), accum=int(accum),
                    resume_step=int(resume_step), resume_epoch=int(resume_epoch),
                    resume_backwards=int(resume_backwards),
                    resume_opt_steps=int(resume_opt_steps))


class RunClock:
    """The run's typed counters. Constructed by new_clock(); never instantiated by a package.

    THE SIX COUNTERS ARE ATTRIBUTES AND THE KINDS ARE PUT ON HERE, ONCE. Every increment below is
    `self.x = self.x + Kind(1)`, never `self.x.n += 1`: spine/units.py::Clock carries `__slots__`
    and no __setattr__ guard, so the in-place spelling writes through to whatever object the
    attribute happens to point at -- which is the shared-class-default defect capacity/api.py::Valve
    records from the other end. Clock.__add__ returns a FRESH instance, so rebinding cannot alias.
    """

    __slots__ = ("step", "flushes", "backwards", "opt_steps", "epoch", "batch_len",
                 "epochs", "batch_windows", "accum", "windows_in_epoch", "_in_epoch",
                 "dropped_windows", "_resumed_at")

    def __init__(self, *, epochs, batch_windows, accum, resume_step=0, resume_epoch=0,
                 resume_backwards=0, resume_opt_steps=0):
        # THE RESUMED STEP IS THE STEP, not an offset held beside one. Cadences seeds _fired[key]
        # at whatever this reads on the first evaluation, so a clock that started at 0 and added
        # the resume afterwards would bank the entire resume step count into the first gate.
        self.step = U.Windows(int(resume_step))
        self.epoch = U.Epochs(int(resume_epoch))
        # WHERE THIS PROCESS STARTED, so a per-process rate can be told from a run total.
        self._resumed_at = int(resume_step)
        self.flushes = U.Flushes(0)
        # SEEDED FROM OPT'S RESTORED COUNT, NOT FROM 0, or note_backward's accum_due and
        # OPT.maybe_step's evaluate two different numbers -- see new_clock's FOUR COUNTERS RESUME.
        self.backwards = U.Backwards(int(resume_backwards))
        self.opt_steps = U.Steps(int(resume_opt_steps))
        self.batch_len = 0
        self.epochs = int(epochs)
        self.batch_windows = int(batch_windows)
        self.accum = int(accum)
        # DECLARED UNKNOWN RATHER THAN GUESSED AT ZERO. A length of 0 would make the first advance()
        # roll immediately; None makes begin_epoch's absence a refusal at the first window instead
        # of a run that rolls through every epoch without reading a single one.
        self.windows_in_epoch = None
        self._in_epoch = 0
        # WINDOWS THAT NEVER REACHED A BACKWARD PASS. The partial batch a roll discards is a
        # DELIBERATE drop with a reason (it indexes the old token stream), but a mechanism that acts
        # and cannot be counted is the armed-but-inert shape from the other side: a run that quietly
        # threw away four windows an epoch across forty epochs has lost a batch and a half and
        # nothing in the report says so. A plain int, because these are windows that were counted in
        # `step` and then not used -- not a clock of their own.
        self.dropped_windows = 0

    @property
    def _finished(self):
        """True when the run has completed every epoch it was asked for. Reads the epochs count
        new_clock resolved from the lever; `epoch` is Epochs and the comparison is same-kind.

        PRIVATE, AND THE UNDERSCORE IS THE WHOLE ARGUMENT. Written `finished` it became a PUBLIC
        entry point on a frozen surface, and two checks said so on the first run after it landed:
        K1 ("a public entry point outside the contract is one nobody has agreed to keep" --
        docs/04_CONTRACT.md does not declare it) and K6 ("named by no row in ASSEMBLY_ORDER or
        LOOP_ORDER and not in DEFERRED_ENTRY_POINTS"). Neither could be answered by adding a row,
        because ROWS ARE ENTRY-POINT CALLS and nothing calls this: the loop driver reads the answer
        off `Tick.finished`, which IS a declared field of a declared record. That is the same
        argument PROGRESS_WINDOWS makes for having no row of its own, one file up.
        SO THE PREDICATE IS INTERNAL AND ITS VALUE IS PUBLISHED, which is the shape that keeps the
        lever read honest without widening the surface. advance() puts it on every Tick, so a caller
        never needs to reach in here, and `epochs` still has exactly one reader.
        """
        return self.epoch >= U.Epochs(self.epochs)

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
        # A BARE COUNT, AND A Clock IS REFUSED -- the same way round as its sibling consumer, which
        # is the opposite of what this guard said when it was first written. The first draft here
        # demanded units.Windows and cited spine/compose.py::_run_windows' "IT RETURNS
        # units.Windows"; that sentence is about a DIFFERENT helper. The value handed here comes
        # from _windows_in_epoch, which is `(len(Segmentation.ids) - 1) // LM.ctx` -- a bare int by
        # design, because its other consumer is derive.run_windows_from_epochs, whose rate end
        # REFUSES a Clock in as many words: "a rate is a ratio of two kinds, not a count of one".
        # Demanding Windows here would have made one quantity need two spellings, one per call
        # site. Measured: the strict form raised UnitError on int(634) at the `epoch0` stage of
        # compose(environ={}) on 2026-09-15, which is how the mistake was caught.
        # THE KIND CANNOT SEE THIS ARGUMENT'S REAL DEFECT EITHER, which is the other half of why it
        # is not asked for. `stream_bytes // ctx` and `len(ids) // ctx` are both ints and both would
        # wrap as Windows; what separates them is WHICH STREAM was divided, and no type states that.
        # The division is named once, at _windows_in_epoch, for exactly that reason.
        if isinstance(windows_in_epoch, U.Clock):
            raise U.UnitError(
                f"RUN.RunClock.begin_epoch: windows_in_epoch={windows_in_epoch!r} is a Clock. This "
                f"epoch's length arrives as a plain count from spine/compose.py::_windows_in_epoch, "
                f"which is the same value derive.run_windows_from_epochs takes as its RATE and "
                f"refuses a Clock for. One quantity, one spelling.")
        if int(windows_in_epoch) < 0:
            raise ValueError(
                f"RUN.RunClock.begin_epoch: an epoch cannot hold {int(windows_in_epoch)} windows.")
        self.windows_in_epoch = int(windows_in_epoch)
        # THE EPOCH-LOCAL CURSOR RESETS AND THE RUN TOTAL DOES NOT. `step` is the run's window
        # total across every epoch -- it is what OPT's horizon is compared against -- while
        # `_in_epoch` is how far into THIS stream the loop has read, which is the only quantity a
        # roll may zero.
        self._in_epoch = 0

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
        if self.windows_in_epoch is None:
            raise RuntimeError(
                "RUN.RunClock.advance before begin_epoch: the clock does not know how long this "
                "epoch is, so it cannot say whether this window rolled it. compose.py calls "
                "begin_epoch at the `epoch0` stage for exactly this reason; a loop driver that "
                "reaches here first has skipped it.")
        # ONE ADVANCE, NOT TWO. The old tree wrote `i += WIN; step += 1` at :6796 and :7708, 900
        # lines apart, and every argument about which clock a gate compares against is downstream
        # of that duplication. Rebinding, never `.n +=` -- see the class docstring.
        self.step = self.step + U.Windows(1)
        self._in_epoch += 1
        self.batch_len += 1

        # THE FLUSH IS DECIDED BEFORE THE ROLL, so a batch that fills exactly on an epoch's last
        # window is FLUSHED rather than dropped. The drop below is for a PARTIAL batch, which is
        # what :6533 dropped; a full one has all its windows from the stream it was cut from and
        # discarding it would silently shorten the run by one optimizer step per epoch.
        flush_due = self.batch_len >= self.batch_windows
        if flush_due:
            # COUNTED WHERE THE BATCH FILLS, NOT WHERE THE BACKWARD HAPPENS, and that is the whole
            # reason Flushes and Backwards are two kinds. Incrementing this in note_backward would
            # make the two counters identical BY CONSTRUCTION, and the microbatching case the
            # new_clock docstring names -- more than one backward inside a flush -- would then be
            # undetectable in the very ledger that exists to detect it.
            self.flushes = self.flushes + U.Flushes(1)
            self.batch_len = 0

        rolled = self._in_epoch >= self.windows_in_epoch
        if rolled:
            self.epoch = self.epoch + U.Epochs(1)
            self._in_epoch = 0
            # RE-ARMED TO None, SO A CALLER THAT FORGETS begin_epoch IS REFUSED RATHER THAN SERVED
            # THE OLD LENGTH. advance()'s own docstring puts the obligation on the caller -- "the
            # caller must supply a fresh stream and call begin_epoch()" -- and without this line a
            # caller who skips it keeps rolling on the PREVIOUS epoch's window count. A resampling
            # stream is a different length every epoch, so that is not a small error: it is every
            # later roll landing at the wrong window, silently, with the run still reporting epochs.
            self.dropped_windows += self.batch_len
            self.windows_in_epoch = None
            # THE PARTIAL BATCH IS DROPPED HERE, as at :6533: it holds (bpos, i) indexing the OLD
            # token stream, and carrying it across a resample writes memory entries whose
            # provenance points at unrelated text. The count is taken ABOVE, before this zeroes it.
            self.batch_len = 0
        # `finished` is READ FROM THE PROPERTY so the record and this method cannot disagree, and
        # it is computed AFTER the roll -- the roll is what can finish the run.
        #
        # THE COUNTERS ARE COPIED OUT, AND WITHOUT THIS THE `frozen=True` ON Tick IS A PROMISE THE
        # LANGUAGE DOES NOT KEEP. The record block above says Tick is frozen "because a caller that
        # can write to one of these can move a counter" -- but dataclass freezing refuses to REBIND
        # THE FIELD and says nothing about the object the field points at, and spine/units.py::Clock
        # carries `__slots__` with no __setattr__ guard. Measured on 2026-09-15: `t.step = Windows(999)`
        # raises FrozenInstanceError, and `t.step.n = 999` on the very next line moves the CLOCK to
        # 999 windows, because the freshly-rebound self.step and the Tick's field are the same
        # object. `counters()` had the same hole. `type(x)(x)` is Clock's own documented copy
        # spelling -- __init__ takes a same-kind Clock and reads its `n` -- so this costs one
        # allocation per counter per window and buys back the guarantee the record claims.
        return Tick(step=type(self.step)(self.step), epoch=type(self.epoch)(self.epoch),
                    flush_due=flush_due, rolled=rolled, finished=self._finished)

    def note_backward(self):
        """Record one backward pass and answer whether an optimizer step is due.

        Returns derive.accum_due(self.backwards, accum). The old gate was `_nbwd % ACCUM == 0`
        (:7193) on a counter that HAPPENED to be Backwards, so it was accidentally right; the gate
        before it was on `step`, and two real runs one line apart measured 55 optimizer steps where
        13 were due. Passing a Windows clock here raises UnitError.
        """
        self.backwards = self.backwards + U.Backwards(1)
        due = _derive.accum_due(self.backwards, self.accum)
        if due:
            # THE CLOCK TAKES THE STEP COUNT, because new_clock is "the ONLY object in the tree
            # that increments any of them". A caller that incremented opt_steps itself would be a
            # second place a counter advances, which is the one thing this package contributes.
            self.opt_steps = self.opt_steps + U.Steps(1)
        return due

    def counters(self):
        """The five typed counters plus the batch flush count, as the DID IT FIRE surface -- and,
        since 2026-09-24, the clock's position in its epoch (in_epoch, windows_in_epoch), which the
        checkpoint carries so a resume can tell a boundary save from a mid-epoch one (Q-RUN-10).

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
        # TYPED ON THE WAY OUT, NOT UNWRAPPED. A reader that wants an int calls int() on one of
        # these and says so at their own call site; handing bare ints out of the DID IT FIRE
        # surface is how a Windows total gets compared against a Steps horizon by accident, which
        # is the comparison the composition root exists to make explicitly (Q-OPT-5).
        # COPIED OUT FOR THE REASON advance() GIVES AT LENGTH: handing back the live Clock objects
        # let a reader of the DID IT FIRE surface move the counters it was reading --
        # `counters()["backwards"].n = 4242` set the clock's backward count to 4242, measured.
        return {
            "step": type(self.step)(self.step),
            "flushes": type(self.flushes)(self.flushes),
            "backwards": type(self.backwards)(self.backwards),
            "opt_steps": type(self.opt_steps)(self.opt_steps),
            "epoch": type(self.epoch)(self.epoch),
            # WINDOWS COUNTED IN `step` THAT NEVER REACHED A BACKWARD PASS, because a roll discarded
            # the partial batch holding them. Published so the drop is readable.
            "dropped_windows": self.dropped_windows,
            # HOW MANY WINDOWS ARE QUEUED IN THE ACCUMULATOR RIGHT NOW. A plain int, because it is
            # not a clock. THE READING THIS LINE CARRIED UNTIL 2026-09-15 WAS UNREACHABLE: it said
            # "a run that ends with batch_len > 0 ended mid-batch and those windows never reached a
            # backward pass", but a run ends by finishing its last epoch, and the roll that finishes
            # it zeroes batch_len on the way past -- so the end-of-run value is 0 whether or not
            # windows were discarded. dropped_windows below is the reading that survives, and it
            # exists because this one did not.
            "batch_len": self.batch_len,
            # THE TARGET, PUBLISHED SO `finished` IS ANSWERABLE WITHOUT SPENDING A WINDOW. _finished
            # is private (see its own docstring) and reaches a caller only on a Tick, so a clock
            # RESUMED at epoch >= epochs could not be asked whether it was already done -- the
            # driver had to advance once to find out, and that one window is a window of training
            # the run was not asked for. `epoch` and this are the same comparison the property
            # makes, on the public surface, and it is a lever-derived count rather than a counter.
            # NOTHING ASKED IT UNTIL 2026-09-24, so a resume of a finished run spent exactly that
            # window and overwrote the final checkpoint; spine/compose.py now refuses such a resume
            # on this comparison and spine/loop.py::run refuses a finished clock (Q-RUN-10).
            "epochs_target": self.epochs,
            # WHERE IN THE CURRENT EPOCH THE CLOCK STANDS, published so a checkpoint can say it.
            # spine/loop.py::_payload writes both under payload['RUN'] and spine/compose.py reads
            # them back to WARN when a resume replays part of an epoch (Q-RUN-10): a Snapshot
            # carries only `step` and `epoch`, and at epoch > 0 those two cannot say whether the
            # save was on a boundary. Plain ints; windows_in_epoch is None between a roll and the
            # begin_epoch that follows it, which is exactly the moment a boundary save is taken.
            "in_epoch": self._in_epoch,
            "windows_in_epoch": self.windows_in_epoch,
            # THE STEP THIS PROCESS RESUMED AT (0 on a fresh run), so `step` minus this is the
            # windows THIS process advanced -- what a throughput is a rate of (bench_summary).
            "resumed_at": self._resumed_at,
        }


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
    # owned_by IS CALLED AND NOTHING IS READ THROUGH IT, WHICH IS THE POINT. "Reads NONE of RUN's
    # levers" is a claim about this body, and the ownership handshake is what makes the claim
    # checkable rather than a comment -- a later edit that reaches for run.epochs here has to get
    # past a Config that would hand it over, and O-series reads the LEVERS READ line against what
    # the body touches.
    run = run.owned_by("RUN")
    for key, period in periods.items():
        # EVERY DECLARED PERIOD IS CHECKED AT BUILD, NOT AT FIRST FIRE. Cadences.due refuses a bare
        # int, and three of the five gates were handed one until 2026-08-30 (H51) -- but due() is
        # evaluated inside the loop, so that refusal arrives after the model is built and the
        # corpus is drawn. Checking the mapping here moves every one of those failures to startup.
        if not isinstance(period, U.Windows):
            raise U.UnitError(
                f"RUN.new_cadences: the period for {key!r} is "
                f"{type(period).__name__}({period!r}), not units.Windows. Config hands back a bare "
                f"int for all 35 levers that declare a Clock unit, which is why each period comes "
                f"through its owning package's typed accessor (EVAL.curve_period and its "
                f"siblings); a bare int here is that accessor bypassed.")
    return Cadences(periods)


class Cadences:
    """The one cadence primitive in the tree. Constructed by new_cadences().

    THE LEDGER IS SEEDED WITH EVERY DECLARED KEY, AT BUILD, AND THAT IS WHAT MAKES G4's THIRD STATE
    READABLE. new_cadences' own DID IT FIRE line splits two readings a lazily-built dict cannot:
    "checks > 0 and fires == 0" is armed-but-inert, and "a key ABSENT was never wired". If the row
    only appeared once the gate was first evaluated, a gate that was wired and never reached would
    be indistinguishable from one nobody wired -- which is the armed-but-inert census category
    (57 records) arriving through the mechanism built to report it.
    """

    __slots__ = ("_periods", "_checks", "_fires", "_last", "_seeded")

    def __init__(self, periods):
        self._periods = dict(periods)
        self._checks = {k: 0 for k in self._periods}
        self._fires = {k: 0 for k in self._periods}
        self._last = {k: None for k in self._periods}
        # WHEN THIS KEY LAST FIRED, IN WINDOWS, seeded LAZILY at the first evaluation rather than
        # at 0 here. A baseline of 0 on a resume would make `elapsed = step - 0` exceed every period
        # on the first window -- every gate in the run firing at once because the run was resumed.
        # ON A RESUME restore() PUTS THE PARENT'S SEED HERE BEFORE THE FIRST EVALUATION (Q-RUN-9),
        # so the lazy seed is now what a fresh run, a key the parent did not have, and a checkpoint
        # written before 2026-09-24 get; new_cadences has no clock to read, so it happens where one
        # arrives.
        self._seeded = {}

    def due(self, key, period, clock):
        """Fires at a long-run RATE of once per `period` WINDOWS, with jitter bounded by the caller's
        evaluation stride.

        THIS SENTENCE READ "True at most once per `period` WINDOWS elapsed since this key last
        fired" UNTIL 2026-09-15, AND THE REMAINDER-CARRYING REPAIR BELOW MADE IT FALSE. Measured at
        a declared period of 100 evaluated at the flush tail with batch_windows=64: fires land at
        192, 320, 384, 512, 576 ... so the gaps alternate 128, 64, 128, 64 and FOUR of the first
        nine are SHORTER than the declared period. The old spelling guaranteed the spacing and got
        the rate wrong by up to 28%; this one guarantees the rate and lets the spacing jitter by at
        most one evaluation stride either side. Both are defensible and NEITHER IS FREE, so the one
        this implements is named here rather than left for a reader to infer from a sentence that
        describes the other.
        WHY RATE WAS THE ONE TO KEEP: every period in the mapping is an operator-set "every N
        windows", and all six consumers -- the checkpoint, the curve probe, two manage gates, the
        rekey and the progress line -- are counted per run rather than depended on for a minimum
        separation. A systematic 28% shortfall in how often a checkpoint is written is a silent
        wrong answer to the number somebody typed; an occasional 64-window gap where 100 was asked
        is not. If a gate is ever added that NEEDS the minimum separation, it needs a different
        primitive and this docstring is where that has to be argued.

        ELAPSED-SINCE-LAST-FIRE, NOT MODULO, and this is the load-bearing repair in the package.
        `step % N == 0` evaluated BELOW the batch early-out asks for a simultaneous solution to two
        congruences that usually has none: simulated over 200,000 windows the mint fired 999 times
        at BATCH_W=1 and ZERO times at BATCH_W in {2, 8, 15, 16, 32}, odd ones included. CKPT_EVERY
        sat in that block, so a long run would never have checkpointed. Elapsed-since-last-fire is
        PHASE-INDEPENDENT, so a gate may be evaluated per window or per flush and mean the same
        thing -- which is what lets CKPT.every stay Windows while its gate runs at the flush tail,
        and what makes MEM's Windows cadences need no Windows->Flushes conversion.

        `period` MUST be units.Windows. An int raises; a Flushes raises. A key with no seed seeds at
        the clock's CURRENT step, not 0, so a first evaluation never banks a resume's whole step
        count; on a resume from a checkpoint that carries payload['RUN'], restore() has already put
        the parent's seed back and the gate continues the parent's schedule (Q-RUN-9).
        """
        if key not in self._periods:
            # THE KEYS ARE THE ROOT'S, NOT A CALL SITE'S. A key invented here would have no ledger
            # row, no cadence_audit coverage and no readable "0 fires" -- which is the state this
            # class exists to remove, so an unknown key is a refusal and not a new row.
            raise KeyError(
                f"RUN.Cadences.due: {key!r} is not a declared gate. The declared keys are "
                f"{sorted(self._periods)}, assembled by spine/compose.py::_periods from the "
                f"package that OWNS each threshold. A gate whose key is not in that mapping is a "
                f"gate with no DID IT FIRE surface.")
        if not isinstance(period, U.Windows):
            raise U.UnitError(
                f"RUN.Cadences.due: the period for {key!r} is {type(period).__name__}"
                f"({period!r}), not units.Windows. An int raises and a Flushes raises; the kind is "
                f"what keeps this gate phase-independent across the window and flush call sites.")
        if period != self._periods[key]:
            # TWO SOURCES OF TRUTH FOR ONE THRESHOLD, REFUSED RATHER THAN RECORDED. The ledger
            # prints a period per key and the gate evaluates one; if they can differ, the report
            # says the run checked a cadence it did not check. Both come from the same _periods
            # mapping in a correct caller, so a disagreement is a defect and never a configuration.
            raise ValueError(
                f"RUN.Cadences.due: {key!r} was declared at {self._periods[key]} and evaluated at "
                f"{period}. The ledger prints the declared one, so a run that took this branch "
                f"would report a cadence it did not use.")
        self._checks[key] += 1
        # A NON-POSITIVE PERIOD IS DISARMED, AND WITHOUT THIS LINE IT WAS THE OPPOSITE: FIRE ALWAYS.
        # The comparison below is `now - seeded >= period`, and at Windows(0) that is `0 >= 0` on
        # the first evaluation after seeding and true on every one after -- so the gate fired on
        # EVERY WINDOW. CKPT_EVERY=0 IS THE SHIPPED DEFAULT and its declared meaning is "periodic
        # saving disabled", so measured at those defaults this fired 632 times in 633 evaluations:
        # the most expensive operation in the loop, running every window, on a configuration asking
        # for it never. (633 evaluations, not the run's full length -- compose(environ={}) reports
        # run_windows = Windows(634); the count is what the drive measured, not the run.)
        # THREE STATEMENTS DISAGREED AND ONLY THIS ONE WAS LOAD-BEARING. CKPT's own Gate on the same
        # object reports fired=False and says "the only saves this run makes are the FINAL one and
        # any SIGUSR1"; RUN.cadence_audit on the same mapping prints that 'ckpt' is DISARMED and
        # "cannot fire at ANY run length"; spine/derive.py::cadences_that_cannot_fire puts every
        # `period.n <= 0` in its cannot-fire list. All three described the intended behaviour and
        # this primitive did the reverse, which is the shape where a report is not merely wrong but
        # actively reassuring.
        # THE CHECK IS STILL COUNTED, so the ledger reads checks > 0 with fires == 0 and the period
        # column says 0 -- disarmed AND reached, which is a different fact from either a gate that
        # was never evaluated or one that was armed and never came due.
        # THE CLOCK IS TYPE-CHECKED BEFORE THE DISARMED EARLY-OUT, NOT AFTER. With the order the
        # other way round a caller passing garbage as `clock` got silently no error on any gate
        # whose period was 0 -- and 'ckpt' ships at 0, so the one gate most likely to be wired up
        # wrong was the one gate that validated nothing.
        now = clock.step
        if not isinstance(now, U.Windows):
            raise U.UnitError(
                f"RUN.Cadences.due: clock.step is {type(now).__name__}({now!r}), not "
                f"units.Windows. This gate measures elapsed WINDOWS since the last fire.")
        if int(period) <= 0:
            return False
        if key not in self._seeded:
            # SEEDED AT WHATEVER THE CLOCK READS NOW -- on a fresh run 1, and on a resume only when
            # restore() had nothing to put back (a pre-2026-09-24 checkpoint, or a key the parent
            # did not declare). The first evaluation therefore banks nothing and answers False; the
            # first fire comes one full period later.
            self._seeded[key] = now
            return False
        # ELAPSED-SINCE-LAST-FIRE, NOT MODULO. `step % N == 0` below the batch early-out asks for a
        # simultaneous solution to two congruences that usually has none: simulated over 200,000
        # windows the mint fired 999 times at BATCH_W=1 and ZERO times at BATCH_W in {2, 8, 15, 16,
        # 32}. CKPT_EVERY sat in that block, so a long run would never have checkpointed. The
        # subtraction is same-kind and Clock.__sub__ returns a Windows.
        elapsed = now - self._seeded[key]
        if elapsed >= period:
            # THE SEED ADVANCES BY WHOLE PERIODS, NOT TO `now`, AND THAT IS WHAT MAKES THE
            # PHASE-INDEPENDENCE CLAIM ABOVE TRUE RATHER THAN NEARLY TRUE. `self._seeded[key] = now`
            # DISCARDS THE REMAINDER at every fire, so a gate evaluated at the FLUSH TAIL -- where
            # `now` moves in steps of batch_windows -- silently lengthens its own period to the next
            # multiple of the stride. Measured over 20,000 windows at a declared period of 100,
            # evaluated per flush: effective period 100.5 at batch_windows=1, 104.2 at 8, 128.2 at
            # 32 and 129.0 at 64. A checkpoint cadence 28% slower than the number an operator set,
            # with nothing saying so, is the same class of defect as the modulo form this primitive
            # replaced -- smaller, and silent in the same way.
            # THE FLOOR-DIVISION BOUNDS THE CATCH-UP; IT DOES NOT REMOVE IT, and this comment said
            # it did. Advancing by a SINGLE period after a long gap would leave the seed far behind
            # `now` and fire on many consecutive calls; advancing by as many whole periods as have
            # elapsed lands the seed within one period of `now`, so the backlog is spent at once
            # instead of over a burst. What survives is jitter, not a burst: two CONSECUTIVE
            # evaluations can both fire when the stride is at least `period` minus the carried
            # remainder, which is how a declared period of 100 produces a 64-window gap at
            # batch_windows=64. The docstring states that trade. Evaluated per window the two
            # spellings are identical, because `elapsed` is then exactly `period` and the
            # multiplier is 1.
            self._seeded[key] = self._seeded[key] + type(period)(
                int(period) * (int(elapsed) // int(period)))
            self._fires[key] += 1
            self._last[key] = now
            return True
        return False

    def ledger(self):
        """{key: (checks, fires, last_fired_step, period)} -- the DID IT FIRE surface for every
        periodic gate in the run, in one place, whoever owns the threshold.

        RUN TOTALS ON A RESUMED RUN (2026-09-24, Q-RUN-9): Cadences.restore puts the parent's
        checks, fires and last-fired step back, so a gate that fired before the boundary does not
        read "0 fires" after it -- the same reason MEM's and TOK's restored counters are totals.
        cadence_audit is a different statement and is not affected: it is a startup sentence about
        which periods exceed the run length compose measured, not a count of fires."""
        return {k: (self._checks[k], self._fires[k], self._last[k], self._periods[k])
                for k in self._periods}

    def state(self):
        """What a checkpoint must carry for every gate to keep its SCHEDULE across a resume:
        {'seeded': {key: int}, 'checks': {key: int}, 'fires': {key: int}, 'last': {key: int|None}}.

        WITHOUT IT EVERY GATE RE-SEEDED AT THE RESUMED STEP (2026-09-24, Q-RUN-9). due() seeds
        lazily and answers False on its first evaluation, so a child resumed at step S first fired
        each gate at S + 1 + period instead of on the parent's schedule. Driven: a 160-window parent
        had fired dom.manage at 101; its child fired it next at 261 where the uninterrupted run
        fires at 201, and dom.rekey (period 200) moved from 201 to 361 -- domain culls, folds,
        MEM.apply_domain_plan and the rekey pushed back a period at every boundary, and a run
        resumed in chunks shorter than a period never managed at all. tok/api.py::_due names the
        same outcome as the defect it avoids for TOK's own cadences.
        Plain ints, so the payload holds no Clock object: the kinds are put back by restore().
        """
        return {"seeded": {k: int(v) for k, v in self._seeded.items()},
                "checks": dict(self._checks), "fires": dict(self._fires),
                "last": {k: (None if v is None else int(v)) for k, v in self._last.items()}}

    def restore(self, state):
        """Put back what state() wrote, for the keys STILL DECLARED. Returns how many keys were
        restored; 0 when `state` is None, which is what a checkpoint written before 2026-09-24
        carries -- those resume the old way, seeding lazily at the resumed step.

        A KEY THE PARENT HAD AND THIS RUN DOES NOT DECLARE IS DROPPED, and a key this run declares
        that the parent did not have stays lazy: both are the KEYS ARE THE ROOT'S rule. A PERIOD
        CHANGED AT THE BOUNDARY NEEDS NOTHING HERE: due() compares the elapsed windows since the
        restored seed against the period it is handed NOW, and the whole-period advance bounds the
        catch-up to one fire. A restored seed LATER than the clock (a non-final snapshot mixed with
        a later one) makes `elapsed` negative and the gate only waits, which is harmless.
        """
        if not state:
            return 0
        n = 0
        for k in self._periods:
            if k in state.get("seeded", {}):
                self._seeded[k] = U.Windows(int(state["seeded"][k]))
            if k in state.get("checks", {}):
                self._checks[k] = int(state["checks"][k])
                self._fires[k] = int(state.get("fires", {}).get(k, 0))
                _last = state.get("last", {}).get(k)
                self._last[k] = None if _last is None else U.Windows(int(_last))
                n += 1
        return n


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
    if not bool(run.bench):
        # OFF. Returns None rather than empty lines, because bench PRINTS INSTEAD OF the eval
        # battery -- a caller that got [] would print a heading with nothing under it where the
        # battery should have been.
        return None
    c = clock.counters()
    # THIS PROCESS'S WINDOWS, NOT THE RUN TOTAL (2026-09-24, Q-RUN-10): `step` resumes from the
    # checkpoint while elapsed_s is this process's wall clock, so on a resume the total divided by
    # these seconds was a rate for windows that were trained somewhere else.
    windows = int(c["step"]) - int(c["resumed_at"])
    # bytes_per_window IS AN ARGUMENT AND MUST BE THE LIVE VALUE, which is P1-L42 and is worth
    # restating at the arithmetic rather than only in the docstring: `_bpw` was initialised at the
    # SEED vocabulary (:6237) and refreshed only inside the RATE_EVERY tick (:6493), so a short
    # BENCH run that never reached a tick quoted kB/s and GB/day at the seed vocabulary. What makes
    # that structural rather than a slip is that a RUN-owned throughput number depended on an
    # INSTRUMENT's cadence for its correctness. Taking it as an argument moves the dependency into
    # the signature where a caller can see it.
    total_bytes = windows * float(bytes_per_window)
    secs = max(float(elapsed_s), 1e-9)
    lines = [
        f"bench: {windows} windows in {secs:.1f}s "
        f"({windows / secs:.1f} windows/s, {int(c['opt_steps'])} optimizer steps run total"
        + (f", resumed at step {int(c['resumed_at'])})" if int(c["resumed_at"]) else ")"),
        f"bench: {total_bytes / secs / 1024:.1f} kB/s over {total_bytes / 1024:.1f} kB, "
        f"at {float(bytes_per_window):.4f} bytes/window (LIVE, not the seed vocabulary)",
        f"bench: {total_bytes / secs * 86400 / 1e9:.3f} GB/day at this rate",
        f"bench: {int(n_params)} parameters in the optimizer",
        # THE CLOCKS, SO A READER CAN CHECK THE RATE RATHER THAN TAKE IT. flushes and backwards are
        # printed separately because they are two kinds and coincide only at one backward per flush.
        f"bench: clocks step={c['step']} flushes={c['flushes']} backwards={c['backwards']} "
        f"opt_steps={c['opt_steps']} epoch={c['epoch']} dropped_windows={c['dropped_windows']}",
    ]
    spans = timing.spans() if timing is not None else None
    if spans:
        # THE PER-COMPONENT BREAKDOWN ONLY WHEN PROFILE IS ON, which is what makes `timing=None` a
        # legitimate call rather than a missing argument.
        for name, secs_in in sorted(spans.items(), key=lambda kv: -kv[1]):
            lines.append(f"bench:   {name}: {secs_in:.2f}s ({secs_in / secs * 100:.1f}%)")
    else:
        # SAID RATHER THAN OMITTED. A breakdown that is simply absent reads as a breakdown that was
        # measured and found empty.
        lines.append("bench:   no per-component breakdown -- RUN_PROFILE is off, so no spans were "
                     "timed")
    return lines


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
    starved = _derive.cadences_that_cannot_fire(run_windows, periods)
    if not starved:
        # THE POSITIVE RESULT IS A RETURNED SENTENCE, AND THE ALTERNATIVE READING IS NAMED RATHER
        # THAN LEFT OPEN. This docstring requires that an empty result "must be printed as one",
        # and the only caller does `sysm.warnings.extend(cadence_audit(...))` -- so a literal empty
        # list is printed as NOTHING and is indistinguishable from the audit never having run,
        # which is the exact state the sentence forbids. The other reading puts the obligation on
        # the report instead; it is rejected here because the report does not exist yet and an
        # obligation owed to an absent reader is how C11 went unstated for a round in the first
        # place. If a report is later written that says this itself, this branch is what it
        # replaces -- and one of the two must go, because two sources would print it twice.
        return [f"cadence audit: every declared gate can fire at this run length -- "
                f"{len(periods)} gate(s) checked against a run of {run_windows}."]
    out = []
    # THE THIRD ELEMENT OF THE TUPLE MEANS TWO DIFFERENT THINGS AND THIS LOOP USED TO RENDER IT AS
    # ONE. spine/derive.py::cadences_that_cannot_fire appends `(key, period.n, 0)` when the period
    # is NON-POSITIVE and `(key, period.n, run_windows.n)` when the period merely exceeds the run --
    # so the 0 in the first branch is a SENTINEL, not a length. Printed through one f-string it
    # produced "'ckpt' has a period of 0 windows and this run is 0 windows long" on a run of 634
    # windows, in the same returned list as a 'curve' line correctly saying 634. Two lines from one
    # call disagreeing about the length of the run is a false equation in a report, which is the
    # defect this package's whole cadence apparatus exists to stop printing.
    # THE TWO ARE ALSO DIFFERENT FACTS AND DESERVE DIFFERENT SENTENCES. A period longer than the run
    # is a gate that is ARMED and STARVED -- lengthen the run and it fires. A period at or below
    # zero is a gate that is DISARMED at any run length, and no amount of running reaches it.
    for key, period_n, run_n in starved:
        if period_n <= 0:
            out.append(f"cadence audit: {key!r} has a period of {period_n} windows, so it is "
                       f"DISARMED rather than starved -- it cannot fire at ANY run length, and "
                       f"lengthening the run will not reach it. Whatever it gates does not happen "
                       f"in this run, and a report that says it did nothing is reporting a "
                       f"mechanism that was never armed, which is a different statement. Set a "
                       f"period of 1 or more on the package that owns this threshold.")
        else:
            out.append(f"cadence audit: {key!r} has a period of {period_n} windows and this run is "
                       f"{run_n} windows long, so it CANNOT FIRE ONCE. Whatever it gates does not "
                       f"happen in this run, and a report that says it did nothing is reporting a "
                       f"mechanism that was never reached -- which is a different statement. "
                       f"Shorten the period, or lengthen the run (DATA.stream_bytes, LM.ctx, "
                       f"RUN.epochs).")
    return out
