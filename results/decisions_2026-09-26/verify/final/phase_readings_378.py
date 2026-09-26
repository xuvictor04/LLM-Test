# Model-free replay (same calls as verify/emp3/acts.py) of a k3000 run over the whole-epoch 3.78 MB stream at HEAD:
# the window at which each phase bound is crossed, and how many EVAL_RETENTION_EVERY=1000 readings (first at 1001,
# 04:584-585) fall in each phase, plus one phase-start reading. usage: python phase_readings_378.py <seed> <every>
import sys, os, bisect
sys.path.insert(0, "/home/user/LLM-Test/src")
seed, every = sys.argv[1], sys.argv[2]
env = dict(os.environ)
env.update({"DATA_STREAM_BYTES": "3780000", "RUN_SEED": seed, "RUN_DEVICE": "cpu", "TOK_RETOK_EVERY": every})
from spine import compose as C, units as U
from tok import api as T
s = C.compose(env)
tok, vocab, seg = s.configs["TOK"], s.vocab, s.segmentation
ctx = int(s.configs["LM"].ctx)
w = 0
while (w + 1) * ctx <= len(seg.ids):
    step = w + 1
    due = T.on_window(tok, vocab, seg.ids[w * ctx:(w + 1) * ctx], step=U.Windows(step))
    if due.mint:
        T.mint_burst(tok, vocab, step=U.Windows(step))
    if due.retok:
        seg = T.splice(tok, vocab, seg, s.stream.bytes, s.stream.labels, at=step * ctx, regularize=True)
    w += 1
N = w
bp = seg.byte_pos
bounds = [b for b in s.plan.phase_bounds]
print(f"seed {seed} every {every}: epoch consumed in {N} windows; phase bounds {bounds}")
starts = []
for (lo, hi) in bounds:
    wlo = bisect.bisect_left(bp, lo) // ctx; whi = min(N, bisect.bisect_left(bp, hi) // ctx)
    reads = [r for r in range(1001, N + 1, 1000) if wlo <= r < whi]
    print(f"  phase bytes [{lo},{hi}): windows [{wlo},{whi}) = {whi-wlo}; readings at 1000: {len(reads)}; with a phase-start reading: {len(reads)+1}")
