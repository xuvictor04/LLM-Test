"""Continual-learning testbed for the editable-memory thesis.

Runs, in ONE controlled pass over the same domain sequence:
  ARMS (forgetting):  weights-only | weights+REPLAY (the real CL baseline) | weights+memory[frozen key] |
                      weights+memory[MODEL key -- drifts]
  EDITABILITY:        delete a domain from memory (cheap+local)  vs  UNLEARN it from weights (gradient ascent)
                      -- measures cost + COLLATERAL, exposing why weights can't do targeted forgetting.
  WRONGNESS:          inject corrupted associations; SELF-CONSISTENCY flags them (run the model on each entry's OWN
                      context; a corrupt context->token pair is implausible where a genuine one is a near-miss); sweep. Uses the
                      MODEL key -- the signal needs precise retrieval to separate corrupt from genuine.

Two questions this answers that matter more than "does memory reduce forgetting" (replay does too):
  1. Is EDITING the real differentiator? (memory: local+cheap; weights-unlearn: expensive+collateral)
  2. Does editable memory survive when its key is the model's OWN, DRIFTING representation? (frozen vs model key)

  python3 cl_bench.py [DEVICE=cuda D_MODEL=256 STEPS_PER_DOMAIN=2000 N_DOMAINS=5 LAMBDA=0.5 REPLAY_FRAC=0.3 ...]
"""
import os, json, math, random, time
import torch, torch.nn as nn, torch.nn.functional as F
import sys
try: sys.stdout.reconfigure(line_buffering=True)
except Exception: pass
from memory import EditableMemory

def _i(k, d): return int(os.environ.get(k, d))
def _f(k, d): return float(os.environ.get(k, d))
DEV = os.environ.get("DEVICE", "cpu")
D = _i("D_MODEL", 128); STEPS = _i("STEPS_PER_DOMAIN", 300); SEQ = _i("SEQ", 64); BATCH = _i("BATCH", 32)
LAM = _f("LAMBDA", 0.5); WGATE = _f("WRITE_GATE", 0.3); WRONG_T = _f("WRONG_THRESH", 1.0); KW = _i("KEY_WIN", 8)
REPLAY_FRAC = _f("REPLAY_FRAC", 0.3); UNLEARN_STEPS = _i("UNLEARN_STEPS", 60)
KWM = _i("KEY_WIN_MODEL", 8); REKEY = _i("REKEY", 0); OVERLAP = _i("OVERLAP", 0)
V = 256; N = _i("N_DOMAINS", 3)
torch.manual_seed(_i("SEED", 0)); random.seed(_i("SEED", 0))


# ---------------- synthetic domains: distinct order-k Markov processes ----------------
def make_domain(seed, alphabet, order=2):
    rng = random.Random(seed); A = alphabet; table = {}
    def nxt(ctx):
        if ctx not in table:
            pr = [rng.random() ** 3 for _ in A]; s = sum(pr); table[ctx] = [p / s for p in pr]
        r = rng.random(); c = 0.0
        for i, p in enumerate(table[ctx]):
            c += p
            if r <= c: return A[i]
        return A[-1]
    def stream(n):
        out = [rng.choice(A) for _ in range(order)]
        for _ in range(n): out.append(nxt(tuple(out[-order:])))
        return bytes(out)
    return stream
ALPHA = [list(range(65, 75)), list(range(97, 107)), list(range(48, 58)), list(range(75, 85)), list(range(107, 117))]
# OVERLAP=1: every domain shares ONE alphabet (same tokens, different Markov structure) -> domains overlap,
# so weights-unlearning one should damage the others; disjoint alphabets (=0) are the easy case.
DOMAINS = [make_domain(s, ALPHA[0] if OVERLAP else ALPHA[s % len(ALPHA)]) for s in range(N)]

DATA_MODE = os.environ.get("DATA_MODE", "synthetic")     # 'real' -> use corpora under data/train/<domain>/
_CORPORA = None
if DATA_MODE == "real":
    import glob
    DNAMES = os.environ.get("DOMAINS", "eng,py,num,c").split(",")
    def _load(d):
        fs = sorted(glob.glob(f"{os.environ.get('DATA_DIR', 'data')}/train/{d}/*"))
        return b"".join(open(f, "rb").read() for f in fs)[:_i("CORPUS_CAP", 3000000)]
    _CORPORA = [c for c in (_load(d) for d in DNAMES) if len(c) > (SEQ + 1) * BATCH * 2]
    N = len(_CORPORA)
    print(f"[real data] {N} domains {DNAMES[:N]} | sizes {[len(c)//1000 for c in _CORPORA]}k bytes (distinct sources, shared ASCII = overlap)")


