# Commit record, reconstructed from two sources

The repository's git history begins 2026-08-15. Everything before that survives only in
notes/_evidence/commit_log.txt, which spans 2026-07-21..2026-08-15. Neither alone is the record.

## 2026-07-21 .. 2026-08-15  (267 commits, from notes/_evidence/commit_log.txt)

### 2026-07-21  (23)
- fix: Verification failed in the product loop; fit Reconstructor post-hoc
- probe: keystone validated - functional embedding via cross-content transfer
- build: Verification acts - exclude unverified from reads + VERIFY_SWEEP delete
- handoff: document big-data provenance (streamed slices, never in git)
- state: record GPU-confirmed Verification A/B (AUC 0.980 vs 0.907)
- docs: add one-paste Python-console launcher for the Verification test
- add self-contained console A/B test; reconstruction validated on real data (CPU)
- add run_verify_test.py: single copy-paste script for the Verification A/B
- docs: reject strict per-domain quota; memory-pressure -> grow/retrain/split
- build: Verification (reconstruction) - Reconstructor + opt-in wiring, CPU-validated
- handoff: lock the naming pass (B->Verification, Fabric->Router+Compositor, Sense=modality)
- handoff: add STRUCTURES.md naming pass (clarify what each structure is)
- docs: rename B->V in the CL_TESTBED loop diagram (residual)
- docs: rename B (wrongness) -> V (Verify); set signal handling; gap list
- handoff: surprise is a learning driver (not truth); add reverse embedders
- handoff: tool-experts, router-as-embedder, and the unifying primitive
- handoff: refine directions - subcontracting via router; senses at tokenizer layer
- handoff: capture the interchangeable-base + emergent-subspecialties direction
- handoff: capture the north star and its growability invariant
- handoff: fold in prior-context export; rebuild STATE.md with self-verify
- handoff: add chat-to-chat context-exchange folder
- docs: add file map + handoff, reconcile stale ledger references
- Add overarching continual-learning package

### 2026-07-22  (6)
- fix: fetch_data.sh leaked Brown POS tags (lowercase) into eng corpus
- state: 5x-steps run - Verification failure is real (not undertraining); model now data-limited
- state: caveat that product-loop numbers are from underfit short runs
- state: honest - reconstruction hits the base-rate wall in the product loop
- docs: add fresh-box preamble (clone + deps) to COMMANDS.md
- fix: run scripts had a dead hardcoded cd ~/overarching-package

### 2026-07-23  (11)
- handoff: correct world-model direction to a GENERAL, physics-like, multimodal model
- handoff: capture 'world model built within the system' as a core design direction
- handoff: capture two design directions (active-learning closed-book, partial compartmentalization)
- feat: report live tokenizer vocab growth at each retokenization
- fix: fetch_big.py clean exit + safer Next-command suggestion
- state: R28 - rescue outcome, honest correction (no checkpoint saved), prompt.py fix
- fix: prompt.py accepts CKPT= (and other KEY=VALUE) as command-line args
- fix: rescue_ckpt.py logs to ~/rescue_status.txt (durable) + absolute ckpt fallback
- feat: rescue_ckpt.py - dump a full promptable checkpoint from a live run via pyrasite
- feat: checkpoint-on-demand via SIGUSR1 (force a save without killing the run)
- feat: mid-run checkpointing (CKPT_EVERY) so long runs are killable/promptable

