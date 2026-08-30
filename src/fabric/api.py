"""FAB -- the frozen public surface. Signatures only; P4 writes the bodies.

FAB is the expert population: a preallocated pool of low-rank experts, a router that picks a
handful per hop, and the two opposed forces that keep the pool honest over a long run -- growth
(spawn, replicate, crossover, mutation) against selection (the utilization cull, the failure cull,
and the spares that stop either from eating something merely mid-adaptation). D1 RULES THE FABRIC
STAYS. Goal A runs through it because it sits in the forward path and its mixture is what the head
decodes. Goal B runs through it because "learn a new area without destroying the old one" is, in
this design, exactly "grow capacity for the new material and do not cull the experts that hold the
old" -- which is why shift_tol, comp_protect, rescue and grace are the load-bearing levers here
and not the routing weights. D7 is a requirement on this package's INSTRUMENTS: overlap among
experts serving overlapping skills is an accepted possible outcome, so `contribution` must be able
to distinguish "interchangeable" from "the counterfactual measured nothing", which is precisely
what C3 destroyed.

ONE FORWARD PASS, BOTH ARMS. `society=True` is the soc loop at depth 1 with per-expert logits
retained -- NOT a second path. The old tree had two, and SUFFICIENCY called fab.society()
unconditionally while the shipped default was the looped path, which is how "479 experts buy
-0.002 b/B" came to be a measurement of a forward path the run never trained (D1, point 2).

RECORD TYPES RETURNED (P4 defines them):
  Population     A, B, cent, n_live, depth_now, and the books born/use/uage/dom_of/ef/es/comp/
                 contrib/births/rescued/parent/mutscale, the growth machine, the counter ledger
                 and the package RNG stream
  FabricOut      logits or hidden, expert_ids, weights, per_expert_logits, aux_loss, gates
  ContribReport  per-expert contribution, distinct_values, positive, negative, degenerate
  ManageReport   cull_fail, cull_util, spared_*, rescued, deepened, cull_gate arithmetic
  GrowReport     asked vs grown, per trigger; declined_cap, declined_newfrac, lineage counts
"""
from spine.lever import Config
from spine import units as U


def build(fab: Config, *, d_model, signature_dim, device, generator):
    """Preallocate the pool and found the population.

    cap = max(n0, slots); allocates A (cap, d_model, rank), B (cap, rank, d_model) ZERO-INIT (every
    expert is born an identity, so adding one never disrupts what already works), cent
    (cap, signature_dim), and the shared eemb/edec/q_route/hproj/halt_key modules. GROWTH NEVER
    REALLOCATES and the optimizer never sees a new parameter; only n_live moves.

    EVERY FOUNDER GETS A BIRTHDAY AND A ZERO USE-CLOCK. The old tree wrote `born` only in grow(),
    so at n0=2048 the entire founding population read age 0 forever and was permanently immune to
    culling (:1868-1876).

    Returns an INERT Population whose forward is the identity when `on` is False -- the composition
    root never reads `on`; this package does, and the ledger then records fab.off and reports every
    other row as "unreachable (FAB_ON=0)" rather than "armed but 0".

    RECEIVES: d_model <- LM.width, signature_dim <- SIG.d, device <- RUN.device, generator <- the
    package RNG stream from rng_for("fabric", seed). Exploration, parent sampling, crossover and
    mutation MUST NOT draw from the global stream: one extra random() shifts which bytes the stream
    builder reads next, so two runs differing only in how much they MEASURED trained on different
    text.

    LEVERS READ: on, norm_only, n0, slots, rank, dk, emb_hid, pressure, grow, halt
    WIRES READ: d_operating_population
    DID IT FIRE: fab.built, fab.n0, fab.cap, fab.operating_population (from
                 derive.operating_population, printed BESIDE the cull gate so the setpoint and the
                 gate are one statement), fab.off
    """
    fab = fab.owned_by("FAB")
    _ = fab.d_operating_population       # WIRE READ HERE -- the setpoint, printed with the gate
    raise NotImplementedError(
        "FAB.build: P4 (fabric) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section FAB.")


