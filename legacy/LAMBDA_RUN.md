# Lambda run — turnkey

Front-loaded: `run_lambda.sh` does the **big full-stack run first** (`big_full`) and prints results
before anything else, so you get the headline number while you're watching. Then continual (the bet),
then tokenizer (incl. byte = prior-test comparison), then the architecture ablations.

Base params match the prior Lambda test for comparability: `D384 / L6 / H6 / CTX256 / LR6e-4 / MEMCAP65536`.

---

## 0. Launch the instance
Lambda Cloud console → launch a capable GPU. **80 GB (A100/H100) recommended** — grow-only growth +
re-encode is memory-hungry, and more memory = more growth. It still runs on smaller cards: the probe is
NMAX-adaptive and will hold the largest population that fits. Note the instance **IP**.

## 1. Upload (laptop)
```
scp -i C:\Users\victo\Downloads\Laptop.pem overarching-package.zip ubuntu@<IP>:~
```

## 2. SSH in + one-time setup (instance)
```
ssh -i C:\Users\victo\Downloads\Laptop.pem ubuntu@<IP>
sudo apt-get update -qq && sudo apt-get install -y unzip tmux
unzip -o overarching-package.zip
cd overarching-package
bash setup_lambda.sh
```
`setup_lambda.sh` verifies torch+CUDA (installs the CUDA wheel only if missing) and prints the GPU + VRAM.

## 3. Run (instance, inside tmux so it survives disconnect)
```
tmux new -s greg
bash run_lambda.sh
```
Detach with **Ctrl+b** then **d**. Re-attach later with `tmux attach -t greg`.
**Never `exit` the tmux window** — that kills the run. Detach instead.

## 4. Monitor (instance)
```
tail -f ~/lambda.log
```
GPU/VRAM is also visible in the **Lambda Cloud console dashboard** (the Guest Agent installed by
`setup_lambda.sh` streams it there within a few minutes) — handy for watching memory headroom while the
population grows, with no CLI. Two things to check at the start:
- **`PROBING` lines** — which `NMAX/batch` it settles on. If it lands on `NMAX=16` and you wanted more
  growth, stop and rerun with `ENABLE_REENCODE=0 bash run_lambda.sh` (frees memory → higher NMAX).
- **First `big_full` eval** — `mem-conf {...}` should be **nonzero** (memory is writing) and `in-held`
  should be **descending**. If `mem-conf` is all 0.0, stop and tell me.

## 5. Retrieve results
On the instance, bundle the small logs (the checkpoints are multi-GB — skip unless you want one for chat):
```
cd ~/overarching-package
tar czf ~/results.tgz lambda.log */*_log.jsonl 2>/dev/null
```
On the laptop:
```
scp -i C:\Users\victo\Downloads\Laptop.pem ubuntu@<IP>:~/results.tgz .
scp -i C:\Users\victo\Downloads\Laptop.pem ubuntu@<IP>:~/lambda.log .     # decision tables are in here
```
`lambda.log` already contains the `read_results.py` tables (BWT per arm, bits/byte per run). The `.jsonl`
files are the per-eval detail if you want to plot curves.

(Optional — keep the trained model for `chat.py`:)
```
scp -i C:\Users\victo\Downloads\Laptop.pem ubuntu@<IP>:~/overarching-package/big_full/ckpt.pt .
```

## 6. Stop billing
**Terminate the instance in the Lambda web console.** Closing SSH does NOT stop billing.

---

## Phases (you can Ctrl+C after any phase — results print after A and B)
- **A — `big_full`**: full Greg at prior scale (dynamic tokenizer + MoE embedders + mirror + counterparts + grow-only). *Watch this.*
- **B — continual**: `cont_off / cont_mir / cont_rep` → backward transfer (negative = no forgetting = the bet pays).
- **C — tokenizer**: `v1_frz` (frozen 8192) + `v1_byte` (**byte-level = direct prior-test comparison**).
- **D — ablations** (matched steps, vs `big_full`): `abl_noembed` (M_EMBED=0), `abl_nocp` (counterparts off), `abl_noreenc` (re-encode off).

Budget: nine D384 runs with re-encode + grow-only is a long night (~12 h+). A and B are the priority and
each prints `read_results.py` when done — Ctrl+C after B still leaves you the headline numbers.

## Knobs to change before launching (edit the top of run_lambda.sh)
- `ENABLE_REENCODE=0` in `BASE` → faster, bigger batch, higher NMAX (re-encode rarely helps; on = prior-comparable).
- `STEPS=5000` → fixed step count per run (raise for closer-to-one-epoch).
- Probe `NMAX` ladder `48 32 24 16` → raise the top if you have an 80 GB+ card and want more growth.
