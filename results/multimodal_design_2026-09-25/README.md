# Multimodal design workflow, 2026-09-25

Evidence behind `docs/proposals/03_AUDIO_VIDEO.md`. CPU prototypes at toy scale, mostly one seed:
signals, not results.

- `workflow_result.json`: the whole workflow output. Keys: `map` (the tree's constraints),
  `lit` (literature), `codec` (codec research), `designs` (three routes), `judge` (scores, winner,
  grafts, dissent), `critic` (verdict and issues), `profile` (the GPU slowdown root cause, repaired
  in 4feb65f).
- `prototypes/design-stream`: Route 1, a shared discrete token stream (the winner).
- `prototypes/design-world`: Route 2, continuous latents through WORLD.
- `prototypes/design-hybrid`: Route 3, the hybrid. `synth.py` holds the aud/tones generator and
  inverse that S1 ports; `spec_codec.py` is the spectral FSQ codec.
- `prototypes/judge`: the judge's in-tree 25 Hz spectral codec check.
- `prototypes/profile`: the merge-scan profiling and bench scripts.
- `prototypes/map`, `prototypes/research-codecs`: notes. Third-party source the agents downloaded
  for reading (EnCodec, DAC, Moshi) is deliberately not committed.

Changes made when copying: each prototype's `runs/` subfolder is renamed `run_logs/` so the
repository's `runs/` ignore rule does not drop it. Scripts that write to `runs/` still say
`runs/`. Model checkpoints (`*.pt`) are not committed.
