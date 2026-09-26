# Model-free simulation of TOK's online minting + the mid-epoch act over the fleet-shaped stream, to find
# how many bytes a HEAD default run (TOK_RETOK_EVERY=3000) has read by window N. Minting is a pair tally over
# the window ids (TOK.on_window) plus TOK.mint_burst -- neither reads the model -- and probation is off at
# TOK_PROBATION_USES=0, so the segmentation a real run trains on is reproduced without training.
import sys, os, time
sys.path.insert(0, "/home/user/LLM-Test/src")
seed, every, N = sys.argv[1], sys.argv[2], int(sys.argv[3])
env = dict(os.environ); env.update({"DATA_STREAM_BYTES": "20000000", "RUN_SEED": seed, "RUN_DEVICE": "cpu",
                                    "TOK_RETOK_EVERY": every})
from spine import compose as C, units as U
from tok import api as T
t0 = time.time()
s = C.compose(env)
tok = s.configs["TOK"]; vocab = s.vocab; seg = s.segmentation; ctx = int(s.configs["LM"].ctx)
print(f"seed={seed} retok_every={every} probation_uses={tok.probation_uses} grow_every={tok.grow_every} burst={tok.grow_burst} "
      f"start vocab={vocab.size()} ids={len(seg.ids)} compose {time.time()-t0:.0f}s", flush=True)
marks = {}
for w in range(N):
    step = w + 1
    due = T.on_window(tok, vocab, seg.ids[w*ctx:(w+1)*ctx], step=U.Windows(step))
    if due.mint:
        T.mint_burst(tok, vocab, step=U.Windows(step))
    if due.retok:
        before = len(seg.ids); k0 = step * ctx
        seg = T.splice(tok, vocab, seg, s.stream.bytes, s.stream.labels, at=k0, regularize=True)
        tail_b = seg.byte_pos[len(seg.ids)-1] - seg.byte_pos[k0]
        print(f"  act at window {step}: vocab {vocab.size()} ids {before} -> {len(seg.ids)}; "
              f"tail bytes/window {(seg.byte_pos[min(k0+3000*ctx, len(seg.ids)-1)] - seg.byte_pos[k0]) / 3000:.1f} (next 3000 windows) "
              f"t={time.time()-t0:.0f}s", flush=True)
    if step in (1300, 3000, 5000, 10000, 15000, 20000, N):
        marks[step] = seg.byte_pos[step*ctx]
for k in sorted(marks):
    print(f"  bytes read by window {k}: {marks[k]} ({marks[k]/1e6:.3f} MB, {marks[k]/k:.1f} bytes/window)")
print(f"  scored bytes windows [0,1300): {seg.byte_pos[1300*ctx+1] - seg.byte_pos[1]}")
print(f"  final vocab {vocab.size()}; phase-1 bound 5,000,000 {'CROSSED' if marks.get(N, 0) >= 5_000_000 else 'not crossed'} by window {N}; t={time.time()-t0:.0f}s")
import bisect, collections
bp = list(seg.byte_pos)
kx = bisect.bisect_left(bp, 5_000_000)
print(f"  phase-1 bound 5,000,000 reached at window {kx // ctx}; windows in phase 2 by window {N}: {N - kx // ctx}")
end = bp[N*ctx]
print("  areas read in bytes [5e6, end):", dict(collections.Counter(s.stream.labels[5_000_000:end])), "; areas in [0,5e6):", dict(collections.Counter(s.stream.labels[:5_000_000])))
print("  plan schedule", s.plan.schedule, "names", s.areas.names)
