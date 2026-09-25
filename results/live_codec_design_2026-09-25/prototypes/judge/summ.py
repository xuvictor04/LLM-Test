"""Judge summary: D1-harness arms (designer records + judge reruns) and D3 arms, side by side."""
import json, os, glob
S = "/tmp/claude-0/-home-user-LLM-Test/e880caf7-1208-58de-93fd-49c41549bf70/scratchpad/mm2"
def d1(path):
    r = json.load(open(path)); f = r["final"]; a = r["after_A"]
    return dict(A_bps_A=a["A"]["bits_per_s"], A_bps_end=f["A"]["bits_per_s"], B_bps_end=f["B"]["bits_per_s"],
                A_capb_A=a["A"]["caption_bits_per_byte"], B_capb_end=f["B"]["caption_bits_per_byte"],
                A_mel_A=a["A_codec"]["mel"], A_mel_end=f["A_codec"]["mel"], B_mel_end=f["B_codec"]["mel"],
                A_recx=f["A_codec"]["recon_probe_exact"], B_recx=f["B_codec"]["recon_probe_exact"],
                A_und_A=a["A"]["understand_exact_train"], B_und=f["B"]["understand_exact_train"],
                B_gen07=f["B"]["generate_t0.7"]["exact_train"], A_gen07_A=a["A"]["generate_t0.7"]["exact_train"],
                text_end=f["text_bpb"], codec_steps=r["counters"]["codec_steps"], wall=r["wall_s"])
rows = []
for s in (0, 1):
    for arm in ("frozen25", "live25", "live25free"):
        rows.append((f"D1 {arm} s{s} (designer)", d1(f"{S}/d1/res/{arm}_s{s}.json")))
for p in sorted(glob.glob(f"{S}/judge/d1c/res/*.json")):
    rows.append(("JUDGE d1 " + os.path.basename(p)[:-5], d1(p)))
keys = list(rows[0][1].keys())
print("arm | " + " | ".join(keys))
for n, d in rows:
    print(n + " | " + " | ".join(str(d[k]) for k in keys))
def d3(path):
    r = json.load(open(path)); e = r["evals"]["after_P2"]
    t, m = e["tones"], e["melody"]
    return dict(t_bps=t["bits_train_combos"]["bits_per_s"], m_bps=m["bits_train_combos"]["bits_per_s"], t_mel=t["recon_mel"], m_mel=m["recon_mel"],
                t_und=t["understand"]["train"]["exact"], m_und=m["understand"]["train"]["exact"],
                t_gen07=t["generate_t0.7"]["train"]["exact"], m_gen07=m["generate_t0.7"]["train"]["exact"], text=e["text_bpb"], codec_steps=e["codec_steps"])
print()
rows = []
for a in ("frozen25_s0", "frozen25c_s0", "ttc25_s0", "ttc25c_s0", "frozen25_s1", "frozen25c_s1", "ttc25_s1", "ttc25c_s1", "live25_s0"):
    rows.append(("D3 " + a + " (designer)", d3(f"{S}/d3/res/{a}.json")))
for p in sorted(glob.glob(f"{S}/judge/d3c/res/*.json")):
    if "flipdist" in p: continue
    rows.append(("JUDGE d3 " + os.path.basename(p)[:-5], d3(p)))
keys = list(rows[0][1].keys())
print("arm | " + " | ".join(keys))
for n, d in rows:
    print(n + " | " + " | ".join(str(d[k]) for k in keys))
