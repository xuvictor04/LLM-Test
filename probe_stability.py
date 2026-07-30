#!/usr/bin/env python3
"""Does the system DISCOVER structure, or does it invent a different one every time?

This is the question the clustering scores cannot answer. Purity and V-measure compare a partition to
categories WE spliced in, so a high score means "it reconstructed our scaffold". A high score against
ANOTHER INDEPENDENT RUN means something different and stronger: the structure is in the data, because
two runs that share nothing but the corpora found the same thing.

    # two runs, different SEED, everything else identical
    SEED=1 ... SAVE_CKPT=runs/s1/ck.pt python3 self_organize.py
    SEED=2 ... SAVE_CKPT=runs/s2/ck.pt python3 self_organize.py
    python3 probe_stability.py A=runs/s1/ck.pt B=runs/s2/ck.pt

Each run is treated as a LABELLING FUNCTION over window-space -- encode a window, take the nearest
domain centroid -- so the two are comparable even though their streams, their domain ids and their
domain COUNTS all differ. Both functions are applied to one common probe set drawn from the corpora.

WITH A NULL, because raw agreement is meaningless: two partitions with few large clusters agree a lot
by accident. The same agreement is recomputed against a random relabelling of B that preserves B's
cluster sizes exactly. Only the excess over that floor is evidence of discovery.
"""
import os, sys, math, random
from collections import Counter

_kv = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a)
A_CK = _kv.get("A"); B_CK = _kv.get("B")
NPER = int(_kv.get("N", 512))                              # probe windows per corpus
NULLS = int(_kv.get("NULLS", 20))                          # random relabellings for the floor
if not A_CK or not B_CK:
    sys.exit("usage: probe_stability.py A=<ckpt> B=<ckpt> [N=512] [NULLS=20]")
os.environ.setdefault("DATA_MODE", "real")
os.environ.setdefault("DOMAINS", "eng,py,num,c")
os.environ.setdefault("DATA_DIR", "data")
os.environ.setdefault("STREAM_LEN", "200000")
os.environ.setdefault("ENC_WARMUP", "0")
os.environ["BENCH"] = "1"
for _k in ("WORLD_MODEL", "FABRIC", "EXPERTS"): os.environ.setdefault(_k, "0")

import torch, torch.nn as nn, torch.nn.functional as F
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import self_organize as S


class Enc(nn.Module):
    def __init__(s, nv, dd, sd):
        super().__init__(); s.emb = nn.Embedding(nv, dd); s.gru = nn.GRU(dd, dd, batch_first=True); s.proj = nn.Linear(dd, sd)
    def forward(s, x): h, _ = s.gru(s.emb(x)); return F.normalize(s.proj(h[:, -1]), dim=-1)


def load(tag, path):
    # probe.pt first: it is the same encoder and the same centroids at tens of MB instead of gigabytes, so two runs
    # can be compared on a machine that never touched the GPU they were trained on. Falls back to ckpt.pt.
    p = path if path.endswith(".pt") and os.path.isfile(path) else next(
        (os.path.join(path, n) for n in ("probe.pt", "ckpt.pt") if os.path.isfile(os.path.join(path, n))),
        os.path.join(path, "ckpt.pt"))
    if not os.path.isfile(p): sys.exit(f"no checkpoint at {p}")
    d = torch.load(p, map_location=S.DEV, weights_only=False)
    if "cent" in d and "asm" not in d: d = dict(d, asm={"cent": d["cent"]})   # sidecar stores centroids at top level
    if not d.get("asm") or not d["asm"].get("cent"): sys.exit(f"{p} has no domain centroids")
    nv, dm = d["enc"]["emb.weight"].shape
    e = Enc(nv, dm, int(d.get("sig_d", S.SIG_D))).to(S.DEV); e.load_state_dict(d["enc"]); e.eval()
    ids = sorted(d["asm"]["cent"]); C = torch.stack([d["asm"]["cent"][i].to(S.DEV) for i in ids])
    print(f"  {tag}: {p}  ->  {len(ids)} domains | vocab {nv} | d {dm} | win {d.get('win')} | step {d.get('step','?')}")
    return e, F.normalize(C, dim=-1), int(d.get("win", S.WIN)), nv


