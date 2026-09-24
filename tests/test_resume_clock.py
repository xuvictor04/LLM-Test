"""WHAT A RESUME DOES TO THE CLOCK, THE EPOCH AND max_windows. Driven through the real composition
root with an in-memory Snapshot of a short real run, so nothing is written to disk.

    python3 tests/test_resume_clock.py        # exit 0 = every check passed

WHY IT EXISTS (the resume-clock repair, 2026-09-24; Q-RUN-9 .. Q-RUN-12 in docs/04_CONTRACT.md).
Each of these was driven on the tree before the repair, and none of them failed anything:

  C1  A PARENT SAVED PARTWAY THROUGH AN ACCUMULATION RESUMES AND STEPS. The clock restarted its
      backward count at 0 while OPT restored the parent's, so at OPT_ACCUM=4 a misaligned child
      took 0 optimizer steps and then raised at R before the final save.
  C2  THE CADENCE SCHEDULE CROSSES THE BOUNDARY. Every gate re-seeded at the resumed step and fired
      a whole period late; the ledger restarted at 0.
  C3  max_windows COUNTS THIS PROCESS'S WINDOWS. A resume given N <= its restored step trained one.
  C4  A RESUME OF A FINISHED RUN IS REFUSED, and loop.run will not spend a window on a finished clock.
  C5  A RESUME DRAWS THE EPOCH IT RESUMED IN, not epoch 0.
  C6  A STOP ON AN EPOCH BOUNDARY STOPS THERE, without drawing the next epoch or training a window.
  C7  THE EPOCH HOLDS (len(ids) - 1) // ctx WINDOWS, so no flush is counted without a backward.
  C8  THE MINT MARK STARTS AT THE MINT COUNT THE RUN ENTERED WITH, not at 0.
  C9  A MID-EPOCH RESUME IS WARNED; A BOUNDARY RESUME IS NOT.
"""
import dataclasses
import os
import sys

_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(_ROOT, "src"))

import torch                                                       # noqa: E402
torch.set_num_threads(1)

from spine import lever as _lever                                  # noqa: E402
from spine import rng                                              # noqa: E402
from spine import loop                                             # noqa: E402
from spine import compose as C                                     # noqa: E402
from ckpt import api as ckpt_api                                   # noqa: E402
from data import api as data_api                                   # noqa: E402
from opt import api as opt_api                                     # noqa: E402
from world import api as world_api                                 # noqa: E402

FAILS = []
# SMALL ON PURPOSE, the same base tests/test_resume.py uses: a tenth-size fabric keeps each compose
# to a few seconds.
BASE = {"DATA_STREAM_BYTES": "60000", "SIG_WARMUP": "20", "FAB_N0": "256", "FAB_SLOTS": "512"}


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" -- {detail}" if detail else ""))
    if not ok:
        FAILS.append(name)


def build(restored=None, **env):
    """One real System per configuration; the assembly latch and the rng registry are reopened
    first because each call here stands for a different process."""
    _lever._reopen_assembly()
    rng.reset_issued()
    e = dict(BASE)
    e.update({k: str(v) for k, v in env.items()})
    return C.compose(environ=e, restored=restored)


def snapshot_of(sysm, *, epoch=None):
    """The Snapshot CKPT.load would return for a save of `sysm` -- the payload and recorded geometry
    spine/loop.py::_save writes, held in memory, at the clock's own step and epoch unless told."""
    recorded = dict(C._geometry_manifest(sysm))
    for k, v in world_api.geometry(sysm.configs["WORLD"], sysm.world).items():
        recorded.setdefault(k, v)
    c = sysm.clock.counters()
    return ckpt_api.Snapshot(payload=loop._payload(sysm), geometry=recorded, step=int(c["step"]),
                             epoch=int(c["epoch"]) if epoch is None else int(epoch),
                             best_state=None, resume=None)


