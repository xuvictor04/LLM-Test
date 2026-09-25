"""Toy-scale stream prototype: one LM over one id space (bytes | specials | media block), trained on ONE
pass over a stream (RUN_EPOCHS=1) of  [area A = aud/tones media + text replay] then [area B = aud/melody
media + text replay], windows of CTX positions cut in order, OPT_BATCH_WINDOWS=B.

Arms (all start from the SAME codec-phase checkpoint and the SAME per-seed text-only LM checkpoint):
  frozen25  : proposal-03 baseline. 25 Hz spec-FSQ codec frozen after the codec phase; codes filled once.
  live25    : codec keeps training all run on its own loss (+ rehearsal of earlier areas, + assignment-
              stability hinge on earlier areas); the TOKENIZING SNAPSHOT is refreshed from the online codec
              every ACT windows; codes (re)encoded just in time at window cut when stale. Fixed 25 Hz.
  live25free: codec keeps training, NO snapshot and NO anchor: codes come from the online codec at every cut.
  live50bpe : THIS DESIGN. 50 Hz base, live codec as in live25, plus online acoustic BPE minting merges
              over the consumed windows; at each act the unconsumed tail is re-encoded with the new snapshot,
              re-segmented with all merges, spliced at the cursor, and RunClock.revise_epoch_length() keeps the
              cursor (Q-RUN-8 option (a)).
  live50def : as live50bpe but the re-segmentation is DEFERRED to an epoch roll that never comes (the
              tree's current TOK behaviour at RUN_EPOCHS=1): merges are minted, their rows sit in the
              softmax, no minted id ever reaches the data. Fixed 50 Hz.
Usage: python run_arm.py --arm live50bpe --seed 0 --out res/live50bpe_s0.json
"""
import os, sys, time, json, math, copy, argparse, bisect
os.environ.setdefault("OMP_NUM_THREADS", "1"); os.environ.setdefault("MKL_NUM_THREADS", "1")
import torch, torch.nn as nn, torch.nn.functional as F
torch.set_num_threads(1)
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import synth as S
import melody as M
import codec as K
import codec_lib as C
from bpe import MediaBPE

T2A, A2T, AUD_B, AUD_E, EOT, PAD = 256, 257, 258, 259, 260, 261
CODE_BASE, NBASE, MINT_SLOTS = 264, 1000, 512
NTOK = NBASE + MINT_SLOTS
V = CODE_BASE + NTOK
CTX, W = 128, 128
AREAS = {"A": dict(mod=S, train=S.TRAIN_COMBOS, all=S.all_combos(), held=S.HELDOUT_COMBOS),
         "B": dict(mod=M, train=M.TRAIN, all=M.all_combos(), held=M.HELDOUT)}
ARMS = {
    "frozen25":   dict(stride=2, live=0, anchor_w=0.0, snapshot=1, bpe="off"),
    "live25":     dict(stride=2, live=1, anchor_w=10.0, snapshot=1, bpe="off"),
    "live25free": dict(stride=2, live=1, anchor_w=0.0, snapshot=0, bpe="off"),
    "live50bpe":  dict(stride=1, live=1, anchor_w=10.0, snapshot=1, bpe="on"),
    "live50def":  dict(stride=1, live=1, anchor_w=10.0, snapshot=1, bpe="defer"),
    "frozen50":   dict(stride=1, live=0, anchor_w=0.0, snapshot=1, bpe="off"),
    "frozen50bpe": dict(stride=1, live=0, anchor_w=0.0, snapshot=1, bpe="on"),
}


def kind_of(area, p):
    return p[0] if area == "A" else "mel-" + p[0]


def caption(area, p):
    return AREAS[area]["mod"].caption(p)


def render(area, p, seed):
    return AREAS[area]["mod"].render(p, torch.Generator().manual_seed(seed))


# ---------------------------------------------------------------------------------------------- text
def markov_text(n, seed):
    """Order-2 Markov text over 15 symbols (same process as design-hybrid/corpus.py::markov_text)."""
    alpha = "etaoinshrdlu .,"
    g = torch.Generator().manual_seed(1234)
    k = len(alpha)
    gam = -torch.log(torch.rand(k * k, k, generator=g).clamp_min(1e-9))
    gam = gam ** (1 / 0.3)
    P = gam / gam.sum(-1, keepdim=True)
    gs = torch.Generator().manual_seed(seed)
    cdf = P.cumsum(-1).tolist(); u = torch.rand(n, generator=gs).tolist()
    a, b = 0, 1; out = []
    for i in range(n):
        c = min(k - 1, bisect.bisect_left(cdf[a * k + b], u[i]))
        out.append(alpha[c]); a, b = b, c
    return "".join(out).encode()


TEXT_EV = None


def text_eval_windows():
    global TEXT_EV
    if TEXT_EV is None:
        t = markov_text(40 * 200, 2)
        TEXT_EV = torch.tensor([list(t[i * 200:i * 200 + CTX + 1]) for i in range(40)])
    return TEXT_EV


