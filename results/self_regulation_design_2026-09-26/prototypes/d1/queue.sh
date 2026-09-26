#!/bin/bash
# usage: bash queue.sh "arm:seed:extra args" ...   (runs at most 2 at once, skips finished outputs)
cd "$(dirname "$0")"
export OMP_NUM_THREADS=1
run() {
  IFS=: read -r arm seed extra <<< "$1"
  [ -f "out/${arm}_s${seed}.json" ] && return
  timeout 600 python3 -W ignore run.py --arm "$arm" --seed "$seed" $extra > "logs/${arm}_s${seed}.stdout" 2>&1
}
for job in "$@"; do
  while [ "$(jobs -rp | wc -l)" -ge 2 ]; do sleep 2; done
  run "$job" &
done
wait
echo QUEUE_DONE
