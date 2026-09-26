#!/bin/bash
export OMP_NUM_THREADS=1 PYTHONHASHSEED=4242
W=$(dirname $0)
while pgrep -f queue_a.sh >/dev/null; do sleep 5; done
cd $W/d3
for s in 0 1 2; do python3 -W ignore run_tags.py --arm fulltd --tags 1 --seed $s --tag _tags > logs/fulltd_tags_s$s.stdout 2>&1; done
