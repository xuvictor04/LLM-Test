# Compose at the fleet's shape (DATA_STREAM_BYTES = WINDOWS*1000 = 20e6) and locate window 20000 in the stream.
import sys, os, bisect, hashlib, collections, time
SRC = sys.argv[1]; seed = sys.argv[2]
sys.path.insert(0, SRC)
env = dict(os.environ); env.update({"DATA_STREAM_BYTES": "20000000", "RUN_SEED": seed, "RUN_DEVICE": "cpu"})
from spine import compose as C
t = time.time()
s = C.compose(env)
seg = s.segmentation; ctx = int(s.configs["LM"].ctx); bp = list(seg.byte_pos)
n_win = (len(seg.ids) - 1) // ctx
d = s.configs["DATA"]
print(f"src={SRC.split('/')[-2]} seed={seed} ctx={ctx} phases={d.phases} phase_live={d.phase_live} phase_sched={d.phase_sched!r} draw={d.draw}")
print(" schedule", s.plan.schedule, "names", s.areas.names, "bounds", s.plan.phase_bounds)
print(f" stream={len(s.stream.bytes)} tokens={len(seg.ids)} windows/epoch={n_win} bytes/window={len(s.stream.bytes)/n_win:.1f} bpt={s.vocab.bytes_per_token:.4f}")
p20 = bp[20000*ctx]
print(f" byte at window 20000 = {p20} ({p20/1e6:.3f} MB); bytes/window over first 20000 = {p20/20000:.1f}")
for lo, _ in s.plan.phase_bounds[1:]:
    k = bisect.bisect_left(bp, lo)
    print(f"  phase bound {lo} first reached at window {k//ctx}")
lab = s.stream.labels[:p20]
print(" areas in first 20000 windows (bytes):", dict(collections.Counter(lab)))
print(f" bytes/window needed to reach 5e6 by window 20000: {5e6/20000:.0f}; t={time.time()-t:.0f}s")
