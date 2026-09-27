"""DOM'S HALF OF LEVELS (Proposal 05 §8 1.2, register TREE-S0b-LEVELS and C12; docs/04_CONTRACT.md
Q-DOM-5): the unit DOM's competence book is folded in, driven through the real composition root and loop
with real on-disk checkpoints written under a temporary directory.

    python3 tests/test_levels.py        # exit 0 = every check passed

WHY IT EXISTS. DOM.note_competence folded each window's mean cross-entropy / ln 2 -- a level PER TOKEN.
A mid-epoch act re-spells the unconsumed tail in longer tokens, so the same text costs more bits per
token after it than before, and every domain's EMA shifted at every act by the act's bytes-per-token
ratio; the cull's competence spare, the book's one consumer, read that as a change in competence.
DOM_LEVELS (default on) has the root hand bits per BUILD-TIME token instead: the per-token bits x
Vocabulary.bytes_per_token / the window's own bytes per token, the window's bytes off
Segmentation.byte_pos (spine/loop.py::_build_token_scale). OFF is today's per-token unit, bit for bit.
Each check below pins one known answer of that unit, or the plumbing that carries it.

  L1  IDENTITY, the arithmetic: at a window whose bytes per token equals the build-time value the
      factor is exactly 1.0, and ON's bits equal OFF's to the bit, over 10,000 seeded readings and five
      geometries (one non-dyadic), on both branches of the window's byte count (inside the
      segmentation and at the stream's end).
  L2  IDENTITY, end to end: at TOK_MODE=bytes (build-time and every window's bytes per token are 1.0)
      a DOM_LEVELS=1 run and a DOM_LEVELS=0 run hand DOM the same bits to the bit, with manage passes
      and the competence spare reachable, and end with the same loss curve, the same books and the
      same part.* counters; loop.levels_rescaled is PRESENT-and-0 on the ON arm (armed, never
      rescaled) and ABSENT on the OFF arm.
  L3  CROSS-ACT, the unit, on a real segmentation: a bytes-only stream spliced at the build table
      (the act's own TOK.splice), scored by an oracle whose per-token loss is c x the token's byte
      length. spine/loop.py::_window_bytes equals the targets' byte lengths on every window; the
      converted level is c x bpt_build / ln 2 on every window before and after the splice, while the
      per-token level jumps by the splice's bytes-per-token ratio.
  L4  CROSS-ACT, through the real act: the same oracle standing in for LM.lm_loss's per-window
      return in a run with mint bursts and mid-epoch acts. ON: every reading DOM is handed is
      c x bpt_build / ln 2 across the whole run, and loop.levels_rescaled counts. OFF: each reading
      is the oracle's mean / ln 2 exactly, and they vary.
  L5  THE UNIT REACHES DOM AND IS ACCOUNTED, the real model: at DOM_LEVELS=1 each handed reading is
      the per-token bits x bpt_build / the window's bytes per token, the window's bytes counted here
      off Vocabulary.id2bytes; converting every reading back to bytes sums to loop.bytes_scored, the
      root's independent count; at OPT_BATCH_WINDOWS=2 each row of a flush is rescaled by its own
      window's bytes. At DOM_LEVELS=0 each reading is float(nats) / ln 2 exactly.
  L6  THE RESUME STAMP: DOM.state_dict writes `comp_unit` ('token' off, 'build_token' on); a resume
      into the other unit counts part.n_comp_unit_changed 1 and the root warns before the first
      window; the same unit counts 0 with no warning; a fresh partition has no key; a blob older
      than the stamp reads as the per-token unit.
  L7  RESUME EXACTNESS OF THE CONVERTED BOOK: at the default ON, across mint bursts and acts, a run
      saved and resumed ends with the uninterrupted run's comp and comp_glob to the bit, because
      the build-time bytes per token crosses the resume in the vocabulary file (tok.bpt_adopted).

WHAT THIS FILE CANNOT SEE: whether Levels help. Competence is a control signal; whether the converted
unit improves domain management is read on GPU (Proposal 05 U-series family (h), S5 (iii)), and an
adverse reading there returns the lever to OFF. Everything here is an operation check.
"""
import math
import os
import random
import struct
import sys
import tempfile

