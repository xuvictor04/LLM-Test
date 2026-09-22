"""WORLD -- the frozen public surface. Signatures only; P4 writes the bodies.

WORLD is a latent state for the observed stream plus a routed population that predicts it forward.
Against GOAL A exactly one lever matters: `feedback`, which conditions the LM's hidden state on the
forecast; with it off the whole subsystem is a costed side head that changes no emitted token. Its
structural claim is "ROOM FOR ADDITIONAL MODALITIES" -- the encoder reads OBSERVATION EMBEDDINGS,
the lowest layer, so a second sense needs new rows in LM's embedding and nothing new here.

D4 RULES IT STAYS AND THAT OFF MUST BE A FIRST-CLASS CONFIGURATION, which is the half the old tree
failed: WORLD_GROW defaults ON and its step hook calls world_fwd.n() OUTSIDE the `if WORLD_MODEL:`
block (:6768 against :4156, where world_fwd is None), so WORLD_MODEL=0 died on None at the first
MANAGE_EVERY and the ab_no_world arm exited 1 with no data. THE ONE ABLATION THAT WOULD HAVE PRICED
THIS PACKAGE WAS THE ONE ABLATION THAT COULD NOT RUN. Here `enabled=False` returns a NULL WORLD
whose every method is defined and returns the inert answer, so no other package can dereference it.

FIVE UNDECLARED CONSTANTS THE PORT MUST NOT INHERIT, none of which has a census row and none of
which may be minted as a lever here: w_cov = 0.04 (hardcoded at :7061 AND as a keyword default in
world_model.py:55 -- a second default living inside a declared lever, and the product loop never
calls wm_loss so the two copies have never had to agree); w_bal = 0.01 (flat for the whole run at
:7060 while the probe decays it 0.05 -> 0 over 2000 steps, so loop and probe optimise different
objectives); min_mass = 1e-3; tau = 1.0; and the plateau pair `_winv > 0.9*_wl_ema` /
`step - _wl_lastgrow > 4*MANAGE_EVERY` (:6769), two magic numbers deciding whether growth may ever
fire, printed nowhere. They become NAMED MODULE CONSTANTS with a written reason, or Gate
parameters -- not levers.

RECORD TYPES RETURNED (P4 defines them):
  World         encoder, population (preds/keys/qproj), fit/mass/alive/grown buffers, world_proj,
                the plateau state (_wl_ema, _wl_lastgrow), counters. `built` is "live" | "null".
  WorldStep     loss, latent, inv, latent_std, horizon -- the last one ADDED WITH THE BODY THAT
                RETURNS IT, because loss_terms' docstring requires that every reading carry the
                horizon it was measured at and `inv` and `latent_std` are readings whose meaning
                changes with it; the record's own docstring argues the case
  ManageResult  grow_attempted, grown, soft_culled, live, blocked_reason
"""
import dataclasses

import torch
from torch import nn
from torch.nn import functional as F

from spine.lever import Config, LeverError


# ==================================================================================================
# THE UNDECLARED CONSTANTS, NAMED -- the module docstring's "FIVE UNDECLARED CONSTANTS THE PORT MUST
# NOT INHERIT", for the two that `loss_terms` below actually reads, plus one the docstring's list
# missed. Each is a MODULE CONSTANT with a written reason, which is the disposition that docstring
# rules: not a lever (no census row creates one, and inventing a name and a default on no authority
# is how a knob acquires its second default in the first place) and not a signature default living
# inside a declared lever, which is the shape L1 forbids.
#
# min_mass = 1e-3 and the plateau pair are NOT declared here. They are read by `manage`, which is
# still a stub, and a named constant with no reader is the armed-and-inert shape one level down --
# they land with the body that reads them.
# ==================================================================================================

W_COV = 0.04
"""The covariance half of the anti-collapse term, relative to the variance half.

IT WAS A SECOND DEFAULT INSIDE A DECLARED LEVER, in two places that never had to agree: hardcoded at
self_organize.py:7061 as `WORLD_VAR * (_wv + 0.04 * _wc)` and again as the keyword default
`w_cov=0.04` in world_model.py:55, whose wm_loss the product loop never calls. The covariance half of
WORLD_COLLAPSE_W's term is therefore controlled by that lever TIMES A CONSTANT NOBODY CAN SET; the
constant stays (no census row mints a lever for it) but it is spelled once, here, so the two copies
cannot drift and a reader can find it."""

W_BAL = 0.01
"""The load-balance weight folded into the prediction term: `inv + W_BAL * bal`.

FLAT FOR THE WHOLE RUN, AND THE PROBE DISAGREES. self_organize.py:7060 holds it at 0.01 while
world_model.py's _probe_population decays it 0.05 -> 0 over 2000 steps
(`_bal = 0.05 * max(0.0, 1.0 - step / 2000.0)`), so the loop and the probe optimise different
objectives and every "population specialises" reading came from the decayed one. The flat value is
what the PRODUCT loop used and is what is ported; the decay is a lever-shaped question nobody has
filed a census row for, and the disagreement is recorded here rather than resolved by a body that
would then be a third answer."""

TAU = 1.0
"""The routing softmax temperature. world_model.py's signature says tau=1.0 and the product loop
passed (3, 6, 128, 24) without one, so 1.0 is what every recorded run actually routed at -- while
_probe_population passes tau=0.5 and reports the specialisation number the subsystem is argued for
on. Spelled here so "the probe routes sharper than the run" is a fact a reader can see."""

FIT_DECAY = 0.98
"""The EMA rate on the per-predictor fitness and routing-mass books.

A SIXTH UNDECLARED CONSTANT, FOUND WHILE WRITING loss_terms AND NOT ON THE MODULE DOCSTRING'S LIST
OF FIVE: `update_fitness(s, w, outs, z_next, decay=0.98)` (world_model.py) is a signature default
that the product loop never overrides, so it has exactly the shape the other five are indicted for.
It is recorded rather than inherited silently. It is NOT FAB's comp_ema and must not be wired to it:
that rate smooths a per-EXPERT competence over language-model loss, this one smooths a per-PREDICTOR
forward-error over a latent MSE, and a wire between them would make two different quantities move at
one rate because they were spelled alike."""


class World:
    """The dynamics subsystem, or a NULL one that every method still answers for.

    THE NULL WORLD IS NOT None AND THAT IS THE WHOLE OF THE D4 REPAIR. At WORLD_ENABLED=0 this
    object still exists and every method returns the inert answer -- zero loss terms, no forecast,
    an empty manage result, an empty geometry. A None would make every caller test for it, and the
    branch that only runs when the subsystem is off is the branch that rots between the runs that
    use it. Here OFF is a configuration the run can actually take, on the same code path.

    `built` is "live" or "null" and is the first thing the report prints about this package,
    because "0 world loss" from a live subsystem and "0 world loss" from a null one are different
    statements and the survey has 57 records of them being printed the same way.

    EVERY SHAPE COMES FROM THE Config. world_model.py's own signature defaults are
    (n0=2, nmax=8, hid=128, route_dim=32, tau=1.0) while the product loop passed (3, 6, 128, 24) --
    four of five differ, so a reader who trusts the module tells themselves the wrong population
    size, cap and key width.
    """

    __slots__ = ("built", "encoder", "preds", "keys", "qproj", "world_proj", "fit", "mass",
                 "alive", "grown", "nmax", "n_live", "horizon", "feedback", "lat",
                 "_wl_ema", "_wl_lastgrow", "counters", "rng")

    def __init__(self, *, built, nmax=0, n_live=0, horizon=1, feedback=False, lat=0, rng=None):
        self.built = built
        self.encoder = self.qproj = self.world_proj = None
        self.preds = self.keys = None
        self.fit = self.mass = self.alive = self.grown = None
        self.nmax, self.n_live = nmax, n_live
        self.horizon, self.feedback, self.lat = horizon, feedback, lat
        self._wl_ema, self._wl_lastgrow = None, 0
        self.counters = {"world.built": built, "world.live": n_live, "world.nmax": nmax}
        self.rng = rng

    def _is_live(self):
        return self.built == "live"

    def parameters(self):
        """Every trainable tensor this package owns, for the composition root's `base` group.

        THE ROOT ASKS THE OBJECT, IT DOES NOT WALK A MODULE TREE -- the same contract
        fabric/api.py::Population.parameters answers, in the same words, for the same reason:
        spine/compose.py::_base_parameters calls `getattr(obj, "parameters", None)` on the model,
        the population and the world, and appends a WARNING where it is missing rather than
        failing. THAT WARNING HAS BEEN PRINTED ON EVERY RUN THIS TREE HAS EVER TAKEN, and this
        method is what stops it being true.

        WHAT THE ABSENCE WAS, MEASURED, AND IT IS NOT "THE WORLD MODEL DOES NOT LEARN". WORLD's
        loss DOES enter the objective -- spine/loop.py::_flush adds it to `total` and backs the sum
        -- and obs_emb is LM.embed's OUTPUT, not a detached copy, so the gradient reaches the
        language model whether or not anything ever steps a world tensor. At initialisation, one
        seed, a batch of 4 windows of 64 tokens at the shipped defaults: the world loss's gradient
        norm on `emb.weight` is 0.005194 against the language-modelling loss's own 0.006371 -- 45%
        of the embedding's total, and the world loss touches NOTHING ELSE in the model, so it is
        not diluted across the rest of the tree. So the state this method ends is a FROZEN RANDOM
        NETWORK supplying nearly half the training signal to the lowest layer of the language
        model, for the whole run, while the measurement inside world/api.py::forecast (max
        abs(delta) over 60 windows, exactly 0.0 for encoder, qproj, preds and keys) recorded that
        the teacher never learned anything. The share is a reading at step 0 and will move as the
        LM's own gradient falls; the direction it moves is up.
        RE-TAKEN WITH THIS METHOD IN PLACE, over the same 60 windows: preds 7.955e-02, encoder's
        two weight matrices 8.078e-02 and 8.075e-02, keys 1.737e-03, qproj 1.156e-03. world_proj
        is the ONE that still reads exactly 0.0, and it is not this method's to move: world_proj
        appears in no expression but the forecast's, which has no caller (Q-WORLD-10), so the only
        gradient it can ever receive arrives the moment that call site exists.
        THE DESIGN IS NOT THE DEFECT. Shaping the embedding by predictability plus an anti-collapse
        penalty is what world/api.py::loss_terms is FOR (`predict_w * pop_loss + collapse_w *
        (var_loss + W_COV * cov_loss)`), and leaving obs_emb attached is what makes the language
        model a participant rather than a data source. What was wrong is only that one side of that
        exchange was never stepped.
        PREALLOCATED, SO THE GROUP STRUCTURE IS FIXED. `preds` and `keys` are (nmax, ...)
        Parameters and growth only advances n_live into rows that already exist, so this list is
        the same length on every step of every run and a checkpoint's param-group structure cannot
        depend on how much the population grew -- the same argument Population.parameters makes,
        and the reason WORLD.manage's add_param_group is about a FUTURE mint rather than about
        these five tensors.
        THE NULL WORLD RETURNS AN EMPTY LIST AND NOT AN ERROR, which is the D4 rule this class is
        built on: WORLD_ENABLED=0 is a configuration a run takes, every method is defined on it,
        and `built == "null"` is what a report reads -- so contributing nothing here is the honest
        answer rather than a missing method, which is the state that produced the warning.
        """
        if not self._is_live():
            return []
        return ([self.preds, self.keys] + list(self.encoder.parameters())
                + list(self.world_proj.parameters()) + list(self.qproj.parameters()))


