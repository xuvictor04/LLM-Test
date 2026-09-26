"""Credibility-signal audit: is there an AREA-LEVEL signal that separates the liar ('false') from the
credible sources ('cred', 'corrob') on the shared testbed, and how noisy is it?
Trains the BASELINE (planned draw, uniform weights) and at 8 checkpoints measures, on 2 disjoint halves
of N probe windows per area (stream 'audit', disjoint from readings and from run.py's probe):
  cos_full  : cosine of whole-parameter held-out gradients (what run.py 'consistency' uses)
  cos_out   : cosine of output-layer gradients only
  zc        : excess surprise (-log2 p - H, bits) on confident tokens (H<1 bit) (run.py 'surprise')
  zval      : excess surprise on the byte after '=' only (claim positions -- STRUCTURE-AWARE reference,
              not deployable without a claim aligner)
Usage: python cred_audit.py --seed 0 [--n 32]
"""
import sys, os, json, argparse, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "testbed"))
import torch, torch.nn.functional as F
import testbed as tb
torch.set_num_threads(1)
ap = argparse.ArgumentParser()
ap.add_argument("--seed", type=int, default=0)
ap.add_argument("--n", type=int, default=32)
ap.add_argument("--bytes", type=int, default=4_000_000)
args = ap.parse_args()
world = tb.World(args.seed)
AUD = {}
for a in tb.AREAS:
    b, _ = tb.AreaGen(a, args.seed, world, stream="audit").gen(args.n * (tb.CTX + 1))
    AUD[a] = torch.tensor(list(b), dtype=torch.long).view(args.n, tb.CTX + 1)
EQ = ord("=")
out = []


def measure(model, x):
    model.zero_grad()
    lg = model(x[:, :-1])
    nats = F.cross_entropy(lg.reshape(-1, 256), x[:, 1:].reshape(-1), reduction="none")
    nats.mean().backward()
    gf = torch.cat([p.grad.reshape(-1) for p in model.parameters() if p.grad is not None]).clone()
    go = torch.cat([model.out.weight.grad.reshape(-1), model.out.bias.grad.reshape(-1)]).clone()
    model.zero_grad()
    with torch.no_grad():
        lp = F.log_softmax(lg.reshape(-1, 256), -1)
        H = -(lp.exp() * lp).sum(-1) / tb.L2
        ex = nats.detach() / tb.L2 - H
        conf = H < 1.0
        val = (x[:, :-1].reshape(-1) == EQ)
    return gf, go, float(ex[conf].mean()), float(ex[val].mean()) if int(val.sum()) else float("nan"), int(val.sum())


def audit(model, step):
    if (step + 1) % 244 and step + 1 != 1953:
        return
    rec = {"step": step + 1, "halves": []}
    for h in range(2):
        sl = slice(h * args.n // 2, (h + 1) * args.n // 2)
        G = {a: measure(model, AUD[a][sl]) for a in tb.AREAS}
        cos = lambda u, v: float(u @ v / (u.norm() * v.norm() + 1e-12))
        r = {"cos_full": {}, "cos_out": {}, "zc": {}, "zval": {}, "nval": {}}
        for i, a in enumerate(tb.AREAS):
            r["zc"][a] = G[a][2]; r["zval"][a] = G[a][3]; r["nval"][a] = G[a][4]
            for b in tb.AREAS[i + 1:]:
                r["cos_full"][f"{a}|{b}"] = cos(G[a][0], G[b][0])
                r["cos_out"][f"{a}|{b}"] = cos(G[a][1], G[b][1])
        rec["halves"].append(r)
    out.append(rec)
    h0, h1 = rec["halves"]
    print(step + 1, "zval", {a: (round(h0['zval'][a], 3), round(h1['zval'][a], 3)) for a in ("cred", "false", "corrob")},
          "cos_out c|f,c|r,f|r", [(round(h0['cos_out'][k], 3), round(h1['cos_out'][k], 3)) for k in ("cred|false", "cred|corrob", "false|corrob")],
          "cos_full", [(round(h0['cos_full'][k], 3), round(h1['cos_full'][k], 3)) for k in ("cred|false", "cred|corrob", "false|corrob")],
          flush=True)


res = tb.train(args.seed, args.bytes, extra={"after_step": audit})
json.dump(out, open(os.path.join(HERE, "out_audit", f"audit_s{args.seed}.json"), "w"), indent=1)
