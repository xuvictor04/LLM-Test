"""Model-free sizing of register §8 6.3b's real-text fleet through DATA's, TOK's, EVAL's and OPT's own entry points
(CPU, operation only): the build vocabulary's bytes/token, the epoch's windows and each phase's, the held-out blocks
and the windows each half pins, the exposure and the plan's gates, phase 1's bytes and where the two draws first part,
and the learning rate OPT prices each draw's epoch at.

    python3 realplan.py <seed> [DATA_STREAM_BYTES]      # 3,780,000 by default: the fleet's EPOCH_BYTES

The pins are the fleet's (DATA_SOURCE=real, EVAL_RETENTION_EVERY=650, EVAL_HOLDOUT_WINDOWS=256,
EVAL_RETENTION_N=24) and each draw is the arm's: 'planned' (k0 and S) and 'replay' at 0.27 (S_replay).
Run it in place, by its path, from any directory but the checkout's root (it finds src/ two folders up)."""
import bisect
import hashlib
import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or ".") != ROOT]
sys.path.insert(0, os.path.join(ROOT, "src"))
import torch                                                        # noqa: E402
from spine.assemble import build as _build                         # noqa: E402
from spine import derive, lever as _lever, rng, units as U          # noqa: E402
from data import api as data_api                                   # noqa: E402
from eval import api as eval_api                                   # noqa: E402
from opt import api as opt_api                                     # noqa: E402
from tok import api as tok_api                                     # noqa: E402

