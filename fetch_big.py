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
  the-stack    bigcode/the-stack           CODE, by language. GATED -- see below.
Or pass any HF dataset id directly:  --dataset some/dataset --config en --field text

GATED DATASETS (the-stack and friends) need the terms accepted in a browser AND a token:
    1. sign in and accept at  https://huggingface.co/datasets/bigcode/the-stack
    2. export HF_TOKEN=hf_...        (read scope is enough)   or   huggingface-cli login
    3. python3 fetch_big.py --dataset the-stack --data-dir data/python --domain py --gb 0.03
Step 1 is the one people skip; without it a perfectly valid token still returns 401/403.
"""
import argparse, json, os, sys, time

PRESETS = {
    "fineweb-edu": dict(path="HuggingFaceFW/fineweb-edu", config="sample-10BT", field="text", split="train"),
    "c4":          dict(path="allenai/c4",                config="en",          field="text", split="train"),
    "openwebtext": dict(path="Skylion007/openwebtext",    config=None,          field="text", split="train"),
    "wikipedia":   dict(path="wikimedia/wikipedia",       config="20231101.en", field="text", split="train"),
    "oasst1":      dict(path="OpenAssistant/oasst1",      config=None,          field="text", split="train"),
    "pile":        dict(path="monology/pile-uncopyrighted", config=None,        field="text", split="train"),
    # CODE. Both are GATED: the terms must be accepted on the dataset page in a browser before any token works.
    # Organised by LANGUAGE as directories, not configs, so pick one with --data-dir data/python. The text lives
    # in `content`, not `text` -- with the default field this failed on a KeyError after authenticating, which
    # reads like an auth problem and is not one.
    "the-stack":     dict(path="bigcode/the-stack",       config=None, field="content", split="train"),
    "the-stack-dedup": dict(path="bigcode/the-stack-dedup", config=None, field="content", split="train"),
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
    ap.add_argument("--min-score", type=float, default=None,
                    help="skip documents whose --score-field is below this. fineweb-edu carries an educational-"
                         "quality classifier score in `score` (roughly 0-5); >=3 is a markedly cleaner slice than "
                         "the default >=2.5 the sample already applies. Silently does nothing if the field is "
                         "absent, so it is safe to pass to any dataset -- the count of skipped documents is "
                         "reported at the end either way.")
    ap.add_argument("--score-field", default="score")
    ap.add_argument("--data-dir", default=None,
                    help="subdirectory within the dataset repo (the-stack: data/python, data/c, ...)")
    ap.add_argument("--token", default=None,
                    help="HF access token. Defaults to $HF_TOKEN / $HUGGINGFACE_HUB_TOKEN, then to whatever "
                         "`huggingface-cli login` cached. Needed for GATED datasets -- and the terms must ALSO "
                         "be accepted on the dataset page first; a token alone does not open a gated repo.")
    ap.add_argument("--resume", action="store_true",
                    help="continue a previous pull instead of overwriting it (see the manifest note below)")
    a = ap.parse_args()

    # A PRESET IS FOUND BY ITS SHORT KEY *OR* BY THE DATASET ID IT POINTS AT. Both name the same thing, and
    # only one of them used to work. `--dataset the-stack-dedup` resolved field="content"; `--dataset
    # bigcode/the-stack-dedup` -- the id printed on the dataset page, the id in this file's own gated-dataset
    # instructions, and the id longrun.sh's round18 note told people to run -- missed the table entirely and
    # fell through to field="text". The docstring above already describes what happens next: "with the default
    # field this failed on a KeyError after authenticating, which reads like an auth problem and is not one."
    # So the documented command could not have worked even with a valid token and the terms accepted.
    _by_path = {v["path"]: k for k, v in PRESETS.items()}
    _key = a.dataset if a.dataset in PRESETS else _by_path.get(a.dataset)
    p = PRESETS.get(_key) if _key else None
    if p is None:
        p = dict(path=a.dataset, config=a.config, field="text", split="train")
    else:
        print(f"[fetch_big] preset {_key}: field={p.get('field', 'text')!r}"
              + (f" config={p['config']!r}" if p.get("config") else "")
              + (f" data_dir={p['data_dir']!r}" if p.get("data_dir") else ""))
    path = p["path"]; config = a.config or p.get("config"); field = a.field or p.get("field", "text")
    split = a.split or p.get("split", "train")

    outdir = os.path.join(a.out, "train", a.domain)
    os.makedirs(outdir, exist_ok=True)
    target = int(a.gb * 1e9)
    print(f"[fetch_big] {path}" + (f" ({config})" if config else "") + f" -> {outdir}  target {a.gb} GB")
    # WHOSE CORPUS IS ALREADY IN THERE -- ASKED BEFORE THE NETWORK IS TOUCHED. The manifest used to record only
    # how far the last pull got, so a directory holding one corpus was indistinguishable from a directory
    # holding another, and --resume would continue the OTHER dataset's byte count into these shards. Checked
    # here rather than beside the resume read below because opening the dataset first turns a bookkeeping
    # question into a network round trip, and on a gated repo into an authorisation error that hides it.
    _mp0 = os.path.join(outdir, "_fetch_manifest.json")
    if os.path.exists(_mp0):
        try:
            _was = (json.load(open(_mp0)) or {}).get("source")
        except Exception:
            _was = None
        if _was and _was != path:
            sys.exit(
                f"[fetch_big] {outdir} already holds a corpus pulled from {_was}, and this call asks for {path}.\n"
                f"  Writing into it would leave a directory that is part one corpus and part the other, with a\n"
                f"  manifest describing neither, and every number a run reports on it would be about a mixture\n"
                f"  nobody chose. Nothing here deletes your corpus:\n"
                f"    mv {outdir} {outdir}.{_was.replace('/', '_')}     # then re-run to pull {path}\n"
                + (f"    (what is on disk was built by fetch_local.py, not by any --dataset; keep it by running\n"
                   f"     the pilot with 'local' as the dataset argument instead)\n"
                   if _was == "local" else
                   f"    --dataset {_was}                                  # keep what is on disk\n")
                + f"    --out <another directory>                         # both, side by side")

    # THE LIBRARY IS NEEDED FOR THE PULL, NOT FOR THE BOOKKEEPING ABOVE. Checking provenance first means a
    # wrong-corpus mistake is reported as a wrong-corpus mistake, on any machine, instead of as a missing
    # dependency or -- on a gated repo -- as an authorisation error that hides it entirely.
    try:
        from datasets import load_dataset
    except ImportError:
        sys.exit("need: pip install datasets")

    kw = dict(split=split, streaming=True)
    if config: kw["name"] = config
    data_dir = a.data_dir or p.get("data_dir")
    if data_dir: kw["data_dir"] = data_dir
    # THE STACK IS ORGANISED BY LANGUAGE AS DIRECTORIES. Without --data-dir it streams EVERY language, so a
    # pull labelled --domain py delivers a mixture of Python, Java, JavaScript, HTML and generated files. The
    # run then trains on it, calls it "py" in every per-domain line, and measures the cost of adding "Python"
    # against something that is not mostly Python. Nothing downstream can detect that, which is why it is said
    # here rather than left to be noticed.
    elif "the-stack" in path:
        print(f"[fetch_big] !! no --data-dir: {path} is organised by LANGUAGE as directories, so this streams "
              f"ALL of them mixed together.\n"
              f"             For one language:  --data-dir data/{a.domain}   (data/python, data/c, data/java, ...)\n"
              f"             Continuing with the mixture -- it will be labelled --domain {a.domain!r} regardless.")

    # AUTH, EXPLICITLY. Relying on the ambient credential means "works on my machine" and an opaque 401 on
    # anyone else's. Order: --token, then the environment, then whatever huggingface-cli cached (token=None lets
    # the library find it). `token=` replaced `use_auth_token=` in datasets 2.14; accept both so an older pin
    # still works rather than dying on an unexpected keyword.
    tok = a.token or os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_HUB_TOKEN")
    if tok: kw["token"] = tok
    try:
        ds = load_dataset(path, **kw)
    except TypeError as e:
        if tok and "token" in str(e):
            kw.pop("token"); kw["use_auth_token"] = tok        # datasets < 2.14
            ds = load_dataset(path, **kw)
        else:
            raise
    except Exception as e:
        # A GATED REPO AND A BAD TOKEN LOOK THE SAME from here, and the fix is different, so say both.
        _m = str(e)
        if any(k in _m for k in ("401", "403", "gated", "Gated", "restricted", "authenticated")):
            sys.exit(
                f"[fetch_big] cannot read {path}: {type(e).__name__}: {_m}\n"
                f"  Gated datasets need TWO things, and a token is only one of them:\n"
                f"    1. accept the terms, signed in, at  https://huggingface.co/datasets/{path}\n"
                f"       (this is per-dataset and cannot be done from the CLI)\n"
                f"    2. make the token visible here -- either\n"
                f"         export HF_TOKEN=hf_...        (or pass --token hf_...)\n"
                f"       or  huggingface-cli login\n"
                f"  Token seen by this process: {'yes' if tok else 'NO -- neither --token nor $HF_TOKEN is set'}.\n"
                f"  The token needs only READ scope.\n"
                f"  OR SKIP THE ACCOUNT ENTIRELY. Both code presets here are gated, and the continual-learning\n"
                f"  experiment only needs the second area to be a DIFFERENT DISTRIBUTION from the first -- not\n"
                f"  this particular corpus. fetch_local.py builds one from source already on this machine:\n"
                f"    python3 fetch_local.py --domain {a.domain} --out {a.out} --gb {a.gb}\n"
                f"    bash longrun.sh pilot-add {a.domain} local {a.gb}\n"
                f"  ('local' makes pilot-add skip the fetch, so populating the directory is all it takes.)")
        raise

    is_dialogue = a.dataset == "oasst1"
    # RESUME. A 40 GB pull is hours long and HF streaming has no seek, so a mid-way failure used to mean starting
    # over: the writer always began at part000 and re-streamed from document 0. We record (docs_consumed,
    # bytes_written, shard) in a manifest after every shard, and on --resume skip that many documents with
    # IterableDataset.skip() and continue at the next shard index. Skipping still walks the stream, but it neither
    # decodes nor writes, so it is far cheaper than re-downloading.
    man_path = os.path.join(outdir, "_fetch_manifest.json")

    # WHAT IS IN THIS DIRECTORY, not merely how far the last pull got. The manifest recorded bytes/shard/docs
    # and nothing about the SOURCE, so a directory already holding one corpus was indistinguishable from a
    # directory holding another -- and both --resume here and pilot-add's "is it big enough" test would accept
    # it. The concrete case: `pilot-add py local` builds 57 MB of stdlib Python into data_pilot/train/py; the
    # next day the-stack-dedup's terms are accepted and `pilot-add py bigcode/the-stack-dedup` finds 57 MB
    # already there, skips the fetch, and trains on the interpreter's source while the log says the-stack. The
    # run reports on a corpus nobody chose.
    def _man(b, sh, dc):
        return {"bytes": b, "shard": sh, "docs": dc, "source": path,
                "data_dir": data_dir, "domain": a.domain}   # the RESOLVED data_dir (preset or --data-dir)
    written = shard = docs_done = 0; n_lowscore = 0
    if a.resume and os.path.exists(man_path):
        try:
            man = json.load(open(man_path))
            written, shard, docs_done = int(man["bytes"]), int(man["shard"]) + 1, int(man["docs"])
            print(f"[fetch_big] RESUME: {written/1e9:.2f} GB already on disk in {shard} shard(s); "
                  f"skipping {docs_done:,} documents already consumed")
            ds = ds.skip(docs_done)
        except (ValueError, KeyError, OSError) as e:
            print(f"[fetch_big] manifest unusable ({e}) -- starting fresh"); written = shard = docs_done = 0
    elif a.resume:
        print("[fetch_big] --resume given but no manifest found -- starting fresh")
    if written >= target:
        print(f"[fetch_big] target already met ({written/1e9:.2f} GB >= {a.gb} GB); nothing to do"); return
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
                # QUALITY GATE, on the dataset's OWN score rather than a heuristic of ours. Counted, not silent:
                # a filter that drops 90% of the stream and says nothing turns "the pull is slow" into a mystery.
                if a.min_score is not None:
                    _sc = rec.get(a.score_field)
                    if _sc is not None and float(_sc) < a.min_score:
                        n_lowscore += 1; continue
                txt = txt.strip() + "\n\n"
            f.write(txt); written += len(txt.encode("utf-8", "replace"))
            if written // (a.shard_mb * 1_000_000) > shard:
                f.close()
                json.dump(_man(written, shard, docs_done + i + 1), open(man_path, "w"))
                shard += 1
                f = open(os.path.join(outdir, f"part{shard:03d}.txt"), "w", encoding="utf-8")
            if i % 20000 == 0 and i:
                el = time.time() - t0
                print(f"  {written/1e9:6.2f} GB  ({written/max(1,el)/1e6:5.1f} MB/s)  docs {i:,}", flush=True)
            if written >= target: break
    except KeyboardInterrupt:
        print("\n  interrupted -- keeping what was written")
    finally:
        f.close()
        try: json.dump(_man(written, shard, docs_done + i + 1), open(man_path, "w"))
        except (NameError, OSError): pass

    print(f"[fetch_big] wrote {written/1e9:.2f} GB in {shard+1} shard(s) to {outdir}"
          + (f" | --min-score {a.min_score} skipped {n_lowscore} document(s) on `{a.score_field}`"
             if a.min_score is not None else ""))
    if a.min_score is not None and n_lowscore == 0:
        print(f"[fetch_big] NOTE: --min-score was set and skipped NOTHING. Either every document passed, or this "
              f"dataset has no `{a.score_field}` field and the gate did nothing at all -- those look identical "
              f"from here, and only one of them means what you asked for.")
    tag = a.dataset.replace("/", "_")
    stream_len = int(written * 0.9)
    # Only stack the heavy knobs (long windows / big vocab) for a genuinely LARGE corpus; on a small pull they just
    # make a 40-min run take many hours. ALWAYS include CKPT_EVERY (killable/promptable mid-run) + RUN_NAME (isolates artifacts).
    heavy = written >= 250_000_000
    # ACCUM=4 STAYS, AND IT NOW MEANS WHAT IT SAYS. This line recommended ACCUM=4 alongside BATCH_W=16 while
    # self_organize.py gated the optimizer on `(step + 1) % ACCUM == 0` -- a step counter that advances per
    # WINDOW, tested in a body that runs once per FLUSH. With gcd(16, 4) = 4 that was all-or-nothing per epoch:
    # depending on where the epoch's first step landed, the optimizer either ran on every flush (accumulating
    # nothing, so ACCUM did nothing) or NEVER RAN AT ALL for the whole epoch. Three of four offsets gave zero
    # steps, ACCUM is printed nowhere, and this is the command the repo tells people to launch for the heavy
    # run. The gate counts backward passes now, so this recommendation is safe -- but only from that commit on:
    # a run launched from an older tree with these knobs may have trained nothing and said so nowhere.
    knobs = " WIN=256 BATCH_W=16 ACCUM=4 D_MODEL=768 VMAX=16384" if heavy else ""
    print(f"\nNext ({'large corpus -> heavy config' if heavy else 'small corpus -> light defaults'}; "
          f"CKPT_EVERY = saves every N steps so a crash never loses everything):\n"
          f"  DATA_DIR={a.out} CORPUS_CAP=2000000000 STREAM_LEN={stream_len} CKPT_EVERY=40000 RUN_NAME={tag}{knobs} bash run_full_unfrozen.sh")


if __name__ == "__main__":
    main()
    # HF `datasets` streaming leaves background download threads alive; normal interpreter shutdown then crashes them
    # ("PyGILState_Release: no thread-state" / "Bad file descriptor") AFTER our data is safely written. Skip that noisy
    # teardown with a hard exit -- stdout is already flushed by the prints above.
    sys.stdout.flush()
    os._exit(0)
