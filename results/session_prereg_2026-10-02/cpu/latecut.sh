#!/bin/bash
# F'S START AT THE SESSION'S OWN FIRST CUT (2026-10-02, the review of register §8 5.3a; operation only, CPU).
#     bash latecut.sh BEFORE AFTER WORK
# BEFORE and AFTER are checkouts at b2dba7c (F against the start read at the parent's last cut) and at the commit
# after it (the start read again at the session's own first cut, 'resume_own'); WORK a scratch directory. A parent at
# EXP=heldout's pins, TOK_RETOK_EVERY=100 and TOK_GROW_EVERY=20 (the review's k100: its last act at window 201, its
# mints to 289 after it), then one P session from it in each tree, at OPT_LR 1e-12 (it learns nothing) and at the
# shipped rate, one window each, as EXP=session's job line orders its levers. Printed per session: training byte
# for byte (curve, flush bytes), the 'resume' rows and every later row but R's pairing equal across the trees; F per
# old area (memory-off, report half) against each start, and what the parent's late ids moved.
set -u
B=$(cd "$1" && pwd) && A=$(cd "$2" && pwd) && mkdir -p "$3" && W=$(cd "$3" && pwd) || exit 2
PINS="DATA_DRAW=planned DATA_SYNTH_HOLDOUT=1 EVAL_RETENTION_EVERY=50 EVAL_HOLDOUT_WINDOWS=256 EVAL_RETENTION_N=24 EVAL_GENERATE=0 TOK_MINT_NOVEL=0"
SESS="RUN_EPOCHS=2 DATA_RESAMPLE=1 DATA_AREAS=eng,py,num,c,x5 DATA_N_PROCESSES=5 DATA_STREAM_BYTES=70875 DATA_PHASE_SCHED=x5|x5|x5|x5 OPT_LR_CONTINUE=as_logged"
run() {  # tree tag windows env...
  local t=$1 tag=$2 n=$3; shift 3
  env OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 RUN_DEVICE=cpu RUN_SEED=1 DATA_STREAM_BYTES=56700 TOK_GROW_EVERY=20 \
      FAB_SLOTS=2200 $PINS TOK_RETOK_EVERY=100 "$@" python3 "$t/run.py" --max-windows "$n" --loss-curve "$W/$tag.json" \
      --flush-bytes "$W/$tag.bytes.json" --probe-series "$W/$tag.probe.json" > "$W/$tag.log" 2>&1
  echo "$tag rc=$?" >> "$W/rc.txt"
}
: > "$W/rc.txt"
run "$B" k100.s1 300 CKPT_DIR="$W/ckpt/k100.s1" CKPT_EVERY=0
for x in "b_lr0 $B OPT_LR=1e-12" "a_lr0 $A OPT_LR=1e-12" "b_rate $B" "a_rate $A"; do
  set -- $x; run "$2" "$1" 1 $SESS DATA_DRAW=planned CKPT_RESUME="$W/ckpt/k100.s1" ${3:-} &
done
wait
cat "$W/rc.txt"
grep -h "minted AFTER THE LAST" "$W/k100.s1.log" | cut -c1-110
python3 - "$W" <<'PY'
import json, os, sys
w = sys.argv[1]
rd = lambda p: open(os.path.join(w, p)).read()
rows = lambda t: [x for x in json.load(open(os.path.join(w, t + ".probe.json"))) if isinstance(x, dict)]
strip = lambda r: {k: v for k, v in r.items() if k not in ("paired", "paired_sd")}
for b, a in (("b_lr0", "a_lr0"), ("b_rate", "a_rate")):
    rb, ra = rows(b), rows(a)
    last = lambda rs, k: [x for x in rs if x["kind"] == k and x["closure"] == "memory-off"][-1]
    res, own, R = last(ra, "resume"), last(ra, "resume_own"), last(ra, "boundary")
    ar = list(res["areas"])
    print(f"{a} (against {b}): training byte for byte {rd(b + '.json') == rd(a + '.json') and rd(b + '.bytes.json') == rd(a + '.bytes.json')}; "
          f"'resume' rows equal {[x for x in rb if x['kind'] == 'resume'] == [x for x in ra if x['kind'] == 'resume']}; "
          f"every later row equal but R's pairing "
          f"{[strip(x) for x in rb if x['kind'] != 'resume'] == [strip(x) for x in ra if x['kind'] not in ('resume', 'resume_own')]}; "
          f"rows {[x['kind'] for x in ra if x['closure'] == 'memory-off']}")
    for name, st in (("F against 'resume' (b2dba7c's)", res), ("F against 'resume_own' (now)", own)):
        print(f"  {name:31s} " + " ".join(f"{k} {R['areas'][k]['report'] - st['areas'][k]['report']:+.4f}" for k in ar))
    print(f"  {'resume_own - resume':31s} " + " ".join(
        f"{k} {own['areas'][k]['report'] - res['areas'][k]['report']:+.4f}" for k in ar)
        + f" (its pairing's report half, py: n {own['paired']['py']['report'][0]}, SD {own['paired']['py']['report'][2]:.4f})")
PY
