"""WHAT THE LOOP HANDS FAB.forward -- and what it does with what comes back. Driven through the real
loop (compose -> loop.run -> LM.encode -> FAB.forward -> LM.lm_loss) on short runs.

    python3 tests/test_fabric_forward.py        # exit 0 = every check passed

WHY IT EXISTS (Q-FAB-8 .. Q-FAB-11, docs/04_CONTRACT.md, 2026-09-24). Every one of these was a
wiring gap between spine/loop.py and fabric/api.py that no file in tests/ could see, because
tests/test_fabric.py drives FAB.forward with a head and targets of its own and never through the
loop -- so the bodies were right and the call site starved them:

  W1  HEAD AND TARGETS. The loop passed neither, so the shipped FAB_HOP_VOTE=True never formed and
      FAB_SOCIETY=1 / FAB_HOP_SUP / FAB_IND_W changed nothing but the timing line. The vote's logits
      must BE the prediction lm_loss scores (FabricOut: "the caller must not re-decode hidden"), and
      the three reachable-only counters must be ABSENT where their arm cannot reach them (G4).
  W2  live_domains. The loop passed the literal 1, so FAB_DOM_FRAC could not move the breadth cap.
      It must be DOM.census's n_live, carried from the dom.manage pass.
  W3  THE CONTROL ARMS. FAB_ON=0 and FAB_NORM_ONLY=1 crashed at the first flush on
      `weights is None`; FAB_ON=0 also handed OPT the fabric's 8.9M parameters and grew experts.
  W4  PER-WINDOW DOMAINS. At OPT_BATCH_WINDOWS > 1 FAB.observe and DOM.note_competence took the
      LAST window's id for the whole flush.
  W5  THE MASK. LM.decode masks with -inf and the vote multiplies by weights that are exactly 0 at
      FAB_HALT=0, so without FAB's finite floor the loss is nan at LM_MASK_DEAD_ROWS=1.
  W6  FAB_HOP_MODE=transition (declared, not built) must print REFUSED and exit 2, not a traceback.
"""
import math
import os
import subprocess
import sys

_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(_ROOT, "src"))

import torch                                                       # noqa: E402
torch.set_num_threads(1)

from spine import lever as _lever                                  # noqa: E402
from spine import rng                                              # noqa: E402
from spine import loop                                             # noqa: E402
from spine.compose import compose                                  # noqa: E402
from fabric import api as fab_api                                  # noqa: E402

FAILS = []
BASE = {"DATA_STREAM_BYTES": "60000", "SIG_WARMUP": "20"}


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" -- {detail}" if detail else ""))
    if not ok:
        FAILS.append(name)


def build(**env):
    """One real System per configuration; the assembly latch and the rng registry are reopened
    first because each call here stands for a different run."""
    _lever._reopen_assembly()
    rng.reset_issued()
    e = dict(BASE)
    e.update({k: str(v) for k, v in env.items()})
    return compose(environ=e)


class _Patch:
    """Rebind one module attribute for the duration of a `with`, and put it back whatever happens."""

    def __init__(self, mod, name, fn):
        self.mod, self.name, self.fn = mod, name, fn

    def __enter__(self):
        self.orig = getattr(self.mod, self.name)
        setattr(self.mod, self.name, self.fn(self.orig))
        return self

    def __exit__(self, *exc):
        setattr(self.mod, self.name, self.orig)
        return False


