"""Where do code flips go? Train the spec25 student live for N codec steps from the codec-phase checkpoint,
EMA teacher at several decays; compare teacher codes on the fixed probe set before/after: fraction flipped,
and for flipped codes the lattice distance (number of FSQ dims changed, max |step| on a dim).
Usage: python3 flipdist.py SEED N OUT.json"""
import os, sys, json, time
os.environ.setdefault("OMP_NUM_THREADS", "1")
import torch, torch.nn as nn
torch.set_num_threads(1)
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import d3lib as D

seed, N, out = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
st = torch.load(os.path.join(HERE, "ck", f"spec25_s{seed}.pt"))
m = D.make_codec("spec25", seed); m.load_state_dict(st["student"]); m.eval()
opt = torch.optim.AdamW(m.parameters(), lr=3e-4, betas=(0.8, 0.99)); opt.load_state_dict(st["opt"])
for gp in opt.param_groups: gp["lr"] = 3e-4
decs = [0.0, 0.995, 0.999]
T = {d: D.Teacher(m, d) for d in decs}
pr = {ar: D.eval_set(ar, per, sd) for ar, per, sd in (("tones", 1, 777), ("melody", 2, 778))}
X = torch.cat([pr["tones"][1], pr["melody"][1]])
def codes(t):
    with torch.no_grad():
        ids, _, _ = t.m.encode(X)
    return torch.tensor(ids)
c0 = codes(T[1.0] if 1.0 in T else T[0.0])
g = torch.Generator().manual_seed(900 + seed); res = {}
checks = sorted(set([N // 4, N // 2, N]))
t0 = time.time()
for step in range(1, N + 1):
    mix = [("tones", 1.0)] if step <= N // 2 else [("melody", 1.0), ("tones", 1.0)]
    m.train(); xb = D.media_batch(g, mix, 16); loss, _ = m.train_loss(xb, g)
    opt.zero_grad(); loss.backward(); nn.utils.clip_grad_norm_(m.parameters(), 1.0); opt.step(); m.eval()
    for t in T.values(): t.update(m)
    if step in checks:
        for d, t in T.items():
            c1 = codes(t); fl = c1 != c0
            q = m.q
            a = D.codes_to_lattice(c0[fl], q) * (q.levels // 2).float(); b = D.codes_to_lattice(c1[fl], q) * (q.levels // 2).float()
            diff = (a - b).abs().round().long()
            ndim = (diff > 0).sum(-1); mx = diff.max(-1).values
            res[f"{d}@{step}"] = dict(flip=round(fl.float().mean().item(), 4),
                                     ndims_changed={k: round((ndim == k).float().mean().item(), 3) for k in (1, 2, 3, 4)},
                                     max_step={k: round((mx == k).float().mean().item(), 3) for k in (1, 2, 3)},
                                     max_step_ge4=round((mx >= 4).float().mean().item(), 3),
                                     lm_windows_at_every2=2 * step)
            print(d, step, res[f"{d}@{step}"], round(time.time() - t0), flush=True)
json.dump(res, open(out, "w"), indent=1)
