"""WORLD -- the world model: a latent state for the observed stream, and a population that predicts it forward.

WHAT THIS PACKAGE OWNS. One encoder that maps observation embeddings to a low-dimensional latent, one
routed population of forward-dynamics predictors that learns how that latent EVOLVES, two weights on the
terms those two add to the training loss, and the switch that decides whether the forecast conditions the
base LM or sits beside it as an unused side head. It owns no data, no tokenizer, no cadence and no
instrument. Eleven knobs, all eleven filed under the old tree's `world` family, and -- unusually for this
census -- not one of them moved packages: the subsystem was already a subsystem, it just had no owner.

WHY IT IS HERE AT ALL, stated against the two definitive goals rather than against enthusiasm.

  GOAL A IS LANGUAGE PRODUCTION, and the only thing in this package that touches goal A is `feedback`.
  With it on, the LM's hidden state is conditioned on where the world model predicts the stream is going
  (h += world_proj(forecast)); with it off the whole subsystem is a costed side head that changes no
  token the model emits. The archive names that absence as THE KEY GAP, which is why the switch is a
  declared lever and not an implementation detail.

  "ROOM FOR ADDITIONAL MODALITIES" IS THE STRUCTURAL ARGUMENT FOR THE REST. The encoder reads OBSERVATION
  EMBEDDINGS -- the lowest layer, the point where a new sense plugs in -- and learns dynamics in a latent
  space that knows nothing about tokens. A second modality needs new rows in LM's embedding and nothing
  new here. That is the claim; it is a claim, not a measurement, and the file says so below.

  GOAL B IS SERVED ONLY INDIRECTLY, through the same growth-and-selection primitive the fabric uses:
  `n0`/`nmax`/`grow` are a population that can add a predictor for material it cannot yet predict instead
  of overwriting one that already works. The primitive is shared with FAB on purpose and the names are
  kept parallel (WORLD_N0 beside FAB_N0) so the two can be compared.

D4 AND THE HONEST PRICE. D4 says this package STAYS and that OFF must be a first-class configuration.
Both halves are load-bearing and the second one is the one the old tree failed. The record against the
subsystem is severe and it is recorded here rather than buried: 413 full-stack readings, ZERO with a
positive beat against a persistence baseline, beats ranging -13.6% to -94.2%, and a latent standard
deviation that never once exceeded 0.15 against the code's own "want ~1" bar. That is not a reason to
delete it, because all 413 readings are smoke/equivalence scale (d96, stream 120000, 1875 steps), and a
collapsed latent is exactly what an undertrained encoder looks like -- the broken-instrument case, not the
superfluous case. It IS a reason that `enabled` must be a configuration a run can actually take, so the
ablation that prices the subsystem can be run by someone who did not write it. In the old tree it could
not be: WORLD_GROW defaults ON and its step hook calls world_fwd.n() OUTSIDE the `if WORLD_MODEL:` block
(self_organize.py:6768 against :4156, where world_fwd is None), so WORLD_MODEL=0 died on None at the first
MANAGE_EVERY. The ab_no_world arm of the rerun exited 1 with a traceback and produced no data. The one
ablation that would have told us what this package is worth was the one ablation that could not run.

-------------------------------------------------------------------------------------------------
WHAT WAS EMITTED, AND WHAT WAS NOT
-------------------------------------------------------------------------------------------------
The census (.rework/census.json, filtered on new_owner == "WORLD") files 11 of its 328 rows here. This
file emits 11 levers:

     6  rows with verdict keep    (grow, hid, lat, n0, nmax, feedback)
  +  5  rows with verdict rename  (enabled, horizon, route_d, collapse_w, predict_w)
  -------
    11  Lever declarations, all reachable as WORLD_<FIELD>

Not emitted, by verdict: none. WORLD is the only package in the census with no drop, no merge and no
promote-to-wire row, so CENSUS.md:39's "WORLD 11" and the eleven declarations below are the same eleven
names -- which is worth stating, because for every sibling package those two numbers differ and a reader
who has just come from src/fabric/levers.py (110 rows, 82 declarations) will be expecting a subtraction.

-------------------------------------------------------------------------------------------------
THE THREE CENSUS DEFECTS, AS THEY LAND HERE
-------------------------------------------------------------------------------------------------
1. DOUBLED ENVIRONMENT NAMES -- 11 rows corrected, i.e. every row this package owns, silently, because
   the correction is mechanical. The census records each target as `WORLD.WORLD_ENABLED`: the prefix in
   one column and the prefix REPEATED inside the name in the next (CENSUS.md:371-381). spine/lever.py
   generates the environment name as f"{PREFIX}_{FIELD.upper()}", so taking those rows literally would
   declare a field named `WORLD_ENABLED` answering to `WORLD_WORLD_ENABLED` -- a name no operator has
   ever set, on a lever that would therefore run at its declared default forever while
   registry.unread_env() reported the operator's real WORLD_ENABLED as a typo. Every row is read as
   PREFIX + FIELD: the field is `enabled`, the environment name is WORLD_ENABLED. Unlike FAB, where two
   rows already named a bare field and so proved the doubling was clerical, all eleven WORLD rows are
   doubled; the evidence that it is a slip rather than a decision is the sibling packages' rows, not
   anything in this section of the census.

2. CLOCK KINDS -- 0 rows corrected here, because no WORLD row carries a clock unit at all (3 FLAG,
   5 COUNT, 1 TOKENS, 2 FRACTION). The clock defect this package has is on the INCOMING side, it is real,
   and it is named rather than resolved because resolving it means editing spine/assemble.py:

     CONFLICT, NOT RESOLVED. The world-model growth block fires on FAB's MANAGE_EVERY cadence
     (self_organize.py:6768). That test is `step % MANAGE_EVERY == 0` and it sits ABOVE the batch
     early-out at :6795-6796 (`if len(_bx) < BATCH_W: i += WIN; step += 1; continue`), so it is evaluated
     on EVERY window and `step` advances once per WINDOW -- the cadence is WINDOWS on this path, which is
     what CENSUS.md:218 says the unit is. spine/assemble.py:686 wraps the same field as
     `derive.flush_period(Steps(r["FAB"].manage_every), r["TRAIN"].batch_w)` and publishes it as
     FAB.d_manage_period in FLUSHES, whose `why` states the block "sits below the batch early-out". Both
     are true of DIFFERENT call sites: the sites below the early-out (:6961, :6988, :7077, :7325) gate on
     `_nbwd % max(1, MANAGE_EVERY // BATCH_W)` and really are per-flush, while :6764 and :6768 are
     per-window. One field, two clock kinds in one program, which is the exact defect units.py exists to
     make impossible. The consequence for this package is concrete: WORLD must NOT be handed
     d_manage_period (Flushes) for its growth hook -- at BATCH_W=16 that is a 16x error in when growth is
     allowed to fire, the same shape as the pin_tick and GROW_CAP_EVERY failures. It needs a
     Windows-denominated wire of its own. Naming the two kinds is this file's job; declaring the wire is
     spine/assemble.py's, and picking one kind silently would hide a disagreement two files are currently
     having in writing. See the note on `grow` below.

3. UNRESOLVED MERGES -- none. No census row merges into a WORLD lever and no WORLD row merges away, so
   there is nothing here to invent and nothing to leave dangling.

-------------------------------------------------------------------------------------------------
choices=, AND WHY THIS FILE HAS NONE
-------------------------------------------------------------------------------------------------
The survey found eleven knobs (SIG_MODE, EVICT, CULL_MODE, LR_SCHED, KEY_SRC, CHAIN_ROUTE and the rest,
ISSUES M24) where an unrecognised value fell silently into a default branch, so a typo ran a path the
operator did not ask for. Not one of them is a WORLD knob: every lever below is a bool, an int or a
float, and there is no string-valued choice in this package. `choices=` is therefore absent by
arithmetic, not by oversight. The corresponding hazard here is the bool one the house rule already
carries -- see ON/OFF below -- and the int one on `horizon`, which is guarded by a Gate rather than by a
choice list because its legal range depends on a value another package owns.

ON/OFF LEVERS ARE DECLARED True/False, NOT 1/0, matching src/fabric/levers.py. The value is identical
(True == 1) but the declared TYPE selects the coercion branch in Lever.coerce: with a bool default,
WORLD_ENABLED=off means off; with an int default it raises. The bool branch's own hazard is stated once
and applies to all three flags here -- any string outside ("0", "", "off", "no", "none", "false") reads as
True, so WORLD_ENABLED=flase is silently ON. That is the spine's rule for every bool in the tree.

-------------------------------------------------------------------------------------------------
FIVE UNDECLARED CONSTANTS THIS FILE DOES NOT DECLARE, LISTED SO THE PORT DOES NOT INHERIT THEM
-------------------------------------------------------------------------------------------------
L1 says one literal default and no second default anywhere. This package violates it in five places
today, and none of the five has a census row, so none of them can be emitted here without inventing a
lever and a default on no authority. They are listed instead, with the value the run actually used:

    w_cov = 0.04     the covariance half of the anti-collapse term, hard-coded at self_organize.py:7061
                     AND again as a keyword default in world_model.py:55's wm_loss. A second default
                     living inside a declared lever (`collapse_w`), which is precisely the shape L1
                     forbids -- and the product loop never calls wm_loss, so the two copies have never
                     had to agree.
    w_bal = 0.01     the load-balance weight inside pop_loss (world_model.py:131). The product loop calls
                     `pop_loss(world_fwd, _zt, _zn)` at :7060 with no argument, so it runs FLAT for the
                     whole run, while world_model.py's own probe decays it 0.05 -> 0 over 2000 steps
                     (:239) precisely so the population can specialise late. The loop and the probe are
                     optimising different objectives; the probe's evidence therefore does not describe
                     the loop's behaviour.
    min_mass = 1e-3  the soft-cull threshold (world_model.py:121). See `grow`.
    tau = 1.0        the routing temperature (world_model.py:70). The product loop takes the signature
                     default; the probe passes 0.5 and its comment calls that "sharp routing" -- a second
                     axis on which loop and probe differ.
    0.9 / 4x         the plateau predicate and its cooldown, `_winv > 0.9 * _wl_ema` and
                     `step - _wl_lastgrow > 4 * MANAGE_EVERY` (:6769). Two magic numbers deciding whether
                     the growth mechanism is ever allowed to fire, printed nowhere.

THE SIGNATURE DEFAULTS ARE A SIXTH CASE AND THE MOST MISLEADING ONE. world_model.py:70 declares
`DynamicsPopulation(d_lat, n0=2, nmax=8, hid=128, route_dim=32, tau=1.0)` while the product loop passes
3, 6, 128, 24 (:4156). Four of those five numbers differ from the run's, so reading world_model.py alone
tells a reader the wrong population size, the wrong cap and the wrong key width. Each lever below states
the literal the RUN used; the signature numbers are noise from a file that was written to be run
standalone and then imported.

ONE MORE PORTING NOTE, because it made the file look self-gating when it is not: world_model.py's
docstring still claims "WORLD_MODEL=0 by default in the product loop" while _SPEC says 1, and the module
imports os at L74 and never uses it. All gating lives in self_organize.py. Under this spine it lives in
this package, and `from_env` is the only reader of the environment anywhere.
"""
# ABSOLUTE, NOT `from ..spine.lever import ...`. The tree is imported with `src` itself on sys.path --
# tests/test_derive.py:33 does it, and so does this file's own verification command -- which makes
# `world` a TOP-LEVEL package, and a relative import one level above a top-level package is an
# ImportError ("attempted relative import beyond top-level package"), not a fallback. All eight sibling
# packages (fabric, lm, memory, sig, domains, eval, tok, data) spell it exactly this way; two packages
# that spell one import two ways is the kind of difference that decides which of them a runner can load.
from spine.lever import Lever, LeverSet
from spine import units as U


