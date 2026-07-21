"""All knobs for the overarching cognitive system.
Edit the defaults below, or override any of them with environment variables, e.g.:
    STEPS=50000 D_MODEL=192 DEVICE=cuda python train.py
"""
import os, torch

def _b(k, d): return os.environ.get(k, str(d)).lower() in ("1", "true", "yes", "on")
def _i(k, d): return int(os.environ.get(k, d))
def _f(k, d): return float(os.environ.get(k, d))
def _s(k, d): return os.environ.get(k, d)

_auto = "cuda" if torch.cuda.is_available() else ("mps" if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available() else "cpu")

class cfg:
    # ---- paths ----
    DATA_DIR   = _s("DATA_DIR", "data")
    RUN_DIR    = _s("RUN_DIR", "runs")           # checkpoints + logs land here
    DEVICE     = _s("DEVICE", _auto)             # cuda | mps | cpu  (auto-detected)
    SEED       = _i("SEED", 0)

    # ---- model size (bigger than the reference run; depth is the floor-lever) ----
    D_MODEL    = _i("D_MODEL", 128)              # hidden width
    N_LAYERS   = _i("N_LAYERS", 4)               # base depth (proven to lower the floor)
    N_HEADS    = _i("N_HEADS", 4)
    CTX        = _i("CTX", 128)                  # context length (tokens; bytes if no tokenizer)
    MAX_LEN    = _i("MAX_LEN", 512)              # positional table size; must be >= CTX
    DROPOUT    = _f("DROPOUT", 0.1)              # regularization (helps generalization)
    VOCAB      = _i("VOCAB", 256)                # active/initial vocab (256 = byte-level)
    VMAX       = _i("VMAX", 0)                   # vocab ceiling for DYNAMIC growth (0 => = VOCAB, no growth)
    TOKENIZER  = _s("TOKENIZER", "")             # ""=byte | path/to.json=frozen BPE | "dynamic"=emergent
    MIN_PAIR   = _i("MIN_PAIR", 200)             # dynamic: mint a token once a pair repeats this many times
    MINT_PER_STEP = _i("MINT_PER_STEP", 4)       # dynamic: max tokens to mint per step (fast vocab growth)
    TOK_DROPOUT = _f("TOK_DROPOUT", 0.0)         # dynamic: P(skip a merge) => preferential byte fallback (0=strict)

    # ---- training schedule ----
    BATCH        = _i("BATCH", 32)
    STEPS        = _i("STEPS", 20000)            # total joint training steps
    WARMUP_STEPS = _i("WARMUP_STEPS", 1000)      # base-only language pretrain before joint training
    LR           = _f("LR", 1.5e-3)
    WEIGHT_DECAY = _f("WEIGHT_DECAY", 0.02)
    GRAD_CLIP    = _f("GRAD_CLIP", 1.0)
    EVAL_EVERY   = _i("EVAL_EVERY", 500)
    CKPT_EVERY   = _i("CKPT_EVERY", 1000)
    LOG_EVERY    = _i("LOG_EVERY", 100)

    # ---- fabric / routing ----
    DK           = _i("DK", 32)                  # routing-key dimension
    M_EMBED      = _i("M_EMBED", 4)              # number of specialized (gist-routed) embedders
    ALPHA        = _f("ALPHA", 0.5)              # per-step residual scale in the fabric loop
    N0           = _i("N0", 3)                   # initial fabric nodes
    NMAX         = _i("NMAX", 16)                # max nodes (hard ceiling guardrail)
    MINN         = _i("MINN", 2)                 # min nodes (hard floor guardrail)
    # ---- self-regulating population (growth.py): no fixed loss target / usage floor ----
    GRACE        = _i("GRACE", 400)              # steps a newborn node is immune from pruning
    PATIENCE     = _i("PATIENCE", 400)           # steps of no rel-improvement (plateau) before a spawn
    REL_IMPROVE  = _f("REL_IMPROVE", 0.01)       # relative loss drop that still counts as "learning"
    PRUNE_FRAC   = _f("PRUNE_FRAC", 0.25)        # prune an OLD node using < this fraction of mean usage
    COOLDOWN     = _i("COOLDOWN", 150)           # min steps between structural changes
    PRUNE        = _b("PRUNE", False)             # default OFF: bias toward growth, never cull nodes
    REQUIRE_BALANCE = _b("REQUIRE_BALANCE", False)# default OFF: spawn on any plateau, even if load uneven
    TARGET       = _f("TARGET", 1.3)             # (legacy; unused by growth.py)
    THROTTLE     = _i("THROTTLE", 500)           # (legacy; unused by growth.py)
    PRUNE_EVERY  = _i("PRUNE_EVERY", 400)        # (legacy; unused by growth.py)
    PRUNE_FLOOR  = _f("PRUNE_FLOOR", 0.015)      # (legacy; unused by growth.py)
    PONDER       = _f("PONDER", 0.01)            # depth penalty (charges for fabric steps)
    REENC_COST   = _f("REENC_COST", 0.0)         # 0 => the ROUTER alone decides whether to re-encode
    COUNTERPART_COST = _f("COUNTERPART_COST", 0.05)  # weight on inverse-counterpart local loss (COUNTERPARTS=1)
    ENABLE_REENCODE = _b("ENABLE_REENCODE", True)# re-encode is the expensive op; set 0 to disable for speed
    REENCODE_WARMUP  = _i("REENCODE_WARMUP", 0)  # hold re-encode OFF until this step (let embedders learn tokens first)
    REENCODE_SURPRISE= _b("REENCODE_SURPRISE", False) # scale re-encode's influence by per-example surprise
    SENSE_K          = _i("SENSE_K", 0)          # per-token sense book (0=off); context routes among K sub-meaning branches
    SENSE_SLOTS      = _i("SENSE_SLOTS", 0)      # 0=dense (all tokens); >0=sparse memory-backed, this many spawnable folders
    SENSE_POS        = _b("SENSE_POS", True)     # route senses per-position (within-sequence polysemy) vs per-sequence
    SENSE_PROMOTE    = _f("SENSE_PROMOTE", 20.0) # sparse: surprise mass a token must accumulate before it gets a folder
    FABRIC           = _s("FABRIC", "dense")     # dense = Greg (recurrent expert loop); sparse = Barry (top-k MoE)
    MOE_K            = _i("MOE_K", 2)            # Barry: experts per token (top-k)
    FABRIC_LAYERS    = _i("FABRIC_LAYERS", 2)   # Barry: number of stacked sparse-MoE layers
    CAP_FACTOR       = _f("CAP_FACTOR", 1.25)   # Barry: per-expert capacity slack (higher = fewer dropped tokens)
    LB_COST          = _f("LB_COST", 0.01)      # Barry: load-balancing loss weight (0 for Greg -> no effect)
    LR_WARMUP        = _i("LR_WARMUP", 1000)     # linear LR warmup steps (stabilizes the start at high LR / big batch)
    LR_SCHEDULE      = _s("LR_SCHEDULE", "constant")  # post-warmup LR: constant | wsd (warmup-stable-decay). [cosine removed: hurt OOD]
    LR_MIN_FRAC      = _f("LR_MIN_FRAC", 0.1)    # decay floor as a fraction of peak LR (cosine/wsd)
    WSD_DECAY_FRAC   = _f("WSD_DECAY_FRAC", 0.2) # wsd: fraction of total steps spent decaying at the end
    LABEL_SMOOTH     = _f("LABEL_SMOOTH", 0.0)   # training-loss label smoothing (0=off; eval stays TRUE bits/byte)
    EMA_DECAY        = _f("EMA_DECAY", 0.0)       # weight EMA for eval/save (0=off; e.g. 0.999). Resets on grow/cull.
    OPTIM            = _s("OPTIM", "adamw")        # optimizer: adamw | lion
    GRAD_ACCUM       = _i("GRAD_ACCUM", 1)         # microbatches accumulated per optimizer step (larger effective batch)
    MTP_K            = _i("MTP_K", 1)              # multi-token prediction: predict next K tokens (1 = standard)
    DENOISE          = _f("DENOISE", 0.0)          # denoising: fraction of INPUT tokens corrupted; targets stay CLEAN
    DENOISE_MODE     = _s("DENOISE_MODE", "sub")   # corruption: sub (replace) | swap (adjacent) | mix (both)
    CTX_START        = _i("CTX_START", 0)          # curriculum: starting seq length (0=off=full CTX); ramps up to CTX
    CTX_RAMP_STEPS   = _i("CTX_RAMP_STEPS", 2000)  # steps to ramp CTX_START -> CTX (short sequences first = easier)
    GROWTH_START     = _i("GROWTH_START", 0)       # delay all growth/turnover until this step (form foundation experts first)
    COMPOSE_EMB      = _f("COMPOSE_EMB", 0.0)       # compositional embeddings: add composed vector from constituent atoms (0=off)
    COMPOSE_DEPTH    = _i("COMPOSE_DEPTH", 1)       # levels of RECURSIVE composition (1=immediate parts; higher recurses toward bytes)
    CORRECT_AT       = _s("CORRECT_AT", "none")     # correction/modification hook stage: none | embed (post-tokenizer) | fabric (mid)
    COMPOSE_REFRESH  = _i("COMPOSE_REFRESH", 1)     # recompute composed-embedding table every N forwards (1=exact; higher=cache/faster at scale)
    NN_INIT          = _f("NN_INIT", 0.0)          # warm-start a new token from its nearest EXISTING token's embedding (0=off=mean-of-parts; 1=full adoption)
    NN_INIT_K        = _i("NN_INIT_K", 1)          # blend top-K nearest neighbors (similarity-weighted) for NN-init (1 = single nearest)
    CROSSOVER        = _f("CROSSOVER", 0.0)        # prob a spawn is a CROSSOVER of the top-2 experts instead of a mutation of the best (0=off)
    UNMERGE          = _i("UNMERGE", 0)            # retire tokenizer merges that stopped paying off, every N steps (0=off)
    UNMERGE_MIN      = _f("UNMERGE_MIN", 3.0)      # retire a merged token whose usage EMA falls below this
    DIFFICULTY_CURR  = _i("DIFFICULTY_CURR", 0)    # difficulty curriculum: feed more-compressible (easier) windows first, over N steps (0=off)
    EXPERT_COORD     = _f("EXPERT_COORD", 0.0)     # expert coordination: let each MoE layer's combined output feed a learned cross-expert mix (0=off)
    EARLY_STOP       = _i("EARLY_STOP", 0)       # stop if held OOD hasn't improved in this many evals (0 = off)
    EXPERT_HIDDEN_MULT = _f("EXPERT_HIDDEN_MULT", 4.0)  # expert hidden = mult*d. <4 bottlenecks (forces compression)
    MUTATE           = _i("MUTATE", 0)           # spawn new experts as mutated copies of the best (1) vs random (0)
    MUTATE_STRENGTH  = _f("MUTATE_STRENGTH", 0.05)      # mutation noise, as a fraction of parent weight std
    PRUNE_ECO        = _i("PRUNE_ECO", 0)        # cull the least-contributing expert periodically (survival pressure)
    PRUNE_EVERY      = _i("PRUNE_EVERY", 1000)   # steps between culls (when PRUNE_ECO=1)
    NMIN             = _i("NMIN", 8)             # population floor -- never cull below this many experts
    CULL_METRIC      = _s("CULL_METRIC", "energy")  # selection signal: energy | traffic (router picks) | blend
    AMP              = _b("AMP", False)           # bf16 autocast (big speed + memory win on H100/A100 tensor cores)

    # ---- episodic memory ----
    MEMCAP       = _i("MEMCAP", 4096)            # ring-buffer capacity (key/value pairs)

    # ---- data ----
    DATA_CAP     = _i("DATA_CAP", 0)             # chars per domain (0 = use full files)
    HELD         = _i("HELD", 64)               # in-distribution held chunks per domain
    OOD_N        = _i("OOD_N", 64)              # held-out-source chunks per OOD set

cfg.assert_ok = (cfg.MAX_LEN >= cfg.CTX)
assert cfg.MAX_LEN >= cfg.CTX, "MAX_LEN must be >= CTX"
