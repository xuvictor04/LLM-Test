"""Model-free replay of the fleet's epoch-0 stream (a CPU operation check, no training), adapted from an
analyst's replay: the per-byte area labels of DATA.draw_stream at RUN_SEED=s, DATA_STREAM_BYTES=3780000,
written beside this script as labels.s<seed>.npy, and validated against the k0 run's own per-flush bytes
by re-tokenizing with the build vocabulary. Run a COPY of this folder from a scratch directory (never
with the checkout's root as the working directory: its memory.py shadows src/memory), with
PYTHONDONTWRITEBYTECODE=1:
    python3 replay.py <seed> <unpacked gpu_retok_out> <the checkout's src/ at 319f313's src>"""
import json, os, sys, time
import numpy as np

SRC = os.path.abspath(sys.argv[3])
sys.path[:] = [p for p in sys.path if os.path.abspath(p or ".") != os.path.dirname(SRC)]
sys.path.insert(0, SRC)
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(sys.argv[2])

from spine.assemble import build as _build          # noqa: E402
from spine.compose import RNG_SUBSYSTEMS           # noqa: E402
from data import api as data_api                   # noqa: E402
from tok import api as tok_api                     # noqa: E402
from train import api as run_api                   # noqa: E402

seed = int(sys.argv[1])
env = {k: v for k, v in os.environ.items()}
env.update(RUN_SEED=str(seed), DATA_STREAM_BYTES="3780000", RUN_DEVICE="cpu", TOK_RETOK_EVERY="0",
           OMP_NUM_THREADS="1")
t0 = time.time()
configs, wires, warnings = _build(environ=env)
run, lm, data, tok = configs["RUN"], configs["LM"], configs["DATA"], configs["TOK"]
proc = run_api.process_setup(run)
streams = run_api.streams(run, RNG_SUBSYSTEMS)
areas = data_api.open_areas(data, seed=int(run.seed))
vocab = tok_api.build_vocabulary(tok, area_heads=areas.bodies, seed=int(run.seed), soft_cap=None)
plan = data_api.data_plan(data, areas, epochs=int(run.epochs), win_tokens=int(lm.ctx),
                          bytes_per_token=float(vocab.bytes_per_token))
stream = data_api.draw_stream(data, areas, plan, epoch=0, seed=int(run.seed))
print(f"seed {seed}: stream {len(stream.bytes)} bytes, areas {stream.area_names}, phase bounds {plan.phase_bounds}, "
      f"schedule {plan.schedule}, per-area drawn {stream.per_area_drawn}  ({time.time() - t0:.1f}s)")
names = list(stream.area_names)
lab = np.array([names.index(x) for x in stream.labels], dtype=np.uint8)
np.save(os.path.join(HERE, f"labels.s{seed}.npy"), lab)
json.dump(dict(names=names, bounds=plan.phase_bounds, schedule=[list(p) for p in plan.schedule]),
          open(os.path.join(HERE, f"labels.s{seed}.json"), "w"))

# VALIDATION: the build segmentation's 128-id windows against k0's per-flush bytes
seg = tok_api.tokenize(tok, vocab, stream.bytes, stream.labels, regularize=True, seed=int(run.seed))
bp = list(seg.byte_pos) + [len(stream.bytes)]
ctx = int(lm.ctx)
nwin = len(seg.ids) // ctx
fb = json.load(open(os.path.join(OUT, "curves", f"k0.s{seed}.bytes.json")))
cands = {}
for shift in (0, 1):
    w = []
    for i in range(nwin):
        a, b = i * ctx + shift, (i + 1) * ctx + shift
        if b > len(seg.ids):
            break
        w.append(bp[b] - bp[a])
    cands[shift] = w
for shift, w in cands.items():
    n = min(len(w), len(fb))
    eq = sum(1 for i in range(n) if w[i] == fb[i])
    print(f"  shift {shift}: {len(w)} windows vs k0 {len(fb)} flushes; equal per-window bytes {eq}/{n}; "
          f"first mismatch {next((i for i in range(n) if w[i] != fb[i]), None)}")
print(f"  ids {len(seg.ids)}, bytes/token {seg.bytes_per_token:.4f}; total {time.time() - t0:.1f}s")
