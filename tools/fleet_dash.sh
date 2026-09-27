#!/bin/bash
# ==================================================================================================
# THE FLEET DASHBOARD: IS gpu_world.sh RUNNING, WHAT IS IT DOING, AND IS IT MOVING? (2026-09-27)
# ==================================================================================================
# The retok fleet of 2026-09-27 was stopped by hand because nothing said it was alive. The card read
# 0% most of its first minutes: every smoke and calibration step starts fresh run.py processes that
# build on the CPU (python and torch, corpus, tokenizer, stream, model: 15-16 s at the retok shape on the
# 4-core CPU box, one run alone or four at once, and several times that when other work shares the CPU)
# before they touch the GPU, and the fleet log printed one line per step, at its end. This answers "is it
# doing anything?".
# Run it in a second terminal, from any directory (/workspace/LLM-Test is the owner's checkout):
#
#     bash /workspace/LLM-Test/tools/fleet_dash.sh   # the live fleet beside this checkout (else the newest),
#                                                 # redrawn every 5 s
#     bash tools/fleet_dash.sh gpu_retok_out      # that fleet (a path, relative to here or to the checkout)
#     bash tools/fleet_dash.sh --once             # one frame and exit: paste it into the chat
#     bash tools/fleet_dash.sh --html             # + writes $OUT/dashboard.html each tick, which reloads
#                                                 #   itself: open it in a browser or a file viewer (the
#                                                 #   page's text is plain: the terminal's colour codes
#                                                 #   are left out of it)
#     bash tools/fleet_dash.sh --serve 8080       # + serves that page on http://<this box>:8080/ (0.0.0.0)
#     bash tools/fleet_dash.sh --every 10 --stall-min 5 --no-color
# Ctrl-C ends the dashboard; the fleet keeps running. Plain text and ANSI colour only (no curses), so
# it works in a web terminal.
#
# THE BIG LINE IS THE VERDICT, read off $OUT/STATE, which gpu_world.sh rewrites at every step: its
# pid and that pid's start time, the phase, the step, and at the end how it ended.
#   RUNNING   the fleet's shell is alive: the same pid AND the same start time, so a pid reused after
#             a restart never reads as running;
#   STALLED   alive, but no run log, _started/_done book, cal/table.txt or SUMMARY line has changed for
#             --stall-min minutes (default 5) in the smoke, the calibration or the fleet. The 2026-09-24
#             fleet wrote a progress line every ~40 s at its slowest, so 5 minutes of nothing is a hang;
#   FINISHED  it wrote its analysis and its block;
#   STOPPED   it stopped with a reason (a signal, a tripwire, a failed smoke or analysis, the disk); its
#             block says it;
#   DEAD      no reason: the pid is gone and STATE records no end, or the heartbeat watcher saw the shell
#             vanish (SIGKILL, the OOM killer and a container stop kill without a trap);
#   NO FLEET  nothing in OUT; the fleets beside it are listed.
# An ended fleet whose processes still run (runs orphaned when it was killed) lists them: a launch into
# its OUT is refused until `gpu_world.sh --stop` clears them.
# A fleet launched by a gpu_world.sh from before STATE is read off its SUMMARY.txt, its PASTE_BACK.txt
# and the processes still running for it. It is FINISHED only if SUMMARY shows it ended its own analysis
# ('---- fleet finished' and '=== wrote .../SUMMARY.txt'): a block written afterwards by --analyze on a
# fleet killed part-way leaves it DEAD (2026-09-27 review: it read FINISHED, "runs: 0 of 0").
#
# UNDER IT: the stage and the time in it; each run of the current step -- starting on CPU (its log has
# no '=== device=' / '=== composed' line yet), training, finishing (its run ended and its run_job is
# still at work: k0's kept checkpoints are indexed before its rc is booked), done, FAILED, VANISHED
# (gone with no rc and no final line) -- with its windows so far out of its target, its windows/s and
# when it started; runs alive, done and failed; the aggregate windows/s (the sum of the training runs'
# rates); the ETA of the step, and in the fleet phase of the fleet, wave by wave over PAR slots; GPU
# utilisation and memory (nvidia-smi, when present); the CPU THIS CONTAINER uses, in cores, off its
# cgroup's CPU time, against the cores it may use (/proc/loadavg, printed beside it as the host's load,
# counts every container on the host); the free disk; the age of the fleet log's last line, of the last
# heartbeat and of the newest run output; and the fleet log's last 3 lines (heartbeat lines aside: the
# frame already says what they say).
# A run's windows come from its '[N windows]' progress lines (RUN.PROGRESS_WINDOWS: every 100 windows,
# so every ~2 s at the calibrated 42-50 windows/s per run and every ~40 s at the 2026-09-24 fleet's
# slowest) and from its '=== N windows' summary line; before window 101 a training run shows <101.
# A run's rate is measured from a sample in which it was already past a progress line -- a frame of
# this dashboard, or one gpu_world.sh keeps in $OUT/HEARTBEAT -- to its latest line, each at the time
# its log was written, over at most the last 5 minutes; without one it is averaged since the run began
# training (marked ~). A sample taken while the run was still building on the CPU is never its baseline
# (2026-09-27 review: that counted the startup as training, and the first minutes read 2-5x slow).
#
# IT READS $OUT/STATE, HEARTBEAT, SUMMARY.txt, PASTE_BACK.txt, cal/table.txt, the step's _started.txt,
# _done.txt and run logs, the fleet log STATE names, /proc, nvidia-smi and the disk. IT WRITES NOTHING
# INTO THE FLEET except $OUT/dashboard.html (--html, --serve). --serve serves THAT PAGE ONLY, with
# Python's http.server bound to 0.0.0.0: `python3 -m http.server` over OUT would hand every file there
# (logs, checkpoints) and a listing of them to anyone who can reach the port.
#
# gpu_world.sh reads a fleet through this same reader, so there is one reading, not three:
#   --status OUT     one frame, no colour, and an exit code: 0 RUNNING, 1 FINISHED, 2 NO FLEET,
#                    3 STOPPED, 4 DEAD, 5 STALLED (alive = 0 or 5). `bash gpu_world.sh --status`.
#   --line OUT       one heartbeat line; with --sample a second line, the JSON sample the next line
#                    measures its rates and the container's CPU against, which gpu_world.sh keeps in
#                    $OUT/HEARTBEAT.
#   --scan own|card|desc OUT_OR_PID   processes, one line each (pid, kind, command line):
#                    own  everything carrying GW_FLEET_OUT=OUT, and a gpu_world.sh launch from before
#                         the lock, or a run.py, writing under OUT;
#                    card the shells of fleets under ANOTHER OUT that use the GPU;
#                    desc the descendants of a pid.
set -u
exec python3 - "$(cd "$(dirname "$0")" && pwd)" "$@" <<'PY'
import html
import json
import os
import re
import sys
import time

