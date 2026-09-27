"""THE RATE A CONTINUED RUN STARTS AT (OPT_LR_CONTINUE) AND THE IN-RUN HORIZON REVISION'S OFF ARM
(OPT_HORIZON_REVISE). Proposal 05 §8 1.4; register rows TREE-OPT_HORIZON_REVISE-LEVER, NEW-05, C01;
Q-OPT-12 in docs/04_CONTRACT.md.

    python3 tests/test_lr_continue.py        # exit 0 = every check passed

WHY IT EXISTS. Before §8 1.4 a continued run -- a resume whose horizon differs from its parent's --
started at whatever rate the parent's SHAPE implied: for a finished parent, the floor for good after a
revision log, and otherwise the cosine at the resumed step on the new horizon (about 0.48 of peak at
756 KB, 0.22 at 3.78 MB). Nothing chose it, and the only switch near it (the planned OPT_HORIZON_REVISE) would have
moved it silently (C01). These checks pin the known answers the register names for the build:

  L1  'as_logged' IS TODAY'S PRICING. A no-log parent's child re-prices on the live horizon through
      the untouched _schedule, step for step; a logged parent's child sits at the floor for good and
      equals the saved horizon plus the log plus load_state's resume revision. The label
      opt.continue.regime reads 'as_logged' on the resume and no opt.continue.* key exists on a
      fresh run.
  L2  EACH REGIME'S FIRST STEP EQUALS ITS CLOSED FORM (floor, plateau, rewarm; ramp 50 and 0; both
      parents), through lr_at and through the first maybe_step alike; plateau holds its target, floor
      is constant, rewarm decays monotonically to the floor at the session end; the steps priced and
      the lr_prev clear are counted.
  L3  A SAME-LENGTH RESUME OF A CONTINUED SESSION IS EXACT, and it keeps the recorded regime even when
      the operator asks for another one -- the report line says the ask was not applied.
  L4  OPT_HORIZON_REVISE IS IN-RUN ONLY: at the load boundary True and False give identical rates
      under every regime on both parents, and load_state's resume revision is appended under both.
      In-run, False makes revise_horizon inert, logged nowhere, and counted twice over.
  L5  A 'rewarm' SESSION'S OWN ACT RE-MAPS ITS DECAY LR-CONTINUOUSLY to the floor at the revised end;
      under 'floor' and 'plateau' the same act is logged and moves nothing.
  L6  AT OPT_LR_SCHED=none A REGIME IS INERT AND COUNTED; the shift re-warm still attenuates a regime,
      and the floor still bounds it.
  L7  INTEGRATED THROUGH THE COMPOSITION ROOT at a real epoch boundary (RUN_EPOCHS=2, DATA_RESAMPLE=1):
      each regime's first resumed rate is its closed form, the loop steps at it, the label reaches
      OPT.counters, a rewarm whose projected session end falls inside its ramp is reported as having
      no decay phase; and an act-parent's boundary child trains identical losses at
      OPT_HORIZON_REVISE True and False -- the register's known answer that the lever leaves a
      continued run's LR unchanged.
  L8  'regulated' IS REFUSED BY NAME (NotBuilt, NEW-04), and a misspelt regime is refused at
      resolution rather than falling to a default.

WHAT THIS FILE CANNOT SEE: whether any regime learns better. Every check here is operation on CPU --
a run, a finite rate, a closed form, a counter. The arms are decided on GPU (§8 5.2, [OWNER] O6).
"""
import copy
import dataclasses
import io
import math
import os
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
from spine import assemble                                         # noqa: E402
from spine import units as U                                       # noqa: E402
from spine import compose as C                                     # noqa: E402
from spine.gate import NotBuilt                                    # noqa: E402
from spine.lever import LeverError                                 # noqa: E402
from ckpt import api as ckpt_api                                   # noqa: E402
from opt import api as opt_api                                     # noqa: E402
from world import api as world_api                                 # noqa: E402

FAILS = []
P = 2e-3                     # OPT_LR's shipped default: every closed form below is in these units
F = 0.05                     # OPT_LR_MIN_FRAC's shipped default
REL = 1e-12


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" -- {detail}" if detail else ""))
    if not ok:
        FAILS.append(name)


