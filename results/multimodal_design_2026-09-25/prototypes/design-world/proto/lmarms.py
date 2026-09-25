from worldarms import *
class TinyLM(nn.Module):
    """mirror of lm/api.py's gru arm: drop(emb(x)+pos) -> GRU -> (h + extra) -> head. Plus the two
    PROPOSED conditioning paths: `prefix` (inputs_embeds through the trunk) and `xattn` (gated
    cross-attention after the trunk, Flamingo tanh(alpha) gate born 0)."""
    def __init__(self, W=128, V=256, pos_max=256, cond="none", K=8, lat=LAT):
        super().__init__()
        self.emb = nn.Embedding(V, W); self.pos = nn.Embedding(pos_max, W); self.drop = nn.Dropout(0.1)
        self.body = nn.GRU(W, W, batch_first=True); self.head = nn.Linear(W, V)
        self.cond, self.K = cond, K
        if cond == "extra":
            self.proj = nn.Linear(lat, W); nn.init.zeros_(self.proj.weight); nn.init.zeros_(self.proj.bias)  # born zero, like world_proj
        if cond == "prefix":
            self.proj = nn.Linear(lat, W)
        if cond == "extra_attn":   # computable OUTSIDE the LM -> fits today's LM.encode(extra=) signature
            self.q = nn.Parameter(torch.randn(pos_max, W) * 0.02); self.kv = nn.Linear(lat, W)
            self.att = nn.MultiheadAttention(W, 4, batch_first=True); self.proj = nn.Linear(W, W)
            nn.init.zeros_(self.proj.weight); nn.init.zeros_(self.proj.bias)
        if cond == "xattn":
            self.kv = nn.Linear(lat, W); self.att = nn.MultiheadAttention(W, 4, batch_first=True); self.alpha = nn.Parameter(torch.zeros(()))
    def forward(self, x, media=None):
        L = x.shape[1]; e = self.emb(x)
        npre = 0
        if self.cond == "prefix":
            B, T, D = media.shape; pm = media.reshape(B, self.K, T // self.K, D).mean(2) if self.K < T else media
            pe = self.proj(pm); npre = pe.shape[1]; e = torch.cat([pe, e], 1)
        h = self.drop(e + self.pos.weight[:e.shape[1]].unsqueeze(0))
        h, hn = self.body(h); h = h[:, npre:]
        if self.cond == "extra":
            h = h + self.proj(media.mean(1)).unsqueeze(1).expand(-1, L, -1)      # LM.encode(extra=) today: post-trunk, additive
        if self.cond == "extra_attn":
            kv = self.kv(media); a, _ = self.att(self.q[:L].unsqueeze(0).expand(x.shape[0], -1, -1), kv, kv); h = h + self.proj(a)
        if self.cond == "xattn":
            kv = self.kv(media); a, _ = self.att(h, kv, kv); h = h + torch.tanh(self.alpha) * a
        return self.head(self.drop(h)), h

def cap_batch(Ps):
    cs = [S.caption(p).encode() for p in Ps]; L = max(len(c) for c in cs)
    y = torch.zeros(len(cs), L, dtype=torch.long); m = torch.zeros(len(cs), L)
    for i, c in enumerate(cs): y[i, :len(c)] = torch.tensor(list(c)); m[i, :len(c)] = 1
    x = torch.cat([torch.full((len(cs), 1), 2), y[:, :-1]], 1)   # byte 2 = STX as BOS
    return x, y, m