_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(_ROOT, "src"))

import torch                                                       # noqa: E402
torch.set_num_threads(1)

from spine import lever as _lever                                  # noqa: E402
from spine import rng                                              # noqa: E402
from spine import loop                                             # noqa: E402
from spine import derive                                           # noqa: E402
from spine.compose import compose                                  # noqa: E402
from tok import api as tok_api                                     # noqa: E402
from lm import api as lm_api                                       # noqa: E402
from domains import api as dom_api                                 # noqa: E402

FAILS = []
# The resume tests' small base (tests/test_continuation.py's): a tenth-size fabric keeps each compose
# to a few seconds.
BASE = {"DATA_STREAM_BYTES": "60000", "SIG_WARMUP": "20", "FAB_N0": "256", "FAB_SLOTS": "512"}
# THE MANAGE PASS AND THE SPARE MADE REACHABLE in a short run: DOM.manage runs every 100 windows and
# its cull only examines domains past DOM_GRACE and stale past DOM_CULL_STALE, both 500 by default.
REACH = {"DOM_GRACE": 50, "DOM_CULL_STALE": 50, "DOM_CULL_FRAC": 0.5}
LN2 = math.log(2.0)


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
    b = res.report.get("LOOP(flush books)")
    return b if isinstance(b, dict) else {}


def bits_of(x):
    """A float's exact IEEE bytes: `==` alone would call -0.0 and 0.0 the same reading."""
    return struct.pack("<d", float(x))


def part_counters(s):
    return {k: v for k, v in s.partition.counters.items() if k.startswith("part.")}


class _Patch:
    """Replace one module attribute for the duration of a `with`, and put it back in finally."""

    def __init__(self, mod, name, fn):
        self.mod, self.name, self.fn = mod, name, fn

    def __enter__(self):
        self.orig = getattr(self.mod, self.name)
        setattr(self.mod, self.name, self.fn)
        return self

    def __exit__(self, *exc):
        setattr(self.mod, self.name, self.orig)
        return False


def spy_competence(log):
    """DOM.note_competence, recording each (did, bits) it is handed and then folding it as usual."""
    real = dom_api.note_competence

    def spy(dom, part, *, did, bits):
        log.append((int(did), float(bits)))
        return real(dom, part, did=did, bits=bits)
    return _Patch(dom_api, "note_competence", spy)


def spy_loss(log, oracle=None):
    """LM.lm_loss, recording each flush's per-window return. With `oracle`, the per-window return is
    replaced by oracle(y) and the mean -- the objective's summand -- stays the model's, so the run
    still trains and steps exactly as the tree would."""
    real = lm_api.lm_loss

    def spy(lm, logits, y):
        pw, mean = real(lm, logits, y)
        if oracle is not None:
            pw = oracle(y)
        log.append(pw.detach().float().reshape(-1).tolist())
        return pw, mean
    return _Patch(lm_api, "lm_loss", spy)


def target_bytes(vocab, ids, bounds):
    """The bytes a window's targets decode to, off Vocabulary.id2bytes -- counted apart from
    Segmentation.byte_pos, which is what spine/loop.py::_window_bytes reads."""
    a, b = bounds
    return sum(len(vocab.id2bytes[t]) for t in ids[a + 1:b])


def rel(x, y):
    return abs(x - y) / max(abs(y), 1e-300)


# ---- L1: identity, the arithmetic ------------------------------------------------------------------
_r = random.Random(0)
_nats = [_r.uniform(0.0, 12.0) for _ in range(10000)]
# (tokens in window, bytes in window, bpt_build). The last one is non-dyadic: 171/128 is not a short
# binary fraction, and bpt_build is the tree's own estimator's value for it.
_geoms = [(128, 128, 1.0), (128, 160, 1.25), (128, 192, 1.5), (64, 224, 3.5),
          (128, 171, derive.bytes_per_token(171, 128))]