def close(a, b):
    return math.isclose(a, b, rel_tol=REL, abs_tol=0.0)


# ---- the OPT-level harness: a real resolved Config, a real OPT.build, one 3-element parameter ----
def cfg(**env):
    _lever._reopen_assembly()
    configs, _, _ = assemble.build(environ={k: str(v) for k, v in env.items()})
    return configs["OPT"]


def fresh(opt, run_windows):
    p = torch.nn.Parameter(torch.ones(3))
    st = opt_api.build(opt, param_groups={"base": [p], "encoder": []},
                       run_windows=U.Windows(run_windows))
    return st, p


def step(opt, st, p, shift_at=None):
    opt_api.scaled_backward(opt, st, (p * p).sum())
    return opt_api.maybe_step(opt, st, shift_at=shift_at)


def child(saved, run_windows=400, **env):
    """A resumed OPT: built at `run_windows`, then load_state from a DEEP COPY of the parent's
    state_dict -- torch's load_state_dict may keep the tensors it is handed, and two children must
    not share one set of moments."""
    o = cfg(**env)
    st, p = fresh(o, run_windows)
    rep = opt_api.load_state(o, st, copy.deepcopy(saved))
    return o, st, p, rep


def untouched(opt, horizon, s, eff=None):
    """The as-built schedule at step s, called with NO continuation record: today's function."""
    return opt_api._schedule(
        lr=float(opt.lr), sched=str(opt.lr_sched), min_frac=float(opt.lr_min_frac),
        restarts=bool(opt.lr_restarts), decay=float(opt.lr_decay),
        shift_warm=int(opt.lr_shift_warm), restart_amp=1.0, shift_at=None,
        horizon=horizon, step=s, eff_step=eff)[0]


def parents():
    """(no-log parent's state_dict, its last rate), (logged parent's state_dict, its last rate).
    No log: 200 windows run to the end. Logged: 200 windows revised at step 100 to 150 (the act
    shortened the run) and run to its revised end."""
    o = cfg()
    st, p = fresh(o, 200)
    out = [step(o, st, p) for _ in range(200)]
    nolog = (copy.deepcopy(opt_api.state_dict(o, st)), out[-1].lr)
    st2, p2 = fresh(o, 200)
    out2 = [step(o, st2, p2) for _ in range(100)]
    opt_api.revise_horizon(o, st2, run_windows=150)
    out2 += [step(o, st2, p2) for _ in range(50)]
    logged = (copy.deepcopy(opt_api.state_dict(o, st2)), out2[-1].lr)
    return nolog, logged


