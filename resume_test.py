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
# END ANCHORS ARE THE NEXT BANNER, and inserting a block between two of them breaks this LOUDLY. That has now
# happened three times in one session -- here, when the growth-controller restore landed between the
# bookkeeping and the world model; in section 1, when a second "_wide_by = 0" appeared; and in corpus_test.py,
# when the capacity-gate warning landed inside its span. Every one failed with a NameError from code the test
# was never written for, which is the correct failure: a test that quietly reports on the WRONG text is worth
# less than no test. Anchor on distinctive banner comments, and let drift stop the suite.
BOOK = block('if FABRIC and _RD.get("fab_cfg"):\n            # RESTORED SLOTS',
             "        # ...AND THE GROWTH CONTROLLER'S MEMORY COMES BACK WITH THE POPULATION IT BUILT")
COPY = block('_fsd = dict(_RD["fab"])', "            _mk = fab.load_state_dict(_fsd, strict=False)")
# widen_prefix is module level, so it can be exercised directly rather than through the resume path -- which
# matters because BOTH preallocated geometries now go through it: the fabric's slots and the softmax width.
_wp = {}
exec(compile(block("def widen_prefix(live_sd, ck_sd):", "\ndef bwt_of("), "<self_organize>", "exec"), _wp)
WIDEN = _wp["widen_prefix"]


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
ns = dict(_RD={"fab": ck}, fab=Fab(4096, 2048, sd=cur), _wide_by=3072, _ck_cap=1024,
          widen_prefix=WIDEN)
out = run(COPY, ns)
sd = ns["_fsd"]
for k in ("A", "B", "SRC_p", "K_p", "cent"):
    check(sd[k].shape == cur[k].shape, f"{k} is handed over at THIS run's shape {sd[k].shape}")
    check(all(x == "ck" for x in sd[k].rows[:1024]), f"  ...rows 0..1023 are the checkpoint's")
    check(all(x == "init" for x in sd[k].rows[1024:]), f"  ...rows 1024..4095 keep their initialisation")
for k in ("halt_key", "halt_b"):
    check(sd[k] is ck[k], f"{k} is cap-independent and is passed through untouched")
# COUNTED AGAINST WHAT SHOULD HAVE WIDENED, not just counted. `cent` is a BUFFER registered after the fact,
# so a checkpoint predating it simply has no such key: widen_prefix never sees it, load_state_dict(strict=False)
# never misses it, and every RESTORED expert's routing region comes back at random init. A bare count cannot
# catch an absence.
check(any("widened 5 of 5 cap-shaped fabric tensor" in l for l in out),
      f"...and it reports what it widened AGAINST the cap-shaped total: "
      f"{[l for l in out if 'widened' in l][0][:74] if any('widened' in l for l in out) else '(silent)'}")
check(not any("NOT IN THE CHECKPOINT" in l for l in out),
      "...and says nothing about absentees when there are none")

print("\n  ...and a cap-shaped tensor MISSING from the checkpoint is named, not counted past")
ck_nocent = {k: v for k, v in ck.items() if k != "cent"}
ns_nc = dict(_RD={"fab": ck_nocent}, fab=Fab(4096, 2048, sd=cur), _wide_by=3072, _ck_cap=1024,
             widen_prefix=WIDEN)
out_nc = run(COPY, ns_nc)
check(any("widened 4 of 5" in l for l in out_nc),
      f"4 of 5 widened, and the total is stated so the gap is visible")
check(any("NOT IN THE CHECKPOINT" in l and "cent" in l for l in out_nc),
      "...and `cent` is named as absent rather than silently left at init")
check(any("keep their adapters and lose their addresses" in l for l in out_nc),
      "...with what that actually costs: the routing region of every restored expert")

print("\n  ...and a cap-shaped tensor this code does not know about is refused, not left to torch")
ck2 = dict(ck); ck2["mystery"] = T((7, 5), "ck")
cur2 = dict(cur); cur2["mystery"] = T((9, 3), "init")          # not a prefix in ANY dimension
try:
    run(COPY, dict(_RD={"fab": ck2}, fab=Fab(4096, 2048, sd=cur2), _wide_by=3072, _ck_cap=1024,
                   widen_prefix=WIDEN))
    check(False, "an unreconcilable tensor should refuse")
