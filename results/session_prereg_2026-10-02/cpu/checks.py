"""The CPU operation check of register §8 5.3a's fleet: known answers, operation only (nothing here reads
efficacy). On a scratch clone of the checkout at 80135f1, whose root is C, three fleets:

    (A) a parents stage, then the sessions -- its block is PASTE_BACK.txt:
    EXP=session DEVICE=cpu WINDOWS=300 SEEDS='0 1' PAR=4 FILL=0 PIN_RETOK=40 PROBE_EVERY=50 SESSION_WINDOWS=300 \\
        EXTRA='TOK_GROW_EVERY=20 FAB_SLOTS=2200' FETCH=0 bash "$C/tools/gpu_launch.sh" --go
    (B) the same sessions from A's parents, named as PARENTS -- PASTE_BACK_parents.txt:
        ... KEEP_CKPT=0 PARENTS="$C/gpu_session_out/parents" OUT=gpu_session_p_out ...
    (C) from a CPU EXP=heldout fleet's OUT, the path test 5 takes from test 4 -- PASTE_BACK_heldout.txt. That
        fleet ran at cce2d39: EXP=heldout DEVICE=cpu WINDOWS=150 SEEDS=0 PAR=4 FILL=0 PIN_RETOK=40 PROBE_EVERY=50
        EXTRA='TOK_GROW_EVERY=20'. Its sessions: the same shape, SESSION_WINDOWS=40 KEEP_CKPT=0 PARENTS=<its OUT>
        OUT=gpu_session_h_out.
    python3 checks.py "$C/gpu_session_out" "$C/gpu_session_p_out" "$C/gpu_session_h_out" <C's heldout OUT>

At this toy shape the parents fill the 2,200 slots EXTRA gives them, so W widens to 4,248 (n_live 2,200 +
W_HEADROOM 2,048), and their acts re-measure the epoch, so a session prices as a logged parent at the floor.
Run it from any directory but a checkout's root."""
import json
import math
import os
import re
import subprocess
import sys

A, B, C, H = sys.argv[1:5]
AR = ("eng", "py", "num", "c")
SESS = ("P", "P_parent", "P_twin", "W")
ok_all = True


def say(name, ok, detail=""):
    global ok_all
    ok_all = ok_all and ok
    print(("PASS " if ok else "FAIL ") + name + (f" -- {detail}" if detail else ""))


def rd(p):
    try:
        return open(p, errors="replace").read()
    except OSError:
        return ""


def js(p):
    try:
        return json.load(open(p))
    except (OSError, ValueError):
        return None


def books(out):
    """{book: {tag: rc}} for every step's _done.txt under one fleet."""
    got = {}
    for sub in ("parents", "smoke", os.path.join("smoke", "sessions"), "logs"):
        t = rd(os.path.join(out, sub, "_done.txt"))
        if t:
            got[sub] = dict(re.findall(r"^(\S+) rc=(-?\d+)", t, re.M))
    return got


def sessions(out):
    return sorted(os.path.basename(p)[:-4] for p in os.listdir(os.path.join(out, "logs"))
                  if p.endswith(".log") and p.split(".s")[0] in SESS)


def rows(out, tag, sub="curves"):
    return [x for x in js(os.path.join(out, sub, tag + ".probe.json")) or [] if isinstance(x, dict)]


def last(rs, kind, closure):
    m = [x for x in rs if x.get("kind") == kind and x.get("closure") == closure]
    return m[-1] if m else None


def rep(out, tag, key):
    m = re.search(rf"^\s+{re.escape(key)}\s+(\S.*?)\s*$", rd(os.path.join(out, "logs", tag + ".log")), re.M)
    return m.group(1) if m else None


# ---- (1) every run ended rc=0, and every loss and probe value is finite
for name, out in (("A", A), ("B", B), ("C", C)):
    bk = books(out)
    bad = {s: {t: rc for t, rc in d.items() if rc != "0"} for s, d in bk.items()}
    n = sum(len(d) for d in bk.values())
    nonfin = []
    for t in sessions(out):
        cu = js(os.path.join(out, "curves", t + ".json")) or []
        vals = list(cu) + [v for r_ in rows(out, t) for a_ in (r_.get("areas") or {}).values()
                           for v in (a_.get("control"), a_.get("report")) if v is not None]
        if not cu or not all(math.isfinite(float(v)) for v in vals):
            nonfin.append(t)
    say(f"{name}: every run ended rc=0 ({n}: {', '.join(f'{s} {len(d)}' for s, d in bk.items())}), every loss and "
        f"probe value finite", not any(bad.values()) and n > 0 and not nonfin, f"{bad} {nonfin}")

