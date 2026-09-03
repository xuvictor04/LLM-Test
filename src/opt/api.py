"""OPT -- the frozen public surface. Signatures only; P4 writes the bodies.

OPT owns every rate the system applies and the size of the batch that rate acts on. Every rate is
`lr` times a multiplier in 0..1, and OPT owns the peak, the multiplier's shape, the decoupled
weight decay handed to both AdamW instances, and the two counts whose product is the effective
batch.

ON GOAL A it is the leading standing hypothesis for why language production has not worked yet:
all 17 pilots bottom in held-out bits/byte at ~2.4 around step 6000 and then RISE to ~3.8-4.1 by
48,000 -- across GRU and transformer, fabric and FABRIC=0, every routing variant (:7003-7011). A
cause common to every arm cannot be the fabric or the router. A constant 2e-3 on AdamW for 48k
steps is exactly that shape, and lr_sched="none" is the one-flag ablation for it.

ON GOAL B three levers are about forgetting rather than convergence. lr_min_frac exists because a
schedule that anneals to nothing cannot learn anything that ARRIVES LATE, and the add-area entry
point is the late-arrival case. lr_shift_warm is the schedule's half of note_shift(): growth is
already told "this jump is OURS, not the data's" while the learning rate meets the same fresh text
at 96-99% of peak. weight_decay is a forgetting term THE OPTIMISER introduces -- decoupled decay
is applied every step to every parameter regardless of gradient, so a dormant expert loses ~71% of
its magnitude over a 62.5k-step run.

THE COUNTER IS OPTIMIZER STEPS AND THAT IS THE UNIT REPAIR. OPT maintains its OWN counter of
optimizer steps, advanced only inside maybe_step, and hands THAT to lr_at, so units.Steps becomes
literally true for the counter. At the shipped defaults batch_windows=1, accum=1 the two counters
coincide, so no recorded result moves; at fetch_big.py's own recommended heavy-run command
(WIN=256 BATCH_W=16 ACCUM=4) they differ by 64x.

AND THE HORIZON STILL NEEDED A CONVERSION, WHICH THIS PARAGRAPH USED TO DENY. It said "no
conversion function is needed -- which matters, because spine/derive.py has no Windows->Steps
function today (verified)", and then the horizon four lines below did

    run_steps = max(1, run_windows // d_effective_batch_windows)

which IS a Windows->Steps conversion: a window count divided by windows-per-optimizer-step, inline,
on bare ints, in a package body. A reviewer found the assertion and the line together. Nothing was
numerically wrong at the defaults -- that is what made it survive -- but units.py::Clock.convert is explicit
that the point is naming: "There is no implicit path between kinds ... call the named function in
spine.derive that already knows the rate, so the conversion exists in one place with a name." It
was the only unnamed cross-kind conversion left in the tree.

It is now derive.opt_steps_from_windows(Windows(run_windows), effective_batch_windows) -> Steps,
which refuses a non-Windows at one end and a divisor below 1 at the other. The divisor spans BOTH
boundaries at once -- batch_windows is windows per flush, accum is flushes per optimizer step -- so
the answer is in optimizer steps, which is the only kind units.py allows an LR horizon. Dividing by
batch_windows alone would give Flushes and is a different function, flush_period_windows, on
purpose.

RECORD TYPES RETURNED (P4 defines them):
  OptState     base (the AdamW over param_groups["base"]), encoder (the AdamW over
               param_groups["encoder"]) -- THE TWO FIELDS ARE NAMED, AS OF 2026-09-02, Q-OPT-7:
               this line said "both AdamW instances" and named neither, so SIG.warm_up and
               SIG.train_step were handed the whole state with no expression for "the encoder one",
               and WORLD.manage's `add_param_group` deferral cited the identical hole. One
               vocabulary, and the words are build()'s own param_groups keys. K11 resolves a
               `produces` token against this block, so `encoder` is now a CHECKABLE provenance
               token rather than a comment;
               n_backward (Backwards), opt_step (Steps), lr_prev, restart_amp, cycle_best,
               cycle_index, horizon, param_group_shape, counters,
               shift_at, grad_norms -- TWO FIELDS ADDED BY P4 ON 2026-09-03, because two frozen
               docstrings below already read them and this block did not list them. lr_at's second
               modifier is spelled `0 <= opt_step - st.shift_at < opt.lr_shift_warm`, so the step
               of the last self-inflicted shift has to LIVE on the state between maybe_step (which
               is handed it) and lr_at (which is pure and can only read what it is given);
               counters() promises to RENDER quantiles "accumulated in maybe_step", so the sample
               they are taken over has to live somewhere, and every other field on this record is
               a scalar. Both travel in state_dict for the same reason restart_amp does: a re-warm
               that spans a run boundary, or a norm distribution that restarts empty, is the
               "came back at FULL AMPLITUDE" defect in a second and third place;
  Horizon      run_steps, warmup, wavelength, n_cycles
  StepOutcome  stepped, lr, restart, damped
  LoadReport   restored, refused, reason

`param_group_shape` IS IN THAT LIST BECAUSE load_state REFUSES ON IT (Q-OPT-4). state_dict wrote
every other field and not that one, so ISSUES P1-L50's refusal -- the one thing standing between a
resume and AdamW moments attached positionally to the wrong tensors -- compared against a value
nothing produced. An untrippable guard reads exactly like a guard that never had to fire.
"""
import dataclasses
import math

import torch

from spine.lever import Config
from spine import derive
from spine import units as U
from spine.gate import Gate


# ==================================================================================================
# THE RECORD TYPES. Fields only, no methods: every public method on a public class in an api.py is
# an ENTRY POINT (tests/test_contract.py::api_signatures counts them, K1 compares the set against
# docs/04_CONTRACT.md's ```contract block), and this package's surface is the seven functions
# below and nothing else.
# ==================================================================================================

@dataclasses.dataclass(frozen=True)
class Horizon:
    """The schedule's horizon, resolved ONCE at build() and never re-projected.

    run_steps, warmup and wavelength are units.Steps and not bare ints, because units.Steps is
    "what the LR schedule's horizon is denominated in, and nothing else" and the whole of Q-OPT-2
    is that the counter this is compared against is the optimizer-step counter rather than the
    window counter they coincide with at batch_windows=1, accum=1. n_cycles is a COUNT of cycles,
    not a clock: nothing compares it against a threshold in any kind.
    """
    run_steps: object
    warmup: object
    wavelength: object
    n_cycles: int


@dataclasses.dataclass
class OptState:
    """Both optimizers and everything the closed loop carries across a run boundary.

    NOT frozen, and that is the one mutable record this package has: opt_step and n_backward are
    counters, and a counter that cannot be advanced is not a counter. Every WRITE to it happens in
    exactly two functions -- scaled_backward advances n_backward, maybe_step advances everything
    else -- so "the schedule's counter, and the ONLY thing that advances it" is a property a reader
    can check by grepping this file for `st.`.
    """
    base: object
    encoder: object
    n_backward: object
    opt_step: object
    lr_prev: float
    restart_amp: float
    cycle_best: object
    cycle_index: int
    horizon: Horizon
    param_group_shape: tuple
    counters: dict
    shift_at: object = None
    grad_norms: list = dataclasses.field(default_factory=list)


@dataclasses.dataclass(frozen=True)
class StepOutcome:
    """What one call to maybe_step did. `lr` LEAVES THIS PACKAGE AS A RETURN VALUE, never as a
    local another package reads -- ISSUES P1-H15 is `_lrv` assigned inside `if LR_SCHED != "none"`
    and read unconditionally by the per-expert path, a NameError on the FIRST flush."""
    stepped: bool
    lr: float
    restart: bool
    damped: bool


@dataclasses.dataclass(frozen=True)
class LoadReport:
    """The resume verdict, by name. `refused` is the L50 guard having fired; `reason` is what it
    disagreed about, and it is a sentence rather than a flag because "shape mismatch" over a
    positional moment restore names nothing a reader can act on."""
    restored: bool
    refused: bool
    reason: str


# ==================================================================================================
# PRIVATE HELPERS. Underscore-prefixed so they are not entry points, and none of them takes a
# Config: tests/test_ownership.py::check_o9_one_config_per_signature requires every function with a
# Config-annotated parameter to assert its owner, and an owner assertion repeated in six helpers is
# six chances to write the wrong prefix. The public seven assert once and hand values down.
# ==================================================================================================

_FLOOR = 1e-12                       # only ever a denominator guard, never a rate


def _param_group_shape(param_groups):
    """The LIVE group structure load_state refuses against: order, tensor count, and each shape.

    THE ORDER IS PART OF THE ANSWER AND THAT IS THE WHOLE POINT. AdamW state is POSITIONAL over
    param groups, so a changed group ORDER silently attaches one tensor's moments to another
    (ISSUES P1-L50); a shape summary that sorted its keys would compare equal across exactly the
    rearrangement the guard exists to catch.
    """
    return tuple((str(name), len(tensors),
                  tuple(tuple(int(d) for d in tuple(getattr(t, "shape", ()))) for t in tensors))
                 for name, tensors in param_groups)


def _normalised_shape(shape):
    """A param_group_shape as nested tuples, so a list that survived a JSON round trip compares."""
    out = []
    for row in shape:
        name, count, tensors = row[0], row[1], row[2]
        out.append((str(name), int(count),
                    tuple(tuple(int(d) for d in t) for t in tensors)))
    return tuple(out)


