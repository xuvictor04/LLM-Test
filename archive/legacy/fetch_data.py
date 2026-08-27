"""Diverse corpus fetch -- pulls slices from multiple public sources into data/train/<domain>/,
so the model sees more than Wikipedia. Runs ON THE INSTANCE (needs network + `pip install datasets`).

Every source is BEST-EFFORT: a failure (auth / network / dataset moved) is logged and skipped, never fatal.
New domain folders (web/, reddit/, js/, ...) become new held-out domains automatically -- exactly the
diversity the sparse experts can specialize on.

Env knobs:
  SOURCES   comma list of sources to run (default "web,code,reddit,json")
  WEB_MB    web text to pull        (default 200)
  CODE_MB   code total, split across languages (default 200)
  REDDIT_MB reddit text to pull     (default 100)
  JSON_DIR  folder of your own *.json/*.jsonl to ingest (default data/raw_json)

Usage:  python3 fetch_data.py         # runs the default source set
"""
import os, sys, json, glob

OUT = "data/train"


def write_stream(domain, texts, target_mb, tag, minlen=50):
    """Write an iterable of strings into data/train/<domain>/<tag>.txt up to target_mb megabytes."""
    path = os.path.join(OUT, domain); os.makedirs(path, exist_ok=True)
    fp = os.path.join(path, f"{tag}.txt"); written = 0; limit = int(target_mb * 1_000_000); n = 0
    try:
        with open(fp, "w", encoding="utf-8") as f:
            for t in texts:
                if not t: continue
                t = t.strip()
                if len(t) < minlen: continue
                f.write(t + "\n\n"); written += len(t) + 2; n += 1
                if written >= limit: break
    except Exception as e:
        print(f"  [{tag}] stopped mid-stream: {str(e)[:100]}")
    print(f"  [{tag}] -> {domain}/ : {written/1e6:.1f} MB ({n} docs)")
    return written


def _hf(repo, **kw):
    from datasets import load_dataset
    return load_dataset(repo, split=kw.pop("split", "train"), streaming=True, **kw)


def fetch_web(target_mb):
    """Web crawl text (varied register, unlike Wikipedia). FineWeb, falling back to OpenWebText."""
    for name, field, kw in [("HuggingFaceFW/fineweb", "text", {"name": "sample-10BT"}),
                            ("Skylion007/openwebtext", "text", {}),
                            ("stas/openwebtext-10k", "text", {})]:
        try:
            print(f"  web: {name} ...")
            ds = _hf(name, **kw)
            return write_stream("web", (ex.get(field, "") for ex in ds), target_mb, "web")
        except Exception as e:
            print(f"  web: {name} failed ({str(e)[:90]})")
    return 0


def fetch_code(total_mb):
    """Source code routed into per-language domain folders so experts can specialize by language."""
    LANGS = {"Python": "py", "JavaScript": "js", "C": "c", "C++": "cpp",
             "Java": "java", "Go": "go", "Rust": "rust", "TypeScript": "ts"}
    per = max(1, total_mb // len(LANGS)); lim = per * 1_000_000
    written = {v: 0 for v in LANGS.values()}; files = {}
    ds = None
    for name, kw in [("codeparrot/github-code", {"trust_remote_code": True}), ("bigcode/the-stack-smol", {})]:
        try:
            print(f"  code: {name} ...")
            ds = _hf(name, **kw); break
        except Exception as e:
            print(f"  code: {name} failed ({str(e)[:90]})")
    if ds is None:
        return 0
    done = set()
    try:
        for ex in ds:
            lang = ex.get("language") or ex.get("lang") or ""
            code = ex.get("code") or ex.get("content") or ""
            dom = LANGS.get(lang)
            if not dom or written[dom] >= lim:
                if len(done) >= len(set(LANGS.values())): break
                continue
            if dom not in files:
                p = os.path.join(OUT, dom); os.makedirs(p, exist_ok=True)
                files[dom] = open(os.path.join(p, "github.txt"), "w", encoding="utf-8")
            files[dom].write(code.strip() + "\n\n"); written[dom] += len(code)
            if written[dom] >= lim: done.add(dom)
            if len(done) >= len(set(LANGS.values())): break
    except Exception as e:
        print(f"  code: stopped ({str(e)[:90]})")
    for f in files.values():
        f.close()
    tot = sum(written.values())
    print(f"  code: {tot/1e6:.1f} MB across {sorted(files)}")
    return tot


def fetch_reddit(target_mb):
    """Reddit posts/comments (conversational register). HF datasets, best-effort."""
    for name, field, kw in [("webis/tldr-17", "content", {}),
                            ("SocialGrep/one-million-reddit-questions", "selftext", {}),
                            ("reddit", "body", {})]:
        try:
            print(f"  reddit: {name} ...")
            ds = _hf(name, **kw)
            return write_stream("reddit", (ex.get(field, "") for ex in ds), target_mb, "reddit")
        except Exception as e:
            print(f"  reddit: {name} failed ({str(e)[:90]})")
    return 0


def ingest_json(src_dir, domain="reddit", target_mb=99999):
    """Ingest your OWN *.json / *.jsonl (e.g. Reddit dumps). Extracts common text fields.
    Handles line-delimited JSONL and whole-file JSON arrays. Drop files in JSON_DIR and they get folded in."""
    files = sorted(glob.glob(os.path.join(src_dir, "*.json")) + glob.glob(os.path.join(src_dir, "*.jsonl")))
    if not files:
        return 0
    FIELDS = ("body", "selftext", "content", "text", "title", "comment", "message")
    def pull(obj):
        if isinstance(obj, dict):
            for k in FIELDS:
                if obj.get(k): return obj[k]
        return None
    def texts():
        for fp in files:
            raw = open(fp, encoding="utf-8", errors="ignore").read().strip()
            # try whole-file JSON (array or object) first
            try:
                data = json.loads(raw)
                for o in (data if isinstance(data, list) else [data]):
                    t = pull(o)
                    if t: yield t
                continue
            except Exception:
                pass
            # else line-delimited JSONL
            for line in raw.splitlines():
                line = line.strip()
                if not line: continue
                try:
                    t = pull(json.loads(line))
                    if t: yield t
                except Exception:
                    continue
    return write_stream(domain, texts(), target_mb, "user_json")


if __name__ == "__main__":
    sources = os.environ.get("SOURCES", "web,code,reddit,json").split(",")
    web_mb = int(os.environ.get("WEB_MB", 200))
    code_mb = int(os.environ.get("CODE_MB", 200))
    reddit_mb = int(os.environ.get("REDDIT_MB", 100))
    json_dir = os.environ.get("JSON_DIR", "data/raw_json")
    print(f"diverse fetch | sources={sources} | web={web_mb}MB code={code_mb}MB reddit={reddit_mb}MB")
    total = 0
    if "web" in sources:    total += fetch_web(web_mb)
    if "code" in sources:   total += fetch_code(code_mb)
    if "reddit" in sources: total += fetch_reddit(reddit_mb)
    if "json" in sources:   total += ingest_json(json_dir)
    print(f"diverse fetch done: {total/1e6:.1f} MB added across new domains under {OUT}/")
    if total == 0:
        print("  (nothing fetched -- sources may need `pip install datasets`, an HF account, or network. Non-fatal.)")
