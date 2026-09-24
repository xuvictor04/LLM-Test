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
    reveal it, because compose() THEN stopped at RUN.process_setup, long before the valve; a
    reviewer found it by reading the two surfaces against each other.
    THAT IS NO LONGER WHERE IT STOPS, AND THIS SENTENCE SAID IT WAS UNTIL 2026-09-04. Re-measured
    by running it: RUN.process_setup has a body, and `compose(environ={})` now halts on the 29th of
    the 40 rows in spine/compose.py::ASSEMBLY_ORDER, at CAP.startup_refusals -- which is PAST the
    valve's own row, so new_valve IS built on every compose() today and all THREE of its Gates are
    readable without writing a line -- THREE, corrected 2026-09-05: this said "both its Gates" from
    the edit that added cap.clamp, a count-in-prose falsified in the file that respells "EIGHT keys
    to TEN" twice for exactly this reason and that no check catches, because K13 reads digits and
    "both" is a word. Three more copies of the same stale claim were corrected in
    docs/04_CONTRACT.md in the same edit; a claim about where the root stops is a copy of a fact and
    rots exactly the way a count does, and the reason it survived four places is that the count
    checks read digits and this one is a symbol name. The repair is applied now: derive.pin_tick
    accumulates Windows and raises on Steps, Flushes and Backwards, and the 32 captured oracle cases
    replay unchanged because they record raw ints and never saw the kind.

RECORD TYPES RETURNED. Valve is DECLARED IN THIS FILE, below; Decision and Caps are P4's. The
parenthetical here used to read "(P4 defines them)" for all three, which is false of the one a
reader can already open, and the Valve line then omitted two of its own declared fields:
  Valve     cap_experts, cap_vocab, the two accumulated pin clocks (Windows), four high-water
            marks, best improving seen, stall-test count, last-called window index, origin,
            COUNTERS (the string-keyed ledger new_valve seeds with TEN keys: `cap.targets`, the
            two caps, the two HARD ceilings, the two origins, `cap.mask_dead_rows` -- the honesty
            precondition on the vocabulary arm -- and the two CLAMP COUNTERS
            `cap.lifts_clamped_experts` and `cap.lifts_clamped_vocab`, seeded at 0 here and
            incremented by observe. This ledger is where observe's "the ceilings were frozen
            onto the Valve" actually lands, and therefore where at_hard_ceiling,
            dead_rows_unmasked and the clamp read them. THE COUNT IS SPELLED BECAUSE THIS LINE HAS
            NOW OMITTED KEYS TWICE: it named six of the eight there were then until 2026-09-04,
            missing `cap.targets` from the start and `cap.mask_dead_rows` from the edit that added
            it -- the same failure as the two fields this paragraph was written to fix, one level
            down. K11 resolves provenance tokens against RECORD TYPES blocks, so a key that is
            seeded and not declared here is a key no consumer can be shown to be entitled to) and
            GATES (the spine/gate.py::Gate readings, which are the DID IT FIRE surface for the two
            arms and, since the clamp ruling, for what the valve did with the lifts it took)
  Decision  checks, pinned_experts/vocab, held_experts/vocab, improving, lifted, clamped,
            block_reason. `clamped` is the per-flush half of the clamp reading and is NOT a second
            spelling of `lifted`: a clamped lift IS lifted, at a reduced size, and the two ledgers
            answer "did the cap move" and "was the move held at the ceiling" separately.
  Caps      experts, vocab, and headroom(n) -> max(0, cap - n)
