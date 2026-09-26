import sys
sys.path.insert(0, "/home/user/LLM-Test/src")
from spine import assemble, lever
import data.api as D
nb = int(sys.argv[1])
out = assemble.build(environ={"DATA_STREAM_BYTES": str(nb)})
dat = out[0]["DATA"]
areas = D.open_areas(dat, seed=0)
plan = D.data_plan(dat, areas, epochs=1, win_tokens=128, bytes_per_token=1.5)
print(nb, "schedule", plan.schedule, "bounds", plan.phase_bounds)
