import sys, os
sys.path.insert(0, "/home/user/LLM-Test/src")
env = dict(os.environ); env.update({"DATA_STREAM_BYTES": "20000000", "RUN_SEED": "0", "RUN_DEVICE": "cpu"})
from spine import compose as C
s = C.compose(env); bp = s.segmentation.byte_pos; ctx = 128
sc = lambda a, b: bp[b*ctx+1] - bp[a*ctx+1]   # target bytes of windows a..b-1 (contiguous windows)
a = sc(0, 1001); b = sc(1001, 1300)
print("k0 scored [0,1001)", a, "[1001,1300)", b, "per window", round(b/299, 2))
k1000_total = 251653  # verify/emp/k1000_1300.log loop.bytes_scored
tail = k1000_total - a
print("k1000 [1001,1300) =", tail, "per window", round(tail/299, 2), "ratio vs k0", round(tail / b, 4))
print("pre-act bytes/window", round(a/1001, 2), "k0 whole 20k", round(sc(0, 20000)/20000, 2))