except SystemExit as e:
    # THE REFUSAL MUST NAME THE DIMENSION THAT DIFFERS, NOT THE KNOB WE ASSUMED. The widening predicate tests
    # "leading dim grew, trailing dims match", which is a PROXY for cap-shaped rather than a check of it -- so a
    # tensor failing it may be failing on FAB_RANK, FAB_DK, SIG_D or D_MODEL, and pointing at FAB_NMAX sends the
    # reader to change the one knob that is fine.
    check("mystery" in str(e) and "(7, 5) vs (9, 3)" in str(e),
          f"it names the tensor and both shapes: {str(e)[:88]}...")
    check("trailing dimension" in str(e) and "FAB_RANK" in str(e),
          "...and explains that a trailing dimension is the expert's own geometry, with the knobs that set it")
    # Counting mentions was the wrong assertion: the message names FAB_NMAX twice ON PURPOSE -- once for the
    # case where the leading dimension really did shrink, and once to say it is NOT the answer otherwise. The
    # property that matters is the disclaimer, not the word count.
    check("not FAB_NMAX" in str(e),
          "...and explicitly disclaims FAB_NMAX for a mismatch that is not about the cap")

# --- 4. WIDENING MOVES THE CAPACITY GATE, AND THREE MECHANISMS LIVE BEHIND IT ------------------------------
# The cap is not a free parameter. cull_gate_open is n_live/cap >= FAB_PRESSURE, and its own docstring
# records the cost of getting this wrong: "a wrong answer here does not fail, it silently removes three
# things from the run ... `fabric.spare` read ARMED AND INERT for a whole investigation." A resume that
# widens divides that ratio without touching the population, so it can shut a gate that was open in the run
# being resumed -- which is what FAB_NMAX=4096 would have done here, and it was my own recommendation.
print("\nTHE CAP IS NOT A FREE PARAMETER")
_gate_ns = {"__builtins__": __builtins__}
exec(compile(block("def cull_gate_open(n_live, cap, pressure):", "\ndef bwt_of("),
             "<self_organize>", "exec"), _gate_ns)
gate = _gate_ns["cull_gate_open"]
P = 0.45
check(gate(523, 1024, P), "523 experts in the checkpoint's 1024 cap = 0.51: the gate was OPEN")
check(not gate(523, 4096, P), "the same 523 in a 4096 cap = 0.128: widening SHUTS it")
check(not gate(1046, 4096, P),
      "...and it stays shut after the added area grows a population the size of the original (1046 = 0.26)")
check(gate(1046, 2048, P),
      "at cap 2048 that same 1046 is 0.51 -- the regime the original run ended in, which is the sizing rule")
check(not gate(523, 2048, P), "...while 523 starts at 0.26, so there is room to grow into it first")
check(not gate(2, 1, P) and not gate(1, 1, P), "n_live <= 2 is a floor, not a pressure test")

print("\n  ...and the run says so at startup rather than leaving it to DID IT FIRE afterwards")
WARN = block("# WIDENING THE FABRIC MOVES THE CAPACITY GATE",
             "    # TWO WRITE PATHS, AND ONLY ONE CARRIES THE OWNER.")
# The condition is "can the gate reopen", not "is it shut". 523 experts: doubling to 1046 clears 0.45 at
# cap 2048 (921) but not at cap 4096 (1843). A run that merely STARTS below pressure and grows into it is
# the healthy case and must stay quiet, or the warning is noise and nobody reads it.
# AND IT MUST AGREE WITH THE CULL GATE BANNER, which reads the same state later in the same startup. The ramp
# builds toward FAB_RAMP_TO x cap without reading the loss, and at the registry defaults 0.5 > 0.45, so on a
# FRESH run it always overshoots the gate -- warning there would contradict the banner. On a RESUME whose latch
# came back in the checkpoint the ramp will not fire at all, so nothing is coming and the warning is the correct
# one. Both now consult ramp_done. `latched=True` is the resume case.
for cap, wide, latched, want in ((4096, 3072, True,  True),   # resumed+latched: 1046 < 1843 and no ramp coming
                                 (4096, 3072, False, False),  # ramp still armed: it builds to 2048, banner is right
                                 (2048, 1024, True,  False),  # 1046 > 921: the area's own growth reopens it
                                 (1024, 0,    True,  False),  # not widened at all
                                 (8192, 7168, True,  True),   # further out of reach, and no ramp coming
                                 (1024, 512,  True,  False)): # 1046 > 460, fine
    ns = dict(FABRIC=True, _wide_by=wide, fab=Fab(cap, 523), _warn=[], _f=lambda k, d: d,
              _i=lambda k, d: d, fabgrow=type("G", (), {"ramp_done": latched})())
    run(WARN, ns)
    check(bool(ns["_warn"]) == want,
          f"cap {cap - wide} -> {cap}, 523 experts, ramp {'LATCHED' if latched else 'armed'}: "
          f"{'WARNS' if ns['_warn'] else 'quiet'} -- gate at {int(P * cap)}, 2x population is 1046")
