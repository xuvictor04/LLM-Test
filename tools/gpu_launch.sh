#!/bin/bash
# ==================================================================================================
# THE OWNER'S ONE COMMAND: CHECK THE BOX, THEN LAUNCH A GPU FLEET THAT OUTLIVES THE TERMINAL (2026-09-27)
# ==================================================================================================
# The retok fleet of 2026-09-27 was launched twice by hand -- the second paste started a second fleet
# on the same card and moved the first one's OUT from under it -- and then stopped by shutting the
# container down, because nothing said it was alive. This is the launch that replaces the pasted
# `nohup ... &` line:
#
#     EXP=heldout bash tools/gpu_launch.sh        # the checks: PASS / WARN / FAIL, each FAIL with its fix
#     EXP=heldout bash tools/gpu_launch.sh --go   # the checks, then the launch, confirmed alive
# (from the checkout; from anywhere else, by its path: EXP=heldout bash /workspace/LLM-Test/tools/gpu_launch.sh).
# EXP=heldout is test 4, the current one, and EXP=session (PARENTS=<its OUT>) test 5, which starts from its finals;
# notes/OWNER_BRIEF.md gives each test's command with its EXP.
#
# EXP IS REQUIRED here (gpu_world.sh's default, world, is the 2026-09-24 experiment, already decided).
# Every other knob -- WINDOWS, SEEDS, EXTRA, PAR, MPS, OUT, KEEP_CKPT, RETOK_ARMS, DEVICE, ... -- is
# read from this environment for the checks and reaches gpu_world.sh unchanged:
#     EXP=retok SEEDS="0 1" WINDOWS=5000 bash tools/gpu_launch.sh --go
# Without --go, a clean check ends in a "ready:" line that carries every knob set here -- each one
# gpu_world.sh or this launcher reads, and every lever a run would inherit -- so the pasted line
# launches the fleet that was checked (2026-09-28: it carried EXP and OUT alone, and after the cooldown
# fleet's knobs its paste would have launched the default retok fleet).
#
# THE CHECKS, fast, in order: EXP; python3 >= 3.10; torch imports, sees CUDA, and names the card; the
# torch version against requirements.txt's floor (torch>=2.11, which is load-bearing on aarch64, where
# PyPI's wheels up to 2.10 are CPU-only; on x86_64 a CUDA build below it is a WARN -- torch
# 2.8.0+cu128 passed the 2026-09-27 smoke, its tripwires and five calibration steps on the H200);
# nvidia-smi and whether something already uses the card; the MPS binary (a WARN: without it runs
# time-slice) and an MPS daemon already running; the cores the fleet will size itself by (the cgroup
# quota where it is lower; OMP_NUM_THREADS, which GNU nproc reports instead of the cores, is ignored by
# the fleet's sizing since the 2026-09-27 review: it was a WARN here that --go launched past, into a
# fleet sized at one core); the free disk against the kept checkpoints' estimate (EXP=retok keeps k0's
# saves, EXP=heldout every run's final, EXP=session every session's and its parents stage's, and since 2026-09-29
# an armed retention probe its best saves:
# about 2 x CKPT_MB per file -- 134 MB at EXP=retok, measured on 2026-09-27's finals, whose pins keep the
# trust book off; 151 MB elsewhere, adding the book's 16.8 MB sketch, saved wherever the book is on since
# 04-6.3's flip); the branch and whether it is at origin's head, and a dirty tree; a fleet already RUNNING
# in OUT -- a FAIL, with the commands to watch or stop it -- or processes of an ended one still running
# there (runs orphaned when it was killed: a FAIL, since gpu_world.sh would refuse the launch; --stop
# clears them); and, at DEVICE=cuda, a fleet under another OUT on this machine. DEVICE=cpu skips the GPU
# checks (a CPU fleet: an operation check only). Every command it prints names the checkout by its
# absolute path, so it works from any terminal.
#
# --go LAUNCHES DETACHED: `setsid nohup bash gpu_world.sh >> LOG 2>&1 < /dev/null &` -- its own session,
# so no terminal close or logout reaches it, HUP ignored, no stdin, and the log APPENDED to, never
# truncated (LOG, default <EXP>_fleet.log in the checkout). It then watches for WAIT_S seconds (20):
# a fleet that exits in that time is reported with its log's tail; one that runs is confirmed from
# its $OUT/STATE (the same pid) and the commands to watch, look, stop and paste back are printed. A
# launch still in its own checks after WAIT_S (copying its code, telling a dead fleet's MPS daemon to
# quit: up to 30 s) gets up to 60 s more while its pid lives, before it is reported.
# It refuses to launch while any check FAILs, and it never deletes anything. FETCH=0 skips the `git
# fetch` behind the origin check (30 s at most without a network).
set -u
cd "$(dirname "$0")/.." || exit 2
ROOT=$PWD
GO=0
for a in "$@"; do
  case "$a" in
    --go) GO=1 ;;
    -h|--help) sed -n '2,/^set -u/p' "$0" | sed '$d'; exit 0 ;;
    *) echo "!! unknown argument '$a' (use --go, or nothing for the checks alone)"; exit 2 ;;
  esac
