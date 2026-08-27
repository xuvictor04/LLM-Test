# BLUEPRINT — Rebuildable Spec (wiring-first)

Purpose: reconstruct the system from this document *independently*, then diff your rebuild's wiring against
this reference to surface where connections diverge. So this is organized as **module contracts** (in → out,
with tensor shapes) + the **wiring graph** that connects them + the **knob→wiring map**. Narrative/rationale
lives in `OVERVIEW.md`; this file is only *what connects to what*.

Conventions: `B`=batch, `L`=sequence length, `d`=`D_MODEL`, `V`=active vocab (grows), `VMAX`=vocab ceiling,
`N`=current expert count (per SparseMoE layer, grows/shrinks), `M`=`M_EMBED`, `k`=`MOE_K`. Every module lists:
**Contract** (signature + shapes) · **Wiring** (internal op order) · **Params** · **Knobs** · **Diff-points**
(the wiring choices most likely to come out different on a rebuild).

---

## 0. GLOBAL WIRING GRAPH (the forward)

```
x:(B,L) int tokens, posnov:(B,L) float novelty
  novs = posnov.mean(dim=1)                                    # (B,)
  em, wA, gist = EMBED(x, posnov)                              # em:(B,L,d)
  h0 = ENCODE(em)                                              # (B,L,d)
  if CORRECT_AT=="embed":  h0 = h0 + CORRECT_NET(h0)           # residual hook  (post-tokenizer)
  hf, depth, enc, mass = FABRIC(h0, gist, novs)                # hf:(B,L,d); depth/enc/mass: scalar aux
  if CORRECT_AT=="fabric": hf = hf + CORRECT_NET(hf)           # residual hook  (mid)
  lg, conf, mg, mtp, recon = READOUT(hf, gist, novs)           # lg:(B,L,V)
  cpl = FABRIC.last_cpl (sparse)  OR  counterpart_loss(h0) (dense/off -> 0)
  return lg, aux{depth,enc,mass,gist,hf,wA,conf,mg,cpl,lb,mtp,recon}
```
Wiring invariants: **two residual hook sites** (embed, fabric), gated by one knob. **All heads read the same
`h_final`** produced inside READOUT (not `hf` directly). `cpl` source **branches on fabric mode**.

---

## 1. EMBED

**Contract:** `embed(x:(B,L), posnov:(B,L)) -> em:(B,L,d), wA:(B,M), gist:(B,d)`

**Wiring:**
```
base_em = init_emb(x)                                         # (B,L,d)   Embedding(VMAX,d)
g = base_em.mean(dim=1)                                       # (B,d)     routing summary
if M>0:                                                       # MoE embedder layer
    wA = softmax(routerA(g), -1)                             # (B,M)     Linear(d,M)
    sp = stack([spec_i(x) for i in 0..M-1])                 # (M,B,L,d) each Embedding(VMAX,d)
    em = base_em + sum_i wA[:,i] * sp[i]                     # routed sum
else:
    wA = zeros(B,0); em = base_em
if COMPOSE_EMB>0:                                             # compositional embedding
    em = em + COMPOSE_EMB * atom(parts[x]).mean(dim=2)      # parts[x]:(B,L,2) -> atom:(B,L,2,d) -> mean
if SENSE_K>0:                                                # sense book
    gist_ctx = per-position causal gist (if SENSE_POS) else g broadcast
    branch = sense-select(x, gist_ctx)                       # picks 1 of SENSE_K sub-meanings/token
    em = em + branch
gist = causal/mean gist of em                                # (B,d) fed to fabric + readout
return em, wA, gist
```
**Params:** `init_emb`(VMAX×d), `spec`[M](VMAX×d), `routerA`(d→M); if compose: `atom`(VMAX×d) + buffer
`parts`(VMAX×2); if sense: `sense`(VMAX×SENSE_K×d) + sense router.
**Knobs:** `M_EMBED`, `SENSE_K`, `SENSE_POS`, `COMPOSE_EMB`.
**Diff-points:** (a) compositional term is **additive** and **one-level** (uses `parts[x]` = the token's *2
immediate constituents*, mean-pooled — not recursive to bytes); (b) `parts[base<256] = [self,self]`, filled
to `[a,b]` only on minting; (c) sense is **additive** and independent of MoE routing.

---

## 2. ENCODE

