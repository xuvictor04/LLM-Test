#!/usr/bin/env python3
"""ONE control for the whole system. Every mode + every capability behind a single entry point.

  python3 control.py clbench   [KNOB=val ...]      # CONTINUAL-LEARNING testbed: forgetting / editable memory / wrongness detection
  python3 control.py profile   [--preset X]        # THROUGHPUT + VRAM + hotspot + wall-clock projection (run before a long run!)
  python3 control.py analyze   <dir/ckpt> [secs]   # UNDERSTAND a run: growth payoff / expert specialization / compose / fuzzy
  python3 control.py check                         # PRE-FLIGHT: verify the whole package before GPU testing
  python3 control.py fulltest                      # AUTOMATED: run the ENTIRE EXPERIMENTS.md plan unattended
  python3 control.py setup                        # fetch/prepare data (enwik + diverse)
  python3 control.py train     [KNOB=val ...]     # train the main system (all feature toggles apply)
  python3 control.py continual [KNOB=val ...]     # continual learning across domains + backward-transfer logging
  python3 control.py test      [sec1,sec2 ...]    # tokenizer harness: correct,compress,robust,fuzzy,modeling,recon
  python3 control.py test      components        # run the component correctness tests
  python3 control.py chat      [ckpt]             # generate from a checkpoint (pass the SAME arch knobs / preset you trained with)
  python3 control.py sweep     [eco|training|arch|robust|scale|greg]  # isolate levers: eco/training/arch(incl NN-init)/robust/scale/greg

PRESETS group capabilities by axis so each can be tested in ISOLATION against base (CLI KNOB=val overrides them):
  --preset base    every new capability OFF -- the control baseline
  --preset train   training methods only, NO new params (cosine LR, weight-EMA, z-loss, label-smoothing)
  --preset eco     evolutionary experts (bottleneck + mutation + contribution cull + foundation phase)
  --preset robust  error-correction stack (denoise + reconstruction head + fuzzy tokenizer)
  --preset arch    representation features, PARAM-HEAVY (compositional embeddings + correction hooks + multi-token)
  --preset depth   DEPTH growth: narrow breadth so experts saturate -> the controller grows LAYERS (2-tier growth)
  --preset full    union of train+eco+robust+arch (kitchen sink -- confounded; stress test, not science)
  --preset larry   self-scaling: small seed, breadth+depth growth, competence stop, ceiling -- no target size

Examples:
  python3 control.py train --preset train DATASET=enwik9 DIVERSE=1   # test training methods alone vs base
  python3 control.py train --preset eco                              # test evolutionary experts alone
  python3 control.py train --preset base                             # the baseline to compare against
  python3 control.py sweep training                                  # rank the training-method levers (isolated)
  python3 control.py test robust,fuzzy                               # typo + fuzzy-correction aspects
"""
import os, sys, subprocess

