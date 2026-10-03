"""The CPU operation check of register §8 6.3b's real-text fleet: known answers, operation only (nothing here reads
efficacy). On a scratch copy of the checkout at the commit the block names, whose root is C:

    EXP=heldout HELDOUT_SOURCE=real DEVICE=cpu WINDOWS=300 EPOCH_BYTES=64800 SEEDS='0 1' PAR=4 PIN_RETOK=40 \\
        PROBE_EVERY=30 EXTRA='TOK_GROW_EVERY=20 OPT_LR_WARMUP=20' FETCH=0 bash "$C/tools/gpu_launch.sh" --go
    bash direct.sh "$C" D                    # a final continued with the probe on; the pair without SIG's warm-up
    python3 checks.py "$C/gpu_heldout_real_out" D                 # checks.out

At this toy shape (300 windows of real text at 216 bytes) bursts (TOK_GROW_EVERY 20) and acts (40) fire, and the warmup
is the lever's 20 steps on both draws, as the fleet's is its 1,000 (at 300 windows OPT would clamp it to a tenth of
each epoch, which the two draws' lengths move). The acts, each run's windows, the two draws' epochs and the step their
rates part at come from ../realreplay.py and ../realplan.py, run here at the same shape. THE PAIR'S KNOWN ANSWER WAS
CORRECTED BY THIS CHECK (2026-10-03; register §8 6.3b's row): S and S_replay part at their second flush, since SIG's
pre-loop warm-up draws from the whole epoch-0 stream, and only without it (direct.sh's SIG_WARMUP=0 pair) does nothing
part them before OPT's rates. Run it from any directory but a checkout's root."""
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
S_, R_ = "k40", "k40_replay"
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


