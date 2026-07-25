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
cd "$(dirname "$(readlink -f "$0")")"   # sections 5/6/7 open repo files by RELATIVE path -- without this,
#   `bash /path/to/preflight.sh` from anywhere else "fails" on every repo check for the wrong reason.
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

echo "=== 2b. aarch64 install prerequisites (the wheel you get depends on these) ==="
# PyPI ships manylinux_2_28_aarch64 torch wheels and they ARE CUDA builds (they Require-Dist nvidia-cudnn-cu13 /
# nccl / triton, all of which have aarch64 wheels). But there are only cp310..cp314 aarch64 wheels, and
# manylinux_2_28 needs glibc >= 2.28. Miss either and pip silently falls back to an sdist and tries to COMPILE
# torch from source on 72 Grace cores -- which looks like a hang, not an error.
PYV=$(python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])')
python3 -c 'import sys;sys.exit(0 if sys.version_info[:2]>=(3,10) else 1)' \
  && ok "python $PYV (aarch64 torch wheels are cp310+)" \
  || bad "python $PYV -- NO aarch64 torch wheel exists below cp310; pip will try to build from source"
GLIBC=$(getconf GNU_LIBC_VERSION 2>/dev/null | awk '{print $2}')
[ -n "${GLIBC:-}" ] && python3 -c "
import sys;v=tuple(int(x) for x in '$GLIBC'.split('.')[:2]);sys.exit(0 if v>=(2,28) else 1)" \
  && ok "glibc $GLIBC (manylinux_2_28_aarch64 needs >= 2.28)" \
  || warn "glibc '${GLIBC:-?}' -- manylinux_2_28_aarch64 wheels need >= 2.28 (Ubuntu 20.04+)"

echo "=== 3. torch ==="
# NOTE: stderr is NOT swallowed here. A torch that imports but cannot run is the single most likely aarch64
# failure, and its traceback ("no kernel image is available", "libcudnn.so.9: cannot open shared object") is the
# only thing that tells you which one it is.
if python3 - <<'PY'
import torch, platform, sys, subprocess
print(f"  torch {torch.__version__} | cuda {torch.version.cuda} | {platform.machine()} | avail {torch.cuda.is_available()}")
if not torch.cuda.is_available():
    print("  !! torch.cuda.is_available() is False -- see the install commands below"); sys.exit(1)
# 1. Was this wheel COMPILED for Hopper? If sm_90 is absent every kernel dies with "no kernel image is available",
#    but only at the first launch -- i.e. minutes into a run, after the tokenizer seed.
arches = torch.cuda.get_arch_list(); p = torch.cuda.get_device_properties(0)
sm = f"sm_{p.major}{p.minor}"
print(f"  device: {p.name} | {p.total_memory/2**30:.1f} GiB | {sm} | arch_list {arches}")
if sm not in arches and not any(a.startswith("compute_") for a in arches):
    print(f"  !! wheel has no {sm} cubin -- wrong build for GH200"); sys.exit(1)
# 2. Driver vs CUDA major. cu13 wheels need r580+; cu12 wheels need r525+. A too-old driver on a GH200 image is
#    common and the error ("CUDA driver version is insufficient") arrives at the first real kernel, not at import.
try:
    drv = subprocess.check_output(["nvidia-smi","--query-gpu=driver_version","--format=csv,noheader"],
                                  text=True).strip().splitlines()[0]
    need = 580.0 if int((torch.version.cuda or "12").split(".")[0]) >= 13 else 525.0
    print(f"  driver {drv} (cuda {torch.version.cuda} needs >= {need:.0f})")
    if float(drv.split(".")[0]) < need: print("  !! DRIVER TOO OLD for this wheel"); sys.exit(1)
except (OSError, subprocess.CalledProcessError, ValueError, IndexError) as e:
    print(f"  (driver check skipped: {e})")
# 3. Actually run the three kernels this repo lives or dies on. A matmul alone does not exercise cuDNN, and the
#    profile says 46% of the step is sig_of -- a BATCH-1 cuDNN GRU. That is the kernel to prove, not gemm.
a = torch.randn(512, 512, device="cuda"); assert torch.isfinite(a @ a).all()
b = torch.randn(512, 512, device="cuda", dtype=torch.bfloat16); assert torch.isfinite(b @ b).all()
g = torch.nn.GRU(768, 768, 1, batch_first=True).cuda()
x = torch.randn(1, 256, 768, device="cuda", requires_grad=True)     # the exact sig_of shape: B=1, WIN=256, d=768
y, _ = g(x); y.sum().backward()
assert torch.isfinite(x.grad).all(), "cuDNN GRU backward produced non-finite grads"
torch.cuda.synchronize()
print("  fp32 matmul + bf16 matmul + cuDNN GRU(B=1,T=256,d=768) fwd/bwd: OK")
PY
then ok "torch + CUDA usable on this arch (gemm, bf16, cuDNN GRU all execute)"
else bad "torch/CUDA unusable -- see 'FRESH GH200 BOX' at the bottom of this file for the exact install"
fi

