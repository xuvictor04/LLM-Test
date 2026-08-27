#!/usr/bin/env python3
"""Can a checkpoint be resumed into a fabric of a different size, and does the bookkeeping know which
slots actually came from it?

WHAT HAPPENED. A checkpoint trained at FAB_N0=256 FAB_NMAX=1024 was resumed by a command that set neither,
so it took the registry defaults FAB_N0=2048 FAB_NMAX=4096. It died inside torch:

    RuntimeError: Error(s) in loading state_dict for Fabric:
      size mismatch for A: copying a param with shape [1024, 768, 8] from checkpoint,
      the shape in current model is [4096, 768, 8].      ... and B, SRC_p, K_p, cent

Five tensor shapes and no knob name, after the corpus was pulled and the GPU was warm. The checkpoint has
recorded fab_cfg["cap"], ["rank"] and ["dk"] since it was written and nothing on the restore path read
them -- data recorded and never read, which is the same defect class as a mechanism that runs and does
nothing.

AND THE CRASH WAS THE LUCKY OUTCOME. The three [resume] lines it printed first say so:
    1525 of 2048 experts had no recorded birth step
    1813 of 2048 experts had no recorded UTILIZATION -- backfilled to the population mean 383.45
2048 - 1525 = 523, the checkpoint's live count. The other 1525 slots hold RANDOM INITIALISATION, and the
backfill was entering them as mature veterans at mean utilization: past grace, so cullable and on the
mature per-expert learning rate, yet ranked mid-population in a cull where they would displace genuinely
trained experts. The backfill's conservative direction -- unknown means EXPERIENCED -- is right for a slot
the checkpoint held but did not annotate, and exactly wrong for a slot the checkpoint never had.

Runs without torch: the cap-shaped tensors are stubbed by a shape-only stand-in, and the three blocks
under test are exec'd FROM THE ACTUAL SOURCE TEXT rather than restated here.
"""
import sys, textwrap

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


# ANCHOR ON THE BANNER, NOT ON "_wide_by = 0". That assignment appears twice on purpose -- once beside
# _regrown so part 2 of the resume can read it down any branch, and once inside the gate so the block is
# self-contained. Anchoring on it grabbed from the FIRST to the gate, i.e. a hundred unrelated lines, and
# this test failed with a NameError from code it was never meant to run. A brittle anchor makes a test
# report on the wrong text, which is worse than not having it.
GATE = block("# ---- FABRIC GEOMETRY: CHECKED BEFORE ANYTHING IS RESTORED",
             '        if FABRIC and _RD.get("fab_cfg"):\n            # RESTORED SLOTS')
BOOK = block('if FABRIC and _RD.get("fab_cfg"):\n            # RESTORED SLOTS',
             '        if WORLD_MODEL and _RD.get("world_cfg"):')
COPY = block('_fsd = dict(_RD["fab"])', "            _mk = fab.load_state_dict(_fsd, strict=False)")


class T:
    """Shape-only stand-in for a tensor: enough for the widening copy, nothing more."""
    def __init__(s, shape, fill=0.0):
        s.shape = tuple(shape)
        s.rows = [fill] * shape[0]          # one marker per slot, which is all the copy touches

    def dim(s): return len(s.shape)
    def detach(s): return s
    def clone(s):
        o = T(s.shape); o.rows = list(s.rows); return o

    def __setitem__(s, k, v):
        assert isinstance(k, slice) and k.start is None and k.step is None
        s.rows[:k.stop] = v.rows[:k.stop]


class Fab:
    def __init__(s, cap, n0, r=8, sd=None):
        s.cap, s.n_live, s.r = cap, n0, r
        s.born, s.uage, s.use = {}, {}, {}
        s._sd = sd or {}

    def state_dict(s): return dict(s._sd)


def run(code, ns):
    out = []
    ns.setdefault("print", lambda *a, **k: out.append(" ".join(str(x) for x in a)))
    ns.setdefault("FABRIC", True)
    ns.setdefault("_i", lambda k, d: {"FAB_DK": 32, "FAB_NMAX": 4096, "FAB_N0": 2048, "FAB_GRACE": 48}.get(k, d))
    exec(compile(code, "<self_organize>", "exec"), ns)
    return out


