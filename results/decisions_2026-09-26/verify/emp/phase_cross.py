import sys, os, bisect, hashlib
SRC = sys.argv[1]; seed = sys.argv[2]
sys.path.insert(0, SRC)
os.environ.update({"DATA_STREAM_BYTES": "20000000", "RUN_SEED": seed, "RUN_DEVICE": "cpu", "OMP_NUM_THREADS": "1"})
from spine import compose as C
sysm = C.compose(dict(os.environ))
seg = sysm.segmentation
ctx = int(sysm.configs["LM"].ctx)
bp = seg.byte_pos
n_win = (len(seg.ids) - 1) // ctx
print("src", SRC, "seed", seed, "ctx", ctx, "stream bytes", len(sysm.stream.bytes), "tokens", len(seg.ids), "windows_in_epoch", n_win,
      "bytes/token", round(len(sysm.stream.bytes)/len(seg.ids), 4), "bytes/window(avg)", round(len(sysm.stream.bytes)/n_win, 1))
print("phase_bounds", sysm.plan.phase_bounds, "schedule", sysm.plan.schedule, "names", sysm.areas.names)
# window index at which the stream position crosses each phase bound
for lo, hi in sysm.plan.phase_bounds[1:]:
    tok = bisect.bisect_left(list(bp[:len(seg.ids)]), lo) if not hasattr(bp, 'tolist') else bisect.bisect_left(bp.tolist(), lo)
    print(f"  bound {lo}: reached at token {tok}, window {tok // ctx}")
w20k_tok = 20000 * ctx
print("byte position at window 20000:", bp[w20k_tok] if w20k_tok < len(bp) else None)
print("bytes in first 300 windows:", bp[300*ctx+1] - bp[1])
# which areas are in the first 20000 windows
end = bp[w20k_tok]
labs = sysm.stream.labels[:end]
from collections import Counter
cnt = Counter(labs if isinstance(labs, (bytes, bytearray, list)) else list(labs))
print("area label counts over the first 20000 windows:", dict(cnt))
print("stream hash", hashlib.sha256(bytes(sysm.stream.bytes)).hexdigest()[:12])
