#!/bin/bash
# ==================================================================================================
# THE OWNER'S GPU FLEETS, EACH RUN AS A FLEET THAT FILLS THE CARD: Q-WORLD-10's WORLD EXPERIMENT,
# 03b S0b's RETOK SHIP RULE, AND THE WHOLE-EPOCH WORLD RE-RUN'S SIZING
# ==================================================================================================
# EXP CHOOSES THE EXPERIMENT, AND ANY OTHER VALUE IS REFUSED BY NAME (Proposal 05 §8 1.5): a
# misspelled EXP used to fall through to the WORLD fleet, which then ran under the label meant for
# another one.
#   EXP=world        the default: Q-WORLD-10's four arms, the 2026-09-24 fleet (below)
#   EXP=retok        03b S0b's ship rule for TOK_RETOK_EVERY, with kept checkpoints (§8 2.1)
#   EXP=world_epoch  the whole-epoch, phase-traversing WORLD re-run: sized, and refused until SR0
#
# WHAT EXP=world DECIDED (2026-09-24: within noise, WORLD_FEEDBACK now ships False). Whether WORLD_FEEDBACK stays True (the forecast wired into LM.encode, world_proj
# born zero) and, if it helps, whether the help is WORLD MODELLING or just added capacity. The
# protocol is the judge's from Q-WORLD-10 in docs/04_CONTRACT.md:
#
#   fb_off     WORLD_FEEDBACK=0                          the control; bit-identical to the tree before
#                                                        the forecast had a call site
#   fb_on      the defaults                              wired, world_proj born zero
#   skip       WORLD_PREDICT_W=0 WORLD_COLLAPSE_W=0      the same forecast network in the forward,
#                                                        trained ONLY by the LM loss: the CAPACITY
#                                                        control
#   world_off  WORLD_ENABLED=0                           prices the whole subsystem
#
# plus fb_off seed 0 run TWICE, which measures this card's run-to-run floor (cuDNN's GRU is not
# guaranteed bit-exact, so "identical seed" is not "identical run" on a GPU until measured).
# Metric: per seed, the mean over the LAST HALF of the per-flush loss curve of (arm - fb_off), then
# mean +- SE across seeds and how many seeds come out negative. RUN_EPOCHS=1, so the last half is
# prequential loss on text the model has not trained on yet.
#
# WHY A FLEET AND NOT ONE BIG RUN. One run of this model is LAUNCH-BOUND: sweep_gpu.sh measured the
# best single arm at 30.8% utilisation of an H100 with 1.8 GiB of its 79 in use. A bigger batch
# would fill it but changes the experiment (fewer optimizer steps per window, which sweep_gpu.sh
# showed trades directly against learning). What fills the card WITHOUT changing the experiment is
# running the independent seeds and arms CONCURRENTLY: every process keeps its own geometry and
# step count, and the card interleaves their kernels. So this script:
#   1. smokes every arm for SMOKE_WINDOWS on the card (fails fast, checks each arm's tripwires,
#      measures one process's memory and speed),
#   2. sizes the parallelism from GPU memory, GPU count and CPU cores (each process needs one core
#      to launch its kernels),
#   3. starts CUDA MPS when it can (kernels from different processes then run SIMULTANEOUSLY
#      instead of time-slicing; the numbers each process computes are unchanged),
#   4. FILLS spare slots with extra seeds -- more seeds is the one use of spare card that makes the
#      decision sharper rather than just faster,
#   5. samples nvidia-smi through the whole fleet and says whether the card was actually full,
#   6. analyses the curves, prints the decision, prints the block to paste back and packs $OUT.
#
#     bash gpu_world.sh                                   # 20,000 windows, seeds 0-4, auto-filled
#     WINDOWS=5000 bash gpu_world.sh                      # a quicker first look
#     EXTRA="LM_WIDTH=512 LM_LAYERS=2" bash gpu_world.sh  # your standard geometry, applied to EVERY arm
#     ARCH_ALSO=transformer bash gpu_world.sh             # + fb_off/fb_on at LM_ARCH=transformer
#     LONG=100000 bash gpu_world.sh                       # + one fb_on/fb_off pair (seed 0) that long
#     PAR=12 MPS=0 FILL=0 bash gpu_world.sh               # manual parallelism, no MPS, no extra seeds
#     KEEP_CKPT=1 bash gpu_world.sh                       # + one final checkpoint per run (below)
#     bash gpu_world.sh --status                          # RUNNING / STALLED / FINISHED / STOPPED / DEAD,
#                                                         # where it is and time left; changes nothing
#     bash gpu_world.sh --stop                            # stop the running fleet; it writes its block
#     bash gpu_world.sh --analyze                         # re-analyse what is on disk, paste back, pack
#     bash tools/fleet_dash.sh                            # the dashboard, in a second terminal
#     EXP=retok bash tools/gpu_launch.sh --go             # the checked launcher: the owner's one command
#     cat gpu_world_out/SUMMARY.txt
#
# A FLEET SAYS IT IS ALIVE, AND ONLY ONE RUNS PER OUT (2026-09-27: the retok fleet was stopped by hand
# because the card read idle and the log said nothing, and a second paste of the launch line had
# started a second fleet whose launch moved the first one's OUT from under it):
#   * ONE FLEET PER OUT. A launch takes an flock on <OUT>.lock, beside OUT (inside it, the lock would
#     move with OUT), held by the fleet and every process it starts for as long as any of them runs. A
#     launch that finds it held -- or finds a fleet the lock cannot see: a gpu_world.sh launched before
#     it, or a run.py still writing under OUT -- refuses, moves nothing, and says which fleet is running,
#     where it is, why the card may read idle, and how to watch or stop it. At DEVICE=cuda a fleet under
#     ANOTHER OUT on the same machine is refused too (two fleets on one card measure each other; set
#     ALLOW_CONCURRENT=1 to mean it). A dead fleet's OUT is moved aside as before, and the MPS daemon it
#     left behind (a SIGKILL runs no trap) is told to quit.
#   * $OUT/STATE, rewritten at every step: the shell's pid and its start time, the phase and step and
#     when they began, and at the end how it ended. --status and tools/fleet_dash.sh read their verdict
#     off it: RUNNING, STALLED (no run output for 5 minutes), FINISHED, STOPPED with the reason, or
#     DEAD -- the pid gone with no end recorded, "died without a reason".
#   * A HEARTBEAT: every HB_EVERY seconds (30; 0 turns it off) one line in this log -- the stage, its
#     runs starting on the CPU / training / done / failed, windows, windows/s, the ETA, the GPU's
#     utilisation and memory, the load -- also kept in $OUT/HEARTBEAT and $OUT/heartbeat.log. Each
#     smoke, calibration and fleet step says when its runs START, and that they build on the CPU first
#     (python and torch, corpus, tokenizer, stream, model: the startup the smoke measures and prints)
#     so the card reads idle then. The watcher that prints the heartbeat also notices the shell vanish
#     without a block (SIGKILL, the OOM killer): it says so here, stops the runs, writes the block.
#   * A STOP WRITES ITS BLOCK. INT, TERM and HUP stop the runs, write "STOPPED by SIG<x> during <where>"
#     here and in the block, pack the archive, quit MPS, and exit 128+n; any other exit that wrote no
#     block (a set -u slip, a failed command) writes one naming the command. Under nohup HUP stays
#     ignored -- bash cannot trap a signal ignored at entry -- which is what keeps a closed terminal
#     harmless. A Ctrl-C reaches the WHOLE process group, not just this shell: each run's run_job ignores
#     INT and HUP, so the stop TERMs the run and its run_job books it, and a run orphaned all the same is
#     found by the GW_FLEET_OUT it carries (2026-09-27 review: a Ctrl-C killed every run_job, and its
#     run.py, which ignores INT, trained on as an orphan holding the lock while the fleet said STOPPED).
#     A dead output pipe (`| tee log`, its reader gone with the terminal) stops nothing: SIGPIPE is ignored
#     and SUMMARY is written first. In the analysis nothing runs any more, so a stop there waits the
#     seconds the analysis, the block and the archive take, and the fleet ends FINISHED; an analysis that
#     fails ends STOPPED, with its block saying so, never FINISHED.
#   * PULL SAFETY: the fleet runs its OWN COPY. A launch copies this script, run.py, src/ and
#     tools/fleet_dash.sh into $OUT/code and re-executes the copy, which works in the checkout as
#     before; every run is `python3 $OUT/code/run.py` on $OUT/code/src. A `git pull` during the fleet --
#     or an editor, cp or scp rewriting this file in place, which a running bash would read from the
#     middle -- reaches none of it. SUMMARY records the commit and a sha256 of the copy. --status,
#     --stop and --analyze are readers and run from the checkout.
# The runs' own logs are unbuffered (PYTHONUNBUFFERED=1; that changes no number), so each shows its
# lines as they happen: run.py's first line when it starts, '=== composed' with its startup when it
# begins training, and a '[N windows]' line every 100 windows.
#
# A LAUNCH INTO AN OUT THAT HOLDS A PREVIOUS FLEET MOVES THAT FLEET ASIDE, WHOLE, beside it as
# <OUT>.<its launch stamp> (2026-09-27, build 1.5's review; the reason is at the move, below). Nothing
# is deleted: OUT=<that name> bash gpu_world.sh --analyze still reads it, and its checkpoints stay on
# the disk until you delete it.
#
# CHECKPOINTS ARE OFF BY DEFAULT AND ON AT EXP=retok (KEEP_CKPT; Proposal 05 §8 1.5, register note
# retok fleet (1)). Saving is the most expensive operation in the loop and nothing EXP=world measures
# needs a resume, so there CKPT_DIR stays unset unless KEEP_CKPT=1 asks for one final checkpoint per
# run. At EXP=retok every run gets CKPT_DIR=$OUT/ckpt/<arm>.s<seed>: the act arms save once, at the
# end (CKPT_EVERY 0); k0, k0_nuis and k0_rerun save every KEEP_EVERY windows (default: the gcd of the
# act cadences, 1000); and k0's saves are HARD-LINKED ASIDE as $OUT/ckpt/keep/k0.s<seed>.w<step>,
# with the vocabulary beside each as k0.s<seed>.w<step>.dyntok.json, because CKPT's ring keeps only
# ckpt.pt and ckpt.pt.prev (src/ckpt/api.py::save). A periodic save lands on the window an act of that
# cadence fires at (j x K + 1) and leaves the run's losses bit-identical (tests/test_continuation.py
# S11), so arm - k0 pairs a saving control with arms that save only at the end. The kept copies are
# the spike test's maturity-matched control (register note retok fleet (4)) and parents for
# continuations:
#     CKPT_RESUME=gpu_retok_out/ckpt/keep/k0.s0.w3001 CKPT_DIR=<a NEW directory> OMP_NUM_THREADS=1 \
#         RUN_SEED=0 RUN_DEVICE=cuda DATA_STREAM_BYTES=3780000 TOK_RETOK_EVERY=0 <the fleet's EXTRA> python3 run.py
# WITH THE RUN'S OWN SEED, DEVICE AND STREAM (2026-09-27, build 1.5's review): the script sets them on
# every run and EXTRA does not carry them, and a resume without them is refused -- the segmentation
# rebuilt from the checkpoint's log disagrees with the parent's epoch. DATA_STREAM_BYTES is WINDOWS x
# 189 at EXP=retok (3780000 at 20,000 windows); the block's "resume one" line prints them filled in.
# RESUME INTO A NEW CKPT_DIR, NEVER THE KEPT ONE: a save there rotates the kept copy away, and the
# read-only bit the index sets on kept files stops no rename. Nothing is written under runs/, and a
# SIGUSR1 save lands in the run's own CKPT_DIR (at EXP=world by default there is none, so it saves
# nothing). A hard link costs no disk until the ring drops its own name for the file; the fleet's
# checkpoint disk is estimated from the smoke's largest checkpoint before FILL adds seeds.
# DEVICE=cpu runs the same pipeline without the GPU parts; it exists so the script itself can be
# tested on a machine without a card, and its numbers mean nothing about the GPU.
#
# EXP=retok RUNS 03b S0b's SHIP-RULE MEASUREMENT INSTEAD (2026-09-26): which TOK_RETOK_EVERY ships,
# now that the mid-epoch act performs a retok. Arms k0 (0, the control: no act), k3000 (the shipped
# value), k1000, and k0_nuis (0 again, with SIG_WARMUP=801 -- a small real perturbation neither the act
# nor TOK reads, so |k0 - k0_nuis| per seed is the paired noise floor). Metric: PREQUENTIAL bits per
# byte, sum(per-flush loss x LM_CTX) / ln 2 / bytes -- every window at RUN_EPOCHS=1 is scored before
# its update, and bits per byte does not move with the segmentation, which is exactly what the arms
# change -- read PER PHASE: the stream's N equal byte ranges of DATA_STREAM_BYTES (data_plan's bounds;
# N off each log's data.phase_entered gate), each flush placed by its run's cumulative per-flush bytes
# (run.py --flush-bytes; absent, the whole run is read as one phase and the analysis says so).
# THE RULE IS O14's, READ BY THE eps RULE (Proposal 05 O2, O14; 2026-09-27). Per cadence arm c and
# phase p, the paired differences d(s) = c - k0 over the seeds with both runs give one-sided t bounds,
# mean -+ t x sd / sqrt(n). c FAILS if some phase's LOWER bound exceeds EPS (default 0.05 bits/byte),
# the t taken at 1 - a/N (Bonferroni over the phases) with Holm across the cadence arms (the arm with
# the strongest evidence of harm at a = 0.05/2, the other at 0.05); c PASSES if every phase's one-sided
# 95% UPPER bound is at most EPS; otherwise, and always at n < 2 seeds, it is UNRESOLVED. THE CHOICE:
# 3000 is the incumbent (RETOK_INCUMBENT, the interim default). 1000 replaces it only if 1000 does not
# FAIL and (3000 FAILs, or the one-sided 95% upper bound of the whole-run paired 1000 - 3000 is below
# 0); otherwise 3000 stays, UNRESOLVED readings included. 0 is never shipped by the rule: if every
# cadence FAILs, the DECISION is ESCALATE (the act stays ON at 3000 until the owner answers; the
# remedy arms run next). M = max over seeds |k0 - k0_nuis| and the per-arm means are printed beside the
# rule and decide nothing. RETOK_INCUMBENT exists for operation checks at a shorter shape (a CPU fleet
# whose cadences are 40 and 20); the fleet's rule is O14's, at 3000.
# RETOK_ARMS names the act cadences (arm k<c> each; default "3000 1000", today's arms in today's
# order), and COOLDOWN_ARM=<v> adds k<fastest>_cd<v> at FAB_COOLDOWN=<v>, reported beside the rule and
# never a ship candidate. CALIBRATION RUNS 600 WINDOWS HERE (CAL_WINDOWS; 150 at EXP=world), past FAB's
# first manage pass at window 501: the 2026-09-24 fleet ran about 15x slower than its 150-window
# calibration said, because the per-pass cost starts after it (LOW-GPU-WORLD-ETA). Beside the rule,
# never in it, the analysis reports RATES (windows/s and bytes/s per arm, the act's per-byte cost
# against k0, the aggregate over the fleet's wall, and the ETA against that wall: the post-fix
# throughput re-baseline), SECONDARIES (acts, FAB growth, the blackout share, MEM's re-cut share,
# bytes per token per act, mint waits, the act's share of loop time, bits/byte per phase; §8 1.3's
# counters where the tree has them and one "absent" line where it does not) with a BLACKOUT ALARM
# above 20% of windows (C13) that orders COOLDOWN_ARM=100, and the KEPT CHECKPOINTS with their
# coverage of the act windows. THE BLACKOUT IS SPLIT WHERE THE POOL FILLS (O14; 2026-09-27): the
# 2026-09-24 archive showed FAB's pool reaching FAB_SLOTS in 20 of 21 runs, after which growth is
# held by the ceiling whatever the acts do. fab.blackout_windows is reported before and after the
# first progress line ('[N windows] ... n_live=K') with n_live >= FAB_SLOTS (the log's gate text, else
# EXTRA, else 4096; never filled, it is all before), n_live at the end is printed per arm, and C13's
# alarm reads only the part before. The counter is cumulative and the log has no per-window series, so
# the split is an ESTIMATE built from the act windows and FAB_COOLDOWN (each act blacks out up to a
# cooldown from its window, a later act restarting it), and says so. A LOG WITHOUT THE COUNTER is read
# against an UPPER BOUND on the part before, built from the acts before the fill: the windows their
# cooldowns cover before it, over the windows before it, with a stamp no act line places charged a
# whole cooldown there, and every notification x cooldown only where no act window is known (the
# split's review, 2026-09-27: every notification was charged there, so acts after the fill read as
# blackout before it and a pool full at window 101 alarmed on acts at 1001-1901). The verdict is labelled
# B-provisional (note retok fleet (3)), and
# pre-Levels when this tree lacks DOM_LEVELS or the fleet turns it off (C12). IF THIS FLEET RUNS AFTER
# SR0, 04-Q5's pin rule applies: its margin pairs with pre-SR0 runs, so SR0's build adds
# DATA_SYNTH_HOLDOUT=0 EVAL_RETENTION_EVERY=0 DATA_TRUST=off to every retok run here.
#     EXP=retok bash gpu_world.sh                         # 20,000 windows, seeds 0-2, auto-filled
#     EXP=retok RETOK_ARMS="3000 1000 500" bash gpu_world.sh   # another cadence set
#     EXP=retok COOLDOWN_ARM=100 bash gpu_world.sh        # + k1000_cd100 (the blackout alarm's arm)
#     EXP=retok KEEP_CKPT=0 bash gpu_world.sh             # no checkpoints: the spike test loses its control
#     EXP=retok bash gpu_world.sh --analyze
#     EXP=retok EPS=0.02 bash gpu_world.sh --analyze      # the same runs read against another eps
#
# EXP=world_epoch IS THE WORLD RE-RUN'S SHAPE, SIZED AND GUARDED BUT NOT RUN (register note WORLD 3-4,
# §8 6.5). The 2026-09-24 fleet read phase 1 of a 20 MB stream and never saw an area arrive or fade.
# This shape reads ONE WHOLE EPOCH of a WINDOWS x 189-byte stream (EPOCH_BYTES), as EXP=retok does, with
# the window cap out of reach and "RAN OUT OF STREAM" replaced by a window-cap flag, so every arm
# crosses all four phases. It pins TOK_RETOK_EVERY (PIN_RETOK, 3000; S0b-ship: every dependent
# experiment pins and labels it) and DATA_DRAW=planned (note WORLD 3). Its pre-registered rule reads
# SR0's retention probe with DATA_SYNTH_HOLDOUT ON, which this tree does not declare, so it prints its
# sizing and the pre-registration and exits 2 having written nothing, until GO_WORLD_EPOCH=1 (SR0's
# build adds those settings to its pins and lifts the guard; before that, only an operation check).
#     EXP=world_epoch bash gpu_world.sh                   # the sizing and the pre-registration; exit 2
#     EXP=world_epoch GO_WORLD_EPOCH=1 bash gpu_world.sh  # after SR0
#
# EVERY FLEET ENDS IN A BLOCK TO PASTE BACK AND AN ARCHIVE TO KEEP. The GPU box has a checkout and no
# push token (results/gpu_world_2026-09-24/ANALYSIS.txt was transcribed from its terminal by hand), so
# the end of every fleet, every --analyze and every early stop prints ONE block, from
# "==== PASTE THIS BACK ====" to "==== END ====", at most 80 lines, and writes it to
# $OUT/PASTE_BACK.txt: the commit, the card, the shape, the failed runs, and the result (at EXP=retok
# the per-seed bits/byte, each cadence's per-phase bounds and verdict, eps, the choice and why, M
# reported, rates, secondaries with the blackout split, and kept checkpoints). Paste it
# into the chat. $OUT is then packed beside itself as <name>_<launch date>.tgz -- logs, curves, smoke,
# calibration, SUMMARY, ANALYSIS, the block, KEPT.txt; never a checkpoint -- which the owner keeps
# (the 2026-09-24 precedent, gpu_world_2026-09-24.tgz, and the layout tools/read_fleet_archive.sh reads).
set -u

_EXP_GIVEN=${EXP+x}
EXP=${EXP:-world}
case "$EXP" in
  world|retok|world_epoch) ;;
  *) echo "!! EXP='$EXP' is not an experiment this script runs: world (the default), retok or world_epoch." \
          "Nothing was started."; exit 2 ;;
esac
case "$EXP" in retok) _o=gpu_retok_out ;; world_epoch) _o=gpu_world_epoch_out ;; *) _o=gpu_world_out ;; esac
_OUT_GIVEN=${OUT:+x}
OUT=${OUT:-$_o}
WINDOWS=${WINDOWS:-20000}
SEEDS=${SEEDS:-$([[ "$EXP" == retok ]] && echo "0 1 2" || echo "0 1 2 3 4")}
# DATA_STREAM_BYTES >= 1000 x windows, so every run stops at --max-windows and never at the end of
# the stream. A run that ran out of stream is flagged in the summary; it is a different length of
# experiment wearing the same label.
BYTES=${BYTES:-$(( WINDOWS * 1000 > 2000000 ? WINDOWS * 1000 : 2000000 ))}
# EXP=retok COMPARES THE ARMS OVER THE SAME BYTES, NOT THE SAME WINDOWS. An arm that retokenizes packs
# more bytes into a window, so at a fixed window count it would score a longer stretch of the stream
# than the control and the two averages would be over different text. Every retok run therefore reads
# ONE WHOLE EPOCH of the same stream -- sized so the control takes about WINDOWS windows at the 189
# bytes/window measured on CPU (2026-09-26) -- and the window cap (RUN_WIN) is set out of reach.
# EXP=world_epoch takes the same whole-epoch sizing, for its own reason: the WORLD re-run must cross
# every phase of the stream, and a window cap below the epoch would stop it inside one.
if [[ "$EXP" == retok ]]; then
  BYTES=${RETOK_BYTES:-$(( WINDOWS * 189 ))}
  RUN_WIN=$(( WINDOWS * 3 ))
elif [[ "$EXP" == world_epoch ]]; then
  BYTES=${EPOCH_BYTES:-$(( WINDOWS * 189 ))}
  RUN_WIN=$(( WINDOWS * 3 ))
else
  RUN_WIN=$WINDOWS
fi
SMOKE_WINDOWS=${SMOKE_WINDOWS:-60}
EXTRA=${EXTRA:-}
ARCH_ALSO=${ARCH_ALSO:-}
LONG=${LONG:-0}
PAR=${PAR:-auto}
MPS=${MPS:-auto}
FILL=${FILL:-1}
MAX_SEEDS=${MAX_SEEDS:-16}
DEVICE=${DEVICE:-cuda}
# 600 AT THE WHOLE-EPOCH SHAPES, 150 AT EXP=world (LOW-GPU-WORLD-ETA). 600 is past FAB's first manage
# pass at window 501, which the 2026-09-24 fleet's 150-window calibration never reached: that fleet
# then ran about 15x slower than its ETA. EXP=world keeps 150 until the retok fleet's ETA-against-wall
# reading, which its block prints, says the calibration still misses by more than 1.5x.
CAL_WINDOWS=${CAL_WINDOWS:-$([[ "$EXP" == world ]] && echo 150 || echo 600)}
LADDER=${LADDER:-"1 2 4 8 12 16 24 32 48 64 96 128"}
# THE SCRIPT'S OWN KNOBS ARE NAMED CLEAR OF EVERY PACKAGE PREFIX (RUN_, DATA_, TOK_, FAB_, CKPT_, ...):
# they reach the runs' environment too, and a lever answering to one of these names would be set by
# accident, silently -- spine/lever.py ignores undeclared names under a declared prefix.
RETOK_ARMS=${RETOK_ARMS:-"3000 1000"}      # EXP=retok: the act cadences, one arm k<c> each
COOLDOWN_ARM=${COOLDOWN_ARM:-}             # EXP=retok: FAB_COOLDOWN of an extra arm at the fastest cadence
KEEP_CKPT=${KEEP_CKPT:-$([[ "$EXP" == retok ]] && echo 1 || echo 0)}
KEEP_POLL=${KEEP_POLL:-1}                  # seconds between the kept-checkpoint watcher's looks
PIN_RETOK=${PIN_RETOK:-3000}               # EXP=world_epoch: the TOK_RETOK_EVERY every run pins
GO_WORLD_EPOCH=${GO_WORLD_EPOCH:-0}
# THE eps RULE'S TWO READING-TIME SETTINGS (EXP=retok's analysis; O2, O14). They are read when the
# analysis runs, not recorded at launch, so --analyze can read the same runs against another eps; the
# analysis prints both.
EPS=${EPS:-0.05}                           # eps, bits/byte: a cadence FAILs past it, PASSes within it
RETOK_INCUMBENT=${RETOK_INCUMBENT:-3000}   # the incumbent cadence (O14's interim default)
[[ "$EPS" =~ ^([0-9]+\.?[0-9]*|\.[0-9]+)$ ]] && awk -v e="$EPS" 'BEGIN { exit !(e > 0) }' \
  || { echo "!! EPS='$EPS' is not a positive number of bits/byte (the eps rule's budget). Nothing was started."; exit 2; }
[[ "$RETOK_INCUMBENT" =~ ^[1-9][0-9]*$ ]] \
  || { echo "!! RETOK_INCUMBENT='$RETOK_INCUMBENT' is not a positive cadence. Nothing was started."; exit 2; }
