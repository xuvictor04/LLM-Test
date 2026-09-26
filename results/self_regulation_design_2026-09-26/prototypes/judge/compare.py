"""Judge: paired head-to-head table on the common scoreboard (run score.py first).
Arms are assembled from all designers' post-fix runs plus the judge's reruns/new runs.
Every cell is per seed (s0/s1/s2); '-' = not run. Differences are paired by seed."""
import json, os
M = os.path.dirname(os.path.abspath(__file__))
rows = json.load(open(f"{M}/scoreboard.json"))
def pick(src):
    out = {}
    for who, arm in src:
        for r in rows:
            if r["who"] == who and r["arm"] == arm and r["paired"]:
                out.setdefault(r["seed"], r)
    return out
ARMS = {
 "base (planned, tree today)": [("d2", "base")],
 "d1 lp (LP bandit, probe)": [("d1", "lp")],
 "d1 full (lp + grad trust)": [("judge/w/d1", "full_judge"), ("d1", "full")],
 "d1 lp_train (stream signal)": [("d1", "lp_train")],
 "d1 loss-seeking": [("d1", "loss")],
 "d1 replay 20% (d1 impl)": [("d1", "replay")],
 "d3 replay 20% (d3 impl)": [("d3", "replay_fixed")],
 "d3 replay 27% (matched)": [("d3", "replay_fixed_m27"), ("judge/w/d3", "replay_fixed_m27")],
 "d3 focus (LP+rehearse+MIR)": [("d3", "focus"), ("judge/w/d3", "focus")],
 "d3 focus_nomir": [("d3", "focus_nomir")],
 "d3 fulltd (focus+claimTD)": [("d3", "fulltd"), ("judge/w/d3", "fulltd")],
 "d3 trust_td (planned+claimTD)": [("d3", "trust_td")],
 "judge fulltd act6 (tree acts)": [("judge/w/d3", "fulltd_act6")],
 "d2 tags (untagged read)": [("d2", "tags")],
 "judge graft fulltd+tags (untagged)": [("judge/w/d3", "fulltd_tags")],
}
TAGARMS = {"d2 tags": [("d2", "tags")], "judge graft fulltd+tags": [("judge/w/d3", "fulltd_tags")]}
base = pick(ARMS["base (planned, tree today)"])
def cell(d, k, s):
    return f"{d[s][k]:6.3f}" if s in d and d[s].get(k) is not None else "     -"
for k, lab in [("mean6", "mean gap, 6 learnable areas incl. false (bits/byte, null read)"),
               ("mean5", "mean gap, 5 areas excl. false"), ("late", "gap late (plasticity)"),
               ("fh", "forget hard"), ("fe", "forget easy"), ("noise", "gap noise (calibration)"),
               ("noise_draw", "noise drawn share"), ("cred", "gap cred"), ("Qc", "Qc acc (null_c)"),
               ("Qc_sh", "Qc share_true"), ("Qa", "Qa acc (agreed)")]:
    print(f"\n== {lab} ==   per seed s0/s1/s2  | paired diff vs base")
    for name, src in ARMS.items():
        d = pick(src)
        diffs = [f"{d[s][k]-base[s][k]:+.3f}" if s in d and s in base else "   -  " for s in (0, 1, 2)]
        print(f"  {name:36s} " + " ".join(cell(d, k, s) for s in (0, 1, 2)) + "  | " + " ".join(diffs))
print("\n== tagged inference (true tag) ==")
for name, src in TAGARMS.items():
    d = pick(src)
    for k in ("mean6_tag", "mean5_tag", "noise_tag", "trustQc"):
        print(f"  {name:28s} {k:10s} " + " ".join(cell(d, k, s) for s in (0, 1, 2)))