ns = dict(FABRIC=True, _wide_by=3072, fab=Fab(4096, 523), _warn=[], _f=lambda k, d: d,
          _i=lambda k, d: d, fabgrow=type("G", (), {"ramp_done": True})())
run(WARN, ns)
w = ns["_warn"][0]
check("FAB_NMAX=2048" in w,
      f"...and it names the cap that would have been right, computed not guessed: "
      f"{[x for x in w.split() if x.startswith('FAB_NMAX=')][0]}")
check("1843" in w, "...and where the gate would reopen at the cap actually chosen (0.45 x 4096 = 1843)")
check("ARMED AND INERT" in w,
      "...and that the three mechanisms will read ARMED AND INERT because of THIS, not as a finding")

# --- 5. THE RAMP MUST NOT RE-ARM BECAUSE THE CAP MOVED ------------------------------------------------------
# The ramp exists to BUILD the population and, in the file's own words, "it is built once". Its latch is
# `n >= ramp_to * pool` judged against fab.cap, so widening moves the threshold out from under an already-
# built population: 523 experts have latched at cap 1024 (523 >= 512) and have not at cap 2048 (523 < 1024)
# or 4096 (523 < 2048). PlateauGrowth is rebuilt from env every run and was never in the checkpoint, so
# every resume started with ramp_done=False. The ramp never reads the loss -- it mints on no evidence.
print("\nTHE GROWTH CONTROLLER'S MEMORY SURVIVES THE BOUNDARY")
import ast as _ast
_tree = _ast.parse(SRC)
_cls = next((n for n in _tree.body if isinstance(n, _ast.ClassDef) and n.name == "PlateauGrowth"), None)
if _cls is None:
    check(False, "PlateauGrowth is no longer a module-level class -- this test cannot find its subject")