# ---------------- base LM ----------------
class MiniLM(nn.Module):
    def __init__(s, d):
        super().__init__(); s.emb = nn.Embedding(V, d); s.gru = nn.GRU(d, d, batch_first=True); s.head = nn.Linear(d, V)
    def forward(s, x): h, _ = s.gru(s.emb(x)); return s.head(h), h        # returns logits + hidden (the MODEL key)


FROZEN = torch.randn(V, D, device=DEV) * (D ** -0.5)
def key_frozen(x):
    e = FROZEN[x]; cs = e.cumsum(1); k = cs.clone(); k[:, KW:] = cs[:, KW:] - cs[:, :-KW]
    den = torch.arange(1, x.size(1) + 1, device=DEV).clamp(max=KW).view(1, -1, 1); return k / den

def windows(x, W):                                        # x:(B,L) -> (B,L,W) left-padded context windows
    return F.pad(x, (W - 1, 0)).unfold(1, W, 1)
@torch.no_grad()
def model_key(model, win):                                # win:(N,W) -> (N,D): GRU over the window, last hidden
    h, _ = model.gru(model.emb(win)); return h[:, -1]
def keys_ctx(mode, model, x):                             # -> (keys:(B*L,D), ctx:(B*L,W) or None)
    if mode == "model":
        w = windows(x, KWM).reshape(-1, KWM); return model_key(model, w), w
    return key_frozen(x).reshape(-1, D), None

def batch(di, corrupt=False):
    if DATA_MODE == "real":
        b = _CORPORA[di]; st = torch.randint(0, len(b) - (SEQ + 1), (BATCH,)).tolist()
        t = torch.tensor([list(b[s:s + SEQ + 1]) for s in st], device=DEV)
    else:
        bb = DOMAINS[di]((SEQ + 1) * BATCH)
        t = torch.tensor(list(bb[:(SEQ + 1) * BATCH]), device=DEV).view(BATCH, SEQ + 1)
    x, y = t[:, :-1], t[:, 1:]
    if corrupt: y = y[torch.randperm(BATCH)]
    return x, y


class Replay:
    def __init__(s, cap=40): s.by = {}; s.cap = cap
    def add(s, di, x, y): s.by.setdefault(di, []).append((x.clone(), y.clone())); s.by[di] = s.by[di][-s.cap:]
    def draw(s):
        pool = [p for v in s.by.values() for p in v]
        return random.choice(pool) if pool else None

def train_on(model, di, steps, replay=None):
    opt = torch.optim.AdamW(model.parameters(), lr=2e-3); model.train()
    for t in range(steps):
        x, y = batch(di)
        if replay is not None and random.random() < REPLAY_FRAC:          # rehearse an earlier domain
            r = replay.draw()
            if r is not None: x, y = r
        lg, _ = model(x); loss = F.cross_entropy(lg.reshape(-1, V), y.reshape(-1))
        opt.zero_grad(); loss.backward(); opt.step()
    return float(loss.detach())


def unlearn_weights(model, di, steps):
    """Try to make the weights FORGET domain di via gradient ASCENT on its loss. Returns wall-time."""
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3); model.train(); t0 = time.time()
    for _ in range(steps):
        x, y = batch(di); lg, _ = model(x); loss = F.cross_entropy(lg.reshape(-1, V), y.reshape(-1))
        opt.zero_grad(); (-loss).backward()                                # ascend -> increase loss on di
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step()
    return time.time() - t0

@torch.no_grad()
def keyfn(mode, model, x): return keys_ctx(mode, model, x)[0]              # model-key = window encoding (re-keyable)

@torch.no_grad()
def rekey_mem(model, mem):                                # DRIFT FIX: re-encode all stored keys with current model
    ii, ctx = mem.active_ctx()
    if ctx is None or ii.numel() == 0: return
    ks = [model_key(model, ctx[s:s + 8192]) for s in range(0, ii.numel(), 8192)]
    mem.rekey(torch.cat(ks), ii)