class WORLDLevers(LeverSet):
    """The world model's declared knobs: whether it exists, what shape it is, and what it costs.

    Grouped by the question each one answers -- does the subsystem run, how big is it, how is its
    population managed, what does it add to the loss -- because that is how they fail together. The
    sizing group in particular has never been varied once in the whole recorded history of the project,
    which is the single most important fact about this package and is the reason none of it was dropped.
    """

    PREFIX = "WORLD"

    # ==============================================================================================
    # 1. DOES THE WORLD MODEL EXIST, AND DOES ITS OUTPUT REACH THE LANGUAGE MODEL
    #
    # Two switches, and the difference between them is the difference between a subsystem that is
    # measured and a subsystem that matters. `enabled` builds it; `feedback` puts its forecast in the
    # LM's forward path. Off/on and on/on are two different experiments; the old tree could run neither
    # cleanly, because OFF crashed and ON reached into another package by monkey-patch.
    # ==============================================================================================

    enabled = Lever(True, "Build the world encoder and the dynamics population, and add their terms to "
                          "the training loss; off builds a null world that no other package can "
                          "dereference.", U.FLAG)
    # Census: WORLD_MODEL -> WORLD.WORLD_ENABLED, doubled name corrected to the field `enabled`.
    # Old default `bool(_i("WORLD_MODEL", 1))` at self_organize.py:4144, so the literal is True.
    # RENAMED BECAUSE THE ENV NAME IS GENERATED FROM THE FIELD. `enabled` reads as a switch; `model`
    # reads as a choice of model, and the tree already has MODEL (the LM arm selector, now LM_ARCH),
    # `model_type` in the checkpoint, and `model` the live nn.Module in the same scopes.
    # WHAT OFF HAS TO MEAN NOW, and why it is the whole reason this lever was renamed rather than
    # dropped. OFF was not a configuration in the old tree, it was a crash: `grow` defaults ON and its
    # step hook calls world_fwd.n() outside the `if WORLD_MODEL:` guard (:6768 against :4156, where
    # world_fwd is None), so WORLD_MODEL=0 died on None at the first MANAGE_EVERY and the ab_no_world
    # arm exited 1 with no data. The `and WORLD_MODEL` fold at :4147 is a patch over that shape, not a
    # design -- it makes the EFFECTIVE value of another lever differ from the REQUESTED one, which is
    # why the banner already has to print `world_proj is not None` instead of the env var. Under this
    # spine the package builds a null world object when off, so no foreign block has anything to
    # dereference and the OFF arm cannot rot between the runs that use it.
    # NOT DROPPED DESPITE THE RECORD: 413 full-stack readings, 0 with a positive beat, -13.6% to
    # -94.2%, latent std never above 0.15 against the code's own >0.5 bar -- all at smoke/equivalence
    # scale (d96, stream 120000, 1875 steps), where a collapsed latent is what undertrained looks like.
    # THE COST OF THE RENAME, STATED RATHER THAN DISCOVERED. Every harness line that still sets
    # WORLD_MODEL now sets nothing. It is not silent -- registry.unread_env() names an undeclared
    # WORLD_-prefixed variable at startup -- but it is not a redirection either: run against this file,
    # unread_env("WORLD_MODEL") offers WORLD_HID, WORLD_N0 and WORLD_GROW as its nearest matches,
    # because edit distance does not know that WORLD_ENABLED is the successor. The operator is told the
    # name is dead; they are not told what replaced it. src/fabric/levers.py records the same limit for
    # FAB_NMAX -> FAB_SLOTS, and the two together are the argument for a retired-names table somewhere
    # the typo net can read, not for keeping a name that describes the wrong thing.

    feedback = Lever(True, "Condition the base LM on the forecast (h += world_proj(forecast)) instead "
                           "of leaving the world model as an unused side head.", U.FLAG)
    # Census: WORLD_FEEDBACK, verdict keep; doubled name corrected to the field `feedback`. Old default
    # `bool(_i("WORLD_FEEDBACK", 1))` at :4152 -- True.
    # THIS IS THE LINK TO GOAL A. Off, nothing this package computes changes a single emitted token and
    # the subsystem is pure cost. The archive names its absence as THE KEY GAP.
    # WHAT CHANGES IN THE PORT: the coupling becomes a declared d_ wire into LM. Today it is a
    # monkey-patch -- `model._raw_encode = model.encode` and then model.encode is rebound to a closure
    # (:4158-4169) -- and rewriting another package's forward path has already produced two real
    # defects. (1) The timing probe cleaned up by naming the modules it thought it had touched; that
    # enumeration went stale the day feedback started wrapping encode, so 29 world-model parameters
    # entered the training loop holding gradients computed from a batch of RANDOM TOKENS. Measured:
    # PROBE=1 and PROBE=0 have byte-identical weights, stream and memory entering the loop, split at the
    # second logged step (6.1199 against 6.1125), never rejoin, and end 102 report lines apart. A timing
    # probe decided the run. (2) world_proj had to be added to the checkpoint (:5369) or generation ran
    # a different network than training, which would have invalidated the coherence test.
    # NOT promote-to-wire: the on/off DECISION belongs to this package, only its OUTPUT crosses the
    # boundary. And `_raw_encode` stops existing as a shadow path -- it is kept today only so memory
    # keys stay comparable with what _rekey_amortized re-encodes, which becomes an explicit key-source
    # choice (MEM's KEY_SRC) rather than a hidden second encoder nobody declared.

    # ==============================================================================================
    # 2. THE SHAPE. Three numbers, none of them ever set in the entire recorded history of the project.
    #
    # That is the fact that governs this whole group. The world model has run in exactly ONE shape, and
    # the standing hypothesis for the only failure it has ever shown -- the collapsed latent, std
    # 0.03-0.15 against the code's own "want ~1" -- is that it is a sizing problem nobody has been
    # allowed to test (notes/07_WIP.md:485). Dropping any of these would foreclose the cheapest
    # explanation of that failure. "Never set" is the argument FOR keeping them, not against.
    #
    # ALL THREE ARE CHECKPOINT GEOMETRY THAT IS WRITTEN AND NEVER CHECKED (H22). lat, hid, n, nmax,
    # route and feedback are all recorded into world_cfg at :5365-5366, and the resume reads only
    # world_cfg["n"] (:4590). Change any of the others across a resume and load_state_dict dies inside
    # torch on a shape mismatch naming no knob -- the exact failure the fabric's geometry refusal at
    # :4413-4462 exists to replace. The new gate must name every field below.
    # ==============================================================================================

    lat = Lever(32, "Width of the shared latent world-state the encoder produces and every dynamics "
                    "predictor operates in.", U.COUNT)
    # Census: WORLD_LAT, verdict keep (the name is already clear); doubled name corrected to `lat`.
    # Old default `_i("WORLD_LAT", 32)` at :4144.
    # Structural everywhere the subsystem exists: encoder output, population input, the reshape in both
    # the training loss (:7058) and the held-out eval (:8224), and the shape of world_proj, which is
    # Linear(lat, d_model) -- so it is also half of the wire into LM. The collapsed latent has never
    # been tested against a wider one.

    hid = Lever(128, "Hidden width of the world encoder MLP and of every forward-dynamics predictor "
                     "MLP.", U.COUNT)
    # Census: WORLD_HID, verdict keep; doubled name corrected to `hid`. Old default `_i("WORLD_HID",
    # 128)` at :4144, read on both construction paths -- WorldEncoder(D, WLAT, WHID) at :4155 and
    # DynamicsPopulation(..., WHID, ...) at :4156, which passes it into every ForwardModel.
    # ONE VALUE SIZES TWO STRUCTURALLY DIFFERENT NETS, and it is left as one knob deliberately: no
    # observed defect distinguishes the encoder's width from the predictors', and splitting it would add
    # a coupling nothing has asked for. If the sizing hypothesis is ever tested and the two want
    # different widths, that is the moment to split it, with the measurement in hand.

    route_d = Lever(24, "Width of the routing key space: the output width of qproj and the length of "
                        "each predictor's key vector.", U.COUNT)
    # Census: WORLD_ROUTE -> WORLD.WORLD_ROUTE_D, doubled name corrected to `route_d`. Old default
    # `_i("WORLD_ROUTE", 24)` at :4156.
    # RENAMED BECAUSE THE OLD NAME MISREADS AS A COUNT. On one banner line "WORLD_ROUTE=24" sits beside
    # "WORLD_NMAX=6": 24 is the DIMENSIONALITY of the routing key and 6 is the population size, so a
    # reader who reads 24 as "routes" mis-sizes the population. This project has already lost real work
    # to a knob whose printed name did not describe its quantity (FAB_STEPS, which meant routing hops
    # and sat beside two genuine clocks). The _D suffix says dimension.
    # A GENUINE BEHAVIOURAL KNOB, NOT DECORATION: it scales the routing logits, which are
    # `q @ K.t() / route_dim**0.5` at world_model.py:89, so it sets how sharp the routing is as well as
    # how much capacity the key space has.

    # ==============================================================================================
    # 3. THE POPULATION AND ITS MANAGEMENT
    #
    # The same growth-and-selection primitive as the fabric, reused on dynamics predictors, and the
    # names are kept parallel to FAB_N0 on purpose -- matching names are what let the two be compared.
    # One asymmetry is deliberate and stated so nobody "fixes" it: FAB_NMAX is declared over there as
    # the field `slots`, because five couplings in spine/assemble.py and two functions in
    # spine/derive.py are written against `r["FAB"].slots`. Nothing in assemble reads this package's
    # cap, so WORLD_NMAX keeps its census name and stays WORLD_NMAX for the operator.
    # ==============================================================================================

    n0 = Lever(3, "Number of dynamics predictors the population is built with before any growth.",
               U.COUNT)
    # Census: WORLD_N0, verdict keep; doubled name corrected to `n0`. Old default `_i("WORLD_N0", 3)` at
    # :4156. NOT world_model.py's signature default of 2 -- see the porting note in the module docstring.
    # NOT MADE REDUNDANT BY GROWTH, for a reason that is a defect rather than a design: growth is
    # effectively inert today (the newborn is culled in the same block -- see `grow`), so n0 is in
    # practice the ONLY thing that sets how many predictors a run has. It is also the entire population
    # size on every WORLD_GROW=0 arm, which is one of the arms D4's ablation ladder needs.
    # HALF OF A RESUME GATE THAT DOES NOT EXIST YET. The replay is `while world_fwd.n() < _want2`
    # (:4586), which handles only the GROW direction. A checkpoint holding FEWER predictors than this
    # run's n0 builds falls straight through to load_state_dict and raises "Missing key(s) preds.N.*" --
    # a shape dump naming no knob (M43). The new gate must refuse in both directions and name n0.

    nmax = Lever(6, "Hard cap on the number of LIVE dynamics predictors; also sizes the "
                    "per-predictor fitness, routing-mass and alive buffers.", U.COUNT)
    # Census: WORLD_NMAX, verdict keep; doubled name corrected to `nmax`. Old default `_i("WORLD_NMAX",
    # 6)` at :4156 (not the signature's 8).
    # KEEPING IT IS NOT OPTIONAL: it is the value the resume gate has to be able to NAME. A checkpoint
    # holding more predictors than this run's cap used to spin the replay loop forever with no output,
    # no traceback and no timeout, because grow() returns None WITHOUT appending at capacity
    # (world_model.py:110). That is now a bounded SystemExit at :4593-4598 saying "Set WORLD_NMAX>=N, or
    # resume with WORLD_MODEL=0", which is the pattern the whole tree should follow -- with one thing to
    # carry across the rename: that message names WORLD_MODEL, which no longer exists. It must say
    # WORLD_ENABLED=0, or it sends the operator to set a variable unread_env() will report as a typo.
    # TWO LIVE DEFECTS HANG OFF THIS CAP AND BOTH ARGUE FOR KEEPING IT VISIBLE.
    #   M70: grow()'s `if s.n() >= s.nmax` counts TOTAL predictors, not LIVE ones. Once soft_cull has
    #        deactivated k of them the population stalls at nmax with only nmax-k working, and the
    #        plateau trigger silently stops firing -- no message, the growth mechanism just ends.
    #   M69: soft_cull is IRREVERSIBLE despite both docstrings calling it reversible (world_model.py:83
    #        says "soft-cull mask (reversible: params kept)"). `alive` is only ever written to 0.0 at
    #        :127 and nothing anywhere restores it to 1.0, so capacity is permanently lost to a
    #        predictor that still costs forward compute and gradient while contributing about 1e-6 of
    #        the blend.
    # HELP-STRING MEANING CHANGED 2026-09-02, DEFAULT UNCHANGED AT 6 (Q-WORLD-8, RESOLVED (b)): this
    # caps LIVE predictors, not allocated ones, and a mint at the cap takes the lowest DEAD SLOT
    # rather than appending. THE BUFFER WIDTH IS WHY, and it is not a preference: fit, mass and alive
    # are all width nmax (world_model.py:81-83) while grow() appends to a ModuleList, so "count live
    # and append" -- the literal reading of the contract's own recommendation -- drives n() past nmax
    # and update_fitness's `for i in range(s.n())` walks off the end of three buffers. The frozen
    # `blocked_reason` set says the same thing from the other side: it contains at_live_cap and no
    # at_total_cap, so refusing at n() == nmax with live < nmax has no reason it is allowed to
    # report. Under (b) n() (allocated) is monotone up to nmax and `live` is the number that moves;
    # world/api.py's geometry records the ALLOCATED count, because that is what decides which tensors
    # exist.
    # Because it sizes fit/mass/alive (world_model.py:81-83), changing it across a resume breaks buffer
    # shapes inside torch with no knob named (H22).

    grow = Lever(True, "Selection on the population: clone a predictor from the fittest on a "
                       "forward-loss plateau, and soft-cull predictors whose routing mass has decayed "
                       "away.", U.FLAG)
    # Census: WORLD_GROW, verdict keep; doubled name corrected to `grow`. Old default at :4147 was
    # `bool(_i("WORLD_GROW", 1)) and WORLD_MODEL`. THE LITERAL IS True: the `and WORLD_MODEL` half is
    # not a default, it is a fold of another lever into this one's effective value, which is exactly the
    # computed-default shape Lever.__init__ refuses. It moves INSIDE the package, where the requested
    # value and the effective value can no longer diverge in a banner.
    # THE DO-NOT-DROP-ON-INERT CASE, EXPLICITLY. This mechanism has never been observed to add a working
    # predictor in the product loop, and every cause found so far is plumbing around it rather than the
    # idea:
    #   * grow() appends a predictor and never initialises its `mass` (a zeros buffer sized nmax), and
    #     soft_cull runs in the SAME MANAGE_EVERY block immediately afterwards (:6772) deactivating
    #     anything with mass < 1e-3. The newborn is culled microseconds after it is minted
    #     (ISSUES:46-47). Fix: mass on birth.
    #   * The DID IT FIRE row is broken independently: `grown` is a plain int (world_model.py:75), not a
    #     buffer, so it is absent from state_dict and restarts at 0 on every resume -- while the
    #     resume's grow-replay loop increments it. The row reports the CHECKPOINT's population size as
    #     THIS run's growth events (M71).
    #   * grow()'s seed key is the batch centroid (`_wz.reshape(-1, WLAT).detach()` at :6770), not the
    #     mispredicted region its docstring names (L72). A predictor cloned toward the average of the
    #     batch is not specialising on anything.
    # Three defects in the instrument and the plumbing, none in the mechanism. Keep the lever; the port
    # fixes mass-on-birth and makes `grown` a buffer, and the plateau trigger becomes a Gate that prints
    # its own arithmetic instead of the two bare constants at :6769 (`_winv > 0.9 * _wl_ema` and
    # `step - _wl_lastgrow > 4 * MANAGE_EVERY`).
    # THE CADENCE THIS FIRES ON IS NOT THIS PACKAGE'S AND ITS UNIT IS DISPUTED -- census defect 2, left
    # standing rather than silently resolved. The trigger is `step % MANAGE_EVERY == 0` at :6768, which
    # sits ABOVE the batch early-out at :6795-6796, so it is tested on every window and `step` advances
    # per WINDOW: on THIS path the cadence is Windows, as CENSUS.md:218 says. spine/assemble.py:686
    # publishes the same FAB field as FAB.d_manage_period in FLUSHES, via
    # `derive.flush_period(Steps(r["FAB"].manage_every), r["TRAIN"].batch_w)`, and its `why` says the
    # management block sits BELOW the early-out -- true of :6961/:6988/:7077/:7325, which gate on
    # `_nbwd % max(1, MANAGE_EVERY // BATCH_W)`, and false of this one. Handing WORLD the Flushes wire
    # would be a 16x error in when growth may fire at BATCH_W=16, the same class as pin_tick counting
    # flushes against a threshold in steps. This package needs a Windows-denominated wire; declaring it
    # is spine/assemble.py's job and the disagreement is named here rather than resolved by whoever
    # typed last.

    # ==============================================================================================
    # 4. WHAT IT COSTS THE TRAINING LOSS
    #
    # Two weights, and the ONE thing this file will not let happen is their being folded back into one.
    # The fold IS the historical bug: the integration multiplied the anti-collapse term by WORLD_W=0.1,
    # running it at one tenth strength, and the latent collapsed to std 0.24. Splitting it out as its
    # own full-strength weight (a1767b7) moved latent std 0.24 -> 0.97 and forward-pred against
    # persistence +13.6% -> +34.1%. Both names below now state WHICH TERM they weight, so folding them
    # back together requires deliberately writing the wrong name. The comment at :4145-4146 says the
    # same thing in the old tree, and it is worth keeping in both places.
    #
    # UNIT LABEL, UNDER PROTEST AND SO RECORDED. units.py has no WEIGHT constant, and both of these are
    # dimensionless multipliers on a loss rather than fractions of anything. U.FRACTION is carried
    # because both defaults (1.0 and 0.1) do lie in 0..1, so the label is not falsified by the
    # declaration the way it would be by FAB_MUT_BIG=6.0 -- src/fabric/levers.py applies the same rule
    # and drops to U.COUNT only where the default itself contradicts the label. If a WEIGHT label is
    # ever added to units.py, these two are its first users.
    # ==============================================================================================

    collapse_w = Lever(1.0, "Weight on the VICReg-style variance+covariance anti-collapse term applied "
                            "to the encoder's latent.", U.FRACTION)
    # Census: WORLD_VAR -> WORLD.WORLD_COLLAPSE_W, doubled name corrected to `collapse_w`. Old default
    # `_f("WORLD_VAR", 1.0)` at :4145, applied at FULL strength: `tot = tot + WORLD_W * _wpl +
    # WORLD_VAR * (_wv + 0.04 * _wc)` at :7061.
    # THE NAME IS THE FIX. WORLD_VAR said which STATISTIC it came from; it did not say which TERM it
    # weights, and the next reader folded it into the other weight. The renamed pair cannot be folded by
    # accident.
    # THE 0.04 IN THAT EXPRESSION IS AN UNDECLARED SECOND DEFAULT INSIDE THIS DECLARED LEVER, hard-coded
    # at :7061 and again as w_cov=0.04 in world_model.py:55. The covariance half of the term is
    # therefore not controlled by this lever at all -- it is controlled by this lever times a constant
    # nobody can set. That is what L1 forbids, and the port fixes it rather than carrying it. It is not
    # emitted as a lever here because no census row creates one, and inventing a name and a default on
    # no authority is how a knob acquires its second default in the first place.

    predict_w = Lever(0.1, "Weight on the population forward-prediction (plus load-balance) term in the "
                           "total training loss.", U.FRACTION)
    # Census: WORLD_W -> WORLD.WORLD_PREDICT_W, doubled name corrected to `predict_w`. Old default
    # `_f("WORLD_W", 0.1)` at :4144.
    # Read as "the world model's weight" rather than "the weight on the prediction term", it was USED as
    # such -- it scaled the anti-collapse term too, and that is the collapse defect that cost the
    # subsystem its first month of measurements (std 0.24, +13.6% instead of +34.1%).
    # KEPT AS A LEVER AND NOT MERGED INTO `enabled`: it is the only PRICE control on a subsystem that is
    # costed on every training step and whose 413 full-stack readings never once beat a persistence
    # baseline. The ablation ladder D4 asks for is "measured, not deleted", and measuring the price
    # curve needs a way to turn the cost DOWN without turning the mechanism OFF -- enabled=False and
    # predict_w=0.0 are not the same arm, because the second still trains the encoder under
    # collapse_w and still builds the population.
    # The load-balance weight folded into this term is the w_bal=0.01 signature default listed in the
    # module docstring; the loop never decays it and the probe does, so the two are optimising
    # different objectives.

    # ==============================================================================================
    # 5. WHAT THE PREDICTION MEANS
    # ==============================================================================================

    horizon = Lever(1, "Prediction horizon in stream positions: the latent at t is trained to predict "
                       "the latent at t+horizon.", U.TOKENS)
    # Census: WORLD_K -> WORLD.WORLD_HORIZON, doubled name corrected to `horizon`. Old default
    # `max(1, _i("WORLD_K", 1))` at :4144 -- the literal is 1 and the max() is discussed below.
    # A SINGLE OPAQUE LETTER FOR THE QUANTITY THAT DECIDES WHAT "THE NEXT LATENT" EVEN MEANS. Both the
    # training loss (:7058) and the held-out eval (:8224) slice with it -- `z[:, :-K]` against
    # `z[:, K:]` -- and then print numbers labelled "forward-pred MSE" and "persistence baseline" that
    # silently mean a DIFFERENT COMPARISON at every value. That is the wrong-measurement class, 98 of
    # the survey's 475 records and the class this rebuild is shaped to make hard. The name has to carry
    # the meaning and every Reading has to carry the horizon it was measured at, or two runs' numbers
    # are not comparable and nothing says so.
    # NOT A CLOCK, AND THE DISTINCTION IS DELIBERATE. This is an offset WITHIN one window -- a distance
    # between two positions in the same tensor -- not a count of loop events, so no Clock kind applies
    # and U.TOKENS is metadata. Making it Steps or Windows would be a false statement about what it
    # measures, and units.py is narrow on purpose precisely so its guarantees stay true.
    # TWO GUARDS THE OLD READ GOT WRONG, IN OPPOSITE DIRECTIONS.
    #   The floor: `max(1, ...)` silently rewrites WORLD_K=0 to 1, so the banner prints a value the run
    #   did not use. That is the FAB_MIN_STEPS shape -- a coercion at read time that makes a printed
    #   number a lie -- and it becomes a startup refusal naming the lever, not a silent repair.
    #   The ceiling: there is none. A horizon >= the window width empties BOTH slices, and an empty
    #   tensor produces a loss of nan rather than an error. The bound belongs to another package (LM's
    #   `ctx`, the census's WIN), so it cannot be a choices= list here -- it is a declared Gate against
    #   the wired window width, evaluated at startup and printing its own arithmetic.
