#!/bin/bash
export OMP_NUM_THREADS=1 PYTHONHASHSEED=77
W=$(dirname $0)
while pgrep -f queue_b.sh >/dev/null; do sleep 5; done
cd $W/d3
python3 -W ignore run.py --arm fulltd --seed 0 --bytes 150000 --tag _chk_orig > logs/chk_orig.stdout 2>&1
python3 -W ignore run_tags.py --arm fulltd --tags 0 --seed 0 --bytes 150000 --tag _chk_graft0 > logs/chk_graft0.stdout 2>&1
python3 -W ignore run.py --arm fulltd --seed 2 > logs/fulltd_s2.stdout 2>&1
python3 -W ignore run.py --arm replay_fixed --replay 0.27 --tag _m27 --seed 2 > logs/m27_s2.stdout 2>&1
python3 -W ignore run.py --arm focus --seed 2 > logs/focus_s2.stdout 2>&1
