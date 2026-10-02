"""The CPU operation check of register §8 6.3a's fleet: known answers, operation only (nothing here reads
efficacy). On a scratch copy of the checkout (the tree at 8672c89), whose root is C:

    EXP=heldout DEVICE=cpu WINDOWS=300 SEEDS='0 1' PAR=4 FILL=0 PIN_RETOK=40 PROBE_EVERY=50 \\
        EXTRA='TOK_GROW_EVERY=20' FETCH=0 bash "$C/tools/gpu_launch.sh" --go     # its block: PASTE_BACK.txt
    bash direct.sh "$C" D                                                       # the direct runs
    python3 checks.py "$C/gpu_heldout_out" D                                    # checks.out

At this toy shape bursts (TOK_GROW_EVERY 20) and acts (40) fire. The acts, each run's windows and the bursts
come from ../tokreplay.py, the model-free mint replay, run here at the same shape. Run it from any
directory but a checkout's root."""
import json
import math
import os
import re
import subprocess
import sys
import tempfile

OUT = sys.argv[1]
DIRECT = sys.argv[2] if len(sys.argv) > 2 else None
HERE = os.path.dirname(os.path.abspath(__file__))
AR = ("eng", "py", "num", "c")
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


# THE MODEL-FREE REPLAY at the fleet's shape: 300 windows x 189 bytes, TOK_GROW_EVERY 20, TOK_RETOK_EVERY 40.
replay = {}
with tempfile.TemporaryDirectory() as td:
    for s_ in (0, 1):
        for n_ in ("0", "1.0"):
            p_ = os.path.join(td, f"s{s_}_n{n_}.json")
            r_ = subprocess.run([sys.executable, os.path.join(HERE, "..", "tokreplay.py"), str(s_), "40", n_, "56700",
                                 "20", p_], capture_output=True, text=True, timeout=600,
                                env=dict(os.environ, OMP_NUM_THREADS="1", MKL_NUM_THREADS="1",
                                         PYTHONDONTWRITEBYTECODE="1"))
            print("  replay: " + (r_.stdout.splitlines() or [r_.stderr[-300:]])[0])
            replay[(s_, n_)] = js(p_) or {}

done = dict(re.findall(r"^(\S+) rc=(-?\d+)", rd(os.path.join(OUT, "logs", "_done.txt")), re.M))
sdone = dict(re.findall(r"^(\S+) rc=(-?\d+)", rd(os.path.join(OUT, "smoke", "_done.txt")), re.M))
say("every fleet and smoke run ended rc=0", len(done) == 7 and set(done.values()) == {"0"}
    and len(sdone) == 3 and set(sdone.values()) == {"0"}, f"{done} {sdone}")
tags = sorted(done)
logs = {t: rd(os.path.join(OUT, "logs", t + ".log")) for t in tags}
curves = {t: js(os.path.join(OUT, "curves", t + ".json")) for t in tags}
series = {t: js(os.path.join(OUT, "curves", t + ".probe.json")) for t in tags}
say("finite: no run stopped, every loss and every probe value finite",
    not any("RUN STOPPED" in l for l in logs.values())
    and all(c and all(math.isfinite(x) for x in c) for c in curves.values())
    and all(s and all(math.isfinite(v) for r in s for a in r["areas"].values() for v in (a["control"], a["report"])
                      if v is not None) for s in series.values()))

# THE SERIES' SHAPE: a 'phase' reading at each of the four phases' first windows, 'cadence' readings between,
# memory-off, each over the areas arrived by then (never fewer than before), and R's two boundary readings,
# memory-off and memory-on, over all four areas, at the run's last window.
bad = []
for t, s in series.items():
    inrun = [r for r in s if r["kind"] in ("phase", "cadence")]
    ph = [r for r in s if r["kind"] == "phase"]
    bd = [r for r in s if r["kind"] == "boundary"]
    sizes = [len(r["areas"]) for r in inrun]
    if not (len(ph) == 4 and any(r["kind"] == "cadence" for r in s) and all(r["closure"] == "memory-off" for r in inrun)
            and sizes == sorted(sizes) and sizes[-1] == 4
            and [r["closure"] for r in bd] == ["memory-off", "memory-on"]
            and all(sorted(r["areas"]) == sorted(AR) for r in bd)
            and all(r["step"] == int(re.search(r"=== (\d+) windows", logs[t]).group(1)) for r in bd)):
        bad.append((t, [(r["kind"], r["closure"], r["step"], len(r["areas"])) for r in s]))
say("every series holds phase readings at the four phases' starts and cadence readings, memory-off, over the "
    "areas arrived so far, and R's boundary readings through both closures over all four areas", not bad, str(bad[:1]))
print("    readings per run (phase, cadence):", {t: (sum(r["kind"] == "phase" for r in s),
                                                  sum(r["kind"] == "cadence" for r in s)) for t, s in series.items()})


def first_diff(a, b):
    n = min(len(a), len(b))
    return next((i for i in range(n) if a[i] != b[i]), n)


