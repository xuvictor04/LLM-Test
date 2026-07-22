# Command cheatsheet

Every flag below was verified present in the code before this file was written (grepped, not assumed). If something
here stops working, the code changed and this file didn't — check `../STATE.md` (§5 config, §7 results) first.

`RUN_NAME=<tag>` namespaces the log (`~/<tag>.txt`), checkpoint (`runs/<tag>/`), and tokenizer cache
(`data/tok_<tag>.json`) so runs never overwrite each other. Always set it for anything you want to keep.

## Reproduce the frozen baseline (redundancy regime, 1.967 b/B)
```
cd garry && bash run_full_unfrozen.sh          # writes ~/garry.txt, runs/garry/
python3 prompt.py CKPT=runs/garry              # message it
```

## Reproduce the modularity regime (specialization, 2.002 b/B, concentrated deletion cost)
```
RUN_NAME=modularity ROUTE_GROUNDED=1 ROUTE_T=0.3 bash run_full_unfrozen.sh
```

## Full system, everything on, from the dev copy (root, not garry/)
```
RUN_NAME=full bash run_full_unfrozen.sh
```
Key switches (default ON unless noted): `FABRIC=1 SOCIETY=1 ENS_K=2`, `TOKENIZER=1 TOK_ONLINE=1`, `MANAGE=1`,
`EVICT=recency` (not `usage` — doesn't protect faded knowledge; see `../STATE.md §7`, non-stationary line).

## Fresh cloud box (nothing installed, no clone) — run this first
```bash
cd ~ && rm -rf LLM-Test && git clone -q https://github.com/xuvictor04/LLM-Test.git && cd LLM-Test
python3 -c "import torch" 2>/dev/null || pip install -q torch numpy
```
(The run scripts cd to their own directory, so they work from any clone location.)

## Test VERIFICATION (reconstruction) vs the old self-consistency B  [VERIFY=recon]
**One paste into a Python console (mobile-friendly; clones the public repo itself, needs only torch + the bundled data):**
```python
import os, subprocess
if not os.path.exists("verify_console_test.py"):
    if not os.path.isdir("LLM-Test"):
        subprocess.run(["git", "clone", "https://github.com/xuvictor04/LLM-Test.git"], check=True)
    os.chdir("LLM-Test")
subprocess.run(["git", "pull"], check=False)
os.environ.update(STEPS="8000", RSTEPS="3000", PERDOM="400000")   # a properly-trained run
exec(open("verify_console_test.py").read())
```
Want: reconstruction AUC + precision@1% clearly above self-consistency B (toy CPU already gave 0.978/100% vs 0.903/30.5%).

**Easiest — one script:** `python3 run_verify_test.py` (Garry-like config, Verification ON, prints both precisions).
Or the full-suite route (also prints both, plus everything else):
```
VERIFY=recon WRONG_INJECT=100 RUN_NAME=verify bash run_full_unfrozen.sh
```
Read `~/verify.txt` for two lines: `=== VERIFICATION (reconstruction) … precision P% …` and the old
`=== WRONGNESS (B) … ===` block. SUCCESS = recon precision clearly beats B's ~1%. Default `VERIFY=selfcon` is
unchanged (Reconstructor not built). Knobs: `RECON_W` (recon train weight, 0.1), `RECON_TOK`/`RECON_HID` (32/64).
CPU mechanism check (no GPU): `python3 verification.py` → separation AUC (~0.93 on structured data).

## Ablations (one env var against the full run)
```
RUN_NAME=abl_manage MANAGE=0 bash run_full_unfrozen.sh             # management vs QUALITY? (no cost — STATE §7; RESOLVED)
RUN_NAME=abl_evict EVICT=usage PHASED=1 bash run_full_unfrozen.sh  # does usage-eviction protect faded knowledge? (no)
PHASED=1 RUN_NAME=nonstat bash run_full_unfrozen.sh                # non-stationary stream test
```

## Message the trained model
```
python3 prompt.py CKPT=runs/<tag>                 # plain generation
python3 prompt.py CKPT=runs/<tag> MEM=1           # blend memory into generation
python3 prompt.py CKPT=runs/<tag> MEM=1 GROUND=1  # recall relevant material INTERNALLY first — never shows raw
                                                  # passages; reply is always the model's own language
python3 prompt.py CKPT=runs/<tag> PROMPT="one-shot text"   # no interactive loop
```

## Get more data
```
bash fetch_data.sh                 # ~85 MB: NLTK Gutenberg/Brown/Reuters + CPython source (verified in-sandbox)
BIG=1 bash fetch_data.sh           # ~1 GB: adds GitHub-hosted Gutenberg-derived corpora
pip install datasets
python3 fetch_big.py --dataset fineweb-edu --gb 5   # streams a slice of an ESTABLISHED dataset — HF network is
                                                    # UNTESTED from the build sandbox; the USER must run + debug it
python3 fetch_big.py --dataset oasst1 --gb 1        # DIALOGUE, turn-marked — the one source that teaches turn-taking
```
Then point a run at it: `DATA_DIR=data_big CORPUS_CAP=<bytes> STREAM_LEN=<bytes> bash run_full_unfrozen.sh`.

## Scale up training (throughput fix — STREAM_LEN must scale WITH BATCH_W or the model trains LESS)
```
RUN_NAME=scale DATA_DIR=data_big CORPUS_CAP=2000000000 STREAM_LEN=<scale with BATCH_W> \
  WIN=256 BATCH_W=16 ACCUM=4 D_MODEL_B=768 VMAX=16384 bash run_full_unfrozen.sh
```

## Before any GPU run (standing directive)
Read the printed `[probe]` line + the cl_bench wall-clock estimate — both print and pause before committing. After the run watch:
- `[LM training curve]` — still falling ⇒ more steps/passes help; flat ⇒ needs more capacity.
- `MEMORIZATION CHECK` (train vs held-out gap) — small/negative ⇒ keep training as-is; past ~0.5 ⇒ turn on `DROPOUT=0.1 WEIGHT_DECAY=0.01` (built, default off).
</content>
