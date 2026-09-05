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


def _cycle_steps(horizon):
    """The REALIZED length of one cosine cycle, in optimizer steps. One expression, three readers.

    _schedule prices the phase with it, _cycle_index derives the index from it, and counters()
    prints it -- and each of those wrote it out longhand until 2026-09-04, which is three chances
    for the drift _cycle_index's own docstring records having already happened once.

    IT IS NOT THE SAME NUMBER AS st.horizon.wavelength AND THE REPORT PRINTS BOTH. The wavelength is
    what an operator ASKED for; this is what the whole-cycle fit at build() delivered, which differs
    by at most the rounding the fit does (the period moves by at most about 1/(2n) from nominal).
    Before the fit was corrected it differed by the WARMUP as well -- an operator asking 300 got 225.
    """
    return max(1.0, (int(horizon.run_steps) - int(horizon.warmup))
               / max(1, int(horizon.n_cycles)))


def _cycle_index(horizon, step, restarts):
    """Which cosine cycle `step` falls in, 0-based. Pure arithmetic on one horizon.

    Split out of the schedule because maybe_step has to record st.cycle_index and the schedule is
    documented PURE -- it returns a rate, not a state.

    THE WARMUP OFFSET IS `int(horizon.warmup)` AND _schedule USES THE SAME EXPRESSION, which it did
    not until 2026-09-04: this function read `int(horizon.warmup)` while _schedule read
    `max(1, int(horizon.warmup))`, so at a horizon whose warmup resolved to 0 -- which build()
    permits, since only a NEGATIVE lr_warmup is refused -- the two priced the cosine against
    different offsets and disagreed by one whole cycle on exactly the cycle-boundary steps. The
    stored st.cycle_index was then one cycle AHEAD of the index the rate had been priced with, and
    it travels in state_dict and is reported. The repair is that _schedule dropped the `max(1, ...)`
    rather than that this function gained one: at warmup 0 there is no warmup, so the cosine spans
    the run from step 0, which is what this function already said.
    """
    w = int(horizon.warmup)
    run_end = int(horizon.run_steps)
    n = max(1, int(horizon.n_cycles))
    if not restarts:
        return 0
    if step >= run_end:
        return n - 1
    per_c = _cycle_steps(horizon)
    return max(0, int((step - w) / per_c))


def _schedule(*, lr, sched, min_frac, restarts, decay, shift_warm, restart_amp, shift_at,
              horizon, step):
    """The rate at `step`, plus the five gate observations. PURE: every input is an argument.

    Returns (rate, flags) where flags is
    (in_warmup, damped, shift_warm_applied, envelope_applied, floored).

    THE OLD VERSION REACHED OUT OF ITSELF for `_shift_at`, which DATA's resample branch wrote as a
    closure variable (:6518-6521) -- the L2 violation this replaces. Here the shift step arrives as
    an argument that maybe_step read off the state that the composition root stamped.

    `step` IS 1-BASED HERE AND THE RAMP IS PRICED FOR THAT, corrected 2026-09-04. maybe_step
    advances st.opt_step BEFORE pricing, so the first step this function ever sees is 1, while the
    ramp was written `lr * (step + 1) / w` -- the 0-based form. Three measured consequences, one
    root: the ramp reached full peak at step w-1 instead of at w (warmup 100 -> peak at 99, 20 ->
    19, 3 -> 2); its lowest rung was 2/w of peak instead of 1/w, so at warmup=2 the single warmed
    step was priced at (1+1)/2 = the UNWARMED rate while opt.lr.in_warmup reported 1; and the whole
    ramp was one rung short. `lr * step / w` over `step < w` is the 1-based form: steps 1..w-1 are
    priced below peak, step w is priced by the cosine at p=0, which IS peak, so the ramp reaches
    peak at exactly the step the lever asked for and every step counted by opt.lr.in_warmup is a
    step that was genuinely attenuated.

    AT A RESOLVED WARMUP OF 1 NO STEP CAN BE IN WARMUP, and that is arithmetic rather than a bug:
    with a 1-based counter a ramp that reaches peak at step 1 has no rung below peak. It is not
    exotic -- build() clamps the warmup to `max(1, run_steps // 10)`, so every run of 19 or fewer
    optimizer steps resolves to it -- so counters() carries a Gate opt.lr.warmup that declares it
    UNREACHABLE with the two numbers, instead of leaving opt.lr.in_warmup to print a bare 0 that a
    reader cannot tell from "it ran and never triggered".
    """
    if sched == "none":
        # THE ONE-FLAG ABLATION, and it returns the peak flat -- "none" restores the pre-schedule
        # behaviour EXACTLY, which is the property that makes it an ablation rather than an arm.
        # EVERY FLAG IS False AND NOT ONE OF THEM IS A MEASUREMENT: nothing below this line runs, so
        # counters() must render the mechanisms they feed as UNREACHABLE and not as "armed, did not
        # fire" -- see the sched arm of every gate there.
        return float(lr), (False, False, False, False, False)

    w = int(horizon.warmup)
    if step < w:
        # PAID ONCE, NOT PER CYCLE: the point of warmup is that the optimizer state is COLD, which
        # is only true the first time (:4762-4765). A restart returns to peak in ONE step by
        # design, which is exactly why the damping in group 3 exists.
        # NOT FLOORED AT min_frac, DELIBERATELY: the lever says "linear ramp FROM ZERO", so the
        # first rungs are below the cosine's floor by construction. That is why lr_at's stated
        # minimum property is scoped POST-WARMUP rather than over the whole run.
        return float(lr) * step / w, (True, False, False, False, False)

    run_end = int(horizon.run_steps)
    wave = max(1, int(horizon.wavelength))
    span = max(1, wave - w)
    n = max(1, int(horizon.n_cycles))

    if restarts:
        # WHOLE CYCLES ONLY, FITTED AT build(). Truncating instead left a 30-epoch run with 2
        # cycles and a THIRD of its length parked at the floor. At n == 1 this branch is
        # bit-identical to restarts=off ONLY WHEN THE WAVELENGTH IS THE RUN, which the 0 sentinel
        # forces and which every recorded result was taken under -- the else branch below anneals
        # over `max(1, wave - w)` and this one over `(run_end - w) / n`, so a bare wavelength makes
        # them differ on 899 of 1000 steps. See lr_at's docstring for the measured table.
        per_c = _cycle_steps(horizon)
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
    floored = cyc < min_frac
    cyc = max(min_frac, cyc)
    return float(lr) * cyc, (False, damped, warmed, enveloped, floored)


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


def _stale_note(st, counter_name, reason):
    """Extend an UNREACHABLE reason with the count a resume carried across a boundary.

    THE CONTRADICTION THIS ANSWERS IS PRINTABLE TODAY AND WAS PRINTED SILENTLY. load_state restores
    every counter except opt.build.* -- deliberately, because "a mechanism that fired 4,000 times
    before the boundary must not read 'armed but 0' after it" -- while every reachability predicate
    in counters() is computed from the LIVE Config alone. Resume a run that had clipping, a re-warm
    and four cycles into a run at the shipped defaults and one ledger carried
    opt.lr.envelope_applied=901 beside "Gate opt.lr.decay: UNREACHABLE ... off BY ARITHMETIC",
    opt.lr.shift_warm_applied=4 beside "UNREACHABLE ... OPT_LR_SHIFT_WARM=0", and
    opt.restart.detected=2 beside "UNREACHABLE ... no restart can occur".

    spine/gate.py::Gate.__post_init__ REFUSES a Gate that is both unreachable and fired, which is the
    record's one self-check, and every unreachable arm here passes a literal False -- so the guard
    cannot trip and the contradiction is printed instead of refused. Raising here is the wrong
    repair: it would take down the whole DID IT FIRE surface of the package for a reading that is
    TRUE about the parent run. The right one is to say which run the number belongs to, in the arm's
    own reason, where a reader is already looking.
    """
    n = int(st.counters.get(counter_name, 0) or 0)
    loaded = int(st.counters.get("opt.ckpt.loaded", 0) or 0)
    if not n:
        return reason
    if loaded:
        return (f"{reason} THE LEDGER CARRIES {counter_name}={n} FROM BEFORE A RESUME "
                f"(opt.ckpt.loaded={loaded}): load_state restores every counter, this arm's "
                f"reachability is computed from the LIVE Config, and that number was produced by a "
                f"configuration no longer in force. It is not a measurement of this run.")
    return (f"{reason} AND YET {counter_name}={n} WITH NO RESUME TO EXPLAIN IT, which this "
            f"configuration cannot produce -- read it as a defect in this package, not as a "
            f"measurement.")


def _applied_lr(st):
    """The rate the optimizer is ACTUALLY at: the base group's own `lr`, not a remembered one.

    maybe_step's not-due branch returns "the rate the optimizer is currently at", and it answered
    that from st.lr_prev, which build() initialises to 0.0 and nothing writes until the first step
    is taken. So the first accum-1 calls of every run reported 0.0 while both AdamW instances
    genuinely held opt.lr. Reading the group answers the question the branch actually asks, needs no
    new state, and is correct after a resume too, where st.lr_prev is at best stale.
    """
    for group in st.base.param_groups:
        return float(group["lr"])
    return float(st.lr_prev)


def _encoder_step_signature(optimizer):
    """A cheap fingerprint of how many steps an optimizer has taken, for the Q-OPT-6 tripwire.

    THE COUNTER IT FEEDS HAD NO WRITER UNTIL 2026-09-04, WHICH MADE IT A TRIPWIRE THAT COULD NOT
    TRIP. `opt.encoder_steps_here` was initialised to 0 in build(), named in maybe_step's DID IT
    FIRE block and rendered by counters(), and nothing anywhere incremented it -- so the regression
    it names (SIG.train_step on SIG's cadence and this flush gate BOTH stepping the encoder) would
    have returned with the counter still reading 0, because the only thing that could have raised it
    was the very edit that introduces the defect. A guard whose condition cannot be satisfied is
    exactly the shape spine/gate.py::Gate exists to keep out of the report.

    WHY A FINGERPRINT AND NOT `len(optimizer.state)`. SIG legitimately steps this same optimizer on
    its own cadence, so a state dict that is merely non-empty proves nothing. maybe_step samples this
    BEFORE and AFTER its own body and compares: only a step taken INSIDE maybe_step can move it
    between those two lines, which is precisely the defect and nothing else.

    AdamW stores `step` per parameter, as a tensor on some builds and a float on others, so the sum
    is taken defensively -- a fingerprint that raises on a torch version change would take the run
    down to protect a counter.
    """
    total = 0.0
    for value in getattr(optimizer, "state", {}).values():
        if not isinstance(value, dict):
            continue
        try:
            total += float(value.get("step", 0))
        except (TypeError, ValueError):
            total += 1.0
    return (len(getattr(optimizer, "state", {})), total)


