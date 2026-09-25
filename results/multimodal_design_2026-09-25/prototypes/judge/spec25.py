"""A spectral FSQ codec learned from scratch: STFT log-magnitude frames (hop 160 = 50 Hz at 8 kHz)
-> conv encoder -> FSQ 8,5,5,5 (+ marginal-entropy bonus) -> conv decoder -> log-magnitude ->
Griffin-Lim (a fixed algorithm, no learned or pretrained weights) -> waveform.
Same interface as codec_lib.Codec: enc(x)->(B,64,T); q(z)->(zq, codes, aux); dec(zq)->(B,1,n).
Usage: spec_codec.py MINUTES OUT.pt"""
import os, sys, time, json, math
os.environ.setdefault("OMP_NUM_THREADS", "1"); os.environ.setdefault("MKL_NUM_THREADS", "1")
import torch, torch.nn as nn, torch.nn.functional as F
torch.set_num_threads(1)
HERE = "/tmp/claude-0/-home-user-LLM-Test/e880caf7-1208-58de-93fd-49c41549bf70/scratchpad/mm/design-hybrid"; sys.path.insert(0, HERE)
import codec_lib as C
import synth as S

C.SR[0] = S.SR; C.PRENORM[0] = True; C.FSQ_ENT[0] = 1.0
NFFT, HOP = 512, 160
NB = NFFT // 2 + 1
WIN = torch.hann_window(NFFT)
GL_ITERS = 32


