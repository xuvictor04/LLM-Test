"""STARTUP REFUSALS THAT STOP, NON-FINITE STATE THAT IS NEVER TRAINED ON OR SAVED, AND RUNTIME TEXT
THAT DESCRIBES THE CODE UNDER IT. Driven through the real composition root at a tenth-size fabric.

    python3 tests/test_prose_guards.py        # exit 0 = every check passed

WHY IT EXISTS (the prose-and-guards repair, 2026-09-24; Q-RUN-13 .. Q-RUN-15 in
docs/04_CONTRACT.md). Each of these was driven on the tree before the repair:

  G1  A STARTUP REFUSAL STOPS compose(). RUN_EPOCHS=2 with resampling off returned
      stage='assembled' with the refusal on System.refusals, after building the model and running
      the SIG warm-up; compose() now raises RefusedRun at the `refuse` stage, before any model.
  G2  A DECLARED-AND-NOT-BUILT ARM IS REFUSED AT STARTUP. LM_COMPOSE=1 and MEM_KEY_SRC=frozen
      composed with 0 refusals and raised NotBuilt at the first flush, after the whole warm-up.
  G3  A NEGATIVE PERIOD IS DESCRIBED AS WHAT RUN.Cadences.due DOES WITH IT -- DISARMED -- and not
      as a fire on EVERY window, which is what four refusals and a Gate reason said while the
      ledger beside them read fires=0.
  G4  LM.build_model WRITES THE FIVE lm.build.* GAUGES ITS DID IT FIRE LINE DECLARES; all five were
      ABSENT on both LM_ARCH arms.
  G5  NO _NONFINITE_MEASURED ENTRY CALLS A FUNCTION A STUB WHEN IT HAS A BODY (SIG.train_step and
      FAB.manage were both called stubs in text quoted into an operator's refusal).
  G6  A PARTIAL BATCH LEFT AT THE END OF A RUN IS SAID, and RUN.RunClock.counters reaches the report.
  G7  THE ENCODER'S RATE-WRITE COUNTER IS ABSENT WHEN THE ENCODER GROUP IS EMPTY (SIG_MODE=bigram
      read opt.lr.writes.encoder 12 beside opt.build.params.encoder 0), and fab.spawned /
      fab.spawn_declined are absent at FAB_SPAWN=0 beside gate fab.spawn reading UNREACHABLE.
  G8  RUN_PROFILE=1 TIMES SPANS; nothing opened one and bench said "RUN_PROFILE is off".
  G9  A NON-FINITE LOSS STOPS THE RUN BEFORE THE OPTIMIZER STEPS ON IT, and CKPT.save refuses a
      payload that holds a nan or an inf. One nan loss left 8 of 8 LM tensors non-finite.
"""
import math
import os
import re
import sys
import tempfile

_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(_ROOT, "src"))

import torch                                                       # noqa: E402
torch.set_num_threads(1)

from spine import lever as _lever                                  # noqa: E402
from spine import rng                                              # noqa: E402
from spine import loop                                             # noqa: E402
from spine import assemble                                         # noqa: E402
from spine import compose as C                                     # noqa: E402
from spine.gate import NotBuilt, NonFinite                         # noqa: E402
from ckpt import api as ckpt_api                                   # noqa: E402
from lm import api as lm_api                                       # noqa: E402

FAILS = []
BASE = {"DATA_STREAM_BYTES": "60000", "SIG_WARMUP": "20", "FAB_N0": "256", "FAB_SLOTS": "512"}


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" -- {detail}" if detail else ""))
    if not ok:
        FAILS.append(name)


def _reopen():
    _lever._reopen_assembly()
    rng.reset_issued()


def build(**env):
    _reopen()
    e = dict(BASE)
    e.update({k: str(v) for k, v in env.items()})
    return C.compose(environ=e)


def g1_refusal_stops_compose():
    try:
        build(RUN_EPOCHS=2)
        check("G1 RUN_EPOCHS=2 without resampling raises RefusedRun from compose()", False,
              "compose returned")
        return
    except C.RefusedRun as e:
        s = e.system
        check("G1 RUN_EPOCHS=2 without resampling raises RefusedRun at the `refuse` stage, before "
              "any model, fabric or warm-up exists",
              e.stage == "refuse" and s.model is None and s.fabric is None and s.warmup is None
              and any("RUN_EPOCHS=2" in r for r in e.refusals), f"stage={e.stage!r}")
    # loop.run's own guard, for a System that reaches it by another route.
    s = build()
    s.refusals.append("synthetic refusal for the loop.run guard")
    try:
        loop.run(s, max_windows=1, progress=False)
        check("G1 loop.run refuses a System carrying a refusal", False, "it trained")
    except C.RefusedRun as e:
        check("G1 loop.run refuses a System carrying a refusal, with RefusedRun",
              "synthetic refusal" in str(e))


