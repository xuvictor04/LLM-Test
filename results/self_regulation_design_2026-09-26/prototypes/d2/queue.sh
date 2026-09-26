#!/bin/bash
# runs the d2 experiment grid, 2 at a time. Usage: bash queue.sh
cd "$(dirname "$0")"
export OMP_NUM_THREADS=1
jobs_list=()
for s in 0 1 2; do for a in base tags sel tags_sel loss sel_pos tags_nodrop; do
  [ -f out/${a}_s${s}.json ] || jobs_list+=("$a $s"); done; done
printf '%s\n' "${jobs_list[@]}" | xargs -P 2 -L 1 bash -c 'timeout 480 python run.py --arm $0 --seed $1 >> logs/queue.out 2>&1'
echo DONE >> logs/queue.out