TOOLS = sys.argv[1]
ROOT = os.path.dirname(TOOLS)
ARGS = sys.argv[2:]
VERDICT_RC = {"RUNNING": 0, "FINISHED": 1, "NO FLEET": 2, "STOPPED": 3, "DEAD": 4, "STALLED": 5}
DEFAULT_OUT = {"world": "gpu_world_out", "retok": "gpu_retok_out", "world_epoch": "gpu_world_epoch_out"}
READER_FLAGS = {"--status", "--analyze", "--stop", "--help", "-h"}
HIST_MAX = 24            # heartbeat samples kept (12 minutes at gpu_world.sh's default HB_EVERY of 30 s)
RATE_SPAN = 300.0        # a rate is measured over at most the last 5 minutes
USAGE = ("usage: bash tools/fleet_dash.sh [OUT] [--once] [--html] [--serve PORT] [--every S] "
         "[--stall-min M] [--no-color]\n"
         "       bash tools/fleet_dash.sh --status OUT | --line [--sample] OUT | --scan own|card|desc OUT_OR_PID")


def usage(rc=2):
    print(USAGE)
    sys.exit(rc)


# ------------------------------------------------------------------------------------------ arguments
MODE, OUT_ARG, EVERY, STALL_MIN, HTML, SERVE, SAMPLE, SCAN = "watch", None, 5.0, 5.0, False, None, False, None
COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None
i = 0
while i < len(ARGS):
    a = ARGS[i]
    if a in ("-h", "--help"):
        usage(0)
    elif a in ("--once", "--status", "--line"):
        MODE = a[2:]
    elif a == "--sample":
        SAMPLE = True
    elif a == "--html":
        HTML = True
    elif a == "--no-color":
        COLOR = False
    elif a in ("--every", "--stall-min", "--serve", "--scan"):
        if i + 1 >= len(ARGS):
            usage()
        i += 1
        val = ARGS[i]
        try:
            if a == "--every":
                EVERY = max(1.0, float(val))
            elif a == "--stall-min":
                STALL_MIN = max(0.01, float(val))
            elif a == "--serve":
                SERVE, HTML = int(val), True
            else:
                SCAN, MODE = val, "scan"
        except ValueError:
            print(f"!! {a} {val!r} is not a number")
            sys.exit(2)
    elif a.startswith("-"):
        print(f"!! unknown option {a}")
        usage()
    else:
        OUT_ARG = a
    i += 1
if MODE in ("status", "line", "scan"):
    COLOR = False
    if OUT_ARG is None:
        usage()


# ------------------------------------------------------------------------------------------ /proc
def proc_stat(pid):
    """(state, ppid, starttime) of a process, None when it is gone."""
    try:
        with open(f"/proc/{pid}/stat") as fh:
            f = fh.read().rsplit(")", 1)[1].split()
        return f[0], int(f[1]), f[19]
    except (OSError, IndexError, ValueError):
        return None