def c1_accumulation():
    p = build(OPT_ACCUM=4)
    loop.run(p, max_windows=6, progress=False)
    snap = snapshot_of(p)
    check("C1 control: the parent ended misaligned (backward=6, step=1 at OPT_ACCUM=4)",
          int(p.optimizer.n_backward) == 6 and int(p.optimizer.opt_step) == 1)
    c = build(restored=snap, OPT_ACCUM=4)
    k = c.clock.counters()
    check("C1 the clock is seeded from OPT's restored backward and step counts",
          int(k["backwards"]) == 6 and int(k["opt_steps"]) == 1, {n: int(k[n]) for n in
                                                                  ("backwards", "opt_steps")})
    check("C1 the parent's lost partial accumulation is counted",
          c.optimizer.counters.get("opt.ckpt.partial_accum_dropped") == 2,
          c.optimizer.counters.get("opt.ckpt.partial_accum_dropped"))
    res = loop.run(c, max_windows=6, progress=False)
    # BACKWARD 6 -> 12 CROSSES 8 AND 12, SO TWO STEPS; the old (n - base) // k said 6 // 4 = 1.
    check("C1 the child steps on OPT's schedule (backward 6 -> 12, steps 1 -> 3)",
          int(c.optimizer.n_backward) == 12 and int(c.optimizer.opt_step) == 3
          and res.opt_steps == 3, f"n_backward={int(c.optimizer.n_backward)} "
                                  f"opt_step={int(c.optimizer.opt_step)} res={res.opt_steps}")
    # OPT.counters RAISES on a broken invariant, so returning is the check; the gate's printed
    # value is the comparison it made.
    g = [x for x in opt_api.counters(c.configs["OPT"], c.optimizer).values()
         if getattr(x, "name", None) == "opt.accum.invariant"]
    check("C1 OPT.counters holds the invariant as floor(n/k) - floor(base/k)",
          bool(g) and g[0].value == "12 // 4 - 6 // 4" and g[0].threshold == 2,
          g[0].line() if g and hasattr(g[0], "line") else g)
    # A RAISING R STAGE STILL TAKES THE FINAL SAVE FIRST.
    c2 = build(restored=snap, OPT_ACCUM=4)
    saved, real_save, real_counters = [], loop._save, opt_api.counters

    def _spy_save(sysm, clock, reason, suffix=""):
        saved.append(reason)
        return False

    def _boom(*a, **k):
        raise ValueError("synthetic R-stage failure")
    loop._save, opt_api.counters = _spy_save, _boom
    try:
        loop.run(c2, max_windows=1, progress=False)
        check("C1 a raising R stage re-raises", False, "it returned")
    except ValueError:
        check("C1 a raising R stage takes the final save before re-raising", saved == ["final"],
              saved)
    finally:
        loop._save, opt_api.counters = real_save, real_counters


def c2_cadences_c3_max_windows_c9_replay():
    p = build(DOM_MANAGE_EVERY=5)
    loop.run(p, max_windows=12, progress=False)
    led = p.cadences.ledger()["dom.manage"]
    check("C2 control: the parent fired dom.manage at 6 and 11", led[1] == 2 and int(led[2]) == 11,
          led)
    snap = snapshot_of(p)
    check("C2 the checkpoint payload carries RUN's cadence state and clock position",
          "RUN" in snap.payload and snap.payload["RUN"]["clock"]["in_epoch"] == 12,
          snap.payload.get("RUN", {}).get("clock"))
    c = build(restored=snap, DOM_MANAGE_EVERY=5)
    check("C2 the ledger is restored at compose", c.cadences.ledger()["dom.manage"][:2] == led[:2],
          c.cadences.ledger()["dom.manage"])
    replay = [w for w in c.warnings if w.startswith("MID-EPOCH RESUME REPLAYS ITS EPOCH")]
    check("C9 a mid-epoch resume is warned with the windows it replays",
          len(replay) == 1 and "saved 12 window(s) into epoch 0" in replay[0], replay[:1])
    res = loop.run(c, max_windows=6, progress=False)
    led2 = res.cadence_ledger["dom.manage"]
    # ON THE PARENT'S SCHEDULE THE NEXT FIRE IS 16; RE-SEEDED AT 13 IT WOULD HAVE BEEN 18.
    check("C2 the child continues the parent's schedule (next dom.manage fire at 16, not 18)",
          led2[1] == 3 and int(led2[2]) == 16, led2)
    check("C3 max_windows counts this process's windows (6 more, from 12 to 18)",
          res.windows == 18 and res.windows_here == 6, f"windows={res.windows} "
                                                       f"here={res.windows_here}")
    # A PRE-FIX CHECKPOINT (NO 'RUN' KEY) STILL RESUMES, SEEDING LAZILY AS BEFORE.
    old = dataclasses.replace(snap, payload={k: v for k, v in snap.payload.items() if k != "RUN"})
    o = build(restored=old, DOM_MANAGE_EVERY=5)
    check("C2 a checkpoint without payload['RUN'] resumes and seeds lazily",
          not o.refusals and o.cadences.ledger()["dom.manage"][:2] == (0, 0),
          o.cadences.ledger()["dom.manage"])
    return p


