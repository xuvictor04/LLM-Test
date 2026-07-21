#!/usr/bin/env python3
"""Read every finished arm's log, find the lowest final OOD bits/byte, and print the
completion-run env flags for that config. Used by run_all.sh to pick the Phase-3 config."""
import json, os, sys

ARMS = {                                            # dir -> completion env flags (empty = full aggregate)
    "agg": "",
    "abl_sense":  "SENSE_K=0",
    "abl_sparse": "SENSE_SLOTS=2048 SENSE_PROMOTE=20",
    "abl_cp":     "COUNTERPARTS=0",
    "abl_reenc":  "ENABLE_REENCODE=0",
    "abl_moe":    "M_EMBED=0",
    "abl_tok":    "TOK=frozen",
    "abl_mem":    "MEMORY=off",
    "barry":      "FABRIC=sparse MOE_K=2 FABRIC_LAYERS=2 CAP_FACTOR=1.25 LB_COST=0.01",
}

best_flags, best_ood, best_name = "", 1e9, "agg"
for d, flags in ARMS.items():
    p = os.path.join(d, "train_log.jsonl")
    if not os.path.exists(p):
        continue
    ood = None
    for line in open(p):
        try:
            ood = json.loads(line).get("ood", ood)
        except Exception:
            pass
    if ood is not None and ood < best_ood:
        best_ood, best_name, best_flags = ood, d, flags

sys.stderr.write(f"WINNER: {best_name}  (OOD {best_ood if best_ood < 1e9 else 'n/a'})  -> completion flags: [{best_flags}]\n")
print(best_flags)
