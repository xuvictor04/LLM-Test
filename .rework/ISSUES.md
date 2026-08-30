# ISSUES — everything the survey found that needs addressing

Generated from `.rework/survey/`, 16 independent reader agents over rm-predict @ aee4a52.

**Status discipline.** Every entry below is an agent's claim with an evidence pointer. Three states:

- **CONFIRMED** — I read the source and verified it myself. Cited as fact.
- *(unverified)* — the evidence pointer is specific and plausible; it has NOT been checked. Treat as a
  lead, not a finding. Verify before acting, and before quoting it anywhere.
- **HISTORICAL** — found and fixed earlier in the project. Kept because the *bug class* recurs and the
  rebuild must not reintroduce it.

Counts: critical 58, high 122, medium 181, low 114 — 475 records total.

---


## PART 1 — OPEN, in the code as it stands

These came from reading the source. They are the work list for the rebuild.

### CRITICAL (12)

**C1. Six arm names resolve to a flag set identical to the shipped defaults — they are `base` under another name** *(unverified)*  
`armed-but-inert` · harness · longrun.sh:173 (vote), :174 (socloop), :269 (nogate), :278 (nocompose), :304 (nomem), :378 (gate_press)  
Each of these arms writes its own log, its own .cfg and its own row in the GRID/SEEDS summary, describing an experiment that was never performed: the child process receives environment values identical to the registry defaults, so the run is bit-identical to `base` at the same seed.

**C2. Load-balance loss is identically zero on the default routing path** *(unverified)*  
`armed-but-inert` · so-fabric · self_organize.py:2694 (soc-loop return) consumed at :7031  
FAB_BALANCE, BAL_WARM and BAL_FLOOR are read, printed in the config banner and reasoned about at length as the mechanism that keeps every expert receiving occasional traffic, but under CHAIN_ROUTE=soc (the shipped default) the quantity they multiply is a freshly allocated zero scalar with no graph, so the balance pressure is exactly 0.0 for the entire run and there is no DID IT FIRE row for it.

**C3. The leave-one-out counterfactual does not remove the expert on the default path** *(unverified)*  
`untrippable-guard` · so-fabric · self_organize.py:2618-2694 (soc-loop ignores ban1); called from :6991  
fab.contrib -- the marginal-contribution signal that gates both cull-spare rules and picks replication parents -- is measured by re-walking with ban1 set. The soc-loop never applies ban1 to any logit, so the walk is bit-identical for every candidate; the same number is written to contrib for every expert measured, carrying zero information about which expert matters.

**C4. _eval_sig builds the eval signature from ONE BYTE at the default SIG_WIN=0** **[CONFIRMED]**  
`unit-mismatch` · so-model · self_organize.py:3919 (vs the training width at 5675-5680, 6646)  
On the default configuration (SIG_SPACE=bytes, TOKENIZER=1, EVAL_GIST=1, SIG_WIN=0) every eval window's routing gist is encoded from the LAST SINGLE BYTE of the decoded window, while training encodes a >=256-byte window from the window's start. The router is scored at eval against centroids built in an incommensurable space, so every held-out/retention/boundary number is produced by a router that is routing on one byte.

**C5. Every eval-path signature is built from ONE BYTE: `_eval_sig` uses SIG_WIN raw, whose default 0 becomes max(1,0)=1** **[CONFIRMED]**  
`unit-mismatch` · so-report · self_organize.py:3919 (read by _eval_logits at 3934, consumed throughout 7900-8205)  
On the default config (SIG_SPACE=bytes, TOKENIZER=1, SIG_WIN unset), `_eval_sig` decodes each eval window back to bytes and then keeps only the last `max(1, SIG_WIN)` = 1 byte before encoding it. Every held-out and retention figure that goes through `_eval_logits` therefore routes the fabric on a signature derived from a single byte of context, while training routed on a `_sigw`-byte window (`_sigwidth()` returns max(WIN, WIN*bytes_per_token) when SIG_WIN==0). The router is not blind — the zero-gist fallback that `_eval_sig` was written to replace — but it is near-blind, and nothing in the report says so. Affected: MEMORIZATION CHECK (train and held-out), ANCHORS' THIS MODEL, RETENTION, LEARNING CURVE / `_CURVE`, `holdout_bpb` and hence ACROSS THE RUN BOUNDARY / BWT / F / the checkpoint's stored baseline, and CAN A DOMAIN PREDICT's model term.

**C6. A newly grown dynamics predictor is soft-culled in the same block that created it** *(unverified)*  
`armed-but-inert` · subsys · world_model.py:121-127 (soft_cull) driven by self_organize.py:6768-6772  
grow() appends a predictor and never initialises its mass; soft_cull runs immediately afterwards in the same MANAGE_EVERY block and culls anything with mass < 1e-3. mass is a zeros buffer sized nmax and grow() does not touch it, so the newborn is at 0.0 and is deactivated before update_fitness has ever seen it. The world-model population therefore cannot actually grow in the product loop: world.grow's DID IT FIRE row counts a mint that was undone microseconds later, and the eval line's '(n live)' is the only place the discrepancy surfaces.

**C7. probe_signature.py cannot complete on its default settings: the `frozen` control crashes on an undefined name** *(unverified)*  
`crash` · tools · probe_signature.py:415-427 (control loop) -> self_organize.py:3259  
With SWEEP on (the default, PROBE_SWEEP=1) the run reaches the second control and dies with `NameError: name 'FROZEN' is not defined. Did you mean: '_FROZEN'?`. The bigram control has already printed; the learned-encoder sweep (c), the separation curve (e), the drift probe and the entire verdict() never run. The file's headline question — 'if a trivial featurizer separates the corpora and the learned encoder does not, the encoder is the problem' — cannot be answered because the run dies between the two halves of that comparison.

**C8. prompt.py's memory blend is the exact ungated 50/50 mix that self_organize.py fixed — measured hp is identically 1.0** *(unverified)*  
`unit-mismatch` · tools · prompt.py:154-162 (mem_dist) and prompt.py:212-215 (the blend)  
MEM=1 always takes exactly 50% of the probability mass from retrieval, however bad the nearest neighbour. `hp = dm.sum().clamp(max=1.0)` is meant to gate on match quality, but mem_dist scatters a softmax, so the sum is exactly 1.0 by construction. This is the same defect self_organize.py documents and fixed with MEM_GATE/MEM_CONF0/MEM_W ('hp was therefore identically 1.0 and this was an UNCONDITIONAL 50/50 mix at every position ... memory measured NET-NEGATIVE at every store size'). prompt.py is the tool the deliverable — generations — is read with, and it never got the fix.

**C9. cl_bench.py's memory arms use the same ungated 50/50 mix and bind `conf` only to discard it** *(unverified)*  
`unit-mismatch` · tools · cl_bench.py:159-163 (bpb)  
Every 'weights + memory' number this testbed produces — the whole editable-memory thesis, both key modes, both forgetting arms and the wrongness recovery — is measured with retrieval taking a fixed LAMBDA share regardless of match quality. `dist, conf, hit, w = mem.read(...)` binds conf and never uses it; `hp = pmem.sum(-1)` is 1.0 whenever the store has a valid entry. In my run the memory arms came out WORSE than weights-only (+1.003 and +1.360 vs +0.495), which is exactly the signature self_organize.py attributes to this bug.


**C10. `import memory` from the repository root returns the OLD system's 654-line module, not `src/memory/`** **[CONFIRMED]**  
`silent-overwrite` · rework · ./memory.py vs src/memory/ ; measured 2026-08-29  
`PYTHONPATH=src python3 ...` from the repository root — the natural invocation, and the first one tried — puts the ROOT ahead of `src` on `sys.path`, because PYTHONPATH lands after the script's own directory. `import memory` therefore resolves to the legacy `./memory.py` and not to `src/memory/`, silently, with no error and the wrong module's globals. It surfaced only by luck: the old file has no `levers` attribute, so `import memory.levers` raised `'memory' is not a package`; a plain `import memory`, or an old file that happened to carry the attribute, succeeds and returns the wrong system. None of the ownership checks can see this — O1 through O10 parse `src/` with `ast` and never ask which file a name resolves to. `src/data/` survives the same collision with the tracked `./data/` only because it has an `__init__.py` and a regular package outranks a namespace package found earlier; measured both ways, and removing that one file reverses it. NOT FIXED BY DELETION, because `self_organize.py` imports `memory` by that name and the old tree is the only thing that has ever produced a result. Mitigated by ordering — every entry point does `sys.path.insert(0, <root>/src)` — and tests/test_census.py's N5 re-measures the mitigation in a subprocess rather than asserting the collision is absent.

**C11. The default configuration cannot exercise itself: ten cadence defaults are longer than a default run** **[CONFIRMED]**  
`armed-but-inert` · rework · resolved from `build(environ={})` on 2026-08-30  
`DATA.stream_bytes=120000`, `LM.ctx=128`, `RUN.epochs=1`, so a default run is **at most 937 windows** and about **506** at the project's own measured 1.85 bytes/token (`spine/derive.py:139`). Ten cadence-shaped defaults exceed that:

| lever | default | what never happens on a default run |
|---|---:|---|
| `CAP.pin_windows` | 20000 | the capacity valve never lifts either cap |
| `MEM.use_decay_every` | 20000 | usage decay never runs |
| `FAB.ponder_warm` | 8000 | ponder never arms |
| `FAB.bal_warm` | 4000 | the load-balance term never arms |
| `EVAL.verify_fit_steps` | 3000 | the verification fit never runs |
| `TOK.retok_every` | 3000 | the vocabulary is never re-segmented |
| `EVAL.curve_every` | 2000 | **the learning curve is never probed — the one number P3 exists to produce** |
| `TOK.cand_window` | 1024 | the candidate window never fills |
| `OPT.lr_warmup` | 1000 | the run ends *inside* LR warm-up; the schedule's body never runs |
| `SIG.warmup` | 800 | the encoder warm-up never completes at measured b/token |

Two defaults from two different worlds met in one config: every cadence carries the OLD system's value, tuned against `STREAM_LEN=94000000` and 60k-step runs, while `stream_bytes` carries a smoke-test value. Neither is wrong on its own and together they describe a run in which almost nothing fires. `CAP.pin_windows=20000` is the same number, against a short run, that produced the historical defect where the report said the population "reached the cap but never held it long enough" — a true sentence about a false clock.

This matters most because of what it would certify: PLAN's P3 exit criterion is *empty environment, 200 steps, reaches the end*. A green P3 under these defaults means a system where every cadenced mechanism fired zero times, reported as working. That is the armed-but-inert family (57 records) arriving through the DEFAULTS rather than through a guard.

**Not fixed by editing the numbers**, which would only move the inconsistency. The repair is to make it *loud*: `RUN.startup_refusals` already exists as an entry point, and the resolved run length is known at build time from `stream_bytes`, `ctx`, `epochs` and the measured bytes/token — so a run can say at startup which cadences cannot fire before it spends a single step. Whether the defaults themselves should change is the owner's call (§ *for the owner*, `docs/04_CONTRACT.md`).

**C12. The resume geometry gate would REFUSE every resume, and three statements call it UNCHECKED** **[CONFIRMED]**  
`wrong-measurement` · rework · `src/spine/compose.py`, `docs/04_CONTRACT.md`; found 2026-08-30  
`compose._geometry_manifest` builds **15 fields** across LM, SIG, FAB and WORLD. The save side records **`WORLD.geometry` alone — five fields**, because `WORLD.geometry` is the only `geometry()` entry point in the tree. So ten fields are **in the live manifest and absent from the recording**.

`ckpt/api.py:174-179` specifies that case unambiguously: *"**A MISSING FIELD IS A REFUSAL, NOT A SKIP.** … The comparison is driven off the manifest's KEY SET rather than off truthiness, so `if recorded and recorded != live` — the untrippable-guard shape — is not writable here."* UNCHECKED is the **other** direction — recorded and absent from the manifest — which is where WORLD's grown population counts sit, and which `_geometry_manifest`'s own docstring uses the word for correctly.

Three statements in `compose.py` and three in `docs/04_CONTRACT.md` borrowed the word for the direction it does not cover. That is not a wording quibble. It is the difference between *"the gate checks a sixth of what it names"* and **every resume raising `GeometryRefusal` the day P4 lands** — and a resume is what `ckpt/api.py:3-6` calls *the experiment* for goal B, the definitive goal this whole rework exists for.

Corrected in all six places. **Q-CKPT-2 is therefore BLOCKING, not cosmetic**: either the save side records the same manifest shape keyed by prefix (which needs FAB to declare a sidecar it does not currently claim to emit), or the gate's key set narrows to what is actually recorded — and the second is the one that quietly checks nothing.

### HIGH (53)

**H1. Three arms in the DEFAULT grid list are the same run, and three more are a second identical triple** *(unverified)*  
`wrong-measurement` · harness · longrun.sh:1116-1117 (GRID_ARMS_DEFAULT), resolved at :164 base, :173 vote, :174 socloop, :175 socloop_w, :176 vote_w, :292 weights  
`bash longrun.sh grid` with no arguments runs 20 arms that describe only 17 configurations. base/vote/socloop all resolve to the defaults; socloop_w/vote_w/weights all resolve to exactly `ROUTE_REGION_W=0 FAB_KEY_NORM=1`. Six logs, six named arms, two experiments — and the GRID SUMMARY prints them as six independent rows, inviting a reader to treat identical numbers as replication.

**H2. Three arm comments state defaults the registry contradicts, and each one inverts the arm's meaning** *(unverified)*  
`coupling` · harness · longrun.sh:267-268, longrun.sh:276-277, longrun.sh:363  
The comments justify each arm's existence with a default that is not the default. 'TOK_MINT_PMIN 0.10 IS NOW THE DEFAULT, so `pgate` would have been an alias for `base`' — the default is 0.0, so it is `nogate` that is the alias. 'TOK_COMPOSE is now ON by default, so every arm below states BOTH knobs explicitly' — it is OFF, so `nocompose` states nothing. 'occupancy 0.50, permanently below FAB_PRESSURE=0.75, so the utilization cull never runs' — FAB_PRESSURE is 0.45, so at FAB_N0=2048/FAB_NMAX=4096 the gate is OPEN by default and round5's whole premise is stale.

**H3. `pilot`'s SIDE BY SIDE summary greps the unsuffixed log, so every pilot after the first reports the FIRST pilot's numbers** *(unverified)*  
`wrong-measurement` · harness · longrun.sh:637 (write) vs longrun.sh:645 (read)  
The run writes to `$(_reserve "$OUT/pilot_$ARCH.log")`, which becomes pilot_gru-2.log on the second pilot, but the summary reads the fixed path `$OUT/pilot_$ARCH.log`. The second, third, ... pilot therefore prints run #1's `order-1 X | THIS MODEL Y` under the banner 'SIDE BY SIDE (the only number that compares them directly)'. With `2>/dev/null | head -1` the failure is silent, and the value printed is a real-looking number from a different run.

**H4. `add` never received the three corpus protections that `pilot-add` was fixed with** *(unverified)*  
`wrong-measurement` · harness · longrun.sh:962-966  
`add` — the branch whose own comment says it 'runs the real experiment' — skips the fetch whenever ANY part*.txt exists, with no size check, no _fetch_manifest.json provenance check, and no automatic `--data-dir` for the-stack. All three holes are documented at length in pilot-add (longrun.sh:838-916) as the cause of the 5.6x exposure imbalance and of a corpus labelled the-stack that was actually this machine's Python. At GB scale the same skip means the multi-day continual-learning run can train on a 10 MB leftover while every line of the log names a 10 GB dataset.

**H5. `run`, `resume` and `add` are exempt from the append-only guarantee the file header claims for every subcommand** *(unverified)*  
`silent-overwrite` · harness · longrun.sh:45-48 (the claim) vs longrun.sh:583 and longrun.sh:1044  
The header states 'Every subcommand here used to write $OUT/<name>.log and SAVE_CKPT=$OUT/<name> directly, so re-running a pilot silently destroyed the previous one ... Results are the expensive part of this project; they are now append-only.' But `run` still uses the fixed SAVE_CKPT="$OUT/ck" and `add` the fixed SAVE_CKPT="$OUT/ck_$NAME", neither through `_reserve`. A second `bash longrun.sh run` (as opposed to `resume`) starts a fresh multi-day run that overwrites the previous run's checkpoint in place — the exact artefact `pilot-add` and `add` need as their baseline. There is also no pidfile, so two `run` invocations write to the same checkpoint concurrently.

**H6. sweep_domain_grid.sh cannot start: its own knob-verification step reports eight knobs as unread that are in fact read** *(unverified)*  
`untrippable-guard` · harness · sweep_domain_grid.sh:274-279  
Section 4's grep recognises only `_i("X"`, `_f("X"` and `os.environ.get("X"` — it does not recognise `_env("X"`. DEVICE, DATA_MODE, DATA_DIR, DOMAINS, MODEL, SIG_MODE, KEY_SRC and AMP are all read through `_env`, so the check reports them missing and calls `die`, unconditionally, before any cell runs. FORCE=1 bypasses 4b and 4c but not this. The whole 488-line sweep is dead at HEAD, and the failure message accuses the engine of a bug that is in the checker.

**H7. equiv.sh caches and reuses per-commit logs in a directory that encodes neither SCALE nor LEN, SEED or DEVICE, with no config stamp** *(unverified)*  
`wrong-measurement` · harness · equiv.sh:68 and equiv.sh:87  
`SCALE=fast bash equiv.sh <ref>` then `SCALE=deep bash equiv.sh <ref>` writes and reads the same $ROOT/runs/equiv_<A>_vs_<B>/<sha>.log. run_side reuses any log containing the completion marker without asking what produced it, so the deep-scale verdict is printed from fast-scale logs — the very failure longrun.sh built `_cfgsig`/`_reusable` to stop, unfixed here. The script's own header advertises 'confirm with SCALE=deep before trusting it', which is the command that silently does not re-run.

**H8. `run_full_unfrozen.sh` — still the README's headline command — pins fabric geometry from the archived era and omits CORPUS_CAP/DISK_STREAM** *(unverified)*  
`wrong-measurement` · harness · run_full_unfrozen.sh:45 and run_full_unfrozen.sh:67-80  
It passes FAB_N0=3 FAB_NMAX=6 explicitly, so it runs a 3-expert fabric while HEAD's default is 2048/4096 — precisely the stale value ARCHIVE.md names as the repository's most expensive trap. Its PART B env line sets neither CORPUS_CAP nor DISK_STREAM, so each corpus is capped at the 2,000,000-byte default while STREAM_LEN asks for 6,000,000 — the failure preflight.sh's own header lists as 'a multi-day run that would have trained on 2 MB'. README.md nonetheless presents it as 'the whole system in one command' and 'Start here'.

**H9. DISK_STREAM is undefined on the synthetic path but read unguarded in main()** *(unverified)*  
`crash` · so-config · self_organize.py:1122 (definition), :5470 and :6511 (reads)  
DATA_MODE=synthetic with EPOCHS>1 raises 'NameError: name DISK_STREAM is not defined' at the startup-guard block, before training. EPOCHS=1 short-circuits ('if EPOCHS > 1 and not DISK_STREAM') so it hides at the default.

**H10. 'true switches' are segment starts, not process changes -- the boundary metric is measured against artifacts** *(unverified)*  
`wrong-measurement` · so-config · self_organize.py:1407 / :1411 / :1412 (production), :8481-8483 (consumption)  
boundary precision/recall is scored against every splice segment start, including consecutive segments drawn from the SAME process. On a single-corpus run (NP==1, the goal-A configuration) every one of the ~96 'true switches' is a boundary we manufactured, and with SEG_CONTIG=1 there is not even a discontinuity there.

**H11. The chaining counterfactual is scored against a different function than the loss it is subtracted from** *(unverified)*  
`wrong-measurement` · so-fabric · self_organize.py:6992  
`_d3 = CE(model.head(_h3)) - loss` where `loss` came from the vote logits (fab._votelg). The baseline gap between the plain head and the trained per-hop vote blend is added to every contribution, so contrib's SIGN -- the thing both spare rules test -- is set by that offset rather than by the expert. If the offset is positive, every measured expert reads load-bearing and the utilization cull spares everything it can reach.

**H12. Cull eligibility and cull ranking are the same counter, so only heavily-used experts can ever be culled** *(unverified)*  
`coupling` · so-fabric · self_organize.py:2044-2051, :2224, :2250-2251  
bump_use increments `use` and `uage` together by 1, so (absent FAB_RESCUE, which defaults to 0) they are numerically identical. Eligibility is uage >= grace and the ranking key is use, so the eligible set is exactly the most-used experts and the cull removes whichever of them has least use -- i.e. the expert that just crossed the grace line. An expert the router never selects has use = uage = 0, is permanently ineligible, and can never be culled at all.

**H13. Only the argmax expert is ever credited with use, so the use-age clock cannot reach the population** *(unverified)*  
`coupling` · so-fabric · self_organize.py:2647, :2759, :6866-6872  
Utilization and the grace clock advance for one expert per window per hop. Every other computed expert -- including the one exploration deliberately inserted so it would get traffic -- receives nothing. With a concentrated router this means almost the whole population stays at use-age 0 forever, which the manage() diagnostic reports as "the population is not under selection".

**H14. Discovery always targets the lowest-indexed unused expert and overwrites it every time** *(unverified)*  
`silent-overwrite` · so-fabric · self_organize.py:2421-2426  
`min(range(N), key=use)` returns the FIRST minimum, and with most of a 2048-expert population at use=0 that is deterministically the same slot on every call. Discovery does not credit use, so the recipient never leaves the minimum. Each novel signature overwrites half of that one centroid, so 'discovery' cannot accumulate -- the last novel signature wins and every earlier discovery is erased -- while the `discovered` counter reports it firing.

**H15. `_lrv` is undefined when LR_SCHED="none" and FAB_LR_OWN=1 -> NameError on the first flush** *(unverified)*  
`crash` · so-loop · self_organize.py:7094 (only assignment) vs 7195, 7285  
The run dies with `NameError/UnboundLocalError: _lrv` on the first optimizer step of any configuration that turns the LR schedule off and per-expert rates on.

**H16. The signature width is chosen from the vocabulary-mean bytes/token that the comment 40 lines above declares invalid** *(unverified)*  
`unit-mismatch` · so-loop · self_organize.py:5678 inside `_sigwidth()`, against the reasoning at 5645-5655  
SIG_WIN=0 (the default) picks a signature width from an estimator whose error changes SIGN with vocabulary size, while the coverage percentage printed on the same `[signature]` line is computed from a different, use-weighted estimator -- so the width and the number that judges it disagree, and neither is comparable across VMAX.

**H17. `_ep_start` starts at 0 while `step` starts at `_resume_step`, poisoning the first recorded epoch length and the LR horizon on every resume** *(unverified)*  
`wrong-measurement` · so-loop · self_organize.py:6333 (`_ep_start = 0`) vs 5057 (`step = _resume_step`); consumed at 6524 and 6356  
On a resume, the first `_eplen` entry is `resume_step + this_epoch's_length` instead of the epoch's length. `proj_arith` then computes the shrink ratio as `eplen[-1]/eplen[-2]` = real/inflated, which clamps to the 0.5 floor, so every remaining epoch is priced at half the last -- a geometric under-projection of the run end. The cosine wavelength is latched from that projection and never revised upward (`state[0] = min(state[0], _p)`), so a resumed run anneals against a wavelength derived from a bogus first measurement.

**H18. compose_test scores the BASE model, not the system** **[CONFIRMED]**  
`wrong-measurement` · so-model · self_organize.py:3727 (compose_test), contradicting 3930-3934 (_eval_logits)  
The "PERFORMANCE: does the memory earn its keep?" and "CROSS-SEGMENT COMPOSITION" and "IS THE PARTITION INFORMATIVE?" sections all build pm from model(X)[0], which is the plain LM head. With FABRIC=1 (the default) the fabric is entirely absent from these numbers, and mask_dead is never applied so never-minted and retired ids stay in the denominator.

**H19. holdout_hist can never contain this run's probe, so F is structurally identical to a clipped BWT forever** *(unverified)*  
`armed-but-inert` · so-model · self_organize.py:5161/5205 (the only _HIST appends) vs 5361 (save) and the call order 7917 -> 8028  
_HIST is appended to only inside report_holdout, which is called once at line 8028 — AFTER the final _save_ckpt at 7917. So every checkpoint's holdout_hist is whatever it inherited (i.e. {} in the first run of any chain), the F measure can never draw on more than the single `prev` value, and the caveat printed at 5202-5204 ("The two separate once a chain has two or more prior probes") describes a condition the code can never reach.

**H20. The across-run-boundary held-out probe does not score the same text when the vocabulary grows** *(unverified)*  
`wrong-measurement` · so-model · self_organize.py:5087-5088, against the docstring claim at 5074-5076 and the save comment at 5356-5359  
Window starts are drawn as `_rs.randint(0, len(_v) - WIN - 2)`, where `_v` is the TOKENISED validation text. Under TOK_ONLINE the segmentation changes (every retok clears _VALT at 7771, and 7833 clears it again after the final re-tokenisation), so len(_v) shrinks over a run and differs between a parent run and its child. The seed is fixed but the index space is not, so `prev` and `now` in report_holdout are measured on DIFFERENT held-out windows — the one number the file calls "the ONLY number that spans the run boundary".

**H21. Per-expert memory resume: the un-partitioned prefix copy is resurrected on top of the partitioned one** *(unverified)*  
`silent-overwrite` · so-model · self_organize.py:4943-4972  
On the MEM_PER_EXPERT path the code first writes the saved compacted arrays into rows 0.._mn-1 (4946-4948), then the owner loop does `mem.active[:] = False` and re-places entries at owner*quota+slot, and then line 4972 unconditionally sets `mem.active[:_mn] = True`. Rows 0.._mn-1 therefore come back ACTIVE holding the un-partitioned copy with own=-1 (memory.py:38) and last=0 — duplicate entries in the wrong owner blocks, immediately the oldest under per-owner LRU. Additionally mem.use (4949) and mem.selfcon (4971) are written by compacted row index while the real entries live at _dst, so retrieval fitness and wrongness are attached to the wrong entries.

**H22. World-model geometry is recorded in the checkpoint and never checked on resume** *(unverified)*  
`recorded-never-read` · so-model · self_organize.py:4590 reads only world_cfg["n"]; lat/hid/nmax/route are saved at 5365-5366 and never read here  
DynamicsPopulation registers fit/mass/alive as buffers of size nmax (world_model.py:81-83). A resume with a different WORLD_NMAX (even a LARGER one, which is otherwise harmless) reaches world_fwd.load_state_dict at 4694 with mismatched buffer shapes and dies inside torch naming no knob — exactly the failure the fabric geometry gate at 4413-4462 exists to replace. The same applies to WORLD_LAT / WORLD_HID / WORLD_ROUTE.

**H23. The LM-curve verdict cascade prints 'still improving or flat' immediately after BLEW UP / PLATEAUED / RECOVERED / NOT DIVERGING** *(unverified)*  
`silent-overwrite` · so-report · self_organize.py:8290-8356  
The bits/byte verdict block (`if _bpb_dir is not None:` at 8290) prints one of vocab / blewup / recovering / plateau. The NEXT statement is an independent if/elif/else: the `if` only fires on 'diverging', the `elif` requires `_bpb_dir is None`, so whenever `_bpb_dir` exists and the verdict is anything but 'diverging' the `else` fires and prints '>> still improving or flat: falling = more passes/steps will help; flat = the model has converged...'. A run told 'BLEW UP AND STAYED DOWN... something broke, the run never recovered it' is told two lines later that it is still improving or flat and needs more capacity or data.

**H24. EXPERT INDEPENDENCE restores only 5 tensors and n_live; every per-expert dict stays permuted for the rest of the report** *(unverified)*  
`silent-overwrite` · so-report · self_organize.py:9010-9024, Fabric.remove at :2539-2563  
`fab.remove(_j2)` is a swap-with-last that also mutates `use, uage, born, ef, es, births, comp, contrib, dom_of, rescued` — it pops key `_j2` and re-keys `_last` to `_j2`. The restore puts back only `A, B, K, SRC, cent` for rows `[_j2, _last]` plus `n_live`. So after the section claims '(expert restored -- GENERATION and the remaining evals run on the INTACT model)', the busiest expert's utilization/birth/affiliation/contribution records are gone and the last slot's records are filed under the wrong id. Every later expert diagnostic reads those dicts: ROUTER SELECTION (`fab.use`), the never-selected/young analysis (`fab.born`), LINEAGE (`fab.births`), BREADTH (`fab.dom_of`), marginal contribution (`fab.contrib`), COMPETENCE PROTECTION. In particular the deleted expert was chosen as the BUSIEST, so 'top expert took X%' and 'half the traffic went to N experts' are computed after the largest use count has been deleted, and slot `_last` now has no `born` entry, so `fab.born.get(n, 0)` returns 0 and it reads as maximally old — which is the exact condition that trips the '!! THE PROBE PARTITION IS NOT THE RUN'S ROUTER' false alarm.

**H25. SPECIALIZATION scores the whole population on every window and calls the result each node's competence** *(unverified)*  
`wrong-measurement` · so-report · self_organize.py:9119-9178  
The section header asks 'does the material each node WINS get modelled better by that node than by the population at large?'. The per-window bits/byte `_bw` is computed once, from `fab_logits(...)` — the full routed/blended prediction — and then grouped by entry winner. Both the observed spread and the shuffled null are computed from the same population-scored values, so the statistic measures only whether the entry partition groups windows of differing difficulty. No per-node prediction is ever computed. A population in which every node is identical but the router sends hard text to node A and easy text to node B would read SPECIALIZED.

**H26. SUFFICIENCY measures the society forward path on a default chaining run** *(unverified)*  
`wrong-measurement` · so-report · self_organize.py:9481-9505  
`fab.society(...)` is called unconditionally. On the default SOCIETY=0 the run trains and evaluates through `Fabric.forward` (chaining); society() is a path nothing trained. The CHAINING section 130 lines earlier prints an explicit warning when the reverse happens ('The DEPTH figure below is a report-time probe of a path this run did not use'), but SUFFICIENCY carries no such note, so 'AGGREGATE: no member is sufficient alone, together they are -- which is the design claim, measured on the outcome rather than assumed' is asserted about a forward path the run never used.

**H27. The fabric mass probe pairs token windows with signature windows read at token indices into a byte stream** *(unverified)*  
`unit-mismatch` · so-report · self_organize.py:9046-9055  
`_pos` are STREAM (token) indices used to slice `stream`. The paired signature windows are read as `ENC_SEQ[q:q+WIN]` for the same q. Under the default ONLINE + SIG_SPACE=bytes, ENC_SEQ is the byte stream and a token index is roughly 1/bytes-per-token of the corresponding byte offset, so every signature is drawn from the wrong place — and all of them from the first len(stream) bytes of a much longer byte stream. `encpos()` exists precisely to do this conversion and is not used here. The section then reports 'over N windows: X of Y nodes carry mass, top node Z%' as the router's answer to varied material.

**H28. WRONG_SWEEP=1 leaves the synthetic src=99 entries and the selfcon flags in the store for every downstream section** *(unverified)*  
`coupling` · so-report · self_organize.py:8898-8946  
`mem.delete_src(99)` and `mem.selfcon.fill_(-1.0)` are inside the `else:` (detect-only) branch. With WRONG_SWEEP=1 the sweep branch prints and returns, so the injected cross-domain WRONG entries stay active and the self-consistency flags stay set. Every subsequent measurement then runs on a contaminated, partly-filtered store: compose_test's PERFORMANCE / CROSS-SEGMENT / PARTITION INFORMATIVENESS (which builds `valid = mem.active & (~mem.is_wrong())` and its provenance set from mem.src, now containing a domain 99 that is not a domain), `bpb_true(use_mem=True)` in FABRIC / NON-STATIONARY, and both UNLEARN tests.

**H29. Resume reactivates slots 0..n unconditionally, undoing the per-owner partition restore** *(unverified)*  
`silent-overwrite` · subsys · self_organize.py:4954, 4962, 4972  
The per-owner restore path deliberately clears active and then activates only the reconstructed owner blocks. Six lines later `mem.active[:_mn] = True` runs in BOTH branches and reactivates the first _mn slots regardless of ownership. Those slots still hold the uncompacted bulk copy made at line 4945-4948, so the same checkpoint row exists twice (once at its bulk position, once at its owner-block position), the bulk copies carry own=-1 and last=0, and rebuild_census then counts both.

**H30. The synthetic wrong-entry injection uses src=99, which collides with a real domain id** *(unverified)*  
`coupling` · subsys · self_organize.py:8880 and 8945  
The wrongness evaluation force-writes synthetic entries tagged src=99, then computes precision/recall against `mem.src == 99` and finally calls delete_src(99). Domain ids come from the same namespace and climb monotonically; memory.py's own docstring records 125 source ids on a real run. On any run whose assembler reached domain 99, the genuine domain's entries are counted as 'injected' (inflating recall, deflating the false-positive count) and are then permanently deleted from the store.

**H31. The per-owner write path bypasses probation and the per-source floor entirely, while every report still prints them** *(unverified)*  
`armed-but-inert` · subsys · memory.py:212-241 vs memory.py:242-296  
With MEM_PER_EXPERT=1 the store never reaches the sampled-eviction branch, so _unprotected is never called, the probation-first narrowing never runs, and n_prob_evict/n_main_evict stay 0 — which also makes pressure() return None forever (tot < 1000). Meanwhile _commit still sets prob=True on every write, src_report() still reports a floor and a probation budget, and the [memory] banner still prints 'src floor 0.5'.

**H32. The wrong-flag read filter is structurally inert during training, and the code knows it** *(unverified)*  
`untrippable-guard` · subsys · memory.py:519-532 + self_organize.py:8881  
read() filters on is_wrong(), which needs more than 10 entries with selfcon >= 0. selfcon is written only by selfcheck(), which is called exactly once from the end-of-run report, and _commit resets selfcon to -1 on every write. So during the entire run is_wrong() returns all-False, n_wrong_blocked stays 0, and the per-run 'N of M active entries are excluded from EVERY retrieval' figure describes the state after a pass the report itself just ran, not anything that happened.

**H33. pressure() cannot reach its own threshold because probation is permanently over budget** *(unverified)*  
`untrippable-guard` · subsys · memory.py:401-416 with memory.py:268-280  
Every write lands on probation and only a retrieval promotes out of it. At the observed write:read ratio probation covers most of the store, so `_over` is almost always true, eviction takes the probation branch, n_main_evict stays near zero, and pressure() = main/(main+prob) reads ~0 for the whole run whatever the store is actually suffering. A signal that cannot reach its threshold is indistinguishable from a healthy one.

**H34. retire() is not persisted: a retired token comes back live after save/load** *(unverified)*  
`recorded-never-read` · subsys · tokenizer.py:406-418 and tokenizer.py:479-488  
retire() only pops the byte string from seq2id and records the id in self.retired. save() writes only `merges`, and load() replays every merge into seq2id unconditionally. So a token retired for failing probation is fully re-armed on the next resume, and self.retired and self.prov are both empty after a load. The probation verdict does not survive the run boundary that continual learning is supposed to cross.

**H35. levers.py --quiet crashes with UnboundLocalError** *(unverified)*  
`crash` · tests · levers.py:154-157  
`python3 levers.py --quiet`, the mode its own docstring advertises, dies before printing anything. `_mm` is assigned only inside `if not quiet:` but read unconditionally on the next line.

**H36. tok_test's headline section never enters the mechanism it tests** *(unverified)*  
`armed-but-inert` · tests · tok_test.py:64-86  
All three 'MINTING REACHES THE CAP' fixtures stop at 353 tokens of a 1024/800 cap and pass because `left == 0`, i.e. the corpus ran out of candidates. All three report `0 skipped`, so the candidate-rejection path — the entire subject of the file — is never entered and the fixtures cannot distinguish the fixed code from the pre-fix code. Only the max_tok=2 case (7 skipped, 4 rescued) exercises it.

**H37. lr_test claims a line-for-line check of its reimplementation but does five substring greps** *(unverified)*  
`wrong-measurement` · tests · lr_test.py:22-23 vs :55-60  
The docstring says 'the FIRST test checks that reimplementation still matches the real one line for line -- so this file fails loudly if the schedule is edited without it.' What it actually does is assert five identifier/expression fragments appear anywhere in ast.unparse(_lr_at). Changing `total // 10` to `total // 20`, moving the warmup clamp, or altering the restart cycle arithmetic all leave every fragment present and the reimplementation silently wrong.

**H38. cap_test sections 6 and 7 test re-typed local copies, not shipped code** *(unverified)*  
`wrong-measurement` · tests · cap_test.py:138-139, :168  
The file's header justifies AST-lifting precisely so a re-typed copy cannot 'pass happily while the real code was wrong'. Sections 6 (the stalled band) and 7 (the retok blackout) then define `stalled_old`/`stalled_new`/`valve_may_run` locally. Both shipped predicates live inside main() and are unreachable by AST, so 11 of cap_test's 31 checks assert nothing about self_organize.py.

**H39. cap_test's blackout cooldown is 1500 against a shipped default of 400** *(unverified)*  
`unit-mismatch` · tests · cap_test.py:165  
`COOL = 1500` is PlateauGrowth's SIGNATURE default, not the operating value. The call site builds the controller with `_i("FAB_COOLDOWN", 400)`, and the shipped blackout test reads `fabgrow.cool`. So every numeric claim in section 7 ('...for the whole cooldown', the 41935+1499 case) describes a 1500-step window no default run produces — a 3.75x mismatch between the test's constant and the code's.

**H40. growth_test measures a controller no run builds** *(unverified)*  
`wrong-measurement` · tests · growth_test.py:37  
`S.PlateauGrowth(ramp=4000, **kw)` takes the class's signature defaults cooldown=1500, warmup=2000, burst=3. The run builds it with FAB_COOLDOWN=400, FAB_WARMUP=300, FAB_BURST=1. Every timing claim in the file — the cooldown bounding firings to 'a burst or two', the 8000..16000 suppression scan, the blackout window — is about a configuration that never ships.

