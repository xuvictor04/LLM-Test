"""Self-assembling domains from an UNLABELED stream -- with a LEARNED (unfrozen) domain signature.

The system gets one continuous byte stream that secretly switches between latent processes. It must detect shifts and
assemble its OWN growing set of domains, then tag memory by self-assigned provenance so it can later forget/correct.

SIGNATURE (SIG_MODE):
  learned  (default, the PRODUCT path): a small encoder trained ONLINE, self-supervised -- windows NEARBY in the
           stream (same regime) are pulled together, random windows pushed apart (InfoNCE). It learns regime
           STRUCTURE, not surface bytes, which is what byte statistics couldn't do for e.g. English vs code.
           The encoder is LIVE; domain centroids are RE-KEYED (re-encoded from stored windows) as it improves.
  bigram / unigram : frozen byte-statistic baselines -- FOR TESTING/COMPARISON ONLY.

Ground truth is used ONLY to score. Boundaries come from a shift in the (learned) signature. Wrongness (B) is a
separate SELF-CONSISTENCY check on stored entries.

  python3 self_organize.py [DEVICE=cuda DATA_MODE=real DOMAINS=eng,py,num,c D_MODEL=256 SIG_MODE=learned ...]
"""
import os, math, random, glob, sys
import torch, torch.nn as nn, torch.nn.functional as F
from memory import EditableMemory
from verification import Reconstructor, recon_loss, verify as verify_mem   # Verification (renamed from B): reconstruction, not surprise
try: sys.stdout.reconfigure(line_buffering=True)          # stream progress even when piped through tee (no -u needed)
except Exception: pass

def _i(k, d): return int(os.environ.get(k, d))
def _f(k, d): return float(os.environ.get(k, d))
DEV = os.environ.get("DEVICE", "cpu")
VERIFY = os.environ.get("VERIFY", "selfcon")               # "selfcon" (old B, default, unchanged) or "recon" (Verification)
RECON_W = _f("RECON_W", 0.1)                               # weight of the Reconstructor's training loss (VERIFY=recon only)
D = _i("D_MODEL", 128); WIN = _i("WIN", 128); NP = _i("N_PROCESSES", 4); STREAM_LEN = _i("STREAM_LEN", 120000)
SUSTAIN = _i("SUSTAIN", 2); NEW_DIST = _f("NEW_DIST", 0.35); SHIFT_DIST = _f("SHIFT_DIST", 0.30)
SIG_MODE = os.environ.get("SIG_MODE", "learned"); SIG_D = _i("SIG_D", 64); SIG_DIM = _i("SIG_DIM", 512)
ENC_EVERY = _i("ENC_EVERY", 1); ENC_BATCH = _i("ENC_BATCH", 48); TEMP = _f("TEMP", 0.1); REKEY_EVERY = _i("REKEY_EVERY", 200)
MANAGE_EVERY = _i("MANAGE_EVERY", 500); MANAGE_MERGE = _f("MANAGE_MERGE", 0.12)   # domain management: merge/cull cadence
MANAGE_ON = bool(_i("MANAGE", 1))                          # MANAGE=0 -> ABLATION: no merge/cull (domains grow unbounded)
MANAGE_MIN = _i("MANAGE_MIN", 15); MANAGE_STALE = _i("MANAGE_STALE", 2000)        #   cull domains < MIN windows unseen for STALE
KW = _i("KEY_WIN", 8); V = 256
USE_TOK = bool(_i("TOKENIZER", 0)); TOK_ONLINE = bool(_i("TOK_ONLINE", 0)); TOK = None; BLEN = None   # TOK_ONLINE=1 mints during training
torch.manual_seed(_i("SEED", 0)); random.seed(_i("SEED", 0))


# ---------------- latent processes + the mixed, unlabeled stream ----------------
def make_proc(seed, alphabet, order=2):
    rng = random.Random(seed); A = alphabet; tbl = {}
    def nxt(c):
        if c not in tbl:
            p = [rng.random() ** 3 for _ in A]; s = sum(p); tbl[c] = [q / s for q in p]
        r = rng.random(); a = 0.0
        for i, q in enumerate(tbl[c]):
            a += q
            if r <= a: return A[i]
        return A[-1]
    def gen(n):
        o = [rng.choice(A) for _ in range(order)]
        for _ in range(n): o.append(nxt(tuple(o[-order:])))
        return bytes(o[order:])
    return gen

ALPHA = [list(range(65, 80)), list(range(97, 112)), list(range(48, 58)), list(range(80, 95)), list(range(112, 123))]
DATA_MODE = os.environ.get("DATA_MODE", "synthetic")
if DATA_MODE == "real":
    DN = os.environ.get("DOMAINS", "eng,py,num,c").split(",")
    CORP = [b"".join(open(f, "rb").read() for f in sorted(glob.glob(f"{os.environ.get('DATA_DIR', 'data')}/train/{d}/*")))[:_i("CORPUS_CAP", 2000000)] for d in DN]
    CORP = [c for c in CORP if len(c) > 5000]; NP = len(CORP)
    VAL_FRAC = _f("VAL_FRAC", 0.05)                        # HELD-OUT tail of each corpus, never sampled into the
    VALC = [c[int(len(c) * (1 - VAL_FRAC)):] for c in CORP]  #   training stream. Without it, "is it memorizing?" is
    CORP = [c[:int(len(c) * (1 - VAL_FRAC))] for c in CORP]  #   unanswerable -- every eval was on training data.
    if USE_TOK:                                            # EXPANDING SUBWORD MODE: an online byte-BPE that GROWS its vocab
        from tokenizer import DynamicTokenizer             #   by mint-on-repetition as it reads the stream (byte-grounded)
        _tp = os.environ.get("TOKENIZER_PATH", "data/dyntok.json")
        VMAX = _i("VMAX", 4096)
        _target = _i("SEED_VOCAB", 512) if TOK_ONLINE else VMAX            # online: only SEED here; keep minting during training
        _passes = _i("SEED_PASSES", 2) if TOK_ONLINE else _i("GROW_PASSES", 8)
        if os.path.exists(_tp) and not TOK_ONLINE:
            TOK = DynamicTokenizer.load(_tp)
        else:
            TOK = DynamicTokenizer(vmax=VMAX, min_pair=_i("MIN_PAIR", 50), max_tok=_i("MAX_TOK", 16), dropout=_f("TOK_DROPOUT", 0.0))
            gb = b"".join(c[:_i("TOK_GROW_CAP", 1000000)] for c in CORP)   # bytes the tokenizer grows on
            curve = []
            for _p in range(_passes):                      # iterative: tally pairs at current granularity, mint the frequent ones
                for gi in range(0, len(gb), 8192): TOK.segment(gb[gi:gi + 8192], count=True)
                minted = 0
                while TOK.vocab_size < _target:
                    if TOK.maybe_grow() is None: break
                    minted += 1
                curve.append(TOK.vocab_size)
                print(f"[tokenizer] {'seed' if TOK_ONLINE else 'grow'} pass {_p+1}: vocab {TOK.vocab_size}")
                if minted == 0: break                      # converged: no pair crosses the min_pair threshold
            if not TOK_ONLINE: TOK.save(_tp)
            print(f"[tokenizer] {'SEEDED (will keep minting live)' if TOK_ONLINE else 'EXPANDING byte-BPE grew'} 256 -> {TOK.vocab_size} (mint-on-repetition, {len(curve)} passes): {curve}")
        if TOK_ONLINE:                                     # corpora stay BYTES; model sized to VMAX; tokenized live in main()
            V = VMAX; BLEN = None
            print(f"[tokenizer] ONLINE mode: model sized to vocab {V}; tokenizer keeps minting throughout training")
        else:
            CORP = [TOK.segment(c, count=False) for c in CORP]             # final deterministic tokenization of each corpus
            V = TOK.vocab_size; BLEN = torch.tensor(TOK.bytes_per_id, dtype=torch.float, device=DEV)
            print(f"[tokenizer] vocab {V} | corpora -> tokens ({sum(len(c) for c in CORP)} total, ~{sum(len(c) for c in CORP)//max(1,len(CORP))}/domain)")
    def seg_from(p, L): s = random.randint(0, len(CORP[p]) - L - 1); return CORP[p][s:s + L]
else:
    PROCS = [make_proc(s, ALPHA[s % len(ALPHA)]) for s in range(NP)]
    def seg_from(p, L): return PROCS[p](L)

PHASED = bool(_i("PHASED", 0))                             # NON-STATIONARY stream: processes ENTER and FADE over time
PHASE_SCHED = [[0, 1], [0, 1, 2], [1, 2, 3], [2, 3]]      # who is active in each quarter (2 enters, 0 fades, 3 enters, 1 fades)
PH_BOUNDS = []                                             # stream positions where each phase starts
def build_stream():
    buf = []; lab = []; sw = []; pos = 0
    if PHASED:                                             # NON-STATIONARY: each phase has a different ACTIVE set
        per = STREAM_LEN // len(PHASE_SCHED)
        for pi, act in enumerate(PHASE_SCHED):
            PH_BOUNDS.append(pos); act = [a for a in act if a < NP] or list(range(NP))
            while pos < min((pi + 1) * per, STREAM_LEN) and pos < STREAM_LEN:
                p = random.choice(act); L = random.randint(_i("SEG_MIN", 700), _i("SEG_MAX", 1800))
                seg = list(seg_from(p, L)); buf += seg; lab += [p] * len(seg); sw.append(pos); pos += len(seg)
    else:
        while pos < STREAM_LEN:
            p = random.randrange(NP); L = random.randint(_i("SEG_MIN", 700), _i("SEG_MAX", 1800))
            seg = list(seg_from(p, L)); buf += seg; lab += [p] * len(seg); sw.append(pos); pos += len(seg)
    return buf[:STREAM_LEN], lab[:STREAM_LEN], set(x for x in sw if x < STREAM_LEN)


# ---------------- base LM + LEARNED signature encoder ----------------
MODEL_TYPE = os.environ.get("MODEL", "gru")               # "gru" (default) or "transformer" (scales to H100)
DROPOUT = _f("DROPOUT", 0.0)                               # ANTI-OVERFIT, default OFF. The model is currently badly
WEIGHT_DECAY = _f("WEIGHT_DECAY", 0.0)                     # UNDERFIT (more passes keep helping), so these would only
                                                           # handicap it. Turn them on when val-vs-train shows a gap.
class MiniLM(nn.Module):                                   # base LM (GRU, optionally multi-layer)
    def __init__(s, d, layers=1):
        super().__init__(); s.emb = nn.Embedding(V, d); s.drop = nn.Dropout(DROPOUT)
        s.gru = nn.GRU(d, d, num_layers=layers, batch_first=True, dropout=(DROPOUT if layers > 1 else 0.0))
        s.head = nn.Linear(d, V)
    def encode(s, x): h, _ = s.gru(s.drop(s.emb(x))); return s.drop(h)   # (B,L,D) hidden -- also the memory-key source
    def forward(s, x): h = s.encode(x); return s.head(h), h
class TinyTransformer(nn.Module):                          # decoder-only Transformer (causal) -- the H100-scale option
    def __init__(s, d, layers=4, heads=8, maxlen=512):
        super().__init__(); s.emb = nn.Embedding(V, d); s.pos = nn.Embedding(maxlen, d); s.maxlen = maxlen
        lyr = nn.TransformerEncoderLayer(d, heads, dim_feedforward=4 * d, batch_first=True, dropout=0.0, activation="gelu", norm_first=True)
        s.tr = nn.TransformerEncoder(lyr, layers, enable_nested_tensor=False); s.head = nn.Linear(d, V)
    def encode(s, x):
        L = x.size(1); p = torch.arange(L, device=x.device).clamp(max=s.maxlen - 1)
        h = s.emb(x) + s.pos(p)
        m = torch.triu(torch.ones(L, L, device=x.device), 1).bool()            # causal mask
        return s.tr(h, mask=m)
    def forward(s, x): h = s.encode(x); return s.head(h), h
