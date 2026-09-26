# Independent check (round 3 empirical checker).
# usage: python seeds_bytes.py <src_dir> <seed> <stream_bytes> [retok_every|-]
# Composes the system exactly as run.py does (spine.compose with the environment), then reports:
#   - sha of the epoch-0 stream and of each area body (does RUN_SEED change the text?)
#   - the plan: schedule, phase bounds, protocol, area names
#   - the compose-time (frozen) segmentation: bytes consumed by windows 20000 / 10000 at LM_CTX
#   - which areas the bytes read by window 20000 come from
import sys, os, hashlib, time, collections, bisect
SRC, seed, nb = sys.argv[1], sys.argv[2], sys.argv[3]
retok = sys.argv[4] if len(sys.argv) > 4 else "-"
sys.path.insert(0, SRC)
env = dict(os.environ)
env.update({"DATA_STREAM_BYTES": nb, "RUN_SEED": seed, "RUN_DEVICE": "cpu"})
if retok != "-":
    env["TOK_RETOK_EVERY"] = retok
from spine import compose as C
t = time.time()
s = C.compose(env)
h = lambda b: hashlib.sha256(bytes(b)).hexdigest()[:16]
dat = s.configs["DATA"]
ctx = int(s.configs["LM"].ctx)
print(f"tree={SRC} seed={seed} run.seed={s.configs['RUN'].seed} source={dat.source} areas={s.areas.names} "
      f"stream_bytes={int(dat.stream_bytes)} ctx={ctx} t_compose={time.time()-t:.1f}s")
print("  stream sha", h(s.stream.bytes), "len", len(s.stream.bytes))
print("  bodies", {n: h(s.areas.bodies[n]) for n in s.areas.names})
print("  plan protocol", s.plan.protocol, "schedule", s.plan.schedule, "bounds", s.plan.phase_bounds)
print("  vocab", s.vocab.size(), "bpt(measured)", round(float(s.vocab.bytes_per_token), 4))
seg = s.segmentation
bp = seg.byte_pos
nwin = (len(seg.ids) - 1) // ctx
print("  windows in epoch (frozen seg)", nwin)
for W in (1000, 10000, 20000):
    if W * ctx < len(bp):
        print(f"  bytes read by window {W}: {bp[W*ctx]} ({bp[W*ctx]/W:.2f} B/window)")
if 20000 * ctx < len(bp):
    end = bp[20000 * ctx]
    lab = collections.Counter(s.stream.labels[:end])
    print("  area bytes read by window 20000:", dict(lab))
    kx = bisect.bisect_left(bp, s.plan.phase_bounds[0][1])
    print("  phase-1 upper bound reached at window", kx // ctx)
