"""DOM -- the frozen public surface. Signatures only; P4 writes the bodies.

DOM is the self-assembling partition, and its whole claim on existence is goal B. A partition is
not itself a goal; it earns its place because continual learning without catastrophic forgetting
needs a UNIT OF FORGETTING SMALLER THAN THE WHOLE STORE, and `did` is that unit. The domain count
sets the granularity of deletion (at 25 live domains a delete removes 1.6% of memory; at 4 it
removes 30%), and MEM's per-source floor can only protect a source that is separately named.

The sharpest lever in the file is `cull_stale`, because under a phased schedule the absent
corpus's domains go stale BY CONSTRUCTION and the old cull deleted them along with their memory --
200,000 entries ending under a single source id. That is catastrophic forgetting performed by the
manager rather than suffered by the model, and preventing it is this package's job.

THIS PACKAGE NEVER TOUCHES MEMORY. `manage` returns a PLAN; the spine carries it; MEM applies it.
The old tree had the domain manager call mem.reassign_src() and mem.delete_src() directly and read
three of MEM's internals inline at self_organize.py:3688, including a private method.

RECORD TYPES RETURNED (P4 defines them):
  Partition    per-domain cent/reservoir/size/act/born/last/visits/bornb/rad/tokc/comp, plus
               next_id, merged, cur, run, run_sig, pend, sh, nb, radp, comp_glob, collapsed_at,
               the counters and the package RNG stream
  Assignment   did, boundary, spawned, reentered
  Plan         folds, deletions, live, merged, culled, folded, held, spared, emptied
"""
from spine.lever import Config
from spine import units as U


def open_partition(dom: Config, *, sig_dim, vocab_slots, device, rng, restored=None):
    """Create an empty partition, or restore one from a checkpoint blob.

    `rng` is one spine.rng.Rng for the subsystem "domains". Two draws in this package were made
    from the global python `random` -- the reservoir replacement at :3500 and the pooled resample
    in _absorb at :3597 -- which makes draw order a coupling channel no wire declares and one the
    L3 sweep cannot tell from a lever leak.

    `restored` CARRIES EVERYTHING, which is the repair. The old blob saved cent/size/last/next_id/
    merged/cur/visits/bornb/nb/born/act/rad/radp and explicitly reset `wins = {i: [] for i in
    cent}` with the note "sample windows are stream-local". They are not: the reservoir is the
    UNCENSORED SAMPLE the measured radius is estimated from, so throwing it away means every
    restored domain re-enters on the pooled fallback until its next rekey. It also omitted
    comp/comp_glob (competence protection protects nothing after a resume), tokc (the prior
    histogram restarts empty while still being paid for every window) and the adjacent-distance
    history behind the relative shift test (M51). All four are now in the blob.

    THREE CLOCKS CROSS THE BOUNDARY AND THEY DO NOT AGREE ABOUT WHAT "RESTART" MEANS. `grace`
    re-arms on a restored domain, which is the conservative direction and stays. THE BOUNDARY CLOCK
    MUST NOT RESTART: at :4991 it did, and the fold would have swallowed every restored domain that
    had not happened to be re-entered twice since the resume. Same word, opposite consequence; the
    difference is which side of the comparison the reset lands on.

    LEVERS READ: enabled, reservoir, prior_blend
    WIRES READ: d_expert_slots
    DID IT FIRE: part.n_opened, part.n_restored_domains
    """
    dom = dom.owned_by("DOM")
    _ = dom.d_expert_slots       # WIRE READ HERE -- the domain id namespace bound
    raise NotImplementedError(
        "DOM.open_partition: P4 (domains) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section DOM.")


