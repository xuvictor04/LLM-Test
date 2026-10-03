"""Model-free replay of TOK's trajectory on the REAL whole-epoch stream (CPU, operation only), as
results/heldout_prereg_2026-10-02/tokreplay.py replays the synthetic one: mint bursts every TOK_GROW_EVERY windows
and the act's splice every TOK_RETOK_EVERY windows, in spine/loop.py's order. It reports each phase's windows (§8 0.4)
and, per area, how much of its held-out block the last-cut view segments with tokens minted while that area was not
live -- before it arrived or after it faded. Real areas share one alphabet, so such a token was formed from another
area's text (or, after a fade, from the area's own stale tally): the cross-area re-segmentation synthetic text, whose
alphabets are disjoint, cannot show (src/data/api.py:856).

    python3 realreplay.py <seed> <TOK_RETOK_EVERY> <TOK_MINT_NOVEL> [<DATA_DRAW>]   # the fleet's shape, 3,780,000 B
    python3 realreplay.py <seed> 40 0 <DATA_DRAW> 64800 20 <out.json>   # cpu/'s toy shape: DATA_STREAM_BYTES,
                                                                         # TOK_GROW_EVERY; the acts and windows to a
                                                                         # file for cpu/checks.py

Run it in place, by its path, from any directory but the checkout's root (it finds src/ two folders up)."""
import bisect
import collections
import json
import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or ".") != ROOT]
sys.path.insert(0, os.path.join(ROOT, "src"))
from spine.assemble import build as _build                         # noqa: E402
from spine import units as U                                        # noqa: E402
from data import api as data_api                                   # noqa: E402
from tok import api as tok_api                                     # noqa: E402

seed, retok, novel = int(sys.argv[1]), sys.argv[2], sys.argv[3]
draw = sys.argv[4] if len(sys.argv) > 4 else "planned"
nbytes, grow, jout = (sys.argv[5:8] + [None, None, None])[:3]
env = dict(os.environ, RUN_SEED=str(seed), DATA_STREAM_BYTES=nbytes or "3780000", RUN_DEVICE="cpu", OMP_NUM_THREADS="1",
           DATA_DIR=os.path.join(ROOT, "data"), DATA_SOURCE="real", DATA_DRAW=draw, TOK_RETOK_EVERY=retok,
           TOK_MINT_NOVEL=novel)
if draw == "replay":
    env["DATA_REPLAY_SHARE"] = "0.27"
if grow:
    env["TOK_GROW_EVERY"] = grow
t0 = time.time()
configs, _, _ = _build(environ=env)
run, lm, data, tok = configs["RUN"], configs["LM"], configs["DATA"], configs["TOK"]
areas = data_api.open_areas(data, seed=int(run.seed))
vocab = tok_api.build_vocabulary(tok, area_heads=areas.bodies, seed=int(run.seed), soft_cap=None)
plan = data_api.data_plan(data, areas, epochs=int(run.epochs), win_tokens=int(lm.ctx),
                          bytes_per_token=float(vocab.bytes_per_token))
stream = data_api.draw_stream(data, areas, plan, epoch=0, seed=int(run.seed))
seg = tok_api.tokenize(tok, vocab, stream.bytes, stream.labels, regularize=True, seed=int(run.seed))
ctx, build_size = int(lm.ctx), vocab.size()
build_view = tok_api.view_of(vocab)
bounds = [b for (a, b) in plan.phase_bounds]
names = list(areas.names)
live = [{names[i] for i in ph} for ph in plan.schedule]          # the areas each phase makes live


def phase_of(byte):
    return min(len(bounds) - 1, bisect.bisect_right(bounds, byte))


born = {}                     # minted id -> the phase of the window it was minted at
wph = collections.Counter()   # windows per phase, by each window's first byte (the probe's phase starts)
acts, last_view, i = [], tok_api.view_of(vocab), 0
while True:
    ids = seg.ids
    a, b = i * ctx, i * ctx + ctx + 1
    if b > len(ids):
        break
    step = U.Windows(i + 1)
    due = tok_api.on_window(tok, vocab, ids[a:b], step=step)
    ph = phase_of(seg.byte_pos[a])
    wph[ph] += 1
    if due.mint:
        for m in tok_api.mint_burst(tok, vocab, step=step):
            born[int(m.new_id)] = ph
    if due.retok:
        v = tok_api.view_of(vocab)
        if v != last_view:
            seg = tok_api.splice(tok, vocab, seg, stream.bytes, stream.labels, at=(i + 1) * ctx, regularize=True)
            last_view = v
            acts.append(i + 1)
    i += 1
np_ = len(bounds)
print(f"seed {seed} TOK_RETOK_EVERY={retok} TOK_MINT_NOVEL={novel} DATA_DRAW={draw}: windows {i:,}, acts {len(acts)}, "
      f"build vocab {build_size}, final vocab {vocab.size()}, mints {len(born)} ({time.time() - t0:.0f}s)")
print(f"  windows per phase: {' '.join(f'p{k + 1} {wph[k]:,}' for k in range(np_))}; the shortest / 5 = "
      f"{min(wph[k] for k in range(np_)) / 5:.0f} (§8 0.4: the cap EVAL_RETENTION_EVERY may not pass)")
print("  mints born per phase: " + " ".join(f"p{k + 1} {sum(1 for p in born.values() if p == k)}" for k in range(np_)))
if jout:
    with open(jout, "w") as fh:
        json.dump({"acts": acts, "windows": i, "wph": [wph[k] for k in range(np_)]}, fh)
for ar in names:
    blk = areas.holdout[ar]
    first = min(k for k in range(np_) if ar in live[k])
    last = max(k for k in range(np_) if ar in live[k])
    s0 = tok_api.tokenize(tok, vocab, blk, view=build_view)
    s = tok_api.tokenize(tok, vocab, blk, view=last_view)
    tid, bp = list(s.ids), list(s.byte_pos) + [len(blk)]
    cnt = collections.Counter()
    for k, t in enumerate(tid):
        if t in born:
            p = born[t]
            cnt["before" if p < first else "after" if p > last else "live"] += bp[k + 1] - bp[k]
    pct = {k: 100 * v / len(blk) for k, v in cnt.items()}
    print(f"  {ar:<3} held-out {len(blk):,} B (live p{first + 1}-p{last + 1}): {len(blk) / max(1, len(s0.ids)):.2f} B/token "
          f"at the build vocabulary, {len(blk) / max(1, len(tid)):.2f} at the last-cut view; bytes in tokens minted "
          f"while it was live {pct.get('live', 0.0):.1f}%, before it arrived {pct.get('before', 0.0):.1f}%, after it "
          f"faded {pct.get('after', 0.0):.1f}%")
