"""Model-free replay (CPU, operation only) of TOK through a parent's whole epoch at TOK_RETOK_EVERY 1000, then a
pure-add session onto a fifth synthetic area x5 (epoch 1, DATA_RESAMPLE=1, 4,725,000 bytes over 5 processes) for
<nsess> windows with acts every 1000, as spine/loop.py orders them (on_window per window; the mint at the flush; the
act after it). It answers two questions register §8 5.3a's pre-registration rests on: do the four old held-out blocks
stay byte for byte the parent's when x5 is appended at this stream length, and how much of each old area's held-out
block does the session's last-cut view segment with tokens the session minted (text a pure-add session never trains
in context)?

    python3 sessreplay.py <seed> <TOK_MINT_NOVEL> [<session windows>]       # sessreplay.out: 0 and 1, 0 and 1.0, 5000

Run it in place, by its path, from any directory but the checkout's root (it finds src/ two folders up). Adapted from
the judge's scratch replay of 2026-10-02 (merge/sessreplay.py), which read the same numbers at seed 0."""
import collections
import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or ".") != ROOT]
sys.path.insert(0, os.path.join(ROOT, "src"))
from spine.assemble import build as _build                         # noqa: E402
from spine.compose import RNG_SUBSYSTEMS                           # noqa: E402
from spine import units as U                                       # noqa: E402
from spine import lever as _lever                                  # noqa: E402
from spine import rng as _rng                                      # noqa: E402
from data import api as data_api                                   # noqa: E402
from tok import api as tok_api                                     # noqa: E402
from train import api as run_api                                   # noqa: E402

seed, novel = int(sys.argv[1]), sys.argv[2]
nsess = int(sys.argv[3]) if len(sys.argv) > 3 else 5000
base = dict(os.environ)
base.update(RUN_SEED=str(seed), RUN_DEVICE="cpu", OMP_NUM_THREADS="1", DATA_DIR=os.path.join(ROOT, "data"),
            TOK_RETOK_EVERY="1000", TOK_MINT_NOVEL=novel)
ALPHA = {"eng": set(b"abcdefghijklmno"), "py": set(b"pqrstuvwxyzABCD"), "num": set(b"EFGHIJKLMNOPQRS"),
         "c": set(b"TUVWXYZ0123456"), "x5": set(b"789!?.,;:'\"-()")}


def area_of(bs):
    hit = [a for a, s in ALPHA.items() if all(x in s for x in bs)]
    return hit[0] if len(hit) == 1 else "cross"


def setup(env):
    configs, _, _ = _build(environ=env)
    run, lm, data, tok = configs["RUN"], configs["LM"], configs["DATA"], configs["TOK"]
    run_api.process_setup(run)
    run_api.streams(run, RNG_SUBSYSTEMS)
    return run, lm, data, tok


def walk(tok, vocab, seg, stream, ctx, step0, limit, mints, tag):
    last = tok_api.view_of(vocab)
    i = 0
    while i < limit:
        a = i * ctx
        b = a + ctx + 1
        if b > len(seg.ids):
            break
        step = U.Windows(step0 + i + 1)
        due = tok_api.on_window(tok, vocab, seg.ids[a:b], step=step)
        if due.mint:
            for m in tok_api.mint_burst(tok, vocab, step=step):
                mints.append((tag, area_of(m.token_bytes), int(m.new_id)))
        if due.retok:
            v = tok_api.view_of(vocab)
            if v != last:
                seg = tok_api.splice(tok, vocab, seg, stream.bytes, stream.labels, at=(i + 1) * ctx, regularize=True)
                last = v
        i += 1
    return seg, i, last


t0 = time.time()
# THE PARENT: the four shipped areas, one whole epoch of 3,780,000 bytes (test 4's shape).
run, lm, data, tok = setup(dict(base, DATA_STREAM_BYTES="3780000"))
areas = data_api.open_areas(data, seed=seed)
vocab = tok_api.build_vocabulary(tok, area_heads=areas.bodies, seed=seed, soft_cap=None)
plan = data_api.data_plan(data, areas, epochs=1, win_tokens=int(lm.ctx), bytes_per_token=float(vocab.bytes_per_token))
stream = data_api.draw_stream(data, areas, plan, epoch=0, seed=seed)
seg = tok_api.tokenize(tok, vocab, stream.bytes, stream.labels, regularize=True, seed=seed)
mints = []
seg, n0, pview = walk(tok, vocab, seg, stream, int(lm.ctx), 0, 10 ** 9, mints, "parent")
# THE SESSION: x5 appended at 4,725,000 bytes over 5 processes (945,000 a process, the parent's), pure-add, epoch 1
# redrawn, cut at the parent's vocabulary. A second assembly in one process: the session's levers.
_lever._reopen_assembly()
_rng.reset_issued()
run2, lm2, data2, tok2 = setup(dict(base, DATA_STREAM_BYTES="4725000", DATA_N_PROCESSES="5",
                                    DATA_AREAS="eng,py,num,c,x5", DATA_PHASE_SCHED="x5|x5|x5|x5",
                                    DATA_RESAMPLE="1", RUN_EPOCHS="2"))
areas2 = data_api.open_areas(data2, seed=seed)
same = {a: areas2.holdout[a] == areas.holdout[a] for a in ("eng", "py", "num", "c")}
x5_alpha = set(areas2.holdout["x5"]) <= ALPHA["x5"]
plan2 = data_api.data_plan(data2, areas2, epochs=2, win_tokens=int(lm2.ctx),
                           bytes_per_token=float(vocab.bytes_per_token))
stream2 = data_api.draw_stream(data2, areas2, plan2, epoch=1, seed=seed)
seg2 = tok_api.tokenize(tok2, vocab, stream2.bytes, stream2.labels, regularize=True, seed=seed)
seg2, n1, sview = walk(tok2, vocab, seg2, stream2, int(lm2.ctx), n0, nsess, mints, "session")
sm = collections.Counter(ar for tag, ar, _ in mints if tag == "session")
print(f"seed {seed} TOK_MINT_NOVEL={novel}: parent {n0} windows; session {n1} windows; the four old held-out blocks "
      f"byte for byte the parent's with x5 appended: {all(same.values())} "
      f"({', '.join(f'{a} {len(areas.holdout[a])} B' for a in same)}); x5's block in alphabet 4 alone: {x5_alpha}; "
      f"the session's mints by area {dict(sm)} ({time.time() - t0:.0f}s)")
sess_ids = {mid for tag, _, mid in mints if tag == "session"}
for ar in ("eng", "py", "num", "c"):
    blk = areas.holdout[ar]
    sp = tok_api.tokenize(tok, vocab, blk, view=pview)
    ss = tok_api.tokenize(tok, vocab, blk, view=sview)
    ids, bp = list(ss.ids), list(ss.byte_pos) + [len(blk)]
    moved = sum(bp[k + 1] - bp[k] for k, t in enumerate(ids) if t in sess_ids)
    print(f"  {ar:3s}: held-out tokens at the parent's view {len(sp.ids)}, at the session's last-cut view {len(ids)}; "
          f"bytes in session-minted tokens {100 * moved / len(blk):.1f}%")
