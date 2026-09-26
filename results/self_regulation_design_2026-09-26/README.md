# Self-regulation and source-credibility design workflow, 2026-09-26

This is the evidence behind docs/proposals/04_SELF_REGULATION.md. It answers the owner's request for
self-regulation of focus ("how much the llm focuses on what it wants to"), context awareness
(credibility of sources) and emergence.

It comes from CPU prototypes on a shared synthetic testbed, at toy scale. The testbed has areas of
differing learnability, an unlearnable noise area, a credible source and a false source, and a
late-arriving area. Read every number as a signal, not a result.

## Contents

`workflow_result.json` holds the whole workflow output, under these keys:
- `map`: every hand-set focus decision in the tree, and every signal that could drive it.
- `lit`: the literature.
- `designs`: the three designs.
- `judge`: scores, winner, dissent and the draft proposal.
- `critic`: its verdict and issues.
- `repro`: reruns at new seeds.

`prototypes/` holds the prototypes themselves:
- `testbed/`: the shared synthetic corpus and harness.
- `d1/`: an explicit meta-controller. A learning-progress bandit sets the draw, and a trust weight
  comes from gradient consistency.
- `d2/`: a source-conditioned LM. It gets a source-tag channel with tag dropout, and a readout of
  source agreement from inside the model.
- `d3/`: retention-paced focus. Learning progress sets the allocation, rehearsal is paced by
  forgetting on an online held-out probe, and credibility comes from claim-level truth discovery.
- `judge/`, `critic/`, `repro/`: their reruns and stress tests.

## Headline signals

- **Self-regulated focus ties a fixed replay rate.** Retention-paced focus beats today's planned
  draw. A single hand-set replay rate (27%, spread by deficit) ties it within seed spread.
- **At the tree's default schedule the allocation cannot move.** With 2 live areas the cap forces
  an even split, so only the rehearsal rate is regulated.
- **Claim-level truth discovery finds a fluent liar,** but it measures agreement with the majority.
  It fails under a lying majority, and when a truthful source uses a different format.
- **Source tags with dropout are cheap and improve the tagged read.** The untagged read is about
  unchanged.

## What was changed when copying

- Each `runs/` subfolder is renamed `run_logs/`.
- Checkpoints are not committed.