def alive(pid, start=None):
    """The pid runs (not a zombie) and, given a start time, is the same process."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    st = proc_stat(pid)
    return st is not None and st[0] != "Z" and (not start or st[2] == str(start))


def cmdline(pid):
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as fh:
            return [x.decode(errors="replace") for x in fh.read().split(b"\0") if x]
    except OSError:
        return []


def environ(pid):
    try:
        with open(f"/proc/{pid}/environ", "rb") as fh:
            raw = fh.read().split(b"\0")
    except OSError:
        return {}
    env = {}
    for x in raw:
        k, eq, val = x.decode(errors="replace").partition("=")
        if eq:
            env[k] = val
    return env


def all_pids():
    for d in os.listdir("/proc"):
        if d.isdigit():
            yield int(d)


def ancestors(pid):
    out = set()
    while pid and pid > 1 and len(out) < 4096:
        out.add(pid)
        st = proc_stat(pid)
        if st is None:
            break
        pid = st[1]
    return out


def descendants(root):
    kids = {}
    for p in all_pids():
        st = proc_stat(p)
        if st:
            kids.setdefault(st[1], []).append(p)
    out, todo = [], [root]
    while todo:
        for c in kids.get(todo.pop(), []):
            out.append(c)
            todo.append(c)
    return out


def kind_of(argv):
    base = [os.path.basename(a) for a in argv]
    if not base:
        return "other"
    if base[0].startswith("nvidia-cuda-mps"):
        return "mps"
    if base[0] == "nvidia-smi":
        return "sampler"
    if "run.py" in base:
        return "run"
    if "gpu_world.sh" in base:
        return "shell"
    if base[0] in ("sleep", "timeout", "tar", "tail", "cat", "date", "flock"):
        return "transient"
    return "other"


def launch_out(argv, env, cwd):
    """The OUT of a gpu_world.sh LAUNCH (not a --status/--analyze/--stop call), else None."""
    base = [os.path.basename(a) for a in argv]
    if "gpu_world.sh" not in base:
        return None
    j = base.index("gpu_world.sh")
    if j > 0 and base[0] not in ("bash", "sh"):
        return None
    if set(argv[j + 1:]) & READER_FLAGS:
        return None
    if env.get("GW_FLEET_OUT"):
        return os.path.realpath(env["GW_FLEET_OUT"])
    exp = env.get("EXP") or "world"
    return os.path.realpath(os.path.join(cwd, env.get("OUT") or DEFAULT_OUT.get(exp, "gpu_world_out")))


def scan(mode, target):
    """[(pid, kind, cmdline)]: own = the processes of the fleet in OUT; card = the shells of fleets under
    another OUT on the GPU; desc = the descendants of a pid."""
    if mode == "desc":
        # never this scan's own ancestors (the caller's command substitution is a fork of the fleet's
        # shell, and would read as one of its subshells), never a zombie
        skip = ancestors(os.getpid())
        rows = []
        for p in descendants(int(target)):
            st = proc_stat(p)
            if p in skip or st is None or st[0] == "Z":
                continue
            argv = cmdline(p)
            rows.append((p, kind_of(argv), " ".join(argv)[:240]))
        return rows
    out = os.path.realpath(target)
    skip = ancestors(os.getpid())
    rows = []
    for p in sorted(all_pids()):
        if p in skip:
            continue
        argv = cmdline(p)
        if not argv:
            continue
        env = environ(p)
        try:
            cwd = os.readlink(f"/proc/{p}/cwd")
        except OSError:
            cwd = "/"
        kind, fo, hit = kind_of(argv), env.get("GW_FLEET_OUT"), False
        if mode == "own":
            if fo:
                hit = os.path.realpath(fo) == out
            else:
                hit = launch_out(argv, env, cwd) == out
                if not hit and kind == "run":
                    for k, a in enumerate(argv[:-1]):
                        if a in ("--loss-curve", "--flush-bytes"):
                            hit = hit or os.path.realpath(os.path.join(cwd, argv[k + 1])).startswith(out + os.sep)
        elif mode == "card" and kind == "shell":
            lo = launch_out(argv, env, cwd)
            dev = env.get("GW_DEVICE") or env.get("DEVICE") or "cuda"
            hit = lo is not None and lo != out and dev == "cuda"
            if hit:                              # one row per fleet: its first shell, not every subshell
                if any(r[3] == lo for r in rows):
                    continue
                rows.append((p, kind, f"a fleet in {lo}: " + " ".join(argv)[:200], lo))
                continue
        if hit:
            rows.append((p, kind, " ".join(argv)[:240], None))
    return [r[:3] for r in rows]


if MODE == "scan":
    if SCAN not in ("own", "card", "desc"):
        usage()
    for p, k, c in scan(SCAN, OUT_ARG):
        print(f"{p}\t{k}\t{c}")
    sys.exit(0)


# ------------------------------------------------------------------------------------------ files
def rd(path, limit=None, tail=False):
    try:
        with open(path, "rb") as fh:
            if limit is not None and tail:
                fh.seek(0, 2)
                fh.seek(max(0, fh.tell() - limit))
                data = fh.read()
            else:
                data = fh.read() if limit is None else fh.read(limit)
        return data.decode(errors="replace")
    except OSError:
        return ""


def mtime(path):
    try:
        return os.path.getmtime(path) if path else None
    except OSError:
        return None


def read_kv(path):
    t = rd(path)
    if not t:
        return None
    d = {}
    for ln in t.splitlines():
        k, eq, val = ln.partition("=")
        if eq and not ln.startswith("#"):
            d[k.strip()] = val.strip()          # a key written twice: the later line wins
    return d


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def hms(t):
    return time.strftime("%H:%M:%SZ", time.gmtime(t)) if t else "?"


def dur(s):
    if s is None:
        return "?"
    s = int(max(0, s))
    if s < 60:
        return f"{s} s"
    if s < 3600:
        return f"{s // 60}m{s % 60:02d}s"
    return f"{s // 3600}h{s % 3600 // 60:02d}m"


def eta_txt(s):
    return "?" if s is None else (f"~{s / 3600:.1f} h" if s >= 5400 else f"~{dur(s)}")


# ------------------------------------------------------------------------------------------ the verdict
def summary_phase(out, S):
    """The phase of a fleet with no STATE (launched by a gpu_world.sh from before it), off SUMMARY.txt."""
    if "---- fleet finished" in S:
        return "analysis", "", os.path.join(out, "logs")
    if "---- 2. fleet started" in S:
        return "fleet", "", os.path.join(out, "logs")
    if "---- calibration" in S:
        try:
            ks = sorted(int(n[1:]) for n in os.listdir(os.path.join(out, "cal")) if re.fullmatch(r"k\d+", n))
        except OSError:
            ks = []
        k = ks[-1] if ks else 1
        return "cal", f"k={k}", os.path.join(out, "cal", f"k{k}")
    if "---- 1. smoke" in S:
        return "smoke", "smoke", os.path.join(out, "smoke")
    return "setup", "", out


def newest_output(out, v):
    """The newest write among the step's run logs and books, cal/table.txt and SUMMARY.txt -- never the
    fleet log, which carries the heartbeat, nor HEARTBEAT."""
    t = [mtime(os.path.join(out, "SUMMARY.txt")) or 0, mtime(os.path.join(out, "cal", "table.txt")) or 0]
    d = v.get("step_dir")
    if d and os.path.isdir(d):
        try:
            t += [mtime(os.path.join(d, n)) or 0 for n in os.listdir(d) if n.endswith((".log", ".txt"))]
        except OSError:
            pass
    return max(t) or None


def verdict(out):
    """STATE's fields plus verdict (RUNNING, STALLED, FINISHED, STOPPED, DEAD, NO FLEET) and why."""
    st = read_kv(os.path.join(out, "STATE"))
    S = rd(os.path.join(out, "SUMMARY.txt"))
    now = time.time()
    if st is None:
        if not S and not os.path.isdir(os.path.join(out, "logs")):
            return {"verdict": "NO FLEET", "why": f"nothing in {out}", "out": out}
        pb = rd(os.path.join(out, "PASTE_BACK.txt"))
        ph, step, sd = summary_phase(out, S)
        # ITS OWN LAST WRITE: SUMMARY's. A block --analyze wrote later is no sign of life (2026-09-27 review:
        # it made a dead fleet the dashboard's default pick).
        v = {"phase": ph, "step": step, "step_dir": sd, "old": True, "out": out,
             "updated": mtime(os.path.join(out, "SUMMARY.txt")) or 0}
        m = re.match(r"=== gpu_world\.sh\s+(\S+)\s+commit\s*(\S*)", S)
        if m:
            v["launch"], v["commit"] = m.group(1), m.group(2)
        live = [r for r in scan("own", out) if r[1] in ("shell", "run")]
        # FINISHED ONLY IF THE FLEET ITSELF ENDED ITS ANALYSIS: that script's SUMMARY closes with
        # '---- fleet finished ...' and then '=== wrote .../SUMMARY.txt'. A block and no such end is one
        # --analyze wrote afterwards over a fleet killed part-way (2026-09-27 review: it read FINISHED).
        ended = "---- fleet finished" in S and re.search(r"^=== wrote \S*SUMMARY\.txt$", S, re.M) is not None
        if live:
            v.update(verdict="RUNNING", why=f"{len(live)} process(es) of a gpu_world.sh from before STATE",
                     pid=live[0][0], procs=live)
        elif "==== PASTE THIS BACK ====" in pb:
            m = re.search(r"^STOPPED (?:BEFORE|AT) THE ANALYSIS: (.*)$", pb, re.M)
            if m:
                v.update(verdict="STOPPED", why=m.group(1))
            elif ended:
                v.update(verdict="FINISHED", why="its block is written")
            else:
                where = {"smoke": "the smoke", "cal": f"calibration {step}", "fleet": "the fleet",
                         "analysis": "the analysis"}.get(ph, "the setup")
                v.update(verdict="DEAD", why=f"no process of it runs and it recorded no end: it died during {where} "
                                             f"(a gpu_world.sh from before STATE); its block was written afterwards, "
                                             f"by --analyze")
        else:
            v.update(verdict="DEAD", why="no process of it runs and it wrote no block (a gpu_world.sh from "
                                         "before STATE, which recorded no end)")
        return v
    v = dict(st)
    v["out"] = out
    for k in ("since", "updated", "ended", "hb_every", "step_runs", "step_windows", "par", "runs_total",
              "windows", "startup_s", "launch_t"):
        v[k] = num(v.get(k))
    end = st.get("end")
    here = not st.get("host") or st["host"] == os.uname().nodename
    if end in ("finished", "stopped", "died"):
        v.update(verdict={"finished": "FINISHED", "stopped": "STOPPED", "died": "DEAD"}[end],
                 why=st.get("reason") or {"finished": "its analysis and its block are written",
                                          "stopped": "?", "died": "its shell vanished"}[end])
        # AN ENDED FLEET WHOSE RUNS STILL RUN SAYS SO (2026-09-27 review: a Ctrl-C left a run training, holding
        # the lock, under a STOPPED that listed nothing); its shell, still exiting, is not counted.
        live = [r for r in scan("own", out) if r[1] in ("shell", "run") and str(r[0]) != str(st.get("pid"))] \
            if here else []
        if live:
            v.update(procs=live, why=v["why"] + f"; but {len(live)} of its process(es) still run: gpu_world.sh "
                                                "--stop clears them")
    elif not here:
        hb = mtime(os.path.join(out, "HEARTBEAT"))
        fresh = hb is not None and now - hb < 3 * (v.get("hb_every") or 30) + 10
        v.update(verdict="RUNNING" if fresh else "DEAD",
                 why=f"on host {st['host']}, whose processes cannot be seen from here; its heartbeat is "
                     + (f"{dur(now - hb)} old" if hb else "absent"))
    elif alive(st.get("pid"), st.get("pid_start")):
        v.update(verdict="RUNNING", why="its shell is alive")
        v["newest"] = newest_output(out, v)
        if (st.get("phase") in ("smoke", "cal", "fleet") and v["newest"] is not None
                and now - v["newest"] > STALL_MIN * 60):
            v.update(verdict="STALLED", why=f"its shell is alive, but no run log, book or SUMMARY line has "
                                             f"changed for {dur(now - v['newest'])} (--stall-min {STALL_MIN:g})")
    else:
        live = [r for r in scan("own", out) if r[1] in ("shell", "run")]
        v.update(verdict="DEAD", procs=live,
                 why=f"its shell (pid {st.get('pid')}) is gone and STATE records no end: it was killed without "
                     "a trap (SIGKILL, the OOM killer, a container stop)"
                     + (f"; {len(live)} of its process(es) still run: gpu_world.sh --stop clears them" if live else ""))
    return v


