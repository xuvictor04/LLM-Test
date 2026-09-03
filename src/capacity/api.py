"""CAP -- the frozen public surface. Signatures only; P4 writes the bodies.

CAP owns the EARNED-CAPACITY VALVE: a population that is FULL and a loss that has STOPPED MOVING
may have its ceiling raised, by a little, never lowered. It is the one mechanism in the tree that
lets a run become bigger than it was on EARNED PRESSURE rather than on a schedule or a regression,
which is why it is one of the two honest answers to new material (goal B) -- and why goal A's
"room for more modalities" lands here as arithmetic: C31 recorded `grew 2048 -> 2048 (+0)` on the
first continual-learning run, because the vocabulary was already full of English and the second
language was spelled entirely with English's merges. CAP owns NEITHER POPULATION; it owns the
operating ceiling that sits underneath the hardware one and moves.

ONE VALVE, ONE OWNER, ONE CLOCK. FAB receives a single integer ceiling per flush through
grow_check(soft_cap=...); TOK receives an EVENT through lift_vocab_cap(to=...). No period crosses
either boundary, which is how the Windows/Flushes clash is removed rather than converted.

THE CLOCK REPAIR THIS CONTRACT ADOPTS. derive.pin_tick is re-typed to accumulate units.Windows and
the threshold stays cap.pin_windows (Windows); NO CONVERSION HAPPENS ANYWHERE. The delta the clock
accumulates is `step - _pin_prev` (:7368), a WINDOW delta, so Windows is the kind the arithmetic
already has. capacity/levers.py::<module> sets out two legal repairs and records that applying BOTH
fires the valve 16x TOO EARLY -- the second repair is dividing the threshold by batch_w, which is
exactly what the FAB.d_cap_lift_period and TOK.d_cap_lift_period ledger rows do. Those rows
survive in this contract as REPORTING wires only (see FOR THE OWNER Q-CLOCK-1); the valve does not
read either of them, and Windows(...) >= Flushes(...) raises, so applying both repairs at once is
refused by the type system rather than by discipline.

    TRUE IN THE CODE AS OF 2026-08-30, and it was not when this paragraph was written. For six
    commits this file asserted the repair as done while spine/derive.py still refused a Windows,
    and docs/04_CONTRACT.md stated it done in one section and proposed in another (Q-DERIVE-1). An
    implementer following this contract would have written pin_tick(held_windows, pinned,
    elapsed_windows) and got UnitError on the first flush -- with `int(held) >= cap.pin_windows`,
    the original defect restored at the comparison, as the only form that ran. Nothing executed to
    reveal it, because compose() stops at RUN.process_setup long before the valve; a reviewer found
    it by reading the two surfaces against each other. The repair is applied now: derive.pin_tick
    accumulates Windows and raises on Steps, Flushes and Backwards, and the 32 captured oracle cases
    replay unchanged because they record raw ints and never saw the kind.

RECORD TYPES RETURNED. Valve is DECLARED IN THIS FILE, below; Decision and Caps are P4's. The
parenthetical here used to read "(P4 defines them)" for all three, which is false of the one a
reader can already open, and the Valve line then omitted two of its own declared fields:
  Valve     cap_experts, cap_vocab, the two accumulated pin clocks (Windows), four high-water
            marks, best improving seen, stall-test count, last-called window index, origin,
            COUNTERS (the string-keyed ledger new_valve seeds with the two caps, the two HARD
            ceilings and the two origins -- it is where observe's "the ceilings were frozen onto
            the Valve" actually lands, and therefore where at_hard_ceiling reads them) and GATES
            (the spine/gate.py::Gate readings, which are the DID IT FIRE surface for the two arms)
  Decision  checks, pinned_experts/vocab, held_experts/vocab, improving, lifted, block_reason
  Caps      experts, vocab, and headroom(n) -> max(0, cap - n)
"""
import dataclasses

from spine.lever import Config
from spine import units as U
from spine.gate import Gate