done

# THE KNOBS SET HERE, TAKEN BEFORE ANY DEFAULT IS ASSIGNED BELOW (2026-09-28, review of 88d3fae and
# 510c3a5). The ready line printed EXP (and OUT) alone, so run without --go with the cooldown fleet's
# knobs -- EXP=retok RETOK_ARMS="1000" COOLDOWN_ARM=100 SEEDS="0 1 2 3 4" KEEP_CKPT=0 -- its paste would
# have launched the default retok fleet: k0, k3000, k1000 and k0_nuis at seeds 0-2, with kept
# checkpoints. READYENV holds every knob gpu_world.sh or this launcher reads (KNOBS), then every lever a
# run would inherit (a name under a package PREFIX the tree declares in src/*/levers.py), each one set
# and not empty, once, quoted for the shell.
KNOBS="EXP OUT WINDOWS SEEDS BYTES RETOK_BYTES EPOCH_BYTES SMOKE_WINDOWS EXTRA ARCH_ALSO LONG PAR MPS FILL
       MAX_SEEDS DEVICE CAL_WINDOWS LADDER RETOK_ARMS COOLDOWN_ARM KEEP_CKPT KEEP_POLL KEEP_EVERY PIN_RETOK
       PROBE_EVERY GO_WORLD_EPOCH EPS RETOK_INCUMBENT HB_EVERY ALLOW_CONCURRENT STOP_WAIT LOG WAIT_S FETCH CKPT_MB
       POOL_WITH PARENTS PARENT_ARM SESSION_WINDOWS W_HEADROOM"