# THE HEARTBEAT'S PERIOD (seconds; 0 = no heartbeat) AND PAR, CHECKED AT LAUNCH: an empty or 0 PAR
# made run_fleet wait for a free slot for ever, without a word.
HB_EVERY=${HB_EVERY:-30}
[[ "$HB_EVERY" =~ ^[0-9]+$ ]] || { echo "!! HB_EVERY='$HB_EVERY' is not a number of seconds (0 = no heartbeat). Nothing was started."; exit 2; }
[[ "$PAR" == auto || "$PAR" =~ ^[1-9][0-9]*$ ]] \
  || { echo "!! PAR='$PAR' is not 'auto' or a positive number of runs at a time. Nothing was started."; exit 2; }
# LM_CTX TURNS PER-TOKEN NATS INTO BITS PER BYTE, so the analysis must use the one the runs used: from
# EXTRA, else from this environment (which the runs inherit), else the lever's default.
CTX=$(echo " $EXTRA " | sed -n 's/.* LM_CTX=\([0-9][0-9]*\) .*/\1/p')
CTX=${CTX:-${LM_CTX:-128}}

# THE PRIVATE COPY KNOWS ITSELF by GW_CODE naming the directory it runs from (the launch below sets it
# with GW_ROOT, the checkout, just before it re-executes the copy). It works in the checkout, where OUT
# and the corpus (DATA_DIR) are resolved as before, and reads its code -- run.py, src/, the dashboard --
# from the copy. Anything else runs from the checkout, as it always did.
GW_PRIVATE=0
if [[ -n "${GW_CODE:-}" && -n "${GW_ROOT:-}" && -d "$GW_CODE" \
      && "$(cd "$(dirname "$0")" && pwd -P)" == "$(cd "$GW_CODE" && pwd -P)" ]]; then
  GW_PRIVATE=1
  cd "$GW_ROOT" || { echo "!! GW_ROOT='$GW_ROOT': no such checkout"; exit 2; }
  CODE_DIR=$(cd "$GW_CODE" && pwd -P)
else
  cd "$(dirname "$0")"
  CODE_DIR=$PWD
fi
DASH="$CODE_DIR/tools/fleet_dash.sh"
# THE COMMANDS THIS SCRIPT PRINTS FOR THE OWNER NAME THE CHECKOUT BY ITS ABSOLUTE PATH (2026-09-27 review):
# a second terminal opens in /workspace or /root, where `bash tools/fleet_dash.sh` is "No such file".
GW_HOME=$PWD

# ---------------------------------------------------------------- the arms
arm_env() {  # the lever settings that define each arm; an arm this does not know is refused
  case "$1" in
    fb_off)    echo "WORLD_FEEDBACK=0" ;;
    fb_on)     echo "WORLD_FEEDBACK=1" ;;
    skip)      echo "WORLD_FEEDBACK=1 WORLD_PREDICT_W=0.0 WORLD_COLLAPSE_W=0.0" ;;
    world_off) echo "WORLD_ENABLED=0" ;;
    k0)        echo "TOK_RETOK_EVERY=0" ;;
    k3000)     echo "TOK_RETOK_EVERY=3000" ;;
    k1000)     echo "TOK_RETOK_EVERY=1000" ;;
    k0_nuis)   echo "TOK_RETOK_EVERY=0 SIG_WARMUP=801" ;;
    k[1-9]*_cd[0-9]*) local c=${1%%_cd*}; echo "TOK_RETOK_EVERY=${c#k} FAB_COOLDOWN=${1##*_cd}" ;;
    k[1-9]*)   echo "TOK_RETOK_EVERY=${1#k}" ;;
    # NEVER AN EMPTY ANSWER: an unknown name used to return '' and run the defaults under it.
    *)         echo "!! arm_env: no arm named '$1'" >&2; return 1 ;;
  esac
}
if [[ "$EXP" == retok ]]; then
  for c in $RETOK_ARMS; do
    [[ "$c" =~ ^[1-9][0-9]*$ ]] || { echo "!! RETOK_ARMS: '$c' is not a positive cadence (arm k<c>; k0 is the control). Nothing was started."; exit 2; }
  done
  [[ -n "$RETOK_ARMS" ]] || { echo "!! RETOK_ARMS is empty: the retok fleet needs at least one act cadence."; exit 2; }
  [[ $(echo $RETOK_ARMS | tr ' ' '\n' | sort | uniq -d) ]] && { echo "!! RETOK_ARMS names a cadence twice: '$RETOK_ARMS'."; exit 2; }
  BASE_ARMS="k0"; for c in $RETOK_ARMS; do BASE_ARMS="$BASE_ARMS k$c"; done; BASE_ARMS="$BASE_ARMS k0_nuis"
  if [[ -n "$COOLDOWN_ARM" ]]; then
    [[ "$COOLDOWN_ARM" =~ ^[0-9]+$ ]] || { echo "!! COOLDOWN_ARM='$COOLDOWN_ARM' is not a window count (FAB_COOLDOWN)."; exit 2; }
    BASE_ARMS="$BASE_ARMS k$(echo $RETOK_ARMS | tr ' ' '\n' | sort -n | head -1)_cd$COOLDOWN_ARM"
  fi
  CTRL=k0
  # KEEP_EVERY DEFAULTS TO THE GCD OF THE CADENCES: an act of cadence K fires at window j x K + 1 and a
  # periodic save of period P lands at i x P + 1, so every act window is a save window iff P divides K.
  _g=0; for c in $RETOK_ARMS; do a=$_g; b=$c; while (( b )); do t=$(( a % b )); a=$b; b=$t; done; _g=$a; done
  KEEP_EVERY=${KEEP_EVERY:-$_g}
  [[ "$KEEP_EVERY" =~ ^[1-9][0-9]*$ ]] || { echo "!! KEEP_EVERY='$KEEP_EVERY' is not a positive window count."; exit 2; }
  for c in $RETOK_ARMS; do
    (( c % KEEP_EVERY == 0 )) || echo "WARNING: KEEP_EVERY=$KEEP_EVERY does not divide the k$c cadence: k0 keeps no copy at some k$c act windows."
  done
else
  BASE_ARMS="fb_off fb_on skip world_off"; CTRL=fb_off
  KEEP_EVERY=${KEEP_EVERY:-0}
fi
for a in $BASE_ARMS; do arm_env "$a" > /dev/null || exit 2; done
if [[ "$EXP" != world ]]; then
  [[ -n "$ARCH_ALSO" || "$LONG" -gt 0 ]] && echo "EXP=$EXP: ARCH_ALSO and LONG are ignored"
  ARCH_ALSO=""; LONG=0
fi
# THE PINS EVERY RUN OF THE EXPERIMENT CARRIES, after EXTRA and before the arm's own settings.
EXP_ENV=""
[[ "$EXP" == world_epoch ]] && EXP_ENV="TOK_RETOK_EVERY=$PIN_RETOK DATA_DRAW=planned"
# C12's LABEL, READ OFF THE TREE AND THE FLEET'S SETTINGS AT LAUNCH (so --analyze on another day
# reports what ran, not what the checkout holds then).
LEVELS="on (DOM_LEVELS declared, default on)"
grep -q "levels = Lever" "$CODE_DIR/src/domains/levers.py" 2>/dev/null || LEVELS="pre-Levels (this tree declares no DOM_LEVELS)"
_dl=$(echo " $EXTRA " | sed -n 's/.* DOM_LEVELS=\([^ ]*\) .*/\1/p'); _dl=${_dl:-${DOM_LEVELS:-}}
case "$(echo "$_dl" | tr 'A-Z' 'a-z')" in 0|off|no|none|false) LEVELS="pre-Levels (DOM_LEVELS=$_dl)" ;; esac
# §8 1.3's COUNTERS AND run.py's --flush-bytes, READ OFF THE TREE AT LAUNCH as LEVELS is (2026-09-27,
# build 1.5's review). Under DID IT FIRE an ABSENT key is UNREACHABLE, not missing: tok.bpt_tail is
# written only when an act splices, and fab.blackout_windows is seeded only at a stamp and only at
# FAB_COOLDOWN > 0, so the analysis read "not in this tree" off a fleet where no act fired. Only the
# tree can say a key is missing; each name is looked for as a quoted string in src's Python.
TREE13=""
for _k in fab.blackout_windows tok.mint_wait_windows loop.act_seconds tok.bpt_tail; do
  grep -rqF --include='*.py' "\"$_k\"" "$CODE_DIR/src" 2>/dev/null && TREE13="$TREE13${TREE13:+ }$_k"
done
FB_FLAG=no
grep -q -- '--flush-bytes' "$CODE_DIR/run.py" 2>/dev/null && FB_FLAG=yes

# THE CHECKPOINT SETTINGS OF ONE RUN, '' AT KEEP_CKPT=0 -- so every default command line is the one
# this script ran before the option existed. Appended AFTER the arm's settings, so they win over EXTRA.
ckpt_env() {  # name seed base-dir [smoke]
  [[ "$KEEP_CKPT" == 1 ]] || return 0
  local every=0
  case "$1" in
    k0|k0_nuis|k0_rerun) every=$KEEP_EVERY; [[ -n "${4:-}" ]] && every=$(( SMOKE_WINDOWS / 2 > 0 ? SMOKE_WINDOWS / 2 : 1 )) ;;
  esac
  echo "CKPT_DIR=$3/$1.s$2 CKPT_EVERY=$every"
}
# HOW MANY CHECKPOINT FILES A RUN LEAVES AT MOST: k0 its kept saves plus the ring's two, the rest of
# the k0 family the ring's two, every other run its one final save.
ckpt_files() {  # name
  case "$1" in
    k0) echo $(( (11 * WINDOWS + 10 * KEEP_EVERY - 1) / (10 * KEEP_EVERY) + 2 )) ;;
    k0_nuis|k0_rerun) echo 2 ;;
    *) echo 1 ;;
  esac
}

plan_banner() {  # the fleet's shape, as SUMMARY records it and the EXP=world_epoch guard prints it
  echo "=== $WINDOWS windows per run, DATA_STREAM_BYTES=$BYTES, seeds: $SEEDS, EXTRA='$EXTRA'"
  echo "=== plan: EXP=$EXP; arms $BASE_ARMS, plus ${CTRL}_rerun at seed 0; window cap $RUN_WIN;" \
       "CAL_WINDOWS $CAL_WINDOWS; LM_CTX $CTX"
  if [[ "$KEEP_CKPT" == 1 && "$EXP" == retok ]]; then
    echo "=== kept checkpoints: ON, k0 family CKPT_EVERY=$KEEP_EVERY, act arms final only;" \
         "k0's saves hard-linked under $OUT/ckpt/keep"
  elif [[ "$KEEP_CKPT" == 1 ]]; then
    echo "=== kept checkpoints: ON, one final checkpoint per run under $OUT/ckpt"
  else
    echo "=== kept checkpoints: OFF"
  fi
  local p="" w
  for w in $EXP_ENV; do p="$p${p:+, }$w pinned"; done
  echo "=== pins: ${p:-none}"
  echo "=== DOM Levels: $LEVELS"
  echo "=== §8 1.3 in this tree: counters ${TREE13:-none}; run.py --flush-bytes $FB_FLAG"
}

# bash gpu_world.sh --status : progress and time left of a fleet that is running (or finished),
# read off SUMMARY.txt and the logs. It changes nothing and is safe to run at any time.
# THE ANALYSIS, AS A FUNCTION so --analyze can re-run it on a finished (or interrupted) fleet.
analyze() {  # out device mps_on par ncpu
  if [[ "$EXP" == retok ]]; then analyze_retok "$@"; return; fi
  # EXP=world_epoch READS ONE WHOLE EPOCH: its runs are meant to end at the stream's end, so the
  # flags turn over (the 6th argument). At EXP=world the output is what it always was.
  python3 - "$@" "$([[ "$EXP" == world_epoch ]] && echo 1 || echo 0)" <<'PY'
import glob, json, math, os, re, statistics, sys
out, dev, mps_on, par, ncpu = sys.argv[1], sys.argv[2], sys.argv[3] == "1", int(sys.argv[4]), int(sys.argv[5])
whole = len(sys.argv) > 6 and sys.argv[6] == "1"

def rep(t):
    r = {}
    for m in re.finditer(r"^\s+([A-Za-z_][\w.@()-]*\.[\w.@()-]+)\s+(\S+)\s*$", t, re.M):
        r[m.group(1)] = m.group(2)
    return r

runs = {}
for log in sorted(glob.glob(os.path.join(out, "logs", "*.log"))):
    tag = os.path.basename(log)[:-4]
    name, seed = tag.rsplit(".s", 1)
    t = open(log).read(); r = rep(t)
    try: curve = json.load(open(os.path.join(out, "curves", tag + ".json")))
    except (OSError, ValueError): curve = None
    m = re.search(r"=== (\d+) windows[^\n]*? in ([\d.]+)s", t)
    vocab = re.findall(r"vocab=(\d+)", t)
    runs[(name, int(seed))] = dict(
        curve=curve, r=r, ok=curve is not None,
        windows=int(m.group(1)) if m else None, secs=float(m.group(2)) if m else None,
        stopped_at_max="stopped at max_windows" in t, nonfinite="non-finite" in t.lower() and "refus" in t.lower(),
        vocab=int(vocab[-1]) if vocab else None, mint=r.get("tok.mint"),
        peak=(re.search(r"peak CUDA memory [\d.]+ GiB allocated, ([\d.]+) GiB reserved", t) or [None, None])[1])

def half(a, b):
    n = min(len(a), len(b)); h = n // 2
    return (sum(a[i] - b[i] for i in range(h, n)) / (n - h), sum(a[i] - b[i] for i in range(n)) / n, n)

def stat(xs):
    m = sum(xs) / len(xs)
    se = math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1) / len(xs)) if len(xs) > 1 else float("nan")
    return m, se

print()
print("=== RUNS ===")
for (name, seed), v in sorted(runs.items()):
    wps = v["windows"] / v["secs"] if v["windows"] and v["secs"] else float("nan")
    flags = []
    if not v["ok"]: flags.append("NO CURVE")
    if whole:
        # A WHOLE-EPOCH RUN THAT HIT THE CAP read less than its epoch: a shorter experiment under the label.
        if v["stopped_at_max"]: flags.append("STOPPED AT THE WINDOW CAP: did not read the whole epoch")
    elif v["ok"] and not v["stopped_at_max"]: flags.append("RAN OUT OF STREAM (raise BYTES)")
    if v["nonfinite"]: flags.append("NON-FINITE STOP")
    r = v["r"]
    print(f"  {name:<18} s{seed:<3} {v['windows'] or '?':>6} win {wps:6.2f} w/s  vocab {v['vocab']}  mint {v['mint']}"
          f"  extra_ratio {r.get('lm.encode.extra_ratio', '-'):>9} max {r.get('lm.encode.extra_ratio_max', '-'):>9}"
          f"  latent_std {r.get('world.latent_std', '-'):>9}  peak {v['peak'] or '-'} GiB  {' '.join(flags)}")

# the run-to-run floor
a, b = runs.get(("fb_off", 0)), runs.get(("fb_off_rerun", 0))
floor = None
if a and b and a["curve"] and b["curve"]:
    n = min(len(a["curve"]), len(b["curve"]))
    mx = max(abs(a["curve"][i] - b["curve"][i]) for i in range(n))
    floor = abs(half(a["curve"], b["curve"])[0])
    print()
    print(f"=== RUN-TO-RUN FLOOR (fb_off seed 0 twice): max per-flush |diff| {mx:.3g}, "
          f"last-half mean |diff| {floor:.4f}" + ("  -> BIT-EXACT on this card" if mx == 0 else ""))

# paired comparisons against the group's fb_off
print()
print("=== PAIRED AGAINST fb_off (arm - fb_off, same seed; negative = the arm is better) ===")
results = {}
groups = {}
for (name, seed) in runs:
    if name == "fb_off_rerun": continue
    base, _, suffix = name.partition("@")
    long_ = base.endswith("_long")
    key = ("@" + suffix) if suffix else ("_long" if long_ else "")
    groups.setdefault(key, set()).add(name)
for key, names in sorted(groups.items()):
    ctrl = ("fb_off_long" if key == "_long" else "fb_off" + key)
    for name in sorted(names):
        if name == ctrl: continue
        rows = []
        for (n2, seed), v in sorted(runs.items()):
            if n2 != name: continue
            c = runs.get((ctrl, seed))
            if not (v["curve"] and c and c["curve"]): continue
            mismatch = v["vocab"] != c["vocab"] or v["mint"] != c["mint"]
            rows.append((seed,) + half(v["curve"], c["curve"]) + (mismatch,))
        if not rows: continue
        lh, se = stat([r[1] for r in rows]); fr, fse = stat([r[2] for r in rows])
        neg = sum(1 for r in rows if r[1] < 0)
        results[name] = (lh, se, neg, len(rows), {r[0]: r[1] for r in rows})
        print(f"  {name:<18} vs {ctrl:<12} last half {lh:+.4f} +- {se:.4f} SE   full run {fr:+.4f} +- {fse:.4f}"
              f"   {neg}/{len(rows)} seeds negative")
        print("      per seed (last half): " + "  ".join(f"s{r[0]} {r[1]:+.4f}" for r in rows))
        if any(r[4] for r in rows):
            print("      !! vocab size or tok.mint differs from fb_off on some seed: per-token nats are then not "
                  "comparable; convert to bits per byte before trusting this row")

# the decision, the judge's rule from Q-WORLD-10
print()
print("=== DECISION (Q-WORLD-10's rule) ===")
if whole:
    print("  Q-WORLD-10's rule, shown for continuity; the pre-registered re-run rule (note WORLD 4) needs "
          "SR0's retention probe")
fo, sk, wo = results.get("fb_on"), results.get("skip"), results.get("world_off")
if fo:
    lh, se, neg, n, fo_seeds = fo
    sig = n > 1 and lh < -2 * se
    if floor is not None and abs(lh) < floor:
        print(f"  fb_on - fb_off ({lh:+.4f}) is SMALLER than this card's run-to-run floor ({floor:.4f}): no decision possible.")
    if neg >= math.ceil(0.8 * n) and sig:
        print(f"  TURN WORLD_FEEDBACK ON (=1): lower in {neg}/{n} seeds and more than 2 SE below zero ({lh:+.4f} +- {se:.4f}).")
    else:
        print(f"  WITHIN NOISE ({neg}/{n} seeds negative, {lh:+.4f} +- {se:.4f}): WORLD_FEEDBACK stays off (its "
              f"default since 2026-09-24) -- the path would cost kernel launches for nothing.")
    if sk:
        # PAIRED, skip - fb_on per seed. The first version compared the two arms' means against the
        # larger of their SEs, so a skip arm that was WORSE on average but wildly variable (+0.09 vs
        # +0.003, one seed at +0.36) was printed as "skip ~= fb_on".
        both = [sk[4][s] - fo_seeds[s] for s in sk[4] if s in fo_seeds]
        d = sum(both) / len(both) if both else sk[0] - lh
        dse = (math.sqrt(sum((x - d) ** 2 for x in both) / (len(both) - 1) / len(both))
               if len(both) > 1 else float("inf"))
        if abs(d) <= 2 * dse:
            print(f"  skip - fb_on = {d:+.4f} +- {dse:.4f} (paired): not separable -- if fb_on helps at all, the help "
                  f"is CAPACITY, not world modelling.")
        elif d < 0:
            print(f"  skip BEATS fb_on ({sk[0]:+.4f} vs {lh:+.4f}): WORLD's objectives HURT the forecast path -- revisit "
                  f"WORLD_PREDICT_W / WORLD_COLLAPSE_W or detach the population's input.")
        else:
            print(f"  fb_on beats skip by {d:+.4f} +- {dse:.4f} (paired): WORLD's own objectives keep the forecast "
                  f"path stable (compare the arms' latent_std and extra_ratio_max).")
    if wo and wo[0] < lh:
        print(f"  world_off is better than fb_on ({wo[0]:+.4f} vs {lh:+.4f}): the subsystem does not earn its cost.")
else:
    print("  fb_on has no paired rows; nothing to decide.")

# did the card fill
if dev == "cuda":
    print()
    try:
        rows = [l.strip().split(",") for l in open(os.path.join(out, "smi.csv")) if l.strip()]
        util = [float(r[1]) for r in rows]; mem = [float(r[2]) for r in rows]; tot = float(rows[0][3])
        k = len(util) // 10; body = util[k:len(util) - k] or util        # drop the ramp-up and tail-off
        print(f"=== GPU: utilisation mean {statistics.mean(body):.1f}%  median {statistics.median(body):.0f}%  "
              f">=90% on {100 * sum(u >= 90 for u in body) / len(body):.0f}% of samples  "
              f"memory peak {max(mem) / 1024:.1f} of {tot / 1024:.1f} GiB   (MPS {'on' if mps_on else 'off'}, {par} at a time)")
        if statistics.mean(body) < 80:
            why = (f"parallelism is capped by this box's {ncpu} CPU cores" if par >= ncpu - 1 else
                   "raise PAR (GPU memory allows more)")
            print(f"    The card was NOT full: {why}." + ("" if mps_on else " Without MPS the runs time-slice; MPS=1 if it can be enabled."))
    except (OSError, ValueError, IndexError) as e:
        print(f"=== GPU: no utilisation samples ({e})")
PY
}

# THE RETOK SHIP RULE (EXP=retok): O14's choice, read by the eps rule (O2) on prequential bits/byte per
# phase, paired by seed; then the rates, the secondaries and the kept checkpoints, and the block to
# paste back -- ONE program, so the verdict the block carries is the one ANALYSIS.txt printed, never a
# second reading of the logs.
analyze_retok() {  # out device mps_on par ncpu
  gw_py retok "$1" "$CTX" "$(archive_path)" "$EPS" "$RETOK_INCUMBENT"
}

