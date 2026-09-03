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
import dataclasses

import torch
from torch import nn

from spine.lever import Config
from spine import derive as _derive
from spine.gate import Gate, NotBuilt
from spine.init import is_scale as _is_scale
from spine import units as U


class Population:
    """The preallocated pool and the books. GROWTH NEVER REALLOCATES; only n_live moves.

    THE WHOLE POOL EXISTS FROM STEP 0. A, B and cent are (cap, ...) tensors and growth advances
    n_live into rows that are already there, so the optimizer never sees a new parameter and a
    checkpoint's param-group structure survives a run that grew. That is not an optimisation: it is
    what makes OPT's param_group_shape refusal meaningful, because a fabric that minted parameters
    would make every resume of a grown run a shape mismatch.

    B IS ZERO-INIT, SO EVERY EXPERT IS BORN AN IDENTITY. The expert's contribution is B(A(x)), so a
    newborn adds exactly zero to what already works -- which is goal B's requirement at the level of
    a single expert: adding capacity may not disturb what the population has already learned.

    EVERY FOUNDER GETS A BIRTHDAY AND A ZERO USE-CLOCK. The old tree wrote `born` only in grow(), so
    at n0=2048 the entire founding population read age 0 forever and was permanently immune to
    culling -- the cull, which the owner called "semicritical to our evolutionary mechanism", could
    not touch 2048 of 2048 experts.
    """

    __slots__ = ("A", "B", "cent", "n_live", "cap", "depth_now", "born", "use", "uage", "dom_of",
                 "ef", "es", "comp", "contrib", "births", "rescued", "parent", "mutscale",
                 "modules", "counters", "rng", "on", "hop_arm", "gates")

    def __init__(self, *, cap, n0, d_model, rank, signature_dim, device, rng, on, hop_arm,
                depth_now):
        self.cap, self.n_live, self.depth_now = cap, n0, depth_now
        # nn.Parameter, NOT A PLAIN TENSOR, and this is the difference between a society of experts
        # and 4096 frozen zeros. The first version allocated A and B with torch.zeros, so
        # requires_grad was False, `parameters()` did not exist, and the composition root's
        # `_base_parameters` would have appended a warning and trained nothing: every expert's
        # contribution stays EXACTLY ZERO for the whole run while the population grows, culls and
        # replicates around it, and every report line still prints. That is both goals' central
        # mechanism, inert, with the arithmetic intact.
        self.A = nn.Parameter(torch.zeros(cap, d_model, rank, device=device))
        self.B = nn.Parameter(torch.zeros(cap, rank, d_model, device=device))
        # `cent` IS NOT A PARAMETER and must not become one. Centroids are moved by an EMA in
        # ground_update, not by a gradient; making them trainable would put the router's key space
        # under the loss and let the model minimise by moving the keys rather than the experts.
        self.cent = torch.zeros(cap, signature_dim, device=device)
        self.born = [0] * cap            # every founder HAS a birthday; see the class docstring
        self.use = [0] * cap
        self.uage = [0] * cap
        self.dom_of = [-1] * cap
        self.ef = [0.0] * cap
        self.es = [0.0] * cap
        self.comp = [0.0] * cap
        self.contrib = [0.0] * cap
        self.births = 0
        self.rescued = 0
        self.parent = [-1] * cap
        self.mutscale = [1.0] * cap
        self.modules = None
        self.rng = rng
        self.on = on
        self.hop_arm = hop_arm
        self.counters = {}
        self.gates = ()

    def n(self):
        return self.n_live

    def parameters(self):
        """Every trainable tensor this package owns, for the composition root's `base` group.

        THE ROOT ASKS THE OBJECT, IT DOES NOT WALK A MODULE TREE. compose._base_parameters calls
        `getattr(obj, "parameters", None)` on the model, the population and the world and appends a
        WARNING when it is missing -- so a Population without this method does not fail, it trains
        nothing and says so in a line nobody has to read. The expert pool is preallocated, so this
        list is the same length on every step of every run and a checkpoint's param-group structure
        cannot depend on how much the population grew.
        """
        return [self.A, self.B] + list(self.modules.parameters())


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

    THE HOP ARM IS DECLARED HERE AND ONLY ONE OF ITS TWO VALUES IS PORTED (Q-FAB-1, RESOLVED
    2026-09-02: the lever STAYS). `hop_mode="soc"` is the walk this contract ports -- re-route from
    scratch each hop with the current state in the query. `hop_mode="transition"` is the learned
    successor walk (the R matrix, per-expert SRC marks, the `ctrl` summary) and NO BODY FOR IT
    EXISTS IN THIS TREE. So this function REFUSES `transition` at startup, naming the arm, naming
    Q-FAB-1 and naming what porting it would cost -- rather than accepting the value and running
    soc, which is the M24 shape the `choices=` repair exists to end (`s.loop_soc = (_env(
    "CHAIN_ROUTE","soc") == "soc")` at :1843 made every typo the OTHER walk, silently). The lever is
    NOT dropped and its census row is NOT retired: the owner's standing rule is that a mechanism
    kept for future use is kept with a switch, and a drop here would make the port a census
    amendment later. The refusal is what makes "declared but not built" loud instead of silent.

    THE DEPTH0 SENTINEL IS RESOLVED HERE, THE WAY LM.resolve RESOLVES LM_LAYERS==0. depth0 is
    POPULATION STATE (Population.depth_now) that only maybe_deepen ever advances past its start --
    the curriculum's own docstring on `manage` step 6 gates the staged-depth advance on
    "0 < depth0 < hops", which presupposes depth_now already carries depth0's resolved value at
    step 0. The unresolved sentinel was a hardcoded `1`: every configuration, including
    FAB_DEPTH0=0 ("no curriculum", start at the full `hops` budget per fabric/levers.py::FABLevers.depth0),
    started the chain at exactly one hop and depended on the manage_every=500 cadence to reach
    depth0's OWN literal value, let alone `hops` -- while fab.operating_population and every other
    counter kept printing the operator's number. Fixed the M24 way: `depth_now = hops if depth0==0
    else depth0`, so the sentinel and the literal both take effect at step 0 and the curriculum, if
    any, extends FROM there.

    LEVERS READ: on, norm_only, n0, slots, rank, dk, emb_hid, pressure, grow, halt, hop_mode,
                 depth0, hops
    WIRES READ: d_operating_population
    DID IT FIRE: fab.built, fab.n0, fab.cap, fab.operating_population (from
                 derive.operating_population, printed BESIDE the cull gate so the setpoint and the
                 gate are one statement), fab.off, fab.hop_arm (the ported walk, by name -- "soc";
                 the transition arm never reaches a counter because the refusal is at startup),
                 fab.depth_now (the RESOLVED starting depth -- hops when depth0==0, else depth0
                 verbatim -- printed so a report reader never has to re-derive which branch fired),
                 fab.norm_only / fab.grow / fab.halt (the three control arms AS CONFIGURED, so a
                 report reader can see which arm was armed even before forward/grow_check/counters
                 -- the entry points that act on it -- have bodies)
    """
    fab = fab.owned_by("FAB")
    setpoint = fab.d_operating_population    # WIRE READ HERE -- the setpoint, printed with the gate

    arm = str(fab.hop_mode)
    if arm != "soc":
        # REFUSED AT STARTUP, NAMING THE ARM AND WHAT PORTING IT WOULD COST (Q-FAB-1). Accepting
        # the value and running soc is the M24 shape exactly: `s.loop_soc = (_env("CHAIN_ROUTE",
        # "soc") == "soc")` made every typo the OTHER walk, silently. The lever is NOT dropped and
        # its census row is NOT retired -- the owner's standing rule is that a mechanism kept for
        # future use is kept with a switch -- so this refusal is what makes "declared but not
        # built" loud instead of silent.
        raise NotBuilt(
            f"FAB_HOP_MODE={arm!r} is declared and NOT BUILT (Q-FAB-1, resolved 2026-09-02: the "
            f"lever stays). The ported walk is 'soc' -- re-route from scratch each hop with the "
            f"current state in the query. The 'transition' arm is the learned successor walk and "
            f"needs the R matrix, the per-expert SRC marks and the `ctrl` summary, none of which "
            f"exist in this tree. Refused rather than silently running soc.")

    n0, slots = int(fab.n0), int(fab.slots)
    cap = max(n0, slots)
    d_model, rank = int(d_model), int(fab.rank)
    on = bool(fab.on)
    # THREE CONTROL ARMS, RECORDED AT THE ONE SITE THAT SEES THE CONFIG BEFORE ANY GATED BEHAVIOUR
    # RUNS. norm_only/grow/halt are consumed by forward/grow_check/counters (each already names the
    # lever in its own LEVERS READ), so build() does not re-implement their behaviour -- but before
    # this fix build's docstring CLAIMED to read all three while its body read none of them, so
    # FAB_NORM_ONLY=1 built a Population byte-identical to FAB_NORM_ONLY=0 and nothing this function
    # produced said which arm was configured. Reading and recording them here (before forward/manage
    # exist) is what makes the control arm visible on the ledger from step 0 rather than only once
    # the consuming stub grows a body -- and it turns this docstring's own LEVERS READ line from a
    # claim into a true one.
    norm_only, grow, halt = bool(fab.norm_only), bool(fab.grow), bool(fab.halt)

    # THE SENTINEL IS RESOLVED HERE, ONCE, THE WAY LM.resolve RESOLVES LM_LAYERS==0 -- not left for
    # `manage`'s maybe_deepen to discover. depth0=0 is documented as "start at the full `hops`
    # budget (no curriculum)" (fabric/levers.py::FABLevers.depth0); depth0>0 is a literal starting hop count
    # the curriculum extends FROM. Before this fix depth_now was hardcoded to 1 in
    # Population.__init__ regardless of either value, so FAB_DEPTH0=0 ran ONE hop per pass instead
    # of the full budget and FAB_DEPTH0=3 also started at 1 and waited on manage_every=500 to climb
    # -- while fab.operating_population and the rest of the ledger kept printing the operator's
    # configured numbers as if depth_now had used them.
    depth0, hops = int(fab.depth0), int(fab.hops)
    depth_now = hops if depth0 == 0 else depth0

    pop = Population(cap=cap, n0=n0, d_model=d_model, rank=rank,
                     signature_dim=int(signature_dim), device=device, rng=generator,
                     on=on, hop_arm=arm, depth_now=depth_now)

    # A is drawn, B stays ZERO. Every expert is born an identity; see Population's docstring.
    # THE GENERATOR IS CREATED ON THE TARGET DEVICE. torch's in-place random ops require the
    # generator and the tensor to be on the SAME device, so a cpu Generator filling tensors already
    # moved to cuda raises -- on every GPU run, which is every real run, while every CPU smoke test
    # passes. A device mismatch that only fails on the hardware you cannot test on is the worst
    # shape this defect can take.
    gen = torch.Generator(device=device)
    gen.manual_seed(generator.randint(0, 2 ** 31 - 1))
    with torch.no_grad():
        bound = (1.0 / max(1, d_model)) ** 0.5
        pop.A.uniform_(-bound, bound, generator=gen)
        pop.cent.uniform_(-0.1, 0.1, generator=gen)
        pop.cent.div_(pop.cent.norm(dim=-1, keepdim=True).clamp_min(1e-8))

    dk, hid = int(fab.dk), int(fab.emb_hid)
    pop.modules = nn.ModuleDict({
        "eemb": nn.Sequential(nn.Linear(int(signature_dim), hid), nn.Tanh(), nn.Linear(hid, dk)),
        "edec": nn.Sequential(nn.Linear(dk, hid), nn.Tanh(), nn.Linear(hid, int(signature_dim))),
        "q_route": nn.Linear(d_model, dk),
        "hproj": nn.Linear(d_model, d_model),
        "halt_key": nn.Linear(d_model, 1),
    }).to(device)
    with torch.no_grad():
        for name, t in pop.modules.named_parameters():
            if t.dim() >= 2:
                t.uniform_(-0.1, 0.1, generator=gen)
            elif _is_scale(name):
                t.fill_(1.0)
            else:
                t.zero_()

    pop.counters = {
        "fab.built": 1, "fab.n0": n0, "fab.cap": cap,
        # PRINTED BESIDE THE CULL GATE so the setpoint and the gate are ONE statement. A report that
        # prints "0 culls" without the population it was compared against cannot distinguish a
        # healthy population from a gate that never opened.
        "fab.operating_population": int(_derive.operating_population(float(fab.pressure), slots)),
        "fab.off": 0 if on else 1,
        "fab.hop_arm": arm,
        # THE RESOLVED STARTING DEPTH, not the sentinel: a report reader who sees FAB_DEPTH0=0 in
        # the environment and fab.depth_now=4 (== hops) here does not have to re-derive that the 0
        # meant "no curriculum" -- the resolution already happened and its answer is on the ledger.
        "fab.depth_now": depth_now,
        # THE THREE CONTROL ARMS, AS CONFIGURED -- not as exercised; forward/grow_check/counters
        # still decide what each arm DOES. This is what stops FAB_NORM_ONLY=1 from building a
        # Population indistinguishable from FAB_NORM_ONLY=0: a reader of fab.counters can now see
        # the arm was armed even before the entry point that acts on it has a body.
        "fab.norm_only": 1 if norm_only else 0,
        "fab.grow": 1 if grow else 0,
        "fab.halt": 1 if halt else 0,
    }
    # THE TWO GATES WERE INVERTED IN THE FIRST VERSION and the inversion is worth naming, because
    # it is the exact confusion spine/gate.py exists to prevent, committed inside the gate wiring.
    # `fab.on` is the SWITCH: at FAB_ON=0 it did not fail to be reachable, it was reachable and READ
    # FALSE -- the operator turned the fabric off and the report must say the switch is off, not
    # that the switch could not be evaluated. What becomes UNREACHABLE at FAB_ON=0 is every gate
    # BELOW it, `fab.cull_gate` among them: a cull cannot fire in a population whose forward is the
    # identity, so reporting it as FIRED (which the first version did, because the arithmetic is
    # still true) claims a mechanism ran that could not have.
    cull_open = _derive.cull_gate_open(n0, slots, float(fab.pressure))
    pop.gates = (
        Gate("fab.on", on, on, True,
             reason="" if on else "FAB_ON=0: the forward is the identity, so every gate below this "
                                  "one reports UNREACHABLE rather than 'armed but 0'."),
        Gate("fab.cull_gate", cull_open,
             f"{n0}/{slots}={n0 / max(1, slots):.3f}", float(fab.pressure))
        if on else
        Gate("fab.cull_gate", False,
             f"{n0}/{slots}={n0 / max(1, slots):.3f}", float(fab.pressure), reachable=False,
             reason="FAB_ON=0: there is no population to cull. The occupancy arithmetic still "
                    "evaluates, and printing it as FIRED would claim a mechanism ran that the "
                    "switch above had already turned off."),
    )
    # THE WIRE IS READ AND COMPARED, not merely touched: d_operating_population is the same
    # derive.operating_population call the counter above makes, computed by the assembly from the
    # same two levers, so a disagreement here means the coupling table and this package are
    # computing one quantity two ways -- which is the defect the whole spine exists to remove.
    if int(setpoint) != pop.counters["fab.operating_population"]:
        raise ValueError(
            f"FAB.d_operating_population arrived as {int(setpoint)} while this package computes "
            f"{pop.counters['fab.operating_population']} from FAB_PRESSURE and FAB_SLOTS. One "
            f"quantity, two answers.")
    return pop


def forward(fab: Config, pop, *, h, signature, novelty, head=None, targets=None, step_windows,
            domain_id, live_domains, training, hold_out=None):
    """THE routed forward pass. One implementation, both arms.

    h: (B, L, d_model) from LM. signature: (B, sig_d) from SIG.encode -- NEVER a zero placeholder
    and never None; a caller with no signature is a caller that must not route. novelty: (B,)
    surprise from the previous step. head: LM.decode as a plain callable, needed for the per-hop
    vote and for spending HALT mass on the base representation. targets: (B, L) token ids, needed
    only for hop_sup and ind_w; when None those two terms are UNREACHABLE and say so.
    live_domains: DOM's live domain count -- RUNTIME STATE, so an argument, not the frozen wire
    fabric/levers.py::FABLevers.bal_floor calls d_live_domains. `hold_out`: one expert id excluded from EVERY hop's
    routing distribution.

    Depth is min(depth_now, hops, 2 + n_live//2); society=True pins depth at 1 and keeps per-expert
    logits in the return so leave-one-out is a reweighted sum rather than a rerun.

    HOLD_OUT IS APPLIED INSIDE THE HOP LOOP. The old soc branch computed a banned entry
    distribution and then re-routed from scratch every hop WITHOUT it (:2618-2694), so the
    counterfactual walk was bit-identical for every candidate (C3).

    PER-HOP STATES ARE COLLECTED ON THE SOC LOOP, which is what makes hop_sup reachable on the path
    that actually runs. In the old tree `s._hops.append` occurs at EXACTLY ONE site, :2819, inside
    the transition branch -- so under the shipped hop_mode="soc" any hop_sup above zero added
    exactly nothing to the loss and nothing at the config layer said so (M27). It is a one-line
    repair and it is owed HERE, not to the unported arm: at the shipped hop_vote=True the loop
    already forms head(norm(state)) per hop for the vote (:2675-2680), so the per-hop logits deep
    supervision needs are tensors already in hand; at hop_vote=False it costs one `head` call per
    hop. fab.hopsup_applied reads 0 with hop_sup > 0 ONLY if this collection was not written.

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
                 old report printed the gap with no scale to compare it to, ISSUES P1-L29)
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
    tick faster. It belongs on P9's list -- see FOR THE OWNER Q-FAB-5, RESOLVED 2026-09-02: the
    split stands as specified, `grace` stays a Selections lever at its literal 48, and THE LEVEL IS
    NOT GUESSED HERE. Two corrections to the "32x", because they are different quantities and they
    imply different retunes:
      PER EXPERT the ceiling is `hops`, not chain_k * hops -- one expert can be selected at most
      once per hop -- so its OWN clock ticks at most 4x faster at hops=4.
      POPULATION-WIDE the credit issued per window goes from 1 to chain_k * hops, up to 32x.
      AT THE SHIPPED DEFAULTS the multiplier is 8x, not 32x: depth0=1 starts the chain at one hop
      and maybe_deepen sits on the manage_every=500 cadence, which fires at most once in a default
      run of 506-937 windows.
    AND THE NUMBER THAT DECIDES THE RETUNE IS NOT A LEVER, IT IS A READING: at n0=2048 with 8
    credits per window, mean uage per expert after a full default run is 506*8/2048 = 1.98 against
    grace=48. Reaching 48 needs 12,288 windows at depth 1 (3,072 at full depth 4). Under the OLD
    argmax-only clock the same threshold needed 98,304 windows, so the split improves reachability
    by 8-32x and STILL leaves grace short by 6-24x at the shipped run length. Re-expressing grace as
    k * chain_k * hops is refused: a lever computed from two other levers is the L1 defect, and it
    would make one operator edit to chain_k silently move the cull's eligibility threshold through a
    default, where `grep -rn d_` cannot see it.

    LEVERS READ: comp_ema, err_fast, err_slow
    WIRES READ: none
    DID IT FIRE: fab.observed_windows, fab.experts_with_use (DISTINCT experts ever credited -- the
                 number that reads 43 of 4096 when attribution samples one row in sixteen),
                 fab.experts_past_grace_ever (CUMULATIVE, not the snapshot that made
                 fabric.cull_eligible read ARMED AND INERT, ISSUES P1-M58),
                 fab.uage_per_expert_per_pass BESIDE it, because a cumulative zero does not say
                 WHY: "0 experts past grace=48; mean uage 2.0 over 506 windows at n_live=2048" is
                 an unreachable line carrying its own arithmetic, which is what G4 asks for,
                 fab.mass_per_selection (sum(use)/sum(uage) -- the mean routing mass an expert
                 receives per selection, i.e. how many argmax-equivalents one post-split uage tick
                 is worth. THIS IS THE NUMBER THE P9 RETUNE OF `grace` MUST BE SET FROM. It depends
                 on the router and so cannot be computed at build time, which is exactly why grace
                 stays a literal and the retune is a measurement rather than an argument)
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
          per-hop vote blend (ISSUES P1-H11) -- so a fixed offset was added to every contribution and
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
      0. MERGE, BEFORE EITHER CULL (Q-FAB-2, RESOLVED 2026-09-02 -- and READ THE DEFAULT NOTE IN
         fabric/levers.py's merge_dist comment: implementing this turns a mechanism ON at the
         shipped default for the first time, because merge_dist resolves to 0.10 and not to 0).
         Two experts whose centroids are within merge_dist cosine distance in IDENTITY space are
         consolidated instead of one being deleted -- the only merge-rather-than-kill path in
         either population, which is why goal B keeps it.
         THE ARITHMETIC IS IN DELTA-W SPACE AND NOT IN THE FACTORS, and that correction is the
         whole of this ruling. The legacy merge is :3083, `A[a] = 0.5*(A[a]+A[b]);
         B[a] = 0.5*(B[a]+B[b])`. An expert's function is dW = A@B, so averaging the FACTORS gives
         0.25*(A1B1 + A1B2 + A2B1 + A2B2): the intended contribution is HALVED and two cross terms
         corresponding to no learning either expert did are injected. A and B are ZERO-INIT at
         birth with no shared basis (`build` above), so nothing aligns expert a's rank slot 3 with
         expert b's. The census's headline claim -- "both experts' learning survives where culling
         destroys it" -- is not supported by its own arithmetic, and this is the version that
         makes the claim testable: form the best rank-`rank` approximation of dW_a + dW_b by thin
         QR of [A_a | A_b] (d x 2r) and of [B_a | B_b]^T, then an SVD of the 2r x 2r core --
         O(d*r^2), a few thousand flops at d=128, r=8 -- and write it into A[a], B[a]. Rank cannot
         be widened to hold the exact sum (`load_state_dict` below: rank is an INNER dimension),
         so the truncation is forced and the RESIDUAL is the honest report of what it cost.
         WHAT MERGES: use[a] += use[b]; uage[a] += uage[b]; dom_of[a] |= dom_of[b];
         cent[a] = normalize(cent_a + cent_b); then remove(b) through the ONE declared renumbering
         list. NOTHING IN MEM MOVES AND NO MEM ENTRY POINT IS MINTED -- the escalation's premise
         that "memory ownership is expert_id % n_own, so merging changes which owner block holds
         whose entries" does not survive three reads: MEM.read is GLOBAL across owner blocks
         (memory/api.py, read's second paragraph), an entry's owner is its ROW INDEX and at
         d_owner_blocks=64 against slots=4096 sixty-four experts share every block so "the entries
         owned by expert i" is not a set MEM can name (spine/assemble.py's _owner_blocks note), and
         a CULL already does everything a merge would do to MEM and ships -- remove()'s
         swap-with-last renumbers the survivor above the hole, which moves ITS expert_id % 64 too.
         The merge's MEM blast radius is strictly SMALLER than the cull's.
         ELIGIBILITY, AND THE REACHABILITY IT INHERITS. The absorbed expert `b` must be past grace;
         the absorbing expert `a` need not be. Requiring both would mean merging inside the
         eligible set, which sizes nothing differently -- ELIGIBLE IS PAST-GRACE, rule 3 below --
         while merging over the whole live set re-absorbs every replicate/xover birth, which are
         near-duplicates BY CONSTRUCTION (grow_check below), making `replicate` inert. So one
         grace test, on the expert that disappears. THE CONSEQUENCE MUST BE REPORTED AND NOT
         DISCOVERED: at the shipped defaults the past-grace set is provably EMPTY (Q-FAB-5's
         arithmetic -- mean uage 506*8/2048 = 1.98 against grace=48), so `fab.merged` is
         `unreachable` WITH THAT ARITHMETIC, exactly as fabric.cull_eligible is, and NOT
         "armed but 0". A mechanism that is on and cannot fire must say both things.
         THE SECOND GATE COSTS NO LEVER. If dW_a and dW_b are near-parallel the truncation loses
         almost nothing and the merge is honest; if they are not, the residual is large. Report
         fab.merge_residual_p50/p99 rather than minting a threshold -- a second lever would need a
         census row, and Q-MEM-4's discipline (MEASURE BEFORE RETUNING) applies. If the residual
         reads high the operator lowers merge_dist, which is what that lever is for.
         ONE THING INHERITED AND STATED RATHER THAN HIDDEN: the Adam moments on A[a], B[a] are
         stale after an in-place write. `rescue` at 5 below already does this; the merge does not
         make it worse and does not fix it, and P4 must not pretend either.
         WHY THE MERGE IS NOT GATED ON `contribution`, which would be the better signal: FAB.contribution
         is DEFERRED (spine/compose.py) for want of `candidates` and `baseline_logits_fn`, so the
         output-space redundancy reading does not exist at P4. The weight-space residual is the
         available second gate, and this note is where the revisit is recorded.
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

    THREE STATES, NOT TWO, FOR EVERY GATE ON THIS PASS (Q-FAB-5, RESOLVED 2026-09-02).
    `fabric.cull_eligible` reports `unreachable` -- never "armed but 0" -- when the eligible set is
    empty, and it prints its OWN arithmetic to say so: mean uage, grace, n_live and the window
    count, in the form "unreachable (mean uage 2.0 over 506 windows at n_live=2048; grace=48 needs
    12,288)". This CANNOT ride derive.cadences_that_cannot_fire: that audit refuses anything that
    is not units.Windows and `grace` is units.Selections, so the reachability statement is
    FAB-owned by construction. C11 cannot see this family and whoever answers C11 must be told.
    `fab.merged` takes the identical treatment for the identical reason (step 0).

    LEVERS READ: grace, cull_frac, pressure, slots, comp_protect, comp_ema, err_fast, err_slow,
                 shift_tol, fail_tol, rescue, mut_big, manage_every, depth0, depth_eps,
                 depth_patience, depth_stage_max, hops, merge_dist
    WIRES READ: d_manage_period (recorded on the report beside manage_every, so the WINDOW cadence
                this function is called on and the FLUSH cadence `contribution` is called on are
                visible side by side and a cadence that never coincides reads as a zero rather than
                an absence -- maybe_deepen was NEVER CALLED in a real run at BATCH_W=4)
    DID IT FIRE: fab.cull_fail, fab.cull_util, fab.spared_contrib, fab.spared_comp,
                 fab.spared_shift, fab.rescued (CUMULATIVE, and its gate arms on `rescue > 0 OR the
                 count is nonzero` -- the old row armed on cull_ran, a snapshot reassigned every
                 pass, and discarded a nonzero count, ISSUES P1-M57), fab.deepened, fab.cull_gate,
                 fab.cull_rank_spread (max/min `use` INSIDE the eligible set: at ~1 the ranking
                 carries no information and H12 survived the use/uage split in a new dress, because
                 routing concentrates -- the pilot's top expert took 79.5% of traffic -- so the
                 experts that cross grace first are the most-used ones while the cull then ranks
                 that set by `use` ASCENDING. This counter is the falsifier for the repair itself),
                 fab.merged / fab.merge_residual_p50 / fab.merge_residual_p99 /
                 fab.merge_declined_grace / fab.merge_declined_residual (step 0: "no pair was close
                 enough", "no expert was past grace" and "the residual refused every pair" are
                 THREE different outcomes and one number cannot carry them)
    """
    fab = fab.owned_by("FAB")
    _ = fab.d_manage_period          # WIRE READ HERE -- both cadences reported side by side
    raise NotImplementedError(
        "FAB.manage: P4 (fabric) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section FAB.")


def grow_check(fab: Config, pop, *, flush_loss, step_windows, soft_cap, memory_pressure,
               signature, shift_at=None):
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
    IT ARRIVES AS MEM'S VERDICT, NOT AS MEM'S READING (Q-MEM-4, 2026-09-02). This function reads NO
    threshold and must not: pressure_thresh is MEM's and its only reader is MEM.census, so the
    comparison against 0.80 happens inside MEM and what the composition root passes here is already
    the boolean-equivalent answer. Handing over the raw share instead would make fab.grow_mem_eligible
    fire on every flush, which is the same shape as a gate evaluated at a consumer site. It is an
    ARGUMENT and can never be a wire: a store occupancy measured at runtime is not visible to a
    Coupling.compute, which sees only frozen Configs.
    ITS PRESENT STATE IS unreachable AND THE ARITHMETIC IS MEM'S: MEM.read is deferred and
    MEM.maintain's probe has no contexts, so nothing promotes out of probation, no eviction destroys
    a promoted entry, and MEM's pressure is exactly 0.0 for every configuration -- which is why
    grow_on_mem_pressure also ships False. Two named causes, not one.

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

    THE BLACKOUT: A SHIFT WE CAUSED IS NOT NEW MATERIAL (Q-FAB-6, RESOLVED 2026-09-02 --
    SIGNATURE CHANGE, `shift_at=None` added to this entry point and NOT to `manage`). `shift_at` is
    the step of the last SELF-INFLICTED distribution shift -- an epoch resample, a retok, an LR
    restart -- as units.Windows. This function applies its OWN `cooldown` to
    `step_windows - shift_at` and suppresses BOTH growth legs while it is open, which is precisely
    what the old tree did: note_shift(t) sets `blackout` (:2948) and TWO OF ITS THREE consumers are
    :3004 (`if unexpected and t - s.blackout >= s.cool`) and :3012 (`if t - s.last < s.cool or
    t - s.blackout < s.cool: return 0`), both inside PlateauGrowth.step -- which in this rebuild is
    this function. THE THIRD IS :7397, AND THIS DOCSTRING SAID "ONLY TWO" UNTIL 2026-09-03: the loop
    computes `_blackout = (step - fabgrow.blackout) < fabgrow.cool` at its own call site and gates
    the CAPACITY VALVE on it. That one is not this function's -- it is CAP.observe's `blackout`
    boolean, joined by the root from the state this function puts on GrowReport -- and it does not
    move the ruling: both consumers that decide GROWTH are here, and `manage` is cull-and-spare with
    no cooldown to suppress. It is named because a reader who greps `blackout` finds three sites and
    has to know which one this keyword answers. The contract question proposed the keyword on FAB.manage; manage is
    cull-and-spare and has no cooldown to suppress, so the keyword would have been unreachable
    there. Deciding the wrong entry point costs as much as not deciding.
    THE THRESHOLD STAYS IN THE PACKAGE THAT DECLARES IT. The root supplies only the STAMP; FAB
    applies `cooldown`. That is the same rule manage_period below exists to enforce -- "the wrap
    belongs here and not at the call site because this is where the kind is DECLARED" -- and it is
    why this is not a boolean: a boolean would force the caller to apply FAB's cooldown, a foreign
    lever read at the call site that `grep -rn d_` could never index.
    IT IS AN ARGUMENT AND CAN NEVER BE A WIRE. The shift step is MEASURED at runtime and a
    Coupling.compute sees only frozen Configs; docs/04_CONTRACT.md's refused-wires table already
    says so for OPT's `d_shift_at` and the identical reasoning lands here.
    TWO CLOCKS FOR ONE EVENT, ON PURPOSE. OPT.maybe_step's `shift_at` is units.Steps
    (clock.opt_steps, stamped at the E draw row); FAB's cooldown, warmup and recover_min/max are
    all units.Windows and this function takes step_windows. So the root stamps the SAME event into
    TWO typed clocks and passing OPT's to FAB raises UnitError instead of being 16x wrong at
    batch_windows=16. That is the type system doing its job, not a duplication.
    A DEFAULTED ARGUMENT IS INVISIBLE TO K10, so it gets the counter OPT already carries for the
    same hazard (`opt.shift.notifications`, 0 means nobody is supplying shift_at):
    fab.shift_notifications distinguishes "nobody wired it" from "it was wired and never fired",
    and until it is nonzero the blackout is UNREACHABLE rather than armed.
    CAP'S HALF OF THE SAME EVENT IS ANSWERED FROM HERE AND NOT BY A NEW CAP LEVER. CAP.observe
    takes a `blackout` BOOLEAN and CAP declares no blackout-window lever of its own (its seven are
    targets, fab_start, vocab_start, lift, lift_min, pin_windows, stall_band); in the old tree the
    boolean was `(step - fabgrow.blackout) < fabgrow.cool` (:7397), i.e. computed from FAB's
    `cooldown`. GrowReport therefore carries the blackout state -- open/closed and the windows
    remaining -- so the root joins a value FAB computed with FAB's own lever instead of reading a
    foreign lever at the call site or minting a CAP lever that has no census row. That is exactly
    the route ROW_ARGUMENTS_ELSEWHERE["CAP.observe"] already names ("one field on GrowReport and
    one root join"), and naming it here is what stops it being chosen twice, differently.

    RECEIVES: soft_cap <- CAP.caps().experts, as an argument -- CAP owns the valve, ticks its own
    pin clock and hands FAB a single integer ceiling per flush. memory_pressure <- MEM.census().
    shift_at <- the root, stamped at the E draw row (epoch resample), at TOK.mint_burst's retok and
    at OPT's LR restart -- the three sites the old tree called note_shift from (:6515, :7787,
    :7120) -- as units.Windows off clock.step.

    LEVERS READ: grow, burst, z, plateau, warmup, cooldown, recover_min, recover_max, new_frac,
                 replicate, parent_k, parent_max, birth_win, mut, mut_big, mut_big_p, xover,
                 birth_jitter, grow_on_mem_pressure, spawn, slots, n0
    WIRES READ: d_cap_lift_period (reported beside the decline counters, so "0 lifts" is
                distinguishable from "the valve's period is longer than the run" -- round6 measured
                0 vocabulary lifts and it was a clock-unit fault, not the plateau condition.
                IT IS A SECOND VIEW OF A QUESTION CAP OWNS, AND CAP'S IS THE AUTHORITY: the
                normative answer to "0 lifts -- never full, or never plateaued?" is
                CAP.counters' BLOCK-REASON HISTOGRAM, in the package that owns the valve, in the
                unit the valve compares (pin_windows, Windows), beside the pinned high-water mark,
                and it answers by NAMING the refusing condition rather than leaving it to be
                inferred from a cadence. This line prints the period and points at that histogram;
                it must never grow its own verdict about which condition blocked, because a report
                path and an audit path formatting one quantity two ways is what
                spine/wire.py exists to stop. See FOR THE OWNER Q-CLOCK-1, which is MEASURABLE and
                not resolved: this row retires when CAP.counters has a BODY that renders the
                histogram, and not before)
    DID IT FIRE: fab.grow_asked_regression / fab.grow_asked_stall vs fab.grown_regression /
                 fab.grown_stall (ASK and DELIVERY, separately), fab.declined_cap,
                 fab.declined_newfrac, fab.replicated, fab.crossed, fab.random_born,
                 fab.parent_quota_refusals, fab.distinct_parents (1 means the population is one
                 lineage wearing n hats -- which is a DIFFERENT finding from "the experts are
                 interchangeable", and D7 needs the two separated), fab.grow_mem_eligible,
                 fab.shift_notifications (0 means NOBODY IS SUPPLYING shift_at and the blackout is
                 unreachable, not armed -- copied verbatim from opt.shift.notifications because a
                 defaulted keyword is invisible to K10), fab.growth_blackout_suppressed (asks the
                 blackout actually refused, split by leg so a suppressed REGRESSION is not filed
                 under a suppressed stall -- the two keep separate cooldown clocks above for the
                 same reason)
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
    undefined global: ISSUES P1-H15 was a NameError on `_lrv` whenever LR_SCHED=none and lr_own=1, and
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
                 lr_own, replicate, xover, halt, cull_frac, pressure, slots, grace, manage_every,
                 merge_dist, hop_mode
    WIRES READ: none
    DID IT FIRE: this call IS the DID IT FIRE surface for the package
    """
    fab = fab.owned_by("FAB")
    raise NotImplementedError(
        "FAB.counters: P4 (fabric) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section FAB.")


def state_dict(fab: Config, pop):
    """Parameters (A, B, q_route, hproj, eemb, edec, halt_key, halt_b, norm, q_entry, nov_proj),
    the `cent` BUFFER, every book, the cumulative counter ledger, and the package RNG stream.

    `ctrl` IS NOT IN THAT LIST AND THE ABSENCE IS THE STATEMENT. It was, until 2026-09-02, and
    nothing built it: `ctrl` exists only on the transition hop arm (:1907 mints it, :2827 is its
    only read, both inside the transition branch), `build`'s allocation list creates no such
    module, and Q-FAB-1 rules that the arm stays DECLARED and UNPORTED. So the contract promised to
    checkpoint a parameter nothing allocates -- a save-side claim that could only ever be tested by
    a resume. It returns to this list in the same commit that ports the arm, and not before;
    `q_entry` (:2557, :2564) and `nov_proj` (:2554) stay, because both walks use them.

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
    int for all 35 levers that declare a Clock unit (ISSUES P1-H51), so the row that read
    `Cadences.due('fab.manage', FAB.manage_every, clock)` was passing an int into a function whose
    contract refuses one. EVAL and CKPT already had typed accessors (curve_period, save_period);
    FAB, DOM and MEM did not, and their three rows were the only ones that would have raised.

    THE WRAP BELONGS HERE AND NOT AT THE CALL SITE because this is where the kind is DECLARED.
    fabric/levers.py::FABLevers types manage_every Windows; a root that wrote Windows(fab.manage_every)
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
