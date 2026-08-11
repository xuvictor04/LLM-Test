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

# === CONFIG PROVENANCE =======================================================================================
# Every knob is read through _i/_f, and every read is RECORDED here: what the environment asked for, and whether
# it asked at all. The banner then compares that against the value the LIVE OBJECT ended up with and reports any
# divergence automatically, instead of a human remembering to keep a printf in sync with an `and` clause.
# This exists because the banner has lied three separate times -- "per-expert memory ON " for a whole 48k-step run
# where it was off from step 0, "grounded region + learned bilinear" on a path with no region term, and
# FAB_MIN_STEPS=2 while the code ran 0 -- and each was fixed individually while the next one was already there.
_ENV_ASKED = {}                                            # name -> the value the environment explicitly set
_ENV_READ = set()                                          # every key the code ever ASKED FOR, set or not
# === THE KNOB REGISTRY =======================================================================================
# EVERY environment knob this file reads, in one place, with its type and default. Before this existed the
# 279 knobs were read inline at their point of use across 5,500 lines, so there was nowhere to look to see
# the configuration surface -- and five of them were read with DIFFERENT DEFAULTS in different places:
#   VMAX      the tokenizer targeted 4096 while ByteComposer sized its per-token tables to 2048, so an
#             unset VMAX indexed past the end of delta/dbias.
#   DOMAINS   the checkpoint recorded _env("DOMAINS", "") -- an empty domain list on any run that did not
#             set it, which is what report_holdout keys its retention probe on.
#   RESUME, SAVE_CKPT  None in some places, "" in others; both falsy, so this one was only ever cosmetic.
#   LAYERS    genuinely context-dependent (4 for transformer, 1 for gru) and is EXEMPT below rather than
#             forced to one value.
# _env now checks every read against this table and stops the run on a mismatch, so a default can never
# again disagree with itself. The table is the declaration; the call sites are uses.
# EXEMPT: their default is computed from another knob, so it cannot live in a table of literals. They are
# still LISTED in _SPEC (with None) so the registry stays the complete inventory -- just not enforced.
# KNOBS WHOSE DEFAULT IS COMPUTED FROM ANOTHER KNOB. _env cannot check these against a literal, because the
# literal does not exist -- the default IS an expression. They are exempt from that check and declared in
# _DERIVED below instead, which records WHICH knob each one follows. levers.py re-derives both sets from the
# AST and fails if either has drifted from the source, so this cannot silently go stale.
_DERIVED = {                    # derived knob -> the knob(s) its DEFAULT is read from
    "D_MODEL":        ("D_MODEL_B",),      # an ALIAS, not a coupling: same quantity under the other name
    "ENC_EVERY_IDLE": ("ENC_EVERY",),      # idle cadence follows the active one
    "ENC_POS_MAX":    ("WIN",),            # positional table sized to the window
    "FAB_MIN_STEPS":  ("SOCIETY",),        # HALT is unused on the society path, so 0 there and 2 on chaining
    "LAYERS":         ("MODEL",),          # 4 for transformer, 1 for gru
    "MAX_DOMAINS":    ("FAB_NMAX",),       # the domain cap mirrors the expert slot pool
    "PHASE_W":        ("PHASES",),         # window width follows the phase count
    "SEG_CONTIG":     ("DOMAINS",),        # contiguous when ONE corpus, random when several
    "SIG_LOOK":       ("ENC_EVERY_IDLE",), # TWO HOPS: SIG_LOOK <- ENC_EVERY_IDLE <- ENC_EVERY
}
_SPEC_FREE = set(_DERIVED)
_SPEC = {
    # --- data: corpus, stream and phase schedule ---------------------------------------------------
    "CORPUS_CAP": ("i", 2000000),                         # data
    "DATA_DIR": ("env", "data"),                          # data
    "DATA_MODE": ("env", "synthetic"),                    # data
    "DISK_STREAM": ("i", 0),                              # data
    "DOMAINS": ("env", "eng,py,num,c"),                   # data
    "EPOCHS": ("i", 1),                                   # data
    "PHASED": ("i", 1),                                   # data
    "PHASES": ("i", 4),                                   # data
    "PHASE_SCHED": ("env", ""),                           # data
    "PHASE_W": ("i", None),                               # data -- DEFAULT IS COMPUTED: (n_phases + 1) // 2
    "STREAM_LEN": ("i", 120000),                          # data
    "VAL_FRAC": ("f", 0.05),                              # data
    "WIN": ("i", 128),                                    # data
    # --- tokenizer: vocabulary: build, mint, freeze, re-segment ------------------------------------
    "GROW_PASSES": ("i", 8),                              # tokenizer
    "MAX_TOK": ("i", 16),                                 # tokenizer
    "MIN_PAIR": ("i", 50),                                # tokenizer
    "RETOK_EVERY": ("i", 3000),                           # tokenizer
    "RETOK_TAIL": ("i", 1),                               # tokenizer
    "SEED_PASSES": ("i", 2),                              # tokenizer
    "SEED_VOCAB": ("i", 512),                             # tokenizer
    "TOKENIZER": ("i", 1),                                # tokenizer
    "TOKENIZER_PATH": ("env", "data/dyntok.json"),        # tokenizer
    "TOK_ANCHOR": ("f", 0.05),                            # tokenizer
    "TOK_ANCHOR_TAU": ("f", 4000.0),                      # tokenizer
    "TOK_COMPOSE": ("i", 0),                              # tokenizer
    "TOK_DROPOUT": ("f", 0.0),                            # tokenizer
    "TOK_GROW_CAP": ("i", 1000000),                       # tokenizer
    "TOK_MINT_NOVEL": ("f", 0.0),                         # tokenizer
    "TOK_MINT_UNTIL": ("i", 0),                           # tokenizer
    "TOK_ONLINE": ("i", 1),                               # tokenizer
    "VMAX": ("i", 4096),                                  # tokenizer
    "WARMSTART": ("i", 1),                                # tokenizer
    "WARMSTART_MODE": ("env", "mean"),                    # tokenizer
    "WARMSTART_OPT": ("i", 0),                            # tokenizer
    # --- fabric: the routed expert population, its routing and its growth --------------------------
    "AFF_MIN": ("f", 0.10),                               # fabric
    "CHAIN_BAN": ("env", 1),                              # fabric
    "CHAIN_CURRIC": ("env", 0),                           # fabric
    "CHAIN_DEPTH0": ("env", 1),                           # fabric
    "CHAIN_EPS": ("env", 0.01),                           # fabric
    "CHAIN_PATIENCE": ("env", 6),                         # fabric
    "CHAIN_ROUTE": ("env", "soc"),                        # fabric
    "CHAIN_STAGE_MAX": ("env", 40),                       # fabric
    "CHAIN_STATE_Q": ("env", 0),                          # fabric
    "CHAIN_SUP": ("env", 0.0),                            # fabric
    "CHAIN_VOTE": ("env", 1),                             # fabric
    "DIV_W": ("env", 0.0),                                # fabric
    "ENS_K": ("i", 2),                                    # fabric
    "EXPERTS": ("i", 0),                                  # fabric
    "EXPERT_R": ("i", 4),                                 # fabric
    "EXPERT_REP_MULT": ("f", 2.5),                        # fabric
    "EXP_DOM_FRAC": ("env", 0.10),                        # fabric
    "EXP_DOM_MIN": ("env", 4),                            # fabric
    "FAB_AE_W": ("f", 0.5),                               # fabric
    "FAB_ALPHA": ("f", 0.5),                              # fabric
    "FAB_BALANCE": ("f", 0.01),                           # fabric
    "FAB_BIRTH_WIN": ("env", 256),                        # fabric
    "FAB_BURST": ("i", 3),                                # fabric
    "FAB_CENT_TOPK": ("i", 8),                            # fabric
    "FAB_CHAIN_K": ("env", 8),                            # fabric
    "FAB_COOLDOWN": ("i", 400),                           # fabric
    "FAB_CULL_FRAC": ("f", 0.08),                         # fabric
    "FAB_DERIVE_IDS": ("env", 1),                         # fabric
    "FAB_DISCOVER": ("f", 0.35),                          # fabric
    "FAB_DK": ("i", 32),                                  # fabric
    "FAB_EMB_EVERY": ("env", 1),                          # fabric
    "FAB_EMB_HID": ("env", 128),                          # fabric
    "FAB_EMB_VAR": ("env", 1.0),                          # fabric
    "FAB_ERR_FAST": ("env", 0.05),                        # fabric
    "FAB_ERR_SLOW": ("env", 0.005),                       # fabric
    "FAB_EXPLORE": ("env", 0.15),                         # fabric
    "FAB_FAIL_TOL": ("env", 0.15),                        # fabric
    "FAB_GRACE": ("i", 3000),                             # fabric
    "FAB_GROW": ("env", 1),                               # fabric
    "FAB_HALT": ("env", 1),                               # fabric
    "FAB_HALT_MAX": ("env", 0.9),                         # fabric
    "FAB_HID_MULT": ("f", 2),                             # fabric
    "FAB_KEY_NORM": ("i", 0),                             # fabric
    "FAB_MIN_STEPS": ("i", None),                         # DEFAULT IS COMPUTED: 0 if SOCIETY else 2
    "FAB_MUT": ("env", 0.25),                             # fabric
    "FAB_MUT_BIG": ("env", 6.0),                          # fabric
    "FAB_MUT_BIG_P": ("env", 0.1),                        # fabric
    "FAB_N0": ("i", 3),                                   # fabric
    "FAB_NMAX": ("i", 4096),                              # fabric
    "FAB_NORM_ONLY": ("i", 0),                            # fabric
    "FAB_PARENT_K": ("env", 8),                           # fabric
    "FAB_PARENT_MAX": ("env", 0.20),                      # fabric
    "FAB_PLATEAU": ("f", 0.002),                          # fabric
    "FAB_PRESSURE": ("f", 0.75),                          # fabric
    "FAB_RAMP": ("i", 4000),                              # fabric
    "FAB_RAMP_LATCH": ("env", 1),                         # fabric
    "FAB_RAMP_RATE": ("f", 0.10),                         # fabric
    "FAB_RAMP_TO": ("f", 1.0),                            # fabric
    "FAB_RANK": ("env", 8),                               # fabric
    "FAB_RECOVER_MAX": ("i", 20000),                      # fabric
    "FAB_RECOVER_MIN": ("i", 600),                        # fabric
    "FAB_REPLICATE": ("i", 1),                            # fabric
    "FAB_SHIFT_TOL": ("env", 0.05),                       # fabric
    "FAB_SPAWN": ("i", 1),                                # fabric
    "FAB_SPAWN_FLOOR": ("env", 0.02),                     # fabric
    "FAB_SPAWN_MULT": ("env", 2.0),                       # fabric
    "FAB_STEPS": ("i", 4),                                # fabric
    "FAB_WARMUP": ("i", 300),                             # fabric
    "FAB_XOVER": ("env", 0.35),                           # fabric
    "FAB_Z": ("f", 4.0),                                  # fabric
    "IND_K": ("i", 2),                                    # fabric
    "IND_W": ("f", 0.5),                                  # fabric
    "MAX_EXPERTS": ("i", 256),                            # fabric
    "PONDER": ("f", 0.01),                                # fabric
    "PONDER_WARM": ("i", 8000),                           # fabric
    "ROUTE_GROUNDED": ("env", 1),                         # fabric
    "ROUTE_LEARN": ("env", 1),                            # fabric
    "ROUTE_REGION_W": ("env", 1.0),                       # fabric
    "ROUTE_T": ("env", 0.1),                              # fabric
    "SOCIETY": ("i", 0),                                  # fabric
    # --- domains: self-assembled domains and their management --------------------------------------
    "DOM_ADAPTIVE": ("i", 0),                             # domains
    "DOM_CULL_EMPTY": ("i", 1),                           # domains
    "DOM_CULL_FRAC": ("f", 0.10),                         # domains
    "DOM_DECAY": ("f", 0.9),                              # domains
    "DOM_FOLD_MULT": ("f", 1.5),                          # domains
    "DOM_GRACE": ("i", 500),                              # domains
    "DOM_MANAGE_EVERY": ("i", 100),                       # domains
    "MAX_DOMAINS": ("i", None),                           # domains -- DEFAULT IS COMPUTED: FAB_NMAX
    "DOM_MARGIN": ("f", 0.75),                            # domains
    "DOM_MIN_VISITS": ("i", 2),                           # domains
    "DOM_PRIOR": ("f", 0.15),                             # domains
    "DOM_RADIUS": ("i", 1),                               # domains
    "DOM_RCAP": ("f", 2.0),                               # domains
    "DOM_RECUR": ("i", 1),                                # domains
    "DOM_RECUR_HORIZON": ("i", 32),                       # domains
    "DOM_RELATIVE": ("i", 0),                             # domains
    "DOM_RMULT": ("f", 1.2),                              # domains
    "DOM_RQ": ("f", 0.85),                                # domains
    "DOM_SPAWN_K": ("f", 3.0),                            # domains
    "DOM_WINS": ("i", 40),                                # domains
    "MANAGE": ("i", 1),                                   # domains
    "MANAGE_EVERY": ("i", 500),                           # domains
    "MANAGE_MERGE": ("f", 0.28),                          # domains
    "MANAGE_MIN": ("i", 15),                              # domains
    "MANAGE_STALE": ("i", 500),                           # domains
    "MERGE_FRAC": ("f", 0.8),                             # domains
    "NEW_DIST": ("f", 0.35),                              # domains
    "SEG_CONTIG": ("i", None),                            # DEFAULT IS COMPUTED: 1 if NP == 1 else 0
    "SEG_MAX": ("i", 1800),                               # domains
    "SEG_MIN": ("i", 700),                                # domains
    "SELF_ORG": ("i", 1),                                 # domains
    "SHIFT_DIST": ("f", 0.30),                            # domains
    "SHIFT_MULT": ("f", 1.5),                             # domains
    "SHIFT_Q": ("f", 0.50),                               # domains
    "SHIFT_REL": ("i", 0),                                # domains
    "SUSTAIN": ("i", 2),                                  # domains
    # --- memory: the retrieval store and its keys --------------------------------------------------
    "KEY_BATCH": ("i", 1),                                # memory
    "KEY_LAYERS": ("i", 0),                               # memory
    "KEY_PREGATE": ("i", 1),                              # memory
    "KEY_SRC": ("env", "model"),                          # memory
    "KEY_WIN": ("i", 8),                                  # memory
    "MEM_CAP": ("i", 200000),                             # memory
    "MEM_CONF0": ("f", 0.3),                              # memory
    "MEM_GATE": ("i", 1),                                 # memory
    "MEM_OWNERS": ("i", 64),                              # memory
    "MEM_PER_EXPERT": ("i", 1),                           # memory
    "MEM_QUOTA": ("i", 128),                              # memory
    "MEM_W": ("f", 0.5),                                  # memory
    "RECON_W": ("f", 0.0),                                # memory
    "REKEY_AMORTIZED": ("i", 1),                          # memory
    "REKEY_CHUNK": ("i", 1),                              # memory
    "REKEY_EVERY": ("i", 200),                            # memory
    "VERIFY": ("env", "selfcon"),                         # memory
    "VERIFY_FIT": ("i", 3000),                            # memory
    "VERIFY_SWEEP": ("i", 0),                             # memory
    # --- encoder: signature encoder and signature space --------------------------------------------
    "ENC_BATCH": ("i", 48),                               # encoder
    "ENC_CREG": ("f", 0.0),                               # encoder
    "ENC_EVERY": ("i", 1),                                # encoder
    "ENC_EVERY_IDLE": ("i", None),                        # encoder -- DEFAULT IS COMPUTED: max(ENC_EVERY*6, 12)
    "ENC_FLOOR_K": ("i", 8),                              # encoder
    "ENC_FUSE": ("i", 1),                                 # encoder
    "ENC_POS_MAX": ("i", None),                           # DEFAULT IS COMPUTED: 2 * WIN
    "ENC_PROTO": ("f", 0.0),                              # encoder
    "ENC_SHIFT_WIN": ("i", 400),                          # encoder
    "ENC_VREG": ("f", 5.0),                               # encoder
    "ENC_WARMUP": ("i", 800),                             # encoder
    "ENC_WARMUP_EPS": ("f", 0.015),                       # encoder
    "ENC_WARMUP_MIN": ("i", 3000),                        # encoder
    "ENC_WARMUP_PROBE": ("i", 500),                       # encoder
    "SIG_BATCH": ("i", 1),                                # encoder
    "SIG_D": ("i", 64),                                   # encoder
    "SIG_DIM": ("i", 512),                                # encoder
    "SIG_LOOK": ("i", None),                              # DEFAULT IS COMPUTED: ENC_EVERY_IDLE
    "SIG_MODE": ("env", "learned"),                       # encoder
    "SIG_PROJ_BPT": ("f", 2.4),                           # encoder
    "SIG_SPACE": ("env", "bytes"),                        # encoder
    "SIG_WIN": ("i", 0),                                  # encoder
    # --- world: world model / forward dynamics -----------------------------------------------------
    "WORLD_FEEDBACK": ("i", 1),                           # world
    "WORLD_GROW": ("i", 1),                               # world
    "WORLD_HID": ("i", 128),                              # world
    "WORLD_K": ("i", 1),                                  # world
    "WORLD_LAT": ("i", 32),                               # world
    "WORLD_MODEL": ("i", 1),                              # world
    "WORLD_N0": ("i", 3),                                 # world
    "WORLD_NMAX": ("i", 6),                               # world
    "WORLD_ROUTE": ("i", 24),                             # world
    "WORLD_VAR": ("f", 1.0),                              # world
    "WORLD_W": ("f", 0.1),                                # world
    # --- optim: optimiser, schedule and regularisation ---------------------------------------------
    "ACCUM": ("i", 1),                                    # optim
    "AMP": ("env", "off"),                                # optim
    "BAL_WARM": ("i", 4000),                              # optim
    "BATCH_W": ("i", 1),                                  # optim
    "DROPOUT": ("f", 0.0),                                # optim
    "LR": ("f", 2e-3),                                    # optim
    "LR_EPOCHS": ("i", 0),                                # optim -- cosine horizon in epochs; 0 = follow EPOCHS
    "LR_MIN_FRAC": ("f", 0.05),                           # optim
    "LR_SCHED": ("env", "cosine"),                        # optim
    "LR_WARMUP": ("i", 1000),                             # optim
    "SEED": ("i", 0),                                     # optim
    "TF32": ("i", 1),                                     # optim
    "WEIGHT_DECAY": ("f", 0.0),                           # optim
    # --- report: end-of-run measurement only -- nothing here changes training ----------------------
    "BENCH": ("i", 0),                                    # report
    "BEST_TRACK": ("i", 1),                               # report
    "COH_LEN": ("i", 384),                                # report
    "COH_N": ("i", 16),                                   # report
    "EVAL_N": ("i", 64),                                  # report
    "GEN_LEN": ("i", 200),                                # report
    "GEN_N": ("i", 4),                                    # report
    "GEN_PROCS": ("i", 4),                                # report
    "GEN_TEMP": ("f", 0.7),                               # report
    "HOLDOUT_N": ("i", 32),                               # report
    "PROBE": ("i", 1),                                    # report
    "PROBE_WAIT": ("i", 12),                              # report
    "PROFILE": ("i", 0),                                  # report
    "RATE_EVERY": ("i", 2000),                            # report
    # --- plumbing: paths, device, checkpointing ----------------------------------------------------
    "CKPT_EVERY": ("i", 0),                               # plumbing
    "DEVICE": ("env", "cpu"),                             # plumbing
    "D_MODEL": ("i", None),                               # plumbing -- DEFAULT IS COMPUTED: D_MODEL_B (alias)
    "D_MODEL_B": ("i", 128),                              # plumbing
    "HEADS": ("i", 8),                                    # plumbing
    "LAYERS": ("i", None),                                # DEFAULT IS COMPUTED: 4 transformer / 1 gru
    "MAXLEN": ("i", 512),                                 # plumbing
    "MODEL": ("env", "gru"),                              # plumbing
    "RESUME": ("env", ""),                                # plumbing
    "SAVE_CKPT": ("env", ""),                             # plumbing
    # --- misc: not yet grouped ---------------------------------------------------------------------
    "BIRTH_JITTER": ("env", 0.15),                        # misc
    "CENT_EMA": ("env", 0.02),                            # misc
    "COMP_EMA": ("f", 0.02),                              # misc
    "COMP_PROTECT": ("i", 1),                             # misc
    "CULL_MODE": ("env", "rank"),                         # misc
    "DECAY_EVERY": ("i", 20000),                          # misc
    "EVICT": ("env", "recency"),                          # misc
    "EXPERT_CULL_FRAC": ("f", 0.25),                      # misc
    "EXPERT_CULL_RANK": ("f", 0.08),                      # misc
    "EXPERT_CULL_STALE": ("i", 1000),                     # misc
    "EXPERT_FIT_WIN": ("i", 4000),                        # misc
    "EXPERT_GRACE": ("i", 3000),                          # misc
    "EXPERT_MERGE_DIST": ("f", 0.10),                     # misc
    "EXPERT_NEW_DIST": ("f", 0.5),                        # misc
    "EXPERT_NULLS": ("i", 20),                            # misc
    "EXPERT_PRESSURE": ("f", 0.75),                       # misc
    "FABRIC": ("i", 1),                                   # misc
    "GENERATE": ("i", 1),                                 # misc
    "GENUINE_MIN": ("i", 20),                             # misc
    "GENUINE_SIL": ("f", 0.10),                           # misc
    "GROW_BURST": ("i", 6),                               # misc
    "GROW_EVERY": ("i", 200),                             # misc
    "INFO_NULLS": ("i", 5),                               # misc
    "N_PROCESSES": ("i", 4),                              # misc
    "RECON_HID": ("i", 64),                               # misc
    "RECON_TOK": ("i", 32),                               # misc
    "TEMP": ("f", 0.1),                                   # misc
    "TOPK": ("i", 8),                                     # misc
    "USE_DECAY": ("f", 0.98),                             # misc
    "VAL_CAP": ("i", 4000000),                            # misc
    "WRITE_ADAPTIVE": ("i", 0),                           # misc
    "WRITE_GATE": ("f", 0.3),                             # misc
    "WRITE_QUANTILE": ("i", 1),                           # misc
    "WRITE_TARGET": ("f", 0.5),                           # misc
    "WRONG_CHECK": ("i", 1),                              # misc
    "WRONG_INJECT": ("i", 8),                             # misc
    "WRONG_MARGIN": ("f", 1.5),                           # misc
    "WRONG_MIN_N": ("i", 3),                              # misc
    "WRONG_SWEEP": ("i", 0),                              # misc
    "WRONG_THRESH": ("f", 1.0),                           # misc
}

def _env(k, d=None):
    _ENV_READ.add(k)
    # THE DECLARATION IS THE TABLE. A call site that disagrees with it is a bug -- it means the same knob means
    # two things depending on which code path reached it first, which is exactly how VMAX came to size one
    # tensor for 4096 tokens and another for 2048. Fail loudly at the read rather than quietly at the index.
    if k in _SPEC and k not in _SPEC_FREE and _SPEC[k][1] != d:
        raise SystemExit(f"[config] {k} is read with default {d!r} here but the registry declares "
                         f"{_SPEC[k][1]!r}. Change one of them; they cannot both be right.")
    if k in os.environ: _ENV_ASKED[k] = os.environ[k]
    return os.environ.get(k, d)
def _i(k, d): return int(_env(k, d))
def _f(k, d): return float(_env(k, d))
DEV = _env("DEVICE", "cpu")
VERIFY = _env("VERIFY", "selfcon")               # "selfcon" (old B, default, unchanged) or "recon" (Verification)
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
SIG_MODE = _env("SIG_MODE", "learned"); SIG_D = _i("SIG_D", 64); SIG_DIM = _i("SIG_DIM", 512)
# EVERY SUBSYSTEM ON BY DEFAULT. The audit that found FABRIC=0 found five more: the expanding tokenizer, the
# world model and its growth and feedback, and the per-expert memory partition were all off, so the "full
# system" this project has been measuring was the base LM plus memory plus domains and nothing else. A flag
# that defaults off is a decision nobody makes and everybody inherits -- the same failure as PHASED=0,
# MANAGE_MERGE=0.12, SEG_MIN/WIN and the BATCH_W cadences. Off is now the deliberate ablation.
# STILL OFF, for reasons rather than by oversight:
#   EXPERTS      mutually exclusive with FABRIC -- the forward pass is an elif chain and FABRIC wins, so
#                turning both on makes the expert bank a silent no-op. Exclusivity is arguably a bug; until
#                it composes, FABRIC is the one that carries the routing.
#   DISK_STREAM  a data-source choice, not a subsystem, and it fails without corpora on disk.
#   DOM_ADAPTIVE, DOM_RELATIVE, SHIFT_REL   each MEASURED worse than the constant they replace.
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
# MIRRORS THE EXPERT BANK -- and that invariant was broken by every launcher, which set MAX_DOMAINS=1000000 while
# leaving FAB_NMAX at its default 64. The two populations meant to be duals ran 15,625x apart: hundreds of domains
# routed through 64 experts, so expert granularity was coarser than domain granularity by more than two orders of
# magnitude and dom_exp affiliation was mapping many domains onto each expert. Defaulting to FAB_NMAX keeps them
# tied unless someone deliberately unties them.
MAX_DOMAINS = _i("MAX_DOMAINS", _i("FAB_NMAX", 4096))      # hard cap, mirroring the expert bank's slot pool
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
DOM_CULL_EMPTY = bool(_i("DOM_CULL_EMPTY", 1))   # cull a domain holding NO memory and NO windows, without waiting
#   for the act/stale conjunction that an empty domain can fail forever.
MANAGE_MIN = _i("MANAGE_MIN", 15); MANAGE_STALE = _i("MANAGE_STALE", 500)        #   cull domains < MIN windows unseen for STALE
COMP_EMA = _f("COMP_EMA", 0.02)            # EMA rate for per-domain / per-node COMPETENCE (bits on the material it wins)
FAB_SPAWN = bool(_i("FAB_SPAWN", 1))   # let the ROUTER specify an expert that does not exist and decode it into
#   being. The newborn's weights are edec(query), so the LM loss backpropagates through them into q_route: the
#   router is trained on what it ASKED FOR, not only on what it picked from what already existed.
FAB_AE_W = _f("FAB_AE_W", 0.5)        # weight on the weights->identity->weights round trip that keeps edec honest
FAB_KEY_NORM = bool(_i("FAB_KEY_NORM", 0))   # normalise the LEARNED routing term so it cannot swamp the grounded
#   region term. Principled but UNVALIDATED -- see Fabric.route_w. FAB_KEY_NORM=1 to A/B it.
FAB_DISCOVER = _f("FAB_DISCOVER", 0.35)   # cosine distance beyond which a signature counts as material NOTHING owns,
#   and is handed to the least-used expert rather than the nearest incumbent. 0 disables discovery-by-novelty.
FAB_REPLICATE = bool(_i("FAB_REPLICATE", 1))   # grow by CLONING the fittest expert (+jitter) rather than minting a
#   blank identity. A blank cannot earn traffic and so can never become competent -- see Fabric.grow.
COMP_PROTECT = bool(_i("COMP_PROTECT", 1))  # protect a unit that BEATS the population on its own material from culling,
#   however rarely it is used. COMP_PROTECT=0 restores pure-utilization selection (the ablation).
KW = _i("KEY_WIN", 8); V = 256
# DEFAULT OFF, on measurement. The goal it serves is real -- a minted token should start with parameters, at its
# composite, so the mint is a handover rather than a fresh random row -- and the mechanism does what it says. But
# the one run of it (pilot_gru_8, with TOK_MINT_NOVEL=0.5 also on) landed at 5.360 held-out, far outside the
# 2.0-2.4 band everything else sits in. TWO CAVEATS THE EARLIER VERSION OF THIS COMMENT DID NOT CARRY: that is
# ONE run with TWO flags on, so it convicts neither; and the band it was compared against was assembled from runs
# in DIFFERENT harness modes (pilot checkpoints, seeds does not), which we later found shifts a result by more
# than a bit/byte on its own. It stays available and stays off until an isolating run says which flag did it.
TOK_COMPOSE = bool(_i("TOK_COMPOSE", 0))                    # token vector = composite(bytes) + learned residual
TOK_ANCHOR = _f("TOK_ANCHOR", 0.05)                        # hold a new token near its composite, decaying
TOK_ANCHOR_TAU = _f("TOK_ANCHOR_TAU", 4000.0)              #   over this many steps of the TOKEN's own life
USE_TOK = bool(_i("TOKENIZER", 1)); TOK_ONLINE = bool(_i("TOK_ONLINE", 1)); TOK = None; BLEN = None   # TOK_ONLINE=1 mints during training
torch.manual_seed(_i("SEED", 0)); random.seed(_i("SEED", 0))
# ---- GPU PRECISION (no functionality is removed by either knob; both only change how matmuls are executed) ----
# TF32: on by default for cuDNN but NOT for matmul in current torch, so the fp32 path leaves most of an H100's matmul
# throughput unused. AMP=bf16 additionally runs the LM step in bfloat16 -- same exponent range as fp32 (so no loss
# scaling and no GradScaler), which is the standard training precision on H100-class hardware.
if bool(_i("TF32", 1)):
    torch.backends.cuda.matmul.allow_tf32 = True; torch.backends.cudnn.allow_tf32 = True
AMP = _env("AMP", "off").lower()                 # "off" (default) | "bf16" | "fp16"


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
DATA_MODE = _env("DATA_MODE", "synthetic")
if USE_TOK and DATA_MODE != "real":
    raise SystemExit("TOKENIZER=1 requires DATA_MODE=real -- the tokenizer is only built on the real-data path,\n"
                     "  so the synthetic path leaves TOK=None and dies later inside _retok with a bare\n"
                     "  AttributeError. Add DATA_MODE=real (and DATA_DIR=...) to your command.")
if DATA_MODE == "real":
    DN = _env("DOMAINS", "eng,py,num,c").split(",")
    DISK_STREAM = bool(_i("DISK_STREAM", 0))              # mmap the corpus (disk-paged) so training data can EXCEED RAM (GPT-2 scale)
    from datastream import open_corpus
    CORP = open_corpus(_env("DATA_DIR", "data"), DN, cap=_i("CORPUS_CAP", 2000000), disk=DISK_STREAM)
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
        _tp = _env("TOKENIZER_PATH", "data/dyntok.json")
        VMAX = _i("VMAX", 4096)
        _target = _i("SEED_VOCAB", 512) if TOK_ONLINE else VMAX            # online: only SEED here; keep minting during training
        _passes = _i("SEED_PASSES", 2) if TOK_ONLINE else _i("GROW_PASSES", 8)
        if os.path.exists(_tp) and (not TOK_ONLINE or _env("RESUME", "")):
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
    # HOW A SEGMENT IS DRAWN. Random-offset was the only mode, and on a MULTI-corpus splice that is right: each
    # phase should sample fresh material from whichever corpora are active. On a SINGLE corpus it is wrong, and
    # quietly so. seg_from seeks to a random point every SEG_MIN..SEG_MAX bytes, so an English-only stream jumps
    # elsewhere in English every 8-20 KB -- discontinuities WE manufacture, at a spacing WE choose. The assembler
    # then discovers domains at our seek points. That is how eng_only reported 71 domains at SEG_MIN=700: it was
    # partly counting our splices.
    # CONTIGUOUS reading removes them. The corpus is read in order, so the only boundaries left are the ones in
    # the text -- document ends, topic changes, register shifts -- which is what "domains appear organically in
    # English" has to mean. Default: contiguous when there is ONE corpus, random when there are several (that is
    # the splice experiment, and changing it would silently invalidate every earlier comparison).
    SEG_CONTIG = bool(_i("SEG_CONTIG", 1 if NP == 1 else 0))
    _CUR = [0] * NP                                        # read cursor per corpus; persists ACROSS epochs, so epoch
    #   N+1 continues where N stopped instead of re-reading the same head -- which is also how a 20 GB corpus gets
    #   streamed in order rather than seek-sampled.
    def seg_from(p, L):
        if not SEG_CONTIG:
            s = random.randint(0, SEG_LEN[p] - L - 1); return CORP[p][s:s + L]   # SEG_LEN bounds sampling to the train head
        s = _CUR[p]
        if s + L >= SEG_LEN[p]: s = 0                      # wrap at the end of the training head
        _CUR[p] = s + L
        return CORP[p][s:s + L]
    if SEG_CONTIG:
        print(f"[stream] CONTIGUOUS read: the corpus is consumed in order, so segment boundaries are the TEXT's, "
              f"not seek points we chose. SEG_CONTIG=0 for the random-offset splice.")
else:
    PROCS = [make_proc(s, ALPHA[s % len(ALPHA)]) for s in range(NP)]
    def seg_from(p, L): return PROCS[p](L)

# NON-STATIONARY BY DEFAULT, because that is the only stream that tests the thesis. A stationary i.i.d. splice of
# N corpora does not require continual learning at all -- it is ordinary training with extra machinery, and every
# number this project has reported was measured on it. PHASED shipped in the first commit defaulted to 0, sat
# alongside the ablation flags, and was never once turned on; when finally run it showed faded material +0.65
# bits/byte worse than a stationary control with 100% of its memory evicted, and the "unlearn a faded process"
# arm skipping itself as vacuous. Leaving it off is now the deliberate ablation (PHASED=0), not the default.
PHASED = bool(_i("PHASED", 1))                             # NON-STATIONARY stream: processes ENTER and FADE over time


