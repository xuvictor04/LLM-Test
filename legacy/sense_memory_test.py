"""Sense-branching embedder test (Greg small-modification probe).

The idea under test: instead of a MIXTURE of embedders (M parallel tables, context-routed + summed),
use ONE embedder with a per-token "sense book" -- each base token carries K sub-meaning vectors
(branches / folders), and context selects a weighted branch. Polysemy (same token, different meaning
by context) is handled inside one, more-complex embedder rather than by M separate ones.

Three front-ends share ONE backbone (2-layer causal transformer + head); only embedding differs:
  single : nn.Embedding(V,d)                              -- baseline            (1x  V*d)
  moe    : M tables, route on causal-context gist, sum    -- Greg's MoE embedder (Mx  V*d, M=4)
  sense  : base + per-token K senses, route on gist       -- the new idea        (1+K, K=3 -> 4x V*d)
moe(M=4) and sense(K=3) are parameter-matched (4x V*d); single is the low baseline.

Numbers reported: held bits/byte per domain, and whether the routing SPECIALIZES by domain
(the mixture-of-embedders landmark), plus shared-token polysemy (does one token pick different
senses in code vs english?).
"""
import os, math, glob, random, torch, torch.nn as nn, torch.nn.functional as F
from tokenizer import ByteBPE

torch.manual_seed(0); random.seed(0)
DEV = "cpu"
LN2 = math.log(2)
DOMAINS = ["c", "eng", "num", "py"]
D, L, B, STEPS, K, M = 64, 48, 16, int(os.environ.get("STEPS", 300)), 3, 4

tok = ByteBPE.load("data/tokenizer.json")
V = tok.vocab_size
print(f"frozen tokenizer vocab = {V} | d={D} L={L} steps={STEPS} | senses K={K}, experts M={M}")

# ---- data: tokenize each domain, 90/10 train/held, record bytes/token for bits/byte ----
data = {}
for d in DOMAINS:
    text = ""
    for f in sorted(glob.glob(f"data/train/{d}/*.txt")):
        text += open(f, errors="ignore").read()
        if len(text) >= 30000: break
    text = text[:30000]
    ids = tok.encode(text)
    nb = len(text.encode("utf-8", "ignore"))
    cut = int(0.9 * len(ids))
    data[d] = {"tr": ids[:cut], "he": ids[cut:], "bpt": nb / max(1, len(ids))}
print("  bytes/token:", {d: round(data[d]["bpt"], 2) for d in DOMAINS},
      "| held tokens:", {d: len(data[d]["he"]) for d in DOMAINS})


def batch(ids):
    xs = []
    for _ in range(B):
        s = 0 if len(ids) <= L + 1 else random.randint(0, len(ids) - L - 1)
        xs.append(torch.tensor(ids[s:s + L + 1], dtype=torch.long))
    return torch.stack(xs).to(DEV)


class LM(nn.Module):
    def __init__(self, kind):
        super().__init__()
        self.kind = kind
        self.base = nn.Embedding(V, D)
        if kind == "moe":
            self.embs = nn.ModuleList([nn.Embedding(V, D) for _ in range(M)])
            self.route = nn.Linear(D, M)
        if kind == "sense":
            self.sense = nn.Parameter(torch.randn(V, K, D) * 0.02)
            self.route = nn.Linear(D, K)
        self.pos = nn.Embedding(L + 2, D)
        enc = nn.TransformerEncoderLayer(D, 2, 4 * D, batch_first=True, dropout=0.0, norm_first=True)
        self.tr = nn.TransformerEncoder(enc, 2)
        self.ln = nn.LayerNorm(D); self.head = nn.Linear(D, V)
        self.last_w = None                              # (B,Lc,units) routing weights for the probe

    def emb(self, x):
        be = self.base(x)                               # (B,Lc,D)
        Lc = x.size(1)
        gist = torch.cumsum(be, 1) / torch.arange(1, Lc + 1, device=x.device).view(1, -1, 1)  # causal context
        if self.kind == "single":
            self.last_w = None; return be
        if self.kind == "moe":
            w = torch.softmax(self.route(gist), -1)     # (B,Lc,M)
            st = torch.stack([e(x) for e in self.embs], 2)  # (B,Lc,M,D)
            self.last_w = w.detach(); return (w.unsqueeze(-1) * st).sum(2)
        w = torch.softmax(self.route(gist), -1)         # sense: (B,Lc,K)
        sv = self.sense[x]                              # (B,Lc,K,D)
        self.last_w = w.detach(); return be + (w.unsqueeze(-1) * sv).sum(2)

    def forward(self, x):
        Lc = x.size(1)
        h = self.emb(x) + self.pos(torch.arange(Lc, device=x.device))[None]
        mask = torch.triu(torch.ones(Lc, Lc, device=x.device), 1).bool()
        return self.head(self.ln(self.tr(h, mask=mask)))


