cd "$(dirname "$0")"
run(){ OMP_NUM_THREADS=1 PYTHONHASHSEED=4242 python3 -W ignore td_stress.py "$@" > /dev/null 2>>td_err.log; }
(run --scen base --K 5 --seed 0; run --scen delim --K 5 --seed 0; run --scen imp --imp 0.3 --seed 0; run --scen base --K 8 --seed 0) &
(run --scen stale --K 5 --seed 0; run --scen base --K 3 --seed 0; run --scen imp --imp 0.5 --seed 0; run --scen delim --K 5 --seed 1) &
wait