# THE BLOCK AND ITS PARTS (Proposal 05 §8 1.5). Modes: retok (the analysis above, which also writes
# PASTE_BACK.txt and KEPT.txt), wrap (EXP=world and world_epoch: the header plus ANALYSIS.txt from
# '=== RUNS ===' on), fail (a stop before the analysis). Every header is read off SUMMARY.txt alone,
# so --analyze reproduces the block the fleet wrote.
gw_py() {  # mode out ...
  python3 - "$@" <<'PY'
import glob, json, math, os, re, sys
MODE, OUT = sys.argv[1], sys.argv[2]
CAP = 80                              # lines in the block, both delimiters included
L2 = math.log(2)


def rd(path):
    try:
        with open(path, errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def rep(t):
    r = {}
    for m in re.finditer(r"^\s+([A-Za-z_][\w.@()-]*\.[\w.@()-]+)\s+(\S+)\s*$", t, re.M):
        r[m.group(1)] = m.group(2)
    return r


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def fmt(x, spec=".2f", none="-"):
    if x is None:
        return none
    if spec == "n" and float(x) == int(x):
        return str(int(x))
    return format(x, ".2f" if spec == "n" else spec)


S = rd(os.path.join(OUT, "SUMMARY.txt"))


def sget(rx, g=1):
    m = re.search(rx, S, re.M)
    return m.group(g) if m else None


EXTRA = sget(r"^=== \d+ windows per run, DATA_STREAM_BYTES=\d+, seeds: .*?, EXTRA='(.*)'$") or ""
KEPT_ON = (sget(r"^=== kept checkpoints: (ON|OFF)") or "?")


def head(exp, labels=()):
    """The header, the card and the shape: three lines, the same whenever the block is written."""
    first = S.splitlines()[0] if S else ""
    m = re.match(r"=== gpu_world\.sh\s+(\S+)\s+commit\s*(\S*)(.*)$", first)
    when, commit, dirty = (m.group(1), m.group(2) or "?", "(dirty)" in m.group(3)) if m else ("?", "?", False)
    out = [f"gpu_world.sh EXP={exp}  commit {commit}"
           + (" (DIRTY: src, run.py or gpu_world.sh differed from it)" if dirty else "")
           + f"  launched {when}" + "".join("  " + l for l in labels)]
    gpus = re.findall(r"^\s+\d+, ([^,\n]+), (\d+) MiB, \d+ MiB\s*$", S, re.M)
    kinds = sorted({f"{n.strip()} {mib} MiB" for n, mib in gpus})
    card = (f"{len(gpus)} x {kinds[0]}" if len(kinds) == 1 else ", ".join(kinds)) if gpus else "no GPU listed"
    cores = re.search(r"^=== (\d+) CPU core\(s\), (\d+) GPU\(s\), device=(\w+)", S, re.M)
    par = re.findall(r"^=== \d+ run\(s\), (\d+) at a time", S, re.M)
    tv = sget(r"^=== (torch \S+, CUDA \S+)") or "torch ?"
    out.append(f"card: {card}; {tv}; "
               f"NCPU {cores.group(1) if cores else '?'}; PAR {par[-1] if par else '?'}; "
               f"MPS {'on' if 'CUDA MPS started' in S else 'off'}; device={cores.group(3) if cores else '?'}")
    sz = re.search(r"^=== (\d+) windows per run, DATA_STREAM_BYTES=(\d+), seeds: (.*?), EXTRA='(.*)'$", S, re.M)
    plan = sget(r"^=== plan: .*?window cap (\d+); CAL_WINDOWS (\d+); LM_CTX (\d+)", 0)
    pins = sget(r"^=== pins: (.*)$")
    shp = (f"shape: {sz.group(1)} windows/run, DATA_STREAM_BYTES={sz.group(2)}, seeds {sz.group(3)}, "
           f"EXTRA='{sz.group(4)}'" if sz else "shape: ? (SUMMARY.txt holds no sizing line)")
    if plan:
        pm = re.search(r"window cap (\d+); CAL_WINDOWS (\d+); LM_CTX (\d+)", plan)
        shp += f"; cap {pm.group(1)}; CAL {pm.group(2)}; LM_CTX {pm.group(3)}"
    shp += f"; kept ckpts {KEPT_ON}" + (f"; pins {pins}" if pins and pins != "none" else "")
    out.append(shp)
    return out


def archive_line(archive):
    return (f"archive: {os.path.basename(archive)} beside {OUT} (logs, curves, SUMMARY, ANALYSIS, this block; "
            f"no checkpoints) -- keep it")


def emit(sections):
    """Write the block, at most CAP lines. sections: (name, lines, rank) in order, the LAST one the
    archive line, which always closes the block. `lines` may instead be a function fit(n) returning
    at most n lines (the per-seed table), and fit(None) its whole. When the block is too long the
    highest rank goes first; if it is still too long, each fitted section gets the room the rest
    leaves, so its rows go before any other line of rank 0. Only rank-0 lines that alone outgrow the
    cap, which no fleet's do, would still be truncated from the end. One line says what was cut, all
    of which is in ANALYSIS.txt and the archive.
    RANK 0 WAS CUT BEFORE (2026-09-27, build 1.5's review): the per-seed rows were rank 0 and came
    first, so past about 60 seeds the truncation from the end took the alarms, the margin and the
    DECISION while every seed's row survived."""
    budget = CAP - 2
    tail = sections[-1][1]
    sections = [(n, l if callable(l) else list(l), r) for n, l, r in sections[:-1]]
    cut = []

    def lines(l, n=None):
        return l(n) if callable(l) else l

    def size():
        return sum(len(lines(l)) for _, l, _ in sections) + len(tail) + (1 if cut else 0)

    for rank in sorted({r for _, _, r in sections if r}, reverse=True):
        for i, (name, l, r) in enumerate(sections):
            if r == rank and lines(l) and size() > budget:
                cut.append(name)
                sections[i] = (name, [], r)
    for i, (name, l, r) in enumerate(sections):
        if callable(l):
            whole = l(None)
            if size() > budget:
                rest = size() - len(whole) + (0 if cut else 1)
                fitted = l(max(0, budget - rest))
                if len(fitted) < len(whole):
                    cut.append(f"{name} (condensed)")
                sections[i] = (name, fitted, r)
            else:
                sections[i] = (name, whole, r)
    body = [x for _, l, _ in sections for x in l]
    room = budget - len(tail)
    if cut or len(body) > room:
        room -= 1
    more = max(0, len(body) - room)
    body = body[:room]
    if cut or more:
        body.append(f"(cut to fit {CAP} lines: " + ", ".join(cut + ([f"the last {more} line(s)"] if more else []))
                    + " -- in ANALYSIS.txt and the archive)")
    lines = body + tail
    text = "\n".join(["==== PASTE THIS BACK ===="] + lines + ["==== END ===="]) + "\n"
    # A FULL DISK DOES NOT SWALLOW THE BLOCK (2026-09-27): unwritable, it goes to stderr, which is the
    # fleet's log, and the paste-back file is left unwritten.
    try:
        with open(os.path.join(OUT, "PASTE_BACK.txt"), "w") as fh:
            fh.write(text)
    except OSError as e:
        sys.stderr.write(f"!! could not write {os.path.join(OUT, 'PASTE_BACK.txt')} ({e}); the block:\n" + text)


def done_book():
    d = {}
    for l in rd(os.path.join(OUT, "logs", "_done.txt")).splitlines():
        m = re.match(r"(\S+) rc=(-?\d+) secs=(\d+)", l)
        if m:
            d[m.group(1)] = (int(m.group(2)), int(m.group(3)))
    return d


def last_line(t):
    ls = [x.strip() for x in t.splitlines() if x.strip()]
    return ls[-1][:160] if ls else "(empty log)"


def failures(runs, done, cap=8):
    """rc != 0 with each log's last line (at most `cap`), then runs with no curve or stopped at the cap."""
    bad = [(tag, rc) for tag, (rc, _) in sorted(done.items()) if rc != 0]
    out = [f"runs: {len(done) - len(bad)} of {len(done)} ended rc=0" + (", every one" if not bad else "")]
    for tag, rc in bad[:cap]:
        out.append(f"  FAILED {tag} rc={rc}: {last_line(rd(os.path.join(OUT, 'logs', tag + '.log')))}")
    if len(bad) > cap:
        out.append(f"  ... {len(bad) - cap} more failed run(s): logs/_done.txt")
    nc = [f"{n}.s{s}" for (n, s), v in sorted(runs.items()) if v.get("curve") is None and done.get(f"{n}.s{s}", (0,))[0] == 0]
    cap_ = [f"{n}.s{s}" for (n, s), v in sorted(runs.items()) if v.get("stopped")]
    if nc:
        out.append(f"  NO CURVE: {' '.join(nc[:12])}" + (" ..." if len(nc) > 12 else ""))
    if cap_:
        out.append(f"  STOPPED AT THE WINDOW CAP (did not read the whole stream): {' '.join(cap_[:12])}"
                   + (" ..." if len(cap_) > 12 else ""))
    return out


# >>> THE ε RULE (Proposal 05 O2 and O14, 2026-09-27). tests/test_gpu_world.py F14-F16 exec this block
# by its two marker lines, so it stays self-contained: `math` only -- the GPU box's python has no
# numpy or scipy promised -- and no name from the rest of this program.
def _betacf(a, b, x):
    """The continued fraction of the incomplete beta function, by the modified Lentz method."""
    tiny = 1e-300
    c, d = 1.0, 1.0 - (a + b) * x / (a + 1.0)
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 1000):
        m2 = 2 * m
        for aa in (m * (b - m) * x / ((a - 1.0 + m2) * (a + m2)),
                   -(a + m) * (a + b + m) * x / ((a + m2) * (a + 1.0 + m2))):
            d = 1.0 + aa * d
            d = 1.0 / (d if abs(d) > tiny else tiny)
            c = 1.0 + aa / c
            c = c if abs(c) > tiny else tiny
            h *= d * c
        if abs(d * c - 1.0) < 1e-15:
            break
    return h


def betai(a, b, x):
    """The regularized incomplete beta function I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    bt = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def t_sf(t, df):
    """P(T > t) for Student's t with df degrees of freedom: I_{df/(df+t^2)}(df/2, 1/2) / 2 above 0."""
    tail = 0.5 * betai(df / 2.0, 0.5, df / (df + t * t))
    return tail if t >= 0 else 1.0 - tail


def t_quantile(p, df):
    """The p-quantile of Student's t with df degrees of freedom, by bisection on t_sf."""
    if not 0.0 < p < 1.0:
        raise ValueError(f"t_quantile: p={p} is not inside (0, 1)")
    if p < 0.5:
        return -t_quantile(1.0 - p, df)
    lo, hi = 0.0, 1.0
    while t_sf(hi, df) > 1.0 - p:
        lo, hi = hi, 2.0 * hi
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if t_sf(mid, df) > 1.0 - p:
            lo = mid
        else:
            hi = mid
        if hi - lo <= 1e-13 * hi:
            break
    return 0.5 * (lo + hi)


def mean_se(xs):
    """(n, mean, sd / sqrt(n)); the mean is None at n = 0 and the SE None at n < 2."""
    n = len(xs)
    if not n:
        return 0, None, None
    m = sum(xs) / n
    if n < 2:
        return n, m, None
    return n, m, math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1) / n)


def eps_rule(arms, eps, alpha=0.05):
    """O14's harm reading, by the eps rule (O2). arms: {arm: one list per phase of the paired differences
    arm - k0 over the seeds with both readings}. Per phase the one-sided 95% UPPER bound is
    mean + t(0.95, n-1) x sd / sqrt(n), and the LOWER bound mean - t(1 - a/N, n-1) x sd / sqrt(n): a
    Bonferroni split over the N phases, and Holm across the arms -- the arm with the strongest evidence
    of harm (the smallest N x p of 'difference > eps' over its phases, uncapped so arms that cannot
    FAIL are still ordered) is tested at alpha / K, the next at alpha / (K - 1), and so on, and once one
    does not FAIL no later one can. FAIL if some phase's lower bound exceeds eps; PASS if every phase's
    upper bound is at most eps; otherwise UNRESOLVED -- always so at n < 2, where no bound can be
    formed. Returns {arm: dict(verdict, level, phases, note)} in Holm's order, phases being (n, mean,
    lower, upper) with None where a bound cannot be formed."""
    def p_harm(xs):
        n, m, se = mean_se(xs)
        if se is None:
            return 1.0
        if se == 0.0:
            return 0.0 if m > eps else 1.0
        return t_sf((m - eps) / se, n - 1)

    nph = max([len(v) for v in arms.values()] or [1])
    padj = {a: nph * min([p_harm(xs) for xs in ph] or [1.0]) for a, ph in arms.items()}
    order = sorted(arms, key=lambda a: (padj[a], a))
    out, holm_open = {}, True
    for i, a in enumerate(order):
        level = alpha / (len(order) - i)
        rows = []
        for xs in arms[a]:
            n, m, se = mean_se(xs)
            rows.append((n, m, None, None) if se is None else
                        (n, m, m - t_quantile(1.0 - level / nph, n - 1) * se, m + t_quantile(0.95, n - 1) * se))
        harm = any(lo is not None and lo > eps for _, _, lo, _ in rows)
        fail = harm and holm_open
        ok = bool(rows) and all(up is not None and up <= eps for _, _, _, up in rows)
        note = ("a lower bound exceeds ε, but Holm stopped at an earlier arm that did not FAIL"
                if harm and not holm_open else
                "fewer than 2 paired seeds in some phase: no bound there" if any(n < 2 for n, _, _, _ in rows)
                else "")
        holm_open = holm_open and fail
        out[a] = dict(verdict="FAIL" if fail else "PASS" if ok else "UNRESOLVED", level=level, phases=rows,
                      note=note)
    return out


def better_than(diffs, alpha=0.05):
    """'Significantly better' in O2's form: the one-sided upper bound of the paired whole-run difference
    (challenger - incumbent) is below 0 -- at 95% for one challenger, Holm across several. diffs: {arm:
    [the differences over the seeds with both runs]}. Returns {arm: (n, mean, upper, better, level)}."""
    def p_better(xs):
        n, m, se = mean_se(xs)
        if se is None:
            return 1.0
        if se == 0.0:
            return 0.0 if m < 0 else 1.0
        return 1.0 - t_sf(m / se, n - 1)

    order = sorted(diffs, key=lambda a: (p_better(diffs[a]), a))
    out, holm_open = {}, True
    for i, a in enumerate(order):
        level = alpha / (len(order) - i)
        n, m, se = mean_se(diffs[a])
        up = None if se is None else m + t_quantile(1.0 - level, n - 1) * se
        b = holm_open and up is not None and up < 0
        holm_open = holm_open and b
        out[a] = (n, m, up, b, level)
    return out


def choose(cadences, verdicts, better, inc):
    """O14's choice. cadences: every cadence arm of the fleet (k<c>); verdicts: eps_rule's reading of the
    ones that acted; better: better_than's reading of the acted challengers against the incumbent arm
    `inc` (k3000). Returns (kind, arm, why), kind one of 'undecided' (no cadence acted), 'escalate' (every
    cadence FAILs), 'replace' (arm replaces the incumbent) or 'stays' (the incumbent stays). A challenger
    replaces the incumbent only if it does not FAIL and (the incumbent FAILs, or it is significantly
    better); among several that qualify, the lowest upper bound against the incumbent. 0 is never an
    answer: it is the control, and the rule never ships it."""
    if not verdicts:
        return "undecided", None, "no cadence acted in these runs"
    if cadences and all(verdicts.get(a, {}).get("verdict") == "FAIL" for a in cadences):
        return "escalate", None, "every cadence FAILs against k0 by the ε rule"
    iv = verdicts.get(inc, {}).get("verdict")
    chal = sorted(a for a in verdicts if a != inc)
    bt = {c: better.get(c) or (0, None, None, False, None) for c in chal}
    ok = [c for c in chal if verdicts[c]["verdict"] != "FAIL" and (iv == "FAIL" or bt[c][3])]
    if ok:
        c = min(ok, key=lambda a: (math.inf if bt[a][2] is None else bt[a][2], a))
        b = bt[c]
        why = (f"{c} {verdicts[c]['verdict']} against k0, and "
               + (f"{inc} FAILs" if iv == "FAIL" else
                  f"the whole-run {c[1:]} - {inc[1:]} upper bound {b[2]:+.4f} is below 0"))
        return "replace", c, why
    parts = []
    if inc not in cadences:
        parts.append(f"the fleet has no {inc} arm, so nothing is read against the incumbent")
    elif iv is None:
        parts.append(f"{inc} did not act in these runs, so the incumbent is not read")
    else:
        parts.append(f"{inc} {iv} against k0")
    for c in chal:
        b = better.get(c)
        parts.append(f"{c} FAILs" if verdicts[c]["verdict"] == "FAIL" else
                     f"{c} {verdicts[c]['verdict']}, " + (
                         "not compared with the incumbent" if not b or iv is None else
                         f"the whole-run {c[1:]} - {inc[1:]} upper bound "
                         + ("cannot be formed (n < 2)" if b[2] is None else f"{b[2]:+.4f} is not below 0")))
    return "stays", inc, "; ".join(parts)
# <<< THE ε RULE


