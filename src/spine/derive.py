"""Derived quantities: one pure named function each, carrying its unit, and nothing else in this file.

THE RULE THIS FILE IS. A value computed from more than one lever exists in exactly ONE place, under ONE
name, and no consumer recomputes it. Everything here is a pure function of its arguments -- no os.environ,
no lever import, no module state, no I/O -- so `spine.assemble` can call these once at startup, write the
answers into `d_`-prefixed wired fields (G5), and every consumer reads the answer instead of deriving it
again.

WHY THAT RULE, IN NUMBERS FROM THE SURVEY. 130 of 475 defect records are wrong-measurement or
unit-mismatch. Both of the two defects confirmed by reading the old source are recomputation defects:

  * BYTES PER TOKEN was estimated in three places by three different formulas. One of them,
    `sum(bytes_per_id) / vocab_size`, is a mean over VOCABULARY ENTRIES rather than over tokens as USED,
    so it weights a token minted once and never seen again exactly as heavily as one in every window.
    Its error is a function of the vocabulary's SHAPE and THE SIGN FLIPS with vocabulary size: at 512
    tokens the 256 single-byte seeds dominate the entry count while the stream prefers the longer merges,
    measured 1.50 unweighted against 1.85 as used -- reads LOW; at pilot vocabularies most entries are
    long and rare while the tokens actually carried are the short common merges -- reads HIGH. The
    signature width SIG_WIN=614 was picked off that estimator, along an axis (VMAX) it is not comparable
    across. `bytes_per_token` below is the measured quantity and there is no second estimator.

  * THE SIGNATURE WIDTH was resolved in two places from one knob whose zero meant two different things.
    self_organize.py:5676 resolved SIG_WIN=0 to `max(WIN, int(WIN * bpt))` -- 614 bytes in the last run --
    while self_organize.py:3919 sliced `[-max(1, SIG_WIN):]`, which resolves the same zero to ONE BYTE.
    Every eval-path routing decision in every report was therefore made on a one-byte signature while
    training used 614. Same knob, same zero, opposite meanings. `signature_width_bytes` below is the one
    width, and it has no sentinel value.

WHAT IS NOT HERE, DELIBERATELY. No class, no constant, no table, no cached value. A module-level constant
in this file would be a second place for a default to live, which is the L1 violation the spine exists to
stop. The few bare numbers that appear as keyword defaults below are NOT lever defaults -- each one is a
threshold that was a hard literal in the shipped tree (never an `_i(...)` read), and each carries the
measurement that chose it.

RELATIONSHIP TO THE ORACLE. Eight of these functions replay `.rework/oracle/*.json`, captured from the
shipped code at rm-predict `aee4a52` BEFORE it was frozen (P0, graft G11). Where a shipped function is
reproduced, its argument ORDER and its arithmetic are preserved exactly even where a tidier form exists,
because the table is the only evidence of what the old system actually did. Where the shipped function
reached into the environment from inside its body, the parameter arrives as an argument instead; that is
the only intended behavioural difference, and it is noted on the function.
"""
from .units import Backwards, Clock, Flushes, Steps, UnitError, Windows


# === capacity pressure ===========================================================================

def cull_gate_open(n_live, slots, pressure):
    """Is the population under enough capacity pressure for the utilization cull to run?

    UNIT IN: n_live = experts (count), slots = slots, pressure = fraction 0..1.
    UNIT OUT: on/off.

    THREE MECHANISMS LIVE BEHIND THIS ONE ARITHMETIC LINE -- the utilization cull, the utilization spare
    and FAB_RESCUE -- so a wrong answer here does not fail, it silently removes three things from the run.
    It has done exactly that: FAB_N0=2048 against FAB_NMAX=4096 parks occupancy at 0.50, below a
    FAB_PRESSURE of 0.75, and `fabric.spare` read ARMED AND INERT for an entire investigation. That is the
    untrippable-guard class (60 records) in its most expensive form, because the report showed a mechanism
    switched on.

    `n_live <= 2` IS A FLOOR, NOT A PRESSURE TEST. It is a separate clause with a separate reason: culling
    from a population of two can empty it. Reading it as part of the pressure test is what makes people
    believe the gate is one condition, and it is two.

    Reproduces oracle cull_gate_open exactly, including `max(1, slots)`: the guard against slots=0 is part
    of the shipped answer, not a tidy-up. At slots=0 the ratio is n_live/1, which is >= any pressure <= 1
    for any live population, so the gate stands OPEN on a fabric with no slots -- preserved because the
    table says so, and flagged here because it is surprising.
    """
    return not (n_live <= 2 or (n_live / max(1, slots)) < pressure)


def operating_population(pressure, slots):
    """The population the fabric equilibrates at, given the pressure setpoint and the slot count.

    UNIT IN: pressure = fraction 0..1, slots = slots. UNIT OUT: experts (count).

    THIS COUPLING IS IRREDUCIBLE AND THAT IS THE POINT. `pressure` is not a modifier on the cull, it is a
    SETPOINT: below `pressure x slots` the gate above is shut and nothing is culled, so the population
    grows; at or above it the cull runs. The steady state is therefore `pressure x slots` and no amount of
    interface design makes FAB_PRESSURE independent of FAB_NMAX -- they are one control loop with two
    named ends.

    THIS IS THE EXAMPLE PLAN SECTION 4 USES for why lever independence is stated as three testable
    properties (L1 single declaration, L2 single reader, L3 no undeclared reach) instead of as
    independence. "Levers do not affect each other" is not achievable here and a project that claims it
    is lying about its own control loop. What IS achievable, and what this function makes possible, is
    that the coupling is DECLARED, NAMED, COMPUTED IN ONE PLACE and printed in docs/03_WIRING.md with its
    reason. The claim is "every coupling in this system is enumerable", not "there are none".

    Consistency with the gate is a property, not a coincidence: for 0 < pressure <= 1 and slots >= 3,
    cull_gate_open(operating_population(p, s), s, p) is True and it is False one expert lower.

    The `max(3, ...)` is the same floor as the gate's `n_live <= 2`, restated here rather than shared,
    because a population of two does not become a population of two for a pressure reason.
    """
    n_slots = int(slots)
    exact = float(pressure) * n_slots
    # CEILING, because the gate opens at n_live/slots >= pressure, so the setpoint is the first INTEGER
    # population that satisfies it. The 1e-9 tolerance is not decoration: 0.45 * 4096 is not exactly
    # 1843.2 in IEEE754, and a product that lands one ULP above an integer would push this a whole expert
    # higher on one machine and not another. The isolation sweep (L3) compares integer fingerprints, so a
    # one-expert difference that depends on the host reads as a lever leak rather than as float noise.
    n = int(exact)
    if exact - n > 1e-9:
        n += 1
    n = max(3, n)
    # Never above the hard slot count. Reachable whenever pressure > 1, which is a configuration the gate
    # answers by never opening -- the population then runs to the cap, and this says the cap.
    return min(n_slots, n) if n_slots >= 3 else n_slots


