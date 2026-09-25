"""Tiny learned-from-scratch audio codec on procedural audio (CPU, 1 thread).

Usage: python3 codec.py --quant fsq|rvq|none --sr 16000 --stride 320 --minutes 4 --out res.json
Reports reconstruction error (SNR, SI-SNR, multi-res STFT loss), codebook usage and tokens/s.
"""
import argparse, json, math, os, time
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
import torch, torch.nn as nn, torch.nn.functional as F
torch.set_num_threads(1)

# ---------------------------------------------------------------- procedural audio
def envelope(n, sr, g):
    a = int(sr * (0.005 + 0.05 * torch.rand(1, generator=g).item()))
    d = max(1, n - a)
    t = torch.arange(n, dtype=torch.float32)
    env = torch.where(t < a, t / max(a, 1), torch.exp(-(t - a) / d * (0.5 + 4 * torch.rand(1, generator=g).item())))
    return env

def tone(n, sr, g):
    f = 80 * 2 ** (5 * torch.rand(1, generator=g).item())  # 80..2560 Hz
    t = torch.arange(n) / sr
    return torch.sin(2 * math.pi * f * t + 6.28 * torch.rand(1, generator=g).item())

def chirp(n, sr, g):
    f0 = 100 * 2 ** (4 * torch.rand(1, generator=g).item()); f1 = 100 * 2 ** (4 * torch.rand(1, generator=g).item())
    t = torch.arange(n) / sr; T = n / sr
    if torch.rand(1, generator=g).item() < 0.5:  # linear
        ph = 2 * math.pi * (f0 * t + (f1 - f0) * t * t / (2 * T))
    else:  # exponential
        k = (f1 / f0) ** (1 / T)
        ph = 2 * math.pi * f0 * (k ** t - 1) / math.log(k) if abs(k - 1) > 1e-6 else 2 * math.pi * f0 * t
    return torch.sin(ph)

def harmonic(n, sr, g, f0=None, formants=None):
    f0 = f0 or 80 * 2 ** (2.5 * torch.rand(1, generator=g).item())
    t = torch.arange(n) / sr
    out = torch.zeros(n)
    vib = 1 + 0.01 * torch.sin(2 * math.pi * 5 * t)
    k = 1
    while k * f0 < min(sr / 2 - 200, 4000):
        f = k * f0
        if formants is None:
            amp = 1.0 / k
        else:  # vowel: Gaussian formant peaks on the harmonic amplitudes
            amp = sum(a * math.exp(-((f - fc) / bw) ** 2) for fc, bw, a in formants) + 0.02 / k
        out += amp * torch.sin(2 * math.pi * f * t * vib)
        k += 1
    return out / (out.abs().max() + 1e-6)

VOWELS = {  # rough F1,F2,F3 (Hz) from Peterson & Barney-type tables (unverified values, synthetic use only)
    "a": [(730, 90, 1.0), (1090, 110, 0.5), (2440, 160, 0.25)],
    "i": [(270, 60, 1.0), (2290, 150, 0.4), (3010, 200, 0.3)],
    "u": [(300, 60, 1.0), (870, 90, 0.5), (2240, 160, 0.2)],
    "e": [(530, 80, 1.0), (1840, 130, 0.45), (2480, 160, 0.25)],
    "o": [(570, 80, 1.0), (840, 90, 0.6), (2410, 160, 0.2)],
}

def syllables(n, sr, g):
    out = torch.zeros(n); pos = 0
    f0 = 90 + 150 * torch.rand(1, generator=g).item()
    keys = list(VOWELS)
    while pos < n:
        L = int(sr * (0.12 + 0.2 * torch.rand(1, generator=g).item())); L = min(L, n - pos)
        if torch.rand(1, generator=g).item() < 0.3:  # consonant-like noise burst
            b = min(int(0.03 * sr), L)
            out[pos:pos + b] += 0.3 * torch.randn(b, generator=g) * torch.linspace(1, 0, b)
        v = VOWELS[keys[int(torch.randint(len(keys), (1,), generator=g))]]
        seg = harmonic(L, sr, g, f0=f0 * (1 + 0.1 * torch.randn(1, generator=g).item()), formants=v)
        out[pos:pos + L] += seg * envelope(L, sr, g)
        pos += L + int(sr * 0.03 * torch.rand(1, generator=g).item())
    return out

