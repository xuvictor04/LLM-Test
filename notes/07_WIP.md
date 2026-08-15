# 07 — WIP: unfinished, known-broken, inert, never run

> Nothing in this project has been optimised. Strategy is still being built. Sample sizes are tiny
> — usually n=1, occasionally n=3 — and the measured seed spread on a single arm has reached
> 1.227 b/B (`33a9299`), larger than the gap between any two architectures ever compared here.
> Several confidently-stated findings were later retracted when the measurement turned out to be
> broken. Every entry records **what was observed under these conditions**, never **what is true**.
> Where a result was later invalidated, the invalidation is stated next to it, not in a footnote.

**Written against `eecb277` (2026-08-15), branch `rm-predict`.** Every status line below was
re-derived from the source, the filesystem or `git` at that commit. Where this file disagrees with
`05_ERRORS.md`, `03_EXPERIMENTS.md` or `DOC_PLAN.md`, the disagreement is stated and the
re-verification is shown — those files are cited by id, not re-derived.

---

## THE THREE CATEGORIES, AND WHY THEY ARE KEPT APART

They need different actions and different amounts of GPU time. Conflating them is how this project
came to describe `TOK_ANCHOR` as a contributing loss term for its entire life (`fec2285`).

| Category | Meaning | The action it needs |
|---|---|---|
| **NEVER BUILT** | designed, argued, written down; no code exists | a build decision, then a build. Costs engineering, not GPU. §10, §11 |
| **BUILT BUT NEVER RUN** | code exists, is imported, may even be costed every step — but no run has ever exercised it, or none at a scale that could say anything | a run. Costs GPU, not engineering. The cheapest information in the project. §3, §4, §6, §7 |
| **BUILT, RUN, AND BROKEN** | it executed, it produced a number, and the number or the mechanism is wrong | a fix, and then a re-run of everything downstream. §2, §5 |

A fourth state recurs often enough here to name: **BUILT, RUN, AND UNREAD** — the code executed and
printed its verdict into hundreds of logs that nobody aggregated. The world model (§9.1) is the
worked example.

---

## 1. UNCOMMITTED AT HEAD — none. Record only; nothing was committed by this pass.

`DOC_PLAN.md` §7 required a re-check of `git diff` because two changes were sitting in the working
tree when the plan was written: `FAB_LR_BOOST` in `self_organize.py` and `_stopped`/STOP-file
support in `longrun.sh`. **Both have since landed. The tree is clean.**

Fresh, at `eecb277`:

```
$ git status --porcelain            # (empty)
$ git status --porcelain -uall      # (empty)
$ git diff --stat                   # (empty)
$ git diff --cached --stat          # (empty)
$ git stash list                    # (empty)
$ git status -sb
## rm-predict...origin/rm-predict   # no ahead/behind marker: in sync with origin
```

**Nothing uncommitted, nothing untracked, nothing stashed, nothing unpushed.** This closes
`DOC_PLAN.md` "know NOW" item 3 and satisfies the standing mitigation for `E9.30` (§2.7).

Where the two items went:

| Item | Landed in | State at HEAD |
|---|---|---|
| `_stopped` / STOP-file | `752b1ff` | `longrun.sh:87-93`; called from the `grid`, sweep and rerun loops (`:564`, `:653`, `:734`). **Built, never exercised in any recorded sweep.** |
| `FAB_LR_BOOST` | `752b1ff`, reworked `9146136`, gated `e25d9b5` | `_SPEC` default **2.0 — ON**; `self_organize.py:5333-5348`. Now gated on `fab.use_age(i) >= FAB_GRACE`, ranks within the eligible set. **Built, on by default, never run at pilot scale.** See §3. |

---

## 2. THE TWELVE "NOT FIXED AT HEAD" ENTRIES, RE-VERIFIED

Carried from `05_ERRORS.md` §11 by id. Each was re-checked against `eecb277` for this file.

**Headline: none of the twelve is fixed at HEAD.** The brief anticipated that `e25d9b5`, `daf9f89`,
`9146136` and `95aa336` might have closed several. They did not — and they could not have: all four
are ancestors of `38b02ae`, the commit that wrote `05_ERRORS.md`, so that file was already written
with them in hand (it cites `daf9f89` at `E7.24` and `9146136` at `E2.11`/`E10.47`). What those four
commits did close is the §1 uncommitted-work item, not a §11 defect.

What *did* change is that **four of the twelve are now stated wrongly** in `05_ERRORS.md` — three
whose numbers have gone stale and one that is materially worse than recorded. Those corrections are
the useful output of this pass.

| id | Verdict at `eecb277` | Category |
|---|---|---|
| `E2.10` | NOT FIXED | BUILT, RUN, BROKEN (inert at defaults) |
| `E7.15` | NOT FIXED | BUILT, RUN, BROKEN |
| `E7.41` | NOT FIXED | BUILT, RUN, BROKEN (wording) |
| `E10.2` | NOT FIXED — **and 33% worse than recorded** | BUILT, RUN, BROKEN |
| `E10.46` | NOT FIXED | BUILT, NEVER RUN (inert: `LR_DECAY=0`) |
| `E9.32` | NOT FIXED | NEVER RUN |
| `E9.30` | NOT FIXED (infrastructure) — mitigation currently satisfied | — |
| `E2.6` | NOT FIXED (deliberately) | BUILT, RUN, BROKEN |
| `E2.14` | **Fixed where it runs; stale where it doesn't** — statement needs correcting | BUILT, RUN, BROKEN |
| `E8.29` | NOT FIXED — **premise wrong: it HAS been re-measured 413 times** | BUILT, RUN, UNREAD |
| — (`retire_stale`, `fuzzy_segment`, `track_usage`) | NOT FIXED | BUILT, NEVER RUN |
| `E6.7` | NOT FIXED — **numbers stale; the asymmetry has reversed direction** | BUILT, RUN, BROKEN |

### 2.1 `E2.10` — `EXPERTS` is mutually exclusive with `FABRIC` — NOT FIXED

The `elif` chain stands. `self_organize.py:426` still carries the note from `51889b7` calling the
exclusivity *"arguably a bug"*. The mitigation added at `535f5f6` is a **warning**, not a fix:
`self_organize.py:4131-4134` appends *"EXPERTS=1 AND FABRIC=1 -> the expert bank is a NO-OP… Use one
or the other."* `EXPERTS` defaults to 0 and `FABRIC` to 1, so at defaults the legacy bank is simply
absent and the exclusivity costs nothing today. **BUILT, RUN, BROKEN — but inert.** Action: a fix is
only worth it if the legacy `ExpertBank` path is wanted at all; otherwise delete it and close the
entry. Cross-ref `E9.16` (the `no_experts` gate arm was vacuous because of this).

### 2.2 `E7.15` — memory entry VALUES cannot be remapped — NOT FIXED

`remap_mem_ctx()` (`self_organize.py:2548`, called at `:5740` and `:5802`) re-segments every active
entry's **context** at each retok, exactly as `8bdeca4` describes. The **value** and the **span**
are still unremappable, and the code says so at `:5859-5864`. The instrument added in the same
commit is live: `self_organize.py:5870` prints *"[vocab] memory entries predicting an id the final
stream never carries"*. **BUILT, RUN, BROKEN — measured and reported, not fixed.** Fixing it means
storing bytes rather than ids, which changes the checkpoint format, *"and RESUME is how continual
learning is meant to work here"* (`8bdeca4`). Action: a checkpoint-format decision, not a patch.

