#!/bin/bash
# EXP=heldout UNCHANGED BY THIS BUILD (operation only): test 4 runs at cce2d39, and its top-up pools only with
# that commit's fleet, so the code shared with EXP=session must leave its fleet's output as it was.
#     bash heldout_identity.sh BEFORE AFTER CLONE
# BEFORE and AFTER are one tiny CPU fleet's OUT, run in CLONE (a clone of the checkout, at one path) at
# cce2d39 and then at 80135f1, the last commit of this build to change code:
#     EXP=heldout DEVICE=cpu WINDOWS=150 SEEDS=0 PAR=4 FILL=0 PIN_RETOK=40 PROBE_EVERY=50 \
#         EXTRA='TOK_GROW_EVERY=20' HB_EVERY=0 bash gpu_world.sh
# (1) every curve, flush-bytes and probe-series file, the smoke's too, and the finals' sha256 are compared
# byte for byte; (2) the blocks, with the lines that carry the commit, the launch time and measured seconds
# set aside; (3) one fleet read by both commits' --analyze, on one copy at one path (its checkpoints linked,
# read only): every file the analysis writes.
set -u
BEFORE=$(cd "$1" && pwd) && AFTER=$(cd "$2" && pwd) && CLONE=$(cd "$3" && pwd) || exit 2
n=0; bad=0
for f in $(cd "$BEFORE" && find curves smoke -type f -name '*.json' | sort); do
  n=$((n + 1)); cmp -s "$BEFORE/$f" "$AFTER/$f" || { bad=$((bad + 1)); echo "  DIFFERS $f"; }
done
[[ "$(cd "$BEFORE" && find curves smoke -type f -name '*.json' | sort)" == \
   "$(cd "$AFTER" && find curves smoke -type f -name '*.json' | sort)" ]] || { bad=$((bad + 1)); echo "  file lists differ"; }
echo "(1) $n curve, flush-bytes and probe-series files: $((n - bad)) byte-identical"
cmp -s "$BEFORE/FINALS.sha256" "$AFTER/FINALS.sha256" && echo "    FINALS.sha256 identical: $(grep -c . "$BEFORE/FINALS.sha256") final checkpoint and vocabulary files byte for byte" \
  || echo "    FINALS.sha256 DIFFERS"
TIMED="the probe's seconds|data\.trust\.wall_s|windows/s per run|this fleet: |^gpu_world\.sh EXP=heldout  commit "
for f in ANALYSIS.txt PASTE_BACK.txt; do
  d=$(diff <(grep -Ev "$TIMED" "$BEFORE/$f") <(grep -Ev "$TIMED" "$AFTER/$f") | grep -c '^[<>]')
  echo "(2) $f: $(grep -Ec "$TIMED" "$BEFORE/$f") line(s) carry the commit, the launch or measured seconds; every other line identical ($d differing)"
done
T=$(mktemp -d) && mkdir -p "$T/gpu_heldout_out" "$T/res" || exit 2
for v in cce2d39 80135f1; do
  rm -rf "$T/gpu_heldout_out" "$T"/*.tgz; mkdir "$T/gpu_heldout_out"
  (cd "$BEFORE" && tar -cf - --exclude=./ckpt --exclude=./code .) | (cd "$T/gpu_heldout_out" && tar -xf -)
  ln -s "$BEFORE/ckpt" "$T/gpu_heldout_out/ckpt"
  git -C "$CLONE" checkout -q "$v" || exit 2
  env -i PATH="$PATH" HOME="$HOME" LANG=C.UTF-8 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 EXP=heldout \
      OUT="$T/gpu_heldout_out" bash "$CLONE/gpu_world.sh" --analyze > "$T/res/$v.stdout" 2>&1
  for f in ANALYSIS.txt PASTE_BACK.txt FINALS.sha256; do cp "$T/gpu_heldout_out/$f" "$T/res/$v.$f"; done
done
for f in ANALYSIS.txt PASTE_BACK.txt FINALS.sha256 stdout; do
  cmp -s "$T/res/cce2d39.$f" "$T/res/80135f1.$f" && echo "(3) --analyze, $f: identical at cce2d39 and 80135f1" \
    || echo "(3) --analyze, $f: DIFFERS"
done
rm -rf "$T"
