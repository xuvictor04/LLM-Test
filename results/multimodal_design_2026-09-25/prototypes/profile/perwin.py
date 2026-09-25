import os, sys, time, cProfile, pstats, io
sys.path.insert(0, sys.argv[1] + "/src")
import torch; torch.set_num_threads(1)
env = dict(os.environ); env["FAB_N0"] = sys.argv[2]; env["RUN_PROFILE"]="1"
W=int(sys.argv[3])
from spine.compose import compose
from spine import loop
sysm = compose(environ=env)
loop.run(sysm, max_windows=20, progress=False)   # warm
t0=dict(sysm.mode.timing.spans())
pr=cProfile.Profile(); t=time.perf_counter(); pr.enable()
loop.run(sysm, max_windows=W, progress=False)
pr.disable(); dt=time.perf_counter()-t
sp=sysm.mode.timing.spans()
print("N0",sys.argv[2],"n_live",int(sysm.fabric.n_live),"ms/window",round(1000*dt/W,1))
for k,v in sorted(sp.items(), key=lambda x:-(x[1]-t0.get(x[0],0)))[:10]: print("  %-28s %.1f ms/w"%(k,1000*(v-t0.get(k,0))/W))
s=io.StringIO(); pstats.Stats(pr,stream=s).sort_stats("tottime").print_stats(15); print("\n".join(l[:150] for l in s.getvalue().splitlines()[:40]))
import marshal
pstats.Stats(pr).dump_stats(os.environ["PSTAT"])