def w1():
    seen = {"head": [], "targets": [], "out": [], "scored": []}

    def fw(orig):
        def f(*a, **k):
            out = orig(*a, **k)
            if k.get("training"):
                seen["head"].append(k.get("head"))
                seen["targets"].append(k.get("targets"))
                seen["out"].append(out)
            return out
        return f

    def ll(orig):
        def f(lm, logits, y):
            seen["scored"].append(logits)
            return orig(lm, logits, y)
        return f

    sysm = build()
    with _Patch(loop.fab_api, "forward", fw), _Patch(loop.lm_api, "lm_loss", ll):
        res = loop.run(sysm, max_windows=3, progress=False)
    heads_ok = bool(seen["head"]) and all(callable(h) for h in seen["head"])
    tg_ok = bool(seen["targets"]) and all(t is not None and t.dtype == torch.long
                                          for t in seen["targets"])
    check("W1 the loop passes FAB.forward a callable head and the targets", heads_ok and tg_ok,
          f"{len(seen['head'])} training pass(es); head callable on all: {heads_ok}; targets on "
          f"all: {tg_ok}")
    voted = [o.logits is not None for o in seen["out"]]
    same = [s is o.logits for s, o in zip(seen["scored"], seen["out"])]
    check("W1 at the shipped FAB_HOP_VOTE=True the vote forms and ITS logits are what lm_loss scores",
          all(voted) and all(same),
          f"FabricOut.logits present on {sum(voted)}/{len(voted)} pass(es); lm_loss scored that "
          f"very tensor on {sum(same)}/{len(same)}")
    fc = res.report["FAB.counters"]
    absent = [k for k in ("fab.ind_applied", "fab.halt_spent_on_base") if k not in fc]
    check("W1 counters the default arm cannot reach are ABSENT, and the pass's gates are printed",
          len(absent) == 2 and "gate:fab.independence" in fc
          and fc["gate:fab.independence"][0] == "unreachable",
          f"absent: {absent}; gate:fab.independence = {fc.get('gate:fab.independence', 'MISSING')!r:.80}")

    sysm = build(FAB_SOCIETY=1)
    res = loop.run(sysm, max_windows=3, progress=False)
    fc = res.report["FAB.counters"]
    check("W1 FAB_SOCIETY=1 fires the independence loss and the halt-on-base spend",
          int(fc.get("fab.ind_applied", 0)) > 0 and int(fc.get("fab.halt_spent_on_base", 0)) > 0,
          f"fab.ind_applied={fc.get('fab.ind_applied')}, "
          f"fab.halt_spent_on_base={fc.get('fab.halt_spent_on_base')}")
    dc = fc.get("gate:fab.depth_curriculum", ("MISSING",))
    check("W1 FAB_SOCIETY=1 prints the depth curriculum UNREACHABLE (the walk is pinned at one hop)",
          dc[0] == "unreachable", f"gate:fab.depth_curriculum = {dc!r:.120}")


def w2():
    passed, census = [], []

    def bb(orig):
        def f(pop, n, domain_id, live_domains, dom_frac, dom_min):
            passed.append(int(live_domains))
            return orig(pop, n, domain_id, live_domains, dom_frac, dom_min)
        return f

    def ce(orig):
        def f(*a, **k):
            r = orig(*a, **k)
            census.append(int(r.n_live))
            return r
        return f

    sysm = build(DOM_MANAGE_EVERY=4)
    with _Patch(fab_api, "_breadth_ban", bb), _Patch(loop.dom_api, "census", ce):
        loop.run(sysm, max_windows=12, progress=False)
    # THE LAST A-STAGE CENSUS IS census[-2]: census[-1] is the R stage's, taken after the last flush.
    a_stage = census[:-1]
    ok = bool(a_stage) and passed[-1] == a_stage[-1] and passed[0] == 1
    check("W2 live_domains is DOM.census's n_live from the dom.manage pass, 1 before it fires", ok,
          f"passed per flush {passed}; A-stage census n_live {a_stage}")


