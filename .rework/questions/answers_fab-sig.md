## Q-FAB-1 — port the transition hop arm, or drop `FAB_HOP_MODE`?

**What I read**
`docs/04_CONTRACT.md:886` (the UNCONSUMED row) and `:1036-1042` (the question). `src/fabric/levers.py:165-176` (`hop_mode`), `:184-190` (`hop_sup`), `:192-198` (`hops`), `:200-211` (`depth0`), `:379-401` (the three balance levers), `:485-492` (`spawn`). `src/fabric/api.py:34-66` (build), `:69-131` (forward, incl. the `LEVERS READ:` list at `:109-115`), `:344-361` (counters), `:363-378` (state_dict). `self_organize.py:2567-2599` (entry logits and where `ban1` lands), `:2618-2694` (the soc loop), `:2700-2740` and `:2810-2840` (the transition branch), `:1907` (`ctrl`), `:2819` (`_hops.append`). `.rework/CENSUS.md:174-176`. `.rework/ISSUES.md:24-33` (C2, C3). `tests/test_census.py:75-140` (DEPARTURES), `tests/test_contract.py:164-183` (K4's UNCONSUMED reader), `:348-378` (K1). `.rework/PLAN.md:100` (G10). `docs/proposals/02_ROUTER_RECURSION.md:30-56, 145`.

**What is true today**
The question's position holds, and three of its supporting facts I verified independently:

1. `hop_mode` genuinely has no reader. It is absent from `FAB.forward`'s `LEVERS READ:` list (`fabric/api.py:109-115`) and from `FAB.counters`' (`:352-355`). K4 passes only because the UNCONSUMED table at `docs/04_CONTRACT.md:886` supplies a ≥40-char reason — `tests/test_contract.py:167-182` is the parser that admits it. I ran the suite: `test_contract` prints `12 checks + 34 self-test cases, 0 failing`.
2. `hop_sup` is inert on the shipped path for the reason recorded. `grep -n "s._hops.append"` over 9,859 lines returns **exactly one hit, `self_organize.py:2819`**, inside the transition branch. The soc loop at `:2618-2694` never appends. M27 is confirmed, not merely asserted.
3. The 0.533-vs-0.058 evidence is **not** contaminated by C3, and that distinction matters. C3 voids `fab.contrib` (`self_organize.py:2599` applies `ban1` to `_elg`, and the soc loop at `:2620` re-routes from `entry_logits(..., ban=ban)` with `ban1` nowhere in it, so the walk is bit-identical for every candidate — verified by reading). `H(hop1|hop0)` is a conditional entropy over hop choices, not a leave-one-out, so it never passed through `contrib`. The transition arm's own source carries a *second* independent indictment at `self_organize.py:2731-2734`: "the compute path reached 25% of the experts under society and 8% under chaining, because mass CONCENTRATES as it flows." Two measurements, neither routed through the void counterfactual, both against the transition walk.

Two things the question does **not** say that I found:

4. **The frozen surface already leaks the transition arm.** `fabric/api.py:364-365` declares `FAB.state_dict` saves "`... q_entry, nov_proj, ctrl`". `ctrl` exists only on the transition arm (`self_organize.py:1907` mints it, `:2827` is its only read, inside the transition branch). `FAB.build`'s allocation list (`fabric/api.py:37-40`) creates no `ctrl`. So today the contract promises to checkpoint a parameter nothing builds.
5. The C2 repair does **not** depend on this question. `fabric/api.py:109-115` lists `balance, bal_floor, bal_warm` as read by `forward`, and `:120` declares `fab.balance_nonzero` as "THE C2 ALARM". P4 computes the balance term inside the soc loop from the per-hop distribution (the transition arm's `bal = bal + N * (nm.mean(0)**2).sum()` at `self_organize.py:2720` is one expression, and `_cc[:, :N]` at `:2630` is the soc equivalent). So "three levers were inert only because the transition arm was not the default" is already answered without porting anything.

**The options**
- **(a) Port both arms.** Buys: the learned successor walk as a selectable arm; keeps `ctrl` honest. Costs: a `SRC_p` (cap, dk) parameter that `build` must preallocate and `remove()`'s renumbering must carry; the `R` softmax with its top-k source trick (the full transition is 1.07 GB at N=4096, `self_organize.py:2828-2830`); `ctrl`; per-hop query bookkeeping (`_hopq`); a second set of loss terms; and — the real cost — **two forward paths inside one function**, which is what `fabric/api.py:20-24` ("ONE FORWARD PASS, BOTH ARMS … The old tree had two") exists to forbid. Every one of ~20 FAB DID-IT-FIRE counters would become arm-conditional.
- **(b) Port `soc` only; drop the lever; make `hop_sup` reachable by appending per-hop states on the soc loop.** Buys: one forward path, one meaning per counter, `hop_sup` live, `ctrl` deleted from `state_dict`. Costs: the learned-successor idea leaves the tree; recovering it later is a new census row.
- **(c) Keep the lever as a startup refusal.** Buys nothing. Costs: a knob whose only effect is an error message, printed as a live capability in the generated `docs/04_LEVERS.md`.

**Recommendation**
**(b).** The tree's own recommendation, and I verified rather than repeated it.

The decisive point is not the 0.533 bits — that number is real but it is a measurement of an arm, and the owner has ruled that a mechanism never observed to fire is not thereby proven useless. The decisive point is that **the transition arm is a second forward path**, and `fabric/api.py:20-24` records what the last second forward path cost: "SUFFICIENCY called `fab.society()` unconditionally while the shipped default was the looped path, which is how '479 experts buy -0.002 b/B' came to be a measurement of a forward path the run never trained (D1, point 2)." Porting the arm re-creates, deliberately, the structure D1 point 2 names as the reason the fabric's headline number was void.

`hop_sup` on the soc loop is genuinely cheap and I checked why: at the shipped `hop_vote=True`, the soc loop already forms `head(s.norm(_O2[:, q]))` per hop for the vote (`self_organize.py:2675-2680`), so the per-hop logits exist. Deep supervision is a CE against `targets` on tensors already in hand. With `hop_vote=False` it costs one `head` call per hop.

**Why it fits the framework**
- **Frozen signatures:** `hop_mode` is named in no `LEVERS READ:` list, so dropping it moves **no signature and no ```contract line**. K1 does not see it. It is the cheapest possible drop.
- **DID IT FIRE:** option (c) is the armed-but-inert family with better manners — and worse, it is a *reachable* startup error, which reads to the ledger as a live gate. Option (a) makes ~20 counters arm-conditional on a lever, which is the C2 shape ("a cadence whose value silently means nothing on one of two paths", `fabric/levers.py:476-478`) generalised to a whole package.
- **The ownership spine:** nothing here crosses a package. The drop is entirely inside FAB plus two bookkeeping files.
- **What it would break the other way:** porting the arm would require `FAB.forward` to reach `hop_mode`, adding it to `LEVERS READ:` — legal — but would then make `fab.hops_taken`, `fab.balance_nonzero`, `fab.explored_rows`, `fab.discovered`, `fab.spawned` and `fab.hopsup_applied` each need a per-arm reachability statement, and the survey's 57 armed-but-inert records are precisely what happens when that is not done for every one.

**What changes**
1. `src/fabric/levers.py:165-176` — delete the `hop_mode` Lever. **No signature moves.**
2. `docs/04_CONTRACT.md:886` — delete the `FAB.hop_mode` row from §4 UNCONSUMED (K4 reads it; leaving it names a lever that no longer exists).
3. `tests/test_census.py` DEPARTURES — add `("fabric", "CHAIN_ROUTE"): dict(census="FAB_HOP_MODE", lands=None, where=..., why=...)`. This is required, not optional: N1 (`tests/test_census.py:224`) demands a lever *or* a departure for every renamed row, and `.rework/CENSUS.md:174` classifies `CHAIN_ROUTE` as **rename**. The `("encoder","SIG_WIN")` entry is the shape to copy — it is the existing `lands=None` precedent.
4. `docs/dropped_levers.md` — **this file does not exist** (`ls docs/` returns `02_OPERATIONS.md`, `03_WIRING.md`, `04_CONTRACT.md`, `proposals/`). PLAN's G10 (`.rework/PLAN.md:100`) requires "each drop requiring a line in `docs/dropped_levers.md`". The orchestrator must create it, with the 0.533/0.058 measurement and the 25%-vs-8% coverage measurement as the two reasons. The *enforced* surface is DEPARTURES; the *promised* surface is this file; both are owed.
5. `src/fabric/api.py:365` — delete `ctrl` from `state_dict`'s parameter list. One word. Keep `q_entry` (`self_organize.py:2557`, `:2564`) and `nov_proj` (`:2554`), which both paths use.
6. P4 body work, already specified and not a decision: append per-hop `h` inside the soc loop so `hop_sup` and `fab.hopsup_applied` are reachable; compute the balance term inside the soc loop so `fab.balance_nonzero` can be nonzero.

**Confidence**
**High** on the drop; **high** on items 1-2 and 5-6; **medium** on item 3's exact key, which depends on how `tools/lever_census.py` spells the family for `CHAIN_ROUTE` (I read it as `fabric` from `.rework/CENSUS.md`'s section header at line 94). What would raise it: running `test_census` after the edit — it is the check that would catch a wrong key.

**Literature**
**Bore, and it points the same way.** [Chain-of-Experts (Wang et al., 2506.18945)](https://arxiv.org/abs/2506.18945) is the closest published analogue of this exact choice: it processes tokens iteratively through a chain of experts *within* a layer using **a dedicated router at each iteration, so tokens re-evaluate and select different experts each step** rather than being statically assigned — this is `hop_mode="soc"`, and it is the configuration reported to reduce validation loss (1.20 → 1.12 vs standard MoE) and to make 2× iterations match 3× width. The static-successor structure (`transition`) is the one CoE explicitly moves away from. This is assistance, not authority: it does not know this tree's `ctrl` or its counter discipline, and the framework argument above stands without it. It does mean the recommendation is not sacrificing a design the field currently prefers.

Sources: [Chain-of-Experts](https://arxiv.org/abs/2506.18945)

---

## Q-FAB-2 — does the fabric gain the merge?

**What I read**
`docs/04_CONTRACT.md:887` (UNCONSUMED row) and `:1044-1049` (the question). `src/fabric/levers.py:726-737` (`merge_dist`), `:636-646` (the selection group header), `:667-684` (`cull_frac`, `grace`). `src/fabric/api.py:34-66` (build, incl. the ZERO-INIT sentence), `:168-201` (contribution), `:203-256` (manage), `:254-311` (grow_check), `:363-378` (state_dict / `remove()`). `src/memory/api.py:25-63` (open_store, blocks), `:66-112` (write), `:114-140` (read), `:207-234` (apply_domain_plan). `src/spine/assemble.py:680-695` (`_owner_blocks`), `:722-742` (the two irreducible FAB→MEM couplings). `src/spine/compose.py:1218-1233` (FAB.contribution's deferral), `:815-836` (the `owners` join). `self_organize.py:3061-3085` (the legacy merge), `:2544-2562` (`remove()`'s swap-with-last). `.rework/CENSUS.md:73`.

Resolved values from `assemble.build(environ={})`: `LM.width=128`, `FAB.rank=8`, `FAB.slots=4096`, `MEM.owners=64`, `MEM.d_owner_blocks=64`, `MEM.d_capacity=8192`.

**What is true today**
**The escalation's precondition is false, and this is the finding that changes the answer.** The contract escalated Q-FAB-2 because "memory ownership is `expert_id % n_own`, so merging two experts changes which owner block holds whose entries" and therefore the merge needs "one named MEM entry point, *reassign the entries owned by expert i to expert j*". Three verified facts dismantle that:

1. **`MEM.read` is global.** `memory/api.py:117-119`: "Excludes inactive entries and entries flagged by the active wrongness detector when `wrong_read` is set, **AND NOTHING ELSE — reads stay GLOBAL across owner blocks even when writes are partitioned.** That asymmetry is the design: knowledge is owned but not walled off." No entry becomes unreadable when an expert disappears. Nothing to reassign for retrieval.
2. **MEM has no per-expert ownership to reassign.** `spine/assemble.py:725` computes `d_owner_blocks = _owner_blocks(FAB.slots, MEM.owners) = max(1, min(4096, 64)) = 64`. `assemble.py:728-732` states it as an irreducible fold: "expert ids run to the slot count (4096) while the store has MEM_OWNERS (64) partitions, so 32 experts shared each partition and 'per-expert memory' was per-64-buckets memory." An entry's owner is its *row index* (`memory/api.py:28-29`, block b owns rows `[b*quota, (b+1)*quota)`). "The entries owned by expert i" is not a set MEM can name; at the shipped defaults 64 experts share every block.
3. **A cull already does everything a merge would do to MEM, and ships.** `MEM.write` narrows the candidate slot set by owner (`memory/api.py:76-78`), so removing expert `b` only changes where *future* writes for that material land. `remove()`'s swap-with-last (`fabric/api.py:371-374`, `self_organize.py:2546-2562`) renumbers every surviving expert above the hole — which changes `expert_id % 64` for that expert too. The merge's MEM blast radius is **strictly smaller** than the cull's: it removes one id and preserves the survivor's.

**The real hazard is in weight space, and neither the census nor the contract names it.** The legacy merge is `self_organize.py:3083`:
```
s.bank.A[a] = 0.5 * (s.bank.A[a] + s.bank.A[b]); s.bank.B[a] = 0.5 * (s.bank.B[a] + s.bank.B[b])
```
An expert's function is ΔW = A·B. Averaging the *factors* gives
`ΔW_merged = ¼(A₁B₁ + A₁B₂ + A₂B₁ + A₂B₂)`, not the intended `½(A₁B₁ + A₂B₂)`. Two consequences: the intended contribution is **halved**, and two cross terms `A₁B₂`, `A₂B₁` are injected that correspond to no learning either expert did. And the factors are not aligned by construction — `fabric/api.py:37-39` says A and B are **ZERO-INIT** at birth with no shared basis, so nothing ties expert a's rank-slot 3 to expert b's. **The census's headline claim — "both experts' learning survives where culling destroys it" — is not supported by its own arithmetic.**

Fourth fact, on the *gate*: `merge_dist` is a cosine distance in **identity space** (`cent`), i.e. routing similarity. `div_w` (`fabric/levers.py:414-423`) actively *pays* two co-routed experts for producing **different outputs**. Merging on centroid proximity while paying for output divergence is an internal contradiction: `div_w` manufactures exactly the pairs `merge_dist` would consume.

Fifth: `FAB.contribution` is **deferred** (`spine/compose.py:1218-1233`) for want of `candidates` and `baseline_logits_fn`, so the output-space redundancy signal is unavailable at P4.

**The options**
- **(a) Drop the lever** to the census, per its own condition (`fabric/levers.py:733-737`). Buys: no unmeasured behaviour change; one fewer mechanism. Costs: goal B loses the only merge-rather-than-kill path in either population; the domain population still merges, so the fabric stays the odd one out.
- **(b) Implement the legacy merge verbatim** — average A and B, sum `use`, merge centroids, drop `b`. Costs: the arithmetic above; ships a mechanism whose claim is false.
- **(c) Implement the merge in ΔW space at fixed rank.** Compute the best rank-`r` approximation of `ΔW_a + ΔW_b` via thin QR of `[A_a | A_b]` (d × 2r) and `[B_a | B_b]ᵀ`, then an SVD of the 2r × 2r core — `O(d·r²)`, at `d=128, r=8` a few thousand flops. Write into `A[a], B[a]`; `use[a] += use[b]`; `dom_of[a] |= dom_of[b]`; `cent[a] = normalize(cent_a + cent_b)`; `remove(b)`. Report the **truncation residual** `‖ΔW_a+ΔW_b − ΔŴ‖ / ‖ΔW_a+ΔW_b‖`. Costs: one new arithmetic; the residual counter. Buys: the claim "both experts' learning survives" becomes a *measured* number instead of a slogan.
- **(d) Mint a MEM entry point** as the contract proposed. Costs: a new frozen signature on a package that cannot name the set it would operate on. Buys: nothing verified.

**Recommendation**
**(c), implemented inside `FAB.manage`, with NO MEM entry point.** Option (d) is refused on the facts above; option (b) ships a false claim; option (a) is the correct fallback only if the owner rejects (c).

Three implementation choices that follow from what I read and that the contract's one-line recommendation does not settle:

- **Run it over the LIVE set with the *absorbed* expert required past-grace — not over the eligible set.** The contract says "before the cull, over the eligible set". The legacy merge (`self_organize.py:3077`) gated only on `merge_dist > 0 and len(cent) > 2`. Restricting to the eligible set makes the merge inherit the grace-reachability problem I quantify under Q-FAB-5 — at the shipped defaults it would be provably unreachable. But merging over the *whole* live set immediately re-absorbs every `replicate`/`xover` birth, which are near-duplicates **by construction** (`fabric/api.py:288-296`), making `replicate` inert. Requiring only the absorbed expert `b` to be past grace resolves both: a newborn cannot be swallowed before it has differentiated, and a long-lived twin can be consolidated.
- **The truncation residual is the second gate, and it costs no lever.** If `ΔW_a` and `ΔW_b` are near-parallel, rank-`r` truncation of their sum loses almost nothing and the merge is honest. If they are not, the residual is large. Report `fab.merge_residual_p50/p99` rather than minting a threshold — a second lever would need a census row, and `Q-MEM-4`'s own discipline ("MEASURE BEFORE RETUNING") applies. If the residual reads high the operator lowers `merge_dist`, which is what that lever is *for*.
- **Adam moments go stale on `A[a], B[a]` after an in-place write.** This is pre-existing (`rescue`'s heavy mutation at `fabric/api.py:238-240` does the same) and must be *stated*, not silently inherited.

**Why it fits the framework**
- **The ownership spine permits it entirely.** The merge touches `A`, `B`, `cent`, `use`, `uage`, `dom_of`, `n_live` — all FAB's own books on FAB's own `Population`. No cross-package import, no new wire, no `d_` field. `MEM.read`'s globality (`memory/api.py:117-119`) is what makes that true, and it is the sentence the escalation missed.
- **No frozen signature moves.** `FAB.manage(fab, pop, *, step_windows, flush_loss=None)` already returns a `ManageReport` that **P4 defines** (`fabric/api.py:29`), so `merged`, `merge_residual` and `merge_declined_grace` are new fields on a record type nobody has written yet. This is the cheapest possible landing.
- **DID IT FIRE:** `merge_dist > 0` with `fab.merged == 0` must distinguish "no pair was close enough" (armed but 0) from "no expert was past grace" (unreachable) from "the residual refused every pair". Three states, three counters, one declared `Gate`.
- **What it would break the other way:** minting `MEM.reassign_owner(i, j)` would be a frozen entry point on the package whose whole `apply_domain_plan` contract (`memory/api.py:211-215`) exists because "DOM COMPUTED THIS PLAN AND DID NOT APPLY IT" — a *sources* (domain-id) mechanism. Adding an *owner* (expert-id) mechanism beside it, keyed on a set that is `expert_id % 64` and therefore shared by 64 experts, would be a silent-overwrite record written on purpose.

**What changes**
- `src/fabric/api.py:203-256` (`FAB.manage`) — docstring prose only, inside a frozen signature: a **step 0, MERGE**, before the failure cull, with the eligibility rule, the ΔW-space arithmetic, the residual, and the three counters on `ManageReport`. Add `merge_dist` to `LEVERS READ:` at `:249-252` and to `FAB.counters`' list at `:346-355`.
- `docs/04_CONTRACT.md:887` — delete the `FAB.merge_dist` UNCONSUMED row (the lever now has a reader) and mirror the `manage` prose in the FAB section. **The ```contract block does not change** — no signature moves — so K1 is untouched.
- `src/fabric/levers.py:726-737` — rewrite the comment: the condition is met; state the ΔW-space correction and that MEM needs nothing.
- **Nothing in `src/memory/`.**
- If the owner prefers **(a)**: delete the lever, add `("misc", "EXPERT_MERGE_DIST"): dict(..., lands=None, ...)` to `tests/test_census.py` DEPARTURES (`.rework/CENSUS.md:73` files it under **misc**, not fabric), and a `docs/dropped_levers.md` line.

**Confidence**
**High** that the MEM entry point is not needed — three independent citations. **High** on the factor-averaging arithmetic (it is algebra, and the literature below confirms the practice). **Medium** on the recommendation to implement rather than drop: the merge remains an unmeasured behaviour change, and the honest counterweight is that the residual counter makes it the *first* version of this mechanism whose central claim can be falsified in-run.

**Literature**
**Bore directly, and it is the reason for the ΔW-space correction.** Expert merging in MoE is an active and settled-enough area. [MC-SMoE (ICLR'24 Spotlight)](https://arxiv.org/pdf/2310.01334) merges experts with similar routing policies but **aligns expert weights by permutation with a weight-matching algorithm before frequency-weighted parameter averaging** — the alignment step exists precisely because unaligned factor averaging destroys both experts. [Sub-MoE](https://arxiv.org/html/2506.23266) records that prior mergers "achieve success primarily when handling models with high similarity" and "generally fail" on low-similarity experts "due to significant parameter conflicts", and answers with subspace decomposition and matrix alignment. On the LoRA-factor point specifically, the merging literature is explicit that averaging `A` and `B` separately is **not** equivalent to averaging the materialised `ΔW`, that the exact-mean construction requires **concatenation with 1/√N scaling** (which needs rank 2r and is refused here — `FAB.load_state_dict` at `fabric/api.py:385-396` states rank is an inner dimension that "cannot be prefix-widened"), and that independently trained adapters occupy rotationally misaligned bases requiring Procrustes/permutation alignment ([Rethinking Inter-LoRA Orthogonality](https://arxiv.org/pdf/2510.03262), [Crowded in B-Space](https://arxiv.org/html/2604.16826)). The rank-`r`-truncated ΔW merge I recommend is the alignment-free member of that family and is the only one available at a preallocated fixed rank. On the goal-B side, [Theory on Mixture-of-Experts in Continual Learning](https://arxiv.org/abs/2406.16437) is the formal argument that MoE mitigates forgetting through expert diversification — which is the reason to prefer consolidation over deletion when the two are otherwise close. One dissent worth recording: [REAP the Experts](https://arxiv.org/pdf/2510.13999) argues pruning beats merging for one-shot MoE compression (I could not fetch it — arxiv.org is blocked by this container's egress proxy, so I have only the search snippet and mark it **UNVERIFIED**); note it addresses *compression* of a trained model, not *online consolidation during continual learning*, which is the opposite objective.

Sources: [MC-SMoE](https://arxiv.org/pdf/2310.01334), [Sub-MoE](https://arxiv.org/html/2506.23266), [Theory on MoE in Continual Learning](https://arxiv.org/abs/2406.16437), [Inter-LoRA Orthogonality](https://arxiv.org/pdf/2510.03262), [Crowded in B-Space](https://arxiv.org/html/2604.16826), [REAP the Experts](https://arxiv.org/pdf/2510.13999)

---

## Q-FAB-5 — splitting `use` from `uage` re-denominates `grace`

**What I read**
`docs/04_CONTRACT.md:332`, `:1051-1058`. `src/fabric/api.py:133-166` (`FAB.observe`, the split), `:203-256` (`manage`, rule 3 and the ranking), `:312-336` (`own_lr_scale`, the boost budget). `src/fabric/levers.py:636-646`, `:648-665` (`manage_every`), `:667-675` (`cull_frac`), `:677-684` (`grace`), `:354-361` (`chain_k`), `:192-198` (`hops`), `:200-211` (`depth0`), `:403-412` (the breadth cap and the 79.5% figure). `src/spine/units.py` (whole; `Selections` at the bottom of the Clock family). `src/spine/derive.py:286-326` (`cadences_that_cannot_fire`). `self_organize.py:2044-2051`, `:2647` (`bump_use`), `:2662` (`s.bump_use(_i2[:, 0].tolist())` — argmax only, verified). `.rework/ISSUES.md:65-79` (C11).

Resolved from `assemble.build(environ={})`: `grace=48`, `chain_k=8`, `hops=4`, `depth0=1`, `manage_every=500`, `n0=2048`, `slots=4096`, `pressure=0.45`, `cull_frac=0.02`; `DATA.stream_bytes=120000`, `LM.ctx=128`, `RUN.epochs=1` → **937 windows upper bound, 506 at 1.85 B/token** (C11's numbers, reproduced exactly).

**What is true today**
The split is specified at `fabric/api.py:143-150` and is required for the reasons given (H12/H13). The old clock is confirmed: `self_organize.py:2662` credits `s.bump_use(_i2[:, 0].tolist())` — column 0 of the top-k, i.e. **the argmax only**.

The question's "32× faster" needs two corrections, and they pull in opposite directions:

- **Per-expert**, the ceiling is `hops`, not `chain_k × hops`: one expert can be selected at most once per hop, so its own clock ticks at most **4×** faster. **Population-wide**, the total credit issued per window goes from 1 to `chain_k × hops` = up to **32×**. Both readings are true of different quantities and they imply different retunes.
- At the **shipped** `depth0=1` the effective multiplier is **8×**, not 32×. `depth0=1` starts the chain at one hop and `maybe_deepen` is on the `manage_every=500` cadence, which fires at most once in a default run.

**The number that matters, and it is not in the question.** At `n0=2048` with 8 credits per window, mean `uage` per expert after a full default run is `506 × 8 / 2048 = 1.98`. Reaching `grace=48` needs `48 × 2048 / 8 = 12,288` windows at depth 1 (3,072 at full depth 4). **At the shipped defaults the past-grace set is provably empty**, so the utilization cull, `rescue` (which lives inside it) and `lr_boost`'s budget (sized on the eligible count, `fabric/api.py:319-321`) are all unreachable — even though `derive.cull_gate_open(2048, 4096, 0.45)` returns `True` (I ran it). The gate is open onto an empty set. Under the *old* argmax-only clock the same threshold needed 98,304 windows, so **the split improves reachability by 8–32× and still leaves grace short by 6–24× at the shipped run length.** This is a C11-class finding that the C11 audit cannot see, because `derive.cadences_that_cannot_fire` (`spine/derive.py:317-322`) refuses anything that is not `Windows`, and `grace` is `Selections`.

**A second correction: the split does not fully kill H12.** `use` is credited by routing *mass* and `uage` by *selection count* (`fabric/api.py:145-147`). Under top-k these are strongly correlated — mass ≈ count × mean-mass-per-selection. And because routing concentrates (the pilot's top expert took 79.5% of traffic, `fabric/levers.py:412`), the experts that cross grace first are exactly the *most-used* ones, while the cull then ranks the eligible set by `use` **ascending**. So the eligible set is the high-`use` tail and the cull removes the least-used *within it* — H12 in a new dress unless `use` and `uage` actually decorrelate.

**The options**
- **(a) Split as specified, flag the re-tune on P9.** The tree's position. Costs nothing now; leaves a number nobody can set.
- **(b) Re-express `grace` as a multiple of `chain_k × hops`.** The question correctly refuses this: a lever computed from two other levers is the L1 defect (`.rework/PLAN.md` §4).
- **(c) Split as specified, and add the arithmetic that makes the re-tune a measurement rather than an argument.** Three readings, all pure reads of books FAB already keeps, all on `ManageReport` / `FAB.counters`.

**Recommendation**
**(c) — (a) plus three counters.** The split as specified; `grace` stays a `Selections` lever with a literal default; no derived lever.

The three readings, and why each exists:
1. **`fab.mass_per_selection` = `Σuse / Σuage`.** This *is* the evidential dilution factor: the mean routing mass an expert receives per selection. It is the number that says how many argmax-equivalents one post-split `uage` tick is worth, and it is the only defensible basis for re-scaling 48. It cannot be computed at build time (it depends on the router), which is exactly why `grace` must stay a literal and the retune must be a P9 measurement.
2. **`fab.uage_per_expert_per_pass` beside `fab.experts_past_grace_ever`.** `experts_past_grace_ever` is already declared (`fabric/api.py:163-165`) but a cumulative zero does not say *why*. The rate does: "0 experts past grace=48; mean uage 2.0 over 506 windows at n_live=2048" is an `unreachable` line with its own arithmetic, which is exactly what G4 asks for.
3. **`fab.cull_rank_spread`** — max/min `use` inside the eligible set. If it reads ≈1 the ranking carries no information and H12 survived the split. This is the falsifier for the repair itself.

And one statement the report must make: **at the shipped defaults, `fabric.cull_eligible` is `unreachable`, not `armed but 0`**, for the arithmetic above.

**Why it fits the framework**
- **Unit types force the shape of the answer.** `grace` is `units.Selections` (`fabric/levers.py:677-684`, `spine/units.py`'s `Selections` class). `manage_every` is `Windows`. `Selections >= Windows` raises `UnitError` — which is why the reachability statement **cannot** ride the C11 cadence audit and must be a FAB-owned `Gate` with its own arithmetic. That is the type system doing its job, not an obstacle.
- **The L1 rule forbids (b) outright**, and the question is right about it.
- **No signature moves.** `ManageReport` and the counters ledger are P4-defined record types (`fabric/api.py:29-30`). All three readings are new fields on records nobody has written yet.
- **What it would break the other way:** re-expressing `grace` as `k × chain_k × hops` would make one operator edit to `chain_k` silently move the cull's eligibility threshold — the coupling-through-a-default class that `d_`-prefixing exists to make visible, arriving through a lever default where `grep -rn d_` cannot see it.

**What changes**
- `src/fabric/api.py:143-166` (`FAB.observe`) — prose: state that the per-expert ceiling is `hops` and the population-wide factor is `chain_k × hops`, and that `depth0=1` makes the shipped factor 8×. Add `fab.uage_per_expert_per_pass` and `fab.mass_per_selection` to `DID IT FIRE:`.
- `src/fabric/api.py:203-256` (`FAB.manage`) — add `fab.cull_rank_spread` to `DID IT FIRE:`; state that `fabric.cull_eligible` reports `unreachable` with `mean uage / grace / n_live / windows` when the eligible set is empty.
- `src/fabric/levers.py:677-684` — extend the `grace` comment with the reachability arithmetic (12,288 windows at `depth0=1`, `n0=2048`) and the note that this is a `Selections` threshold and therefore outside `cadences_that_cannot_fire`'s reach.
- P9 list: the `grace` level, with `mass_per_selection` named as the number to set it from. **No lever default changes now** — the tree's discipline (Q-MEM-4) is that changing an instrument's definition and its configuration in one step is how this project produced numbers nobody could attribute, and the split *is* the definition change.
- **No signature moves. No ```contract change.**

**Confidence**
**High** on the arithmetic (I resolved the defaults from `assemble.build` and the run length reproduces C11's 937/506 exactly). **High** that the level is wrong and must not be guessed. **Medium** on the H12-residual claim — it follows from top-k routing plus the recorded 79.5% concentration, but the correlation between `use` and `uage` is an empirical quantity; `fab.cull_rank_spread` is precisely the reading that would settle it, which is why I propose it rather than assert the conclusion.

**Literature**
**NOT APPLICABLE.** This is a question about one tree's internal clock semantics — which counter ticks on which event, and whether a threshold expressed in that counter is reachable at this configuration. No paper knows `chain_k`, `n0` or this run length, and the MoE literature's load-balancing results are about routing distributions, not about grace clocks on a cull. Searching here would have spent the turn.

---

## Q-FAB-6 — nothing can tell the fabric a shift was self-inflicted

**What I read**
`docs/04_CONTRACT.md:1273-1281`. `src/fabric/api.py:133-166` (observe), `:203-256` (manage), `:254-311` (grow_check). `src/fabric/levers.py:528-568` (`z`, `plateau`, `warmup`, `cooldown`, `recover_min/max`). `src/capacity/api.py:89-134` (`CAP.observe`, esp. the `quiet: not blackout` clause at `:118-124`). `src/capacity/levers.py` (all 7 levers). `src/opt/api.py:180-250` (`maybe_step`, `shift_at`, and `opt.shift.notifications` at `:230`). `src/spine/compose.py:631-643` (the E draw row that stamps `shift_at`), `:864-878` (the OPT.maybe_step row), `:897-905` (the FAB observe/grow_check row), `:931-940` (TOK.mint_burst and the RetokEvent), `:1235-1262` (CAP.observe's deferral), `:1360-1400` (ROW_ARGUMENTS_ELSEWHERE, "THE LOOP'S OWN VALUES"). `self_organize.py:2897`, `:2948` (`note_shift`), `:3004`, `:3012` (the two consumers), `:5425` (blackout in the checkpoint), `:6515`, `:7787` (the two call sites), `:7397-7399` (the valve's read).

**What is true today**
The question's factual claim holds: `manage`, `observe` and `grow_check` take `step_windows` and losses, and no FAB entry point accepts a shift event. Four things I can add.

1. **The question names the wrong entry point.** It recommends "add a `shift_at`-style keyword to `FAB.manage`". In the old tree the blackout gates **growth**, not selection: `self_organize.py:2948` sets `s.blackout = t` on `PlateauGrowth`, and its only two consumers are `:3004` (`if unexpected and t - s.blackout >= s.cool`) and `:3012` (`if t - s.last < s.cool or t - s.blackout < s.cool: return 0`) — both inside `PlateauGrowth.step`, which in the rebuild is `FAB.grow_check` (`fabric/api.py:254-311`, the WATCH→BURST→RECOVER machine). `FAB.manage` is cull-and-spare and has no cooldown to suppress. **The keyword belongs on `grow_check`.**
2. **The producer already exists, in the right stage, in the right clock.** `spine/compose.py:635-637`: "The root also stamps `clock.opt_steps` here as the `shift_at` that `OPT.maybe_step`'s B row consumes — a resample is a SELF-INFLICTED shift". The retok half exists too: `compose.py:931-936`, TOK.mint_burst produces "a RetokEvent the root distributes". Both events already have rows. This is not a new join; it is a second consumer of a stamp the root already makes.
3. **The two stamps are in different clock kinds, and that is load-bearing.** OPT's `shift_at` is in **Steps** (`clock.opt_steps`, `compose.py:636`). FAB's `cooldown`, `warmup`, `recover_min/max` are all **Windows** (`fabric/levers.py:542-568`), and `grow_check` takes `step_windows`. So FAB's stamp must be `units.Windows(clock.step)` — a *different object* from OPT's, for the same event. Passing OPT's `shift_at` to FAB would be `Steps` against `Windows` and `spine/units.py`'s `Clock._same` raises `UnitError`. The type system catches it; the root must stamp the one event into two typed clocks on purpose.
4. **`CAP.observe`'s `blackout` boolean has an undeclared coupling behind it.** `capacity/api.py:118-124` takes `blackout` already-computed, and CAP declares **no blackout-window lever** (I listed all seven: `targets, fab_start, vocab_start, lift, lift_min, pin_windows, stall_band`). In the old tree the boolean was `_blackout = (step - fabgrow.blackout) < fabgrow.cool` (`self_organize.py:7397`) — **computed from FAB's `cooldown`**. So whoever supplies CAP's boolean is reading a FAB lever, and `grep -rn d_ src/` will not index it.

**Ordering, checked:** `FAB.observe/grow_check` is at `compose.py:897`, `TOK.mint_burst` at `:931` — two rows *below*. So a retok stamped on this flush reaches `grow_check` on the *next* flush, which is correct (the loss jump follows the retok). The epoch resample is stamped at the E row and precedes every B row.

**The options**
- **(a) Add a `shift_at` keyword to `FAB.grow_check`** (the question's (a), corrected from `manage`), typed `units.Windows`, default `None`.
- **(b) Route it through the `blackout`-shaped path.** Buys nothing here: `grow_check` has no `blackout` parameter to reuse, so (b) *is* (a) with a boolean instead of a stamp — and a boolean forces the caller to apply FAB's `cooldown`, which is a foreign-lever read at the call site.
- **(c) Accept that fabric growth treats a resample like new material.** Costs: the epoch resample and the retok are the two largest loss jumps a run produces, and `z=4.0` MAD-deviations above the slow EMA is exactly what they will read as. Goal B's growth trigger would fire on artefacts we caused, and `burst` would spend the cap on them. Then `new_frac` and the soft cap decline the *next*, real regression.

**Recommendation**
**(a), on `grow_check` rather than `manage`, as `shift_at=None` typed `units.Windows`** — and decided **now**, before P4 writes the body.

`FAB.grow_check(fab, pop, *, flush_loss, step_windows, soft_cap, memory_pressure, signature, shift_at=None)`. FAB applies its **own** `cooldown` to `step_windows - shift_at`; the root supplies only the stamp. That keeps the threshold inside the package that declares it — the same rule `FAB.manage_period` (`fabric/api.py:403-428`) exists to enforce: "THE WRAP BELONGS HERE AND NOT AT THE CALL SITE because this is where the kind is DECLARED."

**One hazard the tree has already been bitten by, and the fix is in the tree.** A defaulted argument is invisible to K10 — `spine/compose.py:1207-1212` records exactly this for `MEM.judge`: "Because `scorer` carries a default, no check asks about it: a row calling `judge(mem, store)` passes every check in the tree and yields `n_checked = 0` forever." So `shift_at=None` must be paired with the counter `OPT` already has: `opt/api.py:230` declares **`opt.shift.notifications` (0 means nobody is supplying `shift_at`)**. Copy it verbatim: **`fab.shift_notifications`**, with `fab.growth_blackout_suppressed` for the fires it prevented. Then "nobody wired it" and "it was wired and never fired" are two different lines, which is precisely what the question asks for ("until then the report must say the blackout is unreachable rather than armed").

**Why it fits the framework**
- **Wire rules force it to be an argument, not a wire.** The shift step is measured at runtime. `docs/04_CONTRACT.md`'s rule is explicit: a coupling's compute sees only frozen Configs, so anything measured at runtime can never be a wire. `shift_at` is an argument, and the same reasoning `opt/levers.py:535-536` already gives for `d_shift_at` — where it is *wrongly* called a wire — applies here in the correct direction.
- **Unit types make the two-clock stamp safe rather than a trap.** `Windows` for FAB, `Steps` for OPT; a mix-up raises instead of being 16× wrong at `batch_w=16`.
- **The frozen surface is cheap NOW and expensive later — say it loudly.** 116 of 121 entry points are stubs. `FAB.grow_check` is one of them. Adding a keyword today is: one line in `src/fabric/api.py:254`, one line in the ```contract block of `docs/04_CONTRACT.md` (K1 compares the two, `tests/test_contract.py:361-373`), one clause in the `compose.py:897` row. **After P4 has written the growth state machine against the current signature, the same change is a body rewrite.** This is a decision that must be made in this phase.
- **What it would break the other way:** option (c) leaves `z=4.0` reading our own retok as new material — and `capacity/api.py:120-123` records exactly where that ends: "a vocabulary lift mints tokens, the retok rebuilds the stream, the loss jumps, the jump reads as a stall, and the stall authorises the next lift. The 0.75 GB run walked 2048 → 8192 in 19 lifts that way." That is the CAP half of the identical loop; the FAB half is the population walking up its cap on artefacts.

**What changes**
- `src/fabric/api.py:254` — **SIGNATURE CHANGE, SAID LOUDLY**: add `shift_at=None` to `grow_check`. Plus docstring: the `cooldown` comparison, `RECEIVES: shift_at <- the root, stamped at the E draw row and at TOK.mint_burst's retok, as units.Windows`; and `fab.shift_notifications` / `fab.growth_blackout_suppressed` under `DID IT FIRE:`.
- `docs/04_CONTRACT.md` — the ```contract line for `FAB.grow_check` (K1 fails otherwise), and the FAB section's `grow_check` prose.
- `src/spine/compose.py:897-905` — name `shift_at` in the FAB observe/grow_check row; and either a fourth `System.__slots__` field (`shift_at_windows`, alongside `due`, `novelty`, `token_seen`) or an entry in `ROW_ARGUMENTS_ELSEWHERE`'s "THE LOOP'S OWN VALUES" block. `System.novelty` is the precedent — a value that crosses backwards where `produces` reads forwards only.
- **Cross-slice, not mine to decide:** `CAP.observe`'s `blackout` boolean either becomes the same `Windows` stamp (CAP applies its own threshold — but CAP has no such lever, so one must be minted or a `FAB.cooldown → CAP.d_blackout_windows` coupling declared), or the root computes it from FAB's `cooldown`, which is an undeclared coupling. **CAP.observe is itself deferred (`compose.py:1235`), so its signature is equally cheap today.**

**Confidence**
**High** that a shift route is needed and that `grow_check` is the right entry point (`self_organize.py:3004` and `:3012` are unambiguous). **High** on the Windows/Steps split. **Medium** on the exact carrier (a `System` slot vs a `ROW_ARGUMENTS_ELSEWHERE` entry) — that is a `compose.py` style call the orchestrator can make. What would raise it: the owner's ruling on whether CAP's `blackout` becomes a stamp, which decides whether one root join serves both consumers.

**Literature**
**NOT APPLICABLE.** "Which FAB entry point should accept the self-inflicted-shift stamp, and in which clock kind" is a question about this tree's `LOOP_ORDER`, its unit types and its counter discipline. No paper can answer it. (The *concept* — suppressing an adaptation trigger during a known self-inflicted distribution change — is ordinary engineering practice and needs no citation; the design is fully determined by `self_organize.py:3004/:3012` and the clock kinds.)

---

## Q-SIG-1 — `prototype_frac` has no supplier and is therefore structurally unreachable

**What I read**
`docs/04_CONTRACT.md:763`, `:1231-1240`. `src/sig/api.py:1-30` (module docstring, `StepOutcome`), `:117-149` (`train_step`, `reservoir=None` at `:117`, the DID IT FIRE line at `:142-143`), `:190-207` (`counters`). `src/sig/levers.py:53-67` (the hand-off list naming `d_prototype_reservoir`), `:306-321` (`prototype_frac`). `src/domains/api.py:15-27` (record types incl. `Partition … reservoir`), the full `^def` list (10 entry points), `:273-290` (`census`), `:293-308` (`state_dict`), `:401-416` of `domains/levers.py` (`reservoir`). `src/spine/compose.py:722-735` (the SIG.train_step LOOP_ORDER row), `:1334-1339` (its ROW_ARGUMENTS_ELSEWHERE entry), `:1218-1233` (the O10 "root may not reach into `pop`" precedent). `src/spine/rng.py:316-328` (`rng_for`). `tests/test_contract.py:20-24` (K4, K5).

**What is true today**
The question is **correct on the facts and already answered by the code** — its recommended option (c) is what `src/sig/api.py` currently specifies. Verified in three places:

1. `SIG.train_step(sig, st, *, stream, seen_units, opt, reservoir=None)` — `sig/api.py:117`.
2. The LOOP_ORDER row at `compose.py:722-734` names `stream`, `seen_units` and `opt` and **nothing else**, and the `ROW_ARGUMENTS_ELSEWHERE` entry at `:1334-1339` covers only `seen_units`. So `reservoir` is `None` on every call the root makes.
3. `DOM` has ten entry points (`open_partition, observe, rekey, note_competence, manage, on_retokenize, prior, census, state_dict, manage_period`) and none returns reservoir windows. `DOM.census` (`domains/api.py:274-282`) returns live/n_live/created/capped/merged/culled/folded/held/spared/emptied/boundaries/windows/visits/born/last/radius/pooled_radius/comp_glob/collapsed_at/partition_off — confirmed, no reservoir.
4. `sig/api.py:142-143` already declares the correct reporting: "`sig.prototype_pairs` (zero here with `prototype_frac > 0` means DOM supplied no reservoir — **unreachable, and the gate says so**)".

**Two things that are wrong in the tree and that this question should carry.**

**(i) `d_prototype_reservoir` is an illegal wire, named twice in `src/`.** `sig/levers.py:66` lists it among "the port's remaining work" wires, and `sig/levers.py:314-316` says "under L2 the reservoir arrives as `d_prototype_reservoir`". A wire's compute sees **only frozen Configs** — a reservoir is a list of stream windows the loop assigned at runtime, which is exactly the class `assemble.NOT_WIRES` exists to refuse (the `SIG_WIN` departure in `tests/test_census.py` refuses `d_signature_width_bytes` for the *same* reason: measured after Config freezes). So the file proposes a coupling the spine cannot build. It survives today only because it is prose: O4 and K5 are AST checks over code, and a `d_` name in a comment is invisible to them. But the contract states that **`grep -rn d_ src/` is meant to be a complete index of the couplings**, and these two comments put a non-coupling into that index.

**(ii) K4 counts a docstring mention as a reader.** `prototype_frac` appears in `SIG.train_step`'s and `SIG.counters`' `LEVERS READ:` lists, so it passes K4 as *consumed* while being structurally unreachable. `tests/test_contract.py:25-31` states this limitation honestly ("`LEVERS READ:` is prose that passes a parser"). This is the purest armed-but-inert form in the tree: the check that exists to catch unread levers cannot see it, and only L2/L3 (which do not exist yet) would.

**The options**
- **(a) Add `DOM.reservoir_pairs(dom, part, *, did, n, rng)`** — a new frozen entry point returning `n` `(window, window)` pairs from one domain's reservoir. Signature-set change: `src/domains/api.py`, the ```contract block, a LOOP_ORDER row.
- **(b) Carry the reservoir on `DOM.census`.** The question refuses it and is right: census runs on the 100-Windows management cadence while `train_step` runs per window, so the sample would be up to 100 windows stale and "two windows the assembler already believes belong together" stops being true. I add a second reason: `DOM.census` is consumed by FAB, MEM and the report; widening it to carry sample windows makes an instrument payload out of a training input.
- **(c) Declare the arm unreachable and print the reason.**
- **(d) Have the root slice `part.reservoir`.** Refused by O10 — `compose.py:1224-1226` establishes the precedent verbatim for `FAB.contribution`: "no entry point exports it and O10 forbids the root reaching into `pop`". The same holds for `part`.

**Recommendation**
**(c) now, (a) when the surface opens — which is the tree's own answer, and the live part of this question is therefore the two comment corrections, not the ruling.**

The correction to (a) worth carrying: **the supplier is a runtime entry point, not a wire.** If P5/P6 ever lands it, `DOM.reservoir_pairs` returns pairs on the per-window call path; `d_prototype_reservoir` must never exist. And the pairs must be drawn from DOM's own RNG stream (`domains/api.py:33-35` records that two draws in that package leaked to the global `random`, "which makes draw order a coupling channel no wire declares and one the L3 sweep cannot tell from a lever leak").

**Do not drop `prototype_frac`.** `sig/levers.py:317-321` gives the reason and I accept it: it is the only declared remedy for the diagnosis in that file's own group header (`sig/levers.py:250-257`) — the positive radius is shorter than a splice segment, so the encoder is explicitly taught that two distant windows of the same corpus differ, and *more* encoder training makes domain identity *worse*. Dropping the only remedy would leave the diagnosis standing with nothing attached, and SIG is the router's only input.

**Why it fits the framework**
- **Wire rules decide (b) and the comment fix.** A runtime-measured value can never be a wire; the reservoir is runtime-measured; therefore `d_prototype_reservoir` cannot exist in any form. That is not a preference.
- **The ownership spine decides (d).** The root holds `part` but may not read into it — O10, with a written precedent one question over.
- **DID IT FIRE decides (c).** `sig/api.py:142-143` already specifies the three-state answer. The one thing (c) must not become is `armed but 0`.
- **The frozen signature already permits (a) later at zero cost to SIG**: `reservoir=None` is a defaulted keyword, so adding a producer later needs no SIG change at all — only a DOM entry point and a LOOP_ORDER row. That is a genuinely good piece of contract design and worth saying so.
- **What it would break the other way:** (b) would put a per-window training input on a 100-window cadence, and the *silent* failure mode is the worst kind — pairs that are 100 windows stale still look like pairs, `sig.prototype_pairs` reads nonzero, and the arm reports as firing while training the encoder on a partition that has since moved.

**What changes**
- `src/sig/levers.py:66` — remove `d_prototype_reservoir` from the four-name hand-off list (leaving the other three, which are genuine build-time couplings).
- `src/sig/levers.py:314-316` — replace "under L2 the reservoir arrives as `d_prototype_reservoir`" with: the reservoir is runtime state and can never be a wire; the supplier, if it lands, is a DOM entry point returning pairs on the per-window path; until then the arm is unreachable and `sig.prototype_pairs` says so.
- `src/sig/api.py:117-146` — one added clause: with `prototype_frac > 0` and `reservoir is None`, `SIG.counters` reports `unreachable (no DOM supplier)`, never `armed but 0`.
- `docs/04_CONTRACT.md:1231-1240` — record that (c) is the *implemented* state and that the illegal-wire comment is the live defect.
- **No signature moves. No lever is dropped. Nothing in `src/domains/`.**

**Confidence**
**High.** Every claim is a direct read: the signature, the LOOP_ORDER row, the DOM entry-point list, and the two comments. The only judgement is "keep the lever", and its warrant is the file's own stated diagnosis.

**Literature**
**Bore on ONE half — whether to keep the arm — and NOT on the ruling.** The supplier question is pure internal structure and no paper can answer it; I did not search for one. On keeping it: prototype-based contrastive objectives are the standard answer to exactly the failure `sig/levers.py:250-257` describes. [Prototypical Contrastive Learning (Li et al., 2005.04966)](https://arxiv.org/abs/2005.04966) introduces ProtoNCE as a generalisation of InfoNCE in which representations are pulled toward assigned cluster prototypes, motivated by the observation that strict instance discrimination induces **class collision** — pushing apart points that should be grouped, which harms clustering and transfer. That is a precise restatement of this tree's diagnosis: a positive radius shorter than a splice segment teaches the encoder that two windows of the same corpus are negatives. It supports **keeping** `prototype_frac` and it also supports the tree's caution — the SIG→DOM→SIG feedback loop is the self-labelling risk PCL manages by alternation, and bounding it to a *fraction* of the batch is the conservative version of the same discipline. It says nothing about who supplies the reservoir in this codebase.

Sources: [Prototypical Contrastive Learning](https://arxiv.org/abs/2005.04966)

---

## Q-EVAL-5 — the curve probe's sample size

**What I read**
`docs/04_CONTRACT.md:1106-1112`. `src/eval/api.py:1-38` (module docstring, G7, ONE LOGITS PATH, record types), `:41-70` (`curve_period`), `:71-92` (`curve_probe`), `:95-119` (`holdout_probe`). `src/eval/levers.py:163-181` (`windows`), `:322-339` (`curve_every`). `src/spine/compose.py:1136-1163` (the `EVAL.curve_probe` and `CKPT.Retention.consider` deferrals), `:864-878` (`best_bpb` has no producer). `src/spine/derive.py:286-326`. `.rework/ISSUES.md:65-79` (C11). `.rework/PLAN.md:134-137` (the seed rule), `:182` (P5). `self_organize.py:6396` context via the contract's citation.

Resolved from `assemble.build(environ={})`: `EVAL.windows=64`, `EVAL.curve_every=2000`, `EVAL.holdout_windows=32`, `EVAL.null_draws=5`; run length **506–937 windows**.

**What is true today**
The tree's position is correct and I confirm it, with two numbers the question does not carry.

1. **The multiplier is 4×**, and it is `64/16`: `EVAL.windows` resolves to **64**, not to some other value. `eval/api.py:74-80` already specifies reading `ev.windows` and already flags the 4× for P9. So this question is largely *decided in code*; what is live is whether the owner accepts the cost.
2. **At the shipped defaults the 4× is 4× of zero.** `curve_every=2000` against a run of at most 937 windows: the curve probe **never fires**. C11 lists it and names it "the one number P3 exists to produce"; I reproduced the run length exactly (`120000 / 128 = 937`; `120000 / 1.85 / 128 = 506`). So the P9 equivalence entry must be **conditioned on run length** — "this number moves 4× on runs long enough to probe, and does not exist at the shipped defaults" — or it will be written as a regression nobody can reproduce.
3. **The probe is deferred and stays deferred.** `compose.py:1146-1163`: `EVAL.curve_probe` is P5 because nothing produces `units_by_domain` or `logits_fn`. Two consequences the tree already records and that bear on the cost argument: `CKPT.Retention.consider` can never fire (`Saves.best` is always zero), and `OPT.maybe_step`'s `best_bpb` has no producer, so the restart damping is unreachable (`compose.py:868-874`).
4. **The cost, when it does exist, is not trivial.** At 64 windows/domain × (say) 20 live domains = 1,280 forward-only windows per probe, against 2,000 windows of training between probes. That is roughly 20-30% wall clock at `curve_every=2000`, versus ~7% at 16. This is a real number and the question does not state it.

**The options**
- **(a) Read `ev.windows`** — the tree's position.
- **(b) Keep the hardcoded 16.** Rebuilds the untrippable-guard shape the rework exists to end, *inside* the document written to end it.
- **(c) Mint a curve-specific `EVAL_CURVE_WINDOWS`.** Buys per-instrument cost control. Costs a census row: N2 (`tests/test_census.py:266`) requires every declared lever to trace to a census row or a declared departure, and no such row exists — so it needs a minted-lever justification the census never voted on (the same objection the contract raises to `OPT_GRAD_CLIP` at `docs/04_CONTRACT.md:1024-1026`).

**Recommendation**
**(a), read the lever** — with two riders that are not in the question.

**Rider 1: the P9 entry must be conditioned on run length.** "The default probe cost rises 4×" is only true of a run that probes at all. At the shipped defaults it rises 4× from nothing. Writing it unconditionally into the equivalence report produces a number nobody can attribute — which is the exact failure `.rework/PLAN.md` P9 exists to prevent ("each is attributable to a named fixed defect").

**Rider 2: `CurveReading` must carry the cost.** `eval/api.py:84-87` already requires `windows_drawn` **per domain**. Add the total (windows × `LM.ctx`), so the operator can see what the probe spent. `EVAL.windows` is then a knob whose cost is visible *and* raisable *and* lowerable — which is precisely the asymmetry the old `EVAL_N` failed: five of its six readers wrapped it as `min(24, EVAL_N)` or `min(48, EVAL_N)`, so it could only ever be lowered.

I considered (c) seriously and reject it on the framework rule. `eval/levers.py:163-164` declares `windows` as "Default number of windows an eval Sample draws **when it does not declare its own**" — `curve_probe` declares none, so `ev.windows` *is* the declared answer. Minting a second sample-size lever without a census row is the L1-adjacent move the contract refuses elsewhere in the same section.

**Why it fits the framework**
- **The L1 rule settles it.** A hardcoded 16 quoted in a lever's own help text as though declared is "an undeclared second default INSIDE THE SENTENCE DESCRIBING THE LEVER" (`eval/api.py:75-77`). That is the defect class this rework exists for, and no cost argument outranks it — the operator can set `EVAL_WINDOWS=16` and get exactly the old behaviour, which is what makes (a) strictly better than (b).
- **DID IT FIRE:** `windows_drawn` per domain, with a domain that yielded zero **reported rather than skipped**, is what makes the sample size auditable. The recorded case is on the record: CAN A DOMAIN PREDICT needed 16 and drew `min(48, EVAL_N)`, so at `EVAL_N=4` it collected 4, produced nothing, and `DOM_PRIOR` was accumulated every window and never read.
- **Frozen signatures:** none move. `curve_probe`'s signature already takes only `units_by_domain`, `logits_fn`, `rng`; the sample size comes off the Config.
- **What it would break the other way:** (b) reinstates a number no operator can change, in the one instrument that feeds `OPT`'s restart damping and `CKPT`'s retention keep-rule.

**What changes**
- **Nothing in `src/` is required** — `eval/api.py:74-80` already specifies reading `ev.windows`. What is owed is the *ruling* plus:
- `src/eval/api.py:82-87` — add the total drawn (windows × ctx) to `CurveReading`'s reported fields.
- `docs/04_CONTRACT.md:1106-1112` — record the resolved value 64 (so "4×" is checkable), and condition the P9 entry on run length.
- P9 list: "curve probe sample 16 → `EVAL.windows` (64); **cost visible only on runs longer than `curve_every`**".
- **No signature moves. No lever changes.**

**Confidence**
**High** on the ruling and on the arithmetic (defaults resolved from `assemble.build`, run length reproduces C11 exactly). **Medium** on the 20-30% wall-clock estimate — it assumes ~20 live domains and forward-only cost ≈ ⅓ of a training window, neither of which I measured. What would raise it: one timed P5 probe against a real domain count.

**Literature**
**Bore only weakly, and I say so rather than dressing it up.** The general framing — that an evaluation's usefulness is a signal-to-noise property and that adding examples reduces noise only up to a floor set by run-to-run variance — is the subject of AI2's [Signal and Noise (2508.13144)](https://arxiv.org/pdf/2508.13144); it supports "make the sample size a declared knob whose cost is reported", but it cannot say whether 16 or 64 is right for *this* probe. **The decisive argument is framework, not literature:** an undeclared hardcode quoted as a declared value is the defect this whole rework exists to end. I did not search further, because the remaining question — "does `curve_probe` read `ev.windows` or a literal" — is internal to this tree.

Sources: [Signal and Noise](https://arxiv.org/pdf/2508.13144)

---

## Q-EVAL-9 — does `holdout_windows` stay at 32?

**What I read**
`docs/04_CONTRACT.md:1114-1120`. `src/eval/levers.py:183-201` (`holdout_windows` and its full comment), `:163-181` (`windows`), `:206-218` (`null_draws` and the L44/L45 note). `src/eval/api.py:1-38` (G7, the `Reading` record with `seed_count`), `:95-119` (`holdout_probe`, esp. the H20 note at `:100-106` and the M82 note at `:108-110`), `:122-140` (`null_excess`). `src/spine/compose.py:1164-1172` (`EVAL.holdout_probe`'s deferral), `:1173-1187` (`EVAL.null_excess`'s deferral). `src/spine/rng.py:316-328` (`rng_for`), `:331-338` (`issued`), `:500-529` (`frozen_rng`). `.rework/PLAN.md:134-137` (the seed rule), `:184` (P7, the R matrix from two seeds). `.rework/ISSUES.md:65-79`.

Resolved: `EVAL.holdout_windows=32`, `EVAL.null_draws=5`; `LM.ctx=128`; run length 506–937 windows.

**What is true today**
The recommendation ("leave it at 32") is right, but **the tree's stated reason is the weakest available and one better reason is missing.**

- The stated reason is "that is the literal the runs used". `.rework/PLAN.md` contains the explicit counter: "**Explicit non-goal:** the new tree will not reproduce rm-predict's numbers, and must not be judged on it … agreement with them would be evidence of a bug faithfully carried forward." Continuity with an old literal is not, by this project's own rules, a reason.
- The second stated reason — "raise it only after G2 has measured this machine's noise floor" — is sound and does the real work. G2 (`tests/test_determinism.py`) has not run against a trained system.
- **The missing reason, and it is the strong one: the retention comparison is PAIRED.** `eval/api.py:100-106` records H20 as the defect that `prev` and `now` "were measured on DIFFERENT WINDOWS" because starts were drawn over the *tokenised* validation text, whose length shrinks under online minting. The repair is byte-coordinate window starts. The point the tree does not draw out is that once the *same* byte windows are scored before and after, the per-window difficulty term **cancels** in the difference. Window-to-window bpb variance in text is large (order 0.3–0.5 b/B); the variance of a *paired* difference on fixed windows is far smaller, because it removes exactly that term. So n=32 **paired** is a materially stronger instrument than n=32 unpaired, and the `research_continual_memory.md:743-745` warning is calibrated for the unpaired case.
- **Pairing is not yet guaranteed.** `holdout_probe(ev, *, units_by_domain, logits_fn, rng)` takes an `rng`, and `spine/rng.py:500-529`'s `frozen_rng` protects the *global* streams — it explicitly does **not** cover "streams handed out by `rng_for()`". So whether every probe in a run draws the *same* windows is a P5 implementation choice that nothing currently pins down. If the stream advances between probes, the pairing is lost silently and the number reverts to the unpaired power the research doc warns about.
- **The other error bar is seeds, not windows.** `.rework/PLAN.md:134-137` makes it a hard rule: "the record's between-seed spread (0.066–0.131 b/B) **exceeds every architectural difference this project has ever claimed**. No comparison may be reported from fewer than two seeds; every `Reading` carries its seed count; the renderer refuses to print a verdict on n=1." Raising `holdout_windows` from 32 to 256 tightens the *within-run* term while leaving the *between-seed* term — the larger one — untouched. P7 already requires two seeds for the R matrix.
- **Both the probe and its null are deferred to P5** (`compose.py:1164-1187`), so nothing measures this today.

**The options**
- **(a) Leave at 32.**
- **(b) Raise to 128–256 now,** per `research_continual_memory.md:743-745`.
- **(c) Leave at 32 and pin the pairing** — draw each domain's window starts once, from a stream keyed by the domain **name**, so every probe in the run and across a resume scores the identical byte windows; compute the 2σ test on the **paired differences**, not on the pooled window spread; report the paired SD.

**Recommendation**
**(c) — 32 stays, and the pairing becomes a stated requirement of `holdout_probe`.**

The mechanism is already in the tree and needs no new machinery: `spine.rng.rng_for("eval.holdout." + domain_name, seed)` (`rng.py:316-328`) gives a stable per-domain stream keyed by name, and `rng.issued()` (`:331-338`) puts it on the register. This is the *same* key rule the lever already declares as part of its meaning — `eval/levers.py:199-201`: "**KEYED BY DOMAIN NAME, not by index**, so adding a domain does not shift the comparison. That property is part of the lever's meaning and has to survive the port." Extending "keyed by name" from the *reporting* to the *drawing* is one sentence and it is what makes the comparison paired.

The order of operations, stated so it cannot be got wrong: **pin the pairing first, then let G2 measure the floor, then decide n.** Raising n before pairing buys the smaller of the two available variance reductions at 8× the cost.

And the honest caveat the answer must carry, per C11: at the shipped defaults a run is 506–937 windows, and **32 held-out windows per domain × `LM.ctx=128` ≈ 7.6 kB of text per domain** — a sample smaller than one splice segment. Any statement about `holdout_windows` presumes a run long enough to have trained on more than the probe measures. If the owner raises `DATA.stream_bytes` (the C11 decision), this question should be re-asked with the noise floor in hand.

**Why it fits the framework**
- **The instrument line.** `eval/api.py:3-5`: EVAL "owns EVERYTHING THAT MEASURES THE RUN AND NOTHING THAT CHANGES IT". Pinning the draw is a statement about the instrument's construction, not about the mechanism it grades, so it belongs entirely inside EVAL.
- **G7 permits it and `rng_for` implements it.** `frozen_rng` explicitly does not cover named streams (`rng.py:525-528`), so a named per-domain stream is the *sanctioned* way to get a repeatable draw, and `issued()` makes "this domain's holdout stream was never drawn" a reportable state rather than a silence.
- **No signature moves.** `holdout_probe(ev, *, units_by_domain, logits_fn, rng)` already takes `rng`. The change is a docstring clause on a frozen signature plus a P5 body decision.
- **The seed rule outranks the window count**, and it is already a hard rule with a renderer that refuses n=1. Raising `holdout_windows` without raising seeds would tighten the visibly smaller error bar and leave the dominant one — which is the wrong-measurement family (98 records) in its most flattering form.
- **What it would break the other way:** raising to 256 now, before G2, changes what every recorded retention number means — the question's own reason for refusing it — and it does so *unpaired*, so most of the extra cost buys variance reduction on a term that pairing removes for free.

**What changes**
- `src/eval/api.py:95-115` (`holdout_probe`) — docstring, inside a frozen signature: window starts per domain are drawn **once**, from `rng_for("eval.holdout." + domain_name, seed)`, and are identical at every probe and across a resume; the 2σ verdict is computed on the **paired per-window differences**; `Reading` carries the paired SD alongside `seed_count`.
- `src/eval/levers.py:183-201` — extend the comment: 32 stays; the reason is the paired design plus "G2 has not run", **not** continuity with the old literal (which PLAN's non-goal forbids as a reason); ≈7.6 kB per domain at `LM.ctx=128` is stated so the sample's size is visible.
- `docs/04_CONTRACT.md:1114-1120` — replace "because that is the literal the runs used" with the paired-design reason and the G2 sequencing.
- P9 list: **no entry** — the number does not move.
- **No signature moves. No lever default changes.**

**Confidence**
**Medium-high.** High that 32 should stay for now and that the seed error bar dominates (PLAN's 0.066-0.131 b/B spread is measured and quoted). High that pinning the draw is cheap and correct. **Medium** on the size of the pairing benefit: I did not measure the within-domain window-to-window bpb spread on this corpus, and the factor by which pairing reduces the variance is exactly that spread relative to the paired-difference spread. What would raise it: G2 plus one holdout probe run twice on the same checkpoint — which is also the cheapest possible experiment and should be the first thing P5 does.

**Literature**
**Bore, and it is a genuine empirical question — but it bore less than the framework did.** The `research_continual_memory.md:743-745` recommendation of 128-256 for a published null is consistent with what the field says about held-out LM evaluation noise: [Signal and Noise (2508.13144)](https://arxiv.org/pdf/2508.13144) frames benchmark usefulness as a signal-to-noise ratio and argues the dominant noise term in LM evaluation is between-checkpoint/between-run variance rather than the number of evaluation items — which is exactly why this project's own seed rule (0.066-0.131 b/B between seeds) is the binding constraint and not `holdout_windows`. On protocol, continual-learning evaluation convention is a T × D matrix of per-domain held-out perplexity recorded after each phase, with BWT and a forgetting measure derived from it — which is `G8`'s R matrix and confirms the tree's structure is standard. What the literature does **not** decide is whether *this* machine's noise floor makes 32 sufficient, and it has nothing to say about the paired-vs-unpaired point in this specific probe, which comes from reading H20's repair. That is the honest division.

Sources: [Signal and Noise](https://arxiv.org/pdf/2508.13144), [Continual evaluation for lifelong learning](https://arxiv.org/pdf/2205.13452)
