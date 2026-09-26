#!/bin/bash
export OMP_NUM_THREADS=1 PYTHONHASHSEED=5
cd $(dirname $0)/d3
for s in 0 1; do python3 -W ignore run_act.py --arm fulltd --act_every 6 --seed $s --tag _act6 > logs/fulltd_act6_s$s.stdout 2>&1; done
