"""Print a per-seed table of the key readings from res/*.json. Usage: summarize.py [glob]"""
import json, glob, sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
pat = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "res", "*_s[0-9]*.json")


def g(d, *ks, default=None):
    for k in ks:
        if not isinstance(d, dict) or k not in d:
            return default
        d = d[k]
    return d


rows = []
for f in sorted(glob.glob(pat)):
    d = json.load(open(f)); e = d["evals"]
    r = dict(run=os.path.basename(f)[:-5],
             text_p1=g(e, "after_P1", "text_bpb"), text_p2=g(e, "after_P2", "text_bpb"), text_p3=g(e, "after_P3", "text_bpb"))
    for tag in ("after_P2", "after_P3"):
        for area in ("A", "B"):
            a = g(e, tag, area)
            if not a:
                continue
            p = f"{tag[-2:]}{area}_"
            r[p + "und"] = g(a, "understand", "train", "exact")
            r[p + "und_ho"] = g(a, "understand", "heldout", "exact")
            r[p + "gen1"] = g(a, "gen_t1", "train", "exact")
            r[p + "gen07"] = g(a, "gen_t07", "train", "exact")
            r[p + "gen0"] = g(a, "gen_t0", "train", "exact")
            r[p + "gen_ho07"] = g(a, "gen_t07", "heldout", "exact")
            if area == "B":
                r[p + "und_note"] = g(a, "understand", "train", "note")
                r[p + "gen07_note"] = g(a, "gen_t07", "train", "note")
                r[p + "gen0_note"] = g(a, "gen_t0", "train", "note")
            r[p + "mel"] = g(a, "recon", "mel")
            r[p + "ceil"] = g(a, "recon", "probe_on_recon", "exact")
            r[p + "capbpb"] = g(a, "bits", "a2t_caption_bits_per_byte")
            r[p + "bpc"] = g(a, "bits", "t2a_bits_per_code")
            r[p + "tfmel"] = g(a, "bits", "tf_pred_mel")
            r[p + "pos_s"] = g(a, "bits", "pos_per_s")
            r[p + "gen_frames07"] = g(a, "gen_t07", "mean_frames_50fps")
            r[p + "gen_pos07"] = g(a, "gen_t07", "mean_positions_per_clip")
    r["stale_A_mel"] = g(d, "stale_A_latents_decoded_by_P3_decoder", "mel")
    r["stale_A_exact"] = g(d, "stale_A_latents_decoded_by_P3_decoder", "probe", "exact")
    r["p2_s_step"] = g(d, "timing", "p2_s_per_step"); r["p3_s_step"] = g(d, "timing", "p3_s_per_step")
    r["p1_codec_s"] = g(d, "timing", "p1_codec_s"); r["total_s"] = g(d, "timing", "total_s")
    pr = d["probes"]
    if pr and "lat_std" in pr[-1].get("A", {}):
        r["lat_std_A_end"] = pr[-1]["A"]["lat_std"]; r["lat_pr_A_end"] = pr[-1]["A"]["lat_pr"]
        r["pos_by_kind_end"] = {**pr[-1]["A"]["pos_per_s_by_kind"], **pr[-1]["B"]["pos_per_s_by_kind"]}
        r["drift_A"] = [(p["step"], p["A"].get("drift_rel_l2_per_1k")) for p in pr]
        r["flip_A"] = [(p["step"], p["A"].get("boundary_flip_per_1k")) for p in pr]
        r["pos_A_t"] = [(p["step"], p["A"]["pos_per_s"], p["B"]["pos_per_s"]) for p in pr]
        r["lat_std_t"] = [(p["step"], p["A"]["lat_std"], p["A"]["lat_pr"]) for p in pr]
    rows.append(r)
for r in rows:
    print(json.dumps(r))
