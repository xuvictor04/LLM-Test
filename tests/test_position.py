"""THE POSITION LEVER, THE DECLARED CONTEXT WIDENING AND THE DESIGNATION IT GATES (register §8 3.6; O17,
NEW-13, C43; docs/04_CONTRACT.md Q-LM-15), driven through the real composition root and loop, with real
on-disk checkpoints written under a temporary directory.

    python3 tests/test_position.py        # exit 0 = every check passed

WHY IT EXISTS. Both LM arms add a learned row per position before the arch branch, so a model trained
with the table is locked to its context, and O17 rules that no checkpoint is designated B's long-lived
parent until a context-widening route PASSes on GPU. §8 3.6 builds the routes that §8 5.8 will read --
an extrapolating value per arm (LM_POS), 'learned''s row-append widening at a declared resume boundary
(LM_CTX_WIDEN) -- and the refusal, and asks for operation only: "the row-append widening's identity
known answer (loss unchanged to 1e-6 on windows at the old ctx) and the cadence-rescaling known answer;
both extrapolating values ... build, run finite and resume exactly; the long-lived-parent designation
is refused by name without a passing route, and its switch works".

  Q1  THE IDENTITY, ON BOTH ARMS WITH FAB, SIG AND MEM ON: a parent at LM_CTX=64 stopped at its epoch
      boundary, and a child resumed from it at LM_CTX=128 LM_CTX_WIDEN=1, give the same LM-level loss
      on windows of 64 tokens or fewer -- bitwise on CPU, and so within 1e-6 -- because the child's
      position table is the parent's 64 rows plus 64 at the initialisation a fresh 128 build draws.
      SIG keeps the parent's width, the child's start read (both closures, through SIG, DOM, FAB and
      MEM) is the unwidened boundary resume's window for window, OPT pads the one widened tensor's
      moments, WORLD reports the width it runs at, lm.ckpt.ctx_widened reads 1 (ABSENT on the
      unwidened child), the child trains at 128, and the startup notice lists every Windows-unit lever
      with its rescaled value.
  Q2  THE REFUSALS: a larger LM_CTX without the lever, and a smaller one with it, at the geometry gate
      by name; a widening across a continuing mid-epoch resume at the `segment` stage, by name. A
      continuing resume at LM_CTX_WIDEN=1 that widens nothing continues exactly, lm.ckpt.ctx_widened
      PRESENT and 0. LM.load_state's own two answers, driven directly: refused naming the lever at 0,
      fitted by prefix at 1 -- and beside a vocabulary widening, alone at 0 and together at 1.
  Q3  THE CADENCE-RESCALING KNOWN ANSWER, spine/derive.py::windows_at_ctx: at 64 -> 128, 1000 -> 500,
      333 -> 167, 1 -> 1 and 0 -> 0; a negative period, a non-Windows period and a width that is not a
      positive int are refused.
  Q4  THE EXTRAPOLATING VALUES: LM_ARCH=transformer LM_POS='alibi' and LM_ARCH=gru LM_POS='none' build
      with no position table, run 120 windows finite, and a continuing resume at 60 reproduces the
      uninterrupted run's last 60 losses exactly. ALiBi's slopes are the paper's, its mask is the
      distance bias with the causal cut, a later token changes no earlier position's hidden state, and
      lm.pos.alibi_applied counts every encode call on that arm and is ABSENT on the others.
  Q5  THE SCHEME ACROSS A RESUME: 'alibi' on the GRU and 'none' on the transformer are refused by name
      at LM.resolve; a checkpoint written at 'learned' is refused by name at LM_POS='none'; a checkpoint
      whose LM geometry carries no scheme (every one written before the lever) resumes as 'learned' and
      continues exactly, and is refused by name at any other scheme.
  Q6  THE DESIGNATION: LM.parent_designation refuses 'learned', 'alibi' and 'none' by name while
      PASSED_WIDENING_ROUTES is empty; with REFUSE_CONTEXT_LOCKED_PARENT off it admits and says the
      refusal was off; a route entered as passed admits that (arch, pos) and no other. The tool,
      tools/designate_parent.py, exits 2 on the refusal and writes nothing, exits 1 on a path with no
      checkpoint, and on an admission writes one record saying which switch admitted it.
  Q7  'learned' IS THE TREE BEFORE THE LEVER: tests/test_baseline.py's B1 reproduces its fixture, and a
      checkpoint written by the tree before LM_POS existed (494936d, run from a clean copy of its src/)
      trains the same first 30 losses as this tree and continues here exactly. UNVERIFIABLE -- printed,
      not failed -- where that commit is not in the repository.

WHAT THIS FILE CANNOT SEE: whether any of it works. CPU runs establish operation only: which scheme a
long-lived parent should carry, and whether a widened parent learns its new positions without losing
its old ones, are §8 5.8's GPU readings, and nothing here enters a route in PASSED_WIDENING_ROUTES.
"""
import contextlib
import dataclasses
import io
import json
import math
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile

_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(_ROOT, "src"))
sys.path.insert(0, os.path.join(_ROOT, "tools"))

import torch                                                       # noqa: E402
torch.set_num_threads(1)

