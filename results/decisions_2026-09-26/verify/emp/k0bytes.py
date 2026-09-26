import sys, os
sys.path.insert(0, "/home/user/LLM-Test/src")
os.environ.update({"DATA_STREAM_BYTES": "20000000", "RUN_SEED": "0", "RUN_DEVICE": "cpu"})
from spine import compose as C
sysm = C.compose(dict(os.environ))
bp = sysm.segmentation.byte_pos; ctx = 128
def scored(a, b):  # windows a..b-1, bytes of targets (as loop: bp[end] - bp[start+1])
    return sum(bp[i*ctx+ctx+1] - bp[i*ctx+1] for i in range(a, b))
print("k0 [0,1001):", scored(0,1001)); print("k0 [1001,1300):", scored(1001,1300))
print("k0 scored bytes windows [0,1000):", scored(0,1000))
print("k0 scored bytes windows [1000,1300):", scored(1000,1300))
print("k0 scored bytes windows [0,1300):", scored(0,1300))