def observe(dom: Config, part, *, signature, sample_window, tokens, now):
    """One window. Detect a boundary, assign it, feed the reservoir, count the visit and the prior.

    Called ONCE PER WINDOW, above the batch early-out -- which is what makes `sustain` a Windows
    clock (`s.run` is incremented once per call, :3483).

    enabled == False returns did=0 for every window and does nothing else. THAT IS NOT A DEGENERACY
    MEM HAS TO DISCOVER: 0 is a real source id that MEM sees, and the report must say "the
    partition is off" rather than leaving the per-source floor to protect exactly one source in
    silence.

    THE BOUNDARY TEST IS ONE OF TWO EXCLUSIVE ARMS. `constant` trips at shift_dist. `relative`
    trips at shift_mult x the shift_q quantile of the last 512 adjacent distances. Neither is a
    boolean any more; an unrecognised value is a startup LeverError, which is the repair for the
    eleven-knob silent-else family (M24). A boundary requires `sustain` consecutive over-threshold
    windows, and THE PENDING SIGNATURES ARE AVERAGED into the assign query -- that smoothing is not
    a debounce, it is what fixed the over-segmentation, because a single raw window sits further
    from its own class mean than the spawn threshold and re-entry reliably spawned.

    ASSIGNMENT IS ONE OF THREE EXCLUSIVE ARMS: `radius` (this domain's own measured acceptance
    radius, with the pooled radius as the bootstrap before its first rekey), `margin` (nearest at
    most `margin` x runner-up), `constant` (spawn_dist alone). The old branch order let radius act
    as a SECOND test inside the relative branch, so DOM_RELATIVE=1 with DOM_RADIUS=1 was a fourth
    configuration nobody named; the enumeration makes `margin` mean margin alone, which is a real
    behavioural change to that arm and not a relabelling.

    At d_expert_slots domains the query is ABSORBED INTO THE NEAREST WITHOUT DRAGGING ITS CENTROID,
    and n_capped counts it -- a forced far match must not pollute the cluster it lands in.

    The reservoir is a TRUE reservoir: replacement with probability reservoir/size, drawn from
    part.rng. The rejected alternative (first-N-only) pinned each centroid to the domain's birth so
    that every rekey undid both the EMA drift and every merge.

    `sample_window` MUST BE THE SAME OBJECT SIG ENCODED, or a rekey does not reproduce the
    signature.

    LEVERS READ: enabled, shift_rule, shift_dist, shift_q, shift_mult, sustain, accept_rule,
                 spawn_dist, margin, reservoir, prior_blend
    WIRES READ: d_expert_slots
    DID IT FIRE: part.n_windows, n_boundaries, n_sustain_partial (runs that started and did not
                 reach sustain -- a detector firing on within-segment variation shows here first),
                 n_created, n_reentered, n_reentered_by_radius, n_reentered_by_margin, n_capped,
                 n_bootstrap_radius (assignments decided on the pooled fallback rather than a
                 measured radius: 0 of 143 domains ever learned one under the censored estimator,
                 so this counter is the evidence that the uncensored one works),
                 n_prior_accumulated
    """
    dom = dom.owned_by("DOM")
    _ = dom.d_expert_slots       # WIRE READ HERE -- the at-cap absorb, and nowhere else
    raise NotImplementedError(
        "DOM.observe: P4 (domains) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section DOM.")


def rekey(dom: Config, part, *, encode):
    """Re-encode every reservoir, recompute every centroid, and re-measure every acceptance radius.

    `encode` is SIG.encode, passed in. THIS IS AN EVENT THE SPINE DELIVERS, NOT A CADENCE THIS
    PACKAGE OWNS: the cadence is MEM's rekey_every and the arm test is SIG's mode == "learned", and
    both were read directly from inside the domain block at self_organize.py:6688-6689 -- two
    foreign reads in one line.

    THE RADIUS IS FREE HERE -- rekey has already encoded the reservoir, so the distances exist
    before the quantile is taken. radius = radius_mult x the radius_q quantile of d(reservoir
    window, own centroid), for domains holding at least four samples; the POOLED radius is the same
    quantile over ALL domains' distances and is what a domain uses before its own first rekey.
    radius_cap then bounds every radius at that multiple of the distance to the nearest OTHER
    centroid, because a radius that absorbs one foreign window measures a larger spread and absorbs
    more (observed reaching 1.24 of a maximum possible 2.0). radius_cap == 0 removes the guard and
    is a real arm. NOTE M32: at radius_cap=2.0 a region reaches TWICE as far as its neighbour's
    centroid, so the guard does not enforce the non-overlap its docstring claims -- 2.0 stays as a
    runaway bound and the claim comes out of the docstring.

    LEVERS READ: radius_q, radius_mult, radius_cap, reservoir
    WIRES READ: none
    DID IT FIRE: part.n_rekey_passes, n_radius_measured, n_radius_capped_voronoi, n_pooled_only
    """
    dom = dom.owned_by("DOM")
    raise NotImplementedError(
        "DOM.rekey: P4 (domains) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section DOM.")


def note_competence(dom: Config, part, *, did, bits):
    """Fold this window's bits/window into the domain's competence EMA and the population's.

    Separate from observe() because the number is only known AFTER the forward pass, later in the
    flush. THE EMA RATE IS THE WIRE d_comp_ema AND NOT AN ARGUMENT: FAB owns the number (the
    fabric's cull and spare rules are where it was first needed), and inventing a lever here would
    put a second answer to "how fast does competence move" in the tree while the report compares
    the two series.

    Competence is the term that lets a rarely-fed domain survive on being GOOD at what it does get
    -- rare-and-stale is exactly what a NICHE domain looks like from a utilization-only vantage
    point, and it is also what a DEAD one looks like.

    LEVERS READ: none -- this is state maintenance whose rate arrives as a wire
    WIRES READ: d_comp_ema
    DID IT FIRE: part.n_competence_updates; comp_glob is None until the first one lands, which is
                 the state in which competence protection cannot fire, and the Gate says so
    """
    dom = dom.owned_by("DOM")
    _ = dom.d_comp_ema           # WIRE READ HERE -- one smoothing rate for both populations
    raise NotImplementedError(
        "DOM.note_competence: P4 (domains) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section DOM.")