else:
    _pg = {"_env": lambda k, d=None: d}
    exec(compile(_ast.Module(body=[_cls], type_ignores=[]), "<self_organize>", "exec"), _pg)
    PlateauGrowth = _pg["PlateauGrowth"]

    # BUILD IT THE WAY THE RUN DOES, NOT THE WAY THE SIGNATURE DEFAULTS DO. PlateauGrowth's own signature has
    # ramp=0, so PlateauGrowth(0.002, 400, 300) has NO ramp at all and every ramp assertion below passes
    # vacuously -- which is what the first version of this test did, and it reported "0 ramp events" while
    # claiming to measure the ramp. The call site at self_organize.py:3905 passes _i("FAB_RAMP", 4000), and
    # the registry default is 4000, so a real run always has one. Mirror the call site exactly.
    def build():
        return PlateauGrowth(0.002, 400, 300,        # FAB_PLATEAU, FAB_COOLDOWN, FAB_WARMUP
                             4.0, 1, 4000,           # FAB_Z, FAB_BURST, FAB_RAMP
                             600, 20000,             # FAB_RECOVER_MIN, FAB_RECOVER_MAX
                             0.10, 0.5)              # FAB_RAMP_RATE, FAB_RAMP_TO

    # what the latch does at each cap, from the REAL class
    for cap, want_latched in ((1024, True), (2048, False), (4096, False)):
        g = build()
        g.step(2.0, 1000, 523, cap, pool=cap)
        check(g.ramp_done == want_latched,
              f"a FRESH controller at cap {cap} with 523 live: ramp {'latches' if g.ramp_done else 'ARMS'} "
              f"(threshold {int(g.ramp_to * cap)})")

    # ...and how many experts a re-armed ramp mints on no evidence, over a flat loss
    def mint(cap, latched, steps=20000):
        """Count experts created, BY REASON. A flat loss also stalls, so a bare total cannot tell ramp growth
        from stall growth -- and the claim here is specifically about the ramp, which never reads the loss."""
        g = build()
        if latched:
            g.ramp_done = True
        n, by = 523, {}
        for t in range(0, steps, 16):                       # BATCH_W=16 flush cadence
            b = min(g.step(2.0, t, n, cap, pool=cap), cap - n)   # FLAT loss: nothing has changed
            if b > 0:
                by[g.why] = by.get(g.why, 0) + b
                n += b
        return by

    for cap in (2048, 4096):
        fresh, kept = mint(cap, latched=False), mint(cap, latched=True)
        check(fresh.get("ramp", 0) > 0,
              f"cap {cap}, latch NOT restored: +{fresh.get('ramp', 0)} experts from the RAMP on a FLAT loss "
              f"(all reasons: { {k: v for k, v in fresh.items()} })")
        check(kept.get("ramp", 0) == 0,
              f"cap {cap}, latch RESTORED: +{kept.get('ramp', 0)} from the ramp -- growth must now come from a "
              f"regression or a stall (all reasons: { {k: v for k, v in kept.items()} })")
        check(sum(fresh.values()) > sum(kept.values()),
              f"...and the difference is what the cap alone would have added: "
              f"{sum(fresh.values())} vs {sum(kept.values())} experts over {20000} steps")
    # At the checkpoint's OWN cap nothing changes either way -- the population had already latched it.
    same = mint(1024, latched=False)
    check(same.get("ramp", 0) == 0,
          f"at the checkpoint's cap 1024 the ramp latches on its own first call, restored or not "
          f"(reasons: { {k: v for k, v in same.items()} })")

    # THE OTHER HALF: the EMA that detects an arriving area is seeded from the material it is supposed to
    # detect. A fresh controller cannot see the boundary it exists for.
    print("\n  ...and the slow EMA is what makes an arriving area visible at all")
    g_fresh, g_kept = build(), build()
    for t in range(0, 6000, 16):                            # 'English': settled around 2.0
        g_fresh.step(2.0, t, 523, 1024, pool=1024)
    g_kept.__dict__.update({k: getattr(g_fresh, k) for k in
                            ("fast", "slow", "dev", "n", "ramp_done", "last", "last_regr", "blackout",
                             "t0", "state", "n_ramp", "n_stall", "n_regr", "n_regr_supp")})
    g_new = build()                                          # what a resume built until now
    g_new.ramp_done = True                                   # isolate the EMA effect from the ramp effect
    seen_kept = seen_new = 0
    for t in range(6000, 12000, 16):                         # 'Python' arrives: loss jumps to 3.4
        if g_kept.step(3.4, t, 523, 1024, pool=1024) and g_kept.why == "REGRESSION": seen_kept += 1
        if g_new.step(3.4, t, 523, 1024, pool=1024) and g_new.why == "REGRESSION": seen_new += 1
    check(seen_kept > 0,
          f"a RESTORED EMA carries the old level, so the arrival registers as a REGRESSION ({seen_kept}x)")
    check(seen_new == 0,
          f"a FRESH EMA seeds from the new material's own loss and sees nothing ({seen_new}x) -- the trigger "
          f"this file calls 'the only signal continual learning has' was blind at the boundary")

print("\n  ...and the restore block itself runs, on the real source")
RESTORE = block("# ...AND THE GROWTH CONTROLLER'S MEMORY COMES BACK WITH THE POPULATION IT BUILT",
                '        if WORLD_MODEL and _RD.get("world_cfg"):')


class FG:
    def __init__(s):
        s.fast = s.slow = s.dev = None; s.n = 0; s.ramp_done = False
        s.last = s.last_regr = s.blackout = s.t0 = 0; s.state = "W"
        s.n_ramp = s.n_stall = s.n_regr = s.n_regr_supp = 0; s.ramp_to = 0.5


saved = {"fast": 2.01, "slow": 2.04, "dev": 0.03, "n": 375, "ramp_done": True, "last": 24000,
         "last_regr": 0, "blackout": 0, "t0": 0, "state": "W", "n_ramp": 12, "n_stall": 3,
         "n_regr": 0, "n_regr_supp": 0}
ns = dict(FABRIC=True, fabgrow=FG(), fab=Fab(4096, 523), _RD={"fabgrow": saved}, _fg_base={})
out = run(RESTORE, ns)
# THE COUNTERS ARRIVE CUMULATIVE, AND POPULATION CHURN REPORTS "growth fired: Nx" AS THIS RUN. Carrying the
# controller is the point of the block, but n_ramp/n_regr/n_stall came with it, so after a resume the churn
# line was attributing the PREVIOUS run's growth events to this one -- in the report the continual-learning
# claim is read out of. The baseline recorded here is what lets the report subtract them.
check(ns["_fg_base"] == {"n_ramp": 12, "n_stall": 3, "n_regr": 0, "n_regr_supp": 0},
      f"the restore records the counts it arrived with: {ns['_fg_base']}")
check(ns["fabgrow"].n_ramp == 12,
      "...while the controller keeps the cumulative total, so the chain's history is not thrown away")