def build(world: Config, *, d_model, device, ctx_tokens, rng):
    """Construct the subsystem, or a NULL WORLD that no other package can dereference.

    When world.enabled is False, every method below is DEFINED and returns the inert answer --
    loss_terms returns zero terms, forecast returns None, manage returns an empty result, geometry
    returns {} -- so OFF is a configuration a run can actually take and cannot rot between the runs
    that use it. That is the whole of the D4 repair.

    THE SIGNATURE DEFAULTS IN world_model.py ARE NOT THE RUN'S. DynamicsPopulation's own signature
    says (n0=2, nmax=8, hid=128, route_dim=32, tau=1.0) while the product loop passes
    (3, 6, 128, 24) at :4156 -- four of five differ, so reading world_model.py alone tells a reader
    the wrong population size, cap and key width. Every value comes from this Config.

    LEVERS READ: enabled, lat, hid, route_d, n0, nmax, feedback, horizon
    WIRES READ: none
    DID IT FIRE: World.built ("live" | "null"), and the constructed shape as a record
    """
    world = world.owned_by("WORLD")
    if not bool(world.enabled):
        # THE NULL WORLD. Constructed, not None -- see the class docstring. It carries the horizon
        # and the feedback flag so a caller can still print what the run WOULD have done, and
        # `built` reads "null" so no report can confuse an inert subsystem with a live one that
        # measured zero.
        return World(built="null", horizon=int(world.horizon), feedback=bool(world.feedback),
                     lat=int(world.lat), rng=rng)

    lat, hid, route_d = int(world.lat), int(world.hid), int(world.route_d)
    n0, nmax = int(world.n0), int(world.nmax)
    if n0 > nmax:
        raise ValueError(
            f"WORLD_N0={n0} exceeds WORLD_NMAX={nmax}: the founding population does not fit in the "
            f"pool. Refused rather than clamped -- a clamp would make the banner print a founding "
            f"size the run did not use.")

    # ON THE TARGET DEVICE, matching the repair already applied to FAB.build, LM.build_model and
    # SIG.build (commit b95c4a4): torch's in-place random ops require the generator and the tensor
    # it fills to share one device, and this constructor draws directly into w.encoder/world_proj/
    # qproj AFTER they are moved `.to(device)` two lines below. A cpu generator there raised
    # RuntimeError on every RUN_DEVICE=cuda run, before any tensor in the world model was built --
    # latent on the CPU-only suite this project runs, which is exactly why the sibling packages'
    # fix (b95c4a4) missed this fourth copy of the identical shape.
    gen = torch.Generator(device=device)
    gen.manual_seed(rng.randint(0, 2 ** 31 - 1))
    w = World(built="live", nmax=nmax, n_live=n0, horizon=int(world.horizon),
              feedback=bool(world.feedback), lat=lat, rng=rng)

    w.encoder = nn.Sequential(nn.Linear(int(d_model), hid), nn.Tanh(), nn.Linear(hid, lat)).to(device)
    w.world_proj = nn.Linear(lat, int(d_model)).to(device)
    w.qproj = nn.Linear(lat, route_d).to(device)
    # PREALLOCATED TO nmax, LIKE THE FABRIC'S POOL, so growth advances n_live into rows that already
    # exist. A dynamics population that MINTS parameters mid-run is the case OPT's add_param_group
    # callable exists for, and it is the one that makes a resume's param-group structure depend on
    # how much the parent grew.
    w.preds = nn.Parameter(torch.zeros(nmax, lat, lat, device=device))
    w.keys = nn.Parameter(torch.zeros(nmax, route_d, device=device))
    # BUFFERS SIZED nmax, NOT n_live. world_model.py registered fit/mass/alive as buffers of size
    # nmax and the resume path read only world_cfg["n"], so a resume at a different WORLD_NMAX
    # reached load_state_dict with mismatched buffer shapes -- which is ISSUES P1-H22 from the side
    # this constructor controls.
    w.fit = torch.zeros(nmax, device=device)
    w.mass = torch.zeros(nmax, device=device)
    w.alive = torch.zeros(nmax, dtype=torch.bool, device=device)
    w.alive[:n0] = True
    w.grown = torch.zeros(nmax, dtype=torch.long, device=device)

    with torch.no_grad():
        for t in list(w.encoder.parameters()) + list(w.world_proj.parameters()) + \
                list(w.qproj.parameters()):
            if t.dim() >= 2:
                t.uniform_(-0.1, 0.1, generator=gen)
            else:
                t.zero_()
        # keys are drawn; preds stay ZERO so a newly grown predictor is the identity-free zero map
        # and adding one perturbs nothing that already works -- the same rule as the fabric's B.
        # DRAWN DIRECTLY INTO w.keys, IN PLACE, rather than filling an implicit-cpu `k =
        # torch.empty(nmax, route_d)` and copying it over: now that `gen` lives on `device` (the
        # fix two lines above this block), a cpu-allocated intermediate tensor would itself raise
        # the same device-mismatch RuntimeError this whole repair exists to remove on
        # RUN_DEVICE=cuda. w.keys was already allocated with device=device at construction, so
        # writing into it directly needs no intermediate tensor and no .to(device) copy at all.
        w.keys.uniform_(-0.1, 0.1, generator=gen)

    w.counters.update({
        "world.built": "live", "world.live": n0, "world.nmax": nmax,
        "world.lat": lat, "world.route_d": route_d, "world.horizon": int(world.horizon),
        "world.ctx_tokens": int(ctx_tokens),
        "world.feedback": 1 if bool(world.feedback) else 0,
    })
    return w


@dataclasses.dataclass(frozen=True)
class WorldStep:
    """What one flush's world-model pass measured. FIELDS ONLY, NO METHODS.

    No methods, for the reason lm/api.py::LoadReport states: a public method on a public class in an
    api.py IS an entry point -- tests/test_contract.py's K1 and K6 both say so -- and a record that
    answers with its fields costs the contract nothing.

    `horizon` IS A FIELD AND THE MODULE DOCSTRING'S FIELD LIST GREW BY IT (loss, latent, inv,
    latent_std -> and horizon), because loss_terms' own docstring makes it an obligation this record
    is the only thing that can keep: "`horizon` slices z[:, :-K] against z[:, K:], so a number
    labelled 'forward-pred MSE' silently means a DIFFERENT COMPARISON at every value -- EVERY READING
    MUST CARRY THE HORIZON IT WAS MEASURED AT or two runs' numbers are not comparable and nothing
    says so." `inv` and `latent_std` are exactly such readings. Putting the horizon in a counter
    instead would separate it from the number it qualifies at the first report line that prints one
    without the other, which is the separation the sentence forbids.

    `inv` AND `latent_std` ARE None ON THE NULL WORLD, AND THAT IS NOT A ZERO. A null world measures
    nothing; a latent_std of 0.0 is what a fully COLLAPSED encoder reads, and the record whose
    subsystem never ran may not print the number its worst failure produces. `loss` is a real zero
    tensor there, because it is a SUMMAND -- the composed objective adds it on every arm and a
    caller that had to branch on None would be the "the branch that only runs when the subsystem is
    off is the branch that rots" case this package's class docstring refuses.
    """
    loss: object
    latent: object
    inv: object
    latent_std: object
    horizon: int


