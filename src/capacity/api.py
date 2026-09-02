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

RECORD TYPES RETURNED (P4 defines them):
  Valve     cap_experts, cap_vocab, the two accumulated pin clocks (Windows), four high-water
            marks, best improving seen, stall-test count, last-called window index, origin
  Decision  checks, pinned_experts/vocab, held_experts/vocab, improving, lifted, block_reason
  Caps      experts, vocab, and headroom(n) -> max(0, cap - n)
"""
from spine.lever import Config


def new_valve(cap: Config, *, restored=None):
    """Build the valve. Returns Valve.

    THE HARD CEILINGS ARRIVE AS WIRES: d_expert_slots (from FAB.slots) and d_vocab_slots (from
    LM.vocab_slots). Both starting caps are SENTINELS -- `fab_start == 0` means "start at the hard
    ceiling, i.e. no room to earn" -- and a default computed from another lever is what lever.py
    refuses by construction, so the literal stays 0 and the fallback is the wire. Until this
    contract added those two rows neither existed in COUPLINGS (capacity/levers.py::<module> says so),
    which means the sentinel stood for a number nothing supplied.

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

    LEVERS READ: targets, fab_start, vocab_start
    WIRES READ: d_expert_slots, d_vocab_slots, d_mask_dead_rows
    DID IT FIRE: Valve.origin -- for each target, (start, source) where source is one of "lever",
                 "hard ceiling (sentinel 0)", "checkpoint", so a cap that came from the wrong place
                 is visible
    """
    cap = cap.owned_by("CAP")
    _ = (cap.d_expert_slots, cap.d_vocab_slots, cap.d_mask_dead_rows)   # WIRES READ HERE
    raise NotImplementedError(
        "CAP.new_valve: P4 (capacity) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section CAP.")


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
    DID IT FIRE: valve.state_written
    """
    raise NotImplementedError(
        "CAP.state: P4 (capacity) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section CAP.")


def restore(cap: Config, valve, state):
    """Put the lifted caps, the pin clocks and the high-water marks back; symmetric with state().

    An EXPLICIT operator request still wins over the checkpoint -- see new_valve.

    LEVERS READ: targets, fab_start, vocab_start
    WIRES READ: none
    DID IT FIRE: valve.state_restored, valve.state_refused
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
