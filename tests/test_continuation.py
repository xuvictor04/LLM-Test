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
  S2b AT OPT_HORIZON_REVISE=False (Proposal 05 §8 1.4, Q-OPT-12) revise_horizon returns None, logs
      nothing, and counts opt.horizon.revise_inert and opt.horizon.revise_declined.
  S3  TOK.splice keeps every unit up to and including the one under the cursor; tokenize(view=) at a
      recorded view rebuilds the segmentation cut then, after later mints and a retirement.
  S4  the act fires after a mint and changes the stream; TOK_RETOK_EVERY=0 arms no act.
  S6  MEM's stored contexts are re-cut at the act's view (MEM.maintain(remap=), Q-MEM-13): a re-cut
      context decodes to the same bytes it held, spelled in the newer tokens, and an act in a run
      remaps the store.
  S5  THE CONTINUATION IS BIT-EXACT: a run saved at window n1 and resumed for n2 windows produces the
      uninterrupted run's losses for those n2 windows exactly -- with no act, with a save between a
      mint and the next act (the critic's blocking case), with a save after an act, and at
      TOK_DROPOUT > 0 -- and under a non-default OPT_LR_CONTINUE, which a same-length resume never
      anchors (Q-OPT-12). THE S0b SECONDARIES CONTINUE TOO (Q-RUN-17): the child's per-flush bytes
      are the uninterrupted run's, and fab.blackout_windows, tok.mint_wait_windows / tok.mint_waited
      and tok.bpt_tail equal its own; a mint before the save is waited across it into the child's
      act (the open births ride loop_carried), and a save inside the blackout splits its windows
      between parent and child (growth['checked_at'] rides FAB's state).
  S7  THE OLDER GENERATION RESUMES TOO (register LOW-Q-TOK-13-PREV, Proposal 05 §8 1.1): a parent
      that saved twice, with a mint between the saves, is resumed from '<dir>/ckpt.pt.prev' and its
      continuation equals the uninterrupted run's losses exactly, because TOK.save_vocabulary
      rotated the vocabulary with the checkpoint. The wrong pairings are still refused both ways,
      a missing file is still refused, a failed rotation keeps the new generation and says so, and
      an in-place resume from .prev rotates onto the file it read, so ckpt.pt.prev -- the parent's
      newer generation -- resumes after the in-place save (corrected 2026-09-27: that arm skipped,
      and the newer generation's vocabulary was lost). The report prints the rotation rows after
      the final save, ABSENT only with saving off, and a parent's rows do not cross a resume from a
      blob that carries them.
  S8  THE IN-RUN REVISION'S OFF ARM IN A RUN (Proposal 05 §8 1.4): S4's shape at
      OPT_HORIZON_REVISE=False still acts, and every revision an act asked for is declined and
      counted -- no revision logged, opt.horizon.revise_inert 1, opt.horizon.revise_declined equal to
      the acts that changed the epoch's length -- while S4's default run did log them.
  S9  THE S0b SECONDARIES (Proposal 05 §8 1.3, Q-RUN-17), on S4's two runs, each against a number
      computed here from something else the run left behind: fab.blackout_windows from the acts'
      warning lines and FAB_COOLDOWN; tok.mint_wait_windows / tok.mint_waited from Vocabulary.prov,
      with every mint waited or stranded; loop.act_seconds / loop.act_remap_seconds as floats that
      tests/test_baseline.py::COUNTER can never read as an integer counter; tok.bpt_tail from the
      final segmentation, and on the act's own line; RunResult.flush_bytes summing to
      loop.bytes_scored; and run.py --flush-bytes beside --loss-curve. On the TOK_RETOK_EVERY=0 run
      each counter is ABSENT -- fab.blackout_windows too since 2026-09-27 (build 1.3's review), which
      read armed and 0 there beside FAB's UNREACHABLE Gate and now waits for the first stamp.
  S10 THE SAVE COUNTERS ARE THE LINEAGE'S, BESIDE A PROCESS TWIN (Proposal 05 §8 1.6, register
      LOW-RESUME-SAVED-COUNTERS): a parent that saved k times and a child that saved j times before
      its report read (k + j, j) on all ten save counts -- where the unfixed tree read k - 1 + j,
      k + j and j across packages -- the child's final blob holds k + j + 1 (a blob counts itself),
      and a resume from that blob restores k + j + 1, tok.vocab_saved included; a resume from a
      lineage's first save, whose blob predates every vocabulary file, restores tok.vocab_saved 1.
      AND ONE RULE FOR THE TWIN (build 1.6's review): no ledger carries one before its process
      saves; the report prints (k + j, 0) at j = 0 with saving on (a grandchild at CKPT_EVERY=0, and
      (0, 0) on a fresh saving run) and the twin ABSENT with saving off, where the run's final save
      no longer builds a payload and so counts nothing; TOK_MODE=bytes reads (k + j, j) on
      tok.vocab_saved too. A save CKPT refuses as non-finite is still counted (OWED, pinned).
  S11 PERIODIC SAVES CHANGE NO NUMBER AND LAND ON THE ACT WINDOWS (Proposal 05 §8 1.5, register note
      retok fleet (1)): S4's two runs rebuilt with CKPT_EVERY at the act cadence reproduce their
      no-save loss curves exactly, act at the same windows, and leave the periodic save at the last
      act's window (121) as the ring's older generation, paired with its own vocabulary -- the
      known answer that lets gpu_world.sh's EXP=retok pair a saving k0 with act arms that save only
      at the end, and keep k0's saves as the spike test's maturity-matched control.

WHAT THIS FILE CANNOT SEE: whether live retokenization helps a long run. That is the owner-scale
ship-rule measurement 03b S0b names (prequential bits/byte, 3 paired seeds).
"""
import json
import os
import re
import shutil
import subprocess
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


# ---- the S0b secondaries' known answers, computed apart from the code that counts them (S9, S5) ---
def act_windows(res):
    """The windows the run's acts fired at, off each act's own warning line."""
    return [int(m.group(1)) for w in res.warnings
            for m in [re.match(r"loop: mid-epoch act at window (\d+):", w)] if m]


def blackout_expected(acts, end, cooldown):
    """fab.blackout_windows at batch 1 with acts as the only stamps: each act blacks out the checks
    after it, up to the next act (whose own flush still checks under the old stamp), the run's end,
    or cooldown - 1 windows, whichever comes first."""
    return sum(min(cooldown - 1, (acts[i + 1] if i + 1 < len(acts) else end) - a)
               for i, a in enumerate(acts))


def mint_wait_expected(vocab, cuts):
    """(tok.mint_wait_windows, tok.mint_waited) off Vocabulary.prov: every id minted online and not
    retired waits from its birth to the first re-segmentation at or after it (an id born in an act's
    own flush waits 0); one no cut reached is stranded and counted in neither."""
    total = n = 0
    for tid, entry in vocab.prov.items():
        rec = tok_api._prov_online(entry)
        if rec is None or int(tid) in vocab.retired:
            continue
        after = [a for a in cuts if a >= rec[0]]
        if after:
            total, n = total + after[0] - rec[0], n + 1
    return total, n


def stranded(res):
    """The count the loop's 'minted AFTER THE LAST RE-SEGMENTATION' warning names, 0 without one."""
    m = next((re.match(r"loop: (\d+) token\(s\) were minted AFTER THE LAST", w) for w in res.warnings
              if "minted AFTER THE LAST RE-SEGMENTATION" in w), None)
    return int(m.group(1)) if m else 0


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

# ---- S2b: the in-run revision's off arm (Proposal 05 §8 1.4, Q-OPT-12) --------------------------
from spine import assemble                                         # noqa: E402
_lever._reopen_assembly()
_off = assemble.build(environ={"OPT_HORIZON_REVISE": "False"})[0]["OPT"]
_p = torch.nn.Parameter(torch.ones(3))
_st = opt_api.build(_off, param_groups={"base": [_p], "encoder": []}, run_windows=U.Windows(1000))
_seeded = _st.counters.get("opt.horizon.revise_declined")
for _ in range(10):
    opt_api.scaled_backward(_off, _st, (_p * _p).sum())
    opt_api.maybe_step(_off, _st)
_got = opt_api.revise_horizon(_off, _st, run_windows=U.Windows(900))
check("S2b at OPT_HORIZON_REVISE=False revise_horizon returns None, logs nothing, and counts "
      "revise_inert = 1 and revise_declined 0 -> 1",
      _got is None and _st.horizon_revisions == [] and "opt.horizon.revisions" not in _st.counters
      and _st.counters.get("opt.horizon.revise_inert") == 1 and _seeded == 0
      and _st.counters.get("opt.horizon.revise_declined") == 1,
      {k: _st.counters.get(k) for k in ("opt.horizon.revise_inert", "opt.horizon.revise_declined")})

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
_s4_len_changes = int(s.clock.counters().get("epoch_revisions", 0))
check("S4 ... at the default OPT_HORIZON_REVISE=True an act that changed the epoch's length logged a "
      "horizon revision (the control S8's off arm is read against)",
      _s4_len_changes >= 1 and int(s.optimizer.counters.get("opt.horizon.revisions", 0)) >= 1
      and "opt.horizon.revise_declined" not in s.optimizer.counters,
      f"length changes {_s4_len_changes}, revisions {s.optimizer.counters.get('opt.horizon.revisions')}")
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
    return same, cont, diff, books(ru), books(rp), books(rc), \
        {"u": u, "ru": ru, "p": p, "rp": rp, "c": c, "rc": rc, "n1": n1, "n2": n2}


# THE S0b SECONDARIES CROSS THE SAVE (Q-RUN-17). Only the new readings are compared between the
# child and the uninterrupted run: tok.retok_mid_epoch, tok.retok and tok.byte_fallback (and
# tok.dropout_skip at TOK_DROPOUT > 0) already differ across a continuing resume whose parent acted
# before its save, because the log replay splices again after restore_vocab put the parent's counts
# back (recorded in Q-RUN-17's 2026-09-27 correction (iii), with this file's numbers; not repaired
# here).
_SECONDARY = ("tok.mint_wait_windows", "tok.mint_waited", "tok.bpt_tail")


def secondaries_cross(tag, x):
    u, ru, c, rc, n1, n2 = x["u"], x["ru"], x["c"], x["rc"], x["n1"], x["n2"]
    fu, fc = u.fabric.counters, c.fabric.counters
    tv = {k: (u.vocab.counters.get(k, "ABSENT"), c.vocab.counters.get(k, "ABSENT"))
          for k in _SECONDARY}
    check(f"S5 {tag}: the secondaries continue too -- the child's per-flush bytes are the "
          f"uninterrupted run's, and fab.blackout_windows and the tok.mint_wait / tok.bpt_tail "
          f"readings equal its own",
          tuple(rc.flush_bytes) == tuple(ru.flush_bytes[n1:n1 + n2]) and len(rc.flush_bytes) == n2
          and fc.get("fab.blackout_windows", "ABSENT") == fu.get("fab.blackout_windows", "ABSENT")
          and all(a == b for a, b in tv.values()),
          f"flush_bytes equal {tuple(rc.flush_bytes) == tuple(ru.flush_bytes[n1:n1 + n2])}; "
          f"blackout u {fu.get('fab.blackout_windows', 'ABSENT')} c "
          f"{fc.get('fab.blackout_windows', 'ABSENT')}; {tv}")


try:
    same, cont, diff, bu, _, _, x = continuation("plain", 60, 40)
    check("S5 no act: the resumed run continues the uninterrupted run's losses exactly",
          same and len(cont) == 1, f"first differing window {diff}")
    secondaries_cross("plain", x)
    same, cont, diff, bu, bp, bc, x = continuation("mint_then_act", 135, 30, TOK_GROW_EVERY=30,
                                                  TOK_RETOK_EVERY=150)
    check("S5 a save between a mint and the next act continues exactly, the act inside the child",
          same and int(bp.get("loop.acts", 0)) == 0 and int(bc.get("loop.acts", 0)) >= 1,
          f"first differing {diff}; acts parent {bp.get('loop.acts')} child {bc.get('loop.acts')}")
    secondaries_cross("mint_then_act", x)
    # THE NON-ZERO RESUME KNOWN ANSWER: ids the parent minted before its save wait across it for the
    # child's act, so their windows are counted only if the open births crossed in loop_carried.
    _open = (x["p"].loop_carried or {}).get("mint_open") or []
    _want = mint_wait_expected(x["u"].vocab, act_windows(x["ru"]))
    _cv = x["c"].vocab.counters
    check("S5 mint_then_act: the parent's open mint waits cross the save and close at the child's "
          "act -- tok.mint_wait_windows and tok.mint_waited equal the count off Vocabulary.prov, "
          "and part of that sum was waited before the save",
          len(_open) > 0 and _want[0] > 0
          and (_cv.get("tok.mint_wait_windows"), _cv.get("tok.mint_waited")) == _want,
          f"{len(_open)} open at the save; prov gives {_want}; child "
          f"{(_cv.get('tok.mint_wait_windows'), _cv.get('tok.mint_waited'))}")
    same, cont, diff, bu, bp, bc, x = continuation("after_act", 135, 25, TOK_GROW_EVERY=30,
                                                  TOK_RETOK_EVERY=40)
    check("S5 a save after an act continues exactly (the log replays the splice)",
          same and int(bp.get("loop.acts", 0)) >= 1,
          f"first differing {diff}; acts parent {bp.get('loop.acts')}")
    secondaries_cross("after_act", x)
    # MID-BLACKOUT: the parent saved inside the act's cooldown, so the child's first check credits
    # one window from the parent's last check (growth['checked_at'] crossed), not from the stamp.
    _bw = blackout_expected(act_windows(x["ru"]), int(x["ru"].windows),
                            int(x["u"].configs["FAB"].cooldown))
    _pb = x["p"].fabric.counters.get("fab.blackout_windows")
    check("S5 after_act: a save inside the blackout splits fab.blackout_windows between parent and "
          "child and the two add to the uninterrupted run's",
          _bw > 0 and 0 < _pb < _bw and x["c"].fabric.counters.get("fab.blackout_windows") == _bw,
          f"expected {_bw}; parent {_pb}; child {x['c'].fabric.counters.get('fab.blackout_windows')}")
    same, cont, diff, bu, bp, bc, x = continuation("dropout", 135, 25, TOK_GROW_EVERY=30,
                                                  TOK_RETOK_EVERY=40, TOK_DROPOUT=0.1)
    check("S5 at TOK_DROPOUT > 0 the continuation is exact (the dropout stream crosses the save)",
          same and int(bp.get("loop.acts", 0)) >= 1, f"first differing {diff}")
    secondaries_cross("dropout", x)
    # A NON-DEFAULT CONTINUATION REGIME (Q-OPT-12): a resume at the parent's horizon is not a session
    # boundary, so no regime is anchored and the continuation stays bit-exact.
    same, cont, diff, bu, bp, bc, x = continuation("regime", 60, 40, OPT_LR_CONTINUE="rewarm")
    check("S5 under OPT_LR_CONTINUE=rewarm a same-length resume continues exactly (no boundary, so "
          "nothing is anchored)", same and len(cont) == 1, f"first differing window {diff}")
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
    _rows = ("tok.vocab_rotated", "tok.vocab_rotate_failed", "tok.vocab_rotated_in_place")
    check("S7 the parent's rotation rows: tok.vocab_rotated = saves - 1, tok.vocab_rotate_failed "
          "= 0, tok.vocab_rotated_in_place ABSENT (not the in-place arm)",
          pc.get("tok.vocab_rotated") == _saves(rp) - 1 and pc.get("tok.vocab_rotate_failed") == 0
          and "tok.vocab_rotated_in_place" not in pc, str({k: pc.get(k) for k in _rows}))
    # THE REPORT READS THE ROWS AFTER THE FINAL SAVE (2026-09-27): its TOK snapshot is taken before
    # that save, and the final save is the one that rotated here. The uninterrupted run saves
    # nothing, so it is the ABSENT arm.
    rpt = rp.report["TOK(vocab.counters)"]
    check("S7 the report counts the final save's rotation (tok.vocab_rotated = saves - 1, though "
          "its snapshot was taken before that save), and a run with saving off prints no rotation row",
          rpt.get("tok.vocab_rotated") == _saves(rp) - 1 and rpt.get("tok.vocab_rotate_failed") == 0
          and not any(k.startswith("tok.vocab_rot") for k in ru.report["TOK(vocab.counters)"]),
          str({k: rpt.get(k, "ABSENT") for k in _rows}))

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
    # WHAT THIS CHILD CAN SHOW ABOUT ITS ROWS, AND NO MORE. It resumed from the step-101 blob, which
    # vocab_state copied before the parent's first vocabulary save, so that blob carries no rotation
    # row and "not carried" is not measurable here (it is below, from a blob that carries them). Its
    # only save is the final one, which is the report's DID IT FIRE case: the rows used to print
    # ABSENT, the "unreachable" reading, on a run where the rotation was armed.
    crpt = rc.report["TOK(vocab.counters)"]
    check("S7 the child's rotation rows: tok.vocab_rotated PRESENT at 0 (one save into an empty "
          "directory), no in-place row, and its report prints them PRESENT though its only save "
          "followed the report's snapshot",
          cc.get("tok.vocab_rotated") == 0 and cc.get("tok.vocab_rotate_failed") == 0
          and "tok.vocab_rotated_in_place" not in cc
          and crpt.get("tok.vocab_rotated") == 0 and crpt.get("tok.vocab_rotate_failed") == 0
          and "tok.vocab_rotated_in_place" not in crpt,
          f"live {({k: cc.get(k, 'ABSENT') for k in _rows})}; "
          f"report {({k: crpt.get(k, 'ABSENT') for k in _rows})}")

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
    check("S7 ... and the report counts the final save's failure too",
          rf.report["TOK(vocab.counters)"].get("tok.vocab_rotate_failed") == _saves(rf) - 1,
          str(rf.report["TOK(vocab.counters)"].get("tok.vocab_rotate_failed", "ABSENT")))
    # PER PROCESS, FROM A BLOB THAT CARRIES THE ROWS (2026-09-27). This run's final blob was taken
    # after its second save failed, so it holds tok.vocab_rotate_failed > 0 and the detail; a child
    # that has not saved yet must hold none of the rotation rows.
    fblob = torch.load(d7 + "/f/ckpt.pt", map_location="cpu", weights_only=False)
    fbc = fblob["payload"]["TOK"]["counters"]
    try:
        f2 = build(CKPT_RESUME=d7 + "/f", CKPT_DIR=d7 + "/f2")
        kind, msg, f2rows = None, "", sorted(k for k in f2.vocab.counters
                                             if k.startswith("tok.vocab_rot"))
    except Exception as e:                                         # noqa: BLE001 -- reported
        kind, msg, f2rows = type(e).__name__, str(e), None
    check("S7 ... the current generation it wrote resumes, and the parent's rotation rows do not "
          "cross: its blob carries tok.vocab_rotate_failed > 0 with the detail, and the child, "
          "which has not saved, carries no tok.vocab_rot* row",
          kind is None and int(fbc.get("tok.vocab_rotate_failed", 0)) > 0
          and "tok.vocab_rotate_failed_detail" in fbc and f2rows == [],
          f"{kind}: {msg[:140]}; blob tok.vocab_rotate_failed {fbc.get('tok.vocab_rotate_failed')}; "
          f"child rows {f2rows}")

    # IN PLACE: a resume from .prev that saves back into the same directory. CKPT.save moves the
    # parent's ckpt.pt (step 135) onto ckpt.pt.prev in that save, so TOK must move the parent's
    # newer vocabulary onto <dir>.prev.dyntok.json -- the file this run replayed -- or that
    # generation loses its only vocabulary. Until 2026-09-27 the rotation was skipped here, and this
    # check pinned the resulting ckpt.pt.prev refusal as expected behaviour.
    shutil.copytree(d7 + "/p", d7 + "/ip")
    shutil.copy(cur_v, d7 + "/ip.dyntok.json")
    shutil.copy(prev_v, d7 + "/ip.prev.dyntok.json")
    with open(d7 + "/ip.dyntok.json", "rb") as fh:
        newer_bytes = fh.read()
    ip = build(CKPT_RESUME=d7 + "/ip/ckpt.pt.prev", CKPT_DIR=d7 + "/ip", **E7)
    rip = loop.run(ip, max_windows=10, progress=False)
    with open(d7 + "/ip.prev.dyntok.json", "rb") as fh:
        after_bytes = fh.read()
    ipc = ip.vocab.counters
    ipb = torch.load(d7 + "/ip/ckpt.pt.prev", map_location="cpu", weights_only=False)
    check("S7 in place: ckpt.pt.prev is now the parent's newer generation, its vocabulary moved "
          "beside it byte for byte, the rotation counted and said, and the new generation landed",
          int(ipb["step"]) == 135 and ipb["payload"]["TOK"]["merge_count"] == mc_cur
          and after_bytes == newer_bytes and _saves(rip) == 1
          and ipc.get("tok.vocab_rotated_in_place") == 1 and ipc.get("tok.vocab_rotated") == 1
          and rip.report["TOK(vocab.counters)"].get("tok.vocab_rotated_in_place") == 1
          and sum("rotated onto the file this run resumed from" in w for w in rip.warnings) == 1
          and _entries(d7 + "/ip.dyntok.json") == ip.vocab.size() - 256,
          f"ckpt.pt.prev step {ipb['step']}, merges {ipb['payload']['TOK']['merge_count']}; "
          + str({k: ipc.get(k) for k in _rows}))
    kind, msg = _refusal(CKPT_RESUME=d7 + "/ip/ckpt.pt.prev", CKPT_DIR=d7 + "/ipc", **E7)
    check("S7 in place: ckpt.pt.prev RESUMES after the in-place save -- the parent's newer "
          "generation, which the skip left beside the older vocabulary and refused",
          kind is None, f"{kind}: {msg[:140]}")
    kind, msg = _refusal(CKPT_RESUME=d7 + "/ip/ckpt.pt", CKPT_DIR=d7 + "/ipc2", **E7)
    check("S7 in place: ... and the child's own ckpt.pt resumes", kind is None, f"{kind}: {msg[:140]}")

    # A DIRECTORY NAMED FOR ANOTHER RUN'S SNAPSHOT IS REFUSED AT COMPOSE (2026-09-27): '<X>.prev'
    # would save its vocabulary to the file run <X> rotates its previous generation onto.
    kind, msg = _refusal(CKPT_DIR=d7 + "/p.prev", **E7)
    kind_b, msg_b = _refusal(CKPT_DIR=d7 + "/p.best3/", **E7)
    kind_ok, msg_ok = _refusal(CKPT_DIR=d7 + "/p.prev2", **E7)
    check("S7 CKPT_DIR ending in .prev or .best<N> is refused at compose, naming the run it would "
          "collide with, before anything is written; a name that merely contains it composes",
          kind == "LeverError" and "reserved" in msg and repr(d7 + "/p") in msg
          and kind_b == "LeverError" and "'.best3'" in msg_b
          and not os.path.exists(d7 + "/p.prev") and not os.path.exists(d7 + "/p.best3")
          and kind_ok is None, f"{kind}: {msg[:120]} | {kind_b} | {kind_ok}: {msg_ok[:120]}")
finally:
    shutil.rmtree(TMP7, ignore_errors=True)

# ---- S8: the in-run revision's off arm in a run -------------------------------------------------
s8 = build(TOK_GROW_EVERY=30, TOK_RETOK_EVERY=40, OPT_HORIZON_REVISE="False")
r8 = loop.run(s8, max_windows=130, progress=False)
_k8 = s8.optimizer.counters
_len8 = int(s8.clock.counters().get("epoch_revisions", 0))
check("S8 at OPT_HORIZON_REVISE=False the act still fires, and every revision it asked for is declined "
      "and counted: no revision logged, revise_inert 1, revise_declined = the acts that changed the "
      "epoch's length",
      int(books(r8).get("loop.acts", 0)) >= 1 and _len8 >= 1 and s8.optimizer.horizon_revisions == []
      and "opt.horizon.revisions" not in _k8 and _k8.get("opt.horizon.revise_inert") == 1
      and _k8.get("opt.horizon.revise_declined") == _len8,
      f"acts {books(r8).get('loop.acts')}, length changes {_len8}, "
      f"declined {_k8.get('opt.horizon.revise_declined')}")
_g8 = r8.report.get("OPT.counters", {}).get("opt.horizon.revise") \
    if isinstance(r8.report.get("OPT.counters"), dict) else None
check("S8 ... and the report's Gate opt.horizon.revise says UNREACHABLE and names the lever",
      _g8 is not None and not _g8.reachable and "OPT_HORIZON_REVISE=False" in _g8.reason,
      _g8.line()[:160] if _g8 is not None else sorted(r8.report)[:8])

# ---- S9: the S0b secondaries (Proposal 05 §8 1.3, Q-RUN-17) --------------------------------------
# S4's two runs again: s/r act (TOK_GROW_EVERY=30 TOK_RETOK_EVERY=40), s0/r0 cannot. Each reading is
# checked against a number computed here from something else the run left behind, and ABSENT on the
# arm that cannot reach it.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_baseline import COUNTER                                  # noqa: E402

_acts = act_windows(r)
_fc, _fc0 = s.fabric.counters, s0.fabric.counters
_bw = blackout_expected(_acts, int(r.windows), int(s.configs["FAB"].cooldown))
# THE GATE BESIDE IT (corrected 2026-09-27, build 1.3's review): this run's key was armed and 0 while
# FAB's own fab.growth_blackout Gate printed UNREACHABLE; the key now waits for the first stamp.
_g0 = r0.report.get("FAB.grow_check(last call's gates)")
_g0 = _g0.get("gate:fab.growth_blackout") if isinstance(_g0, dict) else None
check("S9 fab.blackout_windows counts the windows each act's stamp held growth off (one per check "
      "at batch 1, to the next act, the run's end or the cooldown); ABSENT at TOK_RETOK_EVERY=0, "
      "where no stamp arrives, beside fab.shift_notifications 0 and the Gate's UNREACHABLE",
      bool(_acts) and _bw > 0 and _fc.get("fab.blackout_windows") == _bw
      and "fab.blackout_windows" not in _fc0 and _fc0.get("fab.shift_notifications") == 0
      and _g0 is not None and _g0[0] == "unreachable",
      f"acts {_acts}, expected {_bw}, got {_fc.get('fab.blackout_windows')}; retok 0: "
      f"{_fc0.get('fab.blackout_windows', 'ABSENT')} with "
      f"{_fc0.get('fab.shift_notifications')} notification(s), gate {_g0!r}")
_tc, _tc0 = s.vocab.counters, s0.vocab.counters
_mw = mint_wait_expected(s.vocab, _acts)
check("S9 tok.mint_wait_windows / tok.mint_waited equal the count off Vocabulary.prov, every mint "
      "is waited or stranded, and both are ABSENT at TOK_RETOK_EVERY=0 on one epoch",
      (_tc.get("tok.mint_wait_windows"), _tc.get("tok.mint_waited")) == _mw and _mw[1] > 0
      and _tc.get("tok.mint_waited") + stranded(r) == _tc.get("tok.mint")
      and "tok.mint_wait_windows" not in _tc0 and "tok.mint_waited" not in _tc0,
      f"prov {_mw}; counted {(_tc.get('tok.mint_wait_windows'), _tc.get('tok.mint_waited'))}; "
      f"stranded {stranded(r)}, tok.mint {_tc.get('tok.mint')}; retok 0: "
      f"{_tc0.get('tok.mint_wait_windows', 'ABSENT')}, {_tc0.get('tok.mint_waited', 'ABSENT')}")
_bk, _bk0 = books(r), books(r0)
_as, _ar = _bk.get("loop.act_seconds"), _bk.get("loop.act_remap_seconds")
_leak = [f"{k}={v!r}" for k in ("loop.act_seconds", "loop.act_remap_seconds") for v in
         (_bk.get(k), 0.0) if COUNTER.match(f"       {k:<44} {v}")]
check("S9 loop.act_seconds and loop.act_remap_seconds are wall-clock floats (the act ran and its MEM "
      "re-cut ran), neither can enter test_baseline's integer channel, and both are ABSENT at "
      "TOK_RETOK_EVERY=0",
      isinstance(_as, float) and 0.0 < _as < float(r.elapsed_s) and isinstance(_ar, float)
      and _ar > 0.0 and int(s.store.counters.get("store.n_remap_events", 0)) >= 1 and not _leak
      and "loop.act_seconds" not in _bk0 and "loop.act_remap_seconds" not in _bk0,
      f"act {_as!r}, remap {_ar!r} of {r.elapsed_s:.1f}s; COUNTER matched {_leak}; retok 0: "
      f"{sorted(k for k in _bk0 if k.startswith('loop.act'))}")
_k0 = _acts[-1] * int(s.configs["LM"].ctx)
_seg = s.segmentation
_tail = round((len(s.stream.bytes) - _seg.byte_pos[_k0 + 1]) / (len(_seg.ids) - (_k0 + 1)), 6)
_last = [w for w in r.warnings if w.startswith(f"loop: mid-epoch act at window {_acts[-1]}:")]
check("S9 tok.bpt_tail is the last act's tail bytes per token, printed on that act's line beside "
      "the tail before it and the build-time value; ABSENT where no act ran",
      _tc.get("tok.bpt_tail") == _tail and len(_last) == 1 and f"-> {_tail:.4f}" in _last[0]
      and "against the build-time" in _last[0] and "tok.bpt_tail" not in _tc0,
      f"counter {_tc.get('tok.bpt_tail')!r}, recomputed {_tail}; "
      f"{_last[0][-150:] if _last else 'no act line'}")
for _tag, _res in (("an act-firing run", r), ("TOK_RETOK_EVERY=0", r0)):
    _fb = _res.flush_bytes
    check(f"S9 RunResult.flush_bytes on {_tag}: one positive entry per loss, summing to "
          f"loop.bytes_scored (never_backward 0)",
          len(_fb) == len(_res.loss_curve) == int(_res.flushes) and all(int(v) > 0 for v in _fb)
          and _res.never_backward == 0 and sum(_fb) == books(_res).get("loop.bytes_scored"),
          f"{len(_fb)} entries, {len(_res.loss_curve)} losses, {_res.flushes} flushes; sum "
          f"{sum(_fb)} vs {books(_res).get('loop.bytes_scored')}")
# THE DRIVER FLAG, through run.py, beside --loss-curve (whose format stays a flat list of floats).
TMP9 = tempfile.mkdtemp(prefix="s9_fb_")
try:
    _env = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG", "PYTHONPATH")}
    _env.update(BASE)
    _env.update({"RUN_DEVICE": "cpu", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"})
    _lc, _fbp = os.path.join(TMP9, "curve.json"), os.path.join(TMP9, "bytes.json")
    _p = subprocess.run([sys.executable, "run.py", "--max-windows", "6", "--quiet", "--loss-curve",
                         _lc, "--flush-bytes", _fbp], cwd=os.path.abspath(_ROOT), env=_env,
                        capture_output=True, text=True, timeout=900)
    def _jload(path):
        if not os.path.isfile(path):
            return None
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    _curve, _bytes = _jload(_lc), _jload(_fbp)
    _printed = re.search(r"^\s+loop\.bytes_scored\s+(\d+)\s*$", _p.stdout, re.M)
    check("S9 run.py --flush-bytes writes one positive int per --loss-curve entry, summing to the "
          "printed loop.bytes_scored",
          _p.returncode == 0 and isinstance(_curve, list) and isinstance(_bytes, list)
          and len(_curve) == len(_bytes) == 6 and all(isinstance(v, float) for v in _curve)
          and all(isinstance(v, int) and v > 0 for v in _bytes) and _printed is not None
          and sum(_bytes) == int(_printed.group(1)),
          f"rc {_p.returncode}; curve {len(_curve or [])}, bytes {_bytes}; printed "
          f"{_printed.group(1) if _printed else None}; {_p.stderr[-200:] if _p.returncode else ''}")
finally:
    shutil.rmtree(TMP9, ignore_errors=True)

# ---- S10: every package's save counter is the lineage's, beside a process twin -------------------
# THE REGISTER'S KNOWN ANSWER (LOW-RESUME-SAVED-COUNTERS): a parent saves k times and its child j
# times, and every package reports (k + j, j). Unfixed, the child read k - 1 + j on LM, SIG, FAB,
# WORLD, MEM and TOK (each copied its ledger before counting the save), k + j on OPT, and j on DOM
# and CAP (their ledgers do not travel). k and j come off each run's own 'CKPT.save: N' line: k is
# the parent's N, the final save included, and j is the child's N - 1, because LOOP_ORDER puts the R
# stage before the final save. LM's tally is process-global, so it is cleared before each System,
# which stands for its own process. No R-stage row prints DATA's counters, so DATA is read in the
# blob, which counts itself and so holds one more than the report on every one of these keys but
# tok.vocab_saved, whose file is written after the blob.
# THE TWIN'S RULE, AFTER BUILD 1.6's REVIEW: a package writes its `_here` twin at its process's
# first save and seeds none, and the R report prints it 0 where saving is on
# (spine/loop.py::_SAVE_COUNTS, from System.saving) and ABSENT where it is off. The review drove the
# split this replaced at j = 0 (the shipped CKPT_EVERY=0) and at saving off; both are checked below.
from lm import api as lm_api                                       # noqa: E402

TMP10 = tempfile.mkdtemp(prefix="s10_saved_")
_S10 = (("LM.counters", "lm.ckpt.saved"), ("OPT.counters", "opt.ckpt.saved"),
        ("SIG.counters", "sig.state_written"), ("FAB.counters", "fab.state_written"),
        ("WORLD(w.counters)", "world.state_written"), ("MEM(store.counters)", "store.n_state_dicts"),
        ("DOM(part.counters)", "part.n_state_dicts"), ("CAP.counters", "cap.state_written"),
        ("TOK(vocab.counters)", "tok.state_written"), ("TOK(vocab.counters)", "tok.vocab_saved"))


def _pairs(res):
    out = {}
    for row, key in _S10:
        r = res.report.get(row)
        r = r if isinstance(r, dict) else {}
        out[key] = (r.get(key, "ABSENT"), r.get(key + "_here", "ABSENT"))
    return out


# THE TEN PACKAGES' LEDGERS, READ OFF THE SYSTEM (LM's is the process-global tally), with DATA's,
# which no R row prints. The twin names are the ten above plus DATA's.
_TWIN_KEYS = frozenset([key + "_here" for _, key in _S10] + ["data.state_written_here"])


def _ledgers(s):
    return {"lm": lm_api._COUNTS, "opt": s.optimizer.counters, "sig": s.sig.counters,
            "fab": s.fabric.counters, "world": s.world.counters, "mem": s.store.counters,
            "dom": s.partition.counters, "cap": s.valve.counters, "tok": s.vocab.counters,
            "data": s.areas.counters}


def _twins_on_ledgers(s):
    return sorted(kk for d in _ledgers(s).values() for kk in d if kk in _TWIN_KEYS)


def _lineage_on_ledgers(s):
    lin = {key for _, key in _S10} | {"data.state_written"}
    return {kk: v for d in _ledgers(s).values() for kk, v in d.items() if kk in lin}


try:
    lm_api._COUNTS.clear()
    p10 = build(CKPT_DIR=TMP10 + "/p", CKPT_EVERY=20)
    rp10 = loop.run(p10, max_windows=60, progress=False)
    k = _saves(rp10)
    lm_api._COUNTS.clear()
    c10 = build(CKPT_RESUME=TMP10 + "/p", CKPT_DIR=TMP10 + "/c", CKPT_EVERY=20)
    rc10 = loop.run(c10, max_windows=40, progress=False)
    j = _saves(rc10) - 1
    pp, pc = _pairs(rp10), _pairs(rc10)
    bad_p = {kk: v for kk, v in pp.items() if v != (k - 1, k - 1)}
    bad_c = {kk: v for kk, v in pc.items() if v != (k + j, j)}
    check(f"S10 setup: the parent saved k >= 2 times and the child j >= 1 times before its report, "
          f"and the ten rows here are the ten spine/loop.py::_SAVE_COUNTS renders",
          k >= 2 and j >= 1 and tuple(_S10) == tuple(loop._SAVE_COUNTS), f"k {k}, j {j}")
    check("S10 a fresh parent's report reads (k - 1, k - 1) on every package: lineage == process, "
          "the final save following the report", not bad_p, f"k {k}; off: {bad_p}")
    check("S10 THE KNOWN ANSWER: the child reports (k + j, j) on every package -- the lineage "
          "count beside this process's", not bad_c, f"k {k}, j {j}; off: {bad_c}")
    blob = torch.load(TMP10 + "/c/ckpt.pt", map_location="cpu", weights_only=False)["payload"]
    held = {"lm.ckpt.saved": blob["LM"]["counters"].get("lm.ckpt.saved"),
            "opt.ckpt.saved": blob["OPT"]["counters"].get("opt.ckpt.saved"),
            "sig.state_written": blob["SIG"]["counters"].get("sig.state_written"),
            "fab.state_written": blob["FAB"]["counters"].get("fab.state_written"),
            "world.state_written": blob["WORLD"]["counters"].get("world.state_written"),
            "store.n_state_dicts": blob["MEM"]["counters"].get("store.n_state_dicts"),
            "tok.state_written": blob["TOK"]["counters"].get("tok.state_written"),
            "DOM n_state_dicts": blob["DOM"].get("n_state_dicts"),
            "CAP state_written": blob["CAP"].get("state_written"),
            "data.state_written": blob["DATA"]["counters"].get("data.state_written")}
    dc = blob["DATA"]["counters"]
    check("S10 the child's final blob counts itself: k + j + 1 on every save count it carries "
          "(DATA's too, with data.state_written_here = j + 1), and tok.vocab_saved k + j, its file "
          "being written after the blob",
          all(v == k + j + 1 for v in held.values())
          and dc.get("data.state_written_here") == j + 1
          and blob["TOK"]["counters"].get("tok.vocab_saved") == k + j,
          f"want {k + j + 1}: {held}; data _here {dc.get('data.state_written_here')}; tok.vocab_saved "
          f"{blob['TOK']['counters'].get('tok.vocab_saved')}")
    # AND A GRANDCHILD READ FROM THAT BLOB RESTORES k + j + 1 -- tok.vocab_saved included, because
    # the vocabulary file it replays records its own ordinal -- with no process twin on any of the
    # ten ledgers: none crosses a resume, and since build 1.6's review no package seeds one either.
    # OPT's build seeded its twin 0 and CAP.counters printed 0 for a missing one, while the other
    # eight read ABSENT, and this check asserted that split as correct. Whether saving is armed is
    # the root's to say (System.saving), so it is the R report that prints it: see j = 0 below.
    lm_api._COUNTS.clear()
    g10 = build(CKPT_RESUME=TMP10 + "/c", CKPT_DIR=TMP10 + "/g", CKPT_EVERY=0)
    gl = {"lm.ckpt.saved": lm_api._COUNTS.get("lm.ckpt.saved"),
          "opt.ckpt.saved": g10.optimizer.counters.get("opt.ckpt.saved"),
          "fab.state_written": g10.fabric.counters.get("fab.state_written"),
          "part.n_state_dicts": g10.partition.counters.get("part.n_state_dicts"),
          "cap.state_written": g10.valve.counters.get("cap.state_written"),
          "tok.vocab_saved": g10.vocab.counters.get("tok.vocab_saved")}
    twins = _twins_on_ledgers(g10)
    check("S10 a resume from the child's blob restores k + j + 1 on every save count, "
          "tok.vocab_saved included, and no process twin is on any package's ledger (none crosses, "
          "none is seeded)",
          all(v == k + j + 1 for v in gl.values()) and not twins,
          f"want {k + j + 1}: {gl}; twins on the ledgers {twins}")
    # THE REGISTER'S ANSWER AT j = 0 (build 1.6's review), the shipped CKPT_EVERY=0's case: the
    # grandchild's one save is the final one, after R, so its report must read (k + j + 1, 0) on
    # every package -- saving armed, nothing saved yet. Unfixed, eight rows printed the twin ABSENT
    # and OPT and CAP printed 0.
    rg10 = loop.run(g10, max_windows=5, progress=False)
    bad_g = {kk: v for kk, v in _pairs(rg10).items() if v != (k + j + 1, 0)}
    check("S10 j = 0: a grandchild at CKPT_EVERY=0 with CKPT_DIR set reports (k + j + 1, 0) on "
          "every package -- saving armed, no save before its report -- and saves once, after it",
          not bad_g and _saves(rg10) == 1,
          f"want ({k + j + 1}, 0); off: {bad_g}; saves {_saves(rg10)}")
    # AND SAVING OFF, ON THE SAME BLOB: CKPT_DIR='' reports (k + j + 1, ABSENT) on every package
    # and ends with every lineage count as restored and no twin on any ledger. The final "save" at
    # saving off built the payload after the report, so every package used to count one save CKPT
    # refused as off; spine/loop.py::_save no longer builds it there.
    lm_api._COUNTS.clear()
    x10 = build(CKPT_RESUME=TMP10 + "/c", CKPT_DIR="")
    rx10 = loop.run(x10, max_windows=5, progress=False)
    bad_x = {kk: v for kk, v in _pairs(rx10).items() if v != (k + j + 1, "ABSENT")}
    xl = _lineage_on_ledgers(x10)
    twins_x = _twins_on_ledgers(x10)
    check("S10 saving off: the same blob resumed with CKPT_DIR='' reports (k + j + 1, ABSENT) on "
          "every package, writes nothing, and ends the run with every lineage count as restored "
          "and no process twin on any ledger (its final save built no payload)",
          not bad_x and _saves(rx10) == 0 and len(xl) == 11
          and all(v == k + j + 1 for v in xl.values())
          and not twins_x,
          f"off: {bad_x}; saves {_saves(rx10)}; ledgers after {xl}; twins {twins_x}")
    # A FRESH RUN AT SAVING OFF, the default and tests/test_baseline.py's workload: every twin
    # ABSENT on every row and every ledger. The lineage keys are the packages' own there: OPT seeds
    # opt.ckpt.saved 0 at build and CAP.counters prints cap.state_written 0, and the baseline
    # fixture pins both, while the other eight print ABSENT -- a residue Q-CKPT-4 states.
    lm_api._COUNTS.clear()
    f10 = build(CKPT_DIR="")
    pf = _pairs(loop.run(f10, max_windows=3, progress=False))
    twin_f = {kk: v[1] for kk, v in pf.items() if v[1] != "ABSENT"}
    lin_f = {kk: v[0] for kk, v in pf.items() if v[0] != "ABSENT"}
    check("S10 saving off on a fresh run: every process twin is ABSENT on every row (OPT's and "
          "CAP's printed 0) and on every ledger after the run; of the lineage keys only OPT's and "
          "CAP's print, at 0",
          not twin_f and not _twins_on_ledgers(f10)
          and lin_f == {"opt.ckpt.saved": 0, "cap.state_written": 0},
          f"twins {twin_f}; lineage printed {lin_f}; twins on the ledgers {_twins_on_ledgers(f10)}")
    # THE LINEAGE'S FIRST SAVE: its blob was written before any vocabulary file, so it carries no
    # tok.vocab_saved at all, and the file the resume replays records ordinal 1. Its own report is
    # the fresh run's j = 0 case: (0, 0) on every package, saving armed and nothing saved.
    lm_api._COUNTS.clear()
    r1 = loop.run(build(CKPT_DIR=TMP10 + "/one", CKPT_EVERY=0), max_windows=5, progress=False)
    bad_1 = {kk: v for kk, v in _pairs(r1).items() if v != (0, 0)}
    check("S10 j = 0 on a fresh run: a saving run whose only save follows its report reads (0, 0) "
          "on every package", not bad_1 and _saves(r1) == 1, f"off: {bad_1}; saves {_saves(r1)}")
    first = torch.load(TMP10 + "/one/ckpt.pt", map_location="cpu", weights_only=False)
    lm_api._COUNTS.clear()
    o10 = build(CKPT_RESUME=TMP10 + "/one", CKPT_DIR=TMP10 + "/one_c", CKPT_EVERY=0)
    check("S10 a resume from a lineage's first save counts the file it read: tok.vocab_saved 1 "
          "from a blob that carries none, beside tok.state_written 1",
          "tok.vocab_saved" not in first["payload"]["TOK"]["counters"]
          and o10.vocab.counters.get("tok.vocab_saved") == 1
          and o10.vocab.counters.get("tok.state_written") == 1,
          f"blob {first['payload']['TOK']['counters'].get('tok.vocab_saved', 'ABSENT')}; restored "
          f"{o10.vocab.counters.get('tok.vocab_saved')}, state_written "
          f"{o10.vocab.counters.get('tok.state_written')}")
    # AT TOK_MODE=bytes (build 1.6's review): that arm replays no merge and read no vocabulary file,
    # so a bytes-mode child restored the blob's tok.vocab_saved, one file short, and read
    # (k + j - 1, j) on it beside (k + j, j) on the other nine. build_vocabulary now reads the
    # parent file's ordinal on that arm too.
    lm_api._COUNTS.clear()
    kb = _saves(loop.run(build(TOK_MODE="bytes", CKPT_DIR=TMP10 + "/bp", CKPT_EVERY=20),
                         max_windows=30, progress=False))
    lm_api._COUNTS.clear()
    rbc = loop.run(build(TOK_MODE="bytes", CKPT_RESUME=TMP10 + "/bp", CKPT_DIR=TMP10 + "/bc",
                         CKPT_EVERY=20), max_windows=30, progress=False)
    jb = _saves(rbc) - 1
    bad_b = {kk: v for kk, v in _pairs(rbc).items() if v != (kb + jb, jb)}
    check("S10 at TOK_MODE=bytes the child reports (k + j, j) on every package, tok.vocab_saved "
          "included (the arm reads the parent file's ordinal, and replays nothing)",
          kb >= 2 and jb >= 1 and not bad_b, f"k {kb}, j {jb}; off: {bad_b}")
    # OWED, PINNED AS IT STANDS (build 1.6's review; docs/04_CONTRACT.md Q-CKPT-4): a save CKPT.save
    # refuses for a non-finite payload is still counted by every package, because the payload, and
    # each count in it, is built before CKPT can scan it. No file is written and the loop warns, but
    # the twins then read one save more than the 'CKPT.save: N' line. A repair makes this check
    # fail, and replaces it.
    lm_api._COUNTS.clear()
    n10 = build(CKPT_DIR=TMP10 + "/nan")
    with torch.no_grad():
        n10.fabric.A.view(-1)[0] = float("nan")
    _n0 = len(loop._save_refused)
    wrote10 = loop._save(n10, n10.clock, "periodic")
    refused10 = loop._save_refused[_n0:]
    del loop._save_refused[_n0:]
    check("S10 OWED, pinned as it stands: a save CKPT refuses as non-finite writes no file and is "
          "recorded as refused, and every package still counts it (fab.state_written_here and "
          "lm.ckpt.saved_here 1)",
          not wrote10 and not os.path.exists(TMP10 + "/nan/ckpt.pt") and len(refused10) == 1
          and n10.fabric.counters.get("fab.state_written_here") == 1
          and lm_api._COUNTS.get("lm.ckpt.saved_here") == 1,
          f"wrote {wrote10}; refused {len(refused10)}; fab twin "
          f"{n10.fabric.counters.get('fab.state_written_here')}, lm twin "
          f"{lm_api._COUNTS.get('lm.ckpt.saved_here')}")
finally:
    shutil.rmtree(TMP10, ignore_errors=True)

# ---- S11: periodic saves change no number, and land on the act windows (Proposal 05 §8 1.5) ------
# THE KNOWN ANSWER REGISTER NOTE retok fleet (1) ASKS FOR. `EXP=retok bash gpu_world.sh` saves the k0
# family every KEEP_EVERY windows while its act arms save only at the end, so arm - k0 is unbiased only
# if a periodic save leaves the run it interrupts bit-identical; and k0's copies kept aside are the
# spike test's maturity-matched control only if they sit on the windows the act arms act at. S4's two
# runs, which never saved, are the references: each is rebuilt with CKPT_EVERY=40, the act cadence. A
# periodic save of period P lands at i x P + 1 and an act of cadence K at j x K + 1, so the ring's
# older generation after 130 windows is the save at 121 -- the last act's window, on both arms -- and
# its vocabulary beside it holds that save's merge count, the pairing gpu_world.sh's index checks.
# (At this base minting starts near window 120, so the act arm acts once, at 121, after the mint.)
TMP11 = tempfile.mkdtemp(prefix="s11_saves_")
try:
    _acts11 = act_windows(r)
    for _tag, _every, _ref in (("act", 40, r), ("k0", 0, r0)):
        _s = build(TOK_GROW_EVERY=30, TOK_RETOK_EVERY=_every, CKPT_DIR=f"{TMP11}/{_tag}", CKPT_EVERY=40)
        _r = loop.run(_s, max_windows=130, progress=False)
        _a_ref, _a = books(_ref).get("loop.acts", "ABSENT"), books(_r).get("loop.acts", "ABSENT")
        _diff = next((i for i, (x, y) in enumerate(zip(_r.loss_curve, _ref.loss_curve)) if x != y), None)
        check(f"S11 {_tag} (TOK_RETOK_EVERY={_every}): saving every 40 windows leaves S4's no-save loss "
              f"curve bit-identical, with the same acts at the same windows",
              len(_r.loss_curve) == len(_ref.loss_curve) == 130 and _diff is None and _a == _a_ref
              and act_windows(_r) == act_windows(_ref) and _saves(_r) == 4,
              f"first differing flush {_diff}; loop.acts {_a} vs {_a_ref}; acts {act_windows(_r)} vs "
              f"{act_windows(_ref)}; saves {_saves(_r)}")
        _prev = torch.load(f"{TMP11}/{_tag}/ckpt.pt.prev", map_location="cpu", weights_only=False)
        _mc = _prev["payload"]["TOK"]["merge_count"]
        _ent = _entries(f"{TMP11}/{_tag}.prev.dyntok.json")
        check(f"S11 {_tag}: the ring's older generation is the periodic save at window 121, the act "
              f"arm's last act ({_acts11[-1] if _acts11 else 'none'}), paired with its own vocabulary",
              len(_acts11) >= 1 and _prev["reason"] == "periodic" and int(_prev["step"]) == 121 == _acts11[-1]
              and _mc == _ent,
              f"reason {_prev['reason']}, step {_prev['step']}; acts {_acts11}; merges {_mc}, entries {_ent}")
    check("S11 every act window of the act arm is a window the k0 arm saved at (i x 40 + 1)",
          bool(_acts11) and all((w - 1) % 40 == 0 and w <= 130 for w in _acts11), f"acts {_acts11}")
finally:
    shutil.rmtree(TMP11, ignore_errors=True)

print(f"\n=== {len(FAILS)} failing ===")
sys.exit(1 if FAILS else 0)