_bad = []
for _t, _nb, _bpt in _geoms:
    # Inside the segmentation: b < len(byte_pos), so the window ends at byte_pos[b].
    _bp_in = [0] * (_t + 3)
    _bp_in[1], _bp_in[_t + 1] = 7, 7 + _nb
    # At the stream's end: b == len(byte_pos), so the window ends at n_bytes.
    _bp_end = [0] * (_t + 1)
    _bp_end[1] = 7
    for _bp, _n in ((_bp_in, 10 ** 6), (_bp_end, 7 + _nb)):
        _bounds = (0, _t + 1)
        _wb = loop._window_bytes(_bp, _n, _bounds)
        _s = loop._build_token_scale(_bounds, _bp, _n, _bpt)
        if _wb != _nb or _s != 1.0:
            _bad.append((_t, _nb, _bpt, _wb, _s))
            continue
        _bad += [(_t, _nb, x) for x in _nats if bits_of((x / LN2) * _s) != bits_of(x / LN2)]
check("L1 identity: at bytes per token == bpt_build the factor is exactly 1.0 and ON's bits equal "
      "OFF's to the bit (10,000 readings x 5 geometries x both byte-count branches)",
      not _bad, f"{len(_bad)} mismatches, first {_bad[:2]}")
_s = loop._build_token_scale((0, 129), [0, 0] + [0] * 127 + [192, 0], 10 ** 6, 1.4971)
check("L1 ... and away from it the factor is bpt_build over the window's bytes per token",
      _s == 1.4971 / 1.5, f"{_s!r} vs {1.4971 / 1.5!r}")

# ---- L2: identity, end to end, at TOK_MODE=bytes --------------------------------------------------
_L2 = dict(TOK_MODE="bytes", **REACH)
_arms = {}
for _lv in (1, 0):
    _log = []
    _s2 = build(DOM_LEVELS=_lv, **_L2)
    with spy_competence(_log):
        _res = loop.run(_s2, max_windows=300, progress=False)
    _arms[_lv] = (_s2, _res, _log)
(_s_on, _r_on, _c_on), (_s_off, _r_off, _c_off) = _arms[1], _arms[0]
check("L2 setup: at TOK_MODE=bytes the build-time bytes per token is 1.0 and the manage pass and its "
      "competence spare were reached (so a differing reading could have moved a decision)",
      float(_s_on.vocab.bytes_per_token) == 1.0
      and int(_s_on.partition.counters.get("part.n_manage_passes", 0)) >= 2
      and "part.n_spared_by_competence" in _s_on.partition.counters,
      f"bpt {_s_on.vocab.bytes_per_token}, passes "
      f"{_s_on.partition.counters.get('part.n_manage_passes')}, spared "
      f"{_s_on.partition.counters.get('part.n_spared_by_competence')}, culled "
      f"{_s_on.partition.counters.get('part.n_culled')}")
check("L2 identity end to end: every reading DOM is handed is bit-identical across DOM_LEVELS=1 and 0",
      len(_c_on) == len(_c_off) == 300
      and all(a[0] == b[0] and bits_of(a[1]) == bits_of(b[1]) for a, b in zip(_c_on, _c_off)),
      f"{len(_c_on)} vs {len(_c_off)} readings")
_bk_on, _bk_off = dict(books(_r_on)), dict(books(_r_off))
check("L2 ... so the loss curve, comp, comp_glob, the books and every part.* counter are equal",
      tuple(_r_on.loss_curve) == tuple(_r_off.loss_curve)
      and {k: bits_of(v) for k, v in _s_on.partition.comp.items()}
      == {k: bits_of(v) for k, v in _s_off.partition.comp.items()}
      and bits_of(_s_on.partition.comp_glob) == bits_of(_s_off.partition.comp_glob)
      and part_counters(_s_on) == part_counters(_s_off)
      and {k: v for k, v in _bk_on.items() if k != "loop.levels_rescaled"} == _bk_off,
      f"comp_glob {_s_on.partition.comp_glob!r} vs {_s_off.partition.comp_glob!r}")