from spine import lever as _lever                                  # noqa: E402
from spine import rng                                              # noqa: E402
from spine import loop                                             # noqa: E402
from spine import assemble                                         # noqa: E402
from spine import derive                                           # noqa: E402
from spine import units as U                                       # noqa: E402
from spine.compose import compose, RefusedRun, _windows_in_epoch   # noqa: E402
from ckpt import api as ckpt_api                                   # noqa: E402
from lm import api as lm_api                                       # noqa: E402
import designate_parent as dp                                      # noqa: E402

FAILS = []
# tests/test_continuation.py's small base: a tenth-size fabric keeps each compose to a few seconds.
BASE = {"DATA_STREAM_BYTES": "60000", "SIG_WARMUP": "20", "FAB_N0": "256", "FAB_SLOTS": "512"}
# THE WIDENING WORKLOAD: a short two-epoch stream at LM_CTX=64 with the retention probe armed, so a
# parent stops at its epoch boundary with pinned windows its children re-pin. At 20000 bytes each area
# is generated at 10,000 and 30% holds out 3,000, whose halves hold a 65-byte window behind its prefix.
E1 = {"DATA_STREAM_BYTES": "20000", "RUN_EPOCHS": "2", "DATA_RESAMPLE": "1", "DATA_SYNTH_HOLDOUT": "1",
      "DATA_HOLDOUT_FRAC": "0.3", "EVAL_RETENTION_EVERY": "20", "EVAL_GENERATE": "0", "LM_CTX": "64"}
# THE TREE BEFORE THE LEVER: register §8 3.5's review, the commit this build was made on.
PRE_LEVER = "494936d"
TMP = tempfile.mkdtemp(prefix="position_")


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" -- {detail}" if detail else ""), flush=True)
    if not ok:
        FAILS.append(name)


def build(restored=None, **env):
    """A System under BASE + `env`, built as a fresh run.py process builds one: the issued streams
    forgotten and LM's process-lifetime tally emptied, so a checkpoint carries this lineage's."""
    _lever._reopen_assembly()
    rng.reset_issued()
    lm_api._COUNTS.clear()
    e = dict(BASE)
    e.update({k: str(v) for k, v in env.items()})
    return compose(environ=e, restored=restored)


def configs(**env):
    _lever._reopen_assembly()
    rng.reset_issued()
    e = dict(BASE)
    e.update({k: str(v) for k, v in env.items()})
    return assemble.build(environ=e)[0]


@contextlib.contextmanager
def spy_readings():
    """Every HoldoutReading EVAL.holdout_probe returns to the loop, in RunResult.probe_series order."""
    got = []
    real = loop.eval_api.holdout_probe

    def spy(ev, **kw):
        rd = real(ev, **kw)
        got.append(rd)
        return rd
    loop.eval_api.holdout_probe = spy
    try:
        yield got
    finally:
        loop.eval_api.holdout_probe = real


def per_window(rd):
    """{area: (control values, report values)} of one HoldoutReading."""
    return {a: (list(row.get("control") or ()), list(row.get("report") or ()))
            for a, row in rd.areas.items()}


def lm_level(sysm, x, y):
    """LM.lm_loss's per-window losses of LM.decode(LM.encode(x)) against y, the model in eval mode
    under no_grad and put back after: the language model alone, nothing routed through it."""
    cfg, m = sysm.configs["LM"], sysm.model
    was = m.training
    m.eval()
    try:
        with torch.no_grad():
            h = lm_api.encode(cfg, m, x)
            logits = lm_api.decode(cfg, m, h, live_vocab=int(sysm.vocab.size()),
                                   retired_ids=tuple(sysm.vocab.retired))
            per_window_loss, _mean = lm_api.lm_loss(cfg, logits, y)
    finally:
        m.train(was)
    return per_window_loss


def refusal_text(fn):
    """(exception type name, message) of what fn() raised, or (None, '') when it returned."""
    try:
        fn()
    except RefusedRun as e:
        return "RefusedRun", " || ".join(e.refusals) + f" [stage={e.stage}]"
    except Exception as e:                                          # noqa: BLE001 -- inspected below
        return type(e).__name__, str(e)
    return None, ""


def windows_levers(cfgs):
    """{env name: value} of every lever declared in units.Windows, off the declarations."""
    out = {}
    for pfx, cfg in cfgs.items():
        wired = set(cfg.wired())
        for field in cfg.keys():
            if field not in wired and cfg.lever(field).unit is U.Windows:
                out[cfg.lever(field).env_name] = int(getattr(cfg, field))
    return out