def melody(n, sr, g):
    out = torch.zeros(n); pos = 0
    root = 48 + int(torch.randint(24, (1,), generator=g))
    scale = [0, 2, 4, 5, 7, 9, 11, 12]
    timbre = int(torch.randint(2, (1,), generator=g))
    while pos < n:
        L = min(int(sr * (0.1 + 0.25 * torch.rand(1, generator=g).item())), n - pos)
        midi = root + scale[int(torch.randint(len(scale), (1,), generator=g))]
        f = 440 * 2 ** ((midi - 69) / 12)
        seg = harmonic(L, sr, g, f0=f) if timbre else torch.sin(2 * math.pi * f * torch.arange(L) / sr)
        out[pos:pos + L] += seg * envelope(L, sr, g)
        pos += L
    return out

KINDS = [tone, chirp, harmonic, syllables, melody]

def clip(n, sr, g):
    x = torch.zeros(n)
    k = 1 + int(torch.randint(2, (1,), generator=g))  # 1-2 overlapping events
    for _ in range(k):
        fn = KINDS[int(torch.randint(len(KINDS), (1,), generator=g))]
        s = fn(n, sr, g)
        if fn in (tone, chirp, harmonic):
            s = s * envelope(n, sr, g)
        x += (0.2 + 0.8 * torch.rand(1, generator=g).item()) * s
    if torch.rand(1, generator=g).item() < 0.3:
        x += 0.01 * torch.randn(n, generator=g)
    return 0.9 * x / (x.abs().max() + 1e-6)

def batch(bs, n, sr, g):
    return torch.stack([clip(n, sr, g) for _ in range(bs)]).unsqueeze(1)