# ------------------------------------------------------------------------------------------ retok
def retok(ctx_arg, archive, eps, inc_cadence):
    # LM_CTX: what the fleet recorded at launch, else its EXTRA, else what this shell was given.
    ctx = int(sget(r"^=== plan: .*?LM_CTX (\d+)") or (re.search(r"(?:^| )LM_CTX=(\d+)", EXTRA) or [0, 0])[1]
              or ctx_arg)
    done = done_book()
    runs = {}
    for log in sorted(glob.glob(os.path.join(OUT, "logs", "*.log"))):
        tag = os.path.basename(log)[:-4]
        name, _, seed = tag.rpartition(".s")
        if not name or not seed.isdigit():
            continue
        t = rd(log)
        m = re.search(r"^\s+loop\.bytes_scored\s+(\d+)\s*$", t, re.M)
        acts = re.search(r"^\s+loop\.acts\s+(\d+)\s*$", t, re.M)
        vocab = re.findall(r"vocab=(\d+)", t)
        try: curve = json.load(open(os.path.join(OUT, "curves", tag + ".json")))
        except (OSError, ValueError): curve = None
        try: fbytes = json.load(open(os.path.join(OUT, "curves", tag + ".bytes.json")))
        except (OSError, ValueError): fbytes = None
        bpb = (sum(curve) * ctx / math.log(2) / int(m.group(1))) if (curve and m and int(m.group(1))) else None
        w = re.search(r"=== (\d+) windows[^\n]*? in ([\d.]+)s", t)
        # EACH ACT'S OWN LINE: its window, and the tail's bytes per token before and after (§8 1.3), or
        # failing that the whole stream's ids before and after, whose ratio is the same kind of rise.
        at, rise, rise_kind = [], [], None
        for am in re.finditer(r"mid-epoch act at window (\d+):[^\n]*?\((\d+) -> (\d+) ids;([^\n]*)", t):
            at.append(int(am.group(1)))
            tb = re.search(r"Tail bytes/token ([\d.]+) -> ([\d.]+)", am.group(4))
            if tb:
                rise.append(float(tb.group(2)) / float(tb.group(1)) - 1.0); rise_kind = "tail"
            else:
                rise.append(int(am.group(2)) / int(am.group(3)) - 1.0); rise_kind = rise_kind or "ids"
        cd = re.search(r"cooldown=(\d+) windows", t)
        # THE POOL'S TRAJECTORY (O14's blackout split): the progress lines' n_live every 100 windows, and
        # FAB_SLOTS off the growth gate's text (any FAB_SLOTS= in the log failing that), else EXTRA's, else
        # the lever's default 4096. The fill is the first progress window with n_live >= FAB_SLOTS.
        prog = [(int(pw), int(pn)) for pw, pn in re.findall(r"^\[(\d+) windows\][^\n]*? n_live=(\d+)", t, re.M)]
        sl = (re.search(r"^\s+gate:fab\.growth\s[^\n]*?FAB_SLOTS=(\d+)", t, re.M) or re.search(r"FAB_SLOTS=(\d+)", t)
              or re.search(r"(?:^| )FAB_SLOTS=(\d+)", EXTRA))
        slots = int(sl.group(1)) if sl else 4096
        r_ = rep(t)
        nl = fnum(r_.get("fab.n_live"))
        # THE STREAM'S PHASE COUNT, off data_plan's own gate: "gate:data.phase_entered ('fired', 'E vs N')".
        pe = re.search(r"^\s+gate:data\.phase_entered\s[^\n]*?'(\d+) vs (\d+)'", t, re.M)
        runs[(name, int(seed))] = dict(
            bpb=bpb, acts=acts.group(1) if acts else "-", n=len(curve or []), vocab=vocab[-1] if vocab else "?",
            stopped="stopped at max_windows" in t, r=r_, curve=curve, fbytes=fbytes,
            win=int(w.group(1)) if w else None, secs=float(w.group(2)) if w else None,
            bytes=int(m.group(1)) if m else None, at=at, rise=rise, rise_kind=rise_kind,
            cooldown=int(cd.group(1)) if cd else None, slots=slots,
            fill=next((pw for pw, pn in prog if pn >= slots), None),
            nlive=nl if nl is not None else (float(prog[-1][1]) if prog else None),
            nph=int(pe.group(2)) if pe else None)
    names = {n for (n, s) in runs}
    ACT = sorted((n for n in names if re.fullmatch(r"k[1-9]\d*", n)), key=lambda a: -int(a[1:]))
    CD = sorted(n for n in names if re.fullmatch(r"k[1-9]\d*_cd\d+", n))
    ORDER = [a for a in ["k0"] + ACT + CD + ["k0_nuis"] if a in names]
    levels = sget(r"^=== DOM Levels: (.*)$")
    labels = ["B-provisional"] + (["pre-Levels"] if levels and "pre-Levels" in levels else
                                  ["Levels unrecorded"] if levels is None else [])

    print()
    print(f"=== RUNS (prequential bits/byte = sum(loss) x LM_CTX {ctx} / ln 2 / loop.bytes_scored) ===")
    for (name, seed), v in sorted(runs.items()):
        print(f"  {name:<10} s{seed:<3} {v['n']:>6} flushes  acts {v['acts']:>4}  vocab {v['vocab']:>5}  "
              f"preq {v['bpb'] if v['bpb'] is None else round(v['bpb'], 5)}"
              + ("  STOPPED AT THE WINDOW CAP: this run did not read the whole stream, so its bytes differ "
                 "from the other arms'" if v["stopped"] else ""))
    a, b = runs.get(("k0", 0)), runs.get(("k0_rerun", 0))
    rerun = None
    if a and b and a["bpb"] is not None and b["bpb"] is not None:
        rerun = abs(a['bpb'] - b['bpb'])
        print(f"\n=== RUN-TO-RUN (k0 seed 0 twice): |diff| {rerun:.3g}")
    seeds = sorted({s for (n, s) in runs if n == "k0" and runs[(n, s)]["bpb"] is not None})

    # ---------------------------------------------------------------- the endpoint: bits/byte per phase
    # THE STREAM'S PHASES ARE DATA_STREAM_BYTES CUT INTO N EQUAL BYTE RANGES, phase k covering
    # [round(k B / N), round((k + 1) B / N)) (data/api.py::data_plan, for a generated schedule and an
    # explicit one alike). N is read off the logs' data.phase_entered gate, else EXTRA, else the default 4.
    # Each flush is placed by its first byte, its run's cumulative per-flush bytes (run.py --flush-bytes),
    # and a phase's bits/byte is sum(loss x LM_CTX) / ln 2 / sum(bytes) over its flushes: the whole-run
    # formula above restricted to them, so the phases of a run whose flush bytes sum to
    # loop.bytes_scored average, byte-weighted, to its whole-run value.
    total = int(sget(r"DATA_STREAM_BYTES=(\d+)") or 0)
    gate_n = [v["nph"] for v in runs.values() if v["nph"]]
    if gate_n:
        nph = max(sorted(set(gate_n)), key=gate_n.count)
        nph_src = "the logs' data.phase_entered gate" + ("" if len(set(gate_n)) == 1 else
                                                          f" (the runs disagree: {sorted(set(gate_n))})")
    elif re.search(r"(?:^| )DATA_PHASE_SCHED=(\S+)", EXTRA):
        nph = len(re.search(r"(?:^| )DATA_PHASE_SCHED=(\S+)", EXTRA).group(1).strip("'\"").split("|"))
        nph_src = "EXTRA's DATA_PHASE_SCHED"
    elif re.search(r"(?:^| )DATA_PHASES=(\d+)", EXTRA):
        nph = max(2, int(re.search(r"(?:^| )DATA_PHASES=(\d+)", EXTRA).group(1)))
        nph_src = "EXTRA's DATA_PHASES (floored at 2, as data_plan floors it)"
    else:
        nph, nph_src = 4, "the default DATA_PHASES (no log carries data.phase_entered)"

    def phases(v):
        c, fb = v["curve"], v["fbytes"]
        if not (c and fb and len(c) == len(fb) and total):
            return None
        lo_n, lo_b, off = [0.0] * nph, [0] * nph, 0
        for x, nb in zip(c, fb):
            k = min(nph - 1, next((j for j in range(nph) if off < round((j + 1) * total / nph)), nph - 1))
            lo_n[k] += x; lo_b[k] += nb; off += nb
        return [lo_n[k] * ctx / L2 / lo_b[k] if lo_b[k] else None for k in range(nph)]

    ph_of = {key: phases(v) for key, v in runs.items()}
    fb_off = [f"{n}.s{s} ({sum(v['fbytes'])} vs {v['bytes']})" for (n, s), v in sorted(runs.items())
              if v["fbytes"] and v["bytes"] is not None and sum(v["fbytes"]) != v["bytes"]]

    # ---------------------------------------------------------------- the eps rule (O14, O2)
    # A CADENCE THAT NEVER ACTED IS NOT TESTED: it is the control under another name.
    ACTED = [a for a in ACT if any(runs.get((a, s), {}).get("acts", "-") not in ("-", "0") for s in seeds)]
    rule_runs = [(n, s) for (n, s), v in runs.items() if (n == "k0" or n in ACTED) and v["bpb"] is not None]
    no_ph = sorted(f"{n}.s{s}" for n, s in rule_runs if ph_of[(n, s)] is None)
    rnph = 1 if no_ph else nph

    def endpoint(key):
        v = runs.get(key)
        if not v or v["bpb"] is None:
            return None
        return [v["bpb"]] if rnph == 1 else ph_of[key]

    rule_in = {}
    for arm in ACTED:
        per = [[] for _ in range(rnph)]
        for s in seeds:
            ea, e0 = endpoint((arm, s)), endpoint(("k0", s))
            if ea is None or e0 is None:
                continue
            for p in range(rnph):
                if ea[p] is not None and e0[p] is not None:
                    per[p].append(ea[p] - e0[p])
        rule_in[arm] = per
    R = eps_rule(rule_in, eps)
    INC = f"k{inc_cadence}"                  # the incumbent's arm
    allseeds_ = sorted({s for (n, s) in runs})
    wr = lambda a, s: runs.get((a, s), {}).get("bpb")
    WD = {c: [wr(c, s) - wr(INC, s) for s in allseeds_ if wr(c, s) is not None and wr(INC, s) is not None]
          for c in R if c != INC} if INC in R else {}
    B = better_than({c: d for c, d in WD.items() if d})
    kind, pick, why = choose(ACT, R, B, INC)
    ns = sorted({max([len(xs) for xs in rule_in[a]] or [0]) for a in R})
    ntxt = (f"{ns[0]}" if len(ns) == 1 else f"{ns[0]}-{ns[-1]}") if ns else "0"

    def cell(p, row, n_arm):
        n, m, lo, up = row
        if m is None:
            return f"p{p + 1} -"
        return (f"p{p + 1} {m:+.4f} " + (f"[{lo:+.4f},{up:+.4f}]" if lo is not None else "[-]")
                + (f" (n={n})" if n != n_arm else ""))

    print()
    if rnph > 1:
        ph_head = (f"{rnph} phases, DATA_STREAM_BYTES={total} cut into equal byte ranges (N from {nph_src}), each "
                   f"flush placed by its run's per-flush bytes")
    elif no_ph:
        # A RUN WITHOUT ITS FLUSH BYTES CANNOT BE CUT INTO PHASES, and the pairing needs every run read
        # the same way: the rule then reads the whole run as one phase, and says so.
        ph_head = ("the WHOLE RUN as a single phase, because the per-flush bytes (run.py --flush-bytes) are "
                   "absent for " + ", ".join(no_ph[:6]) + (f" and {len(no_ph) - 6} more" if len(no_ph) > 6 else ""))
    else:
        ph_head = f"a single phase ({nph_src} gives 1)"
    print(f"=== THE ε RULE (Proposal 05 O14, O2): ε = {eps:g} bits/byte; incumbent {INC[1:]} (the interim "
          f"default); endpoint prequential bits/byte per phase: {ph_head} ===")
    print(f"  d = arm - k0 per phase, paired over seeds: mean [lower bound at t(1 - a/{rnph}) with Holm's a across "
          f"the cadences, one-sided 95% upper bound]; FAIL if a lower bound > ε, PASS if every upper bound <= "
          f"ε, else UNRESOLVED (always at n < 2)")
    rule_rows = []
    for arm in ACT:
        if arm not in ACTED:
            if any(wr(arm, s) is not None for s in seeds):
                print(f"  {arm:<6} NO ACT FIRED at any seed: the run is too short for this cadence to act, so it "
                      f"is the control under another name -- no evidence either way, not a pass")
                rule_rows.append(f"  {arm}: NO ACT FIRED at any seed -- no evidence either way, not a pass")
            continue
        r = R[arm]
        n_arm = max([n for n, _, _, _ in r["phases"]] or [0])
        body = " ".join(cell(p, row, n_arm) for p, row in enumerate(r["phases"]))
        line = (f"  {arm} n={n_arm} a={r['level']:.3g}: {body} -> {r['verdict']}"
                + (f" ({r['note']})" if r["note"] else ""))
        print(line)
        rule_rows.append(line)
    for c, (n, m, up, b, level) in sorted(B.items()):
        line = (f"  {c} - {INC} whole run: mean {m:+.4f}, one-sided {100 * (1 - level):.3g}% upper "
                + (f"{up:+.4f}" if up is not None else "- (n < 2)") + f" (n={n}): "
                + ("below 0, significantly better" if b else "not below 0"))
        print(line)
        rule_rows.append(line)
    if fb_off:
        line = (f"  !! per-flush bytes do not sum to loop.bytes_scored in {len(fb_off)} run(s), so a phase's "
                f"bits/byte is over other bytes than the whole run's: {', '.join(fb_off[:4])}")
        print(line)
        rule_rows.append(line)

    # M AND THE PER-ARM MEANS: REPORTED, AND THEY DECIDE NOTHING (O14). 03b's per-seed margin rule failed
    # a harmless 3000 about 30% of the time at 3 seeds by simulation (revise/o11_15.py).
    M = [abs(runs[("k0", s)]["bpb"] - runs[("k0_nuis", s)]["bpb"]) for s in seeds
         if runs.get(("k0_nuis", s), {}).get("bpb") is not None]
    margin = max(M) if M else None
    print()
    mline = (f"M = {margin:.5f} bits/byte (max over {len(M)} seed(s) |k0 - k0_nuis|)" if M else
             "M cannot be formed: no paired k0 / k0_nuis seeds")
    print(f"=== REPORTED, DECIDES NOTHING (O14): {mline} ===")
    means = []
    for arm in ACT + CD:
        d = {s: wr(arm, s) - wr("k0", s) for s in seeds if wr(arm, s) is not None}
        if not d:
            continue
        mean_ = sum(d.values()) / len(d)
        cd_ = arm in CD
        parent = arm.split("_cd")[0]
        dp = [wr(arm, s) - wr(parent, s) for s in d if wr(parent, s) is not None] if cd_ else []
        # THE COOLDOWN ARM IS READ BESIDE THE RULE (C13): it prices the blackout, it is not a cadence.
        print(f"  {arm:<6} - k0 per seed: " + "  ".join(f"s{s} {x:+.5f}" for s, x in sorted(d.items()))
              + f"   mean {mean_:+.5f}" + (f"   vs {parent} {sum(dp) / len(dp):+.5f}" if dp else "")
              + (f"   (FAB_COOLDOWN={arm.split('_cd')[1]}: beside the rule, not a ship candidate)" if cd_ else ""))
        means.append(f"{arm} - k0 mean {mean_:+.5f} over {len(d)} seed(s)"
                     + (f", vs {parent} {sum(dp) / len(dp):+.5f}" if dp else "") + (" (beside the rule)" if cd_ else ""))
    print()
    tail_ = f" (ε {eps:g} bits/byte, n {ntxt} seed(s))"
    if kind == "undecided":
        decision = ("UNDECIDED -- no cadence acted in these runs; raise WINDOWS past the first act "
                    "(minting starts near window 120-200, the first act follows at the cadence)")
    elif kind == "escalate":
        decision = (f"ESCALATE: every cadence FAILs against k0 by the ε rule; the act stays ON at {INC[1:]} until "
                    f"the owner answers; the remedy arms run next (register O14)" + tail_)
    elif kind == "replace":
        decision = f"TOK_RETOK_EVERY ships {pick[1:]}, replacing the incumbent {INC[1:]}: {why}" + tail_
    else:
        decision = (f"TOK_RETOK_EVERY stays {INC[1:]} (the incumbent; 0 is never shipped by the rule): {why}"
                    + tail_)
    print(f"=== DECISION: {decision} ===")
    verdicts = rule_rows + [f"reported, decides nothing (O14): {mline}"] + [f"  {x}" for x in means]
    print("    label: B-provisional -- provisional until SR0's held-out worst-area re-read passes "
          "(register note retok fleet (3))"
          + ("; pre-Levels -- re-run the k0 vs chosen-cadence pair after Levels (C12)" if "pre-Levels" in labels
             else "; Levels unrecorded (SUMMARY.txt predates the record)" if "Levels unrecorded" in labels else ""))

    # ---------------------------------------------------------------- rates
    def per_arm(arm):
        return [(s, v) for (n, s), v in sorted(runs.items()) if n == arm]

    k0x = {s: v["secs"] / v["bytes"] for s, v in per_arm("k0") if v["secs"] and v["bytes"]}
    # THE ACT'S COST IS ITS OWN SECONDS, NOT ITS DISTANCE FROM k0 (2026-09-27, build 1.5's review). With
    # kept checkpoints the k0 family saves every KEEP_EVERY windows INSIDE its loop time, and the act
    # arms only after it (the final save), so no arm here is the plain-text rate and an act arm's
    # per-byte time against k0 is mostly k0's saves: on CPU at 200 windows k40 read -19.6% against k0
    # while its acts and their MEM re-cuts took 0.15% of its loop time. The act's cost is
    # loop.act_seconds + loop.act_remap_seconds over the arm's own loop time; the k0 figure is kept,
    # and qualified wherever k0 saved.
    saves = KEPT_ON == "ON"
    rate_rows, rate_short = [], []
    for arm in ORDER + (["k0_rerun"] if "k0_rerun" in names else []):
        rs = per_arm(arm)
        wps = [v["win"] / v["secs"] for _, v in rs if v["win"] and v["secs"]]
        bps = [v["bytes"] / v["secs"] for _, v in rs if v["bytes"] and v["secs"]]
        wall = [done[f"{arm}.s{s}"][1] for s, _ in rs if f"{arm}.s{s}" in done]
        cost = [v["secs"] / v["bytes"] / k0x[s] - 1.0 for s, v in rs
                if arm not in ("k0", "k0_nuis", "k0_rerun") and s in k0x and v["secs"] and v["bytes"]]
        own = [((fnum(v["r"].get("loop.act_seconds")) or 0.0) + (fnum(v["r"].get("loop.act_remap_seconds")) or 0.0))
               / v["secs"] for _, v in rs if fnum(v["r"].get("loop.act_seconds")) is not None and v["secs"]]
        if not wps:
            rate_rows.append(f"  {arm:<12} no '=== N windows ... in Xs' line in any log")
            rate_short.append(f"  {arm}: no rate")
            continue
        fam = arm in ("k0", "k0_nuis", "k0_rerun") and saves
        rate_rows.append(
            f"  {arm:<12} windows/s {mean(wps):.2f} [{min(wps):.2f}-{max(wps):.2f}]  bytes/s {mean(bps) or 0:.0f}  "
            f"wall {fmt(mean(wall), '.0f')} s  n={len(wps)}"
            + (f"  act + MEM re-cut {100 * mean(own):.2f}% of loop time (loop.act_seconds + act_remap_seconds: "
               f"the act's cost)" if own else "")
            + (f"  per-byte loop time vs k0 {100 * mean(cost):+.1f}%"
               + (" (k0's time includes its periodic saves: not the act's cost)" if saves else "") if cost else "")
            + ("  (includes its periodic saves)" if fam else ""))
        rate_short.append(f"  {arm} {mean(wps):.2f} w/s [{min(wps):.2f}-{max(wps):.2f}] {mean(bps) or 0:.0f} B/s"
                          + (f", act + MEM re-cut {100 * mean(own):.2f}% of loop" if own else "")
                          + (f", per-byte time vs k0 {100 * mean(cost):+.1f}%" + (" (k0 saves)" if saves else "")
                             if cost else "")
                          + (" (with saves)" if fam else ""))
    tw = sum(v["win"] for v in runs.values() if v["win"])
    fin = re.search(r"^---- fleet finished in \d+ min \((\d+) s\)", S, re.M)
    cal = re.search(r"^=== calibration: PAR=(\d+) \(aggregate ([\d.]+) windows/s", S, re.M)
    eta = re.search(r"^=== ETA: about ([\d.]+) h for ([\d,]+) windows at ([\d.]+) windows/s aggregate", S, re.M)
    par = (re.findall(r"^=== \d+ run\(s\), (\d+) at a time", S, re.M) or ["?"])[-1]
    agg = []
    if fin and int(fin.group(1)) > 0:
        wall_s = int(fin.group(1))
        agg.append(f"  aggregate: {tw:,} windows in {wall_s} s of fleet wall at PAR {par} = {tw / wall_s:.2f} windows/s"
                   + (f" (calibrated {float(cal.group(2)):.2f} at PAR {cal.group(1)}: measured/calibrated "
                      f"{tw / wall_s / float(cal.group(2)):.2f})" if cal and float(cal.group(2)) > 0 else ""))
        if eta and float(eta.group(3)) > 0:
            est = int(eta.group(2).replace(",", "")) / float(eta.group(3))
            ratio = wall_s / est if est > 0 else float("nan")
            agg.append(f"  ETA against wall: estimated {est:.0f} s ({eta.group(2)} windows at {eta.group(3)} "
                       f"windows/s), took {wall_s} s: {ratio:.2f}x")
            if ratio > 1.5:
                calw = sget(r"^=== plan: .*?CAL_WINDOWS (\d+)") or "?"
                agg.append(f"  LOW-GPU-WORLD-ETA: the ETA missed the wall by {ratio:.2f}x (> 1.5x) calibrated on "
                           f"{calw} windows: raise EXP=world's default CAL_WINDOWS to >= 520 "
                           f"(FAB_MANAGE_EVERY + 20)")
        else:
            agg.append("  ETA against wall: SUMMARY.txt holds no ETA line (PAR set by hand and no smoke rate)")
    else:
        agg.append(f"  aggregate: {tw:,} windows; no fleet wall time in SUMMARY.txt (the fleet did not finish there)")
    cores = re.search(r"^=== (\d+) CPU core\(s\), (\d+) GPU\(s\), device=(\w+)", S, re.M)
    gpu = (re.findall(r"^\s+\d+, ([^,\n]+), \d+ MiB, \d+ MiB\s*$", S, re.M) or ["no GPU listed"])[0].strip()
    card = (f"  recorded on: {gpu}, PAR {par}, MPS {'on' if 'CUDA MPS started' in S else 'off'}, "
            f"NCPU {cores.group(1) if cores else '?'}")
    print()
    print("=== RATES (post-fix rate at the retok shape; PENDING-GPU-THROUGHPUT-REBASELINE) ===")
    print("  per run: windows/s = N / X and bytes/s = loop.bytes_scored / X from each log's '=== N windows ... "
          "in Xs' (the loop's own time, startup excluded); wall = _done.txt secs; mean [min-max] over seeds")
    if saves:
        print("  k0, k0_nuis and k0_rerun save every KEEP_EVERY windows inside X, the act arms only after it: no arm "
              "is the plain-text rate, and the act's cost is its own seconds, not its distance from k0")
    for l in rate_rows + agg + [card]:
        print(l)

    # ---------------------------------------------------------------- secondaries
    NEW13 = ("fab.blackout_windows", "tok.mint_wait_windows", "loop.act_seconds", "tok.bpt_tail")
    have13 = {k for v in runs.values() for k in v["r"] if k in NEW13}
    have_fb = any(v["fbytes"] for v in runs.values())
    # WHAT THE TREE HAS IS RECORDED AT LAUNCH, AND ONLY THE TREE CAN SAY A KEY IS MISSING (2026-09-27,
    # build 1.5's review). Under DID IT FIRE an ABSENT key is UNREACHABLE: tok.bpt_tail on a fleet where
    # no act fired, fab.blackout_windows with no stamp or at FAB_COOLDOWN=0. This line read every such
    # absence as "§8 1.3 not in this tree", on a tree that holds it. A key the tree has and no log
    # printed is now "unreachable in these runs", with the reason its seeding gives.
    rec = re.search(r"^=== §8 1\.3 in this tree: counters (.*?); run\.py --flush-bytes (yes|no)\s*$", S, re.M)
    tree13 = None if rec is None else set(rec.group(1).split()) & set(NEW13)
    missing = [k for k in NEW13 if k not in have13]
    WHY = {"fab.blackout_windows": "no run stamped, or FAB_COOLDOWN=0 / FAB_GROW=0",
           "tok.mint_wait_windows": "no run both mints and acts",
           "loop.act_seconds": "no run acts at TOK_MODE=online",
           "tok.bpt_tail": "no act spliced"}
    unreach = []
    if tree13 is None:
        # A SUMMARY.txt FROM BEFORE THE RECORD: the logs alone cannot tell missing from unreachable.
        absent_head = "absent from every log (not in this tree, or unreachable here: SUMMARY.txt predates the tree record)"
        absent = missing + ([] if have_fb else ["per-flush bytes (run.py --flush-bytes)"])
    else:
        absent_head = "absent (§8 1.3 not in this tree)"
        absent = ([k for k in missing if k not in tree13]
                  + ([] if have_fb or rec.group(2) == "yes" else ["per-flush bytes (run.py --flush-bytes)"]))
        unreach = ([f"{k} ({WHY[k]})" for k in missing if k in tree13]
                   + (["per-flush bytes (no run wrote its --flush-bytes file)"] if not have_fb and rec.group(2) == "yes"
                      else []))

    # fab.blackout_windows IS ABSENT ON A RUN NO STAMP REACHED (2026-09-27, build 1.3's review,
    # Q-RUN-17): FAB seeds it at the first stamp. So beside a present fab.shift_notifications of 0 it
    # is 0 windows blacked out, wherever the tree has the key -- by the record, or failing that
    # because some run printed it.
    bw_known = "fab.blackout_windows" in have13 or "fab.blackout_windows" in (tree13 or ())

    def blackout(v):
        x = fnum(v["r"].get("fab.blackout_windows"))
        if x is None and bw_known and fnum(v["r"].get("fab.shift_notifications")) == 0:
            return 0.0
        return x

    def cm(arm, key):
        return mean([fnum(v["r"].get(key)) for _, v in per_arm(arm)])

    def share(arm, key, den="win"):
        return mean([fnum(v["r"].get(key)) / v[den] for _, v in per_arm(arm)
                     if fnum(v["r"].get(key)) is not None and v[den]])

    # THE BLACKOUT, SPLIT WHERE THE POOL FILLS (O14, "Holds meanwhile"; 2026-09-27). The 2026-09-24
    # archive's pool reached FAB_SLOTS in 20 of 21 runs (median window 6,501), and past that growth is
    # held by the ceiling whatever the acts do, so an unsplit alarm would blame the acts for it. The
    # fill is the first progress line with n_live >= FAB_SLOTS; a run that never fills is all before.
    # fab.blackout_windows is CUMULATIVE and no log carries a per-window series, so the split is an
    # ESTIMATE built from the act windows: each act blacks out up to FAB_COOLDOWN windows from its window
    # (a later act restarting it, as grow_check's latest stamp does), those windows are counted either
    # side of the fill, and the counter is split in that proportion. Each part is read as a share of
    # its own windows -- the before-part of the windows before the fill -- and C13's alarm reads only
    # the before-part.
    def cooldown_of(arm, v):
        if v["cooldown"]:
            return v["cooldown"]
        m_ = re.fullmatch(r"k\d+_cd(\d+)", arm) or re.search(r"(?:^| )FAB_COOLDOWN=(\d+)", EXTRA)
        return int(m_.group(1)) if m_ else 400

    def cover(arm, v):
        """The windows the acts can black out: [act, act + cooldown) each, merged, clipped at the run's end."""
        cdn, end = cooldown_of(arm, v), v["win"] or max(v["at"] or [0])
        ivs = []
        for a_ in sorted(v["at"]):
            lo, hi = a_, min(a_ + cdn, end)
            if hi <= lo:
                continue
            if ivs and lo <= ivs[-1][1]:
                ivs[-1][1] = max(ivs[-1][1], hi)
            else:
                ivs.append([lo, hi])
        return ivs

    def split(arm, v):
        """(before, after, how) in windows of fab.blackout_windows either side of the fill."""
        bw_ = blackout(v)
        if bw_ is None:
            return None, None, None
        if bw_ == 0:
            return 0.0, (None if v["fill"] is None else 0.0), "zero"
        if v["fill"] is None:
            return bw_, None, "never full"
        ivs = cover(arm, v)
        tot = sum(hi - lo for lo, hi in ivs)
        if tot <= 0:
            # A COUNT WITH NO ACT WINDOW TO PLACE IT is left whole before the fill: the alarm reads more.
            return bw_, None, "unsplit"
        pre = sum(max(0, min(hi, v["fill"]) - lo) for lo, hi in ivs)
        return bw_ * pre / tot, bw_ * (tot - pre) / tot, "estimated"

    def parts(arm, v):
        """(before share, after share, how): each part over its own windows; after is None when never full."""
        b_, a_, how = split(arm, v)
        if b_ is None or not v["win"]:
            return None, None, how
        f_ = v["fill"] if v["fill"] is not None else v["win"]
        pre, post = min(f_, v["win"]), v["win"] - min(f_, v["win"])
        return (b_ / pre if pre else 0.0), (a_ / post if a_ is not None and post else None), how

    # WITHOUT THE COUNTER THE ALARM READS AN UPPER BOUND ON THE BEFORE-PART, BUILT FROM THE ACTS BEFORE
    # THE FILL (2026-09-27, the split's review). It was fab.shift_notifications x cooldown over the
    # windows before the fill, which charged the acts AFTER the fill to the before-part: a fleet whose
    # pool was full at window 101 and whose every act came later read 100% before, and alarmed where the
    # whole-run bound it replaced did not. The bound is now the windows of the acts' cover (above) that
    # fall before the fill, as a share of the windows before it. A stamp no act line places (an epoch
    # roll; fab.shift_notifications above the act lines) is charged a whole cooldown before the fill, and
    # only a run with no act window at all falls back to every notification x cooldown.
    def before_bound(arm, v):
        """(share, how): an UPPER BOUND on the before-part's share of the windows before the fill."""
        n_ = fnum(v["r"].get("fab.shift_notifications"))
        if not v["win"]:
            return None, None
        pre = v["fill"] if v["fill"] is not None and v["fill"] < v["win"] else v["win"]
        if v["at"]:
            b_ = sum(max(0, min(hi, pre) - lo) for lo, hi in cover(arm, v))
            b_ += max(0, (n_ or 0) - len(v["at"])) * cooldown_of(arm, v)
            return min(1.0, b_ / pre), "acts"
        if n_ is None or not v["cooldown"]:
            return None, None
        return min(1.0, n_ * v["cooldown"] / pre), "notifications"

    sec_rows, sec_short, phase_rows, alarms, split_short, unsplit, any_est = [], [], [], [], [], [], False
    any_bb = False
    for arm in ORDER:
        rs = per_arm(arm)
        acts = cm(arm, "loop.acts")
        # EVERY SEED, the unstamped ones at 0 (blackout above), so the share is not over the stamped alone.
        bw = mean([blackout(v) / v["win"] for _, v in rs if blackout(v) is not None and v["win"]])
        cdv = mean([v["cooldown"] for _, v in rs])
        # AN UPPER BOUND: each notification can black out at most one cooldown, and never more than
        # the whole run (a short run's cooldowns overlap and overrun its end).
        ub = mean([min(1.0, fnum(v["r"].get("fab.shift_notifications")) * v["cooldown"] / v["win"]) for _, v in rs
                   if fnum(v["r"].get("fab.shift_notifications")) is not None and v["cooldown"] and v["win"]])
        # ... AND OF THE BEFORE-PART (before_bound): the acts before the fill, not every notification.
        bb = [before_bound(arm, v) for _, v in rs]
        ubb, ubb_how = mean([b[0] for b in bb]), {b[1] for b in bb if b[1]}
        pt = [parts(arm, v) for _, v in rs]
        bwb, bwa = mean([p[0] for p in pt]), mean([p[1] for p in pt])
        est = any(p[2] == "estimated" for p in pt)
        any_est = any_est or est
        unsplit += [f"{arm}.s{s}" for (s, _), p in zip(rs, pt) if p[2] == "unsplit"]
        fills = sorted(v["fill"] for _, v in rs if v["fill"] is not None)
        nlv = [v["nlive"] for _, v in rs if v["nlive"] is not None]
        sls = sorted({v["slots"] for _, v in rs})
        full = (f"full (n_live >= FAB_SLOTS {'/'.join(map(str, sls))}) in {len(fills)}/{len(rs)} run(s)"
                + (f" from window {fills[0]}" + (f"-{fills[-1]}" if fills[-1] != fills[0] else "") if fills else ""))
        nltxt = (f"{mean(nlv):.0f} [{min(nlv):.0f}-{max(nlv):.0f}]" if nlv else "-")
        # WITHOUT THE COUNTER the row gives the before-part's upper bound, which the alarm then reads.
        bb_src = ("the act windows" if ubb_how == {"acts"} else "fab.shift_notifications" if ubb_how == {"notifications"}
                  else "the act windows, else fab.shift_notifications")
        bb_on = bwb is None and ubb is not None
        any_bb = any_bb or bb_on
        split_row = (
            f"  {'':<12} blackout {fmt(bwb and 100 * bwb, '.1f')}% of the windows before the pool fills"
            + (f" (no counter: at most {100 * ubb:.1f}% by {bb_src} x cooldown)" if bb_on else "") + ", "
            f"{fmt(bwa and 100 * bwa, '.1f')}% of those after" + (" (estimated from the act windows)" if est else "")
            + f"; pool {full}; n_live at the end {nltxt}")
        split_short.append(f"  {arm} before {fmt(bwb and 100 * bwb, '.1f')}%" + (f" (<= {100 * ubb:.1f}%)" if bb_on else "")
                           + f" / after {fmt(bwa and 100 * bwa, '.1f')}%"
                           + (" (est.)" if est else "") + f"; {full.replace('(n_live >= FAB_SLOTS', '(slots')}"
                           f"; n_live end {nltxt}")
        waited, wwin = cm(arm, "tok.mint_waited"), cm(arm, "tok.mint_wait_windows")
        ash, rsh = share(arm, "loop.act_seconds", "secs"), share(arm, "loop.act_remap_seconds", "secs")
        # MEM'S RE-CUT SHARE: the entries an act's remap changed, over the store's capacity (n_opened).
        ev, ent, slots = cm(arm, "store.n_remap_events"), cm(arm, "store.n_remapped_entries"), cm(arm, "store.n_opened")
        recut = ent / ev / slots if ev and ent is not None and slots else None
        nr = max([len(v["rise"]) for _, v in rs] or [0])
        rise = [mean([v["rise"][i] for _, v in rs if len(v["rise"]) > i]) for i in range(nr)]
        kind = next((v["rise_kind"] for _, v in rs if v["rise_kind"]), None)
        sec_rows.append(
            f"  {arm:<12} acts {fmt(acts, 'n')} (noop {fmt(cm(arm, 'loop.acts_noop'), 'n')}, tok.retok_noop "
            f"{fmt(cm(arm, 'tok.retok_noop'), 'n')}), replay record {fmt(acts + 1 if acts is not None else None, 'n')} "
            f"event(s); FAB grown regression {fmt(cm(arm, 'fab.grown_regression'), 'n')} / stall "
            f"{fmt(cm(arm, 'fab.grown_stall'), 'n')}, births {fmt(cm(arm, 'fab.births'), 'n')}, blackout-suppressed "
            f"regression {fmt(cm(arm, 'fab.growth_blackout_suppressed.regression'), 'n')} / stall "
            f"{fmt(cm(arm, 'fab.growth_blackout_suppressed.stall'), 'n')}")
        sec_rows.append(
            f"  {'':<12} blackout {fmt(bw and 100 * bw, '.1f')}% of windows (fab.blackout_windows; upper bound "
            f"fab.shift_notifications x cooldown {fmt(cdv, '.0f')} / windows = {fmt(ub and 100 * ub, '.1f')}%); "
            f"mint wait {fmt(wwin / waited if waited else None, '.1f')} windows x {fmt(waited, 'n')} id(s); "
            f"act {fmt(ash and 100 * ash, '.2f')}% of loop time (MEM re-cut {fmt(rsh and 100 * rsh, '.2f')}%); "
            f"MEM re-cut {fmt(recut and 100 * recut, '.1f')}% of the store's slots per act; tok.bpt_tail "
            f"{fmt(cm(arm, 'tok.bpt_tail'), '.4f')}")
        sec_rows.append(split_row)
        if rise:
            sec_rows.append(f"  {'':<12} bytes/token rise per act ("
                            + ("the tail's, before -> after" if kind == "tail" else "whole-stream ids A/B - 1")
                            + "): " + " ".join(f"{100 * x:+.1f}%" for x in rise))
        sec_short.append(
            f"  {arm} acts {fmt(acts, 'n')} noop {fmt(cm(arm, 'loop.acts_noop'), 'n')}; grown reg "
            f"{fmt(cm(arm, 'fab.grown_regression'), 'n')}/stall {fmt(cm(arm, 'fab.grown_stall'), 'n')}; blackout "
            f"{fmt(bw and 100 * bw, '.1f')}% (<= {fmt(ub and 100 * ub, '.1f')}%); act {fmt(ash and 100 * ash, '.2f')}% "
            f"of loop; MEM re-cut {fmt(recut and 100 * recut, '.1f')}%/act; bpt rise/act "
            + (" ".join(f"{100 * x:+.1f}" for x in rise[:8]) + ("..." if len(rise) > 8 else "") + "%" if rise else "-"))
        ph = [ph_of[(arm, s)] for s, _ in rs]
        ph = [p for p in ph if p]
        if ph:
            phase_rows.append((arm, " ".join(fmt(mean([p[k] for p in ph]), '.4f') for k in range(nph)), len(ph)))
        if arm in ACT:
            # C13 READS ONLY THE PART BEFORE THE POOL FILLS (O14): its share of the windows before the fill.
            s_ = bwb if bwb is not None else ubb
            if s_ is not None and s_ > 0.20:
                fastest = min(ACT, key=lambda x: int(x[1:]))
                follow = (f"the cooldown arm {' '.join(CD)} is in this fleet: read its rows" if CD else
                          f"re-run with COOLDOWN_ARM=100 (adds {fastest}_cd100, FAB_COOLDOWN=100 at the fastest "
                          f"cadence)")
                alarms.append(f"  BLACKOUT ALARM (C13): {arm} blacks out {100 * s_:.1f}% of its windows before the "
                              f"pool fills" + (f" (upper bound by {bb_src} x cooldown)" if bwb is None else "")
                              + f", above 20%: {follow}")
    print()
    print("=== SECONDARIES (per arm, mean over seeds; beside the rule, never in it -- register note secondaries) ===")
    for l in sec_rows:
        print(l)
    if phase_rows:
        print(f"  by phase: the stream's {nph} equal byte ranges of DATA_STREAM_BYTES={total} (data_plan's "
              f"bounds; N from {nph_src}), each flush placed by its first byte:")
        for arm, vals, n in phase_rows:
            print(f"  {arm:<12} bits/byte by phase: {vals}  ({n} seed(s))")
    est_note = (["  the blackout split is an ESTIMATE built from the act windows: fab.blackout_windows is "
                 "cumulative and no log carries a per-window series, so each act is taken to black out up to "
                 "FAB_COOLDOWN windows from its window (a later act restarting it), those windows are counted "
                 "either side of the first progress line with n_live >= FAB_SLOTS, and the counter is split in "
                 "that proportion"] if any_est else [])
    unsplit_note = ([f"  blackout unsplit (a count and no act window to place it; all of it read as before the "
                     f"fill): {' '.join(unsplit[:8])}" + (" ..." if len(unsplit) > 8 else "")] if unsplit else [])
    absent_lines = (([f"  {absent_head}: {', '.join(absent)}"] if absent else [])
                    + ([f"  unreachable in these runs (ABSENT from every log; the tree has them): {', '.join(unreach)}"]
                       if unreach else []))
    for l in est_note + unsplit_note + absent_lines + alarms:
        print(l)

    # ---------------------------------------------------------------- kept checkpoints
    kd = os.path.join(OUT, "ckpt", "keep")
    kfiles = sorted(glob.glob(os.path.join(kd, "*.kept.txt")))
    rows = []
    for f in kfiles:
        rows += [l for l in rd(f).splitlines() if l.strip()]
    if kfiles:
        with open(os.path.join(OUT, "KEPT.txt"), "w") as fh:
            fh.write("\n".join(rows) + "\n")
    elif os.path.exists(os.path.join(OUT, "KEPT.txt")):
        os.remove(os.path.join(OUT, "KEPT.txt"))          # never one this ckpt/keep does not hold
    # AN INDEX THAT REFUSED says so in its log's "!!" line (keep_index: a keep directory stamped by
    # another launch), and the block carries it: those saves were left unindexed, never dropped.
    refused = [l.strip() for f in sorted(glob.glob(os.path.join(kd, "*.index.log")))
               for l in rd(f).splitlines() if l.startswith("!!")]
    kept_rows, kept_short = [], []
    if not os.path.isdir(os.path.join(OUT, "ckpt")):
        kept_rows.append("  none: no ckpt/ directory (KEEP_CKPT was off)")
        kept_short.append("KEPT: none (KEEP_CKPT off)")
    else:
        ks = {}
        for l in rows:
            m = re.match(r"^(\S+)\.s(\d+)\.w(\d+) step=(\d+) reason=(\S+) merges=(\S+) entries=(\S+) "
                         r"(coherent|INCOHERENT)", l)
            if m and m.group(1) == "k0":
                ks.setdefault(int(m.group(2)), []).append((int(m.group(4)), m.group(8) == "coherent"))
        cov_tot, short_bad = {}, []
        for s in sorted({s for (n, s) in runs if n == "k0"} | set(ks)):
            got = sorted(ks.get(s, []))
            steps = {st for st, _ in got}
            cov = []
            for arm in ACT + CD:
                aw = runs.get((arm, s), {}).get("at") or []
                if (arm, s) in runs:
                    hit = sum(1 for x in aw if x in steps)
                    cov.append(f"{arm} {hit}/{len(aw)}")
                    t_ = cov_tot.setdefault(arm, [0, 0]); t_[0] += hit; t_[1] += len(aw)
            inc = [st for st, ok in got if not ok]
            miss = [c_ for c_ in cov if c_.split()[1].split("/")[0] != c_.split()[1].split("/")[1]]
            if inc or miss:
                short_bad.append(f"  k0.s{s}: " + "; ".join(
                    ([f"INCOHERENT at {' '.join('w%d' % x for x in inc)}"] if inc else [])
                    + ([f"act windows not kept: {', '.join(miss)}"] if miss else [])))
            kept_rows.append(f"  k0.s{s}: {len(got)} kept" + (f", w{got[0][0]}-w{got[-1][0]}" if got else "")
                             + (", all coherent" if got and not inc else "")
                             + (f", INCOHERENT at {' '.join('w%d' % x for x in inc)}" if inc else "")
                             + ("; act windows covered: " + ", ".join(cov) if cov else ""))
        seen, du = set(), 0
        for root, _, fs in os.walk(os.path.join(OUT, "ckpt")):
            for fn in fs:
                try: st = os.lstat(os.path.join(root, fn))
                except OSError: continue
                if (st.st_dev, st.st_ino) not in seen:
                    seen.add((st.st_dev, st.st_ino)); du += st.st_size
        nk = sum(len(v) for v in ks.values())
        ninc = sum(1 for v in ks.values() for _, ok in v if not ok)
        kept_rows.append(f"  disk: {du / 1e9:.2f} GB under {os.path.join(OUT, 'ckpt')} (hard links counted once)")
        kept_rows += [f"  INDEX REFUSED: {l}" for l in refused]
        first = next(((s, st) for s in sorted(ks) for st, ok in sorted(ks[s]) if ok), None)
        # THE RESUME LINE CARRIES THE RUN'S OWN SEED, DEVICE AND STREAM (2026-09-27, build 1.5's review):
        # run_job sets RUN_SEED, RUN_DEVICE and DATA_STREAM_BYTES on every run and EXTRA carries none of
        # them, so the line without them was refused -- on CPU at 200 windows the segmentation rebuilt
        # from the checkpoint's log held 635 windows where the parent's epoch held 199.
        dev = cores.group(3) if cores else "cuda"
        resume = (f"CKPT_RESUME={os.path.join(kd, f'k0.s{first[0]}.w{first[1]}')} CKPT_DIR=<NEW dir> "
                  f"OMP_NUM_THREADS=1 RUN_SEED={first[0]} RUN_DEVICE={dev} DATA_STREAM_BYTES={total or '?'} "
                  f"TOK_RETOK_EVERY=0" + (f" {EXTRA}" if EXTRA.strip() else "") + " python3 run.py") if first else None
        if first:
            kept_rows.append(f"  resume one: {resume} -- a NEW CKPT_DIR, never a kept copy")
        kept_short.append(f"KEPT: {nk} copies of {len(ks)} k0 run(s)"
                          + (", all coherent" if nk and not ninc else f", {ninc} INCOHERENT" if ninc else "")
                          + (", act windows covered " + ", ".join(f"{a} {h}/{n}" for a, (h, n) in cov_tot.items())
                             if cov_tot else "") + f"; ckpt/ {du / 1e9:.2f} GB")
        kept_short += short_bad[:4] + ([f"  ... {len(short_bad) - 4} more k0 run(s): KEPT.txt"] if len(short_bad) > 4 else [])
        kept_short += [f"  INDEX REFUSED: {l}" for l in refused[:2]] + (
            [f"  ... {len(refused) - 2} more refused index(es): ckpt/keep/*.index.log"] if len(refused) > 2 else [])
        if first:
            kept_short.append(f"  resume one: {resume}")
    print()
    print("=== KEPT CHECKPOINTS (k0's periodic saves, hard-linked aside: the spike test's maturity-matched "
          "control, note retok fleet (1), (4)) ===")
    for l in kept_rows:
        print(l)

    # ---------------------------------------------------------------- the block
    arms_t = ORDER
    allseeds = sorted({s for (n, s) in runs if n in arms_t})
    wd = {a: max(9, len(a)) for a in arms_t}
    diffs = ACT + CD
    t_head = ("bits/byte per seed  " + " ".join(f"{a:>{wd[a]}}" for a in arms_t) + "  |k0-nuis|"
              + "".join(f" {a + '-k0':>{max(10, len(a) + 3)}}" for a in diffs))
    t_rows = []                                   # (seed, row, flagged)
    # EACH CADENCE'S LARGEST (arm - k0), the seed that most drives its upper bound up.
    worst = set()
    for a in ACT:
        ds_ = {s: wr(a, s) - wr("k0", s) for s in allseeds if wr(a, s) is not None and wr("k0", s) is not None}
        if ds_:
            worst.add(max(ds_, key=lambda s: (ds_[s], -s)))
    for s in allseeds:
        g = lambda a: runs.get((a, s), {}).get("bpb")
        cells = " ".join(f"{fmt(g(a), '.5f'):>{wd[a]}}" for a in arms_t)
        nu = abs(g("k0") - g("k0_nuis")) if g("k0") is not None and g("k0_nuis") is not None else None
        ds = "".join(f" {fmt(g(a) - g('k0') if g(a) is not None and g('k0') is not None else None, '+.5f'):>{max(10, len(a) + 3)}}"
                     for a in diffs)
        # A FLAGGED ROW is one a reader looks for first: it sets M, it holds a cadence's largest difference
        # from k0, or a reading is missing. The condensed table keeps these first.
        flag = any(g(a) is None for a in arms_t) or (margin is not None and nu == margin) or s in worst
        t_rows.append((s, f"  s{s:<16} {cells}  {fmt(nu, '.5f'):>9}{ds}", flag))

    def table(n=None):
        """The header and every seed's row; given n lines, the flagged rows first, then the others in
        seed order, and one line counting the rows left out (every value is in ANALYSIS.txt's RUNS)."""
        if n is None or len(t_rows) + 1 <= n:
            return [t_head] + [row for _, row, _ in t_rows]
        room = max(0, n - 2)
        keep = [s for s, _, f in t_rows if f][:room]
        keep += [s for s, _, f in t_rows if not f][:room - len(keep)]
        hid = [f for s, _, f in t_rows if s not in keep]
        nf = sum(hid)
        return ([t_head] + [row for s, row, _ in t_rows if s in keep]
                + [f"  ... {len(hid)} more seed row(s)"
                   + (f", {nf} of them flagged (setting M, holding a cadence's largest difference or missing a "
                      f"reading)" if nf else ", none setting M, holding a cadence's largest difference or missing "
                      "a reading")
                   + ": in ANALYSIS.txt's RUNS"])
    rr = [f"k0_rerun: k0 seed 0 twice, |diff| {rerun:.3g} bits/byte" + (" (BIT-EXACT)" if rerun == 0 else "")
          if rerun is not None else "k0_rerun: no pair (k0.s0 or k0_rerun.s0 has no reading)"]
    verdict = [f"RULE (O14, O2): ε {eps:g} bits/byte, incumbent {INC[1:]}; per phase ({rnph}"
               + (", the whole run: per-flush bytes absent" if no_ph else "") + f"), arm - k0 paired over seeds: "
               f"mean [lower at t(1 - a/{rnph}), Holm a; one-sided 95% upper]"]
    verdict += verdicts + [f"DECISION: {decision}  [{', '.join(labels)}]"]
    rates = ["RATES (post-fix rate at the retok shape; mean [min-max] over seeds"
             + ("; the k0 family's loop time includes its periodic saves" if saves else "") + "):"]
    agg_short = [l for l in agg] + [card]
    sec_head = ["SECONDARIES (mean over seeds; beside the rule):"]
    sec_tail = unsplit_note + absent_lines + alarms
    bo_short = ([f"BLACKOUT SPLIT where n_live first reaches FAB_SLOTS (each part over its own windows; C13 reads the "
                 f"part before" + ("; ESTIMATED from the act windows x FAB_COOLDOWN, the counter being cumulative"
                                   if any_est else "")
                 + ("; no counter: <= is an upper bound, the act windows before the fill x FAB_COOLDOWN, or every "
                    "notification's where no act window is known" if any_bb else "") + "):"] + split_short)
    ph_short = [f"  bits/byte by phase ({nph} equal byte ranges), {arm}: {vals}" for arm, vals, _ in phase_rows]
    emit([
        ("head", head("retok", labels) + failures(runs, done), 0),
        ("per-seed rows", table, 0),
        ("verdict", rr + verdict, 0),
        ("rates", rates, 0), ("per-arm rates", rate_short, 2), ("aggregate", agg_short, 0),
        ("secondaries", sec_head, 0), ("per-arm secondaries", sec_short, 3), ("blackout split", bo_short, 2),
        ("phases", ph_short, 4),
        ("absent and alarm", sec_tail, 0),
        ("kept checkpoints", kept_short, 1),
        ("archive", [archive_line(archive)], 0),
    ])