def g2_not_built_arms_refused_at_startup():
    for env, lever in (({"LM_COMPOSE": "1"}, "LM_COMPOSE=1"),
                       ({"MEM_KEY_SRC": "frozen"}, "MEM_KEY_SRC='frozen'")):
        try:
            build(**env)
            check(f"G2 {lever} is refused at compose", False, "compose returned")
        except NotBuilt as e:
            check(f"G2 {lever} is refused at compose with NotBuilt naming the lever",
                  str(e).startswith(lever), str(e)[:100])


def g3_negative_period_text():
    from memory import api as mem_api
    from domains import api as dom_api
    from eval import api as ev_api
    for env, pfx, fn in (("CKPT_EVERY", "CKPT", ckpt_api.save_period),
                         ("MEM_REKEY_EVERY", "MEM", mem_api.rekey_period),
                         ("DOM_MANAGE_EVERY", "DOM", dom_api.manage_period),
                         ("EVAL_CURVE_EVERY", "EVAL", ev_api.curve_period)):
        _reopen()
        cfgs, _, _ = assemble.build(environ={env: "-1"})
        try:
            fn(cfgs[pfx])
            check(f"G3 {env}=-1 is refused", False, "accepted")
        except Exception as e:
            m = str(e)
            check(f"G3 {env}=-1's refusal says DISARMED and not 'EVERY window'",
                  "DISARM" in m and "EVERY window" not in m and "first window" not in m, m[:140])
    # THE NEGATIVE GATE ARM, reached only with the owner's switch off.
    _reopen()
    cfgs, _, _ = assemble.build(environ={"CKPT_EVERY": "-1", "CKPT_DIR": tempfile.gettempdir()})
    was = ckpt_api.REFUSE_NEGATIVE_PERIOD
    ckpt_api.REFUSE_NEGATIVE_PERIOD = False
    try:
        g = ckpt_api.save_period(cfgs["CKPT"]).gates[0]
    finally:
        ckpt_api.REFUSE_NEGATIVE_PERIOD = was
    check("G3 the ckpt.periodic_armed negative arm says DISARMED, not a checkpoint every window",
          "DISARMED" in g.reason and "a checkpoint EVERY window" not in g.reason, g.reason[:140])


def g4_lm_build_gauges(s):
    c = lm_api.counters(s.configs["LM"], s.model)
    arms = (c.get("lm.build.arm_gru"), c.get("lm.build.arm_transformer"))
    check("G4 exactly one LM arm gauge is 1 and the other 0",
          sorted(arms) == [0, 1], arms)
    check("G4 compose_on is 0, heads_used is 0 on gru, emb_head_allocated is 1 on the built arm",
          c.get("lm.build.compose_on") == 0 and c.get("lm.build.emb_head_allocated") == 1
          and (c.get("lm.build.heads_used") == 0) == (arms[0] == 1),
          {k: c.get(k) for k in ("lm.build.compose_on", "lm.build.heads_used",
                                 "lm.build.emb_head_allocated")})


# THE PREFIX -> PACKAGE DIRECTORY MAP, for resolving `FAB.manage` and `fabric/api.py::manage`.
_PKG = {"FAB": "fabric", "SIG": "sig", "TOK": "tok", "OPT": "opt", "LM": "lm", "MEM": "memory",
        "DOM": "domains", "CAP": "capacity", "RUN": "train", "EVAL": "eval", "WORLD": "world",
        "DATA": "data", "CKPT": "ckpt"}


def _is_stub(pkg, name):
    import importlib
    import inspect
    mod = importlib.import_module(f"{pkg}.api")
    fn = getattr(mod, name, None)
    if fn is None:
        return None
    return "raise NotImplementedError" in inspect.getsource(fn)


