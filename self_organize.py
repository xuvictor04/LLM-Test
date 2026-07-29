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
from world_model import WorldEncoder, DynamicsPopulation, pop_loss, _var_cov   # world model: latent forward-dynamics + SEPARATED population (gated)
try: sys.stdout.reconfigure(line_buffering=True)          # stream progress even when piped through tee (no -u needed)
except Exception: pass

def _i(k, d): return int(os.environ.get(k, d))
def _f(k, d): return float(os.environ.get(k, d))
DEV = os.environ.get("DEVICE", "cpu")
VERIFY = os.environ.get("VERIFY", "selfcon")               # "selfcon" (old B, default, unchanged) or "recon" (Verification)
RECON_W = _f("RECON_W", 0.0)                               # joint Reconstructor training during the loop: OFF by default --
#   it trained on the churning (re-tokenized, re-keyed) store and failed (0.3% precision). Verification now FITS post-hoc
#   on the final settled store (VERIFY_FIT). Set RECON_W>0 only to also nudge the base keys to be reconstructable.
VERIFY_SWEEP = _i("VERIFY_SWEEP", 0)                       # VERIFY=recon: also DELETE unverified entries (detect-AND-remove).
#   The old B stayed detect-only because ~1% precision made deleting suicidal; reconstruction's high precision earns this.
D = _i("D_MODEL", _i("D_MODEL_B", 128))                    # D_MODEL_B accepted as an ALIAS: it is the name used by
#   run_full_unfrozen.sh (which translates it to D_MODEL) and therefore the name every doc/command in this project
#   quotes -- but a DIRECT `D_MODEL_B=768 python3 self_organize.py` silently ran at the d=128 default, because nothing
#   here read it. That mis-sized every direct-invocation run, including the GPU bench (which reported 4.3M/5.1M params
#   instead of the intended 28.7M/53.9M) and the pilot command. Accepting both names removes the silent failure.
WIN = _i("WIN", 128); NP = _i("N_PROCESSES", 4); STREAM_LEN = _i("STREAM_LEN", 120000)
SUSTAIN = _i("SUSTAIN", 2); NEW_DIST = _f("NEW_DIST", 0.35); SHIFT_DIST = _f("SHIFT_DIST", 0.30)
SIG_MODE = os.environ.get("SIG_MODE", "learned"); SIG_D = _i("SIG_D", 64); SIG_DIM = _i("SIG_DIM", 512)
SELF_ORG = bool(_i("SELF_ORG", 1))                         # 0 = DISABLE domain self-assembly (standstill): one bucket, no provenance,
#   no management. Domains only give editing-by-provenance (NOT prediction), so a language-capability run can turn them off.
#   NOTE: the SigEncoder ALSO feeds fabric routing, so to remove ITS cost use SIG_MODE=bigram or the adaptive warmup -- separate lever.
ENC_EVERY = _i("ENC_EVERY", 1); ENC_BATCH = _i("ENC_BATCH", 48); TEMP = _f("TEMP", 0.1); REKEY_EVERY = _i("REKEY_EVERY", 200)
ENC_FUSE = bool(_i("ENC_FUSE", 1))                         # encode the InfoNCE anchor+positive batches in ONE pass (see below)
MANAGE_EVERY = _i("MANAGE_EVERY", 500)                     # expert/world-model cadence (domains use DOM_MANAGE_EVERY)
# CONSOLIDATION SCALE. This was 0.12, and because manage() takes `md = merge_dist if merge_dist > 0 else
# MERGE_FRAC*NEW_DIST`, a non-zero MANAGE_MERGE OVERRIDES the fallback -- so the 0.28 that MERGE_FRAC*NEW_DIST was
# designed to produce ("ONE scale for create AND consolidate", :MERGE_FRAC) had never once run. Creation used 0.35
# while consolidation used 0.12: a 3x mismatch, so domains were created far more readily than they could be joined.
# Measured on the 4 MB GPU run, long segments, everything else fixed:
#     MANAGE_MERGE   live   purity   homogeneity   completeness    V     fragmentation
#         0.12         25    0.97       0.90          0.60        0.72       8x
#         0.45          4    0.97       0.89          0.89        0.89       1x  <- bijection with the 4 corpora
# It reaches the true count while HOLDING purity and homogeneity at the 25-domain run's values, i.e. it consolidates
# siblings rather than smearing corpora. The falsification test matters as much as the result -- CPU, same config,
# pushing further:
#     0.45 -> 7 live, purity 0.96, hom 0.88     0.80 -> 4 live, purity 0.71, hom 0.60   <- COUNTERFEIT 4
#     0.60 -> 6 live, purity 0.88, hom 0.78     1.00 -> 5 live, purity 0.60, hom 0.52
# Beyond 0.45 the count still falls but purity collapses, so "4 domains" can be reached two ways and the COUNT
# ALONE CANNOT TELL THEM APART -- read purity/homogeneity alongside it, always. And note 0.45 yields 7 on CPU and 4
# on GPU: the threshold is a scale, not a target, and the count is a property of the data.
# WHICH IS WHY THE DEFAULT IS 0.28 AND NOT 0.45. 0.45 maximises V-measure against the four SEEDED corpora -- and
# those four are a scaffold we spliced in, not something the system discovered. Optimising to them is a
# RECONSTRUCTION score, and it is bought with the one thing the domain id actually controls.
# `did` is consumed in exactly three places: mem.src (provenance -> delete_src/reassign_src), dom_exp (reporting),
# and the clustering report. ROUTING DOES NOT USE IT -- fabric and experts route on the continuous `gist`, so the
# domain COUNT has essentially no effect on prediction. What it sets is the GRANULARITY OF FORGETTING. Measured,
# unlearning one process: at 25 domains that is 20 deletes of ~1.6% each; at 4 it is a single delete of 30%.
# Coarser domains do not predict better, they only make editing blunter.
# 0.28 = MERGE_FRAC*NEW_DIST, the value the code was designed around, restoring create/consolidate consistency
# without forcing the population down to the seeded count. Treat this as a POLICY knob (how finely do you want to
# be able to forget?), not a correctness one -- and read purity/homogeneity beside the count, never the count alone.
# NOT the final form. The natural scale is the MEASURED radius (pooled 0.29-0.62 across these runs), not a constant:
# two domains should merge when their acceptance balls substantially overlap. Unmeasured, so left undone.
MANAGE_MERGE = _f("MANAGE_MERGE", 0.28)
# --- domain population control. The old rules disagreed about what a domain IS: create at NEW_DIST=0.35 but
# merge at 0.12 (3x tighter, so everything between was permanent); `size` cumulative so anything reaching
# MANAGE_MIN was immortal; and no cap at all -- domains were the only population without a slot pool. The
# result was ~1 domain per SPLICE SEGMENT (96 for 4 corpora), with manage() O(N^2) doubling wall-clock at N~300.
MAX_DOMAINS = _i("MAX_DOMAINS", 64)        # hard cap, mirroring the expert bank's fixed slot pool
MERGE_FRAC = _f("MERGE_FRAC", 0.8)         # merge threshold = MERGE_FRAC*NEW_DIST -> ONE scale for create+merge
DOM_DECAY = _f("DOM_DECAY", 0.9)           # per-manage decay of the activity counter (ExpertRouter's rule)
DOM_GRACE = _i("DOM_GRACE", 500)           # min age before a domain may be culled
DOM_CULL_FRAC = _f("DOM_CULL_FRAC", 0.10)  # per-manage cull budget: bottom fraction by DECAYED activity
DOM_WINS = _i("DOM_WINS", 40)              # reservoir of sample windows per domain (the rekey basis)
# DEFAULTS RESTORED TO THE BEST MEASURED CONFIGURATION. Three successive 'fixes' of mine each LOWERED the
# primary metric: fixed thresholds V=0.42 (boundary recall 0.96) -> adaptive spawn 0.38 -> relative margin
# + recalibrated shift 0.12 -> relative margin + guessed shift 0.00. The scale analysis behind them is
# sound and the probe data is real, but no variant has yet BEATEN the constant thresholds end to end, and
# two of those runs changed the threshold rule and ENC_WARMUP together so they cannot even be attributed.
# They stay in the code, off by default, until a sweep shows one beating V=0.42. Turning them on:
#   DOM_RELATIVE=1   scale-free assignment (validated against 20 probe cells, never validated end to end)
#   SHIFT_REL=1      scale-free boundary test (calibrated q50*1.5 from probe within/across distances)
#   DOM_ADAPTIVE=1   the censored-median spawn threshold (superseded; kept for the record)
DOM_ADAPTIVE = bool(_i("DOM_ADAPTIVE", 0))  # calibrate the spawn threshold to MEASURED within-domain scatter
DOM_SPAWN_K = _f("DOM_SPAWN_K", 3.0)       # spawn only beyond median + K*MAD of recent assign distances
DOM_RELATIVE = bool(_i("DOM_RELATIVE", 0))  # assign on the RELATIVE margin (scale-free) rather than an absolute distance
DOM_MARGIN = _f("DOM_MARGIN", 0.75)        # re-identify when d(nearest) <= DOM_MARGIN * d(runner-up)
SHIFT_REL = bool(_i("SHIFT_REL", 0))       # boundary test relative to recent adjacent-distance scale, not a constant
SHIFT_Q = _f("SHIFT_Q", 0.50)              # quantile of recent adjacent distances used as the base
SHIFT_MULT = _f("SHIFT_MULT", 1.5)         # trip when the jump is this many times that base
# MEASURED ACCEPTANCE RADIUS + RECURRENCE FOLD -- the two that DID beat the constants, on a controlled test that
# isolates the assembler from the encoder (synthetic signatures, 4 recurring processes, known truth, 3 seeds):
#            config                live domains (truth 4)   V     live @ 120 / 240 / 480 segments
#   constant thresholds only              64.0             0.82      64 -> 116 -> 193     GROWS
#   + measured radius x1.2                18.0             0.95      18 ->  20 ->  25     nearly flat
#   + recurrence fold                      4.0             1.00       4 ->   4 ->   4     exact
# The last column is the point, and it is the first thing here that has ever passed it. A domain population that
# grows with stream length is not a partition of the material, it is a LOG OF THE SPLICES -- which is what every
# earlier configuration produced, including the 142-domain GH200 run. Radius + fold is INTENSIVE: it tracks how
# many kinds of thing there are, not how much text went past.
DOM_RADIUS = bool(_i("DOM_RADIUS", 1))     # PER-DOMAIN acceptance radius, measured from that domain's own reservoir
DOM_RQ = _f("DOM_RQ", 0.85)                # radius = this quantile of d(reservoir window, own centroid) ...
DOM_RMULT = _f("DOM_RMULT", 1.2)           # ... times this
# VORONOI GUARD: radius <= DOM_RCAP x the distance to the NEAREST other centroid. CALIBRATED, not assumed -- the
# first value tried here was 0.5 and it was the worst setting in the table, strangling the radius back to the
# baseline it was meant to fix (65 live / V 0.82, vs 4 live / V 1.00 with the guard off). Measured, fold on:
#   cap  0.0(off)  0.5   1.0   1.5   2.0   2.5   4.0
#   live    4.0   65.0   4.0   4.0   4.0   4.0   4.0        <- >= 1.5 is indistinguishable from off
# 2.0 sits in the flat region, so it costs nothing when the geometry is healthy, while still bounding the runaway
# it exists for (a radius that absorbs one foreign window measures a LARGER spread, which lets it absorb more --
# observed reaching 1.24 of a maximum possible 2.0). Set 0 to remove the guard entirely.
DOM_RCAP = _f("DOM_RCAP", 2.0)
DOM_RECUR = bool(_i("DOM_RECUR", 1))       # fold domains that never RECUR into their nearest neighbour
DOM_MIN_VISITS = _i("DOM_MIN_VISITS", 2)   # "recurs" = entered on >= this many SEPARATE occasions
DOM_RECUR_HORIZON = _i("DOM_RECUR_HORIZON", 32)   # judged only after this many BOUNDARIES since birth
DOM_FOLD_MULT = _f("DOM_FOLD_MULT", 1.5)   # refuse to fold further than this x the pooled radius (unguarded -> 1 domain)
# DOMAIN management gets its OWN cadence. It was sharing MANAGE_EVERY=500 with the expert and world-model
# populations, and at that cadence it essentially never ran: a 60 kB run is 468 steps, so `step % 500 == 0` was
# NEVER true and merge/cull/fold all executed ZERO times; the 120 kB GH200 runs are 937 steps, so it fired ONCE.
# Every domain-population number this project has reported was therefore produced with the consolidation half of
# the mechanism switched off by arithmetic. The expert and world cadences are left where they are -- their costs
# and their grace periods are tuned to 500 -- because this is a domain problem, not a shared-cadence problem.
DOM_MANAGE_EVERY = _i("DOM_MANAGE_EVERY", 100)
# DOM_PRIOR: accumulate a token histogram per domain and blend it into the prediction. 0 disables the
# accounting entirely (no cost); >0 is the blend weight actually used at eval. Measured before adopted.
DOM_PRIOR = _f("DOM_PRIOR", 0.15)
MANAGE_ON = bool(_i("MANAGE", 1))                          # MANAGE=0 -> ABLATION: no merge/cull (domains grow unbounded)
MANAGE_MIN = _i("MANAGE_MIN", 15); MANAGE_STALE = _i("MANAGE_STALE", 500)        #   cull domains < MIN windows unseen for STALE
KW = _i("KEY_WIN", 8); V = 256
USE_TOK = bool(_i("TOKENIZER", 0)); TOK_ONLINE = bool(_i("TOK_ONLINE", 0)); TOK = None; BLEN = None   # TOK_ONLINE=1 mints during training
torch.manual_seed(_i("SEED", 0)); random.seed(_i("SEED", 0))
# ---- GPU PRECISION (no functionality is removed by either knob; both only change how matmuls are executed) ----
# TF32: on by default for cuDNN but NOT for matmul in current torch, so the fp32 path leaves most of an H100's matmul
# throughput unused. AMP=bf16 additionally runs the LM step in bfloat16 -- same exponent range as fp32 (so no loss
# scaling and no GradScaler), which is the standard training precision on H100-class hardware.
if bool(_i("TF32", 1)):
    torch.backends.cuda.matmul.allow_tf32 = True; torch.backends.cudnn.allow_tf32 = True
AMP = os.environ.get("AMP", "off").lower()                 # "off" (default) | "bf16" | "fp16"


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
if USE_TOK and DATA_MODE != "real":
    raise SystemExit("TOKENIZER=1 requires DATA_MODE=real -- the tokenizer is only built on the real-data path,\n"
                     "  so the synthetic path leaves TOK=None and dies later inside _retok with a bare\n"
                     "  AttributeError. Add DATA_MODE=real (and DATA_DIR=...) to your command.")
if DATA_MODE == "real":
    DN = os.environ.get("DOMAINS", "eng,py,num,c").split(",")
    DISK_STREAM = bool(_i("DISK_STREAM", 0))              # mmap the corpus (disk-paged) so training data can EXCEED RAM (GPT-2 scale)
    from datastream import open_corpus
    CORP = open_corpus(os.environ.get("DATA_DIR", "data"), DN, cap=_i("CORPUS_CAP", 2000000), disk=DISK_STREAM)
    CORP = [c for c in CORP if len(c) > 5000]; NP = len(CORP)
    VAL_FRAC = _f("VAL_FRAC", 0.05)                        # HELD-OUT tail of each corpus, never sampled into the training stream.
    if DISK_STREAM:                                        # mmap: do NOT slice CORP (would copy the whole thing into RAM) --
        SEG_LEN = [int(len(c) * (1 - VAL_FRAC)) for c in CORP]   #   bound sampling to the training HEAD; keep CORP the full mmap.
        VALC = [bytes(CORP[p][SEG_LEN[p]:min(len(CORP[p]), SEG_LEN[p] + _i("VAL_CAP", 4000000))]) for p in range(NP)]
    else:
        VALC = [c[int(len(c) * (1 - VAL_FRAC)):] for c in CORP]  # in-RAM: unchanged -- val = tail, CORP = head.
        CORP = [c[:int(len(c) * (1 - VAL_FRAC))] for c in CORP]
        SEG_LEN = [len(c) for c in CORP]
    if USE_TOK:                                            # EXPANDING SUBWORD MODE: an online byte-BPE that GROWS its vocab
        from tokenizer import DynamicTokenizer             #   by mint-on-repetition as it reads the stream (byte-grounded)
        _tp = os.environ.get("TOKENIZER_PATH", "data/dyntok.json")
        VMAX = _i("VMAX", 4096)
        _target = _i("SEED_VOCAB", 512) if TOK_ONLINE else VMAX            # online: only SEED here; keep minting during training
        _passes = _i("SEED_PASSES", 2) if TOK_ONLINE else _i("GROW_PASSES", 8)
        if os.path.exists(_tp) and (not TOK_ONLINE or os.environ.get("RESUME")):
            TOK = DynamicTokenizer.load(_tp)               # RESUME must reuse the SAVED vocab: a fresh online seed would
            #   re-mint different ids, so the restored embedding table would be indexed by a DIFFERENT vocabulary.
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
    def seg_from(p, L): s = random.randint(0, SEG_LEN[p] - L - 1); return CORP[p][s:s + L]   # SEG_LEN bounds sampling to the train head
else:
    PROCS = [make_proc(s, ALPHA[s % len(ALPHA)]) for s in range(NP)]
    def seg_from(p, L): return PROCS[p](L)

