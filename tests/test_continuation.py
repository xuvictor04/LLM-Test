"""THE MID-EPOCH ACT AND THE CONTINUING RESUME (03b stage S0b), driven through the real composition root
and loop with real on-disk checkpoints written under a temporary directory.

    python3 tests/test_continuation.py        # exit 0 = every check passed

WHY IT EXISTS. Until 03b S0b a retok request waited for an epoch roll -- at RUN_EPOCHS=1 it never
came, so no id the run minted ever reached its own training data -- and a mid-epoch resume replayed
its epoch from window 0, because the child could not cut the stream where the parent had. The act
re-segments the unconsumed tail mid-epoch; the per-epoch segmentation log lets a resume rebuild the
parent's exact stream and continue. Each check below pins one promise of that pair.

  S1  RunClock.revise_epoch_length keeps the cursor, refuses a length below it, and at n == in_epoch
      rolls on the next advance WITHOUT counting a window.
  S2  OPT.revise_horizon is LR-continuous (lr(now) unchanged), ends at the floor at the revised end,
      and leaves the warmup untouched.
  S3  TOK.splice keeps every unit up to and including the one under the cursor; tokenize(view=) at a
      recorded view rebuilds the segmentation cut then, after later mints and a retirement.
  S4  the act fires after a mint and changes the stream; TOK_RETOK_EVERY=0 arms no act.
  S6  MEM's stored contexts are re-cut at the act's view (MEM.maintain(remap=), Q-MEM-13): a re-cut
      context decodes to the same bytes it held, spelled in the newer tokens, and an act in a run
      remaps the store.
  S5  THE CONTINUATION IS BIT-EXACT: a run saved at window n1 and resumed for n2 windows produces the
      uninterrupted run's losses for those n2 windows exactly -- with no act, with a save between a
      mint and the next act (the critic's blocking case), with a save after an act, and at
      TOK_DROPOUT > 0.
  S7  THE OLDER GENERATION RESUMES TOO (register LOW-Q-TOK-13-PREV, Proposal 05 §8 1.1): a parent
      that saved twice, with a mint between the saves, is resumed from '<dir>/ckpt.pt.prev' and its
      continuation equals the uninterrupted run's losses exactly, because TOK.save_vocabulary
      rotated the vocabulary with the checkpoint. The wrong pairings are still refused both ways,
      a missing file is still refused, a failed rotation keeps the new generation and says so, and
      an in-place resume from .prev never rotates onto the parent's file.

WHAT THIS FILE CANNOT SEE: whether live retokenization helps a long run. That is the owner-scale
ship-rule measurement 03b S0b names (prequential bits/byte, 3 paired seeds).
"""
import json
import os
import re
import shutil
import sys
import tempfile

_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(_ROOT, "src"))

import torch                                                       # noqa: E402
torch.set_num_threads(1)

from spine import lever as _lever                                  # noqa: E402
from spine import rng                                              # noqa: E402
from spine import loop                                             # noqa: E402
from spine import units as U                                       # noqa: E402
from spine.compose import compose                                  # noqa: E402
from train import api as run_api                                   # noqa: E402
from opt import api as opt_api                                     # noqa: E402
from tok import api as tok_api                                     # noqa: E402

FAILS = []
# The resume tests' small base: a tenth-size fabric keeps each compose to a few seconds. Minting first
# fires near window 120 here, so the act cases below save around it.
BASE = {"DATA_STREAM_BYTES": "60000", "SIG_WARMUP": "20", "FAB_N0": "256", "FAB_SLOTS": "512"}


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" -- {detail}" if detail else ""))
    if not ok:
        FAILS.append(name)


def build(**env):
    _lever._reopen_assembly()
    rng.reset_issued()
    e = dict(BASE)
    e.update({k: str(v) for k, v in env.items()})
    return compose(environ=e)


def books(res):
    """The loop's flush books; the report carries a sentence instead of a dict when no key is
    reachable on the arm, which reads here as no books."""
    b = res.report.get("LOOP(flush books)")
    return b if isinstance(b, dict) else {}


# ---- S1: the clock ------------------------------------------------------------------------------
class _R:
    epochs = 1
    def owned_by(self, _p):
        return self


c = run_api.new_clock(_R(), batch_windows=1, accum=1)
c.begin_epoch(10)
for _ in range(4):
    c.advance()
c.revise_epoch_length(7)
check("S1 revise keeps the cursor and takes the new length",
      c.counters()["in_epoch"] == 4 and c.counters()["windows_in_epoch"] == 7
      and c.counters()["epoch_revisions"] == 1, str(c.counters()))