def manage(dom: Config, part, *, now, memory_counts, mem_floor_entries):
    """Fold, merge, cull -- on the management cadence -- and RETURN A PLAN for the spine to hand to
    MEM.

    manage == False freezes the population and returns an empty plan. manage_every == 0 means
    NEVER, BEHIND A GUARD AT THIS READ SITE -- the old `step % DOM_MANAGE_EVERY` had no max(1, ...)
    and three DID IT FIRE rows printed "DOM_MANAGE_EVERY=0" as their disarm reason for a value that
    raises ZeroDivisionError on the first flush. A lever cannot check its own reader; this is the
    reader.

    ORDER IS FIXED AND IS THE MECHANISM: fold, then empty-cull, then merge, then the activity cull.

    FOLD. A domain entered on fewer than min_visits SEPARATE occasions, and past recur_horizon
    BOUNDARIES since its birth, is folded into its nearest neighbour -- unless it is further than
    fold_mult x the pooled radius (leave it standing) or there is no pooled radius yet (also leave
    it standing; an unbounded fold collapses the whole population to one domain). This is the
    change that made the population INTENSIVE: 4 live against a truth of 4, and 4 -> 4 -> 4 at
    120/240/480 segments where constants alone gave 64 -> 116 -> 193.

    MERGE. Every pair under merge_dist collapses, the more ACTIVE surviving. THE RESERVOIRS POOL
    and are resampled to `reservoir` -- pooling is what gives the survivor a second segment, which
    is what turns a segment prototype into a domain prototype. `rad` is reset so the next rekey
    re-measures it.

    CULL. A domain is culled only when ALL of: it is in the bottom cull_frac by decayed activity
    (int(cull_frac * n), WITH NO max(1, ...) -- that floor turned "cull at most a tenth" into "cull
    at least one, every pass, forever" and ratcheted a population to a single domain three separate
    times); act < cull_act_min; now - last > cull_stale; now - born >= grace; and neither brake
    holds. BRAKE ONE is cull_respects_mem_floor: memory_counts[did] >= mem_floor_entries refuses
    the cull, because MEM's floor forbids EVICTING those entries and deleting them is the bigger
    action on the weaker test. It self-releases -- once eviction has genuinely drained the domain
    it falls below the floor. BRAKE TWO is the wire d_comp_protect. `act` is then decayed by
    `decay`, once per pass.

    `mem_floor_entries` IS AN ARGUMENT AND CANNOT BE A WIRE: the floor is
    src_share * capacity / live_eligible_sources and the divisor is LIVE STATE (125 sources holding
    entries against 27 live domains on a measured run, a 4.6x swing). domains/levers.py calls it
    d_mem_floor_entries; this contract records that as a deliberate departure with its reason -- a
    wire quietly recomputed at the call site is self_organize.py:3688 under a new name.

    LEVERS READ: manage, manage_every, merge_dist, cull_frac, cull_act_min, cull_stale, decay,
                 grace, cull_respects_mem_floor, fold, min_visits, recur_horizon, fold_mult,
                 reservoir
    WIRES READ: d_comp_protect
    DID IT FIRE: part.n_manage_passes, n_merged, n_culled, n_folded, n_emptied,
                 n_held_by_mem_floor (THE BRAKE THAT WAS MISSING ENTIRELY, and the one goal B
                 depends on), n_spared_by_competence, n_fold_refused_far,
                 n_fold_refused_no_pooled_radius, n_cull_budget_zero, n_grace_skips -- EACH BRAKE
                 HAS ITS OWN COUNTER, because the cull had one and its brakes had none: a run could
                 delete its way to one domain with every guard either off or never reached and the
                 audit would show only "domains.cull 145"
    """
    dom = dom.owned_by("DOM")
    _ = dom.d_comp_protect       # WIRE READ HERE -- brake two, FAB's policy applied to domains
    raise NotImplementedError(
        "DOM.manage: P4 (domains) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section DOM.")


def on_retokenize(dom: Config, part):
    """The tokenizer re-segmented the stream: decay every domain's token histogram by tokc_decay.

    AN EVENT, NOT A CADENCE. This package must not read TOK.retok_every -- the cadence is TOK's and
    a second copy of it here would be a second answer to "when did the vocabulary change".

    The reasoning behind a default below 1.0: the counts are over TOKEN IDS, and a retok makes the
    same text into DIFFERENT ids, so counts banked before it are observations of a DIFFERENT
    distribution rather than stale observations of this one. 1.0 restores cumulative-forever.

    LEVERS READ: tokc_decay, prior_blend
    WIRES READ: none
    DID IT FIRE: part.n_retok_decays
    """
    dom = dom.owned_by("DOM")
    raise NotImplementedError(
        "DOM.on_retokenize: P4 (domains) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section DOM.")