# ------------------------------------------------------------------------------------------ wrap
def wrap(exp, archive):
    """EXP=world and world_epoch: the header, then ANALYSIS.txt from '=== RUNS ===' on. The run rows
    are what gets cut when the block is too long; the pairing and the decision never are."""
    txt = rd(os.path.join(OUT, "ANALYSIS.txt"))
    i = txt.find("=== RUNS ===")
    body = [l.rstrip() for l in (txt[i:].splitlines() if i >= 0 else
                                 ["(no analysis: ANALYSIS.txt holds no '=== RUNS ===')"])]
    runs_part, rest = body, []
    if "" in body:
        j = body.index("")
        runs_part, rest = body[:j], body[j:]
    rest = [l for k, l in enumerate(rest) if l or not k or rest[k - 1]]      # one blank between sections
    hd = head(exp) + failures({}, done_book())
    fixed = len(hd) + len(rest) + 1
    room = CAP - 2 - fixed
    if len(runs_part) > room:
        keep = max(1, room - 1)
        runs_part = runs_part[:keep] + [f"  ... {len(runs_part) - keep} more run row(s) in ANALYSIS.txt"]
    emit([("head", hd, 0), ("runs", runs_part, 0), ("analysis", rest, 0), ("archive", [archive_line(archive)], 0)])


# ------------------------------------------------------------------------------------------ fail
def fail(exp, archive, reason, logs):
    # A STOP IN THE ANALYSIS PHASE SAYS SO (2026-09-27 review): the analysis itself failed, or the shell
    # died in it, after every run had ended; STATE's phase (its last line) tells the two apart.
    phase = ""
    for ln in rd(os.path.join(OUT, "STATE")).splitlines():
        if ln.startswith("phase="):
            phase = ln[6:]
    lines = head(exp) + [f"STOPPED {'AT' if phase == 'analysis' else 'BEFORE'} THE ANALYSIS: {reason}"]
    for lg in logs:
        t = [x.rstrip()[:160] for x in rd(lg).splitlines() if x.strip()]
        lines += [f"--- {os.path.relpath(lg, OUT) if lg.startswith(OUT) else lg} (last 8 lines)"] + ["    " + x for x in t[-8:]]
    emit([("head", lines, 0), ("archive", [archive_line(archive)], 0)])


if MODE == "retok":
    retok(int(sys.argv[3]), sys.argv[4], float(sys.argv[5]), int(sys.argv[6]))
elif MODE == "wrap":
    wrap(sys.argv[3], sys.argv[4])
elif MODE == "fail":
    fail(sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6:])
PY
}

