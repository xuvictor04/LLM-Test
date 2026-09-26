#!/bin/bash
# d3 grid part 3 (focus ablations, matched replay, seed 2), 2 at a time. Usage: bash queue3.sh
cd "$(dirname "$0")"
export OMP_NUM_THREADS=1
while pgrep -f "arm full --seed" > /dev/null; do sleep 5; done
L="rehearse 0|rehearse 1|focus_nomir 0|focus_nomir 1|replay_fixed 0 --replay 0.27 --tag _m27|replay_fixed 1 --replay 0.27 --tag _m27|base 2|focus 2"
echo "$L" | tr '|' '\n' | xargs -P 2 -L 1 bash -c 'timeout 600 python3 -W ignore run.py --arm $0 --seed $1 $2 $3 $4 $5 >> logs/queue.out 2>&1; echo "done $0 $1 $2 $3 $4 $5 rc=$?" >> logs/queue.out'
echo ALLDONE3 >> logs/queue.out
