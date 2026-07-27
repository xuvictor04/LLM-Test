#!/usr/bin/env python3
"""Is the signature space COLLAPSED, or is the assembler over-fragmenting a perfectly good space?

The genuineness report can only measure separation between the centroids the assembler PRODUCED. If it
produced 13 domains where there are 4 kinds, those 13 centroids are necessarily crowded -- and a low
separation then says nothing about the encoder. This asks the question the report cannot: take the encoder
that a run actually trained, and measure how well it separates the TRUE corpora.

    python3 probe_ckpt_geometry.py CKPT=runs/rerun/ck.pt

Labels are used ONLY to score. Nothing here trains.

READING IT:
  true-label silhouette clearly > 0  -> the space is FINE; the assembler is over-fragmenting (fix creation)
  true-label silhouette ~ 0 or < 0   -> the encoder genuinely cannot separate the kinds (fix the encoder)
The report's COLLAPSE CHECK compares self-assembled centroids against a random-unit-vector null, which is
the wrong null when the population is fragmented -- this script supplies the right one, measured.
"""
import os, sys, math, random

_kv = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a)
CKPT = _kv.get("CKPT", os.environ.get("CKPT", "runs/rerun/ck.pt"))
NPER = int(_kv.get("N", 256))                              # probe windows per corpus
os.environ.setdefault("DATA_MODE", "real")
os.environ.setdefault("DOMAINS", "eng,py,num,c")
os.environ.setdefault("DATA_DIR", "data")
os.environ.setdefault("STREAM_LEN", "200000")              # only used for corpus construction
os.environ.setdefault("ENC_WARMUP", "0")
os.environ["BENCH"] = "1"
for _k in ("WORLD_MODEL", "FABRIC", "EXPERTS"): os.environ.setdefault(_k, "0")

import torch, torch.nn as nn, torch.nn.functional as F
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import self_organize as S

path = CKPT if CKPT.endswith(".pt") and os.path.isfile(CKPT) else os.path.join(CKPT, "ckpt.pt")
if not os.path.isfile(path): sys.exit(f"no checkpoint at {path}")
d = torch.load(path, map_location=S.DEV, weights_only=False)
SIG_D = int(d.get("sig_d", S.SIG_D)); WIN = int(d.get("win", S.WIN))
ew = d["enc"]["emb.weight"]; NV, DMOD = ew.shape


class Enc(nn.Module):                                      # matches SigEncoder exactly; sized from the checkpoint
    def __init__(s, nv, dd, sd):
        super().__init__(); s.emb = nn.Embedding(nv, dd); s.gru = nn.GRU(dd, dd, batch_first=True); s.proj = nn.Linear(dd, sd)
    def forward(s, x): h, _ = s.gru(s.emb(x)); return F.normalize(s.proj(h[:, -1]), dim=-1)


enc = Enc(NV, DMOD, SIG_D).to(S.DEV); enc.load_state_dict(d["enc"]); enc.eval()
print(f"checkpoint {path}\n  encoder: vocab {NV} | d {DMOD} | sig_d {SIG_D} | win {WIN} | step {d.get('step','?')}")
if NV <= 256: print("  (encoder reads the BYTE stream -- probing with bytes, which is what it was trained on)")

CORP = S.CORP; NP = len(CORP)
if NP < 2: sys.exit("need >= 2 corpora")
random.seed(0); torch.manual_seed(0)
wins, ys = [], []
for p, c in enumerate(CORP):
    lim = NV if NV > 256 else 256                          # never index past the embedding
    for _ in range(NPER):
        a = random.randint(0, max(0, len(c) - WIN - 1))
        w = list(c[a:a + WIN])
        if len(w) < WIN: w += [0] * (WIN - len(w))
        wins.append([min(t, lim - 1) for t in w]); ys.append(p)
X = torch.tensor(wins, device=S.DEV); Y = torch.tensor(ys, device=S.DEV)

with torch.no_grad():
    Z = torch.cat([enc(X[i:i + 128]) for i in range(0, X.size(0), 128)])
D = 1 - Z @ Z.t(); n = Z.size(0)
eye = torch.eye(n, dtype=torch.bool, device=S.DEV)
same = Y.unsqueeze(0) == Y.unsqueeze(1)
d_in = D[same & ~eye].mean().item()
d_bt = D[~same].mean().item()
acc = (Y[D.masked_fill(eye, 9e9).argmin(1)] == Y).float().mean().item()

cent = torch.stack([F.normalize(Z[Y == p].mean(0), dim=0) for p in range(NP)])
C = 1 - cent @ cent.t(); C.fill_diagonal_(9e9)
nearest = C.min(1).values
med = C.masked_fill(torch.eye(NP, dtype=torch.bool, device=S.DEV), float("nan"))
cohs = [F.cosine_similarity(Z[Y == p], cent[p].unsqueeze(0)).mean().item() for p in range(NP)]
print(f"\n=== TRUE-LABEL geometry ({NP} corpora x {NPER} windows) ===")
names = os.environ["DOMAINS"].split(",")
for p in range(NP):
    sep = float(nearest[p]); sil = cohs[p] + sep - 1.0
    print(f"  corpus {p} ({names[p] if p < len(names) else '?':>4}): cohesion {cohs[p]:.2f} | "
          f"sep nearest {sep:.2f} | silhouette {sil:+.2f}")
mc = sum(cohs) / NP; ms = float(nearest.mean()); msil = mc + ms - 1.0
rnd = 1.0 / (SIG_D ** 0.5); z = (ms - 1.0) / rnd
print(f"\n  mean cohesion {mc:.2f} | mean nearest separation {ms:.2f} | MEAN TRUE SILHOUETTE {msil:+.2f}")
print(f"  d_within {d_in:.3f} | d_between {d_bt:.3f} | ratio {d_bt/max(1e-9,d_in):.2f} | 1-NN corpus accuracy {acc:.3f}")
print(f"  vs random unit vectors in {SIG_D}-d (1.00 +/- {rnd:.2f}): {z:+.1f} sigma")
print("\n  VERDICT: " + (
    "the encoder SEPARATES the true kinds. A low separation in the run's genuineness report is then a\n"
    "           statement about the ASSEMBLER or about the STREAM, not about the encoder. Check the\n"
    "           SEGMENT/WINDOW config warning first: if a splice segment is only a few analysis windows\n"
    "           long, the clustering scores describe transitions and no assign rule will move them."
    if msil > 0.10 else
    "the encoder does NOT separate the true kinds even with perfect labels. No assign rule can\n"
    "           recover a partition the representation does not contain -- fix the ENCODER."
    if msil < 0.0 else
    "borderline. The kinds are weakly separated; both the encoder and the creation rule are\n"
    "           plausible targets. Widen the probe (N=1024) before concluding."))
print(f"  (1-NN {acc:.3f} is the retrievability of kind; MEAN TRUE SILHOUETTE is its geometric separability.\n"
      f"   They can disagree: kind can be recoverable by nearest-neighbour while centroids sit close.)")