def _var_cov(z):
    """VICReg's two anti-collapse statistics over a (N, lat) latent: (var_loss, cov_loss).

    PORTED FROM world_model.py::_var_cov WITH ONE CHANGE, and the change is the diagonal. The source
    writes `cov.fill_diagonal_(0)` -- an IN-PLACE write into the output of `z.T @ z`, a tensor
    autograd is holding for the backward of the very matmul that produced it. Multiplying by an
    off-diagonal mask is the same arithmetic (the diagonal contributes 0 to the sum either way) with
    no in-place write, which is the difference between a term that is correct and one that is
    correct until torch's version counter starts checking. Nothing else moves: the 1e-4 inside the
    sqrt, the relu(1 - std) hinge and the /d normaliser are the source's.
    """
    n, d = z.shape
    if n < 2:
        # REFUSED, NOT COMPUTED. The covariance divides by (n - 1) and a single row makes that a
        # division by zero -- inf, then nan through the sum, and a nan loss is a NUMBER the run
        # keeps training on rather than an error anybody sees. This is the same refusal
        # startup_refusals makes about an empty slice, at the one place the actual row count is
        # known.
        raise ValueError(
            f"WORLD.loss_terms: the anti-collapse term was handed {n} latent row(s) and needs at "
            f"least 2 -- the covariance normaliser is (n - 1). A batch and a window this small "
            f"cannot estimate a covariance, and computing one anyway returns nan rather than "
            f"raising.")
    z = z - z.mean(0)
    std = torch.sqrt(z.var(0) + 1e-4)
    var_loss = F.relu(1.0 - std).mean()
    cov = (z.t() @ z) / (n - 1)
    off = 1.0 - torch.eye(d, device=z.device, dtype=cov.dtype)
    cov_loss = (cov * off).pow(2).sum() / d
    return var_loss, cov_loss


def _route(w, z, live):
    """(weights, outs) over the LIVE predictors only: weights (N, L), outs (N, L, lat).

    DEAD SLOTS ARE NOT IN THE FORWARD AT ALL, and that is `manage`'s ruling applied at the only
    place the forward exists: "A DEAD PREDICTOR IS SKIPPED IN THE FORWARD, not merely down-weighted:
    world_model.py:92-94 stacks EVERY predictor's output and :88 holds the dead ones down with
    log(alive.clamp_min(1e-6)), so a culled predictor ran and took gradient every step for about
    1e-6 of the routing mass. A hard penalty is a skip." So the log(alive) bias term is deliberately
    NOT ported -- the mask selects the rows instead, and the compute cost of a culled predictor
    actually stops being paid.

    THE PREDICTOR IS RESIDUAL: pred_i = z + z @ preds[i]. world_model.py::ForwardModel returns
    `z + s.net(x)` with the comment "residual: predict the CHANGE (delta) -> stable multi-step
    rollout", and build() relies on exactly this when it leaves `preds` at ZERO: a slot whose map is
    the zero map predicts persistence, which is what makes a newborn "the identity-free zero map"
    that "perturbs nothing that already works". A non-residual `z @ preds[i]` would make every
    newborn predict the ZERO VECTOR instead, which is not a neutral element of the blend.
    """
    q = w.qproj(z)
    keys = w.keys[live]
    logits = (q @ keys.t()) / (float(keys.shape[-1]) ** 0.5)
    weights = torch.softmax(logits / TAU, dim=-1)
    # sum_d z[n,d] * preds[l,d,k] -- each live predictor's linear map applied to every row, in one
    # einsum rather than a python loop over slots: the population is the point of this subsystem and
    # a per-slot loop would make its cost grow with a number the design wants free to grow.
    outs = z.unsqueeze(1) + torch.einsum("nd,ldk->nlk", z, w.preds[live])
    return weights, outs


def loss_terms(world: Config, w, obs_emb):
    """The two terms this subsystem adds to the training loss. Called once per FLUSH.

    obs_emb is LM.embed(lm, model, x), (B, W, d_model) -- an ARGUMENT, because the encoder reads
    OBSERVATION embeddings (the lowest layer, the point where a new sense plugs in) and not the GRU
    state. IT HAS A PRODUCER as of 2026-09-02 (Q-LM-12 RESOLVED (b)): LM exposed no embedding entry
    point, the composition root's own table said the loop applied `model.emb(x)` between two calls,
    and that expression is an AttributeError at lm.compose=1 because LM does not construct `emb`
    under compose. `LM.encode(..., n_layers=0)` was refused as the producer on BOTH arms -- the gru
    arm ignores n_layers by declared gate and would return the full hidden, and the transformer arm
    at zero blocks returns embedding PLUS positional. Returns WorldStep(loss, latent, inv,
    latent_std).

    tot += predict_w * pop_loss(...) + collapse_w * (var + 0.04 * cov). THE TWO WEIGHTS MUST NOT BE
    FOLDED BACK INTO ONE and the names now make folding require deliberately writing the wrong
    name: the integration once multiplied the anti-collapse term by WORLD_W=0.1, running it at one
    tenth strength, and the latent collapsed to std 0.24; splitting it out moved latent std
    0.24 -> 0.97 and forward-pred against persistence +13.6% -> +34.1%.

    `horizon` slices z[:, :-K] against z[:, K:], so a number labelled "forward-pred MSE" silently
    means a DIFFERENT COMPARISON at every value -- EVERY READING MUST CARRY THE HORIZON IT WAS
    MEASURED AT or two runs' numbers are not comparable and nothing says so.

    LEVERS READ: predict_w, collapse_w, horizon
    WIRES READ: none
    DID IT FIRE: WorldStep is returned on every flush; latent_std is the collapse check the record
                 says never once exceeded 0.15 against the code's own "want ~1" bar
    """
    world = world.owned_by("WORLD")
    horizon = int(world.horizon)
    w.counters["world.loss_terms.calls"] = w.counters.get("world.loss_terms.calls", 0) + 1
    if not w._is_live():
        # THE NULL WORLD ANSWERS, AND ITS ANSWER IS NOT A MEASUREMENT. The class docstring's D4
        # repair is this line: OFF is a configuration the run can actually take, on the same code
        # path, so no caller tests for None and the off-branch cannot rot between the runs that use
        # it. `loss` is a real zero on the argument's own device -- it is a summand of the composed
        # objective and the caller adds it unconditionally -- while inv and latent_std are None,
        # because a latent_std of 0.0 is what a COLLAPSED encoder reads and printing the worst
        # failure's number for a subsystem that never ran is the "0 world loss from a live
        # subsystem and 0 world loss from a null one printed the same way" defect the survey has 57
        # records of.
        w.counters["world.loss_terms.inert"] = w.counters.get("world.loss_terms.inert", 0) + 1
        w.counters["world.loss_terms.unreachable"] = (
            "WORLD_ENABLED=0: build() returned a null world, so there is no encoder to measure a "
            "latent with and no population to predict one forward")
        return WorldStep(loss=torch.zeros((), device=obs_emb.device), latent=None, inv=None,
                         latent_std=None, horizon=horizon)

    # THE TWO WEIGHTS, READ AS TWO. Folding them is the historical bug and the names are what make
    # folding require deliberately writing the wrong name: the integration once multiplied the
    # anti-collapse term by WORLD_W=0.1, ran it at one tenth strength, and the latent collapsed to
    # std 0.24; splitting it out moved latent std 0.24 -> 0.97 and forward-pred against persistence
    # +13.6% -> +34.1%. They are read into two locals and multiplied into two separate summands
    # below, and there is no expression anywhere in this function in which one scales the other.
    predict_w, collapse_w = float(world.predict_w), float(world.collapse_w)

    z = w.encoder(obs_emb)
    if z.dim() != 3:
        raise ValueError(
            f"WORLD.loss_terms: obs_emb encoded to {tuple(z.shape)} and this function slices a "
            f"(B, W, lat) latent along its WINDOW axis. LM.embed returns (B, L, width); a caller "
            f"that flattened it has removed the axis the horizon is measured along.")
    width = int(z.shape[1])
    if width <= horizon:
        # BOTH SLICES EMPTY, REFUSED WHERE THE REAL WIDTH IS KNOWN. startup_refusals already
        # refuses horizon >= ctx_tokens, which is the same statement made against the LEVER before
        # any tensor exists; this one is against the tensor that actually arrived, because the two
        # can disagree (a caller may pass a narrower window than LM_CTX) and the failure mode is a
        # loss of nan rather than an error -- a number the run keeps training on.
        raise ValueError(
            f"WORLD.loss_terms: the window is {width} position(s) wide and WORLD_HORIZON is "
            f"{horizon}, so z[:, :-{horizon}] and z[:, {horizon}:] are both empty and the loss "
            f"comes out nan rather than raising. The startup refusal makes this statement against "
            f"LM_CTX; this one is against the tensor that arrived.")

    lat = int(z.shape[-1])
    # THE SLICE IS THE MEASUREMENT'S DEFINITION, which is why every reading below travels with the
    # horizon on the record: at horizon 1 `inv` is "predict the next position", at 8 it is "predict
    # eight positions on", and the two are printed under the same words by every report this
    # project has written.
    z_t = z[:, :-horizon].reshape(-1, lat)
    z_next = z[:, horizon:].reshape(-1, lat)

    live = w.alive.nonzero(as_tuple=True)[0]
    if int(live.numel()) == 0:
        # NOT A ZERO LOSS. An empty live population cannot produce a forecast at all, and returning
        # zero terms here would be indistinguishable from the null world two branches above -- the
        # one confusion this package's whole shape exists to prevent. soft_cull is specified never
        # to take the last live predictor, so reaching this is a `manage` defect and says so.
        raise ValueError(
            "WORLD.loss_terms: every predictor slot is culled (alive.sum() == 0), so nothing can "
            "route and no forward prediction exists. soft_cull never takes the last live "
            "predictor, so this state is written by something that ignored that rule -- it is not "
            "a configuration, and a zero loss here would read as WORLD_ENABLED=0.")
    if int(live.numel()) != int(w.n_live):
        # RECORDED, NOT REPAIRED. `alive` is the load-bearing book (state_dict says so: a resume
        # that rebuilt it from anything else would silently resurrect culled predictors) and
        # `n_live` is a summary of it; when they disagree the mask wins here, and the disagreement
        # is a counter rather than a silent correction, because whichever writer let them drift is
        # the thing that needs finding.
        w.counters["world.live_mask_vs_n_live"] = f"{int(live.numel())} vs {int(w.n_live)}"

    weights, outs = _route(w, z_t, live)
    pred = (weights.unsqueeze(-1) * outs).sum(1)
    inv = F.mse_loss(pred, z_next)
    # THE LOAD-BALANCE HALF OF THE PREDICTION TERM, exactly as world_model.py::pop_loss spells it:
    # uniform load scores w.size(1) * (1/n)^2 summed = 1, and any concentration scores higher. It
    # stops the early collapse onto one predictor, which is the failure that makes a POPULATION an
    # expensive way to have one forward model.
    bal = float(weights.shape[1]) * weights.mean(0).pow(2).sum()
    pop_loss = inv + W_BAL * bal

    # THE ANTI-COLLAPSE TERM IS TAKEN OVER THE WHOLE LATENT, ONCE. The rejected alternative is
    # world_model.py::wm_loss's `w_var * (v1 + v2) + w_cov * (c1 + c2)` -- _var_cov called on BOTH
    # slices and summed -- which at one weight is the same term at DOUBLE magnitude, and this
    # function's docstring fixes the expression as `collapse_w * (var + 0.04 * cov)`, one of each.
    # The two slices' union IS every position of z (z[:, :-K] together with z[:, K:] covers all of
    # them for any K < W), so measuring once over the flattened z regularises exactly the same
    # vectors the paired form does, at the magnitude the 0.24 -> 0.97 repair was measured at.
    var_loss, cov_loss = _var_cov(z.reshape(-1, lat))
    loss = predict_w * pop_loss + collapse_w * (var_loss + W_COV * cov_loss)

    with torch.no_grad():
        # THE BOOKS `manage` SELECTS ON, UPDATED HERE BECAUSE THIS IS THE ONLY CALL THAT HOLDS A
        # ROUTING TABLE *AND* A TARGET TO SCORE IT AGAINST. world_model.py::pop_loss updates
        # fitness inside itself for the same reason.
        # THE SECOND HALF OF THAT SENTENCE IS NEW AND THE SENTENCE WAS FALSE WITHOUT IT the day
        # world/api.py::forecast acquired a body: forecast routes EVERY position of the same latent
        # through the same keys, so "the only call that holds the routing table" stopped being true.
        # What it does not hold is z_next -- it forecasts from the last position of the window too,
        # and that target lies past the window's end -- so a fitness EMA updated there would be an
        # error scored against nothing, and `fit` is a SELECTION key. The books stay here.
        # Leaving them at zero was the rejected alternative and it is not neutral: `mass`
        # is what soft_cull's min_mass tests, so a population whose mass never moves is one where
        # every predictor but the last is culled on the first management pass, and `fit` is what
        # grow() clones the fittest from, so an unmoved fit makes "the fittest" mean slot 0.
        # FIT_DECAY is the module constant above, not FAB's comp_ema -- see its docstring.
        err = (outs - z_next.unsqueeze(1)).pow(2).mean(-1)          # (N, L) per-live-predictor error
        wmass = weights.sum(0)
        werr = (weights * err).sum(0) / wmass.clamp_min(1e-6)
        seeded = w.mass[live] == 0
        # SEEDED ON THE FIRST PASS RATHER THAN DECAYED FROM A ZERO, which is FAB.observe's rule for
        # the identical shape: an EMA decayed from zero reports a fitness no predictor earned for
        # as long as it takes the rate to forget the seed, and `fit` is a selection key.
        w.mass[live] = torch.where(seeded, wmass,
                                   FIT_DECAY * w.mass[live] + (1.0 - FIT_DECAY) * wmass)
        w.fit[live] = torch.where(seeded, werr,
                                  FIT_DECAY * w.fit[live] + (1.0 - FIT_DECAY) * werr)
        latent_std = float(z_t.std(0).mean())
    w.counters["world.fitness_updates"] = w.counters.get("world.fitness_updates", 0) + 1
    # THE COLLAPSE CHECK, AS A GAUGE AND WITH ITS HORIZON. The record says this number never once
    # exceeded 0.15 against the code's own "want ~1" bar across 413 full-stack readings, so it is
    # the first thing a reader of this subsystem looks for; `world.horizon` is already in the
    # counters from build(), and the WorldStep carries it beside the reading itself.
    w.counters["world.latent_std"] = round(latent_std, 6)
    w.counters["world.inv"] = round(float(inv.detach()), 6)
    w.counters["world.live"] = int(live.numel())
    return WorldStep(loss=loss, latent=z_t.detach(), inv=float(inv.detach()),
                     latent_std=latent_std, horizon=horizon)