@torch.no_grad()
def selfcheck(model, mem):                                # SELF-CONSISTENCY: is each stored token plausible under the
    ii, ctx = mem.active_ctx()                            # model given the entry's OWN context? (single pass, every entry)
    if ctx is None or ii.numel() == 0: return
    fr = []
    for s in range(0, ii.numel(), 8192):
        c = ctx[s:s + 8192]; idx = ii[s:s + 8192]
        logits = model(c)[0][:, -1]                       # (n,V): model's prediction for the token AFTER the context
        tl = logits.gather(-1, mem.tok[idx].unsqueeze(-1))
        fr.append((logits > tl).float().sum(-1) / logits.size(-1))   # fraction of vocab ranked above the stored token
    mem.set_selfcon(ii, torch.cat(fr))

@torch.no_grad()
def bpb(model, di, mem=None, lam=0.0, keymode="frozen"):
    model.eval(); tot = 0.0; nb = 0
    for _ in range(6):
        x, y = batch(di); lg, _ = model(x); pm = F.softmax(lg, -1)
        if mem is not None and lam > 0:
            dist, conf, hit, w = mem.read(keyfn(keymode, model, x))
            pmem = dist.reshape(x.size(0), x.size(1), V); hp = pmem.sum(-1, keepdim=True).clamp(max=1.0)
            p = (1 - lam * hp) * pm + (lam * hp) * pmem
        else: p = pm
        lp = torch.log(p.gather(-1, y.unsqueeze(-1)).squeeze(-1).clamp_min(1e-9))
        tot += -(lp.sum().item()) / math.log(2); nb += y.numel()
    return tot / nb

@torch.no_grad()
def populate(model, mem, di, keymode, corrupt=False):
    model.eval()
    for _ in range(4):
        x, y = batch(di, corrupt=corrupt); lg, _ = model(x); pm = F.softmax(lg, -1)
        surprise = 1.0 - pm.gather(-1, y.unsqueeze(-1)).squeeze(-1)   # model error on the TRUE next token (write gate)
        k, ctx = keys_ctx(keymode, model, x)
        mem.write(k, y.reshape(-1), src=di, surprise=surprise.reshape(-1), ctx=ctx)