PFX=$(sed -n 's/^ *PREFIX = "\([A-Z][A-Z0-9]*\)".*/\1/p' src/*/levers.py 2>/dev/null | sort -u | paste -sd'|' -)
shq() {  # one word for the shell: as it is when it is safe bare, else single-quoted
  if [[ "$1" =~ ^[A-Za-z0-9_./:,@%+=-]+$ ]]; then printf '%s' "$1"; else printf "'%s'" "${1//\'/\'\\\'\'}"; fi
}
READYENV=""; _seen=" "
for _k in $KNOBS $([[ -n "$PFX" ]] && compgen -e | grep -E "^($PFX)_[A-Z0-9_]+$" | sort); do
  [[ "$_seen" == *" $_k "* || -z "${!_k:-}" ]] && continue
  _seen="$_seen$_k "; READYENV="$READYENV$_k=$(shq "${!_k}") "
done

NP=0; NW=0; NF=0
if [[ -t 1 ]]; then C_P=$'\033[32m'; C_W=$'\033[33m'; C_F=$'\033[31m'; C_0=$'\033[0m'; else C_P=""; C_W=""; C_F=""; C_0=""; fi
pass() { NP=$(( NP + 1 )); printf '  %sPASS%s %s\n' "$C_P" "$C_0" "$1"; }
warn() { NW=$(( NW + 1 )); printf '  %sWARN%s %s\n' "$C_W" "$C_0" "$1"; [[ -n "${2:-}" ]] && printf '       fix: %s\n' "$2"; return 0; }
fail() { NF=$(( NF + 1 )); printf '  %sFAIL%s %s\n' "$C_F" "$C_0" "$1"; [[ -n "${2:-}" ]] && printf '       fix: %s\n' "$2"; return 0; }

EXP_SET=${EXP:-}
# THE CURRENT TEST, WHICH EVERY EXP FIX NAMES (2026-10-02, review of 49a657d): an unset EXP's named EXP=retok,
# the decided 2026-09-27 fleet, whose launch runs 13 runs with k0's periodic saves. The owner brief's test 4.
CUR_EXP=heldout
DEVICE=${DEVICE:-cuda}
case "$EXP_SET" in retok) _o=gpu_retok_out ;; world_epoch) _o=gpu_world_epoch_out ;; heldout) _o=gpu_heldout_out ;;
                   session) _o=gpu_session_out ;; *) _o=gpu_world_out ;; esac
OUT=${OUT:-$_o}
LOG=${LOG:-${EXP_SET:-fleet}_fleet.log}
CMDENV="EXP=${EXP_SET:-<exp>} "; [[ "$OUT" != "$_o" ]] && CMDENV="${CMDENV}OUT=$OUT "
# THE COMMANDS IT PRINTS WORK FROM ANY DIRECTORY (2026-09-27 review): a second terminal opens in
# /workspace or /root, where `bash tools/fleet_dash.sh` is "No such file". gpu_world.sh cds to its
# checkout, so the relative OUT in CMDENV still resolves there.
GWC="${CMDENV}bash $(printf %q "$ROOT/gpu_world.sh")"
DASHC="bash $(printf %q "$ROOT/tools/fleet_dash.sh")"
OUT_ABS=$(realpath -m -- "$OUT")
LOG_ABS=$(realpath -m -- "$LOG")

echo "=== gpu_launch.sh $(date -u +%Y-%m-%dT%H:%M:%SZ) in $ROOT"
echo "    EXP=${EXP_SET:-(unset)} WINDOWS=${WINDOWS:-(default)} SEEDS='${SEEDS:-(default)}' EXTRA='${EXTRA:-}'" \
     "PAR=${PAR:-auto} MPS=${MPS:-auto} OUT=$OUT DEVICE=$DEVICE LOG=$LOG"
echo "    knobs set here (a ready line carries them all): ${READYENV:-(none)}"

# ------------------------------------------------------------------------------------------ the experiment
case "$EXP_SET" in
  retok|world|heldout|session) pass "EXP=$EXP_SET" ;;
  world_epoch) if [[ "${GO_WORLD_EPOCH:-0}" == 1 ]]; then pass "EXP=world_epoch (GO_WORLD_EPOCH=1)"
               else fail "EXP=world_epoch is sized, not run, until O13's two WORLD levers are built (gpu_world.sh refuses it)" "EXP=$CUR_EXP"; fi ;;
  "") fail "EXP is not set: say which fleet; the owner brief's current test, test 4, is EXP=$CUR_EXP (gpu_world.sh's default, world, is the decided 2026-09-24 experiment)" \
           "EXP=$CUR_EXP bash $(printf %q "$ROOT/tools/gpu_launch.sh")$([[ $GO == 1 ]] && echo ' --go')" ;;
  *) fail "EXP='$EXP_SET' is not an experiment gpu_world.sh runs (world, retok, world_epoch, heldout, session)" "EXP=$CUR_EXP" ;;
esac

# A TOP-UP'S FIRST FLEET (EXP=heldout and session, §8 6.3a, 5.3a): the fleet POOL_WITH names, which gpu_world.sh
# checks again.
if [[ -n "${POOL_WITH:-}" ]]; then
  _pw=$(cd "$POOL_WITH" 2>/dev/null && pwd -P)
  if [[ "$EXP_SET" != heldout && "$EXP_SET" != session ]]; then
    fail "POOL_WITH names a top-up's first fleet, which only EXP=heldout and EXP=session read" "unset POOL_WITH"
  elif [[ -z "$_pw" ]] || ! grep -q "^=== plan: EXP=$EXP_SET;" "$_pw/SUMMARY.txt" 2>/dev/null; then
    fail "POOL_WITH='$POOL_WITH' holds no EXP=$EXP_SET fleet" "the first fleet's OUT, as its block printed it"
  elif [[ "$_pw" == "$OUT_ABS" ]]; then
    fail "POOL_WITH is this OUT, and the launch would move that fleet aside" "OUT=<its own directory>, as the first fleet's block printed it"
  else
    pass "POOL_WITH: this fleet is the top-up of $_pw"
  fi
fi

# EXP=session's PARENTS (§8 5.3a): the parents' finals, PARENT_ARM's at every seed, each listed in the directory's
# FINALS.sha256; gpu_world.sh checks every file's sha256 before it starts. Without PARENTS a parents stage trains them.
if [[ "$EXP_SET" == session ]]; then
  _pa=${PARENT_ARM:-k${PIN_RETOK:-1000}}; _ss=$(echo ${SEEDS:-0 1 2 3 4 5 6})
  if [[ -z "${PARENTS:-}" ]]; then
    pass "no PARENTS: a parents stage trains $_pa at seeds $_ss first, one whole epoch each (about 10-16 minutes more on the GPU)"
  else
    _pd=$(cd "$PARENTS" 2>/dev/null && pwd -P); _miss=""
    for _s in $_ss; do for _f in "ckpt/$_pa.s$_s/ckpt.pt" "ckpt/$_pa.s$_s.dyntok.json"; do
      { [[ -n "$_pd" && -f "$_pd/$_f" ]] && awk -v f="$_f" 'substr($0, 67) == f { k = 1 } END { exit !k }' "$_pd/FINALS.sha256" 2>/dev/null; } \
        || _miss="$_miss $_f"
    done; done
    if [[ -z "$_pd" || ! -f "$_pd/FINALS.sha256" ]]; then
      fail "PARENTS='$PARENTS' holds no FINALS.sha256" "PARENTS=<the held-out fleet's OUT, or the directory its finals tar was unpacked into>"
    elif [[ -n "$_miss" ]]; then
      fail "PARENTS: $(echo $_miss | cut -d' ' -f1) is missing or not in its FINALS.sha256 ($(wc -w <<< "$_miss") file(s) in all)" \
           "PARENT_ARM and SEEDS as the held-out fleet's (PARENT_ARM=k1000_mn if its DECISION shipped TOK_MINT_NOVEL)"
    else
      pass "PARENTS: $_pa's finals at seeds $_ss, in $_pd's FINALS.sha256 (gpu_world.sh checks every sha256 before it starts)"
    fi
  fi
fi

# ------------------------------------------------------------------------------------------ python and torch
if ! command -v python3 > /dev/null 2>&1; then
  fail "python3 not found" "install python3 (3.10 or newer)"
else
  PYV=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null)
  if python3 -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3, 10) else 1)' 2>/dev/null; then
    pass "python3 $PYV"
  else
    fail "python3 ${PYV:-?} is older than 3.10" "install python 3.10+ and put it first on PATH"
  fi
fi
FLOOR=$(sed -n 's/^torch>=\([0-9][0-9.]*\).*/\1/p' requirements.txt 2>/dev/null | head -1)
TORCH=$(timeout 180 python3 - 2>&1 <<'PY'
import platform, sys
try:
    import torch
except Exception as e:                                  # noqa: BLE001 -- said, not raised
    print(f"NOIMPORT|{type(e).__name__}: {e}".replace("\n", " ")[:300])
    sys.exit(0)
ok = torch.cuda.is_available()
name = torch.cuda.get_device_name(0) if ok else ""
n = torch.cuda.device_count() if ok else 0
print(f"OK|{torch.__version__}|{torch.version.cuda}|{int(ok)}|{n}|{name}|{platform.machine()}")
PY
)
TORCH=$(grep -E '^(OK|NOIMPORT)\|' <<< "$TORCH" | tail -1)
if [[ "$TORCH" == NOIMPORT* || -z "$TORCH" ]]; then
  fail "torch does not import: ${TORCH#NOIMPORT|}" "pip install torch --index-url https://download.pytorch.org/whl/cu128"
else
  IFS='|' read -r _ TV TCU TOK TN TNAME TARCH <<< "$TORCH"
  if [[ "$DEVICE" == cpu ]]; then
    pass "torch $TV (DEVICE=cpu: CUDA not required, an operation check only)"
  elif [[ "$TOK" == 1 ]]; then
    pass "torch $TV, CUDA $TCU, $TN GPU(s): $TNAME"
  else
    fail "torch $TV (CUDA ${TCU:-none}) sees no CUDA device: every run would raise at its first .to()" \
         "a CUDA build of torch (pip install torch --index-url https://download.pytorch.org/whl/cu128) and a visible GPU"
  fi
  if [[ -n "$FLOOR" ]]; then
    if python3 -c "import sys, re
v = [int(x) for x in re.findall(r'\d+', '$TV'.split('+')[0])[:2]]
f = [int(x) for x in '$FLOOR'.split('.')[:2]]
sys.exit(0 if v >= f else 1)"; then
      pass "torch $TV meets requirements.txt (torch>=$FLOOR)"
    elif [[ "$TARCH" == aarch64 && "$TOK" != 1 ]]; then
      fail "torch $TV is below requirements.txt's torch>=$FLOOR on aarch64, where PyPI's wheels up to 2.10 are CPU-only" \
           "pip install 'torch>=$FLOOR', or a CUDA 12 build: pip install torch --index-url https://download.pytorch.org/whl/cu128"
    else
      warn "torch $TV is below requirements.txt's torch>=$FLOOR; the floor guards aarch64's CPU-only wheels, and on $TARCH a CUDA build below it ran the 2026-09-27 smoke, tripwires and calibration" \
           "none needed on x86_64 with CUDA; pip install 'torch>=$FLOOR' to match the file"
    fi
  fi
fi

# ------------------------------------------------------------------------------------------ the card
if [[ "$DEVICE" == cpu ]]; then
  pass "GPU checks skipped (DEVICE=cpu)"
else
  if ! command -v nvidia-smi > /dev/null 2>&1; then
    fail "nvidia-smi not found: DEVICE=cuda needs an NVIDIA driver and a GPU" "run on the GPU box (or DEVICE=cpu for an operation check)"
  else
    SMI=$(timeout 20 nvidia-smi --query-gpu=index,name,memory.total,memory.used,utilization.gpu --format=csv,noheader,nounits 2>&1)
    if [[ $? -ne 0 || -z "$SMI" ]]; then
      fail "nvidia-smi did not list a GPU: ${SMI:0:200}" "check the driver (nvidia-smi) and the container's GPU access"
    else
      pass "nvidia-smi: $(awk -F', *' '{printf "%s%s (%s MiB)", (NR>1?"; ":""), $2, $3}' <<< "$SMI")"
      BUSY=$(awk -F', *' '$4 > 1024 || $5 > 5 {printf "GPU %s: %s%% busy, %s MiB used; ", $1, $5, $4}' <<< "$SMI")
      [[ -n "$BUSY" ]] && warn "something already uses the card: ${BUSY%; }" \
        "look before launching: nvidia-smi, and $DASHC (a fleet already running?)"
    fi
  fi
  if [[ "${MPS:-auto}" == 0 ]]; then
    pass "MPS=0: runs time-slice the card (no MPS)"
  elif command -v nvidia-cuda-mps-control > /dev/null 2>&1; then
    pass "nvidia-cuda-mps-control present (runs share the card concurrently)"
  else
    warn "nvidia-cuda-mps-control not installed: the runs will time-slice the card instead of sharing it" \
         "none needed (the fleet runs without it; MPS=0 silences this)"
  fi
  MPSD=$(python3 -c '
import os
for d in sorted(os.listdir("/proc")):
    try:
        a = open(f"/proc/{d}/cmdline", "rb").read().split(b"\0")
    except OSError:
        continue
    if d.isdigit() and os.path.basename(a[0].decode(errors="replace")) == "nvidia-cuda-mps-control" and b"-d" in a[1:]:
        print(d)' 2>/dev/null)
  [[ -n "$MPSD" ]] && warn "an MPS control daemon already runs (pid $(echo $MPSD)): a running fleet's, or one a killed fleet left" \
    "if no fleet runs ($DASHC), gpu_world.sh quits the one it left in OUT; any other: echo quit | CUDA_MPS_PIPE_DIRECTORY=<its pipe dir> nvidia-cuda-mps-control"
fi
# THE CORES THE FLEET SIZES ITSELF BY, as gpu_world.sh reads them: nproc with OMP_NUM_THREADS and
# OMP_THREAD_LIMIT emptied (GNU nproc reports them instead of the cores), then the cgroup quota where it is
# lower. An exported OMP_NUM_THREADS was a WARN here that --go launched past, into a fleet sized at one
# core and PAR 1, and the fix it printed was refused by then (2026-09-27 review); the fleet now ignores it
# for the sizing and gives every run OMP_NUM_THREADS=1 itself, so it is only said.
NCORE=$(OMP_NUM_THREADS= OMP_THREAD_LIMIT= nproc)
QUOTA=$(awk '$1 != "max" && $2 > 0 { q = int($1 / $2); print (q > 0 ? q : 1) }' /sys/fs/cgroup/cpu.max 2>/dev/null)
[[ -n "$QUOTA" ]] || QUOTA=$(awk 'NR == FNR { q = $1; next } q > 0 && $1 > 0 { x = int(q / $1); print (x > 0 ? x : 1) }' \
                               /sys/fs/cgroup/cpu/cpu.cfs_quota_us /sys/fs/cgroup/cpu/cpu.cfs_period_us 2>/dev/null)
if [[ "$QUOTA" =~ ^[0-9]+$ && "$QUOTA" -lt "$NCORE" ]]; then SIZE="$QUOTA, the cgroup quota (nproc reports $NCORE)"
else SIZE="$NCORE (nproc)"; fi
pass "cores the fleet sizes its parallelism by: $SIZE$([[ -n "${OMP_NUM_THREADS:-}${OMP_THREAD_LIMIT:-}" ]] \
  && echo "; OMP_NUM_THREADS/OMP_THREAD_LIMIT set here (${OMP_NUM_THREADS:-}${OMP_THREAD_LIMIT:+ / $OMP_THREAD_LIMIT}) are ignored for that, and every run gets OMP_NUM_THREADS=1")"

# ------------------------------------------------------------------------------------------ the disk
_p=$OUT; while [[ ! -d "$_p" ]]; do _p=$(dirname "$_p"); done
FREE_B=$(( $(df -Pk "$_p" | awk 'NR == 2 {print $4}') * 1024 ))
KC=${KEEP_CKPT:-$([[ "$EXP_SET" == retok || "$EXP_SET" == heldout || "$EXP_SET" == session ]] && echo 1 || echo 0)}
W=${WINDOWS:-20000}
case "$EXP_SET" in retok) _s="0 1 2" ;; heldout|session) _s="0 1 2 3 4 5 6" ;; *) _s="0 1 2 3 4" ;; esac
SD=${SEEDS:-$_s}
NS=$(wc -w <<< "$SD")
# 134 MB A FILE AT EXP=retok, 151 ELSEWHERE (2026-10-02, review of 49a657d): EXP=retok's pins turn the trust
# book off, and DATA.stream_state writes no sketch into a checkpoint at 'off'.
CKPT_MB=${CKPT_MB:-$([[ "$EXP_SET" == retok ]] && echo 134 || echo 151)}
# EXP=session's parents stage (no PARENTS) keeps its finals at any KEEP_CKPT: they are the sessions' parents.
if [[ ( "$KC" == 1 || ( "$EXP_SET" == session && -z "${PARENTS:-}" ) ) && "$W" =~ ^[0-9]+$ ]]; then
  if [[ "$EXP_SET" == retok ]]; then
    ARMS=${RETOK_ARMS:-"3000 1000"}
    g=0; for c in $ARMS; do a=$g; b=$c; while (( b )); do t=$(( a % b )); a=$b; b=$t; done; g=$a; done
    KE=${KEEP_EVERY:-$g}; [[ "$KE" =~ ^[1-9][0-9]*$ ]] || KE=1000
    PER=$(( (11 * W + 10 * KE - 1) / (10 * KE) + 2 + 2 + $(wc -w <<< "$ARMS") + $([[ -n "${COOLDOWN_ARM:-}" ]] && echo 1 || echo 0) ))
    FILES=$(( NS * PER + 2 ))
  else
    # SINCE 04-6.2's FLIP (2026-09-29) A RUN WHOSE RETENTION PROBE IS ARMED LEAVES ITS BEST SAVES BESIDE ITS
    # FINAL ONE (ckpt.pt.best and .best.prev, and CKPT_BEST_KEEP's slots with theirs). gpu_world.sh's own
    # budget block counts them, run here between its markers with this launch's settings -- EXTRA, this
    # environment and, at EXP=world_epoch and heldout, the probe's pin -- so the two disk checks count the
    # same files. EXP=world and world_epoch run four arms a seed, EXP=heldout three (2026-10-02), and each
    # fleet one rerun.
    _pp=""; [[ "$EXP_SET" == world_epoch || "$EXP_SET" == heldout || "$EXP_SET" == session ]] && _pp="EVAL_RETENTION_EVERY=${PROBE_EVERY:-700}"
    BF=$(EXTRA="${EXTRA:-}" EXP_ENV="$_pp" CODE_DIR="$ROOT" WINDOWS="$W" KEEP_EVERY=1000 bash -c \
         "$(sed -n "/^# >>> THE BEST SAVES' BUDGET/,/^# <<< THE BEST SAVES' BUDGET\$/p" gpu_world.sh)"$'\n''echo "$BEST_FILES"' 2>/dev/null)
    [[ "$BF" =~ ^[0-9]+$ ]] || BF=0
    NA=4; [[ "$EXP_SET" == heldout ]] && NA=3
    FILES=$(( (NS * NA + 1) * (1 + BF) ))
    # EXP=session (§8 5.3a): three sessions a parent and W, at KEEP_CKPT=1, and without PARENTS a parent a seed.
    # W'S FILES AT W'S SIZE (2026-10-02, the review of 5.3a): its fabric is preallocated at max(the parent's slots, its
    # n_live + W_HEADROOM), so its files are priced at CKPT_MB x (slots + W_HEADROOM) / slots, the most it can take
    # (slots EXTRA's FAB_SLOTS, else 4096); gpu_world.sh prices them at the smoke's W, the rest at the others'.
    if [[ "$EXP_SET" == session ]]; then
      FILES=0; [[ "$KC" == 1 ]] && FILES=$(( NS * 3 + 1 )); [[ -z "${PARENTS:-}" ]] && FILES=$(( FILES + NS ))
      FILES=$(( FILES * (1 + BF) ))
      WF=0; [[ "$KC" == 1 ]] && WF=$(( 1 + BF ))
      _fs=$(echo " ${EXTRA:-} " | tr ' ' '\n' | sed -n 's/^FAB_SLOTS=\([0-9][0-9]*\)$/\1/p' | tail -1)
      [[ "${_fs:-0}" -gt 0 ]] || _fs=4096; _wh=${W_HEADROOM:-2048}; [[ "$_wh" =~ ^[0-9]+$ ]] || _wh=2048
      W_MB=$(( (CKPT_MB * (_fs + _wh) + _fs - 1) / _fs ))
    fi
  fi
  NEED_B=$(( FILES * CKPT_MB * 2 * 1000000 ))
  [[ "$EXP_SET" == session && "${WF:-0}" -gt 0 ]] && NEED_B=$(( ((FILES - WF) * CKPT_MB + WF * W_MB) * 2 * 1000000 ))
  G() { awk -v b="$1" 'BEGIN { printf "%.1f", b / 1e9 }'; }
  # THE FIX FITS THE EXPERIMENT (2026-10-02, review of 49a657d; gpu_world.sh's own disk check says the same):
  # EXP=retok's spike test needs k0's saves; EXP=heldout's seeds are pre-registered and its first fleet's finals
  # are the next test's parents, which a top-up's (POOL_WITH) are not.
  case "$EXP_SET" in
    retok) _fx="free space there, fewer SEEDS, or KEEP_CKPT=0 (which leaves the spike test without its control)" ;;
    heldout) if [[ -n "${POOL_WITH:-}" ]]; then _fx="free space there, or KEEP_CKPT=0: the next test starts from the first fleet's finals, not a top-up's"
             else _fx="free space there, keeping the 7 pre-registered seeds and KEEP_CKPT on: the finals are the next test's parents"; fi ;;
    session) _fx="free space there, or KEEP_CKPT=0, which keeps no session's checkpoint (a parents stage keeps its finals: the sessions resume them)" ;;
    *) _fx="free space there, fewer SEEDS, or KEEP_CKPT=0" ;;
  esac
  if (( FREE_B < NEED_B )); then
    fail "disk: $(G $FREE_B) GB free at $_p, and the kept checkpoints may need $(G $NEED_B) GB ($FILES files x 2 x $CKPT_MB MB$([[ "${WF:-0}" -gt 0 ]] && echo ", W's $WF at $W_MB MB") at $NS seed(s))" \
         "$_fx"
  elif (( FREE_B < 2 * NEED_B )) && [[ "${FILL:-$([[ "$EXP_SET" == heldout || "$EXP_SET" == session ]] && echo 0 || echo 1)}" != 0 ]]; then
    warn "disk: $(G $FREE_B) GB free, $(G $NEED_B) GB needed at $NS seed(s): FILL will add few extra seeds (it stops at 0.9 of the free disk)" \
         "free space for more seeds, or accept fewer"
  else
    pass "disk: $(G $FREE_B) GB free at $_p; the kept checkpoints may need $(G $NEED_B) GB at $NS seed(s)"
  fi