def l1(nolog, logged):
    sd, r0 = nolog
    o, c, p, rep = child(sd)
    k = c.counters
    check("L1 no-log parent, 'as_logged': the horizon changed, lr_prev cleared, a boundary, no record",
          rep.restored and k["opt.ckpt.horizon_changed"] == 1 and c.lr_prev == 0.0
          and k["opt.ckpt.lr_prev_cleared"] == 1 and k["opt.continue.boundary"] == 1
          and c.continuation is None and "opt.continue.priced" not in k,
          {n: k.get(n) for n in ("opt.ckpt.horizon_changed", "opt.ckpt.lr_prev_cleared",
                                 "opt.continue.boundary")})
    check("L1 ... and the LoadReport's reason is the one load_state returned before §8 1.4",
          rep.reason.startswith("the horizon changed across the boundary and the LIVE one is in "
                                "force."), rep.reason[:80])
    probe = [opt_api.lr_at(o, c, U.Steps(s)) for s in range(201, 401)]
    outs = [step(o, c, p) for _ in range(200)]
    want = [untouched(o, c.horizon, s) for s in range(201, 401)]
    check("L1 ... every child step, through lr_at AND maybe_step, IS the untouched _schedule on the "
          "live horizon (exact)", probe == want and [x.lr for x in outs] == want,
          f"first {outs[0].lr} vs {want[0]}")
    check("L1 ... the first resumed step is not a restart", not outs[0].restart)
    led = opt_api.counters(o, c)
    check("L1 ... the label reads 'as_logged' on the resume",
          led.get("opt.continue.regime") == "as_logged"
          and any(ln.startswith("opt.continue: regime in force 'as_logged'")
                  for ln in led["opt.report_lines"]), led.get("opt.continue.regime"))

    sd, r0 = logged
    o, c, p, rep = child(sd)
    k = c.counters
    h = sd["horizon"]
    saved_h = opt_api.Horizon(run_steps=U.Steps(h["run_steps"]), warmup=U.Steps(h["warmup"]),
                              wavelength=U.Steps(h["wavelength"]), n_cycles=int(h["n_cycles"]))
    log = [tuple(r) for r in sd["horizon_revisions"]] + [(150, 400)]
    check("L1 logged parent, 'as_logged': the saved horizon back, the resume revision appended, a "
          "boundary, lr_prev NOT cleared (today's pricing is continuous here)",
          c.horizon == saved_h and c.horizon_revisions == log and k["opt.continue.boundary"] == 1
          and k.get("opt.ckpt.horizon_changed") == 0 and k["opt.ckpt.lr_prev_cleared"] == 0
          and c.lr_prev == r0 and c.continuation is None and rep.reason == "",
          f"{c.horizon_revisions}; lr_prev {c.lr_prev}")
    outs = [step(o, c, p) for _ in range(250)]
    want = [untouched(o, saved_h, s, opt_api._effective_step(saved_h, log, s))
            for s in range(151, 401)]
    check("L1 ... every child step is the floor for good -- lr x lr_min_frac -- and equals the saved "
          "horizon + log + (150, 400) through _effective_step (exact)",
          [x.lr for x in outs] == want and all(x.lr == P * F for x in outs)
          and not any(x.restart for x in outs), f"{outs[0].lr} vs {P * F}")

    o = cfg()
    st, p = fresh(o, 100)
    for _ in range(10):
        step(o, st, p)
    led = opt_api.counters(o, st)
    check("L1 a fresh run's ledger carries NO opt.continue.* key and no opt.horizon.revise_declined",
          not any(n.startswith("opt.continue.") for n in led)
          and "opt.horizon.revise_declined" not in led
          and not any(ln.startswith("opt.continue:") for ln in led["opt.report_lines"]),
          sorted(n for n in led if "continue" in n))


def closed_first(regime, w, r0, a, e):
    """The register's closed form for the first resumed step, a + 1, in absolute rate."""
    if regime == "floor":
        return P * F
    t = 0.25 if regime == "plateau" else 0.5
    if w > 0:
        return r0 + (t * P - r0) / w
    if regime == "plateau":
        return t * P
    return P * F + (t * P - P * F) * 0.5 * (1.0 + math.cos(math.pi / (e - a)))


def l2(nolog, logged):
    for tag, (sd, r0), a in (("no-log", nolog, 200), ("logged", logged, 150)):
        for regime in ("floor", "plateau", "rewarm"):
            for w in (50, 0):
                o, c, p, rep = child(sd, OPT_LR_CONTINUE=regime, OPT_LR_CONT_WARM=w)
                want = closed_first(regime, w, r0, a, 400)
                probe = opt_api.lr_at(o, c, U.Steps(a + 1))
                outs = [step(o, c, p) for _ in range(400 - a)]
                lrs = [x.lr for x in outs]
                k = c.counters
                check(f"L2 {tag} parent, {regime}, OPT_LR_CONT_WARM={w}: the first resumed step is "
                      f"the closed form (lr_at and maybe_step)",
                      close(probe, want) and close(lrs[0], want) and not outs[0].restart,
                      f"lr_at {probe!r}, stepped {lrs[0]!r}, closed form {want!r}")
                ok = k["opt.continue.priced"] == len(outs) and k["opt.continue.boundary"] == 1 \
                    and not any(x.restart for x in outs) and k["opt.ckpt.lr_prev_cleared"] == 1
                if regime == "floor":
                    ok = ok and all(x == P * F for x in lrs)
                    shape = "constant at lr x lr_min_frac"
                elif regime == "plateau":
                    ok = ok and all(x == 0.25 * P for x in lrs[max(w, 1) - 1:])
                    shape = "0.25 x lr at every j >= warm"
                else:
                    tail = lrs[max(w, 1) - 1:]
                    ok = ok and all(y <= x for x, y in zip(tail, tail[1:])) \
                        and close(lrs[-1], P * F) and tail[0] > P * F
                    shape = "monotone after the ramp and lr x lr_min_frac at the session end"
                check(f"L2 ... {shape}; opt.continue.priced counts {len(outs)} steps; lr_prev "
                      f"cleared once at the anchoring; no restart stamped", ok,
                      f"priced {k.get('opt.continue.priced')}, cleared "
                      f"{k.get('opt.ckpt.lr_prev_cleared')}, last {lrs[-1]!r}")