# ---- capability knob bundles (env), grouped so each GROUP can be tested in isolation against `base`. ----
# base = the clean control. train/eco/robust/arch are single-axis groups. full = their union. larry = self-scaling.
PRESETS = {
    "base": {   # every new capability OFF -- the baseline everything is measured against
        "COMPOSE_EMB": "0", "CORRECT_AT": "none", "DENOISE": "0",
        "CTX_START": "0", "GROWTH_START": "0", "MUTATE": "0", "PRUNE_ECO": "0",
        "LR_SCHEDULE": "constant", "MTP_K": "1", "EMA_DECAY": "0",
        "LABEL_SMOOTH": "0", "EXPERT_HIDDEN_MULT": "4",
    },
    "train": {  # training-method levers only -- NO new parameters/heads (cheapest to test)
        "LR_SCHEDULE": "wsd", "WSD_DECAY_FRAC": "0.2", "EMA_DECAY": "0.999",
        "LABEL_SMOOTH": "0.05",
    },
    "eco": {    # evolutionary experts: bottleneck + mutation + contribution cull (+ foundation phase)
        "EXPERT_HIDDEN_MULT": "1", "MUTATE": "1", "MUTATE_STRENGTH": "0.05",
        "PRUNE_ECO": "1", "PRUNE_EVERY": "1000", "NMIN": "12", "CULL_METRIC": "traffic", "GROWTH_START": "2000",
    },
    "robust": { # error-correction stack: denoise (corrupt->clean) + reconstruction head + fuzzy tokenizer
        "DENOISE": "0.1", "DENOISE_MODE": "mix",
    },
    "arch": {   # representation features (PARAM-HEAVY: compose atoms + correction nets + MTP heads). caching on.
        "COMPOSE_EMB": "0.5", "COMPOSE_DEPTH": "3", "COMPOSE_REFRESH": "8",
        "CORRECT_AT": "emb,fabric", "MTP_K": "2", "NN_INIT": "0.7",
    },
    "depth": {  # DEPTH growth: narrow breadth cap so experts saturate -> controller grows LAYERS (2-tier growth)
        "DEPTH_GROWTH": "1", "MAX_LAYERS": "16", "NMAX": "24", "N0": "16",
    },
    "full": {   # union of train + eco + robust + arch + depth (kitchen sink -- confounded; stress test, not science)
        "LR_SCHEDULE": "wsd", "WSD_DECAY_FRAC": "0.2", "EMA_DECAY": "0.999", "LABEL_SMOOTH": "0.05",
        "EXPERT_HIDDEN_MULT": "1", "MUTATE": "1", "MUTATE_STRENGTH": "0.05", "PRUNE_ECO": "1",
        "PRUNE_EVERY": "1000", "NMIN": "12", "CULL_METRIC": "traffic", "GROWTH_START": "2000",
        "DENOISE": "0.1", "DENOISE_MODE": "mix",
        "COMPOSE_EMB": "0.5", "COMPOSE_DEPTH": "3", "COMPOSE_REFRESH": "8", "CORRECT_AT": "emb,fabric", "MTP_K": "2", "NN_INIT": "0.7",
        "NN_INIT_K": "3", "CROSSOVER": "0.5", "EXPERT_COORD": "0.5", "UNMERGE": "3000", "UNMERGE_MIN": "3", "DIFFICULTY_CURR": "4000",
        "CTX_START": "64", "CTX_RAMP_STEPS": "3000", "DEPTH_GROWTH": "1", "MAX_LAYERS": "16",
    },
    # larry/: self-scaling -- small seed grows breadth-first then depth, stops on competence plateau, ceiling guards VRAM
    "larry": {
        "D_MODEL": "256", "N_LAYERS": "4", "CTX": "512", "N0": "3", "NMAX": "256",
        "DEPTH_GROWTH": "1", "MAX_LAYERS": "24", "EARLY_STOP": "8", "STEPS": "200000",
        "GROWTH_START": "0", "EXPERT_HIDDEN_MULT": "4",
    },
}

# base architecture shared by train/continual -- the real scale spec (mirrors run_barry_scale.sh). All overridable.
BASE_ENV = {
    "SURPRISE": "reverse", "FABRIC": "sparse", "MOE_K": "2", "FABRIC_LAYERS": "2", "COUNTERPARTS": "1",
    "M_EMBED": "4", "SENSE_K": "3", "SENSE_POS": "1", "MEMORY": "mirror",
    "TOKENIZER": "dynamic", "VOCAB": "256", "VMAX": "32768", "MIN_PAIR": "200",
    "DATASET": "enwik9", "DIVERSE": "1",
    "D_MODEL": "512", "N_LAYERS": "8", "N_HEADS": "8", "CTX": "256", "MAX_LEN": "512", "MEMCAP": "65536",
    "NMAX": "64", "N0": "16", "GRACE": "600", "PATIENCE": "500", "COOLDOWN": "300", "LR_WARMUP": "1500", "DEPTH_GROWTH": "0",
}


