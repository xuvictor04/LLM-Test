#!/bin/bash
# usage: runjob.sh DIR SCRIPT SEED ARGS...
export OMP_NUM_THREADS=1 PYTHONHASHSEED=2718
R=$(cd $(dirname $0); pwd)
D=$1; S=$2; SEED=$3; shift 3
cd $R/$D
t0=$(date +%s)
python3 -W ignore $S "$@" --seed $SEED > logs/job_$(echo "$S $* $SEED" | tr ' .-' '___').stdout 2>&1
echo "$(date +%T) done rc=$? $((`date +%s`-t0))s $D $S $* seed=$SEED" >> $R/progress.log
