"""THE GPU FLEET SCRIPT'S READINGS, HELD TO KNOWN ANSWERS ON SYNTHETIC FLEETS (Proposal 05 §8 1.5). No
training: each check writes an output directory by hand -- run logs carrying the lines run.py prints,
loss curves, _done.txt, SUMMARY.txt, dummy checkpoints -- and runs `bash gpu_world.sh --analyze`
against it, or a whole launch whose run.py is a stand-in that answers in milliseconds.

    python3 tests/test_gpu_world.py        # exit 0 = every check passed

WHY IT EXISTS. The owner runs gpu_world.sh on a GPU box that has a checkout and no push token, and
the fleet's verdict comes back as the block the script prints between "==== PASTE THIS BACK ====" and
"==== END ====". Nothing else of a fleet reaches this repository unless the owner uploads its
archive by hand. A wrong margin, a verdict that drifts between ANALYSIS.txt and the block, a block
too long to copy, or an archive that carries checkpoints would each cost a GPU fleet to find, so each
is pinned here, on a fleet whose every number is chosen.

  F1  THE SHIP RULE: prequential bits/byte is sum(curve) x 128 / ln 2 / loop.bytes_scored; M is the
      largest |k0 - k0_nuis|; a cadence within M at every seed is NON-INFERIOR, one past it at one
      seed FAILS, and the lower mean among the non-inferior ships.
  F2  THE BLOCK: stdout carries it between the two delimiters, it equals $OUT/PASTE_BACK.txt, it holds
      the commit, the dirty flag, the card, NCPU, PAR, MPS, every arm's bits/byte at every seed, the
      margin, the DECISION with its B-provisional label and a failed run with its last log line --
      and it stays within 80 lines at 16 seeds with the cooldown arm, and at 60 seeds, where it cuts.
  F3  THE RATES are arithmetic: windows/s per arm is the mean of N / X over the seeds' '=== N windows
      ... in Xs' lines, the aggregate is every run's windows over the fleet's recorded seconds, and the
      ETA against the wall is those seconds over the ETA line's windows / rate, which past 1.5x names
      LOW-GPU-WORLD-ETA.
  F4  THE SECONDARIES tolerate absence (one 'absent' line names §8 1.3's counters and every older
      counter is still read) and read them when present: fab.blackout_windows at 45% of k1000's
      windows sounds the BLACKOUT ALARM with the COOLDOWN_ARM follow-up, and the upper bound is
      fab.shift_notifications x the cooldown / windows.
  F5  THE ARCHIVE: <name minus _out>_<launch date>.tgz beside OUT, with SUMMARY, the block, logs and
      curves, no member under ckpt/ and none ending .pt or .pt.*; tools/read_fleet_archive.sh reads it.
  F6  TODAY'S REFUSALS STAND: an act arm with no act at any seed is NO ACT FIRED and never ships; with
      no k0_nuis no cadence can ship, and the block is still written.
  F7  THE KEPT-CHECKPOINT INDEX, on torch-saved stand-ins: a copy is named for the step it holds and
      is coherent when its merge count equals its vocabulary's entries, INCOHERENT otherwise; the run's
      final save is dropped; the act windows it covers are counted off the act arms' logs.
  F8  THE WHOLE-EPOCH FLAGS: under EXP=world_epoch a run that read its epoch is not "RAN OUT OF
      STREAM" and one that hit the cap is "STOPPED AT THE WINDOW CAP"; EXP=world flags as it did.
  F9  THE REFUSALS: EXP=world_epoch without GO_WORLD_EPOCH=1 exits 2 having written nothing and prints
      its sizing and pins; an unknown EXP and an unusable cadence are refused by name.
  F10 A LAUNCH, WITH run.py STOOD IN: EXP=world with KEEP_CKPT off puts no CKPT_ variable and no
      --flush-bytes on any run and ends in the block and the archive; EXP=retok's default arms the
      k0 family's periodic saves and the act arms' final one, and a smoke whose k0 kept no copy stops
      at the kept-checkpoint tripwire -- with a block, and an archive.
  F11 EXP=world's ANALYSIS.txt of the 2026-09-24 fleet archive is byte-identical to the one the script
      wrote before §8 1.5 (be2382a).
"""
import glob
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "gpu_world.sh")
ARCHIVE_0924 = os.path.join(ROOT, "results", "gpu_world_2026-09-24", "gpu_world_2026-09-24.tgz")
LN2 = math.log(2)
CTX = 128
FAILS = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" -- {detail}" if detail else ""))
    if not ok:
        FAILS.append(name)


def clean_env(**extra):
    """A CLEAN environment, as tests/test_baseline.py builds one: a knob exported in the caller's
    shell (EXP, OUT, KEEP_CKPT, a lever) would otherwise change what is tested."""
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG")}
    env.update({"OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"})
    env.update({k: str(v) for k, v in extra.items()})
    return env


def gw(*args, timeout=300, **env):
    return subprocess.run(["bash", SCRIPT, *args], cwd=ROOT, env=clean_env(**env), capture_output=True,
                          text=True, timeout=timeout)


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)


