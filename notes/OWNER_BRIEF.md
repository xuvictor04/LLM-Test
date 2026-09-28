# Owner brief

The one page for the owner. Everything else — how decisions were made, the evidence, the exact test
rules — is in the repo for reference (`docs/proposals/05_DECISIONS.md`, `docs/04_CONTRACT.md`,
`results/`, `notes/AGENT_STATE.md`) and is not brought up here.

Updated 2026-09-27 (e8628e4).

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
| 2 | Retokenization fleet (`EXP=retok bash gpu_world.sh`) | **paused**: the 2026-09-27 attempt was stopped (the GPU showed no activity and nothing reported progress). A dashboard, heartbeat lines and a checked one-command launcher are being built; a new block replaces the one below when they land | which re-segmentation cadence ships; post-fix GPU speed; checkpoints for the first post-training test |

### Test 2: the retokenization fleet (superseded block, kept for the record; do not use)
On the GPU box, in the repo checkout. It runs in the background, so a dropped connection does not
stop it.
```bash
git fetch origin rm-predict-DC && git checkout rm-predict-DC && git pull --ff-only
nohup env EXP=retok bash gpu_world.sh > retok_fleet.log 2>&1 &
```
- Progress and time left, any time: `EXP=retok bash gpu_world.sh --status`
- When it ends, paste back: `cat gpu_retok_out/PASTE_BACK.txt` (everything from `==== PASTE THIS
  BACK ====` to `==== END ====`). Keep the `.tgz` it packs beside `gpu_retok_out/` and upload it here
  as you did the last one.
- The script sizes itself to the card: it smoke-tests every arm, calibrates for 600 windows, prints
  its ETA, and stops early with a message if the disk is too small for the kept checkpoints.

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
  long-lived parent until a context-widening route passes on GPU. Built 2026-09-28, all off by
  default: the alternative position schemes and the context widening those GPU tests will compare,
  and the refusal itself, which says so by name when anyone tries to designate a parent. Nothing is
  designated; training runs are unchanged.
- **03b's D-1..D-10** (the live-codec design choices of 2026-09-25) carry no quote from you, so they
  are treated as design decisions that GPU readings may revise. If you took any of them yourself,
  name it and it will stand as yours.
