import os, sys
os.environ.setdefault("OMP_NUM_THREADS","1")
sys.path.insert(0, "/tmp/claude-0/-home-user-LLM-Test/e880caf7-1208-58de-93fd-49c41549bf70/scratchpad/mm/design-world/tree/src")
import torch; torch.set_num_threads(1)
from spine import assemble
cfgs, wires, warns = assemble.build(environ=dict(os.environ))
print(type(cfgs), list(cfgs)[:20] if hasattr(cfgs,'__iter__') else cfgs)
w = cfgs["WORLD"]
print(w)
from world import api as world_api
import inspect
print(inspect.signature(world_api.build))
from spine import rng
print([n for n in dir(rng) if not n.startswith('_')])