try:
    # =============================================================================================
    # Q3: the cadence-rescaling known answer (pure; first, because the rest reads it)
    # =============================================================================================
    grid = [(1000, 500), (333, 167), (1, 1), (0, 0), (500, 250), (3000, 1500), (25, 13)]
    got = [(p, int(derive.windows_at_ctx(U.Windows(p), 64, 128))) for p, _ in grid]
    check("Q3 windows_at_ctx at 64 -> 128: 1000 -> 500, 333 -> 167, 1 -> 1, 0 -> 0 (and 500, 3000, 25 "
          "-> 250, 1500, 13: the nearest whole window, a half going up)",
          got == grid, str(got))
    check("Q3 ... the same text per period at 128 -> 256, and a positive period never comes back 0 "
          "(1 at 64 -> 1024 is 1, not 0)",
          [int(derive.windows_at_ctx(U.Windows(p), 128, 256)) for p, _ in grid] == [q for _, q in grid]
          and int(derive.windows_at_ctx(U.Windows(1), 64, 1024)) == 1
          and int(derive.windows_at_ctx(U.Windows(1000), 128, 128)) == 1000)
    _refused = []
    for args in ((U.Windows(-1), 64, 128), (U.Steps(1000), 64, 128), (1000, 64, 128),
                 (U.Windows(1000), 0, 128), (U.Windows(1000), 64, 128.0),
                 (U.Windows(1000), U.Windows(64), 128)):
        try:
            derive.windows_at_ctx(*args)
            _refused.append(False)
        except U.UnitError:
            _refused.append(True)
    check("Q3 ... refused: a negative period, a Steps or bare-int period, a width of 0, a float width and "
          "a Clock width", all(_refused), str(_refused))

    # =============================================================================================
    # Q1: the identity, on both arms, with FAB, SIG and MEM on
    # =============================================================================================
    parents = {}
    for arch in ("gru", "transformer"):
        env = dict(E1, LM_ARCH=arch)
        p = build(CKPT_DIR=f"{TMP}/q1{arch}", **env)
        n_ep = int(_windows_in_epoch(p))
        rp = loop.run(p, max_windows=n_ep, progress=False)
        clk = p.clock.counters()
        parents[arch] = f"{TMP}/q1{arch}"
        with spy_readings() as rd_u:
            u = build(CKPT_RESUME=f"{TMP}/q1{arch}", CKPT_DIR=f"{TMP}/q1{arch}u", **env)
            u_widened = lm_api._COUNTS.get("lm.ckpt.ctx_widened", "ABSENT")
            ru = loop.run(u, max_windows=1, progress=False)
        with spy_readings() as rd_w:
            w = build(CKPT_RESUME=f"{TMP}/q1{arch}", CKPT_DIR=f"{TMP}/q1{arch}w", LM_CTX_WIDEN=1,
                      **dict(env, LM_CTX="128"))
            w_widened = lm_api._COUNTS.get("lm.ckpt.ctx_widened", "ABSENT")
            # THE IDENTITY, before the child trains a window: windows of 64, 17 and 1 tokens at three
            # offsets into the parent's stream, scored by the parent's model and by the child's.
            ids = p.segmentation.ids
            same, worst = [], 0.0
            for L in (64, 17, 1):
                xs = torch.tensor([ids[a:a + L] for a in (0, 700, 1400)])
                ys = torch.tensor([ids[a + 1:a + L + 1] for a in (0, 700, 1400)])
                a_, b_ = lm_level(p, xs, ys), lm_level(w, xs, ys)
                same.append(torch.equal(a_, b_))
                worst = max(worst, float((a_ - b_).abs().max()))
            # THE RESTORED STATE, TAKEN BEFORE THE CHILD'S FIRST WINDOW MOVES IT: the table as
            # LM.load_state fitted it, and the table's AdamW moments as OPT.load_state padded them.
            w_pos = w.model.pos.weight.detach().clone()
            _pos_i = [i for i, t in enumerate(w.base_params) if t is w.model.pos.weight]
            _st = w.optimizer.base.state_dict()["state"]
            w_mom = ({k: v.detach().clone() for k, v in _st[_pos_i[0]].items() if torch.is_tensor(v)}
                     if _pos_i and _pos_i[0] in _st else {})
            rw = loop.run(w, max_windows=1, progress=False)
        check(f"Q1 {arch}: the parent stopped at its epoch boundary ({n_ep} windows at LM_CTX=64, clock at "
              f"epoch 1 in_epoch 0) with the retention probe pinned",
              rp.windows == n_ep and int(clk["epoch"]) == 1 and int(clk["in_epoch"]) == 0
              and bool(p.probe_set.items), f"epoch {clk['epoch']} in_epoch {clk['in_epoch']}")
        check(f"Q1 {arch}: the widened child's LM-level loss equals the parent's on windows of 64, 17 and 1 "
              f"tokens, bitwise (so within 1e-6)", all(same) and worst <= 1e-6,
              f"bitwise {same}, max |diff| {worst}")
        fresh = build(**dict(env, LM_CTX="128"))
        check(f"Q1 {arch}: its position table, as restored, is the parent's 64 rows and then the 64 a fresh "
              f"LM_CTX=128 build draws (the appended rows keep this build's initialisation)",
              tuple(w_pos.shape) == (128, 128)
              and torch.equal(w_pos[:64], p.model.pos.weight.detach())
              and torch.equal(w_pos[64:], fresh.model.pos.weight[64:].detach())
              and w.ctx_widening == (64, 128) and int(w.geometry.ctx) == 128,
              f"shape {tuple(w_pos.shape)}, ctx_widening {w.ctx_widening}")
        del fresh
        _p_st = p.optimizer.base.state_dict()["state"]
        _p_i = [i for i, t in enumerate(p.base_params) if t is p.model.pos.weight]
        _p_mom = _p_st[_p_i[0]] if _p_i and _p_i[0] in _p_st else {}
        check(f"Q1 {arch}: OPT restores with the one widened tensor's moments padded -- the parent's 64 rows' "
              f"moments kept, the appended 64 at zero -- and no refusal",
              not w.refusals and not w.opt_load.refused
              and w.optimizer.counters.get("opt.ckpt.moments_widened") == 1
              and "exp_avg_sq" in w_mom and tuple(w_mom["exp_avg_sq"].shape) == (128, 128)
              and torch.equal(w_mom["exp_avg_sq"][:64], _p_mom["exp_avg_sq"].detach())
              and torch.equal(w_mom["exp_avg"][:64], _p_mom["exp_avg"].detach())
              and float(w_mom["exp_avg_sq"][64:].abs().sum()) == 0.0
              and float(w_mom["exp_avg"][64:].abs().sum()) == 0.0,
              f"moments_widened {w.optimizer.counters.get('opt.ckpt.moments_widened')}")
        check(f"Q1 {arch}: SIG keeps the parent's width ({p.sig.width_units} units; a fresh LM_CTX=128 run "
              f"would take {derive.signature_width_bytes(128, float(w.vocab.bytes_per_token))}), and WORLD "
              f"reports the width the child runs at (world.ctx_tokens 128, not the parent's 64)",
              int(w.sig.width_units) == int(p.sig.width_units) == int(u.sig.width_units)
              and int(derive.signature_width_bytes(128, float(w.vocab.bytes_per_token)))
              != int(w.sig.width_units)
              and w.world.counters.get("world.ctx_tokens") == 128
              and u.world.counters.get("world.ctx_tokens") == 64,
              f"child {w.sig.width_units}, world {w.world.counters.get('world.ctx_tokens')}")
        _ku = [rd for e, rd in zip(ru.probe_series, rd_u) if e["kind"] == "resume"]
        _kw = [rd for e, rd in zip(rw.probe_series, rd_w) if e["kind"] == "resume"]
        check(f"Q1 {arch}: the widened child's start read -- both closures, routed through SIG, DOM, FAB "
              f"and (memory-on) MEM at the parent's pinned windows -- is the unwidened boundary resume's, "
              f"window for window",
              len(_ku) == len(_kw) == 2 and all(per_window(a) == per_window(b) for a, b in zip(_ku, _kw))
              and all(a.control_mean.value == b.control_mean.value for a, b in zip(_ku, _kw)),
              f"{[(a.closure, a.control_mean.value) for a in _ku]} vs "
              f"{[(b.closure, b.control_mean.value) for b in _kw]}")
        _levers = windows_levers(w.configs)
        _note = [x for x in w.warnings if x.startswith("LM_CTX_WIDEN=1 WIDENED LM_CTX 64 -> 128")]
        _pairs = {f"{k} {v} -> {int(derive.windows_at_ctx(U.Windows(v), 64, 128))}"
                  for k, v in _levers.items()}
        check(f"Q1 {arch}: lm.ckpt.ctx_widened reads 1 on the widened child and is ABSENT on the unwidened "
              f"one; the child trains at 128 (its epoch counts (len - 1) // 128 windows); and one startup "
              f"notice lists all {len(_levers)} Windows-unit levers beside windows_at_ctx's value, "
              f"applying none",
              w_widened == 1 and u_widened == "ABSENT" and rw.windows_here == 1
              and math.isfinite(rw.loss_curve[0])
              and int(w.clock.counters()["windows_in_epoch"]) == (len(w.segmentation.ids) - 1) // 128
              and len(_note) == 1 and all(s in _note[0] for s in _pairs)
              and "FAB_MANAGE_EVERY 500 -> 250" in _note[0]
              and int(w.configs["FAB"].manage_every) == 500 and len(_levers) >= 27,
              f"ctx_widened {w_widened} / {u_widened}, notices {len(_note)}, levers {len(_levers)}")
        del p, u, w

    # =============================================================================================
    # Q2: the refusals, and a continuing resume that widens nothing
    # =============================================================================================
    g = parents["gru"]
    kind, msg = refusal_text(lambda: build(CKPT_RESUME=g, **dict(E1, LM_CTX="128")))
    check("Q2 a larger LM_CTX without LM_CTX_WIDEN is refused at the geometry gate, naming LM_CTX, the "
          "EXACT rule and the lever that would admit it",
          kind == "GeometryRefusal" and "LM_CTX" in msg and "EXACT" in msg and "LM_CTX_WIDEN" in msg,
          f"{kind}: {msg[:160]}")
    kind, msg = refusal_text(lambda: build(CKPT_RESUME=g, LM_CTX_WIDEN=1, **dict(E1, LM_CTX="32")))
    check("Q2 a SMALLER LM_CTX at LM_CTX_WIDEN=1 is refused at the gate: it may grow but not shrink",
          kind == "GeometryRefusal" and "LM_CTX" in msg and "grow but not shrink" in msg,
          f"{kind}: {msg[:160]}")
    un = build(**E1)
    run_u = loop.run(un, max_windows=60, progress=False)
    pm = build(CKPT_DIR=f"{TMP}/q2m", **E1)
    loop.run(pm, max_windows=30, progress=False)
    kind, msg = refusal_text(lambda: build(CKPT_RESUME=f"{TMP}/q2m", LM_CTX_WIDEN=1,
                                           **dict(E1, LM_CTX="128")))
    check("Q2 a widening across a continuing mid-epoch resume is refused by name at the `segment` "
          "stage, before the log's replay, saying where a widening can be taken",
          kind == "RefusedRun" and "LM_CTX_WIDEN=1 widens LM_CTX 64 -> 128" in msg
          and "epoch boundary" in msg and "[stage=segment]" in msg, f"{kind}: {msg[:200]}")
    cm = build(CKPT_RESUME=f"{TMP}/q2m", CKPT_DIR=f"{TMP}/q2c", LM_CTX_WIDEN=1, **E1)
    cm_widened = lm_api._COUNTS.get("lm.ckpt.ctx_widened", "ABSENT")
    run_c = loop.run(cm, max_windows=30, progress=False)
    check("Q2 a continuing resume at LM_CTX_WIDEN=1 that widens nothing continues exactly, and "
          "lm.ckpt.ctx_widened is PRESENT and 0 (armed, did not fire)",
          cm.resume_pos is not None and cm_widened == 0
          and list(run_c.loss_curve) == list(run_u.loss_curve[30:60]),
          f"ctx_widened {cm_widened}, first departure "
          f"{next((i for i, (a, b) in enumerate(zip(run_c.loss_curve, run_u.loss_curve[30:60])) if a != b), None)}")
    del un, pm, cm
    # LM.load_state's own two answers, on models built directly: a 64-row table into a 128-row model.
    c64, c128, c128w = configs(LM_CTX=64), configs(LM_CTX=128), configs(LM_CTX=128, LM_CTX_WIDEN=1)
    g64 = lm_api.resolve(c64["LM"])
    m64 = lm_api.build_model(c64["LM"], g64, device="cpu", seed=3)
    blob = lm_api.state_dict(c64["LM"], m64, g64)
    g128 = lm_api.resolve(c128["LM"])
    m128 = lm_api.build_model(c128["LM"], g128, device="cpu", seed=4)
    rep0 = lm_api.load_state(c128["LM"], m128, g128, blob)
    rng.reset_issued()          # a second model at the same seed stands for a second process
    m128w = lm_api.build_model(c128w["LM"], g128, device="cpu", seed=4)
    before = m128w.pos.weight.detach().clone()
    rep1 = lm_api.load_state(c128w["LM"], m128w, g128, blob)
    check("Q2 LM.load_state at LM_CTX_WIDEN=0 refuses a 64-row table into a 128-row model, naming LM_CTX "
          "and the lever; at 1 it fits the table by prefix and leaves the appended rows as built",
          rep0.refused and "LM_CTX" in rep0.reason and "LM_CTX_WIDEN=1 admits a LARGER context" in rep0.reason
          and not rep1.refused and "64 -> 128 rows" in rep1.reason
          and torch.equal(m128w.pos.weight[:64].detach(), m64.pos.weight.detach())
          and torch.equal(m128w.pos.weight[64:].detach(), before[64:])
          and lm_api._COUNTS.get("lm.ckpt.ctx_widened") == 1,
          f"{rep0.reason[:120]} | {rep1.reason[:120]}")
    # ... and beside a VOCABULARY widening, the prefix rule that was there first. load_state widens
    # vocab_slots through a local tensor that once shared the widening's name, and the first draft
    # of this commit crashed every vocabulary-widening resume on it (test_resume.py R2 caught it):
    # at 0 the vocabulary widens alone and the key is ABSENT; at 1 both widen in one restore.
    cv, cvw = configs(LM_CTX=64, LM_VOCAB_SLOTS=4352), configs(LM_CTX=128, LM_VOCAB_SLOTS=4352,
                                                               LM_CTX_WIDEN=1)
    lm_api._COUNTS.pop("lm.ckpt.ctx_widened", None)
    rng.reset_issued()
    gv = lm_api.resolve(cv["LM"])
    mv = lm_api.build_model(cv["LM"], gv, device="cpu", seed=4)
    repv = lm_api.load_state(cv["LM"], mv, gv, blob)
    v_absent = "lm.ckpt.ctx_widened" not in lm_api._COUNTS
    rng.reset_issued()
    gvw = lm_api.resolve(cvw["LM"])
    mvw = lm_api.build_model(cvw["LM"], gvw, device="cpu", seed=4)
    before_v = mvw.emb.weight.detach().clone()
    repvw = lm_api.load_state(cvw["LM"], mvw, gvw, blob)
    check("Q2 ... and beside a vocabulary widening (LM_VOCAB_SLOTS 4096 -> 4352): at LM_CTX_WIDEN=0 the "
          "three vocabulary tensors widen alone and lm.ckpt.ctx_widened is ABSENT; at 1, with LM_CTX "
          "64 -> 128, one restore widens both, each by prefix",
          not repv.refused and repv.widened == 3 and v_absent
          and not repvw.refused and repvw.widened == 3 and "64 -> 128 rows" in repvw.reason
          and torch.equal(mvw.pos.weight[:64].detach(), m64.pos.weight.detach())
          and torch.equal(mvw.emb.weight[:4096].detach(), m64.emb.weight.detach())
          and torch.equal(mvw.emb.weight[4096:].detach(), before_v[4096:])
          and lm_api._COUNTS.get("lm.ckpt.ctx_widened") == 1,
          f"{repv.reason[:80]} | {repvw.reason[:160]}")
    del m64, m128, m128w, mv, mvw

    # =============================================================================================
    # Q4: the two extrapolating values
    # =============================================================================================
    slopes = lm_api._alibi_slopes(8)
    check("Q4 ALiBi's slopes at LM_HEADS=8 are the paper's 1/2 .. 1/256, and at 6 the power of two below "
          "plus every other slope of the one above",
          slopes == [2.0 ** -k for k in range(1, 9)]
          and lm_api._alibi_slopes(6) == [2.0 ** -k for k in (2, 4, 6, 8)] + [2.0 ** -1, 2.0 ** -3])
    mask = lm_api._alibi_mask(torch.tensor(slopes), 2, 4, torch.zeros(1))
    want = torch.full((8, 4, 4), float("-inf"))
    for h in range(8):
        for i in range(4):
            for j in range(i + 1):
                want[h, i, j] = -slopes[h] * (i - j)
    check("Q4 the ALiBi mask is -m_h x (i - j) at or before the query and -inf after it, one (L, L) slab "
          "per head, repeated over the batch in (batch x heads) order",
          tuple(mask.shape) == (16, 4, 4) and torch.equal(mask[:8], want) and torch.equal(mask[8:], want))
    for arch, pos in (("transformer", "alibi"), ("gru", "none")):
        env = dict(LM_ARCH=arch, LM_POS=pos)
        u = build(**env)
        ru = loop.run(u, max_windows=120, progress=False)
        counts = dict(lm_api._COUNTS)
        sd_keys = list(u.model.state_dict())
        # CAUSALITY on the built model: a later token changes no earlier position's hidden state.
        x = torch.tensor([u.segmentation.ids[:40]])
        x2 = x.clone()
        x2[0, 25] = (int(x2[0, 25]) + 1) % int(u.vocab.size())
        was = u.model.training
        u.model.eval()
        with torch.no_grad():
            h1 = lm_api.encode(u.configs["LM"], u.model, x)
            h2 = lm_api.encode(u.configs["LM"], u.model, x2)
            hp = lm_api.encode(u.configs["LM"], u.model, x[:, :25])
        u.model.train(was)
        p = build(CKPT_DIR=f"{TMP}/q4{pos}", **env)
        loop.run(p, max_windows=60, progress=False)
        c = build(CKPT_RESUME=f"{TMP}/q4{pos}", CKPT_DIR=f"{TMP}/q4{pos}c", **env)
        rc = loop.run(c, max_windows=60, progress=False)
        check(f"Q4 LM_ARCH={arch} LM_POS={pos!r} builds with no position table, and runs 120 windows with "
              f"every loss finite",
              not hasattr(u.model, "pos") and not any(k.startswith("pos.") for k in sd_keys)
              and len(ru.loss_curve) == 120 and all(math.isfinite(v) for v in ru.loss_curve)
              and u.geometry.pos == pos,
              f"losses {ru.loss_curve[0]:.4f} -> {ru.loss_curve[-1]:.4f}")
        check(f"Q4 {pos!r}: a later token changes no earlier position's hidden state, and a prefix's hidden "
              f"states are the full window's",
              torch.equal(h1[:, :25], h2[:, :25]) and not torch.equal(h1[:, 25:], h2[:, 25:])
              and torch.allclose(hp, h1[:, :25], atol=1e-5, rtol=0),
              f"prefix max |diff| {float((hp - h1[:, :25]).abs().max()):.2e}")
        check(f"Q4 {pos!r}: a continuing resume at window 60 trains the uninterrupted run's last 60 losses "
              f"exactly", c.resume_pos is not None and list(rc.loss_curve) == list(ru.loss_curve[60:120]),
              f"first departure "
              f"{next((i for i, (a, b) in enumerate(zip(rc.loss_curve, ru.loss_curve[60:120])) if a != b), None)}")
        if pos == "alibi":
            check("Q4 'alibi': the slopes are a buffer outside the checkpoint, and lm.pos.alibi_applied counts "
                  "every encode call (it equals lm.encode.calls)",
                  hasattr(u.model, "alibi_slopes") and "alibi_slopes" not in sd_keys
                  and counts.get("lm.pos.alibi_applied") == counts.get("lm.encode.calls") > 0,
                  f"{counts.get('lm.pos.alibi_applied')} vs {counts.get('lm.encode.calls')}")
        else:
            check("Q4 'none': lm.pos.alibi_applied is ABSENT, and lm.pos.scheme names the scheme and O17",
                  "lm.pos.alibi_applied" not in counts
                  and counts.get("lm.pos.scheme") == "none: extrapolating, not yet designable (O17: no "
                                                     "passed widening route)",
                  str(counts.get("lm.pos.scheme")))
        del u, p, c

    # =============================================================================================
    # Q5: the scheme across a resume
    # =============================================================================================
    for env, pair in (({"LM_POS": "alibi"}, "LM_POS='alibi' on LM_ARCH=gru"),
                      ({"LM_ARCH": "transformer", "LM_POS": "none"},
                       "LM_POS='none' on LM_ARCH=transformer")):
        kind, msg = refusal_text(lambda: build(**env))
        check(f"Q5 {pair} is refused by name at LM.resolve, before any tensor",
              kind == "GeometryError" and pair in msg, f"{kind}: {msg[:140]}")
    kind, msg = refusal_text(lambda: build(CKPT_RESUME=f"{TMP}/q2m", LM_POS="none", **E1))
    check("Q5 a checkpoint written at 'learned' is refused by name at LM_POS='none' (LM.load_state)",
          kind == "RefusedRun" and "LM.load_state refused" in msg
          and "LM_POS: the checkpoint was written at 'learned'" in msg, f"{kind}: {msg[:200]}")
    _lever._reopen_assembly()
    snap = ckpt_api.load(assemble.build(environ={"CKPT_RESUME": f"{TMP}/q2m"})[0]["CKPT"])
    payload = dict(snap.payload)
    lmp = dict(payload["LM"])
    lmp["geometry"] = {k: v for k, v in dict(lmp["geometry"]).items() if k != "pos"}
    payload["LM"] = lmp
    legacy = dataclasses.replace(snap, payload=payload)
    lc = build(restored=legacy, CKPT_RESUME=f"{TMP}/q2m", CKPT_DIR=f"{TMP}/q5c", **E1)
    run_l = loop.run(lc, max_windows=30, progress=False)
    check("Q5 a checkpoint whose LM geometry records no scheme resumes as 'learned', with no refusal, "
          "and continues exactly",
          "pos" not in legacy.payload["LM"]["geometry"] and not lc.refusals and not lc.lm_load.refused
          and list(run_l.loss_curve) == list(run_u.loss_curve[30:60]), lc.lm_load.reason[:120])
    kind, msg = refusal_text(lambda: build(restored=legacy, CKPT_RESUME=f"{TMP}/q2m", LM_POS="none", **E1))
    check("Q5 ... and is refused by name at any other scheme, saying it predates LM_POS",
          kind == "RefusedRun" and "predates LM_POS" in msg, f"{kind}: {msg[:200]}")
    del lc

    # =============================================================================================
    # Q6: the designation
    # =============================================================================================
    cfg = configs()["LM"]
    geoms = {"gru/learned": {"arch": "gru", "pos": "learned", "ctx": 128},
             "transformer/alibi": {"arch": "transformer", "pos": "alibi", "ctx": 128},
             "gru/none": {"arch": "gru", "pos": "none", "ctx": 128},
             "legacy": {"arch": "gru", "ctx": 128}}
    outs = {}
    for k, gm in geoms.items():
        try:
            outs[k] = lm_api.parent_designation(cfg, saved_geometry=gm)
        except lm_api.ContextLockedParent as e:
            outs[k] = str(e)
    check("Q6 with PASSED_WIDENING_ROUTES empty, parent_designation REFUSES every scheme by name -- "
          "'learned' as context-locked, 'alibi' and 'none' as unproven -- a legacy record as 'learned', "
          "each naming O17 and the switch",
          lm_api.PASSED_WIDENING_ROUTES == frozenset() and lm_api.REFUSE_CONTEXT_LOCKED_PARENT is True
          and all(isinstance(v, str) and "O17" in v and "REFUSE_CONTEXT_LOCKED_PARENT" in v
                  for v in outs.values())
          and "LM_ARCH=gru LM_POS='learned'" in outs["legacy"] and "LM_CTX=128 for life" in outs["legacy"]
          and "no GPU reading has shown it to extrapolate" in outs["transformer/alibi"],
          outs["gru/learned"][:120] if isinstance(outs["gru/learned"], str) else repr(outs["gru/learned"]))
    kind, msg = refusal_text(lambda: lm_api.parent_designation(cfg, saved_geometry={"width": 128}))
    check("Q6 a record with no LM geometry is not judged: GeometryError, not the refusal",
          kind == "GeometryError", f"{kind}: {msg[:100]}")
    try:
        lm_api.REFUSE_CONTEXT_LOCKED_PARENT = False
        off = lm_api.parent_designation(cfg, saved_geometry=geoms["gru/learned"])
    finally:
        lm_api.REFUSE_CONTEXT_LOCKED_PARENT = True
    try:
        lm_api.PASSED_WIDENING_ROUTES = frozenset({("gru", "learned")})
        passed = lm_api.parent_designation(cfg, saved_geometry=geoms["gru/learned"])
        label = lm_api._scheme_label("gru", "learned")
        kind, other = refusal_text(lambda: lm_api.parent_designation(
            cfg, saved_geometry={"arch": "transformer", "pos": "learned", "ctx": 128}))
    finally:
        lm_api.PASSED_WIDENING_ROUTES = frozenset()
    check("Q6 THE SWITCHES WORK: REFUSE_CONTEXT_LOCKED_PARENT=False admits, route_passed False, saying "
          "the refusal was off; a route entered as passed admits that (arch, pos), route_passed True, "
          "relabels lm.pos.scheme, and still refuses the other arm",
          isinstance(off, lm_api.Designation) and off.route_passed is False
          and "REFUSE_CONTEXT_LOCKED_PARENT is False" in off.reason
          and isinstance(passed, lm_api.Designation) and passed.route_passed is True
          and (passed.arch, passed.pos, passed.ctx) == ("gru", "learned", 128)
          and "has passed" in label and kind == "ContextLockedParent"
          and lm_api._scheme_label("gru", "learned") == "learned: context-locked (O17: no passed "
                                                       "widening route)",
          f"{off.reason[:80]} | {label}")
    listing = sorted(os.listdir(g))
    # RUN AS AN OPERATOR RUNS IT, BY ITS PATH, FROM A DIRECTORY THAT IS NOT THE REPOSITORY ROOT: the
    # root's own memory.py would shadow src/memory for anything that puts the working directory on
    # sys.path, and the tool must not depend on where it is started from.
    tool = os.path.join(os.path.abspath(_ROOT), "tools", "designate_parent.py")
    pr = subprocess.run([sys.executable, tool, g], cwd=TMP, capture_output=True, text=True,
                        env=dict(os.environ, OMP_NUM_THREADS="1", MKL_NUM_THREADS="1"))
    miss = subprocess.run([sys.executable, tool, f"{TMP}/no_such_run"], cwd=TMP, capture_output=True,
                          text=True, env=dict(os.environ, OMP_NUM_THREADS="1", MKL_NUM_THREADS="1"))
    check("Q6 tools/designate_parent.py exits 2 on the refusal, prints it by name and writes nothing; "
          "on a path with no checkpoint it exits 1",
          pr.returncode == 2 and pr.stdout.startswith("REFUSED:") and "O17" in pr.stdout
          and sorted(os.listdir(g)) == listing and miss.returncode == 1
          and miss.stdout.startswith("UNREADABLE:"),
          f"rc {pr.returncode} {pr.stdout[:100]!r}; missing rc {miss.returncode}")
    try:
        lm_api.REFUSE_CONTEXT_LOCKED_PARENT = False
        _lever._reopen_assembly()
        code, line, written = dp.designate(g)
    finally:
        lm_api.REFUSE_CONTEXT_LOCKED_PARENT = True
    rec = json.load(open(written, encoding="utf-8")) if written else {}
    check("Q6 ... and with the refusal switched off it designates, writing one record beside the "
          "checkpoint that says the switch was off and no route has passed",
          code == 0 and written == os.path.join(g, "ckpt.pt") + ".designation.json"
          and rec.get("refuse_context_locked_parent") is False
          and rec.get("designation", {}).get("route_passed") is False
          and rec.get("designation", {}).get("ctx") == 64 and rec.get("passed_widening_routes") == [],
          line[:120])
    if written and os.path.exists(written):
        os.remove(written)

    # =============================================================================================
    # Q7: 'learned' is the tree before the lever
    # =============================================================================================
    _env = dict(os.environ, OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    b1 = subprocess.run([sys.executable, os.path.join("tests", "test_baseline.py"), "B1"],
                        cwd=os.path.abspath(_ROOT), env=_env, capture_output=True, text=True)
    check("Q7 B1 reproduces its fixture at the shipped defaults (tests/test_baseline.py)",
          b1.returncode == 0 and any(ln.startswith("PASS  B1") for ln in b1.stdout.splitlines()),
          (b1.stdout + b1.stderr)[-300:] if b1.returncode else "")
    have = subprocess.run(["git", "-C", os.path.abspath(_ROOT), "cat-file", "-e",
                           PRE_LEVER + "^{commit}"], capture_output=True)
    if have.returncode != 0:
        print(f"UNVERIFIABLE Q7 a checkpoint written by the tree before LM_POS -- commit {PRE_LEVER} is "
              f"not in this repository, so its tree cannot be run here", flush=True)
    else:
        old = os.path.join(TMP, "pre_lever")
        os.makedirs(old)
        arc = subprocess.run(["git", "-C", os.path.abspath(_ROOT), "archive", "--format=tar", PRE_LEVER,
                              "src", "run.py"], capture_output=True, check=True)
        with tarfile.open(fileobj=io.BytesIO(arc.stdout)) as tf:
            tf.extractall(old)
        # A CLEAN ENVIRONMENT: the levers this file sets and nothing a caller's shell exports.
        oenv = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", ""),
                "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", **BASE,
                "CKPT_DIR": os.path.join(TMP, "q7h")}
        curve = os.path.join(TMP, "q7h_curve.json")
        orun = subprocess.run([sys.executable, "run.py", "--max-windows", "30", "--quiet",
                               "--loss-curve", curve], cwd=old, env=oenv, capture_output=True, text=True)
        head_curve = json.load(open(curve)) if orun.returncode == 0 else []
        ref = build()
        rr = loop.run(ref, max_windows=60, progress=False)
        _lever._reopen_assembly()
        hsnap = ckpt_api.load(assemble.build(environ={"CKPT_RESUME": os.path.join(TMP, "q7h")})[0]["CKPT"])
        hc = build(CKPT_RESUME=os.path.join(TMP, "q7h"), CKPT_DIR=os.path.join(TMP, "q7c"))
        scheme = lm_api._COUNTS.get("lm.pos.scheme")
        rh = loop.run(hc, max_windows=30, progress=False)
        check(f"Q7 the tree before LM_POS ({PRE_LEVER}) trains the same first 30 losses as this tree at the "
              f"shipped defaults, and its mid-epoch checkpoint -- whose LM geometry records no scheme -- "
              f"continues here exactly as 'learned'",
              orun.returncode == 0 and head_curve == list(rr.loss_curve[:30])
              and "pos" not in hsnap.payload["LM"]["geometry"] and hc.resume_pos is not None
              and not hc.refusals and not hc.lm_load.refused
              and scheme == "learned: context-locked (O17: no passed widening route)"
              and list(rh.loss_curve) == list(rr.loss_curve[30:60]),
              f"rc {orun.returncode}{' ' + orun.stderr[-200:] if orun.returncode else ''}; first "
              f"departure {next((i for i, (a, b) in enumerate(zip(rh.loss_curve, rr.loss_curve[30:60])) if a != b), None)}")
finally:
    # EVERY CHECKPOINT, VOCABULARY AND COPIED TREE THIS FILE WROTE IS UNDER TMP.
    shutil.rmtree(TMP, ignore_errors=True)

print(f"\n=== {len(FAILS)} failing ===")
sys.exit(1 if FAILS else 0)