# THE MODEL-FREE REPLAYS at this fleet's toy shape: minting and the act on the real stream, each draw; and the two draws'
# epochs and the optimizer step at which OPT's rate first parts, through OPT's own entry points.
ENV = dict(os.environ, OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", PYTHONDONTWRITEBYTECODE="1")
replay, part = {}, {}
with tempfile.TemporaryDirectory() as td:
    for s_ in (0, 1):
        for d_ in ("planned", "replay"):
            p_ = os.path.join(td, f"s{s_}_{d_}.json")
            r_ = subprocess.run([sys.executable, os.path.join(HERE, "..", "realreplay.py"), str(s_), "40", "0", d_, "64800",
                                 "20", p_], capture_output=True, text=True, timeout=600, env=ENV)
            print("  replay: " + (r_.stdout.splitlines() or [r_.stderr[-300:]])[0])
            replay[(s_, d_)] = js(p_) or {}
        r_ = subprocess.run([sys.executable, os.path.join(HERE, "..", "realplan.py"), str(s_), "64800"], capture_output=True,
                            text=True, timeout=600, env=dict(ENV, OPT_LR_WARMUP="20"))
        m_ = re.search(r"first part at byte ([\d,]+) .*?OPT's rate first differs at optimizer step (\d+)", r_.stdout)
        ep = re.findall(r"DATA_DRAW=(\w+): epoch windows ([\d,]+); phase 1 = bytes \[0, ([\d,]+)\), sha256 (\w+)", r_.stdout)
        print("  plan: seed %d: %s; bytes part at %s, the rate at step %s" % (
            s_, ", ".join(f"{d} {w} windows (phase 1 sha256 {h})" for d, w, _, h in ep),
            m_.group(1) if m_ else "?", m_.group(2) if m_ else "?"))
        p1 = {int(e1.replace(",", "")) for _, _, e1, _ in ep}
        part[s_] = (int(m_.group(2)) if m_ else None, int(m_.group(1).replace(",", "")) if m_ else None,
                    p1.pop() if len(p1) == 1 else None, len({h for *_, h in ep}) == 1 and len(ep) == 2)

done = dict(re.findall(r"^(\S+) rc=(-?\d+)", rd(os.path.join(OUT, "logs", "_done.txt")), re.M))
sdone = dict(re.findall(r"^(\S+) rc=(-?\d+)", rd(os.path.join(OUT, "smoke", "_done.txt")), re.M))
say("every fleet and smoke run ended rc=0", len(done) == 7 and set(done.values()) == {"0"}
    and len(sdone) == 3 and set(sdone.values()) == {"0"}, f"{done} {sdone}")
tags = sorted(done)
logs = {t: rd(os.path.join(OUT, "logs", t + ".log")) for t in tags}
curves = {t: js(os.path.join(OUT, "curves", t + ".json")) for t in tags}
series = {t: js(os.path.join(OUT, "curves", t + ".probe.json")) for t in tags}
trust = {t: js(os.path.join(OUT, "curves", t + ".trust.json")) for t in tags}
say("finite: no run stopped or was refused, every loss and every probe value finite",
    not any("RUN STOPPED" in l or "REFUSED" in l for l in logs.values())
    and all(c and all(math.isfinite(x) for x in c) for c in curves.values())
    and all(s and all(math.isfinite(v) for r in s for a in r["areas"].values() for v in (a["control"], a["report"])
                      if v is not None) for s in series.values()))
say("every run read real text: DATA_SOURCE=real among the pins SUMMARY records, its source line, and S_replay alone at "
    "'replay' 0.27 (its data.replay gate fired)",
    "=== pins: DATA_SOURCE=real pinned" in rd(os.path.join(OUT, "SUMMARY.txt"))
    and "=== source: real text (HELDOUT_SOURCE=real" in rd(os.path.join(OUT, "SUMMARY.txt"))
    and all(bool(re.search(r"^\s+gate:data\.replay\s+\('fired'", logs[t], re.M)) == t.startswith(R_) for t in tags))

# THE SERIES: a 'phase' reading at each phase's start and 'cadence' readings between, memory-off, over the areas arrived
# so far, and R's two boundary readings over all four areas, 128 report windows an area (each closure's row reads
# 4 x 256 windows: both halves).
bad = []
for t, s in series.items():
    inrun = [r for r in s if r["kind"] in ("phase", "cadence")]
    ph = [r for r in s if r["kind"] == "phase"]
    bd = [r for r in s if r["kind"] == "boundary"]
    sizes = [len(r["areas"]) for r in inrun]
    if not (len(ph) == 4 and any(r["kind"] == "cadence" for r in s) and all(r["closure"] == "memory-off" for r in inrun)
            and sizes == sorted(sizes) and sizes[-1] == 4
            and [r["closure"] for r in bd] == ["memory-off", "memory-on"]
            and all(sorted(r["areas"]) == sorted(AR) and r["windows"] == 1024 for r in bd)):
        bad.append((t, [(r["kind"], r["closure"], r["step"], len(r["areas"]), r["windows"]) for r in s]))
say("every series holds phase readings at the four phases' starts and cadence readings, memory-off, over the areas "
    "arrived so far, and R's boundary readings through both closures over all four areas at 1,024 windows (128 report "
    "windows an area)", not bad, str(bad[:1]))
print("    readings per run (phase, cadence):", {t: (sum(r["kind"] == "phase" for r in s),
                                                  sum(r["kind"] == "cadence" for r in s)) for t, s in series.items()})


def first_diff(a, b):
    n = min(len(a), len(b))
    return next((i for i in range(n) if a[i] != b[i]), n)


for s_ in (0, 1):
    t_s, t_r = f"{S_}.s{s_}", f"{R_}.s{s_}"
    acts = {t: [int(x) for x in re.findall(r"mid-epoch act at window (\d+):", logs[t])] for t in (t_s, t_r)}
    w = {t: int(re.search(r"=== (\d+) windows", logs[t]).group(1)) for t in (t_s, t_r)}
    say(f"seed {s_}: the acts and the windows are the replay's: {S_} acts {acts[t_s]} in {w[t_s]} windows, {R_} "
        f"{acts[t_r]} in {w[t_r]}",
        acts[t_s] == replay[(s_, "planned")].get("acts") and acts[t_r] == replay[(s_, "replay")].get("acts")
        and w[t_s] == replay[(s_, "planned")].get("windows") and w[t_r] == replay[(s_, "replay")].get("windows"))
    # O14'S PAIR: S is k0 until its first act -- one draw, so one warm-up, and the same mints -- and parts after it.
    dk = first_diff(curves[f"k0.s{s_}"], curves[t_s])
    say(f"seed {s_}: {S_} equals k0 bit for bit through its first act (window {acts[t_s][0] if acts[t_s] else '?'}): "
        f"their first differing flush is {dk + 1}", bool(acts[t_s]) and dk >= acts[t_s][0], f"first diff {dk + 1}")
    # THE PAIR (corrected 2026-10-03 by this check): one initialisation and one phase-1 stream, but SIG's pre-loop
    # warm-up draws its pairs from the whole epoch-0 stream (spine/compose.py::_signature_units), which 'replay' changes
    # after phase 1, so the two start the loop with different encoders: equal at the first flush, apart from the second.
    d_ = first_diff(curves[t_s], curves[t_r])
    sep = {t: (re.search(r"^\s+sig\.warmup_separation_final\s+(\S+)", logs[t], re.M) or [None, None])[1] for t in (t_s, t_r)}
    wst = {t: (re.search(r"^\s+sig\.warmup_steps\s+(\d+)", logs[t], re.M) or [None, None])[1] for t in (t_s, t_r)}
    say(f"seed {s_}: {S_} and {R_} are bit-identical at their first flush and part at the second: SIG's warm-up, "
        f"{wst[t_s]} steps on each, ends at separation {sep[t_s]} on {S_} and {sep[t_r]} on {R_}, the epoch-0 streams it "
        f"draws from being the two draws'",
        d_ == 1 and sep[t_s] is not None and sep[t_r] is not None and sep[t_s] != sep[t_r]
        and wst[t_s] == wst[t_r] and wst[t_s] not in (None, "0"), f"first diff {d_ + 1}")
    if DIRECT:
        # ... AND WITHOUT THE WARM-UP (direct.sh, SIG_WARMUP=0) NOTHING PARTS THE PAIR BEFORE OPT'S RATES DO.
        step, byte, end1, same1 = part[s_]
        na, nb = js(os.path.join(DIRECT, f"nowarm.s{s_}.json")) or [], js(os.path.join(DIRECT, f"nowarm_replay.s{s_}.json")) or []
        dn = first_diff(na, nb)
        b1 = sum((js(os.path.join(DIRECT, f"nowarm.s{s_}.bytes.json")) or [])[:dn])
        say(f"seed {s_}: without SIG's warm-up (SIG_WARMUP=0, direct.sh) nothing parts the pair before OPT's rates do: "
            f"bit-identical through flush {step}, the last whose parameters no rate apart has touched (window w's "
            f"update takes step w's rate, and the model-free plan's two draws first price step {step} apart), and apart "
            f"from flush {dn + 1}, {b1:,} bytes into the stream: inside phase 1 "
            f"({end1 if end1 is None else format(end1, ',')} bytes, one stream under both draws, their sha256 equal), "
            f"before byte {byte:,}, where the two streams first part",
            len(na) == len(nb) == 30 and same1 and step is not None and end1 is not None and step <= dn < len(na)
            and b1 < end1 <= byte, f"first diff {dn + 1}")

# THE SHARE GAUGES EQUAL THE PLAN: every phase's realised share is its planned one, under both draws; 'replay' names the
# faded areas (eng from phase 2, py in phase 4) and 'planned' only the live ones.
gauges = {t: {(m.group(1), m.group(2), m.group(3)): int(m.group(4)) for m in re.finditer(
    r"^\s+data\.share\.p(\d)\.(\w+)\.(planned|realised)\s+(\d+)\s*$", logs[t], re.M)} for t in tags}
eq = all(g and all(g[(p, a, "planned")] == g.get((p, a, "realised")) for (p, a, k) in g if k == "planned")
         for g in gauges.values())
named = {t: sorted({(int(p), a) for (p, a, k), v in g.items() if k == "planned" and v > 0}) for t, g in gauges.items()}
live = [(0, "eng"), (0, "py"), (1, "num"), (1, "py"), (2, "num"), (2, "py"), (3, "c"), (3, "num")]
faded = sorted(live + [(1, "eng"), (2, "eng"), (3, "eng"), (3, "py")])
say("the share gauges equal the plan in every run, phase by phase; 'replay' gives the faded areas their shares "
    "(eng from phase 2, py in phase 4) and 'planned' only the live areas",
    eq and all(named[t] == (faded if t.startswith(R_) else live) for t in tags),
    str({t: v for t, v in named.items() if v != (faded if t.startswith(R_) else live)}))
print("    S_replay.s0's gauges (permille, planned = realised):",
      " | ".join(f"p{p} " + " ".join(f"{a} {v}" for (pp, a, k), v in sorted(gauges[f"{R_}.s0"].items())
                                       if pp == p and k == "planned") for p in "0123"))

# THE SKEW GATE FLAGS AND DOES NOT REFUSE: data.exposure_skew fires on every run, and every run trained.
sk = {t: re.search(r"^\s+Gate data\.exposure_skew: (FIRED|armed, did not fire) \(([\d.]+) vs ([\d.]+)\)", logs[t], re.M)
      for t in tags}
say("data.exposure_skew fires on every run (" + ", ".join(sorted({f'{m.group(2)} vs {m.group(3)}' for m in sk.values()
                                                                   if m})) + ") as a flag: every run trained to its end",
    all(m and m.group(1) == "FIRED" for m in sk.values()) and len(done) == 7 and set(done.values()) == {"0"})

# CLAIMS FIRE AND THE BOOK'S SECONDS PRINT: data.trust.claims above 0, data.trust.wall_s printed, a series of passes.
cl = {t: (int((re.search(r"^\s+data\.trust\.claims\s+(\d+)", logs[t], re.M) or [0, 0])[1]),
          (re.search(r"^\s+data\.trust\.wall_s\s+([\d.]+)", logs[t], re.M) or [0, None])[1],
          len(trust[t] or []), sum(int(p.get("units") or 0) for p in trust[t] or [])) for t in tags}
say("the book reads real text: data.trust.claims above 0 and data.trust.wall_s printed on every run, and each run's "
    "series of passes covers the units it read: " + ", ".join(f"{t} {c[0]} claims, {c[1]} s, {c[2]} passes"
                                                               for t, c in sorted(cl.items())[:3]) + ", ...",
    all(c[0] > 0 and c[1] is not None and float(c[1]) > 0 and c[2] > 0 and c[3] > 0 for c in cl.values()))

b0 = [r for r in series["k0.s0"] if r["kind"] == "boundary"]
br = [r for r in series["k0_rerun.s0"] if r["kind"] == "boundary"]
say("k0_rerun is exact: its losses and its R readings are k0.s0's", curves["k0.s0"] == curves["k0_rerun.s0"] and b0 == br)

blk = rd(os.path.join(OUT, "PASTE_BACK.txt"))
say("the block reads the fleet by the real-text reader: labelled real text, with O14's, O16's and E3's lines and S's "
    "finals' pack line, within 80 lines",
    "  real text" in blk.splitlines()[1] and "DECISION (O14, real text): " in blk and "DECISION (O16, the draw): " in blk
    and "\nE3 (04-6.3): the book's seconds over the loop's" in blk and "  pack: tar -cf " in blk
    and len(blk.splitlines()) <= 80)
# THE PLAN'S GATES, BOTH DRAWS': every value run.py's startup prints for the three plan gates (its 'Gate' lines, a
# source apart from the R stage's that the block reads) is on the block's line -- 'replay' moves the exposure.
gv = {}
for t in tags:
    for g_, v_, th_ in re.findall(r"^\s+Gate data\.(exposure_skew|exposure_max|splice_window): [^(\n]*\(([\d.]+) vs "
                                  r"([\d.]+)\)", logs[t], re.M):
        gv.setdefault(g_, set()).add(f"{v_} vs {th_}")
pl = (re.search(r"^  the plan's gates \(flags, as pre-registered\): (.*)$", blk, re.M) or [None, ""])[1]
say("the block's plan-gates line names every value the runs' startup prints for the three plan gates, both draws': "
    + "; ".join(f"{g_} {' / '.join(sorted(v))}" for g_, v in sorted(gv.items())),
    len(gv) == 3 and all(f"data.{g_} " in pl and all(x in pl for x in v) for g_, v in gv.items()), pl)

if DIRECT:
    # A FINAL CONTINUES (direct.sh): k40.s0's, resumed into a second epoch with the probe on.
    ch = js(os.path.join(DIRECT, "child.probe.json")) or []
    par = [r for r in series[f"{S_}.s0"] if r["kind"] == "boundary"]
    res = [r for r in ch if r["kind"] == "resume"]
    same = [any(q["closure"] == p["closure"] and sorted(q["areas"]) == sorted(p["areas"])
                and all(q["areas"][a][h] == p["areas"][a][h] for a in p["areas"] for h in ("control", "report"))
                for q in res) for p in par]
    cw = int(re.search(r"=== (\d+) windows", logs[f"{S_}.s0"]).group(1))
    say(f"{S_}.s0's final continues into a second epoch with the probe on (RUN_EPOCHS=2 DATA_RESAMPLE=1): it trains its "
        f"60 windows, its resume readings are the parent's R readings through both closures, area for area, and it "
        f"reads on: " + ", ".join(f"{r['kind']} {r['closure']} at {r['step']}" for r in ch),
        re.search(rf"^=== {cw + 60} windows run total \(60 trained by this process, resumed at {cw}\)",
                  rd(os.path.join(DIRECT, "child.log")), re.M) is not None
        and len(par) == 2 and all(same) and any(r["kind"] == "boundary" for r in ch), str(same))
print("    ok" if ok_all else "    NOT ALL PASSED")
sys.exit(0 if ok_all else 1)