@dataclasses.dataclass
class Valve:
    """The two soft caps, the two pin clocks, and where each cap came from.

    `origin` IS NOT DECORATION. A cap can arrive three ways -- the operator asked for it, a
    checkpoint carried a lifted one, or the sentinel resolved to the hard ceiling -- and the whole
    point of the restore rule is that those are different. The old tree rebuilt `_cap_fab` from the
    environment on every resume, so a run that spent hours lifting handed its successor the starting
    cap back; the first repair took the max instead, which made an explicit CAP_FAB_START=8 lose to
    a checkpoint that had reached 48 and left the startup refusal unreachable on every checkpoint
    written from then on. Recording where the number came from is what makes both of those visible.

    THE PIN CLOCKS ACCUMULATE WINDOWS, not flushes and not Steps. That is repair (a) of the valve
    port: units.py reserves Steps for the LR horizon, and the clock accumulates deltas of `step`,
    which counts windows. So the clock and CAP_PIN_WINDOWS are the same kind and meet without a
    conversion -- and applying the OTHER repair as well would fire the valve 16x too early at
    BATCH_W=16, which is harder to see than the original fault because a valve that fires looks
    like a valve that works.

    EVERY CLOCK DEFAULT IS A FACTORY, AND THE PLAIN FORM WAS A LIVE SHARED-STATE BUG. Written as
    `pin_experts: object = U.Windows(0)` the dataclass evaluates the constructor ONCE, at class
    creation, and hands every Valve in the process the SAME object -- `Valve(1, 2).pin_experts is
    Valve(3, 4).pin_experts` was True, reproduced. dataclasses' own mutable-default refusal does not
    reach it: that refusal triggers on unhashable defaults (list, dict, set) and spine/units.py's
    Clock defines __hash__, so a Clock sails past it. Clock has no mutating method, which is what
    made it survive review -- but it has `__slots__ = ("n",)` and no __setattr__ guard, so the one
    spelling an implementer reaches for while accumulating a clock, `valve.pin_experts.n += dstep`,
    rewrites the CLASS-LEVEL default and every Valve built afterwards starts at that number. That is
    an unearned pin clock arriving from nowhere, which is the M38 family this record exists to fix.
    The factory makes each Valve's clocks its own; `pin_experts = pin_experts + Windows(d)`, which
    Clock.__add__ already returns fresh, stays the correct spelling either way.
    """
    cap_experts: int
    cap_vocab: int
    pin_experts: object = dataclasses.field(default_factory=lambda: U.Windows(0))
    pin_vocab: object = dataclasses.field(default_factory=lambda: U.Windows(0))
    hi_experts: int = 0
    hi_vocab: int = 0
    hi_pin_experts: object = dataclasses.field(default_factory=lambda: U.Windows(0))
    hi_pin_vocab: object = dataclasses.field(default_factory=lambda: U.Windows(0))
    best_improving: float = 0.0
    stall_checks: int = 0
    last_window: int = -1
    origin: tuple = ()
    counters: dict = dataclasses.field(default_factory=dict)
    gates: tuple = ()


