"""Forgetting and end values under NULL and TRUE-tag inference from saved curves. Usage: python forget_tag.py"""
import json, glob, os
D = "/home/user/LLM-Test/results/self_regulation_design_2026-09-26/prototypes/d2"
for a in ["base", "tags", "sel", "tags_sel", "loss", "sel_pos", "tags_nodrop"]:
    for area in ("hard", "easy"):
        row = []
        for s in (0, 1, 2):
            d = json.load(open(f"{D}/out/{a}_s{s}.json"))
            c = d["curve"]; p2 = min(c, key=lambda r: abs(r["frac"] - 0.75)); e = c[-1]
            cond = "tag" if e["tag"] else "null"
            row.append((p2[cond][area], e[cond][area], e[cond][area] - p2[cond][area]))
        print(f"{a:12s} {area:4s} cond={cond:4s} P2end/end/forget per seed:",
              "  ".join(f"{x:.2f}/{y:.2f}/{z:+.2f}" for x, y, z in row),
              f"| mean end {sum(r[1] for r in row)/3:.2f} mean forget {sum(r[2] for r in row)/3:+.2f}")
