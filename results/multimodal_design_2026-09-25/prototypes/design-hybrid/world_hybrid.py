"""The continuous half of the hybrid: WORLD predicts the FROZEN codec's pre-quantisation latent
(64-d, 50 Hz) instead of a self-learned 32-d latent of LM.embed. Compares today's WORLD predictor
shape (memoryless, per-position, residual-linear) with a temporal (causal GRU) one and a
caption-conditioned one; decodes forecasts through the frozen codec and scores them with the probe.
Usage: world_hybrid.py STEPS OUT.json"""
import os, sys, time, json, math
os.environ.setdefault("OMP_NUM_THREADS", "1"); os.environ.setdefault("MKL_NUM_THREADS", "1")
import torch, torch.nn as nn, torch.nn.functional as F
torch.set_num_threads(1)
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import synth as S
import importlib; TC = importlib.import_module(os.environ.get("HYB_CODEC_MOD", "spec_codec"))
import codec_lib as C

HS = (1, 5)  # horizons in codec FRAMES (20 ms, 100 ms)


class Persist(nn.Module):
    def forward(self, z, cap=None):
        return {h: z for h in HS}


class LinRes(nn.Module):          # today's WORLD predictor shape: z + z @ P, per position, no history
    def __init__(self, d):
        super().__init__(); self.P = nn.ParameterDict({str(h): nn.Parameter(torch.zeros(d, d)) for h in HS})
    def forward(self, z, cap=None):
        return {h: z + z @ self.P[str(h)] for h in HS}


class MLPRes(nn.Module):          # memoryless but nonlinear (WORLD's encoder class applied per position)
    def __init__(self, d, hid=128):
        super().__init__(); self.f = nn.ModuleDict({str(h): nn.Sequential(nn.Linear(d, hid), nn.Tanh(), nn.Linear(hid, d)) for h in HS})
    def forward(self, z, cap=None):
        return {h: z + self.f[str(h)](z) for h in HS}


class GRUWorld(nn.Module):        # temporal WORLD: causal context over the latent history (+ optional caption)
    def __init__(self, d, hid=128, cond=False):
        super().__init__()
        self.cond = cond; self.rnn = nn.GRU(d, hid, batch_first=True)
        self.out = nn.ModuleDict({str(h): nn.Linear(hid, d) for h in HS})
        if cond:
            self.cemb = nn.Embedding(256, hid); self.cproj = nn.Linear(hid, hid)
    def h0(self, cap):
        e = self.cemb(cap).mean(1)
        return torch.tanh(self.cproj(e)).unsqueeze(0)
    def forward(self, z, cap=None, h0=None):
        if self.cond and h0 is None:
            h0 = self.h0(cap)
        o, _ = self.rnn(z, h0)
        return {h: z + self.out[str(h)](o) for h in HS}


def caps_tensor(ps):
    cs = [list(S.caption(p).encode()) for p in ps]; n = max(map(len, cs))
    return torch.tensor([c + [32] * (n - len(c)) for c in cs])


def rel_mse(model, z, cap):
    with torch.no_grad():
        pr = model(z, cap); out = {}
        for h in HS:
            e = (pr[h][:, :-h] - z[:, h:]).pow(2).mean().item()
            e0 = (z[:, :-h] - z[:, h:]).pow(2).mean().item()
            out[f"h{h}"] = round(e / e0, 4)
    return out


def decode_latents(codec, zs, mu, sd):
    z = (zs * sd + mu).transpose(1, 2)
    zq, _, _ = codec.q(z)
    y = codec.dec(zq)
    n = zs.shape[1] * 160
    return F.pad(y, (0, max(0, n - y.shape[-1])))[..., :n]


def score(wavs, ps):
    res = {"train_combos": [], "heldout_combos": []}
    for i, p in enumerate(ps):
        res["heldout_combos" if p in S.HELDOUT_COMBOS else "train_combos"].append(S.attr_acc(S.probe(wavs[i, 0]), p))
    agg = lambda ds: {k: round(sum(d[k] for d in ds) / len(ds), 3) for k in ds[0]} | {"n": len(ds)}
    return {k: agg(v) for k, v in res.items()}