"""
import dataclasses

from spine.lever import Config, LeverError
from spine import units as U
from spine import derive
from spine.gate import Gate


def _clamped_lift(cap_value, hard, frac, floor):
    """The lift the valve ACTUALLY APPLIES: derive.lift_to held at the hard ceiling. UNIT: slots.

    THE OWNER RULED THE OVERSHOOT ON 2026-09-04 -- .rework/DECISIONS.md D16, "let's soft clamp if a
    ceiling is overshot, until it goes down" -- and this is the one place that arithmetic is
    written. A soft cap set
    just below its hard ceiling makes the FIRST earned lift land above the ceiling
    (derive.lift_to(4095, 0.08, 8) = 4422 against a ceiling of 4096), and the ruling is CLAMP
    rather than REFUSE: the lift is taken and the result is held at the ceiling, so the evidence
    that earned it is spent instead of wasted. The reading of "until it goes down" this implements,
    the two readings that were open, and how an owner would tell them apart in a report are written
    out in capacity/api.py::observe, which is the entry point the ruling governs.

    ONE SPELLING, BECAUSE TWO WOULD BE TWO ANSWERS. observe is where this WILL be applied, cap.valve
    prints what this returns, and cap.clamp counts what this dropped. THE FIRST OF THOSE THREE IS A
    CONTRACT AND NOT A DESCRIPTION OF THE TREE, and this line said it in the present tense until
    2026-09-05: capacity/api.py::observe is `raise NotImplementedError` today, so nothing in a run
    applies this function, cap.lifts_clamped_experts and cap.lifts_clamped_vocab are seeded at 0 and
    never incremented, and Decision.clamped is never set by any code that exists. EVERY EXECUTING
    CALLER IS INSIDE new_valve -- `_lift_moves`, `_one_lift`, and the mask-and-inert test on the
    vocabulary arm -- i.e. the startup Gate lines, which is the correct state for a frozen-contract
    package and is exactly why the sentence has to be written as an obligation on P4 rather than as
    a report. A reader who takes "observe applies this" for a measurement concludes that the valve
    clamps in a run; it does not yet.
    new_valve's `_lift_moves` already makes
    the argument for calling the shipped function rather than restating its arithmetic -- "a
    reimplementation of the comparison here could disagree with the lift the valve actually takes,
    and then this gate and the mechanism would be two sources of truth" -- and a clamp written
    inline at three sites is that objection three times over.

    THE `max` IS A GUARD ON A REACHABLE INPUT, NOT DECORATION, AND WITHOUT IT THIS FUNCTION WOULD
    LOWER A CAP -- the one thing this valve may never do. `min(lift_to(...), hard)` is a RAISE only
    from BELOW the ceiling. From a cap already at or above it the min IS the ceiling and the cap
    would come DOWN: at CAP_FAB_START=5000 against FAB_SLOTS=4096 -- an ordinary environment
    setting, resolved by new_valve to cap_experts = 5000 with origin "operator (fab_start=5000)" --
    a bare min would return 4096 and take 904 slots off a cap on the flush it was supposed to
    raise, which is the C30 inversion (a clamp that goes the wrong way with nothing in the log)
    arriving through the repair for a different one. observe never reaches that state, because
    at_hard_ceiling refuses `cap >= hard` before any lift is computed; the guard is here anyway
    because the refusal is a caller's discipline and this is where the arithmetic lives.
    THE RETURN IS THEREFORE ALWAYS AT OR ABOVE `cap_value`, on every input, and Caps.headroom is
    the precedent for putting the property in the function rather than in a rule about call sites.
    """
    return max(int(cap_value), min(derive.lift_to(cap_value, frac, floor), int(hard)))


# THE CLOSED SET IS A PARTITION, AND BOTH HALVES ARE LOAD-BEARING. It was one flat tuple named in
# one error message and tested by nothing -- a closed set that closed nothing, so a kind with a
# branch and no tuple entry ran anyway and a tuple entry with no branch advertised itself as
# supported while raising. capacity/api.py::_clamp_blocked_clause now tests membership BEFORE it
# dispatches, so the tuple decides what is accepted, and its fall-through says the other thing.
# THE SPLIT IS THE SECOND JOB AND IT IS WHY THIS IS A PARTITION RATHER THAN A FLAG. `lifts` on the
# Gate counts lifts TAKEN. Five of the six grounds mean no lift is ever taken on that arm -- three
# because none is EARNED, and at_ceiling / refused_unmasked because every earned one is REFUSED
# before it is applied. `inert` is the one ground on which a lift IS taken: it is earned, applied,
# and moves nothing. capacity/api.py::_clamp_gate reads that difference to decide whether a live
# ledger showing lifts CONTRADICTS the startup analysis or AGREES with it, which is a question the
# gate got wrong by not asking it.
_CLAMP_KINDS_NO_LIFT_TAKEN = ("unarmed", "nonpositive", "never_pins", "at_ceiling",
                              "refused_unmasked")
_CLAMP_KINDS_LIFT_TAKEN = ("inert",)
_CLAMP_BLOCKED_KINDS = _CLAMP_KINDS_NO_LIFT_TAKEN + _CLAMP_KINDS_LIFT_TAKEN


def _clamp_blocked_clause(arm, kind, f):
    """ONE ARM, ONE SENTENCE, IN THE CLAMP'S OWN WORDS. Returns a str.

    `kind` is one of the closed set capacity/api.py::_CLAMP_BLOCKED_KINDS, and an unknown one raises
    rather than printing a blank clause -- a gate that silently says nothing about an arm is the
    absent-versus-inert confusion this whole surface exists to refuse. THE SET IS TESTED AND NOT
    MERELY QUOTED: until 2026-09-05 the tuple appeared only inside the fall-through's message, so a
    kind with a branch here and no entry there ran, and the message's "the closed set is ..." was a
    claim about a tuple that decided nothing. The membership test below is what makes it decide, and
    the fall-through now reports the other failure -- a name IN the set with no clause written for
    it -- as the different defect it is.

    THIS FUNCTION EXISTS BECAUSE THE PREVIOUS VERSION OF cap.clamp BORROWED cap.valve's SENTENCES
    AND PRINTED A CONTRADICTION WITH THEM. The unreachable arm opened "no lift can be earned at all
    on this configuration" and then spliced in the `dead` clauses new_valve writes for cap.valve --
    two of which say the opposite in the same breath: "the vocabulary arm has room to earn (1000
    against a hard ceiling of 4096) ... so observe refuses every lift it earns by name as
    dead_rows_unmasked", and "the expert arm's soft cap is 12 and ONE EARNED LIFT DOES NOT MOVE IT".
    A sentence saying nothing can be earned followed by a clause saying what IS earned and then
    refused. Measured on a 25,344-cell sweep of the lever space: 3,464 cells printed one.

    THE REPAIR IS A DISTINCTION AND NOT A REWORDING, because the two gates are not asking the same
    question. THERE IS MORE THAN ONE REASON A LIFT DOES NOT MOVE A CAP and the borrowed prose
    collapsed them into one sentence; .rework/DECISIONS.md D16 names two of them itself -- a lift
    refused as dead_rows_unmasked, and derive.lift_to returning the cap unchanged -- and says they
    "must not be mistaken for a clamp". A clamp needs three things IN ORDER -- a lift EARNED, that
    lift APPLIED rather than refused, and its unclamped arithmetic ABOVE the hard ceiling -- and
    each `kind` below is the first of the three to fail:
      unarmed          CAP_TARGETS does not arm the arm. Nothing is EARNED. (D16's UNREACHABLE row,
                       and D15's ground.)
      nonpositive      the soft cap is at or below zero, where this valve reports the arm dead
                       before any lift is considered. Nothing is EARNED.
      never_pins       the soft cap is above the cull's settling point, so the population never
                       reaches it and never pins. Nothing is EARNED.
      at_ceiling       the cap is already at or above the hard ceiling: lifts are EARNED and observe
                       REFUSES each by name as at_hard_ceiling before computing one.
      refused_unmasked LM_MASK_DEAD_ROWS is off: lifts are EARNED and observe REFUSES each by name
                       as dead_rows_unmasked. `inert_too` records whether the MASK IS THE ONLY thing
                       in the way -- this branch is tested before the no-move one, so an arm can be
                       both, and a reader told only about the mask is told to set a lever that does
                       not change the answer.
      inert            derive.lift_to returns the cap unchanged: lifts are EARNED and APPLIED, and
                       move nothing, so they never approach a ceiling to be held at.
    THE TWO GATES SHARE A COMPUTED VALUE AND NOT A SENTENCE. new_valve builds these records in the
    same branches that build cap.valve's prose, off the same facts, so the two lines cannot disagree
    about the configuration -- and each writes its own words about it, because they are reporting
    different events. Sharing the sentence is how the contradiction got in.

    `f` is the branch's numbers, keyed by name; every key a kind reads is written by new_valve in
    the same statement that appends the record.
    """
    if kind not in _CLAMP_BLOCKED_KINDS:
        raise ValueError(f"cap.clamp: unknown blocked-kind {kind!r}; the closed set is "
                         f"{_CLAMP_BLOCKED_KINDS}")
    if kind == "unarmed":
        return (f"({arm}) NOT ARMED, so NO LIFT IS EVER EARNED on it: CAP_TARGETS="
                f"{f['targets']} does not arm this arm, and a clamp is a property of a lift")
    if kind == "nonpositive":
        # THE ORIGIN IS PART OF THE EQUATION AND DROPPING IT MADE THE CLAUSE FALSE ON THE RESTORE
        # PATH. Printing `{lever}={given}` alone reads "the soft cap is -3 (CAP_FAB_START=0)" when
        # the cap came from a checkpoint -- and 0 is the documented SENTINEL for "start at the hard
        # ceiling", the opposite of -3, so the parenthesis names a lever value that did not produce
        # the cap beside it. capacity/api.py::new_valve._resolve's four origin strings exist so a cap
        # which came from the wrong place is visible, and cap.valve's own nonpositive prose prints
        # both; this clause is the one surface that hid it.
        return (f"({arm}) NO LIFT IS EVER EARNED: the soft cap is {f['cap']} ({f['lever']}="
                f"{f['given']}, {f['origin']}), at or below zero, which this valve reports dead "
                f"before any lift is considered -- a cap there makes the clamp that reads it "
                f"negative (C30)")
    if kind == "never_pins":
        return (f"({arm}) NO LIFT IS EVER EARNED: the soft cap of {f['cap']} sits above the cull's "
                f"settling point of {f['operating']}, so the population never reaches it, never "
                f"pins, and the pin clock never accumulates")
    if kind == "at_ceiling":
        return (f"({arm}) EARNED AND REFUSED, WHICH IS NOT CLAMPED: the cap of {f['cap']} is "
                f"already at or above its hard ceiling of {f['hard']}, so observe refuses by name "
                f"as at_hard_ceiling BEFORE any lift is computed. A refused lift is never applied "
                f"and so can never be held at a ceiling, and a clamp raises a cap only from BELOW "
                f"one -- from {f['cap']} it would be a lowering, which this valve may never do")
    if kind == "refused_unmasked":
        return (f"({arm}) EARNED AND REFUSED, WHICH IS NOT CLAMPED: the cap of {f['cap']} is below "
                f"its hard ceiling of {f['hard']}, so lifts ARE earned here, and "
                f"LM_MASK_DEAD_ROWS={f['mask']} makes observe refuse every one of them by name as "
                f"dead_rows_unmasked. Those refusals are the block-reason histogram's number and "
                f"cap.vocab_arm_honest's line; a lift that is never applied cannot be held"
                + (f". THE MASK IS NOT THE ONLY THING IN THE WAY HERE: derive.lift_to({f['cap']}, "
                   f"CAP_LIFT={f['lift']}, CAP_LIFT_MIN={f['lift_min']}) = {f['cap']}, so even with "
                   f"LM_MASK_DEAD_ROWS=1 the applied lift would move nothing and still reach no "
                   f"ceiling" if f.get("inert_too") else ""))
    if kind == "inert":
        return (f"({arm}) EARNED AND APPLIED AND MOVES NOTHING, WHICH IS NOT CLAMPED: the cap of "
                f"{f['cap']} is below its hard ceiling of {f['hard']}, so an earned lift IS "
                f"applied -- and derive.lift_to({f['cap']}, CAP_LIFT={f['lift']}, CAP_LIFT_MIN="
                f"{f['lift_min']}) = {f['cap']} returns it unchanged, so the applied cap never "
                f"approaches the ceiling and there is nothing for the clamp to hold")
    raise ValueError(f"cap.clamp: blocked-kind {kind!r} is declared in "
                     f"capacity/api.py::_CLAMP_BLOCKED_KINDS and no clause is written for it here, "
                     f"so the closed set advertises a kind this function cannot render. The set is "
                     f"{_CLAMP_BLOCKED_KINDS}")


def _clamp_gate(arith, lifts, clamped, *, dead_facts=None):
    """The clamp's DID IT FIRE reading. Returns one spine/gate.py::Gate named cap.clamp.

    FOUR STATES OUT OF A RECORD THAT HAS THREE VERDICTS, AND THE FOURTH IS CARRIED IN THE NUMBERS
    RATHER THAN BY COLLAPSING TWO WORDS INTO ONE. A clamped lift is neither a clean fire nor a
    refusal, and this valve's whole history is mechanisms that fired or did not without saying
    which, so the four have to stay four:
      UNREACHABLE                  no lift can be HELD AT A HARD CEILING on this configuration --
                                   a clamp is a property of an APPLIED lift that overshoots, so
                                   where that cannot happen the question is INAPPLICABLE and not
                                   merely unmet. THIS IS NOT "no lift can be earned": some of the
                                   ways an arm arrives here EARN lifts and lose them later, and one
                                   of those EARNS AND APPLIES them. `dead_facts` says, per arm,
                                   which of the clamp's three preconditions failed first and on
                                   which lever and value, and the sentence is written by
                                   capacity/api.py::_clamp_blocked_clause -- by this gate, about
                                   this gate's event, and never borrowed from another one.
      armed, 0 clamped of 0 lifts  no lift was earned. The mechanism was live and the condition was
                                   not met, which is a MEASUREMENT and the state spine/gate.py
                                   exists to keep separate from the one above.
      armed, 0 clamped of N lifts  N lifts were earned and every one was applied IN FULL.
      FIRED, M clamped of N lifts  M of the N earned lifts were CLAMPED at the hard ceiling.
    `value` is `<clamped> clamped of <lifts> lift(s) taken` on every arm, so the two middle states
    are told apart by a number the line already prints -- Gate.line renders `(value vs threshold)`
    for exactly this, and its own record says the numbers are there "so the reader can do the
    arithmetic themselves".
    AND `clamped > lifts` IS REFUSED RATHER THAN PRINTED. A clamped lift is a lift TAKEN, so the
    inequality is impossible in a correct ledger; entering the FIRED arm on `if clamped:` alone
    rendered "3 of 0 earned lift(s) were CLAMPED at the hard ceiling" from `(arith, 0, 3)`, a false
    equation on the surface whose whole subject is false equations. It was never reachable through a
    build -- new_valve passes 0 and 0 by construction -- and CAP.counters, which HAS A BODY and is
    called by spine/loop.py's R stage (this clause said it was a stub until 2026-09-22), calls this
    frozen surface with a live ledger, which is when an incoherent pair becomes reachable. The refusal is a ValueError, on capacity/api.py::_clamp_blocked_clause's
    precedent: a DID IT FIRE line handed numbers that cannot both be true fails loudly.

    HOW THIS MAPS ONTO .rework/DECISIONS.md D16's TABLE, SAID OUT LOUD BECAUSE THE TWO USES OF THE
    WORD "FIRED" ARE NOT THE SAME USE. D16 lists the four states with what already owns each: "no
    lift earned" is the armed-but-0 arm, "lift earned, applied in full" is FIRED, "lift earned,
    CLAMPED at the ceiling" is NEW and needs "its own counter and its own Gate arm", and "no lift can
    ever be earned" is UNREACHABLE per D15. Those ownerships are about THE LIFT, whose fired arm is
    lifts_experts / lifts_vocab. This gate reports THE CLAMP, so its FIRED means a lift was CLAMPED
    -- the state D16 calls new -- and the ordinary applied-in-full lift is the `0 clamped of N`
    reading here. Reading D16's "fired" onto this gate's verdict would say a clamped lift is an
    ordinary one, which is the collapse the ruling was written to prevent.
    ITS UNREACHABLE ROW DOES NOT TRANSFER EITHER, AND THAT IS THE ERROR THIS GATE SHIPPED WITH.
    D16's fourth row is "no lift can ever be earned | CAP_TARGETS excludes the arm", which is the
    ground for the LIFT gate's unreachability. This gate borrowed the words as well as the verdict
    and printed them on configurations where CAP_TARGETS arms the arm and lifts ARE earned -- and
    then, in the same sentence, printed cap.valve's clause saying so. The verdict transfers, because
    where no lift is earned none can be clamped; the WORDS do not, because the converse is false:
    a clamp is also impossible on an arm whose earned lifts are refused, and on one whose applied
    lifts move nothing. D16 names both of those in its own next paragraph as cases that "must not be
    mistaken for a clamp" -- reporting them AS "no lift can be earned" is that mistake in the other
    direction. capacity/api.py::_clamp_blocked_clause holds those grounds apart.
    AND THAT IS AN EXTENSION OF D16, NOT A READING OF IT, WHICH IS THE OWNER'S TO CONFIRM AND NOT
    THIS DOCSTRING'S TO SETTLE. D16's table has exactly ONE unreachable row, on ONE ground:
    `CAP_TARGETS` excludes the arm. This gate reports UNREACHABLE on all six grounds in
    capacity/api.py::_CLAMP_BLOCKED_KINDS. `unarmed` IS D16's row, cause and all. Two more
    (`nonpositive`, `never_pins`) reach the STATE that row names -- no lift can ever be earned --
    through a cause the ruling does not mention. The last three (`at_ceiling`, `refused_unmasked`,
    `inert`) EARN lifts, so the row's state does not hold there at all and the verdict rests on this
    gate's own subject instead: a clamp needs an applied lift that overshoots, and on those grounds
    none can exist. The argument above is why
    that is probably right. It is NOT a ruling, and the paragraph that makes it must not be read as
    one: docs/04_CONTRACT.md carries it to the owner as Q-CAP-1, with the population, and until that
    is answered the five extra grounds are this implementation's inference from D16 and D15.

    IT IS BUILT TWICE FROM ONE FUNCTION. capacity/api.py::new_valve calls it at startup, where
    `lifts` and `clamped` are 0 by construction -- the gate is built before the first flush -- so
    the startup line is the second state with the clamp arithmetic for the FIRST earned lift in its
    reason. CAP.counters rebuilds it at the end of the run from the live ledger, which is where the
    last two states become readable. Two builders and one function, for the reason new_valve's
    `_lift_moves` gives about the arithmetic: a second construction of these states somewhere else
    would be a second opinion about what the valve did.

    THE PER-ARM TRUTH IS THE TWO COUNTERS AND NOT THIS LINE. `lifts` and `clamped` are totals over
    both arms, exactly as Decision carries ONE block_reason while at_hard_ceiling and
    dead_rows_unmasked are per-arm; counters["cap.lifts_clamped_experts"] and
    counters["cap.lifts_clamped_vocab"] are where an arm-level count belongs.
    """
    if clamped > lifts:
        raise ValueError(
            f"cap.clamp: {clamped} clamped of {lifts} lift(s) taken is not a ledger this gate can "
            f"read. A CLAMPED LIFT IS A LIFT TAKEN -- the cap did move, which is why this file "
            f"counts it in lifts_experts / lifts_vocab as well and keeps it out of the "
            f"block-reason histogram -- so clamped > lifts is impossible in a correct ledger and "
            f"printing it renders the false equation \"{clamped} of {lifts} earned lift(s) were "
            f"CLAMPED\". Raised in the same spirit as "
            f"capacity/api.py::_clamp_blocked_clause's unknown-kind refusal: an incoherent input "
            f"to a DID IT FIRE line is a startup failure and not a sentence.")
    value = f"{clamped} clamped of {lifts} lift(s) taken"
    need = "0 clamped -- every earned lift applied in full"
    blocked = "; ".join(_clamp_blocked_clause(*rec) for rec in (dead_facts or ()))
    if dead_facts and not lifts and not clamped:
        return Gate(
            "cap.clamp", False, value, need, reachable=False,
            reason=f"NO LIFT CAN BE HELD AT A HARD CEILING on this configuration, which is the only "
                   f"event this gate counts. A clamp needs three things IN ORDER -- a lift EARNED, "
                   f"that lift APPLIED rather than refused, and its unclamped arithmetic ABOVE the "
                   f"hard ceiling -- and on every arm here one of the three fails first: {blocked}. "
                   f"THE VERDICT ABOVE IS NOT A CLAIM THAT NO LIFT IS EARNED and must not be read "
                   f"as one -- the clauses above say, per arm, which case it is in: an arm's "
                   f"earned lifts can be refused by name, and an applied lift can move nothing, "
                   f"and either of those reaches this verdict with lifts having been earned all "
                   f"along. What became of an EARNED lift is cap.valve's line and the "
                   f"block-reason histogram's number; what became of an APPLIED one that overshot "
                   f"is this line's, and there "
                   f"are none here. Reported unreachable rather than as 0 clamped lifts, which "
                   f"would read as a valve that lifted freely and was never held -- the same "
                   f"confusion between an inert mechanism and an absent one that cap.valve is "
                   f"unreachable here to avoid.")
    # THE TWO REACHABLE ARMS DO NOT FALSIFY THE SAME CLAIM, AND ONE OF THEM FALSIFIES NOTHING.
    # A single `falsified` string keyed on `dead_facts` alone was appended to both returns below
    # until 2026-09-05, so the armed-did-not-fire arm printed "no lift reached the hard ceiling"
    # and "THE STARTUP ANALYSIS SAID NO LIFT COULD BE HELD AT A CEILING HERE AND THE LEDGER
    # DISAGREES" in one sentence -- about the same claim, in opposite directions, with the ledger
    # in fact AGREEING. Each arm now says what its own numbers contradict:
    #   clamped > 0   falsifies THIS GATE'S OWN reading. A lift was held at a ceiling where the
    #                 analysis said none could be, whatever the per-arm ground was.
    #   clamped == 0  leaves this gate's reading standing -- 0 clamped is exactly what the
    #                 analysis predicted -- so what a live `lifts` can contradict is the per-arm
    #                 GROUNDS, and only where every one of them says no lift is ever TAKEN there.
    #                 An `inert` ground says the opposite: lifts are taken and move nothing, so
    #                 lifts > 0 with 0 clamped is what that ground predicts and not a disagreement.
    if clamped and dead_facts:
        falsified = (f" THE STARTUP ANALYSIS SAID NO LIFT COULD BE HELD AT A CEILING HERE AND THE "
                     f"LEDGER DISAGREES, so this line reports the LEDGER and not the analysis: "
                     f"{blocked}. Two report lines disagreeing about what the valve did is the "
                     f"shape this gate exists to refuse, and a run is the authority over a reading "
                     f"taken at startup.")
    elif dead_facts and all(rec[1] in _CLAMP_KINDS_NO_LIFT_TAKEN for rec in dead_facts):
        falsified = (f" THE STARTUP ANALYSIS SAID NO LIFT COULD BE TAKEN ON ANY ARM HERE AND THE "
                     f"LEDGER RECORDS {lifts}, so this line reports the LEDGER and not the "
                     f"analysis: {blocked}. WHAT THE LEDGER CONTRADICTS IS THOSE GROUNDS AND NOT "
                     f"THIS GATE'S OWN READING: 0 clamped is what the analysis predicted, and it "
                     f"is the reason the arms were called dead that the run disproves. Two report "
                     f"lines disagreeing about what the valve did is the shape this gate exists to "
                     f"refuse, and a run is the authority over a reading taken at startup.")
    elif dead_facts:
        falsified = (f" THE STARTUP ANALYSIS AGREES WITH THIS LEDGER and is printed for the "
                     f"grounds and not as a disagreement: it said no lift could be HELD AT A "
                     f"CEILING here, and none was; and at least one arm's ground is a lift that is "
                     f"TAKEN and moves nothing, which PREDICTS the {lifts} taken lift(s) above "
                     f"reaching no ceiling rather than contradicting them: {blocked}.")
    else:
        falsified = ""
    if clamped:
        return Gate(
            "cap.clamp", True, value, need,
            reason=f"{clamped} of {lifts} earned lift(s) were CLAMPED at the hard ceiling: the lift "
                   f"was TAKEN and the result held at the ceiling rather than refused, which is the "
                   f"owner's ruling of 2026-09-04 (\"let's soft clamp if a ceiling is overshot, "
                   f"until it goes down\"). A clamped lift is counted in lifts_experts / "
                   f"lifts_vocab as well, because the cap did move; it is NOT in the block-reason "
                   f"histogram, because nothing was refused. Arithmetic: {arith}.{falsified}")
    if lifts:
        return Gate(
            "cap.clamp", False, value, need,
            reason=f"{lifts} earned lift(s) and every one was applied IN FULL -- no lift reached "
                   f"the hard ceiling, so the clamp was live and never had to hold anything. "
                   f"Arithmetic: {arith}.{falsified}")
    return Gate(
        "cap.clamp", False, value, need,
        reason=f"NO LIFT WAS EARNED, so there was nothing to clamp. An armed arm has room and the "
               f"two conditions were never both met; which one refused is the block-reason "
               f"histogram's answer, not this line's. What the FIRST earned lift will do is fixed "
               f"by the arithmetic already: {arith}.")


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
    # THE STARTUP ANALYSIS THE cap.clamp GATE WAS BUILT ON, KEPT SO CAP.counters BUILDS ITS LINE ON
    # THE SAME FACTS (2026-09-24). None when an arm has room to lift, else the per-arm tuple of
    # (arm, kind, facts) new_valve's branches recorded. CAP.counters used to rebuild the gate with no
    # dead_facts at all, so at the shipped CAP_TARGETS=off the R stage printed "An armed arm has
    # room" beside a startup gate that said UNREACHABLE -- and the startup gate is never rendered.
    # Recomputing the analysis at R was refused: after a lift to the hard ceiling it reads
    # `at_ceiling` and would print "the startup analysis said no lift could be taken" about a run
    # whose startup analysis said the opposite. NOT saved or restored by CAP.state/CAP.restore:
    # new_valve rebuilds it on every build, a resume's included, from that build's own caps.
    clamp_dead_facts: object = None



# ==================================================================================================
# HOISTED OUT OF new_valve ON 2026-09-15, UNCHANGED, SO CAP.counters CAN CALL THE SAME TWO.
# Both were nested functions closing over new_valve's `cap`, which made them unreachable from
# CAP.counters -- and CAP.counters is REQUIRED by its own contract to "recompute `arith` FROM THE
# CURRENT CAPS", because new_valve's `arith` is a statement about the STARTING caps and printing it
# on an end-of-run FIRED line reports a true-at-startup equation as a fact about a run whose cap has
# moved. The alternative to hoisting was restating the arithmetic at the second site, which is the
# two-sources-of-truth shape _lift_moves' own docstring argues against in as many words. `cap` is
# now a parameter instead of a closure; nothing else changed.
# ==================================================================================================


def _lift_moves(cap, c, hard):
    """Does ONE EARNED LIFT actually move this cap? LEVERS READ HERE: lift, lift_min.

    capacity/api.py::_clamped_lift IS THE SHIPPED ARITHMETIC observe applies, named in observe's
    own docstring, and it is derive.lift_to -- `int(cap) + max(int(floor), int(frac * cap))` --
    held at the hard ceiling under the owner's clamp ruling. Calling the same named function is
    the point: a reimplementation of the comparison here could disagree with the lift the valve
    actually takes, and then this gate and the mechanism would be two sources of truth.

    THE CLAMP MOVES NO VERDICT ON THIS LINE, AND THAT IS PROVED RATHER THAN HOPED. Every caller
    below has already established `c < hard`, and there the clamp cannot change the answer:
    lift_to(c) > c implies min(lift_to(c), hard) >= min(c + 1, hard) = c + 1 > c, and
    lift_to(c) == c implies the min is c. So the arms that had room before the ruling have room
    after it, which is the control this repair needed -- the REFUSE reading would have moved 302
    of the 4095 sub-ceiling caps from "has room" to "frozen", and the clamp moves none.
    """
    return _clamped_lift(c, hard, cap.lift, cap.lift_min) > c


def _one_lift(cap, c, hard):
    """What ONE EARNED LIFT does to this cap, in the words the mechanism will act on.

    LEVERS READ HERE: lift, lift_min -- through capacity/api.py::_clamped_lift, the same
    function observe applies, for the reason _lift_moves states below.

    THIS LINE PRINTED A NUMBER THE MECHANISM NEVER TAKES UNTIL THE CLAMP RULING LANDED. At
    CAP_TARGETS=both CAP_FAB_START=4095 CAP_VOCAB_START=4095 LM_MASK_DEAD_ROWS=1 it read
    `experts 4095/ceiling 4096/settles 1844/one lift -> 4422` -- a lift 326 slots above the
    ceiling printed on the same line as the ceiling, on a gate whose sentence is that the arm
    has room to earn. That is the false-equation shape this package has paid for five times.
    Under the ruling the valve takes 4096 and drops the rest, so the printed number is 4096 and
    the 4422 survives as what was ASKED FOR, labelled as such.

    THE THIRD FORM IS THE REFUSAL AND IT IS NOT A CLAMP. From a cap already at or above the
    ceiling observe refuses by name as at_hard_ceiling before any lift is computed, so there is
    no lift to print and saying `one lift -> <ceiling>` there would report a lowering as a lift.
    """
    raw = derive.lift_to(c, cap.lift, cap.lift_min)
    got = _clamped_lift(c, hard, cap.lift, cap.lift_min)
    if c >= hard:
        return f"one lift -> none, at_hard_ceiling refuses {c} >= {hard}"
    if got != raw:
        return f"one lift -> {got}, CLAMPED at the ceiling from {raw}"
    return f"one lift -> {got}"


@dataclasses.dataclass(frozen=True)
class Caps:
    """The two soft caps as one flush reads them, and the SUBTRACTION THAT MAY NOT GO NEGATIVE.

    FROZEN, because a consumer that can write to this can move the valve's cap without earning it,
    and every lift in this package is supposed to be earned.

    `headroom` EXISTS SO THE NEGATIVE FORM CANNOT BE WRITTEN AT A CALL SITE. The old tree wrote
    `_nb = min(_nb, _cap_fab[0] - fab.n())` (:7446), which is negative the moment the population
    exceeds the soft cap -- and a negative clamp freezes growth FOR THE ENTIRE RUN with nothing in
    the log saying so, because the trigger counts still increment and the pin counter reads exactly
    as it would on a population legitimately at its cap (C30). Unreachable on a fresh run only if
    FAB_N0 is at or below the cap, which at the shipped defaults it is NOT (see Q-CAP-2); entirely
    reachable on a resume, where the population comes from the checkpoint -- 523 against a gc arm's
    160 is -363. The max(0, ...) is the repair, and putting it HERE rather than in a rule about call
    sites is the same argument capacity/api.py::_clamped_lift makes for its own guard.
    """
    experts: int
    vocab: int

    def headroom(self, n):
        """How many more EXPERTS may be born before the soft expert cap is reached. NEVER < 0.

        THE EXPERT ARM, AND THE ASYMMETRY IS THE CONTRACT'S RATHER THAN A CHOICE MADE HERE.
        docs/04_CONTRACT.md declares exactly one method -- "`Caps.headroom(n)` exists so the
        negative clamp (C30) cannot be written at a call site" -- and C30 is the FABRIC clamp,
        `min(n_born, cap - fab.n())`. The vocabulary arm has no matching consumer to protect:
        tok/api.py::Vocabulary._cap already takes min(soft, hard) itself and never subtracts, so
        `caps.vocab` is read as a bound rather than differenced. A second method for it would be a
        public entry point the document does not declare, which is what K1 refuses, and a method
        nothing calls, which is what O4 counts.
        """
        return max(0, int(self.experts) - int(n))


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
    the mechanism off (ISSUES P3-C30). One choices-valued lever makes "off" mean one thing at both
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

    `restored` IS KEYED BY THE VALVE'S FIELD NAMES -- restored["cap_experts"] and
    restored["cap_vocab"] carry the caps, because that is what CAP.state writes. THIS PARAGRAPH
    SAID THE OPPOSITE UNTIL 2026-09-24 ("keyed by the start levers' own names ... fab_start /
    vocab_start"), written while CAP.state was a stub, and it predicted the failure exactly: the
    body read restored["fab_start"], CAP.state wrote "cap_experts", so the checkpoint branch below
    never ran on any checkpoint this tree writes and `origin` said "sentinel" or "off" for every
    resume. CAP.restore then wrote the caps back ungated -- onto an OFF valve, and onto a widened
    one at the old ceiling (driven: a clean FAB_SLOTS=1024 resume of a 512-slot parent came back
    with cap_experts 512 against a hard ceiling of 1024, origin "off"). The unwritten key
    convention between a live body and a stub is where M38 came back, as this paragraph said it
    would.
    THE CHECKPOINT'S CAP IS TAKEN ONLY FOR AN ARM THE VALVE GOVERNS NOW AND GOVERNED WHEN IT WAS
    SAVED. CAP.state records each arm's `armed_*` flag and `hard_*` ceiling beside its cap, because
    a cap saved under "off" -- or on an arm `targets` does not name -- is the hard ceiling at that
    time and not an earned number; installing it as a soft cap after a slot widening freezes the
    new capacity behind the old ceiling. A saved cap AT its saved ceiling is the sentinel ("start at
    the hard ceiling"), so it follows the ceiling to the live one. Every cap taken is clamped to the
    live hard ceiling: FAB_SLOTS / LM_VOCAB_SLOTS narrowing is refused by the geometry gate, so the
    clamp only bites a checkpoint written before the provenance keys, which carry no `armed_*` and
    are taken as the pre-2026-09-24 restore took them, and say so in `origin`.

    REFUSES AT STARTUP, BY LEVER NAME, WITH BOTH NUMBERS IN THE MESSAGE. Two values are refused and
    EITHER ONE ALONE is enough: CAP_LIFT < 0, and CAP_LIFT_MIN < 0. EITHER NEGATIVE CAN LOWER A CAP,
    so the `or` in the guard is required rather than belt-and-braces -- and this paragraph said the
    opposite ("only the two TOGETHER lower a cap; each on its own is a second spelling of a legal
    value") until 2026-09-04. This module's founding sentence is that a ceiling may be "raised, by a
    little, never lowered", and derive.lift_to is `int(cap) + max(int(floor), int(frac * cap))`.
    THE SIGN OF THE PROPORTIONAL TERM IS THE SIGN OF frac TIMES THE SIGN OF cap, AND THE CAP CAN BE
    NEGATIVE HERE -- new_valve's own five-ways-an-arm-is-dead comment says so ("CAP_FAB_START=-5
    resolves a soft expert cap of -5"), which is what makes the two-negatives statement a false
    universal rather than a rounding of the truth. Both routes, each with its measurement:
      BOTH NEGATIVE, at a cap above zero, the max is negative and an EARNED lift SHRINKS the cap.
      Reproduced before the refusal existed: CAP_TARGETS=experts CAP_FAB_START=12 CAP_LIFT=-0.5
      CAP_LIFT_MIN=-100 gave derive.lift_to(12, -0.5, -100) = 6, and cap.valve rendered
      "one lift -> 6" beside the words "ONE EARNED LIFT DOES NOT MOVE IT" on one printed line.
      CAP_LIFT_MIN ALONE NEGATIVE, at a cap BELOW zero, is enough on its own: the proportional term
      is negative there for a NON-negative CAP_LIFT, so the floor can be the max and still be below
      zero -- derive.lift_to(-100, 0.5, -1) = -101 against derive.lift_to(-100, 0.5, 0) = -100.
    The body below says why this is a refusal rather than a sentence in a Gate, exactly which
    configurations it removes and which it does not, and why only the NEGATIVE half is refused.

    LEVERS READ: targets, fab_start, vocab_start, lift, lift_min
                 (the last two are read for two things and neither takes a lift: the startup
                 refusal above, and cap.valve's question, answered through the same
                 capacity/api.py::_clamped_lift observe applies -- a lift that returns the cap
                 unchanged is an arm that cannot move, and asking that here costs nothing observe
                 does not already do. observe remains the only caller that lifts.)
    WIRES READ: d_expert_slots, d_vocab_slots, d_mask_dead_rows, d_operating_population
                (the cull's settling point. Read HERE, and not only in startup_refusals,
                because cap.valve cannot say whether the expert arm can pin without it --
                a soft cap above the settling point is a cap the population never reaches.
                It is the same derive.operating_population call FAB's own row makes, and
                the row is already declared, so this costs no coupling)
    DID IT FIRE: THREE SURFACES, and this line used to name one of them with the wrong shape and a
                 source set the body never produced -- it said "for each target, (start, source)"
                 for a field that carries the two SOURCES alone, and named a closed set of three
                 ("lever", "hard ceiling (sentinel 0)", "checkpoint") of which the body spells none
                 and to which "off" is a fourth. What is actually produced:
                 (1) Valve.origin -- (experts_source, vocab_source); the two STARTS are the Valve's
                     own cap_experts / cap_vocab, and the counters below pair them. The sources are
                     a closed set of four: "off (valve disabled; ...)" when targets is off,
                     "operator (<lever>=<n>)" and its sentinel form "operator (<lever>=0, the
                     sentinel) -> hard ceiling <n>", "checkpoint (lifted to <n>...)" and its
                     at-ceiling form "checkpoint (at its hard ceiling <m>) -> hard ceiling <n>",
                     and "sentinel 0 -> hard ceiling <n>" (with a parenthesis when a checkpoint's
                     cap was on offer and was saved on an unarmed arm). A cap that came from the
                     wrong place is visible because the four are spelled differently -- which is
                     how the checkpoint source was found never to appear (Q-CAP-3).
                 (2) Valve.counters -- cap.targets, the two caps, the two hard ceilings, the two
                     origins (which is the pairing (1) leaves to the reader), cap.mask_dead_rows,
                     the honesty precondition, added 2026-09-04 because observe's new
                     `dead_rows_unmasked` block reason must read it per flush and observe reads no
                     wires of its own, and the two CLAMP COUNTERS cap.lifts_clamped_experts and
                     cap.lifts_clamped_vocab, seeded at 0 here for the same reason and incremented
                     by observe when the owner's clamp ruling holds a lift at the hard ceiling.
                     SEEDED AT ZERO IS NOT THE SAME AS ABSENT: a counter that only appears once it
                     is non-zero cannot be read as "armed and it did not happen", which is the
                     collapse this package's whole DID IT FIRE surface exists to refuse.
                 (3) Valve.gates -- cap.valve, cap.vocab_arm_honest and cap.clamp. They are the
                     reason this entry point builds Gates at all, and leaving them out of this line
                     made the one that was WRONG invisible to every reader of the contract.
                     cap.clamp IS THE CLAMP'S READING and it carries FOUR distinguishable states,
                     which is one more than spine/gate.py::Gate has verdicts -- so the fourth is
                     carried where Gate.line already prints numbers, in `value`, and not by
                     collapsing two of the three into one word:
                       UNREACHABLE                     no lift can be HELD AT A HARD CEILING on
                                                       this configuration (the same analysis
                                                       cap.valve does, and NOT the same sentences:
                                                       the `dead` prose spliced in here until
                                                       2026-09-05 opened "no lift can be earned at
                                                       all" and then carried cap.valve's own
                                                       clauses saying which lifts ARE earned and
                                                       then refused. The two gates now share the
                                                       FACTS -- `dead_facts`, per arm -- and each
                                                       writes its own sentence; a clamp is a
                                                       property of an APPLIED lift that overshoots,
                                                       so where that cannot happen the question is
                                                       INAPPLICABLE, not unmet)
                       armed, 0 clamped of 0 lifts     no lift was earned yet -- and this is the
                                                       only reachable reading a gate BUILT AT
                                                       STARTUP can have, for the same reason
                                                       cap.valve's FIRED is an arming answer
                       armed, 0 clamped of N lifts     every earned lift was applied IN FULL
                       FIRED, M clamped of N lifts     M earned lifts were CLAMPED at the ceiling
                     CAP.counters REBUILDS IT from the live ledger at the end of the run, through
                     the same capacity/api.py::_clamp_gate this entry point calls, so the last two
                     readings are reachable in a report and not only in principle. Two gates
                     resting on the same reachability fact and saying different things about it is
                     this file's existing shape, not a new one: cap.valve answers "can a lift
                     happen at all" and cap.clamp answers "what happened to the lifts that did".
                     cap.vocab_arm_honest carries all THREE of spine/gate.py's states: UNREACHABLE
                     when the vocabulary arm is not armed, the MIDDLE state when the arm is armed
                     and LM_MASK_DEAD_ROWS is off (the precondition was tested and not met), and
                     FIRED when the arm is armed and the mask is on.
                     cap.valve carries TWO, and this line claimed THREE of it until 2026-09-04.
                     Built at startup it can only answer "can a lift happen at all", so it prints
                     UNREACHABLE or FIRED and never the middle state; FIRED on it is the ARMING
                     answer and not a lift, because the lifts are CAP.counters' lifts_experts and
                     lifts_vocab and a second count here would be a second source of truth for them.
                     THAT PREDICATE IS WHY IT READS THE MASK. "Can a lift happen at all" is
                     answered NO for the vocabulary arm whenever observe would refuse every lift
                     that arm earns, and since 2026-09-04 `dead_rows_unmasked` does exactly that,
                     so the two gates rest on the same fact and say DIFFERENT things about it:
                     cap.vocab_arm_honest reports the PRECONDITION (armed, tested, not met), and
                     cap.valve reports the CONSEQUENCE for reachability. Neither is a copy of the
                     other, and dropping the mask from cap.valve is what made it print FIRED for a
                     valve that could not lift.
    """
    cap = cap.owned_by("CAP")
    hard_experts = int(cap.d_expert_slots)      # WIRES READ HERE -- the two hard ceilings
    hard_vocab = int(cap.d_vocab_slots)
    mask_dead = bool(cap.d_mask_dead_rows)
    targets = str(cap.targets)

    # A LIFT THAT LOWERS THE CAP IS REFUSED HERE, BEFORE ANY CAP IS RESOLVED AND BEFORE EITHER GATE
    # IS BUILT. That is the property this argument needs, and it is what this line now claims: it
    # said "BEFORE ANY OTHER NUMBER IS DERIVED" until 2026-09-04 and four values are derived above
    # it -- hard_experts, hard_vocab, mask_dead and targets, three of them off wires -- which is the
    # kind of absolute a later reader relies on when deciding where a second refusal may go.
    # The valve's founding sentence is a ceiling "raised, by a little, never lowered", and
    # spine/derive.py::lift_to is `int(cap) + max(int(floor), int(frac * cap))`. AT A CAP ABOVE
    # ZERO, with CAP_LIFT < 0 AND CAP_LIFT_MIN < 0, both terms are negative, the max is negative,
    # and an EARNED lift SHRINKS the cap. Measured before this refusal existed, at
    # CAP_TARGETS=experts CAP_FAB_START=12 CAP_LIFT=-0.5 CAP_LIFT_MIN=-100:
    # derive.lift_to(12, -0.5, -100) = 6, and cap.valve printed "one lift -> 6" in its arithmetic
    # beside "ONE EARNED LIFT DOES NOT MOVE IT" in its reason, on one line, for a lift that halved
    # the cap. THE "BOTH" IS THE SUFFICIENT CASE AT A POSITIVE CAP AND NOT THE ONLY ONE ANYWHERE:
    # the proportional term takes the sign of frac TIMES the sign of cap, so at a cap below zero --
    # which CAP_FAB_START=-5 reaches -- a negative CAP_LIFT_MIN ALONE lowers it,
    # derive.lift_to(-100, 0.5, -1) = -101. Both routes are why the guard is an `or`.
    #
    # WHY REFUSED RATHER THAN DESCRIBED, which is the question the Gate below cannot answer. A Gate
    # reason is a REPORT and the mechanism still runs: describing it buys the operator a sentence
    # while every earned lift spends the run's evidence shrinking the thing the evidence says to
    # grow. That is the C30 inversion -- a clamp that goes the wrong way with nothing in the log --
    # arriving through a lever VALUE instead of through a guard, and this package's own
    # startup_refusals clause (1) already refuses the other spelling of it (a soft cap at or below
    # zero). A valve that lowers on evidence it should raise is not a configuration of this
    # mechanism; it is a different mechanism wearing its name.
    #
    # WHAT IT REMOVES, STATED WITH ITS BOUND RATHER THAN AS A UNIVERSAL (corrected 2026-09-04; the
    # sentence here read "IT REMOVES NO CONFIGURATION" and justified it with two claims that are
    # false below zero). AT A CAP AT OR ABOVE ZERO both halves really are second spellings: with
    # CAP_LIFT_MIN >= 0 a negative CAP_LIFT is arithmetically IDENTICAL to CAP_LIFT=0, because
    # int(frac x cap) <= 0 there and max(floor, negative) is the floor, and CAP_LIFT=0 is in range,
    # legal, and spells a flat +CAP_LIFT_MIN lift; with CAP_LIFT >= 0 a negative CAP_LIFT_MIN is
    # likewise identical to CAP_LIFT_MIN=0, because int(frac x cap) >= 0 there and is the max
    # either way. So on every cap this valve is supposed to have, nothing an operator can ask for
    # is lost, and both legal spellings are named in the message.
    # BELOW ZERO NEITHER IDENTITY HOLDS, AND THAT IS THE SECOND REASON TO REFUSE RATHER THAN AN
    # EXCEPTION TO THE FIRST. The proportional term flips sign with the cap, so at cap=-100:
    # derive.lift_to(-100, -0.5, 8) = -50 while derive.lift_to(-100, 0, 8) = -92 (a negative
    # CAP_LIFT is NOT CAP_LIFT=0 there), and derive.lift_to(-100, 0.5, -1) = -101 while
    # derive.lift_to(-100, 0.5, 0) = -100 (a negative CAP_LIFT_MIN is NOT CAP_LIFT_MIN=0 there,
    # and it LOWERS the cap on its own). What is removed at a negative cap is therefore a real
    # behaviour and not a duplicate -- and it is the behaviour this guard exists to refuse, since
    # a cap below zero is already a dead arm (the growth clamp goes negative on the first flush,
    # C30) and the only thing a negative lever adds there is a second way to move it wrongly.
    #
    # ONLY THE NEGATIVE HALF IS REFUSED, AND CAP_LIFT > 1 IS DELIBERATELY LEFT LEGAL. U.FRACTION's
    # unit string is a LABEL the census renders, not a bound -- src/sig/levers.py::SIGLevers says
    # exactly that of its own share ("spine/lever.py::Lever carries choices and no numeric range, so
    # units.FRACTION here is a label"), and src/tok/levers.py::TOKLevers keeps a U.FRACTION lever
    # where "a reader who takes 'fraction 0..1' as a bound on legal values will be surprised by 2.0,
    # which is legal". A lift of 2.0 is a large lift and NEVER a lowering one, which is the property
    # the invariant needs: above zero it raises the cap, and below zero int(2.0 x cap) is more
    # negative than any floor at or above 0, so the max IS the floor and the cap raises or stands
    # still -- derive.lift_to(-100, 2.0, 8) = -92, derive.lift_to(-100, 2.0, 0) = -100. So it does
    # not touch the invariant this refusal holds. Refusing it would be this file deciding a range question the
    # tree has twice decided the other way.
    #
    # WHY HERE AND NOT IN startup_refusals. That entry point is declared for refusals that need TWO
    # packages' numbers -- it takes live_experts and reads d_operating_population -- and it is a
    # stub, so a clause added there would refuse nothing today; it also runs AFTER this row in
    # spine/compose.py::ASSEMBLY_ORDER, so the Gate would render its reason first. This is a range
    # check over CAP's own two levers, at the first place either is read. src/lm/api.py::resolve is
    # the precedent and states the general ground in its own words: the refusals are in a body
    # because "a Lever has no range facility and `choices=` enumerates rather than bounds, so these
    # cannot be declarations" (the word "because" was INSIDE the quotation marks until 2026-09-04
    # and appears nowhere in src/lm/api.py::resolve; the citation was sound and the quotation of it
    # was not, which is a claim about wording and so is worth the same care as a claim about a
    # number).
    if float(cap.lift) < 0 or int(cap.lift_min) < 0:
        # THE LAST CLAUSE IS ABOUT THE VALUES THE OPERATOR ACTUALLY SET, and it exists because the
        # two worked equations below are NOT: they are the two regimes, labelled as such, and at
        # CAP_LIFT=-0.5 with the shipped CAP_LIFT_MIN=8 neither of them is an equation about either
        # of the operator's numbers. A refusal that prints only somebody else's arithmetic is the
        # same defect as a Gate that does, one register down. Each branch is the identity proved in
        # the "WHAT IT REMOVES" comment above and holds only at a cap at or above zero, which is
        # why every branch says so.
        if float(cap.lift) < 0 and int(cap.lift_min) < 0:
            yours = ("BOTH of your values are negative, so no legal pair reproduces this "
                    "configuration: what it does -- lower the cap on earned evidence -- is the one "
                    "thing this valve may never do, at any cap.")
        elif float(cap.lift) < 0:
            yours = (f"FOR THE VALUES YOU SET: CAP_LIFT_MIN={cap.lift_min} is at or above 0, so at "
                    f"any cap at or above zero CAP_LIFT={cap.lift} is arithmetically CAP_LIFT=0 -- "
                    f"set that, and the lift stays the flat +{int(cap.lift_min)} the floor spells.")
        else:
            yours = (f"FOR THE VALUES YOU SET: CAP_LIFT={cap.lift} is at or above 0, so at any cap "
                    f"at or above zero CAP_LIFT_MIN={cap.lift_min} is arithmetically "
                    f"CAP_LIFT_MIN=0 -- set that.")
        raise LeverError(
            f"CAP_LIFT={cap.lift} / CAP_LIFT_MIN={cap.lift_min}: a lift may raise this ceiling and "
            f"may leave it where it is, and may never lower it. derive.lift_to(cap, frac, floor) is "
            f"cap + max(int(floor), int(frac x cap)), so a negative value of EITHER lever can "
            f"return LESS than the cap it was handed and the valve would spend earned evidence "
            f"shrinking the capacity that evidence says to grow: derive.lift_to(12, -0.5, -100) = "
            f"6 with both negative at a cap above zero, and derive.lift_to(-100, 0.5, -1) = -101 "
            f"with the floor alone negative at a cap below zero, which CAP_FAB_START=-5 reaches. "
            f"AT A CAP AT OR ABOVE ZERO neither negative buys anything a legal value does not: "
            f"with a floor at or above 0 a negative CAP_LIFT is exactly CAP_LIFT=0 (a flat "
            f"+CAP_LIFT_MIN lift), and with a fraction at or above 0 a negative CAP_LIFT_MIN is "
            f"exactly CAP_LIFT_MIN=0; BELOW zero neither identity holds, which is the second "
            f"reason both are refused rather than the exception to the first. CAP_LIFT above 1 is "
            f"NOT refused: it is a large lift, not a lowering one. {yours}")

    def _resolve(given, asked, hard, what, arm):
        """Where a starting cap comes from, in the order the four branches below decide it.

        `targets == "off"` FIRST -- the valve disabled means the starting caps are not applied
        either -- then the OPERATOR's explicit value, with an explicit 0 read as the documented
        sentinel because the sentinel is a property of the VALUE and not of where it arrived
        from; then the CHECKPOINT's lifted cap; then the declared default sentinel LAST -- whose
        origin string reads "off for this arm" instead when `targets` does not name the arm, since
        the sentinel's "no room to earn" describes an arm the valve governs (2026-09-24).

        This line read "The sentinel, the operator, and the checkpoint, in that order of
        precedence" until 2026-09-04. It named the sentinel first though it resolves last, and
        did not name `off` at all though `off` dominates every other branch. Every other
        statement of the precedence in this file -- new_valve's own docstring, the two comments
        below, and the four origin strings -- was already right, which is what made the one-line
        summary a reader skims the only thing here that was not.
        """
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
        field = "cap_" + arm
        if (restored is not None and restored.get(field) is not None
                and targets in (arm, "both")):
            # THE LIFTED CAP IS EARNED STATE, NOT A KNOB. Rebuilding it from the environment on
            # every resume handed a run that had spent hours lifting its starting cap back.
            # READ UNDER THE KEY CAP.state WRITES -- `restored[what]` (the lever's name) matched
            # nothing any checkpoint carries, so this branch was unreachable until 2026-09-24.
            # AND ONLY ON AN ARM `targets` ARMS: `off` is handled above, and an arm `targets` does
            # not name is not governed by the valve either, so a saved number is not applied to it.
            saved_cap = int(restored[field])
            was_armed = restored.get("armed_" + arm)
            saved_hard = restored.get("hard_" + arm)
            if was_armed is False:
                # SAVED UNDER A VALVE THAT DID NOT GOVERN THIS ARM: the number is the ceiling at
                # save time, not an earned cap, so the sentinel resolves instead -- and says why.
                return hard, (f"sentinel 0 -> hard ceiling {hard} (the checkpoint's {field}="
                              f"{saved_cap} was saved on an UNARMED arm and is not earned state)")
            if saved_hard is not None and saved_cap >= int(saved_hard):
                # AT ITS SAVED CEILING IS THE SENTINEL'S STATE, so it follows the ceiling: a slot
                # widening on resume must not come back capped at the old hard ceiling.
                return hard, (f"checkpoint (at its hard ceiling {int(saved_hard)}) -> hard "
                              f"ceiling {hard}")
            taken = min(saved_cap, hard)
            tail = "" if was_armed is not None else "; checkpoint carries no arm provenance"
            clamp = "" if taken == saved_cap else f", clamped from {saved_cap}"
            return taken, f"checkpoint (lifted to {taken}{clamp}{tail})"
        # AN ARM `targets` DOES NOT NAME IS OFF FOR THE VALVE, AND ITS ORIGIN SAYS SO (2026-09-24).
        # The number is the hard ceiling exactly as the sentinel's is, but the sentinel's sentence
        # -- "start at the hard ceiling, no room to earn" -- describes an arm the valve governs, and
        # CAP_TARGETS=vocab printed cap.origin_experts "sentinel 0 -> hard ceiling 4096" for an arm
        # no lift can ever reach. Only the reachable-by-the-default branch is re-worded: an
        # operator's explicit CAP_FAB_START on an untargeted arm is still applied as asked above
        # (it is also the fabric growth clamp's operating ceiling, per the lever's own help).
        if targets not in (arm, "both"):
            return hard, (f"off for this arm (CAP_TARGETS={targets} does not name it; the cap is "
                          f"the hard ceiling {hard})")
        # THE SENTINEL. 0 means START AT THE HARD CEILING -- no room to earn -- and it must be a
        # sentinel rather than a literal because lever.py refuses a default computed from another
        # lever, so the number it stands for can only arrive as the wire.
        return hard, f"sentinel 0 -> hard ceiling {hard}"

    # Config.given() returns the WHOLE map of what the environment actually supplied; membership in
    # it is the answer to "did the operator ask", and it is the only correct source -- reading
    # os.environ here would be the L2 violation the whole spine removes.
    asked = cap.given()
    ce, oe = _resolve("fab_start" in asked, cap.fab_start, hard_experts, "fab_start", "experts")
    cv, ov = _resolve("vocab_start" in asked, cap.vocab_start, hard_vocab, "vocab_start", "vocab")

    valve = Valve(cap_experts=ce, cap_vocab=cv, origin=(oe, ov))
    valve.counters = {
        "cap.targets": targets,
        "cap.cap_experts": ce, "cap.cap_vocab": cv,
        "cap.hard_experts": hard_experts, "cap.hard_vocab": hard_vocab,
        "cap.origin_experts": oe, "cap.origin_vocab": ov,
        # FROZEN ONTO THE VALVE HERE, THE WAY THE TWO HARD CEILINGS ARE, AND FOR THE SAME REASON.
        # CAP.observe declares "WIRES READ: none" and means it: everything the per-flush decision
        # needs off another package is read ONCE, at build, and carried on the record. The honesty
        # precondition became a per-flush input on 2026-09-04 when observe's closed set gained
        # `dead_rows_unmasked`, so the flag has to travel the same way -- and it lands in the
        # declared ledger rather than as a new Valve field, because counters is where new_valve
        # already parks what observe must read back and CAP.counters already reports it.
        "cap.mask_dead_rows": mask_dead,
        # THE CLAMP COUNTERS, SEEDED AT ZERO HERE AND INCREMENTED BY observe. The owner ruled on
        # 2026-09-04 that a lift which overshoots the hard ceiling is CLAMPED rather than refused,
        # and a clamped lift is neither a clean fire nor a refusal: it is absent from the
        # block-reason histogram (nothing was refused) and indistinguishable inside lifts_experts /
        # lifts_vocab (the cap did move). Without a number of its own the one thing an operator
        # cannot learn from the report is how much of the earned lift the ceiling took -- which is
        # this package's founding failure, one mechanism further in. They are seeded rather than
        # created on first use for the reason cap.mask_dead_rows is frozen on here: observe reads no
        # wires of its own, and a counter that appears only once it is non-zero cannot be read as
        # "armed and it did not happen".
        "cap.lifts_clamped_experts": 0,
        "cap.lifts_clamped_vocab": 0,
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
        # THE MIDDLE STATE, AND IT READ UNREACHABLE UNTIL 2026-09-04. Two things make UNREACHABLE
        # wrong on this branch, and the FIRST is the criterion the branch above writes down.
        # (a) That branch reports the unarmed arm unreachable because sending an operator to set
        #     LM_MASK_DEAD_ROWS=1 there "would change nothing observable". HERE IT CHANGES THE ONE
        #     THING THIS GATE IS ABOUT -- setting it is the whole repair -- so by this file's own
        #     test the condition is UNMET, not INAPPLICABLE. spine/gate.py::Gate.line prints the
        #     reason on every arm on purpose, so nothing is lost by saying so on the middle one.
        # (b) THE MECHANISM STILL RUNS, AND SINCE 2026-09-04 IT IS ALSO REFUSED BY NAME. Printing
        #     UNREACHABLE put the vocabulary arm among the mechanisms that were INERT this run
        #     while the arm was live, which is the reading spine/gate.py exists to refuse, arriving
        #     from the opposite direction to the one D15 fixed. This comment read "observe's block
        #     reasons are a CLOSED set ... with no entry for unmasked dead rows, and neither
        #     startup_refusals clause covers it either. So nothing in this tree refuses the
        #     dishonest lift: the run makes it." The first half is now false and the correction is
        #     the point: capacity/api.py::observe's closed set gained `dead_rows_unmasked`,
        #     evaluated LAST so the arm still records whether it ever pinned and stalled. THE STATE
        #     OF THIS GATE DOES NOT CHANGE FOR THAT. It is still the middle one -- armed, tested,
        #     not met -- because the arm IS armed and the precondition IS the thing that failed;
        #     what changed is the consequence, and the consequence belongs in the histogram rather
        #     than on this line, or the two become copies of each other.
        vocab_arm = Gate(
            "cap.vocab_arm_honest", False, mask_dead, True,
            reason="LM_MASK_DEAD_ROWS=0: the vocabulary arm IS armed, so this precondition was "
                   "TESTED AND NOT MET -- every row a lift reserves would sit unmasked in the "
                   "softmax denominator, and what the run measures is the reservation and not the "
                   "valve. An UNMET CONDITION and not an unreachable one: setting "
                   "LM_MASK_DEAD_ROWS=1 on this configuration changes the thing this gate is "
                   "about, so an operator sent to set it is sent somewhere useful. THE LIFT IS "
                   "REFUSED, NOT MERELY REPORTED: observe's block-reason set carries "
                   "`dead_rows_unmasked`, evaluated after every other condition, so an earned "
                   "vocabulary lift on an unmasked output layer is declined and counted in "
                   "CAP.counters' block-reason histogram rather than taken. This line says the "
                   "precondition was not met; that histogram says how many lifts it cost. Neither "
                   "is a copy of the other.")
    # WHERE A LIFT CAN ACTUALLY GO, ARM BY ARM. This gate read `Gate("cap.valve", targets != "off",
    # targets, "off")` until 2026-09-04, so its `fired` value and its reachability were the SAME
    # predicate and the only thing it could say on the six armed corners was FIRED -- meaning "the
    # switch is on", printed beside mechanisms that could not move. FIVE WAYS AN ARMED ARM IS DEAD
    # ON ARRIVAL, all six of which printed FIRED:
    #   cap <= 0        the growth clamp `min(n_born, cap - fab.n())` is negative on the FIRST
    #                   flush, so growth is frozen for the whole run with nothing in the log (C30).
    #                   Reachable today: CAP_FAB_START=-5 resolves a soft expert cap of -5, and the
    #                   declared catcher -- startup_refusals clause (1), "a soft cap below the
    #                   population" -- HAS A BODY and runs at compose, so the run DOES say so. This
    #                   line read "is a stub, so no other line in the run says so" until
    #                   2026-09-22, which was a claim about coverage that had stopped being true.
    #   cap >= ceiling  NO ROOM TO EARN: the cap is ALREADY at or above the hard ceiling, which is
    #                   the condition observe refuses by name as at_hard_ceiling. This clause said
    #                   until 2026-09-04 that "derive.lift_to ... from a cap at or above the hard
    #                   ceiling lands above it", which is false at a small ceiling: at FAB_SLOTS=10
    #                   with CAP_LIFT_MIN=0, derive.lift_to(10, 0.08, 0) = 10 + max(0, int(0.8)) =
    #                   10, which lands ON the ceiling and not above it. The ground is the CAP, not
    #                   the lift: from a cap at or above the ceiling one earned lift either lands
    #                   above it or does not move it at all, and neither is room to earn.
    #                   THIS IS THE SHIPPED DEFAULT: both starts are the sentinel,
    #                   the sentinel resolves to the hard ceiling, and the lever's own help text
    #                   spells out what that means -- "0 means start at the hard ceiling, i.e. no
    #                   room to earn". Turning CAP_TARGETS on is NOT enough to arm anything.
    #   cap > settling  (experts only) the cull settles the population at d_operating_population =
    #                   FAB_PRESSURE x FAB_SLOTS = 1844 at the shipped config, so a soft cap above
    #                   it is a cap the population never reaches: it never pins, the pin clock never
    #                   accumulates, and the valve is dead while every report line says it is armed.
    #                   That sentence is this package's OWN, in startup_refusals below and in the
    #                   CAP.d_operating_population row of spine/assemble.py::COUPLINGS. The wire is
    #                   already declared and already delivered onto this Config, so reading it here
    #                   costs no coupling -- the WIRE_BUDGET is not the obstacle it looks like.
    #
    #   lift == cap     (both arms) THE LIFT ITSELF IS ARITHMETICALLY INERT. observe's lift is
    #                   derive.lift_to(cap, cap.lift, cap.lift_min) = cap + max(floor, int(frac x
    #                   cap)), and when BOTH terms round to zero it returns the cap UNCHANGED, so
    #                   the valve can earn a lift on every flush forever and nothing moves. Not
    #                   hypothetical and not a knob nobody sets: capacity/levers.py::CAPLevers is
    #                   where the case is written down -- "at cap 12, int(0.08 x 12) = int(0.96) =
    #                   0, so without the floor `lift_to` returns 12 and the cap can never move
    #                   again, on any evidence, forever". CAP_LIFT_MIN=0 with CAP_FAB_START=12 is
    #                   exactly that configuration, and it printed FIRED. IT IS THREE ENVIRONMENT
    #                   SETTINGS AWAY AND IT IS NOT WHERE THE DEFAULTS SIT -- CAP_TARGETS=experts, a
    #                   small CAP_FAB_START (or a small FAB_SLOTS), and CAP_LIFT_MIN=0. THE SMALL
    #                   CAP IS SUFFICIENT, NOT NECESSARY, and the gate's own sentence said "a small
    #                   cap" as though it were necessary until 2026-09-04: the clause is reached
    #                   whenever int(CAP_LIFT x cap) is 0, and at the legal CAP_LIFT=0 that is EVERY
    #                   cap -- rendered at CAP_FAB_START=1000, where the old parenthetical printed
    #                   "a small cap" beside a printed cap of 1000. THE THREE-SETTINGS SENTENCE is
    #                   the honest form of a claim this file and levers.py both made as "reachable
    #                   in the run this rebuild launches with" until 2026-09-04. This one is CAP's
    #                   OWN arithmetic on CAP's OWN two levers -- no wire, no other package --
    #                   which is what makes its absence the plainest of the five.
    #   mask off        (vocabulary only) THE HONESTY PRECONDITION, and it is the one this gate was
    #                   still getting wrong on 2026-09-04 after the sibling gate was repaired under
    #                   D15. When the vocabulary arm is armed and counters["cap.mask_dead_rows"] is
    #                   False, observe's closed set refuses EVERY vocabulary lift by name as
    #                   `dead_rows_unmasked`, unconditionally, on every flush -- so a vocabulary
    #                   lift cannot happen, and this gate's own predicate is "can a lift happen at
    #                   all". LM_MASK_DEAD_ROWS defaults to False, so this is the SHIPPED-DEFAULT
    #                   half of the vocabulary arm rather than a corner.
    #
    # WHY THIS ARRIVED ONE CONDITION LATE, RECORDED BECAUSE THE CONTROL IS THE LESSON. D15 ruled
    # that a Gate's reachability is keyed on the ARM IT REPORTS, and cap.vocab_arm_honest above was
    # repaired under it; the control offered for "cap.valve is undisturbed" was CAP_TARGETS x
    # LM_MASK_DEAD_ROWS over all eight corners, on which cap.valve was byte-identical. It was
    # byte-identical because on ALL EIGHT of those corners cap.valve is UNREACHABLE by construction
    # -- both starts are the sentinel, the sentinel resolves to the hard ceiling, and `no room to
    # earn` fires first -- so the control could not have detected any interaction whatever. A
    # control run entirely inside the arm that is switched off measures nothing, and that is a
    # property of the control, not of the change. The corner that shows it needs a soft cap with
    # HEADROOM: CAP_TARGETS=vocab CAP_VOCAB_START=1000 LM_MASK_DEAD_ROWS=0 printed
    # `Gate cap.valve: FIRED ... an armed arm has room to earn` on a configuration where the only
    # armed arm is refused every flush by name. Reproduced, both here and at CAP_TARGETS=both with
    # the expert arm at its hard ceiling, where NO lift can happen on either arm and the gate still
    # said one could.
    #
    # THE VOCABULARY ARM GETS NO SETTLING-POINT TEST, DELIBERATELY. The settling point is the
    # FABRIC's cull, and no wire delivers an equivalent for the minted vocabulary; inventing one
    # here would be a number this package cannot support. Its tests are the ones that hold for any
    # cap plus the mask, and the omission is stated rather than left to be inferred from the code.
    #
    # THIS DOES NOT REPLACE startup_refusals AND DOES NOT DUPLICATE IT. That entry point REFUSES,
    # reading the LIVE population, and it is where a run dies. This is the DID IT FIRE line, read
    # at startup off the configuration alone. They share the wire on purpose: a disagreement
    # between them would mean the report and the refusal disagree about whether the valve is alive.
    operating = int(cap.d_operating_population)   # WIRE READ HERE -- the cull's settling point
    expert_armed = targets in ("experts", "both")
    vocab_armed = targets in ("vocab", "both")


    expert_room = (expert_armed and 0 < ce < hard_experts and ce <= operating
                   and _lift_moves(cap, ce, hard_experts))
    vocab_room = (vocab_armed and mask_dead and 0 < cv < hard_vocab
                  and _lift_moves(cap, cv, hard_vocab))


    arith = []
    if expert_armed:
        arith.append(f"experts {ce}/ceiling {hard_experts}/settles {operating}"
                     f"/{_one_lift(cap, ce, hard_experts)}")
    if vocab_armed:
        arith.append(f"vocab {cv}/ceiling {hard_vocab}"
                     f"/{_one_lift(cap, cv, hard_vocab)}"
                     f"/mask_dead_rows {mask_dead}")
    arith = ", ".join(arith) or targets
    need = ("a soft cap in 1..ceiling-1 that the population can reach, a lift that moves it, and "
            "-- on the vocabulary arm -- an output layer whose dead rows are masked")

    dead = []
    # THE SECOND LIST IS THE CLAMP'S, AND IT IS A COMPUTED VALUE RATHER THAN A SENTENCE. cap.clamp
    # needs the SAME analysis of why an arm is dead and a DIFFERENT sentence about it -- it reports
    # what became of the lifts that were applied, not whether one can be earned -- so it gets the
    # facts and writes its own words in capacity/api.py::_clamp_blocked_clause. Splicing `dead` into
    # it is what printed "no lift can be earned at all on this configuration" beside "so observe
    # refuses every lift it earns" on 3,464 of 25,344 swept cells. Two gates may share a fact; they
    # may not share a sentence, because the sentence is the part that is about the event.
    # THE UNARMED ARMS ARE IN THIS LIST AND NOT IN `dead`, which is the one structural difference:
    # cap.valve's prose speaks only of arms CAP_TARGETS armed, but an unarmed arm is a perfectly
    # good reason no lift of its can ever be clamped, and leaving it out would let the clamp gate
    # go unreachable with nothing said about half the valve.
    dead_facts = []
    if not expert_armed:
        dead_facts.append(("expert", "unarmed", {"targets": targets}))
    if expert_armed and not expert_room:
        if ce <= 0:
            dead_facts.append(("expert", "nonpositive",
                               {"cap": ce, "lever": "CAP_FAB_START", "given": cap.fab_start,
                                "origin": oe}))
            dead.append(f"the expert arm's soft cap is {ce} (CAP_FAB_START={cap.fab_start}, {oe}), "
                        f"and a cap at or below zero makes the growth clamp negative on the first "
                        f"flush, freezing fabric growth for the whole run (C30)")
        elif ce >= hard_experts:
            dead_facts.append(("expert", "at_ceiling", {"cap": ce, "hard": hard_experts}))
            dead.append(f"the expert arm's soft cap is {ce} against a hard ceiling of "
                        f"{hard_experts} (CAP_FAB_START={cap.fab_start}, {oe}), so there is no "
                        f"room to earn: the cap is ALREADY at or above the ceiling, which observe "
                        f"refuses by name as at_hard_ceiling BEFORE any lift is computed, and the "
                        f"owner's clamp does not reach this arm -- a clamp holds a lift AT the "
                        f"ceiling, which RAISES a cap only from below it, and from {ce} it would "
                        f"be a lowering, which this valve may never do. The unclamped arithmetic "
                        f"derive.lift_to({ce}, CAP_LIFT={cap.lift}, CAP_LIFT_MIN={cap.lift_min}) = "
                        f"{derive.lift_to(ce, cap.lift, cap.lift_min)} is not below the ceiling "
                        f"either, and is never applied here")
        elif ce > operating:
            dead_facts.append(("expert", "never_pins", {"cap": ce, "operating": operating}))
            dead.append(f"the expert arm's soft cap is {ce} against a cull settling point of "
                        f"{operating} (CAP_FAB_START={cap.fab_start}, {oe}; "
                        f"d_operating_population = FAB_PRESSURE x FAB_SLOTS), so the population "
                        f"never reaches it, never pins, and the pin clock never accumulates")
        else:
            dead_facts.append(("expert", "inert", {"cap": ce, "hard": hard_experts,
                                                   "lift": cap.lift, "lift_min": cap.lift_min}))
            dead.append(f"the expert arm's soft cap is {ce} and ONE EARNED LIFT DOES NOT MOVE IT: "
                        f"derive.lift_to({ce}, CAP_LIFT={cap.lift}, CAP_LIFT_MIN={cap.lift_min}) "
                        f"= {derive.lift_to(ce, cap.lift, cap.lift_min)}, because the lift is "
                        f"max(int(CAP_LIFT_MIN), int(CAP_LIFT x cap)) = "
                        f"max({int(cap.lift_min)}, {int(float(cap.lift) * ce)}) = "
                        f"{max(int(cap.lift_min), int(float(cap.lift) * ce))}, so the cap can never "
                        f"move again on any evidence (capacity/levers.py::CAPLevers records this as "
                        f"the reason lift_min exists; it takes CAP_LIFT_MIN=0 together with a lift "
                        f"that rounds to zero AT THIS CAP, and is not where the shipped defaults "
                        f"sit)")
    if not vocab_armed:
        dead_facts.append(("vocabulary", "unarmed", {"targets": targets}))
    if vocab_armed and not vocab_room:
        if cv <= 0:
            dead_facts.append(("vocabulary", "nonpositive",
                               {"cap": cv, "lever": "CAP_VOCAB_START", "given": cap.vocab_start,
                                "origin": ov}))
            dead.append(f"the vocabulary arm's soft cap is {cv} (CAP_VOCAB_START="
                        f"{cap.vocab_start}, {ov}), and a mint ceiling at or below zero refuses "
                        f"every mint while the clamp that reads it goes negative (C30)")
        elif cv >= hard_vocab:
            dead_facts.append(("vocabulary", "at_ceiling", {"cap": cv, "hard": hard_vocab}))
            dead.append(f"the vocabulary arm's soft cap is {cv} against a hard ceiling of "
                        f"{hard_vocab} (CAP_VOCAB_START={cap.vocab_start}, {ov}), so there is no "
                        f"room to earn: the cap is ALREADY at or above the ceiling, which observe "
                        f"refuses by name as at_hard_ceiling BEFORE any lift is computed, and the "
                        f"owner's clamp does not reach this arm -- a clamp holds a lift AT the "
                        f"ceiling, which RAISES a cap only from below it, and from {cv} it would "
                        f"be a lowering, which this valve may never do. The unclamped arithmetic "
                        f"derive.lift_to({cv}, CAP_LIFT={cap.lift}, CAP_LIFT_MIN={cap.lift_min}) = "
                        f"{derive.lift_to(cv, cap.lift, cap.lift_min)} is not below the ceiling "
                        f"either, and is never applied here")
        elif not mask_dead:
            # THE MASK IS NOT ALWAYS THE ONLY THING IN THE WAY, AND THIS CLAUSE SAID IT WAS. This
            # branch is tested BEFORE the no-move branch below, so an arm that is unmasked AND has
            # an inert lift arrives here and used to be called an arm that "has room to earn". The
            # operator is then sent to set LM_MASK_DEAD_ROWS=1, which by cap.vocab_arm_honest's own
            # criterion must "change the thing this gate is about" -- and on those configurations it
            # does not: with the mask on the arm is still dead, one branch further down. The
            # ordering stays (dead_rows_unmasked is the refusal observe actually raises); what
            # changes is that the second obstacle is now named instead of hidden behind the first.
            inert_too = _clamped_lift(cv, hard_vocab, cap.lift, cap.lift_min) == cv
            dead_facts.append(("vocabulary", "refused_unmasked",
                               {"cap": cv, "hard": hard_vocab, "mask": mask_dead,
                                "lift": cap.lift, "lift_min": cap.lift_min,
                                "inert_too": inert_too}))
            if inert_too:
                dead.append(f"the vocabulary arm's soft cap is {cv} against a hard ceiling of "
                            f"{hard_vocab} and LM_MASK_DEAD_ROWS={mask_dead}, so observe refuses "
                            f"every lift it earns by name as dead_rows_unmasked -- the honesty "
                            f"precondition on this arm, tested and not met, reported on the next "
                            f"line by cap.vocab_arm_honest. AND THE MASK IS NOT THE ONLY THING IN "
                            f"THE WAY: setting LM_MASK_DEAD_ROWS=1 would not arm this arm either, "
                            f"because one earned lift does not move this cap -- "
                            f"derive.lift_to({cv}, CAP_LIFT={cap.lift}, "
                            f"CAP_LIFT_MIN={cap.lift_min}) = {cv} -- so the lever this clause "
                            f"names is not on its own a lever that changes the answer")
            else:
                dead.append(f"the vocabulary arm has room to earn ({cv} against a hard ceiling of "
                            f"{hard_vocab}) and LM_MASK_DEAD_ROWS={mask_dead}, so observe refuses "
                            f"every lift it earns by name as dead_rows_unmasked -- the honesty "
                            f"precondition on this arm, tested and not met, reported on the next "
                            f"line by cap.vocab_arm_honest")
        else:
            dead_facts.append(("vocabulary", "inert", {"cap": cv, "hard": hard_vocab,
                                                       "lift": cap.lift, "lift_min": cap.lift_min}))
            dead.append(f"the vocabulary arm's soft cap is {cv} and ONE EARNED LIFT DOES NOT MOVE "
                        f"IT: derive.lift_to({cv}, CAP_LIFT={cap.lift}, "
                        f"CAP_LIFT_MIN={cap.lift_min}) = "
                        f"{derive.lift_to(cv, cap.lift, cap.lift_min)}, because the lift is "
                        f"max({int(cap.lift_min)}, {int(float(cap.lift) * cv)}) = "
                        f"{max(int(cap.lift_min), int(float(cap.lift) * cv))}, so the cap can never "
                        f"move again on any evidence")

    if targets == "off":
        valve_gate = Gate(
            "cap.valve", False, targets, "off", reachable=False,
            reason="CAP_TARGETS=off: both caps sit at their hard ceilings and no lift can happen. "
                   "Reported unreachable rather than as 0 lifts, which would read as a valve that "
                   "ran and never fired -- the exact confusion this mechanism's own history is.")
    elif expert_room or vocab_room:
        also = f" ONE ARMED ARM IS STILL DEAD ON ARRIVAL: {'; '.join(dead)}." if dead else ""
        valve_gate = Gate(
            "cap.valve", True, arith, need,
            reason=f"CAP_TARGETS={targets}: an armed arm has room to earn and a cap the population "
                   f"can reach. FIRED HERE IS THE ARMING ANSWER AND NOT A LIFT -- this gate is "
                   f"built at startup, before the first flush, so no lift can have happened yet; "
                   f"the lifts are CAP.counters' lifts_experts and lifts_vocab, and a second count "
                   f"on this line would be a second source of truth for them.{also}")
    else:
        valve_gate = Gate(
            "cap.valve", False, arith, need, reachable=False,
            reason=f"CAP_TARGETS={targets} arms the valve and no armed arm can lift: "
                   f"{'; '.join(dead)}. Reported unreachable rather than as a switch that is on, "
                   f"which is what this line said until the arithmetic above was added -- FIRED, "
                   f"printed for a mechanism that cannot move, on every corner but `off`.")
    # THE CLAMP'S OWN READING, BUILT FROM THE SAME FACTS AND ANSWERING A DIFFERENT QUESTION.
    # cap.valve asks "can a lift happen at all"; cap.clamp asks "what happened to the lifts that
    # did". They share the reachability PREDICATE on purpose -- where no lift can be applied, no
    # lift can be clamped -- and sharing it is what keeps the two lines from disagreeing about
    # whether this valve is alive, which is the argument the startup_refusals paragraph above makes
    # for sharing the settling-point wire.
    # THEY SHARE THE PREDICATE AND THE FACTS, AND THEY DO NOT SHARE A SENTENCE. This call passed
    # `dead_reason="; ".join(dead)` until 2026-09-05 -- cap.valve's OWN prose, spliced into a gate
    # whose unreachable arm then opened "no lift can be earned at all on this configuration". Two of
    # cap.valve's dead clauses say the opposite of that opening, and on 3,464 of 25,344 swept
    # configurations the two arrived in one printed sentence: "... no lift can be EARNED at all
    # ...: the vocabulary arm has room to earn (1000 against a hard ceiling of 4096) and
    # LM_MASK_DEAD_ROWS=False, so observe refuses every lift IT EARNS by name as
    # dead_rows_unmasked". That is the false-equation class arriving inside the gate that was added
    # to end it. `dead_facts` is the repair: the same branches above record WHICH of the clamp's
    # three preconditions failed, as a computed value, and capacity/api.py::_clamp_blocked_clause
    # writes the clamp's own sentence about it. Borrowed prose is how the contradiction got in.
    # THE COUNTS ARE ZERO HERE BY CONSTRUCTION, not by measurement: this gate is built before the
    # first flush, exactly as cap.valve is, so the startup line is the "no lift was earned" state
    # and CAP.counters is where the other two reachable states are printed from the live ledger.
    valve.clamp_dead_facts = None if (expert_room or vocab_room) else tuple(dead_facts)
    clamp = _clamp_gate(arith, 0, 0, dead_facts=valve.clamp_dead_facts)
    valve.gates = (valve_gate, vocab_arm, clamp)
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

    The lift is capacity/api.py::_clamped_lift(cap, hard, cap.lift, cap.lift_min) --
    spine/derive.py::lift_to, the shipped module-level arithmetic covered by cap_test.py's
    known-answer table, held
    at the hard ceiling under the owner's clamp ruling below. Unclamped it replays sched_ctl's five
    real lifts
    3000 -> 3240 -> 3499 -> 3778 -> 4080 -> 4406. lift_min is not decoration: at cap 12,
    int(0.08*12) = 0 and without the floor the cap can never move again on any evidence -- a case
    THREE ENVIRONMENT SETTINGS AWAY (CAP_TARGETS=experts, a small CAP_FAB_START or FAB_SLOTS, and
    CAP_LIFT_MIN=0), NOT one the shipped defaults are in. This sentence said "reachable in the
    200-step empty-environment CPU run this rebuild launches with" until 2026-09-04; measured by
    building CAP against an empty environment, that run has targets='off', cap_experts resolved
    from the sentinel to the hard ceiling 4096, and lift_min=8, so no arm is armed, no cap is 12,
    and the floor moves the cap anyway (derive.lift_to(12, 0.08, 8) = 20). A printed gate reason
    quoted it, which is a higher bar than a docstring, and that is where it was caught.

    LEVERS READ: targets, lift, lift_min, pin_windows, stall_band
    WIRES READ: none (the two hard ceilings AND the honesty precondition were both frozen onto the
                Valve at new_valve -- counters["cap.hard_experts"], counters["cap.hard_vocab"] and,
                since 2026-09-04, counters["cap.mask_dead_rows"]. Everything this per-flush decision
                needs from another package is read ONCE, at build, which is what keeps this line
                `none` while the closed set below grew a reason that reads LM's flag.)
    DID IT FIRE: Decision carries, on EVERY call: checks (the stall test RAN -- distinct from it
                 passing), pinned_experts/pinned_vocab, held_experts/held_vocab (Windows),
                 improving, `clamped` (the lift was taken and HELD AT THE HARD CEILING -- see the
                 clamp ruling below; it is a property of a lift that HAPPENED and so is neither a
                 block reason nor a second spelling of `lifted`), and a BLOCK REASON from a closed
                 set: targets_off | not_pinned |
                 warmup(observations/1000) | blackout | not_stalled(|improving|/band) |
                 threshold(held/pin_windows) | at_hard_ceiling | dead_rows_unmasked(the vocabulary
                 arm only). This is the direct repair for the recorded failure at :7372-7380:
                 "0 lifts" ALONE CANNOT DISTINGUISH "never full" FROM "never plateaued", and those
                 have completely different fixes.

    `dead_rows_unmasked` IS NEW ON 2026-09-04 AND IT IS THE REFUSAL THIS PACKAGE HAS OWED SINCE THE
    HONESTY PRECONDITION WAS DECLARED. Until it existed, new_valve's cap.vocab_arm_honest Gate said
    in its own printed reason that NOTHING in this tree refused a vocabulary lift into unmasked dead
    rows -- the arm was armed, the precondition was tested and not met, and the run lifted anyway,
    so a report line was the entire consequence. It bites when the VOCABULARY arm is armed
    (targets in vocab|both), counters["cap.mask_dead_rows"] is False, and every other
    condition has passed: the lift that would have happened does not, and the histogram counts it.
      IT IS EVALUATED LAST, AFTER at_hard_ceiling, AND THE ORDER IS THE POINT. Placed first -- with
      targets_off, which it resembles, being knowable at startup -- it would answer every call on
      an unmasked run and the histogram would never learn whether that arm EVER pinned and stalled,
      which is the exact "0 lifts cannot distinguish never full from never plateaued" collapse this
      closed set was written to end. Placed last it counts precisely the lifts that were earned and
      then refused for dishonesty, which is a number no other line in the run carries.
      IT IS THE VOCABULARY ARM'S ALONE, and at targets=both the expert arm is untouched: an
      unmasked output layer says nothing about reserving EXPERT slots. Decision carries ONE
      block_reason and that is not new -- at_hard_ceiling is already per-arm -- so P4 must not let a
      blocked vocabulary arm read as a valve that did nothing; the per-arm truth is CAP.counters'
      lifts_experts and lifts_vocab, which is where every arm-level count belongs.
      IT IS NOT A STARTUP REFUSAL, DELIBERATELY -- AND THE GROUND IS NARROWER THAN THIS PARAGRAPH
      CLAIMED UNTIL 2026-09-04, which said only that a startup refusal "would remove a configuration
      that runs today -- CAP_TARGETS=vocab with the shipped LM_MASK_DEAD_ROWS=False". Stated that
      loosely it reads as though the valve works on that configuration and a startup refusal would
      take it away. IT DOES NOT WORK: no vocabulary lift can happen there, this block reason refuses
      every one, and cap.valve now reports the arm UNREACHABLE for exactly that. So THE LIFTING
      CAPABILITY IS ABSENT UNDER BOTH DESIGNS and it is not what separates them. WHAT ACTUALLY
      SEPARATES THEM is what the operator gets instead: a startup refusal ends the process and
      produces no measurement at all, while this refuses the LIFT and lets the RUN proceed -- the
      run trains, the expert arm still works at targets=both, the report still carries the curve,
      and the histogram carries a COUNT of the lifts that were earned and then declined, which is a
      number no other line produces and which a dead process cannot produce at all. Diagnosis over
      denial, on a precondition an operator fixes with one lever. spine/assemble.py's
      CAP.d_mask_dead_rows row names the stricter repair as the OWNER's to ask for ("a valve that
      refused to lift the vocabulary at all while the mask is off would need no flag"), and that
      decision stays the owner's; note in passing that its "would need no flag" does not hold as
      written, since a valve that refuses on this condition must still READ the condition to know
      when to refuse -- which is why the wire survives either ruling.

    THE CEILING OVERSHOOT IS CLAMPED, NOT REFUSED -- THE OWNER RULED IT ON 2026-09-04. A soft cap
    set just under its hard ceiling makes the FIRST earned lift land above the ceiling: at
    CAP_FAB_START=4095 against FAB_SLOTS=4096, derive.lift_to(4095, 0.08, 8) = 4422, which is 326
    slots above a ceiling printed on the same gate line. Two audits established that nothing in this
    tree said whether observe REFUSED that lift or CLAMPED it, and both declined to invent an
    answer. The owner's words, recorded as .rework/DECISIONS.md D16, are "let's soft clamp if a
    ceiling is overshot, until it goes down", and the ruling is CLAMP: the lift is APPLIED and the result held at the ceiling --
    capacity/api.py::_clamped_lift -- so the evidence that earned it is spent rather than wasted.
    WHAT THE REFUSE READING WOULD HAVE COST, MEASURED, because it is why the ruling matters: at the
    shipped CAP_LIFT=0.08 and CAP_LIFT_MIN=8 against a ceiling of 4096, every cap from 3794 to 4095
    -- 302 of the 4095 caps below the ceiling -- would be refused every lift it ever earns while
    sitting BELOW its ceiling reporting room to earn, which is the armed-but-dead reading
    spine/gate.py exists to refuse, recreated one mechanism down. At a small ceiling it is nearly
    total: at FAB_SLOTS=10 it is 7 of the 9 caps below the ceiling.

    WHICH READING OF "UNTIL IT GOES DOWN" THIS IS, AND WHY THE MECHANISM RATHER THAN A PREFERENCE
    DECIDED IT. The phrase carries two readings and a ruling implemented under an unstated one is
    how a decision quietly becomes something else, so both are written down:
      (i)  A CLAMPED STATE WITH AN EXIT -- the soft cap sits PINNED at the hard ceiling while demand
           is high and is RELEASED, going back down, when demand falls.
      (ii) A PER-LIFT ARITHMETIC OPERATION WITH NO STATE AT ALL -- each lift is
           min(lift_to(cap), hard) on its own, and "until it goes down" describes what a LATER
           evaluation does when it asks for less, not something this record remembers.
    D16 sets both out in the same two words and instructs that the one the MECHANISM can support is
    the one to take, on the test "whether `Valve` persists anything across flushes".
    THIS IS (ii). Three facts in this tree rule (i) out, and each of the three alone is enough:
      * A CAP MAY NEVER BE LOWERED. This module's founding sentence is a ceiling "raised, by a
        little, never lowered"; new_valve refuses CAP_LIFT < 0 and CAP_LIFT_MIN < 0 at startup to
        hold it, and _clamped_lift's own `max` exists so the clamp itself cannot break it.
        "Released" in (i) means the soft cap moves DOWN off the ceiling, which is the one thing this
        valve may not do -- so (i) is not a reading of this valve, it is a different mechanism.
      * NOTHING PERSISTS A CLAMPED STATE AND THE RECORD THAT WOULD CARRY IT IS CLOSED. Valve
        declares fourteen fields and none of them is a clamp flag; CAP.state below carries "the
        lifted caps AND the two pin clocks AND the high-water marks" and nothing else, and both
        halves of that payload are keyed by name in restore. A state with an exit that evaporates at
        the next checkpoint is the M38 family -- earned state rebuilt from somewhere it was never
        written -- arriving through the repair for a different one.
      * THE SIGNAL (i) WOULD RELEASE ON DOES NOT REACH THIS CALL AS A LEVEL. What arrives per flush
        is live_experts / live_vocab compared against the caps (a boolean per arm, `pinned`) and
        `improving`; the hard ceiling is FROZEN onto the Valve at build and cannot move under the
        cap. There is no "demand fell" edge here to release on.
    HOW AN OWNER TELLS THE TWO APART IN A REPORT, which is the test that makes this statement worth
    writing: under (ii) an arm reaches the hard ceiling ONCE and stays -- cap.clamp shows at most one
    clamped lift per arm, and every flush after it is refused as at_hard_ceiling. Under (i) the cap
    would LEAVE the ceiling when the population fell below it and be lifted back to it, so
    lifts_experts would keep climbing and the reported cap would print a SMALLER number than it
    printed on an earlier flush. A cap that ever goes down is (i); on this implementation it is a
    defect, and the two readings are therefore distinguishable from the report alone.

    A CLAMPED LIFT IS A LIFT TAKEN, AND IT GETS ITS OWN NUMBER BECAUSE IT IS NEITHER A CLEAN FIRE
    NOR A REFUSAL. It does NOT enter the block-reason histogram: that histogram counts the flushes
    on which NO lift happened, and filing a lift that happened in it would make its total stop
    meaning what the paragraph above says it means. It is counted in TWO ledgers answering two
    questions -- lifts_experts / lifts_vocab say the cap moved, and
    counters["cap.lifts_clamped_experts"] / counters["cap.lifts_clamped_vocab"], seeded at 0 by
    new_valve the way cap.mask_dead_rows is frozen on, say how many of those lifts were held at the
    ceiling. Decision.clamped is the same fact for the ONE flush, and capacity/api.py::_clamp_gate
    turns the pair into the cap.clamp reading.
    at_hard_ceiling IS UNCHANGED BY THE RULING, AND THAT IS WHY THE CLAMP CAN BITE ONLY ONCE PER
    ARM. It tests `cap >= hard` -- the reading new_valve's gate reasons have always spelled, "the cap
    is ALREADY at or above the ceiling" -- and it is evaluated BEFORE the lift is computed. So the
    sequence on an armed arm with room is: lifts land in full while the arithmetic stays at or below
    the ceiling, the first one that would overshoot is CLAMPED to it, and every flush after that is
    refused as at_hard_ceiling. The clamp therefore adds no new block reason and the closed set above
    is unchanged; what it adds is a counter for a lift that was taken at a reduced size.
    THE THIRD NOT-MOVING CASE IS NOT A CLAMP AND MUST NOT BE COUNTED AS ONE. derive.lift_to returns
    the cap UNCHANGED when BOTH its terms round to zero (CAP_LIFT_MIN=0 with int(CAP_LIFT x cap) ==
    0), and a lift declined as dead_rows_unmasked is a refusal for dishonesty. Three different
    things with three different readings: the inert lift is cap.valve's UNREACHABLE with its
    arithmetic printed, the dishonest one is a block reason in the histogram, and the clamped one is
    a lift TAKEN with a counter of its own. A report that adds them together says nothing.
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

    A CAP THIS CALL RETURNS CAN NO LONGER EXCEED ITS HARD CEILING BY LIFTING, WHICH IS THE OTHER
    HALF OF THE CLAMP RULING AND IS WHAT A READER OF THESE TWO NUMBERS RELIES ON. Before the ruling
    a soft cap of 4095 became 4422 against a ceiling of 4096 on its first earned lift, and the
    number an operator reads as the run's capacity exceeded the capacity the run has;
    capacity/api.py::_clamped_lift removes that route. IT DOES NOT MAKE THE PROPERTY UNIVERSAL, and
    the difference must not be glossed: an OPERATOR can still start a cap above the ceiling
    (CAP_FAB_START=5000 against FAB_SLOTS=4096 resolves cap_experts = 5000), which the valve never
    lowers and observe refuses to lift by name as at_hard_ceiling. So a consumer that must not see a
    number above its own ceiling still takes min(soft, hard) -- tok/api.py::Vocabulary._cap already
    does, and fabric/api.py::forward says of the spawn door that "It is NOT bound by CAP's operating
    soft cap". What the clamp buys is that the VALVE never creates that state.

    LEVERS READ: targets
    WIRES READ: none
    DID IT FIRE: caps.experts / caps.vocab as one-shot readings per flush, printed beside
                 fab.declined_cap and tok.mint_ceiling_refused
    """
    cap = cap.owned_by("CAP")
    # READ OFF THE VALVE, NOT RE-RESOLVED FROM THE LEVERS. new_valve decided where each cap STARTS
    # -- sentinel, operator or checkpoint, recorded in Valve.origin -- and observe is the only thing
    # that moves one afterwards. Re-deriving either number here would rebuild the starting cap on
    # every flush and silently discard whatever the valve had earned, which is the defect
    # Valve.origin exists to make visible: the old tree rebuilt `_cap_fab` from the environment on
    # every resume and handed a run that had spent hours lifting its starting cap back.
    # `targets` IS DECLARED AND READ, and it is read for the reason the arm exists: under "off"
    # _resolve already set both caps to their hard ceilings, so this returns the ceilings and the
    # consumers clamp against something real rather than against a valve that is not running.
    # It is read through the Gate the valve already carries rather than re-tested here.
    _ = cap.targets
    return Caps(experts=int(valve.cap_experts), vocab=int(valve.cap_vocab))


def startup_refusals(cap: Config, valve, *, live_experts):
    """Refusals that need two packages' numbers. Returns a list of strings.

    (1) A SOFT CAP BELOW THE POPULATION freezes growth for the run, silently (C30). Refuse, naming
        cap.fab_start, the population, and where the population came from.
        A CAP AT OR BELOW ZERO IS THE SAME CLAUSE AND IS SPELLED OUT because it is reachable from
        the environment and looks like a different kind of mistake: CAP_FAB_START=-5 resolves
        cap_experts=-5 with origin "operator (fab_start=-5)", and CAP_VOCAB_START likewise. It is
        below any population there can be, so this clause covers it -- `min(n_born, cap - fab.n())`
        is negative on the FIRST flush and growth is frozen for the whole run with nothing in the
        log. Naming it here is what the 2026-09-03 sentinel repair left owed: moving an explicit 0
        out of the soft-cap space did not close the shape 0 belonged to. This body exists as of
        2026-09-15 and the clause below refuses it by name; capacity/api.py::new_valve's cap.valve
        still reports it as UNREACHABLE with this arithmetic in the reason, which remains a report
        line and not a refusal -- the two are the startup ANALYSIS and the startup REFUSAL and they
        are meant to agree, not to substitute for one another.
        WHAT THIS CLAUSE CANNOT SAY, DECLARED RATHER THAN GLOSSED: "where the population came
        from". The population arrives as the plain int `live_experts` and carries no provenance, so
        the message below names BOTH reachable sources (a fresh run's FAB_N0, a resume's checkpoint)
        instead of the one that applies. Closing it means widening this frozen signature, which is
        an owner's call and not a P4 one; the alternative -- reading FAB's levers from inside CAP to
        tell the two apart -- is the ownership violation the spine exists to prevent.
    (2) THE IRREDUCIBLE COUPLING, DECLARED RATHER THAN REMOVED: the soft cap must sit at or below
        the cull's settling point, which arrives as the wire d_operating_population (FAB.pressure x
        FAB.slots, through the SAME derive.operating_population call the fabric's own row uses).
        Above it the population never pins, the pin clock never accumulates, and the valve is dead
        while looking armed.

    LEVERS READ: fab_start, targets. BOTH ARE READ BY THE BODY as of 2026-09-15; until then this
                 line named fab_start while nothing below touched it, and the messages printed the
                 RESOLVED cap under the lever's name -- telling an operator to change a number that
                 was not the number shown. `fab_start` is the value ASKED FOR and Valve.cap_experts
                 is what it RESOLVED to; they differ whenever the sentinel, a checkpoint or
                 targets="off" is in play, and both belong in a refusal about either.
    WIRES READ: d_operating_population
    DID IT FIRE: the returned list; an empty list is a positive result and is printed as one
    """
    cap = cap.owned_by("CAP")
    # THE WIRE IS READ ONCE, HERE. d_operating_population is FAB.pressure x FAB.slots through the
    # SAME spine/derive.py::operating_population call the fabric's own row uses, so this check and
    # the mechanism it checks cannot disagree about where the cull settles the population -- which
    # is the whole reason the quantity is a wire and not a second multiplication written here.
    settles = int(cap.d_operating_population)
    # ASKED VERSUS RESOLVED, AND THE DECLARED LEVERS READ LINE IS WHY BOTH ARE HERE. This body read
    # only `targets` and the wire until 2026-09-15, while the docstring declared "fab_start,
    # targets" -- a LEVERS READ line naming a lever the body never touched, which is the prose-that-
    # passes-a-parser shape tests/test_contract.py's closing note warns it cannot catch. Reading it
    # makes the line true AND makes the messages better: the number an operator TYPED and the number
    # the valve RESOLVED are different whenever the sentinel, a checkpoint or `targets=off` is in
    # play, and a message that prints only the second while naming the first as the thing to change
    # is telling them to edit a value they cannot see.
    asked_e = int(cap.fab_start)
    out = []
    cap_e, cap_v = int(valve.cap_experts), int(valve.cap_vocab)
    # origin is a 2-tuple set by new_valve. Read defensively rather than indexed blind: a Valve
    # built by a test with the default `origin=()` would turn a refusal into an IndexError, and a
    # guard that crashes while reporting is worse than one that reports "unrecorded".
    orig_e = valve.origin[0] if len(valve.origin) > 0 else "unrecorded"
    orig_v = valve.origin[1] if len(valve.origin) > 1 else "unrecorded"

    # (1a) A CAP AT OR BELOW ZERO. Taken BEFORE the below-population clause, and spelled as its own
    # sentence, because it is reachable straight from the environment and reads as a different kind
    # of mistake. _resolve reads an explicit 0 as the documented sentinel and hands back the hard
    # ceiling, so the only route to this state is a NEGATIVE request: CAP_FAB_START=-5 resolves
    # cap_experts=-5 with origin "operator (fab_start=-5)". It is below any population there can be,
    # so `min(n_born, cap - fab.n())` is negative on the FIRST flush and growth is frozen for the
    # whole run with nothing in the log saying so. BOTH ARMS GET THE CLAUSE: the vocabulary cap
    # reaches the identical state by the identical route through CAP_VOCAB_START, and there is no
    # live_vocab argument to reach it by the population test below.
    for lever_name, value, origin in (("CAP_FAB_START", cap_e, orig_e),
                                      ("CAP_VOCAB_START", cap_v, orig_v)):
        if value <= 0:
            out.append(f"the soft cap is {value}, from {origin}, which is at or "
                       f"below zero and therefore below any population there can be. The growth "
                       f"clamp takes min(n_born, cap - population), so it is negative on the FIRST "
                       f"flush and growth is frozen for the entire run while the trigger counts "
                       f"keep incrementing -- the C30 shape, where the log reads exactly as it "
                       f"would on a population legitimately at its cap. Set {lever_name} above the "
                       f"population, or to 0 for the sentinel, which starts at the hard ceiling.")

    # (1b) A SOFT CAP BELOW THE POPULATION. Same freeze, arrived at from above rather than from
    # below, and the one the 2026-09-03 sentinel repair left owed: moving an explicit 0 out of the
    # soft-cap space did not close the shape 0 belonged to. Guarded on `cap_e > 0` so a negative cap
    # is reported once, by (1a), which names the specific mistake -- two refusals for one number
    # would make an operator fixing the second wonder what the first one was.
    if 0 < cap_e < int(live_experts):
        out.append(f"the soft expert cap is {cap_e}, from {orig_e} (CAP_FAB_START={asked_e}), below "
                   f"the live population of {int(live_experts)}. The growth clamp takes "
                   f"min(n_born, cap - population) = {cap_e - int(live_experts)} on the first "
                   f"flush, so growth is frozen for the whole run and the pin counter reads exactly "
                   f"as it would on a population legitimately at its cap (C30). THE POPULATION'S "
                   f"SOURCE IS NOT VISIBLE FROM HERE -- it arrives as a plain count -- so it is "
                   f"either a resume carrying a checkpoint's population (523 experts against a gc "
                   f"arm's 160 is -363, the case this clause was written for) or a fresh run whose "
                   f"FAB_N0 is simply above this cap. Raise the cap above {int(live_experts)}, or "
                   f"set CAP_FAB_START=0 for the hard ceiling.")

    # (2) THE IRREDUCIBLE COUPLING, DECLARED RATHER THAN REMOVED. The soft cap must sit AT OR BELOW
    # the cull's settling point. Above it the population never reaches the cap, never pins, the pin
    # clock never accumulates, and the valve is dead while every report line says it is armed --
    # which is strictly worse than a valve that is off, because "off" is legible.
    #
    # GATED ON THE ARM BEING ARMED, AND THE GATE IS LOAD-BEARING RATHER THAN TIDINESS. At the
    # shipped defaults targets is "off", which makes _resolve hand back the HARD CEILING as the cap
    # -- 4096 against a settling point of 0.45 x 4096 -> 1844 -- so an ungated comparison refuses
    # the default configuration of the whole tree on a condition about a mechanism that is switched
    # off. Pinning is what the valve does; where the valve may not lift the experts, a cap above the
    # settling point costs nothing and there is nothing to report. Measured: cap.d_operating_population
    # is 1844 and cap_experts is 4096 on compose(environ={}).
    if cap.targets in ("experts", "both") and cap_e > settles:
        # THE SETTLING POINT IS NAMED, NOT RE-DERIVED. This message printed "(FAB_PRESSURE x
        # FAB_SLOTS)" until 2026-09-15 and that is not the arithmetic: spine/derive.py::
        # operating_population is `min(n_slots, max(3, n))` around the product, so at a small
        # FAB_SLOTS the printed equation and the number beside it disagree -- a false equation in a
        # refusal, which is the defect class this package was founded on. The wire's NAME is the
        # honest citation, and it is the same call the fabric's own row makes.
        clash = "" if int(live_experts) <= settles else (
            f" NOTE: the live population is already {int(live_experts)}, ABOVE this settling point, "
            f"so every cap at or below {settles} also trips the below-population clause and NO cap "
            f"satisfies both at once. That is a statement about the FAB defaults rather than about "
            f"any cap you could choose; it is filed as Q-CAP-2 in .rework/DECISIONS.md.")
        out.append(f"the soft expert cap is {cap_e}, from {orig_e} (CAP_FAB_START={asked_e}), with "
                   f"CAP_TARGETS={cap.targets!r}, above the cull's settling point of {settles} "
                   f"(the wire d_operating_population, through spine/derive.py::"
                   f"operating_population). The cull holds the population at about {settles}, so it "
                   f"never reaches {cap_e}, never pins, the pin clock never accumulates and the "
                   f"valve cannot lift -- while every report line says it is armed. Set "
                   f"CAP_FAB_START to {settles} or below, raise FAB_PRESSURE so the population "
                   f"settles higher, or set CAP_TARGETS to a value that does not include the "
                   f"experts.{clash}")
    return out


def state(valve):
    """The lifted caps AND the two pin clocks AND the high-water marks, for the checkpoint -- and,
    since 2026-09-24, each cap's PROVENANCE (armed_experts / armed_vocab, hard_experts /
    hard_vocab), which new_valve needs to tell an earned cap from a hard ceiling saved on an arm
    the valve did not govern.

    Adding the PIN CLOCKS is a change from the old tree and it is half of the M38 fix; the lifted
    caps were already saved at :5423 and the clocks were not, so the valve resumed with an earned
    ceiling and an unearned clock.

    THE CLAMP ADDS NOTHING TO THIS PAYLOAD, AND THAT ABSENCE IS LOAD-BEARING RATHER THAN AN
    OVERSIGHT. Under the reading of the owner's ruling that observe implements -- the clamp is a
    per-lift arithmetic operation and not a state with an exit -- there IS no clamped state to
    carry: what survives a resume is the lifted cap, which is already here. The two clamp counters
    are REPORT state and travel with lifts_experts / lifts_vocab, which this payload has never
    carried either. If a later reader wants the OTHER reading, this is the line that has to change
    first, and a clamp state that is not written here is one that evaporates at every checkpoint --
    the M38 family, arriving through the repair for a different one.

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
    # THE CLOCKS TRAVEL WITH THE CAPS, WHICH IS HALF OF THE M38 FIX. The old tree saved the lifted
    # caps at :5423 and not the clocks, so a resumed valve carried an EARNED ceiling and an UNEARNED
    # clock -- and with `_pin_prev = [0]` on the other side the first flush banked every window
    # since the run began. Both halves are here, as plain ints, because a checkpoint payload is
    # written by torch.save and read back by a different process: a units.Clock would round-trip as
    # a pickled object of a class that may have moved, and CAP.restore puts the kinds back.
    payload = {
        "cap_experts": int(valve.cap_experts), "cap_vocab": int(valve.cap_vocab),
        "pin_experts": int(valve.pin_experts), "pin_vocab": int(valve.pin_vocab),
        "hi_experts": int(valve.hi_experts), "hi_vocab": int(valve.hi_vocab),
        "hi_pin_experts": int(valve.hi_pin_experts), "hi_pin_vocab": int(valve.hi_pin_vocab),
        "best_improving": float(valve.best_improving), "stall_checks": int(valve.stall_checks),
        "last_window": int(valve.last_window),
    }
    # THE CAPS' PROVENANCE TRAVELS WITH THEM (2026-09-24). A cap saved on an arm the valve did not
    # govern -- every arm under the shipped CAP_TARGETS=off -- is that moment's HARD CEILING, not an
    # earned number, and a resume that widened FAB_SLOTS installed it as a soft cap below the new
    # ceiling. new_valve reads these to take a saved cap only where it was earned. Read off the
    # ledger new_valve seeded, because that is where the valve keeps what it was built under.
    targets = str(valve.counters.get("cap.targets", ""))
    for arm in ("experts", "vocab"):
        payload["armed_" + arm] = targets in (arm, "both")
        hard = valve.counters.get("cap.hard_" + arm)
        payload["hard_" + arm] = None if hard is None else int(hard)
    # THE LEDGER KEY, NOT AN ATTRIBUTE. This line used to be declared as `valve.state_written`,
    # which is neither a field of Valve nor produced anywhere, so the one signal saying the
    # checkpoint carried the valve's earned state had no home a reader could find.
    valve.counters["cap.state_written"] = valve.counters.get("cap.state_written", 0) + 1
    return payload


def restore(cap: Config, valve, state):
    """Put the pin clocks and the high-water marks back. THE CAPS ARE new_valve'S, NOT THIS
    FUNCTION'S.

    IT WROTE THE CAPS TOO UNTIL 2026-09-24, and that was the half of the resume that was wrong.
    new_valve takes the lifted cap so Valve.origin records where the starting cap came from
    (spine/compose.py's `valve` row and docs/04_CONTRACT.md say restore puts back "the two pin clocks
    and the high-water marks"); this function then overwrote whatever new_valve resolved with the
    saved number, on every arm the operator had not pinned -- under CAP_TARGETS=off, which "MUST
    ALSO MEAN THE STARTING CAPS ARE NOT APPLIED", and after a slot widening at the old ceiling --
    without touching Valve.origin or the cap.cap_* / cap.origin_* ledger, so the report named an
    origin for a number that came from somewhere else. Driven: a checkpoint doctored to
    cap_experts == n_live resumed at the shipped off valve with Caps(experts=n_live) and "off
    (valve disabled; the cap is the hard ceiling)" beside it, and a regression-triggered birth was
    declined at headroom 0.

    An EXPLICIT operator request still wins over the checkpoint -- see new_valve -- and is still
    COUNTED here as cap.state_refused, because this is the entry point that knows a checkpoint's cap
    was on offer -- and ONLY when it was: armed now, not saved on an unarmed arm, not saved at its
    own ceiling, which is new_valve's test for taking it.

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
    if not state:
        return
    asked = cap.given()
    # AN EXPLICIT OPERATOR REQUEST STILL WINS OVER THE CHECKPOINT, and this is the branch new_valve
    # points at. Taking the max instead made CAP_FAB_START=8 lose to a checkpoint that had reached
    # 48, which left the startup refusal unreachable on every checkpoint written from then on. THE
    # CAP IS LEFT EXACTLY AS new_valve RESOLVED IT ON EVERY ARM -- new_valve has already seen
    # `restored`, applied the operator / off / unarmed / checkpoint precedence and recorded the
    # answer in Valve.origin -- so this loop only COUNTS the arms where an operator's request beat a
    # saved cap. It used to write the saved cap onto every other arm, gated on nothing.
    # ONLY A CAP THAT WAS ON OFFER CAN BE REFUSED (2026-09-24). This counted every arm with a saved
    # cap and an operator lever, so a cap saved on an UNARMED arm, or any cap under CAP_TARGETS=off
    # or on an arm `targets` does not name -- none of which new_valve would have taken -- read as
    # "an operator's request beat a saved cap". Driven: a parent saved with armed_experts False,
    # resumed at CAP_TARGETS=experts CAP_FAB_START=400, printed state_refused 1, while the same
    # checkpoint without the lever resolves to the sentinel and never offers its cap. The test is
    # new_valve's checkpoint branch's: armed now, not saved unarmed, not saved at its own ceiling.
    targets = str(cap.targets)
    for field, lever_name, arm in (("cap_experts", "fab_start", "experts"),
                                   ("cap_vocab", "vocab_start", "vocab")):
        saved_hard = state.get("hard_" + arm)
        on_offer = (state.get(field) is not None and targets in (arm, "both")
                    and state.get("armed_" + arm) is not False
                    and not (saved_hard is not None and int(state[field]) >= int(saved_hard)))
        if lever_name in asked and on_offer:
            # COUNTED, BECAUSE A REFUSAL THAT CANNOT BE COUNTED IS THE STATE THIS PACKAGE EXISTS TO
            # MAKE READABLE. This is the THIRD state and not an error: a checkpoint whose lifted cap
            # loses to an explicit request is refused ON PURPOSE, and that has to be separable from
            # "no checkpoint at all", which reaches the early return above and counts nothing.
            valve.counters["cap.state_refused"] = valve.counters.get("cap.state_refused", 0) + 1
    # THE KINDS GO BACK ON HERE, because state() took them off to travel. Windows, because the pin
    # clocks accumulate WINDOWS -- units.py reserves Steps for the LR horizon, and applying the
    # other repair as well would fire the valve 16x too early at BATCH_W=16.
    for field, kind in (("pin_experts", U.Windows), ("pin_vocab", U.Windows),
                        ("hi_pin_experts", U.Windows), ("hi_pin_vocab", U.Windows)):
        if state.get(field) is not None:
            setattr(valve, field, kind(int(state[field])))
    for field, cast in (("hi_experts", int), ("hi_vocab", int), ("best_improving", float),
                        ("stall_checks", int), ("last_window", int)):
        if state.get(field) is not None:
            setattr(valve, field, cast(state[field]))
    valve.counters["cap.state_restored"] = valve.counters.get("cap.state_restored", 0) + 1


def counters(cap: Config, valve):
    """The DID IT FIRE ledger: lifts_experts, lifts_vocab, THE TWO CLAMP COUNTERS, the four
    high-water marks, stall_checks, best_improving, and THE BLOCK-REASON HISTOGRAM.

    The histogram is the point. round11 pinned 42,425 against a threshold of 20,000, lifted
    nothing, and left no evidence of which of the two remaining conditions refused.

    THE CLAMP COUNTERS ARE valve.counters["cap.lifts_clamped_experts"] AND ITS vocab TWIN, seeded
    at 0 by new_valve and incremented by observe when the owner's clamp ruling holds an earned lift
    at the hard ceiling. They are REPORTED HERE AND NOT RE-DERIVED: this entry point reads the
    ledger the valve carries, because a second count of the same event computed from the caps would
    be the two-sources-of-truth shape the rest of this file argues against.

    IT ALSO REBUILDS cap.clamp, through capacity/api.py::_clamp_gate, with the LIVE lifts and
    clamped counts. THAT IS THE HALF new_valve CANNOT PRINT: built at startup both numbers are 0 by
    construction, so the startup line can only ever read "no lift was earned" or UNREACHABLE, and
    the two readings that matter after a run -- every earned lift applied IN FULL, and M of N lifts
    CLAMPED at the ceiling -- are reachable only from here. The gate is built by the same function
    at both sites so the two lines cannot disagree about what the valve did.
    AND IT MUST RECOMPUTE `arith` FROM THE CURRENT CAPS BEFORE PASSING IT. new_valve's `arith` is a
    statement about the STARTING caps -- "experts 3/ceiling 10/settles 5/one lift -> 10, CLAMPED at
    the ceiling from 11" -- and passing that string through to an end-of-run FIRED line prints a
    true-at-startup equation as a statement about a run whose cap has been 10 for most of its
    length. That is the false-equation shape this package has paid for six times. (This sentence
    went on "and the only reason it is an obligation here rather than a defect is that this entry
    point is still a stub" until 2026-09-24; it has had a body since P4 wrote it.) The caps are on
    the Valve; the two hard ceilings are in the ledger this call already reads.

    LEVERS READ: targets, lift, lift_min, pin_windows, stall_band, fab_start, vocab_start
    WIRES READ: d_operating_population (the settling point, printed in the clamp arithmetic beside
                the experts cap; this line said "none" until 2026-09-24 while the body read it)
    DID IT FIRE: this call IS the DID IT FIRE surface for the package
    """
    cap = cap.owned_by("CAP")
    led = valve.counters
    hard_experts = int(led.get("cap.hard_experts", 0))
    hard_vocab = int(led.get("cap.hard_vocab", 0))
    ce, cv = int(valve.cap_experts), int(valve.cap_vocab)
    targets = cap.targets

    # ARITH IS RECOMPUTED FROM THE CURRENT CAPS, WHICH IS THIS ENTRY POINT'S OWN OBLIGATION.
    # new_valve's `arith` is a statement about the STARTING caps -- "experts 3/ceiling 10/settles
    # 5/one lift -> 10, CLAMPED at the ceiling from 11" -- and passing that string through to an
    # end-of-run FIRED line prints a true-at-startup equation as a fact about a run whose cap has
    # been 10 for most of its length. That is the false-equation shape this package has paid for
    # six times. The caps are on the Valve and both hard ceilings are in the ledger this call
    # already reads, so nothing has to be re-resolved from a lever to say it.
    # THE TWO HELPERS ARE THE SAME TWO new_valve CALLS, which is why they were hoisted to module
    # level rather than restated here: a second spelling of the lift arithmetic would let this line
    # and the startup line disagree about what one lift does.
    arith = []
    if targets in ("experts", "both"):
        arith.append(f"experts {ce}/ceiling {hard_experts}"
                     f"/settles {int(cap.d_operating_population)}"
                     f"/{_one_lift(cap, ce, hard_experts)}")
    if targets in ("vocab", "both"):
        arith.append(f"vocab {cv}/ceiling {hard_vocab}/{_one_lift(cap, cv, hard_vocab)}"
                     f"/mask_dead_rows {led.get('cap.mask_dead_rows')}")
    arith = ", ".join(arith) or targets

    lifts = int(led.get("cap.lifts_experts", 0)) + int(led.get("cap.lifts_vocab", 0))
    clamped = (int(led.get("cap.lifts_clamped_experts", 0))
               + int(led.get("cap.lifts_clamped_vocab", 0)))
    # REBUILT BY THE SAME FUNCTION new_valve USES, SO THE TWO LINES CANNOT DISAGREE ABOUT WHAT THE
    # VALVE DID. This is the half new_valve cannot print: built at startup both numbers are 0 by
    # construction, so its line can only ever read "no lift was earned" or UNREACHABLE, and the two
    # readings that matter after a run -- every earned lift applied IN FULL, and M of N lifts
    # CLAMPED at the ceiling -- are reachable only from here.
    # dead_facts IS THE STARTUP ANALYSIS, PASSED AS new_valve RECORDED IT ON THE VALVE, AND IT WAS
    # NOT PASSED AT ALL UNTIL 2026-09-24. The reason given was "if none was [taken] the startup gate
    # already said why in its own sentence" -- but valve.gates is never rendered, so this line was
    # the only cap.clamp a report carried, and without the facts _clamp_gate's UNREACHABLE branch
    # cannot open: at the shipped CAP_TARGETS=off every run printed "NO LIFT WAS EARNED ... An armed
    # arm has room" beside cap.origin_experts "off (valve disabled ...)". With the recorded facts
    # the 0/0 case reads UNREACHABLE on a dead configuration, and the lifts > 0 cases compare the
    # live ledger against the startup analysis, which is what the "falsified" / "agrees" clauses
    # were written to do. NOT RE-DERIVED from the current caps: after a lift to the ceiling that
    # would read `at_ceiling` and claim the startup analysis refused a lift the run took.
    clamp = _clamp_gate(arith, lifts, clamped,
                        dead_facts=getattr(valve, "clamp_dead_facts", None))

    out = {
        "cap.targets": targets,
        "cap.cap_experts": ce, "cap.cap_vocab": cv,
        "cap.hard_experts": hard_experts, "cap.hard_vocab": hard_vocab,
        "cap.origin_experts": led.get("cap.origin_experts"),
        "cap.origin_vocab": led.get("cap.origin_vocab"),
        "cap.lifts_experts": int(led.get("cap.lifts_experts", 0)),
        "cap.lifts_vocab": int(led.get("cap.lifts_vocab", 0)),
        # THE CLAMP COUNTERS ARE REPORTED AND NOT RE-DERIVED. A second count of the same event
        # computed from the caps would be the two-sources-of-truth shape this file argues against
        # everywhere else; observe increments these and this call reads them.
        "cap.lifts_clamped_experts": int(led.get("cap.lifts_clamped_experts", 0)),
        "cap.lifts_clamped_vocab": int(led.get("cap.lifts_clamped_vocab", 0)),
        "cap.hi_experts": int(valve.hi_experts), "cap.hi_vocab": int(valve.hi_vocab),
        "cap.hi_pin_experts": int(valve.hi_pin_experts),
        "cap.hi_pin_vocab": int(valve.hi_pin_vocab),
        "cap.stall_checks": int(valve.stall_checks),
        "cap.best_improving": float(valve.best_improving),
        "cap.mask_dead_rows": led.get("cap.mask_dead_rows"),
        # THE STATE COUNTERS, SO A RESUME IS READABLE FROM THE REPORT. Absent means the run never
        # wrote or restored valve state, which is a different fact from having written it zero
        # times, and `.get(..., 0)` would hide the difference.
        "cap.state_written": int(led.get("cap.state_written", 0)),
        "cap.state_restored": int(led.get("cap.state_restored", 0)),
        "cap.state_refused": int(led.get("cap.state_refused", 0)),
        # THE BLOCK-REASON HISTOGRAM IS THE POINT OF THIS CALL. round11 pinned 42,425 against a
        # threshold of 20,000, lifted nothing, and left no evidence of WHICH of the two remaining
        # conditions refused. observe writes one key per refusal ground; they are reported here
        # verbatim, and an EMPTY histogram beside lifts == 0 says the valve was never even asked.
        "cap.block_reasons": {k[len("cap.block."):]: v for k, v in led.items()
                              if k.startswith("cap.block.")},
        "cap.clamp": clamp,
    }
    return out