else
  (( FREE_B > 2000000000 )) && pass "disk: $(( FREE_B / 1000000000 )) GB free at $_p (no kept checkpoints)" \
    || warn "disk: only $(( FREE_B / 1000000 )) MB free at $_p" "free a few GB for the logs and the archive"
fi

# ------------------------------------------------------------------------------------------ the checkout
BR=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
if [[ -z "$BR" ]]; then
  warn "not a git checkout: the fleet's commit will read '?'" ""
else
  [[ "$BR" == rm-predict-DC ]] && pass "branch $BR" || warn "branch $BR, not rm-predict-DC" "git checkout rm-predict-DC && git pull --ff-only"
  if [[ "${FETCH:-1}" == 0 ]]; then
    warn "origin not checked (FETCH=0)" "git fetch origin $BR; git status"
  elif timeout 30 git fetch -q origin "$BR" > /dev/null 2>&1; then
    L=$(git rev-parse HEAD); R=$(git rev-parse "origin/$BR" 2>/dev/null)
    if [[ "$L" == "$R" ]]; then pass "at origin/$BR's head ($(git rev-parse --short HEAD))"
    elif git merge-base --is-ancestor HEAD "origin/$BR" 2>/dev/null; then
      warn "behind origin/$BR by $(git rev-list --count HEAD.."origin/$BR") commit(s): the fleet would run older code" "git pull --ff-only"
    elif git merge-base --is-ancestor "origin/$BR" HEAD 2>/dev/null; then
      warn "ahead of origin/$BR by $(git rev-list --count "origin/$BR"..HEAD) local commit(s) that are not on origin" "none needed if you meant it"
    else
      warn "diverged from origin/$BR" "git status; then git pull --ff-only once it can"
    fi
  else
    warn "could not reach origin (git fetch failed): cannot say whether this is the newest code" "check the network; git pull --ff-only"
  fi
  if git diff --quiet HEAD -- src run.py gpu_world.sh tools 2>/dev/null; then pass "no local edits under src/, run.py, gpu_world.sh, tools/"
  else warn "local edits under src/, run.py, gpu_world.sh or tools/: the block will say DIRTY" "git stash, or git checkout -- <files>"; fi
