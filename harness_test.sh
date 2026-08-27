#!/usr/bin/env bash
# === DOES THE HARNESS DESCRIBE THE RUN IT ACTUALLY LAUNCHED? =====================================================
#
# longrun.sh is 1,500 lines and nothing has ever tested a line of it. That is the wrong way round: a bug in
# self_organize.py produces a bad number, which the instruments are built to catch, while a bug in the harness
# files a good number against the WRONG DESCRIPTION -- and nothing catches that, ever, because the log looks
# fine and the arm name at the top of it is a string the harness chose.
#
# It has happened. From longrun.sh's own comments and from this session:
#
#   - _flags_for lived inside the `grid)` case branch, so `smoke` calling it ran SEVEN ARMS WITH NO FLAGS and
#     reported seven identical runs as seven passing arms.
#   - an unknown arm name returned "" and therefore ran the DEFAULT configuration under the misspelled arm's
#     log name -- a result filed against an experiment that never happened.
#   - arm flags were placed FIRST in the env line, so every knob hardcoded after them silently discarded the
#     arm's value: `grid 3 VMAX=512` ran at 2048 and labelled the log 512.
#   - twice this session an arm was defined in the ARMS preset case instead of _flags_for, and resolved to
#     nothing.
#   - `pilot` never passed TOKENIZER_PATH, so the vocabulary went to a shared default while pilot-add looked
#     beside the checkpoint -- the continual-learning demo could not run at all.
#
# Every one of those is a pure-shell property that a test can hold. This file sources the functions out of
# longrun.sh WITHOUT executing the script body, so it costs nothing and cannot start a run.
#
#   bash harness_test.sh
set -u
FAIL=0
ok()   { echo "  ok    $1"; }
bad()  { echo "  FAIL  $1"; FAIL=1; }
ck()   { if [ "$1" = 0 ]; then ok "$2"; else bad "$2"; fi; }

HERE="$(cd "$(dirname "$0")" && pwd)"
LR="$HERE/longrun.sh"
[ -f "$LR" ] || { echo "!! no longrun.sh beside this test"; exit 1; }

# SOURCE THE FUNCTIONS, NOT THE SCRIPT. longrun.sh dispatches on $1 at the bottom; sourcing it whole would run
# something. Slicing out the function definitions keeps this test free of side effects -- which is the only way
# a harness test is safe to run as often as it should be.
eval "$(sed -n '/^_reserve()/,/^}/p'   "$LR")"
eval "$(sed -n '/^_flags_for()/,/^}/p' "$LR")"

echo "harness_test: longrun.sh arm resolution and the append-only guarantee"

