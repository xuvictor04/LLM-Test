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
from torch.nn import functional as F

from spine.lever import Config
from spine import derive as _derive
from spine.gate import Gate, NotBuilt
from spine.init import is_scale as _is_scale
from spine import units as U


@dataclasses.dataclass(frozen=True)
class FabricOut:
    """What ONE routed forward pass produced. The field list is the module docstring's, verbatim.

    `logits` OR `hidden`, and which one is present is the whole statement about who decodes. With a
    `head` and hop_vote (or the society arm) the population VOTES and this record carries the vote's
    logits, so the caller must not re-decode `hidden` -- that is the H11 offset, a loss scored
    through a different function from the one the contribution counterfactual is subtracted from.
    Without a head there is no vote, `logits` is None, and the caller decodes `hidden` itself.

    `weights` is the (B, n_live) routing distribution ACCUMULATED over the hops and renormalised --
    the attribution table `observe`, the breadth cap and MEM's owner argmax all read. `expert_ids`
    is its top-`ens_k`. `per_expert_logits` is (B, k, L, V) and is filled ONLY on the society arm,
    where leave-one-out is a reweighted sum of tensors already in hand rather than a re-walk.

    `aux_loss` is ONE scalar with a graph -- never a float and never a freshly allocated zero. C2 is
    the record of what a graphless zero costs: FAB_BALANCE, BAL_FLOOR and BAL_WARM were read,
    printed and reasoned about for the whole life of the old tree while multiplying `h.new_zeros(())`.

    NO `counters` FIELD, ON PURPOSE. The DID IT FIRE ledger lives on `Population.counters`, which is
    where fabric/api.py::build put it and where fabric/api.py::counters reads it; a second copy on a
    per-pass record is a second source of truth for the same numbers, and the report would then have
    to choose. `gates` is per-pass because a gate's ARITHMETIC is about the pass that evaluated it.
    """
    logits: object = None
    hidden: object = None
    expert_ids: object = None
    weights: object = None
    per_expert_logits: object = None
    aux_loss: object = None
    gates: tuple = ()


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

    # THE LAST FIVE ARE THE RE-EARNED STATE fabric/api.py::state_dict ALREADY NAMES ("Re-earned
    # rather than restored: the identity cache, halt_ema, the routing-mix samples"). They are slots
    # rather than ad-hoc attributes because __slots__ is closed: `pop._kc = ...` raises
    # AttributeError, so a cache invented at the point of use would be a crash on the first routed
    # window rather than a design. ident/ident_step/ident_live are the emb_every cache the old tree
    # carried as _kc/_kstep/_kn (self_organize.py:1938-1953); halt_ema is its _mass_ema.
    __slots__ = ("A", "B", "cent", "n_live", "cap", "depth_now", "born", "use", "uage", "dom_of",
                 "ef", "es", "comp", "contrib", "births", "rescued", "parent", "mutscale",
                 "modules", "counters", "rng", "on", "hop_arm", "gates", "halt_b",
                 "ident", "ident_live", "ident_step", "ident_graph", "halt_ema", "marks")

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
        # ONE SET PER EXPERT, NOT ONE INTEGER. `dom_of` is the AFFILIATION MAP -- which domains this
        # expert has served -- and both of its declared consumers need the CARDINALITY: fabric/api.py::observe
        # specifies the write as `dom_of[e].add(domain_id)`, and the breadth cap in fabric/api.py::forward
        # bans an expert once `len(dom_of[e])` passes dom_frac x live_domains. It was `[-1] * cap`, an
        # int per expert, on which `.add` is an AttributeError and `len` is a TypeError -- so the
        # frozen docstring that specifies the write could not have been implemented against the field
        # it names, and the cap could never have been evaluated. Found while writing `forward`, which
        # is the first entry point that reads it; nothing before this could have noticed, because the
        # only two readers were both stubs.
        self.dom_of = [set() for _ in range(cap)]
        self.ef = [0.0] * cap
        self.es = [0.0] * cap
        self.comp = [0.0] * cap
        self.contrib = [0.0] * cap
        self.births = 0
        self.rescued = 0
        self.parent = [-1] * cap
        self.mutscale = [1.0] * cap
        # THE LEARNED HALT PRIOR, ALLOCATED HERE RATHER THAN IN `modules` BECAUSE nn.ModuleDict
        # CANNOT HOLD A BARE PARAMETER. Shape and initialisation are the frozen old tree's, not a
        # guess: `s.halt_b = nn.Parameter(torch.zeros(1))` at :1733, "prior on halting, learned;
        # 0 = whatever the query says". It sits beside A and B, which is also how state_dict's
        # parameter list reads it -- the list is parameters, not module keys.
        self.halt_b = nn.Parameter(torch.zeros(1, device=device))
        self.modules = None
        self.rng = rng
        self.on = on
        self.hop_arm = hop_arm
        self.counters = {}
        self.gates = ()
        # THE IDENTITY CACHE, RE-EARNED AND NEVER CHECKPOINTED. `ident` holds the DETACHED (K, SRC)
        # pair for `ident_live` experts as of window `ident_step`; `ident_graph` holds the LIVE pair
        # for the current window only. The two are different objects on purpose -- the old tree
        # handed back the live tensors on a later step, whose graph the previous backward had already
        # freed ("Trying to backward through the graph a second time"), and it never fired only
        # because the society path called _ids without a step (self_organize.py:1934-1946).
        self.ident = None
        self.ident_live = -1
        self.ident_step = None
        self.ident_graph = None
        self.halt_ema = None
        # DISTINCT-RECIPIENT SETS, WHICH A COUNTER CANNOT HOLD. `fab.discover_targets` and
        # `fab.explore_distinct_targets` are counts of DISTINCT experts, and 1 is H14 -- discovery's
        # `min(range(N), key=use)` returns the FIRST minimum and discovery never credits use, so
        # every novel signature overwrites one slot forever. A cumulative count of firings cannot
        # say that; the identities have to be remembered, and `counters` holds numbers.
        self.marks = {}

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
        return [self.A, self.B, self.halt_b] + list(self.modules.parameters())