fi

# ------------------------------------------------------------------------------------------ a fleet already running
ST=$(bash gpu_world.sh --status 2>/dev/null)
STV=$?
# PROCESSES OF THE FLEET IN OUT THAT STILL RUN, AS gpu_world.sh's LAUNCH GATE FINDS THEM (runs and shells
# carrying its GW_FLEET_OUT, or a launch from before the lock writing under OUT). An ended fleet's
# orphaned runs PASSed here as "not running" and --go then launched into gpu_world.sh's refusal, "THE
# FLEET EXITED within 1 s" (2026-09-27 review): it is a FAIL, with --stop as its fix.
LEFT=$(bash tools/fleet_dash.sh --scan own "$OUT" 2>/dev/null | awk -F'\t' '$2 == "run" || $2 == "shell" { print $1 }')
case "$STV" in
  0|5) fail "a fleet is RUNNING in $OUT ($(grep -m1 -o '#####  [A-Z ]*  #####' <<< "$ST" | tr -d '#' | xargs)): launching again would be refused" \
            "watch it: $DASHC $(printf %q "$OUT_ABS") | look: $GWC --status | stop it: $GWC --stop" ;;
  *) V=$(grep -m1 -o '#####  [A-Z ]*  #####' <<< "$ST" | tr -d '#' | xargs)
     if [[ -n "$LEFT" ]]; then
       fail "$OUT holds a ${V:-previous} fleet that is not running, but $(wc -w <<< "$LEFT") of its process(es) still run (pid $(echo $LEFT)): runs orphaned when it was killed or interrupted, and gpu_world.sh refuses a launch while they run" \
            "$GWC --stop   (it stops them; then launch again)"
     elif [[ "$STV" == 2 ]]; then
       pass "no fleet in $OUT yet"
     else
       pass "$OUT holds a ${V:-previous} fleet, not running: the launch moves it aside whole, as $OUT.<its launch stamp> (nothing is deleted)"
     fi ;;
