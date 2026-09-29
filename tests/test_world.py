"""THE WORLD FORECAST'S BIRTH AND ITS RESUME -- is the forecast an exact no-op when it is wired in,
does it still learn, and does a resume keep a trained world_proj while re-zeroing an untrained one?
Driven through the real entry points (WORLD.build / forecast / state_dict / load_into, LM.embed /
encode, and one short loop.run per feedback arm).

    python3 tests/test_world.py        # exit 0 = every check passed

WHY IT EXISTS (Q-WORLD-10, docs/04_CONTRACT.md). WORLD.forecast got its call site on 2026-09-24:
spine/loop.py::_flush passes its return to LM.encode as `extra`. That is safe ONLY because
world_proj is born ZERO -- before, a first call added build()'s uniform(-0.1, 0.1) draw, 7.6% of h
at the real call site -- and because WORLD.load_into re-zeroes a world_proj no forecast ever
reached (a pre-wiring checkpoint restored |W| 3.70 over the zero). Nothing else in tests/ reads
world_proj at all, so each of these could regress in silence:

  W1  AFTER build(), world_proj's weight and bias are ALL ZERO, and encoder, qproj and keys hold
      EXACTLY the uniform draw build() made before the zeroing existed -- replayed here from the
      same generator seed, so "zeroed after the draw, not taken out of it" is checked, not assumed.
  W2  forecast() returns EXACT zeros on a fresh build, LM.encode(extra=forecast) equals
      LM.encode() bit for bit, and a backward through that encode gives world_proj.weight a
      NONZERO gradient (a zero map with a dead gradient would be a forecast that never learns).
      Then one short loop per feedback arm: wired, world.forecasts == lm.encode.extra_applied ==
      flushes and the ratio gauges are present; at WORLD_FEEDBACK=0, world.forecast.inert == calls
      and world.forecasts and lm.encode.extra_ratio are ABSENT. The loops run under 04-Q5's three
      pins (2026-09-29): the shipped retention probe forecasts beside training, off the flush count.
  W3  load_into: a blob with the `proj_trained` field decides by the field (True restores the saved
      tensor, False re-zeroes it) EVEN WHEN the counters say otherwise; a blob that predates the
      field falls back to `world.forecasts` in its counters; world.proj_zeroed_on_load counts across
      the lineage and adds 0 on a restore even when the parent's counters already carry it; and
      world.proj_trained_basis names which evidence decided.
  W4  THE POPULATION REFUSAL, M43, HAD NO TEST (Proposal 05 §8 1.6, register CONTRACT-Q-CKPT-2-R2,
      docs/04_CONTRACT.md Q-CKPT-2). A WORLD population mismatch in either direction is refused by
      name before training: WORLD.load_into refuses a 6-predictor blob at WORLD_NMAX=4 and 8 with no
      live tensor moved; through compose a lever-driven mismatch is refused first by the geometry
      gate (world.nmax is EXACT), and a snapshot whose population disagrees with its recorded
      extent is refused by M43 itself; the parent's files hash identically afterwards.
"""
import copy
import dataclasses
import hashlib
import os
import random
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import torch                                                       # noqa: E402
torch.set_num_threads(1)

from spine import lever as _lever                                  # noqa: E402
from spine import rng                                              # noqa: E402
from spine import loop                                             # noqa: E402
from spine import assemble                                         # noqa: E402
from spine.compose import compose                                  # noqa: E402
from ckpt import api as ckpt_api                                   # noqa: E402
from lm import api as lm_api                                       # noqa: E402
from world import api as world_api                                 # noqa: E402

FAILS = []
# WORLD_FEEDBACK=1 IN THE BASE: these checks are about the WIRED forecast path, which the lever still
# offers although it ships False since the 2026-09-24 GPU fleet (Q-WORLD-10). The off arm is asked for
# explicitly where it is the thing under test.
BASE = {"DATA_STREAM_BYTES": "60000", "WORLD_FEEDBACK": "1"}
LOOP_WINDOWS = 4


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" -- {detail}" if detail else ""))
    if not ok:
        FAILS.append(name)


def build(**env):
    """One real System per configuration. The assembly latch and the rng registry are reopened
    first because each call here stands for a different run."""
    _lever._reopen_assembly()
    rng.reset_issued()
    e = dict(BASE)
    e.update({k: str(v) for k, v in env.items()})
    return compose(environ=e)