for s_ in (0, 1):
    k0, kc, mn = curves[f"k0.s{s_}"], curves[f"k40.s{s_}"], curves[f"k40_mn.s{s_}"]
    acts = [int(x) for x in re.findall(r"mid-epoch act at window (\d+):", logs[f"k40.s{s_}"])]
    acts_mn = [int(x) for x in re.findall(r"mid-epoch act at window (\d+):", logs[f"k40_mn.s{s_}"])]
    toy, toy_mn = replay[(s_, "0")], replay[(s_, "1.0")]
    w = {t: int(re.search(r"=== (\d+) windows", logs[t]).group(1)) for t in (f"k0.s{s_}", f"k40.s{s_}", f"k40_mn.s{s_}")}
    d0 = first_diff(k0, kc)
    say(f"seed {s_}: k40 equals k0 bit for bit through its first act (window {acts[0] if acts else '?'}): the first "
        f"differing flush is {d0 + 1}", bool(acts) and acts[0] <= d0 < len(k0), f"acts {acts}")
    say(f"seed {s_}: the acts and the window counts are the replay's: k40 acts {acts}, k40_mn {acts_mn}; windows k40 "
        f"{w[f'k40.s{s_}']} k40_mn {w[f'k40_mn.s{s_}']} against the replay's {toy.get('windows')} and "
        f"{toy_mn.get('windows')}",
        acts == [a for a, _ in toy.get("acts", [])] and acts_mn == [a for a, _ in toy_mn.get("acts", [])]
        and w[f"k40.s{s_}"] == toy.get("windows") and w[f"k40_mn.s{s_}"] == toy_mn.get("windows"))
    first_b = next((k for k, (x, y) in enumerate(zip(toy.get("bursts", []), toy_mn.get("bursts", []))) if x != y), None)
    bw = toy["bursts"][first_b][0] if first_b is not None else None
    dm = first_diff(kc, mn)
    rr = re.search(r"^\s+tok\.mint_novel_reranked\s+(\d+)", logs[f"k40_mn.s{s_}"], re.M)
    say(f"seed {s_}: k40_mn equals k40 through the first burst the re-rank reorders -- the replay's burst {(first_b or 0) + 1} "
        f"at window {bw}, after {first_b} it left alone -- the first differing flush being {dm + 1}; "
        f"tok.mint_novel_reranked {rr.group(1) if rr else 'absent'}",
        first_b is not None and first_b >= 1 and bw <= dm < len(kc) and rr is not None and int(rr.group(1)) > 0)

b0 = [r for r in series["k0.s0"] if r["kind"] == "boundary"]
br = [r for r in series["k0_rerun.s0"] if r["kind"] == "boundary"]
say("k0_rerun is exact: its losses and its R readings are k0.s0's", curves["k0.s0"] == curves["k0_rerun.s0"] and b0 == br)

if DIRECT:
    # THE DIRECT RUNS (direct.sh): the probe's size moves no training number, and a final continues with the probe on.
    raised, default = js(os.path.join(DIRECT, "raised.json")), js(os.path.join(DIRECT, "default.json"))
    rb, db = js(os.path.join(DIRECT, "raised.bytes.json")), js(os.path.join(DIRECT, "default.bytes.json"))
    say("k0.s0 at the fleet's probe sizes and at the defaults: the same losses and flush bytes as each other and as "
        "the fleet's k0.s0, which saved its final and best checkpoints",
        raised is not None and raised == default == curves["k0.s0"]
        and rb is not None and rb == db == js(os.path.join(OUT, "curves", "k0.s0.bytes.json")), f"{len(raised or [])} flushes")
    ch = js(os.path.join(DIRECT, "child.probe.json")) or []
    par = [r for r in series["k40.s0"] if r["kind"] == "boundary"]
    res = [r for r in ch if r["kind"] == "resume"]
    same = [any(q["closure"] == p["closure"] and sorted(q["areas"]) == sorted(p["areas"])
                and all(q["areas"][a][h] == p["areas"][a][h] for a in p["areas"] for h in ("control", "report"))
                for q in res) for p in par]
    say("k40.s0's final continues into a second epoch with the probe on (RUN_EPOCHS=2 DATA_RESAMPLE=1): it trains its 60 windows, its "
        "resume readings are the parent's R readings through both closures, area for area (each area now "
        "seen_by_parent), and it reads on: "
        + ", ".join(f"{r['kind']} {r['closure']} at {r['step']}" for r in ch),
        re.search(r"^=== 352 windows run total \(60 trained by this process, resumed at 292\)",
                  rd(os.path.join(DIRECT, "child.log")), re.M) is not None
        and len(par) == 2 and all(same) and all(v["seen_by_parent"] for q in res for v in q["areas"].values())
        and any(r["kind"] == "boundary" for r in ch), str(same))
print("    ok" if ok_all else "    NOT ALL PASSED")
sys.exit(0 if ok_all else 1)
