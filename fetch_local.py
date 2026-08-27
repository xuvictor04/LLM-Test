#!/usr/bin/env python3
"""Build a corpus from SOURCE ALREADY ON THIS MACHINE. No network, no account, no dataset terms.

WHY THIS EXISTS. The continual-learning chain -- train English, ADD a second area, re-measure English -- is the
one claim this project actually rests on, and it has never run end to end. Not for want of code: round18's
`fix_resume` arm produced a clean checkpoint and `pilot-add` resolved its vocabulary correctly, then died on

    [fetch_big] cannot read bigcode/the-stack-dedup: DatasetNotFoundError: ... is a gated dataset on the Hub.

Both code presets in fetch_big.py are gated, so the second area needs a Hugging Face account, accepted terms in
a browser, and a token in the environment -- three things that have nothing to do with the experiment. The
second area only has to be a DIFFERENT DISTRIBUTION from the first. A Python interpreter ships tens of MB of
real, diverse, idiomatic Python, and every machine that can run this project already has one.

    python3 fetch_local.py --domain py --out data_pilot --gb 0.03
    RESUME_FROM=runs/fix/fix_resume bash longrun.sh pilot-add py local 0.03

`pilot-add` skips its fetch when the target directory already has part*.txt, so populating it here is enough --
the third argument is then only a label.

WHAT IT REFUSES TO DO. It will not quietly hand back a corpus far smaller than asked for. The failure this
project keeps finding is a mechanism that runs and does nothing, and a 2 MB corpus delivered against a 30 MB
request is that failure in its purest form: the run completes, the report prints, and every number in it is
about a stream that ran out. Short of target it says so, with what it found and where, and exits non-zero
unless --allow-short.
"""
import argparse, hashlib, os, random, site, sys, sysconfig

# The shard size and the document separator match fetch_big.py exactly. datastream.open_corpus concatenates
# part*.txt in sorted order, so a corpus assembled here has to be indistinguishable from a downloaded one --
# otherwise "eng vs py" would also be "downloaded vs local", and the comparison would carry a second variable.
SHARD_MB = 256
SEP = "\n\n"

EXT = {"py": [".py"], "c": [".c", ".h"], "js": [".js", ".ts"], "go": [".go"], "rs": [".rs"],
       "md": [".md", ".rst"], "sh": [".sh"]}

# The Stack names its language directories in full. Our domains are short. Printing "--data-dir data/py" in
# the fallback advice below would hand the user a path that does not exist on the Hub, which is a worse
# failure than printing nothing: it looks authoritative and fails after the download starts.
STACK_DIR = {"py": "python", "c": "c", "js": "javascript", "go": "go", "rs": "rust", "sh": "shell"}

# Directories whose content is overwhelmingly generated, vendored or repetitive. Test trees are the big one:
# CPython's Lib/test is ~30% of the stdlib by bytes and is mostly assertion boilerplate, so including it would
# let a single template dominate the distribution the model is supposed to be learning.
SKIP_DIRS = {"test", "tests", "__pycache__", ".git", "node_modules", ".mypy_cache", ".pytest_cache",
             "idle_test", "lib2to3", ".venv", "venv"}


def roots_for(domain, extra):
    """Default search roots. Explicit --root always wins and is used alone.

    ASK site, NOT ONLY sysconfig. sysconfig.get_paths() reports purelib and platlib, which on Debian and
    Ubuntu -- what most of these boxes run -- both collapse to /usr/local/lib/pythonX/dist-packages. The
    system packages live in /usr/lib/python3/dist-packages, a THIRD directory that sysconfig never names.
    Measured on this container: sysconfig gives 2 paths, site.getsitepackages() gives 3. So the walk missed
    an entire install root, which is the first thing to suspect behind "the corpus is too small".
    site.getusersitepackages() adds ~/.local/lib/... for pip --user, missed the same way.
    """
    if extra:
        return list(extra)
    if domain != "py":
        return []
    cand = []
    for k in ("stdlib", "purelib", "platlib"):
        cand.append(sysconfig.get_paths().get(k))
    try:
        cand += list(site.getsitepackages())
    except AttributeError:                     # absent inside some virtualenvs
        pass
    try:
        cand.append(site.getusersitepackages())
    except Exception:
        pass
    # A NESTED ROOT IS NOT A NEW ROOT. stdlib is often the parent of a dist-packages entry, and walking both
    # visits every file twice -- harmless for the corpus (the content hash dedups it) but it doubles the read
    # and makes the "found N unique files" line disagree with what is on disk. Drop any candidate that lives
    # under one already kept.
    out = []
    for p in cand:
        if not p or not os.path.isdir(p):
            continue
        rp = os.path.realpath(p)
        if any(rp == q or rp.startswith(q + os.sep) for q in out):
            continue
        out = [q for q in out if not q.startswith(rp + os.sep)] + [rp]
    return out


