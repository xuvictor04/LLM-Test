# Operations — how the work actually gets done

Not a design document. This is the operating manual: whose machine runs what, what each side can and
cannot do, how results move between us, and what I have assumed about your operation and got wrong.

Sourced from the full chat record (2026-07-21 .. 2026-08-29, 78 environment-related records extracted
across all four spans) plus checks I ran directly. Every line is marked VERIFIED, RECORDED or UNKNOWN.
Nothing here is written from recollection.

---

## 1. Your machine

**VERIFIED — it is a rented box that is re-provisioned between rounds.** Fifteen distinct addresses appear
across the record:

```
192-222-50-5    192-222-50-114  192-222-50-188  192-222-51-110  192-222-51-135
192-222-52-116  192-222-53-46   192-222-53-218  192-222-54-145  192-222-54-220
192-222-55-36   192-222-56-84   192-222-57-12   192-222-58-77   192-222-58-178
```

This is the most consequential operating fact in this document and I only learned it from the survey.
It means: **nothing on that box is durable.** Anything that must survive is committed and pushed, or it is
gone at the next round. It also bears on whether long unattended runs are safe (see UNKNOWN below).

| | |
|---|---|
| user / path | VERIFIED `ubuntu@…:~/LLM-Test` — repo at `/home/ubuntu/LLM-Test` |
| OS | VERIFIED Ubuntu |
| GPU | VERIFIED present and used; `preflight.sh` returns `PREFLIGHT OK -- safe to launch` |
| cores | VERIFIED 8 — `PASS OMP_NUM_THREADS=8 on 8 cores` |
| device selection | VERIFIED **not** automatic. You began prefixing `DEVICE=cuda` from round11 onward |
| Hugging Face | VERIFIED account + token in env; `bigcode/the-stack-dedup` terms accepted 2026-08-28 |
| `datasets` | VERIFIED importable in the run interpreter (the gated-repo error is downstream of that import) |
| exact GPU / arch | **UNKNOWN** — see §5 |

### Measured throughput, for planning

RECORDED from your own pastes — treat as signals, not constants, since corpus and geometry both move:

| run | steps | wall clock |
|---|---|---|
| 0.75 GB, `lr_075`, `STREAM_LEN=94000000 EPOCHS=8` | ~1,051,405 | **8.4 h** on cuda |
| round18 grid arm, `STREAM_LEN=4000000 EPOCHS=4` | — | ~950 s per arm |
| pilot (`STREAM_LEN=4000000 EPOCHS=8`) | ~15,625 | ~15-20 min |
| smoke bench | 312 | 0.27 min (1163 steps/min, 1.6M params, 0.35 GiB peak) |

I have been wrong about throughput repeatedly — quoting ~1.6 GB/day, then 0.8-1.1 GB/day, against a
measured 2.24 GB/day at population 3000. **Do not let me estimate run times; measure them.**

## 2. My container

| | |
|---|---|
| path | `/home/user/LLM-Test` — a *different* checkout from yours |
| GPU | VERIFIED **none**. `nvidia-smi` missing, `torch.cuda.is_available()` False |
| cores | VERIFIED 4, 15 GiB RAM, x86_64 |
| workflow concurrency | VERIFIED capped at 2 (min(16, cores−2)) — 20-agent fan-outs take hours here |
| torch | VERIFIED present now (2.13.0+cu130, CPU-only). **RECORDED: it has vanished on a container rebuild before**, leaving tests unrunnable |
| pypi.org | VERIFIED reachable, 200 |
| **huggingface.co** | VERIFIED **UNREACHABLE** (connection fails through the agent proxy) |
| github.com | VERIFIED reachable via the GitHub MCP tools and git push |
| durability | VERIFIED none. Ephemeral, reclaimed after inactivity |

**What this means in practice.** I can verify mechanism, instruments and invariants on CPU — the full
`selftest` takes 8-12 minutes here. I cannot measure scale, speed, or anything needing a GPU, and I cannot
fetch a corpus from Hugging Face. Every number that matters comes from your box.

