"""Proposal 04 revision: goal-B end-state, time-integrated and per-phase readings, re-derived from the
preserved run JSONs (no new training). Usage: python3 metrics.py <prototypes dir> > metrics.txt

Definitions (all bits/byte, null read, held-out windows of testbed.eval):
  gap_end[a]      = bpb_end_null[a] - oracle[a]                     (the file's own gap_end)
  gap_p2end_hard  = hard_at_p2end - oracle[hard]                    (hard just before it fades)
  forget_hard     = the file's forget_hard (= end minus end of P2; LEVEL-RELATIVE, secondary)
  tig[a]          = time-integrated gap: mean over the 8 prequential eval points (frac 0.125 .. 1.0)
                    of curve[i].null[a] - oracle[a], from the area's first live point on
                    (late: frac >= 0.875; every other area: all 8 points)
  tig_P3[a]       = the same mean over the P3 points only (frac 0.875, 1.0): the fade period
  share_P{k}[a]   = phase_drawn_share[k][a] (planned base: 1/6 in P0-P2, 1/5 of live in P3)
  mean6 / mean5   = mean gap_end over hard,easy,cred,false,corrob,late (mean5 drops false)
"""
import json, os, sys

R = sys.argv[1] if len(sys.argv) > 1 else "."
L6 = ["hard", "easy", "cred", "false", "corrob", "late"]
L5 = [a for a in L6 if a != "false"]
ARMS = {
    "base":        {0: "d2/out/base_s0.json", 1: "d2/out/base_s1.json", 2: "d2/out/base_s2.json",
                    3: "repro/d2/out/base_s3.json", 4: "repro/d2/out/base_s4.json"},
    "focus":       {0: "d3/out/focus_s0.json", 1: "d3/out/focus_s1.json", 2: "judge/w/d3/out/focus_s2.json",
                    3: "repro/d3/out/focus_s3.json", 4: "repro/d3/out/focus_s4.json"},
    "m27":         {0: "d3/out/replay_fixed_m27_s0.json", 1: "d3/out/replay_fixed_m27_s1.json",
                    2: "judge/w/d3/out/replay_fixed_m27_s2.json",
                    3: "repro/d3/out/replay_fixed_m27_s3.json", 4: "repro/d3/out/replay_fixed_m27_s4.json"},
    "replay_late": {0: "critic/w/d3/out/replay_late_s0.json", 1: "critic/w/d3/out/replay_late_s1.json"},
    "fulltd":      {0: "d3/out/fulltd_s0.json", 1: "d3/out/fulltd_s1.json", 2: "judge/w/d3/out/fulltd_s2.json",
                    3: "repro/d3/out/fulltd_s3.json", 4: "repro/d3/out/fulltd_s4.json"},
    "graft":       {0: "judge/w/d3/out/fulltd_tags_s0.json", 1: "judge/w/d3/out/fulltd_tags_s1.json",
                    2: "judge/w/d3/out/fulltd_tags_s2.json"},
    "lp":          {0: "d1/out/lp_s0.json", 1: "d1/out/lp_s1.json", 2: "d1/out/lp_s2.json"},
    "rehearse":    {0: "d3/out/rehearse_s0.json", 1: "d3/out/rehearse_s1.json"},
    "focus_nomir": {0: "d3/out/focus_nomir_s0.json", 1: "d3/out/focus_nomir_s1.json"},
}


def load(p):
    p = os.path.join(R, p)
    return json.load(open(p)) if os.path.exists(p) else None


def planned_phase_shares():
    P = [["hard", "easy", "noise", "cred", "false", "corrob"]] * 3 + [["late", "noise", "cred", "false", "corrob"]]
    return [{a: (1.0 / len(ph) if a in ph else 0.0) for a in L6 + ["noise"]} for ph in P]


