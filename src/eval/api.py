"""EVAL -- the frozen public surface. Signatures only; P4/P5/P6 write the bodies.

EVAL owns EVERYTHING THAT MEASURES THE RUN AND NOTHING THAT CHANGES IT -- the instrument line.
Several knobs arrive here from the packages they grade (aff_min from the fabric, verify_fit_steps
from the store, genuine_min/genuine_sil from `misc`) for one reason: a threshold that only shapes a
PRINTED number must not ride in the Config a mechanism receives, or the fabric grades its own
affiliation report. Against goal A it is gen_* and coh_*; against goal B it is holdout_windows, the
only instrument that answers "did adding an area damage what was already known". Every lever here
is a sample size or a threshold, because both project goals are CLAIMS and a claim is only as good
as the instrument under it.

WHICH OF THESE ARE LIVE AT WHICH PHASE, STATED RATHER THAN IMPLIED. At P3 exactly one function
below was called by the composition root: curve_period, because the loop needs a cadence slot.
SINCE 2026-09-27 (Proposal 04 SR0 and NEW-03, Q-EVAL-12) THE RETENTION PROBE IS BUILT, OFF at the
shipped EVAL_RETENTION_EVERY=0: pin_holdout at the root's 'probe' row, retention_period in its
cadence mapping, holdout_probe at stage B, at R and at a resume's start, blowup after each B
reading, and generate after the final save. curve_probe and null_excess are still P5, and four of
the five instruments at the bottom are P6. THEY ARE DECLARED HERE ANYWAY, and that is a deliberate
choice this contract records: an instrument declared with a signature has a named reader for its
levers, so `EVAL_COH_LEN` is a knob whose consumer is written down rather than one of the 57
armed-but-inert records. What P6 owns is the BODY, not the interface.

THE SIX STUB MARKERS BELOW SAY P5/P6 WHILE THE OTHER TWELVE PACKAGES SAY P4, AND THEY STAY THAT
WAY. RE-CHECKED 2026-09-04 AND THE RULING STILL HOLDS: .rework/ISSUES.md P2-H11 rules that the
PHASES renumber and the markers do not, that eval's markers move WITH the renumbering, and that the
renumbering is deliberately NOT YET APPLIED because it touches every row below P2 while the phase
in flight is P4 under the split numbering. Counted rather than assumed: two stub markers here
name phase P5 -- curve_probe, null_excess -- and four name P6 -- coherence, verdicts,
wrongness_probe, verification_fit -- against the P4 marker the other twelve api.py files carry, and
docs/04_CONTRACT.md's EVAL section attributes the SAME P5/P6 phases to these same entry points.
(EIGHT until 2026-09-27, when holdout_probe and generate got bodies and their markers went with
their stubs.) (The phase names are spelled without their parenthesised package here ON PURPOSE: the
obvious way to check this paragraph is `grep -c` for the marker string, and a marker quoted inside
the count that describes it is a claim that corrupts its own measurement -- which is this file's
subject, one level up.) So rewriting these six to P4 would apply half of a deferred renumbering and put this
file at odds with the document that declares it. THIS PARAGRAPH EXISTS SO THE NEXT READER DOES NOT
"FIX" IT EITHER: the open item is the renumbering, and it belongs to whoever applies PLAN.md
section 5's amendment, not to this package.

TWO RULES EVERY FUNCTION BELOW OBEYS, both from the survey:
  G7  an instrument may not leave the model in a different mode than it found it, and may not move
      an RNG stream. Every probe runs under spine.rng.frozen_rng and draws from its own named
      stream. Before c76dc74, changing the holdout n from 4 to 16 moved 48 report lines INCLUDING A
      VERDICT SIGN FLIP, because build_stream drew segment lengths from the same global RNG the
      diagnostics drew from -- how much you MEASURED decided what you TRAINED on.
  ONE LOGITS PATH, RESTATED 2026-09-02 UNDER Q-MEM-10 AND BUILT 2026-09-27 UNDER Q-EVAL-12, STILL
      ONE PATH PER SYSTEM. `logits_fn` is passed in, never constructed here. compose_test built `pm`
      from `model(X)[0]`, the plain LM head, while the held-out path used _eval_logits, so with
      FABRIC=1 three report sections scored a system the run never trained. The rule is therefore:
      ONE CLOSURE PER SCORED SYSTEM, formed in the composition root, passed in, never constructed
      here -- AND EVERY READING NAMES WHICH CLOSURE PRODUCED IT. There are two systems and not one:
      the trained path (memory off) and the trained path plus retrieval (memory on), which has never
      entered training. The -0.097 -> +0.085 b/B price of retrieval IS the difference between them,
      so the PAIR is the deliverable and a single unnamed number is the defect.
      THE TWO CLOSURES EXIST NOW, as spine/compose.py::_logits_fn(sysm, *, use_memory), each with a
      `.name` ('memory-off', 'memory-on') every reading records. THE CONVENTION IS
      fn(x, *, prefix_bytes) -> (B, L, V) logits: x is (B, L) token ids and prefix_bytes holds, per
      row, the bytes BEFORE x's first byte -- the closure routes on them the way training routes on
      the width_units units before each window (Q-FAB-7), so no reading routes on its own targets.
      Inside it is the path the run trained: SIG.encode on the prefix, DOM.nearest (the domain the
      window WOULD be routed to, written nowhere), LM.embed, WORLD.forecast, LM.encode(extra=),
      FAB.forward(training=False) with the head and the NEXT window's routing clock, and the vote or
      LM.decode -- all under no_grad in eval mode, the modes restored. The memory-on closure adds
      softmax -> MEM.encode_queries -> MEM.read(promote=False) -> MEM.blend -> log, the one place
      that mix is written. NO SIGNATURE HERE MOVED FOR THE MIX: `blend_fn` is NOT added to
      curve_probe, holdout_probe, generate or coherence -- see Q-MEM-10 in docs/04_CONTRACT.md,
      which recommended exactly that and was overruled, because four bodies each doing
      softmax -> blend -> log is the ungated mix recomputed at a consumer site, i.e. C8 (prompt.py)
      and C9 (cl_bench.py) rebuilt inside the instrument line.

TWO DECLARED OUTPUTS HAD NO CHANNEL IN THE FROZEN SIGNATURE THAT MUST PRODUCE THEM (found
2026-09-03, referred twice for want of an agent owning both sides). BOTH ARE CLOSED, 2026-09-04, BY
WIDENING THE SIGNATURE ON BOTH SIDES AT ONCE -- docs/04_CONTRACT.md's Q-EVAL-11 carries the full
ruling and the alternatives; what follows is what the two `def` lines now say and why:
  * `CurveReading.step` is returned by curve_probe, whose signature was
    `(ev, *, units_by_domain, logits_fn, rng)`. `step` is RUN's window counter; no argument carried
    it and EVAL owns no clock, so the field could not be filled by the function that returns it.
    curve_probe now takes `step`, and A WIRE WAS NEVER AVAILABLE HERE: a Coupling.compute receives
    only frozen Configs and Config freezes when build() returns, so a per-window counter is refused
    on the same ground as d_curve_bpb and d_shift_at already are in docs/04_CONTRACT.md section 0's
    "Candidates examined and refused as wires" table, whose preamble states that ground in exactly
    those words. NOT THE SAME TABLE AS spine/assemble.py::NOT_WIRES, and this sentence named that
    one until 2026-09-04: NOT_WIRES holds SEVEN rows -- RUN.seed, RUN.epochs -> OPT.d_lr_horizon,
    SIG.d_signature_width_bytes, EVAL.gist, the run length in windows, MEM.cap, and
    FAB.manage_every -> WORLD.d_manage_period_windows -- and neither d_curve_bpb nor d_shift_at is
    among them. The two tables are different and the document's own rows distinguish them (its
    SIG.d_signature_width_bytes row says "already refused in assemble.NOT_WIRES", which would be
    noise if every row were). THE RULING IS UNCHANGED AND DOES NOT REST ON THE CITATION: the ground
    is a property of Coupling.compute, tests/test_couplings.py::check_c2_escapes_refused is what holds it, and both of
    those rows are refused on it -- d_curve_bpb because a held-out measurement is produced thousands
    of windows into the run, d_shift_at because an optimizer step index is runtime state. Only the
    place they are written down was wrong. tests/test_ownership.py::check_o12_citations_name_symbols
    says in its own docstring that it cannot catch this -- "a citation naming a symbol that exists
    and is the wrong one ... no check reaches it" -- so the correction is the only thing that does.
  * `verification_fit`'s DID IT FIRE declares a Gate on `verify != "off"` -- MEM's lever -- and the
    signature was `(ev, *, store_copy, rng)`, which had no such parameter. MEM's Store carries no
    verify field either (its __slots__ are the entry arrays, the block partition and the census,
    re-checked 2026-09-04 against memory/api.py::Store), so the value could not be recovered from
    `store_copy`, and reading MEM's Config here is exactly what owned_by refuses. verification_fit
    now takes `verify_mode`, which the composition root reads off MEM's frozen Config -- the same
    idiom the root already uses for `vocab_slots=LM.vocab_slots` and `lm_kind=LM.arch` into
    MEM.open_store, and for `sig_dim=SIG.d` into DOM.open_partition.
THE WIRE WAS THE OTHER CANDIDATE FOR THE SECOND ONE AND IT LOST ON ITS MERITS, not on its price.
EVAL DECLARES NO WIRES AND RECEIVES NONE, and that is a design statement rather than an accident:
this package measures the run and changes nothing in it, so a value it consumes to RENDER A GATE
never reaches a mechanism. The ledger has room -- 19 cross-package wires against a budget of 25, so
six edges remain, and the "two left" this paragraph carried until 2026-09-04 was a miscount of
couplings as wires -- and the argument is still the wrong thing to spend one on. THE GATE AND THE
FIELD STAYED DECLARED THROUGHOUT. Deleting either to make this file self-consistent would have
traded a recorded gap for a silently missing reading, which is the trade this package refuses.

RECORD TYPES RETURNED (P4/P5 define them; the five below the first are DECLARED as dataclasses in
this file since 2026-09-27, Q-EVAL-12):
  CurveReading   per_domain_bpb, mean_bpb, windows_drawn, units_drawn (the total this probe spent:
                 windows_drawn summed across domains x LM.ctx -- Q-EVAL-5), step
  Reading        value, seed_count, at -- PLAN 3.8 forbids a verdict on n=1, and OPT refuses to damp
                 a restart on a Reading whose seed count is 1; `at` (2026-09-27) is the window it
                 was taken at, so a consumer handed the same Reading twice can tell
  ProbeSet       items, halves, window_bytes, prefix_bytes, shortfall, reason, rng_names -- the
                 pinned held-out windows, per area and per half (control, report); probe_set is the
                 root's name for it
  HoldoutReading areas, control_mean, report_mean, paired, paired_sd, closure, boundary, windows,
                 nonfinite, step
  BlowupReading  name, fired, fires, since_best, best, n, horizon_windows, reason
  NullReading    real, null_mean, null_sd, draws, verdict_allowed
  Sample         population, size, rule, per_domain, closure, temp, reason -- the measured
                 population, its SIZE, and the rule that drew it
"""
import dataclasses
import math