try:
    c.revise_epoch_length(3)
    check("S1 a length below the cursor is refused", False, "accepted")
except ValueError:
    check("S1 a length below the cursor is refused", True)
c.revise_epoch_length(4)
t = c.advance()
check("S1 revise(n == in_epoch) rolls on the next advance without counting a window",
      bool(t.rolled) and int(t.step) == 4 and c.counters()["in_epoch"] == 0, str(t))

# ---- S2: the LR horizon -------------------------------------------------------------------------
H = opt_api.Horizon(run_steps=1000, warmup=100, wavelength=1000, n_cycles=1)


def _lr(step, revs):
    e = opt_api._effective_step(H, revs, step) if revs else None
    return opt_api._schedule(lr=1.0, sched="cosine", min_frac=0.05, restarts=True, decay=0.0,
                             shift_warm=0, restart_amp=1.0, shift_at=None, horizon=H, step=step,
                             eff_step=e)[0]


revs = [(400, 900)]
check("S2 a revision leaves lr(now) unchanged", abs(_lr(400, []) - _lr(400, revs)) < 1e-12,
      f"{_lr(400, [])} vs {_lr(400, revs)}")
check("S2 the revised schedule reaches the floor at the revised end",
      abs(_lr(900, revs) - 0.05) < 1e-12 and _lr(899, revs) > 0.05, f"{_lr(899, revs)}")
revs2 = revs + [(600, 850)]
check("S2 a second revision is continuous too and ends at the floor",
      abs(_lr(600, revs) - _lr(600, revs2)) < 1e-12 and abs(_lr(850, revs2) - 0.05) < 1e-12)
check("S2 the warmup is untouched", _lr(50, revs2) == _lr(50, []))

# ---- S3: splice and views -----------------------------------------------------------------------
v = tok_api.Vocabulary(ceiling=600)
v._add(b"ab", prov="t")
v._add(b"abc", prov="t")
data = b"abcab abc xabcx abcabc ab"
V0 = tok_api.view_of(v)
ids0, pos0 = tok_api._segment(v, data)
v._add(b"x ", prov="t")
v._retire(257)
ids_v, _ = tok_api._segment(v, data, view=V0)
check("S3 segmenting at a recorded view rebuilds the cut taken then, after a mint and a retirement",
      ids_v == ids0 and tok_api._segment(v, data)[0] != ids0, f"{ids_v} vs {ids0}")


class _T:
    dropout = 0.0
    def owned_by(self, _p):
        return self


seg0 = tok_api.Segmentation(ids=ids0, byte_pos=pos0, labels=None, bytes_per_token=1.0)
sp = tok_api.splice(_T(), v, seg0, data, at=2)
check("S3 splice keeps every unit up to and including the one under the cursor",
      sp.ids[:3] == ids0[:3] and sp.byte_pos[:3] == pos0[:3] and sp.ids != ids0,
      f"{sp.ids} from {ids0}")

# ---- S6 (unit): the MEM remap re-cuts a stored context to the same bytes -------------------------
from spine import loop as _loop                                    # noqa: E402
v2 = tok_api.Vocabulary(ceiling=600)
v2._add(b"ab", prov="t")
text = b"xxabcabcab abcabc"
old_ctx = tok_api._segment(v2, text)[0][-8:]
_abc = v2._add(b"abc", prov="t")
fn = _loop._mem_remap_fn(_T(), v2, list(tok_api.view_of(v2))[:1] + [[]])
new_ctx = fn([[0, 0] + old_ctx])[0]
check("S6 a re-cut context decodes to the bytes it held and uses the newer token",
      v2.decode(new_ctx) == v2.decode(old_ctx) and _abc in new_ctx and _abc not in old_ctx,
      f"{old_ctx} -> {new_ctx} (new id {_abc})")

# ---- S4: the act in a run -----------------------------------------------------------------------
s = build(TOK_GROW_EVERY=30, TOK_RETOK_EVERY=40)
r = loop.run(s, max_windows=130, progress=False)
check("S4 the act fires after a mint and splices the stream",
      int(books(r).get("loop.acts", 0)) >= 1 and int(s.vocab.counters.get("tok.retok_mid_epoch", 0)) >= 1
      and any("mid-epoch act" in w for w in r.warnings), str(books(r)))
s0 = build(TOK_GROW_EVERY=30, TOK_RETOK_EVERY=0)
r0 = loop.run(s0, max_windows=130, progress=False)
check("S4 TOK_RETOK_EVERY=0 arms no act (loop.acts ABSENT)", "loop.acts" not in books(r0),
      str(books(r0)))