def row(d):
    o = d["oracle"]
    g = d["gap_end"]
    out = {"gap_end": g, "mean6": sum(g[a] for a in L6) / 6, "mean5": sum(g[a] for a in L5) / 5,
           "gap_p2end_hard": d["hard_at_p2end"] - o["hard"], "forget_hard": d["forget_hard"],
           "forget_easy": d["forget_easy"]}
    tig, tig3 = {}, {}
    for a in L6 + ["noise"]:
        pts = [(c["frac"], c["null"][a] - o[a]) for c in d["curve"]]
        use = [v for f, v in pts if (f >= 0.8 if a == "late" else True)]
        tig[a] = sum(use) / len(use)
        p3 = [v for f, v in pts if f >= 0.8]
        tig3[a] = sum(p3) / len(p3)
    out["tig"] = tig
    out["tig_P3"] = tig3
    out["tig6"] = sum(tig[a] for a in L6) / 6
    out["phase_share"] = d.get("phase_drawn_share") or planned_phase_shares()
    out["drawn_share"] = d["drawn_share"]
    out["rho3"] = (d.get("rho_by_phase") or [None] * 4)[3]
    out["counters"] = d.get("counters", {})
    fe = d["facts_end"].get("null_c", {})
    out["Qa_acc"] = fe.get("Qa", {}).get("acc_true")
    out["Qc_share"] = fe.get("Qc", {}).get("share_true")
    out["Qc_acc"] = fe.get("Qc", {}).get("acc_true")
    out["wall"], out["wall_probe"] = d.get("wall"), d.get("wall_probe")
    out["oracle_cred"] = o["cred"]
    return out


def f3(x):
    return "   -  " if x is None else f"{x:+.3f}" if x < 0 else f"{x:.3f}"


rows = {arm: {s: row(load(p)) for s, p in m.items() if load(p) is not None} for arm, m in ARMS.items()}


def line(label, fn, arms=("base", "focus", "m27", "replay_late", "fulltd", "graft", "lp"), seeds=(0, 1, 2, 3, 4)):
    print(f"\n== {label} ==   seeds {'/'.join(map(str, seeds))}")
    for arm in arms:
        vals = []
        for s in seeds:
            r = rows[arm].get(s)
            vals.append(None if r is None else fn(r))
        if all(v is None for v in vals):
            continue
        print(f"  {arm:12s} " + "  ".join(f3(v) for v in vals))


def diff(label, fn, a, b, seeds=(0, 1, 2, 3, 4)):
    vals = []
    for s in seeds:
        ra, rb = rows[a].get(s), rows[b].get(s)
        vals.append(None if ra is None or rb is None else fn(ra) - fn(rb))
    print(f"  {a} - {b:12s} " + "  ".join(f3(v) for v in vals) + f"   [{label}]")


print(__doc__)
print("pairing check, oracle cred per seed:")
for arm in rows:
    print(f"  {arm:12s}", {s: round(r['oracle_cred'], 6) for s, r in rows[arm].items()})
line("mean6 (end state)", lambda r: r["mean6"])
line("mean5 (end state, excl. false)", lambda r: r["mean5"])
for a in L6 + ["noise"]:
    line(f"gap_end {a}", lambda r, a=a: r["gap_end"][a])
line("hard gap at end of P2 (just before fade)", lambda r: r["gap_p2end_hard"])
line("forget_hard (level-relative, secondary)", lambda r: r["forget_hard"])
line("forget_easy (level-relative, secondary)", lambda r: r["forget_easy"])
line("time-integrated gap, mean of 6 learnable areas", lambda r: r["tig6"])
for a in ["hard", "easy", "late"]:
    line(f"time-integrated gap {a}", lambda r, a=a: r["tig"][a])
for a in ["hard", "easy"]:
    line(f"P3 (fade period) mean gap {a}", lambda r, a=a: r["tig_P3"][a])
for k in (2, 3):
    for a in ["hard", "easy", "noise", "cred", "corrob", "late"]:
        line(f"phase P{k} drawn share {a}", lambda r, a=a, k=k: r["phase_share"][k].get(a, 0.0))