### 2.3 `E7.41` — ACROSS THE RUN BOUNDARY is weights-only — NOT FIXED

Identified `f8599b7`; the wording is unchanged at HEAD in **both** places it appears:
`self_organize.py:5977` still prints *"ACROSS THE RUN BOUNDARY: what did this run do to what was
already known?"*, and `holdout.py:6` still calls it *"the one number a continual-learning run exists
for"*. Neither says it reads weights alone. `holdout_bpb()` calls `_eval_logits`, which does not
consult the store. **BUILT, RUN, BROKEN (wording).** Action: one sentence in two files — the
cheapest open item in this document, and it bears directly on the only continual-learning result in
the project (`a9d7258`, `INV-25`).

### 2.4 `E10.2` — `main()` — NOT FIXED, and materially worse than recorded

`05_ERRORS.md` records *"~2,940 lines with 658 locals at HEAD"*, a figure carried forward from
`9c59a84` (2026-08-10) rather than re-measured. Re-measured for this file by parsing the AST of
`self_organize.py` and reading `co_nlocals` off the compiled `main`:

| commit | date | `main()` lines | locals |
|---|---|---|---|
| `9c59a84` | 2026-08-10 | 2,964 | 496 |
| `eecb277` | 2026-08-15 | **3,953** | **574** |

`main()` spans lines 3275–7227 of a 7,232-line file. **It grew ~1,000 lines and 78 locals in the
five days after the split was reverted.** The seam `9c59a84` measured at 136 values has not been
re-measured and is not smaller. **BUILT, RUN, BROKEN.** Action unchanged from `9c59a84`: a rename
pass over the per-block temporaries first, then a cut — *"a real piece of work with its own
verification"*. Note that the recorded 658-locals figure and this 574 are different counting
methods; the direction of travel is what matters and both measurements here use one method.

### 2.5 `E10.46` — the `LR_DECAY` envelope multiplies the floor — NOT FIXED

Verified line by line at HEAD. `self_organize.py:3680` builds `_cyc` **already containing** the
`LR_MIN_FRAC` floor; `:3695-3698` then multiplies that by `_env`, which itself only bottoms at
`LR_MIN_FRAC`, giving `LR_MIN_FRAC²`. `_env` is computed from global progress, so the horizon
dependence `LR_EPOCHS` exists to remove is re-introduced. `_SPEC` has `LR_DECAY` at **0.0**, so
nothing measured is affected and nothing ever will be until someone sets it. **BUILT, NEVER RUN, AND
KNOWN-BROKEN — the worst of the three states**, because the first person to use the knob inherits
the bug. Found `9645050` by a research agent reading code written the same session.

### 2.6 `E9.32` — no GPU noise baseline — NOT FIXED. See §11.1.

`ls runs/equiv_noise_*` → **No such file or directory**, re-confirmed at `eecb277`. 47 directories
under `runs/` and none of them is a noise baseline.

### 2.7 `E9.30` — the container has rolled back at least three times — NOT FIXED (infrastructure)

`b6952da` and `046fd81` record three rollbacks in one day, one of which produced a false audit
finding *"true of the checkout it read but not of the repo"*. Unfixable in this repo. The standing
mitigation — push early — **is currently satisfied**: the tree is clean and `rm-predict` is in sync
with `origin/rm-predict` (§1). This entry stays open because the hazard recurs, not because
anything is at risk right now.

### 2.8 `E2.6` — `SEG_MIN`/`SEG_MAX` still sized for a byte `WIN` — NOT FIXED, deliberately

At HEAD `_SPEC` has `SEG_MIN=700`, `SEG_MAX=1800`, `WIN=128`. `3f44ce3` added the arithmetic guard
(`self_organize.py:4204`, computing segment/window from `SEG_MIN`, `SEG_MAX`, `WIN` and live
bytes-per-token) and **deliberately did not move the defaults** — the falsification in that commit
shows V rising monotonically with segment length (0.19 → 0.50 → 0.68) while the live domain count
barely moves. **BUILT, RUN, BROKEN — with a loud guard instead of a fix.** Action: this is a
testbed-design decision (how long a splice segment should be), not a bug fix; it belongs with
`bigpop`-class experiment planning, §7.

### 2.9 `E2.14` — `ENC_WARMUP` above the measured 1-NN optimum — **statement needs correcting**

The probe at `d6acf20` measured 1-NN corpus accuracy peaking at **N=1000–4000** and degrading after
(98.5% at N=1000 → 80.4% at N=16000). `05_ERRORS.md` §11 says `ENC_WARMUP` is *"still above the
measured 1-NN optimum"* at HEAD. Re-checked:

| where | value | verdict |
|---|---|---|
| `_SPEC` default | **800** | *below* the optimum band, not above |
| `longrun.sh` (all pilot/grid/sweep arms, 7 sites) | **2000** | inside the band |
| `rerun.sh:58` | 2000 | inside the band |
| `longrun.sh:823` (smoke) | 60 | smoke scale, not comparable |
| `bench_gpu.sh:99` | 300 | throughput bench, not a result |
| **`sweep_domains.sh:92`** | **30000** | **the flagged value, still hard-coded** |
| **`docs/FILES.md:96`** | **30000** | documented as the Part-B invocation |

So the finding **was** acted on for every path that produces a held-out number, without a commit
saying so, and `ENC_FLOOR_K` (`f0375c5`, on at 8 since `510c695`) addressed the rest. What survives
is `sweep_domains.sh` and a doc page. **Correct the entry to: fixed in the harness, stale in
`sweep_domains.sh:92` and `docs/FILES.md:96`.** Anyone re-running the domain sweep re-runs it at the
value the probe falsified.

### 2.10 `E8.29` — the world model — NOT FIXED, and its premise is wrong. See §9.1.

### 2.11 `retire_stale`, `fuzzy_segment`, `track_usage` — NOT FIXED. See §6.

### 2.12 `E6.7` — growth and cull cadences not matched — **numbers stale, direction reversed**

`05_ERRORS.md` §11 states the asymmetry as *"`FAB_NEW_WIN`=400 vs `MANAGE_EVERY`=50"*, quoting the
source comment at `self_organize.py:587-588`, which itself quotes `6d5e6d7`. Re-read `_SPEC` at
HEAD:

| knob | value in the entry | `_SPEC` at `eecb277` | effect |
|---|---|---|---|
| `FAB_NEW_WIN` | 400 | `0` → falls back to `FAB_COOLDOWN` = **400** | unchanged |
| `MANAGE_EVERY` | 50 | **500** | the cull now runs **10× less often than stated** |
| `FAB_CULL_FRAC` | 0.08 | **0.02** (`9146136`) | the cull considers a quarter as many |
| `FAB_GRACE` | 3000 steps | **48 selections** (`9146136`) | a use clock, not a wall clock |