**Contract:** `encode_(em:(B,L,d)) -> h0:(B,L,d)` — positional/initial encode before the fabric.
**Diff-points:** whether positional info is added here vs inside the fabric; residual structure.

---

## 3. CORRECT_NET (stage-agnostic correction hook)

**Contract:** `correct_net(h:(B,L,d)) -> (B,L,d)`, applied as **residual**: `h = h + correct_net(h)`.
**Wiring:** `Linear(d,d) -> GELU -> Linear(d,d)`, **last layer zero-initialized** (starts as identity).
**Knobs:** `CORRECT_AT` ∈ {none, embed, fabric} — selects the site (or off). One shared module, one site.
**Diff-points:** identity-init is essential (else it perturbs a trained-elsewhere signal); it's a *generic*
residual corrector trained via denoise/recon, not a bespoke algorithm.

---

## 4. FABRIC (two implementations behind one contract)

**Contract:** `fabric(h0:(B,L,d), gist:(B,d), novs:(B,)) -> hf:(B,L,d), depth:scalar, enc:scalar, mass:scalar`
`FABRIC` knob selects `dense` (Greg) or `sparse` (Barry). Both return the same tuple; aux differs.

### 4a. DENSE (Greg)
Recurrent stack of dense experts with ponder/adaptive-depth (→ `depth`), re-encode (→ `enc`, proven dead
weight, default off), counterpart invertibility. `mass` = routing mass diagnostic.

### 4b. SPARSE (Barry) = ModuleList of `FABRIC_LAYERS` × SparseMoE, applied in sequence with residuals
Each layer consumes/produces (B,L,d); `enc`/`depth` are 0/const for sparse; `mass` from load. `last_cpl` set
if counterparts on (sum of per-layer invertibility). `last_lb` = sum of per-layer load-balance losses.

**SparseMoE.forward (per layer):** `x:(T,d)` where `T=B*L`
```
logits = router(x)                                            # (T,N)   Linear(d,N,bias=False)
probs  = softmax(logits, -1)                                  # (T,N)
gate, idx = topk(probs, k)                                    # (T,k) each token's k experts + weights
C = ceil(CAP_FACTOR * T * k / N)                              # per-expert capacity
# build dispatch: for each (token,slot) route to expert idx; drop overflow beyond C
disp_tok, disp_slot, eidx = capacity_assign(idx, C)          # index tensors (no dense mask)
xin = x[disp_tok]                                             # gather routed tokens
out = VecExperts(xin, eidx)                                   # batched bmm over the stacked bank -> (~N*C,d)
contrib = out * gate[disp_tok,disp_slot][:,None]             # apply gate
y = zeros(T,d).index_add(0, disp_tok, contrib)              # scatter back
lb = N * (frac(counts) * probs.mean(0)).sum()               # Switch load-balance
# selection signals (EMA), used by growth/cull:
self.contrib = 0.98*self.contrib + 0.02*(per-expert gated output energy)
self.traffic = 0.98*self.traffic + 0.02*(per-expert token counts)
return x + y, lb                                              # RESIDUAL around the block
```
**Params:** `router`(d→N), `experts`=VecExperts, optional `inv`=VecExperts(hidden=2d).
**Knobs:** `MOE_K`, `FABRIC_LAYERS`, `CAP_FACTOR`, `LB_COST`(applied in loss), `COUNTERPARTS`,
`EXPERT_HIDDEN_MULT` (expert hidden dim), `CULL_METRIC` (which of contrib/traffic drives `score()`).
**Diff-points:** (a) dispatch is **index-based with a hard capacity C** (overflow dropped), not a dense mask;
(b) experts run as **one bmm over a stacked weight bank**, never a Python loop; (c) the **residual is around
the whole block**; (d) `contrib`/`traffic` are **EMA buffers**, recomputed every forward, and are the ONLY
link between the fabric and the growth/cull logic.

### VecExperts (the stacked expert bank)
**Contract:** `forward(xin:(T',d), eidx:(T',)) -> (T',d)` — each row processed by its expert.
**Wiring:** stacked params `W1:(N,d,h)`, `b1:(N,h)`, `W2:(N,h,d)`, `b2:(N,d)` with `h=EXPERT_HIDDEN_MULT*d`;
compute per-expert via gather+bmm: `relu(xin·W1[eidx]+b1[eidx])·W2[eidx]+b2[eidx]`.
**Mutations to the bank (structural, see §7):** `grow(add, parent, strength)` appends rows (parent's rows +
noise, or random); `remove(idx)` drops a row. Router and `inv` grow/shrink in lockstep.
**Diff-points:** parent-based (mutation) vs random growth; whether router/inv rows stay index-aligned with
expert rows through grow/remove (they must).

