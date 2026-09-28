#!/usr/bin/env bash
# Fetch a much LARGER open-source corpus (~35-45 MB vs the bundled 5.7 MB).
# Run this once on the GPU box, then point the system at it:
#     bash fetch_data.sh                 # -> writes data_big/train/{eng,py,num,c}/
#     DATA_DIR=data_big bash run_full_unfrozen.sh
#
# Sources (all open / public domain):
#   eng : NLTK Gutenberg (Austen, Melville, Milton, Shakespeare, KJV, ...) + Brown + Reuters + abc + state_union
#   py  : CPython's own Lib/*.py
#   c   : CPython's Objects/*.c + Python/*.c
#   num : synthesised numeric tables (kept, so the 4th domain stays clearly distinct)
set -e
OUT=${OUT:-data_big}; TMP=$(mktemp -d)
mkdir -p "$OUT"/train/{eng,py,num,c}
NLTK=https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/packages/corpora

echo "[1/4] English -- Gutenberg + Brown + Reuters + movie_reviews + nps_chat + inaugural + treebank"
: > "$OUT/train/eng/eng.txt"
# NB: NO --size filter. Reuters/movie_reviews documents are SMALL; a `-size +1k` filter silently discarded ~9MB of
# Reuters on the first version of this script. Only READMEs/metadata are excluded.
for c in gutenberg brown reuters movie_reviews nps_chat inaugural treebank; do
  curl -sL --max-time 600 -o "$TMP/$c.zip" "$NLTK/$c.zip" || { echo "  skip $c (download)"; continue; }
  ( cd "$TMP" && unzip -qo "$c.zip" >/dev/null 2>&1 ) || { echo "  skip $c (unzip)"; continue; }
  find "$TMP/$c" -type f ! -name 'README*' ! -name 'CONTENTS*' ! -name 'cats.txt' \
       ! -name 'stopwords' ! -name '*.xml' ! -name '*.json' -size +100c -exec cat {} + 2>/dev/null \
    | sed -E 's#/[A-Za-z$][A-Za-z$*+-]*##g; s#\[[^]]*\]##g' >> "$OUT/train/eng/eng.txt" || true  # strip POS tags: Brown uses LOWERCASE tags (the/at movie/nn) -> [A-Z] alone leaked them; digits/dots excluded so 12/25 & URLs survive
  printf "  %-14s -> eng.txt %9d bytes\n" "$c" "$(wc -c < "$OUT/train/eng/eng.txt")"
done

# BIG=1 -> add large GitHub-hosted corpora (hundreds of MB). These are what make GPT-2-scale training possible;
# the NLTK set above is only ~45MB. Both are Project Gutenberg derived and open.
if [ "${BIG:-0}" = "1" ]; then
  echo "[1b/4] LARGE corpora (this takes a while)..."
  for R in "Zeta-and-Company/Gutenberg_subset:master" "tnhaider/english-gutenberg-poetry:master"; do
    repo=${R%%:*}; br=${R##*:}; tag=$(basename "$repo")
    echo "  fetching $repo ..."
    curl -sL --max-time 3600 -o "$TMP/$tag.tgz" "https://codeload.github.com/$repo/tar.gz/refs/heads/$br" || continue
    tar -xzf "$TMP/$tag.tgz" -C "$TMP" 2>/dev/null || continue
    # .txt directly; .xml/.html stripped of tags
    find "$TMP" -path "*$tag*" -name '*.txt' -exec cat {} + 2>/dev/null >> "$OUT/train/eng/eng.txt" || true
    find "$TMP" -path "*$tag*" \( -name '*.xml' -o -name '*.html' \) -exec cat {} + 2>/dev/null \
      | sed -E 's#<[^>]*>##g' >> "$OUT/train/eng/eng.txt" || true
    printf "  %-32s -> eng.txt %9d bytes\n" "$tag" "$(wc -c < "$OUT/train/eng/eng.txt")"
    rm -rf "$TMP/$tag.tgz"
  done
fi

echo "[2/4] Python + C (CPython source)..."
curl -sL --max-time 600 -o "$TMP/cp.tgz" https://codeload.github.com/python/cpython/tar.gz/refs/tags/v3.11.0
tar -xzf "$TMP/cp.tgz" -C "$TMP"
CP=$(find "$TMP" -maxdepth 1 -type d -name 'cpython-*' | head -1)
find "$CP/Lib" -name '*.py' -size -200k | head -1200 | xargs cat > "$OUT/train/py/py.txt" 2>/dev/null || true
{ find "$CP/Objects" -name '*.c'; find "$CP/Python" -name '*.c'; find "$CP/Modules" -name '*.c'; } \
  | head -500 | xargs cat > "$OUT/train/c/c.txt" 2>/dev/null || true

echo "[3/4] Numeric tables..."
python3 - "$OUT/train/num/num.txt" <<'PY'
import random, sys
random.seed(0)
with open(sys.argv[1], "w") as f:
    for _ in range(150000):
        f.write(",".join(f"{random.uniform(0, 10000):.2f}" for _ in range(random.randint(3, 8))) + "\n")
PY

echo "[4/4] Result:"
tot=0
for d in eng py num c; do
  b=$(cat "$OUT"/train/$d/* 2>/dev/null | wc -c); tot=$((tot+b))
  printf "  %-4s %12d bytes (%.1f MB)\n" "$d" "$b" "$(echo "$b/1000000" | bc -l)"
done
printf "  %-4s %12d bytes (%.1f MB total)\n" "ALL" "$tot" "$(echo "$tot/1000000" | bc -l)"
rm -rf "$TMP"
echo
echo "Now run with:"
echo "  DATA_DIR=$OUT CORPUS_CAP=100000000 STREAM_LEN=80000000 WIN=256 BATCH_W=16 ACCUM=4 bash run_full_unfrozen.sh"
echo
echo "For a MUCH larger corpus (hundreds of MB, needed for GPT-2-scale training):  BIG=1 bash fetch_data.sh"
