# Independent model-free replay of TOK's per-window tally, mint bursts and mid-epoch acts (spine/loop.py:1110,
# :1220, :2355) over the 20 MB default stream at HEAD, to measure bytes consumed by window 20000.
# usage: python acts.py <seed> <retok_every> <N>
import sys, os, bisect, collections
sys.path.insert(0, "/home/user/LLM-Test/src")
seed, every, N = sys.argv[1], sys.argv[2], int(sys.argv[3])
env = dict(os.environ)
env.update({"DATA_STREAM_BYTES": "20000000", "RUN_SEED": seed, "RUN_DEVICE": "cpu", "TOK_RETOK_EVERY": every})
from spine import compose as C, units as U
from tok import api as T
s = C.compose(env)
tok, vocab, seg = s.configs["TOK"], s.vocab, s.segmentation
ctx = int(s.configs["LM"].ctx)
acts = []
for w in range(N):
    step = w + 1
    due = T.on_window(tok, vocab, seg.ids[w * ctx:(w + 1) * ctx], step=U.Windows(step))
    if due.mint:
        T.mint_burst(tok, vocab, step=U.Windows(step))
    if due.retok:
        k0 = step * ctx
        seg = T.splice(tok, vocab, seg, s.stream.bytes, s.stream.labels, at=k0, regularize=True)
        acts.append((step, vocab.size(), len(seg.ids)))
bp = seg.byte_pos
end = bp[N * ctx]
print(f"seed {seed} every {every} ctx {ctx}: acts {acts}")
print(f"  bytes by window {N}: {end} = {end/1e6:.3f} MB ({end/N:.1f} B/window avg); final vocab {vocab.size()}")
b1 = s.plan.phase_bounds[0][1]
k = bisect.bisect_left(bp, b1)
print(f"  phase-1 bound {b1} crossed at token {k} = window {k // ctx}; windows past it by {N}: {max(0, N - k // ctx)}")
print("  labels of bytes read after the phase-1 bound:", dict(collections.Counter(s.stream.labels[b1:end])))