def _phases(n, p=None, w=None):
    """Who is active in each phase -- GENERATED FROM A RULE, not looked up in a table.

    A sliding window of `w` processes over `n`, across `p` phases. Every process enters, is active for a
    contiguous stretch, and fades; the last phase excludes at least one process whenever n > 1, which matters
    because `faded` is computed from PHASE_SCHED[-1] and a schedule ending with everything active makes the
    unlearn-a-faded-process test skip itself as vacuous.

    This replaced a per-n lookup table, which replaced a single fixed 4-process list. Both were arbitrary in
    exactly the way the splice itself is arbitrary: WE chose who was active when, and then measured the system
    against our choice. A rule at least applies the same shape at any n, and PHASE_SCHED= overrides it outright
    when a specific schedule is wanted:
        PHASE_SCHED="0|0,1|0,1|1"      explicit, pipe-separated phases
        PHASES=6 PHASE_W=2             six phases, two processes live at a time
    n <= 1 is genuinely stationary and says so: one corpus cannot have processes enter and fade. On that
    configuration the non-stationarity has to come from ADDING an area later, which is the real test anyway --
    a spliced phase schedule is our scaffold, a new corpus arriving is not."""
    p = p or max(2, _i("PHASES", 4))
    if n <= 1: return [[0] if n else []] * p
    w = w or max(1, min(n, _i("PHASE_W", (n + 1) // 2)))
    if w >= n: w = n - 1                                   # never all-active: something must be able to fade
    out = []
    for i in range(p):
        lo = round(i * (n - w) / max(1, p - 1))             # window slides from the first process to the last
        out.append(list(range(lo, lo + w)))
    return out


def _phases_env(n):
    """PHASE_SCHED= wins over the generator. Parsed here so a bad value fails loudly at startup rather than
    producing a silently different experiment."""
    raw = _env("PHASE_SCHED", "").strip()
    if not raw: return _phases(n)
    try:
        sched = [[int(x) for x in ph.split(",") if x != ""] for ph in raw.split("|")]
        if not sched or any(not ph for ph in sched): raise ValueError("empty phase")
        if any(j < 0 or j >= n for ph in sched for j in ph): raise ValueError(f"process id outside 0..{n-1}")
        return sched
    except ValueError as e:
        raise SystemExit(f"PHASE_SCHED={raw!r} is not usable ({e}). Format: \"0|0,1|0,1|1\" -- "
                         f"pipe-separated phases, comma-separated process ids in 0..{n-1}.")


PHASE_SCHED = _phases_env(NP)                                  # rebuilt after NP is known on the real-data path (below)
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
MODEL_TYPE = _env("MODEL", "gru")               # "gru" (default) or "transformer" (scales to H100)
DROPOUT = _f("DROPOUT", 0.0)                               # ANTI-OVERFIT, default OFF. The model is currently badly
ENC_VREG = _f("ENC_VREG", 5.0); ENC_CREG = _f("ENC_CREG", 0.0)   # read ONCE, at module level, so the
#   banner and the encoder loss cannot disagree about what regularisation ran.
WEIGHT_DECAY = _f("WEIGHT_DECAY", 0.0)                     # UNDERFIT (more passes keep helping), so these would only
                                                           # handicap it. Turn them on when val-vs-train shows a gap.

# === TOKENS AS THEIR OWN CONTENT ==============================================================================
# A minted token currently gets an arbitrary sequential id and a FRESH ROW in the embedding and the head, which
# somebody then has to initialise -- that is the whole WARMSTART machinery, and it is why every mint costs the
# model something to recover from.
# Literal integer-valued ids (id = the token's bytes read as an integer) cannot index a table: max_tok=16 makes
# that a 128-bit number. But the property that makes the idea good survives without them. If the id determines
# the BYTES -- which it already does, via TOK.id2bytes -- then the token's representation can be COMPUTED from
# those bytes instead of stored. A new token then has no parameters of its own, so:
#   nothing to initialise, so no warm start and no WARMSTART_MODE question
#   no new parameters appear mid-run, so minting stops being a moving target for the optimizer
#   no VMAX: the vocabulary can grow as far as the tokenizer wants
#   a token that shares bytes with known tokens starts out near them, automatically
# The cost is that every token's row is now a function of 256 byte embeddings, so tokens can no longer be
# arbitrarily unrelated to each other -- which is the point, not a limitation.
class ByteComposer(nn.Module):
    """token id -> vector, computed from the token's BYTES. 256 byte embeddings plus a length term, pooled and
    projected. The output doubles as the input embedding table and (tied) the output head, so a vocabulary of any
    size costs the same parameters."""
    def __init__(s, d, maxb=16):
        super().__init__()
        s.d = d; s.maxb = maxb
        s.byte = nn.Embedding(256, d)
        s.pos = nn.Embedding(maxb, d)                      # WHERE in the token a byte sits: "ab" != "ba"
        s.length = nn.Embedding(maxb + 1, d)
        s.proj = nn.Sequential(nn.LayerNorm(d), nn.Linear(d, d))
        s.bias = nn.Linear(d, 1)                           # the composed part of the per-token output bias
        # === PER-TOKEN PARAMETERS, STARTING AT THE COMPOSITE ==================================================
        # The composition is the STARTING POINT, not the whole representation. Each token also owns a free
        # residual, zero-initialised, so at the instant "ab" is minted its vector is exactly what its bytes
        # compose to -- and its bytes are its parts -- and from there it learns its own identity by moving away.
        # That is the transition this is for: mint is continuous, because a token begins as its composite and
        # becomes itself gradually, instead of appearing as a fresh row that has to be guessed at.
        s.delta = nn.Parameter(torch.zeros(int(_env("VMAX", 4096)), d))
        s.dbias = nn.Parameter(torch.zeros(int(_env("VMAX", 4096))))
        s.born = None                                      # per-token birth step, for the anchor below
        s._idx = None; s._msk = None; s._cache = None; s._v = -1
    def note_born(s, ids, step):
        if s.born is not None:
            for _i in ids:
                if 0 <= _i < s.born.numel() and int(s.born[_i]) < 0: s.born[_i] = step

    def set_vocab(s, id2bytes, dev, vmax=None):
        """Called whenever the vocabulary changes. Builds the (V, maxb) byte-index tensor once per change.
        SIZED TO VMAX, not to the live vocabulary: the table has no per-token parameters, so the unused rows cost
        nothing, and sizing it to the live count means any lag between a mint and this call is an IndexError on
        the training stream. Unassigned ids get an all-zero mask and never appear in the stream anyway."""
        _V = max(len(id2bytes), int(vmax or 0))
        id2bytes = list(id2bytes) + [b""] * (_V - len(id2bytes))
        idx = torch.zeros(_V, s.maxb, dtype=torch.long)
        msk = torch.zeros(_V, s.maxb)
        for i, bs in enumerate(id2bytes):
            b = bs[:s.maxb]
            if b:
                idx[i, :len(b)] = torch.tensor(list(b), dtype=torch.long)
                msk[i, :len(b)] = 1.0
        _prev = 0 if s.born is None else int(s._v)
        _b = torch.full((_V,), -10**9, dtype=torch.long)
        if s.born is not None: _b[:min(_prev, _V)] = s.born[:min(_prev, _V)].cpu()
        s.born = _b.to(dev)
        s._idx = idx.to(dev); s._msk = msk.to(dev)
        s._len = s._msk.sum(-1).long().clamp(max=s.maxb).to(dev)
        s._v = _V; s._cache = None
    def table(s):
        """(V, d) -- every token's vector, and the bias. Recomputed each call so gradient reaches the bytes."""
        m = s._msk[:, :, None]
        e = (s.byte(s._idx) + s.pos.weight[None, :s.maxb, :]) * m
        pooled = e.sum(1) / m.sum(1).clamp_min(1.0)
        _c = s.proj(pooled + s.length(s._len))
        _n = _c.size(0)
        w = _c + s.delta[:_n]                              # composite + what this token has learned to be
        return w, (s.bias(_c).squeeze(-1) + s.dbias[:_n])

    def anchor(s, step, tau):
        """HOLD A NEW TOKEN NEAR ITS COMPOSITE, then let go. A freshly minted token has delta=0, so it IS its
        composite; without this it is free to be dragged anywhere by the first gradients it sees, which is the
        same discontinuity the old fresh-random row had, just starting from a better place. Penalising its
        residual with a weight that decays over `tau` steps of the token's own life makes the handover gradual:
        strongly anchored while it is new, free once it has seen enough of its own material to deserve to be."""
        if s.born is None or s._v <= 0: return None
        _age = (step - s.born[:s._v]).clamp_min(0).float()
        _w = torch.exp(-_age / max(1.0, tau))
        if float(_w.max()) < 1e-3: return None             # nothing young enough to hold
        return (_w[:, None] * s.delta[:s._v].pow(2)).sum(-1).mean()

class MiniLM(nn.Module):                                   # base LM (GRU, optionally multi-layer)
    def __init__(s, d, layers=1, nv=None):
        super().__init__(); s._V = nv or V
        s.compose = ByteComposer(d) if TOK_COMPOSE else None
        s.emb = nn.Embedding(s._V, d); s.drop = nn.Dropout(DROPOUT)
        s.gru = nn.GRU(d, d, num_layers=layers, batch_first=True, dropout=(DROPOUT if layers > 1 else 0.0))
        s.head = nn.Linear(d, s._V)
    def _tbl(s):
        if s.compose is None or s.compose._idx is None: return None
        return s.compose.table()
    def encode(s, x):
        _t = s._tbl()
        _e = (_t[0][x] if _t is not None else s.emb(x))     # composed table indexes exactly like an Embedding
        h, _ = s.gru(s.drop(_e)); return s.drop(h)          # (B,L,D) hidden -- also the memory-key source
    def forward(s, x):
        h = s.encode(x); _t = s._tbl()
        return ((h @ _t[0].t() + _t[1]) if _t is not None else s.head(h)), h
class TinyTransformer(nn.Module):                          # decoder-only Transformer (causal) -- the H100-scale option
    def __init__(s, d, layers=4, heads=8, maxlen=512, nv=None):
        super().__init__(); s._V = nv or V
        s.emb = nn.Embedding(s._V, d); s.pos = nn.Embedding(maxlen, d); s.maxlen = maxlen
        lyr = nn.TransformerEncoderLayer(d, heads, dim_feedforward=4 * d, batch_first=True, dropout=0.0, activation="gelu", norm_first=True)
        # norm=LayerNorm(d): with norm_first=True the FINAL sublayer output is never normalised, which is fine at
        # L1-L4 and progressively worse with depth -- GPT-2 has this final norm. prompt.py MUST match or every
        # saved checkpoint loads into a different network.
        s.tr = nn.TransformerEncoder(lyr, layers, norm=nn.LayerNorm(d), enable_nested_tensor=False)
        s.head = nn.Linear(d, s._V)
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
def build_lm(nv=None):
    """nv OVERRIDES the module-level vocabulary so a loader can size the model from a CHECKPOINT. Without it every
    consumer had to reimplement these classes, which is exactly how prompt.py went stale and stopped working."""
    if MODEL_TYPE == "transformer":
        return TinyTransformer(D, layers=_i("LAYERS", 4), heads=_i("HEADS", 8), maxlen=_i("MAXLEN", 512), nv=nv)
    return MiniLM(D, layers=_i("LAYERS", 1), nv=nv)
# ON by default. It was 0, nobody set it, and so the routed expert population -- the core of the architecture --
# was ABSENT from every run of this project: "fabric nodes 0" in every phase table, no FABRIC section in any
# report, and every conclusion about domains, coherence and bits/byte drawn from a system missing its routing
# layer. Same failure class as PHASED=0, MANAGE_MERGE=0.12 and the BATCH_W cadences.
# Measured, English, 120 kB, everything else identical:
#   FABRIC=0  held-out 3.543  -> LOSES to order-1 (3.495) by 0.048
#   FABRIC=1  held-out 3.441  -> BEATS order-1 by 0.054;  fabric contributes +0.709 bits/byte
# +0.709 is four times what the memory contributes and the largest single component effect measured here.
# Read with the caveat the FABRIC section itself prints: at these settings the router HALTs 90% of the time
# and mean routed depth is 0.10 of 4 steps, so the gain is the population being PRESENT, not the routing
# working. Fixing the router is a separate question from having one at all.
FABRIC = bool(_i("FABRIC", 1))                             # FABRIC=1: the routed expert population
ENS_K = _i("ENS_K", 2)                                     # how many experts are ensembled at the output layer
# DEFAULT: CHAINING. 0 = experts COMPOSE -- routing mass flows expert -> expert through a learned transition over
# multiple hops, HALT absorbing, so expert i can build on expert j's output. 1 = the society: independent experts
# blended at the prediction level, one hop, nobody sees anybody.
# This default was 1 for every run this project has made, which meant the composition machinery was written,
# debugged and reported on while never once running in a training step. Composition is the point of the design, so
# it is what runs unless SOCIETY=1 says otherwise.
SOCIETY = bool(_i("SOCIETY", 0))
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
        # === THE POPULATION, AS TENSORS =========================================================================
        # Three things capped this at 64, and none of them was a design decision.
        #   PARAMETERS. A FabricNode was a full residual MLP d -> 2d -> d: 2.36M parameters at d=768. A thousand
        #     experts is 2.36B parameters (9.5 GB fp32); a million is 9.4 TB. The low-rank form d -> r -> d that
        #     ExpertBank already uses is 12.3k at r=8 -- a million experts is 12.3B (49 GB), which is reachable.
        #     Each expert is individually far weaker, which is the point: no single one is meant to suffice.
        #   PYTHON. keys was a ParameterList and qproj a ModuleList, so every step ran
        #     torch.stack(list(s.keys)) and [q(gist) for q in s.qproj] -- O(N) Python object iteration per step.
        #     Invisible at 64, dominant at 10,000. They are single tensors now, so routing is two matmuls at any N.
        #   SLOTS. Growth appends, which reallocates, which invalidates the optimizer's parameter references.
        #     Preallocating to FAB_NMAX avoids that entirely: the tensors never change identity, only `n` grows.
        #     Unused rows are zero in B, i.e. exact identities, so they cost memory and nothing else.
        # Cost is 2*NMAX*d*r floats: 0.5 GB at NMAX=10k, 49 GB at 1M. That is the number to size against.
        s.r = max(1, int(_env("FAB_RANK", 8)))
        cap = max(n0, int(_env("FAB_NMAX", 4096)))
        s.cap = cap; s.n_live = n0
        s.A = nn.Parameter(torch.randn(cap, d, s.r) * (d ** -0.5))
        s.B = nn.Parameter(torch.zeros(cap, s.r, d))        # zero -> every expert is born an IDENTITY, so adding one
        #   never disrupts what already works. Same principle the full-MLP node used with its zero-init second layer.
        s.register_buffer("cent", F.normalize(torch.randn(cap, sig_d), dim=-1))   # one region per expert. BUFFER, not a
        #   plain attribute: as an attribute it was absent from state_dict(), so the GROUNDED router's centroids -- which
        #   ARE the routing function when ROUTE_GROUNDED=1 (the default) -- were never saved, never resumed, and never
        #   moved to the GPU. prompt.py therefore routed every generation with untrained centroids.

        # SHARED query projection, per-expert KEY -- i.e. actual attention over the population. Giving every expert
        # its own sig_d x dk query matrix made scoring O(N*sig_d*dk): measured 1.7 ms at N=64 but 345 ms at N=65536,
        # so the population was affordable in PARAMETERS and unaffordable in TIME. One shared projection makes it
        # O(N*dk) -- and it also drops per-expert parameters by a third, since QW was 2048 of the 6208 floats an
        # expert cost at d=256. The score is still bilinear and still per-expert; only the query is shared, which is
        # what every attention mechanism does.
        s.q_route = nn.Linear(sig_d, dk)
        # WHAT THE ROUTER CANNOT SEE. The transition query is q_route(gist) + SRC[holder] + ctrl(summary). `gist`
        # is the INPUT signature -- identical at every hop -- SRC says WHICH expert holds the state but nothing
        # about what it produced, and ctrl is three scalars. So the hop-2 query is very nearly a fixed function of
        # the hop-1 holder, and the router has no way to ask "given what the computation looks like NOW, what
        # next?". Measured: I(domain; (hop0,hop1) pair) equalled I(domain; hop0) to three decimals on every seed,
        # i.e. the second choice carried zero independent information. hproj puts the CURRENT STATE in the query.
        s.hproj = nn.Linear(d, dk)
        # OUTGOING SIGNATURE, one per expert. K[m] is where a message may be SENT; SRC[n] is the mark expert n puts
        # on a message it emits. Together they make the transition depend on WHO IS HOLDING THE MASS:
        #     R[n -> m] = softmax( (q_route(gist) + SRC[n] + ctrl(summary)) . K[m] )
        # The original carried this as a per-expert Linear(sig_d, dk) -- a full matrix each -- which is O(N.sig_d.dk)
        # to evaluate and was the 345 ms at N=65536 that made me collapse it to ONE shared query. That collapse
        # made R identical for every source: verified directly, all mass on expert 0 and all mass on expert 4 give
        # the SAME next distribution. The chain kept composing in h and stopped being a chain in the routing.
        # A dk-vector per expert restores per-source routing at O(N.dk) -- 32 floats each instead of a matrix.
        # EXPERT EMBEDDERS: routing identity is DERIVED FROM THE EXPERT'S OWN WEIGHTS, in their entirety.
        # K and SRC were free parameters -- they described an expert without being derived from it, so what an
        # expert DOES and where it is ROUTED drifted independently: an expert could learn something new and keep
        # the key that sent it the old material, or keep a key nothing matched while its weights were fine.
        # Running the full adapter (A and B flattened, 2*d*r numbers, nothing summarised) through a dedicated
        # embedder makes identity a function of function. Consequences that fall out rather than being coded:
        # a replicated child is near its parent in routing space because its WEIGHTS are near; an expert that
        # mutates moves its own key; a culled slot cannot leave a stale identity behind.
        # A SEPARATE embedder, used only for experts -- it is not the SigEncoder and never sees the stream.
        s.eemb = nn.Sequential(nn.Linear(2 * d * s.r, int(_env("FAB_EMB_HID", 128))), nn.GELU(),
                               nn.Linear(int(_env("FAB_EMB_HID", 128)), 2 * dk))
        # THE DECODER: identity -> weights. With eemb the router can RECOGNISE an expert by what it is; with edec
        # it can SPECIFY one. The router already emits a query in identity space (q_route(gist)) that is matched
        # against every K. Read that query as "the expert I want": route to the nearest if one is close, and if
        # NOTHING is close, decode the query into actual weights and create the expert that was asked for.
        # Discovery stops being "hand the odd material to whoever is idle" and becomes "build what was specified".
        # And because the newborn's weights ARE edec(query), the LM loss backpropagates through those weights into
        # q_route -- so the router is trained on what it asked for. It learns to specify, not just to select.
        s.edec = nn.Sequential(nn.Linear(dk, int(_env("FAB_EMB_HID", 128))), nn.GELU(),
                               nn.Linear(int(_env("FAB_EMB_HID", 128)), 2 * d * s.r))
        s.emb_var = float(_env("FAB_EMB_VAR", 1.0))   # variance+decorrelation on the identity embeddings
        s.spawn_mult = float(_env("FAB_SPAWN_MULT", 2.0))   # query must be this many times the population's
        #   own typical nearest-neighbour distance away before it counts as material nothing serves
        s.spawn_floor = float(_env("FAB_SPAWN_FLOOR", 0.02))  # absolute floor, so a degenerate population
        #   (every identity identical -> typ = 0) cannot spawn on every single query
        s._spawn_gap = s._spawn_typ = 0.0
        s.spawned = 0
        # DEFAULT 1 (was 50, and inert on the society path because that path never passed step=). >1 makes the
        # routing keys stale AND throttles the identity gradient channel to 1-in-N steps -- see _ids. Raise it only
        # if the embed is measured to be the bottleneck, and read GRADIENT REACH in the report when you do.
        s.emb_every = max(1, int(_env("FAB_EMB_EVERY", 1)))   # recompute cadence: O(N * 2*d*r * hid) is real
        s._kc = None; s._kcl = None; s._kstep = -10**9; s._kn = -1
        s.derive_ids = bool(int(_env("FAB_DERIVE_IDS", 1)))
        s.SRC_p = nn.Parameter(torch.randn(cap, dk) * 0.1)       # fallback identities when FAB_DERIVE_IDS=0
        s.K_p = nn.Parameter(torch.randn(cap, dk) * 0.1)
        s.halt_key = nn.Parameter(torch.randn(dk) * 0.1)
        # HALT ON THE SOCIETY PATH. HALT used to exist only inside the chaining loop, where it is an ABSORBING
        # operator that ends the walk. On the society path it was COMPUTED AND THROWN AWAY: the learned branch of
        # route_w built a distribution over N+1 operators and then sliced off column N, and the grounded branch had
        # no HALT operator at all. So the router could choose WHICH experts answer but never WHETHER they should --
        # every window went through the population whether or not the population had anything to add, and the base
        # model's own head was unreachable except by ablation.
        # HALT is now a real operator in both branches. Its mass says "no expert is needed here"; the caller spends
        # that mass on model.head(h) directly, so the router owns the completion decision on both paths.
        s.halt_b = nn.Parameter(torch.zeros(1))            # prior on halting, learned; 0 = whatever the query says
        s.halt_on = bool(int(_env("FAB_HALT", 1)))
        s.halt_max = float(_env("FAB_HALT_MAX", 0.9))   # BARRIER, not a preference. At halt=1 the experts
        #   receive no gradient at all, and an expert that receives no gradient can never become worth routing to --
        #   the same trap top-k exploration exists to avoid. Clamping leaves >=10% of the blend on the population,
        #   so a bad early halt is recoverable rather than absorbing.
        s.halt_ema = None                                  # running mean halt mass, for the report (kept on device)
        s._halt = None                                     # (B,1) halt mass from the last route_w call
        # BREADTH CAP: how many DOMAINS one expert may serve, as a fraction of the live domain population.
        # Without it a handful of experts absorb everything -- which is exactly what the affiliation map showed when
        # hundreds of domains routed through 64 experts. A percentage rather than a count because the domain
        # population is itself grown and culled: a fixed ceiling would be permissive early and crushing later.
        s.dom_of = {}                                      # expert -> set of domains it has actually served
        s.use = {}                                         # expert -> windows won (UTILIZATION)
        s.parent = {}                                      # expert -> the expert it was replicated FROM
        s.replicated = 0
        s.parent_k = int(_env("FAB_PARENT_K", 8))     # shortlist size: how many region-owners compete to breed
        s.mut = float(_env("FAB_MUT", 0.25))          # mutation as a FRACTION of the parent's own std
        s.mut_big = float(_env("FAB_MUT_BIG", 6.0))   # heavy tail: occasional large jump
        s.mut_big_p = float(_env("FAB_MUT_BIG_P", 0.1))
        s.mutscale = {}
        s.discovered = 0; s.crossed = 0; s.explored = 0; s.failed_out = 0
        s.ef = {}; s.es = {}                               # per-expert FAST / SLOW error EMAs
        s.ef_a = float(_env("FAB_ERR_FAST", 0.05))
        s.es_a = float(_env("FAB_ERR_SLOW", 0.005))
        s.shift_tol = float(_env("FAB_SHIFT_TOL", 0.05))   # fast above slow by this -> adapting, protect
        s.fail_tol = float(_env("FAB_FAIL_TOL", 0.15))     # both ends above the population -> failing
        s.births = {}                                      # parent -> recent births (sliding, halved when full)
        s.births_win = int(_env("FAB_BIRTH_WIN", 256))
        s.parent_max = float(_env("FAB_PARENT_MAX", 0.20))  # max share of recent births per parent
        s.chain_k = int(_env("FAB_CHAIN_K", 8))   # experts COMPUTED per chaining hop (was: all of them)
        # === STAGED DEPTH ===================================================================================
        # THE ORDER PROBLEM, and THREE ATTEMPTS AT IT THAT DID NOT WORK. All three default OFF. They are kept as
        # flags, not deleted, because the problem is real and the next attempt should start from what was measured
        # rather than repeat it.
        #
        # The structural facts are not in doubt. A depth-D chain over N experts has N^D orderings; the only loss is
        # one cross-entropy at the END of the walk, diluted back through every later hop's LayerNorm and mixture;
        # and topk's INDICES are not differentiable, so the gradient can say "weight the expert you already picked
        # more or less" but never "you should have gone somewhere else".
        #
        # Measured on a task where each domain needs an ORDERED pair of transforms (6 domains, 24 experts, depth 4,
        # 3 seeds), uniform-guess loss 3.871:
        #     baseline                          loss 2.52 / 3.00 / 2.72
        #     CHAIN_SUP=0.3  (per-hop loss)     loss 3.17 / 3.50 / 3.64   consistently WORSE
        #     CHAIN_CURRIC=1 (staged depth)     depth rarely left 1; where it reached 2, worse
        #     CHAIN_STATE_Q=1 (state in query)  loss 2.79 / 2.71 / 2.74   neutral
        #
        # A CORRECTION ON THE DIAGNOSIS. The observation that prompted this was I(domain; (hop0,hop1)) equalling
        # I(domain; hop0) to three decimals, read as "the second hop carries zero information". That reading is
        # wrong: I(dom; pair) >= I(dom; hop0) always, and when hop0 already identifies the domain at ~0.83 the
        # metric is saturated, so equality is what CORRECT behaviour looks like too. If the domain determines the
        # right pair, hop1 being a deterministic function of hop0 is the answer, not the failure. The metric that
        # would actually settle it is H(hop1 | hop0, domain) -- whether the chain can vary its second move for the
        # same first move when the material calls for it -- and that has not been measured.
        #
        # So: the concentration is real and measured (25 distinct experts against society's 487 in the pilot); the
        # claim that per-hop credit assignment is what causes it is NOT established, and these three interventions
        # are evidence against it.
        # TWO CHANGES LANDED BETWEEN PILOT 6 (+1.438) AND THE GRID (+2.287) AND WERE NEVER SEPARATED: the
        # breadth-cap ban began masking the chaining path's logits, and the growth ramp started latching off.
        # Both are scoring/selection changes, both are plausible causes of that regression, and both are now
        # flags rather than facts so one grid can tell them apart.
        s.chain_ban = bool(int(_env("CHAIN_BAN", 1)))     # dom_ban applied on the chaining path
        s.region_w = float(_env("ROUTE_REGION_W", 1.0))   # 0 = route on PREDICTED WEIGHTS ONLY
        s.state_q = bool(int(_env("CHAIN_STATE_Q", 0)))   # transition query sees the CURRENT state
        s.curric = bool(int(_env("CHAIN_CURRIC", 0)))
        s.depth_now = int(_env("CHAIN_DEPTH0", 1)) if s.curric else max_steps
        s.dp_best = None; s.dp_wait = 0; s.dp_seen = 0
        s.dp_stage_max = int(_env("CHAIN_STAGE_MAX", 40))   # checks before a stage ends regardless
        s.dp_patience = int(_env("CHAIN_PATIENCE", 6))   # plateau checks before adding a hop
        s.dp_eps = float(_env("CHAIN_EPS", 0.01))        # improvement that counts as progress
        s.deepened = []                                            # (step, new depth) for the report
        s.sup_w = float(_env("CHAIN_SUP", 0.0))          # per-hop deep supervision weight
        s._hops = []                                               # per-hop hidden states, for that supervision
        s._hopq = []                                               # per-hop router queries, for per-hop spawn
        # DIV_W is a LOCAL in main(), so Fabric.forward could not see it -- a NameError on the first chaining hop
        # that would have killed every chaining arm. Read it here, from the same env var and the same default.
        s.div_w = float(_env("DIV_W", 0.0))
        # === SOCIETY x CHAINING: multi-hop, but blended at the PREDICTION level =============================
        # The two paths differ in TWO independent ways and the grid only ever tested them together:
        #   depth      one hop (society) vs many (chaining)
        #   where the experts are combined -- at the PREDICTION (society: sum_i w_i * head(o_i)) or in the
        #              HIDDEN STATE (chaining: h <- mix of expert outputs, decoded once at the end)
        # Society won the grid outright and chaining lost to FABRIC=0 entirely. This runs the multi-hop structure
        # with the society's combination rule: at every hop the experts vote on the OUTPUT, and h still carries
        # each hop's result into the next, so composition survives.
        #
        # IT IS ALSO THE ONLY THING THAT GIVES HALT A JOB. Today _alive merely scales the residual update and only
        # h_final is decoded, so HALT's gradient answers "how much fabric do I want at all" and never "when am I
        # done" -- PONDER=0.01 is the sole pressure toward stopping and it measured 0.0000 in all 18 arms. Here the
        # mass that halts AT HOP t selects hop t's prediction, so stopping early is rewarded exactly when later
        # hops are worse. The accumulation is a convex combination by construction: entry-halt + sum of newly
        # halted per hop + never-halted = 1.
        # HOW EACH HOP PICKS ITS EXPERTS.
        #   "transition"  the learned transition matrix: route FROM the current holder, via its SRC mark. This is
        #                 what "chaining" has always meant here, and it is where the rail comes from --
        #                 H(hop1 | hop0) measured 0.007-0.058 bits in every arm, i.e. one decision then a fixed
        #                 successor, because the query is dominated by the holder's identity and a signature that
        #                 does not change between hops.
        #   "soc"         re-route from scratch every iteration with the SOCIETY router -- the same grounded +
        #                 weight-prediction scoring society uses -- with the CURRENT STATE in the query. No
        #                 transition matrix and no SRC. This is "run the society, feed the result back in, run it
        #                 again", which is a different architecture from chaining and has never been run.
        # DEFAULT: soc. The society, looped. It is the only configuration that has produced real multi-hop
        # routing -- H(hop1 | hop0) = 0.533 bits over 202k transitions against 0.005-0.058 for every arm that used
        # the transition matrix -- and it restores society-class stability (+0.683 since minimum, against +2.287
        # for transition chaining). CHAIN_ROUTE=transition for the old learned-successor walk.
        s.loop_soc = (_env("CHAIN_ROUTE", "soc") == "soc")
        # DEFAULT ON, and it has to be: soc-loop routes each round from the current state and lets HALT choose
        # when to answer, which only means anything if each round's experts actually VOTE on the output. With
        # CHAIN_VOTE=0 the rounds are mixed in the hidden state and decoded once, and HALT measured 0.0000 in all
        # 18 grid arms because stopping early bought it nothing.
        s.vote = bool(int(_env("CHAIN_VOTE", 1)))
        s._votelg = None; s._vchk = 0
        # ONE SOURCE OF TRUTH FOR min_steps. Forcing it off inside forward() with a local conditional left
        # s.min_steps reading 2 while the effective value was 0 -- and the [config] banner, the CHAINING report
        # section and the CHECKPOINT all print or save it. That is the same class of lie the banner rewrite was
        # supposed to make impossible; a value that is overridden must be overridden where it lives.
        # ...AND IT IS AN OVERRIDE, NOT A DEFAULT. Under CHAIN_VOTE the hop that halts SELECTS that hop's
        # answer, so "block HALT for the first N hops" has no meaning and 0 is the only coherent value. But
        # CHAIN_VOTE defaults to 1, so an explicit FAB_MIN_STEPS=2 was accepted, printed in the banner, saved
        # to the checkpoint -- and discarded. A knob that cannot be set must say so rather than agree and then
        # do something else. Refused on the same contract as a registry default mismatch: they cannot both be
        # right. Nothing that has run sets both, so this refuses no configuration anyone has used.
        if s.vote:
            _fms = os.environ.get("FAB_MIN_STEPS", "")
            if _fms.strip() not in ("", "0") and min_steps:
                raise SystemExit(
                    f"[config] FAB_MIN_STEPS={_fms} is set AND CHAIN_VOTE=1. Under CHAIN_VOTE the halting hop "
                    f"selects that hop's answer, so blocking HALT for the first {min_steps} hop(s) has no "
                    f"meaning and the value would be forced to 0. Set CHAIN_VOTE=0 to use FAB_MIN_STEPS, or "
                    f"drop FAB_MIN_STEPS; they cannot both be right.")
            s.min_steps = 0
        s._mass_ema = None                     # training-time HALT mass on the chaining path
        s._div = None                          # distinctness penalty from the last chaining walk
        s._rmix = []; s._sample_mix = False    # (grounded spread, weight-prediction spread) samples
        s._ord = []                            # (hop0, hop1) expert pairs, for H(hop1 | hop0)
        s.explore = float(_env("FAB_EXPLORE", 0.15))   # fraction of steps that force an off-policy expert
        s.xover = float(_env("FAB_XOVER", 0.35))       # fraction of births assembled from SEVERAL parents
        s.born = {}                                        # expert -> step it was created (grace before culling)
        s.removed = 0; s.spared = 0
        s.breadth = float(_env("EXP_DOM_FRAC", 0.10))
        s.breadth_min = int(_env("EXP_DOM_MIN", 4))   # never squeeze below this, or a small population
        #   cannot route at all (10% of 8 domains is 0 and every expert would be banned from everything).
        s.comp = {}                                        # COMPETENCE per node: EMA bits/window on what it wins.
        s.contrib = {}                                     # MARGINAL CONTRIBUTION: EMA of (loss WITHOUT this node
        #   minus loss WITH it). Positive = the system is worse without it. This is the SELECTION signal; `comp`
        #   is the cheap per-step correlate, kept as a cross-check because it can be fooled by easy material.
        #   Neither is a Parameter or in state_dict -- selection statistics, re-earned after a resume.
        s.q_entry = nn.Linear(sig_d, dk); s.nov = nn.Linear(1, dk); s.ctrl = nn.Linear(3, dk)
        s.norm = nn.LayerNorm(d); s.grown = 0
        s.norm_only = norm_only                             # ABLATION: normalization only, no nodes, no routing
        s.route_t = float(_env("ROUTE_T", 0.1))   # <1 sharpens routing -> mass concentrates -> specialization.
        #   DEFAULT LOWERED 1.0 -> 0.1: signature and centroid are unit vectors in SIG_D=64, so cosine logits have
        #   std ~1/sqrt(64) = 0.125. At T=1.0 the top-vs-mean weight ratio is ~1.37x REGARDLESS of N -- at N=64 that
        #   is w ~= 0.016 +/- 12%, i.e. very nearly uniform, so top-k picks noise and no expert can specialize.
        #   T=0.1 amplifies the same differences 10x, which is what makes a large population selectable at all.
        # GROUNDED ROUTING: an expert owns a REGION of signature space, exactly as a domain does (and domains DO
        # differentiate: purity 0.92). Free learned keys start symmetric, and with every expert trained to solve the
        # whole task there is no gradient that breaks the symmetry -> uniform generalists. A centroid EMA'd toward the
        # signatures it actually serves acquires a constituency, so its traffic becomes distinct and it specializes.
        s.grounded = bool(int(_env("ROUTE_GROUNDED", 1)))
        s.route_learn = bool(int(_env("ROUTE_LEARN", 1)))   # add the learned bilinear term (see route_w)
        s.birth_jitter = float(_env("BIRTH_JITTER", 0.15))
        s.cent_m = float(_env("CENT_EMA", 0.02))
    def _ids(s, N, step=None):
        """(K, SRC) for the N live experts, embedded from their full weights. Cached on a cadence: the embed is
        O(N * 2*d*r * hid) and at N=4096, d=768, r=8 that is a real cost to pay every step for something that
        moves slowly. Between refreshes the cached values are used as-is, so gradient reaches the embedder on
        refresh steps -- which is what trains it."""
        if not s.derive_ids: return s.K_p[:N], s.SRC_p[:N]
        # TWO KINDS OF REUSE, and conflating them was the bug.
        #   SAME STEP  -- return the LIVE tensors. _ids can be called more than once in a step (route_w, forward,
        #                 spawn_from), and every one of those consumers must sit on the same graph or the second
        #                 one silently trains nothing.
        #   LATER STEP -- return DETACHED copies. This used to hand back the live tensors, whose graph the previous
        #                 backward had already freed: "Trying to backward through the graph a second time". It only
        #                 never fired because the society path calls _ids WITHOUT step=, so the cadence test always
        #                 failed. That made emb_every dead code on one path and live on the other -- and since the
        #                 identity channel is the ONLY one that reaches every expert (routing computes k of N, but
        #                 eemb reads ALL N weights), a stale cache cuts the one gradient the rest of the population
        #                 ever sees by a factor of emb_every. DEFAULT 1: pay the embed, keep the channel.
        if s._kc is not None and s._kn == N and step is not None:
            if step == s._kstep and s._kcl is not None: return s._kcl
            if step - s._kstep < s.emb_every:
                s._kcl = None                             # release the old graph; it can never be returned again
                return s._kc
        W = torch.cat([s.A[:N].reshape(N, -1), s.B[:N].reshape(N, -1)], -1)   # FULL weights, not a summary
        e = s.eemb(W)
        out = (e[:, :s.dk], e[:, s.dk:])
        s._kcl = out                                                          # live, this step only
        s._kc, s._kn = (out[0].detach(), out[1].detach()), N
        if step is not None: s._kstep = step
        return out

    def ae_loss(s, N):
        """Autoencoder tie. edec is only meaningful as an inverse of eemb, and nothing else would train it: the
        decoder is used at BIRTH, which is rare, so its gradient signal is far too sparse to shape it. This makes
        the round trip weights -> identity -> weights the thing that keeps the two consistent."""
        if not s.derive_ids or N < 1: return None
        W = torch.cat([s.A[:N].reshape(N, -1), s.B[:N].reshape(N, -1)], -1)
        e = s.eemb(W)
        # ANTI-COLLAPSE ON THE IDENTITIES. Measured: the population's typical nearest-neighbour distance in
        # identity space was 0.000 -- every expert embedded to the SAME vector. Routing then has nothing to
        # discriminate on (argmax lands arbitrarily on one node), specialization reads exactly 0.000, and the
        # spawn can never fire because a query is always 0.000 from "the nearest". One collapsed embedder
        # explains every routing symptom at once.
        # This is the failure _var_cov already exists for -- it guards the SigEncoder and the dynamics population
        # -- and I gave the expert embedder no protection at all. The inputs make it near-inevitable: experts are
        # replicated clones, so their weights are similar by construction, and a net with no variance pressure
        # maps similar inputs to one point.
        _v, _c = _var_cov(e)
        return F.mse_loss(s.edec(e[:, :s.dk]), W) + s.emb_var * (_v + _c)

    def spawn_from(s, q, step=None):
        """CREATE THE EXPERT THE ROUTER ASKED FOR. q is the router's query -- a point in identity space. If no
        live expert is near it, decode it into weights and instantiate. Returns the new slot or None."""
        if s.n_live >= s.cap: return None
        with torch.no_grad():
            Kd, _ = s._ids(s.n_live, step)
            near = float((F.normalize(Kd, dim=-1) @ F.normalize(q, dim=-1).squeeze()).max()) if s.n_live else -1.0
        # RELATIVE, not absolute. `1 - near > 0.45` compares the query to the NEAREST of N identities, and that
        # distance shrinks as N grows -- so an absolute threshold makes spawning impossible exactly when the
        # population is large. Worse, the experts are near-duplicates of a few lineages, so their identities pack
        # into a tight cluster that any query is close to. Measured: 4096 experts, threshold 0.45, ZERO spawns in
        # a full pilot -- the mechanism could not fire, which is not the same as deciding not to.
        # Compare instead against how tightly the population ALREADY packs: spawn when the query is further from
        # everything than the experts typically are from each other. Scale-free, and it tightens on its own as the
        # population densifies rather than switching off.
        with torch.no_grad():
            _Kn = F.normalize(Kd, dim=-1)
            _sub = _Kn if s.n_live <= 512 else _Kn[torch.randperm(s.n_live, device=_Kn.device)[:512]]
            _P = 1 - _sub @ _sub.t()
            _P.fill_diagonal_(9e9)
            _typ = float(_P.min(1).values.median())        # the population's own nearest-neighbour distance
        s._spawn_gap = 1.0 - near; s._spawn_typ = _typ     # kept for the report: WHY it did or did not fire
        if (1.0 - near) < max(s.spawn_mult * _typ, s.spawn_floor):
            return None                                    # no further from everything than they are from each other
        j = s.n_live
        with torch.no_grad():
            W = s.edec(q.detach().reshape(1, -1))[0]
            s.A[j] = W[:s.d * s.r].reshape(s.d, s.r); s.B[j] = W[s.d * s.r:].reshape(s.r, s.d)
        s.born[j] = int(step) if step is not None else 0
        for _D in (s.use, s.comp, s.contrib, s.ef, s.es): _D.pop(j, None)
        s.n_live += 1; s.grown += 1; s.spawned += 1; s._kc = None
        return j

    @property
    def K(s):
        """COMPATIBILITY: several sites index s.K[j] to write a newborn's key. With identities derived from
        weights there is nothing to write -- the key follows the weights -- so those writes go to the fallback
        parameter and are simply unused while FAB_DERIVE_IDS=1."""
        return s.K_p

    @property
    def SRC(s): return s.SRC_p

    @property
    def bodies(s):
        """COMPATIBILITY: the population is tensors now, but `len(fab.bodies)` is read in eight places (the probe
        line, the resume replay, the phase snapshot, the growth cap, the checkpoint, the report). range(n) makes
        every one of them keep working without a rewrite, and len() is all any of them ever wanted."""
        return range(s.n_live)

    def n(s): return s.n_live

    def grow(s, gist=None, step=None):                      # add an expert; returns its new params
        dev = s.halt_key.device
        _ng = (F.normalize(gist.detach().mean(0, keepdim=True).cpu()
                           + s.birth_jitter * torch.randn(1, s.sig_d), dim=-1) if gist is not None
               else F.normalize(torch.randn(1, s.sig_d), dim=-1))
        #   JITTER: a burst grows several experts at ONE signature, so without it they are born as exact clones with
        #   identical regions and can never differentiate. Small enough to keep the newborn in the region that
        #   triggered its birth, large enough that the routing EMA can pull them apart.
        if s.n_live >= s.cap: return []                     # at capacity: growth is a no-op, not an error
        j = s.n_live
        # REPLICATE THE FITTEST, do not mint a blank. Identity birth (B=0) was chosen so that adding a node could
        # never disrupt what already works -- but it also means the newborn computes NOTHING, has no competence,
        # and so attracts no routing mass; and it cannot acquire competence because it gets no traffic. That is a
        # trap with no exit, and the pilot shows where it leads: 4096 experts, ONE of them carrying 75% of the
        # mass, 4095 blank identities that never competed for anything.
        # Selection needs variation of something that WORKS. The newborn inherits the fittest expert's adapter plus
        # a perturbation, so it starts competent and differentiates from there -- the same clone-and-perturb the
        # world model already uses ("cloned from the fittest") and that ExpertBank had in the dead legacy path.
        # Fitness = marginal contribution where measured (the system is worse without it), utilization otherwise.
        # PARENT = RELEVANT first, fit second, and sampled rather than argmaxed.
        # Cloning the globally fittest is the wrong rule: growth is triggered BY A REGION (the signature `gist`),
        # and the expert that matters for that region is whichever already serves it -- which may be a niche
        # expert with low global utilization and high local value. A global argmax hands every birth to the same
        # incumbent, which is how a population converges on one lineage. So: shortlist by RELEVANCE (nearest
        # centroids to the birth signature), then SAMPLE within that shortlist with probability proportional to
        # fitness. Sampling matters as much as the shortlist -- an argmax over the shortlist would still let one
        # local incumbent monopolise every birth in its region.
        _par = None
        if FAB_REPLICATE and s.n_live > 0:
            _fit = {i: (s.contrib[i] if i in s.contrib else 0.0) for i in range(s.n_live)}
            if gist is not None:
                _q = F.normalize(gist.detach().mean(0), dim=-1).to(s.cent.device)
                _sim = (F.normalize(s.cent[:s.n_live], dim=-1) @ _q)
                _k = min(max(1, s.parent_k), s.n_live)
                _cand = _sim.topk(_k).indices.tolist()      # the experts that OWN this region
            else:
                _cand = list(range(s.n_live))
            #   fitness -> non-negative weights. contrib can be negative (the system is BETTER without that expert),
            #   and a negative-contribution parent should be able to reproduce only rarely, not never: shifting to
            #   a floor keeps the tail alive, which is the whole point of not using an argmax.
            # PARENT QUOTA. The incumbent wins the routing, so it is in every relevance shortlist AND it is the
            # fittest -- so every birth is its child, and the population becomes one lineage wearing 4096 hats.
            # Diversity of the POPULATION is not the same as diversity of its ANCESTRY. Cap how many of the recent
            # births any one expert may parent; once at quota it is skipped and the next candidate breeds.
            _recent = sum(s.births.values()) or 1
            _cand = [c for c in _cand if s.births.get(c, 0) / _recent < s.parent_max] or _cand
            _w8 = [max(1e-3, _fit.get(i, 0.0) - min(_fit.get(c, 0.0) for c in _cand) + 1e-3) for i in _cand]
            _tot = sum(_w8)
            _r = random.random() * _tot
            for _i4, _c4 in enumerate(_cand):
                _r -= _w8[_i4]
                if _r <= 0: _par = _c4; break
            if _par is None: _par = _cand[-1]
            if not (0 <= _par < s.n_live): _par = None
        with torch.no_grad():
            s.cent[j] = _ng.to(s.cent.device)[0]            # the newborn OWNS the region that triggered its birth
            if _par is None:
                s.A[j].normal_(0, s.d ** -0.5); s.B[j].zero_()   # no parent yet -> identity, as before
            else:
                # MUTATION, scaled to the parent rather than absolute. A fixed 0.02 is a rounding error against a
                # weight whose own scale is unknown, so a clone was effectively an exact copy and the population
                # explored nothing. Scale by the parent's own std, and give it a heavy tail: most offspring stay
                # near the parent, a few (FAB_MUT_BIG) jump far enough to reach somewhere the lineage has not been.
                # Without the tail a population converges on its founder however many members it has.
                _sa = float(s.A[_par].std()) or 1.0; _sb = float(s.B[_par].std()) or (s.d ** -0.5)
                _m = s.mut * (s.mut_big if random.random() < s.mut_big_p else 1.0)
                s.A[j] = s.A[_par].clone(); s.B[j] = s.B[_par].clone()
                # CROSSOVER: take whole RANK SLICES from other parents. A low-rank expert is a sum of r rank-1
                # maps A[:,i] (x) B[i,:], so slice i is a self-contained piece of function -- the natural
                # "connected section" to inherit. Recombination lets a newborn hold a piece of one lineage and a
                # piece of another, which mutation alone cannot produce: mutation explores AROUND a parent,
                # crossover reaches BETWEEN them. Parents are drawn from the same relevance shortlist, so the
                # pieces come from experts that serve the same region.
                if s.xover > 0 and s.r > 1 and len(_cand) > 1 and random.random() < s.xover:
                    _nsl = random.randint(1, max(1, s.r // 2))
                    for _sl2 in random.sample(range(s.r), _nsl):
                        _o = random.choice([c for c in _cand if c != _par])
                        s.A[j][:, _sl2] = s.A[_o][:, _sl2]
                        s.B[j][_sl2, :] = s.B[_o][_sl2, :]
                    s.crossed += 1
                s.A[j] += _m * _sa * torch.randn_like(s.A[j])   # mutation on TOP of whatever was inherited
                s.B[j] += _m * _sb * torch.randn_like(s.B[j])
                s.parent[j] = int(_par); s.replicated += 1
                s.mutscale[j] = _m
                s.births[_par] = s.births.get(_par, 0) + 1
                if sum(s.births.values()) > s.births_win:   # sliding window: decay so an old monopoly expires
                    for _bk in list(s.births): s.births[_bk] *= 0.5
                    s.births = {k: v for k, v in s.births.items() if v >= 1}
            s.K[j] = (s.seed_key(gist) if gist is not None else torch.randn(s.dk, device=dev) * 0.1)
            s.SRC[j] = (s.SRC[_par] + 0.1 * torch.randn(s.dk, device=dev)) if _par is not None \
                else torch.randn(s.dk, device=dev) * 0.1   # a child inherits WHERE ITS PARENT SENDS, perturbed

        s.born[j] = int(step) if step is not None else 0    # GRACE is measured from here
        s.use.pop(j, None); s.comp.pop(j, None); s.contrib.pop(j, None)     # a reused slot starts clean
        s.n_live += 1; s.grown += 1
        return []                                           # rows of EXISTING Parameters -- already in the optimizer,
        #   which is the whole reason for preallocating. Nothing to add_param_group.
    def dom_ban(s, did, n_domains):
        """Experts already serving their share of the domain population, EXCLUDING this domain if they already have
        it. Returns a bool mask over the live population, or None when nothing is capped.
        Breadth is checked at ROUTING time rather than fixed up afterwards: an expert that cannot win this domain
        never accumulates mass on it, so the cap shapes the population instead of just reporting on it."""
        if s.breadth <= 0 or not s.dom_of: return None
        lim = max(s.breadth_min, int(s.breadth * max(1, n_domains)))
        over = [e for e, ds in s.dom_of.items() if len(ds) >= lim and did not in ds and e < s.n_live]
        if not over: return None
        m = torch.zeros(s.n_live, dtype=torch.bool)
        m[torch.tensor(over, dtype=torch.long)] = True
        return m

    def note_dom(s, e, did):
        """Record that expert e served domain did. AFFILIATION ONLY -- it used to also bump `use`, which conflated
        two different measurements and made them impossible to sample at different rates."""
        s.dom_of.setdefault(int(e), set()).add(int(did))

    def note_use(s, ids):
        """UTILIZATION: the resource the population competes for. Culling ranks on it, exploration picks its cold
        set from it, and discovery hands novel material to its minimum."""
        for _e in ids: s.use[int(_e)] = s.use.get(int(_e), 0.0) + 1.0

    def note_err(s, e, v):
        """Per-expert FAST and SLOW error EMAs. The pair is the whole point: their DIFFERENCE separates an expert
        that cannot model its material from one whose material just changed.
          fast ~= slow, both high  -> persistent incompetence. Cull.
          fast >> slow             -> a SHIFT is in progress and the expert is adapting. Protect: this is exactly
                                      the case where old news changes, and culling here would destroy the
                                      learning we are trying to measure.
        Utilization cannot see either of these -- it only knows how OFTEN an expert was called, never whether it
        was any good when it was."""
        e = int(e)
        s.ef[e] = v if e not in s.ef else (1 - s.ef_a) * s.ef[e] + s.ef_a * v
        s.es[e] = v if e not in s.es else (1 - s.es_a) * s.es[e] + s.es_a * v

    def failing(s, e, pop):
        """True only for SUSTAINED elevation against the population. Returns False during a spike by construction:
        a spike makes fast exceed slow, and that is the adaptation case."""
        if e not in s.ef or e not in s.es or pop is None: return False
        if s.ef[e] > s.es[e] * (1 + s.shift_tol): return False      # rising fast -> shift, not failure
        return min(s.ef[e], s.es[e]) > pop * (1 + s.fail_tol)       # both ends above the population

    def manage(s, step, grace=3000, cull_frac=0.08, pressure=0.75, protect=True, comp_glob=None):
        """SELECTION for the fabric population. There was NONE.

        router.manage() -- create/replicate/cull -- is gated on `EXPERTS`, which is mutually exclusive with FABRIC
        and therefore 0 in every default run. fab.remove() is called only by the independence TEST, which restores
        immediately after. So the fabric was GROW-ONLY: it ramped to its cap and nothing ever removed a node. A
        population that only grows is not under selection, whatever the growth rule is, and the competence
        protection wired into router.manage sat on a code path that never executed (hence `spared 0`, every run).

        Mirrors the domain manager deliberately: cull only under CAPACITY PRESSURE, only the bottom rank fraction
        by utilization, never a newborn, and never a node that EARNS its place -- a positive marginal contribution
        (the system is measurably worse without it) or, failing that, a competence better than the population's.
        That is the protection for the useful-but-rare: rarely called is the bottom of a utilization ranking, and
        it is also what a niche expert looks like."""
        # TWO ROUTES OUT, not one. Utilization-based culling only fires under capacity pressure -- correct for
        # "the bank is full, drop the least used" but blind to an expert that is CALLED OFTEN AND BAD. The
        # sustained-error route runs at ANY occupancy, because a failing expert is worth removing whether or not
        # the population is full.
        culled = spared = 0
        if protect is not None and comp_glob is not None:
            for i in list(range(s.n_live)):
                if s.n_live <= 2: break
                if step - s.born.get(i, step) < grace: continue
                if not s.failing(i, comp_glob): continue
                if protect and s.contrib.get(i, 0.0) > 0:            # load-bearing despite the error -> keep
                    spared += 1; continue
                s.remove(i); culled += 1; s.failed_out += 1
        if s.n_live <= 2 or (s.n_live / max(1, s.cap)) < pressure: return culled, spared
        order = sorted(range(s.n_live), key=lambda i: s.use.get(i, 0.0))
        for i in list(order[:max(1, int(cull_frac * s.n_live))]):
            if s.n_live <= 2: break
            if step - s.born.get(i, step) < grace: continue
            if protect:
                _c = s.contrib.get(i)
                if _c is not None and _c > 0: spared += 1; continue        # load-bearing: worse without it
                if _c is None and comp_glob is not None and s.comp.get(i, 1e9) < comp_glob:
                    spared += 1; continue                                   # better than the population on its own
            s.remove(i); culled += 1
        return culled, spared

    def route_w(s, gist, nov, ban=None, step=None, learn_regions=True):
        """Routing weights over the N experts. Two terms, both kept:
          GROUNDED  cosine of the signature to each expert's owned REGION (centroid, EMA'd under no_grad).
          LEARNED   qproj[i](gist).keys[i] -- a per-expert bilinear score. This revives parameters that were
                    measurably DEAD: with ROUTE_GROUNDED=1 the router ran entirely off the centroid buffer and a
                    detached signature, so keys/qproj/q_entry/nov/ctrl/halt_key received NO gradient at all and
                    routing could not learn. `gist` is still detached (sig_of is no_grad), so the gradient reaches
                    the router's own parameters but never back into the SigEncoder -- which is the intent."""
        N = s.n_live
        if s.grounded:
            logits = s.entry_logits(gist, nov, N, step=step, ban=ban)
            w = s._with_halt(logits, gist, N)
            # AN EVAL PASS MUST NOT MOVE THE REGIONS. See fab_logits: every eval path (learning curve, holdout
            # probe, bpb_true, generation) called this with a FABRICATED ZERO gist, and F.normalize(0) is 0, so
            # each one dragged the top-FAB_CENT_TOPK experts' centroids toward the ORIGIN.
            # HOW MUCH THAT COSTS IS NOT ESTABLISHED, and an earlier version of this comment claimed it was.
            # Two runs with byte-identical model code and the same seed, differing only in whether SAVE_CKPT was
            # set (which gates the extra holdout_bpb passes), read 3.694 and 2.100. That difference is real. But
            # the extra passes are ~125 centroid nudges against ~240,650 from training -- 0.05% -- which cannot
            # ACCUMULATE to 1.6 bits/byte. What it shows is that this system is chaotically sensitive: a 0.05%
            # perturbation lands the run somewhere else entirely. The fix is right on its own terms -- an eval
            # pass must not mutate training state -- not because it recovers a measured 1.594.
            if learn_regions: s.ground_update(gist, w, N)
        else:
            _Kd, _ = s._ids(N, step)
            K = torch.cat([_Kd, s.halt_key[None]], 0)
            _lg = ((s.q_entry(gist) + s.nov(nov[:, None])) @ K.t()) / max(1e-3, s.route_t)
            if ban is not None:
                _lg[:, :N] = _lg[:, :N].masked_fill(ban.to(_lg.device)[None], float("-inf"))
            c = torch.softmax(_lg, -1)
            s._record_halt(c[:, N:N + 1])
            w = c[:, :N]; w = w / w.sum(-1, keepdim=True).clamp_min(1e-9)      # router weights over experts
        return w

    def entry_logits(s, gist, nov, N, step=None, ban=None, qextra=None):
        """WHERE DOES THIS MATERIAL BELONG? Scores the N live experts for a signature. ONE implementation, called
        by BOTH forward paths.

        It used to be duplicated, and the two copies had drifted into different routers. route_w (society) scored a
        GROUNDED cosine to each expert's owned REGION plus a learned key term. Fabric.forward (chaining) had only
        `q_entry(gist) @ K.t()` -- free learned keys, no region, and no centroid update anywhere in the path. That
        is exactly the design this class's own comment calls out as unable to specialize: near-identical experts
        give near-identical keys, route_t=0.1 amplifies the noise between them, whoever wins first collects the
        gradient and becomes more distinct, and nothing ever gives anyone else a constituency. Rich-get-richer
        with no path in.
        Measured, on a task where 8 domains each need their OWN map and the signatures are separable by
        construction, so any failure is the router's: I(domain; chosen expert)/H(domain) was 0.34-0.87 on the
        society path and EXACTLY 0.000 on chaining -- 1 expert of 32 taking 100% of the traffic, both seeds. The
        router could not learn where anything belonged. ROUTE_GROUNDED reported ON in the banner throughout,
        because it WAS on: for the path that was not running."""
        # ROUTE_REGION_W scales the SIGNATURE-REGION term. At 0 the router runs on PREDICTED WEIGHTS ALONE:
        # q_route emits a point in identity space, every expert's full weights are embedded into that same space
        # by eemb, and the nearest wins -- with edec decoding the query into a real expert when nothing is near.
        # That is this branch's whole design, and until it was measured it was contributing 2% of the decision.
        # NOT the same as ROUTE_GROUNDED=0, which drops to the OLD q_entry key router and skips this path entirely.
        C = F.normalize(s.cent[:N].to(gist.device), dim=-1)
        _gterm = (F.normalize(gist, dim=-1) @ C.t()) / max(1e-3, s.route_t)
        logits = s.region_w * _gterm
        if s.route_learn:
            # BOTH TERMS ARE COSINES, ON THE SAME SCALE when FAB_KEY_NORM=1. The raw form is a dot product of two
            # unconstrained trained vectors added to a bounded cosine: an expert whose key norm grows large scores
            # high for EVERY input with any positive projection, regardless of its region. It remains the default
            # only because the normalized form has not been A/B'd at a size where the answer means anything.
            _Kd, _ = s._ids(N, step)                       # identity embedded from the experts' own weights
            _qq = s.q_route(gist) if qextra is None else s.q_route(gist) + qextra
            _lrn = ((F.normalize(_qq, dim=-1) @ F.normalize(_Kd, dim=-1).t())
                    / max(1e-3, s.route_t)) if FAB_KEY_NORM else (_qq @ _Kd.t())
            logits = logits + _lrn + s.nov(nov[:, None]).sum(-1, keepdim=True)
            # WHICH ROUTER IS ACTUALLY DECIDING? This branch's premise is that the router PREDICTS THE WEIGHTS of
            # the expert it wants (q_route -> identity space, matched against eemb of every expert's full weights,
            # and decoded into a real expert by edec when nothing is near). The grounded term is the OLDER
            # signature-region router, and summing them means one can silently dominate the other. Only the SPREAD
            # across experts matters -- a constant shift cancels in the softmax -- so compare standard deviations.
            # Sampled on a cadence the caller sets, because these are two host syncs.
            if getattr(s, "_sample_mix", False):
                with torch.no_grad():
                    s._rmix.append((float((s.region_w * _gterm).std()), float(_lrn.std())))
                s._sample_mix = False
        if ban is not None: logits = logits.masked_fill(ban.to(logits.device)[None], float("-inf"))
        return logits

    def ground_update(s, gist, w, N):
        """The other half of grounded routing, and just as absent from the chaining path: an expert's REGION moves
        toward the signatures it actually served. Without this the centroids sit at their initialisation forever
        and the cosine term in entry_logits is scoring against noise."""
        with torch.no_grad():
            # EVERY EXPERT THAT SERVED THIS SIGNATURE MOVES TOWARD IT, in proportion to how much it served.
            # Updating the ARGMAX WINNER ONLY makes discovery structurally impossible: the winner drifts toward
            # every region it wins and so becomes closer still, while every other centroid stays frozen at its
            # initialisation. A newcomer cannot win because its region never moved, and its region never moves
            # because it never wins.
            _wm = w.mean(0)
            _topm = min(_i("FAB_CENT_TOPK", 8), N)
            _iv, _ii = _wm.topk(_topm)
            _g1 = F.normalize(gist, dim=-1).mean(0)
            _share = _iv / _iv.sum().clamp_min(1e-9)
            for _q5 in range(_topm):
                _jj = int(_ii[_q5]); _rate = s.cent_m * float(_share[_q5])
                s.cent[_jj] = F.normalize((1 - _rate) * s.cent[_jj].to(gist.device) + _rate * _g1, dim=-1).cpu()
            # NOVELTY -> DISCOVERY. If this signature is far from EVERY centroid, it is material nothing owns.
            # Hand it to the LEAST-USED expert instead of to the nearest incumbent: that is the mechanism by which
            # new material recruits new capacity rather than being absorbed by whoever is already largest.
            if FAB_DISCOVER > 0 and N > 1:
                _best = float((F.normalize(s.cent[:N], dim=-1).to(gist.device) @ _g1).max())
                if 1.0 - _best > FAB_DISCOVER:
                    _cold = min(range(N), key=lambda i: s.use.get(i, 0.0))
                    s.cent[_cold] = F.normalize(0.5 * s.cent[_cold].to(gist.device) + 0.5 * _g1, dim=-1).cpu()
                    s.discovered += 1


    def _with_halt(s, logits, gist, N):
        """Append HALT to the grounded branch's operator set and return the renormalised weights over experts.

        The grounded branch scores experts by cosine of the signature to their region; HALT owns no region, so its
        logit comes from the SAME place the learned expert term does -- the router's query in identity space,
        matched against halt_key -- plus a learned scalar prior. That keeps it on one scale with the terms it is
        competing against, which is the bug that made the raw-dot learned key a winner-take-all amplifier."""
        if not s.halt_on:
            s._halt = None
            return torch.softmax(logits, -1)
        _qh = s.q_route(gist)
        _hl = ((_qh @ s.halt_key[:, None]) if (s.route_learn and not FAB_KEY_NORM)
               else (F.normalize(_qh, dim=-1) @ F.normalize(s.halt_key, dim=-1)[:, None]) / max(1e-3, s.route_t))
        c = torch.softmax(torch.cat([logits, _hl + s.halt_b], -1), -1)
        s._record_halt(c[:, N:N + 1])
        w = c[:, :N]
        return w / w.sum(-1, keepdim=True).clamp_min(1e-9)

    def _record_halt(s, hm):
        """Store the halt mass for the caller and keep a running mean for the report. Clamped at halt_max so the
        population always keeps a share of the blend -- see halt_max in __init__ for why that is a barrier and not
        a preference. Kept ON DEVICE: a float() here would be a GPU sync every step for a reporting number."""
        if not s.halt_on:
            s._halt = None; return
        s._halt = hm.clamp(max=s.halt_max)
        with torch.no_grad():
            _m = s._halt.mean().detach()
            s.halt_ema = _m if s.halt_ema is None else 0.99 * s.halt_ema + 0.01 * _m

    def society(s, h, gist, nov, k=None, ban=None, step=None, learn_regions=True):
        """SOCIETY OF EXPERTS: every expert maps the SAME base representation to its OWN output -- no chaining, so
        expert i's output never depends on expert j's.

        SPARSE: only the top-k experts by routing mass are COMPUTED. This is not an approximation of what ran before
        -- the caller already used only the top ENS_K outputs to form the logits and threw the dense blend away, so
        every expert beyond the k-th was computed, unused, and un-gradiented. Computing k of N makes the cost match
        the selection that was already happening, which is what makes a LARGE expert population affordable.
        Returns (w_full, O_k, idx) where idx maps O_k's columns back to global expert ids."""
        N = s.n_live
        w = s.route_w(gist, nov, ban=ban, step=step, learn_regions=learn_regions)
        kk = N if k is None else int(min(max(1, k), N))
        # PER WINDOW, not per batch. This was w.mean(0).topk -- ONE expert set and one weight vector for all
        # BATCH_W windows, so every window in a batch was served by the same experts however different its
        # material. Specialization was impossible by construction: an expert cannot come to own a kind of text if
        # it is never selected FOR that text, only for the batch average that happens to contain it. That is why
        # discovery, crossover and exploration all fired thousands of times and moved nothing -- they change WHICH
        # expert is chosen, not the fact that 16 windows shared one choice.
        # Costs nothing: einsum('bld,kdr->bklr') already computed every b x k pair, so per-window indexing is the
        # same arithmetic with a batch dimension on the gather.
        idx = (w.topk(kk, dim=-1).indices if kk < N
               else torch.arange(N, device=w.device)[None].expand(w.size(0), N))
        # EXPLORATION. top-k is on-policy: only experts the router already prefers are ever COMPUTED, so only they
        # receive gradient. An expert outside the top-k is not merely unused -- it is frozen, and can never improve
        # into contention. Swap one slot for an expert sampled toward LOW USE, so untried capacity gets both
        # traffic and gradient. This is the difference between a population and a leaderboard.
        if s.explore > 0 and kk >= 2 and N > kk:
            _cold2 = sorted(range(N), key=lambda i: s.use.get(i, 0.0))[:max(8, N // 16)]
            _rows = [r for r in range(idx.size(0)) if random.random() < s.explore]
            if _rows:
                idx = idx.clone()
                for _r5 in _rows:                          # per ROW: exploration is a property of a window, not a batch
                    idx[_r5, -1] = random.choice(_cold2)
                s.explored = getattr(s, "explored", 0) + len(_rows)
        # BATCHED low-rank apply for the selected k: h + (h @ A_i) @ B_i, all k at once. This was k separate
        # module calls; it is now two einsums whose cost is k, not N -- which is what makes N large affordable.
        _A = s.A[idx]; _B = s.B[idx]                                           # (B,kk,d,r) (B,kk,r,d)
        O = h.unsqueeze(1) + torch.einsum('bklr,bkrd->bkld', torch.einsum('bld,bkdr->bklr', h, _A), _B)
        return w, O, idx
    def maybe_deepen(s, lf, step):
        """ONE MORE HOP, once this depth has stopped paying. The user-facing rule: train the chain at its current
        length until the loss stops improving, then extend it by one. Returns the new depth if it grew.

        Deliberately keyed on the SLOW loss and a patience counter rather than on a single step: the population is
        also growing, and a burst of new experts causes a transient worsening that must not read as a plateau."""
        if not s.curric or s.depth_now >= s.max_steps: return None
        s.dp_seen += 1
        # A PLATEAU TEST ALONE CANNOT FIRE ON AN UNDERFIT MODEL, and this model is underfit by its own report
        # (train-vs-held-out gap -0.035, "UNDERFIT -> more data/passes"). The first version of this waited for the
        # loss to stop improving and so sat at depth 1 for the whole run -- which I then reported as "staged depth
        # did not help". It had not run. A stage also ends after CHAIN_STAGE_MAX checks, so depth advances on a
        # still-falling loss rather than never.
        _plateau = not (s.dp_best is None or lf < s.dp_best - s.dp_eps)
        if s.dp_best is None or lf < s.dp_best: s.dp_best = lf
        if not _plateau: s.dp_wait = 0
        else: s.dp_wait += 1
        if s.dp_wait < s.dp_patience and s.dp_seen < s.dp_stage_max: return None
        s.dp_seen = 0
        s.depth_now += 1; s.dp_wait = 0; s.dp_best = lf
        s.deepened.append((step, s.depth_now))
        return s.depth_now

    def remove(s, j):
        """DELETE an expert outright: its parameters are gone. In a society this should cost roughly that expert's
        own contribution; in an entangled mixture it damages everyone (the weights-unlearn failure mode)."""
        # SWAP-WITH-LAST rather than rebuild: O(1) and the tensors stay dense. The centroid moves WITH its expert,
        # which the list version had to be fixed to do -- reading cent[:N] against a shifted body list routed every
        # expert above j by its neighbour's region.
        last = s.n_live - 1
        if j != last:
            with torch.no_grad():
                for _T in (s.A, s.B, s.K, s.SRC, s.cent): _T[j] = _T[last]
            for _D in (s.use, s.born, s.ef, s.es, s.births):
                _D.pop(j, None)
                if last in _D: _D[j] = _D.pop(last)
            for _D in (s.comp, s.contrib):
                _D.pop(j, None)
                if last in _D: _D[j] = _D.pop(last)
        else:
            for _D in (s.comp, s.contrib): _D.pop(j, None)
        s.dom_of.pop(j, None)
        if last in s.dom_of: s.dom_of[j] = s.dom_of.pop(last)   # the swapped-in expert keeps ITS affiliations
        s.n_live = last
    def seed_key(s, gist):
        """TARGETED BIRTH: put the new expert's key where the router will actually send this region, instead of at
        random. A randomly-keyed expert receives no traffic, gets no gradient, and stays dead (measured: 12/17 idle)."""
        with torch.no_grad(): return s.q_entry(gist).detach().squeeze(0).clone()
    def forward(s, h, gist, nov, step=None, ban1=None, ban=None, head=None, learn_regions=True):
        """ban1: a single expert id to hold OUT of this walk entirely -- the counterfactual the marginal-contribution
        rule needs. On the society path leave-one-out is free (per-expert logits are already separate); here the
        walk itself changes when an expert is removed, so the only honest answer is to run it again without them."""
        N = s.n_live; HALT = N
        if s.norm_only:                                                       # control arm: just the normalization
            steps = max(1, min(s.max_steps, 2 + N // 2))
            for _ in range(steps): h = s.norm(h)
            z = h.new_zeros(())
            return h, z, torch.zeros(N + 1, device=h.device), z
        _Kd, _SRCd = s._ids(N, step)                                          # both embedded from full weights
        K = torch.cat([_Kd, s.halt_key[None]], 0)                             # (N+1, dk) operator keys
        nb = s.nov(nov[:, None])                                              # surprise -> routing bias
        # ENTRY USES THE SHARED ROUTER. This was `q_entry(gist) @ K.t()` -- free learned keys with no region term
        # and no centroid update, i.e. a different and strictly weaker router than the society path's, on the path
        # that is now the default. See entry_logits for the measurement: I(domain; expert) was 0.000 here.
        if s.grounded:
            # BREADTH CAP, which never reached this path. dom_ban bans experts already serving more than their
            # share of domains, and it was computed in the society branch of the training loop and simply not
            # passed to forward() -- so on the DEFAULT path the cap was inert and a handful of experts could and
            # did absorb everything (top expert 79.5% of traffic in the last pilot).
            _nlg = s.entry_logits(gist, nov, N, step=step, ban=ban)
        else:
            _nlg = ((s.q_entry(gist) + nb) @ _Kd.t()) / max(1e-3, s.route_t)
        # THE LEARNED HALT PRIOR APPLIES HERE TOO. halt_b was added for the society path and measured DEAD on this
        # one -- an optimizer parameter with an identically-zero gradient on what is now the default path. HALT is
        # one operator with one key; it should have one prior as well.
        _hlg = (((F.normalize(s.q_route(gist), dim=-1) @ F.normalize(s.halt_key, dim=-1)[:, None])
                 / max(1e-3, s.route_t)) + s.halt_b if s.halt_on
                else (s.q_entry(gist) + nb) @ s.halt_key[:, None])
        _elg = torch.cat([_nlg, _hlg], -1)
        if ban1 is not None: _elg[:, ban1] = float("-inf")                     # held out of the ENTRY distribution
        c = torch.softmax(_elg, -1)                                           # (B,N+1) ENTRY distribution
        # ...and the regions MOVE toward what they served, which the chaining path never did either. Without it
        # the cosine term scores against centroids frozen at initialisation and grounding buys nothing.
        if s.grounded and ban1 is None and learn_regions: s.ground_update(gist, c[:, :N], N)
        #   route_t applied HERE TOO. It was only ever applied on the society path, so the chaining path kept the
        #   flat T=1.0 distribution -- with N+1 near-equal logits, HALT starts with ~1/(N+1) and, being ABSORBING,
        #   accumulates every step. That is a large part of the measured 'halt 0.76, mean routed depth 0.24 of 4'.
        # CURRICULUM DEPTH. depth_now is 1 until the loss plateaus, then grows toward max_steps -- see the block
        # in __init__ for why the order is learned one position at a time rather than all at once.
        steps = max(1, min(s.depth_now, s.max_steps, 2 + N // 2))             # adaptive depth budget
        # === SOCIETY, LOOPED ===================================================================================
        # Run the society; feed its result back in; run it again. Each iteration re-routes FROM SCRATCH with the
        # society's own router, with the current state in the query, so the second choice is not a successor of
        # the first -- there is no transition matrix and no SRC here at all.
        # The stop decision is a per-iteration PROBABILITY rather than an absorbing mass, which makes the mixture
        # convex by construction: alive starts at 1, each iteration takes alive * p_stop and passes on
        # alive * (1 - p_stop). That is also the honest reading of "when am I done": at each round the router
        # looks at where the computation actually is and decides whether to answer or go round again.
        if s.loop_soc:
            _alive_p = torch.ones(h.size(0), device=h.device)
            _lgv = None; _last = None; _dacc2 = None
            _dep2 = h.new_zeros(()); _mass2 = torch.zeros(N + 1, device=h.device)
            _wsum = None
            for _t2_ in range(steps):
                _lgr = s.entry_logits(gist, nov, N, step=step, ban=ban,
                                      qextra=s.hproj(h.mean(1)))               # WHERE THE COMPUTATION IS NOW
                _hlr = (((F.normalize(s.q_route(gist) + s.hproj(h.mean(1)), dim=-1)
                          @ F.normalize(s.halt_key, dim=-1)[:, None]) / max(1e-3, s.route_t)) + s.halt_b
                        if s.halt_on else torch.full((h.size(0), 1), -1e4, device=h.device))
                _cc = torch.softmax(torch.cat([_lgr, _hlr], -1), -1)            # (B,N+1)
                _ph = _cc[:, N].clamp(max=s.halt_max) if s.halt_on else torch.zeros(h.size(0), device=h.device)
                _wn = _cc[:, :N] / _cc[:, :N].sum(-1, keepdim=True).clamp_min(1e-9)
                _mass2 = _mass2 + _cc.mean(0).detach(); _dep2 = _dep2 + (1 - _ph).mean()
                _wsum = _wn.detach() if _wsum is None else _wsum + _wn.detach()
                if s.grounded and ban1 is None and learn_regions: s.ground_update(gist, _wn, N)
                _k2 = min(s.chain_k, N)
                _v2, _i2 = _wn.topk(_k2, dim=-1)
                if s.explore > 0 and _k2 >= 2 and N > _k2 and ban1 is None:
                    _cold = sorted(range(N), key=lambda i: s.use.get(i, 0.0))[:max(8, N // 16)]
                    _rw = [r for r in range(_i2.size(0)) if random.random() < s.explore]
                    if _rw:
                        _i2 = _i2.clone(); _v2 = _v2.clone()
                        for _r in _rw:
                            _i2[_r, -1] = random.choice(_cold); _v2[_r, -1] = _wn[_r, _i2[_r, -1]]
                        s.explored = getattr(s, "explored", 0) + len(_rw)
                if ban1 is None:
                    with torch.no_grad():
                        for _u in _i2[:, 0].tolist(): s.use[_u] = s.use.get(_u, 0.0) + 1.0
                        if _t2_ < 2: 
                            if getattr(s, "_sample_ord", False): s._ord.append((_t2_, _i2[:, 0].tolist()))
                _O2 = h.unsqueeze(1) + torch.einsum('bklr,bkrd->bkld',
                                                    torch.einsum('bld,bkdr->bklr', h, s.A[_i2]), s.B[_i2])
                _cw2 = _v2 / _v2.sum(-1, keepdim=True).clamp_min(1e-9)
                # DISTINCTNESS. This branch RETURNS EARLY, before the transition path's DIV_W term, so setting
                # DIV_W with CHAIN_ROUTE=soc was a silent no-op -- a pilot ran 20 minutes with DIV_W=0.05 and
                # came back byte-identical to the DIV_W=0 run on every metric.
                if s.div_w > 0 and _k2 >= 2 and ban1 is None:
                    _dq = F.cosine_similarity(_O2[:, 0].reshape(_O2.size(0), -1),
                                              _O2[:, 1].reshape(_O2.size(0), -1), dim=-1).clamp_min(0.0).mean()
                    _dacc2 = _dq if _dacc2 is None else _dacc2 + _dq
                if head is not None:
                    _vk2 = min(ENS_K, _k2)
                    _vw2 = _cw2[:, :_vk2] / _cw2[:, :_vk2].sum(-1, keepdim=True).clamp_min(1e-9)
                    _l2 = None
                    for _q2 in range(_vk2):
                        _p2 = head(s.norm(_O2[:, _q2])) * _vw2[:, _q2][:, None, None]
                        _l2 = _p2 if _l2 is None else _l2 + _p2
                    _take = (_alive_p * _ph)[:, None, None]
                    _lgv = _take * _l2 if _lgv is None else _lgv + _take * _l2
                    _last = _l2
                _alive_p = _alive_p * (1 - _ph)
                h = s.norm(h + s.alpha * (_cw2[:, :, None, None] * _O2).sum(1) - s.alpha * h)
            if head is not None and _last is not None:
                _lgv = _lgv + _alive_p[:, None, None] * _last                   # never stopped -> the last round
                s._votelg = _lgv
            if ban1 is None:
                s._div = (_dacc2 / steps) if _dacc2 is not None else None
                s._wrun = _wsum / _wsum.sum(-1, keepdim=True).clamp_min(1e-9)
                with torch.no_grad():
                    _hm3 = (1.0 - _alive_p).mean().detach()
                    s._mass_ema = _hm3 if s._mass_ema is None else 0.99 * s._mass_ema + 0.01 * _hm3
            return h, _dep2 / steps, _mass2 / steps, h.new_zeros(())

        depth = h.new_zeros(()); mass = torch.zeros(N + 1, device=h.device); bal = h.new_zeros(())
        wacc = None                                                           # (B,N) per-window mass over all hops
        dacc = None                                                           # DISTINCTNESS penalty, accumulated
        _vote = s.vote and head is not None and ban1 is None
        s._votelg = None
        lgacc = None; _hbase = h; _hsum = None
        if _vote:                                                             # mass that halted BEFORE any hop ran
            lgacc = c[:, HALT][:, None, None] * head(_hbase)
            _hsum = c[:, HALT]
        if ban1 is None: s._hops = []; s._hopq = []
        for _t_ in range(steps):
            # MIN_STEPS IS OFF UNDER CHAIN_VOTE, and must be. It zeroes the accumulated HALT column at the top of
            # each early hop, so an increment counted as "halted at hop t" would be discarded a hop later and the
            # accumulator would stop being a convex combination -- mass counted twice, or lost. It also exists to
            # stop the router writing the experts off before they can learn, and under voting that reasoning
            # inverts: HALT now SELECTS which hop answers rather than switching the fabric off, so forcing it to
            # keep walking is forcing it to keep a worse answer.
            if _t_ < s.min_steps:                                             # block HALT early: force the nodes to be used
                c = torch.cat([c[:, :N], torch.zeros_like(c[:, N:])], -1)
                c = c / c.sum(-1, keepdim=True).clamp_min(1e-9)
            nm = c[:, :N]
            bal = bal + N * (nm.mean(0) ** 2).sum()                            # load balance: spread mass across nodes
            # SPARSE PER HOP. This computed EVERY node at every hop: Bo is (B,N,L,d), which at N=972, B=16,
            # L=256, d=768 is 12 GB for ONE hop -- times the depth budget, times the autograd graph. That is the
            # OOM, and it is why chaining could not be run at population scale at all.
            # Only the top-k by CURRENT routing mass are computed. The semantics are unchanged in the part that
            # matters -- mass still flows expert -> expert through the transition below, so an expert still builds
            # on another's output -- but a hop now costs k experts instead of N. Everything outside the top-k
            # contributed a weight of ~0 to the mixture anyway; it was computed, multiplied by nothing, and kept
            # alive in the graph for the backward pass.
            _ck = min(s.chain_k, N)
            _cv, _ci = nm.topk(_ck, dim=-1)                                   # (B,k) per WINDOW, not per batch
            # EXPLORATION, which this path did not have. society() swaps one slot per window for a low-use expert
            # precisely because top-k is on-policy: an expert outside the k is not merely unused, it is FROZEN, and
            # cannot improve into contention. Chaining had no such mechanism, and it is worse off without one --
            # measured on a 1024 population over 60 steps, the compute path reached 25% of the experts under
            # society and 8% under chaining, because mass CONCENTRATES as it flows: each hop's top-k is drawn from
            # a distribution the previous hop already sharpened. More hops did not mean more experts learning.
            if s.explore > 0 and _ck >= 2 and N > _ck and ban1 is None:
                _cold3 = sorted(range(N), key=lambda i: s.use.get(i, 0.0))[:max(8, N // 16)]
                _rows3 = [r for r in range(_ci.size(0)) if random.random() < s.explore]
                if _rows3:
                    _ci = _ci.clone(); _cv = _cv.clone()
                    for _r3 in _rows3:
                        _ci[_r3, -1] = random.choice(_cold3)
                        _cv[_r3, -1] = nm[_r3, _ci[_r3, -1]]                  # its REAL mass, not the displaced one's
                    s.explored = getattr(s, "explored", 0) + len(_rows3)
            # RECORD UTILIZATION HERE TOO. use[] was only written on the society path, so under SOCIETY=0 the
            # table stayed EMPTY -- and everything that reads it ran blind: culling ranks the bottom fraction by
            # utilization (all zero, so it culled arbitrarily), the breadth cap counts domains per expert, and the
            # discovery rule hands novel material to the "least-used" expert. A chaining run had none of that
            # information. Cheap to fix and it silently disabled three selection mechanisms.
            # ...but a COUNTERFACTUAL walk must not record anything: it did not happen, and letting it write
            # utilization would have the leave-one-out probe inflate the use counts of the experts it is measuring.
            if ban1 is None:
                with torch.no_grad():
                    for _uu in _ci[:, 0].tolist(): s.use[_uu] = s.use.get(_uu, 0.0) + 1.0
                    wacc = nm.detach() if wacc is None else wacc + nm.detach()   # per-window mass, over all hops
            # ORDERING, RECORDED IN THE REAL RUN. The question "can the chain vary its SECOND move for the same
            # first move" was only ever asked on a 24-expert synthetic toy, which is not the system. Recording the
            # (hop0, hop1) pair here costs two small int lists on a cadence and answers it at whatever scale the
            # run actually uses, against real material.
            if ban1 is None and getattr(s, "_sample_ord", False) and _t_ < 2:
                s._ord.append((_t_, _ci[:, 0].tolist()))
            if getattr(s, '_trace', None) is not None: s._trace.append(_ci[:, 0].tolist())
            _cA = s.A[_ci]; _cB = s.B[_ci]                                    # (B,k,d,r) (B,k,r,d)
            Bo = h.unsqueeze(1) + torch.einsum('bklr,bkrd->bkld',
                                               torch.einsum('bld,bkdr->bklr', h, _cA), _cB)
            _cw = _cv / _cv.sum(-1, keepdim=True).clamp_min(1e-9)
            _hb = c[:, HALT]                                                  # halted mass BEFORE this hop settles
            if _vote:
                # SOCIETY'S RULE, AT THIS HOP: every computed expert decodes its OWN output and they are blended
                # as PREDICTIONS. Only the top ENS_K are decoded -- the rest carry ~0 weight and decoding all of
                # chain_k would hold k x (B,L,V) in the graph per hop.
                _vk = min(ENS_K, _ck)
                _vwn = _cw[:, :_vk] / _cw[:, :_vk].sum(-1, keepdim=True).clamp_min(1e-9)
                _lgt = None
                for _q7 in range(_vk):
                    _l7 = head(s.norm(Bo[:, _q7])) * _vwn[:, _q7][:, None, None]
                    _lgt = _l7 if _lgt is None else _lgt + _l7
            # DISTINCTNESS ON THE CHAINING PATH. DIV_W was gated on SOCIETY because it needs per-expert outputs and
            # a composed walk has no separable per-expert LOGITS -- but it does have separable per-expert OUTPUTS,
            # right here in Bo, one set per hop. Penalising agreement between the two experts a hop actually leans
            # on is the same pressure the society path applies, computed where this path has the tensors.
            # It matters now because specialization finally moved off the floor (0.094 vs a 0.000 null) and DIV_W
            # is the only term in the system that rewards experts for DIFFERING. It has never once been on.
            if s.div_w > 0 and _ck >= 2 and ban1 is None:
                _da = Bo[:, 0].reshape(Bo.size(0), -1); _db = Bo[:, 1].reshape(Bo.size(0), -1)
                _dv = F.cosine_similarity(_da, _db, dim=-1).clamp_min(0.0).mean()
                dacc = _dv if dacc is None else dacc + _dv
            upd = (_cw[:, :, None, None] * Bo).sum(1)                         # soft mixture of the computed nodes
            # HALT NOW ACTUALLY HALTS. This renormalised over the top-k and applied the step at FULL strength no
            # matter how much mass had already halted -- so the loop ran its full depth and h kept changing after
            # the router had decided to stop. HALT accumulated mass and charged ponder cost while changing
            # nothing about when the computation ended: the router was answering "how much" and never "when".
            # Scaling the residual by the mass still routing makes the decision real -- as HALT absorbs, updates
            # shrink to zero and h settles, which is the router determining completion rather than the loop
            # counter determining it.
            _alive = nm.sum(-1, keepdim=True)[:, :, None]                     # (B,1,1) mass NOT yet halted
            h = s.norm(h + s.alpha * _alive * (upd - h))                      # residual fabric step, gated by HALT
            # PER-HOP STATE, kept for DEEP SUPERVISION. With a single loss at the end of the walk, hop t's router
            # learns only through the chain rule from D-t hops away; scoring head(h_t) directly gives that hop --
            # and the expert it chose -- a local answer to "did this move help?". It is also what makes the
            # curriculum's stopping test meaningful, since depth-1 then has a loss of its own.
            if ban1 is None and s.sup_w > 0: s._hops.append(h)
            depth = depth + (1 - c[:, HALT]).mean(); mass = mass + c.mean(0).detach()
            if ban1 is None:
                with torch.no_grad():                     # the HALT column, as it actually was during training
                    _hh = c[:, HALT].mean().detach()
                    s._mass_ema = _hh if s._mass_ema is None else 0.99 * s._mass_ema + 0.01 * _hh
            ent = -(c.clamp_min(1e-9).log() * c).sum(-1)
            summ = torch.stack([nm.sum(-1), c[:, HALT], ent], -1)             # recurrent control summary
            bias = nb + s.ctrl(summ)
            # PER-SOURCE, and only for the sources that actually hold mass. The full (B,N,N+1) transition is
            # 1.07 GB at N=4096 alone; the top-k sources hold essentially all of it, so R is built for those.
            Q = (s.q_route(gist)[:, None, :] + _SRCd[_ci]                      # (B,k,dk): + the HOLDER's own mark
                 + bias[:, None, :]
                 + (s.hproj(h.mean(1))[:, None, :] if s.state_q else 0))       # ...+ what the state looks like NOW
            # THE QUERY IS A REQUEST, AND IT MAY HAVE NO ANSWER. Spawn-by-specification ran at ENTRY only, so the
            # case the router hits at hop 2 -- "given where I am, I want an expert like THIS" with nothing near it
            # -- could never create anything. Kept for the caller to act on after the walk: growing the population
            # mid-walk would resize the very tensors being indexed.
            if ban1 is None: s._hopq.append(Q[:1, 0].detach())
            _rlg = torch.einsum('bkd,md->bkm', Q, K) / max(1e-3, s.route_t)
            if ban is not None:                                                # ...and out of every TRANSITION too
                _rlg[:, :, :N] = _rlg[:, :, :N].masked_fill(ban.to(_rlg.device)[None, None], float("-inf"))
            if s.halt_on: _rlg = _rlg + F.pad(s.halt_b.expand(1, 1, 1), (N, 0))   # same prior on every transition
            if ban1 is not None: _rlg[:, :, ban1] = float("-inf")              # ...and out of every TRANSITION
            R = torch.softmax(_rlg, -1)                                        # (B,k,N+1)
            _cvn = _cv / _cv.sum(-1, keepdim=True).clamp_min(1e-9)
            nxt = torch.einsum('bk,bkm->bm', _cvn * nm.sum(-1, keepdim=True), R)   # mass moves FROM each holder
            nxt = nxt.clone(); nxt[:, HALT] = nxt[:, HALT] + c[:, HALT]       # HALT absorbs
            c = nxt / nxt.sum(-1, keepdim=True).clamp_min(1e-9)
            if _vote:
                # WHAT HALTED HERE TAKES THIS HOP'S ANSWER. This is the term that makes HALT mean "done".
                _dh = (c[:, HALT] - _hb).clamp_min(0.0)
                lgacc = lgacc + _dh[:, None, None] * _lgt
                _hsum = _hsum + _dh
                _lglast = _lgt
        if _vote:
            _rem = (1.0 - c[:, HALT]).clamp_min(0.0)                          # never halted -> the last hop's answer
            lgacc = lgacc + _rem[:, None, None] * _lglast
            if s._vchk < 3:                                                    # CHECK THE INVARIANT, first few steps
                with torch.no_grad():
                    _tw = float((_hsum + _rem).mean())
                    if abs(_tw - 1.0) > 1e-3:
                        print(f"  [chain-vote] !! hop weights sum to {_tw:.4f}, not 1 -- the per-hop blend is no "
                              f"longer a convex combination and the logits are mis-scaled.")
                s._vchk += 1
            s._votelg = lgacc                                                  # weights sum to 1 by construction
        # PER-WINDOW EXPERT UTILIZATION, the chaining twin of society()'s `w`. Everything that attributes an
        # OUTCOME to an EXPERT reads a (B,N) table -- competence EMAs, the fast/slow error pair the sustained-error
        # cull rule needs, the domain affiliation map, per-expert memory ownership. All of it was gated on SOCIETY
        # and therefore dead under chaining, so a chaining run had exactly one live cull route (utilization under
        # capacity pressure) and no idea which expert was responsible for anything.
        # Integrated over hops rather than taken at entry: an expert that receives mass on hop 3 served the window
        # just as much as the one that took it at hop 0.
        if ban1 is None:
            s._div = (dacc / steps) if dacc is not None else None
            s._wrun = (wacc / wacc.sum(-1, keepdim=True).clamp_min(1e-9)) if wacc is not None else None
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
    def __init__(s, rel=0.002, cooldown=1500, warmup=2000, z=4.0, burst=3, ramp=0, rmin=600, rmax=20000,
                 rate=0.10, ramp_to=1.0):
        s.fast = s.slow = None; s.rel = rel; s.cool = cooldown; s.warm = warmup; s.last = -10**9
        s.z = z; s.burst = max(1, burst); s.ramp = ramp; s.rmin = rmin; s.rmax = rmax
        s.dev = 0.0; s.n = 0; s.state = "W"; s.t0 = 0; s.blackout = -10**9; s.why = ""
        # FAB_GROW=0 freezes the population at FAB_N0 for the whole run: no ramp, no regression burst, no stall
        # growth. Nothing else changes -- culling, routing, selection and replication all still run, so this
        # isolates GROWTH from everything else the fabric does. The 2.4 -> 3.5 climb between steps 6k and 12k is
        # the largest remaining loss in every arm at every seed, and it coincides with the ramp building the
        # population; this is the arm that says whether those two facts are related.
        s.grow_on = bool(int(_env("FAB_GROW", 1)))
        s.latch = bool(int(_env("FAB_RAMP_LATCH", 1)))          # 0 restores the never-terminating ramp
        s.ramp_done = False; s.n_ramp = 0; s.n_stall = 0; s.n_regr = 0   # why growth fired, for the report
        s.rate = max(0.0, rate); s.ramp_to = ramp_to      # GEOMETRIC ramp: grow a FRACTION of the population, not a
        #   fixed count. +3 every 50 steps reaches ~240 experts by the end of a 4000-step ramp window and then stops,
        #   because afterwards growth needs a plateau or a regression and those are rare. A population of thousands is
        #   unreachable by addition; 3 -> 4096 at +10% per event is ~76 events. The ramp also ends on POPULATION SIZE
        #   rather than on a step number, so it does not quietly expire before the population is built.
    def note_shift(s, t): s.blackout = t          # retok / resample: the loss jump is OURS, not the data's
    def step(s, loss, t, n=None, cap=None):
        if not s.grow_on: return 0                                           # population frozen at FAB_N0
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
        # THE RAMP MUST LATCH OFF, and it did not. The condition was `n < ramp_to * cap` -- CURRENT population
        # below the target -- and culling keeps the population just under the cap indefinitely, so the ramp stayed
        # armed for the whole run and re-fired every cool//8 = 187 steps.
        # The arithmetic, since the obvious reading is wrong: growth is clamped by FAB_NMAX - n, so at the cap the
        # ramp adds NOTHING. What it does is REFILL, immediately, whatever the last cull removed. Across three
        # pilots: ~10062 grown = ~4093 building the population once + ~5969 refilling 5969 culls. The population
        # reads as a stable 4096 while being replaced about 1.5x over, so a tenth of it is freshly-initialised at
        # any moment -- and the identity space that every eemb key and every centroid is defined over is exactly
        # that churning set. When this was written, all three runs diverged shortly after the population first
        # reached the cap -- but divergence has since been traced to the LR schedule and the eval-pass centroid
        # corruption, both fixed, and the six-arm pilot reaches the cap without diverging. The cull-refill
        # dynamic below is real and still worth understanding; the divergence it was blamed for is not.
        # This is NOT the loss-driven feedback loop guessed at earlier: the ramp never reads the loss. It is a
        # cull-refill cycle that selection cannot win, because whatever it removes is replaced within 187 steps.
        # Latch on FIRST arrival: the ramp exists to BUILD the population, and it is built once. After that,
        # growth must come from a REGRESSION or a stall -- i.e. from evidence that more capacity is needed.
        if s.latch and n is not None and cap is not None and n >= s.ramp_to * cap: s.ramp_done = True
        _ramping = (t < s.ramp) if (n is None or cap is None) else not s.ramp_done
        if s.ramp and _ramping and t - s.last >= max(1, s.cool // 8):
            s.last = t; s.why = "ramp"; s.n_ramp += 1
            return max(s.burst, int(s.rate * n)) if n else s.burst
        if s.state == "R":                                                   # RECOVER: wait for the stall
            if t - s.t0 >= s.rmin and (improving < s.rel or t - s.t0 > s.rmax): s.state = "W"
            return 0
        if t - s.last < s.cool or t - s.blackout < s.cool: return 0
        unexpected = (loss - s.slow) > s.z * max(1e-6, s.dev)                 # a REGRESSION we did not cause
        if unexpected or (t >= s.warm and improving < s.rel):
            s.last = t; s.t0 = t; s.state = "R"; s.why = "REGRESSION" if unexpected else "stall"
            if unexpected: s.n_regr += 1
            else: s.n_stall += 1
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
        s.created = 0; s.replicated = 0; s.removed = 0; s.merged = 0; s.spared = 0
        s.comp_of = None                                      # set by the loop: expert id -> (its competence EMA,
        #   the population's). Injected rather than computed here because the router does not see the LM loss.
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
                    # COMPETENCE PROTECTION, same principle as the domains: `fit` here is use-per-unit-time, so the
                    # bottom of this ranking is "rarely called", which a niche expert and a dead one share. Spare
                    # the ones that model their own material better than the population does.
                    if COMP_PROTECT and s.comp_of is not None:
                        # CONTRIBUTION first (counterfactual: is the system worse without it?), competence EMA only
                        # as a fallback where no contribution has been measured yet. The EMA can be fooled by easy
                        # material; the counterfactual cannot, and cannot be gamed by a loud message either.
                        _c, _g = s.comp_of(i)
                        if _c is not None and _g is not None and (_c > 0 if _g == "contrib" else _c < _g):
                            s.spared = getattr(s, "spared", 0) + 1; continue
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
SIG_SPACE = _env("SIG_SPACE", "bytes").strip().lower()
if SIG_SPACE not in ("bytes", "tokens"): sys.exit(f"SIG_SPACE must be bytes|tokens, got {SIG_SPACE!r}")
SIG_WIN = _i("SIG_WIN", 0)
ENC_V = V if (USE_TOK and (not TOK_ONLINE or SIG_SPACE == "tokens")) else 256
class SigEncoder(nn.Module):                               # LEARNED, LIVE domain-signature encoder (stays GRU regardless of LM)
    def __init__(s, d, sd, nv=None):
        # nv OVERRIDES ENC_V so a loader can size the table from a CHECKPOINT rather than from this run's env.
        # Without it prompt.py had to keep its own copy of this class, and a duplicated model class is what left
        # prompt.py dead for several commits when the fabric changed underneath it.
        super().__init__(); s.emb = nn.Embedding(nv or ENC_V, d); s.gru = nn.GRU(d, d, batch_first=True); s.proj = nn.Linear(d, sd)
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
KEY_SRC = _env("KEY_SRC", "model")
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
    _vw = ENC_VREG; _cw = ENC_CREG
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
        s.comp = {}; s.comp_glob = None                                   # COMPETENCE: EMA bits/window on the material
        #   this domain wins, against the population's own EMA. Selection was utilization-only; this is the term
        #   that lets a rarely-fed domain survive on being GOOD at what it does get.
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
        _L = len(flat[0]) if flat else 0                                  # DEFENSIVE: one ragged window used to kill
        if any(len(w) != _L for w in flat):                               #   the whole run here. Normalise instead --
            flat = [(list(w[:_L]) + [0] * (_L - len(w))) if len(w) != _L else w for w in flat]   # a truncated or
            print(f"  [rekey] normalised {sum(1 for w in s.wins.values() for _ in w)} sample windows to width {_L} "
                  f"-- widths should not differ within a run; report this if it appears.")
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
        # === EMPTY DOMAINS ARE CULLED, unconditionally =============================================================
        # The existing cull needs `act < min_size AND unseen > stale` -- a conjunction that a domain holding NOTHING
        # can still fail, because `act` decays toward zero rather than reaching it and `last` only moves when the
        # domain is fed. So an empty domain sat in the population indefinitely, counted in every domain total, and
        # took a share of the routing softmax. The pilot log shows the symptom: zero culls for the first 1000 steps
        # against 5-8 merges per manage -- domains consolidated but were never selected OUT.
        # Empty means exactly that: no memory entries carry its provenance and it holds no sample windows. Nothing
        # is lost by removing it, so it does not need the staleness conjunction, only enough grace to have been
        # filled in the first place.
        if DOM_CULL_EMPTY:
            for d in [i for i in list(s.cent) if not s.wins.get(i)]:
                if len(s.cent) <= 1: break
                if step - s.born.get(d, step) < DOM_GRACE: continue        # newborns have not had a chance yet
                if mem is not None and int((mem.src == int(d)).sum()) > 0: continue   # still owns memory -> not empty
                for _D in (s.cent, s.wins, s.size, s.last, s.act, s.born, s.rad, s.visits, s.bornb, s.tokc, s.comp):
                    _D.pop(d, None)
                culled += 1; s.emptied = getattr(s, "emptied", 0) + 1; s._dirty()
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
                # COMPETENCE PROTECTION. Rare and stale is exactly what a niche domain looks like from a
                # utilization-only vantage point, and it is also what a dead one looks like. The difference is
                # whether the material it does get is modelled BETTER than the population manages on average.
                if COMP_PROTECT and s.comp_glob is not None and d in s.comp and s.comp[d] < s.comp_glob:
                    s.protected = getattr(s, "protected", 0) + 1; continue
                if mem is not None: mem.delete_src(d)                     # CULL -> memory follows (direct prune)
                for _D in (s.cent, s.wins, s.size, s.last, s.act, s.born, s.rad, s.visits, s.bornb, s.tokc): _D.pop(d, None)
                culled += 1; s._dirty()
        for i in s.act: s.act[i] *= DOM_DECAY                             # DECAY -> `act` reflects RECENT use, so a domain
        s.comp = {i: v for i, v in s.comp.items() if i in s.cent}         # competence follows the population
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
    seq = list(seed); _bad = [0]
    for _ in range(n):
        x = torch.tensor([seq[-256:]], device=DEV)
        lg = (fab_logits(model, fab, model.encode(x), gist)[0, -1] if fab is not None
              else model(x)[0][0, -1])
        lg = torch.nan_to_num(lg, nan=-1e4, posinf=1e4, neginf=-1e4)
        if vlim is not None and vlim < lg.numel(): lg = lg.clone(); lg[vlim:] = float("-inf")   # never sample untrained ids
        pm = F.softmax(lg / temp, -1)
        if use_mem:
            dist, _cf, _, _ = mem.read(mem_key(x)[-1:])   # retrieval for the next position
            pmem = dist[0]; hp = _mem_hp(dist, _cf, dim=-1)[0]
            p = (1 - hp) * pm + hp * pmem
            p = (p / p.sum().clamp_min(1e-9))
        else:
            p = pm
        # SANITIZE BEFORE SAMPLING. multinomial raises a device-side CUDA assert on any NaN/inf/negative entry or
        # an all-zero row, and it does so INSIDE the report -- which is how four arms of an 18-arm grid finished
        # training and then lost their entire report to a bad sample. A diverged run produces exactly that: the
        # logits go non-finite, softmax yields NaN, and the run is destroyed at the last step.
        # Generation is a DIAGNOSTIC of a model that may already be broken. It must survive one.
        if not bool(torch.isfinite(p).all()) or float(p.sum()) <= 0:
            p = torch.nan_to_num(p, nan=0.0, posinf=0.0, neginf=0.0).clamp_min(0.0)
            if float(p.sum()) <= 0:                       # nothing survived: fall back to uniform over the live vocab
                _n = p.numel() if vlim is None else min(vlim, p.numel())
                p = torch.zeros_like(p); p[:_n] = 1.0 / max(1, _n)
            _bad[0] = _bad[0] + 1
        seq.append(int(torch.multinomial(p, 1)))
    if _bad[0]:
        print(f"  [generate] {_bad[0]} of {n} sampling steps had a non-finite distribution and were repaired -- "
              f"the model's logits are not finite, which is a REAL failure of the run, not of the sampler. "
              f"Read the generated text as evidence of that, not as output.")
    return seq[len(seed):]

@torch.no_grad()
def _units(TOK, USE_TOK, text):
    """Text -> the units the model is trained on: tokens if the tokenizer is on, raw bytes if not.
    Written out inline in eight places, every one of them the same conditional.
    count=False matters and is easy to drop: counting would tally the pair statistics that drive MINTING, so an
    EVALUATION pass would silently steer the vocabulary."""
    return TOK.segment(text, count=False) if USE_TOK else list(text)


def _eval_logits(model, fab, FABRIC, x):
    """Logits for x through the SAME path the model trained with -- the one line that must never drift between
    the six evaluation sites that use it. `fab if FABRIC else None` is the whole of it, and getting that wrong
    scores the base model while claiming to score the system."""
    return fab_logits(model, fab if FABRIC else None, model.encode(x))


def fab_logits(model, fab, h, gist=None, nov=None, k=None):
    """THE single path from hidden state to logits. In SOCIETY mode the experts are ENSEMBLED AT THE PREDICTION
    LEVEL (sum of w_i * head(o_i)), not by averaging their hidden states -- averaging hiddens produces a
    representation no expert was ever trained to emit, which decodes badly. Blending OUTPUTS is what makes the
    population an ensemble that degrades gracefully when a member is deleted."""
    if fab is None: return model.head(h)
    # THIS IS THE EVAL PATH, AND IT MUST NOT TRAIN THE ROUTER'S REGIONS. The zero gist below is a placeholder so
    # the routing arithmetic has the right shape -- it is NOT a signature. ground_update normalises it (zero) and
    # moves every top-ranked expert's centroid toward the origin, which is how a diagnostic's sampling frequency
    # came to change the final model at all. learn_regions=False makes an eval pass read-only.
    # The size of that change is NOT attributable to accumulation here -- see route_w -- it is chaotic
    # sensitivity. The correctness argument stands on its own: a diagnostic must not train the router.
    # Training does not come through here: it calls fab.society()/fab() directly with a real signature.
    if gist is None: gist = torch.zeros(h.size(0), fab.q_entry.in_features, device=h.device)
    if nov is None: nov = torch.zeros(h.size(0), device=h.device)
    if not SOCIETY:
        _hh = fab(h, gist, nov, head=(model.head if fab.vote else None), learn_regions=False)[0]
        return fab._votelg if fab._votelg is not None else model.head(_hh)
    kk = int(k or ENS_K)
    w, O, oid = fab.society(h, gist, nov, k=kk, learn_regions=False)   # SPARSE: only the kk it is about to use
    ww = w.gather(1, oid)                                     # oid is (B,kk): each row's OWN experts and weights
    ww = ww / ww.sum(-1, keepdim=True).clamp_min(1e-9)
    out = None
    for j in range(O.size(1)):
        lj = model.head(fab.norm(O[:, j])) * ww[:, j][:, None, None]
        out = lj if out is None else out + lj
    return halt_blend(model, fab, h, out)


def halt_blend(model, fab, h, out):
    """Spend the router's HALT mass on the base model's own head. The society path is one-shot, so HALT cannot mean
    "stop walking" the way it does in the chaining loop -- it means "no expert is needed for this window", and the
    only honest way to honour that is to let the base representation complete it directly.
    Same operator, same key, same softmax on both paths; only what the halted mass BUYS differs."""
    hm = getattr(fab, "_halt", None)
    if hm is None: return out
    hm = hm[:, :, None]                                    # (B,1,1) broadcast over positions and vocab
    return (1 - hm) * out + hm * model.head(h)


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
    # WHICH CODE PRODUCED THIS LOG. Arms are compared across days and commits; without this, "pilot 6 vs the
    # grid" is a comparison between two things nobody can identify later. Printed first, before anything can fail.
    def _git(*a):
        try:
            import subprocess
            return subprocess.run(("git",) + a, cwd=os.path.dirname(os.path.abspath(__file__)),
                                  capture_output=True, text=True, timeout=5).stdout.strip()
        except Exception:
            return ""
    _br = _git("rev-parse", "--abbrev-ref", "HEAD") or "?"
    _sha = _git("rev-parse", "--short=10", "HEAD") or "?"
    # TRACKED modifications only. `git status --porcelain` also lists UNTRACKED files, and a working tree that
    # has ever run a pilot is full of them -- fetched corpora, checkpoints, logs. Counting those as "uncommitted
    # changes" marks a freshly-pulled clean checkout as DIRTY, which is a false alarm about the one thing this
    # line exists to certify: whether the CODE matches the commit.
    _mods = _git("status", "--porcelain", "--untracked-files=no")
    _dirty = (f"DIRTY -- {len([l for l in _mods.splitlines() if l.strip()])} tracked file(s) modified, this log is "
              f"NOT reproducible from the commit") if _mods else "clean"
    _desc = _git("log", "-1", "--format=%cs %s")
    print(f"[build] branch {_br} | commit {_sha} | {_dirty}" + (f" | {_desc}" if _desc else ""))
    print(f"self-organize | d{D} | {NP} hidden processes | stream {STREAM_LEN} | win {WIN} | SIG_MODE={SIG_MODE} | data {DATA_MODE}")
    # === WHAT IS ACTUALLY ON ===================================================================================
    # DEFERRED until every object exists -- see _banner() below, called after construction. This used to print
    # HERE, before model/fab/mem were built, which forced it to re-read os.environ for everything. That is a
    # PARALLEL DESCRIPTION of the system rather than a reading of it, and a parallel description drifts: it printed
    # "per-expert memory ON " for a 48k-step run where the effective value was `... and SOCIETY` on a SOCIETY=0
    # run, i.e. off from step 0. Reading the live objects makes that class of lie impossible rather than fixed.
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
    def encpos(s):
        """Loop index (a TOKEN index under ONLINE) -> an index INTO ENC_SEQ. The one place this conversion lives.
        ENC_SEQ is bytes under SIG_SPACE=bytes and the token stream under SIG_SPACE=tokens, so the translation
        through tok_bs is right in one case and wrong in the other. The training loop got this right inline
        (`i if SIG_SPACE == "tokens" else bpos`); every EVAL site did `tok_bs[s]` unconditionally, which under
        SIG_SPACE=tokens scales a token index by ~2.5 and reads a window from the wrong place -- silently, until
        the offset ran off the end of ENC_SEQ and `torch.tensor` raised on a zero-length slice. The smoke grid
        caught it as a crash; the crash was the visible tail of a misread that had no symptom before it."""
        if not ONLINE or SIG_SPACE == "tokens": return s
        return tok_bs[s] if s < len(tok_bs) else (tok_bs[-1] if tok_bs else s)
    def encwin(b):
        """A WIN-long window of ENC_SEQ starting at b, always. Slicing past the end returns a SHORT list and
        torch.tensor then raises on the ragged batch -- an exception whose message ('expected sequence of length
        64, got 0') names neither ENC_SEQ nor the tail. Clamp the start, pad the remainder."""
        b = max(0, min(int(b), max(0, len(ENC_SEQ) - 1)))
        w = list(ENC_SEQ[b:b + WIN])
        return w if len(w) == WIN else (w + [0] * (WIN - len(w)))
    route_at = torch.full(((len(ENC_SEQ) if ONLINE else len(stream)) + WIN + 2,), -1, dtype=torch.int16) if EXPERTS else None
    model = build_lm().to(DEV); enc = SigEncoder(D, SIG_D).to(DEV)
    recon = Reconstructor(D, V, _i("RECON_TOK", 32), _i("RECON_HID", 64)).to(DEV) if VERIFY == "recon" else None
    # WORLD MODEL (first brick, gated off by default): reads OBSERVATION EMBEDDINGS (the lowest layer = the point where
    # new SENSES plug in) and learns to predict how that observed world EVOLVES in latent space (physics-like, modality-agnostic).
    WORLD_MODEL = bool(_i("WORLD_MODEL", 1)); WLAT = _i("WORLD_LAT", 32); WORLD_W = _f("WORLD_W", 0.1); WORLD_K = max(1, _i("WORLD_K", 1)); WHID = _i("WORLD_HID", 128)
    WORLD_VAR = _f("WORLD_VAR", 1.0)                     # anti-collapse (variance+decorrelation) weight -- applied at FULL strength,
    #   NOT scaled by WORLD_W (scaling it by 0.1 let the latent collapse to std 0.24; the standalone probe uses full strength).
    WORLD_GROW = bool(_i("WORLD_GROW", 1)) and WORLD_MODEL   # GROW-on-plateau + soft-cull the dynamics population (like experts).
    #   `and WORLD_MODEL` is load-bearing: WORLD_GROW defaults ON and its step hook calls world_fwd.n() OUTSIDE the
    #   `if WORLD_MODEL:` block, so WORLD_MODEL=0 crashed on None at the first MANAGE_EVERY. That is why the
    #   ab_no_world arm of the rerun exited 1 with a traceback and produced no data -- the one ablation that would
    #   have told us what the world model is worth was the one that could not run.
    WORLD_FEEDBACK = bool(_i("WORLD_FEEDBACK", 1))       # THE LINK THAT MAKES IT MATTER: wire the world model's forecast BACK to
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
    os.environ.setdefault("FAB_NMAX", str(_i("FAB_NMAX", 4096)))   # Fabric preallocates from it
    fab = Fabric(D, SIG_D, _i("FAB_DK", 32), _i("FAB_N0", 3), _f("FAB_ALPHA", 0.5), _i("FAB_STEPS", 4),
                 _f("FAB_HID_MULT", 2), _i("FAB_MIN_STEPS", 0 if SOCIETY else 2),
                 bool(_i("FAB_NORM_ONLY", 0))).to(DEV) if FABRIC else None
    # FAB_MIN_STEPS DEFAULTS BY PATH. On the society path HALT is unused and 0 is right. On the CHAINING path 0
    # means HALT can absorb on the very first hop -- measured: mean routed depth 0.00 of 4, i.e. chaining switched
    # on and nothing chained. Blocking HALT for two hops forces experts to actually compose before the router is
    # allowed to stop: depth 0.00 -> 0.60 on the same config. A composition mechanism that is enabled but never
    # entered is worse than one that is off, because it reads as tested.
    fabgrow = PlateauGrowth(_f("FAB_PLATEAU", 0.002), _i("FAB_COOLDOWN", 400), _i("FAB_WARMUP", 300),
                            _f("FAB_Z", 4.0), _i("FAB_BURST", 3), _i("FAB_RAMP", 4000),
                            _i("FAB_RECOVER_MIN", 600), _i("FAB_RECOVER_MAX", 20000),
                            _f("FAB_RAMP_RATE", 0.10), _f("FAB_RAMP_TO", 1.0)) if FABRIC else None
    # 64 was never a design decision, it was a default nothing pushed against -- and the population saturated it at
    # step 1295 of the pilot, after which "selection" is merge/cull churn over a full bank. With low-rank experts the
    # ceiling is memory: 2*NMAX*d*r floats, so 4096 experts costs 0.2 GB at d=768/r=8, 10k costs 0.5 GB, 1M costs 49.
    FAB_NMAX = _i("FAB_NMAX", 4096); PONDER = _f("PONDER", 0.01)   # raised from 8: with sparse top-k the cost of a
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
    # DID EACH LOSS TERM ACTUALLY FIRE? The config audit verifies a knob's VALUE was read; it cannot see whether
    # the code path that uses it was ever reached. DIV_W was set to 0.05 on a path that returns before the
    # distinctness term is computed, and the run came back identical to DIV_W=0 with nothing saying so. Counting
    # the steps each auxiliary term contributed to `tot` catches that whole class.
    _termfired = {}
    def _term(nm, v):
        if v is not None: _termfired[nm] = _termfired.get(nm, 0) + 1
        return v
    TOK_MINT_UNTIL = _i("TOK_MINT_UNTIL", 0)                  # freeze the vocabulary after this step; 0 = never
    _mint_frozen = [False]
    def _inherit_opt(opt, param, nid, a, b):
        """Give a newly minted token the Adam moments of the two tokens it was minted from. Without this its
        second moment is 0 and its first update is Adam's maximum step, which overwrites the warm start."""
        st = opt.state.get(param)
        if not st: return
        with torch.no_grad():
            for _k in ("exp_avg", "exp_avg_sq"):
                _t = st.get(_k)
                if _t is not None and _t.dim() >= 1 and nid < _t.size(0):
                    _t[nid] = 0.5 * (_t[a] + _t[b])
    if TOK_COMPOSE and USE_TOK and getattr(model, "compose", None) is not None:
        model.compose.set_vocab(TOK.id2bytes, DEV, VMAX)   # the table exists from step 0, sized to VMAX
        print(f"[tokenizer] TOK_COMPOSE: token vectors are COMPUTED from their bytes -- no per-token embedding or "
              f"head row is guessed at. Each token is composite(its bytes) + a learned residual that starts at "
              f"ZERO, so at the instant it is minted it IS its composite, and it becomes itself from there. "
              f"TOK_ANCHOR={TOK_ANCHOR} holds that residual near 0 for ~{TOK_ANCHOR_TAU:.0f} steps of the "
              f"token's own life, so the mint is a handover rather than a jump. No VMAX ceiling on the "
              f"composite. {model.compose.byte.num_embeddings} byte embeddings underlie all "
              f"{TOK.vocab_size} tokens.")
    BEST_TRACK = bool(_i("BEST_TRACK", 1))                    # keep the best-by-held-out checkpoint, not just the last
    _best_bpb = [None, -1, False]                             # [best mean bits/byte, step, saved?]
    _greach = []; _nbwd = 0                                   # experts receiving a nonzero gradient, sampled on cadence
    _rlive, _rseen = set(), set()                             # router parameters that DID / could receive gradient
    _lm_run = []; _lm_curve = []                              #   has very noisy gradients; this fixes that WITHOUT
                                                              #   breaking the stream. Also track the LM loss curve --
                                                              #   we had no way to see whether the LM had converged.
    IND_W = _f("IND_W", 0.5); IND_K = _i("IND_K", 2)          # independence-loss weight / how many experts get it
    BAL_WARM = _i("BAL_WARM", 4000)                           # load-balance pressure DECAYS to 0 over this many steps:
    DIV_W = _f("DIV_W", 0.0)                                  #   it exists to stop early collapse, but equal load and
    # (a module-level ROUTE_T = _f("ROUTE_T", 1.0) used to sit here: assigned, never read by anything, and with a
    #  DIFFERENT default from the one that actually routes -- Fabric.route_t reads ROUTE_T with default 0.1. Two
    #  names for one env var with disagreeing defaults is how a config gets misread. The live one is Fabric's.)
    #   DIV_W rewards experts for DISAGREEING (distinct competence); balance and specialization are opposed.
    def fab_bal(w): return w.size(1) * (w.mean(0) ** 2).sum()
    experts = ExpertBank(_i("MAX_EXPERTS", 256), D, _i("EXPERT_R", 4)).to(DEV) if EXPERTS else None
    router = ExpertRouter(experts, _f("EXPERT_NEW_DIST", 0.5), _i("EXPERT_CULL_STALE", 1000), _f("EXPERT_REP_MULT", 2.5),
                          _f("EXPERT_CULL_FRAC", 0.25), _i("EXPERT_GRACE", 3000), _env("CULL_MODE", "rank"),
                          _f("EXPERT_CULL_RANK", 0.08), _f("EXPERT_PRESSURE", 0.75), _f("EXPERT_MERGE_DIST", 0.10),
                          _i("EXPERT_FIT_WIN", 4000)) if EXPERTS else None
    if _i("PROBE", 1):                                     # measure actual step cost + extrapolate BEFORE the long run
        import time as _t
        xb = torch.randint(0, V, (1, WIN), device=DEV)
        def _one():                                        # time the REAL step incl. the fabric (or the estimate lies)
            h = model.encode(xb)
            if FABRIC:
                _g0 = torch.zeros(1, SIG_D, device=DEV); _n0 = torch.zeros(1, device=DEV)
                if SOCIETY:                                # timing probe: zero gist, so read-only (see fab_logits)
                    _w0, _O0, _ = fab.society(h, _g0, _n0, k=ENS_K, learn_regions=False)
                    model.head(fab.norm(_O0[:, 0])).sum().backward(); model.zero_grad()
                    if FABRIC: fab.zero_grad()
                    return
                h = fab(h, _g0, _n0, learn_regions=False)[0]
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
              f"{f'Ctrl-C in {_i(chr(80)+chr(82)+chr(79)+chr(66)+chr(69)+chr(95)+chr(87)+chr(65)+chr(73)+chr(84), 12)}s to abort/resize.' if (DEV=='cuda' and _i('PROBE_WAIT', 12) > 0) else ''}")
        print("  [probe is a LOWER BOUND -- it times ONLY the LM forward/backward. The real step also pays sig_of, the "
              "live contrastive encoder, the amortized re-key, domain assembly and memory. Trust the [rate] lines below.]")
        # PROBE_WAIT=0 for unattended runs. The pause exists so a human can Ctrl-C after reading the size
        # estimate; with nobody watching it is dead time per arm and the message is a lie.
        if DEV == "cuda" and _i("PROBE_WAIT", 12) > 0: _t.sleep(_i("PROBE_WAIT", 12))
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
    _regrown = []                                          # param groups re-created by a RESUME's growth replay
    _hb, _hbs = {}, 0                                      # held-out probe carried in from a RESUME (empty otherwise).
    #   Declared BEFORE the resume block: sitting after it, this line clobbered the value resume had just loaded.
    RESUME = _env("RESUME", "")
    _RD, _resume_step = None, 0
    if RESUME:
        _RD = torch.load(RESUME if RESUME.endswith(".pt") else f"{RESUME}/ckpt.pt", map_location=DEV, weights_only=False)
        if FABRIC and _RD.get("fab_cfg"):
            fab.n_live = max(fab.n_live, min(int(_RD["fab_cfg"]["n"]), fab.cap))   # rows already exist
        if WORLD_MODEL and _RD.get("world_cfg"):
            # REPLAY THE PARAM GROUPS, not just the population size. Growth calls om.add_param_group DURING
            # training, so a checkpoint taken after any growth has more groups than a freshly built optimizer --
            # and load_state_dict then refuses the whole thing, discarding every moment. Capturing what each
            # replayed grow() returns lets the optimizer below be rebuilt with the SAME group structure, in the
            # same order, so the moments load exactly. This was the last "known broken, reported not fixed" item.
            while world_fwd.n() < _RD["world_cfg"]["n"]:
                _np2 = world_fwd.grow()
                if _np2: _regrown.append(_np2)
        model.load_state_dict(_RD["model"]); _load_enc(enc, _RD["enc"])
        if FABRIC and _RD.get("fab") is not None:
            # TOLERANT, AND LOUD ABOUT IT. A checkpoint written before a router parameter existed (halt_b is the
            # current example) is missing that key, and a strict load throws away the ENTIRE fabric -- every
            # expert, every centroid -- over one freshly-initialised scalar. Load non-strict so a resume across a
            # code change works, and PRINT what did not match, because silently absorbing a mismatch is how a
            # resume quietly loads a different model than the one that was saved.
            _mk = fab.load_state_dict(_RD["fab"], strict=False)
            if _mk.missing_keys or _mk.unexpected_keys:
                print(f"  [resume] fabric state partially matched -- missing {list(_mk.missing_keys)} "
                      f"(left at init), unexpected {list(_mk.unexpected_keys)} (ignored)")
        if EXPERTS and _RD.get("experts") is not None: experts.load_state_dict(_RD["experts"])
        if WORLD_MODEL and _RD.get("world_enc") is not None:
            world_enc.load_state_dict(_RD["world_enc"]); world_fwd.load_state_dict(_RD["world_fwd"])
            if world_proj is not None and _RD.get("world_proj") is not None: world_proj.load_state_dict(_RD["world_proj"])
        _resume_step = int(_RD.get("step", 0))
    # PARAM-GROUP STRUCTURE MUST MATCH THE CHECKPOINT. Anything the resume replayed as a grow() was originally its
    # OWN group (add_param_group during training), so it is excluded from the base group and re-added below in the
    # same order. Without this the optimizer had one group where the checkpoint had several, load_state_dict threw,
    # and every Adam moment was silently discarded on every resume.
    _rg_ids = {id(_x) for _g in _regrown for _x in _g}
    _base = [_x for _x in (list(model.parameters()) + (list(experts.parameters()) if EXPERTS else [])
                           + (list(fab.parameters()) if FABRIC else [])
                           + (list(recon.parameters()) if recon is not None else [])
                           + (list(world_enc.parameters()) + list(world_fwd.parameters()) if WORLD_MODEL else [])
                           + (list(world_proj.parameters()) if world_proj is not None else []))
             if id(_x) not in _rg_ids]
    # === LEARNING RATE ======================================================================================
    # There was NO SCHEDULE: lr=2e-3, constant, for the whole run. Every pilot in this project -- 17 of them,
    # GRU and transformer, fabric and FABRIC=0, every routing variant -- bottoms in held-out bits/byte at ~2.4
    # around step 6000 and rises to ~3.8-4.1 by 48000. A cause common to all of them cannot be the fabric, the
    # router or the blend rule. A constant 2e-3 on AdamW for 48k steps is exactly that shape: fast early progress,
    # then the optimizer bounces around a minimum it can no longer settle into, and slowly degrades.
    # This is a hypothesis, not a proof -- but unlike the tokenizer theory it explains the transformer arms too,
    # and it is one flag to test. LR_SCHED=none restores the old behaviour exactly.
    LR = _f("LR", 2e-3); LR_SCHED = _env("LR_SCHED", "cosine")
    LR_WARMUP = _i("LR_WARMUP", 1000); LR_MIN_FRAC = _f("LR_MIN_FRAC", 0.05)
    om = torch.optim.AdamW(_base, lr=LR, weight_decay=WD)
    for _g in _regrown: om.add_param_group({"params": _g})   # same groups, same order as the original run
    oe = torch.optim.AdamW(enc.parameters(), lr=LR, weight_decay=WD)
    def _lr_at(st, total):
        """Linear warmup, then cosine to LR_MIN_FRAC of peak. Never returns 0: this is a continual-learning
        system and a schedule that anneals to nothing cannot learn anything that arrives late."""
        if LR_SCHED == "none": return LR
        # WARMUP CANNOT EXCEED THE RUN. At LR_WARMUP=1000 a 360-step run never leaves warmup and trains at a
        # third of the peak rate throughout -- which looks like the schedule hurting when it is the schedule
        # never having run. Clamped to a tenth of the total.
        _w = min(LR_WARMUP, max(1, total // 10))
        if st < _w: return LR * (st + 1) / _w
        _p = min(1.0, (st - _w) / max(1, total - _w))
        return LR * (LR_MIN_FRAC + (1 - LR_MIN_FRAC) * 0.5 * (1 + math.cos(math.pi * _p)))
    # PER-EXPERT MEMORY: each expert owns MEM_QUOTA entries, evicted by LRU on last USE. Sized to FAB_NMAX so the
    # partition does not have to be rebuilt as the population grows. MEM_PER_EXPERT=0 keeps the single global store.
    # DEFAULT OFF, on measurement: same seed, same config, only the store differs --
    #   global 200k slots -> memory contributes -0.097 b/B
    #   32 owners x 64    -> memory contributes -0.652 b/B
    # The partition costs 0.555 b/B at the scale tested, so it does not become the default path until it is shown to
    # help. (Memory being slightly net-negative even globally is a separate, pre-existing finding.)
    # NOT society-only any more. Ownership needs one thing -- a (B,N) table saying which expert served which
    # window -- and the chaining path now produces exactly that (fab._wrun). Gating it on SOCIETY meant flipping
    # to chaining silently turned per-expert memory OFF, which is the failure mode the [config] banner exists for.
    MEM_PER_EXPERT = bool(_i("MEM_PER_EXPERT", 1)) and FABRIC
    MEM_QUOTA = _i("MEM_QUOTA", 128)
    mem = EditableMemory(_i("MEM_CAP", 200000), D, DEV, V, _f("WRITE_GATE", 0.3), _f("WRONG_THRESH", 1.0), _i("TOPK", 8),
                         ctx_w=(KW if KEY_SRC == "model" else 0), wrong_margin=_f("WRONG_MARGIN", 1.5), wrong_min_n=_i("WRONG_MIN_N", 3),
                         adaptive_gate=bool(_i("WRITE_ADAPTIVE", 0)), gate_target=_f("WRITE_TARGET", 0.5),
                         evict=_env("EVICT", "recency"), use_decay=_f("USE_DECAY", 0.98), decay_every=_i("DECAY_EVERY", 20000),
                         quantile_gate=bool(_i("WRITE_QUANTILE", 1)),   # WRITE_QUANTILE=0 restores the old additive controller
                         n_own=(min(_i("FAB_NMAX", 4096), _i("MEM_OWNERS", 64)) if MEM_PER_EXPERT else 1), quota=(MEM_QUOTA if MEM_PER_EXPERT else None))
    if MEM_PER_EXPERT:
        print(f"[memory] PER-EXPERT: {mem.n_own} owners x {mem.quota} entries = {mem.cap} slots, LRU by last USE "
              f"(writes partitioned by routed expert; reads global so information still mixes)")
    asm = DomainAssembler()
    if _RD is not None:                                    # part 2 of RESUME: optimizer moments, memory store, domains
        try: om.load_state_dict(_RD["opt_m"]); oe.load_state_dict(_RD["opt_e"])
        except (KeyError, ValueError) as e:
            # KNOWN AND BOUNDED, not a mystery. Growth (world predictors, fabric nodes, experts) calls
            # om.add_param_group DURING training, so a checkpoint taken after any growth has more param groups than
            # the optimizer rebuilt at resume, which puts every parameter in group 0. The SET of parameters is the
            # same; only the grouping differs, and remapping moments across a different flattening would silently
            # attach them to the wrong tensors -- worse than restarting them. So they restart: Adam re-accumulates
            # its moments over roughly 1/(1-beta2) ~ 1000 steps, about 20 seconds at the observed rate. Weights,
            # memory, domains and the recurrence clock all restore exactly; this costs a brief transient, not a run.
            print(f"[resume] optimizer MOMENTS not restored ({type(e).__name__}: {e}).\n"
                  f"         Expected after growth -- the checkpoint has more param groups than a fresh optimizer.\n"
                  f"         Weights/memory/domains ARE restored; Adam re-warms over ~1000 steps. Watch the first\n"
                  f"         [rate] line after a resume: a brief bump in bits/byte is this, and it should recover.")
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
            # born/act: absent from checkpoints written before this was found, so default rather than KeyError --
            # born to the resume step (a restored domain is treated as newly born, which only makes DOM_GRACE
            # protect it a little longer), act to its recorded size so nothing looks unused on the first manage().
            asm.born = {int(k): int(v) for k, v in _a.get("born", {}).items()}
            asm.act = {int(k): float(v) for k, v in _a.get("act", {}).items()}
            for _i2 in asm.cent:
                asm.visits.setdefault(_i2, 0); asm.bornb.setdefault(_i2, asm.nb); asm.rad.setdefault(_i2, None)
                asm.born.setdefault(_i2, _resume_step); asm.act.setdefault(_i2, float(asm.size.get(_i2, 1)))
        _hb, _hbs = _RD.get("holdout") or {}, int(_RD.get("holdout_step", _resume_step))
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

    def _namehash(nm):                                     # deterministic: hash() is SALTED per process, so using it
        h = 0                                              #   would draw different probe windows every run and make
        for ch in nm.encode(): h = (h * 131 + ch) % 1000003 #   the whole comparison meaningless
        return h

    def holdout_bpb():
        """Per-DOMAIN bits/byte on the HELD-OUT tail, on windows fixed by domain NAME.

        THE MEASUREMENT THAT LETS AREAS BE ADDED LATER. Every existing metric is computed on the CURRENT stream, so
        the moment a new domain is introduced the question that matters -- did adding it damage what was already
        known? -- is unanswerable: both old and new material are in the new stream and both were just trained on.
        RETENTION compares a process's earliest windows to its latest WITHIN one stream, which cannot see across a
        run boundary at all.
        Keyed by NAME rather than by index on purpose: adding a domain shifts every index after it, so an
        index-keyed probe would silently compare `eng` against `py`. The window draw is seeded from the name too,
        so a domain is scored on exactly the same held-out text whatever position it now occupies."""
        out = {}
        model.eval()
        try:
            for _p in range(len(VALC)):
                nm = DN[_p] if _p < len(DN) else str(_p)
                _v = _VALT.get(_p)
                if _v is None:
                    _v = _units(TOK, USE_TOK, VALC[_p])
                    _VALT[_p] = _v
                if len(_v) < WIN + 2: continue
                _rs = random.Random(_namehash(nm))
                _st = [_rs.randint(0, len(_v) - WIN - 2) for _ in range(_i("HOLDOUT_N", 32))]
                with torch.no_grad():
                    _X = torch.tensor([_v[a:a + WIN] for a in _st], device=DEV)
                    _Y = torch.tensor([_v[a + 1:a + WIN + 1] for a in _st], device=DEV)
                    _lg = _eval_logits(model, fab, FABRIC, _X)
                    _pp = F.softmax(_lg, -1).gather(-1, _Y.unsqueeze(-1)).squeeze(-1)
                # PER WINDOW, not pooled, so the number carries an error bar. A pooled sum-over-all-windows gives
                # one figure with no way to tell a real change from sampling noise -- which is exactly how the
                # coherence metric went wrong, and there is no excuse for repeating it one section later.
                if USE_TOK:                                # same live-vocabulary denominator as the learning curve
                    _bl = _BL.get(TOK.vocab_size)
                    if _bl is None:
                        _bl = torch.tensor(TOK.bytes_per_id[:TOK.vocab_size], dtype=torch.float, device=DEV)
                        _BL.clear(); _BL[TOK.vocab_size] = _bl
                    _dw = _bl[_Y.clamp(max=TOK.vocab_size - 1)].sum(-1)
                else:
                    _dw = torch.full((_Y.size(0),), float(_Y.size(1)), device=DEV)
                _nw = -(torch.log(_pp.clamp_min(1e-9)).sum(-1)) / math.log(2) / _dw.clamp_min(1.0)
                _mu = float(_nw.mean())
                _se = float(_nw.std(unbiased=True) / (_nw.numel() ** 0.5)) if _nw.numel() > 1 else 0.0
                out[nm] = (_mu, _se)
        except Exception as _e:
            print(f"[holdout probe skipped: {type(_e).__name__}: {_e}]")
        finally:
            model.train()
        return out

    def report_holdout(prev, prev_step, title):
        """prev = the probe stored in the checkpoint we resumed from. Anything present then and now is a RETENTION
        number that spans the run boundary; anything only now is a domain this run is seeing for the first time."""
        now = holdout_bpb()
        if not now: return now
        print(f"\n=== {title} (held-out, per domain, bits/byte -- lower is better) ===")
        def _ms(v): return v if isinstance(v, (tuple, list)) else (float(v), 0.0)   # tolerate older checkpoints
        if not prev:
            for k in sorted(now):
                _m, _e = _ms(now[k]); print(f"  {k:<10} {_m:.3f} +/- {_e:.3f}   (no earlier probe to compare against)")
            return now
        _kept = [k for k in sorted(now) if k in prev]
        for k in sorted(now):
            _m, _e = _ms(now[k])
            if k in prev:
                _pm, _pe = _ms(prev[k]); _d = _m - _pm; _ed = (_e ** 2 + _pe ** 2) ** 0.5
                print(f"  {k:<10} was {_pm:.3f} @ step {prev_step}  ->  now {_m:.3f}   {_d:+.3f} +/- {_ed:.3f}  "
                      f"{'WORSE (forgetting)' if _d > 2 * _ed else ('better' if -_d > 2 * _ed else 'HELD (inside the noise)')}")
            else:
                print(f"  {k:<10} {_m:.3f} +/- {_e:.3f}   NEW this run -- no baseline, nothing to forget yet")
        if _kept:
            _m = sum(_ms(now[k])[0] - _ms(prev[k])[0] for k in _kept) / len(_kept)
            _em = (sum(_ms(now[k])[1] ** 2 + _ms(prev[k])[1] ** 2 for k in _kept) ** 0.5) / len(_kept)
            print(f"  mean change on the {len(_kept)} domain(s) that existed before: {_m:+.3f} +/- {_em:.3f} bits/byte"
                  + ("" if abs(_m) > 2 * _em else "  -- inside the noise, do not read this as forgetting"))
            print(f"  >> this is the ONLY number that spans the run boundary. Every other retention figure is")
            print(f"     computed on the current stream and cannot see what was known before this run started.")
        return now
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
    if _env("SAVE_CKPT", "").strip().lower() in ("0", "", "off", "no", "none", "false"):
        os.environ.pop("SAVE_CKPT", None)

    def _save_ckpt(src_stream, quiet=False, suffix=""):    # persist model+tokenizer+memory so `prompt.py` can load it
        ck = _env("SAVE_CKPT", "")
        if not ck: return False                            # RETURNS whether it saved: the caller used to assume it did
        ck = ck + suffix                                   # suffix=".best" writes the best-by-held-out snapshot
        os.makedirs(ck, exist_ok=True)
        if USE_TOK: TOK.save(_env("TOKENIZER_PATH", "data/dyntok.json"))
        act = mem.active
        torch.save({"model": model.state_dict(), "D": D, "V": V, "KW": KW, "KEY_SRC": KEY_SRC,
                    "model_type": MODEL_TYPE, "layers": _i("LAYERS", 4 if MODEL_TYPE=="transformer" else 1), "heads": _i("HEADS", 8), "maxlen": _i("MAXLEN", 512),
                    "use_tok": USE_TOK, "tok_path": (_env("TOKENIZER_PATH", "data/dyntok.json") if USE_TOK else None),
                    "mem_keys": mem.keys[act].cpu(), "mem_tok": mem.tok[act].cpu(), "mem_src": mem.src[act].cpu(),
                    "mem_ctx": (mem.ctx[act].cpu() if mem.ctx_w > 0 else None), "topk": mem.topk,
                    "mem_pos": mem.pos[act].cpu(),                     # -> source passages for grounded answers
                    "mem_use": mem.use[act].cpu(), "mem_selfcon": mem.selfcon[act].cpu(),   # for RESUME (retrieval fitness + wrongness)
                    "mem_own": mem.own[act].cpu(), "mem_last": mem.last[act].cpu(),         # per-expert partition + LRU clock
                    "mem_n_own": mem.n_own, "mem_quota": mem.quota, "mem_tick": mem.tick,
                    "sig_d": SIG_D, "win": WIN, "enc": enc.state_dict(),          # encoder -> gist for fabric routing
                    # HELD-OUT PROBE, keyed by domain NAME. This is what makes "add a new area later" measurable:
                    # the next run scores the SAME held-out windows and reports what changed on the domains that
                    # already existed. Cheap (HOLDOUT_N windows per domain) and the only figure that survives a
                    # run boundary.
                    "holdout": holdout_bpb(), "holdout_step": step,
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
                            # born and act were the two fields nothing saved. _absorb reads s.born[a] with NO
                            # default, so the first domain merge after ANY resume died on KeyError -- i.e. every
                            # resumed run crashed within DOM_MANAGE_EVERY steps, which is the whole recovery path
                            # for a multi-day run. act is the DECAYED use that drives culling; restoring it empty
                            # makes every domain look unused and invites a mass cull on the first manage().
                            "born": dict(asm.born), "act": dict(asm.act),
                            "rad": dict(asm.rad), "radp": asm._radp},
                    "experts": (experts.state_dict() if EXPERTS else None),
                    "fab": (fab.state_dict() if FABRIC else None),
                    "fab_cfg": ({"n": fab.n(), "rank": fab.r, "cap": fab.cap, "dk": _i("FAB_DK", 32), "alpha": _f("FAB_ALPHA", 0.5),
                                 "max_steps": _i("FAB_STEPS", 4), "hid_mult": _f("FAB_HID_MULT", 2),
                                 "min_steps": fab.min_steps, "norm_only": bool(_i("FAB_NORM_ONLY", 0)),
                                 "society": SOCIETY, "grounded": fab.grounded, "route_t": fab.route_t,
                                 "route_learn": fab.route_learn, "ens_k": ENS_K,
                                 "halt_on": fab.halt_on, "halt_max": fab.halt_max} if FABRIC else None)},
                   f"{ck}/ckpt.pt.tmp")
        if os.path.exists(f"{ck}/ckpt.pt"):                       # keep ONE previous generation: a corrupt or
            try: os.replace(f"{ck}/ckpt.pt", f"{ck}/ckpt.prev.pt")   # interrupted write is then always recoverable
            except OSError: pass
        os.replace(f"{ck}/ckpt.pt.tmp", f"{ck}/ckpt.pt")          # ATOMIC: a kill mid-save used to leave a truncated
        #   ckpt.pt and destroy the only copy, together with the tokenizer that decodes it.
        with open(f"{ck}/source.bin", "wb") as _srcf:             # the corpus text retrieval points INTO
            _srcf.write(bytes(byte_stream) if ONLINE else (bytes(src_stream) if not USE_TOK else TOK.decode(src_stream).encode("utf-8", "replace")))
        # PROBE SIDECAR. ckpt.pt carries the memory store (MEM_CAP x KW floats) and both optimizers' moments, so at
        # D=768/MEM_CAP=200000 it runs to gigabytes -- fine on the machine that wrote it, impractical to move off a
        # rented GPU box. probe_ckpt_geometry and probe_stability need FOUR things: the signature encoder, the domain
        # centroids, SIG_D and WIN. That is tens of MB. Written every save so the geometry and stability questions
        # can be asked anywhere, on any machine, long after the GPU is returned.
        torch.save({"enc": enc.state_dict(), "sig_d": SIG_D, "win": WIN, "step": step,
                    "cent": {int(k): v.cpu() for k, v in asm.cent.items()}, "size": dict(asm.size),
                    "sig_space": SIG_SPACE, "domains": _env("DOMAINS", "eng,py,num,c"), "enc_v": ENC_V,
                    "use_tok": USE_TOK, "tok_path": (_env("TOKENIZER_PATH", "data/dyntok.json") if USE_TOK else None)},
                   f"{ck}/probe.pt.tmp")
        os.replace(f"{ck}/probe.pt.tmp", f"{ck}/probe.pt")
        if not quiet:
            print(f"[saved checkpoint -> {ck}/ckpt.pt | {int(act.sum())} memory entries{', fabric ' + str(len(fab.bodies)) + 'n' if FABRIC else ''} | prompt it: python3 prompt.py CKPT={ck}]")
        return True                                        # saved, and the caller may say so


    import signal as _signal                               # CHECKPOINT-ON-DEMAND: `kill -USR1 <pid>` sets a flag and the
    _ckpt_req = {"on": False}                              #   loop saves at the next SAFE point (never torch.save inside a

    def _on_usr1(*_): _ckpt_req["on"] = True              #   handler -- reentrancy). Pause+dump without killing the run.
    try: _signal.signal(_signal.SIGUSR1, _on_usr1)
    except (ValueError, OSError): pass                     # not the main thread / unsupported platform -> silently skip
    if _env("SAVE_CKPT", ""):
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
    if _env("SAVE_CKPT", "") and not CKPT_EVERY:
        _warn.append("SAVE_CKPT set but CKPT_EVERY=0 -> the ONLY save is at the very end (plus SIGUSR1). "
                     "A crash loses the whole run. Set CKPT_EVERY.")
    if MEM_PER_EXPERT and mem.cap != _i("MEM_CAP", 200000):
        _want = _i("MEM_CAP", 200000)
        _warn.append(f"MEM_CAP={_want} was OVERRIDDEN: the per-expert partition derives the store size as "
                     f"n_own x quota = {mem.n_own} x {mem.quota} = {mem.cap} slots (memory.py: 'cap is DERIVED from "
                     f"the partition'), a {_want/max(1,mem.cap):.1f}x reduction. Every memory result scales with "
                     f"this. To keep {_want} slots at {mem.n_own} owners set MEM_QUOTA={_want//max(1,mem.n_own)}; "
                     f"to keep a small per-expert quota, accept the smaller store deliberately; or MEM_PER_EXPERT=0.")
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
    # SIGNATURE WIDTH must track the LOOP STRIDE, which grows as the tokenizer compresses better.
    # SIG_WIN=0 meant "use WIN", i.e. 256 BYTES -- while the loop advances WIN TOKENS. Early in a run one token is
    # about one byte and that matches; by the time the vocabulary has grown to ~2.4 bytes/token the loop strides
    # 614 bytes and the signature encoder is characterising the first 256 of them. The domain encoder was reading
    # 42% of the stream and nothing downstream could tell, because every window still produced A signature -- just
    # one computed from the opening fragment of the material it claims to describe.
    # FIXED FOR THE LIFETIME OF THE RUN. I first made this recompute live as the tokenizer grew, which crashed both
    # pilot arms at the first rekey: asm.wins still held windows captured at the OLD width, rekey concatenates them
    # into one batch, and a ragged batch is a ValueError. The crash was the lesser problem. Domain centroids ARE
    # means of encoded windows, so changing the width mid-run makes signatures taken before and after the change
    # incomparable -- every centroid, radius and boundary test would silently straddle two different measurements.
    # A width that moves is wrong in principle, not just in implementation.
    # Fixed means it cannot track a growing stride, so SIG_PROJ says what the coverage will be once the vocabulary
    # has grown, and SIG_WIN= sets it outright if you want full coverage at the END rather than at the start.
    def _sigwidth():
        if SIG_WIN > 0: return SIG_WIN                      # explicit setting always wins
        if not (ONLINE and SIG_SPACE == "bytes"): return WIN
        _b = (sum(TOK.bytes_per_id[:TOK.vocab_size]) / max(1, TOK.vocab_size)) if (USE_TOK and TOK is not None) else 1.0
        return max(WIN, int(WIN * max(1.0, _b)))            # never narrower than the stride the loop takes
    _sigw = _sigwidth()
    if ONLINE and SIG_SPACE == "bytes":
        _stride_b = WIN * max(1.0, _bpt)
        _cov = min(1.0, _sigw / _stride_b)
        # PROJECTED, not just current. The width is fixed for the run but the STRIDE grows as the vocabulary
        # compresses better, so a window that covers 100% at step 0 covers less every hour. Saying only the
        # starting number is how "covers 100%" gets believed for a run that ends at 60%.
        _bpt_end = _f("SIG_PROJ_BPT", 2.4)                  # rough end-of-run bytes/token at VMAX~2048 byte-BPE
        _stride_end = WIN * max(1.0, _bpt_end); _cov_end = min(1.0, _sigw / _stride_end)
        print(f"[signature] space=bytes | window {_sigw} B (FIXED for the run) | loop stride now {_stride_b:.0f} B "
              f"({WIN} tok x {_bpt:.2f}) -> covers {_cov*100:.0f}% now"
              + (f", ~{_cov_end*100:.0f}% once the vocabulary has grown (~{_bpt_end:.1f} B/tok)"
                 if _cov_end < _cov - 0.01 else "")
              + ("" if min(_cov, _cov_end) >= 0.99 else
                 f"; SIG_WIN={int(_stride_end)} covers it throughout (wider than one loop window early on, which "
                 f"means consecutive signatures overlap -- a real trade, not a free fix)"))
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

    s_cfg_known = set()
    def _config_audit():
        """RUN AT THE END, when every _env() call in the file has actually happened. Two questions the log could
        not answer before: was a knob I set never verified against a live value, and was a knob I set never READ
        AT ALL. The second is the dangerous one on an unattended grid -- a typo trains for twenty minutes on the
        default while the command line implies otherwise, and nothing says so.
        It has to be here rather than in the banner: several knobs (FAB_CULL_FRAC, FAB_CENT_TOPK) are read only
        inside the report, so at banner time they look exactly like typos."""
        _plumb = {"DEVICE", "DATA_MODE", "DATA_DIR", "DOMAINS", "STREAM_LEN", "WIN", "BATCH_W", "D_MODEL",
                  "MODEL", "LAYERS", "HEADS", "SAVE_CKPT", "RESUME", "CKPT_EVERY", "RATE_EVERY", "PROFILE",
                  "SEED", "DISK_STREAM", "CORPUS_CAP", "SIG_WIN", "SIG_MODE", "SIG_D", "VMAX", "PROBE_WAIT",
                  "GEN_LEN", "GEN_TEMP", "GEN_N", "GEN_PROCS", "COH_N", "COH_LEN", "MANAGE_EVERY", "DOM_MANAGE_EVERY", "ENC_WARMUP",
                  "ENC_WARMUP_MIN", "SEG_MIN", "SEG_MAX", "GROW_EVERY", "GROW_BURST", "VERIFY", "OUT", "EPOCHS"}
        _unreg = sorted(set(_ENV_ASKED) - s_cfg_known - _plumb)
        _pfx = ("FAB_", "ROUTE_", "CHAIN_", "SOCIETY", "DIV_W", "IND_", "ENS_", "MEM_", "DOM_", "ENC_",
                "WORLD_", "TOK", "EXPERT", "EXP_", "BAL_", "PONDER", "CENT_", "SHIFT_", "WRITE_", "SELF_ORG")
        _typo = sorted(k for k in os.environ if k.startswith(_pfx) and k not in _ENV_READ)
        if _typo:
            print(f"\n[config-audit] !! NOTHING READ THESE: {', '.join(_typo)} -- set in the environment but no "
                  f"code path ever asked for them. Almost certainly a typo; this run used the DEFAULTS for "
                  f"whatever was meant, and every number above describes that run, not the intended one.")
        if _unreg:
            print(f"[config-audit] set and read, but not verified against a live value: {', '.join(_unreg)}")
        if not _typo and not _unreg:
            print(f"\n[config-audit] all {len(_ENV_ASKED)} environment settings were read and accounted for.")
        # A KNOB CAN BE READ, REGISTERED, AND STILL UNREACHABLE. This is the check the value-level audit cannot
        # do: did the loss term the knob controls ever actually contribute?
        for _tn, _tv in (("DIV_W", DIV_W), ("IND_W", IND_W if SOCIETY else 0.0),
                         ("CHAIN_SUP", fab.sup_w if FABRIC else 0.0)):
            if _tv > 0 and not _termfired.get(_tn):
                print(f"[config-audit] !! {_tn}={_tv} was ON and its loss term NEVER FIRED -- the code path that "
                      f"applies it was not reached on this configuration. This run is identical to {_tn}=0.")
        if _termfired:
            print(f"[config-audit] auxiliary loss terms that fired: "
                  + ", ".join(f"{k} x{v}" for k, v in sorted(_termfired.items())))
    def _banner():
        """WHAT IS ACTUALLY ON. Printed because this project's largest single error was not a bug: it was SIX
        subsystems silently defaulting OFF, and nothing in the output said so.

        EVERY VALUE HERE IS READ FROM THE LIVE OBJECT OR THE COMPUTED VARIABLE -- never re-read from os.environ.
        An env var is what was ASKED FOR; these are what RAN, and the two differ whenever an effective value is an
        AND with something else (MEM_PER_EXPERT and FABRIC; WORLD_GROW and WORLD_MODEL; FAB_MIN_STEPS defaulting
        by path). Each of those printed the env var and each of them lied in a real log."""
        def _on(b): return "ON " if b else "off"
        _F = fab if FABRIC else None
        print(f"[config] SUBSYSTEMS  fabric {_on(FABRIC)}"
              + (f" ({_F.cap} slots, rank {_F.r}, {_F.n()} live now)" if _F else "")
              + f" | world {_on(WORLD_MODEL)} (grow {_on(WORLD_GROW)}, "
                f"feedback {_on(world_proj is not None)})"
              f" | domains {_on(SELF_ORG)} (cap {MAX_DOMAINS}) | manage {_on(MANAGE_ON)}"
              f" | tokenizer {_on(USE_TOK)} (online {_on(TOK_ONLINE)})"
              f" | per-expert memory {_on(MEM_PER_EXPERT)}"
              + (f" ({mem.n_own} owners x {mem.quota})" if MEM_PER_EXPERT else "")
              + f" | phased {_on(PHASED)}")
        # === EFFECTIVE CONFIG, DERIVED ==========================================================================
        # One declarative table: env name -> the LIVE value that actually ran. Everything below is computed from
        # it, so a knob cannot be printed with a value the code is not using, and a knob whose effective value is
        # an AND with something else reports the AND rather than the request. Adding a flag means adding a row.
        _F0 = fab if FABRIC else None
        _G0 = fabgrow if (FABRIC and fabgrow is not None) else None
        _EFF = [
            ("FABRIC",         FABRIC),                  ("SOCIETY",        SOCIETY),
            ("SELF_ORG",       SELF_ORG),                ("MANAGE",         MANAGE_ON),
            ("TOKENIZER",      USE_TOK),                 ("TOK_ONLINE",     USE_TOK and TOK_ONLINE),
            ("TOK_MINT_UNTIL", TOK_MINT_UNTIL),         ("WARMSTART",      bool(_i("WARMSTART", 1))),
            ("WARMSTART_OPT",  bool(_i("WARMSTART_OPT", 0))),
            ("WARMSTART_MODE", _env("WARMSTART_MODE", "mean")),
            ("TOK_COMPOSE",    TOK_COMPOSE),            ("TOK_ANCHOR",     TOK_ANCHOR),
            ("TOK_ANCHOR_TAU", TOK_ANCHOR_TAU),
            ("TOK_MINT_NOVEL", _f("TOK_MINT_NOVEL", 0.0)),
            ("PHASED",         PHASED),                  ("EPOCHS",         EPOCHS),
            ("WORLD_MODEL",    WORLD_MODEL),             ("WORLD_GROW",     WORLD_GROW),
            ("WORLD_FEEDBACK", world_proj is not None),  ("MEM_PER_EXPERT", MEM_PER_EXPERT),
            ("MEM_CAP",        mem.cap, "rounded up to owners x quota"),
            ("MEM_OWNERS",     mem.n_own),
            ("MEM_QUOTA",      mem.quota if MEM_PER_EXPERT else mem.cap,
                               "no per-expert partition, so one global quota = the whole store"),
            ("MAX_DOMAINS",    MAX_DOMAINS),
            ("EXPERTS",        bool(EXPERTS and not FABRIC)),
            ("DIV_W",          DIV_W),                   ("IND_W",          IND_W if SOCIETY else 0.0),
            ("DROPOUT",        DROPOUT),                 ("WEIGHT_DECAY",   WD),
            ("RECON_W",        RECON_W),                 ("BAL_WARM",       BAL_WARM),
            ("LR",             LR),                      ("LR_SCHED",       LR_SCHED),
            ("LR_WARMUP",      LR_WARMUP),               ("LR_MIN_FRAC",    LR_MIN_FRAC),
            ("LR_EPOCHS",      _i("LR_EPOCHS", 0) or EPOCHS),
            ("PONDER",         PONDER),                  ("ENS_K",          ENS_K),
        ]
        if _F0 is not None: _EFF += [
            ("FAB_NMAX",       _F0.cap),                 ("FAB_RANK",       _F0.r),
            ("FAB_N0",         _i("FAB_N0", 3)),
            ("FAB_STEPS",      _F0.max_steps),           ("FAB_MIN_STEPS",  _F0.min_steps),
            ("FAB_CHAIN_K",    _F0.chain_k),             ("FAB_EXPLORE",    _F0.explore),
            ("FAB_HALT",       _F0.halt_on),             ("FAB_HALT_MAX",   _F0.halt_max),
            ("FAB_EMB_EVERY",  _F0.emb_every),           ("FAB_DERIVE_IDS", _F0.derive_ids),
            ("ROUTE_T",        _F0.route_t),             ("ROUTE_GROUNDED", _F0.grounded),
            ("ROUTE_LEARN",    _F0.route_learn),         ("ROUTE_REGION_W", _F0.region_w),
            ("FAB_KEY_NORM",   FAB_KEY_NORM),            ("CHAIN_VOTE",     _F0.vote),
            ("CHAIN_ROUTE",    "soc" if _F0.loop_soc else "transition"),
            ("CHAIN_BAN",      _F0.chain_ban),           ("CHAIN_CURRIC",   _F0.curric),
            ("CHAIN_SUP",      _F0.sup_w),               ("CHAIN_STATE_Q",  _F0.state_q),
            ("EXP_DOM_FRAC",   _F0.breadth),             ("EXP_DOM_MIN",    _F0.breadth_min),
        ]
        if _G0 is not None: _EFF += [("FAB_RAMP_LATCH", _G0.latch), ("FAB_RAMP_TO", _G0.ramp_to),
                                     ("FAB_GROW", _G0.grow_on)]
        _EFF = [(r[0], r[1], (r[2] if len(r) > 2 else None)) for r in _EFF]
        _known = {r[0] for r in _EFF}
        def _norm(v):
            if isinstance(v, bool): return "1" if v else "0"
            if isinstance(v, float): return f"{v:g}"
            return str(v)
        # ASKED FOR BUT NOT RUN, detected rather than remembered. Anything the environment set explicitly whose
        # live value disagrees is printed. This is the check that would have caught all three past banner lies.
        _bad, _adj = [], []
        for _n, _v, _note in _EFF:
            _a = _ENV_ASKED.get(_n)
            if _a is None: continue
            try:
                _same = (abs(float(_a) - float(_v)) < 1e-9) if not isinstance(_v, str) else (_a == _v)
            except (TypeError, ValueError):
                _same = (_norm(_a) == _norm(_v))
            if _same: continue
            (_adj if _note else _bad).append((_n, _a, _norm(_v), _note))
        # `!!` is reserved for a divergence NOBODY REGISTERED -- i.e. a surprise. A known, benign adjustment
        # (a rounding, a partition collapsing to a global store) reports plainly, or the loud marker stops
        # meaning anything and gets skimmed past, which is how the last three lies survived.
        for _n, _a, _v, _ in _bad:
            print(f"[config] !! OVERRIDDEN: {_n}={_a} was asked for, {_n}={_v} is what RAN.")
        for _n, _a, _v, _note in _adj:
            print(f"[config] adjusted: {_n} {_a} -> {_v} ({_note})")
        # (the two integrity checks that need EVERY read to have happened live at the end of the run, in
        #  _config_audit -- at banner time the report's own reads have not occurred yet and every one of them
        #  looks like a typo. Verified: FAB_CULL_FRAC, read only inside the report, was flagged from here.)
        s_cfg_known.update(_known)
        print("[config] EFFECTIVE  " + "  ".join(f"{_n}={_norm(_v)}" for _n, _v, _ in _EFF))
        # === COUPLINGS: knobs whose EFFECTIVE value was decided by ANOTHER knob ================================
        # The registry gives one declared place for every knob, but a declaration cannot show that setting one
        # of them silently moves another. Three do:
        #   CHAIN_VOTE forces FAB_MIN_STEPS to 0, inside Fabric.__init__, where nobody reading the config finds it.
        #   TOK_MINT_UNTIL stops MINTING and leaves RETOK_EVERY firing -- two knobs, one idea, and setting only
        #     the obvious one leaves half the behaviour in place.
        #   SOCIETY + CHAIN_ROUTE together choose one of three forward paths; neither alone tells you which.
        # Nothing here CHANGES a value. It prints what the run is actually doing, so a coupling cannot be
        # discovered again by losing a day to it.
        _cpl = []
        if LR_SCHED != "none":
            _lre = _i("LR_EPOCHS", 0)
            _cpl.append(
                f"EPOCHS={EPOCHS} sets run length AND the cosine horizon, so it changes the LR at EVERY step, "
                f"not only how many steps there are -- two runs differing only in EPOCHS are two different "
                f"schedules, and on the vmax4k pair they were 11x apart by step 44000. "
                + (f"LR_EPOCHS is unset, so the horizon follows EPOCHS={EPOCHS} and this run is NOT comparable "
                   f"at fixed LR to a run at another EPOCHS."
                   if not _lre else
                   f"LR_EPOCHS={_lre}: the cosine is shaped over {_lre} epochs and then holds at the "
                   f"LR_MIN_FRAC={LR_MIN_FRAC:g} floor for the remaining {max(0, EPOCHS - _lre)}, so the LR at "
                   f"each step matches an EPOCHS={_lre} run and only the length differs."))
        if FABRIC and not SOCIETY and bool(_i("CHAIN_VOTE", 1)):
            _cpl.append(f"CHAIN_VOTE=1 -> FAB_MIN_STEPS={fab.min_steps} (forced; the declared default is "
                        f"{0 if SOCIETY else 2}), so HALT may absorb on the first hop. What it actually did is "
                        f"in this run's HALT MASS and mean-routed-depth lines.")
        if USE_TOK and TOK_MINT_UNTIL and _i("RETOK_EVERY", 3000) > 0:
            _cpl.append(f"TOK_MINT_UNTIL={TOK_MINT_UNTIL} stops MINTING at that step, but RETOK_EVERY="
                        f"{_i('RETOK_EVERY', 3000)} keeps RE-SEGMENTING for the whole run. After the freeze each "
                        f"retok rebuilds an identical stream while still clearing the lookahead queue and "
                        f"blacking out fabric growth. Set RETOK_EVERY=0 to stop that too -- the two knobs are "
                        f"independent and neither implies the other.")
        if USE_TOK and TOK_MINT_UNTIL and _i("RETOK_EVERY", 3000) == 0:
            _cpl.append("TOK_MINT_UNTIL is set AND RETOK_EVERY=0: nothing about the segmentation moves after "
                        "the freeze, and fabric growth is never blacked out by a retok.")
        # VMAX IS TWO LEVERS UNDER ONE NAME: the model's softmax width, fixed here and now, and the tokenizer's
        # ceiling, which is only reached if minting has the BUDGET to reach it. The budget is EPOCHS, through
        # GROW_EVERY and GROW_BURST -- and raising VMAX does not raise it. Every row minting cannot reach is a
        # row no window ever carries as a target: it holds its initialisation and sits in the loss denominator
        # for the whole run, which is the same shape as freezing the vocabulary far below the width. That is
        # worth knowing BEFORE the GPU time is spent, not from the [vocab] line afterwards.
        # The step count is deliberately the optimistic one: it is measured at the CURRENT vocabulary, and the
        # stream shortens as tokens are minted, so the real run has FEWER steps than this. A shortfall reported
        # here is therefore a floor on the real shortfall.
        if ONLINE and not TOK_MINT_UNTIL:
            _gb        = _i("GROW_BURST", 6)
            _ep_steps  = max(1, len(stream) // WIN)              # steps in ONE epoch at the current vocabulary
            _ep_mints  = max(1, (_ep_steps // max(1, GROW_EVERY)) * _gb)     # mints ONE epoch can pay for
            _need      = VMAX - TOK.vocab_size                   # mints to fill the width from where we are
            _reach     = min(VMAX, TOK.vocab_size + EPOCHS * _ep_mints)
            _ep_needed = -(-_need // _ep_mints)                  # ceil: epochs that would cover _need
            if _reach < VMAX:
                _cpl.append(f"VMAX={VMAX} sizes the softmax NOW, but minting cannot fill it: GROW_EVERY="
                            f"{GROW_EVERY} x GROW_BURST={_gb} pays for ~{_ep_mints} mints per epoch, so "
                            f"EPOCHS={EPOCHS} reaches ~{_reach} at best from a {TOK.vocab_size}-token seed -- "
                            f"leaving >={VMAX - _reach} rows ({(VMAX - _reach) / max(1, VMAX) * 100:.0f}% of the "
                            f"width) that are never a target. EPOCHS is the lever that buys mints without "
                            f"changing how minting behaves: ~{_ep_needed} epochs covers the {_need} needed here. "
                            f"GROW_BURST would also cover it, but it changes how large a segmentation shift each "
                            f"grow event is, which is a different experiment.")
        for _c in _cpl: print(f"[config] COUPLING    {_c}")
        # DERIVED KNOBS. A knob left unset whose default is computed FOLLOWS another knob, so changing the
        # other one moves it too. That is fine and often right, but it was only visible by reading the read
        # site, which is how FAB_NMAX quietly setting MAX_DOMAINS and ENC_EVERY quietly setting SIG_LOOK (two
        # hops, through ENC_EVERY_IDLE) stayed unstated. _DERIVED declares every one of them and levers.py
        # fails if that declaration and the source disagree, so this list cannot go stale.
        _drv = [f"{_k}<-{'+'.join(_DERIVED[_k])}" for _k in sorted(_DERIVED) if _k not in _ENV_ASKED]
        _set = [_k for _k in sorted(_DERIVED) if _k in _ENV_ASKED]
        print(f"[config] DERIVED     following another knob: {'  '.join(_drv) if _drv else '(none)'}"
              + (f" | set explicitly, so following nothing: {', '.join(_set)}" if _set else ""))
        print(f"[config] EXPERT POPULATION  the FABRIC is the expert population ({'ON' if FABRIC else 'OFF'}). "
              f"The legacy ExpertBank (EXPERTS={int(bool(EXPERTS))}) is {'ON' if EXPERTS else 'off'} and is mutually "
              f"exclusive with it -- with the fabric on, that flag being 0 is CORRECT, not a missing subsystem.")
        if _F:
            print(f"[config] SELECTION   replicate {_on(FAB_REPLICATE)} (parent: sampled by fitness among the "
                  f"{_F.parent_k} nearest region-owners; mutation {_F.mut:.0%} of parent std, "
                  f"{_F.mut_big_p:.0%} of births x{_F.mut_big:.0f}) | competence protection {_on(COMP_PROTECT)}"
                  f" | cull-empty domains {_on(DOM_CULL_EMPTY)} | expert breadth cap {_F.breadth:.0%} of domains "
                  f"(floor {_F.breadth_min}) | ramp {fabgrow.rate:.0%}/event to {fabgrow.ramp_to:.0%} of cap"
                  f"{' [latch off: the ramp will re-arm forever]' if not fabgrow.latch else ''}")
            print(f"[config] PATH        "
                  + ("SOCIETY (SOCIETY=1) -- independent experts, ONE round, blended at the prediction level; "
                     "nobody sees anybody and nothing composes." if SOCIETY else
                     (f"CHAINED SOCIETY (default) -- the society run {_F.max_steps} times over. Each round "
                      f"re-routes FROM SCRATCH with the society's own router, with the CURRENT STATE in the "
                      f"query; the round's experts vote on the OUTPUT; and the state carries into the next round, "
                      f"so composition survives. No transition matrix, no SRC. HALT is a per-round STOP "
                      f"PROBABILITY: alive starts at 1, each round takes alive x p_stop and passes on "
                      f"alive x (1-p_stop), so 'when am I done' is asked against where the computation actually "
                      f"is. CHAIN_ROUTE=transition for the old learned-successor walk."
                      if _F.loop_soc else
                      f"CHAINING, TRANSITION-ROUTED (CHAIN_ROUTE=transition) -- mass flows expert -> expert "
                      f"through the learned transition matrix for up to {_F.max_steps} hops ({_F.chain_k} "
                      f"computed per hop), HALT blocked for the first {_F.min_steps}. This is the path whose "
                      f"H(hop1|hop0) measured 0.005-0.058 bits: one decision, then a fixed successor."
                      + (" Experts vote on the PREDICTION each hop (CHAIN_VOTE=1)." if _F.vote else
                         " Experts are mixed in the HIDDEN STATE and decoded once (CHAIN_VOTE=0); HALT measured "
                         "0.0000 in all 18 grid arms because stopping bought it nothing."))))
            print(f"[config] ROUTING     "
                  + ("PREDICTED WEIGHTS ONLY (ROUTE_REGION_W=0) -- the signature-region term is off; routing is "
                     "q_route's point in identity space against every expert's embedded FULL WEIGHTS"
                     if (_F.grounded and _F.region_w == 0) else
                     f"region x{_F.region_w:g} + weight-prediction" if _F.grounded else
                     "learned q_entry keys only (ROUTE_GROUNDED=0 -- NOT the weight-prediction path)")
                  + f" | HALT {_on(_F.halt_on)} on BOTH paths (cap {_F.halt_max:.2f})"
                  f" | exploration {_F.explore:.0%} of windows swap a slot for a low-use expert"
                  f" | identities {'from FULL WEIGHTS' if _F.derive_ids else 'free parameters (FAB_DERIVE_IDS=0)'}"
                  f", refreshed every {_F.emb_every} step(s) | route_t {_F.route_t}")
            if _F.grounded and _F.region_w == 0 and not FAB_KEY_NORM:
                print("[config] !! ROUTE_REGION_W=0 with FAB_KEY_NORM=0: the weight-prediction term is a RAW dot "
                      "whose spread across experts measured 0.075, against a region term at 3.7. With the region "
                      "term removed the logits are nearly UNIFORM and routing is close to random. Set "
                      "FAB_KEY_NORM=1 so that term is a cosine over route_t and actually has dynamic range.")
            if not SOCIETY:
                print(f"[config] not on CHAINING: IND_W={IND_W} (each expert must solve the task ALONE) needs "
                      f"SEPARABLE per-expert LOGITS, which a composed walk does not have. Marginal contribution IS "
                      f"measured here, by re-walking without each candidate. DIV_W={DIV_W} IS applied on this path "
                      f"({'ON' if DIV_W > 0 else 'off at 0'}), from the per-hop expert OUTPUTS.")
        print(f"[config] OFF ON PURPOSE  DIV_W={DIV_W} (expert distinctness reward) | "
              f"ENC_CREG={ENC_CREG} (encoder decorrelation; ENC_VREG={ENC_VREG} IS on) | "
              f"DROPOUT={DROPOUT} | RECON_W={RECON_W} | WEIGHT_DECAY={WD}")
        if EXPERTS and FABRIC:
            print("[config] !! EXPERTS and FABRIC are mutually exclusive (FABRIC wins the elif chain) -- experts are a NO-OP")
        if NP < 2 and PHASED:
            print("[config] note: PHASED with ONE corpus degenerates to a stationary stream. The non-stationarity that "
                  "matters comes from ADDING an area later (longrun.sh add/pilot-add), not from a splice.")
        print()
    _banner()
    _total_steps = EPOCHS * (len(stream) // WIN)
    _bpw = WIN * (len(byte_stream) / max(1, len(stream))) if ONLINE else WIN     # BYTES of corpus consumed per step
    # === THE RUN IS SHORTER THAN THIS NUMBER WHENEVER THE VOCABULARY GROWS ====================================
    # _total_steps is EPOCHS x (tokens // WIN) measured ONCE, at the seed vocabulary. Under TOK_ONLINE the stream
    # is re-tokenized as tokens are minted, and minted tokens are LONGER, so the same bytes become fewer tokens
    # and every later epoch is shorter than the first. pilot_gru_8: _total_steps said 81840, the run ended at
    # ~48800 -- a 40% overestimate, and it grows with how much the vocabulary grows.
    # Everything downstream of it was therefore wrong: the ETA, the "SAMPLED FROM step ~N" label, and (the one
    # that matters) the cosine LR schedule, which was stretched over a horizon the run never reached and so never
    # annealed. _proj_steps() re-projects from where the run actually is: the steps already spent, plus the
    # epochs still to come at the CURRENT token length.
    # MEASURED, on four runs at one seed with everything else identical:
    #   E8  minting   projected  63,024   ran  48,130   over 31%   cosine reached p=0.760, LR floor never touched
    #   E12 minting   projected  94,536   ran  70,368   over 34%   p=0.742
    #   E18 minting   projected 141,804   ran 103,805   over 37%   p=0.730, ended at 21% of peak LR
    #   FROZEN vocab  projected 118,776   ran 118,743   over  0%   p=1.000, ended at 5% of peak -- as designed
    # The frozen-vocabulary run is the only one that ever annealed, and only because a vocabulary that does not
    # grow makes the projection exact. That made "frozen tokenizer" and "schedule that anneals" the same
    # experiment, and neither could be credited. It also means EPOCHS was never just run length: at step 48,130
    # the E18 schedule was at 1.52e-3 and the E8 schedule at 3.58e-4, a 4.3x difference on the same step.
    # === EPOCHS WAS TWO LEVERS: HOW LONG THE RUN IS, AND HOW THE LEARNING RATE FALLS =========================
    # The cosine is shaped over the projected END of the run, and EPOCHS sets that end, so changing EPOCHS
    # changes the LR at EVERY step -- not just how many steps there are. Two runs that differ only in EPOCHS
    # are not the same run measured at two lengths; they are two different schedules. Measured on the vmax4k
    # pair (identical config, identical vocabulary trajectory, both reaching 4096 near step 40k):
    #     step   E8 lr      E18 lr     ratio
    #     20000  1.263e-03  1.807e-03    1.4x
    #     40000  1.683e-04  1.275e-03    7.6x
    #     44000  1.046e-04  1.148e-03   11.0x     <- E8's best held-out (2.059) is at this step
    # By the end of E8 the two schedules are an order of magnitude apart. E8 is consolidating at the floor
    # where E18 is still near peak, so "8 epochs beat 18 epochs" and "a low LR beat a high one" are the same
    # observation, and neither run can be credited.
    #
    # LR_EPOCHS separates them: it is the horizon the cosine is SHAPED over, in epochs, defaulting to EPOCHS
    # so nothing changes unless it is set. EPOCHS=18 LR_EPOCHS=8 reproduces the 8-epoch run's LR at every step
    # for the first 8 epochs and then holds at the LR_MIN_FRAC floor (_lr_at clamps its progress at 1.0), which
    # is what a continual-learning system wants anyway: anneal, then keep a small non-zero rate for whatever
    # arrives later. Any remaining difference is then attributable to run length alone.
    LR_EPOCHS = _i("LR_EPOCHS", 0) or EPOCHS               # 0 = follow EPOCHS
    _ep_start = 0                                          # step at which the current epoch began
    # TWO CONSUMERS, TWO PROJECTIONS. One function served both the ETA and the LR horizon, so they could not
    # be given different horizons without one silently taking the other's. They also need SEPARATE monotone
    # clamps: a shared running minimum would let the shorter horizon drag the longer one down with it.
    def _project(step, horizon_epochs, state):
        _per = max(1, len(stream) // WIN)                  # steps per epoch AT THE CURRENT VOCABULARY
        _p = max(step + 1, _ep_start + (horizon_epochs - _epoch) * _per)
        # The projection only ever shrinks in truth (minting makes tokens longer, so later epochs are shorter),
        # but len(stream) jitters with each epoch's resample. Clamping to the running minimum keeps the cosine's
        # progress monotone, so the LR falls and never steps back UP mid-run -- a schedule that reverses is worse
        # than one that is merely wrong.
        state[0] = min(state[0], _p)
        return max(step + 1, state[0])
    _proj = [10 ** 9]                                      # monotone NON-INCREASING: see above
    _proj_lr = [10 ** 9]
    def _proj_steps(step):                                 # WORK REMAINING -- the ETA. Always the real end.
        return _project(step, EPOCHS, _proj)
    def _lr_total(step):                                   # SCHEDULE HORIZON -- what the cosine is shaped over.
        return _project(step, LR_EPOCHS, _proj_lr)
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
                        _v = _units(TOK, USE_TOK, VALC[_p])
                        _VALT[_p] = _v
                    if len(_v) < WIN + 2: continue
                    _rs = random.Random(1234 + _p)          # SAME windows every time -> the curve is comparable
                    _st = [_rs.randint(0, len(_v) - WIN - 2) for _ in range(16)]
                    with torch.no_grad():
                        _X = torch.tensor([_v[a:a + WIN] for a in _st], device=DEV)
                        _Y = torch.tensor([_v[a + 1:a + WIN + 1] for a in _st], device=DEV)
                        _lg = _eval_logits(model, fab, FABRIC, _X)
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
        # === KEEP THE BEST MODEL =========================================================================
        # WHY THIS EXISTS: ckpt.pt is written on a cadence and overwritten, so the saved artifact is the LAST
        # state, not the best one. When this was added, the last state was 1.1-1.3 bits/byte worse than the model
        # around step 6000 in every arm of every seed, so every text sample the project had judged came from a
        # degraded model.
        # THAT IS NO LONGER TRUE, and the tracking is what shows it. Once the LR schedule read a horizon the run
        # actually reaches and eval passes stopped moving the routing centroids, the early-peak-then-rise pattern
        # disappeared: in the six-arm pilot, FIVE of six arms ended at `+0.000 since its own minimum`, i.e. the
        # final model IS the best one. The exception was DROPOUT+WEIGHT_DECAY together, which still diverges
        # (+1.216). Keep the tracking -- it is how we would notice the pattern coming back -- but do not read the
        # old claim as current.
        if BEST_TRACK and _CURVE:
            _cs = [b for st, _p, b, _a in _CURVE if st == step]
            if _cs:
                _cm = sum(_cs) / len(_cs)
                if _best_bpb[0] is None or _cm < _best_bpb[0] - 1e-6:
                    _best_bpb[0] = _cm; _best_bpb[1] = step
                    try:
                        _best_bpb[2] = bool(_save_ckpt(stream, quiet=True, suffix=".best"))
                    except Exception as _e:
                        print(f"  [best-ckpt save failed: {type(_e).__name__}: {_e}]")
        if RATE_EVERY and step % RATE_EVERY == 0 and step > _s_mark:
            _now = _time.time(); _rate = (step - _s_mark) / max(1e-9, _now - _t_mark)      # steps/sec over the last window
            # bytes-per-step moves with the vocabulary too, so kB/s and GB/day were quoted at the SEED vocabulary
            # for the whole run. Both are two len() calls; recompute them here rather than report a stale number.
            _bpw = WIN * (len(byte_stream) / max(1, len(stream))) if ONLINE else WIN
            _left = max(0, _proj_steps(step) - (step - _resume_step))
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
            i = 0; _ep_start = step
            # LR ON THE EPOCH LINE. The schedule was not observable anywhere in a log, which is how a lever that
            # moves the LR 11x between two runs stayed invisible across every comparison we made. Printed as a
            # fraction of peak so it reads without arithmetic: 100% = untouched, 5% = at the LR_MIN_FRAC floor.
            _lrn = _lr_at(step, max(1, _lr_total(step)))
            print(f"  [epoch {_epoch + 1}/{EPOCHS}{' (fresh sample)' if DISK_STREAM else ''} @ step {step} | "
                  f"vocab {TOK.vocab_size if USE_TOK else 256} | mem {mem.n} | domains {len(asm.cent)} | "
                  f"lr {_lrn:.2e} ({_lrn / max(1e-12, LR) * 100:.0f}% of peak)]")
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
        if FABRIC and MANAGE_ON and step % MANAGE_EVERY == 0 and step > 0:
            _fc, _fs = fab.manage(step, grace=_i("FAB_GRACE", 3000), cull_frac=_f("FAB_CULL_FRAC", 0.08),
                                  pressure=_f("FAB_PRESSURE", 0.75), protect=COMP_PROTECT,
                                  comp_glob=asm.comp_glob)
            fab.removed += _fc; fab.spared += _fs
            if _fc or _fs:
                print(f"  [experts @ {step}] culled {_fc} spared {_fs} -> {fab.n()} live "
                      f"(cull under capacity pressure, bottom {_f('FAB_CULL_FRAC', 0.08):.0%} by utilization; "
                      f"spared = load-bearing or better than the population on its own material)")
        if EXPERTS and MANAGE_ON and step % MANAGE_EVERY == 0 and step > 0:
            router.comp_of = ((lambda i: (fab.contrib[i], "contrib") if i in fab.contrib
                               else (fab.comp.get(i), asm.comp_glob)) if FABRIC else (lambda i: (None, None)))
            router.manage(step)   # experts: create/replicate/cull (their own selective force)
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
            if not _mint_frozen[0]:
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
        _w = _oid = None; _hd = {}                              # defined on EVERY path: competence attribution reads them
        _sl = router.route(sig, step) if EXPERTS else -1        # route by SIGNATURE to the expert population (coarser than domains)
        if EXPERTS and _sl >= 0: route_at[bpos:bpos + WIN] = _sl   # remember WHICH expert trained on this span
        h = model.encode(x)                                      # includes the world-model feedback when enabled (wrapped above)
        _wz = world_enc(model.emb(x)) if WORLD_MODEL else None   # world latent per position (also used by the world loss)
        # CADENCE ON THE BACKWARD COUNTER, not on `step`. `step` counts WINDOWS and this block runs only on the
        # 1-in-BATCH_W flush steps, so `step % MANAGE_EVERY == 0` samples the intersection of two unrelated
        # cadences -- at BATCH_W=4, MANAGE_EVERY=20 that intersection is EMPTY and the instrument silently never
        # fires. This is the second time in this file; _greach had the same bug and the same fix.
        if FABRIC:
            _armed = (_nbwd % max(1, MANAGE_EVERY // max(1, BATCH_W)) == 0)
            fab._sample_mix = _armed; fab._sample_ord = _armed
        if FABRIC:
            # DISCOVERY BY SPECIFICATION. The router's query for THIS signature is a point in identity space;
            # if nothing live is near it, the expert it is asking for does not exist -- so build it. Cheap enough
            # to try on the manage cadence rather than every step, and bounded by FAB_NMAX like any other growth.
            # NOT society-only: q_route is the chaining path's transition query too, so "the router asked for an
            # expert that does not exist" is exactly as meaningful there, and it was simply never asked.
            if FAB_SPAWN and MANAGE_ON and step % MANAGE_EVERY == 0 and step > 0:
                with torch.no_grad(): _q6 = fab.q_route(sigb[:1])
                _new6 = fab.spawn_from(_q6, step=step)
                if _new6 is not None:
                    print(f"  [expert @ {step}] router asked for an expert nothing served -> DECODED it into "
                          f"slot {_new6} ({fab.n()} live, {fab.spawned} spawned this way)")
        if FABRIC and SOCIETY:
            # SPARSE: compute only the experts whose outputs are actually consumed below. The dense blend that used
            # to be assigned to h here was never read -- the logits come from _O -- so it was pure waste.
            _ban = fab.dom_ban(did, len(asm.cent)) if SELF_ORG else None
            _w, _O, _oid = fab.society(h, sigb, _fab_nov.expand(x.size(0)), k=max(ENS_K, IND_K), ban=_ban, step=step)
            _dep = h.new_zeros(()); _bal = fab_bal(_w)
        elif FABRIC:
            _ban = fab.dom_ban(did, len(asm.cent)) if (SELF_ORG and fab.chain_ban) else None
            h, _dep, _mass, _bal = fab(h, sigb, _fab_nov.expand(x.size(0)), step=step, ban=_ban,
                                       head=(model.head if fab.vote else None))
            # THE SAME (B,N) ATTRIBUTION TABLE THE SOCIETY PATH PRODUCES, so everything downstream that asks
            # "which expert served this window" works here too instead of being skipped.
            _w = fab._wrun
            if _w is not None: _oid = _w.topk(min(max(ENS_K, 1), _w.size(-1)), dim=-1).indices
        if FABRIC and _w is not None:
            # AFFILIATION, on both paths. This drives the breadth cap (how many domains one expert may serve) and
            # the end-of-run affiliation map; under chaining neither had any data at all.
            with torch.no_grad():
                # EVERY WINDOW IN THE BATCH, not row 0. This recorded ONE expert per step, from the first row --
                # so at BATCH_W=16, fifteen of every sixteen windows' experts were never recorded as serving
                # anything. Measured consequence: "experts serving none: 4053" of 4096, an affiliation map built
                # from a 1-in-16 sample of one row. dom_ban reads that table, so the percentage breadth cap could
                # only ever ban the ~30 experts that happened to land in it.
                _tops = _w.argmax(-1).tolist() if _w.dim() == 2 else [int(_w.argmax())]
                for _e5 in _tops: fab.note_dom(_e5, did)
                # ...and utilization ONLY on the society path here, because the chaining paths already record it
                # per row inside forward(). Society recorded it nowhere else, so its `use` table was that same
                # 1-per-step sample while chaining's was BATCH_W per step -- the two paths were measuring
                # utilization at rates differing by BATCH_W, and their ROUTER SELECTION figures were compared
                # to each other throughout this branch as if they meant the same thing.
                if SOCIETY: fab.note_use(_tops)
                _wd = _w[0].detach()                       # which experts serve THIS domain, and how much. Kept ON DEVICE:
                #   `.cpu()` here forced a full GPU->CPU synchronization EVERY step for a number that is only read once, in
                #   the end-of-run affiliation report. Accumulate on device; move to host when reporting.
                if did in dom_exp and dom_exp[did].numel() == _wd.numel(): dom_exp[did] += _wd
                else: dom_exp[did] = _wd.clone()
        elif _sl >= 0:
            h = experts.one(h, _sl)
        if FABRIC and SOCIETY:                             # ENSEMBLE the experts' OUTPUTS (not their hidden states)
            _ki = torch.arange(min(ENS_K, _O.size(1)), device=_O.device)   # _O is ALREADY the top-k, in rank order
            # PER-ROW ensemble weights: _oid is (B,kk) now, so each window is blended with ITS OWN experts at ITS
            # OWN weights. gather rather than index -- _w[:, _oid] would broadcast the whole batch against itself.
            _wk = _w.gather(1, _oid[:, _ki])                                   # (B,ens_k)
            _wk = _wk / _wk.sum(-1, keepdim=True).clamp_min(1e-9)
            _hd = {}                                       # cache: ENS_K and IND_K overlap, so share the head passes
            lg = None
            for _q, _j in enumerate(_ki.tolist()):
                _hd[_j] = model.head(fab.norm(_O[:, _j]))
                _cw = _wk[:, _q][:, None, None]
                lg = _hd[_j] * _cw if lg is None else lg + _hd[_j] * _cw
            # THE ROUTER DECIDES WHETHER THE POPULATION ANSWERS AT ALL. Its HALT mass buys the base head directly;
            # the rest buys the ensemble. This is the term that lets "no expert fits this" be a routing OUTCOME
            # rather than something only an ablation flag could express.
            lg = halt_blend(model, fab, h, lg)
        elif FABRIC and fab.vote and fab._votelg is not None:
            lg = fab._votelg                       # the hybrid already produced logits, one vote per hop
        else:
            lg = model.head(h)
        # PER-WINDOW loss, then the mean. Same arithmetic, same cost -- reduction='none' and .mean() is exactly
        # what cross_entropy does internally -- but it leaves the per-window numbers available, and COMPETENCE
        # cannot be tracked without them.
        _plw = F.cross_entropy(lg.reshape(-1, V), y.reshape(-1), reduction="none").reshape(y.size(0), -1).mean(-1)
        loss = _plw.mean()
        # === COMPETENCE, the term selection was missing ==========================================================
        # Every cull rule in this system ranks on UTILIZATION: fabric soft_cull on routing mass, ExpertRouter on
        # use-per-unit-time, domains on decayed `act`. Utilization is the right resource -- it is what the
        # population competes for -- but on its own it cannot tell a niche expert that is excellent when called
        # from a dead one, because both are called rarely. The protections that existed were all TIME-based
        # (grace for the newborn, an AND-clause on staleness, bounded rank turnover): they protect the NEW and
        # they bound the RATE of death. Nothing protected the USEFUL-BUT-RARE.
        # So track, online and free, how well the material each domain and each node WINS is actually modelled,
        # as an EMA against the population's own EMA. A unit that beats the population on its own material is
        # earning its place however seldom it is called, and the cull rules now check that before dropping it.
        with torch.no_grad():
            _cg = float(loss)
            asm.comp_glob = _cg if asm.comp_glob is None else (1 - COMP_EMA) * asm.comp_glob + COMP_EMA * _cg
            for _r, _dd in enumerate(_bd[:_plw.size(0)]):
                _v = float(_plw[_r])
                asm.comp[_dd] = _v if _dd not in asm.comp else (1 - COMP_EMA) * asm.comp[_dd] + COMP_EMA * _v
            # BOTH PATHS. This was society-only, so a chaining run tracked no per-expert competence and no
            # fast/slow error pair -- which means the sustained-error cull route (the one that distinguishes an
            # expert that is FAILING from one that is ADAPTING) had no inputs and never fired, leaving utilization
            # under capacity pressure as the only way an expert could ever die.
            if FABRIC and _w is not None and _w.dim() == 2:
                # _w is indexed by GLOBAL node id (the code below reads it as _w[:, _oid[rank]]), so argmax over it
                # is already the node id. Indexing _oid with it treated a global id as a rank and went out of bounds.
                _wn = _w.argmax(-1)                                      # the expert each window leans on most
                if _wn is not None:
                    for _r in range(min(_plw.size(0), _wn.numel())):
                        _n = int(_wn[_r]); _v = float(_plw[_r])
                        fab.comp[_n] = _v if _n not in fab.comp else (1 - COMP_EMA) * fab.comp[_n] + COMP_EMA * _v
                        fab.note_err(_n, _v)               # fast+slow pair -> sustained-vs-transient discrimination
            # === MARGINAL CONTRIBUTION: what the system LOSES without this expert =================================
            # The EMA above has a flaw that matters for a rule deciding who lives. It credits a node with the loss
            # on the windows it WINS, against the population's loss on ALL material -- so a node that happens to
            # win easy windows scores well even if any node would do as well on them. It measures the material as
            # much as the expert.
            # The counterfactual does not have that problem: drop the expert, recombine, ask what the loss does.
            # It also cannot be gamed by producing a large or noisy message, which is the failure mode a
            # contribution-magnitude signal would have -- a noisy expert makes the blend WORSE when present, so
            # removing it IMPROVES the loss and its contribution goes NEGATIVE. Only being useful scores.
            # Nearly free, and only because society() returns per-expert outputs separately: every _hd[j] is
            # already computed for the forward pass, so leave-one-out is a re-weighted sum of tensors in hand
            # rather than k extra forward passes. Run on the manage cadence -> 1-in-MANAGE_EVERY cross_entropy.
            if (FABRIC and SOCIETY and MANAGE_ON and len(_hd) > 1 and step % MANAGE_EVERY == 0 and step > 0):
                _kk2 = sorted(_hd)
                for _j2 in _kk2:
                    _keep = [q for q in _kk2 if q != _j2]
                    _kt = torch.tensor(_keep, device=_w.device)
                    _w2 = _w.gather(1, _oid[:, _kt])           # (B,keep) -- per row, like the forward pass
                    _w2 = _w2 / _w2.sum(-1, keepdim=True).clamp_min(1e-9)
                    _lg2 = None
                    for _t2, _q2 in enumerate(_keep):
                        _cw2 = _w2[:, _t2][:, None, None]
                        _lg2 = _hd[_q2] * _cw2 if _lg2 is None else _lg2 + _hd[_q2] * _cw2
                    #   Blend the same way the real forward pass did, or the counterfactual is measured against a
                    #   different function than the one that produced `loss` and every contribution is offset by
                    #   whatever HALT was spending on the base head.
                    _lg2 = halt_blend(model, fab, h, _lg2)
                    _d2 = float(F.cross_entropy(_lg2.reshape(-1, V), y.reshape(-1)) - loss)
                    #   ROW 0's expert for this rank slot: with per-window routing a slot no longer names ONE
                    #   expert across the batch, so attribute to the most common holder of that slot.
                    _nid = int(torch.mode(_oid[:, _j2]).values)
                    fab.contrib[_nid] = _d2 if _nid not in fab.contrib else \
                        (1 - COMP_EMA) * fab.contrib[_nid] + COMP_EMA * _d2
            # CHAINING gets the same signal, at the cost the path implies. There are no separable per-expert logits
            # to recombine here -- removing an expert changes the WALK, so the counterfactual has to be walked. That
            # is one extra fabric forward per candidate, under no_grad, on the manage cadence: at MANAGE_EVERY=500
            # and FAB_CHAIN_K=8 it is 8 forwards per 500 steps. Without it, chaining culls on utilization alone,
            # which cannot tell a niche expert that is excellent from a dead one -- both are called rarely.
            elif (FABRIC and MANAGE_ON and _w is not None and _oid is not None
                  and step % MANAGE_EVERY == 0 and step > 0):
                _cand = sorted({int(v) for v in _oid.reshape(-1).tolist()})[:fab.chain_k]
                for _n3 in _cand:
                    _h3 = fab(model.encode(x), sigb, _fab_nov.expand(x.size(0)), step=step, ban1=_n3)[0]
                    _d3 = float(F.cross_entropy(model.head(_h3).reshape(-1, V), y.reshape(-1)) - loss)
                    fab.contrib[_n3] = _d3 if _n3 not in fab.contrib else \
                        (1 - COMP_EMA) * fab.contrib[_n3] + COMP_EMA * _d3
        # === DEEP SUPERVISION: give every hop its own answer ====================================================
        # The chain's only loss was at the END of the walk. Hop t's router therefore learned through the chain rule
        # from D-t hops away, and since topk's INDICES carry no gradient, that signal could only re-weight experts
        # already chosen -- never say "you should have gone elsewhere". Measured consequence: on a task where each
        # domain needs an ORDERED pair of transforms, I(domain; hop-1 choice) equalled I(domain; hop-0 choice) to
        # three decimals on every seed. The second hop carried no information at all.
        # Scoring the state after EACH hop gives that hop, and the expert it picked, a local "did this help?".
        _sup = None
        if FABRIC and not SOCIETY and fab.sup_w > 0 and len(getattr(fab, "_hops", [])) > 1:
            for _hh in fab._hops[:-1]:                          # the last hop IS the main loss; don't double-count
                _sl = F.cross_entropy(model.head(_hh).reshape(-1, V), y.reshape(-1))
                _sup = _sl if _sup is None else _sup + _sl
            _sup = _sup / max(1, len(fab._hops) - 1)
        # NEW TOKENS ARE TRAINED WITH THE LOSS, held to their composite while young. This is the term that makes
        # the mint a HANDOVER rather than a jump: the residual is penalised in proportion to how recently the
        # token was minted, so it behaves as its composite at birth and is progressively released.
        _anc = model.compose.anchor(step, TOK_ANCHOR_TAU) if (TOK_COMPOSE and TOK_ANCHOR > 0
                                                              and getattr(model, "compose", None) is not None) else None
        _bw = max(0.0, 1.0 - step / max(1, BAL_WARM))            # DECAY balance: uniform early (no collapse), free later
        _pw = min(1.0, step / max(1, PONDER_WARM))               # ANNEAL ponder: don't charge for depth before the
        # EVERY STEP, not on the embed cadence. The refresh cadence exists because RE-READING identities is
        # O(N * 2*d*r * hid); TRAINING the embedder is capped at 256 experts and is cheap. Tying the two meant the
        # embedder got one update per 50 steps at weight 0.05 -- twelve weak updates in a short run -- and it stayed
        # collapsed. Isolated, the same loss separates identities from 0.021 to 0.217 in 300 updates; it was never
        # given 300. Cost of the split: the loss trains every step, the cache still refreshes on cadence.
        _ael = fab.ae_loss(min(fab.n(), 256)) if (FABRIC and FAB_SPAWN) else None
        tot = loss + ((PONDER * _pw) * _dep + FAB_BAL * _bw * _bal if FABRIC else 0.0) \
            + (FAB_AE_W * _ael if _ael is not None else 0.0) \
            + (fab.sup_w * _term("CHAIN_SUP", _sup) if _sup is not None else 0.0) \
            + (TOK_ANCHOR * _term("TOK_ANCHOR", _anc) if _anc is not None else 0.0)  # nodes have had a chance
        if FABRIC and not SOCIETY and DIV_W > 0 and getattr(fab, "_div", None) is not None:
            tot = tot + DIV_W * _term("DIV_W", fab._div)   # same pressure, from the per-hop expert outputs
        if FABRIC and SOCIETY and DIV_W > 0 and _O.size(1) > 1:   # DISTINCTNESS: reward experts for DISAGREEING, so
            #   RANK SLOTS, not global ids. `_w.mean(0).topk(...)` returns GLOBAL expert ids while `_O` is indexed
            #   by RANK -- so this indexed a rank slot with an expert id and raised IndexError the first time
            #   anyone set DIV_W > 0. Nobody ever had: it defaults to 0, so the one term in this system that
            #   rewards experts for DIFFERING has been un-runnable since routing went per-window, and silently.
            #   _O is already returned in rank order, so slots 0 and 1 ARE the top two by routing mass.
            _a = _O[:, 0].reshape(-1); _b = _O[:, 1].reshape(-1)   # they carry different competence instead of
            tot = tot + DIV_W * _term("DIV_W", F.cosine_similarity(_a, _b, dim=0).clamp_min(0.0))
        if FABRIC and SOCIETY and IND_W > 0:                # INDEPENDENCE: each expert must solve the task ALONE
            for _j in range(min(IND_K, _O.size(1))):          #   (weighted by its routing mass) -- makes the population
                _lj = _hd.get(_j)                             #   an ENSEMBLE, which survives member removal, rather than
                if _lj is None: _lj = model.head(fab.norm(_O[:, _j]))   #   a DECOMPOSITION, which does not
                #   `.detach()` instead of `float()`: numerically identical (both stop the gradient) but stays on device,
                #   where `float()` forced a GPU->CPU sync per expert per step.
                tot = tot + IND_W * _w.gather(1, _oid[:, _j:_j + 1]).mean().detach() * _term(
                    "IND_W", F.cross_entropy(_lj.reshape(-1, V), y.reshape(-1)))
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
        # === HOW MANY EXPERTS ACTUALLY LEARN THIS STEP? ==========================================================
        # The population is selected sparsely, so only the experts the router COMPUTED appear in the graph -- the
        # rest have an exactly-zero gradient row and are frozen, not merely unused. That number is the ceiling on
        # how fast a large population can become differentiated, and nothing was measuring it: a run could report
        # 4096 experts while a few dozen did all the learning, and the report would look identical.
        # Counted straight off the gradient, on the manage cadence, before the step clears it.
        # Cadence on a counter of BACKWARD passes, not on `step`. `step` counts WINDOWS and this block only runs on
        # the 1-in-BATCH_W steps where the batch flushes, so `step % MANAGE_EVERY == 0` samples the intersection of
        # two unrelated cadences -- at BATCH_W=4, MANAGE_EVERY=20 that intersection is EMPTY and the measurement
        # silently never fired. Exactly the class of bug this measurement exists to catch, one level up.
        _nbwd += 1
        if FABRIC and not fab.norm_only and _nbwd % max(1, MANAGE_EVERY // max(1, BATCH_W)) == 0 and fab.A.grad is not None:
            with torch.no_grad():
                _gn = int((fab.A.grad[:fab.n_live].abs().sum(dim=(1, 2)) > 0).sum())
                # WHICH ROUTER PARAMETERS ARE ACTUALLY BEING TRAINED. This project has shipped a dead router
                # parameter more than once -- keys/qproj/q_entry/nov/ctrl/halt_key all received exactly zero
                # gradient under grounded routing until it was noticed, and halt_b was dead on the chaining path
                # the day chaining became the default. A parameter that is allocated, optimized and decayed but
                # never gradiented is indistinguishable from a working one in every other line of the report.
                for _rn in ("q_entry", "q_route", "nov", "ctrl", "halt_key", "halt_b", "eemb", "edec"):
                    _rm = getattr(fab, _rn, None)
                    if _rm is None: continue
                    _rp = list(_rm.parameters()) if isinstance(_rm, nn.Module) else [_rm]
                    if any(p.grad is not None and bool(p.grad.abs().sum() > 0) for p in _rp):
                        _rlive.add(_rn)
                    _rseen.add(_rn)
            _greach.append(_gn)
        if LR_SCHED != "none":
            _lrv = _lr_at(step, max(1, _lr_total(step)))     # the LIVE horizon, not the seed-vocabulary guess
            for _g in om.param_groups: _g["lr"] = _lrv
            for _g in oe.param_groups: _g["lr"] = _lrv
        if (step + 1) % ACCUM == 0: om.step(); om.zero_grad()
        _t1("lm fwd+bwd (incl. fabric/world)", _plm)
        _lf = float(loss.detach())                               # ONE host sync per step (was two: the curve and the
        _lm_run.append(_lf)                                      #   plateau detector each pulled the same scalar back)
        if _due("lmcurve", max(1, (STREAM_LEN // WIN) // 8)) and _lm_run:
            _lm_curve.append((step, sum(_lm_run[-2000:]) / len(_lm_run[-2000:]))); _lm_run = _lm_run[-2000:]
        # ...and the same cadence fix again. `step % MANAGE_EVERY == 0` never coincides with a flush step at
        # BATCH_W=4, so maybe_deepen was NEVER CALLED in a real run. I reported "staged depth did not help" off
        # the back of that. It had not run. Only the synthetic probe, which called it directly, tested it at all.
        if (FABRIC and not fab.norm_only and not SOCIETY and MANAGE_ON and _nbwd > 0
                and _nbwd % max(1, MANAGE_EVERY // max(1, BATCH_W)) == 0):
            _nd = fab.maybe_deepen(_lf, step)
            if _nd is not None:
                print(f"  [chain @ {step}] depth {_nd - 1} stopped paying -> {_nd} hop(s) of {fab.max_steps}. "
                      f"The order is learned one position at a time; hop {_nd} now chooses in the context of a "
                      f"settled hop {_nd - 1}.")
            # PER-HOP SPAWN. The hop-2 query is a request that may have no answer, and spawn-by-specification only
            # ever ran at entry. Ask on the deepest hop that actually ran.
            if FAB_SPAWN and fab._hopq:
                _nw = fab.spawn_from(fab._hopq[-1], step=step)
                if _nw is not None:
                    print(f"  [expert @ {step}] a MID-CHAIN query had no near match -> decoded it into slot {_nw} "
                          f"(hop {len(fab._hopq)}, {fab.n()} live)")
        if FABRIC and not fab.norm_only:
            _nb = fabgrow.step(_lf, step, fab.n(), FAB_NMAX)    # 0, or HOW MANY to grow (burst on an unexpected regression)
            _nb = min(_nb, FAB_NMAX - fab.n())
            for _g in range(max(0, _nb)):                       # each newborn is keyed at the CURRENT signature, so a
                _fp = fab.grow(sig[None, :], step=step)      # burst owns the CURRENT region, on either path:
                #   a newborn keyed at random receives no traffic, gets no gradient and stays dead, and that is
                #   as true of a chaining walk's entry distribution as it is of the society's router.
                if _fp: om.add_param_group({"params": _fp})
                #   EMPTY GROUPS ARE NOT FREE. Since the population became preallocated tensors, grow() returns []
                #   -- the rows are already in the optimizer. Adding a group anyway appended an EMPTY param group
                #   per growth event, so a checkpoint after 60 growths had 60 phantom groups, load_state_dict
                #   refused the count mismatch, and every Adam moment was discarded on every resume.
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
                _own = None if not (FABRIC and MEM_PER_EXPERT and _w is not None) else \
                    [int(_w[min(_b, _w.size(0) - 1)].argmax()) % max(1, mem.n_own) for _b in range(x.size(0))]
                #   FOLDED into the owner count. The store has MEM_OWNERS partitions (64) while expert ids now run to
                #   FAB_NMAX (4096+), so an unfolded id indexes past the partition table. Owners are a memory-eviction
                #   scheme, not an identity: several experts sharing one LRU block is fine, an out-of-range write
                #   is not. Sizing owners to FAB_NMAX instead would have given 200000/4096 = 48 entries per expert.
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
        # STOP MINTING EVENTUALLY -- an option, NOT a recommendation. The argument for it was that minting
        # re-tokenizes the stream, so the same text acquires new ids and the rows learned for the old segmentation
        # are invalidated continuously. On that reasoning this knob was believed to fix "the project's own
        # continual-learning failure mode".
        # MEASURED, AND IT IS THE OTHER WAY ROUND. Six arms, one seed, identical harness, at 707f1af:
        #     base       (mint the whole run)                held-out 1.962
        #     frozen     (TOK_MINT_UNTIL=1)                  held-out 2.072
        #     frozen_nr  (TOK_MINT_UNTIL=1 RETOK_EVERY=0)    held-out 2.365
        # Minting for the whole run is BEST. The earlier result that made freezing look good was measuring the LR
        # schedule: a vocabulary that never grows makes _total_steps accurate, which was the only way the cosine
        # ever annealed. Fix the schedule and the advantage inverts. 0 = never freeze, and 0 is the default for a
        # reason.
        if ONLINE and TOK_MINT_UNTIL and step >= TOK_MINT_UNTIL and not _mint_frozen[0]:
            _mint_frozen[0] = True
            print(f"  [tokenizer @ {step}] MINTING FROZEN at vocab {TOK.vocab_size} (TOK_MINT_UNTIL={TOK_MINT_UNTIL}). "
                  f"The segmentation stops moving here; everything learned after this point is learned against a "
                  f"fixed vocabulary.")
        if ONLINE and not _mint_frozen[0]:                 # ONGOING minting: mint from the tally accumulated above
            if _due("grow", GROW_EVERY):
                for _ in range(_i("GROW_BURST", 6)):       # mint several of the current top pairs per grow event
                    g = TOK.maybe_grow()
                    if g is None: break
                    if _i("WARMSTART", 1):                 # init the new token "ab" from (emb[a]+emb[b])/2 instead of random
                        nid, a, b = g                      #   -> the LM doesn't relearn it from scratch (cuts moving-target cost)
                        # OPTIMIZER-STATE INHERITANCE, OFF BY DEFAULT because the reason for it did not survive
                        # being checked. The argument was: a row that never received gradient has Adam v = 0, so
                        # its first update is lr * sign(g) -- the maximum step -- which would overwrite the warm
                        # start we just placed. That is wrong. Adam's step counter is PER-TENSOR, not per-row, so
                        # by the time a token is minted the bias correction already reflects thousands of steps
                        # and DAMPS a fresh row rather than amplifying it. Measured on a 5-step toy: the new row's
                        # first update was 5.4e-4 with v=0 and 1.0e-3 with inherited moments -- inheritance makes
                        # the first step LARGER, the opposite of the motivation.
                        # Kept as a flag, off, because "start the new token moving the way its parents were
                        # moving" may still be right for a different reason; it just is not the one I had.
                        if _i("WARMSTART_OPT", 0):
                            _inherit_opt(om, model.emb.weight, nid, a, b)
                            _inherit_opt(om, model.head.weight, nid, a, b)
                            if model.head.bias is not None: _inherit_opt(om, model.head.bias, nid, a, b)
                            if SIG_SPACE == "tokens" and nid < enc.emb.num_embeddings:
                                _inherit_opt(oe, enc.emb.weight, nid, a, b)
                        # THE TWO SIDES ARE NOT SYMMETRIC, and averaging both was leaving most of the warm
                        # start's value on the table.
                        #   HEAD  scores "the next token is ab" from the state at position t. That is the same
                        #         decision the model already made when it scored "next is a" there -- the contexts
                        #         where ab now appears are exactly the contexts where a appeared and b followed.
                        #         head[b] is tuned for a DIFFERENT conditioning state, the one AFTER consuming a,
                        #         so averaging it in is mixing in the wrong row. -> head[ab] = head[a]
                        #   EMB   is what the recurrence CONSUMES. After consuming ab the state should be where
                        #         consuming a then b left it, and the last symbol dominates what gets handed
                        #         forward. -> emb[ab] = emb[b]
                        # Measured on the immediate post-mint loss (what the model must climb back from at every
                        # mint), 6 pairs x 3 seeds = 18 trials:
                        #     random               2.1699 (sd 0.120)
                        #     mean/mean  [old]     1.8222 (sd 0.078)
                        #     mean/first           1.6252 (sd 0.071)
                        #     last/first [now]     1.4822 (sd 0.011)   -0.340 vs old, 31x its own sd
                        #     sum/first            1.6518 (sd 0.100)
                        # The old warm start beat random by 0.348; this beats the old warm start by 0.340, so on
                        # THAT measurement it roughly doubles what the mechanism is worth.
                        #
                        # IT IS NOT THE DEFAULT, because the only end-to-end check available disagrees: on a short
                        # toy with minting on, held-out came out 5.214 with last/first against 5.100 with mean.
                        # That is one run of one seed and the gap is well inside the 0.06-0.17 seed spread measured
                        # at pilot scale, so it does not refute the 18-trial result -- but the 18-trial result only
                        # measures the IMMEDIATE post-mint loss, and "cheaper to recover from" is not the same
                        # claim as "better model at the end". Two measurements, pointing different ways, neither
                        # decisive. Defaulting on the one that has never been checked end to end is the mistake
                        # this branch has made repeatedly.
                        # WARMSTART_MODE=last/first to run it; the pilot decides.
                        if TOK_COMPOSE:
                            # NOTHING TO INITIALISE. The new token's vector is already determined by its bytes;
                            # all that is needed is to tell the composer the vocabulary grew.
                            model.compose.set_vocab(TOK.id2bytes, DEV, VMAX)
                            model.compose.note_born([nid], step)   # its residual is held near 0 while it is new
                            continue
                        _wm = _env("WARMSTART_MODE", "mean")
                        with torch.no_grad():
                            if _wm == "mean":
                                model.emb.weight[nid] = 0.5 * (model.emb.weight[a] + model.emb.weight[b])
                                model.head.weight[nid] = 0.5 * (model.head.weight[a] + model.head.weight[b])
                                if model.head.bias is not None:
                                    model.head.bias[nid] = 0.5 * (model.head.bias[a] + model.head.bias[b])
                            else:
                                model.emb.weight[nid] = model.emb.weight[b]
                                model.head.weight[nid] = model.head.weight[a]
                                if model.head.bias is not None:
                                    model.head.bias[nid] = model.head.bias[a]
                            if SIG_SPACE == "tokens" and nid < enc.emb.num_embeddings:
                                # The signature encoder needs this MORE than the LM does: a domain centroid is a mean
                                # of encodings, so one freshly-random token id inside a window perturbs every
                                # signature that contains it, and the assembler reads those as a domain shift.
                                # It is a sequence encoder consuming the token, so it takes the CONSUMED side.
                                enc.emb.weight[nid] = (0.5 * (enc.emb.weight[a] + enc.emb.weight[b])
                                                       if _wm == "mean" else enc.emb.weight[b])
        _t1("tokenizer (mint/tally)", _ptok)
        _bx = []; _by = []; _bg = []; _bd = []; _bp = []
        i += WIN; step += 1
        if (CKPT_EVERY and _due("ckpt", CKPT_EVERY)) or _ckpt_req["on"]:   # periodic OR on-demand (kill -USR1) save
            _why = "SIGUSR1" if _ckpt_req["on"] else f"every {CKPT_EVERY}"; _ckpt_req["on"] = False
            _save_ckpt(stream, quiet=True); print(f"  [checkpoint @ {step} ({_why}) -> {_env('SAVE_CKPT', '')}]"); model.train()
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
            # THE HELD-OUT CURVE'S CACHE MUST DIE WITH THE SEGMENTATION. _VALT tokenises the validation text ONCE
            # and never invalidated it, so after the first mint the curve compared a model trained on the CURRENT
            # segmentation against validation text frozen in an OLD one -- and the mismatch grew with every mint.
            # That is not a comparison across time; the reference moves out from under it.
            # It explains the shape exactly: the curve degrades over the MINTING window (steps ~3000-21000) and
            # goes flat the moment minting stops (vocab caps at 21056, +0 tokens after), which is the behaviour of
            # a drifting yardstick, not of a model that suddenly stops getting worse. It also explains why "best"
            # lands at ~6000 in every arm at every seed: that is the last sample where the cache still matched.
            _VALT.clear(); _BL.clear()
            if SIG_SPACE == "tokens":                        # the encoder reads the TOKEN stream, which was just rebuilt
                ENC_SEQ = stream; set_enc_tensor(ENC_SEQ)    #   -> re-point it, or it trains on a stale segmentation
            if FABRIC and fabgrow is not None: fabgrow.note_shift(step)   # the loss jump after a retok is OURS, not a shift
            # WHAT IT ACTUALLY MINTED, not just how many. The count says the vocabulary grew; it cannot say
            # whether the growth was worth having, and a run that ends up spelling in fragments looks identical
            # here to one minting whole words. A sample of the newest ids costs nothing and makes the DRIFT
            # visible while the run is still going -- early cohorts are short and word-like, and the question is
            # what the late ones look like. `vocab.py` reads the whole list afterwards from TOKENIZER_PATH.
            _new = []
            for _t in range(max(256, _last_vsz), TOK.vocab_size):
                _s = TOK.id2bytes[_t].decode("utf-8", "replace")
                _new.append("·" + _s[1:] if _s.startswith(" ") else _s)
            print(f"  [tokenizer @ {step}] vocab {TOK.vocab_size}/{TOK.vmax} (minting live; "
                  f"+{TOK.vocab_size - _last_vsz} since last retok)"
                  + (f" newest: {'  '.join(repr(_x) for _x in _new[-8:])}" if _new else ""))
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
        TOK.save(_env("TOKENIZER_PATH", "data/dyntok.json"))
        print(f"[tokenizer] ONLINE: minted throughout -> grew 256 -> {TOK.vocab_size} during training; final re-tokenization for eval")

    # === SOFTMAX WIDTH vs THE VOCABULARY THAT EXISTS =========================================================
    # V is the row count the LM loss normalises over. Under ONLINE it is VMAX, fixed before training starts,
    # while the vocabulary is whatever the tokenizer reaches. Rows the stream never carries as a target appear
    # only in the denominator -- they take the push-down half of the cross-entropy gradient and never the
    # push-up half -- but they get there two different ways, and the two do not mean the same thing:
    #   NEVER MINTED (width - minted): the id was never assigned to any byte sequence. The row holds its
    #     initialisation for the entire run. This gap is set by configuration, not by the data, and a run with a
    #     large one is not measuring what its VMAX says it is.
    #   MINTED THEN UNUSED (minted - used): the id existed and lost its occurrences to later merges. This is
    #     ordinary vocabulary turnover; the row was trained while it was in use.
    # Neither is otherwise anywhere in the log, so a run spreading its loss over rows that index nothing reads
    # exactly like one that is simply bad. Print-only; nothing below depends on it.
    try:
        _seen = torch.zeros(int(V), dtype=torch.bool)
        for _c0 in range(0, len(stream), 1 << 20):
            _seen[torch.as_tensor(list(stream[_c0:_c0 + (1 << 20)]), dtype=torch.long)] = True
        _nused = int(_seen.sum()); _nmint = TOK.vocab_size if USE_TOK else 256
        _nnever = int(V) - _nmint; _nturn = _nmint - _nused
        print(f"[vocab] softmax width {int(V)} | minted {_nmint} | used in the training stream {_nused}")
        print(f"[vocab]   never minted     {_nnever:6d}  ({_nnever / max(1, int(V)) * 100:5.1f}% of width)  "
              f"-- rows at their initialisation, in the denominator for the whole run")
        print(f"[vocab]   minted, unused   {_nturn:6d}  ({_nturn / max(1, int(V)) * 100:5.1f}% of width)  "
              f"-- trained while in use, then lost to later merges")
    except Exception as _e:                                          # an instrument must not be able to end a run
        print(f"[vocab] width-vs-live check skipped: {type(_e).__name__}: {_e}")

    _save_ckpt(stream)                                               # final save (also runs mid-run if CKPT_EVERY>0)

    assigns = [(i, asm.resolve(d), t) for i, d, t in assigns]        # follow merges -> the surviving domain
    try:                                                   # === MEMORIZATION CHECK: train vs HELD-OUT ===
        model.eval()
        _vb = []
        for _p in range(len(VALC)):
            _v = _units(TOK, USE_TOK, VALC[_p])
            if len(_v) < WIN + 2: continue
            _st = [random.randint(0, len(_v) - WIN - 2) for _ in range(min(24, _i("EVAL_N", 64)))]
            with torch.no_grad():
                _X = torch.tensor([_v[a:a + WIN] for a in _st], device=DEV)
                _Y = torch.tensor([_v[a + 1:a + WIN + 1] for a in _st], device=DEV)
                _lg = _eval_logits(model, fab, FABRIC, _X)
                _pp = F.softmax(_lg, -1).gather(-1, _Y.unsqueeze(-1)).squeeze(-1)
                _vb.append(-(torch.log(_pp.clamp_min(1e-9)).sum().item()) / math.log(2) / nbytes(_Y))
        _tb = []
        for _p in range(len(CORP)):                        # same measurement on TRAIN data, for a like-for-like gap
            _src = CORP[_p][max(0, SEG_LEN[_p] - len(VALC[_p])):SEG_LEN[_p]]   # tail of the TRAIN region (disk: CORP still holds val, so bound by SEG_LEN)
            _t = _units(TOK, USE_TOK, _src)
            if len(_t) < WIN + 2: continue
            _st = [random.randint(0, len(_t) - WIN - 2) for _ in range(min(24, _i("EVAL_N", 64)))]
            with torch.no_grad():
                _X = torch.tensor([_t[a:a + WIN] for a in _st], device=DEV)
                _Y = torch.tensor([_t[a + 1:a + WIN + 1] for a in _st], device=DEV)
                _lg = _eval_logits(model, fab, FABRIC, _X)
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
                    _v = _units(TOK, USE_TOK, VALC[_p])
                    _cat += _v[:20000]
                _trn = []                                   # FIT the baselines on TRAIN, score them on HELD-OUT.
                for _p in range(len(CORP)):                 # Measuring a bigram's entropy ON the text it is scored
                    _s2 = CORP[_p][:min(SEG_LEN[_p], 200000)]   # on makes it a model that has seen the answers --
                    _trn += (_units(TOK, USE_TOK, _s2))[:20000]   # an unfairly strong
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
        # Cross-run first: it is the only retention figure that can see past the start of this run, so it should
        # be read before the within-stream one that cannot.
        report_holdout(_hb, _hbs, "ACROSS THE RUN BOUNDARY: what did this run do to what was already known?")
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
                    _lg = _eval_logits(model, fab, FABRIC, _X)
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
                        _v = _units(TOK, USE_TOK, _vb)
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
                            _pm = F.softmax(_eval_logits(model, fab, FABRIC, _X), -1)
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
                _v = _units(TOK, USE_TOK, VALC[_p])
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
        # THIS LINE USED TO READ THE SIGN BACKWARDS, AND ONLY LOOKED AT THE LAST TWO POINTS.
        # _d8 is prev-minus-current, so NEGATIVE means the loss went UP -- and the text said "still FALLING =
        # more passes/steps will help" whatever the sign. A pilot whose loss bottomed at step 5.9k and then rose
        # for the next 42k steps printed "-0.059: still FALLING = more passes will help". Two points also cannot
        # see a 40k-step trend. Measure against the MINIMUM of the whole curve and say the direction out loud.
        _bi = min(range(len(_lm_curve)), key=lambda q: _lm_curve[q][1])
        _bs, _bl = _lm_curve[_bi]; _fs, _fl = _lm_curve[-1]
        _d8 = (_lm_curve[-2][1] - _lm_curve[-1][1]) if len(_lm_curve) > 1 else 0.0
        print(f"  best {_bl:.2f} @ step {_bs} | final {_fl:.2f} @ step {_fs} | since the minimum {_fl - _bl:+.3f}"
              f" | last segment {'-' if _d8 > 0 else '+'}{abs(_d8):.3f} ({'improving' if _d8 > 0 else 'worsening'})")
        # CROSS-CHECK AGAINST THE UNIT-STABLE CURVE BEFORE CALLING IT DIVERGENCE. This curve is per-TOKEN
        # cross-entropy, and the tokenizer mints throughout a run (256 -> 2048 here), so each token comes to carry
        # more bytes and the per-token loss rises MECHANICALLY even when the model is improving per byte. _CURVE
        # is bits/byte on held-out text and is not subject to that. Reporting "DIVERGING" off the per-token curve
        # alone was reading a unit change as a failure, and I have been quoting it for many turns.
        _bpb_dir = None
        try:
            _bp = sorted({st: b for st, _p, b, _a in _CURVE}.items())
            if len(_bp) >= 6:
                _bmin = min(v for _, v in _bp)
                _bpb_dir = (_bp[-1][1] - _bmin, _bp[-1][1] - _bp[len(_bp) // 3][1])
        except Exception:
            _bpb_dir = None
        # IS IT STILL LEARNING? The single most-asked question about this curve, and it was never answered
        # directly: "best" and "since the minimum" describe the whole run, and a run can be flat for its second
        # half while still showing a good minimum somewhere early. The SLOPE over the second half says whether
        # more steps at this setting would buy anything.
        try:
            _bp2 = sorted({st: b for st, _p, b, _a in _CURVE}.items())
            if len(_bp2) >= 8:
                _hh = _bp2[len(_bp2) // 2:]
                _mx = sum(a for a, _ in _hh) / len(_hh); _my = sum(b for _, b in _hh) / len(_hh)
                _sl = (sum((a - _mx) * (b - _my) for a, b in _hh)
                       / max(1e-9, sum((a - _mx) ** 2 for a, _ in _hh))) * 10000
                print(f"  STILL LEARNING? over the SECOND HALF of the run: {_hh[0][1]:.2f} -> {_hh[-1][1]:.2f}, "
                      f"slope {_sl:+.4f} bits/byte per 10k steps.")
                # SAY WHAT IT MOVED, NOT WHAT THAT MEANS. This read "the second half bought nothing. The model
                # is not learning at this setting any more" for any |slope| <= 0.02 -- printed directly beside
                # its own numbers showing 2.04 -> 1.97, i.e. 0.07 b/B that it did buy. The threshold is a
                # reasonable place to stop caring; the sentence was asserting more than the threshold knows.
                _d2 = _hh[-1][1] - _hh[0][1]
                print("    " + ("clearly still improving -- more steps at this setting will buy more."
                                if _sl < -0.02 else
                                f"NEARLY FLAT: {_d2:+.3f} b/B over the whole second half, |slope| <= 0.02 per "
                                f"10k steps. At this rate more steps buy little -- read that against the seed "
                                f"spread before calling it converged."
                                if abs(_sl) <= 0.02 else
                                "getting WORSE through the second half, not merely flat."))
        except Exception:
            pass
        if _bpb_dir is not None:
            print(f"  UNIT-STABLE CROSS-CHECK (held-out bits/byte, the curve above): {_bpb_dir[0]:+.3f} since its "
                  f"own minimum, {_bpb_dir[1]:+.3f} over the last two thirds. Per-token loss can rise purely "
                  f"because minted tokens got longer; this cannot.")
            if _fl - _bl > 0.05 and _bpb_dir[0] <= 0.05:
                print(f"  >> NOT DIVERGING -- the per-token rise is the growing vocabulary, not the model. "
                      f"Judge this run on bits/byte.")
            elif _bpb_dir[1] <= 0.05:
                # PLATEAU IS NOT DIVERGENCE. Measuring only from the global minimum cannot tell "climbed early
                # then settled" from "still climbing", and it called a run DIVERGING whose last two thirds were
                # flat to -0.007. The slope over the recent stretch is the one that says whether it is STILL
                # getting worse, which is the question.
                print(f"  >> PLATEAUED, not diverging. It rose {_bpb_dir[0]:+.3f} from its minimum early on and "
                      f"has been flat since ({_bpb_dir[1]:+.3f} over the last two thirds). What to explain is the "
                      f"EARLY transition, not the tail -- more steps at this setting will not help either, but "
                      f"nothing is degrading.")
        if (_fl - _bl > 0.05 and _bi < len(_lm_curve) - 2
                and (_bpb_dir is None or (_bpb_dir[0] > 0.05 and _bpb_dir[1] > 0.05))):
            print(f"  >> DIVERGING on BOTH the per-token and the bits/byte curve. The loss bottomed at step {_bs} "
                  f"and has been RISING for the "
                  f"{_fs - _bs} steps since -- {100 * (len(_lm_curve) - 1 - _bi) / max(1, len(_lm_curve) - 1):.0f}% "
                  f"of the run was spent getting worse. More steps will NOT help; this needs diagnosing.")
            print(f"     things that change on that timescale: the fabric hitting FAB_NMAX (growth fires on "
                  f"worsening, so a rising loss GROWS the population, which is a feedback loop), BAL_WARM "
                  f"decaying the load-balance pressure to 0, the tokenizer still minting (per-TOKEN loss rises "
                  f"mechanically as tokens get longer -- cross-check the per-process bits/byte curve above, which "
                  f"is unit-stable), and the memory store reaching MEM_CAP.")
        elif _fl - _bl > 0.05 and _bpb_dir is None:
            # ONLY WHEN THERE IS NO UNIT-STABLE CURVE TO ASK. This fired on the PER-TOKEN rise alone, so a run
            # that had just been told "NOT DIVERGING -- the per-token rise is the growing vocabulary, not the
            # model. Judge this run on bits/byte" was told six lines later that it "turned upward at the very
            # end -- watch it", on the strength of the very curve it had been told to ignore. When _bpb_dir
            # exists, one of the three branches above has already given the verdict from the stable units.
            print(f"  >> the PER-TOKEN curve turned upward at the end -- too recent to call, and there is no "
                  f"unit-stable curve this run to check it against. Watch it.")
        else:
            print(f"  >> still improving or flat: falling = more passes/steps will help; flat = the model has "
                  f"converged and needs more CAPACITY or more DATA, not more steps.")
    n_self = len(asm.cent); print(f"SELF-ASSEMBLED {n_self} LIVE domains after {'management' if MANAGE_ON else 'NO MANAGEMENT (ablation)'} (truth had {NP} processes)")
    _ent = sorted((asm.visits.get(i, 0) for i in asm.cent), reverse=True)
    _rec = sum(1 for v in _ent if v >= DOM_MIN_VISITS)
    print(f"  domain population: {asm.created} created | {asm.folded} folded on non-recurrence | {len(asm.merged)} merged"
          f" (fold+merge, absorbed not deleted) | cap bound {asm.capped}x (MAX_DOMAINS={MAX_DOMAINS}) | "
          f"{asm.nb} boundaries | radius {sum(1 for i in asm.cent if asm.rad.get(i) is not None)}/{n_self} measured"
          f"{f', pooled {asm._radp:.3f}' if asm._radp else ''}")
    print(f"  ENTRIES per live domain {_ent[:12]} | recurrent (>= {DOM_MIN_VISITS} entries) {_rec}/{n_self}")
    if FABRIC:
        # === DO THE EXPERTS CHAIN? ============================================================================
        # Asked because it was assumed. The fabric has TWO forward paths and only one of them chains:
        #   SOCIETY=0 (DEFAULT)  forward()  -- routing mass flows node -> node through a learned transition
        #                                     matrix, HALT absorbs, depth is adaptive and charged for (ponder).
        #   SOCIETY=1            society()  -- every expert maps the SAME h to its own output and the outputs are
        #                                     blended. Expert i never sees expert j. Depth is identically 0.
        # The default was the SOCIETY for every run this project made before now, which is why this section exists:
        # the transition matrix, FAB_STEPS, PONDER and PONDER_WARM were all inert, and the depth figures came from
        # a report-time probe of a path nothing had trained. Under the current default they are what ran.
        print(f"\n=== CHAINING: do experts compose, or only vote? ===")
        print(f"  ROUTER INPUTS: signature (detached SigEncoder summary of the raw window) + novelty scalar"
              + (" + the SOURCE's identity, embedded from that expert's FULL WEIGHTS (SRC), + a control summary "
                 "(routed mass, halted mass, entropy). Provenance is in the routing query: the transition depends "
                 "on WHICH expert is holding the state." if not SOCIETY else
                 ". No source term exists on this path -- there is no holder, because nothing is passed between "
                 "experts."))
        print(f"  COMPLETION: " + ("the ROUTER decides. The residual step is scaled by the mass still routing, so "
                                   "as HALT absorbs, updates shrink to zero and the state settles -- the loop "
                                   "counter is only an upper bound."
                                   if not SOCIETY else
                                   ("the ROUTER decides, on this path too. One hop, but HALT is a real operator in "
                                    "the same softmax as the experts, and its mass is spent on the base head "
                                    "instead of on the population -- so 'no expert is needed here' is a routing "
                                    "OUTCOME, not something only an ablation flag could say."
                                    if fab.halt_on else
                                    "ONE-SHOT, HALT DISABLED (FAB_HALT=0). Experts compute once and go straight to "
                                    "the head; the halt mass is computed and discarded, so the router chooses WHICH "
                                    "experts answer but never WHETHER they should.")))
        print(f"  SOCIETY={int(SOCIETY)} -> " + (
            "NO CHAINING (non-default: SOCIETY=1 was set). Experts are independent and blended at the router; each "
            "sees the base representation only. The composition machinery specific to chaining (transition matrix, "
            "adaptive depth, ponder) is present but NEVER RUNS -- HALT is the exception and runs on both paths. "
            "The DEPTH figure below is a report-time probe of a path this run did not use."
            if SOCIETY else
            "CHAINING ACTIVE (the default). Mass flows expert -> expert through the transition matrix over multiple "
            "hops, HALT absorbing, so an expert CAN build on another's output. Depth below is what actually ran."))
        if not SOCIETY:
            print(f"  HALT blocked for the first {fab.min_steps} hop(s) of {fab.max_steps} (FAB_MIN_STEPS"
                  + (", forced to 0 by CHAIN_VOTE" if fab.vote else "")
                  + "). At 0 nothing stops the router halting on the first hop; the depth it actually reached "
                    "is the mean-routed-depth figure in this section.")
        if SOCIETY:
            print(f"  (ponder cost this run: 0 by construction -- _dep is zeros on the society path, so PONDER="
                  f"{PONDER} and PONDER_WARM={PONDER_WARM} had no effect on training whatsoever)")
        # SOCIETY only: on the chaining path route_w never runs, so halt_ema is None and this would print nan.
        # That path reports its own halt mass in the FABRIC probe line below, where HALT means "the walk ended".
        # CHAINING REPORTS ITS TRAINING HALT TOO. This was gated to SOCIETY, so on the default path the only halt
        # figure in the report came from the report-time probe -- and every chaining arm printed "halt 0.00" with
        # no way to tell whether that was the run or the probe. It is the run: depth 1.00 of 4 means the walk ran
        # its full length at full strength on every window, so the router never once chose to stop.
        if fab.halt_on and not SOCIETY and fab._mass_ema is not None:
            _hm2 = float(fab._mass_ema)
            print(f"  HALT MASS during TRAINING (running mean): {_hm2:.4f}. At ~0 the router never stops early, so "
                  f"all {fab.max_steps} hops run at full strength on every window regardless of whether the "
                  f"material needs them -- PONDER={PONDER} charges for depth and still could not lift it.")
        if fab.halt_on and SOCIETY and fab.halt_ema is not None:
            _hv = float(fab.halt_ema)
            print(f"  HALT MASS (running mean over the run): {_hv:.3f} -- the share of the prediction the router "
                  f"handed to the BASE HEAD rather than to the expert population, capped at {fab.halt_max:.2f} "
                  f"(FAB_HALT_MAX) so the experts always keep a share of the gradient.")
            print(f"   read it as: ~0 = the router wants the population on every window (it has not learned that "
                  f"some material needs no expert, or none does); ~{fab.halt_max:.2f} = it is routing around the "
                  f"population, which means the experts are not earning their place and the barrier is the only "
                  f"thing keeping them alive; in between = a real WHETHER decision, per window.")
    if FABRIC and not fab.norm_only:
        # POPULATION CHURN. "4096 nodes (10062 grown)" was the only trace of this and it reads as healthy growth.
        # It is not: 10062 grown against 5969 culled to hold a steady 4096 means the population was REPLACED about
        # 1.5x over, continuously, and a tenth of it was freshly-initialised noise at any moment -- while the
        # centroids and eemb keys are all defined over exactly that churning set.
        _net = fab.n() - _i("FAB_N0", 3)
        _chn = (fab.grown - max(0, _net)) / max(1, fab.grown)
        print(f"\n=== POPULATION CHURN: how much of the growth was NET? ===")
        print(f"  {fab.grown} grown, {fab.removed} removed, net {_net:+d} -> {fab.n()} live of {fab.cap} | "
              f"{_chn:.0%} of all growth was replaced rather than added")
        print(f"  growth fired: {fabgrow.n_ramp}x on the RAMP (population-building), {fabgrow.n_regr}x on a "
              f"REGRESSION, {fabgrow.n_stall}x on a stall")
        if _chn > 0.5:
            print(f"  >> CHURNING. More than half of everything grown was later culled, so capacity is being "
                  f"rebuilt rather than accumulated. Every newborn is untrained, and the identity space the "
                  f"router scores in is defined over the population -- so a high churn rate keeps moving the "
                  f"ground the router stands on.")
        if fabgrow.ramp_done:
            print(f"  (the ramp has LATCHED OFF -- the population reached {fabgrow.ramp_to:.0%} of cap and "
                  f"the ramp does not re-arm when culling drops it back below)")
        elif fabgrow.n_ramp > 50:
            print(f"  >> the RAMP is still firing after {fabgrow.n_ramp} events. It should have latched off once "
                  f"the population was built; if it has not, growth is not reading the loss at all.")
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
                bps = [encpos(s) for s in ii]
                EW = torch.tensor([encwin(x) for x in bps], device=DEV)
                pm = F.softmax(fab_logits(model, fab, h, enc(EW)), -1); h = None
            elif use_exp and EXPERTS:
                bps = [encpos(s) for s in ii]
                if pin:                                    # PINNED: the expert this span actually trained with
                    sl = torch.tensor([int(route_at[min(b, route_at.numel() - 1)]) for b in bps], device=DEV)
                else:                                      # ROUTED: nearest centroid at eval time (what inference does)
                    EW = torch.tensor([encwin(x) for x in bps], device=DEV)
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
    if FABRIC and dom_exp:                                 # === AFFILIATION: which experts serve which domains? ===
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
    if FABRIC and len(fab.bodies) > 1:                     # === INDEPENDENCE: what does deleting ONE expert cost? ===
        _ps2 = sorted(set(labels))
        with torch.no_grad():                              # find the busiest expert (the one worth deleting)
            _sg2 = enc(torch.tensor([list(ENC_SEQ[WIN * 3:WIN * 4])], device=DEV))
            _h2b = model.encode(torch.tensor([list(stream[:WIN])], device=DEV))
            if SOCIETY:
                _w2, _, _ = fab.society(_h2b, _sg2, torch.zeros(1, device=DEV), k=1, learn_regions=False)
            else:                                          # chaining exposes the same table -- see Fabric.forward
                fab(_h2b, _sg2, torch.zeros(1, device=DEV), learn_regions=False)
                _w2 = fab._wrun
        _j2 = int(_w2[0].argmax()) if _w2 is not None else max(fab.use, key=fab.use.get, default=0)
        _pre = {p: bpb_true(p, use_mem=False) for p in _ps2}
        # RESTORE AFTERWARDS: this ablation deletes the BUSIEST expert, and every eval below it -- including the
        # generation samples used to judge coherence -- must run on the INTACT model. remove() is now a
        # swap-with-last on preallocated tensors, so the backup is the affected ROWS plus the live count, not a
        # deepcopy of the whole population (which at FAB_NMAX=4096 would clone 0.2 GB of parameters to undo one
        # deletion).
        _last = fab.n_live - 1
        _bak = {nm: getattr(fab, nm)[[_j2, _last]].detach().clone()
                for nm in ("A", "B", "K", "SRC", "cent")}
        _bak_n = fab.n_live
        fab.remove(_j2)                                    # <- the expert's parameters are deleted
        _post = {p: bpb_true(p, use_mem=False) for p in _ps2}
        _d2 = sum(_post[p] - _pre[p] for p in _ps2) / max(1, len(_ps2))
        print(f"\n=== EXPERT INDEPENDENCE: delete ONE expert of {len(fab.bodies) + 1} -- what breaks? ===")
        print(f"  deleted expert {_j2} (busiest, routing mass {float(_w2[0, _j2]):.2f})")
        for p in _ps2: print(f"    process {p}: {_pre[p]:.3f}->{_post[p]:.3f} ({_post[p] - _pre[p]:+.4f})")
        print(f"  mean collateral {_d2:+.4f}  ->  {'INDEPENDENT (society survives losing a member)' if abs(_d2) < 0.3 else 'ENTANGLED (the population depended on it)'}")
        with torch.no_grad():                              # put the two swapped rows back and restore the count
            for nm, _v in _bak.items(): getattr(fab, nm)[[_j2, _last]] = _v
        fab.n_live = _bak_n
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
            _, _d, _m, _ = fab(model.encode(torch.tensor([list(stream[:WIN])], device=DEV)), _sg,
                               torch.zeros(1, device=DEV), learn_regions=False)
        print(f"\n=== FABRIC: does the routed node population help? (bits/byte, lower=better) ===")
        print(f"  model ALONE {_b:.3f}  ->  + FABRIC {_f2:.3f} (fabric {_b - _f2:+.3f})  ->  + FABRIC + MEMORY {_fm:.3f}")
        print(f"  nodes {len(fab.bodies)} | mean routed depth {float(_d):.2f} of {max(1, min(fab.max_steps, 2 + len(fab.bodies)//2))} steps"
              f" | node mass {[round(float(v), 2) for v in _m[:-1]]} halt {float(_m[-1]):.2f}")
        print(f"  (mass spread across nodes = SPECIALIZED; all mass on one node = collapsed; all mass on HALT = the")
        print(f"   router wrote the nodes off before they could learn -- raise FAB_MIN_STEPS / PONDER_WARM)")
        print(f"  NOTE: 'model ALONE' here is an ABLATION of a component the model TRAINED WITH (it also removes the")
        print(f"   fabric's LayerNorm), so it overstates the fabric's contribution. The honest comparison is this run's")
        print(f"   '+ FABRIC + MEMORY' against a FABRIC=0 run's 'model + MEMORY'.")
    # === IS THE SIGNATURE SPACE A SPACE, OR A POINT? ==========================================================
    # The question every routing result depends on and that nothing measured. Routing sends a window to the expert
    # whose centroid is nearest its SIGNATURE. If the encoder maps all material to nearly the same signature, then
    # there is one region, one nearest centroid, and one used expert -- and no routing rule, temperature, or
    # discovery mechanism can spread traffic across a blob. Diagnosing that from the OUTSIDE cost a separate probe
    # script and a surviving checkpoint; it belongs here, in the run that produced the routing.
    if FABRIC and SIG_MODE == "learned":
        try:
            _sw2 = [encwin(encpos(a)) for a in range(0, min(len(stream) - WIN - 2, 200 * WIN), WIN)][:200]
            if len(_sw2) >= 16:
                with torch.no_grad(): _Zs = enc(torch.tensor(_sw2, device=DEV))
                _Dm = 1 - _Zs @ _Zs.t()
                _off = _Dm[~torch.eye(_Zs.size(0), dtype=torch.bool, device=DEV)]
                _ev = torch.linalg.svdvals(_Zs - _Zs.mean(0, keepdim=True)) ** 2
                _pr = float((_ev.sum() ** 2) / (_ev ** 2).sum().clamp_min(1e-12))   # participation ratio
                _near = (F.normalize(fab.cent[:fab.n_live], dim=-1).to(DEV) @ _Zs.t()).argmax(0)
                _du = len(set(_near.tolist()))
                print(f"\n=== SIGNATURE SPACE: can the router tell this material apart at all? ===")
                print(f"  {len(_sw2)} held-back windows | mean pairwise cosine distance {float(_off.mean()):.3f} "
                      f"(0 = every window has the same signature) | spread {float(_off.std()):.3f}")
                print(f"  effective dimensions {_pr:.1f} of {SIG_D} | distinct nearest-experts {_du} of "
                      f"{fab.n_live} live")
                print(f"  >> " + (
                    "DEGENERATE: the encoder maps this material to essentially ONE point, so there is one region "
                    "to route to. No routing rule can spread traffic across a blob -- the lever is the ENCODER "
                    "(ENC_CREG is 0.0) or the material, not ROUTE_T."
                    if float(_off.mean()) < 0.10 or _pr < 2.0 else
                    "SEPARABLE: the encoder does distinguish this material, so concentration of routing is the "
                    "ROUTER's doing rather than the representation's. ROUTE_T and DIV_W are then the levers."))
        except Exception as _e:
            print(f"[signature-space check skipped: {type(_e).__name__}: {_e}]")

    # === ARE THE EXPERTS GOOD AT ANYTHING? ====================================================================
    # The fabric block above reports node MASS -- how routing load is spread. Load is not competence. A population
    # can spread mass perfectly and have every node do the same undifferentiated job, which is precisely what
    # DIV_W=0 permits after BAL_WARM decays. What was never asked: does the material each node WINS get modelled
    # better by that node than by the population at large?
    # Answered against a null, because per-node bits/byte differences are mostly material difficulty: the same
    # windows are re-scored with the node assignment SHUFFLED. Excess over that shuffle is specialization; no
    # excess means the nodes are interchangeable however evenly the mass is spread.
    if FABRIC and fab is not None and not getattr(fab, "norm_only", False) and len(fab.bodies) > 1:
        try:
            _N = len(fab.bodies)
            _ew, _ex, _ey = [], [], []
            for _q in sorted(set(labels)):
                for _s0 in eval_win.get(_q, [])[:32]:
                    _ew.append(encwin(encpos(_s0)))
                    _ex.append(list(stream[_s0:_s0 + WIN])); _ey.append(list(stream[_s0 + 1:_s0 + WIN + 1]))
            if len(_ew) >= 8:
                with torch.no_grad():
                    _G = enc(torch.tensor(_ew, device=DEV))
                    _K = torch.cat([fab._ids(_N)[0], fab.halt_key[None]], 0)
                    _nb = fab.nov(torch.zeros(_G.size(0), 1, device=DEV))
                    _c = torch.softmax(((fab.q_entry(_G) + _nb) @ _K.t()) / max(1e-3, fab.route_t), -1)
                    _win = _c[:, :_N].argmax(-1)           # the node that takes this window at ENTRY
                    _X = torch.tensor(_ex, device=DEV); _Y = torch.tensor(_ey, device=DEV)
                    _pp = F.softmax(fab_logits(model, fab, model.encode(_X), _G), -1) \
                            .gather(-1, _Y.unsqueeze(-1)).squeeze(-1)
                    _den = (BLEN[_Y].sum(-1) if (USE_TOK and BLEN is not None) else
                            torch.full((_Y.size(0),), float(_Y.size(1)), device=DEV))
                    _bw = -(torch.log(_pp.clamp_min(1e-9)).sum(-1)) / math.log(2) / _den.clamp_min(1.0)
                _used = sorted(set(_win.tolist()))
                _per = {int(n): [float(_bw[i]) for i in range(len(_bw)) if int(_win[i]) == n] for n in _used}
                _tot = float(_bw.mean())
                # NULL: same windows, same per-node group SIZES, assignment shuffled. Run several times because a
                # single shuffle is itself noisy, and report the spread.
                _nulls = []
                _rr = random.Random(0)
                for _ in range(_i("EXPERT_NULLS", 20)):
                    _sh = _win.tolist(); _rr.shuffle(_sh)
                    _g = {}
                    for i, n in enumerate(_sh): _g.setdefault(n, []).append(float(_bw[i]))
                    _nulls.append(sum(abs(sum(v) / len(v) - _tot) for v in _g.values()) / len(_g))
                _spread = sum(abs(sum(v) / len(v) - _tot) for v in _per.values()) / len(_per)
                _nm = sum(_nulls) / len(_nulls)
                _nsd = (sum((x - _nm) ** 2 for x in _nulls) / max(1, len(_nulls) - 1)) ** 0.5
                print(f"\n=== EXPERTS: is the population SPECIALIZED, or just evenly loaded? ===")
                print(f"  {_N} nodes, {len(_used)} of them win at least one of {len(_bw)} held-back windows"
                      f" | population mean {_tot:.3f} bits/byte")
                for n in sorted(_per, key=lambda k: -len(_per[k]))[:8]:
                    _v = _per[n]
                    print(f"    node {n:<3} wins {len(_v):>4} windows ({100*len(_v)/len(_bw):4.1f}%) | "
                          f"{sum(_v)/len(_v):.3f} bits/byte on them ({sum(_v)/len(_v) - _tot:+.3f} vs population)")
                if len(_per) > 8: print(f"    ... and {len(_per)-8} more")
                print(f"  SPECIALIZATION (mean |node - population|)  {_spread:.3f}")
                print(f"  shuffled-assignment null                   {_nm:.3f} +/- {_nsd:.3f}")
                print(f"  >> " + ("SPECIALIZED: the material a node wins really is material it models differently."
                                  if _spread > _nm + 2 * _nsd else
                                  "INTERCHANGEABLE: nodes differ no more than a random split of the same windows "
                                  "would. Routing load is spread, competence is not -- see DIV_W (0.0 by default, "
                                  "and BAL_WARM decays the only other pressure to 0 by step 4000)."))
                print(f"  ({len(_used)} of {_N} nodes used: unused nodes are capacity the router never calls on.)")
                _lin = sorted(fab.births.values(), reverse=True)
                print(f"  SELECTION OUT: {getattr(fab,'removed',0)} culled total, of which "
                      f"{getattr(fab,'failed_out',0)} for SUSTAINED error (fast~=slow AND both above the "
                      f"population; a SPIKE is read as adaptation and protected, never culled) | "
                      f"{getattr(fab,'spared',0)} spared as load-bearing")
                print(f"  LINEAGE: {len(fab.births)} distinct parents in the recent-birth window | largest share "
                      f"{(100*_lin[0]/max(1,sum(_lin))) if _lin else 0:.0f}% (cap {100*fab.parent_max:.0f}%) "
                      f"-- one lineage wearing N hats is not N experts")
                print(f"  SPAWNED BY SPECIFICATION: {getattr(fab,'spawned',0)} expert(s) decoded into being from a "
                      f"router query nothing served (LM loss then trains q_route through what it asked for)")
                # MEASURED HERE, UNCONDITIONALLY. These were captured inside spawn_from -- which only runs when the
                # spawn bar is MET -- so the number meant to diagnose a collapse was recorded only on the path the
                # collapse prevents. It printed a stale 0.000 and read as "identities are identical" whether or not
                # they were. A diagnostic that depends on the thing it diagnoses is not a diagnostic.
                with torch.no_grad():
                    _Ki, _ = fab._ids(fab.n_live)
                    _Kin = F.normalize(_Ki, dim=-1)
                    _sub2 = _Kin if fab.n_live <= 512 else _Kin[torch.randperm(fab.n_live, device=_Kin.device)[:512]]
                    _Pi = 1 - _sub2 @ _sub2.t(); _Pi.fill_diagonal_(9e9)
                    _nn = _Pi.min(1).values
                    _off2 = _Pi[_Pi < 9e8]
                # WHAT THE ROUTER ACTUALLY SELECTED, over the whole run. "N of 4096 used" above is measured on 32
                # EVAL windows -- it answers "how many experts serve this small probe", not "how many did the
                # router ever choose". fab.use counts every window each expert won during TRAINING, which is the
                # question that was being asked and that nothing reported.
                _uv = sorted((v for v in fab.use.values() if v > 0), reverse=True)
                _ut = sum(_uv) or 1
                if not _uv:
                    print("  ROUTER SELECTION: no utilization recorded -- fab.use is empty. If this is a chaining "
                          "run that means selection ran blind (see below); otherwise it is a bug.")
                _c50 = 0; _acc = 0.0
                for _u in _uv:
                    _acc += _u; _c50 += 1
                    if _acc >= 0.5 * _ut: break
                if _uv:
                    print(f"  ROUTER SELECTION over the whole run: {len(_uv)} distinct experts won at least one "
                          f"window | top expert took {100*_uv[0]/_ut:.1f}% | half the traffic went to {_c50} expert(s)")
                print(f"    (the 'N of 4096 used' line above is 32 EVAL windows -- a probe, not the run. These two "
                      f"answer different questions and only this one says whether the router ever chose variety.)")
                # === GRADIENT REACH: how many experts LEARN per step? =========================================
                # Distinct from utilization. `use` says who WON a window at some point in the run; this says how
                # many experts were in the graph on a single step, i.e. how many were being trained at once.
                # It is the ceiling on differentiation speed and it does NOT grow with the population: selection
                # computes k per window, so the number is set by BATCH_W x k, not by how many experts exist.
                if _greach:
                    _gm = sum(_greach) / len(_greach)
                    print(f"  GRADIENT REACH: {_gm:.0f} of {fab.n_live} experts received a nonzero gradient on a "
                          f"typical step ({_gm/max(1,fab.n_live):.1%}), sampled {len(_greach)}x | "
                          f"min {min(_greach)} max {max(_greach)}")
                    print(f"    every other expert was FROZEN that step -- not merely unused. An expert outside "
                          f"the computed set gets no gradient, so it cannot improve into contention; that is what "
                          f"exploration (FAB_EXPLORE={fab.explore:.0%}) exists to break.")
                    _ee = fab.emb_every
                    print(f"    the high end is the identity channel: eemb reads the FULL weights of every live "
                          f"expert to build the routing keys, so the LM loss scatters gradient to ALL of them -- "
                          f"but it teaches 'be an expert routing can tell apart', not 'predict the text better'. "
                          + (f"FAB_EMB_EVERY={_ee} throttles that channel to 1 step in {_ee} AND routes on keys up "
                             f"to {_ee} steps stale." if _ee > 1 else
                             "FAB_EMB_EVERY=1: keys are recomputed every step, so the channel is never throttled "
                             "and the router never scores on stale weights."))
                # === WHICH ROUTER IS DECIDING? ===============================================================
                if fab._rmix:
                    _gs = sum(a for a, _ in fab._rmix) / len(fab._rmix)
                    _ws = sum(b for _, b in fab._rmix) / len(fab._rmix)
                    _tot2 = _gs + _ws
                    print(f"  ROUTING MIX over {len(fab._rmix)} samples: signature-region term spread {_gs:.3f} "
                          f"({_gs / max(1e-9, _tot2):.0%}) vs WEIGHT-PREDICTION term spread {_ws:.3f} "
                          f"({_ws / max(1e-9, _tot2):.0%})")
                    print(f"    the weight-prediction term IS this branch's premise: q_route emits a point in "
                          f"identity space, every expert's FULL WEIGHTS are embedded into the same space by eemb, "
                          f"and edec decodes the query into a real expert when nothing is near. The region term is "
                          f"the older signature router, summed on top. Only the SPREAD across experts decides "
                          f"anything (a constant shift cancels in the softmax), so these two numbers are the split.")
                    print(f"    EVERYTHING that reaches the expert ranking, so the mix above is not read as more "
                          f"exclusive than it is:")
                    print(f"      1. signature-region cosine    x{fab.region_w:g}   (0 = off)")
                    print(f"      2. weight prediction: q_route(signature) vs eemb(every expert's full weights)"
                          f"{'  [cosine/route_t]' if FAB_KEY_NORM else '  [RAW dot -- ~50x smaller, see above]'}")
                    print(f"      3. novelty: a per-window CONSTANT added to all N expert logits, so it cancels in "
                          f"the softmax and cannot change WHICH expert wins -- it only shifts experts against HALT")
                    print(f"      4. breadth-cap ban: a hard -inf mask on experts already serving >"
                          f"{fab.breadth:.0%} of domains {'[ON]' if SELF_ORG else '[off: SELF_ORG=0]'}")
                    print(f"      5. exploration: AFTER ranking, {fab.explore:.0%} of windows have one top-k slot "
                          f"replaced by a low-use expert outright")
                    if not SOCIETY:
                        print(f"      6. hops 2+ only -- the transition query is q_route(signature) + SRC[holder] "
                              f"+ novelty + control-summary, matched against the same weight embeddings. SRC is "
                              f"weight-derived; novelty and the control summary are NOT, and ROUTE_REGION_W does "
                              f"not touch them because the transition never had a region term.")
                    if _ws / max(1e-9, _tot2) < 0.2:
                        print(f"    >> the weight prediction is NOT driving routing -- the region term is. "
                              f"ROUTE_GROUNDED=0 to run on predicted weights alone.")
                    elif _gs / max(1e-9, _tot2) < 0.2:
                        print(f"    >> routing is essentially ALL weight-prediction; the region term is decoration. "
                              f"FAB_KEY_NORM={int(FAB_KEY_NORM)} -- at 0 that term is an UNBOUNDED raw dot against "
                              f"a bounded cosine, which is how it comes to dominate.")
                # === CAN THE CHAIN VARY ITS SECOND MOVE? =====================================================
                # H(hop1 | hop0) in bits. 0 = hop 1 is a fixed successor of hop 0, i.e. the chain makes ONE
                # decision and then follows a rail, however many hops it runs. This is the measurement that was
                # missing: the earlier attempt used I(domain; pair) vs I(domain; hop0), which saturates whenever
                # hop 0 already identifies the domain and so cannot distinguish "collapsed" from "correct".
                if fab._ord and not SOCIETY:      # on the society path forward() only runs in the report probe,
                    from collections import Counter as _Ct   # so this would report a 1-sample artifact as a finding
                    _h0 = [v for t, v in fab._ord if t == 0]; _h1 = [v for t, v in fab._ord if t == 1]
                    _pr = [(a, b) for r0, r1 in zip(_h0, _h1) for a, b in zip(r0, r1)]
                    if _pr:
                        _jt = _Ct(_pr); _m0 = _Ct(a for a, _ in _pr); _n2 = len(_pr)
                        _hc = -sum((c / _n2) * math.log2((c / _n2) / (_m0[a] / _n2)) for (a, _), c in _jt.items())
                        _succ = {}
                        for a, b in _pr: _succ.setdefault(a, set()).add(b)
                        _fixed = sum(1 for v in _succ.values() if len(v) == 1)
                        print(f"  CHAIN ORDER: H(hop1 | hop0) = {_hc:.3f} bits over {_n2} transitions | "
                              f"{len(_succ)} distinct hop-0 experts, {_fixed} of which ALWAYS hand to the same "
                              f"successor")
                        print(f"    0 bits = the chain makes ONE decision and then follows a rail: however many "
                              f"hops run, only the entry choice carries information. >0 = the second move genuinely "
                              f"depends on more than the first, which is what composition requires.")
                elif not SOCIETY:
                    print(f"  CHAIN ORDER: not measured -- fewer than 2 hops ran (depth_now={fab.depth_now}).")
                if _rseen:
                    _rdead = sorted(_rseen - _rlive)
                    print(f"  ROUTER LEARNING: trained this run -> {', '.join(sorted(_rlive)) or 'NOTHING'}")
                    print(f"    never gradiented -> {', '.join(_rdead) if _rdead else '(none)'}"
                          + ("  [edec is LM-dead BY DESIGN -- it is used at BIRTH, far too rarely to shape it, and "
                             "is trained by ae_loss instead]" if _rdead == ['edec'] else ""))
                    print(f"    a parameter that is allocated, optimized and decayed but never gradiented reads as "
                          f"a working subsystem everywhere else in this report. That is why it is printed.")
                print(f"  IDENTITY SPACE: {fab.n_live} experts | nearest-neighbour distance median "
                      f"{float(_nn.median()):.4f} (min {float(_nn.min()):.4f}) | mean pairwise "
                      f"{float(_off2.mean()):.4f}")
                print(f"  >> " + (
                    "COLLAPSED: every expert embeds to essentially the SAME identity, so the router has nothing to "
                    "discriminate on -- argmax lands arbitrarily on one node, specialization reads 0.000, and a "
                    "spawn can never fire because any query is 0 from 'the nearest'. Raise FAB_EMB_VAR."
                    if float(_nn.median()) < 0.01 else
                    "DISTINCT: experts occupy different points in identity space, so routing concentration (if any) "
                    "is a property of the ROUTER rather than of collapsed identities."))
                print(f"    spawn bar is {fab.spawn_mult:g}x that median = "
                      f"{max(fab.spawn_mult*float(_nn.median()), fab.spawn_floor):.4f}; last query sat "
                      f"{getattr(fab,'_spawn_gap',0):.4f} from its nearest identity")
                print(f"  DISCOVERY: {getattr(fab,'discovered',0)} signature(s) too far from every centroid were "
                      f"handed to the LEAST-USED expert (novelty > {FAB_DISCOVER:.2f} cosine) | "
                      f"{getattr(fab,'explored',0)} off-policy routings forced so unused experts got gradient | "
                      f"{getattr(fab,'crossed',0)} births assembled from MULTIPLE parents (rank-slice crossover)")
                print(f"  (top-{_i('FAB_CENT_TOPK', 8)} centroids move toward each signature they serve, weighted by "
                      f"share -- updating only the argmax winner is what made discovery impossible)")
                if fab.dom_of:
                    _lim = max(fab.breadth_min, int(fab.breadth * max(1, len(asm.cent))))
                    _br = sorted((len(v) for v in fab.dom_of.values()), reverse=True)
                    _at = sum(1 for v in _br if v >= _lim)
                    print(f"  BREADTH: an expert may serve <= {_lim} domains ({fab.breadth:.0%} of {len(asm.cent)}, "
                          f"floor {fab.breadth_min}). widest {_br[0] if _br else 0} | {_at} expert(s) at the cap | "
                          f"median {_br[len(_br)//2] if _br else 0}")
                    print(f"  (at the cap an expert is masked OUT of the routing softmax for domains it does not "
                          f"already serve, so breadth shapes the population rather than being reported after it.)")
                # WHAT PROTECTION ACTUALLY DID. A selection change that reports nothing is a change nobody can
                # audit, and this one deliberately keeps units that the utilization ranking wanted dead.
                _spd = getattr(asm, "protected", 0) + getattr(router, "spared", 0) if EXPERTS else getattr(asm, "protected", 0)
                print(f"  COMPETENCE PROTECTION [{'on' if COMP_PROTECT else 'OFF (pure-utilization ablation)'}]: "
                      f"spared {_spd} unit(s) that utilization ranked for culling but that model their own material "
                      f"better than the population (COMP_PROTECT=0 to compare).")
                # === IS THE POPULATION SUFFICIENT WHERE NO MEMBER IS? =============================================
                # The design claim is that no expert suffices alone but together they do. That is a claim about
                # OUTCOMES, so measure it on the outcome: the ensemble's bits/byte against the best that any
                # SINGLE expert manages on the same windows. If the best member matches the population, the
                # population is not buying anything and the selective story has a hole in it whatever the
                # culling does.
                try:
                    with torch.no_grad():
                        _Xs = torch.tensor(_ex, device=DEV); _Ys = torch.tensor(_ey, device=DEV)
                        _hs = model.encode(_Xs)
                        _ws, _Os, _os = fab.society(_hs, _G, torch.zeros(_Xs.size(0), device=DEV),
                                                    k=max(ENS_K, 2), learn_regions=False)
                        _kn = min(ENS_K, _Os.size(1))
                        _wk2 = _ws.gather(1, _os[:, :_kn])
                        _wk2 = _wk2 / _wk2.sum(-1, keepdim=True).clamp_min(1e-9)
                        _heads = [model.head(fab.norm(_Os[:, j])) for j in range(_kn)]
                        _lgp = sum(_heads[j] * _wk2[:, j][:, None, None] for j in range(_kn))
                        _den2 = (BLEN[_Ys].sum() if (USE_TOK and BLEN is not None) else float(_Ys.numel()))
                        def _bpb2(_l):
                            return float(F.cross_entropy(_l.reshape(-1, V), _Ys.reshape(-1), reduction="sum")
                                         / math.log(2) / max(1.0, float(_den2)))
                        # _os is (B,kk) since routing went PER WINDOW: `int(_os[j])` was int() of a whole row and
                        # threw ValueError every run, so this entire section has been silently swallowed by the
                        # except below ever since -- the one measurement that asks whether the population beats its
                        # own best member has not printed once. Rank slot j is now labelled by its MODAL holder,
                        # the same attribution the marginal-contribution loop uses.
                        _pop = _bpb2(_lgp)
                        _solo = [(_bpb2(_heads[j]), int(torch.mode(_os[:, j]).values)) for j in range(len(_heads))]
                        _best, _bid = min(_solo)
                        # The comparison above is EXPERTS ONLY, deliberately -- mixing the base head into it would
                        # confound "the population aggregates" with "the base model is good". This is what the
                        # router actually emitted on the same windows, HALT included.
                        _fullb = _bpb2(halt_blend(model, fab, _hs, _lgp)) if fab.halt_on else None
                    print(f"\n=== SUFFICIENCY: does the POPULATION beat its best single member? ===")
                    print(f"  population ({len(_heads)} experts blended) {_pop:.3f} bits/byte | "
                          f"best single rank-slot (modal holder node {_bid}) {_best:.3f} | "
                          f"population buys {_best - _pop:+.3f}")
                    print(f"   (a 'rank slot' is one expert per window -- each window's own k-th choice -- since "
                          f"routing is per window. That is a STRONGER baseline than one fixed expert for everything.)")
                    if _fullb is not None:
                        print(f"  as the router actually emitted it (HALT mass spent on the base head): {_fullb:.3f} "
                              f"bits/byte | HALT changes the answer by {_fullb - _pop:+.3f} vs experts alone")
                    print(f"  >> " + ("AGGREGATE: no member is sufficient alone, together they are -- which is the "
                                      "design claim, measured on the outcome rather than assumed."
                                      if _best - _pop > 0.02 else
                                      "NOT AGGREGATE: the best single expert does as well as the whole blend, so the "
                                      "population is redundant here. Expect this while the nodes are interchangeable."))
                except Exception as _e:
                    print(f"[sufficiency check skipped: {type(_e).__name__}: {_e}]")
                if fab.contrib:
                    _pos = [n for n, v in fab.contrib.items() if v > 0]
                    print(f"  marginal contribution measured for {len(fab.contrib)} nodes; {len(_pos)} are "
                          f"LOAD-BEARING (system worse without them). Selection protects these regardless of how "
                          f"rarely they are called.")
                if asm.comp_glob is not None and asm.comp:
                    _bet = [d for d, v in asm.comp.items() if v < asm.comp_glob]
                    print(f"  {len(_bet)} of {len(asm.comp)} live domains beat the population EMA "
                          f"({asm.comp_glob:.3f} bits/window) on their own material.")
        except Exception as _e:
            import traceback as _tb
            print(f"[expert specialization check skipped: {type(_e).__name__}: {_e}]")
            print("  " + _tb.format_exc().strip().replace("\n", "\n  "))
            #   THE TRACEBACK, not just the message. This except swallowed an AttributeError on fab.keys -- a stale
            #   reference left by the tensor refactor -- and the whole EXPERTS and SUFFICIENCY output vanished from
            #   the report with no indication it had ever been attempted. A bare message would not have located it.

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
        # WHICH MODEL THIS IS. The samples below come from the LIVE model at the END of training. In every arm of
        # every seed so far that is 1.1-1.3 bits/byte worse than the model that existed around step 6000, so the
        # text being judged is the degraded one. Say so, and say where the good one went.
        if BEST_TRACK and _best_bpb[0] is not None:
            _fin = None
            _lastc = [b for st, _p, b, _a in _CURVE if st == max(st2 for st2, _, _, _ in _CURVE)]
            if _lastc: _fin = sum(_lastc) / len(_lastc)
            # SAY "not saved" WHEN IT WAS NOT SAVED. This printed "saved to None.best" on a run with SAVE_CKPT
            # off, because _save_ckpt returned early without saying so and the caller assumed success.
            # the REAL last step, not the projection. This said "step ~81840" on a run that ended at ~48800,
            # because _total_steps was measured at the seed vocabulary and minted tokens made every later epoch
            # shorter. `step` is the number the loop actually stopped on.
            print(f"  SAMPLED FROM: the FINAL model, step {step}"
                  + (f" ({_fin:.3f} held-out bits/byte)" if _fin else "")
                  + f" -- NOT the best. Best was {_best_bpb[0]:.3f} at step {_best_bpb[1]}"
                  + (f", saved to {_env('SAVE_CKPT', '')}.best" if _best_bpb[2] else " (not saved: SAVE_CKPT is off)")
                  + (f". The final model is {_fin - _best_bpb[0]:+.3f} bits/byte worse than it; read the text below "
                     f"as the END of the run, not its best." if _fin else "."))
            if _best_bpb[2]:
                print(f"  to sample the BEST model instead:  python3 prompt.py CKPT={_env('SAVE_CKPT', '')}.best")
        # MORE THAN ONE SAMPLE PER PROCESS. GEN_PROCS caps how many DOMAINS get sampled, and this project runs ONE
        # corpus, so every text judgement in it has rested on a SINGLE 200-token continuation. The composing check
        # below is the clearest cost: it scored "% of generated words that appear in the training text" on 64-91
        # words, so 91% and 71% were three or four words apart and the difference between them was not resolvable.
        # GEN_N draws several DISTINCT seed passages per process -- random.sample, not repeated random.choice, so
        # the same passage cannot be drawn twice and the samples are not secretly correlated.
        # Cost: GEN_N x 2 x GEN_LEN single-token forwards (4 x 2 x 200 = 1600), seconds, once, after training.
        _gn = max(1, _i("GEN_N", 4))
        for p in sorted(set(labels))[:_i("GEN_PROCS", 4)]:
            starts = [s for s in range(0, len(stream) - (WIN + 1), WIN) if labels[s] == p]
            if not starts: continue
            _vl = TOK.vocab_size if USE_TOK else None
            _nsamp = min(_gn, len(starts))
            for _si, s0 in enumerate(random.sample(starts, _nsamp)):
                seed = list(stream[s0:s0 + WIN])
                _gg = None
                if FABRIC:                                 # generation must run the SAME path the model trained with
                    with torch.no_grad():
                        _b0 = encpos(s0)
                        _gg = enc(torch.tensor([encwin(_b0)], device=DEV))
                gno = generate(model, mem, seed, _i("GEN_LEN", 200), False, DEV, temp=_f("GEN_TEMP", 0.7), vlim=_vl, fab=fab, gist=_gg)
                gme = generate(model, mem, seed, _i("GEN_LEN", 200), True, DEV, temp=_f("GEN_TEMP", 0.7), vlim=_vl, fab=fab, gist=_gg)
                print(f"\n-- process {p} | sample {_si + 1}/{_nsamp} | seed ...{_dec(seed[-44:])}")
                print(f"   MODEL ONLY: {_dec(gno)}")
                print(f"   MODEL+MEM : {_dec(gme)}")
                _gen_keep.append((p, seed, gno, gme))
        # === IS IT COMPOSING WORDS, OR EMITTING MEMORISED CHUNKS? ================================================
        # Word-shaped output at 2 bits/byte invites a fair objection: a tokenizer that minted whole words would let
        # the model emit one token and look like it had spelled something. That is a measurable difference, not an
        # argument. TOKENS PER WORD > 1 means the model chose a SEQUENCE of pieces and the spelling is its doing;
        # ~1.0 would mean the vocabulary is doing the work. Reported next to how many generated words actually
        # exist in the training text, which separates composition from recall.
        try:
            if _gen_keep and USE_TOK:
                _bpt2 = sum(TOK.bytes_per_id[:TOK.vocab_size]) / max(1, TOK.vocab_size)
                _voc = set()
                for _c2 in CORP[:1]:
                    _voc = set(bytes(_c2[:4_000_000]).decode("utf-8", "replace").split())
                _gw = []
                for _p3, _sd3, _a3, _b3 in _gen_keep:
                    _t3 = TOK.decode(_a3)
                    _gw += (_t3 if isinstance(_t3, str) else bytes(_t3).decode("utf-8", "replace")).split()
                if _gw:
                    _real = sum(1 for w in _gw if w.strip(".,;:!?()'\"") in _voc)
                    _tpw = sum(len(TOK.segment(w.encode(), count=False)) for w in _gw[:400]) / max(1, len(_gw[:400]))
                    print(f"\n=== IS IT COMPOSING? (generated text vs the vocabulary it had) ===")
                    print(f"  vocabulary {TOK.vocab_size} tokens, mean {_bpt2:.2f} bytes each | "
                          f"{len(_gw)} generated words")
                    print(f"  TOKENS PER GENERATED WORD {_tpw:.2f}  -> " +
                          ("the model is SPELLING: each word is a sequence it chose, not one unit it looked up"
                           if _tpw > 1.5 else
                           "close to one token per word -- the VOCABULARY is doing the spelling, not the model"))
                    print(f"  {100*_real/len(_gw):.0f}% of generated words appear in the training text "
                          f"({_real}/{len(_gw)}) -- the rest are word-SHAPED but novel, which is the interesting half")
        except Exception as _e:
            print(f"[composition check skipped: {type(_e).__name__}: {_e}]")

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
            # WHICH CENTROIDS? With >= 2 spliced corpora, the true-corpus centroids are the stricter reference:
            # they are OURS, so agreeing with them cannot be self-confirming. On a SINGLE corpus there are no
            # true-corpus centroids to use and this section used to skip itself entirely -- which is exactly the
            # configuration an English-only run has, and it would have removed the one metric that speaks to
            # "is this proper language". Fall back to the SELF-ASSEMBLED domains: does a continuation stay in the
            # domain the system itself put its seed in? That is a weaker claim (the partition being scored is the
            # system's own) and it is labelled as such, but it is a real question and it is the only one available
            # when nothing was spliced.
            _self_ref = False
            if _gen_keep and SIG_MODE == "learned":
                _cent = {}
                for _p in sorted(set(labels)):             # true-corpus centroids from REAL data, not from domains
                    _st = [s for s in range(0, len(stream) - WIN - 1, WIN) if labels[s] == _p]
                    if len(_st) < 8: continue
                    random.shuffle(_st)
                    _bs = [encpos(s) for s in _st[:64]]
                    with torch.no_grad():
                        _Z = enc(torch.tensor([encwin(b) for b in _bs], device=DEV))
                    if _Z.numel(): _cent[_p] = F.normalize(_Z.mean(0), dim=0)
                if len(_cent) < 2 and asm is not None and len(asm.cent) > 1:
                    _self_ref = True                        # single corpus -> score against what the system assembled
                    _cent = {int(k): F.normalize(v.to(DEV), dim=0) for k, v in asm.cent.items()}
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
                    # MEASURED ON ITS OWN SAMPLE, NOT ON THE FOUR PRINTED ONES. The printed generations exist to be
                    # read by eye; scoring them made coherence a mean over GEN_PROCS=4 samples of a ~200-token
                    # continuation, which at WIN=256 and stride WIN//2 is about TWO windows each. Every coherence
                    # number this project ever printed landed exactly on 0.25/0.50/0.75/1.00 -- the signature of a
                    # four-sample mean -- and its standard error there is 0.25. "memory HELPS (0.50 -> 0.75)" and
                    # "the fabric buys coherence (0.75 vs 0.50)" are both ONE SAMPLE flipping. They were reported as
                    # findings, including by me, twice, in opposite directions on consecutive runs.
                    # COH_N seeds x COH_LEN tokens instead: ~10x the decisions, and the standard error is PRINTED so
                    # a difference inside it cannot be read as a result.
                    _cn, _cl = _i("COH_N", 16), _i("COH_LEN", 384)
                    _rn, _rm, _rr = [], [], []
                    # Seeds: one per corpus in rotation when corpora were spliced; anywhere in the stream when
                    # they were not. HOME is what the continuation is asked to stay in -- the seed's corpus in the
                    # spliced case, and the self-assembled domain the seed actually lands in otherwise. The second
                    # has to be MEASURED per seed (encode it, take the nearest centroid) rather than looked up,
                    # because on one corpus there is no label to look up.
                    _cps = [p for p in sorted(set(labels)) if p in _cent]
                    _allst = [s for s in range(0, len(stream) - (WIN + 1), WIN)]
                    for _k in range(_cn):
                        if _self_ref:
                            if not _allst: continue
                            _s0 = random.choice(_allst)
                        else:
                            if not _cps: continue
                            _p = _cps[_k % len(_cps)]
                            _sts = [s for s in range(0, len(stream) - (WIN + 1), WIN) if labels[s] == _p]
                            if not _sts: continue
                            _s0 = random.choice(_sts)
                        _sd2 = list(stream[_s0:_s0 + WIN])
                        _g2 = None
                        if FABRIC or _self_ref:
                            with torch.no_grad(): _g2 = enc(torch.tensor([encwin(encpos(_s0))], device=DEV))
                        if _self_ref:
                            _p = int(_ks[int((_C @ _g2[0]).argmax())])   # the domain the system put this seed in
                        if not FABRIC: _g2 = None
                        for _acc, _um in ((_rn, False), (_rm, True)):
                            _v = _stay(generate(model, mem, _sd2, _cl, _um, DEV, temp=_f("GEN_TEMP", 0.7),
                                                vlim=(TOK.vocab_size if USE_TOK else None), fab=fab, gist=_g2), _p)
                            if _v is not None: _acc.append(_v)
                        _v = _stay(list(stream[_s0:_s0 + _cl]), _p)   # CEILING: real text, same length, same measure
                        if _v is not None: _rr.append(_v)
                    def _msd(a):                           # mean and STANDARD ERROR OF THE MEAN -- the resolution
                        _m = sum(a) / len(a)               #   of the number, which is what was missing
                        _v = sum((x - _m) ** 2 for x in a) / max(1, len(a) - 1)
                        return _m, (_v / len(a)) ** 0.5
                    if _rn and _rm:
                        (_mn, _en), (_mm, _em) = _msd(_rn), _msd(_rm)
                        _ceil = sum(_rr) / len(_rr) if _rr else float("nan")
                        _floor = 1.0 / len(_cent)
                        _d = _mm - _mn; _ed = (_en ** 2 + _em ** 2) ** 0.5
                        print(f"\n=== COHERENCE: does a continuation STAY in the domain of its seed?"
                              + (" [SELF-ASSEMBLED reference] ===" if _self_ref else " ===")) 
                        if _self_ref:
                            print(f"  reference = the {len(_cent)} domains the SYSTEM assembled, not corpora we spliced in."
                                  f" Weaker evidence: the partition being scored is the system's own, so a tidy score"
                                  f" could mean the encoder is self-consistent rather than that the text is coherent."
                                  f" Read the GENERATION samples above alongside it.")
                        print(f"  model ALONE {_mn:.2f} +/- {_en:.2f}  |  model+MEMORY {_mm:.2f} +/- {_em:.2f}  |  "
                              f"REAL text (ceiling) {_ceil:.2f}  |  chance (floor) {_floor:.2f}")
                        print(f"  >> fraction of generated windows whose nearest "
                              + ("self-assembled domain" if _self_ref else "true-corpus")
                              + f" centroid is the SEED's,"
                              f" over {len(_rn)} continuations of {_cl} tokens (COH_N/COH_LEN).")
                        _best = max(_mn, _mm)
                        print(f"  >> {'ON-TOPIC -- close to what real text of this corpus scores' if _best >= _ceil - 0.15 else ('PARTIAL -- better than chance but wanders well before real text does' if _best > _floor + 0.10 else 'INCOHERENT -- indistinguishable from ignoring the seed entirely')}"
                              f"; memory {'HELPS' if _d > 2 * _ed else ('HURTS' if -_d > 2 * _ed else 'is NEUTRAL')} here"
                              f" ({_d:+.2f} +/- {_ed:.2f}"
                              + ("" if abs(_d) > 2 * _ed else "; inside the noise -- do not read this as a result") + ").")
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
    _config_audit()
    print("\n(SIG_MODE={} -- learned = the unfrozen product path; deltas + purity + locality are what matter.)".format(SIG_MODE))


if __name__ == "__main__":
    main()