# ---- (2) the anchor: each session's start reads its parent's R, area for area and item for item
for name, out, pdir in (("A", A, os.path.join(A, "parents")), ("B", B, os.path.join(A, "parents")),
                        ("C", C, os.path.join(H, "curves"))):
    res = []
    for t in sessions(out):
        seed = t.rsplit(".s", 1)[1]
        prs = [x for x in js(os.path.join(pdir, f"k40.s{seed}.probe.json")) or [] if isinstance(x, dict)]
        rs = rows(out, t)
        for cl in ("memory-off", "memory-on"):
            s_, p_ = last(rs, "resume", cl), last(prs, "boundary", cl)
            same = (s_ is not None and p_ is not None and s_["step"] == p_["step"]
                    and set(s_["areas"]) == set(AR) == set(p_["areas"])
                    and all(s_["areas"][a]["report"] == p_["areas"][a]["report"]
                            and s_["areas"][a]["control"] == p_["areas"][a]["control"] for a in AR))
            pz = all(v[0] > 0 and v[1] == 0 and v[2] in (0, None)
                     for hs in ((s_ or {}).get("paired") or {"x": {"h": [0, 1, 1]}}).values() for v in hs.values())
            res.append((t, cl, same and pz))
    say(f"{name}: each session's resume-start readings, through both closures, are its parent's R readings area for "
        f"area at the parent's step, and their pairing against them reads differences of exactly 0 on every item",
        res and all(x[2] for x in res), str([x for x in res if not x[2]][:4]))

# ---- (3) P_parent rehearses the parent from window 0 at 0.27 of every phase; no other session does
for name, out in (("A", A), ("C", C)):
    got = {}
    for t in sessions(out):
        lg = rd(os.path.join(out, "logs", t + ".log"))
        g = re.search(r"^\s+gate:data\.rehearse_parent\s+\('([\w-]+)'", lg, re.M)
        sh = [int(x) / int(y) for x, y in re.findall(r"phase \d: eng, py, num, c (\d+) of (\d+) bytes", lg)]
        got[t] = (g.group(1) if g else None, sh, "faded from window 0" in lg)
    pp = {t: v for t, v in got.items() if t.startswith("P_parent")}
    say(f"{name}: data.rehearse_parent FIRED on every P_parent session, the old areas faded from window 0 and laid at "
        f"0.27 of each phase's bytes (data.replay), and on no other session",
        pp and all(v[0] == "fired" and len(v[1]) == 4 and all(abs(x - 0.27) < 0.001 for x in v[1]) and v[2]
                   for v in pp.values())
        and all(v[0] == "unreachable" and not v[1] for t, v in got.items() if t not in pp),
        str({t: (v[0], [round(x, 4) for x in v[1]]) for t, v in got.items()}))

# ---- (4) the measurement protocol's rate (CONTRACT-Q-DATA-7): each session prices as its parent's case -- a parent
# whose acts re-measured its epoch (opt.horizon.revise fired) carries a log and holds its child at the floor; one
# whose acts did not (C's, at 150 windows) is a no-log parent, re-priced -- and the regime is as_logged on all.
def plog(nm, seed):
    p_ = os.path.join(H, "logs", f"k40.s{seed}.log") if nm == "C" else os.path.join(A, "parents", f"k40.s{seed}.log")
    return re.search(r"opt\.horizon\.revise\s+Gate\(name='opt\.horizon\.revise', fired=True", rd(p_)) is not None


pa = [(nm, t, rep(o, t, "opt.continue.pricing"), plog(nm, t.rsplit(".s", 1)[1]))
      for nm, o in (("A", A), ("B", B), ("C", C)) for t in sessions(o)]
rg = {rep(o, t, "opt.continue.regime") for o in (A, B, C) for t in sessions(o)}
say("every session's opt.continue.pricing is its parent's case: 'logged parent: floor' under A's and B's parents, "
    "whose acts re-measured their epochs, and 'no-log parent: re-priced' under C's, whose one act did not; "
    "opt.continue.regime as_logged on all",
    all(v == ("logged parent: floor" if lg else "no-log parent: re-priced") for _, _, v, lg in pa)
    and {lg for nm, _, _, lg in pa if nm in "AB"} == {True} and {lg for nm, _, _, lg in pa if nm == "C"} == {False}
    and rg == {"as_logged"}, str(sorted({(nm, v) for nm, _, v, _ in pa})) + f" {rg}")