### 2026-07-24  (33)
- chore: gitignore per-run tokenizer/checkpoint artifacts
- fix: persist and correctly restore the per-expert memory partition
- fix: apply the world-model feedback once, centrally, so evals run the network that was trained
- feat: per-expert LRU memory (implemented, default OFF on measurement)
- feat: burst growth to a large expert population, and three fixes that make it mean something
- perf+fix: sparse top-k experts, and revive the routing parameters that received no gradient
- fix: memory provenance positions were byte/token misaligned, so grounded lookups read the wrong text
- fix: five critical defects that made the multi-epoch run test something other than the system
- fix: single-domain runs crashed in the eval battery; add live domain/boundary counter
- fix: quantile write gate (WRITE_TARGET was silently ignored) + tail-only retokenization
- test: SIG_BATCH measured -- sig_of 9%->3%, +10.4%, bit-identical on the stress case
- perf: SIG_BATCH -- batch sig_of over the span where the encoder is provably frozen
- test: KEY_BATCH A/B -- equivalence measured, and no CPU speedup, as predicted
- perf: batch the memory-key encodes -- attack call count, which is what the A100 profile blamed
- fix: D_MODEL_B was read by nothing -- every direct run silently used d=128
- bench: report param count, fix the LAYERS confound, flag that the 85% figure is data-dependent
- feat: GPU throughput bench (bench_gpu.sh) + BENCH=1 early exit
- perf: isolate the two contrastive_step changes -- gather is bit-identical, fuse is not
- perf: add ENC_FUSE flag; the encoder fusion is equivalent but not bit-identical
- perf: cut the real bottleneck -- contrastive_step, measured at 87% of the loop
- perf: profile the loop, encode memory keys behind the surprise gate, drop per-step host syncs
- fix: make the checkpoint complete (world model + RESUME) and the ETA honest
- feat: disk-streaming data loader (DISK_STREAM) -- data disk-bounded, not RAM-bounded
- fix: world-model collapse bug + RECON_W=0 waste + clean EPOCHS mechanism
- perf: no-compromise fixes -- amortized rekey + shift-gated encoder (keep full functionality)
- feat: world-model feedback link -- forecast conditions the base LM's generation
- perf: adaptive SigEncoder warmup + SELF_ORG switch to disable domains
- feat: separated world model (DynamicsPopulation) verified end-to-end; honest negative on specialization
- test: retune population probe - decaying balance, param-matched monolith, K=5
- feat: separated world model (DynamicsPopulation) - routed society of dynamics predictors
- chore: gitignore generated tokenizer caches (data/dyntok.json, data/tok_*.json)
- feat: integrate world model into the stream + robust held-out eval; document undertraining finding
- feat: world_model.py - first brick (latent forward-dynamics core), CPU-verified

### 2026-07-25  (15)
- domains: the encoder budget was the dominant term, and management was never running
- domains: measure the acceptance radius instead of assuming it, and fold what never recurs
- metric: judge domains on RECURRENCE, not on recovering the seeded corpora
- revert defaults to the best MEASURED config; add DOM_RADIUS; guard the sweep against unread knobs
- fix: recalibrate the scale-free shift test -- q75*2.0 switched boundary detection OFF
- fix: scale-free assignment AND boundary detection, validated against the signature probe
- fix: ENC_POS_MAX above its default crashed contrastive_step; probe_signature bug workaround
- fix: adaptive domain spawn threshold -- a fixed NEW_DIST made re-entry impossible
- fix: profile attribution divided a WINDOW's time by the WHOLE run's elapsed
- fix: completeness formula was homogeneity; guard TOKENIZER=1 without DATA_MODE=real
- fix: domain over-segmentation -- the assembler was partitioning by SPLICE SEGMENT, not by corpus
- feat: KEY_LAYERS + cached causal mask; apply route_t on the chaining path
- feat: fetch_40g.sh + resumable fetch_big.py for the multi-epoch corpus
- fix: GH200 readiness -- aarch64 torch trap, the memory blend rule, and the generation path
- feat: preflight.sh -- fail loudly on a fresh box before burning GPU hours

### 2026-07-26  (2)
- report: the adaptive warmup claimed a plateau it never detected
- fix: four cadences below the batch accumulator never fired when BATCH_W > 1

### 2026-07-27  (9)
- measure retention -- the continual-learning claim rested on a test that had never been run
- domains: measure whether the partition means anything, without the seeded labels
- domains: the consolidation scale was 3x tighter than the creation scale, and had been since the start
- signature: make what the encoder reads a measurable choice, and let it grow with the vocabulary
- fix: SAVE_CKPT=0 wrote checkpoints to a directory named `0`, and it got committed
- guard: warn when a splice segment is only a few analysis windows long
- retract the COLLAPSE CHECK verdict; add the probe that can actually settle it
- perf: size the signature encoder by the stream it reads, not by the LM's vocab
- report: separation was measured with an order statistic that shrinks as the population grows

