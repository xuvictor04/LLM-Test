"""Emergence / did-it-fire gauges per run: python gauges.py [arm ...]
  plan trajectory: mean planned share per area over probes in P0-P2 (frac<0.75) and P3
  counters: plan_revisions, floor_binds, cap_binds, lp_negative_pulls, rehearsal_bytes, trust_updates,
            trust_min_binds, unresolved
  style gap: |acc_true(null_f prompt) - acc_true(null_c prompt)| on Qc+Wc (does the model answer differently
             in the liar's style vs the credible style? 0 = no emergent source conditioning)
  trust: final trust of cred / false / corrob
"""
import json, glob, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
arms = sys.argv[1:]
for fn in sorted(glob.glob(os.path.join(HERE, "out", "*_s*.json"))):
    arm = os.path.basename(fn).rsplit("_s", 1)[0]
    if arms and arm not in arms:
        continue
    d = json.load(open(fn))
    c = d.get("counters") or {}
    n_steps = d["n_steps"]
    pl = c.get("plog") or []
    early = [p for s, p in pl if s < 0.75 * n_steps]
    late = [p for s, p in pl if s >= 0.75 * n_steps]
    mean = lambda L: {a: round(sum(p.get(a, 0) for p in L) / len(L), 3) for a in ("hard", "easy", "noise", "cred", "false", "corrob", "late")} if L else None
    f = d["facts_end"]
    gap = sum(abs(f["null_f"][k]["acc_true"] - f["null_c"][k]["acc_true"]) for k in ("Qc", "Wc")) / 2
    cnt = {k: c.get(k) for k in ("plan_revisions", "floor_binds", "cap_binds", "lp_negative_pulls", "rehearsal_bytes",
                                 "trust_updates", "trust_min_binds", "unresolved_conflicts")}
    tr = c.get("final_trust") or {}
    print(f"{arm}_s{d['seed']}: counters {cnt}")
    print(f"   plan P0-2 {mean(early)}")
    print(f"   plan P3   {mean(late)}")
    print(f"   realised share {({a: round(v, 3) for a, v in d['drawn_share'].items()})}")
    print(f"   style_gap {gap:.3f}  trust cred/false/corrob {tr.get('cred')}/{tr.get('false')}/{tr.get('corrob')}")
