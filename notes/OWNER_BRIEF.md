# Owner brief

The one page for the owner. Everything else — how decisions were made, the evidence, the exact test
rules — is in the repo for reference (`docs/proposals/05_DECISIONS.md`, `docs/04_CONTRACT.md`,
`results/`, `notes/AGENT_STATE.md`) and is not brought up here.

Updated 2026-09-27 (8144701).

## How we work
- **Owner:** leads and monitors, keeps the goals from drifting, adds ideas, expands the project, and
  runs GPU tests when the card is free.
- **Manager (the agent):** resolves decisions, designs, builds, tests operation on CPU, writes the
  GPU scripts, reads their results, and documents everything.
- **Brought to the owner:** major issues that threaten the project, potential expansions, and GPU
  tests as copy-paste blocks. Each GPU script ends by printing a `==== PASTE THIS BACK ====` block;
  paste it into the chat (the GPU box has no push token).
- Owner rulings stand until the owner changes them. If a GPU result contradicts one, it comes here.

## Goals check
- **B — keep learning after training, without risking too much (first priority).** Not there yet:
  the tree has no post-training learning mode, and forgetting cannot be measured during a run until
  the retention probe is built (the next build stage, SR0). Rollback now works one generation back.
  The path: small builds (all six built and reviewed) → the retokenization fleet → SR0 (probe, best checkpoint) →
  the continue preset (chained learning sessions with a gate) → GPU tests of forgetting and
  plasticity.
- **A — universal-capable.** Kept open: media and modality work is designed (Proposals 01-03b) and
  waits behind B, as the priority says.
- **The unreliability belief.** Honoured as a hypothesis: it decides which experiments run first;
  GPU tests decide whether it holds.

## Major issues
1. **Risk being worked: the expert pool fills up before training ends.** In the 2026-09-24 fleet
   the expert pool hit its hard ceiling (4,096) in 20 of 21 runs, by about a third of the way in, on
   a simple two-area stream. After training, new material would find no free room. The manager is
   handling it with GPU tests of more headroom and of how old experts make room (register NEW-20).
   No decision needed.

## Potential expansions
(none raised yet)

## GPU tests
| # | Test | Status | What it decides |
|---|---|---|---|
| 1 | Read the 2026-09-24 fleet archive | **done** (you uploaded it; `results/gpu_world_2026-09-24/ARCHIVE_READS.md`) | data source; expert pool; culls; gradients |
| 2 | Retokenization fleet (`EXP=retok bash tools/gpu_launch.sh --go`) | **ready to relaunch**: the 2026-09-27 attempt was stopped because nothing showed it was alive. The fleet now prints a heartbeat, refuses a second launch, writes its block on any stop, and has a dashboard; the block below replaces the old one | which re-segmentation cadence ships; post-fix GPU speed; checkpoints for the first post-training test |

### Test 2: the retokenization fleet
Nothing from the 2026-09-27 attempts needs keeping, and nothing is running. On the GPU box, in the repo
checkout:
```bash
cd /workspace/LLM-Test
git fetch origin rm-predict-DC && git checkout rm-predict-DC && git pull --ff-only
EXP=retok bash tools/gpu_launch.sh --go
```
- **The launcher checks the box first.** It checks python, torch and CUDA, the card, MPS, the disk
  for the kept checkpoints (about 22 GB at 3 seeds), the branch, and whether a fleet is already
  running. Each check prints PASS, WARN or FAIL, and every FAIL comes with its fix; nothing launches
  while any check FAILs. torch 2.8.0+cu128 shows a WARN: it is below requirements.txt's floor, which
  matters only on aarch64. The fleet then runs detached, so closing the terminal or losing the
  connection does not stop it. After 20 s the launcher prints `RUNNING: pid N`, or the end of the log
  if the fleet died.
- **Watch it in a second terminal:** `bash /workspace/LLM-Test/tools/fleet_dash.sh`. Every command in
  this block names the checkout by its full path, so it works from whatever directory a new terminal
  opens in. The top line says RUNNING, STALLED, FINISHED, STOPPED (with the reason) or DEAD. Below it
  are the stage and every run (starting on CPU, training, finishing, done, failed) with its windows
  and speed, then the GPU, this container's CPU in cores, the disk, the ETA and the log's last lines.
  It redraws every 5 s; Ctrl-C closes the dashboard, not the fleet. For a browser, add `--html`: it
  writes `/workspace/LLM-Test/gpu_retok_out/dashboard.html`, which reloads itself; `--serve 8080`
  serves that page on port 8080 if your platform exposes ports. For one look from any terminal:
  `EXP=retok bash /workspace/LLM-Test/gpu_world.sh --status`.
