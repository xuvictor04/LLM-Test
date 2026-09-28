#!/usr/bin/env python3
"""Can the domain manager delete the area the run is not currently streaming?

WHAT HAPPENED. The first run that ever added a second area to a trained system -- English trained, Python
added -- ended with ONE live domain out of 144 created, and a 200,000-entry memory store whose every entry
carried a single source id. The manage trace shows it as a ratchet, three separate times:

    [manage @ 96500] merged 0 culled 1 -> 3 live domains
    [manage @ 97300] merged 0 culled 1 -> 2 live domains
    [manage @ 97400] merged 0 culled 1 -> 1 live domains
    [manage @ 102800] -> 5 ... -> 4 ... -> 3 ... -> 2 ...  [105500] -> 1 live domains

Two independent defects produced it.

THE BUDGET FLOOR. `order[:max(1, int(DOM_CULL_FRAC * len(s.cent)))]` -- int(0.10 * n) is 0 for every
population under ten, so max(1, ...) turned "cull at most a tenth" into "cull at least one, every pass,
for as long as the run lasts". Nothing but `len(s.cent) <= 1` could stop it, which is exactly where it
stopped, every time.

THE MISSING BRAKE. `act` decays by DOM_DECAY every manage pass and `last` only moves when the domain is
fed, so under PHASE_SCHED [[0],[0],[1],[1]] every domain of the process the schedule is NOT currently
streaming trips `act < min_size AND stale` by construction, within MANAGE_STALE steps of the switch. The
cull then calls mem.delete_src(), deleting the domain's entries outright -- entries MEM_SRC_FLOOR forbids
EVICTING. The lossless empty-cull directly above it checks whether the domain still owns memory; the one
that destroys everything did not.

This is the memory lesson one level up, and mem_evict_test.py states it first: "English was not less
useful, it had merely stopped being WRITTEN."

The cull block is exec'd FROM THE ACTUAL SOURCE TEXT rather than restated here, so a change to the rule
that this test does not know about breaks it loudly instead of being quietly untested.

    python3 domain_test.py
"""
import textwrap
import torch

FAILED = []


def check(ok, msg):
    print(f"  {'ok  ' if ok else 'FAIL'}  {msg}")
    if not ok:
        FAILED.append(msg)


SRC = open("self_organize.py").read()


def block(start, end):
    a = SRC.index(start)
    a = SRC.rfind("\n", 0, a) + 1
    return textwrap.dedent(SRC[a:SRC.index(end, a)])


# ANCHOR ON THE BANNER COMMENT, not on `if len(s.cent) > 1:` -- that line appears twice in manage(), once for
# the merge loop's guard. The end anchor is the decay line that closes the cull.
CULL = block("        if len(s.cent) > 1:                                               # CULL:",
             "        for i in s.act: s.act[i] *= DOM_DECAY")


class Mem:
    """Only what the cull touches: per-entry source ids, the floor's inputs, and delete_src."""
    def __init__(s, per_src, cap=200000, src_floor=0.5):
        s.cap, s.src_floor = cap, src_floor
        ids = []
        for d, n in per_src.items():
            ids += [d] * n
        ids += [-1] * (cap - len(ids))                       # the rest of the store is unwritten
        s.src = torch.tensor(ids)
        s.deleted = []

    def _eligible(s):
        return torch.tensor([bool((s.src == d).any()) for d in range(int(s.src.max()) + 1)])

    def delete_src(s, d):
        s.deleted.append(int(d))
        s.src[s.src == int(d)] = -1


class Asm:
    def __init__(s, doms, step_now, born=0, last=None):
        s.cent = {d: object() for d in doms}
        s.act = dict(doms)
        s.born = {d: born for d in doms}
        s.last = {d: (last if last is not None else 0) for d in doms}
        s.wins = {d: [] for d in doms}
        s.size = {d: 1 for d in doms}
        s.rad = {d: None for d in doms}
        s.visits = {d: 1 for d in doms}
        s.bornb = {d: 0 for d in doms}
        s.tokc = {}
        s.comp = {}
        s.comp_glob = None
        s.held = 0
        s.protected = 0

    def _dirty(s): pass


def run_cull(asm, mem, step=100000, frac=0.10, grace=500, floor_on=True, comp=True,
             min_size=15, stale=500):
    ns = {"s": asm, "mem": mem, "step": step, "culled": 0,
          "min_size": min_size, "stale": stale,
          "DOM_CULL_FRAC": frac, "DOM_GRACE": grace,
          "DOM_CULL_FLOOR": floor_on, "COMP_PROTECT": comp}
    exec(compile(CULL, "<self_organize>", "exec"), ns)
    return ns["culled"]


