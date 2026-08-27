"""Test each novelty mechanism INSIDE Greg's structure (the overarching system).

Loads the trained checkpoint, takes Greg's real in-distribution held sets (c/eng/num/py) and
held-out OOD sets (rust, sherlock), adds a NOISE set, and scores each candidate novelty mechanism
using Greg's own representations/base:

  trigram   Greg's native Nov.score_pos (byte-trigram rarity)        [current mechanism]
  mem_nov   1 - memory-recall confidence (episodic memory)
  surprise  Greg base CE (bits/char)
  pred_ent  Greg base predictive entropy (bits)
  dist_mem  RMS z-distance of Greg's gist from the in-dist gist memory  [node_novelty style]
  gzip_head min(base_bpb,8) - gzip_bpb                                  [cheap learnability]
  dS        compression-progress: burst Greg's base on the set, bits gained below uniform

Question: which mechanism scores FAMILIAR low, NOVEL-LEARNABLE (rust/sherlock) high, and how does
each treat NOISE (engage = high, or recognize-as-not-worth-learning = low)?
"""
import os, math, gzip, copy, random
import torch, torch.nn.functional as F
from config import cfg
from data_utils import load_corpus
from system import load_system

torch.manual_seed(0); random.seed(0); torch.set_num_threads(1)
dev = cfg.DEVICE; LN2 = math.log(2); FLOOR = 8.0
sysm, _ck = load_system("runs/ckpt.pt", cfg, dev); sysm.eval()
base = sysm.base
TRAIN, HELD, OOD = load_corpus(cfg)

# build the test sets (chunks are (CTX,) byte tensors)
random.seed(7); nb = bytes(random.randint(0, 255) for _ in range(40000))
noise_chunks = [torch.tensor(list(nb[i:i + cfg.CTX])) for i in range(0, len(nb) - cfg.CTX, cfg.CTX)][:cfg.OOD_N]
SETS = {}
for dm, cs in HELD.items(): SETS[dm] = cs
for nm, cs in OOD.items(): SETS[nm] = cs
SETS["noise"] = noise_chunks
INDIST = list(HELD.keys())                      # familiar
NOVEL = list(OOD.keys())                          # novel-learnable

def stack(chunks): return torch.stack(chunks).to(dev)
@torch.no_grad()
def base_bpb(model, chunks):
    x = stack(chunks); logits, _ = model(x)
    return float(F.cross_entropy(logits[:, :-1].reshape(-1, 256), x[:, 1:].reshape(-1))) / LN2
@torch.no_grad()
def pred_entropy(chunks):
    x = stack(chunks); logits, _ = base(x); p = F.softmax(logits, -1)
    return float((-(p * (p + 1e-9).log2()).sum(-1)).mean())
@torch.no_grad()
def trigram_nov(chunks):
    return float(torch.stack([sysm.nov.score_pos(c[None]).mean() for c in chunks]).mean())
@torch.no_grad()
def mem_nov(chunks):
    x = stack(chunks); g = sysm.init_emb(x).mean(1); conf = sysm.mem.read(g)[1]
    return 1.0 - float(conf.mean())
@torch.no_grad()
def gist(chunks):
    x = stack(chunks); return sysm.init_emb(x).mean(1)
def gzip_bpb(chunks):
    b = bytes(torch.stack(chunks).reshape(-1).tolist()[:9000]); return 8.0 * len(gzip.compress(b, 9)) / len(b)
def dS(chunks, steps=50):
    n = int(len(chunks) * 0.6); tr, he = chunks[:n], chunks[n:]
    if len(he) < 2: he = chunks[-2:]
    m = copy.deepcopy(base); before = base_bpb(m, he)
    m.train(); op = torch.optim.Adam(m.parameters(), lr=1.5e-3); xt = stack(tr)
    for _ in range(steps):
        ix = torch.randint(0, xt.shape[0], (min(24, xt.shape[0]),)); x = xt[ix]
        logits, _ = m(x); loss = F.cross_entropy(logits[:, :-1].reshape(-1, 256), x[:, 1:].reshape(-1))
        op.zero_grad(); loss.backward(); op.step()
    m.eval(); after = base_bpb(m, he)
    return max(0.0, FLOOR - after) - max(0.0, FLOOR - before)

# in-dist gist memory for distance novelty
gmem = torch.cat([gist(SETS[d]) for d in INDIST], 0)
gmean = gmem.mean(0); gvar = gmem.var(0) + 1e-3
def dist_mem(chunks):
    g = gist(chunks); z2 = ((g - gmean) ** 2 / gvar).mean(-1)
    return float(z2.sqrt().mean())

MECHS = {"trigram": trigram_nov, "mem_nov": mem_nov, "surprise": lambda c: base_bpb(base, c),
         "pred_ent": pred_entropy, "dist_mem": dist_mem, "gzip_head": lambda c: min(base_bpb(base, c), FLOOR) - gzip_bpb(c),
         "dS": dS}
order = INDIST + NOVEL + ["noise"]
rows = {m: {s: fn(SETS[s]) for s in order} for m, fn in MECHS.items()}

print(f"Greg: d{cfg.D_MODEL}/L{cfg.N_LAYERS}  nodes={len(sysm.bodies)}  sets: familiar={INDIST} novel={NOVEL} + noise\n")
print(f"  {'mechanism':<10}" + "".join(f"{s[:8]:>9}" for s in order))
for m in MECHS:
    print(f"  {m:<10}" + "".join(f"{rows[m][s]:>9.2f}" for s in order))

print("\nverdict per mechanism (familiar vs novel-learnable vs noise):")
for m in MECHS:
    fam = sum(rows[m][s] for s in INDIST) / len(INDIST)
    nov = sum(rows[m][s] for s in NOVEL) / len(NOVEL)
    noi = rows[m]["noise"]
    sep = "separates" if nov > fam else "FAILS sep"
    noise_beh = "noise>novel (engages noise)" if noi > nov else ("noise<novel (filters noise)" if noi < nov * 0.6 else "noise~novel")
    print(f"  {m:<10} familiar={fam:+.2f}  novel={nov:+.2f}  noise={noi:+.2f}   {sep}; {noise_beh}")
