# Build the synthetic stream through spine.compose (RUN_SEED -> open_areas -> draw_stream) per seed; hash it.
import sys, os, hashlib, time
SRC = sys.argv[1]; seed = sys.argv[2]; nbytes = sys.argv[3] if len(sys.argv) > 3 else "200000"
sys.path.insert(0, SRC)
env = {k: v for k, v in os.environ.items()}
env.update({"DATA_STREAM_BYTES": nbytes, "RUN_SEED": seed, "RUN_DEVICE": "cpu"})
from spine import compose as C
t = time.time()
s = C.compose(env)
h = lambda b: hashlib.sha256(bytes(b)).hexdigest()[:12]
print("src", SRC.split('/')[-2], "seed", seed, "run.seed", s.configs["RUN"].seed, "source", s.configs["DATA"].source,
      "stream", h(s.stream.bytes), "len", len(s.stream.bytes),
      "bodies", {n: h(s.areas.bodies[n]) for n in s.areas.names},
      "vocab_size", s.vocab.size(),
      "bpt", round(float(s.vocab.bytes_per_token), 4), "first40", bytes(s.stream.bytes[:40]), "t", round(time.time()-t, 1))
