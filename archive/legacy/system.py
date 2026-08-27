"""The overarching cognitive system, as one configurable module.

Pipeline:  bytes
  -> adaptive-tokenizer / NOVELTY signal (online byte-trigram frequency model)
  -> gist-routed MIXTURE OF EMBEDDERS (specializes per domain; collapse-free)
  -> TRAINABLE deep base encoder (+ dropout) : the floor-lever
  -> gist-routed, growable / self-halting / prunable ROUTER FABRIC
        operators per step: experts (nodes) | RE-EMBED | RE-ENCODE | HALT
        routers are RECURRENT (each step's control is fed back into the next routing query)
        the ROUTER decides whether to re-encode; novelty is one of its inputs
  -> EPISODIC (one-shot) MEMORY recall, blended into the readout, gated by confidence x novelty
  -> readout head

Key finding this architecture demonstrated at small scale: it DECOUPLES in-distribution fit
from out-of-distribution degradation -- memory carries the familiar via recall while the base
is spared from over-memorizing, so in-held CE drops without OOD getting worse.
"""
import os
import torch, torch.nn as nn, torch.nn.functional as F
from language import ByteLM

# ---------------------------------------------------------------- small parts
class Expert(nn.Module):
    """A fabric node: residual MLP (dim->4dim->dim). Swap for any dim->dim module."""
    def __init__(self, dim, hidden=None):
        super().__init__()
        hidden = hidden or dim * 4
        self.net = nn.Sequential(nn.Linear(dim, hidden), nn.GELU(), nn.Linear(hidden, dim))
    def forward(self, x): return x + self.net(x)

class InverseCounterpart(nn.Module):
    """Paired with an expert: reconstructs the expert's INPUT from its transform output.
    The reconstruction MSE is a LOCAL signal -- trains the expert to be information-preserving
    (Section 17 'inverse counterpart'). One per fabric node when COUNTERPARTS=1."""
    def __init__(self, dim, hidden=None):
        super().__init__()
        hidden = hidden or dim * 2
        self.net = nn.Sequential(nn.Linear(dim, hidden), nn.GELU(), nn.Linear(hidden, dim))
    def forward(self, y): return self.net(y)

class Nov:
    """Adaptive tokenizer / novelty signal: online byte-trigram frequencies. Rare trigram -> high novelty."""
    def __init__(self): self.cnt = {}
    def update(self, x_cpu):
        c = self.cnt
        for seq in x_cpu.tolist():
            for i in range(len(seq) - 2):
                k = (seq[i] << 16) | (seq[i + 1] << 8) | seq[i + 2]; c[k] = c.get(k, 0) + 1
    def score_pos(self, x_cpu):                 # (B,L) cpu -> (B,L) cpu novelty in (0,1]
        B, L = x_cpu.shape; out = torch.ones(B, L); xb = x_cpu.tolist(); g = self.cnt.get
        for b, seq in enumerate(xb):
            for i in range(L - 2):
                out[b, i] = 1.0 / (1.0 + g((seq[i] << 16) | (seq[i + 1] << 8) | seq[i + 2], 0))
        return out

class Mem:
    """Episodic one-shot memory: ring buffer of (key,value); single-exposure write; nearest-neighbour recall."""
    def __init__(self, cap, dim, device):
        self.cap, self.dim, self.device = cap, dim, device
        self.keys = torch.zeros(cap, dim, device=device); self.vals = torch.zeros(cap, dim, device=device)
        self.ptr = 0; self.n = 0
    def write(self, k, v):
        for i in range(k.size(0)):
            self.keys[self.ptr] = k[i]; self.vals[self.ptr] = v[i]
            self.ptr = (self.ptr + 1) % self.cap; self.n = min(self.n + 1, self.cap)
    def read(self, q):
        if self.n == 0: return torch.zeros_like(q), torch.zeros(q.size(0), device=q.device)
        ks = self.keys[:self.n]; sim = F.normalize(q, dim=-1) @ F.normalize(ks, dim=-1).t()
        w = torch.softmax(sim * 8.0, -1)
        return w @ self.vals[:self.n], sim.max(-1).values

class ReverseSurprise:
    """Novelty from the reverse/counterpart predictor: per-position next-byte error of the base LM.
    Replaces the unbounded trigram Nov.cnt -- no growing state, vectorized. novelty in (0,1]."""
    def __init__(self, base, device): self.base = base; self.device = device; self.last_ce = None
    def update(self, x_cpu): pass
    @torch.no_grad()
    def score_pos(self, x_cpu):
        B, Lc = x_cpu.shape; x = x_cpu.to(self.device)
        out = self.base(x); lg = out[0] if isinstance(out, tuple) else out
        V = lg.size(-1)
        ce_pos = F.cross_entropy(lg[:, :-1].reshape(-1, V), x[:, 1:].reshape(-1), reduction="none").reshape(B, Lc - 1)
        self.last_ce = (ce_pos.mean(1) / 0.6931471805599453).detach().cpu()   # per-example error in bits (for the write gate)
        nov = 1.0 - torch.exp(-ce_pos)
        o = torch.ones(B, Lc, device=x.device); o[:, :Lc - 1] = nov
        return o.cpu()

