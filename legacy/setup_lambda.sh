#!/bin/bash
# setup_lambda.sh -- one-time setup on a fresh Lambda instance.
# Run from inside the unzipped overarching-package/ directory.
set -u
echo "=== Greg / Lambda setup ==="

# torch + CUDA: Lambda Stack usually ships it already. Only install if missing, and prefer the CUDA wheel
# (a plain 'pip install torch' can silently pull a CPU build and break the GPU run).
if python3 -c "import torch,sys; sys.exit(0 if torch.cuda.is_available() else 1)" 2>/dev/null; then
  echo "torch + CUDA already present."
else
  echo "installing CUDA torch (can take a minute)..."
  pip3 install torch numpy --index-url https://download.pytorch.org/whl/cu121 2>/dev/null \
    || pip3 install torch numpy --break-system-packages
fi
python3 -c "import numpy" 2>/dev/null || pip3 install numpy --break-system-packages 2>/dev/null || true

# ---- training corpus ----  DATASET=enwik8 (default, ~96MB) or enwik9 (~1GB, 10x more, breaks the plateau)
DATASET=${DATASET:-enwik8}
if [ ! -f "data/train/eng/${DATASET}.txt" ]; then
  echo
  echo "fetching ${DATASET} ..."
  mkdir -p data/train/eng
  if [ "$DATASET" = enwik9 ]; then
    urls="http://mattmahoney.net/dc/enwik9.zip https://cs.fit.edu/~mmahoney/compression/enwik9.zip"; member=enwik9; minsz=500000000
  else
    urls="http://mattmahoney.net/dc/enwik8.zip https://cs.fit.edu/~mmahoney/compression/enwik8.zip"; member=enwik8; minsz=50000000
  fi
  for url in $urls; do
    if wget -q --timeout=600 "$url" -O /tmp/e.zip && unzip -p /tmp/e.zip "$member" > "data/train/eng/${DATASET}.txt" 2>/dev/null; then break; fi
    echo "  (mirror failed, trying next)"
  done
  sz=$(stat -c%s "data/train/eng/${DATASET}.txt" 2>/dev/null || echo 0)
  if [ "$sz" -lt "$minsz" ]; then
    echo "  !! ${DATASET} fetch FAILED or truncated ($sz bytes). Corpus will be small -> overfit."
    rm -f "data/train/eng/${DATASET}.txt"
  else
    echo "  ${DATASET} OK ($((sz/1000000)) MB)"
  fi
  rm -f /tmp/e.zip
fi

# ---- extra public-domain books (best-effort; more prose diversity). Set EXTRA_BOOKS=0 to skip. ----
if [ "${EXTRA_BOOKS:-1}" = 1 ]; then
  echo "fetching extra public-domain books (best-effort)..."
  mkdir -p data/train/eng
  for id in 1342 84 2701 1661 98 1400 74 2600 1080 76 1232 205 2542 174 1260; do
    f="data/train/eng/gb_${id}.txt"; [ -f "$f" ] && continue
    for u in "https://www.gutenberg.org/files/${id}/${id}-0.txt" "https://www.gutenberg.org/cache/epub/${id}/pg${id}.txt"; do
      if wget -q --timeout=60 -U "Mozilla/5.0" "$u" -O "$f" && [ "$(stat -c%s "$f" 2>/dev/null || echo 0)" -gt 10000 ]; then break; fi
      rm -f "$f"
    done
  done
  echo "  books present: $(ls data/train/eng/gb_*.txt 2>/dev/null | wc -l)"
fi

# ---- diverse sources (web / code-per-language / reddit / your own JSON) -- set DIVERSE=1 to enable ----
if [ "${DIVERSE:-0}" = 1 ]; then
  echo
  echo "installing 'datasets' + fetching diverse sources (web, code, reddit)..."
  pip3 install -q datasets 2>/dev/null || pip3 install -q datasets --break-system-packages 2>/dev/null \
    || echo "  (could not install 'datasets' -- diverse fetch skipped, non-fatal)"
  # honors SOURCES / WEB_MB / CODE_MB / REDDIT_MB / JSON_DIR env; every source is best-effort
  python3 fetch_data.py || echo "  (diverse fetch had errors -- non-fatal; continuing with whatever landed)"
  echo "  domains now: $(ls -d data/train/*/ 2>/dev/null | xargs -n1 basename 2>/dev/null | tr '\n' ' ')"
fi

python3 - <<'PY'
import torch
print("torch", torch.__version__, "| CUDA available:", torch.cuda.is_available())
if torch.cuda.is_available():
    p = torch.cuda.get_device_properties(0)
    print(f"GPU: {p.name} | {p.total_memory/1e9:.0f} GB")
else:
    print("WARNING: no CUDA GPU visible -- the run will refuse to start.")
PY

# Lambda Guest Agent -- streams GPU/VRAM metrics to the Cloud console dashboard
# (GUI monitoring, complements `tail -f ~/lambda.log`). Non-fatal: a failure here never blocks the run.
echo
echo "installing Lambda Guest Agent (console GPU/VRAM monitoring)..."
curl -L https://lambdalabs-guest-agent.s3.us-west-2.amazonaws.com/scripts/install.sh | sudo bash \
  || echo "  (guest agent skipped/failed -- console metrics unavailable; the run is unaffected)"
sudo systemctl --no-pager status lambda-guest-agent* 2>/dev/null | head -5 || true

chmod +x run_lambda.sh 2>/dev/null || true
echo
echo "READY.  Start the run with:"
echo "    tmux new -s greg"
echo "    bash run_lambda.sh          # then Ctrl+b, d to detach;  tail -f ~/lambda.log"
