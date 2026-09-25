"""d3 main run: one continual stream  P0 text -> P1 aud/tones (+25% text) -> P2 aud/melody + tones (+25% text).

Arms (all share the stream, the LM, the eval sets; per seed the codec at the P0/P1 boundary is the SAME
cached codec-phase checkpoint for arms of one architecture):
  frozen25  prior route: spec25 codec, trained in the codec phase, frozen at the P0/P1 boundary
  live25    spec25, student keeps training, LM codes from the ONLINE student (no teacher lag)
  ttc25     spec25, student keeps training, LM codes from an EMA teacher (decay --decay)
  ttcMR     nested multi-rate codec, student keeps training, EMA teacher, per-segment stride allocation (--rho)
  ttcN25    nested codec forced to stride 2 everywhere (fixed 25 Hz) -- isolates the allocation
  frozenMR  nested codec, adaptive allocation, frozen at the boundary -- isolates live vs frozen in the MR arch
Usage: python3 run.py ARM SEED OUT.json [--p0 N --p1 N --p2 N ...]
"""
import os, sys, time, json, math, argparse, bisect, copy
os.environ.setdefault("OMP_NUM_THREADS", "1"); os.environ.setdefault("MKL_NUM_THREADS", "1")
import torch, torch.nn as nn, torch.nn.functional as F
torch.set_num_threads(1)
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import d3lib as D

ARMS = {
    "frozen25": dict(arch="spec25", decay=1.0, live=False, force=None),
    "live25": dict(arch="spec25", decay=0.0, live=True, force=None),
    "ttc25": dict(arch="spec25", decay=None, live=True, force=None),
    "ttcMR": dict(arch="nested", decay=None, live=True, force=None),
    "ttcN25": dict(arch="nested", decay=None, live=True, force=2),
    "frozenMR": dict(arch="nested", decay=1.0, live=False, force=None),
    # lattice-coordinate LM rows (drift tolerance): media embedding/logit = function of FSQ coordinates + free residual
    "frozen25c": dict(arch="spec25", decay=1.0, live=False, force=None, coord=True),
    "ttc25c": dict(arch="spec25", decay=None, live=True, force=None, coord=True),
    "ttcMRc": dict(arch="nested", decay=None, live=True, force=None, coord=True),
}
T2A, A2T, AUD_B, AUD_E, EOT, PAD = 256, 257, 258, 259, 260, 261
CB = 264
L = 96
W = 128


def markov_text(n, seed):
    alpha = "etaoinshrdlu .,"
    g = torch.Generator().manual_seed(1234)
    k = len(alpha)
    gam = -torch.log(torch.rand(k * k, k, generator=g).clamp_min(1e-9)); gam = gam ** (1 / 0.3)
    P = gam / gam.sum(-1, keepdim=True)
    gs = torch.Generator().manual_seed(seed)
    cdf = P.cumsum(-1).tolist(); u = torch.rand(n, generator=gs).tolist()
    a, b = 0, 1; out = []
    for i in range(n):
        row = cdf[a * k + b]; c = min(k - 1, bisect.bisect_left(row, u[i])); out.append(alpha[c]); a, b = b, c
    return "".join(out).encode()


class LM(nn.Module):
    def __init__(self, V):
        super().__init__()
        self.emb = nn.Embedding(V, W); self.rnn = nn.GRU(W, W, 2, batch_first=True); self.head = nn.Linear(W, V)

        self.coord = False

    def add_coord(self, P, gen):
        """P (nmedia, K): each media id's FSQ digit slots (+ stride slot) as a 0/1 row. The media input vector
        becomes cemb-sum over its slots + a free row; the media logit becomes (o @ chead) @ P^T + a free logit.
        Free media rows are zeroed so the coordinate part carries the meaning at birth."""
        self.coord = True
        self.register_buffer("Pm", P)
        self.cemb = nn.Parameter(torch.randn(P.shape[1], W, generator=gen) * 0.5)
        self.chead = nn.Parameter(torch.zeros(W, P.shape[1]))
        with torch.no_grad():
            self.emb.weight[CB:] = 0; self.head.weight[CB:] = 0; self.head.bias[CB:] = 0

    def forward(self, x, h=None):
        e = self.emb(x)
        if self.coord:
            med = (x >= CB).unsqueeze(-1).float()
            e = e + (self.Pm[(x - CB).clamp(min=0)] @ self.cemb) * med
        o, h = self.rnn(e, h)
        lg = self.head(o)
        if self.coord:
            lg = torch.cat([lg[..., :CB], lg[..., CB:] + (o @ self.chead) @ self.Pm.t()], -1)
        return lg, h


