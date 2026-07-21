"""tokenizer.py -- byte-level BPE for Greg.

A byte-level model spends its whole budget predicting single characters, which caps how low
bits/byte can go at a given compute. A BPE vocabulary merges frequent byte-pairs into single
tokens (`the`, `tion`, ` =`, ...), so each prediction covers more text -> lower effective
bits/byte on the SAME hardware. This is the standard, deterministic choice (the emergent
mint-on-repetition variant in continual_tokenizer.py is the online/continual upgrade).

Trained once on the corpus, saved to JSON, then loaded by data_utils / system / chat.
Always byte-grounded (vocab starts as the 256 bytes), so it round-trips ANY input losslessly
and `bytes_per_id` lets evaluation report true bits/BYTE for apples-to-apples with byte runs.

    python tokenizer.py            # build data/tokenizer.json from data/train/**, print stats
    VOCAB=4096 python tokenizer.py # target vocab size
"""
import os, json, glob, time, random
from collections import Counter


class ByteBPE:
    def __init__(self):
        # id -> bytes; first 256 ids are the raw bytes
        self.id2bytes = [bytes([i]) for i in range(256)]
        self.merges = []                      # ordered list of (a_id, b_id) -> new_id (= 256+k)
        self._rank = {}                       # (a,b) -> merge rank, for encoding
        self._cache = {}
        self._refresh()

    def _refresh(self):
        self._rank = {pair: k for k, pair in enumerate(self.merges)}
        self.bytes_per_id = [len(b) for b in self.id2bytes]
        self._cache = {}

    @property
    def vocab_size(self): return len(self.id2bytes)

    # ---- training (incremental: only re-examine words touched by each merge -> fast) ----
    def train(self, text: str, vocab_size: int = 4096, min_freq: int = 2, verbose=True):
        bs = text.encode("utf-8", "ignore")
        words = Counter(); start = 0
        for i, byte in enumerate(bs):
            if byte == 0x20 or byte == 0x0a:
                words[bs[start:i + 1]] += 1; start = i + 1
        if start < len(bs): words[bs[start:]] += 1
        wseq = {w: list(w) for w in words}
        pairs = Counter(); pair2words = {}
        for w, c in words.items():
            seq = wseq[w]
            for j in range(len(seq) - 1):
                p = (seq[j], seq[j + 1]); pairs[p] += c; pair2words.setdefault(p, set()).add(w)
        t0 = time.time()
        while self.vocab_size < vocab_size:
            if not pairs: break
            (a, b), cnt = pairs.most_common(1)[0]
            if cnt < min_freq: break
            nid = self.vocab_size
            self.id2bytes.append(self.id2bytes[a] + self.id2bytes[b]); self.merges.append((a, b))
            for w in list(pair2words.get((a, b), ())):       # only words containing this pair
                seq = wseq[w]; c = words[w]
                for j in range(len(seq) - 1):                # remove this word's old pair mass
                    pairs[(seq[j], seq[j + 1])] -= c
                out, i, n = [], 0, len(seq)
                while i < n:
                    if i < n - 1 and seq[i] == a and seq[i + 1] == b:
                        out.append(nid); i += 2
                    else:
                        out.append(seq[i]); i += 1
                wseq[w] = out
                for j in range(len(out) - 1):                # add the word's new pair mass
                    p = (out[j], out[j + 1]); pairs[p] += c; pair2words.setdefault(p, set()).add(w)
            pairs.pop((a, b), None); pair2words.pop((a, b), None)
            if self.vocab_size % 512 == 0:
                pairs = +pairs                               # drop non-positive entries (keeps it bounded)
                if verbose: print(f"  vocab {self.vocab_size}  (last merge x{cnt})  {time.time()-t0:.0f}s")
        self._refresh()
        return self

    # ---- encode / decode ----
    def _encode_chunk(self, bs: bytes):
        if bs in self._cache: return self._cache[bs]
        ids = list(bs)
        if self._rank:
            while len(ids) > 1:
                best, bestpos = None, -1
                for i in range(len(ids) - 1):
                    r = self._rank.get((ids[i], ids[i + 1]))
                    if r is not None and (best is None or r < best):
                        best, bestpos = r, i
                if best is None: break
                ids[bestpos:bestpos + 2] = [256 + best]
        self._cache[bs] = ids
        return ids

    def encode(self, text: str):
        """Word-chunked + cached: split on spaces/newlines (kept), encode short pieces independently."""
        bs = text.encode("utf-8", "ignore")
        if not self._rank: return list(bs)
        out, start = [], 0
        for i, byte in enumerate(bs):
            if byte == 0x20 or byte == 0x0a:          # break after spaces/newlines -> short chunks
                out.extend(self._encode_chunk(bs[start:i + 1])); start = i + 1
        if start < len(bs): out.extend(self._encode_chunk(bs[start:]))
        return out

    def decode(self, ids):
        return b"".join(self.id2bytes[int(i)] for i in ids).decode("utf-8", "replace")

    def blen(self, i): return self.bytes_per_id[int(i)]   # #bytes this token spans (for bits/byte)

    # ---- persistence ----
    def save(self, path):
        json.dump({"merges": self.merges}, open(path, "w"))
        return path

    @classmethod
    def load(cls, path):
        t = cls(); data = json.load(open(path))
        for a, b in data["merges"]:
            t.id2bytes.append(t.id2bytes[a] + t.id2bytes[b]); t.merges.append((a, b))
        t._refresh(); return t


