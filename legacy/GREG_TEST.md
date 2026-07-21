# The Greg Test — runbook

## One command (does everything)
After upload + connect (steps below), the entire pipeline is a single launch:
```
sudo apt-get update -qq && sudo apt-get install -y unzip tmux && unzip -o overarching-package.zip && cd overarching-package && tmux new -s greg 'bash run_all.sh'
```
`run_all.sh` runs: setup -> Greg diagnostic (aggregate + ablations) -> Barry (sparse) -> auto-picks the
lowest-OOD winner -> completion run. Resumable (re-run the same line to continue). Detach with Ctrl-b then d.
Watch: `watch -n 15 python3 greg_status.py ~/greg_all.log`. Phone push: prefix `NOTIFY_URL=https://ntfy.sh/your-topic`.
Knobs: `FULL=1` (9 ablation arms), `SKIP_COMPLETION=1` (stop after the comparison), `COMPLETION="ENABLE_REENCODE=0"` (override the winner).
Total ~1 day on one H100. The individual scripts below still exist if you want to run a single stage.

---

Two phases on one GPU:

- **Phase 1 (diagnostic)** — `run_greg_test.sh`. Aggregate (all ideas on) + leave-one-out ablations, at a higher step count to fight undertraining. Tells you which ideas earn their keep and gives you the winning config.
- **Phase 2 (completion)** — `run_greg_completion.sh`. Takes that winner and runs it long, toward convergence.

There's a separate axis (continual / forgetting) in `run_lambda_followup.sh` — optional, run it if you also want the backward-transfer numbers. It doesn't feed the completion choice.

Everything is checkpoint-resumable: interrupt any time, re-run the same command, it continues.

---

## 0. Prerequisites
- A Lambda GPU instance, **80 GB recommended** (the probe/grow-only peak fits batch 16 there).
- Your key: `C:\Users\victo\Downloads\Laptop.pem`.
- The bundle: `overarching-package.zip`.
- All corpora except enwik8 are bundled in the zip; enwik8 is fetched on the instance by `setup_lambda.sh`.

## 1. Upload + connect
```
scp -i C:\Users\victo\Downloads\Laptop.pem overarching-package.zip ubuntu@<IP>:~
ssh -i C:\Users\victo\Downloads\Laptop.pem ubuntu@<IP>
```

## 2. Set up (once)
```
sudo apt-get update -qq && sudo apt-get install -y unzip tmux
unzip -o overarching-package.zip && cd overarching-package
bash setup_lambda.sh          # verifies CUDA torch, fetches enwik8, installs the console GPU monitor
```
If torch isn't CUDA-enabled: `pip3 install torch --index-url https://download.pytorch.org/whl/cu121`

## 3. Phase 1 — run the diagnostic
Always run inside tmux so it survives disconnects.

Recommended first pass (5 arms — the open questions: sense dense, sense sparse, counterparts, re-encode):
```
tmux new -s greg
QUICK=1 bash run_greg_test.sh
```
Full matrix (9 arms — also re-confirms tokenizer / MoE / memory at the higher step count):
```
tmux new -s greg
bash run_greg_test.sh
```
Detach with **Ctrl-b then d**. Re-attach with `tmux attach -t greg`. **Never `exit` the tmux window** — that kills the run.

Rough time: ~30 min per 5000 steps per arm, so ~1.5 h/arm at 15000. QUICK ≈ 7–8 h, full ≈ 13 h. Lower `STEPS` if you want a faster look; raise it if you want a cleaner ranking. Interrupted? Just re-run the same line — each arm resumes from its own `ckpt.pt`.

## 4. Monitor — live dashboard (this replaces staring at the log)
In a second pane (`tmux new -w` or split), or after `tmux attach`:
```
watch -n 15 python3 greg_status.py
```
It shows: arms done / total, the current arm's **step / % / ema loss / nodes / it-s / live ETA**, a **whole-run ETA**, the **ranking so far** (in-held / OOD, sorted), and a feed of the last events (evals, growth, completions). For the completion run: `watch -n 15 python3 greg_status.py ~/greg_completion.log`.

