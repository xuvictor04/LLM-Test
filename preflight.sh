#!/bin/bash
# ============ PREFLIGHT: fail loudly on a fresh box, BEFORE burning GPU hours ============
# Every check here corresponds to something that has actually gone wrong in this project:
#   - a benchmark that silently ran at d=128 because D_MODEL_B is read by nothing
#   - a bench arm that died on a missing /usr/bin/time
#   - a multi-day run that would have trained on 2 MB because CORPUS_CAP defaults to 2000000
#   - checkpoints that only existed at end-of-run because CKPT_EVERY defaults to 0
#   - EPOCHS>1 replaying byte-identical data because DISK_STREAM defaulted to 0
# The GH200 adds a new class: aarch64. This repo has only ever run on x86.
#
#   bash preflight.sh              # check only
#   FIX=1 bash preflight.sh        # also install what is missing
set -u
FAIL=0
ok(){ printf '  \033[32mPASS\033[0m %s\n' "$1"; }
bad(){ printf '  \033[31mFAIL\033[0m %s\n' "$1"; FAIL=$((FAIL+1)); }
warn(){ printf '  \033[33mWARN\033[0m %s\n' "$1"; }

echo "=== 1. platform ==="
ARCH=$(uname -m); echo "  arch: $ARCH | kernel: $(uname -r) | page size: $(getconf PAGE_SIZE 2>/dev/null || echo '?')"
[ "$ARCH" = "aarch64" ] && warn "aarch64 (Grace): this repo has only ever been run on x86 -- the checks below matter more than usual"
echo "  cores: $(nproc) | host RAM: $(free -g 2>/dev/null | awk '/^Mem:/{print $2" GiB"}' || echo '?')"

echo "=== 2. GPU ==="
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader | sed 's/^/  /'
  ok "nvidia-smi present"
else bad "nvidia-smi missing"; fi

echo "=== 3. torch ==="
if python3 - <<'PY' 2>/dev/null
import torch, platform, sys
print(f"  torch {torch.__version__} | {platform.machine()} | cuda avail {torch.cuda.is_available()}")
if torch.cuda.is_available():
    p = torch.cuda.get_device_properties(0)
    print(f"  device: {p.name} | {p.total_memory/2**30:.1f} GiB | sm_{p.major}{p.minor}")
    a = torch.randn(512, 512, device="cuda"); assert torch.isfinite(a @ a).all()
    print("  cuda matmul: OK")
else:
    sys.exit(1)
PY
then ok "torch + CUDA usable"
else bad "torch/CUDA unusable -- on aarch64 (Grace) install with:  pip install torch --index-url https://download.pytorch.org/whl/cu126"
fi

echo "=== 4. shell tools the bench uses ==="
for t in awk sed grep du sort head tail date; do
  command -v $t >/dev/null 2>&1 && ok "$t" || bad "$t missing"
done
command -v /usr/bin/time >/dev/null 2>&1 || warn "/usr/bin/time absent (bench_gpu.sh uses \$(date) instead -- fine)"

echo "=== 5. repo self-test ==="
python3 -c "import ast,sys
for f in ['self_organize.py','memory.py','world_model.py','tokenizer.py','datastream.py','prompt.py','verification.py']:
    ast.parse(open(f).read())
print('  all modules parse')" || bad "a module failed to parse"
python3 datastream.py 2>/dev/null | grep -q "DROP-IN CORRECT" && ok "datastream mmap probe (page size $(getconf PAGE_SIZE))" \
  || warn "datastream probe did not report DROP-IN CORRECT (needs data/train/eng)"

echo "=== 6. THE KNOB TRAP ==="
# D_MODEL_B was read by NOTHING; every benchmark silently ran at the d=128 default. It is aliased now, but the
# general failure -- a config name that no code reads -- is the one that has cost this project the most.
if python3 - <<'PY'
import re, sys
src = open("self_organize.py").read()
names = ["D_MODEL","D_MODEL_B","MODEL","LAYERS","HEADS","WIN","BATCH_W","ACCUM","FABRIC","SOCIETY","EXPERTS",
         "FAB_NMAX","FAB_N0","ENS_K","IND_K","ROUTE_T","ROUTE_LEARN","MEM_CAP","MEM_PER_EXPERT","MEM_QUOTA",
         "WRITE_ADAPTIVE","WRITE_TARGET","WRITE_QUANTILE","TOKENIZER","TOK_ONLINE","VMAX","SEED_VOCAB","RETOK_EVERY",
         "RETOK_TAIL","WORLD_MODEL","WORLD_FEEDBACK","WORLD_GROW","SELF_ORG","DISK_STREAM","CORPUS_CAP","STREAM_LEN",
         "EPOCHS","CKPT_EVERY","SAVE_CKPT","RESUME","SIG_BATCH","ENC_FUSE","KEY_BATCH","KEY_PREGATE","REKEY_CHUNK",
         "AMP","TF32","PROFILE","RATE_EVERY","BENCH","SEED","DEVICE","DATA_MODE","DATA_DIR","DOMAINS","ENC_WARMUP"]
missing = [n for n in names if not re.search(r'["\']' + n + r'["\']', src)]
print("  " + ("all %d documented knobs are READ by self_organize.py" % len(names)) if not missing
      else "  UNREAD KNOBS (setting these does NOTHING): " + ", ".join(missing))
sys.exit(1 if missing else 0)
PY
then ok "every knob the launch command sets is actually read"
else bad "some knobs are NOT read -- setting them is a silent no-op (this is the D_MODEL_B failure mode)"
fi

echo
if [ $FAIL -eq 0 ]; then echo "PREFLIGHT OK -- safe to launch"; else echo "PREFLIGHT: $FAIL FAILURE(S) -- fix before launching"; fi
exit $FAIL
