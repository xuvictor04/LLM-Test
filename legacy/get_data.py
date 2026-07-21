"""Download/build the training + OOD corpus into data/.
    python get_data.py
Training sources (public-domain prose + permissively-licensed source code) go to data/train/<domain>/,
and held-out ENTIRE sources (never trained on) go to data/ood/<name>/.
To scale up: drop more .txt files into any data/train/<domain>/ folder (they're concatenated),
or add entries to TRAIN_SOURCES / OOD_SOURCES below.  Re-run is safe (skips files already present).
Override the numeric-domain size with NUM_ROWS=20000 python get_data.py
"""
import os, random, urllib.request

DATA_DIR = os.environ.get("DATA_DIR", "data")
NUM_ROWS = int(os.environ.get("NUM_ROWS", 8000))

# domain -> list of (filename, url).  Prose domains must start with "eng" (they get Gutenberg-cleaned).
TRAIN_SOURCES = {
    "eng": [("candle.txt", "https://raw.githubusercontent.com/GITenberg/The-Chemical-History-of-a-Candle_14474/master/14474.txt")],
    "py":  [("argparse.txt",   "https://raw.githubusercontent.com/python/cpython/main/Lib/argparse.py"),
            ("typing.txt",     "https://raw.githubusercontent.com/python/cpython/main/Lib/typing.py"),
            ("dataclasses.txt","https://raw.githubusercontent.com/python/cpython/main/Lib/dataclasses.py")],
    "c":   [("sds.txt", "https://raw.githubusercontent.com/antirez/sds/master/sds.c")],
    # "num" is generated below
}
OOD_SOURCES = {   # held-out ENTIRE sources -- the real generalization test
    "eng_OOD":  [("sherlock.txt", "https://raw.githubusercontent.com/GITenberg/The-Adventures-of-Sherlock-Holmes_1661/master/1661.txt")],
    "code_OOD": [("rust.txt",     "https://raw.githubusercontent.com/rust-lang/rust/master/library/alloc/src/vec/mod.rs")],
}

def fetch(url, path):
    if os.path.exists(path) and os.path.getsize(path) > 0:
        print(f"  skip {path} (exists)"); return
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    data = urllib.request.urlopen(req, timeout=120).read()
    open(path, "wb").write(data); print(f"  saved {path} ({len(data)} bytes)")

def gen_num(path, rows):
    if os.path.exists(path) and os.path.getsize(path) > 0:
        print(f"  skip {path} (exists)"); return
    random.seed(0)
    lines = (",".join(f"{random.randint(0,9999)}.{random.randint(0,99):02d}" for _ in range(6)) for _ in range(rows))
    open(path, "w").write("\n".join(lines)); print(f"  generated {path} ({rows} rows)")

def main():
    for root, sources in (("train", TRAIN_SOURCES), ("ood", OOD_SOURCES)):
        for dom, files in sources.items():
            folder = os.path.join(DATA_DIR, root, dom); os.makedirs(folder, exist_ok=True)
            print(f"[{root}/{dom}]")
            for fn, url in files:
                try: fetch(url, os.path.join(folder, fn))
                except Exception as e: print(f"  FAILED {url}: {e}  (you can drop the file in manually)")
    numdir = os.path.join(DATA_DIR, "train", "num"); os.makedirs(numdir, exist_ok=True)
    print("[train/num]"); gen_num(os.path.join(numdir, "num.txt"), NUM_ROWS)
    print("\nCorpus ready under", DATA_DIR)

if __name__ == "__main__":
    main()
