import os, sys, time
os.environ["OMP_NUM_THREADS"]="1"; os.environ["MKL_NUM_THREADS"]="1"
sys.path.insert(0, sys.argv[1] + "/src")
import torch; torch.set_num_threads(1)
ctx = sys.argv[2]; arch = sys.argv[3]
env = {"DATA_STREAM_BYTES": "120000", "LM_CTX": ctx, "LM_ARCH": arch, "SIG_WARMUP": "20",
       "SIG_WARMUP_PROBE_EVERY": "10"}
from spine.compose import compose
from spine import loop, rng
rng.reset_issued()
sysm = compose(environ=env)
t = time.time()
res = loop.run(sysm, max_windows=30, progress=False)
dt = time.time() - t
print(f"arch={arch} ctx={ctx} windows={res.windows_here} {res.windows_here/dt:.2f} win/s "
      f"{res.windows_here*int(ctx)/dt:.0f} tok/s loss_first={res.loss_first:.3f}")
