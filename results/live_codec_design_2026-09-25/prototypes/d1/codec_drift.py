"""Codec-only drift/plasticity frontier (no LM): continue training the codec-phase checkpoint on
area A for N1 steps, then on area B (+ half-batch rehearsal of A) for N2 steps, under different
(learning rate, anchor scope) settings. Reports code flips on the fixed probe sets (vs the start and per
step), mel distance and probe-exact on reconstructions for both areas.
Usage: python codec_drift.py STRIDE N1 N2 OUT.json"""
import os, sys, json, time, copy, math
os.environ.setdefault("OMP_NUM_THREADS", "1")
import torch, torch.nn as nn
torch.set_num_threads(1)
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import synth as S, melody as M, codec as K, codec_lib as C
from eval_codec import sets

CONFIGS = [
    dict(name="lr3e-4_noanchor", lr=3e-4, rewarm=None, anchor="none"),
    dict(name="lr3e-4_anchor_old", lr=3e-4, rewarm=None, anchor="old"),
    dict(name="lr3e-4_anchor_all", lr=3e-4, rewarm=None, anchor="all"),
    dict(name="lr5e-5_noanchor", lr=5e-5, rewarm=None, anchor="none"),
    dict(name="lr5e-5_anchor_old", lr=5e-5, rewarm=None, anchor="old"),
    dict(name="floor5e-5_rewarm3e-4onB_anchor_old", lr=5e-5, rewarm=3e-4, anchor="old"),
    dict(name="lr5e-5_anchor_all", lr=5e-5, rewarm=None, anchor="all"),
    dict(name="lr5e-5_anchor_all_w10", lr=5e-5, rewarm=None, anchor="all", w=10.0),
    dict(name="lr3e-4_anchor_all_w10", lr=3e-4, rewarm=None, anchor="all", w=10.0),
    dict(name="floor5e-5_rewarm3e-4onB_anchor_all_w10", lr=5e-5, rewarm=3e-4, anchor="all", w=10.0),
]


def crops(g, area_list, n=S.SR // 2):
    xs = []
    for ar in area_list:
        mod = S if ar == "A" else M
        _, x = mod.sample(g)
        s = int((S.SR - n) * torch.rand(1, generator=g).item()); xs.append(x[s:s + n])
    return torch.stack(xs).unsqueeze(1)


def score(m, ev):
    out = {}
    for area, (mod, ps, X) in ev.items():
        codes, _ = K.encode(m, X); Y = K.decode_codes(m, codes)
        ex = sum(mod.attr_acc(mod.probe(Y[i]), ps[i])["exact"] for i in range(len(ps))) / len(ps)
        out[area] = dict(mel=round(C.mel_dist(X.unsqueeze(1), Y.unsqueeze(1)).item(), 4), recx=round(ex, 3),
                         codes_used=int(torch.unique(codes).numel()))
    return out


def main():
    stride, n1, n2, outp = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
    only = sys.argv[5].split(",") if len(sys.argv) > 5 else None
    ev = sets(); ck = torch.load(os.path.join(HERE, "ck", f"codec{50 if stride == 1 else 25}.pt"))
    res = {}
    for cfg in CONFIGS:
        if only and cfg["name"] not in only:
            continue
        t0 = time.time()
        m = K.make_codec(stride); m.load_state_dict(ck["model"])
        opt = torch.optim.AdamW(m.parameters(), lr=cfg["lr"], betas=(0.8, 0.99))
        # DEEP COPY: Optimizer.load_state_dict keeps the SAME moment tensors when dtype/device match, so a second
        # config in one process would otherwise start from the first config's final Adam moments (a bug in the
        # first version of this script: every config after the first in a process was contaminated).
        opt.load_state_dict(copy.deepcopy(ck["opt"]))
        for gp in opt.param_groups:
            gp["lr"] = cfg["lr"]
        snap = copy.deepcopy(m).eval()
        c0 = {a: K.encode(m, ev[a][2])[0] for a in ev}
        g = torch.Generator().manual_seed(42)
        traj = []
        prev = c0
        for step in range(1, n1 + n2 + 1):
            inB = step > n1
            if cfg["rewarm"] and inB:
                k = step - n1
                lr = cfg["lr"] + (cfg["rewarm"] - cfg["lr"]) * 0.5 * (1 + math.cos(math.pi * min(1.0, k / n2)))
                for gp in opt.param_groups:
                    gp["lr"] = lr
            areas = ["B" if (inB and i % 2 == 0) else "A" for i in range(16)]
            x = crops(g, areas)
            cur = "B" if inB else "A"
            if cfg["anchor"] == "all":
                am = torch.ones(16, dtype=torch.bool)
            elif cfg["anchor"] == "old":
                am = torch.tensor([a != cur for a in areas])
            else:
                am = torch.zeros(16, dtype=torch.bool)
            anc = K.encode(snap, x[:, 0])[0] if am.any() else None
            m.train(); loss, _, _ = K.codec_loss(m, x, anc, am, cfg.get("w", 1.0) if cfg["anchor"] != "none" else 0.0)
            opt.zero_grad(); loss.backward(); nn.utils.clip_grad_norm_(m.parameters(), 1.0); opt.step(); m.eval()
            if step % 50 == 0:
                cur_c = {a: K.encode(m, ev[a][2])[0] for a in ev}
                traj.append(dict(step=step, flipA_vs_start=round((cur_c["A"] != c0["A"]).float().mean().item(), 4),
                                 flipB_vs_start=round((cur_c["B"] != c0["B"]).float().mean().item(), 4),
                                 flipA_per_50=round((cur_c["A"] != prev["A"]).float().mean().item(), 4),
                                 flipB_per_50=round((cur_c["B"] != prev["B"]).float().mean().item(), 4)))
                prev = cur_c
                snap = copy.deepcopy(m).eval()  # the tokenizing snapshot refreshes every 50 codec steps
            if step == n1:
                after1 = score(m, ev)
        res[cfg["name"]] = dict(cfg=cfg, start=score(K.make_codec(stride).eval() if False else _load(stride, ck), ev),
                                after_A=after1, after_B=score(m, ev), traj=traj, s=round(time.time() - t0, 1))
        print(cfg["name"], json.dumps({k: v for k, v in res[cfg["name"]].items() if k != "traj"}), flush=True)
        print("  traj", res[cfg["name"]]["traj"], flush=True)
        json.dump(res, open(os.path.join(HERE, outp), "w"), indent=1)


def _load(stride, ck):
    m = K.make_codec(stride); m.load_state_dict(ck["model"]); return m.eval()


if __name__ == "__main__":
    main()
