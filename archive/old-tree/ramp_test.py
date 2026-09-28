#!/usr/bin/env python3
"""Does turning the capacity valve ON switch the population-building ramp OFF?

THE COUPLING. The growth call site passes the SOFT cap as `cap`:

    _nb = fabgrow.step(_lf, step, fab.n(), _cap_fab[0])

and PlateauGrowth latches its ramp on `n >= s.ramp_to * cap`. With GROW_CAP off, `_cap_fab[0]` IS FAB_NMAX, so
the latch threshold is a fraction of the PREALLOCATED pool and the ramp builds the population up to it. With
GROW_CAP on, `_cap_fab[0]` is GROW_CAP_FAB0 -- a much smaller number -- so the same FAB_RAMP_TO now means a much
lower threshold, and a population that starts at or above it latches the ramp on the first step.

That is the failure mode this file exists to pin down, because it is invisible in the config: nothing in the
launch line says GROW_CAP_FAB0 reprograms FAB_RAMP_TO, and the symptom (no lift, ever) looks identical to the
plateau condition never being met. round6 and round7 both ended in "never pinned, valve correctly declined" and
this is one mechanism that produces exactly that.

`cap` must therefore mean two DIFFERENT things at the two sites it is used for:
  - the LATCH asks "is the population built?"    -> against the hardware pool, FAB_NMAX
  - the CLAMP asks "may it grow any further?"    -> against the operating ceiling, the soft cap

Loaded from the shipped source by AST rather than imported, as with proj_test.py and cap_test.py: this is
control flow over ints and testing it should not be unrunnable because torch is missing.

Run: python3 ramp_test.py
"""
import ast
import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "self_organize.py")
_tree = ast.parse(open(_SRC).read())
_cls = next((n for n in _tree.body if isinstance(n, ast.ClassDef) and n.name == "PlateauGrowth"), None)
if _cls is None:
    print("!! PlateauGrowth is not a module-level class in self_organize.py -- this test cannot find the code "
          "it is supposed to be testing, which means it is testing nothing.")
    sys.exit(1)
_ns = {"_env": lambda k, d=None: d}          # the class reads only FAB_RAMP_LATCH, and the default is what we want
exec(compile(ast.Module(body=[_cls], type_ignores=[]), _SRC, "exec"), _ns)
PlateauGrowth = _ns["PlateauGrowth"]

FAILED = []


def check(cond, msg):
    if not cond: FAILED.append(msg); print(f"  FAIL  {msg}")
    else: print(f"  ok    {msg}")


def ramp_events(n0, cap, pool=None, ramp_to=0.5, steps=4000):
    """Drive the grower with a FLAT loss over `steps`, holding the population at n0, and count ramp events.

    A flat loss is the point: it removes REGRESSION and stall from the picture entirely, so whatever growth
    comes back is the ramp and only the ramp. The population is held fixed because we are asking whether the
    ramp is ARMED at this (n, cap, pool), not how far it would get.

    pool=None reproduces the OLD single-cap call, which is how the coupling is demonstrated below.
    """
    g = PlateauGrowth(ramp=4000, burst=12, rate=0.10, ramp_to=ramp_to, warmup=0, cooldown=1500)
    grown = 0
    for t in range(steps):
        nb = g.step(2.0, t, n0, cap) if pool is None else g.step(2.0, t, n0, cap, pool=pool)
        if nb and g.why == "ramp": grown += 1
    return grown, g.n_ramp


print("PlateauGrowth: does the soft cap silently disarm the ramp?\n")

# --- 1. THE DEFECT, AT THE LAUNCH CONFIG ---------------------------------------------------------------------
# FAB_N0=2048, FAB_NMAX=8192, FAB_RAMP_TO=0.5. The only difference between these two lines is whether GROW_CAP
# is on, which is supposed to control the CEILING and nothing else. Both calls pass ONE cap, as the call site
# used to; this block is the evidence that a single cap cannot serve both decisions.
print("ONE CAP FOR BOTH DECISIONS -- FAB_N0=2048  FAB_NMAX=8192  FAB_RAMP_TO=0.5")
_off, _ = ramp_events(2048, 8192)                 # GROW_CAP off -> the one cap IS FAB_NMAX
_on, _ = ramp_events(2048, 3000)                  # GROW_CAP on  -> the one cap is GROW_CAP_FAB0=3000
print(f"  valve OFF (cap 8192, latch at 4096): {_off:3d} ramp events -- population builds toward 4096")
print(f"  valve ON  (cap 3000, latch at 1500): {_on:3d} ramp events -- 2048 >= 1500, latched on step 1")
check(_off > 0, "valve OFF, one cap: the ramp runs and the population is built")
check(_on == 0, "valve ON, one cap: the ramp is DEAD -- switching the valve on switched the ramp off")