# NON-STATIONARY BY DEFAULT, because that is the only stream that tests the thesis. A stationary i.i.d. splice of
# N corpora does not require continual learning at all -- it is ordinary training with extra machinery, and every
# number this project has reported was measured on it. PHASED shipped in the first commit defaulted to 0, sat
# alongside the ablation flags, and was never once turned on; when finally run it showed faded material +0.65
# bits/byte worse than a stationary control with 100% of its memory evicted, and the "unlearn a faded process"
# arm skipping itself as vacuous. Leaving it off is now the deliberate ablation (PHASED=0), not the default.
# Safe at any NP: the per-phase active set is filtered to existing processes and falls back to all of them, so a
# single-corpus run degenerates to stationary on its own.
PHASED = bool(_i("PHASED", 1))                             # NON-STATIONARY stream: processes ENTER and FADE over time
PHASE_SCHED = [[0, 1], [0, 1, 2], [1, 2, 3], [2, 3]]      # who is active in each quarter (2 enters, 0 fades, 3 enters, 1 fades)
PH_BOUNDS = []                                             # stream positions where each phase starts
def build_stream():
    buf = []; lab = []; sw = []; pos = 0
    if PHASED:                                             # NON-STATIONARY: each phase has a different ACTIVE set
        PH_BOUNDS.clear()                                  # REBUILT, not appended: build_stream runs once PER EPOCH
        #   under DISK_STREAM, and this list is read as `sum(1 for b in PH_BOUNDS if bpos >= b) - 1` to get the
        #   current phase. Accumulating gave 4 entries per epoch, so by epoch 3 that index read 8 for a position
        #   whose phase was 2 -- straight past the end of PHASE_SCHED. PHASED=1 would have failed in exactly the
        #   multi-epoch configuration it exists for.
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
        # norm=LayerNorm(d): with norm_first=True the FINAL sublayer output is never normalised, which is fine at
        # L1-L4 and progressively worse with depth -- GPT-2 has this final norm. prompt.py MUST match or every
        # saved checkpoint loads into a different network.
        s.tr = nn.TransformerEncoder(lyr, layers, norm=nn.LayerNorm(d), enable_nested_tensor=False)
        s.head = nn.Linear(d, V)
    def _mask(s, L, dev):
        # cache the causal mask: it is rebuilt on EVERY encode, and _model_key calls encode thousands of times per
        # step on tiny KW-length windows, so the allocate+triu is pure per-call overhead there.
        k = (L, str(dev))
        if getattr(s, "_mk", None) is None: s._mk = {}
        if k not in s._mk: s._mk[k] = torch.triu(torch.ones(L, L, device=dev), 1).bool()
        return s._mk[k]
    def encode(s, x, nlayers=None):
        """nlayers: run only the FIRST n blocks. The memory key only needs a representation of a KW=8 window, but it
        was paying the full stack -- at LAYERS=12 that is 12 layers of attention over 8 tokens, thousands of rows per
        step, in both the memory write and the amortized rekey, and it is what made the transformer lose overall
        despite its LM step time matching the GRU's. KEY_LAYERS caps the depth for the key path ONLY; the LM keeps
        every layer. Keys stay mutually comparable because rekey re-encodes stored contexts through the same path."""
        L = x.size(1); p = torch.arange(L, device=x.device).clamp(max=s.maxlen - 1)
        h = s.emb(x) + s.pos(p)
        m = s._mask(L, x.device)
        if nlayers is None or nlayers >= len(s.tr.layers):
            return s.tr(h, mask=m)
        for _l in s.tr.layers[:max(1, int(nlayers))]:
            h = _l(h, src_mask=m)
        return h
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
        s.d, s.sig_d, s.dk, s.alpha, s.max_steps, s.hid = d, sig_d, dk, alpha, max_steps, int(hid_mult * d)
        s.min_steps = min_steps                             # HALT blocked for this many steps. DEFAULT 0: measured,
                                                            #   the router's OWN light-touch routing (mass ~0.1) beat
                                                            #   forcing node use (2.034 vs 2.176). Only raise this if
                                                            #   node mass is ~0 AND the fabric is underperforming.
        s.bodies = nn.ModuleList([FabricNode(d, s.hid) for _ in range(n0)])
        s.register_buffer("cent", F.normalize(torch.randn(n0, sig_d), dim=-1))   # one region per expert. BUFFER, not a
        #   plain attribute: as an attribute it was absent from state_dict(), so the GROUNDED router's centroids -- which
        #   ARE the routing function when ROUTE_GROUNDED=1 (the default) -- were never saved, never resumed, and never
        #   moved to the GPU. prompt.py therefore routed every generation with untrained centroids.
        s.keys = nn.ParameterList([nn.Parameter(torch.randn(dk) * 0.1) for _ in range(n0)])
        s.qproj = nn.ModuleList([nn.Linear(sig_d, dk) for _ in range(n0)])
        s.halt_key = nn.Parameter(torch.randn(dk) * 0.1)
        s.q_entry = nn.Linear(sig_d, dk); s.nov = nn.Linear(1, dk); s.ctrl = nn.Linear(3, dk)
        s.norm = nn.LayerNorm(d); s.grown = 0
        s.norm_only = norm_only                             # ABLATION: normalization only, no nodes, no routing
        s.route_t = float(os.environ.get("ROUTE_T", 0.1))   # <1 sharpens routing -> mass concentrates -> specialization.
        #   DEFAULT LOWERED 1.0 -> 0.1: signature and centroid are unit vectors in SIG_D=64, so cosine logits have
        #   std ~1/sqrt(64) = 0.125. At T=1.0 the top-vs-mean weight ratio is ~1.37x REGARDLESS of N -- at N=64 that
        #   is w ~= 0.016 +/- 12%, i.e. very nearly uniform, so top-k picks noise and no expert can specialize.
        #   T=0.1 amplifies the same differences 10x, which is what makes a large population selectable at all.
        # GROUNDED ROUTING: an expert owns a REGION of signature space, exactly as a domain does (and domains DO
        # differentiate: purity 0.92). Free learned keys start symmetric, and with every expert trained to solve the
        # whole task there is no gradient that breaks the symmetry -> uniform generalists. A centroid EMA'd toward the
        # signatures it actually serves acquires a constituency, so its traffic becomes distinct and it specializes.
        s.grounded = bool(int(os.environ.get("ROUTE_GROUNDED", 1)))
        s.route_learn = bool(int(os.environ.get("ROUTE_LEARN", 1)))   # add the learned bilinear term (see route_w)
        s.birth_jitter = float(os.environ.get("BIRTH_JITTER", 0.15))
        s.cent_m = float(os.environ.get("CENT_EMA", 0.02))
    def grow(s, gist=None):                                 # add an expert; returns its new params
        dev = s.halt_key.device
        _ng = (F.normalize(gist.detach().mean(0, keepdim=True).cpu()
                           + s.birth_jitter * torch.randn(1, s.sig_d), dim=-1) if gist is not None
               else F.normalize(torch.randn(1, s.sig_d), dim=-1))
        #   JITTER: a burst grows several experts at ONE signature, so without it they are born as exact clones with
        #   identical regions and can never differentiate. Small enough to keep the newborn in the region that
        #   triggered its birth, large enough that the routing EMA can pull them apart.
        s.cent = torch.cat([s.cent.cpu(), _ng], 0)          # the newborn OWNS the region that triggered its birth
        b = FabricNode(s.d, s.hid).to(dev)                  # IDENTITY at birth -> inherits the CURRENT base's competence
        k = nn.Parameter(s.seed_key(gist) if gist is not None else torch.randn(s.dk, device=dev) * 0.1)
        q = nn.Linear(s.sig_d, s.dk).to(dev)
        s.bodies.append(b); s.keys.append(k); s.qproj.append(q); s.grown += 1
        return list(b.parameters()) + [k] + list(q.parameters())
    def route_w(s, gist, nov):
        """Routing weights over the N experts. Two terms, both kept:
          GROUNDED  cosine of the signature to each expert's owned REGION (centroid, EMA'd under no_grad).
          LEARNED   qproj[i](gist).keys[i] -- a per-expert bilinear score. This revives parameters that were
                    measurably DEAD: with ROUTE_GROUNDED=1 the router ran entirely off the centroid buffer and a
                    detached signature, so keys/qproj/q_entry/nov/ctrl/halt_key received NO gradient at all and
                    routing could not learn. `gist` is still detached (sig_of is no_grad), so the gradient reaches
                    the router's own parameters but never back into the SigEncoder -- which is the intent."""
        N = len(s.bodies)
        if s.grounded:
            C = F.normalize(s.cent[:N].to(gist.device), dim=-1)
            logits = (F.normalize(gist, dim=-1) @ C.t()) / max(1e-3, s.route_t)
            if s.route_learn:
                Q = torch.stack([q(gist) for q in s.qproj], 1)                 # (B,N,dk)
                Kn = torch.stack(list(s.keys), 0)                              # (N,dk)
                logits = logits + (Q * Kn[None]).sum(-1) + s.nov(nov[:, None]).sum(-1, keepdim=True)
            w = torch.softmax(logits, -1)
            with torch.no_grad():                                              # the winner's region moves toward this signature
                j = int(w.mean(0).argmax())
                s.cent[j] = F.normalize((1 - s.cent_m) * s.cent[j].to(gist.device)
                                        + s.cent_m * F.normalize(gist, dim=-1).mean(0), dim=-1).cpu()
        else:
            K = torch.stack(list(s.keys) + [s.halt_key], 0)
            c = torch.softmax(((s.q_entry(gist) + s.nov(nov[:, None])) @ K.t()) / max(1e-3, s.route_t), -1)
            w = c[:, :N]; w = w / w.sum(-1, keepdim=True).clamp_min(1e-9)      # router weights over experts
        return w

    def society(s, h, gist, nov, k=None):
        """SOCIETY OF EXPERTS: every expert maps the SAME base representation to its OWN output -- no chaining, so
        expert i's output never depends on expert j's.

        SPARSE: only the top-k experts by routing mass are COMPUTED. This is not an approximation of what ran before
        -- the caller already used only the top ENS_K outputs to form the logits and threw the dense blend away, so
        every expert beyond the k-th was computed, unused, and un-gradiented. Computing k of N makes the cost match
        the selection that was already happening, which is what makes a LARGE expert population affordable.
        Returns (w_full, O_k, idx) where idx maps O_k's columns back to global expert ids."""
        N = len(s.bodies)
        w = s.route_w(gist, nov)
        kk = N if k is None else int(min(max(1, k), N))
        idx = w.mean(0).topk(kk).indices if kk < N else torch.arange(N, device=w.device)
        O = torch.stack([s.bodies[int(i)](h) for i in idx], 1)                 # (B,kk,L,d) INDEPENDENT outputs
        return w, O, idx
    def remove(s, j):
        """DELETE an expert outright: its parameters are gone. In a society this should cost roughly that expert's
        own contribution; in an entangled mixture it damages everyone (the weights-unlearn failure mode)."""
        keep = [i for i in range(len(s.bodies)) if i != j]
        s.bodies = nn.ModuleList([s.bodies[i] for i in keep])
        s.keys = nn.ParameterList([s.keys[i] for i in keep])
        s.qproj = nn.ModuleList([s.qproj[i] for i in keep])
        s.cent = s.cent[keep].clone()                       # PRUNE THE CENTROID TOO. Without this, society() reads
        #   cent[:N] against the SHIFTED body list, so after deleting expert j every expert above j is routed by its
        #   neighbour's region -- silently misrouting the whole population and corrupting the independence test.
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
        c = torch.softmax(((s.q_entry(gist) + nb) @ K.t()) / max(1e-3, s.route_t), -1)   # (B,N+1) ENTRY distribution
        #   route_t applied HERE TOO. It was only ever applied on the society path, so the chaining path kept the
        #   flat T=1.0 distribution -- with N+1 near-equal logits, HALT starts with ~1/(N+1) and, being ABSORBING,
        #   accumulates every step. That is a large part of the measured 'halt 0.76, mean routed depth 0.24 of 4'.
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
            R = torch.softmax(torch.einsum('bnk,mk->bnm', Q, K) / max(1e-3, s.route_t), -1)   # (B,N,N+1) TRANSITION
            nxt = torch.einsum('bn,bnm->bm', nm, R)                           # propagate mass node -> operator
            nxt = nxt.clone(); nxt[:, HALT] = nxt[:, HALT] + c[:, HALT]       # HALT absorbs
            c = nxt / nxt.sum(-1, keepdim=True).clamp_min(1e-9)
        return h, depth / steps, mass / steps, bal / steps

