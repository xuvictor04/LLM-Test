# The 2026-09-27 retok fleet's checkpoints (kept off-repo)

The checkpoints are too large for the repository. The owner packed them on the GPU box on
2026-09-27 at 21:23 UTC. That box's `/workspace` was the container's overlay disk, not a
persistent volume, so the copies that survive are the ones the owner downloads. The checksums
below are how any copy is verified.

| File | Bytes | SHA-256 | Contents |
|---|---|---|---|
| `retok_2026-09-27_finals.tar` | 1,745,653,760 | `4f6b3196f01b60b3a7fb8de4ee47fd3533f11be9202369d5e1393ad7e200ab29` | `ckpt/<run>/ckpt.pt` and `ckpt/<run>.dyntok.json` for all 13 runs (k0, k3000, k1000 and k0_nuis at seeds 0-2, and k0_rerun at seed 0); the ring's `.prev` generation is excluded |
| `retok_2026-09-27_k0kept.tar` | 7,642,972,160 | `73b6773f6ac4881ede57f523063f2eadba4b2817d46eb1da4dda0f970add97d8` | `ckpt/keep/k0.s<seed>.w<step>/ckpt.pt` and `.dyntok.json`: k0's 57 periodic saves (every 1,000 windows, seeds 0-2), all coherent (`KEPT.txt` in the fleet archive) |

**What they are for.**
- The finals are the parents for the first after-training tests (register §8 6.1, the
  continuation from the fleet's checkpoints onto a new area).
- The kept copies are the offline control for the retok spike test (register note retok fleet
  (4)): k0 models at the maturity of each act window.

**Resume one.** Unpack a file so that `ckpt/` sits under a directory `<d>`, then run:

    CKPT_RESUME=<d>/ckpt/k1000.s0 CKPT_DIR=<new dir> RUN_SEED=0 DATA_STREAM_BYTES=3780000 \
        TOK_RETOK_EVERY=1000 python3 run.py

The fleet's `PASTE_BACK.txt` has the kept-copy form of the same command. Every run in the fleet
was at commit 319f313.
