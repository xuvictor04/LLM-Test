#!/bin/bash
# d3 grid part 2 (after the conf fix), 2 at a time. Usage: bash queue2.sh
cd "$(dirname "$0")"
export OMP_NUM_THREADS=1
while pgrep -f "arm replay_fixed --seed" > /dev/null; do sleep 5; done
L="full 0|full 1|trust 0|trust 1|focus_nomir 0|focus_nomir 1|replay_fixed 0 --replay 0.27 --tag _m27|replay_fixed 1 --replay 0.27 --tag _m27|base 2|full 2|rehearse 0|mf_base 0|mf_trust 0"
echo "$L" | tr '|' '\n' | xargs -P 2 -L 1 bash -c 'timeout 600 python3 -W ignore run.py --arm $0 --seed $1 $2 $3 $4 $5 >> logs/queue.out 2>&1; echo "done $0 $1 $2 $3 $4 $5 rc=$?" >> logs/queue.out'
echo ALLDONE >> logs/queue.out