def forecast(world: Config, w, obs_emb):
    """The forecast the LM's hidden state is conditioned on: world_proj(pop(z)). None when
    `feedback` is off, and None on the null world.

    obs_emb is LM.embed's return, the same object loss_terms takes and the same the B row above
    produces -- which is why that row is the FIRST of the B rows: this call supplies LM.encode's
    `extra` on the row below it.

    THIS IS A RUNTIME ARGUMENT, NOT A WIRE, and the levers file's phrase "becomes a declared d_ wire
    into LM" cannot be honoured literally: a Coupling value is resolved once and frozen when
    build() returns, and this is a tensor recomputed every flush. The repair the phrase is reaching
    for is real and is kept: LM.encode takes `extra` as a PARAMETER, so the monkey-patch at
    :4158-4169 (`model._raw_encode = model.encode`, then rebinding model.encode to a closure) does
    not port. That patch cost two real defects -- a timing probe's stale module enumeration let 29
    world-model parameters enter the training loop holding gradients computed from RANDOM TOKENS
    (PROBE=1 and PROBE=0 had byte-identical weights entering the loop and split at the second
    logged step, 6.1199 vs 6.1125, never rejoining), and world_proj had to be added to the
    checkpoint (:5369) or generation ran a different network than training.

    LEVERS READ: feedback
    WIRES READ: none
    DID IT FIRE: World.forecasts -- the count of flushes on which a forecast was actually APPLIED
    FOUR MORE KEYS THE BODY WRITES, declared here the way fabric/api.py::grow_check declares its
    own additions: a key a report can read and the contract does not admit to producing is the same
    defect as a declared key nothing writes, and this entry point needs all four to say which of
    its three states a run was in.
      world.forecast.calls -- how many times this function was CALLED. Without it `world.forecasts`
        is ABSENT both when a lever refused the forecast and when nothing invoked this function at
        all, and ON 2026-09-22 THE SECOND IS THE TRUE ONE: no row of spine/loop.py's LOOP_ORDER
        names `forecast`, so the pair (calls present, forecasts absent) is the only shape that can
        separate "called and declined" from "never reached".
      world.forecast.inert -- calls that returned None, which is the denominator `world.forecasts`
        has no other way to state.
      world.forecast.unreachable -- WHY None, in a sentence, and it is the SAME key
        world/api.py::loss_terms writes on the null arm for the same reason: WORLD_ENABLED=0 and
        WORLD_FEEDBACK=0 are two different configurations that return the identical None, and a
        subsystem that was never built and one that was built and is not listened to are the two
        readings this package exists to keep apart.
      world.forecast_rms -- the root-mean-square of the additive term itself. `world.forecasts`
        counts fires and cannot tell conditioning from a no-op, and the claim this whole package
        makes against goal A is that the forecast CHANGES an emitted token: a term of magnitude
        1e-6 beside a hidden state of order 1 changes none of them while the fire counter reads
        one per flush. IT IS HALF A READING AND SAYS SO -- the hidden state is not an argument
        here, so nothing in this package can form the ratio; the other half is LM's own
        lm.encode.extra_applied, which counts the flushes on which the term was actually added.
    """
    world = world.owned_by("WORLD")
    # THIS ENTRY POINT HAS NO CALLER AND HAS NOT BEEN GIVEN ONE (Q-WORLD-10, HELD 2026-09-22).
    # THE FIRST OF THE HOLD'S TWO REASONS IS CLOSED AND THE SECOND IS NOT, which is why this
    # paragraph is still here. Closed: World.parameters() now exists, WORLD's tensors are in
    # OPT's `base` group, and over 60 windows preds moves 7.955e-02 and the encoder 8.08e-02 where
    # both read EXACTLY 0.0 before. So the population is no longer the identity map it is
    # zero-initialised as, and `z` is no longer build()'s uniform draw.
    # STILL OPEN: world_proj. It appears in NO expression in this package but the one below, so the
    # forecast's own call site is the only gradient path it can ever have -- re-measured over those
    # same 60 windows it is the one tensor still reading exactly 0.0, while every other moved. A
    # first call therefore adds world_proj's RANDOM uniform(-0.1, 0.1) projection to the hidden
    # state: one measured call returned world.forecast_rms 0.11047, and WORLD_FEEDBACK ALREADY
    # SHIPS True, so a call site is the only thing withholding it.
    # THAT IS A BOOTSTRAP AND NOT A PERMANENT DEFECT -- it is what adding any head looks like -- but
    # this tree has a rule about it and world_proj does not follow it: fabric/api.py::build
    # zero-inits A and B so "every expert is born an identity, so adding one never disrupts what
    # already works", and build() above zero-inits `preds` citing the same sentence. world_proj is
    # the third tensor of that kind and is drawn uniform. SETTLE THAT BEFORE WIRING, not after: the
    # question is whether the forecast should be born a no-op and grow, like everything else this
    # tree adds mid-run, and it costs nothing to answer while there is still no caller.
    # THE CALL COUNT IS SEEDED BEFORE EITHER GATE BELOW DECIDES ANYTHING, which is this tree's rule
    # about absence: ABSENT must mean the mechanism was UNREACHABLE on the arm this run took, so a
    # counter seeded inside the else of the gate it describes is a defect rather than a detail.
    # `world.forecasts` is deliberately NOT seeded here and is written only where a forecast is
    # produced -- on the two arms below no forecast can EVER be produced, so a present-and-0 there
    # would say "armed and did not fire" about a mechanism that is not armed.
    w.counters["world.forecast.calls"] = w.counters.get("world.forecast.calls", 0) + 1
    if not w._is_live():
        # THE NULL WORLD ANSWERS AND ITS ANSWER IS None, not a zero tensor -- the D4 repair the
        # class docstring states, one entry point over from loss_terms. The asymmetry with that
        # function is deliberate and is the contract's: `loss` is a SUMMAND the composed objective
        # adds unconditionally, so it must be a real zero; the forecast is LM.encode's `extra`,
        # which that function already accepts as None and shape-checks when it is not
        # (lm/api.py::encode), so None costs no caller a branch.
        # AND A ZERO TENSOR HERE WOULD BE WORSE THAN AN ALLOCATION. lm/api.py::encode bumps
        # lm.encode.extra_applied for every non-None `extra` it adds, so returning zeros would make
        # a run with no world model report one conditioned hidden state per flush -- the "0 world
        # loss from a live subsystem and 0 world loss from a null one printed the same way" defect
        # this package's shape exists to prevent, rebuilt one package away where WORLD cannot see
        # it.
        w.counters["world.forecast.inert"] = w.counters.get("world.forecast.inert", 0) + 1
        w.counters["world.forecast.unreachable"] = (
            "WORLD_ENABLED=0: build() returned a null world, so there is no encoder to produce a "
            "latent, no population to route it through and no world_proj to project it back into "
            "the hidden state's width")
        return None
    if not bool(world.feedback):
        # THE ONE LEVER THIS FUNCTION READS, AND THE ONLY THING IN THIS PACKAGE THAT TOUCHES GOAL A.
        # Off, the subsystem is still built, still measured and still costed -- loss_terms runs
        # every flush -- and not one emitted token differs from a run without it. world/levers.py
        # records the archive's verdict on that state; this branch is where it is taken, and the
        # sentence on the counter is what makes a report say "built and not listened to" instead of
        # printing the same None the disabled arm prints.
        w.counters["world.forecast.inert"] = w.counters.get("world.forecast.inert", 0) + 1
        w.counters["world.forecast.unreachable"] = (
            "WORLD_FEEDBACK=0: the world model is built and trains, and its forecast is "
            "deliberately not applied -- the costed side head this lever exists to turn into a "
            "contribution")
        return None

    # THE ENCODER RUNS A SECOND TIME ON THE SAME obs_emb, AND THE COST IS MEASURED RATHER THAN
    # WAVED AT. loss_terms already encodes this flush's embeddings; the frozen signature takes
    # obs_emb and not the latent, so the two calls cannot share one forward and the flush pays two
    # encoder passes over (B, W, d_model). Measured at the shipped geometry, one window of 128
    # tokens, threads pinned: the duplicate encoder pass is 0.075 ms and this whole entry point
    # 0.464 ms, against 5.558 ms for the LM.encode call it conditions -- so the duplication is
    # about 1% of the forward it rides on. A shared `z` would also have to travel from a B row that
    # runs AFTER this one (loss_terms sits below encode in LOOP_ORDER's B block, and this call
    # supplies encode's argument), so the sharing would invert the order before it saved anything.
    z = w.encoder(obs_emb)
    if z.dim() != 3:
        # THE SAME REFUSAL loss_terms MAKES, AGAINST THE SAME ARGUMENT, because the two functions
        # are handed the identical object by the identical row and a caller that flattened it is a
        # caller both must refuse. Here the axis matters for a second reason: LM.encode compares
        # `extra`'s shape against the hidden's EXACTLY, so a (N, lat) forecast would be refused one
        # package away by a message about width rather than here by one about the window axis.
        raise ValueError(
            f"WORLD.forecast: obs_emb encoded to {tuple(z.shape)} and LM.encode's `extra` must be "
            f"exactly (B, L, width). LM.embed returns (B, L, d_model); a caller that flattened it "
            f"has removed the axis the forecast has to be laid back along.")
    n_b, n_w, lat = int(z.shape[0]), int(z.shape[1]), int(z.shape[-1])

    live = w.alive.nonzero(as_tuple=True)[0]
    if int(live.numel()) == 0:
        # NOT A None. An empty live population cannot route, and returning None here would be
        # indistinguishable from WORLD_FEEDBACK=0 two branches above -- which is the one confusion
        # this package's whole shape exists to prevent, and is why loss_terms raises on the same
        # state rather than returning zero terms. This function runs BEFORE loss_terms in the B
        # block, so on a run where the population has been emptied THIS is the refusal an operator
        # sees; it names the rule that was broken rather than the symptom.
        raise ValueError(
            "WORLD.forecast: every predictor slot is culled (alive.sum() == 0), so nothing can "
            "route and no forecast exists. soft_cull never takes the last live predictor, so this "
            "state is written by something that ignored that rule -- it is not a configuration, "
            "and a None here would read as WORLD_FEEDBACK=0.")

    # EVERY POSITION IS FORECAST, NOT ONLY THE ONES loss_terms SCORES, AND THAT IS FORCED.
    # loss_terms routes z[:, :-horizon] because it needs z[:, horizon:] as a target; `extra` has to
    # be EXACTLY the hidden's shape (lm/api.py::encode refuses anything else rather than
    # broadcasting), so a forecast missing the last `horizon` positions could not be the additive
    # term at all. WHAT THAT COSTS IS WORTH WRITING DOWN: the last `horizon` position(s) of each
    # window are conditioned on a prediction whose target lies past the window's end, so they are
    # the positions whose forecast NOTHING in this package has ever scored. They are also the
    # positions the LM is furthest along on, and the term is additive rather than gating, so the
    # exposure is bounded by world_proj's own magnitude -- which is what world.forecast_rms below
    # is for.
    # NO HORIZON IS READ HERE AND THE LEVERS READ LINE SAYS feedback ALONE. The horizon is baked
    # INTO the predictors by training -- loss_terms fits them to carry z_t to z_{t+K} -- so this
    # function applies the map and has no slice to take; reading WORLD_HORIZON here would be a
    # second declaration of one number in the one place it cannot disagree with itself yet.
    # AND NO POSITION IS SHIFTED, WHICH IS THE CAUSALITY ARGUMENT AND IT IS MEASURED. Nothing in
    # this expression mixes positions: the encoder is position-wise, `_route` flattens the window
    # into rows and every row is routed and predicted on its own, so forecast[:, t] is a function
    # of obs_emb[:, t] ALONE -- verified by perturbing obs_emb at position 40 of a 128-token window
    # and finding position 40 and no other moved in the return. That is what makes this term safe
    # to add to a CAUSAL model's hidden state: h[:, t] already saw x[t], so conditioning it on a
    # map of x[t] tells it nothing it did not have. A shifted variant (laying the forecast of
    # z_{t+K} onto position t+K) would also be causal but would be a LAGGED RE-ENCODING rather than
    # a forecast, and the frozen docstring's expression is world_proj(pop(z)) with no shift in it.
    weights, outs = _route(w, z.reshape(-1, lat), live)
    # THE SAME BLEND loss_terms TAKES, spelled the same way on purpose: the forecast that
    # conditions the LM and the forecast the prediction loss is measured on must be ONE quantity,
    # or the subsystem is trained on one map and read through another. `_route` already skips the
    # dead slots rather than down-weighting them (world/api.py::_route), so a culled predictor
    # contributes nothing to what the LM sees and costs nothing to compute.
    pred = (weights.unsqueeze(-1) * outs).sum(1)
    # BACK ONTO THE WINDOW AXIS, THEN INTO THE HIDDEN STATE'S WIDTH. world_proj is Linear(lat,
    # d_model) and this is the ONLY place in the package that calls it -- build constructs it,
    # state_dict saves it, load_into restores it, and nothing else reads it.
    out = w.world_proj(pred.reshape(n_b, n_w, lat))

    # NOT DETACHED, AND THE DETACH WOULD HAVE BEEN THE DEFECT. world_proj appears in no other
    # expression in this file, so the LM loss reaching back through this return is the ONLY
    # gradient it can ever receive: detaching here would leave it at build()'s uniform(-0.1, 0.1)
    # draw for the whole run while state_dict faithfully saved it, which is an untrained random
    # projection added to every hidden state -- noise conditioning wearing a world model's name,
    # and precisely the failure the archive records when world_proj had to be added to the
    # checkpoint or generation ran a different network than training.
    # MEASURED, NOT ARGUED, AND THE MEASUREMENT FOUND A SECOND THING: on a 60-window run at the
    # shipped defaults, w.world_proj.weight.grad is None on the way out -- loss_terms ran 60 times
    # and never touched it, so before this body existed world_proj had never received a gradient
    # from anything at all. THE SAME RUN SHOWED THE LARGER HOLE AND IT IS NOW CLOSED, ONE
    # LINE OF THIS FILE AWAY:
    # max|delta| over 60 windows was exactly 0.0 for encoder, qproj, preds AND keys while their
    # .grad was nonzero (the encoder's first weight accumulated a gradient sum of 19.5) -- WORLD's
    # tensors took gradient and were never STEPPED, because spine/compose.py::_base_parameters
    # harvests each object by `getattr(obj, "parameters", None)` and this package's World class had
    # no such method. World.parameters() supplies it, the startup warning that said so is gone, and
    # the same 60 windows now move preds by 7.955e-02 and the encoder by 8.08e-02.
    # WHAT THAT MEANS FOR THE PARAGRAPH ABOVE: the gradient this return carries is now the ONLY one
    # world_proj receives AND the only one it is missing, since every other tensor here is fed by
    # loss_terms. It is the one tensor that still measures exactly 0.0 over those 60 windows, for
    # the plain reason that nothing calls this function.
    # THE ENCODER AND THE POPULATION TAKE GRADIENT FROM THE LM LOSS THROUGH THIS PATH TOO, which is
    # a real coupling and not a side effect: `feedback` on means the latent is shaped by what makes
    # the language model better as well as by what predicts the latent forward, and that is the
    # difference between a side head and a subsystem. It is also why the off arm above returns
    # before the encoder runs at all rather than after -- an unread forward would still build a
    # graph on the world model's parameters and still be paid for on the backward.
    with torch.no_grad():
        # THE MAGNITUDE OF WHAT IS ACTUALLY ADDED, AS A GAUGE. A fire counter cannot distinguish a
        # forecast that conditions the LM from one that is numerically absent, and the collapsed
        # latent is the state this subsystem has been in for every reading ever taken of it
        # (world/levers.py carries them) -- which is exactly the state in which world_proj's output
        # goes small. Measured on a fresh build the term is 7.5% of the hidden state's own RMS and
        # after 60 windows 0.4%, so the number moves and is worth printing. Read off the tensor
        # that leaves this function, detached, so the reading cannot hold the graph open past the
        # return.
        w.counters["world.forecast_rms"] = round(float(out.detach().pow(2).mean().sqrt()), 6)
    # THE FIRE COUNTER, WRITTEN WHERE THE FORECAST IS PRODUCED. It counts what this package can
    # honestly count -- forecasts RETURNED -- and its DID IT FIRE line says APPLIED, which is one
    # package away: lm.encode.extra_applied is the other half and the two must agree flush for
    # flush. A gap between them is a composition root that computed a forecast and dropped it, and
    # no counter inside WORLD can see that -- which is why the pair is named here rather than left
    # to whoever reads the report. TODAY BOTH READ ABSENT: nothing calls this function, so the
    # honest statement is "never reached", not "reached and worth 0".
    w.counters["world.forecasts"] = w.counters.get("world.forecasts", 0) + 1
    return out