def forward(fab: Config, pop, *, h, signature, novelty, head=None, targets=None, step_windows,
            domain_id, live_domains, training, hold_out=None):
    """THE routed forward pass. One implementation, both arms.

    h: (B, L, d_model) from LM. signature: (B, sig_d) from SIG.encode -- NEVER a zero placeholder
    and never None; a caller with no signature is a caller that must not route. novelty: (B,)
    surprise from the previous step. head: LM.decode as a plain callable, needed for the per-hop
    vote and for spending HALT mass on the base representation. targets: (B, L) token ids, needed
    only for hop_sup and ind_w; when None those two terms are UNREACHABLE and say so.
    live_domains: DOM's live domain count -- RUNTIME STATE, so an argument, not the frozen wire
    fabric/levers.py:408 calls d_live_domains. `hold_out`: one expert id excluded from EVERY hop's
    routing distribution.

    Depth is min(depth_now, hops, 2 + n_live//2); society=True pins depth at 1 and keeps per-expert
    logits in the return so leave-one-out is a reweighted sum rather than a rerun.

    HOLD_OUT IS APPLIED INSIDE THE HOP LOOP. The old soc branch computed a banned entry
    distribution and then re-routed from scratch every hop WITHOUT it (:2618-2694), so the
    counterfactual walk was bit-identical for every candidate (C3).

    THE LOAD-BALANCE TERM HAS A GRAPH. The soc loop's return was
    `return h, _dep2/steps, _mass2/steps, h.new_zeros(())` (:2694) -- the fourth element is `bal`,
    consumed at :7031 as `FAB_BAL * _bw * _bal`, and fab_bal() is real but called only on the
    society branch, which defaults off. So FAB_BALANCE, BAL_FLOOR and BAL_WARM were read, printed
    and reasoned about at length while multiplying a freshly allocated zero for the entire run (C2).

    NOVELTY ENTERS THE QUERY, not the logit vector. `logits + s.nov(nov[:,None]).sum(-1,
    keepdim=True)` (:2361) collapses the term to a per-ROW scalar broadcast identically across all
    N expert logits, so it CANCELS in the softmax over experts and survives only as a shift against
    HALT -- while the class docstring describes it as biasing expert selection (M28).

    HALT GATES THE STATE UPDATE. :2683 applies the mixture at full strength on every hop regardless
    of how much probability has already halted, so the hidden state keeps changing after the router
    has decided to answer (M30). The residual step is scaled by the surviving mass.

    `.aux_loss` is the single scalar of every FAB-side penalty, ALL WITH A GRAPH: ponder, balance,
    div_w distinctness, ind_w independence, hop_sup per-hop CE, and the ae_w identity round-trip
    with its emb_var variance term. `.gates` carries the arithmetic of every gate this pass
    evaluated.

    LEVERS READ: on, norm_only, society, hop_vote, hop_sup, hops, depth0, halt, halt_max, alpha,
                 ponder, ponder_warm, route_region_w, route_learn, route_t, cent_topk, cent_ema,
                 discover, chain_k, ens_k, explore, ec_w, balance, bal_floor, bal_warm, dom_frac,
                 dom_min, div_w, ind_k, ind_w, dk, rank, emb_hid, emb_var, emb_every, ae_w, spawn,
                 spawn_mult, spawn_floor
    WIRES READ: none
    DID IT FIRE: fab.route_calls, fab.hops_taken, fab.halt_mass_train (TRAINING passes only -- the
                 old EMA averaged eval passes in and moved when nothing but HOLDOUT_N changed),
                 fab.halt_clamped, fab.explored_rows, fab.explore_distinct_targets,
                 fab.discovered + fab.discover_targets (DISTINCT recipients; 1 is H14, where
                 `min(range(N), key=use)` returns the FIRST minimum and discovery never credits
                 use, so every novel signature overwrites the same slot), fab.banned_experts,
                 fab.ec_applied, fab.balance_nonzero (THE C2 ALARM: 0 while balance > 0 means the
                 term is multiplying a zero again), fab.div_applied, fab.ind_applied,
                 fab.hopsup_applied, fab.ident_refreshed, fab.holdout_applied, fab.spawned,
                 fab.spawn_declined with fab.spawn_gap and fab.spawn_typ recorded AS A PAIR (the
                 old report printed the gap with no scale to compare it to, ISSUES L29)
    """
    fab = fab.owned_by("FAB")
    raise NotImplementedError(
        "FAB.forward: P4 (fabric) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section FAB.")


