"""Self-contained VERIFICATION (reconstruction) vs old-B (self-consistency) A/B test -- REALISTIC regime.

Needs ONLY torch + the data/train/{eng,py,num,c} corpora -- NOT the rest of the repo, and no git pull.
    python3 verify_console_test.py
    # or in a Python console:  exec(open("verify_console_test.py").read())

Why this test is set up the way it is: the old B works FINE on abundant cross-domain corruption (~80% precision) --
that is NOT where it fails. It fails in the PRODUCT-LOOP regime: the write gate only stores SURPRISING entries, so the
store is full of genuine-but-surprising associations, and B (which flags surprising) can't tell them from wrong ones.
So here the NEGATIVES are SURPRISE-GATED genuine entries (the hard case), and we compare with base-rate-honest metrics:
  - AUC (threshold-free: P(a corrupt scores higher than a genuine)), and
  - precision at a realistic 1% corruption base rate (from the measured TPR/FPR at the adaptive threshold).
SUCCESS = reconstruction AUC (and precision@1%) clearly beats self-consistency B.
Override via env: DEVICE, DATA_DIR, PERDOM, STEPS, RSTEPS, NGEN, NNEG, NCORR.
"""
import os, glob, random, torch, torch.nn as nn, torch.nn.functional as F
dev = os.environ.get("DEVICE") or ("cuda" if torch.cuda.is_available() else "cpu")
torch.manual_seed(0); random.seed(0)
DATA = os.environ.get("DATA_DIR", "data"); PER = int(os.environ.get("PERDOM", 400000))
V, D, WIN = 256, 256, 64
corp = {d: b"".join(open(f, "rb").read() for f in sorted(glob.glob(f"{DATA}/train/{d}/*")))[:PER] for d in ["eng", "py", "num", "c"]}
corp = {d: c for d, c in corp.items() if len(c) > 20000}
doms = list(corp); assert len(doms) >= 2, f"need >=2 domains with data under {DATA}/train/*; found {doms}"
sb = []; lb = []
for d in doms: sb += list(corp[d]); lb += [d] * len(corp[d])
S = torch.tensor(sb, dtype=torch.long); L = lb; N = len(S)
print(f"[data] {N} bytes | domains {doms} | device {dev}")
class LM(nn.Module):
    def __init__(s):
        super().__init__(); s.emb = nn.Embedding(V, D); s.gru = nn.GRU(D, D, batch_first=True); s.head = nn.Linear(D, V)
    def enc(s, x): h, _ = s.gru(s.emb(x)); return h
    def forward(s, x): h = s.enc(x); return s.head(h), h
lm = LM().to(dev); opt = torch.optim.AdamW(lm.parameters(), lr=2e-3)
STEPS = int(os.environ.get("STEPS", 3000)); BS = 64
for step in range(STEPS):
    j = torch.randint(0, N - WIN - 1, (BS,))
    x = torch.stack([S[a:a + WIN] for a in j]).to(dev); y = torch.stack([S[a + 1:a + WIN + 1] for a in j]).to(dev)
    lg, _ = lm(x); loss = F.cross_entropy(lg.reshape(-1, V), y.reshape(-1))
    opt.zero_grad(); loss.backward(); opt.step()
    if step % 500 == 0: print(f"[train] step {step} loss {loss.item():.3f}")
pool = {d: [] for d in doms}
for a in range(0, N - WIN - 1):
    if L[a] == L[a + WIN]: pool[L[a]].append(a)
pool = {d: p for d, p in pool.items() if len(p) > 50}; doms = list(pool)
@torch.no_grad()
def kt(idxs):
    x = torch.stack([S[a:a + WIN] for a in idxs]).to(dev); _, h = lm(x)
    return h[:, -1], S[torch.tensor(idxs) + WIN].to(dev)
@torch.no_grad()
def selfcon(idxs):                                        # old B: implausibility of the TRUE next token = "surprise"
    x = torch.stack([S[a:a + WIN] for a in idxs]).to(dev); lg, _ = lm(x)
    t = S[torch.tensor(idxs) + WIN].to(dev); last = lg[:, -1]
    return (last > last.gather(1, t[:, None])).float().mean(1)
class Recon(nn.Module):                                   # NEW: cross-reconstruct the expected token-code from the key
    def __init__(s, td=32, hid=64):
        super().__init__(); s.register_buffer("tc", F.normalize(torch.randn(V, td), dim=-1))
        s.net = nn.Sequential(nn.Linear(D, hid), nn.GELU(), nn.Linear(hid, hid), nn.GELU(), nn.Linear(hid, td))
    def err(s, k, t): return F.mse_loss(s.net(k), s.tc[t], reduction="none").mean(-1)
rc = Recon().to(dev); ro = torch.optim.Adam(rc.parameters(), lr=1e-3)
NG = int(os.environ.get("NGEN", 5000)); gi = [random.choice(pool[random.choice(doms)]) for _ in range(NG)]
gk, gt = kt(gi)
for e in range(int(os.environ.get("RSTEPS", 1500))):
    ro.zero_grad(); rc.err(gk.detach(), gt).mean().backward(); ro.step()
gsc = selfcon(gi); gate = gsc.median()                    # SURPRISE-GATE: keep the surprising half as HARD negatives
hardneg = [gi[i] for i in range(NG) if gsc[i] >= gate]; random.shuffle(hardneg)
hardneg = hardneg[:int(os.environ.get("NNEG", 800))]
nk, nt = kt(hardneg); n_re = rc.err(nk, nt); n_sc = selfcon(hardneg)
NC = int(os.environ.get("NCORR", 800)); cctx = []; ct = []
for _ in range(NC):
    p, q = random.sample(doms, 2); a = random.choice(pool[p]); b = random.choice(pool[q])
    cctx.append(S[a:a + WIN]); ct.append(int(S[b + WIN]))
CX = torch.stack(cctx).to(dev); CT = torch.tensor(ct).to(dev)
with torch.no_grad():
    lg, h = lm(CX); c_re = rc.err(h[:, -1], CT); last = lg[:, -1]; c_sc = (last > last.gather(1, CT[:, None])).float().mean(1)
def auc(pos, neg): return (pos.unsqueeze(1) > neg.unsqueeze(0)).float().mean().item()
def prec_at(pos, neg, base=0.01):                         # precision at a realistic 1% corruption base rate
    allv = torch.cat([pos, neg]); med = allv.median(); mad = (allv - med).abs().median(); thr = med + 2.5 * (mad + 1e-6)
    tpr = (pos >= thr).float().mean().item(); fpr = (neg >= thr).float().mean().item()
    return (tpr * base) / max(1e-9, tpr * base + fpr * (1 - base))
print("=" * 68)
print("REALISTIC regime -- negatives are SURPRISE-GATED genuine entries (the hard case)")
print(f"  {'signal':26s} AUC     precision@1%base   recall(TPR)")
for nm, cp, np_ in [("RECONSTRUCTION (new)", c_re, n_re), ("SELF-CONSISTENCY B (old)", c_sc, n_sc)]:
    allv = torch.cat([cp, np_]); med = allv.median(); mad = (allv - med).abs().median(); thr = med + 2.5 * (mad + 1e-6)
    print(f"  {nm:26s} {auc(cp, np_):.3f}   {prec_at(cp, np_):6.1%}          {(cp >= thr).float().mean().item():5.1%}")
print("SUCCESS = reconstruction AUC (and precision@1%) clearly beats self-consistency B.")
print("=" * 68)