def w3():
    for arm, env in (("FAB_ON=0", {"FAB_ON": 0}), ("FAB_NORM_ONLY=1", {"FAB_NORM_ONLY": 1})):
        sysm = build(**env)
        n0 = int(sysm.fabric.n_live)
        fab_ids = {id(t) for t in (sysm.fabric.A, sysm.fabric.B, sysm.fabric.halt_b)}
        in_opt = sum(1 for t in sysm.base_params if id(t) in fab_ids)
        err = None
        try:
            res = loop.run(sysm, max_windows=3, progress=False)
        except Exception as e:                                    # noqa: BLE001 -- the check IS this
            err, res = e, None
        books = res.report.get("LOOP(flush books)") if res else None
        ok = err is None and isinstance(books, dict) and books.get("loop.owners_from_domain") == 3
        check(f"W3 {arm} runs to completion and takes MEM's owner from the domain, counted",
              ok, f"error={err!r:.100}; LOOP(flush books)={books!r}")
        if arm == "FAB_ON=0":
            fc = res.report["FAB.counters"] if res else {}
            check("W3 FAB_ON=0 hands OPT no fabric parameter and grows/culls nothing",
                  in_opt == 0 and int(sysm.fabric.n_live) == n0 and "fab.grow_checks" not in fc
                  and "fab.manage_passes" not in fc
                  and fc.get("gate:fab.growth_armed", ("",))[0] == "unreachable",
                  f"fabric tensors in base_params {in_opt}; n_live {n0} -> "
                  f"{int(sysm.fabric.n_live)}; fab.grow_checks "
                  f"{'ABSENT' if 'fab.grow_checks' not in fc else fc['fab.grow_checks']}")
        else:
            check("W3 FAB_NORM_ONLY=1 keeps the experts in the optimizer (the arm's point)",
                  in_opt == 3, f"fabric tensors (A, B, halt_b) in base_params: {in_opt}")


def w4():
    obs, nc, fo = [], [], []

    def ob(orig):
        def f(*a, **k):
            r = orig(*a, **k)
            obs.append(int(r.did))
            return r
        return f

    def ncf(orig):
        def f(*a, **k):
            nc.append(int(k["did"]))
            return orig(*a, **k)
        return f

    def fob(orig):
        def f(*a, **k):
            d = k["domain_id"]
            fo.append(list(d) if isinstance(d, (list, tuple)) else [int(d)])
            return orig(*a, **k)
        return f

    sysm = build(OPT_BATCH_WINDOWS=2)
    with _Patch(loop.dom_api, "observe", ob), _Patch(loop.dom_api, "note_competence", ncf), \
            _Patch(loop.fab_api, "observe", fob):
        res = loop.run(sysm, max_windows=8, progress=False)
    rows = [obs[2 * i:2 * i + 2] for i in range(len(fo))]
    check("W4 at OPT_BATCH_WINDOWS=2 FAB.observe gets one domain id per window",
          bool(fo) and fo == rows, f"windows' dids {rows}; FAB.observe got {fo}")
    check("W4 DOM.note_competence is called once per window, on that window's id",
          nc == obs[:len(nc)] and len(nc) == len(obs), f"{len(nc)} call(s) for {len(obs)} windows")
    books = res.report.get("LOOP(flush books)")
    check("W4 loop.flush_mixed_domain is seeded at batch > 1",
          isinstance(books, dict) and "loop.flush_mixed_domain" in books, f"{books!r}")


def w5():
    sysm = build(LM_MASK_DEAD_ROWS=1, FAB_HALT=0)
    res = loop.run(sysm, max_windows=2, progress=False)
    ok = all(math.isfinite(x) for x in res.loss_curve) and len(res.loss_curve) == 2
    check("W5 the vote over masked logits is finite at LM_MASK_DEAD_ROWS=1 FAB_HALT=0", ok,
          f"loss curve {[round(x, 6) for x in res.loss_curve]}")


def w6():
    env = dict(os.environ)
    env.update(BASE)
    env.update({"FAB_HOP_MODE": "transition", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"})
    p = subprocess.run([sys.executable, os.path.join(_ROOT, "run.py"), "--max-windows", "1",
                        "--quiet"], cwd=_ROOT, env=env, capture_output=True, text=True, timeout=600)
    ok = p.returncode == 2 and "REFUSED: FAB_HOP_MODE='transition'" in p.stdout \
        and "Traceback" not in p.stderr
    check("W6 FAB_HOP_MODE=transition prints REFUSED and exits 2", ok,
          f"rc={p.returncode}; first stdout line {p.stdout.splitlines()[:1]!r:.100}")


def main():
    w1()
    w2()
    w3()
    w4()
    w5()
    w6()
    print(f"\n{len(FAILS)} FAIL(s)" + (": " + ", ".join(FAILS) if FAILS else ""))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
