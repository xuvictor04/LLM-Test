# 05 — DEFAULTS: what is on, what is off, and what every knob is set to

**GENERATED FILE — do not edit.** `python3 tools/render_defaults.py` rewrites it from the live lever
registry in `src/*/levers.py`; `tests/test_assemble.py`'s A10 fails if what is on disk is not what
the generator would write today. Nothing below this paragraph is typed by hand.

`notes/CURRENT_DEFAULTS.md` is the same idea for `self_organize.py` — the ARCHIVED tree. Every knob
in that file is one this system no longer reads, under a name it no longer generates. This file is
about `src/`.

**Env names are GENERATED, not declared.** A lever is a field on a `LeverSet` with a `PREFIX`, and
the operator's name for it is `PREFIX_FIELD` upper-cased. There is no second list to keep in step,
which is why a name that looks wrong here is a field that is wrong in `src/<pkg>/levers.py`.

**A default is the one value `from_env` never coerces** (`spine/lever.py::Lever`), so a default is
also the one value no `choices=`/`domain=` check ever sees at resolution time. The declaration-time
checks in that constructor are what stand in for it.


## 1. What is OFF at the shipped defaults

Read this before reading a run's DID IT FIRE report. A mechanism that is off by configuration and a
mechanism that ran and found nothing print the same 0, and the whole of this tree's counter
convention exists to separate them — but only for mechanisms that were ASKED. A lever that is off
here was never asked, and no counter in any report can say so on its own.

**Boolean levers that ship False.** These are flags; False is unambiguous.


| lever | what it turns off |
|---|---|
| `DATA_RESAMPLE` | Redraw a fresh stream from the areas at the start of every epoch instead of replaying the same bytes. |
| `DATA_SEG_CONTIG` | Read each area in order instead of seeking to a random offset every segment, so the only boundaries left are the text's own. |
| `FAB_GROW_ON_MEM_PRESSURE` | Let the memory-pressure signal make fabric growth eligible, instead of only being printed. |
| `FAB_LR_OWN` | Put each expert on its own cyclical learning-rate schedule, clocked from its own use count. |
| `FAB_NORM_ONLY` | Control arm: keep the fabric's normalization, remove nodes and routing from the forward pass. |
| `FAB_SOCIETY` | One hop with experts blended at the PREDICTION level, instead of multi-hop chaining through Fabric.forward. |
| `LM_COMPOSE` | Build each token's vector from its bytes plus a learned residual, instead of storing a free row per token. |
| `LM_MASK_DEAD_ROWS` | Take never-minted and retired vocabulary rows out of the distribution wherever logits become one. |
| `MEM_WRONG_SWEEP` | Whether the selected wrongness detector DELETES flagged entries or only flags them. |
| `RUN_BENCH` | Stop immediately after the training loop and print throughput instead of running the eval battery. |
| `RUN_PROFILE` | Per-component wall-clock attribution of the training step, dumped on the rate cadence and again in the throughput summary. |

11 levers ship False.

**Numeric levers that ship 0.** Zero is this tree's documented OFF sentinel in most of these places
and a legitimate value in some, so the help text is quoted rather than summarised. `spine/lever.py`
records the rule and `src/tok/api.py` names five of the exceptions by hand: *"freeze_at, retok_every,
mint_pmin, mint_novel and probation_uses"* all use 0 as OFF, while a period of 0 elsewhere means
DISARMED — which the cadence audit reports as a different state from starved.


| lever | unit | what the help says |
|---|---|---|
| `CAP_FAB_START` | experts | Soft expert cap the valve starts from and only lifts; 0 means start at the hard ceiling, i.e. no room to earn. |
| `CAP_VOCAB_START` | tokens | Soft vocabulary cap the valve starts from and only lifts |
| `CKPT_BEST_KEEP` | count | How many recent local lows in held-out bits/byte to retain as rotating .best1..bestN checkpoints, on top of the single global .best. |
| `CKPT_EVERY` | Windows | How often a mid-run checkpoint is written, in windows elapsed since the last one |
| `DATA_PHASE_LIVE` | count | How many areas are live in each phase of the GENERATED schedule |
| `FAB_EC_W` | fraction 0..1 | Expert-choice deficit bonus: nudge routing toward experts under their share, by construction rather than by a loss. |
| `FAB_HOP_SUP` | fraction 0..1 | Weight on per-hop deep supervision: a cross-entropy at every hop, not only at the end of the walk. |
| `FAB_RESCUE` | fraction 0..1 | Give an expert about to be culled one heavy mutation and a reset use-clock instead of deleting it. |
| `LM_DROPOUT` | probability | Dropout probability, at three sites: the token embedding, between GRU layers when depth is greater than one, and the READOUT in LM.decode before the head. |
| `LM_LAYERS` | count | Depth of the base LM -- transformer blocks or GRU layers |
| `MEM_JUDGE_FRAC` | fraction 0..1 | Share of the ALREADY-CHECKED store that judge() re-scores on each pass, on top of the entries written since the last one. 0.0 re-scores nothing. |
| `MEM_KEY_DEPTH` | count | Cap the transformer depth used for the memory key path only |
| `OPT_GRAD_CLIP` | fraction 0..1 | Global gradient-norm clip applied to the BASE parameter group before each optimizer step. 0.0 is OFF, which is what every recorded number in this project was measured under. |
| `OPT_LR_SHIFT_WARM` | Steps | Re-warm length after a distribution shift the system caused itself, applied as an attenuation of the current cycle. |
| `OPT_LR_WAVELENGTH` | Steps | Length of one cosine cycle, stated directly in optimizer steps |
| `OPT_WEIGHT_DECAY` | fraction 0..1 | AdamW decoupled weight decay, applied to the base optimizer and the encoder optimizer alike. |
| `RUN_SEED` | count | Root seed for the whole run |
| `SIG_COV_WEIGHT` | count | Weight on the covariance (decorrelation) term of the same anti-collapse regulariser. |
| `SIG_PROTOTYPE_FRAC` | fraction 0..1 | Fraction of the InfoNCE batch replaced by pairs drawn from ONE domain's reservoir, so the encoder is trained on kind-invariance and not only on locality. |
| `TOK_DROPOUT` | probability | Probability of skipping an available merge during a counting segmentation, so byte-level material still reaches the tally. |
| `TOK_FREEZE_AT` | Windows | Window after which no further token is minted |
| `TOK_MINT_NOVEL` | fraction 0..1 | Exponent re-ranking mint candidates by how much a pair has grown since it was last considered |
| `TOK_MINT_PMIN` | probability | Minimum p(b\|a) for a merge to be accepted as a unit rather than a frequent collision across a boundary |
| `TOK_PROBATION_USES` | count | How many appearances a newly minted token must earn before it keeps its place in the match table |