def coord_matrix(codec):
    levels = [int(v) for v in codec.q.levels]; K = sum(levels); n = codec.nmedia
    nst = 1 if codec.arch == "spec25" else len(D.Nested.STRIDES)
    P = torch.zeros(n, K + (nst if nst > 1 else 0))
    ids = torch.arange(n); code = ids % D.NCODE
    digits = (code.unsqueeze(-1) // codec.q.basis) % codec.q.levels
    off = 0
    for d, Ld in enumerate(levels):
        P[ids, off + digits[:, d]] = 1.0; off += Ld
    if nst > 1:
        P[ids, K + ids // D.NCODE] = 1.0
    return P


class World(nn.Module):
    """WORLD.media_terms stand-in: GRU over the student's 25 Hz latents predicting the TEACHER's latents
    40 ms (h=1) and 200 ms (h=5) ahead. Input and target are both detached (no gradient into the codec)."""
    def __init__(self, Dm=64, H=64):
        super().__init__(); self.rnn = nn.GRU(Dm, H, batch_first=True); self.out = nn.Linear(H, 2 * Dm); self.Dm = Dm

    def forward(self, zin):  # (B, T, D)
        h, _ = self.rnn(zin); B, T, _ = zin.shape
        return self.out(h).view(B, T, 2, self.Dm)


def world_losses(pred, tgt):
    l1 = F.mse_loss(pred[:, :-1, 0], tgt[:, 1:]); l5 = F.mse_loss(pred[:, :-5, 1], tgt[:, 5:])
    p1 = F.mse_loss(tgt[:, :-1], tgt[:, 1:]); p5 = F.mse_loss(tgt[:, :-5], tgt[:, 5:])
    return l1, l5, p1, p5


def seq_t2a(cap, ids):
    s = [T2A] + list(cap.encode()) + [AUD_B] + [CB + i for i in ids] + [AUD_E]
    return s, [0] * (len(s) - len(ids) - 1) + [1] * (len(ids) + 1)


def seq_a2t(cap, ids):
    s = [A2T, AUD_B] + [CB + i for i in ids] + [AUD_E] + list(cap.encode()) + [EOT]
    return s, [0, 0] + [1] * (len(ids) + 1) + [0] * (len(cap) + 1)


def pack(seqs):
    X, Mo, N = [], [], []
    for s, m in seqs:
        s = s[:L + 1]; m = m[:L + 1]; n = len(s)
        X.append(s + [PAD] * (L + 1 - n)); Mo.append(m + [0] * (L + 1 - n)); N.append(n)
    X = torch.tensor(X); Mo = torch.tensor(Mo)
    valid = torch.arange(L + 1).unsqueeze(0) < torch.tensor(N).unsqueeze(1)
    return X, Mo, valid


class Main:
    def __init__(self, a):
        self.a = a; cfg = dict(ARMS[a.arm]); self.cfg = cfg
        if cfg["decay"] is None:
            cfg["decay"] = a.decay
        self.arch = cfg["arch"]
        self.student = D.make_codec(self.arch, a.seed)
        ck = os.path.join(HERE, "ck", f"{self.arch}_s{a.seed}.pt")
        st = torch.load(ck)
        self.student.load_state_dict(st["student"]); self.codec_phase = st["info"]
        self.copt = torch.optim.AdamW(self.student.parameters(), lr=a.codec_lr, betas=(0.8, 0.99))
        self.copt.load_state_dict(st["opt"])
        for gp in self.copt.param_groups:
            gp["lr"] = a.codec_lr
        self.teacher = D.Teacher(self.student, cfg["decay"])
        self.V = CB + self.student.nmedia
        self.TEXT_OK = torch.zeros(self.V, dtype=torch.bool); self.TEXT_OK[:CB] = True; self.TEXT_OK[PAD] = False
        self.AUD_OK = torch.zeros(self.V, dtype=torch.bool); self.AUD_OK[CB:] = True; self.AUD_OK[AUD_E] = True
        # LM INIT INDEPENDENT OF THE MEDIA ROW COUNT: the GRU and the first CB+1000 rows are the spec25 arms'
        # init exactly, so the text-only P0 is the same network in every arm of a seed (paired goal-B reading).
        torch.manual_seed(1000 + a.seed)
        base = LM(CB + D.NCODE)
        if self.V == CB + D.NCODE:
            self.lm = base
        else:
            self.lm = LM(self.V)
            with torch.no_grad():
                self.lm.rnn.load_state_dict(base.rnn.state_dict())
                self.lm.emb.weight[:CB + D.NCODE] = base.emb.weight; self.lm.head.weight[:CB + D.NCODE] = base.head.weight
                self.lm.head.bias[:CB + D.NCODE] = base.head.bias
        if cfg.get("coord"):
            self.lm.add_coord(coord_matrix(self.student), torch.Generator().manual_seed(4000 + a.seed))
        self.lm = self.lm; self.opt = torch.optim.AdamW(self.lm.parameters(), lr=2e-3, weight_decay=0.0)
        self.world = World(); self.wopt = torch.optim.Adam(self.world.parameters(), lr=1e-3)
        self.g_data = torch.Generator().manual_seed(100 + a.seed)   # identical stream across arms
        self.g_codec = torch.Generator().manual_seed(200 + a.seed)
        self.g_alloc = torch.Generator().manual_seed(300 + a.seed)
        self.text_tr = markov_text(300_000, 1); self.text_ev = markov_text(20_000, 2)
        self.ev = {ar: D.eval_set(ar, per, sd) for ar, per, sd in (("tones", 3, 555), ("melody", 4, 556))}
        self.pr = {ar: D.eval_set(ar, per, sd) for ar, per, sd in (("tones", 1, 777), ("melody", 2, 778))}
        self.rec = dict(arm=a.arm, seed=a.seed, arch=self.arch, coord=bool(cfg.get("coord")), decay=cfg["decay"], rho=a.rho if self.arch == "nested" else None,
                        force=cfg["force"], live=cfg["live"], p0=a.p0, p1=a.p1, p2=a.p2, every=a.every, codec_lr=a.codec_lr,
                        V=self.V, lm_params=sum(p.numel() for p in self.lm.parameters()), codec_phase=self.codec_phase,
                        meas=[], rate_log=[], timing={}, evals={})
        self.step = 0; self.codec_steps = 0; self.prev_probe = []

    # ------------------------------------------------------------------ encoding
    def encode(self, codec, X):
        if self.arch == "nested":
            return codec.encode(X, rho=self.a.rho, force=self.cfg["force"])
        return codec.encode(X)

    def masked(self, logits, tmod):
        allow = torch.where(tmod.unsqueeze(-1) == 1, self.AUD_OK, self.TEXT_OK)
        return logits.masked_fill(~allow, float("-inf"))

    def nll(self, X, Mo, valid):
        logits, _ = self.lm(X[:, :-1])
        lg = self.masked(logits, Mo[:, 1:])
        y = X[:, 1:]
        nll = F.cross_entropy(lg.reshape(-1, self.V), y.reshape(-1), reduction="none").view_as(y)
        return nll, valid[:, 1:]

    def text_batch(self, g, bs):
        starts = torch.randint(0, len(self.text_tr) - L - 2, (bs,), generator=g).tolist()
        X = torch.tensor([list(self.text_tr[s:s + L + 1]) for s in starts])
        return X, torch.zeros_like(X), torch.ones_like(X, dtype=torch.bool)

    @torch.no_grad()
    def eval_text(self, nwin=60):
        g = torch.Generator().manual_seed(77); tot = 0.0; n = 0
        for _ in range(nwin // 20):
            starts = torch.randint(0, len(self.text_ev) - L - 2, (20,), generator=g).tolist()
            X = torch.tensor([list(self.text_ev[s:s + L + 1]) for s in starts])
            nll, v = self.nll(X, torch.zeros_like(X), torch.ones_like(X, dtype=torch.bool))
            tot += nll[:, 16:].sum().item(); n += nll[:, 16:].numel()
        return tot / n / math.log(2)

    # ------------------------------------------------------------------ training steps
    def lm_step(self, X, Mo, v):
        nll, v = self.nll(X, Mo, v)
        loss = nll[v].mean(); self.opt.zero_grad(); loss.backward()
        nn.utils.clip_grad_norm_(self.lm.parameters(), 1.0); self.opt.step()
        return loss.item()

    def codec_step(self, mix):
        self.student.train()
        xb = D.media_batch(self.g_codec, mix, 16)
        loss, codes = self.student.train_loss(xb, self.g_codec)
        self.copt.zero_grad(); loss.backward(); nn.utils.clip_grad_norm_(self.student.parameters(), 1.0); self.copt.step()
        self.student.eval(); self.teacher.update(self.student); self.codec_steps += 1
        return loss.item(), int(torch.unique(codes).numel())

    def media_step(self, lm_mix, codec_mix, tm):
        a = self.a; bs = 16; k = bs // 4
        t0 = time.time()
        clips = D.draw_clips(self.g_data, lm_mix, bs - k)
        X = torch.stack([c[2] for c in clips])
        ids, smap, z = self.encode(self.teacher.m, X)           # just-in-time: codes from the teacher NOW
        tm["encode"] += time.time() - t0
        seqs = []
        for j, (ar, p, x) in enumerate(clips):
            cap = D.AREAS[ar]["caption"](p)
            seqs.append(seq_t2a(cap, ids[j]) if j % 2 == 0 else seq_a2t(cap, ids[j]))
        Xa, Ma, va = pack(seqs)
        Xt, Mt, vt = self.text_batch(self.g_data, k)
        t1 = time.time()
        loss = self.lm_step(torch.cat([Xa, Xt]), torch.cat([Ma, Mt]), torch.cat([va, vt]))
        tm["lm"] += time.time() - t1
        # rate log
        for j, (ar, p, x) in enumerate(clips):
            self.rate_acc.append((ar, D.kind_of(ar, p), len(ids[j])))
        # WORLD over the student's latents -> teacher's latents (both detached)
        t2 = time.time()
        with torch.no_grad():
            zt = self.teacher.m.world_latent(z).transpose(1, 2)
            zs = zt if not self.cfg["live"] else self.student.world_latent(self.student.enc(
                torch.nn.functional.pad(X, (0, 320)) if self.arch == "nested" else X)).transpose(1, 2)
        pred = self.world(zs)
        l1, l5, _, _ = world_losses(pred, zt)
        self.wopt.zero_grad(); (l1 + l5).backward(); self.wopt.step()
        tm["world"] += time.time() - t2
        if self.cfg["live"] and self.step % a.every == 0:
            t3 = time.time(); cl, cu = self.codec_step(codec_mix); tm["codec"] += time.time() - t3
            self.last_codec = (cl, cu)
        return loss

    # ------------------------------------------------------------------ measurements
    @torch.no_grad()
    def seq_bits(self, area, ps, X, ids, heldout=False):
        """t2a bits on media targets (codes + END) per clip; mean bits per code position."""
        sel = [i for i, p in enumerate(ps) if (p in D.AREAS[area]["held"]) == heldout]
        seqs = [seq_t2a(D.AREAS[area]["caption"](ps[i]), ids[i]) for i in sel]
        Xs, Ms, vs = pack(seqs)
        nll, v = self.nll(Xs, Ms, vs)
        tm = Ms[:, 1:] == 1; y = Xs[:, 1:]
        med = tm & v
        code = med & (y >= CB)
        bits_clip = torch.where(med, nll, torch.zeros_like(nll)).sum(1) / math.log(2)
        return dict(bits_per_pos=round((nll[code].mean() / math.log(2)).item(), 4),
                    bits_per_s=round(bits_clip.mean().item(), 3),
                    pos_per_s=round(code.sum(1).float().mean().item(), 2), n=len(sel))

    @torch.no_grad()
    def measure(self, phase):
        """Drift + LM tolerance on the fixed probe set (every a.meas steps)."""
        rec = dict(step=self.step, phase=phase, codec_steps=self.codec_steps)
        cur = {}
        for ar in ("tones", "melody"):
            ps, X = self.pr[ar]
            ids, smap, z = self.encode(self.teacher.m, X)
            fc = D.frame_codes(ids, self.arch)
            cur[ar] = dict(ids=ids, fc=fc, z=z.clone())
            lmr = self.teacher.m.decode(ids, want_lm=True)[..., :50]
            rec[f"{ar}_recon_logmag_l1"] = round((lmr - D.logmag(X)[..., :50]).abs().mean().item(), 4)
            rec[f"{ar}_pos_per_s"] = round(sum(len(r) for r in ids) / len(ids), 2)
            rec[f"{ar}_bits"] = self.seq_bits(ar, ps, X, ids)
            for back, key in ((1, "d1"), (4, "d4")):
                if len(self.prev_probe) >= back:
                    old = self.prev_probe[-back]
                    rec[f"{ar}_flip_{key}"] = round((old[ar]["fc"] != fc).float().mean().item(), 4)
                    oz, nz = old[ar]["z"], z
                    rec[f"{ar}_zdrift_{key}"] = round(((nz - oz).norm() / nz.norm()).item(), 4)
                    rec[f"{ar}_bits_stale_{key}"] = self.seq_bits(ar, ps, X, old[ar]["ids"])["bits_per_pos"]
                    rec[f"{ar}_steps_{key}"] = self.step - old["step"]
        cur["step"] = self.step
        self.prev_probe.append(cur); self.prev_probe = self.prev_probe[-4:]
        rec["text_bpb"] = round(self.eval_text(), 4)
        self.rec["meas"].append(rec)
        print("MEAS", json.dumps({k: v for k, v in rec.items() if not isinstance(v, dict)}), flush=True)

    @torch.no_grad()
    def understand(self, area, ps, ids):
        B = len(ps); hs, last = [], []
        for i in range(B):
            pr = [A2T, AUD_B] + [CB + c for c in ids[i]] + [AUD_E]
            lg, h = self.lm(torch.tensor([pr])); hs.append(h); last.append(lg[:, -1])
        h = torch.cat(hs, 1); nxt = torch.cat(last, 0)
        out = [[] for _ in range(B)]; done = [False] * B
        for _ in range(44):
            tok = self.masked(nxt, torch.zeros(B, dtype=torch.long)).argmax(-1)
            for i in range(B):
                if not done[i]:
                    if int(tok[i]) == EOT or int(tok[i]) >= 256:
                        done[i] = True
                    else:
                        out[i].append(int(tok[i]))
            lg, h = self.lm(tok.unsqueeze(1), h); nxt = lg[:, -1]
        A = D.AREAS[area]; res = {"train": [], "held": []}
        for i in range(B):
            d = A["acc"](A["parse"](bytes(out[i]).decode(errors="replace")), ps[i])
            res["held" if ps[i] in A["held"] else "train"].append(d)
        return {k: agg(v) for k, v in res.items()}

    @torch.no_grad()
    def generate(self, area, reps=3, temp=1.0, seed=5):
        g = torch.Generator().manual_seed(seed); A = D.AREAS[area]
        ps = [p for p in A["all"]() for _ in range(reps)]; B = len(ps)
        hs, last = [], []
        for p in ps:
            lg, h = self.lm(torch.tensor([[T2A] + list(A["caption"](p).encode()) + [AUD_B]])); hs.append(h); last.append(lg[:, -1])
        h = torch.cat(hs, 1); nxt = torch.cat(last, 0)
        budget = 50 if self.arch == "spec25" else 52
        ids = [[] for _ in range(B)]; frames = [0] * B; invalid = 0; npos = 0
        for t in range(52):
            if all(f >= budget for f in frames):
                break
            lg = self.masked(nxt, torch.ones(B, dtype=torch.long)) / temp
            tok = torch.multinomial(lg.softmax(-1), 1, generator=g)[:, 0]
            bad = tok < CB
            best = lg[:, CB:].argmax(-1) + CB
            for i in range(B):
                if frames[i] >= budget:
                    continue
                npos += 1
                if bool(bad[i]):
                    invalid += 1; tok[i] = best[i]
                r = int(tok[i]) - CB
                ids[i].append(r)
                frames[i] += 2 if self.arch == "spec25" else D.Nested.STRIDES[r // D.NCODE]
            lg2, h = self.lm(tok.unsqueeze(1), h); nxt = lg2[:, -1]
        wav = self.teacher.m.decode(ids)
        res = {"train": [], "held": []}; pos = []
        for i, p in enumerate(ps):
            d = A["acc"](A["probe"](wav[i]), p); res["held" if p in A["held"] else "train"].append(d); pos.append(len(ids[i]))
        out = {k: agg(v) for k, v in res.items()}
        out["invalid_end_rate"] = round(invalid / max(1, npos), 4); out["pos_per_s"] = round(sum(pos) / B, 2)
        return out

    @torch.no_grad()
    def full_eval(self, tag, areas, final=False):
        t0 = time.time(); ev = dict(text_bpb=round(self.eval_text(), 4), codec_steps=self.codec_steps)
        for ar in areas:
            ps, X = self.ev[ar]
            ids, smap, z = self.encode(self.teacher.m, X)
            r = {}
            Y = self.teacher.m.decode(ids)
            r["recon_mel"] = round(D.mel(X, Y), 4)
            A = D.AREAS[ar]
            acc = [A["acc"](A["probe"](Y[i]), p) for i, p in enumerate(ps)]
            r["recon_probe"] = agg(acc)
            # rate by kind
            kinds = {}
            for i, p in enumerate(ps):
                kinds.setdefault(D.kind_of(ar, p), []).append(len(ids[i]))
            r["pos_per_s_by_kind"] = {k: round(sum(v) / len(v), 2) for k, v in kinds.items()}
            r["pos_per_s"] = round(sum(len(x) for x in ids) / len(ids), 2)
            if smap is not None:
                r["stride_frac"] = {s: round((smap == s).float().mean().item(), 3) for s in (1, 2, 4)}
            codes_all = torch.tensor([c for row in ids for c in row])
            r["codes_used"] = int(torch.unique(codes_all).numel())
            h = torch.bincount(codes_all, minlength=self.student.nmedia).float(); pr = h / h.sum()
            r["code_entropy_bits"] = round(-(pr[pr > 0] * pr[pr > 0].log2()).sum().item(), 3)
            r["bits_train_combos"] = self.seq_bits(ar, ps, X, ids)
            r["bits_heldout_combos"] = self.seq_bits(ar, ps, X, ids, heldout=True)
            r["understand"] = self.understand(ar, ps, ids)
            r["generate_t1.0"] = self.generate(ar, temp=1.0)
            if final:
                r["generate_t0.7"] = self.generate(ar, temp=0.7)
            # WORLD
            zt = self.teacher.m.world_latent(z).transpose(1, 2)
            zs = zt if not self.cfg["live"] else self.student.world_latent(self.student.enc(
                F.pad(X, (0, 320)) if self.arch == "nested" else X)).transpose(1, 2)
            l1, l5, p1, p5 = world_losses(self.world(zs), zt)
            r["world"] = dict(rel_mse_40ms=round((l1 / p1).item(), 4), rel_mse_200ms=round((l5 / p5).item(), 4),
                              target_std=round(zt.std(dim=(0, 1)).mean().item(), 4))
            if tag == "after_P1" and ar == "tones":
                self.p1_tones_ids = ids
            if tag == "after_P2" and ar == "tones" and getattr(self, "p1_tones_ids", None) is not None:
                # AQM question: do codes written at the end of P1 still decode (and still read) under the P2 teacher?
                Yo = self.teacher.m.decode(self.p1_tones_ids)
                acc = [A["acc"](A["probe"](Yo[i]), p) for i, p in enumerate(ps)]
                r["p1_codes_under_p2_teacher"] = dict(recon_mel=round(D.mel(X, Yo), 4), recon_probe=agg(acc),
                                                      bits=self.seq_bits(ar, ps, X, self.p1_tones_ids),
                                                      frac_ids_changed=round(sum(int(a != b) for r1, r2 in zip(self.p1_tones_ids, ids) for a, b in zip(r1, r2)) / max(1, sum(min(len(r1), len(r2)) for r1, r2 in zip(self.p1_tones_ids, ids))), 4))
            ev[ar] = r
        ev["eval_s"] = round(time.time() - t0, 1)
        self.rec["evals"][tag] = ev
        print("EVAL", tag, json.dumps(ev), flush=True)

    def flush_rate(self, phase):
        if not self.rate_acc:
            return
        by = {}
        for ar, kd, n in self.rate_acc:
            by.setdefault(f"{ar}/{kd}", []).append(n)
        self.rec["rate_log"].append(dict(step=self.step, phase=phase, **{k: round(sum(v) / len(v), 2) for k, v in by.items()}))
        self.rate_acc = []

    def run(self):
        a = self.a; self.rate_acc = []; self.last_codec = None
        tm = dict(encode=0.0, lm=0.0, world=0.0, codec=0.0)
        # P0: text only (the codec phase happened here; its result is the cached checkpoint)
        t0 = time.time()
        for _ in range(a.p0):
            X, Mo, v = self.text_batch(self.g_data, 16); self.lm_step(X, Mo, v); self.step += 1
        self.rec["timing"]["p0_s_per_step"] = round((time.time() - t0) / max(1, a.p0), 4)
        self.rec["evals"]["after_p0"] = dict(text_bpb=round(self.eval_text(), 4))
        print("after P0", self.rec["evals"]["after_p0"], flush=True)
        self.measure("boundary")
        phases = [("P1", a.p1, [("tones", 1.0)], [("tones", 1.0)], ["tones"]),
                  ("P2", a.p2, [("melody", 2.0), ("tones", 1.0)], [("melody", 1.0), ("tones", 1.0)], ["tones", "melody"])]
        for name, n, lm_mix, codec_mix, areas in phases:
            t0 = time.time(); tm = dict(encode=0.0, lm=0.0, world=0.0, codec=0.0)
            for i in range(n):
                loss = self.media_step(lm_mix, codec_mix, tm); self.step += 1
                if (i + 1) % a.meas == 0:
                    self.flush_rate(name)
                    self.measure(name)
                    print(name, i + 1, round(loss / math.log(2), 3), self.last_codec, round(time.time() - t0), flush=True)
            el = time.time() - t0
            self.rec["timing"][f"{name}_s_per_step"] = round(el / max(1, n), 4)
            self.rec["timing"][f"{name}_parts_s_per_step"] = {k: round(v / max(1, n), 4) for k, v in tm.items()}
            self.full_eval(f"after_{name}", areas, final=(name == "P2"))
        return self.rec


def agg(ds):
    if not ds:
        return {}
    return {k: round(sum(d[k] for d in ds) / len(ds), 3) for k in ds[0]} | {"n": len(ds)}


def codec_phase(arch, seed, steps, lr=1e-3, floor=0.3):
    """The codec phase (runs during P0 in the tree). aud/tones only (the area present). LR warms up
    over 100 steps and decays linearly to floor*lr; live arms then continue AT the floor (never zero)."""
    out = os.path.join(HERE, "ck", f"{arch}_s{seed}.pt")
    m = D.make_codec(arch, seed); opt = torch.optim.AdamW(m.parameters(), lr=lr, betas=(0.8, 0.99))
    g = torch.Generator().manual_seed(200 + seed + 50)
    t0 = time.time(); log = []
    for step in range(1, steps + 1):
        for gp in opt.param_groups:
            gp["lr"] = lr * min(1.0, step / 100) * (1 - (1 - floor) * step / steps)
        m.train(); xb = D.media_batch(g, [("tones", 1.0)], 16)
        loss, codes = m.train_loss(xb, g)
        opt.zero_grad(); loss.backward(); nn.utils.clip_grad_norm_(m.parameters(), 1.0); opt.step()
        if step % 250 == 0:
            log.append((step, round(time.time() - t0), round(loss.item(), 3), int(torch.unique(codes).numel())))
            print(arch, seed, log[-1], flush=True)
    info = dict(arch=arch, seed=seed, steps=steps, s=round(time.time() - t0), s_per_step=round((time.time() - t0) / steps, 4),
                params=sum(p.numel() for p in m.parameters()), log=log)
    torch.save(dict(student=m.state_dict(), opt=opt.state_dict(), info=info), out)
    print(json.dumps(info))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("arm"); ap.add_argument("seed", type=int); ap.add_argument("out")
    ap.add_argument("--p0", type=int, default=250); ap.add_argument("--p1", type=int, default=600)
    ap.add_argument("--p2", type=int, default=600); ap.add_argument("--every", type=int, default=2)
    ap.add_argument("--decay", type=float, default=0.995); ap.add_argument("--rho", type=float, default=0.1)
    ap.add_argument("--codec_lr", type=float, default=3e-4); ap.add_argument("--meas", type=int, default=150)
    ap.add_argument("--codec_steps", type=int, default=1500)
    a = ap.parse_args()
    if a.arm == "codec_phase":
        for arch in a.out.split(","):
            codec_phase(arch, a.seed, a.codec_steps)
        sys.exit(0)
    t0 = time.time()
    rec = Main(a).run()
    rec["wall_s"] = round(time.time() - t0)
    json.dump(rec, open(a.out, "w"), indent=1)
    print("DONE", a.arm, a.seed, rec["wall_s"])