**H41. growth_test inherits ambient FAB_GROW and FAB_RAMP_LATCH** *(unverified)*  
`coupling` · tests · growth_test.py:21-25  
It is the only gate that imports self_organize without stubbing _env, so PlateauGrowth reads the real environment. FAB_GROW=0 exported (an arm sets exactly that) produces 5 failures; FAB_RAMP_LATCH=0 produces 3. Worse, under FAB_GROW=0 the two 'no false positives' checks pass vacuously, because zero growth trivially satisfies REGRESSION==0.

**H42. SIG_MODE=frozen is a guaranteed NameError everywhere, not only in the probe** *(unverified)*  
`crash` · tools · self_organize.py:3259, reachable from sweep_domain_report.py:173-174 and probe_signature.py:415  
Any code path that calls sig_of() with SIG_MODE not in ('learned','bigram') raises NameError. sweep_domain_report.full_env_of() will happily emit `SIG_MODE=frozen` into a 'reproduce it' command block for a cell that could never have run. The bigram branch also falls through to the same line when a window has <=1 element.

**H43. cl_bench.py prints '(forgotten)' unconditionally, even when zero entries were deleted and the score improved** *(unverified)*  
`untrippable-guard` · tools · cl_bench.py:218-219  
The word '(forgotten)' is a hardcoded literal in the format string. In my run it printed `MEMORY delete : 0 entries in 0.1 ms | domain0 5.785->5.762 (forgotten)` — no entries were deleted (the store had already evicted domain 0) and the loss went DOWN, and the line still asserted forgetting. This is the headline of the EDITABILITY section, the claim the file exists to support, and no data can make it fail.

**H44. cl_bench.py's 'editability edge' sentence cannot express memory losing, and printed '0x less collateral' when memory had 2.3x MORE collateral** *(unverified)*  
`wrong-measurement` · tools · cl_bench.py:227  
`{w_coll/max(mem_coll,1e-4):.0f}x less collateral` formats a ratio below 1 as '0x' and wraps it in the word 'less'. In my run w_coll=0.0512 and mem_coll=0.1162, so memory leaked more than twice as much as gradient-ascent unlearning, and the report announced 'memory is 1895x faster and 0x less collateral' as an edge.

**H45. cl_bench.py's DRIFT verdict is computed from a different comparison than the number printed beside it** *(unverified)*  
`wrong-measurement` · tools · cl_bench.py:208-209  
The line prints `model-key vs frozen-key = {meanforget(Rmm)-meanforget(Rmf)}` and then a verdict decided by `meanforget(Rmm) < meanforget(Rwo)-0.05` — Rmm against WEIGHTS-ONLY, not against the frozen key. A reader sees a frozen-vs-model number and a verdict that was never about it. The two can disagree in sign.

**H46. cl_bench.py's before/after comparisons are measured on freshly drawn random data, so every editability and recovery delta is confounded by resampling noise** *(unverified)*  
`wrong-measurement` · tools · cl_bench.py:92-101 (batch) used by cl_bench.py:155-166 (bpb), called at :214-215, :223, :242, :251  
bpb() draws 6 NEW random batches on every call; there is no fixed evaluation set. So `Rmf[0][N-1] -> mem_after0`, the collateral columns, and `domain1 b1 -> a1` compare independent samples. In my run the memory-delete 'before' and 'after' differed by 0.023 b/B even though delete_src removed 0 entries — pure sampling noise reported as an edit effect. self_organize.py's own unlearn report uses a fixed EVAL_N-window eval for exactly this reason.

**H47. compare.py's seed-budget adequacy line counts CROSSINGS, not independent observations — the exact error the MIN_PAIRS guard above it was fixed for** *(unverified)*  
`wrong-measurement` · tools · compare.py:337-343  
On the unpaired branch `pairs` is the n_a x n_b cross product. `_n_indep` was introduced at compare.py:292 with a comment saying MIN_PAIRS 'was always meant to be counting' independent observations — and then the very next block reverts to `len(pairs)`. With 4 runs an arm and need=5 it printed 'sample size is adequate (16 >= 5 needed)'. Both the adequate branch and the 'you have N' branch report crossings.

**H48. compare.py's per-seed 'diff' column has the OPPOSITE sign to the 'mean difference' line above it on higher-is-better metrics** *(unverified)*  
`unit-mismatch` · tools · compare.py:282-284 vs compare.py:300-302 / :332-334 / :346-348  
The headline prints the ORIENTED mean (`_mean(diffs)` over negated pairs), labelled '(A - B, oriented: + means A is worse)'. The per-seed table prints the RAW `da[s]-db[s]`. On --metric d_order1 the two disagree in sign for every row: my run printed `mean difference (A - B, oriented: + means A is worse) -0.6000` immediately above five rows each reading `+0.6000`. A reader who averages the column gets the negation of the headline.

**H49. probe_ckpt_geometry.py and probe_stability.py label per-corpus rows from the ENVIRONMENT's DOMAINS, ignoring the checkpoint's own recorded `domains` — and ignoring self_organize's post-drop realignment** *(unverified)*  
`recorded-never-read` · tools · probe_ckpt_geometry.py:89 and probe_signature.py:395,398; probe_stability.py:85 (corpus set)  
self_organize.py drops corpora under 5000 bytes and explicitly realigns DN so 'the per-domain scores below are labelled correctly'; the probes re-split os.environ['DOMAINS'] instead of reading S.DN, so after any drop every 'corpus p (name)' row names the wrong corpus. Worse, the probe sidecar RECORDS which domains the checkpoint trained on and neither probe reads it: I probed a checkpoint trained on 'eng,py' and probe_ckpt_geometry printed four rows labelled eng/py/num/c plus a confident VERDICT.

**H50. fetch_big.py's dialogue formatting keys off the raw --dataset string, so the full dataset id resolves the preset but loses the turn markers** *(unverified)*  
`coupling` · tools · fetch_big.py:212 vs fetch_big.py:112-114  
Lines 105-114 were explicitly rewritten so a preset is found by short key OR by full id. Line 212 was not: `is_dialogue = a.dataset == "oasst1"`. So `--dataset OpenAssistant/oasst1` — the id printed on the dataset page — resolves field='text' from the preset and then writes plain text with no `<|user|>` / `<|assistant|>` markers. The preset's entire stated purpose ('DIALOGUE. Formats as turn-marked conversations', 'teaches TURN-TAKING') is silently discarded, and nothing downstream can detect it. Same bug class, one line below the fix.


**H51. All 35 levers that declare a Clock unit resolve to a bare int, so the unit is metadata at every read site** **[CONFIRMED]**  
`unit-mismatch` · rework · measured from `build(environ={})` on 2026-08-30  
`spine/units.py` exists because one number compared against two clock kinds is this project's most repeated defect. 35 levers declare a Clock unit — `CAP.pin_windows` (Windows), `DOM.manage_every` (Windows), `EVAL.curve_every` (Windows), `OPT.lr_warmup`, `FAB.bal_warm`, `TOK.retok_every` and 29 others — and `Config` hands back **`int` for 34 of them and `float` for one**. So the kind is a comment unless the reader wraps it:

```
held >= cfg.pin_windows              -> UnitError   (the mechanism working)
int(held) >= cfg.pin_windows         -> silence     (the original defect)
Windows(held) >= Windows(cfg.pin_windows)  -> correct, and nothing requires it
```

**Where the protection IS real**, so this is not "the units do nothing": `spine/derive.py`'s functions type-check their arguments and refuse a foreign kind, and `spine/assemble.py` wraps explicitly at every coupling (`derive.flush_period_windows(Windows(r["CAP"].pin_windows), ...)`). Any value travelling through a derive function or a wire is checked. The gap is a **package body reading its own lever** and comparing it to anything — the one place the spine cannot see, and the place all six historical instances of this defect lived.

**Not fixable by making `Config` return `unit(value)`**, which was the obvious patch and was measured before being rejected: a `Clock` refuses `*`, `//`, `%` and comparison against a bare int, and several of these levers are used arithmetically (`max(1, manage_every // batch_w)` is the shipped shape). Auto-wrapping would turn every such site into a `TypeError` at once. Doing it properly means routing each arithmetic site through a **named** conversion in `spine.derive` — which is the design's own rule and is exactly what `flush_period_windows` was added for — and that is P4 work, package by package, not a patch to `lever.py`.

Until then the honest statement is the one to put in the report: the clock kinds are enforced **between** packages and advisory **within** one.

**H52. At the shipped defaults every clock kind is numerically identical, so P3's exit criterion cannot detect a units defect** **[CONFIRMED]**  
`wrong-measurement` · rework · resolved from `build(environ={})` on 2026-08-30  
`OPT.batch_windows=1` and `OPT.accum=1`, so **one window is one flush is one backward pass is one optimizer step**. Every conversion in `spine/derive.py` is the identity at those numbers, and a Windows/Flushes confusion — the single most repeated defect in the survey, and the entire reason `spine/units.py` exists — produces *identical output* to correct code.

PLAN's P3 exit criterion was `empty environment, 200 steps, reaches the end; both data paths`. Under it, a run that reaches the end is evidence the code executes and **no evidence whatever about units**. Every historical instance of the defect needed `BATCH_W > 1` to appear: the pin clock reading 43,645 real ticks as 2,650 (÷16), `MANAGE_EVERY` compared against a window counter above the early-out and a flush counter below it, accumulation gated on windows so 55 optimizer steps were measured where 13 were due.

This is not an argument for changing the defaults — `batch_windows=1` is a reasonable smoke-test value. It is an argument that **the test must not be run only there**. P3's criterion is amended to require a second arm at `OPT_BATCH_WINDOWS=16`, and the two arms must differ only where the units say they should. Recorded rather than silently added to the test, because the criterion is PLAN's and this is a change to it.

**H53. `SIG.d_idle_cadence` was relocated from a computed default into a coupling that was never declared, so the relation is simply gone** **[CONFIRMED]**  
`recorded-never-read` · rework · `src/sig/levers.py:402-410`, found by `tests/test_ownership.py` O11 on 2026-08-30  
The old declaration was `_i("ENC_EVERY_IDLE", max(ENC_EVERY * 6, 12))` — a default read from another lever, which `spine/lever.py` refuses by construction. The census's repair was not to delete the relation but to **move** it: the comment says the intent "is not lost, it is relocated: the census proposes `SIG.d_idle_cadence = max(train_every*6, train_every_idle)` declared in `spine/assemble.py`, so the relation prints in the coupling graph instead of hiding inside a default" — and then, in its own words, "it is simply not declared yet."

It still is not. So `train_every_idle` sits at a literal 12 with **no connection to `train_every` at all**: change the dense cadence and the idle cadence does not follow, silently. The literal is defensible on its own — at the shipped `ENC_EVERY=1`, `max(1*6, 12) = 12`, so the run of record is unchanged — which is exactly what let it survive. What is lost is the *rule*, and the coupling graph is the one place this architecture puts rules so they can be read.

The comment is right that `assemble.py` already supports the shape: `FAB.d_operating_population` is a same-package coupling computed from FAB's own levers. This is one row.

**How it was found is the part worth keeping.** No check looked for it. O11 was written to catch unnamed cross-kind arithmetic in *code*, found nothing because every body is a stub, and was then widened to read the docstring specifications P4 will implement — at which point it reported this. A defect recorded as "relocated" to somewhere it never landed is invisible to every check that reads declarations, because the declaration it was relocated *to* does not exist.

### MEDIUM (118)

**M1. sweep_domain_grid.sh's unpinned-assembly-knob guard also fires on eight DOM_* knobs added since it was written** *(unverified)*  
`untrippable-guard` · harness · sweep_domain_grid.sh:287-302  
Even if section 4 were fixed, 4b dies on DOM_CULL_EMPTY, DOM_CULL_FLOOR, DOM_FOLD_MULT, DOM_MANAGE_EVERY, DOM_MIN_VISITS, DOM_PRIOR, DOM_RECUR, DOM_RECUR_HORIZON unless FORCE=1 — and FORCE=1 is precisely the flag that lets them run at their defaults and confound the axes the guard exists to protect. The guard has become a permanent stop rather than a check.

**M2. equiv.sh's noise baseline is keyed by device but applied across scales, and can subtract a real behavioural change** *(unverified)*  
`wrong-measurement` · harness · equiv.sh:116-129  
The baseline file is $ROOT/runs/equiv_noise_${DEV}.txt and holds line SHAPES with every number replaced by NUM/N. A shape recorded as noisy at SCALE=fast is then subtracted from a SCALE=deep comparison, and because normalisation erases the values, 'this line varies run to run' and 'this line changed because of the commit' are the same pattern. An INERT verdict is only as strong as the noise set is small, and nothing bounds or reports its size at verdict time.