def manage(world: Config, w, *, latent, plateau, add_param_group):
    """Selection on the dynamics population, ON THE WINDOWS CADENCE. Returns ManageResult.

    THE CADENCE IS WINDOWS AND MUST NOT BE FAB.d_manage_period. :6768 tests
    `step % MANAGE_EVERY == 0` ABOVE the batch early-out, so it is evaluated on every window and
    `step` advances per WINDOW -- CENSUS.md:218 agrees. The ledger publishes the same field as
    FAB.d_manage_period in FLUSHES with a `why` that says the block sits BELOW the early-out, which
    is true of :6961/:6988/:7077/:7325 and FALSE of this one. Handing WORLD the Flushes wire is a
    16x error at BATCH_W=16, the same class as pin_tick. THE COMPOSITION ROOT evaluates the gate
    with FAB.manage_every through RUN's Windows-typed Cadences and calls this function only when it
    fires; no period enters WORLD's Config (FOR THE OWNER Q-WORLD-6).

    THREE PLUMBING DEFECTS, NONE IN THE MECHANISM, ALL FIXED HERE:
      C6  -- grow() appends a predictor and NEVER INITIALISES ITS `mass` (a zeros buffer sized
             nmax), and soft_cull runs in the SAME block immediately afterwards (:6772)
             deactivating anything with mass < 1e-3. The newborn is culled microseconds after it
             is minted, and the DID IT FIRE row counts the mint.
      M70 -- `if s.n() >= s.nmax` counts TOTAL predictors, not LIVE ones, so once soft_cull has
             deactivated k the population stalls at nmax with nmax-k working and the plateau
             trigger silently stops firing. THE CAP IS ON LIVE PREDICTORS, AND THE MINT CLAIMS A
             DEAD SLOT -- Q-WORLD-8, RESOLVED 2026-09-02 (b). "Count live and append" is NOT
             implementable and that is why the literal reading of the recommendation had to be
             refused: fit, mass and alive are buffers of width nmax (world_model.py:81-83) and
             grow() does `s.preds.append(...)`, so appending while comparing LIVE against nmax
             drives n() past nmax and update_fitness's `for i in range(s.n())` indexes past the end
             of every one of them -- besides unbounded forward compute and a checkpoint whose n
             exceeds its own nmax, which geometry and load_into exist to refuse. Slot reuse is the
             only implementation the fixed-width buffers admit, AND THE FROZEN DID IT FIRE ROW
             ALREADY DEMANDS IT: `blocked_reason` is one of {grow_off, at_live_cap, no_plateau,
             cooldown, null_world} -- `at_live_cap` and no `at_total_cap`, so a grow() that refuses
             because n() == nmax while live < nmax has NO LEGAL REASON TO REPORT. A mint therefore
             takes the LOWEST DEAD SLOT: clone the fittest into it, reset that slot's fit and mass,
             set alive = 1. n() never exceeds nmax and never narrows; `live` is the number that
             varies. Count reused-slot mints SEPARATELY from fresh ones (n_slots_reused beside
             `grown`), because "minting and culling at the cap indefinitely" is then a number the
             report states rather than a hypothesis the design has to pre-empt.
      M71 -- `grown` is a plain int (world_model.py:75), absent from state_dict, restarting at 0 on
             every resume WHILE the resume's grow-replay loop increments it, so the DID IT FIRE row
             reports THE CHECKPOINT'S POPULATION SIZE as this run's growth events. It becomes a
             buffer.
      L72 -- grow()'s seed key is the BATCH CENTROID (:6770), not the mispredicted region its
             docstring names. A predictor cloned toward the average of the batch is not
             specialising on anything.
      M69 -- soft_cull is IRREVERSIBLE despite both docstrings calling it reversible: `alive` is
             only ever written to 0.0 (:127) and nothing restores it. THIS CONTRACT FIXES M70 ONLY
             and removes the reversibility claim from the docstrings -- fixing both would let the
             population oscillate at the cap indefinitely, minting and culling (Q-WORLD-8).
             STILL ONE-WAY IN THE SENSE THAT MATTERS, and the "reversible: params kept" claim is
             DELETED from world_model.py:83 and :121 in the port: a culled predictor's LEARNING is
             never restored. Resurrection (alive back to 1.0) is refused for a stronger reason than
             oscillation -- a resurrected predictor's `mass` is BY DEFINITION below min_mass, so it
             is culled again on the next pass unless something else changed, which is a mechanism
             that cannot work rather than one that works badly. Slot reuse overwrites the slot, and
             that is also what the plasticity literature does (ReDo reinitialises dormant units;
             continual backprop reinitialises the least-used ones) -- nothing there restores a dead
             unit.
             AND THE COMPUTE COST ACTUALLY STOPS BEING PAID. A DEAD PREDICTOR IS SKIPPED IN THE
             FORWARD, not merely down-weighted: world_model.py:92-94 stacks EVERY predictor's output
             and :88 holds the dead ones down with log(alive.clamp_min(1e-6)), so a culled predictor
             ran and took gradient every step for about 1e-6 of the routing mass. A hard penalty is
             a skip, and this is the half of "the honest repair is a hard routing penalty, not
             resurrection" that a docstring change alone does not deliver.
             C6 RIDES WITH IT AND MUST: mass initialised on birth, or a newborn -- fresh or reused --
             is culled by the soft_cull in the same block microseconds later, which turns slot reuse
             into pure churn. The plateau predicate and the 4 x MANAGE_EVERY cooldown bound the mint
             rate and both become Gates printing their own arithmetic.

    add_param_group is OPT's optimizer.add_param_group, passed as a callable, because growth mints
    parameters mid-run and the optimizer must learn about them (:6771).

    LEVERS READ: grow, nmax
    WIRES READ: none
    DID IT FIRE: ManageResult(grow_attempted, grown, soft_culled, live, blocked_reason) where
                 blocked_reason is one of {grow_off, at_live_cap, no_plateau, cooldown, null_world};
                 `grown` is a BUFFER so the counter survives a resume and is not inflated by the
                 replay; ManageResult.live vs n() is the number that says whether the population
                 has silently become mostly dead
    """
    world = world.owned_by("WORLD")
    raise NotImplementedError(
        "WORLD.manage: P4 (world) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section WORLD.")