import torch

from spine.lever import Config, LeverError
from spine import units as U
from spine import derive as _derive
from spine import rng as _rng


# ==================================================================================================
# THE SWITCH ON THE NEGATIVE-PERIOD REFUSAL
# ==================================================================================================

REFUSE_NEGATIVE_PERIOD = True
"""Whether curve_period refuses a negative EVAL_CURVE_EVERY. True is the shipped state; False lets
the value through to units.Windows exactly as it did before 2026-09-04.

THE RULING (owner, 2026-09-04): "On the periods, let's refuse for now. If it has a bad effect, we
can turn off the refusal." The first sentence is the guard in curve_period; this name is the second,
which binds just as hard -- .rework/DECISIONS.md D4 rules that a thing kept for later is kept WITH A
SWITCH rather than as a code path that rots, and OFF is what is being kept.

THE ALTERNATIVES, THEIR PRICES AND THE MEASUREMENT THAT WOULD SETTLE THE CHOICE ARE WRITTEN OUT
ONCE, AT ckpt/api.py::REFUSE_NEGATIVE_PERIOD, and are not restated here: CKPT is where this question
was opened and where the first of the five refusals shipped. WHAT IS THIS FILE'S OWN, and the reason
the name is spelled here rather than imported: tests/test_ownership.py::check_o10_no_backdoor_imports
forbids EVAL to import ckpt, so the five switches are five per-package policies that happen to share
a default, each governing only its own package's lever. This one governs EVAL_CURVE_EVERY and
nothing else, and turning it off here leaves the other four refusing.

THE COST, SO IT IS NOT DISCOVERED: turning it off is a CODE EDIT. There is no
EVAL_REFUSE_NEGATIVE_PERIOD, no census row and no row in the generated lever document -- deliberately,
because a lever per package would be five environment names for one decision and would make "some
accessors refuse and some do not" a reachable configuration.
"""


# ==================================================================================================
# THE RECORDS THIS PACKAGE RETURNS, DECLARED (2026-09-27, Q-EVAL-12)
# ==================================================================================================
# FROZEN, all five, for the reason every record in this tree is: a caller that can write to a
# reading can change what the run reported. The module docstring's RECORD TYPES block names them.

@dataclasses.dataclass(frozen=True)
class Reading:
    """One held-out measurement a consumer may act on: (value, seed_count, at).

    `seed_count` is PLAN 3.8's: a verdict on n=1 is forbidden, and OPT refuses to damp a restart on
    a Reading whose seed count is 1. One run is one seed, so every Reading this package builds from
    a single run carries 1. `at` is the window (RunClock.step, an int) the reading was taken at, so
    a consumer handed the same Reading on every flush can tell a new measurement from the last one
    re-delivered -- OPT counts one per distinct `at` (Q-OPT-13). None where no clock stamped it.
    """
    value: float
    seed_count: int
    at: object = None


@dataclasses.dataclass(frozen=True)
class ProbeSet:
    """The pinned held-out windows, drawn ONCE per run and per resume, by pin_holdout.

    items         {area: {"control": ((start, prefix, window), ...), "report": (...)}} -- `start`
                  is the window's byte offset in the area's held-out BLOCK, `prefix` the
                  prefix_bytes bytes before it, `window` the window_bytes bytes it scores; both
                  inside the same half, so neither half ever reads the other's text
    halves        {area: (mid, block_len)} -- control is block[:mid], report is block[mid:]
    window_bytes  the scored window's width in bytes (LM.ctx + 1 when first pinned)
    prefix_bytes  the routing prefix's width in bytes (the SIG width when first pinned)
    shortfall     {area: {"control": n, "report": n}} -- items a half was too short to supply
    reason        "" when pinned; otherwise why nothing was (the probe off, no block)
    rng_names     the child streams drawn, in draw order
    """
    items: dict
    halves: dict
    window_bytes: int
    prefix_bytes: int
    shortfall: dict
    reason: str
    rng_names: tuple