def block_of(stdout):
    """The lines from '==== PASTE THIS BACK ====' to '==== END ====', both included."""
    ls = stdout.splitlines()
    try:
        i = ls.index("==== PASTE THIS BACK ====")
        j = ls.index("==== END ====", i)
    except ValueError:
        return None
    return ls[i:j + 1]


# ---- a synthetic fleet --------------------------------------------------------------------------
def summary(out, *, exp="retok", seeds="0 1 2", windows=20000, stream=3780000, extra="", dirty=False,
            par=12, fin_s=16560, eta=("0.3", "420,000", "461.6"), cal="461.589", kept="ON",
            levels="on (DOM_LEVELS declared, default on)", cap=60000, calw=600):
    arms = "k0 k3000 k1000 k0_nuis" if exp == "retok" else "fb_off fb_on skip world_off"
    lines = [
        f"=== gpu_world.sh  2026-10-01T12:00:00Z  commit abc1234{' (dirty)' if dirty else ''}",
        "    index, name, memory.total [MiB], memory.used [MiB]",
        "    0, NVIDIA H200, 143771 MiB, 1 MiB",
        "=== 20 CPU core(s), 1 GPU(s), device=cuda",
        "=== torch 2.4.0+cu124, CUDA 12.4",
        f"=== {windows} windows per run, DATA_STREAM_BYTES={stream}, seeds: {seeds}, EXTRA='{extra}'",
        f"=== plan: EXP={exp}; arms {arms}, plus k0_rerun at seed 0; window cap {cap}; CAL_WINDOWS {calw}; "
        f"LM_CTX {CTX}",
        f"=== kept checkpoints: {kept}, k0 family CKPT_EVERY=1000, act arms final only; k0's saves "
        f"hard-linked under {out}/ckpt/keep",
        "=== pins: none",
        f"=== DOM Levels: {levels}",
        "",
        "=== CUDA MPS started (kernels from different runs execute concurrently)",
        f"=== calibration: PAR={par} (aggregate {cal} windows/s; the smallest k within 10% of the best measured)",
        f"=== 13 run(s), {par} at a time",
        f"=== ETA: about {eta[0]} h for {eta[1]} windows at {eta[2]} windows/s aggregate",
        "---- 2. fleet started 12:10:00Z",
        f"---- fleet finished in {fin_s // 60} min ({fin_s} s)",
    ]
    write(os.path.join(out, "SUMMARY.txt"), "\n".join(lines) + "\n")


def curve_for(bpb, n, nbytes):
    """A curve of n equal per-flush losses whose prequential bits/byte is bpb (to float rounding)."""
    return [bpb * LN2 * nbytes / (CTX * n)] * n


def preq(curve, nbytes):
    return sum(curve) * CTX / LN2 / nbytes


def run(out, name, seed, bpb, *, n=100, nbytes=18900, secs=10.0, win=None, acts=None, at=(),
        counters=None, stopped=False, rc=0, last=None, curve=True, fbytes=None, tail=True, losses=None):
    """One run's log, curve and _done.txt line. Returns the curve written (None without one)."""
    tag = f"{name}.s{seed}"
    win = n if win is None else win
    c = curve_for(bpb, n, nbytes) if (curve and bpb is not None) else None
    c = list(losses) if losses is not None else c
    L = ["=== device=cuda amp=off tf32=(True, True) torch_seed=1"]
    if rc == 0:
        L.append(f"=== {win} windows, {win} flushes, {win} optimizer steps, 1 epoch(s) in {secs}s "
                 f"({win / secs:.1f} w/s)")
    for w in at:
        L.append(f"WARNING: loop: mid-epoch act at window {w}: re-segmented the unconsumed tail at vocabulary "
                 f"size 600 (500000 -> 490000 ids; this epoch now holds 19000 windows, {w} read)."
                 + (" Tail bytes/token 1.5000 -> 1.5450 (+3.0%), +2.0% against the build-time 1.5150 SIG's "
                    "width was derived from." if tail else ""))
    if stopped:
        L.append(f"WARNING: loop: stopped at max_windows={win} window(s) trained by THIS process")
    L.append("=== R STAGE -- the did-it-fire surfaces:")
    cc = {"loop.bytes_scored": nbytes, "tok.mint": 594}
    if acts is not None:
        cc.update({"loop.acts": acts, "loop.acts_noop": 0})
    cc.update(counters or {})
    for k, v in cc.items():
        L.append(f"       {k:<44} {v}")
    L.append("       gate:fab.growth_blackout                     ('armed-but-zero', \"'3 notification(s)' vs "
             "'cooldown=400 windows'\")")
    if last:
        L.append(last)
    write(os.path.join(out, "logs", tag + ".log"), "\n".join(L) + "\n")
    if c is not None:
        write(os.path.join(out, "curves", tag + ".json"), json.dumps(c))
    if fbytes is not None:
        write(os.path.join(out, "curves", tag + ".bytes.json"), json.dumps(fbytes))
    with open(os.path.join(out, "logs", "_done.txt"), "a") as fh:
        fh.write(f"{tag} rc={rc} secs={int(secs) + 5}\n")
    return c


OLD13 = {"fab.grown_regression": 2, "fab.grown_stall": 0, "fab.births": 299,
         "fab.growth_blackout_suppressed.regression": 2, "fab.growth_blackout_suppressed.stall": 0,
         "fab.shift_notifications": 3, "store.n_remap_events": 3, "store.n_remapped_entries": 3000,
         "store.n_opened": 8192, "tok.retok_noop": 0}