def new_valve(cap: Config, *, restored=None):
    """Build the valve. Returns Valve.

    THE HARD CEILINGS ARRIVE AS WIRES: d_expert_slots (from FAB.slots) and d_vocab_slots (from
    LM.vocab_slots). Both starting caps are SENTINELS -- `fab_start == 0` means "start at the hard
    ceiling, i.e. no room to earn" -- and a default computed from another lever is what lever.py
    refuses by construction, so the literal stays 0 and the fallback is the wire. BOTH ROWS ARE IN
    spine/assemble.py's COUPLINGS NOW, verified 2026-09-03 by building CAP and reading the values
    (d_expert_slots -> 4096 from FAB.slots, d_vocab_slots -> 4096 from LM.vocab_slots); before they
    landed the sentinel stood for a number nothing supplied. capacity/levers.py::<module> carried the
    "neither exists yet" sentence long after they did, and it has been corrected there.

    `targets == "off"` MUST ALSO MEAN THE STARTING CAPS ARE NOT APPLIED, and this is the note the
    port must not lose. GROW_CAP_FAB was read at only two places -- the pin test (:7366) and the
    report (:9571) -- while the starting expert cap it nominally governed was read UNGATED at :5209
    and fed the growth clamp at :7444 whatever it said. So GROW_CAP_FAB=0 read as "the expert valve
    is off" while still freezing fabric growth at GROW_CAP_FAB0: an off-switch that does not switch
    the mechanism off (ISSUES.md:1464). One choices-valued lever makes "off" mean one thing at both
    targets and leaves no second boolean to contradict it.

    `restored` is the LIFTED cap from a CKPT Snapshot. THE LIFTED CAP IS EARNED STATE, NOT A KNOB
    (:5221-5227): `_cap_fab` was rebuilt from the environment on every resume, so a run that spent
    hours lifting handed its successor the starting cap back. AN EXPLICIT REQUEST STILL WINS -- the
    first version took the max instead, so CAP_FAB_START=8 against a checkpoint that had reached 48
    restored 48 and made the startup refusal unreachable on every checkpoint written from then on.
    "Did the operator ask" is answered by Config.given(), not by reading os.environ.

    d_mask_dead_rows is the HONESTY PRECONDITION on the vocabulary arm, not a lever here: lifting
    the vocabulary while dead rows are unmasked reserves rows that sit in the softmax denominator
    indexing nothing -- 6144 of them at 8192 reserved against 2048 minted -- so the run measures
    the reservation and not the mechanism. LM owns the output layer, so it arrives as a wire.

    `restored` IS KEYED BY THE START LEVERS' OWN NAMES -- restored["fab_start"] and
    restored["vocab_start"] carry the LIFTED caps -- and that convention is written here because the
    only other end of it, CAP.state, is still a stub. Keying the payload on the Valve's field names
    instead (cap_experts / cap_vocab) would make restored.get("fab_start") return None on every
    resume, silently: the valve would fall through to the sentinel and a run that spent hours
    lifting would resume at its hard ceiling with `origin` truthfully reporting "sentinel". That is
    the M38 family again, and an unwritten key convention between a live body and a stub is exactly
    where it comes back.

    LEVERS READ: targets, fab_start, vocab_start
    WIRES READ: d_expert_slots, d_vocab_slots, d_mask_dead_rows
    DID IT FIRE: THREE SURFACES, and this line used to name one of them with the wrong shape and a
                 source set the body never produced -- it said "for each target, (start, source)"
                 for a field that carries the two SOURCES alone, and named a closed set of three
                 ("lever", "hard ceiling (sentinel 0)", "checkpoint") of which the body spells none
                 and to which "off" is a fourth. What is actually produced:
                 (1) Valve.origin -- (experts_source, vocab_source); the two STARTS are the Valve's
                     own cap_experts / cap_vocab, and the counters below pair them. The sources are
                     a closed set of four: "off (valve disabled; ...)" when targets is off,
                     "operator (<lever>=<n>)" and its sentinel form "operator (<lever>=0, the
                     sentinel) -> hard ceiling <n>", "checkpoint (lifted to <n>)", and
                     "sentinel 0 -> hard ceiling <n>". A cap that came from the wrong place is
                     visible because the four are spelled differently.
                 (2) Valve.counters -- cap.targets, the two caps, the two hard ceilings and the two
                     origins, which is the pairing (1) leaves to the reader.
                 (3) Valve.gates -- cap.valve and cap.vocab_arm_honest, each carrying all THREE of
                     spine/gate.py's states. They are the reason this entry point builds Gates at
                     all and leaving them out of this line made the one that was WRONG invisible to
                     every reader of the contract.
    """
    cap = cap.owned_by("CAP")
    hard_experts = int(cap.d_expert_slots)      # WIRES READ HERE -- the two hard ceilings
    hard_vocab = int(cap.d_vocab_slots)
    mask_dead = bool(cap.d_mask_dead_rows)
    targets = str(cap.targets)

    def _resolve(given, asked, hard, what):
        """The sentinel, the operator, and the checkpoint, in that order of precedence."""
        if targets == "off":
            # "off" MEANS THE STARTING CAPS ARE NOT APPLIED EITHER, and this is the note the port
            # must not lose. GROW_CAP_FAB read as "the expert valve is off" while the starting cap
            # it nominally governed was read UNGATED and fed the growth clamp anyway -- an
            # off-switch that does not switch the mechanism off. One choices-valued lever makes
            # "off" mean one thing at both targets, with no second boolean to contradict it.
            return hard, "off (valve disabled; the cap is the hard ceiling)"
        if given:
            # AN EXPLICIT REQUEST WINS OVER A RESTORED CAP. Taking the max instead made
            # CAP_FAB_START=8 lose to a checkpoint that had reached 48, which left the startup
            # refusal unreachable on every checkpoint written from then on. "Did the operator ask"
            # is answered by Config.given(), never by reading the environment.
            #
            # AND THE SENTINEL IS A PROPERTY OF THE VALUE, NOT OF WHERE THE VALUE CAME FROM. This
            # branch used to return `int(asked)` unconditionally, so 0 meant "the hard ceiling" when
            # it arrived from the declared default and "a soft cap of literally zero" when the
            # operator typed the same number: CAP_TARGETS=both CAP_FAB_START=0 resolved cap_experts
            # to 0 against a hard ceiling of 4096 -- reproduced. A soft cap of 0 is C30 by
            # construction: `min(_nb, cap - fab.n())` is negative on the first flush, growth is
            # frozen for the whole run, and nothing in the log says so. One number may not mean two
            # things because of its provenance, and the lever's own help text spends 0 on the
            # sentinel ("0 means start at the hard ceiling, i.e. no room to earn"), so the sentinel
            # is what an explicit 0 asks for. The REQUEST still wins over the checkpoint -- an
            # operator asking for the hard ceiling is asking to discard a lifted cap -- and the
            # origin string records that this is where the number came from.
            if int(asked) == 0:
                return hard, f"operator ({what}=0, the sentinel) -> hard ceiling {hard}"
            return int(asked), f"operator ({what}={asked})"
        if restored is not None and restored.get(what) is not None:
            # THE LIFTED CAP IS EARNED STATE, NOT A KNOB. Rebuilding it from the environment on
            # every resume handed a run that had spent hours lifting its starting cap back.
            return int(restored[what]), f"checkpoint (lifted to {int(restored[what])})"
        # THE SENTINEL. 0 means START AT THE HARD CEILING -- no room to earn -- and it must be a
        # sentinel rather than a literal because lever.py refuses a default computed from another
        # lever, so the number it stands for can only arrive as the wire.
        return hard, f"sentinel 0 -> hard ceiling {hard}"

    # Config.given() returns the WHOLE map of what the environment actually supplied; membership in
    # it is the answer to "did the operator ask", and it is the only correct source -- reading
    # os.environ here would be the L2 violation the whole spine removes.
    asked = cap.given()
    ce, oe = _resolve("fab_start" in asked, cap.fab_start, hard_experts, "fab_start")
    cv, ov = _resolve("vocab_start" in asked, cap.vocab_start, hard_vocab, "vocab_start")

    valve = Valve(cap_experts=ce, cap_vocab=cv, origin=(oe, ov))
    valve.counters = {
        "cap.targets": targets,
        "cap.cap_experts": ce, "cap.cap_vocab": cv,
        "cap.hard_experts": hard_experts, "cap.hard_vocab": hard_vocab,
        "cap.origin_experts": oe, "cap.origin_vocab": ov,
    }
    # THE HONESTY PRECONDITION ON THE VOCABULARY ARM, and it is LM's flag, not a lever here.
    # Lifting the vocabulary while dead rows are unmasked reserves ids that sit in the softmax
    # denominator indexing nothing -- 6144 of them at 8192 reserved against 2048 minted -- so the
    # run measures the reservation instead of the mechanism.
    #
    # THREE STATES, AND THE PREDICATE IS "CAN A VOCABULARY LIFT HAPPEN AT ALL", NOT "IS THE MASK
    # ON". This gate asks a strictly narrower question than cap.valve above -- IF a vocabulary lift
    # could happen, would it be honest -- and that question is INAPPLICABLE on every `targets` value
    # whose vocabulary arm is not armed, which is `off` and `experts` alike. Written as
    # `mask_dead or targets == "off"` it read the mask on runs where nothing could ever reserve a
    # row, and reached the opposite verdict from its sibling two lines above on the SAME condition:
    # at the shipped defaults (CAP_TARGETS=off, LM_MASK_DEAD_ROWS=False) cap.valve printed
    # UNREACHABLE while this one printed "armed, did not fire (False vs True)" -- a reachable,
    # unfired reading for a mechanism that cannot fire, which is the exact collapse spine/gate.py
    # exists to refuse. It was wrong at the other end too: at CAP_TARGETS=experts with the mask ON
    # it printed FIRED, certifying as honest a vocabulary lift the run will never attempt, and with
    # the mask OFF it printed UNREACHABLE under the reason "the vocabulary arm can lift", which is
    # false on that configuration. Reachability is therefore keyed on the ARM, and the mask is only
    # consulted once the arm is live.
    #
    # THE ARITHMETIC ON THE UNREACHABLE ARM IS THE ONE THAT DECIDED IT. spine/gate.py::Gate.line
    # prints value-vs-threshold on every arm on purpose, so the numbers must be the ones the verdict
    # rests on: when the arm is not armed that is `targets` against the two values that arm it, the
    # same shape cap.valve uses, and the mask's value is carried in the reason so nothing is hidden.
    if targets not in ("vocab", "both"):
        vocab_arm = Gate(
            "cap.vocab_arm_honest", False, targets, "vocab|both", reachable=False,
            reason=f"CAP_TARGETS={targets}: the valve's vocabulary arm is not armed, so no row is "
                   f"ever reserved and there is nothing for the dead-row mask to make dishonest. "
                   f"LM_MASK_DEAD_ROWS={mask_dead} is recorded and not tested. Reported unreachable "
                   f"rather than as an unmet condition, which would send an operator to set "
                   f"LM_MASK_DEAD_ROWS=1 and change nothing observable.")
    elif mask_dead:
        vocab_arm = Gate("cap.vocab_arm_honest", True, mask_dead, True)
    else:
        vocab_arm = Gate(
            "cap.vocab_arm_honest", False, mask_dead, True, reachable=False,
            reason="LM_MASK_DEAD_ROWS=0: the vocabulary arm can lift, but every row it reserves "
                   "sits unmasked in the softmax denominator, so what the run would measure is "
                   "the reservation and not the valve. Declared dishonest rather than lifted "
                   "silently.")
    valve.gates = (
        Gate("cap.valve", targets != "off", targets, "off")
        if targets != "off" else
        Gate("cap.valve", False, targets, "off", reachable=False,
             reason="CAP_TARGETS=off: both caps sit at their hard ceilings and no lift can happen. "
                    "Reported unreachable rather than as 0 lifts, which would read as a valve that "
                    "ran and never fired -- the exact confusion this mechanism's own history is."),
        vocab_arm,
    )
    return valve