@dataclasses.dataclass(frozen=True)
class HoldoutReading:
    """One reading of the pinned windows through one closure. Returned by holdout_probe.

    areas         {area: {"control": [bits/byte per window], "report": [...], "control_mean",
                  "report_mean", "seen_by_parent"}}
    control_mean  Reading(mean over areas of each area's control mean, 1, step) -- the number
                  CKPT, EVAL's blow-up alarm and OPT consume; None when no window was scored
    report_mean   Reading(the same over the report halves, 1, step) -- the number the run reports
                  and nothing acts on; None when no window was scored
    paired        {area: {half: (n, mean_diff, sd_diff)}} against `previous`, on the items both
                  readings scored; {} with no previous
    paired_sd     the SD of every paired per-window difference, both halves, all areas; None with
                  fewer than two
    closure       the name of the logits_fn that produced it ('memory-off' / 'memory-on')
    boundary      True for the holdout_windows reading (R, a resume's start), False for the cadence
    windows       windows scored
    nonfinite     windows whose bits/byte was not finite (left out of every mean)
    step          the window it was taken at (int)
    """
    areas: dict
    control_mean: object
    report_mean: object
    paired: dict
    paired_sd: object
    closure: str
    boundary: bool
    windows: int
    nonfinite: int
    step: int


@dataclasses.dataclass(frozen=True)
class BlowupReading:
    """The divergence alarm over one series of control means. Returned, per series, by blowup.

    name             'all' for the all-area mean, else the area
    fired            whether the alarm is fired in the current excursion (it re-arms on a new best)
    fires            how many times it fired over the whole series
    since_best       readings since the last new best -- a GAUGE, not a count
    best             the best (lowest) value of the current excursion, or None
    n                readings in the series
    horizon_windows  how long the alarm waits, in windows, at this cadence (derive.blowup_horizon)
    reason           "" when judged; otherwise why it cannot fire yet (fewer than three readings)
    """
    name: str
    fired: bool
    fires: int
    since_best: int
    best: object
    n: int
    horizon_windows: int
    reason: str


@dataclasses.dataclass(frozen=True)
class Sample:
    """What generate returns: the measured population, its SIZE, and the rule that drew it.

    population  {area: [{"prompt": bytes, "ids": [prompt ids + generated ids], "generated": [ids]}]}
    size        the number of continuations
    rule        how the prompts were chosen and the tokens drawn, as a sentence
    per_domain  {area: continuations}
    closure     the logits_fn's name
    temp        EVAL_GEN_TEMP as it was read
    reason      "" when generated; otherwise why nothing was
    """
    population: dict
    size: int
    rule: str
    per_domain: dict
    closure: str
    temp: float
    reason: str


def curve_period(ev: Config):
    """The learning-curve cadence, AS units.Windows. Handed to RUN's Cadences.due.

    UNIT IS Windows: the guard is `step % RATE_EVERY == 0` (:6385) and `step` advances per WINDOW,
    so this knob has always been denominated in Windows while its name and every discussion of it
    said steps. The block sits ABOVE the batch early-out, so unlike CKPT_EVERY it DID fire -- it
    was the LABEL that was wrong, not the gate.

    RENAMED *AND SPLIT*. One cadence drove five unrelated things: the curve probe (:6385), the
    rate/ETA meter (:6489), the profiler dump, the per-expert LR line (:7297) and the
    no-eligible-expert line. Setting RATE_EVERY=100000 to quieten smoke runs SUPPRESSED THE CURVE
    TABLE ENTIRELY, so the curve fix went unverified on a live table for a whole round. Here the
    MEASUREMENT cadence is this lever and the progress line takes RUN's own fixed constant --
    RUN.PROGRESS_WINDOWS, 100 Windows, a module constant with no environment name (Q-RUN-1, RESOLVED
    2026-09-02, and this file's wording was the one of the three that was already right) -- so
    quietening a log can no longer disable a measurement, and there is no log knob left to turn up.

    LEVERS READ: curve_every
    WIRES READ: none
    DID IT FIRE: Cadences.ledger()["curve"]
    """
    ev = ev.owned_by("EVAL")
    # NOT A STUB, AND THE FOUR SIBLINGS ARE NOT EITHER -- DOM.manage_period, FAB.manage_period,
    # MEM.rekey_period and CKPT.save_period, each verified stub-free. This comment said THREE, which
    # is the same off-by-one docs/04_CONTRACT.md corrected in its own sentence about these five
    # accessors on 2026-09-03, one row over and for the same reason it gave: the number is spelled
    # as a WORD and tests/test_contract.py's K13 reads digits, so nothing in the tree could see it.
    # A period accessor is one construction over ITS DECLARED LEVERS, and this sentence read "one
    # declared lever" until 2026-09-04 while naming ckpt/api.py::save_period four lines above --
    # which is a claim about a NEIGHBOUR that the neighbour had already corrected of itself, in its
    # own copy of this comment. That round could not repair this file and wrote the correction down
    # as a REFERRAL instead, which is why the wrong sentence outlived the thing it was wrong about.
    # It is corrected now, in the file it was wrong in: save_period reads TWO,
    # `every` and `dir` through ckpt/api.py::saving_on, and says so on its own LEVERS READ line.
    # THIS accessor really does read one, `curve_every`, which is what its LEVERS READ line above
    # says -- the correction is to the general sentence, not to this function's count.
    # Its whole job is that Cadences.due REFUSES a
    # bare int while Config hands one back for all 37 levers that declare a Clock unit
    # (ISSUES P1-H51). Leaving it a stub kept spine.compose._periods -- and therefore
    # RUN.cadence_audit, the one statement that makes ISSUES P1-C11 visible -- unreachable
    # until P4, for no reason but symmetry with entry points that have real work to do.
    every = int(ev.curve_every)
    # A NEGATIVE CURVE PERIOD IS REFUSED HERE, AT THE ONLY PLACE `curve_every` IS READ (added
    # 2026-09-04 under the owner's ruling; the switch and the alternatives are at
    # REFUSE_NEGATIVE_PERIOD above). It fires BEFORE the Windows is constructed, so no other number
    # is derived from the bad value -- the placement rule capacity/api.py::new_valve took from
    # lm/api.py::resolve, applied here rather than copied: this is a range check over EVAL's own
    # lever at its first read, and EVAL declares no refusal entry point for it to live in.
    #
    # WHAT A NEGATIVE ACTUALLY DOES TODAY, MEASURED RATHER THAN ASSUMED. `assemble.build` accepts
    # EVAL_CURVE_EVERY=-5 and freezes it; this accessor returned Windows(-5); and
    # spine/derive.py::cadences_that_cannot_fire then reported ("curve", -5, 0) -- the SAME shape of
    # line it prints for a period of zero, whose meaning is a per-package sentinel -- AND FOR THE
    # GATE THAT LINE IS RIGHT. RUN.Cadences.due's body opens with `if int(period) <= 0: return
    # False`, so a negative DISARMS the curve gate. UNTIL 2026-09-24 THIS PARAGRAPH SAID A NEGATIVE
    # WAS A FULL CURVE PROBE EVERY WINDOW, a prediction from Cadences.due's contract made before its
    # body existed (the same false premise ckpt/api.py::save_period carried); the body disarms. A
    # negative is an undeclared spelling of "never probe" and the refusal stands on the owner's
    # ruling for that reason. (EVAL.curve_probe itself is deferred, so no probe runs at any value.)
    #
    # ZERO IS NOT TOUCHED, AND WHAT ZERO MEANS HERE IS NOT DECIDED BY THIS GUARD. Unlike CKPT.every
    # (0 disables periodic saving, in the lever's own help text) and MEM.rekey_every (0 DISARMS, in
    # memory/api.py::maintain), EVAL_CURVE_EVERY=0 has NO declared meaning in src/eval/levers.py or
    # in this file. The test below is strictly `< 0`, so whatever the tree eventually rules 0 to
    # mean, it still reaches the same readers it reaches today.
    #
    # IT REMOVES NO CONFIGURATION. EVAL_CURVE_EVERY=1 is the every-window probe and is in range; the
    # negative range spells nothing the help text gives a meaning to.
    if REFUSE_NEGATIVE_PERIOD and every < 0:
        raise LeverError(
            f"EVAL_CURVE_EVERY={every}: a learning-curve period is a count of windows ELAPSED "
            f"since the last probe and may not be negative. RUN.Cadences.due (train/api.py) "
            f"returns False for every period <= 0, so {every} would DISARM "
            f"the curve gate -- an undeclared spelling of 'never probe', printed DISARMED by "
            f"RUN.cadence_audit. Refused rather than read as off, under the owner's switch "
            f"(REFUSE_NEGATIVE_PERIOD at the top of eval/api.py). EVAL_CURVE_EVERY=1 is the "
            f"every-window probe and is in range. This "
            f"lever declares no meaning for 0 either, and 0 is deliberately left alone by this "
            f"refusal rather than folded into it.")
    return U.Windows(every)


