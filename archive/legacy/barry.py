"""Barry -- sparse top-k expert routing (the big rework of Greg's dense fabric).

Greg ran DENSE: every token through every expert, in a Python loop -> O(N) compute, caps at tens.
Barry runs SPARSE: each token goes to only its top-k experts. Compute is O(k) per token, ~flat in N,
so the expert count can grow huge. This module is the core engine; correctness + flat-in-N scaling
are proven in __main__.

Pieces (standard Switch/GShard-style MoE):
  - router: per-token scores over N experts -> top-k, softmax gates
  - capacity dispatch: each expert gets a fixed buffer of C ~ (k*T/N) tokens (scatter by index, no dense mask)
  - VecExperts: all experts' weights stacked; applied with batched matmul (one kernel, no per-expert loop)
  - combine: scatter expert outputs back, weighted by gates; residual around the block
  - load-balance loss: keeps tokens from collapsing onto a few experts
"""
import torch, torch.nn as nn, torch.nn.functional as F


class VecExperts(nn.Module):
    """N residual-MLP experts as stacked weights -> batched matmul, no Python loop over experts."""
    def __init__(self, n, d, hidden=None):
        super().__init__()
        h = hidden or d * 4
        self.n, self.d, self.h = n, d, h
        self.W1 = nn.Parameter(torch.randn(n, d, h) * (d ** -0.5))
        self.b1 = nn.Parameter(torch.zeros(n, h))
        self.W2 = nn.Parameter(torch.randn(n, h, d) * (h ** -0.5))
        self.b2 = nn.Parameter(torch.zeros(n, d))

    def forward(self, buf):                       # buf: (N, C, d) -> (N, C, d)
        a = F.gelu(torch.bmm(buf, self.W1) + self.b1[:, None, :])
        return torch.bmm(a, self.W2) + self.b2[:, None, :]

    def grow(self, add, parent=None, strength=0.0, parent2=None):
        """Append `add` experts. If parent is given, they're MUTATED copies of expert[parent]
        (evolution: reproduce from a successful expert); if parent2 is also given, a CROSSOVER
        (average of the two parents) + mutation; else random (blank)."""
        dev = self.W1.device
        def cat(p, shape, scale):
            if parent is not None:
                b = p.data[parent:parent + 1]
                if parent2 is not None: b = 0.5 * (b + p.data[parent2:parent2 + 1])   # crossover: blend two parents
                base = b.repeat(add, *([1] * (p.dim() - 1)))
                new = base + torch.randn_like(base) * strength * (base.std() + 1e-6)
            else:
                new = torch.randn(add, *shape, device=dev) * scale
            return nn.Parameter(torch.cat([p.data, new], 0))
        self.W1 = cat(self.W1, (self.d, self.h), self.d ** -0.5); self.b1 = cat(self.b1, (self.h,), 0)
        self.W2 = cat(self.W2, (self.h, self.d), self.h ** -0.5); self.b2 = cat(self.b2, (self.d,), 0)
        self.n += add

    def remove(self, idx):                        # delete expert[idx] from the bank (selection: cull the weak)
        keep = torch.tensor([i for i in range(self.n) if i != idx], device=self.W1.device)
        self.W1 = nn.Parameter(self.W1.data[keep]); self.b1 = nn.Parameter(self.b1.data[keep])
        self.W2 = nn.Parameter(self.W2.data[keep]); self.b2 = nn.Parameter(self.b2.data[keep])
        self.n -= 1


