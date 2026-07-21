"""build_continual_data.py -- populate data/continual/ with DISTINCT domains that ARRIVE in sequence.

The continual run (continual.py) pretrains on data/train/ then streams these phases one at a time,
measuring how much earlier domains are forgotten as later ones arrive (backward transfer). For that
to be meaningful the phases must be genuinely DIFFERENT from each other and from the pretrain set --
so we pull a new programming language (Rust), two unseen prose sources, and a fresh numeric stream.

Run on the instance (full internet):  python3 build_continual_data.py
Then build the tokenizer over EVERYTHING (train + continual):  python3 tokenizer.py
"""
import os, urllib.request, random, re

RAW = "https://raw.githubusercontent.com"
PHASES = {
    # phase dir            : list of (url, is_prose)
    "01_rust":   [(f"{RAW}/rust-lang/rust/master/library/alloc/src/vec/mod.rs", False),
                  (f"{RAW}/rust-lang/rust/master/library/alloc/src/string.rs", False)],
    "02_sawyer": [(f"{RAW}/GITenberg/The-Adventures-of-Tom-Sawyer_74/master/74.txt", True)],
    "03_dracula":[(f"{RAW}/GITenberg/Dracula_345/master/345.txt", True)],
}

def clean_gutenberg(t):
    m = re.search(r"\*\*\* START OF.*?\*\*\*", t, re.S)
    if m: t = t[m.end():]
    m = re.search(r"\*\*\* END OF", t, re.S)
    if m: t = t[:m.start()]
    return re.sub(r"\n{3,}", "\n\n", t.replace("\r", "")).strip()

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")

def main():
    root = "data/continual"; os.makedirs(root, exist_ok=True)
    for phase, srcs in PHASES.items():
        d = os.path.join(root, phase); os.makedirs(d, exist_ok=True)
        out = os.path.join(d, "a.txt")
        if os.path.exists(out) and os.path.getsize(out) > 50_000:
            print(f"skip {phase} (exists)"); continue
        text = ""
        for url, is_prose in srcs:
            try:
                t = fetch(url); text += (clean_gutenberg(t) if is_prose else t) + "\n"
                print(f"  {phase}: +{len(t)} from {url.split('/')[-1]}")
            except Exception as e:
                print(f"  {phase}: FAIL {url.split('/')[-1]}: {e}")
        if text:
            open(out, "w", encoding="utf-8").write(text)
            print(f"wrote {out} ({len(text)} chars)")

    # phase 04: a fresh numeric stream with a DIFFERENT seed than pretrain's num
    d = os.path.join(root, "04_num2"); os.makedirs(d, exist_ok=True)
    out = os.path.join(d, "a.txt")
    if not (os.path.exists(out) and os.path.getsize(out) > 50_000):
        random.seed(777)
        rows = [",".join(f"{random.randint(0,9999)}.{random.randint(0,99):02d}" for _ in range(6))
                for _ in range(4000)]
        open(out, "w", encoding="utf-8").write("\n".join(rows))
        print(f"wrote {out} ({sum(len(r) for r in rows)} chars)")

    print("\nphases:", sorted(os.listdir(root)))
    print("next: python3 tokenizer.py   (rebuild vocab over train+continual)")

if __name__ == "__main__":
    main()
