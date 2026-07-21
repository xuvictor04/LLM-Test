"""Vectorized experts vs the Python loop -- correctness + speedup.

Greg's fabric currently does:  Bo = torch.stack([b(h) for b in self.bodies], 1)
i.e. a Python for-loop over N experts, each a residual MLP  x + W2(gelu(W1 x)).
That's N separate kernel launches -> latency-bound, throughput collapses as N grows.

Here we stack all expert weights into (N,...) tensors and compute every expert at once
with two batched einsums. Same math, one fused op. We check the outputs match, then time both.
"""
import time, torch, torch.nn as nn, torch.nn.functional as F

torch.manual_seed(0)
DEV = "cuda" if torch.cuda.is_available() else "cpu"
if DEV == "cuda":
    D, H, B, L, NS, ITERS = 512, 2048, 24, 256, [8, 24, 64, 128, 256], 8   # ramped scale
else:
    D, H, B, L, NS, ITERS = 128, 512, 8, 64, [8, 32, 64, 128], 3           # CPU-friendly


class Expert(nn.Module):                             # identical to system.py's Expert
    def __init__(self, dim, hidden):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(dim, hidden), nn.GELU(), nn.Linear(hidden, dim))
    def forward(self, x): return x + self.net(x)


def loop_forward(bodies, h):                          # current Greg path
    return torch.stack([b(h) for b in bodies], 1)     # (B, N, L, d)


def stack_weights(bodies):                            # pack the ModuleList into (N,...) tensors
    eW1 = torch.stack([b.net[0].weight.t() for b in bodies])   # (N, d, H)
    eb1 = torch.stack([b.net[0].bias for b in bodies])         # (N, H)
    eW2 = torch.stack([b.net[2].weight.t() for b in bodies])   # (N, H, d)
    eb2 = torch.stack([b.net[2].bias for b in bodies])         # (N, d)
    return eW1, eb1, eW2, eb2


def vec_forward(W, h):                                # vectorized path -- no Python loop over experts
    eW1, eb1, eW2, eb2 = W
    a = torch.einsum('bld,ndh->bnlh', h, eW1) + eb1[None, :, None, :]
    a = F.gelu(a)
    o = torch.einsum('bnlh,nhd->bnld', a, eW2) + eb2[None, :, None, :]
    return h[:, None] + o                             # (B, N, L, d)


def timed(fn, *a, iters=ITERS):
    if DEV == "cuda": torch.cuda.synchronize()
    for _ in range(2): fn(*a)                         # warmup
    if DEV == "cuda": torch.cuda.synchronize()
    t = time.time()
    for _ in range(iters): fn(*a)
    if DEV == "cuda": torch.cuda.synchronize()
    return (time.time() - t) / iters * 1000           # ms/call


print(f"device={DEV}  d={D} hidden={H} batch={B} ctx={L}\n")
print(f"  {'N experts':>10} {'loop ms':>10} {'vector ms':>11} {'speedup':>9} {'max|diff|':>11}")
for N in NS:
    bodies = nn.ModuleList([Expert(D, H) for _ in range(N)]).to(DEV).eval()
    h = torch.randn(B, L, D, device=DEV)
    W = stack_weights(bodies)
    with torch.no_grad():
        lo, ve = loop_forward(bodies, h), vec_forward(W, h)
        diff = (lo - ve).abs().max().item()
        t_loop = timed(lambda: loop_forward(bodies, h))
        t_vec = timed(lambda: vec_forward(W, h))
    print(f"  {N:>10} {t_loop:>10.1f} {t_vec:>11.1f} {t_loop/t_vec:>8.1f}x {diff:>11.2e}")
    del bodies, h, W
    if DEV == "cuda": torch.cuda.empty_cache()

print("\nmax|diff| ~1e-5 => identical math (float rounding only).  On GPU the speedup grows with N,")
print("because the loop launches N tiny kernels while the vector path is 2 big batched matmuls.")
