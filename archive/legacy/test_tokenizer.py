"""Unified tokenizer test harness. Every section toggles on/off via env so we can probe one axis at a time:

  SECTIONS  comma list (default "correct,compress,robust"). Options:
    correct   lossless round-trip on edge cases + every corpus file (ByteBPE + Dynamic + Dyn-dropout)
    compress  bytes/token by domain (compression quality)
    robust    word-level typo robustness: token inflation + byte-fallback under swap/drop/dup/sub
    recon     model self-correction loop (needs CKPT + matching arch env): reconstruct -> decode -> re-tokenize
  FULL_BPE=1  also build the frozen ByteBPE 8192 vocab (slow, ~3min on the bundled corpus)
  VMAX, MIN_PAIR  dynamic-tokenizer settings for the built vocab (default 8192 / 200)
  CKPT        checkpoint for the recon section

Related standalone aspects (separate experiments, not folded -- they carry their own mini-systems):
  control.py continual        continual learning across domains + backward-transfer (runs the main system)
  control.py --preset larry    self-scaling preset (folded from larry/): seed + growth signal + ceiling, no target size

Examples:
  python3 test_tokenizer.py                         # correctness + compression + robustness (dynamic)
  SECTIONS=robust python3 test_tokenizer.py         # just the typo probe
  FULL_BPE=1 python3 test_tokenizer.py              # include the frozen-BPE audit
  SECTIONS=recon CKPT=eco_full/best.pt <arch env> python3 test_tokenizer.py
"""
import os, glob, random, time
import torch
from tokenizer import ByteBPE, DynamicTokenizer
import data_utils as D
random.seed(0)

SECTIONS = os.environ.get("SECTIONS", "correct,compress,robust").split(",")
VMAX = int(os.environ.get("VMAX", 8192)); MIN_PAIR = int(os.environ.get("MIN_PAIR", 200))


def _load_corpus():
    files = sorted(glob.glob("data/train/*/*.txt"))
    corpus = {f: open(f, encoding="utf-8", errors="ignore").read() for f in files}
    if not corpus:
        corpus = {"synthetic": "the quick brown fox jumps over the lazy dog 0123456789 " * 5000}
    return corpus


def _build_dynamic(corpus, warm_passes=1):
    stream = "".join(corpus.values()).encode()
    dyn = DynamicTokenizer(vmax=VMAX, min_pair=MIN_PAIR)
    for _ in range(warm_passes):
        for i in range(0, len(stream), 1024):
            dyn.segment(stream[i:i + 1024])
            for _ in range(4):
                if not dyn.maybe_grow(): break
    return dyn, stream


# ---- word-level typo injectors (the common error classes) ----
def _swap(w):
    if len(w) < 2: return w
    i = random.randrange(len(w) - 1); b = bytearray(w); b[i], b[i + 1] = b[i + 1], b[i]; return bytes(b)
def _drop(w):
    if len(w) < 2: return w
    i = random.randrange(len(w)); return w[:i] + w[i + 1:]
def _dup(w):
    if not w: return w
    i = random.randrange(len(w)); return w[:i + 1] + w[i:i + 1] + w[i + 1:]
def _sub(w):
    if not w: return w
    i = random.randrange(len(w)); b = bytearray(w); b[i] = random.randint(97, 122); return bytes(b)
TYPOS = {"swap": _swap, "drop": _drop, "dup": _dup, "sub": _sub}