def l3(nolog):
    sd, r0 = nolog
    env = {"OPT_LR_CONTINUE": "rewarm", "OPT_LR_CONT_WARM": 50}
    o, u, pu, _ = child(sd, **env)
    uninterrupted = [step(o, u, pu).lr for _ in range(60)]
    o, c, pc, _ = child(sd, **env)
    first = [step(o, c, pc).lr for _ in range(30)]
    mid = copy.deepcopy(opt_api.state_dict(o, c))
    record = dict(c.continuation)
    for label, genv in (("the same env", env),
                        ("OPT_LR_CONTINUE=floor asked", dict(env, OPT_LR_CONTINUE="floor"))):
        og, g, pg, rep = child(mid, **genv)
        second = [step(og, g, pg).lr for _ in range(30)]
        k = g.counters
        check(f"L3 a same-length resume of a rewarm session ({label}) continues it exactly",
              first + second == uninterrupted and k["opt.continue.boundary"] == 0
              and g.continuation == record and rep.reason == ""
              and k["opt.continue.priced"] == 60,
              f"boundary {k.get('opt.continue.boundary')}, priced {k.get('opt.continue.priced')}")
        led = opt_api.counters(og, g)
        line = next((ln for ln in led["opt.report_lines"] if ln.startswith("opt.continue:")), "")
        if genv["OPT_LR_CONTINUE"] == "floor":
            check("L3 ... the recorded 'rewarm' governs, the label says so, and the line says the "
                  "asked 'floor' was NOT applied",
                  led["opt.continue.regime"] == "rewarm" and "was NOT applied" in line
                  and "OPT_LR_CONTINUE='floor'" in line, line[:200])


def l4(nolog, logged):
    for tag, (sd, _r0) in (("no-log", nolog), ("logged", logged)):
        for regime in ("as_logged", "floor", "plateau", "rewarm"):
            seqs, revs = [], []
            for flag in ("True", "False"):
                o, c, p, _ = child(sd, OPT_LR_CONTINUE=regime, OPT_LR_CONT_WARM=50,
                                   OPT_HORIZON_REVISE=flag)
                seqs.append([step(o, c, p).lr for _ in range(100)])
                revs.append((list(c.horizon_revisions), c.counters.get("opt.horizon.revisions"),
                             c.counters.get("opt.horizon.revise_declined")))
            want_log = 2 if tag == "logged" else 0
            check(f"L4 {tag} parent, {regime}: OPT_HORIZON_REVISE True and False price 100 child steps "
                  f"identically, and load_state's resume revision is appended under both",
                  seqs[0] == seqs[1] and revs[0][:2] == revs[1][:2]
                  and len(revs[0][0]) == want_log and revs[0][2] is None and revs[1][2] == 0,
                  f"{revs}")
    # IN-RUN, the off arm.
    o = cfg(OPT_HORIZON_REVISE="False")
    st, p = fresh(o, 200)
    seeded = st.counters.get("opt.horizon.revise_declined")
    for _ in range(100):
        step(o, st, p)
    got = opt_api.revise_horizon(o, st, run_windows=150)
    outs = [step(o, st, p).lr for _ in range(100)]
    want = [untouched(o, st.horizon, s) for s in range(101, 201)]
    k = st.counters
    check("L4 in-run at OPT_HORIZON_REVISE=False: revise_horizon returns None, logs nothing, counts "
          "revise_inert=1 and revise_declined 0 -> 1, and every later step is the unrevised schedule",
          got is None and st.horizon_revisions == [] and "opt.horizon.revisions" not in k
          and k.get("opt.horizon.revise_inert") == 1 and seeded == 0
          and k.get("opt.horizon.revise_declined") == 1 and outs == want,
          {n: k.get(n) for n in ("opt.horizon.revise_inert", "opt.horizon.revise_declined")})
    led = opt_api.counters(o, st)
    g = led.get("opt.horizon.revise")
    check("L4 ... Gate opt.horizon.revise is UNREACHABLE and names the lever and the declined count",
          g is not None and not g.reachable and "OPT_HORIZON_REVISE=False" in g.reason
          and "declined 1 revision" in g.reason, g.line()[:160] if g else None)
    o = cfg()
    st, p = fresh(o, 200)
    for _ in range(100):
        step(o, st, p)
    got = opt_api.revise_horizon(o, st, run_windows=150)
    g = opt_api.counters(o, st).get("opt.horizon.revise")
    check("L4 in-run at the default True: the revision is taken, revise_declined stays ABSENT, and the "
          "Gate FIRED", int(got) == 150 and st.horizon_revisions == [(100, 150)]
          and "opt.horizon.revise_declined" not in st.counters and g.fired,
          g.line()[:120] if g else None)


