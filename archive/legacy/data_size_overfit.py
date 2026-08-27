"""Is the overfitting caused by small data? Fixed model + steps; vary only training-data size.
Held in-dist set is a CHUNK-LEVEL random holdout (same domain mix as train), so it is a proper
in-distribution generalization measure. If the OOD/in-held gap shrinks as data grows, the rise
was small-data overfitting (revisitation)."""
import os, math, glob, random
import torch, torch.nn as nn, torch.nn.functional as F
torch.manual_seed(0); random.seed(0); torch.set_num_threads(1)
LN2, L = math.log(2), 32
DATA = "/mnt/user-data/outputs/overarching-package/data"

def load_concat(folder):
    return b"".join(open(f, "rb").read() for f in sorted(glob.glob(os.path.join(folder, "*.txt"))))
def chunkify(bb):
    return [list(bb[i:i + L + 1]) for i in range(0, len(bb) - L - 1, L) if len(bb[i:i + L + 1]) == L + 1]

# chunk each in-dist domain, combine, shuffle -> train/held share the same mix
allc = []
for d in ["eng", "py", "c", "num"]:
    allc += chunkify(load_concat(f"{DATA}/train/{d}"))
random.shuffle(allc)
held = allc[:300]; pool = allc[300:]
ood = chunkify(b"".join(load_concat(f"{DATA}/ood/{d}") for d in os.listdir(f"{DATA}/ood")))

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
        super().__init__(); s.emb = nn.Embedding(256, d); s.pos = nn.Embedding(64, d)
        s.blocks = nn.ModuleList([Block(d, h) for _ in range(nl)]); s.lnf = nn.LayerNorm(d); s.head = nn.Linear(d, 256)
    def forward(s, x):
        h = s.emb(x) + s.pos(torch.arange(x.shape[1]))[None]
        for b in s.blocks: h = b(h)
        return s.head(s.lnf(h))

@torch.no_grad()
def bpb(model, chunks, cap=400):
    t = torch.tensor(chunks[:cap]); x, y = t[:, :L], t[:, 1:L + 1]
    return F.cross_entropy(model(x).reshape(-1, 256), y.reshape(-1)).item() / LN2

STEPS, BATCH = 1200, 16
print(f"model d96/L2, {STEPS} steps, batch {BATCH} (fixed); chunk-level random in-dist holdout\n")
print(f"  {'train_chunks':>13}{'epochs':>8}{'train':>8}{'in-held':>9}{'OOD':>8}{'gap(OOD-inheld)':>17}")
for ncar in [900, 3600, 14000]:
    tr_chunks = pool[:ncar]; data = torch.tensor(tr_chunks)
    model = ByteLM(); opt = torch.optim.Adam(model.parameters(), lr=2e-3)
    for _ in range(STEPS):
        ix = torch.randint(0, len(data), (BATCH,)); b = data[ix]
        x, y = b[:, :L], b[:, 1:L + 1]
        l = F.cross_entropy(model(x).reshape(-1, 256), y.reshape(-1)); opt.zero_grad(); l.backward(); opt.step()
    model.eval()
    ep = STEPS * BATCH / ncar
    tr = bpb(model, tr_chunks); ih = bpb(model, held); oo = bpb(model, ood)
    print(f"  {ncar:>13}{ep:>8.1f}{tr:>8.3f}{ih:>9.3f}{oo:>8.3f}{oo-ih:>17.3f}")
print("\ngap shrinks as data grows -> the OOD rise was small-data overfitting (revisitation)")