_gr = {k: getattr(ns["fabgrow"], k) - ns["_fg_base"].get(k, 0)
       for k in ("n_ramp", "n_stall", "n_regr", "n_regr_supp")}
check(_gr == {"n_ramp": 0, "n_stall": 0, "n_regr": 0, "n_regr_supp": 0},
      f"...so a run that has grown nothing yet reports {_gr['n_ramp']}x on the RAMP, not 12x")
ns_fresh = dict(FABRIC=True, fabgrow=FG(), fab=Fab(4096, 523), _RD={}, _fg_base={})
run(RESTORE, ns_fresh)
check(ns_fresh["_fg_base"] == {},
      "a checkpoint with no controller state records no baseline, so a fresh run subtracts nothing")
check(ns["fabgrow"].ramp_done and abs(ns["fabgrow"].slow - 2.04) < 1e-9,
      "the restore block puts the latch and the EMAs back")
check(any("stays latched" in l and "4096" in l for l in out),
      "...and says the latch holds at the WIDER cap, which is the whole point")
check(any("carries the PREVIOUS material's level" in l for l in out),
      "...and that the EMA is what will make the arriving area visible")
ns2 = dict(FABRIC=True, fabgrow=FG(), fab=Fab(4096, 523), _RD={}, _fg_base={})
out2 = run(RESTORE, ns2)
check(any("predates the growth controller being saved" in l for l in out2),
      "an older checkpoint keeps the old behaviour and is TOLD so, not silently re-armed")
check(any("FAB_RAMP_TO<=0.1277" in l for l in out2),
      f"...with the value that would latch it immediately: "
      f"{[l for l in out2 if 'FAB_RAMP_TO' in l][0].split('FAB_RAMP_TO')[1][:12] if any('FAB_RAMP_TO' in l for l in out2) else '(none)'}")

# --- 6. TWO OPTIMIZERS, TWO INDEPENDENT HAZARDS ------------------------------------------------------------
# _wide_by is a fact about the FABRIC's cap-shaped parameters, all of which are in om. oe is
# AdamW(enc.parameters()) and holds nothing sized by fab.cap, so widening cannot invalidate one of its
# moments -- yet the first version of this fix dropped them anyway, because both loads shared a line. enc
# produces `gist`: the routing query, and the space every centroid lives in. Resetting its Adam state at the
# exact boundary where a new area's signatures first arrive is the worst available moment, and the message
# blamed the fabric for it. A quantity computed for one consumer and spent on another -- committed while
# fixing that very class of bug, which is why this section exists.
print("\nEACH OPTIMIZER IS SKIPPED FOR ITS OWN REASON, OR NOT AT ALL")
OPT = block("# ONE FLAG WAS GATING TWO OPTIMIZERS", '        _mk = _RD["mem_keys"]')


class Opt:
    def __init__(s, name): s.name, s.loaded = name, False
    def load_state_dict(s, d): s.loaded = True


# A THIRD REASON THE MODEL'S MOMENTS CANNOT BE RESTORED, and the one I missed. emb.weight, head.weight and
# head.bias are all in om, so widening the SOFTMAX invalidates its moments exactly as widening the fabric
# does -- and the skip was gated on _wide_by alone. A resume that raises VMAX without touching FAB_NMAX
# therefore loaded moments shaped for the old vocabulary, cleanly, and would die at the first om.step().
# Masked on both harness paths only because they happen to widen the fabric too: a latent crash, not a
# theoretical one, and it is the same bug the commit that introduced it is named for.
for wide, mwide, resized, want_m, want_e in (
        (0, 0, False, True, True),        # ordinary resume: both restore
        (3072, 0, False, False, True),    # fabric widened: only om is affected
        (0, 3, False, False, True),       # VMAX widened alone: om is STILL affected -- the case I missed
        (0, 0, True, True, False),        # encoder resized: only oe is affected
        (3072, 3, True, False, False)):   # everything
    om_, oe_ = Opt("m"), Opt("e")
    ns = dict(_wide_by=wide, _mwide=mwide, _enc_resized=resized, om=om_, oe=oe_,
              _RD={"opt_m": {}, "opt_e": {}})
    out = run(OPT, ns)
    check(om_.loaded == want_m and oe_.loaded == want_e,
          f"_wide_by={wide} _mwide={mwide} _enc_resized={resized}: "
          f"model {'restored' if om_.loaded else 'skipped'}, "
          f"encoder {'restored' if oe_.loaded else 'skipped'}")
    if mwide and not wide:
        check(any("widened for a larger VMAX" in l for l in out),
              "...and a VMAX-only widening says so in its own words, not the fabric's")
    if wide and not resized:
        check(any("ENCODER's moments are unaffected and are restored" in l for l in out),
              "...and a widened fabric says so explicitly, rather than blaming the fabric for the encoder")
    if resized:
        check(any("ENCODER optimizer's moments are not restored" in l for l in out),
              "...and a resized embedding is named as its own, different reason")

