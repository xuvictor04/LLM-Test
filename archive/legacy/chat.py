"""Chat with a trained Greg -- byte-level continuation from the checkpoint.

  python chat.py                      # interactive REPL
  python chat.py "Once upon a time"   # one-shot continuation

IMPORTANT: pass the SAME model env vars used during training (D_MODEL, N_LAYERS, N_HEADS, CTX,
MAX_LEN, MEMCAP, MEMORY, NOVELTY, and for v1: VOCAB, TOKENIZER, COUNTERPARTS) so the checkpoint
loads with matching architecture. With a TOKENIZER set, chat encodes/decodes via BPE automatically.

Greg is a byte-level model trained on prose / code / numbers. It CONTINUES text in the style of its
training data; it is not an instruction-tuned assistant -- don't expect Q&A, expect autocompletion.
"""
import os, sys, torch, torch.nn.functional as F
from config import cfg
from system import load_system, ReverseSurprise

dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
CKPT = os.environ.get("CKPT")
if not CKPT:                                            # prefer best.pt (early-stop's peak) over the last ckpt.pt
    _rd = os.environ.get("RUN_DIR", "runs")
    CKPT = os.path.join(_rd, "best.pt") if os.path.exists(os.path.join(_rd, "best.pt")) else os.path.join(_rd, "ckpt.pt")
assert os.path.exists(CKPT), f"no checkpoint at {CKPT} -- train first (python train.py)"
sysm, ck = load_system(CKPT, cfg, dev)
if (os.environ.get("SURPRISE") or os.environ.get("NOVELTY") or "reverse") == "reverse" and not isinstance(sysm.surprise, ReverseSurprise):
    sysm.surprise = ReverseSurprise(sysm.base, dev)
sysm.eval()
print(f"loaded {CKPT} | nodes {len(sysm.bodies)} | layers {len(sysm.base.blocks)} | "
      f"mem {getattr(sysm.mem, 'n', 0)} | device {dev}")


@torch.no_grad()
def generate(prompt, n=240, temp=0.8, top_k=40):
    dyn = getattr(sysm, "dyntok", None); bpe = getattr(sysm, "bpe", None)   # token-mode if either set
    if dyn is not None:
        ids = dyn.segment(prompt.encode("utf-8", "ignore"), count=False) or [32]
    elif bpe is not None:
        ids = bpe.encode(prompt) or [32]
    else:
        ids = list(prompt.encode("utf-8", errors="ignore")) or [32]
    for _ in range(n):
        ctx = torch.tensor([ids[-cfg.CTX:]], device=dev)
        posnov = sysm.surprise.score_pos(ctx.cpu()).to(dev)            # reverse-novelty input
        out = sysm(ctx, posnov); lg = out[0] if isinstance(out, tuple) else out  # memory recall is read-only here
        logits = lg[0, -1] / max(temp, 1e-6)
        if top_k:
            v, _ = torch.topk(logits, min(top_k, logits.numel())); logits[logits < v[-1]] = -float("inf")
        ids.append(int(torch.multinomial(F.softmax(logits, -1), 1)))
    if dyn is not None: return dyn.decode(ids)
    if bpe is not None: return bpe.decode(ids)
    return bytes(ids).decode("utf-8", errors="replace")


if len(sys.argv) > 1:
    print(generate(" ".join(sys.argv[1:]))); sys.exit(0)

print("type a prompt (or 'quit').  controls:  /temp 0.7   /len 300")
temp, ln = 0.8, 240
while True:
    try:
        s = input("\nyou> ").strip()
    except EOFError:
        break
    if s in ("quit", "exit"):
        break
    if s.startswith("/temp"):
        temp = float(s.split()[1]); print(f"temp={temp}"); continue
    if s.startswith("/len"):
        ln = int(s.split()[1]); print(f"len={ln}"); continue
    if s:
        print("\ngreg>", generate(s, n=ln, temp=temp))