# ---------------------------------------------------------------------------------------------- LM
_BASIS = torch.tensor([1, 8, 40, 200]); _LV = torch.tensor(K.LEVELS)
DIG = (torch.arange(NBASE).unsqueeze(1) // _BASIS) % _LV     # (1000, 4) FSQ lattice coordinates of each id


class LM(nn.Module):
    """media_rows='table': one free row per lattice id (proposal 03). 'lattice': a media id's input and
    output rows are sum_d E_d[coord_d] + a residual row (the LM_COMPOSE analogue over FSQ coordinates), so an
    encoder drift that moves a frame to a NEIGHBOURING lattice point changes one of four components."""
    def __init__(self, media_rows="table"):
        super().__init__()
        self.emb = nn.Embedding(V, W); self.rnn = nn.GRU(W, W, 2, batch_first=True); self.head = nn.Linear(W, V)
        self.media_rows = media_rows
        if media_rows == "lattice":
            self.lat_in = nn.ParameterList([nn.Parameter(torch.randn(L, W) * 0.5) for L in K.LEVELS])
            self.lat_out = nn.ParameterList([nn.Parameter((torch.rand(L, W) * 2 - 1) / (2 * math.sqrt(W))) for L in K.LEVELS])

    def start_lattice(self):
        """Called once when media enters: residual media rows start at zero so the lattice structure leads."""
        if self.media_rows == "lattice":
            with torch.no_grad():
                self.emb.weight[CODE_BASE:CODE_BASE + NBASE] = 0.0
                self.head.weight[CODE_BASE:CODE_BASE + NBASE] = 0.0

    def weights(self):
        E, Hw = self.emb.weight, self.head.weight
        if self.media_rows == "lattice":
            ai = sum(self.lat_in[d][DIG[:, d]] for d in range(4)); ao = sum(self.lat_out[d][DIG[:, d]] for d in range(4))
            E = torch.cat([E[:CODE_BASE], E[CODE_BASE:CODE_BASE + NBASE] + ai, E[CODE_BASE + NBASE:]])
            Hw = torch.cat([Hw[:CODE_BASE], Hw[CODE_BASE:CODE_BASE + NBASE] + ao, Hw[CODE_BASE + NBASE:]])
        return E, Hw

    def forward(self, x, h=None):
        E, Hw = self.weights()
        o, h = self.rnn(F.embedding(x, E), h)
        return F.linear(o, Hw, self.head.bias), h

    @torch.no_grad()
    def init_rows(self, new):
        """LM_NEW_ROW_INIT=mean: a minted id's rows start at the mean of its parents' (effective) rows."""
        for nid, a, b in new:
            E, Hw = self.weights()
            i, pa, pb = CODE_BASE + nid, CODE_BASE + a, CODE_BASE + b
            self.emb.weight[i] = 0.5 * (E[pa] + E[pb])
            self.head.weight[i] = 0.5 * (Hw[pa] + Hw[pb])
            self.head.bias[i] = 0.5 * (self.head.bias[pa] + self.head.bias[pb])


def allow_table(live):
    text_ok = torch.zeros(V, dtype=torch.bool); text_ok[:CODE_BASE] = True; text_ok[PAD] = False
    med_ok = torch.zeros(V, dtype=torch.bool); med_ok[CODE_BASE:CODE_BASE + live] = True; med_ok[AUD_E] = True
    return torch.stack([text_ok, med_ok])


def nll_masked(model, X, tmod, allow):
    logits, _ = model(X[:, :-1])
    lg = logits.masked_fill(~allow[tmod[:, 1:].long()], float("-inf"))
    return F.cross_entropy(lg.reshape(-1, V), X[:, 1:].reshape(-1), reduction="none").view(X.shape[0], -1)


def pretrain_text(seed, steps, B, path):
    torch.manual_seed(seed); model = LM()
    opt = torch.optim.AdamW(model.parameters(), lr=2e-3, weight_decay=0.0)
    text = markov_text(steps * B * CTX + CTX + 2, 100 + seed)
    allow = allow_table(NBASE)
    t0 = time.time()
    for s in range(steps):
        a = s * B * CTX
        X = torch.tensor(list(text[a:a + B * CTX + 1]))
        X = torch.stack([X[j * CTX:j * CTX + CTX + 1] for j in range(B)])
        nll = nll_masked(model, X, torch.zeros_like(X), allow)
        loss = nll.mean(); opt.zero_grad(); loss.backward(); nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step()
    bpb = eval_text(model, allow)
    torch.save(dict(model=model.state_dict(), opt=opt.state_dict(), text_bpb=bpb, steps=steps, s=time.time() - t0), path)
    return bpb


@torch.no_grad()
def eval_text(model, allow):
    X = text_eval_windows()
    nll = nll_masked(model, X, torch.zeros_like(X), allow)
    return nll[:, 16:].mean().item() / math.log(2)


# ---------------------------------------------------------------------------------------------- clock
class RunClock:
    """Toy RunClock with the Q-RUN-8 option (a) entry point."""
    def __init__(self):
        self.step = 0; self.epoch = 0; self.windows_in_epoch = None; self._in_epoch = 0
        self.epoch_revisions = 0

    def begin_epoch(self, n):
        self.windows_in_epoch = int(n); self._in_epoch = 0

    def revise_epoch_length(self, n):
        """Re-measure the epoch's length mid-epoch; the cursor (_in_epoch) is KEPT."""
        n = int(n)
        if n < self._in_epoch:
            raise ValueError(f"revise_epoch_length({n}) < windows already consumed ({self._in_epoch})")
        self.windows_in_epoch = n; self.epoch_revisions += 1

    def advance(self):
        self.step += 1; self._in_epoch += 1
        return self._in_epoch >= self.windows_in_epoch

    @property
    def in_epoch(self):
        return self._in_epoch

    def state(self):
        return dict(step=self.step, epoch=self.epoch, windows_in_epoch=self.windows_in_epoch,
                    in_epoch=self._in_epoch, epoch_revisions=self.epoch_revisions)

    def load(self, d):
        self.step, self.epoch, self.windows_in_epoch = d["step"], d["epoch"], d["windows_in_epoch"]
        self._in_epoch, self.epoch_revisions = d["in_epoch"], d["epoch_revisions"]


# ---------------------------------------------------------------------------------------------- world
class World(nn.Module):
    """Minimal WORLD.media_terms stand-in: predicts the tokenizing codec's NEXT continuous FSQ value b[t+1]
    from b[<=t]. Target is stop-gradient (encode() is no_grad): no WORLD gradient reaches the codec."""
    def __init__(self):
        super().__init__()
        self.rnn = nn.GRU(4, 64, 1, batch_first=True); self.out = nn.Linear(64, 4)

    def forward(self, b):
        o, _ = self.rnn(b)
        return self.out(o)


def world_rel(world, b):
    with torch.no_grad():
        pred = world(b[:, :-1])
        mse = (pred - b[:, 1:]).pow(2).mean().item()
        pers = (b[:, :-1] - b[:, 1:]).pow(2).mean().item()
    return mse / max(pers, 1e-9)


# ---------------------------------------------------------------------------------------------- run
class Run:
    def __init__(self, a):
        self.a = a; cfg = dict(ARMS[a.arm]); self.cfg = cfg
        if a.anchor_w is not None and cfg["anchor_w"] > 0:
            cfg["anchor_w"] = a.anchor_w
        self.stride = cfg["stride"]; self.F = S.SR // K.HOP // self.stride
        # ---- stream records (deterministic from seed)
        g = torch.Generator().manual_seed(1000 + a.seed)
        n_text = ((a.n_a + a.n_b) // a.text_every + 2) * a.text_len
        text = markov_text(n_text, 5000 + a.seed); tp = 0
        self.recs = []; self.media_idx = []
        for area, n in (("A", a.n_a), ("B", a.n_b)):
            tr = AREAS[area]["train"]
            for i in range(n):
                p = tr[int(torch.randint(len(tr), (1,), generator=g))]
                task = "t2a" if torch.rand(1, generator=g).item() < 0.5 else "a2t"
                sd = int(torch.randint(2 ** 31 - 1, (1,), generator=g))
                self.recs.append(("m", area, task, p, sd, len(self.media_idx))); self.media_idx.append(len(self.recs) - 1)
                if (i + 1) % a.text_every == 0:
                    self.recs.append(("t", area, text[tp:tp + a.text_len])); tp += a.text_len
            if area == "A":
                self.p2_end_rec = len(self.recs)
        t0 = time.time()
        self.wav = torch.stack([render(r[1], r[3], r[4]) for r in self.recs if r[0] == "m"]).half()
        self.t_render = time.time() - t0
        self.area_media = {ar: ([r for r in self.media_idx if self.recs[r][1] == ar],
                                [self.recs[r][5] for r in self.media_idx if self.recs[r][1] == ar]) for ar in ("A", "B")}
        # ---- eval / probe sets (fixed, disjoint seeds)
        self.ev = {}
        for area, seed, reps in (("A", 555, 4), ("B", 556, 6)):
            ge = torch.Generator().manual_seed(seed); ps, xs = [], []
            for p in AREAS[area]["all"]:
                for _ in range(reps):
                    ps.append(p); xs.append(AREAS[area]["mod"].render(p, ge))
            self.ev[area] = (ps, torch.stack(xs))
        # ---- codec: online (trainable), tokenizing snapshot, reference (codec-phase) for cumulative drift
        ck = torch.load(os.path.join(HERE, "ck", f"codec{50 if self.stride == 1 else 25}.pt"))
        self.codec = K.make_codec(self.stride); self.codec.load_state_dict(ck["model"])
        self.copt = torch.optim.AdamW(self.codec.parameters(), lr=a.codec_lr, betas=(0.8, 0.99))
        if a.codec_keep_opt:
            self.copt.load_state_dict(ck["opt"])
            for gp in self.copt.param_groups:
                gp["lr"] = a.codec_lr
        self.ref = copy.deepcopy(self.codec).eval()
        self.snap = copy.deepcopy(self.codec).eval() if cfg["snapshot"] else self.codec
        self.version = 0
        # ---- LM from the shared per-seed text checkpoint
        lk = torch.load(os.path.join(HERE, "ck", f"lm_p1_s{a.seed}.pt"))
        torch.manual_seed(a.seed)
        self.model = LM(a.media_rows); self.model.load_state_dict(lk["model"], strict=False)
        self.opt = torch.optim.AdamW(list(self.model.emb.parameters()) + list(self.model.rnn.parameters())
                                     + list(self.model.head.parameters()), lr=2e-3, weight_decay=0.0)
        self.opt.load_state_dict(lk["opt"])
        if a.media_rows == "lattice":
            self.model.start_lattice()
            self.opt.add_param_group(dict(params=list(self.model.lat_in) + list(self.model.lat_out), lr=2e-3, weight_decay=0.0))
        self.text_bpb_p1 = lk["text_bpb"]
        self.bpe = MediaBPE(NBASE, MINT_SLOTS, a.bpe_max_frames, a.bpe_min_pair)
        self.world = World(); torch.manual_seed(a.seed); self.world = World()
        self.wopt = torch.optim.Adam(self.world.parameters(), lr=1e-3)
        self.g_codec = torch.Generator().manual_seed(7000 + a.seed)
        self.clock = RunClock()
        self.cnt = dict(acts=0, mints=0, retok_mid_epoch=0, retok_deferred=0, minted_in_consumed=0,
                        media_pos_consumed=0, media_sec_consumed=0.0, codec_steps=0, jit_reencoded=0,
                        world_steps=0, stranded_mints=0)
        self.log = dict(acts=[], curve=[], evals={}, drift=[], rate=[])
        self.win = 0; self.last_act = 0; self.nflush = 0; self.last_mint = 0   # run-global flush count: cadences key on it, never on a local counter
        self.t = dict(lm=0.0, codec=0.0, act=0.0, jit=0.0, world=0.0, eval=0.0)
        # ---- initial segmentation of the whole stream (the proposal's in-place fill, done once)
        t0 = time.time()
        self.seg = self.segment(0, len(self.recs))
        self.t_build = time.time() - t0
        self.clock.begin_epoch(max(1, (len(self.seg["ids"]) - 1) // CTX))
        self.probe_prev = self.probe_codes(self.snap)
        self.probe_ref = self.probe_prev
        self.p2_done = False

    # ------------------------------------------------------------------ segmentation
    def segment(self, r0, r1):
        """Records [r0, r1) -> ids/rec/mod/ver tensors under the CURRENT tokenizing codec and merges."""
        midx = [self.recs[r][5] for r in range(r0, r1) if self.recs[r][0] == "m"]
        toks = {}
        if midx:
            codes = self.encode_media(midx)
            if self.cfg["bpe"] == "on":
                tl = self.bpe.apply(codes)
            else:
                tl = [codes[i] for i in range(codes.shape[0])]
            toks = dict(zip(midx, tl))
        ids, rec, mod = [], [], []
        for r in range(r0, r1):
            R = self.recs[r]
            if R[0] == "t":
                s = list(R[2]); ids += s; rec += [r] * len(s); mod += [0] * len(s); continue
            _, area, task, p, sd, mi = R
            cap = list(caption(area, p).encode())
            tk = (toks[mi] + CODE_BASE).tolist()
            if task == "t2a":
                s = [T2A] + cap + [AUD_B] + tk + [AUD_E]
                md = [0] * (len(cap) + 2) + [1] * (len(tk) + 1)
            else:
                s = [A2T, AUD_B] + tk + [AUD_E] + cap + [EOT]
                md = [0, 0] + [1] * (len(tk) + 1) + [0] * (len(cap) + 1)
            ids += s; rec += [r] * len(s); mod += md
        return dict(ids=torch.tensor(ids, dtype=torch.long), rec=torch.tensor(rec, dtype=torch.int32),
                    mod=torch.tensor(mod, dtype=torch.int8),
                    ver=torch.full((len(ids),), self.version, dtype=torch.int32))

    def jit_refresh(self, a, b):
        """Fixed-rate arms: media records overlapping positions [a, b) whose codes are stale (older tokenizing
        version) are re-encoded in place by the current tokenizing codec. Lengths never change."""
        if self.cfg["bpe"] == "on":
            return
        rr = self.seg["rec"][a:b]; vv = self.seg["ver"][a:b]; mm = self.seg["mod"][a:b]
        stale = torch.unique(rr[(vv != self.version) & (mm == 1)]).tolist()
        stale = [r for r in stale if self.recs[r][0] == "m"]
        if not stale:
            return
        t0 = time.time()
        codes = self.encode_media([self.recs[r][5] for r in stale])
        for j, r in enumerate(stale):
            lo = int(torch.searchsorted(self.seg["rec"], torch.tensor(r, dtype=torch.int32)))
            hi = int(torch.searchsorted(self.seg["rec"], torch.tensor(r, dtype=torch.int32), right=True))
            m = self.seg["mod"][lo:hi] == 1
            ids = self.seg["ids"][lo:hi]
            cpos = torch.nonzero(m & (ids >= CODE_BASE)).squeeze(1)
            assert cpos.numel() == codes.shape[1], (cpos.numel(), codes.shape)
            self.seg["ids"][lo + cpos] = codes[j] + CODE_BASE
            self.seg["ver"][lo:hi] = self.version
        self.cnt["jit_reencoded"] += len(stale); self.t["jit"] += time.time() - t0

    def encode_media(self, midx, chunk=512):
        out = []
        for i in range(0, len(midx), chunk):
            c, _ = K.encode(self.snap, self.wav[midx[i:i + chunk]].float()); out.append(c)
        return torch.cat(out)

    # ------------------------------------------------------------------ probes
    def probe_codes(self, codec):
        cA, _ = K.encode(codec, self.ev["A"][1]); cB, _ = K.encode(codec, self.ev["B"][1])
        return cA, cB

    def drift_record(self, tag):
        cur = self.probe_codes(self.snap)
        d = dict(tag=tag, window=self.win,
                 flipA_vs_prev=round((cur[0] != self.probe_prev[0]).float().mean().item(), 4),
                 flipB_vs_prev=round((cur[1] != self.probe_prev[1]).float().mean().item(), 4),
                 flipA_vs_codecphase=round((cur[0] != self.probe_ref[0]).float().mean().item(), 4),
                 flipB_vs_codecphase=round((cur[1] != self.probe_ref[1]).float().mean().item(), 4),
                 windows_since_prev=self.win - (self.log["drift"][-1]["window"] if self.log["drift"] else 0))
        self.log["drift"].append(d); self.probe_prev = cur

    # ------------------------------------------------------------------ codec + world steps
    def consumed_media(self, area):
        """Media indices of `area` whose records lie wholly before the cursor's record (already consumed)."""
        k0 = min(self.win * CTX, len(self.seg["rec"]) - 1)
        rcur = int(self.seg["rec"][k0])
        rl, ml = self.area_media[area]
        return ml[:bisect.bisect_left(rl, rcur)]

    def codec_step(self, cur_area):
        a = self.a; g = self.g_codec
        pools = {ar: self.consumed_media(ar) for ar in ("A", "B")}
        old = [ar for ar in ("A", "B") if ar != cur_area and pools[ar] and ar < cur_area]
        bs, n = 16, S.SR // 2
        picks, is_old = [], []
        for i in range(bs):
            ar = old[i % len(old)] if (old and i % 2 == 1) else cur_area
            pool = pools[ar]
            if not pool:
                ar = cur_area; pool = pools[ar]
            if not pool:
                return
            picks.append(pool[int(torch.randint(len(pool), (1,), generator=g))]); is_old.append(ar != cur_area)
        st = [int((S.SR - n) * torch.rand(1, generator=g).item()) for _ in picks]
        x = torch.stack([self.wav[m, s:s + n].float() for m, s in zip(picks, st)]).unsqueeze(1)
        amask = torch.tensor(is_old) if a.anchor_scope == "old" else torch.ones(bs, dtype=torch.bool)
        anc_codes = None
        if self.cfg["anchor_w"] > 0 and amask.any():
            anc_codes, _ = K.encode(self.snap, x[:, 0])
        self.codec.train()
        loss, codes, anc = K.codec_loss(self.codec, x, anc_codes, amask, self.cfg["anchor_w"])
        self.copt.zero_grad(); loss.backward(); nn.utils.clip_grad_norm_(self.codec.parameters(), 1.0); self.copt.step()
        self.codec.eval()
        self.cnt["codec_steps"] += 1
        if not self.cfg["snapshot"]:
            self.version += 1  # the online codec IS the tokenizing codec: every step makes stored codes stale

    def world_step(self, cur_area):
        pool = self.consumed_media(cur_area)
        if not pool:
            return
        g = self.g_codec
        picks = [pool[int(torch.randint(len(pool), (1,), generator=g))] for _ in range(4)]
        _, b = K.encode(self.snap, self.wav[picks].float())
        loss = (self.world(b[:, :-1]) - b[:, 1:]).pow(2).mean()
        self.wopt.zero_grad(); loss.backward(); self.wopt.step(); self.cnt["world_steps"] += 1

    # ------------------------------------------------------------------ the act (after a flush)
    def act(self):
        t0 = time.time(); a = self.a
        rec = dict(window=self.win, in_epoch=self.clock.in_epoch, wie_before=self.clock.windows_in_epoch)
        if self.cfg["bpe"] in ("on", "defer"):
            new = self.bpe.mint(a.bpe_burst, self.win)
            self.model.init_rows(new); self.cnt["mints"] += len(new); rec["minted"] = len(new)
        cur_area = self.recs[int(self.seg["rec"][min(self.win * CTX, len(self.seg["rec"]) - 1)])][1]
        wr_before = world_rel(self.world, K.encode(self.snap, self.ev[cur_area][1])[1])
        if self.cfg["live"] and self.cfg["snapshot"]:
            self.snap = copy.deepcopy(self.codec).eval(); self.version += 1
        if self.cfg["live"]:
            self.drift_record("act")
        rec["world_rel_before"] = round(wr_before, 4)
        rec["world_rel_after"] = round(world_rel(self.world, K.encode(self.snap, self.ev[cur_area][1])[1]), 4)
        if self.cfg["bpe"] == "on":
            k0 = self.win * CTX
            if k0 < len(self.seg["ids"]) - 1:
                r0 = int(self.seg["rec"][k0])
                p = int(torch.searchsorted(self.seg["rec"], torch.tensor(r0, dtype=torch.int32), right=True))
                old_len = len(self.seg["ids"]); prefix = self.seg["ids"][:p].clone()
                tail = self.segment(r0 + 1, len(self.recs))
                for k in ("ids", "rec", "mod", "ver"):
                    self.seg[k] = torch.cat([self.seg[k][:p], tail[k]])
                assert torch.equal(self.seg["ids"][:p], prefix)   # prefix preserved
                n = max(self.clock.in_epoch, (len(self.seg["ids"]) - 1) // CTX)
                ie = self.clock.in_epoch
                self.clock.revise_epoch_length(n)
                assert self.clock.in_epoch == ie                   # cursor kept
                self.cnt["retok_mid_epoch"] += 1
                rec.update(splice_pos=p, len_before=old_len, len_after=len(self.seg["ids"]), wie_after=n)
                mt = tail["mod"] == 1; tk = tail["ids"][mt]; tk = tk[tk >= CODE_BASE]
                nmed = sum(1 for r in range(r0 + 1, len(self.recs)) if self.recs[r][0] == "m")
                rec["tail_media_tokens_per_s"] = round(tk.numel() / max(1, nmed), 3)
                rec["tail_frac_minted"] = round((tk >= CODE_BASE + NBASE).float().mean().item(), 4) if tk.numel() else 0.0
        elif self.cfg["bpe"] == "defer":
            self.cnt["retok_deferred"] += 1
        self.bpe.reset_tally(0.0)
        self.cnt["acts"] += 1; self.t["act"] += time.time() - t0
        rec["s"] = round(time.time() - t0, 2)
        self.log["acts"].append(rec)

    # ------------------------------------------------------------------ main loop
    def run(self, max_steps=None, loss_trace=None):
        a = self.a; B = a.B; nstep = 0
        while True:
            left = self.clock.windows_in_epoch - self.clock.in_epoch
            if left <= 0:
                break
            if max_steps is not None and nstep >= max_steps:
                return False
            b = min(B, left)
            lo = self.win * CTX; hi = (self.win + b) * CTX + 1
            self.jit_refresh(lo, hi)
            X = torch.stack([self.seg["ids"][(self.win + j) * CTX:(self.win + j) * CTX + CTX + 1] for j in range(b)])
            Mo = torch.stack([self.seg["mod"][(self.win + j) * CTX:(self.win + j) * CTX + CTX + 1] for j in range(b)])
            ism = (Mo == 1) & (X >= CODE_BASE)
            if self.cfg["bpe"] in ("on", "defer"):
                self.bpe.observe((X - CODE_BASE).clamp_min(0), ism)
            allow = allow_table(self.bpe.size)
            t0 = time.time()
            self.model.train()
            nll = nll_masked(self.model, X, Mo, allow)
            loss = nll.mean(); self.opt.zero_grad(); loss.backward(); nn.utils.clip_grad_norm_(self.model.parameters(), 1.0); self.opt.step()
            self.t["lm"] += time.time() - t0
            if loss_trace is not None:
                loss_trace.append(loss.item())
            tm = Mo[:, 1:] == 1
            self.cnt["minted_in_consumed"] += int((X[:, 1:][tm] >= CODE_BASE + NBASE).sum())
            nm = int((ism[:, 1:]).sum()); self.cnt["media_pos_consumed"] += nm
            for _ in range(b):
                self.clock.advance()
            self.win += b; nstep += 1; self.nflush += 1
            if self.nflush % 50 == 0:
                with torch.no_grad():
                    tb = nll[~tm].mean().item() / math.log(2) if (~tm).any() else float("nan")
                    mb = nll[tm].mean().item() / math.log(2) if tm.any() else float("nan")
                self.log["curve"].append((self.win, round(tb, 4), round(mb, 4)))
            k0 = min(self.win * CTX, len(self.seg["rec"]) - 1)
            cur_area = self.recs[int(self.seg["rec"][k0])][1]
            if self.cfg["live"] and self.nflush % a.codec_every == 0:
                t1 = time.time()
                for _ in range(a.codec_per_flush):
                    self.codec_step(cur_area)
                self.t["codec"] += time.time() - t1
            t1 = time.time(); self.world_step(cur_area); self.t["world"] += time.time() - t1
            if a.mint_every and self.cfg["bpe"] == "on" and self.win - self.last_mint >= a.mint_every and self.win - self.last_act < a.act_every:
                new = self.bpe.mint(a.bpe_burst, self.win); self.model.init_rows(new); self.cnt["mints"] += len(new)
                self.cnt["mints_between_acts"] = self.cnt.get("mints_between_acts", 0) + len(new); self.last_mint = self.win
            if self.cfg["live"] and not self.cfg["snapshot"] and self.win - self.last_act >= a.act_every:
                self.drift_record("measure"); self.last_act = self.win
            elif (self.cfg["live"] or self.cfg["bpe"] != "off") and self.win - self.last_act >= a.act_every:
                self.act(); self.last_act = self.win
            if not self.p2_done and int(self.seg["rec"][k0]) >= self.p2_end_rec:
                self.p2_done = True
                t1 = time.time(); self.log["evals"]["after_A"] = self.evaluate(["A"], recon_areas=["A", "B"]); self.t["eval"] += time.time() - t1
                print("after_A", json.dumps(self.log["evals"]["after_A"])[:600], flush=True)
        return True

    # ------------------------------------------------------------------ evaluation
    def tokens_for(self, area):
        ps, X = self.ev[area]
        codes, b = K.encode(self.snap, X)
        tl = self.bpe.apply(codes) if self.cfg["bpe"] == "on" else [codes[i] for i in range(codes.shape[0])]
        return ps, X, codes, tl, b

    @torch.no_grad()
    def evaluate(self, lm_areas, recon_areas):
        self.model.eval(); allow = allow_table(self.bpe.size); out = dict(window=self.win)
        out["text_bpb"] = round(eval_text(self.model, allow), 4)
        for area in recon_areas:
            ps, X, codes, tl, b = self.tokens_for(area)
            Y = K.decode_codes(self.snap, codes)
            probe = AREAS[area]["mod"]
            ex = sum(probe.attr_acc(probe.probe(Y[i]), ps[i])["exact"] for i in range(len(ps))) / len(ps)
            out[f"{area}_codec"] = dict(mel=round(C.mel_dist(X.unsqueeze(1), Y.unsqueeze(1)).item(), 4),
                                        recon_probe_exact=round(ex, 3), codes_used=int(torch.unique(codes).numel()),
                                        world_rel_h1=round(world_rel(self.world, b), 4))
        for area in lm_areas:
            out[area] = self.eval_lm_area(area, allow)
        self.model.train()
        return out

    @torch.no_grad()
    def eval_lm_area(self, area, allow):
        ps, X, codes, tl, _ = self.tokens_for(area)
        mod = AREAS[area]["mod"]; held = AREAS[area]["held"]
        # likelihoods: t2a media bits (codes + END) per clip-second and per position; a2t caption bits/byte
        bits_s, bits_pos, capb, ntoks = [], [], [], []
        by_kind = {}
        for i, p in enumerate(ps):
            cap = list(caption(area, p).encode()); tk = (tl[i] + CODE_BASE).tolist()
            s = [T2A] + cap + [AUD_B] + tk + [AUD_E]; md = [0] * (len(cap) + 2) + [1] * (len(tk) + 1)
            X1 = torch.tensor([s]); nll = nll_masked(self.model, X1, torch.tensor([md], dtype=torch.int8), allow)[0]
            mb = nll[-(len(tk) + 1):].sum().item() / math.log(2)
            bits_s.append(mb); bits_pos.append(mb / (len(tk) + 1)); ntoks.append(len(tk))
            by_kind.setdefault(kind_of(area, p), []).append(len(tk))
            s2 = [A2T, AUD_B] + tk + [AUD_E] + cap + [EOT]; md2 = [0, 0] + [1] * (len(tk) + 1) + [0] * (len(cap) + 1)
            nll2 = nll_masked(self.model, torch.tensor([s2]), torch.tensor([md2], dtype=torch.int8), allow)[0]
            capb.append(nll2[-(len(cap) + 1):-1].mean().item() / math.log(2))
        res = dict(bits_per_s=round(sum(bits_s) / len(bits_s), 2), bits_per_pos=round(sum(bits_pos) / len(bits_pos), 4),
                   caption_bits_per_byte=round(sum(capb) / len(capb), 4),
                   positions_per_s=round(sum(ntoks) / len(ntoks), 2),
                   positions_per_s_by_kind={k: round(sum(v) / len(v), 2) for k, v in sorted(by_kind.items())})
        # understanding: greedy caption
        und = {"train": [], "held": []}
        hs, last = [], []
        for i, p in enumerate(ps):   # prompts differ in length under BPE: one forward each, then batched greedy
            lg, h = self.model(torch.tensor([[A2T, AUD_B] + (tl[i] + CODE_BASE).tolist() + [AUD_E]]))
            hs.append(h); last.append(lg[:, -1])
        h = torch.cat(hs, 1); nxt = torch.cat(last, 0); Bn = len(ps)
        outs = [[] for _ in range(Bn)]; done = [False] * Bn
        for _ in range(40):
            t = nxt.masked_fill(~allow[0], float("-inf")).argmax(-1)
            for i in range(Bn):
                if not done[i]:
                    if int(t[i]) >= 256:
                        done[i] = True
                    else:
                        outs[i].append(int(t[i]))
            if all(done):
                break
            lg, h = self.model(t.unsqueeze(1), h); nxt = lg[:, -1]
        for i, p in enumerate(ps):
            d = mod.attr_acc(mod.parse_caption(bytes(outs[i]).decode(errors="replace")), p)
            und["held" if p in held else "train"].append(d["exact"])
        res["understand_exact_train"] = round(sum(und["train"]) / len(und["train"]), 3)
        res["understand_exact_heldout"] = round(sum(und["held"]) / len(und["held"]), 3)
        for temp in (1.0, 0.7):
            res[f"generate_t{temp}"] = self.generate(area, allow, temp)
        if self.cfg["bpe"] == "on":   # same END rule as the fixed-rate arms: END only once F frames are out
            res["generate_t0.7_dur"] = self.generate(area, allow, 0.7, dur=True)
        return res

    @torch.no_grad()
    def generate(self, area, allow, temp, reps=None, dur=False):
        mod = AREAS[area]["mod"]; held = AREAS[area]["held"]
        reps = reps or (3 if area == "A" else 4)
        g = torch.Generator().manual_seed(5)
        ps = [p for p in AREAS[area]["all"] for _ in range(reps)]
        B = len(ps); hs, last = [], []
        for p in ps:
            lg, h = self.model(torch.tensor([[T2A] + list(caption(area, p).encode()) + [AUD_B]])); hs.append(h); last.append(lg[:, -1])
        h = torch.cat(hs, 1); nxt = torch.cat(last, 0)
        seqs = [[] for _ in range(B)]; nfr = [0] * B; done = [False] * B
        maxsteps = self.F if self.cfg["bpe"] != "on" else self.F + 1
        for t in range(maxsteps):
            lg = nxt.masked_fill(~allow[1], float("-inf"))
            if self.cfg["bpe"] != "on" or dur:
                lg[:, AUD_E] = float("-inf")    # baseline grammar: exactly F frames, END forced after
            tok = torch.multinomial((lg / temp).softmax(-1), 1, generator=g)[:, 0]
            for i in range(B):
                if done[i]:
                    continue
                ti = int(tok[i])
                if ti == AUD_E:
                    done[i] = True; continue
                ex = self.bpe.expand(ti - CODE_BASE)
                seqs[i] += ex; nfr[i] += len(ex)
                if nfr[i] >= self.F:
                    done[i] = True
            if all(done):
                break
            logits, h = self.model(tok.unsqueeze(1), h); nxt = logits[:, -1]
        lens = [len(s) for s in seqs]
        codes = torch.zeros(B, self.F, dtype=torch.long)
        n_short = 0
        wavs = []
        sil = int(K.encode(self.snap, torch.zeros(1, S.SR))[0][0, self.F // 2])  # the codec's own silence id
        for i, s in enumerate(seqs):
            s = s[:self.F]
            if len(s) < self.F:
                n_short += 1
                s = s + [sil] * (self.F - len(s))    # predicted END before 1 s: the rest is silence
            wavs.append(K.decode_codes(self.snap, torch.tensor([s]))[0])
        res = {"train": [], "held": []}
        for i, p in enumerate(ps):
            d = mod.attr_acc(mod.probe(wavs[i]), p)
            res["held" if p in held else "train"].append(d["exact"])
        return dict(exact_train=round(sum(res["train"]) / len(res["train"]), 3),
                    exact_heldout=round(sum(res["held"]) / len(res["held"]), 3),
                    mean_frames=round(sum(lens) / B, 1), short=n_short)

    # ------------------------------------------------------------------ checkpoint / resume
    def state(self):
        k0 = self.win * CTX
        r0 = int(self.seg["rec"][min(k0, len(self.seg["rec"]) - 1)])
        p = int(torch.searchsorted(self.seg["rec"], torch.tensor(r0, dtype=torch.int32), right=True))
        return dict(
            arm=self.a.arm, seed=self.a.seed, model=self.model.state_dict(), opt=self.opt.state_dict(),
            codec=self.codec.state_dict(), copt=self.copt.state_dict(),
            snap=self.snap.state_dict() if self.cfg["snapshot"] else None, version=self.version,
            bpe=self.bpe.state_dict(), world=self.world.state_dict(), wopt=self.wopt.state_dict(),
            g_codec=self.g_codec.get_state(), clock=self.clock.state(), win=self.win, last_act=self.last_act, nflush=self.nflush, last_mint=self.last_mint,
            # byte-cursor analogue: the record under the cursor and the unconsumed remainder of ITS ids
            # (segmented under an older state); everything after it re-segments from (snapshot, merges).
            cursor=dict(k0=k0, rec=r0, rem_ids=self.seg["ids"][k0:p].clone(), rem_rec=self.seg["rec"][k0:p].clone(),
                        rem_mod=self.seg["mod"][k0:p].clone(), rem_ver=self.seg["ver"][k0:p].clone()),
            cnt=dict(self.cnt), p2_done=self.p2_done, probe_prev=self.probe_prev)

    def load(self, d):
        self.model.load_state_dict(d["model"]); self.opt.load_state_dict(d["opt"])
        self.codec.load_state_dict(d["codec"]); self.copt.load_state_dict(d["copt"])
        if self.cfg["snapshot"]:
            self.snap.load_state_dict(d["snap"])
        self.version = d["version"]; self.bpe.load_state_dict(d["bpe"])
        self.world.load_state_dict(d["world"]); self.wopt.load_state_dict(d["wopt"])
        self.g_codec.set_state(d["g_codec"]); self.win = d["win"]; self.last_act = d["last_act"]; self.nflush = d["nflush"]; self.last_mint = d["last_mint"]
        self.cnt = dict(d["cnt"]); self.p2_done = d["p2_done"]; self.probe_prev = d["probe_prev"]
        cur = d["cursor"]
        tail = self.segment(cur["rec"] + 1, len(self.recs))
        # rebuild: a dummy prefix of k0 positions (consumed; never read again) + remainder + fresh tail
        k0 = cur["k0"]
        pre = dict(ids=torch.full((k0,), PAD, dtype=torch.long), rec=torch.full((k0,), -1, dtype=torch.int32),
                   mod=torch.zeros(k0, dtype=torch.int8), ver=torch.zeros(k0, dtype=torch.int32))
        rem = dict(ids=cur["rem_ids"], rec=cur["rem_rec"], mod=cur["rem_mod"], ver=cur["rem_ver"])
        self.seg = {k: torch.cat([pre[k], rem[k], tail[k]]) for k in pre}
        self.seg["rec"][:k0] = cur["rec"]  # consumed prefix: only its record index is ever read (cursor lookups)
        self.clock.load(d["clock"])
        n = max(self.clock.in_epoch, (len(self.seg["ids"]) - 1) // CTX)
        self.remeasure = (n, self.clock.windows_in_epoch)
        print("CRITIC remeasure", n, "saved", self.clock.windows_in_epoch, "MATCH" if n == self.clock.windows_in_epoch else "MISMATCH -> the synthesis's resume rule refuses", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", default="live50bpe"); ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--n_a", type=int, default=8000); ap.add_argument("--n_b", type=int, default=8000)
    ap.add_argument("--text_every", type=int, default=4); ap.add_argument("--text_len", type=int, default=96)
    ap.add_argument("--B", type=int, default=8)
    ap.add_argument("--codec_every", type=int, default=4, help="AUD_TRAIN_EVERY in LM steps (B windows each)")
    ap.add_argument("--codec_lr", type=float, default=5e-5, help="live codec LR = the codec-phase schedule's floor (1e-3 x 0.05)")
    ap.add_argument("--codec_keep_opt", type=int, default=1)
    ap.add_argument("--anchor_scope", default="all"); ap.add_argument("--anchor_w", type=float, default=None,
                                                                   help="override the arm's AUD_ANCHOR_W (live arms default 10)")
    ap.add_argument("--act_every", type=int, default=2000, help="windows between acts (snapshot refresh + mint + retok)")
    ap.add_argument("--bpe_burst", type=int, default=32); ap.add_argument("--bpe_min_pair", type=int, default=50)
    ap.add_argument("--bpe_max_frames", type=int, default=16)
    ap.add_argument("--p1_steps", type=int, default=800)
    ap.add_argument("--media_rows", default="table", help="table | lattice (LM media rows from FSQ coordinates)")
    ap.add_argument("--resume_test", type=int, default=0, help="steps before a save/restore; compares continuation")
    ap.add_argument("--codec_per_flush", type=int, default=1, help="CRITIC: codec steps per codec cadence fire")
    ap.add_argument("--mint_every", type=int, default=0, help="CRITIC: mint on a separate cadence between acts (TOK_GROW_EVERY shape)")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    os.makedirs(os.path.join(HERE, "ck"), exist_ok=True)
    p1 = os.path.join(HERE, "ck", f"lm_p1_s{a.seed}.pt")
    if not os.path.exists(p1):
        print("text P1", a.seed, pretrain_text(a.seed, a.p1_steps, a.B, p1), flush=True)
    if a.resume_test:
        return resume_test(a)
    T0 = time.time()
    run = Run(a)
    print(f"built: records={len(run.recs)} positions={len(run.seg['ids'])} windows={run.clock.windows_in_epoch} "
          f"render_s={run.t_render:.1f} build_s={run.t_build:.1f}", flush=True)
    wie0 = run.clock.windows_in_epoch
    run.run()
    t1 = time.time(); final = run.evaluate(["A", "B"], recon_areas=["A", "B"]); run.t["eval"] += time.time() - t1
    k_last = run.win * CTX
    res = dict(arm=a.arm, seed=a.seed, args=vars(a), cfg=run.cfg, fps_base=run.F,
               text_bpb_after_text_phase=round(run.text_bpb_p1, 4),
               after_A=run.log["evals"].get("after_A"), final=final,
               windows_initial=wie0, windows_final=run.clock.windows_in_epoch, windows_consumed=run.win,
               clock=run.clock.state(), counters=run.cnt, bpe_size=run.bpe.size, bpe_refused_len=run.bpe.refused_len,
               unconsumed_tail_positions=len(run.seg["ids"]) - k_last,
               wall_s=round(time.time() - T0, 1), timers={k: round(v, 1) for k, v in run.t.items()},
               s_per_step_lm=round(run.t["lm"] / max(1, run.clock.step / a.B), 4),
               s_per_window_total=round((time.time() - T0 - run.t["eval"]) / max(1, run.win), 5),
               acts=run.log["acts"], drift=run.log["drift"], curve=run.log["curve"])
    print(json.dumps({k: v for k, v in res.items() if k not in ("curve", "acts", "drift")}, indent=1))
    if a.out:
        os.makedirs(os.path.dirname(os.path.join(HERE, a.out)), exist_ok=True)
        json.dump(res, open(os.path.join(HERE, a.out), "w"), indent=1)
        torch.save(dict(model=run.model.state_dict(), snap=run.snap.state_dict(), bpe=run.bpe.state_dict(), version=run.version),
                   os.path.join(HERE, "ck", "final_" + os.path.basename(a.out).replace(".json", ".pt")))


def resume_test(a):
    """Uninterrupted run vs save at step s -> fresh process-equivalent objects -> continue. Losses must match."""
    t0 = time.time()
    A = Run(a); la = []; A.run(loss_trace=la)
    Bq = Run(a); lb = []; Bq.run(max_steps=a.resume_test, loss_trace=lb)
    path = os.path.join(HERE, "ck", f"resume_{a.arm}_s{a.seed}.pt"); torch.save(Bq.state(), path)
    acts_before = Bq.cnt["acts"]; del Bq
    Cq = Run(a); Cq.load(torch.load(path, weights_only=False)); lc = []; Cq.run(loss_trace=lc)
    cont = lb + lc
    n = min(len(la), len(cont))
    diff = max(abs(x - y) for x, y in zip(la[:n], cont[:n])) if n else None
    res = dict(arm=a.arm, seed=a.seed, steps_uninterrupted=len(la), steps_resumed_total=len(cont), save_at_step=a.resume_test,
               acts_before_save=acts_before, acts_total=A.cnt["acts"], max_abs_loss_diff=diff,
               bit_identical=(la == cont), remeasured_vs_saved=getattr(Cq, "remeasure", None), mints_between_acts=A.cnt.get("mints_between_acts", 0), windows_final_A=A.clock.windows_in_epoch, windows_final_C=Cq.clock.windows_in_epoch,
               epoch_revisions_A=A.clock.epoch_revisions, epoch_revisions_C=Cq.clock.epoch_revisions, s=round(time.time() - t0, 1))
    print(json.dumps(res, indent=1))
    if a.out:
        json.dump(res, open(os.path.join(HERE, a.out), "w"), indent=1)


if __name__ == "__main__":
    main()
