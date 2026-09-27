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

  F1  THE SHIP RULE: prequential bits/byte is sum(curve) x 128 / ln 2 / loop.bytes_scored; without
      per-flush bytes the eps rule reads the whole run as one phase and says so; M, the largest
      |k0 - k0_nuis|, is reported and decides nothing; two harmless cadences PASS, and 3000 stays
      because 1000 is not significantly better (O14, 2026-09-27: it was 03b's per-seed margin rule).
  F2  THE BLOCK: stdout carries it between the two delimiters, it equals $OUT/PASTE_BACK.txt, it holds
      the commit, the dirty flag, the card, NCPU, PAR, MPS, every arm's bits/byte at every seed, the
      rule's rows, M, the DECISION with its B-provisional label and a failed run with its last log
      line -- and it stays within 80 lines at 16 seeds with the cooldown arm, and at 60 and 72 seeds,
      where it cuts: the per-seed rows are condensed to the flagged ones (setting M, a cadence's
      largest difference), and the rule, M, the DECISION and the alarms survive (build 1.5's review:
      they were truncated from the end).
  F3  THE RATES are arithmetic: windows/s per arm is the mean of N / X over the seeds' '=== N windows
      ... in Xs' lines, the aggregate is every run's windows over the fleet's recorded seconds, and the
      ETA against the wall is those seconds over the ETA line's windows / rate, which past 1.5x names
      LOW-GPU-WORLD-ETA.
  F4  THE SECONDARIES tolerate absence (one 'absent' line names §8 1.3's counters and every older
      counter is still read) and read them when present: fab.blackout_windows at 45% of k1000's
      windows sounds the BLACKOUT ALARM with the COOLDOWN_ARM follow-up, and the upper bound is
      fab.shift_notifications x the cooldown / windows. "Not in this tree" is read off the tree record
      SUMMARY.txt carries; a key the tree has and no log printed is "unreachable in these runs", and a
      SUMMARY.txt without the record says it cannot tell the two apart (build 1.5's review). The act
      arms' rates carry the act's own share of loop time and qualify their distance from a saving k0.
  F5  THE ARCHIVE: <name minus _out>_<launch date>.tgz beside OUT, with SUMMARY, the block, logs and
      curves, no member under ckpt/ and none ending .pt or .pt.*; tools/read_fleet_archive.sh reads it,
      and its pool rows (O20, NEW-20) read a synthetic fleet to the known answer: the fill window, the
      windows from it to the end and their share, the lines at FAB_SLOTS (off the gate text over a
      stray FAB_SLOTS= and EXTRA, off a FAB_SLOTS= in the log over EXTRA, off EXTRA, else 4096
      labelled assumed), the drops from within 2% of it on the lines after the passes as a lower bound
      per pass beside merged + culled (a dip from below the band not counted, the band's edge pinned),
      and the pooled line without the *_rerun replicate; the rows add one line per run and the pooled
      line to the block, nothing else.
  F6  AN ACT ARM WITH NO ACT AT ANY SEED is NO ACT FIRED and never ships, and an incumbent that did not
      act is not read, so it stays; with no k0_nuis, M is not formed and still decides nothing, the
      DECISION reads, and the block is written.
  F7  THE KEPT-CHECKPOINT INDEX, on torch-saved stand-ins: a copy is named for the step it holds and
      is coherent when its merge count equals its vocabulary's entries, INCOHERENT otherwise; the run's
      final save is dropped; the act windows it covers are counted off the act arms' logs; the resume
      line carries the run's seed, device and stream. A keep directory stamped by another launch is
      refused, with nothing indexed and nothing dropped, and the block says so.
  F8  THE WHOLE-EPOCH FLAGS: under EXP=world_epoch a run that read its epoch is not "RAN OUT OF
      STREAM" and one that hit the cap is "STOPPED AT THE WINDOW CAP"; EXP=world flags as it did.
  F9  THE REFUSALS: EXP=world_epoch without GO_WORLD_EPOCH=1 exits 2 having written nothing and prints
      its sizing and pins; an unknown EXP and an unusable cadence are refused by name.
  F10 A LAUNCH, WITH run.py STOOD IN: EXP=world with KEEP_CKPT off puts no CKPT_ variable and no
      --flush-bytes on any run and ends in the block and the archive; EXP=retok's default arms the
      k0 family's periodic saves and the act arms' final one, and a smoke whose k0 kept no copy stops
      at the kept-checkpoint tripwire -- with a block, and an archive. With a stand-in that saves the
      way CKPT and TOK do (a .tmp, the ring's rotation, the vocabulary after the checkpoint), the
      watcher and the index keep every periodic save coherent, the tripwire passes, and a second
      launch into the same OUT moves the first fleet aside whole and keeps its own copies (build
      1.5's review: it used to delete them as duplicates of the first fleet's).
  F11 EXP=world's ANALYSIS.txt of the 2026-09-24 fleet archive is byte-identical to the one the script
      wrote before §8 1.5 (be2382a).
  F12 THE WATCHER'S LOOK, keep_sweep, over staged ring states: a checkpoint whose vocabulary has not
      landed is not taken, a .prev whose vocabulary has just rotated is, two missed saves leave the
      ring's two whole, and a save landing between the look and the link removes the half-taken copy.
      Every kept checkpoint sits beside its own vocabulary.
  F13 THE WATCHER ENDS WITH ITS run_job: killed, the watcher takes a last look and exits (build 1.5's
      review: it polled for ever).
  F14 THE STUDENT-t QUANTILE, the script's own (its eps-rule block, exec'd by its markers): pure python,
      held to t(0.95, 2) = 2.919986, t(0.95, 4) = 2.131847, t(0.975, 2) = 4.302653 and more.
  F15 THE eps RULE (Proposal 05 O2, O14), on its own and on synthetic per-phase fleets: a harmless
      cadence PASSes, a harmful one FAILs, a noisy one and one at n < 2 are UNRESOLVED; the Bonferroni
      split over phases and Holm across the cadences (the stronger evidence at alpha/2, the other at
      alpha, none after the first that does not FAIL); the block carries each arm's per-phase means and
      bounds, its verdict, eps and n. Each flush is placed by its run's cumulative bytes: an act arm
      whose flushes grow after its act reads each phase at its known value, where index quarters
      would mix neighbouring phases (the split's review: every fleet had equal flushes, so a
      placement ignoring the bytes passed).
  F16 O14's CHOICE: 1000 replaces 3000 when it is significantly better or when 3000 FAILs; 3000 stays
      on UNRESOLVED readings and when 1000 FAILs; every cadence FAILing is ESCALATE; no act is
      UNDECIDED; the whole truth table, and 0 is never an answer.
  F17 THE BLACKOUT SPLIT where n_live first reaches FAB_SLOTS (O14): an estimate from the act windows and
      the cooldown, each part over its own windows, FAB_SLOTS off the gate text, a pool that never fills
      read as all before, n_live at the end per arm; C13's alarm reads the before-part only. Without
      the counter it reads an upper bound built from the acts before the fill: acts all after it bound
      the part before at 0% and sound nothing (the split's review: every notification was charged
      there, and both alarmed at 100%), a stamp no act line places is charged a cooldown before, and
      only a log with no act window falls back to every notification x cooldown.
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
NEW13 = ("fab.blackout_windows", "tok.mint_wait_windows", "loop.act_seconds", "tok.bpt_tail")


def summary(out, *, exp="retok", seeds="0 1 2", windows=20000, stream=3780000, extra="", dirty=False,
            par=12, fin_s=16560, eta=("0.3", "420,000", "461.6"), cal="461.589", kept="ON",
            levels="on (DOM_LEVELS declared, default on)", cap=60000, calw=600, tree13=(), fbflag="no"):
    """tree13: the §8 1.3 counters the launch found in the tree (None: a SUMMARY.txt from before the
    record, which has no such line)."""
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
    ] + ([] if tree13 is None else
         [f"=== §8 1.3 in this tree: counters {' '.join(tree13) or 'none'}; run.py --flush-bytes {fbflag}"]) + [
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
        counters=None, stopped=False, rc=0, last=None, curve=True, fbytes=None, tail=True, losses=None,
        lines=(), cooldown=400):
    """One run's log, curve and _done.txt line. Returns the curve written (None without one). `lines`
    are further log lines (progress lines, gates), written after the counters."""
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
             f"'cooldown={cooldown} windows'\")")
    L.extend(lines)
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


def retok_fleet(out, *, seeds=(0, 1), k3000=None, k1000=None, nuis=True, cd=False, nuisv=None, **kw):
    """k0 at 1.0, k0_nuis at 1.0001 (so M = 0.0001), k3000 and k1000 at the given per-seed values."""
    summary(out, seeds=" ".join(map(str, seeds)), **kw)
    for s in seeds:
        run(out, "k0", s, 1.0, secs=10.0 + s)
        if nuis:
            run(out, "k0_nuis", s, (nuisv or {}).get(s, 1.0001), secs=10.0)
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
    check("F1 M is the largest |k0 - k0_nuis| (0.0001), reported beside the rule and deciding nothing (O14)",
          "=== REPORTED, DECIDES NOTHING (O14): M = 0.00010 bits/byte (max over 2 seed(s) |k0 - k0_nuis|) ===" in a1
          and re.search(r"k1000\s+- k0 per seed: s0 \+0\.00005\s+s1 \+0\.00030\s+mean \+0\.00018$", a1, re.M) is not None)
    check("F1 without per-flush bytes the rule reads the whole run as a single phase, and says so",
          "endpoint prequential bits/byte per phase: the WHOLE RUN as a single phase, because the per-flush bytes "
          "(run.py --flush-bytes) are absent for k0.s0, k0.s1, k1000.s0, k1000.s1, k3000.s0, k3000.s1 ===" in a1)
    # k3000 - k0 is -0.0002 at both seeds (sd 0: both bounds are the mean); k1000 - k0 is +0.00005 and
    # +0.0003: mean 0.000175, SE 0.000125, one-sided 95% upper 0.000175 + t(0.95, 1) x 0.000125.
    _up = 0.000175 + 6.313752 * 0.000125
    check("F1 by the eps rule both cadences PASS at 2 seeds: every upper bound is within eps 0.05",
          re.search(r"^  k3000 n=2 a=0\.0\d+: p1 -0\.0002 \[-0\.0002,-0\.0002\] -> PASS$", a1, re.M) is not None
          and re.search(r"^  k1000 n=2 a=0\.0\d+: p1 \+0\.0002 \[-0\.\d+," + re.escape(f"{_up:+.4f}") + r"\] -> PASS$",
                        a1, re.M) is not None,
          str([l for l in a1.splitlines() if "-> " in l]))
    # 1000 - 3000 whole run: +0.00025 and +0.0005, mean 0.000375, SE 0.000125.
    _up13 = 0.000375 + 6.313752 * 0.000125
    check("F1 3000 stays: neither FAILs, and 1000 is not significantly better (its whole-run upper bound "
          "against 3000 is above 0)",
          "=== DECISION: TOK_RETOK_EVERY stays 3000 (the incumbent; 0 is never shipped by the rule): k3000 PASS "
          f"against k0; k1000 PASS, the whole-run 1000 - 3000 upper bound {_up13:+.4f} is not below 0 (ε 0.05 "
          "bits/byte, n 2 seed(s)) ===" in a1, str([l for l in a1.splitlines() if "DECISION" in l]))

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
    check("F2 the block holds the rule's rows, M reported, and the DECISION with its B-provisional label",
          "RULE (O14, O2): ε 0.05 bits/byte, incumbent 3000" in t2
          and re.search(r"^  k1000 n=16 a=[\d.]+: p1 .* -> PASS$", t2, re.M) is not None
          and "reported, decides nothing (O14): M = 0.00010 bits/byte" in t2
          and re.search(r"^DECISION: TOK_RETOK_EVERY stays 3000 .*\[B-provisional\]$", t2, re.M) is not None)
    check("F2 the block names a failed run with its last log line",
          "FAILED k0_rerun.s0 rc=1: RuntimeError: boom at window 1234" in t2)
    check("F2 the cooldown arm is reported beside the rule, never as a ship candidate",
          "(beside the rule)" in t2 and "ships 1000_cd100" not in t2)
    # PAST ABOUT 60 SEEDS THE PER-SEED ROWS ARE CONDENSED, NOT THE VERDICT TRUNCATED (build 1.5's
    # review). Seed 7's nuisance pair sets M (0.0003) and seed 11 holds k1000's largest difference
    # (+0.0005): those rows are flagged, with s0, where k3000's equal differences first reach their largest.
    for nseeds in (60, 72):
        o2b = os.path.join(TMP, f"f2b_{nseeds}", "gpu_retok_out")
        retok_fleet(o2b, seeds=tuple(range(nseeds)), cd=True, nuisv={7: 1.0003}, k1000={11: 1.0005})
        p2b = gw("--analyze", EXP="retok", OUT=o2b)
        b2b = block_of(p2b.stdout) or []
        t2b = "\n".join(b2b)
        check(f"F2 at {nseeds} seeds the block is cut to at most 80 lines, says what it cut, and still ends in "
              f"the archive line and END", p2b.returncode == 0 and 0 < len(b2b) <= 80
              and "cut to fit 80 lines" in t2b and "per-seed rows (condensed)" in t2b
              and b2b[-2].startswith("archive: ") and b2b[-1] == "==== END ====", f"{len(b2b)} lines")
        seedrows = re.findall(r"^  s(\d+) ", t2b, re.M)
        more = re.search(r"^  \.\.\. (\d+) more seed row\(s\), none setting M, holding a cadence's largest "
                         r"difference or missing a reading: in ANALYSIS\.txt's RUNS$", t2b, re.M)
        check(f"F2 at {nseeds} seeds the per-seed rows keep the one that sets M (s7) and k1000's largest "
              f"difference (s11), and count the rest",
              "7" in seedrows and "11" in seedrows and more is not None
              and int(more.group(1)) + len(seedrows) == nseeds, f"{len(seedrows)} rows; {more and more.group(0)}")
        check(f"F2 at {nseeds} seeds M, both cadences' rule rows, the DECISION, the absent line and both "
              f"BLACKOUT ALARMs survive the cut",
              "M = 0.00030 bits/byte" in t2b and "k1000 - k0 mean" in t2b
              and re.search(rf"^  k1000 n={nseeds} a=[\d.]+: p1 .* -> PASS$", t2b, re.M) is not None
              and re.search(rf"^  k3000 n={nseeds} a=[\d.]+: p1 .* -> PASS$", t2b, re.M) is not None
              and re.search(r"^DECISION: TOK_RETOK_EVERY stays 3000 .*\[B-provisional\]$", t2b, re.M) is not None
              and "absent (§8 1.3 not in this tree)" in t2b
              and "BLACKOUT ALARM (C13): k3000" in t2b and "BLACKOUT ALARM (C13): k1000" in t2b,
              str([l for l in b2b if "DECISION" in l or "ALARM" in l]))

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
        counters={"fab.shift_notifications": 0})
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
          "BLACKOUT ALARM (C13): k1000 blacks out 45.0% of its windows before the pool fills, above 20%: re-run "
          "with COOLDOWN_ARM=100 (adds k1000_cd100" in a4 and "BLACKOUT ALARM (C13): k1000" in b4
          and "BLACKOUT ALARM (C13): k3000" not in a4)
    check("F4 the upper bound beside it is 1 x 400 / 1000 = 40.0%",
          "fab.shift_notifications x cooldown 400 / windows = 40.0%" in a4)
    # k0 CARRIES NO fab.blackout_windows: FAB seeds it at the first stamp (2026-09-27, Q-RUN-17), and
    # this run's fab.shift_notifications is 0. That is 0 windows blacked out, not a missing reading.
    _sec = a4[a4.find("=== SECONDARIES"):].splitlines()
    _k0 = next((i for i, l in enumerate(_sec) if l.startswith("  k0 ")), None)
    _k0b = _sec[_k0 + 1] if _k0 is not None and _k0 + 1 < len(_sec) else ""
    check("F4 a run no stamp reached has fab.blackout_windows ABSENT beside fab.shift_notifications 0, "
          "and reads 0.0% of windows, not a missing reading",
          "blackout 0.0% of windows (fab.blackout_windows;" in _k0b
          and re.search(r"k0 acts .*; blackout 0\.0% \(<= 0\.0%\)", b4) is not None,
          f"{_k0b.strip()[:90]} | {[l for l in b4.splitlines() if 'k0 acts' in l]}")
    check("F4 §8 1.3's readings are read when present (mint wait 800 / 40, act 1.5 s of 100 s, "
          "tok.bpt_tail) and no 'absent' line prints",
          "mint wait 20.0 windows x 40 id(s); act 1.50% of loop time (MEM re-cut 0.50%)" in a4
          and "tok.bpt_tail 1.6000" in a4 and "absent (§8 1.3" not in a4)
    check("F4 bits/byte by phase splits the run at the stream's quarter points off the per-flush bytes "
          "(1, 2, 3 and 4 bits/byte by construction)",
          re.search(r"k0\s+bits/byte by phase: 1\.0000 2\.0000 3\.0000 4\.0000", a4) is not None,
          str([l for l in a4.splitlines() if "by phase" in l]))
    # THE ACT'S COST IS ITS OWN SECONDS (build 1.5's review): k1000's loop.act_seconds 1.5 and
    # act_remap_seconds 0.5 of its 100 s are 2.00%. Its per-byte time against k0 (10 s) is +900%, and
    # with kept checkpoints ON that figure says it is against k0's time with its saves.
    _r1000 = next((l for l in a4.splitlines() if l.startswith("  k1000 ") and "windows/s" in l), "")
    check("F4 an act arm's rate carries the act's own share of loop time (loop.act_seconds + "
          "act_remap_seconds), and qualifies its distance from a saving k0, in ANALYSIS and in the block",
          "act + MEM re-cut 2.00% of loop time (loop.act_seconds + act_remap_seconds: the act's cost)" in _r1000
          and "per-byte loop time vs k0 +900.0% (k0's time includes its periodic saves: not the act's cost)" in _r1000
          and re.search(r"^  k1000 [\d.]+ w/s .*, act \+ MEM re-cut 2\.00% of loop, per-byte time vs k0 \+900\.0% \(k0 saves\)$",
                        b4, re.M) is not None
          and "the k0 family's loop time includes its periodic saves" in b4, _r1000)
    # UNREACHABLE IS NOT MISSING (build 1.5's review). The tree record lists all four counters and
    # run.py's --flush-bytes, but no act fired and nothing was stamped: tok.bpt_tail and
    # fab.blackout_windows are in no log. The line read "§8 1.3 not in this tree" there.
    o4b = os.path.join(TMP, "f4b", "gpu_retok_out")
    summary(o4b, seeds="0", windows=1000, stream=189000, tree13=NEW13, fbflag="yes")
    _quiet = {"fab.shift_notifications": 0, "tok.mint_wait_windows": 0, "tok.mint_waited": 0,
              "loop.act_seconds": 0.0, "loop.act_remap_seconds": 0.0}
    run(o4b, "k0", 0, 1.0, n=10, win=1000, nbytes=189000, fbytes=[18900] * 10,
        counters={"fab.shift_notifications": 0})
    run(o4b, "k0_nuis", 0, 1.0001, n=10, win=1000, nbytes=189000, fbytes=[18900] * 10,
        counters={"fab.shift_notifications": 0})
    for a in ("k3000", "k1000"):
        run(o4b, a, 0, 1.0, n=10, win=1000, nbytes=189000, acts=0, fbytes=[18900] * 10, counters=_quiet)
    gw("--analyze", EXP="retok", OUT=o4b)
    a4b = open(os.path.join(o4b, "ANALYSIS.txt")).read()
    b4b = open(os.path.join(o4b, "PASTE_BACK.txt")).read()
    _un = ("unreachable in these runs (ABSENT from every log; the tree has them): fab.blackout_windows (no run "
           "stamped, or FAB_COOLDOWN=0 / FAB_GROW=0), tok.bpt_tail (no act spliced)")
    check("F4 a key the tree records and no log printed is 'unreachable in these runs', with its reason, and "
          "never 'not in this tree', in ANALYSIS and in the block",
          _un in a4b and _un in b4b and "not in this tree" not in a4b + b4b,
          str([l for l in a4b.splitlines() if "absent" in l or "unreachable" in l]))
    check("F4 ... and where the tree has fab.blackout_windows, a run with fab.shift_notifications 0 reads 0.0% "
          "of windows blacked out even when no run in the fleet was stamped",
          re.search(r"k1000 acts 0 .*; blackout 0\.0% \(<= 0\.0%\)", b4b) is not None,
          str([l for l in b4b.splitlines() if "k1000 acts" in l]))
    o4c = os.path.join(TMP, "f4c", "gpu_retok_out")
    shutil.copytree(o4b, o4c)
    summary(o4c, seeds="0", windows=1000, stream=189000, tree13=None)
    gw("--analyze", EXP="retok", OUT=o4c)
    a4c = open(os.path.join(o4c, "ANALYSIS.txt")).read()
    check("F4 a SUMMARY.txt from before the tree record names the absent keys without claiming the tree lacks "
          "them", "absent from every log (not in this tree, or unreachable here: SUMMARY.txt predates the tree "
          "record): fab.blackout_windows, tok.bpt_tail" in a4c and "(§8 1.3 not in this tree)" not in a4c,
          str([l for l in a4c.splitlines() if "absent" in l]))

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
    # THE POOL AT ITS CEILING (O20, NEW-20). SUMMARY.txt's EXTRA says FAB_SLOTS=3500; the runs are 2050 windows.
    # k0 (and its twin k0_rerun, left out of the pool) reads 3000 off the growth gate's text, over a stray
    # FAB_SLOTS=3200 earlier in its log and over EXTRA. Its passes are every 500 windows, so the lines one window
    # after them (501, 1001, 1501, 2001) read their dips: 2500 -> 2400 at 501, before the fill and far below the
    # 2% band (2940), is not counted; the fill is at 901, and 10, 25 and 15 at 1001, 1501 and 2001 are. That is
    # 1149 of 2050 windows to the end, 9 of the 12 lines there at it, 60 merged + culled in 4 passes. k3000 has
    # no gate text and reads the stray FAB_SLOTS=3200, fills at 1301 and dips 20 at 1501: 749 of 2050, 7 of 8,
    # no passes counter. k1000 has neither and reads EXTRA's 3500, whose band starts at 3430: the drop of 29
    # from 3429 is outside it, the drop of 30 from 3430 inside. A fleet with an empty EXTRA and no FAB_SLOTS=
    # in its log reads the lever's 4096, labelled assumed.
    o5p = os.path.join(TMP, "f5p", "gpu_retok_out")
    summary(o5p, seeds="0", windows=2050, extra="FAB_GRACE=1 FAB_SLOTS=3500")

    def pl(pairs):
        return [f"[{w} windows] loss=2.0000 opt_steps={w} n_live={n} vocab=600 uncalled=0" for w, n in pairs]
    stray = "=== a stray mention outside the growth gate: FAB_SLOTS=3200"
    fill_k0 = list(zip(range(101, 2002, 100), [2100, 2200, 2300, 2500, 2400, 2600, 2750, 2900, 3000, 2990, 3000,
                                               3000, 3000, 3000, 2975, 3000, 3000, 3000, 3000, 2985]))
    gate3000 = ("       gate:fab.growth                              ('armed-but-zero', \"'0 asked, 0 grown, "
                "n_live=3000' vs 'soft cap headroom + new_frac=0.04 of 3000 (FAB_N0=2048, FAB_SLOTS=3000)'\")")
    for a in ("k0", "k0_rerun"):
        run(o5p, a, 0, 1.0, n=20, win=2050, lines=[stray] + pl(fill_k0) + [gate3000],
            counters={"fab.merged": 40, "fab.cull_fail": 16, "fab.cull_util": 4, "fab.manage_passes": 4,
                      "fab.manage_every_windows": 500})
    run(o5p, "k3000", 0, 1.0, n=20, win=2050, counters={"fab.merged": 20},
        lines=[stray] + pl([(w, 2049 + w // 100 * 80) for w in range(101, 1300, 100)]
                           + [(w, {1501: 3180}.get(w, 3200)) for w in range(1301, 2002, 100)]))
    run(o5p, "k1000", 0, 1.0, n=20, win=2050,
        lines=pl([(w, 2049 + w // 100 * 50) for w in range(101, 1500, 100)]
                 + [(1501, 3429), (1601, 3400), (1701, 3430), (1801, 3400), (1901, 3430), (2001, 3430)]),
        counters={"fab.merged": 5, "fab.cull_fail": 2, "fab.manage_passes": 40, "fab.manage_every_windows": 50})
    r5p = subprocess.run(["bash", os.path.join(ROOT, "tools", "read_fleet_archive.sh"), o5p], cwd=TMP,
                         env=clean_env(), capture_output=True, text=True, timeout=120)
    rows5 = [l.strip() for l in r5p.stdout.splitlines() if l.strip().startswith("ceiling ")]
    check("F5 the reader's pool row: FAB_SLOTS off the gate text, else a FAB_SLOTS= in the log, else EXTRA; the fill, "
          "the windows from it to the end and their share, the lines at the ceiling, the drops from within 2% of it "
          "(not a dip from below) as a lower bound per pass, and merged + culled over the passes",
          r5p.returncode == 0 and rows5 == [
              "ceiling 3000 from w901: 1149 of 2050 w to the end (56.0%), at it on 9/12 lines; freed/pass >= med 15, "
              "max 25 (3 drops); merged+culled 60 in 4 passes (15.0/pass, whole run)"] * 2 + [
              "ceiling 3500 never reached (max n_live 3430 at w1701); freed/pass >= med 30, max 30 (1 drop); "
              "merged+culled 7 in 40 passes (0.2/pass, whole run)",
              "ceiling 3200 from w1301: 749 of 2050 w to the end (36.5%), at it on 7/8 lines; freed/pass >= med 20, "
              "max 20 (1 drop); merged+culled 20, passes absent"], str(rows5) + r5p.stderr[-300:])
    # The block before O20, for these 4 logs (none with a data plan), was 15 lines: the delimiter, the archive line,
    # the banner's head and its one line, the protocol line, the '-- per run' header, 2 rows per run, the end. O20
    # adds a row per run and the pooled line: 20, the '-- per run' header still at index 5 and still one line.
    bl5 = block_of(r5p.stdout) or []
    i5 = next((i for i, l in enumerate(bl5) if l.startswith("-- per run:")), -1)
    check("F5 ... the pooled line leaves the *_rerun twin out, says the rest of the lines read a pass's dip, calls "
          "the drops a LOWER BOUND and says a drop can span passes when they are closer than the lines; the rows add "
          "one line per run and the pooled line to the block, nothing else",
          bl5[-2:] == [
              "-- pool, 3 runs (*_rerun left out): 2/3 reach the ceiling; fill to end 36.5-56.0% of the run (median "
              "46.3%); at it on 75.0-87.5% of the lines from the fill on (the rest read a pass's dip); freed/pass >= "
              "med 20 (10-30, 5 drops), a LOWER BOUND from the sampling (no log holds the per-pass count); passes "
              "every 50/500 w, lines every 100 w (a drop can span passes)", "==== END ===="]
          and len(bl5) == 20 and i5 == 5 and bl5[i5 + 1].strip().startswith("k0.s0 ") and "n_live" in bl5[i5 + 1],
          f"{len(bl5)} lines, header at {i5}: " + str(bl5[i5:i5 + 2] + bl5[-2:]))
    o5a = os.path.join(TMP, "f5a", "gpu_retok_out")
    summary(o5a, seeds="0", windows=500, extra="")
    run(o5a, "k0", 0, 1.0, n=5, win=500, lines=pl([(101, 3000), (201, 4096), (301, 4096), (401, 4096)]))
    r5a = subprocess.run(["bash", os.path.join(ROOT, "tools", "read_fleet_archive.sh"), o5a], cwd=TMP,
                         env=clean_env(), capture_output=True, text=True, timeout=120)
    check("F5 ... with no FAB_SLOTS= in the log and an empty EXTRA the row reads the lever's 4096 and says it is assumed",
          [l.strip() for l in r5a.stdout.splitlines() if l.strip().startswith("ceiling ")] == [
              "ceiling 4096 (assumed) from w201: 299 of 500 w to the end (59.8%), at it on 3/3 lines; freed/pass: no "
              "drop near it; merged+culled absent"], r5a.stdout[-600:] + r5a.stderr[-300:])

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
          "make it a candidate); the incumbent 3000 did not act, so it is not read and stays",
          "k3000  NO ACT FIRED at any seed" in a6 and re.search(r"^  k1000 n=2 a=[\d.]+: .* -> PASS$", a6, re.M)
          and "=== DECISION: TOK_RETOK_EVERY stays 3000 (the incumbent; 0 is never shipped by the rule): k3000 did "
          "not act in these runs, so the incumbent is not read; k1000 PASS, not compared with the incumbent" in a6,
          str([l for l in a6.splitlines() if "DECISION" in l]))
    o6b = os.path.join(TMP, "f6b", "gpu_retok_out")
    retok_fleet(o6b, nuis=False)
    p6b = gw("--analyze", EXP="retok", OUT=o6b)
    a6b = open(os.path.join(o6b, "ANALYSIS.txt")).read()
    check("F6 with no k0_nuis M is not formed and still decides nothing: the DECISION reads, the later sections "
          "print, and the block is written",
          p6b.returncode == 0 and "=== REPORTED, DECIDES NOTHING (O14): M cannot be formed: no paired k0 / k0_nuis "
          "seeds ===" in a6b and "=== DECISION: TOK_RETOK_EVERY stays 3000" in a6b and "=== RATES" in a6b
          and os.path.exists(os.path.join(o6b, "PASTE_BACK.txt"))
          and "DECISION: TOK_RETOK_EVERY stays 3000" in open(os.path.join(o6b, "PASTE_BACK.txt")).read())

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
    write(os.path.join(kd, ".fleet"), "2026-10-01T12:00:00Z\n")        # this fleet's launch (summary())
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
    # THE RESUME LINE IS THE RUN'S OWN (build 1.5's review): run_job sets RUN_SEED, RUN_DEVICE and
    # DATA_STREAM_BYTES on every run and EXTRA carries none of them; without them the resume is refused.
    _res = (f"CKPT_RESUME={kd}/k0.s0.w1001 CKPT_DIR=<NEW dir> OMP_NUM_THREADS=1 RUN_SEED=0 RUN_DEVICE=cuda "
            f"DATA_STREAM_BYTES=3780000 TOK_RETOK_EVERY=0 python3 run.py")
    check("F7 the resume line names the run's seed, device and stream, in ANALYSIS and in the block",
          f"resume one: {_res} -- a NEW CKPT_DIR, never a kept copy" in a7
          and f"  resume one: {_res}" in open(os.path.join(o7, "PASTE_BACK.txt")).read(),
          str([l for l in a7.splitlines() if "resume one" in l]))
    # A KEEP DIRECTORY STAMPED BY ANOTHER LAUNCH IS REFUSED (build 1.5's review): an index that took an
    # existing w<step> for a duplicate deleted this fleet's own save. Here the directory carries another
    # launch's stamp and that launch's w1001; this fleet's save at step 1001 is left, and so is theirs.
    o7b = os.path.join(TMP, "f7b", "gpu_retok_out")
    shutil.copytree(o7, o7b)
    kdb = os.path.join(o7b, "ckpt", "keep")
    write(os.path.join(kdb, ".fleet"), "2026-09-30T08:00:00Z\n")
    _w = os.path.join(kdb, "k0.s0.w1001", "ckpt.pt")
    _ino = os.stat(_w).st_ino
    d = os.path.join(kdb, "k0.s0.save001")
    os.makedirs(d)
    torch.save({"step": 1001, "epoch": 0, "reason": "periodic", "payload": {"TOK": {"merge_count": 3}}},
               os.path.join(d, "ckpt.pt"))
    write(d + ".dyntok.json", json.dumps({"entries": [[0, 1]] * 3}))
    p7b = gw("--analyze", EXP="retok", OUT=o7b)
    ilog = open(os.path.join(kdb, "k0.s0.index.log")).read() if os.path.exists(os.path.join(kdb, "k0.s0.index.log")) else ""
    check("F7 a keep directory stamped by another launch is refused: the save is left as save001, the other "
          "launch's w1001 is untouched, and the index says why",
          os.path.isfile(os.path.join(d, "ckpt.pt")) and os.stat(_w).st_ino == _ino
          and "!! k0.s0: " in ilog and "is stamped by the fleet launched 2026-09-30T08:00:00Z, not by this one "
          "(2026-10-01T12:00:00Z): nothing indexed and nothing dropped" in ilog, ilog[-300:])
    check("F7 ... and the block carries the refusal",
          "INDEX REFUSED: !! k0.s0: " in open(os.path.join(o7b, "PASTE_BACK.txt")).read())

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
# STUB_SAVES=1: A PERIODIC RUN SAVES AS CKPT AND TOK DO -- a .tmp, the ring rotated onto .prev, the
# .tmp moved in; the vocabulary after the checkpoint, rotating onto <dir>.prev.dyntok.json -- at
# windows iP+1 and at the end, one more merge each time, and records its stream in the blob.
if os.environ.get("STUB_SAVES") == "1" and os.environ.get("CKPT_DIR") and int(os.environ.get("CKPT_EVERY", "0")) > 0:
    import time, torch
    ck, P = os.environ["CKPT_DIR"], int(os.environ["CKPT_EVERY"])
    os.makedirs(ck, exist_ok=True)
    def rot(cur, prev):
        if os.path.exists(cur):
            os.replace(cur, prev)
        os.replace(cur + ".tmp", cur)
    saves = [(i * P + 1, "periodic") for i in range(1, n) if i * P + 1 <= n] + [(n, "final")]
    for i, (step, reason) in enumerate(saves):
        torch.save({"step": step, "epoch": 0, "reason": reason, "stream": int(os.environ["DATA_STREAM_BYTES"]),
                    "payload": {"TOK": {"merge_count": 256 + i}}}, os.path.join(ck, "ckpt.pt.tmp"))
        rot(os.path.join(ck, "ckpt.pt"), os.path.join(ck, "ckpt.pt.prev"))
        with open(ck + ".dyntok.json.tmp", "w") as fh:
            json.dump({"entries": [[0, 1]] * (256 + i)}, fh)
        rot(ck + ".dyntok.json", ck + ".prev.dyntok.json")
        time.sleep(float(os.environ.get("STUB_SAVE_SLEEP", "0")))
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

    # THE WATCHER'S SUCCESS PATH, END TO END (build 1.5's review: only the tripwire's failure was
    # driven). The stand-in saves as CKPT and TOK do. RETOK_ARMS "10 20" makes KEEP_EVERY 10, so k0
    # saves at 11, 21, 31 and 41 of its 50 windows and at the end; the smoke's k0 saves at 6 of 10.
    o10c = os.path.join(TMP, "f10c", "gpu_retok_out")

    def launch(windows, seeds, book_):
        return subprocess.run(["bash", SCRIPT], cwd=ROOT, capture_output=True, text=True, timeout=300,
                              env=clean_env(PATH=env10["PATH"], STUB_BOOK=book_, EXP="retok", DEVICE="cpu",
                                            WINDOWS=windows, SEEDS=seeds, PAR=1, SMOKE_WINDOWS=10,
                                            RETOK_ARMS="10 20", KEEP_POLL="0.2", STUB_SAVES=1,
                                            STUB_SAVE_SLEEP="0.4", OUT=o10c))

    def blob(path):
        return torch.load(path, map_location="cpu", weights_only=False)

    p10c = launch(20, "0 1", os.path.join(TMP, "f10c_book.jsonl"))
    kd10 = os.path.join(o10c, "ckpt", "keep")
    s10 = open(os.path.join(o10c, "SUMMARY.txt")).read() if os.path.exists(os.path.join(o10c, "SUMMARY.txt")) else ""
    launch1 = (re.match(r"=== gpu_world\.sh  (\S+)  commit", s10) or [None, ""])[1]
    kept10 = "".join(open(f).read() for f in sorted(glob.glob(os.path.join(kd10, "*.kept.txt"))))
    want10 = [f"k0.s{s}.w{w} step={w} reason=periodic merges={256 + i} entries={256 + i} coherent"
              for s in (0, 1) for i, w in enumerate((11, 21, 31, 41))]
    check("F10 with a stand-in that saves like CKPT and TOK, EXP=retok runs through: the smoke's tripwire keeps "
          "w6, and every periodic save of both k0 runs is kept beside its own vocabulary, the final save dropped",
          p10c.returncode == 0 and "smoke kept: k0.s0.w6 step=6 reason=periodic merges=256 entries=256 coherent" in s10
          and all(w in kept10 for w in want10) and kept10.count(" coherent ") == 8
          and not glob.glob(os.path.join(kd10, "*.save[0-9]*")) and not glob.glob(os.path.join(kd10, "*.w50*")),
          f"rc {p10c.returncode}; {kept10.count(' coherent ')} coherent; {p10c.stderr[-300:]!r}")
    b10c = "\n".join(block_of(p10c.stdout) or [])
    check("F10 ... the block counts them, its resume line carries RUN_SEED, RUN_DEVICE and the stream "
          "(20 x 189 bytes), the keep directory is stamped with the launch, and SUMMARY records the tree",
          "KEPT: 8 copies of 2 k0 run(s), all coherent" in b10c
          and f"resume one: CKPT_RESUME={kd10}/k0.s0.w11 CKPT_DIR=<NEW dir> OMP_NUM_THREADS=1 RUN_SEED=0 "
              f"RUN_DEVICE=cpu DATA_STREAM_BYTES=3780 TOK_RETOK_EVERY=0 python3 run.py" in b10c
          and launch1 and open(os.path.join(kd10, ".fleet")).read().strip() == launch1
          and "=== §8 1.3 in this tree: counters fab.blackout_windows tok.mint_wait_windows loop.act_seconds "
              "tok.bpt_tail; run.py --flush-bytes yes" in s10,
          str([l for l in b10c.splitlines() if "KEPT" in l or "resume" in l]))

    # A SECOND LAUNCH INTO THE SAME OUT (build 1.5's review). It used to delete its own saves at 11, 21,
    # 31 and 41 as "duplicate steps" of the first fleet's copies, keep those under the names, and read
    # the first fleet's seed-1 logs as its own. At 24 windows its stream is 4536 bytes, not 3780.
    w11 = os.path.join(kd10, "k0.s0.w11", "ckpt.pt")
    id1 = (os.stat(w11).st_ino, os.stat(w11).st_mtime_ns) if os.path.exists(w11) else None
    p10d = launch(24, "0", os.path.join(TMP, "f10d_book.jsonl"))
    aside = os.path.realpath(o10c) + "." + launch1.replace(":", "")
    s10d = open(os.path.join(o10c, "SUMMARY.txt")).read() if os.path.exists(os.path.join(o10c, "SUMMARY.txt")) else ""
    a_w11 = os.path.join(aside, "ckpt", "keep", "k0.s0.w11", "ckpt.pt")
    check("F10 a second launch into the same OUT moves the first fleet aside whole, as <OUT>.<its launch stamp>, "
          "its copies untouched (same inode and mtime), and says so",
          p10d.returncode == 0 and os.path.isfile(os.path.join(aside, "logs", "k0.s1.log"))
          and open(os.path.join(aside, "SUMMARY.txt")).read().startswith(f"=== gpu_world.sh  {launch1}  ")
          and id1 is not None and os.path.exists(a_w11) and (os.stat(a_w11).st_ino, os.stat(a_w11).st_mtime_ns) == id1
          and f"=== the previous fleet in {o10c} was moved aside, whole, to {aside}" in s10d,
          f"rc {p10d.returncode}; {os.path.basename(aside)}; {p10d.stderr[-300:]!r}")
    idx = "".join(open(f).read() for f in glob.glob(os.path.join(kd10, "*.index.log")))
    streams = [blob(os.path.join(kd10, f"k0.s0.w{w}", "ckpt.pt")).get("stream")
               if os.path.exists(os.path.join(kd10, f"k0.s0.w{w}", "ckpt.pt")) else None for w in (11, 21, 31, 41)]
    a10d = open(os.path.join(o10c, "ANALYSIS.txt")).read() if os.path.exists(os.path.join(o10c, "ANALYSIS.txt")) else ""
    b10d = "\n".join(block_of(p10d.stdout) or [])
    check("F10 ... and keeps its own copies: w11-w41 hold its 4536-byte stream, no save was dropped as a "
          "duplicate, no first-fleet run is in its analysis, and its block and KEPT.txt are its own",
          streams == [4536] * 4 and "duplicate" not in idx and not os.path.exists(os.path.join(o10c, "logs", "k0.s1.log"))
          and not re.search(r"^\s+k0\s+s1 ", a10d, re.M) and "KEPT: 4 copies of 1 k0 run(s), all coherent" in b10d
          and "DATA_STREAM_BYTES=4536" in b10d
          and open(os.path.join(o10c, "KEPT.txt")).read().count(" coherent ") == 4,
          f"{streams}; {'duplicate' in idx}")

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

    # ---- F12: the watcher's look over staged ring states ------------------------------------------
    # THE SCRIPT'S OWN keep_sweep AND keep_watch, cut out of it and sourced. A generation g is a
    # checkpoint "ckpt-g" and a vocabulary "vocab-g" (keep_sweep reads names, sizes and mtimes, never
    # contents); each save goes through CKPT's and TOK's steps in their order, one step at a time.
    text = open(SCRIPT).read()
    fns = "\n".join(re.search(rf"^{f}\(\) \{{.*?^\}}$", text, re.M | re.S).group(0) for f in ("keep_sweep", "keep_watch"))
    t12 = os.path.join(TMP, "f12")
    ck, kd12 = os.path.join(t12, "ring", "k0.s0"), os.path.join(t12, "keep")
    os.makedirs(ck)
    os.makedirs(kd12)
    stage = os.path.join(TMP, "stage.py")
    write(stage, r'''import os, sys
ck = sys.argv[1]
T0 = 1_790_000_000_000_000_000
def put(path, text, ns):
    with open(path, "w") as fh:
        fh.write(text)
    os.utime(path, ns=(ns, ns))
def rot(cur, prev):
    if os.path.exists(cur):
        os.replace(cur, prev)
    os.replace(cur + ".tmp", cur)
# one save's steps, in CKPT.save's and then TOK.save_vocabulary's order
g, upto = int(sys.argv[2]), sys.argv[3]
t = T0 + g * 1_000_000_000
steps = {"c": lambda: (put(os.path.join(ck, "ckpt.pt.tmp"), f"ckpt-{g}", t),
                       rot(os.path.join(ck, "ckpt.pt"), os.path.join(ck, "ckpt.pt.prev"))),
         "v1": lambda: (put(ck + ".dyntok.json.tmp", f"vocab-{g}", t + 1000),
                        os.path.exists(ck + ".dyntok.json") and os.replace(ck + ".dyntok.json", ck + ".prev.dyntok.json")),
         "v2": lambda: os.replace(ck + ".dyntok.json.tmp", ck + ".dyntok.json")}
for k in {"c": ["c"], "v1": ["v1"], "v2": ["v2"], "all": ["c", "v1", "v2"]}[upto]:
    steps[k]()
''')
    harness = os.path.join(TMP, "sweep.sh")
    # `ln` IS SHADOWED BY A FUNCTION so a save can land between the look and the link: when $RACE
    # exists, the first link first runs a whole save of the generation it names.
    write(harness, "KEEP_POLL=0.2\n" + fns + "\n" + f'''
ln() {{ if [[ -n "${{RACE:-}}" && -e "$RACE" ]]; then g=$(cat "$RACE"); rm -f "$RACE"; "{sys.executable}" "{stage}" "{ck}" "$g" all; fi; command ln "$@"; }}
case "$1" in
  sweep) keep_sweep "{ck}" "{kd12}" k0.s0 ;;
  watch) KEEP_POLL=2
         ( me=$BASHPID; keep_watch "{ck}" "{kd12}" k0.s0 "$me" & echo $! > "{t12}/wpid"; sleep 60 >/dev/null 2>&1 ) &
         owner=$!; sleep 1; "{sys.executable}" "{stage}" "{ck}" "$2" all; kill -9 $owner
         for i in $(seq 1 40); do kill -0 "$(cat "{t12}/wpid")" 2>/dev/null || {{ echo WATCHER-GONE; exit 0; }}; sleep 0.2; done
         echo WATCHER-ALIVE; kill "$(cat "{t12}/wpid")" ;;
esac
''')

    def save(g, upto="all"):
        subprocess.run([sys.executable, stage, ck, str(g), upto], check=True)

    def sweep(**env):
        return subprocess.run(["bash", harness, "sweep"], capture_output=True, text=True, timeout=60,
                              env=clean_env(**env))

    def kept_pairs():
        """{ckpt content: vocab content} of every copy taken, and the count of copies."""
        out = {}
        for d in sorted(p for p in glob.glob(os.path.join(kd12, "k0.s0.save[0-9]*")) if os.path.isdir(p)):
            out[open(os.path.join(d, "ckpt.pt")).read()] = (open(d + ".dyntok.json").read()
                                                             if os.path.exists(d + ".dyntok.json") else None)
        return out

    save(1)
    save(2)
    sweep()
    check("F12 two whole saves are both taken: ckpt.pt with its vocabulary, ckpt.pt.prev with the rotated one",
          kept_pairs() == {"ckpt-1": "vocab-1", "ckpt-2": "vocab-2"}, str(kept_pairs()))
    save(3, "c")
    sweep()
    check("F12 CKPT rotated and TOK not yet: the new checkpoint sits beside the older vocabulary and is not "
          "taken (mid-save), and the .prev is not taken again", kept_pairs() == {"ckpt-1": "vocab-1", "ckpt-2": "vocab-2"},
          str(kept_pairs()))
    save(3, "v1")
    sweep()
    check("F12 TOK rotated with no new file yet: nothing new is taken, and no checkpoint is paired with another's "
          "vocabulary", kept_pairs() == {"ckpt-1": "vocab-1", "ckpt-2": "vocab-2"}, str(kept_pairs()))
    save(3, "v2")
    sweep()
    check("F12 the save completed: it is taken whole", kept_pairs().get("ckpt-3") == "vocab-3", str(kept_pairs()))
    for g in (4, 5, 6):
        save(g)
    sweep()
    check("F12 two saves missed (4 and 5 unseen, 6 landed): the ring's two, 5 and 6, are taken, each with its own "
          "vocabulary; 4 is gone from the ring",
          kept_pairs() == {f"ckpt-{g}": f"vocab-{g}" for g in (1, 2, 3, 5, 6)}, str(kept_pairs()))
    # A FRESH LOOK AT A MID-SAVE RING: ckpt.pt is 8 beside vocab-7, ckpt.pt.prev is 7 beside vocab-6. Nothing
    # is whole, so nothing is taken; once TOK rotates, 7's .prev pair is.
    save(7)
    save(8, "c")
    shutil.rmtree(kd12)
    os.makedirs(kd12)
    sweep()
    none_yet = kept_pairs()
    save(8, "v1")
    sweep()
    check("F12 a first look at a ring mid-save takes nothing, and after TOK's rotation takes 7 from .prev beside "
          "its own vocabulary", none_yet == {} and kept_pairs() == {"ckpt-7": "vocab-7"}, f"{none_yet} {kept_pairs()}")
    save(8, "v2")
    sweep()
    # THE RACE: 9 is on disk and unseen; as the look links it, save 10 lands, so the link takes 10 under
    # 9's identity. The half-taken copy is removed, 9 is taken from .prev, and the next look takes 10.
    save(9)
    race = os.path.join(t12, "race")
    write(race, "10")
    r = sweep(RACE=race)
    after_race = kept_pairs()
    sweep()
    check("F12 a save that lands between the look and the link leaves no half-taken copy: 9 is taken from .prev, "
          "10 at the next look, every checkpoint beside its own vocabulary",
          not os.path.exists(race) and after_race == {f"ckpt-{g}": f"vocab-{g}" for g in (7, 8, 9)}
          and kept_pairs() == {f"ckpt-{g}": f"vocab-{g}" for g in (7, 8, 9, 10)}
          and len([p for p in glob.glob(os.path.join(kd12, "k0.s0.save[0-9]*")) if os.path.isdir(p)]) == 4,
          f"{after_race} {kept_pairs()} {r.stderr[-200:]}")

    # ---- F13: the watcher ends with its run_job --------------------------------------------------
    # run_job's stand-in starts the watcher with its own pid (KEEP_POLL 2 s here). A second later save 11
    # lands and the stand-in is killed as an OOM kill would (-9), before it can drop the stop file. The
    # watcher's next look is its last: it must take 11 there, and exit.
    shutil.rmtree(kd12)
    os.makedirs(kd12)
    r13 = subprocess.run(["bash", harness, "watch", "11"], capture_output=True, text=True, timeout=60, env=clean_env())
    check("F13 a watcher whose run_job was killed takes a last look and exits (it used to poll for ever)",
          "WATCHER-GONE" in r13.stdout and kept_pairs().get("ckpt-11") == "vocab-11",
          f"{r13.stdout.strip()}; {kept_pairs()}")

    # ---- F14: the Student-t quantile, the script's own ----------------------------------------------
    # THE eps RULE'S BLOCK, CUT OUT OF THE SCRIPT BY ITS MARKERS AND EXEC'D: what is tested is the code the
    # GPU box runs, with `math` only (the box's python has no numpy or scipy promised).
    _blk = re.search(r"^# >>> THE ε RULE.*?^# <<< THE ε RULE$", open(SCRIPT).read(), re.M | re.S)
    ER = {"math": math}
    exec(_blk.group(0), ER)
    tq = ER["t_quantile"]
    known = {(0.95, 2): 2.919986, (0.95, 4): 2.131847, (0.975, 2): 4.302653, (0.95, 1): 6.313752,
             (0.975, 1): 12.706205, (0.99, 10): 2.763769, (0.95, 30): 1.697261, (0.995, 3): 5.840909,
             (0.05, 4): -2.131847}
    got = {k: tq(*k) for k in known}
    check("F14 t_quantile holds the known values to 1e-6: t(0.95,2) 2.919986, t(0.95,4) 2.131847, t(0.975,2) "
          "4.302653, and six more (df 1 to 30, both tails)",
          all(abs(got[k] - v) < 1e-6 for k, v in known.items()),
          str({k: round(v, 7) for k, v in got.items() if abs(v - known[k]) >= 1e-6}))
    check("F14 ... and at a large df it approaches the normal quantile (t(0.95, 1e6) = 1.644855)",
          abs(tq(0.95, 1e6) - 1.644855) < 1e-5 and abs(tq(0.5, 3)) < 1e-12)
    _df2 = [(pp, (2 * pp - 1) / math.sqrt(2 * pp * (1 - pp))) for pp in (0.9, 0.99375, 0.999)]
    check("F14 ... and at df 2 it equals the closed form (2p - 1) / sqrt(2p(1 - p)), deep in the tail too "
          "(p 0.99375 is the Holm-Bonferroni level at a/2 over 4 phases)",
          all(abs(tq(pp, 2) - want_) < 1e-7 * want_ for pp, want_ in _df2), str([(pp, tq(pp, 2)) for pp, _ in _df2]))

    # ---- F15: the eps rule ---------------------------------------------------------------------------
    rule, better_than, choose = ER["eps_rule"], ER["better_than"], ER["choose"]
    HARMLESS = [0.001, -0.002, 0.0005]                  # mean -0.0002: the upper bound is well inside 0.05
    HARMFUL = [0.30, 0.31, 0.29]                        # the lower bound, even at t(0.99375, 2), is above 0.05
    NOISY = [0.10, -0.05, 0.02]                         # neither bound clears 0.05
    r15 = rule({"kH": [HARMLESS] * 4, "kX": [HARMFUL] * 4, "kN": [NOISY] * 4, "k1": [[0.001]] * 4}, 0.05)
    check("F15 a harmless cadence PASSes, a harmful one FAILs, a noisy one is UNRESOLVED, one at n < 2 is "
          "UNRESOLVED (no bound can be formed)",
          [r15[a]["verdict"] for a in ("kH", "kX", "kN", "k1")] == ["PASS", "FAIL", "UNRESOLVED", "UNRESOLVED"]
          and r15["k1"]["phases"][0][2:] == (None, None), str({a: r15[a]["verdict"] for a in r15}))
    _m, _se = sum(NOISY) / 3, math.sqrt(sum((x - sum(NOISY) / 3) ** 2 for x in NOISY) / 2 / 3)
    _lv = r15["kN"]["level"]
    check("F15 the bounds are mean -+ t x sd / sqrt(n): the upper at t(0.95, n-1), the lower at t(1 - a/N, n-1) "
          "with Holm's a for the arm and N = 4 phases",
          all(abs(lo - (_m - tq(1 - _lv / 4, 2) * _se)) < 1e-12 and abs(up - (_m + tq(0.95, 2) * _se)) < 1e-12
              for _, _, lo, up in r15["kN"]["phases"]), str(r15["kN"]))
    # HOLM: the stronger evidence of harm is tested at alpha/2, the other at alpha; and once one does
    # not FAIL, none after it can. kA's one-phase p is 0.03 and kB's 0.04, by construction (sd = 0.01).
    def at_p(pv, df=2):
        m_ = 0.05 + tq(1 - pv, df) * 0.01 / math.sqrt(3)
        return [m_ - 0.01, m_, m_ + 0.01]
    r15b = rule({"kA": [at_p(0.03)], "kB": [at_p(0.04)]}, 0.05)
    r15c = rule({"kB": [at_p(0.04)]}, 0.05)
    r15d = rule({"kA": [HARMFUL], "kB": [[0.20, 0.22, 0.18]]}, 0.05)
    check("F15 Holm across the cadences: the arm with the stronger evidence is tested at alpha/2, the other at "
          "alpha, and both FAIL when both clear their levels",
          (r15d["kA"]["level"], r15d["kB"]["level"]) == (0.025, 0.05)
          and [r15d[a]["verdict"] for a in ("kA", "kB")] == ["FAIL", "FAIL"], str(r15d))
    check("F15 ... Holm stops at the first arm that does not FAIL: kB (p 0.04) FAILs alone at alpha 0.05, but "
          "beside kA (p 0.03, not FAILing at 0.025) it is UNRESOLVED, and says why",
          r15c["kB"]["verdict"] == "FAIL" and r15b["kA"]["verdict"] == "UNRESOLVED"
          and r15b["kB"]["verdict"] == "UNRESOLVED" and "Holm stopped" in r15b["kB"]["note"], str(r15b))
    r15e = rule({"kA": [HARMLESS, HARMLESS, HARMLESS, HARMFUL]}, 0.05)
    check("F15 one harmful phase is enough to FAIL, and every phase must be within eps to PASS",
          r15e["kA"]["verdict"] == "FAIL" and rule({"kA": [HARMLESS] * 3 + [NOISY]}, 0.05)["kA"]["verdict"]
          == "UNRESOLVED")

    # A SYNTHETIC PER-PHASE FLEET: 4 phases of 10 flushes of 94,500 bytes (3,780,000, the summary's
    # stream), each phase's losses chosen so its bits/byte is exact; k0 at 2.0, 2.1, 2.2, 2.3 plus a
    # per-seed offset, each arm at k0 plus its own per-seed difference.
    FB, PER = 94500, 10
    K0 = {0: 0.0, 1: 0.01, 2: -0.01}

    def run_ph(out, name, seed, ph, **kw):
        losses = [ph[k] * LN2 * FB / CTX for k in range(len(ph)) for _ in range(PER)]
        n = PER * len(ph)
        return run(out, name, seed, None, n=n, win=kw.pop("win", 20000), nbytes=FB * n, losses=losses,
                   fbytes=[FB] * n, lines=["       gate:data.phase_entered                      ('fired', '4 vs 4')"]
                   + list(kw.pop("lines", ())), **kw)

    def ph_fleet(out, arms, seeds=(0, 1, 2), acted=True):
        """arms: {name: {seed: difference from k0 (every phase), or a list per phase}}."""
        summary(out, seeds=" ".join(map(str, seeds)))
        for s in seeds:
            base = [2.0 + 0.1 * k + K0[s] for k in range(4)]
            run_ph(out, "k0", s, base)
            run_ph(out, "k0_nuis", s, [b + 0.001 * (s + 1) for b in base])
            for a, d in arms.items():
                dd = d[s] if isinstance(d[s], list) else [d[s]] * 4
                run_ph(out, a, s, [b + x for b, x in zip(base, dd)], acts=(3 if acted else 0), at=(3001,))
        return gw("--analyze", EXP="retok", OUT=out)

    def per_seed(xs):
        return dict(enumerate(xs))

    def ana(out):
        return (open(os.path.join(out, "ANALYSIS.txt")).read(), open(os.path.join(out, "PASTE_BACK.txt")).read())

    ALL = {}                                             # every analysis and block, for F16's "never 0"
    o15 = os.path.join(TMP, "f15", "gpu_retok_out")
    p15 = ph_fleet(o15, {"k3000": per_seed(HARMLESS), "k1000": per_seed(NOISY)})
    a15, b15 = ana(o15)
    ALL["f15"] = a15 + b15
    check("F15 on a fleet, each phase's paired difference is read off the per-flush bytes: 4 phases from the "
          "logs' data.phase_entered gate, the harmless k3000 PASSes, the noisy k1000 is UNRESOLVED",
          p15.returncode == 0 and "4 phases, DATA_STREAM_BYTES=3780000 cut into equal byte ranges (N from the "
          "logs' data.phase_entered gate)" in a15
          and re.search(r"^  k3000 n=3 a=[\d.]+: p1 -0\.0002 \[-0\.\d+,\+0\.\d+\] p2 -0\.0002 .* -> PASS$", a15, re.M)
          and re.search(r"^  k1000 n=3 a=[\d.]+: p1 \+0\.0233 \[-0\.\d+,\+0\.1\d+\] .* -> UNRESOLVED$", a15, re.M),
          str([l for l in a15.splitlines() if "-> " in l]) + p15.stderr[-300:])
    check("F15 the block carries the rule: eps, the incumbent, each arm's n, Holm level, per-phase mean and "
          "bounds, and its verdict, with the DECISION carrying eps and n",
          "RULE (O14, O2): ε 0.05 bits/byte, incumbent 3000; per phase (4), arm - k0 paired over seeds" in b15
          and len(re.findall(r"^  k(?:3000|1000) n=3 a=[\d.]+: p1 \S+ \[\S+\] p2 \S+ \[\S+\] p3 \S+ \[\S+\] p4 \S+ "
                             r"\[\S+\] -> (?:PASS|UNRESOLVED)$", b15, re.M)) == 2
          and re.search(r"^DECISION: .*\(ε 0\.05 bits/byte, n 3 seed\(s\)\)  \[B-provisional\]$", b15, re.M),
          str([l for l in b15.splitlines() if "->" in l or "DECISION" in l]))
    o15b = os.path.join(TMP, "f15b", "gpu_retok_out")
    ph_fleet(o15b, {"k3000": per_seed(HARMLESS), "k1000": {s: [HARMLESS[s]] * 3 + [HARMFUL[s]] for s in (0, 1, 2)}})
    a15b, b15b = ana(o15b)
    ALL["f15b"] = a15b + b15b
    check("F15 a cadence harmful in one phase only FAILs by that phase (p4), read on the fleet",
          re.search(r"^  k1000 n=3 a=0\.025: p1 -0\.0002 .* p4 \+0\.3000 \[\+0\.2\d+,\+0\.3\d+\] -> FAIL$", a15b, re.M)
          is not None, str([l for l in a15b.splitlines() if "-> " in l]))
    o15c = os.path.join(TMP, "f15c", "gpu_retok_out")
    ph_fleet(o15c, {"k3000": per_seed(HARMLESS), "k1000": per_seed(HARMLESS)}, seeds=(0,))
    a15c, b15c = ana(o15c)
    ALL["f15c"] = a15c + b15c
    check("F15 at one seed every cadence is UNRESOLVED and 3000 stays",
          re.search(r"^  k3000 n=1 a=[\d.]+: p1 \+0\.0010 \[-\] .* -> UNRESOLVED", a15c, re.M)
          and re.search(r"^  k1000 n=1 .* -> UNRESOLVED", a15c, re.M)
          and "=== DECISION: TOK_RETOK_EVERY stays 3000" in a15c, str([l for l in a15c.splitlines() if "->" in l]))
    # EACH FLUSH IS PLACED BY ITS RUN'S CUMULATIVE BYTES, NOT BY ITS INDEX (the split's review). Every fleet
    # above has equal flushes, where index quarters place them alike, so a placement that ignored the
    # bytes passed. A retok raises the bytes per token, so an act arm's flushes grow after its act: k1000
    # reads phase 1 in 15 flushes of 63,000 bytes and, after its act, phases 2-4 in 30 flushes of 94,500.
    # By their bytes they fall 15/10/10/10; index quarters (i x 4 // 45) would place 12/11/11/11 and mix
    # phases 1-2, 2-3 and 3-4 (phase 2 would read 0.2 x phase 1 + 0.8 x phase 2: a difference of -0.0020
    # where it is +0.0200). k1000 - k0 is +0.01, +0.02, +0.04 and +0.30 by phase, plus a per-seed jitter
    # of mean 0 (K0's offsets also average 0), so its phases read 2.01, 2.12, 2.24 and 2.60 bits/byte.
    o15d = os.path.join(TMP, "f15d", "gpu_retok_out")
    summary(o15d, seeds="0 1 2")
    FB_ACT = [63000] * 15 + [94500] * 30
    PH_ACT = [0] * 15 + [1] * 10 + [2] * 10 + [3] * 10
    D15, J15 = [0.01, 0.02, 0.04, 0.30], [0.001, -0.002, 0.001]
    for s in (0, 1, 2):
        base = [2.0 + 0.1 * k + K0[s] for k in range(4)]
        run_ph(o15d, "k0", s, base)
        run_ph(o15d, "k0_nuis", s, [b + 0.001 * (s + 1) for b in base])
        run_ph(o15d, "k3000", s, [b + HARMLESS[s] for b in base], acts=3, at=(3001,))
        v15 = [base[k] + D15[k] + J15[s] for k in range(4)]
        run(o15d, "k1000", s, None, n=len(FB_ACT), win=20000, nbytes=sum(FB_ACT), fbytes=FB_ACT, acts=1, at=(5001,),
            losses=[v15[k] * LN2 * nb / CTX for k, nb in zip(PH_ACT, FB_ACT)],
            lines=["       gate:data.phase_entered                      ('fired', '4 vs 4')"])
    p15d = gw("--analyze", EXP="retok", OUT=o15d)
    a15d, b15d = ana(o15d)
    ALL["f15d"] = a15d + b15d
    check("F15 each flush is placed by its run's cumulative bytes: k1000's flushes grow after its act (15 of 63,000 "
          "bytes, then 30 of 94,500), and its phases read their known values, 2.0100 2.1200 2.2400 2.6000 bits/byte, "
          "+0.0100 +0.0200 +0.0400 +0.3000 against k0, FAILing by phase 4 (index quarters read p2 -0.0020)",
          p15d.returncode == 0 and sum(FB_ACT) == 3780000
          and re.search(r"^  k1000\s+bits/byte by phase: 2\.0100 2\.1200 2\.2400 2\.6000  \(3 seed\(s\)\)$", a15d, re.M)
          and re.search(r"^  k1000 n=3 a=[\d.]+: p1 \+0\.0100 \[\S+\] p2 \+0\.0200 \[\S+\] p3 \+0\.0400 \[\S+\] "
                        r"p4 \+0\.3000 \[\+0\.2\d+,\+0\.3\d+\] -> FAIL$", a15d, re.M)
          and re.search(r"^  k1000 n=3 a=[\d.]+: p1 \+0\.0100 .* p2 \+0\.0200 .* -> FAIL$", b15d, re.M)
          and "=== DECISION: TOK_RETOK_EVERY stays 3000" in a15d,
          str([l for l in a15d.splitlines() if "-> " in l or "by phase:" in l]) + p15d.stderr[-300:])

    # ---- F16: O14's choice ------------------------------------------------------------------------------
    CASES = {
        # name: (k3000's differences, k1000's, the DECISION's start)
        "replace_better": ([0.010, 0.012, 0.011], [0.000, 0.001, -0.001],
                           "TOK_RETOK_EVERY ships 1000, replacing the incumbent 3000: k1000 PASS against k0, and the "
                           "whole-run 1000 - 3000 upper bound "),
        "replace_3000_fails": (HARMFUL, NOISY,
                               "TOK_RETOK_EVERY ships 1000, replacing the incumbent 3000: k1000 UNRESOLVED against "
                               "k0, and k3000 FAILs"),
        "stays_1000_unresolved": (HARMLESS, NOISY,
                                  "TOK_RETOK_EVERY stays 3000 (the incumbent; 0 is never shipped by the rule): k3000 "
                                  "PASS against k0; k1000 UNRESOLVED, the whole-run 1000 - 3000 upper bound "),
        "stays_3000_unresolved": (NOISY, HARMLESS,
                                  "TOK_RETOK_EVERY stays 3000 (the incumbent; 0 is never shipped by the rule): k3000 "
                                  "UNRESOLVED against k0; k1000 PASS, the whole-run 1000 - 3000 upper bound "),
        "stays_1000_fails": (HARMLESS, HARMFUL,
                             "TOK_RETOK_EVERY stays 3000 (the incumbent; 0 is never shipped by the rule): k3000 PASS "
                             "against k0; k1000 FAILs"),
        "escalate": ([0.20, 0.22, 0.21], HARMFUL,
                     "ESCALATE: every cadence FAILs against k0 by the ε rule; the act stays ON at 3000 until the "
                     "owner answers; the remedy arms run next (register O14) (ε 0.05 bits/byte, n 3 seed(s))"),
    }
    for cname, (d3, d1, want_) in CASES.items():
        oc = os.path.join(TMP, "f16_" + cname, "gpu_retok_out")
        pc = ph_fleet(oc, {"k3000": per_seed(d3), "k1000": per_seed(d1)})
        ac, bc = ana(oc)
        ALL[cname] = ac + bc
        dl = [l for l in ac.splitlines() if l.startswith("=== DECISION: ")]
        check(f"F16 {cname}: the DECISION reads '{want_[:60]}...', in ANALYSIS and in the block",
              pc.returncode == 0 and len(dl) == 1 and dl[0].startswith("=== DECISION: " + want_)
              and f"DECISION: {dl[0][len('=== DECISION: '):-len(' ===')]}  [B-provisional]" in bc,
              str(dl) + pc.stderr[-300:])
    # 1000 - 3000, whole run, in "replace_better": -0.010, -0.011, -0.012 (each phase alike).
    _d = [-0.010, -0.011, -0.012]
    _up16 = -0.011 + tq(0.95, 2) * math.sqrt(sum((x + 0.011) ** 2 for x in _d) / 2 / 3)
    check("F16 'significantly better' is the one-sided 95% upper bound of the whole-run 1000 - 3000, below 0",
          f"k1000 - k3000 whole run: mean -0.0110, one-sided 95% upper {_up16:+.4f} (n=3): below 0, significantly "
          f"better" in ALL["replace_better"] and f"upper bound {_up16:+.4f} is below 0" in ALL["replace_better"])
    o16u = os.path.join(TMP, "f16_undecided", "gpu_retok_out")
    ph_fleet(o16u, {"k3000": per_seed(HARMLESS), "k1000": per_seed(HARMLESS)}, acted=False)
    a16u, b16u = ana(o16u)
    ALL["undecided"] = a16u + b16u
    check("F16 with no act at any cadence the DECISION is UNDECIDED",
          "=== DECISION: UNDECIDED -- no cadence acted in these runs" in a16u and "k3000  NO ACT FIRED" in a16u)
    # THE WHOLE TRUTH TABLE, on choose() itself: every verdict pair and both 'better' readings.
    table_ok, bad_rows = True, []
    for v3 in ("PASS", "FAIL", "UNRESOLVED"):
        for v1 in ("PASS", "FAIL", "UNRESOLVED"):
            for bt_ in (False, True):
                V = {"k3000": {"verdict": v3}, "k1000": {"verdict": v1}}
                bt3 = {"k1000": (3, -0.01, -0.001 if bt_ else 0.002, bt_, 0.05)}
                kind_, arm_, _why = choose(["k3000", "k1000"], V, bt3, "k3000")
                want_k = ("escalate" if v3 == v1 == "FAIL" else
                          "replace" if v1 != "FAIL" and (v3 == "FAIL" or bt_) else "stays")
                want_a = {"escalate": None, "replace": "k1000", "stays": "k3000"}[want_k]
                if (kind_, arm_) != (want_k, want_a) or arm_ in ("k0", "0"):
                    table_ok = False
                    bad_rows.append((v3, v1, bt_, kind_, arm_))
    check("F16 O14's truth table on choose(): ESCALATE iff both FAIL; 1000 replaces 3000 iff 1000 does not FAIL "
          "and (3000 FAILs or 1000 is significantly better); otherwise 3000 stays; 0 is never an answer",
          table_ok and choose([], {}, {}, "k3000")[0] == "undecided", str(bad_rows))
    never0 = {k: re.findall(r"(?:ships|stays) (\d+)", v) for k, v in ALL.items()}
    check("F16 across every fleet above no DECISION ships or keeps 0",
          all("0" not in v for v in never0.values()) and not any("ships 0" in v for v in ALL.values()), str(never0))

    # ---- F17: the blackout split ---------------------------------------------------------------------
    # 2000 windows, cooldown 400. k1000: acts at 101, 601, 1201, 1801, blacked out [101,501) [601,1001)
    # [1201,1601) [1801,2000) = 1399 windows; the pool reaches FAB_SLOTS 4096 (the default: no gate text)
    # at the progress line of window 1001, so 800 of them are before it (of 1001 windows) and 599 after
    # (of 999). k3000: FAB_SLOTS 3000 off the growth gate's text, reached at window 201, acts at 1101 and
    # 1601: all 799 after; unsplit it is 40% of the run, but its before-part is 0. k1000_cd100: cooldown
    # 100, a pool that never fills (4000 of 4096), 350 windows: all before, 17.5%.
    o17 = os.path.join(TMP, "f17", "gpu_retok_out")
    summary(o17, seeds="0", windows=2000, stream=378000)

    def prog(fill_at, top):
        """Progress lines every 100 windows: n_live climbs from 2049 and holds at `top` from `fill_at` on."""
        return [f"[{w} windows] loss=2.0000 opt_steps={w} n_live="
                f"{top if fill_at is not None and w >= fill_at else min(top, 2049 + w // 100 * 100)} "
                f"vocab=600 uncalled=0" for w in range(101, 2000, 100)]

    run(o17, "k0", 0, 1.0, n=20, win=2000, nbytes=378000, counters={"fab.shift_notifications": 0, "fab.n_live": 4096},
        lines=prog(1001, 4096))
    run(o17, "k0_nuis", 0, 1.0001, n=20, win=2000, nbytes=378000, counters={"fab.shift_notifications": 0})
    run(o17, "k1000", 0, 1.0, n=20, win=2000, nbytes=378000, acts=4, at=(101, 601, 1201, 1801),
        counters=dict(OLD13, **{"fab.shift_notifications": 4, "fab.blackout_windows": 1399, "fab.n_live": 4096}),
        lines=prog(1001, 4096))
    run(o17, "k3000", 0, 1.0, n=20, win=2000, nbytes=378000, acts=2, at=(1101, 1601),
        counters=dict(OLD13, **{"fab.shift_notifications": 2, "fab.blackout_windows": 799, "fab.n_live": 3000}),
        lines=prog(201, 3000) + ["       gate:fab.growth                              ('armed-but-zero', "
                                 "\"'0 asked, 0 grown, n_live=3000' vs 'soft cap headroom + new_frac=0.04 of 3000 "
                                 "(FAB_N0=2048, FAB_SLOTS=3000)'\")"])
    run(o17, "k1000_cd100", 0, 1.0, n=20, win=2000, nbytes=378000, acts=4, at=(101, 601, 1201, 1801), cooldown=100,
        counters=dict(OLD13, **{"fab.shift_notifications": 4, "fab.blackout_windows": 350, "fab.n_live": 4000}),
        lines=prog(None, 4000))
    p17 = gw("--analyze", EXP="retok", OUT=o17)
    a17, b17 = ana(o17)
    # EACH ARM'S SPLIT ROW, the third of its SECONDARIES rows.
    sp = {a: re.search(rf"^  {a} +acts [^\n]*\n[^\n]*\n +(blackout [^\n]*)$", a17, re.M)
          for a in ("k1000", "k3000", "k1000_cd100")}
    sp = {a: (m.group(1) if m else "") for a, m in sp.items()}
    check("F17 the split: k1000 blacks out 79.9% of the windows before the pool fills (800 of 1001) and 60.0% of "
          "those after (599 of 999), estimated from the act windows; the pool full at window 1001; n_live 4096",
          p17.returncode == 0 and sp["k1000"] == (
              f"blackout {100 * 800 / 1001:.1f}% of the windows before the pool fills, {100 * 599 / 999:.1f}% of those "
              "after (estimated from the act windows); pool full (n_live >= FAB_SLOTS 4096) in 1/1 run(s) from window "
              "1001; n_live at the end 4096 [4096-4096]"), sp["k1000"] + p17.stderr[-300:])
    check("F17 FAB_SLOTS is read off the growth gate's text (3000, reached at window 201): k3000's 799 windows are "
          "all after the fill",
          sp["k3000"].startswith(f"blackout 0.0% of the windows before the pool fills, {100 * 799 / 1799:.1f}% of those "
                                 "after (estimated from the act windows); pool full (n_live >= FAB_SLOTS 3000) in 1/1 "
                                 "run(s) from window 201; n_live at the end 3000"), sp["k3000"])
    check("F17 a pool that never fills is all before (350 of 2000 windows at cooldown 100), with no after-part",
          sp["k1000_cd100"].startswith("blackout 17.5% of the windows before the pool fills, -% of those after; pool "
                                       "full (n_live >= FAB_SLOTS 4096) in 0/1 run(s); n_live at the end 4000"),
          sp["k1000_cd100"])
    check("F17 C13's alarm reads the before-part only: k1000 (79.9% before) sounds; k3000, 40% of its run blacked "
          "out but none of it before the fill, does not",
          f"BLACKOUT ALARM (C13): k1000 blacks out {100 * 800 / 1001:.1f}% of its windows before the pool fills, above "
          "20%" in a17 and "BLACKOUT ALARM (C13): k3000" not in a17 and "BLACKOUT ALARM (C13): k1000" in b17
          and "blackout 40.0% of windows (fab.blackout_windows;" in a17,
          str([l for l in a17.splitlines() if "ALARM" in l]))
    check("F17 the analysis says the split is an estimate built from the act windows, and the block carries the "
          "split and n_live per arm",
          "the blackout split is an ESTIMATE built from the act windows: fab.blackout_windows is cumulative" in a17
          and "BLACKOUT SPLIT where n_live first reaches FAB_SLOTS (each part over its own windows; C13 reads the part "
              "before; ESTIMATED from the act windows x FAB_COOLDOWN" in b17
          and f"  k1000 before {100 * 800 / 1001:.1f}% / after {100 * 599 / 999:.1f}% (est.); full (slots 4096) in 1/1 "
              "run(s) from window 1001; n_live end 4096 [4096-4096]" in b17
          and "  k0 before 0.0% / after 0.0%; full (slots 4096) in 1/1 run(s) from window 1001; n_live end 4096" in b17,
          str([l for l in b17.splitlines() if "before" in l]))
    # WITHOUT THE COUNTER THE ALARM READS AN UPPER BOUND BUILT FROM THE ACTS BEFORE THE FILL (the split's
    # review). The tree record lists no §8 1.3 counter, so no log carries fab.blackout_windows. The bound
    # was fab.shift_notifications x cooldown over the windows before the fill, which charged the acts
    # after the fill to the part before: on this fleet, the pool full at window 101 and every act later
    # (k3000 at 1501; k1000 at 1001, 1501 and 1901), it read 100.0% for both and sounded both alarms,
    # where the whole-run bound before the split (20.0% for k3000) sounded none for k3000.
    o17b = os.path.join(TMP, "f17b", "gpu_retok_out")
    summary(o17b, seeds="0", windows=2000, stream=378000)
    for a, at in (("k0", ()), ("k0_nuis", ()), ("k3000", (1501,)), ("k1000", (1001, 1501, 1901))):
        run(o17b, a, 0, 1.0, n=20, win=2000, nbytes=378000, acts=(len(at) if at else None), at=at,
            counters=(dict(OLD13, **{"fab.shift_notifications": len(at)}) if at else {"fab.shift_notifications": 0}),
            lines=prog(101, 4096))
    p17b = gw("--analyze", EXP="retok", OUT=o17b)
    a17b, b17b = ana(o17b)
    sp17b = {a: re.search(rf"^  {a} +acts [^\n]*\n[^\n]*\n +(blackout [^\n]*)$", a17b, re.M) for a in ("k3000", "k1000")}
    sp17b = {a: (m.group(1) if m else "") for a, m in sp17b.items()}
    check("F17 without the counter, an arm whose every act follows the fill is bounded at 0.0% before it and sounds "
          "no alarm (the pool full at 101; k3000's act at 1501, k1000's at 1001-1901): the bound counts the acts "
          "before the fill, not every notification (it read 100.0% and alarmed both)",
          p17b.returncode == 0 and "BLACKOUT ALARM" not in a17b + b17b
          and all(sp17b[a].startswith("blackout -% of the windows before the pool fills (no counter: at most 0.0% by "
                                      "the act windows x cooldown), -% of those after; pool full (n_live >= FAB_SLOTS "
                                      "4096) in 1/1 run(s) from window 101") for a in sp17b)
          and "fab.shift_notifications x cooldown 400 / windows = 20.0%" in a17b
          and "  k3000 before -% (<= 0.0%) / after -%; full (slots 4096) in 1/1 run(s) from window 101" in b17b
          and "no counter: <= is an upper bound, the act windows before the fill x FAB_COOLDOWN" in b17b,
          str(sp17b) + str([l for l in a17b.splitlines() if "ALARM" in l]) + p17b.stderr[-300:])
    # ... AND THE BOUND WHERE ACTS COME BEFORE THE FILL (at 1001 here). k1000's acts at 101 and 601 cover
    # [101,501) and [601,1001): 800 of the 1001 windows before the fill, 79.9% (every notification's
    # 4 x 400 read 100%). k3000's one act, at 1501, is after it, but a second stamp no act line places is
    # charged a whole cooldown before: 400 of 1001, 40.0%. k1000_cd100 prints no act line, so its bound
    # falls back to every notification: 3 x 100 of 1001, 30.0%.
    o17c = os.path.join(TMP, "f17c", "gpu_retok_out")
    summary(o17c, seeds="0", windows=2000, stream=378000)
    for a in ("k0", "k0_nuis"):
        run(o17c, a, 0, 1.0, n=20, win=2000, nbytes=378000, counters={"fab.shift_notifications": 0},
            lines=prog(1001, 4096))
    run(o17c, "k1000", 0, 1.0, n=20, win=2000, nbytes=378000, acts=4, at=(101, 601, 1201, 1801),
        counters=dict(OLD13, **{"fab.shift_notifications": 4}), lines=prog(1001, 4096))
    run(o17c, "k3000", 0, 1.0, n=20, win=2000, nbytes=378000, acts=1, at=(1501,),
        counters=dict(OLD13, **{"fab.shift_notifications": 2}), lines=prog(1001, 4096))
    run(o17c, "k1000_cd100", 0, 1.0, n=20, win=2000, nbytes=378000, acts=3, cooldown=100,
        counters=dict(OLD13, **{"fab.shift_notifications": 3}), lines=prog(1001, 4096))
    p17c = gw("--analyze", EXP="retok", OUT=o17c)
    a17c, b17c = ana(o17c)
    sp17c = {a: re.search(rf"^  {a} +acts [^\n]*\n[^\n]*\n +(blackout [^\n]*)$", a17c, re.M)
             for a in ("k1000", "k3000", "k1000_cd100")}
    sp17c = {a: (m.group(1) if m else "") for a, m in sp17c.items()}
    _al = [l for l in a17c.splitlines() if "ALARM" in l]
    check("F17 without the counter the bound is the act windows before the fill x cooldown (k1000: 800 of 1001, "
          "79.9%), a stamp no act line places is charged a cooldown before (k3000: 400 of 1001, 40.0%), and with no "
          "act window every notification x cooldown (k1000_cd100: 3 x 100 of 1001, 30.0%); the alarm reads the bound",
          p17c.returncode == 0
          and sp17c["k1000"].startswith(f"blackout -% of the windows before the pool fills (no counter: at most "
                                        f"{100 * 800 / 1001:.1f}% by the act windows x cooldown)")
          and sp17c["k3000"].startswith(f"blackout -% of the windows before the pool fills (no counter: at most "
                                        f"{100 * 400 / 1001:.1f}% by the act windows x cooldown)")
          and sp17c["k1000_cd100"].startswith(f"blackout -% of the windows before the pool fills (no counter: at most "
                                              f"{100 * 300 / 1001:.1f}% by fab.shift_notifications x cooldown)")
          and f"BLACKOUT ALARM (C13): k1000 blacks out {100 * 800 / 1001:.1f}% of its windows before the pool fills "
              "(upper bound by the act windows x cooldown), above 20%: the cooldown arm k1000_cd100 is in this fleet" in a17c
          and f"BLACKOUT ALARM (C13): k3000 blacks out {100 * 400 / 1001:.1f}% of its windows before the pool fills "
              "(upper bound by the act windows x cooldown)" in a17c and len(_al) == 2
          and f"  k1000 before -% (<= {100 * 800 / 1001:.1f}%) / after -%" in b17c,
          str(sp17c) + str(_al) + p17c.stderr[-300:])
finally:
    shutil.rmtree(TMP, ignore_errors=True)

print(f"\n=== {len(FAILS)} failing ===")
sys.exit(1 if FAILS else 0)