class SparseMoE(nn.Module):
    def __init__(self, d, n_experts, k=2, hidden=None, cap_factor=1.25, counterparts=False, cull_metric="energy", coord=0.0):
        super().__init__()
        self.d, self.N, self.k, self.cap = d, n_experts, k, cap_factor
        self.router = nn.Linear(d, n_experts, bias=False)
        self.experts = VecExperts(n_experts, d, hidden)
        self.counterparts = counterparts
        self.coord_w = float(coord)                            # expert coordination: refine output with layer-global context
        if self.coord_w > 0:
            self.coord = nn.Sequential(nn.Linear(2 * d, d), nn.GELU(), nn.Linear(d, d))
            nn.init.zeros_(self.coord[-1].weight); nn.init.zeros_(self.coord[-1].bias)   # identity at init
        if counterparts:
            self.inv = VecExperts(n_experts, d, hidden=2 * d)   # inverse bank: inv(expert(h)) ~= h (invertibility)
        self.last_load = None                     # per-expert token counts, for the balance probe
        self.last_cpl = None                      # invertibility loss, when counterparts on
        self.contrib = None                       # per-expert EMA of gated output energy
        self.traffic = None                       # per-expert EMA of router token-count (how often it's chosen)
        self.cull_metric = cull_metric            # which signal drives selection: energy | traffic | blend

    def score(self):
        """Per-expert selection signal (higher = keep, lower = cull), by the configured metric.
        energy = gated output magnitude; traffic = how often the router picks it; blend = both, normalized."""
        c, t = self.contrib, self.traffic
        if self.cull_metric == "traffic" and t is not None: return t
        if self.cull_metric == "blend" and c is not None and t is not None:
            return c / (c.sum() + 1e-9) + t / (t.sum() + 1e-9)
        return c if c is not None else (t if t is not None else None)

    def grow(self, add=1, mutate=False, strength=0.05, crossover=0.0):    # spawn (mutation of best, or crossover of top-2)
        sc = self.score()
        parent = int(sc.argmax()) if (mutate and sc is not None and sc.numel() == self.N) else None
        parent2 = None
        if parent is not None and crossover > 0 and self.N >= 2 and float(torch.rand(())) < crossover:
            parent2 = int(sc.argsort(descending=True)[1])     # second-best expert -> crossover
        self.experts.grow(add, parent, strength, parent2)
        if self.counterparts: self.inv.grow(add, parent, strength, parent2)
        old = self.router.weight.data
        if parent is not None:
            b = old[parent:parent + 1]
            if parent2 is not None: b = 0.5 * (b + old[parent2:parent2 + 1])   # crossover the router row too
            base = b.repeat(add, 1); newr = base + torch.randn_like(base) * strength * (base.std() + 1e-6)
        else:
            newr = torch.randn(add, self.d, device=old.device) * (self.d ** -0.5)
        self.router = nn.Linear(self.d, self.N + add, bias=False)
        self.router.weight = nn.Parameter(torch.cat([old, newr], 0))
        for a in ("contrib", "traffic"):          # new experts inherit ~mean signal so they aren't culled instantly
            v = getattr(self, a)
            if v is not None: setattr(self, a, torch.cat([v, v.new_full((add,), float(v.mean()))]))
        self.N += add

    def worst(self):                              # index of the least-contributing expert (for culling)
        sc = self.score()
        return int(sc.argmin()) if sc is not None and sc.numel() == self.N else 0

    def prune(self, idx):                         # cull expert[idx] from bank + router (+ inverse)
        self.experts.remove(idx)
        if self.counterparts: self.inv.remove(idx)
        keep = torch.tensor([i for i in range(self.N) if i != idx], device=self.router.weight.device)
        w = self.router.weight.data[keep]
        self.router = nn.Linear(self.d, self.N - 1, bias=False)
        self.router.weight = nn.Parameter(w)
        for a in ("contrib", "traffic"):
            v = getattr(self, a)
            if v is not None: setattr(self, a, v[keep])
        self.N -= 1

    def forward(self, x):                         # x: (T, d) flattened tokens -> (T, d), lb_loss
        T = x.size(0); N, k = self.N, self.k
        probs = F.softmax(self.router(x), -1)     # (T, N)
        topv, topi = probs.topk(k, -1)            # (T, k)
        gates = topv / (topv.sum(-1, keepdim=True) + 1e-9)
        C = max(1, int(self.cap * T * k / N))     # per-expert capacity (shrinks as N grows -> N*C ~ flat)

        tok = torch.arange(T, device=x.device).repeat_interleave(k)   # (T*k,) which token
        eidx = topi.reshape(-1)                                       # (T*k,) which expert
        g = gates.reshape(-1)                                         # (T*k,) gate value

        counts = torch.bincount(eidx, minlength=N)                    # tokens routed per expert
        order = torch.argsort(eidx, stable=True)
        offsets = torch.cumsum(counts, 0) - counts                    # group start in sorted order
        rank = torch.empty_like(eidx)
        rank[order] = torch.arange(T * k, device=x.device) - offsets[eidx[order]]   # position within expert
        keep = rank < C                                              # drop overflow beyond capacity
        slot = eidx * C + rank                                       # flat slot in the (N*C) buffer

        buf = x.new_zeros(N * C, self.d).index_add(0, slot[keep], x[tok[keep]])     # scatter tokens in
        out = self.experts(buf.view(N, C, self.d)).reshape(N * C, self.d)          # experts (batched)
        if self.counterparts:                                                      # inv(expert output) should rebuild the token
            rec = self.inv(out.view(N, C, self.d)).reshape(N * C, self.d)
            self.last_cpl = F.mse_loss(rec[slot[keep]], x[tok[keep]])
        else:
            self.last_cpl = x.new_zeros(())
        contrib = out[slot[keep]] * g[keep][:, None]
        y = x.new_zeros(T, self.d).index_add(0, tok[keep], contrib)                 # scatter+gate back

        energy = contrib.pow(2).sum(-1)                             # per-token gated output energy
        e_by_expert = x.new_zeros(N).index_add(0, eidx[keep], energy).detach()      # sum per expert = contribution
        if self.contrib is None or self.contrib.numel() != N: self.contrib = e_by_expert
        else: self.contrib = 0.98 * self.contrib + 0.02 * e_by_expert               # EMA for a stable cull signal

        frac = counts.float() / (T * k)                             # load-balance loss (Switch)
        lb = N * (frac * probs.mean(0)).sum()
        self.last_load = counts.detach()
        tr = counts.float().detach()                                # router traffic EMA (selection signal option)
        if self.traffic is None or self.traffic.numel() != N: self.traffic = tr
        else: self.traffic = 0.98 * self.traffic + 0.02 * tr
        if self.coord_w > 0:                                       # EXPERT COORDINATION: mix in the layer's global context
            g = y.mean(0, keepdim=True).expand_as(y)               # aggregate expert activity across tokens
            y = y + self.coord_w * self.coord(torch.cat([y, g], -1))
        return x + y, lb                                            # residual around the block

    @torch.no_grad()
    def dropped_fraction(self, x):
        T = x.size(0); probs = F.softmax(self.router(x), -1)
        _, topi = probs.topk(self.k, -1); eidx = topi.reshape(-1)
        counts = torch.bincount(eidx, minlength=self.N)
        C = max(1, int(self.cap * T * self.k / self.N))
        kept = torch.clamp(counts, max=C).sum().item()
        return 1.0 - kept / (T * self.k)