print("\n  ...and _load_enc reports the reshape rather than leaving the caller to guess")
_src = block("def _load_enc(enc, sd):", "\n# ALLOCATED LAZILY")


class Enc:
    def __init__(s): s.sd = None
    def load_state_dict(s, d): s.sd = d


class W:
    def __init__(s, n): s.n = n
    def size(s, i): return s.n
    def __getitem__(s, k): return W(k.stop)


for rows, encv, want in ((512, 512, False), (1024, 512, True)):
    ns = {"ENC_V": encv, "print": lambda *a, **k: None}
    exec(compile(_src, "<self_organize>", "exec"), ns)
    e = Enc()
    got = ns["_load_enc"](e, {"emb.weight": W(rows)})
    check(got == want,
          f"a {rows}-row saved embedding into ENC_V={encv}: _load_enc returns {got} "
          f"({'reshaped, so the moments are stale' if want else 'unchanged, so they are fine'})")

# --- 7. THE CULL BUDGET, AND THE SIGN OF RETENTION ---------------------------------------------------------
# Both found in pilot_gru_py.log, the first run that ever crossed a run boundary.
print("\nTHE CULL BUDGET IS SIZED ON THE SET IT CAN BE SPENT ON")
# The comment above the ranking explains why RANKING happens inside _elig; the budget was left on n_live.
# Measured in that run: n_live 523, eligible 84 (the [experts] lines print it -- "ranked among the 84 past
# their ..."), FAB_CULL_FRAC 0.02. It removed 10 a pass where the intent is 1, and _elig shrank 84 -> 75 -> 65
# as it ate through them. 159 removed against 84 grown; the population fell 523 -> 448 while a whole new
# language was being added, and the churn line read "100% of all growth was replaced rather than added".
for n_live, elig, frac in ((523, 84, 0.02), (523, 75, 0.02), (523, 65, 0.02), (523, 523, 0.02), (100, 3, 0.02)):
    was, now = max(1, int(frac * n_live)), max(1, int(frac * elig))
    check(now <= was,
          f"n_live {n_live}, eligible {elig}: budget {was} -> {now} "
          f"({'unchanged' if now == was else f'{was / now:.0f}x less aggressive'})")
check(max(1, int(0.02 * 84)) == 1 and max(1, int(0.02 * 523)) == 10,
      "the run's own numbers: 10 removed a pass where 1 was intended -- a 10x over-cull, aimed entirely at "
      "the trained population a resume exists to preserve")
check(max(1, int(0.02 * 3)) == 1,
      "and the max(1, ...) floor still lets a tiny eligible set be culled at all, rather than deadlocking")

print("\nRETENTION'S SUBTRACTION RUNS THE SAME WAY AS bwt_of")
# bits/byte is LOWER-IS-BETTER, so forgetting is latest MINUS earliest. The section computed earliest minus
# latest while printing "a positive number is FORGETTING" two lines down -- so every genuine case of
# forgetting arrived with the sign that means retention. From the run: process 0 (eng) 2.114 -> 2.223 got
# WORSE and was reported -0.109; process 1 (py) 1.447 -> 1.103 got BETTER and was reported +0.344. The
# verdict "DRIFTING -- earlier material is measurably worse" printed BECAUSE PYTHON IMPROVED.
RUN = [(0, 2.114, 2.223, 2816, "eng"), (1, 1.447, 1.103, 4879, "py")]
OLD_NAMES = {"eng"}                                   # py was NEW this run: it has no prior probe
for _p, e, l, _n, nm in RUN:
    worse = l > e
    check((l - e > 0) == worse,
          f"process {_p} ({nm}) {e:.3f} -> {l:.3f}: drift {l - e:+.3f} "
          f"-- {'worse, and positive' if worse else 'better, and negative'}")
    check((e - l > 0) != worse or not worse,
          f"  ...the old subtraction gave {e - l:+.3f}, which says the opposite")
_judge = [r for r in RUN if r[4] in OLD_NAMES]
worst_new = max(l - e for _p, e, l, _n, nm in _judge)
mean_old = sum(e - l for _p, e, l, _n, nm in RUN) / len(RUN)
check(abs(worst_new - 0.109) < 1e-9,
      f"the verdict is taken over the {len(_judge)} process(es) that existed before: worst {worst_new:+.3f}")