---

## 5. READOUT (+ heads)

**Contract:** `readout(h_fab:(B,L,d), gist:(B,d), novs:(B,)) -> lg:(B,L,V), conf:(B,), mg:(B,), mtp, recon`

**Wiring:**
```
recall, conf = mem.read(gist)                                # mirror memory recall + confidence
mg = sigmoid(gate_lin(cat([conf, novs], -1)))               # (B,) recall gate
h_final = h_fab + (mg * recall)[:,None,:]                    # gated recall added to hidden  <-- all heads read THIS
lg    = linear(h_final, head.weight[:V], head.bias[:V])     # (B,L,V)  main next-token logits
mtp   = [linear(h_final, mh.weight[:V], mh.bias[:V]) for mh in mtp_heads]  or None   # MTP_K-1 heads
recon = linear(h_final, recon_head.weight[:V], recon_head.bias[:V])       or None   # denoise-AE head
return lg, conf, mg, mtp, recon
```
**Params:** `mem` (mirror), `gate_lin`(2→1), `head`(d→VMAX, sliced to V), `mtp_heads`[MTP_K-1](d→VMAX),
`recon_head`(d→VMAX or None).
**Knobs:** `MEMORY`, `MTP_K`, `RECON`.
**Diff-points:** (a) heads are **sliced to active V** (`[:V]`) every call — vocab grows but tables are
pre-allocated to VMAX; (b) recall is **gated then added** to `h_fab` to form `h_final`; (c) MTP heads predict
**offset tokens** (head i → token t+2+i), recon head predicts **same-position** clean token.

---

## 6. LOSS WIRING (assembled in the training loop)

```
loss  = ce(lg, x)                                            # next-token CE; label_smoothing=LABEL_SMOOTH
      + PONDER*aux.depth + REENC_COST*aux.enc + COUNTERPART_COST*aux.cpl + LB_COST*aux.lb
      + (Z_LOSS>0)     * Z_LOSS * (logsumexp(lg[:,:-1], -1)**2).mean()
      + (MTP_K>1)      * mean_i[ ce(mtp_i[:, :-(i+2)] , x[:, (i+2):]) ]     # offset targets
      + (RECON>0)      * RECON * ce(recon.reshape(-1,V), x.reshape(-1))     # per-position clean target
loss  = loss / GRAD_ACCUM
```
Notes: `ce` = shifted next-token CE. **Eval uses TRUE CE (no label smoothing)** so OOD bits/byte stays
comparable. **The recon target is the CLEAN `x`** even when the forward input was corrupted (denoising).
**Diff-points:** which aux terms are summed and with which coefficients; MTP target offsets; recon uses same-
position (not shifted) targets.

---

## 7. STRUCTURAL DYNAMICS WIRING (things that change the graph over time)

### 7a. Vocab growth (tokenizer mints a token → model activates a row)
```
mint: DynamicTokenizer.maybe_grow() returns (pair_count, a, b) when a byte-pair a+b crosses MIN_PAIR (V<VMAX)
grow_vocab(a,b):  v = self.V
    init_emb[v] = mean(init_emb[a], init_emb[b]);  each spec[v] = mean(...)
    if sense_slots==0: sense[v] = mean(sense[a],sense[b])
    head[v] = mean(head[a],head[b]);  each mtp_head[v] = mean(...);  recon_head[v] = mean(...)
    if COMPOSE_EMB>0: parts[v] = [a,b]                 # record the token's definition
    base.grow_vocab(a,b); V += 1
if MP_WORKERS>0: broadcast (a,b) to worker vocab replicas
```
**Diff-points:** EVERY head/table that has a VMAX row must get its `[v]` mean-initialized from `[a],[b]`
(init_emb, spec, sense, head, mtp_heads, recon_head) — a rebuild that forgets one desyncs that table;
`parts[v]=[a,b]` is the compositional link.

