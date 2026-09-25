# Proposal 03b — Nothing frozen: the live codec and the measured rate

**Status: design, reviewed and checked, not built.** This document is binding over
[Proposal 03](03_AUDIO_VIDEO.md). Its §0b replaces 03's §0 wherever the two disagree. §6 is
replaced whole. §7, §10, §11, §12, §13 and §16 take the deltas below, and everything else in 03
stands. The section numbers below are 03's.

**Why it exists.** The owner, on 03, 2026-09-25: *"I don't like the idea of frozen codecs, I don't
want anything frozen or fixed unless absolutely necessary. I am also reconsidering the hz."*

**How to read it.**
- It is a build specification, not an essay.
- The plain-language summary is the first bullet list of §0b.
- The default stack, each item with its reason and alternative, is §0b.1.
- The evidence table is §0b.2.
- What stays fixed, and why each item is necessary, is §0b.3.
- Every default, on and off, is §0b.5.
- The build order is §13. It starts with S0b, the mid-epoch act, which also makes text
  retokenization live.

**How it was produced and checked.**
- A tree map and a literature review came first.
- Three designs were then prototyped on CPU against a frozen-codec 25 Hz baseline.
- A judge synthesised them.
- An adversarial critic reviewed the synthesis: sound with fixes, 1 blocking and 9 major issues.
- An independent reproduction reran 11 headline claims at new seeds: 8 reproduced and 3 reproduced
  weaker.
- The revision folded in the critic's fixes under recorded decisions D-1 to D-10.
- Checkers for critic coverage, numbers and tree fit then ran in rounds, each followed by fixes.
  - Serious findings went 19, then 14, then 7, then 4, then 4.
  - The final tree-fit round was clean.
  - The last 4 findings were fixed by hand. A targeted check then found partial gaps, and those
    were fixed and re-verified against the records.
- The minor findings not applied are in the checklist's "not applied" lists and in
  `verify_checks.json`.

Evidence lives under `results/live_codec_design_2026-09-25/`:
- `workflow_result.json`: the whole design workflow.
- `prototypes/{map,d1,d2,d3,judge,critic,repro}/`: code, logs and records.
- `prototypes/rev/`:
  - `checklist.md`: every critic issue and checker finding, mapped to its answer;
  - `revise_checks.json` and `verify_checks.json`: the check rounds;
  - the probe-timing and D1-audit scripts, with their outputs.

Every number is a CPU prototype reading at toy scale on 1 s clips: a signal, not a result. The GPU
experiments in §13 decide the defaults.

---

## 0b. Nothing frozen: the live-codec revision — binding over everything below, §0 included

> Owner, 2026-09-25: "I don't like the idea of frozen codecs, I don't want anything frozen or fixed unless absolutely necessary. I am also reconsidering the hz. Otherwise things look pretty good."

**In plain words, what changed and why.**
- The codec no longer freezes at window 3000. It trains all run on its own reconstruction loss, slowly (a learning-rate floor that never reaches zero), rehearsing the audio it has already heard.
- The LM reads codes cut by a snapshot of that codec, refreshed at every act (at least every 2000 windows, or 4000 while the ceiling guard withholds a refresh); between acts the snapshot is held, so every window sees one codec, while the codec keeps learning underneath.
- That is the only live regime measured against a frozen codec at 4 paired LM seeds. On LM bits per audio-second (a codec-dependent unit) it was lower in 24 of 24 paired readings. The codec-invariant readings split in two:
  - on the **LM side** there was **no consistent cost, and no gain**: caption bits/byte worse in 11 of 16 paired readings (−8.7% to +7.9%), understanding worse in 5 of 8, generation exact worse in 12 of 32 (18 better, 2 tied); grounding was not recorded;
  - on the **codec's own ceiling** there was **a consistent cost**: recover exact below the frozen codec's reading at 4 of 4 live seeds on area A and 3 of 4 plus a tie on B. The frozen codec and the probe set never move, so these are four perturbations of one codec init against one reading per area, and D3, which retrains its codec per seed, shows exact match mixed. That is what the ceiling guard exists for.

  All of it is 4 LM seeds, ONE codec initialisation, 25 Hz, one LM step per 8 windows, and a codec pre-trained for 4000 steps. The shipped default differs from that regime, so an S3 replica must confirm the LM-side label against a frozen control of its own (0b.1 item 6).
- The Hz is no longer set by hand. Before any audio reaches the LM, the run measures 50, 25 and 12.5 Hz codecs on exact attribute recovery and keeps the coarsest rate within a tolerance of the finest.
- That rule was not prototyped. At toy scale a fixed stride (25 Hz in D3 and D2, 50 Hz in D1's pair) beat or tied every per-segment adaptive rate on LM bits/s (D3, D1: 3 seeds) and, for D2's router, on mel (2 seeds). Bits/s is alphabet-dependent across rate arms (item 19), and on the codec-invariant readings the same pairs tie within noise. So a GPU sweep with longer clips decides whether the rate should also adapt per segment.
- The codec architecture stays the proposal's spectral codec. The multi-rate "nested" codec is an arm: its melody timbre recovery was lower at 3 of 3 seeds (at 64 clips, one of the three beyond noise), and S3 decides at 400.
- A live codec improves mel distance and lowers TIMBRE recovery. At D3's high plasticity, which was not step-matched: tones 4 of 4 seeds, melody 3 of 4 plus a tie. At D3's low plasticity: tones lower at 2 of 2, by less. D1 records exact match only. Exact match falls in D1 (one codec init) and is mixed in D3. Recovery is therefore the codec's acceptance metric; a guard, calibrated at S3 above the measured live-vs-frozen spread, holds the snapshot when recovery drops further; the faster "re-warm" stays off until shown harmless.
- What stays fixed, each with its reason (0b.3): the 50 frames/s analysis grid (the audio byte), the FSQ lattice (the id address space), tensor sizes, and the hold of one segmentation between acts that makes a resume exact.
- The largest frozen learned thing in the tree is the TEXT tokenizer's segmentation: at one epoch its re-tokenizations wait for a roll that never comes. Stage S0b builds the mid-run act for text first; audio reuses the same act.
- The LM's audio rows are built from the codec's lattice coordinates (−9.9% to −16.7% bits/s in D1, one codec init, smaller at the new seeds; −11.3% to −15.3% in D3; 4 of 4 seeds in each, a sample-efficiency effect); they raise interference between audio areas, so earlier audio is rehearsed in the LM stream.
- Cost: about +20% wall on CPU at the default cadence for the codec step, the re-encode and the acts (one uncontended run, measured, D1's tiny LM). Probing for exact recovery is extra and not cheap on CPU: at the default act spacing (the union of the 2000- and 3000-window cadences), about +71% of D1's LM time per arrived area, or about +2.2-2.9% on R12's basis (§12, from a preserved timing). The GPU cost is owed to the bench before any default is fixed.

**Scope.** In the owner's instruction, "frozen" means:
- a learned thing that stops learning;
- a representation rate or size fixed by hand.

What stays is software and measurement contracts, which the owner did not object to: frozen Configs, frozen §7 entry-point signatures, frozen record dataclasses, once-resolved wires, EVAL `frozen_rng`, the fixed held-out and probe sets.

**Precedence.** Where 0b disagrees with §0 or any later section, 0b wins. §6 is replaced whole. §7, §10, §11, §12, §13 and §16 take the deltas that follow 0b. Everything 0b does not touch stands as written.

**Evidence.**
- Three prototyped designs:
  - D1: a living discrete codec behind an act-refreshed snapshot, online acoustic BPE, and the Q-RUN-8 option (a) act;
  - D2: a live continuous codec with a learned router;
  - D3: a two-timescale EMA teacher, lattice-coordinate rows and a nested multi-rate codec.
- A judge synthesis, an adversarial critic (verdict *sound with fixes*: 1 blocking, 9 major, 8 minor, 14 missing items), and an independent reproduction. The reproduction tested 11 claims: 8 reproduced, 3 reproduced-weaker. Its seeds:
  - new seeds 2 and 3 for claims 1, 2, 3, 6, 7 and 11;
  - seed 2 only for claims 4, 5, 8 (the act rerun) and 9 (the D1 'bpe' pair);
  - seeds 1 and 2 for claim 9's D3 arms (`ttcN25`, `ttcMRc`; `ttcMR` at s2), and seed 1 only for claim 9's D2 fixed arm;
  - the same seed only for claim 10 (D2) and for the resume test (claim 8, seed 0).
  The codec-side allocator sweep was re-aggregated, not rerun.
- Conditions: CPU, one thread, toy scale, synthetic aud/tones then aud/melody, GRU width 128.
- Evidence paths below are relative to `results/live_codec_design_2026-09-25/prototypes/` (`map`, `d1`, `d2`, `d3`, `judge`, `critic`, `repro`, and `rev`). `rev/` holds this revision's own measurements, each with its command in the file: `rev/probe_time.{py,txt}` (the probe timing, §12) and `rev/audit_d1.{py,txt}` (the recount of D1's codec-invariant readings, 0b.2 rows 1-2).
- Every number is a signal, not a result.

**Words used below.**
- *Recover exact* means the analytic inverse applied to a reconstruction or generation: `DATA.recover` in the tree, `probe` in the prototypes. It is per attribute (tones: kind, band, timbre, count; melody: contour, register, timbre) and exact-match.
- An *act* is the post-flush, empty-batch re-segmentation event of S0b.
- A *seed* in D1 is an LM/stream seed. All D1 seeds share one codec checkpoint (the `.pt` was not preserved; `d1/ck/codec25.pt.json` records its 4000 steps), so D1 codec readings are **one codec init × N LM/stream seeds**. D3 retrains its codec per seed.
- *Codec-invariant readings* are those whose unit does not move with the codec: recover exact, caption bits/byte, understanding and generation exact, grounding bits, mel. Bits per audio-second is **codec-dependent**: two codecs give two alphabets, so a bits/s difference between a live and a frozen codec is not a like-for-like LM comparison (item 19). The same argument is used against 'nested' in item 4. The codec-invariant readings come in two kinds, reported separately below: the **LM-side** readings (caption bits/byte, understanding and generation exact, and grounding bits, which D1 does not record) and the **codec's own ceiling** (recover exact and mel on reconstructions).

### 0b.1 Decisions — the default stack

Each item gives the default, the reason, and the alternatives, which are recorded here and not deleted.

**1 — THE CODEC NEVER STOPS TRAINING.** `AUD_FREEZE_AT` 0 (never).
- *Reason.* The owner's instruction. Measured at the regime of item 6 (0b.2 rows 1-2), live against frozen:
  - lower LM bits/s, a codec-dependent unit, in 24/24 paired readings: 6 table-row readings (original) + 6 lattice-row readings (judge) + 12 new-seed readings (reproduction, claim 3: "12/12 new-seed readings");
  - on the LM-side codec-invariant readings, no consistent cost and no gain: caption bits/byte worse in 11 of 16 paired readings (−8.7% to +7.9%); B understanding worse in 5 of 8; generation exact worse in 12 of 32, better in 18, tied in 2 (`rev/audit_d1.txt`); grounding unrecorded in D1;
  - on the codec's own ceiling, a consistent cost: 4 of 4 live seeds below the frozen codec's A reading, and 3 of 4 plus a tie on B (A 0.229 / 0.292 / 0.271 / 0.271 vs 0.347; B 0.188 / 0.25 / 0.271 / 0.26 vs 0.271). Each frozen value is a single reading per area from one codec init (the frozen codec and the probe set never move), so these are four perturbations of one codec; the A gaps of 0.055-0.118 are each about 1-2 unpaired SE at n = 144. The per-seed-codec harness (D3) shows exact match mixed (row 15);
  - all of it with one codec init, at 25 Hz, from a codec pre-trained for 4000 steps (item 6 lists how the shipped default differs).
  So the case for "live" is the owner's instruction plus the absence of a measured LM-side cost. It is not a measured LM gain, and it comes with a measured codec-ceiling cost that item 8's guard watches.
- *Alternatives.*
  - `AUD_FREEZE_AT > 0` stays as the frozen-codec **control arm**, because goal-B readings need its baseline.
  - "Train to readiness, then freeze" is rejected. It is the old design with a better Gate.

**2 — READINESS, NOT A FREEZE.** The freeze Gate becomes `AUD.ready`, which fires once, **never before `AUD_READY_MIN` windows after the codec's birth** (the window at which the codec group's cosine reaches its floor), when all three hold:
- `codes_used ≥ AUD_COLLAPSE_MIN`;
- `rms_ratio ≥ AUD_QUIET_MIN`;
- per-attribute recover exact on reconstructions of `AUD_PROBE_N` (400) fixed held-out clips of the readiness areas meets the **family floor**.

Under `'measured'` there are three candidate codecs. The Gate then reads: every candidate meets the collapse and quiet conditions (a candidate that fails either is excluded from the rate choice and reported), and the finest candidate (stride 1) meets the family floor or the plateau rule. The coarser candidates are judged by the rate rule (item 3), not by the floor.

The family floor:
- It is calibrated per family at S3 on recover exact: the S3-measured per-attribute plateau at 2 codec seeds minus `AUD_READY_MARGIN` 0.05, stored with the family (the R9 per-family clip-length pattern).
- Until a family is calibrated, the Gate fires on a **plateau**: no attribute rose by more than `AUD_READY_PLATEAU` 0.02, or by more than 2 paired SE of that rise where that is larger (0.02 is under 1 paired SE at n = 400, §6.3, so noise alone would otherwise keep a flat codec from plateauing), over `AUD_READY_PATIENCE` 3 readings, read every `AUD_PROBE_EVERY` 500 windows during readiness (Cadences seeds a key lazily at window 1, so readings land at 501, 1001, …: 5 by window 3000, the 6th at 3001). §12 gives the probe cost, from a preserved timing (`rev/probe_time.{py,txt}`), that sets 500 rather than 200.

Readiness data and timing:
- Readiness trains on `AUD_READY_AREAS`. The default is the first media area in `DATA_PHASE_SCHED`; the root resolves '' against DATA's phase plan and passes the areas to `DATA.media_batch` (AUD may not read DATA's levers, O10). Later areas are unseen by the codec until their phase starts. This differs from D1's measured codec, whose 4000 pre-training steps drew half their crops from a generic 5-kind mix that included a melody kind (item 6).
- The Gate stops nothing.
- `AUD_READY_MIN` 3000 U.Windows, counted from the codec's birth, sets the Gate's first test: the first probe reading at or after it (window 3001 on a fresh run). The startup refusal refuses a media LM phase that starts before the flush after that test, so the Gate and its relay act precede all media. The birth window is checkpointed (`aud.born_at`): 0 on a fresh run, and the resume window on an add-a-modality resume (proposal §11 R-CKPT), where the codec is born mid-run. Counting from window 0 would let a resume past 3000 force the Gate on a nearly untrained codec. Known answer (S3): an add-a-modality resume at window 5000 (first Gate test at 8001) refuses a media phase at 6000 and at 8001 and admits one at 8002 at `OPT_BATCH_WINDOWS` 1. The readiness cadence (`AUD_READY_EVERY` 4) and the cosine run to `AUD_READY_MIN` whatever the readings, so the cadence never drops to the live 1/32 while the cosine is mid-way. Readiness therefore gives each candidate 3000 / 4 = 750 codec steps by window 3001 at any `OPT_BATCH_WINDOWS`, because the codec step's row is evaluated per window (§6.2 step 1).
- After the Gate and until the first media window (the owner's schedule may put media later than 3000), the codec keeps training at the live cadence on `DATA.media_batch` crops of the readiness areas, so there is no gap in which it trains on nothing.
- If the Gate has not fired when a media phase starts, it is forced with the readings in hand. `aud.ready.late` fires (PRESENT-and-0 while armed), and the warning names the failing attribute.

*Reason.*
- The first draft's 0.30 is S3's "probe ceiling ≥ 30%", set on a different probe. On recover exact, D3's codecs and D1's melody reading fall below it, and D1's tones reading passes:
  - D3 frozen after 1500 steps: tones 0.259/0.204, melody 0.203/0.141;
  - D1 after 4000 steps: tones 0.347, melody 0.271.
- Training readiness only on the first area keeps the later areas' codec-BWT row and arrival readings meaningful.

*Alternatives.*
- Rejected: an absolute 0.30; a mel threshold (mel is secondary, and it improves while timbre recovery falls, item 8); readiness on every scheduled area (then no area would be new to the codec); a Gate that may fire before `AUD_READY_MIN` (it would cut the readiness cadence mid-cosine, a regime nobody measured).
- An arm, `AUD_READY_AREAS='+generic'` with `AUD_READY_EVERY` 1: D1's pre-training recipe (the first area plus a declared generic synthetic set, about 3000 codec steps by window 3000). The S3 replica (item 6) switches the default to it if the first-area recipe loses to D1 live25.

**3 — THE RATE IS MEASURED PER RUN AT READINESS.** `AUD_RATE_MODE='measured'`.

The rule:
- At the readiness Gate, before any media is consumed by the LM, the run chooses its stride from `AUD_STRIDES` {1,2,4} on the 50 frames/s grid (50 / 25 / 12.5 Hz).
- The choice comes from MEASURED rate-distortion on the readiness areas: the coarsest stride whose per-attribute recover exact on reconstructions stays within `AUD_RATE_TOL` (0.05, absolute) of the finest stride's, on every attribute and on exact match.

How it runs under each architecture:
- Under `AUD_ARCH='spec'` there is one spec codec per candidate stride, trained during readiness only. The cost is about 3× the codec cost, and 3× the probe cost, until readiness, and zero after (§12 gives both bases). The chosen codec continues live; the others are dropped, and their readings are reported (`aud.rate.cand.<s>.*`).
- Under `'nested'`, one codec serves all strides.

Layout:
- **Positions per clip are exact at every candidate stride.** A family's clip length must be a whole number of 20 ms frames (R9's per-family length). `AUD.startup_refusals` refuses any other, from the per-family clip lengths and `DATA_AUD_SR` that the root passes beside `phase_plan` (AUD may not read DATA's levers, O10). A clip of f frames at stride s takes F = ceil(f / s) positions under 'spec'. Under 'nested' and 'alloc', the clip is first padded to whole 80 ms segments, so F = ceil(f / 4) × 4 / s. The pad is silence (zero waveform) appended at the clip's end, and the decoder's output is trimmed to the clip's samples. This is what D3 did: it padded 320 samples, so a 1 s clip gave 13 positions at stride 4 and 26 at stride 2 (`d3/d3lib.py:189`, `d3/run.py:250`; trim at `d3/d3lib.py:139`). So a 1 s aud/tones clip (50 frames) takes 13 positions at stride 4 under 'spec': 2 pad frames, 4% more positions than 12.5 per second. F stays a function of levers, which is what R1 and R9 need. Known answer (S3's selection test and S4's relay): a 1 s tones clip at stride 4 gives F = 13, decodes to exactly 8000 samples, and its END falls after position 13.
  - *Alternatives*, rejected: (a) excluding from a family's candidates any stride that does not divide its frame count. That would take 12.5 Hz away from the default family, which the rule must be able to choose (the toy exact-match readings alone would have chosen it, row 13). (b) Requiring every family's clip length to be a whole number of 80 ms segments. That would change aud/tones from the 1 s the draft and every prototype used.
- Compose lays the media tail out provisionally at `AUD_RATE_STRIDE` (2).
- If the chosen stride differs, the readiness act re-lays the unconsumed media tail at it. No media has been consumed yet, so no LM work is lost. The re-lay needs `TOK.splice`'s media re-interleave, so it is built and tested at S4; S3 tests the selection only.
- The stride is chosen from the readiness areas only (the first media area by default). Under `'spec'` every later area is laid out at that stride without its own measurement, which 0b.3 lists as not necessary; the arm `AUD_RATE_MODE='measured_arrival'` (below) removes it.

*Reason.*
- The owner is reconsidering the Hz, and this takes the hand-set 25 Hz out while costing no LM work.
- It is honest about the evidence: **'measured' itself was NOT prototyped.** At toy scale, with 1 s clips, a fixed stride (2 in D3 and D2; 1 in D1's 'bpe' pair) beat or tied every per-segment adaptive route **on LM bits/s** (3 seeds for D3 and D1, 2 for D2; 0b.2 row 12). D2's router is the exception: it is judged on mel.
  - D3 'alloc' vs fixed, same nested codec, table rows: +10.0/+13.3% (s0), +14.3/+10.6% (s1), +3.6/+15.2% (s2) bits/s;
  - D3 nested 'alloc' with coordinate rows vs the spec fixed codec with coordinate rows (**unpaired across codec architectures**, V 3264 vs 1264): −2.1/+2.6%, −0.5/+5.4%, −1.6/+5.5%;
  - D1 'bpe' against fixed 50 Hz: worse in 7/9 readings, better in 2 (−0.08, −1.69);
  - the D2 router: worse on mel at 2 seeds.

  Bits/s is alphabet-dependent across rate arms (item 19; S5 reports it and does not use it for rate arms). On the codec-invariant readings the same D3 pairs tie within noise: melody recover exact, 'alloc' vs fixed on one nested codec init per seed, 0.141 / 0.141 / 0.25 vs 0.109 / 0.125 / 0.219 ('alloc' higher at 3 of 3, each by one or two clips of 64); tones exact 0.278 / 0.333 / 0.315 vs 0.343 / 0.315 / 0.361. So the toy evidence does not favour per-segment adaptivity, and it does not show that a fixed stride is better on the primaries either.
- Forced 12.5 Hz cost +11.9/+11.6% tones codec mel (+9.3/+8.7% melody) against forced 25 Hz. This is D3's **nested codec forced to stride 4** in the codec-only drift sweep (n = 36 / 32 probe clips), not a separately trained stride-4 'spec' codec, which is what 'measured' trains by default. **Per-stride 'spec' rate-distortion is unmeasured.**
- Applied to those toy nested-codec readings with exact match alone, this rule would have chosen 12.5 Hz in all four (area, seed) cells (0b.2 row 13). So:
  - the S3 deliverable includes a known-answer test of the selection, with a noise fixture;
  - R_s and R_1 are read on the **same** probe clips, so the rule tests a paired difference. `AUD_PROBE_N` is sized on the SE of that paired difference (§6.3), and the Gate reports the realised SE and the expected false-"out" rate over its cells;
  - the S5 GPU sweep (2-4 s clips, 2 paired seeds: fixed 12.5 / 25 / 50, 'measured', 'alloc' at rho 0.1 and 0.5, 'bpe') decides whether per-segment adaptivity becomes the default.

*Alternatives, all built as arms:*
- `'fixed'`: `AUD_RATE_STRIDE`, default 2. The control arm.
- `'alloc'`: per-segment, rho `AUD_ALLOC_RHO`.
- `'bpe'`: online acoustic BPE over lattice ids.
- `'router'`: H-Net, continuous route only.
- `'measured_arrival'`: 'measured', plus a re-measure at each new media area's arrival, whose unconsumed tail is re-laid at that area's own chosen stride through an act. Built under `'nested'` only (one codec, and stride blocks are already separate ids). Under `'spec'` it would need per-stride id blocks and the losing candidates kept alive at the floor, so it is not built.

**4 — ARCHITECTURE `AUD_ARCH='spec'`; `'nested'` IS AN ARM.**
- *Reason.* The judge made 'nested' the default on seed 0 bits/s and tones mel. It fails its own pre-declared switch criterion ("nested at stride 2 ≥ 'spec' on mel, codes used AND per-attribute ceiling"):
  - melody timbre recover 0.359 (nested) vs 0.500 (spec, live) / 0.641 (spec, frozen) at s0;
  - melody exact 0.109 vs 0.172 / 0.203;
  - the lower nested bits/s goes with lower code entropy (tones 7.628 vs 7.759 bits).
- The reproduction's records give s1 and s2 as well (derived here, 0b.2 row 14): melody timbre is lower under nested at **3/3 seeds** (0.359/0.375/0.531 vs 0.500/0.609/0.578), while nested wins tones mel at 3/3.
- *S3 decides.* The pre-declared criterion at 2 seeds, INCLUDING per-attribute recover exact on every attribute, decides whether 'nested' becomes the default. Each comparison carries a non-inferiority margin of 2 SE of the paired difference (§6.1), because at dozens of strict comparisons noise alone would fail even two equal codecs.
- *Alternatives.* `'nested'` (D3), `'wave'` (SEANet, GPU), and `'dmel'` (training-free binning, S8) are arms.

**5 — CODES ARE CUT BY A SNAPSHOT, REFRESHED AT EVERY ACT.** `AUD_CODES='snapshot'`.
- The tokenizing codec is a snapshot of the live codec. It is refreshed at **every** act, as decided (D-5) and as D1 did (`d1/run_arm.py:696`, where every act was "snapshot refresh + mint + retok"). AUD raises its own refresh Due every `AUD_REFRESH_EVERY` 2000 windows, the cadence D1 measured, so no snapshot is held longer than 2000 windows, or 4000 under a ceiling-guard hold (item 8). A TOK retok act refreshes it too. Both bounds are exact at `OPT_BATCH_WINDOWS` 1. Otherwise each can run up to one flush stride (`OPT_BATCH_WINDOWS` − 1 windows) late, because `Cadences.due` fires at a long-run rate with jitter bounded by the caller's evaluation stride (`train/api.py` `Cadences.due`) and the act runs only after a flush. `AUD_REFRESH_EVERY` 0 is refused at startup under 'snapshot' with AUD enabled (`AUD.startup_refusals`). By the tree's sentinel convention, 0 would disarm AUD's Due, and with `TOK_RETOK_EVERY` 0 (which S0b's ship rule may ship) the tokenizing snapshot would then never refresh: a freeze by configuration.
- The consequence, stated: with `TOK_RETOK_EVERY` 3000 and `AUD_REFRESH_EVERY` 2000 the acts fall at 3000, 4000, 6000, 8000, 9000, … (a fire of AUD's Due before readiness raises no act: there is no snapshot to refresh) and the holds are 1000-2000 windows, not D1's constant 2000. That is less hold than D1 measured, which is the owner's direction, and it is an unmeasured deviation (S5's plasticity matrix covers it; `aud.flip_per_refresh` reports it).
- **Between acts the snapshot is held, the codec itself keeps training, and the act cadence is a lever.**
- A refresh makes the unconsumed tail's codes stale. They are rewritten lazily: at window cut, any clip record whose codes predate the current snapshot is re-encoded in place by it (D1's `jit_refresh`, `d1/run_arm.py:338`). Lengths never change at a fixed per-run stride, so an act raised only by AUD's Due splices no text (item 13).

*Reason.*
- It is the measured D1 regime (item 6).
- It makes item 14's resume exact.
- The routing stack sees one drift event per act instead of continuous drift.

*Alternatives.*
- Refresh only at acts that carry AUD's refresh Due, which would keep D1's constant 2000-window hold exactly. Recorded, not the default: D-5 asks for a refresh at every act, and a refresh at a TOK act rides on a shift stamp and a re-key the act makes anyway, so it adds no drift event of its own while shortening the hold.

