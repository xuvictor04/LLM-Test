"""Repro: metrics per run (same definitions as judge/score.py) for original and reproduced files."""
import json, os, glob, sys
R = os.path.dirname(os.path.abspath(__file__)); M = os.path.dirname(R)
L6 = ["hard", "easy", "cred", "false", "corrob", "late"]; L5 = ["hard", "easy", "cred", "corrob", "late"]
def met(f):
    j = json.load(open(f)); g = j["gap_end"]; fc = j["facts_end"]["null_c"]
    r = dict(mean6=sum(g[n] for n in L6)/6, mean5=sum(g[n] for n in L5)/5, late=g["late"], noise=g["noise"],
             fe=j["forget_easy"], fh=j["forget_hard"], Qc=fc["Qc"]["acc_true"], Qc_sh=fc["Qc"]["share_true"],
             Wc=fc["Wc"]["acc_true"], Qa=fc["Qa"]["acc_true"], cred_or=j["oracle"]["cred"])
    if "bpb_end_tag" in j:
        t = j["bpb_end_tag"]; o = j["oracle"]
        r["mean6_tag"] = sum(t[n]-o[n] for n in L6)/6; r["mean5_tag"] = sum(t[n]-o[n] for n in L5)/5
        r["trustQc"] = j.get("trusted_tag_acc", {}).get("Qc")
        r["td_trusted"] = j.get("td_tag", {}).get("trusted_source")
    if "rho_by_phase" in j: r["rho3"] = j["rho_by_phase"][3]
    if "trust_log" in j and j["trust_log"]:
        t0 = j["trust_log"][0]
        if "n_conflicted" in t0: r["tl0"] = (t0["step"], t0["n_conflicted"], t0["r"].get("false"), t0["r"].get("cred"))
    r["_bpb"] = j["bpb_end_null"]; r["_facts"] = j["facts_end"]
    return r
def show(tag, f):
    if not os.path.exists(f): print(f"{tag:40s} MISSING"); return None
    r = met(f)
    print(f"{tag:40s} " + " ".join(f"{k}={v:.4f}" if isinstance(v, float) else f"{k}={v}" for k, v in r.items() if not k.startswith("_")))
    return r
if __name__ == "__main__":
    pairs = [l.split() for l in open(sys.argv[1])] if len(sys.argv) > 1 else []
    for d, name in pairs:
        o = f"{M}/{d}/out/{name}.json" if not d.startswith("judge") else f"{M}/{d}/out/{name}.json"
        rd = d.split("/")[-1]
        a = show("ORIG " + d + "/" + name, o); b = show("REPR " + rd + "/" + name, f"{R}/{rd}/out/{name}.json")
        if a and b:
            ident = a["_bpb"] == b["_bpb"] and a["_facts"] == b["_facts"]
            print(f"   -> bit-identical bpb_end_null+facts_end: {ident}; max|d bpb| = {max(abs(a['_bpb'][k]-b['_bpb'][k]) for k in a['_bpb']):.2e}")
