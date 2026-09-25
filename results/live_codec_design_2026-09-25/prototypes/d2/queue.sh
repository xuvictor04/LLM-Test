#!/bin/bash
# launch queued runs whenever fewer than 3 d2run.py processes are alive
cd "$(dirname "$0")"
Q=("d2_nolm 0 d2_nolm_s0" "d2_tgtgrad 0 d2_tgtgrad_s0" "d2_fixed 0 d2_fixed_s0" "d2 0 d2n4_s0 NRATIO=4")
for item in "${Q[@]}"; do
  set -- $item
  while [ "$(pgrep -fc 'python3 d2run.py')" -ge 3 ]; do sleep 5; done
  if [ -n "$4" ]; then export D2_$4; fi
  OMP_NUM_THREADS=1 nohup python3 d2run.py $1 $2 res/$3.json > logs/$3.log 2>&1 &
  unset D2_NRATIO
  echo "launched $3 $(date +%T)"
  sleep 20
done