def observe(fab: Config, pop, out, *, per_window_loss, domain_id):
    """Book the outcome of one forward pass against the experts that produced it.

    per_window_loss: (B,) cross-entropy per window, from LM.lm_loss. Updates, FOR EVERY WINDOW IN
    THE BATCH and not just row 0:
      - `use`  (fitness)         credited by ROUTING MASS over the computed experts;
      - `uage` (the grace clock) credited by SELECTION over the computed experts.
    THOSE ARE TWO DIFFERENT QUESTIONS and the old tree made them one number (bump_use incremented
    both by 1 for the ARGMAX ONLY, :2044-2051, :2647), so eligibility (uage >= grace) and the
    cull's ranking key (use) were IDENTICAL and the cull removed whichever expert had just crossed
    the grace line (H12), while every non-argmax expert stayed at use-age 0 forever and could never
    be culled at all (H13) -- including the one exploration deliberately inserted so it would get
    traffic.
      - `comp` per expert and the population EMA comp_glob, both at rate comp_ema;
      - `ef`/`es`, the fast/slow error pair whose DIFFERENCE separates an expert that cannot model
        its material from one whose material just changed;
      - `dom_of[e].add(domain_id)`, the affiliation the breadth cap reads.

    THE SPLIT IS A BEHAVIOUR CHANGE WITH NO MEASUREMENT BEHIND IT: grace=48 was set against a clock
    that ticked once per window, and crediting chain_k experts per hop over `hops` hops makes it
    tick up to 32x faster. It belongs on P9's list -- see FOR THE OWNER Q-FAB-5.

    LEVERS READ: comp_ema, err_fast, err_slow
    WIRES READ: none
    DID IT FIRE: fab.observed_windows, fab.experts_with_use (DISTINCT experts ever credited -- the
                 number that reads 43 of 4096 when attribution samples one row in sixteen),
                 fab.experts_past_grace_ever (CUMULATIVE, not the snapshot that made
                 fabric.cull_eligible read ARMED AND INERT, ISSUES M58)
    """
    fab = fab.owned_by("FAB")
    raise NotImplementedError(
        "FAB.observe: P4 (fabric) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section FAB.")


def contribution(fab: Config, pop, *, h, signature, novelty, head, targets, baseline_loss,
                 baseline_logits_fn, step_windows, domain_id, live_domains, candidates):
    """Marginal contribution by leave-one-out: what the system LOSES without each expert.

    On the society arm this is free -- per-expert logits are already separate, so the
    counterfactual is a reweighted sum of tensors in hand. On the looped arm it is one no_grad
    forward per candidate with hold_out set, on the manage cadence.

    TWO THINGS THE OLD ONE GOT WRONG, BOTH CHECKED HERE.
      (1) THE WALK DID NOT ACTUALLY CHANGE: the soc loop ignored ban1 (C3), so the same number was
          written to fab.contrib for every candidate -- and contrib gates BOTH spare rules and
          picks replication parents, so the population's entire selection signal carried zero
          information about which expert matters. `forward` now applies hold_out at every hop and
          this function ASSERTS that the counterfactual logits differ from the baseline for at
          least one candidate. If they do not it records fab.contrib_degenerate and WRITES NOTHING
          to contrib: a signal carrying no information must be ABSENT, not plausible.
      (2) THE COUNTERFACTUAL WAS SCORED THROUGH A DIFFERENT FUNCTION from the loss it was
          subtracted from -- `model.head(_h3)` at :6992 against a `loss` that came from the trained
          per-hop vote blend (ISSUES H11) -- so a fixed offset was added to every contribution and
          contrib's SIGN, the thing both spare rules test, was set by that offset. The baseline is
          now produced by `baseline_logits_fn`, THE SAME CALLABLE that produced `baseline_loss`.

    LEVERS READ: comp_ema, chain_k, society, ens_k
    WIRES READ: none
    DID IT FIRE: fab.contrib_measured, fab.contrib_distinct_values (THE C3 ALARM: 1 distinct value
                 across a pass means the counterfactual removed nothing), fab.contrib_positive /
                 fab.contrib_negative (a population where EVERY measured expert reads load-bearing
                 is the H11 offset, not a healthy population), fab.contrib_degenerate
    """
    fab = fab.owned_by("FAB")
    raise NotImplementedError(
        "FAB.contribution: P4 (fabric) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section FAB.")


