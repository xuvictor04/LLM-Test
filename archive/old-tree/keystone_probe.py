"""Keystone probe: can we embed by FUNCTION (the operation) instead of CONTENT (the operands)?

The whole subtokenize->embed->match->REUSE architecture hinges on this: two sub-tasks should route to the same
sub-skill when they need the SAME PROCEDURE, even on different data. The current signature encoder learns CONTENT
similarity (InfoNCE, nearby-in-stream). The design's proposed fix: embed the TRANSFORMATION that maps input->output,
not the surface. This probe tests whether that actually clusters by operation and NOT by content.

Setup (synthetic, torch-only, CPU): inputs are length-L digit strings; each sample applies one of N OPS
(identity/reverse/sort/increment/roll) to random content, giving (input, output). Two embeddings are trained on the
SAME data with DIFFERENT objectives:
  FUNCTIONAL: z = e(input, output); a decoder d(input, z) must reproduce output. Since input alone can't determine
              output (the op is unknown), a bottlenecked z is FORCED to encode the operation -> functional embedding.
  SURFACE   : z2 = e(input, output); a decoder d2(z2) must reconstruct the raw (input, output) -> z2 carries content.
Metric: k-NN OP-purity of the embedding (fraction of a sample's nearest neighbours sharing its op). High = the space is
organized by FUNCTION. Chance = 1/N_ops. SUCCESS = functional op-purity >> surface op-purity (and >> chance).
    python3 keystone_probe.py
"""
import os, random, torch, torch.nn as nn, torch.nn.functional as F
dev = os.environ.get("DEVICE") or ("cuda" if torch.cuda.is_available() else "cpu")
torch.manual_seed(0); random.seed(0)
Vd, Lc, ZD = 10, 8, 8                                        # digits 0-9, length 8, bottleneck 8
OPS = ["identity", "reverse", "sort", "incr", "roll"]; NOP = len(OPS)
def apply_op(o, s):
    if o == 0: return s
    if o == 1: return s[::-1]
    if o == 2: return sorted(s)
    if o == 3: return [(d + 1) % Vd for d in s]
    return s[1:] + s[:1]
def gen(n):
    inp = []; out = []; op = []
    for _ in range(n):
        o = random.randrange(NOP); s = [random.randrange(Vd) for _ in range(Lc)]
        inp.append(s); out.append(apply_op(o, s)); op.append(o)
    return (torch.tensor(inp, device=dev), torch.tensor(out, device=dev), torch.tensor(op, device=dev))
class Enc(nn.Module):                                        # (input, output) -> z  (both models encode the pair)
    def __init__(s, d=32):
        super().__init__(); s.ei = nn.Embedding(Vd, d); s.eo = nn.Embedding(Vd, d)
        s.gru = nn.GRU(2 * d, d, batch_first=True); s.head = nn.Linear(d, ZD)
    def forward(s, i, o):
        h, _ = s.gru(torch.cat([s.ei(i), s.eo(o)], -1)); return s.head(h[:, -1])
class FuncDec(nn.Module):                                    # d(input, z) -> output : z must supply the OPERATION
    def __init__(s, d=32):
        super().__init__(); s.ei = nn.Embedding(Vd, d); s.net = nn.Sequential(nn.Linear(d + ZD, d), nn.GELU(), nn.Linear(d, Vd))
    def forward(s, i, z):
        x = torch.cat([s.ei(i), z[:, None, :].expand(-1, Lc, -1)], -1); return s.net(x)
class SurfDec(nn.Module):                                    # d2(z) -> (input, output) : z must carry CONTENT
    def __init__(s, d=32):
        super().__init__(); s.net = nn.Sequential(nn.Linear(ZD, d), nn.GELU(), nn.Linear(d, 2 * Lc * Vd))
    def forward(s, z): return s.net(z).reshape(-1, 2 * Lc, Vd)
def gen_pair(n):                                            # two inputs under the SAME op -> forces z to be a
    i1 = []; o1 = []; i2 = []; o2 = []                       #   content-invariant FUNCTION code (reusable across content)
    for _ in range(n):
        op = random.randrange(NOP)
        s1 = [random.randrange(Vd) for _ in range(Lc)]; s2 = [random.randrange(Vd) for _ in range(Lc)]
        i1.append(s1); o1.append(apply_op(op, s1)); i2.append(s2); o2.append(apply_op(op, s2))
    return (torch.tensor(i1, device=dev), torch.tensor(o1, device=dev), torch.tensor(i2, device=dev), torch.tensor(o2, device=dev))
def train(kind, steps=6000):
    enc = Enc().to(dev)
    dec = (FuncDec() if kind == "func" else SurfDec()).to(dev)
    opt = torch.optim.Adam(list(enc.parameters()) + list(dec.parameters()), lr=2e-3)
    for st in range(steps):
        if kind == "func":                                  # TRANSFER: code z from pair 1 must transform pair 2 (same op,
            i1, o1, i2, o2 = gen_pair(256); z = enc(i1, o1)  #   NEW content) -> z cannot hold content, only the operation
            loss = F.cross_entropy(dec(i2, z).reshape(-1, Vd), o2.reshape(-1))
        else:
            i, o, _ = gen(256); z = enc(i, o)
            tgt = torch.cat([i, o], 1); loss = F.cross_entropy(dec(z).reshape(-1, Vd), tgt.reshape(-1))
        opt.zero_grad(); loss.backward(); opt.step()
    return enc
def op_purity(z, op, k=10):
    z = F.normalize(z, dim=-1); sim = z @ z.t(); sim.fill_diagonal_(-1e9)
    idx = sim.topk(k, dim=-1).indices
    return (op[idx] == op[:, None]).float().mean().item()
ei, eo, eop = gen(2000)
enc_f = train("func"); enc_s = train("surf")
with torch.no_grad():
    zf = enc_f(ei, eo); zs = enc_s(ei, eo)
pf, ps, ch = op_purity(zf, eop), op_purity(zs, eop), 1.0 / NOP
print("=" * 62)
print(f"KEYSTONE probe: k-NN OP-purity (1.0 = perfectly organized by function, chance = {ch:.2f})")
print(f"  FUNCTIONAL (embed the transformation) : {pf:.3f}")
print(f"  SURFACE    (embed the content)         : {ps:.3f}")
print(f"  gap (functional - surface) = {pf - ps:+.3f}")
print(f"  -> {'FUNCTION is separable from content -- the keystone mechanism works (transfer-coding)' if pf > ps + 0.2 and pf > 0.7 else 'weak / inconclusive'}")
print("=" * 62)