def _split_args(argv):
    """Return (preset_name_or_None, {KNOB:val}, [positional])."""
    preset, knobs, pos = None, {}, []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--preset":
            preset = argv[i + 1]; i += 2; continue
        if "=" in a and a.split("=", 1)[0].isupper():
            k, v = a.split("=", 1); knobs[k] = v
        else:
            pos.append(a)
        i += 1
    return preset, knobs, pos


def _env(preset, knobs, with_base_arch=True):
    e = dict(os.environ)
    if with_base_arch:
        for k, v in BASE_ENV.items(): e.setdefault(k, v)
    if preset:
        if preset not in PRESETS:
            sys.exit(f"unknown preset '{preset}'. options: {', '.join(PRESETS)}")
        for k, v in PRESETS[preset].items(): e[k] = v          # preset sets capability defaults...
    for k, v in knobs.items(): e[k] = v                        # ...explicit CLI knobs override
    return e


def _run(cmd, env):
    print(f"[control] {' '.join(cmd)}" + (f"  (preset applied)" if env is not os.environ else ""))
    return subprocess.run(cmd, env=env).returncode


def main():
    if len(sys.argv) < 2:
        print(__doc__); return
    mode = sys.argv[1]
    preset, knobs, pos = _split_args(sys.argv[2:])

    if mode == "fulltest":
        sys.exit(subprocess.run(["bash", "run_full_test.sh"], env=_env(None, {})).returncode)
    if mode == "clbench":
        e = _env(None, knobs)
        sys.exit(subprocess.run([sys.executable, "cl_bench.py"], env=e).returncode)
    if mode == "profile":
        e = _env(preset, knobs)
        sys.exit(subprocess.run([sys.executable, "bench.py"], env=e).returncode)
    if mode == "analyze":
        e = _env(preset, knobs)
        sys.exit(subprocess.run([sys.executable, "analyze.py"] + pos, env=e).returncode)
    if mode == "check":
        sys.exit(subprocess.run([sys.executable, "preflight.py"]).returncode)
    if mode == "setup":
        e = _env(preset, knobs)
        sys.exit(_run(["bash", "setup_lambda.sh"], e))
    if mode == "train":
        e = _env(preset, knobs)
        sys.exit(_run(["python3", "train.py"], e))
    if mode == "continual":
        e = _env(preset, knobs)
        sys.exit(_run(["python3", "continual.py"], e))
    if mode == "test":
        if pos and pos[0] == "components":                     # run the component correctness tests through the control
            e = _env(preset, knobs)
            tests = ["vector_experts_test.py", "sense_memory_test.py", "test_mirrored_integration.py",
                     "greg_reverse_novelty.py", "measure_memory.py"]
            rc = 0
            for t in tests:
                if os.path.exists(t):
                    print(f"\n[control] component test: {t}")
                    rc = subprocess.run(["python3", t], env=e).returncode or rc
            sys.exit(rc)
        e = _env(preset, knobs, with_base_arch=False)
        if pos: e["SECTIONS"] = pos[0] if "," in pos[0] else ",".join(pos)
        sys.exit(_run(["python3", "test_tokenizer.py"], e))
    if mode == "chat":
        e = _env(preset, knobs)
        if pos: e["CKPT"] = pos[0]
        sys.exit(_run(["python3", "chat.py"] + (pos[1:] if len(pos) > 1 else []), e))
    if mode == "sweep":
        which = pos[0] if pos else "eco"
        script = {"eco": "run_eco_sweep.sh", "training": "run_training_sweep.sh", "arch": "run_arch_sweep.sh", "robust": "run_robust_sweep.sh", "scale": "run_barry_scale.sh", "greg": "run_all.sh"}.get(which)
        if not script: sys.exit(f"unknown sweep '{which}' (eco | training | arch | robust | scale | greg)")
        e = _env(preset, knobs)
        sys.exit(_run(["bash", script], e))
    print(f"unknown mode '{mode}'.\n"); print(__doc__)


if __name__ == "__main__":
    main()
