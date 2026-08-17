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
                 evict="recency", use_decay=0.98, decay_every=20000, quantile_gate=True,
                 n_own=1, quota=None, src_floor=0.5, n_src_hint=64):
        # PER-OWNER PARTITION (n_own > 1): the store is split into n_own contiguous blocks of `quota` entries, one per
        # expert, and an entry lives at index owner*quota + slot. Eviction is per-owner LRU on LAST-USE TIME -- not
        # self.use, which is a decayed retrieval COUNT (an LFU signal, and decayed by WRITE count rather than time).
        # Rationale: a global recency FIFO gives every expert the same 66-second window regardless of how useful its
        # entries are, and makes the whole store one undifferentiated pool. Partitioning gives each expert a small,
        # bounded, independently-managed memory -- partial compartmentalization at the storage level -- while READS
        # stay global so information can still mix.
        self.n_own = max(1, int(n_own))
        self.quota = int(quota) if quota else int(cap // self.n_own)
        if self.n_own > 1: cap = self.n_own * self.quota          # cap is DERIVED from the partition
        self.cap, self.kd, self.dev, self.V = cap, key_dim, device, vocab
        self.own = torch.full((cap,), -1, dtype=torch.long, device=device)   # which expert owns each slot
        self.last = torch.zeros(cap, dtype=torch.long, device=device)        # LAST-USE TICK (monotonic), for true LRU
        self.tick = 0
        self.write_gate = float(write_gate)      # write only items with surprise (1-p_model) >= this (0 = write everything)
        # ADAPTIVE GATE (optional): the surprise scale drifts as the base trains, so a FIXED gate is too permissive early
        # / too strict late. When on, the threshold self-calibrates to keep a stable write fraction (gate_target) at any
        # scale: it rises when firing above target (refractory), falls when quiet (receptivity returns).
        self.adaptive_gate = bool(adaptive_gate); self.gate_target = float(gate_target)
        self.gate_step = float(gate_step); self.gate_floor = float(gate_floor); self.gate_theta = float(write_gate)
        self.gate_ceil = float(gate_ceil)        # cap so the controller can't overshoot and starve writes (skewed-high surprise)
        self.quantile_gate = bool(quantile_gate) # honour gate_target by QUANTILE rather than an absolute threshold (see _gate)
        # EVICTION. Three rules, and the difference between them is WHICH CLOCK decides who dies:
        #   "recency" = circular overwrite. WRITE order. The oldest write dies regardless of value, so a domain that
        #               stops being written is erased on a fixed schedule whether or not anything still needs it.
        #   "usage"   = least-RETRIEVED dies (LFU on decayed retrieval mass).
        #   "lru"     = least-recently-RETRIEVED dies. USE-BASED RECENCY: the clock is reads, not writes, so a quiet
        #               domain that still answers queries stays and a loud domain nothing asks for goes.
        # "usage" and "lru" are the selection pressure memory otherwise has none of -- the same relative-fitness rule
        # the domains and fabric nodes live under. Both are only real if reads HAPPEN during training; with reads
        # confined to eval, `use` stays 0 everywhere and `last` stays at write time, and both degenerate to FIFO.
        self.evict = str(evict); self.use_decay = float(use_decay); self.decay_every = int(decay_every); self._wc = 0
        self.pos = torch.zeros(cap, dtype=torch.long, device=device)   # SOURCE POSITION of each entry: lets retrieval
                                                                       # return the actual PASSAGE it came from, not just
                                                                       # a token -- the basis of grounded answers.
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
        self.recon = torch.full((cap,), -1.0, device=device)                 # per-entry RECONSTRUCTION error (Verification
        #   signal, decoupled from surprise; set by verification.verify()); -1 = not checked
        self.selfcon = torch.full((cap,), -1.0, device=device)               # per-entry self-consistency implausibility
        #   (fraction of vocab the model ranks above the stored token, given the entry's own context); -1 = not checked
        self.use = torch.zeros(cap, device=device)                          # retrieval count (for turnover)
        self.src_floor = float(src_floor)   # fraction of cap reserved per live source; 0 = no floor (old behaviour)
        self.nsrc = torch.zeros(max(1, int(n_src_hint)), device=device)     # ACTIVE entries per source id, kept
        self._floor_blocked = 0             #   incrementally in _commit; a recount is 200k elements per write
        self.live_src = None                # set_live_src(): source ids with a live domain. None = all eligible.
        # HIGH-WATER MARK per source. Occupancy below the floor means two completely different things -- a domain
        # that never wrote that much yet, and a domain that HAD it and lost it -- and only the second is a
        # failure. Without this the starvation alarm fires on every newly-appearing domain, and a warning that
        # cries wolf is a warning nobody reads.
        self.nsrc_max = torch.zeros(max(1, int(n_src_hint)), device=device)
        self.active = torch.zeros(cap, dtype=torch.bool, device=device)
        self.ctx_w = int(ctx_w)                                              # if >0, store a raw context window per
        if self.ctx_w > 0:                                                   #   entry so keys can be RE-ENCODED (drift fix)
            self.ctx = torch.zeros(cap, self.ctx_w, dtype=torch.long, device=device)
        self.ptr = 0

    @property
    def n(self): return int(self.active.sum())

    def _gate(self, surprise):
        """The surprise gate + its controller, factored out so a batched caller can run the gate for several windows
        BEFORE paying for any key encode. Advances gate_theta exactly as write() does, in call order."""
        sd = surprise.detach()
        if self.adaptive_gate and self.quantile_gate:
            # QUANTILE GATE. The additive controller below CANNOT hit gate_target on a large vocabulary: surprise is
            # 1 - p_model(true token), so with V=16384 an undertrained model puts surprise ~1.0 almost everywhere, the
            # controller drives gate_theta straight into gate_ceil=0.95, and the kept fraction runs 1.00/0.93/0.80
            # instead of the requested 0.12 -- MEM_CAP was reached by step ~831 instead of ~6510. An absolute threshold
            # cannot track a distribution squeezed against 1.0; a QUANTILE is scale-free and hits the target by
            # construction. Tracked as an EMA so a genuinely dull stretch still writes less and a surprising one more,
            # which is what the "relative surprise" intent was after. Kept on-device: no per-window host sync.
            q = torch.quantile(sd.float().flatten(), max(0.0, min(1.0, 1.0 - self.gate_target)))
            if not torch.is_tensor(self.gate_theta):
                self.gate_theta = q.detach().clone()                      # seed from the first batch, not from write_gate
            else:
                self.gate_theta = (1 - self.gate_step) * self.gate_theta + self.gate_step * q.detach()
            return sd > self.gate_theta
        if self.adaptive_gate:
            keep = sd > self.gate_theta                      # gate on RELATIVE surprise (above the self-calibrated level)
            fired = float(keep.float().mean())               # controller: rise if firing above target, fall if below ->
            self.gate_theta = min(self.gate_ceil, max(self.gate_floor, self.gate_theta + self.gate_step * (fired - self.gate_target)))
        else:
            keep = sd >= self.write_gate                     # keep only tokens the model was unsure about (>= fixed gate)
        return keep

    # NOTE: write() below routes its gating through _gate() too, so WRITE_QUANTILE applies on BOTH paths. It previously
    # had its own inline copy of the additive controller, which meant the quantile fix silently did nothing whenever
    # KEY_PREGATE=0 or KEY_BATCH=0 sent writes down the per-window path.

    def write_batch(self, rows, key_fn, owners=None):
        """DISPATCH BATCHING: write several windows with ONE key encode instead of one per window.

        Profiling on an A100 showed the step is dominated by call COUNT, not FLOPs: `_model_key` ran ~1952 times per
        976 steps on tiny tensors against ~61 real LM forwards, and memory-key + rekey were 48-72% of the loop. The
        per-window write loop was BATCH_W of those calls. Here the gate runs for every window first (same order, so
        gate_theta evolves identically), the survivors are concatenated, ONE key_fn call encodes all of them, and the
        stores then proceed per window exactly as before. Row-independent encoder => identical keys.

        rows: list of (tok, src, surprise, ctx, pos). Returns total entries written."""
        keeps = [self._gate(r[2]) for r in rows]             # gate FIRST, for every window, before any encode
        ctxs = [r[3][k] for r, k in zip(rows, keeps) if r[3] is not None and int(k.sum()) > 0]
        if not ctxs: return 0
        allk = key_fn(torch.cat(ctxs, 0)).detach()           # <-- the single encode this whole method exists for
        n = 0
        off = 0
        for _r, (r, keep) in enumerate(zip(rows, keeps)):
            tok, src, _, ctx, pos = r
            m = int(keep.sum())
            if ctx is None or m == 0: continue
            n += self._store(allk[off:off + m], tok[keep], src, ctx[keep], (None if pos is None else pos[keep]),
                             own=(None if owners is None else owners[_r]))
            off += m
        return n

    # ---- WRITE (surprise-gated, provenance-tagged) ----
    def write(self, k, tok, src, surprise=None, ctx=None, pos=None, key_fn=None):
        """k:(B,d) keys, tok:(B,) next tokens, src:int domain id. surprise:(B,)=1-p_model(true tok) gates writing.
        ctx:(B,ctx_w) optional
        raw context window stored so keys can be re-encoded later (drift fix).

        key_fn: if given, k may be None and the keys are encoded from ctx AFTER the surprise gate instead of before.
        The caller was encoding a key for EVERY position and then throwing ~88% of them away here (the gate keeps only
        `gate_target` of them), which made this the most expensive operation in the step by a wide margin. Encoding the
        survivors only is exactly equivalent -- the encoder is row-independent, so a row's key does not depend on which
        other rows are in the batch -- and the gate, its controller and the resulting entries are untouched."""
        if k is not None: k = k.detach()
        if surprise is not None:
            keep = self._gate(surprise)                      # SAME gate as write_batch (incl. WRITE_QUANTILE)
            if k is not None: k = k[keep]
            tok = tok[keep]
            if ctx is not None: ctx = ctx[keep]
            if pos is not None: pos = pos[keep]
        if k is None:                                    # deferred encode: only the SURVIVORS pay for a key
            if key_fn is None or ctx is None: raise ValueError("write(k=None) requires key_fn and ctx")
            if tok.numel() == 0: return 0
            k = key_fn(ctx).detach()
        return self._store(k, tok, src, ctx, pos)

    def _store(self, k, tok, src, ctx, pos, own=None):
        """Commit already-gated, already-keyed rows. Shared by write() and write_batch() so the two cannot drift."""
        m = k.size(0)
        if m == 0: return 0
        if self.n_own > 1 and own is not None:
            # PER-OWNER LRU. One window can present far more survivors than a small quota holds, so keep the most
            # surprising `quota` of them rather than letting the tail evict rows written microseconds earlier in the
            # same call. Then fill this owner's free slots first, and only after that evict its least-recently-USED.
            o = int(own) % self.n_own
            base = o * self.quota
            if m > self.quota:
                m = self.quota
                k, tok = k[:m], tok[:m]
                if ctx is not None: ctx = ctx[:m]
                if pos is not None: pos = pos[:m]
            blk = torch.arange(base, base + self.quota, device=self.dev)
            free = blk[~self.active[blk]]
            if free.numel() >= m:
                idx = free[:m]
            else:
                need = m - free.numel()
                lru = blk[self.last[blk].argsort()][:need]                    # oldest LAST-USE within this owner only
                idx = torch.cat([free, lru]) if free.numel() else lru
            self.tick += 1
            self.own[idx] = o; self.last[idx] = self.tick
            return self._commit(idx, k, tok, src, ctx, pos, m)
        if self.evict in ("usage", "lru") and int(self.active.sum()) >= self.cap:
            # SAMPLED victim selection: draw a candidate pool and kill the worst of it, O(m) rather than O(cap).
            #   "usage" = LEAST-RETRIEVED dies (LFU on decayed retrieval mass).
            #   "lru"   = LEAST-RECENTLY-USED dies, where USED means RETRIEVED. Both signals are only real if reads
            #             actually happen during training -- see MEM_PROBE_EVERY. Without a read probe `use` and
            #             `last` never move off their write-time values and this degenerates to arbitrary/FIFO.
            ns = int(min(self.cap, max(8 * m, 64)))
            cand = torch.randint(0, self.cap, (ns,), device=self.dev)
            cand = self._unprotected(cand, m)                                 # PER-SOURCE FLOOR, see below
            kk = int(min(m, cand.numel()))
            _sig = self.use[cand] if self.evict == "usage" else self.last[cand].float()
            idx = cand[_sig.topk(kk, largest=False).indices]
            if idx.numel() < m:                                               # pad with circular if the sample was short
                pad = (torch.arange(m - idx.numel(), device=self.dev) + self.ptr) % self.cap
                idx = torch.cat([idx, pad])
        else:
            idx = (torch.arange(m, device=self.dev) + self.ptr) % self.cap    # circular overwrite (recency only)
        self.ptr = int((self.ptr + m) % self.cap)
        self.tick += 1; self.last[idx] = self.tick                            # a fresh entry starts its clock at NOW,
        #   so an entry that is never retrieved ages from its write and an entry that is retrieved keeps resetting.
        #   The global path never stamped `last` at all before this line existed.
        return self._commit(idx, k, tok, src, ctx, pos, m)

    # ---- PER-SOURCE FLOOR: no domain can be driven to zero by a domain that is currently streaming ----
    def _src_counts(self):
        """Active entries per source. Maintained incrementally in _commit -- an O(cap) recount on every write is
        200k elements per step at the sizes this runs at."""
        return self.nsrc

    def _unprotected(self, cand, need):
        """Drop candidates belonging to a source that is at or below its reserved floor.

        WHY THIS EXISTS, and why a better ranking function cannot replace it. Eviction ranked on retrieval --
        `use` or `last` -- asks "what is the CURRENT stream asking for". For a domain that is not currently
        streaming the answer is nothing, by construction: no query resembles it, so it is never retrieved, its
        clock never advances, and it is the victim every time. Measured twice, once under write-recency and again
        under retrieval-recency, with the same outcome both times: after a Python run, English held 0 of 200000
        entries. The read probe made the signal real; the signal it made real is still the current stream.
        So the floor is not a tie-break, it is the only thing in the design that a silent domain can survive on.

        floor_i = src_floor * cap / (number of sources with any entries). At src_floor=0.5 and two domains each
        is guaranteed a quarter of the store and the other half is contested -- partial isolation, which is the
        stated goal: overlap between domains is expected, TOTAL overlap is the failure.

        NEVER DEADLOCKS. If protection would leave nothing to evict -- every source at its floor, which happens
        when the store is full and sources are balanced -- the filter is dropped for this call and the ranking
        decides. A store that cannot evict is worse than one that evicts something protected."""
        if self.src_floor <= 0.0: return cand
        has = self._eligible()
        live = int(has.sum())
        if live <= 1: return cand                                            # one source owns everything anyway
        floor = int(self.src_floor * self.cap / live)
        if floor <= 0: return cand
        prot = has & (self.nsrc <= floor)                                    # (nsrc_len,) bool, per source id
        cs = self.src[cand].clamp(min=0, max=self.nsrc.numel() - 1)
        keep = ~prot[cs]
        keep &= (self.src[cand] >= 0)                                        # never protect an unwritten slot
        out = cand[keep]
        self._floor_blocked += int(cand.numel() - out.numel())
        return out if out.numel() >= need else cand

    def _eligible(self):
        """Sources that both HOLD entries and still have a LIVE domain behind them.

        ORPHANS ARE NOT PROTECTED AND DO NOT DILUTE THE FLOOR, and both halves of that matter. Measured on a real
        run: 125 source ids held entries while 27 domains were live, so dividing the reserved capacity by "sources
        with anything in them" gave each 800 slots instead of the ~3300 a live domain is due -- and most of the
        reservation went to domains that no longer exist. An orphan is precisely the entry eviction should reach
        first, so protecting it inverts the mechanism.

        Sources go orphaned legitimately: the assembler folds domains together (reassign_src) and culls them
        (delete_src), and ids climb monotonically, so a long run accumulates them. live_src=None means "no domain
        information supplied" and everything with entries is eligible, which is the previous behaviour."""
        has = (self.nsrc > 0)
        if self.live_src is None: return has
        lv = torch.zeros_like(has)
        for s in self.live_src:
            if 0 <= s < lv.numel(): lv[s] = True
        return has & lv

    def set_live_src(self, live):
        """Tell the store which source ids still correspond to a live domain. Called on the domain-manage cadence;
        pass None to go back to treating every source with entries as eligible."""
        self.live_src = None if live is None else set(int(x) for x in live)

    def src_report(self):
        """Per-source occupancy against the floor. Printed rather than inferred: the domain that vanished did so
        silently for the whole project, and the only reason anyone noticed was an unrelated unlearn test going
        vacuous."""
        has = self._eligible()
        live = int(has.sum())
        orph = int((self.nsrc > 0).sum()) - live
        floor = int(self.src_floor * self.cap / max(1, live)) if self.src_floor > 0 else 0
        rows = [(int(s), int(self.nsrc[s])) for s in (self.nsrc > 0).nonzero(as_tuple=True)[0].tolist()]
        # `lost` is the only starvation worth an alarm: the source once held a floor's worth and no longer does.
        lost = [(int(s), int(self.nsrc[s]), int(self.nsrc_max[s]))
                for s in (self.nsrc_max >= max(1, floor)).nonzero(as_tuple=True)[0].tolist()
                if floor > 0 and int(self.nsrc[s]) < max(1, floor // 4)]
        return {"floor": floor, "per_source": rows, "blocked": self._floor_blocked, "lost": lost,
                "live": live, "orphan": orph}

    def _commit(self, idx, k, tok, src, ctx, pos, m):
        """Write the chosen slots. Split out so the partitioned and global eviction paths share one body."""
        # SOURCE ACCOUNTING, before the overwrite: the slots being taken still hold their old owners' counts.
        old = self.src[idx]
        oa = old[(old >= 0) & self.active[idx]]
        if oa.numel():
            self.nsrc.index_add_(0, oa.clamp(min=0, max=self.nsrc.numel() - 1),
                                 torch.full((oa.numel(),), -1.0, device=self.dev, dtype=self.nsrc.dtype))
        s_i = int(src)
        if s_i >= self.nsrc.numel():                                         # a new source id: grow both tables
            grow = torch.zeros(s_i + 1 - self.nsrc.numel(), device=self.dev, dtype=self.nsrc.dtype)
            self.nsrc = torch.cat([self.nsrc, grow])
            self.nsrc_max = torch.cat([self.nsrc_max, grow.clone()])
        if s_i >= 0:
            self.nsrc[s_i] += idx.numel()
            self.nsrc_max[s_i] = torch.maximum(self.nsrc_max[s_i], self.nsrc[s_i])
        self.keys[idx] = torch.nn.functional.normalize(k, dim=-1)
        self.tok[idx] = tok.to(self.dev)
        self.src[idx] = int(src)
        if pos is not None: self.pos[idx] = pos[:idx.numel()].to(self.dev)   # remember WHERE it came from
        if self.ctx_w > 0 and ctx is not None: self.ctx[idx] = ctx.to(self.dev)
        self.use[idx] = 0.0; self.active[idx] = True
        self.selfcon[idx] = -1.0                                              # new entry: self-consistency not yet checked
        self.recon[idx] = -1.0                                                # new entry: reconstruction not yet checked
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
        valid = self.active & (~self.is_wrong()) & (~self.is_unverified())   # exclude old-B-wrong AND recon-unverified
        #   (is_unverified() is a no-op until verify() has populated recon, so default runs are unchanged)
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
        # LAST-USE STAMP, UNCONDITIONALLY. This used to be gated on n_own > 1, so on the global store `last` was
        # never written by a read AND never written by a write -- it stayed all-zero for the entire run and any
        # eviction rule consulting it was choosing arbitrarily. `last` is the clock for USE-BASED RECENCY: an entry
        # is young because it was RETRIEVED recently, not because it was WRITTEN recently. That distinction is the
        # whole point -- write-recency evicts a domain that has gone quiet by construction, use-recency evicts a
        # domain nothing is asking for, and a quiet domain that still answers queries survives.
        self.tick += 1
        self.last[gi.reshape(-1)] = self.tick
        # NOTE reads are deliberately GLOBAL across owners even when the store is partitioned: writes compartmentalize,
        # reads mix. That is the "partially, not fully, isolate" property -- an expert's knowledge is its own to keep
        # and to lose, but any query can still reach it.
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

    # ---- VERIFICATION (renamed from B): reconstruction error, decoupled from surprise ----
    def set_recon(self, idx, err):
        """Record per-entry reconstruction error (the Verification signal). Set by verification.verify()."""
        self.recon[idx] = err.to(self.dev)

    def is_unverified(self):
        """Flagged by VERIFICATION: reconstruction error in the high tail (adaptive median + k*MAD) -- the entry can't be
        regenerated from its own key, i.e. it is OFF the learned-association manifold. Parallels is_wrong() but uses
        reconstruction error instead of self-consistency, so genuine-novel (low error) and corrupt (high error) separate."""
        checked = self.recon >= 0
        out = torch.zeros_like(self.active)
        if int(checked.sum()) > 10:
            v = self.recon[checked]; med = v.median(); mad = (v - med).abs().median()
            thr = med + self.selfcon_k * (mad + 1e-6)
            out = self.active & checked & (self.recon >= thr)
        return out

    # ---- FORGET (the editability) ----
    def delete(self, mask):
        """mask:(cap,) bool -> deactivate those entries. Returns count removed."""
        gone = mask & self.active
        rm = int(gone.sum())
        if rm:
            # KEEP THE SOURCE CENSUS HONEST. nsrc drives the per-source floor, so a delete that does not
            # decrement it leaves a source looking fuller than it is -- and therefore protected from eviction on
            # the strength of entries that no longer exist. delete_src, sweep_wrong and the unlearn tests all
            # route through here, which is why the accounting lives here and not in each caller.
            gs = self.src[gone]
            gs = gs[gs >= 0]
            if gs.numel():
                self.nsrc.index_add_(0, gs.clamp(min=0, max=self.nsrc.numel() - 1),
                                     torch.full((gs.numel(),), -1.0, device=self.dev, dtype=self.nsrc.dtype))
                self.nsrc.clamp_(min=0)
        self.active[mask] = False
        return rm

    def delete_src(self, src):
        return self.delete(self.src == int(src))

    def reassign_src(self, old, new):
        # (nsrc is rebuilt for the two ids involved rather than tracked incrementally: a merge is rare and the
        #  two-source recount is exact, where an incremental delta would drift if the caller merged twice.)
        """Remap provenance old->new (when the domain manager MERGES two domains). Keeps memory consistent with the
        managed domain set -- pruning/merging domains INDIRECTLY prunes+relabels their memory."""
        m = self.src == int(old); self.src[m] = int(new)
        for _s in (int(old), int(new)):
            if 0 <= _s < self.nsrc.numel():
                self.nsrc[_s] = float(((self.src == _s) & self.active).sum())
        return int(m.sum())

    def sweep_wrong(self):
        """Delete every entry currently flagged wrong (self-inconsistent: stored token implausible for its own context)."""
        return self.delete(self.is_wrong())

    def stats(self):
        act = self.active
        per_src = {}
        for s in self.src[act].unique().tolist():
            per_src[int(s)] = int((self.src == s).logical_and(act).sum())
        return {"n": self.n, "flagged_wrong": int(self.is_wrong().sum()), "per_source": per_src,
                "src_floor": self.src_floor, "floor_blocked": self._floor_blocked}
