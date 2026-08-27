"""Measure Greg's memory footprint, focusing on whether anything grows more than expected.

  - Mem (episodic): fixed ring buffer -> bounded, computed directly.
  - model params: counted.
  - Nov.cnt: byte-trigram dict that is NEVER evicted -> measure distinct-trigram growth vs bytes
    processed on Greg's real corpus, and extrapolate to Larry-scale corpora.
"""
import os, sys, glob, resource
sys.path.insert(0, "/mnt/user-data/outputs/overarching-package")
import torch
from system import Nov, Mem
from language import ByteLM

DATA = "/mnt/user-data/outputs/overarching-package/data"
def load_all():
    bb = b""
    for f in glob.glob(f"{DATA}/train/**/*.txt", recursive=True) + glob.glob(f"{DATA}/ood/**/*.txt", recursive=True):
        bb += open(f, "rb").read()
    return bb
corpus = load_all()
print(f"corpus available for probe: {len(corpus)/1e6:.2f} MB\n")

# ---- bounded structures ----
MEMCAP, D = 4096, 128
mem_bytes = 2 * MEMCAP * D * 4
print(f"Mem ring buffer (MEMCAP={MEMCAP}, dim={D}): {mem_bytes/1e6:.2f} MB  (FIXED, bounded)")
try:
    base = ByteLM(d=128, nl=4, h=4, vocab=256, maxlen=512)
    nparam = sum(p.numel() for p in base.parameters())
    print(f"base params (d128/L4): {nparam/1e6:.2f} M  (~{nparam*4/1e6:.1f} MB fp32)\n")
except Exception as e:
    print(f"(base param count skipped: {e})\n")

# ---- Nov.cnt growth ----
def entry_bytes(cnt):
    # python dict table + per-entry (large-int key ~28B, int val ~28B, slot overhead) ~ rough
    return sys.getsizeof(cnt) + len(cnt) * 92

nov = Nov()
print(f"  {'bytes_seen':>12}{'distinct_trigrams':>20}{'~Nov.cnt MB':>14}{'new/KB':>10}")
marks = [50_000, 100_000, 200_000, 400_000, 800_000, len(corpus)]
prev_n = prev_b = 0; rate_tail = 0
step = 20_000
i = 0
while i < len(corpus):
    seg = corpus[i:i + step]
    nov.update(torch.tensor([list(seg)]))
    i += step
    if any(m <= i < m + step for m in marks) or i >= len(corpus):
        n = len(nov.cnt); rate = (n - prev_n) / max(1, (i - prev_b) / 1000)
        print(f"  {i:>12}{n:>20}{entry_bytes(nov.cnt)/1e6:>14.2f}{rate:>10.1f}")
        rate_tail = rate; prev_n, prev_b = n, i

# ---- extrapolation to Larry ----
print()
final_n = len(nov.cnt); final_mb = entry_bytes(nov.cnt) / 1e6
print(f"after {len(corpus)/1e6:.2f} MB: {final_n} distinct trigrams, ~{final_mb:.2f} MB in Nov.cnt")
print(f"tail growth rate: ~{rate_tail:.1f} new trigrams / KB processed")
for gb, label in [(0.1, "100 MB"), (1.0, "1 GB"), (10.0, "10 GB")]:
    extra_kb = (gb * 1e9 - len(corpus)) / 1000
    proj_n = final_n + rate_tail * extra_kb
    proj_mb = (sys.getsizeof(nov.cnt) + proj_n * 92) / 1e6
    cap = 256 ** 3
    proj_n_capped = min(proj_n, cap)
    print(f"  extrapolated to {label:>6} corpus: ~{proj_n_capped/1e6:.2f}M trigrams, ~{proj_mb:.0f} MB Nov.cnt "
          f"(hard ceiling 256^3 = {cap/1e6:.1f}M -> ~{(sys.getsizeof(nov.cnt)+cap*92)/1e6:.0f} MB max)")
print(f"\nprocess RSS now: {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1e3:.0f} MB")