def observe(cap: Config, valve, *, elapsed_windows, live_experts, live_vocab, improving,
            observations, blackout):
    """One valve evaluation. Called ONCE PER FLUSH, after the optimizer step. Returns Decision.

    `elapsed_windows` is units.Windows -- how many WINDOWS have elapsed since the last call, which
    at the flush cadence is batch_windows of them. It is supplied by RUN's RunClock, whose
    last-called index is SEEDED AT THE RESUMED STEP. That is the M38 fix: `_pin_prev = [0]` on a
    resume (:5252) against `_dstep = step - _pin_prev[0]` (:7368) means the first flush computes
    dstep = N, so a population at its cap banks N windows it never spent pinned -- 20,000 satisfied
    instantly, and the first lift of the session unearned.

    THE TWO CONDITIONS, BOTH REQUIRED. Pressure alone grows a run that is still learning (waste);
    stall alone grows a run with plenty of unused room (dilution).
      pinned:  live_experts >= valve.cap_experts / live_vocab >= valve.cap_vocab, accumulated by
               derive.pin_tick and DECAYED while below -- not an unbroken run of it, because
               culling drops the population below its cap within a thousand steps and the first
               version restarted the clock every time.
      stalled: abs(improving) < cap.stall_band. A BAND, NOT A ONE-SIDED THRESHOLD. `improving` is
               (slow - fast)/|slow|, NEGATIVE when the loss is RISING, and the shipped gate
               `improving < GROW_CAP_PLATEAU` passed for every negative value there is -- the valve
               fired hardest exactly when the run was degrading worst and said so in its own log
               line ("the loss has stalled (improving -0.1937 < 0.002)"). Three of the five expert
               lifts in the 0.75 GB run went to a run that was getting worse.
      warmed:  observations >= 1000 -- a PROPERTY of the hardcoded 0.998 EMA rate (two time
               constants), deliberately NOT a knob. The old outer gate read
               `fabgrow.n >= GROW_CAP_EVERY`, i.e. 20,000 CALLS = 320,000 windows at BATCH_W=16,
               and round11 pinned 42,425 with the pin clock already fixed and still lifted nothing
               because this second gate never opened -- two clocks-in-the-wrong-unit faults, one
               masking the other.
      quiet:   not blackout. note_shift marks retok, epoch resample and LR restart -- "the loss
               jump is OURS, not the data's". The valve read the same fast/slow pair and IGNORED
               the flag, so it fired on the artefact and THEN CAUSED THE NEXT ONE: a vocabulary
               lift mints tokens, the retok rebuilds the stream, the loss jumps, the jump reads as
               a stall, and the stall authorises the next lift. The 0.75 GB run walked 2048 -> 8192
               in 19 lifts that way. This is a CAP-SIDE CONDITION and there is deliberately no
               lever to switch it off.

    The lift is derive.lift_to(cap, cap.lift, cap.lift_min), the shipped module-level arithmetic
    covered by cap_test.py's known-answer table; it replays sched_ctl's five real lifts
    3000 -> 3240 -> 3499 -> 3778 -> 4080 -> 4406. lift_min is not decoration: at cap 12,
    int(0.08*12) = 0 and without the floor the cap can never move again on any evidence --
    reachable in the 200-step empty-environment CPU run this rebuild launches with.

    LEVERS READ: targets, lift, lift_min, pin_windows, stall_band
    WIRES READ: none (the ceilings were frozen onto the Valve at new_valve)
    DID IT FIRE: Decision carries, on EVERY call: checks (the stall test RAN -- distinct from it
                 passing), pinned_experts/pinned_vocab, held_experts/held_vocab (Windows),
                 improving, and a BLOCK REASON from a closed set: targets_off | not_pinned |
                 warmup(observations/1000) | blackout | not_stalled(|improving|/band) |
                 threshold(held/pin_windows) | at_hard_ceiling. This is the direct repair for the
                 recorded failure at :7372-7380: "0 lifts" ALONE CANNOT DISTINGUISH "never full"
                 FROM "never plateaued", and those have completely different fixes.
    """
    cap = cap.owned_by("CAP")
    raise NotImplementedError(
        "CAP.observe: P4 (capacity) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section CAP.")