line("whole-run drawn share late", lambda r: r["drawn_share"]["late"])
line("whole-run drawn share noise", lambda r: r["drawn_share"]["noise"])
line("last-phase rho (rho_by_phase[3])", lambda r: r["rho3"], arms=("focus", "fulltd", "graft"))
line("rho_cap_binds (counter)", lambda r: r["counters"].get("focus.rho_cap_binds"), arms=("focus", "fulltd", "graft"))
line("focus.replans (counter)", lambda r: r["counters"].get("focus.replans"), arms=("focus", "fulltd", "graft"))
line("Qa acc_true null_c", lambda r: r["Qa_acc"])
line("Qc share_true null_c", lambda r: r["Qc_share"])
line("wall s", lambda r: r["wall"], arms=("base", "focus", "m27", "replay_late", "fulltd"))
line("wall_probe s", lambda r: r["wall_probe"], arms=("focus", "m27", "replay_late", "fulltd", "rehearse", "focus_nomir"))
line("probe share of wall (wall_probe / wall; MIR on except focus_nomir)",
     lambda r: None if not r["wall_probe"] else r["wall_probe"] / r["wall"],
     arms=("focus", "fulltd", "rehearse", "focus_nomir"))
line("rehearse/focus_nomir mean6", lambda r: r["mean6"], arms=("rehearse", "focus_nomir", "m27", "focus"), seeds=(0, 1))
line("rehearse/focus_nomir gap_end hard", lambda r: r["gap_end"]["hard"], arms=("rehearse", "focus_nomir", "m27"), seeds=(0, 1))
line("rehearse/focus_nomir gap_end late", lambda r: r["gap_end"]["late"], arms=("rehearse", "focus_nomir", "m27"), seeds=(0, 1))
line("rehearse last-phase rho", lambda r: r["rho3"], arms=("rehearse", "focus_nomir"), seeds=(0, 1))
line("rehearse rho_cap_binds", lambda r: r["counters"].get("focus.rho_cap_binds"), arms=("rehearse", "focus_nomir"), seeds=(0, 1))

LIVE = [["hard", "easy", "noise", "cred", "false", "corrob"]] * 3 + [["late", "noise", "cred", "false", "corrob"]]
print("\n== per-phase noise gauge (live bytes only): noise share of the phase's LIVE bytes / even live share;"
      " then the learnable live areas noise out-draws ==")
for arm in ("focus", "fulltd", "graft", "rehearse"):
    for s_, r in sorted(rows[arm].items()):
        ps = r["phase_share"]
        cells = []
        for k in range(4):
            L = LIVE[k]
            tot = sum(ps[k].get(a, 0.0) for a in L)
            n = ps[k]["noise"] / tot
            beaten = [a for a in L if a != "noise" and ps[k].get(a, 0.0) < ps[k]["noise"]]
            cells.append(f"P{k} {n * len(L):.2f} [{','.join(beaten)}]")
        print(f"  {arm:9s} s{s_}  " + "  ".join(cells))

print("\n== paired differences ==   seeds 0/1/2/3/4")
diff("mean6", lambda r: r["mean6"], "focus", "m27")
diff("mean6", lambda r: r["mean6"], "focus", "base")
diff("mean6", lambda r: r["mean6"], "m27", "base")
diff("mean6", lambda r: r["mean6"], "replay_late", "m27")
diff("mean6", lambda r: r["mean6"], "focus", "replay_late")
diff("mean5", lambda r: r["mean5"], "focus", "m27")
diff("gap_end hard", lambda r: r["gap_end"]["hard"], "focus", "m27")
diff("gap_end easy", lambda r: r["gap_end"]["easy"], "focus", "m27")
diff("gap_end late", lambda r: r["gap_end"]["late"], "focus", "m27")
diff("gap_end late", lambda r: r["gap_end"]["late"], "focus", "replay_late")
diff("gap_end noise", lambda r: r["gap_end"]["noise"], "focus", "m27")
diff("gap_end cred", lambda r: r["gap_end"]["cred"], "focus", "m27")
diff("gap_end corrob", lambda r: r["gap_end"]["corrob"], "focus", "m27")
diff("time-integrated gap mean6", lambda r: r["tig6"], "focus", "m27")
diff("time-integrated gap hard", lambda r: r["tig"]["hard"], "focus", "m27")
diff("P3 mean gap hard", lambda r: r["tig_P3"]["hard"], "focus", "m27")
diff("forget_hard", lambda r: r["forget_hard"], "focus", "m27")
diff("gap_end hard", lambda r: r["gap_end"]["hard"], "fulltd", "m27")
diff("mean6", lambda r: r["mean6"], "fulltd", "m27")