**M3. `watch`'s progress filter cannot match the rate lines it exists to show** *(unverified)*  
`untrippable-guard` · harness · longrun.sh:1962  
The pattern is `\[rate\]` — the literal string '[rate]'. self_organize.py prints '  [rate @ 12345] 3200 steps/min | ...'. The most frequent progress line in a multi-day run (RATE_EVERY=5000) is invisible to `bash longrun.sh watch`; only [epoch, [PHASE and [saved checkpoint survive, plus the three prose sentences that happen to contain the literal '[rate]' at startup and after a resume, which `tail -12` then scrolls off.

**M4. rerun.sh's per-arm summary greps two report lines that no longer exist** *(unverified)*  
`recorded-never-read` · harness · rerun.sh:68-69  
`go` prints a fixed set of extracted lines; two of its seven patterns can never match at HEAD. 'mean drift' appears nowhere in self_organize.py (the retention verdict now reads 'RETAINED --' / 'DRIFTING -- earlier material is measurably worse'), and 'model ALONE .*model\+MEMORY .*ceiling' requires all three tokens on one line while the printed line is 'model ALONE (weights only) X  ->  model + MEMORY Y   (memory contributes Z)' with no 'ceiling'. The summary silently prints two blank rows where two of its headline numbers should be.

**M5. rerun.sh's smoke gate runs 11 arms in parallel that all write the same shared tokenizer file** *(unverified)*  
`silent-overwrite` · harness · rerun.sh:112 (with TINY setting SAVE_CKPT=0 at rerun.sh:84)  
With SAVE_CKPT=0 and no TOKENIZER_PATH, self_organize.py's vocabulary save target falls back to TOKENIZER_PATH's default data/dyntok.json. SMOKE_JOBS (default nproc) arms run concurrently and every one of them writes that single file at end of run, racing each other and leaving the repo's shared vocabulary as whichever arm finished last.

**M6. bench_gpu.sh writes FAILED rows space-separated into a file the summary parses as tab-separated** *(unverified)*  
`unit-mismatch` · harness · bench_gpu.sh:111 (write) vs bench_gpu.sh:118 (write) and bench_gpu.sh:131 (read)  
The success path writes 8 tab-separated fields; the failure path writes 6 space-padded fields. The summary reads with `IFS=$'\t' read -r tag model amp fuse wall util bench prof`, so a failed arm lands entirely in $tag and every other variable is empty. SUMMARY.txt then shows a line like '[A gru off 1 FAILED (exit 1) n/a] MODEL= AMP= ENC_FUSE=' followed by three blank lines — the one row a reader most needs to parse is the one that is mangled.

**M7. bench_gpu.sh pip-installs `datasets` into the training environment, which preflight.sh explicitly forbids** *(unverified)*  
`coupling` · harness · bench_gpu.sh:51  
preflight.sh's install notes say 'numpy is NOT needed ... Install it only for `datasets`, and never into the same env as an NGC torch (upgrading numpy under NGC's torch breaks its ABI). Fetch in a THROWAWAY env'. bench_gpu.sh does the opposite unconditionally when $DATA is missing, and preflight section 3b exists specifically to detect the resulting ABI break.

**M8. preflight.sh documents a FIX=1 knob that nothing in the file reads** *(unverified)*  
`armed-but-inert` · harness · preflight.sh:12  
'FIX=1 bash preflight.sh        # also install what is missing' is the second line of the usage block. The string FIX appears exactly once in the file. Setting it does nothing; a user following the header believes missing dependencies were installed. This is the D_MODEL_B failure mode inside the script written to catch the D_MODEL_B failure mode.

**M9. `bash longrun.sh pilot-add <name> local` at its own recommended size exits 1 on most machines** *(unverified)*  
`crash` · harness · longrun.sh:665 (the recommendation) and longrun.sh:897 (the call)  
The fourth argument now defaults to PILOT_GB (0.06 GB) so the two corpora match, and `pilot` closes by printing exactly that command. fetch_local.py refuses a short corpus with a non-zero exit unless --allow-short, and the run recorded in longrun.sh's own round18 note produced 10.26 MB of local Python. So the advertised continual-learning demo aborts before touching the GPU on any box with under ~54 MB of local Python source, and neither the recommendation nor the usage text mentions FETCH_ARGS="--allow-short".

**M10. `smoke`'s banner says 'every pilot arm'; the default list is 7 of 99 and contains none of the arms the current rounds use** *(unverified)*  
`wrong-measurement` · harness · longrun.sh:1817 vs longrun.sh:1821, and the header claim at longrun.sh:15  
The header sells `smoke` as 'does every pilot arm still REACH ITS REPORT? minutes, run before any grid' and the banner interpolates `${SMOKE_ARMS:-every pilot arm}`. The actual default set is base nogate frozen pgate_t prob_use prob_emb compose — all tokenizer arms — and one of those (nogate) is a duplicate of base. No lr_*, gc_*, gate_*, sched_* or fix_* arm is covered, so running smoke before `grid round17` greenlights nothing about round17.

**M11. harness_test.sh's arm-resolution check does not cover the DEFAULT grid list or the smoke list** *(unverified)*  
`untrippable-guard` · harness · harness_test.sh:49  
The scan regex requires a preset case-label and `ARMS="..."` on one line. GRID_ARMS_DEFAULT (an assignment spanning two lines) and the SMOKE_ARMS default (a `${...:-...}` expansion in a for-loop) match neither. So the arm list that `bash longrun.sh grid` runs with no arguments, and the arm list `bash longrun.sh smoke` runs, are exactly the two lists the harness test does not check — while the test's own header cites 'an arm defined in the ARMS preset case instead of _flags_for' as the failure it exists to catch.

**M12. `seeds` and `repeat` SUMMARY glob every matching log in the directory, including ones this invocation never validated** *(unverified)*  
`wrong-measurement` · harness · longrun.sh:1686 and longrun.sh:1776  
`_reusable` is only consulted for seeds in this invocation's SEEDLIST. The end-of-run python then globs `{tag}_seed*.log` and prints held-out / vs-order-1 / specialization for every file that matches, including logs from an earlier invocation at a different EPOCHS or STREAM_LEN that this run never touched. Running `SEEDS="0 1 2" seeds` and later `SEEDS="3 4" seeds` with a different config prints five rows and a mean/spread across two configurations — the exact failure the file's own _cfgsig note at longrun.sh:60-70 says was fixed.

**M13. `pilot-add`'s log path is derived from the checkpoint reservation, so an orphaned log is overwritten by tee** *(unverified)*  
`silent-overwrite` · harness · longrun.sh:831  
`_PA_CK=$(_reserve "$OUT/pilot_${PA}_$NAME"); _PA_LOG="$_PA_CK.log"` reserves against the CHECKPOINT path. `_reserve` returns the base path unchanged when the checkpoint directory does not exist, even if `<base>.log` does. So if the checkpoint directory was deleted, moved, or never written (a run killed before its first save), the next pilot-add returns the unsuffixed path and `tee` truncates the existing log — losing the ACROSS THE RUN BOUNDARY result that is the one number the command exists to produce.

**M14. fetch_data.sh's closing recommendation sets WIN=256, which run_full_unfrozen.sh silently overrides with WIN=96** *(unverified)*  
`coupling` · harness · fetch_data.sh:75 vs run_full_unfrozen.sh:67  
fetch_data.sh ends by printing the exact command to run next: `DATA_DIR=$OUT CORPUS_CAP=100000000 STREAM_LEN=80000000 WIN=256 BATCH_W=16 ACCUM=4 bash run_full_unfrozen.sh`. DATA_DIR, CORPUS_CAP, BATCH_W and ACCUM reach the child through the inherited environment, but WIN is re-assigned on run_full_unfrozen.sh's own env line, which wins. The user gets a 96-byte window while believing they asked for 256, and nothing says so.

**M15. run_cl_test.sh part 3 asks for a 2,000,000-byte stream against the 2,000,000-byte default corpus cap, with DISK_STREAM off** *(unverified)*  
`coupling` · harness · run_cl_test.sh:17 and run_cl_test.sh:34-46  
STREAM=${STREAM_LEN:-2000000} and none of the three self_organize.py invocations sets CORPUS_CAP or DISK_STREAM. Each corpus is therefore truncated at 2 MB and the stream is materialised from that truncation. The same omission preflight.sh lists as a known past failure.

**M16. fetch_40g.sh `status` reports progress against GB's default, not against the pull actually in flight** *(unverified)*  
`wrong-measurement` · harness · fetch_40g.sh:19, :38, :40  
GB is read fresh on every invocation and never persisted. After `GB=60 bash fetch_40g.sh`, a plain `bash fetch_40g.sh status` prints 'target  : 40 GB' and computes progress as have/(40e9) — a fetch 40 GB into a 60 GB pull reports 100%. The manifest line beside it is printed raw, so the two disagree with no note.

**M17. fetch_40g.sh, selftest.sh, harness_test.sh, rerun.sh, bench_gpu.sh, fetch_data.sh and sweep_domains.sh all depend on the caller's cwd** *(unverified)*  
`crash` · harness · fetch_40g.sh:81, selftest.sh:48-96, sweep_domains.sh:22  
Only preflight.sh, run_cl_test.sh, run_full_unfrozen.sh (and sweep_domain_grid.sh via `cd "$REPO"`) resolve their own directory. `bash /path/to/fetch_40g.sh` from anywhere else nohups a python that cannot find fetch_big.py, writes the pidfile into the wrong directory, and then reports success because the pidfile exists for the first three seconds. selftest.sh has the same exposure for all 16 relative `python3 X.py` calls and for `bash harness_test.sh`. preflight.sh:14 fixed exactly this class and left the others.

**M18. PHASE_W's declared parent is PHASES; its actual parent is the process count** *(unverified)*  
`unit-mismatch` · so-config · self_organize.py:1345, declared at :91 and :107  
Anyone reading _DERIVED or the registry comment believes PHASE_W tracks the number of phases. It tracks NP. Changing PHASES leaves PHASE_W's default untouched; adding a corpus (or losing one to the 5000-byte filter) silently changes it.

**M19. The resume-side tokenizer path guess does not match the save-side _TOK_SAVE convention** *(unverified)*  
`coupling` · so-config · self_organize.py:1010-1012 (write) vs :1216-1219 (resume read guess)  
A run started with SAVE_CKPT=runs/x writes its vocabulary to 'runs/x.dyntok.json'. Resuming with RESUME=runs/x/ckpt.pt (a supported form) computes the candidate 'runs/x/ckpt.dyntok.json', which does not exist, and falls through to the shared data/dyntok.json. The same happens for SAVE_CKPT with a trailing slash, because _ck0 is only .strip()ed while _rz is .rstrip('/')ed.

**M20. Registry defaults are mutually contradictory: the default configuration cannot run** *(unverified)*  
`other` · so-config · self_organize.py:121 and :100 (declarations), :1103-1106 (refusal)  
`python3 self_organize.py` with a clean environment exits immediately with 'TOKENIZER=1 requires DATA_MODE=real'. The registry, whose whole purpose is to be the single statement of what the system does when unconfigured, declares a combination the system refuses.

**M21. ByteComposer.maxb is hardcoded 16 and does not follow MAX_TOK** *(unverified)*  
`unit-mismatch` · so-config · self_organize.py:1441 (signature), :1549 (construction), :1487 (truncation)  
With TOK_COMPOSE=1 and MAX_TOK>16, every token longer than 16 bytes is silently truncated in its composite, so two distinct long tokens that share their first 16 bytes get IDENTICAL composites and identical starting vectors. The 'a token that shares bytes with known tokens starts out near them' property becomes 'starts out identical to them'.

**M22. TOK_COMPOSE=1 is a silent no-op on MODEL=transformer, and the coupling note asserts the opposite** *(unverified)*  
`armed-but-inert` · so-config · self_organize.py:1563-1594 (TinyTransformer), :4219 (hookup), :6038-6046 (coupling note)  
TinyTransformer has no compose attribute and forwards through s.head unconditionally, so with MODEL=transformer TOK_COMPOSE=1 nothing composite happens. The coupling block at :6038 takes the 'if TOK_COMPOSE and TOK_ANCHOR > 0' branch and prints 'a new token is held near its composite until it has APPEARED that many times' -- a statement about a mechanism that does not exist in this model.

**M23. Knobs read only in sibling modules are invisible to the registry, so the typo detector reports them as unread** *(unverified)*  
`wrong-measurement` · so-config · tokenizer.py:140 / :492 / :496 vs self_organize.py:5786-5795  
TOK_MINT_NOVEL_K is read by DynamicTokenizer.__init__ but is absent from _SPEC, so it never enters _ENV_READ. Its family prefix 'TOK' IS in _fam (from TOKENIZER, TOK_ANCHOR, ...), so setting TOK_MINT_NOVEL_K=64 makes the audit print 'NOTHING READ THESE: TOK_MINT_NOVEL_K ... This run used the DEFAULTS for whatever was meant' -- which is false; the tokenizer did read it and did use it.

**M24. String knobs other than AMP are compared case-sensitively with no normalisation or refusal** *(unverified)*  
`other` · so-config · self_organize.py:1102 / :1120 (DATA_MODE) and every other env-typed knob in the region  
DATA_MODE=Real takes the SYNTHETIC branch silently -- and then, with TOKENIZER at its default 1, hits the SystemExit at :1104 with a message that reads as if the user had asked for synthetic. Same class for SIG_MODE, MODEL, VERIFY, LR_SCHED, KEY_SRC, SIG_SPACE, EVICT, CULL_MODE, WARMSTART_MODE, TOK_PROBATION_BY, CHAIN_ROUTE: an unrecognised value falls into whichever branch is the else, rather than being refused.

**M25. The exploration cold set is index-biased, so most of the population is never explored** *(unverified)*  
`other` · so-fabric · self_organize.py:2504, :2638, :2735  
`sorted(range(N), key=use)` is a stable sort over a mostly-tied key, so the cold set is the max(8, N//16) LOWEST-INDEXED zero-use experts. Exploration therefore samples a fixed prefix of the slot array rather than the population, and high-index experts can only ever be reached once the low-index ones accrue use -- which requires them to win the argmax first.

**M26. Mid-chain spawn-by-specification can never fire under the default CHAIN_ROUTE** *(unverified)*  
`armed-but-inert` · so-fabric · self_organize.py:7337 gated on fab._hopq, filled only at :2837  
The per-hop spawn reads fab._hopq[-1]; _hopq is appended only in the transition branch and is reset only at line 2705, which the soc-loop returns before reaching. Under CHAIN_ROUTE=soc it stays the empty list it was initialised to, so the branch is dead and its print can never appear.

**M27. CHAIN_SUP deep supervision is unreachable on the default path** *(unverified)*  
`armed-but-inert` · so-fabric · self_organize.py:7003 gated on fab._hops, filled only at :2819  
Same mechanism as _hopq: _hops is populated only in the transition branch, so setting CHAIN_SUP > 0 under CHAIN_ROUTE=soc adds nothing to the loss and nothing says so at the config layer (the _termfired audit would report it, but only after a full run).

**M28. The novelty/surprise term cannot influence which expert is routed to** *(unverified)*  
`armed-but-inert` · so-fabric · self_organize.py:2361  
`s.nov(nov[:, None]).sum(-1, keepdim=True)` is a per-row scalar broadcast identically across all N expert logits, so it cancels in the softmax over experts. It survives only as a shift of experts against HALT. The class docstring and the `nb  # surprise -> routing bias` comment describe it as biasing expert selection, which it structurally cannot do on the grounded path.

**M29. HALT and the experts are scored on different scales at FAB_KEY_NORM=0** *(unverified)*  
`unit-mismatch` · so-fabric · self_organize.py:2359-2360 vs :2595-2597 and :2626-2628  
With the default FAB_KEY_NORM=0 the learned expert term is an unbounded raw dot product of two trained vectors, while the HALT logit on both chaining paths is always a normalized cosine divided by route_t. As key norms grow during training the expert side can drift arbitrarily against a bounded HALT, so the whether-to-halt decision is decided by key magnitude rather than by the query. _with_halt (society) does respect FAB_KEY_NORM; the chaining sites do not.

**M30. HALT does not gate the state update on the default path** *(unverified)*  
`armed-but-inert` · so-fabric · self_organize.py:2683  
The transition path scales the residual step by the mass that has not halted (`_alive`), which is the fix documented as "HALT NOW ACTUALLY HALTS". The soc-loop applies the mixture at full strength on every hop regardless of how much probability has already halted, so the hidden state keeps changing after the router has decided to answer.

**M31. The Fabric cull keeps the max(1, ...) ratchet the domain cull removed** *(unverified)*  
`other` · so-fabric · self_organize.py:2263  
`max(1, int(cull_frac * len(_elig)))` guarantees at least one removal per manage pass whenever the pressure gate is open and anything is eligible, regardless of how small the eligible set is -- the exact pattern the DomainAssembler documents as having ratcheted a population down to a single member and deliberately deleted.

**M32. The Voronoi radius guard does not enforce the non-overlap invariant it claims** *(unverified)*  
`untrippable-guard` · so-fabric · self_organize.py:3577-3588  
The comment states the cap exists "so acceptance regions cannot overlap and no domain can eat a neighbour whole", but the cap is DOM_RCAP x the distance to the nearest other centroid with DOM_RCAP defaulting to 2.0. At 2.0 a domain's acceptance region reaches twice as far as its nearest neighbour's centroid -- it contains that neighbour outright. Non-overlap would require DOM_RCAP <= 0.5.

**M33. DOM_CULL_EMPTY can only fire on a resumed run** *(unverified)*  
`untrippable-guard` · so-fabric · self_organize.py:3635-3642  
The empty-domain cull selects domains with no reservoir windows, but update() appends a window to a newly created domain in the same call that created it, and no other code path empties a reservoir except the resume restore. In a fresh run the mechanism is armed and structurally unable to fire, while its DID IT FIRE row tests only DOM_CULL_EMPTY and would report it as armed-and-inert without the reason.

**M34. The end-of-run report describes the default path as the transition matrix** *(unverified)*  
`wrong-measurement` · so-fabric · self_organize.py:8399-8401 and :8478  
The FABRIC section prints "CHAINING ACTIVE (the default). Mass flows expert -> expert through the transition matrix over multiple hops" and the banner prints "soft routing + transition matrix + HALT". Under CHAIN_ROUTE=soc no transition matrix, no SRC mark and no ctrl summary are ever evaluated -- each hop re-routes from scratch. Anyone reading the report attributes the results to a mechanism that did not run.

**M35. ground_update round-trips centroids through the host inside the training step** *(unverified)*  
`other` · so-fabric · self_organize.py:2417  
cent is a device buffer, but each of the FAB_CENT_TOPK updated centroids is written back with `.cpu()` (and `float(_share[_q5])` forces a sync per expert). At 8 centroids per hop and 4 hops that is dozens of device/host synchronisations per training step for a slow-moving EMA.

**M36. The stall growth trigger fires on a rising loss** *(unverified)*  
`other` · so-fabric · self_organize.py:3013  
`improving = (slow - fast)/|slow|` is negative when the loss is climbing, and the test is one-sided, so a degrading run satisfies the stall condition and grows an expert -- capacity added in answer to divergence. The GROW_CAP valve fixed exactly this for itself with an absolute-value band and documented why; PlateauGrowth.step still has the one-sided form.

**M37. `route_at` is written with a TOKEN width at a BYTE offset** *(unverified)*  
`unit-mismatch` · so-loop · self_organize.py:6811  
Under the online tokenizer, only the first WIN bytes of each ~WIN*bpt-byte window are labelled with the expert that trained on it; the remaining ~46-75% of the span stays -1. Under SIG_SPACE=tokens the array is token-length while the index is a byte position, so writes clip off the end entirely.

**M38. `_pin_prev[0] = 0` on a resume hands the capacity valve the whole resume step count in one tick** *(unverified)*  
`unit-mismatch` · so-loop · self_organize.py:5252 (`_pin_prev = [0]`) vs 7368 (`_dstep = step - _pin_prev[0]`)  
On a resume at step N, the first flush computes `_dstep = N`. If the population or vocabulary is at its soft cap on that flush, `pin_tick` adds N to a clock that started at 0, so GROW_CAP_EVERY (20000) is satisfied instantly and a soft-cap lift is 'earned' for time the run never spent pinned in this session.

**M39. The in-loop cull message compares occupancy against `fab.cap` even when the gate that ran was judged against the SOFT cap** *(unverified)*  
`wrong-measurement` · so-loop · self_organize.py:6746 and 6749-6751  
With FAB_PRESS_SOFT=1 the run prints "the UTILIZATION cull did not run: n/fab.cap = X is below FAB_PRESSURE=Y" using the hardware preallocation as the denominator, while fab.manage was actually given `cap=_cap_fab[0]`. The printed X can be far below FAB_PRESSURE while the real gate was open, or vice versa -- an explanation that contradicts the decision it is explaining.

**M40. The signature lookahead queue is not cleared at a non-DISK_STREAM epoch roll** *(unverified)*  
`coupling` · so-loop · self_organize.py:6508-6632; `_sigq = []` appears only inside the `if DISK_STREAM:` branch at 6514  
When DISK_STREAM=0, the epoch roll sets `i = 0` but leaves any queued signatures in `_sigq`. Those were encoded from windows at the END of the stream and are then popped as the signature for the FIRST window(s) of the new epoch, so domain assembly (and possibly a spurious boundary) is driven by unrelated text.

**M41. TOK_PROBATION_BY="embed" silently degrades to "use" when TOK_COMPOSE=0** *(unverified)*  
`armed-but-inert` · so-loop · self_organize.py:7601-7613  
Setting TOK_PROBATION_BY=embed without TOK_COMPOSE=1 leaves `_emb = None`, so the judging falls through to `_keep = _earned` -- the 'use' test -- with no warning anywhere. The banner prints the requested mode and the end-of-run [vocab] line says "judged by embed".

**M42. mem_selfcon is saved and restored but is always -1.0** *(unverified)*  
`recorded-never-read` · so-model · self_organize.py:5352 (save), 4971 (restore), 4060 (only writer), 8881 (only call site)  
set_selfcon is called only from selfcheck, selfcheck is called only from the end-of-run report at 8881, and every memory write resets selfcon to -1 (memory.py:492). The final checkpoint is written at 7917, before 8881, and 8946 wipes the flags again afterwards. So mem_selfcon in every checkpoint ever written is entirely -1, the restore at 4971 carries no information, and is_wrong() (which needs >10 checked entries) is a no-op on every resumed run.

**M43. A checkpoint with FEWER dynamics predictors than WORLD_N0 crashes opaquely** *(unverified)*  
`crash` · so-model · self_organize.py:4591-4598 then 4694  
The replay is `while world_fwd.n() < _want2`, which handles only the grow direction. If the checkpoint holds fewer predictors than this run builds, the loop never runs and load_state_dict raises "Missing key(s) preds.N.*" — a shape dump with no knob name, the very thing the fabric's narrowing refusal (4457-4462) was written to avoid.

**M44. holdout_bpb's `finally: model.train()` clobbers the report's enclosing eval() mode** *(unverified)*  
`coupling` · so-model · self_organize.py:5123-5124, inside the eval battery bracketed by 7953 (model.eval) and 8206 (model.train)  
report_holdout at 8028 calls holdout_bpb, whose finally block unconditionally puts the model back into TRAIN mode. Everything measured after that point in the eval battery — RETENTION at 8046+, and every later section up to 8206 — runs with the model in training mode. Inert at the default DROPOUT=0.0, live and silent the moment anyone sets DROPOUT>0, which is exactly what the memorisation section tells them to do (7990).

**M45. A resume overwrites the parent's .best checkpoint on its first probe** *(unverified)*  
`silent-overwrite` · so-model · self_organize.py:4243 (_best_bpb never restored) and 6437-6446  
_best_bpb starts [None, -1, False] on every process and nothing in the checkpoint carries it. On a resume the first learning-curve probe therefore satisfies `_best_bpb[0] is None` and writes SAVE_CKPT+".best", replacing the parent's best-by-held-out snapshot with whatever the resumed model scores at its first probe — which the file itself says is usually the post-resume Adam re-warm bump (4921-4922).

**M46. .best/.bestN snapshots point at a tokenizer file that keeps growing under them** *(unverified)*  
`coupling` · so-model · self_organize.py:5335-5337, 5344-5348  
`ck = ck + suffix` is applied to the checkpoint directory but `TOK.save(_TOK_SAVE)` always writes the BASE vocabulary path, and the ckpt records `tok_path: _TOK_SAVE` plus tok_vocab/tok_merges as of that moment. Every later save overwrites the base file with a larger vocabulary, so by the end of a run a .best checkpoint's recorded merge count no longer matches the file it names and resuming from it trips the VOCABULARY MISMATCH refusal (4380-4408). Recoverable via the printed prefix-trim, but .best is not directly resumable.

**M47. selfcheck scores every stored entry through a blind router** *(unverified)*  
`wrong-measurement` · so-model · self_organize.py:4056  
selfcheck calls fab_logits without a gist, so the zero-gist placeholder is used and the grounded router ranks the population identically for every entry. The wrongness score that gates retrieval (memory.py:520-534) is therefore computed under a routing configuration that never occurs in training — the exact defect _eval_sig/_eval_logits were introduced to remove, on a site that was not converted.

**M48. The 'cent is missing' warning is unreachable on a same-cap resume** *(unverified)*  
`untrippable-guard` · so-model · self_organize.py:4651-4671  
The _capshaped/_absent audit — whose whole purpose is to catch a cap-shaped tensor (notably `cent`, each expert's routing region) being absent from the checkpoint so restored experts "keep their adapters and lose their addresses" — is nested inside `if _wide_by:`. On a same-cap resume _fsd is just `dict(_RD["fab"])` and only the generic missing_keys line at 4690 prints, without the explanation. A guard that cannot trip on the common path is the defect class this file exists to catch.

**M49. The model state dict is loaded strictly while the fabric's is tolerant** *(unverified)*  
`crash` · so-model · self_organize.py:4635 vs 4688  
`model.load_state_dict(_msd)` uses strict=True. widen_prefix returns `dict(ck_sd)` (846:864), so any key the live model has and the checkpoint lacks is simply absent and torch raises. Adding one parameter to MiniLM/TinyTransformer therefore makes every existing checkpoint unresumable, with a raw torch error — while the fabric explicitly loads strict=False for exactly this reason and prints what did not match.

**M50. Lowering MEM_CAP on a resume silently drops the tail of the store** *(unverified)*  
`silent-overwrite` · so-model · self_organize.py:4944-4945  
`_mn = min(_mn, mem.cap)` truncates the restored entries to the first mem.cap rows IN SAVE ORDER (the order they appeared under mem.active), with no message. Every other narrowing in this path (fabric cap, model VMAX) is refused with a named SystemExit; the memory store's is not even reported.

**M51. asm.comp / comp_glob, asm.tokc and the adaptive threshold histories are not checkpointed** *(unverified)*  
`recorded-never-read` · so-model · self_organize.py:5373-5382 (save) vs 3430-3442 (fields)  
The saved `asm` dict carries cent/size/last/next_id/merged/cur/visits/bornb/nb/born/act/rad/radp. It does NOT carry comp or comp_glob (so COMP_PROTECT at 3694 protects nothing after a resume until competence is re-accumulated), tokc (so the DOM_PRIOR token histogram restarts empty), or _dh/_sh (so the adaptive spawn and shift thresholds recalibrate from scratch at exactly the boundary where new material arrives).

**M52. mem.prob is not restored, disarming scan resistance at the run boundary** *(unverified)*  
`armed-but-inert` · so-model · self_organize.py:4943-4972 (no prob restore); memory.py:99, 265-275  
Every restored entry comes back with prob=False, so after a resume `_pn = int(self.prob.sum())` is 0 and `_over` is False: the probation-first eviction branch — the mechanism that makes a flood of new material eat itself rather than the working set — cannot engage until new writes alone exceed prob_frac*cap. That is precisely the moment (a new area arriving) it was written for.

**M53. The per-source high-water mark is reset by rebuild_census on every resume** *(unverified)*  
`recorded-never-read` · so-model · self_organize.py:4980; memory.py:339-342  
rebuild_census zeroes nsrc, recounts, then does `nsrc_max = maximum(nsrc_max, nsrc)` on a freshly constructed (zero) nsrc_max. The peak occupancy a source ever reached is therefore lost across a run boundary, and the starvation alarm — whose stated purpose is to distinguish "never wrote that much yet" from "HAD it and lost it" — cannot tell them apart for anything that predates the resume.

**M54. holdout_bpb swallows a mid-loop exception and returns a PARTIAL domain set** *(unverified)*  
`wrong-measurement` · so-model · self_organize.py:5077-5125  
The try wraps the whole per-domain loop, so an exception on domain 3 of 4 prints one line and returns `out` containing domains 0-2. report_holdout then computes _kept, the mean change, BWT and F over a silently reduced domain set, and _save_ckpt stores that truncated dict as the next run's baseline.

**M55. ExpertRouter's population state is not checkpointed at all** *(unverified)*  
`recorded-never-read` · so-model · self_organize.py:5383 (only experts.state_dict() is saved); 3038  
When EXPERTS=1, the checkpoint carries the ExpertBank's nn parameters but nothing of ExpertRouter's cent/use/last/born/free dictionaries. A resume therefore restores trained adapters with no centroids (every expert unroutable), no ages (all cullable or all newborn depending on defaults), no utilization, and `free = list(range(cap))` — so newly created experts overwrite trained slots. This is the identical failure the fab_born/fab_uage/fab_use fixes at 4497-4539 were written for, unfixed on the parallel population. Latent: EXPERTS defaults to 0.

**M56. POPULATION CHURN's net growth subtracts the environment's FAB_N0 from a population that may have been restored from a checkpoint** *(unverified)*  
`unit-mismatch` · so-report · self_organize.py:8435-8440, 8478  
`_net = fab.n() - _i("FAB_N0", 2048)` uses the env knob, but on a resume `fab.n_live = max(fab.n_live, _ck_n)` so the run may start well above FAB_N0, while `fab.grown` and `fab.removed` are per-run counters (initialised in __init__ and never restored). `_chn = (fab.grown - max(0, _net)) / max(1, fab.grown)` can therefore go strongly negative and print a nonsense '% of all growth was replaced', and the FABRIC one-liner's 'N grown on plateau from FAB_N0' names a starting population the run did not have.

**M57. DID IT FIRE's fabric.rescue arms on a snapshot (`cull_ran`) while its counter is cumulative** *(unverified)*  
`armed-but-inert` · so-report · self_organize.py:8583-8586, Fabric.manage at :2234  
`s.cull_ran = cull_gate_open(...)` is reassigned on every manage() call, so at report time it holds only the LAST pass's answer. The row arms on `FAB_RESCUE > 0.0 and getattr(_fb, "cull_ran", False)`, while the count `_fb.n_rescued` is cumulative over the run. A run whose occupancy fell below FAB_PRESSURE by the end prints `off fabric.rescue -- UNREACHABLE: ... occupancy < FAB_PRESSURE` and discards a nonzero rescue count, because the print loop drops the number entirely for unarmed rows. This is the exact failure the tokenizer.mint and lr.restart rows were rewritten to avoid (both now OR in 'or the count is nonzero').

**M58. DID IT FIRE's fabric.cull_eligible reports a snapshot as if it were a run total, and its off-reason does not match its arming test** *(unverified)*  
`untrippable-guard` · so-report · self_organize.py:8590-8592, Fabric.manage at :2224  
`s.n_elig = sum(1 for i in range(s.n_live) if s.use_age(i) >= grace)` is an assignment at each manage() pass, so the audit reads the LAST pass only. A run in which thousands of experts were cull-eligible for most of its length but none at the end prints '!! ZERO fabric.cull_eligible ARMED AND INERT'. Separately, the row's `why` string ('nobody reached the use-grace, so the cull had nothing to rank') is only ever printed when the row is UNARMED, and the arming test is `_cfg("MANAGE")` — so the reason printed for MANAGE=0 describes a different cause entirely.

**M59. `_ragged` counts windows dropped from the genuineness reservoir and is never printed** *(unverified)*  
`recorded-never-read` · so-report · self_organize.py:8754, 8768  
The ragged-window guard keeps only the modal length in each domain's reservoir and accumulates the number dropped into `_ragged[0]`, with a comment saying to 'say how many were dropped rather than dying on the stack'. Nothing reads `_ragged` afterwards, so cohesion/separation/silhouette can be computed on a fraction of a domain's stored windows with no indication in the output. The condition is reachable exactly when tokens are retired mid-run.

**M60. '{genuine}/{len(live)} live domains GENUINE' uses a denominator that includes domains never evaluated** *(unverified)*  
`wrong-measurement` · so-report · self_organize.py:8756-8780  
Domains in `live` whose reservoir is empty are skipped with `continue` before cohesion is computed, and domains whose kept window list is empty are skipped again — but `len(live)` is the denominator of the printed fraction and of the '(N domains merged/culled ...)' accounting. The genuine fraction is therefore diluted by domains that were not measured, not by domains that failed the test.

**M61. 'DURING TRAINING the gate ran on N read(s)' includes the report's own retrieval reads** *(unverified)*  
`wrong-measurement` · so-report · self_organize.py:8930-8944  
`mem.n_wrong_reads` is incremented inside `Memory.read` on every call while the gate is on, including `holdout_bpb(use_mem=True)` which the retention decomposition runs earlier in this same report. The line is labelled DURING TRAINING and is the basis for the 'ZERO, AND STRUCTURALLY SO' explanation, so the denominator can be nonzero purely because the report read the store.

**M62. IS IT COMPOSING checks generated words against the FIRST corpus only** *(unverified)*  
`wrong-measurement` · so-report · self_organize.py:9668-9686  
`_voc` is built from `CORP[:1]` — one corpus, first 4 MB — while `_gw` pools words from generations seeded in every sampled process. On a multi-corpus splice (the default DOMAINS=eng,py,num,c) the Python, numeric and C continuations are checked for membership in the English word set, so '% of generated words appear in the training text' is systematically deflated and the 'the rest are word-SHAPED but novel' reading is wrong for every non-first corpus.

**M63. The memorization gap's train sample is the slice of training text immediately adjacent to the held-out tail** *(unverified)*  
`wrong-measurement` · so-report · self_organize.py:7968  
`_src = CORP[_p][max(0, SEG_LEN[_p] - len(VALC[_p])):SEG_LEN[_p]]` takes the LAST len(VALC) bytes of the train region. On a corpus written in arrival order (which the code's own comment at 1173-1180 says fetch_big.py produces) that is the material most similar to the held-out block, so the train figure is biased low against the rest of train and the train-vs-heldout gap — the number the MEMORIZING/UNDERFIT verdict is computed from — is systematically understated.

**M64. 'SAMPLED FROM' averages the last learning-curve probe over ALL processes, including absent ones, contradicting `_curve_by_step`** *(unverified)*  
`wrong-measurement` · so-report · self_organize.py:9540  
`_lastc = [b for st, _p, b, _a in _CURVE if st == max(...)]` ignores the was-active flag, while `_curve_by_step` — used a few hundred lines earlier for the unit-stable cross-check — filters on it precisely because an absent process's rise 'asks whether the model is blowing up and answers with the phase schedule' (2.51 ACTIVE to 4.64 ABSENT in the recorded case). Under PHASED the printed 'final model at X b/B on the LEARNING-CURVE probe', and hence the 'the final model is +N bits/byte worse than the best' claim, is inflated by processes that had left the stream.

**M65. The three unlearn edits are sequenced destructively, so the last one can measure a store the first one already emptied** *(unverified)*  
`coupling` · so-report · self_organize.py:9828-9853  
`_edit_test('an ACTIVE')`, `_edit_test('a FADED')` and the final whole-process UNLEARN each call `mem.delete_src` and are not undone. The final UNLEARN picks the true process with the most self-domains, which under PHASED can be the same process `_edit_test` just deleted; `rm` is then 0 and the delta ~0, and the line prints 'LOCAL' from an edit that removed nothing. The final block also runs unconditionally, outside the `if PHASED:` guard that holds the first two.

**M66. Memory probation state and reconstruction errors are not in the checkpoint** *(unverified)*  
`recorded-never-read` · subsys · self_organize.py:5349-5354 (save) vs memory.py:99, 77 (state)  
mem.prob and mem.recon are never saved. After a resume every restored entry has prob=False, i.e. is treated as already promoted, so the scan-resistance the probation region exists to provide is off until enough new writes accumulate; and the `_pn` probation census restarts from whatever the new writes produce. n_promoted / n_prob_evict / n_main_evict / _floor_blocked / n_dup_slot / n_src_underflow / n_wrong_* all restart at 0 too, so every DID IT FIRE row about memory measures only the current segment.

**M67. nsrc_max (the starvation alarm's only baseline) does not survive a resume** *(unverified)*  
`recorded-never-read` · subsys · memory.py:342 with self_organize.py:4980  
The MEMORY STARVATION alarm fires only for sources whose HIGH-WATER mark once reached the floor. nsrc_max is not checkpointed; rebuild_census sets it to `maximum(zeros, restored nsrc)`, i.e. equal to the current count. So immediately after a resume no source can be reported as having lost ground, and a domain that was driven to zero before the checkpoint is invisible to the alarm for the rest of the run.

**M68. gate_theta is not checkpointed, so the adaptive/quantile write gate re-seeds after every resume** *(unverified)*  
`recorded-never-read` · subsys · memory.py:46, 143-144 vs self_organize.py:5349-5354  
Under WRITE_QUANTILE the controller seeds gate_theta from the FIRST batch it sees and then EMAs. A resume constructs a fresh store, so gate_theta restarts at float(write_gate) and is re-seeded from the first post-resume batch — a different write rate on the same material, with nothing in the log saying so.

**M69. soft_cull is irreversible despite both docstrings calling it reversible** *(unverified)*  
`armed-but-inert` · subsys · world_model.py:82, 121-128  
alive is only ever written to 0.0; nothing in world_model.py or self_organize.py ever restores a predictor to 1.0. The routing penalty log(1e-6) is soft, so the predictor keeps consuming forward compute and gradient forever while contributing ~1e-6 of the blend, and grow() still counts it against nmax so capacity is permanently lost to it.

**M70. grow() refuses at nmax even when culled slots exist** *(unverified)*  
`untrippable-guard` · subsys · world_model.py:109  
`if s.n() >= s.nmax: return None` counts total predictors, not live ones. Once soft_cull has deactivated k predictors the population is capped at nmax with only nmax-k doing work, and the plateau trigger silently stops firing. Combined with the immediate-newborn-cull above, a run can reach nmax with almost nothing live.

**M71. world_fwd.grown is a plain int: lost on resume and inflated by the resume's own replay** *(unverified)*  
`wrong-measurement` · subsys · world_model.py:75, 111 with self_organize.py:4589-4600 and 8686  
grown is assigned as an ordinary attribute, not a buffer, so it is absent from state_dict and restarts at 0 on every resume. Worse, the resume replays grow() in a loop to rebuild the population size, and each replay increments it — so the DID IT FIRE row 'world.grow' reports the checkpoint's population size as this run's growth events.

**M72. _floor_blocked counts candidates it blocked even when the floor was then dropped for that call** *(unverified)*  
`wrong-measurement` · subsys · memory.py:374-375  
The counter is incremented before the never-deadlock escape hatch. When protection would leave too few victims, `cand` is returned unfiltered and NOTHING was actually protected — but _floor_blocked has already been credited with the full difference. The DID IT FIRE row memory.floor_block can therefore be large on a run where the floor never once changed an eviction outcome.

**M73. flag_min_w is a dead knob with a live-sounding comment** *(unverified)*  
`armed-but-inert` · subsys · memory.py:65-66  
Its comment says it gates which retrievals an entry is JUDGED on ('only JUDGE an entry on retrievals where it was a CLOSE match'). Nothing reads it — the retrieval-weight signal it belonged to was removed when wrongness became self-consistency. The three knobs beside it are explicitly documented as unused; this one is not, and cl_bench.py passes it a non-default value (0.12) on all three of its stores.

**M74. reassign_src does not grow the census table, so a merge into an unseen id makes that source invisible to the floor** *(unverified)*  
`silent-overwrite` · subsys · memory.py:637-641  
The recount is guarded by `if 0 <= _s < self.nsrc.numel()`. _commit and rebuild_census both GROW the table when an id exceeds it; reassign_src does not. If the domain manager folds b into a and `a` has never itself written to memory (or exceeds the table), the relabelled entries are active with src=a while nsrc has no bucket for a — so `has = (nsrc > 0)` is false, the merged source is never eligible for floor protection, and _unprotected's clamp maps it onto the LAST source's protection status instead.

**M75. _unprotected and delete clamp out-of-range source ids into the last census bucket** *(unverified)*  
`silent-overwrite` · subsys · memory.py:369 and memory.py:623  
Both do `.clamp(min=0, max=self.nsrc.numel() - 1)`, which is exactly the pattern rebuild_census's own docstring identifies as a re-break ('a RESUME ... then this clamped every id past the end into the last bucket'). Any src id past the table silently borrows or corrupts the last bucket's count and protection status. It is only latent because _commit normally grows the table first — which reassign_src can defeat.

**M76. After any deletion the store stops being full and eviction silently reverts to circular FIFO** *(unverified)*  
`coupling` · subsys · memory.py:242 vs memory.py:297  
The sampled/probation/floor branch is guarded on `int(self.active.sum()) >= self.cap`. delete_src (domain cull), sweep_wrong and the unlearn tests all drop the active count below cap, so until the store refills every write uses `(arange(m)+ptr) % cap` — which can overwrite still-active entries while free slots exist elsewhere, with no floor and no probation. Nothing reports that the eviction rule changed.

**M77. gate_forced claims to take the most FREQUENT candidate but iterates a novelty-sorted list** *(unverified)*  
`wrong-measurement` · subsys · tokenizer.py:308-312 with tokenizer.py:262-269  
The fail-open fallback comment says 'take the most frequent candidate clearing min_pair -- exactly what the ungated path would have chosen'. When TOK_MINT_NOVEL>0, _top has already been re-sorted by (c-seen)/(1+seen)^novel, so the fallback takes the most NOVEL candidate above min_pair. The two re-rankers were designed to compose; the fallback silently inherits one of them.

**M78. The successor cache is invalidated on len(pair), which does not change when counts do** *(unverified)*  
`unit-mismatch` · subsys · tokenizer.py:203  
_succ rebuilds only `if self._sstamp != len(self.pair)`. The training loop increments existing pair counts far more often than it introduces new keys, and maybe_grow itself zeroes counts without changing len. So H(next|a) and the p(b|a) denominator the predictability gate divides by can be arbitrarily stale relative to the numerator `self.pair[(a,b)]`, which is read live — the gate can compare a current count against an old total and produce p > 1 or a badly wrong ratio.

**M79. Retire followed by a re-mint of the same byte string creates two vocabulary ids with identical bytes** *(unverified)*  
`silent-overwrite` · subsys · tokenizer.py:328-331 with tokenizer.py:412  
_mintable rejects a candidate whose bytes are already in seq2id. retire() removes the bytes from seq2id but leaves them in id2bytes. So after a retirement the same pair can be minted again at a NEW id: seq2id then maps the bytes to the new id, the old id becomes unreachable by segmentation but is still emittable by the softmax, and the model holds two rows meaning the same string with the statistics split between them.

**M80. Loading a tokenizer silently overrides MIN_PAIR, MAX_TOK, TOK_DROPOUT and max_pairs from the file** *(unverified)*  
`silent-overwrite` · subsys · tokenizer.py:479-483 with self_organize.py:1226-1256  
On the load branch the constructor arguments all come from the saved json. VMAX is the only one the resume path explicitly repairs (with a printed message). So a resume that sets MIN_PAIR=200 or MAX_TOK=6 runs with the parent's values and nothing says so — a silent config override of exactly the kind _env's default-mismatch refusal exists to prevent, sitting one level below where that check applies.

**M81. The datastream docstring names an interface the DISK_STREAM path must not use** *(unverified)*  
`coupling` · subsys · datastream.py:3-4 vs self_organize.py:1167 and 1305-1307  
The module says the training loop's access is 'CORP[p][s:s+L] (random segments) + len(CORP[p])'. Under DISK_STREAM the mmap is deliberately NOT sliced, so len(CORP[p]) includes the held-out validation tail; the only thing keeping training off the held-out data is SEG_LEN, which is computed in self_organize. Any future caller that follows the documented interface trains on the eval set.

**M82. The held-out set is a different object depending on DISK_STREAM** *(unverified)*  
`coupling` · subsys · self_organize.py:1166-1172  
On the disk path VALC is the tail truncated to VAL_CAP (4 MB) and CORP keeps the whole corpus; on the RAM path VALC is the entire VAL_FRAC tail and CORP is physically truncated. So every held-out number — the memorization check, the anchors, ACROSS THE RUN BOUNDARY — is computed over a different amount of text depending on a knob that is nominally about where bytes live.

**M83. mem.pos points into a stream that no longer exists after a DISK_STREAM epoch boundary** *(unverified)*  
`unit-mismatch` · subsys · self_organize.py:6513 and 5440-5441 with memory.py:59 and prompt.py:94-112  
mem.pos records a byte offset into the CURRENT byte_stream. Under DISK_STREAM each epoch calls _resample(), which builds an entirely new byte_stream from fresh corpus samples, while memory entries persist across epochs. source.bin, which prompt.py's grounded recall indexes with mem_pos, is written from whatever byte_stream is current at checkpoint time. Every entry written before the final epoch therefore quotes an unrelated passage. The same failure mode is documented and fixed for the partial batch at an epoch boundary but not for the store itself.

**M84. _probe_population prints K=3 while the world it built has K=5 regimes** *(unverified)*  
`wrong-measurement` · subsys · world_model.py:206 vs world_model.py:267  
The headline of the separated-world-model verdict states the number of distinct physics regimes, and it is wrong by construction. Anyone reading the probe output will attribute the population-vs-monolithic gap to a 3-regime world.

**M85. _probe_population's two arms see different training data** *(unverified)*  
`wrong-measurement` · subsys · world_model.py:216, 233, 246-247  
The batch-index sampler uses the module-level generator g, which is created once and consumed sequentially: train(False) runs 6000 steps advancing g, then train(True) continues from the advanced state. torch.manual_seed(0) inside train() only controls weight init. So the monolithic and population arms are trained on different index sequences, and the reported 'population beats monolithic by X%' includes that confound.

**M86. selftest's 'read probe is live' passes when the read probe is OFF** *(unverified)*  
`untrippable-guard` · tests · selftest.sh:134  
The check greps the fresh log for the fixed string 'read probe'. The banner prints `| read probe OFF` when MEM_PROBE_EVERY=0 and `| read probe 64 queries every 25 steps` otherwise, so the substring is present either way. The assertion's label claims liveness it cannot establish.

**M87. selftest's 'memory floor is live' is a startup-banner grep the source itself records as having passed while the floor protected nothing** *(unverified)*  
`untrippable-guard` · tests · selftest.sh:133  
It greps for 'src floor 0.5', which is printed on line 11 of a 276-line log before training starts. It cannot distinguish a live floor from a disabled one, and self_organize.py names this check by file as the thing that kept passing through the nsrc-not-rebuilt bug.

**M88. resume_test's retention-sign mirror check is a tautology** *(unverified)*  
`untrippable-guard` · tests · resume_test.py:560-561  
`check((e - l > 0) != worse or not worse, ...)` where `worse = l > e`. When worse is False the `or not worse` arm makes it True; when worse is True then l>e so e-l<0 so the first arm is True. The condition cannot be False for any inputs. The check that is supposed to demonstrate the OLD subtraction says the opposite proves nothing.

**M89. selftest.sh cannot be run from anywhere but the repo root** *(unverified)*  
`crash` · tests · selftest.sh:48-96  
Every gate is invoked by bare filename and three of them open self_organize.py by relative path. `bash /home/user/LLM-Test/selftest.sh --quick` from /tmp fails all 16 gates with 'can't open file'. The fix already exists in this repo, one file over.

**M90. compare_test never asserts compare.py's exit code** *(unverified)*  
`recorded-never-read` · tests · compare_test.py:92-246  
`rc, out = _run(...)` appears at 13 call sites; `rc` is never read. compare.py returns 0, 1 and 2 on different paths (2 = 'no pairs to compare'), and none of that is checked. Any caller that branches on compare.py's status has no coverage.

**M91. selftest section 3's stated expected answer is wrong and unasserted** *(unverified)*  
`wrong-measurement` · tests · selftest.sh:160-164  
The comment says 'there is nothing to find -- which makes NOT SIGNIFICANT the right answer'. With one log per arm and MIN_PAIRS=3, compare.py must return NO VERDICT, and it does. The only assertion is that the literal 'P(A better)' appears, so neither the correct nor the claimed verdict is checked, and the check is satisfied by the UNPAIRED fallback rather than the paired path.

**M92. notes_check's HISTORICAL escape hatch swallows live drift** *(unverified)*  
`untrippable-guard` · tests · notes_check.py:86-90  
The regex treats any line containing 'was', 'were', 'then', 'before', 'previously', 'recorded' etc. as a historical record and skips it entirely. 31 of the 42 candidate lines in the live corpus are skipped, and 9 of those state values _SPEC contradicts. notes/07_WIP.md:499 says 'on the default VERIFY=recon' while _SPEC says 'selfcon', and is skipped only because the word 'then' appears elsewhere on the line.

**M93. notes_check does not scan notes/_evidence, contradicting its own scope claim** *(unverified)*  
`other` · tests · notes_check.py:128-131  
_live_markdown's docstring says 'Everything outside archive/ is now in scope'. os.listdir is non-recursive, so 30 .md files under notes/_evidence/ are silently excluded. Re-running the drift check over them would report 19 lines stating defaults _SPEC contradicts (FAB_NMAX=6, SOCIETY=1, CORPUS_CAP=2, MAX_DOMAINS=64, LAYERS=4...).

**M94. corpus_test section 3 claims to check build_stream and never touches it** *(unverified)*  
`wrong-measurement` · tests · corpus_test.py:112-171  
The banner reads 'THE PREDICTED PER-CORPUS SHARE MATCHES WHAT build_stream ACTUALLY DRAWS'. Both `predict` and `simulate` are hand restatements in the test file; build_stream (self_organize.py:1393) is never read, extracted or executed. The section validates the test's model of the guard against the test's model of the sampler.

**M95. domain_test can never reach the COMP_PROTECT branch** *(unverified)*  
`armed-but-inert` · tests · domain_test.py:81-98  
The Asm stub sets `comp_glob = None` and `comp = {}`, and the exec'd cull block guards competence protection on `s.comp_glob is not None`. Every domain_test case passes comp=True, but the branch is never entered, `asm.protected` is never incremented, and no check reads it. One of the two brakes in the cull block has zero coverage.

**M96. domain_test's memory stub omits the live_src semantics that set the floor divisor** *(unverified)*  
`wrong-measurement` · tests · domain_test.py:73-74  
The stub's _eligible returns 'any source with entries'. The real one returns `has & lv` where lv is live_src, and its docstring records a measured run where 125 sources held entries against 27 live domains — a 4.6x difference in the divisor `int(src_floor * cap / eligible)` that decides whether a domain is held or deleted. That divergence is invisible to the test.

**M97. harness_test's dup-knob and _SPEC checks cover 62 of ~99 defined arms** *(unverified)*  
`other` · tests · harness_test.sh:49  
The arm list is scraped with a regex requiring `ARMS="..."` on the same line as a case label, which yields 62 arms. _flags_for defines ~99. Arms like kitchen, society, vmax4k, vmax8k, nolatch, nomem, softroute and lr_075_norst are never checked for a knob set twice or a knob missing from _SPEC — which is the exact class the section exists to catch.

**M98. selftest passes with 14 armed-and-inert mechanisms and asserts nothing about them** *(unverified)*  
`armed-but-inert` · tests · selftest.sh:127-130  
The DID IT FIRE checks assert the section renders, that the audit did not throw, that no row is uncountable, and that at least one 'fired' and one 'off' row exist. They do not fail on '!! ZERO ... ARMED AND INERT'. The suite's own run reports 14, including domains.cull, domains.held, memory.wrong_block, fabric.cull, tokenizer.mint_reject and loss.TOK_ANCHOR — several of which are the exact subjects of domain_test, mem_evict_test and tok_test.

**M99. mem_evict_test inherits ambient MEM_WRONG_READ** *(unverified)*  
`coupling` · tests · mem_evict_test.py:169  
EditableMemory reads MEM_WRONG_READ from os.environ at construction and the test never sets it. `MEM_WRONG_READ=0 python3 mem_evict_test.py` exits 1. The docstring claims the section 'checks all three: the floor, the gating, and the knob', but the knob is exercised only by mutating `m.wrong_read` directly, so the env->attribute plumbing at memory.py:67 has no coverage.

**M100. The blow-up alarm's input is not filtered on the active flag, and no test covers the construction** *(unverified)*  
`wrong-measurement` · tests · self_organize.py:6433  
`_cs = [b for st, _p, b, _a in _CURVE if st == step]` averages every process at that step including ones the phase schedule is not streaming. _curve_by_step — the function resume_test §9 tests precisely for excluding absent windows, quoting a +2.13 b/B absent-window step against a 0.5 threshold — does filter. blowup_test drives blowup_stale on synthetic curves and never touches how _cs is built, so the same defect class survives at the other consumer.

**M101. compare.py prints 'SIGNIFICANT AND MEANINGFUL ... by enough to act on' immediately followed by 'NEGLIGIBLE ... not worth resolving'** *(unverified)*  
`silent-overwrite` · tools · compare.py:310-325 then compare.py:326-336  
The three-way verdict is printed before the effect-size floor is checked, so both `>>` verdict lines appear for any consistent-but-tiny effect. Reproduced with 5 paired seeds differing by 0.005 b/B: `>> SIGNIFICANT AND MEANINGFUL -- A is better, and by enough to act on.` then `>> NEGLIGIBLE -- the arms differ by 0.0050 b/B ... an effect this size would not change a decision if it were.` The word MEANINGFUL is Bouthillier's gamma sense, but nothing in the output says so.

**M102. compare.py accepts unknown flags as log filenames instead of erroring — a mistyped --metric silently reverts to the default metric** *(unverified)*  
`untrippable-guard` · tools · compare.py:198-203 (`_sides` uses ap.parse_known_args)  
parse_known_args returns unrecognised tokens, which the code treats as paths. `compare.py --metrics d_order1 A.log -- B.log` reports '--metrics has no held-out line -- EXCLUDED' and 'd_order1 has no held-out line -- EXCLUDED', then runs the whole comparison on the DEFAULT metric held_out and prints '[held_out, lower is better]' as if that were what was asked for. argparse's own unknown-argument error is bypassed.

**M103. The probe sidecar's sig_space/enc_v/use_tok/tok_path fields are written and read by nothing — self_organize.py says so in the code** *(unverified)*  
`recorded-never-read` · tools · self_organize.py:5448-5451 (`# written, not read`) consumed by probe_ckpt_geometry.py, probe_stability.py, prompt.py  
A checkpoint trained with SIG_SPACE=tokens has a signature encoder over the TOKEN alphabet (ENC_V = V). All three consumers feed it raw BYTES from S.CORP / the message string, with no check, and still print a verdict. sig_space and enc_v exist in the sidecar precisely to make that detectable. rerun.sh runs a `sig_tokens:SIG_SPACE=tokens` smoke arm, so such checkpoints do get produced.

**M104. prompt.py's GROUND=1 is silently inert unless MEM=1 is also set** *(unverified)*  
`armed-but-inert` · tools · prompt.py:223 / :234-238 / :98  
respond() checks `if GROUND and SRC is not None:` and then calls _recall, which returns [] whenever USE_MEM is false. So GROUND=1 alone changes nothing and says nothing. Verified: `GROUND=1 PROMPT=... python3 prompt.py` produced byte-identical output to the plain run, and the load banner did not mention memory. The GROUND knob is documented in the comment at :223-224 with no mention of the MEM dependency.

**M105. rerun.sh's read-back gate passes `N=16` to prompt.py, which reads no such knob** *(unverified)*  
`armed-but-inert` · tools · rerun.sh:135 against prompt.py:20-22, :168  
prompt.py's KEY=VALUE loop sets os.environ['N']='16' and nothing reads it; the generation length knob is GEN_LEN (default 200). The one automated gate that exercises the deliverable therefore generates 200 tokens while its author intended 16 — the knob is armed and inert, and levers.py cannot see it because it only audits self_organize.py.

**M106. sweep_domain_report.py reports 'K2 capped==0 — all cells clean' for a directory containing zero cells** *(unverified)*  
`untrippable-guard` · tools · sweep_domain_report.py:194-196  
`voids` is empty both when every cell passed and when nothing was parsed, and the message only distinguishes 'clean' from 'VOID'. K1 and K5 correctly say 'Stage A/D incomplete'; K2 does not. Run against an empty directory the report printed a PASS for a pre-registered kill criterion on no data at all.

**M107. sweep_domain_report.py's --pick prints nothing and exits 0 when no Stage-B cell parsed, and the sweep then substitutes a hardcoded 'winner'** *(unverified)*  
`silent-overwrite` · tools · sweep_domain_report.py:255-259 with sweep_domain_grid.sh:413-415  
When pick() returns None the --pick branch does nothing at all, so BEST is empty; sweep_domain_grid.sh then falls back to a literal `ENC_POS_MAX=1024 ENC_WARMUP=800 NEW_DIST=0.65 SHIFT_DIST=0.557` and announces it as 'Stage-B winner carried into stages R/C/D/E'. Stages R/C/D/E then all run at a config no cell measured, and every downstream verdict is about it.

**M108. sweep_domain_report.py's NP_TRUE is a module global that parse() overwrites from whichever cell log is parsed last** *(unverified)*  
`coupling` · tools · sweep_domain_report.py:69-71, consumed at :146, :203, :207, :300  
`global NP_TRUE; NP_TRUE = int(m.group(1))` runs inside per-cell parsing, so the true-class count that gates K3 ('live must be between NP_TRUE and 2*NP_TRUE') and orders the pick tiebreak is set by log filename sort order. If one cell's log is truncated before that line, NP_TRUE silently retains the previous cell's value.

**M109. sweep_domain_report.py's 'median wins/dom' threshold hardcodes STREAM_LEN=120000 and WIN=128, which Stage D deliberately varies** *(unverified)*  
`wrong-measurement` · tools · sweep_domain_report.py:298-300  
The diagnostics note computes `120000 // (128 * NP_TRUE) // 2` as the level below which 'each domain is about one splice segment'. Stage D runs cells at len 120000/240000/480000, so for two thirds of that stage the printed threshold is 2x or 4x too small and the guidance is wrong for exactly the rows the reader is comparing.

**M110. fetch_big.py's shuffle/seed resume guard cannot fire on the manifests most at risk** *(unverified)*  
`untrippable-guard` · tools · fetch_big.py:250-258  
`if _sb is not None and (...)` disables the check for any manifest written before the shuffle fields existed — i.e. every arrival-order pull, which is precisely the case where resuming with the now-default shuffle_buffer=10000 skips documents the first pass never saw and re-writes ones it did. Separately, if the datasets version cannot shuffle a stream, a.shuffle_buffer is mutated to 0 at :245 BEFORE the comparison at :251, so a manifest recording 10000 hard-exits with advice ('Pass --shuffle-buffer 10000') that this library version cannot honour.

**M111. fetch_local.py's SHARD_MB is 256 while fetch_big.py's --shard-mb default is 512, directly contradicting fetch_local.py's own load-bearing comment** *(unverified)*  
`other` · tools · fetch_local.py:30-32 vs fetch_big.py:68  
The comment says 'The shard size and the document separator match fetch_big.py exactly ... a corpus assembled here has to be indistinguishable from a downloaded one -- otherwise "eng vs py" would also be "downloaded vs local"'. SEP does match; SHARD_MB does not. Content is unaffected (open_corpus concatenates part*.txt in sorted order), but the invariant the comment asserts as the reason the file is trustworthy is false, and shard COUNT is a visible difference between a local and a downloaded corpus.

**M112. fetch_local.py has no provenance check and no cleanup, so a re-run into a populated directory can leave a mixed corpus** *(unverified)*  
`silent-overwrite` · tools · fetch_local.py:181-198 and :207-209, called from longrun.sh:895  
fetch_local always starts at part000 and never removes existing shards. longrun.sh's 'topping up' branch sets _HAVE=0 and calls it on a NON-empty directory. If the new --gb yields fewer shards than what is on disk, the stale higher-numbered shards survive, open_corpus concatenates them, and the manifest is overwritten with a byte count that describes only the new write. fetch_big.py has an explicit source-provenance refusal for exactly this failure (fetch_big.py:128-151); fetch_local.py, which wrote the lesson down, has none.

**M113. probe_signature.py carries a workaround for a self_organize bug that has since been fixed, and now double-clamps the training stream** *(unverified)*  
`other` · tools · probe_signature.py:217-229  
The docstring asserts 'BUG WORKAROUND (self_organize.py:589) -- contrastive_step bounds the ANCHOR with hi = seen - 3*WIN' and proposes 'Fix in self_organize: hi = seen - WIN - max(2*WIN, _pmax)'. That fix is now in the code verbatim. The workaround still runs, passing a reduced `seen`, so the probe trains its encoder on a shorter stream than a real run at the same ENC_POS_MAX — the clamp is applied twice. The cited line number (589) is also ~2700 lines stale.

**M114. probe_ckpt_geometry.py's verdict turns on a knife-edge at zero while printing the deciding number rounded to 2 dp** *(unverified)*  
`other` · tools · probe_ckpt_geometry.py:96, :99-109  
The three branches are msil > 0.10, msil < 0.0, else 'borderline'. My run printed 'MEAN TRUE SILHOUETTE -0.00' and then the categorical 'the encoder does NOT separate the true kinds ... fix the ENCODER'. At the printed precision +0.001 and -0.001 are the same number and produce opposite verdicts, and the docstring's own reading guide says '~ 0 or < 0 -> the encoder genuinely cannot separate', which the code does not implement.

**M115. runs.py `stale` flags FAB_NMAX as '<predates this knob>' for any run with FABRIC=0, because that row is emitted only when the fabric exists** *(unverified)*  
`untrippable-guard` · tools · runs.py:162-181 against self_organize.py:5936-5942  
FAB_NMAX appears on the EFFECTIVE line only inside `if _F0 is not None:` (_F0 is None when FABRIC=0). runs.py treats a blank parsed column as 'the run predates the knob' and appends it to the reproduce list. So every FABRIC=0 baseline in the registry is reported as needing a FAB_NMAX override it never had, and the one row type where the knob is genuinely irrelevant is the one flagged.

**M116. cl_bench.py mislabels its corpora when the size filter drops one** *(unverified)*  
`wrong-measurement` · tools · cl_bench.py:65-67  
`_CORPORA` is filtered by size and `N = len(_CORPORA)`, but the banner prints `DNAMES[:N]` — the first N NAMES, not the names of the corpora that survived. If DOMAINS=eng,py,num,c and `num` is too small, the run prints "3 domains ['eng','py','num']" while actually training on eng, py and c, and every subsequent per-domain index is off. self_organize.py fixed exactly this realignment for itself.

**M117. cl_bench.py's ESTIMATE arm measures memory-read cost at a 15x larger store than the benchmark it is estimating** *(unverified)*  
`unit-mismatch` · tools · cl_bench.py:260 vs cl_bench.py:181-182  
estimate() defaults MEM_CAP to 300000, main() to 20000. Both callers leave MEM_CAP unset in some invocations, so the 'eval+read' per-op time — explicitly described as growing with store size — is measured against a store 15x bigger than the run it prices. One knob name, three defaults across two functions in one file plus the engine's registry (200000).

**M118. probe_stability.py never checks that the two checkpoints and the probe corpora describe the same experiment** *(unverified)*  
`untrippable-guard` · tools · probe_stability.py:31-33, :85-90  
The probe corpus set comes from the ambient DOMAINS/DATA_DIR (setdefault 'eng,py,num,c'), while each checkpoint's own `domains` field is ignored. I compared two encoders trained on 'eng,py' against a four-corpus probe set and got a confident 'the two runs found SUBSTANTIALLY THE SAME partition' verdict with no warning. The only cross-checkpoint guard is WIN.


### LOW (91)

**L1. `set -e 2>/dev/null || true` silently enables errexit for the rest of a script whose header sets only `set -u`** *(unverified)*  
`other` · harness · longrun.sh:1573, :1679, :1769, :1843  
The idiom reads as 'restore the previous state' but `set -e` cannot fail, so it unconditionally turns errexit ON after the first arm/seed/run. Everything after the loops — the grid summary greps, the seeds/repeat python heredocs, the smoke tally — then runs under errexit that the file never opted into. It survives today only because each extractor pipeline ends in awk/sed (exit 0) and each bare test sits in an AND-OR list; any future non-conditional command that returns non-zero will abort the sweep between the last arm and its summary.

**L2. `_AI=1` is hand-typed while the comment two lines above claims it is computed from the DOMAINS order** *(unverified)*  
`other` · harness · longrun.sh:928-932  
The comment says 'Computed from the DOMAINS order rather than hand-typed: DOMAINS="eng,$NAME" makes the added area index 1, and a hand-written PHASE_SCHED="1|1|1|1" silently becomes wrong the moment that order changes.' The code then writes `_AI=1` as a literal. Nothing reads DOMAINS. The stated fix was not made, so the failure mode it names is still live and now looks handled.

**L3. grid's config stamp records an empty flags field, because `_cfgsig` reads ARMFLAGS and grid uses FLAGS** *(unverified)*  
`coupling` · harness · longrun.sh:97 vs longrun.sh:1550 and :1580  
`_cfgsig` interpolates `"${ARMFLAGS:-}"`, a variable only `seeds` and `repeat` set. In `grid` the arm's flag set lives in `$FLAGS`, so every grid .cfg reads `flags=`. Arm identity survives only through the log filename and through `commit=`, which means an UNCOMMITTED edit to `_flags_for` changes what an arm means without changing its signature, and the completed log is then reused as if interchangeable.

**L4. `_done` — and therefore every resume-skip and equiv.sh verdict — is false whenever SIG_MODE is not "learned"** *(unverified)*  
`untrippable-guard` · harness · longrun.sh:133 and equiv.sh:87/95  
The marker is produced by `.format(SIG_MODE)`, so an arm or ARMFLAGS setting SIG_MODE=bigram prints '(SIG_MODE=bigram -- learned = ...)' and never matches. Such a run would be re-run forever by `grid` (its complete log moved aside as .partial-N each time) and reported by equiv.sh as 'did not reach the report' despite finishing cleanly. Latent today because no arm sets SIG_MODE, but seeds/pair/ladder accept arbitrary flags and sweep_domains.sh:170 already runs SIG_MODE=bigram.

**L5. `fix_resume` sets MEM_SRC_FLOOR to its own default value** *(unverified)*  
`armed-but-inert` · harness · longrun.sh:521  
The arm comment describes it as 'Small, checkpointed, and with a memory floor and a live population so the resume has something to restore', implying the floor is being switched on. MEM_SRC_FLOOR's registry default is already 0.5, so the flag pins rather than enables. Harmless as a pin, but the arm reads as testing a condition it does not create.

**L6. selftest.sh's fresh leg passes TOKENIZER_PATH=$OUT/t.json, a file that is never read and never written** *(unverified)*  
`armed-but-inert` · harness · selftest.sh:122 and the comment at selftest.sh:139-143  
With SAVE_CKPT set, the vocabulary save target is SAVE_CKPT+'.dyntok.json'; with TOK_ONLINE=1 and no RESUME the read path is not consulted. So t.json never comes into existence. The comment nevertheless states 't.json now keeps the 256-token seed it was written with, so pointing a resume at it is a genuine mismatch and the engine says so' — describing the contents of a file that does not exist.

**L7. `repeat` writes its tokenizer artefact to a path that omits the seed, so two SEEDs collide** *(unverified)*  
`silent-overwrite` · harness · longrun.sh:1762  
The log is `${TAG}_seed${RSEED}_run$R.log` but the tokenizer is `${TAG}_run$R.dyntok.json`. `SEED=0 repeat 3` then `SEED=1 repeat 3` overwrite each other's vocabulary files. With SAVE_CKPT=0 that file IS the run's saved vocabulary, and it is the only record of what the run's tokenizer became.

**L8. `GRID_ARMS` silently overrides an explicitly-named preset** *(unverified)*  
`other` · harness · longrun.sh:1537  
`ARMS=${GRID_ARMS:-$ARMS}` runs after the case that resolves `$2`. An exported GRID_ARMS left over from an earlier command therefore makes `bash longrun.sh grid round16` run something other than round16, with the banner printing the arms it actually used but nothing saying the preset was discarded.

**L9. The grid banner prints the harness's EPOCHS even when an arm overrides it** *(unverified)*  
`wrong-measurement` · harness · longrun.sh:1538 vs longrun.sh:225  
`vmax8k` sets EPOCHS=18 and arm flags come last, so it wins — but the banner has already printed '$((G_SL/1000)) kB/epoch x $G_EP epochs each', i.e. 8. The per-arm header at longrun.sh:1552 does print the flag set, so the information is recoverable, but the summary line that names the sweep is wrong for that arm.

**L10. The default-grid comment block documents five arms the default list does not contain** *(unverified)*  
`other` · harness · longrun.sh:1050-1084 vs longrun.sh:1116-1117  
The 'WHY DOES IT DIVERGE? each arm removes one suspect' block describes frozvocab, nomem, softroute, stateq and wt_div as members of the sweep. GRID_ARMS_DEFAULT lists none of them. A reader planning around the comment expects a control that will not run.

**L11. longrun.sh's header usage block omits the five sweep subcommands the file is mostly about** *(unverified)*  
`other` · harness · longrun.sh:5-16 vs longrun.sh:1967  
The header lists pilot, pilot-add, fetch, add, run, resume, smoke and watch. grid, seeds, repeat, pair and ladder — which occupy roughly 900 of the file's 1,968 lines and are how every recorded round was run — appear only in the error-path usage string, which a user sees only after mistyping a subcommand.

**L12. fetch_data.sh depends on curl, unzip, tar and bc, none of which preflight.sh checks** *(unverified)*  
`crash` · harness · fetch_data.sh:22-23, :49-50, :69 vs preflight.sh:106-109  
preflight section 4 checks awk sed grep du sort head tail date and warns about /usr/bin/time. fetch_data.sh runs under `set -e` and needs curl, unzip, tar and bc; fetch_40g.sh needs numfmt and df; sweep_domain_grid.sh needs sha256sum; sweep_domains.sh needs column; equiv.sh needs diff and comm. A missing bc aborts fetch_data.sh at its final summary after the whole download has completed.

**L13. Under TOK_COMPOSE the MiniLM emb and head tensors are allocated, checkpointed and never used** *(unverified)*  
`recorded-never-read` · so-config · self_organize.py:1550, :1552, :1556-1562  
Both nn.Embedding(V, d) and nn.Linear(d, V) are constructed and enter the optimizer and the checkpoint, but once set_vocab has run neither receives any gradient (encode reads the composed table, forward computes 'h @ _t[0].t() + _t[1]'). At VMAX=4096, d=768 that is ~6.3M parameters counted in every reported model size and written to every checkpoint.

**L14. TOK_COMPOSE=1 with TOKENIZER=0 builds the composer and never initialises it** *(unverified)*  
`armed-but-inert` · so-config · self_organize.py:1549 vs :4219  
ByteComposer is constructed whenever TOK_COMPOSE is set, but set_vocab is only called under 'TOK_COMPOSE and USE_TOK', so with TOKENIZER=0 the composer's _idx stays None, _tbl() returns None forever, and every composer parameter (byte/pos/length/proj/bias/delta/dbias, delta alone being VMAX x d) is dead weight in the optimizer and the checkpoint.

**L15. ENC_POS_MAX below 2*WIN is silently ignored** *(unverified)*  
`silent-overwrite` · so-config · self_organize.py:3311, declared at :332 and :87  
'_pmax = max(2 * WIN, _i("ENC_POS_MAX", 2 * WIN))' means the knob can only WIDEN the positive-pair radius. Setting ENC_POS_MAX=64 at WIN=128 runs at 256 with no message. The comment above it explains only the opposite problem (values above 2*WIN used to IndexError), so a reader concludes the knob is now fully usable.

**L16. FAB_MIN_STEPS' declared default of 2 is unreachable, and only an explicit setting is refused** *(unverified)*  
`armed-but-inert` · so-config · self_organize.py:191 / :88 (declaration), :1860-1868 (override)  
With the defaults (SOCIETY=0 so the derived default is 2, CHAIN_VOTE=1) Fabric.__init__ sets s.min_steps = 0 unconditionally. The SystemExit only triggers when FAB_MIN_STEPS was explicitly set to something other than '' or '0', so the DEFAULT silently disagrees with what runs.

**L17. The unshuffled-manifest advisory can crash the run it is only supposed to warn about** *(unverified)*  
`crash` · so-config · self_organize.py:1182-1190  
The try/except covers only open()+json.load(). The following line does '_mj.get(...)' and 'int(...)' outside it, so a manifest whose shuffle_buffer is a non-numeric string, or whose top level is a list, raises AttributeError/ValueError at import with a bare traceback -- from a block whose entire output is one advisory print.

**L18. The out-of-range-process filter in build_stream cannot fire** *(unverified)*  
`untrippable-guard` · so-config · self_organize.py:1404  
'act = [a for a in act if a < NP] or list(range(NP))' is dead: PHASE_SCHED is built at :1369 from the final NP, _phases can only emit indices in 0..n-1, and _phases_env validates 'j < 0 or j >= n'. Nothing can put an out-of-range id into a phase, so neither the filter nor the all-processes fallback is reachable.

**L19. MERGE_FRAC is inert at every default configuration** *(unverified)*  
`armed-but-inert` · so-config · self_organize.py:599 / :287 (declaration), :3643 (only consumer)  
The fallback 'MERGE_FRAC * NEW_DIST' only runs when merge_dist <= 0, and MANAGE_MERGE defaults to 0.28. Worse, 0.8 * 0.35 == 0.28 exactly, so even setting MANAGE_MERGE=0 to reach the fallback produces the identical number -- MERGE_FRAC can only be observed by changing MERGE_FRAC or NEW_DIST *and* zeroing MANAGE_MERGE.

**L20. Several tokenizer knobs are never read on the branch the default configuration takes** *(unverified)*  
`armed-but-inert` · so-config · self_organize.py:1224-1226, :1256  
GROW_PASSES is unreachable at TOK_ONLINE=1 (the default); SEED_VOCAB and SEED_PASSES are unreachable at TOK_ONLINE=0; MIN_PAIR, MAX_TOK and TOK_DROPOUT are unreachable whenever the tokenizer is LOADED from disk (every resume). Setting any of them on the wrong branch is silently ignored AND produces a 'NOTHING READ THESE' line whose stated cause (a typo, or a knob from a different commit) is wrong.

**L21. EXPOSURE_MAX and EXPOSURE_SKEW cannot fire on a single-corpus run** *(unverified)*  
`armed-but-inert` · so-config · self_organize.py:5497 (guard), :5535 / :5544 (reads), :110-111 (declaration)  
Both are read only inside 'if DATA_MODE == "real" and NP > 1'. The whole-run repetition and imbalance warnings are therefore unavailable on exactly the one-corpus language-quality configuration, which is where corpus-repetition is easiest to reach accidentally.

**L22. Phase fill uses integer division and overshoots by a whole segment, so phase widths drift and the stream can be short** *(unverified)*  
`other` · so-config · self_organize.py:1402-1407  
'per = STREAM_LEN // len(PHASE_SCHED)' truncates, and each inner loop appends a whole 700-1800 byte segment past its bound, so phase k's start is the previous phase's overshoot rather than k*per. With STREAM_LEN not divisible by the phase count the final stream is shorter than STREAM_LEN, and PH_BOUNDS -- which the phase-snapshot line reads -- reflects the drifted positions.

**L23. _phases returns p aliases of a single list when n <= 1** *(unverified)*  
`coupling` · so-config · self_organize.py:1344  
'return [[0] if n else []] * p' produces p references to ONE list object. Nothing currently mutates a phase in place, so it is latent -- but any future in-place edit of PHASE_SCHED[i] silently edits every phase.

**L24. cull_gate_open's docstring names a test file that does not exist** *(unverified)*  
`other` · so-config · self_organize.py:833-834  
'Module level so manage_test.py can exercise it' -- there is no manage_test.py in the repo. The function IS tested, by curve_test.py and resume_test.py, so the pointer sends a reader to nothing while the real coverage is elsewhere.

**L25. The _SPEC type tag is recorded and never read** *(unverified)*  
`recorded-never-read` · so-config · self_organize.py:96-513 (element 0 of every tuple)  
Nothing consumes _SPEC[k][0]. It is also internally inconsistent -- 44 knobs are tagged 'env' while carrying numeric defaults (DIV_W=0.02, FAB_EXPLORE=0.15, ROUTE_T=0.1, CENT_EMA=0.02, ...) because the tag actually records the READER used at the call site, not the type. A reader treating it as a type declaration will mis-predict what _env returns.

**L26. Setting both D_MODEL and D_MODEL_B silently discards D_MODEL_B with no OVERRIDE note** *(unverified)*  
`silent-overwrite` · so-config · self_organize.py:534  
'D = _i("D_MODEL", _i("D_MODEL_B", 128))' reads D_MODEL_B eagerly and then throws the value away whenever D_MODEL is set. Both are recorded in _ENV_ASKED and both are in _ENV_READ, so the config audit reports them as read and accounted for, while only one of them affected the run. levers.py's OVERRIDE section lists only FAB_MIN_STEPS.

**L27. The per-operator routing mass is accumulated every hop and never read** *(unverified)*  
`recorded-never-read` · so-fabric · self_organize.py:2621/2632 (and :2696/:2820) returned to :6850  
An (N+1,) vector is allocated and accumulated with a `_cc.mean(0)` reduction on every hop of every step, returned as the third value, assigned to `_mass` at the call site, and never referenced again. At N=2048 that is a 2049-wide reduction over the batch four times per step for nothing.

**L28. Replication lineage and mutation scale are written and never read** *(unverified)*  
`recorded-never-read` · so-fabric · self_organize.py:2137-2138  
s.parent (child -> parent) and s.mutscale (child -> mutation multiplier) are the only record of ancestry and of how far each newborn jumped, and nothing anywhere reads either. s.parent is additionally NOT renumbered by remove(), which swaps slot indices, so even if something started reading it the mapping would be stale after the first cull.

**L29. deepened and _spawn_typ are recorded for a report that never reads them** *(unverified)*  
`recorded-never-read` · so-fabric · self_organize.py:2536, :1995  
`s.deepened.append((step, s.depth_now))` is described as "for the report" and has no reader; `s._spawn_typ` is stored alongside `_spawn_gap` as "WHY it did or did not fire" but only `_spawn_gap` is printed, so the report shows the gap with no scale to compare it against.

**L30. grow() leaves stale fast/slow error EMAs on a reused slot** *(unverified)*  
`other` · so-fabric · self_organize.py:2149  
grow() clears use, comp and contrib for the slot it is about to occupy but not ef/es, so a newborn can inherit a dead expert's error history (remove() also leaves ef/es behind when it removes the top slot). spawn_from clears all five, so the two birth paths disagree.

**L31. The sustained-error cull loop lacks the out-of-range guard the utilization loop has** *(unverified)*  
`other` · so-fabric · self_organize.py:2236-2242  
The loop iterates a list built from the pre-removal n_live while remove() shrinks n_live, so later indices can exceed the live range. A remove() called on an out-of-range index would copy the last live expert into a dead slot and decrement n_live, silently deleting a live expert. It is unreachable only by accident: remove() moves the dict entries away from the tail, so failing() returns False for those indices.

**L32. spawn_from poisons the identity cache for the step it runs on** *(unverified)*  
`other` · so-fabric · self_organize.py:1978-1980 with :1950-1952  
spawn_from calls _ids inside torch.no_grad(), which writes detached tensors into _kcl/_kc and stamps _kstep with the current step. When it declines to spawn it does not clear the cache, so the routing pass later in that same step reuses no-grad identities and the eemb/A/B gradient channel through routing is cut for that step (it fires once per MANAGE_EVERY).

**L33. Exploration pays an O(N log N) sort every hop even when no row explores** *(unverified)*  
`other` · so-fabric · self_organize.py:2638 and :2735  
The cold-set sort over the whole population is computed before the per-row exploration draw, so at N=2048 and 4 hops the training step sorts 2048 entries four times per step regardless of whether any row is actually explored (the draw is 15% per row).

**L34. The soc-loop never resets _votelg, so a head-less walk leaves the previous walk's logits standing** *(unverified)*  
`other` · so-fabric · self_organize.py:2686 vs :2700  
The transition branch clears s._votelg at the top of the walk; the soc branch only assigns it when head is not None. A walk called without a head (the contribution counterfactual) therefore leaves the previous walk's logits in place, and the consumer at :6896 tests only `fab._votelg is not None`. Harmless in the current call order, but it makes a stale-logits read a one-line change away.

**L35. Stale comment claims the regression/stall cooldown collision is unfixed** *(unverified)*  
`other` · so-fabric · self_organize.py:2917-2921  
The block comment says "STILL BROKEN ... REGRESSION and stall share ONE cooldown through s.last, and stall keeps re-arming it ... Not fixed here", while the code twenty lines below gives REGRESSION its own last_regr clock and tests it before every shared gate. Two comments in the same class now describe opposite states of the same mechanism.

**L36. `_collapsed[0]` records the step of domain collapse but nothing ever reads it** *(unverified)*  
`recorded-never-read` · so-loop · self_organize.py:4347 (init), 6706-6707 (only write)  
The step at which the domain partition collapsed is stored and never surfaced; only the truthiness is used, as a once-only latch for the printed alarm. A post-mortem cannot ask when the partition died.

**L37. `_cyc_seen` is declared with a stated purpose and is never read or written again** *(unverified)*  
`recorded-never-read` · so-loop · self_organize.py:4737 (comment), 4740 (init)  
The comment describes a mechanism ('the cycle index the loop last acted on, so the decision is taken once per boundary') that does not exist; restart detection is done by rate-rising comparison against `_lr_prev` instead. A reader looking for per-cycle bookkeeping finds a variable that implies it is there.

**L38. The COUPLINGS header comment names three couplings; the code emits none for the third** *(unverified)*  
`other` · so-loop · self_organize.py:5988-5996 vs the `_cpl` appends at 6002-6115  
The section header says "Three do:" and lists SOCIETY + CHAIN_ROUTE as one of them, but no `_cpl` entry covers it. A reader auditing whether every declared coupling is reported will find the declaration and no matching COUPLING line.

**L39. The typo net can only catch a misspelling in the SUFFIX of a knob, never in its family token** *(unverified)*  
`untrippable-guard` · so-loop · self_organize.py:5786-5789  
`FAB_NMXA` is caught; `FAV_NMAX`, `FABRIK_NMAX`, or a single-token typo like `EPOCH` for `EPOCHS` are not -- the family token itself is the key, so the one class of typo the net cannot see is a typo in the part it matches on.

**L40. The stale comment at 6657-6659 describes an initialisation that no longer exists** *(unverified)*  
`other` · so-loop · self_organize.py:6658 vs 5281  
The comment says `_fired["retok"]` has a "-1e9 init", but `_fired` is a defaultdict whose factory and explicit seeds are all the current `step`. A reader reasoning about the lookahead clamp from this comment will reason from a value the code does not hold.

**L41. `_armed` (fabric mix/order sampling) is the one flush cadence with no `_nbwd > 0` guard** *(unverified)*  
`coupling` · so-loop · self_organize.py:6818-6820  
`fab._sample_mix` and `fab._sample_ord` are armed on the very first flush (_nbwd == 0), while the four sibling cadences at 6836, 6961, 6988 and 7325 all require `_nbwd > 0`. The first flush's diagnostic samples are taken before any backward pass has occurred.

**L42. `_bpw` used by the BENCH report can be stale at the seed vocabulary** *(unverified)*  
`wrong-measurement` · so-loop · self_organize.py:6237 (init), 6493 (refresh, RATE_EVERY only), 7811-7812 (consumer)  
A short BENCH run that never reaches a RATE_EVERY tick reports kB/s and GB/day computed from the bytes-per-window measured at the SEED vocabulary -- the exact staleness the refresh at 6493 was added to fix for the rate meter.

**L43. BEST_TRACK rescans the whole `_CURVE` list on every window** *(unverified)*  
`other` · so-loop · self_organize.py:6432-6433  
`_cs = [b for st, _p, b, _a in _CURVE if st == step]` runs once per WINDOW (the block is above the batch early-out) over a list that grows by len(VALC) entries every RATE_EVERY steps, and returns empty on all but 1-in-RATE_EVERY of them. Pure overhead in the hot path.

**L44. INFO_NULLS=0 crashes the report with ZeroDivisionError and compose_test is unguarded** *(unverified)*  
`crash` · so-model · self_organize.py:3831-3835, called at 8949  
`for _s in range(_i("INFO_NULLS", 5))` produces an empty _nl when INFO_NULLS=0, and `_null = sum(_nl) / len(_nl)` then divides by zero. compose_test at 8949 has no try/except (the very next section at 8951 does), so the whole remainder of the report is lost.

**L45. INFO_NULLS=1 makes the 2-sigma verdict a rubber stamp** *(unverified)*  
`untrippable-guard` · so-model · self_organize.py:3836, 3843  
`_sd = (sum(...) / max(1, len(_nl) - 1)) ** 0.5` is exactly 0.0 with a single permutation, so the test `_real - _null > 2 * _sd + 1e-9` reduces to "any excess above 1e-9" and prints "the partition CARRIES INFORMATION" on noise — the failure mode the multi-permutation comment at 3826-3829 was added to prevent.

**L46. compose_test can vanish from the report with no explanation** *(unverified)*  
`other` · so-model · self_organize.py:3724, 3730  
`if not wins: return` and `if vi.numel() == 0: return` produce no output at all, so the PERFORMANCE and CROSS-SEGMENT sections silently disappear — inconsistent with the explicit "CANNOT BE MEASURED" block added two paragraphs later (3788-3795) for exactly this reason.

**L47. _step0 ("the step THIS run started at") is only assigned inside the fabric branch** *(unverified)*  
`coupling` · so-model · self_organize.py:4349-4353 (declaration) vs 4487 (only assignment)  
`_step0[0] = _ck_step` sits inside `if FABRIC and _RD.get("fab_cfg"):`. A resume with FABRIC=0, or from a checkpoint saved with FABRIC=0 (fab_cfg is None), leaves _step0 at 0 while step starts at the chain-wide resume step — so any age-against-this-run's-span calculation reads the chain total instead.

**L48. mem.tick is not max'd against the restored last-use clock on the per-owner path** *(unverified)*  
`coupling` · so-model · self_organize.py:4963 vs 4970  
The global path does `mem.tick = max(int(_RD.get("mem_tick", 0)), int(mem.last[:_mn].max()))`; the per-owner path does only `mem.tick = int(_RD.get("mem_tick", 0))`. A checkpoint whose mem_tick is behind its stored `last` values leaves the clock behind the entries it is supposed to order.

**L49. _decompose's memory-blended probe mutates the store's eviction state** *(unverified)*  
`coupling` · so-model · self_organize.py:5100-5101, 5134; memory.py:553-559  
holdout_bpb(use_mem=True) calls mem.read, which index_adds into `use`, clears `prob` for every hit, and stamps `last`. The @no_rng_drift decorator protects only the RNG stream, not the store. Report-time only today (the only use_mem=True call is from _decompose at 5134, reached from 8028), so the damage is confined to metrics computed after it.

**L50. The optimizer moment restore does not verify that the module composition matches the checkpoint** *(unverified)*  
`coupling` · so-model · self_organize.py:4702-4707, 4934-4942  
_base is built from model + experts + fab + recon + world_enc + world_fwd + world_proj in a fixed order, and om.load_state_dict is attempted whenever nothing widened. torch validates group counts and per-group parameter counts, not identities — so a resume that changes EXPERTS, VERIFY=recon or WORLD_FEEDBACK while leaving the total parameter count in a group unchanged would attach moments to the wrong tensors, the outcome the code explicitly refuses to risk two lines away (4899-4902).

**L51. fab_logits decodes through model.head while MiniLM.forward decodes through the composed byte table** *(unverified)*  
`coupling` · so-model · self_organize.py:1562 vs 4006/4023/4030/4043  
Under TOK_COMPOSE=1 the model's own forward uses `h @ table.t() + bias`, but every fabric path (and halt_blend) uses model.head. Training goes through model.head (6889, 6899), so fab_logits agrees with training — but compose_test (3727) and generate's non-fab branch (3865) call model(x) and therefore decode through a different output layer than the one being trained. Latent: TOK_COMPOSE defaults to 0.

**L52. source.bin is written non-atomically after the atomic checkpoint replace** *(unverified)*  
`other` · so-model · self_organize.py:5438-5441  
ckpt.pt and probe.pt are written to .tmp and os.replace'd; source.bin is opened and written in place afterwards. A kill between the ckpt replace and the source.bin write leaves a valid checkpoint beside a truncated or stale corpus file that retrieval positions point into.

**L53. SIGNATURE SPACE and SPECIALIZATION call training-stream windows 'held-back' / 'held-out'** *(unverified)*  
`wrong-measurement` · so-report · self_organize.py:9093/9104 and 9128-9131/9180  
SIGNATURE SPACE encodes the FIRST 200 windows of `stream` and prints '{len(_sw2)} held-back windows'. SPECIALIZATION uses `eval_win`, drawn from `stream`, and prints 'win at least one of {len(_bw)} held-back windows'. Both are training text. A reader comparing these against the genuinely held-out sections has no way to know from the output which is which.

**L54. Report-time forward passes can append to `fab._ord` / `fab._rmix` if the last training step left the sampling flags armed** *(unverified)*  
`coupling` · so-report · self_organize.py:6819-6820, 2649, 2765-2766, 2370  
`fab._sample_mix` and `fab._sample_ord` are set each training step from a cadence expression and are never cleared before the report. If the final flush step armed them, the report's own `fab(...)` calls (the EXPERT INDEPENDENCE busiest-expert probe at 9000-9003, the FABRIC mass probe at 9055) and `fab.society(...)` (SUFFICIENCY at 9488) would append eval samples into the run-wide CHAIN ORDER and ROUTING MIX statistics.

**L55. The memorization headline prints a pooled mean with the standard error of a different (per-window) mean** *(unverified)*  
`wrong-measurement` · so-report · self_organize.py:7980-7988  
`_tr`/`_va` are means over domains of a byte-pooled bits/byte; `_tse`/`_vse` are standard errors of the unweighted per-window mean pooled across domains (`_mu_se` returns both and the code discards the mean). The printed '+/-' therefore does not belong to the printed number, and the '>> a difference smaller than ~2*(_tse+_vse) is inside this instrument's noise' rule is applied to a value the interval was not computed for.

**L56. MEMORIZATION's current-verdict line is binary while the guidance beside it is three-way** *(unverified)*  
`untrippable-guard` · so-report · self_organize.py:7989-7991  
The printed rule says gap<~0.3 UNDERFIT and gap>~0.5 MEMORIZING, leaving 0.3-0.5 deliberately unclassified; the verdict then prints UNDERFIT for everything at or below 0.5. A run at gap 0.45 is told 'more data/passes, not regularization' by a line whose own guidance does not claim that band is underfit.

**L57. tokenizer.mint_reject reads TOK.gate_skipped directly, so a non-tokenizer run reports '?' rather than off** *(unverified)*  
`other` · so-report · self_organize.py:8676-8679  
`_tk_rej` is defined with a `if USE_TOK else 0` guard, but the row itself passes `lambda: TOK.gate_skipped`. With USE_TOK=0, TOK is None, the lambda raises, the count becomes None and the row prints '? tokenizer.mint_reject -- NO COUNTER'. The arming test `_cfg("TOK_ONLINE")` reads the env knob, which can still be 1 while TOKENIZER=0, so the row lands in the `_blind` list ('a missing counter is indistinguishable from a mechanism that never ran') for a configuration where the mechanism structurally cannot exist.

**L58. On the TOK_ONLINE=0 path the memorization check indexes a token list with byte offsets** *(unverified)*  
`unit-mismatch` · so-report · self_organize.py:7968, 8005  
With TOKENIZER=1 and TOK_ONLINE=0, `CORP` is replaced by token lists at 1286 while `SEG_LEN` was computed as byte lengths at 1167-1172 and `VALC` stays bytes. `CORP[_p][SEG_LEN[_p] - len(VALC[_p]):SEG_LEN[_p]]` then slices a token list with byte offsets (start index typically past the end), and `_units(TOK, USE_TOK, _src)` re-segments already-segmented token ids as if they were bytes. The likely outcome is an empty `_tb`, which suppresses the entire MEMORIZATION/ANCHORS block silently (the `if _vb and _tb:` guard).

**L59. The wrongness precision/recall denominators mix active and all-slot counts** *(unverified)*  
`wrong-measurement` · so-report · self_organize.py:8890-8896  
`tb = int((sr == 99).sum())` counts slots whose src is 99 without ANDing `mem.active`, while `flg = int(iw.sum())` counts only active flagged entries (is_wrong ANDs active). Recall `fb/tb` and precision `fb/flg` are therefore computed against differently-scoped populations. The VERIFY branch a few lines above uses the consistent form `(mem.src == 99) & mem.active`.

**L60. is_wrong / is_unverified compute their adaptive threshold over INACTIVE entries too** *(unverified)*  
`wrong-measurement` · subsys · memory.py:584-591 and memory.py:603-608  
`checked = self.selfcon >= 0` (resp. recon) is not intersected with `active` before taking the median and MAD; only the final mask is. delete() leaves selfcon/recon untouched on deactivated slots, so a store that has just swept or culled computes its median+k*MAD partly over entries that no longer exist, shifting the threshold for the ones that do.

**L61. delete() does not clear the probation flag, so deleted slots keep inflating the probation census** *(unverified)*  
`wrong-measurement` · subsys · memory.py:612-628 vs memory.py:268  
`_pn = int(self.prob.sum())` counts every slot with prob=True, active or not. A deactivated slot keeps prob=True from its last write, so after a delete_src the probation region looks larger than it is and `_over` trips more readily than the store warrants.

**L62. read() returns hit indices and retrieval weights that every product call site discards** *(unverified)*  
`recorded-never-read` · subsys · memory.py:509 with self_organize.py:3870, 5101, 8838  
The signature is (dist, conf, hit_idx, weights). All three product call sites unpack as `dist, _cf, _, _`, and the probe call sites discard the whole tuple. hit and wfull are computed (an extra (B,topk) allocation per read) and never read outside cl_bench and mem_evict_test — they are the inputs flag_min_w was written for.

**L63. read()'s softmax temperature tau is not a knob** *(unverified)*  
`other` · subsys · memory.py:509  
tau defaults to 0.1 and no call site anywhere in the live tree passes it, so the sharpness of the retrieval vote — which directly sets how much a single neighbour dominates the returned distribution — is a hardcoded constant that no ablation can reach.

**L64. seg() is defined twice; the first definition is dead** *(unverified)*  
`other` · subsys · tokenizer.py:389-392 and tokenizer.py:394-401  
Two consecutive `def seg(self, blist, count=False)` bodies. The second shadows the first, so the usage-tracking variant is the one that exists and the first is unreachable. Neither is called anywhere in the live tree.

**L65. self.retired is written and never read** *(unverified)*  
`recorded-never-read` · subsys · tokenizer.py:141, 416  
retire() adds the id to a set that nothing anywhere consults — not save(), not load(), not the vocabulary report, not any test in the live tree. retire_stale(), which retires in bulk, does not even add to it, so the two retirement paths disagree about their own bookkeeping.

**L66. The maybe_grow lock protects a Counter that the live training loop mutates without it** *(unverified)*  
`armed-but-inert` · subsys · tokenizer.py:241 with self_organize.py:6794  
maybe_grow holds self.lock 'so a background batch-prefetch thread can tally pair concurrently'. No such thread exists in the live tree (self_organize imports no threading and spawns no Thread); the pair tally is written inline at self_organize.py:6794 without the lock. The lock is therefore pure overhead and, if a prefetch thread is ever reintroduced, the tally site is already outside it.

**L67. Two comments in maybe_grow contradict each other about whether a gate-rejected pair is zeroed** *(unverified)*  
`coupling` · subsys · tokenizer.py:292-294 vs tokenizer.py:340  
The gate section states 'A rejected pair is NOT zeroed. It is not spent ... so it stays in the tally at full count and is reconsidered.' The mintable walk builds _cands from the whole window (including pairs the gate rejected) and zeroes each one it examines. Whenever the leading candidate is unmintable, gate-rejected pairs behind it are zeroed and can never be reconsidered.

**L68. h_pmin_seen grows without bound** *(unverified)*  
`other` · subsys · tokenizer.py:234  
_predictable appends one float per candidate judged, for the whole run, purely so the end-of-run report can take a median. With TOK_MINT_GATE_K=1024 and a burst every GROW_EVERY steps this is a per-run list of millions of floats. Only reachable with TOK_MINT_PMIN>0 (default 0).

**L69. segment()'s merge dropout draws from the global random module** *(unverified)*  
`coupling` · subsys · tokenizer.py:190  
`random.random()` is the process-global generator, which this project otherwise guards carefully (frozen_rng / no_rng_drift exist because diagnostics were silently editing runs). With TOK_DROPOUT>0 every segmentation — including maintenance passes — consumes global draws and shifts the run. Latent only because the default is 0.0.

**L70. MmapConcat.__getitem__ silently ignores a slice step** *(unverified)*  
`other` · subsys · datastream.py:56-60  
Only key.start and key.stop are read. `corp[a:b:2]` returns the contiguous slice a..b, a different answer from the `bytes` object it is a drop-in for, with no error. The correctness probe tests random forward slices, an int index and a negative slice, but never a step.

**L71. MmapConcat never closes its files or mmaps** *(unverified)*  
`other` · subsys · datastream.py:20-36  
The file objects `f` are local and dropped; the mmaps are held in self.maps with no close(), __del__ or context-manager support. Harmless in the single long-lived run the class was written for, but any caller that constructs MmapConcat repeatedly leaks mappings.

**L72. grow()'s key is seeded from the whole batch, not the mispredicted region its docstring names** *(unverified)*  
`wrong-measurement` · subsys · world_model.py:113-118 with self_organize.py:6770  
The docstring says 'keyed at the mispredicted region'. The caller passes every latent in the batch, and grow() takes their mean, so the new predictor's routing key is the batch centroid — the point most likely to be already well served by the existing predictors, not the one that is being mispredicted.

**L73. The MEM_PER_EXPERT fallback warning describes behaviour the code does not have** *(unverified)*  
`wrong-measurement` · subsys · self_organize.py:5610-5615 vs memory.py:212  
The startup warning says 'write() has no owner argument -- every entry will land in partition 0'. In fact `if self.n_own > 1 and own is not None` is false, so _store falls through to the GLOBAL eviction path and writes anywhere across the whole n_own*quota range with self.own left at -1 — which then also breaks the per-owner restore on the next resume, since (own == o) matches none of them.

**L74. world_model.py imports os and never uses it** *(unverified)*  
`other` · subsys · world_model.py:16  
The module docstring says it is 'standalone + gated (WORLD_MODEL=0 by default in the product loop)', but the module itself reads no environment variable — all gating lives in self_organize. The import is a leftover that makes the file look self-gating when it is not.

**L75. The random-offset stream sampler can raise on a corpus barely above the drop floor** *(unverified)*  
`crash` · subsys · self_organize.py:1305 with datastream/open_corpus sizing  
`_SRNG[0].randint(0, SEG_LEN[p] - L - 1)` with L drawn from [SEG_MIN, SEG_MAX]. The corpus floor is 5000 bytes and SEG_MAX defaults to 1800, so the default is safe — but rerun.sh runs SEG_MIN=8000 SEG_MAX=20000, where any corpus between 5000 and ~21000 bytes makes the upper bound negative and randint raises.

**L76. blowup_test's constants check cannot fail** *(unverified)*  
`untrippable-guard` · tests · blowup_test.py:90  
`check(RISE is not None and STALE is not None, "both constants are module-level in the shipped source")` sits 44 lines after a `sys.exit(1)` on exactly that condition, so it is unreachable-false and adds a passing line to the report for a property already enforced.

**L77. levers.py prints an unverified OVERRIDE paragraph as if it were a finding** *(unverified)*  
`recorded-never-read` · tests · levers.py:113-117  
Four print statements assert that FAB_MIN_STEPS is forced to 0 by CHAIN_VOTE, that CHAIN_VOTE defaults to 1, that the declared default of 2 never runs, and that self_organize refuses the combination. None of it is checked against the source. If the mechanism were removed the paragraph would keep printing in the same tool whose entire purpose is catching declaration/source drift.

**L78. levers.py's _F0 guard is line-scoped** *(unverified)*  
`untrippable-guard` · tests · levers.py:142  
`if "_F0." in _code and "_F0 is not None" not in _code` excludes a whole physical line as soon as one guard appears on it. The _EFF list packs multiple tuples per line — line 5880 already holds three — so a second, UNGUARDED _F0 dereference on a line whose first reference is guarded would pass. That is exactly the AttributeError that cost a grid arm.

**L79. tok_test's clean control self-disables when the fixture changes** *(unverified)*  
`untrippable-guard` · tests · tok_test.py:102  
`check(tc.mint_rescued == 0 if tc.gate_skipped == 0 else True, ...)` reduces to `True` the moment the max_tok=16 fixture starts rejecting anything, while still printing an ok line whose message reports the counts. It is correct today only because gate_skipped happens to be 0.

**L80. compare_test's DIRECTION comment claims two opposite verdicts from one fixture; both name the same arm** *(unverified)*  
`wrong-measurement` · tests · compare_test.py:236 vs :239-252  
'Arm A is worse on the loss and therefore better on the margin -- one fixture, two opposite correct verdicts.' With a shared order-1 anchor of 3.742, B has both the lower loss and the larger margin, so BB wins under held_out and under d_order1. The direction bug is still caught (by the header string and the per-seed column), but not by the mechanism the comment describes.

**L81. ramp_test's comment about what PlateauGrowth reads is stale** *(unverified)*  
`other` · tests · ramp_test.py:38  
'the class reads only FAB_RAMP_LATCH, and the default is what we want'. It also reads FAB_GROW. The `lambda k, d=None: d` stub happens to return the right default for both, so the test is correct while its stated justification is not — and the stub will silently absorb any further knob the class starts reading.

**L82. compare.py's DIRTY-tree guard has no test** *(unverified)*  
`armed-but-inert` · tests · compare_test.py:28-36  
The `_w` fixture hardcodes '| clean |' in the [build] line, so `row["dirty"]` is always False and the warning at compare.py:222-223 never fires. compare_test's GUARDS section covers four of compare.py's five pre-comparison guards.

**L83. selftest continues asserting after the run it is asserting about has failed** *(unverified)*  
`other` · tests · selftest.sh:125, :147  
A nonzero RC from self_organize.py records one FAIL and then thirteen log greps run against a truncated log, so a single crash reports as fourteen failures with no indication which one is the cause.

**L84. self_organize.py points at a test file that does not exist** *(unverified)*  
`other` · tests · self_organize.py:833  
cull_gate_open's docstring says it is module level 'so manage_test.py can exercise it'. There is no manage_test.py. A reader looking for the coverage of the gate that hides three mechanisms is sent to a file that was never written; the real coverage is in curve_test.py and resume_test.py.

**L85. prompt.py rebinds MT from the model type to the memory-token tensor** *(unverified)*  
`silent-overwrite` · tools · prompt.py:28 and prompt.py:153  
`MT = d.get("model_type", "gru")` is used at :37 to set the MODEL env, then :153 rebinds MT to `d["mem_tok"]`. It currently works only because the first use precedes the second; any future read of the model type after line 153 gets a tensor.

**L86. probe_ckpt_geometry.py computes `med` and never reads it** *(unverified)*  
`recorded-never-read` · tools · probe_ckpt_geometry.py:86  
`med = C.masked_fill(torch.eye(...), float("nan"))` builds a masked centroid-distance matrix that appears nowhere else in the file.

**L87. probe_ckpt_geometry.py's path resolver builds a nonsense path when given a non-existent .pt** *(unverified)*  
`other` · tools · probe_ckpt_geometry.py:39-45  
`_resolve` returns `os.path.join(c, "ckpt.pt")` for anything that is not an existing .pt, so `CKPT=/x/ck.pt` reports 'no checkpoint at /x/ck.pt/ckpt.pt' — a path the user never typed.

**L88. vocab.py --list prints a header describing a token range it does not then print** *(unverified)*  
`other` · tools · vocab.py:127-131  
The header uses `lo` but the loop clamps to `max(256, lo)`. With `--from 100 --list 40` the header announces 'tokens 100..139' and the loop iterates range(256, 140) — nothing.

**L89. sweep_domain_report.py treats argv[1] as the output directory unconditionally, so a bare --pick reads a directory named '--pick'** *(unverified)*  
`other` · tools · sweep_domain_report.py:252, :255  
`out = sys.argv[1] if len(sys.argv) > 1 else "sweep_out"` runs before the --pick check, so `python3 sweep_domain_report.py --pick` globs `--pick/cells/*.log`, finds nothing, and exits 0 silently. The shipped caller passes the directory first, so this is latent.

**L90. compare.py suppresses the cross-corpus warning for --metric train, which is just as corpus-dependent as held_out** *(unverified)*  
`untrippable-guard` · tools · compare.py:224-227  
The order-1 anchor mismatch check fires only when metric == 'held_out'. A `--metric train` comparison across two corpora prints no warning at all, even though train bits/byte is not comparable across corpora either.

**L91. keystone_probe.py does not re-seed between its two arms, so the functional and surface encoders differ in initialisation as well as in objective** *(unverified)*  
`other` · tools · keystone_probe.py:20, :75  
torch.manual_seed(0)/random.seed(0) run once at import; train('func') then train('surf') consume the same RNG stream sequentially, so the surface arm starts from a different init and different data. The reported gap (0.303 in my run) mixes the objective difference with an unmatched init. The probe is also entirely unparameterised — steps=6000 and n=2000 are hardcoded.


## PART 2 — in the documentation and the archive

Claims the code contradicts, and instructions in archived docs that are still written as binding.


### CRITICAL (3)

**C1. archive/STATE.md declares itself BINDING and instructs the reader to update it every turn — an armed instruction on a frozen file** *(unverified)*  
`armed-but-inert` · archive · archive/STATE.md:3-10  
Any agent that greps the repo and lands on this file is told, in imperative form, that its protocol is binding and that it must update this ledger before responding every turn, check §2/§5 before any choice, and treat §7 as authoritative. The file has been frozen and moved to archive/; nothing enforces or reads it, and its §5 config carries FAB_N0=3 / FAB_NMAX=6 / EVICT=recency / MEM_CAP=300000 against live defaults of 2048 / 4096 / lru / 200000.

**C2. The society-not-chaining decision is stated as SETTLED and REJECTS the configuration that is now the default** *(unverified)*  
`coupling` · archive · archive/handoff/decisions/society-mode-not-chained-mixture-experts-compute-independently.md:4  
The decision file says 'The chained-mixture fabric (SOCIETY=0, legacy port) is rejected' and gives entanglement as the reason. At HEAD SOCIETY defaults to 0 and the chaining society IS the default, on an explicit later USER instruction. A rebuild that honours this decision file would reverse a user decision made six weeks later.

**C3. STATE.md §7 is headed 'authoritative' but every headline number in it is void under later invalidations** *(unverified)*  
`wrong-measurement` · archive · archive/STATE.md:579-591  
The section header reads 'Measured results (authoritative — from real GPU runs)' and states −0.0009 expert-deletion collateral, 1.967 b/B, 2.002 / +0.127 modularity, and memory contribution figures. INV-13 voids every arm comparison before 2026-08-13 because diagnostics were editing the runs; INV-02 voids every domain/coherence/bits-byte conclusion before 2026-07-29; INV-36 retracts the +0.709 fabric number that justified defaulting FABRIC on; INV-06 degrades every memory-contribution figure. A rebuild quoting §7 would re-publish retracted numbers under the word 'authoritative'.


### HIGH (10)

**H1. archive/garry/self_organize.py:565 reads FAB_N0 default 3 in a file that looks exactly like the live one** *(unverified)*  
`silent-overwrite` · archive · archive/garry/self_organize.py:565  
A repo-wide grep for FAB_N0 returns this line beside the live registry, and the wrong one is in a file with the same name and the same shape. The documented consequence: FAB_N0=3 was stated as the current default in nine notes for a week, including 00_INDEX's 'five things to know before spending any GPU time' item 1.

**H2. 07_WIP and 05_ERRORS §11 still state `LR_DECAY` defaults to 0; `_SPEC` says 1.0** *(unverified)*  
`other` · notes-num · notes/07_WIP.md:84, :146, :263; notes/05_ERRORS.md:2282 — vs self_organize.py:377  
Three separate places tell a reader the known-broken `LR_DECAY` envelope is inert ("BUILT, NEVER RUN (inert: LR_DECAY=0)", "`_SPEC` has `LR_DECAY` at **0.0**, so nothing measured is affected and nothing ever will be until someone sets it", "| `LR_DECAY` | 0.0 | never run"). It has defaulted to 1.0 since 2026-08-26, so the envelope is live on every multi-cycle schedule.

**H3. A verbatim commit quotation in 06 was silently altered to satisfy the automated drift check** *(unverified)*  
`other` · notes-num · notes/06_CONTINUAL_LEARNING.md:94  
The block quote is introduced as "worth quoting in full" from `c316813`, but reads "PHASED was 0 at the time and it had never been executed"; the commit says "PHASED defaults to 0 and it had never been executed". A file whose whole value is that quotations are checkable now contains an edited quotation with no marker.

**H4. A historical table cell in 06 was rewritten to the CURRENT default, making it factually wrong for the commit its own column names** *(unverified)*  
`unit-mismatch` · notes-num · notes/06_CONTINUAL_LEARNING.md:461  
The table is headed "default at `b92f358`" (2026-08-14) and the `FAB_N0` cell now reads "**2048** (was **3** until 2026-08-17)" — self-contradictory, since the parenthetical says the value at that date was 3. Anyone reconstructing what the one continual-learning run inherited gets the wrong founding population.

**H5. 04_RESULTS still asserts in the present tense that the default configuration is arm D and not arm B** *(unverified)*  
`other` · notes-num · notes/04_RESULTS.md:417-420, :822-823  
"HEAD's fabric defaults (`FAB_GROW=1`, `FAB_N0=3`, `FAB_NMAX=4096`) are arm D … **not arm B.** A default run today is not arm B" and "Two of them (`seedfloor_s0`, `seedfloor_s1`) are the **HEAD default configuration** at two of three seeds". `FAB_N0` has been 2048 since 2026-08-17. The drift check did not catch it because the claim is attributed to a commit, which its HISTORICAL regex exempts.

**H6. Every line citation in 09_COMMENT_AUDIT is stale; the file is now the victim of the exact failure it diagnoses** *(unverified)*  
`other` · notes-num · notes/09_COMMENT_AUDIT.md:114 and the whole of §3, §5, §7  
The file states `self_organize.py` is 7,238 lines and cites ~120 exact line ranges. The file is now 9,859 lines. Its own top-priority item, W01 at "`self_organize.py:1084-1093`" ("the single most consequential line in the file"), now points at `make_proc`, a synthetic-stream helper. §6.2 of the same file prescribes citing by heading text "because line numbers do not [survive edits], and this file has proven it twice".

**H7. 05_ERRORS §11 and 07_WIP §2.3 record E7.41 (ACROSS THE RUN BOUNDARY is weights-only) as NOT FIXED; the matched-pair fix is in the code** *(unverified)*  
`recorded-never-read` · notes-num · notes/05_ERRORS.md:2280; notes/07_WIP.md:113-121; notes/06_CONTINUAL_LEARNING.md:576-584  
Three files call this "the cheapest open item in this document" and 06 §9 makes it "Step 0 — the highest-value change in the file". At HEAD `holdout_bpb` already takes `use_mem`, the report prints `weights-only X | + memory Y | memory contributes Z`, and BWT and the Forgetting Measure are computed. Following the notes would re-implement work that exists, or leave a reader believing the project's retention metric still cannot see memory.

**H8. LITREVIEW_FINDINGS's corrected seed table applies the sqrt(2) twice, inflating every seed requirement ~2x** *(unverified)*  
`unit-mismatch` · notes-research · /home/user/LLM-Test/notes/LITREVIEW_FINDINGS.md:56-62  
The table's `d` column is already a z-score, Delta/sqrt(sigma_A^2+sigma_B^2), but the file then applies P(A>B)=Phi(d/sqrt(2)), which is only valid when d is Cohen's d = Delta/sigma with equal sigmas. P(A>B) is understated and the Noether seed counts derived from it are roughly doubled.

**H9. research_experts_routing.md states the balance loss decays to exactly zero; the code floors it at BAL_FLOOR=0.15** *(unverified)*  
`other` · notes-research · /home/user/LLM-Test/notes/research_experts_routing.md:78-79, 861-894, 988  
The file's C.12 verdict ('the decay to zero is CONTRADICTED by practice') and its self-declared 'highest-value change in this document' — replace fab_bal-with-decay and dom_ban with a loss-free per-expert bias — are both predicated on a premise that is false in current code. A reader acting on it would fix a problem that no longer exists.

**H10. RESEARCH_BRIEF_DIFFERENTIATION states FAB_GROW now defaults off; it defaults ON** *(unverified)*  
`other` · notes-research · /home/user/LLM-Test/notes/RESEARCH_BRIEF_DIFFERENTIATION.md:255  
The brief's decision table tells an external reader 'FAB_GROW now defaults off, which sidesteps the problem instead of solving it'. If growth is actually on by default, the growth pathology the brief documents (five experts born twenty steps before the end of a run) is live in the default configuration, not sidestepped — which changes the priority of the whole §2b question.


### MEDIUM (25)

**M1. handoff/README.md still lists B-direction (Q3) as one of the four decisions needing the user, contradicting its own decisions/ and open-questions/ files** *(unverified)*  
`coupling` · archive · archive/handoff/README.md:24  
The bootstrap file a blank chat is told to read FIRST presents 'B (wrong-detection) — ~1% precision every realistic run. Rec on file: cut it' as an open user decision. Both the Q3 file and the B-rename decision file mark that fork SUPERSEDED. A fresh reader following the prescribed reading order meets the retracted framing before the correction.

**M2. docs/HANDOFF.md §5 lists the management ON/OFF ablation as an open question after it was resolved** *(unverified)*  
`coupling` · archive · archive/docs/HANDOFF.md:56-57  
HANDOFF.md tells the next session that Q1 'Management ON/OFF ablation' is 'still open' and 'still owed a number'. decisions/management-bounds-domain-record-growth-not-prediction-quality.md records it as RUN and RESOLVED, and STATE.md §4 lists it under RESOLVED. Same tree, two answers.

**M3. docs/FILES.md claims garry/ and root share identical cl_bench.py and tokenizer.py; both now differ** *(unverified)*  
`other` · archive · archive/docs/FILES.md:56  
The per-file diff table says cl_bench.py, tokenizer.py, requirements.txt and run_cl_test.sh are 'identical' between the frozen snapshot and root. tokenizer.py is now 302 lines in garry against 509 live, and cl_bench.py differs by the control.py header line. Anyone using the table to decide 'I can read the garry copy instead' reads a different tokenizer.

**M4. GARRY.md states the faded-eviction problem can only be fixed by a per-domain quota — the one remedy the user rejected** *(unverified)*  
`coupling` · archive · archive/garry/GARRY.md:64-65  
The frozen milestone's 'honest limitations' section concludes 'Only an explicit per-domain quota would' fix faded knowledge being evicted. The user later rejected a strict per-domain quota outright as fighting growability; the replacement direction is memory pressure → grow experts / retrain / split. A rebuild reading GARRY.md alone would build the rejected thing.

**M5. The GRU-default decision gives a causal reason the archive's own later ledger entry refutes** *(unverified)*  
`wrong-measurement` · archive · archive/handoff/decisions/GRU-is-the-default-base-model-transformer-needs-big-batches.md:5-6  
The decision states a Transformer 'trained far worse here' because batch-1 online training does not suit it. The same tree's R40 measures the LM spans as a tie — 1.532 ms (GRU, 28.7M) vs 1.572 ms (TRF, 53.9M) — and attributes 99% of the transformer's deficit to the _model_key path running the full stack on ~1000 tiny KW=8 rows per step. The verdict (GRU stays default) survives; the stated reason does not.

**M6. The EVICT=usage finding recorded across four archive files was measured through a constant** *(unverified)*  
`wrong-measurement` · archive · archive/STATE.md:632; archive/handoff/COMMANDS.md:25,61; archive/handoff/designed-but-not-built/memory-pressure-triggers-expert-growth-or-domain-split-not-a-quota.md:4  
Four archive files state as measured fact that EVICT=usage does not protect faded knowledge 'by construction (faded ≡ least-used)'. INV-24 establishes that mem.read() was called only from eval-only paths, so `use` stayed 0 for every entry during training and every path evicted by write order whatever the knob said. The conclusion may still be right, but no run ever tested it.

**M7. ARCHIVE.md claims the only live references to the moved trees were two comments, but README.md carries four** *(unverified)*  
`recorded-never-read` · archive · ARCHIVE.md:10  
ARCHIVE.md asserts 'Nothing live imports, executes or reads any of it — checked before the move; the only references were two comments, since amended.' The claim holds for code (no live import of archive/), but the top-level README.md still directs readers to `garry/GARRY.md`, `STATE.md` (twice) and `CL_TESTBED.md` at paths that no longer exist. A reader following README lands on nothing.

**M8. The archive's decision on the full test names a harness the project stopped using a month earlier** *(unverified)*  
`other` · archive · archive/handoff/decisions/the-full-test-runs-ALL-ideas-ON-in-run_full_unfrozen.md:3-6  
A file in decisions/ — the folder reserved for settled USER calls — canonicalizes `run_full_unfrozen.sh` as THE full run. The live harness has been longrun.sh since 2026-07-25. The script still exists and still runs, so the failure is silent: a rebuild would reproduce a superseded workflow rather than error.

**M9. 07_WIP contradicts itself about the default arm within one file** *(unverified)*  
`other` · notes-num · notes/07_WIP.md:286 vs notes/07_WIP.md:242-245  
§5 item 4 says "**The default configuration is arm D**", while §3's dated RESOLVED paragraph forty lines earlier says `6380519`/`25aba88` set `FAB_N0=2048` so "the default IS arm B's population". A reader gets opposite answers depending on which section they open.

**M10. 09_COMMENT_AUDIT's MOVE count and its own reconciliation note both disagree with its table** *(unverified)*  
`other` · notes-num · notes/09_COMMENT_AUDIT.md:125, :233-235  
§2.2 records 51 MOVE blocks; §3 says "51 rows" then continues the table to M60. The reconciliation note at :233-235 claims "42 in `self_organize.py`, 3 in `tokenizer.py`, 1 in `memory.py`, 5 in `longrun.sh`". Counting the table: 51 `self_organize.py` + 3 `tokenizer.py` + 1 `memory.py` + 5 `longrun.sh` = 60. Neither 51 nor 42 is right.

**M11. 09 §5.2 S4's ENC_WARMUP_MIN premise is contradicted by `_SPEC`** *(unverified)*  
`untrippable-guard` · notes-num · notes/09_COMMENT_AUDIT.md:306  
S4 argues "At HEAD `ENC_WARMUP = 800` and `ENC_WARMUP_MIN = 3000` … so the adaptive stop is OFF in the default configuration" and prescribes a replacement comment saying "which is the DEFAULT (3000 >= 800)". `ENC_WARMUP_MIN` is 200, so `_wfloor = min(200, 800) = 200 < 799` and the adaptive stop IS reachable. Applying the prescribed comment would install a false statement.

**M12. 06 §2's zero-gist limitation is superseded by `_eval_sig`** *(unverified)*  
`other` · notes-num · notes/06_CONTINUAL_LEARNING.md:148-153  
"at `fab_logits:3232` the eval path **fabricates a zero gist** … So the number is weights-plus-fabric-without-routing-signal". `_eval_logits` now passes `gist=_eval_sig(x)`, and `_eval_sig` builds a real read-only signature under `EVAL_GIST=1` (default), falling back to the placeholder only when it cannot.

**M13. 07_WIP and 08_GLOSSARY state `_SPEC` holds 310 knobs; it holds 328** *(unverified)*  
`other` · notes-num · notes/07_WIP.md:375-382; notes/08_GLOSSARY.md:209, :687, :760, :783  
08 §1.15 presents "274 → 279 → 310" as the knob-count history and 07 §8's whole never-set analysis (223 of 310, 90 of 310) is denominated in 310. The registry has 328 keys, so both the fractions and the 90-name list are out of date; several names on the never-set list (`MEM_PROBE_EVERY`, `MEM_PROBE_N`, `FAB_LR_AMIN/_CYCLE/_GAMMA`) are described elsewhere in the same file as on-by-default mechanisms.

**M14. Six files still cite top-level paths that were moved to `archive/` on 2026-08-27** *(unverified)*  
`other` · notes-num · notes/00_INDEX.md:15-20; notes/08_GLOSSARY.md:30-33, :221-236; notes/09_COMMENT_AUDIT.md:462-470; notes/07_WIP.md:587-605; notes/02_IDEAS.md:113, :2529; notes/DOC_PLAN.md:48-52, :113-115, :333-338  
The staleness warnings themselves are stale: `STATE.md`, `CL_TESTBED.md`, `docs/`, `handoff/`, `garry/` and `legacy/` no longer exist at top level. Every pointer into `handoff/designed-but-not-built/` and `handoff/open-questions/` — the source for 07_WIP §10 and §11.2 and for 02_IDEAS' north-star paraphrase — resolves nowhere.

**M15. The arm inventory in 03 Part III and 07 §7 is denominated against 52 arms; `longrun.sh` now defines 99** *(unverified)*  
`other` · notes-num · notes/03_EXPERIMENTS.md:799-803, :810, :823; notes/07_WIP.md:330-331; notes/08_GLOSSARY.md:725  
"29 of 52 run at pilot scale, 23 never" and "52 case labels" and (in the glossary) "46 of them". The arm list has nearly doubled, so the never-run set is much larger than recorded and the glossary's 46 was already superseded by the same corpus.

**M16. 07_WIP §2.4's `main()` measurement is stale by a further 47%** *(unverified)*  
`other` · notes-num · notes/07_WIP.md:129-139  
The table gives `main()` at 3,953 lines / 574 locals at `eecb277` and frames the finding as "~1,000 lines and 78 locals in five days". `main()` is now 5,794 lines (4062–9855) in a 9,859-line file. The trend the entry exists to flag has accelerated and the recorded number understates it.

**M17. 07_WIP §4 files the GROW_CAP family as "never been set anywhere in the project's history" while §8.2 of the same file corrects exactly that claim** *(unverified)*  
`other` · notes-num · notes/07_WIP.md:261 vs notes/07_WIP.md:426-430  
The §4 table cell still reads "Also §8: all seven have **never been set anywhere in the project's history**", but the §8.2 entry it points at was corrected on 2026-08-26 to say the family drives ~20 arms and has run for over a million steps. `notes_check.py`'s own docstring names this entry as one of the two errors that motivated building the checker.

**M18. All log-derived evidence in 06, 07 and 09 rests on a `runs/` directory that does not exist and was never tracked** *(unverified)*  
`recorded-never-read` · notes-num · notes/07_WIP.md:455-469 (413 world-model readings), :613 (47 directories); notes/09_COMMENT_AUDIT.md:506 (420 logs); notes/06_CONTINUAL_LEARNING.md:420-424 (no surviving checkpoint)  
07 §9.1's correction of E8.29 — the single strongest empirical claim any of these files makes on its own authority — is unre-checkable. So are DOC_PLAN Q10 ("what did `runs/equiv_c14f876_vs_37ecb20` conclude?") and Q11 ("how many of the 481 logs are useful?").

**M19. 09 §5.1's W16/D3 finding — `nocompose` is a duplicate of `base` — is recorded in three files and still unfixed** *(unverified)*  
`armed-but-inert` · notes-num · notes/09_COMMENT_AUDIT.md:294; notes/10_HISTORY_FINDINGS.md:569-575; notes/03_EXPERIMENTS.md:842  
`longrun.sh` states "TOK_COMPOSE is now ON by default" (reverted at `be50e3a`, `_SPEC` = 0), so the `nocompose` arm changes nothing and "will read as a control" in the `ablate` and `tokens` presets — the identical defect the corpus already flagged for `pgate`.

**M20. The litreview's headline seed counts (≈9 and ≈80,000) are not reproducible from the formula it quotes** *(unverified)*  
`wrong-measurement` · notes-research · /home/user/LLM-Test/notes/_evidence/litreview/08_seeds_and_variance.md:26-36; 00_README_AND_CONTRADICTIONS.md:110-118; 15_additional_notes.md:9-12  
The file quotes Noether's formula N >= ((Phi^-1(1-alpha) - Phi^-1(beta))/(sqrt(6)*|0.5-gamma|))^2 with alpha=0.05, beta=0.2, then reports N≈9 at P(A>B)=0.949 and N≈80,000 at P=0.505. Plugging its own numbers in gives ≈5 and ≈41,000. The '≈9 paired seeds' figure is the single most-quoted number from the bundle and it is repeated in 15_additional_notes as the top-ranked action.

**M21. research_continual_memory's 'single most important fix in this document' has already been implemented** *(unverified)*  
`recorded-never-read` · notes-research · /home/user/LLM-Test/notes/research_continual_memory.md:40-43, 720-728, 932-933  
The file asserts three times that holdout_bpb() calls _eval_logits with model+fabric and no memory, so 'the headline cross-run retention number currently measures the weights, not the system', and ranks reporting both arms as priority action #1. The function now takes use_mem and is called both ways, and the difference is computed. A reader following the note re-does completed work and mistrusts a number that is now correct.

**M22. RESEARCH_BRIEF_DIFFERENTIATION gives the Fabric expert rank as 4; FAB_RANK defaults to 8** *(unverified)*  
`other` · notes-research · /home/user/LLM-Test/notes/RESEARCH_BRIEF_DIFFERENTIATION.md:268-269  
Section 4 ('Context the reader needs about this system') tells an external researcher the experts are 'A: (cap, d, r) and B: (cap, r, d) ... Rank 4 by default'. The A/B (cap,d,r) shape is the Fabric, whose rank knob is FAB_RANK=8. Rank 4 is EXPERT_R, the legacy ExpertBank's knob, which is inert when EXPERTS=0 (the default). Any scale judgement the external reader makes is off by 2x in parameter count.

**M23. research_tokenizer.md's Part C analyses a tokenizer configuration in which every gate it discusses is off by default** *(unverified)*  
`armed-but-inert` · notes-research · /home/user/LLM-Test/notes/research_tokenizer.md:32-40, 361-381, 383-398  
The file's system description and its three most substantive comparisons (the p(b|a) merge gate vs Picky BPE's IoS, probation vs Unigram pruning, LOSS_MASK_DEAD vs the glitch-token literature) all describe mechanisms whose defaults are 0. A reader takes the file as a description of what the system does; it is a description of what the system can be configured to do.

**M24. research_experts_routing describes per-expert LR as part of the design without stating it defaults off** *(unverified)*  
`armed-but-inert` · notes-research · /home/user/LLM-Test/notes/research_experts_routing.md:81-82, 835-857, 986-987  
The Fabric description lists 'Per-expert learning rates (FAB_LR_OWN): each expert on its own cosine schedule clocked from its birth step' among the population dynamics, and C.11 spends ~22 lines on it, marked UNTESTED-in-MoE with the principle SUPPORTED. FAB_LR_OWN defaults to 0, and RESEARCH_BRIEF_DIFFERENTIATION later measured it at 0.0040 b/B — an order of magnitude below the replication floor. The two notes together describe a mechanism as central that is both off and measured null.

**M25. Six of the seven research notes are absent from the 00_INDEX reading order** *(unverified)*  
`recorded-never-read` · notes-research · /home/user/LLM-Test/notes/00_INDEX.md:57-69, 93  
The reading-order table lists 01-10 plus LITREVIEW_FINDINGS.md only. EXTERNAL_RESEARCH_BRIEF.md, RESEARCH_BRIEF_DIFFERENTIATION.md and the four research_*.md surveys (3,407 lines of literature survey) appear nowhere in it; notes/_evidence/litreview/ appears only as one line under Provenance. A reader following the stated reading order never encounters the differentiation brief, which contains the project's strongest open question for goal (B).


### LOW (16)

**L1. The Fabric → Router + Compositor rename is recorded as CONFIRMED in two archive files and was never adopted** *(unverified)*  
`recorded-never-read` · archive · archive/handoff/STRUCTURES.md:7,47-51; archive/handoff/GLOSSARY.md:19-26  
STRUCTURES.md marks the names 'CONFIRMED by the user' and GLOSSARY.md declares 'Fabric — RETIRED name (2026-07-21)'. Nothing in the code, harness, runs.csv or the live notes uses Router/Compositor; 'Fabric' is the live term everywhere. A rebuild adopting the confirmed names would rename against every other artefact.

**L2. handoff/README.md's prescribed reading order has two items numbered 4** *(unverified)*  
`other` · archive · archive/handoff/README.md:11-12  
The bootstrap list for a zero-context reader runs 1, 2, 3, 4 (migrations/), 4 (STATE.md), 5, 6, 7, 8, 9, 10 — so the ordering between migrations/ and the ledger is undefined in the one document whose entire job is telling a blank chat what to read first.

**L3. 30 archive markdown files end with a stray </content> (one also with </invoke>) — generation artifacts committed as content** *(unverified)*  
`other` · archive · archive/handoff/GLOSSARY.md:70; archive/docs/FILES.md:97-98; and 28 others  
A closing XML tag from the authoring tool was written into the file body and committed. Harmless to render, but it means these files were never re-read after generation, which is exactly the review gap that let the other stale content through.

**L4. The legacy file count is stated three different ways across the archive** *(unverified)*  
`other` · archive · archive/STATE.md:115; archive/docs/FILES.md:64; archive/handoff/history/phase-01-cleanup-ledger-and-the-expanding-tokenizer.md  
STATE.md says '~57 legacy files', docs/FILES.md says '~55 files', phase-01 says 57 files were moved; the directory holds 56. Trivial in itself, but it is the same class of unverified restatement that produced the FAB_N0 incident.

**L5. notes_check.py's markdown scan does not recurse, so the anti-drift guard covers only the repo root and notes/** *(unverified)*  
`untrippable-guard` · archive · notes_check.py:128-133  
_live_markdown() iterates os.listdir(ROOT) for top-level .md and os.listdir(NOTES) for notes/*.md. Any markdown in another non-archive subdirectory (e.g. data_pilot/, .claude/, a future docs dir) states defaults invisibly to the guard that exists precisely because STATE.md slipped through an earlier narrower scan. It currently reports 20 live markdown files.

**L6. ARCHIVE.md excludes itself from the drift check while quoting two defaults** *(unverified)*  
`untrippable-guard` · archive · notes_check.py:130  
The scan skips ARCHIVE.md by name (`fn != "ARCHIVE.md"`), yet ARCHIVE.md:23-24 asserts 'The live default has been **2048** since 6380519/25aba88'. The exclusion is deliberate (the file quotes the stale 3 as an example) but it means the one live document explaining the archive can itself go stale unnoticed.

**L7. 00_INDEX says `commit_log.txt` holds 282 commits; it holds 267, and 01_TIMELINE says 267** *(unverified)*  
`other` · notes-num · notes/00_INDEX.md:85 vs notes/01_TIMELINE.md:18  
The provenance section — the part that tells a reader the record is checkable — states a count that does not match the file or the timeline's own header.

**L8. 01_TIMELINE states the commit log runs to `92a967b`; the log's newest entry is `95aa336`** *(unverified)*  
`other` · notes-num · notes/01_TIMELINE.md:18  
"267 commits on `rm-predict`, `8150f8a` 2026-07-21 → `92a967b` 2026-08-15". `92a967b` is the commit that CREATED the log and therefore cannot be in it; the log's first (newest) hash is `95aa336`. The range as stated is unverifiable against the artefact it names.

**L9. 09 asserts "`00_INDEX.md` does not yet exist"** *(unverified)*  
`other` · notes-num · notes/09_COMMENT_AUDIT.md:472  
"`00_INDEX.md` does not yet exist; when written, its staleness warning should cite this section." It exists and has since 2026-08-15; the citation it asks for was never added.

**L10. 07_WIP §1 states the tree is clean and `rm-predict` is in sync with origin, and 09 §10 states `git status --porcelain` is empty** *(unverified)*  
`other` · notes-num · notes/07_WIP.md:34-53; notes/09_COMMENT_AUDIT.md:492-506  
Both are point-in-time assertions about a working tree from 2026-08-15, written without a marker that they expire. They close `DOC_PLAN` "know NOW" #3 and satisfy the standing mitigation for E9.30 on evidence that cannot be re-checked at any later commit.

**L11. DOC_PLAN still cites the non-existent hash `4713186` three times after 06 identified it** *(unverified)*  
`other` · notes-num · notes/DOC_PLAN.md:284, :285, :309  
06 §3 explicitly records "`DOC_PLAN` cites this last mechanism as `4713186`. That hash does not exist … Recorded here so the citation can be fixed rather than re-derived." The citation was never fixed, and DOC_PLAN was edited at `0065372` after 06 was written.

**L12. 00_INDEX's reading-order line counts are wrong for four of eleven files** *(unverified)*  
`other` · notes-num · notes/00_INDEX.md:59-69  
02_IDEAS listed as 2500 (actual 2532), 05_ERRORS as 2455 (actual 2463), 07_WIP as 687 (actual 688), 08_GLOSSARY as 847 (actual 848). Harmless individually, but the table is the corpus' only self-description of its own size.

**L13. 05_ERRORS' index count (226) disagrees with its own methodology section (~180)** *(unverified)*  
`other` · notes-num · notes/05_ERRORS.md:57 vs :2440  
The header advertises "226 catalogued errors" and the per-class table sums to 226 by counting §11's 12 cross-links; the tally section then says it counted "over the ~180 entries above". The E-id sequence is also non-contiguous, so neither number can be reconstructed by counting entries.

**L14. RESEARCH_BRIEF_DIFFERENTIATION's 'thirty times below the floor' is off by ~3x** *(unverified)*  
`unit-mismatch` · notes-research · /home/user/LLM-Test/notes/RESEARCH_BRIEF_DIFFERENTIATION.md:30  
The FAB_LR_OWN row states the 0.0040 b/B effect is 'thirty times below the floor'. The floor stated in the same document is 0.039 b/B, giving a ratio of 9.75x. The conclusion (the effect is far below the noise floor) survives; the number does not, and it is the kind of figure an external reader would quote.

**L15. research_lr_schedules records LR_DECAY default 0.0 = off; it is now 1.0** *(unverified)*  
`other` · notes-research · /home/user/LLM-Test/notes/research_lr_schedules.md:544  
The project-configuration block that grounds all of Part C states 'LR_DECAY envelope (default 0.0 = off)'. The default is now 1.0 — the file's own C.3 item 1 recommendation, adopted. Reading Part C as current would lead someone to think the envelope is inert and to re-run an argument that is settled.

**L16. research_continual_memory's eviction table does not contain the current default eviction mode** *(unverified)*  
`other` · notes-research · /home/user/LLM-Test/notes/research_continual_memory.md:32, 636-650  
The Part 0 table and the C.3 mapping enumerate evict="recency" (circular FIFO) and evict="usage" (sampled LFU with write-count decay) as the global options, with true LRU appearing only in the partitioned n_own>1 path. The current global default is EVICT=lru. Every C.3 recommendation is therefore aimed at a policy set that no longer includes the one actually running.


## PART 3 — HISTORICAL: found and fixed during the project

Recovered from the full chat history. Every one is already fixed. They are here because the bug CLASS is what recurs -- this list is the regression suite the rebuild must not fail.


### CRITICAL (46)

**C1. Utilization cull, spare and rescue silently unreachable in every run for several commits** *(historical — fixed)*  
`untrippable-guard` · chat-a · Fabric.manage() early return in self_organize.py; introduced by commit 6380519 (FAB_N0 3 -> 2048)  
`if s.n_live <= 2 or (s.n_live / max(1, s.cap)) < pressure: return culled, spared` sits above FAB_RESCUE and the utilization spare. With FAB_N0=2048 against FAB_NMAX=4096, occupancy is 0.50 against FAB_PRESSURE=0.75, so the gated route never executed once. The owner had called culling 'semicritical to our evolutionary mechanism'.

**C2. Ramp starves the REGRESSION and stall growth triggers** *(historical — fixed)*  
`untrippable-guard` · chat-a · PlateauGrowth.step() in self_organize.py  
The ramp re-fires every cool//8 = 187 steps and each firing sets s.last, so the `t - s.last < s.cool` gate below it never opens. Direct probe: N0=3 cap=4096 to=1.0 gave 107 ramp / 0 REGRESSION / 0 stall. On the old default the continual-learning growth path was unreachable by construction.

**C3. Capacity valve pin clock counted flushes, not steps (16x slow at BATCH_W=16)** *(historical — fixed)*  
`unit-mismatch` · chat-a · pin_tick() below the batch early-out in self_organize.py; fixed in d195618, covered by cap_test.py  
Pinned from step 4495 to 48140 = 43,645 steps, clock read 2,650 (= 42,400/16). GROW_CAP_EVERY=20000 actually demanded 320,000 steps at BATCH_W=16. The report said 'reached the cap but never held it long enough' — a true sentence about a false clock.

**C4. Second units fault one layer up: fabgrow.n counts calls, gating the valve behind a step-count threshold** *(historical — fixed)*  
`unit-mismatch` · chat-a · `if GROW_CAP and fabgrow.slow is not None and fabgrow.n >= GROW_CAP_EVERY` in self_organize.py; fixed in f8c28aa by replacing it with PLATEAU_WARM=1000  
After the pin clock was fixed, the valve still lifted nothing at 42,425 pinned steps against a threshold of 20,000, because a second gate compared a flush count to a step count and demanded 320,000 steps before the valve could even be considered. The first clock masked the second.

**C5. Valve plateau test admitted every negative improvement — a run getting worse read as a stall** *(historical — fixed)*  
`untrippable-guard` · chat-a · capacity valve plateau gate; fixed in 4a29000, covered by cap_test.py using the five real lifts as the known answer  
`improving` is (slow - fast)/|slow|, so negative means the loss is climbing; the gate was `improving < GROW_CAP_PLATEAU`. A logged lift reads 'the loss has stalled (improving -0.1937 < 0.002)' — a 19% degradation authorising capacity. Three of the five expert lifts in the 0.75 GB run went to a run that was actively getting worse.

**C6. Growth call site passed the soft cap for both the ramp latch and the growth clamp — turning the valve on disarmed the mechanism that makes the valve fire** *(historical — fixed)*  
`coupling` · chat-a · `_nb = fabgrow.step(_lf, step, fab.n(), _cap_fab[0])` in self_organize.py; fixed in dc6a6dd by taking a separate `pool` argument; covered by ramp_test.py  
The latch wants the hardware pool ('is the population BUILT?'), the clamp wants the operating ceiling ('may it grow FURTHER?'). ramp_test measured: valve OFF, cap arg 8192 -> latch at 4096 -> 22 ramp events; valve ON, cap arg 3000 -> latch at 1500 -> 0 ramp events, latched on step 1. The population would have sat at 2048, never reached 3000, never pinned, and the valve would have declined for 16 hours — and the symptom is indistinguishable from 'never plateaued'.

**C7. `_keep` name collision destroyed a completed 60,227-step run in its report line** *(historical — fixed)*  
`crash` · chat-a · self_organize.py:7621 in main(); fixed in 8f624e6 (renamed _bkeep, block wrapped in try/except)  
`for _st, _bb, _sl in _keep: _live[_sl] = (_st, _bb)` -> TypeError: 'int' object is not iterable. `_keep` is reused as a throwaway local in five other places in a ~7,800-line function. The arm (gc_real) had completed and produced a full result set; it died in a print. On the 0.75 GB job the same fault would have cost eleven hours.

**C8. GRID SUMMARY `curve` column grepped the per-TOKEN divergence line while the unit-stable bits/byte figure sat three lines below it in the same log** *(historical — fixed)*  
`unit-mismatch` · chat-a · longrun.sh line ~734; fixed in 4cb7f0c  
Every arm's `curve` was a units artifact — minted tokens carry more bytes, so per-token loss rises mechanically while bits/byte falls. On the unit-stable metric base and mintok are both +0.000. Arithmetic: base 4.10/token / 1.97 b/B = 2.08 bytes/token; mintok 2.64 / 1.97 = 1.34. The log already printed 'NOT DIVERGING -- the per-token rise is the growing vocabulary, not the model. Judge this run on bits/byte.'

**C9. compare.py hardcoded lower-is-better for --metric d_order1, which is a margin (higher better)** *(historical — fixed)*  
`wrong-measurement` · chat-a · compare.py; fixed in 2c527d4 with LOWER_IS_BETTER map and _orient(); second sign fault in that file  
Header, P(A better), verdict sentence and three per-seed blocks all inverted and all agreeing with each other. It matters because d_order1 is the only cross-corpus-comparable column and compare.py TELLS you to switch to it whenever the anchors differ — routing you onto the one metric it got wrong.

**C10. The divergence alarm fired on 4 of 4 healthy runs, then could never fire again** *(historical — fixed)*  
`untrippable-guard` · chat-b · self_organize.py, the blow-up alarm (`_blew = [False]`, `if not _blew[0]`)  
It compared ONE probe against the best-so-far at +0.5 b/B. Across round15 it went off at steps 8,000-12,000 in every arm — on runs that went on to produce the session's best result. And because `_blew[0]` was never cleared, all four arms spent their single warning on that false positive and were then SILENT through mid-run excursions of +2.34, +2.05, +2.04 and +2.16 bits/byte.

**C11. The LR schedule was open-loop: a losing restart was re-taken identically, forever** *(historical — fixed)*  
`coupling` · chat-b · self_organize.py _lr_at / the cosine restart site  
A warm restart is a bet — give up the anneal, explore, re-anneal into something at least as good — and nothing connected that bet to its outcome. On the 0.75 GB run it lost three times and the schedule took it again at full amplitude each time, ratcheting the model from 2.030 to 2.848. Three rounds of launch-config fixes did not hold because the defect was in the schedule.

**C12. The two newest LR mechanisms were unreachable on the arms the same commits recommended, and DID IT FIRE had no LR row at all** *(historical — fixed)*  
`armed-but-inert` · chat-b · self_organize.py:4128 / 4158; longrun.sh:484, 489; the DID IT FIRE rows at 7364-7410  
704c432 added closed-loop restart damping; b990c9d, one commit earlier, fixed the same failure by setting LR_RESTARTS=0, which forces `_n, _ci = 1, 0`. Neither LR_DECAY= nor LR_RESTART_DAMP= appears anywhere in longrun.sh (0 occurrences each). And the audit built to catch "armed and inert" had 20 rows, none about the learning rate — the part of the system that has broken the most runs.

**C13. ENC_WARMUP_MIN: the registry was corrected and the call site was not — every run would have SystemExit'd for five commits** *(historical — fixed)*  
`crash` · chat-b · self_organize.py:4410 `_wfloor = min(_i("ENC_WARMUP_MIN", 3000), wu)` against registry 200  
d267864 corrected the registry (3000 -> 200) and left the read site at 3000. _env() raises SystemExit on exactly that mismatch and the encoder warmup runs in EVERY run, so every arm launched from d267864 onward would have exited immediately. Five commits shipped, none run on a GPU. levers.py checked declaration and derivation but not default agreement.

**C14. maybe_grow returned None for 'candidate rejected' as well as for 'nothing left to mint'** *(historical — fixed)*  
`untrippable-guard` · chat-b · tokenizer.py maybe_grow()  
One unmintable top pair ended the burst with thousands of pairs still above min_pair — six lines below a comment forbidding exactly that. Measured on real English: 1845/2048 (9.9% of the softmax width never minted, 3940 candidates left) and 658/4000 (83.5% dead, 1866 left). The first fix did not work: with both re-rankers off `_k` is 1, so the candidate window is a SINGLE pair and "walk to the next candidate" had nothing to walk.

**C15. The checkpoint carried fab_uage and fab_born but not fab_use, and use is the cull's only ranking key** *(historical — fixed)*  
`recorded-never-read` · chat-b · self_organize.py checkpoint save/restore; Fabric cull `order = sorted(_elig, key=lambda i: s.use.get(i, 0.0))`  
After a resume every expert reads past-grace with utilization 0.0, the stable sort degenerates to slot order, and the utilization cull removes the LOWEST-NUMBERED slots — the founders — while printing an ordinary line. Only reachable on the continual-learning path.

**C16. The memory source census (nsrc) was never rebuilt on resume, so MEM_SRC_FLOOR protected nothing** *(historical — fixed)*  
`recorded-never-read` · chat-b · memory.py nsrc (maintained incrementally in _commit); the resume block in self_organize.py  
A resume restores the arrays and sets `active` directly, never touching _commit, so nsrc stayed at the zeros a fresh store starts with. `has = (nsrc > 0)` all False, `prot` all False. Silent in the worst way: mem_evict_test.py proves the floor works, the banner prints `src floor 0.5`, selftest.sh asserts that line is present, and the mechanism is off.

**C17. compare.py could not pair a single log the project has ever produced** *(historical — fixed)*  
`recorded-never-read` · chat-b · compare.py:80 `row["seed"] = _grab(r"\bSEED=(\d+)", eff) or ...`; compare_test.py:31  
SEED was never in _EFF, so `SEED=` appears in 0 of 37 real logs. 33 of 37 get seed=None, the tool falls to the UNPAIRED path and dies with ZeroDivisionError. compare_test.py FABRICATED `SEED={seed}` into its own fixture, so the paired path passed against a format that has never existed. Reproduced on four real arms.

**C18. pilot -> pilot-add could never work: the tokenizer went to the shared path** *(historical — fixed)*  
`silent-overwrite` · chat-b · longrun.sh pilot (SAVE_CKPT set, no TOKENIZER_PATH)  
self_organize.py wrote the vocabulary to the default data/dyntok.json while pilot-add searches beside the checkpoint, so pilot-add exited 1 before touching the GPU. That is the continual-learning demo — the one thing that had never run. The same gap also broke the append-only invariant: a second pilot gets pilot_gru-2 for its checkpoint and then OVERWRITES the shared vocabulary, orphaning the first run's weights.

**C19. A corpus dropped by the 5000-byte floor did not take its name with it** *(historical — fixed)*  
`coupling` · chat-b · self_organize.py `CORP = [c for c in CORP if len(c) > 5000]` with DN left untouched  
open_corpus returns one entry per name in DOMAINS order so CORP[i] is DN[i]; filtering CORP alone desyncs them. Reproduced: DN=['eng','py'] sizes [1880, 84000] -> after filter sizes [84000], NP=1, and VALC[0] is the PYTHON corpus which report_holdout names 'eng'. ACROSS THE RUN BOUNDARY looks up the previous run's score BY NAME, so a short English corpus makes the next run compare this run's Python against last run's English and report the difference as forgetting — the number goal B rests on. Trigger is an undersized corpus, exactly what the owner hit.

**C20. A resume could not change the fabric's size: fab_cfg recorded cap/rank/dk and nothing on the restore path read them** *(historical — fixed)*  
`recorded-never-read` · chat-b · self_organize.py `_mk = fab.load_state_dict(_RD["fab"], strict=False)`; longrun.sh pilot-add / add  
fix_resume was trained at FAB_N0=256 FAB_NMAX=1024; pilot-add pins sixteen env vars and neither of those is among them, so the resume built 2048/4096 and died inside torch with five tensor shapes and no knob name. It cost a run with the tokenizer resolved, the corpus pulled and the GPU warm. Data recorded and never read.

**C21. The resume backfill could not tell 'the checkpoint did not annotate this slot' from 'this slot never existed'** *(historical — fixed)*  
`coupling` · chat-b · self_organize.py, the fab_born / fab_uage / fab_use backfill  
1525 of 2048 slots held random initialisation and were being entered as MATURE VETERANS — past grace (so cullable, on the mature per-expert LR) yet ranked mid-population in a utilization cull where they would displace genuinely trained experts. The rule 'unknown means experienced' is right for an unannotated restored slot and exactly wrong for a slot the checkpoint never had. The crash was the lucky outcome.

**C22. FAB_NMAX=4096 (the assistant's own recommendation) would have silently removed three mechanisms for the whole run** *(historical — fixed)*  
`untrippable-guard` · chat-b · cull_gate_open(n_live, cap, pressure) in self_organize.py  
Widening divides n_live/cap without touching the population: 523 experts at cap 1024 = 0.511 OPEN; the same 523 at 4096 = 0.128 SHUT; even 1046 at 4096 = 0.255 still SHUT. The utilization cull, the utilization spare and FAB_RESCUE all live behind that gate and would read ARMED AND INERT as an artefact of the cap. Worse for goal B, FAB_PRESSURE is a SETPOINT, so 4096 also invites the population toward ~1843 whether or not the new area needs the experts.

**C23. The population ramp re-armed against the widened cap and grew on no evidence** *(historical — fixed)*  
`untrippable-guard` · chat-b · self_organize.py PlateauGrowth latch `n >= s.ramp_to * _pool` judged against fab.cap; fabgrow rebuilt from env at 3905 and never checkpointed  
523 experts in a cap of 1024 have latched (523 >= 512) and the ramp exists to build the population once. Resume into any larger cap and the threshold moves out from under it — and since the controller was never in the checkpoint, every resume started ramp_done=False. Simulated on a FLAT loss: cap 2048 grew +594 from the ramp (625 total) vs 0/32 with the latch restored; cap 4096 grew +1649 vs 0/32. The ramp never reads the loss.

**C24. The regression trigger — 'the only signal continual learning has' — was structurally blind at the boundary** *(historical — fixed)*  
`coupling` · chat-b · self_organize.py PlateauGrowth `s.slow = loss if s.slow is None else ...`  
The EMAs are seeded from the first loss they see, which on a resume is the first loss on the NEW material, so `(loss - slow) > z * dev` has no jump left to detect. The file itself calls this trigger "the arrival of a new area and the only signal continual learning has", and it could not fire at the one moment an area arrives. Measured: EMAs carried across -> REGRESSION fires twice; fresh -> zero.

**C25. RETENTION had the subtraction inverted, on the line the continual-learning claim rests on** *(historical — fixed)*  
`wrong-measurement` · chat-b · self_organize.py:7446 `drift {_e - _l:+.3f}` on a lower-is-better metric  
process 0 (eng) went 2.114 -> 2.223 (WORSE) and was reported -0.109; process 1 (py) went 1.447 -> 1.103 (BETTER) and was reported +0.344, against a legend saying "positive is FORGETTING". The verdict DRIFTING printed BECAUSE Python improved. Additionally, a mean over processes lets a domain that arrived THIS run cancel an old domain's forgetting.

**C26. The cull budget was sized on n_live while the candidates came from the eligible set** *(historical — fixed)*  
`unit-mismatch` · chat-b · self_organize.py:2051 `for i in list(order[:max(1, int(cull_frac * s.n_live))]):` with `order` drawn from `_elig`  
In the real CL run n_live was 523 while only 84 were eligible: budget int(0.02*523)=10 against a correct int(0.02*84)=1. Ten removed per pass instead of one, drawn entirely from the experts that had had their chances — 159 removed against 84 grown, 523 -> 448 live WHILE ADDING A LANGUAGE, churn reading "100% of all growth was replaced rather than added". The same defect existed in the LR-boost budget.

**C27. The LM-curve verdict collapses every process to one under PHASED** *(historical — fixed)*  
`wrong-measurement` · chat-b · self_organize.py:7800 and :7811, twice: `_bp = sorted({st: b for st, _p, b, _a in _CURVE}.items())`  
_CURVE rows are (step, process, bits/byte, was_active); keying on step alone drops both the process and the active flag, so each step keeps whichever process was appended LAST — systematically the highest-indexed, i.e. the NEWEST corpus, the one that cannot have been forgotten. Reliably wrong in the direction that hides goal B's failure mode. Also, _a is discarded, so an ABSENT window can enter rise_since_min: at step 26000 it took 5.75 where the active mean is 2.12.

**C28. SPECIALIZATION partitions held-out windows with a projection that was never gradiented** *(historical — fixed)*  
`armed-but-inert` · chat-b · self_organize.py:8548, building the winner from fab.q_entry  
Both live entry paths fork to entry_logits under s.grounded, which scores with s.q_route — a different nn.Linear. ROUTE_GROUNDED defaults to 1 and the pilot ran with 1. The run's own audit prints "never gradiented -> ctrl, q_entry". So SPECIALIZATION partitions with a randomly-initialised projection and then asks whether that beats a random partition of the same sizes — it is drawn from its own null. INTERCHANGEABLE across 32 arms is thirty-two arms reading a dead input. The file even noticed the symptom (5 of 448 winners vs ROUTER SELECTION's 415) and rationalised it away as "a probe, not the run".

**C29. 'Detect-only' covered deletion but not reads: a third of the memory store was unreachable** *(historical — fixed)*  
`coupling` · chat-b · memory.py Memory.read `valid = self.active & (~self.is_wrong()) & (~self.is_unverified())`, sharing the predicate WRONG_SWEEP gates  
WRONG_SWEEP gates sweep_wrong(); read() filters on the SAME predicate. So the 63,146 genuine entries flagged at 3% precision were already excluded from every retrieval — about a third of the store unreachable, to keep 1,820 corrupt entries out of the vote, while memory was contributing +0.085 b/B and the log read as reassurance. is_wrong() also had NO DID IT FIRE row despite gating every query, and opens with `if checked.sum() > 10`, below which the whole filter is inert — inert and over-eager printed the same nothing.

**C30. A soft cap below the population freezes growth for the entire run, silently** *(historical — fixed)*  
`untrippable-guard` · chat-b · self_organize.py:4874 `_cap_fab = [int(_i("GROW_CAP_FAB0", 0)) or FAB_NMAX]` and the clamp `_nb = min(_nb, _cap_fab[0] - fab.n())`  
Once fab.n() exceeds the soft cap that expression is NEGATIVE and nothing ever grows — and nothing says so, because the trigger counts still increment and the pin counter reads exactly as it would on a population legitimately at its cap. Unreachable on a fresh run; entirely reachable now that FAB_N0 comes from the checkpoint: 523 experts against any GROW_CAP arm's GROW_CAP_FAB0=160 gives -363. Also _cap_fab is accumulated state (the valve only lifts) that was re-read from the environment on every resume.

**C31. The vocabulary was full before the second modality arrived** *(historical — fixed)*  
`untrippable-guard` · chat-b · VMAX in self_organize.py; longrun.sh pilot-add hardcoding VMAX=2048  
`grew 2048 -> 2048 (+0)` on the first-ever continual-learning run. VMAX was already filled by English, so the new language got ZERO tokens of its own and was segmented entirely with English's merges. New experts, no new tokens — half of what 'strap on another modality' means. Also, tokenizer.mint reported this as `ZERO -- ARMED AND INERT`, which reads as 'minting is broken' rather than 'the vocabulary is full'.

**C32. `longrun.sh add` — the command that runs the real experiment — could not resume at all** *(historical — fixed)*  
`armed-but-inert` · chat-c · longrun.sh add) branch, line ~866-903  
It set no TOKENIZER_PATH, so the child fell back to data/dyntok.json, minted a fresh 512-token vocabulary, and self_organize.py refused with `[resume] VOCABULARY MISMATCH` — AFTER the block had computed the correct FAB_N0 and FAB_NMAX, which were then discarded. It also hardcoded VMAX=2048 and DEVICE=cuda. The branch's own comment says it "runs the real experiment".

**C33. VALC NameError — DATA_MODE=synthetic has crashed since 2026-08-15** *(historical — fixed)*  
`crash` · chat-c · self_organize.py training loop, `if RATE_EVERY and step % RATE_EVERY == 0 and step > _s_mark and VALC:`  
VALC is built only inside `if DATA_MODE == "real":` and the loop reads it unguarded, so every synthetic run dies the first time the rate meter comes round. Introduced in d3d2bdc (2026-08-15), twelve days before this session, confirmed by merge-base. Nothing caught it because nothing runs the synthetic path: preflight.sh's END-TO-END SMOKE is the sole caller, and it reported "FAILED on CUDA" for a defect with nothing to do with the architecture — which on a GH200 sends you hunting wheels and drivers. Fixed with `VALC = []` declared before the branch.

**C34. A memory write named the same slot twice, so a count of active entries went negative** *(historical — fixed)*  
`silent-overwrite` · chat-c · memory.py — the global victim path used torch.randint (WITH replacement); the per-owner path ranked the whole block by `last`, where free slots read 0 (the oldest possible)  
Pilot A printed `s779 (-2 now, peaked 111230)`. A repeat costs twice: index assignment collapses it silently so the store holds fewer rows than the caller was told, and `_commit` decrements the displaced owner once per occurrence. Measured directly: 23 then 6 rows into a 25-slot block stored FOUR of the six and charged the source for six. This matters because nsrc is the per-source floor's only input and `nsrc > 0` is what makes a source eligible for protection at all — an undercounted source loses the protection of the floor that exists to stop it being driven to zero. On that run the floor blocked 6,728,733 of 11,677,625 writes.

**C35. DynamicTokenizer.load reconstructed vmax from the saved json, so a resumed run could not mint a single token** *(historical — fixed)*  
`armed-but-inert` · chat-c · tokenizer.py DynamicTokenizer.load; maybe_grow's first line `if vocab_size >= vmax: return None`  
pilot-add doubled VMAX to 4096 and the resume widened emb/head and printed "the tokenizer stays at 2048 tokens and now has room above it" — but the tokenizer came back capped at pilot A's 2048, full, so maybe_grow refused before forming a candidate. `tokenizer.mint 0`, `mint_reject 0` — not one token for Python, not one candidate formed, for 52,000 steps. The NON-STATIONARY table showed `vocab | 2048` at every phase. Fixed at the load path (never below what is already minted; VMAX is a hard ceiling because emb has exactly that many rows). resume_test now fails on the old code with `got 2048`.

**C36. The domain cull budget was a minimum, not a fraction — it drove the domain population to one** *(historical — fixed)*  
`untrippable-guard` · chat-c · self_organize.py domain manager, `max(1, int(DOM_CULL_FRAC * n))`  
`int(0.10 * n)` is 0 for any population under ten, so "cull at most a tenth" was "cull at least one, every manage pass, forever", and only `len(cent) <= 1` could stop it — which is exactly where it stopped, three separate times (`[manage @ 96500] merged 0 culled 1 -> 3 live domains` ... `-> 1 live domains`). Reproduced as a unit test: forty passes over a dead population settle at 9 with the fix, 1 without.

**C37. "Nobody fed this domain" was the phase schedule talking, and the cull destroyed memory the floor forbids evicting** *(historical — fixed)*  
`untrippable-guard` · chat-c · self_organize.py domain cull; calls mem.delete_src()  
`act` decays every pass and `last` only moves when a domain is fed, so under PHASE_SCHED [[0],[0],[1],[1]] every domain of the process not currently streaming trips `act < min_size AND stale` BY CONSTRUCTION within MANAGE_STALE steps of a switch. The cull then destroys entries MEM_SRC_FLOOR forbids EVICTING — while the lossless empty-cull directly above it DOES check whether the domain still owns memory. The branch that destroys everything had the weaker test. 145 culls with every guard either off or never reached looked the same as 145 healthy ones because the cull had a counter and its brakes had none.

**C38. The held-out tail was a contiguous block of the last repositories, not a sample** *(historical — fixed)*  
`wrong-measurement` · chat-c · fetch_big.py wrote documents in arrival order; VAL_FRAC holds out the LAST 5% of each corpus  
The Stack is organised by repository, so py's held-out 5% was whichever repos the stream ended on. Signature in the numbers: py held out 5.061 ± 0.560 vs in-stream 2.922 (gap 2.1 b/B, error bar 4x eng's); eng held out 2.273 ± 0.092 vs in-stream 2.303 (no gap) — eng came from fineweb-edu, shuffled upstream. Every held-out number about py (the memorization check, the anchors, ACROSS THE RUN BOUNDARY, the continual-learning claim itself) was a measurement of that block.

**C39. A resume wrote its vocabulary over the file it read the parent's from, inside runs/** *(historical — fixed)*  
`silent-overwrite` · chat-c · self_organize.py tokenizer save sites, both writing through TOKENIZER_PATH  
TOKENIZER_PATH had two jobs — read the parent's vocabulary, save this run's own. Harmless only while minting was broken; once the tokenizer-cap fix let Python mint 2048 tokens, pilot_gru_py-3 wrote 4096 merges over pilot A's 2048. The next resume died with `[resume] VOCABULARY MISMATCH -- refusing to load` naming the SAME file on both lines. This violated the owner's standing rule that runs/ must not be overwritten. Fix: a run's vocabulary goes beside its own checkpoint (SAVE_CKPT + ".dyntok.json"), tok_path records where it was WRITTEN, and a resume with SAVE_CKPT off saves no vocabulary at all.

**C40. Run banner printed the environment variable, not the effective value** *(historical — fixed)*  
`armed-but-inert` · chat-early · self_organize.py [config] banner; reported in notes/_evidence/chat/chunks/chunk_07.md:4155-4162  
A full pilot ran with `[config] ... per-expert memory ON` while MEM_PER_EXPERT required SOCIETY and the run was SOCIETY=0 — the feature was off from step 0. WORLD_GROW had the same shape. Every conclusion drawn from that run about per-expert memory measured nothing.

**C41. Learning-curve verdict read its own sign backwards and only compared two points** *(historical — fixed)*  
`wrong-measurement` · chat-early · self_organize.py LM training-curve report; chunk_07.md:4123-4145  
A 48k-step chaining pilot that had been diverging for 91% of its length (loss bottomed 3.56 @ step 5903, rose to 4.68 @ 47231) was reported as "last segment change -0.059: still FALLING = more passes/steps will help".

**C42. Modulo cadence never coincided with batch-flush steps — four subsystems silently never fired** *(historical — fixed)*  
`armed-but-inert` · chat-early · self_organize.py management cadence; chunk_08.md:3747  
`step % MANAGE_EVERY == 0` can never coincide with a batch-flush step at BATCH_W=4, so `_greach`, ROUTING MIX, CHAIN ORDER and `maybe_deepen` all silently never ran. Fixed by replacing the modulo with an `_nbwd` counter.

**C43. Fabric.remove(j) did not prune the centroid buffer** *(historical — fixed)*  
`silent-overwrite` · chat-early · Fabric.remove; user_turns.md:5020  
Removing expert j left s.cent unpruned, misrouting every expert above j for the rest of the run.

**C44. No mid-run checkpointing — a day of H100 compute produced nothing loadable** *(historical — fixed)*  
`other` · chat-early · self_organize.py checkpoint path (pre-CKPT_EVERY); chunks/chunk_02.md:1814-1822  
An end-only save meant a ~24h run that crashed at the end left no checkpoint. pyrasite failed and a gdb attach hit SIGSEGV trying to run PyRun_SimpleString while the process held CUDA with the GIL released.

**C45. Machine non-determinism invalidates every commit-to-commit comparison** *(historical — fixed)*  
`wrong-measurement` · chat-early · equiv.sh determinism self-test; user_turns.md:10207-10208  
Two runs of the SAME commit disagreed, so the DIFFERS/SAME verdicts used to validate the levers refactor could prove nothing. The seed-spread analyses that followed ("why seed 0 is so much worse than 2") sit on top of this.

**C46. Verification worked standalone (AUC 0.980) and collapsed in the product loop (0.3% precision)** *(historical — fixed)*  
`wrong-measurement` · chat-early · verification.py + self_organize.py VERIFY path; user_turns.md:573 and :2600  
The reconstruction signal scored AUC 0.980 / 100% precision@1% in the isolated console test but flagged 64 of 768 injected entries at 0.3% precision in the loop. Two wrong root causes were proposed (joint-training-on-churn, undertraining) before the base-rate wall was identified.


### HIGH (62)

**H1. Cull report line named a route that did not run, and DID IT FIRE conflated unreachable with inert** *(historical — fixed)*  
`wrong-measurement` · chat-a · cull report line and DID IT FIRE audit in self_organize.py; fixed in 95da3fe  
The line claimed 'cull under capacity pressure, bottom N% by utilization' for all 24 culls that actually came from the sustained-error route; fabric.rescue printed ARMED AND INERT, which reads as 'the idea does not work' when it means 'the run never asked'.

**H2. REGRESSION shares its cooldown with stall, so the rare important event is suppressed by the common one** *(historical — fixed)*  
`untrippable-guard` · chat-a · PlateauGrowth in self_organize.py; fixed in 383c7e5, covered by growth_test.py  
At an injected regression the machine is in state W with unexpected=True and is dropped anyway on t - s.last = 772 against cool = 1500, because s.last had been set by a routine stall 772 steps earlier. Every archived run reads '0x on a REGRESSION'.

**H3. Capacity valve ignored the note_shift() blackout, so vocabulary lifts fed on their own damage** *(historical — fixed)*  
`coupling` · chat-a · capacity valve vs note_shift() in self_organize.py; fixed in 4a29000  
note_shift() marks retok/epoch-resample/LR-restart as 'the loss jump is OURS, not the data's' and PlateauGrowth refuses to grow inside that blackout; the valve read the same EMA pair without checking the flag. A vocabulary lift mints tokens -> retok rebuilds the stream -> loss jumps -> the jump reads as a stall -> next lift. 19 vocabulary lifts, 2048 -> 8192.

**H4. Pin clock required contiguous steps at the cap and reset to zero on any dip** *(historical — fixed)*  
`other` · chat-a · capacity valve pin accounting; fixed to accumulate/decay (`_pin_fab[0] = (_pin_fab[0]+1) if _fabpin else max(0, _pin_fab[0]-1)`)  
Harmless for a vocabulary, which never shrinks — which is exactly why the vocabulary half of the valve worked and the expert half never did. A brief cull-induced dip cost the entire accumulated pin time.

**H5. GROW_CAP_EVERY measured steps since the last LIFT, not steps PINNED** *(historical — fixed)*  
`wrong-measurement` · chat-a · capacity valve gate; fixed in 31874a5 (each cap now carries its own pin timestamp)  
A population pinned five minutes ago and one pinned two hours ago were treated identically, and a cap never reached still aged toward eligibility — so the first plateau after a quiet stretch could lift a cap nothing was pressing against.

**H6. Unguarded `_F0.div_mass` in the _EFF banner crashes every FABRIC=0 run** *(historical — fixed)*  
`crash` · chat-a · self_organize.py ~line 4677, base (unguarded) _EFF list; fixed at 0d0b8f3 plus a new static check in levers.py  
AttributeError: 'NoneType' object has no attribute 'div_mass'. The assistant spotted this two rounds earlier and declined to fix it, reasoning 'the nofabric arm has run since, so something must be catching it'. Nothing was — nofabric is in GRID_ARMS_DEFAULT but that list had never been run. It cost a grid arm (round9 nofabric FAILED rc=1 after 18s).

**H7. _proj_steps priced every remaining epoch at the current epoch's length while minting keeps shortening them** *(historical — fixed)*  
`wrong-measurement` · chat-a · _proj_steps / proj_arith in self_organize.py; fixed in 96660b3, hoisted to module level, covered by proj_test.py  
Worst error 18.7%, mean 6.8% from epoch 2 onward; the cosine was stretched over a horizon it never reached. In one pair base projected 67,872 total steps at step 2000 and ended at 48,140 — a 41% overestimate. Epochs 0-1 remain uncorrected by design (no completed pair to estimate from), and proj_test asserts that rather than weakening the check.

**H8. End-of-run verdict called a blown-up run 'PLATEAUED, not diverging'** *(historical — fixed)*  
`wrong-measurement` · chat-a · end-of-run report; fixed in 0ef2fca (new BLEW UP AND STAYED DOWN verdict plus an in-run alarm at the probe it happens on)  
round13 reached 2.226 at step 38,000, went to 6.80 within 6,000 steps, and spent ~520,000 further steps (about seven hours) below a level it had already reached, while the report said 'nothing is degrading'. The tail tells you whether a run is STILL falling apart; the height tells you whether it already did.

**H9. Diagnostics attached to _EFF's `note` field are inert — that field only renders when the asked value differs from the live one** *(historical — fixed)*  
`armed-but-inert` · chat-a · _EFF banner in self_organize.py; hit twice — the FAB_PRESSURE occupancy warning (made an unconditional [config] CULL GATE line) and nearly again for the LR_STEPS COUPLING note  
The occupancy warning never printed once in all of round5, which is how the shut cull gate hid for a round. 'Writing an inert diagnostic while fixing an inert mechanism is the joke this file keeps making.'

**H10. TOK_ANCHOR=0.05 is armed and has never once entered the loss** *(historical — fixed)*  
`armed-but-inert` · chat-a · self_organize.py, gated on TOK_COMPOSE=0  
Reported as on in the config banner; the file's own header says it has never entered the loss. Not fixed in this range.

**H11. HALT has no working regime** *(historical — fixed)*  
`untrippable-guard` · chat-a · halt_key path, self_organize.py ~1524/1656  
FAB_KEY_NORM=0 -> HALT mass 0.0000 at routed depth 1.00 (all 4 hops at full strength on every window, PONDER=0.01 could not lift it); FAB_KEY_NORM=1 -> 0.9999 at depth 0.10-0.15 (halts on hop 0, chains nothing). At 0 it is a raw dot with spread ~0.075 competing in the same softmax against a region term at 3.7. Not fixed.

**H12. Nothing protects the optimizer from the epoch resample shift** *(historical — fixed)*  
`coupling` · chat-a · LR schedule vs note_shift() in self_organize.py  
note_shift() tells growth (and now the valve) that a loss jump is ours, but the LR meets the fresh sample at whatever the cosine says — 96-99% of peak at the second boundary in every run measured. This is what destroyed round13. LR_SHIFT_WARM was built as the fix but defaults to 0 and was only pilot-tested at round15.

**H13. Domain layer produces routing targets carrying no information on a single corpus** *(historical — fixed)*  
`wrong-measurement` · chat-a · self-assembling domain partition  
33 live domains, 30 scored `weak`, over ~2100 ephemeral source ids; own-domain 1.924 vs random-other 2.144 (gap +0.220) against a shuffled-provenance floor of +0.223 +/- 0.003, excess -0.003 — fails its own null. The encoder underneath measures healthy (silhouette +0.24, 1-NN 0.984). Not fixed.

**H14. The plateau verdict used a one-sided threshold for the third time in one session** *(historical — fixed)*  
`wrong-measurement` · chat-b · self_organize.py, `elif _bpb_dir[1] <= 0.05:`  
`<= 0.05` passes for every negative value, so sched_ctl — whose last two thirds FELL -0.086 — was told "PLATEAUED... more steps at this setting will not help" two lines after the LM curve block said "clearly still improving — more steps will buy more". Both numbers were computed correctly; one was described backwards, and they gave opposite advice about the same run.

**H15. A corpus smaller than STREAM_LEN duplicates itself, silently** *(historical — fixed)*  
`untrippable-guard` · chat-b · build_stream() in self_organize.py, and _pilot_corpus() in longrun.sh  
build_stream draws random segments until it has STREAM_LEN bytes and stops — it never checks whether that many DISTINCT bytes exist. And _pilot_corpus returns early if ANY part file exists, never checking size. So data_pilot fetched at 0.06 GB for round12 would be reused unchanged by a run configured for 0.75 GB, repeating the corpus ~1.6x per epoch with nothing in any log saying so.

**H16. LR_DECAY: an envelope built for this exact failure, shipped off at 0.0, and unsafe to turn on** *(historical — fixed)*  
`armed-but-inert` · chat-b · self_organize.py:368 `"LR_DECAY": ("f", 0.0)`  
LR_DECAY was written against an 18-epoch run whose curve "swings 1.5 b/B and never resettles" after a restart — the same failure, long before this session — and sat at 0.0 ever since. Turning it on was never safe either: written as a function of GLOBAL progress with no reference to cycle count, it also squeezed SINGLE-cycle runs, multiplying one cosine by another so a run that should end at LR_MIN_FRAC ended at its square.

**H17. Five management cadences ran below the batch early-out, firing for a minority of flush residues** *(historical — fixed)*  
`unit-mismatch` · chat-b · self_organize.py, `step % MANAGE_EVERY == 0` at the FAB_SPAWN, SOCIETY-merge and chain-order sites (plus ACCUM later)  
`step` advances once per WINDOW while the block runs once per FLUSH, so at BATCH_W=16 MANAGE_EVERY=500 the gate fires for 4 of 16 possible flush residues and ZERO for the other 12. FAB_SPAWN did fire in real runs (34-144), so the shipped pairing was lucky, not correct.

**H18. rebuild_census (the fix for the above) clamped source ids into a 64-wide table instead of growing it** *(historical — fixed)*  
`silent-overwrite` · chat-b · memory.py rebuild_census(), self_organize.py:4309 `n_src_hint=max(64, _i("MAX_DOMAINS", 32) * 2)`  
memory.py's own docstring records 125 source ids on a real run, so the fix for the resume floor would have re-broken it at exactly the scale it was written for. The assistant's own fix, caught by the follow-on audit.

**H19. compare.py's unpaired branch counted a cross-product as independent observations** *(historical — fixed)*  
`wrong-measurement` · chat-b · compare.py `pairs = [(x, y) for x in da.values() for y in db.values()]`  
Two runs per arm became 4 "pairs", clearing MIN_PAIRS=3 and printing P(A better) = 1.000, CI [1.000, 1.000], SIGNIFICANT AND MEANINGFUL — reproducing the exact collapse the docstring says MIN_PAIRS exists to prevent.

**H20. Two different numbers in every log are both labelled 'held-out bits/byte'** *(historical — fixed)*  
`wrong-measurement` · chat-b · self_organize.py, the MEMORIZATION CHECK line vs the `SAMPLED FROM ... (X held-out bits/byte)` line  
27 of 36 finished logs disagree by more than compare.py's own 0.03 floor, max gap 0.190 — larger than most arm effects this project has claimed. runs.csv puts one in `held_out` and a figure from the other instrument in `past_min`. Nothing reconciled them.

**H21. The world-model resume replay could hang forever with no output** *(historical — fixed)*  
`untrippable-guard` · chat-b · self_organize.py `while world_fwd.n() < _RD["world_cfg"]["n"]: world_fwd.grow()`  
grow() returns None WITHOUT appending at capacity (world_model.py:105), so a checkpoint with more predictors than this run's WORLD_NMAX spins forever — no output, no traceback, no timeout. Bounded now with a SystemExit naming WORLD_NMAX.

**H22. The resampling guard summed the corpora instead of checking each one** *(historical — fixed)*  
`unit-mismatch` · chat-b · self_organize.py, the STREAM_LEN vs sum(SEG_LEN) startup warning  
build_stream draws PER CORPUS in PHASE_SCHED's proportions; the guard compared STREAM_LEN against sum(SEG_LEN). 60 MB English + 8 MB Python reads as 68 MB against a 4 MB stream and passes. The assistant's first replacement was PER-EPOCH and still missed it — exposure is a whole-run quantity: at EPOCHS=8 the added area is seen 2.1x over while the original is 28% sampled. Writing the exposure check in epoch units is the same units fault the check exists to catch.

**H23. fetch_big presets were findable only by short key, so the documented command could not have worked** *(historical — fixed)*  
`other` · chat-b · fetch_big.py `p = PRESETS.get(a.dataset, dict(path=a.dataset, ..., field="text"))`  
`--dataset the-stack-dedup` resolved field='content'; `--dataset bigcode/the-stack-dedup` — the id on the dataset page, in fetch_big.py's own instructions, and in round18's note — missed the table and fell through to field='text', producing "a KeyError after authenticating, which reads like an auth problem and is not one".

**H24. A widened fabric would have loaded stale Adam moments and crashed on the first step, not at load** *(historical — fixed)*  
`crash` · chat-b · self_organize.py `om.load_state_dict(_RD["opt_m"])`  
exp_avg and exp_avg_sq are shaped like the parameter they track, so a checkpoint holds [1024,d,r] moments for an A that is now [4096,d,r]. torch's Optimizer.load_state_dict does NOT validate shape — it would load cleanly and fail minutes into training with nothing connecting it to the resume.

**H25. One flag (_wide_by) gated two unrelated optimizers** *(historical — fixed)*  
`coupling` · chat-b · self_organize.py `om.load_state_dict(...); oe.load_state_dict(...)` sharing a line  
_wide_by is a fact about the FABRIC's cap-shaped parameters, all in om. oe is AdamW(enc.parameters()) and holds nothing sized by fab.cap, so widening cannot invalidate its moments — yet they were dropped and the message blamed the fabric. enc produces gist: the routing query and the space every centroid lives in, so resetting its Adam state at the boundary where a new area's signatures first arrive is the worst available moment. Committed WHILE fixing that exact class of bug.

**H26. pilot-add's fetch guard skipped on 'any part file exists', not on size** *(historical — fixed)*  
`untrippable-guard` · chat-b · longrun.sh pilot-add `if [ -z "$(ls "$P_DD/train/$NAME"/part*.txt 2>/dev/null)" ]; then`  
This is exactly how the first continual-learning run got its 5.6x exposure imbalance: an earlier `pilot-add py local 0.03` had left ~10 MB, the next invocation asked for 0.06 GB, saw part000.txt, and skipped. The identical defect was already documented for _pilot_corpus.

**H27. The geometry gate had three blind spots** *(historical — fixed)*  
`untrippable-guard` · chat-b · self_organize.py:4171 `_ck_cap = int(_fc.get("cap") or 0)` and the widened-count report at :4359  
(a) a fab_cfg without "cap" slid through all three branches (each guarded on `_ck_cap and ...`) straight to load_state_dict and the original five-shape dump; (b) FAB_NMAX was named as the remedy for trailing-dimension mismatches that are not about the cap; (c) the widened count was never compared to anything, so a checkpoint missing `cent` would restore every adapter and silently leave every restored expert's routing region at random init.

**H28. ACCUM was the last modulo cadence below the batch early-out** *(historical — fixed)*  
`unit-mismatch` · chat-b · self_organize.py `if (step + 1) % ACCUM == 0:`  
At BATCH_W=16 ACCUM=4 the optimizer either steps on EVERY flush (ACCUM accumulates nothing) or never steps at all for the epoch — 3 of 4 starting offsets give zero om.step() calls. bench_gpu.sh ships BATCH_W=16 ACCUM=2. Harmless only at ACCUM=1.

**H29. ACCUM gate counted windows, not backward passes — the knob accumulated nothing at any value** *(historical — fixed)*  
`unit-mismatch` · chat-c · self_organize.py training loop; gate was `if (step + 1) % ACCUM == 0`  
om.step() and om.zero_grad() are the only calls to either in the loop and both sat inside a gate keyed on `step`, which advances per WINDOW, while the body runs per FLUSH. Measured: old gate 55 om.step() calls vs new gate 13, over ~52 backward passes at BATCH_W=4 ACCUM=4 — i.e. it stepped roughly once per backward pass whatever ACCUM was set to.

**H30. SPECIALIZATION partitioned held-out windows with a projection that never trained** *(historical — fixed)*  
`armed-but-inert` · chat-c · self_organize.py SPECIALIZATION section, built its winner from fab.q_entry  
Entry moved to the shared grounded router (entry_logits, scoring with q_route) and this copy was never updated. ROUTE_GROUNDED defaults to 1, and the run's own ROUTER LEARNING audit printed `never gradiented -> ctrl, q_entry`. The section was drawn from its own null and would read INTERCHANGEABLE whatever the population did. Symptom visible as 5 probe winners against 415 run winners and explained away as "a probe, not the run".

**H31. The curve verdict read one process, always the newest corpus** *(historical — fixed)*  
`wrong-measurement` · chat-c · self_organize.py curve verdict, `{st: b for st, _p, b, _a in _CURVE}`  
Keying on step alone means the last-appended process wins; appends ascend by id so it is always the highest, which under "add an area" is the NEWEST corpus — the one that cannot have been forgotten. Confirmed on a live table: the old series is process 1's row verbatim, and 7 of its 12 samples were windows where process 1 was ABSENT.

**H32. One shell gate for three unrelated derivations — setting FAB_N0 silently reverted VMAX and FAB_NMAX** *(historical — fixed)*  
`coupling` · chat-c · longrun.sh:717, VMAX and FAB_NMAX nested inside `if [ -z "${FAB_N0:-}" ]`  
Setting FAB_N0 — which the block's OWN failure message instructs you to do — silently reverted VMAX to 2048 and FAB_NMAX to 4096 and re-created both round18 defects with no message. FAB_N0 is a population count; the other two are the softmax width and the slot pool.

**H33. Model optimizer moments skipped on `_wide_by` alone — a VMAX-only widening crashes at the first om.step()** *(historical — fixed)*  
`crash` · chat-c · self_organize.py optimizer restore  
emb.weight, head.weight and head.bias are all in om, so widening the SOFTMAX invalidates its moments exactly as widening the fabric does. A resume raising VMAX without touching FAB_NMAX loaded moments shaped for the old vocabulary cleanly and died at the first om.step(). Masked on both harness paths only by accident, because both currently widen the fabric too. Same bug class as the fix it was written for.

**H34. FAB_RANK and FAB_DK were not inherited by the harness** *(historical — fixed)*  
`crash` · chat-c · longrun.sh pilot-add / add geometry inheritance  
The harness inherited n, cap and the softmax width and left rank and dk on registry defaults. Both are INNER dimensions (A is [cap,d,rank]; SRC_p/K_p are [cap,dk]) so no prefix of a rank-4 adapter is a valid rank-8 one and a mismatch is fatal by design. It bit the moment `add` first met a real checkpoint.

**H35. corpus_test.py and resume_test.py — 185 checks — were in no test entry point** *(historical — fixed)*  
`armed-but-inert` · chat-c · selftest.sh  
Both were written this session and never wired into selftest.sh, the file anyone runs before a launch. The project's own gate silently skipped 59+126 checks covering the widening, the geometry refusals, the newborn split, the growth controller, the cull budget, the exposure guards and the ACCUM gate. They passed the whole time; nothing was asking them.

**H36. AMP=fp16 autocasts without a GradScaler** *(historical — fixed)*  
`armed-but-inert` · chat-c · self_organize.py precision block, guarded on `AMP in ("bf16","fp16") and DEV == "cuda"`  
The comment justifies bf16 correctly ("same exponent range as fp32, so no loss scaling and no GradScaler") but the knob also accepts fp16, whose exponent range is far smaller. Small gradients underflow to zero: the model trains, the loss curve looks plausible, an unknown fraction of every update is discarded, and the run prints a confident `[precision] LM step in fp16 autocast`. REFUSED (SystemExit naming the reason and pointing at bf16) rather than fixed, deliberately — adding a scaler changes the optimizer step, which is now gated on accumulated backward passes, and an unscale at the wrong point in that cycle silently breaks accumulation instead.

**H37. Self-inflicted process bug: editing selftest.sh while bash was executing it produced exit 0 with the end-to-end phase never running** *(historical — fixed)*  
`armed-but-inert` · chat-c · selftest.sh (harness), assistant's own workflow  
Bash reads scripts incrementally by byte offset, so inserting two lines shifted the file under the running interpreter. It resumed mid-token, printed `line 101: ts:: command not found`, re-printed the header and exited 0 without training anything. `ts::` appears nowhere in the file. "An exit code of 0 on a suite whose main phase silently didn't execute is precisely the failure mode this project exists to catch — a mechanism that runs and does nothing — and I produced it in the test harness itself while auditing for it."

**H38. IndexError in the cross-domain injection — a guard written FOR this exact crash checked the wrong quantity** *(historical — fixed)*  
`untrippable-guard` · chat-c · self_organize.py injection, `sp = random.choice([s for s in range(0, len(stream) - (WIN + 1), WIN) if labels[s] == p])` behind `if ninj > 0 and len(procs) < 2`  
`procs` is sorted(set(labels)) — every label present ANYWHERE in the stream — while the sampler only takes positions that are MULTIPLES of WIN. A process can be in labels and have no window-aligned start at all (narrow bands, short streams, PHASED schedules), so the guard passes and the comprehension is still empty. The guard's own comment describes this exact failure. Crashed after training and the checkpoint had completed. Fixed by building the candidate lists first and keeping only processes that have one.

**H39. The probe-vs-run guard the assistant added compared quantities in different units and could not be satisfied** *(historical — fixed)*  
`unit-mismatch` · chat-c · self_organize.py SPECIALIZATION probe check, `len(_used) * 10 < len(_uv)`  
8 probe winners against 633 run winners — but the probe scores only 32 windows, so len(_used) can never exceed 32. A perfect probe picking a different expert every window gives 320 < 633 and still trips, voiding every SPECIALIZATION verdict. Replaced with MEMBERSHIP (dimensionless) plus the coupon-collector expectation sum_i (1-(1-p_i)^W) for 32 draws from the run's own distribution.

**H40. tokenizer.mint reported "off — the vocabulary was already FULL" over 1536 mints** *(historical — fixed)*  
`wrong-measurement` · chat-c · self_organize.py DID IT FIRE arming test for tokenizer.mint  
It asked "is there room NOW" at report time and printed "off -- the vocabulary was already FULL at 512/2048 when this run started, so there was no room to mint" while discarding a count of 1536 and with the log directly above showing vocab climbing 512 -> 824 -> 1148 -> 1304. Room at the start is a question about TOK_V0, which is already the count's own baseline.

**H41. memory.wrong_block said "read() filters nothing" in the same report as "61,952 of 200,000 entries excluded from EVERY retrieval"** *(historical — fixed)*  
`wrong-measurement` · chat-c · self_organize.py DID IT FIRE arming test, `(selfcon >= 0).sum() > 10` evaluated at report time  
Every write resets selfcon to -1 and the pilot wrote 11.7M times into 200k slots, so the final snapshot said nothing could be flagged. Memory.read counts its own exclusions now and WRONGNESS states the training-time number beside the end-of-run snapshot.

**H42. "Does the memory earn its keep?" was scored on the training stream** *(historical — fixed)*  
`wrong-measurement` · chat-c · self_organize.py compose_test, draws its windows from `stream`  
A retrieval that returns the very window being scored counts as a hit, so the section is partly a memorisation score — and it is the one in the biggest type. The pilot printed both answers 127 lines apart: `+0.212` on the training stream against `-0.100` on eng's held-out tail. The generation samples settle it: two different seeds produced the identical span "elements are visitors to 1,0,000,000,000 and Maryland, CTA area of fuels". Nothing computed was changed; the held-out pair now prints beside it and the verdict separates the two questions.

**H43. Every resume reported a phantom cosine restart on its second step, suppressing the regression reading exactly when a new area arrives** *(historical — fixed)*  
`wrong-measurement` · chat-c · self_organize.py LR schedule, `_lr_prev` starts at 0.0  
`[lr @ 47079] cosine restart 1: 0.00e+00 -> 1.15e-03 (57% of peak, x1145648405)`. A fresh run's warmup holds early rates under the `> 0.5 * LR` bar until a real previous value exists; a resume skips warmup so the first rate computed is already 57% of peak and is compared against zero. The x1.1-billion multiplier is _lrv over the 1e-12 floor, not a ratio. It cost more than a log line: note_shift() told the growth controller the loss jump was self-inflicted, suppressing the regression reading on the exact step a new area arrives — the one moment that controller exists for.

**H44. A local corpus would have been trained on and reported as the-stack-dedup** *(historical — fixed)*  
`wrong-measurement` · chat-c · longrun.sh pilot-add size check; fetch_big.py / fetch_local.py had no provenance record  
data_pilot/train/py held 57 MB of the owner's local Python. The size check would have accepted it, skipped the fetch entirely, and trained on the interpreter's source with `the-stack-dedup` in every line of the log, with nothing downstream able to detect it. Both fetchers now write `_fetch_manifest.json` and refuse a source mismatch — but directories that predate the manifest only get a warning, so the owner had to `mv` it by hand.

**H45. The FABRIC node-mass line measured a batch of exactly one window and diagnosed a routing collapse from it** *(historical — fixed)*  
`wrong-measurement` · chat-c · self_organize.py FABRIC report line, measured stream[:WIN]  
Printed "1 of 2214 nodes carry any, top node 100%" under a note saying "all mass on one node = collapsed", in the SAME report as "ROUTER SELECTION over the whole run: 2108 distinct experts | top 6.1%". A single window puts its mass on one node whatever the router does, so the line could not have said anything else. The assistant's own previous-round conclusion that routing had collapsed was wrong. Now averages over EVAL_N windows and names its sample.

**H46. Second tokenizer clobber, latent: grid and seed arms all wrote to the shared data/dyntok.json** *(historical — fixed)*  
`silent-overwrite` · chat-c · sweep/grid/seed harness paths leaving TOKENIZER_PATH at its default  
Every arm wrote its vocabulary to one file and each checkpoint's tok_path named it, so any arm's checkpoint would restore embeddings indexed by whichever arm last wrote. pilot-add's own fallback already warned about that file ("if any other pilot has run since, this vocabulary is that one's"). Each arm now writes beside its own checkpoint; an unset TOKENIZER_PATH on a resume defaults to <RESUME>.dyntok.json.

**H47. dom_ban breadth cap was inert because the table it reads was sampled once per step** *(historical — fixed)*  
`armed-but-inert` · chat-early · Fabric.dom_ban / fab.note_dom; chunk_08.md:1367 and :5385  
The percentage-based breadth cap the owner explicitly requested could only ever ban the ~30 experts that happened to land in the one-sample-per-step table. When commit 99e5da0 fixed the sampling (1 -> BATCH_W=16 samples/step) the previously dead routing constraint went live and the held-out figure moved from ~2.1 to ~3.7 b/B — read at the time as a regression.

**H48. DIV_W was a silent no-op on the default chaining path** *(historical — fixed)*  
`armed-but-inert` · chat-early · self_organize.py diversity loss; chunk_08.md:561, :3748, :6024  
A 20-minute pilot ran with DIV_W=0.05 and measured nothing. The loss was un-runnable on both paths at different times: NameError on chaining (main()-local), IndexError on society (global id indexed into a rank-ordered list), then still inert on the soc-loop via an early return.

**H49. Adaptive encoder warmup reported a plateau stop when it had merely run out of budget** *(historical — fixed)*  
`untrippable-guard` · chat-early · self_organize.py adaptive warmup; user_turns.md:7419, and visible in run output at :4259  
The log line reads "(adaptive warmup: stopped at 30000/30000 on separation plateau; floor 30000, eps 0.015)" — floor equals budget, so the plateau test can never be reached, yet the report claims the plateau caused the stop.

**H50. Bare `except Exception` swallowed the learning-curve error so the section never appeared** *(historical — fixed)*  
`recorded-never-read` · chat-early · self_organize.py learning-curve block; user_turns.md:7423  
A whole report section silently vanished from every run. Root cause: `nbytes()` reads `BLEN`, which is `None` until the final re-tokenization under TOK_ONLINE.

**H51. Expert region centroids were a plain attribute, absent from state_dict** *(historical — fixed)*  
`recorded-never-read` · chat-early · Fabric; user_turns.md:5021  
`s.cent` was not a registered buffer, so it was not saved in the checkpoint — every RESUME restarted routing from cold centroids.

**H52. HALT was computed and then discarded on the society path** *(historical — fixed)*  
`recorded-never-read` · chat-early · Fabric.society; user_turns.md:9694  
HALT mass was calculated every step and thrown away, so the router's stop decision had no effect on the society path. The owner spotted it from the run: "Chaining is being run, but, halt should have been set on this".

**H53. `_due(k, n)` is not a predicate — it consumes the event** *(historical — fixed)*  
`armed-but-inert` · chat-early · self_organize.py cadence helper; user_turns.md:11000  
`_due` records `_fired[k] = step` and returns True, so calling it twice in one step silently consumes the event and the second consumer never fires.

**H54. TOK_ANCHOR_USES=400 is gated on TOK_COMPOSE, which defaults to 0** *(historical — fixed)*  
`armed-but-inert` · chat-early · tokenizer.py ByteComposer / anchor release; user_turns.md:11004-11005  
The owner explicitly set anchor release to 400 appearances; the knob sits behind TOK_COMPOSE=0 and therefore does nothing at default settings. The [config] guard that would have caught it existed but the value was never checked against the gate.

**H55. `_VALT` held-out tokenization cache was never invalidated** *(historical — fixed)*  
`wrong-measurement` · chat-early · self_organize.py held-out evaluation cache; user_turns.md:9704  
The learning curve was not comparable across time within a run because the cached held-out tokenization went stale as the tokenizer minted. The owner flagged the fix as suspicious: "You said that (18fdd6c) fixed a stale held-out tokenisation cache happened, but it looks more like it broke something, since output looked better before".

**H56. Brown corpus POS-tag stripper only matched uppercase tags** *(historical — fixed)*  
`wrong-measurement` · chat-early · fetch_data.sh line ~69; user_turns.md:3362-3365  
Brown uses lowercase tags (`the/at movie/nn`); a `[A-Z]`-only character class leaked them into the English training corpus, and they surfaced in generated text as "/at", "/nn", "/cc" artifacts.

**H57. Reported "system chaos" spread was measured with a since-fixed bug** *(historical — fixed)*  
`wrong-measurement` · chat-early · seed-spread analysis; user_turns.md:11006  
A documented same-seed spread of 1.594 b/B — used as the noise floor against which arm differences were judged — was itself measured with a bug that was later fixed, so the noise floor is unreliable.

**H58. Expert affiliation report shows every expert serving every domain — the metric cannot discriminate** *(historical — fixed)*  
`wrong-measurement` · chat-early · run report AFFILIATION section; user_turns.md:589-592  
"experts serving >1 domain: 6 | serving exactly 1 (exclusive): 0 | serving none: 0 / domains served per expert: [443, 443, 443, 443, 442, 440]" with 6 experts and 443 domains. Blast radius is therefore always 0 orphans, so the whole "deleting a domain releases its experts" claim is untestable at that population size.

**H59. End-of-run full-stream re-tokenization OOMs the GPU** *(historical — fixed)*  
`crash` · chat-early · self_organize.py final _retok; user_turns.md:8950  
"torch.OutOfMemoryError: CUDA out of memory. Tried to allocate 11.39 GiB" on an 80 GiB card at the end of a pilot — the run completes training then dies before writing its report.

**H60. asm.rekey crashed on ragged windows** *(historical — fixed)*  
`crash` · chat-early · self_organize.py asm.rekey; user_turns.md:8471  
"ValueError: expected sequence of length 384 at dim 1 (got 426)" killed a pilot at the domain-centroid re-key step.

**H61. Refactor introduced NameError and UnboundLocalError in the report path** *(historical — fixed)*  
`crash` · chat-early · self_organize.py _report / _retok after the levers refactor; user_turns.md:10148, :10171  
"NameError: name '_retok' is not defined" then "UnboundLocalError: local variable 'assigns' referenced before assignment" — the refactor that was supposed to be behaviour-preserving broke the run twice in a row on the owner's box.

**H62. Six latent defects from agent reports left unfixed as of 2026-08-15** *(historical — fixed)*  
`other` · chat-early · self_organize.py / memory.py / tokenizer.py; user_turns.md:11145  
Batch accumulator straddles the epoch boundary (`_bx/_by/_bg` not cleared at the roll, `_posv` indexes new `tok_bs` with old indices); `mem.tok`/`mem.ctx` keep write-time segmentation and are never remapped; `asm.tokc` mixes counts across segmentations; `ENC_SEQ` not re-pointed after the final retok under SIG_SPACE=tokens; pair tally + Counter trim continue after saturation; `_bpt` is an unweighted mean overstating by up to 8% and growing with VMAX.


### MEDIUM (38)

**M1. `_pin_fab[0]` read after being cleared in the same print** *(historical — fixed)*  
`other` · chat-a · capacity valve report line; fixed before commit  
The lift message would report a pin duration of zero because the clock was cleared by the lift before the print consumed it.

**M2. Config banner listed DIV_W under 'OFF ON PURPOSE' while it was on** *(historical — fixed)*  
`wrong-measurement` · chat-a · config banner; fixed in 6380519  
Printed '[config] OFF ON PURPOSE ... DIV_W=0.02' two lines above 'DIV_W=0.02 IS applied on this path (ON)' — a hardcoded list rather than a read of the live value.

**M3. Report line advising 'Raise FAB_EMB_VAR' recommends the knob that produces the condition it warns about** *(historical — fixed)*  
`wrong-measurement` · chat-a · IDENTITY SPACE report line; replaced with measured numbers in 80fa009  
The line was written on no measurement and sent the assistant down a whole grid; FAB_EMB_VAR=16 is the only COLLAPSED arm in round3 (NN 0.0017).

**M4. `_i('FAB_N0',3)` call site missed by the config checker because of single quotes** *(historical — fixed)*  
`other` · chat-a · self_organize.py; fixed in 6380519  
Default-mismatch audit did not catch it until an end-to-end CPU run printed the mismatch warning on the FABRIC line.

**M5. First [config] CULL GATE insert landed inside the ROUTE_REGION_W conditional** *(historical — fixed)*  
`untrippable-guard` · chat-a · config banner; caught by reading output, not by syntax check  
The unconditional diagnostic would have printed only when a different, unrelated knob was on.

**M6. Arm definitions placed in the longrun.sh ARMS preset `case` instead of `_flags_for` — twice** *(historical — fixed)*  
`armed-but-inert` · chat-a · longrun.sh; caught both times by testing preset resolution in isolation  
The arm name resolves in the preset list but carries no flags, so the arm silently runs as base.

**M7. fabric.spawn fires 1-9 times per run regardless of any intervention** *(historical — fixed)*  
`untrippable-guard` · chat-a · Fabric spawn gate  
Against replicate 412, crossover 124, explore 27095. The assistant's hypothesis that identity collapse starved it was refuted — the identity space is distinct at HEAD and spawn still does not fire, so the gate is the problem, not the geometry. Not fixed.

**M8. verification.py's report line appears in zero logs under runs/** *(historical — fixed)*  
`armed-but-inert` · chat-a · verification.py  
Built, shipped, and never observed to run. Not investigated in this range.

**M9. TOK_ANCHOR is armed by default but its loss term can never fire** *(historical — fixed)*  
`armed-but-inert` · chat-b · self_organize.py:121 `"TOK_ANCHOR": ("f", 0.05)`  
Armed at a nonzero default, its loss term has never once entered the loss, so every default run emits a guaranteed false "ARMED AND INERT" for it. Confirmed present in all three round18 logs.

**M10. grid never wrote $LOG.cfg, so the documented skip-and-resume workflow could never work** *(historical — fixed)*  
`untrippable-guard` · chat-b · longrun.sh grid  
`seeds` and `repeat` both stamp a .cfg; grid is the only sweep that calls _reusable and never wrote one, and _reusable returns 1 on a MISSING .cfg. So the documented `sleep 2h && git pull && bash longrun.sh grid` exited 1 on the first completed arm.

**M11. The vs-order-1 column matched only the winning branch, so a loss printed identically to 'not measured'** *(historical — fixed)*  
`wrong-measurement` · chat-b · longrun.sh:1204 `grep -a -oE "beats order-1 by \+[0-9.]+"`  
self_organize.py prints "beats order-1 by +X" OR "DOES NOT BEAT ORDER-1 (-X)", and the pattern only matched the first. An arm that LOSES to a two-line frequency table printed `-`. The report's own gate is "if it does not beat order-1, nothing below is worth reading".

**M12. fetch_local's root discovery missed two whole install roots on Debian/Ubuntu** *(historical — fixed)*  
`other` · chat-b · fetch_local.py roots_for() using sysconfig.get_paths() only  
purelib and platlib both collapse to /usr/local/lib/pythonX/dist-packages while system packages live in /usr/lib/python3/dist-packages. Found 10.7 MB where 26.9 MB existed — a 2.5x undercount that produced the 'corpus too small' error the owner reported.

**M13. Growth events were counted before the clamp that declines them** *(historical — fixed)*  
`wrong-measurement` · chat-b · self_organize.py, n_regr incremented inside PlateauGrowth.step, returned before the call-site cap/FAB_NEW_FRAC clamp  
A declined regression still reported as fired — and the diagnostic built to catch exactly this ("the REGRESSION trigger never fired... the arrival was invisible to growth") is gated on n_regr == 0, so it stayed silent precisely when it was needed.

**M14. The quantile write gate is a default that cannot fire, with no DID IT FIRE row** *(historical — fixed)*  
`armed-but-inert` · chat-b · memory.py:119 `if self.adaptive_gate and self.quantile_gate:`  
quantile_gate defaults True but adaptive_gate comes from WRITE_ADAPTIVE=0, so WRITE_QUANTILE reads as a live tuned setting and can never execute. Same shape as TOK_ANCHOR — which at least has a DID IT FIRE row; this did not. Surfaced as a COUPLING line at the end of this range; whether a DID IT FIRE row was added is not shown.

**M15. The DomainAssembler / sweep_domain_report mem delta column reads the wrong line** *(historical — fixed)*  
`wrong-measurement` · chat-b · sweep_domain_report.py, the `mem db/B` column  
It reads the FIRST "memory contributes" in the log, which is the per-domain retention line, not the run-level ablation its own header documents. On real logs this flips the sign of the documented "POSITIVE means memory helped" reading. Reported by the analysis audit; whether it was fixed is not shown in this range.

**M16. holdout.py and runs.py have no tests, and runs.py asserts staleness about knobs a run demonstrably set** *(historical — fixed)*  
`untrippable-guard` · chat-b · holdout.py (four unguarded rules), runs.py  
runs.py will ingest a log whose entire config line failed to parse, then assert in `stale` that the run "predates" knobs it demonstrably set. Reported by the analysis audit; no fix shown in this range.

**M17. The assistant's own first read of round15 was wrong** *(historical — fixed)*  
`wrong-measurement` · chat-b · the log-extraction grep for 'held-out'  
It caught the BLOW-UP ALARM line rather than the final report, which made all four arms look identical (sched_ctl and sched_warm the same, sched_step and sched_both the same) and produced a wrong table before it was corrected from the ANCHORS block.

**M18. The system-audit workflow's verify stage crashed on a JS bug, so none of its findings were adversarially checked** *(historical — fixed)*  
`other` · chat-b · the round15 deep-read workflow script  
The agents returned `arm` as a descriptive string, so the file lookup found nothing and the verify stage produced nothing. The assistant verified each claim by hand instead; three of four held.

**M19. GROW_CAP_FAB0 refusal guard was unreachable on every checkpoint** *(historical — fixed)*  
`untrippable-guard` · chat-c · self_organize.py resume path  
The checkpoint's saved cap_fab=48 was restored over the explicit GROW_CAP_FAB0=8 request BEFORE the guard ran, so the guard the assistant had just added could never trip on any checkpoint written from then on (they all carry cap_fab). Found only by firing it.

**M20. Cull budget sized on the whole population instead of the eligible experts** *(historical — fixed)*  
`wrong-measurement` · chat-c · self_organize.py cull, `order[:max(1, int(cull_frac * s.n_live))]`  
2.25x more experts culled than intended. Measured with n_elig 21 against n_live 120: 18 removed (old) vs 8 (new), population 120->102 vs 120->113.

**M21. Declined-growth counter tested a leftover string — 107 declines against 9 real asks** *(historical — fixed)*  
`recorded-never-read` · chat-c · self_organize.py growth controller, tested `fabgrow.why`  
`fabgrow.why` is a leftover from the last firing that is never cleared, so every non-growth flush counted as a decline. A counter meant to expose a silent failure was producing one.

**M22. Growth counters ride in the checkpoint, so POPULATION CHURN attributed the previous run's events to this one** *(historical — fixed)*  
`wrong-measurement` · chat-c · self_organize.py POPULATION CHURN / fabgrow checkpoint state  
The counters are saved and restored, so the section reported a chain total as if it were this run. Fixed with `_fg_base` recording the baseline; the chain total is now printed alongside.

**M23. Self-inflicted: a replace-first-occurrence patched `run)` instead of `add)`** *(historical — fixed)*  
`silent-overwrite` · chat-c · longrun.sh — `replace(..., 1)` hit line 576 (run\)) rather than line 873 (add\))  
`run)` got VMAX made overridable (an unintended change) and, having no $TOKENIZER_PATH, may have been broken under `set -u`; `add)`'s VMAX stayed hardcoded. Caught because the child still printed `vocab 2048`.

**M24. `609% precision` — a hardcoded constant from one investigation left in a general report line** *(historical — fixed)*  
`wrong-measurement` · chat-c · self_organize.py WRONGNESS report, `100 * 1820 / max(1, flg)`  
1820 was the pilot's caught-count baked into a line that runs on every run; against a fresh run's 299 flagged it printed 609%. Worse, it asserted a precision figure at all on a run where none was measured — `fb` only exists inside `if ninj > 0` and that run injected nothing, and said so eleven lines earlier. Found only because "run the tests" meant all fourteen this time.

**M25. CORP NameError laundered by a catch-all into a message indistinguishable from a real failure** *(historical — fixed)*  
`other` · chat-c · self_organize.py memorization check, broad try/except printing "[memorization check skipped: NameError: name 'CORP' is not defined]"  
CORP is real-path-only like VALC. The catch-all made the run print something that reads as a bug in the check rather than as a configuration that cannot support it — and a GENUINE failure of that battery on the real-data path arrives at the same except and prints in the same shape, so one of the two is background noise and neither is legible. Fixed with a named `_NoHeldOut` sentinel raise at the top of the existing try, moving no code (re-indenting the ~270-line body was deliberately rejected as the kind of edit that introduces bugs).

**M26. Probe guard second false alarm: newly-grown experts flagged as "never selected"** *(historical — fixed)*  
`wrong-measurement` · chat-c · self_organize.py SPECIALIZATION probe check  
It flagged experts 106 and 2182 as "never selected once in 720144 routed windows — every SPECIALIZATION verdict above is void", forty lines below EXPERT INDEPENDENCE calling 106 the BUSIEST expert at routing mass 1.00. Both were newly grown: seed_key aims a newborn at traffic the router already sends, so it wins a probe window before a training one, and the cull's swap-with-last drops late arrivals into low slot ids. Fixed: age checked against this run's span, the two cases print separately, and the alarm names each id's eval routing mass beside its zero.

**M27. MEMORY PRESSURE cannot reach its threshold on this configuration** *(historical — fixed)*  
`untrippable-guard` · chat-c · memory.py pressure() = main/(main+probation) evictions  
Every write lands on probation and only retrieval promotes out of it, so at 11.7M writes against 1469 read probes probation is 82% of the store rather than a 10% region — permanently over budget, so eviction always takes the probation branch, n_main_evict stays near zero and the signal is pinned at ~0 for the run. Its silence reads as a healthy store. REPORTED, NOT CHANGED.

**M28. pilot's closing hint recommended a corpus half the size of the one it just pulled** *(historical — fixed)*  
`coupling` · chat-c · longrun.sh pilot closing message, hardcoded `pilot-add py local 0.03` against PILOT_GB=0.06  
Both corpora get the same share of the stream whatever their sizes, so following the printed advice builds the added area at half the size and draws it just as often from half as much text — the exact confound pilot-add's fourth-argument default was changed to remove. Now resolves PILOT_GB.

**M29. lr.restart audit row asserted the mechanism could not have run, over a run that had run it** *(historical — fixed)*  
`untrippable-guard` · chat-c · self_organize.py DID IT FIRE, lr.restart / lr.damp arming tests  
`lr.restart` printed "one cycle fits this run, so there is nothing to restart" over a run that had taken one, discarding the count; lr.damp armed on that phantom restart and reported ZERO/ARMED AND INERT. Same shape as tokenizer.mint the round before: an arming test asserting the mechanism could not have run, printed above a number showing it did. The row now arms if a restart actually happened.

**M30. The wrong-flag read gate has never gated anything and structurally cannot** *(historical — fixed)*  
`armed-but-inert` · chat-c · memory.py selfcheck() / MEM_WRONG_READ  
selfcheck() is called once, from the report, never from the training loop, while every write resets selfcon to -1. It ran on 1875 reads and blocked zero. So "67,858 entries excluded from EVERY retrieval" is the state after a pass the report itself just ran — MEM_WRONG_READ gates the report's own evaluations, not the run. REPORTED, NOT CHANGED.

**M31. fetch_big.py printed a --data-dir path that does not exist on the Hub, in the very warning fetch_local.py has a comment about not printing** *(historical — fixed)*  
`other` · chat-c · fetch_big.py fallback advice, printed `--data-dir data/{a.domain}` i.e. `data/py`  
fetch_local.py carries the note "Printing '--data-dir data/py' in the fallback advice below would hand the user a path that does not exist on the Hub, which is a worse failure than printing nothing" — in the file that cannot download. The mapping now lives in fetch_big.py and fetch_local.py imports it.

**M32. A verdict tested against a number it did not print** *(historical — fixed)*  
`wrong-measurement` · chat-c · self_organize.py ACROSS THE RUN BOUNDARY verdict  
`+0.149 +/- 0.092 HELD (inside the noise)` reads as a contradiction. The rule is 2σ and 0.184 appeared nowhere in the output. Both are printed now.

**M33. TOK_ANCHOR is armed and inert in every run and is still on the EFFECTIVE line** *(historical — fixed)*  
`armed-but-inert` · chat-c · self_organize.py loss assembly; the anchor lives on ByteComposer which only exists under TOK_COMPOSE  
TOK_COMPOSE defaults to 0, so model.compose is None and the TOK_ANCHOR term has never once entered the loss — while TOK_ANCHOR=0.05 TOK_ANCHOR_TAU=4000 print on the EFFECTIVE line of every run in the project. DID IT FIRE reports `!! ZERO loss.TOK_ANCHOR 0 ARMED AND INERT`. A COUPLING line now states it; the knob itself was NOT fixed.

**M34. SUFFICIENCY report dead since per-window routing was introduced** *(historical — fixed)*  
`crash` · chat-early · self_organize.py SUFFICIENCY section; user_turns.md:9695  
`int(_os[j])` applied to a row raised ValueError, so the section never rendered; fixed to use the modal holder.

**M35. PH_BOUNDS accumulated across epochs under DISK_STREAM** *(historical — fixed)*  
`unit-mismatch` · chat-early · self_organize.py phase scheduling; user_turns.md:7427  
The phase index ran past PHASE_SCHED, so the non-stationary phase structure — the actual catastrophic-forgetting test — was wrong after epoch 1.

**M36. CHAIN_ROUTE was missing from the knob registry one commit after the registry was built** *(historical — fixed)*  
`other` · chat-early · _SPEC registry; user_turns.md:9701  
The registry built specifically to prevent unregistered knobs immediately admitted one; it now self-polices.

**M37. FABRIC ablation removes the fabric's LayerNorm and overstates its contribution** *(historical — fixed)*  
`wrong-measurement` · chat-early · run report ablation; user_turns.md:614-616  
"model ALONE 7.357 -> + FABRIC 2.586 (fabric +4.772)" is not a fabric contribution — it ablates a component the model trained with, including its LayerNorm. The report itself flags this, but the headline number is still printed.

**M38. mask_dead missed retired token ids** *(historical — fixed)*  
`other` · chat-early · tokenizer / loss masking; user_turns.md:11508  
Retired ids sit below vocab_size rather than forming a suffix, so a suffix-based dead-row mask left them in the cross-entropy denominator.


### LOW (7)

**L1. Test-fixture faults the assistant made and caught** *(historical — fixed)*  
`other` · chat-b · blowup_test.py, tok_test.py, curve_test.py, harness_test.sh, resume_test.py, corpus_test.py  
Defaults referencing module constants not in the exec namespace; `(a, b), cnt, ns = None, 0, None` (invalid unpack); max_tok=3 never rejecting anything so the skip counter stayed 0 (needed max_tok=2); `base` (the legitimately empty control arm) treated as undefined; curve_test asserting two different answers for identical inputs two lines apart; PlateauGrowth built with its signature default ramp=0 so every ramp assertion passed vacuously; and THREE separate anchor drifts where an inserted block made an extract-and-exec test run code it was never written for.

**L2. "holds 0 MB" printed for a directory holding 40 kB** *(historical — fixed)*  
`wrong-measurement` · chat-c · longrun.sh top-up message; same fault in fetch_local.py ("target 0 MB" for a 400 kB request)  
Integer division by 1e6 floors anything under a megabyte to 0, and "0" reads as EMPTY — the one thing the message exists to distinguish from. An empty directory is a fetch that never happened; a short one stopped early, and they want different responses. Both print two decimals now.

**L3. Self-inflicted: `pkill -f "DATA_MODE=synthetic"` matched its own wrapper and killed the run it had just launched** *(historical — fixed)*  
`other` · chat-c · assistant's own shell commands  
Three `exit 144`s attributed to the run were the pkill killing its own wrapper's command line.

**L4. pilot-add printed "would enter -42 identity experts at step 0"** *(historical — fixed)*  
`wrong-measurement` · chat-c · longrun.sh pilot-add geometry message, `$((2048 - _CKN))` with a hardcoded FAB_N0 default  
Only the right sentence while the checkpoint holds FEWER experts than the default; the pilot's holds 2090. The default is now read from the same _SPEC line the arm list reads, and the other direction gets its own sentence.

**L5. levers.py caught the assistant reading a knob with a non-registry default to test whether it was set** *(historical — fixed)*  
`other` · chat-c · assistant's first attempt at the TOKENIZER_PATH "was it set" check  
`_env`/`_i`/`_f` raise SystemExit on call-site/registry mismatch; levers.py checks statically. "levers.py caught my first attempt at the 'was it set' check — reading a knob with a non-registry default — which is what it exists for."

**L6. Two-domain run_verify_test reported as pending a result when it had been killed by the assistant's own timeout** *(historical — fixed)*  
`other` · chat-c · assistant's `timeout 1500` on a CPU run  
exit=124 at 25 minutes, right before the WRONGNESS block it exists to produce. "I shouldn't have framed it as pending a result." Not re-queued; it is an A/B experiment rather than a regression test, so it blocks nothing.

**L7. ExpertBank path is unreachable in every real run yet retained as a smoke arm** *(historical — fixed)*  
`coupling` · chat-early · self_organize.py:63 comment; chunk_08.md:8528, chunk_09.md:625, :1024  
EXPERTS and FABRIC are mutually exclusive and lose the elif chain, so `EXPERTS=1 FABRIC=0` is the only config that reaches ExpertBank — a supported-but-never-used config. It was offered for deletion as dead code, then kept because it is one of the eleven smoke arms.


---

## Bug classes, by frequency

| class | count | what it means |
|---|---|---|
| `wrong-measurement` | 98 | the number printed is not the quantity named |
| `other` | 88 | — |
| `untrippable-guard` | 60 | a guard whose condition cannot be satisfied |
| `armed-but-inert` | 57 | a mechanism that is switched on and never runs |
| `coupling` | 47 | one lever changes another's meaning |
| `recorded-never-read` | 39 | data is stored and nothing consumes it |
| `unit-mismatch` | 32 | a quantity produced in one unit, consumed in another |
| `silent-overwrite` | 29 | state is destroyed with no error |
| `crash` | 25 | the run dies |

---

## PART 4 — defect-shaped statements recorded as facts, not as bugs

The survey's `bugs` arrays were not the only place defects landed. These are statements from the
`facts` and `carry_forward` arrays that describe something broken, inert, or self-contradictory and
that did not appear in Parts 1-3. They are *unverified* by construction and several will turn out to be
descriptions of intended behaviour — but a work list built only from the `bugs` field would have missed
them, which is itself the `recorded-never-read` class applied to this document.

- **[archive/facts]** DECISION/INVARIANT — fab_logits() is the SINGLE hidden→logits path; a new consumer of model output MUST use it or a fabric-trained checkpoint silently runs the wrong forward pass. This bug hit at least 3 times.  
  `archive/handoff/decisions/fab_logits-is-the-single-hidden-to-logits-path-and-diagnostics-never-crash-a-run.md:4-7; still asserted live at self_organize.py:4001`
- **[archive/facts]** DESIGNED-BUT-NOT-BUILT — corroboration-based wrongness detection (does an entry disagree with its nearest neighbours?) was proposed as the only plausible fix for B's ~1% precision and never built.  
  `archive/handoff/designed-but-not-built/corroboration-based-wrongness-detection.md:3-6`
- **[archive/facts]** The 11 process/ rules are the project's working protocol: report every add/remove/change AND omission; end each build with a recommended next step and who does it; estimate wall-clock before any GPU run; bias toward pruning; flag [me] defaults and ask rather than silently default; name sandbox blockers explicitly and hand off ready-to-run commands; no GPU here (user runs H100 and pastes results); disclose the CPU-only + network-allowlist sandbox; develop on the designated branch; update STATE.md before responding; verify ledger edits actually landed.  
  ``ls /home/user/LLM-Test/archive/handoff/process` → 11 files, each named for its rule`
- **[archive/facts]** The most operationally important process rule is 'verify the edit landed': STATE.md silently stopped being written to disk for ~30 turns while later turns narrated edits to it, and that is named as the single root cause of the project's worst drift.  
  `archive/handoff/process/verify-ledger-edits-actually-landed-before-claiming-success.md:3-6; archive/STATE.md:5-6`
- **[archive/facts]** The archive records that D_MODEL_B was read by NOTHING — self_organize.py reads D_MODEL and only run_full_unfrozen.sh translated the name — so a direct D_MODEL_B=768 run silently used the d=128 default, including in the pilot command handed to the user.  
  `archive/STATE.md:198-202`
- **[archive/facts]** The 12 history/ files reconstruct Phases 0–11 and are the narrative source for how each decision was made; STATE.md §6 declares the phase framing canonical over the older inconsistent turn labels (T33, T18/T24).  
  `archive/STATE.md:15; archive/STATE.md:564-577; `ls archive/handoff/history | wc -l` → 12`
- **[chat-a/facts]** INSTRUCTION (L1721): "The vocabulary size increse looks liek too much, 640 when at 2k, is almost 30%. / The increase should be more like 5-10% each time. Similarly for the experts, at a similar percentage.. / It works, now lets see it in action, and run some more pilots to see if it improves." — this reverses the owner's own earlier "linear (so not 1.1x)" instruction; the assistant flagged the reversal explicitly rather than switching silently.  
  `jsonl:1721; assistant at :1776 ("This does reverse your earlier 'linear, not percentage' instruction, so I want to be explicit rather than quietly switch")`
- **[chat-a/facts]** QUESTION (L2254): "Are these enough?" (round11); (L2331) "What happened? It didn't go down, and never reached the loss of the short runs" (the 0.75 GB run); (L2473) "Looks worse again" (round13).  
  `jsonl:2254, jsonl:2331, jsonl:2473`
- **[chat-a/facts]** ASSISTANT ASSUMPTION THAT WAS WRONG: it claimed the GROW_CAP soft-cap mechanism did not exist and had to be built, when the owner remembered correctly that it did. "You're right and I was wrong — the mechanism exists. I missed it because it isn't in the groups I dumped, and because GROW_CAP defaults to 0, so it has never run." The proximate cause was a stale note: notes/02_IDEAS.md A91 said "NEVER IMPLEMENTED" while citing the very commit (e2db890) that implemented it.  
  `assistant at jsonl:908, :1015`
- **[chat-a/facts]** MEASURED (round5, runs/round5, cull-gate arms, judged on DID IT FIRE as pre-committed): base 23 culls all sustained-error, 0 utilization culls, 0 spares, rescue unreachable; gate_nmax 296/5/291/1578; gate_press 220/16/204/1253; gate_soft 484/35/449/2749; gate_nmax_resc 104/16/88/3211 with FAB_RESCUE firing 203 times — the first ever measurement of A92.  
  `assistant at jsonl:1499; grid summary at :1450`
- **[chat-a/carry_forward]** Judge structural interventions on DID IT FIRE, not on bits/byte, and commit to that before seeing the numbers. 'An arm that changes nothing AND never fires is a different finding from one that fires and changes nothing — only the second is about the idea.'  
  `assistant at jsonl:1092, :1446`
- **[chat-a/carry_forward]** 'Unreachable' is not the same as 'inert', and the audit must distinguish them — they have different fixes. A mechanism reported as ARMED AND INERT when the run simply never asked reads as 'the idea does not work'.  
  `assistant at jsonl:1376, :1387`
- **[chat-a/carry_forward]** `longrun.sh grid` skips completed arms and never overwrites a finished log; `pair` runs both arms over the SAME seeds so they cannot be compared unpaired by accident. These are the mechanical enforcement of the owner's no-overwrite constraint and of paired comparison.  
  `owner-pasted harness output at jsonl:651; assistant at :714`
- **[chat-b/facts]** ASSISTANT CONTAINER: /home/user/LLM-Test, has NO torch installed, so mem_evict_test.py and growth_test.py cannot be run there — they are written for the owner's box and shipped unrun.  
  `transcript:L3697 ("ModuleNotFoundError: No module named 'torch'"), L4448, L5309 ("those four checks are unrun until you run them on your box")`
- **[chat-b/facts]** ASSISTANT CONTAINER: huggingface.co is UNREACHABLE through the agent proxy (CONNECT tunnel failed, 403); pypi.org and files.pythonhosted.org return 200 and `pip download` works at ~56 MB/s.  
  `transcript:L4034, L4037, L4246, L4251`
- **[chat-b/facts]** MEASURED (sched_ctl): final step 282744, vocab 2048/2048, population 3685/8192, 3160 grown / 1523 removed / net +1637, 5 capacity-valve lifts (3000->3240->3499->3778->4080->4406), longest spell at cap 39363 steps against GROW_CAP_EVERY=20000. The final soft cap 4406 was never used.  
  `transcript:L2887`
- **[chat-b/facts]** MEASURED (two identically-labelled held-out numbers): 36 finished logs carry BOTH the MEMORIZATION CHECK figure (what compare.py and runs.py read) and the `SAMPLED FROM ... (X held-out bits/byte)` figure (what a human greps). 27 of 36 disagree by more than compare.py's own 0.03 "worth resolving" floor; the largest gap is 0.190 (lr_vcap 2.178 vs 1.988), then pop1024 2.104/1.966 (+0.138) and pop128 2.289/2.156 (+0.133). Signs go both ways.  
  `transcript:L3767, L3785, L3788`
- **[chat-b/carry_forward]** A default that cannot fire is worse than one that is off: WRITE_QUANTILE=1 gated behind WRITE_ADAPTIVE=0; TOK_ANCHOR=0.05 whose loss term never enters the loss; LR_DECAY/LR_RESTART_DAMP unreachable on every arm that would be run. Every such knob needs a DID IT FIRE row that distinguishes 'off by arithmetic' from 'armed and inert'.  
  `transcript:L3144, L3235, L5277, L5399`
- **[chat-c/carry_forward]** There are TWO preallocated geometries and they must be reasoned about separately: the fabric slot pool (FAB_NMAX → A, B, SRC_p, K_p, cent) and the softmax width (VMAX → emb.weight, head.weight, head.bias). emb/head/bias are in the MODEL optimizer, so widening the softmax invalidates om's moments exactly as widening the fabric does. FAB_RANK and FAB_DK are INNER dimensions — they cannot be prefix-widened and a mismatch is fatal by design.  
  `chat L5849, L5856, L5942, L5985`
- **[chat-c/carry_forward]** RATE_EVERY gates the per-process curve probe as well as the rate meter. Setting RATE_EVERY high to suppress smoke-run output silently removes the table you are trying to verify.  
  `chat L5743, L5810`
- **[chat-c/carry_forward]** Every guard must be expressed in the same units as the thing it guards. Two failed on this: `len(_used) * 10 < len(_uv)` compared 32-window probe winners with whole-run winners; `if ninj > 0 and len(procs) < 2` used set(labels) where the sampler needs window-aligned positions. Build the candidate list first and test IT, so the guard and the consumer cannot disagree.  
  `chat L7036, L6479, L6520`
- **[chat-c/carry_forward]** Three items were REPORTED AND DELIBERATELY NOT FIXED and must survive into the bugs/issues list: MEMORY PRESSURE cannot reach its threshold on this configuration (probation is 82% of the store, so the signal is pinned at ~0 and its silence reads as health); MEM_WRONG_READ gates only the report's own evaluations because selfcheck() is called once from the report while every write resets selfcon to -1; TOK_ANCHOR has never once entered the loss because it is gated on TOK_COMPOSE=0 while printing on the EFFECTIVE line of every run.  
  `chat L7036, L7141, L7527, L6727`
- **[chat-c/carry_forward]** AMP=fp16 is REFUSED, not fixed, and on purpose: adding a GradScaler changes the optimizer step, which is now gated on accumulated backward passes, and an unscale at the wrong point in that cycle silently breaks accumulation instead. bf16 is what an H100/GH200 wants anyway.  
  `chat L6152, L6163, L6166`
- **[chat-early/facts]** ENVIRONMENT: `bc` is not installed on the GPU box — `fetch_data.sh` printed "line 69: bc: command not found" four times, silently zeroing every corpus size report ("eng 40040948877 bytes (0.0 MB)")  
  `notes/_evidence/chat/user_turns.md:4235-:4244`
- **[chat-early/carry_forward]** 2026-07-29/31 — Harness era begins: rerun.sh (mix / eng / ablate / smoke arms, 2026-07-29) then longrun.sh (pilot regime, 2026-07-31). Defaults were changed so subsystems are ON by default after the owner found things silently off in prior tests ("Change defaults to have things on. Since things were off in prior tests, do we need a rerun?", asked four times).  
  `notes/_evidence/chat/chunks/chunk_05.md:3815 (rerun.sh, 2026-07-29T20:46), :7309 (longrun.sh, 2026-07-31); notes/_evidence/chat/user_turns.md:7159-:7172`
- **[chat-early/carry_forward]** 2026-08-04/05 — Chaining landed and became the default path (SOCIETY=0 + CHAIN_ROUTE=soc + CHAIN_VOTE=1, 'chained society'). The owner's definition: 'the society system, but allowed to loop over and over, (in chains)'. HALT was found computed-and-discarded on the society path and had to be wired in.  
  `notes/_evidence/chat/user_turns.md:9323, :9483, :9509, :9694; notes/_evidence/chat/chunks/chunk_07.md:3502`
- **[harness/carry_forward]** Both `pilot-add` and `add` must read the checkpoint's fab_cfg and export FAB_N0, FAB_NMAX (2x cap), VMAX (2x V, NOT 2x tok_vocab), FAB_RANK and FAB_DK, each behind its OWN `[ -z "${X:-}" ]` test. Nesting them inside one gate meant that setting FAB_N0 by hand silently reverted VMAX to 2048 and FAB_NMAX to 4096.  
  `longrun.sh:770-807 (pilot-add), longrun.sh:990-1010 (add); the V-vs-tok_vocab reasoning is inline at longrun.sh:752-757`
- **[notes-num/facts]** The notes corpus was written against branch `rm-predict` at HEAD `92a967b` (2026-08-15); this checkout's branch is `rm-predict-DC` at `aee4a52` (2026-08-28), and `git cat-file -t` cannot resolve 92a967b, a5cc7ea, c76dc74, 5f4f117, cc0a377, a9d7258, e9f2e58, daf9f89 or 9645050 — the entire hash vocabulary of the notes is unreachable from any branch in this checkout.  
  `notes/01_TIMELINE.md:37 "HEAD at time of writing is `92a967b` (2026-08-15)"; `git rev-parse --short HEAD` → aee4a52; `git cat-file -t c76dc74` → "fatal: Not a valid object name"`
- **[notes-num/facts]** `runs.csv` has NOT been updated since 2026-08-15 — its last commit is `d3d2bdc` — so none of the 2026-08-26..28 work (the 0.75 GB run, rounds 15–18, the two CL arms that "disagree by 10x") appears in it, and 04_RESULTS' master table is the complete run record only up to 08-15.  
  ``git log -1 --format='%h %ad' -- runs.csv` → d3d2bdc 2026-08-15; `git log --oneline` shows commits b990c9d/3174460/934789d/271f875 dated 2026-08-26..27 describing runs absent from the CSV`
- **[notes-num/facts]** 07_WIP §6 verifies that `retire_stale`, `fuzzy_segment` and `track_usage` are defined and never called in the live tree; this is still true at HEAD — `fuzzy_segment` is reached only behind `getattr(self,'_use_fuzzy',False)` which nothing sets, and `retire_stale`/`track_usage` have no live caller.  
  `notes/07_WIP.md:309-313; tokenizer.py:391,396 (`_use_fuzzy` guard), tokenizer.py:402,420 (definitions); grep over the live tree finds no call site`
- **[notes-num/facts]** `longrun.sh`'s `_flags_for` now defines 99 arms, against the 52 recorded in 03 Part III and 07 §7 and the 46 in 08_GLOSSARY — so the "29 run / 23 never run" inventory is measured against a list that has nearly doubled.  
  ``sed -n '163,533p' longrun.sh | grep -cE '^\s{4}[a-z0-9_|]+\)\s+echo'` → 99; notes/03_EXPERIMENTS.md:800; notes/07_WIP.md:330; notes/08_GLOSSARY.md:725`
- **[notes-num/facts]** `runs/` does not exist in this checkout at all and is gitignored, so it was never tracked. Every log-derived count in the corpus (07_WIP's 413 world-model readings across 47 directories, 09's "420 logs", 06 §7's checkpoint survey, DOC_PLAN Q10/Q11) rests on files that cannot be re-checked here.  
  ``ls runs` → No such file or directory; `.gitignore` contains `runs/`; `git ls-files runs` → 0 entries; notes/07_WIP.md:459, :613; notes/09_COMMENT_AUDIT.md:506`
- **[notes-num/facts]** The nine recurring defect classes are named with the countermeasure each escaped: unread knob, cadence-never-coincides, diagnostic-writes-training-state, read-but-unreachable, section-vanishes-silently, maintenance-path-with-no-counter, comment-records-a-measurement, fix-that-is-itself-broken, and comparison-at-the-wrong-scale.  
  `notes/05_ERRORS.md:2383-2393`
- **[notes-num/carry_forward]** `_due` is not a predicate: it RECORDS the step and returns True, so calling it twice in one `if`/`elif` consumes the event. This killed re-segmentation entirely for three 18-epoch runs, was separately armed for `grow`, and its early-return on n<=0 silently disabled signature batching for every `RETOK_EVERY=0` arm.  
  `notes/05_ERRORS.md:353-388 (E3.3, E3.4, E3.5); notes/08_GLOSSARY.md:537-539`
- **[notes-num/carry_forward]** A maintenance path with no counter cannot be told from one that silently stopped. The corpus names `retire_stale`, `fuzzy_segment`, `track_usage`, `FAB_RESCUE`, `remap_mem_ctx`, the memory probe and the domain-prior section as instances, and now ships a count with every new maintenance path.  
  `notes/05_ERRORS.md:2390, :2461-2463; notes/07_WIP.md:315-321; still true at HEAD — tokenizer.py:391,396,402,420 have no live caller`
- **[notes-num/carry_forward]** A value can be wrong (banner), unread (typo), or read-but-unreachable — and each needed its own check because each is invisible to the others. The three layers are the derived `[config] EFFECTIVE` banner, the NOTHING-READ-THESE/not-verified audit, and the never-fired loss-term audit.  
  `notes/05_ERRORS.md:2021-2032 (E10.21), :2397-2398; notes/08_GLOSSARY.md:716-719`
- **[notes-num/carry_forward]** Prefer a RETRAINED ablation to an eval-time KNOCKOUT. They disagree badly: the FABRIC knockout said +0.709 b/B, the retrained pair said 3.089 vs 3.090.  
  `notes/08_GLOSSARY.md:640-643; notes/04_RESULTS.md:549-559`
- **[notes-num/carry_forward]** 29 retractions exist ONLY in the conversation and never reached the repo record (R21–R49 in 10_HISTORY_FINDINGS, each marked '— not in INV'). Several are still asserted in durable places: the shared-`q_route` refactor that made the chain memoryless, the 'single runs are valid' methodology that governed a week of collection, the `be50e3a` commit message, and the GPT-2 anchor.  
  `notes/10_HISTORY_FINDINGS.md:95-99, :217-224 (R32), :246-265 (R35, R36), :278-283 (R38), :337-345 (R45)`
- **[notes-num/carry_forward]** The automated drift check has a failure mode of its own: it rewrites history to satisfy a check about the present. At `0065372` it produced an altered verbatim commit quotation (06:94) and a historical table cell that contradicts its own column header (06:461), and its regexes still miss table cells and 'has X at Y' prose (07_WIP's LR_DECAY=0.0 survives).  
  `notes_check.py:103-111, :141; `git show 0065372 -- notes/06_CONTINUAL_LEARNING.md`; notes/07_WIP.md:146 still reads '`_SPEC` has `LR_DECAY` at **0.0**' while _SPEC says 1.0`
- **[notes-research/facts]** Q3 answer: per-source quota is used by NONE of the five retrieval leads. SeMem is unbounded and never evicts; CREAM prunes per-cluster with retain iff SimDist(x,p_c) < mu_c + gamma*sigma_c; TraceRetain is the only one with a real capacity bound (K=50) and its score has no source term; Goodtriever partitions into two physically separate stores; arXiv 2505.00675 was never reached.  
  `/home/user/LLM-Test/notes/_evidence/litreview/03_domain_isolation_bounded_store.md:5-20, 89-96, 146-160, 220, 258-273`
- **[notes-research/facts]** Q10 supplies the standard forgetting apparatus with formulas: the T x T matrix R_{i,j}, ACC, BWT = mean(R_{T,j} - R_{j,j}) (negative = forgetting), FWT, and Chaudhry's Forgetting Measure f_j^k = max_l (R_{l,j} - R_{k,j}) (positive = forgetting), with the instruction to report both because they disagree when a task keeps improving after training stops.  
  `/home/user/LLM-Test/notes/_evidence/litreview/11_forgetting_metrics.md:20-55`
- **[notes-research/facts]** The cache-eviction finding is explicitly accepted as a strong lead rather than a settled result ('I have not verified this against a primary source ... and it contradicts a design decision made here last week') with a cheap internal test proposed: compare the new domain's occupancy share under EVICT=lru vs EVICT=recency after a domain switch.  
  `/home/user/LLM-Test/notes/LITREVIEW_FINDINGS.md:112-124`
- **[so-config/facts]** _cfg is never called with any of the 9 derived knobs, which is necessary: their _SPEC default is None and float(None) would return None from _cfg, silently making an 'armed' predicate false.  
  `AST scan of all 40 _cfg call sites (self_organize.py:8566-8722); none names a key in _DERIVED`
- **[so-config/facts]** SEG_CONTIG's declared parent is DOMAINS, but its actual default is '1 if NP == 1 else 0' where NP is len(CORP) AFTER the 5000-byte drop filter -- so it also depends on DATA_DIR contents and CORPUS_CAP, and a partially-fetched corpus can silently flip the stream from random-offset splicing to contiguous reading.  
  `self_organize.py:1299 'SEG_CONTIG = bool(_i("SEG_CONTIG", 1 if NP == 1 else 0))'; NP set at :1147 'NP = len(CORP)' after the filter at :1142-1146; declared parent at :92`
- **[so-config/facts]** NP serves two purposes: it is the N_PROCESSES knob value on the synthetic path and the surviving-corpus count on the real path. N_PROCESSES therefore has no effect whatsoever under DATA_MODE=real.  
  `self_organize.py:539 'NP = _i("N_PROCESSES", 4)'; :1147 'NP = len(CORP)'; N_PROCESSES appears nowhere else (grep)`
- **[so-config/facts]** On the tokenizer LOAD path, MIN_PAIR, MAX_TOK and TOK_DROPOUT are never read from the environment -- DynamicTokenizer.load reconstructs them from the saved json. They are read only in the fresh-construction else-branch.  
  `self_organize.py:1226 'if os.path.exists(_tp) and (not TOK_ONLINE or _env("RESUME", "")):' -> load; :1256 is in the else branch; tokenizer.py:481-482 't = cls(d.get("vmax", 8192), d.get("min_pair", 200), d.get("max_tok", 16), d.get("dropout", 0.0), ...)'`
- **[so-config/facts]** VMAX is the one saved-tokenizer field that IS corrected on a resume, and only when it is a widening: 'if TOK.vmax != VMAX and VMAX >= TOK.vocab_size'. A narrowing silently does nothing here and is caught later.  
  `self_organize.py:1245-1254; the later refusal is ByteComposer.set_vocab at :1476-1481 (TOK_COMPOSE only) and the resume geometry gate near :4616`
- **[so-config/facts]** GROW_PASSES is never read at the default configuration: line 1225 evaluates '_i("SEED_PASSES", 2) if TOK_ONLINE else _i("GROW_PASSES", 8)' and TOK_ONLINE defaults to 1. Symmetrically SEED_VOCAB (1224) and SEED_PASSES are never read when TOK_ONLINE=0.  
  `self_organize.py:1224-1225; :137 '"TOK_ONLINE": ("i", 1)'`
- **[so-config/facts]** EXPOSURE_MAX and EXPOSURE_SKEW are read only inside 'if DATA_MODE == "real" and NP > 1', so on a single-corpus run -- the configuration for goal A -- neither is ever read and the exposure/imbalance warnings cannot fire.  
  `self_organize.py:5497 guard; reads at :5535, :5538, :5544, :5546`
- **[so-config/facts]** AMP is the only string knob in the region that is case-normalised. DATA_MODE, SIG_MODE, MODEL, VERIFY, KEY_SRC, LR_SCHED, SIG_SPACE, WARMSTART_MODE, TOK_PROBATION_BY, CHAIN_ROUTE, CULL_MODE and EVICT are all compared case-sensitively, so DATA_MODE=Real silently takes the synthetic branch.  
  `self_organize.py:1063 'AMP = _env("AMP", "off").lower()' vs :1102/:1120 'DATA_MODE = _env(...)' then 'if DATA_MODE == "real":' with no normalisation`
- **[so-config/facts]** ENC_WARMUP_MIN must be strictly below ENC_WARMUP or the adaptive early stop is unreachable, because the code takes min(ENC_WARMUP_MIN, ENC_WARMUP). The registry default 200 against ENC_WARMUP 800 satisfies this; the shipped state was once 3000 against 800.  
  `self_organize.py:336-342`
- **[so-config/facts]** FAB_PRESSURE=0.45 is documented as a SETPOINT that chooses the operating population (pressure x cap), not a threshold; at the previous 0.75 against FAB_N0=2048/FAB_NMAX=4096 occupancy parked at 0.50 and the utilization cull, the utilization spare and FAB_RESCUE -- all three of which live behind cull_gate_open -- were unreachable.  
  `self_organize.py:201-209; cull_gate_open at :823-836 'return not (n_live <= 2 or (n_live / max(1, cap)) < pressure)'`
- **[so-config/facts]** BLOWUP_RISE/BLOWUP_STALE and CURVE_RISE_BLEWUP/CURVE_FLAT/CURVE_TOK_RISE are module constants, not registry knobs, so they cannot be swept from the environment and do not appear in the config audit.  
  `self_organize.py:748-749 and :782-784; neither name appears in _SPEC`
- **[so-config/facts]** `glob` is imported at line 18 and never used anywhere in the file.  
  `self_organize.py:18 'import os, math, random, glob, json, sys, contextlib, functools'; `grep -c 'glob\.'` returns 0`
- **[so-config/facts]** TinyTransformer has no ByteComposer at all -- no s.compose attribute, and forward is 's.head(h)' unconditionally -- so TOK_COMPOSE has no effect on MODEL=transformer.  
  `self_organize.py:1563-1594; the composer hookup at :4219 requires 'getattr(model, "compose", None) is not None'`
- **[so-config/carry_forward]** A saved tokenizer carries its OWN vmax, min_pair, max_tok and dropout in the json. On a resume only vmax is corrected from the environment; the other three are silently the parent's.  
  `self_organize.py:1229-1254; tokenizer.py:474-482`
- **[so-config/carry_forward]** ENC_WARMUP_MIN must be strictly below ENC_WARMUP; the code takes min(ENC_WARMUP_MIN, ENC_WARMUP), so an inverted pair collapses the floor onto the full warmup and the adaptive early stop can never fire.  
  `self_organize.py:338-342`
- **[so-config/carry_forward]** MANAGE_MERGE is a POLICY knob, not a correctness one: `did` is consumed only by mem.src provenance, dom_exp reporting and the clustering report -- routing uses the continuous gist, so the domain COUNT sets the granularity of FORGETTING, not prediction quality. Never read the domain count without purity and homogeneity beside it; 0.80 also reaches '4 domains' with purity 0.71.  
  `self_organize.py:559-588`
- **[so-fabric/facts]** With FAB_DERIVE_IDS=1 (default) the free parameters K_p and SRC_p are never read for routing; the K/SRC properties exist only so old write sites (grow) still work.  
  `self_organize.py:1930 `if not s.derive_ids: return s.K_p[:N], s.SRC_p[:N]`; :2008-2016 property K/SRC docstring "simply unused while FAB_DERIVE_IDS=1"; :2143-2145 writes`
- **[so-fabric/facts]** FAB_MIN_STEPS is force-zeroed whenever CHAIN_VOTE=1 (the default), and an explicit non-zero env value raises SystemExit rather than being silently discarded.  
  `self_organize.py:1860-1868`
- **[so-fabric/facts]** FAB_RESCUE defaults to 0.0, so the one path that makes use and uage diverge (rescue keeps use, zeroes uage) never runs by default.  
  `self_organize.py:694 `FAB_RESCUE = _f("FAB_RESCUE", 0.0)`; :2280-2290`
- **[so-fabric/facts]** `failing()` returns False whenever the fast error EMA exceeds the slow one by more than shift_tol, so an adapting expert cannot be culled by the error route by construction.  
  `self_organize.py:2189-2194`
- **[so-fabric/facts]** The mid-chain spawn is gated on `fab._hopq` being non-empty, so under CHAIN_ROUTE=soc it can never fire.  
  `self_organize.py:7337 `if FAB_SPAWN and fab._hopq and fab.n() < _cap_fab[0]`; :1810 `s._hopq = []``
- **[so-fabric/facts]** Deep supervision is gated on len(fab._hops) > 1, so CHAIN_SUP is unreachable under CHAIN_ROUTE=soc even if set above its 0.0 default.  
  `self_organize.py:7003 `if FABRIC and not SOCIETY and fab.sup_w > 0 and len(getattr(fab, "_hops", [])) > 1``
- **[so-fabric/facts]** maybe_deepen returns immediately unless CHAIN_CURRIC=1, which defaults to 0, so `deepened` is always empty and staged depth never runs in a default run.  
  `self_organize.py:2522 `if not s.curric or s.depth_now >= s.max_steps: return None`; registry :145 `"CHAIN_CURRIC": ("env", 0)``
- **[so-fabric/facts]** grow() always returns [] because the rows already belong to preallocated Parameters, so the caller's add_param_group branch is dead by design.  
  `self_organize.py:2151-2152; :7487 `if _fp: om.add_param_group({"params": _fp})``
- **[so-loop/facts]** The CULL GATE line computes occupancy against the SOFT cap when FAB_PRESS_SOFT else `_F.cap` (the preallocation), and states that when SHUT the utilization cull, the utilization spare and FAB_RESCUE are all unreachable because the latter two live inside that gate.  
  `self_organize.py:6168-6177`
- **[so-loop/facts]** The learning-curve `except` deliberately prints once rather than swallowing silently: "a silent except here hid the whole learning curve, printing nothing at all".  
  `self_organize.py:6417-6420`
- **[so-loop/facts]** The code itself declares that `mem.pressure()` CANNOT reach its own threshold on this configuration: eviction narrows to probation whenever probation is over budget, every write lands on probation, and only retrieval promotes out of it -- at a measured 11.7M writes into 200k slots against 1469 read probes, probation is 82% of the store and permanently over budget, so n_main_evict stays near zero.  
  `self_organize.py:6572-6581; the PROBATION IS Nx ITS BUDGET alarm at 6582-6593`
- **[so-loop/facts]** `om.add_param_group({"params": _fp})` is guarded on `if _fp:` because grow() returns [] with preallocated tensors; adding an empty group anyway appended one phantom param group per growth event, so load_state_dict refused the count mismatch and every Adam moment was discarded on every resume.  
  `self_organize.py:7484-7492`
- **[so-loop/facts]** Probation uses its own `_due("probation", GROW_EVERY)` key rather than `_due("grow")`, because `_due` RECORDS the step and returns True -- asking it under the grow key would consume the grow event and the minting block would never fire.  
  `self_organize.py:7583-7591; _due at 5283-5285`
- **[so-loop/facts]** Branching entropy cannot be a post-probation test because minting DESTROYS the evidence: greedy longest-match consumes a+b into the merged token so the pair never occurs again and p(b|a) is 0 from the merge onward (measured 0 after forty more passes). Entropy is therefore a PRE-mint criterion, which is where TOK_MINT_PMIN already is.  
  `self_organize.py:6314-6319`
- **[so-loop/facts]** A single `_due` call guards the retok if/else: asking `_due` twice in one if/elif CONSUMED the event, so the retok never ran, `_last_vsz` (written only inside the retok body) stayed at the seed value, and the skip branch could never fire either -- BOTH paths were dead across three 18-epoch runs.  
  `self_organize.py:7726-7733`
- **[so-loop/facts]** Per-window loss is kept (`reduction="none"` then `.mean()`) at identical cost, because COMPETENCE tracking cannot be done without the per-window numbers.  
  `self_organize.py:6900-6902, 6918-6919`
- **[so-model/facts]** _eval_sig returns None on any exception and the caller silently falls back to the zero gist; nothing counts how often that happens.  
  `self_organize.py:3926-3927 `except Exception: return None``
- **[so-model/facts]** compose_test returns silently (no output at all) when there are no windows or no valid memory entries.  
  `self_organize.py:3724 `if not wins: return`; 3730 `if vi.numel() == 0: return``
- **[so-model/facts]** fab.use is filtered to keys < ck_n on restore, so any recorded utilization for slots beyond the checkpoint's live count is discarded.  
  `self_organize.py:4530`
- **[so-model/facts]** A soft cap below the starting population is refused with SystemExit, because the growth clamp min(burst, soft_cap - n) would be negative and nothing would ever grow, silently.  
  `self_organize.py:5228-5249; clamp at 7446`
- **[so-model/facts]** In the per-owner store, allocation is purely block-arithmetic (base = owner*quota) and self.own is written but never read for allocation; own is initialised to -1, not 0.  
  `memory.py:38, 216-240`
- **[so-report/facts]** The per-process surviving-memory line silently drops any memory whose source domain is not a key of `s2t` (a domain with no window in `assigns`, or the injected src=99), so the printed counts need not sum to the active store.  
  `self_organize.py:9822-9824 `for _d, _c in Counter(mem.src[mem.active].tolist()).items(): if _d in s2t: _cnt[s2t[_d]] += _c``
- **[so-report/carry_forward]** Section verdict thresholds are hardcoded and inconsistent across sections that use the same words: LOCAL is |delta|<0.1 in `_edit_test` and <0.05 in the final UNLEARN; INDEPENDENT is |mean collateral|<0.3; DOMAINS PREDICT needs both gaps >0.01; SPECIALIZED needs >2 sigma of an EXPERT_NULLS-sized shuffle; PARTITION INFORMATIVE needs >2 sigma of an INFO_NULLS-sized permutation; RETAINED/DRIFTING/CATASTROPHIC at 0.10/0.40.  
  `self_organize.py:9839, 9852, 9021, 8199, 9166, 3843, 8097`
- **[subsys/facts]** EditableMemory's cap is DERIVED, not configured, when the per-expert partition is on: n_own>1 replaces cap with n_own*quota, so MEM_CAP is silently overridden (at defaults 64 owners x 128 = 8192 slots instead of 200000).  
  `memory.py:35-37 `self.quota = int(quota) if quota else int(cap // self.n_own)` / `if self.n_own > 1: cap = self.n_own * self.quota`; warned at self_organize.py:5622-5628`
- **[subsys/facts]** The quantile gate lives INSIDE the adaptive branch, so WRITE_QUANTILE (registry default 1) has no effect unless WRITE_ADAPTIVE (registry default 0) is also on.  
  `memory.py:133 `if self.adaptive_gate and self.quantile_gate:`; self_organize.py:6111-6115 emits a coupling warning saying exactly this`
- **[subsys/facts]** write_batch silently writes nothing for any row whose ctx is None, and returns 0 outright if no row has a ctx.  
  `memory.py:170-171 `if not ctxs: return 0`; memory.py:178 `if ctx is None or m == 0: continue``
- **[subsys/carry_forward]** The tokenizer file carries its own vmax, min_pair, max_tok, dropout and max_pairs. Only vmax is repaired on resume; the rest silently override the environment.  
  `tokenizer.py:473-483; self_organize.py:1229-1254`
- **[tests/facts]** The end-to-end config is DOMAINS=eng, i.e. NP=1, so every NP>1 path is unreachable in the only real run the suite performs.  
  `selftest.sh:114 `DOMAINS=eng`; self_organize.py:5497 `if DATA_MODE == "real" and NP > 1:``
- **[tests/facts]** notes_check.py guarantees: notes/CURRENT_DEFAULTS.md is byte-identical to what generate() produces from _SPEC; ARCHIVE.md exists whenever archive/ does; and no non-historical line in a scanned .md states a default value _SPEC contradicts. _SPEC currently holds 328 knobs and 20 files are scanned.  
  `notes_check.py:155-163, :165-169, :171-181; run output 'notes_check: 328 knobs, 20 live markdown files'`
- **[tests/facts]** blowup_test.py guarantees, against the AST-lifted blowup_stale and module constants: the two real healthy curve openings that defeated the old rule fire the old rule and not the new one; a single 4.82 spike cannot fire it; two blow-up-shaped curves fire with most of the run left; BLOWUP_STALE sits above every measured healthy run (max 50) and below both blow-ups (min 261) with >=1.5x margin; the rule needs >=3 probes, a best, elevation AND staleness; and it re-arms on a new best so a run can be warned twice but does not chatter.  
  `blowup_test.py:92-159`
- **[tests/facts]** curve_test.py does NOT cover how curve_verdict's INPUTS are computed. `_bpb_dir` (rise since minimum, change over the last two thirds) is built inline in main() inside a bare `except Exception: _bpb_dir = None`, so a failure there silently removes the whole verdict with no message.  
  `self_organize.py:8255-8262, :8290-8294`
- **[tests/carry_forward]** Anything selftest.sh does not name explicitly is skipped. Two tests (corpus_test, resume_test) sat unwired for a whole session, silently omitting ~120 checks. The file now states what it deliberately does NOT run and why.  
  `selftest.sh:72-77, :84-94`
- **[tools/facts]** fetch_big.py cannot be exercised in this environment: the `datasets` package is not installed, and its own docstring says the download path was never tested end to end.  
  ``python3 -c "import datasets"` -> ModuleNotFoundError; fetch_big.py:5-6 "this sandbox's network is allowlisted to GitHub/PyPI only, so I cannot reach HuggingFace/S3 to test the streaming path end-to-end"`
- **[tools/carry_forward]** Direction is per-metric and must be applied to EVERY printed quantity, not just the statistics. compare.py orients the pairs for the bootstrap but leaves the per-seed diff column raw, so the headline and the table disagree in sign on d_order1.  
  `compare.py:126-133 (the header note), :273 (opairs), :282-284 (oriented mean) vs :302 (raw per-seed diff); reproduced -0.6000 headline against +0.6000 per-seed rows`
- **[tools/carry_forward]** fetch_big.py's preset lookup accepts both the short key and the full dataset id (fetch_big.py:112-114), but `is_dialogue` at :212 still compares only the short key — so `--dataset OpenAssistant/oasst1` silently loses the turn markers the preset exists for.  
  `fetch_big.py:105-114 (the fix, with its own commentary) vs fetch_big.py:212 `is_dialogue = a.dataset == "oasst1"``