print("=== STABILITY: do two independent runs find the SAME structure? ===")
encA, CA, winA, nvA = load("A", A_CK)
encB, CB, winB, nvB = load("B", B_CK)
if winA != winB: sys.exit(f"WIN differs ({winA} vs {winB}) -- the two runs are not comparable")
if CA.size(0) < 2 or CB.size(0) < 2:
    # A run that assembled ONE domain has no partition to agree about, and NMI over a constant labelling is 0 by
    # construction -- which would print as "no more than chance" and read as a finding rather than as an absent
    # experiment. Say what actually happened instead.
    sys.exit(f"\n  CANNOT BE MEASURED: A has {CA.size(0)} domain(s), B has {CB.size(0)}. Stability compares two\n"
             f"  PARTITIONS; a run with a single domain did not partition anything, so there is nothing to agree\n"
             f"  about and NMI would be 0 whatever the data.\n"
             f"  >> check the run logs for '!! ENCODER COLLAPSE' and for '0 boundaries'. On a homogeneous corpus\n"
             f"     the signature encoder shrinks to a point (InfoNCE has no cross-kind negatives), SHIFT_DIST\n"
             f"     never fires, and the assembler is inert. That is the result -- not a stability score.")
WIN = winA

random.seed(0); torch.manual_seed(0)
wins, truth = [], []
for p, c in enumerate(S.CORP):
    for _ in range(NPER):
        a = random.randint(0, max(0, len(c) - WIN - 1))
        w = list(c[a:a + WIN])
        if len(w) < WIN: w += [0] * (WIN - len(w))
        wins.append(w); truth.append(p)


def labels_of(enc, C, nv):
    out = []
    with torch.no_grad():
        for s in range(0, len(wins), 128):
            X = torch.tensor([[min(t, nv - 1) for t in w] for w in wins[s:s + 128]], device=S.DEV)
            out += (C @ enc(X).t()).argmax(0).tolist()
    return out


LA, LB = labels_of(encA, CA, nvA), labels_of(encB, CB, nvB)


def nmi(x, y):
    n = len(x); cx, cy = Counter(x), Counter(y); cxy = Counter(zip(x, y))
    hx = -sum(v / n * math.log(v / n) for v in cx.values())
    hy = -sum(v / n * math.log(v / n) for v in cy.values())
    i = sum(v / n * math.log((v / n) / (cx[a] / n * cy[b] / n)) for (a, b), v in cxy.items())
    return 0.0 if hx + hy == 0 else 2 * i / (hx + hy)


real = nmi(LA, LB)
_r = random.Random(0)
nulls = []
for _ in range(NULLS):                                     # preserve B's cluster SIZES, destroy its correspondence
    sh = LB[:]; _r.shuffle(sh); nulls.append(nmi(LA, sh))
null = sum(nulls) / len(nulls)
tA, tB = nmi(LA, truth), nmi(LB, truth)

print(f"\n  probe: {len(wins)} windows over {len(S.CORP)} corpora, WIN={WIN}")
print(f"  A used {len(set(LA))} of its domains on this probe; B used {len(set(LB))}")
print(f"\n  AGREEMENT A vs B (normalised mutual information)  {real:.3f}")
print(f"  shuffled-B floor (same cluster sizes, no correspondence)  {null:.3f}"
      f"   [{min(nulls):.3f}-{max(nulls):.3f} over {NULLS} draws]")
print(f"  EXCESS OVER THE FLOOR  {real - null:+.3f}")
print(f"\n  for reference, agreement with the SEEDED corpora: A {tA:.3f} | B {tB:.3f}")
print(f"  (a run can agree strongly with the other run while both disagree with the seeded labels --"
      f" that would be DISCOVERY of structure we did not put there.)")
print("\n  VERDICT: " + (
    "the two runs found SUBSTANTIALLY THE SAME partition. The structure is in the data, not in the\n"
    "           initialisation -- this is the discovery evidence the clustering scores cannot give."
    if real - null > 0.30 else
    "PARTIAL agreement. Some shared structure, but a large part of each partition is run-specific.\n"
    "           Raise N, and compare against agreement-with-seeds above before concluding."
    if real - null > 0.10 else
    "NO MORE THAN CHANCE. The two runs did not find the same structure, so what either found is a\n"
    "           property of that run rather than of the data. Domain identity is not reproducible here."))
