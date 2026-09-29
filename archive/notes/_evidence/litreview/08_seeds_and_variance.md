# Q9 — How many seeds does a result need?

You were right that this is the binding constraint. But the conclusion is better than
"everything you measured is noise." Plugging your numbers into the standard machinery
splits your results cleanly into one that is probably real and cheap to confirm, and one
that should be abandoned as a question.

---

## Your numbers, run through the standard test

**Source: Bouthillier, Delaunay, Bronzi, Trofimov, Nichyporuk, Szeto, Sepah, Raff, Madan,
Voleti, Ebrahimi Kahou, Michalski, Serdyuk, Arbel, Pal, Varoquaux, Vincent. "Accounting for
Variance in Machine Learning Benchmarks." MLSys 2021, arXiv:2103.03098.** Read in full.

You report 4 runs of one nominally identical configuration spread over **1.227 b/B**.
For n=4 normal samples, E[range] ≈ 2.059σ, so:

**σ ≈ 0.596 b/B within-configuration.**

(Crude — range-based σ from n=4 is high-variance itself. Compute the actual sample std.)

Now the standard criterion. Bouthillier recommends **P(A > B) ≥ γ** with γ = 0.75, rather than
comparing means, and Noether's sample-size formula for that test (Appendix C.3):

```
N ≥ ( (Φ⁻¹(1−α) − Φ⁻¹(β)) / (√6 · |½ − γ|) )²
```

Applied to your three growth conditions:

| Comparison | Δ b/B | Cohen's d | P(A>B) | Paired seeds needed |
|---|---|---|---|---|
| 3→4096 vs 2048→4096 | 1.375 | 2.31 | **0.949** | **≈ 9** |
| 3→4096 vs fixed 2048 | 1.385 | 2.32 | **0.950** | **≈ 9** |
| 2048→4096 vs fixed 2048 | 0.010 | 0.02 | 0.505 | **≈ 80,000** |

**This is the actionable result.**

1. **Your headline growth finding is probably real and costs ~9 paired runs per arm to
   establish.** Not 4, not 1, but also not 30. Nine. That is affordable, and it converts your
   most interesting result from an anecdote into a claim. Do this before anything else.

2. **The 2.009 vs 1.999 comparison is dead.** It needs ~80,000 seeds. Stop treating "growing
   2048→4096 is nearly free" as a finding; it is a question your instrument cannot answer.
   Either accept it as unresolvable at this σ, or reduce σ first (see below).

3. **Everything you've compared at n=1 with Δ < ~1.0 b/B is uninterpretable.** Your σ is 0.6,
   so anything under about 1 b/B has P(A>B) < 0.88 and needs 11+ seeds.

**Caveats on the arithmetic:** P(A>B) = Φ(d/√2) assumes unpaired normal samples. Pairing
(below) will *reduce* the required N, so these are upper bounds. And the σ estimate is soft.

---

## Before you spend the 9 seeds: is 1.227 b/B actually seed variance?

σ = 0.6 b/B is enormous. For scale, it is roughly half the entire range from GPT-2-small on
web text (1.09) to GPT-2-small on code (1.79). Bouthillier's own case studies show variance on
the order of published improvements, but published improvements in b/B are ~0.05, not 0.6.

**My read: some of your 1.227 is probably not seed variance. It is instability.** Candidate
sources, in the order I would check them:

1. **Routing/culling ties broken nondeterministically.** If two experts tie on fitness rank and
   the tie-break is hash-order or GPU-reduction-order dependent, you get bifurcating training
   trajectories from the same seed. This is the classic way a "nominally identical" config
   isn't.
2. **Newborn expert init interacting with the birth schedule.** If births are triggered by a
   threshold on a noisy statistic, run-to-run the *number and timing* of births differs, which
   means the four runs are not the same configuration.
3. **Non-deterministic kernels.** Bouthillier's Appendix A is unusually candid here: they found
   models with convolutional layers were not reproducible unless `cudnn.deterministic` was
   enabled and `cudnn.benchmark` disabled; that different GPU *models* gave different results;
   and that PyTorch version changes results. For one of their five case studies (PascalVOC
   segmentation) they were **unable to make the pipeline reproducible at all** and had to
   measure the residual as "numerical noise."
4. **Genuine multi-stability.** The MoE ecology paper (file 02) reports three seeds converging
   to identical accuracy through three completely different tier organizations. If your Fabric
   has functionally-degenerate attractors, high variance may be intrinsic — but then it should
   show up as *high variance in internal structure with low variance in b/B*, not high variance
   in b/B.

**The diagnostic that separates these, and it is cheap:** run the same config with every seed
*fixed* and every source of nondeterminism pinned, several times. Bouthillier did exactly this
(200 runs, all seeds fixed) to isolate numerical noise. If your all-fixed runs still spread,
you have a bug or hardware nondeterminism, not seed variance. If they collapse to a point, the
1.227 is real stochasticity and you're in the 9-seeds regime above.

**Do this before spending 9 seeds per arm.** If it's a bug, fixing it may cut σ by an order of
magnitude, which turns your 80,000-seed comparison into a tractable one.

---

## The methodology, in the order it matters for you

