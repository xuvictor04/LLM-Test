# Owner brief

The one page for the owner. Everything else — how decisions were made, the evidence, the exact test
rules — is in the repo for reference (`docs/proposals/05_DECISIONS.md`, `docs/04_CONTRACT.md`,
`results/`, `notes/AGENT_STATE.md`) and is not brought up here.

Updated 2026-10-03 (test 4, the held-out re-read of rebuilding, is ready; test 5, the first learning sessions
after training, and test 6, the same re-read on real text, follow it: their blocks are under GPU tests).

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
  the tree has no post-training learning mode, and the retention probe that measures forgetting
  during a run is built (SR0, below) but has not yet been read on GPU. Rollback now works one
  generation back.
  The path: small builds (all six built and reviewed) → the retokenization fleet (done) → SR0 (probe, best
  checkpoint; built) → the continue preset (chained learning sessions with a gate) → GPU tests of forgetting and
  plasticity.
- **Stage 3 (SR0) is done: built, reviewed and merged on 2026-09-29.** Runs now measure forgetting as they train.
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
2. **Risk being worked: rebuilding leaves older text worse by the end of a run.** Read text area by
   area (not the fleets' deciding reading): rebuilding every 1000 windows helps newly arriving text,
   but it leaves the older numeric text about 0.1 bits/byte worse than no rebuilding by the end of the
   run. That is about twice the budget, at every seed on both cards, and rebuilding every 3000 windows
   was worse there. SR0's held-out check decides it (test 4, ready), with the first fix aimed at that
   text tested beside it.
   No decision is needed: rebuilding stays on, and turning it off in training runs comes to you only if
   every cadence and fix fails (O14, unchanged).

## Potential expansions
(none raised yet)

## GPU tests
| # | Test | Status | What it decides |
|---|---|---|---|
| 1 | Read the 2026-09-24 fleet archive | **done** (you uploaded it; `results/gpu_world_2026-09-24/ARCHIVE_READS.md`) | data source; expert pool; culls; gradients |
| 2 | Retokenization fleet (`EXP=retok bash tools/gpu_launch.sh --go`) | **done** 2026-09-27, 13 of 13 runs. Rebuilding every 1000 windows now ships: better than every 3000, and within budget against no rebuilding phase by phase (area by area, see Major issues 2). Provisional until SR0's held-out check, which must watch older text rebuilt late in a run (`results/gpu_retok_2026-09-27/RESULTS.md`) | which re-segmentation cadence ships; post-fix GPU speed; checkpoints for the first post-training test |
| 3 | Cooldown fleet | **done** 2026-09-28, 21 of 21 runs on an H100. Rebuilding every 1000 windows stays. The 400-window pause of the pool's growth requests stays; it stays by rule, whatever this test read. Cutting it to 100 showed no measurable cost to learning: growth requests rose, the pause covered 10% of the run instead of 38%, and bits/byte did not move. One baseline run started learning late; it decides nothing (`results/gpu_retok_2026-09-28/RESULTS.md`) | whether the 400-window pause of the pool's growth requests costs learning at the shipped cadence (a measured cost; the pause stays); 1000 against no rebuilding, re-read at 5 seeds |
| 4 | Held-out re-read of rebuilding (below) | **ready** 2026-10-02 (register §8 6.3a) | whether rebuilding every 1000 windows keeps each older area's held-out text within budget (Major issue 2), and if not, whether the first fix aimed at it ships |
| 5 | The first learning sessions after training (below) | **ready** 2026-10-02 (register §8 5.3a); run it after test 4: it starts from test 4's kept checkpoints | whether a model learning a new area after training keeps each older area within budget, learning the new area alone and with its old text rehearsed; how noisy one session's reading is, which sizes the future gate; more expert room after training (described) |
| 6 | Held-out re-read of rebuilding on real text, with the draw comparison (below) | **ready** 2026-10-03 (register §8 6.3b); run it after test 4's blocks, before or after test 5 | whether rebuilding keeps each older area within budget on real text, where a new area's merged tokens can re-cut older text; whether rehearsing faded areas in training ('replay') beats the default draw (if it does, that comes to you); what the source-reliability book costs; the first real-text checkpoints |

### Test 4: the held-out re-read of rebuilding (about 25-30 minutes)
Rebuilding every 1000 windows ships, but read area by area it may leave older numeric text worse than
no rebuilding (Major issue 2). This fleet reads every area on held-out text at the end of a run,
against no rebuilding, and beside it the first fix aimed at that text: new tokens minted for the text
that is new rather than for text already learned (`TOK_MINT_NOVEL` 1.0).
On the GPU box, from any provider (`R` is the checkout's path; set it to yours):
```bash
R=/workspace/LLM-Test
# on a new box, first: git clone https://github.com/xuvictor04/LLM-Test "$R"
cd "$R" && git fetch origin rm-predict-DC && git checkout rm-predict-DC && git pull --ff-only
EXP=heldout SEEDS='0 1 2 3 4 5 6' FILL=0 bash "$R/tools/gpu_launch.sh" --go
```
- The launcher checks the box and prints each FAIL with its fix (a CUDA build of torch, the card, about
  20 GB of free disk for the kept checkpoints, about 22 GB if a top-up follows: it budgets 12 GB more
  while `gpu_heldout_out/ckpt/` stays). It launches the fleet detached and prints
  `RUNNING: pid N`. Watch it with `bash "$R/tools/fleet_dash.sh"`; stop it with
  `EXP=heldout bash "$R/gpu_world.sh" --stop`, which writes its block. For its first minutes the card
  reads idle while the runs build on the CPU. Do not launch it again, and do not `git pull` until this
  test's blocks are pasted back: a top-up is read with this fleet only at the same commit.
- **Time:** 22 runs. On the H100 PCIe box (26 cores) they run as one wave, about 30 minutes from launch
  to block. On the H200 box (13 cores), two waves, about 25 minutes.
- **When the dashboard says FINISHED or STOPPED, paste back** `cat "$R/gpu_heldout_out/PASTE_BACK.txt"`,
  from `==== PASTE THIS BACK ====` to `==== END ====`, and upload the `.tgz` its `archive:` line names,
  beside `gpu_heldout_out/`. If the dashboard says DEAD, paste `bash "$R/tools/fleet_dash.sh" --once`
  instead.
- **If the block's DECISION says UNRESOLVED,** the line under it is a `top-up:` command that adds seeds
  up to 11. Run the command after `top-up:` on the same box (it is read with this fleet only on the same
  card and torch); it takes about 20 minutes. Then paste back
  `cat "$R/gpu_heldout_topup_out/PASTE_BACK.txt"` and upload its `.tgz`.
- **Keep `gpu_heldout_out/ckpt/` on the box:** the next test starts from its finals. If the box will be
  given up, run the command after `pack:` in `gpu_heldout_out`'s block (a top-up's block has none) and
  download the `_finals.tar` it writes (about 2.1 GB).

### Test 5: the first learning sessions after training (about 10-35 minutes)
Each model test 4 kept learns a new, fifth area for 5,000 windows: once alone and once with its old text
rehearsed. A third copy differs only by one part in ten thousand in its learning rate, to measure the
noise, and the model with the most experts runs once more with room to grow. It reads whether each older
area stays within budget, and which of the two ways to learn to keep. Run it after test 4's blocks (its
top-up's too) are pasted back, from any provider (`R` is the checkout's path; set it to yours):
```bash
R=/workspace/LLM-Test
# on a new box, first: git clone https://github.com/xuvictor04/LLM-Test "$R"
# and unpack test 4's finals: mkdir -p "$R/gpu_heldout_out" && tar -xf <test 4's _finals.tar> -C "$R/gpu_heldout_out"
cd "$R" && git fetch origin rm-predict-DC && git checkout rm-predict-DC && git pull --ff-only
EXP=session SEEDS='0 1 2 3 4 5 6' FILL=0 PARENTS="$R/gpu_heldout_out" bash "$R/tools/gpu_launch.sh" --go
```
- If test 4's DECISION shipped `TOK_MINT_NOVEL` 1.0, put `PARENT_ARM=k1000_mn` before `bash`.
- The launcher checks test 4's kept models against their `FINALS.sha256` before anything starts. Without
  them (`PARENTS` left out) the fleet trains the seven models again first. It also checks the disk: the
  sessions' kept checkpoints need about 20 GB beside test 4's (`KEEP_CKPT=0` keeps none).
