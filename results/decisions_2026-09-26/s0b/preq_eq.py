"""Prequential bits/byte over ONE WHOLE EPOCH of the same stream (equal bytes across arms)."""
import json, math, os, sys, time
sys.path.insert(0, "/home/user/LLM-Test/src")
os.environ.setdefault("OMP_NUM_THREADS", "1")
import torch; torch.set_num_threads(1)
from spine import compose, loop
env = dict(a.split("=", 1) for a in sys.argv[1:]); env.setdefault("RUN_DEVICE", "cpu")
t0 = time.time()
sysm = compose.compose(environ=env)
res = loop.run(sysm, max_windows=None, progress=False)
b = res.report.get("LOOP(flush books)"); b = b if isinstance(b, dict) else {}
ctx = int(sysm.configs["LM"].ctx)
nbytes = int(b.get("loop.bytes_scored", 0))
print(json.dumps({"env": env, "windows": len(res.loss_curve), "bytes_scored": nbytes,
                  "preq_bpb": sum(res.loss_curve) * ctx / math.log(2) / nbytes if nbytes else None,
                  "acts": b.get("loop.acts"), "vocab": int(sysm.vocab.size()),
                  "secs": round(time.time() - t0)}))
