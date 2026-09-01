All six suites were run before answering. Quoting the summary lines:

```
tests/test_ownership.py   47 file(s) parsed   PASS O1..O5 (+ rest)
tests/test_contract.py    13 package(s); document docs/04_CONTRACT.md; Python 3.11.15   PASS K1..K5 (+ rest)
tests/test_census.py      328 census row(s) ... 259 declared lever(s), 23 wire target(s), 9 declared departure(s)  PASS N1..N4
tests/test_assemble.py    23 declared coupling(s), 25 wire budget   PASS A1..A5
tests/test_couplings.py   === 4 checks, 0 failing ===
tests/test_derive.py      575 oracle cases, 0 mismatches   (_phases 60 cases OK, pin_tick 32 cases OK)
```

---

## Q-DATA-4 — `data/continual/` and `data/ood/` are unreachable from any DATA lever

**What I read**
`docs/04_CONTRACT.md:944-953`; `src/data/api.py:29-76` (`open_areas`) and `:198-210` (`restore_stream_state`); `src/data/levers.py:216-226` (`dir`), `:228-247` (`areas`); `datastream.py:69-83`; `tests/test_census.py:75-140` (the `DEPARTURES` table) and `:244-270` (N2's body); `ls -R data`, `du -sh data/*`; `grep -rln` over `archive/`.

**What is true today**
The question is live and every factual claim in it checks out.

- `datastream.py:72` is `paths = [p for p in sorted(glob.glob(f"{data_dir}/train/{d}/*")) ...]`, and `:75` repeats `train/` inside the refusal message. The `train/` level is hardcoded, not a knob.
- The rebuild carries the rule forward verbatim: `src/data/api.py:33` says *"reads `dat.dir + "/train/<area>/*"`"*, and `src/data/levers.py:216` help text says *"areas are read from DATA_DIR/train/&lt;area&gt;/part\*.txt"*. Both are frozen text a P4 author will implement literally.
- The material is present: `data/continual/{01_rust,02_sawyer,03_dracula,04_num2}` (1.5 M) and `data/ood/{code_OOD,eng_OOD}` (764 K), each holding `a.txt` / `rust.txt` / `sherlock.txt`. `data/train/` holds `c, eng, num, py` (6.9 M).
- Nothing in `src/`, `tests/`, or the root harnesses (`longrun.sh`, `run_cl_test.sh`, `cl_bench.py`) names either directory. The only readers are `archive/legacy/{build_continual_data.py,continual.py,README.md,LAUNCH.md,CONTINUAL.md}` and the transcript chunks under `notes/_evidence/`. Confirmed by grep.
- There is no escape by setting `dir`: `DATA_DIR=data` + `DATA_AREAS=01_rust` resolves to `data/train/01_rust` (absent); `DATA_DIR=data/continual` resolves to `data/continual/train/01_rust` (absent). The directories are genuinely unreachable without moving files.
- `archive/legacy/continual.py:47` records the legacy protocol — *"Each subfolder of `data/continual/` is one phase (one arriving domain). 80/20 adapt/held split"* — which is exactly `DATA.areas` + `phase_sched` + `holdout_frac`. The shape already matches; only the path does not.

**The options**

| | cost | buys |
|---|---|---|
| (a) allow `/` in an `areas` entry, joined under `dir` verbatim; `train/` stays the implicit prefix when there is no slash | one lever's *string* changes meaning; two new startup refusals; the label rule has to be stated | no lever, no wire, no signature; `DATA_AREAS="eng,continual/01_rust"` works and the Sample records it |
| (b) a new `DATA_SUBDIR`/`DATA_SPLIT` lever defaulting to `"train"` | **fails `tests/test_census.py` N2 as the tree stands.** N2 requires every declared lever to trace to a census row or a `DEPARTURES` entry, and `DEPARTURES` is keyed by `(family, old_name)` — *a census row's own identity*. A lever with no census ancestor has no key to write, so the departure cannot be declared either. This is a census amendment, not a lever declaration | one subdir per run — which is also its flaw: you cannot mix `train/eng` with `continual/01_rust` in one run, which is the add-an-area experiment |
| (c) do nothing; the operator restructures the disk | free in code | the configuration becomes a filesystem state no `Sample` can record — the exact defect the question names |
| (d) drop `train/` entirely, join `areas` under `dir` always, ship `areas="train/eng,train/py,..."` | changes the shipped default's meaning (a default nobody decided) and breaks every harness that exports `DOMAINS`/`DATA_AREAS` | one rule instead of two |

**Recommendation**
**(a)**, with two refusals the contract's sketch does not name:

1. an entry that is absolute or contains `..` is a **startup refusal**. Without it, `areas` becomes an arbitrary-path read — a corpus lever that can open `/etc`.
2. the area **label** is the basename, and a label collision (`continual/01_rust` beside `ood/01_rust`) is a **startup refusal**, printed with both source paths.

**Why it fits the framework**
It is the only option that touches nothing structural. No lever is minted, so N2/N4/K4 are untouched. No wire is added, so the 25-wire budget and `grep -rn d_ src/` stay exactly as they are. No frozen signature moves. `dir` and `areas` are read at exactly one site — `DATA.open_areas` — so the whole decision stays inside the package that owns the bytes, and what leaves is still `Areas.names`, unchanged in type. (b) is the option that fights the framework: the census is a closed set, `DEPARTURES` is keyed by census identity, and N2 has no slot for a lever with no ancestor. (c) is refused by the DID-IT-FIRE discipline rather than by taste — a run whose corpus selection lives in `mv` is a run whose report cannot state what it trained on.

**A second finding, verified, that gates the same benchmark one row later.** `src/data/api.py:198-203` says `restore_stream_state` *"REFUSES LOUDLY if the recorded area names, holdout offsets or holdout sizes disagree with what `open_areas` just produced"*. An add-an-area run is **by definition** a resume whose area list gained a name (`longrun.sh:938` runs `DOMAINS="eng,$NAME"` against a parent trained on `eng`). Read as set-equality, that refusal **refuses the goal-B headline experiment at startup**; read as *"every area carried over from the parent must have the same holdout offset and size, and a name the parent did not have is admitted with a printed `data.area_added` line"*, it permits it and still catches the moved-block case the docstring's own reason is about. Two readings, different code, and no question asks it. `compose.py:304-309` confirms the row runs unconditionally whenever `"DATA" in saved`.

**What changes**
- `src/data/api.py:29-76` — `open_areas` docstring: the path rule (`"/" in entry → dir + "/" + entry`, else `dir + "/train/" + entry`), the two refusals, and two counters in `DID IT FIRE`: `data.area_path_refused`, `data.area_label_collision`.
- `src/data/api.py:198-210` — `restore_stream_state` docstring: state which of the two readings of the name check is normative, and add `data.area_added` to `DID IT FIRE`.
- `src/data/levers.py:216-218` (`dir` help) and `:228-232` (`areas` help) — the help text is what `docs/04_LEVERS.md` prints, so it must carry the slash rule.
- `docs/04_CONTRACT.md:944-953` (the ruling) and `:220-223` (the DATA counter list).
- **No frozen signature moves.**

**Confidence** High on the facts (paths, absent readers, N2's mechanics — all run or grepped). Medium on the label rule: if `ACROSS THE RUN BOUNDARY` must look up a parent that recorded the bare name, basename-labelling is right; if it should record the full string, that is the owner's call and it is a one-word change.

**Literature** NOT APPLICABLE. This is a path-and-ownership question about this tree; no paper can say where `train/` should sit.

---

## Q-DATA-6 — the held-out split becomes a seeded random block

**What I read**
`docs/04_CONTRACT.md:965-974` and `:74` (the refused-wires table); `src/data/api.py:44-52`, `:177-196`, `:198-210`; `src/data/levers.py:405-443` (`holdout_frac`, `val_cap`) and `:126-131`; `src/spine/compose.py:120-125` (`RNG_SUBSYSTEMS`); `self_organize.py` context around the measured numbers via `data/levers.py`'s citations.

**What is true today**
The rule is **already written into the tree**, so this is a ratification, not an open design question.

- `src/data/api.py:44-52`: *"THE HELD-OUT BLOCK IS A SEEDED RANDOM CONTIGUOUS BLOCK PER AREA, from `rng_for("data.holdout", seed)`, of size `min(holdout_frac * present, val_cap)` — NOT the tail."* It also states the block is **physically removed** from the training body (M81) and that `val_cap` applies on both paths (M82).
- The plumbing is already in place: `"data.holdout"` is in `RNG_SUBSYSTEMS` (`compose.py:125`), `Areas` declares `rng_holdout` and `holdout_bytes` (`api.py:21`), `stream_state` checkpoints the offsets (`api.py:177-186`), and `restore_stream_state` refuses a moved block (`api.py:198-203`).
- The measured motivation checks out as quoted: py held out at **5.061 ± 0.560** against 2.922 in-stream, eng (shuffled upstream) **2.273** against 2.303 — a ~2.1 b/B artefact of corpus ordering reported as a property of Python.

**Two things are NOT written and one of them is a stale claim.**
- `src/data/levers.py:130` and `:441` both assert the resolved held-out size *"is declared in spine.assemble on the RECEIVER (`EVAL.d_holdout_bytes`)"*. **It is not.** `grep -rn holdout_bytes src/` finds no such coupling, and `docs/04_CONTRACT.md:74` lists `EVAL.d_holdout_bytes` in the **refused** wires with the correct reason: the size depends on bytes on disk, so `build()` would have to `stat` the corpus, and wiring `val_cap` instead would print the *ceiling* as the size. The wire is not merely absent, it is **structurally impossible** under the freeze rule — the same rule that refused `bytes_per_token` and the SIG width. `K5` passes because the wire was never declared; the two levers.py sentences are stale and will mislead a P4 author into looking for a row that must not exist.
- Nothing yet names the **field on the Sample that records which split rule ran**, which is the half of this ruling that makes the two eras distinguishable.

**The options**

| | cost | buys |
|---|---|---|
| (a) contiguous tail (status quo ante) | keeps a measured 2.1 b/B ordering artefact inside the one number goal B rests on | every historical held-out number stays comparable |
| (b) seeded random contiguous block (what is written) | **every historical held-out number becomes non-comparable**; one extra adjacency seam per area (a middle block has two training neighbours, a tail has one); the training body gains one manufactured discontinuity, which interacts with `seg_contig=True`'s claim that *"the only boundaries left are the text's own"* (`data/levers.py:349-360`) | removes the ordering confound; position is a function of `(seed)` and is recorded and refusable on resume |
| (c) whole-file / document-boundary holdout | `holdout_frac` becomes quantised to file sizes and is undefined for a single-file 60 MB fetched shard | the split the contamination literature actually endorses |
| (d) (b) + a measured overlap reading | one exact-substring pass at startup | answers the near-duplicate question with data instead of an argument |

**Recommendation**
**(b) as written, plus (d)**, and confirm the break loudly. Three additions:

1. **The split rule, the seed and the per-area `(offset, size)` go on the Sample and in the report banner** — not as prose but as fields, so the two eras sort apart rather than mixing silently. This is the part of the ruling that makes the break honest, and it is currently unwritten.
2. **Count the seam.** Removing a middle block leaves exactly one discontinuity in a body that `seg_contig=True` reads in order from a persisting cursor. Declare `data.holdout_seam` (one per area) so the single-area goal-A configuration's contiguity claim is either still true or visibly qualified. One seam per area against the thousands `seg_from` manufactures is a good trade — but it must be a printed number, not an assumption.
3. **A Reading, not a lever:** the fraction of held-out bytes that also occur verbatim in the training body at some fixed n-gram length, printed once at startup, per area. This is the `OPT.counters` grad-norm move from Q-OPT-3 applied here: it costs no lever, no wire, no default, and it answers the only question the split rule *cannot* answer.

**Why it fits the framework**
Everything (b) needs already exists: the RNG subsystem is minted, `Areas` carries the offsets, `stream_state` checkpoints them, `restore_stream_state` refuses a move. A `holdout_rule` **lever** is not available — N2 has no census row for one (same mechanism as Q-DATA-4 option (b)) — so the rule is a package decision recorded on the Sample, which is what `data/levers.py:423` already says. The tail rule is refused not by preference but by the wrong-MEASUREMENT rule: it lets a corpus-ordering artefact be reported as a property of a language, which is the defect family the rebuild exists to end. And the two stale sentences at `levers.py:130` and `:441` must be corrected to match `docs/04_CONTRACT.md:74`, or a P4 author will try to declare an impossible coupling and `A1`/`K5` will bounce it with a confusing message.

**What changes**
- `src/data/levers.py:126-131` and `:437-443` — replace *"declared in spine.assemble on the RECEIVER"* with the contract's actual verdict: refused as a wire, travels as an argument, recorded as a Sample field (`docs/04_CONTRACT.md:74`).
- `src/data/api.py:44-52` — add `data.holdout_seam` and the overlap Reading to `DID IT FIRE`; state the Sample fields.
- `docs/04_CONTRACT.md:965-974` — mark the confirmation given; add the break to P9's "numbers that moved" list with this reason.
- **No frozen signature moves.**

**Confidence** High that (b) beats (a) here — the ordering effect is measured at ~2.1 b/B and the adjacency cost is bounded by one extra seam. Medium on (d)'s cost at a 60 MB corpus; a suffix-automaton or a hashed-shingle pass is cheap, a naive one is not, and I did not benchmark it.

**Literature — this is the question it bore on most.**
It supports the *direction* and refuses the *complacency*:
- Lee et al., **Deduplicating Training Data Makes Language Models Better** (arXiv:2107.06499): models *"underestimate perplexity on evaluation documents with near duplicates in the training corpus by several points"*, web scrapes carry 3.04% (C4) to 13.63% (RealNews) near-duplicates, and — the sentence that bears directly — benchmarks *"should actively remove contaminated training data, rather than just partitioning held out splits by documents"*. **Neither the tail nor the random block is safe on its own.** That is the whole argument for addition (3).
- Magnusson et al., **Paloma** (arXiv:2312.10523): decontamination should be at the **sub-document** level, because contaminated spans inside otherwise-unrelated documents still inflate the score. The project's areas are concatenated file bodies, i.e. sub-document by construction — so the caution applies directly.
- The grouped/temporal-split literature cuts the **other** way and is worth stating so the owner is not sold a one-sided case: random splits over non-independent rows *"inflate metrics"*, and *"contiguous folds provide more conservative and realistic benchmarks"* than shuffled ones. That argument applies to randomly *sampled* held-out text. It does **not** transfer to a randomly *positioned contiguous block*, which keeps contiguity and randomises only where the block sits. The honest summary: (b) buys removal of a 2.1 b/B systematic ordering bias and pays one additional adjacency boundary per area.

Sources: [Deduplicating Training Data Makes Language Models Better](https://ar5iv.labs.arxiv.org/html/2107.06499) · [Paloma: A Benchmark for Evaluating Language Model Fit](https://arxiv.org/pdf/2312.10523) · [Temporal Splits: Splitting Train/Test by Time to Prevent Leakage](https://kumo.ai/pyg/concepts/temporal-split/)

---

## Q-DATA-7 — how is D2 (PURE_ADD) actually produced?

**What I read**
`docs/04_CONTRACT.md:955-963`; `src/data/api.py:77-126` (`data_plan`) and `:22` (the `Plan` record); `src/data/levers.py:332-380` (`phase_sched`), `:382-403` (`phase_live`), `:105-124` (DEFECT 3); `src/spine/derive.py:673-713` (`phase_schedule`); `longrun.sh:921-940`; `grep -c PURE_ADD self_organize.py`; `tests/test_derive.py` output.

**What is true today**
Every claim in the question verifies, and one fact it does not state decides the answer.

- `grep -c PURE_ADD self_organize.py` → **0**. It is `longrun.sh:930-935`: `if [ "${PURE_ADD:-0}" = 1 ] && [ -z "${PHASE_SCHED:-}" ]; then _AI=1; export PHASE_SCHED="$_AI|$_AI|$_AI|$_AI"`, with the comment *"DOMAINS is 'eng,$NAME', so the added area is index 1"*. So the harness already assumes **the last entry is the arriving area** — but only by hardcoding `1` for a list it knows has two entries.
- `Plan.protocol` already declares the four names it must produce: *"which of explicit / generated / stationary / pure_add ran"* (`data/api.py:88`).
- **The fact that decides it:** `derive.phase_schedule` is **oracle-pinned**. `tests/test_derive.py` replays `_phases` at **60 cases, 0 mismatches**. So D2 cannot be implemented by changing the generator; a second generator inside DATA that shadows `derive`'s is the two-defaults L1 defect. `data/levers.py:337-350` says the same thing and is correct.
- The generator cannot produce pure-add anyway: `derive.py:680-684` states *"THE LAST PHASE EXCLUDES AT LEAST ONE AREA whenever `n_areas > 1`"*, because `faded` is read off the last phase.

**The options**

| | cost | buys |
|---|---|---|
| (a) last entry of `DATA.areas` is the arriving area; the resolver **generates** pure-add | makes area ORDER load-bearing with nothing stating it; and it collides with `phase_sched=""`, which already means *generate the rehearsed sliding window* — empty cannot mean both | one general rule at any n, no new lever |
| (b) infer from `CKPT.resume` | a cross-package read of a value DATA does not own — and it is also the **wrong signal**: a resume with an unchanged area list is not an add | nothing |
| (c) the launcher writes the schedule; the resolver only **names** what it was handed | D2 stays a *harness* default rather than a *lever* default, and that has to be said out loud | cannot be wrong; the protocol name reaches the Sample immediately |

**Recommendation**
**(c) now — and (a) is very likely never needed**, which is where I depart slightly from the written *"(c) now, (a) later"*.

(c) is implementable today with **zero surface change**, because `Plan.protocol`'s four values can be assigned by **recognising** the schedule's shape rather than by generating it. The recogniser, stated so two P4 authors cannot disagree:

- `phase_sched` empty → `"generated"`.
- explicit, one phase, every area live → `"stationary"` (this is the PHASED=0 arm the merge owes, `data/levers.py:105-124`).
- explicit, `n_areas > 1`, every phase is the same single area → `"pure_add"`.
- explicit, anything else → `"explicit"`.

That needs no area ordering, no new lever, no new argument and no signature. It closes exactly the gap D2 opened: the protocol name on the Sample.

The residual, and it should be stated rather than implied: under (c) a run that sets nothing still gets the **rehearsed** sliding window, so *"D2 makes PURE_ADD the default protocol"* is true of `longrun.sh`, not of `DATA_PHASE_SCHED`. That is the honest state and it belongs in `docs/02_OPERATIONS.md`. It is also the *right* state: `data/levers.py:344-350` argues that the two arms disagreed 10× on the same toy (+0.046 HELD rehearsed vs +0.444 WORSE pure), so a default that silently picks one is a result the report cannot attribute. (a) would install exactly that silent default.

**Why it fits the framework**
The recogniser reads only DATA's own resolved schedule and its own area count — no cross-package read, no wire, no argument, no signature. It leaves `derive.phase_schedule` untouched, which is required: 60 oracle cases pin it, and `spine.derive` is the shared named-function surface, not a place a package's protocol ruling may land. (b) is refused by the ownership spine on its face. (a) would either re-point `phase_sched=""` at a second generator (two meanings for one default) or add a generator inside DATA that shadows `derive`'s (L1).

**What changes**
- `src/data/api.py:77-100` — `data_plan`'s docstring gains the four recogniser predicates **verbatim**, next to the existing `Plan.protocol` sentence, plus `data.protocol_named` in `DID IT FIRE`.
- `docs/04_CONTRACT.md:955-963` — record (c) as adopted and (a) as not needed.
- `docs/02_OPERATIONS.md` — state that pure-add is a launcher configuration, not a default.
- **No frozen signature moves. No change to `spine/derive.py`.**

**Confidence** High. The oracle-pinning is quoted from a run, the harness expansion is quoted from `longrun.sh`, and the recogniser needs nothing the tree lacks.

**Literature** Bears only obliquely and I did not lean on it. The continual-learning literature does establish that rehearsal confounds a forgetting measurement — which is `longrun.sh:921-926`'s own argument, already in the tree with a measured 10× disagreement. It has nothing to say about *how a protocol name is produced by a resolver*, which is what the question actually asks.

---

## Q-DATA-8 — steps per epoch, and what a "window" is measured in

**What I read**
`docs/04_CONTRACT.md:975-983`; `src/spine/units.py:1-24` and the `Clock` class; `src/spine/compose.py:1821-1861` (`_run_windows`), `:1863-1875` (`_windows_in_epoch`), `:390-409` (the `segment` row), `:512-531` (`clock`/`epoch0`), `:643-659` (stage E), `:1092-1102` (`bench_summary`), `:1592-1605`; `src/spine/derive.py:286-320` and `:347-392`; `src/data/levers.py:92-101`, `:311-321`; `self_organize.py` — every one of the 20 `STREAM_LEN` sites, plus `:4317`, `:4719`, `:5656`, `:6236-6237`, `:6339`, `:7319`.

**What is true today — and the question's summary is partly wrong, which matters**

The *repair* is already in the tree and is correct:
- `compose.py:1873`: `return max(1, len(sysm.segmentation.ids) // int(sysm.configs["LM"].ctx))`.
- `compose.py:1860`: `return units.Windows(_windows_in_epoch(sysm) * int(sysm.configs["RUN"].epochs))`.
- The typing is enforced at both consumers, verified by opening them: `derive.py:318-320` (`cadences_that_cannot_fire`) and `derive.py:383-385` (`opt_steps_from_windows`) each `raise UnitError` when `type(run_windows) is not Windows`.
- `units.py` settles what a window is: `Windows` = *"Stream windows. What `step` counts"*, `Steps` = *"Optimizer steps. What the LR schedule's horizon is denominated in, and nothing else"*. `compose.py:512-525` names **one clock and four spellings** (`step`, `step_windows`, `now`, `epoch`). Q-DERIVE-1 already re-typed `pin_tick` to `Windows`, and `tests/test_derive.py` replays `pin_tick` at 32 cases OK. **The unit question is settled; only the confirmation is open.**

**The claim that does not survive checking.** The question says the byte-over-token form is *"which the LR horizon and every ETA were computed from"*. Grepping all 20 `STREAM_LEN` sites:
- The **runtime LR horizon** and the ETA both go through `_project` (`self_organize.py:6338-6362`), whose `_per = max(1, len(stream) // WIN)` (`:6339`) and `_total_steps = EPOCHS * (len(stream) // WIN)` (`:6236`) use **`stream`, the TOKEN stream** — `byte_stream` is the separate byte one (`:5656` computes `len(byte_stream) / len(stream)` as the measured bytes/token). So the LR horizon was **already token-measured**.
- `STREAM_LEN // WIN` survives in exactly **two** live places: the pre-run `[probe]` ETA banner (`:4317`) and one **live cadence period** — `_due("lmcurve", max(1, (STREAM_LEN // WIN) // 8))` at `:7319`, the LM curve probe. `:4719` is a prose comment.

This matters for P4 direction: the LR horizon's real defect is a *different* one — the shrinkage projection at `:6338-6362`, which `compose.py:1845-1850` already flags as Q-OPT-5. Sending an implementer to fix a byte/token bug in the horizon would send them to the wrong function.

The other half of the question is right as written: *"a window is WIN bytes"* is true only at `tok.mode="bytes"` (where a token **is** a byte) and false on `fixed`/`online`, where the overstatement is the compression ratio (~2.5× at a grown vocabulary).

**The options**

| | cost | buys |
|---|---|---|
| (a) confirm what is written — `run_windows` measured from the segmentation that exists, `Windows`-typed | none; it is the current code | the count is a measurement; the byte form becomes unrepresentable |
| (b) keep a byte-derived estimate anywhere (e.g. a ported probe banner) | the same ~2.5× overstatement, now in a banner an operator sizes a multi-day run from | a step count before tokenizing |
| (c) make `run_windows` a build-time wire or lever | **refused, structurally**: `bytes_per_token` is measured after `build()` freezes. `compose.py:1825-1834` gives the rejection, and `tests/test_census.py`'s `("encoder","SIG_WIN")` departure gives the identical one for the SIG width | a number readable at startup |

**Recommendation**
**(a) — confirm**, with one addition the question does not name: **the ETA must be computed from the same `_windows_in_epoch`**, i.e. after the epoch-0 segmentation exists, never from `stream_bytes // ctx`; and the report line must print `stream_bytes`, `len(Segmentation.ids)`, the measured `bytes_per_token`, `windows_in_epoch` and `run_windows` **together on one line**, so the ratio is checkable by eye. `RUN.bench_summary` already takes `bytes_per_window = LM.ctx × Segmentation.bytes_per_token` (`compose.py:1095-1096`); this is that line plus two numbers and one division.

**Why it fits the framework**
The unit type is what makes the wrong form unrepresentable rather than merely discouraged: `_run_windows` returns `units.Windows`, `stream_bytes` is `U.BYTES` metadata, and `Windows` is not constructible from a byte budget by anything in `derive`. Both consumers refuse a bare int with a message naming the reason (`derive.py:318`, `:383`). The wire route is closed by the freeze rule and closed *twice*, on two independent grounds that `compose.py:1824-1834` is careful to separate. And the DID-IT-FIRE discipline is what forces the printed line: a step count 2.5× the truth is invisible unless the three numbers appear together — an ETA alone reads as an ETA.

**What changes**
- `src/spine/compose.py:1821-1861` — correct the docstring's account of the old tree: the byte//token form was the `[probe]` banner (`:4317`) and the `lmcurve` cadence period (`:7319`), **not** the LR horizon, which used `len(stream)//WIN` at `:6236`/`:6339`. As written it will send a P4 author hunting a horizon bug that belongs to Q-OPT-5.
- `docs/04_CONTRACT.md:975-983` — the same correction, and mark the confirmation given.
- `src/spine/compose.py:1092-1102` — `bench_summary`'s row note gains the three-number line.
- **No frozen signature moves.**

**Confidence** High. `_windows_in_epoch` and `_run_windows` were read line by line, both `UnitError` raises were opened, and the old-tree correction rests on an exhaustive grep of all 20 `STREAM_LEN` occurrences plus `:5656` establishing that `stream` is the token stream.

**Literature** NOT APPLICABLE. This is internal unit consistency; no paper can say what `step` counts in this tree. (LR-schedule *indexing* is a real literature question, but it is Q-OPT-2's, in another slice.)

---

## Q-TOK-3 — does `dropout` reach the training stream, or only the build tallies?

**What I read**
`docs/04_CONTRACT.md:984-995`; `tokenizer.py:183-200` and `:386-400`; every `.segment(` call in `self_organize.py` and `tokenizer.py`; `src/tok/api.py:91-125` (`tokenize`) and `:41-88` (`build_vocabulary`); `src/tok/levers.py:399-414` (`dropout`); `src/spine/compose.py:120-125`, `:390-409`, `:643-655`, `:1596-1605`.

**What is true today**
The diagnosis is exactly right, and the repair is **already written**.

Verified in the old tree:
- `tokenizer.py:183` `def segment(self, blist, count=True, dropout=None)`; `:187` `p = (self.dropout if dropout is None else dropout) if count else (0.0 if dropout is None else dropout)`; `:193` `if p and random.random() < p: continue` — the **process-global** `random`.
- The only `count=True` call anywhere is `self_organize.py:1264` — the build pass. Every other segmentation is `count=False`: `:1286` (final deterministic), `:3241`, `:3900`, `:4093` (**the training stream**), `:9679`. The wrapper `seg()` defaults `count=False` (`tokenizer.py:389` and `:394` — it is defined twice, second wins). So at `mode="online"` the regularizer runs during the seed build and **never again**, while the lever's purpose says it exists *"so byte-level material still reaches the tally"*.

Verified in the rebuild — option (b) is already in the frozen surface:
- `src/tok/api.py:91`: `def tokenize(tok, vocab, data, labels=None, *, start=0, regularize=False, seed=0)`.
- `:108-113`: *"`regularize=True` applies `tok.dropout` … it is used for the TRAINING stream and never for held-out text, generation, or the final segmentation, which must be deterministic. THE SKIP TEST ABOVE IS DISABLED WHENEVER `dropout > 0`."*
- The root passes it: `compose.py:1602` (`regularize=True`) for epoch 0, and the rows at `:391` and `:644` for the per-epoch segmentation.
- The RNG defect is already repaired: `"tok.dropout"` is a declared subsystem (`compose.py:124`), so the process-global draw is gone.

So Q-TOK-3 is a **confirmation request on written code**, not an open choice. Every record in the project was taken at `dropout=0.0`, where (a) and (b) are identical, so the claim that nothing measured moves holds.

**The options**
(a) keep the tally-only semantics and Gate-declare the regularizer unreachable after the build — faithful, and admits the lever has never run and structurally cannot at `mode="online"`.
(b) apply it to the training-stream segmentation — what BPE-dropout is for, and what the tree writes.

**Recommendation**
**(b) — confirm**, with two consequences that P4 must be told and the contract does not state:

1. **The run length becomes a function of the dropout draw.** With `regularize=True` on the epoch-0 and every-epoch segmentation, `len(Segmentation.ids)` — and therefore `_windows_in_epoch`, `_run_windows` and the LR horizon — are stochastic in the `tok.dropout` stream at `dropout > 0`. That is acceptable because it is **measured, not estimated** (Q-DATA-8's whole point), but `draw_stream`'s invariant *"two arms differing in one unrelated knob still read the same text at epoch 2"* (`data/api.py:150-156`) is a statement about **bytes** and does not extend to tokens. Say so, or the first person to compare two `dropout>0` arms will read a length difference as a bug.
2. **`bytes_per_token` is measured with dropout applied.** `build_vocabulary` (`tok/api.py:62-64`) measures it over the *counting* segmentation, which applies `tok.dropout`. More, shorter tokens → a lower bytes/token → a different `derive.signature_width_bytes` for SIG and a different `data.splice_window` gate threshold. Both take the measured value and so follow correctly, but the fact that the SIG width moves with a TOK regularizer belongs in the docstring.

**Why it fits the framework**
`regularize` is already a frozen parameter, so (b) costs nothing; (a) would require **removing** it, which is a signature change in the expensive direction. The determinism rule the whole design rests on — *"a re-segmentation whose match table has not moved is REFUSED and counted as `tok.retok_noop`"* — is unsound under dropout, and `tok/api.py:110-113` already disarms it correctly and says why. The DID-IT-FIRE surface already distinguishes the states: `tok.dropout_skip` is declared *"unreachable at dropout=0.0, the default"*. And the RNG rule is honoured: the draw comes from `rng_for("tok.dropout", seed)`, a declared subsystem, so `rng.issued()["tok.dropout"].draws == 0` reads as armed-but-inert rather than as silence.

**What changes**
- `src/tok/api.py:108-113` — add the two consequences above.
- `src/tok/levers.py:399-414` — the *"IT CARRIES ONE HARD REQUIREMENT"* paragraph can be marked satisfied (`compose.py:124`).
- `docs/04_CONTRACT.md:984-995` — mark the confirmation given.
- **No frozen signature moves.**

**Confidence** High. Every call site was enumerated; the rebuild's parameter and the root's three call sites were read.

**Literature — it bore here, and it is decisive.**
Provilkov, Emelianenko & Voita, **BPE-Dropout: Simple and Effective Subword Regularization** (ACL 2020, arXiv:1910.13267). The method is defined as stochastically corrupting the segmentation procedure so that *multiple segmentations* are produced within one fixed BPE vocabulary, and the reported protocol is **BPE-dropout during training, standard deterministic BPE at inference** — up to +2.3 BLEU over BPE. That is `tok/api.py:108-110`'s rule word for word. Under (a) the lever would be a tally-time-only device the literature has no name for and which, at `mode="online"`, is inert after the seed build. The literature does **not** override anything here — it happens to agree with what the framework already permits, which is the cheap case.

Source: [BPE-Dropout: Simple and Effective Subword Regularization](https://aclanthology.org/2020.acl-main.170/)

---

## Q-TOK-9 — `build_passes` had a per-arm default (2 online, 8 offline)

**What I read**
`docs/04_CONTRACT.md:996-1002`; `src/tok/levers.py:275-289` (`build_passes`), `:291-303` (`build_bytes`), `:36-42`; `src/tok/api.py:41-88`; `self_organize.py:1223-1228`; `src/fabric/levers.py:104`, `src/domains/levers.py:166`, `src/opt/levers.py:499`.

**What is true today**
- `self_organize.py:1225` is exactly as quoted: `_passes = _i("SEED_PASSES", 2) if TOK_ONLINE else _i("GROW_PASSES", 8)`. One quantity read on opposite sides of a ternary, so exactly one name is reachable per run and the other is reported as an operator typo.
- `src/tok/levers.py:275` declares `build_passes = Lever(2, ...)`, and `:284-289` says the 8 *"carries over as the 'fixed' arm's declared target inside this package's build code"* and *"must NOT come back as a second lever"*.
- **The two frozen surfaces disagree.** `src/tok/api.py:57` says, with no arm branch: *"Otherwise: `tok.build_passes` tally-and-mint passes over `b"".join(h[:tok.build_bytes] for h in area_heads)`"*, and `:75` lists `build_passes` once in `LEVERS READ`. `:49-51` describes the three `mode` arms and mentions passes on none of them.

So a P4 author reading `levers.py` writes `passes = 8 if mode == "fixed" else tok.build_passes`; one reading `api.py` writes `passes = tok.build_passes`. Two readings, different code, and a different `tok.v0` on the arm that carries the project's largest recorded effect (4.364 vs 2.175 b/B).

**The options**
(a) one literal (2) on both arms, plus a startup line recommending `TOK_BUILD_PASSES=8` at `mode="fixed"`.
(b) keep the 8 inside the build code — a second literal in a second place.
(c) two levers — the state the census merge removed; N1 has one row (`SEED_PASSES → TOK_BUILD_PASSES` absorbing `GROW_PASSES`), so a second lever needs a second row.
(d) make it a derived value — **not available**: it would be a TOK→TOK edge, and `d_` is the *cross*-package namespace. `data/levers.py:355-360` states the rule for the identical case (`seg_contig`): *"`d_` is the CROSS-package namespace, `lever.py` refuses a `d_`-named lever, and an intra-package derivation would enter the coupling graph as an edge from DATA to DATA."*

**Recommendation**
**(a)**, and the deciding fact is mechanical rather than aesthetic: **`docs/04_LEVERS.md` is generated from the registry.** `fabric/levers.py:104`, `domains/levers.py:166` and `opt/levers.py:499` all say so — the last one explicitly: *"`docs/04_LEVERS.md` reads the default off the registry instead of retyping it."* An 8 living in build code therefore prints as **2** in the operator's only reference, for the arm where it is wrong. That is the L1 failure the merge exists to end, moved from a second environment name into a second literal.

Two refinements:
- The startup line must be a **declared Gate with its predicate**, not a warning: on `mode="fixed"` it prints `build_passes=2; the offline build historically used 8 — set TOK_BUILD_PASSES=8 to reproduce it`; on the other arms it prints `unreachable (mode != fixed)`. Advice that only appears sometimes and says nothing when it does not is the armed-but-inert shape applied to prose.
- The recommendation belongs on P9's list of numbers that moved, because a `mode="fixed"` run at 2 passes is not the offline build of record.

**Why it fits the framework**
L1 is the rule: one declaration, one place. The Lever carries one default by construction, and the arm-dependence is real, so the honest resolution is to keep the default honest and make the arm-specific advice **visible** rather than to hide a second number where the generated doc cannot reach it. `docs/04_CONTRACT.md:220-226` already has the precedent for the reporting shape: five DATA levers are *"arm-dead under `source="synthetic"`"* and that is *"a declared arm reported through a Gate, not an unread lever."* This is the same construction one package over.

**What changes**
- `src/tok/levers.py:284-289` — **delete** *"so 8 carries over as the 'fixed' arm's declared target inside this package's build code"* and replace it with: there is ONE literal, 2; the offline build's 8 is a printed recommendation, not a second default.
- `src/tok/api.py:41-88` — `build_vocabulary`'s `DID IT FIRE` gains `Gate tok.build_passes_advice` with its predicate.
- `docs/04_CONTRACT.md:996-1002` and P9's moved-numbers list.
- **No frozen signature moves.**

**Confidence** High. `self_organize.py:1225` was read; both rebuild surfaces were read; the "generated from the registry" claim is quoted from three separate levers files.

**Literature** NOT APPLICABLE. How many merge passes a BPE build takes is corpus-dependent and this is a question about where one literal lives, not about what it should be.

---

## Q-TOK-10 — `TOK.save_vocabulary` takes no suffix, so M46 is not closed

**What I read**
`docs/04_CONTRACT.md:1203-1216`; `src/ckpt/api.py:83-101` (`save`), `:16-23` (record types), `:195-208` (`new_retention`), `:210-250` (`Retention`); `src/tok/api.py:41-88` (`build_vocabulary`), `:275-287` (`save_vocabulary`), `:288-310` (`vocab_state`), `:312-322` (`restore_vocab`); `src/spine/assemble.py:845-876` (both path couplings); `src/spine/compose.py:308-329` (the TOK assembly rows), `:964-1048` (the C fan-out).

**What is true today — and it is one step worse than the question states**
- `ckpt/api.py:83`: `def save(ckpt, *, payload, geometry, step, epoch, reason, suffix="")`; `:91-99`: *"THE SUFFIX APPLIES TO THE WHOLE SNAPSHOT … A SNAPSHOT'S VOCABULARY IS PART OF THE SNAPSHOT: the tokenizer bytes go in `payload`."*
- `tok/api.py:275`: `def save_vocabulary(tok, vocab)` — no suffix; it writes `d_vocab_save_path`, frozen at `build()`.
- `assemble.py:848-850`: `d_vocab_save_path = CKPT.dir + ".dyntok.json"`. `assemble.py:864-866`: `d_vocab_read_path = CKPT.resume + ".dyntok.json"`.
- `tok/api.py:288-291` (`vocab_state`): *"Everything a resume needs **that the merge list alone does not carry**"* — explicitly **not** the merges.
- `tok/api.py:52-56` (`build_vocabulary`): *"If `d_vocab_read_path` is non-empty and exists, the parent's merges are REPLAYED instead of built."* `compose.py:326-329` confirms the ordering: `restore_vocab` runs **after** `build_vocabulary` *"has replayed the parent's merges from `d_vocab_read_path`"*, and its refusal *"compares the state's merge count against the vocabulary that was just built."*

So the resume's merge source is **the file**, not the payload — which the contract's option (a) does not account for. And the consequence in the **new** tree is worse than an overwrite: resuming from a `.bestN` snapshot sets `CKPT.resume` to that snapshot's base, so `d_vocab_read_path` resolves to `<base>.best3.dyntok.json` — **a file nothing ever writes**, because `save_vocabulary` always writes `<base>.dyntok.json`. `build_vocabulary` then falls through to *"Otherwise: build"*, and the restored embedding table is indexed by a freshly-minted, different vocabulary. M46 is not merely open; the best-snapshot resume path **cannot work at all**.

**The options**

| | cost, priced honestly | buys |
|---|---|---|
| (a) merges travel in `payload["TOK"]`; `save_vocabulary` becomes a human-readable sidecar | **not "one sentence in `vocab_state`".** `build_vocabulary`'s merge source has to move from the wire-supplied file to the payload, and the payload is not one of its arguments — so either `build_vocabulary` gains `saved=None` (**a signature change**) or `restore_vocab` is re-chartered from *"refuse on mismatch"* to *"install the match table"*, which throws away a full corpus build and leaves `bytes_per_token` measured on a vocabulary that was then replaced. It also strands `d_vocab_read_path`, half of a promote the census made on purpose | the snapshot becomes self-contained, which is what `ckpt/api.py:91-99` already claims |
| (b) `save_vocabulary(tok, vocab, *, suffix="")` | **one frozen signature moves** | M46 closed; ownership of the merges unchanged; `<base>.best3.dyntok.json` now exists, so resuming from a best snapshot works — which today it cannot; `d_vocab_read_path`'s compute is already `CKPT.resume + ".dyntok.json"`, so the read side becomes symmetric with no edit at all |
| (c) refuse `best_keep > 0` with `mode == "online"` at startup | forbids best-checkpoint retention on exactly the arm goal B's headline runs use | correct in that the overwrite is harmless at `mode` in {`bytes`,`fixed`}, where the vocabulary never moves after the build |

**Recommendation**
**(b)** — and this is one of two places where I disagree with the written recommendation. Four reasons, the first structural:

1. **The framework rule decides it.** The suffix is chosen **at runtime** by the retention policy — `BestAction(save_best, rotate_slot)` (`ckpt/api.py:23`, `:213`). A coupling's compute sees only frozen Configs, so `d_vocab_save_path` **structurally cannot** carry it. A runtime value reaches a package as an **argument**. That is the identical rule that made `bytes_per_token` an argument to `data_plan` and `curve_bpb` an argument to `Retention.consider` (`ckpt/api.py:215-219`). `save_vocabulary` is the only entry point in the C fan-out that writes a file and does **not** receive the runtime value that names it.
2. **(b) is the smaller change, measured.** (a) moves a merge source across a wire boundary and re-charters two docstrings; (b) adds one keyword-only parameter with a default.
3. **Cheap now, expensive later.** 116 of 121 entry points are stubs and P4 writes against the list. This is one line in `docs/04_CONTRACT.md` §7 and one in `src/tok/api.py:275`. **LOUD: THIS IS A CHANGE TO THE FROZEN SIGNATURE SET, and K1 compares the document against the tree in both directions, so both edits must land in the same commit.**
4. **It also closes the half the question does not mention** — the non-existent `.bestN` vocabulary file — with no further work, because the read coupling already concatenates the whole `CKPT.resume` string.

**Keep (a)'s sentence anyway, as reporting.** The live defect is that **two frozen docstrings disagree about where a snapshot's vocabulary lives**, and that is true regardless of which option wins. Under (b) the fix is to correct `ckpt/api.py:96-99` — the tokenizer's *file* travels under the snapshot's suffix; the payload carries what `vocab_state` declares — rather than to move the bytes. If the owner rules that a snapshot must be **self-contained** (a checkpoint plus a sidecar is two artifacts one `cp` can separate), then (a) wins and its full cost above must be paid; I have named it so the choice is priced.

**What changes**
- **`src/tok/api.py:275` — FROZEN SIGNATURE CHANGE:** `def save_vocabulary(tok: Config, vocab, *, suffix="")`, docstring stating the suffix applies for the same reason `CKPT.save`'s does.
- `docs/04_CONTRACT.md` §7 (the normative signature list) and the TOK table — same commit, or K1 fails.
- `src/spine/compose.py:1039-1043` — the C row currently says *"It takes no suffix, so a `.bestN` snapshot still overwrites the base vocabulary file — M46 is NOT closed by this row"*: replace with `(vocab, suffix)` and the source of the suffix.
- `src/ckpt/api.py:96-99` — correct the *"the tokenizer bytes go in `payload`"* clause to match what `vocab_state` actually declares.
- **No wire changes.** Both path couplings stand exactly as they are.

**Confidence** Medium-high. The mechanics are all verified by reading. What would raise it to high: the owner's ruling on snapshot self-containment, which is the only consideration that flips this to (a).

**Literature** NOT APPLICABLE. Checkpoint-artifact layout in this tree; no paper bears.

---

## Q-TOK-11 — `residual_ratio` is sourced at mint time, when it is zero by construction

**What I read**
`docs/04_CONTRACT.md:1217-1231`; `src/tok/api.py:210-244` (`judge_probation`, with the `RECEIVES` clause at `:231-234`), `:154-208` (`mint_burst`); `src/tok/levers.py:415-445`; `src/lm/api.py:23` (record types), `:203-234` (`anchor_term`), `:236-276` (`on_mint`, with the residual sentence at `:260-261`), `:331-347` (`counters`), and the full entry-point list at `:29,69,114,148,180,203,236,277,300,331`; `self_organize.py:7595-7612`.

**What is true today**
The diagnosis is correct in every part.

- `tok/api.py:210`: `def judge_probation(tok, vocab, *, step, appearances, residual_ratio=None)`; `:216-221` the embed arm keeps a token iff `earned AND residual_ratio[t] >= tok.probation_residual`; `:231-234` sources it from *"LM's `MintReport` (‖delta[nid]‖ / ‖composite[nid]‖)"*.
- `lm/api.py:236` `on_mint` runs **at the mint**, and `:260-261` confirms `MintReport.residual_ratio` is produced there. At that instant the composer's `delta` is the freshly-initialised residual — zero by construction under every `new_row_init` arm — so `>= probation_residual` fails for **every** candidate and the arm retires 100%.
- The old tree does it right, verified at `self_organize.py:7600-7605`: it recomputes at **judgement** time from `model.compose.table()` and `.delta`, once per pass, with the comment *"the embedding test still requires the token to have been TRAINED: a residual that is near zero because the token was never seen says nothing about the merge."*
- **No producer exists.** LM's ten entry points are `resolve, build_model, encode, decode, lm_loss, anchor_term, on_mint, state_dict, load_state, counters`. `counters` returns `{name: int}` (`:332`), not a per-token float vector. Nothing returns a live residual read. Confirmed by enumeration, not by grep alone.
- **Not in the question and load-bearing:** `LM.anchor_term` (`lm/api.py:203-206`) already computes exactly this quantity every flush — it *"holds a newly minted token's residual near its byte composite"*. So option (a) is not new machinery; it is **exposing a read the package already performs**.

**The options**
(a) add `LM.residual_ratios(lm, model)` — a pure read, no grad, no side effect. A signature-**set** change (a 122nd entry point).
(b) cache the last `MintReport` — this is the bug restated.
(c) leave `residual_ratio=None` and print the declared Gate *"unreachable (no residual_ratio supplied)"*.

**Recommendation**
**(a) now, with (c) permanently as the fallback** — a small departure from the written *"(a) when the surface opens, (c) until then"*, because **the surface is open right now**. 116 of 121 entry points are stubs, LM's bodies are unwritten, and a 122nd entry point costs one stub, one row in `docs/04_CONTRACT.md` §7, one row in `LOOP_ORDER`. After P4 it costs a coordinated edit across ten independent agents.

(c) is not an alternative to (a) — it is required **alongside** it, because `residual_ratio` legitimately has no value at `lm.compose == False` (there is no composer to read), and ISSUES M41 is the record of what happens when the embed arm silently runs the `use` test while the banner says `embed`. The Gate must print either way.

Shape the entry point must have, so P4 does not guess: it returns a value indexed the same way `appearances` is (a `vocab_slots`-length vector, or `None`); it returns `None` when `lm.compose` is False; its `DID IT FIRE` is `lm.residual_read` / `Gate lm.residual_unreachable (compose off)`.

**Why it fits the framework**
`residual_ratios` is LM's own read of LM's own tensors, handed to TOK as an **argument** assembled by the root. That is precisely the idiom already in the contract — `MEM.write(key_fn=...)`, `DOM.rekey(encode=...)` — and it crosses no import boundary. It cannot be a wire, for the reason `tok/api.py:233-234` already gives and which is the same one that refused `EVAL.d_holdout_bytes` and the SIG width: it is read off a live tensor after `build()` freezes. Under `K6`, the new entry point needs a row or a `DEFERRED_ENTRY_POINTS` entry; a row is available and correct — stage **B**, immediately before `TOK.judge_probation`, whose row (`compose.py:940-948`) already notes that *"two of its three inputs are flush-side: the counter this flush's batch just updated, and `residual_ratio`, read off live model tensors and defaulted, so no check asks about it."* Adding the producer converts that acknowledged blind spot into a K10-checked argument.

**What changes**
- **LOUD: THIS ADDS AN ENTRY POINT TO THE FROZEN SET (121 → 122).** `docs/04_CONTRACT.md` §7 and the §LM table, plus `src/lm/api.py` (new stub, `LEVERS READ: compose`), **in the same commit** — K1 compares both directions.
- `src/spine/compose.py` `LOOP_ORDER` — a **B** row for `LM.residual_ratios(model)` immediately before `TOK.judge_probation`, `produces` column spelling it `residual_ratio` (the consuming name).
- `src/tok/api.py:231-234` — correct the `RECEIVES` clause: it is LM's judgement-time read, **not** the `MintReport`.
- `docs/04_CONTRACT.md:1217-1231` — record the ruling.

**Confidence** High on the defect and on the absence of a producer (enumerated). Medium on the disposition: `probation_uses` defaults to **0**, so the whole probation family is inert at the shipped default (`tok/api.py:239-241` declares all four counters unreachable there) — which is a fair argument that shipping (c) alone is survivable. The cost asymmetry is what tips it: (a) is cheap today and expensive after P4, and the arm is wrong-by-construction until it lands.

**Literature** NOT APPLICABLE to the ruling. The general question — whether a subword unit has *earned* its embedding — touches vocabulary-pruning work, but the question here is which of this tree's 121 entry points may return a tensor read, and no paper speaks to that. I did not search for one.

---

## Q-TOK-12 — which window's `Due` does the flush act on?

**What I read**
`docs/04_CONTRACT.md:1327-1336` and `:868`; `src/tok/api.py:127-153` (`on_window`), `:154-208` (`mint_burst`), `:210-244` (`judge_probation`), `:91-125` (`tokenize`); `src/spine/compose.py:773-786` (the A row), `:786-796` (`RunClock.advance`), `:927-953` (the B rows), `:1451-1468` (`System.due`'s comment); `src/tok/levers.py:214`, `:233`, `:425`, `:436`; `src/opt/levers.py:549`, `:579`.

**What is true today**
Live, undecided, and the tree says so in three places rather than deciding by accident — which is the right state, but it is now the last thing standing between P4 and the loop body.

- `TOK.on_window` is asked **per window**, once, with all four cadences (`tok/api.py:127-131`; A row at `compose.py:773-775`).
- `mint_burst`, the retok and `judge_probation` act **per flush** (B rows at `compose.py:927-953`).
- The carrier is declared: `System.due`, `compose.py:1457-1461` — *"asked PER WINDOW and acted on PER FLUSH by `mint_burst` / `judge_probation` / the retok. `batch_windows` of them reach one flush; which one wins is Q-TOK-12 and must not be decided by accident at a call site."*
- The cadence semantics that make (a) lossy: `on_window`'s docstring (`tok/api.py:138-141`) — *"`_due` RECORDS the step and returns True, so asking under a shared key CONSUMES the event."* The clock advances on the **ask**, so a Due that a flush discards is a fire that is silently gone.

**Sizing the two options, arithmetically.** Under (a) a Due survives only when the window that raised it is the last of its batch. With elapsed-since-fire cadences the fires land at multiples of the period, so the surviving fraction is `gcd(period, batch_windows) / batch_windows`:
- `grow_every = 200`, `batch_windows = 16` → `gcd = 8` → **half of all mints dropped**.
- `retok_every = 3000`, `batch_windows = 16` → `gcd = 8` → **half of all retoks dropped**.
- any period **coprime** with the batch (e.g. `grow_every = 201` at 16) → **15 of every 16 fires dropped**.

At the shipped defaults (`opt/levers.py:549`, `batch_windows = 1`) (a) and (b) are **identical** and no recorded result moves — the same structure as Q-OPT-2. The divergence appears at `fetch_big.py`'s own heavy-run command (`BATCH_W=16`).

**The options**
(a) the LAST window's Due — simple; drops up to `batch_windows - 1` fires, at the rates above.
(b) the OR over the batch — no fire lost; the flush acts on a cadence that fired mid-batch.
(c) hoist the three B-stage acts to A — puts a mint inside the accumulator and invalidates the batch the model is mid-flush on.

**Recommendation**
**(b)**, with three refinements P4 needs and the contract does not state:

1. **OR per cadence key, not one boolean.** `Due` has four fields and `frozen` is a **state**, not an event: `tok/api.py:145-147` says *"at `step >= tok.freeze_at` … `Due.frozen` is True from then on."* So OR `mint`, `retok`, `probation`; take `frozen` from the **last** window (it is monotone, so last == OR — saying so removes the ambiguity rather than relying on the reader noticing).
2. **Two counters, not one, and one of them must read zero forever.** `tok.due_merged` — a flush where more than one window in the batch raised the same key — and `tok.due_dropped`, which under (b) is **0 by construction**. Declaring a counter that must read zero is exactly the `fired / armed-but-0 / unreachable` distinction G4 requires, and it is the only way a later reader can tell which reading was actually implemented. Under (a) the same counter is the number that says what (a) cost.
3. **State the birth-step consequence.** `step` handed to `mint_burst` and `judge_probation` is `clock.step` at the flush (`compose.py:927`, `:940`), so under (b) a mint's birth step is flush-aligned while the Due that triggered it was raised mid-batch. `probation_deadline` compares `step - birth`, both `Windows`, so nothing raises — but the offset is up to `batch_windows - 1` windows and should be written down rather than rediscovered.

**Why it fits the framework**
The failure this entire cadence design exists to prevent is **the silent non-fire**, and `on_window`'s own docstring is the evidence: minting fired 999 times at `batch_w=1` and **zero** times at `batch_w` in {2,8,15,16,32} under a modulo cadence (`tok/api.py:133-137`), and a shared cadence key *"killed BOTH retok branches for three 18-epoch runs"* (`:138-141`). Option (a) reintroduces that same failure by a different route and at a computable rate. Option (b)'s cost — acting on a cadence raised up to `batch_windows - 1` windows earlier — is bounded latency against a `grow_every` of 200 windows, i.e. under 8% of one period at `batch_w=16`. It is also **consistent** with `judge_probation`'s other input: `compose.py:940-943` notes `appearances` is *"the counter this flush's batch just updated"*, so acting once per flush on the OR uses a counter covering exactly the windows the OR covers.

**What changes**
- `src/spine/compose.py:773-786` — the A row's `produces` note picks (b) and names both counters (it currently states both options and defers).
- `src/spine/compose.py:1457-1461` — `System.due`'s comment records the ruling.
- `src/tok/api.py:127-153` — `on_window`'s docstring states what the root does with `batch_windows` Dues, and `DID IT FIRE` gains `tok.due_merged` and `tok.due_dropped`.
- `docs/04_CONTRACT.md:1327-1336` and §3.10.
- **No frozen signature moves.** `Due` keeps its four fields; the OR happens in the root, which is the only place that can see a batch.

**Confidence** High. Every surface was read; the survival-fraction arithmetic follows from the elapsed-since-fire semantics `on_window` declares, and it is checkable by hand. The one thing I did not do is simulate it, which is what would raise it further — and it is a ten-line simulation P4 can run against the real `Cadences`.

**Literature** NOT APPLICABLE, and deliberately not searched. This is *"which window's Due does the flush act on"* — a question about this tree's own loop structure, and the brief names it as an example of what not to search for.
