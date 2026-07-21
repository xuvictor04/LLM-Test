# SINGLE CONTROL

Everything runs through `control.py` -- one entry point, one place to turn capabilities on/off:

    python3 control.py setup                     # data
    python3 control.py train    --preset full    # train the main system (all capabilities on)
    python3 control.py train    --preset larry    # self-scaling growth run (no target size)
    python3 control.py continual                  # continual learning + backward-transfer
    python3 control.py test     robust,fuzzy      # tokenizer harness (correct/compress/robust/fuzzy/modeling/recon)
    python3 control.py chat      best.pt           # generate (pass the arch/preset you trained with)
    python3 control.py sweep     eco               # sweeps: eco | scale | greg

Presets bundle capability knobs (CLI `KNOB=val` overrides them): `base` (all off), `full` (all on),
`larry` (self-scaling). The sections below document individual knobs; the control just composes them.

---
# Barry scale-up — runbook

Full-capability Barry (sparse fabric + counterparts + MoE embedders + sense + memory + surprise + growth),
high expert ceiling, on the fixed full-enwik8 corpus. Everything below is copy-paste. Replace `<IP>` with your
instance IP. Your key is `C:\Users\victo\Downloads\Laptop.pem`.

---

## 1. Upload (from your laptop / PowerShell)
```
scp -i C:\Users\victo\Downloads\Laptop.pem overarching-package.zip ubuntu@<IP>:~
```

## 2. Connect
```
ssh -i C:\Users\victo\Downloads\Laptop.pem ubuntu@<IP>
```

