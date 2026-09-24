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
  GrowReport     asked vs grown, per trigger; declined_cap, declined_newfrac, lineage counts, and
                 the blackout state (open/closed and the windows left) the root joins into
                 CAP.observe's `blackout` boolean
"""
import dataclasses
import math

import torch
from torch import nn
from torch.nn import functional as F

from spine.lever import Config, LeverError
from spine import derive as _derive
from spine.gate import Gate, NotBuilt
from spine.init import is_scale as _is_scale
from spine import units as U


# ==================================================================================================
# THE SWITCH ON THE NEGATIVE-PERIOD REFUSAL
# ==================================================================================================

REFUSE_NEGATIVE_PERIOD = True
"""Whether manage_period refuses a negative FAB_MANAGE_EVERY. True is the shipped state; False lets
the value through to units.Windows exactly as it did before 2026-09-04 -- AT THIS ACCESSOR, which
since 2026-09-05 is no longer the same thing as through the composition root. A negative
FAB_MANAGE_EVERY is now refused earlier, by spine/derive.py::flush_period_windows inside the
FAB.d_manage_period coupling compute, so `assemble.build` raises UnitError with this constant in
EITHER position and the OFF configuration is unreachable that way. Measured, not assumed: with this
set False, build(environ={'FAB_MANAGE_EVERY': '-5'}) still raises. The switch still binds for a
caller that reaches manage_period with a Config built off that coupling path; the fuller statement
of where the arm stands, and of what would make it fire through the root again, is in
manage_period's own body beside the guard.

THE RULING (owner, 2026-09-04): "On the periods, let's refuse for now. If it has a bad effect, we
can turn off the refusal." The first sentence is the guard in manage_period; this name is the
second, which binds just as hard -- .rework/DECISIONS.md D4 rules that a thing kept for later is
kept WITH A SWITCH rather than as a code path that rots, and OFF is what is being kept.

THE ALTERNATIVES, THEIR PRICES AND THE MEASUREMENT THAT WOULD SETTLE THE CHOICE ARE WRITTEN OUT
ONCE, AT ckpt/api.py::REFUSE_NEGATIVE_PERIOD, and are not restated here: CKPT is where this question
was opened and where the first of the five refusals shipped. WHAT IS THIS FILE'S OWN, and the reason
the name is spelled here rather than imported: tests/test_ownership.py::check_o10_no_backdoor_imports
forbids FAB to import ckpt, so the five switches are five per-package policies that happen to share
a default, each governing only its own package's lever. This one governs FAB_MANAGE_EVERY and
nothing else, and turning it off here leaves the other four refusing.

IT IS NOT THE OFF SWITCH FOR THE FABRIC OR FOR ITS MANAGEMENT PASS. FAB_ON removes the fabric from
the forward path and FAB_GROW freezes the population; this constant touches neither, and it does not
touch FAB_MANAGE_EVERY=0 in either position.

THE COST, SO IT IS NOT DISCOVERED: turning it off is a CODE EDIT. There is no
FAB_REFUSE_NEGATIVE_PERIOD, no census row and no row in the generated lever document -- deliberately,
because a lever per package would be five environment names for one decision and would make "some
accessors refuse and some do not" a reachable configuration.
"""


# ==================================================================================================
# WHAT A NON-FINITE FLOAT LEVER WAS MEASURED TO DO, PER LEVER
# ==================================================================================================

_NONFINITE_MEASURED = {
    "FAB_ALPHA":
        "the residual mixing coefficient of one fabric step, `h <- norm(h + alive*(alpha*(mixture - "
        "h)))`, multiplied UNGUARDED in fabric/api.py::forward -- one pass takes aux_loss, the "
        "composed objective and 19 of 23 gradient-carrying tensors non-finite, and writes NaN "
        "PERMANENTLY into pop.cent through the grounded update in the same pass",
    "FAB_CENT_EMA":
        "the centroid EMA rate, multiplied unguarded in fabric/api.py::_ground_update and written "
        "back into the routing centroid BUFFER pop.cent -- one pass, aux nan, composed nan, 19/23 "
        "gradients non-finite, pop.cent PERMANENTLY non-finite, while the fab.discover gate reports "
        "'armed, did not fire (0 handover(s))' for the pass that poisoned every centroid it touched",
    "FAB_ROUTE_REGION_W":
        "the weight on the signature-region cosine term in fabric/api.py::_entry_logits -- every "
        "entry logit is non-finite, the softmax over them is nan, and the nan reaches pop.cent "
        "through the grounded update: aux nan, composed nan, 19/23 gradients non-finite, pop.cent "
        "PERMANENTLY non-finite",
    "FAB_HALT_MAX":
        "the halt-mass ceiling, reached as `ph = raw.clamp(max=halt_max)` in fabric/api.py::forward "
        "-- clamp(max=nan) is nan and clamp(max=-inf) is -inf, so the halted mass that multiplies "
        "the residual and the per-hop vote is non-finite: aux nan, composed nan, 19/23 gradients "
        "non-finite, pop.cent PERMANENTLY non-finite. At +inf it is instead bit-identical to the "
        "default on the measured pass and the CEILING IS SIMPLY GONE, which is the reading "
        "fabric/levers.py::FABLevers gives halt_max: a barrier and not a preference, because an "
        "expert that receives no gradient can never become worth routing to",
    "FAB_BAL_FLOOR":
        "the permanent floor under the load-balance pressure, reached as `max(floor, 1.0 - "
        "step_n/max(1, warm_n))` in fabric/api.py::_decay_to_floor -- Python's max KEEPS ITS FIRST "
        "ARGUMENT when the comparison is False and every comparison with NaN is False, so max(nan, "
        "x) is nan: aux nan, composed nan, 17/23 gradients non-finite (pop.cent survives this one). "
        "At +inf the scale is inf and aux is inf. At -inf the floor is DELETED and the defect is "
        "LATE: bit-identical to the baseline at step_windows=1 and, at step_windows=100000 with "
        "bal_warm at its default, the balance scale is -24.0 and aux_loss is NEGATIVE (-0.196 "
        "against +0.497), i.e. the objective PAYS the population to collapse onto one expert -- "
        "which is bit-for-bit the harm build() refuses FAB_BALANCE<0 for",
    "FAB_SPAWN_MULT":
        "the relative half of the spawn threshold, `if gap < max(spawn_mult*typ, spawn_floor)` in "
        "fabric/api.py::_spawn_check -- max(nan, floor) is nan and `gap < nan` is False, so the test "
        "SPAWNS UNCONDITIONALLY on every query and the absolute floor is bypassed entirely (measured "
        "at these widths: two forward passes, two spawns, n_live 6 -> 8, fab.spawn_declined 0), "
        "while the gate renders a threshold that was never used",
    "FAB_SPAWN_FLOOR":
        "the absolute half of the same threshold -- max(spawn_mult*typ, nan) returns spawn_mult*typ, "
        "so the floor whose declared purpose is 'so a degenerate population cannot spawn on every "
        "query' is SILENTLY DELETED while the gate prints 'floor=nan' as though it were in force; "
        "at +inf the threshold is inf, spawn can never fire again, and the gate reports "
        "'armed, did not fire' -- the armed-but-0 state standing in for UNREACHABLE",
    "FAB_ROUTE_T":
        "the one temperature for three operators, floored as `max(1e-3, route_t)` in "
        "fabric/api.py::_entry_logits and ::_halt_logit. At +inf every routing logit and the halt "
        "logit are exactly 0.0, so the population is routed UNIFORMLY -- there is no routing "
        "decision left -- while Gate fab.route_learned still prints FIRED. At nan and -inf the same "
        "max keeps 1e-3 and the pass is bit-identical to the already-legal FAB_ROUTE_T=0, so "
        "refusing those two removes no configuration: 0 already spells it",
    "FAB_PRESSURE":
        "the occupancy setpoint. This lever does not reach here at nan or +/-inf: it is consumed "
        "DURING spine/assemble.py::build by the FAB.d_operating_population coupling, which calls "
        "spine/derive.py::operating_population, so the refusal that fires is that function's and it "
        "names the quantity rather than this lever",
}
"""Per-lever, what a nan or an inf was MEASURED to do -- quoted into build()'s refusal for whichever
levers the operator actually set. Nine entries against 43 float levers, and the gap is the honest
part: the other 34 are refused on the same rule with no measurement of their own. THE SET WITHOUT A
LIVE READER SHRANK ON 2026-09-17 and this sentence moved with it: FAB.grow_check and
FAB.own_lr_scale have bodies, so z, plateau, new_frac, parent_max, mut, mut_big, mut_big_p, xover,
birth_jitter, lr_cycle, lr_gamma, lr_amin, lr_maxr and lr_boost are now read on a real flush and a
nan in any of them reaches arithmetic rather than freezing into the Config -- WHICH IS WORSE AND NOT
BETTER, and is exactly why the refusal above enumerates every float lever rather than a list. What
is still unread is FAB.manage's and FAB.contribution's: the cull fraction, the merge distance and
the two error tolerances, which freeze a nan into the Config and arm the day a body is written (one
of them, FAB_COMP_EMA, already crosses a package boundary as DOM.d_comp_ema before this function
runs, and is read here by FAB.observe as well). The remaining eleven are the magnitude levers whose
nan/+inf refusal build() already carried.

WHAT THIS DOES NOT SAY, AND MUST NOT BE READ AS SAYING. Refusing nan/+inf/-inf closes FOUR VALUES
PER LEVER AND LEAVES THE MECHANISM OPEN. A FINITE value does the same damage and worse: measured on
this package's own sweep, FAB_ALPHA=1e26 gives aux=0.5150710 and composed=2.943258 -- an
ordinary-looking loss pair no report would flag -- over a population whose gradient tensors are
already 15/23 poisoned, while 1e28 and nan are indistinguishable from each other at 19/23. So no lever below is
'safe', 'bounded' or 'validated' after this refusal; each is exactly four values less open than it
was. A declared per-lever domain is the general answer and is the owner's open question."""


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


@dataclasses.dataclass(frozen=True)
class ManageReport:
    """What ONE selection pass did. FROZEN, for GrowReport's reason: a caller that can write to this
    can change what the run reported.

    THE THREE SPARES ARE THREE FIELDS AND NOT A TOTAL, because they are three different reasons an
    expert survived a cull it was ranked into -- it was carrying load (contrib), it was better than
    the population (comp_protect), or it was mid-shift (shift_tol). A run where every survivor was
    spared by the shift test is a run adapting to new material; one where every survivor was spared
    by contrib is a run whose ranking disagrees with its own load measure. One number cannot say
    which, and goal B is the difference.

    `cull_gate` CARRIES THE ARITHMETIC AND NOT THE VERDICT, which is what lets a pass that did not
    open the gate still be read: derive.cull_gate_open takes (n_live, slots, pressure) and TWO
    conditions live in it -- n_live <= 2 is a FLOOR, not a pressure test -- so "the gate was shut"
    has two causes and the string says which. It is recorded EVERY pass, open or not, because a run
    above pressure for most of its length and below it at the end must not print "unreachable".

    NO COUNTER COPY. The DID IT FIRE ledger lives on Population.counters; this record is what ONE
    pass did, and the counters are cumulative. fab.rescued is the case that forces the distinction:
    ISSUES P1-M57 is a gate armed on a per-pass snapshot that discarded a nonzero cumulative count.
    """
    merged: int = 0
    merge_declined_grace: int = 0
    merge_declined_residual: int = 0
    cull_fail: int = 0
    cull_util: int = 0
    spared_contrib: int = 0
    spared_comp: int = 0
    spared_shift: int = 0
    rescued: int = 0
    deepened: bool = False
    eligible: int = 0
    cull_gate: str = ""
    manage_every: int = 0
    manage_period_flushes: object = None


