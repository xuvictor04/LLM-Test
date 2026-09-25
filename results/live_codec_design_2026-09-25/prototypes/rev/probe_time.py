"""Time one probe reading of D1's 25 Hz spec codec on one CPU thread: encode, Griffin-Lim 32 decode,
and the analytic inverse (D1's `probe`, the prototypes' name for DATA.recover), per clip.

Usage (from results/live_codec_design_2026-09-25/prototypes/):
    python3 rev/probe_time.py d1 d1/ck/codec25.pt 3 | tee rev/probe_time.txt

The codec checkpoint is not committed (README: "Model checkpoints are not committed"); D1's codec
phase (d1/codec.py, 4000 steps, recorded in d1/ck/codec25.pt.json) re-creates it. The timing is
machine-dependent; the output records the machine and the torch version beside the numbers.
"""
import os
import platform
import sys
import time

os.environ["OMP_NUM_THREADS"] = "1"
import torch  # noqa: E402

torch.set_num_threads(1)

D1 = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "d1")
CK = sys.argv[2] if len(sys.argv) > 2 else os.path.join(D1, "ck", "codec25.pt")
REPS = int(sys.argv[3]) if len(sys.argv) > 3 else 3
sys.path.insert(0, D1)
import synth as S  # noqa: E402
import melody as M  # noqa: E402
import codec as K  # noqa: E402

cpu = "unknown"
try:
    with open("/proc/cpuinfo") as fh:
        cpu = next((ln.split(":", 1)[1].strip() for ln in fh if ln.startswith("model name")), cpu)
except OSError:
    pass
print(f"# command: python3 {' '.join(sys.argv)}")
print(f"# machine: {cpu}; {platform.system()} {platform.release()}; torch {torch.__version__}; threads 1")

ck = torch.load(CK)
m = K.make_codec(ck["stride"])
m.load_state_dict(ck["model"])
m.eval()
totals = []
for rep in range(REPS):
    for area, mod, seed in (("A", S, 555), ("B", M, 556)):
        ge = torch.Generator().manual_seed(seed)
        ps, xs = [], []
        for p in mod.all_combos()[:60]:
            ps.append(p)
            xs.append(mod.render(p, ge))
        X = torch.stack(xs)
        n = len(ps)
        with torch.no_grad():
            t0 = time.time()
            codes, _ = K.encode(m, X)
            t1 = time.time()
            Y = K.decode_codes(m, codes)
            t2 = time.time()
            sum(mod.attr_acc(mod.probe(Y[i]), ps[i])["exact"] for i in range(n))
            t3 = time.time()
        tot = (t3 - t0) / n * 1000
        totals.append(tot)
        print(f"rep {rep} area {area} clips {n}: encode {(t1 - t0) / n * 1000:.1f} ms/clip, "
              f"decode (Griffin-Lim 32) {(t2 - t1) / n * 1000:.1f} ms/clip, "
              f"inverse {(t3 - t2) / n * 1000:.1f} ms/clip, total {tot:.1f} ms/clip")
lo, hi, mean = min(totals), max(totals), sum(totals) / len(totals)
print(f"# per clip: min {lo:.1f} ms, max {hi:.1f} ms, mean {mean:.1f} ms")
print(f"# one 400-clip reading: {400 * lo / 1000:.1f}-{400 * hi / 1000:.1f} s")
print(f"# readiness under 'measured' (3 candidates x 1 area x 6 readings): "
      f"{18 * 400 * lo / 60000:.1f}-{18 * 400 * hi / 60000:.1f} min")