class PlateauGrowth:
    """Grow capacity on a REGRESSION BURST, then hold until progress stalls again.

    The old rule grew ONE node whenever fast-vs-slow improvement fell below a threshold. Three problems, all measured:
    it could not fire before FAB_WARMUP=2000, then only once per FAB_COOLDOWN=1500, so a run got ~3 growth events in
    its first minute and none ever again; and one node per event cannot answer a distribution shift that needs several.

    The state machine instead is:
      WATCH   -- looking for an UNEXPECTED worsening: loss above the slow EMA by `z` robust deviations (running MAD,
                 so it is scale-free like the original fast/slow design and does not fire on ordinary gradient noise).
                 Also fires on a RAMP early on, so growth is rapid at the start instead of blocked by a warmup.
      BURST   -- return a burst of `burst` nodes at once.
      RECOVER -- do NOT re-arm while the model is re-learning. The burst itself causes a transient worsening, which
                 would otherwise re-trigger immediately; this is the "not resetting till stall" the design calls for.
                 Leaves RECOVER only once improvement has flattened (the ORIGINAL plateau test), or after rmax steps.
    Returns an INT (how many to grow), 0 for none."""
    def __init__(s, rel=0.002, cooldown=1500, warmup=2000, z=4.0, burst=3, ramp=0, rmin=600, rmax=20000):
        s.fast = s.slow = None; s.rel = rel; s.cool = cooldown; s.warm = warmup; s.last = -10**9
        s.z = z; s.burst = max(1, burst); s.ramp = ramp; s.rmin = rmin; s.rmax = rmax
        s.dev = 0.0; s.n = 0; s.state = "W"; s.t0 = 0; s.blackout = -10**9; s.why = ""
    def note_shift(s, t): s.blackout = t          # retok / resample: the loss jump is OURS, not the data's
    def step(s, loss, t):
        s.fast = loss if s.fast is None else 0.98 * s.fast + 0.02 * loss
        s.slow = loss if s.slow is None else 0.998 * s.slow + 0.002 * loss
        s.n += 1
        d = abs(loss - s.slow)                                               # running MAD -> robust scale
        s.dev = d if s.n == 1 else 0.99 * s.dev + 0.01 * d
        improving = (s.slow - s.fast) / max(1e-6, abs(s.slow))
        # EARLY RAMP first, and deliberately ABOVE the RECOVER gate: rapid initial growth is the point, and the
        # recover-until-stall rule (rmin=600) is far longer than the ramp cadence, so gating the ramp behind it let
        # the ramp fire exactly once. During the ramp the population is still forming, so there is no progress to
        # protect; RECOVER starts mattering after it.
        if s.ramp and t < s.ramp and t - s.last >= max(1, s.cool // 8):
            s.last = t; s.why = "ramp"; return s.burst
        if s.state == "R":                                                   # RECOVER: wait for the stall
            if t - s.t0 >= s.rmin and (improving < s.rel or t - s.t0 > s.rmax): s.state = "W"
            return 0
        if t - s.last < s.cool or t - s.blackout < s.cool: return 0
        unexpected = (loss - s.slow) > s.z * max(1e-6, s.dev)                 # a REGRESSION we did not cause
        if unexpected or (t >= s.warm and improving < s.rel):
            s.last = t; s.t0 = t; s.state = "R"; s.why = "REGRESSION" if unexpected else "stall"
            return s.burst if unexpected else 1                               # burst on shift, single node on a stall
        return 0

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
# THE ENCODER IS SIZED BY THE STREAM IT ACTUALLY READS, NOT BY THE LM'S VOCAB. It was nn.Embedding(V, d), and V is
# VMAX in online-tokenizer mode -- but ENC_SEQ is the raw BYTE stream there (see _resample: the ONLINE branch returns
# `_b` as ENC_SEQ), so ids 256..VMAX-1 could never be indexed. At Run A's VMAX=16384 / d=768 that is 12.4M of the
# encoder's 16.2M parameters -- 77% -- unreachable, yet allocated, held in two AdamW moment buffers, and traversed
# by the optimizer every single step, while the encoder is 70% of wall clock. It is NOT always 256: with
# TOKENIZER=1 TOK_ONLINE=0 the corpora themselves are tokenized, so ENC_SEQ really does carry ids up to
# TOK.vocab_size. Size it by which of those two streams this configuration feeds it.
# WHAT THE SIGNATURE ENCODER READS. Two independent choices, both default to the historical behaviour.
#
# SIG_SPACE=bytes (default): the signature window is raw bytes. This is a STABILITY choice, not a quality one --
#   with TOK_ONLINE the vocabulary grows mid-run and _retok re-segments the stream, so the same text maps to
#   different token sequences over time, while domain centroids persist for the WHOLE run and memory provenance is
#   keyed by domain id. Bytes are a fixed alphabet, so the coordinate system cannot shift underneath the assembler.
# SIG_SPACE=tokens: read the LM's token window instead. NOT a frozen vocabulary -- DynamicTokenizer minting is
#   append-only, so an id never changes meaning; only the SEGMENTATION of text changes as new tokens are minted,
#   and rekey() already re-encodes every reservoir on a cadence, which is exactly the mechanism for tracking that
#   drift. New ids are warm-started from their two constituents (the trick the LM already uses at :WARMSTART), so
#   the encoder inherits what it knows about "th" and "e" when "the" is minted rather than relearning from noise.
#   The signature space grows with the vocabulary instead of being pinned to it.
# SIG_WIN: byte width of the signature window when in byte space. 0 = WIN, the historical value -- which is a
#   WIDTH in bytes against a loop STRIDE of WIN tokens, so the encoder has been seeing only WIN/(WIN*bytes_per_
#   token) of the stream (~53% at 1.9 B/token) and that fraction DRIFTS as compression improves. Nobody chose
#   that. Set SIG_WIN to about WIN*bytes_per_token to cover the same text the LM step consumed.
SIG_SPACE = os.environ.get("SIG_SPACE", "bytes").strip().lower()
if SIG_SPACE not in ("bytes", "tokens"): sys.exit(f"SIG_SPACE must be bytes|tokens, got {SIG_SPACE!r}")
SIG_WIN = _i("SIG_WIN", 0)
ENC_V = V if (USE_TOK and (not TOK_ONLINE or SIG_SPACE == "tokens")) else 256
class SigEncoder(nn.Module):                               # LEARNED, LIVE domain-signature encoder (stays GRU regardless of LM)
    def __init__(s, d, sd):
        super().__init__(); s.emb = nn.Embedding(ENC_V, d); s.gru = nn.GRU(d, d, batch_first=True); s.proj = nn.Linear(d, sd)
    def forward(s, x): h, _ = s.gru(s.emb(x)); return F.normalize(s.proj(h[:, -1]), dim=-1)

def _load_enc(enc, sd):
    """Restore an encoder whose saved embedding may be the OLD over-sized one. Rows 0..ENC_V-1 are the only ones
    that were ever indexed, so they carry all the training that happened; the rest are at their init values."""
    w = sd.get("emb.weight")
    if w is not None and w.size(0) != ENC_V:
        if w.size(0) < ENC_V: raise ValueError(f"checkpoint encoder vocab {w.size(0)} < required {ENC_V}")
        sd = dict(sd); sd["emb.weight"] = w[:ENC_V]
        print(f"  [resume] encoder embedding {w.size(0)} -> {ENC_V} rows (ids >= {ENC_V} were never indexable)")
    enc.load_state_dict(sd)

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
KEY_LAYERS = _i("KEY_LAYERS", 0)                                            # >0: memory keys use only the first N
#   transformer blocks (see TinyTransformer.encode). 0 = full stack, i.e. unchanged. No effect on the GRU.


@torch.no_grad()
def _model_key(win):                                                        # (N,W) -> (N,D)
    _enc = getattr(model, "_raw_encode", model.encode)                      # RAW: keys must match what rekey re-encodes
    if KEY_LAYERS and MODEL_TYPE == "transformer":
        return _enc(win, nlayers=KEY_LAYERS)[:, -1]
    return _enc(win)[:, -1]
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

# MEMORY BLEND, GATED ON MATCH QUALITY. `hp` was dist.sum(), but read() scatters a SOFTMAX over the top-k, so
# dist ALWAYS sums to exactly 1.0 -- verified numerically. hp was therefore identically 1.0 and this was an
# UNCONDITIONAL 50/50 mix at every position, however bad the nearest neighbour. Meanwhile `conf` (the top cosine
# similarity) was computed by read() and discarded by every caller. That is why memory measured NET-NEGATIVE at
# every store size (-0.097 at 200k slots, -0.652 at 2k): half the probability mass came from retrieval even when
# retrieval had nothing useful. Gating on conf makes a poor match contribute ~nothing and a strong one contribute
# up to MEM_W. MEM_GATE=0 restores the old unconditional mix for A/B.
MEM_W = _f("MEM_W", 0.5)                                   # max share retrieval may take when the match is perfect
MEM_GATE = bool(_i("MEM_GATE", 1))                         # 0 = old unconditional 0.5 mix
MEM_CONF0 = _f("MEM_CONF0", 0.3)                           # similarity below this contributes nothing


def _mem_hp(dist, conf, dim=-1):
    """Blend weight for the memory distribution: MEM_W scaled by how good the nearest neighbour actually was."""
    if not MEM_GATE or conf is None:
        return dist.sum(dim, keepdim=True).clamp(max=1.0) * (MEM_W if MEM_GATE else 0.5)
    g = ((conf - MEM_CONF0) / max(1e-6, 1.0 - MEM_CONF0)).clamp(0.0, 1.0)
    return (MEM_W * g).reshape(*g.shape, 1) if g.dim() == dist.dim() - 1 else (MEM_W * g).unsqueeze(-1)


def sig_of_batch(wins, enc):
    """Signatures for N windows in ONE encoder call. `sig_of` is a BATCH-1 GRU over WIN timesteps run once per step,
    measured at 46% of the loop on an A100 at d=768 (4.7 ms/step, invariant to model type / AMP / ENC_FUSE) -- the
    single largest cost. Rows are independent, so this returns the same signatures the per-window calls would."""
    if SIG_MODE != "learned": return torch.stack([sig_of(w, enc) for w in wins])
    with torch.no_grad(): return enc(torch.tensor(wins, device=DEV, dtype=torch.long))


_ENC_T = {"t": None}                                       # device-resident copy of the encoder sequence (see below)


def set_enc_tensor(seq):
    """Cache the encoder's source sequence as a DEVICE tensor. contrastive_step is the single most expensive part of the
    step (profiled: ~87% of loop wall-clock at ENC_EVERY=1), and a large part of that was building its two batches out of
    Python lists -- 2*ENC_BATCH*WIN int conversions per step -- and copying them to the device. Gathering the same windows
    out of a resident tensor produces bit-identical batches with none of that."""
    if seq is None: _ENC_T["t"] = None; return
    try:
        _ENC_T["t"] = torch.as_tensor(bytes(seq) if isinstance(seq, (bytes, bytearray)) else list(seq),
                                      dtype=torch.uint8 if max(seq) < 256 else torch.int32, device=DEV)
    except (ValueError, TypeError, RuntimeError):
        _ENC_T["t"] = None                                 # fall back to the original list path rather than fail a run


def contrastive_step(enc, opt, stream, seen, asm=None):    # InfoNCE: nearby windows = positive, random = negative
    # The anchor bound must leave room for the POSITIVE, whose furthest start is `off` and which is WIN long.
    # `hi = seen - 3*WIN` only allowed for the DEFAULT radius (off <= 2*WIN, +WIN for the window), so raising
    # ENC_POS_MAX above 2*WIN ran the positive past the end of the stream -- IndexError on the gather path, and a
    # short window into torch.tensor on the list path. i.e. the knob added to TEST wider positives could not be
    # used at any non-default value. Bound it by the radius actually in use.
    _pmax = max(2 * WIN, _i("ENC_POS_MAX", 2 * WIN))
    hi = seen - WIN - _pmax
    if hi < ENC_BATCH: return
    enc.train()
    # POSITIVE-PAIR RADIUS. This sets what the encoder learns to be INVARIANT to, and it is the root of the
    # over-segmentation: the default draws the positive 64-256 bytes away (WIN//2 .. 2*WIN at WIN=128), which is
    # SHORTER than a splice segment (SEG_MIN=700). So a well-trained encoder is explicitly taught that two distant
    # windows of the SAME corpus are different -- and _assign, querying a single window against a 40-window centroid
    # mean, then spawns a new domain on every re-entry. MORE encoder training makes this WORSE, not better.
    # Widening it teaches corpus-level rather than 256-byte-locality invariance, but it also raises the fraction of
    # positives that straddle a domain boundary (measured 17.3% at 2*WIN with 4 domains), which teaches the opposite
    # error. The trade is real and unmeasured at scale, so the default is UNCHANGED and this is a sweepable knob.
    st = [random.randint(0, hi) for _ in range(ENC_BATCH)]; off = [random.randint(WIN // 2, max(WIN // 2 + 1, _pmax)) for _ in st]
    _t = _ENC_T["t"]
    if _t is not None and _t.numel() >= len(stream):
        _ar = torch.arange(WIN, device=DEV)
        A = _t[torch.tensor(st, device=DEV).unsqueeze(1) + _ar].long()
        P = _t[torch.tensor([s + o for s, o in zip(st, off)], device=DEV).unsqueeze(1) + _ar].long()
    else:
        A = torch.tensor([list(stream[s:s + WIN]) for s in st], device=DEV)
        P = torch.tensor([list(stream[s + o:s + o + WIN]) for s, o in zip(st, off)], device=DEV)
    # PROTOTYPE PAIRS. The offset positive above can only ever teach LOCALITY -- "these two windows are 64-256 bytes
    # apart". The assembler then asks a question the encoder was never trained on: "are these two windows the same
    # KIND of material", where the two may be tens of thousands of bytes apart. ENC_PROTO replaces a fraction of the
    # batch with pairs drawn from ONE domain's reservoir, which are exactly that: two windows the assembler already
    # believes belong together, at whatever separation the stream gave them.
    # THE HAZARD IS REAL AND IS WHY THIS IS OFF BY DEFAULT: the assembler's own partition trains the encoder that
    # produces the partition, so a wrong grouping can reinforce itself. That is bounded here by using only a
    # FRACTION of the batch (the rest stays grounded in raw stream locality) and by sweeping it before adopting.
    _pro = _f("ENC_PROTO", 0.0)
    if _pro > 0 and asm is not None and asm.cent:
        _cand = [i for i in asm.cent if len(asm.wins.get(i, ())) >= 2]
        _np = min(ENC_BATCH - 1, int(round(_pro * ENC_BATCH))) if _cand else 0   # never the WHOLE batch
        if _np > 0:
            _ar, _pr = [], []
            for _ in range(_np):
                _w = asm.wins[random.choice(_cand)]
                _x, _y = random.sample(range(len(_w)), 2)
                _ar.append(list(_w[_x])); _pr.append(list(_w[_y]))
            A[:_np] = torch.tensor(_ar, device=DEV); P[:_np] = torch.tensor(_pr, device=DEV)
    if ENC_FUSE:                                           # ONE encoder pass instead of two: the encoder is row-independent,
        z = enc(torch.cat([A, P], 0))                      #   so the MATHS is identical, at half the sequential GRU launches.
        za, zp = z[:ENC_BATCH], z[ENC_BATCH:]              #   Note: a different batch shape changes the kernel's reduction
    else:                                                  #   order, so results agree only to float32 rounding (~1e-5 rel),
        za, zp = enc(A), enc(P)                            #   not bit-for-bit. ENC_FUSE=0 restores the two-pass form.
    logits = za @ zp.t() / TEMP
    loss = F.cross_entropy(logits, torch.arange(ENC_BATCH, device=DEV))
    # ANTI-COLLAPSE. InfoNCE draws its negatives from the same stream, so on HOMOGENEOUS material there are no
    # cross-kind negatives and the trivial solution -- emit one constant vector -- is reachable. Its loss is exactly
    # ln(ENC_BATCH), and a single-corpus 4 MB run plateaued at 3.83 against ln(48)=3.871 while separation fell
    # 0.16 -> 0.05 and the assembler found 0 boundaries. The 4-corpus run reached 2.10 on the same code: the other
    # corpora were not throwing the system off, they were the only thing PREVENTING the collapse.
    # _var_cov is the project's existing VICReg-style remedy (world_model.py), used for the dynamics population and
    # never applied to the encoder that actually collapses. Its variance hinge targets std>=1, which is impossible
    # for L2-NORMALISED outputs -- a uniform unit vector in SIG_D dims has per-dim std 1/sqrt(SIG_D) -- so scale by
    # sqrt(SIG_D) first, which puts a well-spread signature space exactly at the hinge.
    # ON by default. The realistic target is ONE large corpus, where collapse is not a risk but a certainty,
    # and the cost on mixed material is small: 4 corpora scored V 0.56 -> 0.52 and 4.322 -> 4.384 bits/byte
    # with it on, against 1-2 inert domains -> 13-24 working ones on a single corpus. 5.0 is the value that
    # actually restores an orthogonal-ish space (separation 0.97); 1.0 leaves it half-collapsed at 0.44.
    _vw = _f("ENC_VREG", 5.0); _cw = _f("ENC_CREG", 0.0)
    if _vw > 0.0 or _cw > 0.0:
        _v, _c = _var_cov(torch.cat([za, zp], 0) * (SIG_D ** 0.5))
        loss = loss + _vw * _v + _cw * _c
    # LOSS FLOOR -- the single largest measured lever on domain identity, and the one that says the ASSIGN RULE was
    # never the main problem. Freezing the encoder is not an option in a continual system; new material has to be
    # able to move it. But training it to convergence is actively HARMFUL: 1-NN corpus accuracy PEAKS at ~1000-4000
    # steps and degrades after, while d(query, own centroid) inflates .037 -> .668 over the same range, because
    # InfoNCE keeps pushing same-corpus windows apart long after they are separable. The floor gates the STEP, not
    # the loss, so training resumes by itself the moment new material makes the loss climb back.
    # WHY THIS FORM: with batch B, one positive and B-1 negatives, ln(1 + (B-1)/K) is the loss of an encoder that
    # cannot separate the positive from K-1 equally-good candidates. If the stream holds NP kinds of material, ~
    # (B-1)/NP of the negatives are the SAME kind as the positive, so a perfect KIND encoder cannot do better than
    # ln(1 + (B-1)/NP) -- i.e. K = the number of kinds present, and everything below that floor is the encoder
    # learning to tell apart things that are not actually different.
    # MEASURED, real text, 60 kB / 4 corpora / ENC_WARMUP=4000, everything else identical:
    #   arm                        live  created  folded  recurrent  bnd prec/rec  hom   comp    V
    #   constants (old default)     50     50       0        34%      0.61/0.84   0.80  0.29   0.42
    #   radius+fold                 36     46      10        61%      0.61/0.84   0.70  0.28   0.40
    #   floor K=8 alone             23     28       0        48%      0.78/0.84   0.70  0.38   0.49
    #   floor K=8 + radius+fold     16     21       1        88%      0.76/0.86   0.70  0.39   0.50
    #   floor K=4 + radius+fold      6     10       0        83%      0.79/0.59   0.56  0.52   0.54
    # The floor dominates, the two compose, and K=4 (= NP here, the theoretical value) lands closest to the truth.
    # The default is 8 and not 4 deliberately: K=4 buys its V by finding only 38 of 49 true switches (recall 0.59)
    # and by letting homogeneity fall to 0.56, and a domain that blends two corpora poisons provenance -- delete_src
    # would unlearn the wrong material. 8 keeps recall 0.86 and homogeneity 0.70. It also nearly HALVES wall clock.
    # Caveat, stated plainly: one run per arm, one stream length, one seed. sweep_domains.sh stage 1b grids K.
    _fk = _i("ENC_FLOOR_K", 8)
    if _fk > 0 and float(loss.detach()) <= math.log(1.0 + (ENC_BATCH - 1) / float(_fk)):
        return float(loss.detach())
    opt.zero_grad(); loss.backward(); opt.step()
    return float(loss.detach())


class DomainAssembler:
    """Self-organizes an unlabeled stream into domains AND MANAGES them: MERGES redundant domains and CULLS
    tiny/stale ones (analogous to the expert cull -- the project's biggest win). Domains carry STABLE ids so the
    memory's provenance stays valid across merges/culls. manage() prunes the domain set and the MEMORY together --
    a merge reassigns the loser's memory to the survivor; a cull deletes the culled domain's memory.

    OVER-SEGMENTATION FIX. The old version partitioned the stream into ~1 domain per SEGMENT (96 domains for 4
    corpora) because four rules disagreed with each other:
      1. _assign was queried with the SINGLE raw window that tripped the boundary -- the noisiest possible sample of
         the new run -- against centroids that are MEANS of 40 windows. A single-window signature sits further from
         its own class mean than NEW_DIST, so re-entering a known domain reliably SPAWNED instead of re-identifying.
         The encoder makes this worse as it trains: contrastive_step's positive is a window 64-256 bytes away, i.e.
         its learned invariance radius is SHORTER than a segment (SEG_MIN=700), so a trained encoder is *supposed* to
         separate two distant windows of the same corpus. Assign now uses the MEAN of the run that triggered the
         boundary, which shrinks within-domain scatter without touching between-domain separation.
      2. creation used NEW_DIST=0.35 but consolidation used MANAGE_MERGE=0.12 -- 3x tighter. Every pair in
         [0.12, 0.35) was permanent. Merge now derives from the SAME scale as creation (MERGE_FRAC*NEW_DIST).
      3. `size` was cumulative and never reset, so any domain that ever reached MANAGE_MIN windows was immortal.
         `act` is a DECAYED activity counter -- the exact rule ExpertRouter already uses (`s.use[i] *= 0.9`).
      4. domains were the only UNCAPPED population. MAX_DOMAINS mirrors the expert bank's fixed slot pool: at cap we
         absorb into the nearest centroid instead of growing. `capped` counts how often the cap bound (if it is
         large, the encoder or NEW_DIST is wrong -- the cap is a safety net, not a substitute for calibration).
    Also: _assign/manage/rekey were O(N) and O(N^2) PYTHON loops with a .item() sync per pair. They are now one
    matmul each, which is what makes a bounded-but-large population affordable."""
    def __init__(s):
        s.run_sig = None; s.cent = {}; s.wins = {}; s.size = {}; s.last = {}
        s.act = {}; s.born = {}                                           # act: DECAYED use (cull); size: cumulative (reporting)
        s.cur = -1; s.run = 0; s.next_id = 0; s.merged = {}               # merged[b]=a: b was folded into a (for scoring)
        s._ids = []; s._C = None; s._pend = []                            # cached (N,SIG_D) centroid matrix + pending run sigs
        s._dh = []                                                        # recent assign distances -> the adaptive spawn threshold
        s._sh = []                                                        # recent adjacent-window distances -> scale-free shift test
        s.rad = {}; s._radp = None                                        # per-domain radius + POOLED radius (young domains)
        s.tokc = {}                                                       # domain -> token counts (the PREDICTIVE prior)
        s.visits = {}; s.bornb = {}; s.nb = 0                             # recurrence: separate entries, BOUNDARY clock
        s.created = 0; s.capped = 0; s.folded = 0
    def _dirty(s): s._C = None
    def _mat(s):
        if s._C is None:
            s._ids = list(s.cent); s._C = torch.stack([s.cent[i] for i in s._ids]) if s._ids else None
        return s._ids, s._C
    def _new(s, sig, step):
        i = s.next_id; s.next_id += 1
        s.cent[i] = sig.clone(); s.wins[i] = []; s.size[i] = 0; s.act[i] = 0.0
        s.last[i] = step; s.born[i] = step; s.created += 1
        s.rad[i] = None; s.visits[i] = 0; s.bornb[i] = s.nb                # radius is measured at the next rekey
        s._dirty(); return i
    def resolve(s, d):
        while d in s.merged: d = s.merged[d]                              # follow merge chains to the survivor
        return d
    def _touch(s, i, sig):
        s.cent[i] = F.normalize(0.9 * s.cent[i] + 0.1 * sig, dim=0); s._dirty(); return i
    def update(s, sig, window, step):
        boundary = False
        if s.run_sig is None: s.run_sig = sig.clone()
        else:
            d = 1 - F.cosine_similarity(sig.unsqueeze(0), s.run_sig.unsqueeze(0)).item()
            # SCALE-FREE SHIFT TEST, CALIBRATED. q75*2.0 (the first attempt) was a GUESS shipped alongside the
            # probe-validated DOM_MARGIN, and it silently switched the boundary detector OFF: against the measured
            # within/across distances it stops firing from N=1000 onward, and a run at ENC_WARMUP=4000 found 14
            # boundaries for 3213 true switches (recall 0.01), collapsing the assembler to a single domain.
            #   N=200  within 0.019 across 0.094 | q75*2.0 = 0.068 fires | q50*1.5 = 0.028 fires
            #   N=1000 within 0.106 across 0.215 | q75*2.0 = 0.316 DEAD  | q50*1.5 = 0.159 fires
            #   N=4000 within 0.212 across 0.342 | q75*2.0 = 0.559 DEAD  | q50*1.5 = 0.318 fires
            # q50*1.5 fires at every stage the probe measured (it fails only at N=16000, where the distributions
            # overlap so heavily that AUC is 0.70 and no threshold does well -- another reason not to over-train
            # the encoder). SHIFT_DIST has exactly the disease NEW_DIST had: the probe measured
            # within-segment adjacent-window distance running 0.044 -> 0.229 -> 0.317 -> 0.340 as the encoder
            # trains, against a CONSTANT 0.30 -- so boundary precision goes 0.92 at N=200 to 0.27 at N=16000,
            # tripping on ordinary within-segment variation. Compare instead against a running quantile of recent
            # adjacent distances, which rides the scale up with the encoder. SHIFT_REL=0 restores the constant.
            thr = SHIFT_DIST
            if SHIFT_REL and len(s._sh) >= 64:
                v = sorted(s._sh); thr = max(1e-6, v[min(len(v) - 1, int(SHIFT_Q * len(v)))] * SHIFT_MULT)
            s._sh.append(d)
            if len(s._sh) > 512: s._sh.pop(0)
            if d > thr: s.run += 1; s._pend.append(sig); boundary = s.run >= SUSTAIN
            else: s.run = 0; s._pend = []; s.run_sig = F.normalize(0.85 * s.run_sig + 0.15 * sig, dim=0)
        if boundary: s.nb += 1                                            # BOUNDARY clock -> the recurrence horizon. A step
        #   clock would judge a domain born in a quiet stretch on the same deadline as one born in a busy one; what a
        #   domain needs before "it never came back" is fair is a number of CHANCES to be re-entered, i.e. boundaries.
        if boundary or s.cur < 0 or s.cur not in s.cent:
            q = F.normalize(torch.stack(s._pend).mean(0), dim=0) if s._pend else sig   # SMOOTHED assign query
            _prev = s.cur
            s.cur = s._assign(q, step); s.run_sig = q.clone(); s.run = 0; s._pend = []
            if s.cur != _prev: s.visits[s.cur] = s.visits.get(s.cur, 0) + 1   # a SEPARATE entry (not a re-confirmation)
        s.size[s.cur] += 1; s.act[s.cur] = s.act.get(s.cur, 0.0) + 1.0; s.last[s.cur] = step
        w = s.wins[s.cur]
        if len(w) < DOM_WINS: w.append(window)                             # RESERVOIR (was: first-40-only, which pinned the
        elif random.random() < DOM_WINS / float(s.size[s.cur]):            #   centroid to the domain's BIRTH forever, so rekey
            w[random.randrange(DOM_WINS)] = window                         #   kept undoing both the EMA drift and every merge)
        return s.cur, boundary
    def _assign(s, sig, step):
        if not s.cent: return s._new(sig, step)
        ids, C = s._mat()
        sims = C @ sig                                                    # ONE matmul + ONE sync (was N python .item() calls)
        j = int(sims.argmax()); d = 1 - float(sims[j])
        # ADAPTIVE SPAWN THRESHOLD. A FIXED NEW_DIST cannot work here, and the GH200 run showed exactly why:
        # measured mean within-domain cohesion 0.61, i.e. a query re-entering its OWN domain sits 0.39 from that
        # domain's centroid -- while NEW_DIST is 0.35. Re-entry was ARITHMETICALLY FORCED to spawn, every time, so
        # the population ran to 142 domains for 4 corpora with silhouette -0.22 (not distinct clusters at all).
        # The scale of within-domain scatter is a property of the encoder and of the data, and it MOVES as the
        # encoder trains -- so it has to be measured, not assumed. Track the distances at which we actually assign
        # and spawn only on the high tail (median + k*MAD), the same robust-deviation rule used for self-consistency.
        # SCALE-FREE ASSIGNMENT. The previous rule tracked the median of distances AT WHICH ASSIGNMENT HAPPENED --
        # but assignment only happens when d < threshold, so that sample is CENSORED and structurally cannot follow
        # the drift it exists to follow. It halved the domain count and made the partition worse.
        # The measured problem is that the metric's SCALE is non-stationary while every threshold is a constant:
        # d(query, own centroid) runs .037 -> .136 -> .319 -> .421 -> .668 at 200/400/800/1000/4000 encoder steps,
        # because the InfoNCE positive is only 64-256 bytes away and training keeps pushing same-corpus windows
        # apart. NEW_DIST=0.35 is below d_other early (everything merges) and above d_own later (everything splits);
        # no constant sits between them for more than a few hundred steps.
        # The RELATIVE margin is invariant to that whole inflation: the corpus signal is intact throughout
        # (1-NN corpus accuracy 84-95% at every stage), so ask whether the nearest centroid is decisively nearer
        # than the runner-up, not whether it is nearer than some absolute number.
        # MEASURED RADIUS. Every acceptance rule above compares d against a number that was never measured on THIS
        # domain: NEW_DIST is a constant, the margin is a ratio to whatever happens to be second-nearest. What the
        # question actually needs is this domain's own spread -- and that is already sitting in the reservoir, which
        # rekey() encodes anyway, so it costs nothing to measure (see rekey).
        # Note what this is NOT: an earlier version of this estimated the radius from the distances at which a domain
        # was MATCHED. That cannot bootstrap -- matching requires a radius, so with NEW_DIST too tight nothing is
        # matched, no samples accumulate, and the radius never activates. Measured: 0 of 143 domains ever learned one,
        # and a pooled prior over the same censored sample did not fix it (the pool held 3-5 entries). The reservoir
        # is UNCENSORED: a window enters it because it was assigned, whatever the threshold said.
        _r = None
        if DOM_RADIUS:
            _r = s.rad.get(ids[j])
            if _r is None: _r = s._radp                                   # pooled fallback until this domain's first rekey
        if DOM_RELATIVE and sims.numel() >= 2:
            top2 = torch.topk(sims, 2).values
            d1 = 1 - float(top2[0]); d2 = 1 - float(top2[1])
            if d1 <= DOM_MARGIN * d2 or (_r is not None and d1 <= _r): return s._touch(ids[j], sig)
            if len(s.cent) < MAX_DOMAINS: return s._new(sig, step)
            s.capped += 1; return ids[j]                                 # at cap: absorb without dragging
        if _r is not None and d <= _r: return s._touch(ids[j], sig)      # inside this domain's own spread -> re-entry
        thr = NEW_DIST
        if DOM_ADAPTIVE and len(s._dh) >= 64:
            v = sorted(s._dh); m = v[len(v) // 2]
            mad = sorted(abs(x - m) for x in v)[len(v) // 2]
            thr = max(NEW_DIST, min(0.9, m + DOM_SPAWN_K * (mad + 1e-6)))
        if d < thr:
            s._dh.append(d)
            if len(s._dh) > 512: s._dh.pop(0)
            return s._touch(ids[j], sig)
        if len(s.cent) >= MAX_DOMAINS:                                    # AT CAP: absorb into the nearest WITHOUT dragging
            s.capped += 1; return ids[j]                                  #   its centroid (a forced far match must not
        #   pollute the cluster it lands in). manage() reclaims slots on the next tick; `capped` says if the cap is binding.
        return s._new(sig, step)
    def rekey(s, enc, chunk=512):
        ids = [i for i in s.cent if s.wins[i]]
        if not ids: return
        flat = [w for i in ids for w in s.wins[i]]                        # ONE batched encode for ALL domains (was N
        with torch.no_grad():                                             #   sequential GRU passes: N*128 serial launches)
            Z = torch.cat([enc(torch.tensor(flat[a:a + chunk], device=DEV)) for a in range(0, len(flat), chunk)])
        o = 0; _all = []
        for i in ids:
            n = len(s.wins[i]); zi = Z[o:o + n]; c = F.normalize(zi.mean(0), dim=0); s.cent[i] = c; o += n
            di = 1 - zi @ c; _all.append(di)                               # the radius is FREE here: already encoded
            if n >= 4: s.rad[i] = float(di.kthvalue(max(1, min(n, int(round(DOM_RQ * n))))).values) * DOM_RMULT
        if _all: s._radp = float(torch.quantile(torch.cat(_all), DOM_RQ)) * DOM_RMULT
        s._dirty()
        if DOM_RCAP > 0 and len(s.cent) > 1:
            # VORONOI GUARD. A radius estimated from a domain's own scatter can run away in the wrong direction: let
            # it absorb one foreign window and it measures a LARGER scatter, which lets it absorb more (measured:
            # pooled radius 1.24 of a maximum possible 2.0, after exactly that collapse). Bound every radius by the
            # distance to the nearest OTHER centroid, so acceptance regions cannot overlap and no domain can eat a
            # neighbour whole -- consolidation stays the merge loop's job, where it is bounded and symmetric.
            ids2, C2 = s._mat(); M = C2 @ C2.t(); M.fill_diagonal_(-2.0)
            _nn = 1 - M.max(1).values                                     # (not `nn` -- that is torch.nn at module scope)
            for k, i in enumerate(ids2):
                cap = DOM_RCAP * float(_nn[k])
                s.rad[i] = cap if s.rad.get(i) is None else min(s.rad[i], cap)
            if s._radp: s._radp = min(s._radp, DOM_RCAP * float(_nn.median()))
    def _absorb(s, a, b, mem):
        """Fold b into a: memory provenance follows, reservoirs pool, ids stay resolvable through s.merged."""
        if mem is not None: mem.reassign_src(b, a)                        # MERGE/FOLD -> memory follows (indirect prune)
        na, nb = s.size[a], s.size[b]
        s.cent[a] = F.normalize((s.cent[a] * na + s.cent[b] * nb) / max(1, na + nb), dim=0)
        s.size[a] += nb; s.act[a] = s.act.get(a, 0.0) + s.act.get(b, 0.0)
        s.visits[a] = s.visits.get(a, 0) + s.visits.get(b, 0)
        if b in s.tokc:                                                   # counts follow the merge, like memory does
            s.tokc[a] = s.tokc[a] + s.tokc[b] if a in s.tokc else s.tokc[b]
        pool = s.wins[a] + s.wins[b]                                      # SAMPLE the union (was [:40], which kept only the
        s.wins[a] = random.sample(pool, DOM_WINS) if len(pool) > DOM_WINS else pool   # survivor's -> next rekey UNDID the merge).
        #   It also matters for the fold specifically: pooling is what gives the survivor a SECOND segment, which is
        #   what turns a segment prototype into a domain prototype.
        s.last[a] = max(s.last[a], s.last[b]); s.born[a] = min(s.born[a], s.born[b])
        s.bornb[a] = min(s.bornb.get(a, s.nb), s.bornb.get(b, s.nb)); s.rad[a] = None   # re-measure at the next rekey
        for _D in (s.cent, s.wins, s.size, s.last, s.act, s.born, s.rad, s.visits, s.bornb, s.tokc): _D.pop(b, None)
        s.merged[b] = a; s._dirty()
    def manage(s, step, mem, merge_dist, min_size, stale):
        merged = culled = 0
        if DOM_RECUR and len(s.cent) > 1:
            # RECURRENCE FOLD. Domains are created at boundaries; until now nothing ever asked whether the thing
            # created came BACK. That is the whole test for self-assembly: a real domain is re-entered when similar
            # material returns (a corpus recurs ~STREAM/(NP*SEG) times), while a splice artifact is entered once and
            # never again. Fold rather than delete, so provenance survives and the survivor inherits the reservoir.
            drop = [i for i in s.cent if s.visits.get(i, 0) < DOM_MIN_VISITS
                    and s.nb - s.bornb.get(i, s.nb) >= DOM_RECUR_HORIZON]
            ds = set(drop)                                                # never fold one doomed domain into another
            for b in sorted(drop, key=lambda i: s.act.get(i, 0.0)):
                keep = [i for i in s.cent if i != b and i not in ds]
                if not keep: break
                K = torch.stack([s.cent[i] for i in keep]); sm = K @ s.cent[b]
                k = int(sm.argmax())
                # FAIL SAFE, both ways. Too far from anything -> leave it standing. NO pooled radius yet (no rekey
                # has run) -> also leave it standing: an unbounded fold collapses the whole population to one
                # domain, which is far worse than folding late.
                if not s._radp or 1 - float(sm[k]) > DOM_FOLD_MULT * s._radp: ds.discard(b); continue
                s._absorb(keep[k], b, mem); s.folded += 1
        md = merge_dist if merge_dist > 0 else MERGE_FRAC * NEW_DIST      # ONE scale for create AND consolidate
        while len(s.cent) > 1:                                            # merge every pair under md, ONE matmul per merge
            ids, C = s._mat(); n = len(ids)
            M = C @ C.t(); M.fill_diagonal_(-2.0)
            k = int(M.argmax()); r, c = k // n, k % n
            if 1 - float(M[r, c]) >= md: break
            a, b = ids[r], ids[c]
            if s.act.get(b, 0.0) > s.act.get(a, 0.0): a, b = b, a         # keep the more ACTIVE (was: the lower id)
            s._absorb(a, b, mem); merged += 1
        if len(s.cent) > 1:                                               # CULL: DECAYED activity + age grace (expert rule)
            order = sorted(s.cent, key=lambda i: s.act.get(i, 0.0))
            for d in order[:max(1, int(DOM_CULL_FRAC * len(s.cent)))]:
                if len(s.cent) <= 1: break
                if step - s.born.get(d, step) < DOM_GRACE: continue
                if not (s.act.get(d, 0.0) < min_size and step - s.last[d] > stale): continue
                if mem is not None: mem.delete_src(d)                     # CULL -> memory follows (direct prune)
                for _D in (s.cent, s.wins, s.size, s.last, s.act, s.born, s.rad, s.visits, s.bornb, s.tokc): _D.pop(d, None)
                culled += 1; s._dirty()
        for i in s.act: s.act[i] *= DOM_DECAY                             # DECAY -> `act` reflects RECENT use, so a domain
        return merged, culled                                             #   that stops being fed becomes cullable

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
    confG = torch.zeros(pm.size(0), device=DEV)           # top similarity per query -- the blend gate (see _mem_hp)
    for s in range(0, keys.size(0), 4096):                # chunk to bound memory
        sim = F.normalize(keys[s:s + 4096], dim=-1) @ K.t()
        tv, ti = sim.topk(kk, -1); w = torch.softmax(tv / 0.1, -1)
        confG[s:s + 4096] = tv.max(-1).values.clamp(0, 1)
        ht = toks[ti]; hs = srcs[ti]
        div_sum += (torch.tensor([len(set(r.tolist())) for r in hs], device=DEV).float()).sum().item(); n += hs.size(0)
        distG[s:s + 4096].scatter_add_(1, ht, w)
        keep = (hs == hs[:, 0:1]).float(); wS = w * keep; wS = wS / wS.sum(-1, keepdim=True).clamp(min=1e-9)
        distS[s:s + 4096].scatter_add_(1, ht, wS)
    def bpb(dist, cf=None):
        hp = _mem_hp(dist, cf, dim=-1)
        pp = (1 - hp) * pm + hp * dist
        return -(torch.log(pp.gather(-1, Y.unsqueeze(-1)).squeeze(-1).clamp_min(1e-9)).sum().item()) / math.log(2) / nbytes(Y)
    bm, bg, bs = bpb(torch.zeros_like(distG)), bpb(distG, confG), bpb(distS, confG)   # ALONE vs +memory vs siloed
    print(f"\n=== PERFORMANCE: does the memory earn its keep? (bits/byte, lower=better) ===")
    print(f"  model ALONE (weights only) {bm:.3f}  ->  model + MEMORY {bg:.3f}   (memory contributes {bm - bg:+.3f})")
    print(f"\n=== CROSS-SEGMENT COMPOSITION (do the {len(procs)}-process / many-segment store's segments work together?) ===")
    print(f"  top-{kk} retrieval spans {div_sum / max(1, n):.2f} distinct segments per position  (>1 = composing across segments)")
    print(f"  model+memory GLOBAL (all segments) {bg:.3f}  vs  SILOED (nearest segment only) {bs:.3f}")
    print(f"  >> cross-segment retrieval {'HELPS' if bs > bg + 1e-3 else 'is not load-bearing'} by {bs - bg:+.3f} bits/byte "
          f"({'segments compose' if bs > bg + 1e-3 else 'each query served by one segment -- still fine, no siloing cost'})")
    # ---- IS THE PARTITION INFORMATIVE? A LABEL-FREE TEST. ------------------------------------------------------
    # Every clustering score above is scored against the SEEDED corpora, which are a scaffold WE spliced in -- so
    # they can only ever measure reconstruction of our own categories, never discovery. This asks a question that
    # needs no labels at all: restrict retrieval to the entries written by ONE domain, and compare the domain the
    # assembler actually assigned against a RANDOM other domain. If the partition carries information about the
    # data, own-domain retrieval predicts better than foreign-domain retrieval. If it is arbitrary, they tie.
    # Note this is deliberately NOT "own-domain vs global": global retrieval is expected to win (it has more to
    # draw on, and cross-segment composition is load-bearing above). The comparison is own vs foreign at MATCHED
    # restriction, which isolates whether the LABEL means anything.
    _own = mem.src[vi]                                    # provenance of every retrievable entry
    _doms = sorted(set(_own.tolist()))
    if len(_doms) < 2:
        # SAY WHY, rather than vanishing. This section disappearing silently is itself the signal: it needs at
        # least two domains with surviving entries, and a bounded store under a NON-STATIONARY stream can evict
        # everything except the most recent one. Observed at MEM_CAP=6000 with PHASED=1: p0=0 p1=0 p2=4976 p3=0.
        print(f"\n=== IS THE PARTITION INFORMATIVE? -- CANNOT BE MEASURED ===")
        print(f"  only {len(_doms)} domain(s) still hold retrievable entries out of a {mem.cap}-entry store, so "
              f"there is no 'other domain' to compare against.")
        print(f"  >> that is the answer to a different question: the store has EVICTED everything but the most "
              f"recent material. Raise MEM_CAP, or shorten the run, before reading any per-domain memory result.")
    else:
        def _own_vs_foreign(prov):
            """bits/byte with retrieval restricted to the query's OWN domain, and to a RANDOM OTHER one."""
            _ds = sorted(set(prov.tolist())); _dm = {d: k for k, d in enumerate(_ds)}
            _dt = torch.tensor(_ds, device=DEV)
            dO = torch.zeros(pm.size(0), V, device=DEV); dF = torch.zeros(pm.size(0), V, device=DEV)
            cO = torch.zeros(pm.size(0), device=DEV); cF = torch.zeros(pm.size(0), device=DEV)
            _g = torch.Generator(device="cpu"); _g.manual_seed(0)
            for s in range(0, keys.size(0), 4096):
                sim = F.normalize(keys[s:s + 4096], dim=-1) @ K.t()
                near = prov[sim.argmax(-1)]                                    # the query's own domain
                sh = torch.randint(1, len(_ds), (near.size(0),), generator=_g).to(DEV)
                ix = torch.tensor([_dm[int(x)] for x in near.tolist()], device=DEV)
                far = _dt[(ix + sh) % len(_ds)]                                # always a DIFFERENT domain
                for tag, dst, cf in ((near, dO, cO), (far, dF, cF)):
                    m = (prov.unsqueeze(0) == tag.unsqueeze(1))
                    sm = sim.masked_fill(~m, -1e9)
                    k2 = min(kk, int(m.sum(-1).max().item()) or 1)
                    tv2, ti2 = sm.topk(k2, -1)
                    ok = tv2 > -1e8
                    w2 = torch.softmax(tv2.masked_fill(~ok, -1e9) / 0.1, -1) * ok.float()
                    cf[s:s + 4096] = tv2.max(-1).values.clamp(0, 1)
                    dst[s:s + 4096].scatter_add_(1, toks[ti2], w2)
            return bpb(dO, cO), bpb(dF, cF)
        bo, bf = _own_vs_foreign(_own)
        # THE CONTROL, WITHOUT WHICH THE ABOVE IS WORTHLESS. "Own domain" is defined as the domain of the query's
        # NEAREST entry, so own-domain retrieval always contains the global top-1 hit and foreign never does -- it
        # would win on a partition made of coin flips. Re-run the identical comparison on a RANDOM PERMUTATION of
        # the provenance tags: same sizes, same top-1 advantage, no information. The permuted gap is the floor;
        # only the excess over it is evidence that the partition means anything.
        # SEVERAL permutations, not one. With a single draw the null has no error bar, and the verdict then turns
        # on a hard threshold that can sit inside the noise: two runs of the SAME configuration on one corpus came
        # back at excess +0.010 and +0.013 against a cutoff of 0.010, and printed opposite conclusions. An excess
        # is only evidence if it clears the spread of the null it is measured against.
        _nl = []
        for _s in range(_i("INFO_NULLS", 5)):
            _pm2 = _own[torch.randperm(_own.numel(), generator=torch.Generator().manual_seed(_s)).to(DEV)]
            _b1, _b2 = _own_vs_foreign(_pm2); _nl.append(_b2 - _b1)
        _real = bf - bo
        _null = sum(_nl) / len(_nl)
        _sd = (sum((x - _null) ** 2 for x in _nl) / max(1, len(_nl) - 1)) ** 0.5
        print(f"\n=== IS THE PARTITION INFORMATIVE? (label-free -- the seeded corpora play no part) ===")
        print(f"  OWN domain {bo:.3f}  vs  a RANDOM OTHER domain {bf:.3f}   -> gap {_real:+.3f} bits/byte "
              f"over {len(_doms)} domains present in memory")
        print(f"  SHUFFLED-provenance control (same sizes, no information)   -> gap {_null:+.3f} +/- {_sd:.3f} "
              f"over {len(_nl)} permutations  [the floor]")
        print(f"  >> EXCESS OVER THE NULL {_real - _null:+.3f} bits/byte, against a null spread of +/-{_sd:.3f}. "
              + ("the partition CARRIES INFORMATION beyond the top-1 artifact" if _real - _null > 2 * _sd + 1e-9 else
                 "NOT distinguishable from a random partition of the same shape (excess is within 2 sigma of"
                 " the null) -- the domain labels are not earning their keep for prediction. They may still be"
                 " earning it for EDITING, which this test does not measure."))

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
            dist, _cf, _, _ = mem.read(mem_key(x)[-1:])   # retrieval for the next position
            pmem = dist[0]; hp = _mem_hp(dist, _cf, dim=-1)[0]
            p = (1 - hp) * pm + hp * pmem
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
    kk = int(k or ENS_K)
    w, O, oid = fab.society(h, gist, nov, k=kk)               # SPARSE: computes only the kk it is about to use
    ww = w[:, oid]; ww = ww / ww.sum(-1, keepdim=True).clamp_min(1e-9)
    out = None
    for j in range(O.size(1)):
        lj = model.head(fab.norm(O[:, j])) * ww[:, j][:, None, None]
        out = lj if out is None else out + lj
    return out


@torch.no_grad()                                           # was building a full autograd graph over every stored
def selfcheck(model, mem, fab=None):                       # entry -- tens of GiB at L12, and pure waste: nothing
    #                                                        here is ever backpropagated. WRONGNESS (B): is each
    #                                                        stored token plausible under the model
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
    ONLINE = USE_TOK and TOK_ONLINE
    def _retok(bstream, blabels, start=0):                 # tokenize given bytes with the LIVE vocab -> (ids, byte-pos, labels)
        ids = TOK.segment(bytes(bstream[start:]) if start else bytes(bstream), count=False); bs, off = [], start
        for t in ids: bs.append(off); off += TOK.blen(t)
        return ids, bs, [blabels[min(o, len(blabels) - 1)] for o in bs]
    def _resample():                                       # (re)build the stream from a FRESH corpus sample -- called PER EPOCH on
        _b, _l, _sw = build_stream()                       #   disk so each epoch draws NEW data from the larger-than-RAM corpus
        if ONLINE:
            _s, _t, _lab = _retok(_b, _l)
            # ENC_SEQ is what contrastive_step TRAINS on, so it must be the same space the signature is READ in --
            # training the encoder on bytes and then querying it with token ids would index a table it never saw.
            return _s, _b, _l, _t, _lab, (_s if SIG_SPACE == "tokens" else _b), _sw
        return _b, None, _l, None, _l, _b, _sw
    stream, byte_stream, byte_labels, tok_bs, labels, ENC_SEQ, true_sw = _resample()
    set_enc_tensor(ENC_SEQ)
    route_at = torch.full(((len(ENC_SEQ) if ONLINE else len(stream)) + WIN + 2,), -1, dtype=torch.int16) if EXPERTS else None
    model = build_lm().to(DEV); enc = SigEncoder(D, SIG_D).to(DEV)
    recon = Reconstructor(D, V, _i("RECON_TOK", 32), _i("RECON_HID", 64)).to(DEV) if VERIFY == "recon" else None
    # WORLD MODEL (first brick, gated off by default): reads OBSERVATION EMBEDDINGS (the lowest layer = the point where
    # new SENSES plug in) and learns to predict how that observed world EVOLVES in latent space (physics-like, modality-agnostic).
    WORLD_MODEL = bool(_i("WORLD_MODEL", 0)); WLAT = _i("WORLD_LAT", 32); WORLD_W = _f("WORLD_W", 0.1); WORLD_K = max(1, _i("WORLD_K", 1)); WHID = _i("WORLD_HID", 128)
    WORLD_VAR = _f("WORLD_VAR", 1.0)                     # anti-collapse (variance+decorrelation) weight -- applied at FULL strength,
    #   NOT scaled by WORLD_W (scaling it by 0.1 let the latent collapse to std 0.24; the standalone probe uses full strength).
    WORLD_GROW = bool(_i("WORLD_GROW", 0))               # opt-in: also GROW-on-plateau + soft-cull the dynamics population (like experts)
    WORLD_FEEDBACK = bool(_i("WORLD_FEEDBACK", 0))       # THE LINK THAT MAKES IT MATTER: wire the world model's forecast BACK to
    #   condition the base LM -- generation is now informed by where the world model predicts the world is going, not a side-head.
    world_enc = WorldEncoder(D, WLAT, WHID).to(DEV) if WORLD_MODEL else None
    world_fwd = DynamicsPopulation(WLAT, _i("WORLD_N0", 3), _i("WORLD_NMAX", 6), WHID, _i("WORLD_ROUTE", 24)).to(DEV) if WORLD_MODEL else None  # SEPARATED: a routed society of dynamics predictors
    world_proj = nn.Linear(WLAT, D).to(DEV) if (WORLD_MODEL and WORLD_FEEDBACK) else None   # forecast -> hidden-state conditioning
    if WORLD_MODEL and WORLD_FEEDBACK:
        # WORLD FEEDBACK, APPLIED ONCE, CENTRALLY. Training added world_proj(forecast) to h inline while every eval and
        # generation path called model.encode directly -- so their numbers described a DIFFERENT network than the one
        # being trained. Wrapping encode fixes all of them at once. _raw_encode is kept for _model_key, whose output
        # must stay comparable with the stored keys that _rekey_amortized re-encodes.
        model._raw_encode = model.encode
        def _encode_wf(_xx, _m=model):
            _h = _m._raw_encode(_xx)
            _z = world_enc(_m.emb(_xx))
            _p = world_fwd(_z.reshape(-1, WLAT))[0].reshape(_xx.size(0), _xx.size(1), WLAT)
            return _h + world_proj(_p)
        model.encode = _encode_wf
    _wl_ema = None; _wl_lastgrow = 0                     # world-loss EMA + cooldown for plateau-triggered growth
    fab = Fabric(D, SIG_D, _i("FAB_DK", 32), _i("FAB_N0", 3), _f("FAB_ALPHA", 0.5), _i("FAB_STEPS", 4),
                 _f("FAB_HID_MULT", 2), _i("FAB_MIN_STEPS", 0), bool(_i("FAB_NORM_ONLY", 0))).to(DEV) if FABRIC else None
    fabgrow = PlateauGrowth(_f("FAB_PLATEAU", 0.002), _i("FAB_COOLDOWN", 400), _i("FAB_WARMUP", 300),
                            _f("FAB_Z", 4.0), _i("FAB_BURST", 3), _i("FAB_RAMP", 4000),
                            _i("FAB_RECOVER_MIN", 600), _i("FAB_RECOVER_MAX", 20000)) if FABRIC else None
    FAB_NMAX = _i("FAB_NMAX", 64); PONDER = _f("PONDER", 0.01)   # raised from 8: with sparse top-k the cost of a
    #   LARGE population is the k it computes, not N, so the old cap (3 growth events, all spent in the first
    #   minute) was limiting the population for a reason that no longer applies.
    _fab_nov = torch.full((), 0.5, device=DEV)
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
                if SOCIETY:
                    _w0, _O0, _ = fab.society(h, _g0, _n0, k=ENS_K)
                    model.head(fab.norm(_O0[:, 0])).sum().backward(); model.zero_grad()
                    if FABRIC: fab.zero_grad()
                    return
                h = fab(h, _g0, _n0)[0]
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
        print("  [probe is a LOWER BOUND -- it times ONLY the LM forward/backward. The real step also pays sig_of, the "
              "live contrastive encoder, the amortized re-key, domain assembly and memory. Trust the [rate] lines below.]")
        if DEV == "cuda": _t.sleep(12)
    # WEIGHT DECAY was implicit (AdamW defaults to 0.01). Decoupled decay is applied EVERY step to EVERY parameter
    # regardless of gradient, so a dormant expert loses ~71% of its magnitude over a 62.5k-step run -- an UNCONTROLLED
    # forgetting term inside a system whose whole point is CONTROLLED forgetting. Now explicit; 0 disables it.
    WD = WEIGHT_DECAY                                     # default 0.0: we are UNDERFIT, regularization would hurt
    # ---- RESUME (RESUME=runs/x): reload a checkpoint and CONTINUE training instead of starting from zero. A multi-day
    # multi-epoch run that dies at hour 20 previously lost everything even though checkpoints existed -- they were
    # generate-only. Grown populations (fabric nodes, dynamics predictors) are re-grown to their saved size BEFORE the
    # optimizers are built so their params are in the param groups and their Adam moments restore.
    KEY_PREGATE = bool(_i("KEY_PREGATE", 1))              # encode memory keys AFTER the surprise gate (see the write call)
    KEY_BATCH = bool(_i("KEY_BATCH", 1))                  # ...and encode the whole BATCH_W batch in ONE call (KEY_BATCH=0 = per-window)
    RESUME = os.environ.get("RESUME", "")
    _RD, _resume_step = None, 0
    if RESUME:
        _RD = torch.load(RESUME if RESUME.endswith(".pt") else f"{RESUME}/ckpt.pt", map_location=DEV, weights_only=False)
        if FABRIC and _RD.get("fab_cfg"):
            while len(fab.bodies) < _RD["fab_cfg"]["n"]: fab.grow()
        if WORLD_MODEL and _RD.get("world_cfg"):
            while world_fwd.n() < _RD["world_cfg"]["n"]: world_fwd.grow()
        model.load_state_dict(_RD["model"]); _load_enc(enc, _RD["enc"])
        if FABRIC and _RD.get("fab") is not None: fab.load_state_dict(_RD["fab"])
        if EXPERTS and _RD.get("experts") is not None: experts.load_state_dict(_RD["experts"])
        if WORLD_MODEL and _RD.get("world_enc") is not None:
            world_enc.load_state_dict(_RD["world_enc"]); world_fwd.load_state_dict(_RD["world_fwd"])
            if world_proj is not None and _RD.get("world_proj") is not None: world_proj.load_state_dict(_RD["world_proj"])
        _resume_step = int(_RD.get("step", 0))
    om = torch.optim.AdamW(list(model.parameters()) + (list(experts.parameters()) if EXPERTS else [])
                           + (list(fab.parameters()) if FABRIC else [])
                           + (list(recon.parameters()) if recon is not None else [])
                           + (list(world_enc.parameters()) + list(world_fwd.parameters()) if WORLD_MODEL else [])
                           + (list(world_proj.parameters()) if world_proj is not None else []), lr=2e-3, weight_decay=WD)
    oe = torch.optim.AdamW(enc.parameters(), lr=2e-3, weight_decay=WD)
    # PER-EXPERT MEMORY: each expert owns MEM_QUOTA entries, evicted by LRU on last USE. Sized to FAB_NMAX so the
    # partition does not have to be rebuilt as the population grows. MEM_PER_EXPERT=0 keeps the single global store.
    # DEFAULT OFF, on measurement: same seed, same config, only the store differs --
    #   global 200k slots -> memory contributes -0.097 b/B
    #   32 owners x 64    -> memory contributes -0.652 b/B
    # The partition costs 0.555 b/B at the scale tested, so it does not become the default path until it is shown to
    # help. (Memory being slightly net-negative even globally is a separate, pre-existing finding.)
    MEM_PER_EXPERT = bool(_i("MEM_PER_EXPERT", 0)) and FABRIC and SOCIETY
    MEM_QUOTA = _i("MEM_QUOTA", 128)
    mem = EditableMemory(_i("MEM_CAP", 200000), D, DEV, V, _f("WRITE_GATE", 0.3), _f("WRONG_THRESH", 1.0), _i("TOPK", 8),
                         ctx_w=(KW if KEY_SRC == "model" else 0), wrong_margin=_f("WRONG_MARGIN", 1.5), wrong_min_n=_i("WRONG_MIN_N", 3),
                         adaptive_gate=bool(_i("WRITE_ADAPTIVE", 0)), gate_target=_f("WRITE_TARGET", 0.5),
                         evict=os.environ.get("EVICT", "recency"), use_decay=_f("USE_DECAY", 0.98), decay_every=_i("DECAY_EVERY", 20000),
                         quantile_gate=bool(_i("WRITE_QUANTILE", 1)),   # WRITE_QUANTILE=0 restores the old additive controller
                         n_own=(_i("FAB_NMAX", 64) if MEM_PER_EXPERT else 1), quota=(MEM_QUOTA if MEM_PER_EXPERT else None))
    if MEM_PER_EXPERT:
        print(f"[memory] PER-EXPERT: {mem.n_own} owners x {mem.quota} entries = {mem.cap} slots, LRU by last USE "
              f"(writes partitioned by routed expert; reads global so information still mixes)")
    asm = DomainAssembler()
    if _RD is not None:                                    # part 2 of RESUME: optimizer moments, memory store, domains
        try: om.load_state_dict(_RD["opt_m"]); oe.load_state_dict(_RD["opt_e"])
        except (KeyError, ValueError) as e: print(f"[resume] optimizer state not restored ({e}) -- weights still loaded")
        _mk = _RD["mem_keys"]; _mn = _mk.size(0)
        if _mn > 0:
            _mn = min(_mn, mem.cap)
            mem.keys[:_mn] = _mk[:_mn].to(DEV); mem.tok[:_mn] = _RD["mem_tok"][:_mn].to(DEV)
            mem.src[:_mn] = _RD["mem_src"][:_mn].to(DEV); mem.pos[:_mn] = _RD["mem_pos"][:_mn].to(DEV)
            if mem.ctx_w > 0 and _RD.get("mem_ctx") is not None: mem.ctx[:_mn] = _RD["mem_ctx"][:_mn].to(DEV)
            if _RD.get("mem_use") is not None: mem.use[:_mn] = _RD["mem_use"][:_mn].to(DEV)
            if _RD.get("mem_own") is not None and mem.n_own > 1 and int(_RD.get("mem_n_own", 1)) == mem.n_own:
                # restore the partition IN PLACE (owner*quota+slot), not compacted -- compacting would reassign every
                # entry to the wrong owner block and silently destroy the per-expert structure.
                _ow = _RD["mem_own"].to(DEV); _la = _RD["mem_last"].to(DEV)
                mem.active[:] = False
                for _o in range(mem.n_own):
                    _sel = (_ow == _o).nonzero(as_tuple=True)[0][:mem.quota]
                    if _sel.numel() == 0: continue
                    _dst = torch.arange(_o * mem.quota, _o * mem.quota + _sel.numel(), device=DEV)
                    mem.keys[_dst] = _mk[_sel].to(DEV); mem.tok[_dst] = _RD["mem_tok"][_sel].to(DEV)
                    mem.src[_dst] = _RD["mem_src"][_sel].to(DEV); mem.pos[_dst] = _RD["mem_pos"][_sel].to(DEV)
                    if mem.ctx_w > 0 and _RD.get("mem_ctx") is not None: mem.ctx[_dst] = _RD["mem_ctx"][_sel].to(DEV)
                    mem.own[_dst] = _o; mem.last[_dst] = _la[_sel]; mem.active[_dst] = True
                mem.tick = int(_RD.get("mem_tick", 0))
            if _RD.get("mem_selfcon") is not None: mem.selfcon[:_mn] = _RD["mem_selfcon"][:_mn].to(DEV)
            mem.active[:_mn] = True; mem.ptr = _mn % mem.cap
        _a = _RD.get("asm")
        if _a:
            asm.cent = {int(k): v.to(DEV) for k, v in _a["cent"].items()}
            asm.size = {int(k): v for k, v in _a["size"].items()}; asm.last = {int(k): v for k, v in _a["last"].items()}
            asm.wins = {i: [] for i in asm.cent}           # sample windows are stream-local; the new stream refills them
            asm.next_id = _a["next_id"]; asm.merged = {int(k): int(v) for k, v in _a["merged"].items()}; asm.cur = -1
            # RECURRENCE MUST SURVIVE RESUME. Without this every restored domain resumes at visits=0, bornb=0 against a
            # boundary clock restarting at 0 -- so DOM_RECUR_HORIZON boundaries later the fold would swallow every
            # domain that had not happened to be re-entered twice since the resume, destroying the assembled history.
            asm.visits = {int(k): int(v) for k, v in _a.get("visits", {}).items()}
            asm.bornb = {int(k): int(v) for k, v in _a.get("bornb", {}).items()}
            asm.nb = int(_a.get("nb", 0))
            asm.rad = {int(k): (None if v is None else float(v)) for k, v in _a.get("rad", {}).items()}
            asm._radp = _a.get("radp")                     # radii re-measure at the first rekey; the pooled one carries
            for _i2 in asm.cent: asm.visits.setdefault(_i2, 0); asm.bornb.setdefault(_i2, asm.nb); asm.rad.setdefault(_i2, None)
        print(f"[RESUME] {RESUME} -> step {_resume_step} | {mem.n} memory entries | {len(asm.cent)} domains"
              + (f" | fabric {len(fab.bodies)}n" if FABRIC else "") + (f" | {world_fwd.n()} dynamics predictors" if WORLD_MODEL else "")
              + "  (encoder warmup skipped: already trained)")
    if SIG_MODE == "learned" and _RD is None:              # WARM UP the encoder first (unsupervised on the raw stream);
        wu = _i("ENC_WARMUP", 800)                         #   an undertrained encoder gives noisy (unseparated) signatures.
        def _sep_probe():                                  # mean pairwise distance of random-window encodings (global spread)
            with torch.no_grad():
                st = [random.randint(0, len(ENC_SEQ) - WIN - 1) for _ in range(64)]
                Z = enc(torch.tensor([list(ENC_SEQ[s:s + WIN]) for s in st], device=DEV))
                return float((1 - Z @ Z.t()).mean())
        # ADAPTIVE WARMUP: stop once separation PLATEAUS instead of always running the full (30k) budget -- the #1 startup
        # cost. Probe periodically; stop when the trailing relative gain < eps, with a min floor so we never underfit it.
        curve = []; _wfloor = min(_i("ENC_WARMUP_MIN", 3000), wu); _weps = _f("ENC_WARMUP_EPS", 0.015); _probe_ev = max(1, _i("ENC_WARMUP_PROBE", 500))
        _prev_sep = None; _stop = wu; _plateau = False; _smax = 0.0
        for t in range(wu):
            l = contrastive_step(enc, oe, ENC_SEQ, len(ENC_SEQ))
            if t % _probe_ev == 0 or t == wu - 1:
                _sep = _sep_probe(); curve.append((t, l if l is not None else 0.0, _sep))
                _smax = max(_smax, _sep)
                # `_sep <= _prev_sep*(1+eps)` is true when separation is FLAT and equally true when it is
                # COLLAPSING, and the stop could not tell them apart. On a single-corpus stream separation ran
                # 0.16 -> 0.05, a 69% collapse, and this reported a converged plateau and stopped -- after which
                # SHIFT_DIST never fired, the run found 0 boundaries and 1 domain, and the entire domain apparatus
                # sat inert while every report line still printed. Detect the difference.
                if t >= _wfloor and _prev_sep is not None and _sep <= _prev_sep * (1 + _weps):
                    _stop = t + 1; _plateau = True; break
                _prev_sep = _sep
        if wu:
            print("[encoder training curve] step:loss:separation -> " + "  ".join(f"{t}:{l:.2f}:{s:.2f}" for t, l, s in curve))
            # SAY WHICH ONE ACTUALLY HAPPENED. This used to claim "stopped on separation plateau" unconditionally,
            # including when it had simply run out of budget -- and setting ENC_WARMUP_MIN == ENC_WARMUP makes the
            # plateau test UNREACHABLE (`t >= _wfloor` needs t == wu, but the loop stops at wu-1), so the run that
            # paid all 30000 steps was told it had converged at 30000. A message that cannot report failure is not
            # a message. Also warn, because equal MIN and budget is the one setting that disables the whole feature.
            print(f"  (adaptive warmup: {'STOPPED EARLY at' if _plateau else 'ran the FULL budget'} {_stop}/{wu}"
                  f"{' on separation plateau' if _plateau else ' -- no plateau detected'}; floor {_wfloor}, eps {_weps})")
            if not _plateau and _wfloor >= wu:
                print(f"  !! ENC_WARMUP_MIN ({_wfloor}) >= ENC_WARMUP ({wu}) makes the plateau test unreachable -- "
                      f"the adaptive stop was OFF for this run. Lower ENC_WARMUP_MIN to enable it.")
            _sfin = curve[-1][2] if curve else 0.0
            if _smax > 0 and (_sfin < 0.7 * _smax or _sfin < 0.15):
                print(f"  !! ENCODER COLLAPSE: signature separation ended at {_sfin:.2f} against a peak of "
                      f"{_smax:.2f}. The encoder is mapping everything to nearly one point, so SHIFT_DIST "
                      f"({SHIFT_DIST}) will rarely or never fire and domain assembly will be INERT -- expect ~0 "
                      f"boundaries and 1 domain, with every downstream domain metric technically valid and "
                      f"meaningless. This is the expected failure on a HOMOGENEOUS corpus: InfoNCE has no "
                      f"cross-kind negatives, so nothing stops the representation shrinking. Widen the material, "
                      f"or use ENC_PROTO/SIG_SPACE to change what the encoder is asked to tell apart.")
    assigns = []; bounds = []; i = 0; step = _resume_step; _cur_ph = -1; PH_SNAP = []
    _CURVE = []; _VALT = {}; _CURVE_ERR = []; _BL = {}                                 # (step, process, bits/byte, was_active) + tokenised-val cache
    _last_vsz = TOK.vocab_size if USE_TOK else 256         # for the live tokenizer-growth report at each retok
    dom_exp = {}                                           # domain -> routing mass per expert (the AFFILIATION map)
    GROW_EVERY = _i("GROW_EVERY", 200); RETOK_EVERY = _i("RETOK_EVERY", 3000)
    # CADENCES BELOW THE BATCH EARLY-OUT MUST BE THRESHOLDS, NOT MODULO. Everything after the
    # `if len(_bx) < BATCH_W: step += 1; continue` accumulator only executes on FLUSH steps, which land on a fixed
    # residue mod BATCH_W -- while `step` advances on every window. `step % N == 0` then asks for a simultaneous
    # solution to two congruences that usually has none, so the block silently NEVER fires. Simulated over 200k
    # windows: at BATCH_W=1 the mint fires 999 times and re-tokenization 66 times; at BATCH_W = 2, 8, 15, 16 or 32
    # it fires ZERO times -- for every BATCH_W > 1 tested, odd ones included. That is exactly what the 4 MB
    # BATCH_W=16 run showed: "vocab 512/16384 (minting live; +0 since last retok)", a model sized for 16384 ids
    # running on the 512 the SEED passes had already produced. CKPT_EVERY sat in the same block, so a long run
    # would also never have checkpointed. Elapsed-since-last-fire is phase-independent and resume-safe.
    _fired = {"grow": step, "retok": step, "ckpt": step, "lmcurve": step}
    def _due(_k, _n):                                      # True at most once per _n steps, whatever the batch phase
        if _n <= 0 or step - _fired[_k] < _n: return False
        _fired[_k] = step; return True
    # ---- NO-COMPROMISE PERF: amortized re-key + shift-gated encoder (keep FULL drift-survival + FULL responsiveness) ----
    REKEY_AMORTIZED = bool(_i("REKEY_AMORTIZED", 1))       # spread the SAME whole-store re-encode across steps -> no periodic spike,
    _rk = {"ii": None, "cur": 0}                           #   SAME per-entry refresh rate + freshness. Nothing removed.
    # REKEY_CHUNK: do C steps' worth of re-keying in ONE call every C steps instead of a small call EVERY step.
    # Identical total work and identical per-entry refresh RATE; an entry's refresh can land up to C steps later than
    # it would have. Profiling showed the loop is bound by _model_key CALL COUNT (~1952 calls per 976 steps against
    # ~61 real LM forwards), and after batching the writes this is what remains. Default 1 = exactly the old cadence.
    REKEY_CHUNK = max(1, _i("REKEY_CHUNK", 1))
    RETOK_TAIL = bool(_i("RETOK_TAIL", 1))                 # re-tokenize only the UNCONSUMED tail at each retok (see below)
    def _rekey_amortized(chunk=1):
        if KEY_SRC != "model": return
        if _rk["ii"] is None or _rk["cur"] >= _rk["ii"].numel():        # snapshot exhausted -> take a fresh one (once per full pass)
            valid = mem.active & (~mem.is_wrong()) & (~mem.is_unverified())   # only entries that can be READ (skip re-keying dead weight)
            _rk["ii"] = valid.nonzero(as_tuple=True)[0]; _rk["cur"] = 0
            if _rk["ii"].numel() == 0: return
        per = max(1, -(-_rk["ii"].numel() // max(1, REKEY_EVERY))) * chunk   # ceil: cover the whole snapshot once per REKEY_EVERY steps
        a = _rk["cur"]; b = min(a + per, _rk["ii"].numel()); idx = _rk["ii"][a:b]
        if mem.ctx_w > 0 and idx.numel() > 0: mem.rekey(_model_key(mem.ctx[idx]), idx)
        _rk["cur"] = b
    ENC_EVERY_IDLE = _i("ENC_EVERY_IDLE", max(ENC_EVERY * 6, 12))       # shift-gated encoder: throttle when the stream is STABLE,
    ENC_SHIFT_WIN = _i("ENC_SHIFT_WIN", 400); _last_boundary = -10 ** 9  #   but snap back to ENC_EVERY on a detected boundary (full responsiveness)
    # SIG_BATCH: compute signatures for a RUN of upcoming windows in one encoder call. The batching interval is not
    # BATCH_W -- it is the span over which `enc` is PROVABLY frozen, i.e. from one contrastive_step firing to the next.
    # `enc.parameters()` are written ONLY by contrastive_step (`asm.rekey` reads it, never writes), so every window in
    # that span is encoded under exactly the parameters the sequential loop would have used. A detected boundary moves
    # `_last_boundary` and therefore the cadence, so a boundary INVALIDATES the queue -- that closes the
    # sig -> boundary -> cadence -> sig feedback loop rather than ignoring it.
    SIG_BATCH = bool(_i("SIG_BATCH", 1)); SIG_LOOK = max(1, _i("SIG_LOOK", ENC_EVERY_IDLE))
    _sigq = []                                              # pre-computed signatures for the current frozen run

    def _sig_horizon(s, L):                                 # how many steps until the NEXT encoder update, if no boundary fires
        if (s - L) < ENC_SHIFT_WIN:                         # dense phase: cadence ENC_EVERY, and never cross the dense->idle flip
            return max(1, min((s // ENC_EVERY + 1) * ENC_EVERY, L + ENC_SHIFT_WIN) - s)
        return max(1, (s // ENC_EVERY_IDLE + 1) * ENC_EVERY_IDLE - s)
    CKPT_EVERY = _i("CKPT_EVERY", 0)                       # >0: also save the checkpoint every N steps mid-run, so a long
    import bisect as _bisect                               #      run is killable/promptable and a crash never loses everything

    # SAVE_CKPT=0 MEANS OFF. Every other switch in this file is an integer flag, so `SAVE_CKPT=0` is the obvious way
    # to disable checkpointing -- but this one is a PATH, and "0" is a truthy string. `if not ck: return` never
    # fired, os.makedirs("0") ran, and the run wrote ckpt.pt/source.bin into a directory literally named `0` in the
    # repo root. It is not covered by .gitignore (source.bin is not *.pt and `0/` is not `runs/`), so it got
    # committed. Normalise the disabled spellings once, here, so all four call sites see a clean value.
    if os.environ.get("SAVE_CKPT", "").strip().lower() in ("0", "", "off", "no", "none", "false"):
        os.environ.pop("SAVE_CKPT", None)

    def _save_ckpt(src_stream, quiet=False):               # persist model+tokenizer+memory so `prompt.py` can load it
        ck = os.environ.get("SAVE_CKPT")
        if not ck: return
        os.makedirs(ck, exist_ok=True)
        if USE_TOK: TOK.save(os.environ.get("TOKENIZER_PATH", "data/dyntok.json"))
        act = mem.active
        torch.save({"model": model.state_dict(), "D": D, "V": V, "KW": KW, "KEY_SRC": KEY_SRC,
                    "model_type": MODEL_TYPE, "layers": _i("LAYERS", 4 if MODEL_TYPE=="transformer" else 1), "heads": _i("HEADS", 8), "maxlen": _i("MAXLEN", 512),
                    "use_tok": USE_TOK, "tok_path": (os.environ.get("TOKENIZER_PATH", "data/dyntok.json") if USE_TOK else None),
                    "mem_keys": mem.keys[act].cpu(), "mem_tok": mem.tok[act].cpu(), "mem_src": mem.src[act].cpu(),
                    "mem_ctx": (mem.ctx[act].cpu() if mem.ctx_w > 0 else None), "topk": mem.topk,
                    "mem_pos": mem.pos[act].cpu(),                     # -> source passages for grounded answers
                    "mem_use": mem.use[act].cpu(), "mem_selfcon": mem.selfcon[act].cpu(),   # for RESUME (retrieval fitness + wrongness)
                    "mem_own": mem.own[act].cpu(), "mem_last": mem.last[act].cpu(),         # per-expert partition + LRU clock
                    "mem_n_own": mem.n_own, "mem_quota": mem.quota, "mem_tick": mem.tick,
                    "sig_d": SIG_D, "win": WIN, "enc": enc.state_dict(),          # encoder -> gist for fabric routing
                    # WORLD MODEL: with WORLD_FEEDBACK the base LM is TRAINED with `h += world_proj(forecast)`. Omitting
                    # it from the checkpoint made generation run a DIFFERENT network than training -> the coherence test
                    # would have been invalid. Saved with its grown population size so it reconstructs exactly.
                    "world_cfg": ({"lat": WLAT, "hid": WHID, "n": world_fwd.n(), "nmax": world_fwd.nmax,
                                   "route": world_fwd.route_dim, "feedback": world_proj is not None} if WORLD_MODEL else None),
                    "world_enc": (world_enc.state_dict() if WORLD_MODEL else None),
                    "world_fwd": (world_fwd.state_dict() if WORLD_MODEL else None),
                    "world_proj": (world_proj.state_dict() if world_proj is not None else None),
                    # RESUME state: optimizer moments + step + domain centroids. Without these a crashed multi-day run
                    # restarts from zero even though a checkpoint exists.
                    "step": step, "opt_m": om.state_dict(), "opt_e": oe.state_dict(),
                    "asm": {"cent": {int(k): v.cpu() for k, v in asm.cent.items()}, "size": dict(asm.size),
                            "last": dict(asm.last), "next_id": asm.next_id, "merged": dict(asm.merged), "cur": asm.cur,
                            "visits": dict(asm.visits), "bornb": dict(asm.bornb), "nb": asm.nb,
                            "rad": dict(asm.rad), "radp": asm._radp},
                    "experts": (experts.state_dict() if EXPERTS else None),
                    "fab": (fab.state_dict() if FABRIC else None),
                    "fab_cfg": ({"n": len(fab.bodies), "dk": _i("FAB_DK", 32), "alpha": _f("FAB_ALPHA", 0.5),
                                 "max_steps": _i("FAB_STEPS", 4), "hid_mult": _f("FAB_HID_MULT", 2),
                                 "min_steps": _i("FAB_MIN_STEPS", 0), "norm_only": bool(_i("FAB_NORM_ONLY", 0)),
                                 "society": SOCIETY, "grounded": fab.grounded, "route_t": fab.route_t,
                                 "route_learn": fab.route_learn, "ens_k": ENS_K} if FABRIC else None)},
                   f"{ck}/ckpt.pt.tmp")
        if os.path.exists(f"{ck}/ckpt.pt"):                       # keep ONE previous generation: a corrupt or
            try: os.replace(f"{ck}/ckpt.pt", f"{ck}/ckpt.prev.pt")   # interrupted write is then always recoverable
            except OSError: pass
        os.replace(f"{ck}/ckpt.pt.tmp", f"{ck}/ckpt.pt")          # ATOMIC: a kill mid-save used to leave a truncated
        #   ckpt.pt and destroy the only copy, together with the tokenizer that decodes it.
        with open(f"{ck}/source.bin", "wb") as _srcf:             # the corpus text retrieval points INTO
            _srcf.write(bytes(byte_stream) if ONLINE else (bytes(src_stream) if not USE_TOK else TOK.decode(src_stream).encode("utf-8", "replace")))
        if not quiet:
            print(f"[saved checkpoint -> {ck}/ckpt.pt | {int(act.sum())} memory entries{', fabric ' + str(len(fab.bodies)) + 'n' if FABRIC else ''} | prompt it: python3 prompt.py CKPT={ck}]")

    import signal as _signal                               # CHECKPOINT-ON-DEMAND: `kill -USR1 <pid>` sets a flag and the
    _ckpt_req = {"on": False}                              #   loop saves at the next SAFE point (never torch.save inside a
    def _on_usr1(*_): _ckpt_req["on"] = True              #   handler -- reentrancy). Pause+dump without killing the run.
    try: _signal.signal(_signal.SIGUSR1, _on_usr1)
    except (ValueError, OSError): pass                     # not the main thread / unsupported platform -> silently skip
    if os.environ.get("SAVE_CKPT"):
        print(f"[pid {os.getpid()}] checkpoint-on-demand: kill -USR1 {os.getpid()}  ->  saves to {os.environ['SAVE_CKPT']} at the next step"
              + (f" (auto every {CKPT_EVERY} steps)" if CKPT_EVERY else " (no periodic auto-save; set CKPT_EVERY to enable)"))
    EPOCHS = max(1, _i("EPOCHS", 1)); _epoch = 0            # multi-EPOCH: reset to the stream start EPOCHS times (clean passes,
    # ---- STARTUP GUARDS: each of these silently produced a run that did NOT test what it claimed to ----
    _warn = []
    if EPOCHS > 1 and not DISK_STREAM:
        _warn.append(f"EPOCHS={EPOCHS} with DISK_STREAM=0 -> every epoch is a BYTE-IDENTICAL REPLAY "
                     f"(_resample runs only under DISK_STREAM). Set DISK_STREAM=1 for fresh data per epoch.")
    if _i("CORPUS_CAP", 2000000) <= 2000000 and DATA_MODE == "real":
        _warn.append(f"CORPUS_CAP={_i('CORPUS_CAP', 2000000)} bytes -> each domain is capped at ~2MB regardless of how "
                     f"much data is on disk. A multi-day run would see 2MB of text. Set CORPUS_CAP to the real size.")
    if os.environ.get("SAVE_CKPT") and not CKPT_EVERY:
        _warn.append("SAVE_CKPT set but CKPT_EVERY=0 -> the ONLY save is at the very end (plus SIGUSR1). "
                     "A crash loses the whole run. Set CKPT_EVERY.")
    if not PHASED and NP > 1:
        _warn.append("PHASED=0 -> the stream is STATIONARY: every process is present throughout, in i.i.d. "
                     "proportion. Nothing ever has to be retained across a distribution shift, so this run does "
                     "NOT test continual learning -- it is ordinary training. The RETENTION and NON-STATIONARY "
                     "sections below will look good for that reason alone. Use PHASED=1 (the default) to test it.")
    if EXPERTS and FABRIC:
        _warn.append("EXPERTS=1 AND FABRIC=1 -> the expert bank is a NO-OP. The forward pass is an elif chain "
                     "(FABRIC wins), so the adapters never receive gradient, yet the end-of-run report still prints "
                     "expert counts. Use one or the other.")
    # SEGMENT LENGTH vs ANALYSIS WINDOW -- the guard that would have saved the most wasted tuning in this project.
    # Domain assembly is a SEQUENTIAL problem: detect a shift, then settle into the new domain. Detection alone costs
    # SUSTAIN windows. If a splice segment is not many windows long there is no settled interior left to assign from,
    # and purity/homogeneity measure the transition rather than the domain. SEG_MIN/SEG_MAX (700/1800 bytes, mean
    # ~1250) were set when WIN was ~96 BYTES -- 13 windows per segment, a sane regime. At WIN=256 TOKENS the window
    # is ~490 bytes, so a segment is 2.6 windows, SUSTAIN=2 consumes two of them, and under one clean window per
    # segment remains. That is not a domain stream, it is a transition stream, and no assign rule fixes it.
    _bpt = (sum(TOK.bytes_per_id[:TOK.vocab_size]) / max(1, TOK.vocab_size)) if (USE_TOK and TOK is not None) else 1.0
    # SIGNATURE WINDOW WIDTH vs LOOP STRIDE. In byte space the width is a byte count while the loop advances WIN
    # TOKENS, so the encoder sees width/(WIN*bytes_per_token) of the stream -- and that fraction SHRINKS as the
    # tokenizer compresses better. Report it, because it was never a decision anyone made.
    _sigw = SIG_WIN if SIG_WIN > 0 else WIN
    if ONLINE and SIG_SPACE == "bytes":
        _stride_b = WIN * max(1.0, _bpt)
        _cov = min(1.0, _sigw / _stride_b)
        print(f"[signature] space=bytes | window {_sigw} B | loop stride {_stride_b:.0f} B ({WIN} tok x {_bpt:.2f}) "
              f"-> covers {_cov*100:.0f}% of the stream"
              + ("" if _cov >= 0.99 else f"; SIG_WIN={int(_stride_b)} would cover it all"))
    elif SIG_SPACE == "tokens":
        print(f"[signature] space=TOKENS | window {WIN} tok (~{WIN*_bpt:.0f} B) | encoder vocab {ENC_V}, live {TOK.vocab_size if USE_TOK else 256}"
              f" | new ids warm-started from their constituents; centroids re-encoded every REKEY_EVERY={REKEY_EVERY}")
    _winb = WIN * max(1.0, _bpt); _segb = 0.5 * (_i("SEG_MIN", 700) + _i("SEG_MAX", 1800))
    if DATA_MODE == "real" and _segb / _winb < 8:
        _warn.append(f"SEGMENT/WINDOW = {_segb:.0f}B / {_winb:.0f}B = {_segb/_winb:.1f} windows per splice segment "
                     f"(SUSTAIN={SUSTAIN} of those are spent DETECTING the boundary, leaving "
                     f"{max(0.0, _segb/_winb - SUSTAIN):.1f}). Clustering scores here describe the TRANSITIONS, not "
                     f"the domains. Raise SEG_MIN/SEG_MAX (>= {int(8*_winb)}/{int(20*_winb)}) or lower WIN.")
    if _warn:
        print("\n".join(["!! CONFIG WARNING: " + w for w in _warn]) + "\n")
    # LIVE RATE METER: the [probe] extrapolates from a SYNTHETIC LM-only step, so its ETA has always been optimistic --
    # this measures the ACTUAL loop and re-projects from observed throughput, so the ETA self-corrects as the run goes.
    import time as _time
    RATE_EVERY = _i("RATE_EVERY", 2000); _t_start = _time.time(); _t_mark = _t_start; _s_mark = step
    _AC = None                                             # autocast context for the LM step (None = plain fp32)
    if AMP in ("bf16", "fp16") and DEV == "cuda":
        _AC = torch.autocast("cuda", dtype=(torch.bfloat16 if AMP == "bf16" else torch.float16))
        print(f"[precision] LM step in {AMP} autocast (memory keys stay fp32 -- retrieval is a dot-product over "
              f"normalized keys and is the one place reduced precision would change behaviour, not just speed)")
    elif AMP != "off":
        print(f"[precision] AMP={AMP} ignored on device {DEV}")
    # PER-COMPONENT PROFILER (PROFILE=1): attributes wall-clock to each part of the step, so tuning targets what is
    # actually slow instead of what seems slow. Off by default -- on CUDA it must synchronize to attribute time, which
    # itself costs throughput, so it is a diagnostic mode, not the run mode.
    PROFILE = bool(_i("PROFILE", 0)); _prof = {}
    class _Null:
        def __enter__(s): return s
        def __exit__(s, *a): return False
    _NULL = _Null()
    class _Timer:
        __slots__ = ("k", "t")
        def __init__(s, k): s.k = k
        def __enter__(s):
            if DEV == "cuda": torch.cuda.synchronize()
            s.t = _time.time(); return s
        def __exit__(s, *a):
            if DEV == "cuda": torch.cuda.synchronize()
            _prof[s.k] = _prof.get(s.k, 0.0) + (_time.time() - s.t); return False
    def _T(k): return _Timer(k) if PROFILE else _NULL      # zero cost when PROFILE=0
    def _t0():                                             # start/stop form, for spans too long to re-indent into a `with`
        if not PROFILE: return None
        if DEV == "cuda": torch.cuda.synchronize()
        return _time.time()
    def _t1(k, t):
        if t is None: return
        if DEV == "cuda": torch.cuda.synchronize()
        _prof[k] = _prof.get(k, 0.0) + (_time.time() - t)
    _total_steps = EPOCHS * (len(stream) // WIN)
    _bpw = WIN * (len(byte_stream) / max(1, len(stream))) if ONLINE else WIN     # BYTES of corpus consumed per step
    while True:                                             #   memory-efficient -- build the stream ONCE, iterate; step keeps counting)
        # ---- PER-PROCESS LEARNING CURVE: the other half of continual learning. -----------------------------------
        # Retention says whether old material survives. This says how FAST new material is picked up, and it is the
        # half nothing measured: a process ENTERS at a phase boundary and we never asked how many steps it took to
        # model it, nor watched its cost climb again once it FADED. Held-out text per process, on the rate cadence,
        # so the cost is one small eval every RATE_EVERY steps rather than anything in the hot path.
        if RATE_EVERY and step % RATE_EVERY == 0 and step > _s_mark and VALC:
            try:
                model.eval()
                for _p in range(len(VALC)):
                    _v = _VALT.get(_p)
                    if _v is None:
                        _v = TOK.segment(VALC[_p], count=False) if USE_TOK else list(VALC[_p])
                        _VALT[_p] = _v
                    if len(_v) < WIN + 2: continue
                    _rs = random.Random(1234 + _p)          # SAME windows every time -> the curve is comparable
                    _st = [_rs.randint(0, len(_v) - WIN - 2) for _ in range(16)]
                    with torch.no_grad():
                        _X = torch.tensor([_v[a:a + WIN] for a in _st], device=DEV)
                        _Y = torch.tensor([_v[a + 1:a + WIN + 1] for a in _st], device=DEV)
                        _lg = fab_logits(model, fab if FABRIC else None, model.encode(_X))
                        _pp = F.softmax(_lg, -1).gather(-1, _Y.unsqueeze(-1)).squeeze(-1)
                    # nbytes() is unusable mid-run: it reads BLEN, which is None until the final re-tokenization
                    # whenever TOK_ONLINE is set. Build the byte denominator from the LIVE tokenizer, cached per
                    # vocab size since the vocabulary grows underneath us.
                    if USE_TOK:
                        _bl = _BL.get(TOK.vocab_size)
                        if _bl is None:
                            _bl = torch.tensor(TOK.bytes_per_id[:TOK.vocab_size], dtype=torch.float, device=DEV)
                            _BL.clear(); _BL[TOK.vocab_size] = _bl
                        _den = float(_bl[_Y.clamp(max=TOK.vocab_size - 1)].sum())
                    else:
                        _den = float(_Y.numel())
                    _CURVE.append((step, _p, -(torch.log(_pp.clamp_min(1e-9)).sum().item()) / math.log(2) / max(1.0, _den),
                                   _p in (PHASE_SCHED[min(_cur_ph, len(PHASE_SCHED) - 1)] if (PHASED and _cur_ph >= 0)
                                          else list(range(NP)))))
                model.train()
            except Exception as _e:                        # never swallow: a silent except here hid the whole
                model.train()                              #   learning curve, printing nothing at all
                if not _CURVE_ERR:
                    _CURVE_ERR.append(1); print(f"  [learning-curve sample failed: {type(_e).__name__}: {_e}]")
        if RATE_EVERY and step % RATE_EVERY == 0 and step > _s_mark:
            _now = _time.time(); _rate = (step - _s_mark) / max(1e-9, _now - _t_mark)      # steps/sec over the last window
            _left = max(0, _total_steps - (step - _resume_step))
            print(f"  [rate @ {step}] {_rate*60:.0f} steps/min | {_rate*_bpw/1e3:.1f} kB/s of corpus | "
                  f"elapsed {(_now-_t_start)/60:.0f} min | ~{_left/max(1e-9,_rate)/3600:.1f} h left ({_left} steps) | "
                  f"{_rate*_bpw*86400/1e9:.2f} GB of text per DAY at this rate | "
                  # DOMAIN FORMATION, LIVE: on a single-domain corpus the byte-level signature may never shift enough
                  # to trigger a boundary, which would leave domain assembly / provenance / per-domain unlearning
                  # untested. Surfacing it here turns a multi-day unknown into an hour-one signal.
                  f"{len(asm.cent)} domains / {len(bounds)} boundaries")
            if PROFILE and _prof:
                _tot = sum(_prof.values())
                _br = "  ".join(f"{k} {v/max(1e-9,_tot)*100:.0f}%" for k, v in sorted(_prof.items(), key=lambda kv: -kv[1]))
                print(f"    [profile] {_br}   ({_tot/max(1e-9,_now-_t_mark)*100:.0f}% of this window attributed)")
                _prof.clear()
            _t_mark = _now; _s_mark = step
        if i + WIN + 1 >= len(stream):
            _epoch += 1
            if _epoch >= EPOCHS: break
            if DISK_STREAM:                                # draw FRESH data from the larger-than-RAM corpus each epoch
                stream, byte_stream, byte_labels, tok_bs, labels, ENC_SEQ, true_sw = _resample()
                set_enc_tensor(ENC_SEQ); _sigq = []          # stream replaced -> queued lookahead windows are stale
                if FABRIC and fabgrow is not None: fabgrow.note_shift(step)
            i = 0; print(f"  [epoch {_epoch + 1}/{EPOCHS}{' (fresh sample)' if DISK_STREAM else ''} @ step {step} | vocab {TOK.vocab_size if USE_TOK else 256} | mem {mem.n} | domains {len(asm.cent)}]")
            continue
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
        # SIGNATURE window. Bytes when online (tokenization-invariant -- see SIG_SPACE), else the token window.
        # _sigw is the byte WIDTH; the loop STRIDE is WIN tokens, so width < stride means the encoder skips text.
        ew = list(byte_stream[bpos:bpos + _sigw]) if (ONLINE and SIG_SPACE == "bytes") else list(w[:-1])
        _enc_cad = ENC_EVERY if (step - _last_boundary) < ENC_SHIFT_WIN else ENC_EVERY_IDLE   # shift-gated: dense near a boundary, throttled when stable
        if SIG_MODE == "learned" and step % _enc_cad == 0:
            with _T("encoder(contrastive)"): contrastive_step(enc, oe, ENC_SEQ, (i if SIG_SPACE == "tokens" else bpos), asm)   # `seen` must be
            #   an index INTO ENC_SEQ: bpos counts bytes, i counts tokens, and ENC_SEQ is whichever SIG_SPACE says
        with _T("sig_of"):
            if not (SIG_BATCH and SIG_MODE == "learned"):
                sig = sig_of(ew, enc)
            else:
                if not _sigq:                               # refill: one encoder call for the whole frozen run
                    _H = min(_sig_horizon(step, _last_boundary), SIG_LOOK, (len(stream) - 1 - i) // WIN)
                    if ONLINE: _H = min(_H, RETOK_EVERY - (step - _fired["retok"]))   # stream is rebuilt at retok
                    #   -> stop the lookahead there. Must track the SAME threshold retok now fires on: reading a
                    #   modulo here while retok fires on elapsed-since-last would queue windows built from a stream
                    #   that gets rebuilt underneath them.
                    _H = max(1, _H)
                    _ws = [ew]
                    for _k in range(1, _H):                 # the SAME byte windows the later steps would build
                        _j = i + _k * WIN
                        if ONLINE and SIG_SPACE == "bytes":
                            if _j >= len(tok_bs): break
                            _b0 = tok_bs[_j]; _w = list(byte_stream[_b0:_b0 + _sigw])   # _sigw, not WIN: the
                        else:                                                            #   lookahead must build the
                            _w = list(stream[_j:_j + WIN])                               #   SAME width as `ew`, or
                        if len(_w) != (_sigw if (ONLINE and SIG_SPACE == "bytes") else WIN): break   # the batch is ragged
                        _ws.append(_w)
                    _sigq = list(sig_of_batch(_ws, enc)) if len(_ws) > 1 else [sig_of(ew, enc)]
                sig = _sigq.pop(0)
        if SELF_ORG:
            with _T("domain assembly"): did, boundary = asm.update(sig, ew, step)
        else:
            did, boundary = 0, False                        # domains DISABLED: one bucket, no provenance/management
        if boundary:
            bounds.append(bpos); _last_boundary = step      # a real distribution shift -> re-densify encoder updates
            _sigq = []                                      # cadence just changed -> queued signatures are no longer valid
        if step % REKEY_EVERY == 0 and step > 0:
            if SIG_MODE == "learned" and SELF_ORG: asm.rekey(enc)                                        # RE-KEY domain centroids
            if not REKEY_AMORTIZED: rekey_memory(mem)                                                    # full re-encode (spike) -- fallback path
        if REKEY_AMORTIZED and step > 0 and step % REKEY_CHUNK == 0:
            with _T("rekey(amortized)"): _rekey_amortized(REKEY_CHUNK)                                  # no-compromise: same work, spread out, no stall
        if SELF_ORG and MANAGE_ON and step % DOM_MANAGE_EVERY == 0 and step > 0:                    # MANAGE the domain set
            m, c = asm.manage(step, mem, MANAGE_MERGE, MANAGE_MIN, MANAGE_STALE)                     #   merge redundant + cull + fold
            if m or c: print(f"  [manage @ {step}] merged {m} culled {c} -> {len(asm.cent)} live domains (memory reassigned/pruned)")
        if EXPERTS and MANAGE_ON and step % MANAGE_EVERY == 0 and step > 0: router.manage(step)   # experts: create/replicate/cull (their own selective force)
        if WORLD_GROW and step % MANAGE_EVERY == 0 and step > 0:                                    # world-model SELECTION (same cadence as experts/domains)
            if world_fwd.n() < world_fwd.nmax and _wl_ema is not None and _winv > 0.9 * _wl_ema and step - _wl_lastgrow > 4 * MANAGE_EVERY:
                _newp = world_fwd.grow(_wz.reshape(-1, WLAT).detach())   # plateau (no improvement) -> add a dynamics predictor, cloned from the fittest
                if _newp: om.add_param_group({"params": _newp}); _wl_lastgrow = step; print(f"  [world-model @ {step}] plateau -> grew to {world_fwd.n()} dynamics predictors")
            _wcull = world_fwd.soft_cull()
            if _wcull: print(f"  [world-model @ {step}] soft-culled {_wcull} unused -> {int(world_fwd.alive[:world_fwd.n()].sum())} live predictors")
        _bx.append(list(w[:-1])); _by.append(list(w[1:])); _bg.append(sig); _bd.append(did); _bp.append((bpos, i))
        # PER-WINDOW BOOKKEEPING GOES ABOVE THE EARLY-OUT. Both of these describe THIS window, not the batch, and
        # both used to sit below the accumulator -- so at BATCH_W=16 they saw 6.2% of the stream. `assigns` is what
        # every clustering metric is computed from, which means the 4 MB run's purity/homogeneity/completeness/
        # V-measure and its whole RECURRENCE histogram were computed from one window in sixteen (and recurrence in
        # particular is destroyed by subsampling, since it counts maximal consecutive runs). The tokenizer pair
        # tally was under-counted by the same factor, on top of never being acted on.
        assigns.append((bpos, did, byte_labels[min(bpos, len(byte_labels) - 1)] if ONLINE else labels[i]))
        # PER-DOMAIN TOKEN COUNTS -- the one route by which a domain could pay for itself in PREDICTION.
        # Conditioning RETRIEVAL on the domain is already measured dead: restricting to the query's own domain beats
        # a foreign domain by no more than a shuffled-provenance null, i.e. the label carries nothing the memory keys
        # do not. A prior is a different claim -- not "which stored entry is similar" but "in this kind of text,
        # which tokens are likely at all" -- and the anchors say a global order-0 model is worth something (3.86 b/B
        # on English), so a SHARPER per-domain one is worth something more, IF the domains are real.
        if DOM_PRIOR > 0.0:
            _c = asm.tokc.get(did)
            if _c is None: _c = asm.tokc[did] = torch.zeros(V, device=DEV)
            _c.index_add_(0, torch.tensor(w[:-1], device=DEV), torch.ones(len(w) - 1, device=DEV))
        if ONLINE:
            for a, b in zip(w[:-1], w[1:]): TOK.pair[(a, b)] += 1   # ONGOING minting: tally THIS window's pairs
        if len(_bx) < BATCH_W:                              # accumulate a batch of windows first
            i += WIN; step += 1; continue
        model.train()
        with _T("batch->tensor"):
            x = torch.tensor(_bx, device=DEV); y = torch.tensor(_by, device=DEV)   # (BATCH_W, WIN)
            sigb = torch.stack(_bg)
        _plm = _t0()
        if _AC is not None: _AC.__enter__()                     # autocast the LM step (entered/exited explicitly rather
        #   than as a `with` block purely to avoid re-indenting the whole step); backward runs OUTSIDE it, as recommended.
        _sl = router.route(sig, step) if EXPERTS else -1        # route by SIGNATURE to the expert population (coarser than domains)
        if EXPERTS and _sl >= 0: route_at[bpos:bpos + WIN] = _sl   # remember WHICH expert trained on this span
        h = model.encode(x)                                      # includes the world-model feedback when enabled (wrapped above)
        _wz = world_enc(model.emb(x)) if WORLD_MODEL else None   # world latent per position (also used by the world loss)
        if FABRIC and SOCIETY:
            # SPARSE: compute only the experts whose outputs are actually consumed below. The dense blend that used
            # to be assigned to h here was never read -- the logits come from _O -- so it was pure waste.
            _w, _O, _oid = fab.society(h, sigb, _fab_nov.expand(x.size(0)), k=max(ENS_K, IND_K))
            _dep = h.new_zeros(()); _bal = fab_bal(_w)
            _wd = _w[0].detach()                           # which experts serve THIS domain, and how much. Kept ON DEVICE:
            #   `.cpu()` here forced a full GPU->CPU synchronization EVERY step for a number that is only read once, in
            #   the end-of-run affiliation report. Accumulate on device; move to host when reporting.
            if did in dom_exp and dom_exp[did].numel() == _wd.numel(): dom_exp[did] += _wd
            else: dom_exp[did] = _wd.clone()
        elif FABRIC:
            h, _dep, _mass, _bal = fab(h, sigb, _fab_nov.expand(x.size(0)))
        elif _sl >= 0:
            h = experts.one(h, _sl)
        if FABRIC and SOCIETY:                             # ENSEMBLE the experts' OUTPUTS (not their hidden states)
            _ki = torch.arange(min(ENS_K, _O.size(1)), device=_O.device)   # _O is ALREADY the top-k, in rank order
            _wk = _w[:, _oid[_ki]].mean(0); _wk = _wk / _wk.sum().clamp_min(1e-9)
            _hd = {}                                       # cache: ENS_K and IND_K overlap, so share the head passes
            lg = None
            for _q, _j in enumerate(_ki.tolist()):
                _hd[_j] = model.head(fab.norm(_O[:, _j]))
                lg = _hd[_j] * _wk[_q] if lg is None else lg + _hd[_j] * _wk[_q]
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
            for _j in range(min(IND_K, _O.size(1))):          #   (weighted by its routing mass) -- makes the population
                _lj = _hd.get(_j)                             #   an ENSEMBLE, which survives member removal, rather than
                if _lj is None: _lj = model.head(fab.norm(_O[:, _j]))   #   a DECOMPOSITION, which does not
                #   `.detach()` instead of `float()`: numerically identical (both stop the gradient) but stays on device,
                #   where `float()` forced a GPU->CPU sync per expert per step.
                tot = tot + IND_W * _w[:, _oid[_j]].mean().detach() * F.cross_entropy(_lj.reshape(-1, V), y.reshape(-1))
        if recon is not None and RECON_W > 0:                    # VERIFICATION: train the Reconstructor on GENUINE (key, token)
            tot = tot + RECON_W * recon_loss(recon, mem_key(x), y.reshape(-1))   # guard RECON_W>0: skips a redundant key-encode
        #   that was computed then multiplied by 0.0 on the default VERIFY=recon path (workflow finding)
        if WORLD_MODEL:                                          # WORLD MODEL: predict how the OBSERVED world evolves in latent space
            # _wz was computed above (once) from observation embeddings -- NOT the GRU state (world, not self)
            _zt = _wz[:, :-WORLD_K].reshape(-1, WLAT); _zn = _wz[:, WORLD_K:].reshape(-1, WLAT)
            _wv, _wc = _var_cov(_wz.reshape(-1, WLAT))           # anti-collapse (variance + decorrelation)
            _wpl, _, _winv = pop_loss(world_fwd, _zt, _zn)       # routed POPULATION forward-prediction + load-balance
            tot = tot + WORLD_W * _wpl + WORLD_VAR * (_wv + 0.04 * _wc)   # anti-collapse at FULL strength (was under-weighted -> collapse)
            if WORLD_GROW:                                       # selection: GROW on plateau, SOFT-CULL the unused (like experts)
                _wl_ema = _winv if _wl_ema is None else 0.98 * _wl_ema + 0.02 * _winv
        if _AC is not None: _AC.__exit__(None, None, None)
        (tot / ACCUM).backward()                                 # gradient accumulation over ACCUM windows
        if (step + 1) % ACCUM == 0: om.step(); om.zero_grad()
        _t1("lm fwd+bwd (incl. fabric/world)", _plm)
        _lf = float(loss.detach())                               # ONE host sync per step (was two: the curve and the
        _lm_run.append(_lf)                                      #   plateau detector each pulled the same scalar back)
        if _due("lmcurve", max(1, (STREAM_LEN // WIN) // 8)) and _lm_run:
            _lm_curve.append((step, sum(_lm_run[-2000:]) / len(_lm_run[-2000:]))); _lm_run = _lm_run[-2000:]
        if FABRIC and not fab.norm_only:
            _nb = fabgrow.step(_lf, step)                       # 0, or HOW MANY to grow (burst on an unexpected regression)
            _nb = min(_nb, FAB_NMAX - len(fab.bodies))
            for _g in range(max(0, _nb)):                       # each newborn is keyed at the CURRENT signature, so a
                om.add_param_group({"params": fab.grow(sig[None, :] if SOCIETY else None)})   # burst owns this region
            if _nb > 0:
                print(f"  [fabric @ {step}] {fabgrow.why} -> grew {_nb} -> {len(fab.bodies)}/{FAB_NMAX} experts")
        _pmem = _t0()
        with torch.no_grad():
            pm = F.softmax(lg.detach(), -1)                    # reuse the expert-routed logits for the write-gate surprise
            surprise = 1 - pm.gather(-1, y.unsqueeze(-1)).squeeze(-1)
            if FABRIC: _fab_nov = surprise.mean()               # last step's surprise biases the next routing query
            #   kept as a 0-dim DEVICE tensor: it is consumed next step by torch.full/expand, so `float()` bought
            #   nothing but a per-step synchronization.
            # KEY-BEHIND-THE-GATE: `mem_key(x)` used to encode a key for EVERY position -- (BATCH_W*WIN, KW) through the
            # LM, i.e. KW times MORE token-positions than the main forward, every step -- and then `write` discarded the
            # ~88% that fail the surprise gate. Encoding only the survivors is exactly equivalent (row-independent
            # encoder, identical gate/controller/entries) and removes the step's single largest cost. KEY_PREGATE=0
            # restores the old order for A/B verification.
            def _posv(_b, _n):
                # TRUE byte position PER TOKEN. This used to be arange(bpos, bpos+WIN), which walks one BYTE per
                # TOKEN -- but under the online tokenizer a token averages ~1.85 bytes, so by the end of a WIN=256
                # window the recorded provenance drifted ~200+ bytes while prompt.py's _recall reads only a 220-byte
                # span around it. Every grounded passage lookup was pointing at the wrong text.
                _bp0, _it = _bp[_b]
                if not ONLINE: return torch.arange(_bp0, _bp0 + _n, device=DEV)
                _sl = tok_bs[_it:_it + _n]
                if len(_sl) < _n: _sl = _sl + [_sl[-1] if _sl else _bp0] * (_n - len(_sl))
                return torch.tensor(_sl, device=DEV, dtype=torch.long)
            _C = mem_ctx(x); _n1 = x.size(1)
            _pre = KEY_PREGATE and KEY_SRC == "model" and _C is not None
            if _pre and KEY_BATCH:                          # ONE key encode for the whole BATCH_W batch instead of
                # OWNER = the argmax-routed expert for this batch. Writes are compartmentalized per expert (each gets
                # its own quota, evicted by LRU); READS stay global, so knowledge is owned but not walled off.
                _own = None if not (FABRIC and SOCIETY and MEM_PER_EXPERT) else \
                    [int(_w[min(_b, _w.size(0) - 1)].argmax()) for _b in range(x.size(0))]
                mem.write_batch([(y[_b], _bd[_b], surprise[_b],   # BATCH_W separate tiny encodes -- the measured
                                  _C[_b * _n1:(_b + 1) * _n1],    # bottleneck was CALL COUNT, not FLOPs
                                  _posv(_b, _n1))
                                 for _b in range(x.size(0))], _model_key, owners=_own)
            else:
                _K = None if _pre else mem_key(x)
                for _b in range(x.size(0)):                 # per-window: each carries its OWN domain + source position
                    _cb = None if _C is None else _C[_b * _n1:(_b + 1) * _n1]
                    mem.write(None if _pre else _K[_b * _n1:(_b + 1) * _n1], y[_b], src=_bd[_b], surprise=surprise[_b],
                              ctx=_cb, key_fn=(_model_key if _pre else None),
                              pos=_posv(_b, _n1))
        _t1("memory key+write", _pmem)
        _ptok = _t0()
        if ONLINE:                                         # ONGOING minting: mint from the tally accumulated above
            if _due("grow", GROW_EVERY):
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
                            if SIG_SPACE == "tokens" and nid < enc.emb.num_embeddings:
                                # The signature encoder needs this MORE than the LM does: a domain centroid is a mean
                                # of encodings, so one freshly-random token id inside a window perturbs every
                                # signature that contains it, and the assembler reads those as a domain shift.
                                enc.emb.weight[nid] = 0.5 * (enc.emb.weight[a] + enc.emb.weight[b])
        _t1("tokenizer (mint/tally)", _ptok)
        _bx = []; _by = []; _bg = []; _bd = []; _bp = []
        i += WIN; step += 1
        if (CKPT_EVERY and _due("ckpt", CKPT_EVERY)) or _ckpt_req["on"]:   # periodic OR on-demand (kill -USR1) save
            _why = "SIGUSR1" if _ckpt_req["on"] else f"every {CKPT_EVERY}"; _ckpt_req["on"] = False
            _save_ckpt(stream, quiet=True); print(f"  [checkpoint @ {step} ({_why}) -> {os.environ.get('SAVE_CKPT')}]"); model.train()
        if ONLINE and _due("retok", RETOK_EVERY):          # refresh the token stream with the grown vocab; remap position by byte
            cur_byte = tok_bs[i] if i < len(tok_bs) else len(byte_stream)
            if RETOK_TAIL:
                # TAIL-ONLY RETOK: re-segment just the UNCONSUMED remainder. The old code re-tokenized the whole
                # byte_stream every RETOK_EVERY steps, so the cost scaled with STREAM_LEN and taxed throughput ~x0.77
                # at a 10MB stream and ~x0.25 at 100MB -- for work that is pure waste, since the consumed prefix is
                # never read again this epoch. Safe because DynamicTokenizer minting is APPEND-ONLY: existing ids keep
                # their meaning, so a stream whose prefix uses the older vocab still decodes correctly (which is what
                # _save_ckpt's source.bin needs). `i` is unchanged because the prefix is preserved verbatim.
                _ti, _tb, _tl = _retok(byte_stream, byte_labels, cur_byte)
                stream = stream[:i] + _ti; tok_bs = tok_bs[:i] + _tb; labels = labels[:i] + _tl
            else:
                stream, tok_bs, labels = _retok(byte_stream, byte_labels); i = _bisect.bisect_left(tok_bs, cur_byte)
            _sigq = []                                       # re-tokenized -> window boundaries moved, queue is stale
            if SIG_SPACE == "tokens":                        # the encoder reads the TOKEN stream, which was just rebuilt
                ENC_SEQ = stream; set_enc_tensor(ENC_SEQ)    #   -> re-point it, or it trains on a stale segmentation
            if FABRIC and fabgrow is not None: fabgrow.note_shift(step)   # the loss jump after a retok is OURS, not a shift
            print(f"  [tokenizer @ {step}] vocab {TOK.vocab_size}/{TOK.vmax} (minting live; +{TOK.vocab_size - _last_vsz} since last retok)")
            _last_vsz = TOK.vocab_size

    if bool(_i("BENCH", 0)):                               # THROUGHPUT BENCH: stop after the training loop. The eval
        _el = _time.time() - _t_start                      #   battery (final re-tokenization, memorization check,
        _sr = (step - _resume_step) / max(1e-9, _el)       #   generation, unlearn tests) is a large fixed cost that
        _np = sum(p.numel() for p in model.parameters()) + (sum(p.numel() for p in fab.parameters()) if FABRIC else 0)
        print(f"[BENCH] {step - _resume_step} steps in {_el/60:.2f} min = {_sr*60:.0f} steps/min | "   # would swamp a short
              f"{_sr*_bpw/1e3:.1f} kB/s | {_sr*_bpw*86400/1e9:.3f} GB/day | {_np/1e6:.1f}M params"     # timing run.
              + (f" | peak GPU mem {torch.cuda.max_memory_allocated()/2**30:.2f} GiB" if DEV == "cuda" else ""))
        if PROFILE and _prof:
            _tt = sum(_prof.values())
            print("[BENCH profile] " + "  ".join(f"{k} {v/max(1e-9,_tt)*100:.0f}%" for k, v in sorted(_prof.items(), key=lambda kv: -kv[1])))
        return
    if ONLINE:                                             # freeze + final tokenization for eval + persist the grown vocab
        stream, tok_bs, labels = _retok(byte_stream, byte_labels)
        BLEN = torch.tensor(TOK.bytes_per_id, dtype=torch.float, device=DEV)
        TOK.save(os.environ.get("TOKENIZER_PATH", "data/dyntok.json"))
        print(f"[tokenizer] ONLINE: minted throughout -> grew 256 -> {TOK.vocab_size} during training; final re-tokenization for eval")

    _save_ckpt(stream)                                               # final save (also runs mid-run if CKPT_EVERY>0)

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
            _src = CORP[_p][max(0, SEG_LEN[_p] - len(VALC[_p])):SEG_LEN[_p]]   # tail of the TRAIN region (disk: CORP still holds val, so bound by SEG_LEN)
            _t = TOK.segment(_src, count=False) if USE_TOK else list(_src)
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
            # ---- ANCHORS. A bits/byte number alone is uninterpretable: 2.9 could be excellent or worthless. -----
            # These are computed on the SAME held-out material, in the SAME units, so the model's score can be read
            # against something. If the model does not clearly beat ORDER-1, none of the architecture is doing work
            # that a two-line frequency table could not -- and that is a result worth being unable to avoid seeing.
            try:
                from collections import Counter                # imported locally: the module-level import of
                #   Counter happens further down, in the clustering report, and this block runs before it
                _cat = []
                for _p in range(len(VALC)):
                    _v = TOK.segment(VALC[_p], count=False) if USE_TOK else list(VALC[_p])
                    _cat += _v[:20000]
                _trn = []                                   # FIT the baselines on TRAIN, score them on HELD-OUT.
                for _p in range(len(CORP)):                 # Measuring a bigram's entropy ON the text it is scored
                    _s2 = CORP[_p][:min(SEG_LEN[_p], 200000)]   # on makes it a model that has seen the answers --
                    _trn += (TOK.segment(_s2, count=False) if USE_TOK else list(_s2))[:20000]   # an unfairly strong
                if len(_cat) > 256 and len(_trn) > 256:     # anchor, which is the opposite of the mistake to make.
                    _nb = sum(TOK.bytes_per_id[t] for t in _cat) if USE_TOK else len(_cat)
                    _sc = len(_cat) / _nb                   # tokens per byte: bits/token -> bits/byte
                    _VS = TOK.vocab_size if USE_TOK else 256
                    _k = 0.1                                # add-k smoothing, so unseen pairs cost finite bits
                    _c1 = Counter(_trn); _N1 = len(_trn)
                    _c2 = Counter(zip(_trn[:-1], _trn[1:])); _ctx = Counter(_trn[:-1])
                    _b0 = -sum(math.log2((_c1[t] + _k) / (_N1 + _k * _VS)) for t in _cat) / len(_cat)
                    _b1 = -sum(math.log2((_c2[(a, b2)] + _k) / (_ctx[a] + _k * _VS))
                               for a, b2 in zip(_cat[:-1], _cat[1:])) / max(1, len(_cat) - 1)
                    _u = math.log2(_VS)
                    print(f"  ANCHORS -- fitted on TRAIN, scored on the SAME held-out text (bits/byte):")
                    print(f"    uniform {_u * _sc:.3f} | order-0 {_b0 * _sc:.3f} | order-1 {_b1 * _sc:.3f} | "
                          f"THIS MODEL {_va:.3f}")
                    _o1 = _b1 * _sc
                    print(f"  >> {'beats order-1 by ' + format(_o1 - _va, '+.3f') + ' bits/byte' if _va < _o1 else 'DOES NOT BEAT ORDER-1 (' + format(_o1 - _va, '+.3f') + ') -- a two-line frequency table does as well'}"
                          f". GPT-2-small sits near 1.0-1.2 b/B on comparable text, for scale.")
            except Exception as _e:
                print(f"  [anchors skipped: {type(_e).__name__}: {_e}]")
        # === RETENTION: is the system still good at what it saw FIRST? =======================================
        # THE central continual-learning question, and until now nothing measured it on a default run. The
        # forgetting test that did exist (PHASED=1) is off by default and had never been executed; when finally
        # run it showed faded material +0.65 bits/byte worse than a stationary control, with 100% of its memory
        # evicted. Every "unlearning is local" result in this project was measured on ACTIVE material -- deleting
        # something the store already evicted is vacuous.
        # This needs no labels, no PHASED mode and no seeded corpora: the stream is a splice of the same corpora
        # throughout, so its first fifth and its last fifth are statistically identical. Both were TRAINED on, so
        # a gap is not generalisation -- it is forgetting. Memory is included because retention is a property of
        # the whole system, weights plus store, and the store is bounded and evicts.
        # MUST BE COMPARED PER PROCESS. The first version of this took the first fifth against the last fifth and
        # asserted they were "statistically identical material" -- true only when the stream is STATIONARY. Under
        # PHASED (now the default) phase 0 is processes [0,1] and phase 3 is [2,3], an EMPTY intersection, so that
        # comparison was measuring which corpora are intrinsically harder, exactly the confound that had to be
        # corrected by hand when the non-stationary test was first run. Condition on the label: for each process,
        # its EARLIEST windows against its LATEST windows. Same material either side, so a gap is drift in the
        # model, not a difference in the text.
        try:
            def _bpb_at(starts):
                _X = torch.tensor([list(stream[a:a + WIN]) for a in starts], device=DEV)
                _Y = torch.tensor([list(stream[a + 1:a + WIN + 1]) for a in starts], device=DEV)
                with torch.no_grad():
                    _lg = fab_logits(model, fab if FABRIC else None, model.encode(_X))
                    _pp = F.softmax(_lg, -1).gather(-1, _Y.unsqueeze(-1)).squeeze(-1)
                return -(torch.log(_pp.clamp_min(1e-9)).sum().item()) / math.log(2) / nbytes(_Y)
            _rows = []
            for _p in sorted(set(labels)):
                _at = [a for a in range(0, len(stream) - WIN - 2, WIN) if labels[a] == _p]
                if len(_at) < 32: continue                 # need enough of it at BOTH ends to say anything
                _k = min(48, len(_at) // 3)
                _rows.append((_p, _bpb_at(_at[:_k]), _bpb_at(_at[-_k:]), len(_at)))
            if _rows:
                print(f"\n=== RETENTION: does it still know what it saw FIRST? (per process -- like for like) ===")
                for _p, _e, _l, _n in _rows:
                    print(f"  process {_p}: earliest windows {_e:.3f}  ->  latest {_l:.3f}   "
                          f"drift {_e - _l:+.3f} bits/byte  ({_n} windows)")
                _d = sum(e - l for _, e, l, _n in _rows) / len(_rows)
                print(f"  mean drift {_d:+.3f} bits/byte over {len(_rows)} process(es)")
                print(f"  >> both ends were TRAINED on and are the SAME material, so a positive number is "
                      f"FORGETTING, not generalisation.")
                print(f"  >> {'RETAINED -- what it saw first is modelled as well as what it saw last' if _d < 0.10 else ('DRIFTING -- earlier material is measurably worse' if _d < 0.40 else 'CATASTROPHIC -- it has largely moved on from what it saw first')}"
                      f". This is what the continual-learning claim rests on; the domain scores are not.")
                if not PHASED:
                    print(f"  >> NOTE: PHASED=0, so nothing ever left the stream. Retention is easy here by "
                          f"construction -- read this number only alongside a PHASED=1 run.")
        except Exception as _e:
            print(f"[retention check skipped: {type(_e).__name__}: {_e}]")
        # === LEARNING CURVE: how fast does it pick a process UP, and how fast does it lose it? ==================
        # The sample-efficiency half of continual learning. Retention asks whether old material survives; this asks
        # what happens at the two transitions -- the step a process ENTERS the stream, and the step it FADES out.
        try:
            if _CURVE and len(set(p for _s, p, _b, _a in _CURVE)) > 0:
                _byp = {}
                for _s, _p, _b, _a in _CURVE: _byp.setdefault(_p, []).append((_s, _b, _a))
                print(f"\n=== LEARNING CURVE: bits/byte per process over training (A=active, .=absent) ===")
                _steps = sorted(set(s for s, _p, _b, _a in _CURVE))
                print(f"  step:      " + " ".join(f"{s:>7}" for s in _steps))
                for _p in sorted(_byp):
                    _m = {s: (b, a) for s, b, a in _byp[_p]}
                    print(f"  process {_p}: " + " ".join(
                        (f"{_m[s][0]:6.2f}{'A' if _m[s][1] else '.'}" if s in _m else "      -") for s in _steps))
                _gain = _loss = 0.0; _ng = _nl = 0
                for _p, _rows in _byp.items():
                    _rows = sorted(_rows)
                    for _k in range(1, len(_rows)):
                        _d = _rows[_k - 1][1] - _rows[_k][1]          # positive = improved over this window
                        if _rows[_k][2]: _gain += _d; _ng += 1        # measured while ACTIVE  -> acquisition
                        else: _loss += _d; _nl += 1                   # measured while ABSENT  -> retention/decay
                if _ng: print(f"  mean change per {RATE_EVERY} steps while a process is ACTIVE:  {_gain/_ng:+.3f} bits/byte  (positive = learning)")
                if _nl: print(f"  mean change per {RATE_EVERY} steps while a process is ABSENT:  {_loss/_nl:+.3f} bits/byte  (negative = forgetting)")
                if _ng and _nl:
                    print(f"  >> acquisition {_gain/_ng:+.3f} vs decay-while-absent {_loss/_nl:+.3f}. "
                          + ("it LEARNS faster than it forgets" if _gain/_ng > -(_loss/_nl) else
                             "it FORGETS absent material faster than it learns present material -- the store and the"
                             " weights are not holding what leaves the stream"))
                elif not _nl:
                    print(f"  >> nothing ever left the stream, so the ABSENT column is empty. Only PHASED=1 fills it.")
        except Exception as _e:
            print(f"[learning curve skipped: {type(_e).__name__}: {_e}]")
        # === CAN A DOMAIN PREDICT? ==============================================================================
        # Four arms on HELD-OUT text -- held-out because a per-domain histogram would trivially win on the training
        # windows it counted. Each eval window is assigned to a domain the way the assembler actually does it
        # (encode, nearest centroid), never by which memory entry happens to be closest.
        #   model alone            what the weights predict
        #   + GLOBAL prior         one histogram over all domains: what a bare order-0 model is worth here
        #   + OWN-domain prior     the claim -- a sharper histogram, IF domains are real
        #   + RANDOM-domain prior  the null -- same machinery, wrong domain
        # OWN must beat GLOBAL to show the PARTITION adds anything over frequency, and must beat RANDOM to show the
        # LABEL is doing it rather than the blend.
        try:
            if DOM_PRIOR > 0.0 and asm.tokc and len(asm.cent) >= 2 and VALC:
                _ids = [k for k in asm.cent if k in asm.tokc]
                if len(_ids) >= 2:
                    _P = torch.stack([asm.tokc[k] for k in _ids])                # (D, V) raw counts
                    _P = (_P + 0.5) / (_P.sum(1, keepdim=True) + 0.5 * V)        # add-k smoothed
                    _G = torch.stack([asm.tokc[k] for k in _ids]).sum(0)
                    _G = (_G + 0.5) / (_G.sum() + 0.5 * V)                       # one global histogram
                    _C = torch.stack([asm.cent[k] for k in _ids])
                    _xs, _ys, _ds = [], [], []
                    _rs = random.Random(7)
                    for _p in range(len(VALC)):
                        _vb = VALC[_p]
                        _v = TOK.segment(_vb, count=False) if USE_TOK else list(_vb)
                        if len(_v) < WIN + 2: continue
                        _cum = [0]
                        for _t2 in _v: _cum.append(_cum[-1] + (TOK.bytes_per_id[_t2] if USE_TOK else 1))
                        for _ in range(min(48, _i("EVAL_N", 64))):
                            _a = _rs.randint(0, len(_v) - WIN - 2)
                            _b0 = _cum[_a]
                            if _b0 + WIN > len(_vb): continue
                            _xs.append(_v[_a:_a + WIN]); _ys.append(_v[_a + 1:_a + WIN + 1])
                            _ds.append(list(_vb[_b0:_b0 + WIN]))                 # BYTE window -> signature
                    if len(_xs) >= 16:
                        _X = torch.tensor(_xs, device=DEV); _Y = torch.tensor(_ys, device=DEV)
                        with torch.no_grad():
                            _sg = enc(torch.tensor(_ds, device=DEV))
                            _own = (_C @ _sg.t()).argmax(0)                      # the assembler's own rule
                            _pm = F.softmax(fab_logits(model, fab if FABRIC else None, model.encode(_X)), -1)
                        _rnd = (_own + torch.randint(1, len(_ids), _own.shape, device=DEV)) % len(_ids)
                        _den = nbytes(_Y)
                        def _sc(mix):
                            _q = _pm if mix is None else (1 - DOM_PRIOR) * _pm + DOM_PRIOR * mix.unsqueeze(1)
                            _pp = _q.gather(-1, _Y.unsqueeze(-1)).squeeze(-1)
                            return -(torch.log(_pp.clamp_min(1e-9)).sum().item()) / math.log(2) / _den
                        _a0, _ag = _sc(None), _sc(_G.expand(len(_xs), -1))
                        _ao, _ar = _sc(_P[_own]), _sc(_P[_rnd])
                        print(f"\n=== CAN A DOMAIN PREDICT? (held-out, blend weight {DOM_PRIOR}) ===")
                        print(f"  model alone {_a0:.3f} | + GLOBAL prior {_ag:.3f} | + OWN-domain prior {_ao:.3f} | "
                              f"+ RANDOM-domain prior {_ar:.3f}   ({len(_ids)} domains)")
                        print(f"  >> own vs global {_ag - _ao:+.3f} (does the PARTITION beat plain frequency?) | "
                              f"own vs random {_ar - _ao:+.3f} (is it the LABEL, or just the blend?)")
                        print(f"  >> " + ("DOMAINS PREDICT: the own-domain histogram beats both a global one and a "
                                          "wrong-domain one, so the partition is carrying predictive information"
                                          if (_ag - _ao) > 0.01 and (_ar - _ao) > 0.01 else
                                          "NOT YET: " + ("the partition does not beat a single global histogram"
                                                         if (_ag - _ao) <= 0.01 else
                                                         "the gain is the blend, not the label -- a wrong domain does "
                                                         "as well")))
        except Exception as _e:
            print(f"[domain-prior check skipped: {type(_e).__name__}: {_e}]")
        model.train()
    except Exception as _e:
        print(f"[memorization check skipped: {type(_e).__name__}: {_e}]")
    if WORLD_MODEL:                                        # === WORLD MODEL: forward-dynamics on HELD-OUT observations ===
        try:                                              # ROBUST: unseen data, a real baseline, and a collapse check
            world_enc.eval(); world_fwd.eval()
            _wm, _pm, _sd = [], [], []
            for _p in range(len(VALC)):
                _v = TOK.segment(VALC[_p], count=False) if USE_TOK else list(VALC[_p])
                if len(_v) < WIN + 2: continue
                _st = [random.randint(0, len(_v) - WIN - 2) for _ in range(min(24, _i("EVAL_N", 64)))]
                with torch.no_grad():
                    _X = torch.tensor([_v[a:a + WIN] for a in _st], device=DEV)   # HELD-OUT windows, never trained on
                    _z = world_enc(model.emb(_X))
                    _zt = _z[:, :-WORLD_K].reshape(-1, WLAT); _zn = _z[:, WORLD_K:].reshape(-1, WLAT)
                    _wm.append(F.mse_loss(world_fwd(_zt)[0], _zn).item())         # POPULATION blended forward prediction
                    _pm.append(F.mse_loss(_zt, _zn).item())                       # baseline: "assume the world doesn't change"
                    _sd.append(_z.reshape(-1, WLAT).std(0).mean().item())         # collapse check
            if _wm:
                wm, pm, sd = sum(_wm) / len(_wm), sum(_pm) / len(_pm), sum(_sd) / len(_sd)
                _nlive = int(world_fwd.alive[:world_fwd.n()].sum())
                print(f"\n=== WORLD MODEL (separated population): forward-dynamics on HELD-OUT observations (unseen + baseline + collapse) ===")
                print(f"  forward-pred MSE {wm:.4f} | persistence baseline {pm:.4f} | beats baseline {(1 - wm / max(pm, 1e-9)) * 100:+.1f}% | latent std {sd:.2f}")
                print(f"  dynamics predictors: {world_fwd.n()} ({_nlive} live) | per-predictor fitness (err, lower=fitter): {[round(float(world_fwd.fit[i]),3) for i in range(world_fwd.n())]}")
                print(f"  >> positive beat AND std > ~0.5 = it learned real dynamics on UNSEEN data; ~0% beat or std~0 (collapsed) = it did NOT")
            world_enc.train(); world_fwd.train()
        except Exception as _e:
            print(f"[world-model eval skipped: {type(_e).__name__}: {_e}]")
    if _lm_curve:
        print("[LM training curve] step:loss -> " + "  ".join(f"{a}:{b:.2f}" for a, b in _lm_curve))
        _d8 = (_lm_curve[-2][1] - _lm_curve[-1][1]) if len(_lm_curve) > 1 else 0.0
        print(f"  (last segment change {_d8:+.3f}: still FALLING = more passes/steps will help;"
              f" flat = the model has converged and needs more CAPACITY or more DATA, not more steps)")
    n_self = len(asm.cent); print(f"SELF-ASSEMBLED {n_self} LIVE domains after {'management' if MANAGE_ON else 'NO MANAGEMENT (ablation)'} (truth had {NP} processes)")
    _ent = sorted((asm.visits.get(i, 0) for i in asm.cent), reverse=True)
    _rec = sum(1 for v in _ent if v >= DOM_MIN_VISITS)
    print(f"  domain population: {asm.created} created | {asm.folded} folded on non-recurrence | {len(asm.merged)} merged"
          f" (fold+merge, absorbed not deleted) | cap bound {asm.capped}x (MAX_DOMAINS={MAX_DOMAINS}) | "
          f"{asm.nb} boundaries | radius {sum(1 for i in asm.cent if asm.rad.get(i) is not None)}/{n_self} measured"
          f"{f', pooled {asm._radp:.3f}' if asm._radp else ''}")
    print(f"  ENTRIES per live domain {_ent[:12]} | recurrent (>= {DOM_MIN_VISITS} entries) {_rec}/{n_self}")
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
    # PURITY ALONE IS NOT A SCORE. It rises MONOTONICALLY with fragmentation -- one window per cluster gives purity
    # 1.0 -- so it read 0.96 while the assembler was producing one domain per SPLICE SEGMENT (96 for 4 corpora), and
    # the "improvement" from 0.54 was mostly the cluster count going 4 -> 96. COMPLETENESS is the other half (are all
    # windows of one true process in ONE domain), and V-measure is their harmonic mean. Report all three, always.
    import math as _m
    _n = max(1, len(assigns))
    _ct = Counter(t for _, _, t in assigns)                 # true-class sizes
    _ck = Counter(d for _, d, _ in assigns)                                        # cluster sizes
    _hck = -sum(c[t] / _n * _m.log((c[t] / max(1, sum(c.values()))) or 1)
                for c in by.values() for t in c)                                   # H(true | domain)
    _hc = -sum(v / _n * _m.log(v / _n) for v in _ct.values() if v)                  # H(true)
    homogeneity = 1.0 if _hc == 0 else max(0.0, 1 - _hck / _hc)
    # COMPLETENESS is the OTHER conditional: H(domain | true). Getting this backwards printed 0.89 for a partition
    # that was 16x fragmented -- H(true|domain) is homogeneity, which is high for ANY pure-but-shattered clustering.
    _hkc = -sum(by[d][t] / _n * _m.log((by[d][t] / max(1, _ct[t])) or 1) for d in by for t in by[d])
    _hk = -sum(v / _n * _m.log(v / _n) for v in _ck.values() if v)                  # H(domain)
    completeness = 1.0 if _hk == 0 else max(0.0, 1 - _hkc / _hk)
    vmeas = 0.0 if (homogeneity + completeness) == 0 else 2 * homogeneity * completeness / (homogeneity + completeness)
    _frag = len(smap) / max(1, len(_ct))
    print(f"clustering purity: {purity:.2f} | homogeneity: {homogeneity:.2f} | completeness: {completeness:.2f} | V-measure: {vmeas:.2f}"
          f"   [{len(smap)} self-domains for {len(_ct)} true processes = {_frag:.0f}x fragmentation]")
    print(f"  >> vs the 4 SEEDED corpora (a SCAFFOLD, not the target -- see recurrence below). "
          f"{'fragmented rel. to seeds' if _frag > 3 else 'aligned with seeds'} (first 20 self->true) {smap[:20]}")
    # RECURRENCE -- the metric that actually matches the thesis. The seeded corpora are how the STREAM was built,
    # not what the system is asked to find: the design intent is self-assembled, naturally OVERLAPPING domains, so
    # "did you recover exactly 4" is the wrong question and V-measure against 4 labels penalises the intended
    # behaviour. What distinguishes a real self-assembled domain from a splice-segment artifact is whether it is
    # RE-ENTERED: genuine structure recurs when similar material comes back; an artifact is visited once and never
    # again. A visit is a maximal run of consecutive windows assigned to the same domain.
    _seq = [d for _, d, _ in assigns]
    _visits = Counter()
    for _k, _d in enumerate(_seq):
        if _k == 0 or _seq[_k - 1] != _d: _visits[_d] += 1
    _nv = sorted(_visits.values(), reverse=True)
    _once = sum(1 for v in _nv if v == 1)
    _recur = sum(1 for v in _nv if v >= 3)
    _meanv = sum(_nv) / max(1, len(_nv))
    print(f"  RECURRENCE: {len(_nv)} domains | mean visits/domain {_meanv:.1f} | "
          f"visited ONCE {_once} ({_once/max(1,len(_nv))*100:.0f}%) | recurring (>=3 visits) {_recur} "
          f"({_recur/max(1,len(_nv))*100:.0f}%) | top visit counts {_nv[:8]}")
    print(f"  >> THE test for self-assembly: a domain that RECURS is real structure; one visited once is a splice"
          f" artifact. {'ARTIFACTS DOMINATE' if _once > len(_nv) * 0.5 else 'domains recur -- self-assembly is working'}")
    biggest = max(by, key=lambda d: sum(by[d].values())); tgt = s2t[biggest]

    # ---- GENUINENESS on the FINAL MANAGED set (merge/cull already applied live) ----
    # A domain is GENUINE only if it is a real, separated cluster -- not just large. We use a silhouette-style score:
    #   sil = (mean similarity of members to their OWN centroid) - (similarity to the NEAREST OTHER centroid) = coh+sep-1.
    # sil>0 means members are genuinely closer to their own domain than to any neighbor; sil<=0 means the domain overlaps
    # a neighbor and is really an arbitrary slice of a continuum. (The old test used coh>=0.5 & sep>=0.10, which never
    # bound -- so it silently reduced to a size threshold. This makes cohesion AND separation actually count.)
    # SIZE COMES FROM THE ASSEMBLER, NOT FROM THE REPORT LOG. `by` is built from `assigns`, which is one record per
    # window -- correct now, but it made every size in this table read 1/BATCH_W of the truth for as long as
    # assigns.append sat below the batch accumulator (the 4 MB run showed "size 134" for a domain of ~2100). asm.size
    # is incremented inside update(), which runs per window unconditionally, so it cannot drift from the stream again.
    sizes = {d: int(asm.size.get(d, sum(by[d].values()))) for d in by}
    MIN_SIZE = _i("GENUINE_MIN", 20); SIL_MIN = _f("GENUINE_SIL", 0.10)
    live = [d for d in by if d in asm.cent]               # domains that survived management (still have a centroid)
    print(f"\n=== domain genuineness ({len(live)} live domains: size | cohesion | separation | silhouette=coh+sep-1) ===")
    # SEPARATION IS REPORTED TWICE, ON PURPOSE. `sep` is a MIN over the other N-1 centroids -- an extreme order
    # statistic, so it shrinks mechanically as the population grows and penalises exactly the fragmentation the
    # recurrence fold exists to reduce. For OVERLAPPING self-assembled domains (the stated design intent) that is
    # the wrong question: neighbouring domains are SUPPOSED to touch. `sepm` is the MEDIAN distance to the other
    # centroids, which asks instead whether this domain sits anywhere distinct in the space at all. Read them
    # together: sil < 0 with silm > 0 means "crowded by a near neighbour but globally placed" (fragmentation, which
    # merging fixes); BOTH negative means the signature space has no cluster structure and no assign rule can help.
    genuine = 0; cohs = []; seps = []; sils = []; sepms = []; silms = []
    with torch.no_grad():
        for d in sorted(live, key=lambda k: -sizes[k]):
            if not asm.wins[d]: continue
            W = torch.tensor([w for w in asm.wins[d]], device=DEV)
            sg = enc(W) if SIG_MODE == "learned" else torch.stack([sig_of(list(w), enc) for w in asm.wins[d]])
            coh = F.cosine_similarity(sg, asm.cent[d].unsqueeze(0)).mean().item()
            _o = sorted(1 - F.cosine_similarity(asm.cent[d].unsqueeze(0), asm.cent[o].unsqueeze(0)).item()
                        for o in asm.cent if o != d)
            sep = _o[0] if _o else 1.0                     # nearest other centroid
            sepm = _o[len(_o) // 2] if _o else 1.0         # MEDIAN other centroid (population-size robust)
            sil = coh + sep - 1.0                          # silhouette-style cluster-validity score
            silm = coh + sepm - 1.0
            g = sizes[d] >= MIN_SIZE and sil >= SIL_MIN
            genuine += g; cohs.append(coh); seps.append(sep); sils.append(sil); sepms.append(sepm); silms.append(silm)
            if sizes[d] >= 5:
                print(f"  domain {d:4d}: size {sizes[d]:6d} | cohesion {coh:.2f} | sep nearest {sep:.2f} median "
                      f"{sepm:.2f} | sil {sil:+.2f} / median {silm:+.2f} | {'GENUINE' if g else 'weak'}")
    _mc = sum(cohs)/max(1,len(cohs)); _ms = sum(sils)/max(1,len(sils)); _mm = sum(silms)/max(1,len(silms))
    print(f"  >> {genuine}/{len(live)} live domains GENUINE (size>={MIN_SIZE} AND silhouette>={SIL_MIN}) | "
          f"mean cohesion {_mc:.2f} sep {sum(seps)/max(1,len(seps)):.2f}/{sum(sepms)/max(1,len(sepms)):.2f} "
          f"sil {_ms:+.2f} / median {_mm:+.2f}")
    # SPREAD CHECK. An earlier version of this compared the median centroid separation against a RANDOM-UNIT-VECTOR
    # null (1.0 +/- 1/sqrt(SIG_D)) and declared the space "COLLAPSED" below -3 sigma. That null is wrong and the
    # verdict was worthless: centroids of related text are nowhere near orthogonal, so a MEASURED-HEALTHY encoder
    # (true-label silhouette +0.25, 1-NN corpus accuracy 0.90) also scores -4.8 sigma -- against -5.2 for the run
    # that prompted the check. The test could not separate the two cases it existed to separate.
    # What IS scale-free is the median silhouette itself: it compares separation against this domain's OWN scatter,
    # so it needs no null. And note what neither number can settle -- both are computed between the centroids the
    # assembler PRODUCED, so a fragmented population is crowded by construction and says nothing about the encoder.
    # Only the true labels can settle that, which is what probe_ckpt_geometry.py is for.
    _rnd = 1.0 / (SIG_D ** 0.5)
    print(f"  >> SPREAD: median silhouette {_mm:+.2f} (cohesion {_mc:.2f} vs median separation "
          f"{sum(sepms)/max(1,len(sepms)):.2f}); random unit vectors in {SIG_D}-d would sit at 1.00+/-{_rnd:.2f}, but "
          f"real centroids sit FAR below that even when healthy -- do not read the gap as collapse.")
    _sv = ("domains ARE separated relative to their own scatter" if _mm > 0.10 else
           "domains are NOT separated relative to their own scatter -- the space may be poor OR the population may be"
           " fragmented, and this report CANNOT tell which")
    print(f"  >> {_sv}. To settle it: python3 probe_ckpt_geometry.py CKPT=<your SAVE_CKPT>"
          f"  (separability of the TRUE corpora, using the encoder this run trained)")
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
                dist, _cf, _, _ = mem.read(mem_key(X))
                pmem = dist.reshape(X.size(0), X.size(1), V)
                hp = _mem_hp(dist, _cf, dim=-1).reshape(X.size(0), X.size(1), 1)
                pp = (1 - hp) * pm + hp * pmem
            else:
                pp = pm
            return -(torch.log(pp.gather(-1, Y.unsqueeze(-1)).squeeze(-1).clamp_min(1e-9)).sum().item()) / math.log(2) / nbytes(Y)
    # ---- WRONGNESS (B) IN THE LOOP: detect + remove implausible associations via self-consistency ----
    if _i("WRONG_CHECK", 1):
        ninj = _i("WRONG_INJECT", 8)                       # inject a few cross-domain WRONG windows so B has real errors to catch
        procs = sorted(set(labels))
        if ninj > 0 and len(procs) < 2:
            # SINGLE-DOMAIN RUN: the injection builds a WRONG pair by taking a context from one process and a
            # continuation from a DIFFERENT one, which is undefined with a single source -- `random.choice` on the
            # empty "other processes" list raised IndexError and killed the whole eval battery AFTER training and the
            # checkpoint had completed. An English-only run is a supported configuration, so skip the injection and
            # say so, rather than crashing on it.
            print(f"[wrongness] skipping synthetic injection: needs >=2 source processes, found {len(procs)} "
                  f"(single-domain run). Self-consistency still runs on the GENUINE store below.")
            ninj = 0
        if ninj > 0:
            rx = []; ry = []
            for _ in range(ninj):
                p = random.choice(procs); qd = random.choice([z for z in procs if z != p])
                sp = random.choice([s for s in range(0, len(stream) - (WIN + 1), WIN) if labels[s] == p])
                sq = random.choice([s for s in range(0, len(stream) - (WIN + 1), WIN) if labels[s] == qd])
                rx.append(list(stream[sp:sp + WIN])); ry.append(list(stream[sq + 1:sq + WIN + 1]))
            XW = torch.tensor(rx, device=DEV); YW = torch.tensor(ry, device=DEV)
            mem.write(mem_key(XW), YW.reshape(-1), src=99, surprise=None, ctx=mem_ctx(XW))   # bypass gate: force-write the synthetic wrong entries
        selfcheck(model, mem, fab if FABRIC else None)
        if VERIFY == "recon" and recon is not None:              # VERIFICATION (reconstruction): the A/B against old B
            verify_mem(mem, recon, fit_steps=_i("VERIFY_FIT", 3000))   # FIT on the FINAL settled store (joint training fails on the churning loop)
            _uv = mem.is_unverified(); _inj = (mem.src == 99) & mem.active
            _tp = int((_uv & _inj).sum()); _fp = int((_uv & (mem.src != 99) & mem.active).sum()); _pos = int(_inj.sum())
            _pr = _tp / max(1, _tp + _fp); _rc = _tp / max(1, _pos)
            print(f"=== VERIFICATION (reconstruction) [VERIFY=recon]: flagged {_tp} injected / {_pos} "
                  f"(precision {_pr:.1%}, recall {_rc:.1%}) -- compare to self-consistency B below ===")
            if VERIFY_SWEEP:                                     # detect-AND-remove (the old B never earned this at ~1% precision)
                _before = mem.n; _rm = mem.delete(mem.is_unverified())
                print(f"    VERIFY_SWEEP: removed {_rm} unverified entries ({_before}->{mem.n}); reads now exclude them.")
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
        dom_exp = {_k: _v.cpu() for _k, _v in dom_exp.items()}   # accumulated on device (no per-step sync) -> host ONCE, here
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
            _w2, _, _ = fab.society(model.encode(torch.tensor([list(stream[:WIN])], device=DEV)), _sg2,
                                    torch.zeros(1, device=DEV), k=1)
        _j2 = int(_w2[0].argmax())
        _pre = {p: bpb_true(p, use_mem=False) for p in _ps2}
        import copy as _copy
        _fab_bak = _copy.deepcopy(fab)                     # RESTORE AFTERWARDS: this ablation deletes the BUSIEST
        fab.remove(_j2)                                    # <- the expert's parameters are deleted
        _post = {p: bpb_true(p, use_mem=False) for p in _ps2}
        _d2 = sum(_post[p] - _pre[p] for p in _ps2) / max(1, len(_ps2))
        print(f"\n=== EXPERT INDEPENDENCE: delete ONE expert of {len(fab.bodies) + 1} -- what breaks? ===")
        print(f"  deleted expert {_j2} (busiest, routing mass {float(_w2[0, _j2]):.2f})")
        for p in _ps2: print(f"    process {p}: {_pre[p]:.3f}->{_post[p]:.3f} ({_post[p] - _pre[p]:+.4f})")
        print(f"  mean collateral {_d2:+.4f}  ->  {'INDEPENDENT (society survives losing a member)' if abs(_d2) < 0.3 else 'ENTANGLED (the population depended on it)'}")
        # restore by swapping the containers back -- load_state_dict cannot repopulate a ModuleList that remove()
        # shrank (its keys are gone from the live module), so reassign the four things remove() rebuilds.
        fab.bodies = _fab_bak.bodies; fab.keys = _fab_bak.keys; fab.qproj = _fab_bak.qproj; fab.cent = _fab_bak.cent
        print("  (expert restored -- GENERATION and the remaining evals run on the INTACT model; before this fix every"
              " eval after this point, including the generation samples used to judge coherence, ran on the mutilated one)")
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
        _gen_keep = []
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
            _gen_keep.append((p, seed, gno, gme))
        # ---- COHERENCE, AS A NUMBER. ----------------------------------------------------------------------------
        # Generation has always been printed and eyeballed, which is how "it is producing code" got claimed for
        # output that merely contained code-shaped tokens. The visible failure in these samples is DRIFT: a
        # continuation seeded with prose slides into C within a few dozen tokens. That is measurable with machinery
        # already here -- encode successive windows of the CONTINUATION and ask which true-corpus centroid each is
        # nearest. Staying in the seed's corpus is coherence; wandering is not.
        # Bracketed by a floor and a ceiling, because the raw fraction means nothing on its own:
        #   CEILING = REAL text from that corpus scored the same way (the encoder is not perfect, so this is < 1)
        #   FLOOR   = chance, 1/NP, what a generator ignorant of the seed would get
        try:
            if _gen_keep and SIG_MODE == "learned" and len(set(labels)) > 1:
                _cent = {}
                for _p in sorted(set(labels)):             # true-corpus centroids from REAL data, not from domains
                    _st = [s for s in range(0, len(stream) - WIN - 1, WIN) if labels[s] == _p]
                    if len(_st) < 8: continue
                    random.shuffle(_st)
                    _bs = [(tok_bs[s] if ONLINE else s) for s in _st[:64]]
                    with torch.no_grad():
                        _Z = enc(torch.tensor([list(ENC_SEQ[b:b + WIN]) for b in _bs
                                               if b + WIN <= len(ENC_SEQ)], device=DEV))
                    if _Z.numel(): _cent[_p] = F.normalize(_Z.mean(0), dim=0)
                if len(_cent) > 1:
                    _ks = sorted(_cent); _C = torch.stack([_cent[k] for k in _ks])
                    def _stay(units, home):                # fraction of windows nearest the HOME corpus centroid
                        _txt = TOK.decode(units) if USE_TOK else bytes(units)
                        _by = list(_txt.encode("utf-8", "replace") if isinstance(_txt, str) else _txt)
                        _w = [_by[a:a + WIN] for a in range(0, max(0, len(_by) - WIN + 1), WIN // 2)]
                        _w = [x for x in _w if len(x) == WIN]
                        if not _w: return None
                        with torch.no_grad(): _Z = enc(torch.tensor(_w, device=DEV))
                        return float((torch.tensor(_ks, device=DEV)[(_C @ _Z.t()).argmax(0)] == home).float().mean())
                    _rn, _rm, _rr = [], [], []
                    for _p, _sd, _a, _b in _gen_keep:
                        if _p not in _cent: continue
                        for _acc, _u in ((_rn, _a), (_rm, _b)):
                            _v = _stay(_u, _p)
                            if _v is not None: _acc.append(_v)
                        _st = [s for s in range(0, len(stream) - WIN - 1, WIN) if labels[s] == _p]
                        if _st:                            # CEILING: real text of the same corpus, same measurement
                            _v = _stay(list(stream[_st[0]:_st[0] + _i("GEN_LEN", 200)]), _p)
                            if _v is not None: _rr.append(_v)
                    if _rn and _rm:
                        _mn, _mm = sum(_rn) / len(_rn), sum(_rm) / len(_rm)
                        _ceil = sum(_rr) / len(_rr) if _rr else float("nan")
                        _floor = 1.0 / len(_cent)
                        print(f"\n=== COHERENCE: does a continuation STAY in the domain of its seed? ===")
                        print(f"  model ALONE {_mn:.2f}  |  model+MEMORY {_mm:.2f}  |  REAL text (ceiling) {_ceil:.2f}"
                              f"  |  chance (floor) {_floor:.2f}")
                        print(f"  >> fraction of generated windows whose nearest true-corpus centroid is the SEED's."
                              f" Drift out of the seed's domain is the failure these samples show by eye.")
                        _best = max(_mn, _mm)
                        print(f"  >> {'ON-TOPIC -- close to what real text of this corpus scores' if _best >= _ceil - 0.15 else ('PARTIAL -- better than chance but wanders well before real text does' if _best > _floor + 0.10 else 'INCOHERENT -- indistinguishable from ignoring the seed entirely')}"
                              f"; memory {'HELPS' if _mm > _mn + 0.02 else ('HURTS' if _mn > _mm + 0.02 else 'is neutral')} here.")
        except Exception as _e:
            print(f"[coherence check skipped: {type(_e).__name__}: {_e}]")

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
