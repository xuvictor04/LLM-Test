"""d2 prototype: continuous end-to-end latents + learned chunking, vs the frozen-FSQ fixed-25 Hz baseline.

One process = one arm x one seed. Phases (same data and LM steps in every arm):
  P1  text-only LM steps (T1) ; codec steps on A+B clips (C1 for live arms, CB = C1+P2+P3 for the frozen
      baseline, i.e. the baseline gets the SAME total codec updates, all before its freeze)
  P2  area A = aud/tones   (12 media rows + 4 text rehearsal rows per step)
  P3  area B = aud/melody  (8 B rows + 4 A rehearsal rows + 4 text rows per step)
Arms:
  base        spectral FSQ(8,5,5,5) codec, stride 2 -> fixed 25 Hz, frozen after its codec phase;
              LM over discrete ids with a modality-masked softmax (lm_hybrid 'mask_replay' shape)
  d2          live codec for the whole run; continuous chunk vectors enter the LM directly; encoder gets
              LM gradient through the INPUT side (targets detached); H-Net-style router + ratio loss picks
              chunk boundaries over the 50 fps STFT grid; GMM head for the next chunk vector, categorical
              duration head, END predicted
  d2_fixed    as d2 but boundaries fixed every 2 frames (25 Hz), no router     -> isolates chunking
  d2_nolm     as d2 but the encoder gets NO LM gradient (codec on its own loss) -> isolates end-to-end
  d2_tgtgrad  as d2 but GMM targets NOT detached (naive joint backprop, the 6.3 failure case)
Usage: d2run.py ARM SEED OUT.json     (env D2_* overrides; see E(...) below)
"""
import os, sys, time, json, math
os.environ.setdefault("OMP_NUM_THREADS", "1"); os.environ.setdefault("MKL_NUM_THREADS", "1")
import torch, torch.nn as nn, torch.nn.functional as F
torch.set_num_threads(1)
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import codec_lib as C
import synth as S
import melody as MEL
C.SR[0] = S.SR; C.PRENORM[0] = True; C.FSQ_ENT[0] = 1.0


def E(k, d, f=int):
    return f(os.environ.get("D2_" + k, d))


T1, C1, P2, P3 = E("T1", 400), E("C1", 500), E("P2", 800), E("P3", 800)
BS, L, W = 16, 80, 128
NFFT, HOP = 512, 160
NB = NFFT // 2 + 1
WIN = torch.hann_window(NFFT)
TFR = S.SR // HOP  # 50 STFT frames per 1 s clip
DMAX = E("DMAX", 16)
NRATIO = E("NRATIO", 2.0, float)
RATIO_W = E("RATIO_W", 0.1, float)
VAR_W = E("VAR_W", 1.0, float)
VAR_G = E("VAR_G", 0.3, float)
DLAT = E("DLAT", 8)
KMIX = E("KMIX", 8)
GMM_W = E("GMM_W", 0.1, float)      # weight of the GMM NLL (per latent dim) in the LM loss
LOGSIG_MIN = E("LOGSIG_MIN", -4.0, float)
PROBE_EVERY = E("PROBE_EVERY", 200)
LR_LM, LR_CODEC, LR_FLOOR = 2e-3, 1e-3, 0.05

T2A, A2T, AUD_B, AUD_E, EOT, PAD, AUD_C, SLOT = range(256, 264)
CODE_BASE, NCODE = 264, 1000


# ------------------------------------------------------------------ signal helpers
def logmag(x):
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


def lm2wav(lmag):  # (B, NB, T) log-magnitude -> (B, T*HOP)
    return griffin_lim((lmag.exp() - 1e-4).clamp_min(0), lmag.shape[-1] * HOP)


def spec_loss(pred, tgt):
    return F.l1_loss(pred, tgt) + 2.0 * F.l1_loss(pred.exp(), tgt.exp())