def _shape_summary(shape):
    """The one-line form of a param_group_shape, for a refusal message."""
    return ", ".join(f"{row[0]}:{row[1]} tensor(s)" for row in shape) or "(no groups)"


def _cycle_index(horizon, step, restarts):
    """Which cosine cycle `step` falls in, 0-based. Pure arithmetic on one horizon.

    Split out of the schedule because maybe_step has to record st.cycle_index and the schedule is
    documented PURE -- it returns a rate, not a state.
    """
    w = int(horizon.warmup)
    run_end = int(horizon.run_steps)
    n = max(1, int(horizon.n_cycles))
    if not restarts:
        return 0
    if step >= run_end:
        return n - 1
    per_c = max(1.0, (run_end - w) / n)
    return max(0, int((step - w) / per_c))


def _schedule(*, lr, sched, min_frac, restarts, decay, shift_warm, restart_amp, shift_at,
              horizon, step):
    """The rate at `step`, plus the four gate observations. PURE: every input is an argument.

    Returns (rate, flags) where flags is (in_warmup, damped, shift_warm_applied, envelope_applied).

    THE OLD VERSION REACHED OUT OF ITSELF for `_shift_at`, which DATA's resample branch wrote as a
    closure variable (:6518-6521) -- the L2 violation this replaces. Here the shift step arrives as
    an argument that maybe_step read off the state that the composition root stamped.
    """
    if sched == "none":
        # THE ONE-FLAG ABLATION, and it returns the peak flat -- "none" restores the pre-schedule
        # behaviour EXACTLY, which is the property that makes it an ablation rather than an arm.
        return float(lr), (False, False, False, False)

    w = max(1, int(horizon.warmup))
    if step < w:
        # PAID ONCE, NOT PER CYCLE: the point of warmup is that the optimizer state is COLD, which
        # is only true the first time (:4762-4765). A restart returns to peak in ONE step by
        # design, which is exactly why the damping in group 3 exists.
        return float(lr) * (step + 1) / w, (True, False, False, False)

    run_end = int(horizon.run_steps)
    wave = max(1, int(horizon.wavelength))
    span = max(1, wave - w)
    n = max(1, int(horizon.n_cycles))

    if restarts:
        # WHOLE CYCLES ONLY, FITTED AT build(). Truncating instead left a 30-epoch run with 2
        # cycles and a THIRD of its length parked at the floor. At n == 1 this branch is
        # bit-identical to restarts=off (:4785), which is what keeps every earlier result
        # reproducible under the new default.
        per_c = max(1.0, (run_end - w) / n)
        if step < run_end:
            p = ((step - w) / per_c) % 1.0
            ci = max(0, int((step - w) / per_c))
        else:
            p = 1.0
            ci = n - 1
    else:
        p = min(1.0, (step - w) / span)
        ci = 0

    cyc = min_frac + (1.0 - min_frac) * 0.5 * (1.0 + math.cos(math.pi * p))

    damped = ci > 0 and restart_amp < 1.0
    if damped:
        # DAMP THE SWING ABOVE THE FLOOR, NEVER BELOW IT.
        cyc = min_frac + (cyc - min_frac) * restart_amp

    warmed = bool(shift_warm) and shift_at is not None and 0 <= step - int(shift_at) < shift_warm
    if warmed:
        # AN ATTENUATION, NEVER A REPLACEMENT. Returning `lr * ramp` would RAISE the rate whenever
        # a shift lands late in the anneal; this MULTIPLIES, so it can only ever lower the rate and
        # rejoins the cycle exactly where the cycle would have been.
        cyc *= max(min_frac, (step - int(shift_at) + 1) / shift_warm)

    enveloped = decay > 0.0 and n > 1 and run_end > w
    if enveloped:
        # GATED ON n > 1. Without the gate it multiplied a SINGLE cycle's cosine by a second cosine
        # that also bottoms at the floor, so a run that should end at lr_min_frac ended at
        # lr_min_frac SQUARED -- 0.0025 of peak, which is why LR_DECAY sat at 0.0 from the day it
        # was written.
        gp = min(1.0, max(0.0, (step - w) / max(1, run_end - w)))
        env = min_frac + (1.0 - min_frac) * 0.5 * (1.0 + math.cos(math.pi * gp))
        cyc = cyc * ((1.0 - decay) + decay * env)

    # THE FLOOR IS A FLOOR, AND THIS LINE IS WHAT MAKES lr_at's STATED PROPERTY TRUE. lr_at
    # promises "the schedule's minimum over a whole run equals lr * lr_min_frac at EVERY restart
    # count, single-cycle included". Each modifier above is individually floored at min_frac, and
    # that is NOT enough: the envelope MULTIPLIES a cycle that already bottoms at min_frac by a
    # second cosine that also bottoms at min_frac, so at n_cycles > 1 with the shipped
    # lr_decay = 1.0 the last cycle ends at min_frac SQUARED -- the identical arithmetic the `n > 1`
    # gate was added to remove from the single-cycle case, surviving one level up where the gate
    # cannot see it. Measured, at lr=2e-3, lr_min_frac=0.05, n_cycles=3: 5.0e-06 without this
    # clamp against 1.0e-04 with it, a factor of 20 below the floor an operator set. The same
    # applies to the shift re-warm, whose ramp can multiply a mid-anneal cycle below the floor.
    # lr_min_frac is a GOAL B lever -- "a schedule that anneals to nothing cannot learn anything
    # that ARRIVES LATE" -- so a floor that the composition of two floored terms can dive under is
    # not a floor, it is a coincidence that holds at the shipped defaults.
    cyc = max(min_frac, cyc)
    return float(lr) * cyc, (False, damped, warmed, enveloped)


def _quantile(sorted_values, q):
    """The q-quantile of an already-sorted list, by nearest rank. Empty -> None, never 0.0.

    NONE AND NOT ZERO, because Q-OPT-3's whole first half is that a norm of 0.0 reported for a run
    that never measured one is indistinguishable from a run whose gradients were zero -- which is
    exactly what reporting the quantile from counters(), after the zero_grad, would have produced
    with every check in this repository green.
    """
    if not sorted_values:
        return None
    k = min(len(sorted_values) - 1, max(0, int(round(q * (len(sorted_values) - 1)))))
    return float(sorted_values[k])


def _params_of(optimizer):
    """Every tensor an optimizer holds, in group order. The base group's, for the norm and the clip."""
    return [p for g in optimizer.param_groups for p in g["params"]]


def _global_grad_norm(params):
    """The global L2 norm over `params`' gradients -- the BASE group's, read while they still exist.

    SCOPE IS THE BASE GROUP AND THAT IS Q-OPT-3'S SECOND HALF: the encoder's gradients at flush time
    are produced on SIG's cadence and stepped by SIG (Q-OPT-6), so folding them into one number
    makes it uninterpretable.
    """
    total = 0.0
    for p in params:
        g = getattr(p, "grad", None)
        if g is None:
            continue
        n = float(g.detach().float().norm(2))
        total += n * n
    return total ** 0.5


def _reading(best_bpb):
    """(value, seed_count) out of whatever EVAL handed over, or (None, 0) for no reading at all.

    IT REFUSES A BARE FLOAT, and that refusal is the most important line this package has. The
    lever this feeds turns a HELD-OUT MEASUREMENT into a training decision -- the only number in
    the system crossing the instrument line backwards -- and PLAN 3.8 forbids a verdict on n=1. A
    float carries no seed count, so accepting one would make the seed-count rule unenforceable at
    the one site it exists for, silently, in the direction that always looks like it works.
    """
    if best_bpb is None:
        return None, 0
    value = getattr(best_bpb, "value", None)
    seeds = getattr(best_bpb, "seed_count", None)
    if value is None and seeds is None and isinstance(best_bpb, (tuple, list)) \
            and len(best_bpb) == 2:
        value, seeds = best_bpb
    if value is None or seeds is None:
        raise ValueError(
            f"OPT.maybe_step: best_bpb={best_bpb!r} carries no seed count. It is documented as a "
            f"Reading (value, seed_count) because a damped restart IS a verdict and PLAN 3.8 "
            f"forbids a verdict on n=1 -- a bare float would make that rule unenforceable at the "
            f"one site it exists for. Pass EVAL's Reading, a (value, seed_count) pair, or None.")
    return float(value), int(seeds)


# ==================================================================================================
# THE SEVEN ENTRY POINTS
# ==================================================================================================

