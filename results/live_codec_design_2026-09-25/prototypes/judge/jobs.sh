#!/bin/bash
# Judge reruns. Max 3 concurrent processes, one thread each.
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
J=/tmp/claude-0/-home-user-LLM-Test/e880caf7-1208-58de-93fd-49c41549bf70/scratchpad/mm2/judge
run() { name=$1; dir=$2; shift 2; echo "start $name $(date +%T)" >> $J/jobs.log; ( cd $dir && "$@" > $J/logs_$name.txt 2>&1; echo "done $name rc=$? $(date +%T)" >> $J/jobs.log ) & }
waitmax() { while [ "$(jobs -rp | wc -l)" -ge 3 ]; do sleep 5; done; }
mkdir -p $J
waitmax; run d1_resume $J/d1c python3 run_arm.py --arm live50bpe --seed 0 --n_a 150 --n_b 150 --act_every 48 --bpe_min_pair 5 --bpe_burst 16 --resume_test 10 --out smoke/resume_save10.json
waitmax; run d3_flipdist $J/d3c python3 flipdist.py 0 500 res/flipdist_s0.json
waitmax; run d1_live25_s0 $J/d1c python3 run_arm.py --arm live25 --seed 0 --out res/live25_s0.json
waitmax; run d1_frozen25lat_s0 $J/d1c python3 run_arm.py --arm frozen25 --seed 0 --media_rows lattice --out res/frozen25lat_s0.json
waitmax; run d2_dbggrad $J/d2c python3 dbg_grad.py
waitmax; run d1_live25lat_s0 $J/d1c python3 run_arm.py --arm live25 --seed 0 --media_rows lattice --out res/live25lat_s0.json
waitmax; run d3_ttc25c_s0 $J/d3c python3 run.py ttc25c 0 res/ttc25c_s0.json
waitmax; run d1_frozen25lat_s1 $J/d1c python3 run_arm.py --arm frozen25 --seed 1 --media_rows lattice --out res/frozen25lat_s1.json
waitmax; run d1_live25lat_s1 $J/d1c python3 run_arm.py --arm live25 --seed 1 --media_rows lattice --out res/live25lat_s1.json
wait
echo ALLDONE >> $J/jobs.log