- **In the first minutes nvidia-smi looks idle, and that is normal.** Each smoke and calibration run
  spends 15-30 s on the CPU first (python and torch, corpus, tokenizer, stream, model), longer when the
  CPU is shared: at this fleet's shape on the 4-core CPU box it took 15-16 s, one run alone or four at
  once, and 66-71 s each while another job shared that CPU. The smoke prints the figure measured on
  your box. The card reads 0% for that part of every step, while the dashboard shows the runs
  "starting on CPU" and the CPU busy. The smoke takes about half a minute to a minute and the
  calibration about 3-5 minutes; then `---- 2. fleet started` and the ETA appear. `retok_fleet.log`
  gets a heartbeat line every 30 s. Judge progress by the dashboard or `--status`, never by nvidia-smi.
- **Do not launch it again while it runs** (a second launch is refused now in any case), and do not
  `git pull` while it runs. **To stop it:** `EXP=retok bash /workspace/LLM-Test/gpu_world.sh --stop`,
  which writes its block. Please do not stop the container to stop the fleet.
- **When the dashboard says FINISHED or STOPPED, paste back** the output of
  `cat /workspace/LLM-Test/gpu_retok_out/PASTE_BACK.txt`: everything from `==== PASTE THIS BACK ====`
  to `==== END ====`. Keep the `.tgz` it packs beside `gpu_retok_out/` and upload it as before. If the
  dashboard says DEAD, paste the output of `bash /workspace/LLM-Test/tools/fleet_dash.sh --once`
  instead.
- The launch moves the earlier attempts' `gpu_retok_out` aside as `gpu_retok_out.<stamp>`. Nothing in
  those directories is needed, and they can be deleted.

## Rulings that touch your earlier rulings (no action needed)
The manager resolved the 20 decisions that were queued for you (register §3.3, Appendix D). These
are the ones that touch something you said; say so only if one is wrong.
- **Priority order.** Your ranking (B above A, flexibility serving B) is the register's order. Your
  rulings stand until you change them, and any GPU result that contradicts one comes to you.
- **"Too much" (ε).** Set provisionally at 0.05 bits/byte per area per session and 0.10 cumulative
  since release. These are the manager's numbers, not yours; give other numbers if you want them.
- **The unreliability belief.** Tested at its widest reading, including the system's own components.
  No default leans on it until the GPU reads it.
- **Trust.** Until copy detection passes on GPU, only trusted origins reach the weights: the training
  manifest plus `data/continual/01-04`. Name any origin to add or remove it.
- **Stream rebuilding (your approval).** Stays on. The cadence, every 3000 windows, is the manager's
  interim value, and the retokenization fleet may change it to 1000. Turning it off in training runs
  comes to you only if every cadence and remedy is shown to harm learning beyond the budget.
- **D8 ('planned' draw).** Stays the training default. If the GPU draw comparison favours 'replay',
  that result comes to you before anything changes. The tie-break question you were asked about
  (04 §8 Q2) is ruled conditionally yes.
- **D2 (pure-add).** Unchanged. The new post-training sessions, which did not exist when you ruled
  D2, rehearse the parent's data (provisional until the GPU test).
- **D4 (WORLD kept).** WORLD stays on in every branch. If the whole-epoch re-run shows it costs old
  areas beyond the budget, its gradient into the language model is cut first. Only a cost that
  survives that comes to you.
- **D16 (soft clamp).** Stands as written. `cap.clamp` also reads UNREACHABLE on five more grounds
  where no lift can be held at a ceiling, and every ground is printed. This is recorded as the
  manager's note, not your words.
- **"Nothing frozen".** A frozen codec stays a test control and never becomes the default by winning.
  Both language-model arms carry a context-locked position table, so no checkpoint is made B's
  long-lived parent until a context-widening route passes on GPU.
- **03b's D-1..D-10** (the live-codec design choices of 2026-09-25) carry no quote from you, so they
  are treated as design decisions that GPU readings may revise. If you took any of them yourself,
  name it and it will stand as yours.