### 1. Which sources of variance actually matter (Section 2.2, Figure 1)

Measured across five case studies, ~8 GPU years:

- **Data sampling (bootstrap) is the largest single source.**
- **Model initialization is generally less than 50% of the variance of bootstrap**, and is on
  par with SGD data visit order.
- Hyperparameter optimization induces about as much variance as weight initialization.

**Implication you should feel:** the field's default of "vary the init seed" probes the *small*
source. If you're only varying init, you are underestimating your own variance. Vary data
order and data sampling too.

### 2. Randomize more, not less — the counter-intuitive result

Their central technical finding. For a biased estimator that fixes hyperparameter optimization,
the variance is (Eq. 7):

```
Var(μ̃_(k) | ξ) = Var(R̂_e | ξ)/k  +  ((k−1)/k) · ρ · Var(R̂_e | ξ)
```

Fixing sources of variation induces **correlation ρ between runs**, and the second term does
not shrink with k. So adding more runs while holding seeds fixed buys you almost nothing.
Randomizing *more* sources decorrelates the runs, kills ρ, and makes k actually help.

Empirically: randomizing only weight init converges to the equivalent of just **k=2** ideal
samples. Randomizing all non-HPO sources converges to the equivalent of **k=2 to k=100**.
Same compute.

**Cost figures:** their ideal estimator at k=100 took **1,070 hours**; the cheap all-sources
estimator at k=100 took **21 hours** — a 51× reduction with most of the benefit.

### 3. Don't compare means. Use P(A > B).

Their simulation of decision-rule error rates (Figure 6):

| Criterion | False positives | False negatives |
|---|---|---|
| Single-point comparison | ≈ 10% | ≈ 75% |
| Mean difference, k=50 | < 5% | ≈ 90% |
| **P(A>B) with γ=0.75** | **≈ 5%** | **≈ 30%** |

The single-point comparison is bad in *both* directions. The mean-difference comparison — the
prevalent practice — is not "conservative but safe"; it misses 90% of real effects.

Procedure (Appendix C):
```
P(A > B) = (1/k) Σᵢ 1{ R̂ᴬₑᵢ > R̂ᴮₑᵢ }
```
Compute a confidence interval by **percentile bootstrap** (K resamples of the N pairs), then:

- `CI_min ≤ 0.5` → not significant, draw no conclusion
- `CI_max ≤ γ` → significant but not *meaningful*
- `CI_min > 0.5 ∧ CI_max > γ` → significant and meaningful

### 4. Pair your runs (Appendix C.2)

Rather than not seeding at all, seed *deliberately* with different seeds per run and **re-use
the same seed for both arms of a comparison.** Unpaired, the std of the difference is
σ_A + σ_B; paired, σ_{A−B} ≤ σ_A + σ_B. This reduces required N at no compute cost.

For your growth comparisons: use the same data order, same init seed, same batch schedule for
3→4096 and 2048→4096. The only difference should be the growth schedule. Pairing is likely
worth more to you than any other single change, because your arms share almost all machinery.

### 5. Min/max/median vs mean±std — what they actually recommend

**Neither, as the primary reporting.** They recommend reporting P(A>B) with a bootstrap CI, and
"highlight not only the best-performing procedure, but also all those within the significance
bounds." Their normality check (Figure G.3, Shapiro-Wilk) found performance distributions close
to normal in four of five case studies, so mean±std is not *wrong* as a descriptive summary —
it's just not a decision rule.

For your reporting: give n, mean, std, min, max, and the paired P(A>B) with CI. The min/max
matters for you specifically because your σ is large and readers will want to see the spread.

---

## Related work you named

- **Henderson et al., "Deep Reinforcement Learning That Matters," AAAI 2018.** Cited by
  Bouthillier as part of the "loose hyperparameters lead to non-reproducible benchmarks" line.
  **[CITED, not read this session]** — its specific recommendations (report multiple trials,
  bootstrap CIs, be explicit about seeds) predate and are subsumed by Bouthillier.
- **Dodge et al. on reporting** — **[NOT REACHED]**. The one you asked for that I did not get
  to. The relevant paper is likely "Show Your Work: Improved Reporting of Experimental Results"
  (EMNLP 2019), whose contribution is expected-max-performance-as-a-function-of-budget curves.
  I have not verified this; do not cite it from me.
- Bouthillier & Varoquaux's survey of NeurIPS 2019 / ICLR 2020 experimental methods is the
  source for "most researchers can afford only a small number of model fits" — useful if you
  need to justify a budget request.

---

## Concrete recommendation

1. Pin nondeterminism, run 5× with all seeds fixed. Confirm whether 1.227 is stochasticity or a
   bug. **~5 runs.**
2. If it's a bug, fix it and re-measure σ.
3. Pair 9 seeds per arm on 3→4096 vs 2048→4096. Report P(A>B) with percentile-bootstrap CI.
   **~18 runs.** This establishes your headline result.
4. Retire the 2.009 vs 1.999 question until σ drops by an order of magnitude.
5. Randomize data order and data sampling, not just init, in all future comparisons.

That is ~23 runs to convert your best finding from unsupported to publishable, and it is
almost certainly a better use of GPU time than any additional architecture sweep.