### 2026-07-28  (2)
- add the two metrics the audit said were missing: an anchor for bits/byte, and coherence as a number
- non-stationary by default, and fix the two things that kept it from being usable

### 2026-07-29  (9)
- prep the reruns: catch the store-size override, add a launcher, widen the knob trap
- every subsystem on by default -- five more were off besides the fabric
- the router fabric was OFF in every run of this project
- make domains available to PREDICTION, and measure whether they earn it
- give the informativeness null an error bar -- the verdict was flipping on noise
- the signature encoder was collapsing on homogeneous text; the other corpora were hiding it
- detect encoder collapse -- the adaptive warmup could not tell convergence from it
- report why the partition test cannot run, instead of letting the section vanish
- add the sample-efficiency half of continual learning, and a test for DISCOVERY

### 2026-07-30  (3)
- smoke gate: 4 min instead of 20, on the GPU if there is one
- probe sidecar: ask the geometry and stability questions off the GPU box
- the ablation arms were never run, so two of them were broken

### 2026-07-31  (10)
- competence by COUNTERFACTUAL, not correlation -- and sufficiency measured on the outcome
- selection gains a COMPETENCE term, so useful-but-rare survives; pilot runs both architectures
- measure the EXPERTS, and put output and retention above the domain scores
- read one corpus CONTIGUOUSLY: more than half of English's domains were our seek points
- english is ONE corpus, and the phase schedule is generated rather than tabulated
- the phase schedule was hard-coded for four processes, and English-first uses two
- english first, then ADD -- and the measurement that makes adding an area meaningful
- balance the fetch: the stream samples domains UNIFORMLY, so corpus size buys repetition not attention
- prep the multi-day run: resume was broken, and the corpus glob ate the fetch manifest
- coherence was a four-sample statistic and I read it as a finding, twice

### 2026-08-02  (3)
- the signature width must NOT move mid-run -- it killed both pilot arms
- pilot-add verified end to end; drop a stale reference to the `web` domain
- the signature encoder was reading 42% of the stream

### 2026-08-03  (10)
- open a path in: discovery was structurally impossible, not merely tuned badly
- breed by RELEVANCE not global fitness, and mutate by enough to matter
- grow by REPLICATING the fittest -- a blank newborn can never earn its way in
- the fabric had no culling at all -- the expert population was grow-only
- print what the run actually is, and stop the signature encoder ending at 62% coverage
- the optimizer moments were a one-line bug, not the inherent limit I called it
- the gate never read a checkpoint back, and one of its arms tested nothing
- breadth cap, empty-domain culling -- and prompt.py had been dead since the refactor
- experts as tensors: 64 was three ceilings, and the two populations were 15,625x apart
- the expert population was capped at 64 by three accidents and a wrong routing shape

### 2026-08-04  (13)
- the router trains ON the experts' current weights -- make that channel honest
- chaining is the default, and everything the old default was silently gating
- HALT on the society path: the router decides WHETHER the population answers
- HALT now actually halts, and chaining was recording no utilization at all
- the router was never broken -- I was reading a 32-window probe as if it were the run
- the router can now SPECIFY an expert that does not exist, and it gets built
- expert identity is now DERIVED from the expert's full weights, not a free parameter beside it
- restore per-source routing: I optimised away the thing that made the chain a chain
- chaining OOM'd because every hop computed every expert -- and then chained nothing anyway
- the experts have never chained, and the ponder schedule I built the pilot around is inert
- selection by SUSTAINED error, a parent quota, and the pilot drops to GRU only
- put the routing diagnosis IN the report, and stop shipping unvalidated router fixes
- route PER WINDOW, not per batch -- which is why discovery, crossover and exploration changed nothing