class _FixedRng:
    """A stand-in for WORLD's rng stream: build() takes exactly one randint from it (the generator
    seed), so a fixed answer makes the draw replayable."""

    def __init__(self, seed):
        self.seed = seed
        self._r = random.Random(0)
        self._draws = 0

    def randint(self, a, b):
        self._draws += 1
        return self.seed


def w1_born_zero(cfg_world, d_model, ctx):
    seed = 424242
    w = world_api.build(cfg_world, d_model=d_model, device=torch.device("cpu"), ctx_tokens=ctx,
                        rng=_FixedRng(seed))
    check("W1 world_proj.weight is all zero after build",
          bool((w.world_proj.weight == 0).all()),
          f"|W| {float(w.world_proj.weight.detach().norm()):.6g}")
    check("W1 world_proj.bias is all zero after build", bool((w.world_proj.bias == 0).all()))
    # THE REPLAY: build()'s draw order is encoder, world_proj, qproj (every >=2-dim tensor
    # uniform(-0.1, 0.1), every 1-dim one zero), then keys. world_proj's draw is TAKEN and then
    # overwritten, so encoder/qproj/keys must equal a replay that still draws into world_proj.
    gen = torch.Generator(device="cpu")
    gen.manual_seed(seed)
    ref = {}
    order = ([("encoder", n, t) for n, t in w.encoder.named_parameters()]
             + [("world_proj", n, t) for n, t in w.world_proj.named_parameters()]
             + [("qproj", n, t) for n, t in w.qproj.named_parameters()])
    for mod, n, t in order:
        r = torch.empty_like(t)
        if t.dim() >= 2:
            r.uniform_(-0.1, 0.1, generator=gen)
        else:
            r.zero_()
        ref[(mod, n)] = r
    keys = torch.empty_like(w.keys).uniform_(-0.1, 0.1, generator=gen)
    same = all(torch.equal(t.detach(), ref[(mod, n)]) for mod, n, t in order if mod != "world_proj")
    check("W1 encoder and qproj hold exactly the pre-zeroing draw", same)
    check("W1 keys hold exactly the pre-zeroing draw", torch.equal(w.keys.detach(), keys))
    check("W1 the replayed world_proj draw is NOT zero (the replay has teeth)",
          float(ref[("world_proj", "weight")].norm()) > 0.0,
          f"|W| of the draw {float(ref[('world_proj', 'weight')].norm()):.6g}")


def w2_forecast_noop_and_learns(sysm):
    cfg_w, lm_cfg = sysm.configs["WORLD"], sysm.configs["LM"]
    ids = sysm.segmentation.ids
    x = torch.tensor([ids[0:64]], dtype=torch.long)
    with torch.no_grad():
        h0 = lm_api.encode(lm_cfg, sysm.model, x)
    sysm.model.zero_grad(set_to_none=True)
    sysm.world.world_proj.zero_grad(set_to_none=True)
    obs = lm_api.embed(lm_cfg, sysm.model, x)
    f = world_api.forecast(cfg_w, sysm.world, obs)
    check("W2 forecast on a fresh build is exactly zero", f is not None and bool((f == 0).all()),
          "None" if f is None else f"max|f| {float(f.detach().abs().max()):.3g}")
    h = lm_api.encode(lm_cfg, sysm.model, x, extra=f)
    check("W2 encode(extra=forecast) == encode() bit for bit at birth", torch.equal(h.detach(), h0))
    # ANY loss that depends on h; a fixed random direction keeps it clear of a symmetric zero.
    g = torch.Generator().manual_seed(7)
    (h * torch.randn(h.shape, generator=g)).sum().backward()
    gw = sysm.world.world_proj.weight.grad
    gn = 0.0 if gw is None else float(gw.norm())
    check("W2 world_proj.weight gets a NONZERO gradient through the zero forecast", gn > 0.0,
          f"|dL/dW| {gn:.6g}")


# 04-Q5's PIN RULE ON W2's LOOP (2026-09-29). Its equalities are per flush -- world.forecasts,
# lm.encode.extra_applied, world.forecast.calls and .inert each equal to the flushes -- and since the
# flip the shipped retention probe and its generation call WORLD.forecast beside training (Q-EVAL-12's
# exact accounting moves world.forecast.calls and .inert by their forwards, tests/test_probe.py P2).
# So the loop runs under the three values that restore the tree the equalities were written on
# (tests/test_baseline.py's PRE_SR0_PINS, imported).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_baseline import PRE_SR0_PINS                            # noqa: E402


