# Q11 — MoE auxiliary-loss coefficients and expert-choice routing

## The standard load-balancing loss

**Source: Fedus, Zoph & Shazeer, "Switch Transformers," JMLR 2022; restated with full notation
in Zoph et al., "ST-MoE: Designing Stable and Transferable Sparse Expert Models,"
arXiv:2202.08906, Appendix A.**

For N experts indexed i = 1..N and a batch B of T tokens:

```
loss = α · N · Σ_{i=1}^{N}  f_i · P_i                                    (ST-MoE Eq. 7)

f_i = (1/T) Σ_{x∈B} 1{ argmax p(x) = i }        fraction of tokens dispatched to expert i
P_i = (1/T) Σ_{x∈B} p_i(x)                      mean router probability for expert i
```

**The coefficient people actually use: α = 10⁻².** ST-MoE states it directly — α = 1e-2 was
sufficiently large to ensure load balancing while small enough not to overwhelm the primary
cross-entropy objective. This value is inherited essentially unchanged across Switch, ST-MoE,
Mixtral's HuggingFace implementation, and most subsequent work.

Three details that matter and are usually skipped:

1. **Why the factor of N.** Under uniform routing, Σ f_i·P_i = Σ (1/N)(1/N) = 1/N. Multiplying
   by N makes the minimum equal 1 **regardless of expert count**, so α means the same thing at
   8 experts and at 4096. If your balance term omits the N, your effective α is scaled by 1/N —
   **at 4096 experts that is a factor of 4096, and your balance floor is essentially off.**
   This is the first thing I'd check in your code.

2. **Only P is differentiable.** f is a hard argmax count and carries no gradient. All the
   pressure flows through the router probabilities. The gradient w.r.t. P_i is proportional to
   how overloaded expert i is, giving a self-correcting loop: overloaded experts get pushed
   down, underloaded ones get relative upward pressure via softmax normalization. Note the
   consequence: **a fully dead expert (f_i = 0) contributes exactly zero to the loss and
   receives zero balance pressure.** The Switch loss prevents collapse; it does not, by itself,
   revive. This is worth holding next to the revival claims in file 02.

3. **An equivalent variance form exists.** Skywork-MoE (arXiv:2406.06563) derives the same
   objective from `Σ_j (k/n − p_j)²`, using `p_j ≈ (k/T) Σ_i g_ij` as the differentiable
   surrogate. Same idea, quadratic penalty on deviation from uniform. Useful if you want the
   "variance penalty on assignment counts" formulation that the MoE ecology paper (file 02)
   described but never wrote down.

**Sensitivity to α, with a number.** arXiv:2204.09598 swept α ∈ {0.05, 0.1, 1, 2} on a QA task:
at 4 experts, raising α monotonically *hurt* (52.83 → 49.74); at 16 experts, raising α
monotonically *helped* (50.44 → 51.33). **The optimal α grows with expert count.** At 4096 you
are far outside any published sweep, and the 0.01 default has no claim on you. This is the
citation you were missing when you set your balance floor by argument.

Also note α interacts with the router z-loss (ST-MoE uses 1e-3) — RLRS in file 01 used
z-loss 0.001 with balance 0.01.

---

## Expert-choice routing

**Source: Zhou, Lei, Liu, Du, Huang, Zhao, Dai, Chen, Le, Laudon, "Mixture-of-Experts with
Expert Choice Routing," NeurIPS 2022, arXiv:2202.09368.**

The inversion: instead of each token picking its top-k experts, **each expert picks its top-C
tokens**.

```
T_j = TopC_i( S_{i,j}, C )                # expert j selects C tokens
y_i = Σ_{j : i ∈ T_j}  g_{i,j} · FFN_j(x_i)
```

with C set so that E·C = c·T (c = capacity multiplier). Setting C = kN/E matches token-choice
top-k in total compute.

**What it buys, and it is exactly what you asked about:**
- **Perfect load balance by construction.** Every expert processes exactly C tokens.
- **No auxiliary load-balancing loss needed at all.**
- **No dropped tokens** from capacity overflow.
- Variable compute per token — a token can be picked by many experts or none. The paper frames
  this as adaptive computation and it is the secondary selling point.
- ~1.1× convergence speedup vs top-1 routing in the original; a recent decoder study
  (arXiv:2604.01622) reports EC reaching loss 3.75 in 10.6h vs ~20h for both token-choice
  variants — **~2.0× faster** — at 52.1 TFLOP/s/GPU, 1.5–2.1× higher throughput.

**So: does it make your culling machinery unnecessary?** Structurally, an expert cannot be
starved — it always gets C tokens. So there are no dead experts in the routing-mass sense the
whole file-02 taxonomy is built on. That is a real and strong claim.

**But there are four blockers, and the first is probably fatal for you:**

1. **Expert choice is not causal.** Selecting the top-C tokens requires a global top-C over the
   batch or sequence. In an autoregressive LM, that leaks information from future positions
   into the routing decision for earlier ones. This is why Zhou et al. evaluated on
   encoder-decoder models, and why the survey literature flags it as needing "global top-C
   selection per expert over the batch or sequence." Recent work (arXiv:2604.01622) claims to
   extend EC to decoders — **that is the paper to read before you invest**, and I have not
   verified how it resolves causality. Options in the literature include per-sequence
   restriction, AdaMoE-style null experts, or chunked selection.

2. **Token coverage is not guaranteed.** Some tokens get no expert at all. In classification
   that's tolerable; in next-token prediction, a token that routes nowhere falls back to the
   residual and gets no expert computation. Whether that's acceptable depends on your
   architecture.

3. **C shrinks as E grows.** With E = 4096 and E·C = c·T, C = c·T/4096. At a typical
   per-device token count, C may be a handful of tokens or less than one. **Perfect balance at
   4096 experts means each expert sees almost nothing per step**, which is a different pathology
   from death but not obviously better. This is unexplored territory — the survey literature
   notes EC's cost is comparable to per-token top-k, but nobody has run it at your expert count.

4. **Balance ≠ specialization.** EC guarantees every expert is *used*; it does not guarantee
   any expert is *good*. Your culling is (I assume) ranking on fitness, not on occupancy. If
   so, EC removes the dead-expert justification for culling but not the
   weak-expert justification. Worth being precise about which one you're actually solving.

**Adjacent alternatives worth knowing:** BASE Layers (Lewis et al. 2021) solves routing as a
linear assignment problem, also giving balanced assignment. Auxiliary-loss-free balancing via
per-expert bias terms (Wang et al., arXiv:2408.15664; used in DeepSeek-V3) gets balance without
an aux loss *and* stays causal — **this may be the better fit for you than EC**, precisely
because it keeps token-choice routing and therefore keeps causality, while removing the aux-loss
tuning problem you're currently solving by argument.

## What I'd check first, in order

1. Is the `N` factor present in your balance loss? At 4096 experts this is a 4096× error if not.
2. Sweep α. The one published sweep says optimal α rises with expert count, and you are 256×
   beyond the largest point in that sweep.
3. Read arXiv:2408.15664 (loss-free bias balancing) before arXiv:2202.09368 (expert choice).
   It is causal, it is deployed at scale in DeepSeek-V3, and it does not require you to
   restructure routing.
