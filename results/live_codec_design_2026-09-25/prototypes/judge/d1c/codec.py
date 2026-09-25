"""Spectral FSQ codec (the proposal-03 codec) with a frame-rate option, plus live-training helpers.

STFT log-magnitude (n_fft 512, hop 160 at 8 kHz = 50 fps) -> conv encoder (stride 1 -> 50 Hz codes,
stride 2 -> 25 Hz codes) -> FSQ 8,5,5,5 (1000 lattice ids, marginal-entropy bonus) -> conv decoder ->
log-magnitude -> Griffin-Lim 32 (fixed algorithm, no weights) -> waveform.
Architecture copied from results/multimodal_design_2026-09-25/prototypes/{design-hybrid/spec_codec.py,
judge/spec25.py}; only the stride became a constructor argument.

Pretraining (the codec phase, identical for every arm): python codec.py STRIDE STEPS OUT.pt
"""
import os, sys, time, json, math, copy
os.environ.setdefault("OMP_NUM_THREADS", "1"); os.environ.setdefault("MKL_NUM_THREADS", "1")
import torch, torch.nn as nn, torch.nn.functional as F
torch.set_num_threads(1)
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import codec_lib as C
import synth as S

C.SR[0] = S.SR; C.PRENORM[0] = True; C.FSQ_ENT[0] = 1.0
NFFT, HOP = 512, 160
NB = NFFT // 2 + 1
WIN = torch.hann_window(NFFT)
GL_ITERS = 32
LEVELS = [8, 5, 5, 5]
NCODE = 1000