def l5(nolog):
    sd, _r0 = nolog
    a = 200
    o, c, p, _ = child(sd, OPT_LR_CONTINUE="rewarm", OPT_LR_CONT_WARM=50)
    for _ in range(80):
        step(o, c, p)
    before = opt_api.lr_at(o, c, U.Steps(a + 80))
    opt_api.revise_horizon(o, c, run_windows=350)
    after = opt_api.lr_at(o, c, U.Steps(a + 80))
    at_end = opt_api.lr_at(o, c, U.Steps(350))
    just_before = opt_api.lr_at(o, c, U.Steps(349))
    outs = [step(o, c, p).lr for _ in range(350 - a - 80)]
    check("L5 rewarm: an act in the session leaves the rate at the act unchanged and re-maps the "
          "decay to reach lr x lr_min_frac at the revised end",
          c.horizon_revisions == [(280, 350)] and abs(after - before) <= REL * before
          and abs(at_end - P * F) <= REL * P and just_before > P * F
          and abs(outs[-1] - P * F) <= REL * P, f"{before!r} -> {after!r}; end {at_end!r}")
    for regime in ("floor", "plateau"):
        o, c, p, _ = child(sd, OPT_LR_CONTINUE=regime, OPT_LR_CONT_WARM=50)
        for _ in range(80):
            step(o, c, p)
        grid = [opt_api.lr_at(o, c, U.Steps(s)) for s in range(a + 80, 401)]
        opt_api.revise_horizon(o, c, run_windows=350)
        grid2 = [opt_api.lr_at(o, c, U.Steps(s)) for s in range(a + 80, 401)]
        check(f"L5 {regime}: the same act is logged and moves no rate",
              grid == grid2 and c.horizon_revisions == [(280, 350)]
              and c.counters.get("opt.horizon.revisions") == 1)


def l6(nolog):
    sd, r0 = nolog
    o, c, p, _ = child(sd, OPT_LR_SCHED="none", OPT_LR_CONTINUE="plateau")
    outs = [step(o, c, p).lr for _ in range(20)]
    led = opt_api.counters(o, c)
    line = next((ln for ln in led["opt.report_lines"] if ln.startswith("opt.continue:")), "")
    check("L6 OPT_LR_SCHED=none under 'plateau': the rate is the flat peak, the regime is INERT and "
          "counted, no record is written, and the line says why",
          all(x == P for x in outs) and c.counters.get("opt.continue.inert") == 1
          and c.continuation is None and "opt.continue.priced" not in c.counters
          and led["opt.continue.regime"] == "as_logged" and "INERT at OPT_LR_SCHED=none" in line,
          line[:160])
    a, w, sw = 200, 50, 20
    o, c, p, _ = child(sd, OPT_LR_CONTINUE="plateau", OPT_LR_CONT_WARM=w, OPT_LR_SHIFT_WARM=sw)
    shift = U.Steps(a + 1)
    outs = [step(o, c, p, shift_at=shift).lr for _ in range(sw + 5)]
    s0 = r0 / P
    want = []
    for j in range(1, sw + 6):
        cyc = s0 + (0.25 - s0) * j / w
        if j <= sw:
            cyc *= max(F, j / sw)
        want.append(P * max(F, cyc))
    k = c.counters
    check("L6 a shift stamped at the first resumed step attenuates the plateau ramp for "
          "OPT_LR_SHIFT_WARM steps and the floor still bounds it",
          all(close(x, y) for x, y in zip(outs, want)) and k["opt.lr.shift_warm_applied"] == sw
          and k["opt.continue.priced"] == sw + 5 and k["opt.lr.floor_applied"] >= 1,
          f"first {outs[0]!r} vs {want[0]!r}; applied {k['opt.lr.shift_warm_applied']}, floored "
          f"{k['opt.lr.floor_applied']}")