check("L2 loop.levels_rescaled is PRESENT-and-0 at DOM_LEVELS=1 (armed, no window rescaled) and "
      "ABSENT at DOM_LEVELS=0 (unreachable)",
      _bk_on.get("loop.levels_rescaled") == 0 and "loop.levels_rescaled" not in _bk_off,
      f"on {_bk_on.get('loop.levels_rescaled', 'ABSENT')}, off "
      f"{_bk_off.get('loop.levels_rescaled', 'ABSENT')}")

# ---- L3: cross-act, the unit, on a real segmentation ----------------------------------------------
C = 0.5          # the oracle's nats per BYTE: a model equally good at every byte of the text
s3 = build()
_tok, _v3, _data = s3.configs["TOK"], s3.vocab, s3.stream.bytes
ctx = int(s3.configs["LM"].ctx)
_bpt3 = float(_v3.bytes_per_token)
_seg0 = tok_api.tokenize(_tok, _v3, _data, s3.stream.labels, view=(256, ()))
_at = 10 * ctx
_seg1 = tok_api.splice(_tok, _v3, _seg0, _data, s3.stream.labels, at=_at)
_rows = []
for _i in range(30):
    _bd = loop._window_bounds(_seg1.ids, _i, ctx)
    _tb = target_bytes(_v3, _seg1.ids, _bd)
    _wb = loop._window_bytes(_seg1.byte_pos, len(_data), _bd)
    _mean = C * _tb / ctx                       # the oracle's per-window mean, in nats per token
    _per_token = _mean / LN2
    _conv = _per_token * loop._build_token_scale(_bd, _seg1.byte_pos, len(_data), _bpt3)
    _rows.append((_i, _tb, _wb, _per_token, _conv))
check("L3 setup: the stream before the splice is all bytes and after it is spelled in the build table",
      all(r[1] == ctx for r in _rows[:10]) and all(r[1] > ctx for r in _rows[10:]),
      f"target bytes {[r[1] for r in _rows[8:13]]} around window 10")
check("L3 spine/loop.py::_window_bytes is the bytes the window's targets decode to, on every window",
      all(r[1] == r[2] for r in _rows), str([(r[0], r[1], r[2]) for r in _rows if r[1] != r[2]][:3]))
_want3 = C * _bpt3 / LN2
_dev = max(rel(r[4], _want3) for r in _rows)
_pre = sum(r[3] for r in _rows[:10]) / 10
_post = sum(r[3] for r in _rows[10:]) / len(_rows[10:])
check("L3 cross-act: the converted level is c x bpt_build / ln 2 on every window before and after the "
      "splice (continuous), while the per-token level jumps by the splice's bytes per token",
      _dev < 1e-12 and _post / _pre >= 1.3,
      f"max rel deviation {_dev:.3g}; per-token post/pre {_post / _pre:.4f}; bpt_build {_bpt3:.4f}")

# ---- L4: cross-act, through the real act ----------------------------------------------------------
_L4 = dict(TOK_GROW_EVERY=20, TOK_RETOK_EVERY=50)


def _oracle_for(s):
    def oracle(y):
        lens = torch.tensor([len(b) for b in s.vocab.id2bytes], dtype=torch.float32)
        # c x (the targets' bytes / ctx): exact in float32, since the sum is a small integer and
        # ctx is a power of two -- so the reading the loop takes with .float() is the oracle's own.
        return C * lens[y.detach().cpu()].mean(-1)
    return oracle


_l4 = {}
for _lv in (1, 0):
    _cl, _ll = [], []
    _s4 = build(DOM_LEVELS=_lv, **_L4)
    with spy_competence(_cl), spy_loss(_ll, oracle=_oracle_for(_s4)):
        _r4 = loop.run(_s4, max_windows=400, progress=False)
    _l4[_lv] = (_s4, _r4, _cl, [x for f in _ll for x in f])