def cfg(cap=1024, n=523, rank=8, dk=32):
    return {"cap": cap, "n": n, "rank": rank, "dk": dk}


# --- 1. THE GATE NAMES A KNOB, NOT A TENSOR SHAPE ----------------------------------------------------------
print("THE GEOMETRY GATE REFUSES BY NAME, BEFORE ANYTHING IS RESTORED")

# the exact failure from the run: checkpoint cap 1024, this run 4096
ns = dict(_RD={"fab_cfg": cfg()}, fab=Fab(4096, 2048))
out = run(GATE, ns)
check(ns["_wide_by"] == 4096 - 1024, f"cap 1024 -> 4096 WIDENS by {ns['_wide_by']}, it does not refuse")
check(any("WIDENING" in l and "1024" in l and "4096" in l for l in out),
      f"...and says so: {out[0][:88] if out else '(silent)'}")

# narrowing must refuse: it would drop trained experts
try:
    run(GATE, dict(_RD={"fab_cfg": cfg(cap=4096)}, fab=Fab(1024, 256)))
    check(False, "cap 4096 -> 1024 should refuse")
except SystemExit as e:
    check("FAB_NMAX" in str(e) and "4096" in str(e),
          f"cap 4096 -> 1024 refuses and names the knob: {str(e)[:96]}...")

# rank and dk are inner dimensions: no prefix of them is meaningful
try:
    run(GATE, dict(_RD={"fab_cfg": cfg(rank=4)}, fab=Fab(4096, 2048, r=8)))
    check(False, "a rank change should refuse")
except SystemExit as e:
    check("FAB_RANK" in str(e), f"a rank change refuses and names FAB_RANK: {str(e)[:88]}...")
try:
    run(GATE, dict(_RD={"fab_cfg": cfg(dk=64)}, fab=Fab(4096, 2048)))
    check(False, "a dk change should refuse")
except SystemExit as e:
    check("FAB_DK" in str(e), f"a dk change refuses and names FAB_DK: {str(e)[:88]}...")

# and the case that must stay exactly as it was
ns = dict(_RD={"fab_cfg": cfg(cap=1024)}, fab=Fab(1024, 523))
out = run(GATE, ns)
check(ns["_wide_by"] == 0 and not out, "a same-cap resume is untouched and silent")

# --- 2. RESTORED vs NEW: OPPOSITE CONSERVATIVE DIRECTIONS --------------------------------------------------
print("\nA SLOT THE CHECKPOINT NEVER HELD IS A NEWBORN, NOT A VETERAN")

# reproduce the run exactly: 523 saved, 2048 live, 235 of the saved ones carried a use record
saved_born = {i: 100 + i for i in range(523)}
saved_use = {i: 300.0 + i for i in range(235)}
ns = dict(_RD={"fab_cfg": cfg(n=523), "fab_born": saved_born, "fab_uage": {i: 60.0 for i in range(523)},
               "fab_use": saved_use, "step": 24707},
          fab=Fab(4096, 2048))
out = run(BOOK, ns)
fab = ns["fab"]
new = list(range(523, 2048))
check(fab.n_live == 2048, f"n_live stays at FAB_N0 ({fab.n_live}) -- the new capacity is real capacity")
check(any(f"{len(new)} slot(s) are LIVE here but were not in the checkpoint" in l for l in out),
      f"...and the {len(new)} slots the checkpoint never held are named: "
      f"{[l for l in out if 'LIVE here' in l][0][:86] if any('LIVE here' in l for l in out) else '(silent)'}")
check(all(fab.born[i] == 24707 for i in new),
      f"every new slot is born AT THE RESUME STEP ({fab.born[new[0]]}), not at step 0")
check(all(fab.uage[i] == 0.0 for i in new),
      "every new slot has zero use-age, so grace protects it while it trains up")
check(all(i not in fab.use for i in new),
      "every new slot has NO utilization record -- grow() pops rather than zeroes, and this matches it")
# the restored ones keep the old, correct treatment
check(fab.born[0] == 100 and fab.uage[0] == 60.0 and fab.use[0] == 300.0,
      "a restored slot keeps exactly what the checkpoint recorded")
check(len(fab.use) == 523 and abs(fab.use[522] - (sum(saved_use.values()) / 235)) < 1e-6,
      f"a restored slot with no use record gets the mean of the RESTORED ones "
      f"({sum(saved_use.values())/235:.2f}), not a mean diluted by random slots")