24 numeric levers ship 0.

---

## 2. Every lever, by package

262 levers across 13 packages.


### CAP (7 levers)

| lever | default | unit | accepts | what it is |
|---|---|---|---|---|
| `CAP_FAB_START` | `0` | experts |  | Soft expert cap the valve starts from and only lifts; 0 means start at the hard ceiling, i.e. no room to earn. |
| `CAP_LIFT` | `0.08` | fraction 0..1 |  | Fraction of the current soft cap added on each earned lift. |
| `CAP_LIFT_MIN` | `8` | slots |  | Absolute floor on one lift, so a small soft cap still moves. |
| `CAP_PIN_WINDOWS` | `20000` | Windows |  | Accumulated windows a population must sit pinned against its soft cap before a lift is earned. |
| `CAP_STALL_BAND` | `0.002` | fraction 0..1 |  | Half-width of the band around zero improvement inside which the loss counts as stalled and a lift is authorised. |
| `CAP_TARGETS` | `'off'` | name | choices `'off'`, `'experts'`, `'vocab'`, `'both'` | Which populations the valve may lift: neither, the experts, the vocabulary, or both. |
| `CAP_VOCAB_START` | `0` | tokens |  | Soft vocabulary cap the valve starts from and only lifts |

### CKPT (5 levers)

| lever | default | unit | accepts | what it is |
|---|---|---|---|---|
| `CKPT_BEST_KEEP` | `0` | count |  | How many recent local lows in held-out bits/byte to retain as rotating .best1..bestN checkpoints, on top of the single global .best. |
| `CKPT_BEST_KEEP_TOL` | `0.02` | fraction 0..1 |  | How close to the best held-out bits/byte seen so far a descending probe must land, as a fraction of it, to earn a rotation slot. |
| `CKPT_DIR` | `''` | path |  | Directory this run writes its checkpoint into -- model, tokenizer, memory store, optimizer moments, domain centroids |
| `CKPT_EVERY` | `0` | Windows |  | How often a mid-run checkpoint is written, in windows elapsed since the last one |
| `CKPT_RESUME` | `''` | path |  | Checkpoint to continue training from -- a run directory or a .pt file |

### DATA (18 levers)

