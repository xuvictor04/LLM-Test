"""Per-run act log: windows_in_epoch revisions, tail rate, minted share, per-act code flips, WORLD target jump.
Usage: python acts_summary.py res/live50bpe_s0.json [...]"""
import json, sys
for f in sys.argv[1:]:
    r = json.load(open(f))
    print("==", f, "windows initial", r["windows_initial"], "final", r["windows_final"], "consumed", r["windows_consumed"],
          "revisions", r["clock"]["epoch_revisions"], "unconsumed tail positions", r["unconsumed_tail_positions"])
    print("  counters", r["counters"], "bpe_size", r["bpe_size"], "refused_len", r["bpe_refused_len"])
    print("  timers", r["timers"], "s/win", r["s_per_window_total"], "wall", r["wall_s"])
    dr = {d["window"]: d for d in r.get("drift", [])}
    for a in r["acts"]:
        d = dr.get(a["window"], {})
        print("  act@%5d wie %5s->%5s minted %3s tail tok/s %6s minted%% %6s flipA %s flipB %s world %s->%s  %ss" % (
            a["window"], a["wie_before"], a.get("wie_after", "-"), a.get("minted", "-"), a.get("tail_media_tokens_per_s", "-"),
            a.get("tail_frac_minted", "-"), d.get("flipA_vs_prev", "-"), d.get("flipB_vs_prev", "-"),
            a.get("world_rel_before"), a.get("world_rel_after"), a.get("s")))
    if not r["acts"]:
        for d in r.get("drift", []):
            print("  measure@%5d flipA %s flipB %s vs codec-phase A %s B %s" % (d["window"], d["flipA_vs_prev"], d["flipB_vs_prev"],
                                                                          d["flipA_vs_codecphase"], d["flipB_vs_codecphase"]))
    for tag in ("after_A", "final"):
        e = r.get(tag) or {}
        for area in ("A", "B"):
            if area in e:
                print(f"  {tag} {area} pos/s by kind", e[area]["positions_per_s_by_kind"])
