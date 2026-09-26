import sys, os, hashlib
SRC = sys.argv[1]
sys.path.insert(0, SRC)
from spine import assemble, rng
from data import api as d
env = {"DATA_STREAM_BYTES": sys.argv[2] if len(sys.argv) > 2 else "120000"}
configs, wires, warns = assemble.build(environ=env)
dat = configs["DATA"]
print("src", SRC, "source", dat.source, "areas", dat.areas, "n_processes", dat.n_processes, "stream_bytes", dat.stream_bytes)
for seed in (0, 1, 2):
    rng.reset_issued()
    areas = d.open_areas(dat, seed=seed)
    hs = {n: hashlib.sha256(areas.bodies[n]).hexdigest()[:10] for n in areas.names}
    ho = {n: hashlib.sha256(bytes(areas.heldout[n]) if hasattr(areas,'heldout') else b'').hexdigest()[:10] for n in areas.names} if hasattr(areas,'heldout') else None
    print("seed", seed, "bodies", hs, "heldout", ho)
