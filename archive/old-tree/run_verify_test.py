#!/usr/bin/env python3
"""One-shot VERIFICATION (reconstruction) vs old-B A/B test -- copy-paste onto the H100 and run:

    python3 run_verify_test.py

It configures a Garry-like GPU run with Verification ON, runs the product loop (train -> assemble -> the
wrongness test), and prints BOTH signals' precision on the SAME injected corruption -- that single run IS the A/B.
Watch the output for two lines:
    === VERIFICATION (reconstruction) [VERIFY=recon]: ... precision P% ...   <- the new signal
    === WRONGNESS (B) in the loop: ...                                        <- the old ~1% baseline below it
SUCCESS = the reconstruction precision clearly beats B's ~1%.

Every setting is overridable from the environment, e.g. a fast CPU smoke test:
    DEVICE=cpu STREAM_LEN=4000 D_MODEL=32 WIN=16 ENC_WARMUP=60 FABRIC=0 TOKENIZER=0 PROBE=0 python3 run_verify_test.py
"""
import os

# ---- Garry-like config with Verification ON. os.environ wins, so any override above takes effect. ----
DEFAULTS = {
    "DEVICE": "cuda", "DATA_MODE": "real", "DOMAINS": "eng,py,num,c",
    # the thing under test:
    "VERIFY": "recon",            # 'recon' = the new reconstruction Verification; 'selfcon' = the old B (default in repo)
    "RECON_W": "0.1",             # Reconstructor training weight
    "WRONG_INJECT": "100",        # inject 100 corrupt entries so precision is a STABLE number, not noise (was 8)
    "WRONG_SWEEP": "0",
    # base model + stream (Garry redundancy regime):
    "MODEL": "gru", "D_MODEL": "512", "WIN": "96", "STREAM_LEN": "6000000",
    # society / router:
    "FABRIC": "1", "SOCIETY": "1", "ENS_K": "2", "IND_W": "0.5", "IND_K": "2",
    "FAB_N0": "3", "FAB_NMAX": "6", "FAB_STEPS": "3", "FAB_DK": "32", "PONDER": "0.01",
    # online tokenizer:
    "TOKENIZER": "1", "TOK_ONLINE": "1", "VMAX": "8192", "SEED_VOCAB": "1024", "MIN_PAIR": "80",
    "GROW_EVERY": "40", "GROW_BURST": "10", "RETOK_EVERY": "3000", "GROW_PASSES": "10", "TOK_GROW_CAP": "1500000",
    # memory + assembly:
    "KEY_SRC": "model", "MEM_CAP": "300000", "EVICT": "recency", "MANAGE": "1", "EXPERTS": "0",
    "SIG_MODE": "learned", "SIG_D": "64", "ENC_WARMUP": "30000", "ENC_EVERY": "2", "ENC_BATCH": "128",
    "REKEY_EVERY": "300", "EVAL_N": "128", "WRITE_ADAPTIVE": "1", "WRITE_TARGET": "0.4",
    "PROBE": "1",                 # prints the wall-clock estimate + a 12s abort window before the long run
}
for k, v in DEFAULTS.items():
    os.environ.setdefault(k, v)

bar = "=" * 74
print(bar)
print("VERIFICATION A/B TEST  --  reconstruction (new) vs self-consistency B (old)")
print("  VERIFY=%s  WRONG_INJECT=%s  MODEL=%s  D_MODEL=%s  STREAM_LEN=%s  DEVICE=%s"
      % (os.environ["VERIFY"], os.environ["WRONG_INJECT"], os.environ["MODEL"],
         os.environ["D_MODEL"], os.environ["STREAM_LEN"], os.environ["DEVICE"]))
print("  -> look for 'VERIFICATION (reconstruction) ... precision' and the 'WRONGNESS (B)' block below it.")
print("  -> SUCCESS = reconstruction precision clearly beats B's ~1%.")
print(bar, flush=True)

import self_organize            # module-level setup reads the env set above (config + data load)
self_organize.main()           # runs the product loop, incl. the Verification/B A/B in the wrongness test