*The arm `AUD_CODES='jit_ema'`* (D3):
- Codes are cut at every window by an EMA teacher of the live codec. It is the fully continuous alternative.
- **Its measured value so far is a lower flip rate, not LM bits:**
  - flips per 50 codec steps 0.089–0.152 vs 0.473–0.504 online (D3's nested codec, codec-only, 2 seeds; the direction reproduced on spec25 through flipdist);
  - at s0, no bits/s difference from online codes (a codec-dependent unit, item 19; one seed: tones 111.53 vs 112.35) and LOWER recover exact (tones 0.231 vs 0.315).

**6 — PLASTICITY IS D1's MEASURED LOW-PLASTICITY REGIME** (`d1/run_arm.py` arm `live25`, defaults at lines 686-702). Its exact settings:

| Setting | D1 live25 as measured | Default here |
|---|---|---|
| Codec learning rate | 5e-5 constant after a 4000-step codec phase whose schedule (100-step warm-up, then linear decay) ended at the same floor, 1e-3 × 0.05 (`d1/codec.py:170`) | The codec group (`'codec.<s*>'` at the default, `'codec'` otherwise, §6.2 step 1), on a schedule AUD owns: peak `AUD_CODEC_LR` 1e-3 (the draft's `OPT_CODEC_LR`, renamed), cosine with no warm-up (deviation (a)) to `AUD_CODEC_LR_MIN_FRAC` 0.05 (5e-5) over `derive.codec_steps_from_windows(AUD_READY_MIN, AUD_READY_EVERY)` = 750 codec steps, then the floor for the rest of the run; never zero. The schedule is indexed by the group's own optimiser-step count (units.Steps, Q-OPT-2), not by windows |
| Optimiser | AdamW betas (0.8, 0.99), torch's default weight decay 0.01, codec-phase moments kept into the live phase (`d1/run_arm.py:268`, `d1/codec.py:162`); gradient norm clipped at 1.0 at every codec step (`d1/run_arm.py:412`, `d1/codec.py:168`) | `OPT_CODEC_BETA1` 0.8, `OPT_CODEC_BETA2` 0.99, `OPT_CODEC_WEIGHT_DECAY` 0.01, and `AUD_CODEC_GRAD_CLIP` 1.0 applied by `AUD.loss_terms`: D1's values. The tree's AdamW otherwise takes torch's default betas and `OPT_WEIGHT_DECAY` 0.0 (`opt/api.py:1055`), and `OPT_GRAD_CLIP` is off and clips the base group only (`opt/api.py:1645`), which would have been unstated deviations. The group's moments carry from readiness into the live phase |
| Who steps the codec optimiser | the prototype loop | `AUD.loss_terms(aud, codec, wave, *, opt, anchor=None)` steps the codec group itself, as `SIG.train_step` steps `encoder` (Q-OPT-6), AND clips its gradient and writes its lr from AUD's own schedule before each step. OPT builds the group (betas, weight decay) and never writes its lr. Why AUD, not OPT: every input to the codec schedule is AUD's. Its horizon is `AUD_READY_MIN` / `AUD_READY_EVERY`, its floor and peak are AUD levers, its re-warm is `AUD_REWARM` / `AUD_REWARM_WINDOWS`, and its clock is codec steps. Each package reads only its own Config (`cfg.owned_by(PREFIX)`), so OPT cannot read any of these, and `OPT.maybe_step` runs on the LM's flush cadence, which the codec's clock does not follow. The alternative, an `OPT.build(..., codec_horizon=)` argument plus a `maybe_step(..., codec_events=)` move (the R8 / `open_store(key_dim=)` route), is recorded and not taken. It would cost two frozen-signature moves to carry values OPT does not otherwise need. The ruling is **Q-OPT-11** (next free), a ruling without a move: `maybe_step` writes lr to `base` and `encoder` only, and the stepper of any other group owns that group's schedule. Retiring a group is OPT's: **`OPT.retire_group(opt, st, *, key)`** (+1 entry point, S3). It drops the group's optimiser and moments and records the key as retired for R-OPT's restore rule. The root calls it at the readiness Gate for each losing `'codec.<s>'` candidate, and in the frozen-control arm for the kept group. AUD is new at S3, so `loss_terms` has its first signature here, not a move |
| **Codec steps and data before live** | **4000 standalone steps; half aud/tones crops, half a generic 5-kind mix (tone, chirp, harmonic, syllables, melody; `d1/codec.py:143-156`, `d1/codec_lib.py:88-101`)** | **≥ 750 steps per candidate (`AUD_READY_MIN / AUD_READY_EVERY`), cosine, on the first media area only (item 2). An unmeasured deviation: 5.3× fewer steps and no generic set** |
| Codec cadence | one codec step per 4 LM steps × 8 windows = **one per 32 windows** (308 steps over 9866-9871 windows) | `AUD_TRAIN_EVERY` **32** U.Windows after readiness. `AUD_READY_EVERY` 4 during readiness only, when the LM consumes no media (R12's costed codec-phase cadence). The windows (data per codec step) are held fixed, not the LM steps: at `OPT_BATCH_WINDOWS` 1 that is 32 LM steps per codec step against D1's 4, **a deviation** (f) |
| Batch | 16 crops × 0.5 s | `AUD_BATCH` 16 × `AUD_CROP_S` 0.64 s. 0.64 s is a whole number of 80 ms segments for stride 4, a stated deviation from the measured 0.5 s |
| Codec rehearsal | odd crops from earlier consumed areas (0.5) | `AUD_REHEARSE` 0.5, from clips the stream has consumed, rendered by reference |
| Anchor | w 10, margin 0.25, all crops, target = the tokenizing snapshot's lattice point | `AUD_ANCHOR_W` 10, `AUD_ANCHOR_MARGIN` 0.25, `AUD_ANCHOR_SCOPE` 'all', target = the snapshot's lattice point |
| Snapshot refresh | at every act, every 2000 windows (`act_every`, 250 LM steps); 4 refreshes per run | at every act, and at least every `AUD_REFRESH_EVERY` 2000 U.Windows (item 5); holds of 1000-2000 windows with `TOK_RETOK_EVERY` 3000 (as many LM steps at `OPT_BATCH_WINDOWS` 1). **A deviation** |
| **Frame rate** | **25 Hz only** | **measured per run (item 3): 12.5, 25 or 50 Hz. On the toy readings the rule would have picked 12.5 Hz, where this regime was never measured** |

*Reason.*
- It is the only live regime measured against a frozen codec at 4 paired LM seeds. Its readings (0b.2 rows 1-2):
  - lower bits/s (codec-dependent) in 24/24 paired readings;
  - on the LM-side codec-invariant readings, no consistent cost or gain: caption bits/byte worse in 11 of 16 (−8.7% to +7.9%), B understanding worse in 5 of 8, generation exact worse in 12 of 32 (18 better, 2 tied); no grounding reading;
  - on the codec ceiling, a consistent cost: recover exact lower in 7 of 8 with 1 tie.
- **The label "no consistent LM-side cost" is measured only in this regime: 25 Hz, D1's 4000-step pre-trained codec, one codec init, one LM step per 8 windows.** It compares matched LM steps, NOT matched compute (+20% wall at this cadence, D1 s1 uncontended; about 2× at one step per 4 windows), and NOT matched codec steps: the frozen codec took no further step, the live one took +308 at 5e-5.
- The shipped default differs from D1 live25 in the rows marked in bold (steps and data before live; the frame rate), in the crops, the refresh holds and the LM steps per codec step ((a)-(f) below). A weaker readiness codec (5.3× fewer steps) may drift more once live, so matching D1 live25 would not show that live and frozen are still equivalent. **So S3 runs a CPU replica of the full shipped default stack in the D1 harness at 2 seeds, at the tree's `OPT_BATCH_WINDOWS` 1 and on the shipped optimiser path (not D1's `codec_step`), with a frozen control of its own, before the label applies to the default** (§13 S3):
  - *replica-live*: the shipped stack, `'measured'`;
  - *replica-frozen*: the same recipe and the same chosen stride, with `AUD_FREEZE_AT` at the window the Gate fired;
  - *readiness-only*: D1 live25 as measured (8 windows per LM step, stride 2, 0.5 s crops, a refresh every 2000 windows), with only its codec phase replaced by the shipped readiness recipe (first area, 750 steps, cosine, no warm-up).
  - **The transfer test.** The label transfers only if replica-live is non-inferior to replica-frozen on every LM-side codec-invariant primary the D1 harness records (caption bits/byte, understanding exact, generation exact; grounding is first read at S5; margin 2 paired SE) at both seeds. Its recover-exact drop against replica-frozen is reported against D1's measured drop, and it sets the ceiling guard's calibration (item 8).
  - **The recipe check.** The readiness-only cell, which differs from D1 live25 in readiness alone, is compared with it on those primaries at the same seeds. If it is worse beyond 2 paired SE on any of them, S3 switches readiness to the `'+generic'` arm (item 2: D1's recipe, about 3000 codec steps) and re-runs the replica. If the `'+generic'` cell fails too, both go to the owner, and the default ships the recipe closer to D1 live25 on the primaries.
  - Bits/s is reported and never used in either test: the arms do not share a codec (item 19).
- **The cadence.** `AUD_TRAIN_EVERY` 32 because 1/32 is the only cadence with a paired live-vs-frozen measurement at 4 LM seeds (D-4: the default is the regime measured against frozen). The 1/4 cadence (the critic's rerun, 0b.2 row 3) is 2 seeds, one codec init, not reproduced:
  - against 1/32 it leaned better on the codec-invariant readings: caption bits/byte better at 3 of 4 (B 0.1267 / 0.1246 vs 0.1377 / 0.1376; A after A 0.3359 / 0.3154 vs 0.3475 / 0.3061, where s1 goes the other way), B understanding 0.179 / 0.262 vs 0.095 / 0.167 (2 of 2), recover exact higher at 3 of 4 (A 0.306 / 0.299 vs 0.229 / 0.292; B 0.219 / 0.198 vs 0.188 / 0.25, where s1 goes the other way). Each gap is about the size of the seed-to-seed spread of the same reading;
  - against 1/32 its newest-area bits/s was +1.0% / +4.2%. That is a comparison across two live codecs, so it is not a like-for-like LM reading (item 19);
  - against frozen, its recover exact was lower on both areas at both seeds, and B bits/s was +2.6% at s1.
  **So neither cadence is established as better.** 1/32 ships because it is the measured one, not because of bits/s or CPU cost. Both cadences are S5 (ii) cells, and S5 decides on the codec-invariant primaries under §13's rule. The CPU figures (codec time about 130% of LM time at 1/4, contended, against +16% at 1/32) are cost information in §12, not grounds for the default.

*The anchor is a measured value, not a settled mechanism.*
- `AUD_ANCHOR_W` ships at D1's measured 10, and 0 is a measured arm.
- The earlier claim that the anchor is "measured load-bearing" is **dropped**:
  - the LM-level evidence compares live25 with live25free, which differ in snapshot AND anchor (`d1/run_arm.py:40-41`), so the two cannot be separated;
  - codec-only (D1's **50 Hz codec**, `codec50.pt`, 200 area-A + 300 area-B codec steps, one seed), after area B the anchored codec is lower on area A: recover exact 0.264 vs 0.347 (about 1.5 unpaired SE at n = 144, one seed), mel 0.4994 vs 0.4955 (within noise). The quoted "0.506 → 0.475" was area A before B.
  - so the acceptance-metric evidence so far leans AGAINST anchor 10: recover exact at the end is lower with it in 5 of 6 readings: codec-only area A (0.264 vs 0.347), and the 4 LM-harness readings of row 6, A and B at s0/s1, where it is confounded with the snapshot. The sixth, codec-only area B, goes the other way (0.25 with the anchor vs 0.198 without). After area A only, the LM harness is mixed (A 0.278 vs 0.278 and 0.312 vs 0.292; B 0.26 vs 0.24 and 0.219 vs 0.229, anchored first). Anchor 10 stays the default by D-4 because it is the regime measured against frozen on the LM side; S5's {anchor 0, 10} cells decide.
- The missing arms are added. S5 crosses {anchor 0, 10} with {snapshot, jit_ema}, which covers the snapshot without an anchor, and the EMA with and without a teacher-targeted anchor. S3's codec-only matrix makes A-after-B recover exact an acceptance reading.
- Retargeting the anchor to an EMA teacher's lattice point applies only under `AUD_CODES='jit_ema'` and is **unmeasured**.

*Alternatives.* The S5 plasticity matrix covers:
- the 1/4 cadence;
- D3's high plasticity (3e-4, a step every 2 LM steps): LM bits/s (codec-dependent, item 19) vs frozen with the same rows **−0.1% to +8.1% (7 of 8 worse, 4 seeds, coordinate rows); +3.2% to +8.1% (table rows, 3 seeds); reproduced-weaker** (0b.2 row 4); on the codec-invariant readings, timbre recovery lower at 4 of 4 tones seeds (row 15);
- `'jit_ema'` (item 5).

**7 — RE-WARM SHIPS OFF.** `AUD_REWARM` 0.
- *Reason.* 0.3 × peak = 3e-4 is the "hot" learning rate of D3's ttc25 and of the judge's live25hot, the regime with the largest timbre drop. D1's codec-only re-warm evidence is D1's **50 Hz codec** (`codec50.pt`), 200 area-A + 300 area-B codec steps, one seed:
  - after B, B mel 0.5688 vs 0.5769 (anchor alone);
  - A recover 0.271 vs 0.264 (anchor alone) vs 0.347 (no anchor).
- *The switch.* `AUD_REWARM` turns on (0.3, over `AUD_REWARM_WINDOWS`) only when the S3 codec-only matrix shows that no attribute's recover exact falls under it by more than 2 SE of the paired difference, at either of 2 codec seeds, and only after the harmonic / multi-resolution loss arm (item 8) is built.
- *Length.* `AUD_REWARM_WINDOWS` 9600 = 300 codec steps at the default 1/32 cadence: the span D1's only measured re-warm covered (its 300-step B phase). The judge's 1200 windows was 300 steps at 1/4 and would be 37.5 steps at 1/32; it is a cell, unmeasured.
- *Alternatives.*
  - Re-warm at 0.3 is an arm.
  - Re-warm triggered by a rise in reconstruction loss on fresh clips (the SIG floor-skip pattern) is an arm.

**8 — RECOVER EXACT IS THE CODEC'S ACCEPTANCE METRIC, AND ITS GUARD ACTS BEYOND THE MEASURED SPREAD.** A live codec improves mel and lowers TIMBRE recovery wherever timbre is recorded (D3); exact match falls in D1, which records exact match only, and is mixed in D3 (0b.2 row 15):
- D3 at **high plasticity** (3e-4, a codec step every 2 LM steps, +600 steps over the frozen codec, so **not step-matched**): tones timbre lower at 4 of 4 seeds (0.481 / 0.556 / 0.481 / 0.509 vs 0.648 / 0.602 / 0.565 / 0.648); melody timbre lower at 3 of 4 plus a tie;
- D3 at **low plasticity** (cold: 5e-5, a step every 8), the regime nearer the default: tones timbre lower at 2 of 2, by less (0.593 vs 0.648 at s0, `judge/d3c/res/ttc25c_cold_s0.json`; 0.537 vs 0.565 at s2, `repro/d3/res/ttc25c_cold_s2.json`); melody timbre tied at s0 (0.641) and lower at s2 (0.609 vs 0.625);
- D1 exact match at the end, one codec init: A lower at 4 of 4 (0.229 / 0.292 / 0.271 / 0.271 vs 0.347), B lower at 3 of 4 plus a tie (0.188 / 0.25 / 0.271 / 0.26 vs 0.271);
- D3 exact match is mixed: tones lower at 2 of 4 (higher at s1 and s2), melody lower at 3 of 4;
- codec-only: D3's nested codec lost melody exact (0.312 / 0.125 → 0.094 / 0.094) while melody mel improved (0.623 / 0.634 → 0.521 / 0.531), but its tones exact rose or held (0.222 → 0.278, 0.306 → 0.306); D1's 50 Hz codec with no anchor raised area-A exact (0.292 → 0.347).

The robust part is timbre. That is an objective misalignment (L1 on log-magnitude and magnitude does not weigh harmonic structure), not a codec defect, and it is why recover exact, not mel, is the acceptance metric.

The guard:
- `aud.ceiling_drop` fires when an attribute's recover exact on the probe falls below its baseline by more than the family's **drop threshold**.
- The threshold is calibrated per family at S3: the live-vs-frozen drop measured at the default plasticity at 2 codec seeds, plus 2 SE of the paired difference, stored with the family. It sits above the measured regime on purpose. At a flat 0.05 the guard would have fired in the very regime the default is: D1 s0's area A fell 0.069 by the end of A and 0.118 by the end of the run, s1's 0.055 by the end.
- Until a family is calibrated, `AUD_CEIL_DROP` 0.05 is used for counting only. `aud.ceiling_drop` counts, nothing is held, and `aud.ceiling.hold` is ABSENT with reason "family drop threshold not calibrated (S3)".
- Baselines: for a readiness area, each attribute's value at readiness. For a later area, its value when its readings first plateau after its arrival (the `AUD_READY_PLATEAU` / `AUD_READY_PATIENCE` rule); until then that area's guard is not armed (`aud.ceiling.armed.<area>` PRESENT-and-0).
- Its action on a calibrated family (`AUD_CEIL_ACTION='hold'`):
  - the next snapshot refresh is withheld, so the LM keeps the last snapshot whose ceiling held;
  - the codec keeps training at its floor (`aud.moved` is read on the live codec, item 9);
  - when `AUD_CEIL_HOLD_WINDOWS` 2000 U.Windows (one refresh period) have passed since the first withheld refresh, an act Due is raised, and that act's refresh goes ahead with a warning. The withholding act's RefreshReport carries `hold_expires_at` (U.Windows, kept in AUD's hold state), and the root raises the Due by a one-shot Windows comparison, `clock.step >= hold_expires_at`, as for the freeze; the root's copy crosses a save in `payload['LOOP']`. It does not wait for the next periodic refresh Due. The first withheld refresh comes at most `AUD_REFRESH_EVERY` after the last refresh, so the longest possible hold is `AUD_REFRESH_EVERY + AUD_CEIL_HOLD_WINDOWS` = **4000 windows** (plus the flush-stride slack of item 5). The guard can never become a freeze, and the hidden-freeze audit counts that longest hold (item 9);
  - the decision, the copy and the counters are `AUD.refresh`'s (item 9), against baselines AUD holds in its own state.
- Under `'jit_ema'` there is no refresh to withhold. The guard counts, and `aud.ceiling.hold` is ABSENT with reason "AUD_CODES='jit_ema': no refresh event".
- Counters: `aud.refresh_held` and `aud.ceiling_drop`.
- S3 builds a harmonic / multi-resolution spectral loss arm BEFORE re-warm may default on.
- **'hold' at the calibrated threshold is not a measured regime.** It guards against drops larger than the measured ones. {hold, count} is a cell of S3's codec-only matrix and of S5 (ii).

*Alternatives.* `'count'` (report only) is an arm. A flat 0.05 hold is rejected: it would fire in the measured regime and turn the refresh cadence into an unmeasured run of holds, each up to 4000 windows, back to back. The learned vocoder is S8. A forced refresh that waited for the next periodic refresh Due is rejected: with holds starting at TOK acts it could reach 6000 windows, which the audit could not bound by one sum.

**9 — NO HIDDEN FREEZE.**
- Every codec time constant is declared in U.Windows and converted through named derive functions. Three are new at S3, each with known-answer rows owed in `tests/test_derive.py` (O11, `check_o11_no_unnamed_clock_arithmetic`, forbids these conversions at call sites):
  - `derive.codec_steps_from_windows(span: Windows, every: Windows) -> Steps`: the schedule horizon (known answer: (3000, 4) → 750) and the re-warm length ((9600, 32) → 300);
  - `derive.ema_decay_from_half_life(half_life: Windows, every: Windows) -> float`: the `'jit_ema'` teacher's per-codec-step decay, 0.5^(every / half_life) (known answer: (4416, 32) → 0.99499, a half-life of 138 codec steps);
  - `derive.latent_frames_from_seconds(s: float, fps: float) -> int`: WORLD's horizons, the nearest whole latent frame with halves rounding up and a minimum of 1 (known answers: (0.04, 25) → 1, (0.2, 25) → 5, (0.04, 12.5) → 1, (0.2, 12.5) → 3, (0.04, 50) → 2).
  The declared constants are the `'jit_ema'` teacher's half-life `AUD_EMA_HALF_LIFE`, the re-warm length, the refresh period, and the ceiling guard's hold `AUD_CEIL_HOLD_WINDOWS`.
- The aud.* **periods** join compose's `_periods`, so `RUN.cadence_audit` states them at startup like every other cadence: `aud.ready`, `aud.train`, `aud.probe` and `aud.refresh`, all four unconditionally in `_periods`' returned literal, which is all K9 and K13 read. With `AUD_ENABLED` False every aud.* period accessor returns Windows(0), DISARMED. Under 'snapshot' `AUD_REFRESH_EVERY` 0 is refused (item 5); under `'jit_ema'` `AUD.refresh_period` returns 0, so the audit prints one DISARMED line for it, which is true (no refresh event). The frozen control's freeze is not a period. It is a one-shot Windows comparison, `AUD.freeze_at(aud) > 0 and clock.step >= AUD.freeze_at(aud)`, that fires only while the codec group is not yet retired (§6.2 step 9). `Cadences.due` is a rate primitive that would fire it again at every multiple, and at the default 0 `cadence_audit` would print a DISARMED line on every run.
- **Half-lives and holds are not periods, so they get their own audit.** `RUN.cadence_audit(run, *, run_windows, periods)` reads no lever ("LEVERS READ: none", `train/api.py:1216`). It checks only periods that exceed the run or are ≤ 0, and anything put in `_periods` becomes a Cadences gate. So AUD states its own horizons through a new entry point, **`AUD.horizon_audit(aud, *, run_windows) -> [str]`** (+1, S3, on the ASSEMBLY 'audit' row beside `RUN.cadence_audit`). The root appends its sentences to the same startup warnings. Its LEVERS READ are `AUD_HALF_LIFE_WARN`, `AUD_EMA_HALF_LIFE`, `AUD_REWARM_WINDOWS`, `AUD_REFRESH_EVERY` and `AUD_CEIL_HOLD_WINDOWS`, which is what K4 needs. It **warns** when an armed half-life, or the longest possible hold (`AUD_REFRESH_EVERY + AUD_CEIL_HOLD_WINDOWS` = 4000 windows), exceeds `AUD_HALF_LIFE_WARN` 0.25 × run_windows. The alternative, a `RUN.cadence_audit(..., horizons=, warn_frac=)` signature move under a Q-RUN-17 ruling, is recorded and not taken: RUN would then need AUD's warning fraction handed in, and a second meaning would be added to a function whose one job is periods.
- **It does not refuse.** The tree states too-long cadences rather than raising them, because a short run is a legitimate request and run_windows is not known when build() freezes (`train/api.py:1216`, ISSUES P1-C11). A refusal at ≥ run_windows would have refused the proposal's own 200-window S4 acceptance run.
- New reading `aud.moved`: did the **live codec** move since the last reading, in parameters and in probe codes. `AUD.refresh` reads it (§6.2 step 5), at every act under 'snapshot' and on the `aud.probe` period under `'jit_ema'` (step 8), so the arm with no refresh event is not silent. It is read on the live codec, not on the snapshot, so a refresh the ceiling guard withheld does not read as a freeze. It is PRESENT-and-0 under the freeze arm; a 0 in a live run is a warning.

*Reason.* Refusing EMA ≥ 1 does not catch a freeze in effect. At 0.995 per codec step the half-life is about 138 codec steps: 553 windows at one step per 4 windows, 4416 at the default 32. At 0.99999 it is about 69k codec steps, longer than any run.

*Alternatives.* A refusal of decay ≥ 1 only, rejected for that reason. A refusal at ≥ run_windows, rejected for the reason above.

**10 — NOTHING PERSISTS A MEDIA CODE AS TRUTH.**
- R1's layout stays. Placeholders carry **clip references**: area, clip index and seed, or the waveform offset for a real area.
- DOM reservoirs, EVAL prompts, generated samples, codec rehearsal and any MEM-over-media entry hold references. Each is rendered by the new `DATA.render` and re-encoded by the current snapshot at its own rekey or probe time.
  - For DOM this is a state-shape change. `_sample_window` (compose.py:3391) returns its units plus a parallel `(clip_ref, frame_offset)` track for media units, and DOM's Partition reservoir stores that track beside the units (a restore row; counted in Contract accounting). The composed re-key callable re-encodes only the media units; text units are untouched.
  - Both change the argument contract of frozen DOM entry points without changing a signature. `DOM.observe(dom, part, *, signature, sample_window, tokens, now)` (`domains/api.py:576`) receives the track inside `sample_window`, and `DOM.rekey(dom, part, *, encode)` (`domains/api.py:887`, whose docstring says "`encode` is SIG.encode, passed in") receives a callable that takes the track as well. That needs a ruling: **Q-DOM-4** (next free after Q-DOM-3), which covers the reservoir's reference track, `SIG.encode`'s `windows` (the same object, `domains/api.py::observe`; SIG ignores the track) and the composed callable's contract. Once media is in the reservoir, the periodic A-stage `DOM.rekey` gets the composed callable too, so no media unit is re-keyed from stale codes. It is listed under the new rulings, and the X-stage `DOM.rekey` row is counted in Contract accounting.
- §3.1's "Everything persisted stores ABSOLUTE ids" stays for text and for a media id's transport address. It no longer promises a media id's meaning.
- **One exception, for resume only.** The checkpoint's replay record (item 14) holds the consumed prefix's ids [0, cursor), media codes included, exactly as the uninterrupted run holds them in memory. Only the resumed run's own reads of that prefix touch it (SIG's pair draws, the look-back), the same reads the uninterrupted run makes with the same codes. No code in it is re-encoded, re-keyed or used as meaning elsewhere.

*Reason.* Persisting codes as truth has a measured cost:
- stale latents decoded by a later decoder: area A latents from the end of P2, decoded by the P3 decoder, +0.063/+0.076 mel against their own P2 decode (+0.072/+0.080 against a fresh P3 re-encode) (D2, 2 seeds);
- codes 600 LM steps stale: +2.6% to +15.7% LM bits/position under an EMA teacher (D3; table rows 3 seeds, coordinate rows 4 seeds; s2/s3 derived from the reproduction's records), and +17.8%/+21.4% with online codes and table rows (D3 live25, s0) (0b.2 row 10).

*Alternative.* Versioned persisted codes, rejected.

**11 — LM MEDIA ROWS ARE FUNCTIONS OF LATTICE COORDINATES.** `LM_MEDIA_ROWS='coord'`.
- A media id's input vector is a set of learned per-digit vectors (the 4 FSQ digits, plus a stride-block slot under 'nested') plus a zero-born free residual row.
- Its logit is the same composition on the head side plus a zero-born free logit.
- The lattice reaches LM through an **`LM.build_model(..., media_lattice=None)` argument**, the `open_store(key_dim=LM.width)` idiom. It is one counted signature move, and no 22nd wire.
- The draft's coupling `LM.d_aud_rows` (proposal §5; no such coupling is in the tree yet) stays one wire, but its declared source tuple grows to (`AUD.enabled`, `AUD.arch`, `AUD.levels`, `AUD.strides`, `AUD.rate_mode`, `AUD.bpe_slots`), and `derive.media_rows(enabled, arch, levels, strides, rate_mode, bpe_slots)` computes it: 0 when AUD is off, 1002 under 'spec', 3002 under 'nested', + `AUD_BPE_SLOTS` under 'bpe'. `spine/assemble.py`'s `_view` exposes exactly the declared fields and `_Reads.__getitem__` raises for anything undeclared, so the tuple must name every lever the value depends on. Without `AUD.enabled`, `compute()` could not return 0, a text-only run would get 1002 media rows and a non-zero `lm.media_rows.aud`, and the 'media off bit-identical' acceptance would fail. Known answers (`tests/test_derive.py`): (False, 'spec', '8,5,5,5', '1,2,4', 'measured', 512) → 0; (True, 'spec', same, 'measured', 512) → 1002; (True, 'nested', same, 'fixed', 512) → 3002; (True, 'spec', same, 'bpe', 512) → 1514. They supersede R14's string form and Appendix A's `media_rows([8,5,5,5]) == 1002` row (0b.6).

*Reason, restated as SAMPLE EFFICIENCY measured at 600-1200 media LM steps, not drift tolerance.* It is robust at 4 of 4 seeds in each harness (0b.2 row 9):
- D1, one codec init: −9.9% to −16.7% current-area bits/s, smaller at the new seeds (A after A −11.6% to −14.2% there against −14.1% to −16.7% originally; reproduced-weaker, claim 1);
- D3, codec retrained per seed: −11.3% to −15.3% (tones −12.9/−13.2/−12.8/−12.4%; melody −14.2/−15.3/−13.2/−11.3%).

It is NOT drift tolerance:
- coordinate rows make the LM MORE sensitive to stale codes, at 3 of 3 seeds with both row types (6 of 6 readings): tones +10.2% / +15.1% / +13.7% vs table +2.6% / +11.9% / +9.9%; melody +5.1% / +11.0% / +15.7% vs +4.6% / +4.7% / +9.2% (s0 / s1 / s2);
- online codes with table rows (D3 live25, s0): tones +17.8%, melody +21.4%;
- only 62.9-67.8% of flips at 500 codec steps change a single FSQ coordinate.

The B-understanding gain did not replicate: lattice rows were better in 1 of 4 new-seed readings. **Drift mitigation is carried by the snapshot hold (item 5) and the anchor (item 6), not by the rows.**

*Cost.* Higher cross-area interference at 4/4 seeds: the earlier area's bits/s rises +42 to +59 after the next area, against +34 to +41 with table rows. The end level still ties or beats table rows (−7.1% to +0.1%). Hence item 12.

*Alternatives.*
- `'table'` stays a LIVE S5 arm, and a longer / larger-data check (S5) runs before coordinate rows are unconditional: the gain may be data starvation that shrinks at 20k windows.
- A 22nd wire, rejected on budget: the tree has 19 of 25 wires, the audio stages take 21 and VID 23, leaving 2. The lattice is build-time structure, so it goes where build-time structure goes: a build argument, as `open_store(key_dim=)` does. (A Coupling can carry any declared unit, including a U.NAME string, so "a wire cannot carry it" was not the reason.)

**12 — EARLIER MEDIA AREAS ARE REHEARSED IN THE LM STREAM.** `DATA_MEDIA_REHEARSE` 1/3.
- Inside a media phase, that share of media windows is drawn from earlier media areas. `DATA_TEXT_SHARE` 0.3 is unchanged.
- *Reason.*
  - With no LM media rehearsal, the earlier area's understanding reads 0.0 at the end in every D1 run, and its caption bits/byte rises 0.28-0.36 → 2.10-2.77 across all D1 runs (original, judge, critic and reproduction records).
  - D2's base arm drew 4 of its 12 media rows from the earlier area (1/3; 25% of all 16 rows, text included; `d2/d2run.py:7`, `:751`), and tones understanding held: 0.25 → 0.234 (s1), 0.125 → 0.25 (s0).
  - D3 used the same 12 media + 4 text rows with one-third of media rows from the earlier area (`d3/run.py:227`, `:434`), and tones bits held flat under coordinate rows (D3 frozen25c: 3.612 → 3.615 bits/position).
  - So both harnesses measured 1/3 in the lever's unit, and 1/3 ships.
- *Alternatives.* 0 is the lower-bound arm; larger shares are measured in S5.

**13 — S0b: THE MID-EPOCH ACT (Q-RUN-8 OPTION (a)) COMES FIRST, AND MAKES TEXT RETOK LIVE.**
- `RunClock.revise_epoch_length(n)` is added, and the act moves from `_flush` into `run`, after the flush while the batch is empty. It is a new LOOP_ORDER stage, 'X', with its own `_CALLS['X']` entry.
- **One X row per package call.** `loop.py`'s `_rows_by_stage` credits `{PKG}.{name}` only from each row's own package and name columns, and its misfiled check (`loop.py:~627`) raises for any `_CALLS['X']` name that is not a row at X. The epoch roll, stage E, has one row per call for the same reason. So the act is four X rows at S0b: `TOK.splice`, `RUN.RunClock.revise_epoch_length`, `OPT.revise_horizon` and `DOM.on_retokenize`. `AUD.refresh` is added at S3 and `DOM.rekey` at S4. The MEM hand-over is not an X row. The act sets `resegment` and `remap` for the next B-stage `MEM.maintain`, as the roll sets `resegment` today (`loop.py:1225`), so they are named in that row's text.
- The act runs when any of its Dues is raised, OR'd per Q-TOK-12:
  - TOK's retok Due, from `TOK.on_window`'s own `_due` (its state is checkpointed as `tok.retok_seeded_window` in vocab_state's counters);
  - AUD's refresh Due, `Cadences.due('aud.refresh', AUD.refresh_period(aud), clock)` (from S3; Cadences state is checkpointed, Q-RUN-9); a fire before readiness raises no act;
  - the readiness relay Due (from S4);
  - the ceiling guard's hold-expiry Due and the frozen control's Due, each a one-shot Windows comparison in the root (from S3; item 8, §6.2 step 9);
  - the 'alloc' / 'bpe' arms' Dues.
- **What the act does to text depends on which Dues it carries.** Only an act carrying TOK's retok Due re-segments text at the current vocabulary. An act raised only by AUD's refresh splices nothing: lengths do not change at a fixed per-run stride, and codes are re-encoded lazily at cut. A relay act re-lays media at the view of the last text segmentation, so no id minted since then enters the stream (item 14); an act carrying both TOK's Due and the relay Due re-segments at the current vocabulary and re-lays media in one splice. Without this rule the effective text retok cadence would be min(2000, `TOK_RETOK_EVERY`), and `TOK_RETOK_EVERY=0` would stop meaning "never re-segment in-run" once media is on.
- *Reason.*
  - At `RUN_EPOCHS=1` every text retok today waits for a roll that never comes. About 600 mints per 20k-window run are stranded (arithmetic from `TOK_GROW_EVERY` 200 × burst 6), and `TOK_RETOK_EVERY` decides nothing at any `RUN_EPOCHS` (measured 2026-09-24, `docs/04_CONTRACT.md` Q-RUN-8).
  - D1 prototyped the act: 12 acts at 2 seeds, plus 6 more at s2 in the reproduction; every prefix and cursor assertion passed.
- S0b rewrites `TOK_RETOK_EVERY`'s help to the new behaviour and re-renders `docs/05_DEFAULTS.md`. The help today reads "0 disarms the ask. The ask waits for the next epoch roll, which re-segments whatever this is set to" (`tok/levers.py:280-282`); the act gives 0 the meaning its former help claimed until 2026-09-24 ("leaves already-emitted ids alone forever") and that Q-RUN-8 requires.
- *Alternatives* (Q-RUN-8's own):
  - (b) `begin_epoch(n, at=)`, rejected there;
  - (c) leave the lever inert, rejected there.

**14 — A RESUME CONTINUES FROM THE LAST ACT'S STATE** (the critic's blocking issue, option (b)).
- The checkpoint records the view of the last TEXT SEGMENTATION (an epoch start, or an act that splices; item 13), and TOK segments at that view: ids minted after it become visible to the stream at **the next act that carries TOK's retok Due** (≤ `TOK_RETOK_EVERY` windows). This refines D-1's "at the next act": an act raised only by AUD's refresh does not re-segment text (item 13), so that `TOK_RETOK_EVERY` keeps its meaning once media is on.
- Media likewise: whatever produced the codes and layout at the last act is recorded in the Segmentation record and the checkpoint as of that act, and never recomputed from moved state. That covers:
  - the codec snapshot;
  - the stride maps;
  - the applied BPE merges;
  - the chosen stride.
- Text likewise: the BPE-dropout stream's state from just before the last text segmentation (below).
- A resume rebuilds the Segmentation from the last act's recorded state and the consumed prefix's replay record, so it is **bit-exact against the uninterrupted run**, for a save at an optimizer-step boundary with the stream's Configs unchanged (§11).

*How "segment at rev" is made computable in this tree.* A rev number alone is not enough, for three reasons found in `tok/api.py`: `vocab.rev` is a per-process cache stamp that restarts at 0 in a child (`:287-299`) and is not in `vocab_state` (`:2829`); `mint_burst` reinstates retired ids (`:2058-2062`, `_reinstate` `:426`), so one id can be retired, reinstated and retired again; and `retire()` pops the id from `seq2id`, so an id live at the act but retired since is absent from today's match table. So:
1. **`vocab.rev` becomes run-global.** `vocab_state` carries it, `restore_vocab` sets it after the merge replay (so the child's rev equals the parent's, whatever the replay's own bumps), and it is never reset.
2. **Every Segmentation carries its view**: `Segmentation.view = (rev, size, retired)`, the match table's revision, `len(id2bytes)` and the retired set when it was cut (a record-shape change). The retired set is small (probation retirements) and `id2bytes` is append-only.
3. **Segment at a view.** TOK builds the view's match table from `id2bytes[:size]` minus `retired`, with its own per-first-byte bound, and `_segment` runs its greedy longest match on it. This is exact because one byte string never has two ids (`_reinstate` restores the same id with the same bytes, P1-M79) and `_segment` is a memoryless greedy longest match. Today's `seq2id` is not consulted, so an id retired after the act is still found and an id minted after it is not.
4. **The one-slot cache is not shared across views.** `tokenize`'s `_retok_cache` is keyed on (data, start, len) plus a stamp of the CURRENT table, `(vocab.size(), len(vocab.seq2id), len(vocab.retired), vocab.rev)` (`tok/api.py:1475-1477`). A call at an old view on the same buffer would store a view-V answer under the current stamp, and a later `view=None` call would be served it as a `tok.retok_noop`, or the reverse. So a call with `view` not None neither reads nor writes the cache. The epoch-start resume, a roll at `TOK_RETOK_EVERY=0` and the held-out encode each pay one segmentation, and the act's no-op test compares views directly (§13 S0b). Known answer (S0b): `tokenize(view=V)` followed by `tokenize(view=None)` on the same buffer returns the current-table segmentation and counts no no-op.
5. The loop's `seg_table_moved` flag and the −1 / −2 sentinels of `rev_at_last_seg` (`loop.py:429-436`, `:703-706`; `compose.py:2562-2564`) are replaced by comparisons against `run.seg.view.rev`. Today a child's first roll re-tells DOM through that sentinel (an extra `DOM_TOKC_DECAY` 0.5 the uninterrupted run does not apply); with the view it does not.

*The BPE-dropout stream crosses the save* (it does not today). BPE-dropout draws from `vocab.dropout_rng`, the ONE stream `build_vocabulary` mints at `"tok.dropout.mint"` from RUN.seed, and it must CONTINUE across calls (P1-H56; `tokenize`'s docstring: "`seed` IS ACCEPTED AND DELIBERATELY NOT READ"). `spine/rng.py`'s Rng has deliberately no `setstate()`, and `vocab_state` carries no stream state today, so a resume re-mints the stream fresh (`tok/api.py:886`). Resume is therefore not bit-exact at `TOK_DROPOUT > 0` as the tree stands. The fix follows the DOM / SIG / FAB / WORLD pattern: those packages save `(rng._r.getstate(), rng._draws)` in their state_dict and put it back with `rng._r.setstate` (for example `sig/api.py:1636`, `:1698`).
- `vocab_state` carries the dropout stream's state (a state-shape change with a restore row), and `restore_vocab` puts it back.
- `run.seg` records the stream's state from just before the last text segmentation, a relay's splice included.
- The resume's splice rewinds the stream to that recorded state, draws, and must end at the state `vocab_state` saved. A mismatch is refused, because it means something drew between the act and the save.
- No per-call seed is read anywhere. `TOK.splice` takes `stream_state=None` (the resume passes `run.seg`'s), not `seed`. A per-event derived child (`tok.dropout.seg.e<n>.k<k0>`) is the recorded alternative. It is not taken because it would restart the stream at every segmentation, which is the restart P1-H56 forbids. Q-TOK-15 states that neither `tokenize(view=)` nor `splice` reads `seed`, and that the one stream's position is what crosses the save.

*What else a resume must rebuild, and how* (§11 gives the payload):
- **The consumed prefix is read after a resume.** `SIG.train_step` draws anchor pairs from the whole consumed prefix (`sig/api.py:862`, `_draw_pairs` `:1068`) under `SIG_SPACE` 'tokens' and 'typed' (and 'typed' is required with media, proposal §5). `_sample_window` reads the `width_units` units ending at the cursor (`compose.py:3391-3409`). The unit under the act's cursor, [k0, p), was cut by an earlier view and snapshot. A dummy prefix (D1's, `d1/run_arm.py:670-682`, which had no SIG) is therefore not enough.
- **The replay record covers the whole consumed prefix, [0, cursor), as held in memory at the save.** [0, p) alone would not do. Positions [p, cursor) were consumed after the last act. Under 'snapshot' they were cut by the act's snapshot, so the splice regenerates them exactly (a check, not a need). Under `'jit_ema'` they were cut window by window by a teacher that moved between cuts, and none of those teacher states is kept. **Codes cut at a window cut, under either mode (the lazy re-encode under 'snapshot', the teacher's cut under `'jit_ema'`), are written in place into the Segmentation**, so SIG's pair draws, the look-back and the LM read one code per position. The record is therefore the codes they read.
- **The record's fields** (about 10 bytes per position): ids (4), `byte_pos` (4; a media position's is its clip's anchor, which a cumulative sum of `bytes_per_id` could not give), modality and role (1), and the snapshot-version track (1). `_signature_cursor` (`compose.py:3367`) reads `byte_pos[i·ctx]`, and `MEM.write` takes positions from it. Two fields are re-derived, not stored: `labels` as `stream.labels[byte_pos]` (the stream is re-drawn deterministically by `DATA.restore_stream_state`), and the record's `bytes_per_token`, which the resume's splice measures over the spliced record as the act did (`compose.py:3588` `_bytes_per_window` reads it).
- **Loop-carried values.** `System.novelty` (it feeds `FAB.forward`'s routing; compose restores only `token_seen`, `compose.py:2540-2564`), `probe_prev` (`loop.py:722`) and `manage_losses` (`loop.py:765`, FAB.manage's flush-loss mean) join `payload['LOOP']`. S0b audits every value `run` carries across flushes: each is checkpointed or shown re-derivable, with a test. `_mint_at_last_seg` (renamed from `_mint_at_last_roll`) is seeded from `run.seg`, so the stranded-mint warning counts mints since the last text segmentation (`tests/test_resume_clock.py` C8 is rewritten to match).
- **The clock.** No surface restores the epoch position today: `new_clock` has no in-epoch argument (`train/api.py:463`) and `begin_epoch` zeroes `_in_epoch` (`:663`). The fix is a signature move, `RUN.new_clock(..., resume_in_epoch=0, resume_windows_in_epoch=None)`, with a Q-RUN ruling (Q-RUN-16, next free) that supersedes Q-RUN-10's declared replay. ASSEMBLY_ORDER runs 'clock' (`RUN.new_clock`) before 'epoch0' (`RUN.RunClock.begin_epoch`), and begin_epoch would zero what new_clock restored. So **on a mid-epoch resume carrying `run.seg` the epoch0 row does not call `begin_epoch`**: new_clock has already opened the epoch at the saved position, and the re-measure refusal (§11) then compares the rebuilt Segmentation's length with the saved `windows_in_epoch`. The row's note says so. `run()` seeds its cut index `win_in_epoch` from the restored `counters()['in_epoch']`: it zeroes it on entry today (`loop.py:685`), and the clock's `_in_epoch` is private (`:784-792`). Known answer (S0b): after assembly on a mid-epoch resume, `clock.in_epoch` and `windows_in_epoch` equal the saved values, and the first window cut has the saved in_epoch as its index.
- **A boundary checkpoint resumes as the roll would.** A periodic, SIGUSR1 or max_windows save in the window that rolled runs before the roll's draw and re-segmentation (`loop.py:1104-1135`, then `:1146ff`), so it holds epoch e+1, in_epoch 0 and `windows_in_epoch` None (`train/api.py:707-715`) while `run.seg` still describes epoch e. So `run.seg`'s text part carries its epoch. When that is behind the clock's, compose segments the drawn stream from byte 0 at the roll's view (`run.seg.view` at `TOK_RETOK_EVERY=0`, else the restored table) from `vocab_state`'s stream state, then calls `begin_epoch` and writes a fresh `run.seg`.
- **A stamp exists from window 0.** `run.seg`'s text part is written at every text segmentation (compose's epoch-0 row, every roll, every act that splices) and its media part at every act, so a checkpoint taken before the first act has one.

*Reason.*
1. **Bit-exact continuation becomes a tree invariant here. It is NEW, not inherited.** Today `tests/test_resume.py` (R1-R8) and `tests/test_resume_clock.py` (C1-C9) check what crosses the save and what is refused, never a continuation against the uninterrupted run. C9 asserts that a mid-epoch resume "is warned with the windows it replays": Q-RUN-10 kept that replay deliberately (`train/api.py::new_clock`: "A MID-EPOCH RESUME REPLAYS THE EPOCH IT WAS INTERRUPTED IN, DELIBERATELY"). `tests/test_tok_persist.py:29-33` records that the resumed stream "does not today" match the uninterrupted run (Q-TOK-13, "Not in this ruling, and OPEN"). Once the act runs mid-epoch, a replay would re-train windows at a vocabulary and snapshot the uninterrupted run did not have at those windows, so the replay stops being a harmless repeat. R-RESUME-AT-ACT closes Q-RUN-10's replay and Q-TOK-13's open item.
2. It gives `TOK_RETOK_EVERY=0` the meaning its former help text claimed. Q-RUN-8 (`docs/04_CONTRACT.md` line 4261) says that meaning needs exactly "a vocabulary that excludes what was minted since the last segmentation".

The failure it fixes (critic, toy, seed 0): with mints between acts, the resume re-measured 231 windows against 233 saved, and continuing gave max |dloss| 0.4755. D1's bit-identical resume held only because D1 minted and refreshed only inside acts.

*Cost.*
- A TOK "segment at view" capability: the keyword signature move `TOK.tokenize(..., view=None)` with a Q-TOK ruling (Q-TOK-15, next free); `Segmentation.view`; `rev` and the dropout stream's state in `vocab_state`.
- The clock restore: the `RUN.new_clock` signature move with Q-RUN-16.
- The replay record: about 10 bytes per consumed position, about 26 MB at the end of a 20k-window run × 128 positions (arithmetic).

*Known-answer tests* (each bit-identical against the uninterrupted run; §13 S0b lists them all): save between a mint and the next act; between a retire and the next act; between a reinstatement and the next act; two resumes in one run; one window after an act; at `TOK_DROPOUT > 0`; a boundary checkpoint at `RUN_EPOCHS=2`; a save requested between flushes at `OPT_BATCH_WINDOWS` 2 and at `OPT_ACCUM` 2; and, first of all, a text-only continuation with no act, the first continuation-equality test in the tree. At S3, a save after an AUD-only act at `TOK_DROPOUT > 0`, and under `'jit_ema'` a save k windows after an act, with k > `AUD_TRAIN_EVERY` so the teacher moved between cuts; at S4 the same with SIG 'typed' on and media inside the look-back.

*Alternatives, recorded and rejected:*
- **(a) "a resume is an act".** Bit-identity would hold only against a run that also acted at the save point. So every `CKPT_EVERY` save would perturb training, and bit-exact continuation would be given up.
- **(c) "mint only at acts".** It would change TOK's own measured mint dynamics as a side effect of a resume fix: `TOK_GROW_EVERY` 200 against acts every 3000 needs 15× bursts or 15× fewer mints. It would also tie text vocabulary growth to AUD's refresh cadence. Bit-exactness is available without it.
- A separate `TOK.tokenize_at` entry point (+1), rejected. `tokenize` is documented as the "ONE function [that] serves" every whole-stream segmentation. A second whole-stream function that differs only in which table it reads is the report-path / audit-path split the tree refuses. The keyword keeps one meaning ("segment with the match table as it stood at a recorded view; None = as it now stands"). `TOK.splice` (item 15) is not that split. It re-segments a tail of an existing record, and it owns the spliced record's `bytes_per_token`, which a whole-stream call cannot define. Q-TOK-15 rewrites `tokenize`'s docstring sentence to match: `tokenize` serves every whole-stream segmentation (the initial one, a roll, the final one before eval, the held-out encode), and `splice` serves every tail re-segmentation of an existing record (an act, a resume).
- A per-id event log `[(rev, born | retired | reinstated)]` instead of the view, rejected: it answers the same question with more state, and the view is what a splice needs anyway.
- Replaying the chain of every act since the epoch start instead of a replay record, rejected: media codes in the prefix were cut by snapshots that no longer exist (it would need every snapshot since the epoch start, about 5 MB each), and a resume would pay one tail tokenization per act.
- A replay record of [0, p) only, rejected: under `'jit_ema'` it cannot reproduce the codes of [p, cursor) (above).

*Held-out and generation.* Between acts they segment at `run.seg.view`, so evaluation reads the vocabulary the LM is trained on. The alternative, the current table, is rejected: ids minted since the last act have initialised rows the LM has never trained. The tree has no held-out encode call site yet (`EVAL.holdout_probe` is deferred to P5, and `EVAL.generate` to P6), so the rule applies when those land. S0b's ship rule uses the training stream's prequential bits per byte instead (§13 S0b).

**15 — THE ACT ON AN INTERLEAVED STREAM SPLICES AFTER THE UNIT UNDER THE CURSOR.**
- The splice, in order:
  1. Find the unit under the cursor `at` (a text token, or a whole clip record `[task] BEGIN codes END`). `at` is always the cursor k0, in the act and in the resume.
  2. Splice after it, at p.
  3. Re-tokenize the text tail from the next text byte, at the given view.
  4. Re-run `TOK.interleave` on the tail.
- Segmentation ownership stays TOK's, through a TOK splice helper (+1 entry point): `TOK.splice(tok, vocab, seg, data, labels, *, at, view=None, media=(), id_fn=None, regularize=False, stream_state=None) -> Segmentation`. It takes `regularize` like `tokenize` (`tok/api.py:1320`). It takes `stream_state`, the BPE-dropout stream's recorded position, instead of a `seed`: the one stream continues across calls (P1-H56), and a resume rewinds it to `run.seg`'s recorded state (item 14). So a resume at `TOK_DROPOUT > 0` needs no later signature move.
- It is the tree's second segmentation surface, and legitimately so: it re-segments only the tail of an existing record, and it owns that spliced record's `bytes_per_token`. `tokenize` stays the one whole-stream function, and Q-TOK-15 rewrites `tokenize`'s "ONE function" docstring sentence to say so (item 14's alternatives).
- It calls `_segment` directly with the view's match table, not `tokenize`. It owns `tok.retok` (or `tok.relay` at a relay-only act), `tok.byte_fallback` and `tok.dropout_skip` for its call (on a resume's rebuild the root puts the saved counters back afterwards and counts `tok.segment_resume` instead, §11), and it leaves `_retok_cache` alone: `tokenize` always counts `tok.segment` and keys its one-slot cache on (data, start), so routing the splice through it would count wrongly and evict the slot the roll's no-op refusal relies on. `_segment`'s docstring says those two counters are "declared by tokenize() and by nothing else". S0b updates it to name `splice` and `tokenize(view=)` as well.
- The spliced record's `bytes_per_token` is TOK's measurement over the spliced record, and `tok.bpt_tail` reports the tail's own value. The run's throughput reading depends on this field being live (`compose.py:3588-3595` `_bytes_per_window`, ISSUES P1-L42; `RUN.bench_summary`, `loop.py:1616`). SIG's width stays on `Vocabulary.bytes_per_token`, which is where the build-time value belongs.
- Under `'bpe'`, codes are held from the act (encoded by the act's snapshot and merged at the act's merge revision), not cut just in time.
- Known-answer test: a cursor inside a clip.

*Reason.* The judge's S0b row computed `b0 = byte_pos[k0]`. For a media position that is the clip's anchor, so the tail would re-emit a partly consumed clip. D1 spliced after the record (`d1/run_arm.py:443-452`) and kept act-time codes for 'bpe' (`jit_refresh` returns early under 'bpe', `:341`).

*Alternative.* The root assembling the Segmentation, rejected: it is TOK's record type, and `bytes_per_token` of a spliced record would be defined outside TOK.

**16 — THE ROUTING STACK SEES MEDIA THROUGH LATTICE COORDINATES, AND EVERY REFRESH IS A SELF-INFLICTED SHIFT.**
- SIG 'typed' embeds a media unit by the same coordinate composition as the LM rows, not by a free code table. It uses a `SIG.build(..., media_lattice=None)` argument, one counted signature move.
- New gauge `sig.media_drift`: the signature change on fixed probe clips at each refresh.
- **FAB, OPT and CAP.** An act stamps `shift_at_windows` / `shift_at_steps` when it moves the text view, and when it refreshes the snapshot or re-lays media **once media has been consumed**. Before the first media window a refresh or a relay changes nothing the LM or the routing stack has seen, so there is no shift to mis-read, and stamping it would be an unmeasured pause of growth for nothing. After that, every refreshing act stamps, as D-8 decided. This refines D-8's wording, not its reason: the reason (so that DOM and FAB do not read a refresh as a domain shift) has no object while no media is in the stream.
  - The stamps reach two consumers today: `FAB.grow_check(shift_at=)` (FAB's cooldown) and `OPT.maybe_step(shift_at=)` (inert at `OPT_LR_SHIFT_WARM` 0).
  - A third arrives at P4: `CAP.observe(..., blackout)` (`capacity/api.py:1300`), whose docstring says "note_shift marks retok, epoch resample and LR restart". `CAP.observe` is a deferred stub today (P4), so the act stamp reaches CAP's blackout when that row lands.
  - The cost is stated: `FAB_COOLDOWN` 400 windows at every stamping act blacks out FAB growth for about 20% of windows at a 2000-window act cadence, and about 27% for the union of 2000 and 3000 (arithmetic). `FAB_GROW` ships True (`fabric/levers.py:339`), so this is an unmeasured partial pause of growth. 0b.3 lists it as not necessary, and S5 (iii) decides. S0b and S5 report the share from a new FAB counter, `fab.cooldown_windows` (windows inside the cooldown): `fab.growth_blackout` is a Gate, and the `*_refused_cooldown` counters count refused asks, not windows.
  - Arms (S5 iii), selected by `AUD_SHIFT_STAMP`: `'flips'` stamps a refresh only when the fraction of probe codes flipped since the last stamp exceeds `AUD_SHIFT_FLIPS`, which then serves both code modes; `'always'` stamps every act from readiness on, before media included. The default, `'refresh'`, is the rule above. AUD returns the decision as RefreshReport's `stamp` (§7), which the act's step 10 reads. `'flips'` is not the default, because D-8 decided that every refreshing act stamps. S5 (iii) measures whether the thresholded stamp loses anything the default protects.
- **DOM.** `DOM.observe` has no shift input, so the stamp does not protect DOM. What protects it is a re-key at the act: `DOM.on_retokenize` when the text view moved, and `DOM.rekey` with a root-composed callable (`DATA.render` → the new snapshot's `AUD.encode` → `SIG.encode`) when the snapshot was refreshed after media was consumed. `DOM.rekey` runs only at `SIG_MODE=learned` (Q-DOM-3). `DOM.on_retokenize` runs whenever the text view moved, at any `SIG_MODE`, as it does at the roll today (`loop.py:1248-1250` has no `SIG_MODE` test), so `DOM_TOKC_DECAY` still applies at `SIG_MODE=bigram`. `DOM.rekey` re-encodes every reservoir of the one Partition (`domains/api.py:887`); there are no "media-holding partitions". Its cost goes in §12.
- **Per-byte levels, and how they meet R11's running baselines.** The root converts before it hands over, and each consumer's unit is stated:
  - DOM competence (`DOM.note_competence`) and CAP's improving test (`CAP.observe`): bits per byte × the build-time bytes_per_token, i.e. bits per build-time token, for text; bits per clip-second for media, withheld inside the cooldown after a refresh. R11's per-modality running baseline then normalises that value. Unit invariance first, cross-modality comparability second. The CAP half is inert until `CAP.observe` is rowed (P4); it is specified now so that P4 lands on the converted unit.
  - MEM's surprise gate: MEM's surprise is a probability complement, `1 − p(true token)` (`loop.py:2085`; `MEM_WRITE_GATE` is U.PROBABILITY, `memory/levers.py:190`). The root hands `surprise_b = 1 − p^(bpt_build / bytes(token))`, the per-token probability rescaled to a build-time token by its per-byte geometric mean. That re-denominates `MEM_WRITE_GATE`, which needs a ruling (Q-FAB-5 is the precedent): Q-MEM-14 (next free after the remap's Q-MEM-13) updates its help. Media levels are not handed to MEM: media windows skip MEM (proposal §5), and MEM-over-media is S8 move #8.
- *Reason.* No prototype had SIG, DOM, FAB or MEM. `loop.py:2199-2206` records that one changed id perturbs every signature containing it "and the assembler reads that as a domain shift".
- Under `'jit_ema'` there is no refresh event, because drift is continuous. The stamp is raised at a probe reading instead: when the fraction of probe codes flipped since the last stamp exceeds `AUD_SHIFT_FLIPS` 0.25. That value is hand-set (the critic asked for a flip-rate threshold without giving one), and it is an arm-only lever. The probe reading comes from `AUD.refresh` on its own `aud.probe` period after readiness (`AUD_PROBE_EVERY`), not at acts. Under `'jit_ema'` AUD raises no act, so tying it to acts would leave the arm's stamp, flips, `aud.moved` and guard count silent for 3000 windows, or for the whole run at `TOK_RETOK_EVERY` 0.
- *Alternatives.*
  - Teacher-latent pooled signatures, an arm.
  - The S5 (iii) arm (FAB, DOM, MEM on; live vs frozen codec) measures whether coordinate signatures, stamps and re-keys are enough. It reads DOM's spawns and culls as `part.n_created` and `part.n_culled`, FAB's growth as `fab.grown_regression` and `fab.grown_stall` (and `fab.births`) and its culls as `fab.cull_util` and `fab.cull_fail`, `sig.media_drift`, and the FAB blackout share from the new `fab.cooldown_windows`. The others are the tree's existing names; `fab.grow` is the arm's configuration echo (`fabric/api.py:1210-1216`), not growth, and there is no `dom.spawns` or `fab.cull`.

**17 — WORLD's MEDIA TARGET IS THE TOKENIZING CODEC'S LATENT, STOP-GRADIENT, WITH HORIZONS IN U.SECONDS.** §10.
- The target is the snapshot's latent, or the teacher's under `'jit_ema'`.
- The horizons are `WORLD_MEDIA_HORIZONS_S` '0.04,0.2'. units.py has SECONDS and no milliseconds label.
- *Alternative.* A student-input or student-target WORLD, an arm.

**18 — NO NEXT-TOKEN GRADIENT INTO THE CODEC; BOUNDED COUPLINGS ARE ARMS.**
- The old rejection of joint training is narrowed to the LM's likelihood loss flowing into the codec through STE or its targets. Evidence against that coupling:
  - GEAR, gFID about 105 [V];
  - D2's undetached-target arm (tgtgrad, 1 seed): understanding 0.016 vs 0.078; PR 2.45 vs 3.71 / 4.40 (d2) and 2.78 with no LM gradient at all (d2_nolm), so the understanding drop, not the PR, is the evidence.
- Arms, off: `AUD_LM_GRAD='rep'` (a DreamerV3-style bounded term, weight 0.1, 1 nat free bits) and `'input'` (continuous route only).

**19 — READINGS SURVIVE A MOVING CODEC.**
- The R matrix's primary media readings are codec-invariant:
  - recover exact per attribute (codec ceiling, generation, understanding);
  - a2t caption bits/byte;
  - grounding bits per clip;
  - mel.
- Bits per audio-second stays, tagged with the snapshot step. Its alphabet moves, so bits/s over two codecs is not a like-for-like LM comparison; bits/code is secondary.
- New rows per area:
  - codec BWT: mel AND per-attribute recover exact of area a at every later phase end;
  - flips per refresh and cumulative since readiness on the fixed probe;
  - a stale-code probe;
  - `aud.moved`;
  - `sig.media_drift`.

**20 — GEOMETRY IS EXACT ONLY WHERE A TENSOR SHAPE OR AN ID ADDRESS DEPENDS ON IT.**
- `aud.version` becomes a READING: the snapshot step plus a weight hash at save.
- The geometry manifest keeps only Config-derived EXACT / MAY_WIDEN fields, the two rule kinds `CKPT.check_geometry` supports (`ckpt/api.py:1024-1058`). The chosen stride, `aud.version` and `run.seg` are run-time values, so they become payload-side checks with named refusals in a CKPT ruling (§11).
- A resume-time stride change is refused unless an act re-lays the unconsumed tail (§11).

**What of this stack was measured together.**
- *Measured as one stack* (D1 live25, one codec init): item 6's cadence 1/32, floor 5e-5, AdamW betas (0.8, 0.99), weight decay 0.01 and a gradient-norm clip of 1.0, codec rehearsal 0.5 of 0.5 s crops, anchor 10, a snapshot refreshed at every act every 2000 windows; a 25 Hz spec codec pre-trained 4000 steps on half tones and half a generic 5-kind mix; table or lattice rows. Outcome: lower bits/s in 24/24; no consistent cost or gain on the LM-side codec-invariant readings; a consistent codec-ceiling cost, recover exact lower in 7 of 8 with 1 tie (0b.2 rows 1-2).
- *Where the shipped default differs from that stack* (none of it measured):
  - (a) budget: 750 codec steps per candidate by readiness, cosine with no warm-up, against 4000 with a 100-step warm-up and a linear decay;
  - (b) data: readiness on the first media area only, against D1's half-generic mix, which included a melody kind, so D1's area B was not wholly new to its codec;
  - (c) rate: 'measured' may pick 12.5 or 50 Hz, and the regime was measured only at 25 Hz;
  - (d) 0.64 s crops, against 0.5 s;
  - (e) a refresh at every act, with holds of 1000-2000 windows, against a constant 2000;
  - (f) LM steps: the default holds windows (data) per codec step fixed, so at `OPT_BATCH_WINDOWS` 1 it takes 32 LM steps per codec step against D1's 4, and 1000-2000 LM steps per hold against 250.
  S3's CPU replica of the full shipped stack in the D1 harness, against a frozen control of its own (item 6), is what lets the label transfer. Until it passes, the label is D1's, not the default's.
- *Measured separately, not in that stack:*
  - `DATA_MEDIA_REHEARSE` (D2, D3: 1/3 of media rows);
  - flip locality (D3);
  - the act (D1 live50bpe).
- *Not prototyped at all:*
  - the readiness Gate, its per-family floor, and the Gate under 'measured';
  - the `'measured'` rate with 'spec' candidates (per-stride 'spec' rate-distortion is unmeasured);
  - the ceiling guard's calibrated threshold and its hold;
  - the hidden-freeze audit (`AUD.horizon_audit`);
  - the codec schedule owned by AUD, and candidate retirement through `OPT.retire_group`;
  - the silence pad and trim under 'spec' that make positions per clip exact at stride 4 (D3 padded only its nested codec);
  - resume from the last act: the view, the replay record, the clock restore and the loop-carried values;
  - the act's Due rule (text re-segmented only at a TOK Due);
  - the interleaved splice;
  - the routing-stack handling (re-keys, per-byte levels, the stamp only after media is consumed, FAB blackout);
  - the BPE-dropout stream crossing the save, and the replay record of the whole consumed prefix;
  - the probe cadence and size.
  Each is a mechanism with a known-answer test in §13, not a measured gain.
- The combination the judge shipped (just-in-time EMA codes + teacher-targeted anchor + re-warm + one step per 4 windows) was never run in a stream. It is now S5 cells, not the default.
- Owner-scale drift (about 530 live codec steps at the default cadence in 20k windows) is unmeasured, and `aud.flip_cum` reports it.

### 0b.2 The measured basis

**How to read the table.**
- Paths are relative to `results/live_codec_design_2026-09-25/prototypes/`.
- "s0/s1/..." are seeds. Values are per seed, in that order.
- "Repro" is the independent reproduction's verdict on the matching claim, at the seeds it reran: s2 and s3 for claims 1, 2, 3, 6, 7 and 11; s2 only for claims 4, 5, 8 (the act) and 9 (the D1 pair); s1 and s2 for claim 9's D3 arms; s1 for claim 9's D2 arm; the same seed for claim 10 and the resume test. The verdicts are:
  - *reproduced*;
  - *reproduced-weaker*;
  - *not rerun*;
  - *derived*, meaning computed here from existing records and checked by no one else.
- Harnesses:
  - **D1**: a stream prototype. One pass of 8000 aud/tones clips then 8000 aud/melody clips, 25% text replay, windows of 128, 8 windows per LM step, about 9870 windows in total.
  - **D3**: an i.i.d. prototype. Its "window" is one LM step of 16 independent examples.
  - **D2**: a continuous-route prototype.

| # | Claim | Numbers per seed | Seeds / inits | Harness | Repro | Evidence |
|---|---|---|---|---|---|---|
| 1 | At D1's low-plasticity regime (item 6), a live codec gives lower LM bits/s than the frozen codec, with no consistent cost or gain on the LM-side codec-invariant readings, and a consistent codec-ceiling cost (row 2) | live − frozen bits/s as [A after A, A at end, B at end]. **Table rows:** s0 −3.04, −2.10, −2.15; s1 −4.27, −5.23, −2.83; s2 −4.47, −7.76, −4.21; s3 −5.81, −6.59, −3.14. **Lattice rows:** s0 −1.39, −1.71, −2.57; s1 −2.73, −7.58, −2.48; s2 −2.87, −0.93, −1.21; s3 −4.06, −6.96, −3.27. **24/24 lower**, range −0.93 to −7.76 (bits/s is codec-dependent, item 19). **LM-side codec-invariant, same runs:** caption bits/byte (A after A and B at end, both row types) worse in **11 of 16**, −8.7% to +7.9%; B understanding exact worse in **5 of 8** (table 0.095 / 0.167 / 0.214 / 0.238 vs 0.143 / 0.155 / 0.226 / 0.214; lattice 0.262 / 0.262 / 0.19 / 0.179 vs 0.274 / 0.25 / 0.214 / 0.286); generation exact (A and B, t 1.0 and 0.7) worse in **12 of 32**, better in 18, tied in 2; no grounding reading. **Codec ceiling:** recover exact below the single frozen reading per area at 4 of 4 live seeds (A) and 3 of 4 plus a tie (B) (row 2). Not codec-step-matched: the frozen codec took no further step, the live one +308 at 5e-5 | 4 LM/stream seeds × **ONE codec init** | D1 | bits/s reproduced (claim 3: 12/12 new-seed readings; with the 6 original table-row and 6 judge lattice-row readings, 24/24; the README's "18 of 18" omits the judge's 6 s0/s1 lattice readings); codec-invariant counts *derived* (`rev/audit_d1.py` recounts them) | `d1/res/{live25,frozen25}_s{0,1}.json`; `judge/d1c/res/{live25lat,frozen25lat}_s{0,1}.json`; `repro/d1/res/*_s{2,3}.json`; `repro/compare_out.txt` |
| 2 | Same regime, codec side: mel slightly better, recover exact LOWER, understanding mixed | A mel after A: live 0.5161 / 0.5236 / 0.5107 / 0.5161 vs frozen 0.5319. Recover exact at end: A 0.229 / 0.292 / 0.271 / 0.271 vs 0.347; B 0.188 / 0.25 / 0.271 / 0.26 vs 0.271 (lower 7 of 8, 1 tie, against one frozen reading per area; D3's per-seed codecs are mixed, row 15). B understanding exact (table rows): 0.095 / 0.167 / 0.214 / 0.238 vs 0.143 / 0.155 / 0.226 / 0.214 | one codec init × 4 | D1 | mel reproduced; recover s2/s3 *derived* from the reproduction's records | `d1/res/{live25,frozen25}_s{0,1}.json` (`A_codec`, `B_codec`); `repro/d1/res/{live25,frozen25}_s{2,3}.json`; `repro/compare_out.txt` |
| 3 | The same stack at one codec step per **4** windows (8× denser) | Bits/s vs frozen: A after A 137.31 / 136.63 vs 139.38 / 138.07; A at end 175.99 / 171.98 vs 177.18 / 176.31; B at end 189.07 / 189.95 vs 189.40 / 185.11 (**s1 +2.6%**); 5/6 lower. **Against the 1/32 cadence:** newest-area bits/s +1.0% / +4.2% (worse); B caption bits/byte 0.1267 / 0.1246 vs 0.1377 / 0.1376 (**better 2/2**); B understanding 0.179 / 0.262 vs 0.095 / 0.167 (**better 2/2**); recover exact A 0.306 / 0.299 vs 0.229 / 0.292, B 0.219 / 0.198 vs 0.188 / 0.25 (**higher 3/4**). Against frozen: recover exact lower on both areas at both seeds (vs 0.347 / 0.271); B caption 0.1267 / 0.1246 vs 0.1327 / 0.1316. 2466 / 2468 codec steps; codec time 173.2 / 171.0 s vs LM 133.0 / 132.2 s (**≈130%**, contended) | s0/s1, one codec init | D1 (critic rerun) | not rerun | `critic/d1r/res/live25_every4w_s{0,1}.json`; `d1/res/live25_s{0,1}.json` |
| 4 | High plasticity (3e-4, a codec step every 2 LM steps, EMA 0.995) trades LM bits/s (codec-dependent, item 19) for mel; timbre recovery falls (row 15). **Not step-matched**: the frozen codec stopped at 1500 codec-phase steps, the live arms got 600 more at 3e-4 | Table rows, ttc25 vs frozen25 bits/s: tones +6.6 / +4.7 / +3.4%; melody +8.1 / +4.4 / +3.2% (s0/s1/s2). Tones mel 0.4712 / 0.4693 / 0.4597 vs 0.5438 / 0.5239 / 0.53. Same coordinate rows, ttc25c vs frozen25c, [tones, melody]: s0 +4.1, +5.2; s1 +8.1, +6.3; s2 +2.5, +2.7; s3 +5.1, −0.1 (**7/8 worse**). **Summary: −0.1% to +8.1% (coordinate rows, 4 seeds); +3.2% to +8.1% (table rows, 3 seeds)** | codec retrained per seed | D3 | reproduced-weaker (claim 5); claim 2 notes | `d3/res/{ttc25,frozen25,ttc25c,frozen25c}_s{0,1}.json`; `repro/d3/res/*_s{2,3}.json`; `d3/run.py:485` |
| 5 | Plasticity is a dial, in both harnesses | **D3 cold** (5e-5, a step every 8), ttc25c vs frozen25c bits/s: +1.0 / +1.9% (s0), −0.8 / −0.7% (s2). Mel 0.4897 / 0.6189 (s0) and 0.4806 / 0.6151 (s2), between frozen and hot. **D1 hot** (3e-4, a step every 8 windows, no anchor) vs frozen: A at end +6.4% (s0), +3.7% (s2); B at end −4.1% (s0), −6.4% (s2); A mel at end 0.5456 (s0, worse) / 0.5107 (s2, better) vs 0.5319; flips 46-68% (s0) and 46-76% (s2) per act | s0 (judge), s2 (repro); D1: one codec init (`codec25.pt`) | D3, D1 | reproduced-weaker (claim 4) | `judge/d3c/res/ttc25c_cold_s0.json`; `judge/d1c/res/live25hot_s0.json`; `repro/d3/res/ttc25c_cold_s2.json`; `repro/d1/res/live25hot_s2.json` |
| 6 | Online codes with NO snapshot and NO anchor: **mixed** against the shipped live25 regime | live25free − frozen, A bits/s at end: +2.75 / +4.73 (codec-dependent, item 19). Against live25 (same seed, same codec init): A mel at end worse, 0.5758 / 0.5666 vs 0.5264 / 0.5236; but recover exact better, A 0.257 / 0.299 vs 0.229 / 0.292 and B 0.26 / 0.26 vs 0.188 / 0.25; B understanding 0.155 / 0.262 vs 0.095 / 0.167; B caption bits/byte 0.1334 / 0.1244 vs 0.1377 / 0.1376. **Confound:** live25free differs from live25 in snapshot AND anchor (`d1/run_arm.py:40-41`) | s0/s1, one codec init | D1 | not rerun | `d1/res/live25free_s{0,1}.json` |
| 7 | An EMA teacher lowers the flip rate; no LM bits/s difference (a codec-dependent unit, one seed) | Flips per 50 codec steps (nested codec, codec-only drift sweep), [tones phase, melody phase], decay 0.995 vs online: s0 0.089, 0.152 vs 0.473, 0.496; s1 0.110, 0.114 vs 0.474, 0.504. LM level, s0 only, ttc25 vs online live25: tones 111.53 vs 112.35 bits/s, melody 131.33 vs 131.42; recover exact tones 0.231 vs 0.315, melody 0.172 vs 0.188 | s0/s1 (flips), s0 (LM) | D3 | direction reproduced via flipdist on spec25 (claim 7); the per-50-step values s0/s1 re-aggregated only; LM level not rerun | `d3/res/drift_summary.txt`; `d3/res/{ttc25,live25}_s0.json` |
| 8 | FSQ drift moves each changed coordinate one level, but often more than one coordinate; the EMA does not bound cumulative drift | Max step 1 in 100% of flips at 125/250 codec steps; at 500: 98.9 / 99.7 / 98.3 / 99.1% (s0-s3). Single-coordinate share at 500: 62.9 / 63.5 / 67.8 / 66.5%. Cumulative change at 500 under 0.995: 61.7 / 66.0 / 60.5 / 54.7% | 4 seeds | D3 | reproduced (claim 7, wording caveat) | `d3/res/flipdist_s{0,1}.json`; `repro/d3/res/flipdist_s{2,3}.json` |
| 9 | Coordinate rows beat table rows on current-area bits/s: **a sample-efficiency gain at 600-1200 media LM steps** | **D1 frozen:** A after A −16.7 / −14.8 / −12.4 / −14.2%; B at end −12.4 / −11.2 / −11.3 / −11.1%. **D1 live:** −15.9 / −14.1 / −11.6 / −13.5%; −12.7 / −11.2 / −9.9 / −11.4%. **D3 frozen:** tones −12.9 / −13.2 / −12.8 / −12.4%; melody −14.2 / −15.3 / −13.2 / −11.3%. B understanding (frozen) 0.274 / 0.25 / 0.214 / 0.286 vs 0.143 / 0.155 / 0.226 / 0.214: **did not replicate** (1 of 4 new-seed readings better) | 4 seeds in each harness (D1: one codec init) | D1, D3 | D1 reproduced-weaker (claim 1); D3 reproduced (claim 2) | as rows 1 and 4; `d3/res/{frozen25,frozen25c}_s{0,1}.json` |
| 10 | Coordinate rows make the LM MORE sensitive to stale codes | LM bits/position on codes 600 LM steps stale vs current, under the 0.995 teacher. **Tones:** coordinate +10.2 / +15.1 / +13.7%, table +2.6 / +11.9 / +9.9% (s0 / s1 / s2); coordinate s3 +10.6%. **Melody:** coordinate +5.1 / +11.0 / +15.7%, table +4.6 / +4.7 / +9.2%; coordinate s3 +13.8%. Teacher range **+2.6% to +15.7%**; coordinate above table at 3/3 seeds (6/6 readings). **Online codes with table rows** (D3 live25, s0): tones +17.8%, melody +21.4% | s0/s1 (original); s2/s3 (reproduction records) | D3 | s0/s1 not rerun (critic's reading); s2/s3 *derived* | `d3/res/{ttc25c,ttc25,live25}_s*.json`; `repro/d3/res/{ttc25c_s2,ttc25c_s3,ttc25_s2}.json` (`meas[-1]`, `*_bits_stale_d4`) |
| 11 | Coordinate rows raise interference between media areas (no LM media rehearsal) | Rise of area A's bits/s after training on B. **Frozen:** table +37.80 / +38.24 / +37.32 / +40.78; lattice +53.58 / +58.91 / +42.07 / +54.64. **Live:** table +38.74 / +37.28 / +34.03 / +40.00; lattice +53.26 / +54.06 / +44.01 / +51.74. End level, lattice vs table: −7.1% to +0.1% | 4 seeds, one codec init | D1 | reproduced (claim 6) | `repro/compare_out.txt` |
| 12 | No adaptive rate beat a fixed stride on LM bits/s (alphabet-dependent, item 19); on the codec-invariant readings the same pairs tie within noise | **D3 'alloc' vs fixed**, same nested codec, table rows, [tones, melody] bits/s: s0 +10.0, +13.3%; s1 +14.3, +10.6%; s2 +3.6, +15.2%. **Nested 'alloc' with coordinate rows vs the spec fixed codec with coordinate rows** (unpaired across codec architectures, V 3264 vs 1264): s0 −2.1, +2.6%; s1 −0.5, +5.4%; s2 −1.6, +5.5%. Melody generation 1/42 vs 7/42 at s0. **D1 'bpe' − fixed 50 Hz** (both stride 1): s0/s1 −0.08, +1.17, +2.38, +9.86, +4.72, +1.97; s2 +1.22, −1.69, +5.73 (7/9 worse). **D2 router vs fixed 25 Hz**, tones mel: 0.4362 / 0.4659 vs 0.3972 / 0.4158; melody teacher-forced mel 0.5825 / 0.5885 vs 0.4425 / 0.3957. **Codec-invariant, D3 'alloc' vs fixed** (ttcMR vs ttcN25, recover exact on reconstructions after P2, s0 / s1 / s2): melody exact 0.141 / 0.141 / 0.25 vs 0.109 / 0.125 / 0.219 ('alloc' higher 3/3, by one or two clips of 64); tones exact 0.278 / 0.333 / 0.315 vs 0.343 / 0.315 / 0.361 (n = 108). D1 'bpe' is better in 2 of 9 bits/s readings (−0.08, −1.69) | 3 seeds (D3, D1; D1: one codec init, every seed loads `codec50.pt`, `d1/run_arm.py:266`); 2 (D2) | D3, D1, D2 | bits/s and mel reproduced (claim 9); codec-invariant readings *derived* | `d3/res/{ttcMR,ttcN25,ttcMRc,ttc25c}_s0.json`; `d3/res/{ttcMR,ttc25c}_s1.json`; `repro/d3/res/{ttcN25,ttcMRc}_s{1,2}.json`, `repro/d3/res/{ttcMR,ttc25c}_s2.json`; `d1/aggregate.json`; `repro/d1/res/live50{bpe,def}_s2.json`; `d2/res/{d2_s0,d2_s1,d2_fixed_s0}.json`; `repro/d2/res/d2_fixed_s1.json` |
| 13 | Codec side: 12.5 Hz costs mel; at the toy probe size, exact match alone cannot see it. **D3's nested codec with forced strides, codec-only, n = 36 (tones) / 32 (melody) probe clips; per-stride 'spec' codecs were never measured** | End of the drift sweep (teacher 0.995), positions/s, mel for s0 / s1. Tones: 'alloc' rho 0.1 22.0 / 22.8, 0.433 / 0.429; rho 0.5 16.3 / 16.9, 0.443 / 0.439; forced 50 Hz 52, 0.441 / 0.432; forced 25 Hz 26, 0.430 / 0.431; forced 12.5 Hz 13, **0.481 / 0.481**. Melody: rho 0.1 0.518 / 0.520; forced 25 Hz 0.521 / 0.531; forced 12.5 Hz **0.570 / 0.577**. Exact match at strides 1 / 2 / 4: tones s0 0.306 / 0.278 / 0.278, s1 0.306 / 0.306 / 0.278; melody s0 0.125 / 0.094 / 0.125, s1 0.094 / 0.094 / 0.125. **Applied to these, 'measured' at a tolerance of 0.05 picks stride 4 in all four cells** | s0/s1 | D3 | re-aggregated only; the stride pick is *derived* | `d3/res/drift_s{0,1}.json`; `d3/res/drift_summary.txt` |
| 14 | 'nested' at stride 2 vs 'spec' fails the per-attribute criterion | Nested vs spec (both live, table rows). Bits/s [tones, melody] (unpaired across codec architectures, V 3264 vs 1264; alphabet-dependent, item 19): s0 −2.6, −4.7%; s1 +0.8, +1.4%; s2 +3.4, −3.0%. Tones mel 0.4438 / 0.4441 / 0.4433 vs 0.4712 / 0.4693 / 0.4597. **Melody timbre recover 0.359 / 0.375 / 0.531 vs 0.500 / 0.609 / 0.578** (frozen spec: 0.641 / 0.656 / 0.625). Melody exact 0.109 / 0.125 / 0.219 vs 0.172 / 0.109 / 0.141. Tones exact 0.343 / 0.315 / 0.361 vs 0.231 / 0.259 / 0.306. Tones code entropy (s0) 7.628 vs 7.759 bits | s0 (D3); s1, s2 from reproduction records | D3 | s0 not rerun; s1/s2 *derived* | `d3/res/{ttcN25,ttc25,frozen25}_s0.json`; `d3/res/{ttc25,frozen25}_s1.json`; `repro/d3/res/{ttcN25_s1,ttcN25_s2,ttc25_s2,frozen25_s2}.json` |
| 15 | A live codec improves mel and lowers TIMBRE recovery (D3, where timbre is recorded); exact match falls in D1 (which records exact match only) and is mixed in D3 | **D3 at high plasticity, live vs frozen, after P2** (3e-4, a codec step every 2 LM steps, **not step-matched**: +600 codec steps; s0-s2 ttc25, s3 ttc25c, which shares ttc25's codec): tones timbre 0.481 / 0.556 / 0.481 / 0.509 vs 0.648 / 0.602 / 0.565 / 0.648 (**lower 4/4**); melody timbre 0.500 / 0.609 / 0.578 / 0.625 vs 0.641 / 0.656 / 0.625 / 0.625 (**lower 3/4, tie s3**); tones exact 0.231 / 0.259 / 0.306 / 0.241 vs 0.259 / 0.204 / 0.259 / 0.324 (lower 2/4, higher at s1 and s2); melody exact 0.172 / 0.109 / 0.141 / 0.156 vs 0.203 / 0.141 / 0.125 / 0.266 (lower 3/4). Kind rose s0-s2 and tied s3; count rose s0-s2 and fell s3 (0.639 vs 0.648); band fell at s2 and s3 (0.935 vs 0.963; 0.926 vs 0.944). **D3 at low plasticity** (cold: 5e-5, a step every 8), ttc25c_cold vs frozen25c: tones timbre 0.593 vs 0.648 (s0), 0.537 vs 0.565 (s2), **lower 2/2 by less**; melody timbre 0.641 vs 0.641 (s0), 0.609 vs 0.625 (s2). **D1** (one codec init): exact at end lower 7 of 8 with 1 tie (row 2). **D3 codec-only** (nested codec, 0.995, forced stride 2, 1000 codec steps): melody exact 0.312 / 0.125 → 0.094 / 0.094 while melody mel went 0.623 / 0.634 → 0.521 / 0.531; tones exact 0.222 → 0.278 (s0), 0.306 → 0.306 (s1). **D1 codec-only** (50 Hz codec, lr 5e-5, no anchor): A exact 0.292 → 0.347 after B | 4 seeds (D3 stream); 2 (D3 codec-only); one codec init (D1) | D3, D1 | reproduced-weaker (claim 5, s2); s3 *derived* | `d3/res/{ttc25,frozen25}_s{0,1}.json` (`recon_probe`); `repro/d3/res/{ttc25_s2,frozen25_s2,ttc25c_s3,frozen25_s3}.json`; `judge/d3c/res/ttc25c_cold_s0.json`; `repro/d3/res/ttc25c_cold_s2.json`; `d3/res/drift_summary.txt`; `d1/res_codec/clean_lr5e-5_noanchor.json` |
| 16 | The codec-only anchor: fewer flips; LOWER area-A recover exact after B (0.264 vs 0.347, about 1.5 SE, one seed). **D1's 50 Hz codec (`codec50.pt`), 200 area-A + 300 area-B codec steps, one seed** | After B at lr 5e-5, no anchor vs anchor w10: A mel 0.4955 vs 0.4994; A recover 0.347 vs 0.264; flips per 50 codec steps at step 500: A 0.141 vs 0.043. Floor + re-warm 3e-4 + anchor: A mel 0.4893, A recover 0.271, B mel 0.5688 (anchor alone: 0.5769). The earlier-quoted "0.506 → 0.475" is area A BEFORE B. Without control (3e-4, no anchor): 26-61% (A) and 31-58% (B) of probe frames flip per 50 codec steps | one codec seed, one codec init | D1 codec-only | not rerun | `d1/res_codec/clean_*.json`; `d1/res_codec/drift50.json`, **first config (`lr3e-4_noanchor`) only**: every later config in `drift50.json` and `drift50_b.json` is contaminated by the shared-Adam-moment bug that `d1/codec_drift.py:58-60` records (`drift50_b.json`'s conflicting w10 reading, A mel 0.4901 after B, is one of them); the invocation `codec_drift.py 1 200 300` is recorded in `results/live_codec_design_2026-09-25/workflow_result.json` |
| 17 | Persisted latents go stale | Area A latents from the end of P2 decoded by the P3 decoder: +0.063 / +0.076 mel against their own P2 decode (0.508 / 0.5456 vs 0.4453 / 0.47); +0.072 / +0.080 against a fresh P3 re-encode (0.4362 / 0.4659) | s0/s1 | D2 | not rerun | `d2/res/d2_s{0,1}.json` (`stale_A_latents_decoded_by_P3_decoder`) |
| 18 | The continuous LM interface lost to discrete codes | Tones understanding exact 0.0781 / 0.0781 vs 0.25 / 0.2344; caption bits/byte 0.2501 / 0.2329 vs 0.2059 / 0.1827. GMM gradient norm vs caption CE: at w 1.0, 9.621 vs 1.796 (P2 step 49); at the default w 0.1, 0.582 vs 1.92 (step 49), **2.951 vs 1.621 (step 99)**, 1.065 vs 1.058 (step 149) | s0/s1 | D2 | reproduced (claim 10), same seed only | `d2/res/{base,d2}_s{0,1}.json`; `judge/logs_d2_dbggrad.txt`; `judge/logs2_d2_dbggrad_w1.txt` |
| 19 | The Q-RUN-8 option (a) act works with a live codec and changing ids | windows_in_epoch revised 12991 → 12091 (s0), 12995 → 12096 (s1), 12996 → 12096 (s2), 6 acts each. All prefix and cursor assertions passed. Minted ids in consumed media positions: 82,133 / 684,759 (12.0%), 83,002 / 684,938 (12.1%), 81,081 / 684,767 (11.8%). Deferred control: 0 of 800,000 | 3 seeds | D1 | reproduced (claim 8) | `d1/res/live50{bpe,def}_s{0,1}.json`; `repro/d1/res/live50{bpe,def}_s2.json` |
| 20 | Resume is bit-exact only if nothing changes between acts | Mints and refresh only inside acts: max \|dloss\| 0.0, windows 232 = 232, revisions 4 = 4 (judge and reproduction). With mints every 16 windows between acts every 48: re-measured 231 vs 233 saved, max \|dloss\| 0.4755, not bit-identical | s0, toy (150 + 150 clips, 29 steps) | D1 | first reproduced (claim 8); second not rerun | `judge/d1c/smoke/resume_save10.json`; `repro/d1/smoke/resume_save10.json`; `critic/d1r/smoke/resume_mintbetween.json` |
| 21 | WORLD on a moving target: at 40 ms tones +0.04 to +0.06, melody +0.02 to +0.04 relative MSE; at 200 ms tones +0.01 to +0.04, melody none | D3 relative MSE vs persistence, live − frozen, s0 / s1 / s2 / s3: tones 40 ms +0.037 / +0.040 / +0.065 / +0.044, tones 200 ms +0.007 / +0.013 / +0.037 / +0.022 (**4 of 4 higher**); melody 40 ms +0.018 / +0.030 / +0.034 / +0.043, melody 200 ms −0.012 / −0.012 / −0.001 / +0.001 (none). s0 values: tones 40 ms 0.395 vs 0.433, 200 ms 0.712 vs 0.719. s3 live is ttc25c, which shares ttc25's codec. Target std, frozen 9.47 / 9.02 vs live 8.90 / 8.51 after P2 (live at P1 9.49 / 8.88): a comparison of arms, not a change over time. D1 stand-in: the target's jump at a snapshot refresh stayed within −0.0023..+0.0044 over **32 refresh acts** in 6 runs | s0-s3 (s2/s3 from the reproduction's records, *derived*; D1: one codec init) | D3, D1 | s2/s3 derived from claim 2/5 reruns | `d3/res/aggregate.txt`; `d3/res/{frozen25,ttc25}_s{0,1}.json` (`evals.after_P2.*.world`, `target_std`); `repro/d3/res/{frozen25_s2,ttc25_s2,frozen25_s3,ttc25c_s3}.json`; `d1/res/{live25,live50bpe,live50def}_s{0,1}.json` (`acts[].world_rel_*`) |
| 22 | Codec liveness did not move **toy** text | D1 live − frozen text bits/byte at end: −0.0017 / +0.0007 / +0.0066 / +0.0017 (table rows). Largest rise over P1 in any arm: +0.047 (original) and +0.023 (reproduction). **Toy text:** an order-2 Markov process over 15 symbols, with no TOK, SIG, DOM, FAB or MEM | 4 seeds, D1: one codec init | D1 (D3 text undertrained) | reproduced (claim 11) | `d1/aggregate.json`; `repro/compare_out.txt`; `d1/run_arm.py:62-63` |

**Row 14, every attribute.** Recover exact on reconstructions: nested / spec, both live, table rows, at s0 / s1 / s2. The s1 and s2 values are *derived* from the reproduction's records (`repro/d3/res/ttcN25_s{1,2}.json`, `repro/d3/res/ttc25_s2.json`, `d3/res/ttc25_s1.json`).

| Family | Attribute | s0 | s1 | s2 | Nested lower at |
|---|---|---|---|---|---|
| tones | kind | 0.704 / 0.648 | 0.778 / 0.667 | 0.833 / 0.750 | 0/3 |
| tones | band | 0.898 / 0.954 | 0.935 / 0.935 | 0.954 / 0.935 | 1/3 |
| tones | timbre | 0.491 / 0.481 | 0.444 / 0.556 | 0.537 / 0.481 | 1/3 |
| tones | count | 0.593 / 0.583 | 0.713 / 0.667 | 0.778 / 0.713 | 0/3 |
| tones | exact | 0.343 / 0.231 | 0.315 / 0.259 | 0.361 / 0.306 | 0/3 |
| melody | contour | 0.422 / 0.297 | 0.344 / 0.234 | 0.422 / 0.281 | 0/3 |
| melody | register | 0.984 / 0.969 | 0.781 / 0.922 | 0.906 / 0.922 | 2/3 |
| melody | timbre | 0.359 / 0.500 | 0.375 / 0.609 | 0.531 / 0.578 | **3/3** |
| melody | exact | 0.109 / 0.172 | 0.125 / 0.109 | 0.219 / 0.141 | 1/3 |

**Floors.** Understanding and generation exact sit near the floor in every design (tones generation 1-8%). Held-out combinations are near the floor too: 0 to 0.5 on 6-12 prompts, mostly 0. At n = 108 tones clips one binomial standard error of a single 0.3 rate is about 0.044, and a comparison of two rates has a larger one (about 0.062 unpaired; 0.057 at the prototypes' n = 64 melody clips for a single rate). That is why `AUD_PROBE_N` is 400 and sized on the paired difference (§6.3).

### 0b.3 What stays fixed, and why each item is absolutely necessary

| Thing | Why it is absolutely necessary |
|---|---|
| One codec state per training window: the codes, the LM rows that read them, and WORLD's target | Otherwise one id means two sounds inside one gradient step. The codec itself trains on underneath; this is consistency, not a freeze. |
| One segmentation and one tokenizing snapshot held between acts, recorded as of the last text segmentation (text) and the last act (media) | A resume must rebuild exactly what the uninterrupted run held: the new R-RESUME-AT-ACT invariant (item 14), which replaces Q-RUN-10's declared replay. How long it is held is a lever (`AUD_REFRESH_EVERY`, `TOK_RETOK_EVERY`), not a constant. |
| The analysis grid: `DATA_AUD_SR` 8000, n_fft 512, hop 160 = **50 frames/s** | A base time unit is as necessary as bytes are for text: **the grid is the audio byte**. Every stride, clip length, position count, rate and WORLD horizon is counted in it, and it shapes every codec tensor (257 bins, the frame axis). Its VALUE is a per-run lever, EXACT across a resume. The learned front end is the `'wave'` arm. |
| `AUD_RATE_TOL` (0.05 recover-exact points) | **A decision threshold, not a rate.** Any rule that chooses a rate from data must say what "no worse" means. The rate itself is measured. The threshold sits on a codec-invariant reading, like the tree's other Gate thresholds; S5 reports its sensitivity. |
| The FSQ lattice `AUD_LEVELS` 8,5,5,5 (id k = lattice point k) | It has no parameters. It is the media address space that coordinate rows, SIG signatures and merges index. A change goes through the versioned-block handover arm, never silently. |
| The candidate stride set {1,2,4} (and, under 'nested', the 80 ms segment) | Under 'nested' they are id blocks and decoder schedules, i.e. tensor extents; under 'spec' each is one candidate codec's shape. The set is EXACT across a resume; widening it by appending a block (e.g. stride 8) needs a containment rule kind that `CKPT.check_geometry` does not have, ruled when a stride 8 is built. Which stride is used is measured (item 3). |
| Tensor widths and preallocated extents | Checkpoints load by shape, and the tree has no growth operator. Slots are MAY_WIDEN. |
| Append-only expansions of minted ids (text `id2bytes`; media merges under 'bpe') | A minted row must keep its meaning, and a resume must rebuild the tail at the recorded revision. |
| The act runs only at a flush with an empty batch, splicing after the unit under the cursor | Otherwise windows are replayed or skipped, one batch spans two segmentations, or a partly consumed clip is re-cut. |
| No LM likelihood gradient into the codec through STE or its targets | This is not a freeze: the codec trains all run on its own loss. It bans the one coupling with measured collapse. Bounded couplings are arms. |
| Measurement contracts: held-out and probe clips and seeds, `frozen_rng`, analytic inverses | Drift, flips, forgetting and recover exact are defined only against inputs that do not move. |

**Not necessary, yet still defaults pending measurement.** Each has a named measurement that can move it.

| Default | Why it is not necessary | What decides it |
|---|---|---|
| Griffin-Lim, 32 iterations | A fixed stage where a learned one exists (a Vocos-style iSTFT head [S]). It may contribute to the timbre loss. | S8/GPU learned-vocoder arm, judged on recover exact of decoded audio |
| `AUD_ARCH='spec'` | 'nested' removes the per-stride codecs | S3 criterion at 2 seeds, per-attribute recover exact included (item 4) |
| One stride per run (`'measured'`) rather than per segment | 'alloc' and 'bpe' adapt per segment | S5 rate sweep on 2-4 s clips (item 3) |
| The stride chosen on the readiness areas only and used for every later area | A new area's tail is unconsumed at its arrival, just as media is at readiness, so it could be re-measured and re-laid | the `'measured_arrival'` arm (under 'nested'), in S5's rate sweep |
| Readiness on the first media area only, at least 750 codec steps | D1's measured codec had 4000 steps and a generic pre-training set | S3's recipe check (the readiness-only cell against D1 live25); the `'+generic'` arm (item 2) |
| Probe cadence (every 500 windows in readiness, at every act after it) and `AUD_PROBE_N` 400 | A measurement budget set by CPU cost, not a property of the codec | the GPU bench's probe row (§12) |
| The fixed-stride control, `AUD_RATE_STRIDE` 2 | It is a control arm and the provisional compose layout, not a choice | stays a control |
| Holding the snapshot between acts (`AUD_CODES='snapshot'`, held 1000-2000 windows, ≤ 4000 under a guard hold) | `'jit_ema'` is fully continuous | S5 plasticity matrix |
| A shift stamp at every refreshing act once media is consumed, and with it a FAB growth pause of about 20-27% of windows (`FAB_COOLDOWN` 400, `FAB_GROW` on) | A stamp only when probe flips since the last stamp exceed `AUD_SHIFT_FLIPS` may protect FAB and DOM as well, at a smaller pause | S5 (iii) over `AUD_SHIFT_STAMP`, reading the blackout share from `fab.cooldown_windows` |
| The silence pad at a stride that does not divide a clip's frames (2 frames per 1 s clip at stride 4) | Clip lengths chosen as whole 80 ms segments would need no pad | S5's 2 s and 4 s clip arms (whole segments) need none; `aud.rate.pad_frac` reports the pad share on every area |
| Live cadence 1/32, floor 5e-5, anchor 10, rehearsal 0.5 | They are measured values, not constraints | S3 codec-only and S5 plasticity matrices |
| `AUD_REWARM` 0 | Off only until shown harmless | S3 matrix on per-attribute recover exact |
| Fixed clip length per family (R9) | A synthetic-data convenience; real audio varies | S5 2 s / 4 s clip arms; real areas |
| `LM_CTX` 128 positions (5.12 s at 25 Hz) | Its span in seconds moves with the chosen rate | reported as `lm.media.ctx_seconds`; a width change is a new run |
| Guard thresholds (`AUD_CEIL_DROP` as the uncalibrated count-only fallback, `AUD_CEIL_HOLD_WINDOWS`, `AUD_READY_*`, `AUD_HALF_LIFE_WARN`, `AUD_SHIFT_FLIPS`; `TARGET_COLLAPSE_FRAC` 0.5, a module constant, §10) | Hand-set numbers on measured readings | each reports its firings; S3 calibrates the readiness floor and the ceiling drop threshold per family |

### 0b.4 Other learned or hand-fixed things in the tree

Source: `map/notes.txt` and the map in the workflow output. Tree facts are cited in the map.

| Thing | Today | Disposition |
|---|---|---|
| Text segmentation within a run | Frozen in effect at `RUN_EPOCHS=1`: `due.retok` only increments `retok_pending` (loop.py:2208-2230), and every retok ends in `tok.due_dropped` | Made live by the S0b act (item 13); shipped by the S0b rule (§13) |
| Minted text rows | About 600 per 20k-window run are stranded (arithmetic); their head rows are softmax negatives until first use | Reach the stream at the next act that carries TOK's retok Due (≤ `TOK_RETOK_EVERY` windows; an AUD-only act does not re-segment text, item 13). New reading `tok.mint_wait_windows` (windows from mint to first use) |
| `TOK_RETOK_EVERY=0` | Cannot mean what its former help claimed ("leaves already-emitted ids alone forever", removed 2026-09-24): the roll re-segments at the current vocabulary (Q-RUN-8) | Made true: at a roll, and at every act without a TOK Due, `TOK_RETOK_EVERY=0` keeps the view of the last segmentation (items 13-14); S0b rewrites the help |
| `TOK_PROBATION_USES` | 0: probation off, whatever the appearances (`tok/api.py:150-151`) | Stays an arm; S0b's known answers 10-11 arm it so that ids retire and are reinstated between acts |
| OPT LR horizon | Fixed at build from the epoch-0 length (Q-OPT-5, which refused re-projection twice over); the residual is reported | `OPT.revise_horizon(opt, st, *, run_windows)` at each act that changes the epoch length, LR-continuous, under a Q-OPT-5 reopening ruling (Q-OPT-10) that answers both of Q-OPT-5's grounds (§13 S0b); `OPT_HORIZON_REVISE` True only under that ruling |
| SIG signature width | Fixed from build-time `bytes_per_token` | Kept. S0b reports bpt across acts; a width re-derive (with DOM re-slicing) is ruled on if it moves > 5% (§16) |
| MEM stored contexts | Not remapped at a re-segmentation (memory/api.py:1953); the archive found 82.3% stale after one growth step | A root-passed `remap` in `MEM.maintain` (a signature move) |
| Per-token levels: MEM surprise gate 0.3, CAP stall band, DOM competence, FAB regression z-test | Their operating points shift when segmentation or the codec alphabet changes | FAB: the shift stamp at every act that moves the text view, and at refreshing acts once media is consumed (item 16). CAP/DOM: bits per build-time token from the root. MEM: a surprise rescaled to a build-time token under a Q-MEM ruling, text only (item 16) |
| `world_proj` | Born zero, no gradient at `WORLD_FEEDBACK` False | Stays an off arm pending Q-WORLD-10's GPU test |
| SIG InfoNCE floor skip (K = 8 assumed kinds) | A self-releasing conditional stop | Stays; it is the template for the codec's recon-rise re-warm arm |
| Position-denominated horizons (`WORLD_HORIZON`, `MEM_KEY_WIN`, `LM_CTX`) | In tokens or positions | Media horizons move to U.SECONDS (§10); the media span of `LM_CTX` becomes a reading |
| `CAP_TARGETS` off; `CAP_PIN_WINDOWS` 20000 | Cannot lift inside a 20k run | Outside this proposal; flagged for the CAP owner |
| `TOK_FREEZE_AT`, `TOK_MODE` fixed/bytes, `SIG_MODE` bigram, `MEM_KEY_SRC` frozen, `FAB_GROW` / `DOM_MANAGE` False | Arms, off | Stay arms |
| Architecture widths EXACT | Necessary as built | Stay |

**The S0b plan for these, in order:**
1. The act and `revise_epoch_length`.
2. Segment-at-view (and its cache rule), the run-global rev, the BPE-dropout stream's state in `vocab_state`, the replay record, the clock restore (with the epoch0 row's skip) and the resume from the last act; the text-only continuation test first.
3. The TOK splice helper.
4. `OPT.revise_horizon` under Q-OPT-10.
5. The MEM remap.
6. Per-byte levels for DOM (CAP's is specified and inert until P4), MEM's rescaled surprise (with `Vocabulary.decode` / `blen` taken out of the deferred list), and the shift stamp at every act that moves the text view.
7. The owed paired measurement (3 paired seeds, prequential bits per byte), before `TOK_RETOK_EVERY` 3000 ships as a firing default.

### 0b.5 Defaults, ON and OFF

**New, ON by default:**
- the live codec (`AUD_FREEZE_AT` 0);
- the readiness Gate on per-family recover exact, never before `AUD_READY_MIN` windows after the codec's birth;
- `AUD_RATE_MODE='measured'`;
- `AUD_ARCH='spec'` with candidate codecs during readiness;
- `AUD_CODES='snapshot'`, refreshed at every act and at least every `AUD_REFRESH_EVERY` 2000;
- `AUD_TRAIN_EVERY` 32 and `AUD_READY_EVERY` 4;
- the codec group (`'codec.<s*>'` at the default, `'codec'` otherwise) on AUD's own schedule: a cosine from `AUD_CODEC_LR` 1e-3 to `AUD_CODEC_LR_MIN_FRAC` 0.05 over 750 codec steps (`AUD_READY_MIN` / `AUD_READY_EVERY`), then the floor; D1's AdamW betas (0.8, 0.99) and weight decay 0.01 (OPT levers, read when OPT builds the group) and D1's gradient-norm clip 1.0 (`AUD_CODEC_GRAD_CLIP`, applied by `AUD.loss_terms`);
- the anchor (`AUD_ANCHOR_W` 10);
- codec rehearsal (`AUD_REHEARSE` 0.5);
- the ceiling guard: `'hold'` on families whose drop threshold S3 has calibrated, counting only on the others;
- the hidden-freeze warning (stated by `AUD.horizon_audit` beside `RUN.cadence_audit`; never a refusal) and `aud.moved`;
- clip references and `DATA.render`;
- `LM_MEDIA_ROWS='coord'`;
- `SIG_MEDIA_ROWS='coord'`;
- `DATA_MEDIA_REHEARSE` 1/3;
- WORLD on the tokenizing latent with horizons in seconds;
- the S0b act, after its measurement;
- resume from the last act (R-RESUME-AT-ACT: the view, the replay record, the clock restore);
- `OPT_HORIZON_REVISE` True, under Q-OPT-10;
- shift stamps (to FAB and OPT; to CAP when `CAP.observe` is rowed at P4) at every act that moves the text view, and at every refreshing act once media has been consumed;
- re-keys: `DOM.on_retokenize` at every act that moves the text view (any `SIG_MODE`); `DOM.rekey` at refresh acts once media is consumed, at `SIG_MODE=learned`; MEM's remap;
- per-byte levels to CAP and DOM, and MEM's rescaled surprise for text.

**New, OFF (arms):**
- the frozen codec (`AUD_FREEZE_AT > 0`);
- `AUD_CODES='jit_ema'` (with `AUD_EMA_HALF_LIFE` and `AUD_SHIFT_FLIPS`);
- the flip-thresholded and the 'always' stamp under 'snapshot' (`AUD_SHIFT_STAMP` 'flips' / 'always', S5 iii);
- `AUD_REWARM` > 0;
- `AUD_RECON_LOSS='multires'`; `AUD_ANCHOR_W` 0 (a measured arm) and `AUD_ANCHOR_SCOPE='old'`;
- `AUD_CEIL_ACTION='count'`;
- `AUD_READY_AREAS='+generic'` (D1's pre-training recipe);
- `AUD_ARCH` 'nested' / 'wave' / 'dmel';
- `AUD_RATE_MODE` 'fixed' / 'alloc' / 'bpe' / 'router' / 'measured_arrival';
- `AUD_LM_IO='continuous'`;
- `AUD_LM_GRAD` 'rep' / 'input';
- `LM_MEDIA_ROWS='table'`;
- `SIG_MEDIA_ROWS='table'`;
- `DATA_MEDIA_GEOMETRY='windows'`;
- `WORLD_MEDIA_INPUT='student'`, `WORLD_MEDIA_TARGET='student'`;
- `DATA_MEDIA_REHEARSE` 0.

**Existing levers whose effective behaviour changes:**
- **`TOK_RETOK_EVERY` 3000.** Same value, new meaning. From S0b on it FIRES mid-epoch at `RUN_EPOCHS=1` (once the S0b rule ships it), so every default run changes past window 3000. Only an act carrying TOK's Due re-segments text. At 0, a roll and every act keep the view of the last segmentation, which changes multi-epoch runs at 0. Its help text is rewritten.
- **`TOK_GROW_EVERY` 200.** Same cadence. Its mints now reach the stream at the next act that carries TOK's retok Due, instead of never.
- **`OPT_LR_SHIFT_WARM` 0 (unchanged).** Therefore **neither the media-arrival stamp nor any act stamp re-warms the LM**. R13's re-warm is inert at default; the stamps act through FAB's cooldown only.
- **FAB cooldown.** Now stamped at every act that moves the text view, and at every refreshing act once media has been consumed, not only at epoch rolls. Growth is blacked out for about 20-27% of windows (arithmetic, item 16), and S0b / S5 report the share. 0b.3 lists this as not necessary; S5 (iii) decides.
- **`DOM_TOKC_DECAY` 0.5.** Applied at every act that moves the text view, not only at rolls, and no longer applied a second time by a resumed child's first roll. The Partition is re-keyed at refresh acts once media is consumed (at `SIG_MODE=learned`).
- **MEM.** Contexts are remapped and the rekey snapshot retaken at every act that moves the text view.
- **`MEM_WRITE_GATE`.** It receives a surprise rescaled to a build-time token (Q-MEM-14 rewrites its help). **The CAP stall band and DOM competence** receive bits per build-time token. Their calibrated operating points are therefore unchanged at build.
- **The OPT horizon.** Revised at each act that changes the epoch length, under Q-OPT-10.
- **Resume.** Continues at the cursor from the last act's state, bit-exact; periodic and SIGUSR1 saves wait for an optimizer-step boundary (§11). This closes Q-RUN-10's epoch replay (tests/test_resume_clock.py C9 is rewritten).
- **tok counters.** `tok.retok_deferred` and `tok.retok_satisfied_by_roll` become ABSENT, with reason "S0b: the act runs mid-epoch; nothing is deferred to a roll". `tok.due_dropped` must read 0. New: `tok.retok_mid_epoch`, `tok.relay`, `tok.retok_at_finish`, `tok.segment_resume` (one per resume rebuild, ABSENT on a fresh run); the act's no-op refusals count in `tok.retok_noop`.
- **Held-out bits/byte and generation.** Segment at the view of the last text segmentation, not at the current table, once their call sites exist (`EVAL.holdout_probe` P5, `EVAL.generate` P6; neither is rowed today).
- **`AUD_TRAIN_EVERY`.** From R12's 4 for the whole run to 32 after readiness. R12's 4 survives as `AUD_READY_EVERY`.
- **`AUD_FREEZE_AT`.** 3000 → 0; still read through `AUD.freeze_at` for the control arm.
- **`AUD_CROP_S`.** 0.5 → 0.64.
- **`OPT_CODEC_LR`** (the draft's) becomes **`AUD_CODEC_LR`**, 1e-3 unchanged: AUD writes the codec group's lr (Q-OPT-11).
- **`AUD_PROBE_EVERY`.** New at 500 during readiness. After readiness the probe is read at every act under 'snapshot', and on this period under `'jit_ema'`.
- **`WORLD_MEDIA_HORIZONS` '1,5' frames** becomes `WORLD_MEDIA_HORIZONS_S` '0.04,0.2'.

### 0b.6 Sentences of §0-§16 this revision supersedes

**§0:**
- R1: "At the freeze, AUD.encode writes code ids into the placeholder positions in place: no window boundary moves, nothing is re-segmented. A media LM phase before the freeze stays refused." Also its diagram cell "freeze: encode in place" and "OPT shift stamp (R13)".
- R1: "`F = clip_s(family) × derive.frames_per_second(...)` known from levers at compose" and "`run_windows`, `windows_in_epoch` and OPT's horizon are right from window 0". Under 'measured', F is provisional until the readiness act re-lays the tail at the chosen stride, and every act that changes lengths revises `windows_in_epoch` and OPT's horizon.
- R3, except its accessor: "**R3 — AUD_FREEZE_AT IS AN int WITH UNIT U.Windows, DEFAULT 3000** … plus an AUD startup refusal when `freeze_at >= planned run windows` while a media phase is scheduled." The default is 0 and the refusal goes; the `AUD.freeze_at(aud) -> Windows` accessor STAYS, because the frozen-codec control arm reads the lever through it (K9).
- R6: "AUD (17 levers, all amendments, 11 entry points with `freeze_at`)". This is recounted in Contract accounting.
- R12: "`AUD_TRAIN_EVERY` (U.Windows, default 4) sets the codec cadence" (now 32 after readiness), and "media off / codec phase / media phase" (the bench rows are now those of §12).
- R7: "recorded at the S1 base commit into a checked-in fixture". S0b now lands before S1, so the fixture is recorded at the **S0b** base commit, before anything this proposal builds.
- R11 and §3.3 are amended, not replaced: "those consumers receive per-modality values normalised by that modality's running baseline". The root first converts each value to a segmentation-invariant unit (bits per build-time token for text, bits per clip-second for media; item 16), and R11's running baseline then normalises it.
- R13: "The freeze stamps an OPT shift exactly as an epoch roll does, so the existing OPT_LR_SHIFT_WARM re-warm applies; the codec's own parameters are a separate OPT group ('codec', OPT_CODEC_LR) that retires at the freeze." The group never retires, except in the frozen-codec control arm; at `OPT_LR_SHIFT_WARM` 0 nothing re-warms.
- R14: "`derive.media_rows` takes the lever's string form (`media_rows('8,5,5,5') == 1002`, refusing a malformed one)". It now takes six arguments, `(enabled, arch, levels, strides, rate_mode, bpe_slots)`, and returns 0 when AUD is off (0b.1 item 11). It still parses the levels string and refuses a malformed one.

**§1 and §2:**
- §1 decisions table: "AUD and VID packages train their codecs in-loop in a codec phase, then freeze and version them."
- §2: "trained inside the loop during a codec phase and then **frozen and versioned**", and "a **temporal media head over the frozen codec's continuous latents**".

**§3:**
- §3 diagram: "AUD.encode (frozen codec, epoch roll)"; "WORLD.media_terms(latents, valid, context=h@BEGIN)   <- continuous, frozen target"; "+ AUD.loss_terms(raw clips)          (codec phase only, OPT group 'codec')".
- §3.1: the media half of "Everything persisted stores ABSOLUTE ids: DOM histograms, eval samples, checkpoints, and later MEM entries."
- §3.2: "`spine/units.py` gains unit LABELS only (`HZ`, `FRAMES`), not clock kinds." It gains three labels: **HZ** (kept, for `DATA_AUD_SR`, which the draft labels Hz), **FRAMES**, and **SAMPLES** (`AUD_NFFT`, `AUD_HOP`). Still no clock kind.

**§4:**
- §4.1 rows:
  - "AUD_STRIDE | 2 | latent stride; frame rate = sr/(hop*stride) = **25 Hz**";
  - "AUD_CROP_S | 0.5";
  - "AUD_FREEZE_AT | 3000 … end of the codec phase";
  - "AUD_VERSION | 1 | EXACT geometry; a retrained codec is a new version".
- §4.1: "Entry points (10)".
- §4.1 entry points: "`startup_refusals(aud, *, phase_plan, freeze_at)` | Refuses a media LM phase that starts before the freeze" and "`freeze(aud, codec, *, clock)` | A Gate: runs the collapse and quiet checks, then freezes and hashes the weights into the version".
- §4.1 counters: "`aud.freeze`, a Gate."
- §4.2: "VID_FREEZE_AT | 3000", "VID_VERSION | 1", and "Same shape and the same 10 entry points."

**§5:**
- Move #6: "Codec parameters in their own group, stepped only before the freeze".
- "New entry points: 137 -> **153** at the audio stages, and **163** with VID." and "| S3 | AUD x10 |".
- "`DATA.media_batch(dat, areas, *, n, crop_s, rng)` -> raw clips for the codec phase". It now serves readiness and live codec training.
- LOOP rows: "`AUD.encode` at the epoch roll;", "flush-stage `AUD.loss_terms` in the codec phase;", and "an A-stage `AUD.freeze` on Cadences key `aud.freeze`;". The control arm's freeze is a one-shot Windows comparison, not a Cadences key (§6.2 step 9).
- SIG: "the unit is a byte for text and a code for media". A media unit is now embedded through lattice coordinates.
- Wires: "`LM.d_aud_rows <- AUD.levels`: `prod(levels) + 2` if enabled, else 0." The coupling's sources are now (`AUD.enabled`, `AUD.arch`, `AUD.levels`, `AUD.strides`, `AUD.rate_mode`, `AUD.bpe_slots`) (0b.1 item 11).

**§6, whole**, including:
- "### 6.1 AUD default: 'spec' at 25 Hz";
- "### 6.2 Training and freezing";
- "At the freeze Gate: …";
- "The LM loss NEVER back-propagates into the codec. … AQM's "old codes must stay decodable" all argue against it";
- "A codec never changes silently under a trained LM.";
- "| Joint codec+LM backprop | Collapse evidence above; token meaning drifts under the LM |".

**§7 and §8:**
- §7: "The codec phase runs during the text phases." Readiness runs during the text phases, and the codec never stops.
- §8: "Sample exactly F = clip_s x fps codes under the audio mask. The `mode_fn` grammar keeps END masked until F codes, then forces END." This now holds with fps at the measured stride. Under 'alloc'/'bpe', END is duration-governed for known-length families.

**§10:**
- Item 2: "A causal GRU (WORLD_MEDIA_HID 128) over the frozen codec's 64-d latents at 25 Hz. It predicts horizons `WORLD_MEDIA_HORIZONS='1,5'` frames (40 ms and 200 ms)."
- Item 2: "There is no VICReg on this path: the target is frozen and cannot collapse, so the historic WORLD_W folding defect cannot recur here."

**§11:**
- "| aud.enabled, aud.arch, aud.sr, aud.hop, aud.stride, aud.levels, aud.d, aud.version | EXACT | off / — |"
- "Changing levels, hop, stride, sr, arch or version against a checkpoint that has them is refused: it is a new token space."
- "The codec's frozen weights are saved, so old codes stay decodable (AQM)."
- "| lm.media_rows.aud (and .vid) | EXACT once > 0 | 0 |". It becomes MAY_WIDEN, absent 0. The rows are a preallocated extent (0b.3: "Slots are MAY_WIDEN"), so a birth at an add-a-modality resume (0 → 1002) and the 'bpe' slots (1002 → 1514) are widenings, not new token spaces. A narrowing is still refused.

**§12:**
- "**Codec phase:** … Only for AUD_FREEZE_AT windows."
- "| Audio, 25 Hz | 0.2 | 5.12 s |". The row now reads at the measured stride.
- "A captioned 1 s clip at 25 Hz is 36.6 ids against 9.6 for its caption, a 3.8x multiplier" and "1 h of audio = 703 windows at 25 Hz …". These figures hold at 25 Hz only; at the measured stride they are readings (`lm.media.ctx_seconds`, `bench_summary`'s `media_seconds_per_s`).

**§13:**
- S3: "collapse/quiet/freeze Gates" and "**CPU acceptance: mel < 0.6, codes_used >= 300, probe ceiling >= 30% within 5 CPU-minutes on aud/tones**". The probe ceiling becomes per-family recover exact, and acceptance adds §13's rows.
- S5: "**CPU regression band at 8k windows, 25 Hz**". It now reads "at the measured stride".
- S8: "9. Codec version handover." Now only for a lattice or architecture change.

**§14:**
- "**Joint codec + LM training:** REPA-E, STE collapse, AQM." Narrowed by item 18.
- "The default frame rate is 25 Hz, not 50". The rate is now measured per run.

**§16:**
- Row 1: "R-OPT fresh group and freeze shift stamp".
- Row 2: "| 2 | 25 or 50 Hz | Build both behind one lever, default 25 |".
- Row 11: "| 11 | Codec retraining on real data | Versioned codec handover (S8 i): new id block, nearest-row init | Frozen ids must never change meaning inside a run |".

**Appendix A:**
- "**Step 0 (new, first):** capture the baseline fixture (R7)." The fixture is captured at the **S0b** base commit, before S1 (as R7 above).
- "2. src/spine/units.py: unit LABELS HZ = 'Hz' and FRAMES = 'frames' (and CODES = 'codes')." The labels are HZ, FRAMES and SAMPLES. CODES is not declared: no lever in §7 carries it, and codes-used thresholds are U.COUNT.
- "media_rows(levels) -> prod(levels) + 2." and the known-answer row "| media_rows([8,5,5,5]) | 1002 |". They are replaced by the six-argument form and its known answers (0b.1 item 11).
- "frames_per_second(sr, hop, stride) -> float. Refuses a non-integer frame rate." and the row "| frames_per_second(8000, 150, 1) | refuses (53.33) |". It refuses only a grid that is not a whole number of frames per second (sr / hop); a per-stride rate may be fractional. Known answers: `frames_per_second(8000, 160, 4)` == 12.5; `frames_per_second(8000, 150, 1)` refuses, because 8000 / 150 is not a whole number.

**Appendix B:**
- S3: "(b) 25 Hz against 50 Hz." and "Decision: the default arch and frame rate for S4."
- S4/S5: "(a) 25 against 50 Hz at 20k windows". Both are replaced by §13's S5 rate sweep.
- S8: "(h) Codec version handover (new block with nearest-row init) on a real-audio area." The live codec adapts to a real-audio area in place (§16 row 21); the handover is kept only for a lattice or architecture change.

---

## 6. Codecs (replaces §6)

### 6.1 AUD default: 'spec' spectral FSQ on the 50 frames/s grid, stride measured per run

- **Features.** STFT log-magnitude, n_fft 512, hop 160 at `DATA_AUD_SR` 8000: 50 frames/s, 20 ms per frame. This grid is the audio unit (0b.3).
- **Encoder for stride s** (s ∈ `AUD_STRIDES`):
  - Conv1d(257→256, k3), ELU, Conv1d(256→256, k3), ELU;
  - then log2(s) stride-2 Conv1d layers (none at s = 1);
  - then a 1×1 to 64-d.
  The result is a 64-d latent at 50 / s per second, which is also WORLD's media observation.
- **Quantiser.** GroupNorm, then FSQ 8,5,5,5 with the iFSQ activation and the entropy bonus (`AUD_ENT_W` 1.0). Id k is lattice point k.
- **Decoder.** It mirrors the encoder with transposed stride-2 layers and predicts log-magnitude.
- **Waveform.** Griffin-Lim 32 (fixed; the learned vocoder is an arm, 0b.3).
- **Loss.** L1 on log-magnitude + 2 × L1 on magnitude + the entropy bonus. After readiness, the anchor hinge is added (6.2). `AUD_RECON_LOSS='multires'` (harmonic / multi-resolution spectral terms) is the S3 arm opened by 0b.1 item 8.
- **Crops.** `AUD_CROP_S` 0.64 s, a whole number of 80 ms segments at every candidate stride.
- **Positions per clip.** F = ceil(frames / s), with a silence pad at the clip's end and the decoder's output trimmed to the clip's samples (0b.1 item 3). A 1 s clip is 13 positions at stride 4.
- **Under `'measured'`**, readiness trains one such codec per candidate stride (1, 2, 4), and the Gate keeps one (6.3). Under `'fixed'` only the codec at `AUD_RATE_STRIDE` is built.

Prior archive, measured before this revision (the first draft's §6.1 table; CPU, 1 thread, 250-260 s of training each). It stands:

| Codec | Params | Steps | mel held-out | Codes used | Bits/code | Probe exact on reconstructions |
|---|---|---|---|---|---|---|
| spec 50 Hz (Route 3) | 724k | 5,614 | 0.463 | 630 | 7.46 | 40.3% |
| spec 25 Hz (judge) | 1.2M | 4,161 | 0.525 | 559 | 7.60 | 44.4% |
| SEANet wave 25 Hz | 0.65M | 1,687 | 1.03 | 109 | 5.65 | 57.8% (different probe) |

**Arms.**
- `'nested'` (D3):
  - one encoder with no strided layer;
  - each 80 ms segment (`AUD_SEG_FRAMES` 4) is coded at a stride s by s-average pooling of the latent;
  - id = block(s) × 1000 + code;
  - the decoder receives each quantised vector repeated s times;
  - rate dropout trains one decoder for any stride map.
  Measured: 0b.2 row 14.
- `'wave'`: SEANet, a GPU arm.
- `'dmel'` (S8): training-free log-mel binning (dMel [V]). It has no weights, but its bins are set by hand.

**Pre-declared switch.** `AUD_ARCH` becomes `'nested'` only if S3 shows, at both of 2 seeds, that nested at every candidate stride is no worse than the matching 'spec' codec by more than 2 SE of the paired difference (both read on the same probe clips) on every one of:
- mel;
- codes used;
- recover exact for EVERY attribute of every family, and exact match;

and better than 'spec' beyond that margin on at least one of them. Strict ≥ comparisons are not used: at a paired SE of about 0.02-0.03 and dozens of comparisons, noise alone would fail two equal codecs and make the switch inert.

The seeds measured so far are lower on melody timbre at 3/3, by 0.141 / 0.234 / 0.047 at n = 64 melody clips, where 2 unpaired SE is about 0.18; only s1 exceeds it. S3 re-measures at n = 400.

### 6.2 Training, for the whole run

1. **Readiness phase** (the codec's birth, window 0 on a fresh run, to at least `AUD_READY_MIN` windows after it).
   - `AUD.loss_terms(aud, codec, wave, *, opt, anchor=None)` runs on `DATA.media_batch` crops of `AUD_READY_AREAS` every `AUD_READY_EVERY` (4) windows, on an A-stage row evaluated per window as `SIG.train_step`'s is, so `Cadences.due` fires once per period at any `OPT_BATCH_WINDOWS` (at a flush row it fires at most once per flush: about 187 readiness steps at `OPT_BATCH_WINDOWS` 16). It steps its own optimiser group (the Q-OPT-6 pattern), clipping its gradient norm at `AUD_CODEC_GRAD_CLIP` 1.0 and writing its lr from AUD's own schedule before each step (Q-OPT-11; 0b.1 item 6). OPT never writes the codec group's lr.
   - Optimiser groups, AdamW with `OPT_CODEC_BETA1` 0.8, `OPT_CODEC_BETA2` 0.99 and `OPT_CODEC_WEIGHT_DECAY` 0.01 (D1's values), built by `OPT.build`:
     - under `'spec'` + `'measured'`, one group per candidate: `'codec.1'`, `'codec.2'`, `'codec.4'`;
     - otherwise, one group `'codec'`.
     The kept candidate's group keeps its key `'codec.<s*>'` after the Gate (no re-key; R-OPT restores it live beside the retired losers), and "the codec group" below means it.
   - Each group follows a cosine from `AUD_CODEC_LR` 1e-3 to `AUD_CODEC_LR_MIN_FRAC` × peak (5e-5) over `derive.codec_steps_from_windows(AUD_READY_MIN, AUD_READY_EVERY)` = 750 of its own steps, then holds the floor.
   - Every `AUD_PROBE_EVERY` (500) windows, per candidate, `AUD.ready` reads the probe on its A-stage row (Cadences key `aud.probe`): per-attribute recover exact on the `AUD_PROBE_N` (400) fixed held-out probe clips, plus mel, `codes_used` and `rms_ratio`. It then tests the Gate.
2. **The readiness Gate** (0b.1 item 2), inside `AUD.ready`, tested from `AUD_READY_MIN` windows after the codec's birth on. When it fires:
   1. the rate is chosen (6.3);
   2. the root retires the losing candidates' groups through `OPT.retire_group(opt, st, *, key)` (A-stage row). R13's retirement now applies only to discarded candidates, never to a codec in use;
   3. the snapshot is copied from the kept codec (`aud.version` step 1);
   4. each attribute's readiness value is recorded, in AUD's state, as the ceiling-guard baseline;
   5. if s\* ≠ `AUD_RATE_STRIDE`, a relay Due is raised for the next act (S4).
3. **Between the Gate and the first media window.** The kept codec trains at the live cadence on `DATA.media_batch` crops of the readiness areas, so it never trains on nothing.
4. **Live phase.**
   - One codec step every `AUD_TRAIN_EVERY` (32) windows, at the floor.
   - Each step is 16 crops: (1 − `AUD_REHEARSE`) from the current media areas and `AUD_REHEARSE` (0.5) from earlier ones. From the first media window on, crops are drawn from clips the stream has consumed, rendered from their references by `DATA.render`.
   - The loss adds the **anchor hinge**: `AUD_ANCHOR_W` (10) × mean over positions of Σ_dims relu(|b − q_snap| − `AUD_ANCHOR_MARGIN`)². Here b is the codec's bounded pre-rounding FSQ value and q_snap is the **snapshot's** lattice point for the same crop.
   - The hinge covers all crops (`AUD_ANCHOR_SCOPE` 'all'). The codec moves freely inside an FSQ cell and is pushed back only before a code would flip. This is D1's `codec_loss` (`d1/codec.py:124-143`).
5. **At every act** after readiness, under 'snapshot' (S0b's act; AUD's own Due raises one at least every `AUD_REFRESH_EVERY` 2000 windows). The per-act work is one entry point, **`AUD.refresh(aud, codec, *, recover_fn, probe_waves, clock) -> RefreshReport`** (+1, S3), on the act's X-stage row. The root passes `DATA.recover` and the probe clips' waves, rendered once by `DATA.render` (the set is fixed; AUD may not import DATA, O10); the truth is `recover_fn` on each rendered wave. In order:
   - The probe is read on the live codec: per-attribute recover exact per arrived area, flips since the last refresh, cumulative flips since readiness, and `aud.moved`.
   - The ceiling guard decides against the baselines AUD holds (0b.1 item 8): hold, or proceed.
   - Unless held, the snapshot ← the codec and the version step increments. The report says whether it refreshed and, while a refresh is withheld, `hold_expires_at` (0b.1 item 8).
   - The root stamps the shift (FAB and OPT) as the report's `stamp` says (§7). If the snapshot was refreshed, the root then runs `DOM.rekey` with the composed callable at `SIG_MODE=learned` if media has been consumed (from S4), reads `sig.media_drift`, and points WORLD's target at the new snapshot.
   - Placeholders of the unconsumed tail are rewritten lazily: at window cut, a clip record whose codes predate the snapshot is re-encoded in place (D1's `jit_refresh`). The new codes are written into the Segmentation (item 14's replay record reads them).
6. **A new media area's arrival.**
   - Its consumed clips join the codec's pool.
   - The OPT/FAB shift is stamped. FAB's cooldown opens; at `OPT_LR_SHIFT_WARM` 0 the LM is not re-warmed.
   - The codec re-warm is the arm `AUD_REWARM` > 0 (0b.1 item 7), applied by AUD's own schedule.
7. **Encoding.**
   - `AUD.encode(aud, codec, wave, *, which='snapshot', stride_map=None)` writes into R1's placeholders, with the silence pad and trim of 0b.1 item 3 where a stride does not divide the clip's frames.
   - Under `'alloc'` it follows the clip's recorded stride map. Under `'bpe'` codes are held from the act.
8. **The `'jit_ema'` arm.**
   - A teacher takes one EMA update per codec step. D3's measured teacher is 0.995 per codec step at one step per 2 D3 windows: a half-life of about 138 codec steps, i.e. about 277 D3 windows (`d3/res/drift_summary.txt`: "500 codec steps = 1000 LM windows at AUD_TRAIN_EVERY=2").
   - The arm matches it **in codec steps**, since the flip-rate reduction it bought is per codec step: `AUD_EMA_HALF_LIFE` 4416 windows = 138 codec steps at the default 1/32 (553 windows in the 1/4 cell), converted by `derive.ema_decay_from_half_life`. The window-matched cell (277 windows, about 8.7 codec steps at 1/32, about 0.923 per step) is the other cell. Both are unmeasured at 1/32.
   - Codes are cut at every window cut by the teacher, and written in place into the Segmentation.
   - The anchor targets the teacher's lattice point. **That retargeting is unmeasured**: D1's anchor targeted a snapshot.
   - There is no refresh event, so after readiness `AUD.refresh` runs on an A-stage row on Cadences key `aud.probe` (`AUD_PROBE_EVERY` 500), with no snapshot copy. It reads the probe, the flips, `aud.moved` and the guard's count, and it decides the `AUD_SHIFT_FLIPS` shift stamp. Tying it to acts would leave the arm silent, because under `'jit_ema'` AUD raises no act.
9. **The frozen-codec control arm** (`AUD_FREEZE_AT > 0`). The freeze is a one-shot Windows comparison in the root, `AUD.freeze_at(aud) > 0 and clock.step >= AUD.freeze_at(aud)`, that fires only while the codec group is not in OptState's retired set, which is checkpointed, so a resume after the freeze does not fire it again. It is not a Cadences key, which would fire again at every multiple of the period. When it fires, the root stops calling `AUD.loss_terms`, retires the codec's group through `OPT.retire_group` (R13's retirement, kept for this arm only), and raises an act Due. That act's `AUD.refresh` copies the final codec into the snapshot and counts `aud.freeze`, the arm's did-it-fire counter (AUD reads `AUD_FREEZE_AT` itself). A freeze before the Gate retires every candidate's group, and the Gate's own snapshot copy stands in for the refresh (`AUD.ready` then counts `aud.freeze`). After that, `aud.moved` reads 0 by design, and it is not warned.
10. **No LM next-token gradient reaches the codec.** Codes are integers, and WORLD's target is stop-gradient.

### 6.3 Choosing the rate: `AUD_RATE_MODE='measured'`

- **Readings.** At the Gate, for each candidate stride s, the root passes `DATA.recover` and the rendered probe waves (§6.2 step 5) into `AUD.ready`. AUD may not import DATA (O10). For each readiness area, attribute a and exact match, the reading R_s[a] is recover exact on the reconstructions of the `AUD_PROBE_N` probe clips.
- **Rule.** s\* is the largest s such that R_s[a] ≥ R_1[a] − `AUD_RATE_TOL` for every area, every attribute and exact match. s = 1 always qualifies.
- **Probe size, on the paired difference.** R_s and R_1 are read on the **same** probe clips, so the rule tests a paired difference, whose SE is about sqrt(d / n) for a discordant fraction d (clips where the two strides disagree on that attribute). At n = 400 it is about 0.022 at d = 0.2 and 0.032 at d = 0.4; unpaired it would be about 0.032 near a rate of 0.3. So 0.05 is 1.5-2.3 SE per cell, not "more than 2 SE" as the first revision said. By default the rule reads 1 area, the first media area (tones: 4 attributes plus exact match, 5 cells); under `'+generic'` or `'measured_arrival'` it reads 2 areas (up to 10 cells). Any cell out rejects a coarser stride, so noise biases the rule toward stride 1. At SE 0.032 one cell falls out with probability about 6%, so 5 cells together fall out about 26% of the time and 10 cells about 45%, if they were independent (correlated cells do better). Therefore:
  - the Gate reports the realised paired SE per cell (from the measured d) and the expected false-"out" rate over its cells, `aud.rate.false_out_est`;
  - S3's known-answer test includes a noise fixture: two stipulated-equal candidates read on 400 simulated clips, whose selection rate of the finer stride is reported against that estimate;
  - `AUD_PROBE_N` is revisited at S3 if the realised SE exceeds `AUD_RATE_TOL` / 2 (an SE of 0.025 needs about 650 clips at d = 0.4), within the probe budget of §12.
  At the prototypes' n = 108 a single rate had an SE of about 0.044, and at n = 64 about 0.057.
- **Reported.**
  - `aud.rate.stride`;
  - `aud.rate.pad_frac`, the share of positions that cover pad frames (0b.1 item 3);
  - `aud.rate.cand.<s>.<area>.<attr>` and its paired SE;
  - mel and positions/s per candidate;
  - the dropped candidates' final readings.
- **Layout** (built and tested at S4, with `TOK.splice`'s media re-interleave).
  - Compose lays media out provisionally at `AUD_RATE_STRIDE`. If s\* differs, the next act re-lays the unconsumed media tail at s\*, at the view of the last segmentation (no minted id enters with it), or at the current view when the act also carries TOK's Due (item 13).
  - The act asserts that no media position has been consumed (`aud.rate.media_consumed_at_gate == 0`).
  - It revises windows_in_epoch and the OPT horizon, and it retakes R4's data_plan media reading.
  - Every clip is laid out at F = ceil(frames / s\*) positions (0b.1 item 3). Known answer: a 1 s aud/tones clip re-laid at stride 4 takes 13 positions and decodes to 8000 samples.
  - If s\* equals the provisional stride, `aud.rate.relay` is ABSENT, with reason "chosen stride equals the provisional layout".
  - If readiness is late, the Gate is forced at the last flush before the first media window, so the relay still precedes all media.
- **Honesty.** This rule was **not prototyped**. On the toy codec-side readings of D3's **nested codec forced to each stride** (n = 36 / 32), exact match alone would have picked 12.5 Hz in all four (area, seed) cells, where tones mel was +12% (0b.2 row 13). The rate-distortion of separately trained 'spec' candidates, which is what 'measured' uses by default, is unmeasured. So:
  - S3 ships a known-answer test of the selection, with the noise fixture (§13);
  - S5 compares 'measured' against every fixed stride on the codec-invariant primaries;
  - §16 asks whether the rule needs a mel term.
- **Arms.**
  - `'fixed'`: the control.
  - `'alloc'`: per segment, the coarsest stride whose snapshot reconstruction error is within (1 + `AUD_ALLOC_RHO`) of the finest. It needs 'nested' and the act. Codec-side at rho 0.1 it matched forced-25 Hz mel on tones with 22.0 / 22.8 positions/s against 26; on melody it used 26.5 / 26.5, more than forced 25 Hz.
  - `'bpe'`: TOK's mint mechanism over lattice ids. It needs the act, and codes are held from the act.
  - `'router'`: H-Net, continuous route only.
  - `'measured_arrival'`: a re-measure at each new area's arrival (0b.1 item 3), under 'nested' only.
- **Generation.** Under 'measured' and 'fixed', F = ceil(clip_s × 50 / s\*) codes (with the pad of 0b.1 item 3), then forced END, and the decoded wave is trimmed to clip_s. Under 'alloc' and 'bpe', END is duration-governed for known-length families and predicted with a clip-length guard otherwise. Measured in D1: predicted END left 32-62 of 64-108 BPE clips short at s0/s1, and 36-74 at s2 (`d1/res/live50bpe_s{0,1}.json`, `repro/d1/res/live50bpe_s2.json`, `final.*.generate_*.short`); duration-governed END left 0 short.

### 6.4 Drift: what it costs and what bounds it

- **Churn is intrinsic.** Without control at 3e-4, 26-61% (area A) and 31-58% (area B) of probe frames flip per 50 codec steps in D1's codec-only run (its **50 Hz codec**, no anchor, 200 + 300 steps, one seed; `d1/res_codec/drift50.json`), and 47-50% in D3's nested codec (codec-only, online codes).
- **At the default regime** (D1 live25, s0/s1; 6.0-15.3% with the reproduction's s2/s3), 6.9-15.3% of probe frames change per refresh (2000 windows ≈ 62 codec steps). The rate is highest at the first refresh (13.8% / 15.3% on A) and falls to 6.9% / 7.1% by the fourth. Cumulative change since the codec phase at window 8000 is 24.8% / 28.5% (A) and 23.8% / 26.0% (B).
- **At 8× the codec steps** (the critic's 1/4 cadence), cumulative change on A reached 26.9% / 26.1%, against 24.8% / 28.5% at 1/32: no systematic increase. At the owner's shape, a 20k-window run has about 530 live codec steps at the default cadence (arithmetic); the drift there is unmeasured, and `aud.flip_cum` reports it.
- **Under an EMA teacher** (the arm), short-horizon flips drop to 9-15%, but cumulative change still reaches 55-66% after 500 codec steps (0b.2 row 8).
- **Drift is local per coordinate but often multi-coordinate.** At 500 steps, 32-37% of flipped codes change two or more FSQ digits.
- **Stale ids never reach the LM or eval.** Codes are rewritten at refresh and at cut, and nothing persists them.
- **What remains is the LM re-learning a moving target.**
  - D3 ttc25c (high plasticity, coordinate rows): tones bits/position rose +7.4% / +4.7% from the end of P1 to the end of P2, against +0.1% / +0.2% frozen.
  - D1 at the default regime: lower bits/s in 24/24, no consistent cost or gain on the LM-side codec-invariant readings, and a consistent codec-ceiling cost (recover exact lower in 7 of 8 with 1 tie; 0b.2 rows 1-2).
- **Old-code decodability (AQM), which the frozen codec guaranteed, is replaced by the codec-BWT row**, read on mel AND per-attribute recover exact. Area A from after A to the end, D1, one codec init, the two regimes differing in snapshot AND anchor:
  - live25 (snapshot + anchor), 4 seeds: mel +0.0103 / +0.0000 / +0.0153 / +0.0082; recover exact −0.049 / −0.020 / −0.062 / −0.035;
  - live25free (online codes, no anchor), 2 seeds: mel +0.025 / +0.024; recover exact −0.021 / +0.007.
  - The two readings disagree: the shipped regime forgets less on mel and more on recover exact, the acceptance metric. S5's {anchor 0, 10} × {snapshot, jit_ema} cells separate the two causes.
  - Timbre recovery falls in D3, and exact match on earlier areas falls in D1 (0b.2 rows 2 and 15). That is the guard's job (0b.1 item 8).

### 6.5 Couplings between the codec and the LM or WORLD

| Coupling | Default | Status |
|---|---|---|
| Codec on its own loss, concurrent with the LM | ON | 0b.1 items 1 and 6 |
| LM likelihood into the codec through STE or its targets | never a default; the `'full'` form exists only on the continuous route | collapse evidence: GEAR [V]; D2's tgtgrad arm, understanding 0.016 vs 0.078 (1 seed) |
| DreamerV3-style bounded predictability term (weight 0.1, 1 nat free bits) | `AUD_LM_GRAD='rep'`, off | unmeasured; needs the collapse gauges and a VICReg term on the codec latent |
| LM gradient through codec outputs used as LM inputs | `AUD_LM_GRAD='input'`, continuous route only, off | D2: no task gain, PR up (1 seed) |
| WORLD gradient into the codec | none | the WORLD target is stop-gradient (§10) |

### 6.6 Rejected and retained options (replaces the old §6.3)

| Option | Status |
|---|---|
| Frozen codec | Not a default. Kept as the `AUD_FREEZE_AT > 0` control arm. |
| Train to readiness, then freeze | Rejected: the old design with a better Gate. |
| `'nested'` as the default | Rejected for now: it fails its pre-declared per-attribute criterion (melody timbre, 3/3 seeds). Kept as the arm S3 decides. |
| Just-in-time EMA-teacher codes as the default | An arm (`'jit_ema'`). Its measured value is flip rate, not LM bits. |
| Per-segment adaptive rate ('alloc', 'bpe', 'router') as the default | Arms. Each lost or tied a fixed stride at toy scale, on LM bits/s (alphabet-dependent across rate arms, item 19) or, for D2's router, on mel, and the D3 pairs tie within noise on the codec-invariant readings; S5 decides on 2-4 s clips. |
| An absolute readiness threshold of 0.30 | Rejected: it was set on a different probe. On recover exact, D3's codecs and D1's melody reading fall below it, and D1's tones reading passes (0b.1 item 2). |
| Re-warm on by default | An arm, off until S3 shows recover exact does not fall beyond 2 paired SE. |
| A flat 0.05 ceiling hold | Rejected: it would fire in the measured regime (item 8). The threshold is calibrated per family at S3. |
| "A resume is an act"; "mint only at acts"; a dummy prefix on resume; replaying the chain of acts | Rejected (0b.1 item 14). |
| A 22nd wire for the lattice | Rejected on the wire budget (2 left after VID); the lattice is build-time structure, passed as `LM.build_model(media_lattice=)` like `open_store(key_dim=)`. |
| Flattened RVQ 4×256 | Rejected: 200 tokens/s, and no reconstruction gain from levels 2-4. |
| Plain FSQ | Rejected: collapsed in 3 of 5 runs. iFSQ plus the entropy bonus is used instead. |
| LM likelihood into the codec through STE or its targets | Rejected as a default (6.5). |
| Continuous media interface (D2) | The S8 arm `AUD_LM_IO='continuous'`. It lost on LM-side readings at 2 seeds, and at the default GMM weight its gradient exceeds caption CE at step 99. |

---

## 7. Lever deltas (amends the §4.1 AUD table, §7's DATA table, and the named levers of other packages)

**Reading the "Gate" column.** For a lever read only by an arm, or inert until something is calibrated, the column names the did-it-fire surface. It is ABSENT, with the reason shown, when the arm is off, so an armed-and-silent lever is never read as a zero.

**Reading the "Unit" column.** Every unit is a label or Clock kind declared in `spine/units.py` (`wire.py`'s `_known_units` refuses any other on a wire). Enums are U.NAME with choices and booleans U.FLAG, as elsewhere in the tree. A loss weight in 0..1 is U.FRACTION (`fraction 0..1`, as FAB's `*_w` levers are, none of which exceeds 1). A weight that can exceed 1 is U.COUNT with a declared domain, the tree's one precedent being `SIG_VAR_WEIGHT` 5.0 (`sig/levers.py:445`); so `AUD_ANCHOR_W` 10 is U.COUNT, domain (0, 100). Three labels are declared in units.py (counted in Contract accounting): **U.HZ** (kept from the draft's §3.2, for `DATA_AUD_SR`), **U.FRAMES** (analysis frames on the 50 frames/s grid) and **U.SAMPLES** (waveform samples).

**Who reads which lever (K4).** `AUD_READY_AREAS` is in `AUD.startup_refusals`' LEVERS READ (it resolves '' against the `phase_plan` argument and refuses a named area that is not a media area); the root resolves it the same way and passes the areas to `DATA.media_batch`. `AUD_BATCH`, `AUD_CROP_S` and `AUD_REHEARSE` are in `AUD.loss_terms`' LEVERS READ (it checks that the batch it receives has that shape and split); the root passes `n`, `crop_s` and the split to DATA as row arguments, as R6 did for `n` and `crop_s`. `AUD_PROBE_N` is in `AUD.ready`'s and `AUD.refresh`'s LEVERS READ (each checks the number of probe waves it receives). `AUD_CODEC_LR`, `AUD_CODEC_LR_MIN_FRAC`, `AUD_CODEC_GRAD_CLIP`, `AUD_READY_MIN` and `AUD_READY_EVERY` (the cosine horizon), `AUD_REWARM`, `AUD_REWARM_WINDOWS` and `AUD_TRAIN_EVERY` (the re-warm's step conversion), and `AUD_ANCHOR_W`, `AUD_ANCHOR_MARGIN` and `AUD_ANCHOR_SCOPE` (the hinge) are in `AUD.loss_terms`' LEVERS READ (it owns the codec schedule, Q-OPT-11, and the loss). `AUD_HALF_LIFE_WARN`, `AUD_EMA_HALF_LIFE`, `AUD_REWARM_WINDOWS`, `AUD_REFRESH_EVERY` and `AUD_CEIL_HOLD_WINDOWS` are in `AUD.horizon_audit`'s. `AUD_CEIL_*`, `AUD_SHIFT_STAMP`, `AUD_SHIFT_FLIPS` and `AUD_FREEZE_AT` are in `AUD.refresh`'s (`AUD_FREEZE_AT` in `AUD.ready`'s too, for a freeze before the Gate). `AUD.refresh` returns the stamp decision as RefreshReport's `stamp`: 'after_media' (stamp once media has been consumed) for a refreshed snapshot under 'refresh', and for one refreshed past `AUD_SHIFT_FLIPS` under 'flips' (under 'jit_ema', a probe reading past it); 'now' at every act under 'always'; otherwise 'no'. Before readiness no `AUD.refresh` runs and an act stamps only when the text view moved. `AUD_REFRESH_EVERY`, `AUD_CODES`, `AUD_HOP` and `AUD_READY_MIN` are also in `AUD.startup_refusals`' (item 5's refusal of 0 under 'snapshot'; item 3's clip-length refusal; item 2's media-phase refusal). AUD never reads a DATA lever (O10).

**AUD**

| Lever | Default (old → new) | Unit | Meaning | Gate if arm-only |
|---|---|---|---|---|
| AUD_ENABLED | False | U.FLAG | null codec when off | — |
| AUD_ARCH | 'spec' (unchanged) | U.NAME: 'spec' \| 'nested' \| 'wave' \| 'dmel' | codec architecture | `aud.nested.*` / `aud.wave.*` ABSENT unless selected |
| AUD_NFFT | new 512 | U.SAMPLES | STFT window; sets the 257 bins of every codec tensor; EXACT. It was a constant in the draft and is declared because the grid is a per-run lever (0b.3) | — |
| AUD_HOP | 160 | U.SAMPLES | STFT hop; with DATA_AUD_SR it sets the 50 frames/s grid; EXACT | — |
| ~~AUD_STRIDE~~ | 2 → removed | — | replaced by AUD_STRIDES and AUD_RATE_STRIDE | — |
| AUD_STRIDES | new '1,2,4' | U.NAME (a comma list; derive parses it to U.FRAMES per position) | candidates for 'measured'; id blocks under 'nested'; EXACT | — |
| AUD_SEG_FRAMES | new 4 | U.FRAMES (80 ms) | the segment of 'nested' / 'alloc' | `aud.seg.*` ABSENT, reason "AUD_ARCH='spec' and AUD_RATE_MODE!='alloc'" |
| AUD_RATE_MODE | new **'measured'** | U.NAME: 'measured' \| 'fixed' \| 'alloc' \| 'bpe' \| 'router' (continuous only) \| 'measured_arrival' ('nested' only) | how the rate is set; 'alloc' and 'bpe' refused until S0b exists | `aud.rate.arrival.*` ABSENT unless 'measured_arrival' |
| AUD_RATE_STRIDE | new 2 | U.FRAMES per position | the stride under 'fixed'; the provisional compose layout under 'measured' | — (read in the default) |
| AUD_RATE_TOL | new 0.05 | U.FRACTION (recover-exact points) | the 'measured' decision threshold (0b.3) | — |
| AUD_ALLOC_RHO | new 0.1 | U.FRACTION (relative reconstruction error) | 'alloc' tolerance | `aud.alloc.calls` ABSENT, reason "AUD_RATE_MODE!='alloc'" |
| AUD_BPE_BURST / MIN_PAIR / MAX_FRAMES / SLOTS / TALLY_DECAY | new 32 / 50 / 16 / 512 / 0.0 | U.COUNT / U.COUNT / U.FRAMES / U.SLOTS / U.FRACTION | 'bpe' arm; a longer candidate is skipped and never aborts the burst | `aud.bpe.*` ABSENT, reason "AUD_RATE_MODE!='bpe'" |
| AUD_LEVELS, AUD_D, AUD_HID, AUD_ENT_W, AUD_BATCH | unchanged | as the draft | | — |
| AUD_RECON_LOSS | new 'logmag' | U.NAME: 'logmag' \| 'multires' | 'multires' = the harmonic / multi-resolution arm | `aud.recon.multires` ABSENT unless selected |
| AUD_CROP_S | 0.5 → **0.64** | U.SECONDS | a whole number of 80 ms segments | — |
| AUD_FREEZE_AT | 3000 → **0 (never)** | U.Windows, read through `AUD.freeze_at` | > 0 = the frozen-codec control arm (§6.2 step 9) | `aud.freeze` ABSENT at 0, reason "AUD_FREEZE_AT=0: the codec never stops" |
| AUD_READY_MIN | new 3000 | U.Windows, counted from the codec's birth (`aud.born_at`) | the Gate's first test is the first probe reading at or after it, and a media LM phase must start after that test's flush; the codec schedule's horizon, converted to codec steps by derive | — |
| AUD_READY_AREAS | new '' | U.NAME (a comma list of area names) | '' = the first media area in DATA_PHASE_SCHED; '+generic' adds D1's generic pre-training set (arm) | `aud.ready.generic` ABSENT unless '+generic' |
| AUD_READY_MARGIN | new 0.05 | U.FRACTION | family floor = the S3-calibrated plateau − margin | `aud.ready.by_floor` ABSENT, reason "no family calibrated (S3)", until one is |
| AUD_READY_PLATEAU / AUD_READY_PATIENCE | new 0.02 / 3 | U.FRACTION / U.COUNT (readings) | the plateau rule (a rise of at most 0.02, or of 2 paired SE where larger) for uncalibrated families, and for a later area's ceiling baseline | `aud.ready.by_plateau` PRESENT-and-0 once every family is calibrated |
| AUD_READY_EVERY | new 4 | U.Windows | codec cadence before readiness (R12's costed value) | — |
| AUD_TRAIN_EVERY | 4 → **32** | U.Windows | codec cadence after readiness (D1's measured cadence) | — |
| AUD_REFRESH_EVERY | new 2000 | U.Windows | AUD's own act Due (D1's measured cadence): the longest snapshot hold outside a ceiling-guard hold (4000 with one); every act refreshes unless the guard withholds it. 0 is refused at startup under 'snapshot' (item 5); under 'jit_ema' the period reads 0 (DISARMED, item 9) | `aud.refresh.*` ABSENT under 'jit_ema', reason "AUD_CODES='jit_ema': no refresh event" |
| AUD_CODES | new 'snapshot' | U.NAME: 'snapshot' \| 'jit_ema' | how codes are cut | — |
| AUD_EMA_HALF_LIFE | new **4416** | U.Windows | teacher half-life under 'jit_ema' = D3's 138 codec steps at 1/32; derive converts it to a per-step decay | `aud.teacher.*` ABSENT, reason "AUD_CODES='snapshot'" |
| AUD_SHIFT_STAMP | new 'refresh' | U.NAME: 'refresh' \| 'flips' \| 'always' | which acts stamp a shift under 'snapshot': 'refresh' = an act that moves the text view, and a refreshing or re-laying act once media is consumed (item 16); 'flips' = a refreshing act only past `AUD_SHIFT_FLIPS`; 'always' = every act from readiness on, before media included. 'flips' and 'always' are S5 (iii) arms | — (read in the default); inert under 'jit_ema', where `aud.shift.stamp` is ABSENT, reason "AUD_CODES='jit_ema': AUD_SHIFT_FLIPS decides" |
| AUD_SHIFT_FLIPS | new 0.25 | U.FRACTION | shift-stamp threshold on probe flips since the last stamp: under 'jit_ema', and under 'snapshot' at `AUD_SHIFT_STAMP='flips'`; hand-set | `aud.shift.by_flips` ABSENT unless `AUD_SHIFT_STAMP='flips'` or `AUD_CODES='jit_ema'` |
| AUD_HALF_LIFE_WARN | new 0.25 | U.FRACTION of run_windows | hidden-freeze warning, stated by `AUD.horizon_audit` at startup; never a refusal | — |
| AUD_ANCHOR_W / MARGIN / SCOPE | new 10 / 0.25 / 'all' | U.COUNT, domain (0, 100) (the `SIG_VAR_WEIGHT` precedent) / U.FRACTION (of one lattice level) / U.NAME: 'all' \| 'old' | hinge to the tokenizing codec's lattice point; W 0 is a measured arm; 'old' is unmeasured | `aud.anchor.*` ABSENT at W 0 |
| AUD_REHEARSE | new 0.5 | U.FRACTION | share of each live codec batch from earlier consumed areas | `aud.rehearse.drawn` PRESENT-and-0 until a second area arrives |
| AUD_CODEC_LR | 1e-3 (the draft's `OPT_CODEC_LR`, renamed) | U.FRACTION | peak of the codec group(s); AUD writes the group's lr (Q-OPT-11) | — |
| AUD_CODEC_LR_MIN_FRAC | new 0.05 | U.FRACTION, domain (0, 1]: 0 is refused, because a zero floor stops the codec after the cosine, a freeze by configuration | the codec group's floor, as a fraction of the peak | — |
| AUD_CODEC_GRAD_CLIP | new 1.0 | U.FRACTION (the `OPT_GRAD_CLIP` precedent) | the codec group's gradient-norm clip, applied by `AUD.loss_terms` before each step: D1's (`d1/run_arm.py:412`); `OPT_GRAD_CLIP` clips the base group only | — |
| AUD_REWARM / AUD_REWARM_WINDOWS | new **0.0** / **9600** | U.FRACTION of AUD_CODEC_LR / U.Windows | re-warm at a media-area arrival, cosine back to the floor; arm 0.3 over 300 codec steps at 1/32 (D1's measured span) | `aud.rewarm` ABSENT, reason "AUD_REWARM=0 (off until S3)" |
| AUD_CEIL_DROP | new 0.05 | U.FRACTION | the uncalibrated fallback: counts only. A calibrated family uses its S3 threshold (measured drop + 2 paired SE) | `aud.ceiling.hold` ABSENT, reason "family drop threshold not calibrated (S3)", until calibrated; ABSENT under 'jit_ema' |
| AUD_CEIL_ACTION | new 'hold' | U.NAME: 'hold' \| 'count' | the guard's action on a calibrated family | as AUD_CEIL_DROP |
| AUD_CEIL_HOLD_WINDOWS | new 2000 | U.Windows | windows after the first withheld refresh at which the root raises an act Due (a one-shot comparison against RefreshReport's `hold_expires_at`) and the refresh proceeds with a warning; the longest hold is `AUD_REFRESH_EVERY` + this = 4000 | as AUD_CEIL_DROP |
| AUD_PROBE_EVERY / AUD_PROBE_N | new **500** / 400 | U.Windows / U.COUNT (clips per area) | probe cadence during readiness (`AUD.ready`), and after it under `'jit_ema'` (`AUD.refresh`); under 'snapshot' the probe is read at every act after readiness. Probe size, reviewed at S3 against the paired SE | — |
| AUD_LM_IO | new 'codes' | U.NAME: 'codes' \| 'continuous' | 'continuous' = D2's S8 route | `lm.media.gmm_*` ABSENT |
| AUD_LM_GRAD | new 'none' | U.NAME: 'none' \| 'rep' \| 'input' (continuous only) | bounded LM → codec couplings | `aud.lm_grad.*` ABSENT |
| AUD_COLLAPSE_MIN, AUD_QUIET_MIN, AUD_GL_ITERS, AUD_LM_W | unchanged | as the draft | | — |
| ~~AUD_VERSION~~ | EXACT 1 → removed | — | `aud.version` is a reading | — |

**Other packages**

| Lever | Default (old → new) | Unit | Meaning | Gate if arm-only |
|---|---|---|---|---|
| ~~OPT_CODEC_LR~~ | the draft's 1e-3 → renamed `AUD_CODEC_LR` | — | AUD owns the codec schedule (Q-OPT-11); the group never retires except at the readiness Gate (losers) and in the frozen control, through `OPT.retire_group` | — |
| OPT_CODEC_BETA1 / OPT_CODEC_BETA2 | new 0.8 / 0.99 | U.FRACTION | the codec group's AdamW betas: D1's measured values (`d1/codec.py:162`) | — |
| OPT_CODEC_WEIGHT_DECAY | new 0.01 | U.FRACTION | the codec group's AdamW weight decay: D1's (torch's default); the LM keeps `OPT_WEIGHT_DECAY` 0.0 | — |
| OPT_HORIZON_REVISE | new True | U.FLAG | `OPT.revise_horizon` at each act that changes the epoch length, LR-continuous, under Q-OPT-10. When `opt.build.cycles_fitted > 1` (an `OPT_LR_WAVELENGTH` shorter than the run), where "the remaining cosine" is undefined, revision is inert, not refused, and the horizon stays as built. The shipped `OPT_LR_RESTARTS` True with `OPT_LR_WAVELENGTH` 0 (one wavelength = the whole run) fits one cycle, so revision is live at the defaults | `opt.horizon.revisions` PRESENT-and-0 until an act; ABSENT, reason "cycles_fitted > 1", when inert |
| OPT_LR_SHIFT_WARM | 0 (unchanged) | U.Steps | **so no stamp re-warms the LM** | — |
| LM_MEDIA_ROWS | new **'coord'** | U.NAME: 'coord' \| 'table' | 'table' = §3's free rows | — |
| LM_MEDIA_GMM_W | new 0.1 | U.FRACTION | GMM head (continuous only) | `lm.media.gmm_grad_ratio` ABSENT |
| LM_MEDIA_MASK | True (unchanged) | U.FLAG | under 'nested', only the active stride block | — |
| SIG_MEDIA_ROWS | new 'coord' | U.NAME: 'coord' \| 'table' | how SIG 'typed' embeds a media unit | `sig.media.*` ABSENT when media is off |
| DATA_MEDIA_REHEARSE | new **1/3** | U.FRACTION | share of media windows from earlier media areas; 1/3 is the share D2 and D3 measured (0b.1 item 12) | `data.media.rehearsed` PRESENT-and-0 in the first media phase |
| DATA_MEDIA_GEOMETRY | new 'inline' | U.NAME: 'inline' \| 'windows' | 'windows' = D2's arm | `data.media.windows.*` ABSENT |
| DATA_AUD_SR | 8000 (the draft's, unchanged) | U.HZ | the one sample-rate lever (R8); with `AUD_HOP` it sets the 50 frames/s grid; EXACT | — |
| DATA_MEDIA_CLIP_S | per family (unchanged) | U.SECONDS | must be a whole number of 20 ms frames, so positions per clip are exact (0b.1 item 3); refused by `AUD.startup_refusals` from the clip lengths the root passes (O10); S5 adds 2 s and 4 s arms | — |
| WORLD_MEDIA_HORIZONS '1,5' (frames) → WORLD_MEDIA_HORIZONS_S | **'0.04,0.2'** | U.SECONDS | converted through derive at the chosen rate, rounded to whole latent frames (≥ 1); the realised horizon is a reading | — |
| WORLD_MEDIA_TARGET / WORLD_MEDIA_INPUT | new 'tokenizer' / 'tokenizer' | U.NAME: 'tokenizer' \| 'student' | the codec state that cut the window's codes; 'student' arms | `world.media.student` ABSENT |
| TOK_RETOK_EVERY | 3000 (unchanged value) | U.Windows | now fires mid-epoch; only an act carrying this Due re-segments text; 0 = never re-segment in-run, and rolls and acts keep the last view. Help text rewritten at S0b | — |
| VID_* (S7) | VID_FREEZE_AT 3000 → 0; VID_VERSION removed; VID_STRIDE → VID_STRIDES / VID_RATE_STRIDE; VID_RATE_MODE 'measured' over the temporal stride; the rest of AUD's new levers mirrored where they apply | as AUD | the same revision at S7; counted as an upper bound in Contract accounting | as AUD |

## 10. WORLD deltas

- **Target.**
  - `WORLD.media_terms` predicts the **tokenizing codec's** 64-d pre-quantisation latent, under stop-gradient: the snapshot by default, the teacher under `'jit_ema'` (`WORLD_MEDIA_TARGET='tokenizer'`).
  - The input is the same latent (`WORLD_MEDIA_INPUT='tokenizer'`), so the LM and WORLD read one codec state per window.
  - The student-input and student-target forms (D3's) are arms.
  - At each refresh act the target changes with the snapshot. The D1 stand-in measured the target's jump at a refresh within −0.0023..+0.0044 relative MSE over 32 refresh acts in 6 runs.
- **Rate.** WORLD reads the latent at the run's chosen stride. Under 'alloc' and 'bpe' it reads the uniform latent at `AUD_RATE_STRIDE`: tokens are the LM's units, frames are WORLD's.
- **Horizons** are declared in U.SECONDS: `WORLD_MEDIA_HORIZONS_S` '0.04,0.2'. units.py has SECONDS and no millisecond label.
  - `derive.latent_frames_from_seconds(s, fps)` (new, 0b.1 item 9) converts them at the chosen rate: the nearest whole latent frame, halves rounding up, with a minimum of 1.
  - The realised horizon is the reading `world.media.horizon_s`. At 12.5 Hz, 0.04 s realises as 0.08 s, and the reading says so.
  - They never move with the LM-side token rate.
  - `WORLD.media_terms` is a new entry point (S6), so it takes the rate as an argument (`fps=`) without a signature move.
- **No VICReg on this path.** The reason changes: WORLD's gradient never reaches the codec, and the codec's reconstruction, entropy bonus and anchor keep the target informative.
  - Gauges `aud.target_std` and `aud.target_pr` are armed. A separate counter, `aud.target_collapse` (PRESENT-and-0 while armed), fires when either falls below half its value at readiness: a named constant `TARGET_COLLAPSE_FRAC` 0.5 in `aud/api.py`, hand-set, reported, and listed in 0b.3 as not necessary. `aud.collapse` keeps its one meaning, codes used per batch below `AUD_COLLAPSE_MIN`.
  - VICReg stays on WORLD's existing path, with `collapse_w` and `predict_w` kept as two separate weights (world/api.py:429-434).
  - Any future joint-gradient arm needs a VICReg term on the codec latent.
- **Measured** (0b.2 row 21).
  - D3, relative MSE against persistence, live − frozen at s0 / s1 / s2 / s3 (s2/s3 from the reproduction's records): tones 40 ms +0.037 / +0.040 / +0.065 / +0.044, 200 ms +0.007 / +0.013 / +0.037 / +0.022; melody 40 ms +0.018 / +0.030 / +0.034 / +0.043, 200 ms −0.012 / −0.012 / −0.001 / +0.001. At s0/s1, tones 40 ms reads 0.395 / 0.354 frozen vs 0.433 / 0.393 live.
  - Target std did not collapse: frozen 9.47 / 9.02 vs live 8.90 / 8.51 after P2 (live at P1 9.49 / 8.88), a comparison of arms, not a change over time.
  - So a moving target costs relative MSE at 40 ms at 4 of 4 seeds in both families (tones +0.04 to +0.06, melody +0.02 to +0.04) and, at 200 ms, +0.01 to +0.04 on tones (4 of 4 higher) and nothing on melody, at D3's high plasticity. At the default low plasticity it is unmeasured.
  - The prior h1 0.134 / h5 0.386 was measured on frozen 50 Hz latents.
- **Unchanged:** `WORLD_MEDIA_COND`, `WORLD_MEDIA_CTX`, the free-running loss, the reporting rule, and the born-zero `media_forecast` under `WORLD_FEEDBACK` False.
- **Arm (unbuilt):** WORLD's per-frame surprise driving the 'alloc' stride choice. It needs a ruling on the circular dependence.

---

## 11. Checkpoint and geometry deltas

**New rulings.**
- **R-LIVE.** A codec field that sets no tensor shape and no id address is not geometry. `aud.version` becomes a READING: the snapshot step plus a weight hash at save.
- **R-RESUME-AT-ACT** (0b.1 item 14; the critic's option (b)). A **new** invariant: a resume continues bit-exact against the uninterrupted run, for a save at an optimizer-step boundary whose stream-defining Configs are unchanged (below). It supersedes Q-RUN-10's declared mid-epoch replay and closes Q-TOK-13's open continuation item. Its pieces:
  - **`run.seg`, the segmentation stamp**, in two parts:
    - the **text part**, rewritten only at a text segmentation (compose's epoch-0 row, every roll, and every act that splices: a TOK act, a relay, or both): the epoch; the cursor k0 (0 at an epoch start), the splice point p and b0, the first re-tokenized text byte; `view = (rev, size, retired)`, that segmentation's view (item 14); and `stream_state`, the BPE-dropout stream's state (`vocab.dropout_rng`, minted once at `"tok.dropout.mint"`) from just before that segmentation (`vocab_state` now carries the stream's current state, item 14);
    - the **media part**, rewritten at every act: the snapshot step and weight hash; `aud.born_at` (item 2); the chosen stride, or "unchosen"; the merge revision under 'bpe' and the stride maps of the unconsumed tail under 'alloc'; the act's Dues.

    An AUD-only act and a refused no-op splice nothing and draw nothing, so they leave the text part alone: the tail beyond them is still the last text segmentation's.
  - **The replay record**: the Segmentation's consumed prefix, positions [0, cursor), as held in memory at the save. It stores ids, `byte_pos`, modality, role and the snapshot-version track, about 10 bytes per position; `labels` and `bytes_per_token` are re-derived (item 14). It contains the retained unit [k0, p), every position consumed since the act, including codes cut at window cuts and written in place (under `'jit_ema'`, by a teacher that moved between cuts), and every look-back the resumed run reads.
  - **The clock**: `RUN.new_clock(..., resume_in_epoch=0, resume_windows_in_epoch=None)`, a signature move with Q-RUN-16, so compose restores the epoch position instead of replaying the epoch.
  - **Save points.** The tree saves per window (`loop.py:1104-1118`), so at `OPT_BATCH_WINDOWS` > 1 or `OPT_ACCUM` > 1 a save can fall with a partial batch, its OR'd Dues and pending gradients, none of which the payload holds. Periodic and SIGUSR1 saves are therefore deferred to the next optimizer-step boundary (batch empty, no accumulated gradient pending), and in an act's window the save follows the act. A driver stop between boundaries keeps today's counted drop (C1) and is outside the invariant.
- **R-RATE.** The chosen stride is a run-time value, checked payload-side (below).
  - A resume-time stride change is refused unless an act re-lays the unconsumed tail. This covers a change of `AUD_RATE_MODE` or `AUD_ALLOC_RHO` as well as of `AUD_RATE_STRIDE`: any change that alters the stride or the layout of the unconsumed tail.
  - Under `'spec'` it is refused outright, because after readiness no codec exists at another stride; re-choosing is a new run.
  - Under `'nested'` it is admitted when the resume's first act re-lays the unconsumed tail. That act is stamped as a self-inflicted shift, and the other stride block's slot vector is reported as untrained (`lm.media.block_untrained`).
- **R-OPT, extended.** Candidate groups `'codec.<s>'` that retired at readiness, and in the frozen control the codec group retired at the freeze, are admitted on restore as retired. Every other group change stays refused.
- **A CKPT ruling (Q-CKPT-5, next free) for payload-side checks.** `CKPT.check_geometry` supports only EXACT and MAY_WIDEN, and MAY_WIDEN only on ints (`ckpt/api.py:1024-1058`); the manifest is built from Configs (compose.py `_geometry_manifest`). Run-time values therefore leave the manifest and are checked on the payload, each with a named refusal: the chosen stride (`RESUME REFUSED: aud.rate_stride differs`), the presence of `run.seg` in a mid-epoch checkpoint that carries a replay record (a pre-S0b checkpoint, which has neither, keeps Q-RUN-10's replay and warning), and the snapshot hash against `aud.version`.

**Geometry manifest fields** (Config-derived only):

| Field | Rule | Absent means (R-CKPT `absent=`) | Why |
|---|---|---|---|
| aud.enabled | EXACT | False | which codec exists |
| aud.arch | EXACT | 'none' | which codec exists |
| data.aud_sr, aud.nfft, aud.hop | EXACT | 0 / 0 / 0 (off) | the base grid (`DATA_AUD_SR`, `AUD_NFFT`, `AUD_HOP`) |
| aud.d, aud.hid, aud.levels | EXACT | 0 / 0 / '' (off) | tensor shapes; the address of every id (a lattice change goes through the versioned-block handover arm) |
| aud.strides | EXACT | '' (off) | the candidate set's shapes and id blocks; widening needs a containment rule kind, ruled when a stride 8 is built |
| aud.seg_frames | EXACT | 0 (off) | the segment of 'nested' / 'alloc' |
| lm.media_rows.aud | MAY_WIDEN (int) | 0 | 0 when AUD is off; 'spec': prod(levels) + 2 = 1002 at any stride; 'nested': \|strides\| × prod(levels) + 2; + AUD_BPE_SLOTS under 'bpe'. The draft's "EXACT once > 0" is superseded (0b.6) |
| lm.media_rows_mode, sig.media_rows_mode | EXACT | 'none' | 'coord' / 'table'; 'none' when media is off |
| world.media_ctx, world.media_lat | EXACT (unchanged) | 'none' / 0 (the draft's) | |

`CKPT.check_geometry` refuses a field the manifest names and the checkpoint lacks, so every new field declares its off value (the draft's R-CKPT `absent=` rule). A pre-audio text checkpoint then reads as AUD off. Resuming it with AUD on is the draft's add-a-modality resume, where each off → on change is a birth, counted in `ckpt.geometry.born.<field>`. Any other change of these fields stays refused. No AUD checkpoint exists in the tree, so there is no first-draft checkpoint to admit.

Not geometry, and so free to change on resume (stamped as a self-inflicted shift; a `'jit_ema'` teacher is born from the snapshot): `aud.codes`, the half-life, learning rates, the anchor, re-warm, refresh period and probe size. **The rate mode and rho** may change on resume only when the stride and the layout of the unconsumed tail are unchanged, or, under 'nested', when the resume's first act re-lays that tail. Otherwise R-RATE refuses (for example 'measured' → 'fixed' at another stride, or → 'alloc' / 'bpe' under 'spec').

**Payload.**
- `aud`:
  - the live codec's state_dict; the snapshot's state_dict; the codec step and the snapshot step;
  - before readiness, every candidate; under 'jit_ema', the teacher;
  - rng children `aud.train` and `aud.probe`;
  - the drift-probe reference codes (the readiness snapshot's);
  - the readiness Gate state, the per-attribute readiness values, each later area's ceiling baseline, and each family's calibrated drop threshold;
  - the ceiling-guard hold state and the re-warm state;
  - under 'bpe', the append-only merge table (also written as a file, like the vocabulary), the live pair tally and the merge revision at the last act;
  - under 'alloc', the stride maps of the unconsumed tail as of the last act.
- `TOK.vocab_state` carries `rev`, now run-global, and the BPE-dropout stream's state; `restore_vocab` sets `rev` after the merge replay and puts the stream back. The Segmentation record carries `view`.
- `aud` also carries `aud.born_at`, the codec's birth window.
- `LOOP` carries `run.seg`, the replay record, `System.novelty`, `probe_prev`, `manage_losses` and the last RefreshReport's `hold_expires_at`, plus whatever else S0b's audit of loop-carried values finds.
- `OptState` carries the codec group (`'codec.<s*>'` at the default, `'codec'` otherwise, §6.2 step 1; every `'codec.<s>'` candidate before readiness) with its own step count and moments, and the set of keys `OPT.retire_group` retired, which the freeze's one-shot reads. The kept group's moments never retire; only readiness losers retire, and the kept group only in the frozen control.

**Rules.**
- **The resume.** compose:
  1. restores the clock at the saved `in_epoch` and `windows_in_epoch` through `RUN.new_clock(resume_in_epoch=, resume_windows_in_epoch=)`. On a mid-epoch resume the epoch0 row then skips `begin_epoch`, which would zero them, and `run()` seeds its cut index from the restored `in_epoch`; a boundary checkpoint resumes as the roll would (item 14);
  2. takes [0, p) from the replay record and calls `TOK.splice(tok, vocab, seg, data, labels, at=k0, view=run.seg.view, media=…, regularize=…, stream_state=run.seg.stream_state)` with the text part's k0, view and stream state. `at` is the last text segmentation's cursor k0 in both that act and the resume, so the splice lands at the same p and lays out [p, end) as the act did. Media in the tail is laid out and coded by the media part's snapshot, stride maps and merges, never by the codec or teacher as it has since moved;
  3. writes the replay record's [p, cursor) over the result. Text ids there are identical by construction, and so are media codes under 'snapshot' (both are checks). Under `'jit_ema'` the record supplies the codes the moving teacher cut, which nothing else could;
  4. checks that the dropout stream now stands where `vocab_state` saved it.

  At an epoch-start text part (no splice yet in the epoch, p = 0) the resume instead segments the epoch's stream from byte 0 at the recorded view and stream state, then applies step 3 from 0. Window i still cuts at i·ctx.
- **A new refusal: the re-measure.** compose compares the re-measured `windows_in_epoch` with `payload['RUN']['clock']['windows_in_epoch']` and raises `RESUME GEOMETRY: re-measured windows_in_epoch differs` on a mismatch. The tree has no such check today (compose.py:2612-2653 only warns about the replay); D1 had it as a prototype assert (`d1/run_arm.py` `load()`). With the stamp it cannot fail on a correct tree, so a mismatch is a defect. It applies only when the Configs that define the epoch's stream and its layout (DATA's, `AUD_ENABLED`, and the rate levers of R-RATE) match the checkpoint's. An add-a-modality or add-an-area resume changes them and has no uninterrupted counterpart. Its first act, at the cursor, keeps the replay record's [0, cursor), lays the child's newly drawn stream out after p from the recorded b0, as the readiness relay lays out a tail, and revises windows_in_epoch and the OPT horizon. It is neither refused by the re-measure nor held to bit-exactness, and it has its own known answer (below).
- **Known-answer tests.** Each must be bit-identical against the uninterrupted run. Text-only at S0b (§13 S0b lists them): a continuation with no act; across an act; between a mint, a retire or a reinstatement and the next act; two resumes in one run; one window after an act; at `TOK_DROPOUT > 0`; a boundary checkpoint at `RUN_EPOCHS=2`; a save requested between flushes at `OPT_BATCH_WINDOWS` 2 and at `OPT_ACCUM` 2. Media, at S3 and S4:
  - save between a snapshot refresh and the next window cut;
  - save during readiness with candidates alive, and just after the Gate;
  - save mid-run under `'jit_ema'` (the teacher's state), k windows after an act with k > `AUD_TRAIN_EVERY`, so positions [p, cursor) were cut by several teacher states;
  - the same `'jit_ema'` case with SIG 'typed' on and media inside the look-back (S4);
  - save after an AUD-only act at `TOK_DROPOUT > 0` (the text part predates the act);
  - save with the ceiling guard holding a refresh;
  - save after the frozen control's freeze (the group restores as retired, and the freeze does not fire again);
  - save one window after an act whose cursor is inside a clip (S4);
  - save with SIG 'typed' on and media inside the look-back (S4).

  An add-a-modality resume (AUD on over a text checkpoint) is not bit-identical. Its own known answer (S3): the first act lays the child's stream out after the replay record's prefix, windows_in_epoch and the OPT horizon match a fresh measurement of that layout, and the codec is born at the resume window with readiness counted from there (item 2).
- **Mixed-origin restores are refused.** `aud`, `lm.media_*`, SIG media rows and `world_media` must come from one checkpoint suffix. The measured analogue: stale latents under a later decoder cost +0.063 / +0.076 mel (D2).
- **R-CKPT's born rule** extends to the snapshot, the coordinate tensors (`C_emb` and `C_head`; the digit matrix is derived at build, not learned) and the drift-probe reference.
- **The act's cadence keys on checkpointed state, never on a loop-local counter.** TOK's retok Due comes from `TOK.on_window`'s `_due` (checkpointed as `tok.retok_seeded_window`); AUD's from `Cadences.due('aud.refresh', …)` (Cadences state is checkpointed, Q-RUN-9). The hold-expiry Due is a one-shot comparison against `hold_expires_at` (in `payload['LOOP']`); the freeze Due is `AUD.freeze_at(aud) > 0 and clock.step >= AUD.freeze_at(aud)` while the codec group is not in OptState's retired set. `RunClock.flushes` counts this process only and is a different Clock kind, so it is not used. Keying on a loop-local counter broke D1's first resume test (max |dloss| 0.0503).
- **Deleted:** "The codec's frozen weights are saved, so old codes stay decodable (AQM)". No code is persisted as truth, and the decodability of earlier areas is the codec-BWT row (mel and per-attribute recover exact).

---

## 12. Cost deltas

**Two bases, stated side by side.** D1's LM is tiny (12.0 ms per window on CPU), so a codec step (about 63 ms: 19.5 s over 308 steps, D1 s1) is about 5 D1 windows. R12's in-tree figure is +16-22% of LM time at one codec step per window, so there a codec step is about 0.2 tree windows. The same cadence therefore costs very different fractions on the two bases. The GPU bench decides.

| Item | D1 basis (measured, CPU, one thread) | R12 basis (arithmetic from the tree's +16-22% per step per window) | Source |
|---|---|---|---|
| **Default live codec** (one step per 32 windows, snapshot, anchor; **probing excluded**, next rows) | codec 2.0 ms/window (+16% of the LM's 12.0 ms/window); just-in-time re-encode 1.2 ms/window; refresh act mean 0.35-0.55 s per act (individual acts 0.30-0.73 s, `acts[].s`); wall without eval 186.5 vs 155.0 s (**+20%**, s1, uncontended); s0 +39% (contended, not comparable). The +20% covers the codec step, the re-encode and the acts only | about +0.5-0.7%, plus re-encode | D1 `d1/res/live25_s{0,1}.json` (`timers`, `acts`); proposal R12 |
| The same stack at one step per 4 windows | codec 173.2 / 171.0 s against LM 133.0 / 132.2 s (**≈130% of LM time**, i.e. about 2× CPU per window; contended) | about +4-5.5% | `critic/d1r/res/live25_every4w_s{0,1}.json` |
| **Readiness under 'spec' + 'measured'** (three candidates at one step per 4 windows, readiness windows only, 0 after) | about 3 × 130% ≈ **+390%** of LM time (arithmetic from row 2) | about **+12-17%** | arithmetic |
| **Probing** (encode, Griffin-Lim 32 decode, analytic inverse), D1's 25 Hz codec, one CPU thread | **28.0-34.9 ms per clip, mean 31.8** (encode 0.7-1.2 ms, Griffin-Lim 32 decode 25.9-31.1 ms, inverse 1.4-2.9 ms), from a preserved timing: `rev/probe_time.py`, output `rev/probe_time.txt`, 3 repetitions × 52 clips. An earlier unpreserved spot timing on another machine gave about 47 ms, so the figure is machine-dependent: about 28-47 ms per clip. From the preserved mean: one 400-clip reading is about 12.7 s (11.2-14.0) per area per codec. **Readiness** under 'measured' (3 candidates, 1 area, 6 readings by window 3001) is about 3.8 min (3.4-4.2) against D1's 36 s of LM time for those windows. At `AUD_PROBE_EVERY` 200 it would be 2.5× that, about 9.5 min. **After readiness**, one reading per act per arrived area, about 12.7 s. At the default act spacing (the 2000 ∪ 3000 union: 4 acts per 6000 windows, against D1's 72 s of LM time) that is **about +71% of LM time per arrived area**; at a 2000-window spacing (`TOK_RETOK_EVERY` 0, or before S0b ships a firing cadence) it is +53% | tree window about 63 ms / (0.16-0.22) ≈ 290-390 ms, so 3000 windows ≈ 860-1180 s: readiness probing about **+19-27%** of those windows (+48-67% at 200); after readiness about **+2.2-2.9% per arrived area** at the default spacing (+1.6-2.2% at a 2000-window spacing) | `rev/probe_time.{py,txt}`; arithmetic |
| `DOM.rekey` at a refresh act | not prototyped: it re-encodes every reservoir of the one Partition (render + encode + `SIG.encode` per media unit) | — | S4 measures it |
| FAB growth blackout (`FAB_COOLDOWN` 400 at every stamping act) | about 20% of windows at a 2000-window act cadence; about 27% for the union of 2000 and 3000 | same | arithmetic; S0b and S5 report the share from the new `fab.cooldown_windows` |
| Replay record in the checkpoint | about 10 bytes per consumed position (ids 4, `byte_pos` 4, modality and role 1, snapshot version 1): about 26 MB at the end of a 20k-window run × 128 positions | same | arithmetic |
| High plasticity (a step every 2 LM steps) | +35-38% per step | — | D3 |
| Live continuous codec vs the same design frozen | +65% per 12-clip media step | — | D2 |
| Coordinate rows | +0.01 s/step (about +5%; noisy across phases) | — | D3 |
| Just-in-time encode | 1.4 ms per 1 s clip (spec25, D3's part timing: 0.0168 s per 12 clips); the first draft measured an encode real-time factor of 0.0008, i.e. 0.8 ms per 1 s clip; the preserved probe timing gives 0.7-1.2 ms per clip for D1's codec | — | D3; first-draft §6.1; `rev/probe_time.txt` |
| 'alloc' | +106% per step against the frozen spec baseline (table rows, V 3264); allocation is 3 decodes per clip, taken at acts | — | D3 |
| 'bpe' act | 9.3 s at the first act on the toy stream, then shrinking; 2.4 ms/window averaged | — | D1 |
| EMA update ('jit_ema') | one lerp over about 1M parameters per codec step | — | arithmetic |
| **S0b tail re-tokenization** | **unmeasured at the owner's 17 MB tail; S0b measures it.** The archive's whole-stream retok cost ×0.77 throughput at 10 MB and ×0.25 at 100 MB per RETOK_EVERY, which is why the act is tail-only | — | archive (map risk 9) |

- **"No consistent LM-side cost" is at matched LM steps, not matched compute and not matched codec steps.** At the default cadence the price is +20% wall on CPU on D1's basis (one uncontended run) for the codec step, the re-encode and the acts. The per-act probe comes on top: at the default act spacing about +71% of D1's LM time per arrived area, or about +2.2-2.9% on R12's basis (+53% and +1.6-2.2% at a 2000-window spacing). The CPU cadence figures (1/32 against 1/4) are cost information, not grounds for the default (0b.1 item 6). S5 adds the step-matched and compute-matched controls (§13).
- **Codec steps in a 20k-window run** (arithmetic):
  - readiness 3000 / 4 = 750 steps per candidate, three candidates under 'measured' + 'spec' (D1's codec had 4000 before its live phase);
  - live about 17,000 / 32 ≈ 530 steps;
  - the old freeze plan: 750 steps.
- **Memory** (arithmetic, not measured): codec, snapshot and moments under 30 MB; the three candidates during readiness under 50 MB.
- **Under 'nested' + 'fixed',** the mixed-window head spans 1002 active media rows, with the other blocks masked. Under 'spec' there is only one block.
- **The GPU cost is owed.** R12's bench arm runs before any S3 default is fixed, at 12 runs per card under MPS, reporting windows/s and peak memory. Its rows:
  - media off;
  - codec frozen;
  - live at 1/32;
  - live at 1/4;
  - the readiness triple;
  - probing (n and cadence; the Griffin-Lim decode dominates on CPU);
  - `DOM.rekey` at an act;
  - 'alloc'.
- **Deleted:** the §12 line "Codec phase … Only for AUD_FREEZE_AT windows".
- The "Audio, 25 Hz" windows-per-media-second row now reads at the measured stride. The rate is `bench_summary`'s `media_seconds_per_s` at the chosen fps.

---

## 13. Staged-plan deltas

**S0 Rulings adds:**
- R-LIVE, R-RESUME-AT-ACT, R-RATE and the R-OPT extension (§11);
- R-ACT: Q-RUN-8 option (a) is adopted and built in S0b;
- one Q-entry per signature move (numbers are the next free ones in `docs/04_CONTRACT.md` today, renumbered at S0 if the draft's own rulings take them first): Q-TOK-15 `TOK.tokenize(view=)` (it also states that neither `tokenize(view=)` nor `TOK.splice` reads a per-call seed, the BPE-dropout stream's position crosses the save instead (P1-H56), and it rewrites `tokenize`'s "ONE function" and `_segment`'s counter docstrings), Q-MEM-13 `MEM.maintain(remap=)`, Q-RUN-16 `RUN.new_clock(resume_in_epoch=, resume_windows_in_epoch=)` (it supersedes Q-RUN-10's replay), Q-LM-13 `LM.build_model(media_lattice=)`, Q-SIG-3 `SIG.build(media_lattice=)`;
- Q-OPT-10, reopening Q-OPT-5 for `OPT.revise_horizon` (S0b OPT row);
- Q-MEM-14, re-denominating `MEM_WRITE_GATE` for the rescaled surprise (0b.1 item 16);
- Q-OPT-11, a ruling without a move: `OPT.maybe_step` writes lr to `base` and `encoder` only, and AUD, the codec group's stepper, owns its schedule (0b.1 item 6);
- Q-DOM-4, a ruling without a move: the reservoir's `(clip_ref, frame_offset)` track inside `DOM.observe`'s `sample_window` and `SIG.encode`'s `windows` (SIG ignores it), and the composed callable `DOM.rekey` receives, at acts and on its periodic A-stage row (0b.1 item 10);
- Q-CKPT-5, the payload-side checks (§11);
- the narrowing of the joint-training rejection (0b.1 item 18).

**S0b — MID-EPOCH RE-SEGMENTATION** (new; a prerequisite; text-only; FIRST, before S1). It makes the text retok live and makes a resume a continuation.

| Piece | Build |
|---|---|
| RUN | `RunClock.revise_epoch_length(n)` (+1 entry point). It keeps `_in_epoch` and refuses a Clock and n < `_in_epoch`. At n == `_in_epoch` it sets a flag that `advance()` checks **before** its step increment, so the next advance rolls without counting a window the loop has no material for (today `advance` increments `step` and `_in_epoch` before testing `rolled`, `train/api.py:686-704`, which is the Q-RUN-12 shape). Counters: `epoch_revisions` (a RunClock field and `counters()` key, unprefixed like its siblings) and `loop.acts`. **The clock restore:** `RUN.new_clock(..., resume_in_epoch=0, resume_windows_in_epoch=None)`, a signature move with Q-RUN-16; compose passes the saved values, so a mid-epoch resume continues instead of replaying (Q-RUN-10's replay and its warning remain only for a pre-S0b checkpoint without `run.seg`). ASSEMBLY_ORDER stays 40 rows, but the 'segment' row's note changes (§11 Rules; Contract accounting) and so does the 'epoch0' row's: on a mid-epoch resume carrying `run.seg` it does not call `RunClock.begin_epoch`, which zeroes `_in_epoch` (`train/api.py:663`), because new_clock has already opened the epoch at the saved position, and `run()` seeds `win_in_epoch` from the restored `in_epoch`; a boundary checkpoint resumes as the roll would, `begin_epoch` included (0b.1 item 14). §7 moves 137 → 138 for `revise_epoch_length`, with the K1/K6/K13 restatements. |
| TOK | **Segment at a view.** `vocab.rev` becomes run-global: `vocab_state` carries it, `restore_vocab` sets it after the merge replay, and it is never reset. Every Segmentation carries `view = (rev, size, retired)`. `TOK.tokenize(..., view=None)`: segment with the match table as it stood at `view` (None = as it now stands), built from `id2bytes[:size]` minus `retired` (exact because one byte string never has two ids, `_reinstate`); a signature move with Q-TOK-15. A call with `view` not None neither reads nor writes the one-slot `_retok_cache`, whose stamp describes the current table (`tok/api.py:1475-1477`). `vocab_state` carries the BPE-dropout stream's state and `restore_vocab` puts it back (the DOM/SIG `(rng._r.getstate(), rng._draws)` pattern). **`TOK.splice(tok, vocab, seg, data, labels, *, at, view=None, media=(), id_fn=None, regularize=False, stream_state=None) -> Segmentation`** (+1 entry point): it finds the unit under the cursor `at`, splices after it at p, re-tokenizes the text tail from the next text byte at `view`, re-interleaves the tail when `media` is given (S4). It calls `_segment` directly, owns `tok.retok` (or `tok.relay`), `tok.byte_fallback` and `tok.dropout_skip` for its call (except on a resume's rebuild, whose counts the root's counter put-back discards; the root then counts `tok.segment_resume` once), and leaves `tokenize`'s one-slot `_retok_cache` alone. `_segment`'s docstring ("declared by tokenize() and by nothing else") is updated to name `splice` and `tokenize(view=)`. `stream_state`, when given, rewinds the one BPE-dropout stream to a recorded position before the splice draws (the resume); no per-call seed is read (Q-TOK-15, P1-H56). The spliced record's `bytes_per_token` is measured over the spliced record (the throughput reading needs the live value, ISSUES P1-L42); `tok.bpt_tail` reports the tail's own. SIG's width stays on `Vocabulary.bytes_per_token`. The `TOK_RETOK_EVERY` help is rewritten and `docs/05_DEFAULTS.md` re-rendered. |
| LOOP | **The act**, a new LOOP_ORDER stage 'X' with `_CALLS['X']`: four X rows, one per package call (`TOK.splice`, `RUN.RunClock.revise_epoch_length`, `OPT.revise_horizon`, `DOM.on_retokenize`), because `_rows_by_stage` credits a name only from its own row and the misfiled check raises otherwise (0b.1 item 13). It moves from `_flush` (loop.py:2208-2230) into `run`, after the flush, with the batch empty. **Its Dues**, OR'd per Q-TOK-12: TOK's retok Due from `TOK.on_window`'s own `_due`; from S3, `Cadences.due('aud.refresh', AUD.refresh_period(aud), clock)` and the one-shot hold-expiry and freeze Dues (0b.1 item 8, §6.2 step 9); from S4, the readiness relay Due. Nothing keys on `RunClock.flushes`, which counts this process only and is another Clock kind. **Its steps:**<br>1. k0 = win_in_epoch · ctx.<br>2. Text, the no-op test first, before anything draws: if TOK's Due is the only text Due and the current view equals `run.seg.view` (at `TOK_DROPOUT` 0; above it the test is off, as `tokenize`'s is, `tok/api.py:~1478`), the act is a no-op for text: refused and counted in `tok.retok_noop` (the tree's no-op refusal, `tok/api.py:~1420-1433`; the archive's 2.189 bits/byte case). Otherwise every splice first records the BPE-dropout stream's state in `run.seg`'s text part, then: with TOK's Due, seg = `TOK.splice(at=k0, view=None)`, counted `tok.retok`; with TOK's Due and the relay Due, the same splice with `media=` at s\*, counted `tok.retok` and `aud.rate.relay`, with the relay's assertion and data_plan retake (§6.3); with the relay Due alone, seg = `TOK.splice(at=k0, view=run.seg.view, media=…)`, counted `tok.relay`. Else (AUD refresh, hold expiry or freeze only): no splice, and the text part is left alone.<br>3. Rebind the loop-local `ids` to the new Segmentation.<br>4. Re-resolve `sig_stream`.<br>5. `revise_epoch_length` if the length changed.<br>6. `OPT.revise_horizon` if the length changed.<br>7. Hand `resegment` and `remap` to MEM if the view moved.<br>8. `DOM.on_retokenize` if the view moved (against `run.seg.view.rev`; this replaces `_rev_at_last_seg`, `sysm.rev_at_last_seg` and `seg_table_moved`).<br>9. From S3: the snapshot refresh and the probe reading (§6.2 step 5).<br>10. Stamp `shift_at_windows` / `shift_at_steps` if the view moved, if media was re-laid once media has been consumed, or as the act's RefreshReport `stamp` says (from S3: 'now', or 'after_media' once media has been consumed; §7, 0b.1 item 16).<br>11. If the view moved, set `_mint_at_last_seg` (renamed from `_mint_at_last_roll`, which the roll sets only when it segments, `loop.py:1270`), so the end-of-run stranded-mint warning (loop.py:1353-1361) counts only mints no act delivered.<br>12. Record `run.seg`: its text part only if step 2 spliced, its media part always.<br>Periodic and SIGUSR1 saves wait for the next optimizer-step boundary and, in an act's window, follow the act (§11 Save points).<br>Counters `tok.retok_mid_epoch`, `tok.relay`, `loop.acts`. `tok.retok_deferred` and `tok.retok_satisfied_by_roll` become ABSENT with reason. `tok.due_dropped` must read 0. **Final-window rule:** a Due raised by the flush that finishes the run has no tail to act on, so it is counted in `tok.retok_at_finish` (PRESENT), never in `due_dropped`. **At a roll** with `TOK_RETOK_EVERY=0`, the roll segments at `run.seg.view`; with `TOK_RETOK_EVERY>0`, the roll is an act. **Held-out and generation** segment at `run.seg.view` once their call sites exist (`EVAL.holdout_probe` P5, `EVAL.generate` P6; neither is rowed today). **Loop-carried values:** `System.novelty`, `probe_prev` and `manage_losses` join `payload['LOOP']`, and the S0b commit carries a table of every value `run` carries across flushes, each checkpointed or shown re-derivable. |
| OPT | `OPT.revise_horizon(opt, st, *, run_windows)` (+1 entry point), converting through `derive.opt_steps_from_windows` with `d_effective_batch_windows` (Q-OPT-1 refuses a run_steps argument). It is **LR-continuous**: it remaps the rest of the schedule so that lr(now) is unchanged and the remaining cosine reaches the floor at the new end. When `opt.build.cycles_fitted > 1` (a restart wavelength shorter than the run), where "the remaining cosine" is undefined, `revise_horizon` is inert, not refused: `opt.horizon.revisions` is ABSENT with that reason and the horizon stays as built, so no previously valid `OPT_LR_WAVELENGTH` setting is refused. At the shipped `OPT_LR_RESTARTS` True with `OPT_LR_WAVELENGTH` 0 (one wavelength spans the whole run), one cycle is fitted and revision is live. The tree's own comment says "armed" for a restart means > 1, not `lr_restarts` == 1 (`opt/levers.py:617`, `opt/api.py:816`). **Q-OPT-10** reopens Q-OPT-5's (b) and answers both of its grounds: (1) the moving-target ground: the revision is an append-only log in `OptState` (`horizon_revisions`: (opt_step, run_steps) pairs), checkpointed, whose first entry is the build-time horizon; `load_state` rebuilds the schedule from that base plus the log, not from the resumed `OPT.build`'s horizon (fitted to the post-act segmentation, `compose.py:596`), and reports the saved last entry against the rebuilt one, so it compares against a recorded target, not a moving one; (2) the history ground: `_project` / `_lr_total` / `_proj_lr` re-projected the total from an estimate at every epoch and re-indexed the schedule, so lr jumped and later epochs latched (E8 p = 0.760, E18 p = 0.730, H17). The remap is instead one continuous change at a measured event (the act's re-measured length), anchored at lr(now), and it ends at the floor by construction; the known-answer test below checks both. `OPT_HORIZON_REVISE` defaults on only under that ruling. |
| MEM | Stored contexts are remapped by a root-passed function (MEM may not import TOK, O10): a `MEM.maintain(…, remap=None)` signature move with Q-MEM-13. The archive measured 82.3% of contexts stale after one growth step. The act sets `remap` and `resegment` for the next B-stage `MEM.maintain`, as the roll sets `resegment` today (`loop.py:1225`). The remap composes `TOK.Vocabulary.decode` (id → bytes) with `TOK.tokenize(..., view=V, regularize=False)` at the act's new view V, so it draws nothing from the dropout stream and, as a view call, neither reads nor writes the one-slot cache (0b.1 item 14). Q-TOK-15 also has a call with no `labels` (no stream) count in its own `tok.segment_remap`, not in the run stream's `tok.segment` and `tok.byte_fallback`; the call is named in the `MEM.maintain` B-row text and listed in `_OFF_TABLE`, as `decode` and `blen` are below. The rescaled surprise reads `TOK.Vocabulary.blen` (id → byte length). Both are deferred entry points today (P4), so S0b takes them out of `DEFERRED_ENTRY_POINTS` (24 → 22). They are named in the `MEM.maintain` and `MEM.write` B-row texts and listed in `loop._OFF_TABLE` on that naming, the `MEM.apply_domain_plan` precedent; K6 and K12 are restated. |
| Levels | The root hands `DOM.note_competence`'s bits as bits per build-time token (per-byte bits × build-time bytes_per_token), and `MEM.write`'s surprise as `surprise_b = 1 − p^(bpt_build / bytes(token))` under Q-MEM-14. R11's running baseline normalises after the conversion. FAB's regression test uses the shift stamp. `CAP.observe`'s improving test takes the same conversion, but it is inert until `CAP.observe` is rowed (a deferred stub, P4); at that point CAP's `blackout` input becomes the act stamp's third consumer. |
| CKPT | `run.seg`, the replay record and the loop-carried values (§11). A resume restores the clock, rebuilds the prefix and replays the last text segmentation's splice at its view. The new re-measure refusal (§11). This closes the Q-RUN-10 replay. |
| Tests | **Rewrites:** tests/test_tok_dom_cap.py T1/D1; tests/test_resume_clock.py C9 (a mid-epoch resume now continues; the replay warning is asserted only for a checkpoint without `run.seg`), and C5, C6 and C9's boundary half, re-run on the boundary path (a boundary checkpoint now carries epoch e's `run.seg`); tests/test_tok_persist.py loses its "WHAT IT CANNOT SEE" caveat, because continuation is now tested; tests/test_resume_clock.py C8 (`:262`, "mints the run entered with are counted as in the stream, not stranded") is rewritten: `_mint_at_last_seg` is seeded from `run.seg`, not from `tok.mint` at loop start (`loop.py:693`), and the stranded warning counts mints since the recorded act. **Known answers:**<br>1. prefix preserved at every act;<br>2. `in_epoch` kept;<br>3. no window replayed or skipped;<br>4. `TOK_RETOK_EVERY=0` at `RUN_EPOCHS=1` bit-identical to the R7 fixture, recorded at the S0b base commit;<br>5. at `RUN_EPOCHS=2`, `DATA_RESAMPLE=1`, `TOK_RETOK_EVERY=0`, no id minted after the epoch-0 segmentation appears in epoch 1;<br>6. `TOK_RETOK_EVERY>0` at `RUN_EPOCHS=1` now CHANGES the loss curve;<br>7. **first: a text-only continuation with no act**: save mid-epoch, resume, and every loss and integer fingerprint equals the uninterrupted run's (the tree's first continuation-equality test), TOK's counters included: in 7-14 every `tok.*` counter equals the uninterrupted run's except `tok.segment_resume` and the resume-only rows `tok.state_restored`, `tok.tally_restored`, `tok.load_reconciled(_detail)`, `tok.bpt_adopted` and `tok.bpt_mismatch`;<br>8. save/restore across an act;<br>9. **save between a mint and the next act** (the blocking case);<br>10. save between a retire and the next act (probation armed, `TOK_PROBATION_USES` > 0; at the shipped 0 nothing retires);<br>11. save between a reinstatement and the next act (probation armed);<br>12. two resumes in one run;<br>13. save one window after an act (the look-back and the retained unit lie before p);<br>14. 8-13 at `TOK_DROPOUT>0` (the dropout stream's state crosses the save; a resume whose splice does not end at the saved stream state is refused);<br>15. revise(n == in_epoch) cuts no empty window;<br>16. a final-window Due leaves `tok.due_dropped == 0`;<br>17. `revise_horizon` keeps lr(now) to 1e-12, ends at the floor, and after a resume gives the uninterrupted run's lr at every later step (the log's base is the build-time horizon); it is inert, ABSENT with its reason, when `opt.build.cycles_fitted > 1` (and live at the shipped one cycle);<br>18. the MEM remap of a context equals a fresh tokenize of its bytes;<br>19. a text act whose view did not move is refused and counted in `tok.retok_noop`;<br>20. segment-at-view of the last act's view equals the Segmentation that act produced;<br>21. `tokenize(view=V)` then `tokenize(view=None)` on the same buffer returns the current-table segmentation and counts no `tok.retok_noop` (the cache is not shared across views);<br>22. after assembly on a mid-epoch resume, `clock.in_epoch` and `windows_in_epoch` equal the saved values (the epoch0 row does not call `begin_epoch`), and the first window cut has the saved in_epoch as its index;<br>23. a boundary checkpoint at `RUN_EPOCHS=2`, `DATA_RESAMPLE=1` (the save in the window that rolled) continues bit-identical: the roll's segmentation, `begin_epoch` and a fresh `run.seg`;<br>24. 8, 9 and 13 at `OPT_BATCH_WINDOWS` 2 and at `OPT_ACCUM` 2, with the save requested between flushes (it is deferred to the step boundary). |
| Measurements owed before the default fires | (1) **3 paired seeds** (the same seeds in every arm), CPU, at the owner's shape, of `TOK_RETOK_EVERY` {0, 3000, 1000} at `RUN_EPOCHS=1`, plus a second control run (cadence 0) per seed that differs only in one declared nuisance rng child that neither the act nor TOK reads (named in the S0b commit). **The instrument** is the training stream's **prequential bits per byte**: Σ over windows of the window's loss before its update × its tokens / ln 2, divided by Σ bytes. The tree has no held-out producer (`EVAL.holdout_probe` is deferred to P5, and compose.py:1171 says "best_bpb HAS NO PRODUCER"). At `RUN_EPOCHS=1` every window is scored before the model has trained on it. Bits per byte over the same bytes in the same order is a unit that does not move with the segmentation, so the arms are comparable (the retok arms take fewer windows for the same bytes, and that is part of what is measured). S0b logs bytes per window for it. The last 2000 windows' value is reported beside it. When `EVAL.holdout_probe` lands (P5), the rule is re-run on held-out bits/byte at the view of the last text segmentation. (2) **Ship rule, non-inferiority, margin from paired-difference noise.** Let M = max over seeds of \|bpb₀(s) − bpb₀′(s)\|, the two control runs' paired spread. Cadence c ∈ {3000, 1000} ships if bpb_c(s) − bpb₀(s) ≤ M at EVERY one of the 3 seeds. M is recomputed if more seeds are added (it is a max over one nuisance pair per seed, so it grows with the seed count). Among those that ship, the lower mean wins. If neither ships, `TOK_RETOK_EVERY` ships 0 (the act still serves AUD and resume) and the report says so. The margin is not the control's between-seed spread, which pairing exists to cancel. (3) Time `TOK.tokenize` and `TOK.splice` on a 17 MB tail. (4) Report bpt across acts (the SIG width rule, §16), `tok.mint_wait_windows`, the MEM remap share, FAB growth (`fab.grown_*`) and the FAB blackout share around acts (`fab.cooldown_windows`, new) (the archive's 2.189 bits/byte side-effect risk), and the replay record's size. |
| Size | About 700-950 lines core (the map's 350-500, plus segment-at-view, the splice helper, the replay record, the clock restore and the loop-carried audit; estimated from reading, not building); 950-1300 with every half. Entry points 137 → 140. LOOP_ORDER 63 → 67 (four X rows). DEFERRED_ENTRY_POINTS 24 → 22 (`TOK.Vocabulary.decode`, `TOK.Vocabulary.blen`). Signature moves: 3 (`TOK.tokenize`, `MEM.maintain`, `RUN.new_clock`). State-shape changes: `Segmentation.view`; `vocab_state` `rev` and the dropout stream's state; `run.seg`, the replay record and the loop-carried values in `payload['LOOP']`; `OptState` `horizon_revisions`. |

**S1 — Spine and synthetic audio:**
- `DATA.render(dat, refs) -> waves` (+1 entry point, deferred until AUD names its consumer at S3).
- Placeholders carry clip references.
- The Segmentation reserves a per-clip stride-map track, empty under 'measured' and 'fixed'.
- The R7 fixture already exists (recorded at the S0b base commit).

**S3 — AUD with a live codec.**

*Build:*
- AUD with 'spec' per-stride candidates, plus the 'nested' and 'wave' arms. Positions per clip F = ceil(frames / s), with the silence pad and decoder trim (0b.1 item 3).
- `AUD.ready`, replacing `freeze`, with the readiness probe and the rate selection inside it; the root passes `recover_fn` and the rendered probe waves. Its A-stage row runs on Cadences key `aud.probe` during readiness. The Gate is tested from `AUD_READY_MIN` windows after the codec's birth (`aud.born_at`); under 'measured' it reads as 0b.1 item 2 says.
- **`AUD.refresh(aud, codec, *, recover_fn, probe_waves, clock) -> RefreshReport`** (+1): the per-act work after readiness; during a hold its report carries `hold_expires_at`. It does the probe reading, the flips, `aud.moved`, the ceiling guard's hold-or-proceed decision against AUD-held baselines, and the snapshot copy unless held (§6.2 step 5). Under 'snapshot' it is on an X-stage row; under `'jit_ema'` it is on an A-stage row on `aud.probe`, with no copy (§6.2 step 8).
- **`AUD.horizon_audit(aud, *, run_windows) -> [str]`** (+1), on the ASSEMBLY 'audit' row beside `RUN.cadence_audit` (0b.1 item 9).
- **`OPT.retire_group(opt, st, *, key)`** (+1, OPT), on an A-stage row: the readiness losers at the Gate, and the kept group in the frozen control (0b.1 item 6).
- Accessors `AUD.freeze_at` (kept for the control arm's one-shot Windows comparison), `ready_period`, `train_period`, `refresh_period`, `probe_period`. The periods join compose's `_periods` under keys `aud.ready`, `aud.train`, `aud.probe` and `aud.refresh` (`aud.refresh` 0, DISARMED, under 'jit_ema'; all four 0 when AUD is off; 0b.1 item 9). `aud.freeze` is not a period (§6.2 step 9).
- `AUD.loss_terms(aud, codec, wave, *, opt, anchor=None)` on an A-stage row evaluated per window, stepping the codec group (`'codec.<s>'` per candidate, then the kept `'codec.<s*>'` at the default; `'codec'` otherwise; the Q-OPT-6 pattern), clipping it at `AUD_CODEC_GRAD_CLIP` and writing its lr from AUD's own schedule (Q-OPT-11): D1's betas and weight decay, and the cosine from `AUD_CODEC_LR` to `AUD_CODEC_LR_MIN_FRAC` over `derive.codec_steps_from_windows(AUD_READY_MIN, AUD_READY_EVERY)` codec steps. The new derive functions `codec_steps_from_windows`, `ema_decay_from_half_life` and `latent_frames_from_seconds` (the last used at S6) land here with their known-answer rows in `tests/test_derive.py`.
- Live training with rehearsal through `DATA.render` and the anchor to the snapshot; training on readiness-area crops between the Gate and the first media window.
- Refresh at every act through S0b's act and AUD's own refresh Due (`AUD_REFRESH_EVERY` 0 refused under 'snapshot'); just-in-time re-encode at cut, written in place into the Segmentation.
- The ceiling guard, calibrated per family, with 'hold' and the root's one-shot act Due at RefreshReport's `hold_expires_at`; the hidden-freeze warning through `AUD.horizon_audit`; `aud.moved` on the live codec; the drift gauges; `aud.target_collapse`.
- The probe: every 500 windows in readiness; after it at every act under 'snapshot' and every 500 windows under `'jit_ema'`; the paired SE per cell.
- The 'jit_ema', re-warm and frozen-control arms; `AUD_RECON_LOSS='multires'`.
- `AUD.allocate` (+1); under 'bpe', `AUD.observe`, `AUD.mint` and `AUD.segment` (+3).

*Acceptance adds:*
- **Readiness calibration.**
  - The per-family floor is measured at 2 codec seeds, on aud/tones first.
  - The Gate fires on a plateau fixture, never before `AUD_READY_MIN` (a fixture that plateaus at window 1000 fires at 3001, the first probe reading at or after it); each candidate has 749 codec steps by window 3000 at `OPT_BATCH_WINDOWS` 1 and at 16; and on a noisy flat fixture (a stipulated-flat codec read on 400 simulated paired clips). `aud.ready.late` fires on a fixture that never plateaus.
  - An add-a-modality resume at window 5000 refuses a media phase at 6000 and at 8001 and admits one at 8002 at `OPT_BATCH_WINDOWS` 1; its Gate is first tested at 8001.
- **The 'measured' known-answer test (selection only; the re-lay is S4's).** Three fixture candidates with stipulated per-attribute readings:
  1. stride 4 within 0.05 on every attribute selects 4;
  2. one stride-4 attribute at −0.06 selects 2;
  3. strides 2 and 4 both out selects 1;
  4. exactly −0.05 counts as within;
  5. a noise fixture: two stipulated-equal candidates read on 400 simulated paired clips; the rate at which the finer stride is chosen is reported against `aud.rate.false_out_est`;
  6. a 1 s aud/tones clip at stride 4: F = 13 positions, 2 pad frames, decoded length exactly 8000 samples.
  The losers' groups retire through `OPT.retire_group`, and their readings are reported.
- **'nested' vs 'spec'** by the pre-declared criterion at 2 seeds, with its non-inferiority margin, including per-attribute recover exact on every attribute of every family (§6.1). The result sets `AUD_ARCH`.
- **The D1-harness replica of the shipped default** (0b.1 item 6). The full default stack (first-area readiness with 750 steps per candidate and the cosine, 'measured', 0.64 s crops, a refresh at every act, D1's betas, weight decay and clip, the ceiling guard) runs in the D1 harness at the tree's `OPT_BATCH_WINDOWS` 1, on the shipped optimiser path (not D1's `codec_step`), at 2 seeds, as three cells:
  - replica-live ('measured');
  - replica-frozen (the same recipe and chosen stride, `AUD_FREEZE_AT` at the window the Gate fired);
  - readiness-only: D1 live25 as measured, with only its codec phase replaced by the shipped readiness recipe (0b.1 item 6).
  - **Transfer test.** The label "no consistent LM-side cost" transfers to the shipped default only if replica-live is non-inferior to replica-frozen on every LM-side codec-invariant primary the D1 harness records (caption bits/byte, understanding exact, generation exact; grounding is first read at S5; margin 2 paired SE) at both seeds. Its recover-exact drop against replica-frozen is reported beside D1's, and it calibrates the ceiling guard.
  - **Recipe check.** The readiness-only cell is compared with D1 live25 at the same seeds on those primaries. If it is worse beyond 2 paired SE on any of them, the replica re-runs with the `'+generic'` readiness arm (D1's recipe; a DATA `aud/generic` family is then added at S3), and the default follows it. If the `'+generic'` cell fails too, both go to the owner, and the default ships the recipe closer to D1 live25 on the primaries.
  - Bits/s is reported and never used here: no two of these cells share a codec (item 19).
- **Hidden freeze.** `RUN.cadence_audit` states the aud.* periods at startup, and `AUD.horizon_audit` warns when an armed half-life or the longest hold exceeds 0.25 × run_windows. Neither refuses: a 200-window run with AUD enabled and no media phase starts and is warned. At `AUD_FREEZE_AT` 0 the freeze never fires and `aud.freeze` is ABSENT. `aud.moved` is 1 after a live act, 1 at an act whose refresh the guard withheld (the live codec still moved), and PRESENT-and-0 under the freeze arm. Under `'jit_ema'` it is read every `AUD_PROBE_EVERY` windows, with or without acts.
- **Ceiling guard.**
  - The drop threshold is calibrated per family at the default plasticity (measured live-vs-frozen drop at 2 codec seeds + 2 paired SE).
  - `aud.ceiling_drop` fires on a fixture that erases harmonics.
  - On a calibrated family the next refresh is withheld; `AUD_CEIL_HOLD_WINDOWS` after the first withheld refresh, the root raises an act Due from `hold_expires_at` and the refresh proceeds with a warning; the longest hold on the fixture is 4000 windows (at `OPT_BATCH_WINDOWS` 1).
  - On an uncalibrated family it counts and never holds; under 'jit_ema' `aud.ceiling.hold` is ABSENT with its reason.
- **Stamps.** A refresh act before the first media window stamps nothing; the first refresh act after media is consumed stamps FAB and OPT.
- **`TOK_RETOK_EVERY=0` with AUD refresh acts:** no id minted after the last text segmentation appears in the stream, and `tok.retok` stays 0.
- **Resume.** Bit-exact against the uninterrupted run for §11's S3 cases: between a snapshot refresh and the next window cut; during readiness with candidates alive; just after the Gate; under 'jit_ema', k windows after an act with k > `AUD_TRAIN_EVERY` (the teacher moved between the cuts of [p, cursor)); while the ceiling guard holds a refresh; after an AUD-only act at `TOK_DROPOUT > 0`; after the frozen control's freeze (the group restores as retired, and the freeze does not fire again). An add-a-modality resume has its own known answer instead (§11).
- **The codec-only matrix.**
  - Cells: {snapshot, jit_ema} × {anchor 0, 10} × {re-warm 0, 0.3} × {ceiling hold, count}, plus the 'multires' loss arm.
  - It runs at **2 codec inits**, on area A then area B.
  - Readings: flips per 50 steps; codec BWT on A after B as mel AND per-attribute recover exact (an acceptance reading); new-area mel and recover exact.
  - `AUD_REWARM` defaults on only if no attribute's recover exact falls under it by more than 2 SE of the paired difference, at either seed.
- **The CPU acceptance** replaces "probe ceiling ≥ 30%": mel < 0.6, codes_used ≥ 300, and per-attribute recover exact at the aud/tones family floor within 5 CPU-minutes (probing excluded from the budget, §12).

*Entry points at the audio stages:* 137 → 169 after S6, 186 with VID (Contract accounting).

**S4 — Shared stream:**
- `TOK.interleave` (+1).
- The act is extended to interleaved streams through `TOK.splice`:
  - it finds the unit under the cursor (a text token, or a whole clip record);
  - it splices after it;
  - it re-tokenizes the text tail from the next text byte;
  - it re-interleaves the tail.
- Known answers for the splice:
  - **a cursor inside a clip**: the clip appears once, whole, in the prefix; no clip is duplicated or dropped; unit_pos stays monotone;
  - a cursor on a caption token;
  - a cursor on END.
- **The readiness relay** (the re-lay half of 'measured''s known-answer test): the relay act lays the tail at the chosen stride at `run.seg.view` (no minted id enters with it; an act that also carries TOK's Due splices at the current view and counts both `tok.retok` and `aud.rate.relay`), asserts that no media has been consumed, and revises windows_in_epoch and the OPT horizon; `aud.rate.relay` is ABSENT with its reason when the stride equals the provisional one. Known answer: a 1 s aud/tones clip re-laid from stride 2 (25 positions) to stride 4 takes 13 positions, its END follows position 13, and it decodes to exactly 8000 samples.
- **Resume**, bit-exact: save one window after an act whose cursor is inside a clip; save with SIG 'typed' on and media inside the look-back; the same under `'jit_ema'`, k > `AUD_TRAIN_EVERY` windows after an act (the replay record supplies [p, cursor)).
- Coordinate rows through `LM.build_model(media_lattice=)`. Known answer: the residual is born zero, and the digit matrix is derived at build.
- SIG 'typed' coordinate embedding through `SIG.build(media_lattice=)`, and the `sig.media_drift` gauge.
- `DATA_MEDIA_REHEARSE`.
- DOM, EVAL and MEM store clip references. `_sample_window` returns a `(clip_ref, frame_offset)` track for media units beside its units; DOM's Partition reservoir stores it (a state-shape change with a restore row). At refresh acts once media is consumed, at `SIG_MODE=learned`, `DOM.rekey` receives the composed callable (`DATA.render` → the snapshot's `AUD.encode` → `SIG.encode`), which re-encodes only media units, on its own X-stage row; the periodic A-stage `DOM.rekey` receives it too once media is in the reservoir. The reservoir track and the callable's contract are ruled by Q-DOM-4 (no signature moves). Its cost is measured here (§12).
- Refresh acts stamp the shift (FAB, OPT) once media has been consumed.
- Under 'nested', the mask covers the active stride block only.

**S5 — Grounding and goal B.** Four pre-declared matrices at **2 paired seeds**, GPU, 2-4 s clips. Seeds vary the codec init as well as the LM, which D1 did not.

- **(i) Rate:**
  - fixed 12.5 / 25 / 50;
  - 'measured';
  - 'measured_arrival' (under 'nested');
  - 'alloc' at rho 0.1 and 0.5;
  - 'bpe';
  - plus the pair the critic found missing: nested fixed-stride vs nested 'alloc', both with coordinate rows.
  It decides whether per-segment adaptivity becomes the default, and whether 'measured' picks as well as the best fixed stride.
- **(ii) Plasticity:** {snapshot-at-act, just-in-time EMA} × {the measured cadence 1/32, 1/4} × {anchor 0, 10} × {ceiling hold, count}, plus the EMA's window-matched half-life cell. Controls:
  - the frozen codec;
  - a **step-matched** frozen control **per cell**: its codec takes the same total number of codec steps as that cell's live arm takes by the end of the run, all before the first media window, then freezes at window `AUD_READY_MIN` + 1 (a pre-Gate freeze, §6.2 step 9), NOT at the Gate's first test: that test lands on the next probe reading (3001 for `AUD_READY_MIN` 2560), and the readiness cadence keeps stepping until then, about 220 steps over the match. Its readiness cadence and horizon are set per cell so that the cosine reaches its floor at the matched count. At a 20k-window run that is about 750 + 530 ≈ 1280 steps for a 1/32 cell (`AUD_READY_EVERY` 2, `AUD_READY_MIN` 2560: period 2 seeded lazily at window 1 steps at 3, 5, …, 2561, 1280 steps, counting window 2561's own step because the readiness row runs before the root's freeze comparison in that window) and about 750 + 4250 ≈ 5000 steps for a 1/4 cell (`AUD_READY_EVERY` 1, no lever gives more; `AUD_READY_MIN` 5000; there `AUD_READY_MIN` + 1 = 5001 coincides with the Gate's first test, so that freeze is at the Gate, and the count is still 5000), which starts its media 2000 windows later. The control's cadence, horizon and, in the 1/4 cell, media timing differ from the cell's; each is labelled, and the matched step count is reported per cell;
  - a **compute-matched** frozen control, which gets the codec's compute as extra LM steps.
- **(iii) Routing stack.**
  - FAB, DOM and MEM on, under a live vs a frozen codec.
  - Arms, over `AUD_SHIFT_STAMP`: the default 'refresh' (every refreshing act once media is consumed) against 'flips' (thresholded at `AUD_SHIFT_FLIPS`) and 'always' (every act from readiness on, including before media).
  - Readings: `part.n_created` and `part.n_culled` (DOM spawns and culls), `fab.grown_regression`, `fab.grown_stall` and `fab.births` (FAB growth), `fab.cull_util` and `fab.cull_fail`, `sig.media_drift`, the per-byte levels, and the FAB blackout share from the new `fab.cooldown_windows`.
- **(iv) Coordinate vs table rows** at 20k windows with at least 10× the prototypes' media LM steps. Readings: the gain and the cross-area interference. `'table'` returns to the default if the gain disappears while the interference stays.

**Decision rule.**
- An arm replaces a default only when, **at both seeds**, it is no worse than the default on **every** codec-invariant primary by more than 2 SE of the paired difference, and better on **at least one** of them beyond that margin. The primaries:
  - generation exact;
  - understanding exact;
  - caption bits/byte;
  - grounding bits;
  - per-attribute recover exact.
- When the two arms share a codec, the arm must also be no worse on bits per audio-second beyond the same margin. When they do not (rate, architecture, plasticity), bits/s is reported and not used (0b.1 item 19).
- Codec BWT must stay within +0.02 mel, and within each family's calibrated drop threshold on per-attribute recover exact.
- On a rate tie (no primary differs beyond the margin), the arm with fewer positions per second wins. On the toy readings, with bits/s set aside, the D3 'alloc' and fixed pairs tie on the codec-invariant readings (0b.2 row 12), so this tie-break would have favoured 'alloc' (on tones 22-23 against 26 positions per second; on melody 24.9-25.6 against 26), even though its LM bits/s on the same nested codec was 4-15% higher. The toy primaries sit near the floor on understanding and generation (0b.2 Floors), so that is not evidence either way. S5 decides at 2-4 s clips, and it reports bits/s beside the primaries.
- **The frozen controls are controls.** If the frozen codec, or its step- or compute-matched control, wins by this rule, no default flips to a freeze on its own. The owner ruled out anything frozen "unless absolutely necessary", so the result goes to the owner as that question, with the best live cell of the plasticity matrix beside it.

**S6 — WORLD:** the tokenizing-latent target, horizons in U.SECONDS, and the §10 gauges.

**S7 — VID:** the same revision throughout:
- `VID_FREEZE_AT` 0;
- a VID snapshot;
- VID coordinate rows;
- 'measured' over the temporal stride;
- a spatial nested-stride arm (the 2-D analogue of 'alloc');
- VID's accessors and entry points mirror AUD's 17, and its levers mirror AUD's new ones where they apply (Contract accounting counts the full mirror as an upper bound).

**S8 arms, in order:**
1. 'alloc' with WORLD-surprise allocation.
2. The continuous route (D2: chunk insert, GMM, duration and END heads, router, `LM_MEDIA_GMM_W`, `lm.media.gmm_grad_ratio`).
3. 'windows' geometry.
4. The 'rep' coupling.
5. The learned vocoder.
6. 'dmel'.
7. The versioned-block handover, for a lattice or architecture change only.
8. The existing S8 list, unchanged below these.

---

## 16. Open questions — deltas

Rows 1, 3-10 and 12 stand as written. Row 2 is replaced; row 11 is replaced by row 21; rows 13-33 are new.

| # | Question | Recommendation (built if unruled) | Why |
|---|---|---|---|
| 2 | The frame rate | `'measured'` per run at readiness. `'fixed'` stride 2 is the control; 'alloc', 'bpe', 'router' and 'measured_arrival' are arms. S5 decides per-segment adaptivity. | It removes the hand-set Hz without losing LM work, since no media has been consumed. The toy evidence favoured a fixed stride over per-segment routes on LM bits/s only (alphabet-dependent across rate arms; the codec-invariant readings tie within noise), and on 1 s clips, which can fake a low-rate cliff [S]. |
| 13 | Is a fixed non-learned transform "absolutely necessary" (grid, lattice, Griffin-Lim)? | Grid and lattice: yes, like bytes, with learned alternatives as arms. Griffin-Lim: no; build the learned vocoder arm. | Neither the grid nor the lattice has parameters, and each gives an id its unit or address. Griffin-Lim is a fixed stage where a learned one exists, and it may contribute to the timbre loss. |
| 14 | Codec plasticity default | D1's measured regime: 1/32 cadence, floor 5e-5, D1's betas, weight decay and clip, anchor 10 to a snapshot refreshed at every act (at least every 2000 windows, 4000 under a guard hold), rehearsal 0.5. Re-warm off. AUD owns the codec schedule (Q-OPT-11). S3's replica, with its own frozen control, confirms the shipped stack; S5 (ii) decides between cadences. | The only live regime measured against a frozen codec at 4 paired LM seeds: lower bits/s (codec-dependent) in 24/24, no consistent cost or gain on the LM-side codec-invariant readings, and a consistent codec-ceiling cost (recover exact lower 7 of 8, 1 tie); one codec init, 25 Hz. 1/32 is the only cadence with a 4-LM-seed paired live-vs-frozen measurement (D-4). The 1/4 cadence leaned better on the codec-invariant readings (caption 3 of 4, understanding 2 of 2, recover exact 3 of 4) at 2 seeds, one codec init, unreproduced and within the seed spread, so neither cadence is established; S5 (ii) decides on the primaries under §13's rule. CPU cost (about 2× at 1/4) is information in §12, not grounds. High plasticity: −0.1% to +8.1% bits/s (codec-dependent, item 19) vs frozen (7 of 8 worse, 4 seeds, coordinate rows), +3.2% to +8.1% (table rows, 3 seeds), reproduced-weaker; on the codec-invariant readings, timbre recovery lower (0b.2 row 15). |
| 15 | S0b changes every default run past window 3000 | Adopt it. Ship `TOK_RETOK_EVERY` by the non-inferiority rule (§13). | Otherwise the text segmentation stays frozen and the lever stays inert. |
| 16 | OPT horizon after an act | `OPT.revise_horizon(opt, st, *, run_windows)`, default on, LR-continuous, inert (ABSENT with its reason) when `opt.build.cycles_fitted > 1` (live at the shipped one cycle), under Q-OPT-10. | Otherwise the under-anneal Q-OPT-5 named occurs inside every run, not only across epochs. Q-OPT-10 answers Q-OPT-5's two grounds: the revision is a checkpointed append-only log, so `load_state` compares against a recorded target; and it is one continuous remap at a measured event, not `_project`'s per-epoch re-projection. |
| 17 | Coordinate rows by default despite more cross-area interference | Yes, with `DATA_MEDIA_REHEARSE` 1/3. `'table'` is a live S5 arm, plus the longer / larger-data check. | A robust sample-efficiency gain at 4/4 seeds in both harnesses (−9.9% to −16.7% in D1, one codec init, smaller at new seeds; −11.3% to −15.3% in D3) that may shrink at scale while the interference stays. It is not drift tolerance. |
| 18 | A live codec improves mel and lowers timbre recovery | Recover exact is the acceptance metric. The guard, calibrated per family above the measured spread, holds the snapshot. The 'multires' loss arm is built before re-warm can default on. | Timbre falls in D3 at high plasticity, not step-matched (tones 4/4, melody 3/4 plus a tie), and at D3's low plasticity by less (tones 2/2); D1 records exact match only. Exact match falls in D1 (one codec init) and is mixed in D3. An objective misalignment, not a codec defect. |
| 19 | Should the LM or WORLD shape the codec? | Default none. 'rep' and 'input' are arms. | Likelihood into the codec collapses or concentrates the latent; bounded terms are unmeasured here. |
| 20 | Media geometry | 'inline' by default; 'windows' is an arm. | Inline supports interleaved documents and needs no act at a per-run stride. |
| 21 | Codec retraining on real data (replaces old Q11) | The live codec adapts in place. A re-warm at the area's arrival waits until S3 clears it. The versioned handover is only for an architecture or lattice change. | Media code meaning is no longer frozen within a run, and nothing persists codes. |
| 22 | Resume when the vocabulary or codec changes between acts | Option (b): resume from the last act's recorded state, through the view, the replay record, the run-global rev and the clock restore. (a) and (c) are recorded as rejected. | Bit-exact continuation, a NEW invariant that replaces Q-RUN-10's declared replay and closes Q-TOK-13's open item; and `TOK_RETOK_EVERY=0`'s meaning (0b.1 item 14). |
| 23 | Codes: snapshot-at-act or just-in-time EMA | Snapshot by default; `'jit_ema'` is an arm. | The measured regime; exact resume; one drift event per act. EMA's measured value is flip rate, not LM bits. |
| 24 | Architecture: 'spec' or 'nested' | 'spec'. S3 decides with the per-attribute criterion and its non-inferiority margin. | 'nested' was lower on melody timbre at 3/3 seeds (one of the three beyond noise at n = 64) while winning tones mel. |
| 25 | Does 'measured' need a mel term, or a larger probe? | No mel term by default, and `AUD_PROBE_N` 400, read as a paired difference with its SE and false-"out" estimate reported. S5 checks 'measured' against every fixed stride. Add a mel term if 'measured' picks a stride that loses on the primaries; raise n if the paired SE exceeds `AUD_RATE_TOL` / 2. | On the toy nested-codec readings, exact match alone would have picked 12.5 Hz where tones mel was +12%. Mel is secondary, but the rule is unprototyped and noise biases it toward stride 1. |
| 26 | The routing stack under a moving tokenizer | Coordinate signatures; shift stamps to FAB and OPT (CAP from P4) at acts that move the text view and at refreshing acts once media is consumed; `DOM.on_retokenize` whenever the view moved (any `SIG_MODE`) and the composed `DOM.rekey` at refresh acts once media is consumed (at `SIG_MODE=learned`, Q-DOM-4); bits per build-time token for DOM (and CAP from P4); MEM's rescaled surprise. The S5 (iii) arm measures them, with `AUD_SHIFT_STAMP` 'flips' and 'always' as arms and the FAB blackout share read from the new `fab.cooldown_windows`. | No prototype had SIG, DOM, FAB or MEM. |
| 27 | Readiness data | The first media area in the schedule. D1's recipe (a declared generic set beside it) is the `'+generic'` arm (row 29). | It keeps later areas new to the codec, so codec BWT and arrival readings mean something. |
| 28 | Fairness of live vs frozen comparisons | Every S5 plasticity cell reports step-matched and compute-matched frozen controls, labelled. | D3's mel gain was not step-matched (1500 vs +600 steps). D1's live vs frozen was not codec-step-matched (+308 steps) and not compute-matched (+20% wall). Bits/s is codec-dependent, so live vs frozen is judged on the codec-invariant primaries. A frozen control that wins goes to the owner as a "necessary?" question, not into the default (§13 decision rule). |
| 29 | Readiness recipe | The first media area, at least 750 codec steps per candidate. The `'+generic'` arm (D1's recipe) takes over if S3's readiness-only cell loses to D1 live25 (the recipe check). | D1's measured codec had 4000 steps and a generic pre-training set; the shipped default has neither, and nobody measured that. |
| 30 | Probe cost | Probe every 500 windows in readiness; after it at every act under 'snapshot' and every 500 windows under `'jit_ema'`; `AUD_PROBE_N` 400; the GPU bench sets n and cadence. | On CPU one 400-clip reading costs about 11-14 s per area per codec (preserved timing, `rev/probe_time.{py,txt}`: 28-35 ms per clip, Griffin-Lim dominates; about 47 ms on another machine). Readiness probing is then about 3.8 min at 500 against 36 s of D1 LM time, and about 9.5 min at 200; after readiness about +71% of D1's LM time per arrived area at the default act spacing. |
| 31 | The ceiling guard's threshold | Calibrated per family at S3 (measured live-vs-frozen drop + 2 paired SE); count-only until calibrated. | A flat 0.05 would fire in the measured regime itself (D1 s0 drops 0.069 and 0.118) and put the refresh cadence into back-to-back holds of up to 4000 windows each (`AUD_REFRESH_EVERY + AUD_CEIL_HOLD_WINDOWS`). |
| 32 | `world_proj` is born zero with no gradient | Leave it off until the GPU test of Q-WORLD-10. | A parameter held at zero pending a measurement, not a codec issue. |
| 33 | The SIG width is fixed from build-time bytes_per_token | Keep it. S0b reports bpt across acts; revisit if it moves by more than 5%. | A re-derive needs DOM re-slicing. |

---

## Contract accounting — deltas (amends §0 R6 and §5's counts)

**Method.** At every stage commit, `python3 tools/sync_counts.py` rewrites the counts in `docs/` and `src/` from `tests/test_contract.py::k13_live_counts`, and `python3 tools/sync_counts.py --check` must pass. Test-file fixtures (A8) are fixed by hand. `tools/render_defaults.py` re-renders `docs/05_DEFAULTS.md`, and `tools/render_wiring.py` re-renders `docs/03_WIRING.md`. The numbers below are the PLAN; the tool's count is the truth at each commit. The tree today reads (k13_live_counts, 2026-09-25): 137 entry points (14 stubs, 24 deferred), 262 levers, 19 of 25 wires, 63 LOOP_ORDER rows, 40 ASSEMBLY_ORDER rows, 6 periods, 10 RNG subsystems, 20 manifest fields and 24 row-argument exemptions. Every population below that the revision moves has a row, and each is synced by the tool.

| Population | Tree | Proposal as drafted | This revision | Delta vs the draft, and why |
|---|---|---|---|---|
| §7 entry points after S0b | 137 | — | **140** | +3: `RunClock.revise_epoch_length`, `OPT.revise_horizon`, `TOK.splice` |
| … after S1 | | 139 | 143 | +1: `DATA.render` (render from a clip reference) |
| AUD entry points | | 10 (§5) / 11 (R6) | **17** | `freeze` → `ready`; `freeze_at` KEPT (the control arm's one-shot comparison reads `AUD_FREEZE_AT` through it, K9); + `refresh` (the per-act probe, guard decision, snapshot copy and `aud.moved`, 0b.1 items 8-9); + `horizon_audit` (half-lives and holds, 0b.1 item 9); + `ready_period`, `train_period`, `refresh_period`, `probe_period`. No `ready_min`: only AUD reads `AUD_READY_MIN`, and K6 refuses an entry point no row names. §5 and R6 disagreed, and both omitted the typed Windows accessors that `_periods` requires for every AUD cadence (compose.py `_periods`: "Cadences.due REFUSES A BARE INT"). The frozen control needs no `AUD.freeze`: the root's comparison, `OPT.retire_group` and the next act's `AUD.refresh` do its work (§6.2 step 9). The hold's expiry needs no accessor either: RefreshReport carries `hold_expires_at` |
| OPT entry points at S3 | | — | +1 | `OPT.retire_group(opt, st, *, key)`: candidate retirement at the Gate and the frozen control's group (0b.1 item 6) |
| … + arms built at S3 | | — | +4 | `AUD.allocate`; `AUD.observe` / `mint` / `segment` ('bpe') |
| … after S3 / S4 / S5 / S6 | | 149 / 150 / 151 / 153 | 165 / 166 / 167 / **169** | +16 at S6 = 3 (S0b) + 1 (render) + 7 (AUD 17 against 10) + 1 (`OPT.retire_group`) + 4 (arms) |
| With VID (S7) | | 163 | **186** | VID mirrors AUD's 17: +23 against the draft |
| K13 prose restatements | | move with 137 → 153 → 163 | move with 137 → 140 → 143 → 165 → 166 → 167 → 169 → 186 | synced by the tool at each commit |
| Stubs | 14 | — | 14 | every new entry point lands implemented; arms are deferred, not stubbed |
| DEFERRED_ENTRY_POINTS | 24 | + DATA.media_batch, DATA.recover until their consumers | **22 at S0b**: `TOK.Vocabulary.decode` and `TOK.Vocabulary.blen` leave it (the MEM remap and the rescaled surprise, named in the `MEM.maintain` / `MEM.write` row texts and listed in `loop._OFF_TABLE`). Then + `DATA.render` until S3; each AUD arm entry point until its LOOP row exists | K6/K12 name the missing arguments (R6) and are restated at S0b |
| ROW_ARGUMENTS_ELSEWHERE (K10) | 24 | — | **27** at S0b, **31** at S3 | Required arguments no earlier row produces, exempted as `RunClock.begin_epoch`, `OPT.build` and `RUN.cadence_audit` are today: + `TOK.splice` (`at`), `RunClock.revise_epoch_length` (`n`), `OPT.revise_horizon` (`run_windows`) at S0b; + `AUD.ready` and `AUD.refresh` (`recover_fn`, `probe_waves`), `AUD.horizon_audit` (`run_windows`), `OPT.retire_group` (`key`) at S3. `MEM.maintain`'s entry gains `remap`, and `AUD.startup_refusals`' names the per-family clip lengths and `sr` beside `phase_plan`. Fewer if a producing row binds one |
| Wires | 19 / 25 | 21 | **21** (VID 23) | 0: the lattice reaches LM and SIG as build arguments, on the wire budget (2 left after VID). The draft's coupling `LM.d_aud_rows` stays one wire; its source tuple grows to (`AUD.enabled`, `AUD.arch`, `AUD.levels`, `AUD.strides`, `AUD.rate_mode`, `AUD.bpe_slots`) and `derive.media_rows` takes the same six, returning 0 when AUD is off |
| Frozen-signature moves | — | 6 unconditional (#1-#6) + 3 conditional | **+5** | `TOK.tokenize(view=)` [S0b, Q-TOK-15], `MEM.maintain(remap=)` [S0b, Q-MEM-13], `RUN.new_clock(resume_in_epoch=, resume_windows_in_epoch=)` [S0b, Q-RUN-16], `LM.build_model(media_lattice=)` [S4, Q-LM-13], `SIG.build(media_lattice=)` [S4, Q-SIG-3]. Move #6 (OPT `'codec'` key) is restated: OPT builds the group and never writes its lr (AUD's schedule, Q-OPT-11); it never retires except the `'codec.<s>'` losers at readiness and the frozen control's group, both through `OPT.retire_group`; `AUD.loss_terms` steps it (the Q-OPT-6 pattern). New rulings without a move: Q-OPT-10, Q-OPT-11, Q-MEM-14, Q-CKPT-5, Q-DOM-4 (the reservoir track in `DOM.observe`'s `sample_window` and `SIG.encode`'s `windows`, and `DOM.rekey`'s composed callable). Rejected routes that would have added moves: `OPT.build(codec_horizon=)` + `maybe_step(codec_events=)` (+2), `RUN.cadence_audit(horizons=, warn_frac=)` (+1) |
| Record and state shapes | — | Segmentation + modality, unit_pos, role, stride-map track | + `Segmentation.view`; `vocab_state` `rev` (run-global) and the BPE-dropout stream's state; `run.seg` (a text part with the epoch and the stream's pre-splice state; a media part with `aud.born_at`), the replay record of [0, cursor) (ids, `byte_pos`, modality, role, snapshot version), `System.novelty`, `probe_prev`, `manage_losses` and `hold_expires_at` in `payload['LOOP']`; `OptState` codec group(s), `horizon_revisions` and the retired keys; `aud.born_at`; DOM Partition reservoir `(clip_ref, frame_offset)` track | each with a restore row; geometry and resume rows (§11) |
| AUD levers | — | 17 (the §4.1 table's 16 + R12's `AUD_TRAIN_EVERY`) | **56** | −2 (AUD_STRIDE, AUD_VERSION) + 39 new (the §7 table, `AUD_NFFT`, `AUD_SHIFT_STAMP` and `AUD_CODEC_GRAD_CLIP` included) + `AUD_CODEC_LR_MIN_FRAC` (new here, in place of the first revision's `OPT_CODEC_LR_MIN_FRAC`) + `AUD_CODEC_LR` (the draft's `OPT_CODEC_LR`, renamed into AUD): 15 kept + 41 |
| Other levers | 262 | (proposal's DATA / LM / OPT / WORLD / FAB / EVAL additions) | +11 new, −1 moved | OPT +4 (`OPT_HORIZON_REVISE`, `OPT_CODEC_BETA1`, `OPT_CODEC_BETA2`, `OPT_CODEC_WEIGHT_DECAY`), LM +2, SIG +1, DATA +2, WORLD +2; `OPT_CODEC_LR` leaves OPT (renamed `AUD_CODEC_LR`); `WORLD_MEDIA_HORIZONS` renamed `_S` |
| Lever total vs the draft | | | **+49** net (audio stages) | +39 (AUD: 56 − 17) + 10 (11 new − 1 moved out of OPT). VID at S7 mirrors AUD's new levers where they apply: at most +39 more, fixed at S7 |
| Census amendment rows (`.rework/census.json`) | | one per new lever | **+51 addition rows, 2 removal rows, 2 rename rows** (net +49 levers) | 40 AUD + 11 other additions; removals AUD_STRIDE, AUD_VERSION; renames `WORLD_MEDIA_HORIZONS` → `_S` and `OPT_CODEC_LR` → `AUD_CODEC_LR` (N2); VID's rows at S7 |
| U.FRACTION population | | | **+18** | AUD_RATE_TOL, AUD_ALLOC_RHO, AUD_BPE_TALLY_DECAY, AUD_READY_MARGIN, AUD_READY_PLATEAU, AUD_SHIFT_FLIPS, AUD_HALF_LIFE_WARN, AUD_ANCHOR_MARGIN, AUD_REHEARSE, AUD_REWARM, AUD_CEIL_DROP, AUD_CODEC_LR_MIN_FRAC, AUD_CODEC_GRAD_CLIP, OPT_CODEC_BETA1, OPT_CODEC_BETA2, OPT_CODEC_WEIGHT_DECAY, LM_MEDIA_GMM_W, DATA_MEDIA_REHEARSE (and AUD_CODEC_LR if the draft had not already labelled OPT_CODEC_LR U.FRACTION, as OPT_LR is). `AUD_ANCHOR_W` is U.COUNT, domain (0, 100), the `SIG_VAR_WEIGHT` precedent (+1 to U.COUNT) |
| Unit labels (`spine/units.py`) | 15 labels | HZ, FRAMES (§3.2; Appendix A adds CODES) | **+3**: U.HZ, U.FRAMES, U.SAMPLES | HZ for `DATA_AUD_SR` (the draft's), FRAMES and SAMPLES for the analysis grid (§7). CODES is not declared: no lever carries it |
| Clock-unit levers (K9) | | AUD_FREEZE_AT, AUD_TRAIN_EVERY | + AUD_READY_EVERY, AUD_REFRESH_EVERY, AUD_PROBE_EVERY (each through its period accessor; AUD_FREEZE_AT through `AUD.freeze_at` for the one-shot comparison). AUD_READY_MIN is read inside AUD only (the Gate, the horizon, the startup refusal). AUD_EMA_HALF_LIFE, AUD_REWARM_WINDOWS and AUD_CEIL_HOLD_WINDOWS are durations converted by the new derive functions and stated by `AUD.horizon_audit`, not cadences | — |
| Named derive conversions (`spine/derive.py`, O11) | 20 functions | the draft's S1 media functions (`media_id`, `media_rows`, `frames_per_second`, …) | + `codec_steps_from_windows`, `ema_decay_from_half_life`, `latent_frames_from_seconds` (S3), with known-answer rows in `tests/test_derive.py`; `media_rows` takes six arguments; `frames_per_second` refuses only a non-integer grid (sr / hop), so 12.5 is legal | 0b.1 items 9 and 11; 0b.6 |
| Periods (compose `_periods`) | 6 | (the draft's aud.freeze) | **10** at S3 | + `aud.ready`, `aud.train`, `aud.probe` and `aud.refresh`, all unconditionally in the returned literal K9 and K13 read (`aud.refresh` reads 0, DISARMED, under 'jit_ema'), so `RUN.cadence_audit` states them. `aud.freeze` is not a period: it is a one-shot Windows comparison, and a zero period at the default would print DISARMED on every run (0b.1 item 9) |
| RNG subsystems | 10 | + aud, aud.train | **13** | + `aud.probe` against the draft. The act draws no seed: BPE-dropout continues the one `tok.dropout.mint` stream, whose state now crosses the save in `vocab_state` |
| Manifest fields (`_geometry_manifest`) | 20 | aud.enabled, arch, sr, hop, stride, levels, d, version + LM / WORLD media fields | **35** at the audio stages | the 15 fields of §11's table, each with its `absent=` off value. Against the draft: − aud.stride, − aud.version (payload-side now), + aud.nfft, aud.hid, aud.strides, aud.seg_frames, and the rows-mode fields; `lm.media_rows.aud` becomes MAY_WIDEN |
| LOOP_ORDER rows | 63 | the draft's AUD rows | **67** at S0b, then the draft's rows restated at S3 and S4 | +4 at S0b: the act's X rows, one per package call (`TOK.splice`, `RUN.RunClock.revise_epoch_length`, `OPT.revise_horizon`, `DOM.on_retokenize`), because `_rows_by_stage` credits a name only from its own row (0b.1 item 13). At S3: `AUD.loss_terms` (A, evaluated per window, whole run; §6.2 step 1), `AUD.ready` (A, on `aud.probe`, readiness), `AUD.refresh` (X under 'snapshot'; A on `aud.probe` under `'jit_ema'`), `OPT.retire_group` (A), and the cut-time `AUD.encode`, which replaces the draft's `AUD.encode` at the roll. At S4: `DOM.rekey` at X. The draft's `aud.freeze` row is gone (the control arm's retirement is the `OPT.retire_group` row) |
| ASSEMBLY_ORDER rows | 40 | the draft's AUD build row | 40 at S0b; +1 at S3 beyond the draft's AUD rows | 0 at S0b. Two notes change. On a mid-epoch resume carrying `run.seg`, the 'segment' row rebuilds the Segmentation from the replay record and `TOK.splice` instead of its whole-stream `tokenize` (its segmentation work is not counted twice: TOK's counters cross the save in `vocab_state`, so the root snapshots `vocab.counters` before the rebuild, puts them back after it, and only then counts the rebuild once in `tok.segment_resume`, the Q-TOK-15 `tok.segment_remap` precedent; the resume's own rows, `tok.state_restored`, `tok.tally_restored`, `tok.load_reconciled(_detail)`, `tok.bpt_adopted` and `tok.bpt_mismatch`, are written before the snapshot as they are today), before 'optimizer', so `OPT.build` sees the post-act length; the epoch-0 row writes `run.seg` and on that resume skips `begin_epoch`. At S3: `AUD.horizon_audit` on the 'audit' stage, beside `RUN.cadence_audit`, plus the draft's AUD rows |
