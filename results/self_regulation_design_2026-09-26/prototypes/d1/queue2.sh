#!/bin/bash
# second batch: waits for queue1, then credibility audit + compute-matched baseline + no-floor ablation (<=2 at once)
cd "$(dirname "$0")"
export OMP_NUM_THREADS=1
until grep -q QUEUE_DONE logs/queue1.out; do sleep 5; done
timeout 600 python3 -W ignore cred_audit.py --seed 0 > logs/audit_s0.stdout 2>&1 &
timeout 600 python3 -W ignore run.py --arm base --seed 0 --bytes 4624000 --tag _cm > logs/base_cm_s0.stdout 2>&1 &
wait
timeout 600 python3 -W ignore run.py --arm base --seed 1 --bytes 4624000 --tag _cm > logs/base_cm_s1.stdout 2>&1 &
timeout 600 python3 -W ignore run.py --arm lp_nofloor --seed 0 > logs/lp_nofloor_s0.stdout 2>&1 &
wait
echo QUEUE2_DONE
