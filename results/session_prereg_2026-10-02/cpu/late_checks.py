"""The CPU operation check of the review's fixes to register §8 5.3a's fleet (2026-10-02; operation only, nothing
here reads efficacy). On a scratch clone at cc17cc3, whose root is C, two fleets at a shape whose parents mint after
their last cut (PIN_RETOK=100 and TOK_GROW_EVERY=20: each parent's last act is at window 201 of 289-295):

    (D) a parents stage, then the sessions -- its block is PASTE_BACK_late.txt:
    EXP=session DEVICE=cpu WINDOWS=300 SEEDS='0 1' PAR=4 FILL=0 PIN_RETOK=100 PROBE_EVERY=50 SESSION_WINDOWS=300 \\
        EXTRA='TOK_GROW_EVERY=20 FAB_SLOTS=2200' HB_EVERY=0 bash "$C/gpu_world.sh"
    (D2) the same sessions from D's parents, named as PARENTS: ... PARENTS="$C/gpu_session_out/parents" \\
        OUT=gpu_session_p_out bash "$C/gpu_world.sh"
    python3 late_checks.py "$C/gpu_session_out" "$C/gpu_session_p_out"

Run it from any directory but a checkout's root."""
import json
import math
import os
import re
import sys

D, D2 = sys.argv[1:3]
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


def sessions(out):
    return sorted(os.path.basename(p)[:-4] for p in os.listdir(os.path.join(out, "logs"))
                  if p.endswith(".log") and p.split(".s")[0] in SESS)


def rows(out, tag, sub="curves"):
    return [x for x in js(os.path.join(out, sub, tag + ".probe.json")) or [] if isinstance(x, dict)]


def last(rs, kind, closure="memory-off"):
    m = [x for x in rs if x.get("kind") == kind and x.get("closure") == closure]
    return m[-1] if m else None


def late_line(out):
    m = re.search(r"^=== parents' ids minted after their last cut[^:]*: (.*)$", rd(os.path.join(out, "SUMMARY.txt")),
                  re.M)
    return {int(a): int(b) for a, b in re.findall(r"s(\d+) (-?\d+)", m.group(1))} if m else None


# ---- (1) every run ended rc=0, and every loss and probe value is finite
for name, out in (("D", D), ("D2", D2)):
    bad, n, nonfin = [], 0, []
    for sub in ("parents", "smoke", os.path.join("smoke", "sessions"), "logs"):
        for tag, rc in re.findall(r"^(\S+) rc=(-?\d+)", rd(os.path.join(out, sub, "_done.txt")), re.M):
            n += 1
            if rc != "0":
                bad.append(f"{sub}/{tag}")
    for t in sessions(out):
        cu = js(os.path.join(out, "curves", t + ".json")) or []
        vals = list(cu) + [v for r_ in rows(out, t) for a_ in (r_.get("areas") or {}).values()
                           for v in (a_.get("control"), a_.get("report")) if v is not None]
        if not cu or not all(math.isfinite(float(v)) for v in vals):
            nonfin.append(t)
    say(f"{name}: every run ended rc=0 ({n}), every loss and probe value finite", n > 0 and not bad and not nonfin,
        f"{bad} {nonfin}")

# ---- (2) each parent's ids minted after its last cut: SUMMARY's line, off its final, is what its run said at its end
late = late_line(D)
said = {}
for s in (0, 1):
    m = re.search(r"WARNING: loop: (\d+) token\(s\) were minted AFTER THE LAST RE-SEGMENTATION",
                  rd(os.path.join(D, "parents", f"k100.s{s}.log")))
    said[s] = int(m.group(1)) if m else 0
say(f"D: SUMMARY's ids minted after each parent's last cut, read off its final ({late}), are the ones its run counted "
    f"at its end ({said}), and D2 reads the same off the same finals",
    late == said and late_line(D2) == said and any(v > 0 for v in said.values()), f"{late} {said} {late_line(D2)}")

# ---- (3) each session reads its start twice where its parent minted after its last cut, once where it did not
res = []
for name, out in (("D", D), ("D2", D2)):
    for t in sessions(out):
        s = int(t.rsplit(".s", 1)[1])
        rs = rows(out, t)
        pr = [x for x in js(os.path.join(D, "parents", f"k100.s{s}.probe.json")) or [] if isinstance(x, dict)]
        kinds = [(x["kind"], x["closure"]) for x in rs[:4]]
        want = [("resume", "memory-off"), ("resume", "memory-on")] + (
            [("resume_own", "memory-off"), ("resume_own", "memory-on")] if late.get(s) else [])
        n_own = sum(1 for x in rs if x["kind"] == "resume_own")
        anchor = all(all(last(rs, "resume", cl)["areas"][a][h] == last(pr, "boundary", cl)["areas"][a][h]
                             for a in AR for h in ("control", "report"))
                     and last(rs, "resume", cl)["step"] == last(pr, "boundary", cl)["step"]
                     and all(v[1] == 0 for hs in last(rs, "resume", cl)["paired"].values() for v in hs.values())
                     for cl in ("memory-off", "memory-on"))
        own, st, R = last(rs, "resume_own"), last(rs, "resume"), last(rs, "boundary")
        start = own or st
        pair_ok = all(abs(R["paired"][a]["report"][1] - (R["areas"][a]["report"] - start["areas"][a]["report"])) < 1e-9
                      for a in AR) and (own is None or all(
                          abs(own["paired"][a]["report"][1] - (own["areas"][a]["report"] - st["areas"][a]["report"]))
                          < 1e-9 for a in AR))
        res.append((name, t, kinds[:len(want)] == want and n_own == (2 if late.get(s) else 0)
                    and all(x["step"] == st["step"] for x in rs[:len(want)]), anchor, pair_ok))
