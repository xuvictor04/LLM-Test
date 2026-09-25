"""Summarise res/drift_s*.json and res/flipdist_s*.json. Usage: python3 drift_summary.py"""
import json, glob
ds = [json.load(open(f)) for f in sorted(glob.glob("res/drift_s*.json"))]
print("EMA decay sweep (nested codec, codec-only). flip_d500 = fraction of 50-fps frame codes changed over 500 codec steps = 1000 LM windows at AUD_TRAIN_EVERY=2;")
print("measured at codec step 500 (end of tones-only) and 1000 (end of melody+tones). l1 = log-mag L1 of the teacher's reconstruction on the probe set.")
for dec in ds[0]["decays"]:
    cells = []
    for st in (500, 1000):
        vals = []
        for d in ds:
            row = [r for r in d["curve"] if r["codec_step"] == st][0]
            vals.append((row.get(f"{dec}/tones/flip_d500"), row.get(f"{dec}/tones/flipS2_d500"), row.get(f"{dec}/melody/flip_d500"),
                         row.get(f"{dec}/tones/zdrift_d500"), row[f"{dec}/tones/l1"], row[f"{dec}/melody/l1"], row[f"{dec}/tones/pos"], row[f"{dec}/melody/pos"]))
        cells.append(f"@{st}: " + " ; ".join(f"s{d['seed']} flip {v[0]} flipS2 {v[1]} mflip {v[2]} zd {v[3]} l1 {v[4]}/{v[5]} pos {v[6]}/{v[7]}" for d, v in zip(ds, vals)))
    print(f"decay {dec}:\n   " + "\n   ".join(cells))
print("\nshort horizon flips (d50 = 100 LM windows), mean over measure points 100..500 (tones phase) and 600..1000 (melody phase):")
for dec in ds[0]["decays"]:
    out = []
    for d in ds:
        a = [r.get(f"{dec}/tones/flip_d50") for r in d["curve"] if 100 <= r["codec_step"] <= 500]
        b = [r.get(f"{dec}/tones/flip_d50") for r in d["curve"] if 600 <= r["codec_step"] <= 1000]
        out.append(f"s{d['seed']}: {sum(a)/len(a):.3f} / {sum(b)/len(b):.3f}")
    print(f"  decay {dec}: " + " | ".join(out))
print("\nallocation (teacher 0.995): pos/s, mel, probe exact per area")
for key in ("alloc_start", "alloc_end", "alloc_end_frozen"):
    print(key)
    for tag in ds[0][key]:
        print("  ", tag, " | ".join(f"s{d['seed']} " + " ".join(f"{ar}: {v['pos_per_s']}/s mel {v['mel']} px {v['probe_exact']}" for ar, v in d[key][tag].items()) for d in ds))
print("\nflip destinations (spec25):")
for f in sorted(glob.glob("res/flipdist_s*.json")):
    r = json.load(open(f))
    for k, v in r.items():
        print(" ", f[-7:-5], k, v)
