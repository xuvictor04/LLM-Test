#!/bin/bash
# usage: lane.sh LANENAME CMDFILE ; each line of CMDFILE: "name|dir|command"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
R=/tmp/claude-0/-home-user-LLM-Test/e880caf7-1208-58de-93fd-49c41549bf70/scratchpad/mm2/repro
while IFS='|' read -r name dir cmd; do
  [ -z "$name" ] && continue
  echo "start $name $(date +%T)" >> $R/logs/$1.log
  ( cd $R/$dir && eval "$cmd" > $R/logs/run_$name.txt 2>&1; echo "done $name rc=$? $(date +%T)" >> $R/logs/$1.log )
done < $2
echo LANEDONE >> $R/logs/$1.log
