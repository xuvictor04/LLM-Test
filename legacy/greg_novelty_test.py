"""Test each novelty mechanism inside GREG's structure (real in-dist-held vs OOD-source split).

Novelty's job in Greg: separate FAMILIAR (in-distribution) from GENUINELY-NEW (held-out OOD sources)
so it can scale learning + trigger growth. We score each candidate mechanism on Greg's actual held
(unseen chunks of seen domains) vs OOD (eng_OOD=Sherlock, code_OOD=Rust) chunks and report the
effect-size separation d' = (mean_OOD - mean_held)/pooled_std. d' > 0 = flags OOD as more novel.

Mechanisms:
  surprise    base CE (bits/byte) on the chunk                        [familiarity via loss]
  mem_cos     1 - kNN cosine of base-feature gist to in-dist memory   [Greg-native familiarity]
  bigram_knn  1 - kNN cosine of byte-bigrams to in-dist memory        [ORIGINAL system_novelty]
  rms_z       RMS z-distance of byte-histogram from in-dist EMA       [ORIGINAL node_novelty]
  dS          compression-progress of a fresh expert on the chunk     [LEARNABILITY, from the arc]
  gzip_head   min(base_bpb,8) - gzip_bpb                              [LEARNABILITY, cheap]
"""
import os, sys, math, gzip, glob, random
import torch, torch.nn as nn, torch.nn.functional as F
sys.path.insert(0, "/mnt/user-data/outputs/cognitive-system")
from system_novelty import byte_features, _cos
from node_novelty import _RunningStats
from collections import Counter
torch.manual_seed(0); random.seed(0); torch.set_num_threads(1)
FLOOR, LN2, L = 8.0, math.log(2), 48
CHUNK = 2000

def load_concat(folder):
    bb = b""
    for f in sorted(glob.glob(os.path.join(folder, "*.txt"))):
        bb += open(f, "rb").read()
    return bb
def chunks(bb, n, start=0.0, end=1.0):
    a, b = int(len(bb) * start), int(len(bb) * end); seg = bb[a:b]
    out = [seg[i:i + CHUNK] for i in range(0, len(seg) - CHUNK, CHUNK)]
    return out[:n]
def wins(bb):
    ws = [list(bb[i:i + L + 1]) for i in range(0, len(bb) - L - 1, L + 1)]
    return [w for w in ws if len(w) == L + 1]
def xy(ws):
    t = torch.tensor(ws); return t[:, :L], t[:, 1:L + 1]

DATA = "/mnt/user-data/outputs/overarching-package/data"
indist = {d: load_concat(f"{DATA}/train/{d}") for d in ["eng", "py", "c", "num"]}
ood = {d: load_concat(f"{DATA}/ood/{d}") for d in os.listdir(f"{DATA}/ood")}