class DynamicTokenizer:
    """EMERGENT vocab: starts as the 256 bytes and MINTS a new token when a pair repeats often enough
    DURING training (mint-on-repetition). segment() is greedy longest-match with the current vocab and
    tallies adjacent-pair counts; maybe_grow() promotes the most-frequent pair to a new token once it
    crosses `min_pair`. The model initializes the new token's embedding (mean of its two parts) via its
    own grow_vocab(). Vocab grows online up to vmax. byte-grounded => lossless; blen() gives bytes/token
    so evaluation reports true bits/byte."""
    def __init__(self, vmax=8192, min_pair=200, max_tok=16, dropout=0.0, max_pairs=60000):
        self.id2bytes = [bytes([i]) for i in range(256)]
        self.seq2id = {bytes([i]): i for i in range(256)}
        self.merges = []                       # ordered (a,b) pairs minted, for save/load
        self.maxlen = 1; self.vmax = vmax; self.min_pair = min_pair; self.max_tok = max_tok
        self.dropout = dropout                 # P(skip a merge) -> preferential, not strict; 0 = strict greedy
        self.max_pairs = max_pairs             # cap the pair tally (keeps memory bounded on large corpora)
        self.pair = Counter()
        self.bytes_per_id = [1] * 256
        self.mlbf = [1] * 256                  # max token byte-length starting with each byte (prunes segment's L-loop)

    @property
    def vocab_size(self): return len(self.id2bytes)

    def segment(self, blist, count=True, dropout=None):
        """Greedy longest-match, but PREFERENTIAL: each candidate merge is skipped with prob `dropout`,
        falling back toward the raw byte (always in vocab). dropout default = self.dropout while training
        (count=True), 0 at eval/inference (deterministic). Lets the model use byte-level material."""
        p = (self.dropout if dropout is None else dropout) if count else (0.0 if dropout is None else dropout)
        bs = bytes(blist); ids = []; i = 0; n = len(bs); mlbf = self.mlbf
        while i < n:
            chosen = None
            for L in range(min(self.maxlen, n - i, mlbf[bs[i]]), 1, -1):   # only lengths that can start with this byte
                if p and random.random() < p: continue          # preferential: probabilistically skip
                j = self.seq2id.get(bs[i:i + L])
                if j is not None: chosen = (j, L); break
            if chosen is None: chosen = (bs[i], 1)               # byte fallback (always valid)
            ids.append(chosen[0]); i += chosen[1]
        if count:
            for a, b in zip(ids, ids[1:]): self.pair[(a, b)] += 1
        return ids

    def maybe_grow(self):
        """Mint the most-frequent pair if it crosses threshold. Returns (new_id, a, b) or None.
        Locked so a background batch-prefetch thread can tally `pair` concurrently without racing most_common()."""
        with self.lock:
            if len(self.pair) > self.max_pairs:                    # bound memory: drop the rare-pair long tail
                self.pair = Counter(dict(self.pair.most_common(self.max_pairs // 2)))
            if self.vocab_size >= self.vmax or not self.pair: return None
            (a, b), cnt = self.pair.most_common(1)[0]
            if cnt < self.min_pair: return None
            self.pair[(a, b)] = 0
            ns = self.id2bytes[a] + self.id2bytes[b]
            if len(ns) > self.max_tok or ns in self.seq2id: return None
            nid = self.vocab_size
            self.id2bytes.append(ns); self.seq2id[ns] = nid; self.merges.append((a, b))
            self.maxlen = max(self.maxlen, len(ns)); self.bytes_per_id.append(len(ns))
            self.mlbf[ns[0]] = max(self.mlbf[ns[0]], len(ns))
            return (nid, a, b)

    @property
    def lock(self):
        l = getattr(self, "_lock", None)
        if l is None:
            import threading; l = threading.Lock(); self._lock = l
        return l

    def apply_merge(self, a, b):
        """Append one already-decided merge (no pair-count check). Used to sync worker-process vocab replicas."""
        ns = self.id2bytes[a] + self.id2bytes[b]
        if len(ns) > self.max_tok or ns in self.seq2id: return
        self.id2bytes.append(ns); self.seq2id[ns] = len(self.id2bytes) - 1; self.merges.append((a, b))
        self.maxlen = max(self.maxlen, len(ns)); self.bytes_per_id.append(len(ns))
        self.mlbf[ns[0]] = max(self.mlbf[ns[0]], len(ns))

    def blen(self, i): return self.bytes_per_id[int(i)]
    def seg(self, blist, count=False):
        """Segmentation used to feed the model. Fuzzy (edit-distance-1 correcting) when enabled, else exact."""
        if getattr(self, "_use_fuzzy", False): return self.fuzzy_segment(blist)
        return self.segment(blist, count=count)

    def seg(self, blist, count=False):
        """Segmentation used to feed the model. Fuzzy (edit-distance-1 correcting) when enabled, else exact."""
        ids = self.fuzzy_segment(blist) if getattr(self, "_use_fuzzy", False) else self.segment(blist, count=count)
        if getattr(self, "_track_use", False):
            u = self._tok_use
            for i in ids: u[i] = u.get(i, 0) + 1
        return ids

    def track_usage(self, on=True):
        self._track_use = on
        if on and not hasattr(self, "_tok_use"): self._tok_use = {}

    def retire_stale(self, min_use=3.0):
        """UN-MERGE: drop merged tokens unused since the last check from the match table -> they re-segment to their
        parts. Soft retire (index stays, embedding goes unused, but segmentation stops producing it). Resets usage."""
        u = getattr(self, "_tok_use", {}); retired = 0
        for tid in range(256, len(self.id2bytes)):
            if u.get(tid, 0) < min_use and self.seq2id.pop(self.id2bytes[tid], None) is not None: retired += 1
        self._tok_use = {}
        if getattr(self, "_use_fuzzy", False): self.build_fuzzy_index()
        return retired

    def set_fuzzy(self, on=True):
        self._use_fuzzy = bool(on)
        if on: self.build_fuzzy_index()
        if hasattr(self, "_seg_cache"): self._seg_cache.clear()   # cached exact segmentations differ from fuzzy

    def decode(self, ids): return b"".join(self.id2bytes[int(i)] for i in ids).decode("utf-8", "replace")

    def build_fuzzy_index(self, min_len=3):
        """Symmetric-delete index: map each delete-1 variant of every vocab token (len>=min_len) to that token.
        Enables edit-distance-1 matching in fuzzy_segment (a typo'd span -> the intended token). Rebuild after growth."""
        idx = {}
        for tid, bs in enumerate(self.id2bytes):
            if len(bs) < min_len: continue
            for k in [bs] + [bs[:i] + bs[i + 1:] for i in range(len(bs))]:
                if k not in idx or len(self.id2bytes[idx[k]]) < len(bs): idx[k] = tid   # prefer the longer token on collision
        self._fuzzy = idx; self._fuzzy_minlen = min_len
        return len(idx)

    def _fuzzy_lookup(self, span):
        """A token id within edit distance ~1 of span (delete-1 on both sides covers sub/ins/del of one char), or None."""
        fz = getattr(self, "_fuzzy", None)
        if fz is None: return None
        best = fz.get(span)                                    # exact / substitution hit
        for i in range(len(span)):                             # deletions of the query (covers insertion errors)
            t = fz.get(span[:i] + span[i + 1:])
            if t is not None and (best is None or len(self.id2bytes[t]) > len(self.id2bytes[best])): best = t
        return best

    def fuzzy_segment(self, blist, max_span=None):
        """LOSSY corrective segmentation: greedily match tokens allowing edit-distance-1, fixing typos to known tokens.
        Separate from segment(): its output need NOT decode to the input (it is corrected). Needs build_fuzzy_index()."""
        if getattr(self, "_fuzzy", None) is None: self.build_fuzzy_index()
        b = bytes(blist); out = []; i = 0; n = len(b); ms = max_span or self.maxlen + 2
        while i < n:
            hit_t, consume = None, 1
            for L in range(min(ms, n - i), self._fuzzy_minlen - 1, -1):
                span = b[i:i + L]
                t = self.seq2id.get(span) or self._fuzzy_lookup(span)   # exact first, then edit-distance-1
                if t is not None: hit_t, consume = t, L; break
            if hit_t is None: out.append(b[i]); i += 1          # nothing >= min_len: pass the raw byte through
            else: out.append(hit_t); i += consume
        return out

    def save(self, path):
        json.dump({"merges": self.merges, "vmax": self.vmax, "min_pair": self.min_pair,
                   "max_tok": self.max_tok, "dropout": self.dropout, "max_pairs": self.max_pairs},
                  open(path, "w")); return path

    @classmethod
    def load(cls, path):
        d = json.load(open(path))
        t = cls(d.get("vmax", 8192), d.get("min_pair", 200), d.get("max_tok", 16),
                d.get("dropout", 0.0), d.get("max_pairs", 60000))
        for a, b in d["merges"]:
            ns = t.id2bytes[a] + t.id2bytes[b]
            t.id2bytes.append(ns); t.seq2id[ns] = len(t.id2bytes) - 1
            t.maxlen = max(t.maxlen, len(ns)); t.bytes_per_id.append(len(ns))
            t.mlbf[ns[0]] = max(t.mlbf[ns[0]], len(ns))
        t.merges = list(map(tuple, d["merges"])); return t


def build_from_corpus(data_dir="data", vocab_size=None, out="data/tokenizer.json"):
    vocab_size = vocab_size or int(os.environ.get("VOCAB", 4096))
    files = sorted(glob.glob(os.path.join(data_dir, "train", "**", "*.txt"), recursive=True))
    assert files, f"no training text under {data_dir}/train/"
    text = "".join(open(f, encoding="utf-8", errors="ignore").read() for f in files)
    cap = int(os.environ.get("BPE_TRAIN_CAP", 5_000_000))      # cap the merge-training text for speed
    if cap and len(text) > cap: text = text[:cap]
    print(f"training byte-BPE to vocab {vocab_size} on {len(text)} chars from {len(files)} files...")
    tok = ByteBPE().train(text, vocab_size=vocab_size)
    tok.save(out)
    ids = tok.encode(text[:200_000])
    bytes_per_tok = sum(tok.blen(i) for i in ids) / max(1, len(ids))
    print(f"saved {out} | vocab {tok.vocab_size} | ~{bytes_per_tok:.2f} bytes/token "
          f"(byte model = 1.0; higher = more compression)")
    return tok


if __name__ == "__main__":
    build_from_corpus()