def build(fab: Config, *, d_model, signature_dim, device, generator):
    """Preallocate the pool and found the population.

    cap = max(n0, slots); allocates A (cap, d_model, rank), B (cap, rank, d_model) ZERO-INIT (every
    expert is born an identity, so adding one never disrupts what already works), cent
    (cap, signature_dim), the shared eemb/edec/q_route/hproj/halt_key/norm/nov_proj modules and
    the learned halt prior halt_b. GROWTH NEVER REALLOCATES and the optimizer never sees a new
    parameter; only n_live moves.

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

    THE FOUR NAMES `state_dict` CLAIMED AND THIS FUNCTION DID NOT ALLOCATE, RULED 2026-09-03.
    state_dict's parameter list named eleven tensors; this function created five, so four of them
    were a SAVE-SIDE CLAIM only a resume could ever test -- a name in that list that nothing builds
    is a checkpoint round-trip that silently loses it. Three are now built here and one is dropped
    from the list (see state_dict, which records why `q_entry` is `ctrl`'s twin rather than
    nov_proj's). The three are built to the FROZEN OLD TREE'S OWN CONSTRUCTORS rather than to a
    guess -- `s.norm = nn.LayerNorm(d)` and `s.nov = nn.Linear(1, dk)` at :1907-1908,
    `s.halt_b = nn.Parameter(torch.zeros(1))` at :1733 -- and each is READ ON THE WALK THIS TREE
    PORTS: norm at :2575 (the norm_only ablation), :2677 and :2683 (the soc loop's per-hop vote and
    its residual step); nov at :2361, inside the grounded `entry_logits` this contract keeps, which
    is the very line `forward` cites for the M28 novelty repair; halt_b at :2628, inside
    `if s.loop_soc:`. "forward is still a stub, so none of these can be exercised today" is an
    argument for allocating them at the geometry the old tree used, NOT for leaving the claim
    outstanding: A, B and the other five modules are unexercised for exactly the same reason, and
    the alternative -- raising spine/gate.py::NotBuilt at a point of use that does not exist yet --
    would refuse a mechanism this tree has not declared unported, which is the one thing NotBuilt
    must not be spent on.

    FIVE OF THE SEVEN SHARED MODULES WERE ALLOCATED AT WIDTHS NO PATH COULD USE, CORRECTED
    2026-09-04 WHILE WRITING `forward`. This is the same family as the four names state_dict claimed
    and nothing built, one level down: there the NAME was missing, here the name was present and its
    GEOMETRY belonged to a different design. Nothing could have caught it, because a width is only
    falsified by a tensor flowing through it and `forward` was the only function that would have made
    one flow. What was there, what it is now, and the authority for each:
      eemb      Linear(SIG.d -> emb_hid -> dk)          ->  Linear(2*d_model*rank -> emb_hid -> dk)
      edec      Linear(dk -> emb_hid -> SIG.d)          ->  Linear(dk -> emb_hid -> 2*d_model*rank)
      q_route   Linear(d_model -> dk)                   ->  Linear(SIG.d -> dk)
      hproj     Linear(d_model -> d_model)              ->  Linear(d_model -> dk)
      halt_key  Linear(d_model -> 1, bias=False)        ->  Linear(dk -> 1, bias=False)
    The authority is this tree's own declarations before it is the old tree's constructors.
    fabric/levers.py::FABLevers.rank declares 2*d*r to be "the size of the embedder's input";
    FABLevers.dk declares dk to be "the shared query projection's OUTPUT and every per-expert K
    vector"; FABLevers.ae_w declares the round trip edec(eemb(W)) to be "weights -> identity ->
    weights"; FABLevers.spawn declares spawn to "decode the router's own query into a new expert",
    which is edec applied to a dk query and can only land in weight space. The old tree agrees line
    for line (self_organize.py:1673 `nn.Linear(sig_d, dk)`, :1680 `nn.Linear(d, dk)`, :1698 and
    :1707 the 2*d*r ends of the pair, :1724 `halt_key = nn.Parameter(torch.randn(dk) * 0.1)`).
    HOW BADLY EACH ONE FAILED, because "wrong width" understates two of them. q_route was a CRASH:
    at the shipped SIG_D=64 and LM_WIDTH=128 the first `q_route(signature)` raises, so no routed
    window could ever have run. eemb and edec were WORSE THAN A CRASH -- SIG.d=64 against
    2*d_model*rank=2048 is a legal shape for neither end, but had the two happened to match (they do
    at d_model*rank=32) the population's routing identity would have been a projection of the
    SIGNATURE, i.e. of the input, and every expert would have embedded to a point that had nothing to
    do with the expert. Identity would have stopped being a function of function, which is the one
    property the whole identity design exists to buy, and every downstream reading -- specialisation,
    nearest-neighbour spacing, the spawn test -- would have measured the signature encoder.
    THE PARAMETER COUNT MOVES AND THAT IS NOT A COST TO HIDE: at the shipped defaults eemb and edec
    go from 64->128->32 and 32->128->64 to 2048->128->32 and 32->128->2048, so the package's shared
    modules grow by about 0.5M parameters. That is the size the design specifies; the smaller number
    was not a saving, it was a different network.

    HALT'S PRIOR IS ONE SCALAR AND WAS NEARLY TWO. In the old tree `halt_key` is a bare (dk,)
    Parameter with no bias of its own (:1724) and the learned prior is added beside it
    (`_hl + s.halt_b`, :2442). This tree had already re-specified halt_key as nn.Linear(d_model, 1),
    whose OWN bias occupies precisely halt_b's additive position -- so allocating halt_b beside it
    would have put two learned scalars in one place, one of which must be dead: the armed-but-inert
    shape this package's own history is made of. halt_key is therefore allocated `bias=False` and
    the prior carries the name the contract gives it. The parameter count is unchanged.

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

    dk, hid, sig_d = int(fab.dk), int(fab.emb_hid), int(signature_dim)
    # THE IDENTITY EMBEDDER'S INPUT IS THE EXPERT'S WHOLE ADAPTER, 2*d*r NUMBERS, NOT A SIGNATURE.
    # fabric/levers.py::FABLevers.rank says it in as many words -- "also ... the size of the
    # embedder's input (2*d*r)" -- and it is the premise of the entire identity design: routing
    # identity is DERIVED FROM WHAT AN EXPERT IS, so a replicated child is near its parent in
    # routing space because its WEIGHTS are near, a mutation moves its own key, and a culled slot
    # cannot leave a stale identity behind (self_organize.py:1689-1699). See the FIVE GEOMETRIES
    # paragraph in this function's docstring for what the four wrong widths were and why every one
    # of them was invisible until `forward` existed.
    ident_in = 2 * d_model * rank
    pop.modules = nn.ModuleDict({
        # WEIGHTS -> IDENTITY. Output is dk, not the old tree's 2*dk: the second half was SRC, the
        # per-expert outgoing mark that only the TRANSITION walk reads (self_organize.py:1683-1688,
        # read at :2814-2830), and this build REFUSES that arm at startup under Q-FAB-1. Emitting a
        # dk-wide block no live path reads would be dk columns of a trained projection receiving
        # exactly zero gradient while AdamW decays them every step -- the armed-but-inert shape this
        # package's own history is made of. The head widens to 2*dk in the commit that ports the arm.
        "eemb": nn.Sequential(nn.Linear(ident_in, hid), nn.Tanh(), nn.Linear(hid, dk)),
        # IDENTITY -> WEIGHTS, the inverse, and what makes spawn-by-specification possible at all:
        # the router's query IS a point in identity space, so `edec(query)` is the expert that was
        # asked for. fabric/levers.py::FABLevers.ae_w names this round trip "weights -> identity ->
        # weights"; an edec landing in signature space could not close it.
        "edec": nn.Sequential(nn.Linear(dk, hid), nn.Tanh(), nn.Linear(hid, ident_in)),
        # THE ROUTER'S QUERY IS BUILT FROM THE SIGNATURE, so its input width is SIG.d and not
        # LM.width. fabric/api.py::forward's first line of prose says the signature is "NEVER a zero
        # placeholder and never None; a caller with no signature is a caller that must not route",
        # and at the shipped SIG_D=64 against LM_WIDTH=128 the previous width made `q_route(signature)`
        # a shape error on the first routed window.
        "q_route": nn.Linear(sig_d, dk),
        # THE CURRENT STATE, PROJECTED INTO THE QUERY'S OWN SPACE -- it is summed with q_route's
        # output (self_organize.py:2677), so it must land in dk. This is the term that makes hop 2 a
        # question about where the computation IS rather than a fixed function of hop 1; the old
        # tree measured I(domain; (hop0,hop1)) equal to I(domain; hop0) to three decimals without it.
        "hproj": nn.Linear(d_model, dk),
        # HALT COMPETES IN IDENTITY SPACE, dk WIDE. Its logit is the cosine of the SAME query the
        # experts are scored by against halt_key, over the same route_t -- which is the whole reason
        # fabric/levers.py::FABLevers.route_t can be described as one temperature for three
        # operators. A halt_key reading d_model would be scored against a vector the query never
        # touches. bias=False, AND THE HALT PRIOR IS `halt_b` INSTEAD -- see the ruling paragraph
        # above: a biased halt_key plus a halt_b would be two learned scalars in one additive
        # position, one of which must be dead. The parameter count is unchanged either way.
        "halt_key": nn.Linear(dk, 1, bias=False),
        # LayerNorm over d_model, per :1908 `s.norm = nn.LayerNorm(d)`. Read on every arm: the
        # norm_only ablation (:2575), the soc loop's per-hop vote and residual step (:2677, :2683),
        # and the unported transition walk (:2781, :2814).
        "norm": nn.LayerNorm(d_model),
        # The (B,) novelty scalar projected INTO THE ROUTING QUERY, per :1907 `s.nov =
        # nn.Linear(1, dk)`. `forward` cites :2361 -- where the old tree summed it into the LOGITS
        # and it cancelled in the softmax -- as the M28 defect; the repair needs this module, so
        # the name is here rather than waiting for the body that will call it.
        "nov_proj": nn.Linear(1, dk),
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


# ==================================================================================================
# PRIVATE HELPERS FOR THE ROUTED FORWARD PASS.
#
# Underscore-prefixed so they are not entry points -- the entry-point census in
# tests/test_contract.py counts public top-level names in every src/*/api.py, and a helper that
# joins that surface is a frozen signature nobody meant to freeze. NONE OF THEM TAKES A Config:
# tests/test_ownership.py::check_o9_one_config_per_signature requires every Config-annotated
# signature to assert its owner, and an owner assertion repeated in nine helpers is nine chances to
# write the wrong prefix. `forward` asserts once and hands plain values down.
#
# NONE OF THEM READS A CLOCK LEVER OFF THE Config EITHER. Every window count arrives here as a bare
# int the caller has already put through units.Windows, which is what keeps the arithmetic below out
# of check_o11_no_unnamed_clock_arithmetic's reach honestly rather than by spelling: these are
# SAME-KIND ratios (windows over windows, dimensionless), not the cross-kind conversions
# spine/units.py::Clock.convert requires a named function in spine.derive for.
# ==================================================================================================

_FLOOR = 1e-9                     # only ever a denominator guard, never a rate
_NEG = -1e4                       # the old tree's own pinned "halt cannot win" logit (:2628)


def _var_cov(z):
    """VICReg variance + decorrelation over a batch of identity embeddings.

    ON A MEASURED FAILURE, not a precaution: the population's typical nearest-neighbour distance in
    identity space was measured at 0.000 without it -- every expert embedding to the same point
    (self_organize.py:1961-1972). A collapsed identity space makes the spawn test fire on every query
    (nothing is ever far from anything), makes routing keys interchangeable, and reads as
    specialisation exactly 0.000. The inputs make it near-inevitable: replicated children have
    similar weights by construction, and a net with no variance pressure maps similar inputs to one
    point.

    Written here rather than imported from world_model.py, which is the frozen old tree's own copy:
    O10 confines this package's imports to the spine's permitted set plus torch, and a package that
    reaches outside src/ for a loss term has a dependency `grep -rn d_` cannot index.
    """
    z = z - z.mean(0)
    std = torch.sqrt(z.var(0) + 1e-4)
    var_loss = F.relu(1.0 - std).mean()
    n, d = z.shape
    if n < 2:
        # ONE EXPERT HAS NO COVARIANCE, and (z.T @ z)/(n-1) would divide by zero. The variance half
        # still means something, so the term is not skipped -- it is halved, and the report says so
        # through fab.ident_refreshed rather than through a silent NaN.
        return var_loss, z.new_zeros(())
    cov = (z.t() @ z) / (n - 1)
    off = cov - torch.diag_embed(torch.diagonal(cov))
    return var_loss, (off ** 2).sum() / d


def _warm_up(step_n, warm_n):
    """0 -> 1 over `warm_n` windows. Both arguments are WINDOW counts; the result is dimensionless.

    `ponder` charges for routed depth, and charging from window 0 is how the router writes the
    population off before its experts can be worth using -- the old tree's own report reads node mass
    near zero (self_organize.py:9081). The anneal is the answer to that, and it is a ratio of two
    quantities of the SAME kind, which is why it is not a spine.derive conversion.
    """
    return min(1.0, step_n / max(1, warm_n))


def _decay_to_floor(step_n, warm_n, floor):
    """1 -> `floor` over `warm_n` windows, and never below it. Same-kind ratio, as above.

    THE FLOOR IS THE MECHANISM, NOT A ROUNDING GUARD. Decaying the load-balance pressure to exactly
    zero leaves nothing pushing routing mass outward, and an expert the router has stopped choosing
    has no route back: no traffic -> no gradient -> no improvement -> still no traffic, and under the
    use clock it is frozen at its use-age so the cull cannot reach it either.
    """
    return max(floor, 1.0 - step_n / max(1, warm_n))


def _identities(pop, n, step_n, emb_every_n):
    """(K, refreshed) -- the n live experts' routing keys, EMBEDDED FROM THEIR OWN WEIGHTS.

    THIS IS THE ONLY GRADIENT CHANNEL THAT REACHES EVERY EXPERT. Routing computes chain_k of n, so
    all but k experts get nothing from the mixture; eemb reads ALL n adapters, so a refresh puts
    every live A and B on the graph. That is why emb_every ships at 1 and why a stale cache is not a
    cost saving -- it throttles the one channel the rest of the population ever sees.

    TWO KINDS OF REUSE, AND CONFLATING THEM WAS THE OLD TREE'S BUG (self_organize.py:1932-1946).
    SAME WINDOW: hand back the LIVE tensors, because `forward` reads identities more than once per
    window (the entry router, then every hop) and two consumers on two graphs means the second one
    silently trains nothing. LATER WINDOW, inside the cadence: hand back a DETACHED copy, because
    the previous backward already freed that graph -- returning the live tensors is "Trying to
    backward through the graph a second time", which never fired in the old tree only because the
    society path called this without a step at all.
    """
    if (pop.ident_step is not None and pop.ident_step == step_n and pop.ident_live == n
            and pop.ident_graph is not None):
        return pop.ident_graph, False
    if (pop.ident is not None and pop.ident_live == n and pop.ident_step is not None
            and step_n - pop.ident_step < emb_every_n):
        pop.ident_graph = None                  # release the old graph; it can never be handed back
        return pop.ident, False
    weights = torch.cat([pop.A[:n].reshape(n, -1), pop.B[:n].reshape(n, -1)], -1)
    keys = pop.modules["eemb"](weights)
    pop.ident_graph = keys
    pop.ident, pop.ident_live, pop.ident_step = keys.detach(), n, step_n
    return keys, True


def _ae_loss(pop, n, emb_var):
    """The weights -> identity -> weights round trip, plus the anti-collapse term.

    edec is used at BIRTH, which is rare, so its gradient signal from spawn alone is far too sparse
    to shape it -- this term is what keeps the decoder an actual inverse of the embedder, and without
    it a spawned expert is noise wearing the requested key.

    IT IS ALSO A GRADIENT ROUTE INTO A AND B THAT DOES NOT PASS THROUGH THEIR PRODUCT, which is
    exactly what INV-R2-1 says a probe of "does the fabric train" needs: `A @ B` is identically zero
    at initialisation, so dL/dA through the mixture is zero on the first step, while dL/dA and dL/dB
    through this reconstruction are not.
    """
    weights = torch.cat([pop.A[:n].reshape(n, -1), pop.B[:n].reshape(n, -1)], -1)
    emb = pop.modules["eemb"](weights)
    var, cov = _var_cov(emb)
    return F.mse_loss(pop.modules["edec"](emb), weights) + emb_var * (var + cov)


def _route_query(pop, signature, novelty, state=None):
    """The router's query in identity space: q_route(signature) + nov_proj(novelty) [+ hproj(state)].

    NOVELTY ENTERS THE QUERY, WHICH IS THE M28 REPAIR AND THE WHOLE POINT OF nov_proj EXISTING.
    `logits + s.nov(nov[:,None]).sum(-1, keepdim=True)` (self_organize.py:2361) collapses the term to
    a per-ROW scalar broadcast identically across all N expert logits, so it CANCELS in the softmax
    over experts and survives only as a shift against HALT -- while the class docstring describes it
    as biasing expert selection. Added to the query instead, a surprising window asks a different
    question of the population, which is what the mechanism was always described as doing.

    `state` is hproj(h.mean(1)), and it is what makes hop 2 a question rather than a fixed function
    of hop 1: without it the query is the input signature, identical at every hop, and the old tree
    measured I(domain; (hop0,hop1)) equal to I(domain; hop0) to three decimals on every seed.
    """
    query = pop.modules["q_route"](signature) + pop.modules["nov_proj"](novelty[:, None])
    if state is not None:
        query = query + pop.modules["hproj"](state)
    return query


def _entry_logits(pop, *, query, signature, keys, n, region_w, route_learn, route_t, ec_w,
                  ban, hold_out):
    """Score the n live experts for this window. ONE implementation, called by every hop.

    TWO TERMS, BOTH COSINES ON ONE SCALE. The signature-region term asks "whose material is this",
    against centroids an EMA moves toward what each expert actually served; the learned term asks
    "which expert do I want", by matching the router's query against identities derived from the
    experts' own weights. Both are divided by route_t, which is what makes
    fabric/levers.py::FABLevers.route_t describable as one temperature for three operators -- the raw
    dot the old tree kept as an option let an expert with a large key norm win every input with any
    positive projection, regardless of its region (M29).

    Returns (logits, ec_applied, banned).
    """
    temp = max(1e-3, route_t)
    cent = F.normalize(pop.cent[:n], dim=-1)
    logits = region_w * ((F.normalize(signature, dim=-1) @ cent.t()) / temp)
    if route_learn and keys is not None:
        logits = logits + (F.normalize(query, dim=-1) @ F.normalize(keys, dim=-1).t()) / temp
    ec_applied = False
    if ec_w > 0.0 and n > 1:
        # ALLOCATION BY CONSTRUCTION RATHER THAN BY LOSS PRESSURE: an expert below its fair share of
        # recent assignments is scored up in proportion to how far below. Literal expert-choice
        # routing is not implementable at this ratio -- BATCH_W windows against thousands of experts
        # gives c well under one item per expert -- so what transfers is the property, not the rule.
        total = float(sum(pop.use[:n]))
        if total > 0:
            fair = total / n
            deficit = torch.tensor([max(0.0, fair - float(u)) / fair for u in pop.use[:n]],
                                   device=logits.device, dtype=logits.dtype)
            logits = logits + ec_w * deficit[None]
            ec_applied = True
    banned = 0
    if ban is not None:
        # NEVER BAN EVERY EXPERT. A row of all -inf is NaN after the softmax, not an empty choice,
        # and the breadth cap is a preference over a population rather than a veto on having one.
        if int(ban.sum()) < n:
            logits = logits.masked_fill(ban.to(logits.device)[None], float("-inf"))
            banned = int(ban.sum())
    if hold_out is not None and n > 1:
        logits = logits.clone()
        logits[:, int(hold_out)] = float("-inf")
    return logits, ec_applied, banned


def _halt_logit(pop, query, route_t, halt_on, rows, device, dtype):
    """HALT's column, on the same scale as the experts it competes with.

    HALT owns no region, so its logit comes from the SAME place the learned expert term does -- the
    router's query in identity space, matched against halt_key -- plus the learned prior halt_b. At
    halt_on=False it is PINNED at a constant rather than derived, which is the old tree's own
    halt-off form (self_organize.py:2628) and the reason `q_entry` could be dropped: a derived
    halt column on the halt-off arm is a never-trained random projection perturbing a centroid EMA.
    """
    if not halt_on:
        return torch.full((rows, 1), _NEG, device=device, dtype=dtype)
    key = F.normalize(pop.modules["halt_key"].weight[0], dim=-1)
    return (F.normalize(query, dim=-1) @ key[:, None]) / max(1e-3, route_t) + pop.halt_b


def _ground_update(pop, signature, weights, n, cent_topk, cent_ema, discover):
    """An expert's REGION moves toward the signatures it actually served. Returns (discovered, slot).

    EVERY EXPERT THAT SERVED THIS SIGNATURE MOVES, in proportion to how much it served. Updating the
    argmax winner only makes discovery structurally impossible: the winner drifts toward every region
    it wins and becomes closer still, while every other centroid stays frozen at its initialisation,
    so a newcomer cannot win because its region never moved and its region never moves because it
    never wins.

    VECTORISED, WHICH IS A FIX AND NOT A STYLE CHOICE. The old tree wrote each of the k centroids back
    with a `.cpu()` and a `float()`, forcing a device synchronisation per expert per hop -- dozens of
    syncs per window for a slow-moving EMA (M35).

    NOT A PARAMETER AND NEVER UNDER THE LOSS: `cent` is moved by this EMA alone. Making it trainable
    would put the router's key space under the objective and let the model minimise by moving the
    keys rather than the experts.
    """
    discovered, slot = 0, -1
    with torch.no_grad():
        mass = weights.mean(0)
        topm = max(1, min(int(cent_topk), n))
        share_v, idx = mass.topk(topm)
        target = F.normalize(signature, dim=-1).mean(0)
        share = share_v / share_v.sum().clamp_min(_FLOOR)
        rate = (float(cent_ema) * share)[:, None]
        pop.cent[idx] = F.normalize((1.0 - rate) * pop.cent[idx] + rate * target[None, :], dim=-1)
        if discover > 0 and n > 1:
            # NOVELTY -> DISCOVERY. A signature far from EVERY centroid is material nothing owns.
            # It goes to the LEAST-USED expert rather than the nearest incumbent: that is the
            # mechanism by which new material recruits new capacity instead of being absorbed by
            # whoever is already largest. H14 IS LIVE AND THE COUNTER IS WHERE IT SHOWS: `min` returns
            # the FIRST minimum and discovery never credits `use`, so with a tied use table every
            # novel signature overwrites one slot. fab.discover_targets is the falsifier.
            best = float((F.normalize(pop.cent[:n], dim=-1) @ target).max())
            if 1.0 - best > discover:
                slot = min(range(n), key=lambda i: pop.use[i])
                pop.cent[slot] = F.normalize(
                    0.5 * pop.cent[slot] + 0.5 * target, dim=-1)
                discovered = 1
    return discovered, slot


def _breadth_ban(pop, n, domain_id, live_domains, dom_frac, dom_min):
    """The breadth cap, as a bool mask over the live population. Returns (mask, limit, reason).

    An expert already serving more than its share of the live domain population is masked out of
    routing FOR DOMAINS IT DOES NOT ALREADY HOLD. Checked at ROUTING time rather than fixed up
    afterwards: an expert that cannot win this domain never accumulates mass on it, so the cap
    shapes the population instead of reporting on it.

    IT NEVER REACHED THE CHAINING PATH IN THE OLD TREE -- computed in the society branch of the
    training loop and simply not passed to forward() -- so on the DEFAULT path the cap was inert and
    a handful of experts absorbed everything (top expert 79.5% of traffic in the last pilot).

    `reason` IS NON-EMPTY EXACTLY WHEN THE CAP CANNOT FIRE, and that is a third state rather than a
    zero: `dom_of` is written by fabric/api.py::observe and by nothing else, so until that entry
    point has a body every expert's affiliation set is empty, `len(...) >= lim` is false for all of
    them, and "0 banned" would be indistinguishable from a cap that ran and found nothing over its
    share.
    """
    if dom_frac <= 0.0:
        return None, 0, "FAB_DOM_FRAC=0: the breadth cap is switched off."
    limit = max(int(dom_min), int(dom_frac * max(1, int(live_domains))))
    affiliated = sum(1 for e in range(n) if pop.dom_of[e])
    if affiliated == 0:
        return None, limit, ("no expert holds an affiliation yet: FAB.observe is the only writer of "
                             "dom_of and it is a stub, so the cap has nothing to measure breadth "
                             "against.")
    over = [e for e in range(n)
            if len(pop.dom_of[e]) >= limit and int(domain_id) not in pop.dom_of[e]]
    if not over:
        return None, limit, ""
    mask = torch.zeros(n, dtype=torch.bool)
    mask[torch.tensor(over, dtype=torch.long)] = True
    return mask, limit, ""


def _explore_swap(pop, idx, val, weights, n, k, explore):
    """Swap the lowest-ranked computed slot of some rows for a cold expert. Returns (rows, targets).

    THE ONLY THING BETWEEN THE UTILIZATION CULL AND A SELF-FULFILLING RANKING: an expert that is
    never selected is never trained and is then culled for not being trained.

    M25 IS REPAIRED HERE. `sorted(range(N), key=use)[:max(8, N//16)]` is a STABLE sort over a mostly
    tied key, so the cold set is the lowest-INDEXED zero-use experts -- a fixed prefix of the slot
    array rather than a sample of the population, and at a fresh population every use is 0 so the
    prefix is literally slots 0..127. The tie is resolved by DRAWING instead: the cold set is every
    expert at or below the cut, and the choice within it is one draw on the fabric's own stream. That
    is one draw per explored row rather than a per-expert sort key, so it also costs less.
    """
    if not (explore > 0.0 and k >= 2 and n > k):
        return idx, val, 0, ()
    order = sorted(range(n), key=lambda i: pop.use[i])
    cut = pop.use[order[min(len(order) - 1, max(8, n // 16))]]
    cold = [i for i in range(n) if pop.use[i] <= cut]
    rows = [r for r in range(idx.size(0)) if pop.rng.random() < explore]
    if not (cold and rows):
        return idx, val, 0, ()
    idx = idx.clone()
    val = val.clone()
    targets = []
    for r in rows:
        pick = int(pop.rng.choice(cold))
        idx[r, -1] = pick
        val[r, -1] = weights[r, pick]
        targets.append(pick)
    return idx, val, len(rows), tuple(targets)


def _spawn_check(pop, query, spawn_mult, spawn_floor, step_n):
    """Spawn-by-specification: decode the router's own query into a new expert. Returns a report.

    `(slot, gap, typ)` -- slot is None when the test declined. THE TEST IS RELATIVE, and that is the
    repair the old tree already made and this port keeps: `1 - near > 0.45` compares the query to the
    NEAREST of n identities, and that distance shrinks as n grows, so an absolute threshold makes
    spawning impossible exactly when the population is large (measured: 4096 experts, ZERO spawns in
    a full pilot). Compared instead against how tightly the population ALREADY packs, the threshold
    tightens on its own as identity space fills in. `spawn_floor` is what keeps the relative test
    safe when the identity space has collapsed and every query is infinitely far in relative terms.

    IT RUNS BEFORE ANY GRAPH IS BUILT, WHICH IS NOT A PREFERENCE. A birth writes into pop.A and
    pop.B in place; pop.A is ONE tensor, so an in-place write after the forward graph has read it
    bumps its version counter and the next backward raises "a variable needed for gradient
    computation has been modified by an inplace operation". The old tree called spawn_from from the
    loop immediately BEFORE the fabric call (self_organize.py:6836-6841) for the same reason, and
    the mid-chain variant it also had could never fire under the shipped hop_mode (M26).

    THE BOOKS ARE ALL CLEARED, INCLUDING ef/es. grow() cleared use/comp/contrib and not the error
    EMAs, so a newborn inherited a dead expert's error history and could be culled by the failure
    route for something it never did (L30).
    """
    n = pop.n_live
    if n >= pop.cap:
        # NOT MEASURED, AND None SAYS SO. Returning 0.0 for the gap and 0.0 for the typical spacing
        # would write two readings the pass never took, and a reader comparing them would conclude
        # the query sat exactly on an existing identity -- the strongest possible "no spawn needed"
        # verdict, manufactured by a full pool.
        return None, None, None
    with torch.no_grad():
        weights = torch.cat([pop.A[:n].reshape(n, -1), pop.B[:n].reshape(n, -1)], -1)
        keys = F.normalize(pop.modules["eemb"](weights), dim=-1)
        q = F.normalize(query.detach().mean(0), dim=-1)
        near = float((keys @ q).max()) if n else -1.0
        # THE SUBSAMPLE IS DRAWN ON THE FABRIC'S OWN STREAM. `torch.randperm(n)` without a generator
        # draws from torch's GLOBAL stream, which is exactly the coupling channel spine/rng.py
        # exists to close: a lever that changes how much this function MEASURES would then shift
        # every later torch draw in the process, and the isolation sweep would report a coupling
        # that is an artifact of draw order. D12 is the ruling on the global generator.
        if n <= 512:
            sub = keys
        else:
            pick = torch.tensor(sorted(pop.rng.sample(range(n), 512)), dtype=torch.long,
                                device=keys.device)
            sub = keys[pick]
        pair = 1.0 - sub @ sub.t()
        pair.fill_diagonal_(9e9)
        typ = float(pair.min(1).values.median()) if sub.size(0) > 1 else 0.0
        gap = 1.0 - near
        if gap < max(float(spawn_mult) * typ, float(spawn_floor)):
            return None, gap, typ
        slot = n
        decoded = pop.modules["edec"](q[None, :])[0]
        d_model, rank = int(pop.A.shape[1]), int(pop.A.shape[2])
        pop.A[slot] = decoded[:d_model * rank].reshape(d_model, rank)
        pop.B[slot] = decoded[d_model * rank:].reshape(rank, d_model)
    pop.born[slot] = int(step_n)
    pop.use[slot] = 0
    pop.uage[slot] = 0
    pop.ef[slot] = 0.0
    pop.es[slot] = 0.0
    pop.comp[slot] = 0.0
    pop.contrib[slot] = 0.0
    pop.dom_of[slot] = set()
    pop.parent[slot] = -1
    pop.mutscale[slot] = 1.0
    pop.n_live = slot + 1
    pop.births += 1
    # THE IDENTITY CACHE IS NOW STALE IN BOTH SENSES -- it is the wrong length, and the tensor it was
    # embedded from has a new version. Dropped rather than patched: a cache that survives a write to
    # its own source is the "backward through the graph a second time" failure with extra steps.
    pop.ident = pop.ident_graph = pop.ident_step = None
    pop.ident_live = -1
    return slot, gap, typ


def _bump(counters, name, by=1):
    """Cumulative DID IT FIRE arithmetic, in one place so a counter cannot be seeded on one branch.

    `setdefault`-then-add rather than `get`-or-0 inside a branch: SIG's cadence ledger shipped a
    counter that was ABSENT rather than 0 for a whole run at the one configuration the tree ships,
    because the two lines that seeded it stood inside the else of the gate they described.
    """
    counters[name] = counters.get(name, 0) + by


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
    HALT -- while the class docstring describes it as biasing expert selection (M28). THE MODULE
    THE REPAIR NEEDS NOW EXISTS: `pop.modules["nov_proj"]` (the old tree's `s.nov`, nn.Linear from
    the novelty scalar into dk), and `pop.modules["norm"]` for the per-hop vote below, both
    allocated by fabric/api.py::build -- state_dict named them and nothing built them until
    2026-09-03. The learned halt prior is `pop.halt_b`, beside A and B rather than in `modules`,
    because nn.ModuleDict cannot hold a bare Parameter.

    HALT GATES THE STATE UPDATE. :2683 applies the mixture at full strength on every hop regardless
    of how much probability has already halted, so the hidden state keeps changing after the router
    has decided to answer (M30). The residual step is scaled by the surviving mass.

    `.aux_loss` is the single scalar of every FAB-side penalty, ALL WITH A GRAPH: ponder, balance,
    div_w distinctness, ind_w independence, hop_sup per-hop CE, and the ae_w identity round-trip
    with its emb_var variance term. `.gates` carries the arithmetic of every gate this pass
    evaluated.

    WRITTEN 2026-09-04, AND WHAT THE FIRST HONEST MEASUREMENT OF IT SAYS. Until this body existed no
    path in the tree exercised an expert, so INV-R2-1's retraction of "the fabric trains" could not
    be answered either way. Through this walk, at FAB_N0=8/SLOTS=16/RANK=4/DK=8 over 30 real
    optimizer steps (DATA -> TOK -> LM -> FAB -> OPT.scaled_backward -> OPT.maybe_step, cross-entropy
    plus this aux_loss), grad|A|max = 1.36e-2 and grad|B|max = 9.07e-3 AT STEP 0 and 1.32e-2 /
    1.61e-2 after 30; max|A_after - A_before| = 0.409 at OPT_WEIGHT_DECAY=0, which is the shipped
    default, so the movement is gradient and not decay. The same script with the retracted probe --
    reaching A and B only through `((h @ A[0] @ B[0]) ** 2)` -- reproduces the void reading exactly:
    grad|A|max = grad|B|max = term = 0.0 at every step, max|dA| = 3.18e-4 at weight_decay=0.01 and
    EXACTLY 0.0 at weight_decay=0.
    WHY dL/dA IS NONZERO AT STEP 0 EVEN THOUGH B IS ZERO, because that is the trap: through the
    mixture alone it would be zero (dL/dA = grad_out @ B^T). It is not zero because A reaches the
    loss by three other routes this body builds -- eemb's identity channel (every live expert's
    adapter is embedded into the routing keys, so routing gradient reaches ALL n of them, not just
    the chain_k computed), the load-balance term, and the ae round trip. dL/dB through the mixture is
    nonzero from the first step because it is (hA)^T @ grad_out, which does not contain B.

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
    # THE INCOMING CLOCK IS PUT THROUGH units.Windows, exactly as sig/api.py::cadence_due does with
    # its two. Config hands back a bare int for every clock-unit lever, so a kind is metadata at the
    # READ site -- but what arrives as an ARGUMENT comes from the root, and spine/units.py::Clock
    # refuses to build a Windows out of a Steps. `ponder_warm` and `bal_warm` are both Windows and
    # both are divided by this number; handed the optimizer's step counter instead they would be
    # wrong by the effective batch width, and right at batch_windows=1 where the two coincide, which
    # is the shape of every clock defect this project has recorded.
    step = U.Windows(step_windows)
    step_n = int(step)
    counters, gates = pop.counters, []
    zero = h.new_zeros(())

    on, norm_only = bool(fab.on), bool(fab.norm_only)
    if not on:
        # THE SWITCH IS OFF AND THAT IS A READING, NOT A FAILURE -- but every gate below it is
        # UNREACHABLE, which is the distinction fabric/api.py::build already draws for the cull gate.
        gates.append(Gate("fab.forward.routed", False, value="FAB_ON=0", threshold="FAB_ON=1",
                          reachable=False,
                          reason="FAB_ON=0: the forward is the identity, so no expert is computed, "
                                 "no routing distribution exists, and every FAB-side term of the "
                                 "objective is ABSENT rather than zero."))
        _bump(counters, "fab.forward_identity")
        return FabricOut(hidden=h, aux_loss=zero, gates=tuple(gates))

    hops, depth0 = int(fab.hops), int(fab.depth0)
    if norm_only:
        # THE CONTROL ARM. It keeps the normalization and removes nodes and routing, which is what
        # separates it from FAB_ON=0: the population is still built, still in the optimizer and still
        # in the checkpoint -- so a run on this arm answers "what did the EXPERTS buy" rather than
        # "what did the whole package buy", and the two questions have different answers.
        out = h
        for _ in range(max(1, min(hops, 2 + int(pop.n_live) // 2))):
            out = pop.modules["norm"](out)
        _bump(counters, "fab.norm_only_passes")
        gates.append(Gate("fab.forward.routed", False, value="FAB_NORM_ONLY=1",
                          threshold="FAB_NORM_ONLY=0", reachable=False,
                          reason="FAB_NORM_ONLY=1: the control arm keeps the fabric's normalization "
                                 "and removes nodes and routing from the forward pass. The experts "
                                 "receive no gradient from this term; they remain in the optimizer, "
                                 "which is what makes this arm different from FAB_ON=0."))
        return FabricOut(hidden=out, aux_loss=zero, gates=tuple(gates))

    # ---- the levers, read once ------------------------------------------------------------------
    society = bool(fab.society)
    hop_vote, halt_on = bool(fab.hop_vote), bool(fab.halt)
    halt_max, alpha = float(fab.halt_max), float(fab.alpha)
    ponder_w, ponder_warm_n = float(fab.ponder), int(fab.ponder_warm)
    region_w, route_learn = float(fab.route_region_w), bool(fab.route_learn)
    route_t = float(fab.route_t)
    cent_topk, cent_ema, discover = int(fab.cent_topk), float(fab.cent_ema), float(fab.discover)
    chain_k, ens_k, explore = int(fab.chain_k), int(fab.ens_k), float(fab.explore)
    ec_w = float(fab.ec_w)
    balance_w, bal_floor, bal_warm_n = float(fab.balance), float(fab.bal_floor), int(fab.bal_warm)
    dom_frac, dom_min = float(fab.dom_frac), int(fab.dom_min)
    div_w, ind_k, ind_w = float(fab.div_w), int(fab.ind_k), float(fab.ind_w)
    hop_sup_w = float(fab.hop_sup)
    dk, rank, emb_hid = int(fab.dk), int(fab.rank), int(fab.emb_hid)
    emb_var, ae_w, emb_every_n = float(fab.emb_var), float(fab.ae_w), max(1, int(fab.emb_every))
    spawn_on = bool(fab.spawn)
    spawn_mult, spawn_floor = float(fab.spawn_mult), float(fab.spawn_floor)

    # THE THREE GEOMETRY LEVERS ARE READ AND COMPARED AGAINST THE POOL, not merely listed under
    # LEVERS READ. A Population built under one FAB_RANK/FAB_DK/FAB_EMB_HID and routed under another
    # is the checkpoint-geometry failure happening inside a single process: the einsum below would
    # either raise five shapes deep or, at a coincidence of widths, quietly index the wrong slice.
    # fabric/api.py::load_state_dict refuses the same disagreement across a resume by name; this is
    # the same refusal at the one place a live tensor can prove it.
    built = (int(pop.A.shape[2]), int(pop.modules["q_route"].out_features),
             int(pop.modules["eemb"][0].out_features))
    if built != (rank, dk, emb_hid):
        raise ValueError(
            f"FAB.forward: the Population was built at (rank, dk, emb_hid)={built} and this Config "
            f"says {(rank, dk, emb_hid)}. One population, two geometries.")

    training = bool(training)
    solo = hold_out is None                 # a counterfactual walk mutates NOTHING and learns NOTHING
    learn = training and solo
    n = int(pop.n_live)
    if n < 1:
        raise ValueError("FAB.forward: n_live is 0. An empty population is not a routing outcome; "
                         "fabric/api.py::build founds n0 experts and nothing may reduce it to none.")

    # SPAWN RUNS FIRST, BEFORE ANY GRAPH EXISTS -- see fabric/api.py::_spawn_check for why that is
    # forced and not preferred. It is also why `spawn` is read here rather than only in grow_check:
    # this is the only entry point that holds the router's own query, and spawn-by-specification is
    # "decode the query into the expert that was asked for".
    # WHAT THIS DOOR IS BOUND BY, AND WHAT IT IS NOT. It is bound by pop.cap, which is the hard
    # preallocation ceiling. It is NOT bound by CAP's operating soft cap, because `soft_cap` arrives
    # at fabric/api.py::grow_check and at no other entry point -- so the sentence in grow_check's
    # docstring, "spawn births are counted here too so BOTH DOORS ARE BOUND BY THE SAME CAP", is
    # today only half true: the count is available to grow_check through fab.spawned, and the
    # BINDING is not. Named here rather than fixed by reading a foreign number: the fix is either a
    # `soft_cap` keyword on this entry point (a frozen-signature move) or a rule that grow_check
    # subtracts spawn births from its own budget, and choosing between those is not this body's
    # decision to take silently. fab.spawned is what makes the gap countable meanwhile.
    spawned = None
    # THE REACHABILITY IS DECIDED BEFORE THE TEST RUNS, not after it. Asking "is the pool full"
    # afterwards reads the state the spawn ITSELF produced -- a birth that takes the population to
    # cap would then be reported as UNREACHABLE and FIRED at once, which spine/gate.py::Gate refuses
    # outright because a report carrying both says nothing.
    could_spawn = bool(spawn_on and learn and int(pop.n_live) < int(pop.cap))
    if spawn_on and learn:
        with torch.no_grad():
            probe = _route_query(pop, signature, novelty)
        spawned, spawn_gap, spawn_typ = _spawn_check(pop, probe, spawn_mult, spawn_floor, step_n)
        # THE GAP AND THE SCALE ARE ONE STATEMENT, AND THEY ARE WRITTEN ONLY WHEN THEY WERE TAKEN.
        # The old report printed the gap with nothing to compare it against (ISSUES P1-L29), so "the
        # query was 0.31 from the nearest identity" said nothing about whether that is far. Both are
        # written together; neither is written when the test did not run.
        if spawn_gap is not None:
            counters["fab.spawn_gap"] = round(float(spawn_gap), 6)
            counters["fab.spawn_typ"] = round(float(spawn_typ), 6)
        if spawned is not None:
            _bump(counters, "fab.spawned")
            n = int(pop.n_live)
        elif spawn_gap is not None:
            # A DECLINE IS A TEST THAT RAN AND SAID NO. A full pool is not a decline -- crediting one
            # would make fab.spawn_declined count passes where the mechanism had no slot, which is
            # the unreachable state wearing the armed-but-0 state's clothes.
            _bump(counters, "fab.spawn_declined")
    _ran = spawn_on and learn
    gates.append(Gate("fab.spawn", spawned is not None,
                      value=(f"gap={counters['fab.spawn_gap']}"
                             if (_ran and could_spawn) else "not measured"),
                      threshold=(f"max({spawn_mult}*typ={counters['fab.spawn_typ']}, "
                                 f"floor={spawn_floor})" if (_ran and could_spawn) else
                                 f"max({spawn_mult}*typ, floor={spawn_floor})"),
                      reachable=could_spawn,
                      reason="" if could_spawn else
                             ("FAB_SPAWN=0" if not spawn_on else
                              "this pass is an eval or a leave-one-out counterfactual, which must "
                              "not create an expert" if not learn else
                              f"the pool is full at cap={int(pop.cap)}: growth never reallocates, "
                              f"so spawn-by-specification has nowhere to put an expert.")))

    # EVERY DID-IT-FIRE KEY EXISTS FROM THE FIRST ROUTED PASS, seeded before any branch decides
    # whether to bump it. A key that is ABSENT and a key that reads 0 are the same thing to a reader
    # of the ledger and two different things about the run, and seeding inside a branch seeds
    # neither: sig/api.py::cadence_due shipped a counter that was absent for a whole run at the one
    # configuration the tree ships, because the two lines that seeded it stood inside the else of the
    # gate they described.
    for _key in ("fab.route_calls", "fab.hops_taken", "fab.halt_clamped", "fab.explored_rows",
                 "fab.explore_distinct_targets", "fab.discovered", "fab.discover_targets",
                 "fab.banned_experts", "fab.ec_applied", "fab.balance_nonzero", "fab.div_applied",
                 "fab.ind_applied", "fab.hopsup_applied", "fab.ident_refreshed",
                 "fab.ident_trained", "fab.holdout_applied", "fab.spawned", "fab.spawn_declined"):
        counters.setdefault(_key, 0)
    _bump(counters, "fab.route_calls")
    # DEPTH. society PINS THE WALK AT ONE HOP and keeps per-expert logits, which is what makes
    # leave-one-out a reweighted sum rather than a re-walk -- it is the same forward pass with a
    # different depth and a different return, NOT a second path. The old tree had two, and
    # SUFFICIENCY called fab.society() unconditionally while the shipped default was the looped
    # path (D1, point 2).
    depth = 1 if society else max(1, min(int(pop.depth_now), hops, 2 + n // 2))
    gates.append(Gate("fab.depth_curriculum", 0 < depth0 < hops,
                      value=f"depth0={depth0}", threshold=f"hops={hops}",
                      reason="" if 0 < depth0 < hops else
                             ("FAB_DEPTH0=0 is the no-curriculum sentinel: build resolved depth_now "
                              "to the full hop budget, so FAB.manage's staged advance has nothing "
                              "to extend." if depth0 == 0 else
                              "FAB_DEPTH0 >= FAB_HOPS: the chain already starts at the budget.")))

    keys, refreshed = (_identities(pop, n, step_n, emb_every_n) if route_learn else (None, False))
    if refreshed:
        _bump(counters, "fab.ident_refreshed")
    ban, ban_limit, ban_reason = _breadth_ban(pop, n, domain_id, live_domains, dom_frac, dom_min)

    # THE PRE-LOOP ENTRY DISTRIBUTION IS NOT COMPUTED, AND THE ABSENCE IS THE STATEMENT. The old tree
    # formed one before the walk (self_organize.py:2584-2603) and its ONLY consumer on the soc arm is
    # `ground_update` -- the `if s.loop_soc:` block returns at :2694 without reading it again, and
    # every later read is in the transition arm Q-FAB-1 leaves unported. It is the same router hop 0
    # runs, minus hproj, so keeping it would mean routing twice per window to nudge the same
    # centroids twice. That analysis is fabric/api.py::state_dict's, written to justify dropping
    # `q_entry`; the same reading decides this.
    h0 = h                       # the base representation HALT mass buys on the society arm
    alive = torch.ones(h.size(0), device=h.device, dtype=h.dtype)
    depth_acc, bal_acc, div_acc = zero, zero, None
    mass_acc, vote, last_vote, per_expert = None, None, None, None
    entry_halt, last_hop_lg = None, None
    last_idx = last_w = None
    hop_logits = []
    hops_taken = halt_clamped = explored_rows = banned_seen = discovered = 0
    ec_any = False

    for _hop in range(depth):
        # RE-ROUTED FROM SCRATCH EVERY HOP, WITH THE CURRENT STATE IN THE QUERY. That is what
        # hop_mode="soc" means: the second choice is not a successor of the first, there is no
        # transition matrix and no SRC anywhere on this walk.
        query = _route_query(pop, signature, novelty, state=h.mean(1))
        logits, ec_applied, banned = _entry_logits(
            pop, query=query, signature=signature, keys=keys, n=n, region_w=region_w,
            route_learn=route_learn, route_t=route_t, ec_w=ec_w, ban=ban, hold_out=hold_out)
        ec_any = ec_any or ec_applied
        banned_seen = max(banned_seen, banned)
        halt_lg = _halt_logit(pop, query, route_t, halt_on, h.size(0), h.device, logits.dtype)
        full = torch.softmax(torch.cat([logits, halt_lg], -1), -1)
        if halt_on:
            raw = full[:, n]
            halt_clamped += int((raw > halt_max).sum())
            ph = raw.clamp(max=halt_max)
        else:
            ph = torch.zeros(h.size(0), device=h.device, dtype=full.dtype)
        w = full[:, :n] / full[:, :n].sum(-1, keepdim=True).clamp_min(_FLOOR)
        if entry_halt is None:
            entry_halt = ph
        mass_acc = w.detach() if mass_acc is None else mass_acc + w.detach()
        depth_acc = depth_acc + (1.0 - ph).mean()
        # THE LOAD-BALANCE TERM HAS A GRAPH, AND THAT IS THE WHOLE OF C2. `w` here is the live
        # routing distribution, not a freshly allocated zero, so FAB_BALANCE, BAL_FLOOR and BAL_WARM
        # scale something that can move. The old soc loop returned `h.new_zeros(())` as its fourth
        # element (self_organize.py:2694) and the training loop multiplied it at :7031.
        bal_acc = bal_acc + w.size(1) * (w.mean(0) ** 2).sum()
        if learn:
            got, slot = _ground_update(pop, signature, w, n, cent_topk, cent_ema, discover)
            if got:
                discovered += got
                pop.marks.setdefault("discover", set()).add(slot)

        k = max(1, min(chain_k, n))
        val, idx = w.topk(k, dim=-1)
        if learn:
            idx, val, rows, targets_cold = _explore_swap(pop, idx, val, w, n, k, explore)
            explored_rows += rows
            if targets_cold:
                pop.marks.setdefault("explore", set()).update(targets_cold)
        # THE EXPERTS, COMPUTED. This is the line both project goals rest on: A[idx] is
        # (B, k, d_model, rank) and B[idx] is (B, k, rank, d_model), so the expert's contribution is
        # B(A(x)) added to the residual. B IS ZERO AT BIRTH, WHICH IS NOT A DEFECT -- it makes a
        # newborn an identity, so adding capacity cannot disturb what already works, which is goal B
        # at the level of a single expert. What it does mean is that dL/dA through THIS term alone is
        # zero on the first step (dL/dA = grad_out @ B^T), which is exactly the trap INV-R2-1 records:
        # a probe reaching A only through A @ B measures zero and reads it as an answer. The other
        # routes -- eemb's identity channel, the balance term, the ae round trip -- do not vanish.
        out = h.unsqueeze(1) + torch.einsum(
            "bklr,bkrd->bkld", torch.einsum("bld,bkdr->bklr", h, pop.A[idx]), pop.B[idx])
        cw = val / val.sum(-1, keepdim=True).clamp_min(_FLOOR)
        last_idx, last_w = idx, w

        if div_w > 0.0 and k >= 2 and solo:
            # WEIGHTED BY WHAT THE ROUTER ACTUALLY LEANS ON. Unweighted, this term pays two experts
            # for producing different outputs regardless of whether either is any good -- and two
            # experts are maximally distinct when they are wrong in different directions, which the
            # LM loss cannot see because it scores only the blend. The product of the two routing
            # weights makes divergence count in proportion to how much the router relies on BOTH, so
            # the reward cannot be farmed by drifting out of the ensemble. x4 normalises it: at
            # equal weights the product is 0.25 and this is the unweighted term.
            dq = F.cosine_similarity(out[:, 0].reshape(out.size(0), -1),
                                     out[:, 1].reshape(out.size(0), -1), dim=-1).clamp_min(0.0)
            dq = (dq * (4.0 * cw[:, 0] * cw[:, 1]).clamp(max=1.0)).mean()
            div_acc = dq if div_acc is None else div_acc + dq

        hop_lg = None
        if head is not None:
            # ens_k IS WHAT DECODES, chain_k IS WHAT COMPUTES, and the society arm widens the decode
            # to max(ens_k, ind_k) because the independence term charges its own experts with
            # solving the task alone -- the old tree's `k=max(ENS_K, IND_K)` (self_organize.py:6846),
            # a coupling that was invisible under the bare name.
            decode_k = max(1, min(k, max(ens_k, ind_k) if society else ens_k))
            parts = [head(pop.modules["norm"](out[:, j])) for j in range(decode_k)]
            vk = max(1, min(ens_k, decode_k))
            vw = cw[:, :vk] / cw[:, :vk].sum(-1, keepdim=True).clamp_min(_FLOOR)
            for j in range(vk):
                piece = parts[j] * vw[:, j][:, None, None]
                hop_lg = piece if hop_lg is None else hop_lg + piece
            if society:
                per_expert = torch.stack(parts, 1)
        if hop_lg is not None:
            # PER-HOP STATES ARE COLLECTED ON THE SOC LOOP, which is the one-line repair M27 is owed.
            # `s._hops.append` occurs at EXACTLY ONE site in the old tree, :2819, inside the
            # transition branch -- so under the shipped hop_mode any hop_sup above zero added exactly
            # nothing to the loss and nothing at the config layer said so. At hop_vote=True these
            # tensors already exist for the vote, so the collection costs nothing.
            hop_logits.append(hop_lg)
            last_hop_lg = hop_lg
            if hop_vote:
                take = (alive * ph)[:, None, None]
                vote = take * hop_lg if vote is None else vote + take * hop_lg
                last_vote = hop_lg

        # HALT GATES THE STATE UPDATE (M30). :2683 applies the mixture at full strength on every hop
        # regardless of how much probability has already halted, so the hidden state kept changing
        # after the router had decided to answer. Scaling the residual by the SURVIVING mass makes
        # "stop" mean stop.
        alive = alive * (1.0 - ph)
        mixture = (cw[:, :, None, None] * out).sum(1)
        h = pop.modules["norm"](h + alive[:, None, None] * (alpha * (mixture - h)))
        hops_taken += 1

    _bump(counters, "fab.hops_taken", hops_taken)
    if halt_on:
        _bump(counters, "fab.halt_clamped", halt_clamped)
    if explored_rows:
        _bump(counters, "fab.explored_rows", explored_rows)
    counters["fab.explore_distinct_targets"] = len(pop.marks.get("explore", ()))
    if discovered:
        _bump(counters, "fab.discovered", discovered)
    counters["fab.discover_targets"] = len(pop.marks.get("discover", ()))
    if banned_seen:
        _bump(counters, "fab.banned_experts", banned_seen)
    if ec_any:
        _bump(counters, "fab.ec_applied")
    if hold_out is not None:
        _bump(counters, "fab.holdout_applied")

    if hop_vote and vote is not None and last_vote is not None:
        vote = vote + alive[:, None, None] * last_vote      # never stopped -> the last round answers
    # WHAT THE HALTED MASS BUYS IS THE ONLY THING THAT DIFFERS BETWEEN THE TWO ARMS. Same operator,
    # same key, same softmax. On the looped arm HALT means "stop walking" and the mass is spent on
    # the hop that stopped, which the accumulation above already did. On the society arm the walk is
    # one-shot, so it can only mean "no expert is needed for this window", and the only honest way
    # to honour that is to let the BASE representation complete it directly
    # (self_organize.py:4035-4043). Without this the society arm computes a halt mass and throws it
    # away, which is what the old grounded router did before halt became a real operator.
    logits_out = None
    if society and head is not None and last_hop_lg is not None and entry_halt is not None:
        held = entry_halt[:, None, None]
        logits_out = (1.0 - held) * last_hop_lg + held * head(h0)
        _bump(counters, "fab.halt_spent_on_base")
    elif hop_vote and vote is not None:
        logits_out = vote
    if learn:
        # TRAINING PASSES ONLY. The old EMA averaged eval passes in, so it moved when nothing but
        # HOLDOUT_N changed -- a reported number that a diagnostic could shift.
        with torch.no_grad():
            mass_now = (1.0 - alive).mean().detach()
            pop.halt_ema = mass_now if pop.halt_ema is None else 0.99 * pop.halt_ema + 0.01 * mass_now
        counters["fab.halt_mass_train"] = round(float(pop.halt_ema), 6)

    weights = mass_acc / mass_acc.sum(-1, keepdim=True).clamp_min(_FLOOR)
    expert_ids = weights.topk(max(1, min(ens_k, n)), dim=-1).indices

    # ---- the aux loss: ONE scalar, every FAB-side penalty, ALL WITH A GRAPH ----------------------
    aux = zero
    ponder_scale = _warm_up(step_n, ponder_warm_n)
    aux = aux + ponder_w * ponder_scale * (depth_acc / max(1, hops_taken))
    bal_scale = _decay_to_floor(step_n, bal_warm_n, bal_floor)
    bal = bal_acc / max(1, hops_taken)
    aux = aux + balance_w * bal_scale * bal
    # THE C2 ALARM, AND IT TESTS THE GRAPH AND NOT ONLY THE VALUE. A balance term that is numerically
    # small is a measurement; one with no grad_fn is the defect -- FAB_BALANCE, BAL_FLOOR and
    # BAL_WARM were read, printed and reasoned about for the whole life of the old tree while
    # multiplying a freshly allocated zero. Recorded on training passes only, because under
    # torch.no_grad() every tensor here legitimately has no graph.
    if balance_w > 0.0 and training:
        live_term = (bal.grad_fn is not None) and float(bal.detach()) != 0.0
        _bump(counters, "fab.balance_nonzero", 1 if live_term else 0)
    div_applied = 0
    if div_acc is not None and div_w > 0.0:
        aux = aux + div_w * (div_acc / max(1, hops_taken))
        div_applied = 1
        _bump(counters, "fab.div_applied")
    ind_applied = 0
    if society and ind_w > 0.0 and per_expert is not None and targets is not None:
        # EACH OF ind_k EXPERTS MUST SOLVE THE TASK ALONE, weighted by its routing mass -- which
        # makes the population an ENSEMBLE, surviving member removal, rather than a DECOMPOSITION,
        # which does not. It is the direct counterweight to div_w and the pair is the question D7
        # asks about aggregate sufficiency.
        vocab = per_expert.size(-1)
        for j in range(max(1, min(ind_k, per_expert.size(1)))):
            share = last_w.gather(1, last_idx[:, j:j + 1]).mean().detach()
            ce = F.cross_entropy(per_expert[:, j].reshape(-1, vocab), targets.reshape(-1))
            aux = aux + ind_w * share * ce
            ind_applied = 1
        if ind_applied:
            _bump(counters, "fab.ind_applied")
    hopsup_applied = 0
    if hop_sup_w > 0.0 and targets is not None and len(hop_logits) > 1:
        sup = None
        for lg in hop_logits[:-1]:                 # the last hop IS the main loss; don't double-count
            ce = F.cross_entropy(lg.reshape(-1, lg.size(-1)), targets.reshape(-1))
            sup = ce if sup is None else sup + ce
        aux = aux + hop_sup_w * (sup / max(1, len(hop_logits) - 1))
        hopsup_applied = 1
        _bump(counters, "fab.hopsup_applied")
    ident_term = 0
    if spawn_on and ae_w > 0.0 and learn:
        # THE ROUND TRIP TRAINS EVERY STEP, not on the embed cadence. The cadence exists because
        # RE-READING identities is O(n * 2*d*r * hid); TRAINING the embedder is capped at 256 experts
        # and is cheap. Tying the two gave the embedder one update per cadence and it stayed
        # collapsed -- and a collapsed identity space makes the spawn test fire on every query.
        aux = aux + ae_w * _ae_loss(pop, min(n, 256), emb_var)
        ident_term = 1
        _bump(counters, "fab.ident_trained")

    # ---- the gates that could not be evaluated until now ----------------------------------------
    gates.append(Gate("fab.balance", balance_w > 0.0,
                      value=f"balance={balance_w} x warm={round(bal_scale, 4)}",
                      threshold="> 0",
                      reason="" if balance_w > 0.0 else
                             "FAB_BALANCE=0: no load-balance pressure. This is 'off', not C2 -- the "
                             "C2 alarm is fab.balance_nonzero reading 0 while this is above zero."))
    # THE DEFICIT BONUS IS ARMED ON A TABLE NOTHING WRITES YET, and that is a third state. `use` is
    # credited by fabric/api.py::observe and by nothing else, so until that entry point has a body
    # every expert's utilization is 0, the fair share is 0, and there is no deficit to score -- which
    # is not the same statement as "ec_w is off" and not the same as "every expert was already at
    # its share".
    _use_total = float(sum(pop.use[:n]))
    gates.append(Gate("fab.expert_choice", ec_any, value=f"ec_w={ec_w}",
                      threshold=f"sum(use)={_use_total}",
                      reachable=bool(ec_w > 0.0 and n > 1 and _use_total > 0),
                      reason="" if (ec_w > 0.0 and n > 1 and _use_total > 0) else
                             ("FAB_EC_W=0: allocation by loss pressure (`balance`) only."
                              if ec_w <= 0.0 else
                              "n_live is 1: one expert has no share to be under." if n <= 1 else
                              "every `use` is 0: FAB.observe is the only writer of the utilization "
                              "table and it is a stub, so the deficit is identically zero.")))
    gates.append(Gate("fab.explore", explored_rows > 0,
                      value=f"{explored_rows} row(s) swapped, "
                            f"{len(pop.marks.get('explore', ()))} distinct cold target(s)",
                      threshold=f"explore={explore}",
                      reachable=bool(explore > 0.0 and learn and n > max(1, min(chain_k, n))),
                      reason="" if (explore > 0.0 and learn and n > max(1, min(chain_k, n))) else
                             ("FAB_EXPLORE=0: nothing stands between the utilization cull and a "
                              "self-fulfilling ranking." if explore <= 0.0 else
                              "training passes only, and this was an eval or a counterfactual"
                              if not learn else
                              f"n_live={n} does not exceed chain_k, so every expert is already "
                              f"computed and there is no cold set to swap one in from.")))
    gates.append(Gate("fab.discover", discovered > 0,
                      value=f"{discovered} handover(s), "
                            f"{len(pop.marks.get('discover', ()))} distinct recipient(s)",
                      threshold=f"cosine distance > {discover}",
                      reachable=bool(discover > 0.0 and learn and n > 1),
                      reason="" if (discover > 0.0 and learn and n > 1) else
                             ("FAB_DISCOVER=0: material nothing owns is absorbed by the nearest "
                              "incumbent." if discover <= 0.0 else
                              "training passes only" if not learn else
                              "n_live=1: there is no least-used expert to hand it to.")))
    gates.append(Gate("fab.distinctness", bool(div_applied), value=f"div_w={div_w}",
                      threshold=f"chain_k={chain_k} >= 2, n_live={n}",
                      reachable=bool(div_w > 0.0 and min(chain_k, n) >= 2 and solo),
                      reason="" if (div_w > 0.0 and min(chain_k, n) >= 2 and solo) else
                             ("FAB_DIV_W=0: nothing pays two co-routed experts for producing "
                              "different outputs, which is one of the two things the fabric is FOR."
                              if div_w <= 0.0 else
                              "a counterfactual walk adds no loss term" if not solo else
                              "fewer than two experts are computed per hop")))
    gates.append(Gate("fab.route_learned", route_learn, value=f"route_learn={route_learn}",
                      threshold="route_learn=True",
                      reason="" if route_learn else
                             "FAB_ROUTE_LEARN=0: routing is the region cosine alone, so q_route, "
                             "eemb and nov_proj receive no gradient from routing and novelty "
                             "reaches only the HALT logit. That is the end of learned routing, not "
                             "a small change."))
    gates.append(Gate("fab.breadth_cap", ban is not None,
                      value=f"limit={ban_limit} of live_domains={int(live_domains)}",
                      threshold=f"dom_frac={dom_frac}, dom_min={dom_min}",
                      reachable=not ban_reason, reason=ban_reason))
    gates.append(Gate("fab.hop_sup", bool(hopsup_applied), value=f"hop_sup={hop_sup_w}",
                      threshold=f"{len(hop_logits)} hop logits collected",
                      reachable=bool(hop_sup_w > 0.0 and targets is not None and head is not None),
                      reason="" if (hop_sup_w > 0.0 and targets is not None and head is not None)
                             else ("FAB_HOP_SUP=0" if hop_sup_w <= 0.0 else
                                   "no targets were supplied, so a per-hop cross-entropy has "
                                   "nothing to score against" if targets is None else
                                   "no head was supplied, so no hop can produce logits")))
    gates.append(Gate("fab.independence", bool(ind_applied), value=f"ind_w={ind_w}, ind_k={ind_k}",
                      threshold="society=True and targets supplied",
                      reachable=bool(society and ind_w > 0.0 and targets is not None
                                     and head is not None),
                      reason="" if (society and ind_w > 0.0 and targets is not None
                                    and head is not None) else
                             ("FAB_SOCIETY=0: per-expert logits are not retained on the looped arm, "
                              "so 'solve it alone' has no per-expert prediction to score"
                              if not society else
                              "FAB_IND_W=0" if ind_w <= 0.0 else
                              "no head was supplied, so no expert can produce a prediction of its "
                              "own" if head is None else "no targets were supplied")))
    gates.append(Gate("fab.identity_round_trip", bool(ident_term),
                      value=f"ae_w={ae_w}, emb_var={emb_var}",
                      threshold=f"spawn={spawn_on}, training={training}",
                      reachable=bool(spawn_on and ae_w > 0.0),
                      reason="" if (spawn_on and ae_w > 0.0) else
                             ("FAB_SPAWN=0 also switches off the identity autoencoder: edec exists "
                              "only to specify a newborn, so nothing would read what it learned."
                              if not spawn_on else "FAB_AE_W=0")))
    gates.append(Gate("fab.halt", halt_on, value=f"mean halted mass "
                                                  f"{round(float((1.0 - alive).mean().detach()), 4)}",
                      threshold=f"halt_max={halt_max}",
                      reason="" if halt_on else
                             "FAB_HALT=0: the halt logit is PINNED at a constant rather than "
                             "derived, so halt_key and halt_b receive no gradient and the walk "
                             "always runs its full depth."))
    gates.append(Gate("fab.forward.routed", True, value=f"{hops_taken} hop(s) over {n} experts",
                      threshold=f"depth={depth}"))

    return FabricOut(
        # WHICH OF logits/hidden IS PRESENT IS THE STATEMENT ABOUT WHO DECODES. When the population
        # voted, the caller must NOT re-decode `hidden`: scoring a prediction through a different
        # function from the one that produced the baseline is H11, and it added a fixed offset to
        # every contribution -- which set the SIGN of contrib, the thing both spare rules test.
        # THE GATES ARE ON THE RECORD AND NOT APPENDED TO pop.gates. Appending would grow one tuple
        # by a dozen entries per window for the length of a run, and a report reading the last pass's
        # arithmetic would have to find it among thousands; fabric/api.py::build's two gates describe
        # the BUILD, which happens once, and these describe THIS PASS.
        logits=logits_out, hidden=h, expert_ids=expert_ids, weights=weights,
        per_expert_logits=per_expert, aux_loss=aux, gates=tuple(gates))


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
    """Parameters (A, B, q_route, hproj, eemb, edec, halt_key, halt_b, norm, nov_proj), the `cent`
    BUFFER, every book, the cumulative counter ledger, and the package RNG stream.

    EVERY NAME IN THAT LIST IS NOW ALLOCATED BY `build`, WHICH IT WAS NOT UNTIL 2026-09-03. The
    list named eleven tensors and build created five; halt_b, norm and nov_proj are now built
    (fabric/api.py::build carries the constructors, the old-tree line each came from, and where
    each is read), and q_entry joins ctrl in being dropped, for the reason below. A name here that
    nothing allocates is not a harmless aspiration: state_dict is the SAVE side, so the claim can
    only ever be falsified by a resume, which is the same shape as the `ctrl` defect this docstring
    already recorded.

    `ctrl` IS NOT IN THAT LIST AND THE ABSENCE IS THE STATEMENT. It was, until 2026-09-02, and
    nothing built it: `ctrl` belongs to the transition hop arm alone -- :1907 mints it in
    __init__, on one line with q_entry and nov (this sentence said "both inside the transition
    branch", which is wrong about the MINT and right about the arm), and :2827
    `bias = nb + s.ctrl(summ)` is its ONLY read, inside the transition branch. `build`'s allocation
    list creates no such module and Q-FAB-1 rules that the arm stays DECLARED and UNPORTED. So the
    contract promised to checkpoint a parameter nothing allocates -- a save-side claim that could
    only ever be tested by a resume. It returns to this list in the same commit that ports the arm,
    and not before.

    `q_entry` IS DROPPED ON THE SAME GROUND, REVERSING THIS DOCSTRING'S OWN EARLIER RULING -- BUT
    NOT ON THE EVIDENCE THIS PARAGRAPH CARRIED UNTIL 2026-09-04, WHICH WAS WRONG TWICE. The reversed
    ruling read "q_entry (:2557, :2564) and nov_proj (:2554) stay, because both walks use them", and
    two of its three line citations no longer resolve to either name. The reversal's own first
    evidence was worse than that and is corrected here rather than left standing: it claimed q_entry
    has "exactly three readers", all behind dropped arms. `grep -n q_entry self_organize.py` returns
    SIX reader sites, and one is reached on an arm this tree SHIPS:
      :2320  route_w's `else` -- the ROUTE_GROUNDED=0 hop router. Dropped arm.
      :2591  the `else` of `if s.grounded:` -- the ROUTE_GROUNDED=0 entry router, which the old
             tree's own comment two lines above calls "a different and strictly weaker router",
             and which fabric/levers.py::FABLevers.cent_ema records as DROPPED here ("now that
             ROUTE_GROUNDED's alternative router is dropped"). Dropped arm.
      :2597  the `else` of `if s.halt_on` -- and it is NOT "on that same non-grounded branch", which
             is what this paragraph asserted. `_hlg` (:2595) sits at the same eight-space indent as
             `if s.grounded:` (:2584), i.e. AFTER that `if` has closed, so it is evaluated on BOTH
             branches and gated on `s.halt_on` alone. FAB_HALT is not a dropped arm: the census
             verdicts it `keep` in .rework/census.json (ROUTE_GROUNDED and FAB_DERIVE_IDS both
             `drop`), fabric/levers.py::FABLevers.halt is Lever(True, ...), and
             fabric/api.py::build reads it and records `fab.halt`. So at the shipped
             ROUTE_GROUNDED=1 with FAB_HALT=0 this read IS reached, on the soc walk this tree ports.
      :2567  `seed_key`'s body (:2564 is the def line), whose single caller is
             `s.K[j] = s.seed_key(gist)` (:2143) -- a write into the FREE identity parameters, and
             fabric/levers.py::FABLevers.dk records FAB_DERIVE_IDS=0 as dropped, so there is no K to
             seed: an expert's key is DERIVED from its weights through eemb. Dropped arm.
      :4019  `fab.q_entry.in_features`, a SHAPE read in fab_logits, used only to fabricate a zero
             gist; this tree's `forward` takes `signature` as an argument and fabricates none.
      :9156  the SPECIALIZATION probe's own `else` -- a diagnostic, not the walk.

    THE DROP SURVIVES ANYWAY, ON THE ARGUMENT :2597 FORCES. Follow what that read produces on the
    ported walk. `_hlg` is concatenated into `_elg` (:2598) and softmaxed into the pre-loop entry
    distribution `c` (:2600); `c` is then consumed by exactly one line, `s.ground_update(gist,
    c[:, :N], N)` (:2603); and the `if s.loop_soc:` block (:2618) returns at :2694 without reading
    `c` again -- every later read of it (:2703 onward) is in the transition arm Q-FAB-1 leaves
    unported. `ground_update`'s entire body is under `with torch.no_grad():` (:2404). So on the walk
    this tree ports, q_entry has NO GRADIENT PATH at EITHER setting of FAB_HALT, which is the fact
    the drop actually rests on.

    WHAT THE DROP COSTS, MEASURED RATHER THAN WAVED AT -- because "it changes nothing numerically"
    is also false. The halt logit enters `c`'s softmax denominator, rescaling row b's expert weights
    by a per-row factor. `ground_update` means over the batch FIRST (`_wm = w.mean(0)`, :2410) and
    renormalises only after (`_share = _iv / _iv.sum().clamp_min(1e-9)`, :2414), so that factor
    cancels EXACTLY at batch 1 and does NOT cancel above it. Replaying :2598-2603 into :2410-2414
    over 400 draws at B=8, N=32, FAB_CENT_TOPK=8, a q_entry-derived halt column against a pinned one
    moved the top-k SET in 137 of 400 draws and the per-index EMA rate in 400 of 400 (max delta
    0.056); at B=1, 0 of 400. That residue is a NEVER-TRAINED random projection perturbing a
    centroid EMA -- a defect of the old tree, not a behaviour to port, and the old tree says as much
    one screen down: the loop's own halt-off arm pins the halt logit to a constant,
    `torch.full((h.size(0), 1), -1e4)` (:2628), instead of deriving it. :2597 is the pre-halt-lever
    remnant, disagreeing with the loop it feeds, and a faithful port of FAB_HALT=0 takes :2628's
    form and needs no q_entry.

    The old tree measured the consequence twice and BOTH citations need their scope stated. Its
    ROUTER LEARNING audit printed "never gradiented -> ctrl, q_entry" (:9141, audit loop at :7085)
    at the shipped ROUTE_GROUNDED=1 AND the shipped FAB_HALT=1 (:1734) -- on its own it says nothing
    about the halt-off arm, which is what the two paragraphs above had to establish. The two
    armed-but-inert records naming the SPECIALIZATION section as having partitioned the population
    with a randomly-initialised q_entry for the whole life of the probe are P3-C28 and P3-H30 in
    .rework/ISSUES.md, cited by RECORD ID because that file's line numbers have already moved once.

    THE TRIGGER FOR q_entry'S RETURN IS NOT "the same commit that ports a non-grounded entry router",
    which is narrower than the truth: it is ANY LIVE CONSUMER OF THE PRE-LOOP ENTRY DISTRIBUTION `c`
    -- a literal port of :2597 that keeps the derived halt logit, or any use of `c` beyond
    `ground_update`'s no-grad EMA (a vote, an aux loss, a hop_sup target) -- because each of those
    puts q_entry back on a gradient path. Until one exists it is not checkpointed. `nov_proj` STAYS
    and is now BUILT, because the reading that kept it is the one that survives: its read at :2361
    is inside `entry_logits`, the grounded router this contract does port, and it is the same line
    `forward` cites for the M28 novelty repair.

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