def main():
    steps, out = int(sys.argv[1]), sys.argv[2]
    D = torch.load(os.path.join(HERE, os.environ.get("HYB_CORPUS", "corpus.pt")))
    codec = TC.make_codec(); codec.load_state_dict(torch.load(os.path.join(HERE, os.environ.get("HYB_CODEC", "codec.pt")))); codec.eval()
    for p in codec.parameters():
        p.requires_grad_(False)
    trz, evz = D["trz"], D["evz"]
    mu = trz.mean((0, 1)); sd = trz.std((0, 1)) + 1e-5
    trn, evn = (trz - mu) / sd, (evz - mu) / sd
    trcap, evcap = caps_tensor(D["tr_p"]), caps_tensor(D["ev_p"])
    d = trz.shape[-1]
    models = dict(persistence=Persist(), linres_memoryless=LinRes(d), mlp_memoryless=MLPRes(d),
                  gru_temporal=GRUWorld(d), gru_temporal_caption=GRUWorld(d, cond=True))
    rec = dict(latent_dim=d, frames_per_s=50, steps=steps, horizons_frames=list(HS))
    g = torch.Generator().manual_seed(4)
    for name, m in models.items():
        t0 = time.time()
        ps = list(m.parameters())
        if ps:
            torch.manual_seed(0)
            opt = torch.optim.Adam(ps, lr=2e-3)
            for s in range(steps):
                idx = torch.randint(0, trn.shape[0], (32,), generator=g)
                z = trn[idx]; pr = m(z, trcap[idx])
                loss = sum((pr[h][:, :-h] - z[:, h:]).pow(2).mean() for h in HS)
                opt.zero_grad(); loss.backward(); opt.step()
        r = dict(train_s=round(time.time() - t0, 1), params=sum(p.numel() for p in ps),
                 rel_mse_vs_persistence=rel_mse(m, evn, evcap))
        # teacher-forced 1-frame forecast, decoded through the frozen codec
        with torch.no_grad():
            pr = m(evn, evcap)[1]
            zf = torch.cat([evn[:, :1], pr[:, :-1]], 1)
            wav = decode_latents(codec, zf, mu, sd)
            X = D["ev_x"].unsqueeze(1)
            r["tf_h1_decoded_mel"] = round(C.mel_dist(X, wav).item(), 4)
            r["tf_h1_decoded_probe"] = score(wav, D["ev_p"])
        rec[name] = r
        print(name, json.dumps(r), flush=True)
    # ---- open-loop generation through WORLD + codec decoder (the continuous generation path)
    with torch.no_grad():
        C.SR[0] = S.SR
        X = D["ev_x"].unsqueeze(1)
        rec["codec_recon_mel"] = round(C.mel_dist(X, decode_latents(codec, evn, mu, sd)).item(), 4)
        for name in ("gru_temporal", "gru_temporal_caption"):
            m = models[name]
            for prompt in (10, 0):
                if prompt == 0 and name == "gru_temporal":
                    continue
                B = evn.shape[0]
                h = m.h0(evcap) if m.cond else None
                zs = [evn[:, t:t + 1] for t in range(prompt)] or [torch.zeros(B, 1, d)]
                o, h = m.rnn(torch.cat(zs, 1), h)
                cur = zs[-1][:, -1:] + m.out["1"](o[:, -1:])
                seq = list(zs) + [cur]
                while sum(s.shape[1] for s in seq) < 50:
                    o, h = m.rnn(cur, h); cur = cur + m.out["1"](o); seq.append(cur)
                zg = torch.cat(seq, 1)[:, :50]
                wav = decode_latents(codec, zg, mu, sd)
                rec[f"rollout_{name}_prompt{prompt}f"] = dict(probe=score(wav, D["ev_p"]),
                                                             mel_vs_truth=round(C.mel_dist(X, wav).item(), 4))
                print(f"rollout {name} prompt{prompt}", json.dumps(rec[f"rollout_{name}_prompt{prompt}f"]), flush=True)
    json.dump(rec, open(out, "w"), indent=1)


if __name__ == "__main__":
    main()