def caps(cap: Config, valve):
    """The current soft caps. Returns Caps(experts, vocab), carrying headroom(n) -> max(0, cap - n).

    THE CLAMP MUST NOT GO NEGATIVE, AND THE FIX IS HERE RATHER THAN AT THE CALL SITE.
    `_nb = min(_nb, _cap_fab[0] - fab.n())` (:7446) is negative the moment the population exceeds
    the soft cap, which freezes growth FOR THE ENTIRE RUN with nothing in the log saying so -- the
    trigger counts still increment and the pin counter reads exactly as it would on a population
    legitimately at its cap (C30). Unreachable on a fresh run; entirely reachable on a resume,
    where the population comes from the checkpoint (523 in the run this was written for) against a
    gc arm's 160: -363, and the run trains to completion having grown nothing on a configuration
    whose entire purpose is to study growth. `headroom` exists so the negative form cannot be
    WRITTEN at a call site.

    LEVERS READ: targets
    WIRES READ: none
    DID IT FIRE: caps.experts / caps.vocab as one-shot readings per flush, printed beside
                 fab.declined_cap and tok.mint_ceiling_refused
    """
    cap = cap.owned_by("CAP")
    raise NotImplementedError(
        "CAP.caps: P4 (capacity) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section CAP.")


def startup_refusals(cap: Config, valve, *, live_experts):
    """Refusals that need two packages' numbers. Returns a list of strings.

    (1) A SOFT CAP BELOW THE POPULATION freezes growth for the run, silently (C30). Refuse, naming
        cap.fab_start, the population, and where the population came from.
    (2) THE IRREDUCIBLE COUPLING, DECLARED RATHER THAN REMOVED: the soft cap must sit at or below
        the cull's settling point, which arrives as the wire d_operating_population (FAB.pressure x
        FAB.slots, through the SAME derive.operating_population call the fabric's own row uses).
        Above it the population never pins, the pin clock never accumulates, and the valve is dead
        while looking armed.

    LEVERS READ: fab_start, targets
    WIRES READ: d_operating_population
    DID IT FIRE: the returned list; an empty list is a positive result and is printed as one
    """
    cap = cap.owned_by("CAP")
    _ = cap.d_operating_population    # WIRE READ HERE -- the cull's settling point
    raise NotImplementedError(
        "CAP.startup_refusals: P4 (capacity) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section CAP.")


