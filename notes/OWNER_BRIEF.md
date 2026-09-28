# Owner brief

The one page for the owner. Everything else — how decisions were made, the evidence, the exact test
rules — is in the repo for reference (`docs/proposals/05_DECISIONS.md`, `docs/04_CONTRACT.md`,
`results/`, `notes/AGENT_STATE.md`) and is not brought up here.

Updated 2026-09-28 (7d9bea1).

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
  The path: small builds (all six built and reviewed) → the retokenization fleet (done) → SR0 (probe, best
  checkpoint) → the continue preset (chained learning sessions with a gate) → GPU tests of forgetting and
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
   The 2026-09-27 fleet, on a four-phase stream and newer code, reached the ceiling in only 2 of 13
   runs (counting each fleet's repeat run, as the 20 of 21 does), and every run ended with room free;
   which of the two differences explains that is not yet known. No decision needed.

## Potential expansions
(none raised yet)

## GPU tests
| # | Test | Status | What it decides |
|---|---|---|---|
| 1 | Read the 2026-09-24 fleet archive | **done** (you uploaded it; `results/gpu_world_2026-09-24/ARCHIVE_READS.md`) | data source; expert pool; culls; gradients |
| 2 | Retokenization fleet (`EXP=retok bash tools/gpu_launch.sh --go`) | **done** 2026-09-27, 13 of 13 runs. Rebuilding every 1000 windows now ships: better than every 3000, and within budget against no rebuilding. Provisional until SR0's held-out check, which must watch older text rebuilt late in a run (`results/gpu_retok_2026-09-27/RESULTS.md`) | which re-segmentation cadence ships; post-fix GPU speed; checkpoints for the first post-training test |
| 3 | Cooldown fleet (below) | **ready** | whether the 400-window pause of the pool's growth requests costs learning at the shipped cadence (a measured cost; the pause stays); 1000 against no rebuilding, re-read at 5 seeds |

### Test 3: the cooldown fleet (about 20-25 minutes)
After each stream rebuild, the expert pool's growth requests (the route to about 1% of new experts)
pause for 400 windows; spawning, which adds the rest, carries on. The same setting also keeps growth
steps 400 windows apart. With a rebuild every 1000 windows, the pauses after rebuilds cover 38% of
the run, past the 20% alarm. This fleet runs the shipped cadence beside the same cadence with the pause
cut to 100 windows, at 5 seeds, and reads whether the pause costs learning. It also re-reads 1000
against no rebuilding at 5 seeds; if 1000 is shown to harm learning there, it stops shipping and every
3000 windows and the other remedies are tested next (nothing comes to you unless they fail too). It
keeps no checkpoints: your 2026-09-27 tars hold what the next tests need.
On the GPU box, in the repo checkout:
```bash
cd /workspace/LLM-Test
git fetch origin rm-predict-DC && git checkout rm-predict-DC && git pull --ff-only
EXP=retok RETOK_ARMS="1000" COOLDOWN_ARM=100 SEEDS="0 1 2 3 4" KEEP_CKPT=0 bash tools/gpu_launch.sh --go
```
- The launcher checks the box, launches the fleet detached and prints `RUNNING: pid N` after 20 s.
  Watch it with `bash /workspace/LLM-Test/tools/fleet_dash.sh`. Stop it with
  `EXP=retok bash /workspace/LLM-Test/gpu_world.sh --stop`, which writes its block. Do not launch it
  again or `git pull` while it runs. For its first minutes the card reads idle while each run builds
  on the CPU; judge it by the dashboard, not by nvidia-smi.
- **Time:** 21 runs. On a box like the 2026-09-27 one (13 cores, 12 runs at a time) that is two
  waves. At that fleet's rates, smoke and calibration take about 3 minutes and each run 7-10 minutes,
  so about 20-25 minutes in all. The ETA line prices the runs as if every slot stayed busy, so it
  reads short. If the block prints a LOW-GPU-WORLD-ETA line, its CAL_WINDOWS advice does not apply.
- **When the dashboard says FINISHED or STOPPED, paste back** the output of
  `cat /workspace/LLM-Test/gpu_retok_out/PASTE_BACK.txt`, everything from `==== PASTE THIS BACK ====`
  to `==== END ====`, and upload the `.tgz` it packs beside `gpu_retok_out/`, as before. If the
  dashboard says DEAD, paste the output of `bash /workspace/LLM-Test/tools/fleet_dash.sh --once`
  instead.
- An earlier `gpu_retok_out` is moved aside as `gpu_retok_out.<stamp>`. Nothing in it is needed.

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
- **Stream rebuilding (your approval).** Stays on. The retokenization fleet moved its cadence, the
  manager's value, from every 3000 windows to every 1000 (provisional until the held-out check after
  SR0). Turning it off in training runs comes to you only if every cadence and remedy is shown to harm
  learning beyond the budget.
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
