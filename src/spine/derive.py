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
from .units import Backwards, Clock, Epochs, Flushes, Steps, UnitError, Windows


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
    the repair toward late would be repeating it in miniature. That claim rests on the divide being
    EXACT, and until 2026-09-04 it was not: units.py::Clock.convert divided in float, so
    flush_period(Steps(2**53 + 3), 2) came back ONE FLUSH LARGER than the true period -- rounded UP,
    the direction this paragraph refuses. It divides in fractions.Fraction now and truncates once at
    the end; see units.py::Clock.convert, which this function and flush_period_windows are the only
    two callers of.

    REFUSES A NEGATIVE CADENCE AND A NON-int RATE (2026-09-05), which is the family's shape and was
    this function's exception to it. A negative period is not a short period: the floor below --
    written for a cadence that TRUNCATED to zero -- answered Flushes(1) for it, the tightest cadence
    that exists. flush_period_windows carries that measurement because it is the one of the pair
    spine/assemble.py::COUPLINGS calls; this one has no row in the table today, so the arm is
    UNREACHABLE from the composition root and reachable from any direct caller. The rate end is
    type-tested for the reason opt_steps_from_backwards sets out: `int()` is what let the foreign
    kinds in.
    """
    if type(period_steps) is not Steps:
        raise UnitError(f"flush_period: period_steps must be Steps, got "
                        f"{type(period_steps).__name__}. A cadence is written in steps; if this value "
                        f"is already in flushes it has been converted twice.")
    if isinstance(batch_w, Clock):
        raise UnitError(f"flush_period: batch_w={batch_w!r} is a Clock. This argument is a RATE -- "
                        f"windows per flush -- and a rate is a ratio of two kinds, not a count of "
                        f"one. See opt_steps_from_backwards for why every conversion here refuses "
                        f"it: `int()` on a Clock succeeds silently, so the rate is the one argument "
                        f"a foreign kind can enter through. Pass the bare number.")
    if type(batch_w) is not int:
        raise UnitError(f"flush_period: batch_w={batch_w!r} is a {type(batch_w).__name__}. This "
                        f"argument is a RATE and every rate in this file is a COUNT of one kind per "
                        f"another, so it is an int and nothing else. It is TYPE-TESTED rather than "
                        f"read through `int()`, because `int()` is what let the foreign kinds in at "
                        f"this end: it took 16.9 as 16 and '16' as 16 and answered Flushes(1250) for "
                        f"both. See opt_steps_from_backwards for the whole measurement.")
    w = batch_w
    if w < 1:
        raise UnitError(f"flush_period: batch_w={batch_w!r} -- a flush covers at least one window.")
    # THE NEGATIVE SIDE IS REFUSED, NOT FLOORED, and it sits AFTER the rate checks for the reason
    # opt_steps_from_backwards gives about its own order: a caller who got both wrong should hear
    # about the rate first, because a bad rate makes every answer wrong rather than one.
    if period_steps.n < 0:
        raise UnitError(f"flush_period: period_steps={period_steps!r} is negative. A cadence is a "
                        f"count of steps BETWEEN two firings, so a negative one has no reading -- "
                        f"and the floor below would not have said so: it would have answered "
                        f"Flushes(1), the TIGHTEST cadence that exists, for a number nobody could "
                        f"have meant. That floor is for a period that TRUNCATED to zero and nothing "
                        f"else. flush_period_windows carries the measurement, because it is the one "
                        f"of the two that spine/assemble.py::COUPLINGS calls.")
    period = period_steps.convert(Flushes, per=w)
    # A PERIOD OF ZERO IS NEVER THE ANSWER. It is either `n % 0` -- a crash -- or, on the guard forms
    # that test `period and n % period == 0`, a mechanism that is switched on and never runs, which is
    # the armed-but-inert class (57 records). One flush is the smallest cadence that exists.
    # THE TEST STAYS `< 1` AND CAN NOW ONLY SEE 0. The refusals above leave the count non-negative
    # and the rate at or above one, so `period.n` cannot be negative here; the clause fires on a
    # true zero -- a cadence shorter than one flush -- which is the only case the paragraph above
    # ever argued for. It was `< 1` when it also had to swallow negatives, and that is exactly how
    # it came to answer the tightest cadence in the system for a lever set below zero.
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
    The truncation is EXACT at every magnitude as of 2026-09-04 -- units.py::Clock.convert divided in
    float until then, which could round a period UP -- and this function and `flush_period` are that
    method's only two callers in the tree.

    AND THE FLOOR MET A NEGATIVE UNTIL 2026-09-05, WHICH IS NOT WHAT IT WAS FOR. `Flushes(1) if
    period.n < 1` was written for a cadence shorter than one flush; handed a negative it answered
    the same Flushes(1), the TIGHTEST cadence in the system, for a number nobody could have meant.
    THIS ONE WAS LIVE, at build time, through the declared table: FAB_MANAGE_EVERY=-500 built
    FAB.d_manage_period=Flushes(1) and CAP_PIN_WINDOWS=-20000 built FAB.d_cap_lift_period and
    TOK.d_cap_lift_period=Flushes(1), so the management pass and the capacity valve would have run
    every flush of the run. Nothing in the suite tested that value at the time;
    tests/test_fabric.py::check_f8_manage_period_kind_and_refusal, added this round, now stands
    over exactly this path and REPORTS which layer refused -- it names the assembly, which is this
    function inside the FAB.d_manage_period coupling. Nothing upstream
    refuses it -- spine/lever.py::Lever carries a default, a help string, a unit and choices and no
    bound, and spine/lever.py::Lever.coerce resolves an int lever as int(float(raw)), which accepts
    a negative -- and the RATE end of this same function had refused its half of the same shape all
    along: OPT_BATCH_WINDOWS=0 and =-4 both raise UnitError out of spine/assemble.py::build. One
    nonsense number stopped the build; the other became the fastest cadence in the system. Both
    stop it now.
    """
    if type(period_windows) is not Windows:
        raise UnitError(f"flush_period_windows: period_windows must be Windows, got "
                        f"{type(period_windows).__name__}. This cadence is compared against `step`, and "
                        f"`step` advances once per window (`i += WIN; step += 1`); if the value is "
                        f"already in flushes it has been converted twice.")
    if isinstance(batch_windows, Clock):
        raise UnitError(f"flush_period_windows: batch_windows={batch_windows!r} is a Clock. This "
                        f"argument is a RATE -- windows per flush -- and a rate is a ratio of two "
                        f"kinds, not a count of one; `int()` on a Clock succeeds silently. Pass the "
                        f"bare number. See opt_steps_from_backwards.")
    if type(batch_windows) is not int:
        raise UnitError(f"flush_period_windows: batch_windows={batch_windows!r} is a "
                        f"{type(batch_windows).__name__}. This argument is a RATE and a rate here is "
                        f"a COUNT -- windows per flush -- so it is an int and nothing else; `int()` "
                        f"read a float, a str and a bool alike and this function answered all three. "
                        f"See opt_steps_from_backwards.")
    w = batch_windows
    if w < 1:
        raise UnitError(f"flush_period_windows: batch_windows={batch_windows!r} -- a flush covers at "
                        f"least one window.")
    if period_windows.n < 0:
        raise UnitError(f"flush_period_windows: period_windows={period_windows!r} is negative. A "
                        f"cadence is a count of windows BETWEEN two firings and a negative one has "
                        f"no reading. Until 2026-09-05 the floor below answered Flushes(1) for it -- "
                        f"the TIGHTEST cadence that exists -- at BUILD time and through the declared "
                        f"table: FAB_MANAGE_EVERY=-500 built FAB.d_manage_period=Flushes(1), and "
                        f"CAP_PIN_WINDOWS=-20000 built FAB.d_cap_lift_period and "
                        f"TOK.d_cap_lift_period=Flushes(1), so the management pass and the capacity "
                        f"valve would have run every flush of the run. Nothing upstream refuses it: "
                        f"spine/lever.py::Lever carries a default, a help string, a unit and choices "
                        f"and no bound, and spine/lever.py::Lever.coerce resolves an int lever as "
                        f"int(float(raw)), which accepts a negative. The rate end of this same "
                        f"function already refused its half -- OPT_BATCH_WINDOWS=0 and =-4 both "
                        f"raise out of spine/assemble.py::build today -- so one nonsense number "
                        f"stopped the build while the other became the fastest cadence in the system.")
    period = period_windows.convert(Flushes, per=w)
    # `< 1` AND NOT `== 0`, and after the refusal above it can only ever be 0: see flush_period's
    # closing comment, which this function's floor is the same floor as.
    return Flushes(1) if period.n < 1 else period