@dataclasses.dataclass(frozen=True)
class GrowReport:
    """What ONE growth check asked for and what the population actually delivered. FROZEN.

    THE ASK AND THE DELIVERY ARE TWO NUMBERS AND BOTH ARE HERE, which is the whole reason this
    record exists rather than an integer. The old tree applied the soft cap and the new_frac budget
    at the CALL SITE, after `n_regr` had already been incremented inside step() (:7444-7470), so a
    regression whose entire burst was declined still printed as a regression that FIRED -- and the
    diagnostic written to catch exactly that was gated on n_regr being zero, so it stayed silent in
    the one case where it was needed. `asked_regression` against `grown_regression` is that pair,
    per leg, and `declined_cap` / `declined_newfrac` say which clamp took the difference.

    `blackout_open` AND `blackout_left` ARE CAP'S HALF OF Q-FAB-6 AND ARE NOT DECORATION. CAP.observe
    takes a `blackout` BOOLEAN and CAP declares no blackout-window lever of its own; in the old tree
    the boolean was `(step - fabgrow.blackout) < fabgrow.cool` (:7397), i.e. computed from FAB's
    `cooldown` at a foreign call site. These two fields are what let the root JOIN a value FAB
    computed with FAB's own lever instead -- the route ROW_ARGUMENTS_ELSEWHERE["CAP.observe"] names
    ("one field on GrowReport and one root join"). `blackout_left` is in units.Windows' unit and is
    an int, because a boolean alone cannot say how long the state still has to run.

    WHAT THIS RECORD DELIBERATELY DOES NOT CARRY, and the absence is a contract statement rather
    than an omission: the READING. docs/04_CONTRACT.md's ROW_ARGUMENTS_ELSEWHERE["CAP.observe"] says
    "GrowReport carries asks, deliveries and decline reasons, not the reading", and CAP.observe's
    `improving` -- (slow - fast)/|slow| off the two EMAs this package now maintains inside
    fabric/api.py::grow_check -- is therefore still without a producer. Adding a field for it here
    would close that gap and would also contradict the sentence the deferral of CAP.observe rests
    on, so it is NOT taken silently: the EMAs are on the counter ledger (fab.grow_slow, fab.grow_fast,
    fab.grow_improving) where a report can read them, and the field is the owner's call.

    NO COUNTER COPY, for FabricOut's reason: the DID IT FIRE ledger lives on Population.counters and
    a second copy on a per-pass record is a second source of truth the report would have to choose
    between. `gates` is per-call because a gate's ARITHMETIC is about the call that evaluated it.
    """
    asked_regression: int = 0
    asked_stall: int = 0
    grown_regression: int = 0
    grown_stall: int = 0
    declined_cap: int = 0
    declined_newfrac: int = 0
    replicated: int = 0
    crossed: int = 0
    random_born: int = 0
    parent_quota_refusals: int = 0
    distinct_parents: int = 0
    blackout_open: bool = False
    blackout_left: int = 0
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

    # THE LAST EIGHT ARE RE-EARNED STATE, NEVER CHECKPOINTED -- fabric/api.py::state_dict names
    # them as "the identity cache, halt_ema, the routing-mix samples", plus `learn_window` and
    # `pass_gates` which that sentence now names too. They are slots rather than ad-hoc attributes because __slots__ is
    # closed: `pop._kc = ...` raises AttributeError, so a cache invented at the point of use would
    # be a crash on the first routed window rather than a design. ident/ident_step/ident_live are
    # the emb_every cache the old tree carried as _kc/_kstep/_kn (self_organize.py:1938-1953);
    # halt_ema is its _mass_ema; `learn_window` is the window index of the last gradient-carrying
    # training pass, which fabric/api.py::forward compares against to refuse a second one.
    # `growth` AND `comp_glob` WERE ADDED 2026-09-17 WITH THE BODIES THAT READ THEM, and they are
    # NOT re-earned: both are checkpointed by fabric/api.py::state_dict beside the books. The module
    # docstring's RECORD TYPES block has listed "the growth machine" among this record's fields for
    # the whole life of the rebuild and nothing allocated it -- the same shape as `dom_of` being an
    # int per expert while the docstring specified `dom_of[e].add(...)`, and invisible for the same
    # reason: its only reader was a stub. There is no writing around it at a point of use, because
    # __slots__ is closed and `pop.growth = {...}` from outside this class is an AttributeError.
    # comp_glob is the population competence EMA fabric/api.py::observe's docstring requires ("comp
    # per expert and the population EMA comp_glob, both at rate comp_ema") and fabric/api.py::manage's
    # comp_protect spare compares against; the old tree kept it on the assembler (:6932).
    __slots__ = ("A", "B", "cent", "n_live", "cap", "depth_now", "born", "use", "uage", "dom_of",
                 "ef", "es", "comp", "contrib", "births", "rescued", "parent", "mutscale",
                 "growth", "comp_glob",
                 "modules", "counters", "rng", "on", "hop_arm", "gates", "halt_b",
                 "ident", "ident_live", "ident_step", "ident_graph", "halt_ema", "marks",
                 "learn_window", "pass_gates")

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
        # THE GROWTH MACHINE: WATCH -> BURST -> RECOVER, and the two clocks that keep the common
        # event from silencing the rare one. `last` is the spacing clock BOTH legs set; `last_regr`
        # is the REGRESSION's OWN, and it exists because sharing one let a routine stall 772 windows
        # earlier suppress an injected regression (self_organize.py:2921-2926) -- the event goal B
        # depends on, refused by the event that happens all the time. `births` is the sliding record
        # (window, parent) that BOTH birth budgets are measured on: new_frac over the last `cooldown`
        # windows, parent_max over the last `birth_win` births. `spawned_seen` is the fab.spawned
        # count as of the previous check, which is how fabric/api.py::grow_check charges a
        # spawn-by-specification birth against the newborn budget it did not go through.
        # A PLAIN DICT AND NOT A CLASS, deliberately: every value is a float, an int, a string, None
        # or a list of pairs, so state_dict can write it and load_state_dict can read it back
        # without a second record type that torch.save would pickle by reference to this module.
        self.growth = {
            "fast": None, "slow": None, "dev": 0.0, "n": 0,
            "state": "W", "t0": None, "last": None, "last_regr": None,
            "births": [], "spawned_seen": 0,
        }
        # None AND NOT 0.0: competence here is a LOSS (lower is better, self_organize.py:3694 spares
        # on `comp[d] < comp_glob`), so a population EMA seeded at zero would read as a population
        # that models everything perfectly and no expert could ever beat it. None means "no window
        # has been attributed yet", which is a different statement and is the one that is true.
        self.comp_glob = None
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
        # THE WINDOW OF THE LAST GRADIENT-CARRYING TRAINING PASS, and None until there is one. Read
        # only by fabric/api.py::forward's one-pass-per-window refusal; re-earned like the identity
        # cache, because a resumed run's first routed pass is at a window no pass in this process
        # has seen and carrying the number across a restart could only produce a false refusal.
        self.learn_window = None
        # THE LAST TRAINING PASS'S GATES, REPLACED (NEVER APPENDED) BY fabric/api.py::forward and
        # rendered by fabric/api.py::counters. Until 2026-09-24 they lived only on FabricOut.gates,
        # which the loop never read -- so the gates that said "no head was supplied" on every pass
        # of every run were never printed, while fab.ind_applied and fab.hopsup_applied printed a
        # present-and-0 that G4 reads as "armed, did not fire". Re-earned: the first training pass
        # of a resumed run writes it, and an empty tuple before that says no pass has run.
        self.pass_gates = ()
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

        EMPTY AT FAB_ON=0 (Q-FAB-11, RESOLVED 2026-09-24). The switch's help says "off removes it
        entirely", and until this line the off arm handed OPT all 8,929,984 fabric parameters of
        the shipped 10,130,057 -- the banner counted them as trainable, AdamW kept moments for
        them and OPT_WEIGHT_DECAY decayed them, for a forward that is the identity and a gradient
        that is identically None. The pool is still ALLOCATED (and checkpointed) on that arm, so
        every consumer of the record -- MEM's owner count, CAP's n_live, CKPT -- reads the same
        shapes on both arms; what the arm removes is everything that trains or acts. FAB_NORM_ONLY=1
        keeps the list: that control arm's point is that the population stays in the optimizer.
        """
        if not self.on:
            return []
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

    ELEVEN MAGNITUDE LEVERS ARE RANGE-CHECKED HERE AND A NEGATIVE ONE IS REFUSED, WHICH IS THE ONLY
    REASON THIS FUNCTION READS THEM -- their behaviour is entirely `forward`'s. They split two ways
    and the body records the measurement for each: FAB_BALANCE, FAB_PONDER and FAB_EMB_VAR multiply
    their loss terms UNGUARDED, so a negative one applies the term with its sign reversed and the
    objective pays for expert collapse, for deeper walks and for a collapsed identity space
    respectively; the other eight are guarded at `> 0.0`, so a negative is bit-identical to 0.0 in
    aux, in every counter and in every gate, and its whole effect is that the gate prints
    "ec_w=-1.0" one line above "FAB_EC_W=0". Neither is a configuration of this package. The
    precedent and the ground are src/capacity/api.py::new_valve's refusal of a negative CAP_LIFT.

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

    TWO REFUSALS WERE WIDENED HERE ON 2026-09-06, AND THE LIST OF LEVERS THIS FUNCTION DECLINES TO
    CHECK IS NOW EMPTY. The first is the non-finite rule: it covered ELEVEN named magnitude levers at
    nan and +inf, and the comment that added it LISTED THE SIX IT DECLINED TO CHECK -- FAB_ALPHA,
    FAB_ROUTE_T, FAB_HALT_MAX, FAB_BAL_FLOOR, FAB_SPAWN_FLOOR, FAB_ROUTE_REGION_W. Five of those six
    carried the identical defect (.rework/audits/sweep_fabric.json): one forward pass, aux_loss nan,
    the composed objective nan, 17-19 of 23 gradient-carrying tensors non-finite, and for four of
    them pop.cent PERMANENTLY non-finite -- a population that correcting the lever afterwards cannot
    recover. The rule is now over EVERY float lever the package declares (43 of the 82), enumerated
    from the declarations through spine/lever.py::Config.keys and ::Config.lever so no second list
    exists to go stale, with the 26 int and 12 bool levers refused earlier by
    spine/lever.py::Lever.coerce and the one str lever by its own `choices=`.
    THE SECOND IS A FLOOR OF ONE ON SIX COUNTS -- FAB_N0, FAB_SLOTS, FAB_RANK, FAB_DK, FAB_EMB_HID
    and FAB_HOPS -- and no finiteness rule could ever have reached it: all six are finite ints that
    pass every type check, and FAB_RANK=0 builds experts with no parameters and a nan loss, FAB_DK=0
    deletes routing identity and returns a nan loss, and FAB_EMB_HID=0 collapses every expert's
    identity to one point SILENTLY, with a finite aux and every gate still printing FIRED. Each
    refusal quotes its own measurement. NEITHER CLAIMS THE LEVER IS SAFE: between them they close
    four values on 43 levers and one arm of six more, and a FINITE value does the same damage --
    FAB_ALPHA=1e26 prints aux 0.5150710 and composed 2.943258, an ordinary-looking pair, over a
    population already 15 of 23 gradient tensors poisoned. A declared per-lever domain is the general
    answer and is the owner's open question.

    LEVERS READ: on, norm_only, n0, slots, rank, dk, emb_hid, pressure, grow, halt, lr_own, hop_mode,
                 depth0, hops, balance, ponder, emb_var, ec_w, explore, div_w, hop_sup,
                 ind_w, ae_w, dom_frac,
                 alpha, bal_floor, birth_jitter, cent_ema, comp_ema, cull_frac, depth_eps, discover,
                 err_fast, err_slow, fail_tol, halt_max, lr_amin, lr_boost, lr_cycle, lr_gamma,
                 lr_maxr, merge_dist, mut, mut_big, mut_big_p, new_frac, parent_max, plateau,
                 rescue, route_region_w, route_t, shift_tol, spawn_floor, spawn_mult, xover, z
                 (the second block is every remaining FLOAT lever, read ONLY for the finiteness
                 refusal above and for nothing else -- their behaviour is forward's, manage's or, for
                 the 23 with no live reader yet, P4's. They are named here because this function does
                 now read them, and a LEVERS READ line that omitted them would be the claim-without-a-
                 read this block's own history is made of, in reverse. `discover` MOVED into this
                 block on 2026-09-14: its negative refusal retired to its own declaration, and the
                 only thing this function reads it for now is the finiteness sweep)
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

    # ELEVEN MAGNITUDE LEVERS MAY NOT BE NEGATIVE -- TEN OF THEM REFUSED BY THE TABLES BELOW AND
    # THE ELEVENTH, FAB_DISCOVER, BY ITS OWN DECLARATION SINCE 2026-09-14 (the paragraph above those
    # tables says why the ruling moved and src/fabric/levers.py::FABLevers carries the measurement
    # it moved with) -- AND THE REFUSAL IS AT STARTUP FOR THE REASON
    # src/capacity/api.py::new_valve gives for CAP_LIFT, in its own words about its own lever: "A
    # valve that lowers on evidence it should raise is not a configuration of this mechanism; it is
    # a different mechanism wearing its name." Read here as: a mechanism running backwards on the
    # evidence it should run forwards is a defect arriving through a lever VALUE rather than through
    # a guard, and a guard is not what catches it -- a refusal is. Each of
    # these eleven is a WEIGHT ON AN ADDITIVE TERM OF THE OBJECTIVE or a RATE/SHARE, declared in
    # fabric/levers.py as the size of a pressure; there is no reading of any of them under which a
    # negative number is that pressure. Decided per lever and measured per lever, not as a blanket
    # -- the eleven split into TWO groups that fail in two different ways, and both were measured on
    # one routed pass at FAB_N0=8/SLOTS=16/RANK=4/DK=8/SOCIETY=1/HOPS=3/DEPTH0=3/CHAIN_K=2 against
    # the same pass at the same lever set to exactly 0.0:
    #
    # (1) THE TERM IS APPLIED AND ITS SIGN REVERSES -- the objective pays for the opposite of what
    #     the lever's own sentence says it buys. `aux = aux + balance_w * bal_scale * bal`,
    #     `aux = aux + ponder_w * ponder_scale * (depth_acc / ...)` and _ae_loss's
    #     `+ emb_var * (var + cov)` are all UNGUARDED multiplications:
    #       FAB_BALANCE=-1.0  aux 0.9000001 vs 1.9836745 at 0.0 -- routing mass pushed INWARD,
    #                         paying the population to collapse onto one expert, which is the exact
    #                         inverse of "every expert keeps accruing use-age instead of a few
    #                         absorbing all traffic" and is hostile to goal B at its root.
    #       FAB_PONDER=-1.0   aux 1.9941328 vs 1.9945074 at 0.0 -- the charge on routed depth
    #                         becomes a SUBSIDY on routed depth: the chain is paid to take hops it
    #                         does not need -- fabric/levers.py::FABLevers declares `ponder` a
    #                         "Charge on routed depth", and this is that sentence read backwards.
    #       FAB_EMB_VAR=-1.0  aux 1.0422100 vs 1.5183606 at 0.0 -- the anti-collapse term becomes a
    #                         PRO-collapse term, and a collapsed identity space is the measured
    #                         failure fabric/api.py::_var_cov exists for (nearest-neighbour distance
    #                         0.000, spawn firing on every query).
    #     FAB_BALANCE is the worst of the three because its GATE also misreported it: on a separate
    #     six-lever sweep at the shipped FAB_SOCIETY=0 (all six of the reasons in group (2) set
    #     negative at once), fab.balance printed fired=False beside a reason that asserted
    #     "FAB_BALANCE=0: no load-balance pressure" -- the reason text hardcoded the 0 rather than
    #     printing the value it read -- while the pass returned a NEGATIVE total aux, -1.0836706,
    #     all of it the reversed balance term since the other five in that sweep are inert; and
    #     `if balance_w > 0.0` held fab.balance_nonzero -- THE C2 ALARM -- at 0, which is the
    #     reading that means "the term is multiplying a zero". A reversed term reported as an
    #     absent one is the wrong-measurement family with the loss itself as the subject.
    #
    # (2) THE TERM IS GUARDED AT `> 0.0` AND A NEGATIVE IS EXACTLY "OFF" -- aux, every counter and
    #     every gate bit-identical to the same run at 0.0 for all eight of FAB_EC_W, FAB_EXPLORE,
    #     FAB_DISCOVER, FAB_DIV_W, FAB_HOP_SUP, FAB_IND_W, FAB_AE_W and FAB_DOM_FRAC. MEASURED on
    #     eight and REFUSED BELOW ON SEVEN: FAB_DISCOVER's negative is refused one layer earlier by
    #     its declared domain, and the measurement in this paragraph is the one that moved there
    #     with it. Nothing runs
    #     backwards, so the defect is entirely in the REPORT: each gate prints the operator's own
    #     negative in its `value` and then a reason asserting the value is 0 one line below it --
    #     "ec_w=-1.0" over "FAB_EC_W=0: allocation by loss pressure only". REFUSING rather than
    #     widening the eight reasons, for the reason capacity gives in the same place: it REMOVES NO
    #     CONFIGURATION, because a negative here is bit-identical to a 0 that is already legal and
    #     already spells the same thing, so nothing an operator can ask for is lost; and it makes the
    #     false reason impossible to produce instead of correct once. The reasons are ALSO widened
    #     to print the value they read (see the gates in `forward`), so neither half depends on the
    #     other being right.
    #
    # ==============================================================================================
    # EVERY FLOAT LEVER THIS PACKAGE DECLARES MUST BE FINITE, AND THE LIST OF THE ONES THIS FUNCTION
    # DECLINES TO CHECK IS NOW EMPTY.
    # ==============================================================================================
    # THE PREVIOUS VERSION OF THIS REFUSAL LISTED THE LEVERS IT DID NOT CHECK, AND FIVE OF THE SIX ON
    # THAT LIST CARRIED THE IDENTICAL DEFECT. The sentence that stood here read "Nor does this touch
    # the levers whose negative side is a different question -- FAB_ALPHA, FAB_ROUTE_T, FAB_HALT_MAX,
    # FAB_BAL_FLOOR, FAB_SPAWN_FLOOR, FAB_ROUTE_REGION_W, FAB_MUT, FAB_PRESSURE -- because that is a
    # range ruling this body has not measured". The 2026-09-05 lever-domain sweep measured it
    # (.rework/audits/sweep_fabric.json): FAB_ALPHA, FAB_CENT_EMA, FAB_ROUTE_REGION_W, FAB_HALT_MAX
    # and FAB_BAL_FLOOR each take ONE forward pass to make aux_loss nan, the composed objective nan
    # and 17-19 of 23 gradient-carrying tensors non-finite, and the first four write NaN PERMANENTLY
    # into pop.cent -- so the population cannot be recovered by correcting the lever afterwards. The
    # FAB_BALANCE=nan repair was therefore RELOCATED, NOT CLOSED, and the file said which levers it
    # had relocated it past. That is the shape this block ends: the rule below is over EVERY float
    # lever the package declares, enumerated from the declarations themselves through
    # spine/lever.py::Config.keys and ::Config.lever, so a float lever added tomorrow is covered
    # without anybody remembering this paragraph, and there is no second list to go stale.
    #
    # WHY "EVERY FLOAT" IS A PER-LEVER RULING AND NOT A BLANKET. It is per-lever because the sweep
    # enumerated this package's declared sentinels and EVERY ONE OF THEM IS A ZERO, not an infinity:
    # depth0=0 (no curriculum), dom_frac=0 (breadth cap off), ec_w/hop_sup/rescue=0 (off),
    # route_region_w=0 (routes on predicted weights alone), and the guard-floored zeros of route_t,
    # bal_warm, ponder_warm, emb_every, chain_k, ens_k and ind_k. No FAB lever uses +inf to mean "no
    # cap"; the three that come closest -- halt_max, spawn_floor, spawn_mult -- all BREAK at inf
    # rather than meaning anything by it, and _NONFINITE_MEASURED records how. The only values this
    # takes away that are harmless today are FAB_ROUTE_T at nan and -inf, which are bit-identical to
    # the already-legal FAB_ROUTE_T=0 (`max(1e-3, route_t)` keeps 1e-3 because `nan > 1e-3` is
    # False), so nothing an operator can ask for is lost.
    #
    # WHAT IS REFUSED IS FOUR VALUES PER LEVER AND NOTHING MORE, AND THIS BODY DOES NOT CLAIM
    # OTHERWISE. FAB_ALPHA=1e26 -- finite, ordinary-looking, a loss pair of 0.5150710 and 2.943258
    # that no report would flag -- already leaves 15/23 gradient tensors non-finite, which is WORSE
    # than +inf's honest nan. So after this block no lever below is safe, bounded or
    # validated; each is four values less open. The general answer is a declared per-lever domain and
    # it is the owner's open question, not this function's.
    #
    # THE INT LEVERS ARE NOT IN THIS SWEEP AND ARE NOT EXEMPT EITHER: spine/lever.py::Lever.coerce
    # resolves an int lever as `int(float(raw))` and refuses nan (ValueError) and +/-inf
    # (OverflowError) by the lever's own owned name before any Config exists, so a second check here
    # would be an untrippable guard. Bools coerce every spelling and the one str lever (hop_mode)
    # carries `choices=` plus the NotBuilt refusal above. That accounts for all 82 declarations:
    # 43 float here, 26 int and 12 bool in coerce, 1 str in choices.
    _nonfinite = []
    for _field in fab.keys():
        if _field.startswith("d_"):
            continue                        # a wire is another package's number arriving, not a lever
        _decl = fab.lever(_field)           # spine/lever.py::LeverView -- default, unit, OWNED env name
        if not isinstance(_decl.default, float):
            continue
        _v = float(getattr(fab, _field))
        if not math.isfinite(_v):
            _nonfinite.append((_decl.env_name, _v))
    if _nonfinite:
        raise LeverError(
            f"FAB: non-finite lever(s) "
            f"{', '.join(f'{k}={v}' for k, v in _nonfinite)}. A nan or an infinity is not a "
            f"magnitude, a rate, a share, a temperature, a threshold or a ceiling, and this package "
            f"declares no float lever for which any of the three is a reading -- every declared "
            f"sentinel in fabric/levers.py::FABLevers is a ZERO. WHAT EACH ONE WAS MEASURED TO DO: "
            + " || ".join(f"{k}={v}: " + _NONFINITE_MEASURED.get(
                k, "no measurement of its own on this table: either it is read on a live path "
                   "whose nan was never driven (FAB.observe, FAB.grow_check and FAB.own_lr_scale "
                   "have bodies as of 2026-09-17, so their levers reach arithmetic), or its only "
                   "readers are FAB.manage and FAB.contribution, which are still P4 stubs -- there "
                   "the value freezes into the Config and arms the day a body is written")
                for k, v in _nonfinite)
            + ". REFUSED AT STARTUP AND NOT DESCRIBED BY A GATE, because a Gate reason is a report "
              "and the mechanism still runs: at FAB_ALPHA=nan the fab.halt gate prints the verdict "
              "FIRED over a mass it reads as nan, and at FAB_CENT_EMA=nan fab.discover prints "
              "'armed, did not fire (0 handover(s))' for the pass that just poisoned every centroid "
              "it touched. WHAT THIS REFUSAL DOES NOT CLAIM: it closes these four values and leaves "
              "the mechanism open. FAB_ALPHA=1e26 is finite, prints an ordinary loss pair "
              "(aux 0.5150710, composed 2.943258) and already leaves 15 of 23 gradient tensors "
              "non-finite -- worse than +inf, which at least comes back nan. Set the lever to a "
              "finite value; a declared per-lever domain is the general answer and is open.")

    # WHAT IS NOT REFUSED, AND WHY THE RULE IS NOT "FRACTION MEANS 0..1". U.FRACTION is a LABEL the
    # census renders and not a bound -- src/sig/levers.py and src/tok/levers.py both say so of their
    # own shares, and capacity leaves CAP_LIFT > 1 legal on exactly that ground. Nothing here refuses
    # a value ABOVE any of these; FAB_BALANCE=5.0 is a large pressure and still the pressure the
    # lever names. NOR IS THE NEGATIVE SIDE OF EVERY FLOAT SETTLED HERE, and this is a NEGATIVE
    # ruling and not a list of levers left unchecked -- the finiteness rule above covers all 43. The
    # ten below -- and FAB_DISCOVER, the eleventh of the same ruling, at its declaration -- are
    # refused negative because each is a weight on an additive term or a share and a negative one is
    # measured to reverse or to misreport it.
    # THE EIGHT THAT ARE NOT REFUSED NEGATIVE ARE NOW MEASURED, WHICH THEY WERE NOT WHEN THIS
    # PARAGRAPH FIRST SAID SO, and the measurement is written down here rather than turned into a
    # guard, because a refusal is a RULING and this round's was the finiteness one. Driven one at a
    # time at FAB_N0=6 FAB_SLOTS=12 FAB_CHAIN_K=3 FAB_DEPTH0=3 FAB_HOPS=4 over two real forward
    # passes, against a baseline of aux 0.5134152173995972 and sum|g|max 1.3968892609970744:
    #   FAB_HALT_MAX=-0.9        `raw.clamp(max=-0.9)` makes the halted mass NEGATIVE, so
    #                            `alive = alive * (1 - ph)` AMPLIFIES the residual instead of
    #                            damping it: sum|g|max 2.5214699913394156, aux 0.5134174823760986.
    #                            A ceiling that becomes a negative mass. The worst of the eight.
    #   FAB_ROUTE_REGION_W=-1.0  the region term applied with its sign REVERSED -- routing scored
    #                            toward the experts whose region is least like the material:
    #                            aux 0.5095041990280151, sum|g|max 1.202592107085124.
    #   FAB_BAL_FLOOR=-0.15      the bounded form of the -inf defect above, and equally LATE:
    #                            bit-identical to the baseline at step_windows=1, and at
    #                            step_windows=100000 aux 0.48843273520469666 against
    #                            0.4970445930957794 -- the balance term with its sign reversed.
    #   FAB_ALPHA=-0.5           the residual step runs BACKWARD, h moving away from the mixture:
    #                            aux unchanged (it is not an aux term), sum|g|max 1.3063406257114876.
    #   FAB_PRESSURE=-0.45       operating_population answers 3 -- its floor -- for a setpoint that
    #                            has no reading, and cull_gate_open is then true at every occupancy.
    #   FAB_ROUTE_T=-0.1, FAB_SPAWN_FLOOR=-0.02, FAB_MUT=-0.25   INERT: bit-identical to the baseline
    #                            in aux, in sum|g|max and in every counter. The first two are floored
    #                            by a `max` at their point of use and the third has no live reader.
    # So four of the eight are the same reversed-term class the eleven are refused for and three are
    # exactly "off", which is the same split the eleven have. Refusing them is a defensible next
    # ruling and it is NOT taken here; what is not acceptable is the sentence that stood in this
    # place claiming they were unmeasured, which is why the numbers are above it.
    # ==============================================================================================
    # FAB_DISCOVER IS NOT IN THE TABLE BELOW ANY MORE, AND ITS ABSENCE IS THE RULING RATHER THAN AN
    # OVERSIGHT. RETIRED 2026-09-14; WHAT IT REFUSED IS NOW REFUSED EARLIER, BY ITS DECLARATION.
    # ==============================================================================================
    # It was the third entry of `_gated_off`. src/fabric/levers.py::FABLevers now declares
    # `discover` with `domain=(0.0, 2.0)` -- a COSINE DISTANCE, whose ceiling is 2.0 and not the 1.0
    # its U.FRACTION label invites -- and spine/lever.py::Lever.coerce checks a domain at the FIRST
    # read, before a Config exists and long before this function runs. So one fact was standing in
    # two places and the SECOND of them could never run:
    # tests/test_ownership.py::check_o15_domain_agrees_with_read_site read both intervals and
    # reported it -- this clause covers (-inf, 0.0), the declaration admits only [0.0, 2.0], nothing
    # was left for the clause to refuse. That is the untrippable-guard family, 60 of the founding
    # survey's 475 records, arrived at by an edit rather than found in the old tree.
    #
    # THE FORK O15 STATES IS RETIRE-OR-DROP AND NEVER BOTH, AND THIS IS THE ARGUMENT FOR RETIRING.
    # The pair says everything this clause said about THIS lever and one measured thing more. The
    # clause refused (-inf, 0.0); the declaration refuses (-inf, 0.0) U (2.0, inf), and the upper
    # half is not decoration -- FAB_DISCOVER=3.0 resolved on this tree until the pair landed and is
    # refused now. Dropping the pair to keep this line would therefore have REMOVED a working
    # refusal to make a check green, to save a line no environment can reach. Checked at the
    # ENDPOINTS too, because a domain is CLOSED at both ends and the two could have disagreed at one
    # point the way OPT_LR_DECAY=1.0 does: they do not. `v < 0.0` is FALSE for -0.0, and -0.0 is
    # inside [0.0, 2.0]; 0.0 and 2.0 both build; -1e-320 is refused by both. The two rules agree at
    # every value, which is what makes this pre-emption and not a disagreement.
    #
    # THE MEASUREMENT MOVED WITH THE RULING AND WAS NOT DELETED. What this clause knew about
    # discover -- that `_ground_update` guards the whole branch at `discover > 0`, so a negative is
    # bit-identical to 0.0 in aux, in every counter and in every gate, and the only thing it changes
    # is that fab.discover prints the operator's negative in its `value` beside a reason asserting
    # the value is 0 -- is quoted at the declaration, where the bound now is. A domain with no
    # argument beside it is the U.FRACTION mistake in a new costume, and this package does not ship
    # one.
    #
    # WHAT RETIRING COST, AT THE ONE DOOR A DECLARATION DOES NOT STAND IN, MEASURED AND NOT WAVED
    # AWAY. A Config that did not come from this declaration reaches this function with no coerce
    # behind it -- spine/lever.py::Config is an ordinary object and tests/test_couplings.py builds
    # one directly today -- and on THAT path a negative `discover` is now accepted here, where the
    # other ten are still refused. Nothing in src/ opens that door, and the asymmetry is a reading
    # rather than a claim: tests/test_fabric.py::check_f4_negative_magnitude_levers_refused drives
    # BOTH doors on all eleven and prints which layer answered at each.
    #
    # AND THE SHAPE MATTERS, BECAUSE ONE OF THESE TWO REFUSALS COULD NOT HAVE BEEN RETIRED THIS WAY.
    # This one is a HAND-TYPED table of names and values, so retiring a lever is deleting the entry
    # somebody typed. The finiteness refusal above is the generated one -- it enumerates every float
    # lever this package declares through spine/lever.py::Config.keys and ::Config.lever -- and
    # excluding a single lever from THAT would be writing a name back into a rule whose whole point
    # is that it has no list to go stale. It needs no exclusion: it still covers `discover`, because
    # a domain with two finite ends already refuses nan, +inf and -inf, so the two never disagree.
    _applied = (("FAB_BALANCE", float(fab.balance)), ("FAB_PONDER", float(fab.ponder)),
                ("FAB_EMB_VAR", float(fab.emb_var)))
    _gated_off = (("FAB_EC_W", float(fab.ec_w)), ("FAB_EXPLORE", float(fab.explore)),
                  ("FAB_DIV_W", float(fab.div_w)), ("FAB_HOP_SUP", float(fab.hop_sup)),
                  ("FAB_IND_W", float(fab.ind_w)), ("FAB_AE_W", float(fab.ae_w)),
                  ("FAB_DOM_FRAC", float(fab.dom_frac)))
    # `v < 0.0` AND NOT A SIGN TEST, AND A CHECK NOW DEPENDS ON THAT. -0.0 is not less than 0.0, so
    # NEGATIVE ZERO is admitted here, and it is off exactly as +0.0 is off -- MEASURED on all eleven
    # at once, one forward and one backward each: aux_loss 0.0 both ways, the composed loss
    # 2.4948575496673584 both ways, and the sum of |grad|max over both adapter banks, the halt prior,
    # every shared module, the head and the incoming representation 0.7345285937190056 both ways,
    # bit for bit. That makes {+0.0, -0.0} the ENTIRE reachable domain of the nine `<= 0.0` gate
    # branches below. The claim is unchanged for FAB_DISCOVER and the LAYER that holds it is not:
    # its `domain=(0.0, 2.0)` admits -0.0 by the same rule (`not -0.0 < 0.0`) and refuses every other
    # negative at the first read, so the nine still have exactly two reachable readings between them
    # -- eight of the nine by the line below and discover's by its declaration.
    # tests/test_fabric.py::check_f7_gate_reasons_print_what_they_read is built on precisely that: it
    # sweeps all nine levers at both zeros because two distinct readings are what make a hardcoded
    # constant in a reason detectable at all, and one reading would leave it green over the defect it
    # exists for. THE TWO DECISIONS ARE COUPLED AND THIS IS THE SENTENCE THAT SAYS SO. Tightening this
    # to `v < 0.0 or math.copysign(1.0, v) < 0` is a defensible ruling -- an operator can only have
    # typed -0.0 by accident -- but it takes F7's second reading away, and F7 will FAIL on its own
    # coverage census when it does, loudly and correctly, naming all nine gates. Whoever makes that
    # ruling owes F7 a different second value, and there is no third one in this domain to reach for.
    # Neither this body nor that check may decide it alone; it is filed in .rework/audits/j_fabric.json
    # as a question for the owner rather than settled here.
    # NOT-A-NUMBER IS NOT A MAGNITUDE EITHER, AND `v < 0.0` IS FALSE FOR IT -- which is why all
    # eleven are ALSO in the finiteness sweep above (it enumerates every float lever, so retiring
    # FAB_DISCOVER from the table below took nothing away from it), and are now caught by it at all
    # three spellings rather than at two. What that block replaced was a `v != v or v == float("inf")` over exactly
    # these eleven names: it caught nan and +inf, left -inf to the `v < 0.0` arm below (which reported
    # it as a negative magnitude rather than as an unreal one), and covered eleven of this package's
    # forty-three float levers. Measured at the suite's own widths before the widening: FAB_BALANCE=nan
    # assembled with no warning, FAB.build accepted it, aux_loss came back nan and every
    # gradient-carrying tensor on the population was non-finite -- while fab.balance printed
    # "armed, did not fire (balance=nan x warm=0.9992 vs > 0) -- FAB_BALANCE=nan: no load-balance
    # pressure", which is F1's defect and F7's defect in one rendered line. FAB_PONDER and FAB_EMB_VAR
    # did the same; FAB_DOM_FRAC=nan did not reach a gate at all, it raised a bare ValueError from
    # _breadth_ban.
    _rev = [f"{k}={v}" for k, v in _applied if v < 0.0]
    _off = [f"{k}={v}" for k, v in _gated_off if v < 0.0]
    if _rev or _off:
        raise LeverError(
            f"FAB: negative magnitude lever(s) {', '.join(_rev + _off)}. Every one of these is a "
            f"weight on an additive term of the objective or a rate, and a negative value is never "
            f"the pressure the lever names. "
            + (f"REVERSED AND APPLIED: {', '.join(_rev)} -- FAB_BALANCE, FAB_PONDER and FAB_EMB_VAR "
               f"multiply their terms UNGUARDED, so a negative one pays the objective for the "
               f"opposite of what it buys (measured at FAB_BALANCE=-1.0: aux 0.9000001 against "
               f"1.9836745 at 0.0, routing mass pushed inward, while the fab.balance gate read "
               f"'no load-balance pressure' and the C2 alarm fab.balance_nonzero stayed at 0). "
               if _rev else "")
            + (f"SWITCHED OFF AND MISREPORTED: {', '.join(_off)} -- these seven are guarded at "
               f"`> 0.0`, so a negative is bit-identical to 0.0 in aux, in every counter and in "
               f"every gate, and the only thing it changes is that the gate prints the negative in "
               f"its value beside a reason asserting the value is 0. " if _off else "")
            + f"Set the lever to 0.0 to switch the mechanism off -- that is what a negative already "
              f"does on the seven and what a negative does NOT do on the three -- or to a positive "
              f"magnitude to run it. Refused here, at startup, rather than described by a Gate, "
              f"because a Gate reason is a report and the mechanism still runs: "
              f"src/capacity/api.py::new_valve makes the same ruling for CAP_LIFT and states "
              f"the ground.")

    # ==============================================================================================
    # THE SIX COUNTS THAT MUST BE AT LEAST ONE, READ TOGETHER AND REFUSED BEFORE ANYTHING IS DERIVED
    # FROM THEM. A FINITENESS RULE COULD NEVER HAVE CAUGHT THESE: all six are ints, all six are
    # FINITE, and all six pass every type check spine/lever.py::Lever.coerce applies.
    # ==============================================================================================
    # Each was driven at 0 in a fresh subprocess through a real assembly, a real FAB.build and two
    # real FAB.forward passes (.rework/audits/sweep_fabric.json), and the measurement is quoted in
    # the refusal itself so the operator reads what their number did rather than a rule. The class is
    # the one the whole sweep is about: a value that is legal to every guard between the environment
    # and the mechanism, and that DELETES the mechanism.
    #   FAB_RANK=0    experts with ZERO PARAMETERS -- A is (cap, d, 0), B is (cap, 0, d), dW = A@B is
    #                 identically zero for the life of the run, the identity embedder's input is
    #                 2*d*rank = 0 numbers so every expert embeds to one constant, _var_cov divides
    #                 by a zero variance and aux_loss comes back nan. Measured here: A.shape
    #                 [12, 16, 0], aux nan, composed nan, sum|g|max 27153.05 against 1.397.
    #   FAB_DK=0      routing identity DELETED -- every per-expert key, the router's query and the
    #                 halt key are zero-width, `keys @ q` is a sum over nothing, the spawn test reads
    #                 the manufactured gap=1.0 typ=1.0 that _spawn_check's own docstring exists to
    #                 avoid, and aux_loss comes back nan. Measured: aux nan, composed nan.
    #   FAB_EMB_HID=0 every expert's identity COLLAPSED TO ONE POINT -- eemb is Linear(2*d*r -> 0)
    #                 then Linear(0 -> dk), so its output does not depend on the expert's weights at
    #                 all. That is precisely the collapse _var_cov and the emb_var term exist to
    #                 detect, arriving as a geometry the operator typed. It is SILENT: aux stays
    #                 finite (0.5549) and every gate still prints FIRED. Measured: sum|g|max
    #                 18509.16 against 1.397, spawn gap and typ both the manufactured 1.0.
    #   FAB_N0=0      a population of NOBODY. This function accepted it, allocated the full pool, the
    #                 two adapter banks and seven shared modules, and the refusal arrived one entry
    #                 point later as a bare ValueError out of FAB.forward on the first routed window.
    #                 That message is a good one and it is kept -- nothing may reduce a live
    #                 population to none -- but a startup value belongs to a startup refusal, and
    #                 this function already reads n0 to compute cap.
    #   FAB_HOPS=0    a hop budget of zero is A CAP THAT DOES NOT CAP: `depth = max(1, min(depth_now,
    #                 hops, 2 + n//2))` in forward silently yields ONE hop, and the gate then prints
    #                 a reason that is false about the configuration it describes -- "armed, did not
    #                 fire (depth0=3 vs hops=0) -- FAB_DEPTH0 >= FAB_HOPS: the chain already starts
    #                 at the budget", beside fab.forward.routed reporting the walk it actually took.
    #                 Measured: 1 hop over 6 experts at depth=1.
    #   FAB_SLOTS=0   `cap = max(n0, slots)` is the declared arithmetic and a cap of n0 is a fine
    #                 answer, so this one is refused for the SETPOINT it derives and not for the
    #                 pool: spine/derive.py::operating_population carries `n = max(3, n)` -- its own
    #                 docstring calls it "the same floor as the gate's n_live <= 2" -- and then
    #                 returns `min(n_slots, n) if n_slots >= 3 else n_slots`, so at slots<3 the floor
    #                 is bypassed and at slots=0 the answer is 0. Measured: fab.cap 6 with
    #                 fab.operating_population 0 and no warning, i.e. the utilization cull's setpoint
    #                 is zero and the number the run reports as its own operating size is one the
    #                 floor above it was written to make impossible. A NEGATIVE reaches the same
    #                 place and is worse: operating_population(0.45, -5) returns -5. THAT FUNCTION IS
    #                 RIGHT AT slots=2 and is pinned there by tests/test_derive.py
    #                 (`operating_population(0.45, 2) == 2` -- "two slots is all there is"), so the
    #                 refusal belongs to the lever's owner and not to the conversion.
    # NOTHING AN OPERATOR CAN ASK FOR IS LOST, which is the same ground capacity gives for CAP_LIFT:
    # 1 is legal for every one of the six and spells the smallest configuration each of them has --
    # FAB_SLOTS=1 is the same `cap = max(n0, slots)` with a setpoint of 1 rather than 0.
    n0, slots = int(fab.n0), int(fab.slots)
    rank, dk, hid = int(fab.rank), int(fab.dk), int(fab.emb_hid)
    depth0, hops = int(fab.depth0), int(fab.hops)
    _floor_one = (("FAB_N0", n0), ("FAB_SLOTS", slots), ("FAB_RANK", rank), ("FAB_DK", dk),
                  ("FAB_EMB_HID", hid), ("FAB_HOPS", hops))
    _below = [f"{k}={v}" for k, v in _floor_one if v < 1]
    if _below:
        raise LeverError(
            f"FAB: geometry/count lever(s) {', '.join(_below)} below one. Each of these six is a "
            f"COUNT the population is built out of -- founders, slots, the low-rank width, the "
            f"routing identity width, the identity embedder's hidden width and the hop budget -- and "
            f"a count below one is not a smaller configuration of this package, it is the mechanism "
            f"removed while every type check still passes. MEASURED, one at a time, at FAB_N0=6 "
            f"FAB_SLOTS=12 FAB_CHAIN_K=3 FAB_DEPTH0=3 FAB_HOPS=4 over two real forward passes "
            f"against a baseline of aux 0.5134152173995972, composed 4.414819717407227 and "
            f"sum|g|max 1.3968892609970744: FAB_RANK=0 -> every expert has zero parameters, A.shape "
            f"[12, 16, 0], aux nan, sum|g|max 27153.05; FAB_DK=0 -> routing identity deleted, the "
            f"spawn test reads the manufactured gap=1.0 typ=1.0, aux nan; FAB_EMB_HID=0 -> every "
            f"expert's identity collapses to ONE POINT with aux still finite (0.5549) and every gate "
            f"still printing FIRED, sum|g|max 18509.16; FAB_N0=0 -> a population of nobody, built in "
            f"full here and refused one entry point later by FAB.forward on the first routed window; "
            f"FAB_HOPS=0 -> a cap that does not cap, the walk takes 1 hop and the "
            f"fab.depth_curriculum gate prints 'FAB_DEPTH0 >= FAB_HOPS: the chain already starts at "
            f"the budget' over a budget of 0; FAB_SLOTS=0 -> fab.cap 6 beside "
            f"fab.operating_population 0, the utilization cull's setpoint at zero because "
            f"spine/derive.py::operating_population's floor of three is bypassed below three slots. "
            f"This removes no configuration: 1 is legal for all six and is the smallest each of them "
            f"has. It is NOT a range: nothing here bounds any of the six from above, and a finite "
            f"value inside the range can still be wrong -- FAB_EMB_HID=0's collapse is a property of "
            f"the identity space, not of the number, and a declared per-lever domain is the general "
            f"answer and is open.")

    cap = max(n0, slots)
    d_model = int(d_model)
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
    # depth0 and hops are read with the other five counts at the refusal above -- the sentinel is
    # resolved here, where its answer is USED, and read there, where a hop budget below one is
    # refused before anything is derived from it. FAB_DEPTH0 is deliberately NOT one of the six:
    # 0 is its DECLARED sentinel and this line is what honours it.
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

    sig_d = int(signature_dim)          # dk and hid were read with the six counts, at their refusal
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
    # THE PAIR THIS GATE PRINTS IS ONE OF ITS TWO CLAUSES, AND FOR SIX ROUNDS IT WAS THE WHOLE LINE.
    # spine/gate.py::Gate.line renders a verdict word, `(value vs threshold)` and -- only when a
    # reason is set -- the reason; with no reason the pair IS the entire arithmetic the reader is
    # invited to do. spine/derive.py::cull_gate_open is TWO clauses, a floor on the live population
    # and an occupancy test, and the pair below renders the occupancy one alone, so at FAB_N0=2
    # FAB_SLOTS=2 FAB_PRESSURE=0.45 this line read
    #     Gate fab.cull_gate: armed, did not fire (2/2=1.000 vs 0.45)
    # -- a value that meets its own printed threshold, beside the words reserved for a condition that
    # WAS tested and was not met, and a reader who does the arithmetic the line invites gets the
    # opposite answer from the line. TWO things put it in that state and both are computed here
    # rather than assumed: the FLOOR, which the pair never shows at all, and the ROUNDING of the
    # occupancy to three places, which can put the printed digits on the other side of the setpoint
    # from the ratio actually compared (measured: FAB_N0=4499 FAB_SLOTS=10000 at FAB_PRESSURE=0.45
    # prints 0.450 and did not fire). The floor is named first because naming it settles the line on
    # its own -- on the arms where both apply, "the floor alone shuts this gate" is what the reader
    # needs and the third decimal is not.
    #
    # THE RATIO IS SPELLED TWICE ON PURPOSE, here and in the `value=` f-string below, and hoisting it
    # into one local would be a NARROWING. K16 in tests/test_contract.py -- the check named
    # tests/test_contract.py::check_k16_verdicts_follow_their_printed_pair -- matches the printed
    # field against the verdict's clause as UNPARSED SOURCE, so a `value=` that reads a local no
    # longer renders `n0 / max(1, slots)`, and this Gate, the one site that check examines in this
    # file, would drop out of its examined set and into its descriptive count. The duplication is
    # load-bearing; the comparison below is not the render.
    _press = float(fab.pressure)
    _occ = n0 / max(1, slots)
    _occ_shown = float(f"{_occ:.3f}")            # the digits the pair prints, which is what is read
    pop.gates = (
        Gate("fab.on", on, on, True,
             reason="" if on else "FAB_ON=0: the forward is the identity, so every gate below this "
                                  "one reports UNREACHABLE rather than 'armed but 0'."),
        Gate("fab.cull_gate", cull_open,
             f"{n0}/{max(1, slots)}={n0 / max(1, slots):.3f}", float(fab.pressure),
             reason=(f"n_live={n0} is at or below the FLOOR OF TWO that "
                     f"spine/derive.py::cull_gate_open applies BEFORE the occupancy test and "
                     f"separately from it -- culling a population of two can empty it -- so that "
                     f"clause alone shuts this gate, whatever the occupancy printed beside this "
                     f"verdict reads. The pair on this line is the occupancy test and only it."
                     if not cull_open and n0 <= 2 else
                     f"the occupancy printed beside this verdict is ROUNDED to three places, and "
                     f"the ratio spine/derive.py::cull_gate_open compared against the FAB_PRESSURE "
                     f"setpoint is {_occ!r} -- which falls on the other side of that setpoint from "
                     f"the digits shown."
                     if (_occ >= _press) != (_occ_shown >= _press) else ""))
        if on else
        Gate("fab.cull_gate", False,
             f"{n0}/{max(1, slots)}={n0 / max(1, slots):.3f}", float(fab.pressure), reachable=False,
             reason="FAB_ON=0: there is no population to cull. The occupancy arithmetic still "
                    "evaluates, and printing it as FIRED would claim a mechanism ran that the "
                    "switch above had already turned off."),
        # THE TWO ARMS THAT ARE DECIDED HERE AND SPENT SOMEWHERE ELSE. Both belong at build for the
        # reason the three control-arm counters above do: the answer is a frozen lever, it is
        # settled before any window runs, and the entry point that acts on it may never be CALLED --
        # spine/loop.py names FAB.grow_check and FAB.own_lr_scale in RunResult.skipped today, so a
        # gate that only existed inside them would leave "growth is switched off" and "growth was
        # never invoked" printing the same nothing, which is the collapse spine/gate.py exists for.
        # NEITHER IS A SECOND EVALUATION OF ANYTHING: grow_check and own_lr_scale read the same
        # lever, and what they add is the per-call arithmetic (the MAD trigger, the envelope), which
        # is about the call and rides their own return.
        # UNREACHABLE AT FAB_ON=0, for the cull gate's reason two entries up. It printed FIRED on
        # that arm, and fabric/api.py::grow_check -- which never read fab.on -- then grew expert
        # 2049 into a fabric whose forward is the identity (measured: n_live 2048 -> 2049 on a
        # 400-loss probe with one jump). grow_check now returns before acting on that arm.
        Gate("fab.growth_armed", grow and on, value=f"FAB_GROW={grow}", threshold="FAB_GROW=True",
             reachable=on,
             reason="FAB_ON=0: there is no fabric in the forward to grow into, so neither growth "
                    "leg is evaluated and FAB.grow_check returns before its counters are seeded."
                    if not on else "" if grow else
                    f"FAB_GROW={grow}: the population is FROZEN at FAB_N0={n0}. Both growth legs "
                    f"are off -- no regression burst and no stall birth -- while culling, routing "
                    f"and selection all still run, which is what makes this the arm that isolates "
                    f"growth from everything else the fabric does. It does not freeze "
                    f"spawn-by-specification, which is FAB_SPAWN and a different door."),
        Gate("fab.lr_own", bool(fab.lr_own) and on, value=f"FAB_LR_OWN={bool(fab.lr_own)}",
             threshold="FAB_LR_OWN=True", reachable=on,
             reason="FAB_ON=0: no expert is in the optimizer (Population.parameters is empty on "
                    "that arm), so there is no per-expert rate to own."
                    if not on else "" if bool(fab.lr_own) else
                    f"FAB_LR_OWN={bool(fab.lr_own)}: every expert trains at the global rate. The "
                    f"per-expert triangular2 envelope, its lr_boost for the cull-eligible bottom "
                    f"and the lr_maxr ratio clamp are all inert, and FAB.own_lr_scale returns None "
                    f"rather than a table of ones -- a table of ones is a schedule that ran and "
                    f"chose 1.0, which is a different statement."),
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

    n=1 IS NOT A HYPOTHETICAL AND IT USED TO POISON THE WHOLE RUN. `torch.var(dim=0)` is UNBIASED --
    it divides by n-1 -- so at one live expert the variance line returned NaN, one line ABOVE a
    guard written for the covariance division and placed below it. Measured before the repair, at
    FAB_N0=1 with the pool full: aux_loss NaN at step 0, six of the twenty FAB tensors NaN after
    that update and ALL 28 LM tensors plus all 20 FAB tensors NaN by step 1 -- one undefined
    variance killing every parameter in the model, and `emb_var` cannot switch it off because
    NaN * 0 is NaN. The guard now stands ABOVE the arithmetic it guards and the n=1 branch uses the
    BIASED estimator, which is the mean squared deviation from the mean and is defined at n=1: the
    term is HALVED exactly as this function's contract says -- covariance 0, variance evaluated --
    and one embedding's spread is 0, so the hinge reads its maximum 1 - sqrt(1e-4) = 0.99 with a
    gradient of exactly zero, because there is nothing a single point can do about its own spread.
    That is a finite reading of a real quantity, where the NaN was a reading of nothing.
    """
    z = z - z.mean(0)
    n, d = z.shape
    if n < 2:
        # ONE EXPERT HAS NEITHER A COVARIANCE NOR AN UNBIASED VARIANCE. (z.T @ z)/(n-1) would divide
        # by zero and so does torch's own var(), which is why this guard is ABOVE both. The mean of
        # the squared ALREADY-CENTRED z is the biased estimator, spelled out rather than passed as a
        # flag, so the n>=2 line below stays the unbiased one it has always been and the two
        # estimators cannot be confused for one another by a later reader.
        std = torch.sqrt((z ** 2).mean(0) + 1e-4)
        return F.relu(1.0 - std).mean(), z.new_zeros(())
    std = torch.sqrt(z.var(0) + 1e-4)
    var_loss = F.relu(1.0 - std).mean()
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

    `max` IS NOT A GUARD AGAINST THE VALUES OF ITS OWN ARGUMENTS, AND FAB_BAL_FLOOR IS ONE OF FOUR
    PLACES IN THIS FILE WHERE THAT MATTERED. Python's max returns its FIRST argument when the
    comparison is False, and every comparison with NaN is False -- so `max(nan, 0.9998)` is nan, the
    balance scale is nan, `aux + balance_w * bal_scale * bal` is nan and 17 of 23 gradient-carrying
    tensors go non-finite, while the fab.balance gate prints FIRED and renders the poison as the
    arithmetic that justified it ("balance=0.01 x warm=nan vs > 0"). At +inf the scale is inf. At
    -inf the floor is simply GONE, and that one is LATE rather than immediate: `max(-inf, 1 -
    step/warm)` is the second term, so the scale goes NEGATIVE the moment step passes bal_warm and
    grows without bound -- measured at step_windows=100000 with bal_warm at its default, the scale is
    -24.0 and aux_loss is -0.196 against +0.497 at the shipped floor, which is the objective PAYING
    the population to collapse onto one expert. At step_windows=1 that cell is bit-identical to the
    baseline in every field, so a same-window sweep would have called it inert.
    ALL THREE ARE NOW REFUSED AT STARTUP by fabric/api.py::build's finiteness rule over every float
    lever, which is where a value refusal belongs; this line is left as the arithmetic it is. The
    other three sites of the same shape are the two `max(1e-3, route_t)` in fabric/api.py::_entry_logits
    and fabric/api.py::_halt_logit, and the `max(spawn_mult*typ, spawn_floor)` in
    fabric/api.py::_spawn_check. A full re-grep of this file found no fifth: every other max/min here
    takes ints or counts, and an int lever cannot hold a nan (spine/lever.py::Lever.coerce).
    WHAT IS STILL OPEN, AND THIS DOCSTRING DOES NOT CLAIM OTHERWISE: a FINITE negative floor reaches
    this line unrefused and reverses the same term more slowly, and nothing here bounds `floor` from
    either side.
    """
    return max(floor, 1.0 - step_n / max(1, warm_n))


def _identities(pop, n, step_n, emb_every_n, *, write=True):
    """(K, refreshed) -- the n live experts' routing keys, EMBEDDED FROM THEIR OWN WEIGHTS.

    THIS IS THE ONLY GRADIENT CHANNEL THAT REACHES EVERY EXPERT. Routing computes chain_k of n, so
    all but k experts get nothing from the mixture; eemb reads ALL n adapters, so a refresh puts
    every live A and B on the graph. That is why emb_every ships at 1 and why a stale cache is not a
    cost saving -- it throttles the one channel the rest of the population ever sees.

    TWO KINDS OF REUSE, AND CONFLATING THEM WAS THE OLD TREE'S BUG (self_organize.py:1932-1946).
    SAME WINDOW: hand back the LIVE tensors, so two reads of one window's identities are two
    consumers of ONE graph and not one consumer of a graph nobody backwards. WHO ACTUALLY REACHES
    THAT BRANCH, stated from the body rather than from the intent: `forward` calls this ONCE per
    call and passes the keys to every hop, so the only way in is a SECOND call at the same window
    index -- and a second GRADIENT-CARRYING pass at one window is refused by name in
    fabric/api.py::forward, for the reasons written there. What legitimately reaches it is a
    no_grad reader -- an eval pass, or a leave-one-out candidate at the window a training pass just
    embedded: it cannot backward, so sharing the live tensors costs it nothing and saves the whole
    re-embedding. LATER WINDOW, inside the cadence: hand back a DETACHED copy, because the previous
    backward already freed that graph -- returning the live tensors is "Trying to backward through
    the graph a second time", which never fired in the old tree only because the society path
    called this without a step at all.

    A PASS THAT CANNOT CARRY A GRAPH MAY READ THIS CACHE AND MAY NOT WRITE IT, WHATEVER THE CALLER
    SAID -- WHICH IS ENFORCED HERE, ON THE FIRST LINE OF THE BODY, AND NOT AT THE CALL SITE. The
    call site is not the only door: `write` used to be handed `solo` (`hold_out is None`), which
    shuts out the leave-one-out counterfactual and leaves an ORDINARY no_grad EVAL pass -- which is
    not a counterfactual and passes solo=True -- wide open. Same defect, one door over. Under
    torch.no_grad() the keys computed below carry NO GRAPH, and the write stamps them into
    `ident_graph` under the reading pass's own step; the next TRAINING pass at that step takes the
    first branch above, is handed a graphless tensor, and the routing term drops out of the
    backward: the one gradient channel that reaches every live expert, switched off for a window by
    a pass that was only looking, with every counter and every gate reading exactly as before --
    `fab.ident_refreshed` is the same number either way, so the ledger cannot see it and only a
    gradient measurement can.
    MEASURED ON THE UNGUARDED BODY -- the `write` line below removed and the call site back at
    `write=solo` -- at FAB_N0=8, FAB_SLOTS=16, FAB_RANK=4, FAB_DK=8, d_model=32, sig_d=64, B=4,
    L=6 and FAB_EMB_EVERY=1 (shipped): training passes at windows 5 and 6, with ONE no_grad eval
    pass at window 6 inserted between them.
    AND UNDER A NAMED OBJECTIVE, WHICH IS THE ONE VARIABLE THESE FOUR NUMBERS TURN ON AND THE ONE
    THIS PARAGRAPH USED TO OMIT. A gradient is a gradient OF something; two backwards from two
    losses are two measurements, and the grad|B| pair quoted here before was taken under the
    second of these while a reader would take it for the first:
      (a) THE COMPOSED OBJECTIVE, which is what the composition root backwards -- spine/compose.py's
          OPT.scaled_backward row, "LM.lm_loss's mean + LM.anchor_term's already-weighted term +
          FabricOut.aux_loss + WORLD's loss" -- here a cross-entropy over head(hidden) PLUS
          FabricOut.aux_loss;
      (b) FabricOut.aux_loss ALONE: a probe with no cross-entropy in it, which is not a pass this
          tree ever runs.
    AT TWO ARMS, BECAUSE EITHER ONE ALONE IS THE WRONG MEASUREMENT QUOTED WITHOUT ITS CONFIGURATION:
      * at the SHIPPED FAB_SPAWN=1 and FAB_AE_W=0.5, the window-6 pass goes from grad|A|max
        2.8533114e-2 to 3.1788775e-3 -- 88.9% of A's gradient on this input draw -- and it reads
        the SAME under (a) and under (b), because A's surviving route is the ae round trip and the
        round trip lives inside aux_loss, which both objectives contain. What survives is that
        round trip, A's OTHER route (fabric/api.py::forward's ablation paragraph). grad|B|max does
        NOT agree between the two: 3.3949580e-2 -> 1.3011797e-2 under (a) (B KEEPS 38% of its
        gradient) against 3.3045854e-2 -> 3.5802231e-3 under (b).
      * at FAB_SPAWN=0, or at FAB_AE_W=0, or at both -- EITHER lever removes that route, because
        the round trip is gated on `spawn_on and ae_w > 0.0 and learn` in fabric/api.py::forward
        -- grad|A|max goes from 2.7976248e-2 to EXACTLY 0.0, one reading at all three of those
        arms and under both objectives: ALL of A's gradient. grad|B|max splits again:
        3.3121154e-2 -> 1.3159202e-2 under (a) against 3.3161595e-2 -> 1.3570179e-11 under (b).
    WHY B SPLITS WHERE A DOES NOT, so the split is a fact about the design and not about the
    harness: B reaches the loss through the MIXTURE as (hA)^T grad_out, a route that does not pass
    through the identity channel and that the cross-entropy keeps whatever happens to the cache --
    fabric/api.py::build draws A uniform and zero-inits only B, so it is dL/dA through the mixture
    that is zero at step 0, not dL/dB. Under (b) there is no cross-entropy at all, so aux_loss's own
    identity-channel route is the ONLY one B has and it vanishes with A's. "grad|B| goes to zero"
    is therefore true of the probe and FALSE of a training pass in the composed run.
    THE TWO PERCENTAGES ARE PROPERTIES OF THIS INPUT DRAW and are printed as the ratio of the two
    numbers beside them, not as constants of the design; what is falsifiable at any draw is that A's
    poisoned reading is EXACTLY 0.0 on all three ae-off arms and a small nonzero residue on the
    shipped one, and that B's is neither under (a).
    With the guard below, both arms are bit-identical to the same pair of passes with no eval
    inserted -- re-measured on THIS body under (a): shipped 2.8533114e-2 / 3.3949580e-2 and ae-off
    2.7976248e-2 / 3.3121154e-2, with and without the inserted eval pass, and `ident_graph` still
    carrying a grad_fn after it. The cheaper half is the same defect one size down -- the middle
    branch clears `ident_graph`, so a read-only pass could force the next real pass to re-embed
    the whole population -- and ONE guard covers both, because it disarms `write` for the whole
    body rather than at each write site in it.
    """
    # THE GUARD IS THE CLASS, NOT THE INSTANCE: not "a counterfactual may not write" and not "an
    # eval pass may not write", but "a pass with no graph to give may not write", which is the
    # property that made both of those unsafe and is true of every caller that will ever exist.
    # torch.is_grad_enabled() is False under no_grad AND under inference_mode, and it is the exact
    # question -- `keys.grad_fn is None` would also refuse a legitimate grad-enabled pass whose
    # parameters are all frozen, where caching is harmless and re-embedding every window is not.
    write = bool(write) and torch.is_grad_enabled()
    if (pop.ident_step is not None and pop.ident_step == step_n and pop.ident_live == n
            and pop.ident_graph is not None):
        return pop.ident_graph, False
    if (pop.ident is not None and pop.ident_live == n and pop.ident_step is not None
            and step_n - pop.ident_step < emb_every_n):
        if write:
            pop.ident_graph = None              # release the old graph; it can never be handed back
        return pop.ident, False
    weights = torch.cat([pop.A[:n].reshape(n, -1), pop.B[:n].reshape(n, -1)], -1)
    keys = pop.modules["eemb"](weights)
    if not write:
        # THE KEYS ARE HANDED BACK AND NOTHING IS REMEMBERED. `refreshed` is False because no cache
        # was refreshed; the counter that reads it is a statement about the population's own clock.
        return keys, False
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

    `state` is the hop's hidden state AT THE WINDOW'S FIRST POSITION, h[:, 0], and it is what makes
    hop 2 a question rather than a fixed function of hop 1: without it the query is the input
    signature, identical at every hop, and the old tree measured I(domain; (hop0,hop1)) equal to
    I(domain; hop0) to three decimals on every seed. h[:, 0] still moves between hops -- the
    mixture a hop adds is computed at every position, position 0 included -- so that property holds.
    IT WAS h.mean(1) UNTIL 2026-09-24, AND THAT MADE THE WHOLE FABRIC NON-CAUSAL (Q-FAB-7). Routing
    is ONE decision per window, applied at every position, so whatever the query reads, position 0
    is routed on. A mean over all L positions let token t+1..L-1 choose the experts, the halt mass
    and the mixture weights that produce position t's logits: measured through LM.encode ->
    FAB.forward -> LM.decode with the window's tokens [t+1:] replaced, max|dlogit| at positions
    <= t was 2.4e-6 at window 2, 1.1e-4 at window 150 and 8.2e-4 at window 600 of a default run
    (LM.encode alone: exactly 0.0), growing as the router learned. h[:, 0] is the only per-window
    summary of the window's own tokens that every position may see -- LM.encode's output at x[0],
    causal on both LM arms (the GRU's first step, the transformer's causally masked first row) --
    and a generator can form it before it emits the window's second token.
    REJECTED: per-position routing on a causal running mean (a (B, L, n) routing distribution, the
    expert gather L times wider, and `use`/`uage`, the halt EMA and the balance term re-denominated
    from windows to positions -- a different fabric, not a repair); and the previous window's pooled
    state (hop-invariant, which is exactly what this term exists not to be).
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

    `max(1e-3, route_t)` FLOORS THE TEMPERATURE AND DOES NOT CAP IT, AND IT IS NOT A GUARD ON THE
    LEVER'S VALUE. The floor is real and declared: FAB_ROUTE_T=0 is the sharpest temperature this
    mechanism admits, and FAB_ROUTE_T=nan and =-inf are BIT-IDENTICAL to it (max keeps 1e-3 because
    `nan > 1e-3` is False), measured at aux 0.5098478198051453 for all three. What the same
    expression does NOT do is the other end: at FAB_ROUTE_T=+inf every routing logit here and the
    halt logit in fabric/api.py::_halt_logit become exactly 0.0, so the softmax over the population
    is UNIFORM -- the region cosine and the learned identity term are both erased and there is no
    routing decision left -- while Gate fab.route_learned still prints "FIRED (route_learn=True vs
    route_learn=True)". Measured: aux 0.4987463653087616 against 0.5134152173995972, halt mass
    0.3703 against 0.0139, and both batch rows selecting identical experts. FAB_ROUTE_T is now
    refused non-finite at startup by fabric/api.py::build; refusing nan and -inf costs nothing
    because 0 already spells exactly what they did. A LARGE FINITE temperature does the same thing
    more slowly and is not refused.

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


def _decode(head, x):
    """`head(x)` with LM.decode's masked rows at a FINITE floor, _NEG, instead of -inf (Q-FAB-8).

    EVERY CONSUMER HERE COMBINES LOGITS LINEARLY WITH WEIGHTS THAT CAN BE EXACTLY ZERO. The vote is
    `take * hop_lg` with take = alive * ph, and ph is identically zero at FAB_HALT=0; the society
    blend is `(1 - held) * last + held * base` with held zero on the same arm. LM.decode masks dead
    and retired rows with -inf at LM_MASK_DEAD_ROWS=1, and 0 * -inf is nan -- so the first vote
    under that lever would put nan in every masked column and the loss would be nan. At _NEG the
    same masked column is a convex combination of -1e4s, which is -1e4, and exp(-1e4 - max) is 0.0
    in fp32 and bf16 alike: the softmax, the cross-entropy and the surprise are the masked ones.
    """
    lg = head(x)
    return lg.masked_fill(torch.isneginf(lg), _NEG)


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
        return None, 0, f"FAB_DOM_FRAC={dom_frac}: the breadth cap is switched off."
    limit = max(int(dom_min), int(dom_frac * max(1, int(live_domains))))
    affiliated = sum(1 for e in range(n) if pop.dom_of[e])
    if affiliated == 0:
        return None, limit, ("no expert holds an affiliation yet: FAB.observe is the only writer of "
                             "dom_of, so until it has been called on a routed flush the cap has "
                             "nothing to measure breadth against. Its body landed 2026-09-17; "
                             "whether it is CALLED is spine/loop.py's answer and RunResult.skipped "
                             "is where a reader finds it.")
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


def _claim_slot(pop, slot, step_n, *, parent=-1, mutscale=1.0):
    """Take slot `slot` into the live population and CLEAR EVERY BOOK. The one birth door.

    ONE FUNCTION FOR BOTH BIRTH PATHS, which is what fabric/api.py::grow_check's docstring requires
    in as many words: "Both birth paths call one claim_slot() that clears EVERY book". The old tree
    had two and they disagreed -- grow() cleared use/comp/contrib and NOT ef/es, so a newborn
    inherited a dead expert's error history and could be culled by the failure route for something
    it never did (L30). Two clearing sites is two chances to forget a book, and the books grow.

    `use` IS CLEARED TO 0.0 AND NOT TO 0, and the type is the statement. Since the use/uage split
    (fabric/api.py::observe) `use` is ROUTING MASS -- a float -- and `uage` is the integer SELECTION
    count; a slot handed back an int 0 reads identically today and is the first place a future
    reader would conclude they are the same kind of number again.

    IT DOES NOT DRAW AND IT DOES NOT WRITE A AND B. The caller has already decided what the new
    expert IS -- a decoded query for spawn, a mutated parent or a fresh identity for growth -- and
    doing it here would put two unrelated mechanisms behind one name.
    """
    pop.born[slot] = int(step_n)
    pop.use[slot] = 0.0
    pop.uage[slot] = 0
    pop.ef[slot] = 0.0
    pop.es[slot] = 0.0
    pop.comp[slot] = 0.0
    pop.contrib[slot] = 0.0
    pop.dom_of[slot] = set()
    pop.parent[slot] = int(parent)
    pop.mutscale[slot] = float(mutscale)
    pop.n_live = slot + 1
    pop.births += 1
    # THE IDENTITY CACHE IS NOW STALE IN BOTH SENSES -- it is the wrong length, and the tensor it was
    # embedded from has a new version. Dropped rather than patched: a cache that survives a write to
    # its own source is the "backward through the graph a second time" failure with extra steps.
    pop.ident = pop.ident_graph = pop.ident_step = None
    pop.ident_live = -1
    return slot


# THE ONE DECLARED RENUMBERING LIST. Every per-expert book this package keeps, named ONCE so a
# removal cannot leave one of them stale. fabric/api.py::state_dict says what the alternative cost:
# "the old remove() renumbered ten of them and left `parent` and `mutscale` stale after the first
# cull (L28), which is also why fab.distinct_parents can be trusted as a D7 reading."
# IT IS A LIST OF NAMES AND NOT A LOOP OVER __slots__, because __slots__ also holds `cap`,
# `n_live`, the module dict, the RNG and four cache fields, and a renumbering that walked all of
# them would swap the population's size with an expert's birthday.
_BOOKS = ("born", "use", "uage", "dom_of", "ef", "es", "comp", "contrib", "parent", "mutscale")


def _remove(pop, slot):
    """Delete one expert by SWAP-WITH-LAST, renumbering every book from `_BOOKS` and the three
    tensors. Returns the id the survivor moved FROM, or None when the victim was already last.

    SWAP-WITH-LAST AND NOT A SHIFT, because A, B and cent are (cap, ...) preallocated tensors and
    n_live is the only thing that moves: a shift would rewrite every row above the hole on every
    cull, and the pool exists precisely so growth never reallocates (Population's own docstring).
    THE SURVIVOR'S ID CHANGES, AND THAT IS THE COST THIS FUNCTION MAKES VISIBLE BY RETURNING IT.
    fabric/api.py::manage's merge paragraph is explicit that a cull already does everything a merge
    would do to MEM -- "remove()'s swap-with-last renumbers the survivor above the hole, which moves
    ITS expert_id % 64 too" -- so a caller that keeps expert ids across a pass has to know.
    THE IDENTITY CACHE IS DROPPED FOR _claim_slot's REASON, verbatim: it is the wrong length now AND
    the tensor it was embedded from has a new version, and a cache that survives a write to its own
    source is the "backward through the graph a second time" failure with extra steps.
    """
    last = int(pop.n_live) - 1
    moved = None
    if slot != last:
        with torch.no_grad():
            pop.A[slot] = pop.A[last]
            pop.B[slot] = pop.B[last]
            pop.cent[slot] = pop.cent[last]
        for name in _BOOKS:
            book = getattr(pop, name)
            book[slot] = book[last]
        moved = last
    with torch.no_grad():
        pop.A[last] = 0.0
        pop.B[last] = 0.0
        pop.cent[last] = 0.0
    pop.dom_of[last] = set()
    pop.parent[last] = -1
    pop.mutscale[last] = 1.0
    pop.n_live = last
    pop.ident = pop.ident_graph = pop.ident_step = None
    pop.ident_live = -1
    return moved


def _merge_into(pop, a, b, rank):
    """Consolidate expert `b` into expert `a` IN DELTA-W SPACE. Returns the truncation residual as
    a fraction of ||dW_a + dW_b||.

    THE ARITHMETIC IS THE WHOLE OF Q-FAB-2 AND THE LEGACY FORM IS WRONG, not merely cruder. The old
    merge is `A[a] = 0.5*(A[a]+A[b]); B[a] = 0.5*(B[a]+B[b])` (self_organize.py:3083). An expert's
    function is dW = A @ B, so averaging the FACTORS gives 0.25*(A1B1 + A1B2 + A2B1 + A2B2): the
    intended contribution is HALVED and two cross terms are injected that correspond to no learning
    either expert did. A and B are ZERO-INIT at birth with no shared basis, so nothing aligns
    expert a's rank slot 3 with expert b's -- the census's headline claim, "both experts' learning
    survives where culling destroys it", is not supported by its own arithmetic.
    WHAT THIS DOES INSTEAD: the best rank-`rank` approximation of dW_a + dW_b, by thin QR of
    [A_a | A_b] (d x 2r) and of [B_a | B_b]^T, then an SVD of the 2r x 2r core. O(d*r^2) -- a few
    thousand flops at d=128, r=8.
    RANK CANNOT BE WIDENED TO HOLD THE EXACT SUM (load_state_dict: rank is an INNER dimension), so
    the truncation is FORCED and the residual is the honest report of what it cost. Returned rather
    than thresholded: a threshold would be a lever with no census row, and Q-MEM-4's discipline is
    MEASURE BEFORE RETUNING. If the residual reads high the operator lowers merge_dist.
    """
    with torch.no_grad():
        Aa, Ab = pop.A[a].float(), pop.A[b].float()          # (d, r) each
        Ba, Bb = pop.B[a].float(), pop.B[b].float()          # (r, d) each
        Acat = torch.cat([Aa, Ab], dim=1)                    # (d, 2r)
        Bcat = torch.cat([Ba, Bb], dim=0)                    # (2r, d)
        qa, ra = torch.linalg.qr(Acat, mode="reduced")       # (d, 2r), (2r, 2r)
        qb, rb = torch.linalg.qr(Bcat.t(), mode="reduced")   # (d, 2r), (2r, 2r)
        core = ra @ rb.t()                                   # (2r, 2r)
        u, sv, vh = torch.linalg.svd(core)
        k = int(rank)
        # THE RESIDUAL IS THE ENERGY THE TRUNCATION DROPS, as a fraction of the sum's own norm.
        # Frobenius norm of a product with orthonormal factors is the norm of the core's singular
        # values, so this needs no explicit dW anywhere -- forming (d, d) would be the one
        # allocation this whole routine exists to avoid.
        total = float(torch.linalg.vector_norm(sv))
        kept = float(torch.linalg.vector_norm(sv[:k]))
        resid = 0.0 if total <= 0.0 else max(0.0, 1.0 - (kept / total))
        root = torch.sqrt(sv[:k])
        pop.A[a] = (qa @ (u[:, :k] * root)).to(pop.A.dtype)
        pop.B[a] = ((root[:, None] * vh[:k, :]) @ qb.t()).to(pop.B.dtype)
        # THE BOOKS MERGE, WHICH IS THE OTHER HALF OF "both experts' learning survives".
        pop.cent[a] = torch.nn.functional.normalize(
            (pop.cent[a].float() + pop.cent[b].float()), dim=-1).to(pop.cent.dtype)
    pop.use[a] = float(pop.use[a]) + float(pop.use[b])
    pop.uage[a] = int(pop.uage[a]) + int(pop.uage[b])
    pop.dom_of[a] = set(pop.dom_of[a]) | set(pop.dom_of[b])
    return resid


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

    NEITHER HALF OF `max(spawn_mult*typ, spawn_floor)` GUARDS THE OTHER, AND BOTH FAILED THE SAME
    WAY. Python's max keeps its FIRST argument when the comparison is False and every comparison with
    NaN is False, so:
      FAB_SPAWN_MULT=nan  max(nan, floor) is nan, `gap < nan` is False, and the test SPAWNS
                          UNCONDITIONALLY on every query for the life of the run -- the absolute
                          floor whose declared purpose is "so a degenerate population cannot spawn on
                          every query" bypassed entirely. Measured at FAB_N0=6/FAB_SLOTS=12: two
                          forward passes, two spawns, n_live 6 -> 8, fab.spawn_declined 0, against 0
                          spawns and 2 declines at the shipped 2.0. The gate then renders a threshold
                          that was never used: "FIRED (gap=0.85165 vs max(nan*typ=0.71431,
                          floor=0.02))" reads as though 0.71431 or 0.02 had governed the comparison.
      FAB_SPAWN_FLOOR=nan max(spawn_mult*typ, nan) returns spawn_mult*typ, so the FLOOR IS SILENTLY
                          DELETED while the gate prints "floor=nan" as though it were in force. On a
                          healthy population nothing changes -- measured bit-identical to the
                          baseline -- and the harm is exactly the case the lever exists for: once the
                          identity space has collapsed, typ -> 0, the threshold goes to 0 and the
                          population spawns on every query with nothing to stop it. At +inf the
                          threshold is inf, spawn can never fire again, and the gate reports "armed,
                          did not fire" -- the armed-but-0 state standing in for UNREACHABLE, which
                          spine/gate.py exists to forbid.
    BOTH ARE NOW REFUSED AT STARTUP by fabric/api.py::build's finiteness rule over every float lever.
    That closes three values on each; it does not bound either lever, and a FINITE FAB_SPAWN_FLOOR
    large enough (measured elsewhere in this tree at 1.5) still makes the test decline every query
    without saying so.
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
    # THE BOOKS ARE CLEARED THROUGH THE ONE DOOR, not inline here: fabric/api.py::_claim_slot is the
    # single clearing site both birth paths go through, and the L30 defect it records is exactly
    # what two of them produced. `parent=-1` because a spawn has no parent -- it is decoded from the
    # router's query, not inherited -- and that -1 is what keeps fab.distinct_parents a reading
    # about REPLICATION rather than about every birth.
    _claim_slot(pop, slot, step_n, parent=-1, mutscale=1.0)
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
    surprise from the previous step. head: LM.decode as a plain ONE-ARGUMENT callable (the vocab
    boundary already bound -- spine/compose.py::_head), needed for the per-hop vote and for
    spending HALT mass on the base representation; it is called only when the vote, the society
    arm or hop_sup consumes it, and its masked -inf rows are floored at _NEG (fabric/api.py::
    _decode). targets: (B, L) token ids, needed only for hop_sup and ind_w; when None those two
    terms are UNREACHABLE and say so. spine/loop.py::_flush passes BOTH since 2026-09-24; for the
    whole life of this body before that it passed neither, so the vote never formed.
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
    loss by TWO routes this body builds, and the count was wrong here until it was ablated.
      1. eemb's IDENTITY CHANNEL. Every live expert's adapter is embedded into the routing keys, so
         the routing distribution is a function of ALL n adapters and not just the chain_k computed
         -- and everything downstream of that distribution carries gradient back through it: the
         load-balance term, the ponder charge, the div_w distinctness weighting, the mixture weights
         and the vote weights. THOSE ARE CONSUMERS OF THIS ROUTE, NOT ROUTES OF THEIR OWN, which is
         the correction: an earlier version of this paragraph named the load-balance term as a third
         independent path. MEASURED, at the widths named above, step 0, OPT_WEIGHT_DECAY=0: with
         FAB_ROUTE_LEARN=0 and FAB_AE_W=0 -- FAB_BALANCE and FAB_DIV_W left at their shipped
         defaults -- grad|A|max is EXACTLY 0.0, so neither term reaches A once the identity channel
         is removed. With route_learn on and ae off it is 1.514e-2; take balance out as well and it
         falls to 4.342e-3; take div_w out too and 1.284e-8 is all that is left, which is the VOTE's
         own weights -- FAB_HOP_VOTE=0 on top of that leaves 1.682e-10, the float rounding in the
         mixture's weight normalisation and nothing else. Adding FAB_PONDER=0 changes nothing at
         all (1.284e-8 again), because the depth charge is annealed and its scale at window 0 is
         exactly zero, so `ponder` buys A no gradient on the step this paragraph is about.
      2. THE ae ROUND TRIP, which reaches A and B without passing through their product at all. On
         its own -- FAB_ROUTE_LEARN=0, ae at its default -- it carries grad|A|max 1.515e-3.
    dL/dB through the mixture is nonzero from the first step because it is (hA)^T @ grad_out, which
    does not contain B: at FAB_ROUTE_LEARN=0 with FAB_AE_W=0, where grad|A| is exactly 0.0,
    grad|B|max is still 4.400e-3.

    LEVERS READ: on, norm_only, society, hop_vote, hop_sup, hops, depth0, halt, halt_max, alpha,
                 ponder, ponder_warm, route_region_w, route_learn, route_t, cent_topk, cent_ema,
                 discover, chain_k, ens_k, explore, ec_w, balance, bal_floor, bal_warm, dom_frac,
                 dom_min, div_w, ind_k, ind_w, dk, rank, emb_hid, emb_var, emb_every, ae_w, spawn,
                 spawn_mult, spawn_floor
    WIRES READ: none
    DID IT FIRE: ALL 24 KEYS THIS BODY WRITES -- counted against the body in BOTH directions on
    2026-09-04 and found four short, which is why the last four lines exist. A key written and not
    declared is a number in the report that the contract does not admit to producing; a key declared
    and not written is the opposite and there are none (all 24 below are written, and 19 of them are
    SEEDED to 0 before any branch decides, so absent never masquerades as zero -- 16 on every routed
    pass and 3, fab.ind_applied, fab.hopsup_applied and fab.halt_spent_on_base, only on the arm
    that can reach them, so that absent says UNREACHABLE for those three as G4 requires). The count is stated
    because the previous one was wrong: this body writes 24 keys, not nineteen, and it declared 14
    distinct Gates and not thirteen when that count was taken -- 15 now, fab.halt_spent_on_base
    being the one added with this reconciliation.
    A LEAVE-ONE-OUT PASS (`hold_out` set) WRITES NONE OF THEM except fab.holdout_applied, which
    exists to count leave-one-out passes. It used to write fab.route_calls and fab.hops_taken like
    any other pass, so eight candidates on one window read 9 route calls and 27 hops taken for a
    walk that took 3 -- a counterfactual moving the instrument it is measured by.
                 fab.route_calls, fab.hops_taken, fab.halt_mass_train (TRAINING passes only -- the
                 old EMA averaged eval passes in and moved when nothing but HOLDOUT_N changed),
                 fab.halt_clamped, fab.explored_rows, fab.explore_distinct_targets,
                 fab.discovered + fab.discover_targets (DISTINCT recipients; 1 is H14, where
                 `min(range(N), key=use)` returns the FIRST minimum and discovery never credits
                 use, so every novel signature overwrites the same slot), fab.banned_experts,
                 fab.ec_applied, fab.balance_nonzero (THE C2 ALARM: 0 while balance > 0 means the
                 term is multiplying a zero again), fab.div_applied, fab.ind_applied,
                 fab.hopsup_applied, fab.ident_refreshed, fab.holdout_applied, fab.spawned,
                 fab.spawn_declined with fab.spawn_gap and fab.spawn_typ recorded AS A PAIR (the
                 old report printed the gap with no scale to compare it to, ISSUES P1-L29),
                 fab.forward_identity (the FAB_ON=0 arm's own count -- the identity forward is a
                 pass this package RAN, and a report that shows no route_calls and no reason is a
                 report of a package that was never called),
                 fab.norm_only_passes (the FAB_NORM_ONLY=1 control arm, counted for the same reason
                 and kept separate from fab.forward_identity because the two arms answer different
                 questions: what the EXPERTS bought, against what the PACKAGE bought),
                 fab.ident_trained (the ae round trip's own count, which is NOT fab.ident_refreshed:
                 the round trip trains on every learning pass while the identity cache refreshes on
                 the emb_every cadence, and tying the two is the defect that left the embedder
                 collapsed -- so the two counters are the falsifier for that being retied),
                 fab.halt_spent_on_base (the society arm only, and ONLY when halt mass was actually
                 spent: at FAB_HALT=0 the blend is the identity on the vote, and counting that as a
                 spend was a wrong measurement wearing a counter's name)
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
    # EXACTLY 0.0, ON h'S GRAPH. FabricOut.aux_loss's frozen docstring requires "ONE scalar with a
    # graph -- never a float and never a freshly allocated zero", and `h.new_zeros(())` is precisely
    # the freshly allocated zero it names: the two switched-off arms below returned one as their
    # WHOLE aux_loss, in the one field C2 is the record of. The composition root SUMS this into the
    # objective it backwards (spine/compose.py's OPT.scaled_backward row: "LM.lm_loss's mean +
    # LM.anchor_term's already-weighted term + FabricOut.aux_loss + WORLD's loss"), so a graphless
    # summand is not an error at either end -- backward() walks past it and the run reports
    # normally,
    # which is the whole C2 failure mode and the reason the record type forbids it by name.
    # `h[:0].sum()` is the sum of NO elements: exactly zero for every h, INCLUDING a non-finite one
    # (`h.sum() * 0.0` would be nan and would blame FAB for the LM's blow-up), differentiable, with
    # a gradient that is identically zero. It does not invent a term -- the FAB-side terms on those
    # two arms are ABSENT and their gates say so -- it makes the record's guarantee true, so a
    # caller may add and backward it without a special case. Under no_grad it has no graph, like
    # every other tensor here, which is why the C2 alarm below tests grad_fn on training passes
    # only.
    zero = h[:0].sum()

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
        if training and hold_out is None:
            pop.pass_gates = tuple(gates)
        return FabricOut(hidden=h, aux_loss=zero, gates=tuple(gates))

    hops, depth0 = int(fab.hops), int(fab.depth0)
    if norm_only:
        # THE CONTROL ARM. It keeps the normalization and removes nodes and routing, which is what
        # separates it from FAB_ON=0: the population is still in the optimizer and still grows,
        # culls and is checkpointed -- so a run on this arm answers "what did the EXPERTS buy"
        # rather than "what did the whole package buy", and the two questions have different
        # answers. At FAB_ON=0 the pool is still ALLOCATED and checkpointed (Q-FAB-11) but hands OPT
        # no parameter and grow_check/manage/own_lr_scale return before acting.
        out = h
        for _ in range(max(1, min(hops, 2 + int(pop.n_live) // 2))):
            out = pop.modules["norm"](out)
        _bump(counters, "fab.norm_only_passes")
        gates.append(Gate("fab.forward.routed", False, value="FAB_NORM_ONLY=1",
                          threshold="FAB_NORM_ONLY=0", reachable=False,
                          reason="FAB_NORM_ONLY=1: the control arm keeps the fabric's normalization "
                                 "and removes nodes and routing from the forward pass. The experts "
                                 "receive no gradient from this term; they remain in the optimizer, "
                                 "which is what makes this arm different from FAB_ON=0 -- where "
                                 "fabric/api.py::Population.parameters hands OPT nothing."))
        if training and hold_out is None:
            pop.pass_gates = tuple(gates)
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

    # ONE GRADIENT-CARRYING TRAINING PASS PER WINDOW, AND THE SECOND IS REFUSED BY NAME. This is a
    # CALLER ERROR and not a cache defect, and the tree's own clock is what decides that:
    # train/api.py::RunClock.advance advances `step` ONE WINDOW at a time and reports `flush_due`,
    # the flush body is what calls this entry point, and spine/compose.py's row for it passes
    # `step_windows=clock.step` -- so the index has moved before the next routed pass. Gradient
    # accumulation is spelled in this tree as MORE BACKWARDS OVER MORE WINDOWS
    # (opt/api.py::scaled_backward counts Backwards and scales by accum;
    # spine/derive.py::opt_steps_from_windows: "effective_batch_windows is batch_windows x accum:
    # windows per FLUSH times flushes per optimizer STEP"), never as two passes at one index.
    # WHAT THE SECOND PASS ACTUALLY DID BEFORE THIS REFUSAL, measured at FAB_N0=8/SLOTS=16/RANK=4/
    # DK=8: at FAB_ROUTE_LEARN=1 (shipped) it raised torch's "Trying to backward through the graph
    # a second time" out of fabric/api.py::_identities' same-window branch -- a bare error naming no
    # lever, no clock and no caller -- and at FAB_ROUTE_LEARN=0 it raised NOTHING and silently
    # applied one window's ponder anneal, balance anneal, spawn test, centroid EMA and halt EMA
    # twice. Refusing at only the first of those would be a guard that exists at one lever value and
    # vanishes at another, which is the shape this package's own history is made of; the refusal is
    # therefore on the clock, where the error is, and not on the cache, where it happened to show.
    # A no_grad EVAL pass and a leave-one-out counterfactual at the same window are LEGAL and
    # untouched -- they are exactly what `learn` excludes.
    # THE GUARD IS BROADER THAN THE MEASUREMENT ABOVE, AND THAT IS STATED RATHER THAN LEFT TO BE
    # DISCOVERED: it is on `learn and torch.is_grad_enabled()`, not on having BACKWARDED, so TWO
    # grad-enabled training forwards at one window with NO backward between them are refused too --
    # measured "NO ERROR" before this refusal and ValueError after it, at FAB_ROUTE_LEARN=1 and at
    # FAB_ROUTE_LEARN=0 alike. That is inside the sentence this raises ("a SECOND gradient-carrying
    # training pass") and it is deliberate -- the second forward applies this window's ponder anneal,
    # balance anneal, spawn test and halt EMA a second time whether or not anyone backwards it --
    # but it is wider than the double-backward the paragraph above justified it with, and a reason
    # that names only the narrower case would be the printed-claim-outside-its-measurement defect
    # this file is otherwise busy removing.
    if learn and torch.is_grad_enabled():
        if pop.learn_window == step_n:
            raise ValueError(
                f"FAB.forward: a SECOND gradient-carrying training pass at step_windows={step_n}. "
                f"The window clock advances once per window (train/api.py::RunClock.advance) and "
                f"this entry point is called once per flush with step_windows=clock.step, so one "
                f"window index is one routed training pass. At FAB_ROUTE_LEARN=1 the two passes "
                f"share this population's identity graph and the second backward raises torch's "
                f"'Trying to backward through the graph a second time' naming no lever and no "
                f"clock; at EVERY value of it the two would apply this window's ponder anneal, "
                f"balance anneal, spawn test and halt EMA twice. Accumulate over "
                f"MORE WINDOWS -- OPT_ACCUM x batch_windows, "
                f"spine/derive.py::opt_steps_from_windows "
                f"-- rather than over one window twice. An eval pass (training=False) or a "
                f"leave-one-out pass (hold_out=...) at this window is legal and is not what this "
                f"refuses.")
        pop.learn_window = step_n

    # SPAWN RUNS FIRST, BEFORE ANY GRAPH EXISTS -- see fabric/api.py::_spawn_check for why that is
    # forced and not preferred. It is also why `spawn` is read here rather than only in grow_check:
    # this is the only entry point that holds the router's own query, and spawn-by-specification is
    # "decode the query into the expert that was asked for".
    # WHAT THIS DOOR IS BOUND BY, AND WHAT IT IS NOT. It is bound by pop.cap, which is the hard
    # preallocation ceiling. It is NOT bound by CAP's operating soft cap, because `soft_cap` arrives
    # at fabric/api.py::grow_check and at no other entry point -- so the sentence in grow_check's
    # docstring, "spawn births are counted here too so BOTH DOORS ARE BOUND BY THE SAME CAP", is
    # half true, and WHICH HALF MOVED ON 2026-09-17. The fork named here was "a `soft_cap` keyword
    # on this entry point (a frozen-signature move) or a rule that grow_check subtracts spawn births
    # from its own budget", and the SECOND was taken: grow_check reads fab.spawned, charges every
    # birth this door produced against the new_frac budget and counts it as
    # fab.newfrac_spent_on_spawn, so the two doors now share one newborn budget. What is still not
    # bound is the moment of the birth itself -- this door neither consults the soft cap nor reads
    # FAB_GROW, so a frozen population still drifts upward by spawn alone (the :7332-7335 defect),
    # and closing that is the first option, which is still a frozen-signature move.
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
                 "fab.ident_refreshed",
                 "fab.ident_trained", "fab.holdout_applied", "fab.spawned", "fab.spawn_declined"):
        counters.setdefault(_key, 0)
    # THREE KEYS ARE SEEDED ONLY ON THE ARM THAT CAN REACH THEM, still before any branch decides.
    # They were in the loop above until 2026-09-24, and spine/loop.py passed no `head` and no
    # `targets` for the whole life of this body -- so every run printed fab.ind_applied 0,
    # fab.hopsup_applied 0 and fab.halt_spent_on_base 0, which G4 reads as "armed, did not fire",
    # about three mechanisms that could not run. The predicates are the ones the three gates below
    # print as `reachable`, except that hop_sup's depth clause is taken on the CONFIGURATION (a
    # society pin or FAB_HOPS=1 can never give it a second hop) rather than on this pass's depth,
    # which moves with the curriculum: an armed hop_sup that is still at one hop is armed-and-0,
    # and its gate states that with the reason.
    if society and ind_w > 0.0 and head is not None and targets is not None:
        counters.setdefault("fab.ind_applied", 0)
    if (hop_sup_w > 0.0 and head is not None and targets is not None and not society
            and hops > 1):
        counters.setdefault("fab.hopsup_applied", 0)
    if society and halt_on and head is not None:
        counters.setdefault("fab.halt_spent_on_base", 0)
    if solo:
        _bump(counters, "fab.route_calls")
    # DEPTH. society PINS THE WALK AT ONE HOP and keeps per-expert logits, which is what makes
    # leave-one-out a reweighted sum rather than a re-walk -- it is the same forward pass with a
    # different depth and a different return, NOT a second path. The old tree had two, and
    # SUFFICIENCY called fab.society() unconditionally while the shipped default was the looped
    # path (D1, point 2).
    depth = 1 if society else max(1, min(int(pop.depth_now), hops, 2 + n // 2))
    # THE SOCIETY ARM NEVER READS depth_now, AND THIS GATE DID NOT SAY SO. At FAB_SOCIETY=1
    # FAB_DEPTH0=0 the report printed fab.depth_now 4 and this gate "armed, did not fire" while
    # fab.hops_taken read 60 over 60 passes -- one hop each, because the line above pins it. A
    # curriculum over a depth nothing reads is UNREACHABLE, not armed, and the reason names the pin.
    _curr_ok = bool(0 < depth0 < hops and not society)
    gates.append(Gate("fab.depth_curriculum", _curr_ok,
                      value=f"depth0={depth0}", threshold=f"hops={hops}",
                      reachable=not society,
                      reason="" if _curr_ok else
                             (f"FAB_SOCIETY=1 pins the walk at one hop, so depth_now="
                              f"{int(pop.depth_now)} is never read and no curriculum over it can "
                              f"move what this pass computes." if society else
                              "FAB_DEPTH0=0 is the no-curriculum sentinel: build resolved depth_now "
                              "to the full hop budget, so FAB.manage's staged advance has nothing "
                              "to extend." if depth0 == 0 else
                              "FAB_DEPTH0 >= FAB_HOPS: the chain already starts at the budget.")))

    # `write=learn`: ONLY A PASS THAT LEARNS MAY WRITE THE IDENTITY CACHE. This was `write=solo`,
    # which is `hold_out is None` and therefore TRUE of an ordinary eval pass -- so the door that
    # was shut on the leave-one-out counterfactual stood open for every no_grad instrument, and one
    # eval pass at the shipped FAB_EMB_EVERY=1 took the next training pass's grad|A|max to 0.0.
    # The load-bearing repair is in fabric/api.py::_identities, which now disarms `write` for ANY
    # pass that cannot carry a graph whatever this line says; `learn` is this call site stating the
    # same rule in the vocabulary the rest of this body uses (_ground_update, _explore_swap,
    # _spawn_check and the halt EMA are all gated on it), so a grad-enabled instrument that forgot
    # its no_grad is refused the cache as well.
    keys, refreshed = (_identities(pop, n, step_n, emb_every_n, write=learn) if route_learn
                       else (None, False))
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
    # THE C2 ALARM'S SUBJECT IS RECORDED WHERE THE TERM IS BUILT, NOT READ OFF THE ACCUMULATOR.
    # `bal_acc` is seeded from `zero`, and `zero` is `h[:0].sum()` -- a tensor that CARRIES h's
    # graph, deliberately, so the two switched-off arms above can return a differentiable aux_loss.
    # An accumulator seeded from it has a grad_fn whatever its terms are, so the alarm's own test,
    # `bal.grad_fn is not None`, was TRUE BY CONSTRUCTION on every training pass from the moment
    # `zero` stopped being a freshly allocated one. MEASURED at FAB_ROUTE_LEARN=0 + FAB_HALT=0,
    # where the entry logits are the region cosine over the DETACHED signature against `cent` (not
    # a Parameter) and the halt column is pinned, so `w` reaches nothing: FAB_BALANCE 0.01 and 5.0
    # both move aux (0.4953668 and 5.9921689) and neither moves one gradient -- autograd.grad of
    # aux over A, B, halt_b, every module and head parameter and h has absmax-sum
    # 0.014852798765332409 at FAB_BALANCE 0, 0.01 AND 5.0 -- while fab.balance_nonzero read 1. That
    # is the C2 failure mode itself, reported clean by the alarm that exists to name it.
    # SEEDING THE ACCUMULATOR GRAPHLESS AGAIN WOULD FIX THE READING AND KEEP THE FRAGILITY: the
    # detector would still be measuring a line two hundred lines away rather than its own subject,
    # and the next edit to `zero` would silently disarm it again. `bal_graph` is that subject --
    # the graph of the balance term ITSELF, `w.size(1) * (w.mean(0) ** 2).sum()`, taken at the one
    # place it is built. It is a bool and not a tensor, so it adds nothing to the objective.
    bal_graph = False
    # THE HEAD IS CALLED ONLY WHEN SOMETHING CONSUMES WHAT IT RETURNS: the vote (hop_vote), the
    # society blend and its per-expert logits, or deep supervision (hop_sup). With all three off a
    # per-hop decode is ens_k full-vocabulary matmuls whose results nobody reads -- and LM.decode
    # applies dropout, so the wasted calls would also move the RNG and make FAB_HOP_VOTE=0 a
    # different run from "no vote" rather than the same run minus the vote.
    decode_on = bool(head is not None and (hop_vote or society or hop_sup_w > 0.0))
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
        # THE STATE IS h[:, 0] AND NOT h.mean(1), BECAUSE THIS ONE DECISION ROUTES EVERY POSITION:
        # a pooled state let tokens after t choose the experts that score token t (Q-FAB-7, and
        # fabric/api.py::_route_query for the measurement and the rejected alternatives).
        query = _route_query(pop, signature, novelty, state=h[:, 0])
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
        bal_term = w.size(1) * (w.mean(0) ** 2).sum()
        bal_graph = bal_graph or (bal_term.grad_fn is not None)
        bal_acc = bal_acc + bal_term
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
        # two routes -- eemb's identity channel and the ae round trip -- do not vanish, and they are
        # TWO and not three: the balance term reaches A only THROUGH the identity channel, measured
        # at exactly 0.0 with FAB_ROUTE_LEARN=0 and FAB_BALANCE at its default. See this function's
        # docstring for the whole ablation.
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
        if decode_on:
            # ens_k IS WHAT DECODES, chain_k IS WHAT COMPUTES, and the society arm widens the decode
            # to max(ens_k, ind_k) because the independence term charges its own experts with
            # solving the task alone -- the old tree's `k=max(ENS_K, IND_K)` (self_organize.py:6846),
            # a coupling that was invisible under the bare name.
            decode_k = max(1, min(k, max(ens_k, ind_k) if society else ens_k))
            parts = [_decode(head, pop.modules["norm"](out[:, j])) for j in range(decode_k)]
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

    # A COUNTERFACTUAL WALK MOVES NO COUNT. It used to move two of the most-read ones: with eight
    # leave-one-out candidates on one window, fab.route_calls read 9 for a single routed window and
    # fab.hops_taken read 27 for three hops taken -- so every per-pass rate computed from either
    # (halt mass per call, hops per call, bans per pass) was divided by a denominator the measurement
    # itself had inflated. That is the instrument moving because it was read, which is the defect
    # class this project exists to kill, and it stood two lines under this body's own sentence that a
    # counterfactual "mutates NOTHING and learns NOTHING". The ONE key a counterfactual may touch is
    # fab.holdout_applied, which exists to count counterfactuals: it is not a reading of the routed
    # walk, it is the number of times the walk was interrogated. The seeding loop above stays on both
    # paths because setdefault can create a key at zero and can never move one.
    if solo:
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
    spent_on_base = 0
    if society and head is not None and last_hop_lg is not None and entry_halt is not None:
        held = entry_halt[:, None, None]
        logits_out = (1.0 - held) * last_hop_lg + held * _decode(head, h0)
        # THE COUNTER SAYS MASS WAS SPENT, SO IT MAY NOT COUNT A BLEND THAT SPENT NONE. At
        # FAB_HALT=0 the halt column is PINNED at a constant and fabric/api.py::_halt_logit's
        # caller sets ph to zeros, so `held` is exactly 0, this line is the identity
        # `logits_out = last_hop_lg`, and the counter still read one spend per society pass. A name
        # that says "halt mass was spent on the base representation" over a pass where the halt
        # operator is switched off is the wrong-measurement family inside a counter name -- the same
        # shape as reporting a cull on a population that cannot be culled. The ARITHMETIC is
        # unchanged and stays unconditional: at held=0 the blend is a no-op and computing it is what
        # keeps the two arms one code path. Only the claim is now conditional on the operator being
        # on AND on some row actually halting, and `fab.halt_mass_train` carries how much.
        spent_on_base = 1 if (halt_on and float(entry_halt.detach().max()) > 0.0) else 0
        if spent_on_base and solo:
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
    # THE GRAPH IT TESTS IS `bal_graph`, TAKEN AT THE ACCUMULATION SITE, and not `bal.grad_fn`.
    # `bal` descends from `zero`, which carries h's graph by design, so `bal.grad_fn is not None`
    # answers a question about the SEED and reads TRUE on a pass where the term reaches nothing --
    # see the comment at `bal_graph`'s declaration for the configuration and the gradient that
    # proves it dead there. The alarm's subject is the balance term, so the alarm reads the balance
    # term. The VALUE half stays on `bal` because that is the number the objective multiplies.
    if balance_w > 0.0 and training and solo:
        live_term = bal_graph and float(bal.detach()) != 0.0
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
        if ind_applied and solo:
            _bump(counters, "fab.ind_applied")
    hopsup_applied = 0
    if hop_sup_w > 0.0 and targets is not None and len(hop_logits) > 1:
        sup = None
        for lg in hop_logits[:-1]:                 # the last hop IS the main loss; don't double-count
            ce = F.cross_entropy(lg.reshape(-1, lg.size(-1)), targets.reshape(-1))
            sup = ce if sup is None else sup + ce
        aux = aux + hop_sup_w * (sup / max(1, len(hop_logits) - 1))
        hopsup_applied = 1
        if solo:
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
                             f"FAB_BALANCE={balance_w}: no load-balance pressure. This is 'off', "
                             f"not C2 -- the C2 alarm is fab.balance_nonzero reading 0 while this "
                             f"is above zero. The value is PRINTED rather than asserted to be 0, "
                             f"and a value BELOW zero does not reach here: fabric/api.py::build "
                             f"refuses at `v < 0.0`, because at balance_w < 0 this term was still "
                             f"APPLIED, with its sign reversed, under this same reason. NEGATIVE "
                             f"ZERO is the one value carrying a minus sign that survives that "
                             f"test -- -0.0 is not less than 0.0 -- and `balance_w > 0.0`, the "
                             f"verdict above, is False for it exactly as it is for +0.0, which is "
                             f"why the equation opening this sentence may print a minus sign."))
    # THE DEFICIT BONUS IS ARMED ON A TABLE ONE ENTRY POINT WRITES, and that is a third state. `use`
    # is credited by fabric/api.py::observe and by nothing else, so on a run where that entry point
    # is never CALLED every expert's utilization is 0, the fair share is 0, and there is no deficit
    # to score -- which is not the same statement as "ec_w is off" and not the same as "every expert
    # was already at its share". The stub is gone (2026-09-17) and the third state is not: a body
    # that exists and a body that runs are different facts, and spine/loop.py's RunResult.skipped is
    # the only place the second one is answered.
    _use_total = float(sum(pop.use[:n]))
    gates.append(Gate("fab.expert_choice", ec_any, value=f"ec_w={ec_w}",
                      threshold=f"sum(use)={_use_total}",
                      reachable=bool(ec_w > 0.0 and n > 1 and _use_total > 0),
                      reason="" if (ec_w > 0.0 and n > 1 and _use_total > 0) else
                             (f"FAB_EC_W={ec_w}: allocation by loss pressure (`balance`) only."
                              if ec_w <= 0.0 else
                              "n_live is 1: one expert has no share to be under." if n <= 1 else
                              "every `use` is 0: FAB.observe is the only writer of the utilization "
                              "table, so until it has been called on a routed flush every share is "
                              "zero and the deficit with it. The body landed 2026-09-17; whether "
                              "the driver CALLS it is a different question and RunResult.skipped "
                              "is where that one is answered.")))
    # THE SWAP NEEDS TWO COMPUTED SLOTS AND THE GATE HAD NOT SAID SO. fabric/api.py::_explore_swap
    # refuses at `k >= 2` because the swap gives away the LOWEST-RANKED of the computed experts, and
    # k here is max(1, min(chain_k, n)) -- so at FAB_CHAIN_K=1 there is no lowest-ranked slot to
    # give away and exploration CANNOT fire at any FAB_EXPLORE. Without this clause the gate read
    # "armed, did not fire (0 row(s) swapped ... vs explore=0.15)" at chain_k=1, which is the
    # untrippable-guard class printed as a measurement.
    _k_live = max(1, min(chain_k, n))
    _explore_ok = bool(explore > 0.0 and learn and _k_live >= 2 and n > _k_live)
    gates.append(Gate("fab.explore", explored_rows > 0,
                      value=f"{explored_rows} row(s) swapped, "
                            f"{len(pop.marks.get('explore', ()))} distinct cold target(s)",
                      threshold=f"explore={explore}, computed={_k_live} of n_live={n}",
                      reachable=_explore_ok,
                      reason="" if _explore_ok else
                             (f"FAB_EXPLORE={explore}: nothing stands between the utilization "
                              f"cull and a self-fulfilling ranking." if explore <= 0.0 else
                              "training passes only, and this was an eval or a counterfactual"
                              if not learn else
                              f"FAB_CHAIN_K={chain_k} computes {_k_live} expert per hop: the swap "
                              f"gives away the lowest-ranked computed slot and there is no second "
                              f"slot to rank it against." if _k_live < 2 else
                              f"n_live={n} does not exceed chain_k, so every expert is already "
                              f"computed and there is no cold set to swap one in from.")))
    gates.append(Gate("fab.discover", discovered > 0,
                      value=f"{discovered} handover(s), "
                            f"{len(pop.marks.get('discover', ()))} distinct recipient(s)",
                      threshold=f"cosine distance > {discover}",
                      reachable=bool(discover > 0.0 and learn and n > 1),
                      reason="" if (discover > 0.0 and learn and n > 1) else
                             (f"FAB_DISCOVER={discover}: material nothing owns is absorbed by the "
                              f"nearest incumbent." if discover <= 0.0 else
                              "training passes only" if not learn else
                              "n_live=1: there is no least-used expert to hand it to.")))
    gates.append(Gate("fab.distinctness", bool(div_applied), value=f"div_w={div_w}",
                      threshold=f"chain_k={chain_k} >= 2, n_live={n}",
                      reachable=bool(div_w > 0.0 and min(chain_k, n) >= 2 and solo),
                      reason="" if (div_w > 0.0 and min(chain_k, n) >= 2 and solo) else
                             (f"FAB_DIV_W={div_w}: nothing pays two co-routed experts for producing "
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
    # DEEP SUPERVISION NEEDS A HOP THAT IS NOT THE LAST ONE, AND THE GATE HAD NOT SAID SO. The body
    # scores `hop_logits[:-1]` -- the last hop IS the main loss and double-counting it is not
    # supervision -- so at depth 1 there is nothing to score and hop_sup CANNOT fire at any
    # FAB_HOP_SUP. Depth is 1 whenever FAB_SOCIETY=1 pins it there, and also whenever FAB_HOPS,
    # FAB_DEPTH0 or the 2 + n_live//2 ramp resolve to one hop. Without this clause the gate read
    # "armed, did not fire (hop_sup=0.3 vs 1 hop logits collected)" on the society arm -- a
    # mechanism that cannot fire, reported as one that ran and found nothing.
    _sup_ok = bool(hop_sup_w > 0.0 and targets is not None and head is not None
                   and len(hop_logits) > 1)
    _why_depth = ("FAB_SOCIETY=1 pins the walk at one hop" if society else
                  f"FAB_HOPS={hops}, FAB_DEPTH0={depth0}, n_live={n}")
    gates.append(Gate("fab.hop_sup", bool(hopsup_applied), value=f"hop_sup={hop_sup_w}",
                      threshold=f"{len(hop_logits)} hop logits collected over depth={depth}",
                      reachable=_sup_ok,
                      reason="" if _sup_ok
                             else (f"FAB_HOP_SUP={hop_sup_w}" if hop_sup_w <= 0.0 else
                                   "no targets were supplied, so a per-hop cross-entropy has "
                                   "nothing to score against" if targets is None else
                                   "no head was supplied, so no hop can produce logits"
                                   if head is None else
                                   f"depth={depth} ({_why_depth}): the last hop IS the main loss, "
                                   f"so a walk of one hop has no earlier hop to supervise.")))
    gates.append(Gate("fab.independence", bool(ind_applied), value=f"ind_w={ind_w}, ind_k={ind_k}",
                      threshold="society=True and targets supplied",
                      reachable=bool(society and ind_w > 0.0 and targets is not None
                                     and head is not None),
                      reason="" if (society and ind_w > 0.0 and targets is not None
                                    and head is not None) else
                             ("FAB_SOCIETY=0: per-expert logits are not retained on the looped arm, "
                              "so 'solve it alone' has no per-expert prediction to score"
                              if not society else
                              f"FAB_IND_W={ind_w}" if ind_w <= 0.0 else
                              "no head was supplied, so no expert can produce a prediction of its "
                              "own" if head is None else "no targets were supplied")))
    # THE ROUND TRIP IS A TRAINING-ONLY TERM AND THE GATE HAD NOT SAID SO. The body's condition is
    # `spawn_on and ae_w > 0.0 and learn`, and `learn` is `training and solo`: an eval pass builds no
    # loss and a leave-one-out counterfactual adds no loss term, so on either of those the round trip
    # CANNOT fire. Without this clause the gate read "armed, did not fire (ae_w=0.5, emb_var=1.0 vs
    # spawn=True, training=False)" on every eval pass -- and the threshold it printed named the one
    # condition that was false as though it were satisfied. fab.explore and fab.discover already
    # draw exactly this distinction; this gate was the one that did not.
    _ae_ok = bool(spawn_on and ae_w > 0.0 and learn)
    gates.append(Gate("fab.identity_round_trip", bool(ident_term),
                      value=f"ae_w={ae_w}, emb_var={emb_var}, "
                            f"{min(n, 256) if ident_term else 0} embedding(s) scored",
                      threshold=f"spawn={spawn_on}, training={training}, counterfactual={not solo}",
                      reachable=_ae_ok,
                      reason="" if _ae_ok else
                             ("FAB_SPAWN=0 also switches off the identity autoencoder: edec exists "
                              "only to specify a newborn, so nothing would read what it learned."
                              if not spawn_on else f"FAB_AE_W={ae_w}" if ae_w <= 0.0 else
                              "training passes only, and this was an eval or a counterfactual")))
    gates.append(Gate("fab.halt", halt_on, value=f"mean halted mass "
                                                  f"{round(float((1.0 - alive).mean().detach()), 4)}",
                      threshold=f"halt_max={halt_max}",
                      reason="" if halt_on else
                             "FAB_HALT=0: the halt logit is PINNED at a constant rather than "
                             "derived, so halt_key and halt_b receive no gradient and the walk "
                             "always runs its full depth."))
    # THE COUNTER fab.halt_spent_on_base NOW HAS A GATE, because a cumulative 0 says neither "the
    # society arm ran and no row halted" nor "there is no society arm on this configuration". The
    # spend exists ONLY on the society arm: the looped walk spends halt mass on the hop that stopped,
    # which the accumulation above already did, so on that arm this mechanism is not off, it is
    # absent.
    _base_ok = bool(society and head is not None and halt_on)
    gates.append(Gate("fab.halt_spent_on_base", bool(spent_on_base),
                      value=f"max entry halt "
                            f"{0.0 if entry_halt is None else round(float(entry_halt.detach().max()), 4)}",
                      threshold=f"society={society}, halt={halt_on}",
                      reachable=_base_ok,
                      reason="" if _base_ok else
                             ("FAB_SOCIETY=0: the looped walk spends halt mass on the hop that "
                              "stopped, so there is no leftover mass for the base representation "
                              "to complete." if not society else
                              "no head was supplied, so there is nothing to decode the base "
                              "representation with" if head is None else
                              "FAB_HALT=0: the halt column is pinned at a constant and no mass "
                              "halts, so the blend is the identity on the vote.")))
    gates.append(Gate("fab.forward.routed", True, value=f"{hops_taken} hop(s) over {n} experts",
                      threshold=f"depth={depth}"))
    if learn:
        pop.pass_gates = tuple(gates)

    return FabricOut(
        # WHICH OF logits/hidden IS PRESENT IS THE STATEMENT ABOUT WHO DECODES. When the population
        # voted, the caller must NOT re-decode `hidden`: scoring a prediction through a different
        # function from the one that produced the baseline is H11, and it added a fixed offset to
        # every contribution -- which set the SIGN of contrib, the thing both spare rules test.
        # THE GATES ARE ON THE RECORD AND NOT APPENDED TO pop.gates. Appending would grow one tuple
        # by a dozen entries per window for the length of a run, and a report reading the last pass's
        # arithmetic would have to find it among thousands; fabric/api.py::build's gates describe
        # the BUILD, which happens once, and these describe THIS PASS. The last TRAINING pass's copy
        # REPLACES pop.pass_gates (set just above), which is what fabric/api.py::counters renders.
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
      - `dom_of[e].add(domain_id)`, the affiliation the breadth cap reads -- PER ROW.

    domain_id: one int for the whole batch, or ONE ID PER WINDOW (a length-B sequence or (B,)
    tensor), which is what spine/loop.py passes since 2026-09-24 (Q-FAB-10). With the scalar the loop handed
    over -- the LAST window's id -- every earlier window of a mixed batch was affiliated with
    another window's domain: measured at OPT_BATCH_WINDOWS=4 over 240 windows, 21 of 60 flushes
    spanned more than one domain and every one of them was booked under one. A scalar is still accepted and is the
    same id for every row, which is exact at OPT_BATCH_WINDOWS=1.

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

    LEVERS READ: comp_ema, err_fast, err_slow, chain_k, grace
    TWO OF THOSE FIVE WERE ADDED WITH THE BODY, 2026-09-17, AND NEITHER IS A CONVENIENCE -- the line
    read three until then and its own DID IT FIRE block below could not be satisfied by three:
      `grace` because fab.experts_past_grace_ever IS a comparison against it. The counter is
        declared four lines down, it is CUMULATIVE by that declaration, and there is no way to
        decide whether an expert has ever crossed the line without reading where the line is.
      `chain_k` because "the COMPUTED experts" is what this function credits, and FabricOut does not
        carry them. FabricOut.weights is the routing distribution ACCUMULATED over the hops and
        RENORMALISED (fabric/api.py::forward), so the per-hop top-`chain_k` sets are not on the
        record; the top-`chain_k` of the accumulated weights is the same set EXACTLY at one hop and
        the union approximation above it. AT THE SHIPPED DEFAULTS THE RECONSTRUCTION IS EXACT --
        depth0=1 means one hop, so `weights` IS that hop's distribution -- which is also the arm the
        Q-FAB-5 arithmetic below is computed on (chain_k=8 credits per window, 8x and not 32x).
        ABOVE ONE HOP IT UNDER-CREDITS: an expert selected on three hops takes one uage tick here
        and three by the specification, so the clock ticks up to `hops` times slower than the
        paragraph above says and fab.mass_per_selection reads correspondingly high. WHAT WOULD CLOSE
        IT is a per-hop selection count leaving `forward` -- a field on FabricOut, or a re-earned
        Population slot forward writes -- and both are changes to a record and a body that are
        already landed, so it is recorded rather than taken here.
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
    THREE MORE KEYS THE BODY WRITES, DECLARED HERE BECAUSE A KEY IN THE REPORT THAT THE CONTRACT
    DOES NOT ADMIT TO PRODUCING IS THE SAME DEFECT AS A DECLARED KEY NOTHING WRITES (the count in
    fabric/api.py::forward's own DID IT FIRE block was taken in both directions for this reason):
      fab.uage_mean -- sum(uage)/n_live, the CUMULATIVE reading the example line above quotes
        ("mean uage 2.0 over 506 windows at n_live=2048"). It is a different number from
        fab.uage_per_expert_per_pass, which is this pass's RATE (credits issued / n_live), and one
        key cannot carry both: the rate says how fast the clock runs and the mean says where it has
        got to, and the unreachability sentence needs them both.
      fab.observe_unrouted -- passes where FabricOut.weights is None, which is exactly the two arms
        `forward` returns early from (FAB_ON=0 and FAB_NORM_ONLY=1). Without it "0 experts credited"
        cannot be told from "no expert was computed", which is this driver's own skipped-mechanism
        distinction arriving one entry point in.
      fab.comp_glob -- the population competence EMA itself, so the comp_protect spare's threshold
        is on the ledger beside the per-expert numbers it will be compared against.
    """
    fab = fab.owned_by("FAB")
    counters = pop.counters
    n = int(pop.n_live)
    # SEEDED BEFORE THE EARLY RETURN, so a run on FAB_ON=0 -- where every call takes that return --
    # reports this family as ZERO rather than as ABSENT. The distinction is the one _bump's
    # docstring records SIG paying for, and here the two are especially easy to confuse because
    # "nothing was credited" is the true answer on that arm and a missing key looks like it.
    for _k in ("fab.observed_windows", "fab.observe_unrouted", "fab.experts_with_use",
               "fab.experts_past_grace_ever"):
        counters.setdefault(_k, 0)
    # THE TWO OFF ARMS DO NOT PRODUCE AN ATTRIBUTION AND THIS IS NOT A FAILURE. FabricOut.weights is
    # None on exactly the paths fabric/api.py::forward returns early from -- FAB_ON=0, where the
    # forward is the identity, and FAB_NORM_ONLY=1, where the control arm keeps the normalization
    # and removes the nodes. Crediting anything here would attribute a window to a population that
    # never saw it, and returning silently would make "no expert was computed" indistinguishable
    # from "every expert scored zero". The counter is the difference.
    w = out.weights
    if w is None or n <= 0:
        _bump(counters, "fab.observe_unrouted")
        return None

    comp_ema = float(fab.comp_ema)
    r_fast, r_slow = float(fab.err_fast), float(fab.err_slow)
    grace, chain_k = int(fab.grace), int(fab.chain_k)

    losses = per_window_loss.detach().reshape(-1)
    rows = int(w.shape[0])
    if int(w.shape[1]) < n:
        # THE ROUTING TABLE IS NARROWER THAN THE POPULATION, which means this FabricOut was produced
        # before the population last grew. Refused rather than credited over the prefix: the columns
        # would still line up, so the attribution would look complete while every expert born since
        # that pass silently took none of it -- and those are exactly the experts a growth burst
        # just created because the material changed, which is the one cohort goal B is about.
        raise ValueError(
            f"FAB.observe: FabricOut.weights is {int(w.shape[1])} wide and n_live is {n}. The "
            f"record is from a pass taken before the population grew, so it cannot attribute this "
            f"flush. `forward` spawns before it routes, so a live record is never narrower than "
            f"the population it routed over.")
    if int(losses.numel()) != rows:
        # REFUSED, NOT TRUNCATED TO THE SHORTER OF THE TWO. `per_window_loss` is LM.lm_loss's
        # reduction='none' vector and `out.weights` is this flush's routing table; they are two
        # views of ONE batch, so a disagreement is a cut defect upstream and not a short read. A
        # min() here would credit the first k windows' experts with the first k windows' losses and
        # report a full attribution, which is the "row 0 only" family (H13) sized differently.
        raise ValueError(
            f"FAB.observe: per_window_loss has {int(losses.numel())} row(s) and FabricOut.weights "
            f"has {rows}. These are the same flush's batch measured twice -- LM.lm_loss's "
            f"per-window vector against FAB.forward's routing distribution -- so they cannot "
            f"disagree about how many windows there were. Attributing the overlap would report a "
            f"complete attribution over part of the batch.")

    # ONE DOMAIN ID PER ROW. A sequence must be exactly as long as the batch, for the reason the
    # per_window_loss refusal above gives: two views of one batch cannot disagree about its size.
    if isinstance(domain_id, torch.Tensor):
        dom_rows = [int(d) for d in domain_id.reshape(-1).tolist()]
    elif isinstance(domain_id, (list, tuple)):
        dom_rows = [int(d) for d in domain_id]
    else:
        dom_rows = [int(domain_id)] * rows
    if len(dom_rows) != rows:
        raise ValueError(
            f"FAB.observe: domain_id carries {len(dom_rows)} id(s) and FabricOut.weights has "
            f"{rows} row(s). One id per window, or one int for the whole batch -- a partial list "
            f"would affiliate the rows past its end with nothing and report them affiliated.")

    # THE COMPUTED SET, AND WHY IT IS RECONSTRUCTED RATHER THAN READ. See the LEVERS READ note
    # above: the per-hop selections do not leave `forward`, `weights` is their renormalised sum, and
    # this top-k is the same set exactly at the shipped depth0=1 and their union above it.
    k = max(1, min(chain_k, n))
    top = w[:, :n].detach().topk(k, dim=-1)
    # THREE HOST SYNCS FOR THE WHOLE PASS, NOT ONE PER EXPERT. At n0=2048 with chain_k=8 the loop
    # below touches 8 books per window; reading each `w[b, e]` off the device inside it would be
    # batch_w * k separate syncs on a GPU run, which is the shape of a mechanism that is correct and
    # unaffordable, and this package's whole cost argument (chain_k decouples population size from
    # per-step cost) would be spent on the instrument rather than on the experts.
    idx_l, mass_l, loss_l = top.indices.tolist(), top.values.tolist(), losses.tolist()

    # comp_glob IS THE FLUSH MEAN, WHICH IS WHAT THE SPARE COMPARES AGAINST. self_organize.py:6932
    # is `_cg = float(loss)` -- the composed per-flush loss -- and the per-expert EMA below is over
    # the per-WINDOW losses, so "this expert beats the population on its own material" is a
    # comparison between an expert's windows and all windows. Seeding on the first pass rather than
    # decaying from a zero, for the reason Population.__init__ gives for the None.
    glob = sum(loss_l) / max(1, len(loss_l))
    pop.comp_glob = glob if pop.comp_glob is None else \
        (1.0 - comp_ema) * float(pop.comp_glob) + comp_ema * glob

    # DISTINCT RECIPIENTS LIVE IN `marks` AND NOT IN A COUNTER, which is what that field is for: a
    # cumulative count of credits cannot answer "how many DIFFERENT experts were ever credited",
    # and 43 of 4096 is the reading the old attribution produced by sampling one row in sixteen.
    used = pop.marks.setdefault("used", set())
    past = pop.marks.setdefault("past_grace", set())
    credits = 0
    for r in range(rows):
        v = float(loss_l[r])
        for e, m in zip(idx_l[r], mass_l[r]):
            e = int(e)
            # TWO DIFFERENT QUESTIONS, TWO DIFFERENT NUMBERS. `use` takes the ROUTING MASS (how much
            # of this window the router actually spent on this expert) and `uage` takes ONE
            # SELECTION. The old tree's bump_use incremented both by 1 for the argmax only
            # (:2044-2051), so the cull's ranking key and its eligibility test were the same number
            # (H12) and every non-argmax expert sat at use-age 0 for ever (H13).
            pop.use[e] = float(pop.use[e]) + float(m)
            pop.uage[e] = int(pop.uage[e]) + 1
            credits += 1
            if pop.uage[e] == 1:
                # SEEDED ON THE FIRST CREDIT, AND THE TEST IS THE USE-CLOCK RATHER THAN `== 0.0`.
                # _claim_slot clears comp/ef/es to 0.0, so "never attributed" and "attributed, and
                # the loss was zero" are the same float; the selection count distinguishes them and
                # is incremented one line above. An EMA decayed from a zero would credit every
                # newborn with a perfect competence it never earned and, worse, would give it a
                # fast/slow error PAIR that agrees -- which is the failure cull's "not adapting"
                # reading, on an expert that has seen one window.
                pop.comp[e] = pop.ef[e] = pop.es[e] = v
            else:
                pop.comp[e] = (1.0 - comp_ema) * float(pop.comp[e]) + comp_ema * v
                # THE PAIR WHOSE DIFFERENCE IS THE WHOLE POINT: fast >> slow is a shift IN PROGRESS
                # and that expert is adapting, not failing, which is the goal-B protection
                # fabric/api.py::manage's shift_tol spare reads. Both are credited over the same
                # COMPUTED set, so the difference is about the expert and not about which of the
                # two happened to be updated on this window.
                pop.ef[e] = (1.0 - r_fast) * float(pop.ef[e]) + r_fast * v
                pop.es[e] = (1.0 - r_slow) * float(pop.es[e]) + r_slow * v
            # THE AFFILIATION MAP, WRITTEN EXACTLY AS THE SPECIFICATION SPELLS IT. `dom_of[e]` is a
            # SET and the breadth cap in `forward` bans an expert once len(dom_of[e]) passes
            # dom_frac x live_domains; it was one int per expert until 2026-09-04, on which this
            # line is an AttributeError -- the field the frozen docstring specified the write
            # against could not have held it. THIS ROW'S id, not the batch's (see domain_id above).
            pop.dom_of[e].add(dom_rows[r])
            used.add(e)
            if pop.uage[e] >= grace:
                past.add(e)

    _bump(counters, "fab.observed_windows", rows)
    counters["fab.experts_with_use"] = len(used)
    # CUMULATIVE, NOT THE SNAPSHOT. ISSUES P1-M58 is the record of what a snapshot costs here:
    # fabric.cull_eligible read ARMED AND INERT off a set recomputed each pass, so a run in which
    # experts crossed grace and were then culled reported that none ever had.
    counters["fab.experts_past_grace_ever"] = len(past)
    counters["fab.uage_per_expert_per_pass"] = round(credits / max(1, n), 6)
    _sum_uage = int(sum(pop.uage[:n]))
    counters["fab.uage_mean"] = round(_sum_uage / max(1, n), 6)
    # THE NUMBER THE P9 RETUNE OF `grace` MUST BE SET FROM: how many argmax-equivalents of routing
    # mass one post-split uage tick is worth. It cannot be computed at build time because it depends
    # on how sharply the router concentrates, which is why `grace` stays a literal 48 and the retune
    # is a measurement. `_sum_uage` is at least `credits` here, so the denominator guard below can
    # only be reached on a population whose books were restored empty.
    counters["fab.mass_per_selection"] = round(float(sum(pop.use[:n])) / max(1, _sum_uage), 6)
    counters["fab.comp_glob"] = round(float(pop.comp_glob), 6)
    # NOTHING IS RETURNED, AND THE ABSENCE IS DELIBERATE. compose.py's LOOP_ORDER row for this entry
    # point is a four-element row with no `produces` column: the books ARE the product, they live on
    # the Population every later reader already holds, and a record here would be a second copy of
    # numbers whose single source of truth is the point of this design.
    return None


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
                 depth_patience, depth_stage_max, hops, merge_dist, on
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
    period = fab.d_manage_period     # WIRE READ HERE -- both cadences reported side by side
    grace, cull_frac = int(fab.grace), float(fab.cull_frac)
    pressure, slots = float(fab.pressure), int(fab.slots)
    comp_protect, comp_ema = bool(fab.comp_protect), float(fab.comp_ema)
    shift_tol, fail_tol = float(fab.shift_tol), float(fab.fail_tol)
    rescue_frac, mut_big = float(fab.rescue), float(fab.mut_big)
    manage_every = int(fab.manage_every)
    depth0, hops = int(fab.depth0), int(fab.hops)
    depth_eps, depth_patience = float(fab.depth_eps), int(fab.depth_stage_max)
    depth_patience = int(fab.depth_patience)
    depth_stage_max = int(fab.depth_stage_max)
    merge_dist = float(fab.merge_dist)
    rank = int(pop.B.shape[1])
    counters, where = pop.counters, "FAB.manage"
    step = U.Windows(step_windows)
    step_n = int(step)

    # FAB_ON=0 RETURNS BEFORE THE SEEDING, SO THIS WHOLE FAMILY IS ABSENT ON THAT ARM (Q-FAB-11).
    # A selection pass over a population whose forward is the identity would cull, merge and
    # deepen experts nothing computes -- a mechanism running on a switched-off package -- and
    # seeding first would print its counters present-and-0, which G4 reads as "armed, did not
    # fire". Absent is the true reading: unreachable on the arm this run took.
    if not bool(fab.on):
        return ManageReport(manage_every=manage_every, manage_period_flushes=period,
                            cull_gate="FAB_ON=0: no selection pass runs on a switched-off fabric")

    # SEEDED BEFORE ANY BRANCH DECIDES -- the rule fabric/api.py::_bump states and that this
    # package's own sig sibling broke for a whole run. Every one of these is reachable on some arm.
    for _k in ("fab.manage_passes", "fab.cull_fail", "fab.cull_util", "fab.spared_contrib",
               "fab.spared_comp", "fab.spared_shift", "fab.rescued", "fab.deepened",
               "fab.merged", "fab.merge_declined_grace", "fab.merge_declined_residual"):
        counters.setdefault(_k, 0)
    _bump(counters, "fab.manage_passes")
    counters["fab.manage_period_flushes"] = int(period)
    counters["fab.manage_every_windows"] = manage_every

    n_live = int(pop.n_live)
    # ELIGIBLE IS PAST-GRACE, AND EVERY RANKING AND BUDGET ON THIS PASS IS SIZED ON IT. The old
    # budget was a fraction of n_live and removed ten where one was due (523 live / 84 eligible).
    # `grace` is units.Selections and `uage` is the SELECTION count -- the H12/H13 split -- so this
    # is a same-kind comparison and not a clock crossing.
    eligible = [i for i in range(n_live) if int(pop.uage[i]) >= grace]
    n_elig = len(eligible)
    # fab.cull_rank_spread IS THE FALSIFIER FOR THE REPAIR ITSELF, which is why it is computed
    # before anything is culled. Routing concentrates -- the pilot's top expert took 79.5% of
    # traffic -- so the experts that cross grace first are the MOST-USED ones, while the cull then
    # ranks that set by `use` ASCENDING. At a spread near 1 the ranking carries no information and
    # H12 has survived the use/uage split in a new dress.
    if n_elig:
        _u = [float(pop.use[i]) for i in eligible]
        counters["fab.cull_rank_spread"] = (max(_u) / min(_u)) if min(_u) > 0 else float("inf")

    # ---- 0. MERGE, BEFORE EITHER CULL (Q-FAB-2) -------------------------------------------------
    # THE ONLY MERGE-RATHER-THAN-KILL PATH IN EITHER POPULATION, which is why goal B keeps it.
    # ELIGIBILITY IS ONE GRACE TEST, ON THE EXPERT THAT DISAPPEARS. Requiring both to be past grace
    # would mean merging inside the eligible set, which sizes nothing differently; merging over the
    # whole live set would re-absorb every replicate/xover birth, which are near-duplicates BY
    # CONSTRUCTION, making `replicate` inert.
    merged = declined_grace = declined_resid = 0
    residuals = []
    if merge_dist > 0.0 and n_live > 1:
        with torch.no_grad():
            cn = torch.nn.functional.normalize(pop.cent[:n_live].float(), dim=-1)
            sim = cn @ cn.t()
        absorbed = set()
        # DESCENDING SIMILARITY so the closest pair merges first; a pair already consumed is
        # skipped rather than re-merged into a survivor whose centroid has since moved.
        pairs = []
        for i in range(n_live):
            for j in range(i + 1, n_live):
                if float(1.0 - sim[i, j]) <= merge_dist:
                    pairs.append((float(sim[i, j]), i, j))
        pairs.sort(reverse=True)
        for _sv, i, j in pairs:
            if i in absorbed or j in absorbed:
                continue
            # `b` IS THE ONE THAT DISAPPEARS AND IT IS THE ONE GRACE TESTS.
            a, b = (i, j) if int(pop.uage[j]) >= int(pop.uage[i]) else (j, i)
            a, b = (b, a) if int(pop.uage[b]) < grace and int(pop.uage[a]) >= grace else (a, b)
            if int(pop.uage[b]) < grace:
                declined_grace += 1
                continue
            resid = _merge_into(pop, a, b, rank)
            residuals.append(resid)
            absorbed.add(b)
            merged += 1
        # THE REMOVALS HAPPEN AFTER THE WHOLE SCAN AND IN DESCENDING SLOT ORDER, because _remove
        # renumbers by swap-with-last: removing a low slot first would move a later victim's id out
        # from under the list this loop is walking.
        for b in sorted(absorbed, reverse=True):
            _remove(pop, b)
        n_live = int(pop.n_live)
    if merged:
        _bump(counters, "fab.merged", merged)
        rs = sorted(residuals)
        counters["fab.merge_residual_p50"] = rs[len(rs) // 2]
        counters["fab.merge_residual_p99"] = rs[min(len(rs) - 1, int(0.99 * len(rs)))]
    if declined_grace:
        _bump(counters, "fab.merge_declined_grace", declined_grace)

    # ---- 1. FAILURE CULL, AT ANY OCCUPANCY ------------------------------------------------------
    # THE GOAL-B PROTECTION AND THE ONLY CULL PATH THAT STILL RUNS ON A SMALL OR SHRINKING
    # POPULATION. An expert is failing when BOTH error EMAs sit above the population by fail_tol
    # AND the fast one is not above the slow one by shift_tol -- because fast >> slow is A SHIFT IN
    # PROGRESS and that expert is ADAPTING, which is the single thing this project exists to keep.
    cull_fail = spared_shift = 0
    if n_elig:
        ef_pop = sum(float(pop.ef[i]) for i in range(n_live)) / max(1, n_live)
        es_pop = sum(float(pop.es[i]) for i in range(n_live)) / max(1, n_live)
        failing = []
        for i in list(eligible):
            if i >= n_live:
                continue          # renumbered away by the merge above
            ef_i, es_i = float(pop.ef[i]), float(pop.es[i])
            if ef_i > ef_pop + fail_tol and es_i > es_pop + fail_tol:
                if ef_i - es_i > shift_tol:
                    spared_shift += 1
                else:
                    failing.append(i)
        for i in sorted(failing, reverse=True):
            _remove(pop, i)
            cull_fail += 1
        n_live = int(pop.n_live)
        eligible = [i for i in range(n_live) if int(pop.uage[i]) >= grace]
        n_elig = len(eligible)

    # ---- 2. UTILIZATION CULL, behind derive.cull_gate_open ---------------------------------------
    # THAT FUNCTION IS CALLED, NOT RESTATED. It is already replayed against a 216-case oracle, and
    # it is TWO conditions -- n_live <= 2 is a FLOOR, not a pressure test -- which is why people
    # read it as one. THE ARITHMETIC IS RECORDED EVERY PASS whether it opened or not, so a run that
    # was above pressure for most of its length and below it at the end does not print
    # "unreachable".
    gate_open = _derive.cull_gate_open(n_live, slots, pressure)
    gate_str = (f"n_live={n_live} / slots={slots} = {n_live / max(1, slots):.3f} against "
                f"FAB_PRESSURE={pressure} with the n_live<=2 floor: "
                f"{'OPEN' if gate_open else 'SHUT'}")
    # THE GATE'S ARITHMETIC GOES ON A Gate AND NOT INTO THE COUNTER LEDGER, and the first driven
    # run of this body is why. `fab.cull_gate` is a DECLARED GATE NAME, and fabric/api.py::counters
    # renders every gate by looking its name up in the ledger and calling int() on what it finds --
    # so a string stored under that key raised ValueError from inside the REPORT PATH, after a
    # 600-window run had already completed. The ledger is declared {name: int}; a sentence is a
    # Gate's `reason`, which is exactly the field that exists to carry arithmetic.
    cull_util = spared_contrib = spared_comp = 0
    if gate_open and n_elig:
        # THE BUDGET IS SIZED ON THE ELIGIBLE SET AND THE max(1, ...) RATCHET IS DROPPED. The budget
        # MAY BE ZERO, and fab.cull_util == 0 under an OPEN gate is a legitimate reported outcome
        # rather than something the code refuses to allow -- the ratchet is the pattern the
        # DomainAssembler documents as having driven a population down to a single member.
        budget = int(cull_frac * n_elig)
        ranked = sorted(eligible, key=lambda i: float(pop.use[i]))
        victims = []
        for i in ranked:
            if len(victims) >= budget:
                break
            # THE THREE SPARES, EACH ITS OWN COUNTER BECAUSE EACH IS A DIFFERENT REASON TO SURVIVE.
            if float(pop.contrib[i]) > 0.0:
                spared_contrib += 1
                continue
            if comp_protect and float(pop.comp[i]) > float(pop.comp_glob or 0.0):
                spared_comp += 1
                continue
            if float(pop.ef[i]) - float(pop.es[i]) > shift_tol:
                spared_shift += 1
                continue
            victims.append(i)
        for i in sorted(victims, reverse=True):
            _remove(pop, i)
            cull_util += 1
        n_live = int(pop.n_live)

    # ---- 5. RESCUE: a heavy mutation instead of a deletion, inside the pressure gate -------------
    # ONCE PER EXPERT. `mutscale` carries whether this expert has already been rescued, so a slot
    # cannot be rescued repeatedly into noise -- and the Adam moments on A[i], B[i] are STALE after
    # an in-place write, which this does not fix and must not pretend to.
    rescued = 0
    if gate_open and rescue_frac > 0.0 and n_elig:
        worst = sorted([i for i in range(n_live) if int(pop.uage[i]) >= grace],
                       key=lambda i: float(pop.use[i]))
        for i in worst[:int(rescue_frac * max(1, n_elig))]:
            if float(pop.mutscale[i]) != 1.0:
                continue
            with torch.no_grad():
                for t in (pop.A, pop.B):
                    t[i] += torch.randn(t[i].shape, generator=pop.rng.torch_generator(),
                                        device=t.device, dtype=t.dtype) * mut_big * t[i].std()
            pop.use[i], pop.uage[i] = 0.0, 0
            pop.mutscale[i] = float(mut_big)
            rescued += 1
        pop.rescued = int(pop.rescued) + rescued

    # ---- 6. maybe_deepen(flush_loss) when the curriculum is on ----------------------------------
    # THE UNIT FAULT IS INHERITED AND REPORTED RATHER THAN SILENTLY CARRIED: depth_eps is declared
    # BITS_PER_BYTE and flush_loss is a per-flush cross-entropy in NATS PER TOKEN. The repair is
    # owed at the COMPARISON, not at the declaration, so the comparison converts and the counter
    # says which unit it was made in.
    deepened = False
    if 0 < depth0 < hops and flush_loss is not None:
        g = pop.growth
        prev = g.get("depth_prev")
        bits = float(flush_loss) / math.log(2.0)
        counters["fab.depth_compared_in"] = "bits_per_token"
        if prev is not None and (prev - bits) < depth_eps:
            g["depth_wait"] = int(g.get("depth_wait", 0)) + 1
            if g["depth_wait"] >= depth_patience and int(pop.depth_now) < min(hops,
                                                                              depth_stage_max):
                pop.depth_now = int(pop.depth_now) + 1
                g["depth_wait"] = 0
                deepened = True
                _bump(counters, "fab.deepened")
        else:
            g["depth_wait"] = 0
        g["depth_prev"] = bits

    for k, v in (("fab.cull_fail", cull_fail), ("fab.cull_util", cull_util),
                 ("fab.spared_contrib", spared_contrib), ("fab.spared_comp", spared_comp),
                 ("fab.spared_shift", spared_shift), ("fab.rescued", rescued)):
        if v:
            _bump(counters, k, v)

    # ---- THREE STATES, NOT TWO, FOR EVERY GATE ON THIS PASS (Q-FAB-5) ---------------------------
    # `fabric.cull_eligible` and `fab.merged` report UNREACHABLE -- never "armed but 0" -- when the
    # eligible set is empty, WITH THEIR OWN ARITHMETIC. This CANNOT ride
    # derive.cadences_that_cannot_fire: that audit refuses anything that is not units.Windows and
    # `grace` is units.Selections, so the reachability statement is FAB-owned by construction.
    _mean_uage = sum(int(pop.uage[i]) for i in range(n_live)) / max(1, n_live)
    _reach = (f"mean uage {_mean_uage:.1f} at n_live={n_live} after {step_n} window(s); "
              f"grace={grace} selection(s)")
    _gates = tuple(g for g in pop.gates
                   if g.name not in ("fabric.cull_eligible", "fab.merged", "fab.cull_gate"))
    pop.gates = _gates + (
        Gate("fabric.cull_eligible", n_elig > 0, n_elig, grace,
             reachable=n_elig > 0,
             reason=(f"{n_elig} of {n_live} expert(s) are past grace and rankable; {_reach}"
                     if n_elig else
                     f"unreachable ({_reach}): NO expert has been SELECTED grace times, so the "
                     f"eligible set is empty and every ranking, budget and spare on this pass is "
                     f"sized on nothing. This is not 'armed and did not fire'")),
        # RECORDED EVERY PASS WHETHER IT OPENED OR NOT, which the contract requires in as many
        # words: "The gate's arithmetic is recorded EVERY pass whether it opened or not, so a run
        # that was above pressure for most of its length and below it at the end does not print
        # 'unreachable'." So this Gate is always REACHABLE -- what varies is `fired`.
        Gate("fab.cull_gate", gate_open, n_live, pressure, reason=gate_str),
        Gate("fab.merged", merged > 0, merged, merge_dist,
             reachable=n_elig > 0 and merge_dist > 0.0,
             reason=(f"{merged} pair(s) consolidated within FAB_MERGE_DIST={merge_dist} cosine; "
                     f"residual p50/p99 "
                     f"{counters.get('fab.merge_residual_p50', 0.0):.4f}/"
                     f"{counters.get('fab.merge_residual_p99', 0.0):.4f}"
                     if merged else
                     f"FAB_MERGE_DIST={merge_dist} is 0: merging is off by configuration"
                     if merge_dist <= 0.0 else
                     f"unreachable ({_reach}): the absorbed expert must be past grace and no "
                     f"expert is. {declined_grace} pair(s) were close enough and declined for it")))

    return ManageReport(
        merged=merged, merge_declined_grace=declined_grace,
        merge_declined_residual=declined_resid, cull_fail=cull_fail, cull_util=cull_util,
        spared_contrib=spared_contrib, spared_comp=spared_comp, spared_shift=spared_shift,
        rescued=rescued, deepened=deepened, eligible=n_elig, cull_gate=gate_str,
        manage_every=manage_every, manage_period_flushes=period)


# ==================================================================================================
# PRIVATE HELPERS FOR GROWTH.
#
# Same three rules as the forward pass's block above and for the same reasons: underscore-prefixed
# so they do not join the frozen entry-point surface, NO Config in any signature (O9 -- one owner
# assertion per entry point, not one per helper), and NO clock lever read off a Config here. Every
# window count arrives as a bare int the caller has already put through units.Windows, so the
# arithmetic below is same-kind (windows against windows) and is not the cross-kind conversion
# spine/units.py::Clock.convert requires a named function in spine.derive for.
# ==================================================================================================

_FAST_EMA, _SLOW_EMA, _MAD_EMA = 0.02, 0.002, 0.01
"""The growth controller's three EMA rates: fast, slow, and the running mean absolute deviation.

PORTED VERBATIM AND DELIBERATELY NOT LEVERS. self_organize.py:2997-2999 is
`s.fast = 0.98*s.fast + 0.02*loss`, `s.slow = 0.998*s.slow + 0.002*loss` and
`s.dev = 0.99*s.dev + 0.01*d`; the three constants are hardcoded there and the census minted no row
for any of them. Three reasons they stay constants rather than becoming FABLevers rows 83, 84 and
85, in the order they bind:
  1. `z` AND `plateau` ARE EXPRESSED IN THESE UNITS. z is "how many robust deviations above the
     slow EMA" and plateau is "relative improvement OF THE SLOW EMA", so moving a rate silently
     reprograms both triggers without either lever's value changing -- the L1 defect (a lever whose
     default is computed from another lever) arriving through a rate instead of through a default.
  2. A lever with no census row is what tests/test_census.py exists to refuse, and three new rows
     would each need the departure entry and the measurement that this round has not taken.
  3. THE RATIO IS THE MECHANISM, not the values: fast/slow at 10x apart is what makes
     (slow - fast)/|slow| a plateau reading at all, and a pair of independent levers admits the
     configuration fast == slow, where `improving` is identically zero and the stall trigger fires
     on every check after warmup.
WHAT THIS IS NOT: a claim that 0.02/0.002/0.01 are right. They have never been swept in this
project, and a sweep is the thing that would justify a lever."""


def _loss_float(x, where):
    """One flush's loss as a plain float, whether it arrived pooled or per-window.

    EXPLICIT DISPATCH ON THE TYPE, NEVER `getattr(x, "mean", None)`. compose.py's LOOP_ORDER row
    says flush_loss is "per_window -- the same return pooled over the flush", and a caller that
    hands the unpooled vector is handing the same quantity one reduction earlier; both are real and
    both are accepted, but WHICH arrived is decided by asking the type, not by probing for a method
    that a float does not have and a tensor does.
    """
    if x is None:
        raise ValueError(
            f"{where}: flush_loss is None. The growth triggers ARE a reading of the loss -- a "
            f"regression is `loss - slow > z * dev` and a stall is a relative improvement of the "
            f"slow EMA -- so there is no answer to give without one, and returning 'did not grow' "
            f"would report a trigger that was never evaluated as one that was and declined.")
    if isinstance(x, torch.Tensor):
        return float(x.detach().float().mean())
    return float(x)


def _headroom(soft_cap, n, where):
    """How many more experts CAP's operating ceiling admits, THROUGH Caps.headroom and never by
    subtracting.

    THE SUBTRACTION IS THE C30 FREEZE AND IT MAY NOT BE WRITTEN HERE. `min(n_born, cap - fab.n())`
    (:7446) is negative the moment the population exceeds the soft cap, which at the shipped
    FAB_N0=2048 against a valve starting below it is the state on step 0 (Q-CAP-2), and a negative
    clamp freezes growth FOR THE WHOLE RUN with nothing in the log saying so -- the trigger counts
    still increment and the pin counter reads exactly as it would on a population legitimately at
    its cap. capacity/api.py::Caps.headroom exists so that expression cannot be written at a call
    site, and this function's whole body is the call. THE max(0, ...) IS NOT REPEATED HERE: the
    record guarantees it, and a second implementation of a one-line method is two answers to one
    quantity, which is what the wire discipline exists to stop.

    A BARE INT IS REFUSED, LOUDLY, AND THAT IS A REAL DISAGREEMENT IN THE CONTRACT rather than
    defensive typing. spine/compose.py's CAP.caps row says the produced value is "soft_cap --
    Caps.experts under FAB.grow_check's spelling" (an int) and says, four lines below, "THE LOOP
    TAKES ITS BIRTH BUDGET THROUGH Caps.headroom(population) AND NEVER BY SUBTRACTING". Both cannot
    be true at this call site: FAB may not import capacity (O10), so the only way to reach the
    method is for the RECORD to arrive. Refusing an int is what makes the choice visible on the day
    the root wires it, instead of leaving FAB to re-derive the subtraction the method was created to
    delete.
    """
    room = getattr(soft_cap, "headroom", None)
    if not callable(room):
        raise TypeError(
            f"{where}: soft_cap arrived as {type(soft_cap).__name__} and this entry point needs "
            f"the capacity/api.py::Caps RECORD, because the birth budget is Caps.headroom(n) and "
            f"nothing else. Pass `soft_cap=caps` (the whole record CAP.caps returns), not "
            f"`caps.experts`: differencing the integer here would re-create `min(n_born, cap - "
            f"fab.n())`, which is ISSUES P3-C30 -- negative the moment the population sits above "
            f"the soft cap, which at FAB_N0=2048 it already does (Q-CAP-2), and silent for the "
            f"whole run. FAB cannot import capacity (O10), so the method has to arrive on the "
            f"object.")
    return int(room(int(n)))


def _signature_point(signature, like, where):
    """The flush's signature as ONE unit vector in the space the centroids live in, ON THEIR DEVICE.

    THE DEVICE MOVE IS NOT DEFENSIVE TYPING. SIG builds its own tensor and need not agree with the
    process device -- spine/loop.py moves it explicitly for exactly that reason -- and this vector
    is both multiplied against `cent` and written into it. Left where it arrived it is a
    device-mismatch raise on the first birth of every GPU run and never on a CPU smoke test, which
    is the failure shape fabric/api.py::build names as the worst one this defect can take.

    The batch is averaged because a birth is ONE event answering ONE flush: the material that
    triggered it is the flush, not a window, and picking row 0 would make the newborn's region a
    property of the batch's cut. The width is CHECKED rather than assumed -- an einsum five frames
    down naming a shape is the geometry failure fabric/api.py::forward refuses by name at the one
    place a live tensor can prove it, and this is that place for the centroid space.
    """
    s = signature.detach().float()
    s = s.mean(0) if s.dim() > 1 else s
    want = int(like.shape[1])
    if int(s.numel()) != want:
        raise ValueError(
            f"{where}: the signature is {int(s.numel())} wide and the centroids are {want}. "
            f"A newborn's region is written in SIG's space, so a mismatch here would either raise "
            f"inside the cosine or, at a coincidence of widths, place every birth in a region "
            f"nothing means.")
    return F.normalize(s.to(device=like.device, dtype=torch.float32), dim=-1)


def _fitness_pick(rng, cands, use):
    """One parent, SAMPLED proportional to fitness within the shortlist. Never argmaxed.

    Argmax is greedy cloning of the incumbent: at parent_k=8 it would make every birth in a burst a
    child of the same expert, which converts population growth into population duplication and is
    exactly what parent_max exists to bound. Sampling keeps the shortlist meaningful.

    ALL-ZERO FITNESS IS UNIFORM, AND IT IS THE STATE A RUN STARTS IN. `use` is credited only by
    fabric/api.py::observe, so before the first attributed flush every candidate reads 0.0 and a
    weighted draw over all-zero weights is undefined (random.choices raises). Uniform is the honest
    answer there -- nothing is known about these experts yet -- and it is not a fallback that hides
    a fault, because the same condition is what fab.experts_with_use reports.
    """
    w = [max(0.0, float(use[c])) for c in cands]
    if sum(w) <= 0.0:
        return rng.choice(cands)
    return rng.choices(cands, weights=w, k=1)[0]


def _birth_write(pop, dst, gen, *, src=None, other=None, scale=0.0, point=None, jitter=0.0,
                 rank_take=()):
    """Write ONE newborn's adapter and centroid. `src=None` mints a fresh identity.

    CROSSOVER TAKES A WHOLE RANK SLICE FROM BOTH FACTORS, and that pairing is the mechanism rather
    than a detail: an expert's function is dW = A @ B, so rank direction j is column j of A TOGETHER
    WITH row j of B. Taking one without the other would splice a left factor onto an unrelated right
    factor and produce a direction neither parent ever learned -- the same arithmetic error the
    merge in fabric/api.py::manage records for averaging the factors instead of the product.

    THE MUTATION IS RELATIVE TO THE PARENT'S OWN STD, so it means the same thing for a well-trained
    parent and a fresh one; that is the scale-free discipline `z` and `spawn_mult` also use. B IS
    ZERO AT A FOUNDER'S BIRTH, so a child of an untrained parent inherits a zero B, its own std is
    zero and its B mutation is zero too -- the newborn is an IDENTITY, which is the Population
    docstring's guarantee holding rather than an inert mutation.

    THE CENTROID IS THE TRIGGERING SIGNATURE PLUS JITTER because a burst grows several experts at
    ONE signature; without the jitter they are born with identical regions and can never
    differentiate (fabric/levers.py::FABLevers.birth_jitter quotes its own source on that).
    """
    with torch.no_grad():
        if src is None:
            # THE FOUNDING INITIALISATION, VERBATIM FROM `build`: A drawn uniform at 1/sqrt(d_model)
            # and B left at ZERO, so a fresh birth is an identity and adding it disturbs nothing.
            bound = (1.0 / max(1, int(pop.A.shape[1]))) ** 0.5
            a = torch.empty_like(pop.A[dst]).uniform_(-bound, bound, generator=gen)
            b = torch.zeros_like(pop.B[dst])
        else:
            a, b = pop.A[src].clone(), pop.B[src].clone()
            if other is not None and len(rank_take):
                idx = torch.tensor(list(rank_take), dtype=torch.long, device=a.device)
                a[:, idx] = pop.A[other][:, idx]
                b[idx, :] = pop.B[other][idx, :]
            if scale > 0.0:
                sa = float(a.std()) if a.numel() > 1 else 0.0
                sb = float(b.std()) if b.numel() > 1 else 0.0
                if sa > 0.0:
                    a = a + (scale * sa) * torch.randn(a.shape, generator=gen, device=a.device,
                                                       dtype=a.dtype)
                if sb > 0.0:
                    b = b + (scale * sb) * torch.randn(b.shape, generator=gen, device=b.device,
                                                       dtype=b.dtype)
        pop.A[dst], pop.B[dst] = a, b
        c = point.to(device=pop.cent.device, dtype=pop.cent.dtype)
        if jitter > 0.0:
            c = c + jitter * torch.randn(c.shape, generator=gen, device=c.device, dtype=c.dtype)
        pop.cent[dst] = F.normalize(c, dim=-1)


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
                 birth_jitter, grow_on_mem_pressure, spawn, slots, n0, on
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
    ELEVEN MORE KEYS THE BODY WRITES, DECLARED HERE FOR THE REASON fabric/api.py::forward gives: a
    key in the report that the contract does not admit to producing is the same defect as a declared
    key nothing writes, and the count is taken in both directions.
      fab.grow_checks -- how many times this entry point was CALLED. Without it every counter below
        reads 0 both when growth declined and when spine/loop.py never invoked it, which is the
        distinction RunResult.skipped exists to make and it has to survive one entry point in.
      fab.grow_regression_refused_cooldown / fab.grow_stall_refused_cooldown -- the old tree's
        n_regr_supp (:2946), split the way the clocks are. "Detected and refused by its own
        spacing" is not "not detected", and the regression one is the number that would have shown
        the shared-clock defect at the time rather than eight months later.
      fab.grow_recover_passes -- checks that returned inside RECOVER. A run whose growth is quiet
        because it is in lockout looks exactly like a run with no evidence, and this is the
        difference.
      fab.grow_warmup_refused -- stall checks before `warmup`, same argument one clock over.
      fab.grow_slow / fab.grow_fast / fab.grow_dev / fab.grow_improving -- THE READINGS the two
        triggers are made of, on the ledger because they exist nowhere else in the tree:
        docs/04_CONTRACT.md's ROW_ARGUMENTS_ELSEWHERE["CAP.observe"] records that `improving` is
        (slow - fast)/|slow| "off the growth controller's EMAs, which live INSIDE FAB and are on no
        returned record", and that the root must NOT maintain a second pair over the same loss. It
        still has no PARAMETER to arrive through, so this is a reading and not the join; what it
        removes is the need to re-derive it from outside.
      fab.newfrac_spent_on_spawn -- spawn births charged against the newborn budget. This is the
        HALF of "both doors are bound by the same cap" that can be closed from here: `forward`'s
        spawn writes into the pool before this entry point ever sees the flush, so it cannot be
        refused retroactively, but it CAN be made to spend the budget, and this is the option
        fabric/api.py::forward's own note names ("a rule that grow_check subtracts spawn births from
        its own budget"). The other half -- spawn ignoring FAB_GROW and the soft cap at the moment
        it fires -- is still open and is a `soft_cap` keyword on `forward`, a frozen-signature move.
      fab.cap_lift_period -- the d_cap_lift_period wire, printed beside the decline counters exactly
        as the WIRES READ line above requires, and NOT a verdict about which condition blocked a
        lift: that is CAP.counters' block-reason histogram and Q-CLOCK-1 is what retires this row.
    """
    fab = fab.owned_by("FAB")
    lift_period = fab.d_cap_lift_period        # WIRE READ HERE -- beside the decline counters
    counters, where = pop.counters, "FAB.grow_check"
    step = U.Windows(step_windows)
    step_n = int(step)

    # THE LEVERS, READ ONCE AND INTO BARE LOCALS. The clock levers among them (warmup, cooldown,
    # recover_min, recover_max) are compared against `step_windows`, which the caller has already
    # typed; reading them off the Config inside the arithmetic below would put a Clock-unit
    # attribute in an operand, which is what O11 forbids and what every cross-kind defect in this
    # project was written as.
    grow_on = bool(fab.grow)
    burst = max(1, int(fab.burst))
    z_dev, plateau = float(fab.z), float(fab.plateau)
    warm_n, cool_n = int(fab.warmup), int(fab.cooldown)
    rec_min, rec_max = int(fab.recover_min), int(fab.recover_max)
    new_frac = float(fab.new_frac)
    mem_on, spawn_on = bool(fab.grow_on_mem_pressure), bool(fab.spawn)
    replicate, parent_k = bool(fab.replicate), max(1, int(fab.parent_k))
    parent_max, birth_win = float(fab.parent_max), max(1, int(fab.birth_win))
    mut, mut_big, mut_big_p = float(fab.mut), float(fab.mut_big), float(fab.mut_big_p)
    xover, jitter = float(fab.xover), float(fab.birth_jitter)
    slots, n0 = int(fab.slots), int(fab.n0)

    # FAB_ON=0 RETURNS BEFORE THE SEEDING (Q-FAB-11). This body never read fab.on, so on the off arm
    # a regression grew an expert into a fabric whose forward is the identity -- measured, n_live
    # 2048 -> 2049 and fab.grown_regression 1 beside gate fab.on's own "every gate below this one
    # reports UNREACHABLE". The family stays ABSENT, which is G4's spelling of unreachable, and the
    # build gate fab.growth_armed says why.
    if not bool(fab.on):
        return GrowReport(gates=(Gate("fab.grow_check", False, value="FAB_ON=0",
                                      threshold="FAB_ON=1", reachable=False,
                                      reason="FAB_ON=0: nothing is grown into a fabric that is "
                                             "not in the forward."),))

    # SEEDED BEFORE ANY BRANCH DECIDES, so ABSENT never masquerades as ZERO. SIG shipped a counter
    # that was missing rather than 0 for a whole run at the one configuration the tree ships,
    # because the lines that seeded it stood inside the else of the gate they described
    # (fabric/api.py::_bump says so). These fourteen are the ones a report reads to decide whether
    # growth happened, so an absent key here is the worst possible spelling of "no".
    # THE ADDED KEYS ARE SEEDED TOO, AND LEAVING THEM OUT WAS CAUGHT BY DRIVING THIS BODY RATHER
    # THAN BY READING IT: the first run of the stall case raised KeyError on
    # fab.grow_recover_passes from the PROBE, i.e. a report that asked the ledger what the RECOVER
    # leg did would have crashed rather than read 0 -- which is the absent-versus-zero defect in the
    # one direction that is loud, and it would have been silent for any reader using .get().
    for _k in ("fab.grow_asked_regression", "fab.grow_asked_stall", "fab.grown_regression",
               "fab.grown_stall", "fab.declined_cap", "fab.declined_newfrac", "fab.replicated",
               "fab.crossed", "fab.random_born", "fab.parent_quota_refusals",
               "fab.grow_mem_eligible", "fab.shift_notifications",
               "fab.growth_blackout_suppressed.regression",
               "fab.growth_blackout_suppressed.stall",
               "fab.grow_regression_refused_cooldown", "fab.grow_stall_refused_cooldown",
               "fab.grow_recover_passes", "fab.grow_warmup_refused",
               "fab.newfrac_spent_on_spawn"):
        counters.setdefault(_k, 0)
    _bump(counters, "fab.grow_checks")
    counters["fab.cap_lift_period"] = int(lift_period)

    # THE CEILING IS READ ON EVERY CHECK AND NOT ONLY WHEN SOMETHING ASKS, and the first driven run
    # of this body is why. With the call inside the `if ask:` block a root that had wired
    # `soft_cap=caps.experts` -- the spelling spine/compose.py's CAP.caps row uses -- ran green for
    # the whole warm-up and raised on the FIRST REGRESSION, hundreds of windows in, which is both
    # the least convenient moment and the one where the run has the most to lose. TWO CEILINGS, TWO
    # KINDS: `room` is CAP's operating valve, reached through Caps.headroom because the subtraction
    # is C30; `pool_room` is the hard PREALLOCATION pop.cap (= max(n0, slots)), and its max(0, ...)
    # is not a repeat of that repair -- n_live can reach cap and never pass it.
    n_live = int(pop.n_live)
    room = _headroom(soft_cap, n_live, where)
    pool_room = max(0, int(pop.cap) - n_live)

    g = pop.growth

    # ---- the blackout: a shift WE caused is not new material (Q-FAB-6) --------------------------
    # THE ROOT SUPPLIES THE STAMP AND THIS PACKAGE APPLIES ITS OWN `cooldown`. A boolean argument
    # would have forced the caller to apply a FAB lever at a foreign call site, which `grep -rn d_`
    # could never index; the threshold stays in the package that declares it, which is the same rule
    # fabric/api.py::manage_period exists to enforce one accessor over.
    # U.Windows() IS THE TYPE CHECK AND NOT A CAST: OPT.maybe_step takes the SAME event stamped into
    # units.Steps off clock.opt_steps, and handing that object here raises UnitError instead of
    # being batch_windows-fold wrong -- 16x at BATCH_W=16, and exactly right at 1, which is the
    # shape of every clock defect this project has recorded.
    blackout_open, blackout_left = False, 0
    if shift_at is not None:
        stamp = U.Windows(shift_at)
        _bump(counters, "fab.shift_notifications")
        since_shift = int(step - stamp)
        if since_shift < cool_n:
            blackout_open, blackout_left = True, cool_n - since_shift

    # ---- the other door's births, charged against this door's budget ----------------------------
    # SPAWN WRITES INTO THE POOL INSIDE `forward`, BEFORE THIS ENTRY POINT SEES THE FLUSH, so it
    # cannot be refused here -- but it spends the same slots, and a newborn budget that ignored it
    # would let the two doors deliver more newborns than either admits. Recorded at THIS window
    # rather than at the window it happened, which is the honest approximation: the count is exact
    # and the timestamp is one flush late at worst. parent=-1 keeps them out of fab.distinct_parents,
    # which is a reading about REPLICATION lineage.
    if spawn_on:
        _seen = int(counters.get("fab.spawned", 0))
        _new = max(0, _seen - int(g.get("spawned_seen", 0)))
        if _new:
            g["births"].extend((step_n, -1) for _ in range(_new))
            _bump(counters, "fab.newfrac_spent_on_spawn", _new)
        g["spawned_seen"] = _seen
    # THE RECORD IS TWO WINDOWS AT ONCE AND IS TRIMMED TO THE LONGER OF THEM: new_frac counts births
    # in the last `cooldown` WINDOWS and parent_max counts them over the last `birth_win` BIRTHS, so
    # dropping on either alone would silently shorten the other.
    _keep_from = len(g["births"]) - birth_win
    g["births"] = [b for i, b in enumerate(g["births"])
                   if i >= _keep_from or (step_n - int(b[0])) < cool_n]

    loss = _loss_float(flush_loss, where)
    mem_eligible = bool(mem_on and memory_pressure)
    if mem_eligible:
        _bump(counters, "fab.grow_mem_eligible")

    asked_r = asked_s = 0
    improving = unexpected = None
    if grow_on:
        # ---- WATCH: the three EMAs, then the two triggers ---------------------------------------
        g["n"] = int(g["n"]) + 1
        g["fast"] = loss if g["fast"] is None else \
            (1.0 - _FAST_EMA) * float(g["fast"]) + _FAST_EMA * loss
        g["slow"] = loss if g["slow"] is None else \
            (1.0 - _SLOW_EMA) * float(g["slow"]) + _SLOW_EMA * loss
        _d = abs(loss - float(g["slow"]))
        g["dev"] = _d if g["n"] == 1 else (1.0 - _MAD_EMA) * float(g["dev"]) + _MAD_EMA * _d
        improving = (float(g["slow"]) - float(g["fast"])) / max(1e-6, abs(float(g["slow"])))
        # A RUNNING MAD AND NOT A FIXED THRESHOLD, which is what makes `z` scale-free: a loss of 8.3
        # at the start of a run and 2.1 at the end are the same distance from their own slow EMA in
        # deviations, and a threshold fitted to one loss level is a threshold that stops detecting
        # anything once the run has improved.
        _thresh = z_dev * max(1e-6, float(g["dev"]))
        unexpected = (loss - float(g["slow"])) > _thresh

        # A REGRESSION IS TESTED FIRST AND ON ITS OWN CLOCK. It preempts RECOVER deliberately:
        # RECOVER exists so a burst's own transient cannot re-trigger growth, which is not evidence
        # about new material, and a genuine regression must be able to interrupt it. What is NOT
        # relaxed is the blackout -- a loss jump WE caused (a retok, a resample, an LR restart) is
        # the system reacting to itself.
        if unexpected:
            if blackout_open:
                _bump(counters, "fab.growth_blackout_suppressed.regression")
            elif g["last_regr"] is not None and (step_n - int(g["last_regr"])) < cool_n:
                # DETECTED AND REFUSED BY ITS OWN SPACING -- counted, never silent. The old tree
                # refused it by the SHARED clock instead, so a routine stall 772 windows earlier
                # suppressed an injected regression (:2921-2926) and the counter that would have
                # said so did not exist on that path.
                _bump(counters, "fab.grow_regression_refused_cooldown")
            else:
                asked_r = burst
                g["last"] = g["last_regr"] = g["t0"] = step_n
                g["state"] = "R"

        if not asked_r:
            if g["state"] == "R":
                # ---- RECOVER: wait for the improvement to FLATTEN, or for the hard ceiling ------
                # THE EXIT TEST IS TWO-SIDED FOR THE SAME REASON THE STALL TEST IS, and this is a
                # judgement this body takes rather than inherits. The old form is `improving < s.rel`
                # (:3010), which every negative value satisfies -- so a DIVERGING run leaves RECOVER
                # at the first opportunity and is then free to grow on the next stall check, which
                # is capacity added in answer to divergence (M36) arriving through the other door.
                # |improving| < plateau is "improvement has flattened", which is what the leg's own
                # description says it waits for; the price is that a run still improving fast stays
                # in RECOVER until recover_max, and recover_max is precisely the escape hatch
                # fabric/levers.py declares for that case ("growth re-arms even if improvement never
                # flattens"). The alternative -- keeping the one-sided form -- was rejected because
                # it makes the lockout shortest exactly when the run is worst.
                _since_t0 = step_n - int(g["t0"] if g["t0"] is not None else step_n)
                if _since_t0 >= rec_min and (abs(improving) < plateau or _since_t0 > rec_max):
                    g["state"] = "W"
                _bump(counters, "fab.grow_recover_passes")
            elif blackout_open:
                _bump(counters, "fab.growth_blackout_suppressed.stall")
            elif g["last"] is not None and (step_n - int(g["last"])) < cool_n:
                _bump(counters, "fab.grow_stall_refused_cooldown")
            elif step_n < warm_n:
                # EARLY NOISE IS NOT A PLATEAU. Memory pressure does not bypass this: an occupancy
                # reading taken while the run is still finding its scale is not evidence about
                # capacity either, and bypassing the one gate that exists to stop early noise from
                # growing the population would be the ramp's defect arriving through MEM.
                _bump(counters, "fab.grow_warmup_refused")
            elif abs(improving) < plateau or mem_eligible:
                # THE STALL TEST IS TWO-SIDED (M36). `improving < plateau` is satisfied by every
                # negative value there is, so a diverging run satisfied the stall condition and grew
                # an expert -- capacity added in answer to divergence. `mem_eligible` stands in for
                # the plateau reading and not for the gates above it: it is MEM's VERDICT (Q-MEM-4),
                # already compared against MEM's own pressure_thresh inside MEM.census, and this
                # function reads no threshold of MEM's.
                asked_s = 1
                g["last"] = g["t0"] = step_n
                g["state"] = "R"

    # ---- BURST: the clamps run INSIDE, before the counter (:7444-7470) --------------------------
    ask = asked_r + asked_s
    grown_r = grown_s = declined_cap = declined_new = 0
    replicated = crossed = random_born = quota_refusals = 0
    n_born = 0
    if ask:
        _bump(counters, "fab.grow_asked_regression", asked_r)
        _bump(counters, "fab.grow_asked_stall", asked_s)
        allow = min(room, pool_room)
        n_born = min(ask, allow)
        declined_cap = ask - n_born
        # THE NEWBORN BUDGET, OVER THE COOLDOWN WINDOW AND INCLUDING THE OTHER DOOR'S BIRTHS.
        # max(1, ...) exists because int(0.04 * 3) is 0 and a small founding population could
        # otherwise never grow at all (measured in the old tree: reached 7 instead of 256).
        recent = sum(1 for _w, _p in g["births"] if (step_n - int(_w)) < cool_n)
        budget = max(0, max(1, int(new_frac * n_live)) - recent)
        if budget < n_born:
            declined_new = n_born - budget
            n_born = budget
        if n_born:
            # THE GENERATOR IS SEEDED OFF THIS PACKAGE'S OWN STREAM, EXACTLY AS `build` DOES IT --
            # and NOT `pop.rng.torch_generator(...)`, which derives its seed from the subsystem NAME
            # and therefore hands back the same stream on every call: every birth in every burst of
            # the whole run would take bit-identical mutation noise, and a population of clones
            # would be reported as a population of mutants.
            gen = torch.Generator(device=pop.A.device)
            gen.manual_seed(pop.rng.randint(0, 2 ** 31 - 1))
            point = _signature_point(signature, pop.cent, where)
            # THE RELEVANCE SHORTLIST: the parent_k region owners nearest the signature that
            # triggered the growth, so a birth lands near the material that asked for it. At k=1
            # growth is greedy cloning of the incumbent and at k=population it is unfocused.
            with torch.no_grad():
                _cos = F.normalize(pop.cent[:n_live].float(), dim=-1) @ point
                shortlist = _cos.topk(max(1, min(parent_k, n_live))).indices.tolist()
            for _ in range(n_born):
                slot = int(pop.n_live)
                parent, other, take, scale = -1, None, (), 1.0
                if replicate:
                    cands = [int(c) for c in shortlist if int(c) < int(pop.n_live)]
                    while cands:
                        pick = _fitness_pick(pop.rng, cands, pop.use)
                        # THE QUOTA IS A SHARE OF THE WINDOW, NOT OF WHAT THE WINDOW HAPPENS TO
                        # HOLD. parent_max x birth_win is 51 of the last 256 births at the shipped
                        # defaults; measuring the share against len(record) instead would refuse
                        # EVERY parent while the record is empty (0 held is not less than 0.2 x 0),
                        # so the first birth of every run would be random and the `replicate` arm
                        # would never be exercised at the one moment it is cheapest to check.
                        # AT parent_max=0.0 NOTHING CAN EVER BE A PARENT and every birth is fresh:
                        # that is the tightest quota the mechanism can state, fabric/levers.py
                        # admits it deliberately and leaves what it does to this body, and this is
                        # what it does -- a legible arm, not an accident.
                        held = sum(1 for _w, p in g["births"][-birth_win:] if p == pick)
                        if held < parent_max * birth_win:
                            parent = pick
                            break
                        cands.remove(pick)
                        quota_refusals += 1
                if parent >= 0:
                    scale = mut
                    if mut_big_p > 0.0 and pop.rng.random() < mut_big_p:
                        # THE HEAVY TAIL: rate and magnitude are separate levers because they trade
                        # off against each other, and one knob carrying both would make "more
                        # exploration" ambiguous.
                        scale = mut * mut_big
                    if xover > 0.0 and len(cands) > 1 and pop.rng.random() < xover:
                        other = _fitness_pick(pop.rng, [c for c in cands if c != parent], pop.use)
                        take = [j for j in range(int(pop.A.shape[2])) if pop.rng.random() < 0.5]
                        if take:
                            crossed += 1
                        else:
                            other = None
                    _birth_write(pop, slot, gen, src=parent, other=other, scale=scale,
                                 point=point, jitter=jitter, rank_take=take)
                    replicated += 1
                else:
                    # A FRESH IDENTITY. This is the counterfactual the inheritance claim needs:
                    # `replicate` says a new expert starts from something already learned, and a
                    # random birth is the only arm that tests it. It is also where a birth lands
                    # when every shortlisted parent is over its quota -- refusing the birth outright
                    # would file a delivered trigger as an undelivered one and would need a third
                    # decline reason no counter names.
                    _birth_write(pop, slot, gen, src=None, point=point, jitter=jitter)
                    random_born += 1
                _claim_slot(pop, slot, step_n, parent=parent, mutscale=scale)
                g["births"].append((step_n, parent))
        # ONE LEG PER CHECK BY CONSTRUCTION: the stall arm is inside `if not asked_r`, so the ask
        # this delivery belongs to is never ambiguous and the two deliveries never double-count.
        if asked_r:
            grown_r = n_born
        else:
            grown_s = n_born
        _bump(counters, "fab.grown_regression", grown_r)
        _bump(counters, "fab.grown_stall", grown_s)
        _bump(counters, "fab.declined_cap", declined_cap)
        _bump(counters, "fab.declined_newfrac", declined_new)
        _bump(counters, "fab.replicated", replicated)
        _bump(counters, "fab.crossed", crossed)
        _bump(counters, "fab.random_born", random_born)
        _bump(counters, "fab.parent_quota_refusals", quota_refusals)

    # THE LINEAGE READING IS ABOUT THE LIVE POPULATION AND NOT ABOUT THE BIRTH RECORD, because D7's
    # question is "is this population one lineage wearing n hats", which is a property of who is
    # alive now. `parent` is renumbered by the one declared list in remove() (state_dict's note on
    # L28), so it survives the cull that the birth record would not.
    _live = int(pop.n_live)
    counters["fab.distinct_parents"] = len({int(p) for p in pop.parent[:_live] if int(p) >= 0})
    if grow_on:
        counters["fab.grow_slow"] = round(float(g["slow"]), 6)
        counters["fab.grow_fast"] = round(float(g["fast"]), 6)
        counters["fab.grow_dev"] = round(float(g["dev"]), 6)
        counters["fab.grow_improving"] = round(float(improving), 6)

    gates = (
        Gate("fab.growth", n_born > 0,
             value=f"{ask} asked, {n_born} grown, n_live={_live}",
             threshold=f"soft cap headroom + new_frac={new_frac} of {_live} (FAB_N0={n0}, "
                       f"FAB_SLOTS={slots})",
             reachable=grow_on,
             reason="" if grow_on else
                    f"FAB_GROW={grow_on}: the population is frozen at FAB_N0={n0}. Neither leg is "
                    f"evaluated -- the EMAs this trigger is made of are not even advanced -- so "
                    f"every growth counter on this ledger is unreachable rather than zero."),
        Gate("fab.growth_regression", asked_r > 0,
             value=("not evaluated" if not grow_on else
                    f"loss-slow={loss - float(g['slow']):.6f}"),
             threshold=("not evaluated" if not grow_on else
                        f"z={z_dev} x dev={float(g['dev']):.6f}"),
             reachable=grow_on,
             reason=("" if grow_on else
                     f"FAB_GROW={grow_on}: the regression trigger -- the only signal continual "
                     f"learning has that new material has arrived -- is not evaluated.")),
        Gate("fab.growth_blackout", blackout_open,
             value=(f"{blackout_left} window(s) left" if blackout_open else
                    f"{int(counters['fab.shift_notifications'])} notification(s)"),
             threshold=f"cooldown={cool_n} windows",
             reachable=int(counters["fab.shift_notifications"]) > 0,
             reason="" if int(counters["fab.shift_notifications"]) > 0 else
                    "NOBODY IS SUPPLYING shift_at: it is a defaulted keyword, which is invisible to "
                    "K10, and 0 notifications means the blackout cannot open at all -- not that it "
                    "was armed and no shift happened. The three sites that would stamp it are the "
                    "epoch resample, TOK.mint_burst's retok and OPT's LR restart."),
        Gate("fab.grow_mem_pressure", mem_eligible,
             value=f"FAB_GROW_ON_MEM_PRESSURE={mem_on}, memory_pressure={memory_pressure!r}",
             threshold="MEM's own verdict, already compared against MEM_PRESSURE_THRESH",
             reachable=bool(mem_on and memory_pressure is not None),
             reason="" if (mem_on and memory_pressure is not None) else
                    (f"FAB_GROW_ON_MEM_PRESSURE={mem_on}: the memory-pressure signal is printed and "
                     f"does not make growth eligible."
                     if not mem_on else
                     "memory_pressure is None: MEM.census is a P4 stub, so no verdict is produced "
                     "at all. Even with a body it would be exactly 0.0 for every configuration "
                     "until MEM.maintain's probe has contexts -- nothing promotes out of probation, "
                     "so every eviction takes the probation branch (Q-MEM-4). TWO named causes, "
                     "not one.")),
        Gate("fab.grow_cap", declined_cap > 0,
             value=f"{declined_cap} of {ask} refused by the ceiling",
             threshold=f"Caps.headroom({n_live})={room}, pool {pool_room} of {int(pop.cap)}",
             reachable=grow_on,
             reason="" if grow_on else
                    f"FAB_GROW={grow_on}: nothing asks, so no ask can be refused."),
    )
    return GrowReport(
        asked_regression=asked_r, asked_stall=asked_s,
        grown_regression=grown_r, grown_stall=grown_s,
        declined_cap=declined_cap, declined_newfrac=declined_new,
        replicated=replicated, crossed=crossed, random_born=random_born,
        parent_quota_refusals=quota_refusals,
        distinct_parents=int(counters["fab.distinct_parents"]),
        blackout_open=blackout_open, blackout_left=blackout_left, gates=gates)


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

    LEVERS READ: on, lr_own, lr_cycle, lr_gamma, lr_amin, lr_maxr, lr_boost, cull_frac, grace
    WIRES READ: d_base_lr, d_lr_min_frac
    DID IT FIRE: fab.lr_scaled_experts, fab.lr_boosted, fab.lr_cycle_max (a max above ~12 means
                 every survivor is pinned at lr_amin and the schedule is a constant)
    FIVE MORE KEYS THE BODY WRITES, DECLARED HERE FOR fabric/api.py::forward's reason (a key in the
    report the contract does not admit to producing is the same defect as a declared key nothing
    writes):
      fab.lr_calls -- how many times this was CALLED, so "no expert was scaled" is distinguishable
        from "spine/loop.py never invoked it", which is the state of the tree today.
      fab.lr_eligible -- the size of the PAST-GRACE set the boost budget is sized on. fab.lr_boosted
        reading 0 has two causes -- nobody is in trouble, and nobody is eligible to be -- and at the
        shipped defaults it is the second: Q-FAB-5's arithmetic puts mean uage at 1.98 against
        grace=48, so this number is 0 and the boost is UNREACHABLE rather than armed. One counter
        cannot say which.
      fab.lr_envelope_pinned -- how many live experts sit at the lr_amin floor. The docstring's
        "a max above ~12 means every survivor is pinned" is a rule of thumb about fab.lr_cycle_max;
        this is the reading itself, and it is what the old tree's warning (:7305-7315) was about.
      fab.lr_ratio_clamped -- experts whose own rate hit the lr_maxr ceiling. All of them clamped is
        the one-moment state the old tree's diagnostic reported when it fired at step 3 and looked
        like a broken mechanism (x4.00..x4.00) rather than a badly timed print.
      fab.lr_zero_applied -- calls where `applied_lr` was not positive. The ratio to a zero rate is
        not a number; the denominator is floored at fabric/api.py::_FLOOR, which is declared "only
        ever a denominator guard, never a rate", and this counter is what stops that floor from
        being read as a measurement.
    """
    fab = fab.owned_by("FAB")
    base_lr, lr_min_frac = fab.d_base_lr, fab.d_lr_min_frac   # WIRES READ HERE -- the two endpoints
    counters = pop.counters
    # FAB_ON=0 RETURNS FIRST, WITH THE WHOLE fab.lr_* FAMILY ABSENT (Q-FAB-11): no expert is in the
    # optimizer on that arm (Population.parameters is empty), so there is no rate to scale and the
    # build gate fab.lr_own reads UNREACHABLE. The seeding below is for FAB_LR_OWN=False, which is
    # an ARMED arm that chose not to scale.
    if not bool(fab.on):
        return None
    _bump(counters, "fab.lr_calls")
    # SEEDED BEFORE THE OFF RETURN, for the reason fabric/api.py::observe seeds its family there:
    # at the shipped FAB_LR_OWN=False every call takes that return, and a reader asking the ledger
    # how many experts were scaled must get 0 and not a KeyError -- which is what the first driven
    # run of grow_check's RECOVER counter produced before it was seeded.
    for _k in ("fab.lr_scaled_experts", "fab.lr_boosted", "fab.lr_cycle_max", "fab.lr_eligible",
               "fab.lr_envelope_pinned", "fab.lr_ratio_clamped", "fab.lr_zero_applied"):
        counters.setdefault(_k, 0)
    # None AND NOT A TABLE OF ONES, which is the same distinction the build-time fab.lr_own gate
    # prints: a table of ones is a schedule that ran and chose 1.0 for every expert, and this arm
    # did not run at all. A caller that multiplied by it would be applying a mechanism that is off.
    if not bool(fab.lr_own):
        return None
    n = int(pop.n_live)
    if n <= 0:
        return None

    # THE CLOCK IS `uage` AND NOT `use`, AND SINCE THE SPLIT THAT IS FORCED RATHER THAN CHOSEN.
    # fabric/levers.py declares lr_cycle in units.Selections; fabric/api.py::observe credits `use`
    # by ROUTING MASS (a float that is not a count of anything) and `uage` by SELECTION, so `use` is
    # no longer a Selections quantity at all. The old tree read `fab.use_age(i)` (:7217) when the
    # two were one number, and the lever's own sentence -- "clocked from its own use count" -- is
    # from that era. Reading `use` here would compare a mass against a half-cycle declared in
    # selections, which is the cross-kind comparison spine/units.py exists to make impossible for
    # clocks and can only be prevented by argument inside one package.
    half = max(1.0, float(fab.lr_cycle))
    gamma, amin = float(fab.lr_gamma), float(fab.lr_amin)
    maxr, boost = float(fab.lr_maxr), float(fab.lr_boost)
    cull_frac, grace = float(fab.cull_frac), int(fab.grace)
    # THE ENVELOPE IS BUILT FROM THE PEAK AND ITS FLOOR, WHICH ARE BOTH WIRES: :7251 is
    # `_lo = LR * LR_MIN_FRAC` and :7252 blends from it. The RATIO is against what the optimizer is
    # ABOUT to apply, which is live and arrives as the argument -- so there is no configuration in
    # which this function reads an undefined global, which ISSUES P1-H15 (a NameError on `_lrv`
    # whenever LR_SCHED=none and lr_own=1) is the record of.
    peak = float(base_lr)
    lo = peak * float(lr_min_frac)
    applied = float(applied_lr)
    if not (applied > 0.0):
        _bump(counters, "fab.lr_zero_applied")

    own, cyc_max, pinned = [], 0.0, 0
    for i in range(n):
        # +half SO A NEWBORN STARTS AT THE PEAK AND NOT IN THE TROUGH (:7217-7219): at t == half the
        # triangle is exactly at its maximum, which is the phase a fresh expert should enter on.
        # The 1e6 ceiling is the old tree's own, and it is a guard against an expert whose selection
        # count has run away rather than a schedule decision.
        t = min(float(pop.uage[i]), 1e6) + half
        cycle = math.floor(1.0 + t / (2.0 * half))
        x = abs(t / half - 2.0 * cycle + 1.0)
        # THE ENVELOPE HAS A FLOOR AND IT NEEDS ONE. gamma**(cycle-1) goes to zero and the use clock
        # has no horizon, so a heavily-selected expert burns cycles fast and is then pinned at the
        # floor for the rest of the run, unable to respond to a distribution shift no matter how
        # badly it is doing -- which is the "aged out and cannot learn" state an evolutionary design
        # may tolerate in an individual but must not impose on every survivor by construction.
        env = gamma ** (cycle - 1.0)
        if env <= amin:
            env, pinned = amin, pinned + 1
        own.append(lo + (peak - lo) * max(0.0, 1.0 - x) * env)
        cyc_max = max(cyc_max, cycle)

    # ---- the boost: the bottom of the SAME ranking the cull uses --------------------------------
    # AN EXPERT IN THE CULL-ELIGIBLE FRACTION IS ALREADY FAILING, and annealing it on the same curve
    # as a thriving one spends its remaining life confirming that. The budget is sized on the
    # ELIGIBLE count and not on n_live: at 523 live / 84 eligible, `cull_frac * n_live` is 10 over a
    # list of 84 and "the worst 2%" meant "all of them" (:7273-7281). `grace` is the same clock the
    # cull tests, so "has had its chances" means one thing in both places.
    eligible = [i for i in range(n) if int(pop.uage[i]) >= grace]
    counters["fab.lr_eligible"] = len(eligible)
    boosted = 0
    if boost > 1.0 and n > 2 and eligible:
        rank = sorted(eligible, key=lambda i: float(pop.use[i]))
        nb = max(1, int(cull_frac * len(eligible)))
        for i in rank[:nb]:
            own[i] = own[i] * boost
            boosted += 1

    denom = applied if applied > 0.0 else _FLOOR
    ratios = [min(o / denom, maxr) for o in own]
    counters["fab.lr_scaled_experts"] = n
    counters["fab.lr_boosted"] = boosted
    counters["fab.lr_cycle_max"] = int(cyc_max)
    counters["fab.lr_envelope_pinned"] = pinned
    counters["fab.lr_ratio_clamped"] = sum(1 for o in own if o / denom > maxr)
    # A TENSOR ON THE POPULATION'S OWN DEVICE AND DTYPE, because the one use this multiplier has
    # ever had is `A[:n] = prev + r.view(-1, 1, 1) * (A[:n] - prev)` (:7291-7293) -- a per-row
    # rescale of the two adapter banks. Returning a Python list would move the arithmetic to the
    # caller and, on a GPU run, put a host-to-device copy inside the optimizer step. THE CONTRACT
    # ALREADY RECORDS THAT NOTHING TAKES IT: compose.py's row for this entry point is a four-element
    # row -- "IT PRODUCES NOTHING ANY SIGNATURE ACCEPTS" -- so fab.lr_scaled_experts counts an
    # effect nothing in this tree applies, and that is the statement, not a defect in this body.
    return torch.tensor(ratios, device=pop.A.device, dtype=pop.A.dtype)



def _three_state(gates, ledger):
    """{name: (state, count, arithmetic)} for every DECLARED gate, in G4's three states.

    RENDERED FROM THE Gate OBJECTS THE PACKAGE ALREADY CARRIES, never from a second inspection of
    the levers. spine/gate.py::Gate is where `fired`, `reachable`, `value`, `threshold` and
    `reason` were decided, at build, with the numbers that made them true or false; recomputing any
    of that here would give this package two answers to "did it fire" and let the report quote
    whichever it reached first. That is the defect the Gate record was introduced to end.

    THE THIRD STATE IS THE ONE THAT COSTS, which is Gate's own sentence. `fired=False,
    reachable=True` is a MEASUREMENT -- the mechanism ran and its condition was not met.
    `reachable=False` is not a measurement at all, and a report that prints them the same way says
    "0" for both. The count comes from the ledger when the ledger has a key of that name, so a
    gate that fired N times says N rather than merely "fired".
    """
    # BOTH CONTAINERS, BECAUSE THE TREE USES BOTH. SIG carries `gates` as a dict {name: Gate}
    # while FAB, MEM and CAP carry a tuple of Gate. Neither is wrong and this is not the place to
    # unify them -- a renderer that accepted only one would silently report zero gates for the
    # packages using the other, which is the "0 fires nobody can read" state in the very function
    # written to prevent it. Measured 2026-09-15: sig.gates is a dict of 2, fabric.gates a tuple
    # of 2, store.gates a tuple of 1, valve.gates a tuple of 3.
    if isinstance(gates, dict):
        gates = tuple(gates.values())
    out = {}
    for g in (gates or ()):
        n = int(ledger.get(g.name, ledger.get(g.name + ".count", 0)) or 0)
        arith = f"{g.value!r} vs {g.threshold!r}"
        if not g.reachable:
            out[g.name] = ("unreachable", n, f"{arith} -- {g.reason}")
        elif g.fired:
            out[g.name] = ("fired", n, arith)
        else:
            # ARMED AND IT DID NOT HAPPEN. The reason rides along when the gate carried one,
            # because "armed but 0" with the arithmetic beside it is what lets a reader tell a
            # threshold that was nearly met from one that was never approached.
            out[g.name] = ("armed-but-zero", n, arith + (f" -- {g.reason}" if g.reason else ""))
    return out


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
    # EVERY GATE HERE IS A DECLARED Gate OBJECT AND NEVER AN INLINE PREDICATE, so an unreachable
    # row prints its own numbers -- "unreachable (fabric.cull: 1838/4096 = 0.449 < 0.45)" is the
    # shape, and it comes from the Gate the build already made rather than from a second reading
    # of the levers here.
    out = dict(pop.counters)
    out.update({f"gate:{k}": v for k, v in
                _three_state(getattr(pop, "gates", ()), pop.counters).items()})
    # AND THE LAST TRAINING PASS'S GATES, which FabricOut.gates carried and nothing printed until
    # 2026-09-24 -- including the three that said "no head was supplied" on every pass of every run.
    # They are PER-PASS arithmetic (the build's are per-run), so the count beside each verdict is
    # the cumulative ledger key of the same name where one exists and the verdict is the last pass's.
    # No name collides with a build gate: fab.on / cull_gate / growth_armed / lr_own are build-only.
    out.update({f"gate:{k}": v for k, v in
                _three_state(getattr(pop, "pass_gates", ()), pop.counters).items()})
    # THE LIVE POPULATION AND ITS CEILING, because every fabric gate's arithmetic is a ratio
    # against one of them and a reader with the verdict but not the denominator has a claim.
    out["fab.n_live"] = int(pop.n_live)
    out["fab.cap"] = int(pop.cap)
    out["fab.births"] = int(pop.births)
    out["fab.rescued"] = int(pop.rescued)
    return out


def state_dict(fab: Config, pop):
    """Parameters (A, B, q_route, hproj, eemb, edec, halt_key, halt_b, norm, nov_proj), the `cent`
    BUFFER, every book, the growth machine and comp_glob, the cumulative counter ledger, and the
    package RNG stream.

    THE GROWTH MACHINE AND comp_glob JOINED THIS LIST ON 2026-09-17, in the same edit that gave
    Population a slot for them and fabric/api.py::grow_check and ::observe bodies that write them.
    They are saved for the reason the lifted cap is (capacity/api.py::new_valve): they are earned
    state, not configuration, and a resume that rebuilt them would re-arm growth inside a lockout
    the checkpointed run was still serving. The payload key is checked by load_state_dict below and
    UPDATES the built default rather than replacing it, so an older checkpoint restores.

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

    Re-earned rather than restored: the identity cache, halt_ema, the routing-mix samples, and
    `learn_window` -- the window index of the last gradient-carrying training pass, which is a
    statement about THIS PROCESS's clock and would only ever produce a false refusal if a
    resume restored it -- and `pass_gates`, the last training pass's gate arithmetic, which the
    resumed run's first pass rewrites.

    LEVERS READ: none
    WIRES READ: none
    DID IT FIRE: fab.state_written
    """
    fab = fab.owned_by("FAB")
    def _t(x):
        return None if x is None else x.detach().cpu().clone()
    out = {
        # THE PARAMETERS. A and B are the expert tensors; halt_b is the halting bias; everything
        # else with parameters lives in `modules`, which build allocates and which carries eemb,
        # edec, q_route, hproj, halt_key, norm and nov_proj under its own names. Going through the
        # ModuleDict rather than listing them here is what keeps this save side from naming a
        # tensor nothing allocates -- the `ctrl` defect this docstring records, where the contract
        # promised to checkpoint a parameter build never created and only a resume could falsify it.
        "A": _t(pop.A), "B": _t(pop.B), "halt_b": _t(pop.halt_b),
        "modules": pop.modules.state_dict(),
        # THE `cent` BUFFER. Not a parameter and not derivable: it is where each expert sits in
        # signature space, and a resume that rebuilt it would route every window differently.
        "cent": _t(pop.cent),
        # EVERY BOOK. These are plain Python lists and one list of sets; they carry which expert was
        # born when, how used it is, which domains it serves, and the per-expert EMAs. dom_of holds
        # sets, which torch.save handles but which are listified here so the payload is inspectable
        # without unpickling behaviour.
        "books": {
            "born": list(pop.born), "use": list(pop.use), "uage": list(pop.uage),
            "dom_of": [sorted(d) for d in pop.dom_of],
            "ef": list(pop.ef), "es": list(pop.es), "comp": list(pop.comp),
            "contrib": list(pop.contrib), "parent": list(pop.parent),
            "mutscale": list(pop.mutscale),
        },
        # THE GROWTH MACHINE AND THE POPULATION COMPETENCE EMA, SAVED AND NOT RE-EARNED. Both are
        # EARNED STATE in the sense capacity/api.py::new_valve gives the phrase for its lifted cap:
        # they are what the run has learned about its own loss, and rebuilding them on a resume
        # would hand the successor a machine with no cooldown clock, no RECOVER leg and no MAD --
        # so the first flush after a restart can fire a growth burst that the run it resumed was
        # still in lockout for, and the report would show a regression the loss never made. The
        # values are plain floats/ints/None/str plus a list of (window, parent) pairs, which is why
        # the field could be a dict rather than a record type (Population.__init__ says so).
        "growth": {k: (list(v) if isinstance(v, list) else v) for k, v in pop.growth.items()},
        "comp_glob": pop.comp_glob,
        "n_live": int(pop.n_live), "cap": int(pop.cap), "depth_now": int(pop.depth_now),
        "births": int(pop.births), "rescued": int(pop.rescued),
        "halt_ema": getattr(pop, "halt_ema", None), "learn_window": pop.learn_window,
        "counters": dict(pop.counters),
        "rng": (pop.rng._r.getstate(), int(pop.rng._draws)) if getattr(pop, "rng", None) else None,
        # THE SIDECAR load_state_dict REFUSES AGAINST. Three widths produced one error message in
        # the old tree (:4678-4684) -- "it can be failing on FAB_EMB_HID, SIG_D or D_MODEL and no
        # prefix of it means anything" -- so each is carried separately and refused by name.
        "sidecar": {
            "slots": int(pop.cap), "rank": int(pop.A.shape[2]), "dk": int(pop.A.shape[1]),
            "signature_dim": int(pop.cent.shape[1]),
        },
    }
    pop.counters["fab.state_written"] = pop.counters.get("fab.state_written", 0) + 1
    return out


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

    def _refuse(reason):
        pop.counters["fab.resume_refused"] = pop.counters.get("fab.resume_refused", 0) + 1
        raise LeverError(reason)

    if not sd:
        return pop
    live = {"slots": int(pop.cap), "rank": int(pop.A.shape[2]), "dk": int(pop.A.shape[1]),
            "signature_dim": int(pop.cent.shape[1])}
    was = dict(sidecar or {})
    # rank AND dk ARE INNER DIMENSIONS AND CANNOT BE PREFIX-WIDENED. A prefix widen adds ROWS; these
    # two change what each row MEANS, so an expert restored across a change of either is a tensor of
    # the right shape holding a different decomposition. signature_dim is the same argument one
    # package over: the centroids were measured in a space of that width.
    for field in ("rank", "dk", "signature_dim"):
        if field in was and int(was[field]) != live[field]:
            _refuse(f"FAB resume refused on {field}: the checkpoint was written at {was[field]} "
                    f"and this run resolves {live[field]}. This is an INNER dimension -- it changes "
                    f"what every row means, not how many there are, so it cannot be prefix-widened "
                    f"and a same-shaped restore would be a different decomposition wearing the "
                    f"right shape.")
    saved_slots = int(was.get("slots", live["slots"]))
    if saved_slots > live["slots"]:
        # SLOTS MAY WIDEN BUT NEVER NARROW. Narrowing would drop trained experts whose indices the
        # books, the centroids and every dom_of set still refer to.
        _refuse(f"FAB_SLOTS: the checkpoint holds {saved_slots} slots and this run allocates "
                f"{live['slots']}. Widening is supported and narrowing is not -- the books, the "
                f"centroids and every dom_of entry index these slots by position.")

    widened = 0
    with torch.no_grad():
        for field in ("A", "B", "cent"):
            got = sd.get(field)
            if got is None:
                continue
            want = getattr(pop, field)
            got = got.to(want.device)
            if tuple(got.shape) == tuple(want.shape):
                want.copy_(got)
            else:
                # THE PREFIX. Slot i stays slot i, and everything above the saved count keeps the
                # initialisation build gave it.
                want[:got.shape[0]].copy_(got)
                widened += 1
        if sd.get("halt_b") is not None:
            pop.halt_b.copy_(sd["halt_b"].to(pop.halt_b.device))
    if sd.get("modules") is not None:
        pop.modules.load_state_dict(sd["modules"])

    books = sd.get("books") or {}
    for name in ("born", "use", "uage", "ef", "es", "comp", "contrib", "parent", "mutscale"):
        if books.get(name) is not None:
            cur = getattr(pop, name)
            cur[:len(books[name])] = list(books[name])
    if books.get("dom_of") is not None:
        for i, ids in enumerate(books["dom_of"]):
            pop.dom_of[i] = set(ids)
    for field in ("n_live", "depth_now", "births", "rescued"):
        if sd.get(field) is not None:
            setattr(pop, field, int(sd[field]))
    if sd.get("growth"):
        # UPDATE, NOT REPLACE, so a checkpoint written before a key existed restores what it has and
        # keeps this build's default for what it does not -- the alternative is a Population whose
        # growth dict is missing a key that every branch of grow_check reads, i.e. a KeyError on the
        # first flush after a resume from an older payload.
        pop.growth.update(sd["growth"])
        pop.growth["births"] = [tuple(b) for b in (pop.growth.get("births") or ())]
    if "comp_glob" in sd:
        pop.comp_glob = sd["comp_glob"]
    if "halt_ema" in sd:
        pop.halt_ema = sd["halt_ema"]
    if "learn_window" in sd:
        pop.learn_window = sd["learn_window"]
    if sd.get("counters"):
        pop.counters.update(sd["counters"])
    if sd.get("rng") and getattr(pop, "rng", None) is not None:
        state, draws = sd["rng"]
        pop.rng._r.setstate(state)
        pop.rng._draws = int(draws)
    pop.counters["fab.resume_widened"] = pop.counters.get("fab.resume_widened", 0) + widened
    return pop


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
    every = int(fab.manage_every)
    # A NEGATIVE MANAGEMENT CADENCE IS REFUSED HERE, AT THE ONLY PLACE `manage_every` IS READ IN
    # THIS PACKAGE (added 2026-09-04 under the owner's ruling; the switch and the alternatives are
    # at REFUSE_NEGATIVE_PERIOD at the top of this file). It fires BEFORE the Windows is constructed,
    # so no other number is derived from the bad value -- the placement rule
    # capacity/api.py::new_valve took from lm/api.py::resolve, applied here rather than copied: this
    # is a range check over FAB's own lever at its first read, and FAB declares no refusal entry
    # point for it to live in.
    #
    # WHAT A NEGATIVE DID UNTIL 2026-09-05, MEASURED RATHER THAN ASSUMED, AND STATED IN THE PAST
    # TENSE BECAUSE THAT IS WHERE IT BELONGS. `assemble.build` ACCEPTED FAB_MANAGE_EVERY=-5 and
    # froze it; this accessor then returned Windows(-5); and
    # spine/derive.py::cadences_that_cannot_fire then reported ("fab.manage", -5, 0) -- the SAME
    # shape of line it prints for a period of zero. Meanwhile RUN.Cadences.due states its contract
    # as "True at most once per `period` WINDOWS elapsed since this key last fired", so a body
    # written to it compares `step - last_fired >= period.n`, which at -5 is true on the FIRST
    # window and every window after. A negative here is therefore the cull, the spares, replication
    # and the staged-depth check on EVERY window, reported by the one live reader as a gate that
    # cannot fire. That is the same false equation ckpt/api.py::save_period was repaired for.
    #
    # THE THIRD READING IS THE REASON THIS ONE MATTERED MORE THAN ITS SIBLINGS, and it is measured
    # rather than feared. This field is ALSO the source of the FAB.d_manage_period wire, which
    # spine/assemble.py computes with spine/derive.py::flush_period_windows -- and until 2026-09-05
    # that function FLOORED AT ONE FLUSH. So at FAB_MANAGE_EVERY=-5 the tree carried three answers
    # for one number at once, checked by running assemble.build on 2026-09-04: the wire resolved to
    # Flushes(1), i.e. "manage on every flush"; this accessor returned Windows(-5); and
    # cadences_that_cannot_fire reported ("fab.manage", -5, 0), i.e. "this gate cannot fire". The
    # ledger and the audit printed opposite sentences about the same lever in the same run.
    # THIS GUARD NEVER STOOD BETWEEN THE LEVER AND THAT COUPLING and was never claimed to: a wire is
    # computed from the frozen Config before any accessor runs, so the floored Flushes(1) reached
    # the ledger whatever this accessor did afterwards.
    #
    # WHICH MAKES THIS ARM UNREACHABLE THROUGH THE COMPOSITION ROOT TODAY, AND THE OWNING FILE IS
    # WHERE THAT HAS TO BE WRITTEN DOWN. spine/derive.py::flush_period_windows now REFUSES a
    # negative period_windows instead of flooring it, and the FAB.d_manage_period row of
    # spine/assemble.py::COUPLINGS calls it inside that row's `compute` -- so FAB_MANAGE_EVERY=-5 is
    # refused during spine/assemble.py::build, at the coupling stage, BEFORE any Config is frozen
    # and long before any accessor runs. MEASURED, three ways, on the tree as it stands rather than
    # relayed: `assemble.build(environ={'FAB_MANAGE_EVERY': '-5'})` raises units.UnitError out of
    # spine/derive.py::flush_period_windows, through that row's `compute` in
    # spine/assemble.py::COUPLINGS, called from spine/assemble.py::build, and never returns a
    # Config; `spine/compose.py::compose` with the same environment ends in the same place, where
    # DOM, EVAL, MEM and CKPT at -5 all end at capacity/api.py::startup_refusals instead; and
    # `assemble.build(environ={'FAB_MANAGE_EVERY': '-5'}, couplings=[])` -- the coupling table
    # emptied, which is the only way left to get a frozen Config carrying the value -- reaches this
    # guard and raises the LeverError below. The fabric suite's F8 check
    # (tests/test_fabric.py::check_f8_manage_period_kind_and_refusal) reports the same thing in its
    # detail line every run, and docs/04_CONTRACT.md records it; this comment is the third of the
    # three and was the last to say so.
    #
    # AND THE SWITCH IS INERT HERE IN BOTH POSITIONS, WHICH IS THE HALF THAT IS NOT ABOUT PROSE.
    # Setting REFUSE_NEGATIVE_PERIOD = False and rebuilding still raises UnitError from the
    # assembly, so the owner's second sentence -- "if it has a bad effect, we can turn off the
    # refusal" -- cannot be exercised for FAB_MANAGE_EVERY by flipping FAB's switch alone. Turning
    # this refusal off for real means the derive arm too, and that one has no switch. The four
    # sibling accessors do not share this: their levers have no coupling row that converts them.
    #
    # IT IS KEPT RATHER THAN DELETED AS DEAD, AND THE REASON IS NOT POLITENESS. The assembly's
    # refusal is a property of the COUPLING TABLE -- it exists because FAB_MANAGE_EVERY happens to
    # be the source of a d_ wire whose compute is a conversion that refuses negatives. Delete that
    # row, change its compute, or add a caller that builds FAB's Config another way, and the lever
    # is unguarded again with nothing saying so. This guard is the range check FAB owes its OWN
    # lever at its own first read, and it is the one that names FAB_MANAGE_EVERY and the value in
    # FAB's own words. WHAT WOULD MAKE IT FIRE AGAIN, named rather than left to be found: the
    # FAB.d_manage_period row leaving spine/assemble.py::COUPLINGS, its compute moving off
    # spine/derive.py::flush_period_windows, that function's `period_windows.n < 0` arm being
    # removed, or any caller reaching this accessor without the coupling table -- which is exactly
    # what the `couplings=[]` measurement above does. AND THE FIRST OF THOSE WAS MEASURED, not
    # imagined: on a scratch copy of the whole tree with the four negative-count arms deleted from
    # spine/derive.py, `assemble.build` accepted FAB_MANAGE_EVERY=-5 again and THIS guard caught it
    # -- the fabric suite stayed green and its F8 detail line changed by itself from "the refusal
    # came from the assembly" to "the refusal came from FAB.manage_period". That is what a second
    # line is for, and it is why this one is not dead code.
    #
    # ZERO IS NOT TOUCHED, AND WHAT ZERO MEANS HERE IS NOT DECIDED BY THIS GUARD. Unlike CKPT.every
    # (0 disables periodic saving, in the lever's own help text) and MEM.rekey_every (0 DISARMS, in
    # memory/api.py::maintain), FAB_MANAGE_EVERY=0 has NO declared meaning in src/fabric/levers.py or
    # in this file, and there is no `manage` flag here either -- DOM has one and FAB does not, which
    # is the asymmetry the two files' split left behind. The test below is strictly
    # `< 0`, so whatever the tree eventually rules 0 to mean, it still reaches the same readers it
    # reaches today.
    #
    # IT REMOVES NO CONFIGURATION. FAB_MANAGE_EVERY=1 is the every-window pass and is in range; the
    # negative range spells nothing this lever's help text gives a meaning to.
    if REFUSE_NEGATIVE_PERIOD and every < 0:
        raise LeverError(
            f"FAB_MANAGE_EVERY={every}: a management cadence is a count of windows ELAPSED since "
            f"the last pass and may not run backwards. RUN.Cadences.due DECLARES its contract as "
            f"a long-run RATE of one fire per `period` WINDOWS, with jitter bounded by the caller's "
            f"evaluation stride -- its body exists, so this is a statement about running code and "
            f"not only about a contract, and that body compares "
            f"`step - last_fired >= period`, so a negative period is true on the first window and "
            f"on every window after it -- {every} does not mean 'manage less often' or 'do not "
            f"manage', it means the cull, the spares, replication and the staged-depth check on "
            f"EVERY window, while spine/derive.py::cadences_that_cannot_fire reports the same value "
            f"as a gate that cannot fire. FAB_MANAGE_EVERY=1 is the every-window pass and is in "
            f"range. This lever declares no meaning for 0 either, and 0 is deliberately left alone "
            f"by this refusal rather than folded into it. No second lever is consulted here: "
            f"FAB_ON removes the fabric from the forward path and FAB_GROW freezes the population, "
            f"and neither is an off switch for the management pass -- this refuses an out-of-range "
            f"value for FAB's own cadence lever, whether or not another lever makes it moot.")
    return U.Windows(every)