esac
if [[ "$DEVICE" != cpu && "${ALLOW_CONCURRENT:-0}" != 1 ]]; then
  OTHER=$(bash tools/fleet_dash.sh --scan card "$OUT" 2>/dev/null)
  [[ -n "$OTHER" ]] && fail "another fleet runs on this machine's GPU: $(cut -f3 <<< "$OTHER" | head -2 | tr '\n' ' ')" \
    "wait for it or stop it (bash $(printf %q "$ROOT/gpu_world.sh") --stop with its EXP/OUT); ALLOW_CONCURRENT=1 runs both anyway"
fi
command -v setsid > /dev/null 2>&1 || warn "setsid not found: the fleet stays in this terminal's session (nohup still ignores the hang-up)" "apt-get install util-linux"

echo "=== $NP PASS, $NW WARN, $NF FAIL"
if [[ "$GO" != 1 ]]; then
  (( NF == 0 )) && echo "    ready: ${READYENV}bash $(printf %q "$ROOT/tools/gpu_launch.sh") --go" || echo "    fix the FAILs, then run this again"
  exit $(( NF > 0 ))
fi
if (( NF > 0 )); then
  echo "!! NOT LAUNCHED: fix the FAIL(s) above first."
  exit 1
fi

# ------------------------------------------------------------------------------------------ --go
mkdir -p -- "$(dirname -- "$LOG")" 2>/dev/null
printf '\n==== %s: tools/gpu_launch.sh --go (EXP=%s OUT=%s), %d PASS %d WARN ====\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$EXP_SET" "$OUT" "$NP" "$NW" >> "$LOG" || { echo "!! cannot write $LOG"; exit 1; }
if command -v setsid > /dev/null 2>&1; then
  setsid nohup bash gpu_world.sh >> "$LOG" 2>&1 < /dev/null &
