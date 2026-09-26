#!/bin/bash
export OMP_NUM_THREADS=1 PYTHONHASHSEED=999
W=$(dirname $0)
(cd $W/d3 && python3 -W ignore run.py --arm fulltd --seed 0 --tag _judge > logs/fulltd_judge_s0.stdout 2>&1)
(cd $W/d2 && python3 -W ignore run.py --arm tags --seed 0 --tag _judge > logs/tags_judge_s0.stdout 2>&1)
