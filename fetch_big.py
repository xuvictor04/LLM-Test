#!/usr/bin/env python3
"""fetch_big.py — pull a SLICE of an established dataset into the DATA_DIR layout.

Streams: it never downloads the whole dataset. A 5 GB slice of a 300 GB corpus costs 5 GB of transfer.
(Written to be run on YOUR machine: this sandbox's network is allowlisted to GitHub/PyPI only, so I cannot
reach HuggingFace/S3 to test the streaming path end-to-end. Everything except the actual download is tested.)

    pip install datasets
    python3 fetch_big.py --dataset fineweb-edu --gb 5
    python3 fetch_big.py --dataset c4 --gb 25 --out data_huge
    python3 fetch_big.py --dataset oasst1 --gb 1        # dialogue: teaches TURN-TAKING

then:
    DATA_DIR=data_big CORPUS_CAP=2000000000 STREAM_LEN=... BATCH_W=16 bash run_full_unfrozen.sh

Presets (--dataset):
  fineweb-edu  HuggingFaceFW/fineweb-edu   quality-filtered web text. BEST text-per-byte; start here.
  c4           allenai/c4 (en)             cleaned Common Crawl, the well-understood default.
  openwebtext  Skylion007/openwebtext      GPT-2's actual training distribution (like-for-like comparison).
  wikipedia    wikimedia/wikipedia (en)    encyclopedic prose, very clean.
  oasst1       OpenAssistant/oasst1        DIALOGUE. Formats as turn-marked conversations.
  pile         monology/pile-uncopyrighted mixed-domain (books/code/papers/web).
Or pass any HF dataset id directly:  --dataset some/dataset --config en --field text
"""
import argparse, json, os, sys, time

PRESETS = {
    "fineweb-edu": dict(path="HuggingFaceFW/fineweb-edu", config="sample-10BT", field="text", split="train"),
    "c4":          dict(path="allenai/c4",                config="en",          field="text", split="train"),
    "openwebtext": dict(path="Skylion007/openwebtext",    config=None,          field="text", split="train"),
    "wikipedia":   dict(path="wikimedia/wikipedia",       config="20231101.en", field="text", split="train"),
    "oasst1":      dict(path="OpenAssistant/oasst1",      config=None,          field="text", split="train"),
    "pile":        dict(path="monology/pile-uncopyrighted", config=None,        field="text", split="train"),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="fineweb-edu")
    ap.add_argument("--config", default=None)
    ap.add_argument("--field", default=None)
    ap.add_argument("--split", default=None)
    ap.add_argument("--gb", type=float, default=5.0, help="how many GB of TEXT to write")
    ap.add_argument("--out", default="data_big")
    ap.add_argument("--domain", default="eng", help="which DATA_DIR domain to fill (eng/py/num/c/...)")
    ap.add_argument("--shard-mb", type=int, default=512, help="split output into shards of this size")
    ap.add_argument("--min-chars", type=int, default=200, help="skip very short documents")
    a = ap.parse_args()

    p = PRESETS.get(a.dataset, dict(path=a.dataset, config=a.config, field="text", split="train"))
    path = p["path"]; config = a.config or p.get("config"); field = a.field or p.get("field", "text")
    split = a.split or p.get("split", "train")

    try:
        from datasets import load_dataset
    except ImportError:
        sys.exit("need: pip install datasets")

    outdir = os.path.join(a.out, "train", a.domain)
    os.makedirs(outdir, exist_ok=True)
    target = int(a.gb * 1e9)
    print(f"[fetch_big] {path}" + (f" ({config})" if config else "") + f" -> {outdir}  target {a.gb} GB")

    kw = dict(split=split, streaming=True)
    if config: kw["name"] = config
    ds = load_dataset(path, **kw)

    is_dialogue = a.dataset == "oasst1"
    written = shard = 0
    t0 = time.time()
    f = open(os.path.join(outdir, f"part{shard:03d}.txt"), "w", encoding="utf-8")
    try:
        for i, rec in enumerate(ds):
            if is_dialogue:                                  # turn-marked so the model can learn EXCHANGE structure
                role = rec.get("role", "")
                txt = rec.get("text", "") or ""
                if not txt.strip(): continue
                txt = f"<|{'user' if role == 'prompter' else 'assistant'}|> {txt.strip()}\n"
            else:
                txt = (rec.get(field) or "")
                if len(txt) < a.min_chars: continue
                txt = txt.strip() + "\n\n"
            f.write(txt); written += len(txt.encode("utf-8", "replace"))
            if written // (a.shard_mb * 1_000_000) > shard:
                f.close(); shard += 1
                f = open(os.path.join(outdir, f"part{shard:03d}.txt"), "w", encoding="utf-8")
            if i % 20000 == 0 and i:
                el = time.time() - t0
                print(f"  {written/1e9:6.2f} GB  ({written/max(1,el)/1e6:5.1f} MB/s)  docs {i:,}", flush=True)
            if written >= target: break
    except KeyboardInterrupt:
        print("\n  interrupted -- keeping what was written")
    finally:
        f.close()

    print(f"[fetch_big] wrote {written/1e9:.2f} GB in {shard+1} shard(s) to {outdir}")
    print(f"\nNext:\n  DATA_DIR={a.out} CORPUS_CAP=2000000000 STREAM_LEN={int(written*0.9)} \\\n"
          f"    WIN=256 BATCH_W=16 ACCUM=4 D_MODEL_B=768 VMAX=16384 bash run_full_unfrozen.sh")


if __name__ == "__main__":
    main()
