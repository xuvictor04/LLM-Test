"""d3: two-timescale co-adaptation. Shared pieces: data areas, codecs (spec25 baseline arch and the
nested multi-rate arch), EMA teacher, just-in-time encoding, rate allocation, decoding.

melody.py is copied from the sibling scratch dir d1 (aud/melody generator + analytic probe);
synth.py / codec_lib.py are copied unchanged from results/.../prototypes/design-hybrid.
"""
import os, sys, math, copy
os.environ.setdefault("OMP_NUM_THREADS", "1"); os.environ.setdefault("MKL_NUM_THREADS", "1")
import torch, torch.nn as nn, torch.nn.functional as F
torch.set_num_threads(1)
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import codec_lib as C
import synth as S
import melody as M

C.SR[0] = S.SR; C.PRENORM[0] = True; C.FSQ_ENT[0] = 1.0
SR = S.SR
NFFT, HOP = 512, 160
NB = NFFT // 2 + 1
WIN = torch.hann_window(NFFT)
LEVELS = [8, 5, 5, 5]
NCODE = 1000
CROP = 5120  # 0.64 s codec training crops (32 frames at 50 fps)

# ----------------------------------------------------------------------------- data areas
AREAS = {
    "tones": dict(sample=lambda g: S.sample(g), all=S.all_combos, render=S.render, caption=S.caption,
                  parse=S.parse_caption, probe=S.probe, acc=S.attr_acc, held=S.HELDOUT_COMBOS),
    "melody": dict(sample=lambda g: M.sample(g), all=M.all_combos, render=M.render, caption=M.caption,
                   parse=M.parse_caption, probe=M.probe, acc=M.attr_acc, held=M.HELDOUT),
}


def kind_of(area, p):
    return p[0] if area == "tones" else "melody"


def draw_clips(g, mix, n):
    """mix: list of (area, weight). Returns list of (area, params, wave(8000))."""
    names = [a for a, _ in mix]; w = torch.tensor([float(v) for _, v in mix])
    out = []
    for _ in range(n):
        a = names[int(torch.multinomial(w, 1, generator=g))]
        p, x = AREAS[a]["sample"](g)
        out.append((a, p, x))
    return out


def media_batch(g, mix, n, crop=CROP):
    xs = []
    for a, p, x in draw_clips(g, mix, n):
        s = int((SR - crop) * torch.rand(1, generator=g).item()); xs.append(x[s:s + crop])
    return torch.stack(xs)


def eval_set(area, per, seed):
    g = torch.Generator().manual_seed(seed); ps, xs = [], []
    for p in AREAS[area]["all"]():
        for _ in range(per):
            ps.append(p); xs.append(AREAS[area]["render"](p, g))
    return ps, torch.stack(xs)