def logmag(x):
    X = torch.stft(x, NFFT, HOP, window=WIN, return_complex=True)[..., : x.shape[-1] // HOP]
    return torch.log(X.abs() + 1e-4)


def griffin_lim(mag, n, iters=GL_ITERS, seed=0):
    g = torch.Generator().manual_seed(seed)
    mag = F.pad(mag, (0, 1))
    ang = torch.rand(mag.shape, generator=g) * 2 * math.pi
    X = mag * torch.exp(1j * ang)
    for _ in range(iters):
        y = torch.istft(X, NFFT, HOP, window=WIN, length=n)
        Xr = torch.stft(y, NFFT, HOP, window=WIN, return_complex=True)
        X = mag * torch.exp(1j * torch.angle(Xr))
    return torch.istft(X, NFFT, HOP, window=WIN, length=n)


class SpecCodec(nn.Module):
    def __init__(self, stride=2, D=64, H=256):
        super().__init__()
        self.stride = stride
        if stride == 2:
            self.enc_net = nn.Sequential(nn.Conv1d(NB, H, 3, padding=1), nn.ELU(), nn.Conv1d(H, H, 3, padding=1), nn.ELU(),
                                         nn.Conv1d(H, H, 4, stride=2, padding=1), nn.ELU(), nn.Conv1d(H, D, 1))
            self.dec_net = nn.Sequential(nn.ConvTranspose1d(D, H, 4, stride=2, padding=1), nn.ELU(), nn.Conv1d(H, H, 3, padding=1),
                                         nn.ELU(), nn.Conv1d(H, H, 3, padding=1), nn.ELU(), nn.Conv1d(H, NB, 1))
        else:
            self.enc_net = nn.Sequential(nn.Conv1d(NB, H, 3, padding=1), nn.ELU(), nn.Conv1d(H, H, 3, padding=1), nn.ELU(),
                                         nn.Conv1d(H, D, 1))
            self.dec_net = nn.Sequential(nn.Conv1d(D, H, 3, padding=1), nn.ELU(), nn.Conv1d(H, H, 3, padding=1), nn.ELU(),
                                         nn.Conv1d(H, NB, 1))
        self.q = C.FSQ(D, LEVELS)
        self.mu, self.sd = -4.0, 3.0

    @property
    def fps(self):
        return S.SR // HOP // self.stride

    def enc(self, x):
        return self.enc_net((logmag(x[:, 0]) - self.mu) / self.sd)

    def bounded(self, z):
        """The FSQ pre-rounding values b (B,T,4); round(b) is the lattice point."""
        q = self.q
        z = q.pin(q.norm(z)).transpose(1, 2)
        L = q.levels.float(); half_l = (L - 1) * (1 + 1e-3) / 2
        offset = torch.where(q.levels % 2 == 0, 0.5, 0.0); shift = torch.atanh(offset / half_l)
        return torch.tanh(z + shift) * half_l - offset

    def dec_logmag(self, zq):
        return self.dec_net(zq) * self.sd + self.mu

    def dec(self, zq):
        lm = self.dec_logmag(zq)
        mag = (lm.exp() - 1e-4).clamp_min(0)
        return griffin_lim(mag, zq.shape[-1] * self.stride * HOP).unsqueeze(1)


def make_codec(stride):
    torch.manual_seed(0)
    return SpecCodec(stride)


@torch.no_grad()
def encode(m, X):
    """X (B, n) waveforms -> codes (B, T) long, b (B, T, 4) float."""
    was = m.training; m.eval()
    out_c, out_b = [], []
    for i in range(0, X.shape[0], 128):
        z = m.enc(X[i:i + 128].unsqueeze(1))
        b = m.bounded(z)
        hw = (m.q.levels // 2).float()
        codes = ((torch.round(b) + hw).long() * m.q.basis).sum(-1)
        out_c.append(codes); out_b.append(b)
    m.train(was)
    return torch.cat(out_c), torch.cat(out_b)


def codes_to_zq(m, codes):
    q = m.q
    L = q.levels; hw = (L // 2).float()
    digits = (codes.unsqueeze(-1) // q.basis) % L
    qv = (digits.float() - hw) / hw
    return q.pout(qv.transpose(1, 2))


@torch.no_grad()
def decode_codes(m, codes, n=None):
    """(B, T) lattice ids -> waveform (B, n)."""
    was = m.training; m.eval()
    y = m.dec(codes_to_zq(m, codes))[:, 0]
    m.train(was)
    n = n or S.SR
    return F.pad(y, (0, max(0, n - y.shape[-1])))[..., :n]


def codec_loss(m, x, anchor_codes=None, anchor_mask=None, anchor_w=0.0, margin=0.25):
    """Own loss only (reconstruction + FSQ entropy bonus); optional assignment-stability hinge.
    anchor_codes (B,T): the tokenizing snapshot's lattice ids for these crops; anchor_mask (B,) which
    crops are anchored. The hinge is zero while b stays within `margin` of the snapshot's lattice point
    (inside its FSQ cell), so the encoder may move inside a cell but is pushed back before a code flips."""
    target = logmag(x[:, 0])
    z = m.enc(x); zq, codes, aux = m.q(z)
    pred = m.dec_logmag(zq)
    T = min(pred.shape[-1], target.shape[-1]); pred = pred[..., :T]; target = target[..., :T]
    loss = F.l1_loss(pred, target) + 2.0 * F.l1_loss(pred.exp(), target.exp()) + aux
    anc = torch.zeros(())
    if anchor_w > 0 and anchor_codes is not None and anchor_mask is not None and anchor_mask.any():
        b = m.bounded(z)[anchor_mask]  # (b, T, 4)
        q = m.q; hw = (q.levels // 2).float()
        digits = (anchor_codes[anchor_mask].unsqueeze(-1) // q.basis) % q.levels
        tgt = digits.float() - hw
        Tm = min(b.shape[1], tgt.shape[1])
        anc = F.relu((b[:, :Tm] - tgt[:, :Tm]).abs() - margin).pow(2).sum(-1).mean()
        loss = loss + anchor_w * anc
    return loss, codes[..., 0], anc


def pretrain_batch(g, bs, n):
    """The prior prototypes' codec-phase recipe (design-hybrid/train_codec.py::train_batch): half aud/tones
    crops, half generic codec_lib clips."""
    xs = []
    for i in range(bs):
        if i % 2 == 0:
            _, x = S.sample(g)
            s = int((S.SR - n) * torch.rand(1, generator=g).item()); xs.append(x[s:s + n])
        else:
            xs.append(C.clip(n, S.SR, g))
    return torch.stack(xs).unsqueeze(1)


def main():
    stride, steps, out = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
    m = make_codec(stride); nparams = sum(p.numel() for p in m.parameters())
    opt = torch.optim.AdamW(m.parameters(), lr=1e-3, betas=(0.8, 0.99))
    g = torch.Generator().manual_seed(1); n = S.SR // 2
    t0 = time.time(); log = []
    for step in range(1, steps + 1):
        x = pretrain_batch(g, 16, n); m.train()
        loss, codes, _ = codec_loss(m, x)
        opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(m.parameters(), 1.0); opt.step()
        for gp in opt.param_groups:
            gp["lr"] = 1e-3 * min(1.0, step / 100) * max(0.05, 1 - step / steps)
        if step % 250 == 0:
            log.append((round(time.time() - t0), step, round(loss.item(), 3), int(torch.unique(codes).numel())))
            print(log[-1], flush=True)
    torch.save(dict(model=m.state_dict(), opt=opt.state_dict(), stride=stride, steps=steps), out)
    res = dict(stride=stride, fps=m.fps, params=nparams, steps=steps, train_s=round(time.time() - t0), log=log)
    json.dump(res, open(out + ".json", "w"), indent=1); print(json.dumps(res))


if __name__ == "__main__":
    main()