- **Time:** 22 sessions. On the H100 PCIe box they run as one wave, about 15-20 minutes from launch to
  block; about 30-35 without `PARENTS`. On the H200 box, two waves, about 10-15 minutes; about 20-25
  without `PARENTS`.
- Watch, stop and paste back as for test 4, with `session` for `heldout`: `bash "$R/tools/fleet_dash.sh"`,
  `EXP=session bash "$R/gpu_world.sh" --stop`, and when it says FINISHED or STOPPED,
  `cat "$R/gpu_session_out/PASTE_BACK.txt"`. Upload the `.tgz` its `archive:` line names.
- **If its DECISION says UNRESOLVED,** run the command after `top-up:` on the same box, before any `git pull`
  (it is read with this fleet only at the same commit). It trains four more models, then their sessions
  (about 25-35 minutes). Paste back `cat "$R/gpu_session_topup_out/PASTE_BACK.txt"` and upload its `.tgz`.

### Test 6: the held-out re-read on real text, with the draw comparison (about 20-30 minutes)
Test 4 reads rebuilding on generated text, whose areas share no letters; on real text a new area's merged tokens can
re-cut older text. This fleet reads each older area on held-out real text against no rebuilding, and beside it the
two ways a run can draw its text: the default, and with faded areas rehearsed ('replay'). It also times the
source-reliability book and keeps the first real-text checkpoints. Run it after test 4's blocks are pasted back, before
or after test 5 (not at the same time), from any provider (`R` is the checkout's path; set it to yours):
```bash
R=/workspace/LLM-Test
# on a new box, first: git clone https://github.com/xuvictor04/LLM-Test "$R"
cd "$R" && git fetch origin rm-predict-DC && git checkout rm-predict-DC && git pull --ff-only
EXP=heldout HELDOUT_SOURCE=real SEEDS='0 1 2 3 4 5 6' FILL=0 bash "$R/tools/gpu_launch.sh" --go
```
- If test 4's DECISION shipped `TOK_MINT_NOVEL` 1.0, put `SHIP_ARM=k1000_mn` before `bash`.
- It writes to `gpu_heldout_real_out/` and leaves test 4's `gpu_heldout_out/` alone. It needs about 20 GB of free disk,
  about 22 GB if a top-up follows (it budgets 12 GB more while `gpu_heldout_real_out/ckpt/` stays).
- **Time:** 22 runs. On the H100 PCIe box they run as one wave, about 25-30 minutes from launch to block. On the H200
  box, two waves, about 20-25 minutes.
- Watch, stop and paste back as for test 4, with `HELDOUT_SOURCE=real` after `EXP=heldout`: `bash "$R/tools/fleet_dash.sh"`,
  `EXP=heldout HELDOUT_SOURCE=real bash "$R/gpu_world.sh" --stop`, and when it says FINISHED or STOPPED,
  `cat "$R/gpu_heldout_real_out/PASTE_BACK.txt"`. Upload the `.tgz` its `archive:` line names.
- **If its first DECISION says UNRESOLVED,** run the command after `top-up:` on the same box, before any `git pull`
  (about 20 minutes). Then paste back `cat "$R/gpu_heldout_real_topup_out/PASTE_BACK.txt"` and upload its `.tgz`.
- **If either block's draw DECISION reads "'replay' at 0.27 is CONFIRMed",** rehearsing faded areas beat the default
  draw: that comes to you (your D8), and the default stays until you answer. A CONFIRM in either block stands.
- **Keep `gpu_heldout_real_out/ckpt/` on the box,** or run the command after `pack:` in its block and download the
  `_finals.tar` it writes (about 1 GB): the first continuation onto new real text starts from them.

Moved on 2026-09-28/29, if you run them from memory: the run.py sweeps are now `bash tools/sweep_gpu.sh`
and `bash tools/sweep_world.sh`, and the old tree's commands start with `cd archive/old-tree`; the fleet
commands are unchanged.

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
  long-lived parent until a context-widening route passes on GPU. Built 2026-09-28, all off by
  default: the alternative position schemes and the context widening those GPU tests will compare,
  and the refusal itself, which says so by name when anyone tries to designate a parent. Nothing is
  designated; training runs are unchanged.
- **03b's D-1..D-10** (the live-codec design choices of 2026-09-25) carry no quote from you, so they
  are treated as design decisions that GPU readings may revise. If you took any of them yourself,
  name it and it will stand as yours.