def geometry(world: Config, w):
    """Every field a resume must match, with its rule: lat/hid/route_d EXACT, nmax MAY_WIDEN, n
    (the grown population) MAY_WIDEN AND MAY_NARROW, feedback EXACT.

    `n` IS THE ALLOCATED PREDICTOR COUNT -- len(preds), the number of ForwardModels that EXIST -- AND
    NEVER THE LIVE COUNT. Stated because Q-WORLD-8 (b) makes the two diverge and M70 is the record of
    them being confused: under slot reuse n() rises to nmax and then stops, while `live` (the alive
    mask's sum) moves in both directions as culls and reused-slot mints happen. n is what decides
    WHICH TENSORS EXIST in the checkpoint, so n is the geometry field and it keeps its MAY_WIDEN AND
    MAY_NARROW rule -- the live count is a ManageResult reading and a state_dict buffer, not a shape,
    and putting it here would make a resume refuse on a number that says nothing about tensor extent.
    n <= nmax is an INVARIANT under (b) and load_into may assert it; before (b) it was not one.

    H22: lat, hid, n, nmax, route and feedback are all recorded into world_cfg at :5365-5366 and
    the resume reads ONLY world_cfg["n"] (:4590), so changing any other across a resume dies inside
    torch on a shape mismatch naming no knob -- the exact failure the fabric's refusal at
    :4413-4468 exists to replace. The bounded refusal at :4593-4598 must stop saying "resume with
    WORLD_MODEL=0": that name no longer exists and unread_env() would report it as a typo. It says
    WORLD_ENABLED=0.

    LEVERS READ: lat, hid, route_d, nmax, n0, feedback
    WIRES READ: none
    DID IT FIRE: the RECORDED side of the resume gate's comparison -- NOT the live manifest
                 check_geometry consumes, which is spine/compose.py's _geometry_manifest and which
                 deliberately holds NO population count at all, because it must run before anything
                 is built and n needs a built world. Corrected 2026-09-02 with Q-WORLD-8: the old
                 wording here said "the manifest CKPT.check_geometry consumes" and that is the same
                 conflation compose.py's own row note had to be corrected for. What this returns is
                 the overlay that supplies `world.n`; a field present in the checkpoint and absent
                 from the live manifest is reported UNCHECKED and is then re-refused, in both
                 directions, by WORLD.load_into (M43)
    """
    world = world.owned_by("WORLD")
    # THE ONE geometry() IN THE TREE, AND IT IS ON THE SAVE SIDE ON PURPOSE. Every other field in
    # the manifest is assembled by the composition root from frozen Configs BEFORE the first
    # allocation, because that is when the geometry gate has to fire; this one needs a BUILT object,
    # since what it contributes is the GROWN population count. CKPT.check_geometry records it and
    # reports it UNCHECKED rather than comparing it, which is the honest placement.
    #
    # `n` IS THE ALLOCATED PREDICTOR COUNT -- len(preds), the ForwardModels that EXIST -- AND NEVER
    # THE LIVE COUNT. M70 is the record of the two being confused: under slot reuse n() rises to
    # nmax and stops, while `live` (the alive mask's sum) moves in BOTH directions as culls and
    # reused-slot mints happen. n is what decides WHICH TENSORS EXIST in the checkpoint, so n is the
    # geometry field; the live count is a ManageResult reading and a state_dict buffer, not a shape,
    # and putting it here would make a resume refuse on a number that says nothing about extent.
    #
    # H22 IS WHY EVERY FIELD IS HERE AND NOT JUST `n`. lat, hid, n, nmax, route and feedback were
    # all recorded into world_cfg at :5365-5366 and the resume read ONLY world_cfg["n"] (:4590), so
    # changing any other across a resume died inside torch on a shape mismatch naming no knob --
    # the exact failure the fabric's refusal exists to replace. Recording six and checking one is
    # the state CKPT.check_geometry reports as UNCHECKED; naming them all here is what lets it.
    if not w._is_live():
        # AN EMPTY GEOMETRY, WHICH IS WHAT THE CLASS DOCSTRING PROMISES AND WHAT THIS FUNCTION DID
        # NOT DO. World's own first paragraph says the null world answers every method with the
        # inert answer -- "zero loss terms, no forecast, an empty manage result, an empty geometry"
        # -- and the body below dereferences w.keys.shape, which is None at WORLD_ENABLED=0. So the
        # documented ablation arm CRASHED: AttributeError from inside the report path, after the
        # corpus, the vocabulary and the whole run had been paid for.
        # NOTHING COULD HAVE CAUGHT IT UNTIL SEPTEMBER, because nothing called this function
        # (Q-CKPT-1, and the paragraph below says so at length). Wiring geometry into _save and into
        # run.py's manifest is what made WORLD_ENABLED=0 reachable enough to fail, which is the
        # same order of events as every other repair in this file: the call site comes first and
        # the defect it exposes is the point of having one.
        # WHAT {} MEANS DOWNSTREAM, and it is a reading rather than a hole: these six keys are
        # merged into the recorded manifest, so a null world simply does not contribute them, and
        # CKPT.check_geometry compares KEY SETS -- a parent that recorded world.* against a child
        # that records none is a difference the gate can see. The one it cannot see is caught one
        # row over, by world/api.py::load_into's own WORLD_ENABLED refusal.
        return {}
    return {
        "world.lat": (int(w.lat), "EXACT", "WORLD_LAT", "the latent width every predictor maps into"),
        "world.route_d": (int(w.keys.shape[1]), "EXACT", "WORLD_ROUTE_D",
                          "the routing key width; qproj projects into it"),
        # THE ENCODER'S HIDDEN WIDTH, AND THIS LINE READ `w.preds.shape[-1]` UNTIL 2026-09-21,
        # WHICH IS `lat`. WORLD_HID is spent in exactly one place -- build's
        # `nn.Sequential(nn.Linear(d_model, hid), nn.Tanh(), nn.Linear(hid, lat))` -- and `preds`
        # is (n, lat, lat), carrying no hid axis at all. So this field reported 32 where the lever
        # said 128 at the shipped defaults: a RECORDED GEOMETRY FIELD THAT NAMED ONE QUANTITY AND
        # CARRIED ANOTHER, under an EXACT rule, inside the instrument that decides whether a resume
        # is allowed to happen.
        # NOTHING COULD HAVE CAUGHT IT BECAUSE NOTHING CALLED THIS FUNCTION. It is the only
        # geometry() in the tree (Q-CKPT-1) and spine/loop.py::_save did not invoke it until the
        # same day, so the wrong number had never been compared against anything. The first
        # comparison ever made refused a legitimate resume by name -- "WORLD_HID: the checkpoint was
        # written at world.hid=32 and this run resolves 128" -- which is the good outcome: a loud
        # refusal on the first call rather than a quiet acceptance on the thousandth.
        # READ OFF THE MODULE THE LEVER BUILT, so a change to the encoder's shape moves this with
        # it and the two cannot drift again.
        "world.hid": (int(w.encoder[0].out_features), "EXACT", "WORLD_HID",
                      "the encoder's hidden width -- Linear(d_model, hid) then Linear(hid, lat); "
                      "an inner dimension with no valid prefix"),
        "world.n": (int(w.preds.shape[0]), "MAY_WIDEN_AND_MAY_NARROW", "WORLD_N0",
                    "the ALLOCATED predictor count, len(preds) -- never the live count (M70)"),
        "world.nmax": (int(w.nmax), "MAY_WIDEN", "WORLD_NMAX",
                       "the ceiling n may grow to; n <= nmax is an invariant under Q-WORLD-8 (b)"),
        "world.feedback": (bool(w.feedback), "EXACT", "WORLD_FEEDBACK",
                           "whether the forecast is fed back into the LM's hidden state"),
    }


