"""Stage-1 of the hybrid: learn the audio codec from scratch (FSQ 8,5,5,5 + marginal-entropy bonus,
50 Hz at 8 kHz), freeze it, and score it with the analytic probe. Usage: train_codec.py MINUTES OUT.pt"""
import os, sys, time, json, math
os.environ.setdefault("OMP_NUM_THREADS", "1"); os.environ.setdefault("MKL_NUM_THREADS", "1")
import torch, torch.nn.functional as F
torch.set_num_threads(1)
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import codec_lib as C
import synth as S

C.SR[0] = S.SR; C.PRENORM[0] = True; C.FSQ_ENT[0] = 1.0


def make_codec():
    torch.manual_seed(0)
    return C.Codec(160, 16, 64, C.FSQ(64, [8, 5, 5, 5]))


def train_batch(g, bs, n):
    xs = []
    for i in range(bs):
        if i % 2 == 0:
            _, x = S.sample(g)
            s = int((S.SR - n) * torch.rand(1, generator=g).item()); xs.append(x[s:s + n])
        else:
            xs.append(C.clip(n, S.SR, g))
    return torch.stack(xs).unsqueeze(1)


def main():
    minutes = float(sys.argv[1]); out = sys.argv[2]
    m = make_codec(); nparams = sum(p.numel() for p in m.parameters())
    opt = torch.optim.AdamW(m.parameters(), lr=1e-3, betas=(0.8, 0.99))
    g = torch.Generator().manual_seed(1); n = S.SR // 2
    t0 = time.time(); step = 0; budget = minutes * 60; log = []
    while time.time() - t0 < budget:
        x = train_batch(g, 8, n); m.train()
        y, codes, aux, T = m(x)
        loss = C.mel_dist(x, y) + C.stft_loss(x, y) + F.l1_loss(y, x) + aux
        opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(m.parameters(), 1.0); opt.step()
        step += 1
        for gp in opt.param_groups:
            gp["lr"] = 1e-3 * min(1.0, step / 200) * max(0.05, 1 - (time.time() - t0) / budget)
        if step % 100 == 0:
            log.append((round(time.time() - t0), step, round(loss.item(), 3), int(torch.unique(codes).numel())))
            print(log[-1], flush=True)
    torch.save(m.state_dict(), out)
    # ---- evaluation on held-out paired clips (disjoint seed) incl. held-out combos
    m.eval(); ge = torch.Generator().manual_seed(999)
    ps, xs = [], []
    for p in S.all_combos():
        for _ in range(4):
            ps.append(p); xs.append(S.render(p, ge))
    X = torch.stack(xs).unsqueeze(1)
    with torch.no_grad():
        tt = time.time(); Y, codes, _, T = m(X); dt = time.time() - tt
    acc_true = {k: 0 for k in ("kind", "band", "timbre", "count", "exact")}
    acc_rec = dict(acc_true)
    for i, p in enumerate(ps):
        for k, v in S.attr_acc(S.probe(X[i, 0]), p).items(): acc_true[k] += v
        for k, v in S.attr_acc(S.probe(Y[i, 0]), p).items(): acc_rec[k] += v
    c = codes[..., 0].reshape(-1); h = torch.bincount(c, minlength=1000).float(); pr = h / h.sum()
    ent = -(pr[pr > 0] * pr[pr > 0].log2()).sum().item()
    res = dict(params=nparams, steps=step, train_s=round(time.time() - t0), frames_per_s=T / 1.0,
               mel_heldout=round(C.mel_dist(X, Y).item(), 4), mel_silence=round(C.mel_dist(X, 1e-4 * torch.randn_like(X)).item(), 4),
               codes_used=int((h > 0).sum()), code_entropy_bits=round(ent, 3), perplexity=round(2 ** ent, 1),
               rtf_encode_decode=round(dt / len(ps), 4),
               probe_acc_true={k: round(v / len(ps), 3) for k, v in acc_true.items()},
               probe_acc_codec_recon={k: round(v / len(ps), 3) for k, v in acc_rec.items()}, log=log[-5:])
    print(json.dumps(res, indent=1)); json.dump(res, open(out + ".json", "w"), indent=1)


if __name__ == "__main__":
    main()