### 2026-08-05  (25)
- minted-token handling: the weights were already inherited, the optimizer state was not
- freezing the vocabulary removes the divergence entirely -- the model never stops improving
- "best at step 6k" is largely the yardstick moving, not the model stopping
- generation sampled the LAST model, never the best -- and the loss pattern is the retokenizer
- "experts serving none: 4053" was an instrumentation bug, and it disabled the breadth cap
- seed spread is bigger than every architecture difference this project has claimed
- the LR schedule works, and "plateaued" is not "diverging"
- there was no learning-rate schedule -- 2e-3 constant for 48,000 steps
- the chained society is the default, and the model's own weights are degrading
- DIV_W was a silent no-op on CHAIN_ROUTE=soc -- a whole pilot measured nothing
- the config registry now polices itself -- it had already drifted once
- CHAIN_ROUTE=soc -- the society, actually looped
- the DIRTY flag counted untracked files, so a clean pull reported DIRTY
- banner lies are now structurally impossible, and every log names its commit
- FAB_MIN_STEPS: one source of truth, because three places were reporting the wrong one
- CHAIN_VOTE: society's blend rule with chaining's depth -- and HALT fires
- the 18-arm grid: chaining loses to no fabric at all
- grid to 18 arms, and DIV_W turns out to have been un-runnable on both paths
- longrun.sh grid: unattended arm grid, and runs/ is now append-only
- the growth ramp never latched off: the population was replaced 1.5x over
- ROUTE_REGION_W: run the router on PREDICTED WEIGHTS ALONE
- the weight-prediction router is 1% of the routing decision -- measured, in the run
- three attempts at chain credit assignment, all measured, all defaulting OFF
- the chaining path had a different, weaker router -- and the banner said otherwise
- the training-curve line read its own sign backwards, and the banner lied twice

### 2026-08-06  (9)
- is a run even a function of (config, commit, seed)? nothing ever checked
- TOK_COMPOSE back to default off -- it is the only change that moved the LEVEL
- the run is 40% shorter than the number every projection used
- grid: the 2x2 that separates TOK_COMPOSE from TOK_MINT_NOVEL, plus a cap-saturation arm
- yes, in every past run -- and minting picks the most damaging pair by construction
- "is it still learning" is now answered in every report, not computed by hand
- minted tokens DO get parameters -- they start at their composite and grow into themselves
- TOK_COMPOSE: a token's vector computed from its bytes, so minting allocates nothing
- minted-token init is asymmetric, and averaging both sides loses most of the benefit

### 2026-08-07  (7)
- two repeated expressions become named helpers
- one declared place for all 274 knobs, and five defaults that disagreed with themselves
- Revert "composite levers: say what you mean, without changing what anything does"
- composite levers: say what you mean, without changing what anything does
- GEN_N: every text judgement in this project rested on one 200-token sample
- seeds and repeat never pulled the pilot corpus
- three fixes: an eval pass no longer trains the router, and the LR horizon is live

### 2026-08-10  (12)
- equiv.sh: a noise baseline, because the GPU is nondeterministic in exactly one subsystem
- equiv.sh: the completion marker matched line 8 of every log
- revert the main() split: the seam was 136 values wide, not 39
- fix the split: _report could not see the six nested functions main() defines
- equiv.sh: same commit twice is a determinism self-test, not an error
- comments state mechanism, not results -- including one I got wrong
- make the three hidden couplings print themselves, without changing any value
- fix the import 7de4daf broke -- and equiv.sh is what caught it
- split main(): the 1,297-line measurement battery moves to _report(R)
- correct six comments that no longer hold, and one that overstated what was measured
- equiv.sh: prove a code change is inert, instead of improvising a command line each time
- the pilot bundle: one resumable block, with the two confounded knobs separated