echo "=== 3b. numpy ==="
# requirements.txt pins numpy>=1.21, but NOTHING in this repo imports numpy (only legacy/ does, which is not on the
# product path). torch prints "Failed to initialize NumPy" and works fine. The DANGEROUS case is the opposite one:
# numpy present but ABI-mismatched with the torch wheel, which turns every tensor<->array boundary into a hard error.
python3 - <<'PY'
import importlib.util, sys
if importlib.util.find_spec("numpy") is None:
    print("  numpy absent -- fine, no product-path module imports it (torch's 'Failed to initialize NumPy' is cosmetic)")
else:
    import numpy, torch
    try:
        torch.from_numpy(numpy.zeros(4, dtype="float32")); print(f"  numpy {numpy.__version__} <-> torch ABI OK")
    except Exception as e:
        print(f"  !! numpy {numpy.__version__} is ABI-INCOMPATIBLE with torch: {e}"); sys.exit(1)
PY
[ $? -eq 0 ] && ok "numpy state is safe" || bad "numpy/torch ABI mismatch -- pip install -U numpy (or uninstall it: nothing here needs it)"

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
# datastream.py's own probe needs data/train/eng and is skipped on a fresh box -- exactly the box where the page
# size changed. Synthesize a corpus instead so the mmap path is ALWAYS exercised, with files deliberately sized to
# straddle a 64 KB page boundary (Grace) as well as a 4 KB one (x86).
python3 - <<'PY'
import os, random, sys, tempfile
sys.path.insert(0, ".")
from datastream import MmapConcat
PS = os.sysconf("SC_PAGE_SIZE")
with tempfile.TemporaryDirectory() as td:                       # honours TMPDIR; no hardcoded /tmp
    sizes = [PS - 1, PS, PS + 1, 3 * PS + 17, 5]                # unaligned, aligned, off-by-one, tiny
    paths, ref = [], b""
    for i, n in enumerate(sizes):
        p = os.path.join(td, f"part{i:03d}.bin")
        blob = bytes(random.randrange(256) for _ in range(n))
        open(p, "wb").write(blob); paths.append(p); ref += blob
    mc = MmapConcat(paths)
    assert len(mc) == len(ref), f"len {len(mc)} != {len(ref)}"
    r = random.Random(0)
    for _ in range(500):                                        # cross-file slices are where bounds/bisect break
        L = r.randint(1, len(ref)); s = r.randint(0, len(ref) - L)
        assert bytes(mc[s:s + L]) == ref[s:s + L], f"slice {s}:{s+L} mismatch"
    assert mc[0] == ref[0] and mc[-1] == ref[-1] and bytes(mc[-500:]) == ref[-500:]
    cap = 2 * PS
    assert len(MmapConcat(paths, cap=cap)) <= cap, "cap not honoured"
    print(f"  MmapConcat OK across {len(sizes)} files, page size {PS} "
          f"({'64K Grace' if PS == 65536 else f'{PS//1024}K'}), 500 random cross-file slices + cap")
PY
[ $? -eq 0 ] && ok "datastream mmap is page-size agnostic (probed at $(getconf PAGE_SIZE) bytes/page)" \
  || bad "MmapConcat is WRONG at this page size -- DISK_STREAM=1 would corrupt the training stream"
python3 datastream.py 2>/dev/null | grep -q "DROP-IN CORRECT" \
  && ok "datastream probe vs the real data/train/eng corpus" \
  || warn "real-corpus probe skipped (no data/train/eng yet) -- the synthetic probe above still ran"

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

echo "=== 7. Grace host settings (72 cores is a LIABILITY for this workload, not an asset) ==="
CORES=$(nproc)
# This loop is batch-1, tiny-tensor, Python-driven. torch defaults intra-op threads to the physical core count;
# at 72 that is 72 OpenMP threads spinning on ops far below the 32768-element parallel grain size. glibc
# additionally allocates up to 8*ncores malloc arenas, which inflates RSS for no gain.
if [ "$CORES" -gt 16 ] && [ -z "${OMP_NUM_THREADS:-}" ]; then
  warn "OMP_NUM_THREADS unset on a ${CORES}-core host -- torch will spawn ${CORES} intra-op threads for batch-1 work. export OMP_NUM_THREADS=8"
else ok "OMP_NUM_THREADS=${OMP_NUM_THREADS:-unset} on ${CORES} cores"; fi
[ -n "${MALLOC_ARENA_MAX:-}" ] || warn "MALLOC_ARENA_MAX unset -- glibc will create up to $((8*CORES)) arenas on this host. export MALLOC_ARENA_MAX=4"
python3 -c "
import torch,os
n=torch.get_num_threads()
print(f'  torch intra-op threads: {n} | interop: {torch.get_num_interop_threads()}')" 2>/dev/null

echo "=== 8. disk headroom for the corpus ==="
AVAIL_KB=$(df -Pk . | awk 'NR==2{print $4}')
printf '  free here: %d GB\n' "$((AVAIL_KB/1024/1024))"
[ "$AVAIL_KB" -gt 52428800 ] && ok "> 50 GB free (a GPT-2-scale fetch fits)" \
  || warn "< 50 GB free -- fetch_big.py --gb N writes N GB and DISK_STREAM reads it from here"

