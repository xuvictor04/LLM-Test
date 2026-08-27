"""Data loading. Corpus lives in folders so you can scale it by dropping more .txt files in:
    data/train/<domain>/*.txt    (concatenated per domain; domains: eng, py, c, num, ...)
    data/ood/<name>/*.txt        (held-out ENTIRE sources, never trained on)
Prose domains (any whose name starts with 'eng') get Gutenberg headers stripped.
Run get_data.py once to populate these folders.
"""
import os, glob, re, random
import torch
from language import encode

PROSE_PREFIX = "eng"  # domains/ood-sets whose name starts with this are treated as prose (cleaned)

def _make_encoder(cfg):
    """Byte encoder by default and for dynamic (segmented live by the trainer);
    a frozen BPE token encoder when cfg.TOKENIZER is a path."""
    mode = getattr(cfg, "TOKENIZER", "")
    if mode and mode != "dynamic":
        from tokenizer import ByteBPE
        tok = ByteBPE.load(mode)
        return lambda s: torch.tensor(tok.encode(s), dtype=torch.long)
    return encode

def dyn_window(cfg):
    """Dynamic mode needs byte windows long enough to segment into >= CTX tokens; 1x otherwise."""
    return cfg.CTX * (4 if getattr(cfg, "TOKENIZER", "") == "dynamic" else 1)

def dyn_batch(chunks, dyntok, n, ctx):
    """Dynamic mode: sample byte windows, take a fixed CTX-token slice -> (B, CTX).
    Segmentation is CACHED (valid forever since vocab only grows); a small fraction re-segment each step.
    Pair-tallying (for minting) is VECTORIZED with NumPy -- one unique-count over the whole batch instead of
    tens of thousands of Counter increments -- so it's no longer a per-token Python loop."""
    import random, numpy as np
    cache = dyntok.__dict__.setdefault("_seg_cache", {})
    if len(cache) > 300000: cache.clear()                        # soft memory cap
    refresh = getattr(dyntok, "refresh_frac", 0.05)             # fraction re-segmented each step
    rows, tries = [], 0
    while len(rows) < n and tries < n * 6:
        tries += 1
        ch = chunks[random.randrange(len(chunks))]; key = id(ch)
        ids = cache.get(key)
        if ids is None or (refresh and random.random() < refresh):
            ids = dyntok.seg(ch.tolist(), count=False)          # fuzzy-aware segmentation (exact unless FUZZY on)
            cache[key] = ids
        if len(ids) < ctx: continue
        s = random.randint(0, len(ids) - ctx)
        rows.append(ids[s:s + ctx])
    if not rows: return None
    arr = np.asarray(rows, dtype=np.int64)                      # (B, CTX)
    vm = dyntok.vmax
    codes = (arr[:, :-1] * vm + arr[:, 1:]).ravel()            # encode each adjacent pair as one int
    uniq, cnts = np.unique(codes, return_counts=True)          # count all pairs at once (C, not Python)
    with dyntok.lock:                                          # brief: maybe_grow reads pair concurrently
        pair = dyntok.pair
        for c, k in zip(uniq.tolist(), cnts.tolist()):
            pair[(c // vm, c % vm)] += k
    return torch.from_numpy(arr)

def clean_gutenberg(t: str) -> str:
    m = re.search(r"\*\*\* START OF.*?\*\*\*", t, re.S)
    if m: t = t[m.end():]
    m = re.search(r"\*\*\* END OF", t, re.S)
    if m: t = t[:m.start()]
    t = re.sub(r"\r", "", t); t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()

def _read_folder(folder, name, cap):
    files = sorted(glob.glob(os.path.join(folder, "*.txt")))
    parts = []
    for fp in files:
        t = open(fp, encoding="utf-8", errors="ignore").read()
        if name.startswith(PROSE_PREFIX): t = clean_gutenberg(t)   # clean EACH file (concatenating first ate enwik8)
        parts.append(t)
    txt = "".join(parts)
    if cap and cap > 0: txt = txt[:cap]
    return txt

def _chunk(txt, L, enc):
    b = enc(txt); cs = [b[i*L:(i+1)*L] for i in range(len(b)//L)]
    return [c for c in cs if len(c) == L]

def load_corpus(cfg):
    """Returns TRAIN (flat list of (CTX,) chunks), HELD {domain: chunks}, OOD {name: chunks}.
    Chunks are byte ids, or BPE token ids when cfg.TOKENIZER is set."""
    L = dyn_window(cfg); enc = _make_encoder(cfg)
    train_root = os.path.join(cfg.DATA_DIR, "train"); ood_root = os.path.join(cfg.DATA_DIR, "ood")
    assert os.path.isdir(train_root), f"missing {train_root} -- run: python get_data.py"
    TRAIN, HELD = [], {}
    for dom in sorted(os.listdir(train_root)):
        folder = os.path.join(train_root, dom)
        if not os.path.isdir(folder): continue
        cs = _chunk(_read_folder(folder, dom, cfg.DATA_CAP), L, enc)
        if not cs: continue
        nsplit = int(len(cs) * 0.9)
        TRAIN += cs[:nsplit]; HELD[dom] = cs[nsplit:nsplit + cfg.HELD]
    OOD = {}
    if os.path.isdir(ood_root):
        for name in sorted(os.listdir(ood_root)):
            folder = os.path.join(ood_root, name)
            if not os.path.isdir(folder): continue
            cs = _chunk(_read_folder(folder, name, cfg.DATA_CAP), L, enc)
            if cs: OOD[name] = cs[:cfg.OOD_N]
    assert TRAIN, "no training data found"
    return TRAIN, HELD, OOD

def sample_batch(TRAIN, cfg):
    import torch
    idx = [random.randrange(len(TRAIN)) for _ in range(cfg.BATCH)]
    return torch.stack([TRAIN[i] for i in idx])   # (B, CTX) on CPU
