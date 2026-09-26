#!/bin/bash
export OMP_NUM_THREADS=1 PYTHONHASHSEED=5
W=$(dirname $0); Q=$1; S=$2
while pgrep -f $Q >/dev/null; do sleep 5; done
cd $W/d3; python3 -W ignore run_act.py --arm fulltd --act_every 6 --seed $S --tag _act6 > logs/fulltd_act6_s$S.stdout 2>&1
