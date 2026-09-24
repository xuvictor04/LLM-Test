"""WHAT A RESUME PUTS BACK, AND WHAT IT REFUSES. Driven through the real composition root with an
in-memory Snapshot of a short real run, so nothing is written to disk.

    python3 tests/test_resume.py        # exit 0 = every check passed

WHY IT EXISTS (the resume-restore repair, 2026-09-24; Q-SIG-2, Q-OPT-8, Q-CAP-3, Q-CKPT-4 and
Q-DOM-1 in docs/04_CONTRACT.md). Every one of these was a restore path that dropped its own
refusal, or a piece of state that did not cross the boundary, and none of them failed anything:

  R1  A REFUSED LM RESTORE STOPS THE RUN. LM.load_state refuses by RETURNING a LoadReport and the
      root discarded it, so a TOK_MAX_BYTES change trained a random model under the parent's
      optimizer, fabric and memory. The refusal must reach System.refusals, and loop.run must not
      train a System that carries one.
  R2  A WIDENED RESUME KEEPS ITS OPTIMIZER. FAB_SLOTS / LM_VOCAB_SLOTS widening made OPT.load_state
      refuse on param_group_shape, which the root also discarded: empty moments, opt_step 0, a
      re-run warmup. A dim-0 widening must restore with padded moments; any other shape change
      must still refuse (the L50 guard).
  R3  THE WARM-UP IS NOT RE-RUN ON A RESTORED ENCODER, and the report is the parent's.
  R4  THE LM COUNTERS, THE DOM AND MEM STREAMS AND THE APPEARANCE COUNTER CROSS THE BOUNDARY.
  R5  THE CAPACITY VALVE: a checkpoint's cap is taken only on an arm armed now AND when it was
      saved, under the key CAP.state writes; CAP.restore no longer writes caps.
  R6  FAB'S SIDECAR RECORDS dk AND emb_hid, not d_model under dk's name, and refuses on them.
"""
import os
import sys

_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(_ROOT, "src"))

import torch                                                       # noqa: E402
torch.set_num_threads(1)

from spine import lever as _lever                                  # noqa: E402
from spine import rng                                              # noqa: E402
from spine import loop                                             # noqa: E402
from spine import assemble                                         # noqa: E402
from spine.compose import compose, _geometry_manifest              # noqa: E402
from ckpt import api as ckpt_api                                   # noqa: E402
from capacity import api as cap_api                                # noqa: E402
from fabric import api as fab_api                                  # noqa: E402
from lm import api as lm_api                                       # noqa: E402
from sig import api as sig_api                                     # noqa: E402
from world import api as world_api                                 # noqa: E402

FAILS = []
# SMALL ON PURPOSE: 256 founding experts in 512 slots keeps the fabric -- which dominates the
# optimizer state -- a tenth of its shipped size, so R2's padding is checked on real tensors quickly.
BASE = {"DATA_STREAM_BYTES": "60000", "SIG_WARMUP": "20", "FAB_N0": "256", "FAB_SLOTS": "512"}
PARENT_WINDOWS = 12


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
    return compose(environ=e, restored=restored)


def snapshot_of(sysm, clock_step):
    """The Snapshot CKPT.load would return for a save of `sysm` -- the same payload and the same
    recorded geometry spine/loop.py::_save writes, held in memory."""
    recorded = dict(_geometry_manifest(sysm))
    for k, v in world_api.geometry(sysm.configs["WORLD"], sysm.world).items():
        recorded.setdefault(k, v)
    return ckpt_api.Snapshot(payload=loop._payload(sysm), geometry=recorded, step=int(clock_step),
                             epoch=0, best_state=None, resume=None)


def parent():
    p = build()
    loop.run(p, max_windows=PARENT_WINDOWS, progress=False)
    return p, snapshot_of(p, PARENT_WINDOWS)


def r1(snap):
    c = build(restored=snap, TOK_MAX_BYTES=12)
    named = [r for r in c.refusals if r.startswith("LM.load_state refused")]
    check("R1 a refused LM restore is carried onto System.refusals",
          bool(named) and c.lm_load is not None and c.lm_load.refused, named[:1])
    check("R1 the refusal names the lever an operator moves (TOK_MAX_BYTES), not a wire",
          bool(named) and "TOK_MAX_BYTES" in named[0] and "LM_MAX_TOKEN_BYTES" not in named[0])
    try:
        loop.run(c, max_windows=PARENT_WINDOWS + 1, progress=False)
        check("R1 loop.run refuses a System carrying refusals", False, "it trained")
    except RuntimeError as e:
        check("R1 loop.run refuses a System carrying refusals", "refusal" in str(e))
    ok = build(restored=snap)
    check("R1 control: an unchanged resume restores LM and carries no refusal",
          not ok.refusals and ok.lm_load is not None and not ok.lm_load.refused, ok.refusals[:1])
    return ok