def state_dict(world: Config, w):
    """The encoder, the population (preds, keys, qproj), the buffers fit/mass/alive/`grown`,
    world_proj, and the loop-side plateau state (_wl_ema, _wl_lastgrow) which MOVES INSIDE THIS
    PACKAGE.

    _wl_ema in particular, for the same reason FAB's growth EMAs must travel: an EMA seeded from
    the first loss on the NEW material cannot detect the arrival of a new area, which is the one
    moment continual learning has a signal.

    LEVERS READ: none
    WIRES READ: none
    DID IT FIRE: world.state_written
    """
    world = world.owned_by("WORLD")
    def _t(x):
        return None if x is None else x.detach().cpu().clone()
    out = {
        "encoder": w.encoder.state_dict() if hasattr(w.encoder, "state_dict") else None,
        "qproj": w.qproj.state_dict() if hasattr(w.qproj, "state_dict") else None,
        "world_proj": w.world_proj.state_dict() if hasattr(w.world_proj, "state_dict") else None,
        # THE POPULATION. preds and keys are Parameters and travel as tensors rather than through a
        # module's state_dict, because they are not owned by one -- they are the population itself.
        "preds": _t(w.preds), "keys": _t(w.keys),
        # THE BUFFERS, AND `alive` IS THE LOAD-BEARING ONE. WORLD.load_into's contract says it may
        # not be re-derived on the other side: a resume that rebuilt `alive` from anything else
        # would silently resurrect culled predictors.
        "fit": _t(w.fit), "mass": _t(w.mass), "alive": _t(w.alive), "grown": _t(w.grown),
        "n_live": int(w.n_live), "nmax": int(w.nmax),
        # THE LOOP-SIDE PLATEAU STATE, WHICH MOVES INSIDE THIS PACKAGE. `_wl_ema` travels for the
        # same reason FAB's growth EMAs must: an EMA seeded from the first loss on the NEW material
        # cannot detect the arrival of a new area, and that arrival is the one moment continual
        # learning has a signal. Seeding it fresh on every resume is the same as not having it.
        "_wl_ema": None if w._wl_ema is None else float(w._wl_ema),
        "_wl_lastgrow": int(w._wl_lastgrow),
        "counters": dict(w.counters),
        "rng": (w.rng._r.getstate(), int(w.rng._draws)) if getattr(w, "rng", None) else None,
    }
    w.counters["world.state_written"] = w.counters.get("world.state_written", 0) + 1
    return out