def _false_stub_refs(text):
    """Every function a 'stub' sentence in `text` names that in fact has a body."""
    out = []
    for sentence in re.split(r"(?<=[.;])\s+|--", text):
        if "stub" not in sentence.lower():
            continue
        refs = [(p, n) for p, n in re.findall(r"\b([a-z]+)/api\.py::(\w+)", sentence)]
        refs += [(_PKG[p], n) for p, n in re.findall(r"\b([A-Z]{2,5})\.([a-z_]+)\b", sentence)
                 if p in _PKG]
        out += [f"{p}.{n}" for p, n in refs if _is_stub(p, n) is False]
    return out


# THE TWO SENTENCES THIS CHECK WAS WRITTEN AGAINST, verbatim from the tree before the repair. The
# check must flag both, or it is a check that cannot fail.
_PRE_REPAIR = (
    "NO LIVE READER TODAY: sig/api.py::train_step is the only function that names it and it is a "
    "NotImplementedError stub, so at every value this lever passes through build untouched",
    "or its only readers are FAB.manage and FAB.contribution, which are still P4 stubs -- there "
    "the value freezes into the Config",
)


def g5_nonfinite_tables_name_no_false_stub():
    import importlib
    trips = [_false_stub_refs(t) for t in _PRE_REPAIR]
    check("G5 the stub-claim check flags both pre-repair sentences (sig.train_step, fabric.manage)",
          trips[0] == ["sig.train_step"] and "fabric.manage" in trips[1], trips)
    bad = []
    for pkg in ("sig", "tok", "opt", "fabric"):
        mod = importlib.import_module(f"{pkg}.api")
        for lever, text in getattr(mod, "_NONFINITE_MEASURED", {}).items():
            bad += [f"{lever}: {r}" for r in _false_stub_refs(text)]
    # FAB's fallback sentence is not in the table; it is rendered into build()'s refusal.
    fsrc = open(os.path.join(_ROOT, "src", "fabric", "api.py")).read()
    fb = fsrc[fsrc.index('_NONFINITE_MEASURED.get('):]
    bad += [f"FAB fallback: {r}" for r in _false_stub_refs(fb[:fb.index("for k, v in _nonfinite)")])]
    check("G5 no _NONFINITE_MEASURED entry (or FAB's fallback) calls a function with a body a stub",
          not bad, bad[:3])


def g6_unflushed_batch_is_said():
    s = build(OPT_BATCH_WINDOWS=4)
    res = loop.run(s, max_windows=6, progress=False)
    check("G6 a max_windows stop mid-batch reports 2 windows that never reached a backward",
          res.never_backward == 2 and any("never flushed" in w and "(max_windows)" in w
                                          for w in res.warnings), res.never_backward)
    row = res.report.get("RUN.RunClock.counters")
    check("G6 RUN.RunClock.counters is rendered at R, with dropped_windows and batch_len",
          isinstance(row, dict) and "dropped_windows" in row and row.get("batch_len") == 2, row)
    return s


def g7_off_arm_counters():
    s = build(SIG_MODE="bigram", FAB_SPAWN="0", RUN_PROFILE="1", RUN_BENCH="1")
    res = loop.run(s, max_windows=3, progress=False)
    oc = s.optimizer.counters
    check("G7 SIG_MODE=bigram: opt.lr.writes.encoder is ABSENT beside opt.build.params.encoder 0",
          oc["opt.build.params.encoder"] == 0 and "opt.lr.writes.encoder" not in oc
          and oc["opt.lr.writes.base"] == oc["opt.step"], {k: v for k, v in oc.items()
                                                           if "lr.writes" in k})
    fc = s.fabric.counters
    check("G7 FAB_SPAWN=0: fab.spawned and fab.spawn_declined are ABSENT (the gate says "
          "UNREACHABLE)", "fab.spawned" not in fc and "fab.spawn_declined" not in fc)
    spans = res.report.get("RUN.Timing.spans")
    bench = res.report.get("RUN.bench_summary")
    check("G8 RUN_PROFILE=1 times the flush and bench prints the breakdown",
          isinstance(spans, dict) and spans.get("flush", 0) > 0
          and not any("RUN_PROFILE is off" in str(l) for l in bench), spans)


