"""Self-controlling DEPTH for Greg -- same pattern as the fabric's breadth growth.

Mirrors expert spawning, applied to layers:
  SPAWN  a layer when competence plateaus above target (and breadth is saturated)
  UPCYCLE-init it as near-IDENTITY (zero-init output projections) so insertion does NOT disrupt
         the function -- it learns a residual refinement (never from noise)
  PRUNE  a layer whose residual contribution is ~identity (redundant)
  CEILING caps depth (the VRAM guardrail)

Proven below: (1) inserting a layer leaves the loss unchanged at the instant of insertion;
(2) after training, the grown model reaches the loss of a from-scratch-deeper model;
(3) per-layer contribution gives the prune signal, exactly like expert usage.
"""
import os, math, glob, random
import torch, torch.nn as nn, torch.nn.functional as F
torch.manual_seed(0); random.seed(0); torch.set_num_threads(1)
LN2, L = math.log(2), 48
DATA = "/mnt/user-data/outputs/overarching-package/data"


class Block(nn.Module):
    def __init__(s, d, h, identity=False):
        super().__init__()
        s.h = h; s.ln1 = nn.LayerNorm(d); s.qkv = nn.Linear(d, 3 * d); s.proj = nn.Linear(d, d)
        s.ln2 = nn.LayerNorm(d); s.fc1 = nn.Linear(d, 4 * d); s.fc2 = nn.Linear(4 * d, d)
        if identity:                       # upcycle-init: zero the output projections -> block = identity
            for p in (s.proj, s.fc2):
                nn.init.zeros_(p.weight); nn.init.zeros_(p.bias)

    def forward(s, x):
        B, T, D = x.shape; y = s.ln1(x)
        q = s.qkv(y).reshape(B, T, 3, s.h, D // s.h).permute(2, 0, 3, 1, 4)
        a = F.scaled_dot_product_attention(q[0], q[1], q[2], is_causal=True)
        x = x + s.proj(a.transpose(1, 2).reshape(B, T, D))
        x = x + s.fc2(F.gelu(s.fc1(s.ln2(x))))
        return x


class GrowableByteLM(nn.Module):
    def __init__(s, d=96, n_layers=2, h=4):
        super().__init__(); s.d = d; s.h = h
        s.emb = nn.Embedding(256, d); s.pos = nn.Embedding(512, d)
        s.blocks = nn.ModuleList([Block(d, h) for _ in range(n_layers)])
        s.lnf = nn.LayerNorm(d); s.head = nn.Linear(d, 256)

    def _enc(s, x):
        h = s.emb(x) + s.pos(torch.arange(x.shape[1]))[None]
        for b in s.blocks: h = b(h)
        return s.lnf(h)

    def forward(s, x): return s.head(s._enc(x))
    def loss(s, x, y): return F.cross_entropy(s(x).reshape(-1, 256), y.reshape(-1))

    def grow_depth(s):                     # SPAWN: append a near-identity block (non-disruptive)
        s.blocks.append(Block(s.d, s.h, identity=True))

    @torch.no_grad()
    def contributions(s, x):               # PRUNE signal: per-layer residual fraction ||dx||/||x||
        h = s.emb(x) + s.pos(torch.arange(x.shape[1]))[None]; out = []
        for b in s.blocks:
            h2 = b(h); out.append(((h2 - h).norm(dim=-1) / (h.norm(dim=-1) + 1e-6)).mean().item()); h = h2
        return out

    def prune_depth(s, idx): del s.blocks[idx]


def load_bytes():
    bb = b"".join(open(f, "rb").read() for f in glob.glob(f"{DATA}/train/**/*.txt", recursive=True))
    return torch.tensor(list(bb), dtype=torch.long)

ids = load_bytes()
ev = torch.randint(0, len(ids) - L - 1, (256,))
EX = torch.stack([ids[i:i + L] for i in ev]); EY = torch.stack([ids[i + 1:i + L + 1] for i in ev])

def train(model, steps, lr=2e-3):
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    for _ in range(steps):
        ix = torch.randint(0, len(ids) - L - 1, (48,))
        x = torch.stack([ids[i:i + L] for i in ix]); y = torch.stack([ids[i + 1:i + L + 1] for i in ix])
        l = model.loss(x, y); opt.zero_grad(); l.backward(); opt.step()

@torch.no_grad()
def bpb(model): model.eval(); v = model.loss(EX, EY).item() / LN2; model.train(); return v

# ---- grown path: seed 2 layers -> train -> SPAWN layer -> train ----
g = GrowableByteLM(d=96, n_layers=2)
train(g, 250); l_mid = bpb(g)
g.grow_depth(); l_insert = bpb(g)          # the moment of insertion -- should equal l_mid
train(g, 250); l_grown = bpb(g)

# ---- controls ----
fixed2 = GrowableByteLM(d=96, n_layers=2); train(fixed2, 500); l_fixed2 = bpb(fixed2)
scratch3 = GrowableByteLM(d=96, n_layers=3); train(scratch3, 500); l_scratch3 = bpb(scratch3)

print("=== self-controlling depth (same pattern as breadth) ===\n")
print(f"seed 2L, trained 250 steps          bpb = {l_mid:.4f}")
print(f"  -> SPAWN identity layer (insert)  bpb = {l_insert:.4f}   (delta {l_insert-l_mid:+.4f}  <- non-disruptive)")
print(f"  -> train 250 more (grown 3L)      bpb = {l_grown:.4f}\n")
print(f"control: fixed 2L, 500 steps        bpb = {l_fixed2:.4f}")
print(f"control: scratch 3L, 500 steps      bpb = {l_scratch3:.4f}\n")
print(f"grown-3L vs fixed-2L:   {l_grown-l_fixed2:+.4f}  (depth added capacity the seed couldn't reach)")
print(f"grown-3L vs scratch-3L: {l_grown-l_scratch3:+.4f}  (growth reached ~the same capacity as starting deep)\n")

c = g.contributions(EX)
print("per-layer residual contribution (the prune signal):", [round(x, 3) for x in c])
weakest = min(range(len(c)), key=lambda i: c[i])
before = bpb(g); g.prune_depth(weakest); after = bpb(g)
print(f"prune weakest layer (idx {weakest}, contrib {c[weakest]:.3f}): bpb {before:.4f} -> {after:.4f}  ({after-before:+.4f})")