# ---------------------------------------------------------------- kept checkpoints (EXP=retok's k0)
# ONE LOOK: hard-link every COMPLETE save generation of the run's ring not yet kept. CKPT.save and
# TOK.save_vocabulary each write a .tmp and os.replace it, so a save is a new file under the same
# name, and spine/loop.py::_save calls save_vocabulary only after CKPT.save returned True -- so a
# generation is complete exactly when its vocabulary is no older than its checkpoint. Both ring
# generations are looked at, ckpt.pt with <dir>.dyntok.json and ckpt.pt.prev with
# <dir>.prev.dyntok.json (TOK rotates its file with CKPT's, 2026-09-26), so a save that a look
# missed is still taken as .prev at the next one. A copy is identified by size and nanosecond mtime,
# which a hard link shares and `cp -p` (the fallback where a link fails) preserves. A save that lands
# between the look and the link shows as a changed identity, and the half-taken copy is removed for
# the next look to take whole. The index below still checks every copy's merge count against its
# vocabulary, so a wrong pairing is flagged INCOHERENT, never kept silently.
keep_sweep() {  # ckdir keepdir tag
  local ck="$1" kd="$2" tag="$3" sfx c v kc mc mv have d n
  have=" $(stat -c '%s:%.9Y' "$kd/$tag".save[0-9]*/ckpt.pt "$kd/$tag".w[0-9]*/ckpt.pt 2>/dev/null | tr '\n' ' ') "
  for sfx in "" .prev; do
    c="$ck/ckpt.pt$sfx"; v="$ck$sfx.dyntok.json"
    kc=$(stat -c '%s:%.9Y' "$c" 2>/dev/null) || continue
    mv=$(stat -c '%.9Y' "$v" 2>/dev/null) || continue
    [[ "$have" == *" $kc "* ]] && continue
    mc=${kc#*:}
    (( ${mv/./} >= ${mc/./} )) || continue           # its vocabulary has not landed yet: mid-save
    n=1; while [[ -e "$kd/$tag.save$(printf %03d $n)" ]]; do n=$(( n + 1 )); done
    d="$kd/$tag.save$(printf %03d $n)"
    mkdir -p "$d" || continue
    ln "$c" "$d/ckpt.pt" 2>/dev/null || cp -p "$c" "$d/ckpt.pt" 2>/dev/null
    ln "$v" "$d.dyntok.json" 2>/dev/null || cp -p "$v" "$d.dyntok.json" 2>/dev/null
    if [[ "$(stat -c '%s:%.9Y' "$d/ckpt.pt" 2>/dev/null)" == "$kc" && "$(stat -c '%.9Y' "$d.dyntok.json" 2>/dev/null)" == "$mv" ]]; then
      have="$have$kc "
    else
      rm -rf "$d" "$d.dyntok.json"
    fi
  done
}
# THE WATCHER: a look every KEEP_POLL seconds until run_job drops the stop file, then a last look. At
# the fleet's cadence (1000 windows) saves are tens of seconds to minutes apart, and a 1 s poll costs
# a few stat calls. IT ALSO ENDS WHEN ITS run_job DOES (2026-09-27, build 1.5's review): the stop file
# was its only exit, and run_job writes it after its run returns, so a run_job that was killed (the
# fleet stopped by a signal, an OOM kill) left the watcher polling for ever. It is given run_job's pid,
# and when that is gone it takes a last look and returns; the copies it took are indexed by --analyze.
keep_watch() {  # ckdir keepdir tag [owner-pid]
  local stop="$2/.$3.stop" own="${4:-}"
  while :; do
    if [[ -e "$stop" ]] || { [[ -n "$own" ]] && ! kill -0 "$own" 2>/dev/null; }; then
      keep_sweep "$1" "$2" "$3"; rm -f "$stop"; return 0
    fi
    keep_sweep "$1" "$2" "$3"
    sleep "$KEEP_POLL"
  done
}
# THE INDEX, AFTER THE RUN: each copy is named for the step it holds, read off the file (never assumed
# from the cadence), and checked against its vocabulary (the checkpoint's TOK merge count against the
# file's entries, the pairing build_vocabulary refuses a resume on). The run's final save duplicates
# the ring's ckpt.pt and a repeated step duplicates a copy, so both are dropped. Kept files are made
# read-only, and <tag>.kept.txt lists every copy. Python from inside the keep directory with src/
# first on its path, as run.py arranges it: the repository root's memory.py shadows src/memory.
# A REPEATED STEP IS A DUPLICATE ONLY WITHIN ONE LAUNCH (2026-09-27, build 1.5's review). A fleet
# launched into an OUT that still held a previous fleet's copies found that fleet's k0.s0.w21 and
# deleted its own save at step 21 as "a duplicate step", keeping the old copy -- trained on another
# stream, perhaps another commit -- under the name. A launch now moves a previous fleet aside whole
# (below), and stamps each keep directory with its launch time in .fleet; given that stamp, the index
# refuses a directory stamped by another launch, and indexes nothing and drops nothing there. A keep
# directory with no .fleet (a fleet launched before the stamp) is indexed as before.
keep_index() {  # keepdir tag [launch stamp]
  ( cd "$1" && python3 - "$PWD" "$2" "$ROOT_DIR" "${3:-}" <<'PY'
import glob, json, os, stat, sys
kd, tag, root, stamp = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
sys.path[:] = [p for p in sys.path if p and os.path.abspath(p) != os.path.abspath(root)]
sys.path.insert(0, os.path.join(root, "src"))
try:
    with open(os.path.join(kd, ".fleet")) as fh:
        owner = fh.read().strip()
except OSError:
    owner = ""
if stamp and owner and owner != stamp:
    print(f"!! {tag}: {kd} is stamped by the fleet launched {owner}, not by this one ({stamp}): nothing "
          f"indexed and nothing dropped; this run's saves are left as {tag}.saveNNN")
    sys.exit(1)
import torch


def load(path):
    try:
        return torch.load(path, map_location="cpu", mmap=True, weights_only=False)
    except TypeError:                                   # a torch without mmap=
        return torch.load(path, map_location="cpu", weights_only=False)


def read(d):
    b = load(os.path.join(d, "ckpt.pt"))
    tok = (b.get("payload") or {}).get("TOK") or {}
    mc = tok.get("merge_count") if isinstance(tok, dict) else None
    try:
        with open(d + ".dyntok.json") as fh:
            ent = len(json.load(fh)["entries"])
    except (OSError, ValueError, KeyError, TypeError):
        ent = None
    return int(b["step"]), str(b["reason"]), mc, ent


def drop(d):
    for f in (os.path.join(d, "ckpt.pt"), d + ".dyntok.json"):
        if os.path.exists(f):
            os.remove(f)
    if os.path.isdir(d):
        os.rmdir(d)


for d in sorted(glob.glob(os.path.join(kd, glob.escape(tag) + ".save[0-9]*"))):
    if not os.path.isdir(d):
        continue
    try:
        step, reason, mc, ent = read(d)
    except Exception as e:                              # noqa: BLE001 -- said, and the copy is left
        print(f"{os.path.basename(d)}: unreadable ({type(e).__name__}: {e}); left as it is")
        continue
    dst = os.path.join(kd, f"{tag}.w{step}")
    if reason == "final" or os.path.exists(dst):
        print(f"{os.path.basename(d)}: step {step} reason {reason} -- "
              + ("the final save, which the ring keeps" if reason == "final" else "a duplicate step") + "; dropped")
        drop(d)
        continue
    os.rename(d, dst)
    if os.path.exists(d + ".dyntok.json"):
        os.rename(d + ".dyntok.json", dst + ".dyntok.json")
rows = []
for d in sorted((p for p in glob.glob(os.path.join(kd, glob.escape(tag) + ".w[0-9]*")) if os.path.isdir(p)),
                key=lambda p: int(p.rsplit(".w", 1)[1])):
    step, reason, mc, ent = read(d)
    ok = mc is not None and ent is not None and int(mc) == int(ent)
    for f in (os.path.join(d, "ckpt.pt"), d + ".dyntok.json"):
        if os.path.exists(f):
            os.chmod(f, os.stat(f).st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
    rows.append(f"{os.path.basename(d)} step={step} reason={reason} merges={mc} entries={ent} "
                f"{'coherent' if ok else 'INCOHERENT'} bytes={os.path.getsize(os.path.join(d, 'ckpt.pt'))}")
with open(os.path.join(kd, tag + ".kept.txt"), "w") as fh:
    fh.write("".join(r + "\n" for r in rows))
print(f"{tag}: {len(rows)} kept")
PY
  )
}
# src/ FOR THE INDEX'S UNPICKLING: the fleet's own copy when it runs one (a launch always does, since
# 2026-09-27), so a pull during the fleet cannot pair its checkpoints with other code.
ROOT_DIR=$CODE_DIR

# ---------------------------------------------------------------- the block and the archive
archive_path() {  # beside OUT, named for the fleet's LAUNCH date, so --analyze on a later day repacks the same name
  local d b
  d=$(sed -n '1s/^=== gpu_world\.sh  \([0-9-]*\)T.*/\1/p' "$OUT/SUMMARY.txt" 2>/dev/null)
  b=$(basename "$OUT")
  echo "$(dirname "$OUT")/${b%_out}_${d:-$(date -u +%Y-%m-%d)}.tgz"
}
paste_back() {  # print the owner's block (EXP=retok's analysis wrote it; the others are wrapped here)
  [[ "$EXP" == retok ]] || gw_py wrap "$OUT" "$EXP" "$(archive_path)"
  echo
  # A MISSING BLOCK IS SAID, NOT SWALLOWED (2026-09-27 review: `cat 2>/dev/null` printed nothing at all)
  if [[ -f "$OUT/PASTE_BACK.txt" ]]; then cat "$OUT/PASTE_BACK.txt" 2>/dev/null
  else echo "!! no block was written: $OUT/PASTE_BACK.txt is missing (the errors above say why)"; fi
}
pack() {  # everything under OUT but checkpoints (and the fleet's code copy), into the archive the owner keeps
  local a p b rc
  gw_hb_stop                # the heartbeat writes into OUT: it ends before the archive is taken
  a=$(archive_path); p=$(dirname "$OUT"); b=$(basename "$OUT")
  # tar's exit 1 is "a file changed as it was read" (the dashboard's page, a run still ending): the
  # archive is written, so it counts as packed.
  tar -czf "$a" -C "$p" --warning=no-file-changed --warning=no-file-removed \
      --exclude="$b/ckpt" --exclude="$b/smoke/ckpt" --exclude="$b/mps" --exclude="$b/code" \
      --exclude='*.pt' --exclude='*.pt.*' --exclude='.*.tmp' "$b"
  rc=$?
  if [[ "$rc" -le 1 && -s "$a" ]]; then
    echo "=== packed $a ($(du -h "$a" | cut -f1)): logs, curves, SUMMARY, ANALYSIS, the block; no checkpoints. Keep it."
  else
    echo "!! could not pack $a"
  fi
}
fail_back() {  # reason [log...] : a stop before (or in) the analysis still ends in a block and an archive
  GW_BLOCKED=1; GW_FAIL_REASON=$1
  gw_hb_stop                # no heartbeat line lands inside the block
  gw_py fail "$OUT" "$EXP" "$(archive_path)" "$@"
  echo 2>/dev/null
  cat "$OUT/PASTE_BACK.txt" 2>/dev/null
  pack
}

# ---------------------------------------------------------------- one fleet per OUT: the lock, STATE, the heartbeat, the stops
# (2026-09-27; the header's "A FLEET SAYS IT IS ALIVE, AND ONLY ONE RUNS PER OUT" says why.)
# THE LOCK SITS BESIDE OUT, NOT IN IT: OUT is what a launch moves aside, and a lock inside it would move
# with it. It is an flock on fd 9, which every process of the fleet inherits -- the runs, the kept-
# checkpoint watchers, the heartbeat -- so the lock is held while ANY of them runs, even when the shell
# itself was killed; the MPS daemon and the nvidia-smi sampler, which outlive a killed fleet, are
# started without it (9>&-), and so are the readers the fleet calls. The file holds nothing and is
# never replaced: a replaced file would hand the next launch a fresh, unlocked one.
LOCKF=${OUT%/}; LOCKF="${LOCKF:-.}.lock"
_cmdenv="EXP=$EXP "; [[ -n "$_OUT_GIVEN" ]] && _cmdenv="${_cmdenv}OUT=$OUT "
# ...AND THEY WORK FROM ANY DIRECTORY: the script and the dashboard by absolute path (GW_HOME, above), the
# dashboard given OUT's absolute path; gpu_world.sh cds to its checkout, where a relative OUT resolves.
GW_CMD="${_cmdenv}bash $(printf %q "$GW_HOME/gpu_world.sh")"
GW_WATCH="bash $(printf %q "$GW_HOME/tools/fleet_dash.sh") $(printf %q "$(realpath -m -- "$OUT")")"

gw_flock() {  # fd: an exclusive lock on it, taken without waiting (0 = taken, 1 = held by another)
  if command -v flock > /dev/null 2>&1; then flock -n "$1"; return; fi
  python3 -c 'import fcntl, sys; fcntl.flock(int(sys.argv[1]), fcntl.LOCK_EX | fcntl.LOCK_NB)' "$1" 2>/dev/null
}
gw_proc() {  # pid: "<state> <start time>" of a process; fails when it is gone
  local s
  read -r s 2>/dev/null < "/proc/$1/stat" || return 1
  s=${s##*) }
  # shellcheck disable=SC2086
  set -- $s
  echo "$1 ${20}"
}
gw_alive() {  # pid start: THAT process (same start time) still runs, and is not a zombie
  local p
  [[ -n "${1:-}" && -n "${2:-}" ]] || return 1
  p=$(gw_proc "$1") || return 1
  [[ "${p%% *}" != Z && "${p#* }" == "$2" ]]
}
gw_is_live() {  # the fleet in OUT runs: fleet_dash.sh's verdict is RUNNING (0) or STALLED (5)
  local v
  bash "$DASH" --status "$OUT" 9>&- > /dev/null 2>&1
  v=$?
  [[ "$v" == 0 || "$v" == 5 ]]
}
gw_refuse_live() {  # why [process rows]: a launch finds a live fleet in OUT
  local frame v
  frame=$(bash "$DASH" --status "$OUT" 9>&- 2>/dev/null)
  v=$?
  if [[ "$v" == 0 || "$v" == 5 ]]; then
    echo "!! A FLEET IS ALREADY RUNNING IN $OUT: $1."
  else
    echo "!! THE FLEET IN $OUT IS NOT RUNNING, BUT PROCESSES IT STARTED STILL ARE ($1): runs orphaned when"
    echo "!! its shell was killed keep writing into OUT. $GW_CMD --stop clears them."
  fi
  echo "!! Nothing was started and nothing was moved (a second launch into a live OUT is what moved the"
  echo "!! 2026-09-27 retok fleet's directory out from under it)."
  if [[ -n "${2:-}" ]]; then echo "   its processes:"; echo "$2" | head -12 | sed 's/^/     /'; fi
  echo "$frame" | sed 's/^/   /'
  echo "   The card can read 0% while it runs: every smoke and calibration step starts its runs on the CPU"
  echo "   (python and torch, corpus, tokenizer, stream, model) before they use the GPU. Judge it by --status"
  echo "   or the heartbeat, never by nvidia-smi or a quiet log, and never by launching again."
  echo "   watch it:  $GW_WATCH"
  echo "   one look:  $GW_CMD --status"
  echo "   stop it:   $GW_CMD --stop      (it writes its block; launch again after)"
}

# STATE: key=value lines, the whole file rewritten (a tmp file, then mv) by the fleet's shell at every
# step; a later line for a key wins. The heartbeat watcher, whose copy of ST is stale, only appends.
declare -A ST=()
ST_KEYS=()
gw_state() {  # key=value ...
  local kv k
  for kv in "$@" "updated=$(date +%s)"; do
    k=${kv%%=*}
    [[ -n "${ST[$k]+x}" ]] || ST_KEYS+=("$k")
    ST[$k]=${kv#*=}
  done
  { for k in "${ST_KEYS[@]}"; do printf '%s=%s\n' "$k" "${ST[$k]}"; done; } > "$OUT/.STATE.tmp" 2>/dev/null \
    && mv -f "$OUT/.STATE.tmp" "$OUT/STATE" 2>/dev/null
  return 0
}
gw_state_add() {  # key=value ...: appended to STATE as it is on disk
  { cat "$OUT/STATE" 2>/dev/null; printf '%s\n' "$@"; } > "$OUT/.STATE.w.tmp" 2>/dev/null \
    && mv -f "$OUT/.STATE.w.tmp" "$OUT/STATE" 2>/dev/null
  return 0
}
gw_st() { sed -n "s/^$1=//p" "$OUT/STATE" 2>/dev/null | tail -1; }   # key: its value in STATE
gw_where() {  # where the fleet is, in words, off STATE
  local n
  case "$(gw_st phase)" in
    smoke) echo "the smoke" ;;
    cal) echo "calibration $(gw_st step)" ;;
    fleet) n=$(grep -c 'rc=' "$OUT/logs/_done.txt" 2>/dev/null)
           echo "the fleet (${n:-0} of $(gw_st runs_total) run(s) ended)" ;;
    analysis) echo "the analysis (the runs had ended: --analyze reads them)" ;;
    stopping) echo "the stop" ;;
    *) echo "the setup, before the smoke" ;;
  esac
}
gw_step() {  # phase step dir runs windows: from now on STATE says the fleet is here
  gw_state phase="$1" step="$2" step_dir="$(realpath -m -- "$3")" step_runs="$4" step_windows="$5" since="$(date +%s)"
}
gw_step_logs() {  # the logs of the current step's runs that did not end rc=0, at most 2 (for the block)
  local d tag rest n=0
  d=$(gw_st step_dir)
  [[ -n "$d" && -f "$d/_started.txt" ]] || return 0
  while read -r tag rest; do
    awk -v t="$tag" '$1 == t && $2 == "rc=0" { f = 1 } END { exit !f }' "$d/_done.txt" 2>/dev/null && continue
    [[ -f "$d/$tag.log" ]] || continue
    echo "$d/$tag.log"; n=$(( n + 1 ))
    (( n >= 2 )) && break
  done < "$d/_started.txt"
}
gw_kids() {  # kind ... | all: this shell's descendants of those kinds, one pid a line (never the MPS daemon)
  local rows p k c want=" $* "
  rows=$(bash "$DASH" --scan desc "$$" 9>&- 2>/dev/null) || return 0
  while IFS=$'\t' read -r p k c; do
    [[ -n "$p" && "$k" != mps ]] || continue
    if [[ "$want" == *" all "* || "$want" == *" $k "* ]]; then echo "$p"; fi
  done <<< "$rows"
}
gw_hb_stop() {  # the heartbeat watcher ends (a no-op where there is none, and in the watcher itself)
  [[ -n "${HB_PID:-}" ]] || return 0
  local i s
  kill "$HB_PID" 2>/dev/null
  # POLLED, NEVER `wait $HB_PID` (2026-09-27 review): a Ctrl-C or a hang-up reaches the whole process group,
  # so the watcher has often died of it already, and bash's wait for that pid inside the stop's trap then
  # blocked until ANOTHER child ended -- a run, minutes away -- so the stop found its runs finished. Gone
  # or a zombie ends the look; 5 s bound it.
  for i in $(seq 1 50); do
    s=$(gw_proc "$HB_PID") || break
    [[ "${s%% *}" == Z ]] && break
    sleep 0.1
  done
  HB_PID=""
  return 0
}
# THIS FLEET'S RUNS THAT ARE NO DESCENDANT OF ITS SHELL (2026-09-27 review). A Ctrl-C at a terminal reaches
# the whole process group: a run_job (an asynchronous subshell of a shell that traps INT, so bash resets
# INT to its default there) died of it, while its run.py -- started in the background, so ignoring INT --
# trained on, adopted by init: no descendant any more, never stopped, holding the lock after the fleet
# said STOPPED. run_job now ignores INT and HUP (below); a run orphaned all the same (a run_job killed
# some other way) is found as the watcher finds one, by the GW_FLEET_OUT it carries.
gw_own_runs() {
  bash "$DASH" --scan own "${GW_FLEET_OUT:-$OUT}" 9>&- 2>/dev/null | awk -F'\t' '$2 == "run" { print $1 }'
}
# gw_kids KIND and the orphaned runs, each pid once. The two scans run one after the other, never beside a
# pipeline's other end: the descendants' scan lists every process of this shell's but its own ancestors,
# so a `sort` running beside it read as a process of the fleet still to wait for.
gw_left() {  # kind ... | all
  local a b
  a=$(gw_kids "$@")
  b=$(gw_own_runs)
  printf '%s\n' $a $b | sort -un
}
gw_stop_children() {  # the heartbeat and the sampler; then this fleet's runs (TERM) and up to 30 s for each
                      # run_job to write its _done line; then TERM and KILL whatever of this shell's is left
  local left i
  : > "$OUT/.stopping" 2>/dev/null         # run_job skips its keep_index: --analyze indexes what is left
  gw_hb_stop
  [[ -n "${SMI_PID:-}" ]] && kill "$SMI_PID" 2>/dev/null
  left=$(gw_left run)
  if [[ -n "$left" ]]; then
    say "   stopping $(wc -w <<< "$left") run(s): pid $(echo $left)"
    kill -TERM $left 2>/dev/null
  fi
  for i in $(seq 1 60); do
    left=$(gw_left all)
    [[ -z "$left" ]] && break
    sleep 0.5
  done
  if [[ -n "$left" ]]; then kill -TERM $left 2>/dev/null; sleep 1; left=$(gw_left all); fi
  [[ -n "$left" ]] && kill -KILL $left 2>/dev/null
  rm -f "$OUT/.stopping"
  return 0
}
gw_mps_quit() {  # this fleet's MPS daemon, once, after its runs are gone (quit waits for its clients)
  [[ "${MPS_ON:-0}" == 1 && -z "${MPS_QUIT:-}" ]] || return 0
  MPS_QUIT=1
  echo quit | timeout 60 nvidia-cuda-mps-control > /dev/null 2>&1 \
    || echo "!! the MPS daemon did not quit within 60 s (CUDA_MPS_PIPE_DIRECTORY=${CUDA_MPS_PIPE_DIRECTORY:-?})"
  return 0
}
gw_on_signal() {  # INT | TERM | HUP: stop the runs, say why here and in the block, pack, exit 128+n
  local sig=$1 n where
  if [[ -n "${GW_STOPPING:-}" ]]; then echo "!! SIG$sig again: the fleet is already stopping (pid $$)" 2>/dev/null; return 0; fi
  # IN THE ANALYSIS NOTHING RUNS ANY MORE (2026-09-27 review). bash holds a trap until the command in the
  # foreground ends, so a --stop here waited for the analysis and then replaced its finished block, and the
  # archive's, with "STOPPED BEFORE THE ANALYSIS". The analysis, the block and the archive take seconds:
  # the signal is noted and they finish, and the fleet ends FINISHED.
  if [[ "${ST[phase]:-}" == analysis ]]; then
    [[ -n "${GW_LATE_SIG:-}" ]] || say "!! SIG$sig at $(date -u +%H:%M:%SZ) during the analysis: every run has ended, so the" \
      "fleet finishes its analysis, its block and its archive first (seconds), then exits (pid $$)"
    GW_LATE_SIG=${GW_LATE_SIG:-SIG$sig}
    return 0
  fi
  GW_STOPPING=SIG$sig
  # A SECOND Ctrl-C DOES NOT CUT THE STOP SHORT: it reaches the whole process group, and killed the
  # python writing the block or the tar packing the archive. From here INT and HUP are ignored, by this
  # shell and by what it starts; a second TERM still says "again".
  trap '' INT HUP
  case "$sig" in INT) n=2 ;; HUP) n=1 ;; *) n=15 ;; esac
  GW_RC=$(( 128 + n ))                     # gw_on_exit records this, whatever $? says by then
  where=$(gw_where)
  say ""
  say "!! gpu_world.sh STOPPED by SIG$sig at $(date -u +%H:%M:%SZ) during $where (pid $$)"
  gw_state phase=stopping since="$(date +%s)" reason="stopped by SIG$sig during $where"
  gw_stop_children
  fail_back "stopped by SIG$sig during $where" $(gw_step_logs)
  exit "$GW_RC"
}
gw_on_exit() {  # every exit of the fleet's shell: say why when nothing did, and leave no process behind
  local rc=$? cmd=$BASH_COMMAND where
  rc=${GW_RC:-$rc}
  # a second Ctrl-C or TERM must not cut the cleanup short (it is bounded: 30 s for the runs, 60 for MPS)
  trap - EXIT
  trap '' INT TERM HUP PIPE
  if [[ -z "${GW_FINISHED:-}" && -z "${GW_BLOCKED:-}" ]]; then
    where=$(gw_where)
    say ""
    say "!! gpu_world.sh stopped unexpectedly (exit $rc) during $where, at: $cmd"
    gw_stop_children
    fail_back "stopped unexpectedly (exit $rc) during $where, at: $cmd" $(gw_step_logs)
  else
    gw_stop_children
  fi
  gw_mps_quit
  if [[ -n "${GW_FINISHED:-}" ]]; then
    gw_state phase=done end=finished rc="$rc" ended="$(date +%s)" \
      reason="its analysis and its block are written${GW_LATE_SIG:+ (a $GW_LATE_SIG that came during the analysis waited for them)}"
  else
    gw_state end=stopped rc="$rc" ended="$(date +%s)" reason="${GW_FAIL_REASON:-exit $rc}"
  fi
  exit "$rc"
}
gw_watch() {  # in the background: a heartbeat line every HB_EVERY s, and the shell's death noticed
  local next=0 now txt
  while :; do
    gw_alive "$GW_PID" "$GW_PSTART" || { gw_watch_died; exit 0; }
    printf -v now '%(%s)T' -1
    if (( now >= next )); then
      next=$(( now + HB_EVERY ))
      txt=$(timeout 60 bash "$DASH" --line --sample "$OUT" 9>&- 2>/dev/null)
      if [[ -n "$txt" ]]; then
        printf '%s\n' "${txt%%$'\n'*}"
        printf '%s\n' "${txt%%$'\n'*}" >> "$OUT/heartbeat.log"
        printf '%s\n' "$txt" > "$OUT/.HEARTBEAT.tmp" && mv -f "$OUT/.HEARTBEAT.tmp" "$OUT/HEARTBEAT"
      fi
    fi
    sleep 1 9>&-
  done
}
gw_watch_died() {  # the shell is gone: if it recorded no end, say so, stop what it left, write the block
  grep -q '^end=' "$OUT/STATE" 2>/dev/null && return 0
  local where msg pids mp
  where=$(gw_where)
  msg="!! THE FLEET'S SHELL (pid $GW_PID) IS GONE AND WROTE NO BLOCK, during $where (noticed $(date -u +%H:%M:%SZ)"
  msg="$msg by its heartbeat watcher): a signal no trap can catch killed it (kill -9, the OOM killer), or it"
  msg="$msg crashed. The watcher stops the processes it left and writes the block."
  echo "$msg"
  echo "$msg" >> "$OUT/SUMMARY.txt"
  pids=$(bash "$DASH" --scan own "$OUT" 9>&- 2>/dev/null | awk -F'\t' '$2 == "run" || $2 == "shell" || $2 == "sampler" { print $1 }')
  if [[ -n "$pids" ]]; then
    kill -TERM $pids 2>/dev/null
    sleep 2
    pids=$(bash "$DASH" --scan own "$OUT" 9>&- 2>/dev/null | awk -F'\t' '$2 == "run" || $2 == "shell" || $2 == "sampler" { print $1 }')
    [[ -n "$pids" ]] && kill -KILL $pids 2>/dev/null
  fi
  mp=$(gw_st mps_pipe)
  [[ -n "$mp" ]] && echo quit | CUDA_MPS_PIPE_DIRECTORY="$mp" timeout 60 nvidia-cuda-mps-control > /dev/null 2>&1
  fail_back "the fleet's shell (pid $GW_PID) vanished during $where and wrote no block: killed by a signal no trap catches (kill -9, the OOM killer), or crashed"
  gw_state_add end=died rc=137 "ended=$(date +%s)" \
    "reason=its shell (pid $GW_PID) vanished during $where without a block (kill -9, the OOM killer, or a crash); its heartbeat watcher stopped what it left and wrote the block"
}
gw_fleet_start() {  # STATE, the traps and the heartbeat, before anything runs
  local log
  GW_PID=$$
  GW_PSTART=$(gw_proc $$); GW_PSTART=${GW_PSTART#* }
  log=$(readlink "/proc/$$/fd/1" 2>/dev/null); [[ -f "$log" ]] || log=""
  gw_state pid=$$ pid_start="$GW_PSTART" host="$(uname -n)" exp="$EXP" out="$GW_FLEET_OUT" code="$CODE_DIR" \
    commit="$COMMIT$DIRTY" launch="$LAUNCH" launch_t="$LAUNCH_T" log="$log" device="$DEVICE" \
    hb_every="$HB_EVERY" lock="${GW_LOCKF:-}" phase=setup step= step_dir="$GW_FLEET_OUT" since="$LAUNCH_T"
  trap 'gw_on_signal INT' INT
  trap 'gw_on_signal TERM' TERM
  trap 'gw_on_signal HUP' HUP
  trap 'gw_on_exit' EXIT
  HB_PID=""
  if (( HB_EVERY > 0 )); then
    gw_watch &
    HB_PID=$!
    gw_state hb_pid="$HB_PID"
  fi
}

# bash gpu_world.sh --analyze : the analysis of whatever runs are on disk, printed and written to
# ANALYSIS.txt, then the block and the archive. For a fleet that finished but never reached its own
# analysis, or one that was stopped part-way (the missing runs simply have no curve and are left out
# of the pairing; k0's copies an interrupted run never indexed are indexed first). NEVER ON A LIVE
# FLEET (2026-09-27): it would write into it and index the checkpoints its runs are still saving.
if [[ "${1:-}" == --analyze ]]; then
  [[ -f "$OUT/SUMMARY.txt" ]] || { echo "!! no $OUT/SUMMARY.txt: nothing to analyse here (OUT=$OUT)"; exit 1; }
  if gw_is_live; then
    echo "!! a fleet is running in $OUT: --analyze would write into it. Wait for it to end, or stop it"
    echo "   ($GW_CMD --stop), which writes its block. Nothing was written."
    exit 2
  fi
  [[ -d "$OUT/code/src" ]] && ROOT_DIR=$(cd "$OUT/code" && pwd -P)   # the fleet's own code unpickles its copies
  if [[ -z "$_EXP_GIVEN" ]]; then     # the experiment the fleet recorded, when EXP was not given
    _e=$(sed -n 's/^=== plan: EXP=\([a-z_]*\);.*/\1/p' "$OUT/SUMMARY.txt" | head -1)
    [[ -z "$_e" ]] && compgen -G "$OUT/logs/k0.s*.log" > /dev/null && _e=retok
    [[ -n "$_e" ]] && EXP=$_e
  fi
  _par=$(sed -n 's/^=== [0-9]* run(s), \([0-9]*\) at a time.*/\1/p' "$OUT/SUMMARY.txt" 2>/dev/null | tail -1)
  _mps=0; grep -q "CUDA MPS started" "$OUT/SUMMARY.txt" 2>/dev/null && _mps=1
  _dev=cuda; [[ -f "$OUT/smi.csv" ]] || _dev=cpu
  _launch=$(sed -n '1s/^=== gpu_world\.sh  \([0-9][0-9T:-]*Z\).*/\1/p' "$OUT/SUMMARY.txt")
  for _t in $(ls -d "$OUT"/ckpt/keep/*.save[0-9]*/ 2>/dev/null | sed 's#/$##; s#.*/##; s/\.save[0-9]*$//' | sort -u); do
    keep_index "$OUT/ckpt/keep" "$_t" "$_launch" > "$OUT/ckpt/keep/$_t.index.log" 2>&1
  done
  analyze "$OUT" "$_dev" "$_mps" "${_par:-1}" "$(nproc)" | tee "$OUT/ANALYSIS.txt"
  _arc=${PIPESTATUS[0]}
  echo "=== wrote $OUT/ANALYSIS.txt"
  # AN ANALYSIS THAT FAILED WRAPS AND PACKS NOTHING (2026-09-27 review: the pipeline's status was tee's):
  # the block and the archive already on disk are left as they were.
  if [[ "$_arc" != 0 ]]; then
    echo "!! the analysis FAILED (exit $_arc; its error is above): ANALYSIS.txt holds what it printed, and"
    echo "   $OUT/PASTE_BACK.txt and the archive were left as they were. Nothing was packed."
    exit 1
  fi
  paste_back
  pack
  exit 0
fi

# bash gpu_world.sh --status : the VERDICT FIRST -- RUNNING, STALLED, FINISHED, STOPPED (with its
# reason), DEAD ("died without a reason": the pid is gone and STATE records no end) or NO FLEET --
# then where it is: the stage and its time, each run of the step, windows, windows/s, the ETA, the
# GPU, the load, the disk, the heartbeat's age and the log's last lines. tools/fleet_dash.sh reads it
# (one reader for this, the dashboard and the heartbeat); the exit code is the verdict's: 0 RUNNING,
# 1 FINISHED, 2 NO FLEET, 3 STOPPED, 4 DEAD, 5 STALLED. It changes nothing and is safe at any time.
if [[ "${1:-}" == --status ]]; then
  bash "$DASH" --status "$OUT" 9>&-
  _v=$?
  [[ "$_v" == 2 && -z "$_EXP_GIVEN" && -z "$_OUT_GIVEN" ]] \
    && echo "   (EXP was not given, so this read $OUT, EXP=world's; the retok fleet is EXP=retok bash $(printf %q "$GW_HOME/gpu_world.sh") --status)"
  exit "$_v"
fi

# bash gpu_world.sh --stop : stop the running fleet the way a signal does -- SIGTERM to its shell, which
# stops its runs, writes STOPPED by SIGTERM in its log and its block, packs its archive and quits MPS --
# and wait for it (STOP_WAIT, 300 s). Then clear whatever still runs for OUT: a fleet from before
# STATE, or what a killed one left (its runs, its sampler, its MPS daemon). Never the container.
if [[ "${1:-}" == --stop ]]; then
  _pid=$(gw_st pid); _pst=$(gw_st pid_start)
  if gw_is_live && gw_alive "$_pid" "$_pst"; then
    echo "=== stopping the fleet in $OUT: SIGTERM to its shell, pid $_pid (it stops its runs, writes its block, packs)"
    kill -TERM "$_pid"
    for _i in $(seq 1 "${STOP_WAIT:-300}"); do gw_alive "$_pid" "$_pst" || break; sleep 1; done
    if gw_alive "$_pid" "$_pst"; then
      echo "!! pid $_pid still runs after ${STOP_WAIT:-300} s: kill -9 $_pid, then $GW_CMD --stop again"
      exit 1
    fi
    cat "$OUT/PASTE_BACK.txt" 2>/dev/null
  fi
  _rows=$(bash "$DASH" --scan own "$OUT" 9>&- 2>/dev/null)
  _p=$(awk -F'\t' '$2 != "mps" && $2 != "" { print $1 }' <<< "$_rows")
  if [[ -n "$_p" ]]; then
    echo "=== stopping $(wc -w <<< "$_p") process(es) still running for $OUT:"
    echo "$_rows" | sed 's/^/    /'
    kill -TERM $_p 2>/dev/null
    sleep 3
    _p=$(bash "$DASH" --scan own "$OUT" 9>&- 2>/dev/null | awk -F'\t' '$2 != "mps" && $2 != "" { print $1 }')
    [[ -n "$_p" ]] && kill -KILL $_p 2>/dev/null
  fi
  _mp=$(gw_st mps_pipe); [[ -n "$_mp" ]] || _mp="$(realpath -m -- "$OUT")/mps/pipe"
  if [[ -d "$_mp" ]] && command -v nvidia-cuda-mps-control > /dev/null 2>&1; then
    echo quit | CUDA_MPS_PIPE_DIRECTORY="$_mp" timeout 30 nvidia-cuda-mps-control > /dev/null 2>&1 \
      && echo "=== told the MPS daemon at $_mp to quit"
  fi
  bash "$DASH" --status "$OUT" 9>&-
  exit 0
fi

# THE WHOLE-EPOCH WORLD RE-RUN WAITS FOR SR0 ("do not run it", Proposal 05 §8 1.5): the sizing and the
# pre-registration are printed and NOTHING is written, not even $OUT.
if [[ "$EXP" == world_epoch && "$GO_WORLD_EPOCH" != 1 ]]; then
  plan_banner
  echo "=== EXP=world_epoch IS SIZED, NOT RUN: it is the WORLD re-run pre-registered after SR0 (register"
  echo "    note WORLD 3-4, §8 6.5). All four arms in ONE post-SR0 commit, 5 paired seeds, every run reading"
  echo "    one whole epoch (all four phases) with TOK_RETOK_EVERY and DATA_DRAW pinned; DATA_SYNTH_HOLDOUT ON"
  echo "    and the retention probe ON, levers this tree does not declare yet (SR0's build adds them to the"
  echo "    pins). Rule: WORLD_FEEDBACK flips ON only if fb_on beats fb_off on the time-integrated all-area"
  echo "    held-out gap (one-sided paired t, alpha 0.05; end-state beside it), is not worse than eps on the"
  echo "    worst area, and no seed shows latent_std < 0.9 or extra_ratio_max > 10. Both endpoints are"
  echo "    reported, with Q-WORLD-10's last-half and full-run prequential statistic beside the rule."
  echo "    GO_WORLD_EPOCH=1 lifts this guard (before SR0, an operation check only). Nothing was written."
  exit 2
fi
if [[ "$KEEP_CKPT" == 1 && "$OUT" =~ [[:space:]] ]]; then
  echo "!! OUT='$OUT' holds whitespace, and with KEEP_CKPT=1 its path rides inside the job lines, which are"
  echo "   split on whitespace. Choose an OUT without spaces. Nothing was started."; exit 2
fi

# ---------------------------------------------------------------- the launch gate (from the checkout)
# 1. THE LOCK. 2. A FLEET THE LOCK CANNOT SEE: a gpu_world.sh launched before the lock existed, or a
# run.py still writing under OUT -- the scan reads /proc (their command lines, working directories and
# environments). 3. At DEVICE=cuda, a fleet under ANOTHER OUT on this machine. 4. A previous fleet in
# OUT, now known dead, moved aside (below), and the MPS daemon it may have left told to quit. 5. The
# private copy, and the re-execution of it: nothing after this block runs from the checkout's script.
# A launch that finds a live fleet refuses before it has moved or written anything but the lock file.
if [[ "$GW_PRIVATE" != 1 ]]; then
  _oabs=$(realpath -m -- "$OUT")
  mkdir -p -- "$(dirname -- "$LOCKF")" 2>/dev/null     # OUT's parent, which the launch creates anyway
  if ! { exec 9<>"$LOCKF"; } 2>/dev/null; then
    echo "!! cannot open the lock file $LOCKF beside OUT: is its directory writable? Nothing was started."; exit 2
  fi
  if ! gw_flock 9; then
    gw_refuse_live "its lock, $LOCKF, is held"
    exit 2
  fi
  _rows=$(bash "$DASH" --scan own "$_oabs" 9>&- 2>/dev/null)
  _live=$(awk -F'\t' '$2 == "run" || $2 == "shell"' <<< "$_rows")
  if [[ -n "$_live" ]]; then
    gw_refuse_live "processes of a fleet the lock cannot see are running for it (launched by a gpu_world.sh from before the lock, or left by a killed one)" "$_live"
    exit 2
  fi
  if [[ "$DEVICE" == cuda && "${ALLOW_CONCURRENT:-0}" != 1 ]]; then
    _other=$(bash "$DASH" --scan card "$_oabs" 9>&- 2>/dev/null)
    if [[ -n "$_other" ]]; then
      echo "!! ANOTHER FLEET IS RUNNING ON THIS MACHINE'S GPU, under another OUT. Nothing was started:"
      echo "$_other" | head -6 | sed 's/^/     /'
      echo "   Two fleets on one card measure each other: the calibration, the rates and the ETA of both would"
      echo "   be wrong. Watch it (bash $(printf %q "$GW_HOME/tools/fleet_dash.sh") <its OUT>), wait for it, or stop"
      echo "   it (bash $(printf %q "$GW_HOME/gpu_world.sh") --stop with its EXP and OUT). ALLOW_CONCURRENT=1 runs this one"
      echo "   beside it anyway."
      exit 2
    fi
  fi
  # a sampler a killed fleet left in OUT writes into it for ever: it is stopped (its MPS daemon, below)
  _stray=$(awk -F'\t' '$2 == "sampler" { print $1 }' <<< "$_rows")
  [[ -n "$_stray" ]] && kill $_stray 2>/dev/null
fi

# A LAUNCH NEVER WRITES INTO A PREVIOUS FLEET (2026-09-27, build 1.5's review). A launch truncated
# SUMMARY.txt and left the rest: the logs and curves of seeds or arms it does not run, which its
# analysis then read as its own; KEPT.txt, PASTE_BACK.txt and ANALYSIS.txt; and at EXP=retok the
# rings and kept copies under ckpt/. The default OUT is reused between fleets (a WINDOWS=5000 look
# before the full fleet, C12's re-run of the k0 vs chosen-cadence pair after Levels), and a re-run
# there lost its own k0 copies: the index read the previous fleet's k0.s0.w21 as "a duplicate step"
# and deleted the new save at step 21, the watcher took the old ring's final checkpoint as a save of
# the new run, and the block called the old copies coherent. So a previous fleet in OUT is MOVED
# ASIDE WHOLE, beside it, as <OUT>.<its launch stamp>: nothing is deleted, and
# OUT=<that name> bash gpu_world.sh --analyze still reads it. The move is of OUT's own directory (a
# symlinked OUT keeps its link and its disk); OUT is recreated empty. A checkout or its parent is
# never moved: such an OUT is refused. ONLY A DEAD FLEET IS MOVED (2026-09-27): the checks above
# refuse a live one, whose runs write to OUT by name -- moved, they had lost their files, and their
# MPS quit reached the NEW fleet's daemon (reproduced).
MOVED_ASIDE=${GW_MOVED_ASIDE:-}
if [[ "$GW_PRIVATE" != 1 ]] && [[ -e "$OUT/SUMMARY.txt" || -e "$OUT/logs" || -e "$OUT/ckpt" || -e "$OUT/STATE" || -e "$OUT/code" ]]; then
  _od=$(cd "$OUT" && pwd -P); _od=${_od%/}
  case "$(pwd -P)/" in
    "$_od"/*) echo "!! OUT='$OUT' holds a previous fleet, and it is this checkout or holds it, so it cannot be moved"
              echo "   aside. Choose another OUT. Nothing was started."; exit 2 ;;
  esac
  _st=$(sed -n '1s/^=== gpu_world\.sh  \([0-9][0-9T:-]*Z\).*/\1/p' "$OUT/SUMMARY.txt" 2>/dev/null | tr -d ':')
  [[ -n "$_st" ]] || _st=$(date -u -r "$_od" +%Y-%m-%dT%H%M%SZ)
  MOVED_ASIDE="$_od.$_st"; _i=2
  while [[ -e "$MOVED_ASIDE" ]]; do MOVED_ASIDE="$_od.$_st.$_i"; _i=$(( _i + 1 )); done
  if ! mv "$_od" "$MOVED_ASIDE" || ! mkdir -p "$_od"; then
    echo "!! could not move the previous fleet in $OUT aside to $MOVED_ASIDE. Move or delete it, or choose another"
    echo "   OUT. Nothing was started."; exit 2
  fi
  # ITS MPS DAEMON, IF IT LEFT ONE (a SIGKILL runs no trap): the daemon listens on the FIFO in its pipe
  # directory, which moved with it, so the quit goes there. Nothing of that fleet runs (checked above).
  if [[ -d "$MOVED_ASIDE/mps/pipe" ]] && command -v nvidia-cuda-mps-control > /dev/null 2>&1; then
    echo quit | CUDA_MPS_PIPE_DIRECTORY="$MOVED_ASIDE/mps/pipe" timeout 30 nvidia-cuda-mps-control 9>&- > /dev/null 2>&1
  fi
fi

# THE PRIVATE COPY, THEN THE RE-EXECUTION OF IT. The commit and the dirty flag are read here, before
# the copy, and checked again after it: a checkout that changed in between (a pull during the launch)
# is refused. fd 9, the lock, stays open across the exec, and the pid does not change.
if [[ "$GW_PRIVATE" != 1 ]]; then
  mkdir -p "$OUT" || { echo "!! cannot create $OUT. Nothing was started."; exit 2; }
  COMMIT=$(git rev-parse --short HEAD 2>/dev/null)
  DIRTY=""
  [[ -n "$COMMIT" ]] && ! git diff --quiet HEAD -- src run.py gpu_world.sh 2>/dev/null && DIRTY=" (dirty)"
  _code="$_oabs/code"
  if ! { mkdir -p "$_code/tools" && cp -p gpu_world.sh run.py "$_code/" && cp -p tools/fleet_dash.sh "$_code/tools/" \
         && tar -cf - --exclude=__pycache__ --exclude='*.pyc' src | tar -xf - -C "$_code"; } 2>/dev/null; then
    echo "!! could not copy the code (gpu_world.sh, run.py, src/, tools/fleet_dash.sh) into $_code: is the disk full?"
    echo "   Nothing was started."; exit 2
  fi
  _sum=$(cd "$_code" && find . -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum | sha256sum | cut -c1-16)
  _dirty2=""
  [[ -n "$COMMIT" ]] && ! git diff --quiet HEAD -- src run.py gpu_world.sh 2>/dev/null && _dirty2=" (dirty)"
  if [[ "$(git rev-parse --short HEAD 2>/dev/null)" != "$COMMIT" || "$_dirty2" != "$DIRTY" ]]; then
    echo "!! the checkout changed while its code was being copied into $_code (a git pull during the launch?)."
    echo "   Launch again. Nothing was started."; exit 2
  fi
  export GW_ROOT="$PWD" GW_CODE="$_code" GW_FLEET_OUT="$_oabs" GW_COMMIT="$COMMIT" GW_DIRTY="$DIRTY" \
         GW_CODE_SUM="$_sum" GW_MOVED_ASIDE="$MOVED_ASIDE" GW_DEVICE="$DEVICE" GW_LOCKF="$(realpath -m -- "$LOCKF")"
  exec bash "$_code/gpu_world.sh" "$@"
fi
{ : >&9; } 2>/dev/null || { echo "!! $0 is a fleet's private copy: launch from the checkout (bash gpu_world.sh)"; exit 2; }

mkdir -p "$OUT/logs" "$OUT/curves" "$OUT/smoke" "$OUT/cal"
S="$OUT/SUMMARY.txt"
: > "$S"
# A DEAD OUTPUT PIPE STOPS NOTHING (2026-09-27 review). Launched as `bash gpu_world.sh 2>&1 | tee log`, a
# Ctrl-C or a closed terminal takes the tee with it, and the next write to the dead pipe raised SIGPIPE:
# say's tee died before SUMMARY got the "STOPPED by" line, then the shell's own echo made bash run its
# EXIT trap at once with $? = 0 -- no archive, rc=0 in STATE, the stop cut short. By the same mechanism,
# `nohup bash gpu_world.sh | tee log` would end at its first write after the terminal closed and took the
# tee with it. SIGPIPE is ignored from here on (a write to the dead pipe fails and the fleet goes on; a tee
# then keeps writing its files), and say writes SUMMARY first. What this shell starts inherits the ignore:
# python ignores SIGPIPE by itself anyway, and the MPS daemon is started with the default restored.
trap '' PIPE
say() { printf '%s\n' "$*" >> "$S"; printf '%s\n' "$*" 2>/dev/null; }

# ---------------------------------------------------------------- preflight
# ONE FLEET, ONE COMMIT: a checkout that differs from its commit where the runs read (src, run.py, this
# script) is flagged, and the flag reaches the block. Both were read in the checkout, before the copy
# this fleet runs from was taken (the launch gate, above).
COMMIT=${GW_COMMIT:-}
DIRTY=${GW_DIRTY:-}
# THE LAUNCH STAMP: SUMMARY's first line, the name a later launch moves this fleet aside under, and
# the .fleet stamp of its keep directories.
LAUNCH_T=$(date +%s)
LAUNCH=$(date -u -d "@$LAUNCH_T" +%Y-%m-%dT%H:%M:%SZ)
say "=== gpu_world.sh  $LAUNCH  commit $COMMIT$DIRTY"
[[ -n "$MOVED_ASIDE" ]] && say "=== the previous fleet in $OUT was moved aside, whole, to $MOVED_ASIDE" \
  "(nothing was deleted: its checkpoints are still on this disk)"
say "=== code: this fleet runs its own copy, $CODE_DIR (gpu_world.sh, run.py, src/, tools/fleet_dash.sh;" \
  "sha256 ${GW_CODE_SUM:-?}), taken from commit $COMMIT$DIRTY at launch: a git pull during the fleet reaches none of it"
gw_fleet_start
say "=== pid $$; watch it: $GW_WATCH | one look: $GW_CMD --status | stop it: $GW_CMD --stop"
# THE CORES, NEVER OMP_NUM_THREADS (2026-09-27 review): GNU nproc reports OMP_NUM_THREADS (capped by
# OMP_THREAD_LIMIT) when either is set, so an OMP_NUM_THREADS=1 exported in the launching shell sized a
# fleet at one core -- ceiling 1, PAR 1, one run at a time. Emptied, nproc ignores them. Every run sets
# OMP_NUM_THREADS=1 for itself (run_job).
NCPU=$(OMP_NUM_THREADS= OMP_THREAD_LIMIT= nproc)
# nproc READS THE CPU AFFINITY MASK, AND IN A CONTAINER THAT IS USUALLY THE HOST'S CORES. The cgroup
# QUOTA is what this container may actually use. The first version of this script sized its
# parallelism off nproc alone and put far more runs on the box than it had CPU for.
CPU_QUOTA=$(python3 - <<'PY'
def quota():
    try:
        a, b = open("/sys/fs/cgroup/cpu.max").read().split()
        return None if a == "max" else int(a) / int(b)
    except Exception:
        pass
    try:
        a = int(open("/sys/fs/cgroup/cpu/cpu.cfs_quota_us").read())
        b = int(open("/sys/fs/cgroup/cpu/cpu.cfs_period_us").read())
        return None if a <= 0 else a / b
    except Exception:
        return None
q = quota()
print(max(1, int(q)) if q else 0)
PY
)
if [[ "$CPU_QUOTA" -gt 0 && "$CPU_QUOTA" -lt "$NCPU" ]]; then
  say "=== nproc reports $NCPU core(s) but the cgroup quota is $CPU_QUOTA: sizing by the quota"
  NCPU=$CPU_QUOTA
fi
NGPU=0
GPU_MEM_MIB=0
if [[ "$DEVICE" == cuda ]]; then
  if ! command -v nvidia-smi >/dev/null; then
    say "!! nvidia-smi not found. DEVICE=cuda needs a GPU."; fail_back "nvidia-smi not found (DEVICE=cuda)"; exit 1
  fi
  if ! python3 -c "import torch,sys; sys.exit(0 if torch.cuda.is_available() else 1)"; then
    say "!! torch sees no CUDA device. Every arm sets RUN_DEVICE=cuda, and RUN.process_setup takes"
    say "!! it verbatim with no fallback, so each would raise at its first .to(). Stopping here."
    fail_back "torch sees no CUDA device (DEVICE=cuda)"
    exit 1
  fi
  NGPU=$(nvidia-smi --query-gpu=index --format=csv,noheader | wc -l)
  GPU_MEM_MIB=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -1 | tr -d ' ')
  nvidia-smi --query-gpu=index,name,memory.total,memory.used --format=csv | sed 's/^/    /' | tee -a "$S"