# --- 1. THE BUDGET IS A FRACTION, NOT A MINIMUM -------------------------------------------------------------
print("A POPULATION TOO SMALL FOR A PROPORTIONAL CULL IS NOT CULLED ANYWAY")
# Nine domains, every one of them stale and inactive: the worst case the old floor turned into one cull a pass.
for n in (2, 3, 5, 9):
    asm = Asm({d: 0.0 for d in range(n)}, step_now=100000)
    mem = Mem({})                                            # no memory at all, so no brake can be crediting it
    c = run_cull(asm, mem)
    check(c == 0 and len(asm.cent) == n,
          f"{n} stale, inactive domains: 10% of {n} rounds to zero, so {c} culled and {len(asm.cent)} still live")

# ...and at ten the fraction stands on its own, so the fix removes nothing from a healthy population.
asm = Asm({d: 0.0 for d in range(10)}, step_now=100000)
check(run_cull(asm, Mem({})) == 1, "10 domains: int(0.10 x 10) = 1, so the proportional cull runs as before")
asm = Asm({d: 0.0 for d in range(40)}, step_now=100000)
check(run_cull(asm, Mem({})) == 4, "40 domains: 4 culled, the declared tenth")

# THE RATCHET ITSELF: cull repeatedly and see where it comes to rest.
asm = Asm({d: 0.0 for d in range(12)}, step_now=100000)
mem = Mem({})
for _ in range(40):
    run_cull(asm, mem)
check(len(asm.cent) == 9,
      f"forty passes over a dead population settle at {len(asm.cent)} domains, not 1 -- the ratchet has a bottom")


# --- 2. A DOMAIN HOLDING PROTECTED MEMORY IS NOT DELETED ----------------------------------------------------
print("\nTHE CULL DOES NOT DELETE WHAT THE FLOOR FORBIDS EVICTING")
# Two areas' worth of domains. `eng` (ids 0..9) is the area the schedule is not streaming: zero activity, long
# stale. It still owns the memory it earned. `py` (10..19) is being fed.
ENG = {d: 12000 for d in range(10)}                          # 12k entries each, well over a 2-source floor
asm = Asm({**{d: 0.0 for d in range(10)}, **{d: 500.0 for d in range(10, 20)}}, step_now=100000)
mem = Mem(ENG)
_fl = int(mem.src_floor * mem.cap / max(1, int(mem._eligible().sum())))
c = run_cull(asm, mem)
check(_fl > 0 and 12000 >= _fl, f"the per-source floor here is {_fl} entries and each eng domain holds 12000")
check(c == 0 and not mem.deleted,
      f"no domain of the absent area is culled and nothing is deleted ({c} culled, {len(mem.deleted)} deleted)")
check(asm.held == 2, f"...and the refusals are COUNTED ({asm.held}), so DID IT FIRE can show the brake holding")

# THE SAME POPULATION WITH THE BRAKE OFF is the pre-fix behaviour, and it must still be reachable: a knob that
# cannot reproduce the failure it was added for is a knob nobody can check.
asm2 = Asm({**{d: 0.0 for d in range(10)}, **{d: 500.0 for d in range(10, 20)}}, step_now=100000)
mem2 = Mem(ENG)
c2 = run_cull(asm2, mem2, floor_on=False)
check(c2 == 2 and len(mem2.deleted) == 2,
      f"DOM_CULL_FLOOR=0 deletes them as before ({c2} culled, {len(mem2.deleted)} source(s) deleted) -- "
      f"{2 * 12000} entries the floor would have refused to evict")

# --- 3. THE BRAKE RELEASES; IT IS NOT A PERMANENT VETO ------------------------------------------------------
print("\nA DOMAIN THAT HAS GENUINELY DRAINED IS STILL CULLED")
# Eviction is what drains a faded domain. Once it is below the floor there is nothing left to protect, and an
# empty-handed stale domain must still be removable or the population can only grow.
DRAINED = {d: 5 for d in range(10)}                          # five entries each: far under any floor
asm3 = Asm({**{d: 0.0 for d in range(10)}, **{d: 500.0 for d in range(10, 20)}}, step_now=100000)
mem3 = Mem(DRAINED)
c3 = run_cull(asm3, mem3)
check(c3 == 2 and asm3.held == 0,
      f"a domain drained to 5 entries is culled normally ({c3} culled, {asm3.held} held) -- the guard is a "
      f"floor test, not an ownership veto")

print("\ndomain_test: all checks passed" if not FAILED else f"\ndomain_test: {len(FAILED)} CHECK(S) FAILED")
raise SystemExit(1 if FAILED else 0)
