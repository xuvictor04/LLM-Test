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
      F1-F17's fleets are shaped like the 2026-09-27 fleet and are read at its incumbent,
      RETOK_INCUMBENT=3000 (the default is 1000 since that fleet's DECISION; F25 reads it).
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
  F7  THE KEPT-CHECKPOINT INDEX, on torch-saved stand-ins: a copy is named for the step it holds and is
      coherent when its merge count equals its vocabulary's entries, INCOHERENT otherwise; the run's
      final save is dropped; the act windows it covers are counted off the act arms' logs; the resume
      line carries the run's seed, device and stream, and, the fleet having recorded no pin, the pins
      this checkout declares (F27). A keep directory stamped by another launch is refused, with nothing
      indexed and nothing dropped, and the block says so. With no ckpt/ (an unpacked archive), KEPT.txt
      is kept and read, and whether the fleet kept any is SUMMARY's to say: ON with no KEPT.txt is "none
      here", never "KEEP_CKPT off" (the review of 88d3fae: --analyze of an archive deleted its KEPT.txt,
      said "off", and repacked the archive without it).
  F8  THE WHOLE-EPOCH FLAGS: under EXP=world_epoch a run that read its epoch is not "RAN OUT OF
      STREAM" and one that hit the cap is "STOPPED AT THE WINDOW CAP"; EXP=world flags as it did.
  F9  THE REFUSALS: EXP=world_epoch without GO_WORLD_EPOCH=1 exits 2 having written nothing and prints
      its sizing and pins -- since SR0's build (2026-09-29) DATA_SYNTH_HOLDOUT=1 and EVAL_RETENTION_EVERY
      at 04-6.2's cap beside TOK_RETOK_EVERY and DATA_DRAW -- and a guard that waits on O13's two WORLD
      levers for its five arms, saying which this tree declares; an unknown EXP, an unusable cadence and
      an unusable PROBE_EVERY are refused by name.
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
      alpha, none after the first that does not FAIL), the upper bound at t(1 - alpha) (2026-10-02: it
      was t(0.95) at any alpha); the block carries each arm's per-phase means and
      bounds, its verdict, eps and n. Each flush is placed by its run's cumulative bytes: an act arm
      whose flushes grow after its act reads each phase at its known value, where index quarters
      would mix neighbouring phases (the split's review: every fleet had equal flushes, so a
      placement ignoring the bytes passed).
  F16 O14's CHOICE: 1000 replaces 3000 when it is significantly better or when 3000 FAILs; 3000 stays
      on UNRESOLVED readings and when 1000 FAILs; every cadence of a two-cadence fleet FAILing is
      ESCALATE; no act is UNDECIDED; the whole truth table, and 0 is never an answer. A fleet of one
      cadence never escalates (the review of 88d3fae; O14 escalates only when both cadences and every
      remedy arm FAIL): the incumbent's FAIL does not ship and names O14's other cadence and the remedy
      arms as next, and a lone challenger's FAIL leaves the incumbent standing.
  F17 THE BLACKOUT SPLIT where n_live first reaches FAB_SLOTS (O14): an estimate from the act windows and
      the cooldown, each part over its own windows, FAB_SLOTS off the gate text, a pool that never fills
      read as all before, n_live at the end per arm; C13's alarm reads the before-part only. Without
      the counter it reads an upper bound built from the acts before the fill: acts all after it bound
      the part before at 0% and sound nothing (the split's review: every notification was charged
      there, and both alarmed at 100%), a stamp no act line places is charged a cooldown before, and
      only a log with no act window falls back to every notification x cooldown.
  F18 ONE FLEET PER OUT (2026-09-27: a second paste of the launch line started a second fleet, whose launch
      moved the first one's OUT from under it): a launch into a live OUT is refused -- exit 2, nothing
      moved, the live fleet named with where it is and how to watch and stop it, by absolute paths that
      work from any terminal -- and the live fleet ends rc 0 in its own block, its pid the one STATE names;
      a run.py of a fleet from before the lock, writing under OUT, is found in /proc and refused the same
      way, and once it is gone the dead fleet is moved aside.
  F19 THE HEARTBEAT: a line every HB_EVERY seconds through the smoke, a calibration step and the fleet,
      naming the stage and the runs starting on the CPU and training; each step's line when its runs start,
      saying they build on the CPU first, and the startup the smoke measured (run.py's '=== composed'
      line); HEARTBEAT and heartbeat.log; every run unbuffered and running the fleet's copy of run.py. The
      fleet sizes itself by the cores, not by the OMP_NUM_THREADS=1 its environment exports (the review of
      2026-09-27: GNU nproc reported 1, and the fleet ran one run at a time).
  F20 A STOP WRITES ITS BLOCK: TERM, HUP and INT in a calibration step exit 128+n with 'STOPPED by SIG<x>
      during calibration k=1' in the log and the block, the runs stopped, nothing left, the archive packed;
      the INT as a terminal's Ctrl-C sends it, to the whole process group (the review of 2026-09-27: each
      run_job died of it, its run.py -- ignoring INT -- trained on as an orphan holding the lock, and the
      fleet said STOPPED): the run is stopped and booked rc=143, the lock is free; a `| tee` launch whose
      tee dies with the group still stops whole -- rc 129, SUMMARY's STOPPED line, the archive (a dead pipe
      raised SIGPIPE, which cut the stop short at rc 0); under nohup a HUP is ignored and the fleet runs on;
      at DEVICE=cuda (nvidia-smi and MPS stood in) the stop quits MPS, and the daemon never held the lock.
      A TERM in the analysis waits for it, and the fleet ends FINISHED with its analysis block (it was
      replaced by 'STOPPED BEFORE THE ANALYSIS'); an analysis that fails ends STOPPED, never FINISHED, its
      block saying 'STOPPED AT THE ANALYSIS: the analysis failed'.
  F21 --status's VERDICT AND EXIT CODE: RUNNING 0, FINISHED 1, STOPPED 3 with its reason, NO FLEET 2; DEAD 4
      after SIGKILL of the shell (its heartbeat watcher says so, stops the runs, writes the block) and of the
      whole fleet (no end recorded); a reused pid is not RUNNING; a fleet from before STATE reads off its
      block, FINISHED only when SUMMARY shows it ended its own analysis (a block --analyze wrote over a fleet
      killed part-way leaves it DEAD); STALLED 5 when nothing moves for --stall-min; an ended fleet whose run
      still runs lists it.
  F22 PULL SAFETY: in a scratch git checkout, gpu_world.sh rewritten in place and run.py and src/ replaced
      mid-fleet change nothing -- rc 0, every run on $OUT/code/run.py, the commit and the copy's sha256 in
      SUMMARY (the launch before the copy died on a syntax error with no block) -- and --status and
      --analyze from the checkout read the fleet as ever.
  F23 THE DASHBOARD (tools/fleet_dash.sh): live frames with the verdict, the stage, each run starting on CPU
      then training with its windows; FINISHED on the finished fleet; --line; --html writes dashboard.html
      and nothing else into OUT; --serve serves that page and only it; run under a terminal, its page holds
      no colour code. A run's rate never counts its startup: a sample taken while it was on the CPU is no
      baseline (the since-training average is used, 50~), one taken while it trained is, at its log's
      times; a run whose run.py ended with its final line but whose rc is not booked yet reads finishing,
      not VANISHED; the CPU line is this container's, the load the host's.
  F24 THE LAUNCHER (tools/gpu_launch.sh): its checks FAIL clearly with their fixes (EXP unset; no GPU at
      DEVICE=cuda) and --go then launches nothing; --go at DEVICE=cpu from a shell that exits at once leaves
      a fleet in its own session that runs to its end and its block, and prints commands by absolute path;
      a second --go FAILs on it; an exported OMP_NUM_THREADS is said, not a WARN; an ended fleet whose run
      still runs is a FAIL whose fix is --stop. Without --go a clean check's "ready:" line carries every
      knob set -- run with env in the launcher's place it gives each one back -- and its KNOBS name every
      knob gpu_world.sh reads (the review of 88d3fae: it carried EXP alone, and after the cooldown fleet's
      knobs its paste would have launched the default retok fleet).
  F25 THE COOLDOWN FLEET AT THE SHIPPED CADENCE (C13's alarm, after the 2026-09-27 DECISION): RETOK_ARMS=1000
      with COOLDOWN_ARM=100 is read at the default incumbent, 1000 -- it stays while k1000 does not FAIL,
      and when k1000, the only cadence, FAILs it does not ship and 3000 and the remedy arms run next, never
      ESCALATE (the review of 88d3fae: O14 escalates only when both cadences and every remedy arm FAIL)
      -- and k1000_cd100 is read against k1000, paired: per phase by the eps rule and over the whole run
      by its one-sided 95% upper bound (below 0: the longer cooldown costs), beside the rule and never
      shipped, in ANALYSIS and in the block.
  F26 THE 2026-09-27 ARCHIVE, RE-READ ON A COPY (the review of 88d3fae): --analyze at RETOK_INCUMBENT=3000
      reproduces the archive's ANALYSIS.txt but the eps rule header's wording and the KEPT section's disk
      and resume lines, which need the checkpoints and give way to one line naming KEPT.txt as the
      source; KEPT.txt stays as it was and the repacked archive holds it; at the default incumbent the
      same runs read "stays 1000"; and the committed archive is never touched.
  F27 04-Q5's PINS ON EVERY RETOK RUN (2026-09-29, the flip of DATA_SYNTH_HOLDOUT, EVAL_RETENTION_EVERY
      and DATA_TRUST; F18 on sr0-build): every run an EXP=retok launch makes carries DATA_SYNTH_HOLDOUT=0
      EVAL_RETENTION_EVERY=0 DATA_TRUST=off, SUMMARY.txt and the block record them, the resume line
      carries them after EXTRA, and EXP=world carries none; on a tree that declares none of the three
      levers, and on one that declares DATA_SYNTH_HOLDOUT alone, each run carries exactly the pins whose
      lever the tree declares. A fleet that recorded no pin (launched before the flip, as the 2026-09-27
      retok fleet was), read by --analyze, gets the pins the reading tree declares on its resume line,
      and a row in ANALYSIS.txt says whose they are (the Stage 3 merge's decision on the flip's open item).
  F28 THE PROBE'S BEST SAVES ARE IN THE DISK BUDGET (2026-09-29, the flip's review; F19 on sr0-build):
      wherever a run's probe is armed ckpt_files counts ckpt.pt.best and .best.prev beside its other
      files, 2 + 2N at CKPT_BEST_KEEP=N -- at EXP=world (the shipped 1000) and EXP=world_epoch (its pin),
      never at EXP=retok (its pins) or at EVAL_RETENTION_EVERY=0, nor on a tree whose default is 0 or that
      declares no probe; the settings read in run_job's order, off the fleet's code. An EXP=world launch
      at KEEP_CKPT=1 budgets 3 files a run and its banner names them, and tools/gpu_launch.sh's disk
      check, which runs the same block, counts them too. k0's kept saves count at EXP=retok alone
      (2026-10-02): an arm named k0 elsewhere divided by KEEP_EVERY 0.
  F29 EXP=heldout's LAUNCH (2026-10-02, register §8 6.3a), with a stand-in that writes a probe series: k0,
      k<c> and k<c>_mn (c = PIN_RETOK) at every seed and k0_rerun; every run's pins after EXTRA, which moves
      none of them, and its arm's settings after the pins (TOK_MINT_NOVEL 1.0 on k<c>_mn alone); --probe-series
      and --flush-bytes on every run; finals only, the k0 family's too; an arm named k0 budgeting 3 files,
      the launcher's disk check the same; the ETA priced by waves; FILL 0 by default; PIN_RETOK refused by name.
      The launcher's disk check at 134 MB a file at EXP=retok, 151 elsewhere, and its FAIL's fix, and the
      fleet's own, fitting the experiment (at EXP=heldout the 7 seeds and the finals kept; at a top-up
      KEEP_CKPT=0); EXP=heldout, the current test, named where EXP is not given (2026-10-02).
  F30 EXP=heldout's READING, on fleets written by hand: each run's endpoint is the last memory-off boundary row
      of its probe series, report half, per area; arm - k0 by the eps rule with the areas as its cells and Holm
      across the act arms, at 0.025 a look; the DECISION's five outcomes -- PASS ends the label, k<c> FAIL
      with k<c>_mn PASS ships TOK_MINT_NOVEL 1.0, both FAIL withdraw (the next remedy arms named, no
      ESCALATE), UNRESOLVED below the cap prints the top-up's command, at the cap it is reported -- and a
      FAIL with the remedy UNRESOLVED topping up; runs with no boundary row or no series named and left out;
      seeds past the cap not read; the reported lines' known answers (the time-integrated gap from 20% of the
      stream, the per-phase prequential reading, memory-on - memory-off, the ETA by waves against the wall).
  F31 THE TOP-UP: read with its first fleet where commit, card, torch and shape match -- the pooled 11 seeds
      deciding what the first 7 could not, both reruns read -- and refused, deciding nothing, where card,
      torch or commit differ or a seed is in both; POOL_WITH at --analyze over SUMMARY's record. End to end
      with the stand-in: the first fleet's printed command launches the top-up that pools with it; the finals'
      manifest and its pack: line, run as printed (a top-up's block packs none); the launch's refusals of
      POOL_WITH, and the launcher's check and ready line.
  F32 EXP=session's LAUNCH (2026-10-02, register §8 5.3a), with a stand-in that saves a parent's final as CKPT does
      (its step, n_live, slots, areas' length and ids minted after its last cut) and writes a session's series:
      from PARENTS, an EXP=heldout stand-in fleet's finals, the smoke resumes P, P_parent and P_twin at the first seed
      and W at the parent with the most experts, and the fleet the three at every seed and W, each resuming its
      parent's final at its seed into a new
      CKPT_DIR -- a second epoch, x5 appended at 5/4 of the parents' stream, pure-add, the rate as logged, the probe's
      pins, the parent arm's settings after them and its own arm's after those (P_twin OPT_LR x 1.0001, W FAB_SLOTS
      max(the parent's slots, its n_live + W_HEADROOM)); SUMMARY names the parents, the sha256 check, W and each
      parent's ids minted after its last cut, the disk check prices W's files at W's own size, and each session's book
      line carries its parent's step. Without PARENTS a parents stage trains them first, keeping its finals with
      a FINALS.sha256, the sessions' smoke runs from them, and the ETA is priced by the two stages. Refused, writing
      nothing: a PARENT_ARM that is no act arm, PARENTS with no manifest or without a seed's final, a final whose
      sha256 moved, parents generated at another stream, EXTRA moving a session's data lever, FILL=1. The launcher's
      check of PARENTS, its disk budget and its ready line.
  F33 EXP=session's READING, on fleets written by hand: each session's endpoint per old area is F = its last
      memory-off 'boundary' row minus its start at its own first cut, report half -- its 'resume_own' row, or its
      'resume' row where it wrote none (since the review of 2026-10-02, which found F counting as the session's what
      its parent's ids minted after its last cut move); P and P_parent are read over the parents by the eps rule with
      the old areas as its cells and Holm across the two, at 0.025 a look; O9's choice -- the one
      admitted, or of two the lower x5 R reading paired by parent, a tie to the smaller worst-area mean F (C25), both
      ways -- and the other outcomes: a top-up's command below the cap (beside an admitted one too), the admitted one
      taken at the cap, UNRESOLVED at the cap, neither admitted, and nothing decided with a candidate unread. Named
      and left out: a session with no series or no resume-start row; flagged: an anchor that moved, a session ended
      before its cap; parents past the cap not read. Reported to known answers: x5's learning, 5.1's SDs with the
      single-run gate's arithmetic (meets it, needs n windows, or O10's replay), W against P, the pricing, the
      rehearsal, rates and the ETA against the wall; the parents' ids minted after their last cut and what they moved.
  F34 THE SESSION TOP-UP: read with its first fleet where commit, card, torch and shape match -- the pooled 11
      parents admitting what the first 7 could not -- and refused, deciding nothing, where card, commit or the
      session's shape differ or a parent is in both. End to end with the stand-in: a fleet with a parents stage
      prints the top-up's command, the launcher passes it, and run as printed it trains parents 7-10 and pools.
  F35 EXP=heldout HELDOUT_SOURCE=real's LAUNCH (2026-10-02, register §8 6.3b), with the stand-in writing the book's series
      too: k0, S (SHIP_ARM, k<PIN_RETOK> by default, or its _mn) and S_replay (S at DATA_DRAW=replay 0.27) at every seed and
      k0_rerun; every run on real text, its pins after EXTRA (DATA_SOURCE=real in DATA_SYNTH_HOLDOUT's place) and its arm's
      settings after them; probe, flush and trust series on every run; the defaults written as numbers (17,476 windows,
      3,780,000 bytes, the probe at 650) and an OUT of its own; HELDOUT_SOURCE=real on every command it prints. Refused,
      writing nothing: an unknown source, real text at another EXP, SHIP_ARM without the real source, an S that is no act
      arm, a real-text top-up of a synthetic fleet. The launcher's check, OUT, log, disk and ready line; the dashboard's
      reading of a real-text launch's OUT.
  F36 EXP=heldout HELDOUT_SOURCE=real's READING, on fleets written by hand, routed to its own reader by SUMMARY's source
      line (a synthetic fleet keeps 6.3a's, F30): O14, S - k0 per area by the eps rule at one arm, a = 0.025 a look --
      PASS ends S's label on real text, FAIL keeps it and names the next remedy arms (TOK_MINT_NOVEL 1.0 first at k<c>),
      UNRESOLVED below the cap prints the top-up's command, at the cap it is reported; O16, S_replay - S, CONFIRMs where
      every area's upper bound is within eps and the time-integrated gap's is below 0 (to the known answer), not where
      replay harms an area, and waits for a top-up's look; E3's wall within and above 2%; each rule's own seeds, where
      both its runs hold R's reading (a k0 with no endpoint leaves O16's 7 pairs whole), the runs each leaves out and its
      seeds past the cap; what is reported beside them, the per-phase prequential reading S - k0's alone; S's finals
      alone in FINALS.sha256 with their pack line.
  F37 THE REAL-TEXT TOP-UP: pooled with its first fleet where commit, card, torch, shape and source match -- the pooled 11
      deciding O14, and O16 where its first look, re-read over the first fleet's seeds, did not CONFIRM: a CONFIRM at
      the first look stands, the pooled reading beside it deciding nothing; O14's cap counts its pairs, as the top-up's
      command does -- and refused, deciding nothing, where card or commit differ, a seed is in both, or the first fleet
      is synthetic. End to end with the stand-in: the printed command passes the launcher and pools.
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
# THE 2026-09-27 FLEET'S INCUMBENT, NAMED WHERE IT IS READ. RETOK_INCUMBENT is read when the analysis runs,
# and its default is 1000 since that fleet's DECISION (Proposal 05 O14). The synthetic retok fleets of
# F1-F17 are shaped like that fleet -- arms k3000 and k1000, 3000 the incumbent -- so every analysis of
# them names 3000, and they hold O14's choice exactly as that fleet read it. F25 reads the default.
INC0927 = {"RETOK_INCUMBENT": "3000"}


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
# 04-Q5's PINS AS EXP=retok SETS THEM ON A TREE THAT DECLARES ALL THREE LEVERS (2026-09-29), in the order the
# script appends them; the resume line carries them after EXTRA, as run_job does (F10, F27).
PINS27 = "DATA_SYNTH_HOLDOUT=0 EVAL_RETENTION_EVERY=0 DATA_TRUST=off"


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
    p = gw("--analyze", EXP="retok", **INC0927, OUT=o1)
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
    p2 = gw("--analyze", EXP="retok", **INC0927, OUT=o2)
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
        p2b = gw("--analyze", EXP="retok", **INC0927, OUT=o2b)
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
    a3 = (gw("--analyze", EXP="retok", **INC0927, OUT=o3), open(os.path.join(o3, "ANALYSIS.txt")).read())[1]
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
    p4 = gw("--analyze", EXP="retok", **INC0927, OUT=o4)
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
    gw("--analyze", EXP="retok", **INC0927, OUT=o4b)
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
    gw("--analyze", EXP="retok", **INC0927, OUT=o4c)
    a4c = open(os.path.join(o4c, "ANALYSIS.txt")).read()
    check("F4 a SUMMARY.txt from before the tree record names the absent keys without claiming the tree lacks "
          "them", "absent from every log (not in this tree, or unreachable here: SUMMARY.txt predates the tree "
          "record): fab.blackout_windows, tok.bpt_tail" in a4c and "(§8 1.3 not in this tree)" not in a4c,
          str([l for l in a4c.splitlines() if "absent" in l]))

    # ---- F5: the archive ------------------------------------------------------------------------
    for f in ("ckpt/k0.s0/ckpt.pt", "ckpt/k0.s0/ckpt.pt.prev", "ckpt/k0.s0.dyntok.json", "smoke/ckpt/x/ckpt.pt",
              "stray.pt", "curves/stray.pt.tmp"):
        write(os.path.join(o1, f), "not a checkpoint")
    p5 = gw("--analyze", EXP="retok", **INC0927, OUT=o1)
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
    p6 = gw("--analyze", EXP="retok", **INC0927, OUT=o6)
    a6 = open(os.path.join(o6, "ANALYSIS.txt")).read()
    check("F6 an act arm with no act at any seed is NO ACT FIRED and never ships (a lower reading does not "
          "make it a candidate); the incumbent 3000 did not act, so it is not read and stays",
          "k3000  NO ACT FIRED at any seed" in a6 and re.search(r"^  k1000 n=2 a=[\d.]+: .* -> PASS$", a6, re.M)
          and "=== DECISION: TOK_RETOK_EVERY stays 3000 (the incumbent; 0 is never shipped by the rule): k3000 did "
          "not act in these runs, so the incumbent is not read; k1000 PASS, not compared with the incumbent" in a6,
          str([l for l in a6.splitlines() if "DECISION" in l]))
    o6b = os.path.join(TMP, "f6b", "gpu_retok_out")
    retok_fleet(o6b, nuis=False)
    p6b = gw("--analyze", EXP="retok", **INC0927, OUT=o6b)
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
    p7 = gw("--analyze", EXP="retok", **INC0927, OUT=o7)
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
    # This fleet's SUMMARY records no pin, so the line also carries the three this checkout declares (the
    # Stage 3 merge; F27).
    _res = (f"CKPT_RESUME={kd}/k0.s0.w1001 CKPT_DIR=<NEW dir> OMP_NUM_THREADS=1 RUN_SEED=0 RUN_DEVICE=cuda "
            f"DATA_STREAM_BYTES=3780000 TOK_RETOK_EVERY=0 {PINS27} python3 run.py")
    check("F7 the resume line names the run's seed, device and stream, and this checkout's pins, in ANALYSIS and in "
          "the block",
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
    p7b = gw("--analyze", EXP="retok", **INC0927, OUT=o7b)
    ilog = open(os.path.join(kdb, "k0.s0.index.log")).read() if os.path.exists(os.path.join(kdb, "k0.s0.index.log")) else ""
    check("F7 a keep directory stamped by another launch is refused: the save is left as save001, the other "
          "launch's w1001 is untouched, and the index says why",
          os.path.isfile(os.path.join(d, "ckpt.pt")) and os.stat(_w).st_ino == _ino
          and "!! k0.s0: " in ilog and "is stamped by the fleet launched 2026-09-30T08:00:00Z, not by this one "
          "(2026-10-01T12:00:00Z): nothing indexed and nothing dropped" in ilog, ilog[-300:])
    check("F7 ... and the block carries the refusal",
          "INDEX REFUSED: !! k0.s0: " in open(os.path.join(o7b, "PASTE_BACK.txt")).read())
    # WITH NO ckpt/, KEPT.txt IS THE FLEET'S RECORD (the review of 88d3fae): an archive packs KEPT.txt and no
    # checkpoint, and --analyze of an unpacked one deleted KEPT.txt, said "KEEP_CKPT off" beside SUMMARY's ON,
    # and repacked the archive without it. o7c is o7 analysed, its ckpt/ then gone, as in an unpacked archive.
    o7c = os.path.join(TMP, "f7c", "gpu_retok_out")
    shutil.copytree(o7, o7c)
    shutil.rmtree(os.path.join(o7c, "ckpt"))
    kept7c = open(os.path.join(o7c, "KEPT.txt")).read()
    p7c = gw("--analyze", EXP="retok", **INC0927, OUT=o7c)
    a7c = open(os.path.join(o7c, "ANALYSIS.txt")).read()
    b7c = open(os.path.join(o7c, "PASTE_BACK.txt")).read()
    tgz7c = os.path.join(os.path.dirname(o7c), "gpu_retok_2026-10-01.tgz")
    names7c = tarfile.open(tgz7c).getnames() if os.path.exists(tgz7c) else []
    check("F7 with no ckpt/ (an unpacked archive) --analyze keeps KEPT.txt as it was and reads its rows -- the same "
          "coverage row, one line naming KEPT.txt in place of the disk and resume lines -- and the archive it packs "
          "holds KEPT.txt",
          p7c.returncode == 0 and os.path.exists(os.path.join(o7c, "KEPT.txt"))
          and open(os.path.join(o7c, "KEPT.txt")).read() == kept7c
          and "k0.s0: 2 kept, w1001-w2001, INCOHERENT at w2001; act windows covered: k1000 1/2" in a7c
          and "  read from KEPT.txt, as the fleet's own analysis wrote it: this directory holds no ckpt/ (an archive "
              "packs none), so no disk figure and no resume line" in a7c
          and "resume one:" not in a7c + b7c and "  disk: " not in a7c
          and "KEPT: 2 copies of 1 k0 run(s), 1 INCOHERENT, act windows covered k1000 1/2; read from KEPT.txt (no "
              "ckpt/ here)" in b7c
          and "gpu_retok_out/KEPT.txt" in names7c,
          str([l for l in (a7c + b7c).splitlines() if "KEPT" in l or "kept" in l]) + p7c.stderr[-300:])
    # WHETHER THE FLEET KEPT ANY IS SUMMARY'S TO SAY: with neither ckpt/ nor KEPT.txt, ON reads "none here" and
    # only OFF reads "KEEP_CKPT off"; and a ckpt/ that holds no index still removes a KEPT.txt it does not hold.
    o7d = os.path.join(TMP, "f7d", "gpu_retok_out")
    retok_fleet(o7d, seeds=(0,))
    gw("--analyze", EXP="retok", **INC0927, OUT=o7d)
    o7e = os.path.join(TMP, "f7e", "gpu_retok_out")
    retok_fleet(o7e, seeds=(0,), kept="OFF")
    gw("--analyze", EXP="retok", **INC0927, OUT=o7e)
    o7f = os.path.join(TMP, "f7f", "gpu_retok_out")
    retok_fleet(o7f, seeds=(0,))
    os.makedirs(os.path.join(o7f, "ckpt"))
    write(os.path.join(o7f, "KEPT.txt"), "k0.s0.w1001 step=1001 reason=periodic merges=3 entries=3 coherent\n")
    gw("--analyze", EXP="retok", **INC0927, OUT=o7f)
    b7d, b7e = (open(os.path.join(o_, "PASTE_BACK.txt")).read() for o_ in (o7d, o7e))
    check("F7 with neither ckpt/ nor KEPT.txt the block reads SUMMARY's record: kept checkpoints ON is 'none here', "
          "OFF is 'KEEP_CKPT off'; and a ckpt/ holding no index still removes a KEPT.txt it does not hold",
          "KEPT: none here (SUMMARY: kept checkpoints ON; no ckpt/, no KEPT.txt)" in b7d and "KEEP_CKPT off" not in b7d
          and "KEPT: none (KEEP_CKPT off)" in b7e
          and not os.path.exists(os.path.join(o7f, "KEPT.txt")),
          str([l for l in (b7d + b7e).splitlines() if "KEPT" in l]))

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
    # THE PIN IS THE SHIPPED CADENCE (S0b-ship: every dependent experiment pins and labels it): 1000 since
    # the 2026-09-27 retok fleet's DECISION (register O14), 3000 before it.
    check("F9 ... having printed its sizing: one whole WINDOWS x 189-byte epoch, the cap at 3 x WINDOWS, "
          "CAL_WINDOWS 600, and the pins -- TOK_RETOK_EVERY at the shipped 1000 and DATA_DRAW, and since SR0 "
          "(2026-09-29) its held-out block on and the probe at 04-6.2's cap, 700",
          "DATA_STREAM_BYTES=3780000" in p9.stdout and "window cap 60000" in p9.stdout
          and "CAL_WINDOWS 600" in p9.stdout and "TOK_RETOK_EVERY=1000 pinned" in p9.stdout
          and "DATA_DRAW=planned pinned" in p9.stdout and "DATA_SYNTH_HOLDOUT=1 pinned" in p9.stdout
          and "EVAL_RETENTION_EVERY=700 pinned" in p9.stdout)
    check("F9 ... and the guard waits on O13's two WORLD levers, not SR0: five arms, detached among them, "
          "and which of the two this tree declares (neither, today)",
          "All five arms -- fb_off, fb_on, skip, world_off and detached" in p9.stdout
          and "WORLD_FORECAST_BOUND not declared, WORLD_INPUT_GRAD not declared" in p9.stdout
          and "after SR0" not in p9.stdout and "(before SR0" not in p9.stdout, p9.stdout[-900:])
    p9e = gw(EXP="world_epoch", PROBE_EVERY="7x", OUT=os.path.join(TMP, "f9e"))
    check("F9 a PROBE_EVERY that is not a positive window count is refused by name, before anything is written",
          p9e.returncode == 2 and "PROBE_EVERY='7x'" in p9e.stdout and not os.path.exists(os.path.join(TMP, "f9e")))
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
    # SINCE 2026-09-27 EVERY RUN IS `python3 $OUT/code/run.py` (the fleet's private copy), so the stand-in
    # answers any */run.py, records which one it was asked for, and is itself a file named run.py (the
    # fleet recognises its runs by that name, to stop them). STUB_STARTUP, STUB_WSLEEP and STUB_PROG make
    # it slow -- seconds before its banner, seconds per window, a progress line every N windows; STUB_MAXW
    # caps its windows (50) -- for the
    # checks of a live fleet (F18-F24); unset, it answers as before. With STUB_CUDA the torch probe says yes.
    binp = os.path.join(TMP, "bin")
    stub = os.path.join(TMP, "stub", "run.py")
    # STUB_ANALYSIS_SLEEP / STUB_ANALYSIS_KILL hold up or SIGKILL the retok analysis (`python3 - retok ...`),
    # for F20's stop in the analysis and its failed analysis.
    write(os.path.join(binp, "python3"),
          f'#!/bin/bash\nif [[ "${{1:-}}" == run.py || "${{1:-}}" == */run.py ]]; then export STUB_RUNPY="$1"; shift; '
          f'exec "{sys.executable}" "{stub}" "$@"; fi\n'
          f'if [[ "${{1:-}}" == -c && "${{2:-}}" == *torch.cuda.is_available* && -n "${{STUB_CUDA:-}}" ]]; then exit 0; fi\n'
          f'if [[ "${{1:-}}" == - && "${{2:-}}" == retok && -n "${{STUB_ANALYSIS_SLEEP:-}}" ]]; then sleep "$STUB_ANALYSIS_SLEEP"; fi\n'
          f'if [[ "${{1:-}}" == - && "${{2:-}}" == retok && -n "${{STUB_ANALYSIS_KILL:-}}" ]]; then kill -9 $$; fi\n'
          f'exec "{sys.executable}" "$@"\n')
    os.chmod(os.path.join(binp, "python3"), 0o755)
    write(stub, r'''import json, os, sys, time
t0 = time.time()
print(f"=== run.py pid {os.getpid()} started {time.strftime('%H:%M:%SZ', time.gmtime(t0))}: the stand-in", flush=True)
a = sys.argv[1:]
w = int(a[a.index("--max-windows") + 1]); curve = a[a.index("--loss-curve") + 1]
tag = os.path.basename(curve)[:-5]
if os.environ.get("STUB_BOOK"):
    with open(os.environ["STUB_BOOK"], "a") as fh:
        fh.write(json.dumps({"tag": tag, "argv": a, "ckpt": {k: v for k, v in os.environ.items() if k.startswith("CKPT_")},
                             "retok": os.environ.get("TOK_RETOK_EVERY"), "cooldown": os.environ.get("FAB_COOLDOWN"),
                             "runpy": os.environ.get("STUB_RUNPY", ""),
                             "unbuffered": os.environ.get("PYTHONUNBUFFERED", ""),
                             "pins": {k: os.environ.get(k) for k in ("DATA_SYNTH_HOLDOUT", "EVAL_RETENTION_EVERY",
                                                                      "DATA_TRUST")},
                             "env": {k: os.environ.get(k) for k in ("TOK_MINT_NOVEL", "EVAL_HOLDOUT_WINDOWS",
                                                                     "EVAL_RETENTION_N", "EVAL_GENERATE", "DATA_DRAW",
                                                                     "TOK_GROW_EVERY", "DATA_STREAM_BYTES",
                                                                     "DATA_SOURCE", "DATA_REPLAY_SHARE")},
                             "sess": {k: os.environ.get(k) for k in ("RUN_SEED", "RUN_EPOCHS", "DATA_RESAMPLE", "DATA_AREAS",
                                                                      "DATA_N_PROCESSES", "DATA_PHASE_SCHED",
                                                                      "OPT_LR_CONTINUE", "DATA_REPLAY_SHARE",
                                                                      "DATA_REHEARSE_PARENT", "OPT_LR", "FAB_SLOTS",
                                                                      "FAB_BIRTH_JITTER")}}) + "\n")
# A RESUME (EXP=session's sessions, §8 5.3a): the parent's step off its blob, and the run counts its windows from it.
base = 0
if os.environ.get("CKPT_RESUME"):
    import torch
    base = int(torch.load(os.path.join(os.environ["CKPT_RESUME"], "ckpt.pt"), map_location="cpu",
                          weights_only=False)["step"])
time.sleep(float(os.environ.get("STUB_STARTUP", "0")))
print(f"=== device={os.environ.get('RUN_DEVICE', 'cpu')} amp=off")
print(f"=== composed: stage=assembled, 0 refusal(s), 0 warning(s); startup took {time.time() - t0:.1f} s (imports and "
      f"compose), training starts now")
n = min(w, int(os.environ.get("STUB_MAXW", "50")))
ws, every = float(os.environ.get("STUB_WSLEEP", "0")), int(os.environ.get("STUB_PROG", "100"))
for i in range(1, n + 1):
    if ws:
        time.sleep(ws)
    if i > 1 and i % every == 1:
        print(f"[{base + i} windows] loss=2.0000 opt_steps={base + i} n_live=2049 vocab=600 uncalled=0", flush=True)
json.dump([2.0] * n, open(curve, "w"))
if "--flush-bytes" in a:
    json.dump([189] * n, open(a[a.index("--flush-bytes") + 1], "w"))
# --probe-series: A SERIES AS run.py WRITES ONE (RunResult.probe_series) -- a 'phase' reading at each quarter's
# first window and a 'cadence' one mid-quarter, memory-off, over the areas arrived so far (eng and py, then
# num, then c), and R's two 'boundary' readings, memory-off then memory-on (0.01 lower). Each area's report
# is planted, 2.0 + 0.1 x its index + 0.001 x the seed, with STUB_HARM added to num on the act arm without
# TOK_MINT_NOVEL and STUB_HARM_MN on the one with it, +- STUB_SPREAD (STUB_SPREAD_MN) by the seed's parity.
ps_rows = []
# A SESSION'S SERIES (a resume): its resume-start readings over the parent's four areas -- the parent's final,
# 2.0 + 0.1 x the area's index + 0.001 x the seed -- then a phase reading where x5 arrives (6.0) and R over all five:
# each old area F above its start, STUB_F on P and P_twin (the twin +- STUB_TWIN by the seed's parity), STUB_F_PP on
# P_parent, STUB_F_W on W, + STUB_F_NUM on num, + STUB_SPREAD by parity on P and P_parent; x5 at 3.0 - STUB_GAIN
# (STUB_GAIN_PP on P_parent). The start rows and R's carry their pairing as the tree writes it since 2026-10-02:
# against the parent's R, 24 differences of 0 a half; against the start, each old area's F with SD STUB_PW_SD (0.1).
arm = tag.rsplit(".s", 1)[0]
if "--probe-series" in a and base:
    AR, seed = ("eng", "py", "num", "c"), int(os.environ.get("RUN_SEED", "0"))
    E = lambda k, d="0": float(os.environ.get(k, d))
    par = 1 if seed % 2 == 0 else -1
    F = {"P": E("STUB_F") + par * E("STUB_SPREAD"), "P_parent": E("STUB_F_PP") + par * E("STUB_SPREAD"),
         "P_twin": E("STUB_F") + par * E("STUB_SPREAD") + par * E("STUB_TWIN"), "W": E("STUB_F_W")}.get(arm, 0.0)
    v0 = {AR[k]: 2.0 + 0.1 * k + 0.001 * seed for k in range(4)}
    def srow(step, kind, closure, vals, off=0.0, pd=None):
        ars = {k: {"control": v + off, "report": v + off, "seen_by_parent": k != "x5"} for k, v in vals.items()}
        m_ = sum(x["report"] for x in ars.values()) / len(ars)
        r_ = {"step": step, "kind": kind, "closure": closure, "control": m_, "report": m_, "windows": 2 * len(ars),
              "nonfinite": 0, "paired_sd": None, "areas": ars}
        if pd is not None:
            r_["paired"] = {k: {h: [24, pd[k][0], pd[k][1]] for h in ("control", "report")} for k in pd}
        return r_
    vr = {k: v + F + (E("STUB_F_NUM") if k == "num" else 0.0) for k, v in v0.items()}
    vr["x5"] = 3.0 - (E("STUB_GAIN_PP") if arm == "P_parent" else E("STUB_GAIN"))
    p0 = {k: (0.0, 0.0) for k in v0}
    pr = {k: (vr[k] - v0[k], E("STUB_PW_SD", "0.1")) for k in v0}
    ps_rows = [srow(base, "resume", "memory-off", v0, pd=p0), srow(base, "resume", "memory-on", v0, -0.01, pd=p0),
               srow(base + 1, "phase", "memory-off", dict(v0, x5=6.0)),
               srow(base + n, "boundary", "memory-off", vr, pd=pr), srow(base + n, "boundary", "memory-on", vr, -0.01, pd=pr)]
    json.dump(ps_rows, open(a[a.index("--probe-series") + 1], "w"))
elif "--probe-series" in a:
    AR, seed = ("eng", "py", "num", "c"), int(os.environ.get("RUN_SEED", "0"))
    act, mn = int(os.environ.get("TOK_RETOK_EVERY") or 0) > 0, float(os.environ.get("TOK_MINT_NOVEL") or 0) > 0
    def val(k):
        h = 0.0
        if act and AR[k] == "num":
            h = float(os.environ.get("STUB_HARM_MN" if mn else "STUB_HARM", "0"))
            h += (1 if seed % 2 == 0 else -1) * float(os.environ.get("STUB_SPREAD_MN" if mn else "STUB_SPREAD", "0"))
        # THE DRAW PAIR (§8 6.3b): at DATA_DRAW=replay every area, at every reading, moves by STUB_REPLAY, +-
        # STUB_SPREAD_REPLAY by the seed's parity.
        if os.environ.get("DATA_DRAW") == "replay":
            h += float(os.environ.get("STUB_REPLAY", "0"))
            h += (1 if seed % 2 == 0 else -1) * float(os.environ.get("STUB_SPREAD_REPLAY", "0"))
        return 2.0 + 0.1 * k + 0.001 * seed + h
    def row(step, kind, closure, nar, off=0.0):
        ars = {AR[k]: {"control": val(k) + off, "report": val(k) + off, "seen_by_parent": False} for k in range(nar)}
        m = sum(v["report"] for v in ars.values()) / nar
        return {"step": step, "kind": kind, "closure": closure, "control": m, "report": m, "windows": 2 * nar,
                "nonfinite": 0, "paired_sd": None, "areas": ars}
    for q in range(4):
        ps_rows += [row(q * n // 4 + 1, "phase", "memory-off", min(4, q + 2)),
                    row(q * n // 4 + n // 8 + 1, "cadence", "memory-off", min(4, q + 2))]
    ps_rows += [row(n, "boundary", "memory-off", 4), row(n, "boundary", "memory-on", 4, -0.01)]
    json.dump(ps_rows, open(a[a.index("--probe-series") + 1], "w"))
if base:
    print(f"=== {base + n} windows run total ({n} trained by this process, resumed at {base}), {n} flushes this process, "
          f"{base + n} optimizer steps run total, 2 epoch(s) in 1.0s ({n} w/s this process)")
    print(f"       opt.continue.pricing                         logged parent: floor")
    print(f"       fab.resume_widened                           {3 if arm == 'W' else 0}")
    if arm == "P_parent":
        print("       gate:data.rehearse_parent                    ('fired', '4 vs 4')")
else:
    print(f"=== {n} windows, {n} flushes, {n} optimizer steps, 1 epoch(s) in 1.0s ({n} w/s)")
if n == w:
    print(f"WARNING: loop: stopped at max_windows={w} window(s) trained by THIS process")
print(f"       loop.bytes_scored                            {189 * n}")
if ps_rows:
    _r = int(os.environ.get("TOK_RETOK_EVERY") or 0)
    print(f"       loop.acts                                    {(n - 1) // _r if _r else 0}")
    print(f"       eval.holdout.seconds                         1.500000")
    print(f"       eval.holdout.windows                         {sum(r['windows'] for r in ps_rows)}")
    print(f"       data.trust.wall_s                            {float(os.environ.get('STUB_TRUST_S', '0.25')):.6f}")
    print(f"       fab.n_live                                   2049")
# --trust-series (§8 6.3b): the book's passes as run.py writes them (RunResult.trust_series), two cadence passes and the
# epoch's last, with STUB_TRUST_S of seconds over the three, and its counters.
if "--trust-series" in a:
    ts = [{"kind": k, "step": st, "at": 0, "units": 100, "seconds": float(os.environ.get("STUB_TRUST_S", "0.25")) / 3,
           "conflicted_claims": 3, "sources": 37, "evidence": {"eng/a.txt": [1.0, 12]}, "trust": {"eng/a.txt": 0.9}}
          for k, st in (("cadence", n // 3), ("cadence", 2 * n // 3), ("roll", n))]
    json.dump(ts, open(a[a.index("--trust-series") + 1], "w"))
    print("       data.trust.passes                            3")
    print("       data.trust.claims                            208")
    print("       data.trust.conflicted_claims                 3")
    print("       data.trust.sources                           37")
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
# STUB_PARENT=1: A RUN WITH A CKPT_DIR AND NO RESUME SAVES ITS FINAL AS CKPT DOES -- a torch blob holding what
# gpu_world.sh's parent_facts reads: its step, n_live (3000 + 10 x the seed), FAB_SLOTS (EXTRA's, else 4096), its
# areas' generated length at its stream, max(1801, 5000, DATA_STREAM_BYTES // 4) x 2, and 6 x the seed ids minted
# after its last cut (512 + 6 x the seed ids against a last cut at 512) -- with its vocabulary beside its directory.
# (EXP=session's parents, §8 5.3a; a resumed run is left to STUB_FINAL_BYTES.)
if os.environ.get("STUB_PARENT") == "1" and os.environ.get("CKPT_DIR") and not base:
    import torch
    ck, sd = os.environ["CKPT_DIR"], int(os.environ.get("RUN_SEED", "0"))
    os.makedirs(ck, exist_ok=True)
    ln = max(1801, 5000, int(os.environ.get("DATA_STREAM_BYTES", "0")) // 4) * 2
    torch.save({"step": n, "epoch": 1, "reason": "final",
                "geometry": {"fab.slots": (int(os.environ.get("FAB_SLOTS", "4096")), "MAY_WIDEN", "FAB_SLOTS", "")},
                "payload": {"FAB": {"n_live": 3000 + 10 * sd},
                            "DATA": {"bytes_present": {k: ln for k in ("eng", "py", "num", "c")}},
                            "TOK": {"merge_count": 256 + 6 * sd},
                            "LOOP": {"seg_log": {"events": [{"kind": "tokenize", "view": [512, []]}]}}}},
               os.path.join(ck, "ckpt.pt"))
    with open(ck + ".dyntok.json", "w") as fh:
        json.dump({"entries": [[0, 1]] * 256}, fh)
# STUB_FINAL_BYTES=n: A RUN WITH A CKPT_DIR LEAVES ONE FINAL CHECKPOINT n BYTES LONG -- sparse, so it takes
# no disk -- and the smoke's largest checkpoint, which the fleet's disk check sizes every file at, is n. With
# STUB_SLOTS_SCALE=1 it is n x FAB_SLOTS / 4096, as a preallocated fabric's is (EXP=session's W at its own size).
elif os.environ.get("STUB_FINAL_BYTES") and os.environ.get("CKPT_DIR"):
    os.makedirs(os.environ["CKPT_DIR"], exist_ok=True)
    nb = int(os.environ["STUB_FINAL_BYTES"])
    if os.environ.get("STUB_SLOTS_SCALE") == "1":
        nb = nb * int(os.environ.get("FAB_SLOTS", "4096")) // 4096
    with open(os.path.join(os.environ["CKPT_DIR"], "ckpt.pt"), "wb") as fh:
        fh.truncate(nb)
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
    check("F10 ... the block counts them, its resume line carries RUN_SEED, RUN_DEVICE, the stream "
          "(20 x 189 bytes) and the fleet's pins, the keep directory is stamped with the launch, and SUMMARY "
          "records the tree",
          "KEPT: 8 copies of 2 k0 run(s), all coherent" in b10c
          and f"resume one: CKPT_RESUME={kd10}/k0.s0.w11 CKPT_DIR=<NEW dir> OMP_NUM_THREADS=1 RUN_SEED=0 "
              f"RUN_DEVICE=cpu DATA_STREAM_BYTES=3780 TOK_RETOK_EVERY=0 {PINS27} python3 run.py" in b10c
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
    # THE LEVEL REACHES BOTH BOUNDS (2026-10-02, review of 0dfb8e5): EXP=heldout reads each of its two looks at
    # 0.025, and the upper bound was t(0.95) at any level.
    r15f = rule({"kN": [NOISY] * 4, "kX": [HARMFUL] * 4}, 0.05, 0.025)
    check("F15 ... at alpha 0.025 the upper bound is at t(0.975) and Holm's levels are 0.0125 and 0.025",
          (r15f["kX"]["level"], r15f["kN"]["level"]) == (0.0125, 0.025)
          and all(abs(up - (_m + tq(0.975, 2) * _se)) < 1e-12 and abs(lo - (_m - tq(1 - 0.025 / 4, 2) * _se)) < 1e-12
                  for _, _, lo, up in r15f["kN"]["phases"]), str(r15f["kN"]))
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
        return gw("--analyze", EXP="retok", **INC0927, OUT=out)

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
    p15d = gw("--analyze", EXP="retok", **INC0927, OUT=o15d)
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
    # A FLEET OF ONE CADENCE NEVER ESCALATES (the review of 88d3fae): O14 escalates only when both of its
    # cadences and every remedy arm FAIL, and a cadence that FAILs does not ship (note retok fleet (3)). The
    # incumbent alone FAILing withdraws it and names O14's other cadence; a lone challenger FAILing leaves the
    # incumbent, which that fleet does not read, where it stands; a lone incumbent that does not FAIL stays.
    one16 = {v: choose(["k1000"], {"k1000": {"verdict": v}}, {}, "k1000") for v in ("PASS", "FAIL", "UNRESOLVED")}
    one16_3 = choose(["k3000"], {"k3000": {"verdict": "FAIL"}}, {}, "k3000")
    lone16 = choose(["k3000"], {"k3000": {"verdict": "FAIL"}}, {}, "k1000")
    check("F16 a fleet of one cadence never escalates: the incumbent's FAIL does not ship and names O14's other "
          "cadence and the remedy arms as next (3000 after 1000, 1000 after 3000); a lone challenger's FAIL leaves the "
          "incumbent standing; a lone incumbent that PASSes or is UNRESOLVED stays",
          one16["FAIL"][:2] == ("withdraw", "k1000") and "; 3000 and the remedy arms run next" in one16["FAIL"][2]
          and "no ESCALATE" in one16["FAIL"][2]
          and one16_3[:2] == ("withdraw", "k3000") and "; 1000 and the remedy arms run next" in one16_3[2]
          and lone16[:2] == ("stays", "k1000") and "the fleet has no k1000 arm" in lone16[2]
          and "k3000 FAILs" in lone16[2]
          and one16["PASS"][:2] == ("stays", "k1000") and one16["UNRESOLVED"][:2] == ("stays", "k1000"),
          str((one16, one16_3, lone16)))
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
    p17 = gw("--analyze", EXP="retok", **INC0927, OUT=o17)
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
    p17b = gw("--analyze", EXP="retok", **INC0927, OUT=o17b)
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
    p17c = gw("--analyze", EXP="retok", **INC0927, OUT=o17c)
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

    # ---- F25: the cooldown fleet at the shipped cadence (C13's alarm, after the 2026-09-27 DECISION) --------
    # The next test's shape, RETOK_ARMS=1000 COOLDOWN_ARM=100 SEEDS="0 1 2 3 4": arms k0, k1000, k0_nuis and
    # k1000_cd100, read at the DEFAULT incumbent (no RETOK_INCUMBENT: 1000). Every phase of k1000 sits D25[s]
    # above k0's, and every phase of k1000_cd100 sits cd[s] above k1000's, so the cooldown arm's paired
    # difference is cd[s] in every phase and over the whole run (the phases hold equal bytes): its bounds are
    # known answers. The mean is read to its printed 4 decimals, each bound to within one unit of them.
    K25 = {0: 0.0, 1: 0.01, 2: -0.01, 3: 0.005, 4: -0.005}
    D25 = [0.001, -0.002, 0.0005, 0.0015, -0.001]

    def cd_fleet(out, d1, cd):
        summary(out, seeds="0 1 2 3 4")
        for s in range(5):
            base = [2.0 + 0.1 * k + K25[s] for k in range(4)]
            run_ph(out, "k0", s, base)
            run_ph(out, "k0_nuis", s, [b + 0.001 * (s + 1) for b in base])
            run_ph(out, "k1000", s, [b + d1[s] for b in base], acts=15, at=(1001,))
            run_ph(out, "k1000_cd100", s, [b + d1[s] + cd[s] for b in base], acts=15, at=(1001,), cooldown=100)
        run_ph(out, "k0_rerun", 0, [2.0 + 0.1 * k for k in range(4)])
        return gw("--analyze", EXP="retok", OUT=out)

    def cd_line(text):
        m_ = re.search(r"^  k1000_cd100 - k1000 \(C13's cooldown arm, beside the rule, never a ship candidate\) "
                       r"n=(\d+): (p1 .*) -> (\w+); whole run mean (\S+), one-sided 95% upper (\S+): (.*)$", text, re.M)
        if not m_:
            return None
        cells_ = re.findall(r"p\d ([+-]\d\.\d{4}) \[([+-]\d\.\d{4}),([+-]\d\.\d{4})\]", m_.group(2))
        return (int(m_.group(1)), [tuple(map(float, c_)) for c_ in cells_], m_.group(3), float(m_.group(4)),
                float(m_.group(5)), m_.group(6))

    def cd_known(cd):
        n_ = len(cd); m_ = sum(cd) / n_
        se_ = math.sqrt(sum((x - m_) ** 2 for x in cd) / (n_ - 1) / n_)
        return m_, m_ - tq(1 - 0.05 / 4, n_ - 1) * se_, m_ + tq(0.95, n_ - 1) * se_

    def close(got_, want_):
        return abs(got_ - want_) <= 0.00006

    CD_SAME = [0.002, -0.001, 0.0005, 0.001, -0.0015]
    CD_BETTER = [-0.010, -0.012, -0.011, -0.009, -0.013]
    o25 = os.path.join(TMP, "f25", "gpu_retok_out")
    p25 = cd_fleet(o25, D25, CD_SAME)
    a25, b25 = ana(o25)
    ALL["f25"] = a25 + b25
    c25, cb25 = cd_line(a25), cd_line(b25)
    m25, lo25, up25 = cd_known(CD_SAME)
    check("F25 RETOK_ARMS=1000 with COOLDOWN_ARM=100 is read at the default incumbent, 1000, which stays while "
          "k1000 does not FAIL (it is the only cadence: no challenger to compare), in ANALYSIS and in the block",
          p25.returncode == 0
          and "incumbent 1000 (RETOK_INCUMBENT); endpoint" in a25
          and "RULE (O14, O2): ε 0.05 bits/byte, incumbent 1000; per phase (4)" in b25
          and re.search(r"^  k1000 n=5 a=0\.05: p1 .* -> PASS$", a25, re.M) is not None
          and "=== DECISION: TOK_RETOK_EVERY stays 1000 (the incumbent; 0 is never shipped by the rule): k1000 PASS "
              "against k0 (ε 0.05 bits/byte, n 5 seed(s)) ===" in a25
          and re.search(r"^DECISION: TOK_RETOK_EVERY stays 1000 .*\[B-provisional\]$", b25, re.M) is not None,
          str([l for l in a25.splitlines() if "DECISION" in l or "-> " in l]) + p25.stderr[-300:])
    check("F25 k1000_cd100 is read against k1000, paired over the 5 seeds: each phase's mean and eps-rule bounds "
          f"(lower at t(1 - 0.05/4), upper at t(0.95)) are the known {m25:+.4f} [{lo25:+.4f},{up25:+.4f}], PASS, and the "
          "whole run's one-sided 95% upper bound is not below 0 -- in ANALYSIS and, the same line, in the block",
          c25 is not None and c25 == cb25 and c25[0] == 5 and len(c25[1]) == 4
          and all(close(mm, m25) and close(ll, lo25) and close(uu, up25) for mm, ll, uu in c25[1])
          and c25[2] == "PASS" and close(c25[3], m25) and close(c25[4], up25) and c25[5] == "not below 0",
          str(c25))
    o25b = os.path.join(TMP, "f25b", "gpu_retok_out")
    cd_fleet(o25b, D25, CD_BETTER)
    a25b, b25b = ana(o25b)
    ALL["f25b"] = a25b + b25b
    c25b = cd_line(a25b)
    m25b, _, up25b = cd_known(CD_BETTER)
    check("F25 a cooldown arm better at every seed reads 'below 0, significantly better (the longer cooldown costs)' on "
          f"the whole run (known upper {up25b:+.4f}) and still never ships: the DECISION is O14's, 1000 stays",
          c25b is not None and c25b[2] == "PASS" and close(c25b[3], m25b) and close(c25b[4], up25b)
          and c25b[5] == "below 0, significantly better (the longer cooldown costs)"
          and "=== DECISION: TOK_RETOK_EVERY stays 1000" in a25b and "ships 1000_cd100" not in a25b + b25b
          and "(beside the rule)" in b25b, str(c25b))
    o25c = os.path.join(TMP, "f25c", "gpu_retok_out")
    cd_fleet(o25c, [0.30, 0.31, 0.29, 0.30, 0.31], CD_SAME)
    a25c, b25c = ana(o25c)
    ALL["f25c"] = a25c + b25c
    # O14 ESCALATES ONLY WHEN BOTH CADENCES AND EVERY REMEDY ARM FAIL (the review of 88d3fae: this fleet read the
    # FAIL of its one cadence as ESCALATE, the act ON at 1000 until the owner answered, though 3000 never FAILed).
    check("F25 when the shipped 1000 FAILs against k0 -- the only cadence -- it does not ship, and 3000 and the remedy "
          "arms run next (note retok fleet (3)): never ESCALATE, never 0, in ANALYSIS and in the block; and the "
          "cooldown arm is still read beside it",
          "=== DECISION: TOK_RETOK_EVERY 1000 does not ship (0 is never shipped by the rule): k1000 FAILs against k0 "
          "by the ε rule, and it is this fleet's only cadence; 3000 and the remedy arms run next (register O14, note "
          "retok fleet (3)); no ESCALATE, which needs both cadences and every remedy arm to FAIL (ε 0.05 bits/byte, "
          "n 5 seed(s)) ===" in a25c
          and re.search(r"^DECISION: TOK_RETOK_EVERY 1000 does not ship .* \(ε 0\.05 bits/byte, n 5 seed\(s\)\)  "
                        r"\[B-provisional\]$", b25c, re.M) is not None
          and "DECISION: ESCALATE" not in a25c + b25c
          and cd_line(a25c) is not None and cd_line(a25c)[2] == "PASS",
          str([l for l in (a25c + b25c).splitlines() if "DECISION" in l or "-> " in l]))
    # THE LAUNCH BUILDS WHAT THE COMMAND NAMES, with run.py stood in (F10's stand-in, which books each run's
    # TOK_RETOK_EVERY, FAB_COOLDOWN and CKPT_ settings): 5 seeds x 4 arms plus k0_rerun, k1000_cd100 at
    # TOK_RETOK_EVERY=1000 and FAB_COOLDOWN=100, no checkpoint setting at KEEP_CKPT=0, and a block.
    o25d = os.path.join(TMP, "f25d", "gpu_retok_out")
    book25 = os.path.join(TMP, "f25d_book.jsonl")
    p25d = subprocess.run(["bash", SCRIPT], cwd=ROOT, capture_output=True, text=True, timeout=300,
                          env=clean_env(PATH=env10["PATH"], STUB_BOOK=book25, EXP="retok", RETOK_ARMS="1000",
                                        COOLDOWN_ARM="100", SEEDS="0 1 2 3 4", KEEP_CKPT="0", DEVICE="cpu",
                                        WINDOWS=20, PAR=12, SMOKE_WINDOWS=5, OUT=o25d))
    rec25 = [json.loads(l) for l in open(book25)] if os.path.exists(book25) else []
    fleet25 = {r["tag"]: r for r in rec25 if "/smoke/" not in r["argv"][r["argv"].index("--loss-curve") + 1]}
    want25 = {f"{a}.s{s}" for a in ("k0", "k1000", "k0_nuis", "k1000_cd100") for s in range(5)} | {"k0_rerun.s0"}
    check("F25 the launch (EXP=retok RETOK_ARMS=1000 COOLDOWN_ARM=100 SEEDS='0 1 2 3 4' KEEP_CKPT=0) runs the 21 "
          "runs it names: k1000_cd100 at TOK_RETOK_EVERY=1000 and FAB_COOLDOWN=100, k1000 at the default cooldown, "
          "k0 and k0_nuis at 0, no CKPT_ setting, no k3000; and it ends in its block",
          p25d.returncode == 0 and set(fleet25) == want25
          and all(fleet25[f"k1000_cd100.s{s}"]["retok"] == "1000" and fleet25[f"k1000_cd100.s{s}"]["cooldown"] == "100"
                  and fleet25[f"k1000.s{s}"]["retok"] == "1000" and fleet25[f"k1000.s{s}"]["cooldown"] is None
                  and fleet25[f"k0.s{s}"]["retok"] == "0" for s in range(5))
          and not any(r["ckpt"] for r in rec25)
          and "=== plan: EXP=retok; arms k0 k1000 k0_nuis k1000_cd100, plus k0_rerun at seed 0" in p25d.stdout
          and 0 < len(block_of(p25d.stdout) or []) <= 80,
          f"rc {p25d.returncode}; {sorted(set(fleet25) ^ want25)}; {p25d.stderr[-400:]}")

    # ---- F26: the 2026-09-27 archive, re-read on a copy (the review of 88d3fae) ------------------------------
    # --analyze rewrites ANALYSIS.txt and the block and repacks <name>_<launch date>.tgz beside OUT, so the re-read
    # the contract and RESULTS.md document runs on a copy unpacked in a scratch directory, never beside the
    # committed archive. At RETOK_INCUMBENT=3000 it reproduces the fleet's ANALYSIS.txt but two things: the eps
    # rule header's wording, and the KEPT section's disk and resume lines, which need the checkpoints the archive
    # does not hold and give way to one line naming KEPT.txt; the block likewise, and its archive line names
    # this OUT. At the default incumbent the same runs read "stays 1000".
    import hashlib
    ARCHIVE_0927 = os.path.join(ROOT, "results", "gpu_retok_2026-09-27", "gpu_retok_2026-09-27.tgz")
    if not os.path.exists(ARCHIVE_0927):
        print("SKIP F26 -- needs results/gpu_retok_2026-09-27/'s archive")
    else:
        sha26 = hashlib.sha256(open(ARCHIVE_0927, "rb").read()).hexdigest()
        r26 = {}
        for side, env26 in (("inc3000", INC0927), ("default", {})):
            d26 = os.path.join(TMP, "f26_" + side)
            os.makedirs(d26)
            shutil.copy(ARCHIVE_0927, d26)
            with tarfile.open(os.path.join(d26, os.path.basename(ARCHIVE_0927))) as tf:
                tf.extractall(d26)
            o26 = os.path.join(d26, "gpu_retok_out")
            was = {f: open(os.path.join(o26, f)).read() for f in ("ANALYSIS.txt", "PASTE_BACK.txt", "KEPT.txt")}
            p26 = gw("--analyze", EXP="retok", **env26, OUT=o26)
            now = {f: (open(os.path.join(o26, f)).read() if os.path.exists(os.path.join(o26, f)) else None)
                   for f in was}
            tgz26 = os.path.join(d26, os.path.basename(ARCHIVE_0927))
            r26[side] = (p26, was, now, o26, tarfile.open(tgz26).getnames() if os.path.exists(tgz26) else [])
        p26, was, now, o26, names26 = r26["inc3000"]
        from_kept = ("  read from KEPT.txt, as the fleet's own analysis wrote it: this directory holds no ckpt/ (an "
                     "archive packs none), so no disk figure and no resume line")
        want_a26 = []
        for l in was["ANALYSIS.txt"].splitlines():
            if l.startswith("  resume one: "):
                continue
            want_a26.append(from_kept if l.startswith("  disk: ") else
                            l.replace("incumbent 3000 (the interim default);", "incumbent 3000 (RETOK_INCUMBENT);"))
        want_b26 = []
        for l in was["PASTE_BACK.txt"].splitlines():
            if l.startswith("  resume one: "):
                continue
            want_b26.append(l.replace("; ckpt/ 9.93 GB", "; read from KEPT.txt (no ckpt/ here)")
                            .replace("beside gpu_retok_out (", f"beside {o26} ("))
        diff26 = [(a_, b_) for a_, b_ in zip(want_a26, (now["ANALYSIS.txt"] or "").splitlines()) if a_ != b_][:3]
        check("F26 --analyze of a copy of the 2026-09-27 archive at RETOK_INCUMBENT=3000 reproduces its ANALYSIS.txt "
              "but the eps rule header's wording and the KEPT section's disk and resume lines (one line names "
              "KEPT.txt in their place), and its block but the KEPT line's tail, the resume line and the archive "
              "line's OUT; the DECISION is the fleet's, 1000 replacing 3000",
              p26.returncode == 0 and (now["ANALYSIS.txt"] or "").splitlines() == want_a26
              and (now["PASTE_BACK.txt"] or "").splitlines() == want_b26
              and "DECISION: TOK_RETOK_EVERY ships 1000, replacing the incumbent 3000: k1000 PASS against k0, and the "
                  "whole-run 1000 - 3000 upper bound -0.0035 is below 0" in (now["PASTE_BACK.txt"] or ""),
              f"{diff26}; {p26.stderr[-300:]}")
        check("F26 ... its KEPT.txt stays as the fleet wrote it (57 coherent copies) and the archive it repacks holds "
              "it; the committed archive is untouched",
              now["KEPT.txt"] == was["KEPT.txt"] and was["KEPT.txt"].count(" coherent") == 57
              and "gpu_retok_out/KEPT.txt" in names26
              and hashlib.sha256(open(ARCHIVE_0927, "rb").read()).hexdigest() == sha26,
              str(names26[:3]))
        a26d = r26["default"][2]["ANALYSIS.txt"] or ""
        check("F26 ... and at the default incumbent the same runs read 'stays 1000'",
              "=== DECISION: TOK_RETOK_EVERY stays 1000 (the incumbent; 0 is never shipped by the rule): k1000 PASS "
              "against k0; k3000 UNRESOLVED, the whole-run 3000 - 1000 upper bound +0.0188 is not below 0" in a26d,
              str([l for l in a26d.splitlines() if "DECISION" in l]))

    # ---- F18-F24: a fleet that says it is alive, and only one per OUT (2026-09-27) --------------------
    # Live fleets of the stand-in above, slowed down (STUB_STARTUP seconds before its banner, STUB_WSLEEP a
    # window), each in the background with its output in a log, the way the owner launches one. Every wait
    # is on the fleet's own STATE or logs, never on a fixed sleep alone.
    import signal
    import socket
    import time
    import urllib.error
    import urllib.request
    DASH = os.path.join(ROOT, "tools", "fleet_dash.sh")
    LAUNCHER = os.path.join(ROOT, "tools", "gpu_launch.sh")
    SLOW = dict(STUB_STARTUP="3", STUB_WSLEEP="0.1", STUB_PROG="5", STUB_MAXW="10")
    BASE = dict(EXP="retok", DEVICE="cpu", WINDOWS=20, SEEDS="0", SMOKE_WINDOWS=10, KEEP_CKPT=0)

    def st_of(out):
        d = {}
        try:
            for ln in open(os.path.join(out, "STATE")):
                k, eq, val = ln.rstrip("\n").partition("=")
                if eq:
                    d[k] = val
        except OSError:
            pass
        return d

    def wait_for(pred, timeout=120.0):
        t_ = time.time()
        while time.time() - t_ < timeout:
            if pred():
                return True
            time.sleep(0.2)
        return False

    def own(out):
        """[(pid, kind)] of the live processes fleet_dash.sh counts as the fleet's own (a transient `sleep`
        aside: the heartbeat's last one-second sleep outlives it by under a second, and holds no lock)."""
        r = subprocess.run(["bash", DASH, "--scan", "own", out], capture_output=True, text=True, timeout=60)
        return [tuple(ln.split("\t")[:2]) for ln in r.stdout.splitlines()
                if ln.strip() and ln.split("\t")[1] != "transient"]

    def dfl():
        # A child that can trap INT, TERM and HUP whatever this process ignores (a test run under nohup,
        # or in the background of a script, would otherwise hand it a signal ignored at entry).
        for s_ in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            signal.signal(s_, signal.SIG_DFL)

    def dfl_group():
        # ... and in a process group of its own, as a terminal's foreground job is: a Ctrl-C or a hang-up
        # reaches every process in it, which os.killpg reproduces.
        dfl()
        os.setpgid(0, 0)

    def fleet(out, log, argv=("bash", SCRIPT), cwd=ROOT, group=False, **env):
        """A launch in the background, its output in `log` (the fleet log STATE names); with `group`, in a
        process group of its own."""
        fh = open(log, "w")
        e = dict(BASE, PATH=env10["PATH"], OUT=out)
        e.update(env)
        return subprocess.Popen(list(argv), cwd=cwd, env=clean_env(**e), stdout=fh, stderr=subprocess.STDOUT,
                                preexec_fn=dfl_group if group else dfl), fh

    def txt(path):
        """A file's text, '' where it is missing (a check reads a file a regressed fleet did not write)."""
        try:
            with open(path, errors="replace") as fh_:
                return fh_.read()
        except OSError:
            return ""

    def lock_free(out):
        """Nothing holds the fleet's lock, <OUT>.lock (an orphaned run inherits it)."""
        import fcntl
        try:
            fd_ = os.open(out + ".lock", os.O_RDWR)
        except OSError:
            return True
        try:
            fcntl.flock(fd_, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False
        finally:
            os.close(fd_)

    def done(p_, fh, timeout=300):
        try:
            rc_ = p_.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            p_.kill()
            rc_ = None
        fh.close()
        return rc_

    def training(logpath):
        return lambda: "=== composed:" in (open(logpath).read() if os.path.exists(logpath) else "")

    def status(out, *extra):
        r = subprocess.run(["bash", SCRIPT, "--status", *extra], cwd=ROOT, capture_output=True, text=True,
                           timeout=120, env=clean_env(OUT=out, EXP="retok"))
        return r.returncode, r.stdout

    # ---- F18: one fleet per OUT -----------------------------------------------------------------------
    o18 = os.path.join(TMP, "f18", "gpu_retok_out")
    pA, fA = fleet(o18, os.path.join(TMP, "f18a.log"), PAR=5, HB_EVERY=1, **SLOW)
    up = wait_for(lambda: st_of(o18).get("phase") == "smoke")
    first18 = open(os.path.join(o18, "SUMMARY.txt")).readline() if up else ""
    p18 = gw(OUT=o18, PAR=1, PATH=env10["PATH"], **BASE)
    check("F18 a second launch into a live OUT is refused (exit 2) and moves nothing -- the live fleet's SUMMARY is "
          "untouched and no <OUT>.<stamp> appears -- and it says which fleet runs, where it is, why the card may read "
          "idle, and how to watch and stop it",
          up and p18.returncode == 2 and "A FLEET IS ALREADY RUNNING IN" in p18.stdout and "its lock" in p18.stdout
          and "#####  RUNNING  #####" in p18.stdout and "stage      smoke" in p18.stdout
          and f"watch it:  bash {DASH} {os.path.realpath(o18)}" in p18.stdout
          and f"stop it:   EXP=retok OUT={o18} bash {SCRIPT} --stop" in p18.stdout
          and "on the CPU" in p18.stdout and not glob.glob(o18 + ".20*")
          and open(os.path.join(o18, "SUMMARY.txt")).readline() == first18,
          f"rc {p18.returncode}; {p18.stdout[:400]!r}")
    rcA = done(pA, fA)
    lA = open(os.path.join(TMP, "f18a.log")).read()
    check("F18 ... and the live fleet runs on to its own end: rc 0, its block, STATE end=finished, and STATE's pid is "
          "the launched one (the re-execution of its private copy keeps the pid, and the lock with it)",
          rcA == 0 and block_of(lA) is not None and st_of(o18).get("end") == "finished"
          and st_of(o18).get("pid") == str(pA.pid), f"rc {rcA}; {st_of(o18)}")
    # A FLEET THE LOCK CANNOT SEE: a run.py writing under OUT for a gpu_world.sh from before the lock (no
    # GW_FLEET_OUT in its environment), found by its command line.
    o18b = os.path.join(TMP, "f18b", "gpu_retok_out")
    summary(o18b, seeds="0")
    os.makedirs(os.path.join(o18b, "logs"), exist_ok=True)
    stray = subprocess.Popen([os.path.join(binp, "python3"), "run.py", "--max-windows", "50", "--loss-curve",
                              os.path.join(o18b, "logs", "k0.s0.json")], cwd=TMP, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, env=clean_env(PATH=env10["PATH"], STUB_WSLEEP="2"))
    seen = wait_for(lambda: ("run" in [k for _, k in own(o18b)]), 30)
    p18b = gw(OUT=o18b, PAR=1, PATH=env10["PATH"], **BASE)
    stray.kill()
    stray.wait()
    p18c = gw(OUT=o18b, PAR=1, PATH=env10["PATH"], **BASE)
    aside18 = os.path.realpath(o18b) + ".2026-10-01T120000Z"
    check("F18 a fleet the lock cannot see -- a run.py writing under OUT, launched by a gpu_world.sh from before the "
          "lock -- is found in /proc and refused the same way, nothing moved; gone, its dead fleet is moved aside as "
          "before and the launch runs",
          seen and p18b.returncode == 2 and "a fleet the lock cannot see" in p18b.stdout and str(stray.pid) in p18b.stdout
          and p18c.returncode == 0 and os.path.isfile(os.path.join(aside18, "SUMMARY.txt"))
          and f"moved aside, whole, to {aside18}" in open(os.path.join(o18b, "SUMMARY.txt")).read(),
          f"seen {seen}; rc {p18b.returncode}/{p18c.returncode}; {p18b.stdout[:300]!r}")

    # ---- F19: the heartbeat and the step lines -----------------------------------------------------------
    # PAR auto with LADDER 1: a smoke, one calibration step, the fleet. clean_env exports OMP_NUM_THREADS=1,
    # which GNU nproc reports instead of the cores; the fleet sizes itself by the cores all the same.
    o19 = os.path.join(TMP, "f19", "gpu_retok_out")
    log19, book19 = os.path.join(TMP, "f19.log"), os.path.join(TMP, "f19_book.jsonl")
    p19, f19 = fleet(o19, log19, HB_EVERY=1, LADDER="1", CAL_WINDOWS=20, STUB_BOOK=book19, STUB_STARTUP="2",
                     STUB_WSLEEP="0.25", STUB_PROG="5", STUB_MAXW="12")
    frames19, st19 = {}, {}

    def grab(tag, pred):
        if wait_for(pred, 120):
            frames19[tag] = subprocess.run(["bash", DASH, "--once", o19], capture_output=True, text=True,
                                           timeout=60).stdout
            st19[tag] = status(o19)

    smoke_started = os.path.join(o19, "smoke", "_started.txt")
    grab("smoke-cpu", lambda: os.path.exists(smoke_started) and len(open(smoke_started).read().splitlines()) == 4)
    grab("smoke-train", training(os.path.join(o19, "smoke", "k0.s0.log")))
    grab("cal", lambda: st_of(o19).get("step") == "k=1" and training(os.path.join(o19, "cal", "k1", "cal.s1001.log"))())
    grab("fleet", lambda: st_of(o19).get("phase") == "fleet" and training(os.path.join(o19, "logs", "k0.s0.log"))())
    rc19 = done(p19, f19)
    L19 = open(log19).read()
    hb19 = re.findall(r"^\[hb (\d\d):(\d\d):(\d\d)Z\] (\w+)[^|]*\| (\S+(?: k=\d+)?) since", L19, re.M)
    gaps = [((int(b[0]) * 3600 + int(b[1]) * 60 + int(b[2])) - (int(a[0]) * 3600 + int(a[1]) * 60 + int(a[2]))) % 86400
            for a, b in zip(hb19, hb19[1:])]
    phases19 = {x[4] for x in hb19}
    check("F19 the heartbeat: a line every HB_EVERY seconds in the fleet log -- through the smoke, the calibration step "
          "and the fleet, each naming its stage and RUNNING -- never more than a few seconds apart",
          rc19 == 0 and {"smoke", "cal k=1", "fleet"} <= phases19 and all(x[3] == "RUNNING" for x in hb19)
          and gaps and max(gaps) <= 4, f"rc {rc19}; phases {sorted(phases19)}; max gap {max(gaps or [0])}")
    S19 = open(os.path.join(o19, "SUMMARY.txt")).read()
    check("F19 each step says when its runs START, and that they build on the CPU before the GPU, in the log and in "
          "SUMMARY; the smoke measures that startup (run.py's '=== composed ... startup took') and the later steps "
          "quote it",
          all(x in S19 and x in L19 for x in ("4 run(s) start ", "Each builds on the CPU first",
                                               "k=1: 1 run(s) x 20 windows start ", "on the CPU first (the GPU reads idle;",
                                               "longer when the CPU is shared", "each spends ~2."))
          and re.search(r"^  startup: each smoke run built on the CPU for 2\.\d s \(median of 4;", S19, re.M) is not None
          and st_of(o19).get("startup_s", "").startswith("2."),
          str([ln for ln in S19.splitlines() if "CPU" in ln]))
    hbfile = open(os.path.join(o19, "HEARTBEAT")).read().splitlines() if os.path.exists(os.path.join(o19, "HEARTBEAT")) else []
    recs19 = [json.loads(ln) for ln in open(book19)] if os.path.exists(book19) else []
    check("F19 a heartbeat names the runs starting on the CPU and those training, with their windows; HEARTBEAT holds "
          "the last line and its JSON sample, heartbeat.log the history; every run was unbuffered "
          "(PYTHONUNBUFFERED=1) and ran the fleet's own copy, $OUT/code/run.py",
          re.search(r"\| 4 run\(s\): 4 on CPU, 0 training", L19) is not None
          and re.search(r"\| 4 run\(s\): 0 on CPU, 4 training \(w (<101|\d+-\d+)/10\)", L19) is not None
          and len(hbfile) == 2 and hbfile[0].startswith("[hb ") and json.loads(hbfile[1]).get("hist")
          and os.path.getsize(os.path.join(o19, "heartbeat.log")) > 0
          and len(recs19) >= 10 and all(r["unbuffered"] == "1" for r in recs19)
          and {r["runpy"] for r in recs19} == {os.path.join(os.path.realpath(o19), "code", "run.py")},
          f"{len(recs19)} runs; {sorted({r['runpy'] for r in recs19})}")
    # THE CORES, NOT OMP_NUM_THREADS: this box's cores as nproc counts them without the OMP variables, then
    # the cgroup quota where it is lower -- the script's own rule -- whatever the exported OMP_NUM_THREADS=1.
    ncore = int(subprocess.run(["nproc"], capture_output=True, text=True,
                               env={k: v for k, v in os.environ.items() if not k.startswith("OMP_")}).stdout)

    def quota19():
        try:
            a_, b_ = open("/sys/fs/cgroup/cpu.max").read().split()
            return None if a_ == "max" else int(a_) / int(b_)
        except (OSError, ValueError):
            pass
        try:
            a_ = int(open("/sys/fs/cgroup/cpu/cpu.cfs_quota_us").read())
            b_ = int(open("/sys/fs/cgroup/cpu/cpu.cfs_period_us").read())
            return None if a_ <= 0 else a_ / b_
        except (OSError, ValueError):
            return None

    q19 = quota19()
    cores19 = max(1, int(q19)) if q19 and max(1, int(q19)) < ncore else ncore
    check(f"F19 the fleet sizes itself by this box's cores ({cores19}), not by the OMP_NUM_THREADS=1 it was launched "
          "with (GNU nproc reports that instead of the cores: the fleet ran one run at a time)",
          f"=== {cores19} CPU core(s), 0 GPU(s), device=cpu" in S19
          and f"=== ceiling: {max(1, cores19 - 1)} by CPU" in S19,
          str([ln for ln in S19.splitlines() if "core" in ln or "ceiling" in ln]))

    # ---- F20: a stop writes its block ------------------------------------------------------------------
    # TERM TO THE SHELL, as --stop sends it; INT AND HUP TO THE WHOLE PROCESS GROUP, as a terminal sends a
    # Ctrl-C and a hang-up (the review of 2026-09-27: INT to the shell's pid alone never met the run_job it
    # killed, so this check passed while a Ctrl-C left the run training as an orphan).
    for sig, name, want in ((signal.SIGTERM, "TERM", 143), (signal.SIGHUP, "HUP", 129), (signal.SIGINT, "INT", 130)):
        o20 = os.path.join(TMP, f"f20{name}", "gpu_retok_out")
        log20 = os.path.join(TMP, f"f20{name}.log")
        grp = name != "TERM"
        p20, f20 = fleet(o20, log20, group=grp, HB_EVERY=1, LADDER="1", CAL_WINDOWS=40, STUB_STARTUP="0.5",
                         STUB_WSLEEP="0.3", STUB_PROG="5", STUB_MAXW="12")
        ready = wait_for(lambda: st_of(o20).get("step") == "k=1"
                         and training(os.path.join(o20, "cal", "k1", "cal.s1001.log"))())
        if grp:
            os.killpg(p20.pid, sig)
        else:
            os.kill(p20.pid, sig)
        rc20 = done(p20, f20)
        L20 = open(log20).read()
        b20 = "\n".join(block_of(L20) or [])
        gone = wait_for(lambda: not own(o20), 10)
        done20 = open(os.path.join(o20, "cal", "k1", "_done.txt")).read() if os.path.exists(
            os.path.join(o20, "cal", "k1", "_done.txt")) else ""
        check(f"F20 SIG{name} {'to the whole process group' if grp else 'to the shell'} during a calibration step stops "
              f"the fleet with a reason: exit {want}, 'STOPPED by SIG{name} ... during calibration k=1' in its log and "
              "its block, STATE end=stopped, its run stopped by the fleet and booked (its _done line rc=143), nothing "
              "of it left running, the lock free, and the archive packed",
              ready and rc20 == want and re.search(rf"^!! gpu_world\.sh STOPPED by SIG{name} at \d\d:\d\d:\d\dZ during "
                                                   rf"calibration k=1 \(pid {p20.pid}\)$", L20, re.M) is not None
              and re.search(r"^   stopping 1 run\(s\): pid \d+$", L20, re.M) is not None
              and f"STOPPED BEFORE THE ANALYSIS: stopped by SIG{name} during calibration k=1" in b20
              and st_of(o20).get("end") == "stopped" and st_of(o20).get("rc") == str(want)
              and "cal.s1001 rc=143" in done20 and gone and lock_free(o20)
              and glob.glob(os.path.join(os.path.dirname(o20), "gpu_retok_*.tgz")),
              f"ready {ready}; rc {rc20}; gone {gone}; lock free {lock_free(o20)}; {done20!r}; {L20[-300:]!r}")
    # A `| tee log` LAUNCH WHOSE tee DIES WITH THE GROUP (a Ctrl-C, a closed terminal): the stop still writes
    # SUMMARY's STOPPED line, the block and the archive, and STATE records rc 129 (a write to the dead pipe
    # raised SIGPIPE, and bash ran its EXIT trap at once with $? = 0: no archive, rc=0).
    o20t = os.path.join(TMP, "f20tee", "gpu_retok_out")
    p20t, f20t = fleet(o20t, os.path.join(TMP, "f20tee.log"), group=True,
                       argv=("bash", "-c", f'bash "{SCRIPT}" 2>&1 | tee "{o20t}.teelog" > /dev/null'),
                       HB_EVERY=1, LADDER="1", CAL_WINDOWS=40, STUB_STARTUP="0.5", STUB_WSLEEP="0.3", STUB_PROG="5",
                       STUB_MAXW="12")
    ready = wait_for(lambda: st_of(o20t).get("step") == "k=1"
                     and training(os.path.join(o20t, "cal", "k1", "cal.s1001.log"))())
    pid20t = st_of(o20t).get("pid", "")
    os.killpg(p20t.pid, signal.SIGHUP)
    done(p20t, f20t)
    ended20t = wait_for(lambda: st_of(o20t).get("end") == "stopped", 60)
    gone20t = wait_for(lambda: not own(o20t), 10)
    S20t = open(os.path.join(o20t, "SUMMARY.txt")).read()
    check("F20 a `bash gpu_world.sh 2>&1 | tee log` launch hung up with its tee: its stop is not cut short by the dead "
          "pipe -- SUMMARY's 'STOPPED by SIGHUP' line, the run booked rc=143, STATE rc=129, the block and the archive",
          ready and ended20t and f"STOPPED by SIGHUP" in S20t and f"(pid {pid20t})" in S20t
          and st_of(o20t).get("rc") == "129"
          and "cal.s1001 rc=143" in txt(os.path.join(o20t, "cal", "k1", "_done.txt"))
          and "STOPPED BEFORE THE ANALYSIS: stopped by SIGHUP" in txt(os.path.join(o20t, "PASTE_BACK.txt"))
          and glob.glob(os.path.join(os.path.dirname(o20t), "gpu_retok_*.tgz")) and gone20t,
          f"ready {ready}; ended {ended20t}; gone {gone20t}; {st_of(o20t)}")
    # UNDER nohup A HANG-UP IS IGNORED -- bash cannot trap a signal ignored at entry -- and the fleet runs on.
    o20n = os.path.join(TMP, "f20nohup", "gpu_retok_out")
    p20n, f20n = fleet(o20n, os.path.join(TMP, "f20nohup.log"), argv=("nohup", "bash", SCRIPT), PAR=5, HB_EVERY=1,
                       STUB_STARTUP="1", STUB_WSLEEP="0.2", STUB_MAXW="12")
    up20 = wait_for(lambda: st_of(o20n).get("phase") == "smoke")
    os.kill(p20n.pid, signal.SIGHUP)
    time.sleep(1.5)
    alive20 = p20n.poll() is None
    rc20n = done(p20n, f20n)
    check("F20 under nohup a hang-up is ignored, as before (a closed terminal stops nothing): the fleet runs on to rc 0 "
          "and its analysis",
          up20 and alive20 and rc20n == 0 and st_of(o20n).get("end") == "finished"
          and "STOPPED by" not in open(os.path.join(TMP, "f20nohup.log")).read(), f"alive {alive20}; rc {rc20n}")
    # AT DEVICE=cuda, WITH MPS: nvidia-smi and nvidia-cuda-mps-control stood in (the daemon forks away,
    # serves a FIFO in CUDA_MPS_PIPE_DIRECTORY, and books its open fds and its quit).
    cbin = os.path.join(TMP, "cbin")
    write(os.path.join(cbin, "nvidia-smi"), r'''#!/bin/bash
q=""; for a in "$@"; do case "$a" in --query-gpu=*) q=${a#--query-gpu=} ;; esac; done
case "$q" in
  index) echo 0 ;;
  memory.total) echo 143771 ;;
  index,name,memory.total,memory.used) echo "index, name, memory.total [MiB], memory.used [MiB]"; echo "0, NVIDIA H200, 143771 MiB, 1 MiB" ;;
  index,utilization.gpu,memory.used,memory.total) while :; do echo "0, 37, 2048, 143771"; sleep 2; done ;;
  utilization.gpu,memory.used,memory.total) echo "37, 2048, 143771" ;;
  *) echo "NVIDIA-SMI stand-in" ;;
esac
''')
    write(os.path.join(cbin, "fake_mps.py"), r'''import os, sys, time
book = os.environ.get("MPS_BOOK", "/dev/null")
def log(m):
    with open(book, "a") as fh:
        fh.write(m + "\n")
d = os.environ.get("CUDA_MPS_PIPE_DIRECTORY", "/tmp/nvidia-mps")
ctl = os.path.join(d, "control")
if sys.argv[1:] == ["-d"]:
    os.makedirs(d, exist_ok=True)
    if os.fork() == 0:
        os.setsid()
        if os.fork() == 0:
            n = os.open(os.devnull, os.O_RDWR)
            for i in (0, 1, 2):
                os.dup2(n, i)
            if os.path.exists(ctl):
                os.unlink(ctl)
            os.mkfifo(ctl)
            log(f"daemon {os.getpid()} fds {sorted(int(x) for x in os.listdir('/proc/self/fd'))}")
            while True:
                with open(ctl) as fh:
                    for line in fh:
                        if line.strip() == "quit":
                            log(f"daemon {os.getpid()} quits")
                            os.unlink(ctl)
                            os._exit(0)
        os._exit(0)
    for _ in range(300):
        if os.path.exists(ctl):
            break
        time.sleep(0.01)
    sys.exit(0)
try:
    fd = os.open(ctl, os.O_WRONLY | os.O_NONBLOCK)
except OSError:
    print("Cannot find MPS control daemon process")
    sys.exit(1)
os.write(fd, sys.stdin.read().encode())
os.close(fd)
for _ in range(100):
    if not os.path.exists(ctl):
        break
    time.sleep(0.05)
''')
    write(os.path.join(cbin, "nvidia-cuda-mps-control"),
          f'#!/bin/bash\nexec -a nvidia-cuda-mps-control "{sys.executable}" "{os.path.join(cbin, "fake_mps.py")}" "$@"\n')
    for f_ in ("nvidia-smi", "nvidia-cuda-mps-control"):
        os.chmod(os.path.join(cbin, f_), 0o755)
    CPATH = binp + os.pathsep + cbin + os.pathsep + os.environ.get("PATH", "")
    o20c = os.path.join(TMP, "f20cuda", "gpu_retok_out")
    mbook = os.path.join(TMP, "f20cuda_mps.book")
    p20c, f20c = fleet(o20c, os.path.join(TMP, "f20cuda.log"), PATH=CPATH, DEVICE="cuda", STUB_CUDA=1, MPS_BOOK=mbook,
                       HB_EVERY=1, LADDER="1", CAL_WINDOWS=40, STUB_STARTUP="0.5", STUB_WSLEEP="0.3", STUB_PROG="5",
                       STUB_MAXW="12")
    ready = wait_for(lambda: st_of(o20c).get("step") == "k=1"
                     and training(os.path.join(o20c, "cal", "k1", "cal.s1001.log"))())
    os.kill(p20c.pid, signal.SIGTERM)
    rc20c = done(p20c, f20c)
    mb = open(mbook).read() if os.path.exists(mbook) else ""
    fds = [int(x) for x in re.findall(r"fds \[([\d, ]+)\]", mb)[0].split(",")] if "fds [" in mb else [9]
    check("F20 at DEVICE=cuda the stop still quits MPS, after its runs are gone; the MPS daemon never held the fleet's "
          "lock (fd 9), so a killed fleet's daemon cannot keep the next launch out",
          ready and rc20c == 143 and "CUDA MPS started" in open(os.path.join(o20c, "SUMMARY.txt")).read()
          and mb.count("quits") == 1 and 9 not in fds and st_of(o20c).get("mps_pipe", "").endswith("/mps/pipe")
          and "STOPPED by SIGTERM" in open(os.path.join(TMP, "f20cuda.log")).read(),
          f"ready {ready}; rc {rc20c}; {mb!r}")

    def archived_block(out):
        """PASTE_BACK.txt as the archive beside OUT holds it ('' without one)."""
        for a_ in glob.glob(os.path.join(os.path.dirname(out), "gpu_retok_*.tgz")):
            with tarfile.open(a_) as tf:
                try:
                    return tf.extractfile(os.path.basename(out) + "/PASTE_BACK.txt").read().decode()
                except KeyError:
                    return ""
        return ""

    # A TERM IN THE ANALYSIS (a --stop at the wrong moment): bash holds the trap until the analysis -- held
    # up 3 s here -- ends; the block and the archive follow, and the fleet ends FINISHED (the review of
    # 2026-09-27: the stop replaced the finished block, and the archive's, with 'STOPPED BEFORE THE ANALYSIS').
    o20a = os.path.join(TMP, "f20ana", "gpu_retok_out")
    p20a, f20a = fleet(o20a, os.path.join(TMP, "f20ana.log"), PAR=1, HB_EVERY=1, STUB_ANALYSIS_SLEEP="3",
                       STUB_STARTUP="0.2", STUB_WSLEEP="0.05", STUB_MAXW="12")
    inana = wait_for(lambda: st_of(o20a).get("phase") == "analysis", 120)
    time.sleep(0.5)
    os.kill(p20a.pid, signal.SIGTERM)
    rc20a = done(p20a, f20a)
    L20a = open(os.path.join(TMP, "f20ana.log")).read()
    pb20a = txt(os.path.join(o20a, "PASTE_BACK.txt"))
    check("F20 a TERM during the analysis waits the seconds it takes: rc 0, STATE end=finished naming the signal, the "
          "block and the archived block the analysis's own (its DECISION), and the log saying the signal came",
          inana and rc20a == 0 and st_of(o20a).get("end") == "finished"
          and "a SIGTERM that came during the analysis waited for them" in st_of(o20a).get("reason", "")
          and "DECISION:" in pb20a and "STOPPED" not in pb20a and archived_block(o20a) == pb20a
          and re.search(r"^!! SIGTERM at \d\d:\d\d:\d\dZ during the analysis: every run has ended", L20a, re.M) is not None,
          f"in analysis {inana}; rc {rc20a}; {st_of(o20a).get('reason')}; {pb20a[:200]!r}")
    # AN ANALYSIS THAT DIES -- SIGKILLed here, as the OOM killer would -- ends the fleet STOPPED, never FINISHED
    # (the review of 2026-09-27: the pipeline's status was tee's, and the fleet said FINISHED, "its block
    # written", with no PASTE_BACK.txt); --analyze then reads the runs again, and fails loudly when it fails.
    o20f = os.path.join(TMP, "f20fail", "gpu_retok_out")
    p20f, f20f = fleet(o20f, os.path.join(TMP, "f20fail.log"), PAR=1, HB_EVERY=1, STUB_ANALYSIS_KILL="1",
                       STUB_STARTUP="0.2", STUB_WSLEEP="0.05", STUB_MAXW="12")
    rc20f = done(p20f, f20f)
    pb20f = txt(os.path.join(o20f, "PASTE_BACK.txt"))
    s20f = status(o20f)
    check("F20 an analysis killed ends the fleet STOPPED, not FINISHED: exit 1, STATE end=stopped naming the failed "
          "analysis, the block 'STOPPED AT THE ANALYSIS: the analysis failed (exit 137: killed by signal 9...' with "
          "--analyze as the way on, --status STOPPED (3), and the archive",
          rc20f == 1 and st_of(o20f).get("end") == "stopped"
          and "the analysis failed (exit 137" in st_of(o20f).get("reason", "")
          and "STOPPED AT THE ANALYSIS: the analysis failed (exit 137: killed by signal 9" in pb20f
          and "gpu_world.sh --analyze reads them again" in pb20f and archived_block(o20f) == pb20f
          and s20f[0] == 3 and "the analysis failed" in s20f[1],
          f"rc {rc20f}; {st_of(o20f)}; {pb20f[-300:]!r}")
    a20k = gw("--analyze", EXP="retok", OUT=o20f, PATH=env10["PATH"], STUB_ANALYSIS_KILL="1")
    pb20k = txt(os.path.join(o20f, "PASTE_BACK.txt"))
    a20g = gw("--analyze", EXP="retok", OUT=o20f, PATH=env10["PATH"])
    check("F20 ... --analyze whose analysis dies says so and exits 1, leaving the block and the archive as they were; "
          "run again, it writes the analysis block",
          a20k.returncode == 1 and "!! the analysis FAILED (exit 137" in a20k.stdout and pb20k == pb20f
          and a20g.returncode == 0 and "DECISION:" in "\n".join(block_of(a20g.stdout) or []),
          f"{a20k.returncode} {a20g.returncode}; {a20k.stdout[-300:]!r}")

    # ---- F21: --status says RUNNING, STALLED, FINISHED, STOPPED, DEAD or NO FLEET, by its exit code -----------
    s_run = st19.get("fleet", (None, ""))
    s_fin = status(o19)
    s_stop = status(os.path.join(TMP, "f20TERM", "gpu_retok_out"))
    s_none = status(os.path.join(TMP, "f21", "nothing_here"))
    check("F21 --status reads RUNNING (0) off a live fleet with its stage and each run's state, FINISHED (1) off a "
          "finished one, STOPPED (3) with its reason, and NO FLEET (2) where there is none",
          s_run[0] == 0 and "#####  RUNNING  #####" in s_run[1] and "stage      fleet:" in s_run[1]
          and " training " in s_run[1]
          and s_fin[0] == 1 and "#####  FINISHED  #####" in s_fin[1]
          and s_stop[0] == 3 and "#####  STOPPED  #####" in s_stop[1]
          and "stopped by SIGTERM during calibration k=1" in s_stop[1]
          and s_none[0] == 2 and "#####  NO FLEET  #####" in s_none[1],
          f"{s_run[0]} {s_fin[0]} {s_stop[0]} {s_none[0]}")
    # SIGKILL OF THE SHELL ALONE: its heartbeat watcher sees it vanish, says so, stops its runs, writes the block.
    o21 = os.path.join(TMP, "f21k", "gpu_retok_out")
    log21 = os.path.join(TMP, "f21k.log")
    p21, f21 = fleet(o21, log21, HB_EVERY=1, LADDER="1", CAL_WINDOWS=40, STUB_STARTUP="0.5", STUB_WSLEEP="0.3",
                     STUB_PROG="5", STUB_MAXW="12")
    ready = wait_for(lambda: st_of(o21).get("step") == "k=1" and training(os.path.join(o21, "cal", "k1", "cal.s1001.log"))())
    os.kill(p21.pid, signal.SIGKILL)
    done(p21, f21)
    ended = wait_for(lambda: st_of(o21).get("end") == "died", 30)
    gone = wait_for(lambda: not own(o21), 15)
    k21 = status(o21)
    L21 = open(log21).read()
    check("F21 SIGKILL of the fleet's shell: its heartbeat watcher says so in the log ('THE FLEET'S SHELL (pid N) IS "
          "GONE AND WROTE NO BLOCK, during calibration k=1'), stops what it left, writes the block, and --status "
          "reads DEAD (4), died without a reason of its own",
          ready and ended and gone and k21[0] == 4 and "#####  DEAD  #####" in k21[1]
          and f"THE FLEET'S SHELL (pid {p21.pid}) IS GONE AND WROTE NO BLOCK, during calibration k=1" in L21
          and "vanished during calibration k=1" in "\n".join(block_of(L21) or []),
          f"ready {ready} ended {ended} gone {gone} rc {k21[0]}")
    # SIGKILL OF EVERYTHING (a container stop): nothing is written, and the pid is gone with no end recorded.
    o21b = os.path.join(TMP, "f21all", "gpu_retok_out")
    p21b, f21b = fleet(o21b, os.path.join(TMP, "f21all.log"), HB_EVERY=1, PAR=1, STUB_STARTUP="0.5",
                       STUB_WSLEEP="0.3", STUB_PROG="5", STUB_MAXW="12")
    ready = wait_for(lambda: st_of(o21b).get("phase") == "smoke" and training(os.path.join(o21b, "smoke", "k0.s0.log"))())
    for _round in range(3):                  # the shell first (the lowest pid), then whatever it had started
        for pid_, _k in own(o21b):
            try:
                os.kill(int(pid_), signal.SIGKILL)
            except OSError:
                pass
        time.sleep(0.3)
    done(p21b, f21b)
    k21b = status(o21b)
    check("F21 SIGKILL of the whole fleet (a container stop): no end in STATE and the pid gone -- --status reads DEAD "
          "(4): 'killed without a trap'",
          ready and k21b[0] == 4 and "killed without a trap" in k21b[1] and "end" not in st_of(o21b),
          f"ready {ready} rc {k21b[0]}")
    # A STATE NAMING A LIVE PROCESS THAT IS NOT THE FLEET (this test, at another start time): not RUNNING. A
    # fleet from before STATE is read off its block. A live fleet whose runs print nothing reads STALLED.
    o21c = os.path.join(TMP, "f21c", "gpu_retok_out")
    summary(o21c, seeds="0")
    write(os.path.join(o21c, "STATE"), f"pid={os.getpid()}\npid_start=1\nphase=fleet\nstep_dir={o21c}/logs\n")
    k21c = status(o21c)
    o21d = os.path.join(TMP, "f21d", "gpu_retok_out")
    summary(o21d, seeds="0")
    write(os.path.join(o21d, "PASTE_BACK.txt"), "==== PASTE THIS BACK ====\nSTOPPED BEFORE THE ANALYSIS: a smoke arm "
                                                 "failed\n==== END ====\n")
    k21d = status(o21d)
    o21e = os.path.join(TMP, "f21e", "gpu_retok_out")
    p21e, f21e = fleet(o21e, os.path.join(TMP, "f21e.log"), PAR=1, HB_EVERY=0, STUB_STARTUP="30")
    quiet = wait_for(lambda: os.path.exists(os.path.join(o21e, "smoke", "_started.txt"))
                     and len(open(os.path.join(o21e, "smoke", "_started.txt")).read().splitlines()) == 4, 60)
    time.sleep(5)
    k21e = subprocess.run(["bash", DASH, "--status", "--stall-min", "0.05", o21e], capture_output=True, text=True,
                          timeout=60)
    os.kill(p21e.pid, signal.SIGTERM)
    done(p21e, f21e)
    check("F21 a STATE whose pid runs with another start time (a reused pid) is not RUNNING but DEAD; a fleet from "
          "before STATE reads STOPPED off its block; a live fleet with no new output for --stall-min reads STALLED (5)",
          k21c[0] == 4 and k21d[0] == 3 and "a smoke arm failed" in k21d[1]
          and quiet and k21e.returncode == 5 and "#####  STALLED  #####" in k21e.stdout,
          f"{k21c[0]} {k21d[0]} {k21e.returncode}")
    # A FLEET FROM BEFORE STATE WITH AN ANALYSIS BLOCK: FINISHED only if its SUMMARY shows it ended its own
    # analysis ('---- fleet finished', then '=== wrote .../SUMMARY.txt'); a block --analyze wrote over a fleet
    # killed in its calibration leaves it DEAD (the review of 2026-09-27: it read FINISHED, "runs: 0 of 0").
    blk = "==== PASTE THIS BACK ====\nruns: 0 of 0 ended rc=0, every one\nDECISION: UNDECIDED\n==== END ====\n"
    o21f = os.path.join(TMP, "f21f", "gpu_retok_out")
    write(os.path.join(o21f, "SUMMARY.txt"), "=== gpu_world.sh  2026-09-27T10:56:02Z  commit ae70638\n"
                                             "---- 1. smoke: every arm, seed 0, 60 windows, all at once\n"
                                             "---- calibration: k copies of the shipped defaults for 600 windows\n"
                                             "    k=1  aggregate 50.000 windows/s  (50.00 per run)  failed 0\n")
    os.makedirs(os.path.join(o21f, "cal", "k2"))
    write(os.path.join(o21f, "PASTE_BACK.txt"), blk)
    k21f = status(o21f)
    o21g = os.path.join(TMP, "f21g", "gpu_retok_out")
    summary(o21g, seeds="0")
    with open(os.path.join(o21g, "SUMMARY.txt"), "a") as fh:
        fh.write(f"=== wrote {o21g}/SUMMARY.txt\n")
    write(os.path.join(o21g, "PASTE_BACK.txt"), blk)
    k21g = status(o21g)
    check("F21 a fleet from before STATE killed in its calibration and analysed afterwards by --analyze reads DEAD (4), "
          "saying so; one whose SUMMARY shows it ended its own analysis reads FINISHED (1)",
          k21f[0] == 4 and "#####  DEAD  #####" in k21f[1] and "it died during calibration k=2" in k21f[1]
          and "written afterwards, by --analyze" in k21f[1] and k21g[0] == 1 and "#####  FINISHED  #####" in k21g[1],
          f"{k21f[0]} {k21g[0]}; {k21f[1][:400]!r}")
    # AN ENDED FLEET WHOSE RUN STILL RUNS (a run orphaned when its fleet was stopped) lists it, and says --stop
    # clears it. The stray carries the fleet's GW_FLEET_OUT, as every run of a fleet does; F24 reuses it.
    o21i = os.path.join(TMP, "f21i", "gpu_retok_out")
    summary(o21i, seeds="0")
    write(os.path.join(o21i, "STATE"), f"pid=999999999\npid_start=1\nphase=stopping\nend=stopped\nrc=130\n"
                                       f"reason=stopped by SIGINT during calibration k=1\nstep_dir={o21i}/cal/k1\n")
    os.makedirs(os.path.join(o21i, "cal", "k1"), exist_ok=True)
    stray21 = subprocess.Popen([os.path.join(binp, "python3"), "run.py", "--max-windows", "500", "--loss-curve",
                                os.path.join(o21i, "cal", "k1", "cal.s1001.json")], cwd=TMP, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, env=clean_env(PATH=env10["PATH"], STUB_WSLEEP="2",
                                                                         STUB_MAXW="500", GW_FLEET_OUT=o21i))
    seen21 = wait_for(lambda: ("run" in [k for _, k in own(o21i)]), 30)
    k21i = status(o21i)
    check("F21 an ended fleet (STOPPED) whose run still runs lists that process and says --stop clears it",
          seen21 and k21i[0] == 3 and "but 1 of its process(es) still run: gpu_world.sh --stop clears them" in k21i[1]
          and f" processes  1 still running for it: {stray21.pid} (run)" in k21i[1],
          k21i[1][:600])

    # ---- F22: pull safety -------------------------------------------------------------------------------
    # A SCRATCH CHECKOUT (a git repository of this tree's gpu_world.sh, run.py, src/ and the dashboard). Mid-
    # fleet its gpu_world.sh is rewritten IN PLACE -- an editor, cp or scp; a running bash reads its script
    # from its offset, so the old launch died on a syntax error with no block -- and a "pull" replaces run.py
    # and a file under src/. The fleet runs its private copy and ends as if nothing happened.
    r22 = os.path.join(TMP, "f22", "repo")
    os.makedirs(os.path.join(r22, "tools"))
    for f_ in ("gpu_world.sh", "run.py"):
        shutil.copy2(os.path.join(ROOT, f_), r22)
    shutil.copy2(DASH, os.path.join(r22, "tools"))
    shutil.copytree(os.path.join(ROOT, "src"), os.path.join(r22, "src"), ignore=shutil.ignore_patterns("__pycache__"))
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "scratch"]):
        subprocess.run(cmd, cwd=r22, check=True, capture_output=True)
    head22 = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=r22, capture_output=True, text=True).stdout.strip()
    o22 = os.path.join(TMP, "f22", "gpu_retok_out")
    log22, book22 = os.path.join(TMP, "f22.log"), os.path.join(TMP, "f22_book.jsonl")
    p22, f22 = fleet(o22, log22, argv=("bash", os.path.join(r22, "gpu_world.sh")), cwd=r22, PAR=1, HB_EVERY=1,
                     STUB_BOOK=book22, STUB_STARTUP="0.5", STUB_WSLEEP="0.1", STUB_PROG="5", STUB_MAXW="10")
    mid = wait_for(lambda: st_of(o22).get("phase") == "fleet")
    g22 = open(os.path.join(r22, "gpu_world.sh")).read()
    with open(os.path.join(r22, "gpu_world.sh"), "w") as fh:
        fh.write("echo INJECTED-FROM-THE-CHECKOUT; exit 99\n" + g22.replace("fleet started", "FLEET MUTANT"))
    write(os.path.join(r22, "run.py"), "raise SystemExit('the pulled run.py ran')\n")
    with open(os.path.join(r22, "src", "spine", "loop.py"), "a") as fh:
        fh.write("\nraise SystemExit('the pulled src ran')\n")
    rc22 = done(p22, f22)
    L22 = open(log22).read()
    recs22 = [json.loads(ln) for ln in open(book22)] if os.path.exists(book22) else []
    S22 = open(os.path.join(o22, "SUMMARY.txt")).read() if os.path.exists(os.path.join(o22, "SUMMARY.txt")) else ""
    check("F22 a git pull or an in-place rewrite of the checkout during a fleet reaches none of it: the fleet runs its "
          "private copy to rc 0 and its block, no rewritten line runs, every run (after the rewrite too) ran "
          "$OUT/code/run.py, and SUMMARY records the commit and the copy's sha256",
          mid and rc22 == 0 and block_of(L22) is not None and "INJECTED" not in L22 and "FLEET MUTANT" not in L22
          and "syntax error" not in L22 and len(recs22) == 9
          and {r["runpy"] for r in recs22} == {os.path.join(os.path.realpath(o22), "code", "run.py")}
          and re.search(rf"^=== code: this fleet runs its own copy, \S+/code \(gpu_world\.sh, run\.py, src/, "
                        rf"tools/fleet_dash\.sh; sha256 [0-9a-f]{{16}}\), taken from commit {head22} at launch", S22, re.M)
          is not None and S22.startswith(f"=== gpu_world.sh  ") and f"commit {head22}\n" in S22.splitlines(True)[0],
          f"mid {mid}; rc {rc22}; {len(recs22)} runs; {S22[:120]!r}")
    a22 = gw("--analyze", EXP="retok", OUT=o22)
    check("F22 ... and --status and --analyze, readers run from the checkout, read that fleet as ever",
          status(o22)[0] == 1 and a22.returncode == 0 and block_of(a22.stdout) is not None, a22.stdout[-300:])

    # ---- F23: the dashboard ---------------------------------------------------------------------------
    fs = frames19
    check("F23 the dashboard, live: the big verdict line, the stage and its time, each run of the step -- starting on "
          "CPU before its banner, then training with its windows -- runs alive/done/failed, and the fleet log's last lines",
          all(f"#####  RUNNING  #####" in fs.get(k, "") for k in ("smoke-cpu", "smoke-train", "cal", "fleet"))
          and "stage      smoke: every arm, seed 0, 4 run(s) x 10 windows; since" in fs.get("smoke-cpu", "")
          and re.search(r"^ k0\.s0 +starting on CPU \(\d+ s\) +-/10 ", fs.get("smoke-cpu", ""), re.M) is not None
          and "every run of this step is still building on the CPU" in fs.get("smoke-cpu", "")
          and re.search(r"^ k0\.s0 +training +(<101|\d+)/10 ", fs.get("smoke-train", ""), re.M) is not None
          and "stage      calibration k=1: 1 run(s) x 20 windows" in fs.get("cal", "")
          and "stage      fleet: 5 run(s), 1 at a time, 20 windows each" in fs.get("fleet", "")
          and "queued, of 5" in fs.get("fleet", "") and "last lines of " in fs.get("fleet", "")
          and " log        f19.log: last line " in fs.get("fleet", ""),
          str({k: v[:200] for k, v in fs.items()}))
    fin23 = subprocess.run(["bash", DASH, "--once", o19], capture_output=True, text=True, timeout=60).stdout
    ln23 = subprocess.run(["bash", DASH, "--line", o19], capture_output=True, text=True, timeout=60).stdout
    before = sorted(os.listdir(o19))
    hp = subprocess.Popen(["bash", DASH, "--html", "--every", "1", o19], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    wrote = wait_for(lambda: os.path.exists(os.path.join(o19, "dashboard.html")), 30)
    time.sleep(1.5)
    hp.terminate()
    hp.wait()
    after = sorted(os.listdir(o19))
    page = open(os.path.join(o19, "dashboard.html")).read() if wrote else ""
    check("F23 on a finished fleet it reads FINISHED and says what to paste back; --line is one heartbeat line; --html "
          "writes $OUT/dashboard.html, which reloads itself, and nothing else into the fleet",
          "#####  FINISHED  #####" in fin23 and "paste back: cat " in fin23
          and len(ln23.splitlines()) == 1 and ln23.startswith("[hb ") and " FINISHED " in ln23
          and wrote and after == sorted(before + ["dashboard.html"]) and "http-equiv='refresh'" in page
          and ">FINISHED<" in page, f"{sorted(set(after) - set(before))}")
    sk = socket.socket()
    sk.bind(("127.0.0.1", 0))
    port = sk.getsockname()[1]
    sk.close()
    sp = subprocess.Popen(["bash", DASH, "--serve", str(port), "--every", "1", o19], stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL)

    def fetch(path):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as r_:
                return r_.status, r_.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, ""
        except OSError:
            return None, ""

    served = wait_for(lambda: fetch("/")[0] == 200 and "FINISHED" in fetch("/")[1], 30)
    code_other = fetch("/SUMMARY.txt")[0]
    sp.terminate()
    sp.wait()
    check("F23 --serve PORT serves that page, and only it, on 0.0.0.0 (a fleet file asked for is a 404)",
          served and code_other == 404, f"served {served}; /SUMMARY.txt -> {code_other}")
    # UNDER A TERMINAL the frame is painted, and the page is not (the review of 2026-09-27: html.escape kept the
    # colour codes, and a browser showed '[1;42;97m  #####  RUNNING').
    import select
    os.remove(os.path.join(o19, "dashboard.html"))
    mfd, sfd = os.openpty()
    hp2 = subprocess.Popen(["bash", DASH, "--html", "--every", "1", o19], stdin=subprocess.DEVNULL, stdout=sfd,
                           stderr=sfd, env=clean_env())
    os.close(sfd)
    tty23, t23 = b"", time.time()
    while time.time() - t23 < 20 and not (b"\x1b[1;44;97m" in tty23
                                           and os.path.exists(os.path.join(o19, "dashboard.html"))):
        if select.select([mfd], [], [], 0.2)[0]:
            try:
                tty23 += os.read(mfd, 65536)
            except OSError:
                break
    time.sleep(0.3)
    hp2.terminate()
    hp2.wait()
    os.close(mfd)
    page2 = open(os.path.join(o19, "dashboard.html")).read() if os.path.exists(os.path.join(o19, "dashboard.html")) else ""
    check("F23 run in a terminal, the dashboard paints its frame and --html still writes a page with no colour code",
          b"\x1b[1;44;97m" in tty23 and "\x1b" not in page2 and "#####  FINISHED  #####" in page2,
          f"{len(tty23)} bytes on the terminal; {page2.count(chr(27))} ESC in the page")

    # A RUN'S RATE NEVER COUNTS ITS STARTUP (the review of 2026-09-27: a sample taken while a run was still
    # building on the CPU was its baseline, and the first minutes read 2-5x slow). A synthetic calibration
    # step whose STATE names this test (so it reads RUNNING): cal.s1001 is a live stand-in whose log says it
    # built for 20 s from t0 and then printed its [501 windows] line 10 s into its training (50 windows/s);
    # cal.s1002 and k0.s0 ended with their final line, their rc not booked yet.
    o23 = os.path.join(TMP, "f23r", "gpu_retok_out")
    sd23 = os.path.join(o23, "cal", "k1")
    os.makedirs(sd23)
    me_start = open("/proc/self/stat").read().rsplit(")", 1)[1].split()[19]
    live23 = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)", "run.py", TMP], cwd=TMP)
    gone23 = subprocess.Popen([sys.executable, "-c", "pass"], cwd=TMP)
    gone23.wait()
    T23 = int(time.time()) - 30
    write(os.path.join(o23, "STATE"),
          f"pid={os.getpid()}\npid_start={me_start}\nexp=retok\nphase=cal\nstep=k=1\nstep_dir={sd23}\nstep_runs=3\n"
          f"step_windows=600\nsince={T23}\nhb_every=30\nlaunch_t={T23 - 60}\n")
    write(os.path.join(sd23, "_started.txt"), "".join(f"{t_} pid={p_} t0={T23} cap=600 target=600\n" for t_, p_ in
                                                     (("cal.s1001", live23.pid), ("cal.s1002", gone23.pid),
                                                      ("k0.s0", gone23.pid))))
    head23 = ("=== run.py pid 1 started 12:00:00Z: importing torch and composing\n=== device=cpu amp=off\n"
              "=== composed: stage=assembled, 0 refusal(s), 0 warning(s); startup took 20.0 s (imports and compose), "
              "training starts now\n")
    prog23 = "".join(f"[{i} windows] loss=2.0000 opt_steps={i} n_live=2049 vocab=600 uncalled=0\n" for i in range(101, 502, 100))
    fin23 = "=== 600 windows, 600 flushes, 600 optimizer steps, 1 epoch(s) in 12.0s (50 w/s)\n"
    write(os.path.join(sd23, "cal.s1001.log"), head23 + prog23)
    write(os.path.join(sd23, "cal.s1002.log"), head23 + prog23 + fin23)
    write(os.path.join(sd23, "k0.s0.log"), head23 + prog23 + fin23)
    for n_ in ("cal.s1001.log", "cal.s1002.log", "k0.s0.log"):
        os.utime(os.path.join(sd23, n_), (T23 + 30, T23 + 30))
    # (a) the only sample was taken while cal.s1001 was still on the CPU (windows 0): no baseline, the
    #     since-training average instead, 501 / (30 - 20) = 50.1~ (the sample would have said 501 / 25 = 20).
    write(os.path.join(o23, "HEARTBEAT"), "[hb] a line\n" + json.dumps(
        {"t": T23 + 5, "hist": [[T23 + 5, {"cal/k1/cal.s1001": 0}, 0, {}]]}) + "\n")
    fa23 = subprocess.run(["bash", DASH, "--once", o23], capture_output=True, text=True, timeout=60).stdout
    la23 = subprocess.run(["bash", DASH, "--line", o23], capture_output=True, text=True, timeout=60).stdout
    # (b) a sample taken while it trained (201 windows, its log written at 24 s): measured from there, at the
    #     log's times, 300 / 6 = 50.0 (against the sample's own time it would read 300 / ~5 = 60).
    write(os.path.join(o23, "HEARTBEAT"), "[hb] a line\n" + json.dumps(
        {"t": T23 + 25, "hist": [[T23 + 25, {"cal/k1/cal.s1001": 201}, 201, {"cal/k1/cal.s1001": T23 + 24}]]}) + "\n")
    fb23 = subprocess.run(["bash", DASH, "--once", o23], capture_output=True, text=True, timeout=60).stdout
    live23.kill()
    live23.wait()
    row = lambda fr, tag: next((ln for ln in fr.splitlines() if ln.startswith(f" {tag} ")), "")
    check("F23 a run's rate never counts its startup: with only a sample from its CPU phase it is the since-training "
          "average (50.1~, where the sample said 20), and from a sample taken while it trained it is measured at its "
          "log's times (50.0); the aggregate is the training runs' sum",
          re.search(r" 501/600 +50\.1~ ", row(fa23, "cal.s1001")) is not None and "50.1 windows/s aggregate" in fa23
          and re.search(r" 501/600 +50\.0 ", row(fb23, "cal.s1001")) is not None and "50.0 windows/s aggregate" in fb23,
          f"{row(fa23, 'cal.s1001')!r} {row(fb23, 'cal.s1001')!r}")
    check("F23 a run whose run.py ended with its final line, its rc not booked yet, reads finishing -- k0's while its "
          "kept checkpoints are indexed -- never VANISHED, and the heartbeat counts it so",
          "finishing (its rc next)" in row(fa23, "cal.s1002") and "finishing (indexing ckpts)" in row(fa23, "k0.s0")
          and " runs       3 in this step: 0 starting on CPU, 1 training, 0 done, 2 finishing, 0 failed" in fa23
          and "VANISHED" not in fa23 and "vanished" not in fa23
          and "3 run(s): 0 on CPU, 1 training (w 501-501/600), 0 done, 2 finishing, 0 failed" in la23,
          f"{row(fa23, 'cal.s1002')!r}; {la23[:300]!r}")
    cpu23 = next((ln for ln in fa23.splitlines() if ln.startswith(" CPU ")), "")
    check("F23 the CPU line is this container's own use against its cores (or says it could not be measured); "
          "/proc/loadavg is shown only as the host's load",
          ("cores busy in this container" in cpu23 or "this container's use not measured" in cpu23)
          and ("host load" in cpu23 or not os.path.exists("/proc/loadavg")) and "(1 min) on" not in cpu23,
          cpu23)

    # ---- F24: the launcher ------------------------------------------------------------------------------
    o24 = os.path.join(TMP, "f24", "gpu_retok_out")
    log24 = os.path.join(TMP, "f24", "retok_fleet.log")
    e24 = dict(PATH=env10["PATH"], DEVICE="cpu", WINDOWS=20, SEEDS="0", SMOKE_WINDOWS=10, KEEP_CKPT=0, PAR=1,
               HB_EVERY=1, OUT=o24, LOG=log24, FETCH=0, WAIT_S=3, STUB_STARTUP="0.5", STUB_WSLEEP="0.15", STUB_PROG="5",
               STUB_MAXW="16")
    n24 = subprocess.run(["bash", LAUNCHER, "--go"], cwd=TMP, capture_output=True, text=True, timeout=300,
                         env=clean_env(**{k: v for k, v in e24.items()}))
    g24 = subprocess.run(["bash", LAUNCHER], cwd=TMP, capture_output=True, text=True, timeout=300,
                         env=clean_env(**dict(e24, EXP="retok", DEVICE="cuda")))
    import shutil as _sh
    check("F24 the launcher's checks FAIL clearly, each with its fix, and --go launches nothing: EXP unset; and on a box "
          "without a GPU, DEVICE=cuda fails on torch's CUDA and on nvidia-smi",
          n24.returncode == 1 and "FAIL EXP is not set" in n24.stdout and "!! NOT LAUNCHED" in n24.stdout
          and not os.path.exists(o24)
          and (_sh.which("nvidia-smi") is not None
               or (g24.returncode == 1 and "FAIL nvidia-smi not found" in g24.stdout and "fix: " in g24.stdout)),
          n24.stdout[-400:] + g24.stdout[-400:])
    # --go FROM A SHELL THAT EXITS AT ONCE: the fleet runs on in its own session to its end.
    sh24 = subprocess.run(["bash", "-c", f'bash "{LAUNCHER}" --go; echo "LAUNCHER-RC=$?"'], cwd=TMP,
                          capture_output=True, text=True, timeout=300, env=clean_env(**dict(e24, EXP="retok")))
    pid24 = int(st_of(o24).get("pid", "0") or 0)
    alive24 = pid24 > 0 and os.path.exists(f"/proc/{pid24}")
    sid_ok = alive24 and os.getsid(pid24) == pid24 and os.getsid(pid24) != os.getsid(0)
    again = subprocess.run(["bash", LAUNCHER, "--go"], cwd=TMP, capture_output=True, text=True, timeout=300,
                           env=clean_env(**dict(e24, EXP="retok")))
    fin24 = wait_for(lambda: st_of(o24).get("end") == "finished", 120)
    L24 = open(log24).read() if os.path.exists(log24) else ""
    r24 = os.path.realpath(o24)
    check("F24 --go (DEVICE=cpu) launches detached and says RUNNING with the pid STATE names; the invoking shell exits "
          "and the fleet runs on in its own session (setsid) to its end, its block in the appended log; the commands "
          "it prints name the checkout by its absolute path, so they work from any terminal",
          "LAUNCHER-RC=0" in sh24.stdout and f"=== RUNNING: pid {pid24} " in sh24.stdout and alive24 and sid_ok
          and f"watch it (a second terminal):  bash {DASH} {r24}" in sh24.stdout
          and f"one look, any time:            EXP=retok OUT={o24} bash {SCRIPT} --status" in sh24.stdout
          and f"stop it (it writes its block): EXP=retok OUT={o24} bash {SCRIPT} --stop" in sh24.stdout
          and f"when it has ended, paste back: cat {r24}/PASTE_BACK.txt" in sh24.stdout
          and fin24 and block_of(L24) is not None and "tools/gpu_launch.sh --go (EXP=retok" in L24,
          f"pid {pid24} alive {alive24} sid {sid_ok} fin {fin24}; {sh24.stdout[-700:]!r}")
    check("F24 ... and a second --go while it runs FAILs on the running fleet, with the commands to watch and stop it, "
          "and launches nothing",
          again.returncode == 1 and f"FAIL a fleet is RUNNING in {o24}" in again.stdout and "!! NOT LAUNCHED" in again.stdout
          and f"bash {SCRIPT} --stop" in again.stdout, again.stdout[-600:])
    # AN EXPORTED OMP_NUM_THREADS (clean_env exports 1) IS SAID, NOT A WARN (the review of 2026-09-27: --go
    # launched past the WARN into a fleet sized at one core, and the fix it printed was then refused); the
    # fleet sizes itself by the cores (F19).
    check("F24 an exported OMP_NUM_THREADS=1 is said, not a WARN: the launcher names the cores the fleet sizes itself "
          "by and that OMP_NUM_THREADS is ignored for that",
          "WARN OMP_NUM_THREADS" not in sh24.stdout and "PASS cores the fleet sizes its parallelism by: " in sh24.stdout
          and "OMP_NUM_THREADS/OMP_THREAD_LIMIT set here (1) are ignored for that" in sh24.stdout,
          [ln for ln in sh24.stdout.splitlines() if "OMP" in ln or "cores" in ln])
    # AN ENDED FLEET WHOSE RUN STILL RUNS (F21's stray, carrying its GW_FLEET_OUT) is a FAIL whose fix is --stop:
    # it PASSed as "not running", and --go then launched into gpu_world.sh's refusal (the review of 2026-09-27).
    or24 = subprocess.run(["bash", LAUNCHER, "--go"], cwd=TMP, capture_output=True, text=True, timeout=300,
                          env=clean_env(**dict(e24, EXP="retok", OUT=o21i, LOG=os.path.join(TMP, "f21i.log"))))
    stray21.kill()
    stray21.wait()
    check("F24 an ended fleet whose run still runs FAILs the launcher's check, its fix --stop, and --go launches nothing",
          or24.returncode == 1 and f"FAIL {o21i} holds a STOPPED fleet that is not running, but 1 of its process(es) "
                                   f"still run (pid {stray21.pid})" in or24.stdout
          and f"fix: EXP=retok OUT={o21i} bash {SCRIPT} --stop" in or24.stdout and "!! NOT LAUNCHED" in or24.stdout
          and not glob.glob(o21i + ".20*"),
          or24.stdout[-700:])
    # THE READY LINE CARRIES EVERY KNOB SET (the review of 88d3fae): without --go, a clean check with the cooldown
    # fleet's knobs printed "ready: EXP=retok bash .../gpu_launch.sh --go", whose paste would have launched the
    # default retok fleet (k0, k3000, k1000, k0_nuis at seeds 0-2, kept checkpoints). The printed line is run
    # here with `env` in the launcher's place: every knob comes back as it was set, and nothing else.
    o24r = os.path.join(TMP, "f24r", "gpu_retok_out")
    k24 = dict(EXP="retok", RETOK_ARMS="1000", COOLDOWN_ARM="100", SEEDS="0 1 2 3 4", KEEP_CKPT="0", DEVICE="cpu",
               FETCH="0", OUT=o24r, WINDOWS="20", PAR="12", EXTRA="LM_CTX=128 FAB_SLOTS='4096'", TOK_GROW_EVERY="200")
    rd24 = subprocess.run(["bash", LAUNCHER], cwd=TMP, capture_output=True, text=True, timeout=300,
                          env=clean_env(PATH=env10["PATH"], **k24))
    rl24 = next((ln[len("    ready: "):] for ln in rd24.stdout.splitlines() if ln.startswith("    ready: ")), "")
    go24 = f" bash {LAUNCHER} --go"
    back24 = {}
    if rl24.endswith(go24):
        ev24 = subprocess.run(["bash", "-c", rl24[:-len(go24)] + " env"], capture_output=True, text=True, timeout=60,
                              env={"PATH": os.environ.get("PATH", "")})
        back24 = dict(ln.split("=", 1) for ln in ev24.stdout.splitlines() if "=" in ln)
    extra24 = set(back24) - set(k24) - {"PATH", "PWD", "OLDPWD", "SHLVL", "_"}
    check("F24 without --go a clean check ends in a ready line that carries every knob set, quoted: run with env in "
          "the launcher's place it gives each one back -- the cooldown fleet's RETOK_ARMS, COOLDOWN_ARM, SEEDS and "
          "KEEP_CKPT, EXTRA with its quotes, and a lever a run inherits -- and nothing it was not given",
          rd24.returncode == 0 and rl24.endswith(go24) and all(back24.get(k) == v for k, v in k24.items())
          and not extra24,
          f"{rl24!r}; {sorted(extra24)}; {rd24.stdout[-400:]!r}")
    lt24 = open(LAUNCHER).read()
    kn24 = re.search(r'^KNOBS="([^"]*)"', lt24, re.M)
    knobs24 = set(kn24.group(1).split()) if kn24 else set()
    read24 = {k for k in re.findall(r"^\s*([A-Z][A-Z0-9_]*)=\$\{\1:-", open(SCRIPT).read() + lt24, re.M)
              if k not in ("CTX", "CKPT_BYTES") and not k.startswith("GW_")}
    check("F24 ... and the launcher's KNOBS name every knob gpu_world.sh and the launcher read with a default "
          "(CTX and CKPT_BYTES are the script's own, assigned before they are read)",
          len(read24) > 20 and read24 <= knobs24, str(sorted(read24 - knobs24)))

    # ---- F27: 04-Q5's pins on every retok run and on its resume line (2026-09-29; F18 on sr0-build) -------
    # EXP=retok's arms and nuisance margin pair with runs made before SR0's defaults flipped, so the launch
    # sets DATA_SYNTH_HOLDOUT=0 EVAL_RETENTION_EVERY=0 DATA_TRUST=off on every run it makes -- each only
    # where the tree declares its lever, so a checkout from before a flip gets no UNREAD name -- SUMMARY.txt
    # and the block record the pins that ran, and the resume line carries them. F10's launches are read
    # first; then the script, copied into a tree that declares none of the three and one that declares
    # DATA_SYNTH_HOLDOUT alone (C1's), launches EXP=retok with the stand-in. SINCE THE FLEET LAYER
    # (2026-09-27) A LAUNCH COPIES run.py AND THE DASHBOARD INTO $OUT/code, so each stand-in tree carries
    # both: the dashboard itself, and a run.py the stand-in python answers for and never runs.
    want27 = dict(p.split("=") for p in PINS27.split())
    none27 = {k: None for k in want27}
    rc27 = [json.loads(l) for l in open(os.path.join(TMP, "f10c_book.jsonl"))] \
        if os.path.exists(os.path.join(TMP, "f10c_book.jsonl")) else []
    rw27 = [json.loads(l) for l in open(book)] if os.path.exists(book) else []
    a27 = txt(os.path.join(aside, "ANALYSIS.txt"))
    check("F27 every run of an EXP=retok launch -- smoke, fleet and rerun, both seeds -- carries the three pins, "
          "SUMMARY.txt's pins line and the block's shape line record them, and EXP=world carries none",
          len(rc27) >= 9 and all(r["pins"] == want27 for r in rc27)
          and {r["tag"] for r in rc27} >= {"k0.s0", "k0.s1", "k10.s0", "k20.s1", "k0_nuis.s1", "k0_rerun.s0"}
          and "=== pins: DATA_SYNTH_HOLDOUT=0 pinned, EVAL_RETENTION_EVERY=0 pinned, DATA_TRUST=off pinned" in s10
          and "; pins DATA_SYNTH_HOLDOUT=0 pinned, EVAL_RETENTION_EVERY=0 pinned, DATA_TRUST=off pinned" in b10c
          and len(rw27) == 9 and all(r["pins"] == none27 for r in rw27),
          f"{len(rc27)} retok run(s), pins {sorted({json.dumps(r['pins']) for r in rc27})[:2]}; "
          f"{len(rw27)} world run(s), pins {sorted({json.dumps(r['pins']) for r in rw27})[:2]}")
    check("F27 ... and ANALYSIS.txt's resume line carries them after EXTRA, as run_job sets them, with no row "
          "naming a pin the fleet did not record",
          f"TOK_RETOK_EVERY=0 {PINS27} python3 run.py -- a NEW CKPT_DIR, never a kept copy" in a27
          and "this checkout's pins" not in a27,
          str([l for l in a27.splitlines() if "resume one" in l]))

    def tree27(tag, data, ev):
        """A stand-in checkout: src/'s two lever files as given, this gpu_world.sh, the dashboard, a run.py."""
        t = os.path.join(TMP, "f27", tag)
        shutil.rmtree(t, ignore_errors=True)
        write(os.path.join(t, "src", "data", "levers.py"), data)
        write(os.path.join(t, "src", "eval", "levers.py"), ev)
        write(os.path.join(t, "run.py"), "raise SystemExit('the stand-in python answers for this file')\n")
        os.makedirs(os.path.join(t, "tools"))
        shutil.copy2(SCRIPT, os.path.join(t, "gpu_world.sh"))
        shutil.copy2(DASH, os.path.join(t, "tools"))
        return t

    ev27 = "    curve_every = Lever(\n        2000, 'x', U.Windows)\n"
    alone27 = ("    resample = Lever(False, 'x', U.FLAG)\n    synth_holdout = Lever(False, 'x', U.FLAG)\n"
               "    trust_rule = Lever('claims', 'x', U.NAME)\n")
    for tag27, data27, pins_want, line_want in (
            ("declares none of the three", "    resample = Lever(False, 'x', U.FLAG)\n", none27, "=== pins: none"),
            ("declares DATA_SYNTH_HOLDOUT alone (C1's)", alone27, dict(none27, DATA_SYNTH_HOLDOUT="0"),
             "=== pins: DATA_SYNTH_HOLDOUT=0 pinned")):
        t27 = tree27(tag27.split()[1], data27, ev27)
        b27 = os.path.join(t27, "book.jsonl")
        o27 = os.path.join(t27, "gpu_retok_out")
        p27 = subprocess.run(["bash", os.path.join(t27, "gpu_world.sh")], cwd=t27, capture_output=True, text=True,
                             timeout=300, env=clean_env(PATH=env10["PATH"], STUB_BOOK=b27, EXP="retok",
                                                        KEEP_CKPT=0, DEVICE="cpu", WINDOWS=20, SEEDS="0", PAR=1,
                                                        SMOKE_WINDOWS=5, OUT=o27))
        r27 = [json.loads(l) for l in open(b27)] if os.path.exists(b27) else []
        s27 = txt(os.path.join(o27, "SUMMARY.txt"))
        check(f"F27 a tree that {tag27}: every retok run carries exactly the pins whose lever it declares, and "
              f"SUMMARY.txt says so ('{line_want}')",
              p27.returncode == 0 and len(r27) == 9 and all(r["pins"] == pins_want for r in r27)
              and line_want + "\n" in s27,
              f"rc {p27.returncode}; {len(r27)} run(s); {sorted({json.dumps(r['pins']) for r in r27})[:2]}; "
              f"{[l for l in s27.splitlines() if l.startswith('=== pins')]}; {p27.stdout[-300:]!r}")

    # A FLEET THAT RECORDED NO PIN, READ HERE (the flip's open item, decided at the Stage 3 merge). A fleet
    # launched before the flip -- the 2026-09-27 retok fleet -- recorded "=== pins: none": its runs had
    # the three features off. --analyze gives its resume line the pins the reading tree declares, after
    # EXTRA, in ANALYSIS.txt and the block, and a row says whose they are; the block's shape line still
    # records no pin, since none ran. Read on this checkout (all three) and on the stand-in tree declaring
    # DATA_SYNTH_HOLDOUT alone (that one), each on its own copy of F10's first fleet.
    for tag27, sh27, pins27 in (("this checkout", SCRIPT, PINS27),
                                ("the tree declaring DATA_SYNTH_HOLDOUT alone",
                                 os.path.join(TMP, "f27", "DATA_SYNTH_HOLDOUT", "gpu_world.sh"), "DATA_SYNTH_HOLDOUT=0")):
        pre27 = os.path.join(TMP, "f27", "pre" + str(len(pins27)), "gpu_retok_out")
        shutil.copytree(aside, pre27, symlinks=True)
        with open(os.path.join(pre27, "SUMMARY.txt"), "w") as fh:
            fh.write(re.sub(r"^=== pins: .*$", "=== pins: none", txt(os.path.join(aside, "SUMMARY.txt")), flags=re.M))
        ap27 = subprocess.run(["bash", sh27, "--analyze"], cwd=os.path.dirname(sh27), capture_output=True, text=True,
                              timeout=300, env=clean_env(PATH=env10["PATH"], EXP="retok", OUT=pre27))
        A27 = txt(os.path.join(pre27, "ANALYSIS.txt"))
        B27 = "\n".join(block_of(ap27.stdout) or [])
        check(f"F27 a fleet that recorded no pin, read by {tag27}: its resume line carries {pins27} after EXTRA, "
              f"in ANALYSIS.txt and the block, a row names them as the checkout's, and the shape line claims none",
              ap27.returncode == 0
              and f"TOK_RETOK_EVERY=0 {pins27} python3 run.py -- a NEW CKPT_DIR, never a kept copy" in A27
              and f"(its {pins27} are this checkout's pins, which SUMMARY.txt does not record" in A27
              and f"TOK_RETOK_EVERY=0 {pins27} python3 run.py" in B27 and "; pins " not in B27,
              f"rc {ap27.returncode}; {[l for l in A27.splitlines() if 'resume one' in l or 'pins' in l]}; "
              f"{ap27.stderr[-300:]!r}")

    # ---- F28: the probe's best saves in the disk budget (2026-09-29, the flip's review; F19 on sr0-build) ---
    # With CKPT_DIR set an armed retention probe writes ckpt.pt.best and ckpt.pt.best.prev (and
    # CKPT_BEST_KEEP's slots, each with its .prev) beside the ring, and ckpt_files counted the final save
    # alone. The budget block, cut out of the script by its markers, is run in this tree and in two
    # stand-in trees -- one whose EVAL_RETENTION_EVERY defaults to 0 (before 04-6.2's flip) and one
    # declaring none (before SR0) -- over each experiment's pins as the script sets them, with CODE_DIR
    # the tree (the fleet's code, which the block reads as LEVELS is read).
    _blk28 = re.search(r"^# >>> THE BEST SAVES' BUDGET.*?^# <<< THE BEST SAVES' BUDGET$", open(SCRIPT).read(),
                       re.M | re.S)
    _pins28 = {"world": "", "retok": PINS27,
               "world_epoch": "TOK_RETOK_EVERY=1000 DATA_DRAW=planned DATA_SYNTH_HOLDOUT=1 EVAL_RETENTION_EVERY=700",
               "heldout": "DATA_DRAW=planned DATA_SYNTH_HOLDOUT=1 EVAL_RETENTION_EVERY=700 EVAL_HOLDOUT_WINDOWS=256 "
                          "EVAL_RETENTION_N=24 EVAL_GENERATE=0 TOK_MINT_NOVEL=0"}
    t28 = os.path.join(TMP, "f28")
    for _d28, _ev28 in (("preflip", "    retention_every = Lever(\n        0, 'x', U.Windows)\n"),
                        ("presr0", "    curve_every = Lever(\n        2000, 'x', U.Windows)\n")):
        write(os.path.join(t28, _d28, "src", "eval", "levers.py"), _ev28)
        write(os.path.join(t28, _d28, "src", "ckpt", "levers.py"), "    best_keep = Lever(0, 'x', U.COUNT)\n")

    def budget28(tree, exp, extra="", **env):
        """[BEST_FILES, ckpt_files fb_off, k0, k0_nuis] at WINDOWS 20000, KEEP_EVERY 1000."""
        prog = (f'EXP={exp}; EXTRA="{extra}"; EXP_ENV="{_pins28[exp]}"; WINDOWS=20000; KEEP_EVERY=1000; '
                f'CODE_DIR="{tree}"\n'
                + (_blk28.group(0) if _blk28 else "BEST_FILES=?")
                + '\necho "$BEST_FILES $(ckpt_files fb_off) $(ckpt_files k0) $(ckpt_files k0_nuis)"\n')
        p = subprocess.run(["bash", "-c", prog], cwd=TMP, env=clean_env(**env), capture_output=True, text=True,
                           timeout=60)
        return [int(x) if x.isdigit() else x for x in p.stdout.split()]

    _pf, _ps = os.path.join(t28, "preflip"), os.path.join(t28, "presr0")
    got28 = {"world": budget28(ROOT, "world"), "world_epoch": budget28(ROOT, "world_epoch"),
             "retok": budget28(ROOT, "retok"), "heldout": budget28(ROOT, "heldout"),
             "EXTRA 0": budget28(ROOT, "world", "EVAL_RETENTION_EVERY=0"),
             "env 0": budget28(ROOT, "world", EVAL_RETENTION_EVERY="0"),
             "env keep 2": budget28(ROOT, "world", CKPT_BEST_KEEP="2"),
             "EXTRA keep 3 over env 1": budget28(ROOT, "world", "CKPT_BEST_KEEP=3", CKPT_BEST_KEEP="1"),
             "world_epoch pin over EXTRA 0": budget28(ROOT, "world_epoch", "EVAL_RETENTION_EVERY=0"),
             "preflip world": budget28(_pf, "world"), "preflip world_epoch": budget28(_pf, "world_epoch"),
             "presr0 world_epoch": budget28(_ps, "world_epoch")}
    # THE k0 FAMILY'S KEPT SAVES ARE EXP=retok's ALONE (2026-10-02, §8 6.3a): elsewhere an arm named k0 leaves its
    # final save as every arm does. The k0 column held retok's count at every EXP (26 at EXP=world, here at
    # KEEP_EVERY 1000), and at EXP=heldout, whose KEEP_EVERY is 0, it divided by 0 and the fleet budgeted 0 GB.
    want28 = {"world": [2, 3, 3, 3], "world_epoch": [2, 3, 3, 3], "retok": [0, 1, 24, 2], "heldout": [2, 3, 3, 3],
              "EXTRA 0": [0, 1, 1, 1], "env 0": [0, 1, 1, 1], "env keep 2": [6, 7, 7, 7],
              "EXTRA keep 3 over env 1": [8, 9, 9, 9], "world_epoch pin over EXTRA 0": [2, 3, 3, 3],
              "preflip world": [0, 1, 1, 1], "preflip world_epoch": [2, 3, 3, 3],
              "presr0 world_epoch": [0, 1, 1, 1]}
    check("F28 ckpt_files counts the probe's best saves where a run's probe is armed: 2 more at EXP=world (the "
          "shipped 1000), EXP=world_epoch and EXP=heldout (their pinned 700), 2 + 2N at CKPT_BEST_KEEP=N (EXTRA "
          "over the environment), none at EXP=retok, at EVAL_RETENTION_EVERY=0 from EXTRA or the environment, on "
          "a tree whose default is 0 or that declares no probe -- and a pin beats EXTRA, as run_job's order does; "
          "k0's kept saves and the ring's .prev count at EXP=retok alone",
          got28 == want28, str({k: v for k, v in got28.items() if v != want28.get(k)}))
    # AND THE LAUNCH SAYS SO: EXP=world at KEEP_CKPT=1, the stand-in leaving a 10 MB final checkpoint --
    # 5 runs x 3 files x 2 x 10 MB is 0.3 GB, where the final save alone was 0.1 -- and the banner names
    # the best saves.
    o28 = os.path.join(TMP, "f28", "gpu_world_out")
    p28 = subprocess.run(["bash", SCRIPT], cwd=ROOT, capture_output=True, text=True, timeout=300,
                         env=clean_env(PATH=env10["PATH"], STUB_BOOK=os.path.join(TMP, "f28_book.jsonl"),
                                       STUB_FINAL_BYTES="10000000", KEEP_CKPT=1, DEVICE="cpu", WINDOWS=20,
                                       SEEDS="0", PAR=1, SMOKE_WINDOWS=5, OUT=o28))
    s28 = txt(os.path.join(o28, "SUMMARY.txt"))
    check("F28 an EXP=world launch at KEEP_CKPT=1 budgets 3 checkpoint files a run -- 0.3 GB for its 5 runs at the "
          "smoke's 10 MB -- and its banner names the probe's best saves beside the final one",
          p28.returncode == 0
          and "=== disk: checkpoints may take about 0.3 GB (10 MB x 2 per file)" in s28
          and "=== kept checkpoints: ON, one final checkpoint per run under " in s28
          and "the retention probe's best saves (ckpt.pt.best and .best.prev): up to 3 checkpoint files per run" in s28,
          f"rc {p28.returncode}; {[l for l in s28.splitlines() if 'disk' in l or 'kept checkpoints' in l]}; "
          f"{p28.stderr[-300:]!r}")
    # AND THE LAUNCHER'S DISK CHECK COUNTS THE SAME FILES (the Stage 3 merge: tools/gpu_launch.sh, written before
    # the probe, counted one final save a run): it runs the script's budget block with the launch's settings.
    # EXP=world at one seed and CKPT_MB=10 is 5 runs x 3 files x 2 x 10 MB, 0.3 GB; at EVAL_RETENTION_EVERY=0
    # in EXTRA 5 files, 0.1 GB; EXP=world_epoch's pin arms the probe over the same EXTRA.
    def disk28(exp, extra=""):
        p = subprocess.run(["bash", LAUNCHER], cwd=TMP, capture_output=True, text=True, timeout=300,
                           env=clean_env(PATH=env10["PATH"], EXP=exp, DEVICE="cpu", SEEDS="0", KEEP_CKPT=1,
                                         CKPT_MB=10, EXTRA=extra, FETCH=0, OUT=os.path.join(TMP, "f28l", exp)))
        m = re.search(r"the kept checkpoints may need ([\d.]+) GB", p.stdout)
        return m.group(1) if m else p.stdout[-300:]

    got28l = [disk28("world"), disk28("world", "EVAL_RETENTION_EVERY=0"), disk28("world_epoch", "EVAL_RETENTION_EVERY=0")]
    check("F28 the launcher's disk check counts the probe's best saves as the script does: 0.3 GB for EXP=world's 5 "
          "runs at 10 MB, 0.1 GB at EVAL_RETENTION_EVERY=0, and 0.3 GB at EXP=world_epoch, whose pin arms the probe",
          got28l == ["0.3", "0.1", "0.3"], str(got28l))

    # ---- F29: EXP=heldout's launch (2026-10-02, register §8 6.3a) -------------------------------------------
    # E2's retok part as its own fleet. The stand-in records what each run saw. PIN_RETOK=10 names the act arms
    # k10 and k10_mn; EXTRA tries to move four of the pinned levers and sets one that is not pinned.
    o29 = os.path.join(TMP, "f29", "gpu_heldout_out")
    b29 = os.path.join(TMP, "f29_book.jsonl")
    k29 = dict(EXP="heldout", DEVICE="cpu", WINDOWS=20, SEEDS="0 1", PAR=3, SMOKE_WINDOWS=5, PIN_RETOK=10,
               PROBE_EVERY=5, EXTRA="TOK_MINT_NOVEL=0.5 EVAL_HOLDOUT_WINDOWS=32 DATA_DRAW=uniform EVAL_GENERATE=1 "
                                   "TOK_GROW_EVERY=20", OUT=o29)
    p29 = subprocess.run(["bash", SCRIPT], cwd=ROOT, capture_output=True, text=True, timeout=300,
                         env=clean_env(PATH=env10["PATH"], STUB_BOOK=b29, STUB_FINAL_BYTES="50000000", **k29))
    r29 = [json.loads(l) for l in open(b29)] if os.path.exists(b29) else []
    s29 = txt(os.path.join(o29, "SUMMARY.txt"))
    smoke29 = [r for r in r29 if "/smoke/" in r["argv"][r["argv"].index("--loss-curve") + 1]]
    fleet29 = [r for r in r29 if r not in smoke29]
    arm29 = {"k0": ("0", "0"), "k0_rerun": ("0", "0"), "k10": ("10", "0"), "k10_mn": ("10", "1.0")}
    check("F29 EXP=heldout launches k0, k<c> and k<c>_mn (c = PIN_RETOK) at every seed and k0_rerun -- the smoke's 3 "
          "and the fleet's 7 runs, rc 0 -- every run pinned after EXTRA (which moves no pinned lever and keeps an "
          "unpinned one), its arm's settings after the pins: TOK_MINT_NOVEL 0 on k0 and k<c>, 1.0 on k<c>_mn",
          p29.returncode == 0 and len(smoke29) == 3 and sorted(r["tag"] for r in fleet29)
          == ["k0.s0", "k0.s1", "k0_rerun.s0", "k10.s0", "k10.s1", "k10_mn.s0", "k10_mn.s1"]
          and all(r["pins"]["DATA_SYNTH_HOLDOUT"] == "1" and r["pins"]["EVAL_RETENTION_EVERY"] == "5"
                  and r["env"]["EVAL_HOLDOUT_WINDOWS"] == "256" and r["env"]["EVAL_RETENTION_N"] == "24"
                  and r["env"]["EVAL_GENERATE"] == "0" and r["env"]["DATA_DRAW"] == "planned"
                  and r["env"]["TOK_GROW_EVERY"] == "20" and r["env"]["DATA_STREAM_BYTES"] == "3780" for r in r29)
          and all((r["retok"], r["env"]["TOK_MINT_NOVEL"]) == arm29[r["tag"].rsplit(".s", 1)[0]] for r in r29),
          f"rc {p29.returncode}; {[(r['tag'], r['retok'], r['env']) for r in r29][:4]}; {p29.stderr[-300:]!r}")
    check("F29 ... each writes its probe series and flush bytes beside its curve, and saves its final alone: CKPT_EVERY "
          "0 on every run, the k0 family's included, the smoke's too",
          all("--probe-series" in r["argv"] and "--flush-bytes" in r["argv"] for r in r29)
          and all(os.path.exists(os.path.join(o29, "curves", r["tag"] + ".probe.json")) for r in fleet29)
          and all(r["ckpt"] == {"CKPT_DIR": os.path.join(o29, "ckpt", r["tag"]), "CKPT_EVERY": "0"} for r in fleet29)
          and all(r["ckpt"] == {"CKPT_DIR": os.path.join(o29, "smoke", "ckpt", r["tag"]), "CKPT_EVERY": "0"}
                  for r in smoke29), str([(r["tag"], r["ckpt"]) for r in r29][:3]))
    # THE k0 BUDGET (the judge's catch, reproduced: ckpt_files divided by KEEP_EVERY 0 at an arm named k0, ended
    # jobs_need's sum, and the disk check budgeted 0 GB): every run its final and the probe's two best saves.
    check("F29 an arm named k0 budgets 3 files as every run does: 7 runs x 3 files x 2 x 50 MB is 2.1 GB, and the "
          "banner names the best saves",
          "=== disk: checkpoints may take about 2.1 GB (50 MB x 2 per file)" in s29
          and "the retention probe's best saves (ckpt.pt.best and .best.prev): up to 3 checkpoint files per run" in s29,
          [l for l in s29.splitlines() if "disk" in l or "kept checkpoints" in l])
    l29 = subprocess.run(["bash", LAUNCHER], cwd=TMP, capture_output=True, text=True, timeout=300,
                         env=clean_env(PATH=env10["PATH"], CKPT_MB=50, FETCH=0,
                                       **dict(k29, OUT=os.path.join(TMP, "f29l", "gpu_heldout_out"))))
    check("F29 the launcher's disk check budgets the same files: three arms a seed and the rerun, 2.1 GB at 50 MB",
          "the kept checkpoints may need 2.1 GB at 2 seed(s)" in l29.stdout and "PASS EXP=heldout" in l29.stdout,
          l29.stdout[-500:])
    # THE LAUNCHER WARNS THAT FILL ADDS FEW SEEDS ONLY WHERE FILL RUNS: at a need between half the free disk and all of
    # it, EXP=heldout (FILL 0) PASSes the check, and with FILL=1 it WARNs as before.
    st29 = os.statvfs(TMP)
    mb29 = max(1, int(st29.f_bavail * st29.f_frsize / 1e6 * 0.7 / 24))      # 1 seed: 4 runs x 3 files x 2 per MB
    w29 = [subprocess.run(["bash", LAUNCHER], cwd=TMP, capture_output=True, text=True, timeout=300,
                          env=clean_env(PATH=env10["PATH"], EXP="heldout", DEVICE="cpu", SEEDS="0", CKPT_MB=mb29, FETCH=0,
                                        OUT=os.path.join(TMP, "f29w", "gpu_heldout_out"), **fl)).stdout
           for fl in ({}, {"FILL": "1"})]
    check("F29 the launcher's warning that FILL adds few seeds comes only where FILL runs: EXP=heldout's FILL 0 PASSes "
          "a disk need between half the free space and all of it, and FILL=1 WARNs",
          "PASS disk: " in w29[0] and "FILL will add few extra seeds" not in w29[0]
          and "WARN disk: " in w29[1] and "FILL will add few extra seeds" in w29[1],
          [l for w_ in w29 for l in w_.splitlines() if "disk" in l])
    # THE ETA BY WAVES (register LOW-GPU-WORLD-ETA's owed fix): with PAR set by hand the rate per run is the smoke's,
    # 5 windows a second, so each run's 20 windows take 4 s and 7 runs over 3 slots end at 12 s.
    check("F29 the ETA is priced by waves: 7 runs over 3 slots are 3 waves of 4 s, 12 s, beside the aggregate ETA",
          re.search(r"^=== ETA by waves: about 0 min \(12 s\): 7 run\(s\) over 3 slot\(s\), 3 wave\(s\), each run "
                    r"its windows at 5\.00 windows/s plus 0 s of startup; each run's R stage and saves come on top$",
                    s29, re.M) is not None
          and "=== ETA: about 0.0 h for 140 windows at 15.0 windows/s aggregate" in s29,
          [l for l in s29.splitlines() if "ETA" in l])
    # FILL IS 0 AT EXP=heldout (its seeds are capped): 4 runs at PAR 10 stay 4, where FILL=1 adds two seeds.
    o29f = os.path.join(TMP, "f29f", "gpu_heldout_out")
    p29f = subprocess.run(["bash", SCRIPT], cwd=ROOT, capture_output=True, text=True, timeout=300,
                          env=clean_env(PATH=env10["PATH"], **dict(k29, SEEDS="0", PAR=10, KEEP_CKPT=0, OUT=o29f)))
    s29f = txt(os.path.join(o29f, "SUMMARY.txt"))
    check("F29 FILL is 0 at EXP=heldout: one seed at PAR 10 runs its 4 runs and no seed is added",
          p29f.returncode == 0 and "=== 4 run(s), 10 at a time" in s29f and "=== FILL" not in s29f,
          [l for l in s29f.splitlines() if "run(s)" in l or "=== FILL" in l])
    p29e = gw(EXP="heldout", PIN_RETOK="10x", OUT=os.path.join(TMP, "f29e"))
    check("F29 a PIN_RETOK that is not a positive cadence is refused by name, before anything is written",
          p29e.returncode == 2 and "PIN_RETOK='10x'" in p29e.stdout and not os.path.exists(os.path.join(TMP, "f29e")))
    # THE LAUNCHER'S DISK CHECK PER EXPERIMENT (2026-10-02, review of 49a657d). A file is 134 MB at EXP=retok, whose
    # pins keep the trust book's 16.8 MB sketch out of its checkpoints, and 151 MB elsewhere (it was 151 everywhere);
    # and the FAIL's fix fits the experiment: at EXP=heldout it gave EXP=retok's, fewer SEEDS (below the 7
    # pre-registered) or KEEP_CKPT=0 "(which leaves the spike test without its control)", where a top-up's finals,
    # unlike the first fleet's, are not the next test's parents. Each launch is sized past any disk: retok by its
    # windows, heldout by 2,000 seeds.
    def fail29(**env):
        p = subprocess.run(["bash", LAUNCHER], cwd=TMP, capture_output=True, text=True, timeout=300,
                           env=clean_env(PATH=env10["PATH"], DEVICE="cpu", FETCH=0, **env))
        m = re.search(r"FAIL disk: .*? \((\d+) files x 2 x (\d+) MB at \d+ seed\(s\)\)\n +fix: (.*)$", p.stdout, re.M)
        return m.groups() if m else p.stdout[-400:]
    many29 = " ".join(map(str, range(2000)))
    d29 = {"retok": fail29(EXP="retok", SEEDS="0", WINDOWS="100000000", OUT=os.path.join(TMP, "f29d", "r")),
           "heldout": fail29(EXP="heldout", SEEDS=many29, OUT=os.path.join(TMP, "f29d", "h")),
           "top-up": fail29(EXP="heldout", SEEDS=" ".join(map(str, range(2, 2002))), POOL_WITH=o29,
                            OUT=os.path.join(TMP, "f29d", "t")),
           "world": fail29(EXP="world", SEEDS=many29, KEEP_CKPT=1, OUT=os.path.join(TMP, "f29d", "w"))}
    check("F29 the launcher's disk check sizes a file at 134 MB at EXP=retok and 151 MB elsewhere, and its FAIL's fix "
          "fits the experiment: the spike test's at EXP=retok; at EXP=heldout the 7 pre-registered seeds and the finals, "
          "the next test's parents, kept; at a top-up KEEP_CKPT=0; elsewhere fewer SEEDS or KEEP_CKPT=0",
          [v[1:] if isinstance(v, tuple) else v for v in d29.values()]
          == [("134", "free space there, fewer SEEDS, or KEEP_CKPT=0 (which leaves the spike test without its control)"),
              ("151", "free space there, keeping the 7 pre-registered seeds and KEEP_CKPT on: the finals are the next "
                      "test's parents"),
              ("151", "free space there, or KEEP_CKPT=0: the next test starts from the first fleet's finals, not a "
                      "top-up's"),
              ("151", "free space there, fewer SEEDS, or KEEP_CKPT=0")], str(d29))
    # AND THE FLEET'S OWN DISK CHECK, sized at the smoke's largest checkpoint (100 GB, sparse): the same fixes.
    def fleet29(tag, **env):
        o_ = os.path.join(TMP, "f29k", tag, "gpu_heldout_out")
        p = subprocess.run(["bash", SCRIPT], cwd=ROOT, capture_output=True, text=True, timeout=300,
                           env=clean_env(PATH=env10["PATH"], STUB_FINAL_BYTES="100000000000",
                                         **dict(k29, SEEDS="2", PAR=4, OUT=o_, **env)))
        return p.returncode, (re.search(r"^!! (Free space.*)$", p.stdout, re.M) or [None, p.stdout[-300:]])[1], \
            "\n".join(block_of(p.stdout) or [])
    k29d, t29d = fleet29("first"), fleet29("topup", POOL_WITH=o29)
    check("F29 ... and gpu_world.sh's own disk check gives the same fixes, at the fleet and at a top-up, in its log and "
          "its block",
          k29d[0] == 1 and k29d[1] == "Free space, keeping the 7 pre-registered seeds and KEEP_CKPT on: the finals are "
                                      "the next test's parents."
          and "GB free (free space, keeping the 7 pre-registered seeds and KEEP_CKPT on" in k29d[2]
          and t29d[0] == 1 and t29d[1] == "Free space, or KEEP_CKPT=0: the next test starts from the first fleet's "
                                          "finals, not a top-up's."
          and "GB free (free space, or KEEP_CKPT=0: the next test starts from the first fleet's finals" in t29d[2],
          f"{k29d[:2]} {t29d[:2]}")
    # EXP=heldout IS THE CURRENT TEST, AND WHERE EXP IS NOT GIVEN THAT IS WHAT IS NAMED (2026-10-02, review of 49a657d):
    # the launcher's fix for an unset EXP, and --status's hint with neither EXP nor OUT, named EXP=retok, the decided
    # 2026-09-27 fleet, whose launch runs 13 runs with k0's periodic saves.
    u29 = subprocess.run(["bash", LAUNCHER, "--go"], cwd=TMP, capture_output=True, text=True, timeout=300,
                         env=clean_env(PATH=env10["PATH"], DEVICE="cpu", FETCH=0, OUT=os.path.join(TMP, "f29u")))
    st29 = gw("--status")
    check("F29 an unset EXP's fix names EXP=heldout, test 4, and --go launches nothing; --status with neither EXP nor OUT "
          "points to it too",
          u29.returncode == 1 and f"fix: EXP=heldout bash {LAUNCHER} --go" in u29.stdout and "EXP=retok" not in u29.stdout
          and "!! NOT LAUNCHED" in u29.stdout and not os.path.exists(os.path.join(TMP, "f29u"))
          and (os.path.exists(os.path.join(ROOT, "gpu_world_out"))
               or (st29.returncode == 2 and f"the owner brief's current test, test 4, is EXP=heldout bash {SCRIPT} "
                                            f"--status)" in st29.stdout and "EXP=retok" not in st29.stdout)),
          u29.stdout[-500:] + st29.stdout[-300:])

    # ---- F30: EXP=heldout's reading, rule and block (2026-10-02, register §8 6.3a) ---------------------------
    # Fleets written by hand, each number chosen. Each area's R reading (the last 'boundary' row, memory-off,
    # report half) is 2.0 + 0.1 x its index + 0.001 x the seed, with `harm` added to num on k1000 (harm_mn on
    # k1000_mn), +- `spread` by the seed's parity; memory-on reads 0.01 lower; the in-run readings' all-area
    # report is 2.5, and 2.5 + tgap from the stream's middle on; the prequential curve reads 2.0 bits/byte in
    # every phase, + preq4 in phase 4 on k1000.
    HO_AR = ("eng", "py", "num", "c")

    def ho_summary(out, *, seeds, commit="abc1234", card="NVIDIA H100 PCIe, 81559", torch_="torch 2.7.0, CUDA 12.8",
                   pool=None, windows=400, par=24):
        n_, mib = card.split(", ")
        L = [f"=== gpu_world.sh  2026-10-03T12:00:00Z  commit {commit}",
             f"=== code: this fleet runs its own copy, {out}/code (gpu_world.sh, run.py, src/, tools/fleet_dash.sh; "
             f"sha256 0123456789abcdef), taken from commit {commit} at launch: a git pull during the fleet reaches none of it",
             "    index, name, memory.total [MiB], memory.used [MiB]", f"    0, {n_}, {mib} MiB, 1 MiB",
             "=== 26 CPU core(s), 1 GPU(s), device=cuda", f"=== {torch_}",
             f"=== {windows} windows per run, DATA_STREAM_BYTES={windows * 189}, seeds: {seeds}, EXTRA=''",
             f"=== plan: EXP=heldout; arms k0 k1000 k1000_mn, plus k0_rerun at seed 0; window cap {3 * windows}; "
             f"CAL_WINDOWS 600; LM_CTX {CTX}",
             f"=== kept checkpoints: ON, one final checkpoint per run under {out}/ckpt, and beside it the retention "
             f"probe's best saves (ckpt.pt.best and .best.prev): up to 3 checkpoint files per run, all counted in the "
             f"disk check",
             "=== pins: DATA_DRAW=planned pinned, DATA_SYNTH_HOLDOUT=1 pinned, EVAL_RETENTION_EVERY=700 pinned, "
             "EVAL_HOLDOUT_WINDOWS=256 pinned, EVAL_RETENTION_N=24 pinned, EVAL_GENERATE=0 pinned, TOK_MINT_NOVEL=0 pinned"]
        if pool:
            L.append(f"=== pool: with {pool} (seeds 0 1 2 3 4 5 6): this fleet is its top-up, and its analysis reads "
                     f"the two fleets' seeds together where commit, card, torch and shape match")
        L += [f"=== {len(seeds.split()) * 3 + 1} run(s), {par} at a time",
              "=== ETA by waves: about 20 min (1200 s): 22 run(s) over 24 slot(s), 1 wave(s), each run its windows "
              "at 19.20 windows/s plus 15 s of startup",
              "---- 2. fleet started 12:10:00Z", "---- fleet finished in 21 min (1260 s)"]
        write(os.path.join(out, "SUMMARY.txt"), "\n".join(L) + "\n")

    def ho_run(out, name, seed, *, harm=0.0, spread=0.0, tgap=0.0, preq4=0.0, windows=400, nobnd=False,
               noseries=False):
        tag = f"{name}.s{seed}"

        def val(k):
            return (2.0 + 0.1 * k + 0.001 * seed
                    + ((harm + (1 if seed % 2 == 0 else -1) * spread) if HO_AR[k] == "num" else 0.0))

        def row(step, kind, closure, nar, rep_=None, off=0.0):
            ars = {HO_AR[k]: {"control": val(k) + off, "report": val(k) + off, "seen_by_parent": False}
                   for k in range(nar)}
            m_ = sum(x["report"] for x in ars.values()) / nar if rep_ is None else rep_
            return {"step": step, "kind": kind, "closure": closure, "control": m_, "report": m_,
                    "windows": 24 * nar, "nonfinite": 0, "paired_sd": None, "areas": ars}
        rows = []
        for q in range(4):
            for st, kind in ((q * windows // 4 + 1, "phase"), (q * windows // 4 + windows // 8 + 1, "cadence")):
                rows.append(row(st, kind, "memory-off", min(4, q + 2), rep_=2.5 + (tgap if st > windows // 2 else 0.0)))
        if not nobnd:
            rows += [row(windows, "boundary", "memory-off", 4), row(windows, "boundary", "memory-on", 4, off=-0.01)]
        cc = {"loop.bytes_scored": 189 * windows, "loop.acts": 0 if name.startswith("k0") else 3,
              "eval.holdout.seconds": "3.000000", "eval.holdout.windows": sum(r_["windows"] for r_ in rows),
              "data.trust.wall_s": "0.500000", "fab.n_live": 2000 + seed}
        write(os.path.join(out, "logs", tag + ".log"), "\n".join(
            ["=== device=cuda amp=off tf32=(True, True) torch_seed=1",
             f"=== {windows} windows, {windows} flushes, {windows} optimizer steps, 1 epoch(s) in 20.0s (20.0 w/s)",
             "=== R STAGE -- the did-it-fire surfaces:"] + [f"       {k:<44} {v}" for k, v in cc.items()]
            + ["       gate:data.phase_entered                      ('fired', '4 vs 4')"]) + "\n")
        write(os.path.join(out, "curves", tag + ".json"), json.dumps(
            [(2.0 + (preq4 if i * 4 // windows == 3 else 0.0)) * LN2 * 189 / CTX for i in range(windows)]))
        write(os.path.join(out, "curves", tag + ".bytes.json"), json.dumps([189] * windows))
        if not noseries:
            write(os.path.join(out, "curves", tag + ".probe.json"), json.dumps(rows))
        with open(os.path.join(out, "logs", "_done.txt"), "a") as fh:
            fh.write(f"{tag} rc=0 secs=25\n")

    def ho_fleet(out, seeds, *, harm=0.0, spread=0.0, harm_mn=0.0, spread_mn=0.0, tgap=0.0, preq4=0.0, nobnd=(),
                 noseries=(), **kw):
        ho_summary(out, seeds=" ".join(map(str, seeds)), **kw)
        for s_ in seeds:
            for nm, h_, sp_, tg_, p4_ in (("k0", 0.0, 0.0, 0.0, 0.0), ("k1000", harm, spread, tgap, preq4),
                                         ("k1000_mn", harm_mn, spread_mn, 0.0, 0.0)):
                ho_run(out, nm, s_, harm=h_, spread=sp_, tgap=tg_, preq4=p4_, nobnd=f"{nm}.s{s_}" in nobnd,
                       noseries=f"{nm}.s{s_}" in noseries)
        ho_run(out, "k0_rerun", 0)

    def ho_read(tag, seeds, pool_env=None, **kw):
        o_ = os.path.join(TMP, "f30", tag, "gpu_heldout_out")
        ho_fleet(o_, seeds, **kw)
        p_ = gw("--analyze", EXP="heldout", OUT=o_, **({"POOL_WITH": pool_env} if pool_env else {}))
        return o_, p_, txt(os.path.join(o_, "ANALYSIS.txt")), "\n".join(block_of(p_.stdout) or [])

    def dec(text):
        return (re.search(r"^DECISION: (.*)$", text, re.M) or [None, ""])[1]

    zero = " ".join(f"{a} +0.0000 [+0.0000,+0.0000]" for a in HO_AR)
    o30, p30, a30, b30 = ho_read("pass", range(7), tgap=0.0625, preq4=0.1)
    check("F30 a harmless fleet: both act arms PASS on every area by the eps rule (the areas its cells, at 0.025 a "
          "look: Holm's 0.0125 on the first arm, the upper bound at t(0.975)), and the DECISION ends 1000's B-provisional "
          "label on this synthetic source; the block, within 80 lines and equal to PASTE_BACK.txt, carries every seed's "
          "per-area readings and both rows",
          p30.returncode == 0 and f"  k1000 n=7 a=0.0125: {zero} -> PASS" in b30
          and f"  k1000_mn n=7 a=0.025: {zero} -> PASS" in b30
          and "each look (7 seeds; a top-up's pooled 11) at 0.025: mean [lower at t(1 - a/4), Holm's a across the act "
              "arms; one-sided upper at t(0.975)]" in b30
          and dec(b30).startswith("TOK_RETOK_EVERY 1000 PASSes against k0 on every area's held-out reading: its "
                                  "B-provisional label ends on this synthetic source")
          and 0 < len(block_of(p30.stdout)) <= 80
          and block_of(p30.stdout) == txt(os.path.join(o30, "PASTE_BACK.txt")).splitlines()
          and re.search(r"^  s6 +2\.0060 +2\.1060 +2\.2060 +2\.3060 \| +\+0\.0000", b30, re.M) is not None,
          b30[-1500:])
    # THE REPORTED LINES' KNOWN ANSWERS. The time-integrated gap: k1000's in-run report steps from 2.5 to 2.5625 at
    # window 201 of 400, read from 20% of the stream (window 80) on: 0.0625 x (400 - 201) / (0.8 x 400).
    tg30 = 0.0625 * (400 - 201) / (0.8 * 400)
    check("F30 ... and beside it, deciding nothing: the time-integrated report gap from 20% of the stream (+0.0389 = "
          "0.0625 x 199 / 320 for k1000, 0 for k1000_mn), the end-state SD per area, O14's per-phase prequential "
          "reading (phase 4 +0.1000, FAIL, reported), memory-on - memory-off (-0.0100), n_live, the probe's seconds "
          "with R's share, data.trust.wall_s, readings per phase, and the ETA by waves against the wall",
          f"k1000 - k0 mean {tg30:+.4f} sd 0.0000 n=7 | k1000_mn - k0 mean +0.0000 sd 0.0000 n=7" in b30
          and "end-state SD per area of arm - k0: k1000 eng 0.0000 py 0.0000 num 0.0000 c 0.0000" in b30
          and re.search(r"prequential per phase \(O14's 2\.1 endpoint\), k1000 - k0 n=7: .*p4 \+0\.1000 "
                        r"\[\+0\.1000,\+0\.1000\] -> FAIL", b30) is not None
          and "k0 eng -0.0100 py -0.0100 num -0.0100 c -0.0100" in b30 and "n_live at the end (NEW-20): k0 2003" in b30
          and "k0 3.0 s, R 0.7 s, in-run 11.47% of loop time" in b30 and "k0 0.50 [0.50-0.50] s" in b30
          and "in-run readings per phase: fewest 2" in b30 and "ETA by waves 1200 s, took 1260 s: 1.05x" in b30,
          [l for l in b30.splitlines() if "REPORTED" in l or l.startswith("  ")][-12:])
    _, _, _, b30r = ho_read("remedy", range(7), harm=0.2)
    check("F30 k1000 FAILs on num (+0.2000, its lower bound past eps) and k1000_mn PASSes: TOK_MINT_NOVEL 1.0 ships "
          "at 1000, in its own default-change commit",
          "num +0.2000 [+0.2000,+0.2000] c +0.0000 [+0.0000,+0.0000] -> FAIL" in b30r
          and dec(b30r).startswith("TOK_MINT_NOVEL 1.0 ships at TOK_RETOK_EVERY 1000, in its own default-change commit: "
                                   "k1000 FAILs against k0 and k1000_mn PASSes"), dec(b30r))
    _, _, _, b30w = ho_read("withdraw", range(7), harm=0.2, harm_mn=0.2)
    check("F30 both FAIL: neither ships, 1000 stays on meanwhile (never 0) and the next remedy arms run, named, with "
          "k3000 read for O14's escalation -- no ESCALATE",
          dec(b30w).startswith("neither ships: k1000 FAILs against k0 and k1000_mn FAILs too; 1000 stays on meanwhile "
                               "(0 is never shipped by the rule) and the next remedy arms run: LM_ANCHOR_USES raised, "
                               "OPT_HORIZON_REVISE=0, and OPT_BORN_CLOCK once §8 4.2 builds it, with k3000 read for "
                               "O14's escalation") and "ESCALATE" not in b30w, dec(b30w))
    o30u, _, _, b30u = ho_read("unres", range(7), harm=0.05, spread=0.1)
    oa30 = os.path.realpath(o30u)
    check("F30 UNRESOLVED below the cap (num +0.0643, bounds -0.1020 and +0.1632 at 7 seeds, a = 0.0125) prints the "
          "top-up's command: the next 4 seeds to the cap of 11, FILL=0, the fleet's shape (WINDOWS here) and PAR, its own "
          "OUT and POOL_WITH this one",
          "num +0.0643 [-0.1020,+0.1632]" in b30u and dec(b30u).startswith("UNRESOLVED at 7 seed(s): k1000 is UNRESOLVED")
          and f"  top-up: EXP=heldout SEEDS='7 8 9 10' FILL=0 WINDOWS=400 PAR=24 OUT={oa30[:-4]}_topup_out "
              f"POOL_WITH={oa30} bash {ROOT}/tools/gpu_launch.sh --go" in b30u, b30u[-900:])
    _, _, _, b30c = ho_read("cap", range(11), harm=0.05, spread=0.1)
    check("F30 the same at the cap of 11 seeds is reported unresolved, never escalated, and 1000 stays B-provisional",
          dec(b30c).startswith("UNRESOLVED at the cap: k1000 is UNRESOLVED against k0 at the seed cap; reported so, "
                               "never escalated, and TOK_RETOK_EVERY 1000 stays, B-provisional")
          and "top-up:" not in b30c, dec(b30c))
    _, _, _, b30f = ho_read("failunres", range(7), harm=0.2, harm_mn=0.05, spread_mn=0.1)
    check("F30 k1000 FAILs and k1000_mn is UNRESOLVED: the top-up runs for the remedy's reading",
          dec(b30f).startswith("UNRESOLVED at 7 seed(s): k1000 FAILs against k0 and k1000_mn is UNRESOLVED")
          and "  top-up: EXP=heldout SEEDS='7 8 9 10'" in b30f, dec(b30f))
    _, _, a30m, b30m = ho_read("missing", range(7), nobnd=("k1000.s3",), noseries=("k1000_mn.s5",))
    check("F30 a run whose series holds no memory-off boundary row, and one with no series, are named and left out of "
          "their arm's pairs (n=6), and the rule reads the rest",
          "left out of the pairs (no endpoint): k1000.s3 k1000_mn.s5" in b30m
          and re.search(r"^  k1000 +s3 .*NO BOUNDARY ROW \(memory-off\)$", a30m, re.M) is not None
          and re.search(r"^  k1000_mn +s5 .*NO PROBE SERIES$", a30m, re.M) is not None
          and f"  k1000 n=6 a=0.0125: {zero} -> PASS" in b30m, b30m[-700:])
    _, _, _, b30x = ho_read("past", range(12))
    check("F30 seeds past the cap of 11 are not read, and the block says which",
          "seeds past the cap of 11, not read: 11" in b30x and f"  k1000 n=11 a=0.0125: {zero} -> PASS" in b30x)

    # ---- F31: a top-up pooled with its first fleet (2026-10-02, register §8 6.3a) ----------------------------------
    # The first fleet reads UNRESOLVED at 7 seeds (num +0.4 at even seeds, 0 at odd); its top-up at seeds 7-10
    # reads +0.3 at each, so the pooled 11, the second look at 0.025, FAIL k1000 (mean +0.2545, lower +0.0784 at
    # t(1 - 0.0125/4)) and the remedy ships.
    o31 = os.path.join(TMP, "f31", "gpu_heldout_out")
    ho_fleet(o31, range(7), harm=0.2, spread=0.2)
    p31a = gw("--analyze", EXP="heldout", OUT=o31)

    def topup(tag, seeds=range(7, 11), pool=o31, **kw):
        o_ = os.path.join(TMP, "f31", tag)
        ho_fleet(o_, seeds, harm=0.3, pool=pool, **kw)
        p_ = gw("--analyze", EXP="heldout", OUT=o_)
        return o_, "\n".join(block_of(p_.stdout) or [])
    o31t, b31t = topup("gpu_heldout_topup_out")
    check("F31 the first fleet alone is UNRESOLVED and asks for the top-up; the top-up, recorded as its pool, reads the "
          "11 seeds together -- its own marked * -- and k1000 FAILs (+0.2545, lower +0.0784) while k1000_mn PASSes: "
          "TOK_MINT_NOVEL 1.0 ships",
          dec("\n".join(block_of(p31a.stdout) or [])).startswith("UNRESOLVED at 7 seed(s)")
          and f"POOLED with the first fleet {o31}: its seeds and this top-up's (marked *) are read together" in b31t
          and "num +0.2545 [+0.0784,+0.3684] c +0.0000 [+0.0000,+0.0000] -> FAIL" in b31t
          and re.search(r"^  s10\* ", b31t, re.M) is not None and re.search(r"^  s6 ", b31t, re.M) is not None
          and dec(b31t).startswith("TOK_MINT_NOVEL 1.0 ships at TOK_RETOK_EVERY 1000")
          and "(ε 0.05 bits/byte, 11 seed(s))" in b31t, b31t[-1500:])
    check("F31 ... and both reruns are read: the first fleet's own, and the top-up's against the first fleet's k0.s0, "
          "the pair that says the two fleets compute alike",
          "k0_rerun (the first fleet's): k0 seed 0 twice, R per area max |diff| 0, summed loss |diff| 0 (BIT-EXACT)" in b31t
          and "k0_rerun (this top-up's, against the first fleet's k0.s0): k0 seed 0 twice, R per area max |diff| 0, "
              "summed loss |diff| 0 (BIT-EXACT)" in b31t)
    for tag31, kw31, why31 in (("card_out", {"card": "NVIDIA H200, 143771"},
                                "they differ in card (NVIDIA H200 143771 MiB here, NVIDIA H100 PCIe 81559 MiB there)"),
                               ("torch_out", {"torch_": "torch 2.8.0, CUDA 12.8"},
                                "they differ in torch (torch 2.8.0, CUDA 12.8 here, torch 2.7.0, CUDA 12.8 there)"),
                               ("commit_out", {"commit": "def5678"}, "they differ in commit (def5678 here, abc1234 there)"),
                               ("overlap_out", {"seeds": range(6, 10)}, "seed(s) 6 are in both")):
        _, b31r = topup(tag31, **kw31)
        check(f"F31 a top-up whose {tag31.split('_')[0]} differs from the first fleet's is not pooled: POOLING REFUSED, "
              f"saying why, and nothing is decided",
              f"POOLING REFUSED with {o31}: {why31}; nothing is decided here" in b31r
              and dec(b31r).startswith("NOTHING IS DECIDED: this top-up's seeds pool with its first fleet's only where "
                                       f"commit, card, torch and shape match, and {why31}")
              and "-- this fleet alone, deciding nothing" in b31r, b31r[-900:])
    o31e, _ = topup("moved_out", pool="/nonexistent/gpu_heldout_out")
    p31e = gw("--analyze", EXP="heldout", OUT=o31e, POOL_WITH=o31)
    check("F31 POOL_WITH given to --analyze reads the top-up with that fleet (an archive unpacked elsewhere), over the "
          "path SUMMARY.txt recorded",
          f"POOLED with the first fleet {o31}:" in p31e.stdout and "TOK_MINT_NOVEL 1.0 ships" in p31e.stdout)
    # A LAUNCH AND ITS TOP-UP, END TO END, with the stand-in: the first fleet's block prints the top-up's command,
    # which is run as printed (env in the launcher's place, as F24 reads a ready line) with the stand-in's planted
    # harm moved, and the top-up's block reads the two fleets together. The stand-in plants num at +0.2 +- 0.2 on
    # k10 in the first fleet (UNRESOLVED at 7 seeds) and +0.3 in the top-up; k10_mn at 0.
    o31l = os.path.join(TMP, "f31l", "gpu_heldout_out")
    e31 = dict(PATH=env10["PATH"], EXP="heldout", DEVICE="cpu", WINDOWS=20, SEEDS="0 1 2 3 4 5 6", PAR=8,
               SMOKE_WINDOWS=5, PIN_RETOK=10, PROBE_EVERY=5, STUB_FINAL_BYTES="1000", OUT=o31l)
    p31l = subprocess.run(["bash", SCRIPT], cwd=ROOT, capture_output=True, text=True, timeout=600,
                          env=clean_env(STUB_HARM="0.2", STUB_SPREAD="0.2", **e31))
    b31l = "\n".join(block_of(p31l.stdout) or [])
    cmd31 = (re.search(r"^  top-up: (.*) bash \S+/tools/gpu_launch\.sh --go$", b31l, re.M) or [None, ""])[1]
    kv31 = dict(re.findall(r"(\w+)=('[^']*'|\S+)", cmd31))
    kv31 = {k: v.strip("'") for k, v in kv31.items()}
    oa31 = os.path.realpath(o31l)
    man31 = txt(os.path.join(o31l, "FINALS.sha256"))
    day31 = (re.match(r"=== gpu_world\.sh  (\d{4}-\d\d-\d\d)T", txt(os.path.join(o31l, "SUMMARY.txt"))) or [None, "?"])[1]
    z1000 = __import__("hashlib").sha256(b"\0" * 1000).hexdigest()
    check("F31 a stand-in launch reads UNRESOLVED at 7 seeds and prints the top-up's command with the fleet's knobs -- "
          "seeds 7-10, FILL=0, WINDOWS, PIN_RETOK, PROBE_EVERY, DEVICE and PAR, its own OUT and POOL_WITH this one -- and "
          "writes FINALS.sha256 over the act arms' finals, the pack command on a line of its own (it was the FINALS "
          "line's tail, which run as printed is a syntax error)",
          p31l.returncode == 0 and dec(b31l).startswith("UNRESOLVED at 7 seed(s): k10 is UNRESOLVED")
          and kv31 == {"EXP": "heldout", "SEEDS": "7 8 9 10", "FILL": "0", "WINDOWS": "20", "PIN_RETOK": "10",
                       "PROBE_EVERY": "5", "DEVICE": "cpu", "PAR": "8", "OUT": oa31[:-4] + "_topup_out",
                       "POOL_WITH": oa31}
          and man31.count(f"{z1000}  ckpt/") == 14 and "  ckpt/k10.s6/ckpt.pt\n" in man31
          and "  ckpt/k0.s0/" not in man31
          and f"\n  pack: tar -cf {os.path.dirname(oa31)}/gpu_heldout_{day31}_finals.tar -C {oa31} "
              f"FINALS.sha256 $(cut -c67- {oa31}/FINALS.sha256)\n" in b31l
          and "the next test's parents, which the pack: line below packs to upload" in b31l
          and "tar " not in (re.search(r"^FINALS: .*$", b31l, re.M) or [""])[0],
          f"rc {p31l.returncode}; {cmd31!r}; {man31[:200]!r}; {b31l[-1200:]}")
    # THE PACK LINE PACKS WHAT THE MANIFEST LISTS, and sha256sum -c accepts it.
    pk31 = (re.search(r"^  pack: (.*)$", b31l, re.M) or [None, "false"])[1]
    subprocess.run(["bash", "-c", pk31], capture_output=True, text=True, timeout=120)
    chk31 = subprocess.run(["bash", "-c", f"cd {oa31} && sha256sum -c --quiet FINALS.sha256"], capture_output=True,
                           text=True, timeout=120)
    try:
        with tarfile.open(f"{os.path.dirname(oa31)}/gpu_heldout_{day31}_finals.tar") as tf_:
            mem31 = sorted(tf_.getnames())
    except (OSError, tarfile.TarError):
        mem31 = []
    check("F31 ... the pack line, run as printed, packs FINALS.sha256 and the 14 finals it lists, and sha256sum -c "
          "accepts the manifest",
          chk31.returncode == 0 and len(mem31) == 15 and "FINALS.sha256" in mem31 and "ckpt/k10_mn.s3/ckpt.pt" in mem31,
          f"{chk31.stdout[-200:]} {mem31[:4]}")
    o31u = kv31.get("OUT", os.path.join(TMP, "f31l", "none"))
    p31u = subprocess.run(["bash", SCRIPT], cwd=ROOT, capture_output=True, text=True, timeout=600,
                          env=clean_env(PATH=env10["PATH"], STUB_HARM="0.3", SMOKE_WINDOWS=5, STUB_FINAL_BYTES="1000",
                                        **{k: v for k, v in kv31.items()}))
    b31u = "\n".join(block_of(p31u.stdout) or [])
    check("F31 ... the top-up, launched with that command, records its first fleet and reads the 11 seeds together: "
          "k10 FAILs and k10_mn PASSes, and TOK_MINT_NOVEL 1.0 ships",
          p31u.returncode == 0 and f"=== pool: with {oa31} (seeds 0 1 2 3 4 5 6)" in txt(os.path.join(o31u, "SUMMARY.txt"))
          and f"POOLED with the first fleet {oa31}" in b31u and "k10 n=11 a=0.0125:" in b31u
          and dec(b31u).startswith("TOK_MINT_NOVEL 1.0 ships at TOK_RETOK_EVERY 10"), b31u[-1500:])
    check("F31 ... and the top-up's block packs no finals: the next test starts from the first fleet's",
          "a top-up's: the next test starts from the first fleet's, which its block's pack: line packs" in b31u
          and "  pack: " not in b31u, [l for l in b31u.splitlines() if "FINALS" in l or "pack" in l])
    # THE LAUNCH'S OWN CHECKS, before anything is written: POOL_WITH at another EXP, naming no EXP=heldout fleet,
    # naming this OUT, or a seed of the first fleet's again.
    r31 = []
    for env31, want31 in (({"EXP": "retok", "POOL_WITH": o31l}, "only EXP=heldout and EXP=session read"),
                          ({"POOL_WITH": os.path.join(TMP, "f31l", "nothing")}, "holds no EXP=heldout fleet"),
                          ({"POOL_WITH": o31l, "OUT": o31l}, "POOL_WITH is this OUT"),
                          ({"POOL_WITH": o31l, "SEEDS": "6 7"}, "seed 6 ran in the first fleet too")):
        o_ = env31.get("OUT", os.path.join(TMP, "f31r", str(len(r31)), "gpu_heldout_out"))
        p_ = gw(**dict({"EXP": "heldout", "DEVICE": "cpu", "OUT": o_}, **env31))
        r31.append(p_.returncode == 2 and want31 in p_.stdout and "Nothing was started" in p_.stdout
                   and (o_ == o31l or not os.path.exists(o_)))
    check("F31 a launch refuses POOL_WITH, writing nothing, at another EXP, where no EXP=heldout fleet is, when it is "
          "this OUT (a launch moves that fleet aside), and when a seed of the first fleet would run again",
          r31 == [True] * 4 and os.path.exists(os.path.join(o31l, "SUMMARY.txt")), str(r31))
    # AND THE LAUNCHER: its check names the first fleet, its ready line carries POOL_WITH back, and it FAILs one
    # naming no fleet.
    l31 = subprocess.run(["bash", LAUNCHER], cwd=TMP, capture_output=True, text=True, timeout=300,
                         env=clean_env(PATH=env10["PATH"], FETCH=0, **dict(kv31, OUT=os.path.join(TMP, "f31m", "o_out"))))
    rl31 = next((ln[len("    ready: "):] for ln in l31.stdout.splitlines() if ln.startswith("    ready: ")), "")
    l31b = subprocess.run(["bash", LAUNCHER], cwd=TMP, capture_output=True, text=True, timeout=300,
                          env=clean_env(PATH=env10["PATH"], FETCH=0, EXP="heldout", DEVICE="cpu",
                                        POOL_WITH=os.path.join(TMP, "f31l", "nothing")))
    check("F31 the launcher names the top-up's first fleet, carries POOL_WITH and the top-up's knobs on its ready line, "
          "and FAILs a POOL_WITH that names no EXP=heldout fleet",
          f"PASS POOL_WITH: this fleet is the top-up of {oa31}" in l31.stdout
          and f"POOL_WITH={oa31}" in rl31 and "SEEDS='7 8 9 10'" in rl31 and "PIN_RETOK=10" in rl31
          and "FAIL POOL_WITH=" in l31b.stdout and "holds no EXP=heldout fleet" in l31b.stdout,
          l31.stdout[-600:] + l31b.stdout[-300:])

    # ---- F32: EXP=session's launch (2026-10-02, register §8 5.3a) ------------------------------------------------
    # The parents: an EXP=heldout stand-in fleet at PIN_RETOK=10 whose finals the stand-in saves as CKPT does
    # (STUB_PARENT=1: step 50, n_live 3000 + 10 x the seed, FAB_SLOTS 4096), and whose analysis writes FINALS.sha256.
    o32p = os.path.join(TMP, "f32", "gpu_heldout_out")
    k32 = dict(PATH=env10["PATH"], DEVICE="cpu", WINDOWS=20, SEEDS="0 1", PAR=4, SMOKE_WINDOWS=5, PIN_RETOK=10,
               PROBE_EVERY=5, STUB_PARENT=1)
    p32p = subprocess.run(["bash", SCRIPT], cwd=ROOT, capture_output=True, text=True, timeout=600,
                          env=clean_env(EXP="heldout", OUT=o32p, **k32))
    oa32p = os.path.realpath(o32p)
    b32 = os.path.join(TMP, "f32_book.jsonl")
    o32 = os.path.join(TMP, "f32", "gpu_session_out")
    p32 = subprocess.run(["bash", SCRIPT], cwd=ROOT, capture_output=True, text=True, timeout=600,
                         env=clean_env(EXP="session", OUT=o32, PARENTS=o32p, PARENT_ARM="k10", SESSION_WINDOWS=8,
                                       STUB_BOOK=b32, STUB_FINAL_BYTES="50000000", STUB_SLOTS_SCALE="1", **k32))
    r32 = [json.loads(l) for l in open(b32)] if os.path.exists(b32) else []
    s32 = txt(os.path.join(o32, "SUMMARY.txt"))
    sm32 = sorted(r["tag"] for r in r32 if "/smoke/" in r["argv"][r["argv"].index("--loss-curve") + 1])
    fl32 = [r for r in r32 if "/smoke/" not in r["argv"][r["argv"].index("--loss-curve") + 1]]
    want32 = {"RUN_EPOCHS": "2", "DATA_RESAMPLE": "1", "DATA_AREAS": "eng,py,num,c,x5", "DATA_N_PROCESSES": "5",
              "DATA_PHASE_SCHED": "x5|x5|x5|x5", "OPT_LR_CONTINUE": "as_logged"}
    arm32 = {"P": {"DATA_DRAW": "planned"}, "P_parent": {"DATA_DRAW": "replay", "DATA_REPLAY_SHARE": "0.27",
                                                        "DATA_REHEARSE_PARENT": "1"},
             "P_twin": {"OPT_LR": "0.0020002"}, "W": {"FAB_SLOTS": "5058"}}

    def lev32(r, k):
        return (r["sess"].get(k) if k in r["sess"] else r["env"].get(k))
    check("F32 EXP=session from PARENTS: the smoke resumes P, P_parent and P_twin at the first seed and W at the parent "
          "with the most experts (seed 1, n_live 3010), and the fleet the three at every seed and W -- 7 sessions, rc 0, "
          "no rerun",
          p32p.returncode == 0 and p32.returncode == 0 and sm32 == ["P.s0", "P_parent.s0", "P_twin.s0", "W.s1"]
          and sorted(r["tag"] for r in fl32) == ["P.s0", "P.s1", "P_parent.s0", "P_parent.s1", "P_twin.s0", "P_twin.s1",
                                                 "W.s1"], f"rc {p32p.returncode}/{p32.returncode}; {sm32}; "
                                                          f"{[r['tag'] for r in fl32]}; {p32.stdout[-400:]!r}")
    check("F32 ... every session resumes its parent's final (CKPT_RESUME the parent's directory, RUN_SEED its seed) into "
          "a new CKPT_DIR, with a second epoch resampled, x5 appended at 5/4 of the parents' stream (4,725 bytes over 5 "
          "processes), pure-add, the rate as logged, the probe's pins, the parent arm's cadence after them and its own "
          "arm's settings after those: P_parent's rehearsal, P_twin's OPT_LR x 1.0001, W's FAB_SLOTS max(4096, 3010 + "
          "2048); --max-windows 8, probe series and flush bytes",
          all(r["ckpt"].get("CKPT_RESUME") == os.path.join(oa32p, "ckpt", "k10.s" + r["tag"][-1])
              and r["sess"]["RUN_SEED"] == r["tag"][-1]
              and r["ckpt"].get("CKPT_DIR") == os.path.join(o32, "ckpt", r["tag"]) and r["ckpt"].get("CKPT_EVERY") == "0"
              and all(r["sess"][k] == v for k, v in want32.items()) and r["env"]["DATA_STREAM_BYTES"] == "4725"
              and r["env"]["EVAL_HOLDOUT_WINDOWS"] == "256" and r["env"]["EVAL_RETENTION_N"] == "24"
              and r["env"]["EVAL_GENERATE"] == "0" and r["pins"]["EVAL_RETENTION_EVERY"] == "5"
              and r["retok"] == "10" and r["env"]["TOK_MINT_NOVEL"] == "0"
              and all(lev32(r, k) == v for k, v in arm32[r["tag"].rsplit(".s", 1)[0]].items())
              and (r["tag"].startswith("P_parent") or r["env"]["DATA_DRAW"] == "planned")
              and r["argv"][r["argv"].index("--max-windows") + 1] == "8"
              and "--probe-series" in r["argv"] and "--flush-bytes" in r["argv"] for r in fl32) and len(fl32) == 7,
          str([(r["tag"], r["ckpt"], r["sess"]) for r in fl32][:2]))
    st32 = txt(os.path.join(o32, "logs", "_started.txt"))
    check("F32 ... SUMMARY names the parents and the sha256 check, the session's pins, W and each parent's ids minted after "
          "its last cut (0 and 6, off its final); the disk check prices W's 3 files at W's smoke checkpoint (61 MB at 5,058 "
          "slots) and the other 18 at the others' largest (50 MB), 2.2 GB, where pricing all 21 at W's read 2.6; and each "
          "session's book line carries its parent's step (base=50), which the dashboard takes off its progress lines",
          f"=== parents: k10 at seeds 0 1, from {oa32p} (4 file(s) sha256-checked against its FINALS.sha256)" in s32
          and "=== session: 8 windows, resumed from its parent's final at its seed" in s32
          and "DATA_STREAM_BYTES=4725 DATA_PHASE_SCHED=x5|x5|x5|x5 OPT_LR_CONTINUE=as_logged; P_twin OPT_LR=0.0020002" in s32
          and "=== W: FAB_SLOTS=5058 at k10.s1, the parent with the most experts (n_live 3010 + W_HEADROOM 2048, "
              "against its 4096 slots)" in s32
          and "=== parents' ids minted after their last cut (in no window a parent trained; its sessions' first cut "
              "holds them, and F leaves out what they move): s0 0 | s1 6" in s32
          and "  smoke checkpoints: the largest but W's was 50 MB, W's 61 MB; deleted" in s32
          and re.search(r"^=== disk: checkpoints may take about 2\.2 GB \(50 MB x 2 per file, W's 61 MB x 2\) of ", s32,
                        re.M) is not None
          and "=== plan: EXP=session; arms P P_parent P_twin, plus W at the parent with the most experts; window cap 8;" in s32
          and st32.count(" base=50") == 7, [l for l in s32.splitlines() if l.startswith("=== ")][4:12])
    # WITHOUT PARENTS: the parents stage first (k10 at both seeds, one whole epoch: cap 60, finals kept under
    # OUT/parents/ckpt with a FINALS.sha256), then the sessions' smoke from its finals, then the sessions.
    b32b = os.path.join(TMP, "f32b_book.jsonl")
    o32b = os.path.join(TMP, "f32b", "gpu_session_out")
    p32b = subprocess.run(["bash", SCRIPT], cwd=ROOT, capture_output=True, text=True, timeout=600,
                          env=clean_env(EXP="session", OUT=o32b, PARENT_ARM="k10", SESSION_WINDOWS=8, STUB_BOOK=b32b,
                                        **k32))
    r32b = [json.loads(l) for l in open(b32b)] if os.path.exists(b32b) else []
    s32b = txt(os.path.join(o32b, "SUMMARY.txt"))
    st32b = [(r["tag"], r["argv"][r["argv"].index("--loss-curve") + 1].split(os.sep)[-2]) for r in r32b]
    oa32b = os.path.realpath(o32b)
    check("F32 without PARENTS: the parents' arm smoked fresh, the parents stage (k10 at both seeds, a whole epoch each, "
          "saving its final under OUT/parents/ckpt at any KEEP_CKPT), the sessions' smoke from its finals, the 7 sessions; "
          "FINALS.sha256 beside the parents, an ETA by two stages, and W's files priced at the parents' smoke final scaled "
          "by (slots + W_HEADROOM) / slots, W not yet run",
          p32b.returncode == 0 and len(st32b) == 14
          # EACH STAGE'S RUNS START AT ONCE, SO THE BOOK ORDERS THE STAGES AND NOT THE RUNS INSIDE ONE.
          and st32b[0] == ("k10.s0", "smoke") and sorted(st32b[1:3]) == [("k10.s0", "parents"), ("k10.s1", "parents")]
          and sorted(st32b[3:7]) == [("P.s0", "sessions"), ("P_parent.s0", "sessions"), ("P_twin.s0", "sessions"),
                                     ("W.s1", "sessions")]
          and sorted(st32b[7:]) == [(t, "curves") for t in ("P.s0", "P.s1", "P_parent.s0", "P_parent.s1", "P_twin.s0",
                                                             "P_twin.s1", "W.s1")]
          and all(r["ckpt"] == {"CKPT_DIR": os.path.join(oa32b, "parents", "ckpt", r["tag"]), "CKPT_EVERY": "0"}
                  and r["argv"][r["argv"].index("--max-windows") + 1] == "60" for r in r32b[1:3])
          and all(r["ckpt"].get("CKPT_RESUME") == os.path.join(oa32b, "parents", "ckpt", "k10.s" + r["tag"][-1])
                  for r in r32b[3:])
          and txt(os.path.join(o32b, "parents", "FINALS.sha256")).count("  ckpt/k10.s") == 4
          and re.search(r"^=== ETA by waves: about \d+ min \(\d+ s\): 2 parent run\(s\) in 1 wave\(s\), then 7 "
                        r"session\(s\) in 2 wave\(s\), over 4 slot\(s\)", s32b, re.M) is not None
          and "---- 2a. parents stage started" in s32b and "---- 2b. the sessions' smoke" in s32b
          # W'S FILES PRICED BEFORE W EXISTS: the parents' smoke final (4,096 slots) x (4096 + 2048) / 4096.
          and "  smoke checkpoints: the largest but W's was 0 MB, W's priced at 0 MB, the parent's x (4096 + 2048) / "
              "4096 slots; deleted" in s32b,
          f"rc {p32b.returncode}; {st32b}; {p32b.stdout[-300:]!r}")
    # THE LAUNCH'S REFUSALS, before anything is written.
    r32r = []
    bad32 = os.path.join(TMP, "f32bad")
    shutil.copytree(o32p, bad32, ignore=shutil.ignore_patterns("code"))
    with open(os.path.join(bad32, "ckpt", "k10.s1.dyntok.json"), "a") as fh_:
        fh_.write(" ")
    for env32r, want32r in (({"PARENT_ARM": "k10x"}, "PARENT_ARM='k10x' is not one of EXP=heldout's act arms"),
                            ({"PARENTS": TMP}, "holds no FINALS.sha256"),
                            ({"SEEDS": "0 1 2"}, "FINALS.sha256 lists no ckpt/k10.s2"),
                            ({"PARENTS": bad32}, "a final does not match its sha256 in FINALS.sha256"),
                            ({"WINDOWS": "200"}, "areas were generated 10000 bytes long, and a session at "
                                                 "DATA_STREAM_BYTES=47250"),
                            ({"EXTRA": "DATA_AREAS=eng"}, "EXTRA sets DATA_AREAS, which EXP=session's parents and "
                                                          "sessions pin"),
                            ({"FILL": "1"}, "FILL=1: EXP=session's seeds are its parents'")):
        o_ = os.path.join(TMP, "f32r", str(len(r32r)), "gpu_session_out")
        e_ = dict(k32, EXP="session", OUT=o_, PARENTS=o32p, PARENT_ARM="k10")
        e_.update(env32r)
        p_ = subprocess.run(["bash", SCRIPT], cwd=ROOT, capture_output=True, text=True, timeout=300, env=clean_env(**e_))
        r32r.append((p_.returncode == 2 and want32r in p_.stdout and "Nothing was started" in p_.stdout
                     and not os.path.exists(os.path.dirname(o_)), p_.stdout[-200:]))
    check("F32 a launch refuses, writing nothing: a PARENT_ARM that is no act arm, PARENTS with no manifest, a manifest "
          "without a seed's final, a final whose sha256 moved, parents generated at another stream than the sessions' "
          "keeps, EXTRA moving a session's data lever, and FILL=1",
          [x[0] for x in r32r] == [True] * 7, str([x[1] for x in r32r if not x[0]][:2]))
    # THE LAUNCHER: its check names the parents, its disk check counts the sessions' files (and a parents stage's),
    # and its ready line carries the session's knobs.
    l32 = subprocess.run(["bash", LAUNCHER], cwd=TMP, capture_output=True, text=True, timeout=300,
                         env=clean_env(PATH=env10["PATH"], EXP="session", DEVICE="cpu", FETCH=0, CKPT_MB=50, SEEDS="0 1",
                                       PARENTS=o32p, PARENT_ARM="k10", SESSION_WINDOWS=8, W_HEADROOM=100,
                                       OUT=os.path.join(TMP, "f32l", "gpu_session_out")))
    rl32 = next((ln[len("    ready: "):] for ln in l32.stdout.splitlines() if ln.startswith("    ready: ")), "")
    l32b = subprocess.run(["bash", LAUNCHER], cwd=TMP, capture_output=True, text=True, timeout=300,
                          env=clean_env(PATH=env10["PATH"], EXP="session", DEVICE="cpu", FETCH=0, CKPT_MB=50, SEEDS="0 1",
                                        PARENT_ARM="k10", KEEP_CKPT=0, OUT=os.path.join(TMP, "f32l", "b")))
    l32c = subprocess.run(["bash", LAUNCHER], cwd=TMP, capture_output=True, text=True, timeout=300,
                          env=clean_env(PATH=env10["PATH"], EXP="session", DEVICE="cpu", FETCH=0, SEEDS="0 1 2",
                                        PARENTS=o32p, PARENT_ARM="k10", OUT=os.path.join(TMP, "f32l", "c")))
    l32d = subprocess.run(["bash", LAUNCHER], cwd=TMP, capture_output=True, text=True, timeout=300,
                          env=clean_env(PATH=env10["PATH"], EXP="session", DEVICE="cpu", FETCH=0, CKPT_MB=1000000,
                                        SEEDS="0 1", PARENTS=o32p, PARENT_ARM="k10", OUT=os.path.join(TMP, "f32l", "d")))
    check("F32 the launcher PASSes EXP=session and its PARENTS, budgets 7 sessions x 3 files (2.1 GB at 50 MB, W's 3 at "
          "50 x (4096 + 100) / 4096), or a parents stage's 2 x 3 files alone at KEEP_CKPT=0 (0.6 GB), FAILs PARENTS without "
          "a seed's final and a disk too small, pricing W's files at (4096 + 2048) / 4096 of the rest's, and its ready "
          "line carries PARENTS, PARENT_ARM, SESSION_WINDOWS and W_HEADROOM",
          "PASS EXP=session" in l32.stdout and f"PASS PARENTS: k10's finals at seeds 0 1, in {oa32p}'s FINALS.sha256" in l32.stdout
          and "the kept checkpoints may need 2.1 GB at 2 seed(s)" in l32.stdout
          and "the kept checkpoints may need 0.6 GB at 2 seed(s)" in l32b.stdout
          and "PASS no PARENTS: a parents stage trains k10 at seeds 0 1 first" in l32b.stdout
          and "FAIL PARENTS: ckpt/k10.s2/ckpt.pt is missing or not in its FINALS.sha256" in l32c.stdout
          and "(21 files x 2 x 1000000 MB, W's 3 at 1500000 MB at 2 seed(s))" in l32d.stdout
          and f"PARENTS={o32p}" in rl32 and "PARENT_ARM=k10" in rl32 and "SESSION_WINDOWS=8" in rl32
          and "W_HEADROOM=100" in rl32, l32.stdout[-700:] + l32b.stdout[-300:] + l32c.stdout[-300:])
    # ---- F33: EXP=session's reading, rule and block (2026-10-02, register §8 5.3a) ---------------------------------
    # Fleets written by hand, each number chosen. A session's resume-start reading of each old area is its parent's R,
    # 2.0 + 0.1 x the area's index + 0.001 x the seed, and its R reading that plus F: `f` on P (num + f_num), `f_pp` on
    # P_parent (num + f_pp_num), each + `spread` (spread_pp) by the seed's parity; P_twin at P's F + `twin` by the
    # parity; W at P's F, at the parent W_SEED. x5 at R is 3.0 - gain (gain_pp on P_parent, 0.02 more on W) and 6.0 at
    # its arrival. R's pairing against the start holds each area's F with SD `pw` over 128 windows a half, the start's
    # 128 zeros against the parent's R. Every session trains 5,000 windows in 400 s past its parent's 20,000.
    SE_AR = ("eng", "py", "num", "c")

    def se_summary(out, *, seeds, commit="abc1234", card="NVIDIA H100 PCIe, 81559", torch_="torch 2.7.0, CUDA 12.8",
                   pool=None, sw=5000, par=24, w_seed=3, late=None):
        n_, mib = card.split(", ")
        L = [f"=== gpu_world.sh  2026-10-03T12:00:00Z  commit {commit}",
             f"=== code: this fleet runs its own copy, {out}/code (gpu_world.sh, run.py, src/, tools/fleet_dash.sh; "
             f"sha256 0123456789abcdef), taken from commit {commit} at launch: a git pull during the fleet reaches none of it",
             "    index, name, memory.total [MiB], memory.used [MiB]", f"    0, {n_}, {mib} MiB, 1 MiB",
             "=== 26 CPU core(s), 1 GPU(s), device=cuda", f"=== {torch_}",
             f"=== 20000 windows per run, DATA_STREAM_BYTES=3780000, seeds: {seeds}, EXTRA=''",
             f"=== plan: EXP=session; arms P P_parent P_twin, plus W at the parent with the most experts; window cap {sw}; "
             f"CAL_WINDOWS 600; LM_CTX {CTX}",
             f"=== parents: k1000 at seeds {seeds}, from /data/gpu_heldout_out (14 file(s) sha256-checked against its "
             f"FINALS.sha256)",
             f"=== session: {sw} windows, resumed from its parent's final at its seed, the pins and the parent arm's "
             f"settings, then RUN_EPOCHS=2 DATA_RESAMPLE=1 DATA_AREAS=eng,py,num,c,x5 DATA_N_PROCESSES=5 "
             f"DATA_STREAM_BYTES=4725000 DATA_PHASE_SCHED=x5|x5|x5|x5 OPT_LR_CONTINUE=as_logged; P_twin OPT_LR=0.0020002; "
             f"W FAB_SLOTS max(the parent's slots, its n_live + 2048)",
             f"=== kept checkpoints: ON, one final checkpoint per run under {out}/ckpt, and beside it the retention "
             f"probe's best saves (ckpt.pt.best and .best.prev): up to 3 checkpoint files per run, all counted in the "
             f"disk check",
             "=== pins: DATA_DRAW=planned pinned, DATA_SYNTH_HOLDOUT=1 pinned, EVAL_RETENTION_EVERY=700 pinned, "
             "EVAL_HOLDOUT_WINDOWS=256 pinned, EVAL_RETENTION_N=24 pinned, EVAL_GENERATE=0 pinned, TOK_MINT_NOVEL=0 pinned"]
        if pool:
            L.append(f"=== pool: with {pool} (seeds 0 1 2 3 4 5 6): this fleet is its top-up, and its analysis reads "
                     f"the two fleets' seeds together where commit, card, torch and shape match")
        L += [f"=== {len(seeds.split()) * 3 + 1} run(s), {par} at a time",
              "=== ETA by waves: about 7 min (420 s): 22 session(s) in 1 wave(s), over 24 slot(s), each run its windows "
              "at 13.00 windows/s plus 15 s of startup; each run's reads (a session's resume start and R) and saves come "
              "on top",
              f"=== W: FAB_SLOTS=6144 at k1000.s{w_seed}, the parent with the most experts (n_live 4096 + W_HEADROOM "
              f"2048, against its 4096 slots)"]
        if late is not None:
            L.append("=== parents' ids minted after their last cut (in no window a parent trained; its sessions' first cut "
                     "holds them, and F leaves out what they move): " + " | ".join(f"s{s_} {late.get(int(s_), 0)}"
                                                                                    for s_ in seeds.split()))
        L += ["---- 2. fleet started 12:10:00Z", "---- fleet finished in 8 min (480 s)"]
        write(os.path.join(out, "SUMMARY.txt"), "\n".join(L) + "\n")

    def se_run(out, name, seed, *, f=0.0, f_num=0.0, x5=3.0, pw=0.1, capped=True, nores=False, noseries=False,
               anchor=0.0, nlive=4096, births=900, widened=0, own=None):
        tag, win, base = f"{name}.s{seed}", 5000, 20000
        v0 = {SE_AR[k]: 2.0 + 0.1 * k + 0.001 * seed for k in range(4)}
        # A PARENT THAT MINTED AFTER ITS LAST CUT: the session reads its start again at its own first cut, `own` off
        # the parent's view per area, and R is that start plus F.
        vo = {a: v + (own or {}).get(a, 0.0) for a, v in v0.items()}
        vr = {a: v + f + (f_num if a == "num" else 0.0) for a, v in vo.items()}

        def row(step, kind, closure, vals, pd=None, off=0.0):
            ars = {a: {"control": v + off, "report": v + off, "seen_by_parent": a != "x5"} for a, v in vals.items()}
            m_ = sum(x["report"] for x in ars.values()) / len(ars)
            r_ = {"step": step, "kind": kind, "closure": closure, "control": m_, "report": m_, "windows": 256 * len(ars),
                  "nonfinite": 0, "paired_sd": None, "areas": ars}
            if pd is not None:
                r_["paired"] = {a: {h: [128, m, s_] for h in ("control", "report")} for a, (m, s_) in pd.items()}
            return r_
        rows = [] if nores else [
            row(base, "resume", "memory-off", v0, pd={a: (anchor, 0.01 if anchor else 0.0) for a in v0}),
            row(base, "resume", "memory-on", v0, off=-0.01, pd={a: (0.0, 0.0) for a in v0})]
        if own and not nores:
            rows += [row(base, "resume_own", "memory-off", vo, pd={a: (vo[a] - v0[a], 0.02) for a in v0}),
                     row(base, "resume_own", "memory-on", vo, off=-0.01, pd={a: (vo[a] - v0[a], 0.02) for a in v0})]
        pr = {a: (vr[a] - vo[a], pw) for a in v0}
        rows += [row(base + 1, "phase", "memory-off", dict(v0, x5=6.0)),
                 row(base + win, "boundary", "memory-off", dict(vr, x5=x5), pd=pr),
                 row(base + win, "boundary", "memory-on", dict(vr, x5=x5), off=-0.01, pd=pr)]
        rh = "('fired', '4 vs 4')" if name == "P_parent" else "('unreachable', 'None vs 4 -- DATA_REHEARSE_PARENT=0')"
        write(os.path.join(out, "logs", tag + ".log"), "\n".join(
            ["=== device=cuda amp=off tf32=(True, True) torch_seed=1",
             f"=== {base + win} windows run total ({win} trained by this process, resumed at {base}), {win} flushes this "
             f"process, {base + win} optimizer steps run total, 2 epoch(s) in 400.0s (12.5 w/s this process)"]
            + ([f"WARNING: loop: stopped at max_windows={win} window(s) trained by THIS process"] if capped else [])
            + ["=== R STAGE -- the did-it-fire surfaces:",
               "       opt.continue.pricing                         logged parent: floor",
               f"       fab.n_live                                   {nlive}",
               f"       fab.births                                   {births}",
               f"       fab.resume_widened                           {widened}",
               f"       gate:data.rehearse_parent                    {rh}"]) + "\n")
        write(os.path.join(out, "curves", tag + ".json"), json.dumps([2.0] * 50))
        if not noseries:
            write(os.path.join(out, "curves", tag + ".probe.json"), json.dumps(rows))
        with open(os.path.join(out, "logs", "_done.txt"), "a") as fh:
            fh.write(f"{tag} rc=0 secs=420\n")

    def se_fleet(out, seeds, *, f=0.0, f_pp=0.0, f_num=0.0, f_pp_num=0.0, spread=0.0, spread_pp=0.0, twin=0.0,
                 gain=0.0, gain_pp=0.0, pw=0.1, w_seed=3, skip=(), nores=(), noseries=(), short=(), anchor=(), late=None,
                 own=None, **kw):
        se_summary(out, seeds=" ".join(map(str, seeds)), w_seed=w_seed, late=late, **kw)
        own_ = (lambda s_: own if own and (late or {}).get(s_, 0) > 0 else None)
        for s_ in seeds:
            par_ = 1 if s_ % 2 == 0 else -1
            for nm, f_, fn_, x5_ in (("P", f + par_ * spread, f_num, 3.0 - gain),
                                     ("P_parent", f_pp + par_ * spread_pp, f_pp_num, 3.0 - gain_pp),
                                     ("P_twin", f + par_ * (spread + twin), f_num, 3.0 - gain)):
                t_ = f"{nm}.s{s_}"
                if t_ not in skip:
                    se_run(out, nm, s_, f=f_, f_num=fn_, x5=x5_, pw=pw, nores=t_ in nores, noseries=t_ in noseries,
                           capped=t_ not in short, anchor=0.001 if t_ in anchor else 0.0, own=own_(s_))
        if w_seed in seeds:
            se_run(out, "W", w_seed, f=f + (1 if w_seed % 2 == 0 else -1) * spread, f_num=f_num, x5=3.0 - gain - 0.02,
                   pw=pw, nlive=4500, births=1300, widened=3, own=own_(w_seed))

    def se_read(tag, seeds, pool_env=None, **kw):
        o_ = os.path.join(TMP, "f33", tag, "gpu_session_out")
        se_fleet(o_, seeds, **kw)
        p_ = gw("--analyze", EXP="session", OUT=o_, **({"POOL_WITH": pool_env} if pool_env else {}))
        return o_, p_, txt(os.path.join(o_, "ANALYSIS.txt")), "\n".join(block_of(p_.stdout) or [])

    from statistics import NormalDist
    T33 = 0.05 / (NormalDist().inv_cdf(1 - 0.05 / 4) + NormalDist().inv_cdf(0.8))
    rate33 = "at the measurement protocol's rate (OPT_LR_CONTINUE=as_logged, CONTRACT-Q-DATA-7), which 5.2 re-reads at "
    zero33 = " ".join(f"{a} +0.0000 [+0.0000,+0.0000]" for a in SE_AR)
    o33, p33, a33, b33 = se_read("take_pp", range(7), twin=0.01, gain_pp=0.1)
    check("F33 a harmless fleet: P and P_parent each PASS on every old area by the eps rule (F = R - start, the "
          "areas its cells, at 0.025 a look: Holm's 0.0125 on the first, the upper bound at t(0.975)); both admitted, x5's "
          "R reading on P_parent - on P (-0.1000, its upper bound below 0) takes P_parent (O9), labelled at the "
          "measurement protocol's rate; the block, within 80 lines and equal to PASTE_BACK.txt, carries every parent's "
          "row, the anchor and both rule rows",
          p33.returncode == 0 and f"  P n=7 a=0.0125: {zero33} -> PASS" in b33
          and f"  P_parent n=7 a=0.025: {zero33} -> PASS" in b33
          and "per old area (4), F = R - start over the parents, each look (7 parents; a top-up's pooled 11) at "
              "0.025: mean [lower at t(1 - a/4), Holm's a across P and P_parent; one-sided upper at t(0.975)]" in b33
          and "O9 (the new area): x5 at R, P_parent - P paired by parent: -0.1000 [-0.1000,-0.1000] n=7" in b33
          and dec(b33).startswith("P_parent is taken (O9): both are admitted, and x5's R reading on P_parent - on P has "
                                  "its one-sided upper bound -0.1000 below 0: P_parent learns the new area better. The "
                                  "continue preset's provisional rehearsal (DATA_REHEARSE_PARENT=1, 'replay' 0.27) holds "
                                  + rate33 + "the preset's; no training default moves (ε 0.05 bits/byte per old area, "
                                  "7 parent(s))")
          and "ANCHOR (O2): the resume start against the parent's R, item for item: equal in 22 of 22 session(s)" in b33
          and 0 < len(block_of(p33.stdout)) <= 80
          and block_of(p33.stdout) == txt(os.path.join(o33, "PASTE_BACK.txt")).splitlines()
          and re.search(r"^  s6 +(\+0\.0000 ){3}\+0\.0000 \| (\+0\.0000 ){3}\+0\.0000 \| +3\.0000 +2\.9000$", b33, re.M)
          is not None and "  synthetic source  as_logged" in b33.splitlines()[1],
          b33[-1800:])
    one33 = math.sqrt(0.01 ** 2 / 2 + 0.1 ** 2 / 128)
    check("F33 ... and beside it, deciding nothing: x5's learning (6.0 -> 3.0, 2.9 on P_parent), 5.1's SDs per old area "
          f"-- between-run 0.0071 (twins at +-0.01: RMS / √2), per-window 0.1000, one session {one33:.4f} against the "
          f"gate's {T33:.4f} (K 4), which it meets at 128 windows a half -- W at its parent (FAB_SLOTS 6144, x5 -0.0200, "
          "n_live 404 past the parent's slots, births, resume_widened), the pricing every session states, the rehearsal "
          "P_parent fired, rates, and the ETA by waves against the wall",
          "x5's learning (its first in-run reading -> R, mean over parents): P 6.0000 -> 3.0000 | P_parent 6.0000 -> "
          "2.9000 | P_twin 6.0000 -> 3.0000" in b33
          and f"= {T33:.4f}, K 4:" in b33
          and f"    num: between 0.0071 (n=7) | per-window 0.1000 | one session {one33:.4f}: meets it at 128 windows a "
              f"half" in b33
          and "  W (NEW-20) at the parent s3, FAB_SLOTS 6144 (its n_live 4096 + 2048; its slots 4096): W - P F eng +0.0000 "
              "py +0.0000 num +0.0000 c +0.0000, x5 -0.0200; n_live at the end W 4500 (404 past the parent's 4096 slots), "
              "P 4096; births W 1300, P 900; fab.resume_widened 3" in b33
          and "opt.continue.pricing (each session's rate, CONTRACT-Q-DATA-7): 'logged parent: floor' 22 of 22" in b33
          and "data.rehearse_parent FIRED (O9's rehearsal): P 0 of 7 | P_parent 7 of 7 | P_twin 0 of 7 | W 0 of 1" in b33
          and "windows/s per session: P 12.50 [12.50-12.50]" in b33
          and "this fleet: 110,000 session windows in 480 s of the sessions' wall = 229.17 windows/s aggregate; ETA by "
              "waves 420 s, took 480 s: 1.14x" in b33,
          [l for l in b33.splitlines() if l.startswith("  ") or "SDs" in l][-14:])
    # PARENTS THAT MINTED AFTER THEIR LAST CUT (2026-10-02, the review of §8 5.3a): seeds 0, 1, 4 and 6 hold 6, 24, 6 and 6
    # such ids (sessreplay.py's counts at seeds 0-6), so their sessions read a second start at their own first cut, py
    # -0.4 and num -0.07 off the parent's view, and R is that start plus F = 0.
    late33 = {0: 6, 1: 24, 2: 0, 3: 0, 4: 6, 5: 0, 6: 6}
    _, _, a33l, b33l = se_read("late", range(7), late=late33, own={"py": -0.4, "num": -0.07})
    check("F33 parents that minted after their last cut: F subtracts each session's start at its own first cut "
          "('resume_own'), so sessions that moved nothing read 0 on every area and both candidates PASS (against the "
          "'resume' row py would read -0.4000 at four parents); the block reports each parent's count and what those ids "
          "moved, py -0.4000 and num -0.0700 at the 12 of 22 sessions whose first cut held them; the anchor reads the "
          "'resume' row",
          f"  P n=7 a=0.0125: {zero33} -> PASS" in b33l and f"  P_parent n=7 a=0.025: {zero33} -> PASS" in b33l
          and "  the parents' ids minted after their last cut (s0 6 | s1 24 | s2 0 | s3 0 | s4 6 | s5 0 | s6 6): the start "
              "at 12 of 22 session(s)' own first cut - at the parent's last, mean [min, max]: eng +0.0000 [+0.0000,+0.0000] "
              "py -0.4000 [-0.4000,-0.4000] num -0.0700 [-0.0700,-0.0700] c +0.0000 [+0.0000,+0.0000]; F leaves it out"
              in b33l
          and "ANCHOR (O2): the resume start against the parent's R, item for item: equal in 22 of 22 session(s)" in b33l
          and re.search(r"^  P +s1 +5000 win  eng \+0\.00000  py \+0\.00000  num \+0\.00000  c \+0\.00000  x5 3\.00000$",
                        a33l, re.M) is not None, b33l[-1500:])
    _, _, _, b33f = se_read("p_fails", range(7), f_num=0.2, pw=0.2)
    n33 = math.ceil(0.2 ** 2 / (T33 ** 2 - 0))
    check("F33 P FAILs on num (+0.2000, its lower bound past eps) and P_parent PASSes: P_parent is taken, the one "
          f"admitted; at a per-window SD of 0.2 and twins equal to P a session needs {n33} windows a half",
          "num +0.2000 [+0.2000,+0.2000] c +0.0000 [+0.0000,+0.0000] -> FAIL" in b33f
          and dec(b33f).startswith("P_parent is taken (O9): P_parent is the one admitted; P FAILs. The continue preset's")
          and f"    eng: between 0.0000 (n=7) | per-window 0.2000 | one session {0.2 / math.sqrt(128):.4f}: needs {n33} "
              f"windows a half" in b33f, dec(b33f) + str([l for l in b33f.splitlines() if "eng: between" in l]))
    _, _, _, b33t = se_read("tie_pp", range(7), f_num=0.02, f_pp_num=0.01, twin=0.03)
    _, _, _, b33u = se_read("tie_p", range(7), f_num=0.01, f_pp_num=0.02)
    check("F33 both admitted and the new area tied (x5 P_parent - P [0, 0]): the smaller worst-area mean F takes it (C25), "
          "P_parent at +0.0100 against P's +0.0200, and P the other way round; twins 0.03 apart make the between-run SD "
          "alone exceed the gate's: O10's second-seed replay",
          dec(b33t).startswith("P_parent is taken (O9): both are admitted and the new area ties (x5 P_parent - P "
                               "[+0.0000,+0.0000]), so the smaller worst-area mean F takes it (C25): P +0.0200, P_parent "
                               "+0.0100.")
          and dec(b33u).startswith("P is taken (O9): both are admitted and the new area ties (x5 P_parent - P "
                                   "[+0.0000,+0.0000]), so the smaller worst-area mean F takes it (C25): P +0.0100, "
                                   "P_parent +0.0200. The preset's rehearsal is not needed " + rate33 + "the preset's, "
                                   "recorded so for 5.2; no training default moves")
          and "    c: between 0.0212 (n=7) | per-window 0.1000 | one session " in b33t
          and "the between-run SD alone exceeds it: O10's second-seed replay" in b33t, dec(b33t) + "\n" + dec(b33u))
    o33u, _, _, b33up = se_read("topup", range(7), spread_pp=0.1, gain_pp=0.1)
    oa33 = os.path.realpath(o33u)
    check("F33 P admitted beside P_parent UNRESOLVED below the cap tops up first: the next 4 parents to the cap of 11, "
          "FILL=0, the parents' arm, PAR, its own OUT and POOL_WITH this one (its parents stage trains the new parents)",
          dec(b33up).startswith("UNRESOLVED at 7 parent(s): P_parent is UNRESOLVED, P is admitted; top up to the cap of "
                                "11 on this card and torch with the command below (its parents stage trains the new "
                                "parents first)")
          and f"  top-up: EXP=session SEEDS='7 8 9 10' FILL=0 PARENT_ARM=k1000 PAR=24 OUT={oa33[:-4]}_topup_out "
              f"POOL_WITH={oa33} bash {ROOT}/tools/gpu_launch.sh --go" in b33up, b33up[-900:])
    _, _, _, b33c = se_read("cap", range(11), spread_pp=0.1)
    _, _, _, b33cu = se_read("capu", range(11), f_num=0.2, spread_pp=0.1)
    _, _, _, b33n = se_read("none", range(7), f_num=0.2, f_pp_num=0.2)
    check("F33 at the cap of 11 the one admitted is taken beside the other UNRESOLVED; one FAILing beside one UNRESOLVED "
          "at the cap is reported unresolved; both FAILing admits neither -- nothing ships, the next arms named, O9 "
          "escalating only when every candidate FAILs",
          dec(b33c).startswith("P is taken (O9): P is the one admitted; P_parent is UNRESOLVED at the parent cap.")
          and "top-up:" not in b33c
          and dec(b33cu).startswith("UNRESOLVED at the cap: P FAILs and P_parent is UNRESOLVED at the parent cap; reported "
                                    "so, nothing ships, and the next arms run (P+parent at 'replay' 0.40; P+parent with "
                                    "W's headroom; 5.2's continuation rates)")
          and dec(b33n).startswith("neither is admitted: P and P_parent both FAIL; nothing ships, and the next arms run "
                                   "(P+parent at 'replay' 0.40; P+parent with W's headroom; 5.2's continuation rates), O9 "
                                   "escalating only when every candidate, these included, FAILs"),
          dec(b33c) + "\n" + dec(b33cu) + "\n" + dec(b33n))
    _, _, a33m, b33m = se_read("missing", range(7), noseries=("P.s5",), nores=("P_parent.s2",), anchor=("P_twin.s3",),
                               short=("P_twin.s4",))
    check("F33 a session with no series and one with no resume-start row are named and left out (n=6); an anchor that "
          "moved is named and F still subtracts the session's own start; a session that ended before its window cap is "
          "flagged",
          "left out (no endpoint): P.s5 P_parent.s2" in b33m
          and re.search(r"^  P +s5 .*NO PROBE SERIES$", a33m, re.M) is not None
          and re.search(r"^  P_parent +s2 .*NO RESUME-START ROW  x5 3\.00000$", a33m, re.M) is not None
          and f"  P n=6 a=0.0125: {zero33} -> PASS" in b33m and f"  P_parent n=6 a=0.025: {zero33} -> PASS" in b33m
          and "equal in 19 of 20 session(s); DIFFERS in 1 (largest |mean| 0.001, P_twin.s3: F still subtracts the "
              "session's own start)" in b33m
          and "  ENDED BEFORE ITS WINDOW CAP: P_twin.s4" in b33m, b33m[:1500])
    _, _, _, b33x = se_read("past", range(12))
    _, _, _, b33z = se_read("nopp", range(7), skip=tuple(f"P_parent.s{s_}" for s_ in range(7)))
    check("F33 parents past the cap of 11 are not read, and the block says which; with no P_parent session read nothing "
          "is decided on P alone",
          "parents past the cap of 11, not read: 11" in b33x and f"  P n=11 a=0.0125: {zero33} -> PASS" in b33x
          and dec(b33z) == "UNDECIDED: P_parent has no reading"
          and "  P_parent: NO READING at any parent -- no evidence either way, not a pass" in b33z,
          dec(b33x) + "\n" + dec(b33z))

    # ---- F34: a session top-up pooled with its first fleet (2026-10-02, register §8 5.3a) ----------------------------
    # The first fleet reads P_parent UNRESOLVED at 7 parents (+-0.06 by parity); its top-up's parents 7-10 read 0, so
    # the pooled 11, the second look at 0.025, admit both, and x5 (-0.1) takes P_parent.
    o34 = os.path.join(TMP, "f34", "gpu_session_out")
    se_fleet(o34, range(7), spread_pp=0.06, gain_pp=0.1)
    p34a = gw("--analyze", EXP="session", OUT=o34)

    def se_topup(tag, seeds=range(7, 11), pool=o34, **kw):
        o_ = os.path.join(TMP, "f34", tag)
        se_fleet(o_, seeds, gain_pp=0.1, pool=pool, w_seed=10, **kw)
        p_ = gw("--analyze", EXP="session", OUT=o_)
        return o_, "\n".join(block_of(p_.stdout) or [])
    o34t, b34t = se_topup("gpu_session_topup_out")
    check("F34 the first fleet alone is UNRESOLVED and asks for the top-up; the top-up, recorded as its pool, reads the "
          "11 parents together -- its own marked * -- and both are admitted: P_parent is taken on the new area",
          dec("\n".join(block_of(p34a.stdout) or [])).startswith("UNRESOLVED at 7 parent(s): P_parent is UNRESOLVED")
          and f"POOLED with the first fleet {o34}: its parents and this top-up's (marked *) are read together" in b34t
          and re.search(r"^  P_parent n=11 a=0\.0(125|25): .* -> PASS$", b34t, re.M) is not None
          and re.search(r"^  s10\* ", b34t, re.M) is not None and re.search(r"^  s6 ", b34t, re.M) is not None
          and dec(b34t).startswith("P_parent is taken (O9): both are admitted")
          and "(ε 0.05 bits/byte per old area, 11 parent(s))" in b34t
          and "W (NEW-20) at the parent s3, FAB_SLOTS 6144" in b34t and "W (NEW-20) at the parent s10*, FAB_SLOTS 6144" in b34t,
          b34t[-1800:])
    for tag34, kw34, why34 in (("card_out", {"card": "NVIDIA H200, 143771"},
                                "they differ in card (NVIDIA H200 143771 MiB here, NVIDIA H100 PCIe 81559 MiB there)"),
                               ("commit_out", {"commit": "def5678"}, "they differ in commit (def5678 here, abc1234 there)"),
                               ("overlap_out", {"seeds": range(6, 10)}, "parent seed(s) 6 are in both"),
                               ("shape_out", {"sw": 4000}, "they differ in shape (")):
        _, b34r = se_topup(tag34, **kw34)
        check(f"F34 a top-up whose {tag34.split('_')[0]} differs from the first fleet's is not pooled: POOLING REFUSED, "
              f"saying why, and nothing is decided",
              f"POOLING REFUSED with {o34}: {why34}" in b34r
              and dec(b34r).startswith("NOTHING IS DECIDED: this top-up's parents pool with its first fleet's only where "
                                       "commit, card, torch and shape match, and " + why34)
              and "-- this fleet alone, deciding nothing" in b34r, b34r[-900:])
    # A LAUNCH AND ITS TOP-UP, END TO END, with the stand-in: the first fleet trains its parents (a parents stage at 7
    # seeds), reads both candidates UNRESOLVED (+-0.06 by parity) and prints the top-up's command, which run as printed
    # trains parents 7-10 and pools: both admitted, and x5 (-0.1 on P_parent) takes P_parent.
    o34l = os.path.join(TMP, "f34l", "gpu_session_out")
    e34 = dict(PATH=env10["PATH"], EXP="session", DEVICE="cpu", WINDOWS=20, SEEDS="0 1 2 3 4 5 6", PAR=8,
               SMOKE_WINDOWS=5, PARENT_ARM="k10", PROBE_EVERY=5, SESSION_WINDOWS=8, STUB_PARENT=1, STUB_GAIN_PP="0.1",
               STUB_FINAL_BYTES="1000", OUT=o34l)
    p34l = subprocess.run(["bash", SCRIPT], cwd=ROOT, capture_output=True, text=True, timeout=900,
                          env=clean_env(STUB_SPREAD="0.06", **e34))
    b34l = "\n".join(block_of(p34l.stdout) or [])
    cmd34 = (re.search(r"^  top-up: (.*) bash \S+/tools/gpu_launch\.sh --go$", b34l, re.M) or [None, ""])[1]
    kv34 = {k: v.strip("'") for k, v in re.findall(r"(\w+)=('[^']*'|\S+)", cmd34)}
    oa34 = os.path.realpath(o34l)
    check("F34 a stand-in launch with a parents stage reads both UNRESOLVED at 7 parents and prints the top-up's command "
          "with the fleet's knobs -- parents 7-10, FILL=0, WINDOWS, PARENT_ARM, PROBE_EVERY, SESSION_WINDOWS, DEVICE and "
          "PAR, its own OUT and POOL_WITH this one; the anchor holds item for item in every session",
          p34l.returncode == 0 and dec(b34l).startswith("UNRESOLVED at 7 parent(s): P and P_parent are UNRESOLVED")
          and kv34 == {"EXP": "session", "SEEDS": "7 8 9 10", "FILL": "0", "WINDOWS": "20", "PARENT_ARM": "k10",
                       "PROBE_EVERY": "5", "SESSION_WINDOWS": "8", "DEVICE": "cpu", "PAR": "8",
                       "OUT": oa34[:-4] + "_topup_out", "POOL_WITH": oa34}
          and "equal in 22 of 22 session(s)" in b34l,
          f"rc {p34l.returncode}; {cmd34!r}; {b34l[-1500:]}")
    o34u = kv34.get("OUT", os.path.join(TMP, "f34l", "none"))
    l34 = subprocess.run(["bash", LAUNCHER], cwd=TMP, capture_output=True, text=True, timeout=300,
                         env=clean_env(PATH=env10["PATH"], FETCH=0, CKPT_MB=50,
                                       **dict(kv34, OUT=os.path.join(TMP, "f34m", "o_out"))))
    rl34 = next((ln[len("    ready: "):] for ln in l34.stdout.splitlines() if ln.startswith("    ready: ")), "")
    p34u = subprocess.run(["bash", SCRIPT], cwd=ROOT, capture_output=True, text=True, timeout=900,
                          env=clean_env(PATH=env10["PATH"], SMOKE_WINDOWS=5, STUB_PARENT=1, STUB_GAIN_PP="0.1",
                                        STUB_FINAL_BYTES="1000", **kv34))
    b34u = "\n".join(block_of(p34u.stdout) or [])
    check("F34 ... the launcher passes the printed command (the top-up of the first fleet, a parents stage for 7-10); the "
          "top-up, launched with it, trains parents 7-10, records its first fleet and reads the 11 parents together: "
          "both admitted, and P_parent is taken on the new area",
          f"PASS POOL_WITH: this fleet is the top-up of {oa34}" in l34.stdout
          and "PASS no PARENTS: a parents stage trains k10 at seeds 7 8 9 10 first" in l34.stdout
          and f"POOL_WITH={oa34}" in rl34 and "SEEDS='7 8 9 10'" in rl34 and "PARENT_ARM=k10" in rl34
          and p34u.returncode == 0
          and f"=== pool: with {oa34} (seeds 0 1 2 3 4 5 6)" in txt(os.path.join(o34u, "SUMMARY.txt"))
          and txt(os.path.join(o34u, "parents", "FINALS.sha256")).count("  ckpt/k10.s") == 8
          and f"POOLED with the first fleet {oa34}" in b34u
          and re.search(r"^  P_parent n=11 a=0\.0(125|25): .* -> PASS$", b34u, re.M) is not None
          and dec(b34u).startswith("P_parent is taken (O9): both are admitted, and x5's R reading on P_parent - on P has "
                                   "its one-sided upper bound -0.1000 below 0"),
          l34.stdout[-600:] + b34u[-1500:])

    # ---- F35: EXP=heldout HELDOUT_SOURCE=real's launch (2026-10-02, register §8 6.3b) --------------------------------
    # E2's shape (b) on real text. The stand-in records what each run saw; PIN_RETOK=10 makes S k10 and S_replay
    # k10_replay; EXTRA tries to move four pinned levers and sets one that is not pinned.
    o35 = os.path.join(TMP, "f35", "gpu_heldout_real_out")
    b35 = os.path.join(TMP, "f35_book.jsonl")
    k35 = dict(EXP="heldout", HELDOUT_SOURCE="real", DEVICE="cpu", WINDOWS=20, SEEDS="0 1", PAR=3, SMOKE_WINDOWS=5,
               PIN_RETOK=10, PROBE_EVERY=5, EXTRA="DATA_SOURCE=synthetic EVAL_HOLDOUT_WINDOWS=32 DATA_DRAW=uniform "
                                                 "TOK_MINT_NOVEL=0.5 TOK_GROW_EVERY=20", OUT=o35)
    p35 = subprocess.run(["bash", SCRIPT], cwd=ROOT, capture_output=True, text=True, timeout=300,
                         env=clean_env(PATH=env10["PATH"], STUB_BOOK=b35, STUB_FINAL_BYTES="50000000", **k35))
    r35 = [json.loads(l) for l in open(b35)] if os.path.exists(b35) else []
    s35 = txt(os.path.join(o35, "SUMMARY.txt"))
    sm35 = [r for r in r35 if "/smoke/" in r["argv"][r["argv"].index("--loss-curve") + 1]]
    fl35 = [r for r in r35 if r not in sm35]
    arm35 = {"k0": ("0", "0", "planned", None), "k0_rerun": ("0", "0", "planned", None),
             "k10": ("10", "0", "planned", None), "k10_replay": ("10", "0", "replay", "0.27")}
    check("F35 EXP=heldout HELDOUT_SOURCE=real launches k0, S (SHIP_ARM, k<PIN_RETOK> by default) and S_replay at every "
          "seed and k0_rerun -- the smoke's 3 and the fleet's 7 runs, rc 0 -- every run on real text, pinned after EXTRA "
          "(which moves no pinned lever and keeps an unpinned one), its arm's settings after the pins: 'replay' at 0.27 "
          "on S_replay alone; DATA_SYNTH_HOLDOUT not pinned; the stream 3,780,000 bytes, written as the number",
          p35.returncode == 0 and len(sm35) == 3 and sorted(r["tag"] for r in fl35)
          == ["k0.s0", "k0.s1", "k0_rerun.s0", "k10.s0", "k10.s1", "k10_replay.s0", "k10_replay.s1"]
          and all(r["env"]["DATA_SOURCE"] == "real" and r["pins"]["DATA_SYNTH_HOLDOUT"] is None
                  and r["pins"]["EVAL_RETENTION_EVERY"] == "5" and r["env"]["EVAL_HOLDOUT_WINDOWS"] == "256"
                  and r["env"]["EVAL_RETENTION_N"] == "24" and r["env"]["EVAL_GENERATE"] == "0"
                  and r["env"]["TOK_GROW_EVERY"] == "20" and r["env"]["DATA_STREAM_BYTES"] == "3780000" for r in r35)
          and all((r["retok"], r["env"]["TOK_MINT_NOVEL"], r["env"]["DATA_DRAW"], r["env"]["DATA_REPLAY_SHARE"])
                  == arm35[r["tag"].rsplit(".s", 1)[0]] for r in r35),
          f"rc {p35.returncode}; {[(r['tag'], r['retok'], r['env']) for r in r35][:4]}; {p35.stderr[-300:]!r}")
    check("F35 ... each writes its probe series, flush bytes and the book's series beside its curve, and saves its final "
          "alone, the smoke's too",
          all("--probe-series" in r["argv"] and "--flush-bytes" in r["argv"] and "--trust-series" in r["argv"] for r in r35)
          and all(os.path.exists(os.path.join(o35, "curves", r["tag"] + ".trust.json")) for r in fl35)
          and all(r["ckpt"] == {"CKPT_DIR": os.path.join(o35, "ckpt", r["tag"]), "CKPT_EVERY": "0"} for r in fl35),
          str([(r["tag"], r["argv"][-6:]) for r in r35][:2]))
    check("F35 ... SUMMARY records the source, S and S_replay, the arms and the pins -- DATA_SOURCE=real in "
          "DATA_SYNTH_HOLDOUT's place -- and every command it prints for the owner carries HELDOUT_SOURCE=real",
          "=== source: real text (HELDOUT_SOURCE=real, §8 6.3b): DATA_SOURCE=real, one epoch of 3780000 bytes; S k10, "
          "S_replay k10_replay ('replay' at 0.27)" in s35
          and "=== plan: EXP=heldout; arms k0 k10 k10_replay, plus k0_rerun at seed 0; window cap 60;" in s35
          and "=== pins: DATA_SOURCE=real pinned, DATA_DRAW=planned pinned, EVAL_RETENTION_EVERY=5 pinned, "
              "EVAL_HOLDOUT_WINDOWS=256 pinned, EVAL_RETENTION_N=24 pinned, EVAL_GENERATE=0 pinned, TOK_MINT_NOVEL=0 pinned"
              in s35
          and f"one look: EXP=heldout HELDOUT_SOURCE=real OUT={o35} bash {SCRIPT} --status" in s35,
          [l for l in s35.splitlines() if l.startswith(("=== source", "=== plan", "=== pins", "=== pid"))])
    # S = k<c>_mn (6.3a shipped TOK_MINT_NOVEL 1.0): S_replay is k<c>_mn at 'replay'.
    b35m = os.path.join(TMP, "f35m_book.jsonl")
    p35m = subprocess.run(["bash", SCRIPT], cwd=ROOT, capture_output=True, text=True, timeout=300,
                          env=clean_env(PATH=env10["PATH"], STUB_BOOK=b35m, SHIP_ARM="k10_mn", KEEP_CKPT=0,
                                        **dict(k35, SEEDS="0", OUT=os.path.join(TMP, "f35m", "gpu_heldout_real_out"))))
    r35m = [json.loads(l) for l in open(b35m)] if os.path.exists(b35m) else []
    check("F35 SHIP_ARM=k<c>_mn runs S at TOK_MINT_NOVEL 1.0 and S_replay at 1.0 and 'replay'",
          p35m.returncode == 0 and {(r["tag"].rsplit(".s", 1)[0], r["retok"], r["env"]["TOK_MINT_NOVEL"],
                                     r["env"]["DATA_DRAW"]) for r in r35m}
          == {("k0", "0", "0", "planned"), ("k0_rerun", "0", "0", "planned"), ("k10_mn", "10", "1.0", "planned"),
              ("k10_mn_replay", "10", "1.0", "replay")}, str(sorted({(r["tag"], r["env"]["DATA_DRAW"]) for r in r35m})))
    # THE DEFAULTS ON REAL TEXT, written as numbers: 17,476 windows (k0's epoch at seed 0), 3,780,000 bytes, the probe
    # at 650; its own OUT.
    o35d = os.path.join(TMP, "f35d")
    os.makedirs(o35d, exist_ok=True)
    p35d = subprocess.run(["bash", SCRIPT], cwd=o35d, capture_output=True, text=True, timeout=300,
                          env=clean_env(PATH=env10["PATH"], EXP="heldout", HELDOUT_SOURCE="real", DEVICE="cpu", SEEDS="0",
                                        PAR=4, SMOKE_WINDOWS=5, KEEP_CKPT=0, OUT=os.path.join(o35d, "gpu_heldout_real_out")))
    s35d = txt(os.path.join(o35d, "gpu_heldout_real_out", "SUMMARY.txt"))
    check("F35 its defaults are written as numbers: 17,476 windows a run (k0's epoch at seed 0), DATA_STREAM_BYTES "
          "3,780,000, the window cap 3 x 17,476, the probe at 650; S is k1000",
          p35d.returncode == 0 and "=== 17476 windows per run, DATA_STREAM_BYTES=3780000, seeds: 0," in s35d
          and "arms k0 k1000 k1000_replay, plus k0_rerun at seed 0; window cap 52428;" in s35d
          and "EVAL_RETENTION_EVERY=650 pinned" in s35d, [l for l in s35d.splitlines() if l.startswith("=== ")][:12])
    # THE REFUSALS, before anything is written: an unknown source, real text at another EXP, SHIP_ARM where the source is
    # not real (a real-text command that lost HELDOUT_SOURCE would launch the synthetic fleet into test 4's OUT), an S
    # that is no act arm, and a real-text top-up of a synthetic first fleet.
    ref35 = {"source": gw(EXP="heldout", HELDOUT_SOURCE="rael", OUT=os.path.join(TMP, "f35r", "a")),
             "exp": gw(EXP="session", HELDOUT_SOURCE="real", OUT=os.path.join(TMP, "f35r", "b")),
             "ship": gw(EXP="heldout", SHIP_ARM="k1000_mn", OUT=os.path.join(TMP, "f35r", "c")),
             "arm": gw(EXP="heldout", HELDOUT_SOURCE="real", SHIP_ARM="k1000x", OUT=os.path.join(TMP, "f35r", "d")),
             "pool": gw(EXP="heldout", HELDOUT_SOURCE="real", SEEDS="7", POOL_WITH=o29, OUT=os.path.join(TMP, "f35r", "e"))}
    want35 = {"source": "HELDOUT_SOURCE='rael' is not a source EXP=heldout reads",
              "exp": "HELDOUT_SOURCE=real is EXP=heldout's (§8 6.3b, E2's shape (b) on real text), not EXP=session's",
              "ship": "SHIP_ARM='k1000_mn' names the real-text fleet's S, and HELDOUT_SOURCE is not real",
              "arm": "SHIP_ARM='k1000x' is not one of 6.3a's act arms",
              "pool": "holds a synthetic EXP=heldout fleet, and this top-up is real-text (HELDOUT_SOURCE)"}
    check("F35 refused by name, writing nothing: an unknown HELDOUT_SOURCE, real text at another EXP, SHIP_ARM without "
          "HELDOUT_SOURCE=real, an S that is no act arm, and a real-text top-up naming a synthetic first fleet",
          all(p_.returncode == 2 and want35[k] in p_.stdout for k, p_ in ref35.items())
          and not os.path.exists(os.path.join(TMP, "f35r")),
          str({k: p_.stdout[-200:] for k, p_ in ref35.items() if want35[k] not in p_.stdout}))
    # THE LAUNCHER: the source's check, its own OUT and log, the same disk budget as EXP=heldout's three arms, the ready
    # line carrying HELDOUT_SOURCE and SHIP_ARM; and its refusals.
    l35 = subprocess.run(["bash", LAUNCHER], cwd=TMP, capture_output=True, text=True, timeout=300,
                         env=clean_env(PATH=env10["PATH"], EXP="heldout", HELDOUT_SOURCE="real", SHIP_ARM="k1000_mn",
                                       DEVICE="cpu", SEEDS="0 1", CKPT_MB=50, FETCH=0))
    rl35 = next((ln[len("    ready: "):] for ln in l35.stdout.splitlines() if ln.startswith("    ready: ")), "")
    l35b = [subprocess.run(["bash", LAUNCHER], cwd=TMP, capture_output=True, text=True, timeout=300,
                           env=clean_env(PATH=env10["PATH"], DEVICE="cpu", FETCH=0, OUT=os.path.join(TMP, "f35l", "x"),
                                         **e_)).stdout
            for e_ in ({"EXP": "heldout", "SHIP_ARM": "k1000_mn"}, {"EXP": "heldout", "HELDOUT_SOURCE": "real",
                                                                    "SHIP_ARM": "k1000x"},
                       {"EXP": "heldout", "HELDOUT_SOURCE": "real", "POOL_WITH": o29})]
    check("F35 the launcher: HELDOUT_SOURCE=real PASSes with S and its own OUT (gpu_heldout_real_out) and log, budgets "
          "three arms a seed and the rerun as EXP=heldout does (2.1 GB at 50 MB), and its ready line carries "
          "HELDOUT_SOURCE and SHIP_ARM; SHIP_ARM without the real source, an S that is no act arm and a real-text top-up "
          "of a synthetic fleet FAIL",
          "PASS HELDOUT_SOURCE=real: real text, S = k1000_mn and its 'replay' twin, OUT gpu_heldout_real_out" in l35.stdout
          and "LOG=heldout_real_fleet.log" in l35.stdout
          and "the kept checkpoints may need 2.1 GB at 2 seed(s)" in l35.stdout
          and "HELDOUT_SOURCE=real" in rl35 and "SHIP_ARM=k1000_mn" in rl35 and "EXP=heldout" in rl35
          and "FAIL SHIP_ARM='k1000_mn' names the real-text fleet's S" in l35b[0]
          and "FAIL SHIP_ARM='k1000x' is not one of test 4's act arms" in l35b[1]
          and "holds an EXP=heldout fleet on other text than this top-up's (HELDOUT_SOURCE)" in l35b[2],
          l35.stdout[-800:] + "".join(x[-300:] for x in l35b))
    # THE DASHBOARD finds a real-text launch from before the lock (no GW_FLEET_OUT) in its own OUT: a gpu_world.sh
    # stood in, at EXP=heldout HELDOUT_SOURCE=real, is a process of gpu_heldout_real_out and not of gpu_heldout_out.
    d35 = os.path.join(TMP, "f35dash")
    write(os.path.join(d35, "gpu_world.sh"), "sleep 30\n")
    sp35 = subprocess.Popen(["bash", os.path.join(d35, "gpu_world.sh")], cwd=d35,
                            env=clean_env(EXP="heldout", HELDOUT_SOURCE="real"))
    try:
        time.sleep(0.5)
        sc35 = [subprocess.run(["bash", DASH, "--scan", "own", os.path.join(d35, o_)], capture_output=True, text=True,
                               timeout=60).stdout for o_ in ("gpu_heldout_real_out", "gpu_heldout_out")]
    finally:
        sp35.kill()
        sp35.wait()
    check("F35 the dashboard reads a real-text launch's OUT as gpu_heldout_real_out, where its own scan finds it",
          f"{sp35.pid}\tshell" in sc35[0] and f"{sp35.pid}\t" not in sc35[1], str(sc35))

    # ---- F36: EXP=heldout HELDOUT_SOURCE=real's reading, rule and block (2026-10-02, register §8 6.3b) ----------------
    # Fleets written by hand, each number chosen, on F30's plan: each area's R reading 2.0 + 0.1 x its index + 0.001 x
    # the seed, with `harm` added to num on S and S_replay (+- `spread` by the seed's parity), `rep` added to every area
    # of S_replay alone (+- `rspread`), or `rep_num` to its num; the in-run all-area report 2.5, and on S_replay 2.5 +
    # `tgap` (+- `tspread`) from the stream's middle on; the book's seconds `trust` over 20 s of loop time.
    def hr_summary(out, *, seeds, s_="k1000", commit="abc1234", card="NVIDIA H100 PCIe, 81559",
                   torch_="torch 2.7.0, CUDA 12.8", pool=None, windows=400, par=24, extra="", source=True):
        n_, mib = card.split(", ")
        L = [f"=== gpu_world.sh  2026-10-03T12:00:00Z  commit {commit}",
             f"=== code: this fleet runs its own copy, {out}/code (gpu_world.sh, run.py, src/, tools/fleet_dash.sh; "
             f"sha256 0123456789abcdef), taken from commit {commit} at launch: a git pull during the fleet reaches none of it",
             "    index, name, memory.total [MiB], memory.used [MiB]", f"    0, {n_}, {mib} MiB, 1 MiB",
             "=== 26 CPU core(s), 1 GPU(s), device=cuda", f"=== {torch_}",
             f"=== {windows} windows per run, DATA_STREAM_BYTES={windows * 189}, seeds: {seeds}, EXTRA='{extra}'",
             f"=== plan: EXP=heldout; arms k0 {s_} {s_}_replay, plus k0_rerun at seed 0; window cap {3 * windows}; "
             f"CAL_WINDOWS 600; LM_CTX {CTX}"]
        if source:
            L.append(f"=== source: real text (HELDOUT_SOURCE=real, §8 6.3b): DATA_SOURCE=real, one epoch of {windows * 189} "
                     f"bytes; S {s_}, S_replay {s_}_replay ('replay' at 0.27); every run writes the book's series "
                     f"(run.py --trust-series)")
        L += [f"=== kept checkpoints: ON, one final checkpoint per run under {out}/ckpt, and beside it the retention "
              f"probe's best saves (ckpt.pt.best and .best.prev): up to 3 checkpoint files per run, all counted in the "
              f"disk check",
              "=== pins: DATA_SOURCE=real pinned, DATA_DRAW=planned pinned, EVAL_RETENTION_EVERY=650 pinned, "
              "EVAL_HOLDOUT_WINDOWS=256 pinned, EVAL_RETENTION_N=24 pinned, EVAL_GENERATE=0 pinned, TOK_MINT_NOVEL=0 pinned"]
        if pool:
            L.append(f"=== pool: with {pool} (seeds 0 1 2 3 4 5 6): this fleet is its top-up, and its analysis reads "
                     f"the two fleets' seeds together where commit, card, torch and shape match")
        L += [f"=== {len(seeds.split()) * 3 + 1} run(s), {par} at a time",
              "=== ETA by waves: about 18 min (1080 s): 22 run(s) over 24 slot(s), 1 wave(s), each run its windows "
              "at 19.20 windows/s plus 15 s of startup",
              "---- 2. fleet started 12:10:00Z", "---- fleet finished in 19 min (1140 s)"]
        write(os.path.join(out, "SUMMARY.txt"), "\n".join(L) + "\n")

    def hr_run(out, name, seed, *, harm=0.0, rep=0.0, rep_num=0.0, tgap=0.0, trust=0.2, windows=400, nobnd=False):
        tag = f"{name}.s{seed}"

        def val(k):
            return 2.0 + 0.1 * k + 0.001 * seed + (harm if HO_AR[k] == "num" else 0.0) + rep \
                + (rep_num if HO_AR[k] == "num" else 0.0)

        def row(step, kind, closure, nar, rep_=None, off=0.0):
            ars = {HO_AR[k]: {"control": val(k) + off, "report": val(k) + off, "seen_by_parent": False}
                   for k in range(nar)}
            m_ = sum(x["report"] for x in ars.values()) / nar if rep_ is None else rep_
            return {"step": step, "kind": kind, "closure": closure, "control": m_, "report": m_,
                    "windows": 24 * nar, "nonfinite": 0, "paired_sd": None, "areas": ars}
        rows = []
        for q in range(4):
            for st, kind in ((q * windows // 4 + 1, "phase"), (q * windows // 4 + windows // 8 + 1, "cadence")):
                rows.append(row(st, kind, "memory-off", min(4, q + 2), rep_=2.5 + (tgap if st > windows // 2 else 0.0)))
        if not nobnd:
            rows += [row(windows, "boundary", "memory-off", 4), row(windows, "boundary", "memory-on", 4, off=-0.01)]
        cc = {"loop.bytes_scored": 189 * windows, "loop.acts": 0 if name.startswith("k0") else 3,
              "eval.holdout.seconds": "3.000000", "eval.holdout.windows": sum(r_["windows"] for r_ in rows),
              "data.trust.wall_s": f"{trust:.6f}", "data.trust.passes": 110, "data.trust.claims": 5000,
              "data.trust.conflicted_claims": 40, "data.trust.sources": 37, "fab.n_live": 2000 + seed}
        # The plan's gates as run.py's R stage prints them: under 'replay' data.exposure_max's value says why its
        # split is exact and holds a quote, so it prints in double quotes, its reason after ' -- '.
        gates = ["       gate:data.phase_entered                      ('fired', '4 vs 4')",
                 "       gate:data.exposure_skew                      ('fired', '6.8082 vs 3.0')",
                 "       gate:data.splice_window                      ('fired', '5.897 vs 8.0')",
                 "       gate:data.exposure_max                       " + (
                     "('armed-but-zero', \"0.0264 vs 2.0 -- DATA_DRAW=replay: this split is EXACT, as under 'planned'\")"
                     if name.endswith("_replay") else "('armed-but-zero', '0.029 vs 2.0')")]
        write(os.path.join(out, "logs", tag + ".log"), "\n".join(
            ["=== device=cuda amp=off tf32=(True, True) torch_seed=1",
             f"=== {windows} windows, {windows} flushes, {windows} optimizer steps, 1 epoch(s) in 20.0s (20.0 w/s)",
             "=== R STAGE -- the did-it-fire surfaces:"] + [f"       {k:<44} {v}" for k, v in cc.items()] + gates) + "\n")
        write(os.path.join(out, "curves", tag + ".json"), json.dumps([2.0 * LN2 * 189 / CTX] * windows))
        write(os.path.join(out, "curves", tag + ".bytes.json"), json.dumps([189] * windows))
        write(os.path.join(out, "curves", tag + ".probe.json"), json.dumps(rows))
        with open(os.path.join(out, "logs", "_done.txt"), "a") as fh:
            fh.write(f"{tag} rc=0 secs=25\n")

    def hr_fleet(out, seeds, *, s_="k1000", harm=0.0, spread=0.0, rep=0.0, rspread=0.0, rep_num=0.0, tgap=0.0,
                 tspread=0.0, trust=0.2, nobnd=(), **kw):
        hr_summary(out, seeds=" ".join(map(str, seeds)), s_=s_, **kw)
        for s_d in seeds:
            par_ = 1 if s_d % 2 == 0 else -1
            h_ = harm + par_ * spread
            for nm, kw_ in (("k0", {}), (s_, {"harm": h_}),
                            (f"{s_}_replay", {"harm": h_, "rep": rep + par_ * rspread, "rep_num": rep_num,
                                              "tgap": tgap + par_ * tspread})):
                hr_run(out, nm, s_d, trust=trust, nobnd=f"{nm}.s{s_d}" in nobnd, **kw_)
        hr_run(out, "k0_rerun", 0, trust=trust)

    def hr_read(tag, seeds, pool_env=None, **kw):
        o_ = os.path.join(TMP, "f36", tag, "gpu_heldout_real_out")
        hr_fleet(o_, seeds, **kw)
        p_ = gw("--analyze", EXP="heldout", OUT=o_, **({"POOL_WITH": pool_env} if pool_env else {}))
        return o_, p_, txt(os.path.join(o_, "ANALYSIS.txt")), "\n".join(block_of(p_.stdout) or [])

    def dec14(text):
        return (re.search(r"^DECISION \(O14, real text\): (.*)$", text, re.M) or [None, ""])[1]

    def dec16(text):
        return (re.search(r"^DECISION \(O16, the draw\): (.*)$", text, re.M) or [None, ""])[1]

    zero36 = " ".join(f"{a} +0.0000 [+0.0000,+0.0000]" for a in HO_AR)
    o36, p36, a36, b36 = hr_read("pass", range(7))
    check("F36 a harmless real-text fleet is read by its own reader: S PASSes against k0 on every area (the eps rule at "
          "one arm, a = 0.025, the upper bound at t(0.975)) and its label ends on real text; 'replay' is not CONFIRMed "
          "(no gap) and passes to E1; the book's 1% of wall is within E3's 2%; the block, within 80 lines and equal to "
          "PASTE_BACK.txt, is labelled real text and carries each seed's k0, S - k0 and S_replay - S",
          p36.returncode == 0 and "commit abc1234  launched 2026-10-03T12:00:00Z  real text" in b36
          and "synthetic source" not in b36 and f"  k1000 n=7 a=0.025: {zero36} -> PASS" in b36
          and "per area (4), S - k0 paired over seeds, each look (7 seeds; a top-up's pooled 11) at 0.025: mean [lower "
              "at t(1 - a/4), one-sided upper at t(0.975)]" in b36
          and dec14(b36).startswith("k1000 PASSes against k0 on every area's held-out reading on real text: its "
                                    "B-provisional label ends here, and whole where 6.3a's synthetic reading PASSed too")
          and f"  end state n=7: {zero36} -> PASS" in b36
          and "  time-integrated gap n=7: mean +0.0000, one-sided upper +0.0000: not below 0" in b36
          and dec16(b36) == "'replay' is not CONFIRMed (the gap's upper bound +0.0000 not below 0): 'planned' stays (D8), "
                            "and the draw passes to E1 (§8 6.4) (7 seed(s))"
          and "E3 (04-6.3): the book's seconds over the loop's, mean 1.00% over 21 run(s) (largest 1.00%), at PAR 24, "
              "against 2%: within it, DATA_TRUST_EVERY (its default, 160) stays" in b36
          and 0 < len(block_of(p36.stdout)) <= 80
          and block_of(p36.stdout) == txt(os.path.join(o36, "PASTE_BACK.txt")).splitlines()
          and "per seed: k0, then k1000 - k0, then k1000_replay - k1000" in b36
          and re.search(r"^  s6 +2\.0060 +2\.1060 +2\.2060 +2\.3060 \| +\+0\.0000 .* \| +\+0\.0000", b36, re.M) is not None,
          b36[-2500:])
    check("F36 ... and beside it, deciding nothing: S - k0's time-integrated gap, the end-state SD per area of both "
          "differences and the gap's, memory-on - memory-off, the book at R, the plan's gates as flags, readings per "
          "phase against the pinned 650, n_live and the probe's seconds, and the ETA by waves against the wall",
          "time-integrated report gap from 20% of the stream, k1000 - k0: mean +0.0000 sd 0.0000 n=7" in b36
          and "end-state SD per area: k1000 - k0 eng 0.0000 py 0.0000 num 0.0000 c 0.0000 | k1000_replay - k1000 eng "
              "0.0000 py 0.0000 num 0.0000 c 0.0000 | time-integrated k1000_replay - k1000 sd 0.0000" in b36
          and "k1000_replay eng -0.0100 py -0.0100 num -0.0100 c -0.0100" in b36
          and "the book at R, mean over the runs: passes 110, claims 5000, conflicted claims 40, sources 37" in b36
          and "the plan's gates (flags, as pre-registered): data.exposure_skew fired 6.8082 vs 3.0; data.exposure_max "
              "armed-but-zero 0.0264 vs 2.0 / armed-but-zero 0.029 vs 2.0; data.splice_window fired 5.897 vs 8.0" in b36
          and "against EVAL_RETENTION_EVERY 650 (§8 0.4)" in b36 and "n_live at the end (NEW-20): k0 2003" in b36
          and "ETA by waves 1080 s, took 1140 s: 1.06x" in b36
          and [l for l in b36.splitlines() if "prequential" in l]
          == ["  prequential per phase (O14's 2.1 endpoint), k1000 - k0 n=7: "
              + " ".join(f"p{k} +0.0000 [+0.0000,+0.0000]" for k in range(1, 5)) + " -> PASS"],
          [l for l in b36.splitlines() if l.startswith("  ")][-12:])
    # THE PER-PHASE PREQUENTIAL READING IS O14's ALONE (2026-10-03, review of 2bb0dac): under 'replay' phases 2-4 train on
    # another mix, so S_replay's training bits/byte, here 2.2-2.22 there against S's 2.0, differ by the text. Every
    # held-out reading of S_replay is S's.
    o36q = os.path.join(TMP, "f36", "preq", "gpu_heldout_real_out")
    hr_fleet(o36q, range(7))
    for s_ in range(7):
        p_ = os.path.join(o36q, "curves", f"k1000_replay.s{s_}.json")
        cu_ = json.load(open(p_))
        write(p_, json.dumps([x if i < 100 else (2.2 + 0.01 * (s_ % 3)) * LN2 * 189 / CTX for i, x in enumerate(cu_)]))
    b36q = "\n".join(block_of(gw("--analyze", EXP="heldout", OUT=o36q).stdout) or [])
    check("F36 the per-phase prequential reading is O14's, S - k0 alone, as the register lists it: S_replay - S's is not "
          "read, its phases 2-4 trained on another text mix (here 0.2 bits/byte above S's there, every held-out reading "
          "S's)",
          [l for l in b36q.splitlines() if "prequential" in l]
          == ["  prequential per phase (O14's 2.1 endpoint), k1000 - k0 n=7: "
              + " ".join(f"p{k} +0.0000 [+0.0000,+0.0000]" for k in range(1, 5)) + " -> PASS"]
          and f"  end state n=7: {zero36} -> PASS" in b36q, [l for l in b36q.splitlines() if "prequential" in l])
    # O16 CONFIRMS: every area 0.02 lower under 'replay' (within eps), the time-integrated gap -0.05 x 199 / 320 =
    # -0.0311 +- 0.01 x 199 / 320 by parity: its upper bound below 0 at t(0.975, 6).
    _, _, _, b36c = hr_read("confirm", range(7), rep=-0.02, tgap=-0.05, tspread=0.01)
    g36 = [(-0.05 + (0.01 if s_ % 2 == 0 else -0.01)) * 199 / 320 for s_ in range(7)]
    m36 = sum(g36) / 7
    u36 = m36 + 2.4469118511449697 * math.sqrt(sum((x - m36) ** 2 for x in g36) / 6 / 7)
    check(f"F36 'replay' CONFIRMs where every area's upper bound is within eps (-0.0200 each) and the time-integrated "
          f"gap's ({u36:+.4f}, its mean {m36:+.4f}) is below 0: it goes to the owner, 'planned' holding until they answer",
          f"  time-integrated gap n=7: mean {m36:+.4f}, one-sided upper {u36:+.4f}: below 0, significantly better" in b36c
          and " ".join(f"{a} -0.0200 [-0.0200,-0.0200]" for a in HO_AR) + " -> PASS" in b36c
          and dec16(b36c) == f"'replay' at 0.27 is CONFIRMed against 'planned' on real text -- every area's upper bound "
                             f"within ε, the time-integrated gap's {u36:+.4f} below 0: it goes to the owner (D8), and "
                             f"'planned' holds until they answer (7 seed(s))", dec16(b36c))
    # O16 READS ITS OWN SEEDS (2026-10-03, review of 2bb0dac): the same fleet with k0.s3's boundary rows gone. O16 pairs
    # S_replay - S where both hold R's reading -- all 7, to the same answer -- and O14 S - k0 at the 6 where k0 does too.
    _, _, _, b36k0 = hr_read("k0miss", range(7), rep=-0.02, tgap=-0.05, tspread=0.01, nobnd=("k0.s3",))
    check("F36 a k0 with no boundary row leaves O14's pairs alone: O16, which does not involve k0, pairs its 7 seeds -- the "
          "same CONFIRM -- and the per-seed row shows S_replay - S beside no k0 reading",
          f"  time-integrated gap n=7: mean {m36:+.4f}, one-sided upper {u36:+.4f}: below 0, significantly better" in b36k0
          and "  end state n=7: " + " ".join(f"{a} -0.0200 [-0.0200,-0.0200]" for a in HO_AR) + " -> PASS" in b36k0
          and dec16(b36k0).endswith("'planned' holds until they answer (7 seed(s))")
          and f"  k1000 n=6 a=0.025: {zero36} -> PASS" in b36k0
          and "left out of O14's pairs (no endpoint): k0.s3" in b36k0 and "left out of O16's" not in b36k0
          and re.search(r"^  s3 +(- +){4}\| +(- +){4}\|( +-0\.0200){4}$", b36k0, re.M) is not None, b36k0[-1800:])
    _, _, _, b36h = hr_read("harm", range(7), rep_num=0.2, tgap=-0.05)
    check("F36 'replay' that harms an area past eps is not CONFIRMed, whatever its gap: num's +0.2000, its lower bound "
          "past eps, FAILs the area condition, and the draw passes to E1",
          "num +0.2000 [+0.2000,+0.2000]" in b36h
          and dec16(b36h).startswith("'replay' is not CONFIRMed (num's upper bound +0.2000 above ε): 'planned' stays (D8)"),
          dec16(b36h))
    _, _, _, b36f = hr_read("fail", range(7), harm=0.2)
    check("F36 S FAILs against k0 on real text: its label stays, 1000 stays on meanwhile (never 0), and O14's next remedy "
          "arms run on real text -- TOK_MINT_NOVEL 1.0 first where S is k1000; no ESCALATE",
          dec14(b36f).startswith("k1000 FAILs against k0 on real text: its B-provisional label stays, 1000 stays on "
                                 "meanwhile (0 is never shipped by the rule) and O14's next remedy arms run on real text: "
                                 "TOK_MINT_NOVEL 1.0 (k1000_mn), then LM_ANCHOR_USES raised, OPT_HORIZON_REVISE=0, and "
                                 "OPT_BORN_CLOCK once §8 4.2 builds it") and "ESCALATE" not in b36f, dec14(b36f))
    _, _, _, b36m = hr_read("failmn", range(7), s_="k1000_mn", harm=0.2)
    check("F36 S at k1000_mn (6.3a shipped TOK_MINT_NOVEL 1.0) FAILs: the next remedy arms start after it",
          dec14(b36m).startswith("k1000_mn FAILs against k0 on real text") and "OPT_HORIZON_REVISE=0" in dec14(b36m)
          and "TOK_MINT_NOVEL 1.0 (" not in dec14(b36m), dec14(b36m))
    o36u, _, _, b36u = hr_read("unres", range(7), harm=0.05, spread=0.1, rep=-0.02, tgap=-0.05, tspread=0.2)
    oa36 = os.path.realpath(o36u)
    check("F36 UNRESOLVED below the cap prints the top-up's command -- HELDOUT_SOURCE=real, SHIP_ARM, the next 4 seeds, "
          "FILL=0, the fleet's shape where it is not the real-text default (WINDOWS, EPOCH_BYTES), PAR, its own OUT and "
          "POOL_WITH this one -- and O16, not CONFIRMed at this look, waits for the pooled second",
          dec14(b36u).startswith("UNRESOLVED at 7 seed(s): k1000 is UNRESOLVED against k0")
          and f"  top-up: EXP=heldout HELDOUT_SOURCE=real SHIP_ARM=k1000 SEEDS='7 8 9 10' FILL=0 WINDOWS=400 "
              f"EPOCH_BYTES=75600 PAR=24 OUT={oa36[:-4]}_topup_out POOL_WITH={oa36} bash {ROOT}/tools/gpu_launch.sh --go"
              in b36u
          and dec16(b36u).startswith("not CONFIRMed at 7 seed(s) (the gap's upper bound ")
          and dec16(b36u).endswith("not below 0): read again over the top-up's pooled seeds, the second look"),
          b36u[-1500:])
    _, _, _, b36x = hr_read("cap", range(11), harm=0.05, spread=0.1)
    check("F36 the same at the cap of 11 is reported unresolved, never escalated, and S's label stays; no top-up",
          dec14(b36x).startswith("UNRESOLVED at the cap: k1000 is UNRESOLVED against k0 at the seed cap; reported so, "
                                 "never escalated, and its B-provisional label stays") and "top-up:" not in b36x, dec14(b36x))
    _, _, _, b36e = hr_read("e3", range(7), trust=1.0, extra="DATA_TRUST_EVERY=320")
    check("F36 E3: the book at 5% of the loop's seconds is above 2%, so DATA_TRUST_EVERY lengthens, named at the fleet's "
          "value",
          "mean 5.00% over 21 run(s) (largest 5.00%), at PAR 24, against 2%: ABOVE it, so DATA_TRUST_EVERY 320 lengthens "
          "(E3's rule)" in b36e, [l for l in b36e.splitlines() if l.startswith("E3")])
    # 13 seeds, S_replay.s3 with no boundary row: O14 reads its first 11 pairs, seeds 0-10; O16 its own first 11, 0-2 and
    # 4-11. Each rule names what it left out and its seeds past the cap; the per-seed rows show each difference its rule reads.
    _, _, a36m, b36g = hr_read("missing", range(13), nobnd=("k1000_replay.s3",))
    check("F36 a run with no boundary row is named and left out of its rule's pairs, each rule reads its own first 11 "
          "seeds where both its runs hold R's reading, and seeds past the cap of 11 are not read, by rule",
          "left out of O16's pairs (no endpoint): k1000_replay.s3" in b36g and "left out of O14's" not in b36g
          and "seeds past the cap of 11, not read by O14: 11 12" in b36g
          and "seeds past the cap of 11, not read by O16: 12" in b36g
          and f"  k1000 n=11 a=0.025: {zero36} -> PASS" in b36g and f"  end state n=11: {zero36} -> PASS" in b36g
          and re.search(r"^  s3 +2\.0030 .*\| +(\+0\.0000 +){4}\|( +-){4}$", b36g, re.M) is not None
          and re.search(r"^  s11 +2\.0110 .*\| +(- +){4}\|( +\+0\.0000){4}$", b36g, re.M) is not None
          and re.search(r"^  s12 ", b36g, re.M) is None
          and re.search(r"^  k1000_replay +s3 .*NO BOUNDARY ROW", a36m, re.M) is not None, b36g[-1500:])
    # THE FINALS: S's alone, 6.1's real-text parents, with the pack line; a synthetic fleet is still read by 6.3a's reader.
    o36k = os.path.join(TMP, "f36", "finals", "gpu_heldout_real_out")
    hr_fleet(o36k, range(2))
    for t_ in ("k0.s0", "k1000.s0", "k1000.s1", "k1000_replay.s0"):
        write(os.path.join(o36k, "ckpt", t_, "ckpt.pt"), "x" * 10)
        write(os.path.join(o36k, "ckpt", t_ + ".dyntok.json"), "{}")
    p36k = gw("--analyze", EXP="heldout", OUT=o36k)
    b36k = "\n".join(block_of(p36k.stdout) or [])
    check("F36 the finals: FINALS.sha256 lists S's final checkpoints and vocabularies alone (4 files: 6.1's real-text "
          "parents) and the block's pack: line packs them; the archive is gpu_heldout_real_<date>.tgz",
          sorted(l[66:] for l in txt(os.path.join(o36k, "FINALS.sha256")).splitlines())
          == ["ckpt/k1000.s0.dyntok.json", "ckpt/k1000.s0/ckpt.pt", "ckpt/k1000.s1.dyntok.json", "ckpt/k1000.s1/ckpt.pt"]
          and "FINALS: 4 file(s), the k1000 runs' final checkpoints and vocabularies" in b36k
          and "§8 6.1's real-text parents, which the pack: line below packs to upload" in b36k
          and re.search(r"^  pack: tar -cf \S+/gpu_heldout_real_2026-10-03_finals\.tar -C ", b36k, re.M) is not None
          and "archive: gpu_heldout_real_2026-10-03.tgz beside" in b36k, b36k[-700:])

    # ---- F37: a real-text top-up pooled with its first fleet (2026-10-02, register §8 6.3b) -----------------------------
    # The first fleet reads S UNRESOLVED at 7 seeds (num +0.4 at even seeds, 0 at odd) and O16 not CONFIRMed (its gap
    # -0.0311 +- 0.0311, its upper bound +0.0041); its top-up's seeds 7-10 read num +0.3 and the gap -0.0311 at each: the
    # pooled 11, the second look, FAIL S and CONFIRM 'replay' (the gap's upper bound -0.0109).
    o37 = os.path.join(TMP, "f37", "gpu_heldout_real_out")
    hr_fleet(o37, range(7), harm=0.2, spread=0.2, rep=-0.02, tgap=-0.05, tspread=0.05)
    p37a = gw("--analyze", EXP="heldout", OUT=o37)
    b37a = "\n".join(block_of(p37a.stdout) or [])
    g37 = [(-0.05 + (0.05 if s_ % 2 == 0 else -0.05)) * 199 / 320 for s_ in range(7)]
    m37 = sum(g37) / 7
    u37 = m37 + 2.4469118511449697 * math.sqrt(sum((x - m37) ** 2 for x in g37) / 6 / 7)

    def hr_topup(tag, seeds=range(7, 11), pool=o37, **kw):
        o_ = os.path.join(TMP, "f37", tag)
        hr_fleet(o_, seeds, harm=0.3, rep=-0.02, tgap=-0.05, pool=pool, **kw)
        p_ = gw("--analyze", EXP="heldout", OUT=o_)
        return o_, "\n".join(block_of(p_.stdout) or [])
    o37t, b37t = hr_topup("gpu_heldout_real_topup_out")
    check("F37 the first fleet alone is UNRESOLVED and asks for the top-up, O16 waiting for it; the top-up, recorded as "
          "its pool, reads the 11 seeds together -- its own marked * -- and S FAILs on real text and 'replay' CONFIRMs at "
          "the second look, the first look's reading beside it",
          dec14(b37a).startswith("UNRESOLVED at 7 seed(s): k1000 is UNRESOLVED") and "top-up:" in b37a
          and dec16(b37a) == f"not CONFIRMed at 7 seed(s) (the gap's upper bound {u37:+.4f} not below 0): read again over "
                             f"the top-up's pooled seeds, the second look"
          and f"POOLED with the first fleet {o37}: its seeds and this top-up's (marked *) are read together" in b37t
          and re.search(r"^  k1000 n=11 a=0\.025: .* -> FAIL$", b37t, re.M) is not None
          and re.search(r"^  s10\* ", b37t, re.M) is not None
          and dec14(b37t).startswith("k1000 FAILs against k0 on real text")
          and f"  the first look, the first fleet's n=7: not CONFIRMed (the gap's upper bound {u37:+.4f} not below 0)" in b37t
          and dec16(b37t).startswith("'replay' at 0.27 is CONFIRMed against 'planned' on real text at the second look -- ")
          and "FINALS: none" in b37t, b37a[-600:] + b37t[-1500:])
    o37n = os.path.join(TMP, "f37", "gpu_heldout_real_neither_out")
    hr_fleet(o37n, range(7, 11), harm=0.3, rep=-0.02, tgap=0.10, pool=o37)
    b37n = "\n".join(block_of(gw("--analyze", EXP="heldout", OUT=o37n).stdout) or [])
    check("F37 a top-up that CONFIRMs 'replay' at neither look: 'planned' stays and the draw passes to E1, said of both",
          dec16(b37n).startswith("'replay' is not CONFIRMed at either look (over the pooled seeds, the gap's upper bound +")
          and dec16(b37n).endswith("not below 0): 'planned' stays (D8), and the draw passes to E1 (§8 6.4) (11 seed(s))")
          and f"  the first look, the first fleet's n=7: not CONFIRMed (the gap's upper bound {u37:+.4f} not below 0)" in b37n,
          b37n[-1200:])
    # A CONFIRM AT THE FIRST LOOK STANDS (2026-10-03, review of 2bb0dac): F36's CONFIRMing draw beside an S UNRESOLVED at 7
    # seeds (num +0.15 at even seeds, -0.05 at odd); the top-up's seeds 7-10 read the gap +0.10 x 199 / 320, so the
    # pooled 11 alone would not CONFIRM. power.py's 4.10% over the two looks counts a CONFIRM at either.
    o37c = os.path.join(TMP, "f37c", "gpu_heldout_real_out")
    hr_fleet(o37c, range(7), harm=0.05, spread=0.1, rep=-0.02, tgap=-0.05, tspread=0.01)
    b37c = "\n".join(block_of(gw("--analyze", EXP="heldout", OUT=o37c).stdout) or [])
    o37ct = os.path.join(TMP, "f37c", "gpu_heldout_real_topup_out")
    hr_fleet(o37ct, range(7, 11), harm=0.05, spread=0.1, rep=-0.02, tgap=0.10, pool=o37c)
    b37ct = "\n".join(block_of(gw("--analyze", EXP="heldout", OUT=o37ct).stdout) or [])
    g37c = g36 + [0.10 * 199 / 320] * 4
    m37c = sum(g37c) / 11
    u37c = m37c + 2.2281388519649385 * math.sqrt(sum((x - m37c) ** 2 for x in g37c) / 10 / 11)
    check(f"F37 'replay' CONFIRMed at the first look, its O14 UNRESOLVED: the top-up's block carries that CONFIRM, which "
          f"stands, and its pooled 11 ({u37c:+.4f}, not below 0) decide nothing",
          dec14(b37c).startswith("UNRESOLVED at 7 seed(s): k1000 is UNRESOLVED") and "top-up:" in b37c
          and dec16(b37c).startswith(f"'replay' at 0.27 is CONFIRMed against 'planned' on real text -- every area's upper "
                                     f"bound within ε, the time-integrated gap's {u36:+.4f} below 0")
          and dec14(b37ct).startswith("UNRESOLVED at the cap")
          and f"  the first look, the first fleet's n=7: CONFIRMed (every area's upper bound within ε, the gap's {u36:+.4f} "
              f"below 0)" in b37ct
          and f"  time-integrated gap n=11: mean {m37c:+.4f}, one-sided upper {u37c:+.4f}: not below 0" in b37ct
          and dec16(b37ct) == "'replay' at 0.27 is CONFIRMed against 'planned' on real text at the first look, the first "
                              "fleet's 7 seed(s): a CONFIRM stands at either look, so it went to the owner with that "
                              "fleet's block (D8), and 'planned' holds until they answer; the pooled 11 above decide nothing",
          dec16(b37c) + " || " + b37ct[-1500:])
    # O14's CAP COUNTS ITS PAIRS, AS THE TOP-UP'S COMMAND DOES (2026-10-03): S.s3 with no boundary row, O14 UNRESOLVED at
    # 6 pairs, so the command asks for seeds 7-11. Pooled, O14 reads 11 pairs, seed 11 in place of seed 3; it read seeds
    # 0-10 where k0 held R's reading, 10 pairs, and left seed 11 past the cap.
    o37p = os.path.join(TMP, "f37p", "gpu_heldout_real_out")
    hr_fleet(o37p, range(7), harm=0.05, spread=0.1, nobnd=("k1000.s3",))
    b37p = "\n".join(block_of(gw("--analyze", EXP="heldout", OUT=o37p).stdout) or [])
    o37pt = os.path.join(TMP, "f37p", "gpu_heldout_real_topup_out")
    hr_fleet(o37pt, range(7, 12), harm=0.05, spread=0.1, pool=o37p)
    b37pt = "\n".join(block_of(gw("--analyze", EXP="heldout", OUT=o37pt).stdout) or [])
    check("F37 a first fleet whose S lost one boundary row reads O14 at 6 pairs and asks for seeds 7-11; pooled, O14 and "
          "O16 each read 11 pairs, seed 11 among them, nothing past the cap, and both name the run they left out",
          dec14(b37p).startswith("UNRESOLVED at 6 seed(s): k1000 is UNRESOLVED") and "SEEDS='7 8 9 10 11'" in b37p
          and re.search(r"^  k1000 n=11 a=0\.025: ", b37pt, re.M) is not None
          and dec14(b37pt).endswith("(ε 0.05 bits/byte, 11 seed(s))") and "  end state n=11: " in b37pt
          and "past the cap" not in b37pt and re.search(r"^  s11\* ", b37pt, re.M) is not None
          and "left out of O14's pairs (no endpoint): k1000.s3" in b37pt
          and "left out of O16's pairs (no endpoint): k1000.s3" in b37pt, b37p[-900:] + b37pt[-1500:])
    for tag37, kw37, why37 in (("card_out", {"card": "NVIDIA H200, 143771"},
                                "they differ in card (NVIDIA H200 143771 MiB here, NVIDIA H100 PCIe 81559 MiB there)"),
                               ("commit_out", {"commit": "def5678"}, "they differ in commit (def5678 here, abc1234 there)"),
                               ("overlap_out", {"seeds": range(6, 10)}, "seed(s) 6 are in both")):
        _, b37r = hr_topup(tag37, **kw37)
        check(f"F37 a real-text top-up whose {tag37.split('_')[0]} differs from the first fleet's is not pooled: POOLING "
              f"REFUSED, NOTHING IS DECIDED", f"POOLING REFUSED with {o37}: {why37}" in b37r
              and dec14(b37r).startswith("NOTHING IS DECIDED") and dec16(b37r).startswith("NOTHING IS DECIDED"),
              b37r[-800:])
    o37s = os.path.join(TMP, "f37", "synth_first", "gpu_heldout_out")
    ho_fleet(o37s, range(7), harm=0.2, spread=0.2)
    _, b37s = hr_topup("source_out", pool=o37s)
    check("F37 a real-text top-up of a synthetic first fleet is not pooled: they differ in shape and source",
          "they differ in" in b37s and "source (real text here, synthetic there)" in b37s
          and dec14(b37s).startswith("NOTHING IS DECIDED"), b37s[-800:])
    # END TO END with the stand-in: a real-text fleet at 7 seeds whose S reads UNRESOLVED prints the top-up's command,
    # which the launcher passes and which, run as printed, pools with it. As F31's, the stand-in plants num at +0.2 +-
    # 0.2 on k10 in the first fleet (UNRESOLVED at 7) and +0.3 in the top-up (FAIL over the pooled 11, its lower bound
    # about +0.10), and 'replay' 0.02 lower on every area of k10_replay, every reading (CONFIRMed).
    o37l = os.path.join(TMP, "f37l", "gpu_heldout_real_out")
    e37 = dict(PATH=env10["PATH"], EXP="heldout", HELDOUT_SOURCE="real", DEVICE="cpu", WINDOWS=20, SEEDS="0 1 2 3 4 5 6",
               PAR=8, SMOKE_WINDOWS=5, PIN_RETOK=10, PROBE_EVERY=5, KEEP_CKPT=0, OUT=o37l)
    p37l = subprocess.run(["bash", SCRIPT], cwd=ROOT, capture_output=True, text=True, timeout=900,
                          env=clean_env(STUB_HARM="0.2", STUB_SPREAD="0.2", STUB_REPLAY="-0.02", **e37))
    b37l = "\n".join(block_of(p37l.stdout) or [])
    cmd37 = (re.search(r"^  top-up: (.*) bash \S+/tools/gpu_launch\.sh --go$", b37l, re.M) or [None, ""])[1]
    kv37 = {k: v.strip("'") for k, v in re.findall(r"(\w+)=('[^']*'|\S+)", cmd37)}
    oa37 = os.path.realpath(o37l)
    check("F37 a stand-in real-text launch reads S UNRESOLVED at 7 seeds and prints the top-up's command with the fleet's "
          "knobs -- HELDOUT_SOURCE=real, SHIP_ARM, seeds 7-10, FILL=0, WINDOWS, PROBE_EVERY, DEVICE and PAR, its own OUT "
          "and POOL_WITH this one (the stream is the default, so no EPOCH_BYTES)",
          p37l.returncode == 0 and dec14(b37l).startswith("UNRESOLVED at 7 seed(s): k10 is UNRESOLVED")
          and kv37 == {"EXP": "heldout", "HELDOUT_SOURCE": "real", "SHIP_ARM": "k10", "SEEDS": "7 8 9 10", "FILL": "0",
                       "WINDOWS": "20", "PROBE_EVERY": "5", "DEVICE": "cpu", "PAR": "8",
                       "OUT": oa37[:-4] + "_topup_out", "POOL_WITH": oa37}, f"rc {p37l.returncode}; {cmd37!r}; {b37l[-1200:]}")
    l37 = subprocess.run(["bash", LAUNCHER], cwd=TMP, capture_output=True, text=True, timeout=300,
                         env=clean_env(PATH=env10["PATH"], FETCH=0, CKPT_MB=50, **dict(kv37, OUT=os.path.join(TMP, "f37m", "o_out"))))
    p37u = subprocess.run(["bash", SCRIPT], cwd=ROOT, capture_output=True, text=True, timeout=900,
                          env=clean_env(PATH=env10["PATH"], SMOKE_WINDOWS=5, KEEP_CKPT=0, STUB_HARM="0.3",
                                        STUB_REPLAY="-0.02", **kv37))
    b37u = "\n".join(block_of(p37u.stdout) or [])
    check("F37 ... the launcher passes the printed command (the top-up of the first, real-text fleet), and run as printed "
          "the top-up records its first fleet and reads the 11 seeds together: S FAILs on real text, 'replay' CONFIRMs",
          f"PASS POOL_WITH: this fleet is the top-up of {oa37}" in l37.stdout and "HELDOUT_SOURCE=real" in l37.stdout
          and p37u.returncode == 0 and f"POOLED with the first fleet {oa37}" in b37u
          and re.search(r"^  k10 n=11 a=0\.025: .* -> FAIL$", b37u, re.M) is not None
          and dec14(b37u).startswith("k10 FAILs against k0 on real text")
          and dec16(b37u).startswith("'replay' at 0.27 is CONFIRMed against 'planned' on real text"),
          l37.stdout[-500:] + b37u[-1500:])

finally:
    # NOTHING THESE CHECKS STARTED OUTLIVES THEM: a process carrying a GW_FLEET_OUT under TMP (a fleet, its
    # runs, its heartbeat) or naming TMP on its command line (a stand-in run, a dashboard) is killed.
    for _d in os.listdir("/proc"):
        if not _d.isdigit() or int(_d) == os.getpid():
            continue
        try:
            _env = open(f"/proc/{_d}/environ", "rb").read().split(b"\0")
            _cmd = open(f"/proc/{_d}/cmdline", "rb").read()
        except OSError:
            continue
        if any(x.startswith(b"GW_FLEET_OUT=" + TMP.encode()) for x in _env) or TMP.encode() in _cmd:
            try:
                os.kill(int(_d), 9)
            except OSError:
                pass
    shutil.rmtree(TMP, ignore_errors=True)

print(f"\n=== {len(FAILS)} failing ===")
sys.exit(1 if FAILS else 0)