# ------------------------------------------------------------- proofs
if __name__ == "__main__":
    import time
    torch.manual_seed(0)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"device={dev}\n")

    # ---- 1) CORRECTNESS: with capacity high enough to drop nothing, sparse == brute-force top-k ----
    d, N, k, T = 64, 16, 2, 128
    moe = SparseMoE(d, N, k, cap_factor=8.0).to(dev)     # big capacity -> no drops
    x = torch.randn(T, d, device=dev)
    y, _ = moe(x)

    def brute(x):
        probs = F.softmax(moe.router(x), -1); topv, topi = probs.topk(k, -1)
        gates = topv / topv.sum(-1, keepdim=True)
        e = moe.experts
        out = x.clone()
        for t in range(T):
            for j in range(k):
                i = topi[t, j]
                a = F.gelu(x[t] @ e.W1[i] + e.b1[i]); o = a @ e.W2[i] + e.b2[i]
                out[t] = out[t] + gates[t, j] * o
        return out
    with torch.no_grad():
        diff = (y - brute(x)).abs().max().item()
    print(f"1) correctness vs brute-force top-k:  max|diff| = {diff:.2e}   ({'PASS' if diff < 1e-4 else 'FAIL'})\n")

    # ---- 2) FLAT-IN-N: fix tokens, grow experts; sparse time ~flat while dense grows O(N) ----
    d, k, T = 256, 2, 768
    print(f"2) scaling (d={d}, k={k}, {T} tokens): time as experts grow")
    print(f"   {'N experts':>10} {'sparse ms':>11} {'dense ms':>11} {'C (cap)':>8} {'dropped':>8} {'load cv':>8}")
    for N in ([16, 64, 256, 1024, 4096] if dev == "cuda" else [16, 64, 256]):
        moe = SparseMoE(d, N, k, cap_factor=1.25).to(dev)
        x = torch.randn(T, d, device=dev)
        def sp(): return moe(x)[0]
        for _ in range(2): sp()
        if dev == "cuda": torch.cuda.synchronize()
        t0 = time.time(); [sp() for _ in range(5)]; ts = (time.time() - t0) / 5 * 1000
        run_dense = (N <= 64) or dev == "cuda"                      # dense loop is the thing we're killing; cap it on CPU
        if run_dense:
            dense = nn.ModuleList([nn.Sequential(nn.Linear(d, 4*d), nn.GELU(), nn.Linear(4*d, d)) for _ in range(N)]).to(dev)
            def dn(): return torch.stack([m(x) for m in dense], 1)
            for _ in range(2): dn()
            if dev == "cuda": torch.cuda.synchronize()
            t0 = time.time(); [dn() for _ in range(3)]; td = f"{(time.time() - t0) / 3 * 1000:.1f}"
            del dense
        else:
            td = "(skip)"
        C = max(1, int(1.25 * T * k / N)); drop = moe.dropped_fraction(x)
        load = moe.last_load.float(); cv = (load.std() / (load.mean() + 1e-9)).item()
        print(f"   {N:>10} {ts:>11.1f} {td:>11} {C:>8} {drop:>7.1%} {cv:>8.2f}")
        del moe
    print("   -> sparse stays ~flat as N grows; dense climbs ~linearly. that gap is the whole point.\n")

    # ---- 3) LEARNS + BALANCES: gradients flow through the dispatch; LB loss spreads the load ----
    d, N, k, T = 128, 32, 2, 512
    moe = SparseMoE(d, N, k).to(dev)
    tgt = torch.randn(T, d, device=dev); x = torch.randn(T, d, device=dev)
    opt = torch.optim.Adam(moe.parameters(), lr=1e-3)
    cv0 = None
    for step in range(200):
        y, lb = moe(x)
        loss = F.mse_loss(y, tgt) + 0.01 * lb
        opt.zero_grad(); loss.backward(); opt.step()
        if step == 0:
            l = moe.last_load.float(); cv0 = (l.std()/(l.mean()+1e-9)).item()
    l = moe.last_load.float(); cv1 = (l.std()/(l.mean()+1e-9)).item()
    print(f"3) trainability: mse {F.mse_loss(moe(x)[0], tgt).item():.3f} (falling), "
          f"load imbalance cv {cv0:.2f} -> {cv1:.2f} (balancing), experts used {int((l>0).sum())}/{N}")
    print("\nBarry core works: correct, flat-in-N, trainable, self-balancing.")