class Block(nn.Module):
    def __init__(s, d, h):
        super().__init__(); s.h = h; s.ln1 = nn.LayerNorm(d); s.qkv = nn.Linear(d, 3 * d); s.proj = nn.Linear(d, d)
        s.ln2 = nn.LayerNorm(d); s.mlp = nn.Sequential(nn.Linear(d, 4 * d), nn.GELU(), nn.Linear(4 * d, d))
    def forward(s, x):
        B, T, D = x.shape; y = s.ln1(x); q = s.qkv(y).reshape(B, T, 3, s.h, D // s.h).permute(2, 0, 3, 1, 4)
        a = F.scaled_dot_product_attention(q[0], q[1], q[2], is_causal=True)
        x = x + s.proj(a.transpose(1, 2).reshape(B, T, D)); return x + s.mlp(s.ln2(x))
class ByteLM(nn.Module):
    def __init__(s, d=96, nl=2, h=4):
        super().__init__(); s.emb = nn.Embedding(256, d); s.pos = nn.Embedding(256, d)
        s.blocks = nn.ModuleList([Block(d, h) for _ in range(nl)]); s.lnf = nn.LayerNorm(d); s.head = nn.Linear(d, 256)
    def features(s, x):
        h = s.emb(x) + s.pos(torch.arange(x.shape[1]))[None]
        for b in s.blocks: h = b(h)
        return s.lnf(h)
    def out(s, x): return s.head(s.features(x))
    def loss(s, x, y): return F.cross_entropy(s.out(x).reshape(-1, 256), y.reshape(-1))

# ---- train base on in-distribution (Greg's training domains) ----
train_bytes = b"".join(chunks_to_bytes := [b"".join(chunks(indist[d], 9999, 0.0, 0.8)) for d in indist])
allb = torch.tensor(list(train_bytes), dtype=torch.long)
base = ByteLM(); opt = torch.optim.Adam(base.parameters(), lr=2e-3)
for _ in range(350):
    ix = torch.randint(0, len(allb) - L - 1, (32,))
    x = torch.stack([allb[i:i + L] for i in ix]); y = torch.stack([allb[i + 1:i + L + 1] for i in ix])
    l = base.loss(x, y); opt.zero_grad(); l.backward(); opt.step()
base.eval()

# ---- memory banks built from in-dist TRAIN chunks ----
bank_chunks = [c for d in indist for c in chunks(indist[d], 16, 0.0, 0.8)]
@torch.no_grad()
def gist(bb):
    x, _ = xy(wins(bb)); return base.features(x).mean((0, 1))
gist_bank = torch.stack([gist(c) for c in bank_chunks]); gist_bank = F.normalize(gist_bank, dim=1)
bigram_bank = [byte_features(c.decode("latin1")) for c in bank_chunks]
rms = _RunningStats(256, momentum=0.95, warmup=3)
def bytehist(bb):
    v = torch.zeros(256)
    for cc in bb: v[cc] += 1.0
    return v / (v.sum() + 1e-9)
for c in bank_chunks: rms.update(bytehist(c))

# ---- mechanisms ----
@torch.no_grad()
def m_surprise(bb): x, y = xy(wins(bb)); return base.loss(x, y).item() / LN2
@torch.no_grad()
def m_mem_cos(bb):
    g = F.normalize(gist(bb), dim=0); sims = (gist_bank @ g).sort(descending=True).values[:5]
    return float(1 - sims.mean())
def m_bigram_knn(bb):
    f = byte_features(bb.decode("latin1")); sims = sorted((_cos(f, m) for m in bigram_bank), reverse=True)[:5]
    return 1 - sum(sims) / len(sims)
def m_rms_z(bb): return rms.score(bytehist(bb))
def m_gzip_head(bb):
    g = 8.0 * len(gzip.compress(bb, 9)) / len(bb); return min(m_surprise(bb), FLOOR) - g
def m_dS(bb):
    ws = wins(bb); n = len(ws) // 2
    xt, yt = xy(ws[:n]); xh, yh = xy(ws[n:])
    m = ByteLM(); 
    with torch.no_grad(): before = m.loss(xh, yh).item() / LN2
    op = torch.optim.Adam(m.parameters(), lr=2e-3)
    for _ in range(25):
        ix = torch.randint(0, xt.shape[0], (24,)); l = m.loss(xt[ix], yt[ix]); op.zero_grad(); l.backward(); op.step()
    with torch.no_grad(): after = m.loss(xh, yh).item() / LN2
    return max(0.0, FLOOR - after) - max(0.0, FLOOR - before)

MECH = {"surprise": m_surprise, "mem_cos": m_mem_cos, "bigram_knn": m_bigram_knn,
        "rms_z": m_rms_z, "dS": m_dS, "gzip_head": m_gzip_head}

held_chunks = [c for d in indist for c in chunks(indist[d], 5, 0.8, 1.0)]      # unseen chunks, seen domains
ood_chunks = [c for d in ood for c in chunks(ood[d], 10, 0.0, 1.0)]            # unseen sources
print(f"base trained; held chunks={len(held_chunks)} (in-dist) | OOD chunks={len(ood_chunks)}\n")
print(f"  {'mechanism':<12}{'held':>9}{'OOD':>9}{'d-prime':>9}   separates OOD as novel?")
rows = []
for name, fn in MECH.items():
    h = [fn(c) for c in held_chunks]; o = [fn(c) for c in ood_chunks]
    mh, mo = sum(h) / len(h), sum(o) / len(o)
    vh = sum((z - mh) ** 2 for z in h) / len(h); vo = sum((z - mo) ** 2 for z in o) / len(o)
    dprime = (mo - mh) / (math.sqrt(0.5 * (vh + vo)) + 1e-9)
    rows.append((name, mh, mo, dprime))
for name, mh, mo, dp in sorted(rows, key=lambda r: r[3], reverse=True):
    verdict = "YES, strong" if dp > 1.0 else ("yes" if dp > 0.3 else ("~no" if dp > -0.3 else "INVERTS"))
    print(f"  {name:<12}{mh:>9.3f}{mo:>9.3f}{dp:>9.2f}   {verdict}")