## 3. Set up (paste the whole block; safe to re-run)
```
sudo apt-get update -qq && sudo apt-get install -y unzip tmux
unzip -o overarching-package.zip && cd overarching-package
```
(The run auto-fetches enwik8 if it isn't already there — no separate setup step needed.)

## Next run — bigger vocab (defaults updated)
The 8,192 vocab was a plateau ceiling. The run now defaults to **VMAX=32768, MIN_PAIR=200, STEPS=50000** (bigger
vocabulary, more eager minting). Two things to know:

- **It must be a FRESH run.** A different vocab size = different table shapes, so it CANNOT resume the old
  `barry_scale/` checkpoint (built at 8192) -- that would crash on a shape mismatch. Clear it first:
  ```
  cp barry_scale/best.pt ~/barry_v1_best.pt 2>/dev/null   # optional: keep the old model
  rm -rf barry_scale
  ```
- **More data is now built in.** Setup auto-fetches, by default, enwik8 (~96MB) **plus ~15 public-domain books**
  (more prose diversity). For a real 10x, launch with `DATASET=enwik9` -> the 1GB Wikipedia dump (breaks the plateau):
  ```
  DATASET=enwik9 tmux new -s barry 'bash run_barry_scale.sh'
  ```
  (enwik9 is a ~300MB download + ~1-2 min to load + ~8-16GB RAM at load -- fine on the 225GB instance. The book
  fetch is best-effort; `EXTRA_BOOKS=0` skips it.) You can still drop your own `*.txt` into `data/train/<domain>/` too.

- **Diverse sources (web + code + reddit), not just Wikipedia** -- add `DIVERSE=1`. Setup installs `datasets` and
  fetches slices of FineWeb (web text), GitHub code **routed into per-language domains** (py/js/c/go/rust/...), and
  Reddit -- each becomes a new domain the experts can specialize on. Best-effort: any source that needs an HF login
  or fails is skipped (non-fatal). Tune with `WEB_MB` `CODE_MB` `REDDIT_MB` (defaults 200/200/100).
  ```
  DIVERSE=1 DATASET=enwik9 tmux new -s barry 'bash run_barry_scale.sh'
  ```
- **Your own Reddit/JSON dumps** -- drop `*.json` / `*.jsonl` into `data/raw_json/` and `DIVERSE=1` ingests them
  (pulls body/selftext/title/text fields) into a `reddit` domain. (Or run `python3 fetch_data.py` directly any time.)

Then launch (new defaults, nothing to remember):
```
tmux new -s barry 'bash run_barry_scale.sh'
```
Override if you want: `VMAX=65536 MIN_PAIR=150 STEPS=80000 bash run_barry_scale.sh`.

**Chatting:** `talk.sh` now defaults to the new vocab (32768). To chat with the OLD step-8000 model, override:
`VMAX=8192 bash talk.sh "..."`.

---
## 4. Launch (the one command)
```
STEPS=30000 NMAX=128 tmux new -s barry 'bash run_barry_scale.sh'
```
**Batch note:** the tokenizer is now ~8x faster (cached segmentation + NumPy-vectorized pair tally + pruned
inner loop) and a **prefetch worker** (on by default) overlaps it with GPU compute. At the batch sizes that fit
(up to the auto-probed 256), tokenizer CPU is now *below* GPU step time, so the run is GPU-bound — the one-core
tokenizer is no longer the bottleneck. Just launch without `BATCH` to auto-probe the max (256); it starts after a
~5-15 min probe, or pin `BATCH=128` to skip the probe and start immediately. `PREFETCH=0` disables overlap if needed.

**Further speed (H100):** add `AMP=1` for bf16 autocast — fast on Hopper, frees memory for a bigger batch. Try it if you want more.
Detach with **Ctrl-b then d**. Re-attach any time with `tmux attach -t barry`. **Never `exit` the tmux window** — that kills the run. Interrupted or crashed? Just run the same line again — it resumes from the last checkpoint.

Phone push (optional — pick an unguessable topic, install the ntfy app, subscribe to it):
```
STEPS=30000 NMAX=128 tmux new -s barry 'NOTIFY_URL=https://ntfy.sh/your-topic bash run_barry_scale.sh'
```

## 5. Watch it live (second pane, or after re-attaching)
```
watch -n 15 python3 greg_status.py ~/barry_scale.log
```
Raw tail if you prefer: `tail -n 30 ~/barry_scale.log`

## 6. What healthy looks like
- **enwik8 is now auto-fetched** by setup (the earlier bug: the fetch was missing). Watch for `enwik8 OK (96 MB)` during setup.
- **Corpus line** must read **tens of thousands of chunks** (~90k with enwik8). If it prints a `!! WARNING: only N train chunks`
  line, enwik8 failed to download — stop and fetch it by hand (the warning prints the exact command), then relaunch.
- After a few minutes of `warming up base`, you'll see `FRESH | nodes 18`, `[surprise] REVERSE-PREDICTOR active`, then `step 0 …`.
- **it/s stays roughly flat** as `nodes` climbs past 24, 50, 100 — that's Barry's whole point (Greg dropped ~linearly here).
- **OOD should fall and keep falling** at each eval (every 2000 steps). Unlike the last run, there's now enough data to justify the steps, so it shouldn't rise/overfit.
- Sanity check in another pane if it ever feels stuck >10 min: `nvidia-smi` — a python process should be using the GPU with several GB held.

## 7. Tune it (env vars in front of the launch, inside the quotes)
| knob | default | meaning |
|---|---|---|
| `STEPS` | 30000 | training steps. Bump higher if OOD is still dropping at the end. |
| `NMAX` | 128 | max experts. Barry grows toward this ~1 per 500 steps. |
| `N0` | 16 | starting experts. Set `N0=64` to pin it high immediately. |
| `MOE_K` | 2 | experts each token uses (top-k). `4` = more capacity per token. |
| `FABRIC_LAYERS` | 2 | stacked sparse-MoE layers (depth of the fabric). |
| `BATCH` | auto | probed to the largest that fits; set to pin it. |
| `D_MODEL` `N_LAYERS` | 512 / 8 | model size. |

Example — pin high and run longer:
```
STEPS=60000 NMAX=256 N0=64 tmux new -s barry 'bash run_barry_scale.sh'
```

## 8. Retrieve results
On the instance:
```
tar czf ~/barry_results.tgz barry_scale.log barry_scale/train_log.jsonl barry_scale/ckpt.pt 2>/dev/null
```
On your laptop:
```
scp -i C:\Users\victo\Downloads\Laptop.pem ubuntu@<IP>:~/barry_results.tgz .
```
Paste `barry_scale.log` back to me and we'll read it together.

## 8b. Which checkpoint to use
Early-stop is on (`EARLY_STOP=5`): the run halts if held OOD stalls for 5 evals, and the **best** model is saved to
`barry_scale/best.pt` (not just the last `ckpt.pt`). Use `best.pt` as the result — it's the peak, before any overfitting.

## 9. Stop billing
Closing SSH does **not** stop the instance. In the Lambda web console, **Terminate/Stop** it when done. (Pull `barry_results.tgz` first if you might resume later — checkpoints live on the instance disk.)

---

## Troubleshooting
- **"warming up base" for a few minutes at the start** — normal (a short base pretrain + first-step compile before `step 0`).
- **~5–15 min of `probing … OOM` lines at the very start** — normal; it's finding the largest batch that fits. Then `BATCH=… LR=…` prints and training begins.
- **Corpus still ~3,409 chunks** — you're on the old code. Re-upload the latest zip and relaunch.
- **Want it to stop overfitting automatically** — ask me to add a train/val split with early-stop; for now, watch the OOD curve and stop when it flattens/rises.
- **Resume** — re-run the exact launch line; it continues from `barry_scale/ckpt.pt`.

---
## Evolutionary Barry — survival-pressure experts (`run_eco_sweep.sh`)
Three architectural levers that make experts *earn* their place, so specialization emerges instead of being designed:
- **Bottleneck** (`EXPERT_HIDDEN_MULT`, default 4.0) — shrink each expert's hidden dim below 4×d so it *can't* memorize much and is pushed toward a compressed, general niche. Try 2, 1, 0.5.
- **Mutation spawn** (`MUTATE=1`, `MUTATE_STRENGTH` 0.05) — new experts are perturbed copies of the *best* expert (by gated-output energy), not random — actual reproduction-from-success.
- **Contribution cull** (`PRUNE_ECO=1`, `PRUNE_EVERY` 1000, `NMIN` 8) — periodically remove the *least*-contributing expert. Combined with growth, the population churns under selection: spawn from the strong, cull the weak.

Run the sweep (scans all three across ~8 arms at a matched batch/steps, then prints OOD):
```
STEPS=8000 tmux new -s eco 'bash run_eco_sweep.sh'
```
Watch: `watch -n 15 python3 greg_status.py ~/eco.log`. Subset with `ARMS="base bn1 full"`. Runs on the full **enwik9 + diverse** corpus by default (the levers need scale + variety); the winner then gets a longer run. ~1 day for all 8 arms at 8000 steps on one H100.

**Honest caveat:** selection guarantees *division of labor*, not that the divisions are *grammatical* — an expert can survive by capturing a lazy surface niche instead of a real rule. The bottleneck makes surface-memorization harder (so generalizing is a better survival strategy), but whether this breaks the 3.43 OOD floor is the open question the sweep answers. It's a research bet, not a known win.

---
## Multiprocess tokenizer (`MP_WORKERS`)
The dynamic tokenizer is single-threaded; caching + the prefetch thread hide it behind the GPU, so at batch 256
it's **not** the bottleneck (GPU-bound). For very large batch / cold cache (enwik9-scale) where one core can't
keep up, `MP_WORKERS=N` runs N worker PROCESSES that segment in parallel (true multi-core, bypasses the GIL):
```
MP_WORKERS=4 tmux new -s barry 'bash run_barry_scale.sh'
```
Workers hold vocab replicas and feed a batch queue; the main process tallies + mints + broadcasts new merges
back. Uses spawn + a memory-mapped corpus (fork is unsafe after torch init). Default `MP_WORKERS=0` = off
(the proven single-thread prefetch runs). Verified end-to-end; enable only if the tokenizer is actually your
bottleneck (check it/s with vs without).