def build(opt: Config, *, param_groups, run_windows):
    """Construct both optimizers, resolve the schedule horizon, and refuse the illegal settings.
    Returns an OptState.

    THERE IS NO `resume` PARAMETER, AS OF 2026-09-02 (Q-OPT-4, and A FROZEN SIGNATURE MOVED). It
    used to take `resume=None` and the root passed Snapshot.payload into it AND into load_state --
    one object, two entry points, adjacent rows. The overlap could not be resolved by documenting
    it, because the work the parameter would do does not exist: the live param-group structure is
    fully determined BEFORE this call (spine/compose.py restores LM, FAB and WORLD "STRICTLY BEFORE
    OPT.build", and the root assembles param_groups from those already-restored objects), so the
    checkpoint's influence on group shape arrives through the module restores, not through OPT.
    A second restore path would also move optimizer state past opt.ckpt.loaded / opt.ckpt.refused,
    which live on load_state -- counters describing one path while the state travels another.
    OPT.load_state IS THE WHOLE RESTORE PATH. The CAP analogue argues the same way and not the
    other: new_valve(restored=) takes the LIFTED CAP ALONE because Valve.origin must record where
    the starting cap came from, a fact the constructor cannot get any other way. build() has no
    equivalent fact.

    param_groups is {"base": [...Parameter], "encoder": [...Parameter]} -- plain lists another
    package's constructor returned. THOSE TWO KEYS ARE THE OptState FIELD NAMES (Q-OPT-7): the
    optimizer built over param_groups["encoder"] is st.encoder, which is what the root hands
    SIG.warm_up and SIG.train_step, and what WORLD.manage's add_param_group addresses. OPT DOES NOT WALK ANYBODY'S MODULE TREE and does not know what
    an encoder is; it knows that both get lr=opt.lr, weight_decay=opt.weight_decay (:4748/:4750)
    and that both get their param_groups' lr rewritten on every step. The old alias
    `WD = WEIGHT_DECAY` at :4329 -- one number, two names, the audit seeing only the first -- has
    no home here because the env name is generated from the field.

    THE HORIZON IS RESOLVED ONCE, HERE, IN OPTIMIZER STEPS, AND PRINTED:
        run_steps  = derive.opt_steps_from_windows(run_windows, d_effective_batch_windows)
        wavelength = opt.lr_wavelength or run_steps          # the 0 sentinel, in ONE visible place
        warmup     = min(opt.lr_warmup, max(1, run_steps // 10))
        n_cycles   = max(1, round((run_steps - warmup) / max(1, wavelength - warmup)))
                     if opt.lr_restarts else 1
    Two defects die here. The old tree resolved the sentinel by READING ANOTHER KNOB
    (`if LR_STEPS: return LR_STEPS`, else project through LR_EPOCHS, :6371) -- a computed default,
    which lever.py refuses by construction -- and the projection machinery carried its own faults:
    the cosine reached only p=0.760 on E8 and p=0.730 on E18 because the projected horizon overran
    the run, and on a resume `_ep_start` started at 0 while `step` started at the checkpoint's
    step, so the first epoch length was inflated and every remaining epoch was priced at half the
    last, latched and never revised upward (ISSUES P1-H17). And the WARMUP CLAMP is a fix that must
    survive: at LR_WARMUP=1000 a 360-step run NEVER LEAVES WARMUP and trains at a third of peak
    throughout, which reads as the schedule hurting when it is the schedule never having run.

    REFUSES AT STARTUP, because every one of these was a clamp at the old read site:
      * lr_restart_damp > 1.0 -- NOTHING catches it today and it INVERTS the mechanism: the damping
        multiplies the restart amplitude CUMULATIVELY, so above 1.0 it AMPLIFIES every failed
        restart -- the ratchet the lever exists to stop, driven by the lever that stops it. The old
        `min(1.0, max(0.0, ...))` at :4739 was the only thing standing there.
      * lr_restart_damp < 0.0; lr <= 0; weight_decay < 0; lr_min_frac outside [0.0, 1.0);
        lr_decay outside [0.0, 1.0]; lr_warmup < 0; lr_wavelength < 0.
      * accum < 1 -- LOUDLY. derive.accum_due does `k = max(1, int(accum))` and clamps in SILENCE,
        which is where a typo hides; batch_windows < 1 already raises UnitError in
        derive.flush_period_windows, and this one must not be quieter than that one.
      * batch_windows < 1, for the same reason and because build() divides by it.
      * grad_clip < 0.0. Zero is OFF and is the shipped default; a negative max-norm is a typo that
        would clip every step to nothing.

    IT ALSO RECORDS param_group_shape ON THE OptState, because load_state refuses against it and
    state_dict has to be able to write it. The shape is whatever P4 makes it -- the group order and
    each group's tensor count and shapes -- but it must be computed HERE, from the live groups,
    since that is the only moment the "live" side of load_state's comparison exists.

    NOTHING HANDED OVER IS DROPPED, AND THE EMPTY GROUP IS COUNTED RATHER THAN REFUSED. Both
    optimizers are constructed over an explicit param-group dict, so a group that arrives EMPTY
    still exists and still gets the rate written into it; docs/04_CONTRACT.md warns that a group
    left out means "the fabric contributes zero parameters to the optimizer" while the loss curve
    looks fine, which silently disables goal B's entire mechanism. opt.build.params.base and
    opt.build.params.encoder are the two numbers that make that visible, and a key in param_groups
    that is neither "base" nor "encoder" IS refused, because dropping it is the same defect
    arriving through a spelling.

    RECEIVES: run_windows <- RUN/DATA, resolved once after the stream and the tokenizer exist. It
    CANNOT be a build-time Coupling: the stream length in windows depends on the tokenization,
    which has not happened when build() freezes -- the same rejection assemble.NOT_WIRES gives the
    SIG width, and a DIFFERENT one from the RUN.epochs -> d_lr_horizon rejection. Both grounds are
    now rows in that table rather than prose here and in the contract (Q-OPT-1, RESOLVED).

    LEVERS READ: lr, weight_decay, lr_warmup, lr_wavelength, lr_restarts, lr_restart_damp,
                 lr_decay, lr_min_frac, lr_sched, accum, batch_windows, grad_clip
    WIRES READ: d_effective_batch_windows
    DID IT FIRE: opt.build.calls (exactly 1), opt.build.wavelength_from_sentinel,
                 opt.build.warmup_clamped (with both numbers), opt.build.cycles_fitted (n_cycles --
                 "armed" for a restart means > 1, NOT lr_restarts == 1),
                 Gate opt.build.grad_clip -- "off (0.0)" or the resolved max-norm, printed either
                 way, because "no clipping" is a run-level fact the report must state rather than
                 leave to be inferred from a missing line
    """
    opt = opt.owned_by("OPT")
    effective = opt.d_effective_batch_windows    # WIRE READ HERE -- the horizon's divisor

    # -- the startup refusals, in one place, because every one was a clamp at the old read site --
    lr = float(opt.lr)
    weight_decay = float(opt.weight_decay)
    grad_clip = float(opt.grad_clip)
    damp = float(opt.lr_restart_damp)
    decay = float(opt.lr_decay)
    min_frac = float(opt.lr_min_frac)
    warmup_asked = int(opt.lr_warmup)
    wavelength_asked = int(opt.lr_wavelength)
    n_accum = int(opt.accum)
    n_batch_windows = int(opt.batch_windows)

    if damp > 1.0:
        raise ValueError(
            f"OPT_LR_RESTART_DAMP={damp!r} is above 1.0, which INVERTS the mechanism. The damping "
            f"multiplies the restart amplitude CUMULATIVELY, so a value above 1.0 AMPLIFIES every "
            f"failed restart instead of shrinking it -- the ratchet this lever exists to stop, "
            f"driven by the lever that stops it. The old `min(1.0, max(0.0, ...))` at :4739 was "
            f"the only thing standing there and a Lever has no range facility.")
    if damp < 0.0:
        raise ValueError(f"OPT_LR_RESTART_DAMP={damp!r} is negative; a negative multiplier flips "
                         f"the sign of the restart swing.")
    if lr <= 0.0:
        raise ValueError(f"OPT_LR={lr!r} must be positive: every rate this system applies is this "
                         f"number times a multiplier in 0..1.")
    if weight_decay < 0.0:
        raise ValueError(f"OPT_WEIGHT_DECAY={weight_decay!r} is negative, which GROWS every "
                         f"parameter every step regardless of gradient.")
    if not 0.0 <= min_frac < 1.0:
        raise ValueError(f"OPT_LR_MIN_FRAC={min_frac!r} is outside [0.0, 1.0). It is a fraction of "
                         f"peak and 1.0 would make the cosine a constant.")
    if not 0.0 <= decay <= 1.0:
        raise ValueError(f"OPT_LR_DECAY={decay!r} is outside [0.0, 1.0]. 0.0 restores the "
                         f"pre-2026-08-26 behaviour (restarts return to full peak) and 1.0 is the "
                         f"full envelope; the values between are meaningful and the ones outside "
                         f"are not.")
    if warmup_asked < 0:
        raise ValueError(f"OPT_LR_WARMUP={warmup_asked!r} is negative; a warmup is a length.")
    if wavelength_asked < 0:
        raise ValueError(
            f"OPT_LR_WAVELENGTH={wavelength_asked!r} is negative. 0 is the sentinel for 'one "
            f"wavelength spans the whole run' and anything above it is a period in optimizer "
            f"steps; a negative is not falsy, so it would take the sentinel's branch nowhere.")
    if n_accum < 1:
        raise ValueError(
            f"OPT_ACCUM={n_accum!r} is below 1. derive.accum_due clamps it to 1 in SILENCE "
            f"(`k = max(1, int(accum))`), which is where a typo hides -- and batch_windows < 1 "
            f"already raises UnitError in derive.flush_period_windows, so this one must not be "
            f"quieter than that one.")
    if n_batch_windows < 1:
        raise ValueError(
            f"OPT_BATCH_WINDOWS={n_batch_windows!r} is below 1: a flush covers at least one "
            f"window, and the effective batch this package divides the horizon by is "
            f"batch_windows x accum.")
    if grad_clip < 0.0:
        raise ValueError(
            f"OPT_GRAD_CLIP={grad_clip!r} is negative. 0.0 is OFF and is the shipped default; a "
            f"negative max-norm is a typo that would clip every step to nothing.")

    # -- the groups, in a declared order, with nothing dropped ------------------------------------
    groups = dict(param_groups)
    unknown = sorted(k for k in groups if k not in ("base", "encoder"))
    if unknown:
        raise ValueError(
            f"OPT.build: param_groups carries {unknown!r}, which are neither 'base' nor 'encoder'. "
            f"Those two keys ARE the OptState field names (Q-OPT-7) and this function has nowhere "
            f"to put a third -- accepting it would drop the tensors on the floor, which is exactly "
            f"the shape docs/04_CONTRACT.md warns about when it says a group left out means the "
            f"package 'contributes zero parameters to the optimizer' while the loss curve looks "
            f"fine.")
    ordered = (("base", list(groups.get("base", ()))), ("encoder", list(groups.get("encoder", ()))))

    # ONE AdamW PER GROUP, BUILT OVER AN EXPLICIT PARAM-GROUP DICT. torch refuses a bare empty list
    # ("optimizer got an empty parameter list"), so a package that contributed nothing would take
    # the whole run down at construction; built this way the empty group EXISTS, gets the rate
    # written into it every step, and is COUNTED below, which is the distinction between "zero
    # parameters" measured and "zero parameters" invisible.
    base_opt = torch.optim.AdamW([{"params": ordered[0][1]}], lr=lr, weight_decay=weight_decay)
    enc_opt = torch.optim.AdamW([{"params": ordered[1][1]}], lr=lr, weight_decay=weight_decay)

    # -- the horizon, in optimizer steps, through the NAMED conversion ----------------------------
    # derive.opt_steps_from_windows refuses a non-Windows at one end and a divisor below 1 at the
    # other. The inline `run_windows // d_effective_batch_windows` this replaces was the last
    # unnamed cross-kind conversion in the tree.
    run_steps = derive.opt_steps_from_windows(run_windows, effective)
    total_steps = int(run_steps)

    from_sentinel = not wavelength_asked
    wavelength = run_steps if from_sentinel else U.Steps(wavelength_asked)

    # A TENTH OF THE HORIZON, IN THE HORIZON'S OWN KIND. This is a Steps -> Steps scaling and not a
    # conversion: no kind boundary is crossed, which is why it is written here rather than named in
    # spine.derive alongside opt_steps_from_windows.
    warmup_cap = max(1, total_steps // 10)
    warmup_n = min(warmup_asked, warmup_cap)
    warmup = U.Steps(warmup_n)

    if bool(opt.lr_restarts):
        n_cycles = max(1, round((total_steps - warmup_n)
                                / max(1, int(wavelength) - warmup_n)))
    else:
        n_cycles = 1

    horizon = Horizon(run_steps=run_steps, warmup=warmup, wavelength=wavelength,
                      n_cycles=int(n_cycles))

    shape = _param_group_shape(ordered)
    overlap = len({id(t) for t in ordered[0][1]} & {id(t) for t in ordered[1][1]})

    counters = {
        "opt.build.calls": 1,
        "opt.build.wavelength_from_sentinel": 1 if from_sentinel else 0,
        "opt.build.wavelength": int(wavelength),
        "opt.build.warmup_clamped": 1 if warmup_asked > warmup_cap else 0,
        "opt.build.warmup_asked": warmup_asked,
        "opt.build.warmup": warmup_n,
        "opt.build.run_steps": total_steps,
        "opt.build.cycles_fitted": int(n_cycles),
        "opt.build.params.base": len(ordered[0][1]),
        "opt.build.params.encoder": len(ordered[1][1]),
        "opt.build.group_overlap": overlap,
        "opt.backward": 0,
        "opt.step": 0,
        "opt.step.not_due": 0,
        "opt.restart.detected": 0,
        "opt.restart.damped": 0,
        "opt.restart.damp_refused_n1": 0,
        "opt.restart.readings": 0,
        "opt.lr.writes.base": 0,
        "opt.lr.writes.encoder": 0,
        "opt.lr.in_warmup": 0,
        "opt.lr.damped_this_step": 0,
        "opt.lr.shift_warm_applied": 0,
        "opt.lr.envelope_applied": 0,
        "opt.encoder_steps_here": 0,
        "opt.clip.applied": 0,
        "opt.clip.armed_no_clip": 0,
        "opt.shift.notifications": 0,
        "opt.ckpt.saved": 0,
        "opt.ckpt.loaded": 0,
        "opt.ckpt.refused": 0,
        "opt.ckpt.horizon_changed": 0,
    }

    return OptState(
        base=base_opt, encoder=enc_opt,
        n_backward=U.Backwards(0), opt_step=U.Steps(0),
        lr_prev=0.0, restart_amp=1.0, cycle_best=None, cycle_index=0,
        horizon=horizon, param_group_shape=shape, counters=counters,
        shift_at=None, grad_norms=[])


def lr_at(opt: Config, st, opt_step):
    """The rate at optimizer step `opt_step`. PURE: no closure reads, no globals, no measurement.

    lr_sched == "none" returns opt.lr flat. Otherwise linear warmup to peak over st.horizon.warmup,
    PAID ONCE and not per cycle -- the point of warmup is that the optimizer state is COLD, which
    is only true the first time (:4762-4765) -- then a cosine from peak to lr_min_frac. Under
    lr_restarts the cosine wraps into a WHOLE NUMBER of cycles fitted to the run, so every cycle
    completes and the run always ENDS annealed; truncating instead left a 30-epoch run with 2
    cycles and a THIRD of its length parked at the floor. At exactly one fitted cycle the schedule
    is bit-identical to lr_restarts=off (:4785), which keeps every earlier result reproducible.

    Three modifiers, each gated, each in this ONE function:
      * restart damping, `st.cycle_index > 0 and st.restart_amp < 1.0`: damps the SWING above the
        floor, never below it.
      * self-inflicted-shift re-warm, `opt.lr_shift_warm and 0 <= opt_step - st.shift_at <
        opt.lr_shift_warm`: an ATTENUATION (a multiply), never a replacement. Returning `lr * ramp`
        would RAISE the rate whenever a shift lands late in the anneal.
      * the monotone envelope, GATED ON n_cycles > 1: without that gate it multiplied a single
        cycle's cosine by a second cosine that also bottoms at the floor, so a run that should end
        at lr_min_frac ended at lr_min_frac SQUARED -- 0.0025 of peak. That is why LR_DECAY sat at
        0.0 from the day it was written, and three documents still say it is inert after the
        default flipped 0.0 -> 1.0.

    THE PROPERTY THE TEST MUST ASSERT, which the compounding defect above makes non-obvious: the
    schedule's minimum over a whole run equals lr * lr_min_frac at EVERY restart count,
    single-cycle included.

    P4 NOTE, 2026-09-03, ON WHAT MAKES THAT PROPERTY TRUE RATHER THAN NEARLY TRUE. The `n_cycles > 1`
    gate removes the compounding from the single-cycle case and NOT from the multi-cycle one: at
    n_cycles = 3 with the shipped lr_decay = 1.0 the last cycle's cosine bottoms at lr_min_frac and
    the envelope bottoms at lr_min_frac on the same step, so their product is lr_min_frac SQUARED.
    The rate is therefore clamped at lr * lr_min_frac as the last act of the schedule, which leaves
    every arm that already satisfied the property bit-identical and makes the two that did not --
    the envelope past its last peak, and a shift re-warm landing mid-anneal -- satisfy it too.
    `st.cycle_index` is maintained by maybe_step and equals the cycle index of the step being
    priced whenever this is called from there; the damping gate reads the index OF THE STEP IT IS
    PRICING, so a probe at an arbitrary step gets that step's answer rather than the last one taken.

    LEVERS READ: lr, lr_sched, lr_min_frac, lr_restarts, lr_restart_damp, lr_decay, lr_shift_warm,
                 lr_warmup, lr_wavelength (the last two through st.horizon)
    WIRES READ: none
    DID IT FIRE: opt.lr.in_warmup, opt.lr.damped_this_step, opt.lr.shift_warm_applied,
                 opt.lr.envelope_applied (the n_cycles > 1 gate, the old _nenv)
    """
    opt = opt.owned_by("OPT")
    if type(opt_step) is not U.Steps:
        raise U.UnitError(
            f"OPT.lr_at: opt_step must be units.Steps, got {type(opt_step).__name__}. The LR "
            f"horizon is denominated in optimizer steps and nothing else; the window counter they "
            f"coincide with at batch_windows=1, accum=1 is the confusion Q-OPT-2 exists to refuse, "
            f"and at WIN=256 BATCH_W=16 ACCUM=4 the two differ by 64x.")

    # THE SHIFT LENGTH IS BOUND TO A LOCAL BEFORE IT IS DIVIDED BY, and the reason is worth one
    # line: lr_shift_warm declares units.Steps, and the ramp below is a Steps/Steps RATIO -- a
    # dimensionless attenuation, not a cross-kind conversion. The named-conversion rule
    # (units.py::Clock.convert, tests/test_ownership.py::check_o11_no_unnamed_clock_arithmetic) is
    # about crossing kinds; there is no kind to cross here and no spine.derive function could name
    # this one without inventing a kind for "fraction of a re-warm".
    shift_warm = int(opt.lr_shift_warm)

    rate, flags = _schedule(
        lr=float(opt.lr), sched=str(opt.lr_sched), min_frac=float(opt.lr_min_frac),
        restarts=bool(opt.lr_restarts), decay=float(opt.lr_decay), shift_warm=shift_warm,
        restart_amp=float(st.restart_amp), shift_at=st.shift_at,
        horizon=st.horizon, step=int(opt_step))

    # THE ONLY WRITES THIS FUNCTION MAKES, and they do not reach the return value: the four gate
    # observations its own DID IT FIRE line names. The old tree wrote _nenv from inside _lr_at for
    # the same reason -- the gate is only observable where it is evaluated.
    in_warmup, damped, warmed, enveloped = flags
    if in_warmup:
        st.counters["opt.lr.in_warmup"] += 1
    if damped:
        st.counters["opt.lr.damped_this_step"] += 1
    if warmed:
        st.counters["opt.lr.shift_warm_applied"] += 1
    if enveloped:
        st.counters["opt.lr.envelope_applied"] += 1
    return rate


def scaled_backward(opt: Config, st, total):
    """Scale the composed loss by accum, call .backward() on it, advance the Backwards clock, and
    return that clock. THE SCALING AND THE COUNTING ARE THE SAME FUNCTION, ON PURPOSE.

    `(total / accum).backward()` is not optional and not separable from the gate: an accumulation
    that gates the step WITHOUT scaling the loss trains at ACCUM times the rate the operator asked
    for, which is the same defect class as the gate itself and would be invisible in exactly the
    same way. In the old tree the scaling was at :7065 and the gate at :7193, 128 lines apart.

    st.n_backward is units.Backwards, never a bare int, so it cannot be handed to a Windows
    comparison and a Windows counter cannot be handed to accum_due.

    LEVERS READ: accum
    WIRES READ: none
    DID IT FIRE: opt.backward (the Backwards count -- the DENOMINATOR of the effective batch, and
                 the number the report must print instead of the configured one)
    """
    opt = opt.owned_by("OPT")
    divisor = max(1, int(opt.accum))
    (total / divisor).backward()
    st.n_backward = st.n_backward + U.Backwards(1)
    st.counters["opt.backward"] = int(st.n_backward)
    return st.n_backward


def maybe_step(opt: Config, st, *, best_bpb=None, shift_at=None):
    """Take an optimizer step if one is due. Returns StepOutcome(stepped, lr, restart, damped).

    Due-ness is derive.accum_due(st.n_backward, opt.accum), which REQUIRES a Backwards clock and
    refuses Windows(55) and bare 55. The measurement this repairs: the old gate was
    `(step + 1) % ACCUM == 0` keyed on the WINDOW counter while the body ran per flush, so it
    accumulated NOTHING at any value -- 55 om.step() calls against 13 due, over ~52 backward passes
    at BATCH_W=4 ACCUM=4 (ISSUES P3-H29). Every learning-rate result taken against that configuration
    is filed under a batch size it was not taken at.

    When due, IN THIS ORDER:
      1. advance st.opt_step (units.Steps) -- the schedule's counter, and the ONLY thing that
         advances it;
      2. lr = lr_at(opt, st, st.opt_step);
      3. the restart detector: `st.lr_prev > 0 and lr > 1.5 * st.lr_prev and lr > 0.5 * opt.lr`.
         The second condition is not decoration -- the warmup ramp climbs from zero, so every early
         step multiplies the previous rate by far more than 1.5 and each one was logged as a
         "cosine restart" (observed at steps 15 and 31 of an 18-epoch run, at 2% and 3% of peak).
         The FIRST condition is why lr_prev is checkpointed: on a resume the old `_lr_prev` came
         back at 0.0 while `st` came back past warmup, so every resume reported a cosine restart on
         its second step ("x1145648405" -- the tell that it is lr divided by a 1e-12 floor), which
         told the growth controller the loss jump was self-inflicted ON EXACTLY THE STEP A NEW AREA
         ARRIVES;
      4. the closed loop: if a restart fired and the cycle that just ended did not beat the best
         held-out it inherited, st.restart_amp *= opt.lr_restart_damp, cumulatively. best_bpb is
         THE HELD-OUT MEASUREMENT CROSSING BACK INTO A TRAINING DECISION -- the only one in the
         system. PLAN 3.8 forbids a verdict on n=1 and a damped restart IS a verdict, so the
         Reading it comes from must carry its seed count; OPT REFUSES TO DAMP on a seed count of 1
         and records that refusal as a counter rather than damping quietly. The failure it answers
         is measured: best 2.030 @ 252,000, restarts at 263,965 / 504,894 / 756,851, final 2.848 --
         81% of the run spent getting worse, the same losing bet re-taken three times at full
         amplitude;
      5. write `lr` into EVERY param group of BOTH optimizers -- st.base and st.encoder -- then
         READ THE GRADIENT NORM, CLIP IF ASKED, and step and zero_grad THE BASE OPTIMIZER ONLY.
         Writing the rate UNCONDITIONALLY is what kills ISSUES P1-H15: `_lrv` is assigned only inside
         `if LR_SCHED != "none"` (:7094) and read unconditionally by the per-expert path (:7195),
         so LR_SCHED="none" with FAB_LR_OWN=1 dies with a NameError on the FIRST flush. Here the
         rate always exists and always leaves this package AS A RETURN VALUE, never as a local
         another package reads.

         THE ENCODER IS NOT STEPPED HERE, AND THAT IS Q-OPT-6 RESOLVED (a), 2026-09-02. This clause
         said "step and zero_grad both" and it described something that never happened: in 9,859
         lines of self_organize.py the encoder optimizer `oe` appears exactly twice -- :5372
         (state_dict into the checkpoint) and :7154 (`for _g in oe.param_groups: _g["lr"] = _lrv`).
         There is no oe.step() and no oe.zero_grad() anywhere; :7287 is `om.step(); om.zero_grad()`,
         the base optimizer alone. The encoder was stepped only inside contrastive_step (:3401),
         which is SIG's mechanism on SIG's cadence. Stepping it from here as well would step it
         twice -- once by SIG.train_step on its Windows cadence and again by this flush gate -- and
         would destroy three declared mechanisms: SIG's floor gate returns BEFORE touching the
         optimizer when the InfoNCE loss is at the floor (:3399-3401; sig/api.py restates it as
         "the step is SKIPPED, opt untouched"), so a step taken here gates nothing; and
         sig.train_every, sig.train_every_idle and sig.dense_window -- plus the SIG.d_idle_cadence
         wire computed from two of them -- would become armed-but-inert BY CONSTRUCTION, because a
         package's cadence lever is only meaningful if that package's mechanism fires on it.
         The lr WRITE still reaches both, so the encoder runs at the schedule's rate; only the
         step and the zero_grad are the base optimizer's.

         THE GRADIENT NORM IS TAKEN HERE BECAUSE IT CANNOT BE TAKEN ANYWHERE ELSE (Q-OPT-3). A
         global grad norm can only be read while gradients EXIST -- after backward, before the
         zero_grad on this line. OPT.counters used to claim it computed the norm; by the time
         counters runs the grads are zero, so a P4 author following that docstring would have
         reported 0.0 for the whole run with every check green. counters RENDERS the accumulated
         quantiles; this is where they are read. SCOPE: THE BASE GROUP ONLY. The encoder's grads at
         flush time belong to SIG's cadence and folding them into one number makes it
         uninterpretable.

         CLIPPING, WHEN opt.grad_clip > 0, HAPPENS ON THE SAME LINE AND IN THE SAME SCOPE: a global
         max-norm over the base group's parameters, applied AFTER the norm is recorded and BEFORE
         the step, so the reported p50/p99 are the norms the run actually produced rather than the
         clipped ones -- an instrument that measures its own remedy answers nothing. Clip-by-norm,
         never clip-by-value: it preserves gradient direction and rescales magnitude only.
         opt.grad_clip DEFAULTS TO 0.0 = OFF, so nothing in any recorded result moves; see Q-OPT-3
         in docs/04_CONTRACT.md for what measurement settles the default.

    RECEIVES: best_bpb <- EVAL, a Reading carrying (value, seed_count) or None; shift_at <- the
    composition root, the optimizer step of the last self-inflicted shift (epoch resample, retok,
    added area). Both are runtime arguments; the old code read `_shift_at` as a CLOSURE VARIABLE
    written by DATA's resample branch (:6518-6521), which is the L2 violation this replaces. Until
    shift_at is supplied, lr_shift_warm has nothing to fire on and its counter reads "armed but 0"
    -- which is a DIFFERENT statement from lr_shift_warm == 0, and the report must make both.

    LEVERS READ: accum, lr, lr_restart_damp, lr_sched (through lr_at), grad_clip, plus everything
                 lr_at reads
    WIRES READ: none
    DID IT FIRE: opt.step (BASE optimizer steps -- the encoder's are sig.train_stepped and live in
                 SIG), opt.step.not_due, opt.restart.detected, opt.restart.damped,
                 opt.restart.damp_refused_n1,
                 opt.restart.readings (ADDED BY P4, 2026-09-03: the mirror of
                 opt.shift.notifications on the other runtime argument. compose.py's LOOP_ORDER row
                 states that best_bpb HAS NO PRODUCER, so opt.restart.damped and
                 opt.restart.damp_refused_n1 are "UNREACHABLE, not zero" -- and with only those two
                 counters nothing at RUNTIME can tell a run where no Reading ever arrived from a
                 run where every Reading said the cycle paid. This is the count that makes that
                 declared UNREACHABLE checkable instead of asserted),
                 opt.lr.writes.base and opt.lr.writes.encoder (each must equal opt.step -- the
                 rate is written to both optimizers on every step; the old single counter said
                 "must equal opt.step, on BOTH optimizers" and could not distinguish a missing
                 encoder write from a missing step),
                 opt.encoder_steps_here (MUST BE 0 -- the regression counter for Q-OPT-6. A
                 nonzero value is the double-step returning, and without a counter it returns
                 silently because both call sites look correct in isolation),
                 opt.grad_norm.p50 / opt.grad_norm.p99 (base group, read before zero_grad;
                 rendered by counters),
                 opt.clip.applied / opt.clip.armed_no_clip (grad_clip > 0 and no step exceeded it
                 -- a DIFFERENT statement from grad_clip == 0, and the report must make both),
                 opt.shift.notifications (0 means nobody is supplying shift_at)
    """
    opt = opt.owned_by("OPT")

    # THE SHIFT IS STAMPED WHETHER OR NOT A STEP IS DUE. A self-inflicted shift lands on a WINDOW,
    # and the flush that notices it may not be a due one; recording it only on due flushes would
    # lose up to accum-1 of them and make lr_shift_warm's fire depend on the batch size.
    if shift_at is not None:
        st.shift_at = int(shift_at)
        st.counters["opt.shift.notifications"] += 1

    if not derive.accum_due(st.n_backward, opt.accum):
        st.counters["opt.step.not_due"] += 1
        # THE RATE THE OPTIMIZER IS CURRENTLY AT, not a fresh one: no step was taken, so nothing
        # rewrote the param groups, and returning a newly computed rate would tell FAB.own_lr_scale
        # a number the optimizer is not using.
        return StepOutcome(stepped=False, lr=float(st.lr_prev), restart=False, damped=False)

    # 1. the schedule's counter, and the ONLY thing that advances it.
    st.opt_step = st.opt_step + U.Steps(1)
    st.counters["opt.step"] = int(st.opt_step)

    # 2. the rate.
    lr = lr_at(opt, st, st.opt_step)
    # THE INDEX OF THE STEP JUST PRICED. _schedule computes the same number from the same horizon
    # and the same step, so st.cycle_index and the index the damping gate used are equal by
    # construction on this path; the field exists so state_dict can carry it and counters can print
    # it, not as a second source the schedule reads back.
    st.cycle_index = _cycle_index(st.horizon, int(st.opt_step), bool(opt.lr_restarts))

    # 3. the restart detector. BOTH conditions: the warmup ramp climbs from zero, so the ratio bar
    #    alone reported a restart at steps 15 and 31 of an 18-epoch run, at 2% and 3% of peak.
    peak = float(opt.lr)
    restart = bool(st.lr_prev > 0 and lr > 1.5 * st.lr_prev and lr > 0.5 * peak)
    damped = False
    if restart:
        st.counters["opt.restart.detected"] += 1
        # 4. the closed loop. A damped restart IS a verdict, so the Reading has to carry its seed
        #    count and a count below 2 is refused rather than damping quietly (PLAN 3.8).
        value, seeds = _reading(best_bpb)
        if value is not None:
            st.counters["opt.restart.readings"] += 1
        paid = st.cycle_best is None or (value is not None and value < st.cycle_best - 1e-6)
        if not paid and float(opt.lr_restart_damp) < 1.0:
            if seeds < 2:
                st.counters["opt.restart.damp_refused_n1"] += 1
            else:
                st.restart_amp *= float(opt.lr_restart_damp)
                st.counters["opt.restart.damped"] += 1
                damped = True
        st.cycle_best = value
    st.lr_prev = float(lr)

    # 5. the rate reaches BOTH optimizers; the step and the zero_grad are the BASE one's.
    for g in st.base.param_groups:
        g["lr"] = lr
    st.counters["opt.lr.writes.base"] += 1
    for g in st.encoder.param_groups:
        g["lr"] = lr
    st.counters["opt.lr.writes.encoder"] += 1

    base_params = _params_of(st.base)
    norm = _global_grad_norm(base_params)
    st.grad_norms.append(norm)

    clip = float(opt.grad_clip)
    if clip > 0.0:
        # AFTER the norm is recorded and BEFORE the step: an instrument that measures its own
        # remedy answers nothing. Clip-by-norm, never clip-by-value.
        if norm > clip:
            st.counters["opt.clip.applied"] += 1
            torch.nn.utils.clip_grad_norm_(base_params, clip)
        else:
            st.counters["opt.clip.armed_no_clip"] += 1

    st.base.step()
    st.base.zero_grad(set_to_none=True)
    # st.encoder IS NOT STEPPED HERE (Q-OPT-6). The counter stays 0 for the life of the run and a
    # nonzero value is the double step returning.
    return StepOutcome(stepped=True, lr=float(lr), restart=restart, damped=damped)


def counters(opt: Config, st):
    """The DID IT FIRE ledger, plus the one invariant that proves the accumulation defect is dead.

    ASSERTS AND REPORTS: `opt.backward // max(1, opt.accum) == opt.step`. The old tree could not
    make this statement because it counted the wrong thing; a run that violates it is running H29
    again under a new name. The report prints backward, step, accum, batch_windows and
    d_effective_batch_windows TOGETHER, so the batch size a run TRAINED at is a printed number
    rather than a configured one -- ACCUM appeared in no print anywhere in the old tree, while
    fetch_big.py names ACCUM=4 in its recommended heavy-run command and bench_gpu.sh ships ACCUM=2.

    Gates rendered with their own arithmetic (G4): lr_sched, lr_restarts (n_cycles > 1, NOT the
    flag), weight_decay > 0, lr_decay > 0 and n_cycles > 1, lr_shift_warm > 0 and a shift_at ever
    supplied. Two levers are reachable only by arithmetic and every result this project has
    recorded came from a single-cycle schedule, so neither lr_restart_damp nor lr_decay has ever
    fired in anger -- ISSUES.md PART 4's [chat-b/carry_forward] entry files exactly this pair as the canonical "off by arithmetic,
    not armed and inert" case.

    RENDERS -- DOES NOT COMPUTE -- the observed global gradient norm (opt.grad_norm.p50/p99, base
    group). THE DISTINCTION IS THE WHOLE OF Q-OPT-3'S FIRST HALF: this paragraph used to say it
    reported the norm "per optimizer step", but maybe_step step 5 does the zero_grad, so a norm
    read from here is a norm over freshly zeroed gradients -- 0.0 for the entire run, with every
    check in this repository green. The quantiles are accumulated in maybe_step, between the
    gradient's last use and the zero_grad, and this call prints them. A counter that answers "0"
    while meaning "unreachable" is the exact distinction DID IT FIRE exists to preserve.

    Beside them it prints the CLIP gate: opt.grad_clip, and opt.clip.applied against
    opt.clip.armed_no_clip. There is NO gradient clipping anywhere in self_organize.py (verified by
    exhaustive grep: two matches, both prose about the forgetting measure F), so 0.0 is the setting
    every recorded number was taken under; see FOR THE OWNER Q-OPT-3 for what measurement settles
    the default.

    AND IT PRINTS THE HORIZON AGAINST THE RUN THAT ACTUALLY HAPPENED (Q-OPT-5). st.horizon.run_steps
    was resolved ONCE at build() from epoch 0's measured length times RUN.epochs; minting merges
    bytes into tokens, so len(Segmentation.ids) FALLS and every later epoch is SHORTER, which means
    the observed total comes in BELOW the projection and the cosine does not complete -- the run
    ends at a rate above lr x lr_min_frac. That is the same direction as the E8 p=0.760
    under-annealing the once-resolved horizon was introduced to kill: the machinery changed and the
    sign of the residual did not. THE MAGNITUDE IS UNMEASURED and this line is what measures it.
    The comparison is between two units.Steps values and is therefore a subtraction, not a
    UnitError: derive.opt_steps_from_windows(Windows(observed_windows), d_effective_batch_windows)
    against st.horizon.run_steps, where the observed side is RunClock.counters()'s window total,
    joined here by the composition root because neither package may read the other. The residual is
    filed with its sign NAMED (under-anneal), not left as two numbers in two report sections.
    Re-projecting the horizon mid-run is NOT the repair and is refused: it is `_project`/`_lr_total`
    /`_proj_lr` (:6335-6376), which produced E8 p=0.760 and E18 p=0.730 and the H17 resume defect,
    and it would require writing into a horizon resolved from a frozen Config.

    ⚠ P4 COULD NOT BUILD THAT LAST PARAGRAPH AND SAYS SO RATHER THAN PRINTING A HALF OF IT AS THE
    WHOLE. The observed side has no route into this function. The signature is frozen at
    `counters(opt, st)`, spine/compose.py's stage-R row is `("R", "OPT", "counters", "(st) -- ...")`
    with no second argument, and nothing stamps a window total onto the OptState, so the join the
    paragraph describes -- "joined here by the composition root" -- has no parameter to arrive
    through. What this call renders is the PROJECTION alone, under `opt.horizon.run_steps`, plus
    `opt.horizon.steps_taken` (st.opt_step, which IS observed and IS in hand) and their difference
    in Steps. That difference is a WEAKER statement than Q-OPT-5 asks for: it measures the schedule
    against the steps the loop actually took, not against the windows the stream actually yielded,
    so it cannot separate "the horizon over-projected" from "the run stopped early". The residual
    Q-OPT-5 names needs either a third parameter on this signature or the observed window total on
    the OptState, and both are frozen surfaces this package may not move alone.

    RETURNS the ledger as {name: count | Gate}, with the rendered report under
    `opt.report_lines`. A Gate value carries its own arithmetic and prints itself through
    spine/gate.py::Gate.line, which is what keeps FIRED, armed-and-inert and UNREACHABLE three
    words rather than one number across thirteen packages.

    LEVERS READ: accum, batch_windows, lr_sched, lr_restarts, lr_decay, lr_shift_warm,
                 weight_decay, lr_restart_damp, grad_clip
    WIRES READ: d_effective_batch_windows
    DID IT FIRE: this call IS the DID IT FIRE surface for the package
    """
    opt = opt.owned_by("OPT")
    effective = opt.d_effective_batch_windows  # WIRE READ HERE -- printed beside opt.backward

    divisor = max(1, int(opt.accum))
    windows_per_flush = int(opt.batch_windows)
    n_bwd = int(st.n_backward)
    n_step = int(st.opt_step)
    due_steps = n_bwd // divisor
    if due_steps != n_step:
        raise ValueError(
            f"OPT.counters: the accumulation invariant is broken -- backward={n_bwd}, "
            f"accum={divisor}, so {due_steps} optimizer steps were due and {n_step} were taken. "
            f"The old tree could not even make this statement because it counted the wrong thing: "
            f"the gate was `(step + 1) % ACCUM == 0` on the WINDOW counter while the body ran per "
            f"flush, which produced 55 om.step() calls against 13 due at BATCH_W=4 ACCUM=4 "
            f"(ISSUES P3-H29). A run that violates this is running H29 again under a new name.")

    sched = str(opt.lr_sched)
    n_cycles = int(st.horizon.n_cycles)
    decay = float(opt.lr_decay)
    damp = float(opt.lr_restart_damp)
    shift_warm = int(opt.lr_shift_warm)
    wd = float(opt.weight_decay)
    clip = float(opt.grad_clip)
    restarts_on = bool(opt.lr_restarts)
    notifications = int(st.counters["opt.shift.notifications"])
    readings = int(st.counters["opt.restart.readings"])

    norms = sorted(st.grad_norms)
    p50, p99 = _quantile(norms, 0.50), _quantile(norms, 0.99)

    ledger = dict(st.counters)
    ledger["opt.accum"] = divisor
    ledger["opt.batch_windows"] = windows_per_flush
    ledger["opt.d_effective_batch_windows"] = int(effective)
    ledger["opt.grad_norm.p50"] = p50
    ledger["opt.grad_norm.p99"] = p99
    ledger["opt.grad_norm.samples"] = len(norms)
    ledger["opt.horizon.run_steps"] = int(st.horizon.run_steps)
    ledger["opt.horizon.steps_taken"] = n_step
    ledger["opt.horizon.residual_steps"] = int(st.horizon.run_steps - st.opt_step)
    ledger["opt.restart_amp"] = float(st.restart_amp)

    gates = [
        Gate("opt.accum.invariant", True, f"{n_bwd} backward // {divisor}", n_step,
             reason="backward // accum == step -- the one statement that proves ISSUES P3-H29 dead"),
        Gate("opt.lr.sched", sched != "none", sched, "cosine",
             reachable=True,
             reason=("OPT_LR_SCHED=none: warmup, wavelength, floor, restarts, damping, envelope "
                     "and re-warm are ALL structurally unreachable, which is what makes this an "
                     "ablation rather than an arm")
             if sched == "none" else ""),
        Gate("opt.build.grad_clip", clip > 0.0, clip if clip > 0.0 else "off (0.0)", "> 0.0",
             reachable=clip > 0.0,
             reason="" if clip > 0.0 else
                    "OPT_GRAD_CLIP=0.0 is OFF, which is the setting every recorded number in this "
                    "project was taken under (Q-OPT-3). 'No clipping' is a run-level fact the "
                    "report states rather than leaving to be inferred from a missing line."),
    ]

    if clip > 0.0:
        gates.append(Gate("opt.clip.applied", st.counters["opt.clip.applied"] > 0,
                          st.counters["opt.clip.applied"], f"max-norm {clip}",
                          reason=("armed and NOTHING exceeded the norm -- a different statement "
                                  "from grad_clip == 0")
                          if not st.counters["opt.clip.applied"] else ""))
    else:
        gates.append(Gate("opt.clip.applied", False, 0, "n/a", reachable=False,
                          reason=f"OPT_GRAD_CLIP={clip} is OFF, so no step can clip. This is not "
                                 f"'armed and did not fire'."))

    # THE RESTART GATE IS ARITHMETIC AND NOT THE FLAG. `_ncyc = [1]  # "armed" for a restart means
    # >1, not LR_RESTARTS=1` (:4746). Every result this project has recorded came from a
    # single-cycle schedule, which is why the two levers below it have never fired in anger.
    if not restarts_on:
        gates.append(Gate("opt.lr.restarts", False, n_cycles, "> 1 cycle", reachable=False,
                          reason="OPT_LR_RESTARTS=off, so the cosine holds at the floor after one "
                                 "cycle and no restart exists to detect."))
    elif n_cycles <= 1:
        why = ("the 0 sentinel makes one wavelength span the whole run"
               if not int(opt.lr_wavelength) else "the period does not divide the run twice")
        gates.append(Gate("opt.lr.restarts", False, n_cycles, "> 1 cycle", reachable=False,
                          reason=f"OPT_LR_RESTARTS is on and exactly ONE cycle fits: "
                                 f"OPT_LR_WAVELENGTH={int(opt.lr_wavelength)} against a horizon of "
                                 f"{int(st.horizon.run_steps)} steps ({why}), so the schedule is "
                                 f"bit-identical to restarts=off and no restart can occur."))
    else:
        gates.append(Gate("opt.lr.restarts", st.counters["opt.restart.detected"] > 0,
                          st.counters["opt.restart.detected"], f"{n_cycles} cycles fitted"))

    if n_cycles <= 1:
        gates.append(Gate("opt.lr.restart_damp", False, damp, "< 1.0 past cycle 0", reachable=False,
                          reason=f"the damping is gated on cycle_index > 0 and only "
                                 f"{n_cycles} cycle(s) fit this run, so OPT_LR_RESTART_DAMP={damp} "
                                 f"is off BY ARITHMETIC rather than armed and inert."))
    elif readings == 0:
        gates.append(Gate("opt.lr.restart_damp", False, damp, "< 1.0 on a losing cycle",
                          reachable=False,
                          reason="no Reading has ever arrived (opt.restart.readings == 0), so the "
                                 "held-out measurement the damping judges a cycle by does not "
                                 "exist. A damped restart is a verdict and PLAN 3.8 forbids one on "
                                 "n<2; with no Reading at all there is nothing to refuse."))
    else:
        gates.append(Gate("opt.lr.restart_damp", st.counters["opt.restart.damped"] > 0,
                          st.counters["opt.restart.damped"],
                          f"damp={damp}, refused_n1={st.counters['opt.restart.damp_refused_n1']}"))

    if decay <= 0.0:
        gates.append(Gate("opt.lr.decay", False, decay, "> 0.0", reachable=False,
                          reason="OPT_LR_DECAY=0.0 restores the pre-2026-08-26 behaviour exactly: "
                                 "restarts return to full peak and no envelope is applied."))
    elif n_cycles <= 1:
        gates.append(Gate("opt.lr.decay", False, decay, "> 0.0 and n_cycles > 1", reachable=False,
                          reason=f"the envelope is gated on n_cycles > 1 and {n_cycles} cycle(s) "
                                 f"fit, so OPT_LR_DECAY={decay} is off BY ARITHMETIC. Without that "
                                 f"gate it squeezed a single cycle to lr_min_frac SQUARED."))
    else:
        gates.append(Gate("opt.lr.decay", st.counters["opt.lr.envelope_applied"] > 0,
                          st.counters["opt.lr.envelope_applied"], f"decay={decay}"))

    if shift_warm <= 0:
        gates.append(Gate("opt.lr.shift_warm", False, shift_warm, "> 0", reachable=False,
                          reason="OPT_LR_SHIFT_WARM=0, the shipped default and the setting every "
                                 "recorded result was produced under."))
    elif notifications == 0:
        gates.append(Gate("opt.lr.shift_warm", False, notifications, "a shift_at ever supplied",
                          reachable=False,
                          reason=f"OPT_LR_SHIFT_WARM={shift_warm} is armed and NOBODY IS SUPPLYING "
                                 f"shift_at (opt.shift.notifications == 0), which is a DIFFERENT "
                                 f"statement from lr_shift_warm == 0 and the report must make "
                                 f"both."))
    else:
        gates.append(Gate("opt.lr.shift_warm", st.counters["opt.lr.shift_warm_applied"] > 0,
                          st.counters["opt.lr.shift_warm_applied"],
                          f"{notifications} notification(s) x {shift_warm} steps"))

    gates.append(Gate("opt.weight_decay", wd > 0.0, wd, "> 0.0",
                      reachable=wd > 0.0,
                      reason="" if wd > 0.0 else
                             "OPT_WEIGHT_DECAY=0.0. AdamW's own default is 0.01, so before this "
                             "lever existed the run WAS decaying dormant experts and nobody had "
                             "chosen it; a dormant expert loses ~71% of its magnitude over a "
                             "62.5k-step run."))

    gates.append(Gate("opt.encoder_steps_here", st.counters["opt.encoder_steps_here"] > 0,
                      st.counters["opt.encoder_steps_here"], 0,
                      reason="Q-OPT-6 REGRESSION COUNTER, READ BACKWARDS: this MUST be 0, so "
                             "'armed, did not fire' IS the passing state and FIRED is the defect. "
                             "A nonzero value is the double step returning -- SIG.train_step on "
                             "SIG's cadence and this flush gate both stepping the encoder, which "
                             "makes SIG's InfoNCE floor and its three cadence levers inert by "
                             "construction, and it returns silently because both call sites look "
                             "correct in isolation."))

    if not st.grad_norms:
        gates.append(Gate("opt.grad_norm", False, None, "any optimizer step", reachable=False,
                          reason="no optimizer step has been taken, so no gradient has ever been "
                                 "measured. This is 'never reached', not 'measured 0.0' -- the "
                                 "distinction Q-OPT-3's first half is entirely about."))
    else:
        gates.append(Gate("opt.grad_norm", True, f"p50={p50:.4g} p99={p99:.4g}",
                          f"{len(norms)} step(s)",
                          reason="read in maybe_step between the gradient's last use and the "
                                 "zero_grad; rendered here, never computed here"))

    lines = [
        f"opt.backward={n_bwd}  opt.step={n_step}  accum={divisor}  "
        f"batch_windows={windows_per_flush}  d_effective_batch_windows={int(effective)}  "
        f"-- the batch this run TRAINED at, printed rather than configured",
        f"opt.lr.writes.base={st.counters['opt.lr.writes.base']}  "
        f"opt.lr.writes.encoder={st.counters['opt.lr.writes.encoder']}  "
        f"(each must equal opt.step={n_step})",
        f"opt.horizon: run_steps={int(st.horizon.run_steps)} (projected once at build, from "
        f"run_windows) vs steps_taken={n_step}; residual="
        f"{int(st.horizon.run_steps - st.opt_step)} steps. Q-OPT-5's residual is against the "
        f"OBSERVED WINDOW TOTAL and this signature has no parameter for it -- see this function's "
        f"docstring.",
        f"opt.horizon: warmup={int(st.horizon.warmup)} (asked "
        f"{st.counters['opt.build.warmup_asked']}, clamped="
        f"{bool(st.counters['opt.build.warmup_clamped'])})  "
        f"wavelength={int(st.horizon.wavelength)} (from the 0 sentinel="
        f"{bool(st.counters['opt.build.wavelength_from_sentinel'])})  cycles_fitted={n_cycles}",
        f"opt.params: base={st.counters['opt.build.params.base']} tensor(s), "
        f"encoder={st.counters['opt.build.params.encoder']} tensor(s), "
        f"overlap={st.counters['opt.build.group_overlap']}",
    ]
    lines.extend(g.line() for g in gates)

    for g in gates:
        ledger[g.name] = g
    ledger["opt.report_lines"] = tuple(lines)
    return ledger


def state_dict(opt: Config, st):
    """Both optimizers' state, plus everything the closed loop needs to survive a run boundary:
    opt_step, n_backward, lr_prev, restart_amp, cycle_best, cycle_index, the resolved horizon,
    param_group_shape, and the counters.

    param_group_shape WAS MISSING FROM THIS ENUMERATION UNTIL 2026-09-02 (Q-OPT-4) AND load_state
    REFUSES ON IT. A refusal armed against a value nothing writes is untrippable: the L50 guard --
    the one thing that stops AdamW moments being reattached positionally to different tensors after
    the population grew -- would have passed every resume by finding no shape to disagree with.
    It is written here and computed in build(), from the live groups.

    The old checkpoint saved opt_m and opt_e (:5372) and NOTHING ELSE from this package, so
    _rst_amp, _cyc_best, _nrst, _ndamp, _ncyc and _lr_prev all reset on every resume: a schedule
    that had damped itself twice came back at FULL AMPLITUDE, and the DID IT FIRE counters
    restarted at zero so a mechanism that fired 4,000 times read "armed but 0". A continual-learning
    system whose LR controller forgets across the run boundary is answering the wrong goal.

    shift_at AND grad_norms TRAVEL TOO (P4, 2026-09-03), on the identical argument. A re-warm that
    spans a checkpoint comes back with nothing to re-warm from, so the boundary itself cancels the
    lever whose whole job is boundaries; and a norm distribution that restarts empty makes
    opt.grad_norm.p50/p99 describe the tail of a run rather than the run, which is the same
    "mechanism that fired 4,000 times read 'armed but 0'" defect one field over.

    LEVERS READ: none (everything comes off st)
    WIRES READ: none
    DID IT FIRE: opt.ckpt.saved
    """
    opt = opt.owned_by("OPT")
    st.counters["opt.ckpt.saved"] += 1
    return {
        "base": st.base.state_dict(),
        "encoder": st.encoder.state_dict(),
        "opt_step": int(st.opt_step),
        "n_backward": int(st.n_backward),
        "lr_prev": float(st.lr_prev),
        "restart_amp": float(st.restart_amp),
        "cycle_best": st.cycle_best,
        "cycle_index": int(st.cycle_index),
        "shift_at": st.shift_at,
        "horizon": {"run_steps": int(st.horizon.run_steps),
                    "warmup": int(st.horizon.warmup),
                    "wavelength": int(st.horizon.wavelength),
                    "n_cycles": int(st.horizon.n_cycles)},
        "param_group_shape": st.param_group_shape,
        "counters": dict(st.counters),
        "grad_norms": list(st.grad_norms),
    }


def load_state(opt: Config, st, saved):
    """Restore, or refuse by name. Returns a LoadReport.

    REFUSES when saved.param_group_shape differs from the live one: the optimizer moment restore in
    the old tree did not verify that the module composition matched the checkpoint (ISSUES P1-L50),
    and AdamW state is POSITIONAL over param groups, so a changed group order silently attaches one
    tensor's moments to another. REPORTS rather than refuses when the horizon changed (a legitimate
    resume at a different run length), and prints both horizons.

    LEVERS READ: none
    WIRES READ: none
    DID IT FIRE: opt.ckpt.loaded, opt.ckpt.refused (with the reason)
    """
    opt = opt.owned_by("OPT")

    live = st.param_group_shape
    was = saved.get("param_group_shape")
    if was is None:
        st.counters["opt.ckpt.refused"] += 1
        return LoadReport(
            restored=False, refused=True,
            reason="the checkpoint carries no param_group_shape. The old checkpoint saved opt_m "
                   "and opt_e (:5372) and nothing else from this package, so there is nothing for "
                   "the L50 guard to compare against -- and a positional moment restore taken "
                   "without that comparison is exactly what the guard exists to stop.")
    was = tuple(tuple(r) if isinstance(r, (list, tuple)) else r for r in was)
    if _normalised_shape(was) != _normalised_shape(live):
        st.counters["opt.ckpt.refused"] += 1
        return LoadReport(
            restored=False, refused=True,
            reason=f"param_group_shape disagrees (ISSUES P1-L50). Checkpoint: "
                   f"{_shape_summary(was)}; live: {_shape_summary(live)}. AdamW state is POSITIONAL "
                   f"over param groups, so restoring across this difference attaches one tensor's "
                   f"moments to another and the run trains on scrambled second moments with every "
                   f"loss curve looking plausible.")

    st.base.load_state_dict(saved["base"])
    st.encoder.load_state_dict(saved["encoder"])
    st.opt_step = U.Steps(int(saved["opt_step"]))
    st.n_backward = U.Backwards(int(saved["n_backward"]))
    st.lr_prev = float(saved["lr_prev"])
    st.restart_amp = float(saved["restart_amp"])
    st.cycle_best = saved.get("cycle_best")
    st.cycle_index = int(saved.get("cycle_index", 0))
    st.shift_at = saved.get("shift_at")
    st.grad_norms = list(saved.get("grad_norms", ()))

    # THE COUNTERS COME BACK, EXCEPT THE ONES THAT DESCRIBE THIS PROCESS'S CONSTRUCTION. A mechanism
    # that fired 4,000 times before the boundary must not read "armed but 0" after it; but
    # opt.build.* describes the horizon THIS build resolved, and taking those from the checkpoint
    # would report the parent run's warmup clamp against this run's schedule.
    for key, value in dict(saved.get("counters", {})).items():
        if key.startswith("opt.build."):
            continue
        st.counters[key] = value
    st.counters["opt.ckpt.loaded"] += 1

    saved_h = dict(saved.get("horizon", {}))
    live_h = {"run_steps": int(st.horizon.run_steps), "warmup": int(st.horizon.warmup),
              "wavelength": int(st.horizon.wavelength), "n_cycles": int(st.horizon.n_cycles)}
    if saved_h and saved_h != live_h:
        # REPORTED, NEVER REFUSED: resuming at a different run length is legitimate, and the LIVE
        # horizon is the one this run's run_windows resolved. Re-projecting mid-run is the
        # `_project`/`_lr_total`/`_proj_lr` machinery (:6335-6376) that produced E8 p=0.760.
        st.counters["opt.ckpt.horizon_changed"] += 1
        return LoadReport(
            restored=True, refused=False,
            reason=f"the horizon changed across the boundary and the LIVE one is in force. "
                   f"Checkpoint: {saved_h}; live: {live_h}. The schedule now prices "
                   f"step {int(st.opt_step)} against the live horizon, so a resume at a different "
                   f"run length moves every rate from here on -- which is the legitimate case, "
                   f"stated rather than silently taken.")
    return LoadReport(restored=True, refused=False, reason="")