def g9_nonfinite():
    real, n = lm_api.lm_loss, [0]

    def poisoned(*a, **k):
        pw, m = real(*a, **k)
        n[0] += 1
        return (pw, m * float("nan")) if n[0] == 3 else (pw, m)
    with tempfile.TemporaryDirectory() as d:
        s = build(CKPT_DIR=d)
        loop.lm_api.lm_loss = poisoned
        try:
            loop.run(s, max_windows=6, progress=False)
            check("G9 a nan loss stops the run", False, "it returned")
        except NonFinite as e:
            finite = all(bool(torch.isfinite(t).all()) for t in s.model.parameters())
            check("G9 a nan loss stops the run with NonFinite naming the window and OPT_LR, "
                  "before the optimizer stepped on it",
                  "window 3" in str(e) and "OPT_LR" in str(e) and finite, str(e)[:120])
            check("G9 the last finite state was saved as the final checkpoint",
                  os.path.exists(os.path.join(d, "ckpt.pt")) and "WAS saved" in str(e))
        finally:
            loop.lm_api.lm_loss = real
        # THE STOPPING SAVE'S BACKWARD COUNT IS THE CLOCK'S (2026-09-24): scaled_backward had
        # counted the nan pass and the clock had not, so the final checkpoint carried one more.
        st = s.optimizer
        check("G9 the discarded nan backward is un-counted: OPT n_backward equals the clock's",
              int(st.n_backward) == int(s.clock.counters()["backwards"])
              and st.counters.get("opt.backward") == int(st.n_backward),
              f"OPT {int(st.n_backward)}, clock {int(s.clock.counters()['backwards'])}")
        # A HUGE-BUT-FINITE LOSS IS REFUSED BY OPT BEFORE THE STEP WOULD POISON ITS MOMENTS.
        big = [0]

        def huge(*a, **k):
            pw, m = real(*a, **k)
            big[0] += 1
            return (pw, m * 1e30) if big[0] == 3 else (pw, m)
        s2 = build()
        loop.lm_api.lm_loss = huge
        try:
            loop.run(s2, max_windows=6, progress=False)
            check("G9 a 1e30 loss is refused before the optimizer steps on it", False, "returned")
        except NonFinite as e:
            bad = sum(1 for v in s2.optimizer.base.state.values() for t in v.values()
                      if torch.is_tensor(t) and t.is_floating_point()
                      and not bool(torch.isfinite(t).all()))
            check("G9 a 1e30 loss is refused by OPT.maybe_step before the step, moments finite",
                  "OPT.maybe_step" in str(e) and bad == 0
                  and s2.optimizer.counters.get("opt.step.refused_nonfinite") == 1,
                  f"{bad} non-finite optimizer tensors; {str(e)[:80]}")
        finally:
            loop.lm_api.lm_loss = real
        before = ckpt_api._SAVES.get("refused_nonfinite", 0)
        try:
            ckpt_api.save(s.configs["CKPT"], payload={"X": {"w": torch.tensor([1.0, math.inf])}},
                          geometry={}, step=1, epoch=0, reason="periodic", suffix=".g9")
            check("G9 CKPT.save refuses a payload holding an inf", False, "it wrote")
        except NonFinite as e:
            check("G9 CKPT.save refuses a payload holding an inf, names the tensor and writes "
                  "nothing", "/payload/X/w (1 of 2)" in str(e)
                  and not os.path.exists(os.path.join(d, "ckpt.pt.g9"))
                  and ckpt_api._SAVES["refused_nonfinite"] == before + 1, str(e)[:120])


def g_text():
    src = open(os.path.join(_ROOT, "run.py")).read()
    check("run.py's docstring no longer says FAB.manage and SIG.train_step have no bodies",
          "are the last two LOOP_ORDER rows without bodies" not in src)
    cap = open(os.path.join(_ROOT, "src", "capacity", "api.py")).read()
    body = cap[cap.index("def counters(cap: Config, valve):"):]
    body = body[:body.index('    """\n', body.index('"""') + 3)]
    check("CAP.counters declares the wire it reads (d_operating_population)",
          re.search(r"WIRES READ: d_operating_population", body) is not None)


if __name__ == "__main__":
    g1_refusal_stops_compose()
    g2_not_built_arms_refused_at_startup()
    g3_negative_period_text()
    g5_nonfinite_tables_name_no_false_stub()
    g_text()
    s = g6_unflushed_batch_is_said()
    g4_lm_build_gauges(s)
    g7_off_arm_counters()
    g9_nonfinite()
    print(f"=== {len(FAILS)} failure(s)")
    sys.exit(1 if FAILS else 0)
