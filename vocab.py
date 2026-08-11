#!/usr/bin/env python3
"""vocab.py -- read a saved tokenizer and ask whether its later tokens earn their place.

A run saves its vocabulary to TOKENIZER_PATH as {"merges": [(a, b), ...]}. Ids are handed out in
order, so id 256+k IS the (k+1)th token ever minted: the file is a complete mint LOG, not just a
table. Nothing read it, so "are the tokens minted late any good?" had no answer short of guessing
from generated text.

Mint order is the axis everything here is grouped by. A token minted in the first cohort had the
whole run to be used and to be trained; one minted in the last cohort arrived near the end, and on
an annealed schedule it arrived with almost no learning rate left. Those are different objects and
averaging over them hides it.

    python3 vocab.py                              # data/dyntok.json, cohort table
    python3 vocab.py runs/vmax/vmax8k.dyntok.json
    python3 vocab.py <path> --corpus data_pilot   # + how much text each cohort actually covers
    python3 vocab.py <path> --list 40             # the newest 40 tokens, in mint order
    python3 vocab.py <path> --list 40 --from 4823 # ...or a window of mint order

WITHOUT --corpus the report is about the token STRINGS only (length, shape, whether they look like
words). Shape is suggestive, not decisive: the question that matters is how much of the stream a
cohort actually covers, and that needs text. Pass --corpus for it.
"""
import argparse
import glob
import json
import os
import sys

BYTES_PER_COHORT_CAP = 8_000_000        # cap the text we segment; the shape of the answer settles fast


def show(b):
    """A token's bytes, printable, with its edges visible -- leading/trailing space is the single
    most informative thing about a subword unit and is invisible in a bare print."""
    s = b.decode("utf-8", "replace")
    s = "".join(c if c.isprintable() or c == " " else {"\n": "\\n", "\t": "\\t", "\r": "\\r"}.get(c, "�")
                for c in s)
    return "·" + s[1:] if s.startswith(" ") else s


def shape(b):
    """Coarse classes. A subword vocabulary is supposed to be mostly word-ish; a vocabulary that has
    run out of words mints interior fragments, and that is what late cohorts are suspected of."""
    try:
        s = b.decode("utf-8")
    except UnicodeDecodeError:
        return "binary"
    core = s.strip()
    if not core:
        return "space"
    if s.startswith(" ") and core.isalpha():
        return "word-initial"          # " the", " because" -- the useful shape
    if core.isalpha():
        return "fragment"              # "ecau", "erent" -- interior of a word, no boundary
    if core.isdigit():
        return "digit"
    return "mixed"


def load_merges(path):
    d = json.load(open(path))
    if "merges" not in d:
        raise SystemExit(f"!! {path} has no 'merges' key -- is it a tokenizer file?")
    id2bytes = [bytes([i]) for i in range(256)]
    for a, b in d["merges"]:
        id2bytes.append(id2bytes[a] + id2bytes[b])
    return d, id2bytes


def read_corpus(spec, cap):
    if os.path.isdir(spec):
        files = sorted(glob.glob(os.path.join(spec, "**", "*.txt"), recursive=True))
        if not files:
            raise SystemExit(f"!! no .txt under {spec}")
    else:
        files = [spec]
    out = bytearray()
    for f in files:
        out += open(f, "rb").read(cap - len(out))
        if len(out) >= cap:
            break
    return bytes(out)


def segment(id2bytes, data, maxlen):
    """Greedy longest-match, the same rule DynamicTokenizer.segment uses, so the counts here are the
    counts the run would have seen. Kept local rather than importing so this tool still reads a
    tokenizer file produced by a version of tokenizer.py that has since moved on."""
    seq2id = {}
    for i, b in enumerate(id2bytes):
        seq2id.setdefault(b, i)
    ids, i, n = [], 0, len(data)
    while i < n:
        for L in range(min(maxlen, n - i), 1, -1):
            j = seq2id.get(data[i:i + L])
            if j is not None:
                ids.append(j); i += L; break
        else:
            ids.append(data[i]); i += 1
    return ids