# ----------------------------------------------------------------------------- signal helpers
def logmag(x):  # (B, n) -> (B, NB, n // HOP)
    X = torch.stft(x, NFFT, HOP, window=WIN, return_complex=True)[..., : x.shape[-1] // HOP]
    return torch.log(X.abs() + 1e-4)


def griffin_lim(mag, n, iters=32, seed=0):
    g = torch.Generator().manual_seed(seed)
    mag = F.pad(mag, (0, 1))
    ang = torch.rand(mag.shape, generator=g) * 2 * math.pi
    X = mag * torch.exp(1j * ang)
    for _ in range(iters):
        y = torch.istft(X, NFFT, HOP, window=WIN, length=n)
        Xr = torch.stft(y, NFFT, HOP, window=WIN, return_complex=True)
        X = mag * torch.exp(1j * torch.angle(Xr))
    return torch.istft(X, NFFT, HOP, window=WIN, length=n)


def lm_to_wave(lm, n):
    mag = (lm.exp() - 1e-4).clamp_min(0)
    return griffin_lim(mag, n)


def codes_to_lattice(codes, q):
    """(..., ) FSQ code ids -> (..., d) lattice coordinates in [-1, 1]."""
    L = q.levels; basis = q.basis; hw = (L // 2).float()
    digits = (codes.unsqueeze(-1) // basis) % L
    return (digits.float() - hw) / hw


def recon_loss(pred, target):
    T = min(pred.shape[-1], target.shape[-1]); pred = pred[..., :T]; target = target[..., :T]
    return F.l1_loss(pred, target) + 2.0 * F.l1_loss(pred.exp(), target.exp())


# ----------------------------------------------------------------------------- codecs
class Spec25(nn.Module):
    """The prior prototype's 25 Hz spectral FSQ codec (judge/spec25.py), unchanged architecture."""
    arch = "spec25"; nmedia = NCODE

    def __init__(self, D=64, H=256):
        super().__init__()
        self.enc_net = nn.Sequential(nn.Conv1d(NB, H, 3, padding=1), nn.ELU(), nn.Conv1d(H, H, 3, padding=1), nn.ELU(),
                                     nn.Conv1d(H, H, 4, stride=2, padding=1), nn.ELU(), nn.Conv1d(H, D, 1))
        self.dec_net = nn.Sequential(nn.ConvTranspose1d(D, H, 4, stride=2, padding=1), nn.ELU(), nn.Conv1d(H, H, 3, padding=1),
                                     nn.ELU(), nn.Conv1d(H, H, 3, padding=1), nn.ELU(), nn.Conv1d(H, NB, 1))
        self.q = C.FSQ(D, LEVELS)
        self.mu, self.sd = -4.0, 3.0

    def enc(self, x):
        return self.enc_net((logmag(x) - self.mu) / self.sd)

    def dec_logmag(self, zq):
        return self.dec_net(zq) * self.sd + self.mu

    def train_loss(self, x, g=None):
        z = self.enc(x); zq, codes, aux = self.q(z)
        return recon_loss(self.dec_logmag(zq), logmag(x)) + aux, codes[..., 0]

    @torch.no_grad()
    def encode(self, x, rho=None):
        """x (B, 8000) -> list of media-relative id lists, per-clip stride info, 25 Hz latent (B,D,25)."""
        z = self.enc(x); zq, codes, _ = self.q(z)
        codes = codes[..., 0]
        return [c.tolist() for c in codes], None, z

    @torch.no_grad()
    def decode(self, ids_list, n=SR, want_lm=False):
        codes = torch.tensor([list(c) for c in ids_list]).clamp(0, NCODE - 1)
        qv = codes_to_lattice(codes, self.q)                     # B T d
        zq = self.q.pout(qv.transpose(1, 2))
        lm = self.dec_logmag(zq)
        if want_lm:
            return lm
        y = lm_to_wave(lm, zq.shape[-1] * 2 * HOP)
        return F.pad(y, (0, max(0, n - y.shape[-1])))[..., :n]

    def world_latent(self, z):  # 25 Hz already
        return z


class Nested(nn.Module):
    """Nested multi-rate spectral FSQ codec. 50 fps base analysis grid; each 80 ms segment (G=4 frames)
    is coded at stride s in {1,2,4} (50 / 25 / 12.5 Hz) by FSQ on the average-pooled latent; the decoder
    sees the quantised vectors repeated s times. Trained with a random stride per segment (rate dropout),
    so ONE decoder decodes any schedule. The stride is carried in the id block: id = sidx*1000 + code."""
    arch = "nested"; nmedia = 3 * NCODE; G = 4; STRIDES = (1, 2, 4)

    def __init__(self, D=64, H=256):
        super().__init__()
        self.enc_net = nn.Sequential(nn.Conv1d(NB, H, 3, padding=1), nn.ELU(), nn.Conv1d(H, H, 3, padding=1), nn.ELU(),
                                     nn.Conv1d(H, D, 1))
        self.dec_net = nn.Sequential(nn.Conv1d(D, H, 3, padding=1), nn.ELU(), nn.Conv1d(H, H, 3, padding=1), nn.ELU(),
                                     nn.Conv1d(H, H, 3, padding=1), nn.ELU(), nn.Conv1d(H, NB, 1))
        self.q = C.FSQ(D, LEVELS)
        self.mu, self.sd = -4.0, 3.0

    def enc(self, x):
        return self.enc_net((logmag(x) - self.mu) / self.sd)

    def dec_logmag(self, zq):
        return self.dec_net(zq) * self.sd + self.mu

    def quant_all(self, z):
        out = {}
        for s in self.STRIDES:
            zs = F.avg_pool1d(z, s, s) if s > 1 else z
            zq, codes, aux = self.q(zs)
            out[s] = (zq.repeat_interleave(s, -1), codes[..., 0], aux)
        return out

    def mix(self, out, smap):
        m = smap.repeat_interleave(self.G, -1).unsqueeze(1)
        return sum((m == s).float() * out[s][0] for s in self.STRIDES)

    def train_loss(self, x, g):
        z = self.enc(x); out = self.quant_all(z)
        B, _, T = z.shape; nseg = T // self.G
        smap = torch.tensor(self.STRIDES)[torch.randint(len(self.STRIDES), (B, nseg), generator=g)]
        zq = self.mix(out, smap)
        aux = sum(out[s][2] for s in self.STRIDES) / len(self.STRIDES)
        return recon_loss(self.dec_logmag(zq), logmag(x)) + aux, out[1][1]

    @torch.no_grad()
    def seg_errors(self, x):
        xp = F.pad(x, (0, 320))
        z = self.enc(xp); out = self.quant_all(z); target = logmag(xp)
        B, _, T = z.shape; nseg = T // self.G
        errs = {s: (self.dec_logmag(out[s][0]) - target).abs().mean(1).view(B, nseg, self.G).mean(-1) for s in self.STRIDES}
        return z, out, errs

    @staticmethod
    def allocate(errs, rho, force=None):
        e1 = errs[1]; smap = torch.ones_like(e1, dtype=torch.long)
        if force is not None:
            return torch.full_like(smap, force)
        for s in (2, 4):  # the coarsest stride within (1+rho) of the finest reconstruction error wins
            smap = torch.where(errs[s] <= (1 + rho) * e1, torch.full_like(smap, s), smap)
        return smap

    @torch.no_grad()
    def encode(self, x, rho=0.1, force=None):
        z, out, errs = self.seg_errors(x)
        smap = self.allocate(errs, rho, force)
        B, nseg = smap.shape; G = self.G
        ids = []
        for b in range(B):
            row = []
            for gi in range(nseg):
                s = int(smap[b, gi]); si = self.STRIDES.index(s)
                c = out[s][1][b, gi * G // s:(gi + 1) * G // s]
                row += (c + si * NCODE).tolist()
            ids.append(row)
        return ids, smap, z

    @torch.no_grad()
    def decode(self, ids_list, n=SR, want_lm=False):
        T = 52; B = len(ids_list); D = self.q.pout.out_channels
        zq = torch.zeros(B, D, T)
        for b, row in enumerate(ids_list):
            if not row:
                continue
            ids = torch.tensor(row).clamp(0, 3 * NCODE - 1)
            si = ids // NCODE; code = ids % NCODE
            vec = self.q.pout(codes_to_lattice(code, self.q).t().unsqueeze(0))[0]  # D, len
            reps = torch.tensor([self.STRIDES[int(k)] for k in si])
            frames = vec.repeat_interleave(reps, -1)[:, :T]
            zq[b, :, :frames.shape[-1]] = frames
            if frames.shape[-1] < T:  # an unfinished schedule: hold the last vector
                zq[b, :, frames.shape[-1]:] = frames[:, -1:]
        lm = self.dec_logmag(zq)
        if want_lm:
            return lm
        y = lm_to_wave(lm, T * HOP)
        return y[..., :n]

    def world_latent(self, z):  # 50 fps -> 25 Hz so WORLD horizons are 40 / 200 ms in every arm
        return F.avg_pool1d(z[..., :50], 2, 2)


def make_codec(arch, seed=0):
    torch.manual_seed(seed)
    return {"spec25": Spec25, "nested": Nested}[arch]()


def frames_of(ids_list, arch):
    """Per clip: number of 50-fps frames covered by its ids (for rate accounting)."""
    if arch == "spec25":
        return [2 * len(r) for r in ids_list]
    return [sum(Nested.STRIDES[i // NCODE] for i in r) for r in ids_list]


def frame_codes(ids_list, arch, T=50):
    """Expand to a per-frame (stride, code) id at 50 fps for drift/flip measurement: (B, T) long."""
    out = torch.full((len(ids_list), T), -1, dtype=torch.long)
    for b, r in enumerate(ids_list):
        f = []
        for i in r:
            s = 2 if arch == "spec25" else Nested.STRIDES[i // NCODE]
            f += [i] * s
        f = f[:T]; out[b, :len(f)] = torch.tensor(f)
    return out


# ----------------------------------------------------------------------------- EMA teacher
class Teacher:
    """Slow copy of the student. decay 0 = online codes; decay 1 = frozen. Never 1 in the design."""
    def __init__(self, student, decay):
        self.m = copy.deepcopy(student).eval(); self.decay = decay
        for p in self.m.parameters():
            p.requires_grad_(False)

    @torch.no_grad()
    def update(self, student):
        d = self.decay
        if d >= 1.0:
            return
        for pt, ps in zip(self.m.parameters(), student.parameters()):
            pt.mul_(d).add_(ps.detach(), alpha=1 - d)


def mel(x, y):
    return C.mel_dist(x.unsqueeze(1), y.unsqueeze(1)).item()