def retok_fleet(out, *, seeds=(0, 1), k3000=None, k1000=None, nuis=True, cd=False, **kw):
    """k0 at 1.0, k0_nuis at 1.0001 (so M = 0.0001), k3000 and k1000 at the given per-seed values."""
    summary(out, seeds=" ".join(map(str, seeds)), **kw)
    for s in seeds:
        run(out, "k0", s, 1.0, secs=10.0 + s)
        if nuis:
            run(out, "k0_nuis", s, 1.0001, secs=10.0)
        run(out, "k3000", s, (k3000 or {}).get(s, 0.9998), acts=6, at=(3001,), counters=OLD13, secs=10.0)
        run(out, "k1000", s, (k1000 or {}).get(s, 1.00005), acts=19, at=(1001, 2001), counters=OLD13,
            secs=10.0)
        if cd:
            run(out, "k1000_cd100", s, 1.00002, acts=19, at=(1001, 2001), counters=OLD13, secs=10.0)
    run(out, "k0_rerun", 0, 1.0, secs=10.0)


TMP = tempfile.mkdtemp(prefix="test_gpu_world_")
try:
    # ---- F1: the ship rule, to the known answer -------------------------------------------------
    o1 = os.path.join(TMP, "f1", "gpu_retok_out")
    retok_fleet(o1, k1000={0: 1.00005, 1: 1.0003})
    p = gw("--analyze", EXP="retok", OUT=o1)
    a1 = open(os.path.join(o1, "ANALYSIS.txt")).read() if os.path.exists(os.path.join(o1, "ANALYSIS.txt")) else ""
    k0c = json.load(open(os.path.join(o1, "curves", "k0.s0.json")))
    want = round(preq(k0c, 18900), 5)
    check("F1 --analyze exits 0 on a synthetic retok fleet", p.returncode == 0, p.stderr[-600:])
    check("F1 bits/byte is sum(curve) x 128 / ln 2 / loop.bytes_scored, as printed on the RUNS line",
          re.search(rf"k0\s+s0\s+100 flushes .*preq {re.escape(str(want))}\b", a1) is not None, f"want {want}")
    check("F1 M is the largest |k0 - k0_nuis| (0.0001)",
          "=== MARGIN M = max over 2 seed(s) |k0 - k0_nuis| = 0.00010 bits/byte ===" in a1)
    check("F1 k3000 at -0.0002 every seed is NON-INFERIOR at every seed",
          re.search(r"k3000\s+- k0 per seed: s0 -0\.00020\s+s1 -0\.00020 .*NON-INFERIOR at every seed", a1) is not None)
    check("F1 k1000 at +0.0003 at s1 FAILS the margin",
          re.search(r"k1000\s+- k0 per seed: s0 \+0\.00005\s+s1 \+0\.00030 .*FAILS the margin", a1) is not None)
    check("F1 the lower mean among the non-inferior ships: TOK_RETOK_EVERY ships 3000",
          "=== DECISION: TOK_RETOK_EVERY ships 3000 (lowest mean among the non-inferior; negative = the act "
          "helps) ===" in a1)

    # ---- F2: the block --------------------------------------------------------------------------
    b1 = block_of(p.stdout)
    pb1 = open(os.path.join(o1, "PASTE_BACK.txt")).read().splitlines()
    check("F2 stdout carries one delimited block, equal to $OUT/PASTE_BACK.txt, within 80 lines",
          b1 is not None and b1 == pb1 and len(b1) <= 80, f"{len(b1 or [])} lines")
    o2 = os.path.join(TMP, "f2", "gpu_retok_out")
    seeds16 = tuple(range(16))
    retok_fleet(o2, seeds=seeds16, cd=True, dirty=True)
    os.remove(os.path.join(o2, "curves", "k0_rerun.s0.json"))
    run(o2, "k0_rerun", 0, None, rc=1, last="RuntimeError: boom at window 1234", curve=False)
    p2 = gw("--analyze", EXP="retok", OUT=o2)
    b2 = block_of(p2.stdout) or []
    t2 = "\n".join(b2)
    rows = {int(m.group(1)): m.group(0) for m in re.finditer(r"^  s(\d+) .*$", t2, re.M)}
    bpbs_ok = all(
        f"{preq(json.load(open(os.path.join(o2, 'curves', f'{a}.s{s}.json'))), 18900):.5f}" in rows.get(s, "")
        for s in seeds16 for a in ("k0", "k3000", "k1000", "k1000_cd100", "k0_nuis"))
    check("F2 at 16 seeds with the cooldown arm the block stays within 80 lines and equals the file",
          p2.returncode == 0 and 0 < len(b2) <= 80
          and b2 == open(os.path.join(o2, "PASTE_BACK.txt")).read().splitlines(), f"{len(b2)} lines")
    check("F2 the block holds every arm's bits/byte at every seed", bpbs_ok and len(rows) == 16,
          f"{len(rows)} seed rows")
    check("F2 the block holds the commit, the dirty flag, the card, NCPU, PAR and MPS",
          all(x in t2 for x in ("commit abc1234", "DIRTY", "NVIDIA H200", "NCPU 20", "PAR 12", "MPS on")))
    check("F2 the block holds the margin and the DECISION with its B-provisional label",
          "MARGIN M = 0.00010" in t2 and re.search(r"^DECISION: .*\[B-provisional\]$", t2, re.M) is not None)
    check("F2 the block names a failed run with its last log line",
          "FAILED k0_rerun.s0 rc=1: RuntimeError: boom at window 1234" in t2)
    check("F2 the cooldown arm is reported beside the rule, never as a ship candidate",
          "(beside the rule)" in t2 and "ships 1000_cd100" not in t2)
    o2b = os.path.join(TMP, "f2b", "gpu_retok_out")
    retok_fleet(o2b, seeds=tuple(range(60)), cd=True)
    p2b = gw("--analyze", EXP="retok", OUT=o2b)
    b2b = block_of(p2b.stdout) or []
    check("F2 at 60 seeds the block is cut to 80 lines, says what it cut, and still ends in the archive "
          "line and END", p2b.returncode == 0 and len(b2b) == 80 and "cut to fit 80 lines" in "\n".join(b2b)
          and b2b[-2].startswith("archive: ") and b2b[-1] == "==== END ====", f"{len(b2b)} lines")

    # ---- F3: the rates --------------------------------------------------------------------------
    # k0: 100 windows in 10 s (s0) and 11 s (s1); every run's windows are 100; 9 runs; 16560 s of wall.
    wps = [100 / 10.0, 100 / 11.0]
    tw = 100 * 9
    est = 420000 / 461.6
    check("F3 per-arm windows/s is the mean of N / X over the seeds, with its range",
          f"k0           windows/s {sum(wps) / 2:.2f} [{min(wps):.2f}-{max(wps):.2f}]" in a1)
    check("F3 the aggregate is every run's windows over the fleet's recorded seconds",
          f"aggregate: {tw:,} windows in 16560 s of fleet wall at PAR 12 = {tw / 16560:.2f} windows/s" in a1)
    check("F3 the ETA against the wall is the recorded seconds over the ETA line's windows / rate",
          f"estimated {est:.0f} s (420,000 windows at 461.6 windows/s), took 16560 s: {16560 / est:.2f}x" in a1)
    check("F3 past 1.5x the LOW-GPU-WORLD-ETA line names the CAL_WINDOWS default to raise",
          "LOW-GPU-WORLD-ETA: the ETA missed the wall by" in a1 and "CAL_WINDOWS to >= 520" in a1)
    o3 = os.path.join(TMP, "f3", "gpu_retok_out")
    retok_fleet(o3, fin_s=1200)
    a3 = (gw("--analyze", EXP="retok", OUT=o3), open(os.path.join(o3, "ANALYSIS.txt")).read())[1]
    check("F3 within 1.5x there is no LOW-GPU-WORLD-ETA line", f"took 1200 s: {1200 / est:.2f}x" in a3
          and "LOW-GPU-WORLD-ETA" not in a3)

    # ---- F4: the secondaries --------------------------------------------------------------------
    check("F4 without §8 1.3's counters one line says so, naming each",
          "absent (§8 1.3 not in this tree): fab.blackout_windows, tok.mint_wait_windows, loop.act_seconds, "
          "tok.bpt_tail, per-flush bytes (run.py --flush-bytes)" in a1)
    check("F4 ... and every older counter is still read (acts, growth, births, blackout-suppressed passes, "
          "the replay record, the tail bytes/token per act)",
          re.search(r"k1000\s+acts 19 \(noop 0, tok\.retok_noop 0\), replay record 20 event\(s\); FAB grown "
                    r"regression 2 / stall 0, births 299, blackout-suppressed regression 2 / stall 0", a1) is not None
          and "bytes/token rise per act (the tail's, before -> after): +3.0% +3.0%" in a1)
    check("F4 the upper bound is fab.shift_notifications x cooldown / windows (3 x 400 / 100, capped at the "
          "whole run)", "fab.shift_notifications x cooldown 400 / windows = 100.0%" in a1)
    check("F4 MEM's re-cut share is store.n_remapped_entries / n_remap_events / n_opened (1000 / 8192)",
          f"MEM re-cut {100 * 1000 / 8192:.1f}% of the store's slots per act" in a1)
    o4 = os.path.join(TMP, "f4", "gpu_retok_out")
    summary(o4, seeds="0", windows=1000, stream=189000)
    # FOUR EQUAL QUARTERS OF 189,000 BYTES, TEN FLUSHES OF 18,900: the flushes opening at bytes 0, 18900
    # and 37800 are phase 0 (< 47250), 56700 and 75600 phase 1, 94500 to 132300 phase 2 (94500 is the
    # bound, so it opens phase 2), 151200 and 170100 phase 3. Each phase's flushes carry the loss of
    # 1, 2, 3 and 4 bits per byte, so a flush placed in the wrong phase moves a reading off its integer.
    _ph = [0, 0, 0, 1, 1, 2, 2, 2, 3, 3]
    run(o4, "k0", 0, 1.0, n=10, win=1000, nbytes=189000, fbytes=[18900] * 10,
        losses=[(k + 1) * LN2 * 18900 / CTX for k in _ph],
        counters={"fab.blackout_windows": 0, "fab.shift_notifications": 0})
    run(o4, "k0_nuis", 0, 1.0001, n=10, win=1000, nbytes=189000, fbytes=[18900] * 10)
    new13 = dict(OLD13, **{"fab.shift_notifications": 1, "tok.mint_wait_windows": 800, "tok.mint_waited": 40,
                           "loop.act_seconds": 1.5, "loop.act_remap_seconds": 0.5, "tok.bpt_tail": 1.6})
    run(o4, "k1000", 0, 1.00005, n=10, win=1000, nbytes=189000, secs=100.0, acts=1, at=(1001,),
        fbytes=[18900] * 10, counters=dict(new13, **{"fab.blackout_windows": 450}))
    run(o4, "k3000", 0, 0.9999, n=10, win=1000, nbytes=189000, secs=100.0, acts=1, at=(3001,),
        fbytes=[18900] * 10, counters=dict(new13, **{"fab.blackout_windows": 100}))
    p4 = gw("--analyze", EXP="retok", OUT=o4)
    a4 = open(os.path.join(o4, "ANALYSIS.txt")).read()
    b4 = "\n".join(block_of(p4.stdout) or [])
    check("F4 with fab.blackout_windows at 45% of k1000's windows the BLACKOUT ALARM sounds with the "
          "COOLDOWN_ARM follow-up, in ANALYSIS and in the block",
          "BLACKOUT ALARM (C13): k1000 blacks out 45.0% of its windows, above 20%: re-run with "
          "COOLDOWN_ARM=100 (adds k1000_cd100" in a4 and "BLACKOUT ALARM (C13): k1000" in b4
          and "BLACKOUT ALARM (C13): k3000" not in a4)
    check("F4 the upper bound beside it is 1 x 400 / 1000 = 40.0%",
          "fab.shift_notifications x cooldown 400 / windows = 40.0%" in a4)
    check("F4 §8 1.3's readings are read when present (mint wait 800 / 40, act 1.5 s of 100 s, "
          "tok.bpt_tail) and no 'absent' line prints",
          "mint wait 20.0 windows x 40 id(s); act 1.50% of loop time (MEM re-cut 0.50%)" in a4
          and "tok.bpt_tail 1.6000" in a4 and "absent (§8 1.3" not in a4)
    check("F4 bits/byte by phase splits the run at the stream's quarter points off the per-flush bytes "
          "(1, 2, 3 and 4 bits/byte by construction)",
          re.search(r"k0\s+bits/byte by phase: 1\.0000 2\.0000 3\.0000 4\.0000", a4) is not None,
          str([l for l in a4.splitlines() if "by phase" in l]))

    # ---- F5: the archive ------------------------------------------------------------------------
    for f in ("ckpt/k0.s0/ckpt.pt", "ckpt/k0.s0/ckpt.pt.prev", "ckpt/k0.s0.dyntok.json", "smoke/ckpt/x/ckpt.pt",
              "stray.pt", "curves/stray.pt.tmp"):
        write(os.path.join(o1, f), "not a checkpoint")
    p5 = gw("--analyze", EXP="retok", OUT=o1)
    tgz = os.path.join(os.path.dirname(o1), "gpu_retok_2026-10-01.tgz")
    names = tarfile.open(tgz).getnames() if os.path.exists(tgz) else []
    check("F5 the archive is <name minus _out>_<launch date>.tgz beside OUT, and the run says so",
          os.path.exists(tgz) and f"=== packed {tgz}" in p5.stdout, os.path.basename(tgz))
    check("F5 it holds SUMMARY, the block, ANALYSIS, the logs and the curves",
          all(f"gpu_retok_out/{x}" in names for x in ("SUMMARY.txt", "PASTE_BACK.txt", "ANALYSIS.txt",
                                                      "logs/k0.s0.log", "curves/k0.s0.json")))
    check("F5 ... and no member under ckpt/ nor ending .pt or .pt.*",
          names and not [n for n in names if "/ckpt" in n or n.endswith(".pt") or ".pt." in n],
          str([n for n in names if "/ckpt" in n or ".pt" in n]))
    rfa = subprocess.run(["bash", os.path.join(ROOT, "tools", "read_fleet_archive.sh"), tgz], cwd=TMP,
                         env=clean_env(), capture_output=True, text=True, timeout=120)
    check("F5 tools/read_fleet_archive.sh reads it", rfa.returncode == 0 and "==== PASTE THIS BACK ====" in rfa.stdout
          and "(9 run logs)" in rfa.stdout, rfa.stderr[-300:])

    # ---- F6: today's refusals stand ---------------------------------------------------------------
    o6 = os.path.join(TMP, "f6", "gpu_retok_out")
    summary(o6, seeds="0 1")
    for s in (0, 1):
        run(o6, "k0", s, 1.0)
        run(o6, "k0_nuis", s, 1.0001)
        run(o6, "k3000", s, 0.9, acts=0)
        run(o6, "k1000", s, 0.9998, acts=4, at=(1001,))
    p6 = gw("--analyze", EXP="retok", OUT=o6)
    a6 = open(os.path.join(o6, "ANALYSIS.txt")).read()
    check("F6 an act arm with no act at any seed is NO ACT FIRED and never ships (a lower reading does not "
          "make it a candidate)", "k3000  NO ACT FIRED at any seed" in a6
          and "=== DECISION: TOK_RETOK_EVERY ships 1000" in a6)
    o6b = os.path.join(TMP, "f6b", "gpu_retok_out")
    retok_fleet(o6b, nuis=False)
    p6b = gw("--analyze", EXP="retok", OUT=o6b)
    a6b = open(os.path.join(o6b, "ANALYSIS.txt")).read()
    check("F6 with no k0_nuis no cadence can ship, the later sections still print, and the block is written",
          p6b.returncode == 0 and "!! no paired k0 / k0_nuis seeds: the margin cannot be formed and no cadence "
          "can ship" in a6b and "=== DECISION" not in a6b and "=== RATES" in a6b
          and os.path.exists(os.path.join(o6b, "PASTE_BACK.txt"))
          and "DECISION: none -- no paired k0 / k0_nuis seeds" in open(os.path.join(o6b, "PASTE_BACK.txt")).read())

    # ---- F7: the kept-checkpoint index, on torch-saved stand-ins ---------------------------------
    import torch
    o7 = os.path.join(TMP, "f7", "gpu_retok_out")
    retok_fleet(o7, seeds=(0,))
    shutil.rmtree(os.path.join(o7, "logs"))
    os.makedirs(os.path.join(o7, "logs"))
    run(o7, "k0", 0, 1.0)
    run(o7, "k0_nuis", 0, 1.0001)
    run(o7, "k1000", 0, 1.00005, acts=2, at=(1001, 3001))
    kd = os.path.join(o7, "ckpt", "keep")
    for i, (step, reason, mc, ent) in enumerate(((1001, "periodic", 3, 3), (2001, "periodic", 4, 3),
                                                  (3050, "final", 5, 5)), 1):
        d = os.path.join(kd, f"k0.s0.save{i:03d}")
        os.makedirs(d)
        torch.save({"step": step, "epoch": 0, "reason": reason, "payload": {"TOK": {"merge_count": mc}}},
                   os.path.join(d, "ckpt.pt"))
        write(d + ".dyntok.json", json.dumps({"entries": [[0, 1]] * ent}))
    p7 = gw("--analyze", EXP="retok", OUT=o7)
    kept = open(os.path.join(kd, "k0.s0.kept.txt")).read() if os.path.exists(os.path.join(kd, "k0.s0.kept.txt")) else ""
    check("F7 a copy is named for the step it holds and is coherent when merges equal the vocabulary's entries",
          os.path.isfile(os.path.join(kd, "k0.s0.w1001", "ckpt.pt"))
          and os.path.isfile(os.path.join(kd, "k0.s0.w1001.dyntok.json"))
          and "k0.s0.w1001 step=1001 reason=periodic merges=3 entries=3 coherent" in kept)
    check("F7 a copy whose merge count disagrees with its vocabulary is kept and flagged INCOHERENT",
          "k0.s0.w2001 step=2001 reason=periodic merges=4 entries=3 INCOHERENT" in kept)
    check("F7 the run's final save is dropped (the ring keeps it), and no saveNNN is left",
          not glob.glob(os.path.join(kd, "k0.s0.save*")) and not os.path.exists(os.path.join(kd, "k0.s0.w3050")))
    a7 = open(os.path.join(o7, "ANALYSIS.txt")).read()
    check("F7 the act-window coverage counts w1001 against k1000's act at window 1001 (and misses 3001)",
          "k0.s0: 2 kept, w1001-w2001, INCOHERENT at w2001; act windows covered: k1000 1/2" in a7)
    check("F7 KEPT.txt gathers the index into the archive's reach",
          open(os.path.join(o7, "KEPT.txt")).read() == kept)
    check("F7 the kept files are read-only", not (os.stat(os.path.join(kd, "k0.s0.w1001", "ckpt.pt")).st_mode & 0o222))

    # ---- F8: the whole-epoch flags --------------------------------------------------------------
    for exp in ("world_epoch", "world"):
        o8 = os.path.join(TMP, "f8_" + exp, "gpu_out")
        summary(o8, exp=exp, seeds="0")
        for a in ("fb_off", "fb_on", "skip", "world_off"):
            run(o8, a, 0, 1.0, stopped=(a == "skip"))
        p8 = gw("--analyze", EXP=exp, OUT=o8)
        a8 = open(os.path.join(o8, "ANALYSIS.txt")).read() if os.path.exists(os.path.join(o8, "ANALYSIS.txt")) else ""
        rowf = {m.group(1): m.group(0) for m in re.finditer(r"^  (\w+)\s+s0 .*$", a8, re.M)}
        if exp == "world_epoch":
            check("F8 EXP=world_epoch: a run that read its epoch is not RAN OUT OF STREAM, one that hit the cap is "
                  "STOPPED AT THE WINDOW CAP, and the rule is labelled as shown for continuity",
                  p8.returncode == 0 and "RAN OUT OF STREAM" not in a8
                  and "STOPPED AT THE WINDOW CAP: did not read the whole epoch" in rowf.get("skip", "")
                  and "STOPPED AT THE WINDOW CAP" not in rowf.get("fb_off", "x")
                  and "Q-WORLD-10's rule, shown for continuity" in a8)
        else:
            check("F8 EXP=world flags as before: a run that did not stop at the cap RAN OUT OF STREAM, and no "
                  "whole-epoch wording appears",
                  p8.returncode == 0 and "RAN OUT OF STREAM (raise BYTES)" in rowf.get("fb_off", "")
                  and "RAN OUT OF STREAM" not in rowf.get("skip", "x") and "WINDOW CAP" not in a8
                  and "shown for continuity" not in a8)
            check("F8 EXP=world ends in its block too, capped at 80 lines",
                  0 < len(block_of(p8.stdout) or []) <= 80 and "=== DECISION (Q-WORLD-10's rule) ===" in p8.stdout)

    # ---- F9: the refusals -----------------------------------------------------------------------
    o9 = os.path.join(TMP, "f9", "gpu_world_epoch_out")
    p9 = gw(EXP="world_epoch", OUT=o9, WINDOWS=20000)
    check("F9 EXP=world_epoch without GO_WORLD_EPOCH=1 exits 2 and writes nothing (OUT is not created)",
          p9.returncode == 2 and not os.path.exists(o9), f"rc {p9.returncode}")
    check("F9 ... having printed its sizing: one whole WINDOWS x 189-byte epoch, the cap at 3 x WINDOWS, "
          "CAL_WINDOWS 600, and the TOK_RETOK_EVERY pin",
          "DATA_STREAM_BYTES=3780000" in p9.stdout and "window cap 60000" in p9.stdout
          and "CAL_WINDOWS 600" in p9.stdout and "TOK_RETOK_EVERY=3000 pinned" in p9.stdout
          and "DATA_DRAW=planned pinned" in p9.stdout)
    p9b = gw(EXP="wrold", OUT=os.path.join(TMP, "f9b"))
    check("F9 an unknown EXP is refused by name, before anything is written",
          p9b.returncode == 2 and "EXP='wrold'" in p9b.stdout and not os.path.exists(os.path.join(TMP, "f9b")))
    p9c = gw(EXP="retok", RETOK_ARMS="3000 x1", OUT=os.path.join(TMP, "f9c"))
    check("F9 a cadence that is not a positive count is refused by name, before anything is written",
          p9c.returncode == 2 and "'x1'" in p9c.stdout and not os.path.exists(os.path.join(TMP, "f9c")))
    p9d = gw(EXP="retok", COOLDOWN_ARM="lots", OUT=os.path.join(TMP, "f9d"))
    check("F9 a cooldown that is not a window count is refused by name",
          p9d.returncode == 2 and "COOLDOWN_ARM='lots'" in p9d.stdout)

    # ---- F10: a launch, with run.py stood in ------------------------------------------------------
    # A python3 on PATH that hands `python3 run.py ...` to a stand-in and everything else to this
    # interpreter. The stand-in records each run's CKPT_ settings and argv, and prints what the
    # smoke's tripwires read (the WORLD arms' forecast counters) and the analysis reads.
    binp = os.path.join(TMP, "bin")
    stub = os.path.join(TMP, "fake_run.py")
    write(os.path.join(binp, "python3"),
          f'#!/bin/bash\nif [[ "${{1:-}}" == run.py ]]; then shift; exec "{sys.executable}" "{stub}" "$@"; fi\n'
          f'exec "{sys.executable}" "$@"\n')
    os.chmod(os.path.join(binp, "python3"), 0o755)
    write(stub, r'''import json, os, sys
a = sys.argv[1:]
w = int(a[a.index("--max-windows") + 1]); curve = a[a.index("--loss-curve") + 1]
tag = os.path.basename(curve)[:-5]
with open(os.environ["STUB_BOOK"], "a") as fh:
    fh.write(json.dumps({"tag": tag, "argv": a, "ckpt": {k: v for k, v in os.environ.items() if k.startswith("CKPT_")},
                         "retok": os.environ.get("TOK_RETOK_EVERY")}) + "\n")
n = min(w, 50)
json.dump([2.0] * n, open(curve, "w"))
if "--flush-bytes" in a:
    json.dump([189] * n, open(a[a.index("--flush-bytes") + 1], "w"))
print("=== device=cpu amp=off")
print(f"=== {n} windows, {n} flushes, {n} optimizer steps, 1 epoch(s) in 1.0s ({n} w/s)")
if n == w:
    print(f"WARNING: loop: stopped at max_windows={w} window(s) trained by THIS process")
print(f"       loop.bytes_scored                            {189 * n}")
if os.environ.get("WORLD_ENABLED") == "0":
    print("       world.built                                  null")
elif os.environ.get("WORLD_FEEDBACK") == "1":
    print("       world.forecasts                              7")
    print("       lm.encode.extra_applied                      7")
''')
    o10 = os.path.join(TMP, "f10", "gpu_world_out")
    book = os.path.join(TMP, "f10_book.jsonl")
    env10 = {"PATH": binp + os.pathsep + os.environ.get("PATH", ""), "STUB_BOOK": book}
    p10 = subprocess.run(["bash", SCRIPT], cwd=ROOT, capture_output=True, text=True, timeout=300,
                         env=clean_env(**env10, DEVICE="cpu", WINDOWS=20, SEEDS="0", PAR=1, SMOKE_WINDOWS=5,
                                       OUT=o10))
    recs = [json.loads(l) for l in open(book)] if os.path.exists(book) else []
    check("F10 EXP=world with KEEP_CKPT off: every run -- smoke, fleet and rerun -- carries no CKPT_ variable "
          "and no --flush-bytes, and no ckpt/ directory appears",
          p10.returncode == 0 and len(recs) == 9 and all(not r["ckpt"] for r in recs)
          and all("--flush-bytes" not in r["argv"] for r in recs) and not os.path.exists(os.path.join(o10, "ckpt")),
          f"rc {p10.returncode}; {len(recs)} run(s); {[r['ckpt'] for r in recs if r['ckpt']][:2]}; "
          f"{p10.stderr[-600:]}")
    b10 = block_of(p10.stdout) or []
    check("F10 ... and the launch ends in its block (equal to the file) and its archive",
          0 < len(b10) <= 80 and b10 == open(os.path.join(o10, "PASTE_BACK.txt")).read().splitlines()
          and glob.glob(os.path.join(os.path.dirname(o10), "gpu_world_*.tgz"))
          and "=== kept checkpoints: OFF" in open(os.path.join(o10, "SUMMARY.txt")).read())
    o10b = os.path.join(TMP, "f10b", "gpu_retok_out")
    book_b = os.path.join(TMP, "f10b_book.jsonl")
    p10b = subprocess.run(["bash", SCRIPT], cwd=ROOT, capture_output=True, text=True, timeout=300,
                          env=clean_env(PATH=env10["PATH"], STUB_BOOK=book_b, EXP="retok", DEVICE="cpu",
                                        WINDOWS=20, SEEDS="0", PAR=1, SMOKE_WINDOWS=10, OUT=o10b))
    rb = {r["tag"]: r for r in (json.loads(l) for l in open(book_b))} if os.path.exists(book_b) else {}
    sm = os.path.join(o10b, "smoke", "ckpt")
    check("F10 EXP=retok arms the kept checkpoints by default: the smoke's k0 family saves at "
          "SMOKE_WINDOWS/2, its act arms at the end only, each in its own CKPT_DIR, with --flush-bytes",
          rb.get("k0.s0", {}).get("ckpt") == {"CKPT_DIR": f"{sm}/k0.s0", "CKPT_EVERY": "5"}
          and rb.get("k0_nuis.s0", {}).get("ckpt") == {"CKPT_DIR": f"{sm}/k0_nuis.s0", "CKPT_EVERY": "5"}
          and rb.get("k3000.s0", {}).get("ckpt") == {"CKPT_DIR": f"{sm}/k3000.s0", "CKPT_EVERY": "0"}
          and rb.get("k1000.s0", {}).get("retok") == "1000" and "--flush-bytes" in rb.get("k0.s0", {}).get("argv", []),
          str({k: v.get("ckpt") for k, v in rb.items()}))
    b10b = "\n".join(block_of(p10b.stdout) or [])
    check("F10 a smoke whose k0 kept no copy stops at the kept-checkpoint tripwire (exit 1, no fleet run) -- "
          "and still ends in a block and an archive",
          p10b.returncode == 1 and "STOPPED BEFORE THE ANALYSIS: the kept-checkpoint tripwire" in b10b
          and b10b == open(os.path.join(o10b, "PASTE_BACK.txt")).read().rstrip("\n")
          and not os.path.exists(os.path.join(o10b, "logs", "_done.txt"))
          and glob.glob(os.path.join(os.path.dirname(o10b), "gpu_retok_*.tgz")),
          f"rc {p10b.returncode}; {p10b.stderr[-400:]}")

    # ---- F11: EXP=world's analysis of the 2026-09-24 archive is unchanged -------------------------
    old = subprocess.run(["git", "show", "be2382a:gpu_world.sh"], cwd=ROOT, capture_output=True, text=True)
    if old.returncode != 0 or not os.path.exists(ARCHIVE_0924):
        print("SKIP F11 -- needs git history (be2382a) and results/gpu_world_2026-09-24/'s archive")
    else:
        outs = []
        for side in ("old", "new"):
            d = os.path.join(TMP, "f11_" + side)
            os.makedirs(d)
            with tarfile.open(ARCHIVE_0924) as tf:
                tf.extractall(d)
            if side == "old":
                write(os.path.join(d, "old.sh"), old.stdout)
                sh = os.path.join(d, "old.sh")
            else:
                sh = SCRIPT
            subprocess.run(["bash", sh, "--analyze"], cwd=ROOT, capture_output=True, text=True, timeout=300,
                           env=clean_env(OUT=os.path.join(d, "gpu_world_out")))
            outs.append(open(os.path.join(d, "gpu_world_out", "ANALYSIS.txt"), "rb").read())
        check("F11 EXP=world's ANALYSIS.txt of the 2026-09-24 fleet is byte-identical to be2382a's",
              outs[0] == outs[1] and len(outs[0]) > 1000, f"{len(outs[0])} vs {len(outs[1])} bytes")
finally:
    shutil.rmtree(TMP, ignore_errors=True)

print(f"\n=== {len(FAILS)} failing ===")
sys.exit(1 if FAILS else 0)
