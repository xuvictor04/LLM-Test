"""Can the REVERSE EXPERT replace Greg's trigram Nov as the novelty signal?

Two readings of "reverse expert", tested against trigram Nov on Greg's in-dist-held vs OOD split:
  nov_trigram   the current Nov.cnt trigram-frequency novelty (the memory hog)
  rev_predict   a counterpart predictor's NEXT-byte error  (high error = unfamiliar)
  rev_recon     an inverse expert RECONSTRUCTING the input from features (autoencoder-style)

We earlier found autoencoder reconstruction is robust to OOD (low error in AND out of dist), so
rev_recon should NOT separate; rev_predict (prediction error) should separate strongly. d' = effect
size (mean_OOD - mean_held)/pooled_std.
"""
import os, sys, math, glob, random
import torch, torch.nn as nn, torch.nn.functional as F
sys.path.insert(0, "/mnt/user-data/outputs/overarching-package")
from system import Nov
torch.manual_seed(0); random.seed(0); torch.set_num_threads(1)
LN2, L, CHUNK = math.log(2), 48, 2000
DATA = "/mnt/user-data/outputs/overarching-package/data"

def load_concat(folder):
    return b"".join(open(f, "rb").read() for f in sorted(glob.glob(os.path.join(folder, "*.txt"))))
def chunks(bb, n, s=0.0, e=1.0):
    seg = bb[int(len(bb) * s):int(len(bb) * e)]
    return [seg[i:i + CHUNK] for i in range(0, len(seg) - CHUNK, CHUNK)][:n]
def wins(bb):
    ws = [list(bb[i:i + L + 1]) for i in range(0, len(bb) - L - 1, L + 1)]; return [w for w in ws if len(w) == L + 1]
def xy(ws):
    t = torch.tensor(ws); return t[:, :L], t[:, 1:L + 1]

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

# base + the reverse-prediction counterpart are the same forward predictor here (prediction error)
train_bytes = b"".join(b"".join(chunks(indist[d], 9999, 0.0, 0.8)) for d in indist)
allb = torch.tensor(list(train_bytes), dtype=torch.long)
base = ByteLM(); opt = torch.optim.Adam(base.parameters(), lr=2e-3)
for _ in range(350):
    ix = torch.randint(0, len(allb) - L - 1, (32,))
    x = torch.stack([allb[i:i + L] for i in ix]); y = torch.stack([allb[i + 1:i + L + 1] for i in ix])
    l = base.loss(x, y); opt.zero_grad(); l.backward(); opt.step()
base.eval()

# reverse-reconstruction expert: inverse map features(x) -> reconstruct input bytes x[i]
recon = nn.Linear(96, 256)
ro = torch.optim.Adam(recon.parameters(), lr=2e-3)
for _ in range(200):
    ix = torch.randint(0, len(allb) - L - 1, (32,)); x = torch.stack([allb[i:i + L] for i in ix])
    with torch.no_grad(): f = base.features(x)
    lg = recon(f); l = F.cross_entropy(lg.reshape(-1, 256), x.reshape(-1)); ro.zero_grad(); l.backward(); ro.step()

# trigram Nov fit on the same in-dist training bytes
nov = Nov(); nov.update(torch.tensor([list(train_bytes)]))

@torch.no_grad()
def s_nov_trigram(bb): x, _ = xy(wins(bb)); return float(nov.score_pos(x).mean())
@torch.no_grad()
def s_rev_predict(bb): x, y = xy(wins(bb)); return base.loss(x, y).item() / LN2
@torch.no_grad()
def s_rev_recon(bb):
    x, _ = xy(wins(bb)); f = base.features(x)
    return F.cross_entropy(recon(f).reshape(-1, 256), x.reshape(-1)).item() / LN2

MECH = {"nov_trigram": s_nov_trigram, "rev_predict": s_rev_predict, "rev_recon": s_rev_recon}
held = [c for d in indist for c in chunks(indist[d], 5, 0.8, 1.0)]
oodc = [c for d in ood for c in chunks(ood[d], 10)]
print(f"held(in-dist)={len(held)}  OOD={len(oodc)}\n")
print(f"  {'signal':<13}{'held':>9}{'OOD':>9}{'d-prime':>9}   verdict")
for name, fn in MECH.items():
    h = [fn(c) for c in held]; o = [fn(c) for c in oodc]
    mh, mo = sum(h) / len(h), sum(o) / len(o)
    vh = sum((z - mh) ** 2 for z in h) / len(h); vo = sum((z - mo) ** 2 for z in o) / len(o)
    dp = (mo - mh) / (math.sqrt(0.5 * (vh + vo)) + 1e-9)
    v = "separates (good novelty)" if dp > 0.8 else ("weak" if dp > 0.3 else "ROBUST/flat — not a novelty signal")
    print(f"  {name:<13}{mh:>9.3f}{mo:>9.3f}{dp:>9.2f}   {v}")
print("\nrev_predict is computed by the base's own forward pass (free, vectorized, no dict).")