_sc = s.store.counters
check("S6 an act in a run remaps MEM's stored contexts",
      int(_sc.get("store.n_remap_events", 0)) >= 1 and int(_sc.get("store.n_remapped_entries", 0)) > 0
      and int(s.vocab.counters.get("tok.segment_remap", 0)) > 0,
      f"events {_sc.get('store.n_remap_events')}, entries {_sc.get('store.n_remapped_entries')}")

# ---- S5: the continuation is bit-exact ----------------------------------------------------------
TMP = tempfile.mkdtemp(prefix="s0b_cont_")


def continuation(tag, n1, n2, **env):
    u = build(**env)
    ru = loop.run(u, max_windows=n1 + n2, progress=False)
    d = os.path.join(TMP, tag)
    p = build(CKPT_DIR=d + "/p", **env)
    rp = loop.run(p, max_windows=n1, progress=False)
    c = build(CKPT_RESUME=d + "/p", CKPT_DIR=d + "/c", **env)
    cont = [w for w in c.warnings if w.startswith("MID-EPOCH RESUME CONTINUES")]
    rc = loop.run(c, max_windows=n2, progress=False)
    a, b = ru.loss_curve[n1:n1 + n2], rc.loss_curve[:n2]
    same = len(a) == len(b) == n2 and all(x == y for x, y in zip(a, b))
    diff = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), None)
    return same, cont, diff, books(ru), books(rp), books(rc)


try:
    same, cont, diff, bu, _, _ = continuation("plain", 60, 40)
    check("S5 no act: the resumed run continues the uninterrupted run's losses exactly",
          same and len(cont) == 1, f"first differing window {diff}")
    same, cont, diff, bu, bp, bc = continuation("mint_then_act", 135, 30, TOK_GROW_EVERY=30,
                                               TOK_RETOK_EVERY=150)
    check("S5 a save between a mint and the next act continues exactly, the act inside the child",
          same and int(bp.get("loop.acts", 0)) == 0 and int(bc.get("loop.acts", 0)) >= 1,
          f"first differing {diff}; acts parent {bp.get('loop.acts')} child {bc.get('loop.acts')}")
    same, cont, diff, bu, bp, bc = continuation("after_act", 135, 25, TOK_GROW_EVERY=30,
                                               TOK_RETOK_EVERY=40)
    check("S5 a save after an act continues exactly (the log replays the splice)",
          same and int(bp.get("loop.acts", 0)) >= 1,
          f"first differing {diff}; acts parent {bp.get('loop.acts')}")
    same, cont, diff, bu, bp, bc = continuation("dropout", 135, 25, TOK_GROW_EVERY=30,
                                               TOK_RETOK_EVERY=40, TOK_DROPOUT=0.1)
    check("S5 at TOK_DROPOUT > 0 the continuation is exact (the dropout stream crosses the save)",
          same and int(bp.get("loop.acts", 0)) >= 1, f"first differing {diff}")
finally:
    shutil.rmtree(TMP, ignore_errors=True)

# ---- S7: the older generation resumes -----------------------------------------------------------
# THE REGISTER'S KNOWN ANSWER: save twice, resume from ckpt.pt.prev, bit-exact against an
# uninterrupted run. S5's mint_then_act levers, so a mint lands between the two saves and the two
# generations' vocabularies differ -- without that, pairing the wrong file could not be told from
# pairing the right one, and every check below would pass on a tree that never rotates.
TMP7 = tempfile.mkdtemp(prefix="s7_prev_")
E7 = {"TOK_GROW_EVERY": 30, "TOK_RETOK_EVERY": 150}


def _saves(res):
    """The run's own save count, off the gated line `run` appends from `_save`'s return value."""
    line = next((g for g in res.gated if g.startswith("CKPT.save:")), "")
    m = re.match(r"CKPT\.save: (\d+) checkpoint", line)
    return int(m.group(1)) if m else -1


def _entries(path):
    with open(path, encoding="utf-8") as fh:
        return len(json.load(fh)["entries"])


def _refusal(**env):
    """What composing a resume raised: (type name, message), or (None, '') when it composed."""
    try:
        build(**env)
        return None, ""
    except Exception as e:                                         # noqa: BLE001 -- reported
        return type(e).__name__, str(e)


