"""Online acoustic BPE over codec lattice ids: the media analogue of TOK's online byte-BPE.

Same mechanism as the text side: a pair TALLY over the windows the LM actually consumed, a mint BURST on a
cadence (TOK_GROW_EVERY / TOK_GROW_BURST analogues), a count threshold (TOK_MIN_PAIR analogue), a length
ceiling in FRAMES (TOK_MAX_BYTES analogue), append-only ids (id2bytes analogue: a minted id always
expands to the same tuple of lattice ids), and rank-order application for segmentation.
Ids here are media-local: 0..nbase-1 are lattice ids, nbase.. are minted merges.
"""
import torch


class MediaBPE:
    def __init__(self, nbase=1000, slots=512, max_frames=16, min_pair=50):
        self.nbase, self.slots, self.max_frames, self.min_pair = nbase, slots, max_frames, min_pair
        self.ntok = nbase + slots
        self.parents = []                       # minted id nbase+k = merge of parents[k]
        self.pair2id = {}
        self.explen = [1] * nbase               # frames each id stands for
        self.tally = torch.zeros(self.ntok * self.ntok)
        self.minted_at = []                     # window index at which each merge was minted
        self.refused_len = 0

    @property
    def size(self):
        return self.nbase + len(self.parents)

    # ------------------------------------------------------------------ tally (TOK.on_window analogue)
    def observe(self, toks, is_media):
        """toks (B, T) media-local ids (anything where is_media False is ignored); counts adjacent pairs
        whose BOTH members are media tokens (so never across BEGIN/END or into text)."""
        a, b = toks[:, :-1], toks[:, 1:]
        m = is_media[:, :-1] & is_media[:, 1:]
        if not m.any():
            return
        key = (a[m] * self.ntok + b[m]).long()
        self.tally.index_add_(0, key, torch.ones(key.numel()))

    # ------------------------------------------------------------------ mint (TOK.maybe_grow analogue)
    def mint(self, burst, window):
        new = []
        if burst <= 0 or len(self.parents) >= self.slots:
            return new
        vals, idx = self.tally.topk(min(self.tally.numel(), max(64, burst * 8)))
        for v, k in zip(vals.tolist(), idx.tolist()):
            if len(new) >= burst or len(self.parents) >= self.slots:
                break
            if v < self.min_pair:
                break
            a, b = divmod(k, self.ntok)
            if (a, b) in self.pair2id:
                continue
            L = self.explen[a] + self.explen[b]
            if L > self.max_frames:
                self.refused_len += 1
                continue                         # skip the candidate, never abort the burst (TOK lesson)
            nid = self.nbase + len(self.parents)
            self.parents.append((a, b)); self.pair2id[(a, b)] = nid; self.explen.append(L)
            self.minted_at.append(window)
            self.tally[k] = 0.0
            new.append((nid, a, b))
        return new

    def reset_tally(self, decay=0.0):
        self.tally.mul_(decay)

    # ------------------------------------------------------------------ segmentation
    def apply(self, codes):
        """codes (N, F) lattice ids -> list of N 1-D tensors of media-local ids (rank-order greedy BPE)."""
        N, Fr = codes.shape
        if not self.parents:
            return [codes[i].clone() for i in range(N)]
        x = torch.cat([codes, torch.full((N, 1), -1, dtype=codes.dtype)], 1).reshape(-1)
        for k, (a, b) in enumerate(self.parents):
            m = (x[:-1] == a) & (x[1:] == b)
            if not m.any():
                continue
            idx = torch.nonzero(m).squeeze(1)
            if a == b:  # overlapping matches in a run: leftmost-greedy = even offsets within each run
                start = torch.ones_like(idx, dtype=torch.bool); start[1:] = idx[1:] != idx[:-1] + 1
                rid = torch.cumsum(start.long(), 0) - 1
                first = idx[start][rid]
                idx = idx[((idx - first) % 2) == 0]
            x[idx] = self.nbase + k
            keep = torch.ones_like(x, dtype=torch.bool); keep[idx + 1] = False
            x = x[keep]
        sep = torch.nonzero(x == -1).squeeze(1)
        out = []; s = 0
        for e in sep.tolist():
            out.append(x[s:e].clone()); s = e + 1
        return out

    def expand(self, tid):
        if tid < self.nbase:
            return [tid]
        a, b = self.parents[tid - self.nbase]
        return self.expand(a) + self.expand(b)

    def state_dict(self):
        return dict(parents=list(self.parents), minted_at=list(self.minted_at), tally=self.tally.clone(),
                    refused_len=self.refused_len)

    def load_state_dict(self, d):
        self.parents = [tuple(p) for p in d["parents"]]
        self.pair2id = {p: self.nbase + k for k, p in enumerate(self.parents)}
        self.explen = [1] * self.nbase
        for a, b in self.parents:
            self.explen.append(self.explen[a] + self.explen[b])
        self.minted_at = list(d["minted_at"]); self.tally = d["tally"].clone(); self.refused_len = d["refused_len"]


if __name__ == "__main__":
    bp = MediaBPE(nbase=10, slots=10, min_pair=1)
    toks = torch.tensor([[3, 3, 3, 3, 3, 1, 2, 1, 2, 3]])
    bp.observe(toks, torch.ones_like(toks, dtype=torch.bool))
    print(bp.mint(3, 0))
    out = bp.apply(torch.tensor([[3, 3, 3, 3, 3, 1, 2, 1, 2, 3], [1, 2, 3, 3, 0, 0, 0, 0, 0, 0]]))
    print(out, [sum(len(bp.expand(int(t))) for t in o) for o in out])