def build_lm():
    if MODEL_TYPE == "transformer":
        return TinyTransformer(D, layers=_i("LAYERS", 4), heads=_i("HEADS", 8), maxlen=_i("MAXLEN", 512))
    return MiniLM(D, layers=_i("LAYERS", 1))
FABRIC = bool(_i("FABRIC", 0))                             # FABRIC=1: the routed expert population
ENS_K = _i("ENS_K", 2)                                     # how many experts are ensembled at the output layer
SOCIETY = bool(_i("SOCIETY", 1))                           # 1 = independent experts blended at a router (default)
                                                           # 0 = the old chained mixture (entangles every expert)
class FabricNode(nn.Module):
    """A fabric node: residual MLP (d -> hid -> d). Born as an IDENTITY (second layer zero-init) so adding a node
    never disrupts what already works -- the same principle as the adapter's zero-init B."""
    def __init__(s, d, hid=None):
        super().__init__(); hid = hid or 2 * d
        s.net = nn.Sequential(nn.Linear(d, hid), nn.GELU(), nn.Linear(hid, d))
        nn.init.zeros_(s.net[2].weight); nn.init.zeros_(s.net[2].bias)
    def forward(s, x): return x + s.net(x)

class Fabric(nn.Module):
    """ROUTER FABRIC: routing state `c` is a DISTRIBUTION over operators (nodes + HALT), not a hard choice.
    Each step every node computes, contributions are mixed by `c`, and a learned TRANSITION MATRIX R re-routes the
    distribution from each node to every operator -- so mass flows node->node across multiple hops (the fabric
    reroutes within itself). HALT is an ABSORBING operator, so depth is adaptive and can be charged for (ponder).
    The routing query is RECURRENT: the previous routing state + surprise bias the next query.
    Contrast with a top-1 bank: there is no hard selection to get wrong, and EVERY node gets gradient every step."""
    def __init__(s, d, sig_d, dk, n0, alpha, max_steps, hid_mult=2, min_steps=1, norm_only=False):
        super().__init__()
        s.d, s.sig_d, s.dk, s.alpha, s.max_steps, s.hid = d, sig_d, dk, alpha, max_steps, hid_mult * d
        s.min_steps = min_steps                             # HALT blocked for this many steps. DEFAULT 0: measured,
                                                            #   the router's OWN light-touch routing (mass ~0.1) beat
                                                            #   forcing node use (2.034 vs 2.176). Only raise this if
                                                            #   node mass is ~0 AND the fabric is underperforming.
        s.bodies = nn.ModuleList([FabricNode(d, s.hid) for _ in range(n0)])
        s.cent = F.normalize(torch.randn(n0, sig_d), dim=-1)   # one region per expert
        s.keys = nn.ParameterList([nn.Parameter(torch.randn(dk) * 0.1) for _ in range(n0)])
        s.qproj = nn.ModuleList([nn.Linear(sig_d, dk) for _ in range(n0)])
        s.halt_key = nn.Parameter(torch.randn(dk) * 0.1)
        s.q_entry = nn.Linear(sig_d, dk); s.nov = nn.Linear(1, dk); s.ctrl = nn.Linear(3, dk)
        s.norm = nn.LayerNorm(d); s.grown = 0
        s.norm_only = norm_only                             # ABLATION: normalization only, no nodes, no routing
        s.route_t = float(os.environ.get("ROUTE_T", 1.0))   # <1 sharpens routing -> mass concentrates -> specialization
        # GROUNDED ROUTING: an expert owns a REGION of signature space, exactly as a domain does (and domains DO
        # differentiate: purity 0.92). Free learned keys start symmetric, and with every expert trained to solve the
        # whole task there is no gradient that breaks the symmetry -> uniform generalists. A centroid EMA'd toward the
        # signatures it actually serves acquires a constituency, so its traffic becomes distinct and it specializes.
        s.grounded = bool(int(os.environ.get("ROUTE_GROUNDED", 1)))
        s.cent_m = float(os.environ.get("CENT_EMA", 0.02))
    def grow(s, gist=None):                                 # add an expert; returns its new params
        dev = s.halt_key.device
        _ng = (F.normalize(gist.detach().mean(0, keepdim=True).cpu(), dim=-1) if gist is not None
               else F.normalize(torch.randn(1, s.sig_d), dim=-1))
        s.cent = torch.cat([s.cent, _ng], 0)                # the newborn OWNS the region that triggered its birth
        b = FabricNode(s.d, s.hid).to(dev)                  # IDENTITY at birth -> inherits the CURRENT base's competence
        k = nn.Parameter(s.seed_key(gist) if gist is not None else torch.randn(s.dk, device=dev) * 0.1)
        q = nn.Linear(s.sig_d, s.dk).to(dev)
        s.bodies.append(b); s.keys.append(k); s.qproj.append(q); s.grown += 1
        return list(b.parameters()) + [k] + list(q.parameters())
    def society(s, h, gist, nov):
        """SOCIETY OF EXPERTS: every expert maps the SAME base representation to its OWN output -- no chaining, so
        expert i's output never depends on expert j's. A router layer blends the outputs. Contrast the mixture path
        below, where each step's blend feeds the next step, entangling every expert with every other."""
        N = len(s.bodies)
        K = torch.stack(list(s.keys) + [s.halt_key], 0)
        nb = s.nov(nov[:, None])
        if s.grounded:                                                         # route by REGION OWNERSHIP
            C = F.normalize(s.cent[:N].to(gist.device), dim=-1)
            w = torch.softmax((F.normalize(gist, dim=-1) @ C.t()) / max(1e-3, s.route_t), -1)
            with torch.no_grad():                                              # the winner's region moves toward this signature
                j = int(w.mean(0).argmax())
                s.cent[j] = F.normalize((1 - s.cent_m) * s.cent[j].to(gist.device)
                                        + s.cent_m * F.normalize(gist, dim=-1).mean(0), dim=-1).cpu()
        else:
            c = torch.softmax(((s.q_entry(gist) + nb) @ K.t()) / max(1e-3, s.route_t), -1)
            w = c[:, :N]; w = w / w.sum(-1, keepdim=True).clamp_min(1e-9)      # router weights over experts
        O = torch.stack([b(h) for b in s.bodies], 1)                           # (B,N,L,d) INDEPENDENT outputs
        return s.norm((w[:, :, None, None] * O).sum(1)), w, O
    def remove(s, j):
        """DELETE an expert outright: its parameters are gone. In a society this should cost roughly that expert's
        own contribution; in an entangled mixture it damages everyone (the weights-unlearn failure mode)."""
        keep = [i for i in range(len(s.bodies)) if i != j]
        s.bodies = nn.ModuleList([s.bodies[i] for i in keep])
        s.keys = nn.ParameterList([s.keys[i] for i in keep])
        s.qproj = nn.ModuleList([s.qproj[i] for i in keep])
    def seed_key(s, gist):
        """TARGETED BIRTH: put the new expert's key where the router will actually send this region, instead of at
        random. A randomly-keyed expert receives no traffic, gets no gradient, and stays dead (measured: 12/17 idle)."""
        with torch.no_grad(): return s.q_entry(gist).detach().squeeze(0).clone()
    def forward(s, h, gist, nov):
        N = len(s.bodies); HALT = N
        if s.norm_only:                                                       # control arm: just the normalization
            steps = max(1, min(s.max_steps, 2 + N // 2))
            for _ in range(steps): h = s.norm(h)
            z = h.new_zeros(())
            return h, z, torch.zeros(N + 1, device=h.device), z
        K = torch.stack(list(s.keys) + [s.halt_key], 0)                       # (N+1, dk) operator keys
        nb = s.nov(nov[:, None])                                              # surprise -> routing bias
        c = torch.softmax((s.q_entry(gist) + nb) @ K.t(), -1)                 # (B, N+1) ENTRY distribution
        steps = max(1, min(s.max_steps, 2 + N // 2))                          # adaptive depth budget
        depth = h.new_zeros(()); mass = torch.zeros(N + 1, device=h.device); bal = h.new_zeros(())
        for _t_ in range(steps):
            if _t_ < s.min_steps:                                             # block HALT early: force the nodes to be used
                c = torch.cat([c[:, :N], torch.zeros_like(c[:, N:])], -1)
                c = c / c.sum(-1, keepdim=True).clamp_min(1e-9)
            nm = c[:, :N]
            bal = bal + N * (nm.mean(0) ** 2).sum()                            # load balance: spread mass across nodes
            Bo = torch.stack([b(h) for b in s.bodies], 1)                     # (B,N,L,d) EVERY node computes
            upd = (nm[:, :, None, None] * Bo).sum(1)                          # soft mixture of node outputs
            h = s.norm(h + s.alpha * (upd - h))                               # residual fabric step
            depth = depth + (1 - c[:, HALT]).mean(); mass = mass + c.mean(0).detach()
            ent = -(c.clamp_min(1e-9).log() * c).sum(-1)
            summ = torch.stack([nm.sum(-1), c[:, HALT], ent], -1)             # recurrent control summary
            bias = nb + s.ctrl(summ)
            Q = torch.stack([q(gist) for q in s.qproj], 1) + bias[:, None, :] # (B,N,dk) per-node routing queries
            R = torch.softmax(torch.einsum('bnk,mk->bnm', Q, K), -1)          # (B,N,N+1) TRANSITION MATRIX
            nxt = torch.einsum('bn,bnm->bm', nm, R)                           # propagate mass node -> operator
            nxt = nxt.clone(); nxt[:, HALT] = nxt[:, HALT] + c[:, HALT]       # HALT absorbs
            c = nxt / nxt.sum(-1, keepdim=True).clamp_min(1e-9)
        return h, depth / steps, mass / steps, bal / steps

class PlateauGrowth:
    """Grow capacity when PROGRESS STALLS, not when a distance threshold trips: fast-vs-slow EMA of the loss is
    scale-free, so it needs no retuning across byte/token modes. Pruning is deliberately OFF by default -- fixed
    thresholds caused grow/prune sawtooth (and did, measurably, in the flat bank: 77% churn)."""
    def __init__(s, rel=0.002, cooldown=1500, warmup=2000):
        s.fast = s.slow = None; s.rel = rel; s.cool = cooldown; s.warm = warmup; s.last = -10**9
    def step(s, loss, t):
        s.fast = loss if s.fast is None else 0.98 * s.fast + 0.02 * loss
        s.slow = loss if s.slow is None else 0.998 * s.slow + 0.002 * loss
        if t < s.warm or t - s.last < s.cool: return False
        if (s.slow - s.fast) / max(1e-6, abs(s.slow)) < s.rel:               # improvement stalled -> add capacity
            s.last = t; return True
        return False

EXPERTS = bool(_i("EXPERTS", 0))                           # EXPERTS=1: a growing, selective bank of per-domain experts
class ExpertBank(nn.Module):
    """GROWING + SELECTIVE per-domain experts: a low-rank adapter (d->r->d) on the base model's hidden state. One
    expert is minted when a domain is born, freed when the domain is culled/merged/unlearned -- the same evolve+select
    principle as the domains and the tokenizer. B init=0 so a fresh/added expert is a no-op (doesn't disrupt the base)."""
    def __init__(s, n, d, r):
        super().__init__(); s.A = nn.Parameter(torch.randn(n, d, r) * (d ** -0.5)); s.B = nn.Parameter(torch.zeros(n, r, d))
    def reset(s, sl):
        with torch.no_grad(): s.A[sl].normal_(0, s.A.size(-1) ** -0.5); s.B[sl].zero_()
    def clone_into(s, dst, src):                              # REPLICATE: copy an expert's adapter + a small perturbation
        with torch.no_grad(): s.A[dst] = s.A[src] + 0.02 * torch.randn_like(s.A[src]); s.B[dst] = s.B[src] + 0.02 * torch.randn_like(s.B[src])
    def one(s, h, sl):    return h + (h @ s.A[sl]) @ s.B[sl]
    def batch(s, h, sls): return h + torch.bmm(torch.bmm(h, s.A[sls]), s.B[sls])
class ExpertRouter:
    """A SEPARATE evolving population of experts, DECOUPLED from domains (a domain is NOT one expert). Each expert owns
    a centroid in SIGNATURE space + a low-rank adapter, and is COARSER than a domain (many domains -> one expert) so it
    gets real data. Its OWN selective force -- the DUAL of the domains': CREATE when a signature fits no expert, REPLICATE
    (split) a busy expert, CULL rare/stale ones. Experts are shared substrate; editable knowledge stays in per-domain MEMORY."""
    def __init__(s, bank, new_dist, cull_stale, rep_mult=2.5, cull_frac=0.25, grace=3000,
                 mode="rank", cull_rank=0.08, pressure_on=0.75, merge_dist=0.10, fit_win=4000):
        s.bank = bank; s.cent = {}; s.use = {}; s.last = {}; s.born = {}; s.free = list(range(bank.A.size(0)))
        s.cap = bank.A.size(0)
        s.new_dist = new_dist; s.cull_stale = cull_stale; s.rep_mult = rep_mult; s.cull_frac = cull_frac
        s.grace = grace                                       # min age before an expert may be culled -- without it,
        s.mode = mode                                         #   selection kills experts before they can specialize
        s.cull_rank = cull_rank; s.pressure_on = pressure_on; s.merge_dist = merge_dist; s.fit_win = fit_win
        s.created = 0; s.replicated = 0; s.removed = 0; s.merged = 0
    def route(s, sig, step, create=True):                     # -> expert slot (or -1)
        sig = sig.detach()
        if s.cent:
            ids = list(s.cent); sims = torch.stack([s.cent[i] for i in ids]) @ sig; j = int(sims.argmax()); best = ids[j]
            if (1 - float(sims[j])) <= s.new_dist or not create or not s.free:
                if create: s.cent[best] = F.normalize(0.97 * s.cent[best] + 0.03 * sig, dim=0); s.use[best] = s.use.get(best, 0) + 1; s.last[best] = step
                return best
        if not create or not s.free: return -1
        sl = s.free.pop(); s.bank.reset(sl); s.cent[sl] = sig.clone(); s.use[sl] = 1; s.last[sl] = step; s.born[sl] = step; s.created += 1; return sl
    def _fit(s, step):
        """AGE-NORMALIZED fitness: usage per unit of life, so a young expert isn't penalized for being young."""
        return {i: s.use.get(i, 0) / max(1.0, min(step - s.born.get(i, step), s.fit_win)) for i in s.cent}
    def _drop(s, i):
        s.free.append(i); s.cent.pop(i, None); s.use.pop(i, None); s.last.pop(i, None); s.born.pop(i, None)
    def manage(s, step):
        """Selection RELATIVE to the rest of the population, mirroring how DOMAINS are managed (merge AND cull):
          MERGE   redundant experts (near-identical centroids) by AVERAGING their adapters -- keeps what both learned,
                  where killing destroyed it. The domain population already merges; this makes the two symmetric.
          CULL    only under CAPACITY PRESSURE (slots scarce) and only the BOTTOM RANK fraction by fitness -> bounded,
                  scale-free turnover. A mean/threshold rule can wipe out most of the population at once, because a few
                  dominant experts drag the mean above nearly everyone (that was the 77%-churn failure).
          Set CULL_MODE=thresh for the older mean-threshold rule."""
        if not s.cent: return
        fit = s._fit(step)
        if s.free:                                            # REPLICATE: the fittest splits (clone + perturb)
            mean = sum(fit.values()) / max(1, len(fit)); d = max(fit, key=fit.get)
            if mean > 0 and fit[d] >= s.rep_mult * mean and s.use.get(d, 0) >= 5:
                sl = s.free.pop(); s.bank.clone_into(sl, d)
                s.cent[sl] = F.normalize(s.cent[d] + 0.02 * torch.randn_like(s.cent[d]), dim=0)
                s.use[sl] = s.use[d] / 2; s.use[d] -= s.use[sl]; s.last[sl] = step; s.born[sl] = step; s.replicated += 1
        if s.merge_dist > 0 and len(s.cent) > 2:              # MERGE the most redundant pair (preserves learning)
            ids = list(s.cent); C = F.normalize(torch.stack([s.cent[i] for i in ids]), dim=-1)
            M = C @ C.t(); M.fill_diagonal_(-2.0); k = int(torch.argmax(M).item()); a, b = ids[k // len(ids)], ids[k % len(ids)]
            if 1 - float(M[k // len(ids), k % len(ids)]) <= s.merge_dist:
                if fit.get(b, 0) > fit.get(a, 0): a, b = b, a  # keep the fitter, absorb the other
                with torch.no_grad():                          # AVERAGE adapters: both experts' learning survives
                    s.bank.A[a] = 0.5 * (s.bank.A[a] + s.bank.A[b]); s.bank.B[a] = 0.5 * (s.bank.B[a] + s.bank.B[b])
                s.cent[a] = F.normalize(s.cent[a] + s.cent[b], dim=0); s.use[a] = s.use.get(a, 0) + s.use.get(b, 0)
                s._drop(b); s.merged += 1
        if s.mode == "rank":                                  # CULL: density-dependent + rank-relative
            if (1 - len(s.free) / max(1, s.cap)) >= s.pressure_on:
                order = sorted(s.cent, key=lambda i: fit.get(i, 0))
                for i in order[:max(1, int(s.cull_rank * len(s.cent)))]:
                    if len(s.cent) <= 2: break
                    if step - s.born.get(i, step) < s.grace: continue
                    s._drop(i); s.removed += 1
        else:                                                 # legacy mean-threshold rule
            mean = sum(s.use.get(i, 0) for i in s.cent) / len(s.cent)
            for i in list(s.cent):
                if len(s.cent) <= 2: break
                if step - s.born.get(i, step) < s.grace: continue
                if s.use.get(i, 0) < s.cull_frac * mean and step - s.last.get(i, 0) > s.cull_stale:
                    s._drop(i); s.removed += 1
        for i in s.use: s.use[i] *= 0.9                       # decay -> fitness reflects RECENT use
class SigEncoder(nn.Module):                               # LEARNED, LIVE domain-signature encoder (stays GRU regardless of LM)
    def __init__(s, d, sd):
        super().__init__(); s.emb = nn.Embedding(V, d); s.gru = nn.GRU(d, d, batch_first=True); s.proj = nn.Linear(d, sd)
    def forward(s, x): h, _ = s.gru(s.emb(x)); return F.normalize(s.proj(h[:, -1]), dim=-1)

FROZEN = torch.randn(V, D, device=DEV) * (D ** -0.5)       # (testing-only byte baselines + memory retrieval key)
def key_frozen(x):
    e = FROZEN[x]; cs = e.cumsum(1); k = cs.clone(); k[:, KW:] = cs[:, KW:] - cs[:, :-KW]
    den = torch.arange(1, x.size(1) + 1, device=DEV).clamp(max=KW).view(1, -1, 1); return k / den

# ---- MEMORY RETRIEVAL KEY (product path = the model's OWN representation, unfrozen + re-keyed) ----
# KEY_SRC=model : key each position by a GRU encoding of its last KW bytes, using the LIVE base model. Domain-aware,
#                 so a query from one process stops retrieving another's entries (the cross-domain contamination
#                 that made 'deleting one domain' perturb the others). Re-keyed periodically as the model drifts.
# KEY_SRC=frozen: static byte-statistic key -- TESTING BASELINE ONLY.
KEY_SRC = os.environ.get("KEY_SRC", "model")
def _windows(x, W): return F.pad(x, (W - 1, 0)).unfold(1, W, 1)             # (B,L) -> (B,L,W)
@torch.no_grad()
def _model_key(win):                                                        # (N,W) -> (N,D)
    return model.encode(win)[:, -1]
@torch.no_grad()
def mem_key(x):                                                             # (B,L) -> (B*L, D)
    if KEY_SRC == "model": return _model_key(_windows(x, KW).reshape(-1, KW))
    return key_frozen(x).reshape(-1, D)
@torch.no_grad()
def mem_ctx(x):                                                             # stored context so keys can be re-encoded
    return _windows(x, KW).reshape(-1, KW) if KEY_SRC == "model" else None
@torch.no_grad()
def rekey_memory(mem):                                                      # refresh ALL stored keys with the current model
    if KEY_SRC != "model": return
    ii, ctx = mem.active_ctx()
    if ctx is None or ii.numel() == 0: return
    ks = [_model_key(ctx[s:s + 8192]) for s in range(0, ii.numel(), 8192)]
    mem.rekey(torch.cat(ks), ii)

def sig_of(win, enc):                                      # win: list[int] -> signature vector
    if SIG_MODE == "learned":
        with torch.no_grad(): return enc(torch.tensor([win], device=DEV))[0]
    t = torch.tensor(win, device=DEV, dtype=torch.long)
    if SIG_MODE == "bigram" and t.numel() > 1:
        bg = (t[:-1] * 256 + t[1:]) % SIG_DIM; v = torch.zeros(SIG_DIM, device=DEV)
        v.scatter_add_(0, bg, torch.ones_like(bg, dtype=torch.float)); return F.normalize(v, dim=0)
    return F.normalize(FROZEN[t].mean(0), dim=0)

def contrastive_step(enc, opt, stream, seen):              # InfoNCE: nearby windows = positive, random = negative
    hi = seen - 3 * WIN
    if hi < ENC_BATCH: return
    enc.train()
    st = [random.randint(0, hi) for _ in range(ENC_BATCH)]; off = [random.randint(WIN // 2, 2 * WIN) for _ in st]
    A = torch.tensor([list(stream[s:s + WIN]) for s in st], device=DEV)
    P = torch.tensor([list(stream[s + o:s + o + WIN]) for s, o in zip(st, off)], device=DEV)
    za, zp = enc(A), enc(P)
    logits = za @ zp.t() / TEMP
    loss = F.cross_entropy(logits, torch.arange(ENC_BATCH, device=DEV))
    opt.zero_grad(); loss.backward(); opt.step()
    return float(loss.detach())


class DomainAssembler:
    """Self-organizes an unlabeled stream into domains AND MANAGES them: MERGES redundant domains and CULLS
    tiny/stale ones (analogous to the expert cull -- the project's biggest win). Domains carry STABLE ids so the
    memory's provenance stays valid across merges/culls. manage() prunes the domain set and the MEMORY together --
    a merge reassigns the loser's memory to the survivor; a cull deletes the culled domain's memory."""
    def __init__(s):
        s.run_sig = None; s.cent = {}; s.wins = {}; s.size = {}; s.last = {}
        s.cur = -1; s.run = 0; s.next_id = 0; s.merged = {}                # merged[b]=a: b was folded into a (for scoring)
    def _new(s, sig, step):
        i = s.next_id; s.next_id += 1
        s.cent[i] = sig.clone(); s.wins[i] = []; s.size[i] = 0; s.last[i] = step; return i
    def resolve(s, d):
        while d in s.merged: d = s.merged[d]                              # follow merge chains to the survivor
        return d
    def update(s, sig, window, step):
        boundary = False
        if s.run_sig is None: s.run_sig = sig.clone()
        else:
            d = 1 - F.cosine_similarity(sig.unsqueeze(0), s.run_sig.unsqueeze(0)).item()
            if d > SHIFT_DIST: s.run += 1; boundary = s.run >= SUSTAIN
            else: s.run = 0; s.run_sig = F.normalize(0.85 * s.run_sig + 0.15 * sig, dim=0)
        if boundary or s.cur < 0 or s.cur not in s.cent:
            s.cur = s._assign(sig, step); s.run_sig = sig.clone(); s.run = 0
        s.size[s.cur] += 1; s.last[s.cur] = step
        if len(s.wins[s.cur]) < 40: s.wins[s.cur].append(window)
        return s.cur, boundary
    def _assign(s, sig, step):
        if not s.cent: return s._new(sig, step)
        ids = list(s.cent); ds = [1 - F.cosine_similarity(sig.unsqueeze(0), s.cent[i].unsqueeze(0)).item() for i in ids]
        j = min(range(len(ids)), key=lambda k: ds[k])
        if ds[j] < NEW_DIST:
            i = ids[j]; s.cent[i] = F.normalize(0.9 * s.cent[i] + 0.1 * sig, dim=0); return i
        return s._new(sig, step)
    def rekey(s, enc):
        with torch.no_grad():
            for i in list(s.cent):
                if s.wins[i]:
                    W = torch.tensor([w for w in s.wins[i]], device=DEV); s.cent[i] = F.normalize(enc(W).mean(0), dim=0)
    def manage(s, step, mem, merge_dist, min_size, stale):
        merged = culled = 0
        ids = list(s.cent)
        for ai in range(len(ids)):
            a = ids[ai]
            if a not in s.cent: continue
            for bi in range(ai + 1, len(ids)):
                b = ids[bi]
                if b not in s.cent or a not in s.cent: continue
                if 1 - F.cosine_similarity(s.cent[a].unsqueeze(0), s.cent[b].unsqueeze(0)).item() < merge_dist:
                    if mem is not None: mem.reassign_src(b, a)             # MERGE -> memory follows (indirect prune)
                    na, nb = s.size[a], s.size[b]
                    s.cent[a] = F.normalize((s.cent[a] * na + s.cent[b] * nb) / max(1, na + nb), dim=0)
                    s.size[a] += nb; s.wins[a] = (s.wins[a] + s.wins[b])[:40]; s.last[a] = max(s.last[a], s.last[b])
                    del s.cent[b], s.wins[b], s.size[b], s.last[b]; s.merged[b] = a; merged += 1
        for d in list(s.cent):
            if s.size[d] < min_size and step - s.last[d] > stale:
                if mem is not None: mem.delete_src(d)                     # CULL -> memory follows (direct prune)
                del s.cent[d], s.wins[d], s.size[d], s.last[d]; culled += 1
        return merged, culled


@torch.no_grad()
def compose_test(model, mem, stream, labels, WIN, V, DEV, EVAL_N=64):
    """Do the self-assembled segments WORK TOGETHER across boundaries? Retrieval is a single global kNN (no src filter),
    so a query should pull from whichever segments are most relevant -- not just its own. This measures (a) how many
    DISTINCT segments each position's top-k retrieval spans, and (b) whether that cross-segment composition is load-
    bearing: bits/byte with GLOBAL retrieval (all segments) vs SILOED (restricted to the segment of the nearest hit)."""
    procs = sorted(set(labels)); wins = []
    for p in procs:
        idx = [s for s in range(0, len(stream) - (WIN + 1), WIN) if labels[s] == p]
        random.shuffle(idx); wins += idx[:EVAL_N]
    if not wins: return
    X = torch.tensor([list(stream[s:s + WIN]) for s in wins], device=DEV)
    Y = torch.tensor([list(stream[s + 1:s + WIN + 1]) for s in wins], device=DEV).reshape(-1)
    pm = F.softmax(model(X)[0], -1).reshape(-1, V)
    keys = mem_key(X)
    valid = mem.active & (~mem.is_wrong()); vi = valid.nonzero(as_tuple=True)[0]
    if vi.numel() == 0: return
    K = mem.keys[vi]; toks = mem.tok[vi]; srcs = mem.src[vi]
    kk = min(mem.topk, vi.numel())
    outs = []
    div_sum = 0.0; n = 0
    distG = torch.zeros(pm.size(0), V, device=DEV); distS = torch.zeros(pm.size(0), V, device=DEV)
    for s in range(0, keys.size(0), 4096):                # chunk to bound memory
        sim = F.normalize(keys[s:s + 4096], dim=-1) @ K.t()
        tv, ti = sim.topk(kk, -1); w = torch.softmax(tv / 0.1, -1)
        ht = toks[ti]; hs = srcs[ti]
        div_sum += (torch.tensor([len(set(r.tolist())) for r in hs], device=DEV).float()).sum().item(); n += hs.size(0)
        distG[s:s + 4096].scatter_add_(1, ht, w)
        keep = (hs == hs[:, 0:1]).float(); wS = w * keep; wS = wS / wS.sum(-1, keepdim=True).clamp(min=1e-9)
        distS[s:s + 4096].scatter_add_(1, ht, wS)
    def bpb(dist):
        hp = dist.sum(-1, keepdim=True).clamp(max=1.0); pp = (1 - 0.5 * hp) * pm + 0.5 * hp * dist
        return -(torch.log(pp.gather(-1, Y.unsqueeze(-1)).squeeze(-1).clamp_min(1e-9)).sum().item()) / math.log(2) / nbytes(Y)
    bm, bg, bs = bpb(torch.zeros_like(distG)), bpb(distG), bpb(distS)   # model ALONE (no memory) vs +memory vs siloed
    print(f"\n=== PERFORMANCE: does the memory earn its keep? (bits/byte, lower=better) ===")
    print(f"  model ALONE (weights only) {bm:.3f}  ->  model + MEMORY {bg:.3f}   (memory contributes {bm - bg:+.3f})")
    print(f"\n=== CROSS-SEGMENT COMPOSITION (do the {len(procs)}-process / many-segment store's segments work together?) ===")
    print(f"  top-{kk} retrieval spans {div_sum / max(1, n):.2f} distinct segments per position  (>1 = composing across segments)")
    print(f"  model+memory GLOBAL (all segments) {bg:.3f}  vs  SILOED (nearest segment only) {bs:.3f}")
    print(f"  >> cross-segment retrieval {'HELPS' if bs > bg + 1e-3 else 'is not load-bearing'} by {bs - bg:+.3f} bits/byte "
          f"({'segments compose' if bs > bg + 1e-3 else 'each query served by one segment -- still fine, no siloing cost'})")

def _dec(units):                                           # bytes OR token IDs -> printable one-liner
    txt = TOK.decode(units) if USE_TOK else bytes(units).decode("utf-8", "replace")
    return txt.replace("\n", "\\n").replace("\r", "")

def nbytes(y):                                             # true bits/BYTE denominator (a token spans >1 byte)
    return float(BLEN[y].sum()) if USE_TOK else y.numel()

@torch.no_grad()
def generate(model, mem, seed, n, use_mem, DEV, temp=0.7, vlim=None, fab=None, gist=None):
    """Autoregressively sample n units (bytes or tokens) after `seed`. If use_mem, interpolate with the
    memory retrieval (same gating as scoring) at every step -- so we can see, in plain text, what the memory adds.
    vlim caps sampling to valid token ids (online: model is sized to VMAX but the vocab grew to fewer)."""
    seq = list(seed)
    for _ in range(n):
        x = torch.tensor([seq[-256:]], device=DEV)
        lg = (fab_logits(model, fab, model.encode(x), gist)[0, -1] if fab is not None
              else model(x)[0][0, -1])
        if vlim is not None and vlim < lg.numel(): lg = lg.clone(); lg[vlim:] = float("-inf")   # never sample untrained ids
        pm = F.softmax(lg / temp, -1)
        if use_mem:
            dist, _, _, _ = mem.read(mem_key(x)[-1:])      # retrieval for the next position
            pmem = dist[0]; hp = pmem.sum().clamp(max=1.0)
            p = (1 - 0.5 * hp) * pm + 0.5 * hp * pmem
            p = (p / p.sum().clamp_min(1e-9))
        else:
            p = pm
        seq.append(int(torch.multinomial(p, 1)))
    return seq[len(seed):]

@torch.no_grad()
def fab_logits(model, fab, h, gist=None, nov=None, k=None):
    """THE single path from hidden state to logits. In SOCIETY mode the experts are ENSEMBLED AT THE PREDICTION
    LEVEL (sum of w_i * head(o_i)), not by averaging their hidden states -- averaging hiddens produces a
    representation no expert was ever trained to emit, which decodes badly. Blending OUTPUTS is what makes the
    population an ensemble that degrades gracefully when a member is deleted."""
    if fab is None: return model.head(h)
    if gist is None: gist = torch.zeros(h.size(0), fab.q_entry.in_features, device=h.device)
    if nov is None: nov = torch.zeros(h.size(0), device=h.device)
    if not SOCIETY: return model.head(fab(h, gist, nov)[0])
    _, w, O = fab.society(h, gist, nov)
    kk = int(min(k or ENS_K, O.size(1)))
    idx = w.mean(0).topk(kk).indices
    ww = w[:, idx]; ww = ww / ww.sum(-1, keepdim=True).clamp_min(1e-9)
    out = None
    for j in range(kk):
        lj = model.head(fab.norm(O[:, idx[j]])) * ww[:, j][:, None, None]
        out = lj if out is None else out + lj
    return out


def selfcheck(model, mem, fab=None):                       # WRONGNESS (B): is each stored token plausible under the model
    ii, ctx = mem.active_ctx()                             # given the entry's OWN context? single pass, every entry judged
    if ctx is None or ii.numel() == 0: return
    fr = []
    for s in range(0, ii.numel(), 8192):
        c = ctx[s:s + 8192]; idx = ii[s:s + 8192]
        logits = (fab_logits(model, fab, model.encode(c))[:, -1] if fab is not None
                  else model(c)[0][:, -1])                 # same path the model trained with
        tl = logits.gather(-1, mem.tok[idx].unsqueeze(-1))
        fr.append((logits > tl).float().sum(-1) / logits.size(-1))   # fraction of vocab ranked above the stored token
    mem.set_selfcon(ii, torch.cat(fr))

def main():
    global model, BLEN
    print(f"self-organize | d{D} | {NP} hidden processes | stream {STREAM_LEN} | win {WIN} | SIG_MODE={SIG_MODE} | data {DATA_MODE}\n")
    stream, labels, true_sw = build_stream()
    ONLINE = USE_TOK and TOK_ONLINE
    if ONLINE:                                             # corpora are BYTES here; derive a token stream with the live vocab
        byte_stream, byte_labels = stream, labels
        def _retok():
            ids = TOK.segment(bytes(byte_stream), count=False); bs, off = [], 0
            for t in ids: bs.append(off); off += TOK.blen(t)
            return ids, bs, [byte_labels[min(o, len(byte_labels) - 1)] for o in bs]
        stream, tok_bs, labels = _retok()
    ENC_SEQ = byte_stream if ONLINE else stream       # signature encoder reads THIS: bytes when online (invariant to re-tokenization)
    route_at = torch.full(((len(ENC_SEQ) if ONLINE else len(stream)) + WIN + 2,), -1, dtype=torch.int16) if EXPERTS else None
    model = build_lm().to(DEV); enc = SigEncoder(D, SIG_D).to(DEV)
    recon = Reconstructor(D, V, _i("RECON_TOK", 32), _i("RECON_HID", 64)).to(DEV) if VERIFY == "recon" else None
    fab = Fabric(D, SIG_D, _i("FAB_DK", 32), _i("FAB_N0", 3), _f("FAB_ALPHA", 0.5), _i("FAB_STEPS", 4),
                 _i("FAB_HID_MULT", 2), _i("FAB_MIN_STEPS", 0), bool(_i("FAB_NORM_ONLY", 0))).to(DEV) if FABRIC else None
    fabgrow = PlateauGrowth(_f("FAB_PLATEAU", 0.002), _i("FAB_COOLDOWN", 1500), _i("FAB_WARMUP", 2000)) if FABRIC else None
    FAB_NMAX = _i("FAB_NMAX", 8); PONDER = _f("PONDER", 0.01); _fab_nov = 0.5
    PONDER_WARM = _i("PONDER_WARM", 8000); FAB_BAL = _f("FAB_BALANCE", 0.01)
    BATCH_W = max(1, _i("BATCH_W", 1))                        # LM steps over BATCH_W windows AT ONCE. Domain assembly
    _bx = []; _by = []; _bg = []; _bd = []; _bp = []          #   and memory stay per-window (sequential, cheap), so
                                                              #   stream semantics are preserved -- this only removes
                                                              #   the batch-1 throughput ceiling that made a large
                                                              #   model impractical to train.
    ACCUM = max(1, _i("ACCUM", 1))                            # accumulate grads over K windows: batch-1 online training
    _lm_run = []; _lm_curve = []                              #   has very noisy gradients; this fixes that WITHOUT
                                                              #   breaking the stream. Also track the LM loss curve --
                                                              #   we had no way to see whether the LM had converged.
    IND_W = _f("IND_W", 0.5); IND_K = _i("IND_K", 2)          # independence-loss weight / how many experts get it
    BAL_WARM = _i("BAL_WARM", 4000)                           # load-balance pressure DECAYS to 0 over this many steps:
    DIV_W = _f("DIV_W", 0.0)                                  #   it exists to stop early collapse, but equal load and
    ROUTE_T = _f("ROUTE_T", 1.0)                              #   specialization are directly opposed. DIV_W rewards
                                                              #   experts for DISAGREEING (distinct competence).
    def fab_bal(w): return w.size(1) * (w.mean(0) ** 2).sum()
    experts = ExpertBank(_i("MAX_EXPERTS", 256), D, _i("EXPERT_R", 4)).to(DEV) if EXPERTS else None
    router = ExpertRouter(experts, _f("EXPERT_NEW_DIST", 0.5), _i("EXPERT_CULL_STALE", 1000), _f("EXPERT_REP_MULT", 2.5),
                          _f("EXPERT_CULL_FRAC", 0.25), _i("EXPERT_GRACE", 3000), os.environ.get("CULL_MODE", "rank"),
                          _f("EXPERT_CULL_RANK", 0.08), _f("EXPERT_PRESSURE", 0.75), _f("EXPERT_MERGE_DIST", 0.10),
                          _i("EXPERT_FIT_WIN", 4000)) if EXPERTS else None
    if _i("PROBE", 1):                                     # measure actual step cost + extrapolate BEFORE the long run
        import time as _t
        xb = torch.randint(0, V, (1, WIN), device=DEV)
        def _one():                                        # time the REAL step incl. the fabric (or the estimate lies)
            h = model.encode(xb)
            if FABRIC:
                _g0 = torch.zeros(1, SIG_D, device=DEV); _n0 = torch.zeros(1, device=DEV)
                h = fab.society(h, _g0, _n0)[0] if SOCIETY else fab(h, _g0, _n0)[0]
            model.head(h).sum().backward(); model.zero_grad()
            if FABRIC: fab.zero_grad()
        for _ in range(3): _one()
        if DEV == "cuda": torch.cuda.synchronize()
        t0 = _t.time()
        for _ in range(15): _one()
        if DEV == "cuda": torch.cuda.synchronize()
        per = (_t.time() - t0) / 15; steps = STREAM_LEN // WIN
        print(f"[probe] {MODEL_TYPE} d{D} L{_i('LAYERS', 4 if MODEL_TYPE=='transformer' else 1)}{f' + FABRIC {len(fab.bodies)}n' if FABRIC else ''} | ~{per*1000:.1f} ms/step x {steps} steps "
              f"= ~{per*steps/60:.1f} min train (+ tokenizer build, {_i('ENC_WARMUP',800)} warmup steps, re-keys, tests). "
              f"{'Ctrl-C in 12s to abort/resize.' if DEV=='cuda' else ''}")
        if DEV == "cuda": _t.sleep(12)
    # WEIGHT DECAY was implicit (AdamW defaults to 0.01). Decoupled decay is applied EVERY step to EVERY parameter
    # regardless of gradient, so a dormant expert loses ~71% of its magnitude over a 62.5k-step run -- an UNCONTROLLED
    # forgetting term inside a system whose whole point is CONTROLLED forgetting. Now explicit; 0 disables it.
    WD = WEIGHT_DECAY                                     # default 0.0: we are UNDERFIT, regularization would hurt
    om = torch.optim.AdamW(list(model.parameters()) + (list(experts.parameters()) if EXPERTS else [])
                           + (list(fab.parameters()) if FABRIC else [])
                           + (list(recon.parameters()) if recon is not None else []), lr=2e-3, weight_decay=WD)
    oe = torch.optim.AdamW(enc.parameters(), lr=2e-3, weight_decay=WD)
    mem = EditableMemory(_i("MEM_CAP", 200000), D, DEV, V, _f("WRITE_GATE", 0.3), _f("WRONG_THRESH", 1.0), _i("TOPK", 8),
                         ctx_w=(KW if KEY_SRC == "model" else 0), wrong_margin=_f("WRONG_MARGIN", 1.5), wrong_min_n=_i("WRONG_MIN_N", 3),
                         adaptive_gate=bool(_i("WRITE_ADAPTIVE", 0)), gate_target=_f("WRITE_TARGET", 0.5),
                         evict=os.environ.get("EVICT", "recency"), use_decay=_f("USE_DECAY", 0.98), decay_every=_i("DECAY_EVERY", 20000))
    asm = DomainAssembler()
    if SIG_MODE == "learned":                              # WARM UP the encoder first (unsupervised on the raw stream);
        wu = _i("ENC_WARMUP", 800)                         #   an undertrained encoder gives noisy (unseparated) signatures.
        def _sep_probe():                                  # mean pairwise distance of random-window encodings (global spread)
            with torch.no_grad():
                st = [random.randint(0, len(ENC_SEQ) - WIN - 1) for _ in range(64)]
                Z = enc(torch.tensor([list(ENC_SEQ[s:s + WIN]) for s in st], device=DEV))
                return float((1 - Z @ Z.t()).mean())
        curve = []
        for t in range(wu):
            l = contrastive_step(enc, oe, ENC_SEQ, len(ENC_SEQ))
            if t % max(1, wu // 6) == 0 and l is not None: curve.append((t, l, _sep_probe()))
        if wu:
            print("[encoder training curve] step:loss:separation -> " + "  ".join(f"{t}:{l:.2f}:{s:.2f}" for t, l, s in curve))
            print(f"  (loss still dropping / separation still rising at the end = MORE warmup would help; flat = converged)")
    assigns = []; bounds = []; i = 0; step = 0; _cur_ph = -1; PH_SNAP = []
    dom_exp = {}                                           # domain -> routing mass per expert (the AFFILIATION map)
    GROW_EVERY = _i("GROW_EVERY", 200); RETOK_EVERY = _i("RETOK_EVERY", 3000)
    import bisect as _bisect
    while i + WIN + 1 < len(stream):
        w = stream[i:i + WIN + 1]
        x = torch.tensor([list(w[:-1])], device=DEV); y = torch.tensor([list(w[1:])], device=DEV)
        bpos = tok_bs[i] if ONLINE else i                  # stable (byte) coordinate so metrics survive re-tokenization
        if PHASED:                                         # snapshot the system state at each distribution shift
            _p = sum(1 for b in PH_BOUNDS if bpos >= b) - 1
            if _p != _cur_ph and _p >= 0:
                _cur_ph = _p
                _snap = (_p, len(asm.cent), (TOK.vocab_size if USE_TOK else 256), (len(fab.bodies) if FABRIC else 0), mem.n)
                PH_SNAP.append(_snap)
                print(f"  [PHASE {_p}] active processes {PHASE_SCHED[_p]} | domains {_snap[1]} | vocab {_snap[2]}"
                      f" | fabric nodes {_snap[3]} | memory {_snap[4]}")
        ew = list(byte_stream[bpos:bpos + WIN]) if ONLINE else list(w[:-1])   # SIGNATURE window: BYTES when online (tokenization-invariant)
        if SIG_MODE == "learned" and step % ENC_EVERY == 0: contrastive_step(enc, oe, ENC_SEQ, bpos)   # LIVE encoder on the STABLE sequence
        sig = sig_of(ew, enc)
        did, boundary = asm.update(sig, ew, step)
        if boundary: bounds.append(bpos)
        if step % REKEY_EVERY == 0 and step > 0:
            if SIG_MODE == "learned": asm.rekey(enc)                                                    # RE-KEY centroids
            rekey_memory(mem)                                                                            # RE-KEY memory store
        if MANAGE_ON and step % MANAGE_EVERY == 0 and step > 0:                                     # MANAGE the domain set
            m, c = asm.manage(step, mem, MANAGE_MERGE, MANAGE_MIN, MANAGE_STALE)                     #   merge redundant + cull
            if m or c: print(f"  [manage @ {step}] merged {m} culled {c} -> {len(asm.cent)} live domains (memory reassigned/pruned)")
        if EXPERTS and MANAGE_ON and step % MANAGE_EVERY == 0 and step > 0: router.manage(step)   # experts: create/replicate/cull (their own selective force)
        _bx.append(list(w[:-1])); _by.append(list(w[1:])); _bg.append(sig); _bd.append(did); _bp.append(bpos)
        if len(_bx) < BATCH_W:                              # accumulate a batch of windows first
            i += WIN; step += 1; continue
        model.train()
        x = torch.tensor(_bx, device=DEV); y = torch.tensor(_by, device=DEV)   # (BATCH_W, WIN)
        sigb = torch.stack(_bg)
        _sl = router.route(sig, step) if EXPERTS else -1        # route by SIGNATURE to the expert population (coarser than domains)
        if EXPERTS and _sl >= 0: route_at[bpos:bpos + WIN] = _sl   # remember WHICH expert trained on this span
        h = model.encode(x)
        if FABRIC and SOCIETY:
            _hs, _w, _O = fab.society(h, sigb, torch.full((x.size(0),), _fab_nov, device=DEV))
            _dep = _hs.new_zeros(()); _bal = fab_bal(_w); h = _hs
            _wd = _w[0].detach().cpu()                     # which experts serve THIS domain, and how much
            if did in dom_exp and dom_exp[did].numel() == _wd.numel(): dom_exp[did] += _wd
            else: dom_exp[did] = _wd.clone()
        elif FABRIC:
            h, _dep, _mass, _bal = fab(h, sigb, torch.full((x.size(0),), _fab_nov, device=DEV))
        elif _sl >= 0:
            h = experts.one(h, _sl)
        if FABRIC and SOCIETY:                             # ENSEMBLE the experts' OUTPUTS (not their hidden states)
            _ki = _w.mean(0).topk(min(ENS_K, _O.size(1))).indices
            _wk = _w[:, _ki].mean(0); _wk = _wk / _wk.sum().clamp_min(1e-9)
            lg = None
            for _q, _j in enumerate(_ki):
                _lj = model.head(fab.norm(_O[:, _j])) * _wk[_q]
                lg = _lj if lg is None else lg + _lj
        else:
            lg = model.head(h)
        loss = F.cross_entropy(lg.reshape(-1, V), y.reshape(-1))
        _bw = max(0.0, 1.0 - step / max(1, BAL_WARM))            # DECAY balance: uniform early (no collapse), free later
        _pw = min(1.0, step / max(1, PONDER_WARM))               # ANNEAL ponder: don't charge for depth before the
        tot = loss + ((PONDER * _pw) * _dep + FAB_BAL * _bw * _bal if FABRIC else 0.0)  # nodes have had a chance to be useful
        if FABRIC and SOCIETY and DIV_W > 0 and _O.size(1) > 1:   # DISTINCTNESS: reward experts for DISAGREEING, so
            _t2 = _w.mean(0).topk(min(2, _O.size(1))).indices          #   they carry different competence instead of
            _a = _O[:, _t2[0]].reshape(-1); _b = _O[:, _t2[1]].reshape(-1)   #   converging on the same generalist function
            tot = tot + DIV_W * F.cosine_similarity(_a, _b, dim=0).clamp_min(0.0)
        if FABRIC and SOCIETY and IND_W > 0:                # INDEPENDENCE: each expert must solve the task ALONE
            _ki = _w.mean(0).topk(min(IND_K, _O.size(1))).indices  #   (weighted by its routing mass) -- makes the population
            for _j in _ki:                                    #   an ENSEMBLE, which survives member removal, rather than
                _lj = model.head(fab.norm(_O[:, _j]))         #   a DECOMPOSITION, which does not
                tot = tot + IND_W * float(_w[:, _j].mean()) * F.cross_entropy(_lj.reshape(-1, V), y.reshape(-1))
        if recon is not None:                                    # VERIFICATION: train the Reconstructor on GENUINE
            tot = tot + RECON_W * recon_loss(recon, mem_key(x), y.reshape(-1))   # (key, token) pairs from the live stream
        (tot / ACCUM).backward()                                 # gradient accumulation over ACCUM windows
        if (step + 1) % ACCUM == 0: om.step(); om.zero_grad()
        _lm_run.append(float(loss.detach()))                     # LM loss curve: is the model still improving?
        if step % max(1, (STREAM_LEN // WIN) // 8) == 0 and _lm_run:
            _lm_curve.append((step, sum(_lm_run[-2000:]) / len(_lm_run[-2000:]))); _lm_run = _lm_run[-2000:]
        if FABRIC and not fab.norm_only and fabgrow.step(float(loss.detach()), step) and len(fab.bodies) < FAB_NMAX:
            om.add_param_group({"params": fab.grow(sig[None, :] if SOCIETY else None)})   # PLATEAU -> new expert, keyed HERE
            print(f"  [fabric @ {step}] progress plateaued -> grew node {len(fab.bodies)}")
        with torch.no_grad():
            pm = F.softmax(lg.detach(), -1)                    # reuse the expert-routed logits for the write-gate surprise
            surprise = 1 - pm.gather(-1, y.unsqueeze(-1)).squeeze(-1)
            if FABRIC: _fab_nov = float(surprise.mean())        # last step's surprise biases the next routing query
            _K = mem_key(x); _C = mem_ctx(x); _n1 = x.size(1)
            for _b in range(x.size(0)):                     # per-window: each carries its OWN domain + source position
                mem.write(_K[_b * _n1:(_b + 1) * _n1], y[_b], src=_bd[_b], surprise=surprise[_b],
                          ctx=(None if _C is None else _C[_b * _n1:(_b + 1) * _n1]),
                          pos=torch.arange(_bp[_b], _bp[_b] + _n1, device=DEV))
        assigns.append((bpos, did, byte_labels[min(bpos, len(byte_labels) - 1)] if ONLINE else labels[i]))
        if ONLINE:                                         # ONGOING minting: tally this window's token pairs, mint, re-tokenize
            for a, b in zip(w[:-1], w[1:]): TOK.pair[(a, b)] += 1
            if step % GROW_EVERY == 0 and step > 0:
                for _ in range(_i("GROW_BURST", 6)):       # mint several of the current top pairs per grow event
                    g = TOK.maybe_grow()
                    if g is None: break
                    if _i("WARMSTART", 1):                 # init the new token "ab" from (emb[a]+emb[b])/2 instead of random
                        nid, a, b = g                      #   -> the LM doesn't relearn it from scratch (cuts moving-target cost)
                        with torch.no_grad():
                            model.emb.weight[nid] = 0.5 * (model.emb.weight[a] + model.emb.weight[b])
                            model.head.weight[nid] = 0.5 * (model.head.weight[a] + model.head.weight[b])
                            if model.head.bias is not None:
                                model.head.bias[nid] = 0.5 * (model.head.bias[a] + model.head.bias[b])
        _bx = []; _by = []; _bg = []; _bd = []; _bp = []
        i += WIN; step += 1
        if ONLINE and step % RETOK_EVERY == 0:             # refresh the token stream with the grown vocab; remap position by byte
            cur_byte = tok_bs[i] if i < len(tok_bs) else len(byte_stream)
            stream, tok_bs, labels = _retok(); i = _bisect.bisect_left(tok_bs, cur_byte)

    if ONLINE:                                             # freeze + final tokenization for eval + persist the grown vocab
        stream, tok_bs, labels = _retok()
        BLEN = torch.tensor(TOK.bytes_per_id, dtype=torch.float, device=DEV)
        TOK.save(os.environ.get("TOKENIZER_PATH", "data/dyntok.json"))
        print(f"[tokenizer] ONLINE: minted throughout -> grew 256 -> {TOK.vocab_size} during training; final re-tokenization for eval")

    if os.environ.get("SAVE_CKPT"):                                  # save trained model + tokenizer + memory so it can be prompted
        ck = os.environ["SAVE_CKPT"]; os.makedirs(ck, exist_ok=True)
        act = mem.active
        torch.save({"model": model.state_dict(), "D": D, "V": V, "KW": KW, "KEY_SRC": KEY_SRC,
                    "model_type": MODEL_TYPE, "layers": _i("LAYERS", 4 if MODEL_TYPE=="transformer" else 1), "heads": _i("HEADS", 8), "maxlen": _i("MAXLEN", 512),
                    "use_tok": USE_TOK, "tok_path": (os.environ.get("TOKENIZER_PATH", "data/dyntok.json") if USE_TOK else None),
                    "mem_keys": mem.keys[act].cpu(), "mem_tok": mem.tok[act].cpu(), "mem_src": mem.src[act].cpu(),
                    "mem_ctx": (mem.ctx[act].cpu() if mem.ctx_w > 0 else None), "topk": mem.topk,
                    "mem_pos": mem.pos[act].cpu(),                     # -> source passages for grounded answers
                    "sig_d": SIG_D, "win": WIN, "enc": enc.state_dict(),          # encoder -> gist for fabric routing
                    "fab": (fab.state_dict() if FABRIC else None),
                    "fab_cfg": ({"n": len(fab.bodies), "dk": _i("FAB_DK", 32), "alpha": _f("FAB_ALPHA", 0.5),
                                 "max_steps": _i("FAB_STEPS", 4), "hid_mult": _i("FAB_HID_MULT", 2),
                                 "min_steps": _i("FAB_MIN_STEPS", 0), "norm_only": bool(_i("FAB_NORM_ONLY", 0)),
                                 "society": SOCIETY} if FABRIC else None)},
                   f"{ck}/ckpt.pt")
        with open(f"{ck}/source.bin", "wb") as _srcf:             # the corpus text retrieval points INTO
            _srcf.write(bytes(byte_stream) if ONLINE else (bytes(stream) if not USE_TOK else TOK.decode(stream).encode("utf-8", "replace")))
        print(f"[saved checkpoint -> {ck}/ckpt.pt | {int(act.sum())} memory entries{', fabric ' + str(len(fab.bodies)) + 'n' if FABRIC else ''} | prompt it: python3 prompt.py CKPT={ck}]")

    assigns = [(i, asm.resolve(d), t) for i, d, t in assigns]        # follow merges -> the surviving domain
    try:                                                   # === MEMORIZATION CHECK: train vs HELD-OUT ===
        model.eval()
        _vb = []
        for _p in range(len(VALC)):
            _v = TOK.segment(VALC[_p], count=False) if USE_TOK else list(VALC[_p])
            if len(_v) < WIN + 2: continue
            _st = [random.randint(0, len(_v) - WIN - 2) for _ in range(min(24, _i("EVAL_N", 64)))]
            with torch.no_grad():
                _X = torch.tensor([_v[a:a + WIN] for a in _st], device=DEV)
                _Y = torch.tensor([_v[a + 1:a + WIN + 1] for a in _st], device=DEV)
                _lg = fab_logits(model, fab if FABRIC else None, model.encode(_X))
                _pp = F.softmax(_lg, -1).gather(-1, _Y.unsqueeze(-1)).squeeze(-1)
                _vb.append(-(torch.log(_pp.clamp_min(1e-9)).sum().item()) / math.log(2) / nbytes(_Y))
        _tb = []
        for _p in range(len(CORP)):                        # same measurement on TRAIN data, for a like-for-like gap
            _t = TOK.segment(CORP[_p][-len(VALC[_p]) or -1:], count=False) if USE_TOK else list(CORP[_p][-len(VALC[_p]):])
            if len(_t) < WIN + 2: continue
            _st = [random.randint(0, len(_t) - WIN - 2) for _ in range(min(24, _i("EVAL_N", 64)))]
            with torch.no_grad():
                _X = torch.tensor([_t[a:a + WIN] for a in _st], device=DEV)
                _Y = torch.tensor([_t[a + 1:a + WIN + 1] for a in _st], device=DEV)
                _lg = fab_logits(model, fab if FABRIC else None, model.encode(_X))
                _pp = F.softmax(_lg, -1).gather(-1, _Y.unsqueeze(-1)).squeeze(-1)
                _tb.append(-(torch.log(_pp.clamp_min(1e-9)).sum().item()) / math.log(2) / nbytes(_Y))
        if _vb and _tb:
            _tr = sum(_tb) / len(_tb); _va = sum(_vb) / len(_vb); _gap = _va - _tr
            print(f"\n=== MEMORIZATION CHECK: train vs HELD-OUT ({VAL_FRAC:.0%} of each corpus, never trained on) ===")
            print(f"  train {_tr:.3f} | held-out {_va:.3f} | gap {_gap:+.3f} bits/byte")
            print(f"  >> gap < ~0.3 = UNDERFIT, keep training / add data (regularization would HURT)")
            print(f"     gap > ~0.5 = MEMORIZING, now turn on DROPOUT=0.1-0.2 and WEIGHT_DECAY=0.01")
            print(f"  currently: {'MEMORIZING -> enable DROPOUT/WEIGHT_DECAY' if _gap > 0.5 else 'UNDERFIT -> more data/passes, not regularization'}")
        model.train()
    except Exception as _e:
        print(f"[memorization check skipped: {type(_e).__name__}: {_e}]")
    if _lm_curve:
        print("[LM training curve] step:loss -> " + "  ".join(f"{a}:{b:.2f}" for a, b in _lm_curve))
        _d8 = (_lm_curve[-2][1] - _lm_curve[-1][1]) if len(_lm_curve) > 1 else 0.0
        print(f"  (last segment change {_d8:+.3f}: still FALLING = more passes/steps will help;"
              f" flat = the model has converged and needs more CAPACITY or more DATA, not more steps)")
    n_self = len(asm.cent); print(f"SELF-ASSEMBLED {n_self} LIVE domains after {'management' if MANAGE_ON else 'NO MANAGEMENT (ablation)'} (truth had {NP} processes)")
    if FABRIC: print(f"FABRIC{' [NORM-ONLY CONTROL: no nodes, no routing]' if fab.norm_only else ''}: {len(fab.bodies)} nodes ({fab.grown} grown on plateau from {_i('FAB_N0',3)}) | depth budget {max(1, min(fab.max_steps, 2 + len(fab.bodies)//2))} steps | soft routing + transition matrix + HALT")
    if EXPERTS: print(f"EXPERTS (separate population, dual selection): {router.created} created, {router.replicated} replicated, {router.merged} merged, {router.removed} removed -> {len(router.cent)} live | rank {_i('EXPERT_R',4)} | churn {router.removed/max(1,router.created):.0%} (merge preserves learning; high churn destroys it)")
    tol = WIN * 3 if (USE_TOK and TOK_ONLINE) else WIN * 2   # byte-coord positions when online
    hits = sum(1 for b in bounds if any(abs(b - s) <= tol for s in true_sw))
    prec = hits / max(1, len(bounds)); rec = sum(1 for s in true_sw if any(abs(b - s) <= tol for b in bounds)) / max(1, len(true_sw))
    print(f"boundary detection: {len(bounds)} found for {len(true_sw)} true switches | precision {prec:.2f} recall {rec:.2f}")
    from collections import Counter, defaultdict
    by = defaultdict(Counter)
    for _, d, t in assigns: by[d][t] += 1
    purity = sum(c.most_common(1)[0][1] for c in by.values()) / max(1, len(assigns))
    s2t = {d: c.most_common(1)[0][0] for d, c in by.items()}
    smap = [(d, s2t[d]) for d in sorted(by)]
    print(f"clustering purity: {purity:.2f}   (1.0 = perfectly recovered)   [{len(smap)} self-domains; first 20 self->true] {smap[:20]}")
    biggest = max(by, key=lambda d: sum(by[d].values())); tgt = s2t[biggest]

    # ---- GENUINENESS on the FINAL MANAGED set (merge/cull already applied live) ----
    # A domain is GENUINE only if it is a real, separated cluster -- not just large. We use a silhouette-style score:
    #   sil = (mean similarity of members to their OWN centroid) - (similarity to the NEAREST OTHER centroid) = coh+sep-1.
    # sil>0 means members are genuinely closer to their own domain than to any neighbor; sil<=0 means the domain overlaps
    # a neighbor and is really an arbitrary slice of a continuum. (The old test used coh>=0.5 & sep>=0.10, which never
    # bound -- so it silently reduced to a size threshold. This makes cohesion AND separation actually count.)
    sizes = {d: sum(by[d].values()) for d in by}
    MIN_SIZE = _i("GENUINE_MIN", 20); SIL_MIN = _f("GENUINE_SIL", 0.10)
    live = [d for d in by if d in asm.cent]               # domains that survived management (still have a centroid)
    print(f"\n=== domain genuineness ({len(live)} live domains: size | cohesion | separation | silhouette=coh+sep-1) ===")
    genuine = 0; cohs = []; seps = []; sils = []
    with torch.no_grad():
        for d in sorted(live, key=lambda k: -sizes[k]):
            if not asm.wins[d]: continue
            W = torch.tensor([w for w in asm.wins[d]], device=DEV)
            sg = enc(W) if SIG_MODE == "learned" else torch.stack([sig_of(list(w), enc) for w in asm.wins[d]])
            coh = F.cosine_similarity(sg, asm.cent[d].unsqueeze(0)).mean().item()
            sep = min([1 - F.cosine_similarity(asm.cent[d].unsqueeze(0), asm.cent[o].unsqueeze(0)).item()
                       for o in asm.cent if o != d] or [1.0])
            sil = coh + sep - 1.0                          # silhouette-style cluster-validity score
            g = sizes[d] >= MIN_SIZE and sil >= SIL_MIN
            genuine += g; cohs.append(coh); seps.append(sep); sils.append(sil)
            if sizes[d] >= 5:
                print(f"  domain {d:4d}: size {sizes[d]:5d} | cohesion {coh:.2f} | separation {sep:.2f} | sil {sil:+.2f} | {'GENUINE' if g else 'weak'}")
    print(f"  >> {genuine}/{len(live)} live domains GENUINE (size>={MIN_SIZE} AND silhouette>={SIL_MIN}) | "
          f"mean cohesion {sum(cohs)/max(1,len(cohs)):.2f} sep {sum(seps)/max(1,len(seps)):.2f} sil {sum(sils)/max(1,len(sils)):+.2f}")
    print(f"  ({len(by)-len(live)} domains merged/culled by management; {sum(1 for d in live if sizes[d] < MIN_SIZE)} live tiny)")

    # ---- fixed eval windows per process: SAME windows before and after the delete (the old version redrew random
    #      windows each call, so before/after weren't comparable -- the 'leak' could have been sampling noise) ----
    EVAL_N = _i("EVAL_N", 64)
    eval_win = {}
    for p in set(labels):
        idx = [s for s in range(0, len(stream) - (WIN + 1), WIN) if labels[s] == p]
        random.shuffle(idx); eval_win[p] = idx[:EVAL_N]
    def bpb_true(p, use_exp=EXPERTS, use_mem=True, pin=True, use_fab=FABRIC):
        ii = eval_win.get(p, [])
        if not ii: return 0.0
        with torch.no_grad():
            X = torch.tensor([list(stream[s:s + WIN]) for s in ii], device=DEV)
            Y = torch.tensor([list(stream[s + 1:s + WIN + 1]) for s in ii], device=DEV)
            h = model.encode(X)
            if use_fab and FABRIC:
                bps = [(tok_bs[s] if ONLINE else s) for s in ii]
                EW = torch.tensor([list(ENC_SEQ[b:b + WIN]) for b in bps], device=DEV)
                pm = F.softmax(fab_logits(model, fab, h, enc(EW)), -1); h = None
            elif use_exp and EXPERTS:
                bps = [(tok_bs[s] if ONLINE else s) for s in ii]
                if pin:                                    # PINNED: the expert this span actually trained with
                    sl = torch.tensor([int(route_at[min(b, route_at.numel() - 1)]) for b in bps], device=DEV)
                else:                                      # ROUTED: nearest centroid at eval time (what inference does)
                    EW = torch.tensor([list(ENC_SEQ[b:b + WIN]) for b in bps], device=DEV)
                    sg = enc(EW); sl = torch.tensor([router.route(sg[k], 0, create=False) for k in range(sg.size(0))], device=DEV)
                mk = (sl >= 0) & (sl < experts.A.size(0))
                if mk.any(): h = h.clone(); h[mk] = experts.batch(h[mk], sl[mk])
            if h is not None: pm = F.softmax(model.head(h), -1)
            if use_mem:
                dist, _, _, _ = mem.read(mem_key(X))
                pmem = dist.reshape(X.size(0), X.size(1), V); hp = pmem.sum(-1, keepdim=True).clamp(max=1.0)
                pp = (1 - 0.5 * hp) * pm + 0.5 * hp * pmem
            else:
                pp = pm
            return -(torch.log(pp.gather(-1, Y.unsqueeze(-1)).squeeze(-1).clamp_min(1e-9)).sum().item()) / math.log(2) / nbytes(Y)
    # ---- WRONGNESS (B) IN THE LOOP: detect + remove implausible associations via self-consistency ----
    if _i("WRONG_CHECK", 1):
        ninj = _i("WRONG_INJECT", 8)                       # inject a few cross-domain WRONG windows so B has real errors to catch
        if ninj > 0:
            procs = sorted(set(labels)); rx = []; ry = []
            for _ in range(ninj):
                p = random.choice(procs); qd = random.choice([z for z in procs if z != p])
                sp = random.choice([s for s in range(0, len(stream) - (WIN + 1), WIN) if labels[s] == p])
                sq = random.choice([s for s in range(0, len(stream) - (WIN + 1), WIN) if labels[s] == qd])
                rx.append(list(stream[sp:sp + WIN])); ry.append(list(stream[sq + 1:sq + WIN + 1]))
            XW = torch.tensor(rx, device=DEV); YW = torch.tensor(ry, device=DEV)
            mem.write(mem_key(XW), YW.reshape(-1), src=99, surprise=None, ctx=mem_ctx(XW))   # bypass gate: force-write the synthetic wrong entries
        selfcheck(model, mem, fab if FABRIC else None)
        if VERIFY == "recon" and recon is not None:              # VERIFICATION (reconstruction): the A/B against old B
            verify_mem(mem, recon)
            _uv = mem.is_unverified(); _inj = (mem.src == 99) & mem.active
            _tp = int((_uv & _inj).sum()); _fp = int((_uv & (mem.src != 99) & mem.active).sum()); _pos = int(_inj.sum())
            _pr = _tp / max(1, _tp + _fp); _rc = _tp / max(1, _pos)
            print(f"=== VERIFICATION (reconstruction) [VERIFY=recon]: flagged {_tp} injected / {_pos} "
                  f"(precision {_pr:.1%}, recall {_rc:.1%}) -- compare to self-consistency B below ===")
        sr = mem.src; iw = mem.is_wrong(); flg = int(iw.sum())
        print(f"\n=== WRONGNESS (B) in the loop: self-consistency detect + sweep ===")
        if ninj > 0:
            fb = int((iw & (sr == 99)).sum()); tb = int((sr == 99).sum()); fg = int((iw & (sr != 99)).sum())
            print(f"  injected {tb} cross-domain WRONG entries | caught {fb} (recall {fb / max(1, tb):.0%}) | "
                  f"flagged genuine {fg} (precision {fb / max(1, flg):.0%})")
        else:
            print(f"  flagged {flg} implausible of {int(mem.active.sum())} entries")
        if _i("WRONG_SWEEP", 0):
            print(f"  swept {mem.sweep_wrong()} -> {int(mem.active.sum())} entries remain")
        else:
            print(f"  (detect-only: sweep OFF -- B's precision is too low on a surprise-gated store to delete safely; WRONG_SWEEP=1 to force)")
            if ninj > 0: mem.delete_src(99)      # remove the SYNTHETIC injected entries so downstream metrics are clean
            mem.selfcon.fill_(-1.0)              # clear flags so genuine entries aren't excluded from retrieval below

    # ---- do the segments WORK TOGETHER across boundaries? (retrieval composition) ----
    compose_test(model, mem, stream, labels, WIN, V, DEV, EVAL_N=_i("EVAL_N", 64))
    if FABRIC and SOCIETY and dom_exp:                     # === AFFILIATION: which experts serve which domains? ===
      try:                                                 # a DIAGNOSTIC must never kill a run (this one did once)
        _NE = max(v.numel() for v in dom_exp.values())     # population GREW mid-run -> vectors differ in length
        def _pad(v): return torch.cat([v, torch.zeros(_NE - v.numel())]) if v.numel() < _NE else v[:_NE]
        _aff = {}                                          # resolve merged domains, keep only live ones
        for _d, _v in dom_exp.items():
            _r = asm.resolve(_d)
            if _r not in asm.cent: continue
            _aff[_r] = _aff.get(_r, torch.zeros(_NE)) + _pad(_v)
        if _aff:
            _share = torch.zeros(_NE)                       # how many domains does each expert meaningfully serve?
            _dom_n = {}
            for _d, _v in _aff.items():
                _p = _v / _v.sum().clamp_min(1e-9)
                _serves = (_p >= _f("AFF_MIN", 0.10)).float()
                if _serves.numel() == _NE: _share += _serves; _dom_n[_d] = int(_serves.sum())
            _excl = int((_share == 1).sum()); _shared = int((_share > 1).sum()); _idle = int((_share == 0).sum())
            print(f"\n=== AFFILIATION: domains are COLLECTIONS of experts -- how shared are they? ===")
            print(f"  experts serving >1 domain: {_shared} | serving exactly 1 (exclusive): {_excl} | serving none: {_idle}")
            print(f"  domains served per expert: {[int(v) for v in _share]}")
            _big = sorted(_aff, key=lambda d: float(_aff[d].sum()), reverse=True)[:5]
            print(f"  BLAST RADIUS if a domain is deleted (experts that would be left with NO other domain):")
            for _d in _big:
                _p = _aff[_d] / _aff[_d].sum().clamp_min(1e-9)
                _mine = (_p >= _f("AFF_MIN", 0.10))
                _orphan = int(((_share == 1) & _mine).sum()); _keep = int((_mine.float().sum())) - _orphan
                print(f"    domain {_d}: uses {int(_mine.sum())} experts -> {_orphan} would be orphaned, {_keep} shared with other domains")
            print(f"  >> deleting a domain should RELEASE its experts, not kill them: an orphaned expert loses its")
            print(f"     traffic and is removed by the EXISTING cull; a shared expert keeps serving the others.")
      except Exception as _e:
        print(f"\n[affiliation report skipped: {type(_e).__name__}: {_e}]")
    if FABRIC and SOCIETY and len(fab.bodies) > 1:         # === INDEPENDENCE: what does deleting ONE expert cost? ===
        _ps2 = sorted(set(labels))
        with torch.no_grad():                              # find the busiest expert (the one worth deleting)
            _sg2 = enc(torch.tensor([list(ENC_SEQ[WIN * 3:WIN * 4])], device=DEV))
            _, _w2, _ = fab.society(model.encode(torch.tensor([list(stream[:WIN])], device=DEV)), _sg2,
                                    torch.zeros(1, device=DEV))
        _j2 = int(_w2[0].argmax())
        _pre = {p: bpb_true(p, use_mem=False) for p in _ps2}
        fab.remove(_j2)                                    # <- the expert's parameters are deleted
        _post = {p: bpb_true(p, use_mem=False) for p in _ps2}
        _d2 = sum(_post[p] - _pre[p] for p in _ps2) / max(1, len(_ps2))
        print(f"\n=== EXPERT INDEPENDENCE: delete ONE expert of {len(fab.bodies) + 1} -- what breaks? ===")
        print(f"  deleted expert {_j2} (busiest, routing mass {float(_w2[0, _j2]):.2f})")
        for p in _ps2: print(f"    process {p}: {_pre[p]:.3f}->{_post[p]:.3f} ({_post[p] - _pre[p]:+.4f})")
        print(f"  mean collateral {_d2:+.4f}  ->  {'INDEPENDENT (society survives losing a member)' if abs(_d2) < 0.3 else 'ENTANGLED (the population depended on it)'}")
        print(f"  reference points: memory-delete collateral ~0.02-0.03 | weights gradient-ascent ~22-25 bits")
    if FABRIC:                                             # does the routed node fabric help?
        _ps = sorted(set(labels))
        _b = sum(bpb_true(q, use_fab=False, use_mem=False) for q in _ps) / max(1, len(_ps))
        _f2 = sum(bpb_true(q, use_fab=True, use_mem=False) for q in _ps) / max(1, len(_ps))
        _fm = sum(bpb_true(q, use_fab=True, use_mem=True) for q in _ps) / max(1, len(_ps))
        with torch.no_grad():
            _sg = enc(torch.tensor([list(ENC_SEQ[WIN * 3:WIN * 4])], device=DEV))
            _, _d, _m, _ = fab(model.encode(torch.tensor([list(stream[:WIN])], device=DEV)), _sg, torch.zeros(1, device=DEV))
        print(f"\n=== FABRIC: does the routed node population help? (bits/byte, lower=better) ===")
        print(f"  model ALONE {_b:.3f}  ->  + FABRIC {_f2:.3f} (fabric {_b - _f2:+.3f})  ->  + FABRIC + MEMORY {_fm:.3f}")
        print(f"  nodes {len(fab.bodies)} | mean routed depth {float(_d):.2f} of {max(1, min(fab.max_steps, 2 + len(fab.bodies)//2))} steps"
              f" | node mass {[round(float(v), 2) for v in _m[:-1]]} halt {float(_m[-1]):.2f}")
        print(f"  (mass spread across nodes = SPECIALIZED; all mass on one node = collapsed; all mass on HALT = the")
        print(f"   router wrote the nodes off before they could learn -- raise FAB_MIN_STEPS / PONDER_WARM)")
        print(f"  NOTE: 'model ALONE' here is an ABLATION of a component the model TRAINED WITH (it also removes the")
        print(f"   fabric's LayerNorm), so it overstates the fabric's contribution. The honest comparison is this run's")
        print(f"   '+ FABRIC + MEMORY' against a FABRIC=0 run's 'model + MEMORY'.")
    if EXPERTS:                                            # do the per-domain experts specialize? (isolate the expert effect)
        _ps = sorted(set(labels))
        _b  = sum(bpb_true(q, use_exp=False, use_mem=False) for q in _ps) / max(1, len(_ps))
        _ep = sum(bpb_true(q, use_exp=True, use_mem=False, pin=True) for q in _ps) / max(1, len(_ps))
        _er = sum(bpb_true(q, use_exp=True, use_mem=False, pin=False) for q in _ps) / max(1, len(_ps))
        _em = sum(bpb_true(q, use_exp=True, use_mem=True, pin=True) for q in _ps) / max(1, len(_ps))
        print(f"\n=== EXPERTS: did the adapters LEARN, and does ROUTING find the right one? (bits/byte, lower=better) ===")
        print(f"  model ALONE {_b:.3f}")
        print(f"  + EXPERTS PINNED (the expert this span trained with) {_ep:.3f}   -> adapters learned: {_b - _ep:+.3f}")
        print(f"  + EXPERTS ROUTED (nearest centroid at eval = inference) {_er:.3f}   -> routing mismatch cost: {_ep - _er:+.3f}")
        print(f"  + EXPERTS(pinned) + MEMORY {_em:.3f}")
        print(f"  >> if PINNED helps but ROUTED hurts, the adapters work and ROUTING is the problem (centroid drift);")
        print(f"     if PINNED also hurts, the adapters themselves aren't learning anything useful.")

    # ---- can it actually produce COMPREHENSIBLE TEXT? model alone vs model+memory, seeded from real text ----
    if _i("GENERATE", 1):
        print("\n=== GENERATION: model ALONE vs model+MEMORY (seed = real text; does memory make it more coherent?) ===")
        for p in sorted(set(labels))[:_i("GEN_PROCS", 4)]:
            starts = [s for s in range(0, len(stream) - (WIN + 1), WIN) if labels[s] == p]
            if not starts: continue
            s0 = random.choice(starts); seed = list(stream[s0:s0 + WIN])
            _vl = TOK.vocab_size if USE_TOK else None
            _gg = None
            if FABRIC:                                     # generation must run the SAME path the model trained with
                with torch.no_grad():
                    _b0 = tok_bs[s0] if ONLINE else s0
                    _gg = enc(torch.tensor([list(ENC_SEQ[_b0:_b0 + WIN])], device=DEV))
            gno = generate(model, mem, seed, _i("GEN_LEN", 200), False, DEV, temp=_f("GEN_TEMP", 0.7), vlim=_vl, fab=fab, gist=_gg)
            gme = generate(model, mem, seed, _i("GEN_LEN", 200), True, DEV, temp=_f("GEN_TEMP", 0.7), vlim=_vl, fab=fab, gist=_gg)
            print(f"\n-- process {p} | seed ...{_dec(seed[-44:])}")
            print(f"   MODEL ONLY: {_dec(gno)}")
            print(f"   MODEL+MEM : {_dec(gme)}")

    # UNLEARN a whole true process: delete EVERY self-domain that is really about it. This is what real unlearning
    # looks like ("forget everything about X"), AND it's a big enough delete to expose cross-domain retrieval leakage
    # -- deleting one fine domain (2.7% of the store at scale) is too small to reveal whether the key is domain-aware.
    if PHASED:
        act_set = sorted(set(PHASE_SCHED[-1])); faded = [p for p in sorted(set(labels)) if p not in act_set]
        print(f"\n=== NON-STATIONARY: did the system adapt as processes entered and faded? ===")
        print(f"  phase | active processes | domains | vocab | fabric nodes | memory")
        for (ph, nd, vv, nf, mn) in PH_SNAP:
            print(f"    {ph}   | {str(PHASE_SCHED[ph]):16} | {nd:7} | {vv:5} | {nf:12} | {mn}")
        print(f"  (domains/vocab/nodes should GROW when a new process enters; memory should stay BOUNDED by MEM_CAP)")
        _ab = sum(bpb_true(p) for p in act_set) / max(1, len(act_set))
        _fb = sum(bpb_true(p) for p in faded) / max(1, len(faded)) if faded else float("nan")
        print(f"  bits/byte on ACTIVE {act_set}: {_ab:.3f} | on FADED {faded}: {_fb:.3f}")
        print(f"  (FADED worse = the system moved on; FADED still good = memory retained it despite the shift)")
        _cnt = Counter()                                    # how much memory does each process still HAVE?
        for _d, _c in Counter(mem.src[mem.active].tolist()).items():
            if _d in s2t: _cnt[s2t[_d]] += _c
        print(f"  memory entries surviving per process: " +
              " ".join(f"p{p}={_cnt.get(p, 0)}" for p in sorted(set(labels))) + f"  (cap {mem.cap})")
        print(f"  >> a FADED process with ~0 entries has been EVICTED by the bounded store -- knowledge of it is gone,")
        print(f"     and 'unlearning' it is then a no-op. Eviction is memory management working; whether faded")
        print(f"     knowledge SHOULD be protected is a design decision, not a bug.")
        def _edit_test(_p, tag):                            # editing test that is only meaningful if entries remain
            _dd = [d for d in by if s2t[d] == _p]; _oth = [q for q in sorted(set(labels)) if q != _p]
            _n0 = _cnt.get(_p, 0)
            if _n0 < 50:
                print(f"  UNLEARN {tag} process {_p}: SKIPPED -- only {_n0} entries left (evicted); test would be vacuous")
                return
            _b4t = bpb_true(_p); _b4o = {q: bpb_true(q) for q in _oth}
            _rm = sum(mem.delete_src(d) for d in _dd)
            _at = bpb_true(_p); _ao = {q: bpb_true(q) for q in _oth}
            _dl = sum(_ao[q] - _b4o[q] for q in _oth) / max(1, len(_oth))
            print(f"  UNLEARN {tag} process {_p}: {len(_dd)} domains / {_rm} entries | target {_b4t:.3f}->{_at:.3f}"
                  f" (Δ {_at - _b4t:+.4f}) | others Δ {_dl:.4f} = {'LOCAL' if abs(_dl) < 0.1 else 'LEAKED'}")
        _at_p = max(act_set, key=lambda p: _cnt.get(p, 0))   # ACTIVE process with the most memory = the meaningful test
        _edit_test(_at_p, "an ACTIVE")
        if faded: _edit_test(max(faded, key=lambda p: _cnt.get(p, 0)), "a FADED")
    tgt = Counter([s2t[d] for d in by]).most_common(1)[0][0]
    to_del = [d for d in by if s2t[d] == tgt]
    others = [p for p in sorted(set(labels)) if p != tgt]
    bt = bpb_true(tgt); bo_each = {p: bpb_true(p) for p in others}
    rm = sum(mem.delete_src(d) for d in to_del)               # experts are SHARED substrate -> not freed here; editable knowledge is the MEMORY
    at = bpb_true(tgt); ao_each = {p: bpb_true(p) for p in others}
    bo = sum(bo_each.values()) / max(1, len(others)); ao = sum(ao_each.values()) / max(1, len(others))
    print(f"\nUNLEARN whole process {tgt}: deleted {len(to_del)} self-domains ({rm} entries) | KEY_SRC={KEY_SRC}")
    print(f"  target process {bt:.3f}->{at:.3f} (rises=forgotten, Δ {at-bt:+.4f})")
    print(f"  other processes {bo:.3f}->{ao:.3f} (Δ {abs(ao-bo):.4f} = {'LOCAL' if abs(ao-bo) < 0.05 else 'LEAKED'})  [fixed {EVAL_N}-window eval]")
    for p in others: print(f"    process {p}: {bo_each[p]:.3f}->{ao_each[p]:.3f} ({ao_each[p]-bo_each[p]:+.4f})")
    print("\n(SIG_MODE={} -- learned = the unfrozen product path; deltas + purity + locality are what matter.)".format(SIG_MODE))


if __name__ == "__main__":
    main()
