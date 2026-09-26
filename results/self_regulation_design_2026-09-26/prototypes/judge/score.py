"""Judge: one common scoreboard over every designer's result JSON (same testbed, 4,000,000 bytes).
Flags runs whose corpus differs from the post-fix corpus (d1 base_s0, full_s0 made before the
PYTHONHASHSEED fix) by comparing the cred oracle to the post-fix base of the same seed.
Usage: python3 score.py [extra_glob ...]"""
import json, glob, os, sys, statistics as stt
M = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
L6 = ["hard", "easy", "cred", "false", "corrob", "late"]
L5 = ["hard", "easy", "cred", "corrob", "late"]
ref = {s: json.load(open(f"{M}/d2/out/base_s{s}.json"))["oracle"]["cred"] for s in (0, 1, 2)}
files = sorted(glob.glob(f"{M}/d[123]/out/*_s[0-9].json")) + sorted(glob.glob(f"{M}/judge/w/d[123]/out/*_s[0-9].json"))
rows = []
for f in files:
    j = json.load(open(f)); s = j["seed"]
    if j.get("bytes", 4000000) != 4000000 and "_cm" not in f:
        continue
    who = f.split("/out/")[0].replace(M + "/", "")
    arm = os.path.basename(f).rsplit("_s", 1)[0]
    ok = abs(j["oracle"]["cred"] - ref[s]) < 1e-9 if s in ref else None
    g = j["gap_end"]
    fc = j["facts_end"]["null_c"]
    r = dict(who=who, arm=arm, seed=s, paired=ok,
             mean6=sum(g[n] for n in L6) / 6, mean5=sum(g[n] for n in L5) / 5,
             noise=g["noise"], hard=g["hard"], easy=g["easy"], cred=g["cred"], false=g["false"],
             corrob=g["corrob"], late=g["late"], fe=j["forget_easy"], fh=j["forget_hard"],
             noise_draw=j["drawn_share"]["noise"], Qc=fc["Qc"]["acc_true"], Qc_sh=fc["Qc"]["share_true"],
             Wc=fc["Wc"]["acc_true"], Qa=fc["Qa"]["acc_true"], Wa=fc["Wa"]["acc_true"])
    if "bpb_end_tag" in j:
        t = j["bpb_end_tag"]; o = j["oracle"]
        r["mean6_tag"] = sum(t[n] - o[n] for n in L6) / 6
        r["mean5_tag"] = sum(t[n] - o[n] for n in L5) / 5
        r["noise_tag"] = t["noise"] - o["noise"]
        r["trustQc"] = j.get("trusted_tag_acc", {}).get("Qc")
    rows.append(r)
cols = ["mean6", "mean5", "noise", "cred", "false", "late", "fe", "fh", "noise_draw", "Qc", "Qc_sh", "Qa", "Wa"]
print(f"{'who/arm':30s} s ok " + " ".join(f"{c:>6s}" for c in cols) + "  tag:mean6 mean5 noise trustQc")
for r in rows:
    extra = ""
    if "mean6_tag" in r:
        extra = f"  {r['mean6_tag']:6.3f} {r['mean5_tag']:6.3f} {r['noise_tag']:6.3f} {r['trustQc']}"
    print(f"{r['who']+'/'+r['arm']:30s} {r['seed']} {'Y' if r['paired'] else 'N'}  " + " ".join(f"{r[c]:6.3f}" for c in cols) + extra)
json.dump(rows, open(f"{M}/judge/scoreboard.json", "w"), indent=1)