else
  nohup bash gpu_world.sh >> "$LOG" 2>&1 < /dev/null &
fi
PID=$!
T0=$(date +%s)
echo "=== launched: pid $PID at $(date -u +%H:%M:%SZ), detached (its own session, hang-up ignored, no stdin); log $LOG (appended)"
WAIT_S=${WAIT_S:-20}
# ALIVE IS THE PID A FRESH $OUT/STATE NAMES (written after this launch, with that pid's start time),
# else the pid started here: setsid execs in place, so the two are one pid, but only STATE is proof.
st_pid() { local lt; lt=$(sed -n 's/^launch_t=//p' "$OUT/STATE" 2>/dev/null | tail -1)
           [[ -n "$lt" && "$lt" -ge $(( T0 - 2 )) ]] && sed -n 's/^pid=//p' "$OUT/STATE" | tail -1; }
st_alive() { local p s; p=$(st_pid); [[ -n "$p" ]] || return 1
             s=$(sed -n 's/^pid_start=//p' "$OUT/STATE" | tail -1)
             [[ "$(sed 's/.*) //' "/proc/$p/stat" 2>/dev/null | cut -d' ' -f20)" == "$s" ]]; }
for _i in $(seq 1 "$WAIT_S"); do
  sleep 1
  if ! kill -0 "$PID" 2>/dev/null && ! st_alive; then
    echo "!! THE FLEET EXITED within $(( $(date +%s) - T0 )) s. The end of $LOG:"
    tail -n 30 "$LOG" | sed 's/^/    /'
    exit 1
  fi