def logmag(x):  # x (B, n) -> (B, NB, T) with T = n // HOP
    X = torch.stft(x, NFFT, HOP, window=WIN, return_complex=True)[..., : x.shape[-1] // HOP]
    return torch.log(X.abs() + 1e-4)


def griffin_lim(mag, n, iters=GL_ITERS, seed=0):
    g = torch.Generator().manual_seed(seed)
    mag = F.pad(mag, (0, 1))  # restore the dropped last frame
    ang = torch.rand(mag.shape, generator=g) * 2 * math.pi
    X = mag * torch.exp(1j * ang)
    for _ in range(iters):
        y = torch.istft(X, NFFT, HOP, window=WIN, length=n)
        Xr = torch.stft(y, NFFT, HOP, window=WIN, return_complex=True)
        X = mag * torch.exp(1j * torch.angle(Xr))
    return torch.istft(X, NFFT, HOP, window=WIN, length=n)


class SpecCodec(nn.Module):
    def __init__(self, D=64, H=256):
        super().__init__()
        self.enc_net = nn.Sequential(nn.Conv1d(NB, H, 3, padding=1), nn.ELU(), nn.Conv1d(H, H, 3, padding=1), nn.ELU(),
                                     nn.Conv1d(H, H, 4, stride=2, padding=1), nn.ELU(), nn.Conv1d(H, D, 1))
        self.dec_net = nn.Sequential(nn.ConvTranspose1d(D, H, 4, stride=2, padding=1), nn.ELU(), nn.Conv1d(H, H, 3, padding=1), nn.ELU(), nn.Conv1d(H, H, 3, padding=1), nn.ELU(),
                                     nn.Conv1d(H, NB, 1))
        self.q = C.FSQ(D, [8, 5, 5, 5])
        self.mu, self.sd = -4.0, 3.0
    def enc(self, x):  # x (B,1,n)
        return self.enc_net((logmag(x[:, 0]) - self.mu) / self.sd)
    def dec_logmag(self, zq):
        return self.dec_net(zq) * self.sd + self.mu
    def dec(self, zq):
        lm = self.dec_logmag(zq)
        mag = (lm.exp() - 1e-4).clamp_min(0)
        return griffin_lim(mag, zq.shape[-1] * 2 * HOP).unsqueeze(1)
    def forward(self, x, nq=None):
        z = self.enc(x); zq, codes, aux = self.q(z)
        return self.dec(zq), codes, aux, z.shape[-1]


def make_codec():
    torch.manual_seed(0)
    return SpecCodec()


def main():
    import train_codec as TC
    minutes = float(sys.argv[1]); out = sys.argv[2]
    m = make_codec(); nparams = sum(p.numel() for p in m.parameters())
    opt = torch.optim.AdamW(m.parameters(), lr=1e-3, betas=(0.8, 0.99))
    g = torch.Generator().manual_seed(1); n = S.SR // 2
    t0 = time.time(); step = 0; budget = minutes * 60; log = []
    while time.time() - t0 < budget:
        x = TC.train_batch(g, 16, n); m.train()
        target = logmag(x[:, 0])
        z = m.enc(x); zq, codes, aux = m.q(z)
        pred = m.dec_logmag(zq); target = target[..., :pred.shape[-1]]; pred = pred[..., :target.shape[-1]]
        loss = F.l1_loss(pred, target) + 2.0 * F.l1_loss(pred.exp(), target.exp()) + aux
        opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(m.parameters(), 1.0); opt.step()
        step += 1
        for gp in opt.param_groups:
            gp["lr"] = 1e-3 * min(1.0, step / 100) * max(0.05, 1 - (time.time() - t0) / budget)
        if step % 200 == 0:
            log.append((round(time.time() - t0), step, round(loss.item(), 3), int(torch.unique(codes).numel())))
            print(log[-1], flush=True)
    torch.save(m.state_dict(), out)
    m.eval(); ge = torch.Generator().manual_seed(999)
    ps, xs = [], []
    for p in S.all_combos():
        for _ in range(4):
            ps.append(p); xs.append(S.render(p, ge))
    X = torch.stack(xs).unsqueeze(1)
    with torch.no_grad():
        tt = time.time(); z = m.enc(X); zq, codes, _ = m.q(z); t_enc = time.time() - tt
        tt = time.time(); Y = m.dec(zq); t_dec = time.time() - tt
        # oracle: Griffin-Lim on the TRUE magnitude (the ceiling this decoder design can reach)
        Yo = griffin_lim(torch.stft(X[:, 0], NFFT, HOP, window=WIN, return_complex=True)[..., :50].abs(), S.SR).unsqueeze(1)
    acc = {}
    for name, W in (("true", X), ("griffinlim_oracle", Yo), ("codec_recon", Y)):
        a = {k: 0 for k in ("kind", "band", "timbre", "count", "exact")}
        for i, p in enumerate(ps):
            for k, v in S.attr_acc(S.probe(W[i, 0]), p).items(): a[k] += v
        acc[name] = {k: round(v / len(ps), 3) for k, v in a.items()}
    c = codes[..., 0].reshape(-1); h = torch.bincount(c, minlength=1000).float(); pr = h / h.sum()
    ent = -(pr[pr > 0] * pr[pr > 0].log2()).sum().item()
    with torch.no_grad():
        lm_err = F.l1_loss(m.dec_logmag(zq), logmag(X[:, 0])).item()
    res = dict(params=nparams, steps=step, train_s=round(time.time() - t0), frames_per_s=25,
               logmag_l1_heldout=round(lm_err, 4),
               mel_heldout=round(C.mel_dist(X, Y).item(), 4), mel_griffinlim_oracle=round(C.mel_dist(X, Yo).item(), 4),
               mel_silence=round(C.mel_dist(X, 1e-4 * torch.randn_like(X)).item(), 4),
               rms_true=round(X.pow(2).mean().sqrt().item(), 4), rms_recon=round(Y.pow(2).mean().sqrt().item(), 4),
               codes_used=int((h > 0).sum()), code_entropy_bits=round(ent, 3), perplexity=round(2 ** ent, 1),
               encode_rtf=round(t_enc / len(ps), 5), decode_rtf_gl32=round(t_dec / len(ps), 4),
               probe_acc=acc, log=log[-4:])
    print(json.dumps(res, indent=1)); json.dump(res, open(out + ".json", "w"), indent=1)


if __name__ == "__main__":
    main()