def r2(snap):
    saved = snap.payload["OPT"]
    for env, n_wide in (({"FAB_SLOTS": 640}, 2), ({"LM_VOCAB_SLOTS": 4352}, 3)):
        c = build(restored=snap, **env)
        o = c.optimizer
        live, was = o.base.state_dict()["state"], saved["base"]["state"]
        wide = [k for k in was if tuple(was[k]["exp_avg"].shape) != tuple(live[k]["exp_avg"].shape)]
        prefix = all(torch.equal(live[k]["exp_avg_sq"][:was[k]["exp_avg_sq"].shape[0]],
                                 was[k]["exp_avg_sq"])
                     and float(live[k]["exp_avg_sq"][was[k]["exp_avg_sq"].shape[0]:].abs().sum()) == 0.0
                     for k in wide)
        check(f"R2 {env}: OPT restores with {n_wide} widened tensor(s) and the parent's step",
              not c.refusals and o.counters["opt.ckpt.loaded"] == 1
              and o.counters.get("opt.ckpt.moments_widened") == n_wide == len(wide)
              and int(o.opt_step) == int(saved["opt_step"]) and o.lr_prev == saved["lr_prev"],
              f"refusals={c.refusals[:1]} widened={o.counters.get('opt.ckpt.moments_widened')} "
              f"opt_step={int(o.opt_step)}")
        check(f"R2 {env}: the saved rows keep their moments and the new rows start at zero", prefix)
    # THE L50 GUARD STILL STANDS for anything that is not a dim-0 widening.
    c = build()
    live_shape = c.optimizer.param_group_shape
    bent = tuple((n, k, tuple(((s[0], s[1] + 1) + tuple(s[2:])) if i == 0 and len(s) > 1 else s
                              for i, s in enumerate(shapes)))
                 for n, k, shapes in live_shape)
    rep = __import__("opt.api", fromlist=["load_state"]).load_state(
        c.configs["OPT"], c.optimizer, {**saved, "param_group_shape": bent})
    check("R2 a trailing-dimension change is still refused by name (ISSUES P1-L50)",
          rep.refused and "first differing tensor" in rep.reason, rep.reason[:160])


def r3(p, snap, c):
    enc_saved = snap.payload["SIG"]["encoder"]
    same = all(torch.equal(v, c.sig.encoder.state_dict()[k]) for k, v in enc_saved.items())
    check("R3 the restored encoder is not re-trained by warm_up", same)
    check("R3 the warm-up report is the parent's",
          c.warmup.verdict == p.warmup.verdict and list(c.warmup.curve) == list(p.warmup.curve)
          and c.warmup.steps == p.warmup.steps,
          f"{c.warmup} vs {p.warmup}")
    g = c.sig.gates["sig.adaptive_stop"]
    check("R3 sig.warmup_skipped_resume fired and the stop gate says why it cannot",
          c.sig.counters.get("sig.warmup_skipped_resume") == 1 and not g.reachable
          and "RESUMED" in g.reason)
    check("R3 a fresh learned run seeds the counter at 0 (armed, did not fire)",
          p.sig.counters.get("sig.warmup_skipped_resume") == 0)
    check("R3 the SIG stream continues where the parent left it",
          c.sig.rng.draws == snap.payload["SIG"]["rng"][1])


def r4(p, snap, c):
    saved = snap.payload["LM"]["counters"]
    check("R4 LM's counters come back (lm.embed.calls)",
          lm_api._COUNTS.get("lm.embed.calls") == saved.get("lm.embed.calls") is not None,
          f"{lm_api._COUNTS.get('lm.embed.calls')} vs {saved.get('lm.embed.calls')}")
    check("R4 DOM's rng stream continues",
          c.partition.rng.draws == p.partition.rng.draws
          and c.partition.rng.getstate() == p.partition.rng.getstate())
    check("R4 MEM's victim generator continues",
          torch.equal(c.store.gen.get_state(), p.store.gen.get_state()))
    check("R4 the appearance counter crosses",
          c.token_seen is not None and torch.equal(c.token_seen.cpu(), p.token_seen.cpu()))