def manage(fab: Config, pop, *, step_windows, flush_loss=None):
    """The selection pass: failure cull, utilization cull, three spares, rescue, staged depth.

    ORDER AND GATING, each with its own reason:
      1. FAILURE CULL, AT ANY OCCUPANCY. An expert is failing when BOTH error EMAs sit above the
         population by fail_tol AND the fast one is not above the slow one by shift_tol -- because
         fast >> slow is a SHIFT IN PROGRESS and that expert is adapting. This is the goal-B
         protection and the only cull path that still runs on a small or shrinking population.
      2. UTILIZATION CULL, only behind derive.cull_gate_open(n_live, slots, pressure). THAT
         FUNCTION IS CALLED, NOT RESTATED -- it is already replayed against a 216-case oracle, and
         it is TWO conditions (n_live <= 2 is a FLOOR, not a pressure test), which is why people
         read it as one. The gate's arithmetic is recorded EVERY pass whether it opened or not, so
         a run that was above pressure for most of its length and below it at the end does not
         print "unreachable". At n0=2048 against slots=4096 occupancy is exactly 0.50, which is why
         pressure defaults to 0.45 and not 0.75: at 0.75 the utilization cull, the utilization
         spare and rescue were ALL unreachable while the report showed them on.
      3. RANKING HAPPENS INSIDE THE ELIGIBLE (past-grace) SET and the budget
         int(cull_frac * len(eligible)) is sized on THAT SAME SET -- the old budget was a fraction
         of n_live and removed ten where one was due (523 live / 84 eligible). The
         `max(1, ...)` ratchet is DROPPED: the budget may be zero, and fab.cull_util == 0 under an
         open gate is a legitimate reported outcome rather than something the code refuses to
         allow. The ratchet is the pattern the DomainAssembler documents as having driven a
         population down to a single member.
      4. SPARES: contrib > 0 (load-bearing); comp better than comp_glob (comp_protect); and the
         shift test.
      5. RESCUE: one heavy mutation at mut_big scale and a reset use-clock instead of a deletion,
         once per expert, inside the pressure gate.
      6. maybe_deepen(flush_loss) when the curriculum is on (0 < depth0 < hops). NOTE THE UNIT
         FAULT THIS INHERITS: depth_eps is declared BITS_PER_BYTE and is compared against a raw
         per-flush cross-entropy in NATS PER TOKEN (:2529 against :7317). The repair is owed at the
         COMPARISON, not at the declaration, and the report prints the unit it was compared in.

    LEVERS READ: grace, cull_frac, pressure, slots, comp_protect, comp_ema, err_fast, err_slow,
                 shift_tol, fail_tol, rescue, mut_big, manage_every, depth0, depth_eps,
                 depth_patience, depth_stage_max, hops
    WIRES READ: d_manage_period (recorded on the report beside manage_every, so the WINDOW cadence
                this function is called on and the FLUSH cadence `contribution` is called on are
                visible side by side and a cadence that never coincides reads as a zero rather than
                an absence -- maybe_deepen was NEVER CALLED in a real run at BATCH_W=4)
    DID IT FIRE: fab.cull_fail, fab.cull_util, fab.spared_contrib, fab.spared_comp,
                 fab.spared_shift, fab.rescued (CUMULATIVE, and its gate arms on `rescue > 0 OR the
                 count is nonzero` -- the old row armed on cull_ran, a snapshot reassigned every
                 pass, and discarded a nonzero count, ISSUES M57), fab.deepened, fab.cull_gate
    """
    fab = fab.owned_by("FAB")
    _ = fab.d_manage_period          # WIRE READ HERE -- both cadences reported side by side
    raise NotImplementedError(
        "FAB.manage: P4 (fabric) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section FAB.")