### 2026-08-11  (23)
- the mint gate starved the vocabulary in the first real pilot; fail open
- smoke duplicated the arm definitions, and they had already drifted
- longrun.sh smoke: does every pilot arm still reach its report?
- three findings from the pilot-matrix audit
- probationary minting: mint provisionally, judge on evidence, un-merge on failure
- runs.csv: results in a table that can be re-checked, not in comments that cannot
- the never-fired audit covers TOK_ANCHOR; restarts replicate at 8 epochs; gate on
- a name collision in my gate report silently deleted the retention section
- LR_RESTARTS: the cosine repeats instead of holding at the floor
- the registry guard caught the LR_EPOCHS default I only half-changed
- the mint gate: p(b|a), not an entropy threshold, and it filters rather than aborts
- a meaning gate on minting, appearances by default, and a fixed LR wavelength
- two bugs an adversarial audit of the anchor path turned up
- TOK_ANCHOR_USES: release a new token on APPEARANCES, not on the clock
- vocab.py --tree: read token quality out of the merge tree, without a corpus
- vocab.py: read the mint log the runs were already writing
- two verdict lines that contradicted the numbers printed beside them
- vmax8k@18ep falsifies the dead-row hypothesis; record the 2x2
- levers: declare every knob that another knob decides, and refuse the one override
- LR_EPOCHS: separate the schedule horizon from the run length
- EPOCHS is the lever, not GROW_BURST; predict the shortfall before the run
- [vocab] print the softmax width against the vocabulary that exists
- frozen1k / frozen2k: separate "fixed vocabulary" from "tiny vocabulary"

### 2026-08-12  (4)
- base_nr: does re-segmenting mid-epoch earn its side effects on a GROWING vocabulary?
- a retok on an unchanged vocabulary is pure damage: 2.189 b/B of it
- pin SEED_VOCAB too: VMAX alone assumed a default the harness overrides
- six arms were configured to guarantee dead rows; the predictor skipped them

### 2026-08-13  (7)
- the instrument was wired into the circuit: diagnostics were editing the run
- vmax4k @18ep, four runs, spread 1.227 b/B: the arm cannot be measured once
- per-module seeds, the restart marked self-inflicted, and a crash I had armed
- VMAX was silently re-rolling every weight in the system
- the signature-coverage projection was pinned at the VMAX=2048 value
- record the 18-epoch field: vmax4k wins twice, restarts look net-negative
- _due is not a predicate: my retok guard killed re-segmentation entirely

### 2026-08-14  (14)
- capacity that is earned: rescue-before-cull, and soft caps that lift on plateau
- mask never-minted ids out of the distribution (LOSS_MASK_DEAD, off by default)
- record the first continual-learning run
- pilot-add never created $OUT, so tee had nowhere to write the report
- fetch_big.py could not open a gated dataset, and would not have read the-stack
- seeds checkpoints on by default; the warmup probe stops moving the run
- everything is kept; nothing is used unless you ask -- and asking was unsafe
- "already complete, skipping" was not asking whether the run matched the config
- runs.py could not ingest any post-fix log
- list smoke and repeat in the usage line
- say why the domain-prior check did not run, instead of producing nothing
- the memory store was queried in a language it was not written in
- the unweighted bytes/token bias flips sign with vocabulary size
- the epoch roll carried a stale batch, and two figures that flattered large VMAX

### 2026-08-15  (17)
- fabric: raise FAB_LR_AMIN to 0.15
- fabric: per-expert Smith triangular2 on a USE clock; use-based grace; balance floor
- notes: external research brief -- measured egress status, what search closed, what needs full text
- memory: give eviction a real signal -- retrieval during training, LRU on use
- memory: honor the documented MEM_PER_EXPERT=0 default; gate LR boost on grace
- mask_dead missed retired ids, which are not a suffix
- notes/: research references and the documentation plan (agent drafts, unreviewed)
- stop a sweep without killing it, and give failing experts room to move
- a missing birthday made an expert immortal; now it makes it cullable
- a decaying envelope, per-expert rates, and the founders had no birthday
- the warmup ramp is not a cosine restart
- the transformer has run twice, and neither run means anything yet
- FAB_BURST=1 and a 4% newborn cap, against an 8% cull
- cap the newborn FRACTION, not just the growth rate
- the config audit could only catch knob families it had been told about
- the soft cap has to bind both growth doors, not one
- the 2x2: size was never the problem, ramping to size is