echo "=== 9. END-TO-END SMOKE (the only check that proves the product path runs on this arch) ==="
# Every check above can pass while the run still dies 20 minutes in. This trains for a few hundred steps on
# synthetic data with the real code path -- tokenizer, memory, world model, fabric, checkpointing -- on CUDA.
if [ "${SMOKE:-1}" = "1" ]; then
  SM=$(mktemp -d); trap 'rm -rf "$SM"' EXIT
  if DEVICE=cuda DATA_MODE=synthetic STREAM_LEN=40000 WIN=128 D_MODEL=256 MODEL=gru LAYERS=1 \
     TOKENIZER=0 WORLD_MODEL=1 FABRIC=1 FAB_N0=3 FAB_NMAX=4 MEM_CAP=20000 \
     AMP=bf16 PROFILE=1 RATE_EVERY=100 BENCH=1 SEED=7 SAVE_CKPT="$SM/ck" CKPT_EVERY=150 \
     timeout 900 python3 self_organize.py > "$SM/smoke.log" 2>&1
  then ok "self_organize.py trains end-to-end on CUDA ($(grep -c . "$SM/smoke.log") log lines)"
       grep -E "^\[BENCH" "$SM/smoke.log" | sed 's/^/    /'
       # CKPT_EVERY is required here: BENCH=1 returns before the end-of-run save, so SAVE_CKPT alone writes nothing.
       # This exercises the ATOMIC checkpoint path (tmp file + rename) on whatever filesystem the box actually has.
       [ -f "$SM/ck/ckpt.pt" ] && ok "atomic checkpoint written + reloadable ($(python3 -c "
import torch;d=torch.load('$SM/ck/ckpt.pt',map_location='cpu',weights_only=False)
print(len(d),'keys, model tensors:',len(d['model']))" 2>&1))" \
         || bad "no ckpt.pt written -- a multi-day run would produce nothing resumable"
  else bad "self_organize.py FAILED on CUDA -- last lines:
$(tail -15 "$SM/smoke.log" | sed 's/^/      /')"
  fi
else warn "SMOKE=0 -- skipped the end-to-end run (this is the check that actually catches arch problems)"; fi

echo
if [ $FAIL -eq 0 ]; then echo "PREFLIGHT OK -- safe to launch"; else echo "PREFLIGHT: $FAIL FAILURE(S) -- fix before launching"; fi

cat <<'EOF'

---------------- FRESH GH200 BOX, FROM ZERO ----------------
# 0. what you are on (all three must be right before pip runs)
uname -m                      # aarch64
python3 -VV                   # 3.10-3.14 : there is NO aarch64 torch wheel below cp310
getconf GNU_LIBC_VERSION      # >= 2.28   : manylinux_2_28_aarch64
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv

# 1. torch. PyPI's manylinux_2_28_aarch64 wheel IS a CUDA build (it Requires-Dist cuda-toolkit / nvidia-cudnn-cu13
#    / nccl / triton, all of which publish aarch64 wheels), so a bare `pip install torch` is enough IF the driver
#    matches the wheel's CUDA major. Check the driver first:
python3 -m venv ~/venv && . ~/venv/bin/activate && pip install -U pip
pip install torch                                                             # driver r580+  (CUDA 13 wheels)
# pip install torch --index-url https://download.pytorch.org/whl/cu128        # driver r525-r579
# pip install torch --index-url https://download.pytorch.org/whl/cu126        # older GH200 images
#    Do NOT `pip install torch==2.1`: the aarch64 wheels of that era were CPU-ONLY. requirements.txt says
#    torch>=2.1, which is satisfiable by a build that cannot see the H100 at all.

# 2. numpy is NOT needed -- no product-path module imports it. Install it only for `datasets`, and never into the
#    same env as an NGC torch (upgrading numpy under NGC's torch breaks its ABI). Fetch in a THROWAWAY env:
python3 -m venv ~/fetchenv && ~/fetchenv/bin/pip install -q datasets
~/fetchenv/bin/python fetch_big.py --dataset fineweb-edu --gb 40 --out data_big

# 3. Grace host env -- put these in the launch, not in your shell history:
export OMP_NUM_THREADS=8 MALLOC_ARENA_MAX=4 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

# 4. verify, then launch
bash preflight.sh

# --- ALTERNATIVE: NGC container (driver-matched, arm64 image, no wheel roulette) ---
docker run --gpus all --ipc=host --ulimit memlock=-1 --ulimit stack=67108864 \
  -e OMP_NUM_THREADS=8 -v "$PWD:/w" -w /w -it nvcr.io/nvidia/pytorch:25.02-py3 bash
#   `docker manifest inspect nvcr.io/nvidia/pytorch:25.02-py3 | grep arm64` confirms the arm64 variant exists.
#   Inside the container: run_full_unfrozen.sh writes its log to ~/$RUN_NAME.txt, which is CONTAINER-LOCAL and
#   dies with the container. Bind-mount it or set RUN_NAME to a path under /w.
EOF
exit $FAIL