def grow_check(fab: Config, pop, *, flush_loss, step_windows, soft_cap, memory_pressure, signature):
    """The growth trigger and, if it fires, the births. Returns WHAT WAS ACTUALLY CREATED.

    WATCH -> BURST -> RECOVER on a running MAD: a loss `z` robust deviations above the slow EMA is
    an unexpected REGRESSION (new material arriving -- the only signal continual learning has) and
    grows `burst`; a relative improvement below `plateau` after `warmup` is a stall and grows one.
    REGRESSION AND STALL KEEP SEPARATE COOLDOWN CLOCKS: sharing one let a routine stall 772 windows
    earlier suppress an injected regression (:2921-2926) -- the common event silencing the rare one
    goal B depends on. THE STALL TEST IS TWO-SIDED (|improving| < plateau): the old one-sided form
    `improving < s.rel` (:3013) is satisfied by every negative value there is, so a DIVERGING run
    satisfied the stall condition and grew an expert -- capacity added in answer to divergence
    (M36). recover_min and recover_max bound the RECOVER leg.

    memory_pressure, when supplied and grow_on_mem_pressure is set, makes growth eligible; when it
    is None that lever is UNREACHABLE and says so.

    THE CLAMPS RUN INSIDE, BEFORE THE COUNTER. soft_cap (CAP's operating ceiling) and the new_frac
    newborn budget were applied at the CALL SITE after n_regr had been incremented (:7444-7470), so
    a regression whose whole burst was declined still printed as a regression that fired -- and the
    diagnostic written to catch precisely that is gated on n_regr being zero, so it stayed silent
    in the one case where it is most needed. Here the trigger's ASK and the population's DELIVERY
    are two numbers and both are reported.

    EVERY BIRTH: relevance shortlist of parent_k region owners nearest `signature`, parent SAMPLED
    proportional to fitness within it (never argmaxed), refused if it already holds parent_max of
    the last birth_win births, crossover of whole rank slices at rate xover, mutation at `mut` x
    the parent's own std with a mut_big_p chance of the mut_big tail, centroid at `signature` plus
    birth_jitter. replicate=False mints a fresh identity. `spawn` births are counted here too so
    BOTH DOORS ARE BOUND BY THE SAME CAP -- the old spawn_from ignored `grow` and the soft cap, so
    a FAB_GROW=0 run still drifted 3 -> 6 experts. Both birth paths call one claim_slot() that
    clears EVERY book: grow() cleared use/comp/contrib and not ef/es, so a newborn inherited a dead
    expert's error history and could be culled by the failure route for something it never did
    (L30).

    RECEIVES: soft_cap <- CAP.caps().experts, as an argument -- CAP owns the valve, ticks its own
    pin clock and hands FAB a single integer ceiling per flush. memory_pressure <- MEM.census().

    LEVERS READ: grow, burst, z, plateau, warmup, cooldown, recover_min, recover_max, new_frac,
                 replicate, parent_k, parent_max, birth_win, mut, mut_big, mut_big_p, xover,
                 birth_jitter, grow_on_mem_pressure, spawn, slots, n0
    WIRES READ: d_cap_lift_period (reported beside the decline counters, so "0 lifts" is
                distinguishable from "the valve's period is longer than the run" -- round6 measured
                0 vocabulary lifts and it was a clock-unit fault, not the plateau condition; see
                FOR THE OWNER Q-CLOCK-1)
    DID IT FIRE: fab.grow_asked_regression / fab.grow_asked_stall vs fab.grown_regression /
                 fab.grown_stall (ASK and DELIVERY, separately), fab.declined_cap,
                 fab.declined_newfrac, fab.replicated, fab.crossed, fab.random_born,
                 fab.parent_quota_refusals, fab.distinct_parents (1 means the population is one
                 lineage wearing n hats -- which is a DIFFERENT finding from "the experts are
                 interchangeable", and D7 needs the two separated), fab.grow_mem_eligible
    """
    fab = fab.owned_by("FAB")
    _ = fab.d_cap_lift_period        # WIRE READ HERE -- reported beside the decline counters
    raise NotImplementedError(
        "FAB.grow_check: P4 (fabric) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section FAB.")


