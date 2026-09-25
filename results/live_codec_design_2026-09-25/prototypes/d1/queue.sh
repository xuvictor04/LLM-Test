#!/bin/bash
# usage: queue.sh MAXPAR "arm seed [extra args]" ...
cd "$(dirname "$0")"; export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
MAX=$1; shift
for job in "$@"; do
  while [ "$(jobs -rp | wc -l)" -ge "$MAX" ]; do sleep 5; done
  set -- $job; arm=$1; seed=$2; shift 2; tag=${TAG:-}
  echo "start $arm s$seed $* $(date +%T)"
  ( python3 run_arm.py --arm $arm --seed $seed "$@" --out res/${arm}${tag}_s${seed}.json > logs/${arm}${tag}_s${seed}.log 2>&1; echo "done $arm s$seed rc=$? $(date +%T)" ) &
done
wait
echo ALLDONE
