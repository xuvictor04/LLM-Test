"""Is the reverse-novelty saturation an undertraining artifact?

1-exp(-ce) saturates when ce is high. If the tiny base just has high ce on everything (in-dist
included) because it is barely trained, then training it more should drop in-dist ce below the
saturation knee while OOD stays high -- re-separating the squashed signal. We train to increasing
levels and measure per-example reverse error (raw bits) and 1-exp(-ce) for in-dist held vs OOD.
"""
import os, math, glob, random
import torch, torch.nn as nn, torch.nn.functional as F
torch.manual_seed(0); random.seed(0); torch.set_num_threads(1)
LN2, L, CHUNK = math.log(2), 48, 2000
DATA = "/mnt/user-data/outputs/overarching-package/data"

def load_concat(folder):
    return b"".join(open(f, "rb").read() for f in sorted(glob.glob(os.path.join(folder, "*.txt"))))
def chunks(bb, n, s=0.0, e=1.0):
    seg = bb[int(len(bb) * s):int(len(bb) * e)]
    return [seg[i:i + CHUNK] for i in range(0, len(seg) - CHUNK, CHUNK)][:n]
def wins(bb):
    w = [list(bb[i:i + L + 1]) for i in range(0, len(bb) - L - 1, L + 1)]; return [z for z in w if len(z) == L + 1]
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
    def forward(s, x):
        h = s.emb(x) + s.pos(torch.arange(x.shape[1]))[None]
        for b in s.blocks: h = b(h)
        return s.head(s.lnf(h))

train_bytes = b"".join(b"".join(chunks(indist[d], 9999, 0.0, 0.8)) for d in indist)
allb = torch.tensor(list(train_bytes), dtype=torch.long)
held = [c for d in indist for c in chunks(indist[d], 5, 0.8, 1.0)]
oodc = [c for d in ood for c in chunks(ood[d], 10)]

@torch.no_grad()
def per_example(model, cks):
    bits, sq = [], []
    for c in cks:
        x, _ = xy(wins(c)); lg = model(x)
        cep = F.cross_entropy(lg[:, :-1].reshape(-1, 256), x[:, 1:].reshape(-1), reduction="none").reshape(x.size(0), -1)
        b = cep.mean(1) / LN2
        bits += b.tolist(); sq += (1 - torch.exp(-b * LN2)).tolist()
    return sum(bits) / len(bits), sum(sq) / len(sq)

model = ByteLM(); opt = torch.optim.Adam(model.parameters(), lr=2e-3)
checkpoints = [150, 400, 900, 1800]
print(f"  {'step':>5}{'in_ce':>8}{'OOD_ce':>8}{'in 1-exp':>10}{'OOD 1-exp':>11}{'gap(1-exp)':>12}")
done = 0
for ck in checkpoints:
    for _ in range(ck - done):
        ix = torch.randint(0, len(allb) - L - 1, (48,))
        x = torch.stack([allb[i:i + L] for i in ix]); y = torch.stack([allb[i + 1:i + L + 1] for i in ix])
        l = F.cross_entropy(model(x).reshape(-1, 256), y.reshape(-1)); opt.zero_grad(); l.backward(); opt.step()
    done = ck
    model.eval()
    ih_ce, ih_sq = per_example(model, held); oo_ce, oo_sq = per_example(model, oodc)
    model.train()
    print(f"  {ck:>5}{ih_ce:>8.2f}{oo_ce:>8.2f}{ih_sq:>10.3f}{oo_sq:>11.3f}{oo_sq-ih_sq:>12.3f}")
print("\nif in_ce falls and in 1-exp de-saturates (drops) while OOD stays high -> saturation was undertraining")
