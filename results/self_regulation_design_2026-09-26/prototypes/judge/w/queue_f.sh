#!/bin/bash
export OMP_NUM_THREADS=1 PYTHONHASHSEED=31
W=$(dirname $0)
while pgrep -f "run_act.py --arm fulltd --act_every 6 --seed 0" >/dev/null; do sleep 5; done
cd $W/d3; python3 -W ignore run.py --arm focus --seed 0 --tag _judge > logs/focus_judge_s0.stdout 2>&1
