import sys, hashlib
sys.path.insert(0, "/home/user/LLM-Test/src")
from spine import assemble, lever
import data.api as data_api
out = assemble.build(environ={"DATA_STREAM_BYTES": "120000"})
dat = out[0]["DATA"]
print("source", dat.source, "areas", dat.areas)
for seed in (0, 1, 2):
    areas = data_api.open_areas(dat, seed=seed)
    b = getattr(areas, "bodies", None) or {}
    print(seed, {k: hashlib.sha1(v).hexdigest()[:10] for k, v in b.items()})
