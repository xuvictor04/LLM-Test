"""Editable external memory for continual learning.

Thesis: knowledge lives HERE, not baked into the weights, so it can be updated or DELETED per-entry without
retraining -- and specifically so WRONG/stale information can be removed. Robustness comes from redundancy +
turnover (many entries cover overlapping ground; bad ones get culled), not from any single entry being stable.

Design (four decisions, each a knob so the formulas can be tuned later):
  WRITE   surprise-gated: store an item only if the model found it hard to predict (surprise = 1-p_model(true tok)
          >= write_gate). Tagged with a source id (provenance) so a whole domain's contributions can be deleted at once.
  READ    kNN over ACTIVE, not-flagged-wrong entries -> a soft token distribution (kNN-LM style).
  FORGET  delete(mask) / delete_src(id): remove entries. Cheap + local -- the editability the thesis is about.
  WRONG   is_wrong(): SELF-CONSISTENCY -- run the model on each entry's OWN context; flag entries whose stored token
          the model ranks in the high tail of implausibility (adaptive median+k*MAD). Excluded from reads / sweepable.

This module is deliberately standalone (torch only) so it can be unit-tested and dropped into any model.
"""
import torch


class EditableMemory:
    def __init__(self, cap, key_dim, device="cpu", vocab=256, write_gate=0.0, wrong_thresh=1.0, topk=8, ctx_w=0,
                 wrong_margin=1.5, wrong_min_n=3, flag_min_w=0.0, selfcon_thresh=2.5,
                 adaptive_gate=False, gate_target=0.5, gate_step=0.02, gate_floor=0.0, gate_ceil=0.95,
                 evict="recency", use_decay=0.98, decay_every=20000):
        self.cap, self.kd, self.dev, self.V = cap, key_dim, device, vocab
        self.write_gate = float(write_gate)      # write only items with surprise (1-p_model) >= this (0 = write everything)
        # ADAPTIVE GATE (optional): the surprise scale drifts as the base trains, so a FIXED gate is too permissive early
        # / too strict late. When on, the threshold self-calibrates to keep a stable write fraction (gate_target) at any
        # scale: it rises when firing above target (refractory), falls when quiet (receptivity returns).
        self.adaptive_gate = bool(adaptive_gate); self.gate_target = float(gate_target)
        self.gate_step = float(gate_step); self.gate_floor = float(gate_floor); self.gate_theta = float(write_gate)
        self.gate_ceil = float(gate_ceil)        # cap so the controller can't overshoot and starve writes (skewed-high surprise)
        # EVICTION: "recency" = circular overwrite (oldest dies regardless of value). "usage" = least-RETRIEVED dies,
        # so entries that stay useful survive -- the same relative-fitness selection the domains and fabric nodes use.
        # Without this, memory is the only population in the system with no selection pressure at all.
        self.evict = str(evict); self.use_decay = float(use_decay); self.decay_every = int(decay_every); self._wc = 0
        self.wrong_thresh = float(wrong_thresh)  # kept for API compat (the retrieval running-mean signal was removed;
        self.wrong_margin = float(wrong_margin)  #   wrongness is now self-consistency, so these three are accepted but
        self.wrong_min_n = int(wrong_min_n)      #   unused -- retained so existing constructor calls don't break)
        self.flag_min_w = float(flag_min_w)      # only JUDGE an entry on retrievals where it was a CLOSE match (weight
        #                                          >= this); loose cross-domain hits are noise that inflates genuine error
        self.selfcon_k = float(selfcon_thresh)   # SELF-CONSISTENCY: flag an entry as wrong if the model ranks its stored
        #   token this many robust-deviations (median + k*MAD) above the typical implausibility. Adaptive, so it tracks
        #   whatever scale the model's distribution produces (corrupt context->token pairs are the high tail).
        self.topk = int(topk)
        self.keys = torch.zeros(cap, key_dim, device=device)
        self.tok = torch.full((cap,), -1, dtype=torch.long, device=device)   # value = the next token to predict
        self.src = torch.full((cap,), -1, dtype=torch.long, device=device)   # provenance (which domain wrote it)
        self.selfcon = torch.full((cap,), -1.0, device=device)               # per-entry self-consistency implausibility
        #   (fraction of vocab the model ranks above the stored token, given the entry's own context); -1 = not checked
        self.use = torch.zeros(cap, device=device)                          # retrieval count (for turnover)
        self.active = torch.zeros(cap, dtype=torch.bool, device=device)
        self.ctx_w = int(ctx_w)                                              # if >0, store a raw context window per
        if self.ctx_w > 0:                                                   #   entry so keys can be RE-ENCODED (drift fix)
            self.ctx = torch.zeros(cap, self.ctx_w, dtype=torch.long, device=device)
        self.ptr = 0

    @property
    def n(self): return int(self.active.sum())

    # ---- WRITE (surprise-gated, provenance-tagged) ----
    def write(self, k, tok, src, surprise=None, ctx=None):
        """k:(B,d) keys, tok:(B,) next tokens, src:int domain id. surprise:(B,)=1-p_model(true tok) gates writing.
        ctx:(B,ctx_w) optional
        raw context window stored so keys can be re-encoded later (drift fix)."""
        k = k.detach()
        if surprise is not None:
            sd = surprise.detach()
            if self.adaptive_gate:
                keep = sd > self.gate_theta                  # gate on RELATIVE surprise (above the self-calibrated level)
                fired = float(keep.float().mean())           # controller: rise if firing above target, fall if below ->
                self.gate_theta = min(self.gate_ceil, max(self.gate_floor, self.gate_theta + self.gate_step * (fired - self.gate_target)))
            else:
                keep = sd >= self.write_gate                 # keep only tokens the model was unsure about (>= fixed gate)
            k, tok = k[keep], tok[keep]
            if ctx is not None: ctx = ctx[keep]
        m = k.size(0)
        if m == 0: return 0
        if self.evict == "usage" and int(self.active.sum()) >= self.cap:      # LEAST-USED dies (sampled, O(m) not O(cap))
            ns = int(min(self.cap, max(8 * m, 64)))
            cand = torch.randint(0, self.cap, (ns,), device=self.dev)
            kk = int(min(m, ns))
            idx = cand[self.use[cand].topk(kk, largest=False).indices]
            if idx.numel() < m:                                               # pad with circular if the sample was short
                pad = (torch.arange(m - idx.numel(), device=self.dev) + self.ptr) % self.cap
                idx = torch.cat([idx, pad])
        else:
            idx = (torch.arange(m, device=self.dev) + self.ptr) % self.cap    # circular overwrite (recency only)
        self.keys[idx] = torch.nn.functional.normalize(k, dim=-1)
        self.tok[idx] = tok.to(self.dev)
        self.src[idx] = int(src)
        if self.ctx_w > 0 and ctx is not None: self.ctx[idx] = ctx.to(self.dev)
        self.use[idx] = 0.0; self.active[idx] = True
        self.selfcon[idx] = -1.0                                              # new entry: self-consistency not yet checked
        self.ptr = int((self.ptr + m) % self.cap)
        self._wc += m                                                         # decay usage so it reflects RECENT utility
        if self.use_decay < 1.0 and self._wc >= self.decay_every:
            self.use *= self.use_decay; self._wc = 0
        return m

    # ---- RE-KEY (drift fix): replace stored keys with freshly-encoded ones ----
    def active_ctx(self):
        """Indices + stored context windows of active entries (to re-encode with the current model)."""
        ii = self.active.nonzero(as_tuple=True)[0]
        return ii, (self.ctx[ii] if self.ctx_w > 0 else None)

    def rekey(self, new_keys, idx):
        self.keys[idx] = torch.nn.functional.normalize(new_keys.detach(), dim=-1)

    # ---- READ (kNN over valid entries -> token distribution) ----
    def read(self, q, tau=0.1):
        """q:(B,d) -> (dist:(B,V), conf:(B,), hit_idx:(B,topk)). Excludes deleted + flagged-wrong entries."""
        B = q.size(0)
        valid = self.active & (~self.is_wrong())
        dist = torch.zeros(B, self.V, device=self.dev)
        conf = torch.zeros(B, device=self.dev)
        hit = torch.full((B, self.topk), -1, dtype=torch.long, device=self.dev)
        if int(valid.sum()) == 0:
            return dist, conf, hit, torch.zeros(B, self.topk, device=self.dev)
        vi = valid.nonzero(as_tuple=True)[0]
        K = self.keys[vi]                                                     # (M,d) already normalized
        sim = torch.nn.functional.normalize(q, dim=-1) @ K.t()                # (B,M)
        kk = min(self.topk, vi.numel())
        tv, ti = sim.topk(kk, dim=-1)                                         # (B,kk)
        w = torch.softmax(tv / tau, dim=-1)                                   # similarity weights
        gi = vi[ti]                                                           # global indices of the hits
        toks = self.tok[gi]                                                   # (B,kk)
        dist.scatter_add_(1, toks, w)                                         # soft vote into a token distribution
        conf = tv.max(-1).values.clamp(0, 1)
        hit[:, :kk] = gi
        wfull = torch.zeros(B, self.topk, device=self.dev); wfull[:, :kk] = w   # retrieval weights (0 for empty slots)
        self.use.index_add_(0, gi.reshape(-1), w.reshape(-1))                 # track usage
        return dist, conf, hit, wfull

    # ---- WRONG (SELF-CONSISTENCY: is each stored token plausible under the model given its OWN context?) ----
    def set_selfcon(self, idx, frac):
        """Record self-consistency implausibility per entry. frac in [0,1] = fraction of the vocabulary the model ranks
        ABOVE the entry's stored token, given the entry's OWN stored context (0 = the model's top pick; 1 = worst). A
        corrupt context->token pair is implausible (high frac); a genuine one -- even a novel one the model didn't
        predict as #1 -- is a near-miss the model still ranks near the top (low frac). This is a per-entry, single-shot
        signal: every entry is checked once, so unlike the retrieval signal it doesn't need repeated confident hits."""
        self.selfcon[idx] = frac.to(self.dev)

    def is_wrong(self):
        """Flagged wrong = self-inconsistent: the model ranks the stored token in the high tail of implausibility given
        the entry's OWN context. ADAPTIVE threshold (median + k*MAD over checked entries) tracks the model's distribution
        scale. (The old retrieval running-mean signal was removed -- superseded by this single-shot self-consistency.)"""
        checked = self.selfcon >= 0
        selfc = torch.zeros_like(self.active)
        if int(checked.sum()) > 10:
            v = self.selfcon[checked]
            med = v.median(); mad = (v - med).abs().median()
            thr = med + self.selfcon_k * (mad + 1e-6)
            selfc = self.active & checked & (self.selfcon >= thr)
        return selfc

    # ---- FORGET (the editability) ----
    def delete(self, mask):
        """mask:(cap,) bool -> deactivate those entries. Returns count removed."""
        rm = int((mask & self.active).sum())
        self.active[mask] = False
        return rm

    def delete_src(self, src):
        return self.delete(self.src == int(src))

    def reassign_src(self, old, new):
        """Remap provenance old->new (when the domain manager MERGES two domains). Keeps memory consistent with the
        managed domain set -- pruning/merging domains INDIRECTLY prunes+relabels their memory."""
        m = self.src == int(old); self.src[m] = int(new); return int(m.sum())

    def sweep_wrong(self):
        """Delete every entry currently flagged wrong (self-inconsistent: stored token implausible for its own context)."""
        return self.delete(self.is_wrong())

    def stats(self):
        act = self.active
        per_src = {}
        for s in self.src[act].unique().tolist():
            per_src[int(s)] = int((self.src == s).logical_and(act).sum())
        return {"n": self.n, "flagged_wrong": int(self.is_wrong().sum()), "per_source": per_src}
