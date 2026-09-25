import os, sys, time, cProfile, pstats, io
os.environ.setdefault("OMP_NUM_THREADS","1")
sys.path.insert(0, sys.argv[1] + "/src")
import torch; torch.set_num_threads(1)
N = int(sys.argv[2]); WARM = int(sys.argv[3]) if len(sys.argv) > 3 else 20
env = dict(os.environ); env["FAB_N0"] = str(N); env["DATA_STREAM_BYTES"] = env.get("DATA_STREAM_BYTES","120000")
from spine.compose import compose
from spine import loop
from fabric import api as fab_api
from spine import units as U
sysm = compose(environ=env)
t=time.perf_counter(); loop.run(sysm, max_windows=WARM, progress=False); tw=time.perf_counter()-t
pop = sysm.fabric; cfg = sysm.configs["FAB"]
print("n_live", int(pop.n_live), "warm win/s", round(WARM/tw,2), flush=True)
pr = cProfile.Profile(); t=time.perf_counter(); pr.enable()
fab_api.manage(cfg, pop, step_windows=U.Windows(WARM+1), flush_loss=5.0)
pr.disable(); dt=time.perf_counter()-t
print("manage seconds", round(dt,2), "n_live after", int(pop.n_live))
s=io.StringIO(); pstats.Stats(pr,stream=s).sort_stats("tottime").print_stats(12); print(s.getvalue()[:3500])
