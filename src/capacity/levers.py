"""CAP -- the earned-capacity valve: the one mechanism that lets a run become bigger than it was.

WHAT THIS PACKAGE OWNS. One decision, taken over and over during a run: a population that is FULL, and a
loss that has STOPPED MOVING, may have its ceiling raised -- by a little, never lowered. Seven levers say
which populations the valve is allowed to lift (`targets`), where each of them starts (`fab_start`,
`vocab_start`), how much one lift hands out (`lift`, with `lift_min` as its floor), and the two conditions
that must BOTH hold before it hands out anything (`pin_windows` -- long enough hard against the ceiling;
`stall_band` -- flat enough in the loss). It owns neither population: the experts are FAB's and the
vocabulary is LM's/TOK's, and their HARDWARE ceilings (FAB_SLOTS, LM_VOCAB_SLOTS) are declared there. What
is CAP's is the OPERATING ceiling that sits underneath them and moves.

WHY THESE ARE THE LEVERS. Goal B is continual learning without catastrophic forgetting, and the whole
argument for this package is that capacity is one of the two honest answers to new material (the other is
the memory store). Every other growth path in the tree is triggered by a schedule or by a regression;
this one is triggered by EARNED PRESSURE -- the system asked for more room, held its hand up for a
measured length of time, and was not improving anyway. That is why the two conditions are separate levers
and why neither is optional: pressure alone grows a run that is still learning (waste), and stall alone
grows a run that has plenty of unused room (dilution). Goal A's "room for more modalities" lands here as
arithmetic rather than aspiration -- C31 recorded `grew 2048 -> 2048 (+0)` on the first continual-learning
run because the vocabulary was already full of English, so the second language got zero tokens of its own
and was spelled entirely with English's merges. `vocab_start` below is the lever that leaves it somewhere
to grow into.

THE MECHANISM IS LIVE AND ITS INSTRUMENT WAS BROKEN, which is the reason none of these nine rows was
dropped and the reason the census reasons are as long as they are. round4's growcap arm never lifted once
because the pin clock counted flushes; round11 pinned 42,425 and still lifted nothing because a second
gate one layer up compared a call count against the same threshold -- the first fault masking the second.
With both clocks fixed, sched_ctl lifted five times: 3000 -> 3240 -> 3499 -> 3778 -> 4080 -> 4406. A
mechanism never observed to fire is not thereby proven useless when the instrument was the thing that was
broken.

CENSUS ACCOUNTING (.rework/census.json, filtered on new_owner == "CAP"): 9 rows, all from the `capacity`
family, and no row filed elsewhere carries new_owner CAP.
    5 rename + 2 keep              -> 7 levers declared below
    2 merge                        -> both fold into `targets`, which is declared here (GROW_CAP_FAB and
                                      GROW_CAP_VOCAB become the `experts` / `vocab` / `both` values)
    0 drop
    0 promote-to-wire
  7 levers from 9 rows. CENSUS.md's ownership table says "CAP 9" because it counts ROWS assigned to this
  package, not declarations that survive them; the difference is exactly the two merges.

THREE CENSUS DEFECTS REPAIRED WHILE READING IT. All three were checked against these nine rows. Two were
present; the third was not, and the negative is recorded too, because "no unresolved merge" is only worth
anything if a later reader can see that it was looked for.

  DEFECT 1 -- DOUBLED ENVIRONMENT NAMES. ALL NINE rows name their target as PREFIX.PREFIX_FIELD:
  `CAP.CAP_TARGETS`, `CAP.CAP_LIFT`, `CAP.CAP_PIN_STEPS` and so on. spine/lever.py::Lever.env_name_for generates the
  environment name as f"{PREFIX}_{FIELD.upper()}", so `CAP.CAP_LIFT` taken literally declares a field
  named `CAP_LIFT` answering to CAP_CAP_LIFT -- a name no operator would ever type, that from_env() would
  never find, and that would therefore sit at its default for the life of the tree while every static
  check reported it declared, owned and resolved. Worse, `unread_env()` would then report the operator's
  real CAP_LIFT as a typo, so the one instrument that exists to catch this would accuse the operator.
  The prefix is stripped from the FIELD in every case and THE ENVIRONMENT NAME IS UNCHANGED from what the
  census intended -- that invariance is the point of the correction rather than a side effect of it.
  SEVEN CORRECTIONS LANDED ON DECLARATIONS: CAP_TARGETS, CAP_LIFT, CAP_LIFT_MIN, CAP_STALL_BAND,
  CAP_PIN_STEPS (see DEFECT 2 for the one further change to this one), CAP_FAB_START, CAP_VOCAB_START.
  The remaining two doubled rows are the merges, whose target `CAP.CAP_TARGETS` is a field already
  corrected above, so they mint nothing new. Nine doubled rows seen, seven corrections landed. Unlike FAB
  and MEM, where some rows already named a bare field and the same document did it both ways, EVERY CAP
  row carries the doubling -- which is the strongest evidence available that it is a clerical habit in
  the census and not a decision anybody took about names.

  DEFECT 2 -- CLOCK KINDS. Exactly one lever here is clock-typed, it is the flagship unit defect of the
  whole project, and it is RE-TYPED: the census files GROW_CAP_EVERY -> CAP_PIN_STEPS as unit `Steps`,
  and it is declared U.Windows below, under the name `pin_windows`.

    WHY WINDOWS. The clock this threshold is compared against is built at self_organize.py:7368,
    `_dstep = step - _pin_prev[0]`, and accumulated by pin_tick. `step` advances once per WINDOW
    (:6796 `i += WIN; step += 1`, and :7708) while the loop body -- including the whole valve block --
    runs once per FLUSH (:934). units.py is unambiguous about which kind that counter is: Windows is
    "what `step` counts", and Steps is "optimizer steps... what the LR schedule's horizon is denominated
    in, AND NOTHING ELSE". A threshold consumed against the window counter is therefore Windows. The
    measurement makes the same point from the other side: on the lr_pilot rehearsal at BATCH_W=16 the
    population sat pinned for 43,645 of these ticks while the broken per-call clock read 2,650 -- and
    2,650 is roughly the number of FLUSHES, which is roughly the number of true optimizer steps. The
    number written on the knob (20,000) has always been meant as the LARGER of those two counts. That is
    the window count.

    WHY THE NAME MOVED TOO, from the census's CAP_PIN_STEPS to CAP_PIN_WINDOWS. The kind and the name
    have to travel together or the next reader re-derives the defect from the label: a lever named
    ..._STEPS sitting beside a Windows-typed clock is an invitation to exactly the comparison units.py
    exists to refuse, and this project has the precedent both ways -- fabric/levers.py renamed FAB_STEPS
    to `hops` for meaning that word the wrong way, and tok/levers.py renamed TOK_PROBATION_STEPS to
    `probation_deadline` for this exact reason ("counts windows and says steps... a 16x error in the same
    family as pin_tick"). Recorded loudly because it is the only place this file departs from a census
    name: the census's intended spelling is CAP_PIN_STEPS, the declared environment name is
    CAP_PIN_WINDOWS, and if the tree later settles the kind the other way the NAME must go back with it.

    THE CONFLICT WITH THE SPINE: SETTLED, 2026-08-30, BY ADOPTING REPAIR (a). This note said "stated
    and not resolved" for six commits, and the cost of leaving it open was measured. src/capacity/api.py
    froze repair (a) as DONE -- "derive.pin_tick is re-typed to accumulate units.Windows ... NO
    CONVERSION HAPPENS ANYWHERE" -- while derive.pin_tick still refused a Windows, and
    docs/04_CONTRACT.md stated the same repair as done in one section and proposed in another. A P4
    implementer following the CAP contract would have written pin_tick(held_windows, pinned,
    elapsed_windows), got UnitError on the first flush, and been left with `int(held) >=
    cap.pin_windows` as the only non-raising form -- which is the original defect, restored at the
    comparison, by someone following the contract correctly.

    WHICH SIDE WAS WRONG IS NOT A PREFERENCE. spine/units.py defines Steps as "Optimizer steps. What
    the LR schedule's horizon is denominated in, AND NOTHING ELSE" and Windows as "Stream windows. What
    `step` counts." The quantity this clock accumulates is the delta of `step` (`_dstep = step -
    _pin_prev[0]`), and `step` advances once per window. So the Steps typing was the original
    conflation moved out of the arithmetic and into the type that had been added to prevent it -- and
    pin_tick's own docstring called the 43,645 "REAL STEPS", using "steps" for the loop counter one
    level below the defect it repaired.

    WHAT IS NOW TRUE, in three files:
      * spine/derive.py `pin_tick` accumulates Windows and RAISES on Steps, Flushes or Backwards. The
        32 captured oracle cases did not move: they record raw ints in and out, so they pin the
        arithmetic and never saw the kind. tests/test_derive.py's typed smoke assertions are what
        changed, and they are the only thing that ever covered it.
      * spine/assemble.py still wires FAB.d_cap_lift_period and TOK.d_cap_lift_period as a FLUSHES
        period -- repair (b) -- but they are read by fabric/api.py and tok/api.py for the REPORT only,
        beside the lift counters, because "0 lifts" cannot otherwise distinguish "never full" from
        "never plateaued". NOTHING COMPARES THEM AGAINST THIS CLOCK.
      * this file declares the threshold Windows, unchanged.
    BOTH REPAIRS CANNOT NOW BE LIVE IN THE VALVE AT ONCE, and not by discipline: Windows >= Flushes
    raises. That matters because applying both overshoots the other way -- pin clock in window deltas
    AND a threshold divided by batch_w makes 20,000 into 1,250 at BATCH_W=16 and the valve fires
    sixteen times too EARLY. Harder to see than the original, because a valve that fires looks like a
    valve that works.
    Doing the conversion inline at the comparison is still the original defect and is still refused.

  DEFECT 3 -- NO UNRESOLVED MERGE HERE, AND IT WAS CHECKED. Both merges name `CAP_TARGETS` as the
  survivor, and CAP_TARGETS has a row of its own in the same family: GROW_CAP, verdict rename. Nothing
  was invented, no lever below exists only because a merge pointed at it, and no row had to be emitted
  under its own name to avoid inventing a target. (FAB emitted two such orphans and MEM one; CAP has
  none.) The census's own reason for the merge is checked and holds: three booleans over exactly four
  reachable behaviours, with the master defined as the OR of the two arms.

WHAT IS DELIBERATELY ABSENT -- the values this package NEEDS and may not declare. lever.py refuses a
d_-named lever precisely so a declaration cannot shadow the wire that writes it, and every one of these
is a number another package owns. ALL FOUR WIRES NOW EXIST IN spine/assemble.py's COUPLINGS and every one
of them is read by a body or a stub in capacity/api.py:
    d_expert_slots         <- FAB.slots              the hard expert ceiling; `fab_start = 0` means
                                                     "start here". Read by capacity/api.py::new_valve.
    d_vocab_slots          <- LM.vocab_slots         the hard vocabulary ceiling; `vocab_start = 0`
                                                     means the same. capacity/api.py::new_valve.
    d_mask_dead_rows       <- LM.mask_dead_rows      the honesty precondition on lifting the vocabulary
                                                     (below). capacity/api.py::new_valve.
    d_operating_population <- FAB.pressure x FAB.slots, through the SAME spine/derive.py::
                                                     operating_population call the fabric's own row
                                                     uses. The soft cap must sit at or below the cull's
                                                     settling point or the population never pins.
                                                     Read by capacity/api.py::startup_refusals.
    the LIFTED CAPS        <- CKPT                   NOT a wire and must not become one: earned state,
                                                     not configuration (see `fab_start`). It arrives as
                                                     new_valve's `restored` argument.

THIS PARAGRAPH SAID THE OPPOSITE FOR SEVERAL COMMITS AND THE STALENESS HAD TEETH. It read "NONE OF THE
FOUR IS IN spine/assemble.py's COUPLINGS TODAY ... there are no CAP wires to be found unread, because
there are no CAP wires", said the only d_expert_slots row targeted DOM, said no d_vocab_slots row existed
at all, and said the two rows that need this package's numbers -- FAB.d_cap_lift_period and
TOK.d_cap_lift_period -- source them from a prefix named TRAIN. Checked against the tree on 2026-09-03:
all four CAP destinations are declared, both cap-lift rows source ("OPT.batch_windows", "CAP.pin_windows")
under this package's own prefix, and spine/assemble.py::_check_endpoints itself records TRAIN as a
corrected name. The cost of leaving it standing is not cosmetic: it tells whoever ports the valve to ADD
four couplings that already exist -- work that was already done, spending four of the SIX edges the
budget still has (19 cross-package wires of WIRE_BUDGET=25; see the correction below) on rows that are
already in the table. A file that reports an absence for something present corrupts the ledger in
exactly the direction that is hardest to notice, because nobody greps to confirm a "not there yet".

AND THE BUDGET CLAUSE ABOVE WAS ITSELF A MISCOUNT, CORRECTED 2026-09-04 -- it read "has room for two
more edges in total -- so acting on the sentence would fail at build() with an over-budget refusal".
Both halves were wrong. Measured by running tests/test_couplings.py today: 23 DECLARED COUPLINGS, of
which 19 are cross-package WIRES against WIRE_BUDGET=25 and 4 are intra-package, so SIX edges remain,
not two. The miscount came from counting declared couplings as wires; an intra-package coupling books
no edge, which is why the two numbers differ by exactly four. The consequence clause fell with it:
adding four couplings takes the ledger 19 -> 23 of the 25 and build() does NOT refuse it. THIS IS NOT A
HARMLESS ARITHMETIC SLIP, AND THE REASON GIVEN HERE UNTIL 2026-09-04 WAS ITSELF WRONG: it read "at least
two agents declined to widen a signature partly because they believed the wire alternative was nearly
exhausted". Nothing in src/, docs/, tools/ or .rework/ says any agent took that decision, and it points
the wrong way -- a budget believed nearly exhausted is an argument AGAINST spending a wire, i.e. FOR
widening a signature, so it cannot be why one was declined. WHAT IS SUPPORTED, in the sentences
themselves rather than in anybody's stated motive: a number wrong in the SCARCE direction biases every
choice that weighs a wire against a widened signature, and it biases it toward the signature, which is
the option nobody has to justify at build(). THE BIAS WAS CARRIED IN FIVE PLACES AT ONCE AND ALL FIVE
ARE NOW CORRECTED. src/eval/api.py::<module> said "two left" (the original find); this file told a
porter that four couplings which ALREADY EXIST would be refused at build(); docs/04_CONTRACT.md's
Q-WORLD-6 point 4 called a legal row "one of the last lines"; src/eval/levers.py::<module> told a
reader that WIRE_BUDGET left "room for two more edges in the whole tree", and now reads "so SIX edges
remain in the whole tree"; and src/spine/assemble.py's WORLD.d_manage_period_windows NOT_WIRES row
said a row there would "spend one of the last coupling lines" -- the one carrier of the five that
tools/render_wiring.py republishes VERBATIM into docs/03_WIRING.md, so that miscount was being
published rather than merely written. THAT FIFTH ONE IS CORRECTED TOO, and the correction is now the
sentence render_wiring.py publishes: read on the tree today, spine/assemble.py's row says a row there
"would also spend one of the six cross-package edges that remain on a WORLD.manage that is itself
deferred today", and docs/03_WIRING.md:188 carries the same words.
THIS PARAGRAPH SAID THAT ROW "still says, present tense" UNTIL 2026-09-04, AND IT WAS FALSE WITHIN THE
HOUR IT WAS WRITTEN: the report filing it as outstanding is timestamped 18:47 and the carrier was
corrected by its own owner shortly afterwards, so the sentence describing the residue outlived the
residue. A STATUS IS A COPY OF A FACT AND ROTS EXACTLY THE WAY A COUNT DOES -- which is this
paragraph's own subject, one level up -- and no check in the suite can see either kind: K13 reads
DIGITS, and neither "last" nor "still" is a number. That property is what let the count survive five
files, and it is what let the status rot go unnoticed too. Every one of the five argued against a
wire on its price. The live figures are printed by tests/test_couplings.py's C4 and embedded by
spine/assemble.py::render, so a prose copy is one that can go stale in silence; this one had, in more
than one file at once.

O4 IS GREEN FOR A REAL REASON NOW, WHICH IT WAS NOT WHEN THAT PARAGRAPH WAS WRITTEN. It reports twenty-
three declared destinations, zero declared-but-unread and zero deferred; CAP contributes four of the
destinations and reads all four. The old note that O4 could not go red here even in principle no longer
applies to this package: tests/test_ownership.py's O4 defers only while a package has no module other
than levers.py/__init__.py, and capacity/api.py is that module, so an unread CAP wire would now fail.

IMPORT STYLE, AND WHY IT DEPARTS FROM THE ASSIGNMENT'S SKETCH. `from ..spine.lever import ...` cannot work
here. Every entry point in this tree puts `src/` itself on sys.path (tests/test_ownership.py,
tests/test_derive.py, and this file's own verification command), which makes `capacity` a TOP-LEVEL
package, and a relative import that walks above one raises "attempted relative import beyond top-level
package" at import time. The absolute form below is what every sibling levers.py file in src/ uses and what
`spine` is already imported by.
"""
from spine.lever import Lever, LeverSet
from spine import units as U


