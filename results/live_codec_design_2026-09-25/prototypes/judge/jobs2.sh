#!/bin/bash
# Judge queue 2: sequential, one thread.
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
J=/tmp/claude-0/-home-user-LLM-Test/e880caf7-1208-58de-93fd-49c41549bf70/scratchpad/mm2/judge
r() { name=$1; dir=$2; shift 2; echo "start $name $(date +%T)" >> $J/jobs2.log; ( cd $dir && "$@" > $J/logs2_$name.txt 2>&1; echo "done $name rc=$? $(date +%T)" >> $J/jobs2.log ); }
r d2_dbggrad_w1 $J/d2c env D2_GMM_W=1.0 D2_LOGSIG_MIN=-5 python3 dbg_grad.py
r d1_live25hot_s0 $J/d1c python3 run_arm.py --arm live25 --seed 0 --codec_lr 3e-4 --codec_every 1 --anchor_w 0 --out res/live25hot_s0.json
r d3_ttc25c_cold_s0 $J/d3c python3 run.py ttc25c 0 res/ttc25c_cold_s0.json --codec_lr 5e-5 --every 8
echo ALLDONE >> $J/jobs2.log