def retention_period(ev: Config):
    """The retention probe's cadence, AS units.Windows. Handed to RUN's Cadences.due.

    ONE CONSTRUCTION OVER ONE DECLARED LEVER, for the reason curve_period gives: Cadences.due refuses
    a bare int while Config hands one back for every Clock-unit lever, so the period arrives through
    this package's typed accessor and spine/compose.py::_periods carries it under the key
    'retention' (2026-09-27, Q-EVAL-12). 0 is the probe OFF: Cadences.due answers False for every
    period <= 0, and the loop's arm test (EVAL_RETENTION_EVERY > 0 and a pinned ProbeSet) runs
    before the gate is ever asked, so at 0 the ledger reads 'retention' with zero checks.

    A NEGATIVE IS REFUSED, under this file's REFUSE_NEGATIVE_PERIOD, exactly as curve_period
    refuses EVAL_CURVE_EVERY < 0: Cadences.due would DISARM the gate on it, which is an undeclared
    second spelling of 0, and the owner's 2026-09-04 ruling refuses those by name. The switch is one
    per package and governs this lever too.

    LEVERS READ: retention_every
    WIRES READ: none
    DID IT FIRE: Cadences.ledger()["retention"]
    """
    ev = ev.owned_by("EVAL")
    every = int(ev.retention_every)
    if REFUSE_NEGATIVE_PERIOD and every < 0:
        raise LeverError(
            f"EVAL_RETENTION_EVERY={every}: a retention period is a count of windows ELAPSED "
            f"since the last reading and may not be negative. RUN.Cadences.due (train/api.py) "
            f"returns False for every period <= 0, so {every} would DISARM the retention gate -- "
            f"an undeclared second spelling of the declared off switch, 0. Refused rather than "
            f"read as off, under the owner's switch (REFUSE_NEGATIVE_PERIOD at the top of "
            f"eval/api.py). EVAL_RETENTION_EVERY=0 turns the probe off; 1000 is the register's "
            f"04-6.2 cadence.")
    return U.Windows(every)