def lift_to(cap, frac, floor):
    """The new soft cap after one earned lift.

    UNIT IN: cap = slots, frac = fraction 0..1, floor = slots. UNIT OUT: slots.

    PROPORTIONAL, SO ONE EARNED LIFT MEANS THE SAME THING AT EVERY CAP SIZE. A lift written as a fixed
    +N is a different-sized decision at 160 slots and at 4096, so a run's growth behaviour became a
    function of where it started rather than of what it earned. The absolute floor exists because the
    proportional term rounds to zero at small caps: at cap=100, frac=0.05 the proportional lift is 5, but
    at cap=16 it is 0 and the cap would be pinned forever with the valve reporting that it lifted.

    Reproduces oracle lift_to exactly, including `int(float(frac) * int(cap))` -- truncation, not rounding,
    so a lift is never larger than what was earned.
    """
    return int(cap) + max(int(floor), int(float(frac) * int(cap)))


# === the tokenizer's two derived widths ==========================================================

def bytes_per_token(n_bytes, n_tokens):
    """Compression as MEASURED on the material the loop actually strides through.

    UNIT IN: n_bytes = bytes, n_tokens = tokens. UNIT OUT: bytes/token.

    THIS IS TOTAL BYTES OVER TOTAL TOKENS OF THE SAME TEXT and nothing else. It is not
    `sum(bytes_per_id) / vocab_size`, which is a mean over vocabulary ENTRIES: that estimator weights a
    token minted once and never seen again exactly as heavily as one carried in every window, so its
    error is a function of the vocabulary's shape and ITS SIGN FLIPS WITH VOCABULARY SIZE -- measured 1.50
    unweighted against 1.85 as used at 512 tokens (reads LOW), and high at pilot vocabularies where most
    entries are long and rare. A biased estimator is survivable; one whose sign depends on the axis you
    are comparing along is not, and VMAX was that axis. The signature width 614 was chosen off it.

    Two len() calls. There is no reason this was ever estimated.

    RAISES rather than returning a placeholder on n_tokens <= 0. A zero-token segment means the tokenizer
    produced nothing for text that exists, which is a defect upstream; returning 1.0 or 0.0 here would
    convert it into a plausible number that flows into the signature width and the coverage report. The
    house rule after 98 wrong-measurement records is that a missing number must be missing, loudly.
    """
    n_t = int(n_tokens)
    if n_t <= 0:
        raise ValueError(f"bytes_per_token: n_tokens={n_tokens!r} -- cannot measure compression over "
                         f"zero tokens. The caller has an empty segmentation, which is the defect.")
    return int(n_bytes) / n_t


def signature_width_bytes(win_tokens, bytes_per_token):
    """The ONE signature window width, in bytes, for the whole run.

    UNIT IN: win_tokens = tokens (the loop stride), bytes_per_token = bytes/token.
    UNIT OUT: bytes.

    CONFIRMED DEFECT THIS REPLACES. The old tree resolved this width in two places from one knob whose
    zero meant two different things:
        self_organize.py:5676  `if SIG_WIN > 0: return SIG_WIN` else `max(WIN, int(WIN * bpt))`  -> 614 B
        self_organize.py:3919  `[-max(1, SIG_WIN):]`                                             ->   1 B
    SIG_WIN defaults to 0. So training characterised each window from 614 bytes and every eval-path
    routing decision -- and therefore every routing, specialization and composition number in every
    report -- was made from ONE BYTE. Nothing failed: every window still produced A signature. There is
    no sentinel in this function for that reason. Zero is not a value with a meaning here; there is one
    width, it is computed from the stride and the measured compression, and both paths call this.

    THE WIDTH MUST TRACK THE STRIDE. The window is a BYTE count while the loop advances win_tokens TOKENS,
    so a width fixed in bytes covers width/(win_tokens x bytes_per_token) of the stream -- and that
    fraction SHRINKS as the tokenizer compresses better. The historical "SIG_WIN=0 means WIN" made the
    width 256 bytes against a stride that grew to 614, so the domain encoder was reading 42% of the
    material it claimed to describe, drifting downward all run, and nobody chose that.

    FIXED FOR THE LIFETIME OF THE RUN, and the caller must keep it so. Recomputing it live as the
    vocabulary grows crashed both pilot arms at the first rekey (windows captured at the old width
    concatenate into a ragged batch -> ValueError), but the crash was the lesser problem: domain
    centroids are MEANS OF ENCODED WINDOWS, so a width that moves mid-run makes signatures taken before
    and after incomparable, and every centroid, radius and boundary test silently straddles two different
    measurements. A width that moves is wrong in principle. Compute once at assemble, wire it, freeze it.

    `max(1.0, bytes_per_token)` and the outer `max(win_tokens, ...)` are both floors that keep the width
    from falling below one loop stride; the first also absorbs a bytes_per_token below 1, which cannot
    happen on UTF-8 but would silently narrow the window if it ever did.
    """
    w = int(win_tokens)
    if w < 1:
        raise ValueError(f"signature_width_bytes: win_tokens={win_tokens!r} -- the loop stride is at "
                         f"least one token, and a width derived from zero stride is the 1-byte defect.")
    return max(w, int(w * max(1.0, float(bytes_per_token))))


# === clocks: the conversions that must exist under a name ========================================