def main(argv):
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("path", nargs="?", default="data/dyntok.json")
    ap.add_argument("--corpus", default=None, help="file or directory of .txt to measure real usage against")
    ap.add_argument("--list", type=int, default=0, metavar="N", help="dump N tokens in mint order")
    ap.add_argument("--from", dest="start", type=int, default=None, metavar="ID",
                    help="with --list: start at this token id (default: the newest N)")
    ap.add_argument("--cohorts", type=int, default=8)
    a = ap.parse_args(argv)

    if not os.path.exists(a.path):
        raise SystemExit(f"!! {a.path} not found. A run writes it to TOKENIZER_PATH "
                         f"(default data/dyntok.json) at the end of training.")
    d, id2bytes = load_merges(a.path)
    V = len(id2bytes); nm = V - 256
    maxlen = max(len(b) for b in id2bytes)
    print(f"{a.path}: vocab {V} ({nm} minted over 256 bytes) | vmax {d.get('vmax','?')} | "
          f"min_pair {d.get('min_pair','?')} | max_tok {d.get('max_tok','?')} | longest {maxlen} B")
    if nm <= 0:
        return 0

    if a.list:
        lo = a.start if a.start is not None else max(256, V - a.list)
        print(f"\n=== tokens {lo}..{min(V, lo + a.list) - 1} in MINT ORDER (id 256+k = the k+1'th minted) ===")
        for i in range(max(256, lo), min(V, lo + a.list)):
            print(f"  #{i - 255:<6} id {i:<6} {len(id2bytes[i]):2d}B  {shape(id2bytes[i]):<12} {show(id2bytes[i])!r}")

    use = cov = None
    if a.corpus:
        data = read_corpus(a.corpus, BYTES_PER_COHORT_CAP)
        ids = segment(id2bytes, data, maxlen)
        use = [0] * V
        for i in ids:
            use[i] += 1
        cov = [use[i] * len(id2bytes[i]) for i in range(V)]
        print(f"\ncorpus: {len(data)/1e6:.1f} MB -> {len(ids)} tokens "
              f"({len(data)/max(1,len(ids)):.2f} bytes/token)")

    print(f"\n=== BY MINT ORDER, {a.cohorts} equal cohorts of the {nm} minted tokens ===")
    hdr = f"  {'cohort':<13} {'ids':<13} {'mean B':>6} {'word-init':>9} {'fragment':>8} {'other':>6}"
    if use: hdr += f" {'uses':>10} {'%tokens':>8} {'%bytes':>7} {'unused':>7}"
    print(hdr)
    step = max(1, -(-nm // a.cohorts))
    tot_u = sum(use[256:]) + sum(use[:256]) if use else 0
    tot_c = sum(cov) if cov else 0
    for c0 in range(256, V, step):
        c1 = min(V, c0 + step)
        grp = list(range(c0, c1))
        mb = sum(len(id2bytes[i]) for i in grp) / len(grp)
        sh = [shape(id2bytes[i]) for i in grp]
        wi = 100 * sh.count("word-initial") / len(grp)
        fr = 100 * sh.count("fragment") / len(grp)
        row = (f"  {f'{c0-255}-{c1-256}':<13} {f'{c0}-{c1-1}':<13} {mb:6.2f} {wi:8.0f}% {fr:7.0f}% "
               f"{100-wi-fr:5.0f}%")
        if use:
            u = sum(use[i] for i in grp); cv = sum(cov[i] for i in grp)
            nz = sum(1 for i in grp if use[i] == 0)
            row += (f" {u:10d} {100*u/max(1,tot_u):7.1f}% {100*cv/max(1,tot_c):6.1f}% "
                    f"{100*nz/len(grp):6.0f}%")
        print(row)

    if use:
        print("\n  %tokens = share of the segmented stream this cohort produced.")
        print("  %bytes  = share of the CORPUS it covers (uses x length) -- the one that says whether it pays.")
        print("  unused  = tokens in the cohort that never appear. A late cohort that is mostly unused was")
        print("            minted from pairs that had already stopped recurring.")
    else:
        print("\n  Shape only -- pass --corpus to measure what each cohort actually covers.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