def fleets_beside(parent, skip=None):
    """[(path, verdict, updated)] of the fleet directories in parent, newest first."""
    rows = []
    try:
        names = os.listdir(parent)
    except OSError:
        return rows
    for n in names:
        p = os.path.realpath(os.path.join(parent, n))
        if not n.startswith("gpu_") or not os.path.isdir(p) or p == skip:
            continue
        if not (os.path.exists(os.path.join(p, "STATE")) or os.path.exists(os.path.join(p, "SUMMARY.txt"))):
            continue
        v = verdict(p)
        rows.append((p, v["verdict"], v.get("updated") or mtime(os.path.join(p, "SUMMARY.txt")) or 0))
    rows.sort(key=lambda r: -r[2])
    return rows


def resolve_out(arg):
    if arg:
        for base in (os.getcwd(), ROOT):
            p = os.path.join(base, arg)
            if os.path.isdir(p):
                return os.path.realpath(p)
        return os.path.realpath(os.path.join(os.getcwd(), arg))
    cands = fleets_beside(ROOT)
    live = [c for c in cands if c[1] in ("RUNNING", "STALLED")]
    return (live or cands)[0][0] if cands else os.path.realpath(os.path.join(ROOT, "gpu_retok_out"))


# ------------------------------------------------------------------------------------------ the runs
_CACHE = {}


def parse_log(path):
    """What a run log says, cached by its size and mtime."""
    try:
        s = os.stat(path)
    except OSError:
        return {}
    key = (s.st_size, s.st_mtime_ns)
    hit = _CACHE.get(path)
    if hit and hit[0] == key:
        return hit[1]
    head = rd(path, 16384)
    whole = rd(path) if s.st_size <= 8_000_000 else rd(path, 8_000_000, tail=True)
    info = {"mtime": s.st_mtime}
    m = re.search(r"^=== composed: [^\n]*?startup took ([\d.]+) s", head, re.M)
    info["startup"] = float(m.group(1)) if m else None
    info["composed"] = "=== device=" in head or "=== composed:" in head
    fin = re.search(r"^=== (\d+) windows[ ,][^\n]*? in ([\d.]+)s", whole, re.M)
    if fin:
        info["final"], info["loop_s"] = int(fin.group(1)), float(fin.group(2))
    pr = re.findall(r"^\[(\d+) windows\]", whole, re.M)
    info["prog"] = int(pr[-1]) if pr else None
    ls = [x for x in whole[-8192:].splitlines() if x.strip()]
    info["last"] = ls[-1][:150] if ls else ""
    _CACHE[path] = (key, info)
    return info


def read_book(path, rx):
    out = {}
    for ln in rd(path).splitlines():
        m = re.match(rx, ln)
        if m:
            out[m.group(1)] = m
    return out


def step_runs(v):
    """The runs of the current step, as dicts: tag, state, windows, target, rate, t0, ..."""
    sd = v.get("step_dir")
    if not sd or not os.path.isdir(sd) or os.path.realpath(sd) == os.path.realpath(v.get("out") or ""):
        return []                                # the setup and the analysis run no step
    started = read_book(os.path.join(sd, "_started.txt"),
                        r"(\S+) pid=(\d+) t0=(\d+)(?: cap=(\d+))?(?: target=(\d+))?")
    done = read_book(os.path.join(sd, "_done.txt"), r"(\S+) rc=(-?\d+) secs=(\d+)")
    tags = list(started) + [t for t in done if t not in started]
    if not started:                              # a fleet from before _started.txt: its logs
        try:
            tags += sorted(n[:-4] for n in os.listdir(sd) if n.endswith(".log") and n[:-4] not in done)
        except OSError:
            pass
    now = time.time()
    rows = []
    for tag in tags:
        s, d = started.get(tag), done.get(tag)
        info = parse_log(os.path.join(sd, tag + ".log"))
        r = {"tag": tag, "t0": int(s.group(3)) if s else None, "pid": int(s.group(2)) if s else None,
             "startup": info.get("startup"), "mtime": info.get("mtime"), "last": info.get("last", ""),
             "windows": info.get("final") or info.get("prog")}
        r["target"] = (int(s.group(5) or s.group(4)) if s and (s.group(5) or s.group(4))
                       else int(v.get("step_windows") or 0) or None)
        if d:
            r["done"], r["rc"] = True, int(d.group(2))
            r["state"] = "done" if r["rc"] == 0 else f"FAILED rc={r['rc']}"
            if info.get("final") and info.get("loop_s"):
                r["rate"] = info["final"] / info["loop_s"]
        else:
            r["done"] = False
            if r["pid"] is None:
                r["state"] = "no pid on record"
            elif alive(r["pid"]) and "run.py" in " ".join(cmdline(r["pid"])):
                if info.get("final") is not None:
                    r["state"], r["phase"] = "finishing (its report)", "train"
                elif info.get("composed"):
                    r["state"], r["phase"], r["windows"] = "training", "train", r["windows"] or 0
                else:
                    r["state"], r["phase"] = f"starting on CPU ({dur(now - r['t0'])})", "cpu"
            elif info.get("final") is not None:
                # ITS RUN ENDED, WITH ITS FINAL LINE, AND ITS run_job IS STILL AT WORK: k0's kept checkpoints
                # are swept and indexed (a torch import, two loads of each copy) before its rc is booked
                # (2026-09-27 review: this read VANISHED, like a crash, in every smoke and at every k0's end).
                r["state"], r["phase"] = ("finishing (indexing ckpts)" if tag.startswith("k0.")
                                          else "finishing (its rc next)"), "post"
                if info.get("loop_s"):
                    r["rate"] = info["final"] / info["loop_s"]
            else:
                r["state"] = "VANISHED (no rc)"
        if r["t0"] and r["startup"] is not None:
            r["t_train"] = r["t0"] + r["startup"]
        rows.append(r)
    return rows