check(abs(mean_old - 0.1175) < 1e-3 and mean_old > 0,
      f"the old mean over ALL processes was {mean_old:+.3f} -- driven by py IMPROVING by 0.344, which a "
      f"retention figure must not be able to absorb")
check(worst_new > 0.10,
      "so the run's verdict is still DRIFTING -- but now because English genuinely drifted, not because "
      "Python learned")

# --- 8. THE VOCABULARY IS THE OTHER PREALLOCATED GEOMETRY --------------------------------------------------
# VMAX is the softmax width; under TOK_ONLINE the model is built to it and the tokenizer mints into it for the
# whole run. emb.weight [V,d], head.weight [V,d] and head.bias [V] are all leading-dim-V, so raising VMAX is
# the same prefix relation the fabric slots have. The run that added Python printed "grew 2048 -> 2048 during
# training (+0)": the checkpoint's vocabulary already filled VMAX=2048, so the new language got not one token
# of its own and was segmented entirely with English's merges. New EXPERTS, no new TOKENS.
print("\nVMAX WIDENS THE SAME WAY THE SLOT POOL DOES")
D = 768
ck_m = {"emb.weight": T((2048, D), "ck"), "head.weight": T((2048, D), "ck"),
        "head.bias": T((2048,), "ck"), "gru.weight_ih_l0": T((3 * D, D), "ck")}
cur_m = {"emb.weight": T((4096, D), "init"), "head.weight": T((4096, D), "init"),
         "head.bias": T((4096,), "init"), "gru.weight_ih_l0": T((3 * D, D), "init")}
sd_m, grew_m, bad_m = WIDEN(cur_m, ck_m)
check(not bad_m, f"a doubled VMAX reconciles cleanly ({len(grew_m)} tensors widened, {len(bad_m)} refused)")
for k in ("emb.weight", "head.weight", "head.bias"):
    check(sd_m[k].shape == cur_m[k].shape, f"{k} arrives at this run's shape {sd_m[k].shape}")
    check(all(x == "ck" for x in sd_m[k].rows[:2048]) and all(x == "init" for x in sd_m[k].rows[2048:]),
          f"  ...ids 0..2047 keep their trained rows; 2048.. are unminted ids at their initialisation")
check(sd_m["gru.weight_ih_l0"] is ck_m["gru.weight_ih_l0"],
      "a tensor not sized by the vocabulary is passed through untouched")

# Narrowing must NOT be silently absorbed -- it would drop trained token rows.
sd_n, grew_n, bad_n = WIDEN({"emb.weight": T((1024, D), "init")}, {"emb.weight": T((2048, D), "ck")})
check(not grew_n and len(bad_n) == 1,
      f"a NARROWED vocabulary is refused, not truncated: {bad_n}")
# ...and a change that is not a leading-dimension change at all is refused too.
sd_d, grew_d, bad_d = WIDEN({"emb.weight": T((2048, 1024), "init")}, {"emb.weight": T((2048, D), "ck")})
check(not grew_d and len(bad_d) == 1, f"a D_MODEL change is refused rather than reinterpreted: {bad_d}")
# An identical geometry is a complete no-op, so an ordinary resume is untouched.
sd_s, grew_s, bad_s = WIDEN(cur_m, {k: T(v.shape, "ck") for k, v in cur_m.items()})
check(not grew_s and not bad_s, "an identical geometry widens nothing and refuses nothing")

# --- 9. FOUR CLAIMS I MADE AND NEVER CHECKED -----------------------------------------------------------
# Audited after the first continual-learning run. Two were true and worse than stated, one was partly wrong
# in my wording, one was true with a consequence I had understated.
print("\nACCUM COUNTS BACKWARD PASSES, NOT WINDOWS")
# `step` advances per WINDOW; the gate's body runs once per FLUSH; om.step()/om.zero_grad() are the only
# calls to either in the loop. `(step + 1) % ACCUM` therefore asked a window question about a per-backward
# decision. With g = gcd(BATCH_W, ACCUM) it is all-or-nothing whenever ACCUM divides BATCH_W -- which is
# every ACCUM worth setting at the BATCH_W=16 longrun.sh hardcodes -- and _bx is cleared at the epoch roll,
# so which way it lands can flip per epoch. fetch_big.py prints ACCUM=4 BATCH_W=16 as the heavy-run command.


