"""Message the trained model and see what it continues.

First save a checkpoint from a run:
    ... SAVE_CKPT=runs/ck TOKENIZER=1 ... python3 self_organize.py     # trains, then writes runs/ck/ckpt.pt

Then prompt it:
    python3 prompt.py CKPT=runs/ck                 # interactive: type a message, get a continuation
    MEM=1 python3 prompt.py CKPT=runs/ck            # blend the editable memory into the continuation
    PROMPT="def add(a, b):" python3 prompt.py CKPT=runs/ck   # single-shot (no stdin), prints once

Knobs: DEVICE, GEN_LEN (default 200), GEN_TEMP (default 0.6), MEM (0/1), TOPK.
The model is a small byte/token-level GRU trained on the stream -- expect domain-appropriate, semi-coherent text, not a chatbot.
"""
import os
import sys
import torch
import torch.nn as nn
import torch.nn.functional as F

for _a in sys.argv[1:]:                       # accept KEY=VALUE on the command line too (docs showed `prompt.py CKPT=...`,
    if "=" in _a and not _a.startswith("="):  # but only env vars were read -> silent fallback to the default checkpoint)
        _k, _v = _a.split("=", 1); os.environ[_k] = _v

DEV = os.environ.get("DEVICE", "cpu")
CK = os.environ.get("CKPT", "runs/ck")
d = torch.load(f"{CK}/ckpt.pt", map_location=DEV)
D, V, KW, KEY_SRC = d["D"], d["V"], d["KW"], d["KEY_SRC"]
MT = d.get("model_type", "gru"); LAYERS = d.get("layers", 1); HEADS = d.get("heads", 8); MAXLEN = d.get("maxlen", 512)


# THE MODEL CLASSES ARE IMPORTED, NOT REIMPLEMENTED. prompt.py used to define its own MiniLM, TinyTransformer,
# SigEncoder and Fabric. The Fabric copy went stale when the population became tensors and this file -- the tool
# GENERATIONS are read with, i.e. the deliverable -- died silently for several commits. The other three had not
# drifted yet, which is luck rather than safety. One definition, in the file that trains them.
# The env is set from the CHECKPOINT before importing, because self_organize sizes its models from module globals.
import os as _os
_os.environ.update(D_MODEL=str(D), VMAX=str(V), MODEL=MT, LAYERS=str(LAYERS), HEADS=str(HEADS), MAXLEN=str(MAXLEN))
for _k, _v in (("DATA_MODE", "real"), ("DATA_DIR", "data"), ("DOMAINS", "eng"), ("STREAM_LEN", "20000"),
               ("TOKENIZER", "0"), ("ENC_WARMUP", "0"), ("WORLD_MODEL", "0"), ("FABRIC", "0"), ("EXPERTS", "0")):
    _os.environ.setdefault(_k, _v)
_os.environ["BENCH"] = "1"
_FC = d.get("fab_cfg")
if _FC:                                                # size the preallocated population to the checkpoint's
    _os.environ["FAB_NMAX"] = str(int(_FC.get("cap", _FC.get("n", 4096))))
    _os.environ["FAB_RANK"] = str(int(_FC.get("rank", 8)))
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from self_organize import build_lm, Fabric, SigEncoder, fab_logits

model = build_lm(nv=V).to(DEV)                        # same constructor the trainer used, checkpoint's vocab
model.load_state_dict(d["model"]); model.eval()

# ---- ROUTER FABRIC (the model was TRAINED with it; running without it gives the crippled path) ----
FAB_CFG = d.get("fab_cfg"); SIG_D = d.get("sig_d"); WIN = d.get("win", 96)
FAB_SOC = bool(FAB_CFG.get("society", True)) if FAB_CFG else False
ENS_K = int(FAB_CFG.get("ens_k", 2)) if FAB_CFG else 2





WCFG = d.get("world_cfg"); WENC = WFWD = WPROJ = None
if WCFG and d.get("world_enc") is not None:
    from world_model import WorldEncoder, DynamicsPopulation
    WENC = WorldEncoder(D, WCFG["lat"], WCFG["hid"]).to(DEV); WENC.load_state_dict(d["world_enc"]); WENC.eval()
    WFWD = DynamicsPopulation(WCFG["lat"], WCFG["n"], WCFG["nmax"], WCFG["hid"], WCFG["route"]).to(DEV)
    WFWD.load_state_dict(d["world_fwd"]); WFWD.eval()
    if WCFG.get("feedback") and d.get("world_proj") is not None:
        WPROJ = nn.Linear(WCFG["lat"], D).to(DEV); WPROJ.load_state_dict(d["world_proj"]); WPROJ.eval()