## 3. The working agreement

RECORDED across the whole span, and consistent throughout:

- **I write one copy-pasteable command; you run it; you paste the terminal output and attach the `.log`.**
  Uploaded logs reach me at `/root/.claude/uploads/…`. 37 real logs moved this way in one span alone.
- I never touch your machine.
- **`runs/` and its contents are never overwritten.** Standing, and I violated it once — see §4.
- Confirm before acting on performance changes.
- No compromises: do not remove or downgrade functionality for speed.
- Default to bash unless python is specified.
- Commit and push to the working branch only. **Currently `rm-predict-DC`; `rm-predict` is frozen (D5).**
- Never put a model identifier in a commit, PR, code comment or any pushed artifact.
- **Tell you the full on/off default state before committing GPU hours** — your words, twice: *"tell me the
  defaults, so I know what is off and on."*
- Results are signals, not facts. The only definitives are the two goals.

### Gotcha worth restating

`export VAR=value` **prints nothing on success.** You flagged this — *"The export does not say anything."*
It is silent by design; `echo $OMP_NUM_THREADS` confirms it took.

## 4. What I assumed about your operation and got wrong

The record. Each is a real correction, most of them yours.

1. **I let you believe test runs were on GPU.** Your words: *"I thought I was running them on GPU."* They
   were CPU-only in my container and I had not said so. The single worst operational miscommunication here.
2. **I overwrote a file inside `runs/`** — the one directory you told me never to overwrite. A resume wrote
   its grown vocabulary over its parent's `.dyntok.json`, making `runs/long/pilot_gru` unloadable. Fixed in
   `aee4a52`; exactly recoverable because minting is append-only.
3. **I assumed Hugging Face gated datasets blocked you too**, and built `fetch_local.py` as the unblock.
   You corrected me: *"I can use HF on my system."* HF is blocked for **me**, not for you.
4. **I assumed ultracode was off** and said I would work directly. You corrected it in the next message.
5. **I told you per-expert memory was already on.** It was not — `MEM_PER_EXPERT` defaults to 0.
6. **I claimed the `GROW_CAP` soft-cap mechanism did not exist and had to be built.** You remembered
   correctly that it did.
7. **My documented prep command was wrong** — `PILOT_DIR=… PILOT_GB=… bash longrun.sh fetch` fetches into
   `$DATA_DIR` at `$ENG_GB`, not into `$PILOT_DIR` at `$PILOT_GB`.
8. **I estimated "roughly 20 min/arm"** against actual 8-34 min, and got throughput wrong three times.
9. **I assumed the corpus fetch appears in the run log.** It does not — the fetch happens outside the
   `tee`, so when you paste a log I cannot see whether a fetch ran or was skipped.
10. **I handed you a command whose size did not match your corpus** (`pilot-add py local 0.03` against
    0.06 GB of English) because the harness's own closing hint said so, and I passed it on unchecked.
11. **I read a routing collapse off a single-window measurement** and reported it as a fact about the
    population. The line could not have said anything else.
12. **I called your box a GH200 for weeks on no evidence** — see §5.

## 5. Still UNKNOWN — five commands would close it

`preflight.sh`'s entire advice section is written for an aarch64 GH200 and is wrong if the box is not one.
I have never seen `uname -m` or `nvidia-smi` from it, only `PREFLIGHT OK` and `8 cores`.

```bash
uname -a && nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
free -g | head -2 && df -h ~ | tail -1
python3 -c "import sys,torch;print(sys.executable, torch.__version__, torch.version.cuda)"
```

- **Which python environment** — system, venv, conda? `preflight` warns that upgrading numpy under an NGC
  torch breaks its ABI, so this decides how the fetch tooling is packaged.
- **Can a run be left unattended for hours or days**, or does the box get reclaimed? Given the fifteen
  addresses, I suspect not — which would make short checkpointed runs the right unit of work, and would
  change the harness design at P7.

---

*Everything above is checkable. If a line is wrong, it is wrong against a specific piece of evidence and
should be corrected here rather than remembered differently.*
