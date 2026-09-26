"""Aggregate d1 runs: python summarize.py [arm ...]  -> table per arm, per seed + mean, and summary.json"""
import json, glob, os, sys, statistics as S
HERE = os.path.dirname(os.path.abspath(__file__))
NONNOISE = ["hard", "easy", "cred", "false", "corrob", "late"]


def read(d):
    f = d["facts_end"]
    styles = ["null_c", "null_f", "null_r"]
    m = lambda cls, k: sum(f[s][cls][k] for s in styles) / 3
    c = d.get("counters", {}) or {}
    return {
        "mean_gap": sum(d["gap_end"][a] for a in NONNOISE) / len(NONNOISE),
        "gap_hard": d["gap_end"]["hard"], "gap_easy": d["gap_end"]["easy"],
        "gap_cred": d["gap_end"]["cred"], "gap_false": d["gap_end"]["false"],
        "gap_corrob": d["gap_end"]["corrob"], "gap_late": d["gap_end"]["late"],
        "gap_noise": d["gap_end"]["noise"],
        "noise_share": d["drawn_share"]["noise"],
        "forget_hard": d["forget_hard"], "forget_easy": d["forget_easy"],
        "Qc_share_true": m("Qc", "share_true"), "Wc_share_true": m("Wc", "share_true"),
        "Qc_acc_true": m("Qc", "acc_true"), "Wc_acc_true": m("Wc", "acc_true"),
        "Qa_acc": m("Qa", "acc_true"), "Wa_acc": m("Wa", "acc_true"),
        "probe_overhead": d.get("probe_overhead_windows_frac", 0.0),
        "wall": d["wall"],
        "lp_negative_pulls": c.get("lp_negative_pulls"), "floor_binds": c.get("floor_binds"),
        "trust_false_end": (c.get("final_trust") or {}).get("false"),
        "trust_cred_end": (c.get("final_trust") or {}).get("cred"),
    }


rows = {}
for fn in sorted(glob.glob(os.path.join(HERE, "out", "*_s*.json"))):
    d = json.load(open(fn))
    arm = os.path.basename(fn).rsplit("_s", 1)[0]
    rows.setdefault(arm, {})[d["seed"]] = read(d)
arms = sys.argv[1:] or sorted(rows)
keys = ["mean_gap", "gap_hard", "gap_easy", "gap_cred", "gap_false", "gap_corrob", "gap_late", "noise_share",
        "forget_hard", "forget_easy", "Qc_share_true", "Wc_share_true", "Qa_acc", "Wa_acc", "probe_overhead"]
out = {}
print("arm".ljust(16) + "".join(k[:12].rjust(13) for k in keys))
for arm in arms:
    if arm not in rows:
        continue
    seeds = sorted(rows[arm])
    out[arm] = {"seeds": seeds, "per_seed": rows[arm]}
    for s in seeds:
        print(f"{arm}.s{s}".ljust(16) + "".join(f"{rows[arm][s][k]:13.3f}" for k in keys))
    mean = {k: S.mean(rows[arm][s][k] for s in seeds) for k in keys}
    out[arm]["mean"] = mean
    print(f"{arm}.mean".ljust(16) + "".join(f"{mean[k]:13.3f}" for k in keys))
# paired differences vs base
if "base" in rows:
    print("\npaired diff vs base (arm - base), per seed:")
    for arm in arms:
        if arm == "base" or arm not in rows:
            continue
        common = sorted(set(rows[arm]) & set(rows["base"]))
        diffs = {k: [rows[arm][s][k] - rows["base"][s][k] for s in common] for k in keys}
        out[arm]["diff_vs_base"] = diffs
        print(arm.ljust(16) + " seeds " + str(common))
        for k in keys:
            print("   " + k.ljust(16) + " ".join(f"{v:+.3f}" for v in diffs[k]))
json.dump(out, open(os.path.join(HERE, "summary.json"), "w"), indent=1)