def accum_steps(BATCH_W, ACCUM, s0, gate, windows=4000):
    bx, step, nbwd, flushes, taken = 0, s0, 0, 0, 0
    for _ in range(windows):
        bx += 1
        if bx < BATCH_W:
            step += 1
            continue
        flushes += 1; nbwd += 1
        if gate(step, nbwd, ACCUM):
            taken += 1
        bx = 0; step += 1
    return flushes, taken


OLD = lambda step, nbwd, A: (step + 1) % A == 0
NEW = lambda step, nbwd, A: nbwd % A == 0
for BW, AC in ((16, 1), (16, 2), (16, 4), (12, 4)):
    old_counts = {accum_steps(BW, AC, s0, OLD)[1] for s0 in range(4)}
    new_counts = {accum_steps(BW, AC, s0, NEW)[1] for s0 in range(4)}
    f = accum_steps(BW, AC, 0, NEW)[0]
    check(len(new_counts) == 1 and new_counts != {0},
          f"BATCH_W={BW} ACCUM={AC}: the new gate takes {new_counts.pop()} step(s) of {f} flushes at EVERY "
          f"starting offset")
    if AC > 1:
        # THIS IS A SIMULATION RESULT AND IT ASSUMES FLUSHES SIT AT A FIXED RESIDUE mod BATCH_W. They do not:
        # the real loop also flushes at segment boundaries and clears the batch at the epoch roll, so positions
        # drift. Measured on two real runs identical but for that one line, BATCH_W=4 ACCUM=4, ~52 backward
        # passes: the OLD gate made 55 om.step() calls and the new one 13. So the observed failure is that ACCUM
        # accumulated NOTHING -- it stepped about once per backward pass whatever it was set to -- not that an
        # epoch took zero steps. The zero case is what this simulation shows and what the arithmetic permits;
        # it is not what was seen, and the distinction is kept here rather than let the stronger claim stand.
        check(0 in old_counts and len(old_counts) > 1,
              f"  ...where the old gate took {sorted(old_counts)} across offsets IN SIMULATION (fixed-residue "
              f"assumption). Measured in a real run it over-stepped instead: 55 calls where 13 were due")
check(accum_steps(16, 4, 0, NEW)[1] == accum_steps(16, 4, 0, NEW)[0] // 4,
      "and ACCUM=4 now genuinely steps once per four backward passes, which is what it is for")

print("\nTHE LEARNING CURVE KEEPS THE PROCESS AND THE ACTIVE FLAG")
_cb = {}
exec(compile(block("def _curve_by_step(curve):", "\ndef bwt_of("), "<self_organize>", "exec"), _cb)
curve_by_step = _cb["_curve_by_step"]
# the pilot's own rows: (step, process, bits/byte, was_active)
CURVE = [(26000, 0, 2.12, True), (26000, 1, 5.75, False),
         (28000, 0, 2.37, False), (28000, 1, 2.80, True),
         (84000, 0, 2.07, False), (84000, 1, 1.74, True),
         (86000, 0, 2.08, False), (86000, 1, 1.74, True)]
old_series = sorted({st: b for st, _p, b, _a in CURVE}.items())
new_series = curve_by_step(CURVE)
check(old_series[0][1] == 5.75,
      f"the old expression took {old_series[0][1]} at step 26000 -- py while it was ABSENT, because the dict "
      f"was keyed on the step alone and appends ascend by process")
check(new_series[0][1] == 2.12,
      f"the new one takes {new_series[0][1]} -- the process that was ACTIVE there")
check(min(v for _, v in new_series) < min(v for _, v in old_series) or
      max(v for _, v in new_series) < max(v for _, v in old_series),
      f"...so an ABSENT window can no longer enter rise_since_min: the old series spanned "
      f"{max(v for _, v in old_series) - min(v for _, v in old_series):.2f} b/B against a "
      f"CURVE_RISE_BLEWUP threshold of 0.5, on nothing but the phase schedule")
# and with two ACTIVE processes at one step it must MEAN over them, not pick one
both = [(1000, 0, 2.0, True), (1000, 1, 3.0, True)]
check(curve_by_step(both) == [(1000, 2.5)],
      "two active processes at one step average, rather than one silently winning")
# a curve with no active flags at all still yields a series rather than nothing
none_active = [(1000, 0, 2.0, False), (2000, 0, 3.0, False)]
check(len(curve_by_step(none_active)) == 2,
      "a curve with nothing marked active falls back to all rows instead of returning empty")

print()
if FAILED:
    print(f"resume_test: {len(FAILED)} CHECK(S) FAILED")
    for f in FAILED:
        print(f"  - {f}")
    sys.exit(1)
print("resume_test: all checks passed")