_s4, _r4, _c4, _p4 = _l4[1]
_want4 = C * float(_s4.vocab.bytes_per_token) / LN2
_dev4 = max(rel(b, _want4) for _, b in _c4) if _c4 else float("inf")
check("L4 setup: the ON run minted and acted mid-epoch, and loop.levels_rescaled counted",
      int(books(_r4).get("loop.acts", 0)) >= 1
      and int(_s4.vocab.counters.get("tok.retok_mid_epoch", 0)) >= 1
      and int(books(_r4).get("loop.levels_rescaled", 0)) > 0,
      f"acts {books(_r4).get('loop.acts')}, retok_mid_epoch "
      f"{_s4.vocab.counters.get('tok.retok_mid_epoch')}, rescaled "
      f"{books(_r4).get('loop.levels_rescaled')} of {len(_c4)}")
check("L4 cross-act ON: every reading DOM is handed across the run and its acts is c x bpt_build / ln 2",
      len(_c4) == int(_r4.windows) and _dev4 < 1e-12,
      f"{len(_c4)} readings, max rel deviation {_dev4:.3g}")
_s4o, _r4o, _c4o, _p4o = _l4[0]
_b4o = [b for _, b in _c4o]
check("L4 cross-act OFF: each reading is the oracle's mean / ln 2 exactly, and the per-token level "
      "moves (it is what ON removes)",
      len(_b4o) == len(_p4o) > 0
      and all(bits_of(b) == bits_of(float(p) / LN2) for b, p in zip(_b4o, _p4o))
      and max(_b4o) / min(_b4o) >= 1.05 and int(books(_r4o).get("loop.acts", 0)) >= 1
      and "loop.levels_rescaled" not in books(_r4o),
      f"{len(_b4o)} readings, max/min {max(_b4o) / min(_b4o):.4f}")

# ---- L5: the unit reaches DOM and is accounted, the real model ------------------------------------
_l5 = {}
for _lv in (1, 0):
    _cl, _ll = [], []
    _s5 = build(DOM_LEVELS=_lv)
    with spy_competence(_cl), spy_loss(_ll):
        _r5 = loop.run(_s5, max_windows=150, progress=False)
    _l5[_lv] = (_s5, _r5, _cl, [x for f in _ll for x in f])
_s5, _r5, _c5, _p5 = _l5[1]
_bpt5 = float(_s5.vocab.bytes_per_token)
_ids5 = _s5.segmentation.ids
_dev5 = []
for _i, ((_, _b), _n) in enumerate(zip(_c5, _p5)):
    _tb = target_bytes(_s5.vocab, _ids5, loop._window_bounds(_ids5, _i, ctx))
    _dev5.append(rel(_b / (_n / LN2), _bpt5 * ctx / _tb))
_back = sum(ctx * _bpt5 * ((_n / LN2) / _b) for (_, _b), _n in zip(_c5, _p5))
_scored = int(books(_r5)["loop.bytes_scored"])
check("L5 setup: no act in this run, so the final segmentation is the one every window was cut from",
      "loop.acts" not in books(_r5) or int(books(_r5)["loop.acts"]) == 0, str(books(_r5)))
check("L5 at DOM_LEVELS=1 each reading DOM is handed is the per-token bits x bpt_build / the window's "
      "own bytes per token (bytes counted off Vocabulary.id2bytes)",
      len(_c5) == len(_p5) == 150 and max(_dev5) < 1e-12, f"max rel deviation {max(_dev5):.3g}")
check("L5 ... and turning every reading back into bytes sums to loop.bytes_scored, the root's own count",
      rel(_back, _scored) < 1e-9, f"{_back:.6f} vs {_scored}")