def _loop_counts(**env):
    lm_api._COUNTS.clear()   # LM's tally is process-global; each arm here stands for its own run
    sysm = build(**PRE_SR0_PINS, **env)
    res = loop.run(sysm, max_windows=LOOP_WINDOWS, progress=False)
    lc = lm_api.counters(sysm.configs["LM"], sysm.model)
    return len(res.loss_curve), dict(sysm.world.counters), lc


def w2_loop_arms():
    n, wc, lc = _loop_counts(WORLD_FEEDBACK=1)
    check("W2 wired: world.forecasts == lm.encode.extra_applied == flushes",
          wc.get("world.forecasts") == lc.get("lm.encode.extra_applied") == n,
          f"forecasts {wc.get('world.forecasts', 'ABSENT')} extra_applied "
          f"{lc.get('lm.encode.extra_applied', 'ABSENT')} flushes {n}")
    check("W2 wired: lm.encode.extra_ratio and extra_ratio_max are present",
          "lm.encode.extra_ratio" in lc and "lm.encode.extra_ratio_max" in lc,
          f"ratio {lc.get('lm.encode.extra_ratio', 'ABSENT')} max "
          f"{lc.get('lm.encode.extra_ratio_max', 'ABSENT')}")
    n, wc, lc = _loop_counts(WORLD_FEEDBACK=0)
    check("W2 WORLD_FEEDBACK=0: world.forecast.inert == calls == flushes, world.forecasts ABSENT",
          wc.get("world.forecast.inert") == wc.get("world.forecast.calls") == n
          and "world.forecasts" not in wc,
          f"inert {wc.get('world.forecast.inert')} calls {wc.get('world.forecast.calls')} "
          f"forecasts {wc.get('world.forecasts', 'ABSENT')}")
    check("W2 WORLD_FEEDBACK=0: lm.encode.extra_ratio and extra_applied ABSENT",
          "lm.encode.extra_ratio" not in lc and "lm.encode.extra_applied" not in lc,
          f"ratio {lc.get('lm.encode.extra_ratio', 'ABSENT')}")


def w3_load(sysm):
    cfg_w, w = sysm.configs["WORLD"], sysm.world
    trained = {k: torch.full_like(v, 0.25) for k, v in w.world_proj.state_dict().items()}

    def blob(**over):
        sd = copy.deepcopy(world_api.state_dict(cfg_w, w))
        sd["world_proj"] = {k: v.clone() for k, v in trained.items()}
        sd.update(over)
        return sd

    def load(sd):
        w.counters.pop("world.proj_zeroed_on_load", None)
        w.counters.pop("world.proj_trained_basis", None)
        world_api.load_into(cfg_w, w, sd)
        return float(w.world_proj.weight.detach().abs().max()), w.counters.get(
            "world.proj_zeroed_on_load"), str(w.counters.get("world.proj_trained_basis", ""))

    # THE FIELD DECIDES, AND IT OUTRANKS THE COUNTERS IN BOTH DIRECTIONS.
    c_none = {k: v for k, v in w.counters.items() if k != "world.forecasts"}
    mx, z, basis = load(blob(proj_trained=True, counters=dict(c_none)))
    check("W3 proj_trained=True restores the saved world_proj even with world.forecasts pruned",
          mx == 0.25 and z == 0 and "field" in basis, f"max|W| {mx} zeroed {z} basis '{basis}'")
    mx, z, basis = load(blob(proj_trained=False, counters=dict(c_none, **{"world.forecasts": 9})))
    check("W3 proj_trained=False re-zeroes world_proj even with world.forecasts in the counters",
          mx == 0.0 and z == 1 and "field" in basis, f"max|W| {mx} zeroed {z} basis '{basis}'")
    # THE FALLBACK, ONLY FOR BLOBS THAT PREDATE THE FIELD.
    old = blob(counters=dict(c_none))
    old.pop("proj_trained", None)
    mx, z, basis = load(old)
    check("W3 pre-field blob without world.forecasts: re-zeroed, basis names the fallback",
          mx == 0.0 and z == 1 and "predates" in basis, f"max|W| {mx} zeroed {z} basis '{basis}'")
    old = blob(counters=dict(c_none, **{"world.forecasts": 9, "world.proj_zeroed_on_load": 2}))
    old.pop("proj_trained", None)
    mx, z, basis = load(old)
    check("W3 pre-field blob with world.forecasts: restored, and the parent's proj_zeroed_on_load "
          "2 is carried with 0 added",
          mx == 0.25 and z == 2 and "predates" in basis, f"max|W| {mx} zeroed {z} basis '{basis}'")
    mx, z, basis = load(blob(proj_trained=False,
                             counters=dict(c_none, **{"world.proj_zeroed_on_load": 2})))
    check("W3 a re-zero adds 1 to the lineage's proj_zeroed_on_load", mx == 0.0 and z == 3,
          f"max|W| {mx} zeroed {z}")
    # AND THE FLAG ROUND-TRIPS: a forecast sets it, state_dict writes it.
    world_api.forecast(cfg_w, w, torch.zeros(1, 4, int(w.encoder[0].in_features)))
    check("W3 state_dict writes proj_trained True once a forecast was returned",
          world_api.state_dict(cfg_w, w).get("proj_trained") is True)