def main():
    print(f"CL testbed | d{D} | {N} domains | {STEPS} steps/domain | lambda {LAM} | replay_frac {REPLAY_FRAC}\n")
    base = MiniLM(D).to(DEV); rep = MiniLM(D).to(DEV)
    mem_f = EditableMemory(_i("MEM_CAP", 20000), D, DEV, V, WGATE, WRONG_T, _i("TOPK", 8), wrong_margin=_f("WRONG_MARGIN", 1.2), wrong_min_n=_i("WRONG_MIN_N", 3), flag_min_w=_f("WRONG_MIN_W", 0.12), adaptive_gate=bool(_i("WRITE_ADAPTIVE", 0)), gate_target=_f("WRITE_TARGET", 0.5))
    mem_m = EditableMemory(_i("MEM_CAP", 20000), D, DEV, V, WGATE, WRONG_T, _i("TOPK", 8), ctx_w=KWM, wrong_margin=_f("WRONG_MARGIN", 1.2), wrong_min_n=_i("WRONG_MIN_N", 3), flag_min_w=_f("WRONG_MIN_W", 0.12), adaptive_gate=bool(_i("WRITE_ADAPTIVE", 0)), gate_target=_f("WRITE_TARGET", 0.5))
    replay = Replay()
    Rwo = [[None]*N for _ in range(N)]; Rrp = [[None]*N for _ in range(N)]
    Rmf = [[None]*N for _ in range(N)]; Rmm = [[None]*N for _ in range(N)]

    for j in range(N):
        train_on(base, j, STEPS)                                          # weights-only base
        train_on(rep, j, STEPS, replay=replay)                            # replay model
        for _ in range(6): x, y = batch(j); replay.add(j, x, y)
        populate(base, mem_f, j, "frozen"); populate(base, mem_m, j, "model")
        if REKEY: rekey_mem(base, mem_m)                              # refresh ALL stored keys to the current model
        for i in range(j + 1):
            Rwo[i][j] = bpb(base, i)
            Rrp[i][j] = bpb(rep, i)
            Rmf[i][j] = bpb(base, i, mem_f, LAM, "frozen")
            Rmm[i][j] = bpb(base, i, mem_m, LAM, "model")
        print(f"after domain {j}: mem {mem_f.stats()['per_source']}")

    def meanforget(R): return sum(R[i][N-1] - R[i][i] for i in range(N-1)) / max(1, N-1)
    print("\n=== FORGETTING (mean bits/byte gained on old domains by the end; lower=less forgetting) ===")
    print(f"  weights-only        : {meanforget(Rwo):+.3f}")
    print(f"  weights + REPLAY    : {meanforget(Rrp):+.3f}   <- the standard CL baseline")
    print(f"  weights + mem[frozen]: {meanforget(Rmf):+.3f}")
    print(f"  weights + mem[MODEL] : {meanforget(Rmm):+.3f}   <- DRIFT gate (key = model's own repr)")
    print(f"  >> memory's edge over replay on forgetting: {meanforget(Rrp)-meanforget(Rmf):+.3f} "
          f"({'similar (as expected -- forgetting is table stakes)' if abs(meanforget(Rrp)-meanforget(Rmf))<0.15 else 'differs'})")
    print(f"  >> DRIFT verdict: model-key vs frozen-key = {meanforget(Rmm)-meanforget(Rmf):+.3f} "
          f"({'survives drift' if meanforget(Rmm) < meanforget(Rwo)-0.05 else 'DRIFT BREAKS IT (keys go stale)'})")

    print("\n=== EDITABILITY: targeted forgetting of domain 0 -- memory vs weights ===")
    # memory: delete domain 0 entries
    t0 = time.time(); rm = mem_f.delete_src(0); dt_mem = (time.time()-t0)*1000
    mem_after0 = bpb(base, 0, mem_f, LAM, "frozen")
    mem_others = [bpb(base, i, mem_f, LAM, "frozen") for i in range(1, N)]
    mem_others0 = [Rmf[i][N-1] for i in range(1, N)]
    mem_coll = sum(abs(a-b) for a, b in zip(mem_others, mem_others0)) / max(1, N-1)
    print(f"  MEMORY delete : {rm} entries in {dt_mem:.1f} ms | domain0 {Rmf[0][N-1]:.3f}->{mem_after0:.3f} (forgotten) | "
          f"collateral {mem_coll:.4f} ({'LOCAL' if mem_coll<0.05 else 'leaked'})")
    # weights: unlearn domain 0 via gradient ascent on the replay model
    w0_before = Rrp[0][N-1]; w_others0 = [Rrp[i][N-1] for i in range(1, N)]
    dt_w = unlearn_weights(rep, 0, UNLEARN_STEPS)
    w_after0 = bpb(rep, 0); w_others = [bpb(rep, i) for i in range(1, N)]
    w_coll = sum(abs(a-b) for a, b in zip(w_others, w_others0)) / max(1, N-1)
    print(f"  WEIGHTS unlearn: {UNLEARN_STEPS} grad-ascent steps in {dt_w*1000:.0f} ms | domain0 {w0_before:.3f}->{w_after0:.3f} | "
          f"collateral {w_coll:.4f} ({'LOCAL' if w_coll<0.05 else 'DAMAGED other domains'})")
    print(f"  >> editability edge: memory is {dt_w*1000/max(dt_mem,1e-3):.0f}x faster and {w_coll/max(mem_coll,1e-4):.0f}x less collateral")

    print("\n=== WRONGNESS: inject corrupted associations, flag by SELF-CONSISTENCY (model vs entry's own context), sweep ===")
    # The model key stores each entry's context, so we can ask the model directly whether each stored token is a
    # plausible continuation of its OWN context. CORRUPT_MODE: 'cross' pairs a domain-1 context with a DIFFERENT
    # domain's token (categorically wrong -- what real wrong-info looks like); 'shuffle' permutes tokens within domain 1
    # (subtly wrong -- still-plausible bytes, an adversarial hard case). This is a single-shot per-entry check.
    cmode = os.environ.get("CORRUPT_MODE", "cross")
    for _ in range(4):
        if cmode == "cross":
            x, _ = batch(1); _, y = batch(2 % N)          # domain-1 keys, another domain's tokens
        else:
            x, y = batch(1, corrupt=True)                 # within-domain shuffle
        k, ctx = keys_ctx("model", base, x)
        mem_m.write(k, y.reshape(-1), src=99, surprise=torch.ones(x.numel(), device=DEV), ctx=ctx)
    b1 = bpb(base, 1, mem_m, LAM, "model")
    selfcheck(base, mem_m)                                 # one pass: score every entry's token-vs-own-context plausibility
    sc, sr = mem_m.selfcon, mem_m.src
    cch = (sr == 99) & (sc >= 0); gch = (sr != 99) & (sc >= 0)
    print(f"  [{cmode}] corrupt implausibility {float(sc[cch].mean()):.3f} vs genuine {float(sc[gch].mean()):.3f} | adaptive thr (median+{mem_m.selfcon_k}*MAD)")
    fl_bad = int((mem_m.is_wrong() & (sr == 99)).sum()); tot_bad = int((sr == 99).sum())
    fl_good = int((mem_m.is_wrong() & (sr != 99)).sum())
    prec = fl_bad / max(1, fl_bad + fl_good)
    print(f"  flagged corrupt {fl_bad}/{tot_bad} (recall {fl_bad/max(1,tot_bad):.0%}) | false-positive genuine {fl_good} (precision {prec:.0%})")
    st = mem_m.stats(); sw = mem_m.sweep_wrong(); a1 = bpb(base, 1, mem_m, LAM, "model")
    print(f"  flagged {st['flagged_wrong']} | swept {sw} | domain1 {b1:.3f}->{a1:.3f} ({'recovered' if a1<b1-1e-3 else 'no change'})")
    print("\n(tiny synthetic MECHANICS check -- deltas + editability matter, absolute numbers do not.)")