# ------------------------------------------------------------------------------------------ rates and ETA
def load_hist(out):
    """The samples gpu_world.sh keeps in HEARTBEAT: [(t, {key: windows}, total, {key: log mtime})], oldest
    first (a sample from before the mtimes were kept has {} there)."""
    for ln in reversed(rd(os.path.join(out, "HEARTBEAT")).splitlines()):
        if ln.startswith("{"):
            try:
                return [(float(e[0]), dict(e[1]), int(e[2]), dict(e[3]) if len(e) > 3 else {})
                        for e in json.loads(ln).get("hist", [])]
            except (ValueError, TypeError, IndexError):
                return []
    return []


def load_cpu(out):
    """The container's CPU sample gpu_world.sh keeps in HEARTBEAT: (t, cpu seconds, cgroup file), or None."""
    for ln in reversed(rd(os.path.join(out, "HEARTBEAT")).splitlines()):
        if ln.startswith("{"):
            try:
                c = json.loads(ln).get("cpu")
                return (float(c[0]), float(c[1]), str(c[2])) if c else None
            except (ValueError, TypeError, IndexError):
                return None
    return None


def apply_rates(rows, key, hist, now):
    """Each training run's windows/s and the aggregate, the sum of those rates. A run's rate runs from the
    oldest sample of the last RATE_SPAN seconds in which it was already past a progress line (windows > 0
    there) to its latest line, each at the time its log was written (a sample without that time: the
    sample's own time, to now), over at least 5 s. A SAMPLE FROM WHILE IT WAS STILL ON THE CPU IS NEVER
    ITS BASELINE (2026-09-27 review): it counted the startup as training, so every calibration step and
    the fleet's first minutes read 2-5x slow, the ETA as many times too long. A run with no such sample is
    averaged since it began training (windows / (its log's time - its start + startup), marked ~)."""
    cur = {f"{key}/{r['tag']}": (r.get("windows") or 0) for r in rows}
    total = sum(cur.values())
    for r in rows:
        k = f"{key}/{r['tag']}"
        if r.get("phase") != "train" or not cur[k]:
            continue
        for t, runs, _tot, mts in hist:                  # oldest first
            b = runs.get(k) or 0
            if not 0 < b < cur[k] or not 5 <= now - t <= RATE_SPAN:
                continue
            t0_, t1_ = (mts[k], r.get("mtime") or now) if mts.get(k) else (t, now)
            if t1_ - t0_ >= 5:
                r["rate"] = (cur[k] - b) / (t1_ - t0_)
                break
    for r in rows:
        if r.get("rate") is None and r.get("phase") == "train" and r.get("windows") and r.get("t_train") \
                and r.get("mtime") and r["mtime"] - r["t_train"] > 1:
            r["rate"], r["rate_avg"] = r["windows"] / (r["mtime"] - r["t_train"]), True
    live = [r["rate"] for r in rows if r.get("rate") and r.get("phase") == "train"]
    agg = sum(live) if live else None
    if not total:                    # no run past its first progress line (window 101): not measured, not 0
        agg = None
    return total, agg, {"t": now, "runs": cur, "total": total,
                        "mt": {f"{key}/{r['tag']}": r["mtime"] for r in rows
                               if r.get("phase") == "train" and r.get("mtime") and cur[f"{key}/{r['tag']}"]}}