def collect(roots, exts, min_bytes, include_tests):
    """Walk the roots and return [(path, text)], de-duplicated by content.

    DE-DUPLICATION IS NOT TIDINESS. site-packages vendors the same modules many times over (half a dozen copies
    of six.py, of packaging/, of pip's own bundled wheels). VAL_FRAC holds out the TAIL of the corpus as
    never-trained material, so a duplicated file that lands on both sides of that cut is trained on AND scored
    as held-out -- and the held-out number, which is the headline of every run, silently becomes a training
    number. Hash the content, keep the first occurrence.
    """
    seen, docs, n_dup, n_small, n_bad = set(), [], 0, 0, 0
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames
                           if d not in SKIP_DIRS or (include_tests and d in ("test", "tests", "idle_test"))]
            for fn in sorted(filenames):
                if not any(fn.endswith(e) for e in exts):
                    continue
                fp = os.path.join(dirpath, fn)
                try:
                    with open(fp, "rb") as fh:
                        raw = fh.read()
                except OSError:
                    n_bad += 1
                    continue
                if len(raw) < min_bytes:
                    n_small += 1
                    continue
                h = hashlib.blake2b(raw, digest_size=16).digest()
                if h in seen:
                    n_dup += 1
                    continue
                try:
                    txt = raw.decode("utf-8")
                except UnicodeDecodeError:
                    n_bad += 1
                    continue
                seen.add(h)
                docs.append((fp, txt))
    return docs, n_dup, n_small, n_bad


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--domain", default="py", help="corpus name; also picks the default extensions and roots")
    ap.add_argument("--out", default="data_pilot", help="writes <out>/train/<domain>/part*.txt")
    ap.add_argument("--gb", type=float, default=0.03, help="target size in GB (decimal, as fetch_big.py)")
    ap.add_argument("--root", action="append", default=[],
                    help="directory to walk; repeatable. Defaults to the Python stdlib + site-packages for --domain py")
    ap.add_argument("--ext", action="append", default=[], help="file extension to include, e.g. --ext .py; repeatable")
    ap.add_argument("--min-bytes", type=int, default=500, help="skip files smaller than this")
    ap.add_argument("--include-tests", action="store_true", help="keep test/ trees (repetitive; off by default)")
    ap.add_argument("--seed", type=int, default=0,
                    help="shuffle seed. The corpus is shuffled so the held-out TAIL is a sample of the whole "
                         "tree rather than whichever package sorts last")
    ap.add_argument("--allow-short", action="store_true", help="exit 0 even if the target was not reached")
    a = ap.parse_args()

    exts = a.ext or EXT.get(a.domain, [".txt"])
    roots = roots_for(a.domain, a.root)
    if not roots:
        sys.exit(f"[fetch_local] no search roots for --domain {a.domain}: pass --root <dir> (repeatable).\n"
                 f"  Only --domain py has defaults, and they are this interpreter's stdlib and site-packages.")
    target = int(a.gb * 1e9)
    print(f"[fetch_local] domain {a.domain} | extensions {' '.join(exts)} | target {target/1e6:.0f} MB")
    for r in roots:
        print(f"[fetch_local]   root {r}")

    docs, n_dup, n_small, n_bad = collect(roots, exts, a.min_bytes, a.include_tests)
    have = sum(len(t.encode("utf-8", "replace")) + len(SEP) for _, t in docs)
    print(f"[fetch_local] found {len(docs)} unique files, {have/1e6:.1f} MB "
          f"(skipped {n_dup} duplicate, {n_small} under {a.min_bytes} B, {n_bad} unreadable)")
    if not docs:
        sys.exit(f"[fetch_local] nothing to write. Check that the roots above contain {' '.join(exts)} files.")

    # SHUFFLE, THEN CUT. self_organize.py holds out the last VAL_FRAC of each corpus as never-trained material.
    # In directory-walk order that tail is one alphabetically-last package -- so "held out" would mean "the
    # xml module", and the headline number of every run would be a measurement of one library. A fixed seed
    # keeps it reproducible: the same machine and the same seed give the same split.
    random.Random(a.seed).shuffle(docs)

    outdir = os.path.join(a.out, "train", a.domain)
    os.makedirs(outdir, exist_ok=True)
    written = shard = ndoc = 0
    f = open(os.path.join(outdir, f"part{shard:03d}.txt"), "w", encoding="utf-8")
    try:
        for _, txt in docs:
            if written >= target:
                break
            chunk = txt.strip() + SEP
            f.write(chunk)
            written += len(chunk.encode("utf-8", "replace"))
            ndoc += 1
            if written // (SHARD_MB * 1_000_000) > shard:
                f.close()
                shard += 1
                f = open(os.path.join(outdir, f"part{shard:03d}.txt"), "w", encoding="utf-8")
    finally:
        f.close()

    print(f"[fetch_local] wrote {written/1e6:.1f} MB in {shard+1} shard(s) from {ndoc} files -> {outdir}")
    if written < target:
        pct = 100.0 * written / max(1, target)
        msg = (f"[fetch_local] SHORT: {written/1e6:.1f} MB of the {target/1e6:.0f} MB asked for ({pct:.0f}%). "
               f"The {len(roots)} root(s) searched hold {have/1e6:.1f} MB of {a.domain} in total:\n"
               + "".join(f"    {r}\n" for r in roots)
               + f"  A corpus this much smaller than requested is not a smaller version of the experiment: the\n"
               f"  two corpora get the same SHARE of the stream whatever their sizes, so the short one is drawn\n"
               f"  just as often from less text and is seen many times over. self_organize.py prints the\n"
               f"  per-corpus exposure at startup and warns past EXPOSURE_MAX / EXPOSURE_SKEW; this is the same\n"
               f"  problem, caught earlier.\n"
               f"  In descending order of how much it helps:\n"
               f"    - pull the real thing. With a Hugging Face token and the terms accepted:\n"
               f"        python3 fetch_big.py --dataset bigcode/the-stack-dedup "
               f"--data-dir data/{STACK_DIR.get(a.domain, a.domain)} \\\n"
               f"            --domain {a.domain} --gb {a.gb} --out {a.out} --resume\n"
               f"    - add roots this walk cannot guess: --root <a checkout> --root <another venv>, repeatable\n"
               f"    - install more source here (a big pure-Python package is tens of MB), then re-run\n"
               f"    - lower --gb to {written/1e9:.3f} and MATCH the other corpus to it, so neither is favoured")
        if not a.allow_short:
            sys.exit(msg + "\n  Pass --allow-short to proceed anyway.")
        print(msg + "\n  --allow-short given; proceeding.")


if __name__ == "__main__":
    main()
