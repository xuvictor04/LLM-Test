"""Tabulate d2 results per arm and seed. Usage: python analyze.py [arms...]"""
import json, glob, os, sys
D = os.path.dirname(os.path.abspath(__file__))
AREAS = ["hard", "easy", "noise", "cred", "false", "corrob", "late"]
arms = sys.argv[1:] or ["base", "tags", "sel", "tags_sel", "loss", "sel_pos", "tags_nodrop"]
rows = {}
for a in arms:
    for f in sorted(glob.glob(f"{D}/out/{a}_s[0-9].json")):
        rows.setdefault(a, []).append(json.load(open(f)))


def fmt(v):
    return "  -  " if v is None else f"{v:5.2f}"


def line(name, fn):
    out = f"{name:34s}"
    for a in arms:
        vals = []
        for r in rows.get(a, []):
            try:
                vals.append(fn(r))
            except Exception:
                vals.append(None)
        out += " | " + ",".join(fmt(v) for v in vals)
        ok = [v for v in vals if v is not None]
        out += f" ({sum(ok)/len(ok):5.2f})" if ok else ""
    print(out)


print("arms:", " | ".join(f"{a} seeds {[r['seed'] for r in rows.get(a, [])]}" for a in arms))
print("--- held-out gap to oracle, bits/byte, NULL tag at inference (end of run) ---")
for n in AREAS:
    line(f"gap_null {n}", lambda r, n=n: r["gap_end"][n])
print("--- held-out gap, TRUE tag at inference ---")
for n in AREAS:
    line(f"gap_tag {n}", lambda r, n=n: r["bpb_end_tag"][n] - r["oracle"][n])
print("--- mean gap over learnable areas (hard,easy,cred,false,corrob,late) ---")
L = ["hard", "easy", "cred", "false", "corrob", "late"]
line("mean_gap_null learnable", lambda r: sum(r["gap_end"][n] for n in L) / len(L))
line("mean_gap_tag learnable", lambda r: sum(r["bpb_end_tag"][n] - r["oracle"][n] for n in L) / len(L))
print("--- forgetting (end minus end-of-P2, null tag; + = forgot) ---")
line("forget_hard", lambda r: r["forget_hard"])
line("forget_easy", lambda r: r["forget_easy"])
line("hard_at_p2end_null", lambda r: r["hard_at_p2end"])
print("--- focus gauges ---")
line("noise drawn share", lambda r: r["drawn_share"]["noise"])
line("noise grad-weight share", lambda r: r["grad_weight_share"]["noise"])
for n in AREAS:
    line(f"wshare/drawshare {n}", lambda r, n=n: r["grad_weight_share"][n] / r["drawn_share"][n])
for ph in range(4):
    line(f"P{ph} mean w noise", lambda r, ph=ph: r["phase_mean_w"][ph]["noise"])
    line(f"P{ph} mean w hard", lambda r, ph=ph: r["phase_mean_w"][ph]["hard"])
print("--- facts: share_true on conflicted (Qc = cred vs false only, Wc = +corrob) ---")
for c in ["null_c", "null_f", "null_r", "tag_c", "tag_f", "tag_r"]:
    for k in ["Qc", "Wc"]:
        line(f"{c} {k} share_true", lambda r, c=c, k=k: r["facts_end"][c][k]["share_true"])
for c in ["null_c", "tag_c", "tag_f"]:
    for k in ["Qc", "Wc", "Qa", "Wa"]:
        line(f"{c} {k} acc_true", lambda r, c=c, k=k: r["facts_end"][c][k]["acc_true"])
print("--- model-internal truth discovery ---")
for src in ["tag_c", "tag_f", "tag_r"]:
    line(f"td_tag rel {src}", lambda r, s=src: r["td_tag"]["rel"][s])
for k in ["Qc", "Wc"]:
    line(f"td_tag acc {k}", lambda r, k=k: r["td_tag"]["acc_weighted"][k])
    line(f"td_style acc {k}", lambda r, k=k: r["td_style"]["acc_weighted"][k])
for src in ["null_c", "null_f", "null_r"]:
    line(f"td_style rel {src}", lambda r, s=src: r["td_style"]["rel"][s])
print("trusted source (tag TD):", {a: [r.get("td_tag", {}).get("trusted_source") for r in rows.get(a, [])] for a in arms})
print("loss-ranked most credible:", {a: [r["loss_ranked_most_credible"] for r in rows.get(a, [])] for a in arms})
print("--- cred vs false held-out bpb (null) ---")
line("bpb cred", lambda r: r["bpb_end_null"]["cred"])
line("bpb false", lambda r: r["bpb_end_null"]["false"])
line("wall s", lambda r: r["wall"])
print("counters:", {a: [r["counters"] for r in rows.get(a, [])][:1] for a in arms})
print("--- steering gap (held-out bpb under WRONG tag minus TRUE tag; >0 = model uses the tag) ---")
for n in AREAS:
    line(f"steer {n}", lambda r, n=n: r["steer_gap_wrong_minus_true"][n])
for k in ["Qc", "Wc", "Qa", "Wa"]:
    line(f"trusted-tag acc {k}", lambda r, k=k: r["trusted_tag_acc"][k])
line("tag-minus-null gap noise", lambda r: r["bpb_end_tag"]["noise"] - r["bpb_end_null"]["noise"])
line("end bpb hard null", lambda r: r["bpb_end_null"]["hard"])
line("end bpb easy null", lambda r: r["bpb_end_null"]["easy"])
