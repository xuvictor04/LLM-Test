#!/bin/bash
# ==================================================================================================
# THE OWNER'S GPU FLEETS, EACH RUN AS A FLEET THAT FILLS THE CARD: Q-WORLD-10's WORLD EXPERIMENT,
# 03b S0b's RETOK SHIP RULE, THE WHOLE-EPOCH WORLD RE-RUN'S SIZING, THE RETOK CADENCE'S HELD-OUT RE-READ
# AND THE FIRST POST-TRAINING SESSIONS
# ==================================================================================================
# EXP CHOOSES THE EXPERIMENT, AND ANY OTHER VALUE IS REFUSED BY NAME (Proposal 05 §8 1.5): a
# misspelled EXP used to fall through to the WORLD fleet, which then ran under the label meant for
# another one.
#   EXP=world        the default: Q-WORLD-10's four arms, the 2026-09-24 fleet (below)
#   EXP=retok        03b S0b's ship rule for TOK_RETOK_EVERY, with kept checkpoints (§8 2.1)
#   EXP=world_epoch  the whole-epoch, phase-traversing WORLD re-run: sized, and refused until O13's two
#                    WORLD levers are built
#   EXP=heldout      E2's retok part (§8 6.3a): the shipped cadence against k0 on SR0's held-out probe,
#                    per area, with O14's first remedy arm (below)
#   EXP=session      the first post-training sessions (§8 5.3a): P, P+parent and a nuisance twin per
#                    parent, from EXP=heldout's finals onto a fifth synthetic area, and W (below)
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
#     KEEP_CKPT=1 bash gpu_world.sh                       # + each run's final and best checkpoints (below)
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
# run -- AND, SINCE 04-6.2's FLIP (2026-09-29), THE RETENTION PROBE'S BEST SAVES BESIDE IT: with
# CKPT_DIR set an armed probe writes a full checkpoint at every new best reading, the first always
# one, as ckpt.pt.best with ckpt.pt.best.prev behind it (and CKPT_BEST_KEEP's slots), so at
# EXP=world and EXP=world_epoch a run leaves up to three checkpoint files at the shipped settings.
# The disk check counts them (ckpt_files, BEST_FILES) and the banner says so; EXP=retok's pins turn
# the probe off, and its runs write none. At EXP=retok every run gets
# CKPT_DIR=$OUT/ckpt/<arm>.s<seed>: the act arms save once, at the end (CKPT_EVERY 0); k0, k0_nuis
# and k0_rerun save every KEEP_EVERY windows (default: the gcd of the act cadences, 1000); and k0's
# saves are HARD-LINKED ASIDE as $OUT/ckpt/keep/k0.s<seed>.w<step>, with the vocabulary beside each
# as k0.s<seed>.w<step>.dyntok.json, because CKPT's ring keeps only
# ckpt.pt and ckpt.pt.prev (src/ckpt/api.py::save). A periodic save lands on the window an act of that
# cadence fires at (j x K + 1) and leaves the run's losses bit-identical (tests/test_continuation.py
# S11), so arm - k0 pairs a saving control with arms that save only at the end. The kept copies are
# the spike test's maturity-matched control (register note retok fleet (4)) and parents for
# continuations:
#     CKPT_RESUME=gpu_retok_out/ckpt/keep/k0.s0.w3001 CKPT_DIR=<a NEW directory> OMP_NUM_THREADS=1 \
#         RUN_SEED=0 RUN_DEVICE=cuda DATA_STREAM_BYTES=3780000 TOK_RETOK_EVERY=0 <the fleet's EXTRA> \
#         DATA_SYNTH_HOLDOUT=0 EVAL_RETENTION_EVERY=0 DATA_TRUST=off python3 run.py
# WITH THE RUN'S OWN SEED, DEVICE AND STREAM (2026-09-27, build 1.5's review): the script sets them on
# every run and EXTRA does not carry them, and a resume without them is refused -- the segmentation
# rebuilt from the checkpoint's log disagrees with the parent's epoch. DATA_STREAM_BYTES is WINDOWS x
# 189 at EXP=retok (3780000 at 20,000 windows); the block's "resume one" line prints them filled in.
# AND WITH THE FLEET'S PINS (2026-09-29, 04-Q5's pin rule; see EXP=retok below): a kept copy was
# written at DATA_SYNTH_HOLDOUT=0, mid-epoch, and a continuing resume onto the shipped DATA_SYNTH_HOLDOUT
# is refused by name, because the admitted block redraws the stream the parent was reading. The block's
# line carries the pins the fleet recorded in SUMMARY.txt, and for a fleet that recorded none -- one
# launched before the flip, as the 2026-09-27 retok fleet was -- the pins the checkout running the
# analysis declares (the Stage 3 merge, 2026-09-29): its runs had those features off.
# RESUME INTO A NEW CKPT_DIR, NEVER THE KEPT ONE: a save there rotates the kept copy away, and the
# read-only bit the index sets on kept files stops no rename. Nothing is written under runs/, and a
# SIGUSR1 save lands in the run's own CKPT_DIR (at EXP=world by default there is none, so it saves
# nothing). A hard link costs no disk until the ring drops its own name for the file; the fleet's
# checkpoint disk is estimated from the smoke's largest checkpoint before FILL adds seeds.
# DEVICE=cpu runs the same pipeline without the GPU parts; it exists so the script itself can be
# tested on a machine without a card, and its numbers mean nothing about the GPU.
#
# EXP=retok RUNS 03b S0b's SHIP-RULE MEASUREMENT INSTEAD (2026-09-26): which TOK_RETOK_EVERY ships,
# now that the mid-epoch act performs a retok. Arms k0 (0, the control: no act), k3000 (the interim
# value the 2026-09-27 fleet replaced), k1000 (the shipped value since that fleet's DECISION), and
# k0_nuis (0 again, with SIG_WARMUP=801 -- a small real perturbation neither the act
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
# the incumbent is RETOK_INCUMBENT, the shipped default -- 1000 since the 2026-09-27 fleet's DECISION,
# the interim 3000 before it. A challenger replaces it only if the challenger does not FAIL and (the
# incumbent FAILs, or the one-sided 95% upper bound of the whole-run paired challenger - incumbent is
# below 0); otherwise the incumbent stays, UNRESOLVED readings included. 0 is never shipped by the rule:
# if every cadence of a fleet of two or more FAILs, the DECISION is ESCALATE (the act stays ON at the
# incumbent until the owner answers; the remedy arms run next). A FLEET OF ONE CADENCE NEVER ESCALATES
# (2026-09-28, review of 88d3fae): O14 escalates only when both of its cadences and every remedy arm
# FAIL, and a re-read of the shipped cadence alone (RETOK_ARMS=1000) cannot show the other one FAILing.
# The incumbent's FAIL there reads "<c> FAILs ...: it does not ship; <O14's other cadence> and the
# remedy arms run next" (register O14, note retok fleet (3): the shipped cadence stops firing), and a
# lone challenger that FAILs leaves the incumbent, unread, as it stands. M = max over seeds
# |k0 - k0_nuis| and the per-arm means are printed beside the rule and decide nothing. RETOK_INCUMBENT
# is read when the analysis runs, like EPS: --analyze of the 2026-09-27 archive reads its DECISION again
# at RETOK_INCUMBENT=3000 -- on a copy unpacked in a scratch directory, never beside the committed
# archive, since --analyze rewrites ANALYSIS.txt and the block and repacks <name>_<date>.tgz beside OUT
# -- and an operation check at a shorter shape (a CPU fleet whose cadences are 40 and 20) names its own.
# RETOK_ARMS names the act cadences (arm k<c> each; default "3000 1000", the 2026-09-27 fleet's arms in
# its order), and COOLDOWN_ARM=<v> adds k<fastest>_cd<v> at FAB_COOLDOWN=<v>, beside the rule and never a
# ship candidate: C13's reading of whether FAB's cooldown costs. It is read against its own cadence's
# arm, k<fastest>_cd<v> - k<fastest> paired over the seeds, per phase by the eps rule and over the whole
# run by the one-sided 95% upper bound (below 0: the shorter cooldown is significantly better), and
# enters no Holm with the cadences. FAB_COOLDOWN is the blackout after each act AND the spacing between
# growth firings and the new_frac budget's window, so the arm prices the cooldown as a whole, not the
# blackout alone (a k0 cooldown control, not built, would separate them). CALIBRATION RUNS 600 WINDOWS HERE
# (CAL_WINDOWS; 150 at EXP=world), past FAB's
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
# pre-Levels when this tree lacks DOM_LEVELS or the fleet turns it off (C12). 04-Q5's PIN RULE APPLIES
# (2026-09-29): this fleet's arms and its nuisance margin pair with runs made before SR0's defaults
# flipped (DATA_SYNTH_HOLDOUT on, EVAL_RETENTION_EVERY 1000, DATA_TRUST 'observe'), so every retok run
# here -- smoke, calibration, fleet and rerun -- carries DATA_SYNTH_HOLDOUT=0 EVAL_RETENTION_EVERY=0
# DATA_TRUST=off, and so does the block's resume line. Each pin is set only where this tree declares
# its lever, read off src/ at launch as LEVELS is, so a checkout from before a flip gets no UNREAD name
# (spine/assemble.py's typo net); the banner and SUMMARY.txt print the pins that ran. A fleet already
# started on an earlier commit is not pulled mid-fleet: its runs pair with each other only.
#     EXP=retok bash gpu_world.sh                         # 20,000 windows, seeds 0-2, auto-filled
#     EXP=retok RETOK_ARMS="3000 1000 500" bash gpu_world.sh   # another cadence set
#     EXP=retok COOLDOWN_ARM=100 bash gpu_world.sh        # + k1000_cd100 (the blackout alarm's arm)
#     EXP=retok RETOK_ARMS=1000 COOLDOWN_ARM=100 SEEDS="0 1 2 3 4" KEEP_CKPT=0 bash gpu_world.sh
#                                                         # C13's cooldown fleet at the shipped cadence
#     EXP=retok KEEP_CKPT=0 bash gpu_world.sh             # no checkpoints: the spike test loses its control
#     EXP=retok bash gpu_world.sh --analyze
#     EXP=retok EPS=0.02 bash gpu_world.sh --analyze      # the same runs read against another eps
#
# EXP=world_epoch IS THE WORLD RE-RUN'S SHAPE, SIZED AND GUARDED BUT NOT RUN (register note WORLD 3-4,
# §8 6.5). The 2026-09-24 fleet read phase 1 of a 20 MB stream and never saw an area arrive or fade.
# This shape reads ONE WHOLE EPOCH of a WINDOWS x 189-byte stream (EPOCH_BYTES), as EXP=retok does, with
# the window cap out of reach and "RAN OUT OF STREAM" replaced by a window-cap flag, so every arm
# crosses all four phases. It pins TOK_RETOK_EVERY (PIN_RETOK, 1000, the shipped cadence since the
# 2026-09-27 retok fleet; S0b-ship: every dependent experiment pins and labels it) and
# DATA_DRAW=planned (note WORLD 3), and -- its pre-registered rule reads SR0's retention probe on a
# synthetic held-out block -- DATA_SYNTH_HOLDOUT=1 and EVAL_RETENTION_EVERY=PROBE_EVERY (700: 04-6.2's
# cap, the shortest phase's windows / 5 on the 3.78 MB shape, 701-721 at k1000 and 722-742 at k3000 in
# the 2026-09-27 retok fleet, written as a number, never computed at run time), and every run writes
# its reading series beside its curve (run.py --probe-series). With KEEP_CKPT=1 each run's final save
# is joined by the probe's best saves, ckpt.pt.best and .best.prev (and CKPT_BEST_KEEP's slots), which
# the disk check budgets (the flip's review, 2026-09-29). 04-Q5's pin rule does not apply here: the
# arms pair only with each other, in one commit. SR0 IS BUILT (2026-09-29) AND THE GUARD STAYS,
# RETARGETED: the re-run is five arms (fb_off, fb_on, skip, world_off and detached; §8 6.5), after
# O13's two WORLD levers are built with CPU known answers -- the forecast bound (WORLD_FORECAST_BOUND)
# and the input gradient (WORLD_INPUT_GRAD, whose 'detached' is the fifth arm), provisional names,
# neither in this tree -- so it prints its sizing and the pre-registration, says which of the two this
# tree declares, and exits 2 having written nothing, until GO_WORLD_EPOCH=1 (that build adds the fifth
# arm and lifts the guard; before it, the four arms here run as an operation check only).
#     EXP=world_epoch bash gpu_world.sh                   # the sizing and the pre-registration; exit 2
#     EXP=world_epoch GO_WORLD_EPOCH=1 bash gpu_world.sh  # an operation check, until O13's build
#
# EXP=heldout IS E2's RETOK PART AS ITS OWN FLEET (Proposal 05 §8 6.3a, O14; 2026-10-02): whether the
# shipped cadence keeps each older area's held-out text within eps, on SR0's probe. Arms k0
# (TOK_RETOK_EVERY=0), k<c> and k<c>_mn -- c is PIN_RETOK, the shipped 1000, and _mn adds O14's first
# remedy arm, TOK_MINT_NOVEL=1.0 -- at seeds 0-6, and k0_rerun: 22 runs, each one whole WINDOWS x
# 189-byte epoch, sized as EXP=world_epoch is. Every run pins DATA_DRAW=planned DATA_SYNTH_HOLDOUT=1
# EVAL_RETENTION_EVERY=PROBE_EVERY EVAL_HOLDOUT_WINDOWS=256 EVAL_RETENTION_N=24 EVAL_GENERATE=0
# TOK_MINT_NOVEL=0 after EXTRA, with its arm's settings after them, and writes its probe series and
# flush bytes beside its curve. KEEP_CKPT is on: each run's final save, and the probe's best saves beside
# it, are the next test's parents (no periodic save; those are EXP=retok's k0 family's alone). FILL is
# 0, since the seeds are capped. THE READING: each area's R reading through the memory-off closure, report
# half -- the last 'boundary' row of curves/<run>.probe.json -- arm - k0 paired by seed, by the eps rule
# with the areas as its cells (Bonferroni over them) and Holm across k<c> and k<c>_mn, each of its two looks
# (the 7 seeds; a top-up's pooled 11) at 0.025, half the rule's 0.05 (LOOK_ALPHA). The DECISION:
# k<c> PASS ends its B-provisional label on this source; k<c> FAIL with k<c>_mn PASS ships TOK_MINT_NOVEL
# 1.0; both FAIL: neither ships, c stays on and the next remedy arms run; UNRESOLVED below the cap of 11
# seeds prints the top-up's command, whose analysis reads both fleets' seeds where commit, card, torch
# and shape match (POOL_WITH, below). Beside the rule, deciding nothing: O14's per-phase prequential
# reading, memory-on minus memory-off, the time-integrated report gap from 20% of the stream, the
# end-state SD per area, n_live, the probe's seconds, data.trust.wall_s, readings per phase, the rates,
# and the act arms' finals with their sha256 (FINALS.sha256) and a line that packs them.
#     EXP=heldout SEEDS='0 1 2 3 4 5 6' FILL=0 bash tools/gpu_launch.sh --go
#     EXP=heldout SEEDS='7 8 9 10' FILL=0 OUT=gpu_heldout_topup_out POOL_WITH=gpu_heldout_out \
#         bash tools/gpu_launch.sh --go                   # a top-up, as the block prints it (with PAR)
#
# EXP=session IS THE FIRST POST-TRAINING SESSIONS (Proposal 05 §8 5.3a, O9, NEW-02, NEW-20; 2026-10-02): does
# learning a new area after training keep each older area within eps? Its parents are PARENT_ARM's finals
# (k<PIN_RETOK>, EXP=heldout's shipped arm; k1000_mn if TOK_MINT_NOVEL ships) at SEEDS: PARENTS=<a directory
# holding FINALS.sha256 and ckpt/<arm>.s<seed>, the held-out fleet's OUT or its unpacked finals>, every file
# sha256-checked before anything is written; without PARENTS a PARENTS STAGE trains them first, EXP=heldout's
# shape and pins, finals kept under $OUT/parents. Each parent then gets three SESSIONS -- P (pure-add), P_parent
# (P+parent: DATA_DRAW=replay DATA_REPLAY_SHARE=0.27 DATA_REHEARSE_PARENT=1, O9's provisional rehearsal) and P_twin
# (P at OPT_LR x 1.0001: the nuisance twin, read at every step; FAB_BIRTH_JITTER is read only at a growth birth,
# under 1% of births, and the GPU reruns are bit-exact) -- and the parent with the most experts a fourth, W (P at
# FAB_SLOTS = max(its slots, its n_live + W_HEADROOM), NEW-20's W). A session resumes its parent's final
# (CKPT_RESUME, RUN_SEED its seed, a new CKPT_DIR) into a second epoch (RUN_EPOCHS=2 DATA_RESAMPLE=1) with x5
# appended (DATA_AREAS=eng,py,num,c,x5 DATA_N_PROCESSES=5 and 5/4 of the parent's DATA_STREAM_BYTES, so every
# old held-out block stays the parent's; DATA_PHASE_SCHED=x5|x5|x5|x5) at OPT_LR_CONTINUE=as_logged, EXP=heldout's
# probe pins and the parent arm's settings, for SESSION_WINDOWS (5000) windows. The script's knobs are named
# clear of every package prefix; EXTRA may not move the session's data levers (refused by name). THE READING: per
# old area F = the session's R reading - its resume-start reading (memory-off, report half; the start reads the
# parent's final weights on the same pinned items, O2's anchor); P and P_parent over the parents by the eps rule,
# Holm across the two, at 0.025 a look; O9 takes, of those admitted, the lower x5 R reading paired by parent (a tie
# to the smaller worst-area mean F); UNRESOLVED below the cap of 11 prints a top-up's command (parents 7-10,
# trained by its parents stage); 5.1's SDs, W against P and the rest are reported beside it.
#     EXP=session SEEDS='0 1 2 3 4 5 6' FILL=0 PARENTS=gpu_heldout_out bash tools/gpu_launch.sh --go
#     EXP=session SEEDS='0 1 2 3 4 5 6' FILL=0 PARENT_ARM=k1000_mn PARENTS=gpu_heldout_out \
#         bash tools/gpu_launch.sh --go                   # if EXP=heldout's DECISION shipped TOK_MINT_NOVEL
#
# EVERY FLEET ENDS IN A BLOCK TO PASTE BACK AND AN ARCHIVE TO KEEP. The GPU box has a checkout and no
# push token (results/gpu_world_2026-09-24/ANALYSIS.txt was transcribed from its terminal by hand), so
# the end of every fleet, every --analyze and every early stop prints ONE block, from
# "==== PASTE THIS BACK ====" to "==== END ====", at most 80 lines, and writes it to
# $OUT/PASTE_BACK.txt: the commit, the card, the shape, the failed runs, and the result (at EXP=retok
# the per-seed bits/byte, each cadence's per-phase bounds and verdict, eps, the choice and why, M
# reported, rates, secondaries with the blackout split, and kept checkpoints; at EXP=heldout the per-seed
# held-out readings, each act arm's per-area bounds and verdict, the DECISION and, where it is UNRESOLVED,
# the top-up's command, what is reported beside it, and the finals' pack line; at EXP=session the per-parent F
# per old area, the anchor, each candidate's bounds and verdict, O9's reading of x5, the DECISION, a top-up's
# command, and what is reported beside it). Paste it
# into the chat. $OUT is then packed beside itself as <name>_<launch date>.tgz -- logs, curves, smoke,
# calibration, SUMMARY, ANALYSIS, the block, KEPT.txt; never a checkpoint -- which the owner keeps
# (the 2026-09-24 precedent, gpu_world_2026-09-24.tgz, and the layout tools/read_fleet_archive.sh reads).
set -u

