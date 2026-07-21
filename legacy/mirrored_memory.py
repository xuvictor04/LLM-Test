"""Assembled episodic memory: dense recall + symbolic mirror + adaptive novelty-gated writes.

One memory, two synchronized faces over the SAME ring-buffer slots:
  dense face   : keys/vals tensors -> batched similarity recall, drop-in for the readout (was Mem)
  symbolic face: folder-path branches, one per slot -> navigate / inspect / consolidate (was the KG)

Writes pass through an ADAPTIVE GATE whose threshold drifts down each step and jumps up when it fires,
so it stores RELATIVE novelty (the unfamiliar) and self-calibrates to the drifting error scale --
no fixed bit threshold. Input is the reverse predictor's per-example error.
"""
import torch, torch.nn.functional as F
from collections import defaultdict


class AdaptiveGate:
    """Threshold drifts DOWN each step, JUMPS UP only when triggered."""
    def __init__(self, theta=3.0, drift=0.02, jump=0.6, floor=1.0):
        self.theta = theta; self.drift = drift; self.jump = jump; self.floor = floor
    def step(self, x):
        if x > self.theta:
            self.theta += self.jump; return True
        self.theta = max(self.floor, self.theta - self.drift); return False


class MirroredMemory:
    def __init__(self, cap, dim, device="cpu", theta=3.0, drift=0.02, jump=0.6, floor=1.0):
        self.cap, self.dim, self.device = cap, dim, device
        self.keys = torch.zeros(cap, dim, device=device)
        self.vals = torch.zeros(cap, dim, device=device)
        self.branch = {}
        self.ptr = 0; self.n = 0
        self.gate = AdaptiveGate(theta, drift, jump, floor)
        self.writes = 0; self.skips = 0

    def read(self, q):
        """Batched dense recall -> (recall, conf). Drop-in for the readout's mem.read(gist)."""
        if self.n == 0:
            return torch.zeros_like(q), torch.zeros(q.size(0), device=q.device)
        ks = self.keys[:self.n]
        sim = F.normalize(q, dim=-1) @ F.normalize(ks, dim=-1).t()
        w = torch.softmax(sim * 8.0, -1)
        return w @ self.vals[:self.n], sim.max(-1).values

    def write(self, keys, vals, novelty, via=0):
        """Per-example adaptive-gated write. novelty: per-example reverse error (B,). via: routed expert id."""
        nov = novelty.tolist() if torch.is_tensor(novelty) else list(novelty)
        wrote = 0
        for i in range(keys.size(0)):
            if self.gate.step(float(nov[i])):
                s = self.ptr
                self.keys[s] = keys[i]; self.vals[s] = vals[i]
                self.branch[s] = {"domain": f"expert_{via}", "novelty": round(float(nov[i]), 3)}
                self.ptr = (self.ptr + 1) % self.cap; self.n = min(self.n + 1, self.cap)
                wrote += 1
        self.writes += wrote; self.skips += keys.size(0) - wrote
        return wrote

    def in_sync(self): return self.n == len(self.branch)

    def consolidate(self, keep_frac=0.7):
        """Review pass ('sleep'): keep the most-novel slots, drop the weakest, compact the buffer.
        Memory curation -- the short-term review half of consolidation; weight-promotion of the
        retained items is done by the trainer's replay. Returns (kept, dropped)."""
        live = sorted(self.branch.keys())
        if not live: return (0, 0)
        scored = sorted(live, key=lambda s: self.branch[s].get("novelty", 0.0), reverse=True)
        keep = sorted(scored[:max(1, int(len(live) * keep_frac))])
        nk = self.keys[keep].clone(); nv = self.vals[keep].clone(); k = len(keep)
        self.keys.zero_(); self.vals.zero_()
        self.keys[:k] = nk; self.vals[:k] = nv
        self.branch = {i: self.branch[old] for i, old in enumerate(keep)}
        self.n = k; self.ptr = k % self.cap
        return (k, len(live) - k)

    def render_tree(self, top=12):
        grp = defaultdict(list)
        for slot, f in self.branch.items():
            grp[f.get("domain", "?")].append((slot, f))
        lines = []
        for dom in sorted(grp):
            lines.append(dom + "/")
            for slot, f in sorted(grp[dom])[:top]:
                lines.append(f"  slot_{slot}/  novelty={f.get('novelty')}")
        return "\n".join(lines)


if __name__ == "__main__":
    torch.manual_seed(0)
    mem = MirroredMemory(cap=8, dim=6, theta=3.0, drift=0.05, jump=0.8)
    # stream of per-example (key, val, reverse-error). baseline ~2.5, a few spikes ~5.
    errs = [2.4, 2.6, 5.1, 2.3, 2.7, 4.9, 2.5, 2.2, 5.3, 2.6]
    for e in errs:
        k = torch.randn(6); v = torch.randn(6)
        mem.write(k[None], v[None], torch.tensor([e]), via=1)
    print(f"writes={mem.writes} skips={mem.skips} (gate kept the spikes, dropped the baseline)")
    print("in_sync:", mem.in_sync())
    print(mem.render_tree())
    r, c = mem.read(torch.randn(2, 6))
    print("batched read shapes:", tuple(r.shape), tuple(c.shape))
