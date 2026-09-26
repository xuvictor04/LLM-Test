#!/bin/bash
# d3 grid, 2 at a time. Usage: bash queue.sh
cd "$(dirname "$0")"
export OMP_NUM_THREADS=1
L="base 0|base 1|full 0|full 1|replay_fixed 0|replay_fixed 1|focus 0|focus 1|trust 0|trust 1|focus_nomir 0|focus_nomir 1|base 2|full 2|replay_fixed 2|rehearse 0|rehearse 1|mf_base 0|mf_trust 0"
echo "$L" | tr '|' '\n' | while read a s; do [ -f out/${a}_s${s}.json ] || echo "$a $s"; done | \
  xargs -P 2 -L 1 bash -c 'timeout 600 python3 -W ignore run.py --arm $0 --seed $1 >> logs/queue.out 2>&1; echo "done $0 $1 rc=$?" >> logs/queue.out'
echo ALLDONE >> logs/queue.out
