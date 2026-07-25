#!/bin/bash
# ============ FETCH THE MULTI-EPOCH CORPUS (default 40 GB) ============
# 40 GB of streamed text is a multi-HOUR download, so this is built to survive: it runs detached, checkpoints its
# position after every shard, and can be re-run to continue rather than start over.
#
#   bash fetch_40g.sh                 # start (or continue) a 40 GB pull, detached
#   bash fetch_40g.sh status          # how far along
#   bash fetch_40g.sh stop            # stop; re-run to resume from the same point
#   GB=60 OUT=data_big bash fetch_40g.sh
#
# WHY 40 GB: GPT-2-small saw ~40 GB of text. At the measured 3.99 GB/day (A100) / ~9.8 projected (GH200), that is
# the corpus a multi-epoch run needs before EPOCHS starts recycling material it has already seen.
#
# WHY A THROWAWAY VENV: `datasets` pulls numpy/pyarrow/pandas. On aarch64 that can upgrade numpy underneath the
# torch you train with and trigger an ABI clash -- for a package the training path never imports. So the fetcher
# gets its own interpreter and cannot touch the training environment.
set -u

GB=${GB:-40}
OUT=${OUT:-data_big}
DATASET=${DATASET:-fineweb-edu}
DOMAIN=${DOMAIN:-eng}
VENV=${VENV:-$HOME/fetchenv}
LOG=${LOG:-$PWD/fetch_40g.log}
PIDF=$PWD/.fetch_40g.pid
DEST="$OUT/train/$DOMAIN"

status() {
  echo "=== fetch status ==="
  if [ -f "$PIDF" ] && kill -0 "$(cat "$PIDF")" 2>/dev/null; then
    echo "  RUNNING (pid $(cat "$PIDF"))"
  else
    echo "  not running"
  fi
  if [ -d "$DEST" ]; then
    local have; have=$(du -sb "$DEST" 2>/dev/null | cut -f1)
    echo "  on disk : $(numfmt --to=iec "${have:-0}" 2>/dev/null || echo "${have:-0} B")  in $(ls "$DEST"/part*.txt 2>/dev/null | wc -l) shard(s)"
    echo "  target  : ${GB} GB"
    [ -f "$DEST/_fetch_manifest.json" ] && echo "  manifest: $(cat "$DEST/_fetch_manifest.json")"
    awk -v h="${have:-0}" -v g="$GB" 'BEGIN{printf "  progress: %.1f%%\n", (h/(g*1e9))*100}'
  else
    echo "  nothing fetched yet"
  fi
  [ -f "$LOG" ] && { echo "  --- last 3 log lines ---"; tail -3 "$LOG" | sed 's/^/  /'; }
}

case "${1:-run}" in
  status) status; exit 0 ;;
  stop)
    if [ -f "$PIDF" ] && kill -0 "$(cat "$PIDF")" 2>/dev/null; then
      kill "$(cat "$PIDF")"; echo "stopped $(cat "$PIDF") -- re-run 'bash fetch_40g.sh' to resume from the manifest"
    else echo "not running"; fi
    rm -f "$PIDF"; exit 0 ;;
esac

# ---------- guard: already running ----------
if [ -f "$PIDF" ] && kill -0 "$(cat "$PIDF")" 2>/dev/null; then
  echo "!! already running (pid $(cat "$PIDF")). 'bash fetch_40g.sh status' or 'stop'."; exit 1
fi

# ---------- guard: disk ----------
NEED=$(( GB + GB / 5 + 5 ))                       # target + 20% slack + 5 GB headroom
AVAIL=$(df -Pk . | awk 'NR==2{printf "%d", $4/1024/1024}')
echo "disk: ${AVAIL} GB free, need ~${NEED} GB for a ${GB} GB pull"
[ "$AVAIL" -lt "$NEED" ] && { echo "!! not enough free disk"; exit 1; }

# ---------- venv ----------
if [ ! -x "$VENV/bin/python" ]; then
  echo "creating throwaway fetch venv at $VENV (keeps datasets/numpy away from your torch)"
  python3 -m venv "$VENV" || { echo "!! venv creation failed (need python3-venv)"; exit 1; }
  "$VENV/bin/pip" install -q --upgrade pip
  "$VENV/bin/pip" install -q datasets || { echo "!! pip install datasets failed"; exit 1; }
fi
echo "fetcher: $("$VENV/bin/python" -c 'import datasets,sys;print("datasets",datasets.__version__,"| python",sys.version.split()[0])')"

# ---------- go ----------
RESUME=""
[ -f "$DEST/_fetch_manifest.json" ] && { RESUME="--resume"; echo "resuming from manifest"; }

echo "starting: $DATASET -> $DEST, target ${GB} GB (detached; log: $LOG)"
nohup "$VENV/bin/python" fetch_big.py --dataset "$DATASET" --gb "$GB" --out "$OUT" --domain "$DOMAIN" \
      --shard-mb 512 $RESUME >> "$LOG" 2>&1 &
echo $! > "$PIDF"
sleep 3
if kill -0 "$(cat "$PIDF")" 2>/dev/null; then
  echo "  started (pid $(cat "$PIDF"))"
  echo "  watch:  bash fetch_40g.sh status     |     tail -f $LOG"
  echo "  NOTE: this is a multi-hour download. It survives logout (nohup) and can be stopped and resumed."
else
  echo "!! died immediately -- last log lines:"; tail -20 "$LOG"; rm -f "$PIDF"; exit 1
fi