# --- 1. EVERY ARM NAMED IN EVERY PRESET MUST RESOLVE -------------------------------------------------------------
# The failure this catches is an arm defined in the ARMS case instead of _flags_for, which happened twice in one
# session and both times ran the wrong thing under the right name.
echo
echo "EVERY ARM IN EVERY PRESET RESOLVES"
ARMS_ALL="$(grep -oE '^[[:space:]]+[a-z0-9_"]+\)[[:space:]]+ARMS="[^"]*"' "$LR" | sed -E 's/.*ARMS="([^"]*)".*/\1/' | tr ' ' '\n' | sort -u | grep -v '^$')"
N_ARMS=0; N_BAD=0
for a in $ARMS_ALL; do
  N_ARMS=$((N_ARMS+1))
  f="$(_flags_for "$a")"
  # EMPTY IS NOT UNDEFINED. `base` is the control and correctly sets no knobs at all; the sentinel is what
  # separates "defined, no overrides" from "never defined". Treating empty as missing would have made this
  # test fail on the one arm every comparison in the project is measured against.
  if [ "$f" = "__UNKNOWN_ARM__" ]; then
    bad "arm '$a' is named in a preset but _flags_for does not define it"; N_BAD=$((N_BAD+1))
  fi
done
[ "$N_BAD" = 0 ] && ok "$N_ARMS distinct arms across all presets, every one defined"

# --- 2. THE UNKNOWN-ARM GUARD ------------------------------------------------------------------------------------
echo
echo "AN UNKNOWN ARM IS REFUSED, NOT SILENTLY RUN AS DEFAULTS"
[ "$(_flags_for definitely_not_an_arm)" = "__UNKNOWN_ARM__" ] \
  && ok "a misspelled arm returns __UNKNOWN_ARM__ rather than an empty flag set" \
  || bad "a misspelled arm does NOT return __UNKNOWN_ARM__ -- it would run the defaults under that name"
[ "$(_flags_for base)" != "__UNKNOWN_ARM__" ] && ok "...and 'base', the no-override control, resolves to an EMPTY flag set" \
  || bad "'base' returns the unknown sentinel"
[ "$(_flags_for keynorm)" != "__UNKNOWN_ARM__" ] && [ -n "$(_flags_for keynorm)" ] && ok "...and an arm with flags returns them" || bad "keynorm does not resolve"

# --- 3. NO ARM MAY SET THE SAME KNOB TWICE -----------------------------------------------------------------------
# `env A=1 A=2` keeps the LAST. A duplicate inside one arm is therefore a silent override, and the banner would
# report the value that ran while the arm definition shows both.
echo
echo "NO ARM SETS THE SAME KNOB TWICE (env keeps the last, so a duplicate is a silent override)"
N_DUP=0
for a in $ARMS_ALL; do
  f="$(_flags_for "$a")"
  [ "$f" = "__UNKNOWN_ARM__" ] && continue
  d="$(echo "$f" | tr ' ' '\n' | grep -oE '^[A-Z][A-Z0-9_]*=' | sort | uniq -d | tr -d '=' | tr '\n' ' ')"
  [ -n "$d" ] && { bad "arm '$a' sets these knobs more than once: $d"; N_DUP=$((N_DUP+1)); }
done
[ "$N_DUP" = 0 ] && ok "no arm sets any knob twice"

# --- 4. EVERY KNOB AN ARM SETS MUST EXIST IN _SPEC ----------------------------------------------------------------
# A typo'd knob is not an error -- it becomes an environment variable nothing reads, and the run proceeds with
# the default while the arm name promises otherwise. The config audit reports it only as "NOTHING READ THESE".
echo
echo "EVERY KNOB AN ARM SETS IS A REAL KNOB"
python3 - "$LR" <<'PY'
import ast, re, subprocess, sys
lr = sys.argv[1]
spec = None
for n in ast.parse(open(lr.replace("longrun.sh", "self_organize.py")).read()).body:
    if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "_SPEC":
        spec = set(ast.literal_eval(n.value))
arms = subprocess.run(["bash", "-c",
    f'eval "$(sed -n \'/^_flags_for()/,/^}}/p\' {lr})"; '
    f'for a in $(grep -oE \'^[[:space:]]+[a-z0-9_"]+\\)[[:space:]]+ARMS="[^"]*"\' {lr} '
    f'| sed -E \'s/.*ARMS="([^"]*)".*/\\1/\' | tr " " "\\n" | sort -u); do echo "$a|$(_flags_for $a)"; done'],
    capture_output=True, text=True).stdout
bad = []
for line in arms.strip().split("\n"):
    if "|" not in line: continue
    arm, flags = line.split("|", 1)
    if flags.strip() == "__UNKNOWN_ARM__": continue
    for k in re.findall(r"\b([A-Z][A-Z0-9_]*)=", flags):
        if k not in spec: bad.append((arm, k))
if bad:
    for arm, k in bad: print(f"  FAIL  arm '{arm}' sets {k}, which is not in _SPEC -- nothing will read it")
    sys.exit(1)
print("  ok    every knob set by every arm is declared in _SPEC")
PY
[ $? = 0 ] || FAIL=1

# --- 5. _reserve: THE APPEND-ONLY GUARANTEE ----------------------------------------------------------------------
# longrun.sh's own header: "NEVER OVERWRITE ANYTHING UNDER runs/ ... Results are the expensive part of this
# project; they are now append-only." That promise is this one function.
echo
echo "_reserve NEVER RETURNS A PATH THAT ALREADY EXISTS"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
p1="$(_reserve "$T/run")";           [ "$p1" = "$T/run" ] && ok "a free path is returned unchanged" || bad "free path: got $p1"
mkdir -p "$p1"
p2="$(_reserve "$T/run")";           [ "$p2" != "$p1" ] && ok "a taken path is suffixed: $(basename "$p2")" || bad "collision: $p2 == $p1"
[ ! -e "$p2" ] && ok "...and the suffixed path is genuinely free" || bad "$p2 already exists"
mkdir -p "$p2"
p3="$(_reserve "$T/run")";           [ "$p3" != "$p1" ] && [ "$p3" != "$p2" ] && ok "it keeps counting: $(basename "$p3")" || bad "third: $p3"
# .log gets the suffix BEFORE the extension, or the log stops being a .log
l1="$(_reserve "$T/a.log")"; : > "$l1"
l2="$(_reserve "$T/a.log")"
case "$l2" in *.log) ok "a .log keeps its extension when suffixed: $(basename "$l2")" ;;
              *)     bad "a suffixed log lost its extension: $l2" ;; esac
[ "$l2" != "$l1" ] && ok "...and does not collide" || bad "log collision"
# 100 reservations, all distinct and none pre-existing -- the property, not three examples.
n_uniq=$(for i in $(seq 1 100); do q="$(_reserve "$T/many")"; mkdir -p "$q"; echo "$q"; done | sort -u | wc -l)
ck $([ "$n_uniq" = 100 ] && echo 0 || echo 1) "100 consecutive reservations are 100 distinct paths (got $n_uniq)"

# --- 6. THE ARMS THIS SESSION DEPENDS ON -------------------------------------------------------------------------
# Named explicitly, because a preset that quietly loses an arm is exactly the failure above and these are the
# ones the next runs will use.
echo
echo "THE ARMS THE NEXT RUNS USE"
for a in lr_075 lr_075_short lr_075_rst lr_075_norst sched_ctl; do
  f="$(_flags_for "$a")"
  case "$f" in
    __UNKNOWN_ARM__|"") bad "$a does not resolve" ;;
    *) ok "$a -> $(echo "$f" | wc -w) knobs" ;;
  esac
done
# lr_075_short must not be able to restart: that is the whole point of the arm.
case "$(_flags_for lr_075_short)" in
  *LR_RESTARTS=0*) ok "lr_075_short pins LR_RESTARTS=0 -- no restart is possible, which is why it exists" ;;
  *)               bad "lr_075_short no longer pins LR_RESTARTS=0" ;;
esac
# ...and lr_075_rst must be able to, or the damping it exists to exercise never runs.
case "$(_flags_for lr_075_rst)" in
  *LR_RESTARTS=0*) bad "lr_075_rst sets LR_RESTARTS=0 -- it cannot exercise the restart damping" ;;
  *LR_STEPS=*)     ok "lr_075_rst sets a short LR_STEPS and does NOT disable restarts" ;;
  *)               bad "lr_075_rst sets no LR_STEPS -- it will not produce multiple cycles" ;;
esac

echo
if [ "$FAIL" = 0 ]; then echo "harness_test: all checks passed"; else echo "!! harness_test FAILED"; fi
exit $FAIL