say("D and D2: every session whose parent minted after its last cut reads its start at the parent's last cut and "
    "again at its own first cut ('resume', then 'resume_own', both closures, at the parent's step), and none other "
    "does; the 'resume' rows are the parent's R rows, item for item; each pairing is against the reading before it, "
    "R's against the session's own start",
    res and all(a and b and c for _, _, a, b, c in res), str([x for x in res if not all(x[2:])][:4]))

# ---- (4) the block: F subtracts the session's own start, and the parents' ids are reported with what they moved
an = rd(os.path.join(D, "ANALYSIS.txt"))
fok, offs = [], {a: [] for a in AR}
for t in sessions(D):
    rs = rows(D, t)
    own, st, R = last(rs, "resume_own"), last(rs, "resume"), last(rs, "boundary")
    start = own or st
    name, s = t.rsplit(".s", 1)
    m = re.search(rf"^  {re.escape(name)} +s{s} +\d+ win  (.*)$", an, re.M)
    got = dict(re.findall(r"(\w+) ([+-]\d+\.\d{5})", m.group(1))) if m else {}
    fok.append(all(got.get(a) == f"{R['areas'][a]['report'] - start['areas'][a]['report']:+.5f}" for a in AR))
    if own:
        for a in AR:
            offs[a].append(own["areas"][a]["report"] - st["areas"][a]["report"])
blk = rd(os.path.join(D, "PASTE_BACK.txt"))
ln = next((l for l in blk.splitlines() if l.startswith("  the parents' ids minted after their last cut")), "")
n_own = len(offs["eng"])
want = " ".join(f"{a} {sum(offs[a]) / n_own:+.4f} [{min(offs[a]):+.4f},{max(offs[a]):+.4f}]" for a in AR) if n_own else ""
say(f"D: the block's F per old area is R minus each session's start at its own first cut, at all {len(fok)} sessions, "
    f"and it reports the parents' ids minted after their last cut beside what they moved at the {n_own} sessions "
    f"whose first cut held them",
    fok and all(fok) and n_own > 0 and want in ln
    and ln.startswith("  the parents' ids minted after their last cut (" + " | ".join(f"s{s} {late[s]}" for s in sorted(late))),
    ln)

# ---- (5) the disk: W's files at W's own size -- scaled from the parents' smoke before W ran, measured from PARENTS
sd, sd2 = rd(os.path.join(D, "SUMMARY.txt")), rd(os.path.join(D2, "SUMMARY.txt"))
m1 = re.search(r"^  smoke checkpoints: the largest but W's was (\d+) MB, W's priced at (\d+) MB, the parent's x "
               r"\((\d+) \+ (\d+)\) / (\d+) slots; deleted$", sd, re.M)
m2 = re.search(r"^  smoke checkpoints: the largest but W's was (\d+) MB, W's (\d+) MB; deleted$", sd2, re.M)
k2 = re.search(r"^=== disk: checkpoints may take about ([\d.]+) GB \((\d+) MB x 2 per file, W's (\d+) MB x 2\)", sd2, re.M)
fpr = re.search(r"up to (\d+) checkpoint files per run", sd2)
say("D: before W has run, W's files are priced at the parents' smoke final x (2200 + 2048) / 2200; D2, from PARENTS, at "
    "the smoke's W, larger than every other session's, and its disk line prices 6 sessions' files at theirs and W's at "
    "W's",
    m1 is not None and (m1.group(3), m1.group(4), m1.group(5)) == ("2200", "2048", "2200")
    and abs(int(m1.group(2)) - int(m1.group(1)) * 4248 / 2200) <= 1
    and m2 is not None and int(m2.group(2)) > int(m2.group(1)) and k2 is not None and fpr is not None
    and (k2.group(2), k2.group(3)) == m2.groups()
    and abs(float(k2.group(1)) - (6 * int(m2.group(1)) + int(m2.group(2))) * int(fpr.group(1)) * 2 / 1000) <= 0.1,
    f"{m1.group(0) if m1 else None} | {m2.group(0) if m2 else None} | {k2.group(0) if k2 else None}")

# ---- (6) D2, from PARENTS, reproduces D's sessions byte for byte
same = [(t, all(rd(os.path.join(D, "curves", t + s)) == rd(os.path.join(D2, "curves", t + s))
                and rd(os.path.join(D, "curves", t + s)) for s in (".json", ".bytes.json", ".probe.json")))
        for t in sessions(D)]
say("D2: launched with PARENTS=D's parents, every session's loss curve, flush bytes and probe series equal D's byte for "
    "byte", sessions(D) == sessions(D2) and all(x for _, x in same), str(same))
print("    ok" if ok_all else "    FAILED")
sys.exit(0 if ok_all else 1)
