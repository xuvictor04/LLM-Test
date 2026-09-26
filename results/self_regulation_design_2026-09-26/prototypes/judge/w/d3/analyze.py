"""Aggregate d3 results: per-seed readings and paired differences vs base. Usage: python analyze.py"""
import json, os, glob, statistics
HERE = os.path.dirname(os.path.abspath(__file__))
AREAS = ["hard", "easy", "noise", "cred", "false", "corrob", "late"]
R = {}
for f in sorted(glob.glob(os.path.join(HERE, "out", "*.json"))):
    d = json.load(open(f))
    R[(d["arm"] + d.get("args", {}).get("tag", ""), d["seed"])] = d


def read(d):
    g = d["gap_end"]
    fc = d["facts_end"]
    out = {
        "gap_hard": g["hard"], "gap_easy": g["easy"], "gap_noise": g["noise"], "gap_cred": g["cred"],
        "gap_false": g["false"], "gap_corrob": g["corrob"], "gap_late": g["late"],
        "gap_mean6": statistics.mean(g[a] for a in AREAS if a != "noise"),
        "forget_hard": d["forget_hard"], "forget_easy": d["forget_easy"],
        "noise_share": d["drawn_share"]["noise"],
        "late_share": d["drawn_share"]["late"],
        "faded_share_P3": sum(d.get("phase_drawn_share", [{}] * 4)[3].get(a, 0) for a in ("hard", "easy")) if "phase_drawn_share" in d else 0.0,
        "Qc_true_c": fc["null_c"]["Qc"]["acc_true"], "Qc_false_c": fc["null_c"]["Qc"]["acc_false"],
        "Qc_share_c": fc["null_c"]["Qc"]["share_true"],
        "Wc_true_c": fc["null_c"]["Wc"]["acc_true"], "Wc_share_c": fc["null_c"]["Wc"]["share_true"],
        "Qc_true_f": fc["null_f"]["Qc"]["acc_true"],
        "wall": d["wall"],
    }
    return out


arms = sorted(set(a for a, s in R))
keys = list(read(next(iter(R.values()))).keys())
table = {}
for arm in arms:
    seeds = sorted(s for a, s in R if a == arm)
    table[arm] = {s: read(R[(arm, s)]) for s in seeds}
print("per-seed readings (bits/byte gaps = held-out null minus oracle; facts on null_c prompts)")
for k in keys:
    print(f"\n{k}")
    for arm in arms:
        vals = table[arm]
        row = " ".join(f"s{s}={v[k]:.3f}" for s, v in vals.items())
        dif = ""
        if arm != "base" and not arm.startswith("mf"):
            ds = [vals[s][k] - table["base"][s][k] for s in vals if s in table.get("base", {})]
            if ds:
                dif = f"  | paired diff vs base: " + " ".join(f"{x:+.3f}" for x in ds) + f"  mean {statistics.mean(ds):+.3f}"
        if arm == "mf_trust" and "mf_base" in table:
            ds = [vals[s][k] - table["mf_base"][s][k] for s in vals if s in table["mf_base"]]
            dif = f"  | vs mf_base: " + " ".join(f"{x:+.3f}" for x in ds)
        print(f"  {arm:13s} {row}{dif}")
print("\ncounters / trust / focus")
for (arm, s), d in sorted(R.items()):
    extra = ""
    if "trust_at_eval" in d:
        extra += " trust_end=" + json.dumps(d["trust_at_eval"][-1]["trust"])
    if "rho_by_phase" in d:
        extra += " rho_by_phase=" + json.dumps([round(x, 3) for x in d["rho_by_phase"]])
    print(f"{arm} s{s} wall={d['wall']:.0f}s probe={d.get('wall_probe',0):.0f}s trust={d.get('wall_trust',0):.0f}s counters={json.dumps(d['counters'])}{extra}")
json.dump({arm: {str(s): v for s, v in t.items()} for arm, t in table.items()}, open(os.path.join(HERE, "summary.json"), "w"), indent=1)