def own_lr_scale(fab: Config, pop, *, applied_lr):
    """Per-expert learning-rate multipliers on each expert's OWN use clock, or None when off.

    Triangular2 with half-cycle lr_cycle SELECTIONS (not steps -- an expert the router calls often
    cycles fast and one it calls rarely cycles slowly, so the population is never in phase),
    envelope lr_gamma per cycle clamped at lr_amin, ratio to `applied_lr` clamped at lr_maxr, and
    lr_boost applied to the bottom cull_frac of the PAST-GRACE ranking so the boost and the cull
    agree on who is in trouble. The boost budget is sized on the ELIGIBLE count, not on n_live: at
    523 live / 84 eligible "the worst 2%" meant "all of them".

    THE TWO ENDPOINTS ARE WIRES AND THE THIRD NUMBER IS AN ARGUMENT, and that distinction is this
    contract's resolution of a disagreement between two independent specs of this mechanism. The
    envelope is built from the PEAK: :7251 is `_lo = LR * LR_MIN_FRAC` and :7252 is
    `_oa = _lo + (LR - _lo) * (1.0 - _x).clamp_min(0.0) * _amp`, where LR is the frozen peak lever
    -- so d_base_lr and d_lr_min_frac are build-time wires. The RATIO CLAMP compares against "what
    the optimizer is ABOUT to apply", which is a live number and arrives as `applied_lr` from
    OPT.maybe_step's StepOutcome. There is no configuration in which this function reads an
    undefined global: ISSUES H15 was a NameError on `_lrv` whenever LR_SCHED=none and lr_own=1, and
    the crash is now unspellable rather than merely fixed.

    LEVERS READ: lr_own, lr_cycle, lr_gamma, lr_amin, lr_maxr, lr_boost, cull_frac, grace
    WIRES READ: d_base_lr, d_lr_min_frac
    DID IT FIRE: fab.lr_scaled_experts, fab.lr_boosted, fab.lr_cycle_max (a max above ~12 means
                 every survivor is pinned at lr_amin and the schedule is a constant)
    """
    fab = fab.owned_by("FAB")
    _ = (fab.d_base_lr, fab.d_lr_min_frac)   # WIRES READ HERE -- the envelope's two endpoints
    raise NotImplementedError(
        "FAB.own_lr_scale: P4 (fabric) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section FAB.")


def counters(fab: Config, pop):
    """The DID IT FIRE ledger: {name: (fired N | armed-but-0 | unreachable, count, arithmetic)}.

    Every gate above is a declared Gate(name, reads, pred, covers) object, NEVER an inline
    predicate, so an unreachable row prints its own numbers:
    "unreachable (fabric.cull: 1838/4096 = 0.449 < 0.45)".

    LEVERS READ: on, norm_only, society, grow, balance, rescue, comp_protect, explore, discover,
                 spawn, dom_frac, ec_w, div_w, ind_w, hop_sup, hop_vote, depth0, hops, emb_every,
                 lr_own, replicate, xover, halt, cull_frac, pressure, slots, grace, manage_every
    WIRES READ: none
    DID IT FIRE: this call IS the DID IT FIRE surface for the package
    """
    fab = fab.owned_by("FAB")
    raise NotImplementedError(
        "FAB.counters: P4 (fabric) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section FAB.")