def _world_h(x, h):
    """Same conditioning the training loop applies, in the same place (before fabric/head)."""
    if WPROJ is None: return h
    z = WENC(model.emb(x))
    pred = WFWD(z.reshape(-1, WCFG["lat"]))[0].reshape(x.size(0), x.size(1), WCFG["lat"])
    return h + WPROJ(pred)


# ---- RETRIEVAL GROUNDING: memory entries point back at real source text ----
import os.path as _op
MPOS = d.get("mem_pos"); SRC = None
_sp = _op.join(CK, "source.bin")
if MPOS is not None and _op.exists(_sp):
    SRC = open(_sp, "rb").read()


@torch.no_grad()
def _recall(msg, k=3, span=220):
    """INTERNAL: find what the system has read that relates to this message. The passages are NEVER shown -- they are
    used to CONDITION generation, so the model speaks in its own words about relevant material. Retrieval is a
    component of the system, not a substitute for it."""
    if SRC is None or not USE_MEM:
        return []
    ids = encode(msg)[-KW:] or [10]
    ids = [10] * (KW - len(ids)) + ids if len(ids) < KW else ids
    q = F.normalize(model(torch.tensor([ids], device=DEV))[1][:, -1], dim=-1)
    sim = (q @ MK.t())[0]
    seen, out = set(), []
    for i in sim.topk(min(400, sim.numel())).indices.tolist():
        p = int(MPOS[i])
        b = max(0, p - span // 3); key = b // span
        if key in seen: continue                            # de-duplicate overlapping hits
        seen.add(key)
        txt = SRC[b:b + span].decode("utf-8", "replace").replace("\n", " ")
        out.append((float(sim[i]), txt.strip()))
        if len(out) >= k: break
    return out


FAB = ENC = None
if FAB_CFG and d.get("fab") is not None:
    FAB = Fabric(D, SIG_D, FAB_CFG["dk"], max(1, int(FAB_CFG["n"])), FAB_CFG["alpha"], FAB_CFG["max_steps"],
                 FAB_CFG.get("hid_mult", 2), FAB_CFG.get("min_steps", 0), FAB_CFG.get("norm_only", False)).to(DEV)
    FAB.n_live = int(FAB_CFG["n"])                     # rows exist already; only the LIVE count is checkpoint state
    # honour the ROUTING MODE the checkpoint was trained with, rather than assuming one
    FAB.grounded = bool(FAB_CFG.get("grounded", True))
    FAB.route_t = float(FAB_CFG.get("route_t", 0.1))
    FAB.route_learn = bool(FAB_CFG.get("route_learn", True))
    FAB.load_state_dict(d["fab"]); FAB.eval()          # loads `cent` too, now that it is a registered buffer
    ENC = SigEncoder(D, SIG_D, nv=d["enc"]["emb.weight"].size(0)).to(DEV); ENC.load_state_dict(d["enc"]); ENC.eval()

# ---- tokenizer (or raw bytes) ----
if d["use_tok"]:
    from tokenizer import DynamicTokenizer
    TOK = DynamicTokenizer.load(d["tok_path"])
    def encode(t): return TOK.segment(t.encode("utf-8", "replace"), count=False)
    def decode(ids): return TOK.decode(ids)
    vocab_note = f"expanding tokenizer, vocab {V}"
    VLIM = TOK.vocab_size
else:
    def encode(t): return list(t.encode("utf-8", "replace"))
    def decode(ids): return bytes(ids).decode("utf-8", "replace")
    vocab_note = "byte-level (vocab 256)"
    VLIM = None

# ---- optional editable memory ----
USE_MEM = bool(int(os.environ.get("MEM", "0")))
TOPK = int(os.environ.get("TOPK", d.get("topk", 8)))
if USE_MEM:
    MK = F.normalize(d["mem_keys"].to(DEV), dim=-1); MT = d["mem_tok"].to(DEV)
    @torch.no_grad()
    def mem_dist(seq):
        win = torch.tensor([seq[-KW:]], device=DEV)
        q = F.normalize(model(win)[1][:, -1], dim=-1)              # model-key of the last KW units
        sim = (q @ MK.t())[0]
        tv, ti = sim.topk(min(TOPK, MK.size(0)))
        w = torch.softmax(tv / 0.1, -1)
        dist = torch.zeros(V, device=DEV); dist.scatter_add_(0, MT[ti], w)
        return dist
    mem_note = f" + memory ({MK.size(0)} entries)"
else:
    mem_note = ""


GEN_LEN = int(os.environ.get("GEN_LEN", 200)); GEN_TEMP = float(os.environ.get("GEN_TEMP", 0.6))
REP_PEN = float(os.environ.get("REP_PENALTY", 1.0)); REP_WIN = int(os.environ.get("REP_WINDOW", 64))   # >1 discourages recent tokens


GIST = None


@torch.no_grad()
def _gist_of(text):                                                 # route by the DOMAIN SIGNATURE of the message
    if ENC is None: return None
    b = list(text.encode("utf-8", "replace"))[-WIN:] or [10]
    b = ([10] * (WIN - len(b)) + b) if len(b) < WIN else b
    return ENC(torch.tensor([b], device=DEV))


@torch.no_grad()
def generate(seed, n, temp):
    seq = list(seed)
    if not seq: seq = [10]                                          # avoid empty context
    for _ in range(n):
        x = torch.tensor([seq[-256:]], device=DEV)
        _h = _world_h(x, model.encode(x))                           # world-model forecast conditions h (as in training)
        if FAB is not None and GIST is not None and FAB_SOC:
            # ENSEMBLE AT THE OUTPUT, exactly as training does: logits are a routing-weighted sum of each expert's
            # OWN head output. Blending hidden states instead produces a representation no expert was trained to
            # emit. society() now returns (w, O, idx) and computes only the top-k, matching self_organize.
            # ONE path, imported. This block used to reimplement the ensemble -- and when routing became
            # per-WINDOW (idx is (B,k) now, not (k,)) the copy kept the batch-level `_w[:, _oid]` and broke.
            # That is the same failure as the duplicated Fabric class, one level down: importing the CLASSES is
            # not enough while the LOGIC that uses them is still copied. fab_logits is the path the trainer uses.
            _n0 = torch.zeros(_h.size(0), device=DEV)
            logits = fab_logits(model, FAB, _h, GIST, _n0, k=ENS_K)[0, -1]
        else:
            if FAB is not None and GIST is not None:
                _h = FAB(_h, GIST, torch.zeros(1, device=DEV))
            logits = model.head(_h)[0, -1]
        if VLIM is not None and VLIM < logits.numel(): logits = logits.clone(); logits[VLIM:] = float('-inf')
        if REP_PEN != 1.0:                                          # repetition penalty on recently-used tokens (anti-degeneracy)
            for t in set(seq[-REP_WIN:]):
                logits[t] = logits[t] / REP_PEN if logits[t] > 0 else logits[t] * REP_PEN
        pm = F.softmax(logits / max(1e-3, temp), -1)
        if USE_MEM:
            dm = mem_dist(seq); hp = dm.sum().clamp(max=1.0)
            p = (1 - 0.5 * hp) * pm + 0.5 * hp * dm
            p = p / p.sum().clamp_min(1e-9)
        else:
            p = pm
        seq.append(int(torch.multinomial(p, 1)))
    return decode(seq[len(seed):])
fab_note = f" + fabric ({FAB_CFG['n']} nodes)" if FAB is not None else ""
print(f"[loaded {CK} | {vocab_note}{mem_note}{fab_note} | GEN_LEN={GEN_LEN} GEN_TEMP={GEN_TEMP}]")

GROUND = bool(int(os.environ.get("GROUND", "0")))          # GROUND=1 -> recall relevant material INTERNALLY and
                                                           #   condition generation on it (passages never shown)


@torch.no_grad()
def respond(msg):
    """The model's reply. With GROUND=1 the system first recalls what it has read that bears on the message and
    silently conditions on it; the reply is still the model's own generated language."""
    GIST_ = _gist_of(msg)
    globals()["GIST"] = GIST_
    seed = encode(msg)
    if GROUND and SRC is not None:
        hits = _recall(msg, k=int(os.environ.get("GROUND_K", 2)))
        if hits:                                            # prime the context with recalled material, then the message
            prime = " ".join(t for _, t in hits)[-int(os.environ.get("GROUND_CHARS", 400)):]
            seed = encode(prime + "\n" + msg)
    return generate(seed, GEN_LEN, GEN_TEMP)
one_shot = os.environ.get("PROMPT")
if one_shot is not None:
    print(f"you> {one_shot}")
    GIST = _gist_of(one_shot)
    print(f"model> {respond(one_shot)}")
else:
    print("Type a message; the model continues it. Ctrl-C or empty line + Ctrl-D to quit.\n")
    while True:
        try:
            msg = input("you> ")
        except (EOFError, KeyboardInterrupt):
            print(); break
        if not msg.strip():
            continue
        GIST = _gist_of(msg)
        print(f"model> {respond(msg)}\n")