### 7b. Expert growth / mutation (add_node)
```
add_node():  for each SparseMoE layer: layer.grow(1, mutate=MUTATE, strength=MUTATE_STRENGTH)
    grow: parent = argmax(score()) if MUTATE else None; append expert row (parent+noise | random);
          append router row + inv row (parent+noise | random); contrib/traffic get ~mean seed for new row
```
### 7c. Contribution cull + paired turnover (evolutionary selection)
```
every PRUNE_EVERY steps, if PRUNE_ECO and g>=GROWTH_START and pop>NMIN:
    idx = argmin over experts of sum_layers( layer.score() )        # score() = contrib|traffic|blend
    for each layer: layer.prune(idx)   (drop expert+router+inv row idx, resize contrib/traffic)
    then add_node()                    # PAIRED respawn (mutation of best) -> constant-size turnover
    rebuild optimizer
```
### 7d. Plateau growth (GrowthController)
```
if g>WARMUP_STEPS and g>=GROWTH_START:
    act = gc.decide(step, fabric_loss, usage)  -> spawn | prune | depth | none
    apply -> rebuild optimizer
```
**Diff-points:** (a) growth is **gated by both `WARMUP_STEPS` and `GROWTH_START`** (curriculum foundation
phase); (b) cull and respawn are **paired** (net-constant population) — decoupling them collapses the pool;
(c) `score()` metric is the single switch for what "weakest/best" means.

---

## 8. TRAINING-STEP WIRING (one iteration)

```
gstep = total + step
set param_group lr = LR_AT(gstep)                            # warmup -> {constant|cosine|wsd}
fetch batch:  MP producer.get()  |  prefetch queue.get()  |  dyn_batch()   (mutually exclusive)
x_cpu = fresh (+ replay rows if REPLAY)
if CTX_START>0: x_cpu = x_cpu[:, :CUR_LEN(gstep)]           # curriculum seq-length ramp
x   = x_cpu.to(dev)                                          # CLEAN target
x_in= corrupt(x_cpu) if DENOISE>0 else x                    # corrupt INPUT only (sub|swap|mix)
lg, aux = model(x_in, surprise.score_pos(x_cpu))           # forward on (maybe) corrupted input
loss = ASSEMBLE (see §6)
(loss/GRAD_ACCUM).backward()
if (gstep+1) % GRAD_ACCUM == 0: clip_grad_norm; opt.step(); opt.zero_grad(); wema_update()
mint loop (§7a): maybe_grow -> grow_vocab -> broadcast
structural (§7b/c/d), gated by GROWTH_START
if gstep % EVAL_EVERY == 0:
    swap-in EMA weights (if EMA_DECAY>0) -> evaluate held/OOD -> save best.pt (=EMA) -> restore LIVE -> save ckpt.pt (=LIVE)
```
**Helper contracts:**
`LR_AT(g)`: `g<LR_WARMUP -> LR*(g+1)/LR_WARMUP`; else constant | cosine(to LR*LR_MIN_FRAC) | wsd(flat then
linear decay over last WSD_DECAY_FRAC).
`CUR_LEN(g)`: `CTX_START + (CTX-CTX_START)*g/CTX_RAMP_STEPS`, capped at CTX (off if CTX_START<=0 or >=CTX).
`corrupt(x)`: with prob DENOISE per token (never pos 0): substitute random token (sub/mix) and/or swap
adjacent (swap/mix); returns corrupted copy.
`wema`: EMA of every named param, **re-seed on shape change** (grow/cull); swap-in for eval only; best.pt =
EMA weights, ckpt.pt = live weights (+ optimizer state) so resume is correct.
**Diff-points:** (a) **input corrupted, target clean** (denoise); (b) **best.pt=EMA, ckpt.pt=live** (mixing
them breaks resume); (c) LR set **every step** (not only during warmup); (d) grad-accum divides loss and gates
the step; (e) EMA swap must restore live before continuing training.

---

## 9. TOKENIZER (DynamicTokenizer) — the emergent vocab