def prior(dom: Config, part, *, did):
    """The per-domain token prior AND the weight it is to be blended at, TOGETHER.

    Returns (probs, weight), or (None, 0.0) when prior_blend == 0, when this domain has no
    histogram, or when the histogram is empty.

    THE WEIGHT TRAVELS WITH THE HISTOGRAM ON PURPOSE. prior_blend was one field doing two jobs -- a
    training-side accounting switch that turns the per-window accumulation on (:6788-6791) and an
    instrument parameter that is the mixing weight at eval (:8147-8192) -- and the two could drift.
    Here `observe` accumulates on exactly the value this call returns, so they cannot.

    LEVERS READ: prior_blend
    WIRES READ: none
    DID IT FIRE: part.n_prior_reads, n_prior_accumulated, n_prior_empty -- the accumulated/read
                 PAIR is the whole finding that the histogram was paid for every window and never
                 read
    """
    dom = dom.owned_by("DOM")
    raise NotImplementedError(
        "DOM.prior: P4 (domains) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section DOM.")


def census(dom: Config, part):
    """Everything the report, FAB and the spine need to know about the partition, in one call.

    Returns live (the list the spine passes to MEM as live_sources), n_live, created, capped,
    merged, culled, folded, held, spared, emptied, boundaries, windows, visits/born/last/radius per
    domain, pooled_radius, comp_glob (what FAB reads for its spare rule -- exporting it HERE is
    what makes that crossing declarable instead of the attribute reach at :6720), collapsed_at (the
    WINDOW at which n_live first fell to 1 in a multi-process run -- recorded and previously never
    surfaced, L36), partition_off, and every part.n_* counter.

    LEVERS READ: enabled, prior_blend
    WIRES READ: none
    DID IT FIRE: this call IS the DID IT FIRE surface for the package
    """
    dom = dom.owned_by("DOM")
    raise NotImplementedError(
        "DOM.census: P4 (domains) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section DOM.")


def state_dict(dom: Config, part):
    """The checkpoint blob: centroids, RESERVOIRS, sizes, activity, births, last-fed, visits, the
    boundary clock and per-domain birth-boundary, merge chains, radii and the pooled radius, the
    TOKEN HISTOGRAMS, the COMPETENCE EMAs and the population baseline, and the ADJACENT-DISTANCE
    HISTORY the relative shift test calibrates on. The four capitalised ones are the omissions that
    each disarmed a live mechanism at the run boundary (M51).

    LEVERS READ: none. Pure read of `part`.
    WIRES READ: none
    DID IT FIRE: part.n_state_dicts
    """
    dom = dom.owned_by("DOM")
    raise NotImplementedError(
        "DOM.state_dict: P4 (domains) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section DOM.")


def manage_period(dom: Config):
    """The domain management cadence, AS units.Windows. Handed to RUN's Cadences.due.

    WHY THIS EXISTS RATHER THAN THE ROOT PASSING cfg.manage_every. Cadences.due states that its
    period "MUST be units.Windows. An int raises; a Flushes raises." -- and Config hands back a bare
    int for all 35 levers that declare a Clock unit (ISSUES H51), so the row that read
    `Cadences.due('dom.manage', FAB.manage_every, clock)` was passing an int into a function whose
    contract refuses one. EVAL and CKPT already had typed accessors (curve_period, save_period);
    FAB, DOM and MEM did not, and their three rows were the only ones that would have raised.

    THE WRAP BELONGS HERE AND NOT AT THE CALL SITE because this is where the kind is DECLARED.
    domains/levers.py types manage_every Windows; a root that wrote Windows(dom.manage_every)
    would be asserting that kind from outside the package that owns it, in three places, each free
    to be wrong on its own. One accessor per period is the same rule the wires follow.

    IT IS A CONSTRUCTION, NOT A CONVERSION. Windows(int) re-attaches the declared kind; it does not
    cross kinds. The inline arithmetic this project calls a defect is
    `manage_every // batch_w` -- Windows to Flushes, unnamed -- which is derive.flush_period_windows
    and is not this.

    LEVERS READ: manage_every
    WIRES READ: none
    DID IT FIRE: no counter of its own -- Cadences.ledger()['dom.manage'] is the surface, and that
                 is the point of routing every gate through one primitive.
    """
    dom = dom.owned_by("DOM")
    return U.Windows(int(dom.manage_every))
