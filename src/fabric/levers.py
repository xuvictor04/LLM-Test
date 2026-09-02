"""FAB -- the expert population: who exists, who gets the token, who is born, who is removed.

WHAT THIS PACKAGE OWNS. One preallocated pool of low-rank experts, a router that picks a handful of
them per hop, and the two opposed forces that keep the pool honest over a long run: growth (spawn,
replicate, crossover, mutation) and selection (the utilization cull, the failure cull, and the spares
that stop either from eating something that was merely mid-adaptation). Both definitive goals of the
project run through here. Goal A because the fabric sits in the forward path and its mixture is what
the head decodes; goal B because "learn a new area without destroying the old one" is, in this design,
"grow capacity for the new material and do not cull the experts that hold the old".

WHY THESE ARE THE LEVERS, AND NOT SOME SMALLER SET. Every knob below is a place where the population's
behaviour is a POLICY rather than an arithmetic consequence -- a rate, a threshold, a budget, a clock,
or an arm of a designed comparison. The census argued each one individually against the old tree; what
this file adds is the part the old tree could not have: a single declaration, an owner-generated
environment name, one literal default, and a unit printed beside it. Nothing here reads the
environment (spine.lever.from_env is the only code that may) and nothing here reads another package's
value. Where the fabric genuinely needs a number somebody else owns -- the live domain count, the base
learning rate, the batch width, the memory-pressure reading -- that value arrives as a d_ wire
declared in spine/assemble.py, and `grep d_` finds every one of them.

-------------------------------------------------------------------------------------------------
WHAT WAS EMITTED, AND WHAT WAS NOT
-------------------------------------------------------------------------------------------------
The census (.rework/census.json) files 110 of its 328 rows under new_owner FAB. This file emits 82
levers:

    80  rows with verdict keep (51) or rename (29)
  +  2  rows with verdict merge whose merge TARGET has no row of its own (see UNRESOLVED MERGES)
  -------
    82  Lever declarations, all reachable as FAB_<FIELD>

Not emitted, by verdict: 20 drop, 9 merge (7 of which fold into a lever this file does declare), and
1 promote-to-wire. The promote-to-wire row is MAX_DOMAINS, which was never a lever -- it was
`MAX_DOMAINS = _i("MAX_DOMAINS", _i("FAB_NMAX", 4096))` at self_organize.py:598, the canonical
computed-default defect. It arrives in DOM as `d_expert_slots`, computed in spine/assemble.py from
this package's `slots`, and declaring it here would shadow the wire that writes it.

-------------------------------------------------------------------------------------------------
THE THREE CENSUS DEFECTS REPAIRED HERE
-------------------------------------------------------------------------------------------------
1. DOUBLED ENVIRONMENT NAMES -- 78 rows corrected, silently, because the correction is mechanical.
   The census records the target of a row as `FAB.FAB_N0`: prefix in one column, and the prefix
   REPEATED inside the name in the next. spine/lever.py generates the environment name as
   f"{PREFIX}_{FIELD.upper()}", so taking those rows literally would declare a field named `FAB_N0`
   answering to `FAB_FAB_N0` -- a name no operator has ever set, on a lever that would therefore run
   at its default forever while `unread_env()` reported the operator's real `FAB_N0` as a typo. Every
   such row is read as PREFIX + FIELD: the field is `n0`, the environment name is `FAB_N0`. The two
   rows that already named a bare field (`manage_every`, `grow_on_mem_pressure`) needed no change,
   which is also the evidence that the doubling is a clerical slip in the census rather than a
   decision -- the same document does it both ways.

2. CLOCK KINDS -- 1 row corrected, 1 conflict left standing and named rather than resolved.
   Ten emitted rows carry a clock unit. Eight were already right (Windows x 6, Selections x 2).
     * CORRECTED: FAB_BAL_WARM, filed by the census as Steps. It is consumed as
       `_bw = max(BAL_FLOOR, 1.0 - step / max(1, BAL_WARM))` at self_organize.py:7023, and `step`
       advances once per WINDOW (:6796, :7708). A threshold denominated in Steps and divided by a
       window counter is the project's single most repeated defect -- the same 16x class as the
       capacity valve's pin clock, which turned GROW_CAP_EVERY=20000 into a silent demand for 320,000
       steps at BATCH_W=16. The census row describes that defect in its own reason and then files the
       unit as Steps anyway; it is declared Windows here.
     * CONFLICT, NOT RESOLVED: `manage_every`. See its declaration -- the census says Windows,
       spine/assemble.py::_owner_blocks wraps the same field in `Steps(...)`, and both cannot be true.

3. UNRESOLVED MERGES -- 2 rows emitted that the census intended to fold away.
   A merge is only a merge if the surviving lever exists. Two FAB rows name a target that no row in
   the census declares, so following them would mean INVENTING a lever with a default nobody wrote
   down -- which is how a knob acquires a second default. Both are emitted under their own names and
   flagged at their declarations: `norm_only` (census: merge into a three-valued FAB_MODE that no row
   creates; the FABRIC row it names creates the two-valued FAB_ON instead) and `route_learn` (census:
   merge into a continuous FAB_ROUTE_IDENT_W that no row creates).

-------------------------------------------------------------------------------------------------
THREE DECLARATION CHOICES THAT ARE NOT THE CENSUS'S
-------------------------------------------------------------------------------------------------
FAB_NMAX IS DECLARED AS THE FIELD `slots`, so its environment name is FAB_SLOTS and not FAB_NMAX.
This is the one place where a census name is not carried over verbatim, and it is forced from the
other side: spine/assemble.py reads `r["FAB"].slots` in five couplings (DOM.d_expert_slots,
MEM.d_owner_blocks, MEM.d_capacity, MEM.d_source_slots, FAB.d_operating_population),
spine/derive.py's cull_gate_open and operating_population are both written against `slots`, and
tests/test_assemble.py's stand-in declares `slots = Lever(4096, ...)` under PREFIX="FAB". Declaring
`nmax` instead would make build() raise "FABLevers has no lever 'slots'" at startup -- loud, but the
package could not be assembled at all. The cost of the choice is real and belongs in the release
note: a run script that still sets FAB_NMAX now sets nothing. It is not silent -- registry.unread_env
names an undeclared FAB_-prefixed variable at startup -- but it is not a redirection either, and the
limit is worth stating rather than discovering: run against this file, unread_env('FAB_NMAX') offers
FAB_N0, FAB_MUT and FAB_RANK as its nearest matches, because edit distance does not know that
FAB_SLOTS is the successor. The operator is told the name is dead; they are not told what replaced
it. Reversing this decision means editing those five coupling rows rather than this line.
  (Aside, because it cost time to resolve: spine/lever.py's illustration writes `cfg.slots -> 2048`,
  which is FAB_N0's default, not this one's, and tests/test_ownership.py's synthetic set repeats it
  while tests/test_assemble.py's uses 4096. The arithmetic settles which is real -- occupancy
  2048/4096 = 0.50 in derive.cull_gate_open is n0 over the CAP -- so `slots` is 4096 here.)

ON/OFF LEVERS ARE DECLARED True/False, NOT 1/0. The value is identical (True == 1, and bool is an
int), but the declared TYPE is what selects a coercion branch in Lever.coerce: with a bool default,
FAB_GROW=off means off; with an int default it raises. Stated honestly, the bool branch has its own
hazard -- any unrecognised string that is not in ("0", "", "off", "no", "none", "false") reads as
True, so FAB_GROW=flase is silently on. That is the spine's rule for every bool in the tree, not a
choice made here; the int form trades it for a startup refusal on "off". The unit label U.FLAG and
the coercion now agree, which they would not if these were ints.

FIVE MULTIPLIERS DO NOT CARRY THE CENSUS'S "fraction 0..1" LABEL. FAB_Z (4.0), FAB_MUT_BIG (6.0),
FAB_SPAWN_MULT (2.0), FAB_LR_MAXR (4.0) and FAB_LR_BOOST (2.0) are multiples, and a label the
DEFAULT ITSELF falsifies is worse than no label -- docs/04_LEVERS.md is generated from these
declarations and would print "6.0 fraction 0..1". They carry U.COUNT plus the line under each saying
what they are a multiple OF. The rule applied is narrow on purpose: where the default satisfies the
census's label (every weight below at 0.0..1.0), the census's label is kept, because a weight that
COULD exceed 1 is a judgement call and this file is not the place to relitigate it. units.py has no
MULTIPLIER constant and adding one is a spine edit, not a fabric edit.
"""
# ABSOLUTE, NOT `from ..spine.lever import ...`. The tree is imported with `src` itself on
# sys.path -- tests/test_derive.py::<module> does it, and so does the verification command for this
# file -- which makes `fabric` a TOP-LEVEL package, and a relative import one level above a
# top-level package is an ImportError ("attempted relative import beyond top-level package"),
# not a fallback. The sibling package src/memory/levers.py imports the spine the same way, and
# two packages that spell one import two ways is the kind of difference that decides which of
# them a runner can load.
from spine.lever import Lever, LeverSet
from spine import units as U