seed, nbytes = int(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else "3780000"
PINS = dict(DATA_SOURCE="real", EVAL_RETENTION_EVERY="650", EVAL_HOLDOUT_WINDOWS="256", EVAL_RETENTION_N="24")


def plan_of(draw):
    env = dict(os.environ, RUN_SEED=str(seed), DATA_STREAM_BYTES=nbytes, RUN_DEVICE="cpu", OMP_NUM_THREADS="1",
               DATA_DIR=os.path.join(ROOT, "data"), DATA_DRAW=draw, **PINS)
    if draw == "replay":
        env["DATA_REPLAY_SHARE"] = "0.27"
    # TWO ASSEMBLIES IN ONE PROCESS, one per draw: the assembly latches after its first build (a run builds once),
    # so this replay reopens it before each, as the tests do.
    _lever._reopen_assembly()
    rng.reset_issued()
    configs, _, _ = _build(environ=env)
    run, lm, data, tok = configs["RUN"], configs["LM"], configs["DATA"], configs["TOK"]
    areas = data_api.open_areas(data, seed=int(run.seed))
    vocab = tok_api.build_vocabulary(tok, area_heads=areas.bodies, seed=int(run.seed), soft_cap=None)
    plan = data_api.data_plan(data, areas, epochs=int(run.epochs), win_tokens=int(lm.ctx),
                              bytes_per_token=float(vocab.bytes_per_token))
    stream = data_api.draw_stream(data, areas, plan, epoch=0, seed=int(run.seed))
    seg = tok_api.tokenize(tok, vocab, stream.bytes, stream.labels, regularize=True, seed=int(run.seed))
    return configs, areas, vocab, plan, stream, seg


t0 = time.time()
out = {d: plan_of(d) for d in ("planned", "replay")}
configs, areas, vocab, plan, stream, seg = out["planned"]
lm, ev = configs["LM"], configs["EVAL"]
ctx = int(lm.ctx)
nwin = len(seg.ids) // ctx
bp = list(seg.byte_pos)
pw = [(bisect.bisect_left(bp, b) - bisect.bisect_left(bp, a)) // ctx for a, b in plan.phase_bounds]
print(f"seed {seed}, DATA_SOURCE=real, DATA_STREAM_BYTES {nbytes} ({time.time() - t0:.0f}s)")
print(f"  build vocabulary: {vocab.size()} ids, {vocab.bytes_per_token:.3f} bytes/token; the epoch: {len(seg.ids):,} ids, "
      f"{nwin:,} windows ({len(stream.bytes) / max(1, nwin):.0f} B/window)")
print(f"  phases: schedule {plan.schedule}; windows at the build vocabulary {pw}; the shortest / 5 = {min(pw) / 5:.0f} "
      f"(§8 0.4: the cap EVAL_RETENTION_EVERY may not pass)")
print("  bodies: " + ", ".join(f"{a} {len(b):,}" for a, b in dict(areas.bodies).items())
      + "; held-out blocks: " + ", ".join(f"{a} {len(b):,}" for a, b in dict(areas.holdout).items()) + " B")
# EACH HALF'S WINDOWS, AS THE ROOT PINS THEM: windows of LM.ctx + 1 bytes behind the SIG width's routing prefix.
P = int(derive.signature_width_bytes(ctx, float(vocab.bytes_per_token)))
ps = eval_api.pin_holdout(ev, blocks=areas.holdout, seed=seed, window_bytes=ctx + 1, prefix_bytes=P)
print(f"  the probe at EVAL_HOLDOUT_WINDOWS 256 (windows of {ctx + 1} B behind a {P}-B prefix): "
      + ", ".join(f"{a} {len(h['control'])}/{len(h['report'])}" for a, h in sorted(ps.items.items()))
      + " windows pinned (control/report); shortfall "
      + ", ".join(f"{a} {sum(s.values())}" for a, s in sorted(ps.shortfall.items())))
print("  exposure: " + ", ".join(f"{a} {x:.2f}" for a, x in sorted(plan.exposure.items(), key=lambda kv: kv[0])))
for g in plan.gates:
    print(f"    Gate {g.name}: {'FIRED' if g.fired else 'armed, did not fire' if g.reachable else 'unreachable'} "
          f"({g.value} vs {g.threshold})")

# THE DRAW PAIR: phase 1's bytes, the first byte the two streams part at, each epoch's windows, and the rate OPT
# prices each at -- its warmup min(OPT_LR_WARMUP, run_steps // 10) and its cosine over the epoch's steps.
rows = {}
for d, (cf, ar, vc, pl, st, sg) in out.items():
    b1 = pl.phase_bounds[0][1]
    n = len(sg.ids) // int(cf["LM"].ctx)
    o = opt_api.build(cf["OPT"], param_groups={"base": [torch.nn.Parameter(torch.zeros(1))], "encoder": []},
                      run_windows=U.Windows(n))
    rows[d] = (st.bytes, b1, n, o, cf["OPT"])
    print(f"  DATA_DRAW={d}: epoch windows {n:,}; phase 1 = bytes [0, {b1:,}), sha256 "
          f"{hashlib.sha256(bytes(st.bytes[:b1])).hexdigest()[:16]}; warmup {int(o.horizon.warmup)} steps over "
          f"{int(o.horizon.run_steps):,}; each phase's bytes by area "
          + " | ".join(" ".join(f"{ar.names[i]} {b:,}" for i, b in ph) for ph in pl.shares))
(ba, b1, na, oa, ca), (bb, _, nb, ob, cb) = rows["planned"], rows["replay"]
first = next((i for i in range(min(len(ba), len(bb))) if ba[i] != bb[i]), None)
lr = [(s, opt_api.lr_at(ca, oa, U.Steps(s)), opt_api.lr_at(cb, ob, U.Steps(s))) for s in range(1, min(na, nb) + 1)]
part = next((s for s, x, y in lr if x != y), None)
print(f"  the two streams first part at byte {first:,} of {len(ba):,} (phase 1 ends at {b1:,}); OPT's rate first differs "
      f"at optimizer step {part} (planned {lr[part - 1][1]!r}, replay {lr[part - 1][2]!r}), "
      f"the warmup's last step {int(oa.horizon.warmup)} at {lr[int(oa.horizon.warmup) - 1][1]!r} on both; at step 5000 "
      f"{lr[4999][1]!r} and {lr[4999][2]!r}")