def load_into(world: Config, w, sd):
    """Symmetric persistence. REFUSES IN BOTH DIRECTIONS on population size (M43): the replay
    `while world_fwd.n() < _want2` (:4591) handles only growth, so a checkpoint with FEWER
    predictors than this run builds falls through to load_state_dict as "Missing key(s)
    preds.N.*".

    THE SIZE IT COMPARES IS THE ALLOCATED COUNT, len(preds), and under Q-WORLD-8 (b) `n <= nmax` is
    an invariant it may assert rather than a hope: a checkpoint whose n exceeds this run's nmax is
    refused NAMING WORLD_NMAX (the old tree spun the replay loop forever there, because grow()
    returns None without appending at capacity). The `alive` mask travels in state_dict, so which
    slots are dead is restored with the parameters and is NOT re-derived here -- a resume that
    rebuilt `alive` from anything else would silently resurrect culled predictors, which is exactly
    what (b) refuses to do on purpose.

    LEVERS READ: n0, nmax
    WIRES READ: none
    DID IT FIRE: world.state_restored, world.state_refused
    """
    world = world.owned_by("WORLD")

    def _refuse(reason):
        w.counters["world.state_refused"] = w.counters.get("world.state_refused", 0) + 1
        raise LeverError(reason)

    if not sd:
        return w
    # THE TWO NULL ARMS, BEFORE ANY SHAPE IS READ. `sd` is TRUTHY on a null world -- state_dict
    # returns a dict of Nones, not an empty one -- so the test above does not cover either of them,
    # and `live_alloc = int(w.preds.shape[0])` below is an AttributeError at WORLD_ENABLED=0.
    # A NULL CHILD RESUMING A TRAINED PARENT IS REFUSED, NAMING THE LEVER. It is not a load that
    # has nothing to do: the parent's every step was taken against an objective that included
    # `predict_w * pop_loss + collapse_w * (...)`, reaching the language model through an
    # undetached obs_emb, and a child without those terms is optimising a different function.
    # Continuing across that boundary and calling it one run is the measurement defect this whole
    # package is organised against -- and turning the world model OFF is a legitimate thing to
    # want, which is why the refusal names WORLD_ENABLED and says to start a fresh run.
    if not w._is_live():
        if sd.get("preds") is not None:
            _refuse(
                f"WORLD_ENABLED=0: the checkpoint holds a trained world model "
                f"({int(sd['preds'].shape[0])} predictor(s)) and this run built a NULL world, so "
                f"there is nothing here to load it into. Refused rather than skipped: the parent "
                f"trained against an objective containing the world terms and this run's does not, "
                f"so resuming would continue a different optimisation under the parent's name. To "
                f"ablate the world model, start a fresh run at WORLD_ENABLED=0.")
        return w
    # AND THE OTHER DIRECTION, NAMED THE SAME WAY. Without this the refusal below fires on
    # WORLD_N0/WORLD_NMAX and reports "the checkpoint allocates 0 predictors" -- true, and no help
    # at all to an operator who turned WORLD_ENABLED back on between two runs.
    if sd.get("preds") is None:
        _refuse(
            f"WORLD_ENABLED: the checkpoint was written by a run with NO world model and this run "
            f"builds {int(w.preds.shape[0])} predictor(s). There is nothing in the blob to restore "
            f"them from, and a silently random world model trained against a resumed language "
            f"model is the state world/api.py::World.parameters was added to end.")
    # THE SIZE COMPARED IS THE ALLOCATED COUNT, len(preds), NOT n_live. Under Q-WORLD-8 (b)
    # `n <= nmax` is an invariant this may assert rather than hope for.
    saved_alloc = 0 if sd.get("preds") is None else int(sd["preds"].shape[0])
    live_alloc = int(w.preds.shape[0])
    if saved_alloc > int(w.nmax):
        # THE OLD TREE SPUN THE REPLAY LOOP FOREVER HERE, because grow() returns None without
        # appending at capacity, so `while world_fwd.n() < _want2` never terminated. Named against
        # the lever an operator can actually move.
        _refuse(f"WORLD_NMAX: the checkpoint holds {saved_alloc} predictors and this run allocates "
                f"at most {int(w.nmax)}. Raise WORLD_NMAX to {saved_alloc} or more, or start a new "
                f"run -- a replay loop cannot grow past its own ceiling and the old tree spun "
                f"forever trying.")
    if saved_alloc != live_alloc:
        # REFUSED IN BOTH DIRECTIONS (M43). The replay `while world_fwd.n() < _want2` (:4591)
        # handles only GROWTH, so a checkpoint with FEWER predictors than this run builds fell
        # through to load_state_dict as "Missing key(s) preds.N.*" -- a torch error about a key
        # name, for a configuration difference an operator could have been told about by name.
        _refuse(f"WORLD_N0/WORLD_NMAX: the checkpoint allocates {saved_alloc} predictors and this "
                f"run allocates {live_alloc}. Both directions are refused: growth is a replay this "
                f"function does not perform, and shrinkage would drop trained predictors whose "
                f"slots other saved tensors still index.")

    if sd.get("encoder") is not None and hasattr(w.encoder, "load_state_dict"):
        w.encoder.load_state_dict(sd["encoder"])
    if sd.get("qproj") is not None and hasattr(w.qproj, "load_state_dict"):
        w.qproj.load_state_dict(sd["qproj"])
    if sd.get("world_proj") is not None and hasattr(w.world_proj, "load_state_dict"):
        w.world_proj.load_state_dict(sd["world_proj"])
    with torch.no_grad():
        for field in ("preds", "keys"):
            if sd.get(field) is not None:
                getattr(w, field).copy_(sd[field].to(getattr(w, field).device))
    for field in ("fit", "mass", "alive", "grown"):
        if sd.get(field) is not None:
            getattr(w, field).copy_(sd[field].to(getattr(w, field).device))
    w.n_live = int(sd.get("n_live", w.n_live))
    w._wl_ema = sd.get("_wl_ema")
    w._wl_lastgrow = int(sd.get("_wl_lastgrow", 0))
    if sd.get("counters"):
        w.counters.update(sd["counters"])
    if sd.get("rng") and getattr(w, "rng", None) is not None:
        state, draws = sd["rng"]
        w.rng._r.setstate(state)
        w.rng._draws = int(draws)
    w.counters["world.state_restored"] = w.counters.get("world.state_restored", 0) + 1
    return w


def startup_refusals(world: Config, *, ctx_tokens):
    """Returns a list of refusal strings.

    (1) world.horizon >= ctx_tokens empties BOTH slices and produces a loss of nan rather than an
        error; the bound belongs to LM (`ctx`, the census's WIN) so it cannot be a choices= list,
        and ctx_tokens arrives as an argument.
    (2) world.horizon == 0: `max(1, _i("WORLD_K", 1))` at :4144 SILENTLY REWROTE IT to 1 so the
        banner printed a value the run did not use -- a refusal naming the lever, not a silent
        repair.

    LEVERS READ: horizon, enabled
    WIRES READ: none
    DID IT FIRE: the returned list; an empty list is a positive result and is printed as one
    """
    world = world.owned_by("WORLD")
    if not bool(world.enabled):
        # THE NULL WORLD IS A LEGAL CONFIGURATION (the class docstring's D4 repair), and both
        # refusals below are about the LIVE loss slices -- build() never computes them on the
        # disabled arm (`if not bool(world.enabled): return World(built="null", ...)`), so a horizon
        # value that would nan a live run's loss cannot nan a run that never builds one. Without
        # this early return, a stale WORLD_HORIZON left over in an operator's environment refused a
        # run that was never going to use it: reproduced with WORLD_ENABLED=0, WORLD_HORIZON=0 and
        # again with WORLD_ENABLED=0, WORLD_HORIZON=999 against ctx_tokens=64 -- both raised on a
        # nan-loss reason that only the live arm can ever reach.
        return []
    out = []
    horizon = int(world.horizon)
    if horizon == 0:
        # Same shape as RUN_EPOCHS=0: `max(1, _i("WORLD_K", 1))` rewrote it to 1 and the banner
        # printed the value the operator typed, not the one the run used.
        out.append("WORLD_HORIZON=0: refused rather than silently rewritten to 1, which is what the "
                   "old `max(1, ...)` did while the banner kept printing 0.")
    elif horizon >= int(ctx_tokens):
        # BOTH SLICES EMPTY. The prediction target is the window shifted by the horizon, so a
        # horizon at or past the context length leaves nothing on either side and the loss comes
        # out nan -- a number, not an error, which is the failure mode this refusal exists for.
        out.append(f"WORLD_HORIZON={horizon} is not below LM_CTX={int(ctx_tokens)}: the input and "
                   f"target slices are both empty and the world loss is nan rather than an error. "
                   f"The bound is LM's context length and arrives here as an argument, because a "
                   f"choices= list cannot name another package's lever.")
    return out