def run_windows_from_epochs(n_epochs, windows_in_epoch):
    """A run's length in EPOCHS, expressed in the WINDOWS `step` counts.

    UNIT IN: n_epochs = Epochs, windows_in_epoch = windows per epoch (count).
    UNIT OUT: Windows.

    THE LAST UNNAMED CROSS-KIND CONVERSION IN THE TREE, AND IT WAS IN THE COMPOSITION ROOT.
    spine/compose.py::_run_windows resolved the run's length as

        return units.Windows(_windows_in_epoch(sysm) * int(sysm.configs["RUN"].epochs))

    -- windows-per-epoch times a count of EPOCHS, multiplied inline on bare ints and wrapped in the
    answer's kind at the end, which is the shape units.py::Clock.convert refuses ("There is no
    implicit path between kinds ... call the named function in spine.derive that already knows the
    rate, so the conversion exists in one place with a name") and the shape
    tests/test_ownership.py::check_o11_no_unnamed_clock_arithmetic exists to forbid. The number was
    right at every configuration, exactly as opt_steps_from_windows' was, and that is the point of
    the rule rather than an argument against it.

    WHY O11 DID NOT CATCH IT, WHICH IS WORTH MORE THAN THE DEFECT. Three independent reasons, any
    one of which is enough: the check drops `src/spine/` twice (its `_PKG_DIRS` subtracts "spine"
    and its module loop skips `src/spine/`, on the ground that derive IS the named conversion and
    must do the arithmetic); its AST half matches an operand that is an ATTRIBUTE whose name is one
    of the OWNING package's clock levers, and both operands there are Calls; and `epochs` is RUN's
    lever, while the file doing the arithmetic belongs to a package with no levers.py at all. The
    exemption is the deliberate one -- this file must multiply and divide -- but it exempts the
    composition root along with the conversions, and the root is the one other place in the tree
    that legitimately holds two packages' clocks at once.

    THE Q RECORDED HERE UNTIL 2026-09-04 WAS "whether O11's skip should be narrowed from
    `src/spine/` to `src/spine/derive.py`", AND THE ANSWER IS NOW MEASURED: narrowing it is
    NECESSARY AND NOT SUFFICIENT, so a reader who makes that one edit and sees green will believe a
    hole is closed that is not. On a scratch tree with the skip narrowed to this file alone and the
    inline multiply put back into spine/compose.py::_run_windows, tests/test_ownership.py reports
    "PASS O11" -- four lines under the skip the loop reads `mine = clocks.get(pkg, set())` and then
    `if not mine: continue`, and src/spine has no levers.py, so the composition root is dropped a
    second time. Two further changes are needed: a clock set for "spine" (the union of every
    package's, the root being the one file that holds them all at once), and an operand test that
    finds a clock-lever Attribute ANYWHERE IN THE OPERAND SUBTREE rather than only at its root,
    because both operands of that multiply are Calls and the textual half wants a bare identifier
    immediately before the operator. The narrowed skip must also keep exempting
    spine/assemble.py, whose COUPLINGS computes scale clock levers by design. Measured both ways on
    the scratch tree: with the three changes O11 FAILS naming the inline multiply and PASSES on the
    tree as it stands. spine/compose.py::_run_windows carries the same finding from the other end.
    It is still the ownership pass's call and not this file's; what is no longer recorded here is a
    remedy nobody ran.

    EPOCHS -> WINDOWS AND NOT EPOCHS -> STEPS, though the horizon eventually wants Steps. Two
    boundaries separate an epoch from an optimizer step and they are crossed by two different
    rates: this one is windows per epoch, MEASURED on the segmentation that exists
    (len(Segmentation.ids) // LM.ctx, spine/compose.py::_windows_in_epoch), and the next is
    windows per optimizer step, which is opt_steps_from_windows' divisor. Folding them into one
    call would put a measured quantity and a configured one under one rate, which is how
    `STREAM_LEN // WIN` came to divide a BYTE budget by a TOKEN window and overstate the step count
    by the whole compression ratio.

    NO FLOOR, AND THAT IS THE SAME RULING opt_steps_from_backwards MAKES rather than the one
    opt_steps_from_windows makes. `windows_in_epoch` is already floored at one by its own producer,
    so the only way to reach zero here is RUN_EPOCHS=0 -- which train/api.py::startup_refusals
    REFUSES with a sentence and deliberately does not clamp, "because a clamp makes the banner
    print a number the run did not use". A floor here would restore exactly that clamp one file
    away from the refusal, and it would be invisible: the run would report one epoch's worth of
    windows for a run configured to make no passes.

    AND THE CLAMP IS RESTORED FURTHER DOWN THIS FILE, WHICH THIS PARAGRAPH USED TO CALL A REFUSAL.
    It ended "the zero horizon that would divide by zero in n_cycles is already refused where it
    matters" until 2026-09-05. opt_steps_from_windows does not refuse a zero: it FLOORS its answer
    at one Step, two functions below the paragraph above arguing that a floor is not a refusal --
    and this tree holds those two words apart on purpose, train/api.py::startup_refusals refusing
    RUN_EPOCHS=0 rather than clamping it to 1 and saying so in the refusal string it returns.
    MEASURED end to end, with
    capacity/api.py::startup_refusals stubbed to [] so the walk gets past the P4 blocker:
    RUN_EPOCHS=1 -> Windows(634) -> Steps(634); RUN_EPOCHS=0 -> Windows(0) -> Steps(1). So the
    honest statement is that the zero horizon cannot divide by zero in n_cycles BECAUSE a floor
    one function away turns it into a one-step schedule, and a run configured to make no passes
    reaches OPT as a run of one optimizer step. This function keeps its half of that: it reports
    the zero it was handed.

    A NEGATIVE COUNT IS REFUSED (2026-09-05), AND A REFUSAL IS NOT THE FLOOR THIS PARAGRAPH
    REJECTS. Minus one pass over the stream has not happened, so there is no number of windows to
    answer for it -- the ruling opt_steps_from_backwards makes at its own count end, for a count of
    events that did not occur. Epochs(0) still answers Windows(0). THIS IS NOT DEFENCE IN DEPTH
    BEHIND AN UPSTREAM THAT ALREADY REFUSES, and the measurement is what says so:
    train/api.py::startup_refusals tests `epochs < 1`, so it does append a refusal string for a
    negative, but that string is RETURNED -- nothing in src/ raises on System.refusals, and
    spine/compose.py::compose collects it and keeps building. With CAP's stub returning [],
    RUN_EPOCHS=-1 built Windows(-634) here and OPT's horizon came out Steps(1): a
    one-optimizer-step LR schedule for a run configured to make minus one pass, with the refusal
    sitting unread in the same System. WHERE THE ARM STANDS TODAY, NAMED RATHER THAN ASSUMED: the
    first call is spine/compose.py::_run_windows inside the OPT.build row, and
    capacity/api.py::startup_refusals raises NotImplementedError one row earlier, so on the tree as
    it stands this refusal is UNREACHABLE through the composition root and reachable from any
    direct caller.

    REFUSES A Clock AS THE RATE, like every conversion in this file: `windows_in_epoch` is a RATIO
    of two kinds and not a count of one, and `int()` on a Clock succeeds silently. See
    opt_steps_from_backwards for the measurement that argument opened.
    """
    if type(n_epochs) is not Epochs:
        raise UnitError(f"run_windows_from_epochs: n_epochs must be Epochs, got "
                        f"{type(n_epochs).__name__}. An epoch is a pass over the stream, not a "
                        f"count of anything the loop compares against -- units.py::Epochs exists "
                        f"so that `epochs >= some_step_threshold` raises, which is the comparison "
                        f"that made EPOCHS set the run length AND the cosine horizon at once.")
    if isinstance(windows_in_epoch, Clock):
        raise UnitError(f"run_windows_from_epochs: windows_in_epoch={windows_in_epoch!r} is a "
                        f"Clock. This argument is a RATE -- windows per epoch -- and a rate is a "
                        f"ratio of two kinds, not a count of one. `int()` on a Clock succeeds, so "
                        f"the divisor is the one argument a foreign kind can enter a conversion "
                        f"through. Pass the bare number.")
    if type(windows_in_epoch) is not int:
        raise UnitError(f"run_windows_from_epochs: windows_in_epoch={windows_in_epoch!r} is a "
                        f"{type(windows_in_epoch).__name__}. This argument is a RATE and a rate "
                        f"here is a COUNT -- windows per epoch -- so it is an int and nothing "
                        f"else. `int()` accepted '10' and answered Windows(30) for a value that "
                        f"never went through spine/lever.py::Lever.coerce. See "
                        f"opt_steps_from_backwards.")
    w = windows_in_epoch
    if w < 1:
        raise UnitError(f"run_windows_from_epochs: windows_in_epoch={windows_in_epoch!r} -- an "
                        f"epoch covers at least one window. spine/compose.py::_windows_in_epoch "
                        f"floors it at 1 for the same reason: an epoch of zero windows is a "
                        f"segmentation shorter than one context, which is a data failure and not "
                        f"a run length.")
    if n_epochs.n < 0:
        raise UnitError(f"run_windows_from_epochs: n_epochs={n_epochs!r} is negative. An Epochs "
                        f"counts passes over the stream and minus one pass has not happened, so "
                        f"there is no number of windows to answer for it -- the ruling "
                        f"opt_steps_from_backwards makes at its own count end, and NOT a floor: "
                        f"Epochs(0) still answers Windows(0), which is the property this function "
                        f"exists to keep. THIS IS NOT DEFENCE IN DEPTH. train/api.py::"
                        f"startup_refusals does test epochs < 1, so it appends a refusal string "
                        f"for a negative -- but the string is RETURNED, nothing in src/ raises on "
                        f"System.refusals, and spine/compose.py::compose collects it and keeps "
                        f"building: with capacity/api.py::startup_refusals stubbed to [] so the "
                        f"walk gets past the P4 blocker, RUN_EPOCHS=-1 built Windows(-634) here "
                        f"and OPT's horizon came out Steps(1), a one-optimizer-step LR schedule "
                        f"for a run configured to make minus one pass, with the refusal sitting "
                        f"unread in the same System.")
    return Windows(n_epochs.n * w)


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

    THE FLOOR KEEPS THE ZERO AND NO LONGER SEES A NEGATIVE (2026-09-05), and those are two rulings
    rather than one. Windows(0) -> Steps(1) is the floor the line above argues for. Windows(-634)
    -> Steps(1) was the SAME answer for a length that is not a short run but not a run at all --
    measured, from RUN_EPOCHS=-1 arriving through spine/compose.py::_run_windows -- so a
    one-optimizer-step horizon was the reported answer for a negative run length, which is also the
    answer for a zero-window run and for a 63-window run at the heavy-run command's divisor of 64.
    The count end refuses the negative now; the zero is still floored, and this docstring is where
    that difference is stated.
    """
    if type(run_windows) is not Windows:
        raise UnitError(f"opt_steps_from_windows: run_windows must be Windows, got "
                        f"{type(run_windows).__name__}. The run's length is counted in the clock "
                        f"`step` advances, and a Steps value here has already been converted once.")
    if isinstance(effective_batch_windows, Clock):
        raise UnitError(f"opt_steps_from_windows: effective_batch_windows="
                        f"{effective_batch_windows!r} is a Clock. This argument is a RATE -- "
                        f"batch_windows x accum, windows per optimizer step -- and a rate is a "
                        f"ratio of two kinds, not a count of one; `int()` on a Clock succeeds "
                        f"silently. Pass the bare number. See opt_steps_from_backwards.")
    if type(effective_batch_windows) is not int:
        raise UnitError(f"opt_steps_from_windows: effective_batch_windows="
                        f"{effective_batch_windows!r} is a "
                        f"{type(effective_batch_windows).__name__}. This argument is a RATE and a "
                        f"rate here is a COUNT -- batch_windows x accum, windows per optimizer "
                        f"step -- so it is an int and nothing else. See opt_steps_from_backwards.")
    w = effective_batch_windows
    if w < 1:
        raise UnitError(f"opt_steps_from_windows: effective_batch_windows={effective_batch_windows!r} "
                        f"-- an optimizer step covers at least one window. It is batch_windows x "
                        f"accum, and both are floored at 1 by their own declarations.")
    if run_windows.n < 0:
        raise UnitError(f"opt_steps_from_windows: run_windows={run_windows!r} is negative. A run's "
                        f"length is a count of windows the stream will yield, and a negative one "
                        f"is not a short run, it is not a run. The floor below answered Steps(1) "
                        f"for it -- the SAME answer it gives a zero-window run -- so a horizon of "
                        f"one optimizer step was reported for a negative run length: measured from "
                        f"RUN_EPOCHS=-1, which reaches here as Windows(-634) through "
                        f"spine/compose.py::_run_windows. The zero is floored and the negative is "
                        f"refused, and those are two rulings, not one.")
    n = run_windows.n // w
    # `< 1` CAN NOW ONLY SEE 0, for the reason flush_period's closing comment gives: the refusal
    # above leaves the count non-negative and the rate at or above one. The floor that remains is
    # the one this docstring argues for -- a horizon of zero divides by zero in n_cycles.
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
    step are not yet a step, and rounding them up would report a step that has not been taken. THAT
    RULE ONLY EVER HAD A NON-NEGATIVE DOMAIN and until 2026-09-04 this function did not say so. A
    Backwards is a count of events that HAPPENED; -3 backward passes have not happened, and there
    is no honest number of optimizer steps to answer for them.

    A NEGATIVE COUNT IS NOW REFUSED, AND THE ROUNDING REPAIR IS WHY (2026-09-04, twice in one day).
    The paragraph above used to end: "A NEGATIVE count is not refused here, and that is deliberate
    -- the only way to produce one is the caller's own resume subtraction (`n_backward -
    backward_at_load`), and its invariant reports that with both numbers and the boundary they were
    measured from, which is a better sentence than any this function could raise." THE PREMISE OF
    THAT SENTENCE WAS MEASURED AND IT IS FALSE. The body then read `n // k`, which FLOORS on a
    negative operand, and floor(n/k) is at most -1 for EVERY n < 0: so every negative delta came
    back non-zero, opt/api.py::counters compared it against a `taken` of Steps(0) and raised. The
    detection the docstring credited to the caller was a SIDE EFFECT OF THE ROUNDING THE SAME
    DOCSTRING CALLED WRONG. Correcting the rounding to truncation -- correct AS ROUNDING, for the
    reason in the sentence above, a partial step is not a step in either direction -- turned every
    deficit of 1 to k-1 backward passes into Steps(0) against Steps(0) and counters() said NOTHING.
    Measured at accum=4, n in (-9,-8,-5,-4,-3,-2,-1) answered (-3,-2,-2,-1,-1,-1,-1) under floor
    and (-2,-2,-1,-1,0,0,0) under truncation: the three states -1, -2, -3 stopped raising, and at
    accum=8 that silent window is seven wide. n_backward going BACKWARDS across a resume was
    checked by that accident and by nothing else in the tree.

    SO THE REPAIR IS TO THE DOMAIN AND NOT TO THE ROUNDING, WHICH IS HOW BOTH HOLD AT ONCE. The
    negative side is refused outright at EVERY magnitude, and that is WIDER than floor's accident
    rather than equal to it: floor was detected through a COMPARISON, `due != taken`, so a resume
    that lost 4 backward passes AND one optimizer step at accum=4 gave due=Steps(-1) against
    taken=Steps(-1) and compared equal, while a refusal fires on the count itself and cannot be
    cancelled by a second regression on the other side. The accepted domain is
    n >= 0, where `//` IS truncation, so the body and this docstring cannot disagree again and the
    hand-written sign split that the rounding repair introduced is gone with the branch it served.
    Positive counts are untouched: at accum=4, 0,1,3 -> 0; 4,7 -> 1; 8 -> 2; 52 -> 13. No live
    run's number moves.

    AND THE NEGATIVE REFUSAL IS NOW THE FAMILY'S, NOT THIS FUNCTION'S ALONE (2026-09-05). It stood
    here and nowhere else for a day, and the other four conversions answered a negative count two
    other ways: run_windows_from_epochs PASSED IT THROUGH (Epochs(-1) x 10 -> Windows(-10)),
    while flush_period, flush_period_windows and opt_steps_from_windows FLOORED it at one -- the
    tightest cadence and the shortest horizon that exist, which is the armed-but-inert class
    inverted into fires-every-flush. Two of those were LIVE at build time through
    spine/assemble.py::COUPLINGS: FAB_MANAGE_EVERY=-500 built FAB.d_manage_period=Flushes(1), and
    CAP_PIN_WINDOWS=-20000 built FAB.d_cap_lift_period and TOK.d_cap_lift_period=Flushes(1). All
    four refuse now, and the GATE does not: accum_due answers False for a negative count, which is
    the same conversion/gate split this docstring already draws at the rate end and which
    tests/test_derive.py::smoke pins.

    THE REFUSAL IS REACHABLE, AND IT IS NOT A GUESS ABOUT THE CALLER. opt/api.py::load_state stamps
    `opt.ckpt.backward_at_load = int(st.n_backward)` AFTER the restore, so the base equals the live
    counter at the boundary; opt/api.py::scaled_backward is the only writer afterwards and it only
    adds `U.Backwards(1)`. `st.n_backward - U.Backwards(base_bwd)` in opt/api.py::counters is
    therefore non-negative in every sound process, and a negative one is a defect with no second
    reading -- which is exactly what makes refusing it a DETECTION and not a narrowing.

    WHAT THE REFUSAL COST FOR ONE DAY, AND HOW IT WAS PAID. At a deficit of k or more, counters()
    used to reach its own ValueError and print base_bwd, base_step and both live counters; from
    2026-09-04 it stopped one line earlier, in this function, which does not hold those numbers.
    The message below names the FOUR counter keys instead so the reader can fetch them -- opt.ckpt.backward_at_load
    and opt.ckpt.step_at_load against opt.backward and opt.step, two bases and two live counters,
    which is what it takes to read the fault. The sentence WITH the numbers
    in it belongs beside base_bwd in opt/api.py::counters -- `if int(st.n_backward) < base_bwd:`
    raising before the conversion is called -- because this file owns the conversion and not the
    resume. IT IS THERE AS OF 2026-09-05: opt/api.py::counters tests `int(st.n_backward) <
    base_bwd` and raises with all four numbers before this function is reached, so the caller that
    HAS the bases reports them. AND THAT MAKES THE ARM BELOW UNREACHABLE FROM src/ TODAY, WHICH IS
    SAID HERE RATHER THAN LEFT TO BE FOUND: opt/api.py::counters holds the ONLY call to this
    function in the tree, so with its guard one line earlier the refusal below now fires for
    tests/test_derive.py::smoke and for a caller nobody has written yet. It is kept, and not as
    politeness: this is the DETECTION, at the count, where no second regression can cancel it, and
    it is the half that does not depend on a caller having stamped a base. The other half is the
    REPORTING, which needs two bases this file has never been handed. A conversion that answers a
    number for a count of events that did not happen is the defect; that it is currently shadowed
    by a better message is a property of one caller, not of the rule.

    REFUSES A Clock AS ITS DIVISOR (added 2026-09-04), and that hole is worth naming because it is
    the general one. Every conversion in this file refuses a foreign kind at the CLOCK end and
    every one of them then wrote `int(rate)` at the other, where units.Clock's own __int__ and
    __index__ make the read succeed: opt_steps_from_backwards(Backwards(52), Windows(4)) returned
    Steps(13), so a Windows crossed a function whose first act is to refuse a Windows. The divisor
    is a RATE -- a ratio of two kinds -- and no count of one kind is ever the right value for it,
    which is why the repair is a refusal and not a conversion. The same lines are now in
    flush_period, flush_period_windows, opt_steps_from_windows, run_windows_from_epochs and
    accum_due, written out at each rather than folded into a helper for the reason pin_tick gives
    about its own two type tests.

    AND THE Clock REFUSAL WAS HALF OF THAT HOLE (2026-09-05). `int(rate)` admits everything int()
    admits, not only a Clock, so the same argument that refuses a Windows here refuses these too:
    flush_period(Steps(20000), 16.9) answered Flushes(1250) for a rate 6% off; this function
    answered Steps(13) for accum=4.9 and for accum='4'; run_windows_from_epochs(Epochs(3), '10')
    answered Windows(30) for a value that never went through spine/lever.py::Lever.coerce, which
    resolves an int lever as int(float(raw)) and cannot hand a str to anything; and a bool arrived
    as a rate of one, so flush_period(Steps(20000), True) answered Flushes(20000). Worst at the
    ends: nan and inf left through ValueError and OverflowError out of int() itself, so two rate
    values escaped this family's own exception type -- the same two values, at the same argument,
    that units.py::Clock.convert stopped letting past on 2026-09-04. THE FIX IS THE SHAPE THE CLOCK
    END HAS ALWAYS HAD: `type(rate) is not int`, an exact type test, which also refuses a bool
    because bool is an int subclass and the clock end refuses True by the same construction. IT
    DOES NOT NARROW units.py::Clock.convert, whose `per` is the GENERAL rate and stays fractional
    (tests/test_derive.py::smoke pins Flushes(250).convert(Steps, per=Fraction(1, 16)) as
    Steps(4000)); every rate in THIS file is declared a count in its own UNIT IN line and arrives
    from an int Lever.

    REFUSES ANYTHING BUT A Backwards AT ONE END, exactly as accum_due does and for the same
    measurement: the old gate counted the WINDOW counter and accumulated nothing, 55 optimizer
    steps where 13 were due. REFUSES A DIVISOR BELOW 1 at the other, as flush_period,
    flush_period_windows, opt_steps_from_windows and run_windows_from_epochs all do -- FOUR, not
    the three this sentence named until 2026-09-05; run_windows_from_epochs has refused a rate
    below one since it was written and was left out of the list. accum_due keeps a `max(1, ...)`
    on the same lever instead, and the asymmetry is recorded rather than tidied away: that clamp
    reproduces the shipped read-site `max(1, _i("ACCUM", 1))` (self_organize.py:4198), which
    opt/levers.py::OPTLevers names as the one surviving guard that "still hides a typo". It was
    SILENT in the sense that mattered -- argued for HERE and in accum_due's own refusal message,
    and nowhere in accum_due's docstring, which is where a reader of accum_due looks -- and that is
    repaired at accum_due as of 2026-09-05 rather than by moving the clamp. This is a CONVERSION
    and not a gate, so it refuses like the other four; and opt/api.py::build refuses OPT_ACCUM
    below 1 at startup, so no live run can reach either behaviour with a divisor the other would
    have handled differently.
    """
    if type(n_backward) is not Backwards:
        raise UnitError(f"opt_steps_from_backwards: n_backward must be Backwards, got "
                        f"{type(n_backward).__name__}. Accumulation counts BACKWARD PASSES -- a "
                        f"window counter measured 55 optimizer steps where 13 were due, and a "
                        f"Steps value here is the answer being fed back in as the question.")
    if isinstance(accum, Clock):
        raise UnitError(f"opt_steps_from_backwards: accum={accum!r} is a Clock. This divisor is a "
                        f"RATE -- backward passes per optimizer step -- and a rate is a RATIO of "
                        f"two kinds, not a count of one, so no Clock can be the right value for it. "
                        f"It is refused rather than read because `int()` on a Clock SUCCEEDS: "
                        f"units.Clock declares __int__ and __index__, so `int(Windows(4))` is 4 and "
                        f"this function would have answered Steps(13) for "
                        f"opt_steps_from_backwards(Backwards(52), Windows(4)) -- the kind refused "
                        f"at the other end, entering through the one argument that had none. Pass "
                        f"the bare number.")
    if type(accum) is not int:
        raise UnitError(f"opt_steps_from_backwards: accum={accum!r} is a {type(accum).__name__}. "
                        f"This divisor is a RATE and a rate here is a COUNT -- backward passes per "
                        f"optimizer step -- so it is an int and nothing else. The Clock refusal "
                        f"above was HALF the hole: `int()` admits every type it admits, so 4.9 came "
                        f"back Steps(13) for a rate that is not a rate, '4' came back Steps(13) for "
                        f"a value that never went through spine/lever.py::Lever.coerce, and nan and "
                        f"inf left the family through ValueError and OverflowError rather than "
                        f"UnitError. The clock end has always been type-tested; this end is now too.")
    k = accum
    if k < 1:
        raise UnitError(f"opt_steps_from_backwards: accum={accum!r} -- an optimizer step covers at "
                        f"least one backward pass. This divisor is accum ALONE and never "
                        f"batch_windows x accum: that product spans two boundaries and belongs to "
                        f"opt_steps_from_windows, which starts a window lower.")
    # THE NEGATIVE SIDE IS REFUSED, NOT ROUNDED, and it sits AFTER the divisor checks on purpose:
    # this message names accum, and a caller who got both wrong should hear about the rate first,
    # because a bad rate makes every answer wrong rather than one.
    n = n_backward.n
    if n < 0:
        raise UnitError(f"opt_steps_from_backwards: n_backward={n_backward!r} is negative. A "
                        f"Backwards counts backward passes that HAPPENED, so there is no number of "
                        f"optimizer steps to answer for a negative one. The only route here is "
                        f"opt/api.py::counters' resume subtraction `st.n_backward - "
                        f"U.Backwards(base_bwd)`, whose base is stamped FROM st.n_backward by "
                        f"opt/api.py::load_state AFTER the restore, and opt/api.py::scaled_backward "
                        f"only ever adds one -- so this says the backward counter went BACKWARDS "
                        f"across a resume by {-n} pass(es), measured at accum={k}. The four numbers "
                        f"are opt.ckpt.backward_at_load and opt.ckpt.step_at_load against "
                        f"opt.backward and opt.step. Until 2026-09-04 this was caught only as a "
                        f"SIDE EFFECT of `//` flooring: floor(n/k) is at most -1 for every n < 0, "
                        f"so no deficit came back as zero and opt/api.py::counters raised on the "
                        f"comparison. Being a comparison is what made it weak -- a resume that "
                        f"lost accum backward passes AND one optimizer step gave due == taken and "
                        f"cancelled it -- and the same-day repair from flooring to TRUNCATION then "
                        f"removed even that, answering Steps(0) for every deficit smaller than "
                        f"accum. It is checked here now, on the count itself, at every magnitude.")
    # `//` IS TRUNCATION ON THE DOMAIN THIS FUNCTION ACCEPTS. The refusal above leaves n >= 0, where
    # floor and truncation are one operation, so the docstring's TRUNCATES and this line agree by
    # construction and not by a hand-written sign split -- the split that briefly stood here was
    # correct arithmetic over a domain that should never have been admitted. Integer `//` and not
    # `int(n / k)`: float division loses exactness above 2**53 and a backward count is unbounded.
    return Steps(n // k)


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

    THE RATE IS CLAMPED HERE AND REFUSED IN opt_steps_from_backwards, AND THAT ASYMMETRY IS
    DELIBERATE -- STATED HERE FROM 2026-09-05, having lived only in the other function's docstring
    and in this one's own refusal message, which is not where a reader of accum_due looks.
    `k = max(1, int(accum))` below reproduces the shipped read-site `max(1, _i("ACCUM", 1))`
    (self_organize.py:4198), which opt/levers.py::OPTLevers names as the one surviving guard that
    still hides a typo. opt_steps_from_backwards is a CONVERSION and refuses a rate below one; this
    is a GATE and answers one. Neither reading is silent any more: opt/api.py::build refuses
    OPT_ACCUM below 1 at startup with its own sentence, so no live run reaches either behaviour,
    and tests/test_derive.py::smoke pins all three answers -- accum_due(Backwards(52), 0) is True,
    accum_due(Backwards(52), -4) is True, accum_due(Backwards(-4), 4) is False -- so the difference
    is a decision on the record rather than one nobody noticed. THE CLAMP IS ABOUT THE VALUE AND
    NOT THE KIND, which is why two refusals sit above it: a Clock rate, and any rate that is not an
    int. No clamp can repair a kind.

    A NEGATIVE COUNT IS ANSWERED, NOT REFUSED, AND THAT IS THE OTHER HALF OF THE SAME SPLIT. `n > 0`
    is False at Backwards(-4), so this gate says no step is due where opt_steps_from_backwards
    raises. A gate is asked a yes/no question about the state it is handed, and "no step is due" is
    a true answer for a state that cannot have accumulated one; a conversion is asked for a NUMBER,
    and there is no honest number of optimizer steps for minus four backward passes. All FIVE
    conversions in this file refuse a negative count as of 2026-09-05 -- flush_period,
    flush_period_windows, run_windows_from_epochs, opt_steps_from_windows and
    opt_steps_from_backwards; this gate is the one that does not, on purpose.
    """
    if type(n_backward) is not Backwards:
        raise UnitError(f"accum_due: n_backward must be Backwards, got {type(n_backward).__name__}. "
                        f"Accumulation counts backward passes -- a window counter measured 55 steps "
                        f"where 13 were due.")
    if isinstance(accum, Clock):
        raise UnitError(f"accum_due: accum={accum!r} is a Clock. This is a RATE -- backward passes "
                        f"per optimizer step -- and a rate is a ratio of two kinds, not a count of "
                        f"one; `int()` on a Clock succeeds silently, so it is refused here as it is "
                        f"in opt_steps_from_backwards. THE max(1, ...) BELOW IS UNTOUCHED and is "
                        f"still the shipped read-site clamp: this refusal is about the KIND, which "
                        f"no clamp can repair, and not about the value.")
    if type(accum) is not int:
        raise UnitError(f"accum_due: accum={accum!r} is a {type(accum).__name__}. This is a RATE "
                        f"and a rate here is a COUNT -- backward passes per optimizer step -- so "
                        f"it is an int and nothing else. THE max(1, ...) BELOW IS UNTOUCHED BY "
                        f"THIS TOO: a clamp is about the VALUE and this is about the TYPE, and "
                        f"`int()` read 4.9 and '4' as 4 and this gate answered True for both. See "
                        f"opt_steps_from_backwards.")
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