# --- 2. IT IS THE CAP ARGUMENT, NOT THE POPULATION -----------------------------------------------------------
# Same population, same FAB_RAMP_TO, only the cap differs. This attributes the coupling to `cap` alone rather
# than to some interaction with n.
print("\nATTRIBUTION -- hold n and ramp_to fixed, vary only the cap argument")
for cap in (8192, 6000, 4096, 3000, 2048):
    ev, _ = ramp_events(2048, cap)
    print(f"  cap {cap:5d} -> latch at {int(0.5*cap):5d} -> {ev:3d} ramp events")
check(ramp_events(2048, 4096)[0] == 0, "cap 4096: latch at 2048, n=2048 meets it exactly -> latched")
check(ramp_events(2048, 6000)[0] > 0, "cap 6000: latch at 3000, n=2048 is below it -> still ramping")

# --- 2b. THE FIX: A SEPARATE POOL FOR THE LATCH --------------------------------------------------------------
# `pool` is the hardware preallocation and never moves; `cap` is the operating ceiling the valve lifts. With the
# two separated, the valve's setting must make NO difference to whether the ramp is armed.
print("\nTWO CAPS -- latch against pool=FAB_NMAX, clamp against the soft cap")
_f_off, _ = ramp_events(2048, 8192, pool=8192)
_f_on, _ = ramp_events(2048, 3000, pool=8192)
print(f"  valve OFF (cap 8192, pool 8192): {_f_off:3d} ramp events")
print(f"  valve ON  (cap 3000, pool 8192): {_f_on:3d} ramp events")
check(_f_on > 0, "the ramp survives the valve being switched on -- the population can now reach the soft cap")
check(_f_on == _f_off, "the valve's setting makes NO difference to the ramp: the two decisions are separated")
check(ramp_events(2048, 3000, pool=4096)[0] == 0,
      "and pool still decides: a pool of 4096 latches at 2048, valve or no valve")

# --- 3. WHAT THE CALLER ACTUALLY WANTS -----------------------------------------------------------------------
# The fix is to latch against the hardware pool while still clamping growth to the soft cap. Assert the shape of
# the wanted behaviour here so the fix has something to satisfy: at the launch config the ramp must run AND the
# growth it produces must be refused above the soft cap. The clamp is the call site's own line, reproduced here
# because the point is that the two decisions read DIFFERENT caps -- the latch the pool, the clamp the ceiling.
print("\nTHE WANTED BEHAVIOUR -- ramp against FAB_NMAX, clamp against the soft cap")
_ev, _ = ramp_events(2048, 8192)                  # latch decided by the hardware pool...
check(_ev > 0, "latching against FAB_NMAX=8192 keeps the ramp alive at n=2048")


def burst_at(n, pool, soft):
    """One ramp burst at population n, latching against `pool`, then clamped by the call site against `soft`."""
    g = PlateauGrowth(ramp=4000, burst=12, rate=0.10, ramp_to=0.5, warmup=0, cooldown=1500)
    for t in range(2000):
        nb = g.step(2.0, t, n, pool)
        if nb: return min(nb, soft - n)           # `_nb = min(_nb, _cap_fab[0] - fab.n())` at the call site
    return 0


# ...while the call site's clamp still binds: 10% of 2995 is 299 nodes wanted, and the soft cap admits 5.
check(burst_at(2995, 8192, 3000) == 5, "just under the soft cap, a 299-node ramp burst is cut to the 5 that fit")
check(burst_at(3000, 8192, 3000) == 0, "AT the soft cap the ramp grows nothing -- which is what 'pinned' means")
check(burst_at(2048, 8192, 8192) > 12, "with no soft cap in the way the burst is the full 10% of the population")

# --- 4. THE LATCH IS ONE-WAY ---------------------------------------------------------------------------------
# Whatever cap it is judged against, arriving must be permanent: the whole reason FAB_RAMP_LATCH exists is that
# culling drops the population back below the threshold and an unlatched ramp then refills every cull forever.
print("\nTHE LATCH MUST NOT RE-ARM -- the cull-refill cycle is what it was added to stop")
g = PlateauGrowth(ramp=4000, burst=12, rate=0.10, ramp_to=0.5, warmup=0, cooldown=1500)
for t in range(2000): g.step(2.0, t, 4096, 8192)          # arrive at the threshold
_after = g.n_ramp
for t in range(2000, 6000): g.step(2.0, t, 1000, 8192)    # then get culled well below it
check(g.ramp_done, "the ramp stays latched after the population is culled back down")
check(g.n_ramp == _after, f"no refill events after the latch ({g.n_ramp - _after} fired, want 0)")

print()
if FAILED:
    print(f"FAILED {len(FAILED)} check(s):")
    for f in FAILED: print(f"  - {f}")
    sys.exit(1)
print("ramp_test: all checks passed")