def flush_period(period_steps, batch_w):
    """A cadence written in STEPS, expressed in the FLUSHES the loop body actually counts.

    UNIT IN: period_steps = Steps, batch_w = windows per flush (count).
    UNIT OUT: Flushes.

    THE CONVERSION THAT BIT REPEATEDLY, AND THE MEASUREMENT THAT CAUGHT IT. The capacity valve's block
    sits below the batch early-out, so it runs once per FLUSH while `step` advances once per WINDOW, and
    its clock therefore ticked at 1/BATCH_W the rate GROW_CAP_EVERY is written in. On the lr_pilot
    rehearsal at BATCH_W=16 the population sat pinned at its soft cap for 43,645 real steps while the
    clock read 2,650 against a GROW_CAP_EVERY of 20,000 -- and the valve reported "reached the cap but
    never held it long enough". 2650 x 16 = 42,400: the entire shortfall was the units. GROW_CAP_EVERY
    =20000 silently meant 320,000 steps at BATCH_W=16 and 640,000 at 32, so a knob's meaning depended on
    the batch size.

    TAKES AND RETURNS CLOCK TYPES, NEVER BARE INTS, and that is the whole defence. A bare int carries no
    kind, so `held >= GROW_CAP_EVERY` compares fine no matter which clock `held` counts. Passing a
    Flushes here raises UnitError at the call, which is the failure the old code needed and did not have.

    TRUNCATES rather than rounds (via Clock.convert). A period that truncates fires marginally EARLY; a
    period that rounds up fires late. The defect being repaired was a clock running 16x slow, and biasing
    the repair toward late would be repeating it in miniature.
    """
    if type(period_steps) is not Steps:
        raise UnitError(f"flush_period: period_steps must be Steps, got "
                        f"{type(period_steps).__name__}. A cadence is written in steps; if this value "
                        f"is already in flushes it has been converted twice.")
    w = int(batch_w)
    if w < 1:
        raise UnitError(f"flush_period: batch_w={batch_w!r} -- a flush covers at least one window.")
    period = period_steps.convert(Flushes, per=w)
    # A PERIOD OF ZERO IS NEVER THE ANSWER. It is either `n % 0` -- a crash -- or, on the guard forms
    # that test `period and n % period == 0`, a mechanism that is switched on and never runs, which is
    # the armed-but-inert class (57 records). One flush is the smallest cadence that exists.
    return Flushes(1) if period.n < 1 else period


def flush_period_windows(period_windows, batch_windows):
    """A cadence written in WINDOWS, expressed in the FLUSHES the loop body actually counts.

    UNIT IN: period_windows = Windows, batch_windows = windows per flush (count).
    UNIT OUT: Flushes.

    WHY THIS EXISTS BESIDE `flush_period` RATHER THAN INSIDE IT. The two differ only in the kind they
    accept, and that is the entire point: a conversion has to name BOTH ends or it is not a conversion,
    it is a division. `flush_period` is pinned to Steps by tests/test_derive.py, which asserts that
    `flush_period(Windows(20000), 16)` RAISES -- correctly, because a cadence denominated in optimizer
    steps and one denominated in stream windows are not the same number the moment ACCUM is greater than
    one. Widening `flush_period` to accept either kind would delete that refusal and put the project's
    most repeated defect back with a broader signature.

    WHY THE CADENCES THE COUPLING TABLE CONVERTS ARE WINDOWS AND NOT STEPS. Read from the source rather
    than from the label. self_organize.py advances the loop counter as `i += WIN; step += 1` (:6796 in
    the batch early-out, :7708 at the flush tail), so `step` counts WINDOWS; the management gates above
    the early-out then test `step % MANAGE_EVERY == 0` (:6716, :6764, :6768), which compares that window
    counter against the knob. MANAGE_EVERY is therefore a threshold in windows. The same knob is ALSO
    read below the early-out as `_nbwd % max(1, MANAGE_EVERY // max(1, BATCH_W))` at five sites (:6819,
    :6836, :6961, :6988, :7077, :7325) against `_nbwd`, which counts flushes -- one number compared
    against two clock kinds, in one file, which is the family this module exists to remove. This function
    is that second reading, written down once.

    AND THE ARITHMETIC IS THE HONEST ONE, WHICH `flush_period` IS NOT. `batch_windows` is windows per
    flush; dividing WINDOWS by it yields FLUSHES and the kinds cancel. `flush_period` divides STEPS by
    the same windows-per-flush, which only balances while one step is one window -- true in the shipped
    loop and exactly the identity that made the conflation invisible. Both functions are kept because
    a genuinely step-denominated cadence (an LR-schedule horizon) still needs the first one; nothing in
    spine/assemble.py's table needs it today, and that is stated at the allowlist entry for `Steps`.

    TRUNCATES rather than rounds, and floors at one flush, for the reasons `flush_period` gives: a period
    that rounds up fires late, and the defect being repaired was a clock running 16x slow; a period of
    zero is either `n % 0` or a mechanism that is switched on and never runs (57 armed-but-inert records).
    """
    if type(period_windows) is not Windows:
        raise UnitError(f"flush_period_windows: period_windows must be Windows, got "
                        f"{type(period_windows).__name__}. This cadence is compared against `step`, and "
                        f"`step` advances once per window (`i += WIN; step += 1`); if the value is "
                        f"already in flushes it has been converted twice.")
    w = int(batch_windows)
    if w < 1:
        raise UnitError(f"flush_period_windows: batch_windows={batch_windows!r} -- a flush covers at "
                        f"least one window.")
    period = period_windows.convert(Flushes, per=w)
    return Flushes(1) if period.n < 1 else period