def _world_at(nmax, seed=4242):
    """A World built by WORLD.build at WORLD_NMAX=nmax off a real assemble.build, and its Config."""
    _lever._reopen_assembly()
    rng.reset_issued()
    cfgs, _w, _ = assemble.build({"WORLD_NMAX": str(nmax)})
    lm_cfg = cfgs["LM"]
    w = world_api.build(cfgs["WORLD"], d_model=int(lm_cfg.width), device=torch.device("cpu"),
                        ctx_tokens=int(lm_cfg.ctx), rng=_FixedRng(seed))
    return cfgs["WORLD"], w


def _world_tensors(w):
    out = {f: getattr(w, f).detach().clone() for f in ("preds", "keys", "alive", "fit", "mass",
                                                        "grown")}
    for mod in ("encoder", "qproj", "world_proj"):
        for n, t in getattr(w, mod).named_parameters():
            out[f"{mod}.{n}"] = t.detach().clone()
    return out


def _tree_hash(d):
    out = {}
    for root, _dirs, files in os.walk(d):
        for f in files:
            p = os.path.join(root, f)
            with open(p, "rb") as fh:
                out[os.path.relpath(p, d)] = hashlib.sha256(fh.read()).hexdigest()
    return out


def _raised(fn):
    try:
        fn()
        return None, ""
    except Exception as e:                                         # noqa: BLE001 -- reported
        return type(e).__name__, str(e)