# ---- L7: through the composition root, at a real epoch boundary ---------------------------------
BASE = {"DATA_STREAM_BYTES": "60000", "SIG_WARMUP": "20", "FAB_N0": "256", "FAB_SLOTS": "512"}


def build(restored=None, **env):
    _lever._reopen_assembly()
    rng.reset_issued()
    e = dict(BASE)
    e.update({k: str(v) for k, v in env.items()})
    return C.compose(environ=e, restored=restored)


def boundary_snapshot(sysm):
    """The Snapshot a parent stopped on its epoch roll records (tests/test_resume_clock.py's
    snapshot_of at epoch 1 with the clock at window 0 of it), ROUND-TRIPPED through torch.save so no
    child shares a tensor with the parent or with another child -- which is what a file does."""
    recorded = dict(C._geometry_manifest(sysm))
    for k, v in world_api.geometry(sysm.configs["WORLD"], sysm.world).items():
        recorded.setdefault(k, v)
    buf = io.BytesIO()
    torch.save(loop._payload(sysm), buf)
    buf.seek(0)
    payload = torch.load(buf, map_location="cpu", weights_only=False)
    payload["RUN"]["clock"]["in_epoch"] = 0
    return ckpt_api.Snapshot(payload=payload, geometry=recorded,
                             step=int(sysm.clock.counters()["step"]), epoch=1,
                             best_state=None, resume=None)


def fresh_copy(snap):
    buf = io.BytesIO()
    torch.save(snap.payload, buf)
    buf.seek(0)
    return dataclasses.replace(snap, payload=torch.load(buf, map_location="cpu",
                                                        weights_only=False))