@torch.no_grad()
def evaluate(m):
    m.eval()
    bb, mix = {}, {}                                    # per-domain bits/byte + mean routing weights
    tok_share = {}                                      # (domain, token) -> [sum_w, count] for polysemy
    for d in DOMAINS:
        ids = data[d]["he"]; tot_ce = tot_n = 0.0
        acc_w = None; nrows = 0
        for s in range(0, len(ids) - L - 1, L):
            xb = torch.tensor(ids[s:s + L + 1], dtype=torch.long, device=DEV)[None]
            lg = m(xb)
            ce = F.cross_entropy(lg[:, :-1].reshape(-1, V), xb[:, 1:].reshape(-1))
            tot_ce += float(ce) * (xb.size(1) - 1); tot_n += (xb.size(1) - 1)
            if m.last_w is not None:
                w = m.last_w[0]                          # (Lc,units)
                acc_w = w.mean(0) if acc_w is None else acc_w + w.mean(0); nrows += 1
                for t in range(xb.size(1)):
                    tid = int(xb[0, t]); key = (d, tid)
                    r = tok_share.setdefault(key, [torch.zeros(w.size(-1)), 0])
                    r[0] += w[t].cpu(); r[1] += 1
        bpt = data[d]["bpt"]
        bb[d] = (tot_ce / max(1, tot_n)) / LN2 / bpt     # bits/byte
        if acc_w is not None: mix[d] = (acc_w / nrows).cpu()
    return bb, mix, tok_share


def train_eval(kind):
    torch.manual_seed(0); random.seed(0)               # identical batch stream across variants
    m = LM(kind).to(DEV)
    opt = torch.optim.AdamW(m.parameters(), lr=3e-3)
    nparam = sum(p.numel() for p in m.parameters())
    m.train()
    for i in range(STEPS):
        d = DOMAINS[i % len(DOMAINS)]
        xb = batch(data[d]["tr"])
        lg = m(xb)
        loss = F.cross_entropy(lg[:, :-1].reshape(-1, V), xb[:, 1:].reshape(-1))
        opt.zero_grad(); loss.backward()
        torch.nn.utils.clip_grad_norm_(m.parameters(), 1.0); opt.step()
    bb, mix, share = evaluate(m)
    overall = sum(bb[d] * len(data[d]["he"]) for d in DOMAINS) / sum(len(data[d]["he"]) for d in DOMAINS)
    return {"kind": kind, "params": nparam, "bb": bb, "overall": overall, "mix": mix, "share": share}


res = {k: train_eval(k) for k in ["single", "moe", "sense"]}

print("\n================ held bits/byte (lower = better) ================")
print(f"  {'variant':<9}{'params':>10}   " + "  ".join(f"{d:>6}" for d in DOMAINS) + f"  {'OVERALL':>8}")
for k in ["single", "moe", "sense"]:
    r = res[k]
    print(f"  {k:<9}{r['params']:>10}   " + "  ".join(f"{r['bb'][d]:>6.2f}" for d in DOMAINS) + f"  {r['overall']:>8.3f}")

print("\n================ routing specialization by domain ================")
for k in ["moe", "sense"]:
    unit = "expert" if k == "moe" else "sense"
    print(f"  [{k}] per-domain mean {unit} weights:")
    for d in DOMAINS:
        v = res[k]["mix"].get(d)
        if v is not None:
            print(f"    {d:<5} " + " ".join(f"{x:.2f}" for x in v.tolist()))

# shared-token polysemy: tokens present in >=2 domains, biggest cross-domain routing gap (sense model)
print("\n================ shared-token polysemy (sense model) ================")
sh = res["sense"]["share"]
by_tok = {}
for (d, tid), (sw, c) in sh.items():
    if c >= 5:                                          # ignore ultra-rare
        by_tok.setdefault(tid, {})[d] = (sw / c)
cands = []
for tid, dm in by_tok.items():
    if len(dm) >= 2:
        vs = list(dm.values())
        gap = max((a - b).abs().sum().item() for a in vs for b in vs)
        cands.append((gap, tid, dm))
cands.sort(reverse=True)
print("  token (repr)              | per-domain sense weights")
for gap, tid, dm in cands[:6]:
    try: rep = repr(tok.decode([tid]))[:14]
    except Exception: rep = f"id{tid}"
    cell = "  ".join(f"{d}:[{' '.join(f'{x:.2f}' for x in w.tolist())}]" for d, w in dm.items())
    print(f"  {rep:<24} | {cell}")
print("\n(if a token's sense weights differ across domains, one embedder captured context-dependent meaning)")