def w4_population_refusal():
    # (a) UNIT, BOTH DIRECTIONS: a blob from the default WORLD_NMAX=6 into Worlds at 4 and 8.
    cfg6, w6 = _world_at(6)
    blob = world_api.state_dict(cfg6, w6)
    for nmax, head in ((4, "WORLD_NMAX:"), (8, "WORLD_N0/WORLD_NMAX:")):
        cfg_n, w_n = _world_at(nmax, seed=99)
        before = _world_tensors(w_n)
        kind, msg = _raised(lambda: world_api.load_into(cfg_n, w_n, blob))
        after = _world_tensors(w_n)
        same = before.keys() == after.keys() and all(torch.equal(before[k], after[k]) for k in before)
        check(f"W4 (M43) a 6-predictor blob into WORLD_NMAX={nmax} is refused by name, before any "
              f"tensor moves",
              kind == "LeverError" and msg.startswith(head) and same
              and w_n.counters.get("world.state_refused") == 1
              and "world.state_restored" not in w_n.counters,
              f"{kind}: {msg[:90]}; tensors unchanged {same}; refused "
              f"{w_n.counters.get('world.state_refused')}, restored "
              f"{w_n.counters.get('world.state_restored', 'ABSENT')}")
    cfg_c, w_c = _world_at(6, seed=99)
    kind, msg = _raised(lambda: world_api.load_into(cfg_c, w_c, blob))
    check("W4 (M43) control: the same blob into a matching WORLD_NMAX=6 restores",
          kind is None and w_c.counters.get("world.state_restored") == 1
          and torch.equal(w_c.preds.detach(), blob["preds"]), f"{kind}: {msg[:90]}")

    # (b) THROUGH compose, WITH A REAL CHECKPOINT ON DISK. The lever-driven mismatch is answered by
    # the geometry gate first -- world.nmax is EXACT -- by name.
    tmp = tempfile.mkdtemp(prefix="w4_m43_")
    try:
        # GENERATION OFF (2026-09-29): since 04-6.2's flip the shipped retention probe generates after
        # the parent's final save, which this check reads nothing of and which costs about a minute on
        # the CPU; a CPU suite that tests no EVAL sets it off (docs/04_CONTRACT.md Q-EVAL-12's dated
        # note).
        env = {"FAB_N0": 256, "FAB_SLOTS": 512, "SIG_WARMUP": 20, "EVAL_GENERATE": 0}
        lm_api._COUNTS.clear()
        loop.run(build(CKPT_DIR=tmp + "/p", **env), max_windows=4, progress=False)
        before = _tree_hash(tmp)
        for nmax in (4, 8):
            lm_api._COUNTS.clear()
            kind, msg = _raised(lambda: build(CKPT_RESUME=tmp + "/p", CKPT_DIR=tmp + f"/g{nmax}",
                                              WORLD_NMAX=nmax, **env))
            check(f"W4 a child at WORLD_NMAX={nmax} is refused at the geometry gate, naming the lever",
                  kind == "GeometryRefusal" and msg.startswith("WORLD_NMAX:"), f"{kind}: {msg[:90]}")
        # (c) M43 ITSELF, PAST THE GATE: the snapshot's WORLD population cut to 4 rows or padded to
        # 8, with its recorded world.n to match, so the gate passes and WORLD.load_into answers.
        _lever._reopen_assembly()
        rng.reset_issued()
        cfgs, _w, _ = assemble.build(dict(BASE, CKPT_RESUME=tmp + "/p",
                                          **{k: str(v) for k, v in env.items()}))
        snap = ckpt_api.load(cfgs["CKPT"])
        for rows, head in ((4, "WORLD_N0/WORLD_NMAX: the checkpoint allocates 4 predictors and "
                               "this run allocates 6"),
                           (8, "WORLD_NMAX: the checkpoint holds 8 predictors and this run "
                               "allocates at most 6")):
            wsd = dict(snap.payload["WORLD"])
            for f in ("preds", "keys", "fit", "mass", "alive", "grown"):
                t = wsd[f]
                wsd[f] = (t[:rows].clone() if rows < t.shape[0] else
                          torch.cat([t, torch.zeros((rows - t.shape[0],) + tuple(t.shape[1:]),
                                                    dtype=t.dtype)], 0))
            geo = dict(snap.geometry)
            if "world.n" in geo:
                geo["world.n"] = (rows,) + tuple(geo["world.n"][1:])
            doc = dataclasses.replace(snap, payload=dict(snap.payload, WORLD=wsd), geometry=geo)
            lm_api._COUNTS.clear()
            _lever._reopen_assembly()
            rng.reset_issued()
            e = dict(BASE, CKPT_DIR=tmp + f"/m{rows}", **{k: str(v) for k, v in env.items()})
            kind, msg = _raised(lambda: compose(environ=e, restored=doc))
            check(f"W4 (M43) past the gate, a {rows}-row WORLD population is refused by WORLD.load_into "
                  f"before any System returns", kind == "LeverError" and msg.startswith(head),
                  f"{kind}: {msg[:110]}")
        after = _tree_hash(tmp)
        check("W4 after every refusal the parent's files hash identically, nothing new is on disk and "
              "no child CKPT_DIR exists",
              before == after and len(before) >= 2
              and not any(os.path.exists(tmp + f"/{d}") for d in ("g4", "g8", "m4", "m8")),
              f"files {sorted(before)}; changed "
              f"{sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    sysm = build()
    lm_cfg = sysm.configs["LM"]
    w1_born_zero(sysm.configs["WORLD"], int(lm_cfg.width), int(lm_cfg.ctx))
    w2_forecast_noop_and_learns(sysm)
    w3_load(build())
    w2_loop_arms()
    w4_population_refusal()
    print(f"\n{len(FAILS)} failing" + (": " + ", ".join(FAILS) if FAILS else ""))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