_EXP_GIVEN=${EXP+x}
EXP=${EXP:-world}
case "$EXP" in
  world|retok|world_epoch|heldout|session) ;;
  *) echo "!! EXP='$EXP' is not an experiment this script runs: world (the default), retok, world_epoch," \
          "heldout or session. Nothing was started."; exit 2 ;;
esac
case "$EXP" in
  retok) _o=gpu_retok_out; _s="0 1 2" ;; world_epoch) _o=gpu_world_epoch_out; _s="0 1 2 3 4" ;;
  heldout) _o=gpu_heldout_out; _s="0 1 2 3 4 5 6" ;; session) _o=gpu_session_out; _s="0 1 2 3 4 5 6" ;;
  *) _o=gpu_world_out; _s="0 1 2 3 4" ;;
esac
_OUT_GIVEN=${OUT:+x}
OUT=${OUT:-$_o}
WINDOWS=${WINDOWS:-20000}
SEEDS=${SEEDS:-$_s}
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
# every phase of the stream, and a window cap below the epoch would stop it inside one. So does
# EXP=heldout: its endpoint is each area's reading at the end of the epoch. And EXP=session's parents, which are
# EXP=heldout's runs (its sessions resume them at 5/4 of their stream, for SESSION_WINDOWS windows).
if [[ "$EXP" == retok ]]; then
  BYTES=${RETOK_BYTES:-$(( WINDOWS * 189 ))}
  RUN_WIN=$(( WINDOWS * 3 ))
elif [[ "$EXP" == world_epoch || "$EXP" == heldout || "$EXP" == session ]]; then
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
# FILL IS 0 AT EXP=heldout AND EXP=session, WHOSE SEEDS ARE CAPPED (§8 6.3a, 5.3a): FILL adds seeds to fill spare
# slots, up to MAX_SEEDS, past a pre-registered cap.
FILL=${FILL:-$([[ "$EXP" == heldout || "$EXP" == session ]] && echo 0 || echo 1)}
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
KEEP_CKPT=${KEEP_CKPT:-$([[ "$EXP" == retok || "$EXP" == heldout || "$EXP" == session ]] && echo 1 || echo 0)}
KEEP_POLL=${KEEP_POLL:-1}                  # seconds between the kept-checkpoint watcher's looks
PIN_RETOK=${PIN_RETOK:-1000}               # the shipped TOK_RETOK_EVERY: every EXP=world_epoch run's pin, EXP=heldout's act arms'
POOL_WITH=${POOL_WITH:-}                   # EXP=heldout and session: a top-up's first fleet (its OUT), whose seeds it reads with its own
PROBE_EVERY=${PROBE_EVERY:-700}            # EXP=world_epoch, heldout and session: the EVAL_RETENTION_EVERY every run pins (04-6.2's cap)
PARENTS=${PARENTS:-}                       # EXP=session: a directory of the parents' finals (FINALS.sha256 and ckpt/); '' = a parents stage
PARENT_ARM=${PARENT_ARM:-k$PIN_RETOK}      # EXP=session: the parents' arm, EXP=heldout's shipped one (k<c> or k<c>_mn)
SESSION_WINDOWS=${SESSION_WINDOWS:-5000}   # EXP=session: the windows a session trains (--max-windows)
W_HEADROOM=${W_HEADROOM:-2048}             # EXP=session: W's slots, max(the parent's slots, its n_live + this) (NEW-20's H)
GO_WORLD_EPOCH=${GO_WORLD_EPOCH:-0}
[[ "$PROBE_EVERY" =~ ^[1-9][0-9]*$ ]] \
  || { echo "!! PROBE_EVERY='$PROBE_EVERY' is not a positive window count (the retention cadence EXP=world_epoch and heldout pin). Nothing was started."; exit 2; }
[[ "$PIN_RETOK" =~ ^[1-9][0-9]*$ ]] \
  || { echo "!! PIN_RETOK='$PIN_RETOK' is not a positive cadence (EXP=world_epoch's pin, EXP=heldout's act arms). Nothing was started."; exit 2; }
# EXP=session's KNOBS, AND THE LEVERS ITS SESSIONS PIN (§8 5.3a). EXTRA reaches the parents stage and every
# session, so a data lever there would train the parents on one stream and resume them on another: refused.
if [[ "$EXP" == session ]]; then
  [[ "$PARENT_ARM" =~ ^k[1-9][0-9]*(_mn)?$ ]] \
    || { echo "!! PARENT_ARM='$PARENT_ARM' is not one of EXP=heldout's act arms (k<c> or k<c>_mn): the parents are its shipped arm's finals. Nothing was started."; exit 2; }
  [[ "$SESSION_WINDOWS" =~ ^[1-9][0-9]*$ ]] \
    || { echo "!! SESSION_WINDOWS='$SESSION_WINDOWS' is not a positive window count (a session's --max-windows). Nothing was started."; exit 2; }
  [[ "$W_HEADROOM" =~ ^[1-9][0-9]*$ ]] \
    || { echo "!! W_HEADROOM='$W_HEADROOM' is not a positive slot count (W's FAB_SLOTS, max(the parent's slots, its n_live + W_HEADROOM)). Nothing was started."; exit 2; }
  for _l in DATA_AREAS DATA_N_PROCESSES DATA_SOURCE DATA_PHASE_SCHED DATA_PHASES RUN_EPOCHS DATA_RESAMPLE \
            OPT_LR_CONTINUE CKPT_RESUME CKPT_DIR; do
    [[ " $EXTRA " == *" $_l="* ]] && { echo "!! EXTRA sets $_l, which EXP=session's parents and sessions pin (§8 5.3a). Nothing was started."; exit 2; }
  done
  [[ "$PARENTS" =~ [[:space:]] ]] \
    && { echo "!! PARENTS='$PARENTS' holds whitespace, and its path rides inside the job lines, which are split on whitespace. Nothing was started."; exit 2; }
  [[ "$FILL" == 1 ]] \
    && { echo "!! FILL=1: EXP=session's seeds are its parents', pre-registered and capped (§8 5.3a), and FILL would add seeds with no parent. Nothing was started."; exit 2; }
fi
# THE eps RULE'S TWO READING-TIME SETTINGS (EXP=retok's analysis; O2, O14). They are read when the
# analysis runs, not recorded at launch, so --analyze can read the same runs against another eps; the
# analysis prints both.
EPS=${EPS:-0.05}                           # eps, bits/byte: a cadence FAILs past it, PASSes within it
RETOK_INCUMBENT=${RETOK_INCUMBENT:-1000}   # the incumbent cadence: the shipped default (O14; 3000 until 2026-09-27)
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
    # O14's FIRST REMEDY ARM (§8 6.3a, EXP=heldout): the cadence with TOK_MINT_NOVEL at 1.0. Ahead of
    # k[1-9]*, which would read k1000_mn as TOK_RETOK_EVERY=1000_mn.
    k[1-9]*_mn) local c=${1%_mn}; echo "TOK_RETOK_EVERY=${c#k} TOK_MINT_NOVEL=1.0" ;;
    k[1-9]*)   echo "TOK_RETOK_EVERY=${1#k}" ;;
    # EXP=session's SESSIONS (§8 5.3a), each after the session's pins and its parent arm's settings: P names
    # the pinned pure-add draw; P_parent rehearses the parent (O9's provisional preset); P_twin is P at OPT_LR x
    # 1.0001 (TWIN_LR); W is P at W_SLOTS, known once the parents are read.
    P)         echo "DATA_DRAW=planned" ;;
    P_parent)  echo "DATA_DRAW=replay DATA_REPLAY_SHARE=0.27 DATA_REHEARSE_PARENT=1" ;;
    P_twin)    echo "OPT_LR=$TWIN_LR" ;;
    W)         [[ -n "${W_SLOTS:-}" ]] || { echo "!! arm_env: W's FAB_SLOTS is not known before the parents are read" >&2; return 1; }
               echo "FAB_SLOTS=$W_SLOTS" ;;
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
elif [[ "$EXP" == heldout ]]; then
  BASE_ARMS="k0 k$PIN_RETOK k${PIN_RETOK}_mn"; CTRL=k0
  KEEP_EVERY=${KEEP_EVERY:-0}
elif [[ "$EXP" == session ]]; then
  # THE THREE SESSIONS EVERY PARENT GETS; W, at one parent, is added where the parents are read. THE TWIN'S RATE
  # is the fleet's OPT_LR x 1.0001 -- EXTRA's, else this environment's, else the lever's declared default, read
  # off the fleet's code as LEVELS is -- at 9 significant digits: 0.0020002 at the shipped 0.002.
  BASE_ARMS="P P_parent P_twin"; CTRL=P
  KEEP_EVERY=${KEEP_EVERY:-0}
  _lr=$(echo " $EXTRA " | tr ' ' '\n' | sed -n 's/^OPT_LR=//p' | tail -1)
  [[ -n "$_lr" ]] || _lr=$(printenv OPT_LR 2>/dev/null)
  [[ -n "$_lr" ]] || _lr=$(sed -n 's/^    lr = Lever( *\([0-9.eE+-]*\) *,.*/\1/p' "$CODE_DIR/src/opt/levers.py" 2>/dev/null | head -1)
  TWIN_LR=$(awk -v x="$_lr" 'BEGIN { if (x + 0 > 0) printf "%.9g", x * 1.0001 }')
  [[ -n "$TWIN_LR" ]] || { echo "!! EXP=session: the fleet's OPT_LR ('$_lr') is not a positive rate, so P_twin's (x 1.0001) cannot be set. Nothing was started."; exit 2; }
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
# EXP=world PINS NONE (2026-09-28, review of 88d3fae), so its command lines stay the ones it ran before:
# its four arms set only WORLD_ levers, and its runs act at the tree's TOK_RETOK_EVERY -- 1000 since the
# 2026-09-27 retok fleet, about 19 acts in a 20,000-window run where 3000 gave about 6. A re-run of it
# that decides anything names the cadence in EXTRA, where SUMMARY and the block record it (S0b-ship:
# every dependent experiment pins and labels TOK_RETOK_EVERY). EXP=retok's arms set it themselves.
EXP_ENV=""
[[ "$EXP" == world_epoch ]] && EXP_ENV="TOK_RETOK_EVERY=$PIN_RETOK DATA_DRAW=planned DATA_SYNTH_HOLDOUT=1 EVAL_RETENTION_EVERY=$PROBE_EVERY"
# EXP=heldout's PINS (§8 6.3a): the probe on at its cap and its boundary reading at 128 report windows
# per area, the in-run reading at 12, no generation, and plain minting -- the arms set the cadence, and
# k<c>_mn TOK_MINT_NOVEL, after them. 04-Q5's pin rule does not apply: the arms pair with each other.
[[ "$EXP" == heldout ]] && EXP_ENV="DATA_DRAW=planned DATA_SYNTH_HOLDOUT=1 EVAL_RETENTION_EVERY=$PROBE_EVERY EVAL_HOLDOUT_WINDOWS=256 EVAL_RETENTION_N=24 EVAL_GENERATE=0 TOK_MINT_NOVEL=0"
# EXP=session's PINS (§8 5.3a): EXP=heldout's, on the parents stage and on every session, so a session pins again
# the report items its parent read. The parent arm's settings follow them on every run (TOK_MINT_NOVEL 1.0 at
# k<c>_mn), then a session's own (SESS_ENV: a second epoch, x5 appended at 5/4 of the parents' stream, so 945,000
# bytes a process at 3,780,000 and no old block moves; pure-add; the rate as logged) and its arm's.
if [[ "$EXP" == session ]]; then
  EXP_ENV="DATA_DRAW=planned DATA_SYNTH_HOLDOUT=1 EVAL_RETENTION_EVERY=$PROBE_EVERY EVAL_HOLDOUT_WINDOWS=256 EVAL_RETENTION_N=24 EVAL_GENERATE=0 TOK_MINT_NOVEL=0"
  _pb=$(echo " $EXTRA " | tr ' ' '\n' | sed -n 's/^DATA_STREAM_BYTES=//p' | tail -1)
  PBYTES=${_pb:-$BYTES}
  [[ "$PBYTES" =~ ^[1-9][0-9]*$ ]] || { echo "!! EXP=session: the parents' DATA_STREAM_BYTES ('$PBYTES') is not a byte count. Nothing was started."; exit 2; }
  SBYTES=$(( 5 * (PBYTES / 4) ))
  SESS_ENV="RUN_EPOCHS=2 DATA_RESAMPLE=1 DATA_AREAS=eng,py,num,c,x5 DATA_N_PROCESSES=5 DATA_STREAM_BYTES=$SBYTES DATA_PHASE_SCHED=x5|x5|x5|x5 OPT_LR_CONTINUE=as_logged"
fi
# 04-Q5's PIN RULE AT EXP=retok (2026-09-29): the three levers whose defaults flipped, at the values
# that restore the tree before them -- each only where this tree declares its lever, read off the
# fleet's code at launch as LEVELS is below. A checkout from before a flip then gets no name its lever
# assembly prints UNREAD for (spine/assemble.py's typo net only warns, so the run would go on at the
# default), and its default is the pinned value already. The register adds DATA_DRAW=planned "if that
# flips"; it has not. TREE_PINS is read at any EXP: --analyze gives it to a resume line (below).
TREE_PINS=""
grep -qE "^ +synth_holdout = Lever\(" "$CODE_DIR/src/data/levers.py" 2>/dev/null && TREE_PINS="DATA_SYNTH_HOLDOUT=0"
grep -qE "^ +retention_every = Lever\(" "$CODE_DIR/src/eval/levers.py" 2>/dev/null && TREE_PINS="$TREE_PINS${TREE_PINS:+ }EVAL_RETENTION_EVERY=0"
grep -qE "^ +trust = Lever\(" "$CODE_DIR/src/data/levers.py" 2>/dev/null && TREE_PINS="$TREE_PINS${TREE_PINS:+ }DATA_TRUST=off"
[[ "$EXP" == retok ]] && EXP_ENV="$TREE_PINS"
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
# THE k0 FAMILY'S PERIODIC SAVES ARE EXP=retok's ALONE (2026-10-02, §8 6.3a): the act windows they land
# on are its spike test's control. An arm named k0 at any other EXP saves once, at the end, as every
# other arm does (EXP=heldout's k0 did a periodic save in the smoke, and its budget divided by 0, below).
ckpt_env() {  # name seed base-dir [smoke]
  [[ "$KEEP_CKPT" == 1 ]] || return 0
  local every=0
  case "$EXP:$1" in
    retok:k0|retok:k0_nuis|retok:k0_rerun)
      every=$KEEP_EVERY; [[ -n "${4:-}" ]] && every=$(( SMOKE_WINDOWS / 2 > 0 ? SMOKE_WINDOWS / 2 : 1 )) ;;
  esac
  echo "CKPT_DIR=$3/$1.s$2 CKPT_EVERY=$every"
}
# >>> THE BEST SAVES' BUDGET (2026-09-29, the flip's review). tests/test_gpu_world.py F28 execs this
# block by its two marker lines, with EXP, EXTRA, EXP_ENV, WINDOWS, KEEP_EVERY and CODE_DIR set, in a
# tree of its own.
# THE RETENTION PROBE'S BEST SAVES ARE CHECKPOINTS TOO (register R22; docs/04_CONTRACT.md Q-EVAL-12).
# Wherever a run's CKPT_DIR is set and its probe is armed, CKPT.Retention saves a full checkpoint at
# every new best reading -- the first reading always one -- as ckpt.pt.best, the one before it rotated
# onto ckpt.pt.best.prev, each with its vocabulary beside the directory; and CKPT_BEST_KEEP=N adds the
# slots .best1 ... .bestN, each rotating onto its own .prev (src/ckpt/api.py::save): 2 + 2N files at
# most. The probe is armed where this tree declares EVAL_RETENTION_EVERY and a run's value is above 0:
# the last one run_job sets -- EXTRA's, then EXP_ENV's (EXP=retok's pin is 0, EXP=world_epoch's
# PROBE_EVERY) -- else this environment's, else the lever's declared default, read off the fleet's code
# at launch as LEVELS is. So EXP=world counts them at the shipped 1000 and EXP=world_epoch at its pin,
# EXP=retok never, and a checkout from before 04-6.2's flip, whose default is 0, not at EXP=world
# either. A value this cannot read is counted armed, and a probe that pins nothing writes none: at most,
# as ckpt_files is. The count is of checkpoint files, as the ring's is; the small vocabulary files ride
# with them.
_setting() {  # NAME -> the value a run sees: the last NAME= in EXTRA and EXP_ENV, else the environment's
  local v
  v=$(echo " $EXTRA $EXP_ENV " | tr ' ' '\n' | sed -n "s/^$1=//p" | tail -1)
  if [[ -n "$v" ]]; then echo "$v"; else printenv "$1" 2>/dev/null; fi
}
BEST_FILES=0
BEST_KEEP=0
if grep -qE "^ +retention_every = Lever\(" "$CODE_DIR/src/eval/levers.py" 2>/dev/null; then
  _pe=$(_setting EVAL_RETENTION_EVERY)
  [[ -n "$_pe" ]] || _pe=$(sed -n '/^ *retention_every = Lever(/{s/.*Lever( *\([0-9][0-9]*\).*/\1/p;n;s/^ *\([0-9][0-9]*\) *,.*/\1/p;}' \
                             "$CODE_DIR/src/eval/levers.py" 2>/dev/null | head -1)
  if ! [[ "$_pe" =~ ^[0-9]+$ ]] || (( 10#$_pe > 0 )); then
    BEST_KEEP=$(_setting CKPT_BEST_KEEP)
    [[ -n "$BEST_KEEP" ]] || BEST_KEEP=$(sed -n 's/^ *best_keep = Lever( *\([0-9][0-9]*\).*/\1/p' "$CODE_DIR/src/ckpt/levers.py" 2>/dev/null | head -1)
    [[ "$BEST_KEEP" =~ ^[0-9]+$ ]] && BEST_KEEP=$(( 10#$BEST_KEEP )) || BEST_KEEP=0
    BEST_FILES=$(( 2 + 2 * BEST_KEEP ))
  fi
fi
# HOW MANY CHECKPOINT FILES A RUN LEAVES AT MOST: at EXP=retok k0 its kept saves plus the ring's two and
# the rest of the k0 family the ring's two; every other run its one final save -- each with the probe's
# best saves beside them, BEST_FILES, 0 where no probe is armed (at EXP=retok, whose pins turn it off,
# always). ONLY AT EXP=retok (2026-10-02, §8 6.3a): an arm named k0 elsewhere divided by KEEP_EVERY 0,
# which ended jobs_need's sum with an error, and the disk check went on with 0 GB needed.
ckpt_files() {  # name
  case "$EXP:$1" in
    retok:k0) echo $(( (11 * WINDOWS + 10 * KEEP_EVERY - 1) / (10 * KEEP_EVERY) + 2 + BEST_FILES )) ;;
    retok:k0_nuis|retok:k0_rerun) echo $(( 2 + BEST_FILES )) ;;
    *) echo $(( 1 + BEST_FILES )) ;;
  esac
}
# <<< THE BEST SAVES' BUDGET

plan_banner() {  # the fleet's shape, as SUMMARY records it and the EXP=world_epoch guard prints it
  echo "=== $WINDOWS windows per run, DATA_STREAM_BYTES=$BYTES, seeds: $SEEDS, EXTRA='$EXTRA'"
  if [[ "$EXP" == session ]]; then
    # A SESSION'S CAP IS ITS --max-windows; the first line's windows and stream are the parents' shape.
    echo "=== plan: EXP=$EXP; arms $BASE_ARMS, plus W at the parent with the most experts; window cap $SESSION_WINDOWS;" \
         "CAL_WINDOWS $CAL_WINDOWS; LM_CTX $CTX"
    if [[ -n "${PARENTS_ABS:-}" ]]; then
      echo "=== parents: $PARENT_ARM at seeds $SEEDS, from $PARENTS_ABS ($PARENTS_CHECKED file(s) sha256-checked against" \
           "its FINALS.sha256)"
    else
      echo "=== parents: $PARENT_ARM at seeds $SEEDS, a parents stage first: one whole epoch each (window cap $RUN_WIN)," \
           "these pins and $(arm_env "$PARENT_ARM"), finals kept under $OUT/parents/ckpt"
    fi
    echo "=== session: $SESSION_WINDOWS windows, resumed from its parent's final at its seed, the pins and the parent" \
         "arm's settings, then $SESS_ENV; P_twin OPT_LR=$TWIN_LR; W FAB_SLOTS max(the parent's slots, its n_live +" \
         "$W_HEADROOM)"
  else
    echo "=== plan: EXP=$EXP; arms $BASE_ARMS, plus ${CTRL}_rerun at seed 0; window cap $RUN_WIN;" \
         "CAL_WINDOWS $CAL_WINDOWS; LM_CTX $CTX"
  fi
  if [[ "$KEEP_CKPT" == 1 && "$EXP" == retok ]]; then
    echo "=== kept checkpoints: ON, k0 family CKPT_EVERY=$KEEP_EVERY, act arms final only;" \
         "k0's saves hard-linked under $OUT/ckpt/keep"
  elif [[ "$KEEP_CKPT" == 1 && "$BEST_FILES" -gt 0 ]]; then
    echo "=== kept checkpoints: ON, one final checkpoint per run under $OUT/ckpt, and beside it the" \
         "retention probe's best saves (ckpt.pt.best and .best.prev$( (( BEST_KEEP > 0 )) &&
         echo ", and CKPT_BEST_KEEP=$BEST_KEEP's slots, each with its .prev")): up to" \
         "$(( 1 + BEST_FILES )) checkpoint files per run, all counted in the disk check"
  elif [[ "$KEEP_CKPT" == 1 ]]; then
    echo "=== kept checkpoints: ON, one final checkpoint per run under $OUT/ckpt"
  else
    echo "=== kept checkpoints: OFF"
  fi
  local p="" w
  for w in $EXP_ENV; do p="$p${p:+, }$w pinned"; done
  echo "=== pins: ${p:-none}"
  [[ -n "${POOL_ABS:-}" ]] && echo "=== pool: with $POOL_ABS (seeds $POOL_SEEDS): this fleet is its top-up, and its" \
       "analysis reads the two fleets' seeds together where commit, card, torch and shape match"
  echo "=== DOM Levels: $LEVELS"
  echo "=== §8 1.3 in this tree: counters ${TREE13:-none}; run.py --flush-bytes $FB_FLAG"
}

