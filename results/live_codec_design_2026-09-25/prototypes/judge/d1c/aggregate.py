"""Aggregate res/*.json into a per-arm, per-seed table. Usage: python aggregate.py [res_dir]"""
import json, os, sys, glob
HERE = os.path.dirname(os.path.abspath(__file__))
d = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "res")
rows = {}
for f in sorted(glob.glob(os.path.join(d, "*.json"))):
    r = json.load(open(f))
    if "final" not in r:
        continue
    rows.setdefault(r["arm"], []).append(r)


def g(r, *path):
    x = r
    for p in path:
        if x is None or p not in x:
            return None
        x = x[p]
    return x


cols = [
    ("text_p1", ("text_bpb_after_text_phase",)),
    ("text_afterA", ("after_A", "text_bpb")), ("text_final", ("final", "text_bpb")),
    ("A_bps@A", ("after_A", "A", "bits_per_s")), ("A_bps@end", ("final", "A", "bits_per_s")),
    ("B_bps@end", ("final", "B", "bits_per_s")),
    ("A_bpp@A", ("after_A", "A", "bits_per_pos")), ("B_bpp@end", ("final", "B", "bits_per_pos")),
    ("A_pos/s@A", ("after_A", "A", "positions_per_s")), ("A_pos/s@end", ("final", "A", "positions_per_s")),
    ("B_pos/s@end", ("final", "B", "positions_per_s")),
    ("A_capb@A", ("after_A", "A", "caption_bits_per_byte")), ("A_capb@end", ("final", "A", "caption_bits_per_byte")),
    ("B_capb@end", ("final", "B", "caption_bits_per_byte")),
    ("A_und@A", ("after_A", "A", "understand_exact_train")), ("A_und@end", ("final", "A", "understand_exact_train")),
    ("B_und@end", ("final", "B", "understand_exact_train")),
    ("A_gen1@A", ("after_A", "A", "generate_t1.0", "exact_train")), ("A_gen.7@A", ("after_A", "A", "generate_t0.7", "exact_train")),
    ("A_gen.7@end", ("final", "A", "generate_t0.7", "exact_train")),
    ("B_gen.7dur@end", ("final", "B", "generate_t0.7_dur", "exact_train")), ("A_gen.7dur@A", ("after_A", "A", "generate_t0.7_dur", "exact_train")),
    ("B_gen1@end", ("final", "B", "generate_t1.0", "exact_train")), ("B_gen.7@end", ("final", "B", "generate_t0.7", "exact_train")),
    ("A_mel@A", ("after_A", "A_codec", "mel")), ("A_mel@end", ("final", "A_codec", "mel")),
    ("B_mel@A", ("after_A", "B_codec", "mel")), ("B_mel@end", ("final", "B_codec", "mel")),
    ("A_recx@end", ("final", "A_codec", "recon_probe_exact")), ("B_recx@end", ("final", "B_codec", "recon_probe_exact")),
    ("A_codes@end", ("final", "A_codec", "codes_used")), ("B_codes@end", ("final", "B_codec", "codes_used")),
    ("wA@A", ("after_A", "A_codec", "world_rel_h1")), ("wA@end", ("final", "A_codec", "world_rel_h1")), ("wB@end", ("final", "B_codec", "world_rel_h1")),
    ("windows", ("windows_consumed",)), ("wall_s", ("wall_s",)), ("s/win", ("s_per_window_total",)),
    ("minted_in_data", ("counters", "minted_in_consumed")), ("mints", ("counters", "mints")),
]
out = {}
for arm, rs in rows.items():
    out[arm] = {}
    for name, path in cols:
        out[arm][name] = [g(r, *path) for r in sorted(rs, key=lambda r: r["seed"])]
    out[arm]["seeds"] = [r["seed"] for r in sorted(rs, key=lambda r: r["seed"])]
    dr = []
    for r in sorted(rs, key=lambda r: r["seed"]):
        acts = [x for x in r.get("drift", []) if x["windows_since_prev"] > 0]
        fa = [x["flipA_vs_prev"] * 1000 / x["windows_since_prev"] for x in acts]
        fb = [x["flipB_vs_prev"] * 1000 / x["windows_since_prev"] for x in acts]
        last = r["drift"][-1] if r.get("drift") else {}
        dr.append(dict(flipA_per_1kwin_mean=round(sum(fa) / len(fa), 4) if fa else 0.0,
                       flipB_per_1kwin_mean=round(sum(fb) / len(fb), 4) if fb else 0.0,
                       flipA_vs_codecphase_end=last.get("flipA_vs_codecphase", 0.0),
                       flipB_vs_codecphase_end=last.get("flipB_vs_codecphase", 0.0)))
    out[arm]["drift"] = dr
for arm, v in out.items():
    print("==", arm, "seeds", v["seeds"])
    for k, x in v.items():
        if k in ("seeds",):
            continue
        print(f"  {k:14s} {x}")
json.dump(out, open(os.path.join(d, "..", "aggregate.json"), "w"), indent=1)