**Contract:** `segment(byte_list, count=bool, dropout=None) -> [token_ids]` (lossless, greedy-longest with a
first-byte max-length prune + per-window id-keyed cache); `maybe_grow() -> (cnt,a,b)|None`;
`apply_merge(a,b)` (append a decided merge, for worker replicas); `decode(ids) -> str`; `id2bytes[i] -> bytes`.
**Wiring to training:** `segment(count=True)` tallies byte-pairs (vectorized `np.unique`); `maybe_grow` mints
the top pair ≥ `MIN_PAIR` while `vocab<VMAX`, appending `id2bytes[v]=id2bytes[a]+id2bytes[b]`. Cache valid
because vocab only grows; small `refresh_frac` re-segments to fold in new tokens.
**Multiprocess variant** (`MP_WORKERS>0`, `mp_tokenizer.py`): spawn workers with vocab replicas over an
mmap'd byte-window corpus; main pulls batches (plain lists), tallies+mints, broadcasts merges back.
**Diff-points:** greedy-longest vs BPE-merge-order segmentation (must match for cache validity + losslessness);
where pair counting happens (main tallies the batch it consumes); vocab-only-grows invariant.

---

## 10. KNOB → WIRING MAP (what each toggle rewires)

| Knob | Rewires |
|---|---|
| `FABRIC` | dense recurrent block ↔ sparse SparseMoE stack (§4) |
| `M_EMBED` | number of routed embedding tables added to `base_em` (§1) |
| `SENSE_K`/`SENSE_POS` | additive per-token sub-meaning branch + its context source (§1) |
| `COMPOSE_EMB` | adds `atom(parts[x]).mean` to `em`; enables `parts` recording in grow_vocab (§1,§7a) |
| `CORRECT_AT` | inserts one residual `correct_net` at embed OR fabric site (§0,§3) |
| `MOE_K`/`CAP_FACTOR` | top-k count + per-expert capacity in dispatch (§4b) |
| `FABRIC_LAYERS` | how many SparseMoE layers in the stack (§4b) |
| `EXPERT_HIDDEN_MULT` | expert hidden dim in VecExperts (§4) |
| `COUNTERPARTS` | adds inverse bank + invertibility loss term (§4b,§6) |
| `MUTATE`/`MUTATE_STRENGTH` | growth appends parent-copy+noise vs random (§7b) |
| `PRUNE_ECO`/`PRUNE_EVERY`/`NMIN` | enables paired cull+respawn turnover (§7c) |
| `CULL_METRIC` | switches `score()` = contrib | traffic | blend (§4b,§7c) |
| `GROWTH_START` | gates all structural change until foundation phase ends (§7,§8) |
| `CTX_START`/`CTX_RAMP_STEPS` | truncates batch to a growing sequence length (§8) |
| `DENOISE`/`DENOISE_MODE` | corrupts the forward INPUT; loss stays vs clean target (§8,§6) |
| `RECON` | adds recon head + per-position reconstruction loss; enables `reconstruct()` (§5,§6) |
| `MTP_K` | adds MTP heads + offset-target aux loss (§5,§6) |
| `LR_SCHEDULE`/`LR_MIN_FRAC`/`WSD_DECAY_FRAC` | shape of `LR_AT(g)` (§8) |
| `OPTIM`/`LION_LR` | AdamW ↔ Lion in `make_opt` (§8) |
| `LABEL_SMOOTH`/`Z_LOSS`/`GRAD_ACCUM`/`EMA_DECAY` | loss terms + step/eval wiring (§6,§8) |
| `MP_WORKERS`/`PREFETCH` | batch-production path (§8,§9) |
| `DATASET`/`DIVERSE` | corpus assembled by setup_lambda.sh/fetch_data.py (data, not model) |

---

## 11. REBUILD & DIFF PROCEDURE

1. Implement each module (§1–5, §9) to its **Contract** — ignore internals, match shapes.
2. Wire them per §0 (forward) and §6/§8 (loss/step).
3. Add structural dynamics §7 (vocab grow, expert grow/mutate/cull, curriculum gates).
4. Diff against this spec at the **Diff-points** first — those are where independent rebuilds most often
   diverge (dispatch strategy, residual sites, which tables grow, EMA/ckpt split, corrupt-input/clean-target,
   paired turnover, head slicing to V, compositional one-level additivity).
5. Behavioral equivalence check: run `test_tokenizer.py` (losslessness must PASS) and a tiny cumulative run
   with all knobs on (must reach DONE + clean resume) — the same checks used to validate the reference build.

Anything not pinned here (exact init scales, layernorm placement, gist construction details, GrowthController
thresholds) is a **free variable** — divergence there is expected and is exactly the "wiring difference" this
document is meant to expose.