class CAPLevers(LeverSet):
    """The valve's declared knobs: what it may lift, from where, by how much, and on what evidence.

    Read `cfg.lift`, never an environment name. Every value here is resolved once by spine.assemble and
    frozen; a function receiving this Config should open with `cap.owned_by("CAP")`, because a Config is
    an ordinary object and a foreign one handed in reads happily and wrongly -- `memory_prune(configs
    ["FAB"])` returning FAB_SLOTS is the reproduction that put that method in lever.py.
    """

    PREFIX = "CAP"

    # ==============================================================================================
    # WHAT THE VALVE MAY LIFT -- one lever where the old tree had three booleans
    # ==============================================================================================

    targets = Lever("off", "Which populations the valve may lift: neither, the experts, the vocabulary, "
                           "or both.", U.NAME, choices=("off", "experts", "vocab", "both"))
    # THE DEFAULT IS THE OLD DEFAULT RE-ENCODED, NOT A NEW DECISION. The old tree shipped
    # GROW_CAP=0, GROW_CAP_FAB=1, GROW_CAP_VOCAB=1 (self_organize.py:252-254), and the master is the OR
    # of the two arms, so the shipped behaviour is "the valve does nothing" -- which is "off". The four
    # reachable behaviours map exactly:
    #     GROW_CAP=0, anything            -> "off"
    #     GROW_CAP=1 FAB=1 VOCAB=1        -> "both"      (growcap, gate_soft, all gc_* arms, lr_pilot)
    #     GROW_CAP=1 FAB=1 VOCAB=0        -> "experts"   (lr_expvalve and every sched_* and lr_075 arm --
    #                                                     longrun.sh:470 names round12 as the one clean
    #                                                     read of the expert valve alone)
    #     GROW_CAP=1 FAB=0 VOCAB=1        -> "vocab"     (never run; a legitimate mirror of lr_expvalve,
    #                                                     which is why the STATE survives the merge)
    # WHAT DOES NOT SURVIVE, AND WHY THAT IS THE POINT OF THE MERGE. The fifth combination -- master on,
    # both arms off -- was expressible and was a lie. GROW_CAP_FAB was read at only two places, the pin
    # test (:7366) and the report (:9571), while the starting expert cap it nominally governed was read
    # UNGATED at :5209 and fed the growth clamp `_nb = min(_nb, _cap_fab[0] - fab.n())` at :7444 whatever
    # it said. So GROW_CAP_FAB=0 read as "the expert valve is off" while still freezing fabric growth at
    # GROW_CAP_FAB0 -- an off-switch that does not switch the mechanism off (ISSUES.md:1464). One
    # choices-valued lever makes `off` mean one thing at both targets and leaves no second boolean to
    # contradict it.
    # A NOTE THE PORT MUST NOT LOSE: the ungated read at :5209 is the reason this cannot be a pure
    # rename. Under this lever, `targets == "off"` MUST also mean the starting caps below are not applied
    # -- otherwise "off" still clamps growth and the untrippable guard survives the rebuild that was
    # supposed to remove it.
    # choices= IS PREVENTION HERE, NOT REPAIR, AND THE DISTINCTION IS WORTH STATING. None of CAP's old
    # knobs is among the eleven silent-else knobs ISSUES P1-M24 lists (SIG_MODE, MODEL, VERIFY, LR_SCHED,
    # KEY_SRC, SIG_SPACE, EVICT, CULL_MODE, WARMSTART_MODE, TOK_PROBATION_BY, CHAIN_ROUTE) -- they were
    # all ints and bools, so they had no else-branch to fall into. This is a NEW string knob minted by
    # the merge, exactly like DOM's `accept_rule` and `shift_rule`, and without choices= `CAP_TARGETS=
    # Experts` or `=vocabulary` would land in whichever branch the reader writes last and run an arm the
    # operator did not ask for. Note also that choices= could not have saved the three booleans it
    # replaces: lever.py::Lever.coerce coerces anything outside ("0","","off","no","none","false") to True, so
    # GROW_CAP_FAB=flase would have been ON, and choices=(True, False) would pass every typo it was
    # added to catch (the argument eval/levers.py::<module> makes at length).

    # ==============================================================================================
    # WHERE EACH CEILING STARTS -- the valve only ever lifts, so this is the floor of the whole run
    # ==============================================================================================

    fab_start = Lever(0, "Soft expert cap the valve starts from and only lifts; 0 means start at the "
                         "hard ceiling, i.e. no room to earn. Also the fabric growth clamp's operating "
                         "ceiling.", U.EXPERTS)
    # 0 IS A SENTINEL AND THAT IS WHY IT IS STILL THE LITERAL. The old line is
    # `_cap_fab = [int(_i("GROW_CAP_FAB0", 0)) or FAB_NMAX]` (:5209): zero means "use FAB_NMAX". A
    # default computed from another knob is precisely what lever.py::Lever.__init__ refuses -- "a value derived
    # from another lever is a WIRE, not a default" -- so the fallback becomes the declared wire
    # d_expert_slots from FAB and the LEVER keeps only its literal, which is 0, which is what the census
    # records and what the old _SPEC records. THE LITERAL THE DEFAULT RUN ACTUALLY USED was FAB's ceiling:
    # 4096 (FAB_NMAX's default, now FAB_SLOTS). The arms set it deliberately and across a wide range --
    # 160 (gc_pin, gc8_*), 256 (gc_real, gc_fast, gc_loose), 2048 (growcap, gate_soft) and 3000 (lr_pilot,
    # every sched_* arm, lr_075) -- so it is genuinely user-facing and not a hidden constant.
    # THE NAME CHANGED FOR A SECOND REASON. "FAB0" reads as a sibling of FAB_N0 (the fabric's STARTING
    # POPULATION) and is not one; it is the valve's starting CEILING. Two adjacent numbers, one of which
    # is a population and one a bound on it, must not share a spelling.
    # TWO DEFECTS RIDE ON THIS LEVER AND THE PORT OWES AN ANSWER TO BOTH:
    #   (1) THE CLAMP GOES NEGATIVE. `_nb = min(_nb, _cap_fab[0] - fab.n())` (:7444) is negative the
    #       moment the population exceeds the soft cap, which freezes growth for the entire run with
    #       nothing in the log saying so -- the trigger counts still increment and the pin counter reads
    #       exactly as it would on a population legitimately at its cap (C30, ISSUES.md:1464).
    #       Unreachable on a fresh run; entirely reachable on a resume, where the population comes from
    #       the checkpoint: 523 experts against a gc arm's 160 is -363.
    #   (2) THE LIFTED CAP IS EARNED STATE, NOT A KNOB. `_cap_fab` was rebuilt from the environment on
    #       every resume, so a run that spent hours lifting handed its successor the STARTING cap back.
    #       It belongs in the checkpoint, which makes the resumed value a CKPT wire and not a re-read of
    #       this lever. :5221-5227 is the shipped half-repair (restore from the checkpoint unless
    #       GROW_CAP_FAB0 was set explicitly) and it depends on reading os.environ to know whether the
    #       operator asked -- which from_env() answers properly through Config.given().
    # AND ONE COUPLING THAT IS IRREDUCIBLE, DECLARED RATHER THAN REMOVED: the soft cap must sit at or
    # below the cull settling point FAB_PRESSURE x FAB_SLOTS or the population never pins, the pin clock
    # never accumulates, and the valve is dead while looking armed. It arrives as the wire
    # d_operating_population and capacity/api.py::startup_refusals is the check that compares against it.
    # THE NUMBER, AT THE SHIPPED DEFAULTS, BECAUSE THIS COMMENT CARRIED A STALE ONE: it said
    # "0.45 x 8192 = 3686 at the launch config", and FAB_SLOTS defaults to 4096, not 8192 -- no config in
    # this tree sets 8192. The wire actually delivers 0.45 x 4096 -> 1844, verified by building CAP and
    # reading cap.d_operating_population. The stale figure was twice the real one in the direction that
    # hurts: a soft cap of 3000, which every sched_* arm used, passes a check against 3686 and sits ABOVE
    # 1844, so the population never reaches it, the pin clock never accumulates, and the valve is dead
    # while every report line says it is armed -- the exact failure the sentence exists to prevent.

    vocab_start = Lever(0, "Soft vocabulary cap the valve starts from and only lifts; 0 means start at "
                           "the model's row count, i.e. no room to earn.", U.TOKENS)
    # SAME SENTINEL, SAME REASONING, DIFFERENT SOURCE PACKAGE -- and the difference matters. The census
    # says the fallback is VMAX and calls it a wire from TOK; but the census ALSO moved VMAX to LM as
    # LM_VOCAB_SLOTS (default 4096, "emb.weight and head.weight have exactly this many rows"), so the
    # wire is d_vocab_slots FROM LM. TOK holds no ceiling of its own to give. Recorded because a wire
    # declared against the wrong package fails at build() and reads like a missing lever.
    # Read at exactly one site, :5262, `if GROW_CAP and USE_TOK and _i("GROW_CAP_VOCAB0", 0):
    # TOK.vmax = min(TOK.vmax, ...)` -- correctly gated on the valve being armed. It is the FABRIC side
    # (:5209, ungated) that has to be made to match this one, not the reverse.
    # Set in every valve arm: 640 (gc_*), 1024 (growcap, gate_soft), 2048 (lr_pilot, sched_*, lr_075).
    # It is the only way to give the vocabulary somewhere to grow INTO, which is what round8's
    # grown-versus-given comparison and lr_pilot's 2048 -> 8192 walk both depend on.
    # THE ONE CLEAN MEASUREMENT OF THE VOCABULARY ARM, AND IT DOES NOT FLATTER IT: round12 (longrun.sh:
    # 470-471) is the single one-knob comparison in the whole sequence and it reads 2.021 b/B frozen at
    # 2048 against 2.162 grown to 3784 -- lower is better, so the FROZEN arm won by 0.141. That is a
    # SIGNAL and not a verdict: it is one run, at one scale, on one language, and it is confounded with
    # the retok blackout defect below, which was live at the time and manufactured the stalls that
    # authorised those lifts. It is recorded here because `targets` defaults to "off" and somebody will
    # eventually ask which arm to turn on first; the honest answer today is "experts, and measure again".
    # THE HONESTY PRECONDITION TRAVELS WITH IT AND IS NOT A LEVER HERE. Lifting the vocabulary while
    # LM.mask_dead_rows is off reserves rows that sit in the softmax denominator indexing nothing, so the
    # run measures the reservation and not the mechanism (self_organize.py:686-688): at 8192 reserved
    # against 2048 minted that is 6144 dead rows taking probability mass. It arrives as d_mask_dead_rows,
    # because it is LM's number and a second copy here could disagree with it.
    # AND THE FEEDBACK LOOP THE PORT MUST BREAK: the 0.75 GB run walked the vocabulary 2048 -> 8192 in 19
    # lifts because each lift minted tokens, forced a retok, and the resulting loss jump read as the
    # stall that authorised the next lift. The fix is to respect note_shift's blackout -- "the loss jump
    # is OURS, not the data's" -- which PlateauGrowth already honours and the valve did not. That is a
    # CAP-side CONDITION, not a knob: there is deliberately no lever below that switches it off.

    # ==============================================================================================
    # HOW MUCH ONE LIFT HANDS OUT
    # ==============================================================================================

    lift = Lever(0.08, "Fraction of the current soft cap added on each earned lift.", U.FRACTION)
    # A FRACTION, WHICH IS THE ONLY FORM OF THIS KNOB THAT MEANS THE SAME THING AT EVERY CAP SIZE, and it
    # reached that shape by failing twice. As a MULTIPLIER of 2.0 each lift handed out more than the one
    # before and the cap ran away. As a flat COUNT of 256 the same knob was +160% against gc_pin's expert
    # cap of 160 and +12.5% against a vocabulary at 2048 -- a nudge and a doubling under one name, in one
    # run. The shipped arithmetic is `lift_to(cap, frac, floor) = int(cap) + max(int(floor),
    # int(frac * cap))` (self_organize.py:742-745), already isolated at module level and covered by
    # cap_test.py's known-answer tests, so it ports as shipped code rather than as a re-derivation --
    # and it replays: 3000 -> 3240 -> 3499 -> 3778 -> 4080 -> 4406 are sched_ctl's five real lifts.
    # ONE CORRECTION TO THE CENSUS REASON, WHICH IS ABOUT THE COUNT AND NOT THE NUMBER: it says 0.08
    # "takes eleven lifts to double". Replaying lift_to with truncation, it is TEN at every starting cap
    # the arms actually used -- 160 -> 336, 256 -> 545, 640 -> 1377, 1024 -> 2205, 2048 -> 4412,
    # 3000 -> 6471, 4096 -> 8836, all in ten. The property being claimed (one lift means the same thing
    # at every size) holds exactly; only the count was off by one, and repeating it here would make this
    # file the second place it is written down wrong.

    lift_min = Lever(8, "Absolute floor on one lift, so a small soft cap still moves.", U.SLOTS)
    # KEPT ON ITS OWN MERITS, NOT ON AN ABSENCE OF EVIDENCE. It never bound in any GPU arm -- the
    # smallest cap ever run is 160, where int(0.08 x 160) = 12 > 8 -- and that is exactly the shape of
    # argument the owner forbade for drops, so the case has to be arithmetic instead. It is: below cap
    # 100 the fraction does not merely inch, it FREEZES. At cap 12, int(0.08 x 12) = int(0.96) = 0, so
    # without the floor `lift_to` returns 12 and the cap can never move again, on any evidence, forever.
    # IT IS REACHABLE FROM THE ENVIRONMENT AND IT IS NOT WHERE THE DEFAULTS SIT, and the difference is
    # written out because this comment claimed the second until 2026-09-04: it read "reachable in the
    # first place this rebuild runs -- the 200-step empty-environment CPU run with a tiny fabric".
    # MEASURED, by building CAP against an empty environment: targets resolves to "off", fab_start is
    # the sentinel 0 which resolves cap_experts to the hard ceiling 4096 (not 12), and lift_min is 8 --
    # so no arm is armed, no cap is 12, and even at cap 12 the floor moves it (lift_to(12, 0.08, 8) =
    # 20). Reaching the inert case takes three deliberate settings: CAP_TARGETS=experts, a small
    # CAP_FAB_START (or a small FAB_SLOTS), and CAP_LIFT_MIN=0. That is still the case for the floor --
    # an operator can type it, and capacity/api.py::new_valve's cap.valve now reports it UNREACHABLE
    # with the arithmetic printed -- but a knob an operator can reach is not the run that launches, and
    # a printed gate reason quoted the stronger claim, which is where it was caught.
    # NEGATIVE VALUES OF EITHER OF THESE TWO ARE REFUSED AT STARTUP, by name, in
    # capacity/api.py::new_valve. `lift_to` is `cap + max(int(floor), int(frac x cap))`, so with BOTH
    # negative the max is negative and an EARNED lift SHRINKS the cap -- lift_to(12, -0.5, -100) = 6 --
    # against this package's founding sentence, "raised, by a little, never lowered". Neither negative
    # buys anything a legal value does not: with lift_min >= 0 a negative lift is exactly lift=0, and
    # with lift >= 0 a negative lift_min is exactly lift_min=0. CAP_LIFT ABOVE 1 IS NOT REFUSED and
    # that is deliberate -- U.FRACTION's unit string is a label the census renders and not a bound
    # (spine/lever.py::Lever carries choices and no numeric range), and a lift of 2.0 still RAISES.
    # UNITS: U.SLOTS rather than U.EXPERTS because the same floor is applied to the
    # vocabulary lift as well (:7434), where the rows are tokens; SLOTS is the one word true of both.

    # ==============================================================================================
    # WHAT MUST BE TRUE BEFORE A LIFT IS EARNED -- two conditions, both required
    # ==============================================================================================

    pin_windows = Lever(20000, "Accumulated windows a population must sit pinned against its soft cap "
                               "before a lift is earned.", U.Windows)
    # CENSUS NAME: CAP_PIN_STEPS, unit Steps. DECLARED HERE AS CAP_PIN_WINDOWS, unit U.Windows. Both
    # halves of that change, the evidence for them, and the three-way disagreement they leave standing
    # with spine/derive.py and spine/assemble.py, are set out under DEFECT 2 in the module docstring --
    # they are too long for a declaration comment and too important to compress. The short form: the
    # clock this threshold is compared against is `step`, `step` advances once per WINDOW, and units.py
    # reserves Steps for the LR horizon and nothing else.
    # IT IS A THRESHOLD, NOT A CADENCE, WHICH IS WHY `_EVERY` HAD TO GO. `pin_tick` accumulates the delta
    # while the population is at its cap and DECAYS it while below (self_organize.py:930-948, now
    # spine/derive.py::flush_period_windows), so this is time-spent-pinned, accumulated -- not time since the last lift and
    # not a modulo. The first version stored the step at which a cap first saturated and required an
    # UNBROKEN run, which is harmless for a vocabulary (it never shrinks) and fatal for the experts
    # (a cull drops the population below its cap within a thousand steps and the clock restarted every
    # time). A name reading `_EVERY` is what let it be mis-compared against a per-flush count twice, in
    # two different places, one masking the other.
    # THE MEASUREMENT, BECAUSE IT IS THE WHOLE CASE FOR TYPING CLOCKS AT ALL: on the lr_pilot rehearsal
    # at BATCH_W=16 the population sat pinned for 43,645 windows while the clock read 2,650 against
    # 20,000, so the report truthfully said "reached the cap but never held it long enough" about a clock
    # running at 1/16 its label. Separately the outer warmup gate read `fabgrow.n >= GROW_CAP_EVERY`,
    # demanding 20,000 flushes = 320,000 steps before the valve could be CONSIDERED; that gate is now
    # PLATEAU_WARM=1000 observations, which is two time constants of the 0.998 slow EMA and is
    # deliberately not a knob (it is a property of hardcoded EMA rates, not of a run).
    # ONE DEFECT STILL LIVE, TO PORT A FIX FOR RATHER THAN TO REDISCOVER: on a resume `_pin_prev = [0]`
    # (:5252) while `_dstep = step - _pin_prev[0]` (:7368), so the first flush computes dstep = N and a
    # population sitting at its cap on that flush banks N windows it never spent pinned -- 20,000 is
    # satisfied instantly and the first lift of the session is unearned (M38, ISSUES.md:417).

    stall_band = Lever(0.002, "Half-width of the band around zero improvement inside which the loss "
                              "counts as stalled and a lift is authorised.", U.FRACTION)
    # A BAND, AND THE NAME HAS TO SAY SO OR THE ONE-SIDED FORM GROWS BACK. `improving` is
    # (slow - fast)/|slow|, which is NEGATIVE when the loss is RISING, and the shipped gate was
    # `improving < GROW_CAP_PLATEAU` -- which passes for every negative value there is. The valve
    # therefore fired hardest exactly when the run was degrading worst, and said so in its own log line:
    # "the loss has stalled (improving -0.1937 < 0.002)" is a 19% degradation authorising capacity.
    # Three of the five expert lifts in the 0.75 GB run went to a run that was getting worse (C5,
    # ISSUES.md:1365). The test is now `abs(improving) < band` at :7411, and the old name
    # (GROW_CAP_PLATEAU) described the one-sided threshold accurately enough that keeping it would invite
    # the one-sided test back the next time somebody reads the name instead of the code.
    # A STALL IS FLAT: not improving, and not falling apart either. Capacity is the answer to the first
    # and never to the second -- a degrading run is what REGRESSION growth is for, and that path has its
    # own cooldown and blackout precisely so the two are not confused.
    # CARRY-FORWARD, AND IT IS NOT THIS PACKAGE'S TO FIX: `PlateauGrowth.step` still holds the unfixed
    # one-sided version of the identical test (M36, ISSUES.md:409, self_organize.py:3013) -- a rising
    # loss satisfies the stall condition and grows an expert. That is FAB's mechanism and FAB's row; it
    # must not be ported as it stands, and the fix is already written here.