ReverseNov = ReverseSurprise   # back-compat alias (old scripts / checkpoints refer to ReverseNov)

class NullMem:
    """Memory ablation (MEMORY=off): no recall, no writes -- the readout gets mg*0."""
    def __init__(self, cap, dim, device):
        self.keys = torch.zeros(1, dim, device=device); self.vals = torch.zeros(1, dim, device=device)
        self.ptr = 0; self.n = 0
    def read(self, q): return torch.zeros_like(q), torch.zeros(q.size(0), device=q.device)
    def write(self, *a, **k): return 0

def ce(lg, idx):
    V = lg.size(-1)
    try:
        from config import cfg as _c; ls = float(getattr(_c, "LABEL_SMOOTH", 0.0))   # training-only; eval stays true CE
    except Exception:
        ls = 0.0
    return F.cross_entropy(lg[:, :-1].reshape(-1, V), idx[:, 1:].reshape(-1), label_smoothing=ls)

# ---------------------------------------------------------------- the system
class OverarchingSystem(nn.Module):
    def __init__(self, cfg, base: ByteLM):
        super().__init__()
        d, DK, M = cfg.D_MODEL, cfg.DK, cfg.M_EMBED
        V = cfg.VOCAB; VMAX = max(getattr(cfg, "VMAX", 0), V)
        self.cfg, self.d, self.DK, self.M, self.V, self.VMAX = cfg, d, DK, M, V, VMAX
        self.base = base
        self.norm_fab = nn.LayerNorm(d)
        self.init_emb = nn.Embedding(VMAX, d); self.routerA = nn.Linear(d, M)
        self.spec = nn.ModuleList([nn.Embedding(VMAX, d) for _ in range(M)]); self.head = nn.Linear(d, VMAX)
        _mtpk = max(1, int(getattr(cfg, "MTP_K", 1)))          # multi-token prediction: extra heads for t+2..t+K
        self.mtp_heads = nn.ModuleList([nn.Linear(d, VMAX) for _ in range(_mtpk - 1)])
        self.recon_head = nn.Linear(d, VMAX) if float(getattr(cfg, "RECON", 0.0)) > 0 else None   # per-position clean-token reconstruction
        self._nn_init = float(getattr(cfg, "NN_INIT", 0.0))         # warm-start new tokens from their nearest existing embedding
        self._nn_k = max(1, int(getattr(cfg, "NN_INIT_K", 1)))      # blend this many nearest neighbors (similarity-weighted)
        self._compose_w = float(getattr(cfg, "COMPOSE_EMB", 0.0))   # compositional embeddings: token vector from its constituent atoms
        if self._compose_w > 0:
            self.atom = nn.Embedding(VMAX, d); nn.init.normal_(self.atom.weight, std=0.02)
            self.register_buffer("parts", torch.arange(VMAX).unsqueeze(1).repeat(1, 2))   # token -> its 2 constituent tokens (base = itself)
            self._compose_depth = max(1, int(getattr(cfg, "COMPOSE_DEPTH", 1))); self._compose_g = 0.5
            self._comp_refresh = max(1, int(getattr(cfg, "COMPOSE_REFRESH", 1))); self._comp_cache = None; self._comp_dirty = False
            self.compose_lin = nn.Linear(2 * d, d)                  # learned composition of two child vectors
            with torch.no_grad():                                  # init so compose(u,v) ~= mean(u,v), then it learns
                W = torch.zeros(d, 2 * d); W[:, :d] = 0.5 * torch.eye(d); W[:, d:] = 0.5 * torch.eye(d)
                self.compose_lin.weight.copy_(W); self.compose_lin.bias.zero_()
        self._correct_stages = set(s for s in str(getattr(cfg, "CORRECT_AT", "none")).split(",") if s and s != "none")
        if self._correct_stages:                               # correction/modification hooks at ANY subset of stages
            def _corr():
                m = nn.Sequential(nn.Linear(d, d), nn.GELU(), nn.Linear(d, d))
                nn.init.zeros_(m[-1].weight); nn.init.zeros_(m[-1].bias); return m   # identity at init
            self.correct_nets = nn.ModuleDict({s: _corr() for s in self._correct_stages})
        for e in [self.init_emb] + list(self.spec): nn.init.normal_(e.weight, std=0.02)
        self.sense_k = int(getattr(cfg, "SENSE_K", 0))              # branches per token folder (0 = off, independent of MoE)
        self.sense_slots = int(getattr(cfg, "SENSE_SLOTS", 0))      # 0 = DENSE (every token); >0 = SPARSE, this many spawnable folders
        self.sense_pos = bool(getattr(cfg, "SENSE_POS", True))      # per-position routing (recovers within-sequence polysemy)
        self.n_promoted = 0
        if self.sense_k > 0:
            self.sense_route = nn.Linear(d, self.sense_k)          # context gist -> which branch of the folder
            if self.sense_slots > 0:                                # SPARSE: folders spawned on demand for surprising tokens
                self.register_buffer("tok2slot", torch.full((VMAX,), -1, dtype=torch.long))
                self.register_buffer("promote_score", torch.zeros(VMAX))
                self.sparse_sense = nn.Parameter(torch.randn(self.sense_slots, self.sense_k, d) * 0.02)
            else:                                                   # DENSE: every token carries a folder
                self.sense = nn.Parameter(torch.randn(VMAX, self.sense_k, d) * 0.02)
        self.nov_vec = nn.Parameter(torch.zeros(d))                  # novelty channel into embedder
        self.nov_proj = nn.Linear(1, DK); self.ctrl_proj = nn.Linear(4, DK); self.gate_lin = nn.Linear(2, 1)
        self.bodies = nn.ModuleList(); self.qproj = nn.ModuleList(); self.node_keys = nn.ParameterList()
        self.reembed_key = nn.Parameter(torch.randn(DK) * 0.1)
        self.reencode_key = nn.Parameter(torch.randn(DK) * 0.1)
        self.halt_key = nn.Parameter(torch.randn(DK) * 0.1)
        self.q_entry = nn.Linear(d, DK); self.q_reenc = nn.Linear(d, DK)
        self.usage = []
        self.surprise = Nov(); self.mem = None                            # mem created in init_runtime()
        self.counterparts = nn.ModuleList() if os.environ.get("COUNTERPARTS", "0") == "1" else None
        self.fabric_mode = getattr(cfg, "FABRIC", "dense")
        self._last_lb = torch.zeros(()); self._last_cpl = torch.zeros(())
        if self.fabric_mode == "sparse":                        # BARRY: stacked sparse top-k MoE replaces the dense loop
            from barry import SparseMoE
            k = int(getattr(cfg, "MOE_K", 2)); nl = int(getattr(cfg, "FABRIC_LAYERS", 2)); capf = float(getattr(cfg, "CAP_FACTOR", 1.25))
            cp = os.environ.get("COUNTERPARTS", "0") == "1"     # Barry now supports counterparts (stacked inverse bank)
            hid = max(1, int(d * float(getattr(cfg, "EXPERT_HIDDEN_MULT", 4.0))))   # <4*d bottlenecks the experts
            self.moe = nn.ModuleList([SparseMoE(d, k, k, hidden=hid, cap_factor=capf, counterparts=cp,
                                                cull_metric=str(getattr(cfg, "CULL_METRIC", "energy")),
                                                coord=float(getattr(cfg, "EXPERT_COORD", 0.0))) for _ in range(nl)])
            self.fab_norms = nn.ModuleList([nn.LayerNorm(d) for _ in range(nl)])
            self.bodies = nn.ModuleList([nn.Module() for _ in range(k)])   # sentinels -> len(bodies) tracks expert count
            self.usage = [0.1] * k
    # -- lifecycle --
    def device(self): return next(self.parameters()).device
    def init_runtime(self):
        # MirroredMemory is Greg's official memory (it won the ablation: best OOD + reduced forgetting).
        # MEMORY=ring (plain buffer) and MEMORY=off (NullMem) remain only for ablation comparisons.
        m = os.environ.get("MEMORY", "mirror")
        if m == "ring":
            self.mem = Mem(self.cfg.MEMCAP, self.d, self.device())
        elif m == "off":
            self.mem = NullMem(self.cfg.MEMCAP, self.d, self.device())
        else:                                                   # default + any unknown value -> mirror
            from mirrored_memory import MirroredMemory
            self.mem = MirroredMemory(self.cfg.MEMCAP, self.d, self.device())
    def add_node(self):
        dev = self.device()
        if self.fabric_mode == "sparse":                        # BARRY: grow every sparse-MoE layer's expert bank
            mut = int(getattr(self.cfg, "MUTATE", 0)) == 1; st = float(getattr(self.cfg, "MUTATE_STRENGTH", 0.05))
            cx = float(getattr(self.cfg, "CROSSOVER", 0.0))
            for layer in self.moe: layer.grow(1, mutate=mut, strength=st, crossover=cx)   # mutate best, or crossover top-2
            self.bodies.append(nn.Module().to(dev)); self.usage.append(0.1)
            return
        self.bodies.append(Expert(self.d).to(dev)); self.qproj.append(nn.Linear(self.d, self.DK).to(dev))
        self.node_keys.append(nn.Parameter((torch.randn(self.DK) * 0.1).to(dev))); self.usage.append(0.1)
        if self.counterparts is not None: self.counterparts.append(InverseCounterpart(self.d).to(dev))
    def cull_worst(self):
        """Evolutionary selection: remove the least-contributing expert (aggregated across layers). Returns True if culled."""
        if self.fabric_mode != "sparse" or len(self.bodies) <= int(getattr(self.cfg, "NMIN", 8)): return False
        scores = [l.score() for l in self.moe if l.score() is not None and l.score().numel() == self.moe[0].N]
        if not scores: return False
        idx = int(torch.stack(scores).sum(0).argmin())          # weakest expert by the configured selection signal
        for layer in self.moe: layer.prune(idx)
        self.bodies = nn.ModuleList([b for j, b in enumerate(self.bodies) if j != idx])
        self.usage = [u for j, u in enumerate(self.usage) if j != idx]
        return True
    def prune_node(self, i):
        if self.fabric_mode == "sparse": return                 # sparse culling goes through cull_worst (contribution-based)
        keep = [j for j in range(len(self.bodies)) if j != i]
        self.bodies = nn.ModuleList([self.bodies[j] for j in keep])
        self.qproj = nn.ModuleList([self.qproj[j] for j in keep])
        self.node_keys = nn.ParameterList([self.node_keys[j] for j in keep])
        self.usage = [self.usage[j] for j in keep]
        if self.counterparts is not None:
            self.counterparts = nn.ModuleList([self.counterparts[j] for j in keep])
    def counterpart_loss(self, h):
        """Mean inverse-reconstruction MSE over experts: each expert's transform must be invertible."""
        if self.fabric_mode == "sparse" or not self.counterparts: return h.new_zeros(())
        tot = h.new_zeros(())
        for i, b in enumerate(self.bodies):
            tot = tot + F.mse_loss(self.counterparts[i](b.net(h)), h)
        return tot / max(1, len(self.bodies))
    def _logits(self, h):                                   # slice head to the ACTIVE vocab V
        return F.linear(h, self.head.weight[:self.V], self.head.bias[:self.V])
    def grow_vocab(self, a, b):
        """Activate one more token across init/spec/head + base, mean-initialized from its parts."""
        with torch.no_grad():
            v = self.V
            if v >= self.VMAX: return False
            self.init_emb.weight[v] = 0.5 * (self.init_emb.weight[a] + self.init_emb.weight[b])
            for e in self.spec: e.weight[v] = 0.5 * (e.weight[a] + e.weight[b])
            if self._nn_init > 0 and v > 3:                    # warm-start from the NEAREST existing token(s)
                q = self.init_emb.weight[v]                    # the composed (mean-of-parts) query vector
                sim = F.cosine_similarity(q.unsqueeze(0), self.init_emb.weight[:v], dim=1)
                sim[a] = -2.0; sim[b] = -2.0                   # exclude its own parts
                w = self._nn_init
                if self._nn_k <= 1:
                    ti = sim.argmax().view(1); wts = None      # single nearest sibling
                else:
                    tv, ti = sim.topk(min(self._nn_k, v)); wts = torch.softmax(tv / 0.1, 0)   # top-K, similarity-weighted
                nbr = self.init_emb.weight[ti[0]] if wts is None else (wts.unsqueeze(1) * self.init_emb.weight[ti]).sum(0)
                self.init_emb.weight[v] = (1 - w) * q + w * nbr
                for e in self.spec:
                    en = e.weight[ti[0]] if wts is None else (wts.unsqueeze(1) * e.weight[ti]).sum(0)
                    e.weight[v] = (1 - w) * e.weight[v] + w * en
            if self.sense_k > 0 and self.sense_slots == 0: self.sense.data[v] = 0.5 * (self.sense.data[a] + self.sense.data[b])
            self.head.weight[v] = 0.5 * (self.head.weight[a] + self.head.weight[b])
            self.head.bias[v] = 0.5 * (self.head.bias[a] + self.head.bias[b])
            for mh in self.mtp_heads:                          # keep MTP heads' new-token rows initialized too
                mh.weight[v] = 0.5 * (mh.weight[a] + mh.weight[b]); mh.bias[v] = 0.5 * (mh.bias[a] + mh.bias[b])
            if self.recon_head is not None:
                self.recon_head.weight[v] = 0.5 * (self.recon_head.weight[a] + self.recon_head.weight[b])
                self.recon_head.bias[v] = 0.5 * (self.recon_head.bias[a] + self.recon_head.bias[b])
            if self._compose_w > 0:                            # record the new token's definition = its 2 constituent tokens
                self.parts[v] = torch.tensor([a, b], device=self.parts.device); self._comp_dirty = True
        self.base.grow_vocab(a, b); self.V += 1; return True
    # -- pieces --
    def Kmat(self): return torch.stack(list(self.node_keys) + [self.reembed_key, self.reencode_key, self.halt_key], 0)
    def embed(self, x, posnov):
        base_em = self.init_emb(x); g = base_em.mean(1)
        if len(self.spec):                                  # MoE EMBEDDER LAYER (toggle: M_EMBED=0 disables it)
            wA = torch.softmax(self.routerA(g), -1)
            sp = torch.stack([e(x) for e in self.spec], 0)
            em = base_em + (wA.permute(1, 0)[:, :, None, None] * sp).sum(0)
        else:                                               # layer off -> just the single initial embedder
            wA = g.new_zeros(g.size(0), 0); em = base_em
        if self._compose_w > 0:                             # COMPOSITIONAL EMBEDDING (recursive), cached for scale
            self._comp_calls = getattr(self, "_comp_calls", 0) + 1
            if self._comp_cache is None or self._comp_dirty or (self._comp_calls % self._comp_refresh == 0):
                V = self.V; comp = self.atom.weight[:V]     # recompute: gradients flow to atoms + compose_lin this forward
                pa = self.parts[:V, 0].clamp(max=V - 1); pb = self.parts[:V, 1].clamp(max=V - 1)
                for _ in range(self._compose_depth):        # each pass folds in one deeper level of constituents
                    composed = self.compose_lin(torch.cat([comp[pa], comp[pb]], -1))
                    comp = comp + self._compose_g * (composed - comp)
                self._comp_cache = comp.detach(); self._comp_dirty = False; use = comp
            else:
                use = self._comp_cache[:self.V]             # reuse cached table (detached; no compose grad this step)
            em = em + self._compose_w * use[x]              # token's recursively-composed "definition"
        if self.sense_k > 0:                                # SENSE BOOK: context picks a per-token sub-meaning branch
            if self.sense_pos:                              # per-position causal gist -> disambiguates same token by local context
                Lc = x.size(1)
                ctx = torch.cumsum(base_em, 1) / torch.arange(1, Lc + 1, device=x.device).view(1, -1, 1)
            else:
                ctx = g[:, None, :].expand(-1, x.size(1), -1)  # per-sequence gist (like the MoE router)
            ws = torch.softmax(self.sense_route(ctx), -1)   # (B, L, K)
            self.last_sense_w = ws.mean(1).detach()         # (B, K) for the sense-mix probe
            if self.sense_slots > 0:                        # SPARSE: gather only promoted folders; others get nothing
                slot = self.tok2slot[x]                     # (B, L), -1 where not promoted
                has = (slot >= 0).to(base_em.dtype)[..., None]
                sv = self.sparse_sense[slot.clamp(min=0)]   # (B, L, K, d)  (masked where -1)
                em = em + has * (ws[..., None] * sv).sum(2)
            else:                                           # DENSE: every token carries a folder
                sv = self.sense[x]                          # (B, L, K, d)
                em = em + (ws[..., None] * sv).sum(2)
        em = em + self.nov_vec[None, None, :] * posnov[:, :, None]
        return em, wA, g

    def promote_senses(self, x, posnov):
        """SPARSE sense: spawn a folder for a token once it has accumulated enough SURPRISE mass (gate-driven)."""
        if self.sense_k <= 0 or self.sense_slots <= 0 or self.n_promoted >= self.sense_slots: return
        with torch.no_grad():
            self.promote_score.index_add_(0, x.reshape(-1), posnov.reshape(-1).to(self.promote_score.dtype))
            thr = float(getattr(self.cfg, "SENSE_PROMOTE", 20.0))
            cand = ((self.promote_score > thr) & (self.tok2slot < 0)).nonzero(as_tuple=True)[0]
            for t in cand.tolist():
                if self.n_promoted >= self.sense_slots: break
                self.tok2slot[t] = self.n_promoted
                self.sparse_sense.data[self.n_promoted].normal_(0, 0.02)
                self.n_promoted += 1
    def encode_(self, emb):
        L = emb.size(1); h = emb + self.base.pos(torch.arange(L, device=emb.device))[None]
        for b in self.base.blocks: h = b(h)
        return self.base.ln_f(h)
    def re_embed(self, h): return torch.softmax(self._logits(h), -1) @ self.init_emb.weight[:self.V]
    def re_encode(self, h):
        hh = h
        for b in self.base.blocks: hh = b(hh)
        return self.base.ln_f(hh)
    def _ctrl_summary(self, c, N): return torch.stack([c[:, :N].sum(1), c[:, N], c[:, N + 1], c[:, N + 2]], -1)
    def _fabric_sparse(self, h0):
        """BARRY fabric: a stack of sparse top-k MoE layers -- each token routes to only its k experts."""
        B, L, d = h0.shape; h = h0; lb = h0.new_zeros(()); cpl = h0.new_zeros(()); load = None
        for i, layer in enumerate(self.moe):
            y, l = layer(h.reshape(B * L, d))
            h = self.fab_norms[i](y.reshape(B, L, d))
            lb = lb + l; load = layer.last_load
            if layer.last_cpl is not None: cpl = cpl + layer.last_cpl
        self._last_lb = lb; self._last_cpl = cpl
        N = self.moe[0].N; mass = h0.new_zeros(N + 3)
        if load is not None: mass[:N] = load.float() / (load.sum() + 1e-9)      # per-expert load, for the interface
        return h, h0.new_zeros(()), h0.new_zeros(()), mass                      # depth/enc not used by the sparse fabric
    def fabric(self, h0, gist, novs):
        if self.fabric_mode == "sparse": return self._fabric_sparse(h0)
        N = len(self.bodies); Kd = min(8, 3 + N // 2); K = self.Kmat(); novb = self.nov_proj(novs[:, None])
        c = torch.softmax((self.q_entry(gist) + novb) @ K.t(), -1); h = h0
        depth = h0.new_zeros(()); enc = h0.new_zeros(()); mass = torch.zeros(N + 3, device=h0.device); HALT = N + 2
        use_re = self.cfg.ENABLE_REENCODE
        re_by_surprise = getattr(self.cfg, "REENCODE_SURPRISE", False)
        for _ in range(Kd):
            nm = c[:, :N]; r_emb = c[:, N]; r_enc = c[:, N + 1]
            Bo = torch.stack([b(h) for b in self.bodies], 1)
            upd = (nm[:, :, None, None] * Bo).sum(1) + r_emb[:, None, None] * self.re_embed(h)
            if use_re:
                rc = r_enc * novs if re_by_surprise else r_enc   # focus re-perception on surprising inputs
                upd = upd + rc[:, None, None] * self.re_encode(h)
            h = self.norm_fab(h + self.cfg.ALPHA * (upd - h))
            depth = depth + (1 - c[:, HALT]).mean(); enc = enc + r_enc.mean(); mass = mass + c.mean(0).detach()
            bias = novb + self.ctrl_proj(self._ctrl_summary(c, N))   # novelty + recurrent control feedback
            Q = torch.stack([q(gist) for q in self.qproj], 1) + bias[:, None, :]
            Qre = (self.q_entry(gist) + bias)[:, None, :]; Qen = (self.q_reenc(gist) + bias)[:, None, :]
            Qall = torch.cat([Q, Qre, Qen], 1); R = torch.softmax(torch.einsum('bnk,mk->bnm', Qall, K), -1)
            nxt = torch.einsum('bn,bnm->bm', c[:, :HALT], R); nxt = nxt.clone(); nxt[:, HALT] = nxt[:, HALT] + c[:, HALT]; c = nxt
        return h, depth / Kd, enc / Kd, mass
    def readout(self, h_fab, gist, novs):
        recall, conf = self.mem.read(gist)
        mg = torch.sigmoid(self.gate_lin(torch.cat([conf[:, None], novs[:, None]], -1)))
        h_final = h_fab + (mg * recall)[:, None, :]
        mtp = [F.linear(h_final, mh.weight[:self.V], mh.bias[:self.V]) for mh in self.mtp_heads] if len(self.mtp_heads) else None
        recon = F.linear(h_final, self.recon_head.weight[:self.V], self.recon_head.bias[:self.V]) if self.recon_head is not None else None
        return self._logits(h_final), conf, mg, mtp, recon
    def forward(self, x, posnov):
        novs = posnov.mean(1)
        em, wA, gist = self.embed(x, posnov)
        if "emb" in self._correct_stages: em = em + self.correct_nets["emb"](em)        # post-tokenizer (rawest) correction
        h0 = self.encode_(em)
        if "hidden" in self._correct_stages: h0 = h0 + self.correct_nets["hidden"](h0)  # post-encode correction
        hf, depth, enc, mass = self.fabric(h0, gist, novs)
        if "fabric" in self._correct_stages: hf = hf + self.correct_nets["fabric"](hf)  # post-fabric (mid) correction
        lg, conf, mg, mtp, recon = self.readout(hf, gist, novs)
        cpl = self._last_cpl if self.fabric_mode == "sparse" else (self.counterpart_loss(h0) if self.counterparts else h0.new_zeros(()))
        return lg, dict(depth=depth, enc=enc, mass=mass, gist=gist, hf=hf, wA=wA, conf=conf, mg=mg, cpl=cpl, lb=self._last_lb, mtp=mtp, recon=recon)
    @torch.no_grad()
    def reconstruct(self, x):
        """Self-correction loop: reconstruction head predicts the clean token per position, then decode those
        corrected tokens to bytes and RE-ROUTE through the tokenizer (recovering proper merges). Needs RECON on
        and a dynamic tokenizer. Returns list of (corrected_ids, retokenized_ids) per row."""
        self.eval()
        pn = self.surprise.score_pos(x).to(x.device)
        _, aux = self(x, pn)
        recon = aux.get("recon")
        if recon is None: return None
        corrected = recon.argmax(-1)                            # (B, L): clean token guess at each position
        dyn = getattr(self, "dyntok", None); out = []
        for row in corrected:
            ids = [int(i) for i in row.tolist()]
            if dyn is not None:
                raw = b"".join(dyn.id2bytes[i] for i in ids if i < len(dyn.id2bytes))   # corrected tokens -> bytes
                retok = dyn.segment(list(raw), count=False)     # re-route through tokenizer -> proper merges
            else:
                raw, retok = bytes(ids), ids
            out.append((ids, retok, raw))
        return out

# ---------------------------------------------------------------- training helpers
def warmup_base(base, TRAIN, cfg, dev):
    flat = torch.cat([c for c in TRAIN]); L = cfg.CTX
    opt = torch.optim.Adam(base.parameters(), lr=2e-3); base.train()
    for _ in range(cfg.WARMUP_STEPS):
        ix = torch.randint(0, len(flat) - L - 1, (cfg.BATCH,))
        x = torch.stack([flat[i:i + L] for i in ix]).to(dev); y = torch.stack([flat[i + 1:i + L + 1] for i in ix]).to(dev)
        _, l = base(x, y); opt.zero_grad(); l.backward(); opt.step()

def seed_node(sysm, x, posnov, cfg):
    if getattr(sysm, "fabric_mode", "dense") == "sparse": return   # Barry's grown experts self-initialize
    em, _, _ = sysm.embed(x, posnov); f = sysm.encode_(em).detach(); nb = sysm.bodies[-1]
    so = torch.optim.Adam(nb.parameters(), lr=3e-3)
    for _ in range(8):
        hh = sysm.norm_fab(f + cfg.ALPHA * (nb(f) - f)); sl = ce(sysm.head(hh), x); so.zero_grad(); sl.backward(); so.step()

@torch.no_grad()
def evaluate_system(sysm, HELD, OOD, cfg):
    sysm.eval(); dev = sysm.device()
    bpe = getattr(sysm, "bpe", None); dyn = getattr(sysm, "dyntok", None); _LN2 = 0.6931471805599453
    cap = cfg.CTX
    def toks(c):
        """raw chunk -> (token tensor, predicted-byte-count). dynamic segments live (no minting)."""
        if dyn is not None:
            ids = dyn.segment(c.tolist(), count=False)[:cap]
            return torch.tensor(ids, dtype=torch.long), sum(dyn.blen(int(x)) for x in ids[1:])
        nb = sum(bpe.blen(int(x)) for x in c[1:]) if bpe is not None else int(c.numel() - 1)
        return c, nb
    def ce_set(cm):                                    # true bits/byte: sum(nats)/sum(bytes)/ln2
        r = {}
        for dm, cs in cm.items():
            tot_nats = 0.0; tot_bytes = 0
            for c in cs:
                t, nb = toks(c)
                if t.numel() < 2: continue
                xc = t[None].to(dev); pn = sysm.surprise.score_pos(t[None]).to(dev)
                lg, _ = sysm(xc, pn)
                tot_nats += float(F.cross_entropy(lg[0, :-1], xc[0, 1:], reduction="sum")); tot_bytes += nb
            r[dm] = round(tot_nats / max(1, tot_bytes) / _LN2, 4)
        return r
    def nov_conf(cm):
        nv, cf = {}, {}
        for dm, cs in cm.items():
            n = q = 0.0
            for c in cs:
                t, _ = toks(c); xc = t[None]
                if t.numel() < 1: continue
                n += float(sysm.surprise.score_pos(xc).mean())
                q += float(sysm.mem.read(sysm.init_emb(xc.to(dev)).mean(1))[1].mean())
            nv[dm] = round(n / max(1, len(cs)), 3); cf[dm] = round(q / max(1, len(cs)), 3)
        return nv, cf
    held = ce_set(HELD); ood = ce_set(OOD); nvh, cfh = nov_conf(HELD); nvo, cfo = nov_conf(OOD)
    sysm.train()
    return {"in_held": round(sum(held.values()) / max(1, len(held)), 4), "held_by_domain": held,
            "ood": round(sum(ood.values()) / max(1, len(ood)), 4) if ood else None, "ood_by_domain": ood,
            "nov_held": nvh, "nov_ood": nvo, "memconf_held": cfh, "memconf_ood": cfo}

@torch.no_grad()
def embed_mix(sysm, HELD):
    sysm.eval(); dev = sysm.device(); res = {}; dyn = getattr(sysm, "dyntok", None); cap = sysm.cfg.CTX
    for dm, cs in HELD.items():
        ws = []
        for c in cs[:8]:
            if dyn is not None:                              # dynamic: segment + cap to CTX (pos table is MAX_LEN)
                ids = dyn.segment(c.tolist(), count=False)[:cap]
                if not ids: continue
                c = torch.tensor(ids, dtype=torch.long)
            xc = c[None]; pn = sysm.surprise.score_pos(xc).to(dev); _, aux = sysm(xc.to(dev), pn); ws.append(aux["wA"][0])
        if ws: res[dm] = [round(float(v), 2) for v in torch.stack(ws).mean(0)]
    sysm.train(); return res

def sense_mix(sysm, HELD):
    """Per-domain mean sense-branch weights -- the sense-book analog of embed_mix (shows if branches specialize)."""
    if getattr(sysm, "sense_k", 0) <= 0: return {}
    sysm.eval(); dev = sysm.device(); res = {}; dyn = getattr(sysm, "dyntok", None); cap = sysm.cfg.CTX
    for dm, cs in HELD.items():
        ws = []
        for c in cs[:8]:
            if dyn is not None:
                ids = dyn.segment(c.tolist(), count=False)[:cap]
                if not ids: continue
                c = torch.tensor(ids, dtype=torch.long)
            xc = c[None]; pn = sysm.surprise.score_pos(xc).to(dev); sysm(xc.to(dev), pn); ws.append(sysm.last_sense_w[0])
        if ws: res[dm] = [round(float(v), 2) for v in torch.stack(ws).mean(0)]
    sysm.train(); return res

# ---------------------------------------------------------------- save / load
def build_system(cfg, dev):
    vmax = max(getattr(cfg, "VMAX", 0), cfg.VOCAB)
    base = ByteLM(vocab=cfg.VOCAB, d_model=cfg.D_MODEL, n_layers=cfg.N_LAYERS, n_heads=cfg.N_HEADS,
                  max_len=cfg.MAX_LEN, dropout=cfg.DROPOUT, vmax=vmax).to(dev)
    sysm = OverarchingSystem(cfg, base).to(dev); sysm.init_runtime()
    sysm.bpe = None; sysm.dyntok = None
    mode = getattr(cfg, "TOKENIZER", "")
    if mode == "dynamic":
        from tokenizer import DynamicTokenizer
        sysm.dyntok = DynamicTokenizer(vmax=vmax, min_pair=getattr(cfg, "MIN_PAIR", 200),
                                       dropout=getattr(cfg, "TOK_DROPOUT", 0.0))
    elif mode:
        from tokenizer import ByteBPE
        sysm.bpe = ByteBPE.load(mode)
    return sysm

def save_system(sysm, path, **extra):
    mem = {"keys": sysm.mem.keys.cpu(), "vals": sysm.mem.vals.cpu(), "ptr": sysm.mem.ptr, "n": sysm.mem.n}
    if hasattr(sysm.mem, "gate"):
        mem["branch"] = sysm.mem.branch; mem["theta"] = sysm.mem.gate.theta
        mem["writes"] = sysm.mem.writes; mem["skips"] = sysm.mem.skips
    torch.save({"state": sysm.state_dict(), "N": len(sysm.bodies), "usage": sysm.usage,
                "fabric": getattr(sysm, "fabric_mode", "dense"),
                "n_layers": len(sysm.base.blocks), "V": sysm.V,
                "cps": (sysm.counterparts is not None),     # self-describe: were counterparts used?
                "dyn_merges": (sysm.dyntok.merges if getattr(sysm, "dyntok", None) else None),
                "novcnt": getattr(sysm.surprise, "cnt", {}), "mem": mem, "sense_k": getattr(sysm, "sense_k", 0),
                "sense_slots": getattr(sysm, "sense_slots", 0), "n_promoted": getattr(sysm, "n_promoted", 0), **extra}, path)

def load_system(path, cfg, dev):
    ck = torch.load(path, map_location="cpu", weights_only=False)
    sysm = build_system(cfg, dev)
    if "cps" in ck:                                         # match checkpoint, not ambient COUNTERPARTS env
        sysm.counterparts = nn.ModuleList() if ck["cps"] else None
    ck_sk = ck.get("sense_k", 0); ck_ss = ck.get("sense_slots", 0)
    if ck_sk != getattr(sysm, "sense_k", 0) or ck_ss != getattr(sysm, "sense_slots", 0):
        for a in ("sense", "sense_route", "sparse_sense"):     # clear whatever the build made
            if hasattr(sysm, a): delattr(sysm, a)
        for b in ("tok2slot", "promote_score"):
            if b in sysm._buffers: del sysm._buffers[b]
        sysm.sense_k, sysm.sense_slots = ck_sk, ck_ss           # match the checkpoint, not ambient env
        if ck_sk > 0:
            sysm.sense_route = nn.Linear(sysm.d, ck_sk)
            if ck_ss > 0:
                sysm.register_buffer("tok2slot", torch.full((sysm.VMAX,), -1, dtype=torch.long))
                sysm.register_buffer("promote_score", torch.zeros(sysm.VMAX))
                sysm.sparse_sense = nn.Parameter(torch.randn(ck_ss, ck_sk, sysm.d) * 0.02)
            else:
                sysm.sense = nn.Parameter(torch.randn(sysm.VMAX, ck_sk, sysm.d) * 0.02)
    sysm.n_promoted = ck.get("n_promoted", getattr(sysm, "n_promoted", 0))
    for _ in range(ck["N"] - len(sysm.bodies)): sysm.add_node()   # top up to saved count (sparse starts at MOE_K)
    while len(sysm.base.blocks) < ck.get("n_layers", len(sysm.base.blocks)):
        sysm.base.grow_depth()                              # restore depth-grown layers before loading weights
    sysm.to(dev)
    sysm.load_state_dict(ck["state"])
    sysm.usage = ck["usage"]
    if hasattr(sysm.surprise, "cnt"): sysm.surprise.cnt = ck.get("novcnt", {})
    m = ck["mem"]; sysm.mem.keys = m["keys"].to(dev); sysm.mem.vals = m["vals"].to(dev); sysm.mem.ptr = m["ptr"]; sysm.mem.n = m["n"]
    if hasattr(sysm.mem, "gate"):
        sysm.mem.branch = m.get("branch", {})
        if "theta" in m: sysm.mem.gate.theta = m["theta"]
        sysm.mem.writes = m.get("writes", 0); sysm.mem.skips = m.get("skips", 0)
    if ck.get("dyn_merges") is not None and getattr(sysm, "dyntok", None) is not None:
        t = sysm.dyntok                                     # replay minted merges into the fresh tokenizer
        for a, b in ck["dyn_merges"]:
            ns = t.id2bytes[a] + t.id2bytes[b]
            t.id2bytes.append(ns); t.seq2id[ns] = len(t.id2bytes) - 1
            t.maxlen = max(t.maxlen, len(ns)); t.bytes_per_id.append(len(ns))
            t.mlbf[ns[0]] = max(t.mlbf[ns[0]], len(ns))
        t.merges = list(map(tuple, ck["dyn_merges"]))
    if "V" in ck: sysm.V = ck["V"]; sysm.base.V = ck["V"]   # restore active-vocab counters
    return sysm, ck