## 2026-08-15 .. 2026-08-28  (112 commits, from git)


### 2026-08-15
- notes: 07_WIP -- unfinished, never-run, and broken, separated because they need different actions
- fabric: correct the growth-vs-cull comment, whose argument my own change inverted
- notes: 06_CONTINUAL_LEARNING -- the target, and the one run that bears on it
- notes: 09_COMMENT_AUDIT, and finish the block 3c2a59e only half-fixed
- notes: extract the full 26-day transcript as evidence

### 2026-08-16
- notes: 10_HISTORY_FINDINGS -- recovered from the agent transcript after a rollback
- notes: recover all 12 transcript extractions from surviving agent transcripts
- notes: 02_IDEAS -- the researcher's ideas and what happened to each
- notes: 00_INDEX -- the map, written last
- memory: a per-source floor, because no eviction clock can save a silent domain
- DID IT FIRE: name every armed mechanism that did nothing
- compare.py: does the difference between two arms mean anything?
- retention: separate forgetting from eviction, and stop routing eval on a zero gist
- selftest: the three instruments get their own tests
- selftest: ignore $DEVICE, so running the tests can never take the GPU
- compare.py: refuse a verdict below three pairs, and parse flags on either side
- FAB_LR_CYCLE back to 24, and `longrun.sh pair` so lever work is paired by default
- _cfgsig sees every knob, and `longrun.sh ladder` for sweeping one
- ladder: LADDER_BASE reuses a baseline rung already run
- compare.py: the verdict could invert its own sign

### 2026-08-17
- memory: the floor was spending most of its reservation on dead domains
- memory: a probationary region, and pressure as a signal rather than a wall
- compare.py: an effect below the replication floor is not worth resolving; _cfgsig fingerprints the corpus
- fabric: FAB_EC_W, expert-choice's property at a scale where expert-choice does not fit
- DIV_W: distinctness counts only where the router leans on both experts
- Add LICENSE file with usage restrictions
- Fix formatting of the LICENSE header
- Update README with rights reserved and contact info
- Clean up README.md formatting and add summary
- Add div element for height styling in README
- Update div height in README.md
- Update README with new usage instructions and spacing
- Enhance README with detailed project description
- Fix spacing in usage warning in README
- Fix contact email formatting in README
- seeds summary: never print specialization without its null
- defaults: DIV_W 0.0 -> 0.02, FAB_LR_OWN 1 -> 0
- notes: research brief on why the experts do not differentiate
- notes: correct the brief -- the encoder is measured healthy, the partition is not
- defaults: FAB_GROW 1 -> 0, FAB_N0 3 -> 2048; stop the banner lying about DIV_W
- growth back ON: the RAMP was broken, not growth

### 2026-08-18
- fix the defect: a REGRESSION could not reach growth
- longrun.sh: arms for identity collapse, HALT, min tokenizer, domains off
- longrun.sh: `grid round3` -- one command for all three questions
- round3: add nodom_mem -- domains off with the EXPERT partition in their place
- report: two verdict lines were giving advice measurement contradicts

### 2026-08-19
- compare.py: --metric d_order1 named the wrong winner, every time
- GROW_CAP: a linear valve, clocked from when the cap is actually hit
- notes: A91 said NEVER IMPLEMENTED about a mechanism that was built
- longrun.sh: round4 -- seven arms for mechanisms that never produced a number

### 2026-08-20
- the LR horizon still assumed the shrinkage away

### 2026-08-21
- the `curve` column was a units artifact, and the log said so all along
- fabric.rescue fired zero times because I disabled the branch it lives in
- round5: let the runs pick which gate reopens the utilization cull
- CULL GATE is an unconditional line now; my banner note was itself inert
- FAB_PRESSURE 0.75 -> 0.45, chosen by round5 rather than by argument
- round6: measure the capacity valve, and keep every local low
- BEST_KEEP killed a completed run with a name collision
- the expert valve was never eligible, and the pin clock could not survive culling
- record round7: the expert valve fires, and the valve is not what cost quality
- GROW_LIFT is a FRACTION of the cap, because 256 meant four different things