# ------------------------------------------------------------------ baseline codec (judge/spec25.py)
class Spec25(nn.Module):
    def __init__(self, D=64, H=256):
        super().__init__()
        self.enc_net = nn.Sequential(nn.Conv1d(NB, H, 3, padding=1), nn.ELU(), nn.Conv1d(H, H, 3, padding=1), nn.ELU(),
                                     nn.Conv1d(H, H, 4, stride=2, padding=1), nn.ELU(), nn.Conv1d(H, D, 1))
        self.dec_net = nn.Sequential(nn.ConvTranspose1d(D, H, 4, stride=2, padding=1), nn.ELU(), nn.Conv1d(H, H, 3, padding=1),
                                     nn.ELU(), nn.Conv1d(H, H, 3, padding=1), nn.ELU(), nn.Conv1d(H, NB, 1))
        self.q = C.FSQ(D, [8, 5, 5, 5])
        self.mu, self.sd = -4.0, 3.0

    def enc(self, lmx):
        return self.enc_net((lmx - self.mu) / self.sd)

    def dec_logmag(self, zq):
        return self.dec_net(zq) * self.sd + self.mu

    def loss(self, lmx):
        zq, codes, aux = self.q(self.enc(lmx))
        pred = self.dec_logmag(zq)
        return spec_loss(pred, lmx[..., :pred.shape[-1]]) + aux

    def codes(self, lmx):
        return self.q(self.enc(lmx))[1][..., 0]  # (B, 25)

    def codes_to_logmag(self, codes):
        q = self.q; Lv = q.levels; hw = (Lv // 2).float()
        digits = (codes.unsqueeze(-1) // q.basis) % Lv
        zq = q.pout(((digits.float() - hw) / hw).transpose(1, 2))
        return self.dec_logmag(zq)


# ------------------------------------------------------------------ live chunking codec (the design)
class ChunkCodec(nn.Module):
    """STFT log-mag (50 fps) -> conv encoder -> frame features f_t -> router p_t (H-Net cosine rule)
    -> boundaries -> chunk vector c_j = tanh(W mean(f in chunk)) in (-1,1)^DLAT  [the LM's media unit]
    -> decoder: per frame [c_j(t), position-in-chunk, chunk length] -> conv -> log-mag."""
    def __init__(self, fixed=0, Fd=64, H=256):
        super().__init__()
        self.fixed = fixed
        self.enc_net = nn.Sequential(nn.Conv1d(NB, H, 3, padding=1), nn.ELU(), nn.Conv1d(H, H, 3, padding=1), nn.ELU(),
                                     nn.Conv1d(H, Fd, 1))
        self.wq = nn.Linear(Fd, Fd, bias=False); self.wk = nn.Linear(Fd, Fd, bias=False)
        with torch.no_grad():
            self.wq.weight.copy_(torch.eye(Fd)); self.wk.weight.copy_(torch.eye(Fd))
        self.cproj = nn.Linear(Fd, DLAT)
        self.dec_net = nn.Sequential(nn.Conv1d(DLAT + 2, H, 3, padding=1), nn.ELU(), nn.Conv1d(H, H, 3, padding=1), nn.ELU(),
                                     nn.Conv1d(H, H, 3, padding=1), nn.ELU(), nn.Conv1d(H, NB, 1))
        self.mu, self.sd = -4.0, 3.0

    def frames(self, lmx):
        return self.enc_net((lmx - self.mu) / self.sd).transpose(1, 2)  # (B, T, Fd)

    def route(self, f):
        B, T, _ = f.shape
        if self.fixed:
            b = (torch.arange(T) % self.fixed == 0).unsqueeze(0).expand(B, T).clone()
            return torch.ones(B, T), b
        q = F.normalize(self.wq(f[:, 1:]), dim=-1); k = F.normalize(self.wk(f[:, :-1]), dim=-1)
        p = torch.cat([torch.ones(B, 1), 0.5 * (1 - (q * k).sum(-1))], 1)
        b = (p >= 0.5).clone()
        run = torch.zeros(B, dtype=torch.long)
        for t in range(T):  # force a boundary when a chunk reaches DMAX frames
            bt = b[:, t] | (run >= DMAX)
            b[:, t] = bt
            run = torch.where(bt, torch.ones_like(run), run + 1)
        return p, b

    def chunk(self, f, b):
        B, T, Fd = f.shape
        seg = b.long().cumsum(1) - 1
        M = seg[:, -1] + 1; Mm = int(M.max())
        sums = torch.zeros(B, Mm, Fd).scatter_add(1, seg.unsqueeze(-1).expand(-1, -1, Fd), f)
        cnt = torch.zeros(B, Mm).scatter_add(1, seg, torch.ones(B, T))
        c = torch.tanh(self.cproj(sums / cnt.clamp_min(1).unsqueeze(-1)))
        return c, cnt.long(), M, seg

    def dec_from(self, c, cnt, seg, b, conf=None):
        B, T = seg.shape
        cu = torch.gather(c, 1, seg.unsqueeze(-1).expand(-1, -1, c.shape[-1]))
        if conf is not None:
            cu = cu * (conf + (1 - conf).detach()).unsqueeze(-1)  # H-Net STE confidence -> router gradient
        idx = torch.arange(T).unsqueeze(0).expand(B, T)
        pos_in = idx - torch.cummax(idx * b.long(), 1)[0]
        d = torch.gather(cnt, 1, seg).float()
        feat = torch.cat([cu, (pos_in.float() / DMAX).unsqueeze(-1), (d / DMAX).unsqueeze(-1)], -1).transpose(1, 2)
        return self.dec_net(feat) * self.sd + self.mu

    def encode(self, lmx):
        f = self.frames(lmx); p, b = self.route(f); c, cnt, M, seg = self.chunk(f, b)
        return dict(f=f, p=p, b=b, c=c, cnt=cnt, M=M, seg=seg)

    def losses(self, lmx, enc):
        p, b = enc["p"], enc["b"]
        conf = None if self.fixed else torch.where(b, p, 1 - p)
        pred = self.dec_from(enc["c"], enc["cnt"], enc["seg"], b, conf)
        rec = spec_loss(pred, lmx)
        if self.fixed:
            ratio = torch.zeros(())
        else:
            Fb = b[:, 1:].float().mean(); G = p[:, 1:].mean(); N = NRATIO
            ratio = N / (N - 1) * ((N - 1) * Fb * G + (1 - Fb) * (1 - G))
        valid = torch.arange(enc["c"].shape[1]).unsqueeze(0) < enc["M"].unsqueeze(1)
        cv = enc["c"][valid]
        var = F.relu(VAR_G - cv.std(0)).mean()
        return rec, ratio, var


def decode_chunks(codec, cs, ds):
    """generation: one item's list of chunk vectors (M, D) and durations (M,) -> log-mag (1, NB, T)"""
    c = cs.unsqueeze(0); d = ds.long()
    b = torch.zeros(1, int(d.sum()), dtype=torch.bool)
    starts = torch.cat([torch.zeros(1, dtype=torch.long), d.cumsum(0)[:-1]])
    b[0, starts] = True
    seg = b.long().cumsum(1) - 1
    return codec.dec_from(c, d.unsqueeze(0), seg, b)


# ------------------------------------------------------------------ LM
class LM(nn.Module):
    def __init__(self, V, cont):
        super().__init__()
        self.V = V
        self.emb = nn.Embedding(V, W); self.rnn = nn.GRU(W, W, 2, batch_first=True); self.head = nn.Linear(W, V)
        if cont:
            self.cin = nn.Linear(DLAT, W); self.din = nn.Embedding(DMAX + 1, W)
            self.gmm = nn.Linear(W, KMIX * (1 + 2 * DLAT)); self.durh = nn.Linear(W, DMAX)

    def trunk(self, ids, cv=None, dv=None, slot=None, h=None):
        e = self.emb(ids)
        if cv is not None:
            e = e + slot.unsqueeze(-1) * (self.cin(cv) + self.din(dv))
        return self.rnn(e, h)


def gmm_split(lm, o):
    out = lm.gmm(o).view(*o.shape[:-1], KMIX, 1 + 2 * DLAT)
    return out[..., 0], out[..., 1:1 + DLAT], out[..., 1 + DLAT:].clamp(LOGSIG_MIN, 1)


def gmm_nll(lm, o, y):
    lg, mu, ls = gmm_split(lm, o)
    z = (y.unsqueeze(-2) - mu) * torch.exp(-ls)
    logn = (-0.5 * z * z - ls - 0.9189385).sum(-1)
    return -torch.logsumexp(F.log_softmax(lg, -1) + logn, -1)


def gmm_sample(lm, o, temp, g):
    lg, mu, ls = gmm_split(lm, o); B = o.shape[0]; ar = torch.arange(B)
    if temp == 0:
        k = lg.argmax(-1); return mu[ar, k].clamp(-0.999, 0.999)
    k = torch.multinomial(F.softmax(lg / temp, -1), 1, generator=g)[:, 0]
    m = mu[ar, k]; s = ls[ar, k].exp()
    return (m + temp * s * torch.randn(m.shape, generator=g)).clamp(-0.999, 0.999)


def masks(V, cont):
    text_ok = torch.zeros(V, dtype=torch.bool); text_ok[:256] = True; text_ok[[T2A, A2T, AUD_B, AUD_E, EOT]] = True
    aud_ok = torch.zeros(V, dtype=torch.bool); aud_ok[AUD_E] = True
    if cont:
        aud_ok[AUD_C] = True
    else:
        aud_ok[CODE_BASE:] = True
    return text_ok, aud_ok


# ------------------------------------------------------------------ data
def markov_text(n, seed):
    import bisect
    alpha = "etaoinshrdlu .,"
    g = torch.Generator().manual_seed(1234); k = len(alpha)
    gam = -torch.log(torch.rand(k * k, k, generator=g).clamp_min(1e-9))
    gam = gam ** (1 / 0.3)
    P = gam / gam.sum(-1, keepdim=True)
    gs = torch.Generator().manual_seed(seed)
    cdf = P.cumsum(-1).tolist(); u = torch.rand(n, generator=gs).tolist()
    a, b = 0, 1; out = []
    for i in range(n):
        c = min(k - 1, bisect.bisect_left(cdf[a * k + b], u[i])); out.append(alpha[c]); a, b = b, c
    return "".join(out).encode()


def area_sample(area, g):
    if area == "A":
        p, x = S.sample(g); return p, x, list(S.caption(p).encode())
    p, x = MEL.sample(g); return p, x, list(MEL.caption(p).encode())


def eval_set(area):
    if area == "A":
        g = torch.Generator().manual_seed(555); ps, xs = [], []
        for p in S.all_combos():
            for _ in range(2):
                ps.append(p); xs.append(S.render(p, g))
        return ps, torch.stack(xs)
    g = torch.Generator().manual_seed(556); ps, xs = [], []
    for _ in range(64):
        p, x = MEL.sample(g); ps.append(p); xs.append(x)
    return ps, torch.stack(xs)


def cap_of(area, p):
    return list((S.caption(p) if area == "A" else MEL.caption(p)).encode())


def score(area, pred_wav, p):
    if area == "A":
        return S.attr_acc(S.probe(pred_wav), p)
    return MEL.attr_acc(MEL.probe(pred_wav), p)


def parse(area, s):
    return S.parse_caption(s) if area == "A" else MEL.parse_caption(s)


def kind_of(area, p):
    return p[0] if area == "A" else "melody"


def agg(ds):
    if not ds:
        return {}
    return {k: round(sum(d[k] for d in ds) / len(ds), 4) for k in ds[0]} | {"n": len(ds)}


# ------------------------------------------------------------------ sequences
def seq_disc(task, cap, codes):
    cc = [CODE_BASE + int(c) for c in codes]
    if task == "t2a":
        s = [T2A] + cap + [AUD_B] + cc + [AUD_E]; mod = [0] * (len(cap) + 2) + [1] * (len(cc) + 1)
        capm = [0] * len(s)
    else:
        s = [A2T, AUD_B] + cc + [AUD_E] + cap + [EOT]; mod = [0, 0] + [1] * (len(cc) + 1) + [0] * (len(cap) + 1)
        capm = [0] * (len(cc) + 3) + [1] * (len(cap) + 1)
    return s, mod, capm, []


def seq_cont(task, cap, M):
    if task == "t2a":
        s = [T2A] + cap + [AUD_B] + [SLOT] * M + [AUD_E]; mod = [0] * (len(cap) + 2) + [1] * (M + 1)
        capm = [0] * len(s); slots = [(len(cap) + 2 + j, j) for j in range(M)]
    else:
        s = [A2T, AUD_B] + [SLOT] * M + [AUD_E] + cap + [EOT]; mod = [0, 0] + [1] * (M + 1) + [0] * (len(cap) + 1)
        capm = [0] * (M + 3) + [1] * (len(cap) + 1); slots = [(2 + j, j) for j in range(M)]
    return s, mod, capm, slots


def build(rows, cont, c=None, cnt=None, M=None, codes=None):
    """rows: list of ('text', bytes) | (task, cap, k). Returns padded tensors (B, L+1)."""
    B = len(rows)
    ids = torch.full((B, L + 1), PAD, dtype=torch.long); mod = torch.zeros(B, L + 1, dtype=torch.long)
    valid = torch.zeros(B, L + 1, dtype=torch.bool); capm = torch.zeros(B, L + 1, dtype=torch.bool)
    t2a = torch.zeros(B, dtype=torch.bool)
    bi, pi, ci, ji = [], [], [], []
    for r, row in enumerate(rows):
        if row[0] == "text":
            s = list(row[1][:L + 1]); ids[r, :len(s)] = torch.tensor(s); valid[r, :len(s)] = True; continue
        task, cap, k = row
        t2a[r] = task == "t2a"
        if cont:
            s, m, cm, slots = seq_cont(task, cap, int(M[k]))
        else:
            s, m, cm, slots = seq_disc(task, cap, codes[k].tolist())
        n = min(len(s), L + 1)
        ids[r, :n] = torch.tensor(s[:n]); mod[r, :n] = torch.tensor(m[:n]); valid[r, :n] = True
        capm[r, :n] = torch.tensor(cm[:n], dtype=torch.bool)
        for pos, j in slots:
            if pos < L + 1:
                bi.append(r); pi.append(pos); ci.append(k); ji.append(j)
    out = dict(ids=ids, mod=mod, valid=valid, capm=capm, t2a=t2a)
    if cont and not bi:
        out["cv"] = torch.zeros(B, L + 1, DLAT); out["dv"] = torch.zeros(B, L + 1, dtype=torch.long)
        out["slot"] = torch.zeros(B, L + 1)
    elif cont:
        idx = (torch.tensor(bi, dtype=torch.long), torch.tensor(pi, dtype=torch.long))
        cvals = c[torch.tensor(ci, dtype=torch.long), torch.tensor(ji, dtype=torch.long)]
        out["cv"] = torch.zeros(B, L + 1, DLAT).index_put(idx, cvals)
        dv = torch.zeros(B, L + 1, dtype=torch.long); dv[idx] = cnt[torch.tensor(ci, dtype=torch.long), torch.tensor(ji, dtype=torch.long)]
        out["dv"] = dv; out["slot"] = (ids == SLOT).float()
    return out


def lm_forward(lm, bt, cont, text_ok, aud_ok, tgt_detach=True):
    ids = bt["ids"]
    if cont:
        o, _ = lm.trunk(ids[:, :-1], bt["cv"][:, :-1], bt["dv"][:, :-1], bt["slot"][:, :-1])
    else:
        o, _ = lm.trunk(ids[:, :-1])
    lg = lm.head(o)
    allow = torch.where(bt["mod"][:, 1:].unsqueeze(-1) == 1, aud_ok, text_ok)
    lg = lg.masked_fill(~allow, float("-inf"))
    y = ids[:, 1:].clone(); is_slot = y == SLOT; y[is_slot] = AUD_C
    y = torch.where(bt["valid"][:, 1:], y, torch.zeros_like(y))
    ce = F.cross_entropy(lg.reshape(-1, lm.V), y.reshape(-1), reduction="none").view_as(y)
    v = bt["valid"][:, 1:]
    res = dict(ce=ce, v=v, o=o, lg=lg)
    if cont:
        sel = is_slot & v
        tgt = bt["cv"][:, 1:]
        if tgt_detach:
            tgt = tgt.detach()
        res["sel"] = sel
        res["nll"] = gmm_nll(lm, o[sel], tgt[sel])
        res["dce"] = F.cross_entropy(lm.durh(o[sel]), bt["dv"][:, 1:][sel] - 1, reduction="none")
    return res


# ------------------------------------------------------------------ run
class Run:
    def __init__(self, arm, seed):
        self.arm, self.seed = arm, seed
        self.cont = arm.startswith("d2")
        torch.manual_seed(1000 * seed + 1)
        if self.cont:
            self.codec = ChunkCodec(fixed=2 if arm == "d2_fixed" else 0)
        else:
            self.codec = Spec25()
        V = CODE_BASE if self.cont else CODE_BASE + NCODE
        self.lm = LM(V, self.cont)
        self.text_ok, self.aud_ok = masks(V, self.cont)
        self.opt_lm = torch.optim.AdamW(self.lm.parameters(), lr=LR_LM, weight_decay=0.0)
        self.opt_c = torch.optim.AdamW(self.codec.parameters(), lr=LR_CODEC, betas=(0.8, 0.99))
        self.codec_steps = 0; self.codec_total = C1 + P2 + P3
        self.g = torch.Generator().manual_seed(100 + seed)
        self.text_tr = markov_text(300_000, 1); self.text_ev = markov_text(20_000, 2)
        self.ev = {a: eval_set(a) for a in ("A", "B")}
        self.rec = dict(arm=arm, seed=seed, T1=T1, C1=C1, P2=P2, P3=P3, BS=BS, L=L, W=W, DMAX=DMAX, NRATIO=NRATIO,
                        RATIO_W=RATIO_W, VAR_W=VAR_W, DLAT=DLAT, KMIX=KMIX, GMM_W=GMM_W, LOGSIG_MIN=LOGSIG_MIN,
                        lm_params=sum(p.numel() for p in self.lm.parameters()),
                        codec_params=sum(p.numel() for p in self.codec.parameters()),
                        probes=[], curve=[], evals={}, timing={})
        self.prev_probe = None; self.step = 0; self.frozen = False

    # ---- codec lr: identical schedule in every arm (warmup 100, linear to a 0.05 floor at C1+P2+P3)
    def codec_lr(self):
        s = self.codec_steps
        for gp in self.opt_c.param_groups:
            gp["lr"] = LR_CODEC * min(1.0, (s + 1) / 100) * max(LR_FLOOR, 1 - s / self.codec_total)

    def text_rows(self, k):
        st = torch.randint(0, len(self.text_tr) - L - 2, (k,), generator=self.g).tolist()
        return [("text", self.text_tr[s:s + L + 1]) for s in st]

    def codec_only_step(self):
        xs = [area_sample("A" if i % 2 == 0 else "B", self.g)[1] for i in range(BS)]
        lmx = logmag(torch.stack(xs)); self.codec.train(); self.codec_lr()
        if self.cont:
            enc = self.codec.encode(lmx); rec, ratio, var = self.codec.losses(lmx, enc)
            loss = rec + RATIO_W * ratio + VAR_W * var
        else:
            loss = self.codec.loss(lmx)
        self.opt_c.zero_grad(); loss.backward(); nn.utils.clip_grad_norm_(self.codec.parameters(), 1.0); self.opt_c.step()
        self.codec_steps += 1
        if self.cont:
            return (round(loss.item(), 4), round(rec.item(), 4), round(enc["M"].float().mean().item(), 2))
        return round(loss.item(), 4)

    def text_step(self):
        bt = build(self.text_rows(BS), self.cont)
        r = lm_forward(self.lm, bt, self.cont, self.text_ok, self.aud_ok)
        loss = r["ce"][r["v"]].mean()
        self.opt_lm.zero_grad(); loss.backward(); nn.utils.clip_grad_norm_(self.lm.parameters(), 1.0); self.opt_lm.step()
        return loss.item()

    def media_step(self, mix):
        rows, clips = [], []
        for area, n in mix:
            for i in range(n):
                p, x, cap = area_sample(area, self.g); k = len(clips); clips.append(x)
                rows.append(("t2a" if i % 2 == 0 else "a2t", cap, k))
        rows += self.text_rows(BS - len(rows))
        lmx = logmag(torch.stack(clips))
        info = {}
        if self.cont and self.frozen:  # d2_frozen: continuous chunks from a codec frozen after its phase
            self.codec.eval()
            with torch.no_grad():
                enc = self.codec.encode(lmx)
            bt = build(rows, True, enc["c"], enc["cnt"], enc["M"])
            r = lm_forward(self.lm, bt, True, self.text_ok, self.aud_ok)
            loss = r["ce"][r["v"]].mean() + GMM_W * r["nll"].mean() / DLAT + r["dce"].mean()
            self.opt_lm.zero_grad(); loss.backward(); nn.utils.clip_grad_norm_(self.lm.parameters(), 1.0); self.opt_lm.step()
            info = dict(lm=round(loss.item(), 4), pos_per_s=round(enc["M"].float().mean().item(), 2))
        elif self.cont:
            self.codec.train(); self.codec_lr()
            enc = self.codec.encode(lmx)
            rec, ratio, var = self.codec.losses(lmx, enc)
            cin = enc["c"] if self.arm in ("d2", "d2_fixed", "d2_tgtgrad") else enc["c"].detach()
            bt = build(rows, True, cin, enc["cnt"], enc["M"])
            r = lm_forward(self.lm, bt, True, self.text_ok, self.aud_ok, tgt_detach=self.arm != "d2_tgtgrad")
            lm_loss = r["ce"][r["v"]].mean() + GMM_W * r["nll"].mean() / DLAT + r["dce"].mean()
            loss = lm_loss + rec + RATIO_W * ratio + VAR_W * var
            self.opt_lm.zero_grad(); self.opt_c.zero_grad(); loss.backward()
            nn.utils.clip_grad_norm_(self.lm.parameters(), 1.0); nn.utils.clip_grad_norm_(self.codec.parameters(), 1.0)
            self.opt_lm.step(); self.opt_c.step(); self.codec_steps += 1
            info = dict(lm=round(lm_loss.item(), 4), rec=round(rec.item(), 4), gmm_nats_per_dim=round(r["nll"].mean().item() / DLAT, 4),
                        pos_per_s=round(enc["M"].float().mean().item(), 2))
        else:
            with torch.no_grad():
                codes = self.codec.codes(lmx)
            bt = build(rows, False, codes=codes)
            r = lm_forward(self.lm, bt, False, self.text_ok, self.aud_ok)
            loss = r["ce"][r["v"]].mean()
            self.opt_lm.zero_grad(); loss.backward(); nn.utils.clip_grad_norm_(self.lm.parameters(), 1.0); self.opt_lm.step()
            info = dict(lm=round(loss.item(), 4))
        return info

    # ---------------------------------------------------------------- probes and evals
    @torch.no_grad()
    def probe(self, phase):
        self.codec.eval(); out = dict(step=self.step, phase=phase, codec_steps=self.codec_steps)
        cur = {}
        for area in ("A", "B"):
            ps, X = self.ev[area]; lmx = logmag(X)
            if self.cont:
                enc = self.codec.encode(lmx)
                U = torch.gather(enc["c"], 1, enc["seg"].unsqueeze(-1).expand(-1, -1, DLAT))
                b = enc["b"]; cur[area] = (U, b)
                valid = torch.arange(enc["c"].shape[1]).unsqueeze(0) < enc["M"].unsqueeze(1)
                cvv = enc["c"][valid]; cov = torch.cov(cvv.T); ev = torch.linalg.eigvalsh(cov).clamp_min(0)
                kinds = {}
                for i, p in enumerate(ps):
                    kinds.setdefault(kind_of(area, p), []).append(enc["M"][i].item())
                out[area] = dict(pos_per_s=round(enc["M"].float().mean().item(), 2),
                                 pos_per_s_by_kind={k: round(sum(v) / len(v), 2) for k, v in kinds.items()},
                                 lat_std=round(cvv.std(0).mean().item(), 4),
                                 lat_pr=round((ev.sum() ** 2 / (ev.pow(2).sum() + 1e-12)).item(), 3))
                if self.prev_probe is not None:
                    U0, b0 = self.prev_probe[area]
                    ds = max(1, self.step - self.prev_step)
                    out[area]["drift_rel_l2_per_1k"] = round(((U - U0).norm() / (U0.norm() + 1e-9)).item() * 1000 / ds, 4)
                    out[area]["boundary_flip_per_1k"] = round((b != b0).float().mean().item() * 1000 / ds, 4)
            else:
                codes = self.codec.codes(lmx); cur[area] = codes
                out[area] = dict(pos_per_s=25.0, codes_used=int(torch.unique(codes).numel()))
                if self.prev_probe is not None:
                    ds = max(1, self.step - self.prev_step)
                    out[area]["code_flip_per_1k"] = round((codes != self.prev_probe[area]).float().mean().item() * 1000 / ds, 4)
        self.prev_probe = cur; self.prev_step = self.step
        self.rec["probes"].append(out)

    @torch.no_grad()
    def text_bpb(self):
        g = torch.Generator().manual_seed(77); tot = n = 0.0
        for _ in range(6):
            st = torch.randint(0, len(self.text_ev) - L - 2, (20,), generator=g).tolist()
            bt = build([("text", self.text_ev[s:s + L + 1]) for s in st], self.cont)
            r = lm_forward(self.lm, bt, self.cont, self.text_ok, self.aud_ok)
            tot += r["ce"][:, 16:].sum().item(); n += r["ce"][:, 16:].numel()
        return round(tot / n / math.log(2), 4)

    @torch.no_grad()
    def encode_eval(self, area):
        ps, X = self.ev[area]; lmx = logmag(X)
        if self.cont:
            return ps, X, lmx, self.codec.encode(lmx)
        return ps, X, lmx, self.codec.codes(lmx)

    @torch.no_grad()
    def recon(self, area, enc_pack=None):
        ps, X, lmx, enc = enc_pack or self.encode_eval(area)
        if self.cont:
            lm_pred = self.codec.dec_from(enc["c"], enc["cnt"], enc["seg"], enc["b"])
        else:
            lm_pred = self.codec.codes_to_logmag(enc)
        wav = lm2wav(lm_pred)
        acc = agg([score(area, wav[i], p) for i, p in enumerate(ps)])
        return dict(mel=round(C.mel_dist(X.unsqueeze(1), wav.unsqueeze(1)).item(), 4),
                    logmag_l1=round(F.l1_loss(lm_pred, lmx[..., :lm_pred.shape[-1]]).item(), 4), probe_on_recon=acc)

    @torch.no_grad()
    def media_bits(self, area, enc_pack):
        """teacher-forced: t2a media-position readings and a2t caption bits/byte (codec-invariant)"""
        ps, X, lmx, enc = enc_pack; n = len(ps)
        rows = [("t2a", cap_of(area, p), i) for i, p in enumerate(ps)] + [("a2t", cap_of(area, p), i) for i, p in enumerate(ps)]
        if self.cont:
            bt = build(rows, True, enc["c"], enc["cnt"], enc["M"])
        else:
            bt = build(rows, False, codes=enc)
        r = lm_forward(self.lm, bt, self.cont, self.text_ok, self.aud_ok)
        ce, v = r["ce"], r["v"]; tm = bt["mod"][:, 1:] == 1
        t2a = bt["t2a"].unsqueeze(1)
        out = dict(a2t_caption_bits_per_byte=round((ce[bt["capm"][:, 1:] & v].mean() / math.log(2)).item(), 4))
        if self.cont:
            aud = tm & v & t2a
            sel = r["sel"]; sel_t2a = sel & t2a
            nll = torch.zeros_like(ce); nll[sel] = r["nll"]; dce = torch.zeros_like(ce); dce[sel] = r["dce"]
            npos = sel_t2a.sum().item()
            out.update(t2a_stop_bits_per_pos=round((ce[aud].sum() / npos / math.log(2)).item(), 4),
                       t2a_dur_bits_per_pos=round((dce[sel_t2a].mean() / math.log(2)).item(), 4),
                       t2a_gmm_nats_per_pos_DIFFERENTIAL=round(nll[sel_t2a].mean().item(), 4),
                       pos_per_s=round(enc["M"].float().mean().item(), 3))
            # teacher-forced one-step prediction decoded to audio (codec-invariant): GMM mode, true durations
            o = r["o"]; mode = gmm_sample(self.lm, o[sel_t2a], 0, None)
            c_pred = enc["c"].clone(); rr, pp = sel_t2a.nonzero(as_tuple=True)
            # map (row, pos) back to chunk index: in t2a rows, slot j sits at input position len(cap)+2+j -> target index pos
            for q, (ri, pi_) in enumerate(zip(rr.tolist(), pp.tolist())):
                j = pi_ + 1 - (len(cap_of(area, ps[ri])) + 2)
                c_pred[ri, j] = mode[q]
            lm_pred = self.codec.dec_from(c_pred, enc["cnt"], enc["seg"], enc["b"])
        else:
            code = tm & v & t2a & (bt["ids"][:, 1:] >= CODE_BASE)
            out.update(t2a_bits_per_code=round((ce[code].mean() / math.log(2)).item(), 4))
            out["t2a_bits_per_s"] = round(out["t2a_bits_per_code"] * 25, 2)
            am = r["lg"][code][:, CODE_BASE:].argmax(-1)
            codes_pred = am.view(n, -1)[:, :enc.shape[1]]
            lm_pred = self.codec.codes_to_logmag(codes_pred)
        wav = lm2wav(lm_pred)
        out["tf_pred_mel"] = round(C.mel_dist(X.unsqueeze(1), wav.unsqueeze(1)).item(), 4)
        out["tf_pred_probe_exact"] = agg([score(area, wav[i], p) for i, p in enumerate(ps)])["exact"]
        return out

    @torch.no_grad()
    def prompt_states(self, prompts, cvs=None):
        hs, last = [], []
        for i, pr in enumerate(prompts):
            ids = torch.tensor([pr])
            if cvs is not None and cvs[i] is not None:
                cv, dv, slot = cvs[i]
                o, h = self.lm.trunk(ids, cv.unsqueeze(0), dv.unsqueeze(0), slot.unsqueeze(0))
            else:
                o, h = self.lm.trunk(ids)
            hs.append(h); last.append(o[:, -1])
        return torch.cat(hs, 1), torch.cat(last, 0)

    @torch.no_grad()
    def understand(self, area, enc_pack):
        ps, X, lmx, enc = enc_pack; B = len(ps); prompts, cvs = [], []
        for i in range(B):
            if self.cont:
                M = int(enc["M"][i]); pr = [A2T, AUD_B] + [SLOT] * M + [AUD_E]
                cv = torch.zeros(len(pr), DLAT); cv[2:2 + M] = enc["c"][i, :M]
                dv = torch.zeros(len(pr), dtype=torch.long); dv[2:2 + M] = enc["cnt"][i, :M]
                slot = torch.zeros(len(pr)); slot[2:2 + M] = 1
                cvs.append((cv, dv, slot))
            else:
                pr = [A2T, AUD_B] + [CODE_BASE + int(c) for c in enc[i]] + [AUD_E]; cvs.append(None)
            prompts.append(pr)
        h, o = self.prompt_states(prompts, cvs)
        out = [[] for _ in range(B)]; done = [False] * B
        for _ in range(32):
            lg = self.lm.head(o).masked_fill(~self.text_ok, float("-inf")); tok = lg.argmax(-1)
            for i in range(B):
                if not done[i]:
                    if int(tok[i]) >= 256:
                        done[i] = True
                    else:
                        out[i].append(int(tok[i]))
            if all(done):
                break
            oo, h = self.lm.trunk(tok.unsqueeze(1), h=h); o = oo[:, -1]
        res = {"train": [], "heldout": []}
        for i, p in enumerate(ps):
            pred = parse(area, bytes(out[i]).decode(errors="replace"))
            d = (S.attr_acc(pred, p) if area == "A" else MEL.attr_acc(pred, p))
            res["heldout" if (area == "A" and p in S.HELDOUT_COMBOS) else "train"].append(d)
        outd = {k: agg(v) for k, v in res.items() if v}
        outd["samples"] = [bytes(out[i]).decode(errors="replace") for i in range(0, B, max(1, B // 6))][:6]
        return outd

    @torch.no_grad()
    def generate(self, area, temp, seed=5):
        g = torch.Generator().manual_seed(seed)
        if area == "A":
            ps = [p for p in S.all_combos() for _ in range(2)]
        else:
            ps = self.ev["B"][0][:48]
        B = len(ps); prompts = [[T2A] + cap_of(area, p) + [AUD_B] for p in ps]
        h, o = self.prompt_states(prompts)
        wavs = []; lens = []
        if self.cont:
            chunks = [[] for _ in range(B)]; done = torch.zeros(B, dtype=torch.bool); frames = torch.zeros(B, dtype=torch.long)
            maxfr = 2 * TFR
            for _ in range(maxfr):
                lg = self.lm.head(o).masked_fill(~self.aud_ok, float("-inf"))
                stop = (lg.argmax(-1) == AUD_E) if temp == 0 else (torch.multinomial(F.softmax(lg / temp, -1), 1, generator=g)[:, 0] == AUD_E)
                stop = stop | (frames >= maxfr)
                done = done | stop
                if done.all():
                    break
                dl = self.lm.durh(o)
                d = (dl.argmax(-1) if temp == 0 else torch.multinomial(F.softmax(dl / temp, -1), 1, generator=g)[:, 0]) + 1
                c = gmm_sample(self.lm, o, temp, g)
                for i in range(B):
                    if not done[i]:
                        chunks[i].append((c[i], int(d[i]))); frames[i] += int(d[i])
                oo, h = self.lm.trunk(torch.full((B, 1), SLOT), c.unsqueeze(1), d.unsqueeze(1), torch.ones(B, 1), h)
                o = oo[:, -1]
            for i in range(B):
                if not chunks[i]:
                    wavs.append(torch.zeros(TFR * HOP)); lens.append(0); continue
                cs = torch.stack([c for c, _ in chunks[i]]); ds = torch.tensor([d for _, d in chunks[i]])
                lmag = decode_chunks(self.codec, cs, ds)
                if lmag.shape[-1] < 8:  # GL needs >= n_fft samples; pad with silence
                    lmag = F.pad(lmag, (0, 8 - lmag.shape[-1]), value=math.log(1e-4))
                wavs.append(lm2wav(lmag)[0]); lens.append(int(ds.sum()))
            npos = sum(len(ch) for ch in chunks) / B
        else:
            F25 = TFR // 2; codes = torch.zeros(B, F25, dtype=torch.long)
            codeonly = torch.zeros(self.lm.V, dtype=torch.bool); codeonly[CODE_BASE:] = True
            for t in range(F25):
                lg = self.lm.head(o).masked_fill(~codeonly, float("-inf"))
                tok = lg.argmax(-1) if temp == 0 else torch.multinomial(F.softmax(lg / temp, -1), 1, generator=g)[:, 0]
                codes[:, t] = tok - CODE_BASE
                oo, h = self.lm.trunk(tok.unsqueeze(1), h=h); o = oo[:, -1]
            W_ = lm2wav(self.codec.codes_to_logmag(codes)); wavs = list(W_); lens = [TFR] * B; npos = F25
        res = {"train": [], "heldout": []}
        for i, p in enumerate(ps):
            d = score(area, wavs[i], p) if lens[i] > 0 else (S.attr_acc(None, p) if area == "A" else MEL.attr_acc(None, p))
            res["heldout" if (area == "A" and p in S.HELDOUT_COMBOS) else "train"].append(d)
        out = {k: agg(v) for k, v in res.items() if v}
        out["mean_positions_per_clip"] = round(npos, 2)
        out["mean_frames_50fps"] = round(sum(lens) / B, 2)
        return out

    def full_eval(self, tag, areas):
        t0 = time.time(); self.lm.eval(); self.codec.eval()
        ev = dict(text_bpb=self.text_bpb())
        for area in areas:
            pack = self.encode_eval(area)
            ev[area] = dict(recon=self.recon(area, pack), bits=self.media_bits(area, pack),
                            understand=self.understand(area, pack),
                            gen_t1=self.generate(area, 1.0), gen_t07=self.generate(area, 0.7), gen_t0=self.generate(area, 0))
        ev["eval_s"] = round(time.time() - t0, 1)
        self.rec["evals"][tag] = ev
        print(tag, json.dumps(ev), flush=True)
        self.lm.train(); self.codec.train()

    def main(self, out):
        t_all = time.time()
        # ---------------- P1
        t0 = time.time()
        for s in range(T1):
            l = self.text_step(); self.step += 1
            if s % 100 == 0:
                self.rec["curve"].append(("P1text", self.step, round(l / math.log(2), 3)))
        self.rec["timing"]["p1_text_s_per_step"] = round((time.time() - t0) / max(1, T1), 4)
        t0 = time.time(); ncs = C1 if (self.cont and self.arm != "d2_frozen") else C1 + P2 + P3
        for s in range(ncs):
            l = self.codec_only_step()
            if s % 200 == 0:
                self.rec["curve"].append(("P1codec", s, l)); print("P1codec", s, l, flush=True)
        self.rec["timing"]["p1_codec_s_per_step"] = round((time.time() - t0) / max(1, ncs), 4)
        self.rec["timing"]["p1_codec_steps"] = ncs
        self.rec["timing"]["p1_codec_s"] = round(time.time() - t0, 1)
        if not self.cont or self.arm == "d2_frozen":
            self.frozen = True  # AUD_FREEZE: no further codec update in this arm
            for p_ in self.codec.parameters():
                p_.requires_grad_(False)
        self.probe("P1end")
        self.full_eval("after_P1", [])
        # ---------------- P2 (area A)
        t0 = time.time()
        for s in range(P2):
            info = self.media_step([("A", 12)]); self.step += 1
            if s % 100 == 0:
                self.rec["curve"].append(("P2", self.step, info)); print("P2", s, info, round(time.time() - t0), flush=True)
            if (s + 1) % PROBE_EVERY == 0:
                self.probe("P2")
        self.rec["timing"]["p2_s_per_step"] = round((time.time() - t0) / max(1, P2), 4)
        self.full_eval("after_P2", ["A"])
        stale = None
        if self.cont:  # persist A's eval latents as they are now (as if stored), to test their meaning after P3
            with torch.no_grad():
                pack = self.encode_eval("A"); e = pack[3]
                stale = {k: e[k].clone() for k in ("c", "cnt", "seg", "b")}
        # ---------------- P3 (area B, with A and text rehearsal)
        t0 = time.time()
        for s in range(P3):
            info = self.media_step([("B", 8), ("A", 4)]); self.step += 1
            if s % 100 == 0:
                self.rec["curve"].append(("P3", self.step, info)); print("P3", s, info, round(time.time() - t0), flush=True)
            if (s + 1) % PROBE_EVERY == 0:
                self.probe("P3")
        self.rec["timing"]["p3_s_per_step"] = round((time.time() - t0) / max(1, P3), 4)
        self.full_eval("after_P3", ["A", "B"])
        if self.cont:
            with torch.no_grad():
                ps, X = self.ev["A"]
                wav = lm2wav(self.codec.dec_from(stale["c"], stale["cnt"], stale["seg"], stale["b"]))
                self.rec["stale_A_latents_decoded_by_P3_decoder"] = dict(
                    mel=round(C.mel_dist(X.unsqueeze(1), wav.unsqueeze(1)).item(), 4),
                    probe=agg([score("A", wav[i], p) for i, p in enumerate(ps)]))
        self.rec["timing"]["total_s"] = round(time.time() - t_all, 1)
        self.rec["codec_updates_total"] = self.codec_steps
        json.dump(self.rec, open(out, "w"), indent=1)
        print("DONE", out, self.rec["timing"], flush=True)


if __name__ == "__main__":
    arm, seed, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    Run(arm, seed).main(out)
