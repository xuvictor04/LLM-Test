# Q12 — Cyclical LR under Adam, and the update-rescaling correctness question

## The correctness question first, since you're running this code now

**Short answer: rescaling the realised update does not corrupt Adam's moment estimates. The
moments are functions of the gradients only, and you are not touching the gradients.**

The AdamW update, per parameter:

```
m_t = β₁·m_{t−1} + (1−β₁)·g_t
v_t = β₂·v_{t−1} + (1−β₂)·g_t²
m̂_t = m_t/(1−β₁ᵗ)          v̂_t = v_t/(1−β₂ᵗ)
Δθ_t = −lr_t · ( m̂_t/(√v̂_t + ε) + λ_wd·θ_{t−1} )
```

`m_t` and `v_t` depend on `g_t` alone. Multiplying `Δθ_t` by a per-group factor `c` afterwards
never enters either recursion. Bias correction is a function of `t` only, also unaffected.
**Confidence: high — this is arithmetic on the update rule, not an empirical claim.**

And your reasoning for doing it this way was right: Adam *is* invariant to a global rescaling of
the gradient (numerator and denominator scale together), so scaling gradients would be a no-op,
and scaling the realised update is the correct way to get a per-group effective step size.

### Four caveats, in descending order of how likely they are to bite you

**1. Weight decay. This one is real and easy to get wrong.**
If you rescale the *whole* realised update, you also scale the decoupled weight-decay term, so
group *g* gets effective weight decay `c_g · λ_wd`. Your WD-to-LR ratio then stays fixed — which
is the AdamW convention and is arguably what you want. But if you instead rescale only the
adaptive part, WD stays constant while LR varies, and the *relative* regularization strength
now oscillates with your cycle. **These are different experiments and neither is obviously
wrong; you just need to know which one you're running.** Check whether your rescale is applied
before or after the WD term in your code. If experts are born and then decayed at a
cycle-varying rate, this silently becomes a per-expert regularization schedule you didn't design.

**2. ε — not a problem.** Since `lr` multiplies the entire `m̂/(√v̂+ε)` expression, post-hoc
rescaling by `c` is *exactly* equivalent to using `lr·c`. ε sits inside the denominator and is
untouched either way. No asymmetry. (Contrast with rescaling the gradient, where ε would break
the scale invariance — another reason your choice was right.)

**3. The one that actually matters for a *cyclical* factor: v is stale relative to a fast cycle.**
`v_t` is an EMA with an effective horizon of roughly `1/(1−β₂)` steps — **1,000 steps at
β₂ = 0.999**. It estimates the second moment of gradients over that window. When you rescale
the update, the parameters move differently, so subsequent gradients differ, so `v` eventually
reflects the new regime — but only after ~1,000 steps.

If your per-group cycle period is **shorter than ~1/(1−β₂) steps, `v` never equilibrates to any
phase of the cycle.** It converges to something like a window-average of the whole cycle, and
the effective step size you get is not the one you designed at either the peak or the trough.
This isn't corruption in the sense of a bug, but it is a real mismatch between intent and
behaviour, and it is specific to cyclical (as opposed to monotone) rescaling.

**Practical rule: keep your cycle period comfortably above 1/(1−β₂), or lower β₂ for the
affected groups.** For a birth-anchored per-expert cycle this is a live constraint — a newborn
expert has fewer than 1,000 steps of history by definition, so its `v` is dominated by bias
correction and initialisation for its entire first cycle.

**4. Trajectory divergence is not corruption.** Rescaling changes where you go, hence future
gradients, hence future m and v. That's true of any LR schedule and is not a pathology.

### Cheap diagnostic

Log, per group, per step: `‖Δθ_realised‖` and `‖m̂/(√v̂+ε)‖`. Their ratio should equal
`lr_t · c_g` exactly (plus the WD term). If it drifts, your rescale is being applied somewhere
you didn't intend — most likely inside the optimizer's internal state update rather than
outside it. Also log `√v̂` per group: if it swings with your cycle, β₂ is too small relative to
the period; if it's flat while `c_g` swings by 4×, `v` is stale and caveat 3 applies.

---

## Do cyclical / warm-restart schedules behave differently under Adam than SGD?

**Yes, and the difference is a damping effect.**

The mechanism: under SGD, changing the LR changes the step size by exactly that factor. Under
Adam, the per-parameter `1/√v̂` term is itself adaptive, and it partially compensates — if a
higher LR drives you into a higher-gradient region, `v` rises and the denominator grows,
shrinking the effective step. So **the amplitude of a cyclical schedule is partly absorbed by
Adam's own normalization**, and cyclical effects are generally weaker under Adam than the SGD
literature (Smith's CLR, Loshchilov & Hutter's SGDR) would lead you to expect.

**Confidence: moderate.** The reasoning follows from the update rule and is standard folklore,
but I did not fetch a paper this session that measures the damping quantitatively. Treat it as
a prediction to test, not a citation.

**What I can point to with more confidence:** Loshchilov & Hutter's decoupled-weight-decay paper
(the AdamW paper) explicitly proposes **AdamWR = AdamW + warm restarts**, i.e. they carried SGDR
into the Adam family deliberately, and reported it working. So the combination is established
practice, not exotic. **[CITED — I did not re-read it this session; verify before citing.]**

Two things I'd flag from what I *did* read:

- **RLRS (file 01, arXiv:2507.03526) is an existence proof that per-group schedule shaping
  works under AdamW specifically.** All their experiments are AdamW, decoupled per-component
  schedules, and they report both speedup (up to 22.8% on MoE) and improved *stability* —
  Figure 4 shows the baseline MoE8×906M exhibiting loss spikes that RLRS removes. Whatever the
  damping story, per-group LR manipulation under Adam empirically helps at their scale.
- **The MoE ecology paper's protocol (file 02)** used AdamW with cosine annealing and separate
  LRs for encoder (1e-4) vs experts+router (1e-3) — a two-group constant split, and the crudest
  version of what you're doing.

## Summary for your code review

| Question | Answer | Confidence |
|---|---|---|
| Does post-hoc update rescaling corrupt m or v? | **No.** They depend on gradients only. | High |
| Is it equivalent to a per-group LR? | **Yes**, exactly, including ε handling. | High |
| Does it change weight decay? | **Yes, if applied to the whole update.** Decide deliberately. | High |
| Is a fast cycle safe with β₂ = 0.999? | **Only if period ≫ 1000 steps.** Newborn experts are the risk case. | Moderate–high |
| Do cyclical schedules behave differently under Adam? | Yes — damped by `1/√v̂`. Magnitude unmeasured here. | Moderate |