def cadences_that_cannot_fire(run_windows, periods):
    """Which periodic gates are longer than the run, so they can never fire once.

    UNIT IN: run_windows = Windows (the resolved length of the run), periods = {key: Windows}.
    UNIT OUT: [(key, period_n, run_n)], sorted longest period first. Empty means every gate can fire.

    WHY THIS IS A FUNCTION AND NOT A COMMENT. Measured on the shipped defaults, 2026-08-30:
    DATA.stream_bytes=120000, LM.ctx=128, RUN.epochs=1 give AT MOST 937 windows and about 506 at the
    project's own measured 1.85 bytes/token -- and TEN cadence-shaped defaults are longer than that,
    including EVAL.curve_every=2000, so the learning curve is never probed, and OPT.lr_warmup=1000,
    so the run ends INSIDE warm-up. Every cadence carries the old system's value, tuned against
    STREAM_LEN=94000000 and 60k-step runs; stream_bytes carries a smoke-test value. Neither is wrong
    alone. Together they describe a run in which almost nothing happens (ISSUES P1-C11).

    WHAT IT IS FOR IS THE REPORT, NOT THE ARITHMETIC. The check is one comparison; the reason it
    exists is that PLAN's P3 exit criterion is "empty environment, 200 steps, reaches the end", and
    under these defaults a green P3 certifies a system in which every cadenced mechanism fired zero
    times. That is the armed-but-inert family (57 records) arriving through the DEFAULTS rather than
    through a guard -- the one place none of O1-O10, K1-K9 or the census checks looks, because all of
    them read declarations and this is a property of the declared VALUES against a measured length.

    NOT A REFUSAL, AND THAT IS DELIBERATE. A short run is a legitimate thing to ask for; a smoke test
    is supposed to be short. What is not legitimate is a report that cannot tell "the mechanism ran
    and did nothing" from "the mechanism was never reached". So this returns the list and the caller
    states it; it does not raise. The owner decides whether to change the numbers.

    STRICT: a period EQUAL to the run length is reported. A gate fires when `period` windows have
    ELAPSED since it last fired, and `_fired[key]` seeds at the resumed step -- so a period exactly
    equal to the run has one chance, at the final window, and only if nothing rounds against it.
    Reporting it is the honest side of a boundary nobody should have to reason about twice.
    """
    if type(run_windows) is not Windows:
        raise UnitError(f"cadences_that_cannot_fire: run_windows must be Windows, got "
                        f"{type(run_windows).__name__}. The run's length is counted in the same clock "
                        f"the gates are compared against -- `step`, which advances once per window. A "
                        f"Flushes here divides the answer by the batch width and reports gates as "
                        f"reachable that are not.")
    out = []
    for key, period in periods.items():
        if type(period) is not Windows:
            raise UnitError(f"cadences_that_cannot_fire: the period for {key!r} must be Windows, got "
                            f"{type(period).__name__}. Cadences.due refuses the same thing; a gate "
                            f"whose period reaches this function in another kind was never going to "
                            f"be evaluable against the clock either.")
        # A PERIOD OF ZERO OR LESS IS A SENTINEL, AND IT MUST BE REPORTED, NOT SKIPPED. The first
        # version tested only `period >= run`, so a period of 0 fell through and the gate vanished
        # from the audit entirely -- which was found by running the audit against the real resolved
        # defaults and noticing that CKPT.every is 0, so the 'ckpt' gate was silently absent from a
        # list whose entire purpose is naming gates that cannot fire.
        # It is reported with run_windows as 0 to say "this is not a length comparison". ckpt/api.py
        # states what the sentinel means there -- "every == 0 means the only save is the final one
        # plus SIGUSR1" -- which is a legitimate configuration and exactly the kind of thing the
        # report must SAY rather than leave the reader to infer from a missing line.
        if period.n <= 0:
            out.append((key, period.n, 0))
        elif period.n >= run_windows.n:
            out.append((key, period.n, run_windows.n))
    return sorted(out, key=lambda r: (-r[1], r[0]))



def opt_steps_from_windows(run_windows, effective_batch_windows):
    """A run's length in WINDOWS, expressed in the OPTIMIZER STEPS the LR schedule is denominated in.

    UNIT IN: run_windows = Windows, effective_batch_windows = windows per optimizer step (count).
    UNIT OUT: Steps.

    THE ONE CROSS-KIND CONVERSION IN THE TREE THAT HAD NO NAME. units.py::Clock.convert states the rule -- "There
    is no implicit path between kinds ... call the named function in spine.derive that already knows
    the rate, so the conversion exists in one place with a name" -- and opt/api.py said in as many
    words that "no conversion function is needed -- which matters, because spine/derive.py has no
    Windows->Steps function today (verified)". It then wrote one, inline, on bare ints:

        run_steps = max(1, run_windows // d_effective_batch_windows)

    which is a window count divided by windows-per-optimizer-step, unguarded, in a package body. A
    reviewer found the assertion and the line four lines apart. Nothing was numerically wrong -- at
    the shipped batch_windows=1, accum=1 the two counters coincide -- but the whole argument for
    units.py is that a conversion written at its call site is one nobody can audit, and this was the
    only one left.

    WHY IT IS Windows -> Steps AND NOT Windows -> Flushes. `effective_batch_windows` is
    batch_windows x accum: windows per FLUSH times flushes per optimizer STEP. So the divisor spans
    both boundaries at once and the answer is in optimizer steps, which is what the LR horizon needs
    and the only kind units.py permits it -- "Optimizer steps. What the LR schedule's horizon is
    denominated in, and nothing else." Dividing by batch_windows alone would give Flushes and is the
    conflation this module exists against; that path is flush_period_windows and is a different
    function on purpose.

    THE SCALE IS NOT ACADEMIC. At fetch_big.py's own recommended heavy-run command
    (WIN=256 BATCH_W=16 ACCUM=4) the two counters differ by 64x, so a horizon taken in the wrong kind
    puts every learning-rate result under a schedule 64 times longer or shorter than its label. That
    is the family this project has the most records of.

    TRUNCATES and floors at one, for flush_period's reasons: a horizon that rounds up ends the
    schedule after the run, and a horizon of zero is a division by zero in n_cycles.
    """
    if type(run_windows) is not Windows:
        raise UnitError(f"opt_steps_from_windows: run_windows must be Windows, got "
                        f"{type(run_windows).__name__}. The run's length is counted in the clock "
                        f"`step` advances, and a Steps value here has already been converted once.")
    w = int(effective_batch_windows)
    if w < 1:
        raise UnitError(f"opt_steps_from_windows: effective_batch_windows={effective_batch_windows!r} "
                        f"-- an optimizer step covers at least one window. It is batch_windows x "
                        f"accum, and both are floored at 1 by their own declarations.")
    n = run_windows.n // w
    return Steps(1) if n < 1 else Steps(n)


