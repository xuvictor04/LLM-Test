# Independent recomputation of the toy statistics §3.2 cites, straight from the run JSONs.
import json, math, os, glob
R = "/home/user/LLM-Test/results/self_regulation_design_2026-09-26/prototypes"
L6 = ["hard", "easy", "cred", "false", "corrob", "late"]
P = {
 "base": ["d2/out/base_s0.json", "d2/out/base_s1.json", "d2/out/base_s2.json", "repro/d2/out/base_s3.json", "repro/d2/out/base_s4.json"],
 "focus": ["d3/out/focus_s0.json", "d3/out/focus_s1.json", "judge/w/d3/out/focus_s2.json", "repro/d3/out/focus_s3.json", "repro/d3/out/focus_s4.json"],
 "m27": ["d3/out/replay_fixed_m27_s0.json", "d3/out/replay_fixed_m27_s1.json", "judge/w/d3/out/replay_fixed_m27_s2.json", "repro/d3/out/replay_fixed_m27_s3.json", "repro/d3/out/replay_fixed_m27_s4.json"],
}
J = {k: [json.load(open(os.path.join(R, p))) for p in v] for k, v in P.items()}

def tig6(d):
    o = d["oracle"]; tot = 0
    for a in L6:
        pts = [(c["frac"], c["null"][a] - o[a]) for c in d["curve"]]
        use = [v for f, v in pts if (f >= 0.8 if a == "late" else True)]
        tot += sum(use) / len(use)
    return tot / 6

def tt(x):
    n = len(x); m = sum(x) / n; sd = math.sqrt(sum((v - m) ** 2 for v in x) / (n - 1))
    return m, sd, m / (sd / math.sqrt(n))

def pr(name, x):
    m, sd, t = tt(x); print(f"  {name:32s} per-seed {[round(v, 3) for v in x]} mean {m:+.4f} sd {sd:.4f} t {t:+.2f}")

print("retention(focus) minus replay 0.27 (m27), seeds 0-4:")
pr("end mean6", [sum(f['gap_end'][a] for a in L6)/6 - sum(m['gap_end'][a] for a in L6)/6 for f, m in zip(J['focus'], J['m27'])])
pr("TIG6", [tig6(f) - tig6(m) for f, m in zip(J['focus'], J['m27'])])
pr("easy end", [f['gap_end']['easy'] - m['gap_end']['easy'] for f, m in zip(J['focus'], J['m27'])])
pr("cred end", [f['gap_end']['cred'] - m['gap_end']['cred'] for f, m in zip(J['focus'], J['m27'])])
print("forget_easy per seed:")
for k in J:
    print(f"  {k:6s}", [round(d['forget_easy'], 3) for d in J[k]])
# the MDE for the all-area mean at 5 seeds
_, sd, _ = tt([sum(f['gap_end'][a] for a in L6)/6 - sum(m['gap_end'][a] for a in L6)/6 for f, m in zip(J['focus'], J['m27'])])
print("  MDE end mean6 (2.132+0.941)*sd/sqrt5 =", round((2.132 + 0.941) * sd / math.sqrt(5), 4))
_, sd, _ = tt([tig6(f) - tig6(m) for f, m in zip(J['focus'], J['m27'])])
print("  MDE TIG6 =", round((2.132 + 0.941) * sd / math.sqrt(5), 4))

print("\nrho_cap_binds / replans in last phase, and rho_by_phase, by arm file:")
for f in sorted(glob.glob(R + "/**/out/*.json", recursive=True)):
    try:
        d = json.load(open(f))
    except Exception:
        continue
    c = d.get("counters", {}) if isinstance(d, dict) else {}
    if "focus.rho_cap_binds" in c:
        print(f"  {os.path.relpath(f, R):45s} rho_cap_binds {c['focus.rho_cap_binds']:3d} replans {c.get('focus.replans')} rehearse_fired {c.get('focus.rehearse_fired')}")