def state(valve):
    """The lifted caps AND the two pin clocks AND the high-water marks, for the checkpoint.

    Adding the PIN CLOCKS is a change from the old tree and it is half of the M38 fix; the lifted
    caps were already saved at :5423 and the clocks were not, so the valve resumed with an earned
    ceiling and an unearned clock.

    LEVERS READ: none. Pure read of `valve`.
    WIRES READ: none
    DID IT FIRE: valve.counters["cap.state_written"]. THE KEY IS NAMED BECAUSE THE RECORD HAS NO
                 FIELD FOR IT: this line used to read `valve.state_written`, which is neither a
                 declared field of Valve nor produced anywhere, so the one signal saying the
                 checkpoint carried the valve's earned state had no home a reader could find. The
                 ledger dict is that home -- new_valve already seeds it and CAP.counters reads it --
                 and setting an ad-hoc attribute on the dataclass instead would put half this
                 package's DID IT FIRE surface somewhere the record type does not describe.
    """
    raise NotImplementedError(
        "CAP.state: P4 (capacity) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section CAP.")


def restore(cap: Config, valve, state):
    """Put the lifted caps, the pin clocks and the high-water marks back; symmetric with state().

    An EXPLICIT operator request still wins over the checkpoint -- see new_valve.

    LEVERS READ: targets, fab_start, vocab_start
    WIRES READ: none
    DID IT FIRE: valve.counters["cap.state_restored"] and valve.counters["cap.state_refused"] --
                 same repair as CAP.state above: both names were declared against no field of Valve
                 and no producer, and a refusal that cannot be counted is the state this package
                 exists to make readable. "Refused" is the third state here and not an error: a
                 checkpoint whose lifted cap loses to an explicit operator request is refused, on
                 purpose, and that has to be countable separately from "no checkpoint".
    """
    cap = cap.owned_by("CAP")
    raise NotImplementedError(
        "CAP.restore: P4 (capacity) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section CAP.")


def counters(cap: Config, valve):
    """The DID IT FIRE ledger: lifts_experts, lifts_vocab, the four high-water marks, stall_checks,
    best_improving, and THE BLOCK-REASON HISTOGRAM.

    The histogram is the point. round11 pinned 42,425 against a threshold of 20,000, lifted
    nothing, and left no evidence of which of the two remaining conditions refused.

    LEVERS READ: targets, lift, lift_min, pin_windows, stall_band, fab_start, vocab_start
    WIRES READ: none
    DID IT FIRE: this call IS the DID IT FIRE surface for the package
    """
    cap = cap.owned_by("CAP")
    raise NotImplementedError(
        "CAP.counters: P4 (capacity) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section CAP.")