**Phone notifications (optional, no account):** set a `NOTIFY_URL` to a free [ntfy.sh](https://ntfy.sh) topic and you get a push per arm start/finish (with that arm's final numbers), plus start/complete for the whole run:
```
NOTIFY_URL=https://ntfy.sh/greg-4f9a2 QUICK=1 bash run_greg_test.sh
```
Install the ntfy app, subscribe to that exact topic string (pick something unguessable). Works for `run_greg_completion.sh` too.

Raw log is still there if you want it: `tail -f ~/greg_test.log`.

## 5. Read the result + pick the winner
At the end the log prints a `read_results.py` table. Rule:
- **Lowest OOD bits/byte** among all arms is your Phase-2 config.
- If an `abl_x` **ties** `agg` (within ~0.05), that idea isn't earning its keep on this axis — drop it in completion (leaner + faster).
- `agg` vs `abl_sense` = does the sense book help. `agg` (dense) vs `abl_sparse` = does promote-driven sparse sense match dense at a fraction of the folders (watch the `N/budget` line — if it saturates, the budget was the limit).
- Sanity: everything at 15000 is still short of true convergence; trust gaps larger than the ~0.05 eval noise, not smaller ones.

## H100 ramp — what changed
Tuned to actually feed an H100 SXM5 80GB (the old d384/batch-16 setup left it ~2% utilized):
- **Bigger model** — d512 / 8 layers (was d384/6), so each expert kernel is meatier.
- **Auto batch-size probe** — on launch each script tries batch 256→16 at full expert population and uses the largest that fits, then **scales LR to it** (√ rule, capped 1.5e-3). All arms share that batch (fair; sized to the aggregate, the memory ceiling).
- **Lower expert ceiling** — `NMAX=24` (was 48) frees memory so the probe can pick a bigger batch. The model only reached ~10 experts before, so 24 is ample headroom.

This is a **new, larger scale** — its bits/byte won't line up with the old d384 numbers; treat it as a fresh test. Everything is env-overridable (`D_MODEL=384 NMAX=48 …`) if you want the old scale back. Note the probe adds ~5–15 min at the very start of each script.

**The re-encode / batch tradeoff worth knowing:** re-encode is the memory hog, so with it *on* (the aggregate) the probe lands a modest batch (~24–48 on 80 GB). If Phase 1 says re-encode isn't earning its keep, `ENABLE_REENCODE=0` in completion lets the probe jump to a much larger batch (128+) — a big utilization win for the long run.

## Time estimates (whole process)
At the ramped scale (d512, auto-probed batch ~24–48, `STEPS` default 8000 for Phase 1 / 40000 for completion). Rough, on one H100 80 GB — the completion stage is the variable part (growth slows it as experts climb to `NMAX`):

| stage | time |
|---|---|
| Phase 1 QUICK (5 arms) | **~5–8 h** |
| Phase 1 full (9 arms) | **~10–14 h** |
| Phase 2 completion, re-encode ON | **~10–16 h** |
| Phase 2 completion, lean winner (re-encode OFF, big batch) | **~7–12 h** |

End-to-end: **QUICK diagnostic + a lean completion ≈ ~half a day to a day; full diagnostic + heavy completion ≈ ~1–1.5 days.** Once a run starts, the dashboard's live ETA is far more accurate than this table — trust it. To shorten: lower `STEPS`, lower `NMAX`, or pick a lean winner.



## You choose the config — nothing is automatic
Phase 1 and Phase 2 are **separate commands**. Phase 1 finishes, prints the ranking, and stops. Nothing launches the completion run for you. You read the ranking (dashboard or the final table), decide which config wins, and then type the Phase-2 command yourself with the flags you want. There is no auto-selection anywhere.


Default is the full aggregate. Override toggles from what Phase 1 told you, then launch:
```
tmux new -s gregfinal
# examples of overriding based on Phase 1:
#   SENSE_K=0 bash run_greg_completion.sh            # dense sense didn't help
#   SENSE_SLOTS=4096 bash run_greg_completion.sh     # sparse sense matched dense -> use it, cheaper at scale
#   ENABLE_REENCODE=0 COUNTERPARTS=0 bash run_greg_completion.sh
STEPS=40000 bash run_greg_completion.sh
```
Writes to `greg_final/`, checkpoints every 5000 steps. Stop/resume any time by re-running. `tail -f ~/greg_completion.log`.

## 7. (Optional) continual axis
Separate question — does surprise-gated replay prevent forgetting, and do counterparts help retention:
```
tmux new -s greg2
STEPS=10000 PRE=6000 ADP=3000 bash run_lambda_followup.sh
```

## 8. Retrieve results
On the instance:
```
tar czf ~/results.tgz greg_test.log greg_completion.log */train_log.jsonl greg_final/ agg/ abl_*/ 2>/dev/null
```
On your laptop:
```
scp -i C:\Users\victo\Downloads\Laptop.pem ubuntu@<IP>:~/results.tgz .
```
Paste `greg_test.log` (it ends with the ranking table) back and we'll read it together and choose the completion config.

## 9. STOP BILLING
Closing SSH does **not** stop the instance. In the Lambda web console, **Terminate/Stop** the instance when done. (Checkpoints are on the instance disk — pull `results.tgz` first if you want to resume later.)

---

## Knob reference (for overrides)
| knob | meaning |
|---|---|
| `STEPS` | training steps (Phase 1 default 8000, Phase 2 default 40000) |
| `BATCH` | **auto-probed** to the largest that fits; set to pin it manually |
| `D_MODEL` `N_LAYERS` | model size (ramp default 512 / 8; set 384 / 6 for the old scale) |
| `NMAX` | max experts (ramp default 24; higher = more capacity, smaller batch) |
| `M_EMBED` | MoE embedder tables (0 = off) |
| `SENSE_K` | branches per token folder (0 = off) |
| `SENSE_SLOTS` | 0 = dense (all tokens); >0 = sparse memory-backed budget |
| `SENSE_POS` | 1 = per-position routing (polysemy), 0 = per-sequence |
| `SENSE_PROMOTE` | surprise mass before a sparse folder spawns |
| `COUNTERPARTS` | invertibility auxiliary (0/1) |
| `ENABLE_REENCODE` | full-base re-encode (0/1); `REENCODE_WARMUP`, `REENCODE_SURPRISE` refine it |
| `MEMORY` | `mirror` (stored vector bank + recall) or `off` |
| `TOK` (completion) | `dynamic` or `frozen` |

Notes: memory is saved in the checkpoint and reloaded (a stored vector bank, not a recomputed context window). Sparse sense folders (`tok2slot`, `sparse_sense`, `n_promoted`) also persist. `BATCH` above 16 will OOM at full population on 80 GB with re-encode on; drop re-encode or lower batch if you change scale.

---
## Barry — the sparse-fabric variant (same system, one knob)
Barry is Greg with the dense expert loop replaced by **sparse top-k MoE** (`barry.py`): each token
routes to only its `MOE_K` best experts, so cost stays ~flat as experts grow. It's the SAME class and
harness — flip one knob:
- **Greg:** `FABRIC=dense` (default) — recurrent dense loop, plus counterparts + re-encode.
- **Barry:** `FABRIC=sparse` — stacked sparse-MoE fabric. Keeps tokenizer, MoE embedders, sense book,
  memory, surprise, growth, replay. (Counterparts and re-encode are dense-fabric features, off for Barry v1.)

Barry knobs: `MOE_K` (experts/token, 2), `FABRIC_LAYERS` (2), `CAP_FACTOR` (1.25, capacity slack),
`LB_COST` (0.01, load-balance weight). Growth grows the sparse bank; checkpoints save/resume.

**Head-to-head:** `STEPS=8000 tmux new -s vs ; bash run_head_to_head.sh` runs both at a matched batch/steps
and prints Greg vs Barry (compare OOD bits/byte for quality, it/s in the log for speed). Watch with
`watch -n 15 python3 greg_status.py ~/vs.log`. You can also run Barry through any command by adding
`FABRIC=sparse` (e.g. `FABRIC=sparse bash run_greg_completion.sh` to take Barry long).