# THE BUG, PINNED. Under the old code every one of these read as a mature veteran.
check(not any(fab.uage.get(i) == 48.0 for i in new),
      "no new slot is handed the grace THRESHOLD, which is what marked 1525 random slots as mature")

print("\n  ...and the mean must not be computed over slots that hold random initialisation")
ns2 = dict(_RD={"fab_cfg": cfg(n=523), "fab_born": {}, "fab_uage": {},
                "fab_use": {**saved_use, 900: 9999.0}, "step": 24707},   # a stray key past ck_n
           fab=Fab(4096, 2048))
run(BOOK, ns2)
check(900 not in ns2["fab"].use or ns2["fab"].use[900] != 9999.0,
      "a use record for a slot beyond the checkpoint's live count is dropped, not averaged in")

print("\n  ...and a same-size resume behaves exactly as before")
ns3 = dict(_RD={"fab_cfg": cfg(n=523), "fab_born": saved_born, "fab_uage": {i: 60.0 for i in range(523)},
                "fab_use": saved_use, "step": 24707},
           fab=Fab(1024, 523))
out3 = run(BOOK, ns3)
check(ns3["fab"].n_live == 523 and not any("LIVE here" in l for l in out3),
      "no new slots, no new message: the path an ordinary resume takes is unchanged")

# --- 3. THE WIDENING COPY IS A PREFIX, AND ONLY A PREFIX ---------------------------------------------------
print("\nTHE WIDENING COPY OVERWRITES THE PREFIX AND LEAVES THE REST AT ITS INITIALISATION")
D, R, DK, SIGD = 768, 8, 32, 64
ck = {"A": T((1024, D, R), "ck"), "B": T((1024, R, D), "ck"), "SRC_p": T((1024, DK), "ck"),
      "K_p": T((1024, DK), "ck"), "cent": T((1024, SIGD), "ck"),
      "halt_key": T((DK,), "ck"), "halt_b": T((1,), "ck")}
cur = {"A": T((4096, D, R), "init"), "B": T((4096, R, D), "init"), "SRC_p": T((4096, DK), "init"),
       "K_p": T((4096, DK), "init"), "cent": T((4096, SIGD), "init"),
       "halt_key": T((DK,), "init"), "halt_b": T((1,), "init")}
ns = dict(_RD={"fab": ck}, fab=Fab(4096, 2048, sd=cur), _wide_by=3072, _ck_cap=1024)
out = run(COPY, ns)
sd = ns["_fsd"]
for k in ("A", "B", "SRC_p", "K_p", "cent"):
    check(sd[k].shape == cur[k].shape, f"{k} is handed over at THIS run's shape {sd[k].shape}")
    check(all(x == "ck" for x in sd[k].rows[:1024]), f"  ...rows 0..1023 are the checkpoint's")
    check(all(x == "init" for x in sd[k].rows[1024:]), f"  ...rows 1024..4095 keep their initialisation")
for k in ("halt_key", "halt_b"):
    check(sd[k] is ck[k], f"{k} is cap-independent and is passed through untouched")
check(any("widened 5 fabric tensor" in l for l in out),
      f"...and it reports what it widened: {[l for l in out if 'widened' in l][0][:80] if any('widened' in l for l in out) else '(silent)'}")

print("\n  ...and a cap-shaped tensor this code does not know about is refused, not left to torch")
ck2 = dict(ck); ck2["mystery"] = T((7, 5), "ck")
cur2 = dict(cur); cur2["mystery"] = T((9, 3), "init")          # not a prefix in ANY dimension
try:
    run(COPY, dict(_RD={"fab": ck2}, fab=Fab(4096, 2048, sd=cur2), _wide_by=3072, _ck_cap=1024))
    check(False, "an unreconcilable tensor should refuse")
except SystemExit as e:
    check("mystery" in str(e) and "FAB_NMAX=1024" in str(e),
          f"it names the tensor and the way out: {str(e)[:96]}...")

print()
if FAILED:
    print(f"resume_test: {len(FAILED)} CHECK(S) FAILED")
    for f in FAILED:
        print(f"  - {f}")
    sys.exit(1)
print("resume_test: all checks passed")
