"""Reproducer summary: D1 and D3 readings, originals (designer/judge) vs repro, plus paired deltas."""
import json, os, glob
S = "/tmp/claude-0/-home-user-LLM-Test/e880caf7-1208-58de-93fd-49c41549bf70/scratchpad/mm2"
R = S + "/repro"
def ld(p):
    return json.load(open(p)) if os.path.exists(p) else None
def d1(r):
    f = r["final"]; a = r["after_A"]
    return dict(A_bps_A=a["A"]["bits_per_s"], A_bps_end=f["A"]["bits_per_s"], B_bps_end=f["B"]["bits_per_s"],
                A_mel_A=a["A_codec"]["mel"], A_mel_end=f["A_codec"]["mel"], B_mel_end=f["B_codec"]["mel"],
                A_und_A=a["A"]["understand_exact_train"], B_und=f["B"]["understand_exact_train"],
                text_end=f["text_bpb"], codec_steps=r["counters"]["codec_steps"], wall=r["wall_s"])
def d3(r):
    e = r["evals"]["after_P2"]; t, m = e["tones"], e["melody"]
    o = dict(t_bps=t["bits_train_combos"]["bits_per_s"], m_bps=m["bits_train_combos"]["bits_per_s"], t_mel=t["recon_mel"], m_mel=m["recon_mel"],
             t_und=t["understand"]["train"]["exact"], m_und=m["understand"]["train"]["exact"], text=e["text_bpb"], codec_steps=e["codec_steps"],
             t_timbre=t["recon_probe"]["timbre"], t_kind=t["recon_probe"]["kind"], t_band=t["recon_probe"]["band"], t_count=t["recon_probe"]["count"],
             t_pos=t["pos_per_s"], m_pos=m["pos_per_s"], wall=r.get("wall_s"))
    return o
print("=== D1 harness ===")
D1 = {}
for p in sorted(glob.glob(R + "/d1/res/*.json")):
    r = ld(p)
    if "final" not in r: continue
    name = os.path.basename(p)[:-5]; D1[name] = d1(r)
    orig = ld(f"{S}/d1/res/{name}.json") or ld(f"{S}/judge/d1c/res/{name}.json")
    tag = ""
    if orig:
        o = d1(orig); same = all(o[k] == D1[name][k] for k in o if k != "wall")
        tag = "  [orig " + ("IDENTICAL" if same else "DIFF: " + str({k: (o[k], D1[name][k]) for k in o if k != 'wall' and o[k] != D1[name][k]})) + "]"
    print(name, {k: v for k, v in D1[name].items()}, tag)
def pct(a, b): return f"{100*(a-b)/b:+.1f}%"
print("-- paired (repro seeds) lattice vs table, live vs frozen --")
for s in (0, 1, 2, 3):
    def get(n):
        n2 = f"{n}_s{s}"
        if n2 in D1: return D1[n2]
        r = ld(f"{S}/d1/res/{n2}.json") or ld(f"{S}/judge/d1c/res/{n2}.json")
        return d1(r) if r else None
    fz, fl, lv, ll = get("frozen25"), get("frozen25lat"), get("live25"), get("live25lat")
    for lab, x, y in (("frozenLAT-vs-frozen", fl, fz), ("liveLAT-vs-live", ll, lv), ("live-vs-frozen", lv, fz), ("liveLAT-vs-frozenLAT", ll, fl)):
        if x and y:
            print(f" s{s} {lab}: A@A {x['A_bps_A']} vs {y['A_bps_A']} ({pct(x['A_bps_A'],y['A_bps_A'])}, {x['A_bps_A']-y['A_bps_A']:+.2f}) | "
                  f"A@end {x['A_bps_end']} vs {y['A_bps_end']} ({pct(x['A_bps_end'],y['A_bps_end'])}, {x['A_bps_end']-y['A_bps_end']:+.2f}) | "
                  f"B@end {x['B_bps_end']} vs {y['B_bps_end']} ({pct(x['B_bps_end'],y['B_bps_end'])}, {x['B_bps_end']-y['B_bps_end']:+.2f}) | "
                  f"B_und {x['B_und']} vs {y['B_und']} | A_mel@A {x['A_mel_A']} vs {y['A_mel_A']} | text {x['text_end']} vs {y['text_end']} ({x['text_end']-y['text_end']:+.4f})")
    for lab, x in (("frozen25", fz), ("frozen25lat", fl), ("live25", lv), ("live25lat", ll)):
        if x:
            print(f" s{s} {lab} interference A_end-A_A = {x['A_bps_end']-x['A_bps_A']:+.2f}")
print("=== D3 harness ===")
D3 = {}
for p in sorted(glob.glob(R + "/d3/res/*_s[0-9].json")):
    r = ld(p)
    if "evals" not in r: continue
    name = os.path.basename(p)[:-5]; D3[name] = d3(r)
    orig = ld(f"{S}/d3/res/{name}.json") or ld(f"{S}/judge/d3c/res/{name}.json")
    tag = ""
    if orig:
        o = d3(orig); same = all(o[k] == D3[name][k] for k in o if k != "wall")
        tag = "  [orig " + ("IDENTICAL" if same else "DIFF: " + str({k: (o[k], D3[name][k]) for k in o if k != 'wall' and o[k] != D3[name][k]})) + "]"
    print(name, D3[name], tag)
def g3(n):
    if n in D3: return D3[n]
    r = ld(f"{S}/d3/res/{n}.json") or ld(f"{S}/judge/d3c/res/{n}.json")
    return d3(r) if r else None
print("-- paired D3 --")
for s in (0, 1, 2, 3):
    for lab, a, b in (("frozen25c-vs-frozen25", "frozen25c", "frozen25"), ("ttc25c-vs-frozen25", "ttc25c", "frozen25"), ("ttc25c-vs-frozen25c", "ttc25c", "frozen25c"),
                      ("ttc25-vs-frozen25", "ttc25", "frozen25"), ("ttcMR-vs-ttcN25", "ttcMR", "ttcN25"), ("ttcMRc-vs-ttc25c", "ttcMRc", "ttc25c"),
                      ("ttc25c_cold-vs-frozen25c", "ttc25c_cold", "frozen25c"), ("ttc25c_cold-vs-ttc25c", "ttc25c_cold", "ttc25c")):
        x, y = g3(f"{a}_s{s}"), g3(f"{b}_s{s}")
        if x and y:
            print(f" s{s} {lab}: tones {x['t_bps']} vs {y['t_bps']} ({pct(x['t_bps'],y['t_bps'])}) | melody {x['m_bps']} vs {y['m_bps']} ({pct(x['m_bps'],y['m_bps'])}) | "
                  f"mel t {x['t_mel']} vs {y['t_mel']} ({pct(x['t_mel'],y['t_mel'])}) m {x['m_mel']} vs {y['m_mel']} ({pct(x['m_mel'],y['m_mel'])}) | "
                  f"und t {x['t_und']} vs {y['t_und']} m {x['m_und']} vs {y['m_und']} | timbre {x['t_timbre']} vs {y['t_timbre']} kind {x['t_kind']} vs {y['t_kind']} band {x['t_band']} vs {y['t_band']} count {x['t_count']} vs {y['t_count']} | pos t {x['t_pos']}/{y['t_pos']} m {x['m_pos']}/{y['m_pos']} | text {x['text']} vs {y['text']}")
