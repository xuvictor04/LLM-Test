"""DOM -- the self-assembling partition: where the stream is cut, what the pieces are called, and which
of those names are allowed to survive.

WHAT THIS PACKAGE OWNS. One online clustering of the stream into named regions. It does four things and
each group of levers below is one of them: DETECT a distribution shift between adjacent windows, ASSIGN
the material after that shift to an existing domain or to a new one, CONSOLIDATE the population (merge
near-duplicates, fold domains that never came back, cull dead ones), and PAY FOR ITSELF (a per-domain
token histogram blended into the prediction). The one number it exports is `did`, a domain id, and `did`
is consumed by exactly three readers: memory provenance (mem.src), the expert-to-domain affiliation map,
and the clustering report.

WHY THESE ARE THE LEVERS, AND WHY THIS PACKAGE EXISTS AT ALL UNDER TWO GOALS AND NOT THREE. A partition
is not itself a goal. It earns its place through goal B: continual learning without catastrophic
forgetting needs a UNIT OF FORGETTING that is smaller than the whole store, and `did` is that unit --
the domain count sets the granularity of deletion (at 25 live domains a delete removes 1.6% of memory; at
4 it removes 30%), and MEM's per-source floor can only protect a source that is separately named. That is
also why the sharpest lever in this file is `cull_stale`: under a phased schedule the absent corpus's
domains go stale BY CONSTRUCTION, and the old cull deleted them with their memory -- 200,000 entries
ending under a single source id (self_organize.py:3676-3688). That is catastrophic forgetting performed
by the manager rather than suffered by the model, and it is this package's to prevent. The contribution
to goal A is one lever, `prior_blend`, and it is the only route by which a domain pays in PREDICTION
rather than in editability -- measured, not assumed, and currently measured against a broken instrument
(see its declaration).

WHAT THE POPULATION MUST BE, WHICH IS THE TEST BEHIND HALF OF THESE DEFAULTS. A domain population that
GROWS with stream length is a log of the splices, not a partition of the material. On the controlled
synthetic test (4 recurring processes, known truth, 3 seeds) the three configurations read:

    config                          live (truth 4)    V      live @ 120 / 240 / 480 segments
    constant thresholds only             64.0        0.82      64 -> 116 -> 193    GROWS
    + measured radius x1.2               18.0        0.95      18 ->  20 ->  25    nearly flat
    + recurrence fold                     4.0        1.00       4 ->   4 ->   4    exact

The last column is the whole point and it is the first thing in this project's history that passed it.
`accept_rule=radius` and `fold=True` are those two rows, and they are the reason the defaults below are
not the ones the project shipped first.

--------------------------------------------------------------------------------------------------
WHAT WAS EMITTED, AND WHAT WAS NOT
--------------------------------------------------------------------------------------------------
The census (.rework/census.json, filtered on new_owner == "DOM") files 33 of its 328 rows here. All 33
sit in the `domains` family; no other family sends a row to this package. This file emits 28 levers:

     20  rows with verdict rename
   +  8  rows with verdict keep
   -------
     28  Lever declarations, all reachable as DOM_<FIELD>

Not emitted, by verdict: 3 drop and 2 merge.
  DROPPED (not declared, and each for a structural reason rather than a null measurement):
    DOM_ADAPTIVE (0)  -- the censored-median spawn threshold. Its estimator is fed by s._dh, appended
                         ONLY inside `if d < thr` (:3551-3554), so the sample is censored at the very
                         threshold it exists to move. 0 of 143 domains ever learned a radius from the
                         equivalent censored pool. The uncensored replacement is `reservoir`, below.
    DOM_SPAWN_K (3.0) -- the MAD multiplier of that estimator. One read site, inside the dropped branch.
    DOM_CULL_EMPTY(1) -- the knob goes, the behaviour stays unconditional. The gated operation is
                         lossless by construction (no reservoir windows AND no memory entries AND past
                         grace), so its off position only reinstates a known-untrippable guard.
  MERGED (both fold into a lever this file DOES declare, so neither is an unresolved merge):
    DOM_RELATIVE (0)  -> the `margin` arm of `accept_rule`
    MERGE_FRAC (0.8)  -> `merge_dist`, and see DEFECT 3 for what that merge cannot mean
  PROMOTED TO WIRE: none from this package. One row lands here from FAB -- see WHAT IS ABSENT.

--------------------------------------------------------------------------------------------------
THE THREE CENSUS DEFECTS, CHECKED HERE
--------------------------------------------------------------------------------------------------
1. DOUBLED ENVIRONMENT NAMES -- 0 rows corrected, because 0 of the 33 DOM rows carry the defect.
   The defect is real and this file is not evidence against it: the census records a target as
   `FAB.FAB_N0` or `MEM.MEM_TOPK` -- prefix in one column and the prefix REPEATED inside the name in
   the next -- and spine/lever.py generates the environment name as f"{PREFIX}_{FIELD.upper()}", so
   taking such a row literally declares a field `FAB_N0` answering to `FAB_FAB_N0`: a name no operator
   has ever set, on a lever that then runs at its default forever while registry.unread_env() reports
   the operator's real `FAB_N0` as a typo. The sibling files corrected 78 such rows (fabric) and 9
   (memory). Every DOM row was checked mechanically against `new_name.startswith("DOM_")`; all 33 name
   a bare field (`DOM.enabled`, `DOM.spawn_dist`, `DOM.accept_rule`), so all 33 are carried over
   verbatim. The adversarial reviewer reached the same conclusion independently and used this section
   as the evidence that the doubling elsewhere is a clerical slip rather than a decision: "the
   `## domains` section uses the correct form ... so the census is internally inconsistent about the
   one rule it most often cites" (.rework/reviews.json, review 2). Reported as 0, not skipped.

2. CLOCK KINDS -- 1 label corrected, 2 gaps named, 1 conflict named rather than resolved.
   THE RULE APPLIED, stated because it is the thing that decides each case: a number COMPARED AGAINST A
   RUNNING COUNTER carries that counter's kind; a number that merely SIZES a container carries COUNT.
     * ALREADY RIGHT (3 rows): `manage_every`, `cull_stale` and `grace` are all filed Windows and all
       three are compared against `step` (:6693, :3672, :3638/:3669), which advances once per WINDOW
       (`i += WIN; step += 1`, :7708) while the loop body runs once per FLUSH. None needed a change.
     * CORRECTED (1 row): `sustain`, filed by the census as `count`. It is compared against `s.run`
       (:3483), a run length incremented once per call to DomainAssembler.update, and update is called
       once per window -- above the batch early-out at :6795, not below it. It is declared U.Windows.
       The label is what makes its one documented coupling legible: at DATA_SEG_MIN/SEG_MAX 700/1800
       and ~490 bytes per window a segment is 2.6 WINDOWS, so sustain=2 spends two of them and leaves
       under one settled window per segment (:5640-5643). "2 count" hides that arithmetic; "2 windows"
       states it. Nothing else in this file changes kind.
     * GAP, NOT A CORRECTION (2 rows): `recur_horizon` counts BOUNDARIES (`s.nb - s.bornb[i]`, :3614)
       and `min_visits` counts separate ENTRIES into a domain (:3491). units.py has neither kind, and
       Selections is expert selections, not domain visits. Both stay U.COUNT with the gap stated at
       the declaration. Inventing a clock kind is a spine edit, not a domains edit -- and this is a
       genuine third clock in the system (windows, flushes, boundaries), which is worth reporting
       rather than papering over: the resume defect at :4991, where the boundary clock restarted at 0
       and the fold would have swallowed every restored domain, is precisely the class Clock exists for.
     * CONFLICT, NAMED NOT RESOLVED: this package's `manage_every` was SPLIT OFF from MANAGE_EVERY,
       which is now FAB's field of the same name -- and spine/assemble.py::_owner_blocks wraps that field as
       `derive.flush_period(Steps(r["FAB"].manage_every), r["TRAIN"].batch_w)` while the census types
       it Windows. Two files, one counter, two kinds. It reaches into this package the moment a DOM
       cadence is needed in flushes, because derive.flush_period REFUSES anything but Steps
       (derive.py::flush_period): there is today NO legal conversion from a Windows-typed cadence to the
       flush clock. Whoever ports the manager must either add a Windows arm to spine.derive or change
       what FAB.manage_every is typed as. Choosing here, silently, is how one number gets two meanings.

3. UNRESOLVED MERGES -- 0. Both merge rows name a surviving lever that this file declares:
   DOM_RELATIVE -> `accept_rule` (minted from DOM_RADIUS's row) and MERGE_FRAC -> `merge_dist` (minted
   from MANAGE_MERGE's row). Nothing had to be emitted under its own name to avoid inventing a target.
   WHAT THE MERGE_FRAC ROW ASKS FOR ANYWAY, AND WHY IT CANNOT HAPPEN, because the row does not merely
   merge: it says "the design intent survives as an intra-package derived default (d_merge_dist =
   frac * spawn_dist resolved once in spine.derive and printed)". Three separate rules forbid that
   sentence. (a) spine/lever.py refuses a computed default outright -- "A value derived from another
   lever is a WIRE, not a default". (b) `d_` is the WIRE namespace and a wire is a CROSS-package
   coupling declared in spine/assemble.py; an intra-package derivation is not a wire and would appear
   in the coupling graph as an edge from DOM to DOM. (c) `frac` has no owner once MERGE_FRAC is merged
   away, so the expression has a free variable. So 0.8 does not survive in any form: `merge_dist`
   (0.28) is the only route to the merge threshold, and the arithmetic in the census's own row is what
   settles it -- `md = merge_dist if merge_dist > 0 else MERGE_FRAC * NEW_DIST` (:3643) means the
   product is unreachable at any non-zero merge_dist, and 0.28 equalling 0.8 x 0.35 is a coincidence,
   not a construction. The adversarial reviewer flagged the same row for the same reason.

--------------------------------------------------------------------------------------------------
WHAT IS DELIBERATELY ABSENT
--------------------------------------------------------------------------------------------------
ONE WIRE ARRIVES, and it must NOT be declared here -- lever.py refuses a d_-named lever precisely so a
declaration cannot shadow the wire that writes it:
    d_expert_slots = FAB.slots        (spine/assemble.py::_view, reducible)
It is the old MAX_DOMAINS, the canonical computed-default defect: `MAX_DOMAINS = _i("MAX_DOMAINS",
_i("FAB_NMAX", 4096))` at :598 read FAB_NMAX eagerly into the audit on every run, and the SAME name was
read as `_i("MAX_DOMAINS", 32)` at :4874 when sizing the memory source census -- one knob, two defaults,
128x apart. The cap it sets is live in this package (:3546-3548, :3556: at cap, absorb into the nearest
WITHOUT dragging its centroid), so the port reads `dom.d_expert_slots` there and nowhere else.

    DECLARING THIS FILE TURNS tests/test_ownership.py O4 REDDER BY ONE ROW, ON PURPOSE. O4's backward
    direction -- "every declared wire is read" -- defers a row while its package has no LeverSet in
    src/. DOM now has one, so DOM.d_expert_slots moves from "deferred (package not in src/ yet)" to a
    seventh declared-but-unread finding, joining the six the fabric and memory declarations already
    produced. The check is right and the tree is half-built; the resolution is the domain manager
    reading it, NOT a stub reader added here to green the check. tests/test_derive.py is unaffected
    (575 cases, 0 mismatches, before and after).

FOUR FOREIGN VALUES THIS PACKAGE READS TODAY AND MAY NOT, each an L2 violation to repair at port. None
is declared here, because a value another package owns is a wire or it is nothing:
    MEM_SRC_FLOOR   -- :3688 computes the floor inline as
                       `int(mem.src_floor * mem.cap / max(1, mem._eligible().sum()))`, reaching through
                       three of MEM's internals including a private method. The floor's ENTRY COUNT
                       must arrive as d_mem_floor_entries; see `cull_respects_mem_floor`.
    COMP_PROTECT    -- FAB's flag (census: FAB.FAB_COMP_PROTECT), read at :3694 inside the domain cull.
                       The competence baseline crosses the other way too: `comp_glob` is DOM's number
                       and FAB reads it at :6720 for the spare rule. One crossing is declared in
                       assemble and the other is not, so `grep d_` does not enumerate the pair.
    REKEY_EVERY     -- MEM's cadence (census: MEM.rekey_every), and asm.rekey runs on it at :6688.
                       The re-key is an EVENT this package receives, not a cadence it owns.
    SIG_MODE        -- SIG's arm; :6689 rekeys only when SIG_MODE == "learned".
And the retok event behind `tokc_decay` arrives from TOK as a signal. DOM must not read RETOK_EVERY.

--------------------------------------------------------------------------------------------------
TWO DECLARATION CHOICES THAT ARE NOT THE CENSUS'S
--------------------------------------------------------------------------------------------------
FOUR MULTIPLIERS DO NOT CARRY THE CENSUS'S "fraction 0..1" LABEL. `shift_mult` (1.5), `radius_mult`
(1.2), `radius_cap` (2.0) and `fold_mult` (1.5) are MULTIPLES, and a label the default itself falsifies
is worse than no label -- docs/04_LEVERS.md is generated from these declarations and would print
"2.0 fraction 0..1". The census says so itself in three of the four rows ("the FRACTION-for-a-multiple
compromise ... that mislabel should be fixed in the units metadata rather than by pretending the number
is a fraction"), and this is the fix it asks for. They carry U.COUNT plus a line under each saying what
they are a multiple OF. The rule is narrow: where the default satisfies the census's label -- `margin`
0.75, `decay` 0.9, `radius_q` 0.85 and every distance threshold here -- the census's label is kept.
This matches src/fabric/levers.py, which made the same call on five multipliers; units.py has no
MULTIPLIER constant and adding one is a spine edit.

ON/OFF LEVERS ARE DECLARED True/False, NOT 1/0, and TWO BOOLEANS BECOME NAMED ARMS. The bool default
selects a coercion branch in Lever.coerce, so DOM_ENABLED=off means off; with an int default it raises.
The honest cost, which is the spine's rule for every bool in the tree and not a choice made here: any
unrecognised string outside ("0", "", "off", "no", "none", "false") reads as True, so DOM_FOLD=flase is
silently on. Separately, `accept_rule` and `shift_rule` are declared with choices= rather than as the
booleans they were. That is not decoration. ISSUES M24 records eleven knobs -- SIG_MODE, EVICT,
CULL_MODE, CHAIN_ROUTE, LR_SCHED and six more -- where an unrecognised string falls into whichever
branch is the `else`, so a typo silently runs a configuration the operator did not ask for and the log
names the arm they meant. These two levers are NEW string knobs; without choices= they would be the
twelfth and thirteenth. With them, DOM_ACCEPT_RULE=radiuss is a startup refusal naming the three legal
values. The second thing choices= buys is exclusivity: the three acceptance rules were three independent
booleans giving eight combinations of which most are meaningless, and the branch order made some
unreachable -- under DOM_RELATIVE=1 the entire NEW_DIST branch at :3545-3556 cannot run. An enumeration
turns that into a declaration, and gives the isolation sweep three arms instead of a boolean cube.
"""
# ABSOLUTE, NOT `from ..spine.lever import ...`. Every entry point in this tree puts `src` ITSELF on
# sys.path -- tests/test_derive.py::<module>, tests/test_ownership.py's SRC insert, and the verification
# command for this file -- which makes `domains` a TOP-LEVEL package, and a relative import one level
# above a top-level package raises "attempted relative import beyond top-level package" at import time.
# Verified, not assumed. The sibling packages src/fabric/levers.py and src/memory/levers.py spell it
# the same way, and two packages that spell one import two ways is the kind of difference that decides
# which of them a runner can load.
from spine.lever import Lever, LeverSet
from spine import units as U