| lever | default | unit | accepts | what it is |
|---|---|---|---|---|
| `DATA_AREAS` | `'eng,py,num,c'` | name |  | The corpora to stream, in order; their names label every per-area score in the report and across the run boundary. |
| `DATA_CORPUS_CAP` | `2000000` | bytes |  | Bytes read from disk per area before any holdout split or stream draw |
| `DATA_DIR` | `'data'` | path |  | Root of the corpus tree; an area with no '/' is read from DATA_DIR/train/<area>/*, and an area containing '/' is joined under DATA_DIR verbatim (DATA_AREAS="eng,continual/01_rust"). |
| `DATA_DRAW` | `'planned'` | name | choices `'planned'`, `'uniform'` | How a phase's bytes are allocated across its live areas: 'planned' gives each area its scheduled share and randomises only the order and the offsets |
| `DATA_EXPOSURE_MAX` | `2.0` | count |  | Whole-run repetition multiple (bytes drawn x epochs / bytes on disk) above which the data plan is flagged before training starts. |
| `DATA_EXPOSURE_SKEW` | `3.0` | count |  | Max/min exposure ratio across areas above which the data plan is flagged as imbalanced. |
| `DATA_HOLDOUT_FRAC` | `0.05` | fraction 0..1 | domain (0.0, 1.0) | Fraction of each area held out and never sampled into the training stream. |
| `DATA_N_PROCESSES` | `4` | count |  | How many synthetic Markov processes the stream is generated from, on DATA_SOURCE=synthetic only. |
| `DATA_PHASE_LIVE` | `0` | count |  | How many areas are live in each phase of the GENERATED schedule |
| `DATA_PHASE_SCHED` | `''` | name |  | Explicit phase schedule, pipe-separated phases of comma-separated area indices OR area names ("0\|0,1\|0,1\|1", "eng\|eng\|rust\|rust") |
| `DATA_PHASES` | `4` | count |  | How many phases the generated sliding-window schedule has, when no explicit schedule is given. |
| `DATA_RESAMPLE` | `False` | on/off |  | Redraw a fresh stream from the areas at the start of every epoch instead of replaying the same bytes. |
| `DATA_SEG_CONTIG` | `False` | on/off |  | Read each area in order instead of seeking to a random offset every segment, so the only boundaries left are the text's own. |
| `DATA_SEG_MAX` | `1800` | bytes |  | Longest spliced segment drawn from one area before the stream switches. |
| `DATA_SEG_MIN` | `700` | bytes |  | Shortest spliced segment drawn from one area before the stream switches. |
| `DATA_SOURCE` | `'synthetic'` | name | choices `'real'`, `'synthetic'` | Which stream the run trains on: `real` splices the corpora under DATA_DIR, `synthetic` generates from Markov processes. |
| `DATA_STREAM_BYTES` | `120000` | bytes |  | Bytes of stream one epoch draws from the areas. |
| `DATA_VAL_CAP` | `4000000` | bytes |  | Maximum bytes of held-out tail kept per area. |

### DOM (28 levers)

| lever | default | unit | accepts | what it is |
|---|---|---|---|---|
| `DOM_ACCEPT_RULE` | `'radius'` | name | choices `'radius'`, `'margin'`, `'constant'` | How re-entry is decided: `radius` uses each domain's own measured acceptance radius, `margin` compares nearest against runner-up, `constant` uses spawn_dist alone. |
| `DOM_CULL_ACT_MIN` | `15` | count |  | Cull threshold on a domain's DECAYED activity counter |
| `DOM_CULL_FRAC` | `0.1` | fraction 0..1 | domain (0.0, 1.0) | Per-pass cull budget: the bottom fraction of domains by decayed activity are considered. |
| `DOM_CULL_RESPECTS_MEM_FLOOR` | `True` | on/off |  | Refuse to cull a domain that still holds a per-source floor's worth of memory entries. |
| `DOM_CULL_STALE` | `500` | Windows |  | Windows since a domain was last fed before it counts as stale for the cull. |
| `DOM_DECAY` | `0.9` | fraction 0..1 | domain (0.0, 1.0) | What each domain's activity counter keeps per management pass, so `act` measures RECENT use rather than cumulative use. |
| `DOM_ENABLED` | `True` | on/off |  | Assemble domains at all; off sends did=0 for every window, so there is one bucket, no provenance and nothing to manage. |
| `DOM_FOLD` | `True` | on/off |  | Fold domains that never recur into their nearest neighbour instead of leaving them standing. |
| `DOM_FOLD_MULT` | `1.5` | count |  | Refuse to fold a domain further than this multiple of the POOLED radius. |
| `DOM_GRACE` | `500` | Windows |  | Minimum age in windows since birth before a domain may be culled, on both cull paths. |
| `DOM_MANAGE` | `True` | on/off |  | Run merge, cull and fold over the population |
| `DOM_MANAGE_EVERY` | `100` | Windows |  | Windows between management passes: merge, then cull, then fold. |
| `DOM_MARGIN` | `0.75` | fraction 0..1 |  | Under accept_rule=margin, re-identify when the nearest centroid is at most this fraction of the runner-up's distance. |
| `DOM_MERGE_DIST` | `0.28` | fraction 0..1 | domain (0.0, 2.0) | Cosine distance under which two domains are merged into one during a management pass. |
| `DOM_MIN_VISITS` | `2` | count |  | 'Recurs' means entered on at least this many SEPARATE occasions |
| `DOM_PRIOR_BLEND` | `0.15` | fraction 0..1 | domain (0.0, 1.0) | Weight of the per-domain token histogram in the blended prediction |
| `DOM_RADIUS_CAP` | `2.0` | count |  | Voronoi guard: no radius may exceed this multiple of the distance to the nearest OTHER centroid. 0 removes the guard. |
| `DOM_RADIUS_MULT` | `1.2` | count |  | Multiplier on the measured quantile that gives the acceptance radius. |
| `DOM_RADIUS_Q` | `0.85` | fraction 0..1 | domain (0.0, 1.0) | Quantile of d(reservoir window, own centroid) that defines a domain's acceptance radius, and of the pooled distances for domains with none yet. |
| `DOM_RECUR_HORIZON` | `32` | count |  | Boundaries that must pass since a domain's birth before it is judged for recurrence at all. |
| `DOM_RESERVOIR` | `40` | count |  | Sample windows kept per domain |
| `DOM_SHIFT_DIST` | `0.3` | fraction 0..1 | domain (0.0, 2.0) | Under shift_rule=constant, the adjacent-window cosine distance that counts as a candidate boundary. |
| `DOM_SHIFT_MULT` | `1.5` | count |  | Under shift_rule=relative, trip when the jump exceeds this many times the shift_q base. |
| `DOM_SHIFT_Q` | `0.5` | fraction 0..1 | domain (0.0, 1.0) | Under shift_rule=relative, the quantile of the last 512 adjacent distances used as the base. |
| `DOM_SHIFT_RULE` | `'constant'` | name | choices `'constant'`, `'relative'` | Boundary test: `constant` trips at a fixed distance, `relative` trips at a multiple of a running quantile of recent distances. |
| `DOM_SPAWN_DIST` | `0.35` | fraction 0..1 | domain (0.0, 2.0) | Cosine distance beyond which an assign query spawns a new domain instead of re-entering the nearest. |
| `DOM_SUSTAIN` | `2` | Windows |  | Consecutive over-threshold windows required before a boundary is declared |
| `DOM_TOKC_DECAY` | `0.5` | fraction 0..1 | domain (0.0, 1.0) | What a domain's token histogram keeps when the tokenizer re-segments |

### EVAL (17 levers)

| lever | default | unit | accepts | what it is |
|---|---|---|---|---|
| `EVAL_AFF_MIN` | `0.1` | fraction 0..1 | domain (0.0, 1.0) | Minimum share of a domain's expert-usage mass at which an expert counts as SERVING it. |
| `EVAL_COH_LEN` | `384` | tokens |  | Tokens of continuation per seed |
| `EVAL_COH_SEEDS` | `16` | count |  | Seed passages the coherence instrument draws |
| `EVAL_CURVE_EVERY` | `2000` | Windows |  | Windows between learning-curve probes |
| `EVAL_GEN_DOMAINS` | `4` | domains |  | How many domains the GENERATION section samples |
| `EVAL_GEN_LEN` | `200` | tokens |  | Tokens per printed continuation, model-only and model+memory, from the same seed. |
| `EVAL_GEN_SAMPLES` | `4` | count |  | Distinct seed passages sampled per domain in the GENERATION section. |
| `EVAL_GEN_TEMP` | `0.7` | fraction 0..1 |  | Sampling temperature for every generated continuation, printed and scored alike. |
| `EVAL_GENERATE` | `True` | on/off |  | Run the GENERATION section: model alone versus model+memory, from the same real seeds. |
| `EVAL_GENUINE_MIN` | `20` | count |  | Minimum member count before a discovered domain is reported as genuine rather than noise. |
| `EVAL_GENUINE_SIL` | `0.1` | fraction 0..1 |  | Minimum silhouette (own-centroid similarity minus nearest-other) for a genuine domain. |
| `EVAL_HOLDOUT_WINDOWS` | `32` | count |  | Held-out windows per domain for the retention probe |
| `EVAL_NULL_DRAWS` | `5` | count |  | Permutation draws used to build the null distribution every 2-sigma verdict is judged against. |
| `EVAL_VERIFY_FIT_STEPS` | `3000` | Steps |  | Optimizer steps spent fitting the Reconstructor post hoc on the final settled store. |
| `EVAL_WINDOWS` | `64` | count |  | Default number of windows an eval Sample draws when it does not declare its own. |
| `EVAL_WRONG_INJECT` | `8` | entries |  | Synthetic cross-domain wrong entries planted so precision and recall have a denominator. |
| `EVAL_WRONGNESS` | `True` | on/off |  | Run the WRONGNESS section: self-consistency detection over the settled store, with its precision and recall. |

### FAB (82 levers)

| lever | default | unit | accepts | what it is |
|---|---|---|---|---|
| `FAB_AE_W` | `0.5` | fraction 0..1 |  | Weight on the weights -> identity -> weights round trip that keeps the identity decoder edec honest. |
| `FAB_ALPHA` | `0.5` | fraction 0..1 |  | Residual mixing coefficient of one fabric step: h <- norm(h + alpha*(mixture - h)). |
| `FAB_BAL_FLOOR` | `0.15` | fraction 0..1 |  | Permanent floor under the load-balance pressure, as a fraction of full, so traffic never stops reaching the tail of the population. |
| `FAB_BAL_WARM` | `4000` | Windows |  | How long the load-balance pressure takes to decay from full to its floor. |
| `FAB_BALANCE` | `0.01` | fraction 0..1 |  | Load-balance pressure on the routing distribution, so every expert keeps accruing use-age instead of a few absorbing all traffic. |
| `FAB_BIRTH_JITTER` | `0.15` | fraction 0..1 |  | Perturbation added to a newborn's centroid so a growth burst does not mint exact clones. |
| `FAB_BIRTH_WIN` | `256` | count |  | Size of the sliding per-parent birth record that parent_max is measured against. |
| `FAB_BURST` | `1` | experts |  | How many experts a REGRESSION grows at once. |
| `FAB_CENT_EMA` | `0.02` | fraction 0..1 |  | Rate at which a node's centroid moves toward the signatures it actually served. |
| `FAB_CENT_TOPK` | `8` | experts |  | How many routed centroids EMA toward the served signature on each grounded update. |
| `FAB_CHAIN_K` | `8` | experts |  | How many experts are COMPUTED per hop (top-k by routing mass) |
| `FAB_COMP_EMA` | `0.02` | fraction 0..1 |  | EMA rate for the per-node competence and marginal-contribution signals that gate cull-sparing. |
| `FAB_COMP_PROTECT` | `True` | on/off |  | Spare a unit from the cull when it models its own material better than the population does, however rarely it is selected. |
| `FAB_COOLDOWN` | `400` | Windows |  | Minimum spacing between growth firings, and the window over which recent births are counted for the new_frac budget. |
| `FAB_CULL_FRAC` | `0.02` | fraction 0..1 | domain (0.0, 1.0) | Fraction of the ELIGIBLE (past-grace) set removed per manage pass, floored at one. |
| `FAB_DEPTH0` | `1` | count |  | Hop count the chain starts at before staged depth extends it |
| `FAB_DEPTH_EPS` | `0.01` | bits/byte |  | Improvement in the smoothed flush loss that still counts as progress, so a depth stage does not advance while the loss is still falling. |
| `FAB_DEPTH_PATIENCE` | `6` | count |  | Consecutive flat depth-checks required before one more hop is added. |
| `FAB_DEPTH_STAGE_MAX` | `40` | count |  | Depth-checks after which a stage ends regardless of the plateau test. |
| `FAB_DISCOVER` | `0.35` | fraction 0..1 | domain (0.0, 2.0) | Cosine distance beyond which a signature counts as material NOTHING owns and is handed to the least-used expert. |
| `FAB_DIV_W` | `0.02` | fraction 0..1 |  | Weight on the distinctness penalty that rewards the experts a hop leans on for producing different outputs. |
| `FAB_DK` | `32` | count |  | Width of the routing identity space: the shared query projection's output and every per-expert K and SRC vector. |
| `FAB_DOM_FRAC` | `0.1` | fraction 0..1 |  | Breadth cap: an expert serving more than this share of the live domain population is masked out of routing for domains it does not hold. |
| `FAB_DOM_MIN` | `4` | domains |  | Absolute floor on the breadth cap, so a small domain population cannot ban an expert from everything. |
| `FAB_EC_W` | `0.0` | fraction 0..1 |  | Expert-choice deficit bonus: nudge routing toward experts under their share, by construction rather than by a loss. |
| `FAB_EMB_EVERY` | `1` | Windows |  | Cadence at which every expert's identity is re-embedded from its weights. |
| `FAB_EMB_HID` | `128` | count |  | Hidden width of the shared identity embedder eemb and its inverse edec. |
| `FAB_EMB_VAR` | `1.0` | fraction 0..1 |  | Weight on the variance + decorrelation term that stops every expert embedding collapsing to one point. |
| `FAB_ENS_K` | `2` | experts |  | How many of the computed experts actually decode logits per hop or per window. |
| `FAB_ERR_FAST` | `0.05` | fraction 0..1 |  | EMA rate of the per-expert FAST error signal. |
| `FAB_ERR_SLOW` | `0.005` | fraction 0..1 |  | EMA rate of the per-expert SLOW error signal, the baseline the fast one is judged against. |
| `FAB_EXPLORE` | `0.15` | fraction 0..1 |  | Fraction of rows whose lowest-ranked computed slot is swapped for a randomly chosen low-use expert, on training passes only. |
| `FAB_FAIL_TOL` | `0.15` | fraction 0..1 |  | How far BOTH error EMAs must sit above the population before an expert counts as in sustained failure and is cullable at any occupancy. |
| `FAB_GRACE` | `48` | Selections |  | How many times an expert must have been SELECTED before the cull may touch it. |
| `FAB_GROW` | `True` | on/off |  | Master switch for population growth: off freezes the population at n0 while routing, selection, replication and the cull all still run. |
| `FAB_GROW_ON_MEM_PRESSURE` | `False` | on/off |  | Let the memory-pressure signal make fabric growth eligible, instead of only being printed. |
| `FAB_HALT` | `True` | on/off |  | HALT as a real operator on both paths: its mass says 'no expert is needed here' and the caller spends that mass on model.head directly. |
| `FAB_HALT_MAX` | `0.9` | fraction 0..1 | domain (0.0, 1.0) | Ceiling on halt mass, so at least 1-halt_max of the blend and its gradient always reaches the population. |
| `FAB_HOP_MODE` | `'soc'` | name | choices `'soc'`, `'transition'` | Which multi-hop path exists: 'soc' re-routes from scratch each hop with the current state in the query, 'transition' walks the learned successor matrix R with SRC marks. |
| `FAB_HOP_SUP` | `0.0` | fraction 0..1 |  | Weight on per-hop deep supervision: a cross-entropy at every hop, not only at the end of the walk. |
| `FAB_HOP_VOTE` | `True` | on/off |  | Each hop's experts vote on the OUTPUT and the halting hop picks the answer, instead of blending hidden states. |
| `FAB_HOPS` | `4` | count |  | Maximum hop budget for one routed forward pass |
| `FAB_IND_K` | `2` | experts |  | How many of the society's experts are charged with solving the task alone. |
| `FAB_IND_W` | `0.5` | fraction 0..1 |  | Independence loss weight: each of those experts must solve the task ALONE, weighted by its routing mass. |
| `FAB_LR_AMIN` | `0.15` | fraction 0..1 | domain (0.0, 1.0) | Floor under the decaying envelope, so a long-lived expert keeps a small permanent capacity to move. |
| `FAB_LR_BOOST` | `2.0` | count |  | Multiply the own-rate for the cull-eligible bottom of the utilization ranking: exploration before removal. |
| `FAB_LR_CYCLE` | `24.0` | Selections |  | Half-cycle of the per-expert triangular2 schedule, measured on the expert's own use clock. |
| `FAB_LR_GAMMA` | `0.5` | fraction 0..1 | domain (0.0, 1.0) | Per-cycle envelope decay: 0.5 is triangular2 exactly, 1.0 degenerates to plain triangular. |
| `FAB_LR_MAXR` | `4.0` | count |  | Ceiling on the ratio of an expert's own rate to the global rate. |
| `FAB_LR_OWN` | `False` | on/off |  | Put each expert on its own cyclical learning-rate schedule, clocked from its own use count. |
| `FAB_MANAGE_EVERY` | `500` | Windows |  | Cadence of the management pass: the fabric cull, spares, replication and the staged-depth check. |
| `FAB_MERGE_DIST` | `0.1` | fraction 0..1 | domain (0.0, 2.0) | Cosine distance under which two redundant experts are MERGED by averaging their adapters, instead of one being culled. |
| `FAB_MUT` | `0.25` | fraction 0..1 |  | Mutation size at birth, as a fraction of the parent's own weight std. |
| `FAB_MUT_BIG` | `6.0` | count |  | Size of the heavy-tail mutation, as a multiple of the ordinary mutation scale. |
| `FAB_MUT_BIG_P` | `0.1` | probability | domain (0.0, 1.0) | Probability that a birth takes the heavy-tail mutation instead of the ordinary one. |
| `FAB_N0` | `2048` | experts |  | Founding population: how many experts are BUILT at construction. |
| `FAB_NEW_FRAC` | `0.04` | fraction 0..1 | domain (0.0, 1.0) | The most of the population that may be newborn at once |
| `FAB_NORM_ONLY` | `False` | on/off |  | Control arm: keep the fabric's normalization, remove nodes and routing from the forward pass. |
| `FAB_ON` | `True` | on/off |  | Build the fabric and put it in the forward path |
| `FAB_PARENT_K` | `8` | experts |  | Shortlist size: how many region-owners compete to be the parent of a new expert. |
| `FAB_PARENT_MAX` | `0.2` | fraction 0..1 | domain (0.0, 1.0) | Maximum share of recent births any one parent may account for. |
| `FAB_PLATEAU` | `0.002` | fraction 0..1 |  | Relative improvement of the slow EMA below which progress counts as stalled: arms the stall growth and releases RECOVER. |
| `FAB_PONDER` | `0.01` | fraction 0..1 |  | Charge on routed depth, so the chain does not take hops it does not need. |
| `FAB_PONDER_WARM` | `8000` | Windows |  | Anneal window for the depth charge, so the fabric is not billed for depth before its experts can be worth using. |
| `FAB_PRESSURE` | `0.45` | fraction 0..1 | domain (0.0, ∞) | Occupancy SETPOINT: below pressure x slots the utilization cull, the utilization spare and `rescue` are all unreachable, so it chooses the operating population size. |
| `FAB_RANK` | `8` | count |  | Low-rank width r of every expert |
| `FAB_RECOVER_MAX` | `20000` | Windows |  | Hard ceiling on the RECOVER lockout, so growth re-arms even if improvement never flattens. |
| `FAB_RECOVER_MIN` | `600` | Windows |  | Minimum RECOVER lockout after a growth burst, so the burst's own transient worsening cannot re-trigger growth. |
| `FAB_REPLICATE` | `True` | on/off |  | Grow by cloning a fit parent plus mutation, instead of minting a fresh random expert. |
| `FAB_RESCUE` | `0.0` | fraction 0..1 |  | Give an expert about to be culled one heavy mutation and a reset use-clock instead of deleting it. |
| `FAB_ROUTE_LEARN` | `True` | on/off |  | Add the learned bilinear identity term to the routing logits. |
| `FAB_ROUTE_REGION_W` | `1.0` | fraction 0..1 |  | Weight on the signature-region cosine term in the routing logits |
| `FAB_ROUTE_T` | `0.1` | fraction 0..1 |  | Routing temperature on the region cosine, the normalized identity term and the HALT logit. |
| `FAB_SHIFT_TOL` | `0.05` | fraction 0..1 |  | How far the fast error may sit above the slow error before the expert counts as ADAPTING and is spared. |
| `FAB_SLOTS` | `4096` | slots |  | Preallocated slot count: cap = max(n0, slots) |
| `FAB_SOCIETY` | `False` | on/off |  | One hop with experts blended at the PREDICTION level, instead of multi-hop chaining through Fabric.forward. |
| `FAB_SPAWN` | `True` | on/off |  | Spawn-by-specification: decode the router's own query into a new expert when nothing near it exists |
| `FAB_SPAWN_FLOOR` | `0.02` | fraction 0..1 |  | Absolute distance floor under the spawn test, so a degenerate population cannot spawn on every query. |
| `FAB_SPAWN_MULT` | `2.0` | count |  | How many times the population's own median nearest-neighbour distance a query must exceed to count as material nothing serves. |
| `FAB_WARMUP` | `300` | Windows |  | How long before the stall trigger may fire at all, so early noise is not read as a plateau. |
| `FAB_XOVER` | `0.35` | fraction 0..1 | domain (0.0, 1.0) | Fraction of births assembled from several parents by taking whole rank slices from a second parent. |
| `FAB_Z` | `4.0` | count |  | How many robust deviations (running MAD) above the slow EMA a loss must sit to count as an unexpected REGRESSION. |

### LM (12 levers)

| lever | default | unit | accepts | what it is |
|---|---|---|---|---|
| `LM_ANCHOR_USES` | `400.0` | count |  | How many appearances in trained-on material a new token is held near its composite for, before the anchor releases it. |
| `LM_ANCHOR_W` | `0.05` | fraction 0..1 |  | Weight of the loss term holding a newly minted token's residual near its byte composite, so the mint is a handover rather than a jump. |
| `LM_ARCH` | `'gru'` | name | choices `'gru'`, `'transformer'` | Which base language model is constructed: the GRU (MiniLM) or the transformer (TinyTransformer). |
| `LM_COMPOSE` | `False` | on/off |  | Build each token's vector from its bytes plus a learned residual, instead of storing a free row per token. |
| `LM_CTX` | `128` | tokens |  | The model's context width |
| `LM_DROPOUT` | `0.0` | probability | domain (0.0, 1.0) | Dropout probability, at three sites: the token embedding, between GRU layers when depth is greater than one, and the READOUT in LM.decode before the head. |
| `LM_HEADS` | `8` | count |  | Attention heads per transformer block |
| `LM_LAYERS` | `0` | count |  | Depth of the base LM -- transformer blocks or GRU layers |
| `LM_MASK_DEAD_ROWS` | `False` | on/off |  | Take never-minted and retired vocabulary rows out of the distribution wherever logits become one. |
| `LM_NEW_ROW_INIT` | `'mean'` | name | choices `'random'`, `'mean'`, `'last_first'` | How a newly minted token's embedding and head rows are initialized from its two parent tokens. |
| `LM_VOCAB_SLOTS` | `4096` | slots |  | How many vocabulary rows the model preallocates |
| `LM_WIDTH` | `128` | count |  | Hidden width of the base LM, and through it the width of every representation keyed off it |

### MEM (26 levers)

| lever | default | unit | accepts | what it is |
|---|---|---|---|---|
| `MEM_BLEND_MAX` | `0.5` | fraction 0..1 |  | Maximum share of the output probability mass retrieval may take when the match is perfect |
| `MEM_EVICT` | `'lru'` | name | choices `'recency'`, `'usage'`, `'lru'` | Which clock picks the victim: write order, decayed retrieval mass, or last retrieval. |
| `MEM_JUDGE_FRAC` | `0.0` | fraction 0..1 |  | Share of the ALREADY-CHECKED store that judge() re-scores on each pass, on top of the entries written since the last one. 0.0 re-scores nothing. |
| `MEM_KEY_DEPTH` | `0` | count |  | Cap the transformer depth used for the memory key path only |
| `MEM_KEY_SRC` | `'model'` | name | choices `'model'`, `'frozen'` | Which representation keys the store: the live model's own encoding, or a frozen byte-statistic table used only as a testing baseline. |
| `MEM_KEY_WIN` | `8` | tokens |  | How many preceding input positions the encoder sees when it builds one memory key. |
| `MEM_MATCH_FLOOR` | `0.3` | fraction 0..1 |  | Top cosine similarity below which a retrieved neighbour contributes nothing |
| `MEM_OWNERS` | `64` | count |  | How many eviction partitions the store is split into |
| `MEM_PRESSURE_THRESH` | `0.8` | fraction 0..1 | domain (0.0, 1.0) | Threshold on pressure() -- the share of evictions destroying PROMOTED entries -- above which the store is declared genuinely short of room. |
| `MEM_PROBATION_FRAC` | `0.1` | fraction 0..1 | domain (0.0, 1.0) | Share of the store the never-retrieved region may occupy before eviction narrows to probation's own oldest. |
| `MEM_PROBE_EVERY` | `25` | Windows |  | Cadence of the training-time read probe: real retrievals issued against the text being trained on. |
| `MEM_PROBE_ROWS` | `64` | count |  | How many query rows each probe read issues |
| `MEM_QUOTA` | `128` | entries |  | Entries each owner block may hold |
| `MEM_RECON_HID` | `64` | count |  | Hidden width of the reconstructor that maps a stored key to its expected token code. |
| `MEM_RECON_TOK` | `32` | count |  | Width of the fixed token-code space the reconstructor predicts into. |
| `MEM_REKEY_EVERY` | `200` | Windows |  | Period over which the whole readable store is re-encoded once, so keys track the model as it drifts. |
| `MEM_SRC_SHARE` | `0.5` | fraction 0..1 |  | Share of the store each live source is entitled to (src_share * cap / live sources) |
| `MEM_TOPK` | `8` | entries |  | How many neighbours each retrieval mixes into the returned token distribution. |
| `MEM_USE_DECAY` | `0.98` | fraction 0..1 | domain (0.0, 1.0) | Multiplier applied to every entry's retrieval count when the decay interval elapses. |
| `MEM_USE_DECAY_EVERY` | `20000` | entries |  | How many entries must be WRITTEN before the retrieval counters are decayed. |
| `MEM_VERIFY` | `'selfcon'` | name | choices `'selfcon'`, `'recon'`, `'off'` | Which mechanism judges a stored entry wrong: self-consistency, a fitted reconstructor, or nothing. |
| `MEM_WRITE_GATE` | `0.3` | probability | domain (0.0, 1.0) | Fixed surprise threshold: store an item only when 1 - p_model(true token) is at least this. |
| `MEM_WRITE_MODE` | `'fixed'` | name | choices `'fixed'`, `'adaptive'`, `'quantile'` | Which rule admits a surprising item: a fixed threshold, the additive controller, or the quantile controller. |
| `MEM_WRITE_TARGET` | `0.5` | fraction 0..1 | domain (0.0, 1.0) | Fraction of candidate writes the adaptive and quantile arms aim to keep. |
| `MEM_WRONG_READ` | `True` | on/off |  | Whether the wrong flag excludes an entry from every retrieval, or only from the sweep. |
| `MEM_WRONG_SWEEP` | `False` | on/off |  | Whether the selected wrongness detector DELETES flagged entries or only flags them. |

### OPT (13 levers)

| lever | default | unit | accepts | what it is |
|---|---|---|---|---|
| `OPT_ACCUM` | `1` | Backwards |  | Backward passes accumulated before one optimizer step |
| `OPT_BATCH_WINDOWS` | `1` | Windows |  | How many stream windows are accumulated into one forward/backward |
| `OPT_GRAD_CLIP` | `0.0` | fraction 0..1 |  | Global gradient-norm clip applied to the BASE parameter group before each optimizer step. 0.0 is OFF, which is what every recorded number in this project was measured under. |
| `OPT_LR` | `0.002` | fraction 0..1 |  | Peak learning rate; every rate the system applies is this times a schedule multiplier in 0..1. |
| `OPT_LR_DECAY` | `1.0` | fraction 0..1 | domain (0.0, 1.0) | Strength of a monotone envelope over successive restart peaks, so each cycle keeps its own high phase while the ceiling comes down. |
| `OPT_LR_MIN_FRAC` | `0.05` | fraction 0..1 | domain (0.0, 1.0) | Floor of the cosine as a fraction of peak |
| `OPT_LR_RESTART_DAMP` | `0.5` | fraction 0..1 | domain (0.0, 1.0) | Multiplier on the next restart's swing when the cycle that just ended failed to beat the best held-out it inherited |
| `OPT_LR_RESTARTS` | `True` | on/off |  | Whether the cosine wraps into repeated warm restarts, with a whole number of cycles fitted to the run, instead of holding at the floor. |
| `OPT_LR_SCHED` | `'cosine'` | name | choices `'cosine'`, `'none'` | Selects the rate schedule: the warmup-then-cosine shape, or a constant peak rate for the whole run. |
| `OPT_LR_SHIFT_WARM` | `0` | Steps |  | Re-warm length after a distribution shift the system caused itself, applied as an attenuation of the current cycle. |
| `OPT_LR_WARMUP` | `1000` | Steps |  | Linear ramp from zero to the peak rate at the start of a run, paid once. |
| `OPT_LR_WAVELENGTH` | `0` | Steps |  | Length of one cosine cycle, stated directly in optimizer steps |
| `OPT_WEIGHT_DECAY` | `0.0` | fraction 0..1 |  | AdamW decoupled weight decay, applied to the base optimizer and the encoder optimizer alike. |

### RUN (7 levers)

| lever | default | unit | accepts | what it is |
|---|---|---|---|---|
| `RUN_AMP` | `'off'` | name | choices `'off'`, `'bf16'` | Autocast precision for the LM step: off runs fp32, bf16 runs the step in bfloat16 while memory keys stay fp32. |
| `RUN_BENCH` | `False` | on/off |  | Stop immediately after the training loop and print throughput instead of running the eval battery. |
| `RUN_DEVICE` | `'cpu'` | name | choices `'cpu'`, `'cuda'` | The torch device every module's .to() targets, and the gate on the mixed-precision branch. |
| `RUN_EPOCHS` | `1` | Epochs |  | How many passes over the stream the run makes |
| `RUN_PROFILE` | `False` | on/off |  | Per-component wall-clock attribution of the training step, dumped on the rate cadence and again in the throughput summary. |
| `RUN_SEED` | `0` | count |  | Root seed for the whole run |
| `RUN_TF32` | `True` | on/off |  | Allow TF32 matmul and cuDNN kernels |

### SIG (18 levers)

| lever | default | unit | accepts | what it is |
|---|---|---|---|---|
| `SIG_BIGRAM_DIM` | `512` | count |  | Width of the hashed bigram feature vector used by the frozen-statistic control |
| `SIG_CONTRASTIVE_BATCH` | `48` | count |  | Anchor/positive pairs drawn per InfoNCE step |
| `SIG_COV_WEIGHT` | `0.0` | count |  | Weight on the covariance (decorrelation) term of the same anti-collapse regulariser. |
| `SIG_D` | `64` | count |  | Dimension of the signature vector |
| `SIG_DENSE_WINDOW` | `400` | Windows |  | How long after a detected boundary the encoder stays on the dense cadence before falling back to the idle one. |
| `SIG_FLOOR_KINDS` | `8` | domains |  | Assumed number of distinct kinds of material in the stream |
| `SIG_MODE` | `'learned'` | name | choices `'learned'`, `'bigram'` | Which signature function the run uses: the online contrastive encoder, or the frozen hashed-bigram control. |
| `SIG_POSITIVE_RADIUS_WINDOWS` | `2.0` | count |  | Furthest offset at which the InfoNCE positive is drawn from its anchor, as a MULTIPLE of the loop window |
| `SIG_PROTOTYPE_FRAC` | `0.0` | fraction 0..1 |  | Fraction of the InfoNCE batch replaced by pairs drawn from ONE domain's reservoir, so the encoder is trained on kind-invariance and not only on locality. |
| `SIG_SPACE` | `'bytes'` | name | choices `'bytes'`, `'tokens'` | Alphabet the signature is built over: raw bytes, or the LM's token stream. |
| `SIG_TEMP` | `0.1` | fraction 0..1 |  | InfoNCE softmax temperature: the divisor on the cosine logits that decides how sharply a near-miss counts as a negative. |
| `SIG_TRAIN_EVERY` | `1` | Windows |  | Encoder training cadence while the stream is near a detected boundary |
| `SIG_TRAIN_EVERY_IDLE` | `12` | Windows |  | Throttled encoder cadence once the stream has been stable for longer than the dense window. |
| `SIG_VAR_WEIGHT` | `5.0` | count |  | Weight on the variance hinge that stops the encoder collapsing to a single point. |
| `SIG_WARMUP` | `800` | Steps |  | Budget of unsupervised contrastive steps run before the main loop starts. |
| `SIG_WARMUP_MIN_FRAC` | `0.25` | fraction 0..1 | domain (0.0, 1.0) | Share of the warmup budget that must be spent before the plateau test is allowed to stop it early. |
| `SIG_WARMUP_PLATEAU_EPS` | `0.015` | fraction 0..1 |  | Relative gain in separation below which the adaptive warmup declares the curve flat and stops early. |
| `SIG_WARMUP_PROBE_EVERY` | `500` | Steps |  | How often, during warmup, the separation probe is taken |

### TOK (18 levers)

| lever | default | unit | accepts | what it is |
|---|---|---|---|---|
| `TOK_BUILD_BYTES` | `1000000` | bytes |  | How many bytes are taken from the head of each corpus for the pre-training vocabulary build. |
| `TOK_BUILD_PASSES` | `2` | count |  | How many tally-and-mint passes over the build corpus the pre-training vocabulary build takes. |
| `TOK_CAND_WINDOW` | `1024` | count |  | How many candidates deep the mint ranking is materialized, so a re-ranker has something to choose from. |
| `TOK_DROPOUT` | `0.0` | probability | domain (0.0, 1.0) | Probability of skipping an available merge during a counting segmentation, so byte-level material still reaches the tally. |
| `TOK_FREEZE_AT` | `0` | Windows |  | Window after which no further token is minted |
| `TOK_GROW_BURST` | `6` | tokens |  | How many new tokens are minted at each grow event. |
| `TOK_GROW_EVERY` | `200` | Windows |  | Cadence at which the vocabulary mints a burst of new tokens. |
| `TOK_MAX_BYTES` | `16` | bytes/token |  | The longest byte string a single token may stand for |
| `TOK_MIN_PAIR` | `50` | count |  | How many times an adjacent pair must have been counted before it is a candidate for minting at all. |
| `TOK_MINT_NOVEL` | `0.0` | fraction 0..1 |  | Exponent re-ranking mint candidates by how much a pair has grown since it was last considered |
| `TOK_MINT_PMIN` | `0.0` | probability |  | Minimum p(b\|a) for a merge to be accepted as a unit rather than a frequent collision across a boundary |
| `TOK_MODE` | `'online'` | name | choices `'bytes'`, `'fixed'`, `'online'` | Which tokenization regime the run uses: raw bytes, a vocabulary built once before training, or an online byte-BPE that keeps minting while it trains. |
| `TOK_PROBATION_BY` | `'use'` | name | choices `'use'`, `'embed'` | Which post-mint test decides whether a token keeps its slot: did it get used, or did its learned residual move away from what its bytes say. |
| `TOK_PROBATION_DEADLINE` | `5000` | Windows |  | The window by which a minted token must have earned its appearances, after which it is judged. |
| `TOK_PROBATION_RESIDUAL` | `0.1` | fraction 0..1 |  | Minimum ratio of a token's learned residual to its byte composite for the token to be judged worth its slot. |
| `TOK_PROBATION_USES` | `0` | count |  | How many appearances a newly minted token must earn before it keeps its place in the match table |
| `TOK_RETOK_EVERY` | `3000` | Windows |  | How often the unconsumed stream is re-segmented with the vocabulary as it now stands |
| `TOK_SEED_VOCAB` | `512` | tokens |  | Target vocabulary size the pre-training build aims for, before any online minting. |

### WORLD (11 levers)

| lever | default | unit | accepts | what it is |
|---|---|---|---|---|
| `WORLD_COLLAPSE_W` | `1.0` | fraction 0..1 |  | Weight on the VICReg-style variance+covariance anti-collapse term applied to the encoder's latent. |
| `WORLD_ENABLED` | `True` | on/off |  | Build the world encoder and the dynamics population, and add their terms to the training loss |
| `WORLD_FEEDBACK` | `True` | on/off |  | Condition the base LM on the forecast (h += world_proj(forecast)) instead of leaving the world model as an unused side head. |
| `WORLD_GROW` | `True` | on/off |  | Selection on the population: clone a predictor from the fittest on a forward-loss plateau, and soft-cull predictors whose routing mass has decayed away. |
| `WORLD_HID` | `128` | count |  | Hidden width of the world encoder MLP and of every forward-dynamics predictor MLP. |
| `WORLD_HORIZON` | `1` | tokens |  | Prediction horizon in stream positions: the latent at t is trained to predict the latent at t+horizon. |
| `WORLD_LAT` | `32` | count |  | Width of the shared latent world-state the encoder produces and every dynamics predictor operates in. |
| `WORLD_N0` | `3` | count |  | Number of dynamics predictors the population is built with before any growth. |
| `WORLD_NMAX` | `6` | count |  | Hard cap on the number of LIVE dynamics predictors |
| `WORLD_PREDICT_W` | `0.1` | fraction 0..1 |  | Weight on the population forward-prediction (plus load-balance) term in the total training loss. |
| `WORLD_ROUTE_D` | `24` | count |  | Width of the routing key space: the output width of qproj and the length of each predictor's key vector. |