def c4_finished_c5_epoch_draw(p):
    # A BOUNDARY SNAPSHOT: epoch 1 with the clock at window 0 of it, which is what a parent stopped
    # on the roll records (C6 drives that stop for real).
    fin = snapshot_of(p, epoch=1)
    fin.payload["RUN"]["clock"]["in_epoch"] = 0
    # compose() RAISES RefusedRun (2026-09-24); the partial System, clock included, rides on it.
    try:
        build(restored=fin)
        check("C4 compose raises RefusedRun on a finished resume", False, "compose returned")
        return p
    except C.RefusedRun as e:
        c = e.system
        check("C4 compose raises RefusedRun on a finished resume, before the SIG warm-up",
              c.warmup is None and c.clock is not None, f"stage={e.stage!r}")
    named = [r for r in c.refusals if "has already completed epoch 1 of RUN_EPOCHS=1" in r]
    check("C4 a resume of a finished run is refused at compose", bool(named), c.refusals[:1])
    try:
        loop.run(c, max_windows=1, progress=False)
        check("C4 loop.run does not train a finished System", False, "it trained")
    except RuntimeError:
        check("C4 loop.run does not train a finished System", True)
    # THE SAME CLOCK, BUILT WITHOUT THE REFUSAL, IS STILL NOT SPENT: loop.run's own guard.
    c.refusals.clear()
    try:
        loop.run(c, max_windows=1, progress=False)
        check("C4 loop.run's own guard refuses a finished clock", False, "it trained")
    except RuntimeError as e:
        check("C4 loop.run's own guard refuses a finished clock", "already completed" in str(e))
    # C5: WHICH EPOCH compose DRAWS.
    drawn, real = [], data_api.draw_stream

    def _spy(*a, **k):
        drawn.append(k.get("epoch"))
        return real(*a, **k)
    data_api.draw_stream = _spy
    try:
        b = build(restored=fin, RUN_EPOCHS=2, DATA_RESAMPLE=1)
        check("C5 a child resumed at epoch 1 draws epoch 1's stream", drawn == [1], drawn)
        check("C9 a boundary resume (in_epoch 0) is not warned as a replay",
              not any(w.startswith("MID-EPOCH") for w in b.warnings)
              and not b.refusals, b.refusals[:1])
        # AT DATA_RESAMPLE=0 AN EPOCH >= 1 RESUME CANNOT TRAIN: RUN refuses RUN_EPOCHS > 1 without
        # resampling, and at RUN_EPOCHS=1 epoch 1 is the finished resume C4 refuses.
        # compose() RAISES RefusedRun at its `refuse` stage (2026-09-24), before the stream row.
        try:
            build(restored=fin, RUN_EPOCHS=2, DATA_RESAMPLE=0)
            check("C5 the DATA_RESAMPLE=0 arm at epoch >= 1 is refused", False, "composed")
        except C.RefusedRun as e:
            check("C5 the DATA_RESAMPLE=0 arm at epoch >= 1 is refused before its stream is drawn",
                  any("resampling off" in r for r in e.refusals) and e.system.stream is None,
                  e.refusals[:1])
    finally:
        data_api.draw_stream = real


def c6_stop_on_boundary():
    s = build(DATA_STREAM_BYTES=4000, RUN_EPOCHS=2, DATA_RESAMPLE=1)
    wie = int(s.clock.counters()["windows_in_epoch"])
    drawn, real = [], data_api.draw_stream

    def _spy(*a, **k):
        drawn.append(k.get("epoch"))
        return real(*a, **k)
    data_api.draw_stream = _spy
    try:
        res = loop.run(s, max_windows=wie, progress=False)
    finally:
        data_api.draw_stream = real
    c = s.clock.counters()
    check("C6 a stop on an epoch boundary stops there (no draw, no extra window, in_epoch 0)",
          res.windows == wie and int(c["epoch"]) == 1 and c["in_epoch"] == 0 and drawn == [],
          f"windows={res.windows} of {wie} epoch={int(c['epoch'])} in_epoch={c['in_epoch']} "
          f"draws={drawn}")


def c7_tail_c8_mint_mark():
    for bw in (1, 2):
        s = build(OPT_BATCH_WINDOWS=bw)
        ctx = int(s.configs["LM"].ctx)
        seg = s.segmentation
        s.segmentation = dataclasses.replace(seg, ids=seg.ids[:6 * ctx])
        s.clock.begin_epoch(C._windows_in_epoch(s))
        check(f"C7 OPT_BATCH_WINDOWS={bw}: a {6 * ctx}-id segmentation holds 5 windows, not 6",
              s.clock.counters()["windows_in_epoch"] == 5)
        # C8 rides on the bw=1 run: the run is entered with 2 tokens already minted.
        if bw == 1:
            s.vocab.counters["tok.mint"] = 2
        res = loop.run(s, progress=False)
        c = s.clock.counters()
        check(f"C7 OPT_BATCH_WINDOWS={bw}: every flush has a backward and no window is lost",
              int(c["flushes"]) == int(c["backwards"]) and int(c["step"]) == 5
              and c["dropped_windows"] == 5 % bw and not any("ran out" in w for w in res.warnings),
              {k: int(c[k]) for k in ("step", "flushes", "backwards", "dropped_windows")})
        if bw == 1:
            mint = [w for w in res.warnings if "minted" in w]
            check("C8 mints the run entered with are counted as in the stream, not stranded",
                  any("2 of them were in the vocabulary at the last re-segmentation" in w
                      for w in mint) and not any("AFTER THE LAST RE-SEGMENTATION" in w
                                                 for w in mint), mint[:2])


if __name__ == "__main__":
    c1_accumulation()
    parent = c2_cadences_c3_max_windows_c9_replay()
    c4_finished_c5_epoch_draw(parent)
    c6_stop_on_boundary()
    c7_tail_c8_mint_mark()
    print(f"=== {len(FAILS)} failure(s)")
    sys.exit(1 if FAILS else 0)
