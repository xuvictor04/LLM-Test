# LAUNCH — full package testing on a fresh GPU instance

Everything runs through `control.py`. This is the copy-paste path from a bare instance to the phased
experiments in `EXPERIMENTS.md`.

## FULLY AUTOMATED — one command runs the entire plan unattended
```
scp -i C:\Users\victo\Downloads\Laptop.pem overarching-package.zip ubuntu@<IP>:~
ssh -i C:\Users\victo\Downloads\Laptop.pem ubuntu@<IP>
sudo apt-get update -qq && sudo apt-get install -y unzip tmux
unzip -o overarching-package.zip && cd overarching-package
tmux new -s full 'python3 control.py fulltest'
```
That single command does everything: **pre-flight -> data fetch -> baseline (Rung 0) -> single-axis groups
(Rung 1: train/eco/robust/arch) -> within-group sweeps (Rung 2: training + eco) -> one aggregated report.**
Each phase is fault-isolated (an OOM in one arm is logged and the run continues). On one H100 the default
(`STEPS=30000`, `SWEEP_STEPS=8000`) is roughly a **half-day**.
- Watch:   `tail -f ~/fulltest.log`   or   `watch -n 15 python3 greg_status.py ~/fulltest.log`
- Results: land in **`~/fulltest_results.txt`** when it finishes.
- Faster pass: `STEPS=12000 SWEEP_STEPS=4000 tmux new -s full 'python3 control.py fulltest'`
- Get pinged on each phase: set an ntfy webhook -> `NOTIFY_URL=https://ntfy.sh/yourtopic python3 control.py fulltest`

The manual, step-by-step path below does the same thing by hand if you want to run phases on separate instances.

---

## AUTOMATIC — one command, unattended (recommended)
After step 0 (below), the entire test runs itself:
```
tmux new -s fulltest 'python3 control.py autotest'
```
This does everything in order: pre-flight (aborts if broken) -> data fetch -> probe batch once -> baseline +
the 4 single-axis groups at matched compute -> a ranked OOD table in `~/fulltest_results.txt`. ~10-20h on one
H100 at the default `STEPS=20000`. Watch: `watch -n 30 tail -20 ~/fulltest.log` (or `cat ~/fulltest_results.txt`).

Scope via env:  `RUNGS=01` (baseline+groups, default) | `RUNGS=012c` (+within-group sweeps +continual) |
`STEPS=8000` (faster first pass) | `NOTIFY_URL=<ntfy/webhook>` (progress pings).

The manual, rung-by-rung path below gives finer control if you'd rather drive it yourself.

---
## 0. Get onto the instance
```
scp -i C:\Users\victo\Downloads\Laptop.pem overarching-package.zip ubuntu@<IP>:~
ssh -i C:\Users\victo\Downloads\Laptop.pem ubuntu@<IP>
sudo apt-get update -qq && sudo apt-get install -y unzip tmux
unzip -o overarching-package.zip && cd overarching-package
```

## 1. PRE-FLIGHT (do this first — it's ~2 min and saves GPU hours)
```
python3 control.py check
```
Must print `READY`. If any check FAILs, stop and fix before spending GPU time.

## 2. Data (fetches enwik9 + web/code/reddit + books; several minutes)
```
python3 control.py setup
```
Confirm `enwik9 OK (~1000 MB)`, per-source sizes, and no `!! WARNING`. `data/continual/` ships populated.

## 3. The phased test (each in its own tmux session; watch with greg_status.py)
Follow `EXPERIMENTS.md`. Minimum viable path:
```
# Rung 0 -- baseline (the number everything is compared to)
STEPS=30000 tmux new -s base 'python3 control.py train --preset base'

# Rung 1 -- single-axis groups (each vs baseline), one at a time or on separate instances
STEPS=30000 tmux new -s tr   'python3 control.py train --preset train'
STEPS=30000 tmux new -s eco  'python3 control.py train --preset eco'
STEPS=30000 tmux new -s rob  'python3 control.py train --preset robust'
STEPS=30000 tmux new -s arch 'python3 control.py train --preset arch'

# Rung 2 -- within-group sweeps (only for groups that beat baseline)
STEPS=8000 tmux new -s tsw 'python3 control.py sweep training'
STEPS=8000 tmux new -s esw 'python3 control.py sweep eco'
```
Watch any run:  `watch -n 15 python3 greg_status.py ~/<log>.log`  (logs: barry_scale.log / eco.log / tsw.log).

## 4. Read results
```
python3 read_results.py <run_dirs...>      # OOD bits/byte per run
```
A lever counts only if it beats baseline by more than run-to-run noise (see EXPERIMENTS.md "reading rules").

## 5. Winner at scale
Take the best justified config (from Rungs 1-3) to a long run:
```
STEPS=50000 tmux new -s win 'python3 control.py sweep scale <winning KNOB=val ...>'
python3 control.py chat best.pt <same arch knobs>     # inspect its completions
```

## Other modes (any time)
```
python3 control.py continual                 # continual learning + backward-transfer (data/continual/ ready)
python3 control.py test correct,compress,robust,fuzzy,modeling   # tokenizer aspects
python3 control.py test components           # component correctness tests
python3 control.py sweep greg                # Greg dense diagnostic
```

## Notes
- `--preset full` is a STRESS test (does everything-on stay stable), not evidence any single lever helps.
- The `arch` group adds VMAX-sized tables (compose atoms + heads) -- watch memory; `COMPOSE_REFRESH=8` keeps it affordable.
- Every preset composes with `KNOB=val` overrides on the same line (overrides win).
