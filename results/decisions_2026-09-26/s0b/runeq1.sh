#!/bin/bash
cd /tmp/claude-0/-home-user-LLM-Test/e880caf7-1208-58de-93fd-49c41549bf70/scratchpad/s0b
run() { OMP_NUM_THREADS=1 python3 preq_eq.py RUN_SEED=$1 TOK_RETOK_EVERY=$2 DATA_STREAM_BYTES=760000 > eq/s$1_k$2.json 2> eq/s$1_k$2.err; }
run 1 0 & run 1 1000 & wait
echo ALLDONE > eq/done.txt