_s5o, _r5o, _c5o, _p5o = _l5[0]
check("L5 at DOM_LEVELS=0 each reading is float(nats) / ln 2 exactly (the unit before 2026-09-26) and "
      "loop.levels_rescaled is ABSENT",
      len(_c5o) == len(_p5o) == 150
      and all(bits_of(b) == bits_of(float(n) / math.log(2.0)) for (_, b), n in zip(_c5o, _p5o))
      and "loop.levels_rescaled" not in books(_r5o), f"{len(_c5o)} readings")
# SEVERAL WINDOWS PER FLUSH: row k of the flush's per-window loss must be rescaled by window k's bytes.
# The sum above cannot see a misalignment (it is a permutation of the same bytes); the per-window
# comparison can, and at OPT_BATCH_WINDOWS=2 the readings still arrive in window order.
_cl, _ll = [], []
_s5b = build(OPT_BATCH_WINDOWS=2)
with spy_competence(_cl), spy_loss(_ll):
    _r5b = loop.run(_s5b, max_windows=150, progress=False)
_p5b = [x for f in _ll for x in f]
_ids5b, _bpt5b = _s5b.segmentation.ids, float(_s5b.vocab.bytes_per_token)
_dev5b = [rel(_b / (_n / LN2), _bpt5b * ctx
              / target_bytes(_s5b.vocab, _ids5b, loop._window_bounds(_ids5b, _i, ctx)))
          for _i, ((_, _b), _n) in enumerate(zip(_cl, _p5b))]
check("L5 at OPT_BATCH_WINDOWS=2 each window's reading is rescaled by that window's own bytes",
      len(_cl) == len(_p5b) == 150 and max(_dev5b) < 1e-12,
      f"{len(_cl)} readings, max rel deviation {max(_dev5b) if _dev5b else float('nan'):.3g}")
check("L5 the report names the unit beside comp_glob",
      _r5.report["DOM.census"].get("comp_unit", "").startswith("bits per build-time token")
      and _r5o.report["DOM.census"].get("comp_unit", "").startswith("bits per token")
      and _r5.report["DOM.census"].get("comp_glob") is not None,
      f"{_r5.report['DOM.census'].get('comp_unit')!r} / {_r5o.report['DOM.census'].get('comp_unit')!r}")

# ---- L6: the resume stamp -------------------------------------------------------------------------
TMP = tempfile.mkdtemp(prefix="levels_")
_warned = lambda s: [w for w in s.warnings if w.startswith("DOM_LEVELS=") and "Q-DOM-5" in w]  # noqa: E731
for _plv, _tag, _unit in ((0, "p_off", "token"), (1, "p_on", "build_token")):
    _p = build(DOM_LEVELS=_plv, CKPT_DIR=os.path.join(TMP, _tag))
    loop.run(_p, max_windows=120, progress=False)
    _blob = torch.load(os.path.join(TMP, _tag, "ckpt.pt"), map_location="cpu",
                       weights_only=False)["payload"]["DOM"]
    check(f"L6 DOM.state_dict stamps comp_unit={_unit!r} at DOM_LEVELS={_plv}, beside a book holding a "
          f"reading", _blob.get("comp_unit") == _unit and _blob.get("comp_glob") is not None,
          f"{_blob.get('comp_unit')!r}, comp_glob {_blob.get('comp_glob')!r}")
    for _clv in (1, 0):
        _c = build(DOM_LEVELS=_clv, CKPT_RESUME=os.path.join(TMP, _tag),
                   CKPT_DIR=os.path.join(TMP, f"{_tag}_c{_clv}"))
        _chg = _c.partition.counters.get("part.n_comp_unit_changed", "ABSENT")
        _want = int(_clv != _plv)
        check(f"L6 a DOM_LEVELS={_plv} parent resumed at DOM_LEVELS={_clv}: part.n_comp_unit_changed "
              f"{_want}, and the root {'warns' if _want else 'says nothing'} before the first window",
              _chg == _want and len(_warned(_c)) == _want,
              f"counter {_chg}; warnings {[w[:90] for w in _warned(_c)]}")
_fresh = build()
check("L6 a fresh partition carries no part.n_comp_unit_changed (ABSENT: nothing was restored)",
      "part.n_comp_unit_changed" not in _fresh.partition.counters)
