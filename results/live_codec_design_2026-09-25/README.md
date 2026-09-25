# Live-codec design workflow, 2026-09-25

This is the evidence behind the owner's instruction: "I don't want anything frozen or fixed unless
absolutely necessary. I am also reconsidering the hz."

It comes from CPU prototypes at toy scale, on 1 s clips from aud/tones and aud/melody.
Read every number as a signal, not a result.

## Contents

`workflow_result.json` holds the whole workflow output, under these keys:
- `map`: every freeze and fixed-rate dependency in the tree and in Proposal 03, plus Q-RUN-8 in depth.
- `lit`: the literature, with sources verified or unverified.
- `designs`: the three prototyped designs.
- `judge`: scores, the winner, grafts, and the synthesis.
- `critic`: its verdict and issues.
- `repro`: independent reruns at the same and new seeds.

`prototypes/` holds the prototypes themselves:
- `d1/`: a living discrete codec behind a snapshot refreshed at each act, an anchor hinge, online
  acoustic BPE, and the mid-epoch act (Q-RUN-8 option a), prototyped with bit-identical resume.
- `d2/`: a live continuous codec whose chunk latents feed the LM end to end, with an H-Net router
  choosing the rate.
- `d3/`: two timescales. A live student feeds an EMA teacher, codes are cut just in time, LM rows
  are built from lattice coordinates, and a nested multi-rate codec lets the rate vary.
- `judge/`, `critic/`, `repro/`: their reruns and extensions.
  `repro/compare_out.txt` puts the reproduced numbers side by side.
- `map/`: the mapper's notes.

## Headline signals (see `repro` for per-seed values)

- **Lattice-coordinate media rows are the largest lever.** They cut bits per audio-second by 11-17%,
  at 4 of 4 seeds, in two harnesses.
- **A live codec at low plasticity beats a frozen one.** It won 18 of 18 paired readings over
  4 LM seeds. The caveat is that all of those runs share one codec initialisation.
- **At high plasticity a live codec trades LM bits for reconstruction,** costing +3% to +8% bits/s.
- **No per-segment adaptive rate beat a fixed stride.** This held over 3 seeds, but only on 1 s clips.
- **The mid-epoch act works:** minted ids reach the stream, and resume is bit-identical.
- **A live codec lowers timbre recoverability** even while mel improves.

## What was changed when copying

- Each prototype's `runs/` folder is renamed `run_logs/`, so the repository's `runs/` ignore rule
  does not drop it.
- Model checkpoints are not committed.
- Third-party repositories the agents cloned for reading are not committed: H-Net, AQM, REPA-E,
  DreamerV3 and IRIS.