try:
    d7 = TMP7
    u = build(**E7)
    ru = loop.run(u, max_windows=135, progress=False)
    p = build(CKPT_DIR=d7 + "/p", CKPT_EVERY=100, **E7)
    rp = loop.run(p, max_windows=135, progress=False)
    check("S7 setup: the saving parent's losses equal the uninterrupted run's (a rename changes no "
          "number)", tuple(rp.loss_curve) == tuple(ru.loss_curve[:135]))
    cur_ck, prev_ck = d7 + "/p/ckpt.pt", d7 + "/p/ckpt.pt.prev"
    cur_v, prev_v = d7 + "/p.dyntok.json", d7 + "/p.prev.dyntok.json"
    check("S7 setup: two saves left both generations on disk, each with its own vocabulary",
          _saves(rp) == 2 and all(os.path.isfile(f) for f in (cur_ck, prev_ck, cur_v, prev_v)),
          f"saves {_saves(rp)}; " + ", ".join(f"{os.path.basename(f)} {os.path.isfile(f)}"
                                                for f in (cur_ck, prev_ck, cur_v, prev_v)))
    bc = torch.load(cur_ck, map_location="cpu", weights_only=False)
    bp = torch.load(prev_ck, map_location="cpu", weights_only=False)
    m7, mc_prev, mc_cur = int(bp["step"]), bp["payload"]["TOK"]["merge_count"], \
        bc["payload"]["TOK"]["merge_count"]
    check("S7 setup: the older generation is a periodic save before the final one, and a mint lies "
          "between them (so the wrong vocabulary is distinguishable from the right one)",
          bp["reason"] == "periodic" and bc["reason"] == "final" and m7 < 135
          and mc_prev < mc_cur, f"step {m7}, merges {mc_prev} -> {mc_cur}")
    check("S7 each vocabulary file matches its own checkpoint's merge count",
          _entries(prev_v) == mc_prev and _entries(cur_v) == mc_cur,
          f"{_entries(prev_v)}/{mc_prev}, {_entries(cur_v)}/{mc_cur}")
    pc = p.vocab.counters
    check("S7 the parent's rotation rows: tok.vocab_rotated = saves - 1, tok.vocab_rotate_failed "
          "= 0, tok.vocab_rotate_refused ABSENT (not the in-place arm)",
          pc.get("tok.vocab_rotated") == _saves(rp) - 1 and pc.get("tok.vocab_rotate_failed") == 0
          and "tok.vocab_rotate_refused" not in pc,
          str({k: pc.get(k) for k in ("tok.vocab_rotated", "tok.vocab_rotate_failed",
                                      "tok.vocab_rotate_refused")}))

    c = build(CKPT_RESUME=prev_ck, CKPT_DIR=d7 + "/c", **E7)
    cont = [w for w in c.warnings if w.startswith("MID-EPOCH RESUME CONTINUES")]
    mint0 = int(c.vocab.counters.get("tok.mint", 0))
    n2 = 135 - m7
    rc = loop.run(c, max_windows=n2, progress=False)
    a, b = ru.loss_curve[m7:135], rc.loss_curve[:n2]
    diff = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), None)
    check("S7 THE KNOWN ANSWER: resumed from ckpt.pt.prev, the continuation equals the "
          "uninterrupted run's losses exactly",
          len(a) == len(b) == n2 and diff is None and len(cont) == 1,
          f"{n2} windows from step {m7}; first differing {diff}; {len(cont)} continue warning(s)")
    cc = c.vocab.counters
    check("S7 the child minted on the way (the continuation crossed a mint)",
          int(cc.get("tok.mint", 0)) > mint0, f"tok.mint {mint0} -> {cc.get('tok.mint')}")
    check("S7 the child's rotation rows are its own: tok.vocab_rotated PRESENT at 0 (one save into "
          "an empty directory), the parent's tok.vocab_rotated not carried, no refused row",
          cc.get("tok.vocab_rotated") == 0 and cc.get("tok.vocab_rotate_failed") == 0
          and "tok.vocab_rotate_refused" not in cc,
          str({k: cc.get(k) for k in ("tok.vocab_rotated", "tok.vocab_rotate_failed",
                                      "tok.vocab_rotate_refused")}))

    # THE MISMATCH REFUSALS STILL FIRE: each generation's checkpoint beside the OTHER generation's
    # vocabulary, and the older checkpoint with none.
    os.makedirs(d7 + "/w")
    shutil.copy(prev_ck, d7 + "/w/ckpt.pt.prev")
    shutil.copy(cur_v, d7 + "/w.prev.dyntok.json")
    kind, msg = _refusal(CKPT_RESUME=d7 + "/w/ckpt.pt.prev", CKPT_DIR=d7 + "/wc", **E7)
    check("S7 the older checkpoint beside the NEWER vocabulary is refused by the merge count",
          kind == "LeverError" and "TOK resume refused" in msg
          and f"records {mc_prev} merges" in msg and f"has {mc_cur}" in msg, f"{kind}: {msg[:140]}")
    os.makedirs(d7 + "/v")
    shutil.copy(cur_ck, d7 + "/v/ckpt.pt")
    shutil.copy(prev_v, d7 + "/v.dyntok.json")
    kind, msg = _refusal(CKPT_RESUME=d7 + "/v", CKPT_DIR=d7 + "/vc", **E7)
    check("S7 the newer checkpoint beside the OLDER vocabulary is refused the other way",
          kind == "LeverError" and "TOK resume refused" in msg
          and f"records {mc_cur} merges" in msg and f"has {mc_prev}" in msg, f"{kind}: {msg[:140]}")
    os.makedirs(d7 + "/n")
    shutil.copy(prev_ck, d7 + "/n/ckpt.pt.prev")
    kind, msg = _refusal(CKPT_RESUME=d7 + "/n/ckpt.pt.prev", CKPT_DIR=d7 + "/nc", **E7)
    check("S7 the older checkpoint with no vocabulary beside it is still refused by name",
          kind == "ValueError" and "does not exist" in msg, f"{kind}: {msg[:140]}")

    # A FAILED ROTATION KEEPS THE NEW GENERATION: a directory stands where the rotation must land.
    os.makedirs(d7 + "/f.prev.dyntok.json")
    f = build(CKPT_DIR=d7 + "/f", CKPT_EVERY=20)
    rf = loop.run(f, max_windows=45, progress=False)
    fc = f.vocab.counters
    fw = [w for w in rf.warnings if "vocabulary rotation failed" in w]
    check("S7 a failed rotation is counted once per save that had a file to move, with its reason",
          _saves(rf) >= 2 and fc.get("tok.vocab_rotate_failed") == _saves(rf) - 1
          and fc.get("tok.vocab_rotated") == 0
          and "f.prev.dyntok.json" in str(fc.get("tok.vocab_rotate_failed_detail")),
          f"saves {_saves(rf)}; {fc.get('tok.vocab_rotate_failed')}; "
          f"{fc.get('tok.vocab_rotate_failed_detail')}")
    check("S7 ... the run completes, the loop warns after the final save, and the new generation "
          "landed", len(fw) == 1 and _entries(d7 + "/f.dyntok.json") == f.vocab.size() - 256
          and os.path.isdir(d7 + "/f.prev.dyntok.json"), f"{len(fw)} warning(s)")
    kind, msg = _refusal(CKPT_RESUME=d7 + "/f", CKPT_DIR=d7 + "/f2")
    check("S7 ... and the current generation it wrote resumes", kind is None, f"{kind}: {msg[:140]}")

    # IN PLACE: a resume from .prev that saves back into the same directory never rotates onto the
    # file it read, and the .prev pair CKPT then leaves mismatched is refused by name.
    shutil.copytree(d7 + "/p", d7 + "/ip")
    shutil.copy(cur_v, d7 + "/ip.dyntok.json")
    shutil.copy(prev_v, d7 + "/ip.prev.dyntok.json")
    with open(d7 + "/ip.prev.dyntok.json", "rb") as fh:
        parent_bytes = fh.read()
    ip = build(CKPT_RESUME=d7 + "/ip/ckpt.pt.prev", CKPT_DIR=d7 + "/ip", **E7)
    rip = loop.run(ip, max_windows=10, progress=False)
    with open(d7 + "/ip.prev.dyntok.json", "rb") as fh:
        after_bytes = fh.read()
    ipc = ip.vocab.counters
    check("S7 in place: the parent's .prev vocabulary is byte-unchanged, the skip is counted and "
          "warned, and the new generation landed",
          after_bytes == parent_bytes and ipc.get("tok.vocab_rotate_refused") == 1
          and ipc.get("tok.vocab_rotated") == 0
          and any("vocabulary was NOT rotated" in w for w in rip.warnings)
          and _entries(d7 + "/ip.dyntok.json") == ip.vocab.size() - 256,
          str({k: ipc.get(k) for k in ("tok.vocab_rotated", "tok.vocab_rotate_refused")}))
    kind, msg = _refusal(CKPT_RESUME=d7 + "/ip/ckpt.pt.prev", CKPT_DIR=d7 + "/ipc", **E7)
    check("S7 in place: the .prev pair CKPT's rotation left mismatched is refused by the merge count",
          kind == "LeverError" and "TOK resume refused" in msg, f"{kind}: {msg[:140]}")
finally:
    shutil.rmtree(TMP7, ignore_errors=True)

print(f"\n=== {len(FAILS)} failing ===")
sys.exit(1 if FAILS else 0)