_legacy = {k: v for k, v in _blob.items() if k != "comp_unit"}
_sd = dict(sig_dim=int(_fresh.configs["SIG"].d), vocab_slots=int(_fresh.configs["LM"].vocab_slots),
           device=torch.device("cpu"), rng=_fresh.streams["domains"])
_pl_on = dom_api.open_partition(_fresh.configs["DOM"], restored=_legacy, **_sd)
_s_off6 = build(DOM_LEVELS=0)
_pl_off = dom_api.open_partition(_s_off6.configs["DOM"], restored=_legacy, **_sd)
_empty = dict(_legacy, comp_glob=None)
_pl_empty = dom_api.open_partition(_fresh.configs["DOM"], restored=_empty, **_sd)
check("L6 a blob older than the stamp reads as the per-token unit: 1 under DOM_LEVELS=1, 0 under "
      "DOM_LEVELS=0; a restored book with no reading has nothing to mix and reads 0",
      _pl_on.counters.get("part.n_comp_unit_changed") == 1
      and _pl_off.counters.get("part.n_comp_unit_changed") == 0
      and _pl_empty.counters.get("part.n_comp_unit_changed") == 0,
      f"on {_pl_on.counters.get('part.n_comp_unit_changed')}, off "
      f"{_pl_off.counters.get('part.n_comp_unit_changed')}, empty "
      f"{_pl_empty.counters.get('part.n_comp_unit_changed')}")
check("L6 the book is kept, not converted or dropped: the restored comp_glob is the parent's",
      _pl_on.comp_glob == _blob["comp_glob"], f"{_pl_on.comp_glob!r} vs {_blob['comp_glob']!r}")

# ---- L7: resume exactness of the converted book ---------------------------------------------------
_L7 = dict(TOK_GROW_EVERY=30, TOK_RETOK_EVERY=40)
_n1, _n2 = 135, 25
_u = build(**_L7)
_ru = loop.run(_u, max_windows=_n1 + _n2, progress=False)
_p7 = build(CKPT_DIR=os.path.join(TMP, "l7p"), **_L7)
_rp = loop.run(_p7, max_windows=_n1, progress=False)
_c7 = build(CKPT_RESUME=os.path.join(TMP, "l7p"), CKPT_DIR=os.path.join(TMP, "l7c"), **_L7)
_rc = loop.run(_c7, max_windows=_n2, progress=False)
check("L7 setup: the parent acted before its save and the build-time bytes per token crossed the resume "
      "(tok.bpt_adopted 1, the same value)",
      int(books(_rp).get("loop.acts", 0)) >= 1
      and int(_c7.vocab.counters.get("tok.bpt_adopted", 0)) == 1
      and bits_of(_c7.vocab.bytes_per_token) == bits_of(_p7.vocab.bytes_per_token)
      and int(books(_rc).get("loop.levels_rescaled", 0)) > 0,
      f"acts {books(_rp).get('loop.acts')}, adopted {_c7.vocab.counters.get('tok.bpt_adopted')}, "
      f"bpt {_c7.vocab.bytes_per_token!r} vs {_p7.vocab.bytes_per_token!r}")
check("L7 the resumed run ends with the uninterrupted run's comp and comp_glob to the bit, and its losses",
      {k: bits_of(v) for k, v in _c7.partition.comp.items()}
      == {k: bits_of(v) for k, v in _u.partition.comp.items()}
      and bits_of(_c7.partition.comp_glob) == bits_of(_u.partition.comp_glob)
      and tuple(_rc.loss_curve[:_n2]) == tuple(_ru.loss_curve[_n1:_n1 + _n2])
      and _c7.partition.counters.get("part.n_comp_unit_changed") == 0,
      f"comp_glob {_c7.partition.comp_glob!r} vs {_u.partition.comp_glob!r}")

print(f"=== {len(FAILS)} failure(s)")
sys.exit(1 if FAILS else 0)
