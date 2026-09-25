#!/bin/bash
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
C=/tmp/claude-0/-home-user-LLM-Test/e880caf7-1208-58de-93fd-49c41549bf70/scratchpad/mm2/critic
for s in 0 1; do
(cd $C/d1r && python3 run_arm.py --arm live25 --seed $s --codec_every 1 --codec_per_flush 2 --out res/live25_every4w_s$s.json > $C/log_d1_live25_every4w_s$s.txt 2>&1; echo DONE >> $C/log_d1_live25_every4w_s$s.txt) &
done
wait
