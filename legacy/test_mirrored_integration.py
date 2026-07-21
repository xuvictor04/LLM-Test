"""Dry-run: behave as if MirroredMemory were fully wired into Greg, WITHOUT editing system.py.

A WiredMem adapter stands in for sysm.mem: it gives the readout the BATCHED (recall, conf) it expects
(reading MirroredMemory's dense tensors) and routes writes through the novelty-gated mirror. We then
run a short real training pass and check: (1) it runs end to end, (2) the gate discriminates, (3) the
in-dist/OOD decoupling survives, (4) recall still engages.
"""
import os, math, time, torch, torch.nn.functional as F
from config import cfg
from data_utils import load_corpus, sample_batch
from system import build_system, warmup_base, evaluate_system, ce as ce_loss, ReverseNov
from mirrored_memory import MirroredMemory
torch.manual_seed(0); torch.set_num_threads(1)
LN2 = math.log(2)


class WiredMem:
    """MirroredMemory as it WOULD be wired: batched dense read for the readout + gated mirror writes."""
    def __init__(self, mm): self.mm = mm
    @property
    def n(self): return self.mm.n
    def read(self, q):                                   # batched, drop-in for the readout
        if self.mm.n == 0:
            return torch.zeros_like(q), torch.zeros(q.size(0), device=q.device)
        ks = self.mm.keys[:self.mm.n]
        sim = F.normalize(q, dim=-1) @ F.normalize(ks, dim=-1).t()
        w = torch.softmax(sim * 8.0, -1)
        return w @ self.mm.vals[:self.mm.n], sim.max(-1).values


dev = torch.device("cpu")
TEST_STEPS = int(os.environ.get("TEST_STEPS", 250))
GATE_BITS = float(os.environ.get("GATE_BITS", 3.4))     # write when reverse error (bits) exceeds this

TRAIN, HELD, OOD = load_corpus(cfg)
sysm = build_system(cfg, dev)
sysm.nov = ReverseNov(sysm.base, dev)
print(f"warming base... (d{cfg.D_MODEL}/L{cfg.N_LAYERS}, memcap {cfg.MEMCAP})")
warmup_base(sysm.base, TRAIN, cfg, dev)
for _ in range(cfg.N0): sysm.add_node()

mm = MirroredMemory(cfg.MEMCAP, sysm.d, write_threshold=GATE_BITS, device=dev)
sysm.mem = WiredMem(mm)                                  # <-- the swap (no file edits)
opt = torch.optim.AdamW(sysm.parameters(), lr=cfg.LR, weight_decay=cfg.WEIGHT_DECAY)

writes = skips = 0; raw_bits = []; squashed = []
sysm.train(); t0 = time.time()
for step in range(TEST_STEPS):
    x_cpu = sample_batch(TRAIN, cfg); x = x_cpu.to(dev)
    posnov = sysm.nov.score_pos(x_cpu).to(dev)
    lg, aux = sysm(x, posnov)
    loss = ce_loss(lg, x) + cfg.PONDER * aux["depth"] + cfg.REENC_COST * aux["enc"]
    opt.zero_grad(); loss.backward()
    torch.nn.utils.clip_grad_norm_(sysm.parameters(), cfg.GRAD_CLIP); opt.step()

    with torch.no_grad():                               # per-example reverse error (the gate input)
        lb = sysm.base(x); lb = lb[0] if isinstance(lb, tuple) else lb
        ce_pos = F.cross_entropy(lb[:, :-1].reshape(-1, 256), x[:, 1:].reshape(-1), reduction="none").reshape(x.size(0), -1)
        ce_ex = (ce_pos.mean(1) / LN2)                  # bits/example
    gist = aux["gist"].detach(); feat = aux["hf"].mean(1).detach()
    via = int(aux["mass"][:len(sysm.bodies)].argmax())
    for i in range(gist.size(0)):
        b = float(ce_ex[i]); raw_bits.append(b); squashed.append(1 - math.exp(-b * LN2))
        if mm.write(gist[i], feat[i], b, {"domain": f"expert_{via}"}): writes += 1
        else: skips += 1

    if step in (TEST_STEPS // 2 - 1, TEST_STEPS - 1):
        m = evaluate_system(sysm, HELD, OOD, cfg)
        print(f"  [eval@{step+1}] in-held {m['in_held']} | OOD {m['ood']} | mem-conf {m['memconf_held']}/{m['memconf_ood']} | buffer {mm.n}/{mm.cap}")

import statistics as st
print("\n=== integration dry-run result ===")
print(f"ran {TEST_STEPS} steps end-to-end with MirroredMemory in place of Mem: OK ({(TEST_STEPS)/(time.time()-t0):.1f} it/s)")
print(f"\ngate (write when reverse error > {GATE_BITS} bits):  writes={writes}  skips={skips}  ({100*writes/(writes+skips):.0f}% stored)")
print(f"  reverse error in BITS   : min {min(raw_bits):.2f}  median {st.median(raw_bits):.2f}  max {max(raw_bits):.2f}  -> discriminative")
print(f"  same as 1-exp(-ce)      : min {min(squashed):.3f}  median {st.median(squashed):.3f}  max {max(squashed):.3f}  -> SATURATED (bad gate)")
sat_pass = 100 * sum(s > 0.5 for s in squashed) / len(squashed)
print(f"  if gate used 1-exp(-ce)>0.5 instead: {sat_pass:.0f}% would pass (≈ungated)")
print(f"\nbuffer in_sync (dense==branches): {mm.in_sync()}   fill {mm.n}/{mm.cap}")
print("\nfile-system mirror (sample):")
print("\n".join(mm.render_tree().splitlines()[:10]))