`fab.manage` is called at `self_organize.py:4889` on `step % MANAGE_EVERY`, i.e. every 500 steps at
defaults, against a growth allowance capped per 400 steps. **The asymmetry has flipped**: growth is
now allowed on a *shorter* window than selection runs on, which is the direction `6d5e6d7` was
guarding against, and the source comment at `:587-588` still says "(50)" and is now wrong. Nothing
measured is affected — no pilot has run since `9146136` (§7). **BUILT, RUN, BROKEN — the comment.**
Action: fix the comment, then decide the cadences on purpose. `6d5e6d7`'s own instruction stands:
*"if a population trends DOWN, that asymmetry is the first place to look."*

---

## 3. BUILT, ON BY DEFAULT, NEVER VALIDATED AT SCALE

Everything here executes on every default run and has never been measured at pilot scale
(4 MB/epoch × 8 epochs, `D_MODEL=768`, `WIN=256`, `BATCH_W=16`, ~48k steps). **This is the most
dangerous list in the file** — it is what a default run is actually made of.

| Knob / mechanism | Default at HEAD | Built | Never validated because |
|---|---|---|---|
| `FAB_NEW_FRAC` | **0.04** | `f4b2e9b`, `6d5e6d7` | added *after* the 2×2 (`cc0a377`) that made it necessary; no pilot since |
| `FAB_BURST` | **1** | `6d5e6d7` | same |
| `FAB_LR_OWN` | **1** | built off at `91fd815`, flipped on at `9146136` | *"nothing measured ran with them on"* (`E2.11`) |
| `FAB_LR_BOOST` | **2.0** | `752b1ff`, gated `e25d9b5` | landed the same day as the last commit; no pilot |
| `FAB_LR_CYCLE` / `_GAMMA` / `_AMIN` | on; `AMIN` **0.15** | `9146136`, `95aa336` | `95aa336` is the second-most-recent code commit on the branch |
| `EVICT=lru` + `MEM_PROBE_EVERY=25` / `MEM_PROBE_N` | on | `daf9f89` | the eviction rule finally has a signal; nothing has run with it |
| `MEM_PER_EXPERT=0` | **0** (was silently 1 for the project's whole life) | `e25d9b5`, `daf9f89` | *every* recorded memory figure used the partitioned store (`INV-06`) |
| `TOK_ANCHOR_USES` | 400.0 | — | **inert**: gated on `TOK_COMPOSE=0`. §4 |
| `LR_RESTARTS` | 1 | — | `ac79e92` measured a real restart swinging the held-out curve 1.5 b/B and never resettling; the arm that isolates it (`vmax4k_18ep_norestart`) is n=1 |
| the retok guard | `RETOK_EVERY=3000` | `d0728fe` | `self_organize.py:4856`; the `RETOK_EVERY=0` companion arm `base_nr` has never run (§7) |

**The compounding fact, from `DOC_PLAN.md` "know NOW" #1:** `_SPEC` at HEAD reads `FAB_GROW=1`,
`FAB_N0=3`, `FAB_NMAX=4096` — that is arm **D** of the population 2×2 (`cc0a377`: mean 3.384, spread
2.074), not arm B (mean 1.999, spread 0.080). Everything in the table above was built to make arm D
survivable. **None of it has been measured.** Until it is, "the default configuration" is a
hypothesis.

---

## 4. BUILT, OFF BY DEFAULT, NEVER MEASURED AT PILOT SCALE

All verified against `_SPEC` at `eecb277`. "Smoke" ≈ 40 kB, "toy" ≈ 400 steps; neither produces a
comparable held-out figure.

| Knob | Default | Best evidence that exists |
|---|---|---|
| `TOK_COMPOSE` | 0 | smoke (`pgate_c`, `compose`); one toy pilot at 5.360 confounded with `TOK_MINT_NOVEL` |
| `TOK_MINT_NOVEL` | 0.0 | toy only (6.034 vs 5.764, *"meaningless here"*) |
| `TOK_MINT_PMIN` | 0.0 | smoke (`pgate_t`); `1a113f5` records it starving the vocabulary in the first real pilot |
| `TOK_PROBATION` (`prob_use` / `prob_emb`) | 0 | smoke only; retired 217 and 224 of 256 minted tokens (`f8599b7`) |
| `LOSS_MASK_DEAD` | 0 | built `e9f2e58`, corrected `f8599b7`; never run at pilot |
| `GROW_CAP` family (`GROW_CAP`, `_EVERY`, `_FAB`, `_FAB0`, `_PLATEAU`, `_VOCAB`, `_VOCAB0`, `GROW_LIFT`) | `GROW_CAP=0` → **whole family inert** | `e2db890`, `41d2c5d`; smoke only. Also §8: all seven have **never been set anywhere in the project's history** |
| `FAB_RESCUE` | 0.0 | `e2db890`; `E6.9` records the rescue path firing **zero** times on an 1800-step run with `FAB_GRACE=3000` |
| `LR_DECAY` | 0.0 | never run — **and known-broken**, §2.5 |
| `WARMSTART_MODE=last`/`first` | `mean` | `mintinit`: an 18-trial microbenchmark and one contradicting toy. *"The pilot decides."* It never ran |
| `CHAIN_SUP` | 0.0 | `chainsup` ran in the 18-arm grid; the mechanism is evidence *against* the diagnosis that motivated it (`E8.30`) |
| `CHAIN_CURRIC` | 0 | `INV-08`: reported from a run in which `maybe_deepen` never executed. **Withdrawn, not upheld** |
| `CHAIN_STATE_Q` | 0 | `stateq` ran in the 18-arm grid, pre-`c76dc74` |
| `DOM_ADAPTIVE`, `DOM_RELATIVE`, `SHIFT_REL` | 0 | measured **worse** than the constant each replaces (`51889b7`) — off for a reason, not by oversight |
| `DOM_RADIUS` | 1 (on) | `510c695`'s radius+fold grid; never isolated at pilot |
| `ENC_PROTO` | 0.0 | never run |
| `SIG_SPACE=tokens` | `bytes` | `E9.17`: it **crashed** the first time a smoke arm exercised it |
| `VERIFY=recon` | `selfcon` | §9.2 — not run since `f5303d6` (2026-07-22) |
| `VERIFY_SWEEP` | 0 | built `fdc8e21`; the detect-and-remove path has never executed on a real store |

---

## 5. KNOWN-BROKEN OR STRUCTURALLY LIMITED

Distinct from §2 in that these are not defects to be patched but shapes the system currently has.

1. **`EXPERTS` ⊥ `FABRIC`** — §2.1 (`51889b7`, `E2.10`).
2. **Memory VALUES and SPANs do not survive re-segmentation** — §2.2 (`8bdeca4`, `E7.15`). Fixing it
   changes the checkpoint format.
3. **`main()` is 3,953 lines with 574 locals; the split was attempted and reverted** — §2.4
   (`9c59a84`, `E10.2`). The seam is ≥136 values wide.
4. **The default configuration is arm D** — §3 (`cc0a377`, `a5cc7ea`). And the best result on record
   (arm B, 1.999) **is not reproducible at HEAD**: founders had no birthday and were immune to
   culling, so arm B ran with zero culls for its whole life; the fix is in (`91fd815`, `a5cc7ea`) and
   the same config now culls 6 times (`INV-15`).
5. **`MODEL=transformer` has never been evaluated where the base model survives** (`bf53d40`). It has
   run twice — held-out 2.130 and 2.184 — but both under `FAB_GROW=1` to 4096 experts, pre-instrument
   fixes, with model-alone at 4.680 and 4.952 and the fabric compensating by +2.625 / +2.801. *"That
   is arm D seed0 exactly."* **BUILT, RUN, AND UNINTERPRETABLE.**
6. **`TOK_ANCHOR=0.05` is printed on the EFFECTIVE line of every run while contributing nothing**
   (`fec2285`) — it is a method of `ByteComposer`, constructed only under `TOK_COMPOSE=1`, which is 0.
   The `[config-audit]` at `self_organize.py:4299-4311` now fires on **every default run** saying so.
   Inert, loudly (`08_GLOSSARY` Q13).
7. **`runs/` holds nothing newer than the `equiv` pair (2026-08-10).** Every GPU result from that date
   onward exists only in commit messages and `runs.csv` (`01_TIMELINE` closing section). The primary
   record is the commit log.

---

## 6. NEVER EXECUTED — code that is present, imported and costed, and has never run

Verified by grep across the live tree at `eecb277` (`legacy/` and `garry/` excluded — those are
frozen snapshots and their call sites do not count).

| Symbol | Defined | Called from | Status |
|---|---|---|---|
| `retire_stale` | `tokenizer.py:372` | **nothing in the live tree.** Only `legacy/train.py:269` calls it | never run. The online vocabulary only ever GROWS |
| `fuzzy_segment` | `tokenizer.py:410` | `tokenizer.py:343`/`:348`, both behind `getattr(self, "_use_fuzzy", False)` — **never set anywhere** | never run |
| `track_usage` | `tokenizer.py:354` | **nothing in the live tree.** Only `legacy/train.py:133` | never run — and it is the prerequisite for `retire_stale` |

`self_organize.py` names all three itself, three separate times, as one recurring pattern:
`:4673` (*"the evidence `retire_stale` was written for and never given"*), `:5763-5764` (*"…which is
how this file collected `retire_stale`, `track_usage` and `fuzzy_segment`, all defined and none of
them ever called"*), `:6093` (*"present, paid for, never executed"*). The general form —
**a maintenance path with no counter cannot be told from one that silently stopped** — is the same
failure as `E6.9` (rescue fired zero times), `INV-08` (`maybe_deepen` never coincided with a flush)
and `INV-05` (`MANAGE_EVERY` exceeded the run).

Wiring `retire_stale` in is a designed-not-built item with a note of its own:
`handoff/designed-but-not-built/retire_stale-tokenizer-unmerge-wiring.md`.

---

## 7. THE 23 ARMS THAT HAVE NEVER RUN AT PILOT SCALE

`_flags_for` in `longrun.sh:127` defines **52 arms** at HEAD (re-counted for this file: 52 case
labels). `03_EXPERIMENTS.md` §15 establishes 29 have run at pilot scale and **23 never have**. That
section is the inventory; this one records **what each was built to answer and whether the question
is still live**. Scale definition and per-arm evidence: `03_EXPERIMENTS.md` §15.

**All 23 would, if run today, be the first arms in this project measured through a clean
instrument** — post-`c76dc74` (diagnostics were editing the run), post-`37100fb`/`8a8fb69` (the
bits/byte conversion was biased), post-`8bdeca4` (memory queried in the wrong segmentation). No arm
comparison in the record predates those safely (`INV-13`).

### 7a. The three flagged high-value (`03_EXPERIMENTS.md` §15 notes 1–3)

| arm | Built to answer | Still live? |
|---|---|---|
| **`frozen2k`** (`TOK_MINT_UNTIL=1 SEED_VOCAB=2048 VMAX=2048`) | Separates *fixed vocabulary* from *tiny vocabulary*. At `frozen`'s 512 the model has almost no whole-word units and spells everything (3.07 tokens/word vs base's 2.52) | **YES, and it is the highest-value unrun arm per unit of GPU.** Until it runs, every frozen-vs-growing comparison (X36, X37, X43) confounds the two variables. Added `a21a721` |
| **the 2×2 + anchor** (`nocompose`, `compose`, `mintnovel`, `composenov`, `noanchor`) | De-confounds `pilot_gru_8` — the 5.360 run that is the **sole** evidence against `TOK_COMPOSE`, in which `TOK_COMPOSE` and `TOK_MINT_NOVEL=0.5` were both on | **YES.** Designed, built, presetted as `grid ablate` / `grid tokens` (`d79c4ba`), never run. *"The single largest designed-and-unrun block."* `noanchor` also isolates the inert-anchor question of §5.6 |
| **`prob_use` / `prob_emb`** (`TOK_PROBATION=200`, `…_BY=embed TOK_COMPOSE=1`) | Does retiring unused minted tokens pay? | **YES — and they carry a live hazard.** `0f96784` records a `_due` double-call that *"would have fired on the first `prob_use` or `prob_emb` run"*, inert only because `TOK_PROBATION` defaults to 0. It is fixed; the arms still have not run. Smoke retired 217/256 and 224/256, but smoke `VMAX` is 256, so that says only that the mechanism fires hard |

### 7b. The remaining 15

| arm | Built to answer | Still live? |
|---|---|---|
| `base_nr` (`RETOK_EVERY=0`) | *"does re-segmenting mid-epoch earn its side effects on a GROWING vocabulary?"* — the arm's own comment | **YES.** X43 answered it only for a **fixed** vocabulary, and that answer is `INV-10` UNATTRIBUTABLE (the arms differed in two ways). The question posed has never been answered |
| `vote` (`CHAIN_VOTE=1`) | the blend rule | Weakened. X28 found `CHAIN_VOTE` was not the idea it was meant to implement; toy 5.191 only |
| `socloop` (`CHAIN_ROUTE=soc CHAIN_VOTE=1`) | society-loop routing | Partly moot: the **configuration** reached pilot scale by becoming the default at `53fbae5` — but never as a controlled arm, so there is no ablation |
| `socloop_w` (`+ ROUTE_REGION_W=0 FAB_KEY_NORM=1`) | region-weighting off, key-norm on | live; toy only (4.925, H(hop1\|hop0) 0.270) |
| `vote_w` | as above with voting | live; exit-0 verification only |
| `vote_soc` (`CHAIN_VOTE=1 FAB_STEPS=1`) | **separates DEPTH from the BLEND RULE** — the isolating arm | **YES.** This is the arm that would settle §6 of `03_EXPERIMENTS`; exit-0 verification only |
| `noban` (`CHAIN_BAN=0`) | does banning re-entry in a chain matter? | live; exit-0 only |
| `nolatch` (`FAB_RAMP_LATCH=0`) | restores the never-terminating ramp | **YES, sharply.** The latch defect (`ff0f0fa`) reshaped every population figure in the project, and its effect was measured **only** inside X24 |
| `frozen1k` | fixed vocabulary at 1024 | live; the earlier defective form ran at 50% dead rows (`INV-42`) |
| `mintinit` (`WARMSTART_MODE`) | how to initialise a newly minted token's embedding | **YES.** X39's 18-trial microbenchmark disagrees with one toy end-to-end run and *"the pilot decides."* The clearest case in the project of a well-measured proxy left unconnected to the deliverable |
| `pgate_t` (`TOK_MINT_PMIN=0.15`) | the mint gate threshold | **YES and urgent** — `1a113f5` records the gate **starving** the vocabulary in the first real pilot (1439 of 2048, held-out 3.600 against ~1.96) and failing open as the fix. The tuned value has never run |
| `pgate_c` (`TOK_COMPOSE=1`) | composition alone | subsumed by the 2×2 above |
| `bigpop` (`FAB_NMAX=16384`) | does the turn at ~step 36k track hitting the **cap**? | **Weakened.** X46 has since offered a different answer (the ramp, not the cap). Run it only if the ramp explanation fails |
| `freeze20k` (`TOK_MINT_UNTIL=20000`) | where to stop minting | live; toy only. Pairs with `freeze6k`, which did run (2.189) |
| `nogrow_s` (`SOCIETY=1 FAB_GROW=0 FAB_N0=1024`) | the single-round-society variant of the arm that did run | live; `nogrow` ran, this did not |

**Summary of live questions: 20 of the 23 are still live; `socloop` is partly moot, `vote` is
weakened by X28, `bigpop` is weakened by X46.**

---

## 8. KNOBS THAT HAVE NEVER BEEN SET

From `08_GLOSSARY.md` §5 Q5, cited not re-derived. `_SPEC` holds **310 knobs** at HEAD (re-confirmed:
parsing `_SPEC` from the AST of `self_organize.py` at `eecb277` yields 310, no duplicates).

- **223 of 310 (72%)** have never been set by `longrun.sh`, `rerun.sh`, `equiv.sh` or `runs.csv`.
- **90 of 310 (29%)** have never been set **anywhere, by anyone, in the 267-commit history** —
  widening the search to `preflight.sh`, `sweep_domains.sh`, `sweep_domain_grid.sh`, `bench_gpu.sh`,
  `run_full_unfrozen.sh`, `README.md`, `STATE.md`, `CL_TESTBED.md`, `docs/`, `handoff/`, `garry/` and
  the full commit log. They have only ever run at their declared default.

The 90: `AFF_MIN`, `BAL_FLOOR`, `BEST_TRACK`, `CENT_EMA`, `CHAIN_DEPTH0`, `CHAIN_EPS`,
`CHAIN_PATIENCE`, `CHAIN_STAGE_MAX`, `COMP_EMA`, `DECAY_EVERY`, `DOM_CULL_EMPTY`, `ENC_CREG`,
`ENC_VREG`, `EXPERT_NULLS`, `EXP_DOM_FRAC`, `FAB_BALANCE`, `FAB_BIRTH_WIN`, `FAB_CENT_TOPK`,
`FAB_DISCOVER`, `FAB_EMB_HID`, `FAB_EMB_VAR`, `FAB_ERR_FAST`, `FAB_ERR_SLOW`, `FAB_FAIL_TOL`,
`FAB_HALT_MAX`, `FAB_HID_MULT`, `FAB_LR_AMIN`, `FAB_LR_CYCLE`, `FAB_LR_GAMMA`, `FAB_LR_MAXR`,
`FAB_MUT`, `FAB_MUT_BIG`, `FAB_MUT_BIG_P`, `FAB_NEW_WIN`, `FAB_NORM_ONLY`, `FAB_PARENT_MAX`,
`FAB_PRESSURE`, `FAB_RAMP`, `FAB_RAMP_TO`, `FAB_RECOVER_MAX`, `FAB_RECOVER_MIN`, `FAB_RESCUE`,
`FAB_SHIFT_TOL`, `FAB_SPAWN`, `FAB_SPAWN_FLOOR`, `FAB_SPAWN_MULT`, `FAB_XOVER`, `FAB_Z`,
`GENUINE_SIL`, `GROW_CAP`, `GROW_CAP_EVERY`, `GROW_CAP_FAB`, `GROW_CAP_FAB0`, `GROW_CAP_PLATEAU`,
`GROW_CAP_VOCAB`, `GROW_CAP_VOCAB0`, `GROW_LIFT`, `INFO_NULLS`, **`LR`**, `LR_MIN_FRAC`, `MEM_CONF0`,
`MEM_GATE`, `MEM_PROBE_EVERY`, `MEM_PROBE_N`, `MEM_W`, `N_PROCESSES`, `PHASES`, `PHASE_W`,
`RECON_HID`, `RECON_TOK`, `SEED_PASSES`, `SIG_PROJ_BPT`, `TOK_MINT_GATE_K`, `TOK_PROBATION_MIN`,
`TOPK`, `USE_DECAY`, `VAL_CAP`, `VAL_FRAC`, `WARMSTART_OPT`, `WORLD_HID`, `WORLD_K`, `WORLD_LAT`,
`WORLD_N0`, `WORLD_NMAX`, `WORLD_ROUTE`, `WORLD_VAR`, `WRITE_GATE`, `WRONG_MARGIN`, `WRONG_MIN_N`,
`WRONG_THRESH`.

### 8.1 `LR` ITSELF HAS NEVER BEEN VARIED

**Every run in this project — every arm, every pilot, every grid, every smoke, all 267 commits —
trained at `LR = 2e-3`, the declared `_SPEC` default (`self_organize.py:308`).** Re-verified for
this file: no `LR=` assignment exists in any shell script, any Python file, any markdown document,
or anywhere in the commit log's command lines.

What *was* varied is the **schedule**: `LR_SCHED` (`cosine` default), `LR_EPOCHS` (the horizon), and
`LR_RESTARTS`. `1593c70`'s *"there was no learning-rate schedule — 2e-3 constant for 48,000 steps"*
is about the schedule; **the peak rate was never moved either.** The one architecture-independent
effect this project ever found outside seed spread came from `LR_SCHED`/`LR_EPOCHS`
(`08_GLOSSARY` §4, optim) — from the shape of a curve whose height was never questioned.

Three consequences:
1. Every architecture comparison in the record is a comparison **at one learning rate**, and the
   project has no evidence that 2e-3 is near-optimal for any of them. A rate sweep is the cheapest
   experiment in this document that could move a held-out number.
2. `LR_MIN_FRAC` has also never been set — so the floor of every cosine cycle is untested, and it is
   the quantity `E10.46` (§2.5) squares.
3. Where the seed floor is 0.080 b/B at best (arm B, `cc0a377`) and 1.227 at worst (`33a9299`), a
   rate sweep needs seeds. `LITREVIEW_FINDINGS.md` §1 establishes that **σ is a property of the arm,
   not of the instrument** (it ranges 26× across four arms of one experiment) — so pick the arm
   first, then the seed count.

### 8.2 Two other families worth naming

- **`GROW_CAP` and its entire family** (`GROW_CAP`, `_EVERY`, `_FAB`, `_FAB0`, `_PLATEAU`, `_VOCAB`,
  `_VOCAB0`, `GROW_LIFT`) have never been set, and `GROW_CAP=0` makes the whole mechanism inert. The
  soft-cap system built at `e2db890` and `41d2c5d` **has never executed outside a smoke test.**
- **The whole `WORLD_*` sizing family** (`_HID`, `_K`, `_LAT`, `_N0`, `_NMAX`, `_ROUTE`, `_VAR`) has
  never been set, so **the world model has only ever run in one shape** — the shape §9.1 shows has
  never worked.
- `FAB_RAMP` and `FAB_RAMP_TO` are on the list: the growth ramp whose latching defect (`ff0f0fa`)
  reshaped every population figure in the project **was never once tuned**.

---

## 9. SUBSYSTEM STATUS — constructed, costed, reachable, last exercised

| Subsystem | Constructed? | Costed? | Reachable at defaults? | Last actually exercised |
|---|---|---|---|---|
| **world model** (`world_model.py`) | YES, always | YES, every step | YES — `WORLD_MODEL=1`, `WORLD_GROW=1`, `WORLD_FEEDBACK=1` | **continuously, to 2026-08-10** — and its verdict has been negative in every one of 413 readings |
| **`verification.py`** | **NO** at defaults | **NO** at defaults | **NO** — `VERIFY=selfcon` | **`f5303d6`, 2026-07-22.** Zero logs under `runs/` contain its report line |
| **domain assembler** | YES | YES | YES — `SELF_ORG=1` | continuously; every smoke and pilot |
| **`prompt.py`** | n/a (separate tool) | n/a | reachable only by hand | **`7b28570`, 2026-08-04** — its last fix. No automated caller |

### 9.1 The world model — BUILT, RUN, AND UNREAD

`E8.29` and `INV-39` state that its only full-stack reading is `51889b7` (2026-07-29), *"beats
baseline **−84.7%** | latent std 0.07"* — which by the criterion the code itself prints
(`world_model.py:186`: *"want ~1; near-0 = collapsed = fake"*; `self_organize.py:6149`) means it has
**not learned dynamics** — and that it has **not been measured since**, while defaulting **ON**.

**Re-verified, and the "not measured since" is wrong.** Aggregating every log under `runs/`:

| | |
|---|---|
| logs containing the world-model reading | **413**, across 47 run directories |
| date range | **2026-07-30 → 2026-08-10** (the `equiv` pair is the newest thing in `runs/`) |
| readings with a **positive** "beats baseline" | **0** |
| range of "beats baseline" | **−13.6% to −94.2%** |
| distinct `latent std` values observed | 0.03, 0.06, 0.07, 0.08, 0.09, 0.10, 0.11, 0.14, 0.15 |
| any reading with `std > 0.5` (the code's own bar) | **none** |

So the correct statement is: **the world model has been measured 413 more times since `51889b7`, and
every single reading agrees with the first one.** It has never once beaten a persistence baseline
and its latent has never once left the collapsed regime. Nobody aggregated the readings, which is
why the record says "unmeasured".

Two caveats that keep this from being a verdict:
- **All 413 are smoke or equivalence scale**, not pilot. The `equiv` logs run at `d96`, `stream
  120000`, 1875 steps (`runs/equiv_c14f876_vs_37ecb20/37ecb20.log`). A collapsed latent at 1875
  steps is what an undertrained latent looks like.
- **The ablation that would price it cannot run cleanly in the record**: `E9.17` — `ab_no_world`
  exited 1 and produced no data, because `WORLD_GROW` defaults ON and its step hook called
  `world_fwd.n()` outside the `if WORLD_MODEL:` block, so `WORLD_MODEL=0` died at the first
  `MANAGE_EVERY`. *"The one ablation that would have said what the world model is worth was the one
  that could not run."* That is fixed; the ablation still has not run at pilot scale.
- Against a **param-matched monolith** on a toy multi-regime probe it is **−5.1%** with routing
  purity 0.32 — *"separation does not improve accuracy or specialize on these tests"* (`74d10d8`).

**Status: BUILT, RUN, AND FAILING ITS OWN CRITERION, ON BY DEFAULT, IN EVERY RUN SINCE 2026-07-29.**
Action, in order: (1) run one pilot with `WORLD_MODEL=0` now that `E9.17` is fixed, and price it;
(2) `WORLD_LAT`/`WORLD_HID`/`WORLD_K`/`WORLD_VAR` have never been set (§8.2) — the collapse may be a
sizing problem nobody has been allowed to test; (3) if it cannot be made to beat persistence, turning
it off is a one-character change that removes a per-step cost from every run.

### 9.2 `verification.py` — BUILT, COSTED NOTHING, UNREACHABLE AT DEFAULTS, NOT RUN SINCE 2026-07-22

Answering `DOC_PLAN.md` open question 8 point by point, from the source at `eecb277`:

- **Still constructed?** **No, not at defaults.** `self_organize.py:3353` reads
  `recon = Reconstructor(...) if VERIFY == "recon" else None`, and `VERIFY` defaults to `selfcon`
  (`_SPEC`, `:263`; read at `:406`). The module is still **imported** at `self_organize.py:21`, so
  the import cost is paid; the model is not.
- **Still costed?** **No.** The in-loop training branch at `:5200` is `if recon is not None and
  RECON_W > 0`, and `RECON_W` defaults to 0.0. `self_organize.py:5202` records the historical
  failure this guards: a term *"that was computed then multiplied by 0.0 on the default VERIFY=recon
  path"* (`a1767b7`).
- **Still reachable?** **Yes, but only explicitly.** `VERIFY=recon` gates construction (`:3353`), the
  in-loop term (`:5200`) and the whole report block (`:6532-6541`, including `VERIFY_SWEEP`'s
  detect-and-remove). Nothing sets it: no shell script, no arm in `_flags_for`, no preset. The only
  invocations are the standalone helper `run_verify_test.py` and `handoff/COMMANDS.md:51`, both
  copy-paste tools requiring a human.
- **Ever run after `f5303d6`?** **No.** Zero of the 420 logs under `runs/` contain the string
  `VERIFICATION (reconstruction)`. `verification.py` was last modified at `9df85b8` (2026-07-21) and
  has not been touched in 25 days of subsequent work.

The recorded reading stands: store-wide precision **0.3–0.5%** across three runs even at 5× steps
(`9df85b8`, `d7c141b`, `f5303d6`), which `f5303d6` locks as *"NOT an undertraining artifact… a dead
end for store-wide use; per-candidate check only."* The standalone CPU probe reaches AUC 0.978/0.980
(`verification.py:73`), so the mechanism works on synthetic data and fails on the real store.

**Status: BUILT, RUN, MEASURED AS FAILING, THEN LEFT WIRED IN BEHIND A FLAG NOBODY SETS.** The
irony `03_EXPERIMENTS.md` X-entry records: `VERIFY=selfcon` is the default, so **the old B mechanism
— the one that motivated building this — is what actually runs.** Open question Q3
(`handoff/open-questions/Q3-...md`) is marked SUPERSEDED, but its underlying fork was never closed:
either build corroboration-based detection
(`handoff/designed-but-not-built/corroboration-based-wrongness-detection.md`) or cut the path. Both
are USER decisions. Meanwhile the dead `recon` branch is ~40 lines of dead weight in
`main()` (§2.4).

### 9.3 The domain assembler — CONSTRUCTED, COSTED, REACHABLE, EXERCISED CONSTANTLY

`DomainAssembler` is defined at `self_organize.py:2742` and instantiated unconditionally at `:3738`;
`SELF_ORG` defaults to 1 (`_SPEC`, `:238`), management runs on its **own** cadence
`DOM_MANAGE_EVERY=100` (`:4886`, separated from `MANAGE_EVERY` at `:524-530`). It runs in every
smoke and every pilot, and it is the most heavily instrumented subsystem in the report battery.

It is on this list not because it is inert but because **most of what it has produced does not
stand**:

- `INV-04` — `MANAGE_MERGE=0.12` overrode the 0.28 fallback for the project's whole life, so
  creation ran at 0.35 and consolidation at 0.12. *"The whole of the fragmentation this project has
  spent weeks attributing"* elsewhere (`13e787a`).
- `INV-05` — `MANAGE_EVERY=500` exceeded the run: merge, cull and fold executed **zero** times on
  60 kB and once on 120 kB. Every domain-population figure before `510c695`, **including the
  142-domain run**, is VOID.
- `INV-16` — *"Domain assembly works, purity 0.54 → 0.96"* is **explicitly retracted**. Purity rises
  monotonically with fragmentation; the assembler was producing one domain per **splice segment**
  (`5e02cfc`).
- `E2.6` (§2.8) — the testbed's own arithmetic bounds what it can measure: at `WIN=256` tokens a
  splice segment is 2.6 analysis windows and `SUSTAIN=2` consumes two of them.
- `DOM_ADAPTIVE`, `DOM_RELATIVE`, `SHIFT_REL` are each off because each measured **worse** than the
  constant it replaces (`51889b7`) — a rare case of off-by-decision rather than off-by-oversight.

**Status: BUILT, RUN CONSTANTLY, AND ITS RESULT HISTORY LARGELY INVALIDATED.** The subsystem is
healthy; the measurements taken through it are not. Action: nothing to build — re-measure, at a
segment length the window can actually resolve (`3f44ce3`'s guard says which).

### 9.4 `prompt.py` — CONSTRUCTED, REACHABLE BY HAND ONLY, LAST EXERCISED 2026-08-04

This is the tool that reads **generations — the deliverable** (`9d90416`: *"the output — generation
is the deliverable"*). It loads a checkpoint written by `_save_ckpt` (`self_organize.py:4014`,
advertised at `:4094`).

- **Constructed / reachable?** Yes, standalone: `python3 prompt.py CKPT=…`. It is checked for
  syntax by `preflight.sh:113` and named in `run_full_unfrozen.sh:82`, but **no harness invokes it**
  — `longrun.sh` has no `readback` arm at HEAD.
- **Costed?** Nothing at train time.
- **Last exercised?** Its last change is `7b28570` (2026-08-04). There is no record of a successful
  generation read through it since.

Its history is the reason it is here (`E9.15`): it *"was completely dead"* for several commits
because it carried a duplicated copy of `Fabric` that went stale the moment the population became
tensors — *"that is the tool used to read GENERATIONS — the deliverable — and it would have failed
silently until someone tried it."* Fixed at `763e9f2` (69 lines of duplicated model code deleted),
then **broke twice more**: `e44b5b0` (per-window routing threw once `idx` became `(B,k)`) and
`7b28570` (the chaining branch assigned the whole `(h, depth, mass, bal)` tuple to `_h` — *"a
guaranteed TypeError the instant a chaining checkpoint was sampled"*). `7b28570` also made the
**checkpoint** decide the routing path rather than the environment.

The countermeasure `4554d6b1` names the general failure: *"Nothing in the pipeline ever loaded a
checkpoint after writing one, which is exactly how `prompt.py` sat completely dead for several
commits."* A read-back gate arm was added, and there are `smoke_readback_train.log` files under
`runs/rerun_0807_1654/` — but the arm is not in `_flags_for` at HEAD.

**Status: BUILT, RUN, BROKEN THREE TIMES, AND CURRENTLY UNVERIFIED.** Two things have changed
underneath it since 2026-08-04 that it has never been tested against: the memory store's eviction
and `last`-stamping rewrite (`daf9f89`) and the per-expert LR / use-clock rework (`9146136`,
`95aa336`, which added `fab_uage` to the checkpoint). Action: load one checkpoint with it before
trusting any generation, and put the read-back arm back in `_flags_for` so this cannot recur.

---

## 10. DESIGNED AND NOT BUILT — `handoff/designed-but-not-built/` (7 items)

**NEVER BUILT.** Costs engineering, not GPU. Full notes in the named files.

| Item | What it is | Blocking on |
|---|---|---|
| `retire_stale-tokenizer-unmerge-wiring.md` | wire `DynamicTokenizer.retire_stale()` into the loop so the online vocabulary can **shrink**, not only grow. Built and tested in isolation (§6) | the wiring, plus `track_usage` which is also never called |
| `release-dont-kill-domain-deletion-wiring.md` | `delete_domain()` should delete the domain's memory entries and **release** its expert affiliations, letting existing culling remove any expert left with zero constituency — never touching expert parameters directly. Semantics already agreed with the user (`handoff/decisions/domain-deletion-RELEASES-experts...`) | the wiring only |
| `corroboration-based-wrongness-detection.md` | replace *"is this token surprising?"* with *"does this entry disagree with its nearest neighbours?"* — the only plausible fix for the ~1% precision of §9.2 | a USER decision (Q3): build it or cut the path |
| `memory-pressure-triggers-expert-growth-or-domain-split-not-a-quota.md` | under a bounded store a process that stops appearing is fully evicted; `EVICT=usage` cannot fix it by construction (faded ≡ least-used). A strict per-domain quota was **REJECTED [USER]** | a mechanism. Note `daf9f89` changed the terrain: `EVICT=lru` is now recency-of-**retrieval**, so a quiet domain that still answers queries survives. That is untested at scale (§3) |
| `ROUTE_T-sweep-below-0.3-and-DIV_W-for-harder-specialization.md` | sweep `ROUTE_T` below 0.3 and tune `DIV_W` for real expert exclusivity. Caveat in the note: the likely ceiling is the **signature encoder's** separability, not more training | GPU. Also `divw` ran in the 18-arm grid and measured nothing (`INV-44`) |
| `observability-dashboard-stream-the-thinking.md` | watch domains assemble/merge/cull, experts born/routed/culled, memory writes, minting, routing mass, as they happen. A stated north-star goal (`handoff/NORTH_STAR.md`) | no design yet. The system already emits most of it as text |
| `multimodality-pluggable-avenues.md` | a "Sense" = a modality; senses integrate at the **lowest tokenizer layer** and are discovered when unusual input arrives, before reconcile → understand | far downstream of everything else here |

Also **NEVER BUILT**, from `handoff/design-directions/` (11 notes, direction not commitment):
active learning by self-generated closed-book reproduction; experts as tool calls crystallized on
repetition; an interchangeable base with emergent subspecialties (the shape Q-regime resolves to);
reverse embedders for thought verification; partial compartmentalization; subtokenization as the
unifying primitive.

---

## 11. UNRESOLVED OPEN QUESTIONS

### 11.1 `E9.32` — the noise baseline, and what would resolve it

**Re-verified at `eecb277`: `runs/equiv_noise_*` does not exist.** 47 directories under `runs/`;
none matches.

`c6f54e6` established that this GPU is nondeterministic **in exactly one subsystem**: training is
bit-reproducible (`model ALONE 3.889 → 3.889`, `model + FABRIC 3.325` — both IDENTICAL), while the
**memory store's retrieval** is not (`3.427` vs `3.431`), and the three numbers derived from it move
with it. `equiv.sh` therefore writes the set of line *shapes* this machine varies on — numbers
masked, so `3.427`-vs-`3.431` and `5100`-vs-`5113` collapse to one pattern each — to
`runs/equiv_noise_<device>.txt`, and a later comparison **subtracts them** and judges the remainder.
Differing only in known-noisy lines reports **INERT** and exits 0.

**Without that file, `equiv.sh` has nothing to subtract, so every INERT verdict it has issued is
untrusted.** `c6f54e6`'s own instruction: *"Run `equiv.sh HEAD HEAD` once per machine to establish
the baseline before trusting a comparison."*

**What would resolve it, exactly:**

1. On the GPU box, on the branch, run `bash equiv.sh HEAD HEAD` once. It writes
   `runs/equiv_noise_<device>.txt`. That is the whole fix; it costs two short runs.
2. **Commit the file**, keyed by device — it is machine-specific, and the CPU baseline does not
   transfer to the GPU or vice versa. Note `E9.30`: the container has rolled back three times, and an
   uncommitted baseline is exactly the kind of thing that gets lost.
3. Then re-issue every equivalence verdict taken without it. The one stored comparison in the tree,
   `runs/equiv_c14f876_vs_37ecb20/` (two `.log` files and two `.norm` files, 2026-08-10), **does not
   contain its own verdict line** — the INERT/DIFFERS judgement was printed by `equiv.sh` to the
   terminal and never stored. So `DOC_PLAN.md` open question 10 ("what did it conclude?") **cannot be
   answered from this checkout**; it must be re-run, which needs step 1 first.

Until then: `equiv.sh` remains the fastest bug-catcher in the project (it caught the broken import of
`7de4daf` in **four minutes**, where `py_compile` passed and the smoke gate would have taken 11 arms)
— it is only its *negative* verdicts that are untrusted.

### 11.2 The four recorded open questions, at HEAD

`handoff/open-questions/`. Status re-read at `eecb277`.

| Q | Question | Status at HEAD |
|---|---|---|
| **Q0** | What TYPE of evolution should the experts use? Fitness is **pure occupancy** (`fit = use/age`) — no loss term anywhere; steady-state, mutation-only, Lamarckian, niche speciation. *"An expert can WIN by being cheap to reach rather than good."* | **STILL OPEN, and it has moved.** `9146136` split the clock: `uage` (selections since birth) now drives grace and the per-expert LR, while `use` remains the comparative fitness. That refines *when* an expert is judged; **it does not add a loss term to the fitness**, which is the piece Q0 calls most clearly wrong. USER decision; *"do not default further"* |
| **Q3** | B direction — attempt corroboration, or cut B and ship A? | **SUPERSEDED on paper, OPEN in fact.** The note records B renamed **Verification** and reframed as reconstruction, *"a BUILD, not a decision"*. §9.2 shows the build happened, measured 0.3–0.5% precision, and was left behind a flag nobody sets. So the original fork is live again: build corroboration (§10) or cut the path |
| **Q-regime** | REDUNDANCY (`ROUTE_T=1.0`: 1.967 b/B, deleting any expert costs −0.0009, nothing specialized) vs MODULARITY (`ROUTE_GROUNDED=1 ROUTE_T=0.3`: 2.002 b/B, deletion costs +0.127 **concentrated**, ~7× ratio) | **DIRECTION SET, MECHANISM OPEN.** USER (2026-07-21) declined the binary: the target is a redundant/interchangeable base **with emergent subspecialties**. That converts a config toggle into a design challenge. Tightly coupled to Q0. Caution: both figures are pre-`c76dc74` and fall under `INV-13` |
| **Q-compute** | What to run next at GPU scale, and at what budget? Both blockers are resolved in code (DATA via `fetch_big.py`; THROUGHPUT via `BATCH_W`) but *"nothing has actually been run at the new scale"* | **STILL OPEN and now the binding constraint on this entire document.** §7's 23 arms, §8.1's rate sweep, §9.1's world-model ablation and §11.1's noise baseline all queue behind one decision. The note's own caution: a GPT-2-scale token budget is **weeks** on one H100 — *"decide the scale on purpose rather than discovering it mid-run"* |

### 11.3 Questions this pass could not close

| Question | Why it is still open | What would close it |
|---|---|---|
| What did `runs/equiv_c14f876_vs_37ecb20` conclude? (`DOC_PLAN` Q10) | the verdict was never written into the stored files | §11.1 steps 1–3 |
| Does the current default configuration reproduce **arm D**? (`DOC_PLAN` Q14, "know NOW" #1) | `FAB_NEW_FRAC=0.04`/`FAB_BURST=1` were built to prevent it and have never been measured (§3) | one 3-seed pilot at defaults. *"It needs an answer before any more GPU time"* |
| What actually ran in the one continual-learning run (`a9d7258`)? (`DOC_PLAN` Q3) | its log was lost; `runs.csv` says `fab_nmax 4096` while the note says *"RESUME from nogrow_s2"* | `holdout.py` on any surviving checkpoint, looking for a `.cfg` beside it |
| Is the **variance** difference between arms the real phenomenon, rather than the mean? | `LITREVIEW_FINDINGS.md` §1: σ ranges 26× across four arms of one experiment (0.047 to 1.225), and *"instability tracks ramping"* — **the variance is the larger effect and the question has never been asked here** | a seeded design that treats σ as the outcome |
| Is `main()`'s seam still 136 values wide? | last measured at `9c59a84`; the function has grown 33% since (§2.4) | re-run the free-variable analysis; it is cheap and it sizes the rename pass |
| Do the never-called maintenance paths (§6) still work? | they have never run, so *"a maintenance path with no counter cannot be told from one that silently stopped"* | wire a counter first, then call them |

---

## 12. IF THERE IS ONE GPU-DAY, IN ORDER

Ordered by information per unit of GPU, with the reason each is cheap.

1. **`equiv.sh HEAD HEAD`** (§11.1) — minutes, not hours. It unblocks trusting every future
   comparison, and nothing else on this list is verifiable without it.
2. **One 3-seed pilot at defaults** (§11.3) — settles whether the shipped configuration is arm D.
   Every other result depends on the answer, and §3 lists nine mechanisms whose only justification is
   that they prevent it.
3. **`frozen2k`** (§7a) — the missing control under X36, X37 and X43. One arm retroactively
   de-confounds three experiments.
4. **`WORLD_MODEL=0` at pilot scale** (§9.1) — prices a subsystem that has failed its own criterion
   413 times and runs in everything. `E9.17` is fixed, so the ablation can finally execute.
5. **The `grid ablate` / `grid tokens` 2×2 + anchor** (§7a) — five arms, already presetted, that
   de-confound the sole piece of evidence against `TOK_COMPOSE`.
6. **An `LR` sweep** (§8.1) — the single knob that has never moved in 267 commits, on the parameter
   with the largest expected effect on a held-out number.

And one that costs no GPU at all: **fix the ACROSS THE RUN BOUNDARY wording** (§2.3). It is two
sentences, and it is attached to the only continual-learning result the project has.
