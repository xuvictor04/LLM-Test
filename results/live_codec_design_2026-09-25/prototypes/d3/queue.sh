#!/bin/bash
# usage: ./queue.sh ARM SEED [ARM SEED ...]  -- runs the pairs sequentially, logging to logs/
cd "$(dirname "$0")"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
while [ $# -ge 2 ]; do
  arm=$1; seed=$2; shift 2
  echo "start $arm s$seed $(date +%T)" >> logs/queue.log
  python3 run.py $arm $seed res/${arm}_s${seed}.json > logs/${arm}_s${seed}.log 2>&1
  echo "done $arm s$seed rc=$? $(date +%T)" >> logs/queue.log
done