def l7():
    p = build()
    loop.run(p, max_windows=12, progress=False)
    r0 = float(p.optimizer.lr_prev)
    a = int(p.optimizer.opt_step)
    snap = boundary_snapshot(p)
    for regime in ("as_logged", "floor", "plateau", "rewarm"):
        c = build(restored=fresh_copy(snap), RUN_EPOCHS=2, DATA_RESAMPLE=1, OPT_LR_CONTINUE=regime)
        oc = c.configs["OPT"]
        first = opt_api.lr_at(oc, c.optimizer, U.Steps(a + 1))
        if regime == "as_logged":
            want = untouched(oc, c.optimizer.horizon, a + 1)
        else:
            want = closed_first(regime, 1000, r0, a, int(c.optimizer.horizon.run_steps))
        second = opt_api.lr_at(oc, c.optimizer, U.Steps(a + 2))
        loop.run(c, max_windows=2, progress=False)
        led = opt_api.counters(oc, c.optimizer)
        check(f"L7 compose, boundary child at RUN_EPOCHS=2 under {regime!r}: the first resumed rate is "
              f"the closed form, the loop stepped at the rates priced, and OPT.counters labels it",
              close(first, want) and int(c.optimizer.opt_step) == a + 2
              and c.optimizer.lr_prev == second and led.get("opt.continue.regime") == regime
              and c.optimizer.counters.get("opt.continue.boundary") == 1,
              f"lr_at {first!r} vs {want!r}; lr_prev {c.optimizer.lr_prev!r} vs {second!r}; "
              f"label {led.get('opt.continue.regime')}")
        if regime == "rewarm":
            # THE SESSION END IS A PROJECTION (this epoch's length x RUN_EPOCHS), and here it falls
            # inside the default 1000-step ramp: the report must say this rewarm has no decay phase.
            end = int(c.optimizer.continuation["end"])
            line = next((ln for ln in led["opt.report_lines"] if ln.startswith("opt.continue:")), "")
            check("L7 ... a rewarm whose projected session end falls inside its ramp says it has NO "
                  "DECAY PHASE (at this shape it does: the child's two epochs end before the ramp)",
                  end <= a + 1000 and "NO DECAY PHASE" in line,
                  f"end {end}, ramp ends {a + 1000}")

    # THE ACT PARENT GOES THROUGH A REAL CHECKPOINT DIRECTORY: its grown vocabulary lives in the file
    # CKPT writes beside the checkpoint (TOK.save_vocabulary), which an in-memory Snapshot does not
    # carry. It runs its whole epoch at RUN_EPOCHS=1, so its final save is the epoch boundary a
    # continuation resumes from (tests/test_resume_clock.py C4/C5 drive the same boundary).
    tmp = tempfile.mkdtemp(prefix="lr_continue_")
    try:
        act = {"TOK_GROW_EVERY": 30, "TOK_RETOK_EVERY": 40}
        ap = build(CKPT_DIR=tmp + "/p", **act)
        loop.run(ap, progress=False)
        logged = int(ap.optimizer.counters.get("opt.horizon.revisions", 0) or 0)
        check("L7 setup: the act parent ran its epoch and logged at least one in-run revision",
              logged >= 1 and len(ap.optimizer.horizon_revisions) >= 1
              and int(ap.clock.counters()["epoch"]) == 1, f"opt.horizon.revisions {logged}")
        curves, ks = [], []
        for flag in ("True", "False"):
            c = build(CKPT_RESUME=tmp + "/p", CKPT_DIR=tmp + "/c" + flag, RUN_EPOCHS=2,
                      DATA_RESAMPLE=1, TOK_GROW_EVERY=30, TOK_RETOK_EVERY=0,
                      OPT_HORIZON_REVISE=flag)
            res = loop.run(c, max_windows=30, progress=False)
            curves.append(list(res.loss_curve))
            ks.append(dict(c.optimizer.counters))
        check("L7 act-parent boundary child: OPT_HORIZON_REVISE True and False train IDENTICAL losses "
              "over 30 windows -- the lever leaves a continued run's LR unchanged",
              len(curves[0]) == 30 and curves[0] == curves[1],
              f"first differing "
              f"{next((i for i, (x, y) in enumerate(zip(*curves)) if x != y), None)}")
        check("L7 ... a session boundary under both, load_state's resume revision appended under both, "
              "and revise_horizon never asked (opt.horizon.revise_inert ABSENT in both)",
              all(k.get("opt.continue.boundary") == 1 and "opt.horizon.revise_inert" not in k
                  for k in ks)
              and ks[0].get("opt.horizon.revisions") == ks[1].get("opt.horizon.revisions")
              == logged + 1, [k.get("opt.horizon.revisions") for k in ks])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def l8():
    o = cfg(OPT_LR_CONTINUE="regulated")
    try:
        fresh(o, 100)
        check("L8 'regulated' is refused at OPT.build", False, "built")
    except NotBuilt as e:
        check("L8 'regulated' is refused at OPT.build with NotBuilt naming the lever and NEW-04",
              str(e).startswith("OPT_LR_CONTINUE='regulated'") and "NEW-04" in str(e), str(e)[:120])
    try:
        cfg(OPT_LR_CONTINUE="bogus")
        check("L8 a misspelt regime is refused at resolution", False, "resolved")
    except LeverError as e:
        check("L8 a misspelt regime is refused at resolution, never defaulted",
              "OPT_LR_CONTINUE" in str(e), str(e)[:120])
    try:
        fresh(cfg(OPT_LR_CONT_WARM=-1), 100)
        check("L8 a negative OPT_LR_CONT_WARM is refused", False, "built")
    except ValueError as e:
        check("L8 a negative OPT_LR_CONT_WARM is refused by name", "OPT_LR_CONT_WARM" in str(e),
              str(e)[:100])


if __name__ == "__main__":
    NOLOG, LOGGED = parents()
    l1(NOLOG, LOGGED)
    l2(NOLOG, LOGGED)
    l3(NOLOG)
    l4(NOLOG, LOGGED)
    l5(NOLOG)
    l6(NOLOG)
    l8()
    l7()
    print(f"\n=== {len(FAILS)} failing ===")
    sys.exit(1 if FAILS else 0)
