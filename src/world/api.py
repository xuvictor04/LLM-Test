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
  WorldStep     loss, latent, inv, latent_std
  ManageResult  grow_attempted, grown, soft_culled, live, blocked_reason
"""
from spine.lever import Config


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

    LEVERS READ: enabled, lat, hid, route_d, n0, nmax, feedback
    WIRES READ: none
    DID IT FIRE: World.built ("live" | "null"), and the constructed shape as a record
    """
    world = world.owned_by("WORLD")
    raise NotImplementedError(
        "WORLD.build: P4 (world) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section WORLD.")


def loss_terms(world: Config, w, obs_emb):
    """The two terms this subsystem adds to the training loss. Called once per FLUSH.

    obs_emb is LM's EMBEDDING of the batch, (B, W, d_model) -- an ARGUMENT, because the encoder
    reads OBSERVATION embeddings (the lowest layer, the point where a new sense plugs in) and not
    the GRU state. Returns WorldStep(loss, latent, inv, latent_std).

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
    raise NotImplementedError(
        "WORLD.loss_terms: P4 (world) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section WORLD.")


def forecast(world: Config, w, obs_emb):
    """The forecast the LM's hidden state is conditioned on: world_proj(pop(z)). None when
    `feedback` is off, and None on the null world.

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
    """
    world = world.owned_by("WORLD")
    raise NotImplementedError(
        "WORLD.forecast: P4 (world) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section WORLD.")


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
             trigger silently stops firing. Count LIVE.
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

    H22: lat, hid, n, nmax, route and feedback are all recorded into world_cfg at :5365-5366 and
    the resume reads ONLY world_cfg["n"] (:4590), so changing any other across a resume dies inside
    torch on a shape mismatch naming no knob -- the exact failure the fabric's refusal at
    :4413-4468 exists to replace. The bounded refusal at :4593-4598 must stop saying "resume with
    WORLD_MODEL=0": that name no longer exists and unread_env() would report it as a typo. It says
    WORLD_ENABLED=0.

    LEVERS READ: lat, hid, route_d, nmax, n0, feedback
    WIRES READ: none
    DID IT FIRE: the manifest CKPT.check_geometry consumes; a field present in the checkpoint and
                 absent here is reported as UNCHECKED
    """
    world = world.owned_by("WORLD")
    raise NotImplementedError(
        "WORLD.geometry: P4 (world) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section WORLD.")


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
    raise NotImplementedError(
        "WORLD.state_dict: P4 (world) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section WORLD.")


def load_into(world: Config, w, sd):
    """Symmetric persistence. REFUSES IN BOTH DIRECTIONS on population size (M43): the replay
    `while world_fwd.n() < _want2` (:4591) handles only growth, so a checkpoint with FEWER
    predictors than this run builds falls through to load_state_dict as "Missing key(s)
    preds.N.*".

    LEVERS READ: n0, nmax
    WIRES READ: none
    DID IT FIRE: world.state_restored, world.state_refused
    """
    world = world.owned_by("WORLD")
    raise NotImplementedError(
        "WORLD.load_into: P4 (world) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section WORLD.")


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
    raise NotImplementedError(
        "WORLD.startup_refusals: P4 (world) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section WORLD.")