### 2026-08-22
- round8: the valve beat both references, and it was not the valve that did it
- round9 refutes the "fewer experts is better" correlation, and fixes the bug I chose not to fix
- the fabric does not add to a healthy base, it makes the base depend on it
- switching the capacity valve on switched the population ramp off
- the pin clock ticked once per flush against a threshold written in steps
- a second clock in the same units fault, standing behind the first

### 2026-08-23
- the valve called a rising loss a stall, and fired on jumps it caused itself

### 2026-08-24
- round12: the vocabulary question is settled, and my saturation claim was wrong
- LR_EPOCHS=0 was my recommendation and it is what broke the run
- LR_STEPS: the cosine wavelength stated in steps, not in epochs

### 2026-08-26
- round15: neither schedule change helped, and my own alarm fired on all four
- round16: the 0.75 GB launch arm, and the corpus hazard that would have made it meaningless
- the alarm could only fire once, and all four runs spent it on a false positive
- the 0.75 GB run was destroyed by three LR restarts I configured into it
- the LR schedule could not see what it was doing to the model
- audit: the LR schedule had no row in the report that exists to catch exactly this

### 2026-08-27
- resolve the audit: the drift is now uncatchable, not just corrected
- sideline the frozen trees: four directories and a ledger that called itself binding
- harness_test: 1,500 lines of launcher, and nothing had ever tested a line of it
- three live defects the untested-code audit found, two of them reproduced
- the memory source census was never rebuilt on resume, and round18 makes each repair visible in a log
- two memory claims verified: one a real latent gap, one narrower than reported
- compare.py could not pair a single log this project has ever produced
- ENC_WARMUP_MIN would have SystemExit'd every run since d267864, and levers.py could not see it
- round18 answered two of its four questions; the other two were never asked
- "corpus too small" was hiding three faults, one of them in the number the CL claim rests on
- a resume could not change the fabric's size, and the crash was the lucky outcome
- FAB_NMAX=4096 was my recommendation and it would have shut three mechanisms for the whole run
- the ramp re-armed against the widened cap, and 95% of the growth would have been the cap talking
- the continual-learning number exists, and four things were distorting it
- the outstanding list, cleared: a soft cap that froze growth, a filter that hid a third of memory
- ACCUM could take zero optimizer steps for an entire epoch, and SPECIALIZATION read a dead projection
- torch installs here after all, so the session's edits were run inside the system -- and one claim was wrong
- the confirmation runs found one more defect, and the two CL arms disagree by 10x
- the last two unverified paths ran, and "holds 0 MB" was a lie about a directory holding 40 kB
- the coverage audit said NO, and it was right: `add` could not resume at all
- the two suites this session wrote were not in the project's own test entry point
- CPU testing structurally cannot see the AMP path, and AMP=fp16 trains without a GradScaler
- a report line I added printed "609% precision", because I hardcoded another run's number into it
- DATA_MODE=synthetic has crashed since 2026-08-15, and preflight is the only thing that runs it

### 2026-08-28
- fixing VALC exposed two more on the same never-run path, one of them a guard that missed its own crash
- a write named the same slot twice, so a count of memory entries went negative
- four report lines that measured the wrong thing, one of them a guard nothing could satisfy
- pilot-add printed "would enter -42 identity experts", and pointed at half the corpus
- "does the memory earn its keep?" was scored on the text the store was written from
- a new area got new EXPERTS and, again, no new TOKENS -- one level below the last fix
- the domain manager was performing the forgetting, and deleting the memory to match
- the file that can download was printing the path that does not exist
- the held-out tail was a block of the last repos, and two report lines argued with themselves
- a resume wrote its vocabulary over the file it read the parent's from
- survey of the whole repo, docs, archive and chat history, as the evidence base for the rework
