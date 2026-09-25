"""Summarise res/*.json per arm with per-seed values. Usage: python3 aggregate.py [res_dir]"""
import json, glob, os, sys

R = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "res")
runs = {}
for f in sorted(glob.glob(os.path.join(R, "*_s[0-9].json"))):
    d = json.load(open(f))
    if "arm" in d: runs.setdefault(d["arm"], []).append(d)


def g(d, path):
    cur = d
    for k in path.split("/"):
        if cur is None:
            return None
        cur = cur.get(k) if isinstance(cur, dict) else None
    return cur


ROWS = [
    ("text bpb after P0", "evals/after_p0/text_bpb"),
    ("text bpb after P1", "evals/after_P1/text_bpb"),
    ("text bpb after P2", "evals/after_P2/text_bpb"),
    ("codec steps total", "evals/after_P2/codec_steps"),
]
for ar in ("tones", "melody"):
    for tag in ("after_P1", "after_P2"):
        if ar == "melody" and tag == "after_P1":
            continue
        pre = f"evals/{tag}/{ar}"
        ROWS += [
            (f"{ar} {tag} recon mel", f"{pre}/recon_mel"),
            (f"{ar} {tag} recon probe exact", f"{pre}/recon_probe/exact"),
            (f"{ar} {tag} codes used (eval set)", f"{pre}/codes_used"),
            (f"{ar} {tag} pos/s", f"{pre}/pos_per_s"),
            (f"{ar} {tag} bits/pos (train combos)", f"{pre}/bits_train_combos/bits_per_pos"),
            (f"{ar} {tag} bits/s (train combos)", f"{pre}/bits_train_combos/bits_per_s"),
            (f"{ar} {tag} understand exact train", f"{pre}/understand/train/exact"),
            (f"{ar} {tag} understand exact heldout", f"{pre}/understand/held/exact"),
            (f"{ar} {tag} generate t1.0 exact train", f"{pre}/generate_t1.0/train/exact"),
            (f"{ar} {tag} generate t1.0 exact heldout", f"{pre}/generate_t1.0/held/exact"),
            (f"{ar} {tag} generate t0.7 exact train", f"{pre}/generate_t0.7/train/exact"),
            (f"{ar} {tag} WORLD rel mse 40ms", f"{pre}/world/rel_mse_40ms"),
            (f"{ar} {tag} WORLD rel mse 200ms", f"{pre}/world/rel_mse_200ms"),
            (f"{ar} {tag} WORLD target std", f"{pre}/world/target_std"),
        ]
ROWS += [
    ("tones: P1 codes decoded by P2 teacher, mel", "evals/after_P2/tones/p1_codes_under_p2_teacher/recon_mel"),
    ("tones: P1 codes decoded by P2 teacher, probe exact", "evals/after_P2/tones/p1_codes_under_p2_teacher/recon_probe/exact"),
    ("tones: P1 codes, LM bits/pos under P2 LM", "evals/after_P2/tones/p1_codes_under_p2_teacher/bits/bits_per_pos"),
    ("tones: frac positional ids changed P1->P2", "evals/after_P2/tones/p1_codes_under_p2_teacher/frac_ids_changed"),
    ("s/step P0", "timing/p0_s_per_step"), ("s/step P1", "timing/P1_s_per_step"), ("s/step P2", "timing/P2_s_per_step"),
    ("wall s", "wall_s"),
]
order = [a for a in ("frozen25", "frozen25c", "live25", "ttc25", "ttc25c", "ttcN25", "ttcMR", "ttcMRc", "frozenMR") if a in runs]
print("metric | " + " | ".join(order))
for name, path in ROWS:
    cells = []
    for a in order:
        vals = [g(d, path) for d in sorted(runs[a], key=lambda d: d["seed"])]
        vals = [v for v in vals if v is not None]
        if not vals:
            cells.append("-"); continue
        mean = sum(vals) / len(vals)
        cells.append(f"{mean:.4g} [" + ", ".join(f"{v:.4g}" for v in vals) + "]")
    print(f"{name} | " + " | ".join(cells))
print()
print("drift on probe set (flip = fraction of 50-fps frame codes changed vs the previous measure, 150 LM windows; d4 = 600 windows):")
for a in order:
    for d in sorted(runs[a], key=lambda d: d["seed"]):
        rows = [m for m in d["meas"] if m["phase"] != "boundary"]
        f1 = [m.get("tones_flip_d1") for m in rows]; f4 = [m.get("tones_flip_d4") for m in rows if m.get("tones_flip_d4") is not None]
        fm = [m.get("melody_flip_d1") for m in rows]
        cur = [m["tones_bits"]["bits_per_pos"] for m in rows]; st = [m.get("tones_bits_stale_d1") for m in rows]
        print(f"  {a} s{d['seed']}: tones flip_d1 {f1} | tones flip_d4 {f4} | melody flip_d1 {fm}")
        print(f"      tones bits/pos current {cur} | stale(d1) {st}")