def estimate():
    import time
    print(f"ESTIMATE | d{D} | {N} domains | {STEPS} steps/domain | seq {SEQ} batch {BATCH} | rekey {REKEY} | device {DEV}\n")
    model = MiniLM(D).to(DEV)
    mem = EditableMemory(_i("MEM_CAP", 300000), D, DEV, V, WGATE, WRONG_T, _i("TOPK", 8), ctx_w=KWM, wrong_margin=_f("WRONG_MARGIN", 1.2), wrong_min_n=_i("WRONG_MIN_N", 3), flag_min_w=_f("WRONG_MIN_W", 0.12), adaptive_gate=bool(_i("WRITE_ADAPTIVE", 0)), gate_target=_f("WRITE_TARGET", 0.5))
    opt = torch.optim.AdamW(model.parameters(), lr=2e-3)
    for j in range(N): populate(model, mem, j, "model")              # fill store to realistic size
    store = mem.n
    def t_op(fn, reps=4, warm=2):
        for _ in range(warm): fn()
        if DEV == "cuda": torch.cuda.synchronize()
        t0 = time.perf_counter()
        for _ in range(reps): fn()
        if DEV == "cuda": torch.cuda.synchronize()
        return (time.perf_counter() - t0) / reps
    def train_step():
        model.train()                                                 # cuDNN RNN backward requires train mode
        x, y = batch(0); lg, _ = model(x); l = F.cross_entropy(lg.reshape(-1, V), y.reshape(-1))
        opt.zero_grad(); l.backward(); opt.step()
    tt = t_op(train_step)
    tem = t_op(lambda: bpb(model, 0, mem, LAM, "model"))            # one eval (6 batches) WITH kNN read at full store
    tep = t_op(lambda: bpb(model, 0))                              # one eval without memory
    trk = t_op(lambda: rekey_mem(model, mem), reps=2)
    train_steps = N * (2 * STEPS)                                 # base + replay (reverse predictor removed)
    eval_calls = sum(j + 1 for j in range(N))                      # (i<=j) pairs
    train_time = train_steps * tt
    eval_time = eval_calls * (2 * tem + 2 * tep)                   # 2 memory arms + 2 plain arms per pair
    rekey_time = (N * trk) if REKEY else 0
    extra = 30 * tep + UNLEARN_STEPS * tt
    total = train_time + eval_time + rekey_time + extra
    print(f"store at estimate: {store} entries (grows the kNN-read cost)")
    print(f"per-op: train {tt*1000:.1f} ms | eval+read {tem*1000:.0f} ms | eval plain {tep*1000:.0f} ms | rekey {trk*1000:.0f} ms")
    print(f"  train ({train_steps} steps): {train_time/60:.1f} min")
    print(f"  eval  ({eval_calls*4} calls incl kNN read): {eval_time/60:.1f} min")
    print(f"  rekey ({N}x full store): {rekey_time/60:.1f} min")
    print(f"  ---- TOTAL ~ {total/60:.1f} min ({total/3600:.2f} h) on {DEV} ----")
    if DEV == "cpu":
        print("  RUN THIS WITH DEVICE=cuda ON THE H100 for the real number (H100 is far faster than this CPU).")
    if total/3600 > 6: print("  >6h: lower STEPS_PER_DOMAIN / MEM_CAP / N_DOMAINS, or raise BATCH, to bring it down.")


if __name__ == "__main__":
    if _i("ESTIMATE", 0): estimate()
    else: main()