def r5():
    def valve(**env):
        _lever._reopen_assembly()
        rng.reset_issued()
        e = {"FAB_N0": "256", "FAB_SLOTS": "512"}
        e.update({k: str(v) for k, v in env.items()})
        cfgs, _, _ = assemble.build(environ=e)
        return cfgs["CAP"]

    cap = valve(CAP_TARGETS="experts")
    v = cap_api.new_valve(cap)
    v.cap_experts = 300                                    # an EARNED cap, below the ceiling
    earned = cap_api.state(v)
    check("R5 CAP.state records each arm's provenance",
          earned.get("armed_experts") is True and earned.get("armed_vocab") is False
          and earned.get("hard_experts") == 512)
    for env, want_cap, want_origin in (
            ({"CAP_TARGETS": "experts"}, 300, "checkpoint (lifted to 300"),
            ({"CAP_TARGETS": "off"}, 512, "off"),
            ({"CAP_TARGETS": "vocab"}, 512, "sentinel"),
            ({"CAP_TARGETS": "experts", "FAB_SLOTS": "1024"}, 300, "checkpoint (lifted to 300")):
        cfg = valve(**env)
        nv = cap_api.new_valve(cfg, restored=earned)
        cap_api.restore(cfg, nv, earned)
        check(f"R5 an earned cap under {env}: {want_cap}, origin '{want_origin}...'",
              nv.cap_experts == want_cap and nv.origin[0].startswith(want_origin),
              f"{nv.cap_experts} {nv.origin[0]}")
    off = cap_api.state(cap_api.new_valve(valve(CAP_TARGETS="off")))
    cfg = valve(CAP_TARGETS="experts", FAB_SLOTS="1024")
    nv = cap_api.new_valve(cfg, restored=off)
    cap_api.restore(cfg, nv, off)
    check("R5 a cap saved on an UNARMED arm is not installed as a soft cap after a widening",
          nv.cap_experts == 1024 and "UNARMED" in nv.origin[0], f"{nv.cap_experts} {nv.origin[0]}")
    at_hard = cap_api.state(cap_api.new_valve(valve(CAP_TARGETS="experts")))
    nv = cap_api.new_valve(cfg, restored=at_hard)
    check("R5 an armed cap AT its saved ceiling follows the ceiling to the live one",
          nv.cap_experts == 1024, f"{nv.cap_experts} {nv.origin[0]}")
    pinned = valve(CAP_TARGETS="experts", CAP_FAB_START=400)
    nv = cap_api.new_valve(pinned, restored=earned)
    cap_api.restore(pinned, nv, earned)
    check("R5 an operator's request still wins, and the refused checkpoint cap is counted",
          nv.cap_experts == 400 and nv.counters.get("cap.state_refused") == 1)


def r6(snap):
    side = snap.payload["FAB"]["sidecar"]
    check("R6 the FAB sidecar records dk and emb_hid as the levers size them",
          side.get("dk") == 32 and side.get("emb_hid") == 128 and side.get("d_model") == 128, side)
    try:
        build(restored=snap, FAB_DK=16)
        check("R6 a FAB_DK change is refused", False, "composed")
    except Exception as e:                                  # noqa: BLE001 -- the gate or FAB
        check("R6 a FAB_DK change is refused", "FAB_DK" in str(e) or "dk" in str(e), str(e)[:120])
    # AND FAB'S OWN REFUSAL FIRES ON IT, which it could not while the sidecar's dk was d_model: the
    # gate above answers first on a real resume, so FAB's check is driven directly.
    c16 = build(FAB_DK=16)
    try:
        fab_api.load_state_dict(c16.configs["FAB"], c16.fabric, snap.payload["FAB"], sidecar=side)
        check("R6 FAB.load_state_dict itself refuses a dk change", False, "restored")
    except Exception as e:                                  # noqa: BLE001
        check("R6 FAB.load_state_dict itself refuses a dk change", "refused on dk" in str(e),
              str(e)[:120])
    c = build()
    old = dict(side)
    old["dk"] = old.pop("d_model")                          # the pre-2026-09-24 sidecar shape
    old.pop("emb_hid")
    try:
        fab_api.load_state_dict(c.configs["FAB"], c.fabric, snap.payload["FAB"], sidecar=old)
        check("R6 an old-format sidecar (dk meaning d_model) still restores", True)
    except Exception as e:                                  # noqa: BLE001
        check("R6 an old-format sidecar (dk meaning d_model) still restores", False, str(e)[:160])


def main():
    p, snap = parent()
    c = r1(snap)
    r3(p, snap, c)
    r4(p, snap, c)
    r2(snap)
    r5()
    r6(snap)
    print(f"=== {len(FAILS)} failing" + (f": {FAILS}" if FAILS else ""))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