done
# A LAUNCH STILL IN ITS OWN CHECKS has written no STATE yet (its code copy; the quit it sends a dead
# fleet's MPS daemon, up to 30 s): up to 60 s more, while its pid lives.
if ! st_alive && kill -0 "$PID" 2>/dev/null; then
  echo "    (no STATE yet after $WAIT_S s: the launch is still in its checks; waiting up to 60 s more)"
  for _i in $(seq 1 60); do sleep 1; st_alive && break; kill -0 "$PID" 2>/dev/null || break; done
fi
if ! st_alive; then
  if kill -0 "$PID" 2>/dev/null; then
    echo "!! pid $PID runs, but no fresh $OUT/STATE names a live fleet after $(( $(date +%s) - T0 )) s. The end of $LOG:"
  else
    echo "!! THE FLEET EXITED within $(( $(date +%s) - T0 )) s. The end of $LOG:"
  fi
  tail -n 15 "$LOG" | sed 's/^/    /'
  exit 1
fi
PID=$(st_pid)
echo "=== RUNNING: pid $PID for $(( $(date +%s) - T0 )) s, confirmed by $OUT/STATE; phase $(sed -n 's/^phase=//p' "$OUT/STATE" | tail -1)"
cat <<EOF
    Each command below works from any terminal and any directory.
    watch it (a second terminal):  $DASHC $(printf %q "$OUT_ABS")
    one look, any time:            $GWC --status
    the log:                       tail -n 20 $(printf %q "$LOG_ABS")
    stop it (it writes its block): $GWC --stop
    when it has ended, paste back: cat $(printf %q "$OUT_ABS/PASTE_BACK.txt")
    For its first minutes the card reads 0% for a stretch of every step: each smoke and calibration
    run builds on the CPU (python and torch, corpus, tokenizer, stream, model: 15-30 s, longer when the
    CPU is shared; the smoke prints the figure measured here) before it uses the GPU. The log
    prints a heartbeat line every ${HB_EVERY:-30} s. Judge it by the dashboard or --status, never by
    nvidia-smi or a quiet terminal, and do not launch it again or git pull while it runs.
EOF
exit 0