def sec_correct(corpus):
    print("== correctness: lossless round-trip ==")
    fails = []
    edge = [("empty", ""), ("ascii", "hello world"), ("unicode", "cafe -- naive \u65e5\u672c\u8a9e \U0001F389 "),
            ("newlines/tabs", "a\n\tb\r\nc  d"), ("nul+control", "a\x00b\x01c"), ("repeated", "aaaa  bbbb")]
    dyn = DynamicTokenizer(vmax=512, min_pair=2)
    for _ in range(40):
        dyn.segment(b"the quick brown fox ")
        while dyn.maybe_grow(): pass
    for label, s in edge:
        r_dyn = dyn.decode(dyn.segment(s.encode(), count=False)) == s
        r_drop = dyn.decode(dyn.segment(s.encode(), count=False, dropout=0.5)) == s
        if not (r_dyn and r_drop): fails.append(label)
        print(f"  {label:14s} Dynamic/Dyn-dropout: {r_dyn}/{r_drop}")
    dyn2, _ = _build_dynamic(corpus)
    allok = all(dyn2.decode(dyn2.segment(s.encode(), count=False)) == s for s in corpus.values())
    print(f"  round-trip all {len(corpus)} files (Dynamic vocab {dyn2.vocab_size}):", "PASS" if allok else "FAIL")
    if os.environ.get("FULL_BPE") == "1":
        t0 = time.time(); bpe = ByteBPE().train("".join(corpus.values()), vocab_size=VMAX, verbose=False)
        bok = all(bpe.decode(bpe.encode(s)) == s for s in corpus.values())
        print(f"  frozen ByteBPE vocab {bpe.vocab_size} built in {time.time()-t0:.0f}s, round-trip:", "PASS" if bok else "FAIL")
    print("  ->", "ALL PASS" if not fails and allok else "FAILURES: " + ",".join(fails))


def sec_compress(corpus):
    print("\n== compression: bytes/token by domain ==")
    dyn, _ = _build_dynamic(corpus)
    dom = {}
    for f, s in corpus.items():
        d = f.split("/")[-2] if "/" in f else "all"; ids = dyn.segment(s.encode(), count=False)
        dom.setdefault(d, [0, 0]); dom[d][0] += sum(dyn.blen(i) for i in ids); dom[d][1] += len(ids)
    print(f"  Dynamic (vocab {dyn.vocab_size}):", {d: round(b / max(1, t), 2) for d, (b, t) in dom.items()})


def sec_robust(corpus):
    print("\n== robustness: word-level typos ==")
    from collections import Counter
    dyn, _ = _build_dynamic(corpus)
    txt = "".join(corpus.values()).encode()
    words = [w for w, _ in Counter(w for w in txt.split() if len(w) >= 4 and w.isalpha()).most_common(50)]
    if not words: words = [b"the", b"and", b"that", b"there", b"people", b"because"]
    agg = {k: [0.0, 0.0, 0] for k in TYPOS}
    for w in words:
        cl = max(1, len(dyn.segment(list(w), count=False)))
        for k, fn in TYPOS.items():
            tw = fn(w)
            if tw == w: continue
            ids = dyn.segment(list(tw), count=False); fb = sum(1 for t in ids if t < 256)
            agg[k][0] += len(ids) / cl; agg[k][1] += fb / max(1, len(ids)); agg[k][2] += 1
    for k in TYPOS:
        s, f, c = agg[k]
        if c: print(f"  {k:5s}: inflation {s/c:.2f}x | byte-fallback {f/c:.0%}  ({c} words)")


def sec_recon(corpus):
    print("\n== model self-correction loop ==")
    ckpt = os.environ.get("CKPT")
    if not (ckpt and os.path.exists(ckpt)):
        print("  (set CKPT + matching arch env with RECON on to run this)"); return
    from config import cfg
    from system import load_system
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    sysm, _ = load_system(ckpt, cfg, dev); sysm.eval()
    dyn = getattr(sysm, "dyntok", None)
    clean = b"the quick brown fox"
    typo = clean.rsplit(b" ", 1)[0] + b" " + _swap(clean.rsplit(b" ", 1)[1])
    ids = torch.tensor([(dyn.segment(list(typo), count=False) if dyn else list(typo))[:cfg.CTX]], device=dev)
    out = sysm.reconstruct(ids)
    if out is None:
        print("  model has no reconstruction head (train with RECON>0)"); return
    cids, retok, raw = out[0]
    print(f"  typo input : {typo!r}")
    print(f"  reconstructed -> re-tokenized: {len(cids)} -> {len(retok)} tokens | bytes {raw[:40]!r}")