def step_eta(rows, v, now):
    """(seconds left, waves, queued): each run at its own rate (a mean for one still on the CPU, after
    the startup the smoke measured), and in the fleet phase the queued runs wave by wave over PAR."""
    rates = [r["rate"] for r in rows if r.get("rate") and not r.get("done")] or \
            [r["rate"] for r in rows if r.get("rate")]
    if not rates:
        return None
    prior = sum(rates) / len(rates)
    startup = v.get("startup_s") or 15.0
    ends = []
    for r in rows:
        if r.get("done") or r.get("phase") == "post" or r.get("state", "").startswith("VANISHED"):
            continue
        target, w = r.get("target") or 0, r.get("windows") or 0
        if r.get("phase") == "cpu":
            ends.append(max(0.0, startup - (now - (r.get("t0") or now))) + target / prior)
        else:
            ends.append(max(0.0, target - w) / (r.get("rate") or prior))
    queued = max(0, int(v.get("runs_total") or 0) - len(rows)) if v.get("phase") == "fleet" else 0
    par = max(1, int(v.get("par") or 0) or len(ends))
    slots = sorted(ends) + [0.0] * max(0, par - len(ends))
    per = startup + (v.get("windows") or v.get("step_windows") or 0) / prior
    for _ in range(queued):
        slots.sort()
        slots[0] += per
    return (max(slots) if slots else 0.0), 1 + -(-queued // par), queued


# ------------------------------------------------------------------------------------------ the machine
def gpu():
    import shutil
    import subprocess
    if not shutil.which("nvidia-smi"):
        return None
    try:
        p = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total",
                            "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=8)
    except (OSError, subprocess.SubprocessError):
        return "nvidia-smi did not answer within 8 s"
    rows = []
    for ln in p.stdout.splitlines():
        f = [x.strip() for x in ln.split(",")]
        try:
            rows.append((float(f[0]), float(f[1]), float(f[2])))
        except (ValueError, IndexError):
            pass
    if not rows:
        return "nvidia-smi answered nothing readable"
    return "; ".join(f"{u:.0f}% busy, {m / 1024:.1f} of {t / 1024:.1f} GiB" for u, m, t in rows)


def cores():
    try:
        a, b = open("/sys/fs/cgroup/cpu.max").read().split()
        if a != "max":
            return max(1, int(a) // int(b)), "cgroup quota"
    except (OSError, ValueError):
        pass
    try:
        a = int(open("/sys/fs/cgroup/cpu/cpu.cfs_quota_us").read())
        b = int(open("/sys/fs/cgroup/cpu/cpu.cfs_period_us").read())
        if a > 0:
            return max(1, a // b), "cgroup quota"
    except (OSError, ValueError):
        pass
    return len(os.sched_getaffinity(0)), "visible"


def load():
    """The 1-minute load average. /proc/loadavg IS NOT PER CONTAINER: it counts every container on the host,
    so it is shown as the host's, beside this container's own CPU (cpu_busy)."""
    try:
        return float(open("/proc/loadavg").read().split()[0])
    except (OSError, ValueError, IndexError):
        return None


def cg_cpu(pid=None):
    """(CPU seconds used so far, the file read) by the cgroup `pid` is in (this process's by default): cgroup
    v2's cpu.stat usage_usec, else v1's cpuacct.usage; None where neither can be read. The path
    /proc/<pid>/cgroup names is tried under the mount first (a cgroup namespace shared with the host), then
    the mount's root (a container's own namespace, or its own v1 subtree mounted there)."""
    try:
        with open(f"/proc/{pid or 'self'}/cgroup") as fh:
            lines = fh.read().splitlines()
    except OSError:
        lines = []
    cands = []
    for ln in lines:
        h, _, rest = ln.partition(":")
        ctl, _, path = rest.partition(":")
        path = path.rstrip("/")
        if h == "0" and not ctl:
            cands += [("v2", f"{b}{path}/cpu.stat") for b in ("/sys/fs/cgroup", "/sys/fs/cgroup/unified")]
            cands.append(("v2", "/sys/fs/cgroup/cpu.stat"))
        elif "cpuacct" in ctl.split(","):
            for d in dict.fromkeys((ctl, "cpuacct", "cpu,cpuacct")):
                cands += [("v1", f"/sys/fs/cgroup/{d}{path}/cpuacct.usage"), ("v1", f"/sys/fs/cgroup/{d}/cpuacct.usage")]
    cands += [("v2", "/sys/fs/cgroup/cpu.stat"), ("v1", "/sys/fs/cgroup/cpuacct/cpuacct.usage")]
    for kind, path in cands:
        try:
            with open(path) as fh:
                if kind == "v1":
                    return int(fh.read()) / 1e9, path
                for ln in fh:
                    k, _, val = ln.partition(" ")
                    if k == "usage_usec":
                        return int(val) / 1e6, path
        except (OSError, ValueError):
            continue
    return None


def cpu_busy(v, prev, wait=True):
    """(cores busy, the seconds measured over, the sample to keep) of the cgroup the fleet's shell is in
    (else this process's): the change in its CPU time since `prev` -- (t, seconds, file), this dashboard's
    last frame or the heartbeat's -- when that is 1-600 s old and read the same file, else over 0.5 s now
    (only with `wait`). None where the cgroup's CPU time cannot be read."""
    pid = v.get("pid") if alive(v.get("pid"), v.get("pid_start")) else None
    t1, cur = time.time(), cg_cpu(pid)
    if cur is None:
        return None
    if prev and prev[2] == cur[1] and 1 <= t1 - prev[0] <= 600 and cur[0] >= prev[1]:
        return (cur[0] - prev[1]) / (t1 - prev[0]), t1 - prev[0], (t1, cur[0], cur[1])
    if not wait:
        return None
    time.sleep(0.5)
    t2, c2 = time.time(), cg_cpu(pid)
    if c2 is None or c2[1] != cur[1] or c2[0] < cur[0]:
        return None
    return (c2[0] - cur[0]) / (t2 - t1), t2 - t1, (t2, c2[0], c2[1])


def disk(out):
    p = out
    while p and not os.path.exists(p):
        p = os.path.dirname(p)
    try:
        s = os.statvfs(p or "/")
        return s.f_bavail * s.f_frsize / 1e9
    except OSError:
        return None


def last_lines(path, n=3):
    return [x.rstrip() for x in rd(path, 65536, tail=True).splitlines()
            if x.strip() and not x.startswith("[hb ")][-n:]


# ------------------------------------------------------------------------------------------ reading a fleet
def collect(out, mem):
    now = time.time()
    v = verdict(out)
    if v["verdict"] == "NO FLEET":
        return v, now
    rows = step_runs(v)
    key = os.path.relpath(v.get("step_dir") or out, out)
    total, agg, sample = apply_rates(rows, key, mem.get("hist") or load_hist(out), now)
    v.update(rows=rows, total=total, agg=agg, sample=sample)
    # THIS CONTAINER'S CPU, not the host's load (2026-09-27 review): measured over 0.5 s only when something
    # of the fleet runs and no earlier sample is at hand
    v["cpu"] = cpu_busy(v, mem.get("cpu") or load_cpu(out),
                        wait=v["verdict"] in ("RUNNING", "STALLED") or bool(v.get("procs")))
    v["eta"] = step_eta(rows, v, now) if rows and v["verdict"] in ("RUNNING", "STALLED") else None
    hb = mtime(os.path.join(out, "HEARTBEAT"))
    v["hb_age"] = now - hb if hb else None
    lg = v.get("log") if v.get("log") and os.path.isfile(v.get("log")) else None
    v["log_path"], v["log_age"] = lg, (now - mtime(lg)) if lg and mtime(lg) else None
    v["newest"] = v.get("newest") or newest_output(out, v)
    return v, now


def counts(rows):
    """cpu (starting), train, post (finishing: ended, rc not booked yet), done, failed, other (vanished)."""
    c = {"cpu": 0, "train": 0, "post": 0, "done": 0, "failed": 0, "other": 0}
    for r in rows:
        if r.get("done"):
            c["done" if r.get("rc") == 0 else "failed"] += 1
        else:
            c[{"cpu": "cpu", "train": "train", "post": "post"}.get(r.get("phase"), "other")] += 1
    return c


def ended_txt(c):
    """', N done[, N finishing], N failed[, N vanished]', as the heartbeat and the frame say it."""
    return (f", {c['done']} done" + (f", {c['post']} finishing" if c["post"] else "") + f", {c['failed']} failed"
            + (f", {c['other']} vanished" if c["other"] else ""))


def stage_short(v):
    ph = v.get("phase") or "?"
    return {"cal": f"cal {v.get('step') or ''}".strip(), "setup": "setup", "smoke": "smoke", "fleet": "fleet",
            "analysis": "analysis", "stopping": "stopping"}.get(ph, ph)


def stage_long(v):
    ph = v.get("phase") or "?"
    runs, win = int(v.get("step_runs") or 0) or "?", int(v.get("step_windows") or 0) or "?"
    if ph == "smoke":
        return f"smoke: every arm, seed 0, {runs} run(s) x {win} windows"
    if ph == "cal":
        return f"calibration {v.get('step') or ''}: {runs} run(s) x {win} windows"
    if ph == "fleet":
        return (f"fleet: {int(v.get('runs_total') or 0) or '?'} run(s), {int(v.get('par') or 0) or '?'} at a "
                f"time, {int(v.get('windows') or 0) or '?'} windows each")
    return {"setup": "setup (the checks before the smoke)", "analysis": "analysis, the block and the archive",
            "stopping": "stopping: its runs are being stopped and its block written"}.get(ph, ph)


def line(v, now):
    """The heartbeat line gpu_world.sh prints."""
    V = v["verdict"]
    head = f"[hb {hms(now)}] {V}"
    if v.get("pid"):
        head += f" pid {v['pid']}" + (f" up {dur(now - v['launch_t'])}" if v.get("launch_t") else "")
    parts = [head]
    if V == "NO FLEET":
        return f"{head} | {v.get('why')}"
    since = v.get("since")
    parts.append(stage_short(v) + (f" since {hms(since)} ({dur(now - since)})" if since else ""))
    rows = v.get("rows") or []
    if rows:
        c = counts(rows)
        tw = [r.get("windows") or 0 for r in rows if r.get("phase") == "train"]
        tgt = int(v.get("step_windows") or 0)
        n = f"{int(v['runs_total'])} run(s), PAR {int(v.get('par') or 0)}" \
            if v.get("phase") == "fleet" and v.get("runs_total") else f"{len(rows)} run(s)"
        wtxt = "" if not tw else (f" (w <101/{tgt})" if max(tw) == 0 else f" (w {min(tw)}-{max(tw)}/{tgt})")
        seg = f"{n}: {c['cpu']} on CPU, {c['train']} training" + wtxt + ended_txt(c)
        if v.get("phase") == "fleet" and v.get("runs_total"):
            q = max(0, int(v["runs_total"]) - len(rows))
            seg += f", {q} queued" if q else ""
        parts.append(seg)
        seg = f"{v.get('total', 0):,} windows, " + (f"{v['agg']:.1f} w/s" if v.get("agg") is not None else
                                                    "rate ?" if v.get("total") else "rate: no run past window 101 yet")
        if v.get("eta"):
            fin, waves, _q = v["eta"]
            seg += f", ETA {eta_txt(fin)}" + (f" ({waves} waves)" if waves > 1 else "")
        parts.append(seg)
    g = gpu()
    if g:
        parts.append("GPU " + g)
    cb, ld = v.get("cpu"), load()
    if cb:
        parts.append(f"CPU {cb[0]:.1f}/{cores()[0]} cores busy")
    elif ld is not None:
        parts.append(f"host load {ld:.1f}")
    if v.get("newest"):
        parts.append(f"newest run output {dur(now - v['newest'])} ago")
    if V != "RUNNING":
        parts.append(v.get("why", ""))
    return " | ".join(p for p in parts if p)


def paint(txt, code):
    return f"\033[{code}m{txt}\033[0m" if COLOR else txt


def cal_history(out):
    rows = []
    for ln in rd(os.path.join(out, "cal", "table.txt")).splitlines():
        f = ln.split()
        try:
            rows.append(f"k={int(f[0])} {float(f[1]):.1f}")
        except (ValueError, IndexError):
            pass
    return ("calibrated so far (aggregate windows/s): " + ", ".join(rows)) if rows else ""


def frame(v, now, width=100):
    V = v["verdict"]
    col = {"RUNNING": "1;42;97", "STALLED": "1;43;30", "FINISHED": "1;44;97", "STOPPED": "1;41;97",
           "DEAD": "1;41;97", "NO FLEET": "1;47;30"}[V]
    out = v.get("out", "?")
    who = [os.path.relpath(out, ROOT) if out.startswith(ROOT + os.sep) else out]
    for k, lab in (("exp", "EXP="), ("pid", "pid "), ("launch", "launched "), ("commit", "commit ")):
        if v.get(k):
            who.append(f"{lab}{v[k]}")
    L = ["=" * width, paint(f"  #####  {V}  #####  ", col) + "  " + "  ".join(who), "=" * width]
    if V != "RUNNING":
        L.append(f" why        {v.get('why', '')}")
    if V == "NO FLEET":
        others = fleets_beside(os.path.dirname(out), skip=out)
        if others:
            L.append(" fleets beside it:")
            L += [f"   {vv:<9} {os.path.basename(p)}   (updated {hms(t)})" for p, vv, t in others[:8]]
        L.append(f" ({hms(now)})")
        return "\n".join(L)
    since = v.get("since")
    L.append(f" stage      {stage_long(v)}" + (f"; since {hms(since)} ({dur(now - since)})" if since else ""))
    hist = cal_history(out)
    if hist:
        L.append(f"            {hist}")
    if v.get("startup_s"):
        L.append(f"            each run first builds on the CPU for ~{v['startup_s']:.0f} s (measured in the smoke;"
                 " longer when the CPU is shared): the GPU reads idle then")
    rows = v.get("rows") or []
    book = rd(os.path.join(out, "logs", "_done.txt"))
    if book and v.get("phase") != "fleet":       # the fleet's runs, once the fleet has run (done, stopped)
        rcs = re.findall(r"^\S+ rc=(-?\d+) ", book, re.M)
        bad = sum(1 for x in rcs if x != "0")
        L.append(f" fleet runs {len(rcs)} ended" + (f" of {int(v['runs_total'])}" if v.get("runs_total") else "")
                 + (f", {bad} FAILED" if bad else ", every one rc=0") + f" ({os.path.join(out, 'logs', '_done.txt')})")
    if rows:
        c = counts(rows)
        seg = f" runs       {len(rows)} in this step: {c['cpu']} starting on CPU, {c['train']} training" + ended_txt(c)
        tgt = sum(r.get("target") or 0 for r in rows)
        if v.get("phase") == "fleet" and v.get("runs_total"):
            q = max(0, int(v["runs_total"]) - len(rows))
            seg += f"; {q} queued, of {int(v['runs_total'])}"
            tgt += q * int(v.get("windows") or 0)
        L.append(seg)
        seg = (f" windows    {v.get('total', 0):,}" + (f" / {tgt:,}" if tgt else "") + "; "
               + (f"{v['agg']:.1f} windows/s aggregate" if v.get("agg") is not None else
                  "rate not measured yet" + ("" if v.get("total") else " (a run prints its first progress line at "
                                                                      "window 101)")))
        if v.get("eta"):
            fin, waves, _q = v["eta"]
            seg += (f"; {'fleet' if v.get('phase') == 'fleet' else 'step'} ETA {eta_txt(fin)}"
                    + (f" ({waves} waves over PAR {int(v.get('par') or 0)})" if waves > 1 else ""))
        L.append(seg)
        if c["cpu"] and not c["train"] and V == "RUNNING":
            L.append("            every run of this step is still building on the CPU (corpus, tokenizer, stream, "
                     "model): the GPU reads idle until they train")
    L.append(f" GPU        {gpu() or 'no nvidia-smi on this machine'}")
    ld, (nc, how), cb = load(), cores(), v.get("cpu")
    host = f"host load {ld:.1f} (all containers)" if ld is not None else ""
    if cb:
        span = f"{cb[1]:.1f} s" if cb[1] < 10 else dur(cb[1])
        L.append(f" CPU        {cb[0]:.1f} of {nc} cores busy in this container ({how}, last {span})"
                 + (f"; {host}" if host else ""))
    else:
        L.append(f" CPU        {nc} cores ({how}); this container's use not measured" + (f"; {host}" if host else ""))
    dk = disk(out)
    L.append(f" disk       {dk:,.1f} GB free at {out}" if dk is not None else " disk       ?")
    ages = []
    if v.get("log_path"):
        ages.append(f"{os.path.basename(v['log_path'])}: last line {dur(v['log_age'])} ago")
    ages.append(f"heartbeat {dur(v['hb_age'])} ago" if v.get("hb_age") is not None else "no heartbeat yet")
    if v.get("newest"):
        ages.append(f"newest run output {dur(now - v['newest'])} ago")
    L.append(" log        " + "; ".join(ages))
    if rows:
        L.append(" " + "-" * (width - 1))
        L.append(f" {'run':<20} {'state':<26} {'windows':>15} {'w/s':>8}   started")
        shown = sorted(rows, key=lambda r: (r.get("done", False), r["tag"]))
        for r in shown[:24]:
            w, tgt = r.get("windows"), r.get("target")
            wt = ("-" if w is None else ("<101" if w == 0 and r.get("phase") == "train" else f"{w:,}")) + \
                (f"/{tgt:,}" if tgt else "")
            rt = (f"{r['rate']:.1f}" + ("~" if r.get("rate_avg") else "")) if r.get("rate") else "-"
            L.append(f" {r['tag']:<20} {r['state'][:26]:<26} {wt:>15} {rt:>8}   {hms(r.get('t0'))}")
        if len(shown) > 24:
            L.append(f" ... {len(shown) - 24} more run(s)")
        if any(r.get("rate_avg") for r in rows):
            L.append(" (~ averaged since the run began training; the rest measured over the last minutes)")
        for r in [r for r in rows if r.get("done") and r.get("rc") != 0][:3]:
            L.append(f" !! {r['tag']} rc={r['rc']}: {r.get('last', '')}")
    if v.get("procs"):
        L.append(f" processes  {len(v['procs'])} still running for it: "
                 + ", ".join(f"{p} ({k})" for p, k, _c in v["procs"][:6]))
    L.append(" " + "-" * (width - 1))
    src = v.get("log_path") or os.path.join(out, "SUMMARY.txt")
    L.append(f" last lines of {src}" + (" (heartbeats aside):" if v.get("log_path") else ":"))
    L += ["   " + x[:width - 3] for x in last_lines(src)]
    if V in ("FINISHED", "STOPPED", "DEAD") and os.path.exists(os.path.join(out, "PASTE_BACK.txt")):
        L.append(f" paste back: cat {os.path.join(out, 'PASTE_BACK.txt')}")
    L.append(f" ({hms(now)})")
    return "\n".join(L)


ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def page(v, text):
    """The --html / --serve page. ITS TEXT IS PLAIN (2026-09-27 review): a dashboard run in a terminal paints
    its frame, and html.escape kept the colour codes, so a browser showed '[1;42;97m  #####  RUNNING'."""
    V = v["verdict"]
    text = ANSI.sub("", text)
    bg = {"RUNNING": "#1b5e20", "STALLED": "#8d6e00", "FINISHED": "#0d47a1", "STOPPED": "#b71c1c",
          "DEAD": "#b71c1c", "NO FLEET": "#555555"}[V]
    return ("<!doctype html><html><head><meta charset='utf-8'>"
            f"<meta http-equiv='refresh' content='{int(EVERY)}'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            f"<title>{html.escape(V)}: {html.escape(os.path.basename(v.get('out', '')))}</title>"
            "<style>body{background:#121212;color:#e0e0e0;font:13px/1.4 ui-monospace,Menlo,Consolas,monospace;"
            "margin:16px}.v{display:inline-block;font-size:30px;font-weight:700;padding:6px 16px;"
            f"border-radius:6px;color:#fff;background:{bg}}}pre{{white-space:pre-wrap;word-break:break-word}}"
            f"</style></head><body><div class='v'>{html.escape(V)}</div><pre>{html.escape(text)}</pre>"
            "</body></html>")


def write_page(out, v, text):
    """dashboard.html, whole or not at all: a tmp file beside it, renamed over it (removed if a stop or a
    full disk interrupts the write)."""
    if not os.path.isdir(out):
        return None
    body = page(v, text)
    tmp = os.path.join(out, ".dashboard.html.tmp")
    try:
        with open(tmp, "w") as fh:
            fh.write(body)
        os.replace(tmp, os.path.join(out, "dashboard.html"))
    except OSError:
        return None
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return body


# ------------------------------------------------------------------------------------------ the modes
OUT = resolve_out(OUT_ARG)
MEM = {}

if MODE in ("once", "status"):
    v, now = collect(OUT, MEM)
    print(frame(v, now))
    sys.exit(VERDICT_RC[v["verdict"]] if MODE == "status" else 0)

if MODE == "line":
    v, now = collect(OUT, MEM)
    print(line(v, now))
    if SAMPLE:
        hist = [h for h in load_hist(OUT) if now - h[0] <= RATE_SPAN * 2]
        s = v.get("sample")
        if s:
            hist.append((s["t"], s["runs"], s["total"], s["mt"]))
        cb = v.get("cpu")
        print(json.dumps({"t": round(now, 3), "hist": [[round(t, 3), r, n, m] for t, r, n, m in hist[-HIST_MAX:]],
                          "cpu": [round(cb[2][0], 3), cb[2][1], cb[2][2]] if cb else None},
                         separators=(",", ":")))
    sys.exit(0)

PAGE = {"body": ""}


def _stop(*_a):
    raise KeyboardInterrupt


def tick():
    """One frame: read the fleet, keep the sample for the next rates, write the page (--html)."""
    v, now = collect(OUT, MEM)
    s = v.get("sample")
    if s:
        MEM["hist"] = [h for h in (MEM.get("hist") or load_hist(OUT)) if now - h[0] <= RATE_SPAN + 60]
        MEM["hist"].append((s["t"], s["runs"], s["total"], s["mt"]))
    if v.get("cpu"):
        MEM["cpu"] = v["cpu"][2]
    text = frame(v, now)
    if HTML:
        b = write_page(OUT, v, text) or page(v, text)
        PAGE["body"] = b
        text += (f"\n (writing {os.path.join(OUT, 'dashboard.html')} every {EVERY:g} s"
                 + (f"; serving it on port {SERVE}" if SERVE is not None else "") + ")")
    return text + f"\n (redrawn every {EVERY:g} s; Ctrl-C ends the dashboard, and the fleet keeps running)"


import signal                                    # noqa: E402 -- the watch loop's own
signal.signal(signal.SIGTERM, _stop)             # a TERM ends the dashboard as Ctrl-C does
try:
    text = tick()                                # the first frame exists before anything is served
    if SERVE is not None:
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        class Page(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path.split("?")[0] not in ("/", "/dashboard.html"):
                    self.send_error(404, "only the dashboard is served here")
                    return
                b = PAGE["body"].encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)

            def log_message(self, *a):
                pass

        try:
            SRV = ThreadingHTTPServer(("0.0.0.0", SERVE), Page)
        except OSError as e:
            print(f"!! --serve {SERVE}: {e}")
            sys.exit(2)
        threading.Thread(target=SRV.serve_forever, daemon=True).start()
        print(f"serving the dashboard on port {SERVE} of every address of this box (http://<its address>:{SERVE}/, "
              f"or the URL your platform maps port {SERVE} to); only the page is served", flush=True)
    while True:
        sys.stdout.write(("\033[H\033[2J" if sys.stdout.isatty() else "") + text + "\n\n")
        sys.stdout.flush()
        time.sleep(EVERY)
        text = tick()
except KeyboardInterrupt:
    print()
    sys.exit(0)
PY
