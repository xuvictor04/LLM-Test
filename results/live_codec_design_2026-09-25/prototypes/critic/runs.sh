#!/bin/bash
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
C=/tmp/claude-0/-home-user-LLM-Test/e880caf7-1208-58de-93fd-49c41549bf70/scratchpad/mm2/critic
(cd $C/d3r && python3 run.py frozen25c 1 res/frozen25c_s1.json > $C/log_d3_frozen25c_s1.txt 2>&1; echo DONE_d3 >> $C/log_d3_frozen25c_s1.txt) &
(cd $C/d1r && python3 run_arm.py --arm frozen25 --seed 1 --media_rows lattice --out res/frozen25lat_s1.json > $C/log_d1_frozen25lat_s1.txt 2>&1; echo DONE_d1 >> $C/log_d1_frozen25lat_s1.txt) &
wait