def state_dict(fab: Config, pop):
    """Parameters (A, B, q_route, hproj, eemb, edec, halt_key, halt_b, norm, q_entry, nov_proj,
    ctrl), the `cent` BUFFER, every book, the cumulative counter ledger, and the package RNG stream.

    `cent` is a BUFFER and not a plain attribute: as an attribute it was absent from state_dict(),
    so the centroids that ARE the routing function were never saved and generation routed on
    untrained regions. remove()'s swap-with-last renumbers EVERY book from ONE DECLARED LIST -- the
    old remove() renumbered ten of them and left `parent` and `mutscale` stale after the first cull
    (L28), which is also why fab.distinct_parents can be trusted as a D7 reading.

    Re-earned rather than restored: the identity cache, halt_ema, the routing-mix samples.

    LEVERS READ: none
    WIRES READ: none
    DID IT FIRE: fab.state_written
    """
    fab = fab.owned_by("FAB")
    raise NotImplementedError(
        "FAB.state_dict: P4 (fabric) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section FAB.")


def load_state_dict(fab: Config, pop, sd, *, sidecar):
    """Restore the population, REFUSING A GEOMETRY CHANGE BY NAME.

    rank and dk are INNER dimensions and cannot be prefix-widened; slots may widen but never
    narrow; signature_dim must match. Each refusal NAMES the field. The old tree recorded tensors
    failing shape checks with no way to tell whether FAB_EMB_HID, SIG_D or D_MODEL was to blame --
    three widths, one error message (:4678-4684).

    LEVERS READ: slots, n0, rank, dk, emb_hid (compared against the sidecar)
    WIRES READ: none
    DID IT FIRE: fab.resume_widened, fab.resume_refused
    """
    fab = fab.owned_by("FAB")
    raise NotImplementedError(
        "FAB.load_state_dict: P4 (fabric) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section FAB.")


def manage_period(fab: Config):
    """The fabric management cadence, AS units.Windows. Handed to RUN's Cadences.due.

    WHY THIS EXISTS RATHER THAN THE ROOT PASSING cfg.manage_every. Cadences.due states that its
    period "MUST be units.Windows. An int raises; a Flushes raises." -- and Config hands back a bare
    int for all 35 levers that declare a Clock unit (ISSUES H51), so the row that read
    `Cadences.due('fab.manage', FAB.manage_every, clock)` was passing an int into a function whose
    contract refuses one. EVAL and CKPT already had typed accessors (curve_period, save_period);
    FAB, DOM and MEM did not, and their three rows were the only ones that would have raised.

    THE WRAP BELONGS HERE AND NOT AT THE CALL SITE because this is where the kind is DECLARED.
    fabric/levers.py:648 types manage_every Windows; a root that wrote Windows(fab.manage_every)
    would be asserting that kind from outside the package that owns it, in three places, each free
    to be wrong on its own. One accessor per period is the same rule the wires follow.

    IT IS A CONSTRUCTION, NOT A CONVERSION. Windows(int) re-attaches the declared kind; it does not
    cross kinds. The inline arithmetic this project calls a defect is
    `manage_every // batch_w` -- Windows to Flushes, unnamed -- which is derive.flush_period_windows
    and is not this.

    LEVERS READ: manage_every
    WIRES READ: none
    DID IT FIRE: no counter of its own -- Cadences.ledger()['fab.manage'] is the surface, and that
                 is the point of routing every gate through one primitive.
    """
    fab = fab.owned_by("FAB")
    return U.Windows(int(fab.manage_every))