fi
say "=== $NCPU CPU core(s), $NGPU GPU(s), device=$DEVICE"
say "=== $(python3 -c 'import torch; print(f"torch {torch.__version__}, CUDA {torch.version.cuda}")' 2>/dev/null || echo 'torch ?, CUDA ?')"
plan_banner | tee -a "$S"
# run.py --flush-bytes (§8 1.3) writes the bytes behind each loss, which the per-phase bits/byte
# needs. Passed at the whole-epoch shapes only, and only where this tree's run.py has the flag.
FLUSH_BYTES=0
[[ "$EXP" != world && "$FB_FLAG" == yes ]] && FLUSH_BYTES=1
say ""

# ---------------------------------------------------------------- 0. MPS, before anything is measured
MPS_ON=0
if [[ "$DEVICE" == cuda && "$MPS" != 0 ]] && command -v nvidia-cuda-mps-control >/dev/null; then
  # AN ABSOLUTE PATH EITHER WAY: "$PWD/$OUT" was a path that does not exist when OUT is absolute.
  _ob=$OUT; [[ "$OUT" == /* ]] || _ob="$PWD/$OUT"
  export CUDA_MPS_PIPE_DIRECTORY="$_ob/mps/pipe" CUDA_MPS_LOG_DIRECTORY="$_ob/mps/log"
  mkdir -p "$CUDA_MPS_PIPE_DIRECTORY" "$CUDA_MPS_LOG_DIRECTORY"
  # THE DAEMON OUTLIVES A KILLED FLEET, SO IT NEVER HOLDS THE LOCK (9>&-). Every exit quits it, after the
  # runs are gone (gw_on_exit); a daemon a SIGKILLed fleet left is quit by the next launch. It starts with
  # SIGPIPE at its default, as before this shell ignored it.
  if ( trap - PIPE; exec nvidia-cuda-mps-control -d ) 9>&- 2>/dev/null; then
    MPS_ON=1; say "=== CUDA MPS started (kernels from different runs execute concurrently)"
    gw_state mps_pipe="$CUDA_MPS_PIPE_DIRECTORY"
  else
    unset CUDA_MPS_PIPE_DIRECTORY CUDA_MPS_LOG_DIRECTORY
    say "=== CUDA MPS could not start (permissions or GPU mode); runs will time-slice instead"
  fi
elif [[ "$DEVICE" == cuda && "$MPS" != 0 ]]; then
  say "=== nvidia-cuda-mps-control not installed; runs will time-slice the GPU instead of sharing it"
fi

# MPS SERVES AT MOST 48 CLIENT PROCESSES PER GPU (Volta and later). A client past that limit fails at
# CUDA init, and the first version of this script launched 65 runs at once: 48 ran and 17 failed.
MPS_CAP=0
[[ "$MPS_ON" == 1 ]] && MPS_CAP=$(( 48 * NGPU ))

# every process: one CPU thread (N processes x torch's default of one thread per core is how this
# project once measured a 60x slowdown), the card, the seed, the stream, the shared geometry, then the
# experiment's pins, then the arm's settings and its checkpoint settings (the later assignment wins).
# EXP=retok's k0 runs with a CKPT_DIR get the kept-checkpoint watcher beside them, and their index
# after them, before the _done.txt line.
run_job() {  # name seed windows gpu arm-env...
  # A Ctrl-C OR A CLOSED TERMINAL REACHES THE WHOLE PROCESS GROUP, AND run_job OUTLIVES IT (2026-09-27
  # review): run_job runs in the background of a shell that traps INT and HUP, so bash resets both to their
  # defaults here, and a Ctrl-C killed it while its run.py -- started in the background, so ignoring INT --
  # trained on as an orphan. Ignoring both, run_job stays to book its run when the fleet's stop TERMs it
  # (its run inherits the ignore; TERM, which the stop sends, is never ignored here).
  trap '' INT HUP
  local name="$1" seed="$2" win="$3" gpu="$4"; shift 4
  local tag="$name.s$seed"
  local log="$OUT/logs/$tag.log" t0=$(date +%s)
  [[ -n "${JOB_DIR:-}" ]] && log="$JOB_DIR/$tag.log"
  local vis=() fb=() ck="" kd="" w="" a
  [[ "$DEVICE" == cuda ]] && vis=(CUDA_VISIBLE_DEVICES="$gpu")
  [[ "$FLUSH_BYTES" == 1 ]] && fb=(--flush-bytes "${CURVE_DIR:-$OUT/curves}/$tag.bytes.json")
  if [[ "$KEEP_CKPT" == 1 && "$EXP" == retok && "$name" == k0 ]]; then
    for a in "$@"; do [[ "$a" == CKPT_DIR=* ]] && ck="${a#CKPT_DIR=}"; done
  fi
  if [[ -n "$ck" ]]; then
    kd="$(dirname "$ck")/keep"; mkdir -p "$kd"; rm -f "$kd/.$tag.stop"
    # THIS run_job's PID, TAKEN HERE: an argument of a command started with & is expanded in the
    # child, where $BASHPID is the watcher's own.
    local me=$BASHPID
    keep_watch "$ck" "$kd" "$tag" "$me" &
    w=$!
  fi
  # THE RUN IS THE FLEET'S OWN COPY OF run.py ($CODE_DIR), UNBUFFERED, AND ITS PID GOES ON THE BOOK
  # (2026-09-27). PYTHONUNBUFFERED=1 puts each line in the log when it is printed (the '[N windows]'
  # progress line was the only flushed one, so a log stayed empty for its first 100 windows); it
  # changes no number. <step>/_started.txt, "tag pid=P t0=T cap=C target=W", is what the heartbeat,
  # the dashboard and a stop read: which runs started, which are alive, and how many windows each is
  # after (at the whole-epoch shapes the cap is out of reach and a run reads about WINDOWS).
  local tw=$win rp
  [[ "$EXP" != world && "$win" -gt "$WINDOWS" ]] && tw=$WINDOWS
  env "${vis[@]}" PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 RUN_DEVICE="$DEVICE" RUN_SEED="$seed" \
      DATA_STREAM_BYTES="$BYTES" $EXTRA $EXP_ENV "$@" \
      python3 "$CODE_DIR/run.py" --max-windows "$win" --loss-curve "${CURVE_DIR:-$OUT/curves}/$tag.json" "${fb[@]}" \
      > "$log" 2>&1 &
  rp=$!
  echo "$tag pid=$rp t0=$t0 cap=$win target=$tw" >> "${JOB_DIR:-$OUT/logs}/_started.txt"
  wait "$rp"
  local rc=$?
  if [[ -n "$w" ]]; then
    : > "$kd/.$tag.stop"
    wait "$w"
    # a stop skips the index (seconds of torch per run): --analyze indexes the copies left unindexed
    [[ -e "$OUT/.stopping" ]] || keep_index "$kd" "$tag" "$LAUNCH" > "$kd/$tag.index.log" 2>&1
  fi
  echo "$tag rc=$rc secs=$(( $(date +%s) - t0 ))" >> "${JOB_DIR:-$OUT/logs}/_done.txt"
  return $rc
}

# a job line is: name seed windows arm-env...   (arm-env may be empty)
declare -a JOBS=()
add_job() { JOBS+=("$*"); }

# IT WAITS ON ITS OWN RUNS BY PID, NEVER WITH A BARE `wait`. The nvidia-smi sampler is a background
# child of this shell too, and it never exits by itself: the first fleet on a real card finished all
# 21 runs and then hung in a bare `wait` for the sampler, so the analysis never ran. `wait -n` had
# the same exposure in reverse (any child ending counted as a slot freed).
run_fleet() {  # runs JOBS with $1 slots, round-robin over GPUs
  local slots="$1" i=0 p
  local -a pids=()
  : > "${JOB_DIR:-$OUT/logs}/_done.txt"
  : > "${JOB_DIR:-$OUT/logs}/_started.txt"
  for line in "${JOBS[@]}"; do
    # shellcheck disable=SC2086
    set -- $line
    local name="$1" seed="$2" win="$3"; shift 3
    local gpu=0
    [[ "$NGPU" -gt 0 ]] && gpu=$(( i % NGPU ))
    while :; do                                   # a free slot = fewer than $slots of OUR pids alive
      local alive=0
      for p in "${pids[@]}"; do kill -0 "$p" 2>/dev/null && alive=$(( alive + 1 )); done
      [[ "$alive" -lt "$slots" ]] && break
      sleep 2
    done
    run_job "$name" "$seed" "$win" "$gpu" "$@" &
    pids+=("$!")
    i=$(( i + 1 ))
  done
  for p in "${pids[@]}"; do wait "$p"; done
}

# EACH KEEP DIRECTORY IS STAMPED WITH THIS LAUNCH before any run can save into it (keep_index refuses
# one stamped by another launch).
if [[ "$KEEP_CKPT" == 1 && "$EXP" == retok ]]; then
  for _k in "$OUT/smoke/ckpt/keep" "$OUT/ckpt/keep"; do mkdir -p "$_k" && echo "$LAUNCH" > "$_k/.fleet"; done
fi

# ---------------------------------------------------------------- 1. smoke every arm
say "---- 1. smoke: every arm, seed 0, $SMOKE_WINDOWS windows, all at once"
JOBS=()
for a in $BASE_ARMS; do add_job "$a 0 $SMOKE_WINDOWS $(arm_env $a) $(ckpt_env $a 0 "$OUT/smoke/ckpt" smoke)"; done
if [[ -n "$ARCH_ALSO" ]]; then
  for a in fb_off fb_on; do add_job "${a}@$ARCH_ALSO 0 $SMOKE_WINDOWS LM_ARCH=$ARCH_ALSO $(arm_env $a) $(ckpt_env "${a}@$ARCH_ALSO" 0 "$OUT/smoke/ckpt" smoke)"; done
fi
# EACH STEP SAYS WHEN ITS RUNS START, AND THAT THEY START ON THE CPU (2026-09-27): a fresh run.py
# imports torch and builds its corpus, tokenizer, stream and model before it touches the GPU, so the
# card reads idle for that long at the start of every smoke and calibration step, and the step's
# own line prints only when it ends. The smoke measures the startup on this machine (below). At the
# retok shape a run took 15-16 s on the 4-core CPU box, one alone or four at once on an idle box (the
# smoke measured 16.2 s, median of 4), and 66-71 s each when another job's tests shared that CPU (2026-09-27
# review; its ~28 s for four at once did not reproduce on the idle box): the startup takes the CPU it gets.
HB_NOTE=""; (( HB_EVERY > 0 )) && HB_NOTE="; a heartbeat line every $HB_EVERY s until then"
gw_step smoke smoke "$OUT/smoke" "${#JOBS[@]}" "$SMOKE_WINDOWS"
say "    ${#JOBS[@]} run(s) start $(date -u +%H:%M:%SZ). Each builds on the CPU first -- python and torch, corpus," \
  "tokenizer, stream, model: 15-30 s on the 4-core CPU box, longer when the CPU is shared, and this smoke" \
  "measures it here -- and only then uses the GPU, so nvidia-smi reads idle until they train. The step's result" \
  "prints when it ends$HB_NOTE."
JOB_DIR="$OUT/smoke" CURVE_DIR="$OUT/smoke" run_fleet "${#JOBS[@]}"
if grep -q "rc=[1-9]" "$OUT/smoke/_done.txt"; then
  say "!! a smoke arm FAILED -- stopping before the fleet:"
  grep "rc=[1-9]" "$OUT/smoke/_done.txt" | sed 's/^/    /' | tee -a "$S"
  for f in $(grep "rc=[1-9]" "$OUT/smoke/_done.txt" | cut -d' ' -f1); do
    say "    --- $f (last 8 lines)"; tail -8 "$OUT/smoke/$f.log" | sed 's/^/      /' | tee -a "$S"
  done
  fail_back "a smoke arm failed" $(grep "rc=[1-9]" "$OUT/smoke/_done.txt" | cut -d' ' -f1 | sed "s#^#$OUT/smoke/#; s#\$#.log#")
  exit 1
fi
# the tripwires and the sizing numbers, read off the smoke logs
SIZING=$(python3 - "$OUT/smoke" "$DEVICE" <<'PY' | tee -a "$S"
import re, sys, glob, os
d, dev = sys.argv[1], sys.argv[2]
def rep(t):
    out = {}
    for m in re.finditer(r"^\s+([A-Za-z_][\w.@()-]*\.[\w.@()-]+)\s+(\S+)\s*$", t, re.M):
        out[m.group(1)] = m.group(2)
    return out
bad, peak, wps = [], 0.0, []
for log in sorted(glob.glob(os.path.join(d, "*.log"))):
    t = open(log).read(); r = rep(t); arm = os.path.basename(log).split(".s")[0].split("@")[0]
    if dev == "cuda" and "device=cuda" not in t:
        bad.append(f"{arm}: the banner does not say device=cuda")
    fc, ea, built = r.get("world.forecasts"), r.get("lm.encode.extra_applied"), r.get("world.built")
    if arm in ("fb_on", "skip") and (ea is None or ea != fc):
        bad.append(f"{arm}: expected world.forecasts == lm.encode.extra_applied, got {fc} / {ea}")
    if arm == "fb_off" and ea is not None:
        bad.append(f"{arm}: lm.encode.extra_applied is PRESENT ({ea}) on the unwired control")
    if arm == "world_off" and built != "null":
        bad.append(f"{arm}: world.built is {built!r}, expected 'null'")
    m = re.search(r"peak CUDA memory [\d.]+ GiB allocated, ([\d.]+) GiB reserved", t)
    if m: peak = max(peak, float(m.group(1)))
    m = re.search(r"=== (\d+) windows[^\n]*? in ([\d.]+)s", t)
    if m and float(m.group(2)) > 0: wps.append(int(m.group(1)) / float(m.group(2)))
for b in bad: print("  TRIPWIRE:", b)
print(f"  smoke: {len(glob.glob(os.path.join(d, '*.log')))} arm(s) ran; peak reserved {peak:.3f} GiB per process; "
      f"{min(wps) if wps else 0:.1f}-{max(wps) if wps else 0:.1f} windows/s per process while all ran at once")
print(f"SIZING peak_gib={peak:.4f} wps={min(wps) if wps else 0:.3f} bad={len(bad)}")
PY
)
if echo "$SIZING" | grep -q "bad=[1-9]"; then
  say "!! a tripwire failed in the smoke -- stopping before the fleet."
  fail_back "a smoke tripwire failed: $(echo "$SIZING" | grep TRIPWIRE | head -3 | sed 's/^ *TRIPWIRE: //' | tr '\n' ';')"
  exit 1
fi
PEAK_GIB=$(echo "$SIZING" | sed -n 's/.*peak_gib=\([0-9.]*\).*/\1/p')
SMOKE_WPS=$(echo "$SIZING" | sed -n 's/.*wps=\([0-9.]*\).*/\1/p')
# THE STARTUP, MEASURED: run.py's '=== composed' line says how long the run took from its first line
# to its first window (imports and compose). Every calibration and fleet step's line quotes it.
STARTUP=$(python3 - "$OUT/smoke" <<'PY'
import glob, os, re, statistics, sys
xs = []
for log in glob.glob(os.path.join(sys.argv[1], "*.log")):
    m = re.search(r"^=== composed: [^\n]*?startup took ([\d.]+) s", open(log, errors="replace").read(), re.M)
    if m:
        xs.append(float(m.group(1)))
print(f"{statistics.median(xs):.1f} {min(xs):.1f} {max(xs):.1f} {len(xs)}" if xs else "")
PY
)
STARTUP_S=""
if [[ -n "$STARTUP" ]]; then
  read -r STARTUP_S _smin _smax _sn <<< "$STARTUP"
  say "  startup: each smoke run built on the CPU for ${STARTUP_S} s (median of $_sn; ${_smin}-${_smax} s) before its" \
      "first window: the GPU idles about that long at the start of every calibration step, longer when the CPU" \
      "is shared"
  gw_state startup_s="$STARTUP_S"
fi
# THE KEPT-CHECKPOINT TRIPWIRE: the smoke's k0 saved at SMOKE_WINDOWS/2, so the watcher and the index
# ran on this card in the first minute, and at least one copy must be kept and coherent. The smoke's
# checkpoints then size the fleet's disk and are deleted.
CKPT_BYTES=0
if [[ "$KEEP_CKPT" == 1 ]]; then
  if [[ "$EXP" == retok ]]; then
    _kept="$OUT/smoke/ckpt/keep/k0.s0.kept.txt"
    if [[ $(grep -c " coherent " "$_kept" 2>/dev/null) -lt 1 ]]; then
      say "!! kept-checkpoint tripwire: the smoke's k0 left no coherent kept copy ($_kept):"
      cat "$_kept" "$OUT/smoke/ckpt/keep/k0.s0.index.log" 2>/dev/null | sed 's/^/    /' | tee -a "$S"
      fail_back "the kept-checkpoint tripwire: no coherent copy of the smoke's k0 periodic save" \
                "$OUT/smoke/ckpt/keep/k0.s0.index.log" "$OUT/smoke/k0.s0.log"
      exit 1
    fi
    say "  smoke kept: $(grep " coherent " "$_kept" | head -1)"
  fi
  CKPT_BYTES=$(find "$OUT/smoke/ckpt" -type f -name 'ckpt.pt*' -printf '%s\n' 2>/dev/null | sort -n | tail -1)
  CKPT_BYTES=${CKPT_BYTES:-0}
  rm -rf "$OUT/smoke/ckpt"
  say "  smoke checkpoints: the largest was $(( CKPT_BYTES / 1000000 )) MB; deleted"
fi

# ---------------------------------------------------------------- 1b. MEASURE the parallelism
# THE CEILING IS ARITHMETIC AND THE CHOICE IS A MEASUREMENT. Cores, GPU memory and the MPS client
# limit say how many runs COULD share the card; none of them says how many SHOULD. The first version
# of this script took the arithmetic ceiling as the answer: 125 slots, 65 runs at once, and the card
# delivered 16.5 windows/s in AGGREGATE -- 0.3 per run -- because a launch-bound process starved of
# CPU and time-sliced against 47 others is slower than the same work done a few at a time. So this
# runs k copies of the shipped defaults for CAL_WINDOWS windows at k = 1, 2, 4, 8, ... up to the
# ceiling, reads each run's own loop time (the "in Xs" of its summary line, which excludes startup),
# and takes the SMALLEST k within 10% of the best aggregate windows/s. Each step costs one short run;
# the ladder stops as soon as doubling k gains less than 10%, so the step where throughput collapses
# is the last one paid for. The copies carry the experiment's pins and never save. CAL_WINDOWS is 600
# at the whole-epoch shapes, past the first FAB manage pass at window 501: the 2026-09-24 fleet ran
# about 15x slower than its 150-window calibration (LOW-GPU-WORLD-ETA).
CPU_SLOTS=$(( NCPU > 1 ? NCPU - 1 : 1 ))
CEIL=$CPU_SLOTS
if [[ "$DEVICE" == cuda ]]; then
  MEM_SLOTS=$(python3 -c "print(max(1, int(0.85*$GPU_MEM_MIB/1024 / (1.5*$PEAK_GIB + 0.5)) * $NGPU))")
  [[ "$MEM_SLOTS" -lt "$CEIL" ]] && CEIL=$MEM_SLOTS
  [[ "$MPS_CAP" -gt 0 && "$MPS_CAP" -lt "$CEIL" ]] && CEIL=$MPS_CAP
fi
say "=== ceiling: $CPU_SLOTS by CPU, ${MEM_SLOTS:-n/a} by GPU memory, ${MPS_CAP/#0/no} MPS cap -> at most $CEIL at once"
if [[ "$PAR" == auto ]]; then
  say "---- calibration: k copies of the shipped defaults for $CAL_WINDOWS windows, aggregate windows/s"
  : > "$OUT/cal/table.txt"
  prev=0
  for k in $LADDER; do
    [[ "$k" -gt "$CEIL" ]] && break
    d="$OUT/cal/k$k"; mkdir -p "$d"
    JOBS=(); for j in $(seq 1 "$k"); do add_job "cal $(( 1000 + j )) $CAL_WINDOWS"; done
    gw_step cal "k=$k" "$d" "$k" "$CAL_WINDOWS"
    say "    k=$k: $k run(s) x $CAL_WINDOWS windows start $(date -u +%H:%M:%SZ): ~${STARTUP_S:-15-30} s on the CPU first" \
        "(the GPU reads idle; the smoke's figure, longer when the CPU is shared), then the training; the step's" \
        "line prints when it ends"
    JOB_DIR="$d" CURVE_DIR="$d" run_fleet "$k"
    # A RUN THAT WROTE NO _done LINE COUNTS AS FAILED (2026-09-27): the count was the _done lines minus the
    # runs with a summary line, which a killed run_job turned negative -- read as "no failure" -- and a
    # missing _done.txt stopped the reader, whose empty answer then killed the script at `set -- $line`
    # (set -u) without a block. With every _done line written, as on every fleet so far, it is unchanged.
    line=$(python3 - "$d" "$k" <<'PY'
import glob, os, re, sys
d, k = sys.argv[1], int(sys.argv[2])
rate, n = 0.0, 0
for log in glob.glob(os.path.join(d, "*.log")):
    m = re.search(r"=== (\d+) windows[^\n]*? in ([\d.]+)s", open(log).read())
    if m and float(m.group(2)) > 0:
        rate += int(m.group(1)) / float(m.group(2)); n += 1
try:
    done = open(os.path.join(d, "_done.txt")).read().count("rc=")
except OSError:
    done = 0
fails = max(done, k) - n
print(f"{k} {rate:.3f} {fails}")
PY
)
    if [[ ! "$line" =~ ^[0-9]+\ [0-9.]+\ -?[0-9]+$ ]]; then
      say "!! calibration k=$k could not be read (its reader answered '${line:-nothing}') -- stopping before the fleet"
      fail_back "calibration k=$k could not be read (its runs' logs are in $d)" $(ls "$d"/*.log 2>/dev/null | head -2)
      exit 1
    fi
    echo "$line" >> "$OUT/cal/table.txt"
    set -- $line
    say "    k=$1  aggregate $2 windows/s  ($(python3 -c "print(f'{$2/$1:.2f}')") per run)  failed $3"
    if [[ "$3" -gt 0 ]]; then say "    runs FAILED at k=$1 -- the ladder stops below it"; sed -i '$d' "$OUT/cal/table.txt"; break; fi
    if python3 -c "import sys; sys.exit(0 if $prev > 0 and $2 < 1.10 * $prev else 1)"; then break; fi
    prev=$2
  done
  read PAR CAL_RATE < <(python3 - "$OUT/cal/table.txt" <<'PY'
import sys
rows = [tuple(map(float, l.split()[:2])) for l in open(sys.argv[1]) if l.strip()]
if not rows:                      # even k=1 failed: run one at a time and let the fleet's logs say why
    print(1, 0); raise SystemExit
best = max(r for _, r in rows)
k, r = min((k, r) for k, r in rows if r >= 0.9 * best)
print(int(k), r)
PY
)
  say "=== calibration: PAR=$PAR (aggregate $CAL_RATE windows/s; the smallest k within 10% of the best measured)"
else
  CAL_RATE=0
  say "=== PAR=$PAR set by hand; no calibration"
fi

# ---------------------------------------------------------------- 2. the job list and its size
JOBS=()
for s in $SEEDS; do for a in $BASE_ARMS; do add_job "$a $s $RUN_WIN $(arm_env $a) $(ckpt_env $a $s "$OUT/ckpt")"; done; done
add_job "${CTRL}_rerun 0 $RUN_WIN $(arm_env $CTRL) $(ckpt_env ${CTRL}_rerun 0 "$OUT/ckpt")"
if [[ -n "$ARCH_ALSO" ]]; then
  for s in $SEEDS; do for a in fb_off fb_on; do add_job "${a}@$ARCH_ALSO $s $WINDOWS LM_ARCH=$ARCH_ALSO $(arm_env $a) $(ckpt_env "${a}@$ARCH_ALSO" $s "$OUT/ckpt")"; done; done
fi
if [[ "$LONG" -gt 0 ]]; then
  for a in fb_off fb_on; do add_job "${a}_long 0 $LONG $(arm_env $a) $(ckpt_env ${a}_long 0 "$OUT/ckpt")"; done
fi

# THE CHECKPOINTS' DISK, SIZED BEFORE FILL (KEEP_CKPT=1): every file at twice the smoke's largest
# checkpoint (the fabric grows toward FAB_SLOTS), k0 at its kept saves plus the ring. FILL stops adding
# seeds past 0.9 of the free space, and a job list that does not fit at its base seeds is refused.
gb() { awk -v b="$1" 'BEGIN { printf "%.1f", b / 1e9 }'; }
jobs_need() {  # bytes the job list's checkpoints may take
  local n=0 line
  for line in "${JOBS[@]}"; do n=$(( n + $(ckpt_files "${line%% *}") )); done
  echo $(( n * CKPT_BYTES * 2 ))
}
if [[ "$KEEP_CKPT" == 1 ]]; then
  FREE_B=$(( $(df -Pk "$OUT" | awk 'NR == 2 {print $4}') * 1024 ))
  NEED_B=$(jobs_need)
  if [[ "$NEED_B" -gt "$FREE_B" ]]; then
    say "!! disk: the kept checkpoints may need $(gb $NEED_B) GB and $OUT has $(gb $FREE_B) GB free."
    say "!! Free space, run fewer SEEDS, or KEEP_CKPT=0 (which leaves the spike test without its control)."
    [[ -n "$MOVED_ASIDE" ]] && say "!! The previous fleet, moved aside to $MOVED_ASIDE, still holds its checkpoints."
    fail_back "disk: checkpoints may need $(gb $NEED_B) GB, $(gb $FREE_B) GB free (free space, fewer SEEDS, or KEEP_CKPT=0)"
    exit 1
  fi
fi

# FILL: spare slots become extra seeds, added to EVERY base arm so the pairing stays complete.
if [[ "$FILL" == 1 && "${#JOBS[@]}" -lt "$PAR" ]]; then
  n_seeds=$(echo $SEEDS | wc -w); next=$(( $(echo $SEEDS | tr ' ' '\n' | sort -n | tail -1) + 1 ))
  n_arms=$(echo $BASE_ARMS | wc -w)
  added=""
  while [[ $(( ${#JOBS[@]} + n_arms )) -le "$PAR" && "$n_seeds" -lt "$MAX_SEEDS" ]]; do
    if [[ "$KEEP_CKPT" == 1 ]]; then
      _more=0; for a in $BASE_ARMS; do _more=$(( _more + $(ckpt_files $a) )); done
      if [[ $(( $(jobs_need) + _more * CKPT_BYTES * 2 )) -gt $(( FREE_B / 10 * 9 )) ]]; then
        say "=== FILL stops at $n_seeds seeds: another would pass 0.9 of the free disk ($(gb $FREE_B) GB)"
        break
      fi
    fi
    for a in $BASE_ARMS; do add_job "$a $next $RUN_WIN $(arm_env $a) $(ckpt_env $a $next "$OUT/ckpt")"; done
    added="$added $next"; next=$(( next + 1 )); n_seeds=$(( n_seeds + 1 ))
  done
  [[ -n "$added" ]] && say "=== FILL: spare slots -> extra seeds$added on every base arm (now $n_seeds seeds)"
fi
[[ "$KEEP_CKPT" == 1 ]] && say "=== disk: checkpoints may take about $(gb $(jobs_need)) GB" \
  "($(( CKPT_BYTES / 1000000 )) MB x 2 per file) of $(gb $FREE_B) GB free at $OUT"
say "=== ${#JOBS[@]} run(s), $PAR at a time"
# THE ETA IS PRICED AT THE MEASURED AGGREGATE RATE at PAR, over every window the job list holds. It
# assumes every slot stays busy, so the last partial wave makes it slightly optimistic, and the rate
# was measured on short runs whose fabric had not grown yet.
python3 - "${CAL_RATE:-0}" "$SMOKE_WPS" "$PAR" <<PY | tee -a "$S"
import math
jobs = """$(printf '%s\n' "${JOBS[@]}")""".split("\n")
# A retok job's window count is its cap, set out of reach; it reads about WINDOWS windows.
total = sum(min(int(j.split()[2]), int("$WINDOWS")) for j in jobs if j.strip())
rate, smoke, par = float("${CAL_RATE:-0}"), float("$SMOKE_WPS" or 0), int("$PAR")
if rate <= 0: rate = smoke * par
if rate > 0:
    print(f"=== ETA: about {total / rate / 3600:.1f} h for {total:,} windows at {rate:.1f} windows/s aggregate")
PY

# ---------------------------------------------------------------- 4. the fleet, with a sampler
say "---- 2. fleet started $(date -u +%H:%M:%SZ)"
gw_step fleet "" "$OUT/logs" "${#JOBS[@]}" "$WINDOWS"
gw_state par="$PAR" runs_total="${#JOBS[@]}" windows="$WINDOWS"
say "    ${#JOBS[@]} run(s), $PAR at a time; each spends ~${STARTUP_S:-15-30} s on the CPU before it trains. The fleet's" \
    "own line prints when its last run ends$HB_NOTE; $GW_WATCH shows every run."
SMI_PID=""
if [[ "$DEVICE" == cuda ]]; then
  # THE SAMPLER NEVER HOLDS THE LOCK (9>&-): it runs until it is killed, and a SIGKILLed fleet cannot.
  nvidia-smi --query-gpu=index,utilization.gpu,memory.used,memory.total \
             --format=csv,noheader,nounits -l 2 > "$OUT/smi.csv" 2>/dev/null 9>&- &
  SMI_PID=$!
  gw_state smi_pid="$SMI_PID"
fi
T0=$(date +%s)
run_fleet "$PAR"
T1=$(date +%s)
[[ -n "$SMI_PID" ]] && kill "$SMI_PID" 2>/dev/null
gw_mps_quit
say "---- fleet finished in $(( (T1 - T0) / 60 )) min ($(( T1 - T0 )) s)"
if grep -q "rc=[1-9]" "$OUT/logs/_done.txt"; then
  say "!! FAILED runs (their logs are in $OUT/logs):"
  grep "rc=[1-9]" "$OUT/logs/_done.txt" | sed 's/^/    /' | tee -a "$S"
fi

# ---------------------------------------------------------------- 5. analysis, the block, the archive
# THE HEARTBEAT ENDS HERE: nothing runs any more, and no heartbeat line may land inside the block.
# A STOP NOW WAITS THE SECONDS THE REST TAKES (2026-09-27 review): gw_on_signal notes an INT, TERM or HUP
# in this phase and returns, and the analysis, the block and the archive's tar run with INT and HUP
# ignored, so a Ctrl-C or a closed terminal that reaches the whole process group cannot cut them short.
# FINISHED ONLY WITH ITS BLOCK (2026-09-27 review): the pipeline's status was tee's, so an analysis that
# raised, or that the OOM killer took, still ended FINISHED, "its block written", with no PASTE_BACK.txt.
# Such a fleet now ends STOPPED, its block saying the analysis failed, and --analyze reads its runs again.
gw_step analysis "" "$OUT" 0 0
gw_hb_stop
rm -f "$OUT/PASTE_BACK.txt"
( trap '' INT HUP; analyze "$OUT" "$DEVICE" "$MPS_ON" "$PAR" "$NCPU" | tee "$OUT/ANALYSIS.txt"; exit "${PIPESTATUS[0]}" ) >> "$S"
_arc=$?
say "=== wrote $S"
cat "$S" | sed -n '/^=== RUNS/,$p'
[[ "$_arc" == 0 ]] && ( trap '' INT HUP; paste_back )
if [[ "$_arc" != 0 || ! -s "$OUT/PASTE_BACK.txt" ]]; then
  if [[ "$_arc" != 0 ]]; then
    _why="the analysis failed (exit $_arc"
    (( _arc > 128 )) && _why="$_why: killed by signal $(( _arc - 128 ))$( (( _arc == 137 )) && echo ', the OOM killer?')"
    _why="$_why; its error is in the fleet log)"
  else
    _why="the analysis wrote no block ($OUT/PASTE_BACK.txt is missing: a full disk? its error is in the fleet log)"
  fi
  say "!! THE FLEET IS NOT FINISHED: $_why. Every run had ended; $GW_CMD --analyze reads them again."
  fail_back "$_why; every run had ended, and $GW_CMD --analyze reads them again"
  exit 1
fi
( trap '' INT HUP; pack )
GW_FINISHED=1
