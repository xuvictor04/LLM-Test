# Learning-signal classification: SURPRISE and RECONSTRUCTION — what each gates, and when [USER — the "handling"]

The two signals are DIFFERENT and drive DIFFERENT things. Keeping them separate is the fix for the project's oldest bug
(B conflated them). This is the "handling" to set BEFORE building.

## The two signals
- **SURPRISE** = `1 − p_model(true token)` — a FORWARD signal. "I did not predict this." Meaning: novelty / where the
  model is wrong-footed. **Drives LEARNING:** where to WRITE to memory, where to DISCOVER a new meaning / domain / expert
  (and, on genuinely new input, a new Sense/modality), where to ADAPT. NOT a truth signal.
- **RECONSTRUCTION error** = decode the representation back (reverse embedder) and COMPARE to the original / expectation —
  a REVERSE signal. "I cannot regenerate this from my understanding." Meaning: lack of UNDERSTANDING. **Drives
  VERIFICATION:** is this genuinely grasped, or only surface-matched?

## The 2×2 that surprise-alone could never see
|                              | low reconstruction error (understood)        | high reconstruction error (not understood)      |
|------------------------------|----------------------------------------------|-------------------------------------------------|
| **low surprise** (expected)  | known & understood — nothing to do           | shallow match / memorized-not-grasped → LEARN deeper |
| **high surprise** (novel)    | genuinely new & already coherent → INTEGRATE | new & not yet grasped → DISCOVER, then verify   |

This is the classification the user means by "reconstruction and surprise ... for the learn signals and times": the PAIR
decides WHAT to learn and WHEN, and separately WHEN something is verified/understood. Surprise alone collapses the whole
table to its left/right split and cannot tell "novel" from "wrong" — the B failure.

## Timing ("times")
- SURPRISE fires at PERCEPTION (forward pass, per token/window) → gates writes / discovery immediately.
- RECONSTRUCTION fires on DEMAND at verify/understand time (reverse pass) → gates whether a provisional sense/expert is
  trusted and INTEGRATED (the "reconcile → understand" stage of the knowledge-base pipeline).

**Status:** the handling spec to build against. Exact reconstruction target + thresholds still open (see the gap list).
**Source:** user, session 2026-07-21.
</content>