def pin_holdout(ev: Config, *, blocks, seed, window_bytes, prefix_bytes):
    """Pin the retention probe's held-out windows: ONE draw per run, per area and per half. -> ProbeSet.

    THE PAIRING IS PINNED HERE, WHICH IS WHAT holdout_probe'S n=32 ARGUMENT RESTS ON (Q-EVAL-9).
    Each area's held-out block (DATA's Areas.holdout) is split at its MIDPOINT into two halves --
    CONTROL, block[:mid], and REPORT, block[mid:] -- and each (area, half) draws its window starts
    sequentially, without repeats, from its own child stream
    rng_for("eval.holdout.<key>.<half>", seed), <key> being derive.stream_key(area), under the
    "eval" parent spine/compose.py::RNG_SUBSYSTEMS declares. The same seed and the same blocks give
    the same starts in every process, so every reading of a run and of its resumes scores the SAME
    byte windows and a difference between two readings is paired (Q-EVAL-12).

    WHY TWO HALVES (Q-EVAL-12). The control half is what the run's consumers read -- CKPT's
    best-model policy, EVAL's blow-up alarm and, at OPT_DAMP_SOURCE='probe', OPT's damping; the
    report half is what the run reports and nothing acts on, so no consumer can be tuned against the
    number the report prints. A window and its routing prefix stay inside ONE half: a start is drawn
    in [prefix_bytes, half_len - window_bytes], so neither half ever reads the other's text.

    HOW MANY. Each half draws the larger of its share of the in-run reading (EVAL_RETENTION_N, the
    odd one to control) and its share of the boundary reading (EVAL_HOLDOUT_WINDOWS, likewise), and
    both readings take the FIRST n of the one draw: the in-run items are a prefix of the boundary
    items, so the two readings stay paired with each other too. The draw is SEQUENTIAL -- each start
    one randint, a repeat redrawn -- because a prefix of a sequential draw is the draw at a smaller
    n, which random.sample does not promise. A half too short to supply its n is recorded as
    `shortfall` and read with what it has.

    THE GEOMETRY IS AN ARGUMENT AND THE ROOT OWNS IT: window_bytes is LM.ctx + 1 when first pinned
    (a window of ctx+1 bytes tokenizes to at most ctx+1 ids, so its inputs fit the model's context
    whatever the vocabulary), prefix_bytes the SIG width; a resume passes the geometry its parent
    recorded in LOOP.eval, so a child re-pins the SAME windows even where its own LM.ctx differs.

    OFF MEANS NOTHING PINNED AND NOTHING DRAWN: at EVAL_RETENTION_EVERY=0 (the build default until
    the register's C9 flip) or with no area holding a block (DATA_SYNTH_HOLDOUT=0 on the synthetic
    source), the ProbeSet is empty, carries the reason, and no stream is minted -- so rng.issued()
    reads exactly as it did before this entry point existed.

    LEVERS READ: holdout_windows, retention_n, retention_every
    WIRES READ: none
    DID IT FIRE: ProbeSet.items per (area, half), ProbeSet.shortfall, ProbeSet.rng_names (and
                 rng.issued(), where each child appears with its draw count); the root books
                 eval.holdout.shortfall from it
    """
    ev = ev.owned_by("EVAL")
    every = int(ev.retention_every)
    hw, rn = int(ev.holdout_windows), int(ev.retention_n)
    W, P = int(window_bytes), int(prefix_bytes)
    if every <= 0:
        return ProbeSet(items={}, halves={}, window_bytes=W, prefix_bytes=P, shortfall={},
                        reason=(f"EVAL_RETENTION_EVERY={every}: the retention probe is off -- no "
                                f"window is pinned, no stream is drawn and no reading is taken."),
                        rng_names=())
    have = {str(a): bytes(b) for a, b in dict(blocks or {}).items() if b}
    if not have:
        return ProbeSet(items={}, halves={}, window_bytes=W, prefix_bytes=P, shortfall={},
                        reason=("no area holds a held-out block (DATA's Areas.holdout is empty -- "
                                "on the synthetic source that is DATA_SYNTH_HOLDOUT=0), so there is "
                                "nothing to pin and the probe reads nothing."),
                        rng_names=())
    if W < 2 or P < 0:
        raise ValueError(
            f"EVAL.pin_holdout: window_bytes={W}, prefix_bytes={P}. A scored window needs at least "
            f"two bytes -- one input and one target -- and a prefix cannot be negative. The root "
            f"passes LM.ctx + 1 and the SIG width, or the geometry a parent recorded.")
    need = {"control": max(-(-rn // 2), -(-hw // 2)), "report": max(rn // 2, hw // 2)}
    items, halves, shortfall, names = {}, {}, {}, []
    for area in sorted(have):
        blk = have[area]
        mid = len(blk) // 2
        halves[area] = (mid, len(blk))
        items[area], shortfall[area] = {}, {}
        for half, (h0, h1) in (("control", (0, mid)), ("report", (mid, len(blk)))):
            lo, hi = P, (h1 - h0) - W
            avail = max(0, hi - lo + 1)
            k = min(need[half], avail)
            name = f"eval.holdout.{_derive.stream_key(area)}.{half}"
            stream = _rng.rng_for(name, seed)
            names.append(name)
            starts, seen = [], set()
            while len(starts) < k:
                s = stream.randint(lo, hi)
                if s in seen:
                    continue
                seen.add(s)
                starts.append(s)
            items[area][half] = tuple(
                (h0 + s, blk[h0 + s - P:h0 + s], blk[h0 + s:h0 + s + W]) for s in starts)
            shortfall[area][half] = need[half] - k
    return ProbeSet(items=items, halves=halves, window_bytes=W, prefix_bytes=P,
                    shortfall=shortfall, reason="", rng_names=tuple(names))


def curve_probe(ev: Config, *, units_by_domain, logits_fn, step, rng):
    """One learning-curve probe. Returns CurveReading.

    THE SAMPLE SIZE IS ev.windows AND NOT A HARDCODED 16 (Q-EVAL-5, RESOLVED 2026-09-02 -- read the
    lever). The old probe drew `range(16)` at :6396 while the lever's own help text quotes that 16
    as if it were declared -- an undeclared second default INSIDE THE SENTENCE DESCRIBING THE LEVER,
    which is the L1 shape arriving through the document written to end it. The old EVAL_N was
    UNRAISABLE -- five of its six readers wrapped it as min(24, EVAL_N) or min(48, EVAL_N), so
    EVAL_N=256 drew 24, the untrippable-guard shape -- and hardcoding 16 here would rebuild it. An
    operator who wants the old cost sets EVAL_WINDOWS=16 and gets exactly it, which is what makes
    reading the lever strictly better than the literal rather than merely tidier.

    THE COST, WITH THE NUMBER AND THE CONDITION ON IT. `ev.windows` resolves to 64, so the multiplier
    is 64/16 = 4x, and it belongs on P9's list of numbers expected to move. BUT IT IS 4x OF ZERO AT
    THE SHIPPED DEFAULTS AND THE P9 ENTRY MUST SAY SO: curve_every=2000 against a default run of
    506-937 windows (DATA.stream_bytes=120000, LM.ctx=128, RUN.epochs=1) means this probe NEVER
    FIRES, which is ISSUES P1-C11. An unconditional "the default probe cost rose 4x" is a number nobody
    can reproduce -- the failure P9 exists to prevent -- so the entry reads "4x on runs long enough
    to probe; does not exist at the shipped defaults". If the C11 run-length ruling raises
    stream_bytes or epochs, this question should be re-read, not carried.

    `step` IS RUN'S WINDOW COUNTER AND IT ARRIVES AS AN ARGUMENT, ADDED 2026-09-04 (Q-EVAL-11).
    CurveReading carries `step` -- it is what makes a curve a curve, and what CKPT's Retention
    compares one reading against another by -- and until this edit the signature had no channel for
    it: EVAL owns no clock, `units_by_domain` carries material rather than position, and a probe
    that stamped its own reading from a counter it invented would be a second source of truth for
    RUN.RunClock. A WIRE COULD NOT HAVE CARRIED IT: spine/assemble.py::COUPLINGS computes from
    FROZEN Configs and a window counter is runtime state, which is the ground docs/04_CONTRACT.md
    section 0's "Candidates examined and refused as wires" table already refuses d_curve_bpb and
    d_shift_at on -- NOT spine/assemble.py::NOT_WIRES, which this sentence named until 2026-09-04
    and which contains neither of them (see this module's docstring for the seven rows it does
    hold). The ground itself is unaffected, and it is the module docstring's, not a borrowed one.
    The composition root passes RunClock's window index when
    P5 writes the row; the value is RUN's, and it is stamped, never derived here.

    LEVERS READ: windows
    WIRES READ: none
    DID IT FIRE: CurveReading.windows_drawn PER DOMAIN -- a domain that yielded zero windows is
                 REPORTED, not skipped (the recorded case: CAN A DOMAIN PREDICT needed 16 and drew
                 min(48, EVAL_N), so at EVAL_N=4 it collected 4, produced nothing, and DOM_PRIOR
                 was accumulated and never read) -- AND THE TOTAL THIS PROBE SPENT, windows_drawn
                 summed across domains times LM.ctx, so the sample size is a knob whose cost is
                 VISIBLE as well as raisable and lowerable. That asymmetry is what EVAL_N failed:
                 it could only ever be lowered, and nothing printed what it bought.
    """
    ev = ev.owned_by("EVAL")
    raise NotImplementedError(
        "EVAL.curve_probe: P5 (eval) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section EVAL.")


def _mean(xs):
    return (sum(xs) / len(xs)) if xs else None


def _sd(xs):
    if len(xs) < 2:
        return None
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def holdout_probe(ev: Config, *, units_by_domain, logits_fn, tokenize_fn, step, boundary=False,
                  previous=None):
    """The retention probe: held-out bits/byte per area, KEYED BY AREA NAME so adding an area
    does not shift the comparison. This is the R matrix's resolution and the entire error bar on
    "did adding an area damage what was already known".

    THE SIGNATURE MOVED 2026-09-27 (Q-EVAL-12). `rng` LEFT: the pinned draw is pin_holdout's, made
    once per run at the root's 'probe' row, so this function draws nothing and a stream handed to it
    could only be a second, unpinned source of starts. `tokenize_fn` and `step` ARRIVED: EVAL may
    not import TOK (O10), so the root hands it TOK.tokenize bound to the vocabulary at the view the
    stream was last cut at (spine/compose.py::_holdout_tokenize); and EVAL owns no clock, so the
    window the reading is taken at arrives as an argument, as curve_probe's `step` did under
    Q-EVAL-11 -- the Readings it returns carry it as `at`. `boundary` and `previous` choose the
    size and the pairing.

    WINDOW STARTS ARE IN BYTE COORDINATES and tokenize_fn is applied to the fixed byte windows.
    ISSUES P1-H20: :5087-5088 drew them as `randint(0, len(_v) - WIN - 2)` where `_v` is the
    TOKENISED validation text, whose length shrinks over a run under online minting and differs
    between parent and child -- so `prev` and `now` were measured on DIFFERENT WINDOWS, on the one
    number the file calls "the ONLY number that spans the run boundary".

    `units_by_domain` IS THE ROOT'S ARRIVED SET, from pin_holdout's ProbeSet:
        {area: {"control": [(prefix, window), ...], "report": [...], "seen_by_parent": bool}}
    Only areas the run has reached are in it (spine/compose.py::_holdout_units): an area whose
    phase has not begun has trained on nothing and its reading would be a measurement of nothing.

    WHAT ONE WINDOW IS WORTH. ids = tokenize_fn(window).ids; x = ids[:-1]; y = ids[1:];
    logits = logits_fn(x[None], prefix_bytes=[prefix]); the window's bits/byte is the summed
    cross-entropy of y in nats / ln 2 / the bytes y covers (len(window) - byte_pos[1], the targets'
    span -- spine/loop.py::_window_bytes' definition, so a probe window and a training window are
    scored per byte the same way). An area's mean is the mean of its windows; the reading's mean is
    the MEAN OF AREA MEANS, so an area with more windows is not weighted up.

    HOW MANY, per arrived area: the first n pinned items of each half, n = retention_n at a cadence
    reading and holdout_windows at a boundary one (R, and a resume's start), split with the odd one
    to control. Both are prefixes of one draw, so a cadence reading and a boundary reading are
    paired on the items they share.

    THE COMPARISON IS PAIRED (Q-EVAL-9): `previous`, when given, is an earlier HoldoutReading, and
    `paired` carries each area's and half's (n, mean difference, SD of the differences) on the items
    both readings scored; paired_sd pools every difference. On the same windows the per-window
    difficulty term cancels, which is what makes n=32 paired a stronger instrument than n=32
    unpaired (research_continual_memory.md:743-745 is calibrated for the unpaired case). And the
    DOMINANT error bar is neither: PLAN 3.8 records a between-seed spread of 0.066-0.131 b/B, so
    every Reading here carries seed_count 1.

    A NON-FINITE WINDOW IS COUNTED AND LEFT OUT OF EVERY MEAN (HoldoutReading.nonfinite): a reading
    that averaged a nan would hand a nan to three consumers, and CKPT.Retention.consider refuses one.

    G7, BOTH HALVES. It runs under spine/rng.py::frozen_rng(strict=True) and refuses a body that
    moved a global stream -- the closure computes under no_grad in eval mode, and a dropout left on
    would move torch's global generator and edit the training run from inside an instrument. And it
    moves nothing it measures: the root's closure routes with DOM.nearest, reads MEM with
    promote=False and passes training=False to FAB.forward, none of which writes.

    LEVERS READ: holdout_windows, retention_n
    WIRES READ: none
    DID IT FIRE: HoldoutReading.windows and .nonfinite, windows per area and half, and the SEED
                 COUNT carried on each Reading; plus the PAIRED SD. The root books the rest --
                 eval.holdout.calls and its three arms, and the closure's own forwards, decodes,
                 cuts and SIG encodes -- in its eval book, because a count here would be a second
                 ledger for the same event
    """
    ev = ev.owned_by("EVAL")
    if not isinstance(step, U.Windows):
        raise U.UnitError(
            f"EVAL.holdout_probe: step is {type(step).__name__}({step!r}), not units.Windows. It "
            f"is RunClock.step, stamped on every Reading this returns as `at`; a bare int carries "
            f"no kind, so a Flushes count arriving here would be off by the batch width with "
            f"nothing to raise on it.")
    n = int(ev.holdout_windows) if boundary else int(ev.retention_n)
    take = {"control": (n + 1) // 2, "report": n // 2}
    closure = str(getattr(logits_fn, "name", getattr(logits_fn, "__name__", "logits_fn")))
    areas, windows, nonfinite = {}, 0, 0
    with _rng.frozen_rng(strict=True) as fr:
        for area in sorted(units_by_domain):
            row = units_by_domain[area]
            got = {"seen_by_parent": bool(row.get("seen_by_parent", False))}
            for half in ("control", "report"):
                vals = []
                for prefix, window in list(row.get(half) or ())[:take[half]]:
                    seg = tokenize_fn(bytes(window))
                    ids = list(seg.ids)
                    if len(ids) < 2:
                        continue
                    span = len(window) - int(seg.byte_pos[1])
                    x = torch.tensor([ids[:-1]], dtype=torch.long)
                    y = torch.tensor(ids[1:], dtype=torch.long)
                    lg = logits_fn(x, prefix_bytes=[bytes(prefix)])
                    nats = float(torch.nn.functional.cross_entropy(
                        lg[0].float(), y.to(lg.device), reduction="sum"))
                    bpb = nats / math.log(2.0) / max(1, span)
                    windows += 1
                    if not math.isfinite(bpb):
                        nonfinite += 1
                        continue
                    vals.append(bpb)
                got[half] = vals
                got[half + "_mean"] = _mean(vals)
            areas[area] = got
    if fr.moved:
        raise _rng.RngError(
            "EVAL.holdout_probe moved a global random stream while reading. The closure must run "
            "under no_grad in eval mode -- a dropout left on draws from torch's global generator, "
            "and an instrument that draws edits the training run it measures (G7). frozen_rng put "
            "the stream back; the reading is refused rather than reported.")
    at = int(step)
    cms = [a["control_mean"] for a in areas.values() if a.get("control_mean") is not None]
    rms = [a["report_mean"] for a in areas.values() if a.get("report_mean") is not None]
    control = Reading(value=_mean(cms), seed_count=1, at=at) if cms else None
    report = Reading(value=_mean(rms), seed_count=1, at=at) if rms else None
    paired, diffs = {}, []
    if previous is not None:
        for area, got in areas.items():
            was = previous.areas.get(area)
            if was is None:
                continue
            paired[area] = {}
            for half in ("control", "report"):
                a, b = list(got.get(half) or ()), list(was.get(half) or ())
                k = min(len(a), len(b))
                d = [a[i] - b[i] for i in range(k)]
                diffs += d
                paired[area][half] = (k, _mean(d), _sd(d))
    return HoldoutReading(areas=areas, control_mean=control, report_mean=report, paired=paired,
                          paired_sd=_sd(diffs), closure=closure, boundary=bool(boundary),
                          windows=windows, nonfinite=nonfinite, step=at)


def blowup(ev: Config, *, series):
    """The divergence alarm, over the retention probe's CONTROL means. -> {name: BlowupReading}.

    THE ALARM THAT WAS NESTED IN A CHECKPOINT FLAG, MOVED TO THE INSTRUMENT (ckpt/api.py::
    Retention.consider says why: "a run that was not SAVING got no warning it had stayed elevated --
    the recorded case lost 4.6 b/B and then spent ~520,000 further steps never getting back"). It
    REPORTS ONLY: nothing reads its verdict to change the run.

    `series` IS THE ROOT'S, carried in LOOP.eval: {name: [entry, ...]}, one entry per reading, where
    an entry is the control mean (a float) or (value, True) -- a reading at which the series
    RE-ARMS. 'all' is the all-area mean; every other name is one area's control mean.

    THE CALL-SITE PATTERN IS blowup_test.py's (:63-80), VERBATIM IN ITS RULE: the last five values
    are the recent window, a new best (x < best - 1e-6) resets the staleness count and re-arms, and
    the alarm fires ONCE PER EXCURSION through spine/derive.py::blowup_stale at its own defaults
    (rise 0.5 b/B, stale 80 readings -- the constants measured across nine real runs).

    THE ALL-AREA SERIES RE-ARMS AT EVERY ARRIVAL (Q-EVAL-12). The mean steps UP when an area
    arrives -- a new area's held-out text is text the run has barely trained on -- so without a
    re-arm the stale-80 rule would fire about 80 readings after every arrival on a healthy run. At a
    re-arm entry the best, the staleness count and the recent window are reset and the arrival's
    reading is the new best. The per-area series need no re-arm: an area's own mean does not jump
    when another arrives.

    ITS HORIZON IS A NAMED CONVERSION: "80 readings" is spine/derive.py::blowup_horizon's answer in
    windows at EVAL_RETENTION_EVERY, because arithmetic on a Clock-unit lever at a call site is what
    tests/test_ownership.py O11 refuses.

    LEVERS READ: retention_every (for the horizon only)
    WIRES READ: none
    DID IT FIRE: BlowupReading.fires per series and .since_best (a gauge); the root books
                 eval.blowup.fired (the total over every series) and eval.blowup.since_best
    """
    ev = ev.owned_by("EVAL")
    stale, horizon = _derive.blowup_horizon(retention_period(ev))
    out = {}
    for name in sorted(series, key=lambda k: (k != "all", k)):
        best, since, recent, fired, fires = None, 0, [], False, 0
        entries = list(series[name])
        for e in entries:
            rearm = isinstance(e, (tuple, list))
            x = float(e[0]) if rearm else float(e)
            if rearm and bool(e[1]):
                best, since, recent, fired = None, 0, [], False
            recent.append(x)
            del recent[:-5]
            if best is None or x < best - 1e-6:
                best, since, fired = x, 0, False
                continue
            since += 1
            if not fired and _derive.blowup_stale(recent, best, since):
                fired = True
                fires += 1
        reason = "" if len(entries) >= 3 else (
            f"{len(entries)} reading(s): blowup_stale judges nothing below three, and the alarm "
            f"waits {stale} readings without a new best ({int(horizon)} windows at "
            f"EVAL_RETENTION_EVERY={int(ev.retention_every)}) before it can fire.")
        out[name] = BlowupReading(name=str(name), fired=bool(fired), fires=int(fires),
                                  since_best=int(since), best=best, n=len(entries),
                                  horizon_windows=int(horizon), reason=reason)
    return out


def null_excess(ev: Config, *, real, permute, rng):
    """The permutation null every 2-sigma verdict is judged against. Returns NullReading.

    REFUSES draws < 2 AT CONSTRUCTION. ISSUES P1-L44: null_draws=0 gives an empty list and
    `sum(_nl)/len(_nl)` is a ZeroDivisionError that takes the whole remainder of the report with it
    (compose_test at :8949 has no try/except while the very next section does). L45: at 1 draw the
    sd is exactly 0.0 and `real - null > 2*sd + 1e-9` reduces to "any excess above 1e-9" -- a
    rubber stamp. `choices=` cannot express "any integer >= 2", so the floor belongs here, as a
    refusal. Two runs of the SAME configuration once printed opposite conclusions at excess +0.010
    and +0.013 against a 0.010 cutoff.

    LEVERS READ: null_draws
    WIRES READ: none
    DID IT FIRE: NullReading.draws, and verdict_allowed=False WITH A REASON when the floor bites
    """
    ev = ev.owned_by("EVAL")
    raise NotImplementedError(
        "EVAL.null_excess: P5 (eval) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section EVAL.")


# ==================================================================================================
# THE P6 INSTRUMENTS. Declared here so their levers have a named reader; P6 writes the bodies.
# ==================================================================================================

def generate(ev: Config, *, logits_fn, prompts_by_domain, rng):
    """Sampled continuations, per domain, for the text judgements. Returns a Sample.

    EVERY TEXT JUDGEMENT IN THIS PROJECT'S HISTORY RESTED ON A SINGLE 200-TOKEN CONTINUATION: 91%
    vs 71% "real words" were three or four words apart. gen_samples x gen_domains is the sample the
    Sample records, and prompt.py:168 declares its OWN GEN_LEN default and a GEN_TEMP of 0.6
    against the registry's 0.7 -- a live L1 violation in the one script that exercises the
    deliverable by hand, which is why prompt.py receives this frozen Config instead of re-reading
    the environment.

    THE BODY, 2026-09-27 (Q-EVAL-12). `prompts_by_domain` is the root's (spine/compose.py::
    _gen_prompts): {area: [{"prefix": bytes, "ids": [token ids]}, ...]} -- report-half held-out
    windows of the arrived areas, tokenized at the view the stream was last cut at, so a prompt is
    text the run never trained on. The FIRST gen_domains areas in sorted order each give their
    first gen_samples prompts, and each prompt is continued by gen_len tokens: logits_fn over the
    whole sequence so far, the last position's logits over gen_temp, and one draw by INVERSE CDF on
    a uniform from rng.torch_generator() -- the stream the root minted once per System at the
    'probe' row as rng_for('eval.generate', seed), so two runs of one seed generate the same text
    and no training stream is touched. gen_temp <= 0 takes the argmax.
    THE CLOSURE OWNS THE WINDOW AND THE PREFIX: this body hands it the whole sequence, and the root's
    closure keeps the last LM.ctx tokens and rebuilds the routing prefix by decoding the dropped
    ids (TOK.Vocabulary.decode), because EVAL can read neither LM's context nor TOK's vocabulary.
    AND IT OWNS THE VOCABULARY BOUNDARY: the closures the root hands this body set every id at or
    above TOK.Vocabulary.size() to -inf, so each draw is an id the vocabulary can print -- at the
    shipped LM_MASK_DEAD_ROWS=0 a never-minted row keeps some mass, and one drawn has no bytes.

    AFTER THE FINAL SAVE, ONCE PER CLOSURE: the root calls this after the final checkpoint is
    written, so generation can cost the run nothing it keeps. Its caveat is recorded here rather
    than printed as prose: the text comes from the LIVE model at the end of training, not from the
    best one.

    LEVERS READ: generate, gen_samples, gen_domains, gen_len, gen_temp
    WIRES READ: none
    DID IT FIRE: Sample.size and the per-domain counts; `generate` off is unreachable, not zero --
                 the root books eval.generate.samples and eval.generate.tokens, ABSENT at
                 EVAL_GENERATE=0 or with no ProbeSet
    """
    ev = ev.owned_by("EVAL")
    closure = str(getattr(logits_fn, "name", getattr(logits_fn, "__name__", "logits_fn")))
    temp = float(ev.gen_temp)
    if not bool(ev.generate):
        return Sample(population={}, size=0, rule="", per_domain={}, closure=closure, temp=temp,
                      reason="EVAL_GENERATE=0: the generation section is off.")
    n_dom, n_s, n_len = int(ev.gen_domains), int(ev.gen_samples), int(ev.gen_len)
    gen = rng.torch_generator()
    pop, per = {}, {}
    for area in sorted(prompts_by_domain)[:max(0, n_dom)]:
        rows = []
        for p in list(prompts_by_domain[area])[:max(0, n_s)]:
            seq = [int(t) for t in p["ids"]]
            made = []
            for _ in range(max(0, n_len)):
                lg = logits_fn(torch.tensor([seq], dtype=torch.long),
                               prefix_bytes=[bytes(p.get("prefix", b""))])
                last = lg[0, -1].float()
                if temp <= 0.0:
                    t = int(last.argmax())
                else:
                    probs = torch.softmax(last / temp, dim=-1).cpu()
                    u = float(torch.rand((), generator=gen))
                    cdf = torch.cumsum(probs, dim=-1)
                    # right=True: the first index whose cumulative mass EXCEEDS the draw, so a
                    # token the closure masked to probability 0 can never be the answer.
                    t = int(min(int(torch.searchsorted(cdf, torch.tensor(u * float(cdf[-1])),
                                                       right=True)),
                                int(probs.shape[0]) - 1))
                seq.append(t)
                made.append(t)
            rows.append({"prompt": bytes(p.get("prefix", b"")), "ids": seq, "generated": made})
        pop[area] = rows
        per[area] = len(rows)
    size = sum(per.values())
    rule = (f"the first {n_s} report-half held-out window(s) of each of the first {n_dom} arrived "
            f"area(s) in sorted order, each continued by {n_len} token(s) at temperature {temp} "
            f"by inverse CDF on uniforms from rng_for('eval.generate', seed)")
    return Sample(population=pop, size=size, rule=rule, per_domain=per, closure=closure,
                  temp=temp, reason="" if size else "no arrived area holds a prompt")


def coherence(ev: Config, *, logits_fn, units_by_domain, encode, rng):
    """The coherence Reading over its OWN seeded sample, not over the printed generations.

    It was scored on the four printed GENERATION samples, ~2 windows each, so every coherence
    number ever printed landed on 0.25/0.50/0.75/1.00 -- a four-sample mean with SE 0.25. "memory
    HELPS (0.50 -> 0.75)" was ONE SAMPLE FLIPPING, reported as a finding twice, in opposite
    directions on consecutive runs. coh_seeds and coh_len size a sample this instrument draws for
    itself.

    THE PARAMETER WAS `sample` UNTIL 2026-09-02 AND THAT IS WHAT LET THE DEFECT HAPPEN
    (Q-EVAL-10, RESOLVED). A `Sample` is the object EVAL.generate returns -- the printed
    generations -- so the signature invited exactly the argument the sentence above forbids, and
    the old code passed it. What this instrument needs is MATERIAL, not a measurement:

      units_by_domain  the same per-domain unit stream curve_probe and holdout_probe take, in the
                       same shape and under the same name, because ONE CALLABLE OR ONE RECORD
                       DECLARED TWICE WITH TWO SHAPES is how a signature width came out 614 on one
                       path and 1 on the other. coh_seeds seeds are drawn FROM it, one per domain
                       in rotation, and the CEILING -- real text of the same length scored the same
                       way -- is cut from it too. The per-domain keys are load-bearing: HOME is the
                       key of the bucket a seed came from, so the strict arm needs no lookup.
      encode           SIG.encode bound to the SigState -- the SAME callable DOM.rekey takes, and
                       the composition root already forms it (_sig_encode_fn). It is here because
                       the measurement IS an encoding: "which centroid is this window of the
                       CONTINUATION nearest" is evaluated per generated window on BOTH arms, and
                       EVAL may not import SIG. Without it this function cannot be written at all.
                       It also builds the TRUE-CORPUS centroids from units_by_domain, which is the
                       stricter reference: scoring against DOM's assembled partition instead would
                       be the self-referential arm, and shipping only that arm would silently
                       downgrade the metric to "the encoder is self-consistent".

    `rng` was always the tell that this instrument draws: a function that only SCORES a handed-in
    sample has no draw to seed, and G7 says every probe draws from its own named stream.

    THE SELF-REFERENTIAL ARM IS STILL P6'S, AND IT NEEDS NOTHING FURTHER FROM THIS SIGNATURE. On a
    run with fewer than two labelled buckets there are no true-corpus centroids; the fallback is
    the partition the system assembled, and HOME is then MEASURED per seed by encoding it and
    taking the nearest centroid (eval/levers.py, coh_seeds) -- with `encode` in hand that is this
    function's own arithmetic. It must be LABELLED as the weaker claim wherever it is printed.

    LEVERS READ: coh_seeds, coh_len, gen_temp
    WIRES READ: none
    DID IT FIRE: Sample.size, and the Reading's seed count. The arm is part of the record: strict
                 (true-corpus centroids) or self-referential, never silently one of the two.
    """
    ev = ev.owned_by("EVAL")
    raise NotImplementedError(
        "EVAL.coherence: P6 (eval) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section EVAL.")


def verdicts(ev: Config, *, domain_sizes, silhouettes, affiliation, coherence_reading):
    """The genuineness and affiliation verdicts, each as a Reading with its own null.

    The predecessor genuineness test was `coh >= 0.5 AND sep >= 0.10`, A CONJUNCTION WHERE ONE
    CLAUSE COULD NEVER BE FALSE; and the sizes it tested came from THE REPORT LOG, so a domain of
    ~2100 members printed as "size 134" -- 1/BATCH_W of the truth. `domain_sizes` therefore arrives
    from DOM.census(), never from a log line.

    LEVERS READ: genuine_min, genuine_sil, aff_min
    WIRES READ: none
    DID IT FIRE: each verdict's Reading with its sample size and its null; a verdict refused for
                 n=1 is a reported state, not a missing line
    """
    ev = ev.owned_by("EVAL")
    raise NotImplementedError(
        "EVAL.verdicts: P6 (eval) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section EVAL.")


def wrongness_probe(ev: Config, *, store_copy, scorer, rng):
    """The injected-wrongness precision/recall Reading, ON A COPY OF THE STORE.

    THE OLD BLOCK MUTATED WHAT IT MEASURED -- force-writes injected entries, runs selfcheck,
    deletes src 99, then `mem.selfcon.fill_(-1.0)` -- so every later section scored a store the
    report had edited. It must be a Sample on a COPY with the G7 digest asserted around it. It is
    also UNDEFINED BELOW TWO SOURCE DOMAINS: the unguarded version raised IndexError and took the
    whole battery down AFTER training and checkpointing completed, which is why the guard is a
    declared Gate and not a try/except.

    Injected entries carry src = -2, which MEM reserves for non-domain provenance, so the harness
    can never collide with a real domain id (H30 -- the old one used src=99).

    LEVERS READ: wrongness, wrong_inject
    WIRES READ: none
    DID IT FIRE: Sample.size, precision, recall, and the Gate that says "unreachable (fewer than
                 two source domains)" with the count
    """
    ev = ev.owned_by("EVAL")
    raise NotImplementedError(
        "EVAL.wrongness_probe: P6 (eval) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section EVAL.")


def verification_fit(ev: Config, *, store_copy, verify_mode, rng):
    """Fit the Reconstructor POST HOC on a SETTLED store and report its precision.

    The joint in-loop fit trained against a churning, re-tokenized, re-keyed store -- its targets
    moved while it fit -- and reached 0.3% precision. Post hoc the target is fixed. `verify_fit_steps`
    is genuine units.Steps: optimizer steps of a small separate model, in a loop with no windows
    and no flushes in it. THIS IS THE ONE PLACE IN THIS FILE WHERE units.Steps IS LITERALLY WHAT IS
    COUNTED, and it must never be compared against curve_every.

    `verify_mode` IS MEM'S `verify` LEVER, ARRIVING AS AN ARGUMENT, ADDED 2026-09-04 (Q-EVAL-11).
    It exists for the Gate below and for nothing else: the post-hoc fit is a reading ABOUT the
    judge the run actually used, and at MEM_VERIFY=off the run judged nothing, so the precision
    this function reports is the precision of a mechanism no run consulted. That has to be on the
    line, not inferred by whoever reads it. It is an ARGUMENT and not a wire: EVAL declares no
    wires and receives none, a value consumed to render a Gate never reaches a mechanism, and the
    composition root already passes another package's frozen lever this way for
    MEM.open_store(vocab_slots=LM.vocab_slots, lm_kind=LM.arch) and
    DOM.open_partition(sig_dim=SIG.d). IT MAY NOT BE RECOVERED FROM `store_copy`: memory/api.py::
    Store's __slots__ are the entry arrays, the block partition and the census, with no verify
    field -- and inferring the mode from whether Store.recon or Store.selfcon holds values would
    read a configuration off the data, which is the shape this whole file exists to refuse.

    LEVERS READ: verify_fit_steps
    WIRES READ: none
    DID IT FIRE: the fit's step count, its precision, and the Gate on `verify_mode != "off"` --
                 which is MEM's lever, so the gate is rendered from the value the composition root
                 passed rather than from a read of MEM's Config, which owned_by refuses. THE GATE
                 IS BUILDABLE AS OF 2026-09-04: it was declared against a signature with no channel
                 for its input from 2026-09-03, recorded rather than deleted, and the channel is
                 now the `verify_mode` parameter above. The Gate stays declared either way: an
                 instrument that silently omits a reading because its input was never wired is the
                 armed-and-inert failure with the evidence removed.
    """
    ev = ev.owned_by("EVAL")
    raise NotImplementedError(
        "EVAL.verification_fit: P6 (eval) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section EVAL.")