# bash gpu_world.sh --status : progress and time left of a fleet that is running (or finished),
# read off SUMMARY.txt and the logs. It changes nothing and is safe to run at any time.
# THE ANALYSIS, AS A FUNCTION so --analyze can re-run it on a finished (or interrupted) fleet.
analyze() {  # out device mps_on par ncpu
  if [[ "$EXP" == retok ]]; then analyze_retok "$@"; return; fi
  if [[ "$EXP" == heldout ]]; then analyze_heldout "$@"; return; fi
  if [[ "$EXP" == session ]]; then analyze_session "$@"; return; fi
  # EVERY EXP BUT world READS ONE WHOLE EPOCH: its runs are meant to end at the stream's end, so the
  # flags turn over (the 6th argument, the EXP). At EXP=world the output is what it always was.
  python3 - "$@" "$EXP" <<'PY'
import glob, json, math, os, re, statistics, sys
out, dev, mps_on, par, ncpu = sys.argv[1], sys.argv[2], sys.argv[3] == "1", int(sys.argv[4]), int(sys.argv[5])
exp = sys.argv[6] if len(sys.argv) > 6 else "world"
whole = exp != "world"

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
if exp == "world_epoch":
    print("  Q-WORLD-10's rule, shown for continuity; the pre-registered re-run rule (note WORLD 4) reads "
          "each run's retention-probe series (curves/<run>.probe.json), which this analysis does not read "
          "yet; the rule is owed with the fifth arm")
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
  GW_TREE_PINS="$TREE_PINS" gw_py retok "$1" "$CTX" "$(archive_path)" "$EPS" "$RETOK_INCUMBENT"
}

# E2's RETOK PART ON THE HELD-OUT PROBE (EXP=heldout; §8 6.3a): the reader, the rule and the block, in one
# program as EXP=retok's are. POOL_WITH given here reads a top-up with that first fleet (an archive unpacked
# elsewhere, say); else the one SUMMARY.txt records.
analyze_heldout() {  # out device mps_on par ncpu
  gw_py heldout "$1" "$CTX" "$(archive_path)" "$EPS" "$POOL_WITH" "$GW_HOME"
}

# THE FIRST POST-TRAINING SESSIONS (EXP=session; §8 5.3a): the reader, the rule and the block, one program as
# EXP=heldout's; POOL_WITH given here reads a top-up with that first fleet, else the one SUMMARY.txt records.
analyze_session() {  # out device mps_on par ncpu
  gw_py session "$1" "$CTX" "$(archive_path)" "$EPS" "$POOL_WITH" "$GW_HOME"
}

# THE BLOCK AND ITS PARTS (Proposal 05 §8 1.5). Modes: retok (the analysis above, which also writes
# PASTE_BACK.txt and KEPT.txt), heldout and session (their readers, which write PASTE_BACK.txt too), wrap
# (EXP=world and world_epoch: the header plus ANALYSIS.txt from '=== RUNS ===' on), fail (a stop before the
# analysis). Every header is read off SUMMARY.txt alone,
# so --analyze reproduces the block the fleet wrote.
gw_py() {  # mode out ...
  python3 - "$@" <<'PY'
import glob, hashlib, json, math, os, re, shlex, sys
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
    arm - k0 over the seeds with both readings}. Per phase the one-sided UPPER bound is
    mean + t(1 - alpha, n-1) x sd / sqrt(n) -- 95% at the default alpha; EXP=heldout reads each of its two
    looks at 0.025 -- and the LOWER bound mean - t(1 - a/N, n-1) x sd / sqrt(n): a
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
                        (n, m, m - t_quantile(1.0 - level / nph, n - 1) * se, m + t_quantile(1.0 - alpha, n - 1) * se))
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


# THE TWO CADENCES O14 NAMES: the interim 3000 and the arm 1000, which the 2026-09-27 fleet shipped. O14
# escalates only when both of them (and every remedy arm) FAIL against k0, so a fleet that holds one
# cadence names the other as what runs next when its own FAILs.
O14_CADENCES = ("k3000", "k1000")


