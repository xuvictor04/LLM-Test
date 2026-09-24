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
      and world.forecasts and lm.encode.extra_ratio are ABSENT.
  W3  load_into: a blob with the `proj_trained` field decides by the field (True restores the saved
      tensor, False re-zeroes it) EVEN WHEN the counters say otherwise; a blob that predates the
      field falls back to `world.forecasts` in its counters; world.proj_zeroed_on_load counts across
      the lineage and adds 0 on a restore even when the parent's counters already carry it; and
      world.proj_trained_basis names which evidence decided.
"""
import copy
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import torch                                                       # noqa: E402
torch.set_num_threads(1)

from spine import lever as _lever                                  # noqa: E402
from spine import rng                                              # noqa: E402
from spine import loop                                             # noqa: E402
from spine.compose import compose                                  # noqa: E402
from lm import api as lm_api                                       # noqa: E402
from world import api as world_api                                 # noqa: E402

FAILS = []
BASE = {"DATA_STREAM_BYTES": "60000"}
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


def _loop_counts(**env):
    lm_api._COUNTS.clear()   # LM's tally is process-global; each arm here stands for its own run
    sysm = build(**env)
    res = loop.run(sysm, max_windows=LOOP_WINDOWS, progress=False)
    lc = lm_api.counters(sysm.configs["LM"], sysm.model)
    return len(res.loss_curve), dict(sysm.world.counters), lc


def w2_loop_arms():
    n, wc, lc = _loop_counts()
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


def main():
    sysm = build()
    lm_cfg = sysm.configs["LM"]
    w1_born_zero(sysm.configs["WORLD"], int(lm_cfg.width), int(lm_cfg.ctx))
    w2_forecast_noop_and_learns(sysm)
    w3_load(build())
    w2_loop_arms()
    print(f"\n{len(FAILS)} failing" + (": " + ", ".join(FAILS) if FAILS else ""))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
