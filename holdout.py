#!/usr/bin/env python3
"""holdout.py — read the per-domain held-out probe back OUT of a checkpoint.

Every checkpoint stores `holdout` (per-domain bits/byte, as (mean, stderr)) and `holdout_step`, written by
_save_ckpt at the moment of the save. That means the one number a continual-learning run exists for --
ACROSS THE RUN BOUNDARY, what this run did to what was already known -- does not depend on the log surviving.
It is in the model file.

    python3 holdout.py <ckpt>                 # what one checkpoint knew, per domain
    python3 holdout.py <parent> <child>       # the boundary comparison, reconstructed

<ckpt> may be the directory containing ckpt.pt, or the .pt itself.

Written because a pilot-add run finished, wrote a valid checkpoint, and lost its entire report to a tee that
could not open its output file. The measurement was never gone; there was just no way to ask for it.
"""
import os, sys


def _load(p):
    import torch
    if os.path.isdir(p):
        for cand in ("ckpt.pt", "ckpt.prev.pt"):
            if os.path.exists(os.path.join(p, cand)):
                p = os.path.join(p, cand); break
        else:
            sys.exit(f"!! no ckpt.pt or ckpt.prev.pt in {p}")
    if not os.path.exists(p):
        sys.exit(f"!! {p} does not exist")
    # mmap avoids materialising ~GB of memory keys just to read a small dict. Falls back for torch < 2.1 and for
    # checkpoints written with a pickler mmap cannot handle.
    try:
        d = torch.load(p, map_location="cpu", weights_only=False, mmap=True)
    except Exception:
        d = torch.load(p, map_location="cpu", weights_only=False)
    return p, d


def _ms(v):
    """Tolerate older checkpoints that stored a bare float instead of (mean, stderr)."""
    return tuple(v) if isinstance(v, (tuple, list)) else (float(v), 0.0)


def _show(path, d):
    hb, step = d.get("holdout") or {}, d.get("holdout_step")
    print(f"\n{path}")
    print(f"  step {step} | vocab {d.get('tok_vocab', '?')} tokens | tokenizer {d.get('tok_path', '?')}")
    if not hb:
        print("  no held-out probe stored -- written before the probe was added, or the save predates the first probe")
        return hb
    for k in sorted(hb):
        m, e = _ms(hb[k])
        print(f"  {k:<10} {m:.3f} +/- {e:.3f}")
    return hb


def main():
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    p1, d1 = _load(sys.argv[1])
    h1 = _show(p1, d1)
    if len(sys.argv) == 2:
        return
    p2, d2 = _load(sys.argv[2])
    h2 = _show(p2, d2)
    if not h1 or not h2:
        sys.exit("\n!! need a stored probe on BOTH sides to compare")

    print(f"\n=== ACROSS THE RUN BOUNDARY (reconstructed from the checkpoints) ===")
    kept = [k for k in sorted(h2) if k in h1]
    for k in sorted(h2):
        m, e = _ms(h2[k])
        if k not in h1:
            print(f"  {k:<10} {m:.3f} +/- {e:.3f}   NEW -- no baseline, nothing to forget yet")
            continue
        pm, pe = _ms(h1[k])
        d = m - pm; ed = (e ** 2 + pe ** 2) ** 0.5
        # SAME 2-SIGMA TEST the in-run report applies, so the two agree rather than inviting a reading contest.
        verdict = ("WORSE (forgetting)" if d > 2 * ed else
                   "better" if -d > 2 * ed else "HELD (inside the noise)")
        print(f"  {k:<10} was {pm:.3f}  ->  now {m:.3f}   {d:+.3f} +/- {ed:.3f}   {verdict}")
    if kept:
        mean = sum(_ms(h2[k])[0] - _ms(h1[k])[0] for k in kept) / len(kept)
        em = (sum(_ms(h2[k])[1] ** 2 + _ms(h1[k])[1] ** 2 for k in kept) ** 0.5) / len(kept)
        print(f"  mean change on the {len(kept)} domain(s) that existed before: {mean:+.3f} +/- {em:.3f} bits/byte"
              + ("" if abs(mean) > 2 * em else "  -- inside the noise, do not read this as forgetting"))
    print("\n  NOTE: these are the probes as of each SAVE. If the child saved mid-run (CKPT_EVERY), this is that")
    print("  moment, not the end of the run. The log remains the only place the full report lives.")


if __name__ == "__main__":
    main()