class FABLevers(LeverSet):
    """The expert population's declared knobs: existence, routing, identity, growth, cull, own-LR.

    Grouped by the mechanism each one steers, because that is how they fail: the levers that break a
    run together are the ones that steer one mechanism, and a flat alphabetical list is what let the
    old tree file BAL_FLOOR under `optim` while its only reader was a fabric loss term.
    """

    PREFIX = "FAB"

    # ==============================================================================================
    # 1. DOES THE FABRIC EXIST, AND WHICH FORWARD PATH IS IT
    #
    # Three switches choose between four different forward passes (off / norm-only / society /
    # chaining), and in the old tree no single place said which one a run was on. The banner printed
    # "grounded region + learned bilinear" for a path with no region term (:30-32), and SUFFICIENCY
    # called fab.society() unconditionally while the shipped default was chaining -- which is how
    # "479 experts buy -0.002 b/B" came to be a measurement of a forward path the run never trained.
    # ==============================================================================================

    on = Lever(True, "Build the fabric and put it in the forward path; off removes it entirely.", U.FLAG)
    # Census: FABRIC -> FAB_ON. The most-read name in the old file (119 occurrences) and it reached
    # memory, eval and the report by direct global read -- MEM_PER_EXPERT was literally `... and
    # FABRIC` at :4866. Every one of those becomes a declared wire, which is the point: FABRIC=0 used
    # to crash the config banner on an unguarded _F0.div_mass because nothing enumerated the readers.

    # UNRESOLVED MERGE (census defect 3). The census merges FAB_NORM_ONLY into "FAB_MODE ... a third
    # choice -- on / off / norm-only", but no row anywhere in the census creates FAB_MODE: the row it
    # names (FABRIC) creates the two-valued FAB_ON above. Inventing FAB_MODE here would mean choosing
    # a default and a spelling for a three-way lever on no authority, and would silently delete
    # FAB_ON. So the arm is emitted under its own name and the merge is left for the port to make on
    # purpose. What the census is right about is the defect: there are two different ways to say "no
    # fabric" and they differ in ways nothing states -- off removes it from the forward pass, while
    # norm_only leaves the object built, its parameters in the optimizer and its state in the
    # checkpoint, and is then re-tested at six separate call sites as `not fab.norm_only`.
    norm_only = Lever(False, "Control arm: keep the fabric's normalization, remove nodes and routing "
                             "from the forward pass.", U.FLAG)

    society = Lever(False, "One hop with experts blended at the PREDICTION level, instead of "
                           "multi-hop chaining through Fabric.forward.", U.FLAG)
    # Census: SOCIETY -> FAB_SOCIETY. Needs a dated glossary entry: an archived decision file records
    # society-vs-chaining as SETTLED against the configuration that is now the default (ISSUES P2-C2).

    hop_mode = Lever("soc", "Which multi-hop path exists: 'soc' re-routes from scratch each hop with "
                            "the current state in the query, 'transition' walks the learned successor "
                            "matrix R with SRC marks.", U.NAME,
                     choices=("soc", "transition"))
    # choices= IS THE REPAIR, and this knob is one of the eleven ISSUES P1-M24 names (with SIG_MODE,
    # EVICT, CULL_MODE, LR_SCHED, KEY_SRC and the rest) where an unrecognised value silently ran a
    # path nobody asked for. The mechanism is one line: `s.loop_soc = (_env("CHAIN_ROUTE","soc") ==
    # "soc")` at :1843 -- so CHAIN_ROUTE=Soc, or a typo, is not "the default", it is the TRANSITION
    # walk, a different forward pass with different losses. (The census reason says the fallthrough
    # is to soc; the source says the opposite, and the source is quoted here.) With choices= the same
    # typo is a startup LeverError naming both legal values.
    # Q-FAB-1, RESOLVED 2026-09-02: THE LEVER STAYS AND ONE ARM IS PORTED. `soc` is built; the
    # transition walk (SRC_p as a live parameter, the R softmax and its top-k source trick -- the
    # full transition is 1.07 GB at N=4096, :2828-2830 -- `ctrl`, the per-hop query book `_hopq`,
    # and a second set of loss terms) is NOT. It was recommended for a drop and the drop was NOT
    # taken: the owner's standing rule is that a mechanism kept for future use is kept WITH A
    # SWITCH rather than deleted, and dropping this would retire census row CHAIN_ROUTE, making the
    # eventual port a census amendment instead of a body. What the drop was RIGHT about is that an
    # unread choice is intolerable, so FAB.build now READS this lever and REFUSES "transition" at
    # startup, naming the arm and the question. Declared-and-refused is loud; declared-and-ignored
    # is the M24 defect wearing the repair's own clothes.
    # WHAT WOULD RETIRE THE REFUSAL, so this is a measurement and not a verdict: port the arm and
    # compare it against soc on THIS tree's instruments -- H(hop1|hop0) over the hop choices (the
    # old tree read 0.533 bits on soc against 0.005-0.058 on every transition arm, over 202k
    # transitions, and that reading did NOT pass through the C3-voided leave-one-out counterfactual)
    # and expert coverage of the compute path (:2731-2734 records 25% under society against 8%
    # under chaining, "because mass CONCENTRATES as it flows"). Both are D1-suspect old-run numbers
    # and both point the same way, which is why the arm is deferred rather than built now -- not
    # why it is deleted. The cost of building it is the thing to weigh: TWO FORWARD PATHS INSIDE
    # ONE FUNCTION, which fabric/api.py's header exists to forbid ("the old tree had two, and
    # SUFFICIENCY called fab.society() unconditionally while the shipped default was the looped
    # path, which is how '479 experts buy -0.002 b/B' came to be a measurement of a forward path
    # the run never trained"), plus ~20 DID-IT-FIRE counters becoming arm-conditional.

    hop_vote = Lever(True, "Each hop's experts vote on the OUTPUT and the halting hop picks the "
                           "answer, instead of blending hidden states.", U.FLAG)
    # Carries the defect that produced the FAB_MIN_STEPS lie: at :1863-1868 this coerces min_steps to
    # 0 and SystemExits only on an EXPLICIT conflicting setting, so the banner printed
    # FAB_MIN_STEPS=2 for runs that used 0. Under the spine that coercion must be a declared
    # derivation, not a silent overwrite of a printed value.

    hop_sup = Lever(0.0, "Weight on per-hop deep supervision: a cross-entropy at every hop, not only "
                         "at the end of the walk.", U.FRACTION)
    # ARMED AND INERT, by wiring rather than by design (ISSUES P1-M27): it reads fab._hops, which only
    # the transition branch fills -- `s._hops.append` occurs at EXACTLY ONE site over 9,859 lines,
    # :2819, inside that branch -- so under the shipped hop_mode="soc" any value above zero adds
    # exactly nothing to the loss and nothing at the config layer says so. Kept because the
    # structural argument stands on its own (:2521-2524): one loss at the end of a depth-D walk,
    # diluted through every later LayerNorm, is the whole reason hop order is hard to learn.
    # AND IT IS NOT INERT IN THE REBUILD: FAB.forward now states that per-hop states are collected
    # ON THE SOC LOOP, which is where the M27 inertness actually came from. At hop_vote=True the
    # per-hop logits already exist for the vote (:2675-2680), so this costs nothing there.
    # fab.hopsup_applied reading 0 with hop_sup > 0 means that collection was not written.

    hops = Lever(4, "Maximum hop budget for one routed forward pass; effective depth is "
                    "min(depth0-stage, hops, 2 + n_live//2).", U.COUNT)
    # Census: FAB_STEPS -> FAB_HOPS, and the rename is the whole point of the row. "STEPS" here means
    # ROUTING HOPS and has nothing to do with optimizer Steps. A lever called FAB_STEPS sitting
    # beside FAB_WARMUP and FAB_COOLDOWN, which really are clocks, is an invitation to exactly the
    # mistake units.py exists to stop -- pin_tick counted flushes against a threshold declared in
    # steps and was 16x wrong at BATCH_W=16.

    depth0 = Lever(1, "Hop count the chain starts at before staged depth extends it; 0 means start "
                      "at the full `hops` budget (no curriculum).", U.COUNT)
    # ABSORBS TWO MERGED ROWS, and both merges remove a pair that could disagree:
    #   CHAIN_CURRIC (0/1) -- `s.depth_now = CHAIN_DEPTH0 if s.curric else max_steps` (:1801-1802)
    #     states one fact twice: the curriculum is on exactly when the start depth is below the
    #     budget. depth0=0 now says "no curriculum" and there is no second boolean to contradict it.
    #   FAB_MIN_STEPS -- whose declared default was `None (derived: 0 if SOCIETY else 2)`, a computed
    #     default that L1 forbids and that never once executed: Fabric.__init__ sets min_steps=0
    #     unconditionally under the default hop_vote, so the banner printed 2 for runs that used 0.
    # DO NOT DROP on the ground that staged depth "did not help": maybe_deepen had never been called
    # in a real run, because its cadence `step % MANAGE_EVERY == 0` could not coincide with a flush
    # step at BATCH_W=4 (:7321-7323). That is a cadence defect, not a verdict on the mechanism.

    depth_eps = Lever(0.01, "Improvement in the smoothed flush loss that still counts as progress, "
                            "so a depth stage does not advance while the loss is still falling.",
                      U.BITS_PER_BYTE)
    # THE UNIT LABEL IS THE CENSUS'S AND THE PORT MUST FIX THE COMPARISON, not the label: it is
    # compared against `_lf = float(loss.detach())` at :7317, a raw per-flush cross-entropy in nats
    # per token, not bits per byte. Filed as the wrong-measurement class (98 records). Declared with
    # the intended unit so that the mismatch is visible in docs/04_LEVERS.md rather than resolved by
    # quietly relabelling the knob to whatever the code happens to do.

    depth_patience = Lever(6, "Consecutive flat depth-checks required before one more hop is added.",
                           U.COUNT)
    depth_stage_max = Lever(40, "Depth-checks after which a stage ends regardless of the plateau "
                                "test.", U.COUNT)
    # Genuinely separate from depth_patience: patience is "how much flatness proves the plateau",
    # stage_max is "advance anyway". stage_max exists because the pure plateau test cannot fire on an
    # underfit model and left depth pinned at 1 for a whole run (:2526-2529). It is the fix for a
    # measured failure, not decoration.

    halt = Lever(True, "HALT as a real operator on both paths: its mass says 'no expert is needed "
                       "here' and the caller spends that mass on model.head directly.", U.FLAG)
    halt_max = Lever(0.9, "Ceiling on halt mass, so at least 1-halt_max of the blend and its "
                          "gradient always reaches the population.", U.FRACTION)
    # A BARRIER, NOT A PREFERENCE (:1735-1738). At halt=1 the experts receive no gradient at all, and
    # an expert that receives no gradient can never become worth routing to: an absorbing state. This
    # is the fabric's version of the trap that top-k exploration exists to avoid.

    alpha = Lever(0.5, "Residual mixing coefficient of one fabric step: h <- norm(h + alpha*(mixture "
                       "- h)).", U.FRACTION)

    ponder = Lever(0.01, "Charge on routed depth, so the chain does not take hops it does not need.",
                   U.FRACTION)
    ponder_warm = Lever(8000, "Anneal window for the depth charge, so the fabric is not billed for "
                              "depth before its experts can be worth using.", U.Windows)
    # CLOCK: Windows, and the census had this one right. `_pw = min(1.0, step / PONDER_WARM)` at
    # :7024 divides by `step`, which advances once per WINDOW (:6796, :7708) -- not by an optimizer
    # step counter. Charging for depth from step 0 is how the router writes the population off before
    # it can learn, which the report itself reports as node mass near zero (:9081).

    # ==============================================================================================
    # 2. HOW BIG THE POPULATION IS
    #
    # Two numbers and a setpoint, and the relationship between them is the project's worked example
    # of an IRREDUCIBLE coupling (PLAN section 4): the pool is preallocated at `slots`, the run starts
    # with `n0` of them alive, and the population equilibrates at `pressure x slots` because that is
    # where the cull gate opens. spine/assemble.py computes exactly that as
    # FAB.d_operating_population, so the number is written down once instead of being rediscovered.
    # ==============================================================================================

    n0 = Lever(2048, "Founding population: how many experts are BUILT at construction.", U.EXPERTS)
    # With the ramp dropped this is the only thing that sets initial population size, which is why
    # the ramp was dropped. Signals, not facts, and both pre-fix: the 2x2 at cc0a377 read GROW=0
    # N0=3 -> 2.117 b/B (spread 0.326), GROW=0 N0=2048 -> 1.999 (spread 0.080), GROW=1 NMAX=4096 ->
    # 3.384 (spread 2.074). The structure -- that the interaction is the whole effect -- is what
    # survives; the numbers do not. Also carries the repository's most expensive stale value: FAB_N0=3
    # is still asserted as current in an archived twin file and in nine notes (ISSUES P2-H1).

    slots = Lever(4096, "Preallocated slot count: cap = max(n0, slots); memory cost is 2*cap*d*rank "
                        "floats and it is the hard ceiling on every growth path.", U.SLOTS)
    # NAMED `slots`, NOT `nmax`, AND THE ENVIRONMENT NAME MOVES WITH IT (FAB_NMAX -> FAB_SLOTS).
    # The full argument is in the module docstring; the short form is that spine/assemble.py reads
    # `r["FAB"].slots` in five couplings and spine/derive.py's two capacity functions are written
    # against the same name, so `nmax` would fail build() at startup. A run script still setting
    # FAB_NMAX is caught by registry.unread_env(), which prints an undeclared FAB_-prefixed name
    # with its nearest declared match -- that is the only thing standing between this rename and a
    # silent default, and it is why the rename is written down here rather than in a commit message.
    # PREALLOCATION IS WHY THIS IS A HARDWARE NUMBER AND NOT A POPULATION TARGET (:1651-1654): growth
    # never reallocates and the optimizer never sees a new parameter. `pressure` chooses the
    # population; this chooses what the machine must hold.

    pressure = Lever(0.45, "Occupancy SETPOINT: below pressure x slots the utilization cull, the "
                           "utilization spare and `rescue` are all unreachable, so it chooses the "
                           "operating population size.", U.FRACTION)
    # THE UNTRIPPABLE-GUARD CLASS (60 records) IN ITS MOST EXPENSIVE FORM, and the reason the default
    # is 0.45 and not the 0.75 the merged EXPERT_PRESSURE row carried: n0=2048 against slots=4096
    # parks occupancy at exactly 0.50, permanently below 0.75, so the gate could never open. Measured
    # 0 culls and 0 spares at 0.75 against 204 and 1253 at 0.45, while the report showed all three
    # mechanisms switched on. Measured the other way too: gate_press predicted 0.45 x 4096 = 1843
    # live and the run ended at 1838 (:201-208). MERGED IN: EXPERT_PRESSURE (0.75), the identical
    # gate on the legacy router -- `(1 - len(free)/cap) >= pressure_on` at :3087 -- whose 0.75 is
    # deliberately NOT carried over, because carrying it would carry the untrippable guard.

    grow = Lever(True, "Master switch for population growth: off freezes the population at n0 while "
                       "routing, selection, replication and the cull all still run.", U.FLAG)
    # The one arm that isolates GROWTH from everything else the fabric does, which the L3 isolation
    # sweep needs. Two live defects belong WITH it rather than against it: spawn_from creates experts
    # independently of this switch, so a grow=off run still drifted 3 -> 6 experts (:7332-7335); and
    # growth_test.py is the only gate that does not stub _env, so an ambient FAB_GROW=0 in the shell
    # produces 5 failures and makes two "no false positives" checks pass vacuously (ISSUES P1-H41).

    # ==============================================================================================
    # 3. ROUTING: WHO GETS THE TOKEN
    #
    # The routing logit is a sum of two terms -- a signature-region cosine and a learned bilinear
    # identity term -- divided by a temperature, with a load-balance pressure and an exploration swap
    # on top. Every one of those five pieces has been measured to be doing nothing at some point in
    # this project's history, and in every case the cause was wiring rather than the mechanism.
    # ==============================================================================================

    route_region_w = Lever(1.0, "Weight on the signature-region cosine term in the routing logits; 0 "
                                "routes on predicted weights alone.", U.FRACTION)
    # For the equivalence report: this is one of only TWO knobs that six named grid arms actually
    # varied, so six "independent" GRID SUMMARY rows describe two experiments (ISSUES:66). Old
    # numbers attributed to it must be re-counted, not carried.

    # UNRESOLVED MERGE (census defect 3). The census merges ROUTE_LEARN into FAB_ROUTE_IDENT_W -- "a
    # weight, symmetric with FAB_ROUTE_REGION_W" -- and no row in the census creates that lever. The
    # argument for the merge is good (routing sums two terms, and expressing one as a boolean and the
    # other as a continuous weight states the same kind of fact in two shapes), but acting on it here
    # means inventing a name, a default and a unit for a lever no row authorises. Emitted as the
    # boolean it is today. What must be said either way, and belongs in docs/03_WIRING.md: turning it
    # off removes the only gradient into q_route and eemb from routing, so a zero here is not a small
    # change, it is the end of learned routing.
    route_learn = Lever(True, "Add the learned bilinear identity term to the routing logits.", U.FLAG)

    route_t = Lever(0.1, "Routing temperature on the region cosine, the normalized identity term and "
                         "the HALT logit.", U.FRACTION)
    # Load-bearing, not cosmetic: a cosine over thousands of experts is near-uniform, and 0.1 is what
    # makes the distribution selectable at all (:2350, :2441). It is meaningful as ONE temperature
    # only because FAB_KEY_NORM was dropped -- at its default 0 the learned term was an unbounded raw
    # dot while the HALT logit was always a normalized cosine, so the two operators it divides sat on
    # different scales and halting was decided by key magnitude (ISSUES P1-M29).

    cent_topk = Lever(8, "How many routed centroids EMA toward the served signature on each grounded "
                         "update.", U.EXPERTS)
    cent_ema = Lever(0.02, "Rate at which a node's centroid moves toward the signatures it actually "
                           "served.", U.FRACTION)
    # CENTROID LEARNING IS THE ROUTING FUNCTION now that ROUTE_GROUNDED's alternative router is
    # dropped: without this rate the centroids sit at their initialisation forever and the cosine
    # term scores against noise (:2400-2404). Performance defect to fix at port, not a lever
    # question: each of the k centroids is written back with .cpu() and a float() that forces a
    # device sync per expert, so 8 centroids x 4 hops is dozens of synchronisations per step for a
    # slow-moving EMA (ISSUES P1-M35).

    discover = Lever(0.35, "Cosine distance beyond which a signature counts as material NOTHING owns "
                           "and is handed to the least-used expert.", U.FRACTION)
    # MERGED IN: EXPERT_NEW_DIST (0.5), the same threshold on the legacy router, which MINTED a new
    # expert at `(1 - sims[j]) > new_dist` (:3051) where this one recruits the coldest existing node
    # (:2421-2424). One concept, two populations, only one of which runs; the 0.5 is not carried.
    # This is the cheap half of the answer to novel material -- the expensive half is `spawn`
    # decoding a new expert -- and it is the only path by which a cold expert acquires a region.

    chain_k = Lever(8, "How many experts are COMPUTED per hop (top-k by routing mass); per-hop cost "
                       "is k, not the population size.", U.EXPERTS)
    # The knob that makes a 4096-expert population affordable at all: it decouples population size
    # from per-step cost, which is the premise the whole preallocated-tensor design rests on.

    ens_k = Lever(2, "How many of the computed experts actually decode logits per hop or per window.",
                  U.EXPERTS)
    # Separate from chain_k on purpose: chain_k is what is computed, this is what is decoded.

    explore = Lever(0.15, "Fraction of rows whose lowest-ranked computed slot is swapped for a "
                          "randomly chosen low-use expert, on training passes only.", U.FRACTION)
    # THE ONLY THING BETWEEN THE UTILIZATION CULL AND A SELF-FULFILLING RANKING: an expert that is
    # never selected is never trained and is then culled for not being trained. Two properties the
    # port must hold it to: training-passes-only (a digest assertion, G7), and that the cold set is
    # actually sampled -- today `sorted(range(N), key=use)` is a stable sort over a mostly-tied key,
    # so exploration samples the LOWEST-INDEXED zero-use experts, a fixed prefix of the slot array
    # rather than the population (ISSUES P1-M25).

    ec_w = Lever(0.0, "Expert-choice deficit bonus: nudge routing toward experts under their share, "
                      "by construction rather than by a loss.", U.FRACTION)
    # Off by default and identical to the previous router at 0, kept because it is the structural
    # ALTERNATIVE to `balance` -- allocation by construction instead of allocation by loss pressure --
    # and `balance` is the one currently proven to be multiplying a zero. Dropping the alternative
    # while the incumbent is unmeasured would leave the balance question with no arm to test against.

    balance = Lever(0.01, "Load-balance pressure on the routing distribution, so every expert keeps "
                          "accruing use-age instead of a few absorbing all traffic.", U.FRACTION)
    bal_floor = Lever(0.15, "Permanent floor under the load-balance pressure, as a fraction of full, "
                            "so traffic never stops reaching the tail of the population.", U.FRACTION)
    bal_warm = Lever(4000, "How long the load-balance pressure takes to decay from full to its "
                           "floor.", U.Windows)
    # CLOCK CORRECTED, Steps -> Windows (census defect 2, the one row corrected). The consumer is
    # `_bw = max(BAL_FLOOR, 1.0 - step / max(1, BAL_WARM))` at :7023 and `step` advances per WINDOW
    # (:6796, :7708). The census reason describes precisely this mismatch -- "at BATCH_W=16 a
    # BAL_WARM of 4000 reaches the floor after 250 flushes, not 4000 update-equivalents" -- and then
    # files the unit as Steps, which would re-declare the defect it just named. If the port decides
    # the decay should instead be denominated in flushes, that is a conversion with a name
    # (derive.flush_period) and a Windows source, not a relabelled threshold.
    #
    # ALL THREE BALANCE LEVERS ARE INERT TODAY AND NOT ONE OF THEM IS A DEAD MECHANISM (ISSUES P1-C2):
    # under the shipped hop_mode="soc" the quantity they scale is a freshly allocated zero scalar with
    # no graph (soc-loop return at :2694, consumed at :7031), so the balance pressure has been exactly
    # 0.0 in every shipped configuration and there is no DID IT FIRE row for it. That is broken
    # wiring. The mechanism is the anti-forgetting half of the population: an expert the router stops
    # choosing gets no traffic, hence no gradient, hence no improvement, hence still no traffic -- and
    # under the use clock it is frozen at its use-age, so the cull cannot reach it either. bal_floor
    # and bal_warm were filed under `optim` in the old tree while their only reader is this loss term;
    # that misfiling is why an OPT change could move a FAB number with nothing to show for it.

    dom_frac = Lever(0.10, "Breadth cap: an expert serving more than this share of the live domain "
                           "population is masked out of routing for domains it does not hold.",
                     U.FRACTION)
    dom_min = Lever(4, "Absolute floor on the breadth cap, so a small domain population cannot ban an "
                       "expert from everything.", U.DOMAINS)
    # The live domain count is DOM's number and arrives as the wire d_live_domains; the fabric does
    # not reach into the assembler for it. dom_min is the floor that stops int(0.10 * small_n)
    # collapsing to zero and banning every expert from every domain it does not already hold -- the
    # same bootstrap deadlock that new_frac's max(1, ...) exists to avoid. Without the cap at all, a
    # handful of experts absorb everything, which is what the affiliation map showed (:1876-1878).

    div_w = Lever(0.02, "Weight on the distinctness penalty that rewards the experts a hop leans on "
                        "for producing different outputs.", U.FRACTION)
    # Differentiation is one of the two things the fabric is FOR. The society branch's copy of this
    # term indexed a rank slot with a global expert id and raised IndexError the first time anyone set
    # it above zero (:7038-7042) -- a crash nobody met, because of a default. That is precisely the
    # bug an isolation sweep finds by flipping the lever, and the reason a knob nobody sets is not
    # thereby safe. DIV_MASS is dropped rather than kept as an arm: unweighted, the reward is largest
    # exactly where it is meaningless (paying an expert for differing from an ensemble it has already
    # drifted out of), and keeping the arm keeps a known defect selectable while silently changing
    # what this weight means.

    ind_k = Lever(2, "How many of the society's experts are charged with solving the task alone.",
                  U.EXPERTS)
    ind_w = Lever(0.5, "Independence loss weight: each of those experts must solve the task ALONE, "
                       "weighted by its routing mass.", U.FRACTION)
    # ind_k silently widens how many experts the society computes, via `k=max(ENS_K, IND_K)` at
    # :6846 -- a coupling that was invisible under the bare name. ind_w is armed only under
    # `society`, and unusually for the old file that gate is stated honestly: the audit refuses to
    # call it armed on the chaining path rather than raise a permanent false alarm (:8690-8694). It
    # is the direct counterweight to div_w -- one rewards experts for differing, the other for being
    # individually sufficient -- and the pair is the question D7 asks about aggregate sufficiency.

    # ==============================================================================================
    # 4. IDENTITY SPACE: HOW AN EXPERT IS ADDRESSED, AND HOW ONE IS SPECIFIED INTO EXISTENCE
    #
    # Every expert's routing key is DERIVED from its own weights through a shared embedder, and the
    # inverse decoder is what makes spawn-by-specification possible: the router decodes its own query
    # into a newborn expert. FAB_DERIVE_IDS=0 (free identity parameters) is dropped, because what an
    # expert DOES and where it is ROUTED then drift independently -- an expert could learn something
    # new and keep the key that sent it the old material (:1693-1700) -- and because setting it to 0
    # silently voided six other levers, the coupling class (47 records) in its purest form.
    # ==============================================================================================

    dk = Lever(32, "Width of the routing identity space: the shared query projection's output and "
                   "every per-expert K and SRC vector.", U.COUNT)
    # What made per-source routing affordable: a dk-vector per expert restores per-source transitions
    # at O(N*dk) where the original per-expert matrix cost 345 ms at N=65536 (:1683-1690). ALSO A
    # CHECKPOINT-COMPATIBILITY VALUE: SRC_p and K_p are [cap, dk], so resuming with a different dk
    # invalidates every identity and every key. The run already refuses that (:4451-4456); in the
    # rebuild the refusal is CKPT's, reading this as a wire.

    rank = Lever(8, "Low-rank width r of every expert; also the number of crossover-able rank slices "
                    "and the size of the embedder's input (2*d*r).", U.COUNT)
    # The parameter that decides whether a population of thousands is affordable: 12.3k parameters
    # per expert at r=8 against 2.36M for the old full MLP (:1643-1650). Documentation drift to
    # correct, not a defect in the knob: a research brief still gives the expert rank as 4
    # (ISSUES P2-M22).

    emb_hid = Lever(128, "Hidden width of the shared identity embedder eemb and its inverse edec.",
                    U.COUNT)
    emb_var = Lever(1.0, "Weight on the variance + decorrelation term that stops every expert "
                         "embedding collapsing to one point.", U.FRACTION)
    # ON A MEASURED FAILURE: nearest-neighbour distance in identity space was measured at 0.000
    # without it (:1709, :1971-1972). A collapsed identity space makes spawn fire on every query --
    # nothing is ever far from anything -- and makes routing keys interchangeable, so this term is
    # load-bearing for spawn_mult's entire premise.

    emb_every = Lever(1, "Cadence at which every expert's identity is re-embedded from its weights.",
                      U.Windows)
    # CLOCK: Windows -- compared against `step`, which advances per window. The cost valve on an
    # O(N * 2*d*r * hid) pass, and its own history is the argument for typing cadences: at 50 it was
    # inert on the society path (that path never passed step=) and on the chaining path it made
    # routing keys stale AND throttled the one gradient channel that reaches every expert to 1-in-N
    # (:1716-1719). A cadence whose value silently means nothing on one of two paths is why cadences
    # became typed clocks.

    ae_w = Lever(0.5, "Weight on the weights -> identity -> weights round trip that keeps the "
                      "identity decoder edec honest.", U.FRACTION)
    # edec is what makes spawn-by-specification possible at all. Without this term the decoder is
    # never trained to invert the embedder, so a spawned expert is noise wearing the requested key.

    spawn = Lever(True, "Spawn-by-specification: decode the router's own query into a new expert when "
                        "nothing near it exists; also gates the identity autoencoder loss.", U.FLAG)
    # The structurally distinct growth path: discovery stops being "hand the odd material to whoever
    # is idle" and becomes "build what was specified", with the LM loss backpropagating through the
    # newborn's weights into q_route so the router learns to specify (:1701-1708). Two defects to fix
    # rather than reasons to drop: it ignores `grow` and the soft cap, so a frozen population still
    # drifts upward (:7332-7335); and the mid-chain variant reads _hopq, which only the transition
    # branch fills, so it can never fire under the default hop_mode (ISSUES P1-M26).

    spawn_mult = Lever(2.0, "How many times the population's own median nearest-neighbour distance a "
                            "query must exceed to count as material nothing serves.", U.COUNT)
    # UNIT: a multiple of a measured distance, not a fraction -- see the module docstring on the five
    # multipliers the census filed as "fraction 0..1". Measuring novelty against the population's own
    # spacing rather than an absolute cutoff is what lets one threshold hold as the population grows
    # and its identity space fills in: the same scale-free discipline as `mut` and `z`.

    spawn_floor = Lever(0.02, "Absolute distance floor under the spawn test, so a degenerate "
                              "population cannot spawn on every query.", U.FRACTION)
    # The guard that keeps a relative test safe, on the measured collapse above: when the median
    # nearest-neighbour distance is 0.000, every query is infinitely far in relative terms and spawn
    # fires unboundedly (:1712-1713).

    # ==============================================================================================
    # 5. GROWTH: WHEN THE POPULATION GETS BIGGER, AND WHAT A NEW EXPERT IS MADE OF
    #
    # THE RAMP IS GONE and this section is what replaces it. Four ramp knobs were dropped together
    # because the ramp did not merely dominate the on-demand triggers, it STARVED them: every ramp
    # firing set the shared cooldown timestamp, so the regression and stall paths could never open.
    # Measured on PlateauGrowth directly over 20k steps with a sustained regression injected at 12k --
    # ramp_to=1.0 gave ramp 107 / REGRESSION 0 / stall 0; ramp_to=0.5 gave ramp 0 / REGRESSION 0 /
    # stall 7 (:2909-2919). That is the "grew 417x on the RAMP, 0x on a REGRESSION, 0x on a stall"
    # line. RISK ACCEPTED AND STATED: nothing in the rebuild grows the population on a schedule, only
    # on evidence, so if the evidence triggers are themselves broken the population will not grow at
    # all -- which is a visible failure, where the ramp's was not.
    # ==============================================================================================

    burst = Lever(1, "How many experts a REGRESSION grows at once.", U.EXPERTS)
    # One node cannot answer a distribution shift that needs several, and the size of that reply is
    # the thing under test on the add-area benchmark -- this is the continual-learning reply to new
    # material arriving. Reporting defect to carry a fix for: both clamps (soft cap and new_frac) run
    # at the call site AFTER n_regr was incremented inside step(), so a burst that delivered nothing
    # still prints as a regression that fired (:7464-7470).

    z = Lever(4.0, "How many robust deviations (running MAD) above the slow EMA a loss must sit to "
                   "count as an unexpected REGRESSION.", U.COUNT)
    # UNIT: a multiple of a deviation, not a fraction (module docstring, the five multipliers). This
    # is the trigger that detects new material arriving, which is the only signal continual learning
    # has (:2925-2929); the running-MAD form is what makes it scale-free rather than a threshold
    # fitted to one loss level. Its measured problem was the shared cooldown, not the z value.

    plateau = Lever(0.002, "Relative improvement of the slow EMA below which progress counts as "
                           "stalled: arms the stall growth and releases RECOVER.", U.FRACTION)
    # Read at two points of one state machine (arming a stall, leaving RECOVER), which is a single
    # lever with two uses rather than a hidden coupling. Distinct from depth_eps in both quantity and
    # clock: that one is an ABSOLUTE loss delta per depth check, this is a RELATIVE improvement of
    # the slow EMA per growth check.

    warmup = Lever(300, "How long before the stall trigger may fire at all, so early noise is not "
                        "read as a plateau.", U.Windows)
    # CLOCK: Windows -- compared against `step` (:6796, :7708). PlateauGrowth's own class-signature
    # default of 2000 against the shipped 300 is a 6.7x mismatch that every timing claim in
    # growth_test.py inherits (ISSUES:222): the test constructs the class directly and gets a
    # different warmup than any run.

    cooldown = Lever(400, "Minimum spacing between growth firings, and the window over which recent "
                          "births are counted for the new_frac budget.", U.Windows)
    # CLOCK: Windows, corrected in the census and worth restating -- it is compared against `step`,
    # and PlateauGrowth's class default of 1500 is a further 3.75x mismatch that growth_test.py is
    # written against (ISSUES:218). MERGED IN: FAB_NEW_WIN, whose default was not a value at all but
    # a hidden read of this lever -- `_i("FAB_NEW_WIN", 0) or _i("FAB_COOLDOWN", 400)` at :734, which
    # L1 forbids outright. The two windows ask one question ("over how long does growth act"), and
    # keeping them apart produced the recorded cadence inversion: the growth window (400) is SHORTER
    # than the cull cadence manage_every (500), where the design assumed 8x longer (:725-728).
    # BEHAVIOURAL DEFECT TO FIX AT PORT: REGRESSION and stall share s.last, so a routine stall 772
    # windows earlier suppressed a genuine injected regression (:2921-2926) -- the common event
    # silencing the rare one that continual learning depends on.

    recover_min = Lever(600, "Minimum RECOVER lockout after a growth burst, so the burst's own "
                             "transient worsening cannot re-trigger growth.", U.Windows)
    recover_max = Lever(20000, "Hard ceiling on the RECOVER lockout, so growth re-arms even if "
                               "improvement never flattens.", U.Windows)
    # CLOCK: Windows for both. recover_max is the escape hatch that stops RECOVER becoming absorbing,
    # which matters most in exactly the regime continual learning cares about: a model still
    # improving when new material arrives.

    new_frac = Lever(0.04, "The most of the population that may be newborn at once; growth takes "
                           "whatever is left of the budget rather than being refused outright.",
                     U.FRACTION)
    # The brake that keeps selection able to outpace growth, which is the premise of a selective
    # population. Two things belong in its port comment: max(1, ...) exists because int(0.10 * 3) is
    # 0 and a small founding population could otherwise never grow at all (measured: reached 7
    # instead of 256, :7455-7458); and it is applied AFTER the trigger has counted its firing, so
    # declined bursts still print as regressions that fired.

    replicate = Lever(True, "Grow by cloning a fit parent plus mutation, instead of minting a fresh "
                            "random expert.", U.FLAG)
    # A real arm on goal B: inheritance is the claim that a new expert starts from something already
    # learned rather than from noise, and random birth is the only counterfactual that tests it.

    parent_k = Lever(8, "Shortlist size: how many region-owners compete to be the parent of a new "
                        "expert.", U.EXPERTS)
    # Sampling a parent from a region-relevant shortlist is what makes a birth land near the material
    # that triggered it: at k=1 growth is greedy cloning of the incumbent, at k=population it is
    # unfocused.

    parent_max = Lever(0.20, "Maximum share of recent births any one parent may account for.",
                       U.FRACTION)
    birth_win = Lever(256, "Size of the sliding per-parent birth record that parent_max is measured "
                           "against.", U.COUNT)
    # Without a per-parent quota the fittest expert clones itself into the whole growth budget, which
    # converts population growth into population duplication and makes an expert count meaningless as
    # a capacity measure. Without a bounded window the quota is measured over the whole run, so one
    # early prolific parent is banned from breeding forever while a late one is unconstrained: the
    # quota only means "recent" if the record is a window.

    mut = Lever(0.25, "Mutation size at birth, as a fraction of the parent's own weight std.",
                U.FRACTION)
    mut_big = Lever(6.0, "Size of the heavy-tail mutation, as a multiple of the ordinary mutation "
                         "scale.", U.COUNT)
    mut_big_p = Lever(0.1, "Probability that a birth takes the heavy-tail mutation instead of the "
                           "ordinary one.", U.PROBABILITY)
    # mut is relative to the parent's std rather than absolute, so it means the same thing for a
    # well-trained parent and a fresh one -- the scale-free principle `z` and `spawn_mult` also use.
    # mut_big is a MULTIPLE (module docstring, the five multipliers), not a fraction; it is also the
    # operator `rescue` applies at the moment of a cull, so weakening it would silently weaken rescue.
    # Rate and magnitude are separate levers because they trade off against each other, and one knob
    # carrying both would make "more exploration" ambiguous.

    xover = Lever(0.35, "Fraction of births assembled from several parents by taking whole rank "
                        "slices from a second parent.", U.FRACTION)
    # The only birth operator that RECOMBINES rather than perturbs. Rank slices are a meaningful unit
    # to exchange precisely because each is an independent low-rank direction, which is why this is
    # coupled to `rank` by construction rather than by accident.

    birth_jitter = Lever(0.15, "Perturbation added to a newborn's centroid so a growth burst does not "
                               "mint exact clones.", U.FRACTION)
    # Its own source comment states the defect it fixes: a burst grows several experts at ONE
    # signature, so without jitter they are born with identical regions and can never differentiate.

    grow_on_mem_pressure = Lever(False, "Let the memory-pressure signal make fabric growth eligible, "
                                        "instead of only being printed.", U.FLAG)
    # WRONG OWNER IN THE OLD TREE, NOT A WRONG KNOB. It was tagged into the memory block, but its
    # entire effect is a call INTO the fabric -- fabgrow.note_shift(step) at :6569-6571 -- and under
    # L2 the memory package may neither read it nor make that call: memory publishes a pressure
    # Reading, the fabric decides what to do with it, and THE READING ARRIVES AS AN ARGUMENT, NOT AS
    # A WIRE. (Corrected 2026-09-02. This comment said "as a wire"; it is FAB.grow_check's
    # `memory_pressure`, supplied per flush from MEM.census, and a store occupancy measured at
    # runtime can never be a wire because a Coupling.compute sees only frozen Configs. The wrong word
    # matters here: `grep -rn d_ src/` is meant to be a complete coupling index and a comment
    # promising a coupling that must never exist is a trap for whoever tries to declare it.) Kept
    # rather than dropped because D3 explicitly retains pressure-drives-growth as a selectable arm,
    # and because it has never fired only because its input signal is pinned near zero -- the
    # broken-instrument case, which does not convict a mechanism. Its own comment gives the honest
    # reason it ships off: "wiring this to growth is a behaviour change nobody has measured, and the
    # last unmeasured default in this file cost a run."
    # AND DO NOT PORT THE OLD CALL, WHICH IS INVERTED -- found while ruling Q-FAB-6, 2026-09-02, and
    # recorded here because this lever's own citation is the thing that would invite it back.
    # :6570 is `fabgrow.note_shift(step)` under the comment "same entry point a regression uses:
    # makes growth eligible now", and it does the OPPOSITE. note_shift sets `blackout = t` (:2948),
    # and every reader of `blackout` SUPPRESSES rather than enables: :3004 (`if unexpected and
    # t - s.blackout >= s.cool`) and :3012 (`if t - s.last < s.cool or t - s.blackout < s.cool:
    # return 0`) inside PlateauGrowth.step, and -- the one this comment called "only two" until
    # 2026-09-03 -- :7397 at the LOOP CALL SITE, `_blackout = (step - fabgrow.blackout) <
    # fabgrow.cool`, which gates the capacity valve and arrives in this rebuild as CAP.observe's
    # `blackout` boolean. Three readers, one direction. So MEM_PRESSURE_ACT=1 printed "growth made eligible at step N"
    # while BLOCKING growth for the next 400 windows. In the rebuild the signal arrives as
    # grow_check's own `memory_pressure` argument and this lever gates on it there, which is why the
    # defect does not carry -- but a P4 author following the :6569-6571 citation would rebuild it.

    # ==============================================================================================
    # 6. SELECTION: WHO IS REMOVED, AND WHO IS SPARED
    #
    # Two cull paths and three spares. The utilization cull removes the bottom `cull_frac` of the
    # past-grace population, but only under capacity pressure; the failure cull removes an expert
    # whose error EMAs both sit above the population by `fail_tol`, at any occupancy. Against them:
    # the grace clock (too new to judge), the shift test (adapting, not failing) and comp_protect
    # (rare but good at its own material). Goal B lives in the spares -- the arrival of a new area
    # makes every relevant expert look temporarily worse, and a cull that cannot tell those apart
    # deletes exactly the experts that hold what came before.
    # ==============================================================================================

    manage_every = Lever(500, "Cadence of the management pass: the fabric cull, spares, replication "
                              "and the staged-depth check.", U.Windows)
    # CLOCK CONFLICT, NAMED RATHER THAN RESOLVED (census defect 2). Two files disagree about this
    # field's kind and both are already written:
    #   * THIS CENSUS ROW says Windows, and gives the mechanism: it is compared against `step`
    #     (:6716, :6764, :6836, :6961, :6988, :7077, :7321) and `step` advances once per WINDOW.
    #   * spine/assemble.py::_owner_blocks computes FAB.d_manage_period as
    #     derive.flush_period(Steps(r["FAB"].manage_every), r["TRAIN"].batch_w), and
    #     derive.flush_period REFUSES anything that is not exactly Steps (derive.py::flush_period). Its stated
    #     reason -- "MANAGE_EVERY is written in STEPS" -- is the opposite claim about the same field.
    # Declared Windows here, because the reading that can be checked against the source wins over the
    # one that cannot: the divisor is `step`, and units.py is explicit that `step` counts windows.
    # THE CONFLICT IS NOT FIXED BY THIS LINE. If Windows is right, then assemble.py is converting from
    # the wrong kind and flush_period needs a Windows arm; if Steps is right, this label is wrong.
    # Nothing here changes assemble.py, because a lever file quietly editing the wiring file to agree
    # with itself is how one number acquires two answers. Worth adding: the old tree ALSO used this
    # same field as `_nbwd % max(1, MANAGE_EVERY // BATCH_W)` at five sites -- one number compared
    # against two clock kinds, which is the defect class the Clock types exist for.

    cull_frac = Lever(0.02, "Fraction of the ELIGIBLE (past-grace) set removed per manage pass, "
                            "floored at one.", U.FRACTION)
    # MERGED IN: EXPERT_CULL_RANK (0.08), the identical rank-relative pressure-gated cull on the
    # legacy router (:3089). The 0.08 is not carried: 0.02 was set against the fabric's own use-age
    # grace and its measured occupancy. Read twice on purpose -- at :2263 for the cull and at :7280
    # to size the lr_boost group -- so the cull and the boost agree on who is in trouble. DEFECT TO
    # CARRY A FIX FOR: bump_use increments use and uage together, so eligibility (uage >= grace) and
    # the ranking key (use) are the same number, and the cull removes the expert that just crossed
    # the grace line rather than the least-used one (ISSUES:110).

    grace = Lever(48, "How many times an expert must have been SELECTED before the cull may touch "
                      "it.", U.Selections)
    # CLOCK: Selections, which is the distinction that kind exists for, and the merge that produced
    # this default is the argument. MERGED IN: EXPERT_GRACE (3000), which counted `step - born`, i.e.
    # windows. At 2048 experts an expert is selected a handful of times in a WHOLE RUN, so a
    # 3000-window grace made the founding population permanently immune to culling (:1877, :2216).
    # A wall-clock grace punishes late births and protects idle founders; a use-clock grace makes
    # "has had its chances" mean one thing in both the cull and lr_boost. Cross-kind comparison is
    # now a UnitError instead of a silent immunity.
    # THE LEVEL IS WRONG AT THE SHIPPED RUN LENGTH AND IS DELIBERATELY NOT GUESSED (Q-FAB-5,
    # RESOLVED 2026-09-02). FAB.observe credits uage by SELECTION over the computed experts, so at
    # n0=2048 with chain_k=8 credits per window at depth0=1, mean uage after a full default run is
    # 506*8/2048 = 1.98. Reaching 48 needs 12,288 windows at depth 1, or 3,072 at full depth 4,
    # against a default run of 506-937 windows. THE PAST-GRACE SET IS THEREFORE PROVABLY EMPTY AT
    # THE SHIPPED DEFAULTS, which makes the utilization cull, `rescue` (which lives inside it),
    # lr_boost's budget (sized on the eligible count) and the new merge all UNREACHABLE -- even
    # though derive.cull_gate_open(2048, 4096, 0.45) returns True. The gate is open onto an empty
    # set, and that is a different report line from "the gate never opened".
    # THIS FAMILY IS OUTSIDE THE C11 AUDIT'S REACH BY TYPE. derive.cadences_that_cannot_fire
    # refuses anything that is not units.Windows and this is units.Selections, so a Selections
    # threshold that cannot be crossed in a run's length can never appear in that audit. Whoever
    # answers C11 must be told there is a SECOND unreachable-threshold family here.
    # THE RETUNE IS A P9 MEASUREMENT AND ITS INPUT IS NAMED: fab.mass_per_selection
    # (sum(use)/sum(uage)) is the evidential dilution factor -- how many argmax-equivalents one
    # post-split uage tick is worth -- and it is the only defensible basis for re-scaling 48. It
    # depends on the router, so it cannot be computed at build time, which is exactly why this
    # stays a literal. Changing an instrument's DEFINITION (the use/uage split) and its
    # CONFIGURATION (this level) in one step is how this project produced numbers nobody could
    # attribute; the split is the definition change, so the level does not move in the same commit.

    comp_ema = Lever(0.02, "EMA rate for the per-node competence and marginal-contribution signals "
                           "that gate cull-sparing.", U.FRACTION)
    comp_protect = Lever(True, "Spare a unit from the cull when it models its own material better "
                               "than the population does, however rarely it is selected.", U.FLAG)
    # BOTH HAD TWO READERS IN THE OLD TREE -- the fabric and the domain assembler -- which L2 forbids.
    # The fabric is the load-bearing reader (contrib is the counterfactual that picks replication
    # parents and spares culls), so FAB owns them and the domains receive d_comp_ema / d_comp_protect
    # as wires. comp_protect is load-bearing for goal B in one sentence from the source: "rare and
    # stale is exactly what a niche domain looks like from a utilization-only vantage point, and it
    # is also what a dead one looks like."

    err_fast = Lever(0.05, "EMA rate of the per-expert FAST error signal.", U.FRACTION)
    err_slow = Lever(0.005, "EMA rate of the per-expert SLOW error signal, the baseline the fast one "
                            "is judged against.", U.FRACTION)
    # THE 10x SEPARATION IS THE MECHANISM (:1757-1761, :2186-2194): an expert whose fast error sits
    # above its slow error is mid-adaptation and must be protected, not culled. One EMA cannot express
    # that distinction, and collapsing the pair into one rate plus a ratio would hide which of the two
    # a change moved.

    shift_tol = Lever(0.05, "How far the fast error may sit above the slow error before the expert "
                            "counts as ADAPTING and is spared.", U.FRACTION)
    fail_tol = Lever(0.15, "How far BOTH error EMAs must sit above the population before an expert "
                           "counts as in sustained failure and is cullable at any occupancy.",
                     U.FRACTION)
    # fail_tol is the only cull path that does not require capacity pressure, so it is the one that
    # still runs on a small or shrinking population -- the regime the pressure gate cannot reach.
    # shift_tol is a direct hit on goal B if it is wrong in either direction, because new material
    # makes every relevant expert look temporarily worse.

    rescue = Lever(0.0, "Give an expert about to be culled one heavy mutation and a reset use-clock "
                        "instead of deleting it.", U.FRACTION)
    # THE CLEAREST DO-NOT-DROP CASE IN THE FAMILY. It fired zero times for a whole investigation and
    # both reasons are defects elsewhere: it lives inside the capacity-pressure branch, unreachable at
    # the old pressure=0.75 with occupancy pinned at 0.50; and its DID IT FIRE row arms on `cull_ran`,
    # which is reassigned on every manage() call and so holds only the LAST pass's answer while
    # n_rescued is cumulative (ISSUES:493). It is also the discrete counterpart of lr_boost -- same
    # intent, weight space at the moment of the cull instead of continuously -- so dropping it would
    # leave that pair half-implemented.

    merge_dist = Lever(0.10, "Cosine distance under which two redundant experts are MERGED by "
                             "averaging their adapters, instead of one being culled.", U.FRACTION)
    # CARRIED OVER ON A CONDITION, AND THE CONDITION IS NOW MET (Q-FAB-2, RESOLVED 2026-09-02).
    # This is the only merge-rather-than-kill mechanism in either expert population -- the legacy
    # router averaged the two adapters and summed their use, so "both experts' learning survives"
    # where culling destroys it (:3063-3085) -- which is why goal B keeps it even though its old
    # home is dropped. The condition the old comment set ("IF THE FABRIC DOES NOT GAIN THE MERGE AT
    # PORT, this must return to the census as a drop") is discharged: FAB.manage gains a step 0.
    #
    # ==> DEFAULT NOTICE, BECAUSE THE OWNER ASKED TO BE TOLD WHAT IS ON AND OFF <==
    # THIS DEFAULT IS 0.10 AND IT IS NOT ZERO. Until 2026-09-02 the mechanism did not exist, so the
    # value was inert; implementing the merge turns it ON for every default run. The default is NOT
    # moved to 0 here -- that would be deciding by argument a question the census already answered,
    # and it would leave goal B without its only consolidation path -- but the state change is
    # loud, in the commit, in docs/04_CONTRACT.md section 4, and here.
    # WHAT IS ACTUALLY REACHABLE AT THE SHIPPED DEFAULTS IS ANOTHER MATTER AND IS NOT THE SAME
    # STATEMENT: the absorbed expert must be past `grace`, and by Q-FAB-5's arithmetic the
    # past-grace set is provably empty at 506-937 windows (mean uage 1.98 against grace=48). So a
    # default run reports fab.merged as `unreachable` WITH THAT ARITHMETIC, not "armed but 0" and
    # not "fired". Three states, and the ledger must be able to say which.
    #
    # THE ARITHMETIC IS CORRECTED AND THE CORRECTION IS THE RULING. The legacy line averages the
    # FACTORS, and dW = A@B is bilinear: 0.5*(A1+A2) @ 0.5*(B1+B2) = 0.25*(A1B1+A1B2+A2B1+A2B2),
    # which HALVES the intended contribution and injects two cross terms nobody trained. A and B
    # are zero-init at birth with no shared basis, so the factors are not aligned by construction
    # either. FAB.manage's step 0 merges in dW space at fixed rank instead and reports the
    # truncation residual, which is what makes the census's claim falsifiable in-run for the first
    # time. The merging literature says the same thing from the other end: MC-SMoE aligns expert
    # weights by permutation BEFORE averaging, precisely because unaligned factor averaging
    # destroys both experts, and the exact-mean LoRA construction needs concatenation at rank 2r,
    # which a preallocated fixed rank refuses.
    # NOTHING IN MEM MOVES. The escalation asked for a MEM entry point "reassign the entries owned
    # by expert i to expert j"; it is refused on three reads -- MEM.read is global across owner
    # blocks, an entry's owner is its row index and 64 experts share every block at the shipped
    # defaults so that set is not nameable, and a cull already has the identical (larger) MEM
    # consequence and ships.
    # ONE INTERNAL TENSION WORTH THE OPERATOR'S ATTENTION: this gate is cosine distance in IDENTITY
    # space, while div_w (above) PAYS two co-routed experts for producing different outputs. div_w
    # manufactures exactly the pairs merge_dist would consume. The residual is the reading that
    # says which of the two is winning, and lowering merge_dist is the operator's answer if it is
    # this one.

    # ==============================================================================================
    # 7. PER-EXPERT LEARNING RATE
    #
    # Each expert on its own cyclical schedule, clocked by its OWN use count, so the population is
    # never all exploring at once. Off by default and NOT dropped: the x64 ladder over lr_cycle read
    # flat and the own-schedule comparison read 2.023 vs 2.019 b/B over three paired seeds -- 0.0040
    # against a same-configuration spread of up to 0.039, thirty times below the floor for running
    # the same thing twice. Both measurements were taken with the schedule OFF or on a population
    # that never finished growing (the ramp was still adding experts 20 steps before the run ended),
    # and the source asks for a re-test on a fixed population (:6292-6301). Dropping the ramp is what
    # makes that re-test possible.
    # ==============================================================================================

    lr_own = Lever(False, "Put each expert on its own cyclical learning-rate schedule, clocked from "
                          "its own use count.", U.FLAG)
    # The saving from leaving it off is real and belongs in the docs: the rescaling path clones every
    # live row of A and B on each optimizer step, about 50 MB at 2048 experts. UNFIXED CRASH ON THE
    # ON PATH (ISSUES P1-H15): _lrv is undefined when LR_SCHED=none and lr_own is on -- a NameError on
    # the first flush. The global rate is OPT's number and must arrive as the wire d_base_lr.

    lr_cycle = Lever(24.0, "Half-cycle of the per-expert triangular2 schedule, measured on the "
                           "expert's own use clock.", U.Selections)
    # CLOCK: Selections, and the clock IS the mechanism -- an expert the router calls often cycles
    # fast and one it calls rarely cycles slowly, so the population is never in phase.

    lr_gamma = Lever(0.5, "Per-cycle envelope decay: 0.5 is triangular2 exactly, 1.0 degenerates to "
                          "plain triangular.", U.FRACTION)
    lr_amin = Lever(0.15, "Floor under the decaying envelope, so a long-lived expert keeps a small "
                          "permanent capacity to move.", U.FRACTION)
    # Without a floor the envelope reaches zero and the only adaptation left in the population is
    # birth and death (:7241) -- which is the opposite of what a continual learner wants from its
    # oldest, most specialised experts. The report already knows how to say when the floor is doing
    # all the work: it warns when experts have run past about 12 cycles and are pinned at amin
    # (:7305-7315).

    lr_maxr = Lever(4.0, "Ceiling on the ratio of an expert's own rate to the global rate.", U.COUNT)
    lr_boost = Lever(2.0, "Multiply the own-rate for the cull-eligible bottom of the utilization "
                          "ranking: exploration before removal.", U.COUNT)
    # UNIT: both are MULTIPLES of the global rate, not fractions (module docstring). lr_maxr is the
    # safety clamp on a schedule that can otherwise multiply the global rate without bound. lr_boost
    # reads grace and cull_frac deliberately, so the boost and the cull agree on who is in trouble
    # (:7264-7280); it is the continuous counterpart of `rescue`. SIZING BUG TO CARRY A FIX FOR: the
    # budget was sized off n_live while the list was already filtered to past-grace experts, so at
    # 523 live / 84 eligible "the worst 2%" meant "all of them" (:7273-7281).