class DOMLevers(LeverSet):
    """The partition's declared knobs: detect, assign, consolidate, cull, fold, predict.

    Grouped by the mechanism each one steers, because that is how they fail together. A flat list is
    what let the old tree file the boundary detector's three parameters under `domains`, the merge
    threshold under `MANAGE_*` with the FABRIC cadences, and TOKC_DECAY under a name that reads as a
    tokenizer knob -- one mechanism, three families, and no single place that said so.

    Read `cfg.spawn_dist`, never an environment name. Every value here is resolved once by
    spine.assemble and frozen; a function receiving this Config should open with `dom.owned_by("DOM")`,
    because a Config is an ordinary object and a foreign one handed in reads happily and wrongly.
    """

    PREFIX = "DOM"

    # ==============================================================================================
    # 1. DOES THE PARTITION EXIST, AND HOW OFTEN IS IT MANAGED
    #
    # Two switches and a cadence. They are separate levers and not one because the off-states differ:
    # `enabled` removes the partition, `manage` keeps it and freezes the population, and a cadence of
    # zero is neither -- it is a crash. The old tree conflated all three and the report advertised the
    # crash as an ablation.
    # ==============================================================================================

    enabled = Lever(True, "Assemble domains at all; off sends did=0 for every window, so there is one "
                          "bucket, no provenance and nothing to manage.", U.FLAG)
    # Census: SELF_ORG -> DOM_ENABLED. Renamed because SELF_ORG names a philosophy and not a package.
    # THE OFF-STATE IS NOT FREE OF FOREIGN EFFECTS, and this is the part the old name hid: with
    # SELF_ORG=0 every memory entry is written under src=0 (:6684), so MEM's per-source floor -- which
    # divides cap x floor by the number of LIVE sources -- protects exactly one source, and the DOMAIN
    # COLLAPSE warning at :6706 describes that state in as many words. In the rebuild the domain id
    # must reach MEM as a declared wire whose value is 0 when this is off, so "domains off" is a
    # configuration MEM can SEE rather than a degeneracy it discovers.

    manage = Lever(True, "Run merge, cull and fold over the population; off freezes the domain set "
                         "and lets it grow unbounded.", U.FLAG)
    # Census: MANAGE -> DOM_MANAGE. THE OWNERSHIP SPLIT IS THE POINT. One field gated five call sites
    # in what the census counts as four packages -- domains (:6693), fabric.manage (:6716), the expert
    # bank (:6764), FAB_SPAWN (:6836) and society (:6961) -- a textbook L2 violation, and the reason the report's "DID IT FIRE" row for
    # `fabric.cull` was disarmed by a knob filed under domains (:8568). FAB declares its own flag; this
    # one gates this package only.
    # DO NOT COLLAPSE THIS INTO manage_every=0 AS THE OFF-STATE. :6693 evaluates
    # `step % DOM_MANAGE_EVERY` with no max(1, ...) guard, so the audit's own advertised armed-predicate
    # "DOM_MANAGE_EVERY=0" (:8617-8639) is a ZeroDivisionError and not an ablation. An explicit flag is
    # also the lesson of SIG_WIN=0, one of the two confirmed fatal defects, where a magic zero meant
    # "derive it" on one path and "one byte" on another.

    manage_every = Lever(100, "Windows between management passes: merge, then cull, then fold.",
                         U.Windows)
    # CLOCK: Windows, and the census and the source agree -- `step % DOM_MANAGE_EVERY` at :6693, and
    # `step` advances once per WINDOW (:7708). See the module header's DEFECT 2 for the conflict this
    # inherits from its sibling: FAB.manage_every, the field it was SPLIT OFF from, is typed Windows by
    # the census and wrapped as `Steps(...)` by spine/assemble.py::_owner_blocks. Not resolved here.
    # LOAD-BEARING, AND THE SPLIT IS WHY. Sharing MANAGE_EVERY=500 with the expert and world
    # populations meant it essentially never ran: a 60 kB run is 468 steps, so `step % 500 == 0` was
    # NEVER true and merge/cull/fold executed ZERO times; the 120 kB GH200 runs are 937 steps and fired
    # it ONCE. Every domain-population number this project has published was produced with the
    # consolidation half of the mechanism switched off by arithmetic (:649-655). That is the owner's
    # "the instrument was broken, not the mechanism" case, stated about a cadence.
    # PORT REQUIREMENT, NOT ENFORCEABLE BY THIS DECLARATION: 0 must mean NEVER, behind a guard at the
    # read site. Today it is a ZeroDivisionError, and three DID IT FIRE rows print it as their disarm
    # reason. A lever cannot check its own reader; `choices=` cannot express "0 or any positive int".
    # COUPLING THAT CANNOT BE REMOVED, so it gets printed instead: `decay` applies once per PASS, so
    # the effective activity half-life in windows is (cadence x decay). Changing this number silently
    # rescales `cull_act_min`. That pair belongs in the coupling graph as irreducible.

    # ==============================================================================================
    # 2. WHERE THE STREAM IS CUT
    #
    # A boundary is an adjacent-window cosine jump that persists. Everything downstream depends on this
    # firing at the right rate: SHIFT_DIST never firing is the documented path to "0 boundaries, 1
    # domain, the entire domain apparatus inert" (:5031-5052), and firing on ordinary within-segment
    # variation gives one domain per splice segment. Both failures have been observed in real runs.
    # ==============================================================================================

    shift_rule = Lever("constant", "Boundary test: `constant` trips at a fixed distance, `relative` "
                                   "trips at a multiple of a running quantile of recent distances.",
                       U.NAME, choices=("constant", "relative"))
    # Census: SHIFT_REL (0) -> DOM_SHIFT_RULE, as a two-choice rule rather than a boolean, so that the
    # parameters belonging to only one arm are visibly scoped. Default `constant` IS the old 0.
    # NOT DROPPED DESPITE BEING OFF, and the distinction is the owner's rule that a broken calibration
    # is not a broken mechanism: the first shipped relative form was a GUESS (q75 x 2.0) that stops
    # firing from N=1000 onward and produced 14 boundaries for 3213 true switches -- recall 0.01,
    # collapsing the assembler to a single domain. The probe-calibrated q50 x 1.5 fires at every stage
    # the probe measured (:3465-3477). The mechanism was never tested; a guess at its parameters was.

    shift_dist = Lever(0.30, "Under shift_rule=constant, the adjacent-window cosine distance that "
                             "counts as a candidate boundary.", U.FRACTION)
    # THE DEFAULT BOUNDARY RULE, AND THE WHOLE PARTITION STARTS HERE -- which is why its known weakness
    # is carried in this comment rather than fixed by deletion. The probe measured WITHIN-segment
    # adjacent distance running 0.044 -> 0.229 -> 0.317 -> 0.340 as the encoder trains, against this
    # CONSTANT 0.30, so boundary precision falls 0.92 at N=200 to 0.27 at N=16000: late in a run the
    # detector trips on ordinary within-segment variation. That is the same disease `spawn_dist` has,
    # and it is why `relative` exists.

    shift_q = Lever(0.50, "Under shift_rule=relative, the quantile of the last 512 adjacent distances "
                          "used as the base.", U.FRACTION)
    shift_mult = Lever(1.5, "Under shift_rule=relative, trip when the jump exceeds this many times "
                            "the shift_q base.", U.COUNT)
    # UNIT: a MULTIPLE of the shift_q base, not a fraction (module header). BOTH COORDINATES ARE
    # LOAD-BEARING and that is why they are two levers and not one product: the probe table shows
    # q75 x 2.0 dead from N=1000 while q50 x 1.5 fires at every measured stage --
    #     N=200   within 0.019  across 0.094 | q75*2.0 = 0.068 fires | q50*1.5 = 0.028 fires
    #     N=1000  within 0.106  across 0.215 | q75*2.0 = 0.316 DEAD  | q50*1.5 = 0.159 fires
    #     N=4000  within 0.212  across 0.342 | q75*2.0 = 0.559 DEAD  | q50*1.5 = 0.318 fires
    # Collapsing them into one number erases the distinction the calibration turns on. Both are read
    # only when shift_rule=relative, which the choices lever now makes a declaration rather than a
    # reading exercise. (q50 x 1.5 also fails at N=16000, where AUC is 0.70 and no threshold does well
    # -- which is a reason not to over-train the encoder, not a reason to retune this.)

    sustain = Lever(2, "Consecutive over-threshold windows required before a boundary is declared; "
                       "the pending signatures are then averaged into the assign query.", U.Windows)
    # CLOCK CORRECTED FROM THE CENSUS (`count` -> Windows). It is compared against `s.run` (:3483), a
    # run length incremented once per DomainAssembler.update, and update runs once per window, above
    # the batch early-out. See DEFECT 2 in the header for the rule and the reason.
    # IT DOES TWO JOBS AND THE SECOND ONE IS WHY IT IS NOT JUST A DEBOUNCE: the pending signatures it
    # accumulates are averaged into the assign query (:3487), and that smoothing is what fixed the
    # over-segmentation -- a single RAW window sits further from its own class mean than the spawn
    # threshold, so re-entry reliably spawned.
    # THE COUPLING THE REPORT ALREADY PRINTS, and the reason this number cannot be raised freely: at
    # DATA_SEG_MIN/SEG_MAX 700/1800 and ~490 bytes per window a segment is 2.6 windows, so sustain=2
    # consumes two of them and leaves under ONE settled window per segment. The clustering scores then
    # describe the transitions rather than the domains (:5640-5643, :5710). Those are DATA's levers and
    # LM's window; the arithmetic must be printed, not re-derived here.

    # ==============================================================================================
    # 3. WHICH DOMAIN THE MATERIAL AFTER A BOUNDARY BELONGS TO
    #
    # One decision -- re-enter the nearest domain, or spawn a new one -- and three rules that make it.
    # In the old tree those were three independent booleans (DOM_RADIUS, DOM_RELATIVE, DOM_ADAPTIVE)
    # giving eight combinations of which most are meaningless, in a branch order that made whole
    # mechanisms unreachable without saying so. They are one enumerated lever now.
    # ==============================================================================================

    accept_rule = Lever("radius", "How re-entry is decided: `radius` uses each domain's own measured "
                                  "acceptance radius, `margin` compares nearest against runner-up, "
                                  "`constant` uses spawn_dist alone.",
                        U.NAME, choices=("radius", "margin", "constant"))
    # Census: DOM_RADIUS (1) -> DOM_ACCEPT_RULE, absorbing DOM_RELATIVE (0) as the `margin` arm. The
    # literal "radius" is the shipped configuration exactly: DOM_RADIUS=1, DOM_RELATIVE=0. "constant"
    # is DOM_RADIUS=0. The DOM_ADAPTIVE arm is not offered -- its row is a drop (see the header).
    # WHY THE RADIUS ARM IS THE DEFAULT: it is one of the two changes that beat the constants on the
    # controlled synthetic test -- live domains 64.0 -> 18.0, V 0.82 -> 0.95, and flat rather than
    # growing with stream length. The other is `fold`.
    # WHAT THE ENUMERATION CHANGES BEHAVIOURALLY, stated because it is not a pure rename: the old
    # branch order let radius act as a SECOND acceptance test inside the relative branch
    # (`if d1 <= DOM_MARGIN * d2 or (_r is not None and d1 <= _r)`, :3542), so DOM_RELATIVE=1 with
    # DOM_RADIUS=1 was a fourth configuration nobody named. Under this lever the arms are exclusive:
    # `margin` means margin alone. That is the coupling the census asked to remove, and it is a real
    # change to the on-margin path rather than a relabelling of it.
    # THE MARGIN ARM SURVIVES ON EVIDENCE, NOT SENTIMENT: the scale-drift it was built for is
    # probe-measured (1-NN corpus accuracy holds 84-95% while absolute distances inflate 18x), and the
    # source's own note says two of the runs that scored it worse changed the threshold rule and
    # ENC_WARMUP together, "so they cannot even be attributed" (:607-616). A confounded measurement is
    # not a proof, so it stays as a selectable arm.

    spawn_dist = Lever(0.35, "Cosine distance beyond which an assign query spawns a new domain instead "
                             "of re-entering the nearest.", U.FRACTION)
    # Census: NEW_DIST -> DOM_SPAWN_DIST. Renamed because NEW_DIST says nothing about which decision it
    # makes, and because the merge threshold had to stop deriving from it by a second route.
    # STILL LOAD-BEARING UNDER accept_rule=radius: it is the bootstrap threshold every domain uses
    # before its first rekey has measured a radius, and the pooled fallback's origin (:3546, :3555).
    # WHY IT CANNOT BE THE WHOLE RULE, measured rather than argued: d(query, own centroid) runs
    # .037 -> .136 -> .319 -> .421 -> .668 over 200-4000 encoder steps (:3518-3521), so a CONSTANT sits
    # between within- and between-domain distances for only a few hundred steps. At GH200 scale
    # within-domain cohesion of 0.61 (d = 0.39 > 0.35) made re-entry arithmetically forced to spawn:
    # 142 domains for 4 corpora, silhouette -0.22.

    margin = Lever(0.75, "Under accept_rule=margin, re-identify when the nearest centroid is at most "
                         "this fraction of the runner-up's distance.", U.FRACTION)
    # The sole parameter of the margin arm, probe-validated against 20 cells. Read only when
    # accept_rule=margin -- which the enumeration now makes explicit, instead of leaving it a knob that
    # silently does nothing in the default configuration.

    radius_q = Lever(0.85, "Quantile of d(reservoir window, own centroid) that defines a domain's "
                           "acceptance radius, and of the pooled distances for domains with none yet.",
                     U.FRACTION)
    # ONE OF THE TWO NUMBERS DEFINING THE MEASURED RADIUS, and it is free: rekey has already encoded
    # the reservoir, so the distances exist before the quantile is taken (:3574-3575). Near-degenerate
    # with radius_mult -- both enlarge one scalar -- but not redundant: the quantile is BOUNDED by the
    # observed reservoir while the multiplier extrapolates past it, and the fold's pooled-radius guard
    # uses this quantile over ALL domains' distances.

    radius_mult = Lever(1.2, "Multiplier on the measured quantile that gives the acceptance radius.",
                        U.COUNT)
    # UNIT: a MULTIPLE of the measured quantile (module header); >1 by design. NOT A FREE PARAMETER --
    # "measured radius x1.2" is the exact configuration in the controlled 3-seed table that took live
    # domains from 64.0 to 18.0 at V 0.95, so the slack factor is part of the measured result.

    radius_cap = Lever(2.0, "Voronoi guard: no radius may exceed this multiple of the distance to the "
                            "nearest OTHER centroid. 0 removes the guard.", U.COUNT)
    # CALIBRATED, NOT ASSUMED, and the first value tried was the worst setting in the table:
    #     cap   0.0(off)   0.5    1.0   1.5   2.0   2.5   4.0
    #     live     4.0    65.0    4.0   4.0   4.0   4.0   4.0     <- >= 1.5 is indistinguishable from off
    # 0.5 strangled the radius back to the baseline it exists to fix (65 live / V 0.82). 2.0 sits in
    # the flat region, so it costs nothing on healthy geometry while still bounding the runaway it is
    # for: a radius that absorbs one foreign window measures a LARGER spread and absorbs more, observed
    # reaching 1.24 of a maximum possible 2.0 (:3577-3588). 0 is a REAL arm precisely because the table
    # shows the guard inert in the healthy case.

    reservoir = Lever(40, "Sample windows kept per domain; the basis for rekey's centroid and for the "
                          "measured radius.", U.COUNT)
    # Census: DOM_WINS -> DOM_RESERVOIR, because WINS reads as a win count and this is a window
    # reservoir. UNIT stays COUNT under the header's rule: it SIZES a container, it is not compared
    # against a running counter.
    # IT IS THE UNCENSORED SAMPLE, which is the whole reason the radius is estimable at all. The
    # rejected alternative estimated the radius from the distances at which a domain was MATCHED, and
    # that cannot bootstrap -- matching requires a radius, so with spawn_dist too tight nothing matches,
    # no samples accumulate, and the radius never activates: 0 of 143 domains ever learned one, and a
    # pooled prior over the same censored sample held 3-5 entries. A window enters this reservoir
    # because it was ASSIGNED, whatever the threshold said. It is also a TRUE reservoir (:3500 replaces
    # with probability reservoir/size), replacing a first-40-only rule that pinned each centroid to the
    # domain's BIRTH so that every rekey undid both the EMA drift and every merge.
    # DECLARED INTRA-PACKAGE DERIVATION, not two independent knobs: this size sets the RESOLUTION of
    # radius_q. At 40 windows the 0.85 quantile is the 34th value, so shrinking the reservoir quietly
    # coarsens every radius in the population.

    # ==============================================================================================
    # 4. CONSOLIDATION -- ONE THRESHOLD, AND THE LESSON THAT IT MUST AGREE WITH CREATION
    # ==============================================================================================

    merge_dist = Lever(0.28, "Cosine distance under which two domains are merged into one during a "
                             "management pass.", U.FRACTION)
    # Census: MANAGE_MERGE -> DOM_MERGE_DIST, absorbing MERGE_FRAC. Renamed out of the MANAGE_* family
    # it never belonged to. See DEFECT 3 in the header for why 0.8 does not survive in any form: this
    # 0.28 is the only route to the merge threshold, and `d_merge_dist` must not exist.
    # THE FAMILY'S BEST-DOCUMENTED LESSON, which is about the RELATION to spawn_dist and not about this
    # number alone: at 0.12 against a creation threshold of 0.35, every pair in [0.12, 0.35) was
    # PERMANENT -- created as distinct, never close enough to merge -- and that is 8x fragmentation.
    # The measured sweep:
    #     0.12 -> 25 live, V 0.72, 8x fragmentation
    #     0.45 ->  4 live, V 0.89, bijection with the 4 corpora
    #     0.80 ->  4 live, purity 0.71                      <- a COUNTERFEIT 4
    # which is why a domain count may never be read without purity and homogeneity beside it.
    # 0.28 IS A POLICY CHOICE, NOT A CORRECTNESS ONE, and the distinction matters for goal B: `did` is
    # consumed only by mem.src, the affiliation map and the report, so this number sets the GRANULARITY
    # OF FORGETTING (20 deletes of 1.6% at 25 domains, against one delete of 30% at 4) -- not
    # prediction quality.

    # ==============================================================================================
    # 5. CULL -- THE LEVERS WITH THE SHARPEST CONTINUAL-LEARNING CONSEQUENCE
    #
    # A domain is culled when it is BOTH inactive and stale, is past grace, is in the bottom cull_frac
    # by activity, and is not protected. Every one of those conjuncts exists because the rule without
    # it destroyed material a run needed. The cull calls mem.delete_src(), so a mistake here is not a
    # bookkeeping error -- it is deletion of the store's contents.
    # ==============================================================================================

    cull_frac = Lever(0.10, "Per-pass cull budget: the bottom fraction of domains by decayed activity "
                            "are considered.", U.FRACTION)
    # THE FIX THAT MOTIVATED IT IS THE COMMENT. `max(1, int(0.10 * n))` made a FRACTION into a MINIMUM
    # of one for any population under ten, turning "cull at most a tenth" into "cull at least one,
    # every pass, forever". The run that added Python shows the ratchet landing three separate times on
    # exactly the number where `len(s.cent) <= 1` is the only thing left to stop it:
    #     [manage @ 96500] merged 0 culled 1 -> 3 live domains
    #     [manage @ 97300] merged 0 culled 1 -> 2 live domains
    #     [manage @ 97400] merged 0 culled 1 -> 1 live domains
    # At n >= 10 the floor never bound (int(0.10 * 10) is already 1), so removing it changed nothing
    # about a healthy population and removed the only rule that could drive one to a single domain
    # (:3648-3663). A population too small for a proportional cull is not culled proportionally; the
    # empty-cull and the merge still run, and both are lossless. THE FABRIC STILL CARRIES THE SAME
    # max(1, ...) ratchet (ISSUES M31, :2263), so this lever's history is also the argument for FAB's.

    cull_act_min = Lever(15, "Cull threshold on a domain's DECAYED activity counter -- not a window "
                             "count, and never readable as one.", U.COUNT)
    # Census: MANAGE_MIN -> DOM_CULL_ACT_MIN, and the rename is mandatory rather than cosmetic. The old
    # name and its own declaration comment ("cull domains < MIN windows unseen for STALE", :957)
    # describe a WINDOW COUNT, while the code compares it against `act` (:3672), a decayed float that
    # never equals a window count: at decay=0.9 and a 100-window cadence, `act` saturates near 1000 for
    # a continuously fed domain, so 15 is roughly 1.5 windows per pass and not 15 windows. That is the
    # wrong-measurement class (98 survey records) sitting inside a lever NAME.
    # UNIT: COUNT, and deliberately not a clock -- the quantity compared is an activity score, not a
    # counter of events. It cannot be read without `decay` and `manage_every` beside it, because
    # (cadence x decay) is what sets the scale this 15 lives on.

    cull_stale = Lever(500, "Windows since a domain was last fed before it counts as stale for the "
                            "cull.", U.Windows)
    # CLOCK: Windows -- `step - s.last[d] > stale` at :3672 and `step` counts windows.
    # THIS IS THE LEVER GOAL B LIVES OR DIES ON, and the failure is recorded, not hypothetical. Under a
    # phased schedule (DATA's PHASE_SCHED, e.g. [[0],[0],[1],[1]]) the ABSENT process's domains have
    # `act` decaying toward zero and `last` stale within cull_stale windows BY CONSTRUCTION -- not
    # because they are useless, but because nobody is streaming them. So while Python streamed,
    # English's whole domain population became cullable and was culled, and its memory went with it:
    # 200,000 entries ending under a single source id (:3676-3688). "Not less useful, merely no longer
    # WRITTEN" is the same sentence MEM's eviction rule needed, one level up. Which is why the next
    # lever exists, and why this one must be a declared coupling with the memory floor rather than a
    # positional argument in a manage() call.

    decay = Lever(0.9, "What each domain's activity counter keeps per management pass, so `act` "
                       "measures RECENT use rather than cumulative use.", U.FRACTION)
    # It replaced a cumulative `size` under which any domain that ever reached the minimum was
    # IMMORTAL, and it is the rule the expert router already uses -- one decay discipline for both
    # populations. THE COUPLING IS NAMED RATHER THAN DENIED: this decays per PASS, so the effective
    # half-life in windows is set by (manage_every x decay), and changing the cadence silently rescales
    # cull_act_min. It cannot be removed -- an activity counter has to be decayed on SOME clock -- so
    # PLAN section 4's rule applies: print it in the coupling graph as an irreducible pair.

    grace = Lever(500, "Minimum age in windows since birth before a domain may be culled, on both cull "
                       "paths.", U.Windows)
    # CLOCK: Windows (`step - s.born[d]`, :3638 and :3669). A newborn domain has BY DEFINITION not had
    # a chance to be re-entered, and both cull paths need the same guard or the weaker one decides.
    # WHAT IT DOES ACROSS A CHECKPOINT, which must be stated because the neighbouring case was a real
    # defect: :4999 records that a RESTORED domain is treated as newly born, so grace is re-armed on
    # resume. That is the conservative direction and should stay -- but the boundary clock in the
    # recurrence path restarted at 0 on resume (:4991), and there the same "clock restarts" behaviour
    # meant the fold would have swallowed every restored domain. Same word, opposite consequence; the
    # difference is which side of the comparison the reset lands on.

    cull_respects_mem_floor = Lever(
        True, "Refuse to cull a domain that still holds a per-source floor's worth of memory entries.",
        U.FLAG)
    # Census: DOM_CULL_FLOOR -> DOM_CULL_RESPECTS_MEM_FLOOR, renamed so the name says WHICH floor and
    # WHOSE. It closes an asymmetry that was catastrophic-forgetting-by-manager: MEM's source floor
    # forbids EVICTING a source's entries, while this cull called mem.delete_src() and deleted them
    # outright -- the bigger action on the weaker of the two tests. ORDERING IS THE WHOLE MECHANISM:
    # evict first, then cull, never cull in order to evict. It self-releases, because once eviction has
    # genuinely drained a domain it falls below the floor and becomes cullable.
    # 0 IS A REAL ARM and stays settable: it is explicitly the configuration that reproduces the
    # collapse-to-one-domain run, which is a thing an isolation sweep needs to be able to ask for.
    # L2 VIOLATION TO REPAIR AT PORT, and it is in this lever's read site: :3688 computes the floor as
    # `int(mem.src_floor * mem.cap / max(1, mem._eligible().sum()))` -- three of MEM's internals
    # including a private method, read from inside the domain manager. The floor's entry count must
    # arrive as the wire d_mem_floor_entries from MEM. This lever then decides whether to CONSULT it.

    # ==============================================================================================
    # 6. THE RECURRENCE FOLD -- THE TEST THAT MAKES A POPULATION INTENSIVE
    #
    # Domains are created at boundaries; until this existed, nothing ever asked whether the thing
    # created came BACK. That question is the whole test for self-assembly: a real domain is re-entered
    # when similar material returns, while a splice artifact is entered once and never again. Folding
    # rather than deleting keeps provenance and hands the survivor the reservoir.
    # ==============================================================================================

    fold = Lever(True, "Fold domains that never recur into their nearest neighbour instead of leaving "
                       "them standing.", U.FLAG)
    # Census: DOM_RECUR -> DOM_FOLD, so that fold and fold_mult read as one mechanism. THIS IS THE
    # CHANGE THAT MADE THE POPULATION INTENSIVE: 4.0 live against a truth of 4, V 1.00, and 4 -> 4 -> 4
    # at 120/240/480 segments where constants alone gave 64 -> 116 -> 193. A population that grows with
    # stream length is a log of the splices; this is the first thing in the project's history that
    # passed that test.
    # KEPT AS AN EXPLICIT FLAG rather than expressed as min_visits=0, because a magic-zero off-switch
    # is what produced SIG_WIN=0 meaning two different things on two paths -- one of the two confirmed
    # fatal defects in the survey.

    min_visits = Lever(2, "'Recurs' means entered on at least this many SEPARATE occasions; below it a "
                          "domain is a fold candidate.", U.COUNT)
    # It is the operational definition of the question the partition exists to answer -- did the thing
    # we created come back? -- and a visit is counted only when s.cur actually CHANGES (:3491), so it
    # counts separate entries rather than re-confirmations.
    # UNIT GAP, STATED NOT INVENTED: this counts domain entries, and units.py has no kind for them
    # (Selections is expert selections). It stays COUNT. It is also read by an INSTRUMENT as well as by
    # the mechanism -- the report's recurrence line at :8359-8364 -- so under the instrument rule it
    # must arrive in the report as a wire and be printed beside the number it defines, which :8364
    # already does.

    recur_horizon = Lever(32, "Boundaries that must pass since a domain's birth before it is judged "
                              "for recurrence at all.", U.COUNT)
    # THE CHOICE OF A BOUNDARY CLOCK OVER A STEP CLOCK IS DELIBERATE AND CORRECT: what a domain needs
    # before "it never came back" is fair is a number of CHANCES to be re-entered, not a number of
    # windows. A domain born in a quiet stretch would otherwise be judged on the same deadline as one
    # born in a busy one (:3614, clock incremented at :3485).
    # UNIT GAP, AND IT IS THE HONEST ONE TO REPORT: this is a genuine THIRD clock in the system --
    # windows, flushes, boundaries -- and units.py has kinds for the first two only. Declared COUNT
    # rather than mislabelled with a clock that exists, because a wrong clock kind is worse than an
    # untyped count: a wrong kind compares fine. Adding a Boundaries kind is a spine edit. The cost of
    # the gap is on record: at :4991 the boundary clock restarted at 0 on resume and the fold would
    # have swallowed every restored domain -- exactly the class Clock exists to catch, on the one clock
    # it cannot see.

    fold_mult = Lever(1.5, "Refuse to fold a domain further than this multiple of the POOLED radius.",
                      U.COUNT)
    # UNIT: a MULTIPLE of the pooled radius (module header).
    # THE FAIL-SAFE, IN BOTH DIRECTIONS, and both clauses must survive the port as part of this one
    # lever rather than becoming implicit behaviour (:3624):
    #   too far from anything      -> leave it standing;
    #   NO pooled radius yet       -> also leave it standing, the bootstrap guard.
    # The failure without it is stated concretely by the source and is not a small one: an unbounded
    # fold collapses the whole population to ONE domain, which is far worse than folding late.

    # ==============================================================================================
    # 7. CAN A DOMAIN PREDICT? -- THE ONLY PLACE THIS PACKAGE TOUCHES GOAL A
    #
    # A per-domain token histogram, blended into the output distribution. It is the one route by which
    # a domain pays for itself in PREDICTION rather than only in editability -- which matters because
    # conditioning RETRIEVAL on the domain is already measured dead against a shuffled-provenance null.
    # ==============================================================================================

    prior_blend = Lever(0.15, "Weight of the per-domain token histogram in the blended prediction; "
                              ">0 also switches on the per-window accumulation that feeds it.",
                        U.FRACTION)
    # Census: DOM_PRIOR -> DOM_PRIOR_BLEND, renamed to say it is a blend weight.
    # ONE FIELD DOING TWO JOBS, and the split is a port requirement rather than a preference: at
    # :6788-6791 this value is a training-side ACCOUNTING SWITCH (accumulate asm.tokc per window), and
    # at :8147-8192 it is an INSTRUMENT PARAMETER (the mixing weight at eval). DOM owns the weight;
    # EVAL receives it as d_prior_blend, with the accumulation gated on the same resolved value so the
    # two cannot drift apart.
    # THE INSTRUMENT IT FEEDS IS VOID TWICE OVER TODAY, which is why no number here should be read as a
    # verdict on the mechanism: (1) it scores through _eval_logits, whose routing runs on the ONE-BYTE
    # eval signature (ISSUES, :3919); and (2) it needs 16 held-out windows while drawing min(48,
    # EVAL_WINDOWS) per domain, so at EVAL_WINDOWS=4 it collects 4 and produces NOTHING -- while the
    # histogram is still paid for on every window (:8172-8177). The report at least says so now.
    # 0.0 disables the accounting entirely and costs nothing, which is the honest off-switch.

    tokc_decay = Lever(0.5, "What a domain's token histogram keeps when the tokenizer re-segments; "
                            "applied once per retok. 1.0 restores cumulative-forever.", U.FRACTION)
    # Census: TOKC_DECAY -> DOM_TOKC_DECAY. Renamed into this namespace because TOKC_DECAY reads as a
    # tokenizer knob while sitting in the domains block -- the same drift that filed LOSS_MASK_DEAD
    # under `# tokenizer` inside the domains section.
    # THE REASONING IS SPECIFIC AND IS THE REASON THE DEFAULT IS NOT 1.0: the counts are over TOKEN
    # IDS, and a retok makes the same text into different ids. Counts banked before it are therefore
    # observations of a DIFFERENT distribution, not stale observations of this one, and the end-of-run
    # test scores against the FINAL vocabulary. Halving per retok leaves the histogram describing
    # roughly the last couple of intervals -- the same discipline `use` and `act` already run on
    # (:7785-7786).
    # THE RETOK EVENT ARRIVES FROM TOK AS A SIGNAL, NOT AS A LEVER READ. This package must not read
    # RETOK_EVERY: the cadence is TOK's to own, and a second copy of it here is a second answer to
    # "when did the vocabulary change".
