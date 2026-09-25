"""Wall-clock per training step, measured back to back in ONE process on one thread (no contention between
arms): text step, codec-only step, media step (P2 mix: 12 tones rows + 4 text rows), for base (frozen
FSQ, codes encoded under no_grad at the cut) and d2 (live codec, e2e) and d2_frozen.
Usage: bench_step.py OUT.json"""
import os, sys, time, json, torch
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import d2run as R


def timeit(fn, n=25, warm=5):
    for _ in range(warm):
        fn()
    t = time.time()
    for _ in range(n):
        fn()
    return round((time.time() - t) / n, 4)


out = {}
for arm in ("base", "d2", "d2_frozen"):
    r = R.Run(arm, 0)
    res = dict(text_step=timeit(r.text_step), codec_only_step=timeit(r.codec_only_step))
    if arm != "d2":
        r.frozen = True
        for p in r.codec.parameters():
            p.requires_grad_(False)
    res["media_step_P2"] = timeit(lambda: r.media_step([("A", 12)]))
    out[arm] = res
    print(arm, res, flush=True)
json.dump(out, open(sys.argv[1], "w"), indent=1)
