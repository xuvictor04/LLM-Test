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
import torch
import torch.nn as nn
import torch.nn.functional as F

DEV = os.environ.get("DEVICE", "cpu")
CK = os.environ.get("CKPT", "runs/ck")
d = torch.load(f"{CK}/ckpt.pt", map_location=DEV)
D, V, KW, KEY_SRC = d["D"], d["V"], d["KW"], d["KEY_SRC"]
MT = d.get("model_type", "gru"); LAYERS = d.get("layers", 1); HEADS = d.get("heads", 8); MAXLEN = d.get("maxlen", 512)


class MiniLM(nn.Module):
    def __init__(s):
        super().__init__(); s.emb = nn.Embedding(V, D); s.gru = nn.GRU(D, D, num_layers=LAYERS, batch_first=True); s.head = nn.Linear(D, V)
    def encode(s, x): h, _ = s.gru(s.emb(x)); return h
    def forward(s, x): h = s.encode(x); return s.head(h), h


class TinyTransformer(nn.Module):
    def __init__(s):
        super().__init__(); s.emb = nn.Embedding(V, D); s.pos = nn.Embedding(MAXLEN, D); s.maxlen = MAXLEN
        lyr = nn.TransformerEncoderLayer(D, HEADS, dim_feedforward=4 * D, batch_first=True, dropout=0.0, activation="gelu", norm_first=True)
        s.tr = nn.TransformerEncoder(lyr, LAYERS, enable_nested_tensor=False); s.head = nn.Linear(D, V)
    def encode(s, x):
        L = x.size(1); p = torch.arange(L, device=x.device).clamp(max=s.maxlen - 1)
        h = s.emb(x) + s.pos(p); m = torch.triu(torch.ones(L, L, device=x.device), 1).bool()
        return s.tr(h, mask=m)
    def forward(s, x): h = s.encode(x); return s.head(h), h


model = (TinyTransformer() if MT == "transformer" else MiniLM()).to(DEV)
model.load_state_dict(d["model"]); model.eval()

# ---- ROUTER FABRIC (the model was TRAINED with it; running without it gives the crippled path) ----
FAB_CFG = d.get("fab_cfg"); SIG_D = d.get("sig_d"); WIN = d.get("win", 96)
FAB_SOC = bool(FAB_CFG.get("society", True)) if FAB_CFG else False


class SigEncoder(nn.Module):
    def __init__(s, dd, sd):
        super().__init__(); s.emb = nn.Embedding(V, dd); s.gru = nn.GRU(dd, dd, batch_first=True); s.proj = nn.Linear(dd, sd)
    def forward(s, x): h, _ = s.gru(s.emb(x)); return F.normalize(s.proj(h[:, -1]), dim=-1)


class FabricNode(nn.Module):
    def __init__(s, dd, hid):
        super().__init__(); s.net = nn.Sequential(nn.Linear(dd, hid), nn.GELU(), nn.Linear(hid, dd))
    def forward(s, x): return x + s.net(x)


class Fabric(nn.Module):
    def __init__(s, dd, sig_d, dk, n, alpha, max_steps, hid_mult, min_steps, norm_only):
        super().__init__()
        s.d, s.dk, s.alpha, s.max_steps, s.hid = dd, dk, alpha, max_steps, hid_mult * dd
        s.min_steps, s.norm_only = min_steps, norm_only
        s.bodies = nn.ModuleList([FabricNode(dd, s.hid) for _ in range(n)])
        s.keys = nn.ParameterList([nn.Parameter(torch.randn(dk) * 0.1) for _ in range(n)])
        s.qproj = nn.ModuleList([nn.Linear(sig_d, dk) for _ in range(n)])
        s.halt_key = nn.Parameter(torch.randn(dk) * 0.1)
        s.q_entry = nn.Linear(sig_d, dk); s.nov = nn.Linear(1, dk); s.ctrl = nn.Linear(3, dk)
        s.norm = nn.LayerNorm(dd)
    def society(s, h, gist, nov):                          # independent experts, blended once at the router
        N = len(s.bodies)
        K = torch.stack(list(s.keys) + [s.halt_key], 0)
        nb = s.nov(nov[:, None])
        c = torch.softmax((s.q_entry(gist) + nb) @ K.t(), -1)
        w = c[:, :N]; w = w / w.sum(-1, keepdim=True).clamp_min(1e-9)
        O = torch.stack([b(h) for b in s.bodies], 1)
        return s.norm((w[:, :, None, None] * O).sum(1))
    def forward(s, h, gist, nov):
        N = len(s.bodies); HALT = N
        steps = max(1, min(s.max_steps, 2 + N // 2))
        if s.norm_only:
            for _ in range(steps): h = s.norm(h)
            return h
        K = torch.stack(list(s.keys) + [s.halt_key], 0)
        nb = s.nov(nov[:, None])
        c = torch.softmax((s.q_entry(gist) + nb) @ K.t(), -1)
        for _t_ in range(steps):
            if _t_ < s.min_steps:
                c = torch.cat([c[:, :N], torch.zeros_like(c[:, N:])], -1)
                c = c / c.sum(-1, keepdim=True).clamp_min(1e-9)
            nm = c[:, :N]
            Bo = torch.stack([b(h) for b in s.bodies], 1)
            h = s.norm(h + s.alpha * ((nm[:, :, None, None] * Bo).sum(1) - h))
            ent = -(c.clamp_min(1e-9).log() * c).sum(-1)
            bias = nb + s.ctrl(torch.stack([nm.sum(-1), c[:, HALT], ent], -1))
            Q = torch.stack([q(gist) for q in s.qproj], 1) + bias[:, None, :]
            R = torch.softmax(torch.einsum('bnk,mk->bnm', Q, K), -1)
            nxt = torch.einsum('bn,bnm->bm', nm, R).clone()
            nxt[:, HALT] = nxt[:, HALT] + c[:, HALT]
            c = nxt / nxt.sum(-1, keepdim=True).clamp_min(1e-9)
        return h


FAB = ENC = None
if FAB_CFG and d.get("fab") is not None:
    FAB = Fabric(D, SIG_D, FAB_CFG["dk"], FAB_CFG["n"], FAB_CFG["alpha"], FAB_CFG["max_steps"],
                 FAB_CFG["hid_mult"], FAB_CFG["min_steps"], FAB_CFG["norm_only"]).to(DEV)
    FAB.load_state_dict(d["fab"]); FAB.eval()
    ENC = SigEncoder(D, SIG_D).to(DEV); ENC.load_state_dict(d["enc"]); ENC.eval()

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
        if FAB is not None and GIST is not None:
            _h = model.encode(x); _n0 = torch.zeros(1, device=DEV)
            _h = FAB.society(_h, GIST, _n0) if FAB_SOC else FAB(_h, GIST, _n0)
            logits = model.head(_h)[0, -1]
        else:
            logits = model(x)[0][0, -1]
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

one_shot = os.environ.get("PROMPT")
if one_shot is not None:
    print(f"you> {one_shot}")
    GIST = _gist_of(one_shot)
    print(f"model> {generate(encode(one_shot), GEN_LEN, GEN_TEMP)}")
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
        print(f"model> {generate(encode(msg), GEN_LEN, GEN_TEMP)}\n")
