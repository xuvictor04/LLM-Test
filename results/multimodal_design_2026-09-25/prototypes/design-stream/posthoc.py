"""Post-hoc generation scoring of a saved Route-1 LM: code-space classifier (independent of the
codec decoder) and the waveform probe, over sampling temperatures. usage: posthoc.py PT HZ OUT"""
import os, sys, json, time, math
os.environ.update(OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", DATA_STREAM_BYTES="120000")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "tree", "src"))
import torch, torch.nn as nn, torch.nn.functional as F
torch.set_num_threads(1)
import audgen as A, codec_lib as C, probe as P
from spine.compose import compose
from lm import api as lm_api
from tok import api as tok_api
PT, HZ, OUT = sys.argv[1], int(sys.argv[2]), sys.argv[3]
sysm = compose(environ=dict(os.environ)); LMC, TOKC = sysm.configs["LM"], sysm.configs["TOK"]
model = sysm.model; model.load_state_dict(torch.load(PT)["model"]); model.eval()
SLOTS = int(LMC.vocab_slots); LIVE = int(sysm.vocab.size()); BASE = 3072; NCODE = 1000; OPEN, CLOSE = BASE + NCODE, BASE + NCODE + 1
cap_ids = [tok_api.tokenize(TOKC, sysm.vocab, (c + ".").encode()).ids for c in A.CLASSES]
C.SR[0] = A.SR; C.PRENORM[0] = True
codec = C.Codec(A.SR // HZ, 16, 64, C.FSQ(64, [8, 5, 5, 5])); codec.load_state_dict(torch.load(os.path.join(HERE, f"codec{HZ}.pt"))); codec.eval()
FR = HZ
def dec_codes(codes):
    q = codec.q; L = q.levels; hw = (L // 2).float(); digits = (codes.unsqueeze(-1) // q.basis) % L
    with torch.no_grad(): y = codec.dec(q.pout(((digits.float() - hw) / hw).transpose(1, 2)))
    return F.pad(y, (0, max(0, A.N - y.shape[-1])))[..., :A.N]
ck = torch.load(os.path.join(HERE, f"codeclf{HZ}.pt"))
emb = nn.Embedding(1000, 128); gru = nn.GRU(128, 128, batch_first=True); head = nn.Linear(128, 16)
emb.load_state_dict(ck["emb"]); gru.load_state_dict(ck["gru"]); head.load_state_dict(ck["head"])
def code_clf(codes):
    with torch.no_grad(): return head(gru(emb(codes))[0][:, -1]).argmax(-1)
probe = P.Probe(); probe.load_state_dict(torch.load(os.path.join(HERE, "probe.pt"))); probe.eval()
AUD = torch.zeros(SLOTS, dtype=torch.bool); AUD[BASE:BASE + NCODE] = True
def gen(temp, per_class=8, seed=0):
    g = torch.Generator().manual_seed(seed); out, want = [], []
    with torch.no_grad():
        for c in range(16):
            for _ in range(per_class):
                s = list(cap_ids[c]) + [OPEN]; codes = []
                for _ in range(FR):
                    lg = model.head(lm_api.encode(LMC, model, torch.tensor(s).unsqueeze(0)))[0, -1].masked_fill(~AUD, -1e9)
                    t = int(lg.argmax()) if temp == 0 else int(torch.multinomial(F.softmax(lg / temp, -1), 1, generator=g))
                    s.append(t); codes.append(t - BASE)
                out.append(codes); want.append(c)
    return torch.tensor(out), torch.tensor(want)
res = {}
xr, cr = A.batch(128, 999_777)
with torch.no_grad(): kr = torch.cat([codec.q(codec.enc(xr[i:i + 64]))[1][..., 0] for i in range(0, 128, 64)])
res["ceiling_codeclf_on_real_codes"] = (code_clf(kr) == cr).float().mean().item()
for T in (1.0, 0.7, 0.3, 0.0):
    t0 = time.time(); g, w = gen(T)
    with torch.no_grad(): pa = (probe(dec_codes(g)).argmax(-1) == w).float().mean().item()
    pred = code_clf(g)
    fam = lambda i: A.CLASSES[i].split()[0] if "beeps" not in A.CLASSES[i] else "beeps"
    res[f"T{T}"] = dict(codeclf_acc=(pred == w).float().mean().item(), probe_acc=pa,
                        family_acc=sum(fam(int(a)) == fam(int(b)) for a, b in zip(pred, w)) / len(w),
                        distinct_codes=int(torch.unique(g).numel()), s=round(time.time() - t0, 1))
    print(T, res[f"T{T}"], flush=True)
json.dump(res, open(OUT, "w"), indent=1); print(json.dumps(res))