def opt_steps_from_backwards(n_backward, accum):
    """A count of BACKWARD PASSES, expressed in the OPTIMIZER STEPS they were due to produce.

    UNIT IN: n_backward = Backwards, accum = backward passes per optimizer step (count).
    UNIT OUT: Steps.

    THE CONVERSION THE ACCUMULATION INVARIANT WAS WRITING BY HAND. opt/api.py::counters proves
    ISSUES P3-H29 dead with one comparison -- backward over accum against the optimizer-step
    counter -- and it wrote that comparison as

        due_steps = (n_bwd - base_bwd) // divisor
        if due_steps != n_step - base_step:

    on operands deliberately unwrapped to bare ints first, so units.Clock saw neither side. A
    backward-pass count divided by backward-passes-per-optimizer-step IS a Steps count, compared
    against a Steps count, with no kind anywhere in it: the exact shape
    tests/test_ownership.py::check_o11_no_unnamed_clock_arithmetic exists to forbid, inside the
    function whose own docstring calls that comparison "the one invariant that proves the
    accumulation defect is dead". O11 could not see it -- its AST half matches `opt.<clock_lever>`
    attribute operands and both of those are locals -- and THE NUMBER WAS RIGHT at every setting
    anyone drove (accum=1: 1000 backward passes, 1000 steps; accum=4: 52 backward passes, 13
    steps). An inline cross-kind division is a defect even when its number is right, which is the
    whole of units.py::Clock.convert's rule: "There is no implicit path between kinds ... call the
    named function in spine.derive that already knows the rate, so the conversion exists in one
    place with a name."

    ONE BOUNDARY, NOT TWO, AND THAT IS WHY THIS IS NOT opt_steps_from_windows. Three clocks sit
    under an optimizer step and there are two boundaries between them: batch_windows is WINDOWS PER
    FLUSH, and accum is backward passes -- one per flush -- PER OPTIMIZER STEP.
    opt_steps_from_windows starts at the window, two boundaries below the step, so its divisor is
    the PRODUCT of both (`effective_batch_windows = batch_windows x accum`). This one starts at the
    backward pass, ONE boundary below the step, so its divisor is `accum` alone. Handing this
    function the two-boundary divisor is the likeliest way to break the invariant while appearing
    to repair it: at the heavy-run command's batch_windows=16 accum=4 it divides 62 backward passes
    by 64 and reports 0 steps due against the 15 that were taken, so a CORRECT run raises the
    P3-H29 message and the reader is sent after a defect that did not happen.

    IT DOES NOT FLOOR AT ONE, AND opt_steps_from_windows DOES. The difference is HORIZON against
    COUNT and it is not a style choice. A horizon of zero divides by zero in n_cycles and ends the
    schedule before the run, so it is floored; a count of steps due is a MEASUREMENT of what has
    happened, and zero backward passes have produced exactly zero optimizer steps. That is the true
    reading at the first call of every run and the reading the invariant is checked against most
    often -- a floor of one here would make counters() raise "1 optimizer step was due and 0 were
    taken" on a state where nothing has run yet, which is the untrippable-guard family inverted
    into a guard that fires on the empty case.

    TRUNCATES, like every conversion in this file: the backward passes accumulated since the last
    step are not yet a step, and rounding them up would report a step that has not been taken. A
    NEGATIVE count is not refused here, and that is deliberate -- the only way to produce one is the
    caller's own resume subtraction (`n_backward - backward_at_load`), and its invariant reports
    that with both numbers and the boundary they were measured from, which is a better sentence
    than any this function could raise.

    REFUSES ANYTHING BUT A Backwards AT ONE END, exactly as accum_due does and for the same
    measurement: the old gate counted the WINDOW counter and accumulated nothing, 55 optimizer
    steps where 13 were due. REFUSES A DIVISOR BELOW 1 at the other, as flush_period,
    flush_period_windows and opt_steps_from_windows do. accum_due keeps a SILENT `max(1, ...)` on
    the same lever instead, and the asymmetry is recorded rather than tidied away: that clamp
    reproduces the shipped read-site `max(1, _i("ACCUM", 1))` (self_organize.py:4198), which
    opt/levers.py::OPTLevers names as the one surviving guard that "still hides a typo". This is a
    CONVERSION and not a gate, so it refuses like the other three; and opt/api.py::build refuses
    OPT_ACCUM below 1 at startup, so no live run can reach either behaviour with a divisor the
    other would have handled differently.
    """
    if type(n_backward) is not Backwards:
        raise UnitError(f"opt_steps_from_backwards: n_backward must be Backwards, got "
                        f"{type(n_backward).__name__}. Accumulation counts BACKWARD PASSES -- a "
                        f"window counter measured 55 optimizer steps where 13 were due, and a "
                        f"Steps value here is the answer being fed back in as the question.")
    k = int(accum)
    if k < 1:
        raise UnitError(f"opt_steps_from_backwards: accum={accum!r} -- an optimizer step covers at "
                        f"least one backward pass. This divisor is accum ALONE and never "
                        f"batch_windows x accum: that product spans two boundaries and belongs to "
                        f"opt_steps_from_windows, which starts a window lower.")
    return Steps(n_backward.n // k)


def accum_due(n_backward, accum):
    """Is an optimizer step due, given how many BACKWARD PASSES have accumulated?

    UNIT IN: n_backward = Backwards, accum = backward passes per optimizer step (count).
    UNIT OUT: on/off.

    ACCUMULATION COUNTS BACKWARD PASSES. Nothing else is the same number. Gating this on a window counter
    accumulated nothing: measured 55 optimizer steps where 13 were due, i.e. at ACCUM=4 the gate fired on
    essentially every window and the effective batch size was a quarter of the configured one -- while
    the run reported the configured one. Every learning-rate result taken against that configuration was
    taken at a different batch size than its label.

    REQUIRES A Backwards CLOCK, so the window counter cannot be handed to it. `Windows(55)` raises here;
    `55` raises here. That is the point of the argument type -- the old bug was not a wrong formula, it
    was the right formula applied to the wrong counter, and no formula can detect that about its input.

    n_backward = 0 is NOT due: no backward pass has happened, so there is nothing to step on. Stepping at
    zero is how a run takes an optimizer step on an empty gradient before its first batch.
    """
    if type(n_backward) is not Backwards:
        raise UnitError(f"accum_due: n_backward must be Backwards, got {type(n_backward).__name__}. "
                        f"Accumulation counts backward passes -- a window counter measured 55 steps "
                        f"where 13 were due.")
    n = int(n_backward)
    k = max(1, int(accum))
    return n > 0 and n % k == 0


def pin_tick(held, pinned, dstep):
    """Advance the pinned-at-the-cap clock by however many WINDOWS elapsed, not by one per call.

    UNIT IN: held = Windows (the accumulated clock), pinned = on/off, dstep = Windows (the delta).
    UNIT OUT: Windows.

    WINDOWS, NOT STEPS, AND THIS FILE SAID STEPS FOR SIX COMMITS. The kind is settled by units.py's
    own definitions, not by preference: `Steps` is "Optimizer steps. What the LR schedule's horizon
    is denominated in, AND NOTHING ELSE"; `Windows` is "Stream windows. What `step` counts." The
    quantity accumulated here is the delta of the loop counter `step` (`_dstep = step - _pin_prev[0]`
    at the call site), and `step` advances once per WINDOW (`i += WIN; step += 1`,
    self_organize.py:6796 and :7708). So the clock was carrying window deltas under the one kind name
    units.py reserves for something else -- the original conflation, moved from the arithmetic into
    the type that was added to prevent it.

    THE CONTRADICTION THIS RESOLVES, because it was frozen on two surfaces at once.
    src/capacity/levers.py::<module> sets out two legal repairs and records that applying BOTH fires the
    valve 16x too EARLY. capacity/api.py::<module> then froze repair (a) as done -- "pin_tick is re-typed to
    accumulate units.Windows ... NO CONVERSION HAPPENS ANYWHERE" -- while this function still refused
    a Windows, and docs/04_CONTRACT.md stated the same repair as done in one section and proposed in
    another. A P4 implementer following the CAP contract would have written
    pin_tick(held_windows, pinned, elapsed_windows) and got UnitError on the first flush; the only
    non-raising implementation left was `int(held) >= cap.pin_windows`, which capacity/levers.py::<module>
    names as "the original defect again". This is repair (a), applied here, once.

    Repair (b) -- converting the THRESHOLD to Flushes -- stays only in FAB.d_cap_lift_period and
    TOK.d_cap_lift_period, which fabric/api.py::grow_check and tok/api.py::vocab_state._ read for REPORTING beside the
    lift counters, because "0 lifts" cannot otherwise distinguish "never full" from "never
    plateaued". (Those two line numbers were :305 and :313 until 2026-09-03 and had drifted onto
    unrelated prose; the reads are the `_ = fab.d_cap_lift_period` and `_ = tok.d_cap_lift_period`
    lines, which K5 will fail on if either goes.) Nothing compares them against this clock, and
    Windows >= Flushes raises, so both repairs cannot be live in the valve at once by construction
    rather than by discipline. THE REPORTING WIRES ARE NOT PERMANENT: Q-CLOCK-1 is MEASURABLE, and
    the condition that retires both rows -- CAP.counters rendering its block-reason histogram beside
    the pinned high-water mark -- is written out there. The point THIS message makes does not depend
    on them and survives their deletion: do not convert the threshold.

    THE 32 ORACLE CASES ARE UNAFFECTED. They record raw ints in and raw ints out -- the shipped
    function had no types to capture -- so the arithmetic they pin is identical and only the wrapper
    kind changed. That is also the limit of what they prove, and it is stated below.

    IT MUST BE A STEP DELTA AND IT WAS A BARE +1/-1. See flush_period above for the measurement: at
    BATCH_W=16 this ran once per flush while the threshold it feeds is written in steps, so 43,645 real
    steps read as 2,650. Callers convert with flush_period; this function does the accumulation only.

    THIS IS THE PROJECT'S FLAGSHIP UNIT DEFECT AND, UNTIL THIS CHANGE, THE ONE FUNCTION IN THIS FILE WITH
    NO UNIT TYPE AT ALL. flush_period refuses a Flushes and accum_due refuses anything but a Backwards;
    pin_tick accepted whatever it was handed and returned a bare int:

        pin_tick(Flushes(2650), True, Flushes(16))  ->  2666   -- a FLUSH count, labelled windows
        pin_tick(True, 400, 16)                     ->    17   -- the bool/int swap, below

    The first line is the shipped defect reconstructed exactly, inside the function whose own docstring
    describes it: flushes accumulate, the answer comes out kindless, and the threshold comparison that
    was the actual failure site -- `held >= GROW_CAP_EVERY`, 20,000 -- passes on a clock running at
    1/BATCH_W. Now `held` and `dstep` are Windows and so is the answer, so that comparison raises
    UnitError against a Flushes threshold instead of quietly being 16x slow.

    BARE INTS ARE COERCED; FOREIGN CLOCKS RAISE. The 32 captured oracle cases pass plain ints, because the
    shipped function had no types to capture, and refusing them would throw away the only evidence of what
    the old code did. So an int (a bool included -- the capture grid passes True as `held`) is read as
    Windows below, reproducing the shipped `int(...)` truncation, while a Flushes raises. THE TABLE CANNOT
    SEE THIS DISTINCTION: a typed implementation and an untyped one replay all 32 cases identically, so
    the typed smoke assertions in tests/test_derive.py are the only thing covering it. That blind spot is
    named there too.

    ARGUMENT ORDER IS THE SHIPPED ORDER, so the oracle table replays. Note what the oracle's own capture
    grid did with it: it passed the BOOLEAN as `held` and the COUNT as `pinned`, and the function
    accepted that silently and produced a full table of confident answers, because a bool and an int are
    positionally interchangeable here. Typing the clocks does NOT close that one -- `bool` IS an `int`,
    so `pin_tick(True, 400, 16)` still coerces to Windows(1) and still answers 17. It is a live hazard in
    this signature, not a historical one -- call it with keywords.

    Clamped at zero on the way down: an unpinned population that has been unpinned longer than it was
    pinned does not owe the valve negative time.
    """
    # THE EXPLICIT TYPE TEST IS FOR THE MESSAGE, not for the refusal: `Steps(Flushes(2650))` already
    # raises UnitError inside Clock.__init__, but it says only "cannot build Steps from Flushes", which
    # names neither the argument nor the defect. Written out once per clock argument rather than folded
    # into a helper, because flush_period and accum_due each state their type test inline and a reader
    # comparing the three unit-typed functions should meet the same shape three times.
    if isinstance(held, Clock) and type(held) is not Windows:
        raise UnitError(f"pin_tick: held must be Windows, got {type(held).__name__}. This clock "
                        f"accumulates deltas of the loop counter `step`, which advances once per WINDOW, "
                        f"against CAP.pin_windows -- a threshold declared in Windows. A Flushes here is "
                        f"the defect that read 43,645 real ticks as 2,650 at BATCH_W=16. A Steps here is "
                        f"the same defect wearing the kind units.py reserves for the LR horizon and "
                        f"nothing else. Do not convert the threshold either: FAB.d_cap_lift_period and "
                        f"TOK.d_cap_lift_period exist for the REPORT, and applying both repairs at once "
                        f"fires the valve 16x too EARLY (capacity/levers.py::<module>).")
    if isinstance(dstep, Clock) and type(dstep) is not Windows:
        raise UnitError(f"pin_tick: dstep must be Windows, got {type(dstep).__name__}. The delta is how "
                        f"many windows elapsed since the last call, not how many times the loop body ran "
                        f"-- ticking once per flush is precisely how the clock came out 16x slow.")
    # BARE INT -> Windows AT THE BOUNDARY. `Windows(v)` is `int(v)` for anything not already a clock,
    # so this is the shipped `int(held)` / `int(dstep)` truncation unchanged and the 32 oracle cases still
    # replay through it. It is a concession to the captured table, not a general invitation: an int gets
    # in because the oracle predates units, a Flushes does not because it is the bug.
    held = Windows(held)
    dstep = max(Windows(0), Windows(dstep))
    return (held + dstep) if pinned else max(Windows(0), held - dstep)


# === continual learning: the sign the whole claim rests on =======================================

def bwt_of(now, prev):
    """Backward transfer: the mean change on OLD material, on a LOWER-IS-BETTER metric.

    UNIT IN: now, prev = {domain: bits/byte}. UNIT OUT: bits/byte (a difference).

    POSITIVE = WORSE = FORGETTING. NEGATIVE = THE OLD DOMAINS IMPROVED. The sign runs OPPOSITE to the
    continual-learning literature, which reports accuracy, where positive is good -- so anyone reading
    this number against a paper reads it backwards unless the convention is stated at every use.

    THIS SUBTRACTION WAS INVERTED ONCE, on the single line the project's continual-learning claim rests
    on, and it shipped. The reason it shipped is the more important half: selftest.sh only ever asserted
    that the strings "BWT" and "negative = old domains IMPROVED" APPEARED IN THE LOG. A test on the words
    passes whichever way the arithmetic runs. This function exists as a pure function of two dicts so
    that a known-answer table can test the NUMBER, and .rework/oracle/bwt_of.json is that table.

    ONLY DOMAINS PRESENT IN BOTH ENTER THE MEAN. A domain that is new has no baseline to have forgotten
    from, and letting it in makes "we added an area" look like catastrophic forgetting of an area that
    did not exist. Empty intersection returns 0.0, not an error: no shared domains is "no evidence about
    forgetting", and the Reading that carries this number carries its own sample size.

    DOES NOT UNWRAP (mean, err) TUPLES, and the oracle records that it raises TypeError on them. Holdout
    values are otherwise carried in that form throughout the old tree; both call sites happened to unwrap
    with `_ms(...)[0]` first, so the contract was honoured BY CONVENTION AT THE CALL SITE. Preserved as
    captured. The rebuild's Reading type is what actually removes the hazard -- value and error are named
    fields, so no caller has to remember.
    """
    ks = [k for k in now if k in prev]
    if not ks:
        return 0.0
    return sum(now[k] - prev[k] for k in ks) / len(ks)


def forgetting_of(now, best):
    """Forgetting measure F: how far each domain sits above its OWN best, clipped at zero, averaged.

    UNIT IN: now, best = {domain: bits/byte}. UNIT OUT: bits/byte (a non-negative difference).

    CLIPPED AT ZERO IS WHAT SEPARATES F FROM BWT. A domain that improved contributes 0 rather than a
    negative that cancels a real regression elsewhere, so F cannot net a catastrophic loss on one area
    against a gain on another. BWT can, and will, and that is a legitimate difference between the two
    measures rather than a defect in either -- they answer different questions and the report must print
    both or name which one it printed.

    F COMPARES AGAINST THE BEST EVER, NOT THE PREVIOUS PROBE. It therefore differs from BWT exactly when
    a domain peaked earlier than the last probe, which is the common case on a noisy per-process curve.
    Two numbers that agree on the clean case and disagree on the ordinary one are the ones most likely to
    be quoted interchangeably.

    Same shared-key rule and same tuple behaviour as bwt_of; see there. Oracle: forgetting_of.json.
    """
    ks = [k for k in now if k in best]
    if not ks:
        return 0.0
    return sum(max(0.0, now[k] - best[k]) for k in ks) / len(ks)


# === end-of-run verdicts =========================================================================

def curve_verdict(rise_since_min, tail_change, tok_rise,
                  rise_blewup=0.5, flat=0.05, tok_rise_thresh=0.05):
    """Which end-of-run verdict the held-out curve earns. Returns one label; the report supplies prose.

    UNIT IN: rise_since_min, tail_change, flat, rise_blewup = bits/byte; tok_rise, tok_rise_thresh =
    bits/token. UNIT OUT: a label name.

    THIS CASCADE SHIPPED A WRONG VERDICT FOUR TIMES, and every time it ran without error and printed a
    confident sentence:
      - it read its own sign backwards and told a FALLING curve it was rising;
      - it called a run DIVERGING whose last two thirds were flat to -0.007, because it measured only
        from the global minimum;
      - it called a run that lost 1.118 b/B and never recovered PLATEAUED ... nothing is degrading,
        because it then keyed only on the tail;
      - and `tail <= flat` is one-sided, so a curve FALLING at -0.086 was described as "flat since".
    Four wrong verdicts, five thresholds, no test: selftest.sh only ever checked that the SECTION
    APPEARED. Being a pure function of three numbers it is checkable, and curve_test.py holds each of
    those four failures as a known answer.

    TWO QUESTIONS, NOT ONE. The HEIGHT (rise_since_min) says whether the run already fell apart; the TAIL
    (tail_change, over the last two thirds) says whether it still is. A verdict reading only one of them
    gets the other case wrong, which is precisely the history above.

    THE THRESHOLDS ARE KEYWORD PARAMETERS, NOT LEVERS AND NOT MODULE CONSTANTS. In the shipped tree they
    were hard literals (CURVE_RISE_BLEWUP, CURVE_FLAT, CURVE_TOK_RISE at self_organize.py:782-784), never
    `_i(...)` reads, so naming them here creates no second default for any lever. The oracle table was
    captured at 0.5 / 0.05 / 0.05 and replays through the defaults.

    THE FINAL `diverging` IS GUARDED ON THE PER-TOKEN CURVE AGREEING, and that guard is load-bearing
    rather than tidy. The original cascade also required `_fl - _bl > 0.05`; dropping it when this was
    refactored into a function would have made it print DIVERGING for runs the report has always been
    silent about. This is a refactor of a decision, not a change to one.

    Reproduces oracle curve_verdict exactly, branch order included -- the order IS the decision.
    """
    if rise_since_min is None or tail_change is None:
        return "diverging" if tok_rise > tok_rise_thresh else "none"
    if tok_rise > tok_rise_thresh and rise_since_min <= flat:
        return "vocab"          # per-token rose, bits/byte did not: the vocabulary moved, not the model
    if rise_since_min > rise_blewup:
        return "blewup"         # left a level it had reached and stayed off it
    if tail_change < -flat:
        return "recovering"     # still falling: not flat, whatever the height says
    if tail_change <= flat:
        return "plateau"        # genuinely flat
    return "diverging" if tok_rise > tok_rise_thresh else "none"


def blowup_stale(recent, best, since_best, rise=0.5, stale=80):
    """Has this run left a level it reached and stopped coming back?

    UNIT IN: recent = [bits/byte] probes, best = bits/byte, since_best = probes (count),
    rise = bits/byte, stale = probes (count). UNIT OUT: on/off.

    THE FIRST VERSION OF THIS ALARM FIRED ON FOUR RUNS OUT OF FOUR, at steps 8,000-12,000, on runs that
    went on to produce the best held-out number this project has recorded (1.94 b/B). It compared ONE
    probe against the best-so-far and fired at +0.5. That cannot work: the per-process curve genuinely
    wanders by more than that, especially early, and the best-so-far is the running MINIMUM of a noisy
    series, so noise crosses best+0.5 in every healthy run. An alarm that cries wolf is worse than no
    alarm, because it teaches the reader to skip the line that matters. Then the fix over-corrected and
    it could never fire again -- both directions of one threshold being wrong, which is why the oracle
    table for this function is a grid rather than a spot check.

    WHAT ACTUALLY SEPARATES THE TWO, measured across nine real runs, is not the SIZE of the excursion but
    how long the run goes without setting a new best WHILE ELEVATED:

        healthy    sched_ctl 28   sched_step 20   sched_warm 22   sched_both 50   lr_vcap 22  lr_pilot2 11
        blown up   round13 261    0.75 GB 309

    Nothing healthy exceeded 50 probes; neither blow-up came in under 261. `stale=80` sits between them
    with margin on both sides and separates all nine correctly. It is deliberately nearer the healthy
    end's ceiling than the midpoint, because a late alarm costs some wasted steps and a false one costs
    the instrument. Both defaults were hard literals in the shipped tree (BLOWUP_RISE, BLOWUP_STALE at
    self_organize.py:748-749), not levers, so they are not a second default for anything.

    THE MEDIAN of recent probes, not the latest, so a single spike cannot trip it: sched_ctl read 4.82 at
    step 14,000 on one probe and was back to 2.95 at the next.

    Fewer than three probes returns False. Two probes have no median worth the name, and an alarm that
    can fire on the second probe of a run is the 4-of-4 failure again.

    Reproduces oracle blowup_stale exactly, including `sorted(recent)[len(recent) // 2]` -- the UPPER
    median on even-length input, which is the shipped choice.
    """
    if best is None or since_best < stale or len(recent) < 3:
        return False
    mid = sorted(recent)[len(recent) // 2]
    return mid > best + rise


# === the continual-learning schedule shape =======================================================

def phase_schedule(n_areas, n_phases=None, width=None):
    """Who is active in each phase -- GENERATED FROM A RULE, not looked up in a table.

    UNIT IN: n_areas = corpora (count), n_phases = phases (count), width = corpora live at once (count).
    UNIT OUT: list of phases, each a list of area indices.

    A sliding window of `width` areas over `n_areas`, across `n_phases` phases. Every area enters, is
    active for a contiguous stretch, and fades. THE LAST PHASE EXCLUDES AT LEAST ONE AREA whenever
    n_areas > 1, and that is a hard requirement rather than an aesthetic one: `faded` is computed from
    the last phase, so a schedule ending with everything active makes the unlearn-a-faded-area test SKIP
    ITSELF AS VACUOUS -- a test that reports passing because it had nothing to check.

    A RULE, NOT A TABLE. This replaced a per-n lookup table, which replaced a single fixed 4-area list.
    Both were arbitrary in exactly the way the splice itself is arbitrary: WE chose who was active when,
    and then measured the system against our own choice. A rule at least applies the same shape at any n.
    n_areas <= 1 is genuinely stationary and says so -- one corpus cannot have areas enter and fade, so
    the non-stationarity has to come from ADDING an area later, which is the real test anyway.

    WHY THE ARGUMENTS ARE ARGUMENTS. The shipped `_phases` read `_i("PHASES")` and `_i("PHASE_W")` from
    INSIDE its body: a pure-looking generator that reached into the environment. That is the L2 ownership
    violation the rebuild forbids -- the schedule SHAPE is data, and its parameters belong to whichever
    package owns those levers. This is the one intended behavioural difference from the oracle capture,
    which supplied the same values through an explicit reader so the table records defaults rather than
    ambient state.

    The `or` fallbacks reproduce the shipped resolution exactly and are NOT lever defaults: `n_phases or
    4` matches the shipped `p or max(2, PHASES)` for every value the table covers, and the floor of two
    belongs on the lever declaration (one phase cannot have anything fade). `width` falling back to
    (n_areas + 1) // 2 -- half the areas live at once -- is a property of the SHAPE, computed from n, and
    genuinely lives here.

    Reproduces oracle _phases exactly, including `round()`'s banker's rounding on the window position and
    including the fact that a caller-supplied `width` is NOT clamped to n_areas by the first expression
    (only by the `>= n_areas` line below it).

    THE STATIONARY CASE BUILDS INDEPENDENT LISTS. The shipped form was `[[0] if n else []] * p`, which
    aliases ONE list p times: appending to one phase appends to all of them, silently. Equal by value to
    the oracle, so the table still replays; different the moment anyone mutates a phase.
    """
    p = n_phases or 4
    if n_areas <= 1:
        return [([0] if n_areas else []) for _ in range(p)]
    w = width or max(1, min(n_areas, (n_areas + 1) // 2))
    if w >= n_areas:
        w = n_areas - 1                                    # never all-active: something must be able to fade
    out = []
    for i in range(p):
        lo = round(i * (n_areas - w) / max(1, p - 1))      # window slides from the first area to the last
        out.append(list(range(lo, lo + w)))
    return out