def choose(cadences, verdicts, better, inc, remedy=None, room=False):
    """O14's choice. cadences: every cadence arm of the fleet (k<c>); verdicts: eps_rule's reading of the
    ones that acted; better: better_than's reading of the acted challengers against the incumbent arm
    `inc` (k1000 since the 2026-09-27 fleet's DECISION, k3000 before it). Returns (kind, arm, why), kind
    one of 'undecided' (no cadence acted), 'escalate' (every cadence of a fleet of two or more FAILs),
    'withdraw' (the incumbent, the fleet's only cadence, FAILs: it does not ship, and `why` names what
    runs next), 'replace' (arm replaces the incumbent) or 'stays' (the incumbent stays). A challenger
    replaces the incumbent only if it does not FAIL and (the incumbent FAILs, or it is significantly
    better); among several that qualify, the lowest upper bound against the incumbent. 0 is never an
    answer: it is the control, and the rule never ships it.
    A FLEET OF ONE CADENCE NEVER ESCALATES (2026-09-28, review of 88d3fae). O14 escalates when both of its
    cadences and every remedy arm FAIL against k0, and a cadence that FAILs does not ship: the other
    cadence or O14's remedy arms run next (register O14, note retok fleet (3)). At 88d3fae the cooldown
    fleet's re-read of the shipped 1000 alone (RETOK_ARMS=1000) would have taken its FAIL for ESCALATE, the
    act ON at 1000 until the owner answered, though 3000 never FAILed. A lone challenger that FAILs does
    not ship either, and the incumbent, which that fleet does not read, stays.
    THE REMEDY BRANCH (2026-10-02, §8 6.3a, EXP=heldout). `remedy` is the arm that runs `inc` with O14's first
    remedy arm on (k<c>_mn), read beside it per area on held-out text; `room` says seeds remain under the test's
    cap. The answer is 'pass' (inc PASSes: its B-provisional label ends on that source), 'remedy' (inc FAILs
    and the remedy PASSes: the remedy ships at inc), 'withdraw' (inc FAILs and the remedy FAILs, or is not
    read, or stays UNRESOLVED at the cap: neither ships, inc stays on meanwhile and the next remedy arms run),
    'topup' (inc UNRESOLVED, or inc FAILs and the remedy is UNRESOLVED, with room), 'unresolved' (inc
    UNRESOLVED at the cap: reported so, never escalated) or 'undecided' (inc did not act)."""
    if remedy is not None:
        iv, rv = verdicts.get(inc, {}).get("verdict"), verdicts.get(remedy, {}).get("verdict")
        if iv is None:
            return "undecided", None, f"{inc} did not act in these runs"
        if iv == "PASS":
            return "pass", inc, f"{inc} PASSes against k0"
        if iv == "FAIL" and rv == "PASS":
            return "remedy", remedy, f"{inc} FAILs against k0 and {remedy} PASSes"
        if iv == "FAIL" and not (rv == "UNRESOLVED" and room):
            return "withdraw", inc, (f"{inc} FAILs against k0 and {remedy} "
                                     + {"FAIL": "FAILs too", None: "did not act"}.get(rv, f"is {rv} at the seed cap"))
        if room:
            return "topup", None, (f"{inc} FAILs against k0 and {remedy} is UNRESOLVED" if iv == "FAIL" else
                                   f"{inc} is UNRESOLVED against k0")
        return "unresolved", inc, f"{inc} is UNRESOLVED against k0 at the seed cap"
    if not verdicts:
        return "undecided", None, "no cadence acted in these runs"
    if cadences and all(verdicts.get(a, {}).get("verdict") == "FAIL" for a in cadences):
        if len(cadences) > 1:
            return "escalate", None, "every cadence FAILs against k0 by the ε rule"
        if cadences[0] == inc:
            nxt = [c[1:] for c in O14_CADENCES if c != inc]
            return "withdraw", inc, (f"{inc} FAILs against k0 by the ε rule, and it is this fleet's only cadence; "
                                     f"{', '.join(nxt)} and the remedy arms run next (register O14, note retok "
                                     f"fleet (3)); no ESCALATE, which needs both cadences and every remedy arm "
                                     f"to FAIL")
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
    # C13's COOLDOWN ARM, READ AGAINST ITS OWN CADENCE'S ARM (2026-09-27: the retok fleet's blackout alarm
    # ordered it, and a mean beside the rule decides nothing). d = k<c>_cd<v> - k<c>, paired over the seeds
    # with both runs, on the rule's endpoint: per phase by the eps rule (does the shorter cooldown harm?),
    # and over the whole run by O2's "significantly better", the one-sided 95% upper bound below 0 (the
    # shorter cooldown learns better, so the longer one costs). FAB_COOLDOWN also spaces growth firings
    # and sets the new_frac budget's window, so this prices the cooldown, not the blackout alone: on CPU
    # k1000_cd100 left k1000 at a growth birth the budget declined, 200-500 windows before the only act.
    # Each arm is read alone -- beside the rule, in no Holm with the cadences, never a ship candidate --
    # and not at all when its cadence never acted.
    CDR = {}
    for arm in CD:
        par_ = arm.split("_cd")[0]
        if par_ not in ACTED:
            CDR[arm] = (par_, None, None)
            continue
        per = [[] for _ in range(rnph)]
        for s in allseeds_:
            ea, ep = endpoint((arm, s)), endpoint((par_, s))
            if ea is None or ep is None:
                continue
            for p in range(rnph):
                if ea[p] is not None and ep[p] is not None:
                    per[p].append(ea[p] - ep[p])
        whole = [wr(arm, s) - wr(par_, s) for s in allseeds_ if wr(arm, s) is not None and wr(par_, s) is not None]
        CDR[arm] = (par_, eps_rule({arm: per}, eps)[arm], better_than({arm: whole})[arm] if whole else None)
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
    print(f"=== THE ε RULE (Proposal 05 O14, O2): ε = {eps:g} bits/byte; incumbent {INC[1:]} (RETOK_INCUMBENT); "
          f"endpoint prequential bits/byte per phase: {ph_head} ===")
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
    for arm, (par_, rc, bc) in sorted(CDR.items()):
        if rc is None:
            line = f"  {arm} - {par_} (C13's cooldown arm, beside the rule): {par_} never acted, so nothing is read"
        else:
            n_arm = max([n for n, _, _, _ in rc["phases"]] or [0])
            body = " ".join(cell(p, row, n_arm) for p, row in enumerate(rc["phases"]))
            line = (f"  {arm} - {par_} (C13's cooldown arm, beside the rule, never a ship candidate) n={n_arm}: {body} "
                    f"-> {rc['verdict']}; whole run " + (
                        "-" if bc is None else
                        f"mean {bc[1]:+.4f}, one-sided 95% upper " + ("- (n < 2)" if bc[2] is None else f"{bc[2]:+.4f}")
                        + (": below 0, significantly better (the longer cooldown costs)" if bc[3] else ": not below 0")))
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
    elif kind == "withdraw":
        # THE SHIPPED CADENCE FAILs IN A FLEET THAT HOLDS NO OTHER (2026-09-28, review of 88d3fae): it stops
        # firing and O14's other cadence and remedy arms run next (note retok fleet (3)); never ESCALATE here.
        decision = f"TOK_RETOK_EVERY {INC[1:]} does not ship (0 is never shipped by the rule): {why}" + tail_
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
                follow = (f"the cooldown arm {' '.join(CD)} is in this fleet: read it against {fastest} beside the "
                          f"rule" if CD else
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
    have_ckpt = os.path.isdir(os.path.join(OUT, "ckpt"))
    kfiles = sorted(glob.glob(os.path.join(kd, "*.kept.txt")))
    rows = []
    for f in kfiles:
        rows += [l for l in rd(f).splitlines() if l.strip()]
    # AN ARCHIVE HOLDS NO CHECKPOINTS, SO KEPT.txt IS ITS ONLY RECORD OF THEM (2026-09-28, review of 88d3fae).
    # --analyze of an unpacked archive found no ckpt/, deleted the KEPT.txt the fleet's own analysis had
    # written, reported "none (KEEP_CKPT off)" beside SUMMARY's "kept checkpoints: ON", and repacked the
    # archive without it. KEPT.txt is rewritten from ckpt/keep, and removed when a ckpt/ here holds no
    # index; with no ckpt/ at all it is kept, and its rows are read as the fleet's record.
    kept_from = ""
    if kfiles:
        with open(os.path.join(OUT, "KEPT.txt"), "w") as fh:
            fh.write("\n".join(rows) + "\n")
    elif os.path.exists(os.path.join(OUT, "KEPT.txt")):
        if have_ckpt:
            os.remove(os.path.join(OUT, "KEPT.txt"))      # never one this ckpt/keep does not hold
        else:
            rows = [l for l in rd(os.path.join(OUT, "KEPT.txt")).splitlines() if l.strip()]
            kept_from = "KEPT.txt"
    # AN INDEX THAT REFUSED says so in its log's "!!" line (keep_index: a keep directory stamped by
    # another launch), and the block carries it: those saves were left unindexed, never dropped.
    refused = [l.strip() for f in sorted(glob.glob(os.path.join(kd, "*.index.log")))
               for l in rd(f).splitlines() if l.startswith("!!")]
    kept_rows, kept_short = [], []
    if not have_ckpt and not kept_from:
        # WHETHER THE FLEET KEPT ANY IS SUMMARY'S TO SAY, not the directory's.
        if KEPT_ON == "ON":
            kept_rows.append("  none here: SUMMARY.txt records kept checkpoints ON, but this directory holds no "
                             "ckpt/ and no KEPT.txt (the fleet's archive packs KEPT.txt, never a checkpoint)")
            kept_short.append("KEPT: none here (SUMMARY: kept checkpoints ON; no ckpt/, no KEPT.txt)")
        elif KEPT_ON == "OFF":
            kept_rows.append("  none: no ckpt/ directory (KEEP_CKPT was off)")
            kept_short.append("KEPT: none (KEEP_CKPT off)")
        else:
            kept_rows.append("  none: no ckpt/ directory, and SUMMARY.txt predates the kept-checkpoint record")
            kept_short.append("KEPT: none (no ckpt/; SUMMARY.txt does not say)")
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
        if kept_from:
            # THE COPIES ARE NOT HERE: no disk to count and no copy to resume from, and the rows say whose.
            kept_rows.append(f"  read from {kept_from}, as the fleet's own analysis wrote it: this directory holds no "
                             f"ckpt/ (an archive packs none), so no disk figure and no resume line")
        else:
            kept_rows.append(f"  disk: {du / 1e9:.2f} GB under {os.path.join(OUT, 'ckpt')} (hard links counted once)")
        kept_rows += [f"  INDEX REFUSED: {l}" for l in refused]
        first = (None if kept_from else
                 next(((s, st) for s in sorted(ks) for st, ok in sorted(ks[s]) if ok), None))
        # THE RESUME LINE CARRIES THE RUN'S OWN SEED, DEVICE AND STREAM (2026-09-27, build 1.5's review):
        # run_job sets RUN_SEED, RUN_DEVICE and DATA_STREAM_BYTES on every run and EXTRA carries none of
        # them, so the line without them was refused -- on CPU at 200 windows the segmentation rebuilt
        # from the checkpoint's log held 635 windows where the parent's epoch held 199.
        # AND THE FLEET'S PINS (2026-09-29, 04-Q5's pin rule), read off SUMMARY.txt's pins line, which
        # records what ran: a kept copy was written under them, mid-epoch, and a continuing resume onto
        # the shipped DATA_SYNTH_HOLDOUT is refused by name. After EXTRA, as run_job sets them.
        # AND THIS CHECKOUT'S, WHERE THE FLEET RECORDED NONE (2026-09-29, the Stage 3 merge): a fleet
        # launched before the flip -- the 2026-09-27 retok fleet -- recorded no pin, because its tree ran
        # each lever's feature off or had none, which is what the pins restore. So every pin whose lever
        # the tree running this analysis declares (TREE_PINS) joins the line, and a row names them.
        dev = cores.group(3) if cores else "cuda"
        pinned = [p[:-len(" pinned")] for p in (sget(r"^=== pins: (.*)$") or "").split(", ")
                  if p.endswith(" pinned")]
        here = [p for p in os.environ.get("GW_TREE_PINS", "").split()
                if p.split("=")[0] not in {q.split("=")[0] for q in pinned}]
        resume = (f"CKPT_RESUME={os.path.join(kd, f'k0.s{first[0]}.w{first[1]}')} CKPT_DIR=<NEW dir> "
                  f"OMP_NUM_THREADS=1 RUN_SEED={first[0]} RUN_DEVICE={dev} DATA_STREAM_BYTES={total or '?'} "
                  f"TOK_RETOK_EVERY=0" + (f" {EXTRA}" if EXTRA.strip() else "")
                  + "".join(f" {p}" for p in pinned + here) + " python3 run.py") if first else None
        if first:
            kept_rows.append(f"  resume one: {resume} -- a NEW CKPT_DIR, never a kept copy")
            if here:
                kept_rows.append(f"  (its {' '.join(here)} are this checkout's pins, which SUMMARY.txt does not "
                                 f"record: the fleet ran before 04-Q5's flip, with those features off, and its copies "
                                 f"continue as they ran only under them)")
        kept_short.append(f"KEPT: {nk} copies of {len(ks)} k0 run(s)"
                          + (", all coherent" if nk and not ninc else f", {ninc} INCOHERENT" if ninc else "")
                          + (", act windows covered " + ", ".join(f"{a} {h}/{n}" for a, (h, n) in cov_tot.items())
                             if cov_tot else "")
                          + (f"; read from {kept_from} (no ckpt/ here)" if kept_from else f"; ckpt/ {du / 1e9:.2f} GB"))
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


# ------------------------------------------------------------------------------------------ heldout
# E2's RETOK PART, READ ON SR0's HELD-OUT PROBE (EXP=heldout; Proposal 05 §8 6.3a, O14, O2; 2026-10-02). The
# endpoint is each area's R reading through the memory-off closure, report half: the LAST row of the run's
# curves/<run>.probe.json whose kind is 'boundary' and closure 'memory-off', its areas[a].report. arm - k0,
# paired by seed, is read by the eps rule with the areas as its cells (Bonferroni over them) and Holm across
# the two act arms, at LOOK_ALPHA a look; choose()'s remedy branch gives the DECISION. A top-up (POOL_WITH,
# recorded in SUMMARY) reads its seeds with its first fleet's only where commit, card, torch and shape match;
# at most CAP_SEEDS seeds are read. Everything after the rule is reported and decides nothing.
HO_AREAS = ("eng", "py", "num", "c")      # the synthetic source's order; any other area follows, sorted
CAP_SEEDS = 11                            # §8 6.3a's cap: 7 seeds, then a top-up of 4
# EACH LOOK AT HALF THE RULE'S 0.05 (2026-10-02, review of 0dfb8e5). The 7 seeds, and the pooled 11 a top-up reads
# where they are UNRESOLVED, are two looks at one question. Read each at 0.05, an arm whose num sits at eps exactly
# PASSed 7.1% of the time over the two; at 0.025 a look, Bonferroni over the two, 3.4% -- PASS's upper bound at
# t(0.975), Holm's FAIL levels from 0.0125 (results/heldout_prereg_2026-10-02/power.out).
LOOK_ALPHA = 0.025
HO_REMEDIES = ("LM_ANCHOR_USES raised, OPT_HORIZON_REVISE=0, and OPT_BORN_CLOCK once §8 4.2 builds it, with k3000 "
               "read for O14's escalation (it needs both cadences and every named remedy to FAIL)")


def ho_runs(out):
    """{(name, seed): run} off one fleet directory: each log, its curve, flush bytes and probe series."""
    runs = {}
    for log in sorted(glob.glob(os.path.join(out, "logs", "*.log"))):
        tag = os.path.basename(log)[:-4]
        name, _, seed = tag.rpartition(".s")
        if not name or not seed.isdigit():
            continue
        t = rd(log)
        r = rep(t)

        def js(sfx):
            try:
                with open(os.path.join(out, "curves", tag + sfx)) as fh:
                    return json.load(fh)
            except (OSError, ValueError):
                return None
        series = js(".probe.json")
        bnd = {}
        for row in series if isinstance(series, list) else []:
            if isinstance(row, dict) and row.get("kind") == "boundary":
                bnd[row.get("closure")] = row               # the LAST boundary row of each closure
        w = re.search(r"=== (\d+) windows[^\n]*? in ([\d.]+)s", t)
        fl = re.search(r"^=== \d+ windows, (\d+) flushes", t, re.M)
        prog = re.findall(r"^\[(\d+) windows\][^\n]*? n_live=(\d+)", t, re.M)
        pe = re.search(r"^\s+gate:data\.phase_entered\s[^\n]*?'(\d+) vs (\d+)'", t, re.M)
        nl = fnum(r.get("fab.n_live"))
        runs[(name, int(seed))] = dict(
            tag=tag, curve=js(".json"), fbytes=js(".bytes.json"), series=series, bnd=bnd, r=r,
            win=int(w.group(1)) if w else None, secs=float(w.group(2)) if w else None,
            flushes=int(fl.group(1)) if fl else None, acts=fnum(r.get("loop.acts")),
            stopped="stopped at max_windows" in t,
            nlive=nl if nl is not None else (float(prog[-1][1]) if prog else None),
            nph=int(pe.group(2)) if pe else None)
    return runs


def ho_end(v, closure="memory-off"):
    """{area: report} of the run's last boundary reading through `closure`; {} where it has none."""
    row = v.get("bnd", {}).get(closure) or {}
    return {a: float(x["report"]) for a, x in (row.get("areas") or {}).items()
            if isinstance(x, dict) and fnum(x.get("report")) is not None}


def ho_facts(s):
    """What a pooled reading must share, off a SUMMARY.txt: the commit with its dirty flag and the code copy's
    sha256, the card, torch, and the shape (windows, stream, EXTRA, arms, LM_CTX, pins)."""
    first = s.splitlines()[0] if s else ""
    m = re.match(r"=== gpu_world\.sh\s+\S+\s+commit\s*(\S*)(.*)$", first)
    code = re.search(r"^=== code: .*?sha256 (\S+)\)", s, re.M)
    sz = re.search(r"^=== (\d+) windows per run, DATA_STREAM_BYTES=(\d+), seeds: .*?, EXTRA='(.*)'$", s, re.M)
    plan = re.search(r"^=== plan: EXP=(\w+); arms (.*?), plus .*?LM_CTX (\d+)", s, re.M)
    pins = re.search(r"^=== pins: (.*)$", s, re.M)
    return {"commit": (m.group(1) + (" (dirty)" if "(dirty)" in m.group(2) else "")) if m else None,
            "code": code.group(1) if code else None,
            "card": ", ".join(sorted({f"{n.strip()} {mib} MiB" for n, mib in
                                      re.findall(r"^\s+\d+, ([^,\n]+), (\d+) MiB, \d+ MiB\s*$", s, re.M)})) or "no GPU",
            "torch": (re.search(r"^=== (torch \S+, CUDA \S+)", s, re.M) or [None, None])[1],
            "shape": (sz.groups() if sz else None, plan.groups() if plan else None, pins.group(1) if pins else None)}


def heldout(ctx_arg, archive, eps, pool_arg, home):
    ctx = int(sget(r"^=== plan: .*?LM_CTX (\d+)") or ctx_arg)
    total = int(sget(r"DATA_STREAM_BYTES=(\d+)") or 0)
    done = done_book()
    here = ho_runs(OUT)
    runs = {k: v for k, v in here.items() if k[0] != "k0_rerun"}
    reruns = [("this fleet's", here.get(("k0_rerun", 0)), here.get(("k0", 0)))]
    mine = {s for (n, s) in runs}

    # ---------------------------------------------------------------- a top-up's first fleet
    pool = (pool_arg or sget(r"^=== pool: with (\S+)") or "").strip()
    pooled, refused, pool_lines = None, None, []
    if pool:
        P = rd(os.path.join(pool, "SUMMARY.txt"))
        if not P:
            refused = f"{pool} holds no SUMMARY.txt"
        else:
            a_, b_ = ho_facts(S), ho_facts(P)
            diff = [k for k in ("commit", "code", "card", "torch", "shape") if a_[k] != b_[k]]
            there = ho_runs(pool)
            both = sorted(mine & {s for (n, s) in there if n != "k0_rerun"})
            # THE TOP-UP'S RERUN IS THE FIRST FLEET'S k0.s0 AGAIN, ON THIS FLEET'S CARD AND TORCH: pooled or not,
            # the pair says whether the two fleets compute alike.
            reruns = [("this top-up's, against the first fleet's k0.s0", here.get(("k0_rerun", 0)),
                       there.get(("k0", 0)))]
            if diff:
                refused = "they differ in " + "; ".join(f"{k} ({a_[k]} here, {b_[k]} there)" for k in diff)
            elif both:
                refused = f"seed(s) {' '.join(map(str, both))} are in both"
            else:
                pooled = pool
                runs.update({k: v for k, v in there.items() if k[0] != "k0_rerun"})
                reruns = [("the first fleet's", there.get(("k0_rerun", 0)), there.get(("k0", 0)))] + reruns
        pool_lines = ([f"POOLED with the first fleet {pooled}: its seeds and this top-up's (marked *) are read "
                       f"together; commit, card, torch and shape match"] if pooled else
                      [f"POOLING REFUSED with {pool}: {refused}; nothing is decided here"])

    # ---------------------------------------------------------------- the endpoint and the rule
    end = {k: ho_end(v) for k, v in runs.items()}
    names = {n for (n, s) in runs}
    incs = sorted((n for n in names if re.fullmatch(r"k[1-9]\d*", n)), key=lambda a: int(a[1:]))
    inc = incs[0] if incs else None
    mn = f"{inc}_mn" if inc and f"{inc}_mn" in names else None
    arms = [a for a in (inc, mn) if a]
    k0s = sorted(s for (n, s) in runs if n == "k0" and end[(n, s)])
    seeds, past = k0s[:CAP_SEEDS], k0s[CAP_SEEDS:]
    seen = [a for e in end.values() for a in e]
    areas = [a for a in HO_AREAS if a in seen] + sorted(set(seen) - set(HO_AREAS))
    acted = [a for a in arms if any((runs.get((a, s)) or {}).get("acts") for s in seeds)]
    diffs = {}
    for a in acted:
        per = [[] for _ in areas]
        for s in seeds:
            ea, e0 = end.get((a, s)), end.get(("k0", s))
            if ea and e0:
                for i, ar in enumerate(areas):
                    if ar in ea and ar in e0:
                        per[i].append(ea[ar] - e0[ar])
        diffs[a] = per
    R = eps_rule(diffs, eps, LOOK_ALPHA) if diffs else {}
    n_read = max([len(xs) for per in diffs.values() for xs in per] or [0])
    room = n_read < CAP_SEEDS and not pool
    kind, pick, why = choose([inc] if inc else [], R, {}, inc, remedy=mn, room=room)
    if refused:
        kind = "refused"
    c = inc[1:] if inc else "?"
    nxt = 1 + max([s for (n, s) in runs] + [int(t.rpartition(".s")[2]) for t in done if t.rpartition(".s")[2].isdigit()]
                  or [-1])
    cmd = None
    if kind == "topup":
        sz = re.search(r"^=== (\d+) windows per run, DATA_STREAM_BYTES=(\d+), seeds: .*?, EXTRA='(.*)'$", S, re.M)
        pe = re.search(r"EVAL_RETENTION_EVERY=(\d+) pinned", S)
        dv = re.search(r"^=== \d+ CPU core\(s\), \d+ GPU\(s\), device=(\w+)", S, re.M)
        pr = (re.findall(r"^=== \d+ run\(s\), (\d+) at a time", S, re.M) or [None])[-1]
        oa = os.path.realpath(OUT)
        kv = [("EXP", "heldout"), ("SEEDS", " ".join(str(s) for s in range(nxt, nxt + CAP_SEEDS - n_read))),
              ("FILL", "0")]
        if sz and sz.group(1) != "20000":
            kv.append(("WINDOWS", sz.group(1)))
        if sz and int(sz.group(2)) != int(sz.group(1)) * 189:
            kv.append(("EPOCH_BYTES", sz.group(2)))
        if sz and sz.group(3):
            kv.append(("EXTRA", sz.group(3)))
        if c != "1000":
            kv.append(("PIN_RETOK", c))
        if pe and pe.group(1) != "700":
            kv.append(("PROBE_EVERY", pe.group(1)))
        if dv and dv.group(1) != "cuda":
            kv.append(("DEVICE", dv.group(1)))
        if pr:
            kv.append(("PAR", pr))
        kv += [("OUT", (oa[:-4] if oa.endswith("_out") else oa) + "_topup_out"), ("POOL_WITH", oa)]
        cmd = " ".join(f"{k}={shlex.quote(v)}" for k, v in kv) + f" bash {shlex.quote(os.path.join(home, 'tools', 'gpu_launch.sh'))} --go"
    tail_ = f" (ε {eps:g} bits/byte, {n_read} seed(s))"
    if kind == "pass":
        decision = (f"TOK_RETOK_EVERY {c} PASSes against k0 on every area's held-out reading: its B-provisional label "
                    f"ends on this synthetic source (real text, E2's shape (b), is §8 6.3's)" + tail_)
    elif kind == "remedy":
        decision = (f"TOK_MINT_NOVEL 1.0 ships at TOK_RETOK_EVERY {c}, in its own default-change commit: {why}" + tail_)
    elif kind == "withdraw":
        decision = (f"neither ships: {why}; {c} stays on meanwhile (0 is never shipped by the rule) and the next "
                    f"remedy arms run: {HO_REMEDIES}" + tail_)
    elif kind == "topup":
        decision = (f"UNRESOLVED at {n_read} seed(s): {why}; top up to the cap of {CAP_SEEDS} on this card and torch "
                    f"with the command below, then paste back the top-up's block, which reads both fleets" + tail_)
    elif kind == "unresolved":
        decision = (f"UNRESOLVED at the cap: {why}; reported so, never escalated, and TOK_RETOK_EVERY {c} stays, "
                    f"B-provisional" + tail_)
    elif kind == "refused":
        decision = (f"NOTHING IS DECIDED: this top-up's seeds pool with its first fleet's only where commit, card, torch "
                    f"and shape match, and {refused}; the first fleet's reading stands, and the top-up runs again on "
                    f"its card and torch, at its commit")
    else:
        decision = f"UNDECIDED: {why}" + ("" if acted else "; no act arm acted in these runs (raise WINDOWS)")

    # ---------------------------------------------------------------- the runs, as read
    print()
    print("=== RUNS (held-out bits/byte at R: the last 'boundary' row, closure memory-off, report half) ===")
    missing = []
    for (n, s), v in sorted(runs.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        e = end[(n, s)]
        why_ = ("NO PROBE SERIES" if v["series"] is None else "NO BOUNDARY ROW (memory-off)" if not e else "")
        if why_:
            missing.append(f"{v['tag']}{'*' if pooled and (n, s) in here else ''}")
        print(f"  {n:<10} s{s:<3} {v['win'] or '?':>6} win  acts {fmt(v['acts'], 'n'):>4}  "
              + ("  ".join(f"{a} {e[a]:.5f}" for a in areas if a in e) or why_)
              + ("  STOPPED AT THE WINDOW CAP" if v["stopped"] else ""))
    rr_lines = []
    for who, a_, b_ in reruns:
        if a_ is None:
            continue
        ea, eb = ho_end(a_), ho_end(b_ or {})
        d_ = [abs(ea[x] - eb[x]) for x in ea if x in eb]
        pq = (abs(sum(a_["curve"]) - sum(b_["curve"])) if a_.get("curve") and b_ and b_.get("curve") else None)
        rr_lines.append(f"k0_rerun ({who}): " + ("no k0.s0 reading to pair it with" if not d_ else
                        f"k0 seed 0 twice, R per area max |diff| {max(d_):.3g}"
                        + (f", summed loss |diff| {pq:.3g}" if pq is not None else "")
                        + (" (BIT-EXACT)" if max(d_) == 0 and pq == 0 else "")))
    print()
    for l in rr_lines:
        print(f"=== RUN-TO-RUN: {l} ===")

    def cell(i, row, n_arm):
        n, m, lo, up = row
        if m is None:
            return f"{areas[i]} -"
        return (f"{areas[i]} {m:+.4f} " + (f"[{lo:+.4f},{up:+.4f}]" if lo is not None else "[-]")
                + (f" (n={n})" if n != n_arm else ""))

    rule_rows = []
    for a in arms:
        if a not in R:
            rule_rows.append(f"  {a}: NO ACT FIRED at any seed -- no evidence either way, not a pass")
            continue
        r_ = R[a]
        n_arm = max([n for n, _, _, _ in r_["phases"]] or [0])
        rule_rows.append(f"  {a} n={n_arm} a={r_['level']:.3g}: "
                         + " ".join(cell(i, row, n_arm) for i, row in enumerate(r_["phases"]))
                         + f" -> {r_['verdict']}"
                         + (f" ({r_['note'].replace('some phase', 'some area')})" if r_["note"] else ""))
    rule_head = (f"RULE (§8 6.3a; O2, O14): ε {eps:g} bits/byte; per area ({len(areas)}), arm - k0 paired over seeds, "
                 f"each look (7 seeds; a top-up's pooled 11) at {LOOK_ALPHA:g}: mean [lower at t(1 - a/{len(areas)}), "
                 f"Holm's a across the act arms; one-sided upper at t({1 - LOOK_ALPHA:g})]"
                 + (" -- this fleet alone, deciding nothing" if refused else ""))
    print()
    print("=== " + rule_head + " ===")
    for l in rule_rows:
        print(l)
    print()
    print(f"=== DECISION: {decision} ===")
    if cmd:
        print(f"    top-up: {cmd}")
    extra_rows = []
    if missing:
        extra_rows.append(f"  left out of the pairs (no endpoint): {' '.join(missing)}")
    if past:
        extra_rows.append(f"  seeds past the cap of {CAP_SEEDS}, not read: {' '.join(map(str, past))}")
    for l in extra_rows:
        print(l)

    # ---------------------------------------------------------------- reported, deciding nothing
    def per_arm(a):
        return [(s, runs[(a, s)]) for s in seeds if (a, s) in runs]

    def sd(xs):
        n_, m_, se_ = mean_se(xs)
        return None if se_ is None else se_ * math.sqrt(n_)

    rep_lines = []
    # (1) O14's per-phase prequential reading (§8 2.1's endpoint), each act arm against k0.
    gate_n = [v["nph"] for v in runs.values() if v["nph"]]
    nph = max(sorted(set(gate_n)), key=gate_n.count) if gate_n else 4

    def phases(v):
        cu, fb = v["curve"], v["fbytes"]
        if not (cu and fb and len(cu) == len(fb) and total):
            return None
        lo_n, lo_b, off = [0.0] * nph, [0] * nph, 0
        for x, nb in zip(cu, fb):
            k = min(nph - 1, next((j for j in range(nph) if off < round((j + 1) * total / nph)), nph - 1))
            lo_n[k] += x
            lo_b[k] += nb
            off += nb
        return [lo_n[k] * ctx / L2 / lo_b[k] if lo_b[k] else None for k in range(nph)]
    ph = {k: phases(v) for k, v in runs.items()}
    pin = {}
    for a in acted:
        per = [[] for _ in range(nph)]
        for s in seeds:
            pa, p0 = ph.get((a, s)), ph.get(("k0", s))
            if pa and p0:
                for k in range(nph):
                    if pa[k] is not None and p0[k] is not None:
                        per[k].append(pa[k] - p0[k])
        pin[a] = per
    PR = eps_rule(pin, eps) if pin else {}
    for a in acted:
        n_arm = max([len(xs) for xs in pin[a]] or [0])
        body = " ".join(f"p{k + 1} " + ("-" if m is None else f"{m:+.4f}" + (f" [{lo:+.4f},{up:+.4f}]" if lo is not None else ""))
                        for k, (n, m, lo, up) in enumerate(PR[a]["phases"]))
        rep_lines.append(f"  prequential per phase (O14's 2.1 endpoint), {a} - k0 n={n_arm}: {body} -> {PR[a]['verdict']}")
    # (2) memory-on minus memory-off per area at R (NEW-03).
    mem = []
    for a in ["k0"] + arms:
        pairs = [(ho_end(v, "memory-on"), ho_end(v)) for _, v in per_arm(a)]
        dd = {ar: mean([on[ar] - off[ar] for on, off in pairs if ar in on and ar in off]) for ar in areas}
        if any(x is not None for x in dd.values()):
            mem.append(f"{a} " + " ".join(f"{ar} {fmt(x, '+.4f')}" for ar, x in dd.items()))
    if mem:
        rep_lines.append("  memory-on - memory-off at R, mean over seeds (NEW-03): " + " | ".join(mem))

    # (3) the time-integrated report gap from 20% of the stream: each run's all-area report mean over its in-run
    # readings (memory-off), a step function of its stream position, integrated over the bytes from 20% of its
    # stream to the end; arm - k0 paired by seed.
    def integ(v):
        ser, fb = v["series"], v["fbytes"]
        if not ser or not fb or not v["win"] or not v["flushes"]:
            return None
        wpf = max(1, round(v["win"] / v["flushes"]))
        cum = [0]
        for b in fb:
            cum.append(cum[-1] + b)
        T = cum[-1]
        pts = sorted((cum[min(len(fb), int(r_["step"]) // wpf)], float(r_["report"])) for r_ in ser
                     if isinstance(r_, dict) and r_.get("kind") in ("phase", "cadence")
                     and r_.get("closure") == "memory-off" and fnum(r_.get("report")) is not None)
        if not pts or T <= 0:
            return None
        lo, acc = 0.2 * T, 0.0
        for i, (x, val) in enumerate(pts):
            a_ = lo if i == 0 else max(x, lo)
            b_ = pts[i + 1][0] if i + 1 < len(pts) else T
            acc += val * max(0.0, min(b_, T) - a_)
        return acc / (T - lo)
    ti = {k: integ(v) for k, v in runs.items()}
    tl = []
    for a in acted:
        xs = [ti[(a, s)] - ti[("k0", s)] for s in seeds
              if ti.get((a, s)) is not None and ti.get(("k0", s)) is not None]
        if xs:
            tl.append(f"{a} - k0 mean {sum(xs) / len(xs):+.4f} sd {fmt(sd(xs), '.4f')} n={len(xs)}")
    if tl:
        rep_lines.append("  time-integrated report gap from 20% of the stream (all areas, in-run readings): "
                         + " | ".join(tl))
    # (4) the end-state SD per area of arm - k0, which sizes the next tests.
    sdl = [f"{a} " + " ".join(f"{ar} {fmt(sd(xs), '.4f')}" for ar, xs in zip(areas, diffs[a])) for a in acted]
    if sdl:
        rep_lines.append("  end-state SD per area of arm - k0: " + " | ".join(sdl))
    # (5) n_live at the end (NEW-20); (6) the probe's seconds, R's share split out by windows (E6's cost);
    # (7) data.trust.wall_s; each per arm, mean [min-max] over the seeds read.
    def mm(xs, spec):
        xs = [x for x in xs if x is not None]
        return (f"{fmt(mean(xs), spec)} [{fmt(min(xs), spec)}-{fmt(max(xs), spec)}]" if xs else "-")
    rep_lines.append("  n_live at the end (NEW-20): " + " | ".join(
        f"{a} {mm([v['nlive'] for _, v in per_arm(a)], '.0f')}" for a in ["k0"] + arms))
    pr_ = []
    for a in ["k0"] + arms:
        tot, inrun, rsh = [], [], []
        for _, v in per_arm(a):
            sec_, win_ = fnum(v["r"].get("eval.holdout.seconds")), fnum(v["r"].get("eval.holdout.windows"))
            rw = sum(int(x.get("windows") or 0) for x in (v["series"] or []) if isinstance(x, dict)
                     and x.get("kind") == "boundary")
            if sec_ is None or not win_:
                continue
            r_s = sec_ * rw / win_
            tot.append(sec_)
            rsh.append(r_s)
            if v["secs"]:
                inrun.append(100 * (sec_ - r_s) / v["secs"])
        if tot:
            pr_.append(f"{a} {mean(tot):.1f} s, R {mean(rsh):.1f} s, in-run {fmt(mean(inrun), '.2f')}% of loop time")
    if pr_:
        rep_lines.append("  the probe's seconds (eval.holdout.seconds; R's share by its windows; E6's cost at the "
                         "pinned cadence): " + " | ".join(pr_))
    tw_ = [f"{a} {mm([fnum(v['r'].get('data.trust.wall_s')) for _, v in per_arm(a)], '.2f')} s" for a in ["k0"] + arms]
    rep_lines.append("  data.trust.wall_s (the book's seconds; no claim fires on synthetic text): " + " | ".join(tw_))
    # (8) in-run readings per phase, and §8 0.4's check on the pinned cadence.
    cnt, short = [], []
    for k, v in runs.items():
        steps, cs = [], []
        for r_ in v["series"] or []:
            if not isinstance(r_, dict) or r_.get("closure") != "memory-off":
                continue
            if r_.get("kind") == "phase":
                steps.append(int(r_["step"]))
                cs.append(1)
            elif r_.get("kind") == "cadence" and cs:
                cs[-1] += 1
        cnt += [(x, v["tag"], i + 1) for i, x in enumerate(cs)]
        if steps and v["win"]:
            ln_ = [b - a for a, b in zip(steps, steps[1:])] + [v["win"] - steps[-1] + 1]
            short.append((min(ln_), v["tag"]))
    every = sget(r"EVAL_RETENTION_EVERY=(\d+) pinned")
    if cnt:
        lo_ = min(cnt)
        sh = min(short) if short else None
        rep_lines.append(f"  in-run readings per phase: fewest {lo_[0]} ({lo_[1]}, phase {lo_[2]}), most {max(cnt)[0]}"
                         + (f"; shortest phase {sh[0]:,} windows ({sh[1]}), / 5 = {sh[0] / 5:.0f} against "
                            f"EVAL_RETENTION_EVERY {every or '?'} (§8 0.4)" if sh else ""))

    # ---------------------------------------------------------------- rates
    rate_rows = []
    for a in ["k0"] + arms:
        wps = [v["win"] / v["secs"] for _, v in per_arm(a) if v["win"] and v["secs"]]
        if wps:
            rate_rows.append(f"{a} {mean(wps):.2f} [{min(wps):.2f}-{max(wps):.2f}]")
    agg = []
    fin = re.search(r"^---- fleet finished in \d+ min \((\d+) s\)", S, re.M)
    eta = re.search(r"^=== ETA by waves: about \d+ min \((\d+) s\)", S, re.M)
    if fin and int(fin.group(1)) > 0:
        wall = int(fin.group(1))
        tw = sum(v["win"] for k, v in here.items() if v["win"])
        agg.append(f"  this fleet: {tw:,} windows in {wall} s of fleet wall = {tw / wall:.2f} windows/s aggregate"
                   + (f"; ETA by waves {eta.group(1)} s, took {wall} s: {wall / max(1, int(eta.group(1))):.2f}x"
                      if eta else ""))

    # ---------------------------------------------------------------- the finals: test 2's parents
    # THIS FLEET'S act arms' final checkpoints and their vocabularies, sha256 in FINALS.sha256 (sha256sum's
    # format, paths relative to OUT), so the next test can check a copy. An archive holds no checkpoint, so with
    # no ckpt/ here the FINALS.sha256 the fleet's own analysis wrote is kept and read.
    fin_lines = []
    ck = os.path.join(OUT, "ckpt")
    man = os.path.join(OUT, "FINALS.sha256")
    if os.path.isdir(ck):
        rows, nb = [], 0
        for (n, s), v in sorted(here.items()):
            if n not in arms:
                continue
            for rel in (f"ckpt/{v['tag']}/ckpt.pt", f"ckpt/{v['tag']}.dyntok.json"):
                p_ = os.path.join(OUT, rel)
                if os.path.isfile(p_):
                    h = hashlib.sha256()
                    with open(p_, "rb") as fh:
                        for blk in iter(lambda: fh.read(1 << 20), b""):
                            h.update(blk)
                    rows.append(f"{h.hexdigest()}  {rel}")
                    nb += os.path.getsize(p_)
        with open(man, "w") as fh:
            fh.write("".join(r_ + "\n" for r_ in rows))
        # THE PACK COMMAND ON A LINE OF ITS OWN, as the top-up's is (2026-10-02, review of 0dfb8e5): it was the FINALS
        # line's tail, and that line run as printed is a syntax error. A top-up's finals are not the next test's
        # parents, so its block packs none.
        oa, tar_ = os.path.realpath(OUT), re.sub(r"\.tgz$", "", os.path.realpath(archive)) + "_finals.tar"
        fin_lines.append(f"FINALS: {len(rows)} file(s), the {' and '.join(arms)} runs' final checkpoints and "
                         f"vocabularies, {nb / 1e9:.2f} GB, sha256 in FINALS.sha256; "
                         + ("a top-up's: the next test starts from the first fleet's, which its block's pack: line packs"
                            if pool else "the next test's parents, which the pack: line below packs to upload"))
        if not pool:
            fin_lines.append(f"  pack: tar -cf {tar_} -C {oa} FINALS.sha256 $(cut -c67- {oa}/FINALS.sha256)")
    elif os.path.exists(man):
        n_ = sum(1 for l in rd(man).splitlines() if l.strip())
        fin_lines.append(f"FINALS: {n_} file(s) in FINALS.sha256, as the fleet's own analysis wrote it (no ckpt/ here: "
                         f"an archive packs none)")
    else:
        fin_lines.append("FINALS: none" + (" (KEEP_CKPT was off)" if KEPT_ON == "OFF" else
                                           ": this directory holds no ckpt/ and no FINALS.sha256"))

    print()
    print("=== REPORTED, DECIDES NOTHING (§8 6.3a) ===")
    for l in rep_lines + ["  windows/s per run (mean [min-max] over the seeds read): " + " | ".join(rate_rows)] + agg:
        print(l)
    print()
    for l in fin_lines:
        print(l if l.startswith("  ") else "=== " + l)

    # ---------------------------------------------------------------- the block
    hd = [f"held-out bits/byte at R (memory-off, report half), per seed: k0, then " + ", then ".join(f"{a} - k0" for a in arms),
          "  seed  " + " ".join(f"{a:>7}" for a in areas) + "".join(" | " + " ".join(f"{a:>8}" for a in areas) for _ in arms)]
    t_rows = []
    for s in seeds:
        e0 = end.get(("k0", s)) or {}
        cells = " ".join(f"{fmt(e0.get(a), '.4f'):>7}" for a in areas)
        for a in arms:
            ea = end.get((a, s)) or {}
            cells += " | " + " ".join(f"{fmt(ea[x] - e0[x] if x in ea and x in e0 else None, '+.4f'):>8}"
                                      for x in areas)
        t_rows.append(f"  {'s' + str(s) + ('*' if pooled and ('k0', s) in here else ''):<6}{cells}")

    def table(n=None):
        if n is None or len(t_rows) + 2 <= n:
            return hd + t_rows
        keep = max(0, n - 3)
        return hd + t_rows[:keep] + [f"  ... {len(t_rows) - keep} more seed row(s): in ANALYSIS.txt's RUNS"]
    labels = ["synthetic source"] + (["pooled"] if pooled else [])
    emit([
        ("head", head("heldout", labels) + failures(here, done), 0),
        ("pool", pool_lines, 0),
        ("per-seed rows", table, 0),
        ("verdict", rr_lines + [rule_head] + rule_rows + [f"DECISION: {decision}"]
         + ([f"  top-up: {cmd}"] if cmd else []) + extra_rows, 0),
        ("reported", ["REPORTED, DECIDES NOTHING:"], 0),
        ("time-integrated and SD", [l for l in rep_lines if "time-integrated" in l or "end-state SD" in l], 1),
        ("prequential", [l for l in rep_lines if "prequential" in l], 2),
        ("memory", [l for l in rep_lines if "memory-on" in l], 2),
        ("readings", [l for l in rep_lines if "readings per phase" in l], 2),
        ("pool and probe costs", [l for l in rep_lines if "n_live" in l or "probe's seconds" in l
                                  or "data.trust" in l], 3),
        ("rates", ["  windows/s per run: " + " | ".join(rate_rows)], 4),
        ("aggregate", agg, 1),
        ("finals", fin_lines, 0),
        ("archive", [archive_line(archive)], 0),
    ])


# ------------------------------------------------------------------------------------------ session
# THE FIRST POST-TRAINING SESSIONS (EXP=session; Proposal 05 §8 5.3a, O2, O9; 2026-10-02). A session's endpoint per
# old area is F = its R reading - its resume-start reading, both through the memory-off closure, report half: the
# last 'boundary' row of curves/<run>.probe.json against its 'resume' row, which reads the parent's final weights on
# the same pinned items (O2's anchor). Over the parents each candidate, P and P_parent, is read by the eps rule with
# the old areas as its cells and Holm across the two, at LOOK_ALPHA a look (7 parents; a top-up's pooled 11). Among
# the admitted, O9 takes the larger new-area gain: d = x5's R reading on P_parent - on P, paired by parent, read by
# its one-sided bounds at t(1 - LOOK_ALPHA); a tie goes to the smaller worst-area mean F (C25). A top-up reads its
# parents with its first fleet's only where commit, card, torch and shape match. Everything after the rule is
# reported and decides nothing: the anchor, x5's learning, 5.1's SDs with the gate's arithmetic, W against P, the
# pricing and the rehearsal, rates.
SE_CANDS = ("P", "P_parent")              # the rule's candidates; P_twin and W are read beside them
SE_NEW = "x5"                             # the session's new area
SE_NEXT = "P+parent at 'replay' 0.40; P+parent with W's headroom; 5.2's continuation rates"


def se_runs(out):
    """{(arm, seed): session} off one EXP=session fleet: each session's resume-start and R rows, its first in-run
    reading holding x5, its windows and seconds in this process, and the lines the reader reports."""
    runs = {}
    for log in sorted(glob.glob(os.path.join(out, "logs", "*.log"))):
        tag = os.path.basename(log)[:-4]
        name, _, seed = tag.rpartition(".s")
        if name not in SE_CANDS + ("P_twin", "W") or not seed.isdigit():
            continue
        t = rd(log)
        r = rep(t)

        def js(sfx):
            try:
                with open(os.path.join(out, "curves", tag + sfx)) as fh:
                    return json.load(fh)
            except (OSError, ValueError):
                return None
        series = js(".probe.json")
        rows = [x for x in series if isinstance(x, dict)] if isinstance(series, list) else []

        def last(kind, closure="memory-off"):
            m_ = [x for x in rows if x.get("kind") == kind and x.get("closure") == closure]
            return m_[-1] if m_ else None
        w = re.search(r"^=== \d+ windows run total \((\d+) trained by this process, resumed at (\d+)\)[^\n]*? in "
                      r"([\d.]+)s", t, re.M)
        pr = re.search(r"^\s+opt\.continue\.pricing\s+(\S.*?)\s*$", t, re.M)
        rh = re.search(r"^\s+gate:data\.rehearse_parent\s+\('([\w-]+)'", t, re.M)
        runs[(name, int(seed))] = dict(
            tag=tag, curve=js(".json"), series=series, r=r, res=last("resume"), R=last("boundary"),
            first5=next((x for x in rows if x.get("closure") == "memory-off" and x.get("kind") in ("phase", "cadence")
                         and SE_NEW in (x.get("areas") or {})), None),
            win=int(w.group(1)) if w else None, base=int(w.group(2)) if w else None,
            secs=float(w.group(3)) if w else None, capped="stopped at max_windows" in t,
            pricing=pr.group(1) if pr else None, rehearse=rh.group(1) if rh else None,
            nlive=fnum(r.get("fab.n_live")), births=fnum(r.get("fab.births")),
            widened=fnum(r.get("fab.resume_widened")))
    return runs


def se_val(row, area, half="report"):
    """One area's mean in one series row, or None."""
    return fnum((((row or {}).get("areas") or {}).get(area) or {}).get(half))


def se_F(v, areas):
    """{area: F}: the session's R reading - its resume-start reading, per old area (memory-off, report half)."""
    out_ = {}
    for a in areas:
        x, y = se_val(v.get("R"), a), se_val(v.get("res"), a)
        if x is not None and y is not None:
            out_[a] = x - y
    return out_


def se_facts(s):
    """ho_facts, and the session's own shape: the session line (its windows, levers, the twin's rate and W's
    headroom) and the parents' arm. Where the parents came from may differ: a top-up's parents stage trains its own."""
    f = ho_facts(s)
    ses = re.search(r"^=== session: (.*)$", s, re.M)
    arm = re.search(r"^=== parents: (\S+) at seeds", s, re.M)
    f["shape"] = f["shape"] + (ses.group(1) if ses else None, arm.group(1) if arm else None)
    return f


def se_choose(V, d, worst, room):
    """O9's choice between the candidates (§8 5.3a). V: eps_rule's reading of P and P_parent; d: (n, mean, lower,
    upper) of x5's R reading on P_parent - on P, paired by parent, each bound one-sided at t(1 - LOOK_ALPHA); worst:
    {candidate: its worst old area's mean F}; room: parents remain under the cap. Returns (kind, arm, why), kind one
    of 'undecided' (a candidate has no reading at all: nothing is decided on the other alone), 'topup' (a candidate
    UNRESOLVED with room -- beside an admitted one too, since it may yet be admitted), 'take' (arm is O9's choice: the
    only one admitted, or of two the larger new-area gain, a tie going to the smaller worst-area mean F), 'unresolved'
    (none admitted and one UNRESOLVED at the cap) or 'none' (both FAIL)."""
    vs = {a: V.get(a, {}).get("verdict") for a in SE_CANDS}
    if any(v is None for v in vs.values()):
        return "undecided", None, ("no session was read" if all(v is None for v in vs.values()) else
                                   " and ".join(a for a in SE_CANDS if vs[a] is None) + " has no reading")
    adm = [a for a in SE_CANDS if vs[a] == "PASS"]
    unr = [a for a in SE_CANDS if vs[a] == "UNRESOLVED"]
    if unr and room:
        return "topup", None, (" and ".join(unr) + (" is" if len(unr) == 1 else " are") + " UNRESOLVED"
                               + "".join(f", {a} FAILs" for a in SE_CANDS if vs[a] == "FAIL")
                               + "".join(f", {a} is admitted" for a in adm))
    if len(adm) == 2:
        n, m, lo, up = d
        if up is not None and up < 0:
            return "take", "P_parent", (f"both are admitted, and x5's R reading on P_parent - on P has its one-sided "
                                        f"upper bound {up:+.4f} below 0: P_parent learns the new area better")
        if lo is not None and lo > 0:
            return "take", "P", (f"both are admitted, and x5's R reading on P_parent - on P has its one-sided lower "
                                 f"bound {lo:+.4f} above 0: P learns the new area better")
        pick = min(SE_CANDS, key=lambda c: (math.inf if worst.get(c) is None else worst[c], SE_CANDS.index(c)))
        return "take", pick, ("both are admitted and the new area ties (x5 P_parent - P "
                              + (f"[{lo:+.4f},{up:+.4f}]" if lo is not None else "unbounded at n < 2")
                              + "), so the smaller worst-area mean F takes it (C25): "
                              + ", ".join(f"{c} {fmt(worst.get(c), '+.4f')}" for c in SE_CANDS))
    if adm:
        o = [c for c in SE_CANDS if c != adm[0]][0]
        return "take", adm[0], (f"{adm[0]} is the one admitted; {o} "
                                + ("FAILs" if vs[o] == "FAIL" else "is UNRESOLVED at the parent cap"))
    if unr:
        return "unresolved", None, (" and ".join(f"{c} " + ("FAILs" if vs[c] == "FAIL" else "is UNRESOLVED")
                                                 for c in SE_CANDS) + " at the parent cap")
    return "none", None, "P and P_parent both FAIL"


def session(ctx_arg, archive, eps, pool_arg, home):
    done = done_book()
    here = se_runs(OUT)
    runs = dict(here)
    mine = {s for (n, s) in runs}

    # ---------------------------------------------------------------- a top-up's first fleet
    pool = (pool_arg or sget(r"^=== pool: with (\S+)") or "").strip()
    pooled, refused, pool_lines = None, None, []
    if pool:
        Pq = rd(os.path.join(pool, "SUMMARY.txt"))
        if not Pq:
            refused = f"{pool} holds no SUMMARY.txt"
        else:
            a_, b_ = se_facts(S), se_facts(Pq)
            diff = [k for k in ("commit", "code", "card", "torch", "shape") if a_[k] != b_[k]]
            there = se_runs(pool)
            both = sorted(mine & {s for (n, s) in there})
            if diff:
                refused = "they differ in " + "; ".join(f"{k} ({a_[k]} here, {b_[k]} there)" for k in diff)
            elif both:
                refused = f"parent seed(s) {' '.join(map(str, both))} are in both"
            else:
                pooled = pool
                runs.update(there)
        pool_lines = ([f"POOLED with the first fleet {pooled}: its parents and this top-up's (marked *) are read "
                       f"together; commit, card, torch and shape match"] if pooled else
                      [f"POOLING REFUSED with {pool}: {refused}; nothing is decided here"])

    # ---------------------------------------------------------------- the endpoint and the rule
    seen = [a for v in runs.values() for a in ((v.get("res") or {}).get("areas") or {})]
    areas = [a for a in HO_AREAS if a in seen] + sorted(set(seen) - set(HO_AREAS))
    F = {k: se_F(v, areas) for k, v in runs.items()}
    X5 = {k: se_val(v.get("R"), SE_NEW) for k, v in runs.items()}
    pseeds = sorted({s for (n, s) in runs if n in SE_CANDS and F[(n, s)]})
    seeds, past = pseeds[:CAP_SEEDS], pseeds[CAP_SEEDS:]
    diffs = {}
    for a in SE_CANDS:
        per = [[F[(a, s)][ar] for s in seeds if ar in F.get((a, s), {})] for ar in areas]
        if any(per):
            diffs[a] = per
    V = eps_rule(diffs, eps, LOOK_ALPHA) if diffs else {}
    n_read = max([len(xs) for per in diffs.values() for xs in per] or [0])
    room = n_read < CAP_SEEDS and not pool
    dd = [X5[("P_parent", s)] - X5[("P", s)] for s in seeds
          if X5.get(("P_parent", s)) is not None and X5.get(("P", s)) is not None]
    n_d, m_d, se_d = mean_se(dd)
    tq = t_quantile(1.0 - LOOK_ALPHA, n_d - 1) if se_d is not None else None
    d_row = (n_d, m_d, None if tq is None else m_d - tq * se_d, None if tq is None else m_d + tq * se_d)
    worst = {a: max([m for m in (mean(xs) for xs in diffs[a]) if m is not None] or [None]) for a in diffs}
    kind, pick, why = se_choose(V, d_row, worst, room)
    if refused:
        kind = "refused"
    # THE NEXT PARENTS: past every seed this fleet named, ran or booked (a seed whose parent failed has no session).
    named = [int(x) for x in (sget(r"^=== \d+ windows per run, DATA_STREAM_BYTES=\d+, seeds: (.*?), EXTRA=") or "").split()
             if x.isdigit()]
    nxt = 1 + max([s for (n, s) in runs] + named
                  + [int(t.rpartition(".s")[2]) for t in done if t.rpartition(".s")[2].isdigit()] or [-1])
    cmd = None
    if kind == "topup":
        sz = re.search(r"^=== (\d+) windows per run, DATA_STREAM_BYTES=(\d+), seeds: .*?, EXTRA='(.*)'$", S, re.M)
        pe = re.search(r"EVAL_RETENTION_EVERY=(\d+) pinned", S)
        dv = re.search(r"^=== \d+ CPU core\(s\), \d+ GPU\(s\), device=(\w+)", S, re.M)
        pr = (re.findall(r"^=== \d+ run\(s\), (\d+) at a time", S, re.M) or [None])[-1]
        pa = sget(r"^=== parents: (\S+) at seeds")
        sw = sget(r"^=== session: (\d+) windows")
        wh = sget(r"^=== session: .*?its n_live \+ (\d+)\)")
        oa = os.path.realpath(OUT)
        kv = [("EXP", "session"), ("SEEDS", " ".join(str(s) for s in range(nxt, nxt + CAP_SEEDS - n_read))),
              ("FILL", "0")]
        if sz and sz.group(1) != "20000":
            kv.append(("WINDOWS", sz.group(1)))
        if sz and int(sz.group(2)) != int(sz.group(1)) * 189:
            kv.append(("EPOCH_BYTES", sz.group(2)))
        if sz and sz.group(3):
            kv.append(("EXTRA", sz.group(3)))
        if pa:
            kv.append(("PARENT_ARM", pa))
        if pe and pe.group(1) != "700":
            kv.append(("PROBE_EVERY", pe.group(1)))
        if sw and sw != "5000":
            kv.append(("SESSION_WINDOWS", sw))
        if wh and wh != "2048":
            kv.append(("W_HEADROOM", wh))
        if dv and dv.group(1) != "cuda":
            kv.append(("DEVICE", dv.group(1)))
        if pr:
            kv.append(("PAR", pr))
        kv += [("OUT", (oa[:-4] if oa.endswith("_out") else oa) + "_topup_out"), ("POOL_WITH", oa)]
        cmd = " ".join(f"{k}={shlex.quote(v)}" for k, v in kv) + f" bash {shlex.quote(os.path.join(home, 'tools', 'gpu_launch.sh'))} --go"
    tail_ = f" (ε {eps:g} bits/byte per old area, {n_read} parent(s))"
    rate = ("at the measurement protocol's rate (OPT_LR_CONTINUE=as_logged, CONTRACT-Q-DATA-7), which 5.2 re-reads "
            "at the preset's")
    if kind == "take" and pick == "P_parent":
        decision = (f"P_parent is taken (O9): {why}. The continue preset's provisional rehearsal (DATA_REHEARSE_PARENT=1, "
                    f"'replay' 0.27) holds {rate}; no training default moves" + tail_)
    elif kind == "take":
        decision = (f"P is taken (O9): {why}. The preset's rehearsal is not needed {rate}, recorded so for 5.2; no "
                    f"training default moves" + tail_)
    elif kind == "none":
        decision = (f"neither is admitted: {why}; nothing ships, and the next arms run ({SE_NEXT}), O9 escalating only "
                    f"when every candidate, these included, FAILs" + tail_)
    elif kind == "unresolved":
        decision = (f"UNRESOLVED at the cap: {why}; reported so, nothing ships, and the next arms run ({SE_NEXT})"
                    + tail_)
    elif kind == "topup":
        decision = (f"UNRESOLVED at {n_read} parent(s): {why}; top up to the cap of {CAP_SEEDS} on this card and torch "
                    f"with the command below (its parents stage trains the new parents first), then paste back the "
                    f"top-up's block, which reads both fleets" + tail_)
    elif kind == "refused":
        decision = (f"NOTHING IS DECIDED: this top-up's parents pool with its first fleet's only where commit, card, "
                    f"torch and shape match, and {refused}; the first fleet's reading stands, and the top-up runs again "
                    f"on its card and torch, at its commit")
    else:
        decision = f"UNDECIDED: {why}"

    # ---------------------------------------------------------------- the runs, as read
    star = lambda k: "*" if pooled and k in here else ""
    print()
    print("=== RUNS (F per old area = R - resume start, memory-off, report half; x5 at R) ===")
    missing = []
    for (n, s), v in sorted(runs.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        f_ = F[(n, s)]
        why_ = ("NO PROBE SERIES" if v["series"] is None else "NO RESUME-START ROW" if not v["res"] else
                "NO R ROW" if not v["R"] else "")
        if why_:
            missing.append(v["tag"] + star((n, s)))
        print(f"  {n:<9} s{s:<3} {fmt(v['win'], 'n'):>6} win  " + ("  ".join(f"{a} {f_[a]:+.5f}" for a in areas if a in f_)
                                                                   or why_)
              + (f"  {SE_NEW} {X5[(n, s)]:.5f}" if X5.get((n, s)) is not None else "")
              + ("" if v["capped"] or why_ else "  ENDED BEFORE ITS WINDOW CAP"))

    def cell(i, row, n_arm):
        n, m, lo, up = row
        if m is None:
            return f"{areas[i]} -"
        return (f"{areas[i]} {m:+.4f} " + (f"[{lo:+.4f},{up:+.4f}]" if lo is not None else "[-]")
                + (f" (n={n})" if n != n_arm else ""))

    rule_rows = []
    for a in SE_CANDS:
        if a not in V:
            rule_rows.append(f"  {a}: NO READING at any parent -- no evidence either way, not a pass")
            continue
        r_ = V[a]
        n_arm = max([n for n, _, _, _ in r_["phases"]] or [0])
        rule_rows.append(f"  {a} n={n_arm} a={r_['level']:.3g}: "
                         + " ".join(cell(i, row, n_arm) for i, row in enumerate(r_["phases"]))
                         + f" -> {r_['verdict']}"
                         + (f" ({r_['note'].replace('some phase', 'some area')})" if r_["note"] else ""))
    rule_head = (f"RULE (§8 5.3a; O2, O9): ε {eps:g} bits/byte; per old area ({len(areas)}), F = R - resume start over "
                 f"the parents, each look (7 parents; a top-up's pooled 11) at {LOOK_ALPHA:g}: mean [lower at t(1 - "
                 f"a/{len(areas)}), Holm's a across P and P_parent; one-sided upper at t({1 - LOOK_ALPHA:g})]"
                 + (" -- this fleet alone, deciding nothing" if refused else ""))
    o9_line = (f"O9 (the new area): {SE_NEW} at R, P_parent - P paired by parent: "
               + ("-" if m_d is None else f"{m_d:+.4f} " + (f"[{d_row[2]:+.4f},{d_row[3]:+.4f}]" if d_row[2] is not None
                                                             else "[-]") + f" n={n_d}")
               + f", one-sided at t({1 - LOOK_ALPHA:g}); below 0 favours P_parent")
    # THE ANCHOR, ITEM FOR ITEM (O2): the resume-start row's pairing against the parent's R (the series' `paired`,
    # written since 2026-10-02): every difference 0 on every area and half says the session read its parent's
    # final reading again.
    anc, anc_bad, anc_none = 0, [], 0
    for k, v in sorted(runs.items()):
        p_ = (v.get("res") or {}).get("paired")
        if not v.get("res"):
            continue
        if not p_:
            anc_none += 1
            continue
        cells = [x for hs in p_.values() for x in hs.values()]
        if cells and all(int(x[0]) > 0 and x[1] == 0 and (x[2] in (0, None)) for x in cells):
            anc += 1
        else:
            anc_bad.append((max((abs(x[1]) for x in cells if x[1] is not None), default=0.0), v["tag"] + star(k)))
    n_res = anc + len(anc_bad) + anc_none
    anchor = (f"ANCHOR (O2): the resume start against the parent's R, item for item: equal in {anc} of {n_res} session(s)"
              + (f"; DIFFERS in {len(anc_bad)} (largest |mean| {max(anc_bad)[0]:.3g}, {max(anc_bad)[1]}: F still "
                 f"subtracts the session's own start)" if anc_bad else "")
              + (f"; {anc_none} with no pairing written (a tree before 2026-10-02)" if anc_none else ""))
    print()
    print("=== " + anchor + " ===")
    print()
    print("=== " + rule_head + " ===")
    for l in rule_rows:
        print(l)
    print("  " + o9_line)
    print()
    print(f"=== DECISION: {decision} ===")
    if cmd:
        print(f"    top-up: {cmd}")
    extra_rows = []
    if missing:
        extra_rows.append(f"  left out (no endpoint): {' '.join(missing)}")
    if past:
        extra_rows.append(f"  parents past the cap of {CAP_SEEDS}, not read: {' '.join(map(str, past))}")
    for l in extra_rows:
        print(l)

    # ---------------------------------------------------------------- reported, deciding nothing
    def per_arm(a):
        return [(s, runs[(a, s)]) for s in seeds if (a, s) in runs]

    def rms(xs):
        xs = [x for x in xs if x is not None]
        return math.sqrt(sum(x * x for x in xs) / len(xs)) if xs else None

    rep_lines = []
    # (1) x5's learning: its first in-run reading (where it arrived) and its R reading, mean over the parents read.
    xl = []
    for a in SE_CANDS + ("P_twin",):
        f5 = mean([se_val(v["first5"], SE_NEW) for _, v in per_arm(a)])
        r5 = mean([X5.get((a, s)) for s, _ in per_arm(a)])
        if r5 is not None:
            xl.append(f"{a} {fmt(f5, '.4f')} -> {r5:.4f}")
    if xl:
        rep_lines.append(f"  {SE_NEW}'s learning (its first in-run reading -> R, mean over parents): " + " | ".join(xl))
    # (2) 5.1's SDs per old area (NEW-02, C04, O11) and the single-run gate's arithmetic: between-run from the twins,
    # per-window from R - resume start item by item (the R row's pairing), one session's SD at the probe's windows.
    K = len(areas) or 1
    try:
        from statistics import NormalDist
        zk, zp = NormalDist().inv_cdf(1.0 - 0.05 / K), NormalDist().inv_cdf(0.80)
    except ImportError:                                  # python < 3.8: the two quantiles at K 4
        zk, zp = 2.241403, 0.841621
    T = eps / (zk + zp)
    sd_rows = []
    for ar in areas:
        tw = [F[("P_twin", s)][ar] - F[("P", s)][ar] for s in seeds
              if ar in F.get(("P_twin", s), {}) and ar in F.get(("P", s), {})]
        sb = rms(tw) / math.sqrt(2) if tw else None
        pw = [(((v.get("R") or {}).get("paired") or {}).get(ar) or {}).get("report") for a in SE_CANDS + ("P_twin",)
              for _, v in per_arm(a)]
        pw = [x for x in pw if isinstance(x, list) and len(x) == 3 and x[2] is not None]
        sw = rms([x[2] for x in pw])
        nw = int(round(mean([x[0] for x in pw]))) if pw else None
        if sb is None and sw is None:
            continue
        one = math.sqrt(sb ** 2 + sw ** 2 / nw) if sb is not None and sw is not None and nw else None
        if one is None:
            verdict_ = "-"
        elif one <= T:
            verdict_ = f"meets it at {nw} windows a half"
        elif sb is not None and sb >= T:
            verdict_ = "the between-run SD alone exceeds it: O10's second-seed replay"
        else:
            verdict_ = f"needs {math.ceil(sw ** 2 / (T ** 2 - sb ** 2))} windows a half"
        sd_rows.append(f"    {ar}: between {fmt(sb, '.4f')} (n={len(tw)}) | per-window {fmt(sw, '.4f')} | one session "
                       f"{fmt(one, '.4f')}: {verdict_}")
    if sd_rows:
        rep_lines.append(f"  5.1's SDs per old area (NEW-02): between-run from the twins, RMS(P_twin - P)/√2; per-window "
                         f"from R - resume start item by item (report half); one session's SD, √(between² + "
                         f"per-window²/n), against the single-run gate's ε/(z(1 - 0.05/{K}) + 0.84) = {T:.4f}, K {K}:")
        rep_lines += sd_rows
    # (3) W at its parent (NEW-20, descriptive): W - P there, its slots, n_live past the parent's, births.
    wl = {}                                   # W's line in this fleet's SUMMARY, and in a pooled first fleet's
    for txt_ in (S, rd(os.path.join(pooled, "SUMMARY.txt")) if pooled else ""):
        for m in re.finditer(r"^=== W: FAB_SLOTS=(\d+) at \S+\.s(\d+), the parent with the most experts \(n_live (\d+) "
                             r"\+ W_HEADROOM (\d+), against its (\d+) slots\)", txt_, re.M):
            wl[int(m.group(2))] = m.groups()
    for (n, s), v in sorted(runs.items()):
        if n != "W":
            continue
        p0 = runs.get(("P", s)) or {}
        fw, fp = F.get(("W", s), {}), F.get(("P", s), {})
        w_ = wl.get(s)
        psl = int(w_[4]) if w_ else None
        rep_lines.append(
            f"  W (NEW-20) at the parent s{s}{star((n, s))}"
            + (f", FAB_SLOTS {w_[0]} (its n_live {w_[2]} + {w_[3]}; its slots {psl})" if w_ else "")
            + ": W - P F " + " ".join(f"{a} {fmt(fw[a] - fp[a] if a in fw and a in fp else None, '+.4f')}" for a in areas)
            + f", {SE_NEW} {fmt(X5.get(('W', s)) - X5[('P', s)] if X5.get(('W', s)) is not None and X5.get(('P', s)) is not None else None, '+.4f')}"
            + f"; n_live at the end W {fmt(v['nlive'], 'n')}"
            + ("" if v["nlive"] is None or not psl else
               f" ({int(v['nlive']) - psl} past the parent's {psl} slots)" if v["nlive"] > psl else
               f" (within the parent's {psl} slots)")
            + f", P {fmt(p0.get('nlive'), 'n')}; births W {fmt(v['births'], 'n')}, P {fmt(p0.get('births'), 'n')}; "
            f"fab.resume_widened {fmt(v['widened'], 'n')}")
    # (4) the pricing every session states (CONTRACT-Q-DATA-7) and the rehearsal P_parent fired.
    pc = {}
    for v in runs.values():
        pc[v["pricing"] or "absent"] = pc.get(v["pricing"] or "absent", 0) + 1
    rep_lines.append("  opt.continue.pricing (each session's rate, CONTRACT-Q-DATA-7): "
                     + ", ".join(f"'{k}' {c}" for k, c in sorted(pc.items(), key=lambda kv: -kv[1]))
                     + f" of {len(runs)}")
    fired = {a: sum(1 for (n, s), v in runs.items() if n == a and v["rehearse"] == "fired") for a in SE_CANDS + ("P_twin", "W")}
    tot = {a: sum(1 for (n, s) in runs if n == a) for a in fired}
    rep_lines.append("  data.rehearse_parent FIRED (O9's rehearsal): " + " | ".join(f"{a} {fired[a]} of {tot[a]}"
                                                                                  for a in fired if tot[a]))

    # ---------------------------------------------------------------- rates
    rate_rows = []
    for a in SE_CANDS + ("P_twin", "W"):
        wps = [v["win"] / v["secs"] for (n, s), v in runs.items() if n == a and v["win"] and v["secs"]]
        if wps:
            rate_rows.append(f"{a} {mean(wps):.2f} [{min(wps):.2f}-{max(wps):.2f}]")
    agg = []
    fin = re.search(r"^---- fleet finished in \d+ min \((\d+) s\)", S, re.M)
    pst = re.search(r"^---- parents stage finished in \d+ min \((\d+) s\)", S, re.M)
    eta = re.search(r"^=== ETA by waves: about \d+ min \((\d+) s\)", S, re.M)
    if fin and int(fin.group(1)) > 0:
        wall = int(fin.group(1)) + (int(pst.group(1)) if pst else 0)
        tw = sum(v["win"] for k, v in here.items() if v["win"])
        agg.append(f"  this fleet: {tw:,} session windows in {fin.group(1)} s of the sessions' wall = "
                   f"{tw / int(fin.group(1)):.2f} windows/s aggregate"
                   + (f"; the parents stage {pst.group(1)} s" if pst else "")
                   + (f"; ETA by waves {eta.group(1)} s, took {wall} s: {wall / max(1, int(eta.group(1))):.2f}x"
                      if eta else ""))
    par_lines = []
    pl = sget(r"^=== parents: (.*)$")
    if pl:
        par_lines.append("parents: " + re.sub(r",? sha256 in its FINALS.sha256$", "", pl)[:200])
    pdone = {}
    for l in rd(os.path.join(OUT, "parents", "_done.txt")).splitlines():
        m = re.match(r"(\S+) rc=(-?\d+) secs=(\d+)", l)
        if m:
            pdone[m.group(1)] = int(m.group(2))
    pbad = [f"{t} rc={c}" for t, c in sorted(pdone.items()) if c != 0]
    if pbad:
        par_lines.append(f"  PARENTS STAGE FAILED: {' '.join(pbad)} -- their seeds' sessions did not run "
                         f"(logs in {os.path.join(OUT, 'parents')})")

    print()
    print("=== REPORTED, DECIDES NOTHING (§8 5.3a) ===")
    for l in rep_lines + ["  windows/s per session (this process): " + " | ".join(rate_rows)] + agg + par_lines:
        print(l)

    # ---------------------------------------------------------------- the block
    hd = [f"F per old area at R - resume start (memory-off, report half), per parent: "
          + " | ".join(a for a in SE_CANDS) + f"; then {SE_NEW} at R",
          "  seed  " + " | ".join(" ".join(f"{a:>7}" for a in areas) for _ in SE_CANDS)
          + " | " + " ".join(f"{a:>8}" for a in SE_CANDS)]
    t_rows = []
    for s in seeds:
        cells = " | ".join(" ".join(f"{fmt(F.get((a, s), {}).get(x), '+.4f'):>7}" for x in areas) for a in SE_CANDS)
        cells += " | " + " ".join(f"{fmt(X5.get((a, s)), '.4f'):>8}" for a in SE_CANDS)
        t_rows.append(f"  {'s' + str(s) + star(('P', s)):<6}{cells}")

    def table(n=None):
        if n is None or len(t_rows) + 2 <= n:
            return hd + t_rows
        keep = max(0, n - 3)
        return hd + t_rows[:keep] + [f"  ... {len(t_rows) - keep} more parent row(s): in ANALYSIS.txt's RUNS"]
    labels = ["synthetic source", "as_logged"] + (["pooled"] if pooled else [])
    fl = failures({k: dict(curve=v["curve"]) for k, v in here.items()}, done)
    short = [v["tag"] for k, v in sorted(here.items()) if not v["capped"] and v["series"] is not None
             and done.get(v["tag"], (1,))[0] == 0]
    if short:
        fl.append(f"  ENDED BEFORE ITS WINDOW CAP: {' '.join(short[:12])}" + (" ..." if len(short) > 12 else ""))
    emit([
        ("head", head("session", labels) + fl + par_lines, 0),
        ("pool", pool_lines, 0),
        ("per-parent rows", table, 0),
        ("verdict", [anchor, rule_head] + rule_rows + [o9_line, f"DECISION: {decision}"]
         + ([f"  top-up: {cmd}"] if cmd else []) + extra_rows, 0),
        ("reported", ["REPORTED, DECIDES NOTHING:"], 0),
        ("x5", [l for l in rep_lines if "learning" in l], 1),
        ("SDs", [l for l in rep_lines if "5.1's SDs" in l or l.startswith("    ")], 1),
        ("W", [l for l in rep_lines if l.startswith("  W (NEW-20)")], 1),
        ("pricing and rehearsal", [l for l in rep_lines if "opt.continue.pricing" in l or "rehearse_parent" in l], 2),
        ("rates", ["  windows/s per session: " + " | ".join(rate_rows)], 4),
        ("aggregate", agg, 3),
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
elif MODE == "heldout":
    heldout(int(sys.argv[3]), sys.argv[4], float(sys.argv[5]), sys.argv[6], sys.argv[7])
elif MODE == "session":
    session(int(sys.argv[3]), sys.argv[4], float(sys.argv[5]), sys.argv[6], sys.argv[7])
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
# first on its path, as run.py arranges it: the root's memory.py shadowed src/memory until 2026-09-28.
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
paste_back() {  # print the owner's block (EXP=retok's, heldout's and session's analyses wrote it; the others are wrapped here)
  [[ "$EXP" == retok || "$EXP" == heldout || "$EXP" == session ]] || gw_py wrap "$OUT" "$EXP" "$(archive_path)"
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
      --exclude="$b/ckpt" --exclude="$b/smoke/ckpt" --exclude="$b/parents/ckpt" --exclude="$b/mps" --exclude="$b/code" \
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
    smoke) [[ "$(gw_st step)" == sessions ]] && echo "the sessions' smoke" || echo "the smoke" ;;
    cal) echo "calibration $(gw_st step)" ;;
    parents) n=$(grep -c 'rc=' "$OUT/parents/_done.txt" 2>/dev/null)
             echo "the parents stage (${n:-0} of $(gw_st runs_total) run(s) ended)" ;;
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
  # THE HINT NAMES THE CURRENT TEST (2026-10-02, review of 49a657d): it named the decided retok fleet.
  [[ "$_v" == 2 && -z "$_EXP_GIVEN" && -z "$_OUT_GIVEN" ]] \
    && echo "   (EXP was not given, so this read $OUT, EXP=world's; the owner brief's current test, test 4, is EXP=heldout bash $(printf %q "$GW_HOME/gpu_world.sh") --status)"
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

# THE WHOLE-EPOCH WORLD RE-RUN WAITS FOR O13's TWO WORLD LEVERS (§8 6.5). It waited for SR0 ("do not run
# it", Proposal 05 §8 1.5) until 2026-09-29; SR0 is built, and its settings are this experiment's pins.
# The sizing and the pre-registration are printed, with which of the two levers this tree declares
# (read off src/, as LEVELS is), and NOTHING is written, not even $OUT.
if [[ "$EXP" == world_epoch && "$GO_WORLD_EPOCH" != 1 ]]; then
  _o13=""
  for _l in forecast_bound:WORLD_FORECAST_BOUND input_grad:WORLD_INPUT_GRAD; do
    if grep -qE "^ +${_l%%:*} = Lever\(" "$CODE_DIR/src/world/levers.py" 2>/dev/null; then _st=declared; else _st="not declared"; fi
    _o13="$_o13${_o13:+, }${_l#*:} $_st"
  done
  plan_banner
  echo "=== EXP=world_epoch IS SIZED, NOT RUN: it is the WORLD re-run pre-registered for §8 6.5 (register"
  echo "    note WORLD 3-4, O13). All five arms -- fb_off, fb_on, skip, world_off and detached -- in ONE"
  echo "    commit, 5 paired seeds, every run reading one whole epoch (all four phases) with the pins above:"
  echo "    TOK_RETOK_EVERY and DATA_DRAW, and SR0's DATA_SYNTH_HOLDOUT ON and retention probe ON at"
  echo "    EVAL_RETENTION_EVERY=$PROBE_EVERY (04-6.2's cap, written as a number), each run writing its reading series."
  echo "    Its checkpoints (KEEP_CKPT=1): each run's final save and the probe's best saves beside it --"
  echo "    ckpt.pt.best and .best.prev$( (( BEST_KEEP > 0 )) && echo ", and CKPT_BEST_KEEP=$BEST_KEEP's slots") -- up to $(( 1 + BEST_FILES )) checkpoint files a run, all budgeted."
  echo "    It waits for O13's two WORLD levers, built with CPU known answers before it (operation only;"
  echo "    provisional names, 'detached' the input gradient's fifth arm): in this tree $_o13."
  echo "    Rule: WORLD_FEEDBACK flips ON only if fb_on beats fb_off on the time-integrated all-area"
  echo "    held-out gap (one-sided paired t, alpha 0.05; end-state beside it), is not worse than eps on the"
  echo "    worst area, and no seed shows latent_std < 0.9 or extra_ratio_max > 10. Both endpoints are"
  echo "    reported, with Q-WORLD-10's last-half and full-run prequential statistic beside the rule."
  echo "    GO_WORLD_EPOCH=1 lifts this guard (until O13's build adds the fifth arm, the four here run as an"
  echo "    operation check only). Nothing was written."
  exit 2
fi
if [[ "$KEEP_CKPT" == 1 && "$OUT" =~ [[:space:]] ]]; then
  echo "!! OUT='$OUT' holds whitespace, and with KEEP_CKPT=1 its path rides inside the job lines, which are"
  echo "   split on whitespace. Choose an OUT without spaces. Nothing was started."; exit 2
fi

# A TOP-UP NAMES ITS FIRST FLEET (§8 6.3a, 5.3a): POOL_WITH=<that fleet's OUT>, which the launch checks before
# anything is written -- a fleet of this EXP there, not this OUT (a launch moves the fleet in OUT aside), and
# none of its seeds run again -- and the banner records for the analysis.
POOL_ABS=""; POOL_SEEDS=""
if [[ -n "$POOL_WITH" ]]; then
  [[ "$EXP" == heldout || "$EXP" == session ]] \
    || { echo "!! POOL_WITH names a top-up's first fleet, which only EXP=heldout and EXP=session read. Nothing was started."; exit 2; }
  POOL_ABS=$(cd "$POOL_WITH" 2>/dev/null && pwd -P)
  if [[ -z "$POOL_ABS" ]] || ! grep -q "^=== plan: EXP=$EXP;" "$POOL_ABS/SUMMARY.txt" 2>/dev/null; then
    echo "!! POOL_WITH='$POOL_WITH' holds no EXP=$EXP fleet (no SUMMARY.txt that records one). Nothing was started."; exit 2
  fi
  if [[ "$POOL_ABS" == "$(realpath -m -- "$OUT")" ]]; then
    echo "!! POOL_WITH is this OUT, and a launch moves the fleet in OUT aside: give the top-up its own OUT, as the"
    echo "   first fleet's block prints it. Nothing was started."; exit 2
  fi
  POOL_SEEDS=$(sed -n "s/^=== [0-9]* windows per run, DATA_STREAM_BYTES=[0-9]*, seeds: \(.*\), EXTRA='.*'\$/\1/p" \
               "$POOL_ABS/SUMMARY.txt" | head -1)
  for _s in $SEEDS; do
    [[ " $POOL_SEEDS " == *" $_s "* ]] \
      && { echo "!! SEEDS: seed $_s ran in the first fleet too ($POOL_SEEDS). Nothing was started."; exit 2; }
  done
fi

# EXP=session's PARENTS (§8 5.3a), checked before anything is written: PARENTS (a directory holding FINALS.sha256
# and ckpt/, the held-out fleet's OUT or its unpacked finals) lists PARENT_ARM's final checkpoint and vocabulary at
# every seed in SEEDS, each file's sha256 equals the manifest's, and each final is read -- its step, n_live, FAB_SLOTS
# and its areas' generated length, which the sessions' stream must keep (so no old block moves). Without PARENTS
# the parents stage trains them, and they are read after it. Read with the fleet's code, cwd the parents' directory.
parent_facts() {  # dir arm seed... -> one line a seed, "seed step n_live slots area_bytes", or "!! <why>"
  ( cd "$1" 9>&- && python3 - "$PWD" "$CODE_DIR" "${@:2}" <<'PY'
import os, sys
d, code, arm, seeds = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]
sys.path[:] = [p for p in sys.path if p and os.path.abspath(p) != os.path.abspath(code)]
sys.path.insert(0, os.path.join(code, "src"))
import torch
for s in seeds:
    p = os.path.join(d, "ckpt", f"{arm}.s{s}", "ckpt.pt")
    try:
        try:
            b = torch.load(p, map_location="cpu", mmap=True, weights_only=False)
        except TypeError:                               # a torch without mmap=
            b = torch.load(p, map_location="cpu", weights_only=False)
        pay = b.get("payload") or {}
        lens = sorted({int(v) for v in ((pay.get("DATA") or {}).get("bytes_present") or {}).values()})
        print(s, int(b["step"]), int((pay.get("FAB") or {})["n_live"]), int((b.get("geometry") or {})["fab.slots"][0]),
              lens[0] if len(lens) == 1 else -1)
    except Exception as e:                              # noqa: BLE001 -- said, and the launch refuses
        print(f"!! {arm}.s{s}: {type(e).__name__}: {str(e)[:200]}")
PY
  )
}
# THE SESSIONS' INPUTS OFF THE FACTS: each parent's step (PSTEP, which the dashboard counts a session's windows
# past), W's parent (the most experts, the lowest seed on a tie) and W_SLOTS, max(its slots, its n_live +
# W_HEADROOM). A parent whose areas were generated at another length than the sessions' stream keeps is refused:
# its old blocks would move (tests/test_holdout.py H2), and the fix is the shape of the fleet that trained it.
declare -A PSTEP=()
W_SEED=""; W_SLOTS=""; W_NLIVE=""; W_PSLOTS=""
parents_take() {  # facts -> 0, or 1 having said why
  local seed step nl sl ln best=-1 want _sm
  _sm=$(echo " $EXTRA " | tr ' ' '\n' | sed -n 's/^DATA_SEG_MAX=//p' | tail -1)
  [[ -n "$_sm" ]] || _sm=$(sed -n 's/^    seg_max = Lever( *\([0-9][0-9]*\) *,.*/\1/p' "$CODE_DIR/src/data/levers.py" 2>/dev/null | head -1)
  want=$(( SBYTES / 5 )); (( want < ${_sm:-0} + 1 )) && want=$(( ${_sm:-0} + 1 )); (( want < 5000 )) && want=5000
  want=$(( 2 * want ))
  while read -r seed step nl sl ln; do
    [[ -z "$seed" ]] && continue
    if [[ "$seed" == "!!" ]]; then echo "!! the parent $step $nl $sl $ln"; return 1; fi
    if [[ "$ln" != "$want" ]]; then
      echo "!! the parent $PARENT_ARM.s$seed's areas were generated $ln bytes long, and a session at DATA_STREAM_BYTES=$SBYTES"
      echo "   (5/4 of the parents' $PBYTES) generates them $want long: its old held-out blocks would move. Give this"
      echo "   fleet the WINDOWS (or EPOCH_BYTES) and EXTRA of the fleet that trained its parents."
      return 1
    fi
    PSTEP[$seed]=$step
    if (( nl > best )); then best=$nl; W_SEED=$seed; W_NLIVE=$nl; W_PSLOTS=$sl; fi
  done <<< "$1"
  [[ -n "$W_SEED" ]] || { echo "!! no parent could be read"; return 1; }
  W_SLOTS=$(( W_NLIVE + W_HEADROOM > W_PSLOTS ? W_NLIVE + W_HEADROOM : W_PSLOTS ))
  return 0
}
PARENTS_ABS=""; PARENTS_CHECKED=0
if [[ "$EXP" == session && -n "$PARENTS" ]]; then
  PARENTS_ABS=$(cd "$PARENTS" 2>/dev/null && pwd -P)
  [[ -n "$PARENTS_ABS" && -f "$PARENTS_ABS/FINALS.sha256" ]] \
    || { echo "!! PARENTS='$PARENTS' holds no FINALS.sha256 (the held-out fleet's OUT, or its finals unpacked). Nothing was started."; exit 2; }
  [[ "$PARENTS_ABS" == "$(realpath -m -- "$OUT")" ]] \
    && { echo "!! PARENTS is this OUT, and a launch moves the fleet in OUT aside: give the sessions their own OUT. Nothing was started."; exit 2; }
  _want=""
  for _s in $SEEDS; do _want="$_want ckpt/$PARENT_ARM.s$_s/ckpt.pt ckpt/$PARENT_ARM.s$_s.dyntok.json"; done
  _lines=$(awk -v w="$_want" 'BEGIN { n = split(w, a, " "); for (i = 1; i <= n; i++) k[a[i]] = 1 }
                               k[substr($0, 67)] == 1 { print; k[substr($0, 67)] = 2 }
                               END { for (f in k) if (k[f] == 1) print "MISSING " f }' "$PARENTS_ABS/FINALS.sha256")
  _miss=$(sed -n 's/^MISSING //p' <<< "$_lines" | sort | head -4 | tr '\n' ' ')
  _lines=$(grep -v '^MISSING ' <<< "$_lines")
  [[ -z "$_miss" ]] || { echo "!! PARENTS' FINALS.sha256 lists no $_miss(PARENT_ARM=$PARENT_ARM, SEEDS='$SEEDS'). Nothing was started."; exit 2; }
  if [[ -n "${GW_PARENTS_SUM:-}" && "$GW_PARENTS_SUM" == "$(sha256sum <<< "$_lines" | cut -c1-16)" ]]; then
    PARENTS_CHECKED=${GW_PARENTS_CHECKED:-0}                 # the checkout's launch checked them before the copy
  else
    _bad=$(cd "$PARENTS_ABS" && sha256sum -c --quiet 2>&1 <<< "$_lines" | head -4)
    [[ -z "$_bad" ]] || { echo "!! PARENTS: a final does not match its sha256 in FINALS.sha256:"; echo "$_bad" | sed 's/^/   /'; echo "   Nothing was started."; exit 2; }
    PARENTS_CHECKED=$(grep -c . <<< "$_lines")
    export GW_PARENTS_SUM=$(sha256sum <<< "$_lines" | cut -c1-16) GW_PARENTS_CHECKED=$PARENTS_CHECKED
  fi
  _facts=$(parent_facts "$PARENTS_ABS" "$PARENT_ARM" $SEEDS)
  parents_take "$_facts" || { echo "   Nothing was started."; exit 2; }
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
  local vis=() fb=() ps=() ck="" kd="" w="" a
  [[ "$DEVICE" == cuda ]] && vis=(CUDA_VISIBLE_DEVICES="$gpu")
  [[ "$FLUSH_BYTES" == 1 ]] && fb=(--flush-bytes "${CURVE_DIR:-$OUT/curves}/$tag.bytes.json")
  # EXP=world_epoch's AND EXP=heldout's RULES READ THE RETENTION PROBE (note WORLD 4, §8 6.3a): each run
  # writes its reading series beside its curve, and the archive packs it with the curves.
  [[ "$EXP" == world_epoch || "$EXP" == heldout || "$EXP" == session ]] \
    && ps=(--probe-series "${CURVE_DIR:-$OUT/curves}/$tag.probe.json")
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
      "${ps[@]}" > "$log" 2>&1 &
  rp=$!
  # A SESSION'S PROGRESS LINES COUNT ITS RUN'S WINDOWS, ITS PARENT'S INCLUDED (EXP=session): base= is its parent's
  # step, which the dashboard takes off them.
  local base=""
  for a in "$@"; do [[ "$a" == CKPT_RESUME=* && -n "${PSTEP[$seed]:-}" ]] && base=" base=${PSTEP[$seed]}"; done
  echo "$tag pid=$rp t0=$t0 cap=$win target=$tw$base" >> "${JOB_DIR:-$OUT/logs}/_started.txt"
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
# EXP=session's SESSIONS RESUME A PARENT (§8 5.3a): its job line is the parent arm's settings, the session's pins, its
# arm's and its resume, in that order, the later winning. Its smoke is the four sessions from the parents, P, P_parent
# and P_twin at the first seed and W at W's, when PARENTS names them; without PARENTS the parents' arm at the first
# seed, fresh, and the sessions' smoke after the parents stage.
P0=$(echo $SEEDS | cut -d' ' -f1)
PDIR=""
[[ "$EXP" == session ]] && PDIR=${PARENTS_ABS:-$(realpath -m -- "$OUT/parents")}
session_job() {  # arm seed windows ckpt-base [smoke] -> its job line
  echo "$1 $2 $3 $(arm_env "$PARENT_ARM") $SESS_ENV $(arm_env "$1") CKPT_RESUME=$PDIR/ckpt/$PARENT_ARM.s$2" \
       "$(ckpt_env "$1" "$2" "$4" ${5:-})"
}
session_smoke_jobs() {
  local a
  JOBS=()
  for a in $BASE_ARMS; do add_job "$(session_job "$a" "$P0" "$SMOKE_WINDOWS" "$OUT/smoke/ckpt" smoke)"; done
  add_job "$(session_job W "$W_SEED" "$SMOKE_WINDOWS" "$OUT/smoke/ckpt" smoke)"
}
JOBS=()
if [[ "$EXP" == session && -n "$PARENTS_ABS" ]]; then
  say "---- 1. smoke: every session from the parents ($PARENT_ARM; W's at seed $W_SEED, the rest at seed $P0)," \
      "$SMOKE_WINDOWS windows each, all at once"
  session_smoke_jobs
elif [[ "$EXP" == session ]]; then
  say "---- 1. smoke: the parents' arm $PARENT_ARM, seed $P0, $SMOKE_WINDOWS windows (the sessions' smoke follows the" \
      "parents stage)"
  add_job "$PARENT_ARM $P0 $SMOKE_WINDOWS $(arm_env "$PARENT_ARM") CKPT_DIR=$OUT/smoke/ckpt/$PARENT_ARM.s$P0 CKPT_EVERY=0"
else
  say "---- 1. smoke: every arm, seed 0, $SMOKE_WINDOWS windows, all at once"
  for a in $BASE_ARMS; do add_job "$a 0 $SMOKE_WINDOWS $(arm_env $a) $(ckpt_env $a 0 "$OUT/smoke/ckpt" smoke)"; done
fi
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
# A SMOKE RUN THAT FAILED STOPS THE FLEET WITH ITS BLOCK; and the tripwires and sizing numbers, read off the smoke's
# logs -- functions since EXP=session's second smoke (the sessions', after its parents stage) reads them too.
smoke_rc() {  # dir
  if grep -q "rc=[1-9]" "$1/_done.txt"; then
    say "!! a smoke arm FAILED -- stopping before the fleet:"
    grep "rc=[1-9]" "$1/_done.txt" | sed 's/^/    /' | tee -a "$S"
    for f in $(grep "rc=[1-9]" "$1/_done.txt" | cut -d' ' -f1); do
      say "    --- $f (last 8 lines)"; tail -8 "$1/$f.log" | sed 's/^/      /' | tee -a "$S"
    done
    fail_back "a smoke arm failed" $(grep "rc=[1-9]" "$1/_done.txt" | cut -d' ' -f1 | sed "s#^#$1/#; s#\$#.log#")
    exit 1
  fi
}
smoke_rc "$OUT/smoke"
smoke_read() {  # dir
python3 - "$1" "$DEVICE" "$EXP" <<'PY'
import json, re, sys, glob, os
d, dev = sys.argv[1], sys.argv[2]
exp = sys.argv[3] if len(sys.argv) > 3 else ""
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
    # A SESSION'S ANCHOR (EXP=session, §8 5.3a): its resume-start reading through the memory-off closure, over
    # the four old areas, is what every F subtracts.
    if exp == "session" and arm in ("P", "P_parent", "P_twin", "W"):
        try:
            ser = json.load(open(log[:-4] + ".probe.json"))
        except (OSError, ValueError):
            ser = None
        if not any(isinstance(x, dict) and x.get("kind") == "resume" and x.get("closure") == "memory-off"
                   and {"eng", "py", "num", "c"} <= set(x.get("areas") or {}) for x in ser or []):
            bad.append(f"{os.path.basename(log)[:-4]}: no resume-start reading over the old areas in its probe series")
    m = re.search(r"peak CUDA memory [\d.]+ GiB allocated, ([\d.]+) GiB reserved", t)
    if m: peak = max(peak, float(m.group(1)))
    m = re.search(r"=== (\d+) windows[^\n]*? in ([\d.]+)s", t)
    # A RESUMED RUN'S LINE COUNTS ITS RUN'S WINDOWS (its parent's included) AND THIS PROCESS'S SECONDS.
    h = re.search(r"^=== \d+ windows run total \((\d+) trained by this process", t, re.M)
    if m and float(m.group(2)) > 0: wps.append((int(h.group(1)) if h else int(m.group(1))) / float(m.group(2)))
for b in bad: print("  TRIPWIRE:", b)
print(f"  smoke: {len(glob.glob(os.path.join(d, '*.log')))} arm(s) ran; peak reserved {peak:.3f} GiB per process; "
      f"{min(wps) if wps else 0:.1f}-{max(wps) if wps else 0:.1f} windows/s per process while all ran at once")
print(f"SIZING peak_gib={peak:.4f} wps={min(wps) if wps else 0:.3f} bad={len(bad)}")
PY
}
smoke_trip() {  # sizing
  if echo "$1" | grep -q "bad=[1-9]"; then
    say "!! a tripwire failed in the smoke -- stopping before the fleet."
    fail_back "a smoke tripwire failed: $(echo "$1" | grep TRIPWIRE | head -3 | sed 's/^ *TRIPWIRE: //' | tr '\n' ';')"
    exit 1
  fi
}
SIZING=$(smoke_read "$OUT/smoke" | tee -a "$S")
smoke_trip "$SIZING"
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
# (EXP=session's parents stage saves its finals at any KEEP_CKPT -- they are the sessions' parents -- so its smoke does.)
if [[ "$KEEP_CKPT" == 1 || "$EXP" == session ]]; then
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
if [[ "$EXP" == session ]]; then
  # THE PARENTS STAGE'S RUNS, WITHOUT PARENTS (their finals saved at any KEEP_CKPT: they are the sessions' parents),
  # THEN THE SESSIONS: three at every seed and W at one. Until the parents are read W stands at the first seed, for
  # the disk check and the ETA.
  PJOBS=()
  if [[ -z "$PARENTS_ABS" ]]; then
    for s in $SEEDS; do PJOBS+=("$PARENT_ARM $s $RUN_WIN $(arm_env "$PARENT_ARM") CKPT_DIR=$PDIR/ckpt/$PARENT_ARM.s$s CKPT_EVERY=0"); done
  fi
  JOBS=("${PJOBS[@]}")
  for s in $SEEDS; do for a in $BASE_ARMS; do add_job "$a $s $SESSION_WINDOWS"; done; done
  add_job "W ${W_SEED:-$P0} $SESSION_WINDOWS"
else
  for s in $SEEDS; do for a in $BASE_ARMS; do add_job "$a $s $RUN_WIN $(arm_env $a) $(ckpt_env $a $s "$OUT/ckpt")"; done; done
  add_job "${CTRL}_rerun 0 $RUN_WIN $(arm_env $CTRL) $(ckpt_env ${CTRL}_rerun 0 "$OUT/ckpt")"
fi
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
jobs_need() {  # bytes the job list's checkpoints may take (EXP=session: its sessions' only at KEEP_CKPT=1)
  local n=0 line
  for line in "${JOBS[@]}"; do
    [[ "$EXP:$KEEP_CKPT" == session:0 && " P P_parent P_twin W " == *" ${line%% *} "* ]] && continue
    n=$(( n + $(ckpt_files "${line%% *}") ))
  done
  echo $(( n * CKPT_BYTES * 2 ))
}
if [[ "$KEEP_CKPT" == 1 || "$EXP" == session ]]; then
  FREE_B=$(( $(df -Pk "$OUT" | awk 'NR == 2 {print $4}') * 1024 ))
  NEED_B=$(jobs_need)
  if [[ "$NEED_B" -gt "$FREE_B" ]]; then
    # THE FIX FITS THE EXPERIMENT (2026-10-02, review of 49a657d; tools/gpu_launch.sh says the same): EXP=retok's
    # spike test needs k0's saves; EXP=heldout's seeds are pre-registered and its first fleet's finals are the next
    # test's parents, which a top-up's (POOL_WITH) are not.
    case "$EXP" in
      retok) _fx="free space, run fewer SEEDS, or KEEP_CKPT=0 (which leaves the spike test without its control)" ;;
      heldout) if [[ -n "$POOL_WITH" ]]; then _fx="free space, or KEEP_CKPT=0: the next test starts from the first fleet's finals, not a top-up's"
               else _fx="free space, keeping the 7 pre-registered seeds and KEEP_CKPT on: the finals are the next test's parents"; fi ;;
      session) _fx="free space, or KEEP_CKPT=0, which keeps no session's checkpoint (a parents stage keeps its finals: the sessions resume them)" ;;
      *) _fx="free space, run fewer SEEDS, or KEEP_CKPT=0" ;;
    esac
    say "!! disk: the kept checkpoints may need $(gb $NEED_B) GB and $OUT has $(gb $FREE_B) GB free."
    say "!! ${_fx^}."
    [[ -n "$MOVED_ASIDE" ]] && say "!! The previous fleet, moved aside to $MOVED_ASIDE, still holds its checkpoints."
    fail_back "disk: checkpoints may need $(gb $NEED_B) GB, $(gb $FREE_B) GB free ($_fx)"
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
[[ "$KEEP_CKPT" == 1 || "$EXP" == session ]] && say "=== disk: checkpoints may take about $(gb $(jobs_need)) GB" \
  "($(( CKPT_BYTES / 1000000 )) MB x 2 per file) of $(gb $FREE_B) GB free at $OUT"
say "=== ${#JOBS[@]} run(s), $PAR at a time"
# THE ETA IS PRICED AT THE MEASURED AGGREGATE RATE at PAR, over every window the job list holds. It
# assumes every slot stays busy, so the last partial wave makes it slightly optimistic, and the rate
# was measured on short runs whose fabric had not grown yet.
# AND BY WAVES (2026-10-02; register LOW-GPU-WORLD-ETA's owed fix): the 2026-09-27 fleet took 1.95x its
# aggregate ETA because 13 runs at PAR 12 left one running alone, where 2 x (20,000 / 42.88 + 12.6 s)
# came within 3% of the wall. Each run takes its windows at the calibrated rate per run (the aggregate
# over PAR) plus the smoke's startup, and starts in the job list's order when a slot frees, as run_fleet
# starts them; the ETA is the last one's end. Its R stage and saves come on top.
python3 - "${CAL_RATE:-0}" "$SMOKE_WPS" "$PAR" <<PY | tee -a "$S"
import heapq, math
jobs = """$(printf '%s\n' "${JOBS[@]}")""".split("\n")
# A retok job's window count is its cap, set out of reach; it reads about WINDOWS windows.
total = sum(min(int(j.split()[2]), int("$WINDOWS")) for j in jobs if j.strip())
rate, smoke, par = float("${CAL_RATE:-0}"), float("$SMOKE_WPS" or 0), int("$PAR")
if rate <= 0: rate = smoke * par
if rate > 0:
    print(f"=== ETA: about {total / rate / 3600:.1f} h for {total:,} windows at {rate:.1f} windows/s aggregate")
    per, st = rate / par, float("${STARTUP_S:-0}" or 0)
    ws = [int(j.split()[2]) if "$EXP" == "world" else min(int(j.split()[2]), int("$WINDOWS")) for j in jobs if j.strip()]
    ends = [0.0] * max(1, min(par, len(ws)))
    for w in ws:
        heapq.heappush(ends, heapq.heappop(ends) + w / per + st)
    eta = max(ends)
    if "$EXP" == "session":
        # TWO STAGES (§8 5.3a): the parents stage's runs, then the sessions, which start when the last parent ends.
        par_w = [w for j, w in zip([j for j in jobs if j.strip()], ws) if j.split()[0] not in ("P", "P_parent", "P_twin", "W")]
        ses_w = [w for j, w in zip([j for j in jobs if j.strip()], ws) if j.split()[0] in ("P", "P_parent", "P_twin", "W")]
        t1 = 0.0
        if par_w:
            ends = [0.0] * max(1, min(par, len(par_w)))
            for w in par_w:
                heapq.heappush(ends, heapq.heappop(ends) + w / per + st)
            t1 = max(ends)
        ends = [t1] * max(1, min(par, len(ses_w)))
        for w in ses_w:
            heapq.heappush(ends, heapq.heappop(ends) + w / per + st)
        eta = max(ends)
        print(f"=== ETA by waves: about {eta / 60:.0f} min ({eta:.0f} s): "
              + (f"{len(par_w)} parent run(s) in {math.ceil(len(par_w) / par)} wave(s), then " if par_w else "")
              + f"{len(ses_w)} session(s) in {math.ceil(len(ses_w) / par)} wave(s), over {par} slot(s), each run its "
              f"windows at {per:.2f} windows/s plus {st:.0f} s of startup; each run's reads (a session's resume start "
              f"and R) and saves come on top")
    else:
        print(f"=== ETA by waves: about {eta / 60:.0f} min ({eta:.0f} s): {len(ws)} run(s) over {par} slot(s), "
              f"{math.ceil(len(ws) / par)} wave(s), each run its windows at {per:.2f} windows/s plus {st:.0f} s of startup; "
              f"each run's R stage and saves come on top")
PY

# ---------------------------------------------------------------- 3. EXP=session's parents stage and its sessions
SMI_PID=""
smi_start() {  # the nvidia-smi sampler, once
  if [[ "$DEVICE" == cuda && -z "$SMI_PID" ]]; then
    # THE SAMPLER NEVER HOLDS THE LOCK (9>&-): it runs until it is killed, and a SIGKILLed fleet cannot.
    nvidia-smi --query-gpu=index,utilization.gpu,memory.used,memory.total \
               --format=csv,noheader,nounits -l 2 > "$OUT/smi.csv" 2>/dev/null 9>&- &
    SMI_PID=$!
    gw_state smi_pid="$SMI_PID"
  fi
}
# WITHOUT PARENTS THE PARENTS COME FIRST (§8 5.3a): the parents' arm at every seed, one whole epoch, its final kept
# under $OUT/parents/ckpt with a FINALS.sha256 beside it as the held-out fleet's (so a later fleet may name it as
# PARENTS); a parent that failed or saved no final drops its seed's sessions, said here and in the block. The
# finals are then read as PARENTS' are, and the sessions' smoke runs from them before the sessions.
if [[ "$EXP" == session ]]; then
  SJOB_SEEDS=$(echo $SEEDS)
  if [[ -z "$PARENTS_ABS" ]]; then
    JOBS=("${PJOBS[@]}")
    mkdir -p "$OUT/parents"
    say "---- 2a. parents stage started $(date -u +%H:%M:%SZ): $PARENT_ARM at seeds $SJOB_SEEDS, one whole epoch each," \
        "$PAR at a time; each spends ~${STARTUP_S:-15-30} s on the CPU before it trains$HB_NOTE"
    gw_step parents "" "$OUT/parents" "${#JOBS[@]}" "$WINDOWS"
    gw_state par="$PAR" runs_total="${#JOBS[@]}" windows="$WINDOWS"
    smi_start
    _t0=$(date +%s)
    JOB_DIR="$OUT/parents" CURVE_DIR="$OUT/parents" run_fleet "$PAR"
    say "---- parents stage finished in $(( ($(date +%s) - _t0) / 60 )) min ($(( $(date +%s) - _t0 )) s)"
    _ok=""
    for s in $SJOB_SEEDS; do
      awk -v t="$PARENT_ARM.s$s" '$1 == t && $2 == "rc=0" { f = 1 } END { exit !f }' "$OUT/parents/_done.txt" 2>/dev/null \
        && [[ -f "$PDIR/ckpt/$PARENT_ARM.s$s/ckpt.pt" && -f "$PDIR/ckpt/$PARENT_ARM.s$s.dyntok.json" ]] && _ok="$_ok $s"
    done
    _ok=$(echo $_ok)
    [[ "$_ok" != "$SJOB_SEEDS" ]] && say "!! parents that FAILED or saved no final (logs in $OUT/parents): their seeds' sessions do" \
      "not run; seeds left: ${_ok:-none}"
    [[ -n "$_ok" ]] || { fail_back "the parents stage left no parent (its logs are in $OUT/parents)" \
                           $(ls "$OUT/parents"/*.log 2>/dev/null | head -2); exit 1; }
    SJOB_SEEDS=$_ok; P0=${_ok%% *}
    ( cd "$PDIR" && for s in $SJOB_SEEDS; do sha256sum "ckpt/$PARENT_ARM.s$s/ckpt.pt" "ckpt/$PARENT_ARM.s$s.dyntok.json"; done ) \
      > "$PDIR/FINALS.sha256"
    if ! parents_take "$(parent_facts "$PDIR" "$PARENT_ARM" $SJOB_SEEDS)" > "$OUT/parents/.take" 2>&1; then
      say "$(cat "$OUT/parents/.take")"
      fail_back "the parents stage's finals could not be read for the sessions: $(head -1 "$OUT/parents/.take" | sed 's/^!! //')"
      exit 1
    fi
    say "=== parents: $(echo $SJOB_SEEDS | wc -w) final(s) under $PDIR, sha256 in its FINALS.sha256"
  fi
  say "=== W: FAB_SLOTS=$W_SLOTS at $PARENT_ARM.s$W_SEED, the parent with the most experts (n_live $W_NLIVE + W_HEADROOM" \
      "$W_HEADROOM, against its $W_PSLOTS slots)"
  if [[ -z "$PARENTS_ABS" ]]; then
    session_smoke_jobs
    mkdir -p "$OUT/smoke/sessions"
    say "---- 2b. the sessions' smoke: every session from the parents (W's at seed $W_SEED, the rest at seed $P0)," \
        "$SMOKE_WINDOWS windows each, all at once"
    gw_step smoke sessions "$OUT/smoke/sessions" "${#JOBS[@]}" "$SMOKE_WINDOWS"
    JOB_DIR="$OUT/smoke/sessions" CURVE_DIR="$OUT/smoke/sessions" run_fleet "${#JOBS[@]}"
    smoke_rc "$OUT/smoke/sessions"
    smoke_trip "$(smoke_read "$OUT/smoke/sessions" | tee -a "$S")"
    rm -rf "$OUT/smoke/ckpt"
  fi
  JOBS=()
  for s in $SJOB_SEEDS; do for a in $BASE_ARMS; do add_job "$(session_job "$a" "$s" "$SESSION_WINDOWS" "$OUT/ckpt")"; done; done
  add_job "$(session_job W "$W_SEED" "$SESSION_WINDOWS" "$OUT/ckpt")"
fi

# ---------------------------------------------------------------- 4. the fleet, with a sampler
FLEET_W=$WINDOWS; [[ "$EXP" == session ]] && FLEET_W=$SESSION_WINDOWS
say "---- 2. fleet started $(date -u +%H:%M:%SZ)"
gw_step fleet "" "$OUT/logs" "${#JOBS[@]}" "$FLEET_W"
gw_state par="$PAR" runs_total="${#JOBS[@]}" windows="$FLEET_W"
say "    ${#JOBS[@]} run(s), $PAR at a time; each spends ~${STARTUP_S:-15-30} s on the CPU before it trains. The fleet's" \
    "own line prints when its last run ends$HB_NOTE; $GW_WATCH shows every run."
smi_start
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