def _priced(opt, st, opt_step):
    """The rate at `opt_step` AND the five gate observations, unpacked from the Config in ONE place.

    IT TAKES THE CONFIG AND DOES NOT ASSERT AN OWNER, and both halves are deliberate. The file's
    private helpers otherwise take values precisely so that `owned_by` is written once per public
    entry point rather than six times; this one receives the Config that lr_at or maybe_step has
    ALREADY asserted on, so it adds no second assertion site and no second chance to write the wrong
    prefix. Its parameter is not Config-ANNOTATED for the same reason -- there is nothing here for
    tests/test_ownership.py::check_o9_one_config_per_signature to ask, because the question was
    answered one frame up.

    WHY IT EXISTS AT ALL: lr_at is documented "PURE: no closure reads, no globals, no measurement"
    and its P4 note invites a probe at an arbitrary step, and it was ALSO the only site that wrote
    opt.lr.in_warmup, damped_this_step, shift_warm_applied and envelope_applied. Those four are
    STEPS-in-state, so a probe over a step grid -- the exact tool the docstring recommends -- made
    them CALLS-in-state and inflated them permanently: fifty probes on a run that had taken zero
    steps left opt.lr.in_warmup reading 50. Splitting the unpack out lets lr_at discard the
    observations and stay pure, and lets maybe_step record them where a step actually happened,
    WITHOUT a second call site for _schedule -- two computations of one number is the defect
    _cycle_index's own docstring is about, one function up.
    """
    if type(opt_step) is not U.Steps:
        raise U.UnitError(
            f"OPT.lr_at / OPT.maybe_step: opt_step must be units.Steps, got "
            f"{type(opt_step).__name__}. The LR "
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

    return _schedule(
        lr=float(opt.lr), sched=str(opt.lr_sched), min_frac=float(opt.lr_min_frac),
        restarts=bool(opt.lr_restarts), decay=float(opt.lr_decay), shift_warm=shift_warm,
        restart_amp=float(st.restart_amp), shift_at=st.shift_at,
        horizon=st.horizon, step=int(opt_step))


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
        n_cycles   = max(1, round((run_steps - warmup) / max(1, wavelength)))
                     if opt.lr_restarts else 1
    THE DIVISOR IS THE WAVELENGTH AND NOT THE WAVELENGTH LESS THE WARMUP, corrected 2026-09-04, and
    the line this replaced was the one this docstring specified character for character. _schedule
    prices a cycle as `per_c = (run_end - w) / n`, so subtracting the warmup from the PERIOD as well
    as from the SPAN made the fitted count too large by wavelength / (wavelength - warmup) and the
    realized cycle correspondingly short: src/opt/levers.py::OPTLevers declares lr_wavelength as
    "Length of one cosine cycle, stated directly in optimizer steps", and an operator who asked for
    300 against a 1000-step horizon with warmup 100 got four cycles of 225. It was pathological
    where the period sat at or below the warmup, because `max(1, wavelength - warmup)` collapsed the
    denominator to 1 -- OPT_LR_WAVELENGTH=7 with warmup=100 over 1000 steps fitted 900 cycles of ONE
    step each. With the warmup out of the denominator the fit is (900 / 300) = 3 cycles of exactly
    300, and the 0 sentinel is untouched: it sets wavelength = run_steps, and the warmup can never
    exceed a tenth of the run, so (run_steps - warmup) / run_steps is always in [0.9, 1.0] and
    rounds to exactly ONE cycle -- which is what keeps every recorded single-cycle result bit-exact.
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

    lr_sched IS NOT IN THE LEVERS READ LINE BELOW AND IT USED TO BE, corrected 2026-09-04. It
    appeared nowhere in this body: the horizon is resolved, the sentinel taken, the warmup clamped
    and the cycles fitted identically whether the schedule is the cosine or the one-flag ablation.
    The line is the tree's only machine-adjacent record of who reads what and
    tests/test_contract.py states in its own header that it checks presence and not truth, so a name
    in it that the body never reads is a false entry no check can see. What remains true and is
    worth a reader's attention rather than a lever name: at OPT_LR_SCHED=none this function still
    resolves and PRINTS a horizon -- warmup, wavelength, cycles -- for a run whose rate is flat, and
    it is counters() that marks every one of those mechanisms UNREACHABLE.

    LEVERS READ: lr, weight_decay, lr_warmup, lr_wavelength, lr_restarts, lr_restart_damp,
                 lr_decay, lr_min_frac, accum, batch_windows, grad_clip
    WIRES READ: d_effective_batch_windows
    DID IT FIRE: opt.build.calls (exactly 1), opt.build.wavelength_from_sentinel,
                 opt.build.warmup_clamped with opt.build.warmup_asked and opt.build.warmup (the two
                 numbers the clamp is between -- named as KEYS here as of 2026-09-04, because
                 "with both numbers" described them without spelling either, and counters() reads
                 opt.build.warmup_asked by name),
                 opt.build.run_steps and opt.build.wavelength (the resolved horizon, ALSO WRITTEN
                 BY THIS FUNCTION AND MISSING FROM THIS ENUMERATION until 2026-09-04. They are the
                 build-time record of what opt_steps_from_windows and the 0 sentinel produced, they
                 survive into the returned ledger through `ledger = dict(st.counters)`, and they are
                 NOT the same reading as the report's own horizon line, which prints
                 st.horizon.run_steps and st.horizon.wavelength -- an unannounced integer in a dict
                 is exactly what opt.build.group_overlap was called out for two entries below),
                 opt.build.cycles_fitted (n_cycles --
                 "armed" for a restart means > 1, NOT lr_restarts == 1),
                 opt.build.params.base and opt.build.params.encoder (the two numbers that make a
                 group arriving EMPTY visible, argued for in this docstring and MISSING FROM THIS
                 ENUMERATION until 2026-09-04),
                 opt.build.group_overlap (tensors in BOTH groups -- one parameter stepped by OPT
                 here and again by SIG, which is the double-step hazard Q-OPT-6 is about seen from
                 the parameter side rather than from the optimizer side. It was written by this
                 function and printed by counters() while being named in no docstring anywhere, so
                 a nonzero value was a number the report printed with no stated meaning),
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
        # THE DIVISOR IS THE PERIOD ITSELF. _schedule prices a cycle as (run_end - w) / n_cycles, so
        # taking the warmup out of the numerator AND the denominator fitted too many cycles and
        # delivered a realized period of wavelength - warmup against the wavelength an operator set.
        n_cycles = max(1, round((total_steps - warmup_n) / max(1, int(wavelength))))
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
        "opt.restart.wraps": 0,
        "opt.restart.below_bar": 0,
        "opt.restart.damped": 0,
        "opt.restart.damp_refused_n1": 0,
        "opt.restart.no_reading": 0,
        "opt.restart.readings": 0,
        "opt.lr.writes.base": 0,
        "opt.lr.writes.encoder": 0,
        "opt.lr.in_warmup": 0,
        "opt.lr.damped_this_step": 0,
        "opt.lr.shift_warm_applied": 0,
        "opt.lr.envelope_applied": 0,
        "opt.lr.floor_applied": 0,
        "opt.encoder_steps_here": 0,
        "opt.clip.applied": 0,
        "opt.clip.armed_no_clip": 0,
        "opt.shift.notifications": 0,
        "opt.ckpt.saved": 0,
        "opt.ckpt.loaded": 0,
        "opt.ckpt.refused": 0,
        "opt.ckpt.horizon_changed": 0,
        "opt.ckpt.lr_prev_cleared": 0,
        "opt.ckpt.backward_at_load": 0,
        "opt.ckpt.step_at_load": 0,
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
    cycles and a THIRD of its length parked at the floor.

    "AT EXACTLY ONE FITTED CYCLE THE SCHEDULE IS BIT-IDENTICAL TO lr_restarts=off" IS TRUE ONLY AT
    THE 0 SENTINEL, and this docstring, _schedule's restarts-branch comment and a PRINTED gate
    reason in counters() all stated it without that scope until 2026-09-04. The two branches are
    priced against different lengths on purpose: restarts ON anneals over `(run_end - w) / n`, the
    RUN, and restarts OFF anneals over `max(1, wave - w)`, the WAVELENGTH, then holds at the floor
    -- which is what "instead of holding at the floor" means in the lever's own declaration. They
    coincide exactly when the wavelength IS the run, which the 0 sentinel forces and which is the
    only case every recorded result was taken under. Measured over a 1000-step horizon at the
    shipped defaults, restarts on against restarts off: OPT_LR_WAVELENGTH=0 and =1000 differ on 0 of
    1000 steps; =900 differs on 899; =800 differs on 899 with a max ratio of 3.6; =1500 differs on
    900. So an OPERATOR who sets a bare wavelength and switches restarts off gets exactly what the
    lever says -- one cycle of that wavelength and then the floor, or an un-annealed tail if the
    wavelength overruns the run -- and neither of those is reproducing an earlier result.

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
    schedule's minimum over a whole run, TAKEN POST-WARMUP AND WITH THE WAVELENGTH AT ITS SENTINEL,
    equals lr * lr_min_frac at EVERY restart count, single-cycle included.

    THE TWO SCOPES ARE NOT HEDGES, THEY ARE THE TWO CASES THE UNSCOPED SENTENCE WAS FALSE IN, and
    both are measured. (1) POST-WARMUP: the ramp is "linear from ZERO" by declaration, so its first
    rung is one warmup-step's fraction of peak, which at the shipped defaults over 1000 windows is
    2e-05 against a floor of 1e-04 -- the ramp starts below the floor because a floor on a ramp from
    zero is not a ramp from zero. (2) AT THE SENTINEL: with OPT_LR_RESTARTS=off and a wavelength
    LONGER than the run the cosine never completes, so the run ends un-annealed and its minimum is
    the final rate -- at OPT_LR_WAVELENGTH=1500 over 1000 steps that is 6.378e-04 against a floor of
    1e-04. That is the E8 p=0.760 under-anneal reachable again through the wavelength, and it is the
    operator's setting rather than a schedule defect, which is why the sentence is scoped rather
    than the arithmetic changed. The floor CLAMP itself is sound at every restart count tested
    (1, 3, 4 and 900).

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

    lr_restart_damp WAS IN THE LEVERS READ LINE BELOW AND THIS FUNCTION NEVER READ IT, corrected
    2026-09-04. The modifier bullet three paragraphs up already says the right thing -- the damping
    gate is `st.cycle_index > 0 and st.restart_amp < 1.0` -- so one docstring stated the dependency
    correctly in prose and incorrectly in the line that is parsed. The distinction is load-bearing
    rather than cosmetic: st.restart_amp is the ACCUMULATED PRODUCT maybe_step maintains and it
    travels in state_dict, while lr_restart_damp does not, and that separation is exactly the "came
    back at FULL AMPLITUDE" defect state_dict's docstring is about. A reader who trusted the line
    concluded the schedule re-reads the lever every step.

    THIS FUNCTION NOW WRITES NOTHING, which is what "PURE" above has always claimed. It used to be
    the only site that incremented opt.lr.in_warmup, opt.lr.damped_this_step,
    opt.lr.shift_warm_applied and opt.lr.envelope_applied, so every probe over a step grid -- the
    tool the P4 note directly invites -- inflated four DID IT FIRE counters permanently: fifty
    probes on a state that had taken zero optimizer steps left a ledger reporting fifty warmup
    steps. Those four are STEPS-in-state, so they are recorded in maybe_step, where a step happens,
    and both functions price through the one shared unpack in _priced.

    LEVERS READ: lr, lr_sched, lr_min_frac, lr_restarts, lr_decay, lr_shift_warm (all through the
                 shared unpack in _priced), lr_warmup, lr_wavelength (those two through st.horizon)
    WIRES READ: none
    DID IT FIRE: none -- see maybe_step for the four schedule observations and the floor, which are
                 counted per STEP and not per call to this function
    """
    opt = opt.owned_by("OPT")
    # THE OBSERVATIONS ARE DISCARDED HERE ON PURPOSE. They are per-STEP counters and this function
    # is a pure price at an arbitrary step; maybe_step calls the same _priced and records them.
    rate, _observations = _priced(opt, st, opt_step)
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
         ARRIVES. CHECKPOINTING lr_prev CLOSED THE COUNTER ROUTE AND LEFT THE HORIZON ROUTE OPEN,
         and load_state now closes that one: a resume that LENGTHENS the run re-prices the same step
         against a longer horizon, which moves the rate UP by far more than 1.5x whenever the parent
         ended deep in the anneal -- and a completed cosine run always does. Measured at pure
         shipped defaults on both sides: parent 1000 windows, checkpoint at opt_step=1000 with
         lr_prev=1.0e-4 (5.00% of peak); child at run_windows=2000 priced its first resumed step at
         1.2133e-3 (60.7% of peak, a 12.1x jump) and stamped restart=True, in the same ledger whose
         opt.lr.restarts gate reads "UNREACHABLE ... no restart can occur". The rate change is
         legitimate; classifying it as a RESTART is not, and no state can tell "the cosine wrapped"
         from "the horizon moved under a resumed step" -- so load_state clears lr_prev on exactly
         the boundary where it has become incomparable, and counts that it did;

      3b. TWO COUNTS THAT ARE NOT THE DETECTOR AND EXIST BECAUSE IT IS ONE. opt.restart.wraps is the
         structural fact -- st.cycle_index advanced -- and opt.restart.below_bar is a >1.5x jump the
         `lr > 0.5 * peak` condition rejected. THE DETECTOR IS BLINDED BY THE TWO MECHANISMS IT
         FEEDS, and the arithmetic is configuration-free: the peak of a damped wrap is
         lr * (min_frac + (1 - min_frac) * restart_amp), so at the shipped lr_min_frac=0.05 the bar
         is cleared only while restart_amp is above (0.5 - 0.05) / 0.95 = 0.4737 -- one damping at
         the shipped lr_restart_damp=0.5 leaves 0.525 of peak (detectable, barely) and two leave
         0.2875 (never again). The envelope does it independently at the shipped lr_decay=1.0, whose
         multiplier passes 0.5 at about 52% of the run. MEASURED over 4000 windows with the envelope
         off, seven fitted cycles, six real wraps, a losing Reading every step: damp=0.9 -> 6
         detected / 5 damped; damp=0.5 -> 3 / 2, amp latched at 0.25; damp=0.4 -> 2 / 1; damp=0.2 ->
         2 / 1. The lever is inverted in its own strength parameter -- the harder an operator damps,
         the fewer times the damping can be applied. And over 2068 steps with restart_amp held at
         1.0, so this is the CEILING on detection rather than the loop's behaviour, wavelength
         1200/700/520/400/300/210 gave 1 of 1, 1 of 2, 2 of 3, 2 of 4, 3 of 6 and 5 of 9 at
         lr_decay=1.0 against a clean sweep at lr_decay=0.0. CHANGING THE DETECTOR CHANGES WHAT A
         RESTART MEANS AND WHAT GETS DAMPED, so it is the owner's ruling and is NOT taken here; what
         is taken here is that the report can no longer be read as "3 restarts happened" when it
         means "3 of 6 wraps were visible". counters() prints wraps beside detected and says so;
      4. the closed loop: if a restart fired AND A READING ARRIVED and the cycle that just ended
         did not beat the best held-out it inherited, st.restart_amp *= opt.lr_restart_damp,
         cumulatively. A restart carrying NO Reading is not a verdict of any kind: it does not damp,
         it does not refuse, it does not disturb the inherited best, and it has its own counter
         (opt.restart.no_reading). Until 2026-09-04 it did the opposite of all three -- it erased
         cycle_best, which let the NEXT losing bet through undamped, and it incremented
         opt.restart.damp_refused_n1, the counter clause 4 reserves for the PLAN 3.8 seed-count
         refusal, on the one state counters() says in writing has nothing to refuse. best_bpb is
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

    lr_restarts AND lr_sched ARE READ HERE AND NOT ONLY THROUGH THE SCHEDULE, and neither was in
    the line below until 2026-09-04: lr_restarts by the cycle-index stamp, and lr_sched by the wrap
    counter, which must not count wraps in a schedule that has no cosine.

    LEVERS READ: accum, lr, lr_restart_damp, lr_restarts, lr_sched, grad_clip (plus everything the
                 schedule reads, through the shared unpack in _priced)
    WIRES READ: none
    DID IT FIRE: opt.step (BASE optimizer steps -- the encoder's are sig.train_stepped and live in
                 SIG), opt.step.not_due, opt.restart.detected, opt.restart.damped,
                 opt.restart.damp_refused_n1,
                 opt.lr.in_warmup, opt.lr.damped_this_step, opt.lr.shift_warm_applied,
                 opt.lr.envelope_applied (the n_cycles > 1 gate, the old _nenv) and
                 opt.lr.floor_applied (the lr_min_frac clamp actually biting -- the floor had
                 neither a counter nor a Gate in any configuration, so "the schedule never returned
                 zero" was unattested in the ledger). THE FIRST FOUR MOVED HERE FROM lr_at, which is
                 documented pure and documented as probeable and was inflating them from every
                 probe; opt.lr.floor_applied IS NEW AND WAS NEVER IN lr_at -- this line said "ALL
                 FIVE MOVED HERE" until 2026-09-04, which is two repairs landing in parallel and
                 being enumerated as one. There was nothing to move: the floor had no counter
                 anywhere in the tree, which is the sentence in this same entry and in counters()'s
                 own docstring, and a counter that never existed cannot have been probed,
                 opt.restart.wraps (cycle-index advances -- the STRUCTURAL restart count, which is
                 not opt.restart.detected and diverges from it exactly when the damping or the
                 envelope has lowered a wrap under the detector's own bar),
                 opt.restart.below_bar (a >1.5x jump the `lr > 0.5 * peak` condition rejected --
                 without it "no restart occurred" and "a restart occurred below the bar" are the
                 same zero),
                 opt.restart.no_reading (a restart that arrived with no held-out measurement: not a
                 damping, not a refusal, and formerly counted as the second),
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
                 silently because both call sites look correct in isolation. It is DERIVED from the
                 encoder optimizer's own step state, sampled around this function's body: nothing
                 incremented it until 2026-09-04, so the only thing that could ever have raised it
                 was the edit that introduces the defect, which made it a tripwire that could not
                 trip),
                 opt.grad_norm.p50 / opt.grad_norm.p99 (base group, read before zero_grad;
                 rendered by counters),
                 opt.clip.applied / opt.clip.armed_no_clip (grad_clip > 0 and no step exceeded it
                 -- a DIFFERENT statement from grad_clip == 0, and the report must make both),
                 opt.shift.notifications (0 means nobody is supplying shift_at)
    """
    opt = opt.owned_by("OPT")
    schedule_live = str(opt.lr_sched) != "none"

    # THE READING IS COUNTED ON ARRIVAL, WHICH IS WHAT MAKES IT THE MIRROR ITS OWN DID IT FIRE LINE
    # CLAIMS. opt.restart.readings used to be incremented inside `if restart:`, so it counted
    # Readings CONSUMED and read 0 on every run where no restart had yet fired no matter how many
    # Readings arrived -- and counters() then printed, on the damping gate's UNREACHABLE arm, "no
    # Reading has ever arrived (opt.restart.readings == 0), so the held-out measurement the damping
    # judges a cycle by does not exist". That is a statement about ANOTHER PACKAGE'S output and it
    # was false whenever EVAL was supplying Readings and no restart had happened yet -- the normal
    # state of every multi-cycle run before its first wrap, and the permanent state of every
    # OPT_LR_SCHED=none run. It sent a reader to debug EVAL for a condition OPT's own detector
    # caused. Counted here, beside opt.shift.notifications and outside the due-ness check exactly as
    # that one is, the counter means what it says. _reading's refusal of a bare float also now runs
    # on EVERY call rather than only on restart steps, which is the direction that refusal wants.
    value, seeds = _reading(best_bpb)
    if value is not None:
        st.counters["opt.restart.readings"] += 1

    # THE SHIFT IS STAMPED WHETHER OR NOT A STEP IS DUE. A self-inflicted shift lands on a WINDOW,
    # and the flush that notices it may not be a due one; recording it only on due flushes would
    # lose up to accum-1 of them and make lr_shift_warm's fire depend on the batch size.
    if shift_at is not None:
        # AND IT IS TYPE-REFUSED, MATCHING lr_at ONE FUNCTION AWAY (2026-09-04). This stamp used to
        # be `st.shift_at = int(shift_at)`, and units.Clock defines __int__/__index__, so a
        # units.Windows or units.Flushes was silently coerced to a bare int and then subtracted from
        # the optimizer-step counter inside _schedule. docs/04_CONTRACT.md states the protection as
        # SYMMETRIC -- "OPT's shift_at is units.Steps (clock.opt_steps); FAB's cooldown, warmup and
        # recover_min/max are units.Windows ... handing OPT's object to FAB raises UnitError instead
        # of being batch_windows-fold wrong" -- and only the FAB direction had it. The two stamps
        # are minted for ONE event on adjacent rows of spine/compose.py::LOOP_ORDER, so the wrong
        # object is one identifier away. Invisible at the shipped batch_windows=1, accum=1 where the
        # two counters coincide; 64x apart at fetch_big.py's recommended heavy-run command, where a
        # units.Windows(15) stamp moved the whole re-warm to optimizer step 15 -- the END of the
        # run. It cannot be repaired by CONVERTING: a Windows to Steps conversion for a runtime
        # INSTANT has no named function in spine.derive and would be a second horizon divisor.
        if type(shift_at) is not U.Steps:
            raise U.UnitError(
                f"OPT.maybe_step: shift_at must be units.Steps, got "
                f"{type(shift_at).__name__}. It is the OPTIMIZER STEP of the last self-inflicted "
                f"shift (clock.opt_steps), and lr_at subtracts it from the optimizer-step counter. "
                f"FAB.grow_check takes the SAME EVENT as units.Windows (System.shift_at_windows), "
                f"and the root mints both on adjacent rows of spine/compose.py::LOOP_ORDER -- so "
                f"the wrong object is one identifier away and at batch_windows=1, accum=1 it is "
                f"the same number. There is no conversion to offer: a runtime instant has no "
                f"named Windows-to-Steps function in spine.derive and inventing one here would be "
                f"a second horizon divisor.")
        st.shift_at = int(shift_at)
        st.counters["opt.shift.notifications"] += 1

    if not derive.accum_due(st.n_backward, opt.accum):
        st.counters["opt.step.not_due"] += 1
        # THE RATE THE OPTIMIZER IS CURRENTLY AT, not a fresh one: no step was taken, so nothing
        # rewrote the param groups, and returning a newly computed rate would tell FAB.own_lr_scale
        # a number the optimizer is not using. READ OFF THE PARAM GROUP AND NOT OFF st.lr_prev
        # (2026-09-04): build() constructs both AdamW instances with lr=opt.lr while st.lr_prev
        # starts at 0.0 and is only written after a step, so every not-due call BEFORE the first
        # optimizer step returned 0.0 while the groups genuinely held opt.lr -- the exact failure
        # this comment names, in the direction that looks safe. It cannot happen at the shipped
        # accum=1, where every call is due; at fetch_big.py's ACCUM=4 it is the first three calls of
        # the run, and StepOutcome.lr is the `applied_lr` argument of FAB.own_lr_scale under the C1
        # ruling. The group is the only thing that knows the answer, and it needs no new state.
        return StepOutcome(stepped=False, lr=_applied_lr(st), restart=False, damped=False)

    # 1. the schedule's counter, and the ONLY thing that advances it.
    st.opt_step = st.opt_step + U.Steps(1)
    st.counters["opt.step"] = int(st.opt_step)

    # 2. the rate, AND the five per-step schedule observations. They are recorded HERE and not in
    #    lr_at because they are STEPS-in-state: lr_at is documented pure and documented as
    #    probeable, and while it wrote them a probe over a step grid inflated all four permanently.
    lr, observations = _priced(opt, st, st.opt_step)
    in_warmup, sched_damped, warmed, enveloped, floored = observations
    if in_warmup:
        st.counters["opt.lr.in_warmup"] += 1
    if sched_damped:
        st.counters["opt.lr.damped_this_step"] += 1
    if warmed:
        st.counters["opt.lr.shift_warm_applied"] += 1
    if enveloped:
        st.counters["opt.lr.envelope_applied"] += 1
    if floored:
        st.counters["opt.lr.floor_applied"] += 1

    # THE INDEX OF THE STEP JUST PRICED. _schedule computes the same number from the same horizon
    # and the same step, so st.cycle_index and the index the damping gate used are equal by
    # construction on this path; the field exists so state_dict can carry it and counters can print
    # it, not as a second source the schedule reads back. (Equal BY CONSTRUCTION is now true at
    # every warmup: the two used different offsets at a resolved warmup of 0 until 2026-09-04.)
    prev_cycle_index = st.cycle_index
    st.cycle_index = _cycle_index(st.horizon, int(st.opt_step), bool(opt.lr_restarts))
    if schedule_live and st.cycle_index > prev_cycle_index:
        # THE STRUCTURAL WRAP COUNT, AND IT IS NOT THE SAME NUMBER AS opt.restart.detected. A wrap
        # is a fact about the horizon: the cycle index advanced. A DETECTED restart is what the rate
        # ratio below could see, and the two diverge because the restart PEAK is itself lowered by
        # the envelope and by the damping, so a genuine late wrap can arrive under the detector's
        # own `> 0.5 * peak` bar. Counted at sched=none never, because there is no cosine to wrap.
        st.counters["opt.restart.wraps"] += 1

    # 3. the restart detector. BOTH conditions: the warmup ramp climbs from zero, so the ratio bar
    #    alone reported a restart at steps 15 and 31 of an 18-epoch run, at 2% and 3% of peak.
    peak = float(opt.lr)
    jumped = bool(st.lr_prev > 0 and lr > 1.5 * st.lr_prev)
    restart = bool(jumped and lr > 0.5 * peak)
    if jumped and not restart and not in_warmup:
        # THE JUMP THE SECOND CONDITION REJECTED, WHICH HAD NO COUNTER AT ALL. Without it "no
        # restart occurred" and "a restart occurred below the bar" are the same zero, and they are
        # different runs. THE WARMUP RAMP IS EXCLUDED, because suppressing the ramp's own >1.5x
        # steps is the second condition's DOCUMENTED job -- the ramp climbs from zero, so its early
        # steps multiply the previous rate by far more than 1.5 and each one was logged as a cosine
        # restart at 2% and 3% of peak. Counting those here would put the intended suppressions and
        # the unintended blinding in one number, which is the collapse this counter exists to undo.
        st.counters["opt.restart.below_bar"] += 1
    damped = False
    if restart:
        st.counters["opt.restart.detected"] += 1
        # 4. the closed loop. A damped restart IS a verdict, so the Reading has to carry its seed
        #    count and a count below 2 is refused rather than damping quietly (PLAN 3.8).
        if value is None:
            # NO READING MEANS NO VERDICT, AND THE INHERITED BEST SURVIVES (2026-09-04). The last
            # line of this branch used to be an unconditional `st.cycle_best = value`, so a restart
            # that arrived with no Reading ERASED the best held-out it inherited -- against a field
            # named cycle_BEST and against clause 4 above, which judges a cycle against "the best
            # held-out IT INHERITED". Two consequences, both measured: the NEXT restart was then
            # judged on `cycle_best is None`, which reads as PAID however bad its reading was, so a
            # cycle of 9.0 against an inherited 2.0 went undamped; and the seed count of a
            # nonexistent Reading is 0, so `not paid` held and opt.restart.damp_refused_n1
            # incremented -- a counter clause 4 documents as the PLAN 3.8 SEED-COUNT refusal, on a
            # state counters() describes in writing as "with no Reading at all there is nothing to
            # refuse". Two different states, one number, and the state the gate called empty was
            # the one filling it. Now: nothing is judged, nothing is refused, the inherited best
            # stands, and the state has its own counter.
            st.counters["opt.restart.no_reading"] += 1
        else:
            paid = st.cycle_best is None or value < st.cycle_best - 1e-6
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

    # THE Q-OPT-6 TRIPWIRE, SAMPLED BEFORE THIS FUNCTION'S OWN STEP. Only a step taken INSIDE
    # maybe_step can move the encoder optimizer between here and the line after st.base.step(); SIG
    # stepping it on SIG's cadence happens outside this frame and is invisible to the comparison,
    # which is what makes the tripwire specific to the defect instead of firing on every correct run.
    encoder_before = _encoder_step_signature(st.encoder)

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
    # nonzero value is the double step returning -- and until 2026-09-04 NOTHING COULD RAISE IT:
    # the counter was initialised in build(), named in this docstring and rendered by counters()
    # with no `+= 1` anywhere in src/, so the regression it guards would have returned with the
    # tripwire still reading 0. It is now derived from the encoder optimizer's own step state,
    # sampled around this function's body, so the edit that introduces the defect is the edit that
    # trips it.
    if _encoder_step_signature(st.encoder) != encoder_before:
        st.counters["opt.encoder_steps_here"] += 1
    return StepOutcome(stepped=True, lr=float(lr), restart=restart, damped=damped)


def counters(opt: Config, st):
    """The DID IT FIRE ledger, plus the one invariant that proves the accumulation defect is dead.

    ASSERTS AND REPORTS: `opt.backward // max(1, opt.accum) == opt.step`, MEASURED FROM THE LAST
    RESUME. The old tree could not make this statement because it counted the wrong thing; a run
    that violates it is running H29 again under a new name. The subtraction is not a softening: the
    accumulation RATE can legitimately change at a run boundary -- OPT_ACCUM is a factor of the
    horizon's divisor, and load_state calls a resume at a changed horizon "the legitimate case" in
    so many words -- and the unshifted form then raised on exactly that resume and took the whole
    DID IT FIRE surface of the package down with it, blaming a defect (P3-H29) that had not
    happened. What it gives up: a parent that miscounted is not re-caught here. The parent's own
    counters() call is where that reading belongs.

    THE COMPARISON IS NOW Steps AGAINST Steps, THROUGH A NAMED CONVERSION, AND IT WAS AN UNNAMED
    ONE UNTIL 2026-09-04. It was written `due_steps = (n_bwd - base_bwd) // divisor` against
    `n_step - base_step`, on operands deliberately unwrapped to bare ints first, so units.Clock saw
    neither side: a backward-pass count divided by backward-passes-per-optimizer-step, compared
    against an optimizer-step count, with no kind anywhere in it. That is the shape
    tests/test_ownership.py::check_o11_no_unnamed_clock_arithmetic exists for, and O11 could not see
    it because its AST half matches only `opt.<clock_lever>` attribute operands and both of those
    were locals. THE NUMBER WAS RIGHT at every setting driven (accum=1: 1000 backward passes, 1000
    steps; accum=4: 62 backward passes, 15 steps, and 52 backward passes, 13 steps), which is
    precisely why it was written down rather than dismissed -- an inline cross-kind division is a
    defect even when it computes the right number, because it is a conversion nobody can audit.
    The function is spine/derive.py::opt_steps_from_backwards, which refuses anything but a
    Backwards at one end and a divisor below 1 at the other and returns units.Steps, so both sides
    of this comparison now carry their kind and units.Clock raises on its own if either is ever the
    wrong one. It is NOT a wire and costs nothing from the budget.

    ITS DIVISOR IS accum ALONE AND NOT THE EFFECTIVE BATCH, which is the way this repair breaks
    while looking correct. spine/derive.py::opt_steps_from_windows divides by
    `d_effective_batch_windows` because it starts at the WINDOW, two boundaries below an optimizer
    step; this starts at the BACKWARD PASS, one boundary below, because a backward pass is one
    flush. Passing the two-boundary divisor here would divide 62 backward passes by 64 at the
    heavy-run command and report 0 steps due against 15 taken -- a correct run raising the P3-H29
    message, which is a worse failure than the unnamed division it replaced.

    AND A BACKWARD COUNTER THAT WENT BACKWARDS IS REFUSED BEFORE THE CONVERSION, WITH THE FOUR
    NUMBERS (2026-09-05). `st.n_backward - U.Backwards(base_bwd)` is negative only if the counter
    fell across a resume, which load_state's stamping makes impossible in a sound process: it sets
    opt.ckpt.backward_at_load FROM st.n_backward AFTER the restore, and scaled_backward only ever
    adds one. spine/derive.py::opt_steps_from_backwards refuses that negative outright and names
    the four counter keys, but it holds neither base and cannot print their values; the guard here
    does, one line earlier. THE DETECTION IS NOT DUPLICATED, IT IS SPLIT ON PURPOSE: until
    2026-09-04 the fault was caught only as a side effect of `//` flooring a negative to at most
    -1, so `due != taken` fired -- a detection through a COMPARISON, which a simultaneous step
    regression cancels exactly, and which the same-day correction to truncation then removed
    altogether for every deficit smaller than accum. The count is now checked as a count, in both
    files, and only this one has the numbers to print.

    The report prints backward, step, accum, batch_windows and
    d_effective_batch_windows TOGETHER, so the batch size a run TRAINED at is a printed number
    rather than a configured one -- ACCUM appeared in no print anywhere in the old tree, while
    fetch_big.py names ACCUM=4 in its recommended heavy-run command and bench_gpu.sh ships ACCUM=2.

    Gates rendered with their own arithmetic (G4): lr_sched, lr_warmup, lr_min_frac (the floor),
    lr_restarts (n_cycles > 1, NOT the flag), lr_restart_damp (< 1.0 on a losing cycle -- ADDED TO
    THIS ENUMERATION 2026-09-04, when its live arm was found not to read the `< 1.0` its own
    unreachable arms already print), weight_decay > 0, grad_clip > 0 (twice: opt.build.grad_clip for
    the setting and opt.clip.applied for the steps that hit it), lr_decay > 0 and n_cycles > 1,
    lr_shift_warm > 0 and a shift_at ever supplied, and opt.ckpt.horizon_changed. Three more Gates
    are not lever-gated and are argued for elsewhere: opt.accum.invariant (the paragraph above),
    opt.grad_norm (the RENDERS paragraph below) and opt.encoder_steps_here (maybe_step's Q-OPT-6
    tripwire, read backwards -- 0 is the passing state). FOURTEEN in all, counted from the tree.

    EVERY ONE OF THEM TESTS `sched` FIRST, and until 2026-09-04 not one of them did. _schedule's
    first statement returns the peak flat at OPT_LR_SCHED=none, so the warmup, the wavelength, the
    floor, the restart wrap, the damping, the envelope and the re-warm are all downstream of a
    return -- and this function built every downstream gate from n_cycles, lr_decay, lr_shift_warm
    and the counters, never from the string. The ablation therefore printed "armed, did not fire"
    -- the words spine/gate.py::Gate reserves for a mechanism that RAN -- for three mechanisms with
    no code path, in the same report whose opt.lr.sched line asserted in writing that all of them
    were structurally unreachable. That is the arm the whole schedule hypothesis is tested on.

    TESTING `sched` FIRST IS NECESSARY AND IS NOT SUFFICIENT, AND TWO GATES NEEDED THE SECOND HALF
    (2026-09-04). Both printed "armed, did not fire" on a configuration where the mechanism ran and
    COULD NOT fire, which is the same collapse one lever down from the ablation.
      * opt.lr.min_frac. The clamp is the last act of _schedule and every term above it is already
        written above the floor -- the cosine bottoms exactly AT min_frac and the damping is
        `min_frac + (cyc - min_frac) * amp` -- so only the two MULTIPLIED modifiers, the envelope
        and the shift re-warm, can dive under it. The gate's reason said exactly that in prose while
        its reachability read only sched and min_frac, so THE SHIPPED DEFAULTS printed it armed:
        measured over the whole 1000-step horizon and 200 steps past it, floor_applied=0 with
        opt.lr.decay and opt.lr.shift_warm both printed UNREACHABLE in the same report.
      * opt.lr.restart_damp. maybe_step clause 4 is gated on `lr_restart_damp < 1.0`, and every
        unreachable arm of this gate already spells "< 1.0" into its own threshold, but the live arm
        did not read it: at OPT_LR_RESTART_DAMP=1.0 over 200 steps at OPT_LR_WAVELENGTH=20 with a
        losing Reading on every step -- 8 wraps, 4 detected restarts, 200 Readings -- the gate read
        "armed, did not fire (0 vs damp=1.0, refused_n1=0, no_reading=0, readings=200)", where the
        two companion zeroes are zero for the same reason the first one is.

    THE opt.accum.invariant GATE PRINTS THE COMPARISON ACTUALLY MADE, AND UNTIL 2026-09-04 IT
    PRINTED A FALSE EQUATION ON EVERY RESUMED RUN. The invariant is measured since the last resume;
    the Gate was built from the UNBASED counters, so a parent at OPT_ACCUM=1 with backward=8 step=8,
    resumed at OPT_ACCUM=4 and driven 8 more backward passes, printed "FIRED (16 backward // 4 vs
    10) -- backward // accum == step". 16 // 4 is 4. It is rendered from `due` and `taken`, the two
    sides of the `!=` itself; the run totals stay on the opt.backward=/opt.step= report line, where
    they are two numbers rather than an equation.

    THE WARMUP AND THE FLOOR HAD NO GATE AT ALL, in any configuration, and the warmup is
    structurally unreachable on every run of 19 or fewer optimizer steps because build() clamps it
    to a tenth of the horizon -- including the OPT_BATCH_WINDOWS=16 OPT_ACCUM=4 arm, where 1000
    windows give 15 steps and the warmup clamps 1000 down to 1. opt.lr.in_warmup then printed a bare
    0 that no reader could tell from "it ran and never triggered", beside a report line still
    reading "warmup=1 (asked 1000, clamped=True)".

    Two levers are reachable only by arithmetic and every result this project has
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

    lr_wavelength WAS MISSING FROM THE LINE BELOW ON THE SHIPPED-DEFAULT PATH. The opt.lr.restarts
    gate's one-cycle arm reads it twice -- once to choose the reason and once to print
    OPT_LR_WAVELENGTH= into it -- and that arm is what the shipped configuration takes, because the
    0 sentinel makes one wavelength span the run and n_cycles resolves to exactly 1. So every
    default run of this package read a lever its own contract said it did not.
    tests/test_contract.py cannot see that and says so in its header: "nothing about whether the
    levers a stub CLAIMS to read are the ones it will read". lr_min_frac joined the line with the
    floor gate.

    LEVERS READ: accum, batch_windows, lr_sched, lr_restarts, lr_decay, lr_shift_warm,
                 weight_decay, lr_restart_damp, grad_clip, lr_wavelength, lr_min_frac
    WIRES READ: d_effective_batch_windows
    DID IT FIRE: this call IS the DID IT FIRE surface for the package
    """
    opt = opt.owned_by("OPT")
    effective = opt.d_effective_batch_windows  # WIRE READ HERE -- printed beside opt.backward

    divisor = max(1, int(opt.accum))
    windows_per_flush = int(opt.batch_windows)
    n_bwd = int(st.n_backward)
    n_step = int(st.opt_step)
    # THE INVARIANT IS MEASURED SINCE THE LAST RESUME, AND THAT IS A REPAIR RATHER THAN A WEAKENING.
    # load_state restores n_backward and opt_step verbatim and BLESSES a resume whose horizon
    # changed -- "the legitimate case, stated rather than silently taken". OPT_ACCUM is a factor of
    # that horizon's divisor, so changing it IS that legitimate case; and the invariant, evaluated
    # with the LIVE accum against a ratio accumulated under the OLD one, then raised and killed the
    # entire DID IT FIRE surface of the package -- every Gate, the quantiles, the horizon residual,
    # the report lines -- with a message naming ISSUES P3-H29, a defect that had not occurred.
    # Measured: parent at OPT_ACCUM=1 with 8 backward and 8 steps, child at OPT_ACCUM=4 loading it,
    # LoadReport(restored=True, refused=False) and then "2 optimizer steps were due and 8 were
    # taken". The rate can only change at a boundary, so the statement that has to hold is about
    # THIS process's backward passes against THIS process's steps; load_state stamps the pair it
    # restored and the subtraction below is what makes the two sides comparable again. What it
    # gives up is stated plainly: a parent that miscounted is no longer caught in the child. The
    # parent's own counters() call is where that reading belongs, and it makes it.
    base_bwd = int(st.counters.get("opt.ckpt.backward_at_load", 0) or 0)
    base_step = int(st.counters.get("opt.ckpt.step_at_load", 0) or 0)
    # BOTH SIDES CARRY THEIR KIND, AND THE CONVERSION BETWEEN THEM HAS A NAME. The two
    # subtractions are within one kind each (Backwards from Backwards, Steps from Steps), which
    # units.Clock permits and which is what makes "since the last resume" expressible at all;
    # spine/derive.py::opt_steps_from_backwards is the one boundary crossed, and `!=` between two
    # units.Steps raises UnitError of its own accord if either side ever arrives in another kind.
    # The divisor is accum, NOT d_effective_batch_windows: that product spans the window boundary
    # as well and belongs to the horizon, which build() resolves with opt_steps_from_windows.
    # THE BACKWARD COUNTER CANNOT GO BACKWARDS ACROSS A RESUME, AND THIS IS THE SENTENCE WITH THE
    # NUMBERS IN IT. spine/derive.py::opt_steps_from_backwards refuses a negative count outright and
    # explains itself, but it holds neither base, so its message can name the four counter keys and
    # not their values. This raises one line earlier, where all four are in hand. Both are kept: the
    # detection belongs at the count, where no second regression can cancel it, and the reporting
    # belongs here, beside the two bases.
    if int(st.n_backward) < base_bwd:
        raise ValueError(
            f"OPT.counters: the backward counter went BACKWARDS across a resume -- "
            f"backward={n_bwd} against opt.ckpt.backward_at_load={base_bwd}, with step={n_step} "
            f"against opt.ckpt.step_at_load={base_step}. load_state stamps the base FROM "
            f"st.n_backward AFTER the restore and scaled_backward only ever adds U.Backwards(1), so "
            f"a sound process cannot produce this. Until 2026-09-04 it was caught only as a SIDE "
            f"EFFECT of `//` flooring: floor(n/k) is at most -1 for every n < 0, so no deficit came "
            f"back as zero and the comparison below raised whenever the step side had not fallen by "
            f"the same amount. Being a COMPARISON is what made it weak "
            f"-- a resume that lost accum backward passes AND one optimizer step gave due == taken "
            f"and cancelled it -- and the same-day repair from flooring to TRUNCATION then answered "
            f"Steps(0) for every deficit smaller than accum and removed even that. It is checked on "
            f"the count itself now, here and in spine/derive.py::opt_steps_from_backwards, and this "
            f"is the one of the two that has the numbers.")
    due = derive.opt_steps_from_backwards(st.n_backward - U.Backwards(base_bwd), divisor)
    taken = st.opt_step - U.Steps(base_step)
    due_steps = int(due)
    if due != taken:
        since = ("" if not (base_bwd or base_step) else
                 f" Measured since the last resume, which restored backward={base_bwd} and "
                 f"step={base_step}: {n_bwd - base_bwd} backward pass(es) and "
                 f"{n_step - base_step} step(s) have happened in THIS process.")
        raise ValueError(
            f"OPT.counters: the accumulation invariant is broken -- backward={n_bwd}, "
            f"accum={divisor}, so {due_steps + base_step} optimizer steps were due and {n_step} "
            f"were taken.{since} "
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
    min_frac = float(opt.lr_min_frac)
    wavelength_set = int(opt.lr_wavelength)          # LEVER READ HERE -- printed in two gate reasons
    sched_live = sched != "none"
    warmup_n = int(st.horizon.warmup)
    warmup_asked = int(st.counters["opt.build.warmup_asked"])
    cycle_steps = _cycle_steps(st.horizon)
    wraps = int(st.counters["opt.restart.wraps"])
    below_bar = int(st.counters["opt.restart.below_bar"])
    detected = int(st.counters["opt.restart.detected"])
    no_reading = int(st.counters["opt.restart.no_reading"])
    ckpt_loaded = int(st.counters["opt.ckpt.loaded"])
    horizon_changed = int(st.counters["opt.ckpt.horizon_changed"])

    # THE TWO MULTIPLIED MODIFIERS, NAMED ONCE, BECAUSE THE FLOOR GATE'S REACHABILITY IS THEIRS.
    # `floored` in _schedule is `cyc < min_frac` evaluated AFTER every other term, and every other
    # term is written so that it cannot go below min_frac: the cosine bottoms exactly AT it and the
    # damping is `min_frac + (cyc - min_frac) * amp`. Only the envelope and the shift re-warm
    # MULTIPLY the floored cycle, so they are the only two conditions under which the clamp can
    # bite -- which is what the floor gate's own reason has always said in prose while its
    # reachability predicate did not read them.
    envelope_live = decay > 0.0 and n_cycles > 1 and int(st.horizon.run_steps) > warmup_n
    rewarm_live = shift_warm > 0 and notifications > 0
    floor_reachable = sched_live and min_frac > 0.0 and (envelope_live or rewarm_live)

    # THE ONE SENTENCE EVERY DOWNSTREAM GATE NEEDS AT THE ABLATION, and the reason they all need it:
    # _schedule's FIRST statement is `if sched == "none": return float(lr), (...)`, so the warmup,
    # the wavelength, the floor, the restart wrap, the damping, the envelope and the shift re-warm
    # are every one of them downstream of a return and NONE of them is evaluated. Until 2026-09-04
    # counters() built each of those gates from n_cycles, lr_decay, lr_shift_warm and the counters
    # and NEVER from `sched`, so the ablation printed "armed, did not fire (0 vs 4 cycles fitted)"
    # for a schedule with no cycles, "(0 vs decay=1.0)" for an envelope with no code path, and
    # "(0 vs 1 notification(s) x 50 steps)" for a re-warm that positively invited the reader to
    # conclude a shift had been declined -- the words spine/gate.py::Gate reserves for "the
    # mechanism ran and its condition was not met", printed three times in the same report whose
    # opt.lr.sched line asserts, in writing, that all of them are structurally unreachable. THIS IS
    # THE ARM THAT MATTERS: lr_sched="none" is this package's one-flag ablation for the only
    # hypothesis that explains all 17 pilots.
    sched_off = (f"OPT_LR_SCHED=none returns the peak flat as _schedule's FIRST statement, so this "
                 f"mechanism is downstream of that return and is never evaluated -- structurally "
                 f"unreachable, which is what makes this an ablation rather than an arm.")

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
    ledger["opt.horizon.cycle_steps"] = cycle_steps

    gates = [
        # THE PRINTED ARITHMETIC IS THE COMPARISON ACTUALLY MADE, AND UNTIL 2026-09-04 IT WAS NOT.
        # The invariant is measured SINCE THE LAST RESUME -- that is what base_bwd and base_step are
        # for, and it is the repair that stopped a blessed resume at a changed OPT_ACCUM from raising
        # P3-H29 -- while this Gate was built from the UNBASED counters. Measured: a parent at
        # OPT_ACCUM=1 with backward=8 step=8, resumed at OPT_ACCUM=4 and driven 8 more backward
        # passes, reaches backward=16 step=10, counters() correctly returns, and the line read
        # "Gate opt.accum.invariant: FIRED (16 backward // 4 vs 10) -- backward // accum == step".
        # 16 // 4 is 4. The gate asserted an equation its own printed numbers refuted, under the word
        # FIRED, in the one line whose stated job is proving P3-H29 dead -- and a reader chasing an
        # accumulation defect on a resumed run has nothing else to go on. `due` and `taken` ARE the
        # two sides of the `!=` three lines up, so the gate now renders those; the unbased pair is
        # still printed, correctly, on the opt.backward=/opt.step= report line above.
        Gate("opt.accum.invariant", True,
             f"{n_bwd - base_bwd} backward // {divisor}", int(taken),
             reason=("backward // accum == step -- the one statement that proves ISSUES P3-H29 dead"
                     if not (base_bwd or base_step) else
                     f"backward // accum == step -- the one statement that proves ISSUES P3-H29 "
                     f"dead, MEASURED SINCE THE LAST RESUME, which restored backward={base_bwd} and "
                     f"step={base_step}. The numbers above are this process's own "
                     f"({n_bwd - base_bwd} backward pass(es) against {int(taken)} step(s)); the "
                     f"run totals are opt.backward={n_bwd} and opt.step={n_step} on the report line "
                     f"above, and OPT_ACCUM may legitimately have changed at the boundary, so those "
                     f"two are NOT the pair this equation holds between.")),
        # reachable=sched_live AND NOT reachable=True. It was hard-coded True, so the ablation
        # printed "armed, did not fire (none vs cosine)" -- the measurement words -- followed by its
        # own reason asserting unreachability. One line making both statements. The two gates
        # immediately below it in this list, opt.build.grad_clip and opt.weight_decay, already spell
        # the lever-valued form correctly and this one now matches them.
        Gate("opt.lr.sched", sched_live, sched, "cosine",
             reachable=sched_live,
             reason=("" if sched_live else
                     "OPT_LR_SCHED=none: the warmup, the wavelength, the floor, the restarts, the "
                     "damping, the envelope and the re-warm are ALL structurally unreachable, "
                     "which is what makes this an ablation rather than an arm. Every gate below "
                     "that names one of them says so on its own line.")),
        # THE WARMUP HAD NO GATE IN ANY CONFIGURATION and surfaced only as the bare counter
        # opt.lr.in_warmup and a report line -- including at a resolved warmup of 1, where NO step
        # can be in warmup and the counter's 0 is indistinguishable from "it ran and never
        # triggered". build() clamps the warmup to a tenth of the horizon, so warmup=1 covers every
        # run of 19 or fewer optimizer steps, and the report line still said
        # "warmup=1 (asked 1000, clamped=True)" -- which a reader takes as one step of warmup having
        # happened. Zero happened.
        Gate("opt.lr.warmup", sched_live and warmup_n > 1
             and st.counters["opt.lr.in_warmup"] > 0,
             st.counters["opt.lr.in_warmup"],
             f"{max(0, warmup_n - 1)} step(s) below peak, peak at step {warmup_n}",
             reachable=sched_live and warmup_n > 1,
             reason=(sched_off if not sched_live else
                     f"the resolved warmup is {warmup_n} optimizer step(s) "
                     f"(OPT_LR_WARMUP={warmup_asked} against build()'s clamp of a tenth of a "
                     f"{int(st.horizon.run_steps)}-step horizon), and the counter this gate reads "
                     f"is 1-BASED: a ramp that reaches peak at step 1 has no rung below peak, so no "
                     f"step can be in warmup. This is not 'armed and did not fire'."
                     if warmup_n <= 1 else
                     "the ramp is linear FROM ZERO and is not floored at lr_min_frac, which is why "
                     "lr_at's minimum property is scoped post-warmup")),

        # THE FLOOR HAD NEITHER A GATE NOR A COUNTER, so "the schedule never returned zero" -- the
        # whole of lr_min_frac's goal-B argument -- was unattested in the ledger, and at
        # OPT_LR_SCHED=none the floor is bypassed with nothing saying so. opt.lr.floor_applied
        # counts the steps where the clamp actually BIT, i.e. where the composition of the cycle
        # with the envelope or the re-warm had dived under the floor and this line pulled it back.
        #
        # AND IT NEEDS A COMPOSED MODIFIER TO EXIST, WHICH THE SHIPPED DEFAULTS DO NOT PROVIDE
        # (2026-09-04). The clamp is the last act of _schedule and every term above it is ALREADY
        # floored: the cosine bottoms AT min_frac (cos(pi * 1.0) is exactly -1.0, so `cyc < min_frac`
        # is False, not True), and the damping is written `min_frac + (cyc - min_frac) * amp`, which
        # cannot go below it either. The only two terms that MULTIPLY a floored cycle -- the envelope
        # and the shift re-warm -- are the only two ways the composition can dive under, which is
        # what this gate's own reason says. At the shipped defaults BOTH are off: n_cycles resolves
        # to 1 from the 0 sentinel so the envelope is gated out, and lr_shift_warm is 0. The gate
        # was reachable=(sched_live and min_frac > 0) regardless, so a default run printed
        # "Gate opt.lr.min_frac: armed, did not fire (0 vs min_frac=0.05 ...)" -- the words
        # spine/gate.py::Gate reserves for a mechanism that RAN and was not satisfied -- two lines
        # above "Gate opt.lr.decay: UNREACHABLE" and "Gate opt.lr.shift_warm: UNREACHABLE", the two
        # mechanisms its own reason names as the only routes to firing. Measured over the whole
        # 1000-step horizon at pure shipped defaults and 200 steps past it: floor_applied = 0,
        # envelope_applied = 0, shift_warm_applied = 0. lr_min_frac is a GOAL B lever and this is the
        # line that reports it, so "armed and inert" against "no composed modifier exists on this
        # configuration" is exactly the distinction that must not collapse here.
        Gate("opt.lr.min_frac", floor_reachable and st.counters["opt.lr.floor_applied"] > 0,
             st.counters["opt.lr.floor_applied"],
             f"min_frac={min_frac} clamping a composed modifier",
             reachable=floor_reachable,
             reason=(sched_off if not sched_live else
                     "OPT_LR_MIN_FRAC=0.0: the clamp is max(0.0, cyc) over a cosine that is already "
                     "non-negative, so no step can be raised by it and the schedule HAS no floor -- "
                     "which is the setting lr_min_frac's goal-B argument exists to warn about."
                     if min_frac <= 0.0 else
                     _stale_note(
                         st, "opt.lr.floor_applied",
                         f"OPT_LR_MIN_FRAC={min_frac} IS the floor and the cosine bottoms AT it, "
                         f"never under it -- and so does the damping, which is written above the "
                         f"floor by construction. Only a MULTIPLIED modifier can dive under, and "
                         f"neither exists here: the envelope needs OPT_LR_DECAY > 0 with more than "
                         f"one cycle fitted (OPT_LR_DECAY={decay}, {n_cycles} cycle(s) fitted over "
                         f"{int(st.horizon.run_steps)} steps against a warmup of {warmup_n}), and "
                         f"the re-warm needs OPT_LR_SHIFT_WARM > 0 with a shift_at supplied "
                         f"(OPT_LR_SHIFT_WARM={shift_warm}, {notifications} notification(s)). So no "
                         f"step of THIS run CAN need pulling back. The floor is still in force and "
                         f"still reached; it is never breached.")
                     if not floor_reachable else
                     "armed and no step needed pulling back: each modifier is individually floored, "
                     "and this counts only the steps where their COMPOSITION dived under the floor "
                     "(the envelope past its last peak, or a re-warm landing mid-anneal)")),

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
        # THE VALUE IS THE REAL COUNTER AND NOT A LITERAL 0, because 'opt.clip.applied' is BOTH a
        # counter key and a Gate name and the last lines of this function do `ledger[g.name] = g` --
        # so the Gate OVERWRITES the counter in the returned dict. With a literal 0 a restored count
        # of 1000 clipped steps was erased from the ledger entirely: st.counters still held 1000 and
        # the ledger the report reads said 0. Passing the counter means the number survives its own
        # overwrite and prints inside the gate's arithmetic.
        gates.append(Gate("opt.clip.applied", False, st.counters["opt.clip.applied"], "n/a",
                          reachable=False,
                          reason=_stale_note(
                              st, "opt.clip.applied",
                              f"OPT_GRAD_CLIP={clip} is OFF, so no step can clip. This is not "
                              f"'armed and did not fire'.")))

    # THE RESTART GATE IS ARITHMETIC AND NOT THE FLAG. `_ncyc = [1]  # "armed" for a restart means
    # >1, not LR_RESTARTS=1` (:4746). Every result this project has recorded came from a
    # single-cycle schedule, which is why the two levers below it have never fired in anger.
    if not sched_live:
        gates.append(Gate("opt.lr.restarts", False, detected, f"{n_cycles} cycles fitted",
                          reachable=False,
                          reason=_stale_note(
                              st, "opt.restart.detected",
                              f"{sched_off} build() still FITS {n_cycles} cycle(s) and this report "
                              f"still prints them, because the horizon is cheap and resolving it "
                              f"costs nothing -- but no cycle is ever priced, so the count is a "
                              f"property of the horizon and not of the run.")))
    elif not restarts_on:
        gates.append(Gate("opt.lr.restarts", False, n_cycles, "> 1 cycle", reachable=False,
                          reason=_stale_note(
                              st, "opt.restart.detected",
                              "OPT_LR_RESTARTS=off, so the cosine holds at the floor after one "
                              "cycle and no restart exists to detect.")))
    elif n_cycles <= 1:
        why = ("the 0 sentinel makes one wavelength span the whole run"
               if not wavelength_set else "the period does not divide the run twice")
        # THE "bit-identical to restarts=off" CLAIM IS SCOPED HERE, because this is a PRINTED line
        # and the claim is true only at the sentinel: restarts ON anneals over the run and restarts
        # OFF anneals over the wavelength, so at OPT_LR_WAVELENGTH=900 against a 1000-step horizon
        # the two differ on 899 of 1000 steps while this gate still reads one fitted cycle. What is
        # true on every arm of this branch, and is the load-bearing half, is that no restart can
        # occur.
        identical = (" and the schedule is bit-identical to restarts=off"
                     if not wavelength_set or wavelength_set == int(st.horizon.run_steps)
                     else " (the schedule is NOT bit-identical to restarts=off here: that branch "
                          "anneals over the WAVELENGTH and holds at the floor, this one anneals "
                          "over the RUN, and they coincide only at the 0 sentinel)")
        gates.append(Gate("opt.lr.restarts", False, n_cycles, "> 1 cycle", reachable=False,
                          reason=_stale_note(
                              st, "opt.restart.detected",
                              f"OPT_LR_RESTARTS is on and exactly ONE cycle fits: "
                              f"OPT_LR_WAVELENGTH={wavelength_set} against a horizon of "
                              f"{int(st.horizon.run_steps)} steps ({why}), so no restart can "
                              f"occur{identical}.")))
    else:
        # DETECTED IS NOT THE RESTART COUNT AND THE REASON SAYS SO WITH BOTH NUMBERS. opt.restart.
        # wraps is the structural fact -- the cycle index advanced -- and detected is what the rate
        # ratio could SEE. They diverge because the restart peak is itself lowered by the envelope
        # (lr_decay) and by the damping (lr_restart_damp), both of which this counter feeds, so the
        # instrument is switched off by its own output: a damped wrap peaks at
        # lr * (min_frac + (1 - min_frac) * restart_amp), which at the shipped lr_min_frac=0.05
        # clears the detector's `> 0.5 * peak` bar only while restart_amp stays above 0.4737.
        gates.append(Gate("opt.lr.restarts", detected > 0, detected, f"{n_cycles} cycles fitted",
                          reason=f"opt.restart.wraps={wraps} cosine wrap(s) actually occurred and "
                                 f"opt.restart.below_bar={below_bar} jump(s) fell under the "
                                 f"detector's own bar of half the peak rate, so DETECTED is what "
                                 f"the rate ratio could see and not the number of restarts. The "
                                 f"envelope and the damping lower each successive wrap's peak, "
                                 f"which is the detector's own input -- read a gap between wraps "
                                 f"and detected as the instrument going blind, not as the schedule "
                                 f"settling."))

    if not sched_live:
        gates.append(Gate("opt.lr.restart_damp", False, damp, "< 1.0 on a losing cycle",
                          reachable=False,
                          reason=_stale_note(st, "opt.restart.damped", sched_off)))
    elif not restarts_on:
        # THE SWITCH AND NOT THE ARITHMETIC IT SET. build() forces n_cycles = 1 in the `else` of
        # `if bool(opt.lr_restarts)`, so at OPT_LR_RESTARTS=off the cycle count is 1 BY DECREE; this
        # arm used to route through the n_cycles <= 1 reason below, which is a true sentence about
        # the wrong lever -- with OPT_LR_WAVELENGTH=300 against a 1000-step horizon three cycles
        # WOULD have fitted, and an operator read it as being told to change the wavelength they
        # had just set. Gate requires the reason to say WHY, not merely that.
        gates.append(Gate("opt.lr.restart_damp", False, damp, "< 1.0 past cycle 0", reachable=False,
                          reason=_stale_note(
                              st, "opt.restart.damped",
                              f"OPT_LR_RESTARTS=off, which forces the cycle count to 1 BY DECREE "
                              f"rather than by fit -- OPT_LR_WAVELENGTH={wavelength_set} against a "
                              f"{int(st.horizon.run_steps)}-step horizon is not what switched this "
                              f"off. The damping is gated on cycle_index > 0 and there is no second "
                              f"cycle, so OPT_LR_RESTART_DAMP={damp} cannot apply.")))
    elif n_cycles <= 1:
        gates.append(Gate("opt.lr.restart_damp", False, damp, "< 1.0 past cycle 0", reachable=False,
                          reason=_stale_note(
                              st, "opt.restart.damped",
                              f"the damping is gated on cycle_index > 0 and only "
                              f"{n_cycles} cycle(s) fit this run, so OPT_LR_RESTART_DAMP={damp} "
                              f"is off BY ARITHMETIC rather than armed and inert.")))
    elif damp >= 1.0:
        # THE LEVER AT ITS IDENTITY VALUE, WHICH EVERY UNREACHABLE ARM ABOVE ALREADY SPELLS INTO ITS
        # OWN THRESHOLD ("< 1.0 on a losing cycle") AND WHICH THIS BRANCH DID NOT READ UNTIL
        # 2026-09-04. maybe_step clause 4 is `if not paid and float(opt.lr_restart_damp) < 1.0`, so
        # at OPT_LR_RESTART_DAMP=1.0 no losing cycle can ever damp and no seed count can ever be
        # refused -- and this gate's else arm was reachable=True, so a multi-cycle run at damp=1.0
        # printed "armed, did not fire (0 vs damp=1.0, refused_n1=0, no_reading=0, readings=200)".
        # MEASURED, over 200 optimizer steps at OPT_LR_WAVELENGTH=20 with a losing Reading (9.0,
        # seed_count 3) on every step: 8 wraps, 4 detected restarts, 200 readings, damped=0. The
        # mechanism ran on four genuine losing restarts and could not fire on any of them, and the
        # three numbers the gate prints beside the 0 say nothing about why -- refused_n1 and
        # no_reading are 0 precisely BECAUSE the multiplier is the identity. build() refuses damp
        # above 1.0 outright, so 1.0 is the whole of this arm.
        gates.append(Gate("opt.lr.restart_damp", False, damp, "< 1.0 on a losing cycle",
                          reachable=False,
                          reason=_stale_note(
                              st, "opt.restart.damped",
                              f"OPT_LR_RESTART_DAMP={damp} is the IDENTITY multiplier and clause 4 "
                              f"of maybe_step is gated on `lr_restart_damp < 1.0`, so a losing "
                              f"cycle cannot be damped however many arrive: "
                              f"{detected} detected restart(s) and {readings} Reading(s) on this "
                              f"run reached that gate and none of them could pass it. The PLAN 3.8 "
                              f"seed-count refusal sits INSIDE the same branch, so "
                              f"opt.restart.damp_refused_n1 cannot move either -- its 0 is this "
                              f"lever's value, not a verdict on any Reading's seed count.")))
    elif readings == 0:
        # THE SENTENCE IS TRUE NOW AND WAS NOT BEFORE. opt.restart.readings counted Readings
        # CONSUMED by a detected restart, so it read 0 on every run where no restart had yet fired
        # no matter how many Readings EVAL had supplied -- and this arm then told the reader to go
        # debug EVAL for a condition OPT's own detector had caused. It is counted on ARRIVAL in
        # maybe_step now, beside opt.shift.notifications and outside the due-ness check exactly as
        # that one is, which is what its own DID IT FIRE line always claimed it was.
        gates.append(Gate("opt.lr.restart_damp", False, damp, "< 1.0 on a losing cycle",
                          reachable=False,
                          reason=_stale_note(
                              st, "opt.restart.damped",
                              f"no Reading has ever arrived (opt.restart.readings == 0, counted on "
                              f"ARRIVAL), so the held-out measurement the damping judges a cycle by "
                              f"does not exist. A damped restart is a verdict and PLAN 3.8 forbids "
                              f"one on n<2; with no Reading at all there is nothing to refuse -- "
                              f"which is why opt.restart.no_reading={no_reading} is its own counter "
                              f"and not an entry in refused_n1.")))
    else:
        gates.append(Gate("opt.lr.restart_damp", st.counters["opt.restart.damped"] > 0,
                          st.counters["opt.restart.damped"],
                          f"damp={damp}, refused_n1="
                          f"{st.counters['opt.restart.damp_refused_n1']}, "
                          f"no_reading={no_reading}, readings={readings}",
                          reason=f"the wrap that TRIGGERS a damping is itself priced before the "
                                 f"multiplier lands, so it is delivered at full amplitude for that "
                                 f"one optimizer step and the cycle after it is the first damped "
                                 f"one -- the ordering is forced, because the detector infers a "
                                 f"restart from the rate ratio and the undamped rate has to exist "
                                 f"before the verdict can. A reader comparing restart_amp="
                                 f"{float(st.restart_amp):.4g} against the rate at the wrap will "
                                 f"find them inconsistent by exactly one step, and this is why."))

    if not sched_live:
        gates.append(Gate("opt.lr.decay", False, decay, f"decay={decay}", reachable=False,
                          reason=_stale_note(st, "opt.lr.envelope_applied", sched_off)))
    elif decay <= 0.0:
        gates.append(Gate("opt.lr.decay", False, decay, "> 0.0", reachable=False,
                          reason=_stale_note(
                              st, "opt.lr.envelope_applied",
                              "OPT_LR_DECAY=0.0 restores the pre-2026-08-26 behaviour exactly: "
                              "restarts return to full peak and no envelope is applied.")))
    elif not restarts_on:
        gates.append(Gate("opt.lr.decay", False, decay, "> 0.0 and n_cycles > 1", reachable=False,
                          reason=_stale_note(
                              st, "opt.lr.envelope_applied",
                              f"OPT_LR_RESTARTS=off, which forces the cycle count to 1 BY DECREE, "
                              f"and the envelope is gated on n_cycles > 1 -- so OPT_LR_DECAY="
                              f"{decay} is off because of the SWITCH and not because "
                              f"OPT_LR_WAVELENGTH={wavelength_set} failed to divide a "
                              f"{int(st.horizon.run_steps)}-step horizon twice.")))
    elif n_cycles <= 1:
        gates.append(Gate("opt.lr.decay", False, decay, "> 0.0 and n_cycles > 1", reachable=False,
                          reason=_stale_note(
                              st, "opt.lr.envelope_applied",
                              f"the envelope is gated on n_cycles > 1 and {n_cycles} cycle(s) "
                              f"fit, so OPT_LR_DECAY={decay} is off BY ARITHMETIC. Without that "
                              f"gate it squeezed a single cycle to lr_min_frac SQUARED.")))
    else:
        gates.append(Gate("opt.lr.decay", st.counters["opt.lr.envelope_applied"] > 0,
                          st.counters["opt.lr.envelope_applied"], f"decay={decay}",
                          reason="the envelope lowers each successive cycle's peak, which is also "
                                 "the restart detector's own input -- see opt.lr.restarts"))

    if not sched_live:
        gates.append(Gate("opt.lr.shift_warm", False, st.counters["opt.lr.shift_warm_applied"],
                          f"{notifications} notification(s) x {shift_warm} steps", reachable=False,
                          reason=_stale_note(
                              st, "opt.lr.shift_warm_applied",
                              f"{sched_off} {notifications} shift notification(s) were still "
                              f"STAMPED, because maybe_step records them whether or not the "
                              f"schedule can act on them -- but no re-warm was priced, so this line "
                              f"must not be read as lr_shift_warm having declined a shift.")))
    elif shift_warm <= 0:
        gates.append(Gate("opt.lr.shift_warm", False, shift_warm, "> 0", reachable=False,
                          reason=_stale_note(
                              st, "opt.lr.shift_warm_applied",
                              f"OPT_LR_SHIFT_WARM={shift_warm}, at or below the 0 that is "
                              f"the shipped default and the setting every recorded result "
                              f"was produced under.")))
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
                             "correct in isolation. IT IS NOW DERIVED AND NOT DECLARED: maybe_step "
                             "fingerprints the encoder optimizer's own step state before and after "
                             "its body, so only a step taken INSIDE maybe_step can raise it. Until "
                             "2026-09-04 nothing in the tree incremented it at all, which made it a "
                             "tripwire whose only possible trigger was the edit that introduces the "
                             "defect -- armed-and-inert words printed for a guard that could not "
                             "be satisfied."))

    # opt.ckpt.horizon_changed HAD NO GATE AND NO REPORT LINE, so the one counter that says a
    # resume changed the schedule's horizon was an unannounced integer in a dict -- while
    # load_state's own docstring singles that resume out as the case it REPORTS rather than refuses.
    if not ckpt_loaded:
        gates.append(Gate("opt.ckpt.horizon_changed", False, horizon_changed, "a checkpoint loaded",
                          reachable=False,
                          reason="no checkpoint has been loaded in this process (opt.ckpt.loaded "
                                 "== 0), so no boundary exists for a horizon to change across. "
                                 "This is not 'a resume happened and the horizon held'."))
    else:
        gates.append(Gate("opt.ckpt.horizon_changed", horizon_changed > 0, horizon_changed,
                          f"{ckpt_loaded} load(s)",
                          reason=f"a changed horizon is the LEGITIMATE resume and the LIVE horizon "
                                 f"is in force, so every rate from the boundary on is priced "
                                 f"against this run's length. st.lr_prev was cleared "
                                 f"{int(st.counters['opt.ckpt.lr_prev_cleared'])} time(s) for the "
                                 f"same reason: the parent's last rate is not comparable across a "
                                 f"horizon change, and comparing it reported a cosine RESTART on "
                                 f"the first resumed step -- the P1-H17 shape, arriving by the "
                                 f"horizon route after checkpointing lr_prev closed the counter "
                                 f"route. The accumulation invariant is measured from this boundary "
                                 f"too (backward={int(st.counters['opt.ckpt.backward_at_load'])}, "
                                 f"step={int(st.counters['opt.ckpt.step_at_load'])} at load)."))

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
        f"{bool(st.counters['opt.build.warmup_clamped'])}, "
        f"{max(0, warmup_n - 1)} step(s) priced below peak)  "
        f"wavelength={int(st.horizon.wavelength)} asked (from the 0 sentinel="
        f"{bool(st.counters['opt.build.wavelength_from_sentinel'])})  cycles_fitted={n_cycles}  "
        f"REALIZED cycle={cycle_steps:.4g} steps -- the number the cosine is actually priced "
        f"against, which the whole-cycle fit moves by at most the rounding it does",
        f"opt.restart: wraps={wraps} (cycle-index advances)  detected={detected} (what the rate "
        f"ratio saw)  below_bar={below_bar}  damped={st.counters['opt.restart.damped']}  "
        f"refused_n1={st.counters['opt.restart.damp_refused_n1']}  no_reading={no_reading}  "
        f"readings={readings} (arrivals)  restart_amp={float(st.restart_amp):.6g}",
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

    ⚠ grad_norms GROWS WITHOUT BOUND AND EVERY SAVE COPIES ALL OF IT, AND P4 IS NOT FIXING THAT
    HERE. maybe_step appends one float per optimizer step and nothing trims it, this function writes
    `list(st.grad_norms)`, and load_state restores the whole list -- so at the 48,000-step runs this
    package's docstring is about that is a 48,000-element list inside every checkpoint, and the cost
    over a run is quadratic in the number of saves. Driving 1000 windows at the defaults leaves
    opt.grad_norm.samples = 1000, verified. The paragraph above requires the DISTRIBUTION to survive
    the boundary and does NOT require the full per-step sample to be its carrier; counters() only
    ever renders two nearest-rank quantiles off it. But every candidate carrier -- a reservoir, a
    histogram, decimation -- CHANGES WHAT THE QUANTILES MEAN, and p50/p99 over a biased sample is a
    different instrument from p50/p99 over the run. That is the owner's ruling, not P4's, so the
    cost is written down here and in .rework/audits/repair_opt.json instead of being traded away
    quietly for a smaller file.

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

    A BLESSED RESUME USED TO MAKE counters() RAISE, AND IT BLAMED THE WRONG DEFECT. OPT_ACCUM is a
    factor of the horizon's divisor (OPT.d_effective_batch_windows is batch_windows by accum), so
    changing it IS the legitimate case this function names -- and n_backward and opt_step come back
    verbatim, accumulated under the OLD accum, while counters() evaluated `backward // accum ==
    step` with the LIVE one. Measured: parent at OPT_ACCUM=1 with 8 backward and 8 steps, child at
    OPT_ACCUM=4, LoadReport(restored=True, refused=False) and then "the accumulation invariant is
    broken -- backward=8, accum=4, so 2 optimizer steps were due and 8 were taken", which named
    ISSUES P3-H29 for a rate change this package had just called legitimate, and took every Gate,
    the grad-norm quantiles, the horizon residual and all the report lines down with it. Nothing
    re-bases n_backward and nothing here should: the parent's backward count is a fact about the
    parent. What was missing was the BOUNDARY, and this function now stamps it
    (opt.ckpt.backward_at_load, opt.ckpt.step_at_load) so the invariant is a statement about this
    process's passes against this process's steps.

    LEVERS READ: none
    WIRES READ: none
    DID IT FIRE: opt.ckpt.loaded, opt.ckpt.refused (with the reason),
                 opt.ckpt.horizon_changed (the resume this docstring singles out as REPORTED rather
                 than refused. It was written here, named in no DID IT FIRE line and given no Gate
                 and no report line by counters(), so the one counter that says a resume changed
                 the schedule's horizon was an unannounced integer in a dict; counters() now carries
                 Gate opt.ckpt.horizon_changed),
                 opt.ckpt.lr_prev_cleared (the same boundary, acted on: the parent's last rate is
                 not comparable across a changed horizon and comparing it stamped a phantom cosine
                 restart on the first resumed step),
                 opt.ckpt.backward_at_load and opt.ckpt.step_at_load (the pair counters() measures
                 the accumulation invariant from, because OPT_ACCUM may legitimately change at
                 exactly this boundary)
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

    # THE ACCUMULATION BOUNDARY, STAMPED AFTER THE RESTORE SO THE RESTORE CANNOT OVERWRITE IT.
    # counters() measures `backward // accum == step` from these two numbers, because OPT_ACCUM is a
    # factor of the horizon's divisor and this function BLESSES a resume at a changed horizon: the
    # ratio accumulated under the parent's accum is not a statement about the live one, and
    # evaluating it as though it were raised ValueError and killed the package's whole DID IT FIRE
    # surface while naming a defect (P3-H29) that had not occurred.
    st.counters["opt.ckpt.backward_at_load"] = int(st.n_backward)
    st.counters["opt.ckpt.step_at_load"] = int(st.opt_step)

    saved_h = dict(saved.get("horizon", {}))
    live_h = {"run_steps": int(st.horizon.run_steps), "warmup": int(st.horizon.warmup),
              "wavelength": int(st.horizon.wavelength), "n_cycles": int(st.horizon.n_cycles)}
    if saved_h and saved_h != live_h:
        # REPORTED, NEVER REFUSED: resuming at a different run length is legitimate, and the LIVE
        # horizon is the one this run's run_windows resolved. Re-projecting mid-run is the
        # `_project`/`_lr_total`/`_proj_lr` machinery (:6335-6376) that produced E8 p=0.760.
        st.counters["opt.ckpt.horizon_changed"] += 1
        # AND st.lr_prev IS CLEARED, BECAUSE ACROSS A CHANGED HORIZON IT IS NOT COMPARABLE. The
        # restart detector is `st.lr_prev > 0 and lr > 1.5 * st.lr_prev and lr > 0.5 * opt.lr`, and
        # a resume that LENGTHENS the run re-prices the same step against a longer horizon, which
        # moves the rate UP by far more than 1.5x whenever the parent ended deep in the anneal --
        # which a completed cosine run always does, because it ends at the floor. Measured at pure
        # shipped defaults on both sides: parent 1000 windows, saved at opt_step=1000 with
        # lr_prev=1.0e-4 (5.00% of peak); child at 2000 windows priced its first resumed step at
        # 1.2133e-3 (60.7% of peak, a 12.1x jump) and stamped restart=True, in a ledger whose
        # opt.lr.restarts gate read "UNREACHABLE ... no restart can occur". Three consequences, and
        # the second is the expensive one: StepOutcome.restart is one of the three self-inflicted
        # shift stamps spine/compose.py::LOOP_ORDER feeds FAB.grow_check, so the growth controller
        # was told "this loss jump is OURS" on exactly the first step after a resume -- the P1-H17
        # shape that checkpointing lr_prev was introduced to kill, arriving by the horizon route
        # after the counter route was closed. Clearing it costs one step of detection on a boundary
        # where the classification was meaningless, and the counter says it happened.
        if st.lr_prev:
            st.counters["opt.ckpt.lr_prev_cleared"] += 1
            st.lr_prev = 0.0
        return LoadReport(
            restored=True, refused=False,
            reason=f"the horizon changed across the boundary and the LIVE one is in force. "
                   f"Checkpoint: {saved_h}; live: {live_h}. The schedule now prices "
                   f"step {int(st.opt_step)} against the live horizon, so a resume at a different "
                   f"run length moves every rate from here on -- which is the legitimate case, "
                   f"stated rather than silently taken. st.lr_prev was cleared, so the first "
                   f"resumed step is not classified as a cosine restart against a rate the parent "
                   f"priced under a different horizon; and the accumulation invariant is measured "
                   f"from backward={int(st.n_backward)}, step={int(st.opt_step)}, so a resume at a "
                   f"changed OPT_ACCUM does not read as P3-H29.")
    return LoadReport(restored=True, refused=False, reason="")