# ---------------------------------------------------------------- quantisers
class FSQ(nn.Module):
    """Finite Scalar Quantization (Mentzer et al. 2023): bound each dim, round, straight-through."""
    def __init__(self, dim, levels):
        super().__init__()
        self.levels = torch.tensor(levels)
        self.pin = nn.Conv1d(dim, len(levels), 1); self.pout = nn.Conv1d(len(levels), dim, 1)
        self.basis = torch.cumprod(torch.tensor([1] + levels[:-1]), 0)
        self.codebook_size = int(torch.prod(self.levels))
    def forward(self, z, nq=None):
        z = self.pin(z).transpose(1, 2)  # B T d
        L = self.levels.float(); half_l = (L - 1) * (1 + 1e-3) / 2
        offset = torch.where(self.levels % 2 == 0, 0.5, 0.0); shift = torch.atanh(offset / half_l)
        b = torch.tanh(z + shift) * half_l - offset
        q = b + (torch.round(b) - b).detach()
        hw = (self.levels // 2).float()
        codes = ((torch.round(b) + hw).long() * self.basis).sum(-1)  # B T
        zq = self.pout((q / hw).transpose(1, 2))
        return zq, codes.unsqueeze(-1), torch.zeros(())

class RVQ(nn.Module):
    """Residual VQ with EMA codebooks, factorised low-dim l2-normalised lookup (DAC-style),
    k-means-free init from data and dead-code restart (SoundStream/EnCodec practice), quantizer dropout."""
    def __init__(self, dim, nq, K, cdim=8, decay=0.99, dead=2.0):
        super().__init__()
        self.nq, self.K, self.cdim, self.decay, self.dead = nq, K, cdim, decay, dead
        self.pin = nn.ModuleList([nn.Conv1d(dim, cdim, 1) for _ in range(nq)])
        self.pout = nn.ModuleList([nn.Conv1d(cdim, dim, 1) for _ in range(nq)])
        self.register_buffer("cb", F.normalize(torch.randn(nq, K, cdim), dim=-1))
        self.register_buffer("cnt", torch.ones(nq, K))
        self.register_buffer("sums", self.cb.clone())
        self.register_buffer("inited", torch.zeros(()))
        self.codebook_size = K
    def forward(self, z, nq=None):
        nq = nq or self.nq
        res = z; out = torch.zeros_like(z); codes = []; commit = 0.0
        for i in range(nq):
            e = F.normalize(self.pin[i](res).transpose(1, 2), dim=-1)  # B T c
            flat = e.reshape(-1, self.cdim)
            if self.training and self.inited.item() == 0:
                idx0 = torch.randperm(flat.shape[0])[: self.K]
                self.cb[i, : len(idx0)] = flat[idx0].detach(); self.sums[i] = self.cb[i].clone()
            d = flat @ self.cb[i].t()
            idx = d.argmax(-1)
            q = self.cb[i][idx].view_as(e)
            if self.training:
                with torch.no_grad():
                    oh = F.one_hot(idx, self.K).float()
                    self.cnt[i].mul_(self.decay).add_(oh.sum(0), alpha=1 - self.decay)
                    self.sums[i].mul_(self.decay).add_(oh.t() @ flat.detach(), alpha=1 - self.decay)
                    self.cb[i] = F.normalize(self.sums[i] / self.cnt[i].clamp_min(1e-5).unsqueeze(1), dim=-1)
                    deadm = self.cnt[i] < self.dead * (1 - self.decay) * flat.shape[0] / self.K * 0.05
                    nd = int(deadm.sum())
                    if nd:
                        pick = flat[torch.randint(flat.shape[0], (nd,))].detach()
                        self.cb[i][deadm] = pick; self.sums[i][deadm] = pick; self.cnt[i][deadm] = 1.0
            commit = commit + F.mse_loss(e, q.detach())
            qst = e + (q - e).detach()
            y = self.pout[i](qst.transpose(1, 2))
            out = out + y; res = res - y.detach()
            codes.append(idx.view(e.shape[0], e.shape[1]))
        if self.training: self.inited.fill_(1)
        return out, torch.stack(codes, -1), commit

class NoQ(nn.Module):
    codebook_size = 0
    def forward(self, z, nq=None): return z, None, torch.zeros(())

# ---------------------------------------------------------------- model
def factor(stride):
    fs = []
    for f in (8, 5, 4, 2):
        while stride % f == 0 and stride > 1:
            fs.append(f); stride //= f
    assert stride == 1
    return sorted(fs)

class Snake(nn.Module):
    """Snake activation x + sin^2(a x)/a (Ziyin et al. 2020; used by DAC): periodic inductive bias."""
    def __init__(self, c):
        super().__init__(); self.a = nn.Parameter(torch.ones(1, c, 1))
    def forward(self, x): return x + (self.a + 1e-9).reciprocal() * torch.sin(self.a * x).pow(2)

ACT = ["elu"]
def act(c): return Snake(c) if ACT[0] == "snake" else nn.ELU()
def wn(m): return nn.utils.parametrizations.weight_norm(m) if ACT[0] == "snake" else m

class Res(nn.Module):
    def __init__(self, c, dil):
        super().__init__()
        self.c1 = wn(nn.Conv1d(c, c, 7, dilation=dil, padding=3 * dil)); self.c2 = wn(nn.Conv1d(c, c, 1))
        self.a1 = act(c); self.a2 = act(c)
    def forward(self, x): return x + self.c2(self.a2(self.c1(self.a1(x))))

class Codec(nn.Module):
    def __init__(self, stride, C, D, quant):
        super().__init__()
        fs = factor(stride); enc = [nn.Conv1d(1, C, 7, padding=3)]; c = C
        for f in fs:
            enc += [Res(c, 1), Res(c, 3), Res(c, 9), act(c), wn(nn.Conv1d(c, 2 * c, 2 * f, stride=f, padding=math.ceil(f / 2)))]; c *= 2
        enc += [act(c), nn.Conv1d(c, D, 3, padding=1)]
        self.enc = nn.Sequential(*enc)
        dec = [nn.Conv1d(D, c, 7, padding=3)]
        for f in reversed(fs):
            dec += [act(c), wn(nn.ConvTranspose1d(c, c // 2, 2 * f, stride=f, padding=math.ceil(f / 2))), Res(c // 2, 1), Res(c // 2, 3), Res(c // 2, 9)]; c //= 2
        dec += [act(c), nn.Conv1d(c, 1, 7, padding=3), nn.Tanh()]
        self.dec = nn.Sequential(*dec)
        self.q = quant
    def forward(self, x, nq=None):
        n = x.shape[-1]
        z = self.enc(x); zq, codes, commit = self.q(z, nq)
        y = self.dec(zq)
        y = F.pad(y, (0, max(0, n - y.shape[-1])))[..., :n]
        return y, codes, commit, z.shape[-1]

class Codec2(nn.Module):
    """Cheaper variant: a learned filterbank front end (kernel 2*s0, stride s0) so all residual
    blocks run at <= sr/s0 Hz instead of at the sample rate."""
    def __init__(self, stride, C, D, quant, s0=16):
        super().__init__()
        assert stride % s0 == 0
        fs = factor(stride // s0) if stride // s0 > 1 else []
        c = 4 * C
        enc = [nn.Conv1d(1, c, 2 * s0, stride=s0, padding=s0 // 2), Res(c, 1), Res(c, 3), Res(c, 9)]
        for f in fs:
            enc += [nn.ELU(), nn.Conv1d(c, 2 * c, 2 * f, stride=f, padding=math.ceil(f / 2)), Res(2 * c, 1), Res(2 * c, 3)]; c *= 2
        enc += [nn.ELU(), nn.Conv1d(c, D, 3, padding=1)]
        self.enc = nn.Sequential(*enc)
        dec = [nn.Conv1d(D, c, 7, padding=3), Res(c, 1), Res(c, 3)]
        for f in reversed(fs):
            dec += [nn.ELU(), nn.ConvTranspose1d(c, c // 2, 2 * f, stride=f, padding=math.ceil(f / 2)), Res(c // 2, 1), Res(c // 2, 3)]; c //= 2
        dec += [Res(c, 9), nn.ELU(), nn.ConvTranspose1d(c, 1, 2 * s0, stride=s0, padding=s0 // 2), nn.Tanh()]
        self.dec = nn.Sequential(*dec)
        self.q = quant
    forward = Codec.forward

class SpecCodec(nn.Module):
    """STFT-domain codec (Vocos/WavTokenizer-style iSTFT head): conv stack over STFT frames,
    power-law compressed complex spectrum in and out. hop = stride // 2, n_fft = 4 * hop."""
    def __init__(self, stride, C, D, quant, width=256, nres=3):
        super().__init__()
        self.hop = stride // 2; self.nfft = 4 * self.hop; nb = self.nfft // 2 + 1
        self.win = torch.hann_window(self.nfft)
        enc = [nn.Conv1d(2 * nb, width, 3, padding=1)] + [Res(width, d) for d in (1, 3, 9)[:nres]]
        enc += [act(width), nn.Conv1d(width, width, 4, stride=2, padding=1), Res(width, 1), Res(width, 3), act(width), nn.Conv1d(width, D, 3, padding=1)]
        self.enc_net = nn.Sequential(*enc)
        dec = [nn.Conv1d(D, width, 3, padding=1), Res(width, 1), Res(width, 3), act(width), nn.ConvTranspose1d(width, width, 4, stride=2, padding=1)]
        dec += [Res(width, d) for d in (1, 3, 9)[:nres]] + [act(width), nn.Conv1d(width, 2 * nb, 3, padding=1)]
        self.dec_net = nn.Sequential(*dec)
        self.q = quant
    def enc(self, x):
        X = torch.stft(x.squeeze(1), self.nfft, self.hop, window=self.win, return_complex=True)[..., :-1]
        mag = X.abs().clamp_min(1e-7); Z = X / mag * mag.pow(0.3)
        self._n = x.shape[-1]
        return self.enc_net(torch.cat([Z.real, Z.imag], 1))
    def dec(self, z):
        o = self.dec_net(z); nb = o.shape[1] // 2
        Z = torch.complex(o[:, :nb], o[:, nb:]); mag = Z.abs().clamp_min(1e-7)
        X = Z / mag * mag.pow(1 / 0.3)
        X = F.pad(X, (0, 1))
        y = torch.istft(X, self.nfft, self.hop, window=self.win, length=self._n)
        return y.unsqueeze(1)
    def forward(self, x, nq=None):
        z = self.enc(x); zq, codes, commit = self.q(z, nq)
        return self.dec(zq), codes, commit, z.shape[-1]

_MEL = {}
def melmat(n_fft, sr, n_mels):
    key = (n_fft, sr, n_mels)
    if key not in _MEL:
        hz2mel = lambda f: 2595 * math.log10(1 + f / 700)
        mel2hz = lambda m: 700 * (10 ** (m / 2595) - 1)
        pts = torch.tensor([mel2hz(m) for m in torch.linspace(0, hz2mel(sr / 2), n_mels + 2).tolist()])
        freqs = torch.linspace(0, sr / 2, n_fft // 2 + 1)
        fb = torch.zeros(n_mels, n_fft // 2 + 1)
        for i in range(n_mels):
            l, c, r = pts[i], pts[i + 1], pts[i + 2]
            fb[i] = torch.clamp(torch.minimum((freqs - l) / (c - l + 1e-9), (r - freqs) / (r - c + 1e-9)), min=0)
        _MEL[key] = fb
    return _MEL[key]

SR = [16000]
def mel_dist(x, y, sizes=((256, 32), (512, 64), (1024, 80)), per_item=False):
    """Multi-scale log10-mel L1 (DAC-style mel loss, eps 1e-5)."""
    tot = 0.0
    for s, nm in sizes:
        w = torch.hann_window(s); M = melmat(s, SR[0], nm)
        X = M @ torch.stft(x.squeeze(1), s, s // 4, window=w, return_complex=True).abs()
        Y = M @ torch.stft(y.squeeze(1), s, s // 4, window=w, return_complex=True).abs()
        d = (torch.log10(X.clamp_min(1e-5)) - torch.log10(Y.clamp_min(1e-5))).abs()
        tot = tot + (d.mean((1, 2)) if per_item else d.mean())
    return tot / len(sizes)

def stft_loss(x, y, sizes=(256, 512, 1024)):
    tot = 0.0
    for s in sizes:
        w = torch.hann_window(s)
        X = torch.stft(x.squeeze(1), s, s // 4, window=w, return_complex=True).abs()
        Y = torch.stft(y.squeeze(1), s, s // 4, window=w, return_complex=True).abs()
        tot = tot + (X - Y).norm() / (X.norm() + 1e-7) + F.l1_loss(torch.log(Y + 1e-5), torch.log(X + 1e-5))
    return tot / len(sizes)

def snr(x, y):
    return (10 * torch.log10(x.pow(2).sum(-1) / ((x - y).pow(2).sum(-1) + 1e-12))).mean().item()

def sisnr(x, y):
    x = x - x.mean(-1, keepdim=True); y = y - y.mean(-1, keepdim=True)
    a = (x * y).sum(-1, keepdim=True) / (x.pow(2).sum(-1, keepdim=True) + 1e-12)
    t = a * x
    return (10 * torch.log10(t.pow(2).sum(-1) / ((t - y).pow(2).sum(-1) + 1e-12))).mean().item()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quant", default="fsq"); ap.add_argument("--sr", type=int, default=16000)
    ap.add_argument("--stride", type=int, default=320); ap.add_argument("--C", type=int, default=16)
    ap.add_argument("--D", type=int, default=64); ap.add_argument("--levels", default="8,5,5,5")
    ap.add_argument("--nq", type=int, default=4); ap.add_argument("--K", type=int, default=256)
    ap.add_argument("--minutes", type=float, default=4.0); ap.add_argument("--bs", type=int, default=8)
    ap.add_argument("--seg", type=float, default=0.5); ap.add_argument("--out", default="res.json")
    ap.add_argument("--seed", type=int, default=0); ap.add_argument("--arch", default="v1"); ap.add_argument("--act", default="elu"); ap.add_argument("--eval_every", type=int, default=0); ap.add_argument("--lr", type=float, default=1e-3)
    a = ap.parse_args()
    torch.manual_seed(a.seed)
    if a.quant == "fsq": q = FSQ(a.D, [int(v) for v in a.levels.split(",")])
    elif a.quant == "rvq": q = RVQ(a.D, a.nq, a.K)
    else: q = NoQ()
    SR[0] = a.sr; ACT[0] = a.act
    m = {"v1": Codec, "v2": Codec2, "spec": SpecCodec}[a.arch](a.stride, a.C, a.D, q)
    nparams = sum(p.numel() for p in m.parameters())
    opt = torch.optim.AdamW(m.parameters(), lr=a.lr, betas=(0.8, 0.99))
    gtr = torch.Generator().manual_seed(a.seed + 1); gev = torch.Generator().manual_seed(12345)
    n = int(a.sr * a.seg)
    ev = batch(16, 2 * a.sr, a.sr, gev)  # 16 held-out clips of 2 s
    t0 = time.time(); step = 0; log = []
    budget = a.minutes * 60
    while time.time() - t0 < budget:
        x = batch(a.bs, n, a.sr, gtr)
        m.train()
        nq = None
        if a.quant == "rvq" and torch.rand(1).item() < 0.5:  # quantizer dropout (SoundStream)
            nq = 1 + int(torch.randint(a.nq, (1,)))
        y, codes, commit, T = m(x, nq)
        loss = mel_dist(x, y) + stft_loss(x, y) + F.l1_loss(y, x) + 0.25 * commit
        opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(m.parameters(), 1.0); opt.step()
        step += 1
        for gp in opt.param_groups: gp["lr"] = a.lr * min(1.0, step / 200) * max(0.05, 1 - (time.time() - t0) / budget)
        if step % 200 == 0:
            log.append((round(time.time() - t0, 1), step, round(loss.item(), 4)))
            print(log[-1], flush=True)
        if a.eval_every and step % a.eval_every == 0:
            m.eval()
            with torch.no_grad():
                ye, *_ = m(ev[:8]); print("EVAL", step, round(time.time() - t0), "mel", round(mel_dist(ev[:8], ye).item(), 4), "snr", round(snr(ev[:8].squeeze(1), ye.squeeze(1)), 2), flush=True)
    train_s = time.time() - t0
    m.eval(); res = {}
    with torch.no_grad():
        tt = time.time(); y, codes, _, T = m(ev); enc_s = time.time() - tt
        frames_per_s = T / 2.0
        res.update(snr_db=snr(ev.squeeze(1), y.squeeze(1)), sisnr_db=sisnr(ev.squeeze(1), y.squeeze(1)),
                   stft=stft_loss(ev, y).item(), mel=mel_dist(ev, y).item(), l1=F.l1_loss(y, ev).item(),
                   rtf_encode_decode=enc_s / (16 * 2.0))
        if codes is not None:
            per = []
            for i in range(codes.shape[-1]):
                c = codes[..., i].reshape(-1)
                h = torch.bincount(c, minlength=q.codebook_size).float(); p = h / h.sum()
                ent = -(p[p > 0] * p[p > 0].log2()).sum().item()
                per.append(dict(used=int((h > 0).sum()), of=q.codebook_size, frac=round(int((h > 0).sum()) / q.codebook_size, 4),
                                perplexity=round(2 ** ent, 1), entropy_bits=round(ent, 3), max_bits=round(math.log2(q.codebook_size), 3),
                                n_tokens=int(c.numel())))
            res["codebooks"] = per
            ncb = codes.shape[-1]
            res["tokens_per_s"] = frames_per_s * ncb
            res["bits_per_s_nominal"] = frames_per_s * ncb * math.log2(q.codebook_size)
            res["bits_per_s_entropy"] = frames_per_s * sum(d["entropy_bits"] for d in per)
            if a.quant == "rvq":
                res["by_nq"] = {}
                for k in range(1, a.nq + 1):
                    yk, _, _, _ = m(ev, k)
                    res["by_nq"][k] = dict(snr_db=round(snr(ev.squeeze(1), yk.squeeze(1)), 2), stft=round(stft_loss(ev, yk).item(), 4), mel=round(mel_dist(ev, yk).item(), 4),
                                           tokens_per_s=frames_per_s * k)
        # baseline: silence
        z0 = torch.zeros_like(ev) + 1e-4 * torch.randn_like(ev)
        res["baseline_zero_stft"] = stft_loss(ev, z0).item(); res["baseline_zero_mel"] = mel_dist(ev, z0).item()
        # baseline: mu-law 8-bit PCM at the same sample rate (classical reference point, 8 bits/sample)
        mu = 255.0; xm = torch.sign(ev) * torch.log1p(mu * ev.abs()) / math.log1p(mu)
        xq = torch.round((xm + 1) / 2 * 255) / 255 * 2 - 1; yq = torch.sign(xq) * ((1 + mu) ** xq.abs() - 1) / mu
        res["baseline_mulaw8_bps"] = a.sr * 8; res["baseline_mulaw8_snr_db"] = snr(ev.squeeze(1), yq.squeeze(1)); res["baseline_mulaw8_mel"] = mel_dist(ev, yq).item()
    res.update(args=vars(a), params=nparams, steps=step, train_seconds=round(train_s, 1),
               audio_seconds_seen=round(step * a.bs * a.seg, 1), frames_per_s=frames_per_s, log=log[-5:])
    print(json.dumps(res, indent=1))
    json.dump(res, open(a.out, "w"), indent=1)

if __name__ == "__main__":
    main()
