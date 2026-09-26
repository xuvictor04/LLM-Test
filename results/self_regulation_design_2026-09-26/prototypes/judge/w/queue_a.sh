#!/bin/bash
export OMP_NUM_THREADS=1 PYTHONHASHSEED=12345
W=$(dirname $0)
(cd $W/d1 && python3 -W ignore run.py --arm full --seed 0 --tag _judge > logs/full_judge_s0.stdout 2>&1)
(cd $W/d1 && python3 -W ignore run.py --arm base --seed 0 --tag _judge > logs/base_judge_s0.stdout 2>&1)
