"""Evaluate a trained checkpoint without training.  Usage:
    python evaluate.py
Loads runs/ckpt.pt and prints in-distribution-held CE, out-of-distribution (held-out source) CE,
the novelty signal and memory-recall confidence on each, and the per-domain embedder mix.
The headline thing to watch: in-held should be LOW while OOD does NOT blow up, and novelty/mem-conf
should cleanly separate familiar (low novelty, high recall confidence) from unseen sources.
"""
import os, json, torch
from config import cfg
from data_utils import load_corpus
from system import load_system, evaluate_system, embed_mix

def main():
    dev = torch.device(cfg.DEVICE)
    ckpt_path = os.path.join(cfg.RUN_DIR, "ckpt.pt")
    assert os.path.exists(ckpt_path), f"no checkpoint at {ckpt_path} -- train first"
    TRAIN, HELD, OOD = load_corpus(cfg)
    sysm, ck = load_system(ckpt_path, cfg, dev)
    print(f"loaded step {ck['total']} | nodes {len(sysm.bodies)} | mem {sysm.mem.n}/{cfg.MEMCAP} | novgrams {len(sysm.surprise.cnt)}")
    m = evaluate_system(sysm, HELD, OOD, cfg)
    print(json.dumps({
        "in_held": m["in_held"], "held_by_domain": m["held_by_domain"],
        "ood": m["ood"], "ood_by_domain": m["ood_by_domain"],
        "novelty_held": m["nov_held"], "novelty_ood": m["nov_ood"],
        "mem_conf_held": m["memconf_held"], "mem_conf_ood": m["memconf_ood"],
        "embedder_mix": embed_mix(sysm, HELD),
    }, indent=2))

if __name__ == "__main__":
    main()
