"""Model-free replay of TOK's trajectory on the synthetic whole-epoch stream (CPU, operation only):
mint bursts every TOK_GROW_EVERY windows and the act's splice every TOK_RETOK_EVERY windows, as
spine/loop.py orders them (on_window per window; mint at the flush; the act after it). Reports where
mints go (by alphabet = area, by phase) and how much of each area's held-out block the last-cut view
segments with tokens minted after a given phase began."""
import os, sys, time, bisect, collections
SRC = "/home/user/LLM-Test/src"
sys.path[:] = [p for p in sys.path if os.path.abspath(p or ".") != "/home/user/LLM-Test"]
sys.path.insert(0, SRC)
from spine.assemble import build as _build
from spine.compose import RNG_SUBSYSTEMS
from spine import units as U
from data import api as data_api
from tok import api as tok_api
from train import api as run_api
seed, retok, novel = int(sys.argv[1]), sys.argv[2], sys.argv[3]
env = {k: v for k, v in os.environ.items()}
env.update(RUN_SEED=str(seed), DATA_STREAM_BYTES="3780000", RUN_DEVICE="cpu", OMP_NUM_THREADS="1",
           DATA_DIR="/home/user/LLM-Test/data", TOK_RETOK_EVERY=retok, TOK_MINT_NOVEL=novel)
t0 = time.time()
configs, wires, warnings = _build(environ=env)
run, lm, data, tok = configs["RUN"], configs["LM"], configs["DATA"], configs["TOK"]
proc = run_api.process_setup(run)
streams = run_api.streams(run, RNG_SUBSYSTEMS)
areas = data_api.open_areas(data, seed=int(run.seed))
vocab = tok_api.build_vocabulary(tok, area_heads=areas.bodies, seed=int(run.seed), soft_cap=None)
plan = data_api.data_plan(data, areas, epochs=int(run.epochs), win_tokens=int(lm.ctx),
                          bytes_per_token=float(vocab.bytes_per_token))
stream = data_api.draw_stream(data, areas, plan, epoch=0, seed=int(run.seed))
seg = tok_api.tokenize(tok, vocab, stream.bytes, stream.labels, regularize=True, seed=int(run.seed))
ctx = int(lm.ctx)
build_size = vocab.size()
bounds = [b for (a, b) in plan.phase_bounds]
def phase_of(byte):
    return bisect.bisect_right(bounds, byte)
ALPHA = {"eng": set(b"abcdefghijklmno"), "py": set(b"pqrstuvwxyzABCD"), "num": set(b"EFGHIJKLMNOPQRS"),
         "c": set(b"TUVWXYZ0123456")}
def area_of(bs):
    hit = [a for a, s in ALPHA.items() if all(x in s for x in bs)]
    return hit[0] if len(hit) == 1 else "cross"
mints = []          # (window, phase, area, id)
acts = []           # (window, view_size)
last_view = tok_api.view_of(vocab)
i = 0
while True:
    ids = seg.ids
    a = i * ctx; b = a + ctx + 1
    if b > len(ids):
        break
    step = U.Windows(i + 1)
    due = tok_api.on_window(tok, vocab, ids[a:b], step=step)
    ph = phase_of(seg.byte_pos[a])
    if due.mint:
        for m in tok_api.mint_burst(tok, vocab, step=step):
            mints.append((i + 1, ph, area_of(m.token_bytes), int(m.new_id)))
    if due.retok:
        v = tok_api.view_of(vocab)
        if v != last_view:
            seg = tok_api.splice(tok, vocab, seg, stream.bytes, stream.labels, at=(i + 1) * ctx, regularize=True)
            last_view = v
            acts.append((i + 1, v[0]))
    i += 1
print(f"seed {seed} TOK_RETOK_EVERY={retok} TOK_MINT_NOVEL={novel}: windows {i}, build vocab {build_size}, "
      f"final vocab {vocab.size()}, mints {len(mints)}, acts {len(acts)} ({time.time()-t0:.0f}s)")
tab = collections.Counter((ph, ar) for _, ph, ar, _ in mints)
for ph in range(4):
    row = {ar: tab.get((ph, ar), 0) for ar in ("eng", "py", "num", "c", "cross")}
    print(f"  mints born in p{ph+1}: {row}")
# the last-cut view: what the probe at R tokenizes held-out text with
view = last_view
birth = {mid: (w, ph) for w, ph, ar, mid in mints}
late_from = {"eng": 1, "py": 3, "num": 3, "c": 99}   # phase index from which a mint is 'after the area faded' (eng after p1; py in p4) or late (num in p4)
for ar in ("eng", "py", "num", "c"):
    blk = areas.holdout[ar]
    s = tok_api.tokenize(tok, vocab, blk, view=view)
    ids, bp = list(s.ids), list(s.byte_pos) + [len(blk)]
    late_b = minted_b = 0
    for k, t in enumerate(ids):
        nb = bp[k + 1] - bp[k]
        if t in birth:
            minted_b += nb
            if birth[t][1] >= late_from[ar]:
                late_b += nb
    print(f"  {ar:3s} held-out block {len(blk)} B at the last-cut view: {len(blk)/max(1,len(ids)):.2f} B/token; "
          f"bytes in online-minted tokens {100*minted_b/len(blk):.1f}%; in tokens minted after "
          f"{'p'+str(late_from[ar]) if ar!='c' else '-'} {100*late_b/len(blk):.1f}%")