def sec_fuzzy(corpus):
    print("\n== intrinsic fuzzy-matching tokenizer (edit-distance-1 typo correction) ==")
    from collections import Counter
    dyn, _ = _build_dynamic(corpus)
    n_idx = dyn.build_fuzzy_index()
    print(f"  built symmetric-delete index: {n_idx} keys over vocab {dyn.vocab_size}")
    txt = "".join(corpus.values()).encode()
    words = [w for w, _ in Counter(w for w in txt.split() if len(w) >= 4 and w.isalpha()).most_common(60)]
    if not words: words = [b"there", b"people", b"because", b"different"]
    plain_inf = fuzzy_inf = recovered = total = 0
    for w in words:
        clean = dyn.segment(list(w), count=False); cl = max(1, len(clean))
        for k, fn in TYPOS.items():
            tw = fn(w)
            if tw == w: continue
            total += 1
            p = dyn.segment(list(tw), count=False); f = dyn.fuzzy_segment(list(tw))
            plain_inf += len(p) / cl; fuzzy_inf += len(f) / cl
            if f == clean: recovered += 1
    if total:
        print(f"  plain inflation {plain_inf/total:.2f}x  ->  fuzzy inflation {fuzzy_inf/total:.2f}x  (lower = corrected)")
        print(f"  typos where fuzzy recovered the CLEAN tokenization exactly: {recovered}/{total} ({100*recovered/total:.0f}%)")


def sec_modeling(corpus):
    """Does tokenization actually LOWER bits/byte vs raw bytes? (folded from compare_tokenizer.py)
    Trains a small ByteLM byte-level vs dynamic-tokenized on the same text, reports TRUE bits/byte (token CE
    converted per-byte, so comparable). Slow -- trains 2 models. MODEL_STEPS controls length (default 300)."""
    import math, time
    from language import ByteLM
    LN2 = math.log(2); STEPS = int(os.environ.get("MODEL_STEPS", 300))
    D, NL, NH, CTX, BATCH, LR = 96, 2, 4, 96, 32, 3e-3
    text = "".join(corpus.values())[:800_000]
    split = int(len(text) * 0.9); train_txt, held_txt = text[:split], text[split:]
    dyn, _ = _build_dynamic(corpus)
    def run(name, ids_train, ids_held, vocab, blen):
        data = torch.tensor(ids_train, dtype=torch.long)
        model = ByteLM(vocab=vocab, d_model=D, n_layers=NL, n_heads=NH, max_len=CTX, dropout=0.1)
        opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=0.1)
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=STEPS)
        model.train()
        for _ in range(STEPS):
            ix = torch.randint(0, len(data) - CTX - 1, (BATCH,))
            x = torch.stack([data[i:i + CTX] for i in ix]); y = torch.stack([data[i + 1:i + 1 + CTX] for i in ix])
            _, loss = model(x, y); opt.zero_grad(); loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step(); sched.step()
        model.eval(); h = torch.tensor(ids_held[:30000], dtype=torch.long); tn = 0.0; tb = 0
        with torch.no_grad():
            for i in range(0, len(h) - CTX - 1, CTX):
                x = h[i:i + CTX][None]; y = h[i + 1:i + 1 + CTX][None]; lg, _ = model(x)
                tn += float(torch.nn.functional.cross_entropy(lg[0], y[0], reduction="sum"))
                tb += sum(blen(int(t)) for t in y[0])
        bpb = tn / max(1, tb) / LN2
        print(f"  {name:14s} vocab {vocab:5d} | held bits/byte {bpb:.3f}")
        return bpb
    print("\n== modeling: does tokenization lower bits/byte vs raw bytes? ==")
    bb = run("byte-level", list(train_txt.encode()), list(held_txt.encode()), 256, lambda t: 1)
    bt = run("dynamic", dyn.segment(train_txt.encode(), count=False), dyn.segment(held_txt.encode(), count=False), dyn.vocab_size, dyn.blen)
    print(f"  -> byte {bb:.3f} vs dynamic {bt:.3f} bits/byte | tokenizer {(bb-bt)/bb*100:+.1f}% lower (positive = tokenizer better)")


if __name__ == "__main__":
    corpus = _load_corpus()
    print(f"corpus: {len(corpus)} files, {sum(len(v) for v in corpus.values())} chars\n")
    if "correct" in SECTIONS: sec_correct(corpus)
    if "compress" in SECTIONS: sec_compress(corpus)
    if "robust" in SECTIONS: sec_robust(corpus)
    if "fuzzy" in SECTIONS: sec_fuzzy(corpus)
    if "modeling" in SECTIONS: sec_modeling(corpus)
    if "recon" in SECTIONS: sec_recon(corpus)