# ---- (5) the twin (OPT_LR x 1.0001) reads P's first flush and parts from the second, its first step at the new rate
for out in (A,):
    tw = []
    for s in (0, 1):
        p_, t_ = js(os.path.join(out, "curves", f"P.s{s}.json")), js(os.path.join(out, "curves", f"P_twin.s{s}.json"))
        k = next((i for i, (x, y) in enumerate(zip(p_, t_)) if x != y), None)
        tw.append((s, k, p_[0] == t_[0]))
    say("A: P_twin's first flush equals P's and the two part at the second -- the twin's first step is its first "
        "at OPT_LR x 1.0001 (register §8 5.3a: not FAB_BIRTH_JITTER, read only at a growth birth)",
        all(k == 1 and f for _, k, f in tw), str(tw))

# ---- (6) W: the widening is accepted and the births land past the parent's slots
w = [t for t in sessions(A) if t.startswith("W.")]
wl = re.search(r"^=== W: FAB_SLOTS=(\d+) at k40\.s(\d+), .*\(n_live (\d+) \+ W_HEADROOM (\d+), against its (\d+) slots\)",
               rd(os.path.join(A, "SUMMARY.txt")), re.M)
if w and wl:
    s_ = wl.group(2)
    cap_w, nl_w, wid = (rep(A, w[0], k) for k in ("fab.cap", "fab.n_live", "fab.resume_widened"))
    cap_p, nl_p = (rep(A, f"P.s{s_}", k) for k in ("fab.cap", "fab.n_live"))
    say(f"A: W at the parent with the most experts (k40.s{s_}, n_live {wl.group(3)} of its {wl.group(5)} slots, full) "
        f"resumes at FAB_SLOTS {wl.group(1)} = {wl.group(3)} + {wl.group(4)}: the widening is accepted "
        f"(fab.resume_widened {wid}, fab.cap {cap_w}) and ends with n_live {nl_w}, past the parent's {wl.group(5)} "
        f"slots, so births landed past them; P there stays at fab.cap {cap_p}, n_live {nl_p}",
        int(wid) > 0 and cap_w == wl.group(1) and int(nl_w) > int(wl.group(5)) and int(wl.group(3)) == int(wl.group(5))
        and cap_p == wl.group(5) and int(nl_p) <= int(wl.group(5)))
else:
    say("A: W ran at the parent with the most experts", False, f"{w} {bool(wl)}")

# ---- (7) B, from PARENTS, reproduces A's sessions bit for bit, the parents' sha256 checked
same = []
for t in sessions(A):
    same.append((t, all(rd(os.path.join(A, "curves", t + s)) == rd(os.path.join(B, "curves", t + s))
                        and rd(os.path.join(A, "curves", t + s)) for s in (".json", ".bytes.json", ".probe.json"))))
sb = rd(os.path.join(B, "SUMMARY.txt"))
say("B: launched with PARENTS=A's parents (their 4 files sha256-checked against its FINALS.sha256), every session's "
    "loss curve, flush bytes and probe series equal A's byte for byte",
    sessions(A) == sessions(B) and all(x for _, x in same)
    and re.search(r"^=== parents: k40 at seeds 0 1, from \S+/gpu_session_out/parents \(4 file\(s\) sha256-checked", sb,
                  re.M) is not None, str(same))

# ---- (8) C: from the held-out fleet's finals, untouched
chk = subprocess.run(["sha256sum", "-c", "--quiet", "FINALS.sha256"], cwd=H, capture_output=True, text=True)
sc = rd(os.path.join(C, "SUMMARY.txt"))
say("C: the sessions resume the EXP=heldout fleet's k40.s0 final at cce2d39 (2 files sha256-checked against its "
    "FINALS.sha256), and that fleet's finals still match their manifest afterwards",
    chk.returncode == 0 and re.search(r"^=== parents: k40 at seeds 0, from \S+ \(2 file\(s\) sha256-checked", sc, re.M)
    is not None and sessions(C) == ["P.s0", "P_parent.s0", "P_twin.s0", "W.s0"], chk.stdout[-200:] + chk.stderr[-200:])

# ---- (9) the blocks
for name, out, anc in (("A", A, 7), ("B", B, 7), ("C", C, 4)):
    b = rd(os.path.join(out, "PASTE_BACK.txt")).splitlines()
    say(f"{name}: the block is written, within 80 lines, its anchor equal in {anc} of {anc} sessions and a DECISION",
        0 < len(b) <= 80 and b[0] == "==== PASTE THIS BACK ====" and b[-1] == "==== END ===="
        and any(f"item for item: equal in {anc} of {anc} session(s)" in l for l in b)
        and any(l.startswith("DECISION: ") for l in b), str(len(b)))
print("    ok" if ok_all else "    FAILED")
sys.exit(0 if ok_all else 1)
