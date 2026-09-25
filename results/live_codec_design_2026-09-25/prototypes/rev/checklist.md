# Checklist: every critic issue, every missing item and every round-2 to round-5 checker finding → where `03_live_codec.md` answers it

Each entry gives the section of `03_live_codec.md`, then the answering sentence or sentences, quoted verbatim. Every quote was checked against the file by exact substring match after the round-5 revision (script: `rev/parts/checkq.py`; its two reported misses are a finding's name, not a quote, and a quote whose `\|` escape the script strips).

Round 1 (the critic): 1 blocking, 9 major, 8 minor, and 14 missing items. Round 2: three checkers, 73 findings (19 major, 54 minor, none blocking; several majors from different checkers name the same resume defect). Round 3: three checkers, 55 findings (14 major, 41 minor, none blocking). Round 4: one checker pass, 38 findings (7 major, 31 minor, none blocking). Round 5: one checker pass, 32 findings (4 major, 28 minor, none blocking). Every one is mapped below. The decision that governs each round-1 item is noted in brackets (D-1 … D-10, MINORS).

---

## Round 1 — Blocking

### B1 — The S0b resume rule fails when TOK mints (or the teacher moves) between acts [D-1]
- **0b.1 item 14**
  > The checkpoint records the view of the last TEXT SEGMENTATION (an epoch start, or an act that splices; item 13), and TOK segments at that view: ids minted after it become visible to the stream at **the next act that carries TOK's retok Due** (≤ `TOK_RETOK_EVERY` windows).

  > A resume rebuilds the Segmentation from the last act's recorded state and the consumed prefix's replay record, so it is **bit-exact against the uninterrupted run**, for a save at an optimizer-step boundary with the stream's Configs unchanged (§11).

  > 2. It gives `TOK_RETOK_EVERY=0` the meaning its former help text claimed. Q-RUN-8 (`docs/04_CONTRACT.md` line 4261) says that meaning needs exactly "a vocabulary that excludes what was minted since the last segmentation".

  > A TOK "segment at view" capability: the keyword signature move `TOK.tokenize(..., view=None)` with a Q-TOK ruling (Q-TOK-15, next free); `Segmentation.view`; `rev` and the dropout stream's state in `vocab_state`.

  > save between a mint and the next act; between a retire and the next act; between a reinstatement and the next act; two resumes in one run; one window after an act; at `TOK_DROPOUT > 0`

  > **(a) "a resume is an act".** Bit-identity would hold only against a run that also acted at the save point.

  > **(c) "mint only at acts".** It would change TOK's own measured mint dynamics as a side effect of a resume fix
- **§11** (media side and the teacher)
  > Media in the tail is laid out and coded by the media part's snapshot, stride maps and merges, never by the codec or teacher as it has since moved

  > save mid-run under `'jit_ema'` (the teacher's state), k windows after an act with k > `AUD_TRAIN_EVERY`, so positions [p, cursor) were cut by several teacher states;
- **§13 S0b, Tests row**
  > 9. **save between a mint and the next act** (the blocking case);
- **Contract accounting**
  > `TOK.tokenize(view=)` [S0b, Q-TOK-15]

*Correction to D-1's stated reason (1).* The decision said bit-exact resume "is a tree invariant (tests/test_resume.py, test_resume_clock.py)". The tree says the opposite (a round-2 checker verified it: C9 asserts a warned replay, Q-RUN-10 kept it, Q-TOK-13 left continuation OPEN). The text keeps option (b) and restates the reason truthfully:
  > **Bit-exact continuation becomes a tree invariant here. It is NEW, not inherited.**

---

## Round 1 — Major

### M1 — The default 'nested' fails its own switch criterion [D-2]
- **0b.1 item 4**
  > **4 — ARCHITECTURE `AUD_ARCH='spec'`; `'nested'` IS AN ARM.**

  > melody timbre is lower under nested at **3/3 seeds** (0.359/0.375/0.531 vs 0.500/0.609/0.578)

  > *S3 decides.* The pre-declared criterion at 2 seeds, INCLUDING per-attribute recover exact on every attribute, decides whether 'nested' becomes the default.
- **0b.2 row 14, and "Row 14, every attribute"**
  > **Row 14, every attribute.** Recover exact on reconstructions: nested / spec, both live, table rows, at s0 / s1 / s2.
- **§6.1**
  > **Pre-declared switch.** `AUD_ARCH` becomes `'nested'` only if S3 shows, at both of 2 seeds, that nested at every candidate stride is no worse than the matching 'spec' codec by more than 2 SE of the paired difference
- **§13 S3 acceptance**
  > **'nested' vs 'spec'** by the pre-declared criterion at 2 seeds, with its non-inferiority margin, including per-attribute recover exact on every attribute of every family (§6.1). The result sets `AUD_ARCH`.

### M2 — A live codec lowers recover exact (the primary reading) while mel improves; the default re-creates the worst regime
- **0b.1 item 8**
  > **8 — RECOVER EXACT IS THE CODEC'S ACCEPTANCE METRIC, AND ITS GUARD ACTS BEYOND THE MEASURED SPREAD.**

  > The robust part is timbre. That is an objective misalignment (L1 on log-magnitude and magnitude does not weigh harmonic structure), not a codec defect

  > - Its action on a calibrated family (`AUD_CEIL_ACTION='hold'`):

  > - S3 builds a harmonic / multi-resolution spectral loss arm BEFORE re-warm may default on.
- **0b.1 item 7** (re-warm ships 0)
  > **7 — RE-WARM SHIPS OFF.** `AUD_REWARM` 0.

  > 0.3 × peak = 3e-4 is the "hot" learning rate of D3's ttc25 and of the judge's live25hot, the regime with the largest timbre drop.
- **0b.1 item 2** (readiness on recover exact)
  > per-attribute recover exact on reconstructions of `AUD_PROBE_N` (400) fixed held-out clips of the readiness areas meets the **family floor**.
- **0b.2 row 15**
  > A live codec improves mel and lowers TIMBRE recovery (D3, where timbre is recorded); exact match falls in D1 (which records exact match only) and is mixed in D3
- **§13 S3 acceptance**
  > **The CPU acceptance** replaces "probe ceiling ≥ 30%": mel < 0.6, codes_used ≥ 300, and per-attribute recover exact at the aud/tones family floor within 5 CPU-minutes

### M3 — The default plasticity is not the measured regime; the schedule horizon is unspecified; the default cadence's cost is missing [D-4, D-10]
- **0b.1 item 6** (the exact measured settings, and the cadence chosen by measurement)
  > **6 — PLASTICITY IS D1's MEASURED LOW-PLASTICITY REGIME**

  > one codec step per 4 LM steps × 8 windows = **one per 32 windows** (308 steps over 9866-9871 windows)

  > **The cadence.** `AUD_TRAIN_EVERY` 32 because 1/32 is the only cadence with a paired live-vs-frozen measurement at 4 LM seeds (D-4: the default is the regime measured against frozen).
- The schedule horizon:
  > to `AUD_CODEC_LR_MIN_FRAC` 0.05 (5e-5) over `derive.codec_steps_from_windows(AUD_READY_MIN, AUD_READY_EVERY)` = 750 codec steps, then the floor for the rest of the run; never zero
- The label, measured only in this regime:
  > **The label "no consistent LM-side cost" is measured only in this regime: 25 Hz, D1's 4000-step pre-trained codec, one codec init, one LM step per 8 windows.** It compares matched LM steps, NOT matched compute
- **0b.1 item 5** (snapshot codes, the mechanism D1 actually measured)
  > **5 — CODES ARE CUT BY A SNAPSHOT, REFRESHED AT EVERY ACT.** `AUD_CODES='snapshot'`.
- **0b.2 row 3** (the critic's 1/4 rerun)
  > The same stack at one codec step per **4** windows (8× denser)
- **§12** (cost of the default cadence)
  > codec 2.0 ms/window (+16% of the LM's 12.0 ms/window); just-in-time re-encode 1.2 ms/window

  > **The GPU cost is owed.** R12's bench arm runs before any S3 default is fixed
- **§13 S5 (ii)**
  > **(ii) Plasticity:** {snapshot-at-act, just-in-time EMA} × {the measured cadence 1/32, 1/4} × {anchor 0, 10} × {ceiling hold, count}

### M4 — The anchor evidence is misattributed; the retargeted anchor is unmeasured [D-7]
- **0b.1 item 6, the anchor paragraph**
  > *The anchor is a measured value, not a settled mechanism.*

  > The earlier claim that the anchor is "measured load-bearing" is **dropped**:

  > the LM-level evidence compares live25 with live25free, which differ in snapshot AND anchor (`d1/run_arm.py:40-41`), so the two cannot be separated;

  > codec-only (D1's **50 Hz codec**, `codec50.pt`, 200 area-A + 300 area-B codec steps, one seed), after area B the anchored codec is not better on area A: mel 0.4994 vs 0.4955 (within noise), recover 0.264 vs 0.347 (about 1.5 unpaired SE at n = 144, one seed).

  > The missing arms are added. S5 crosses {anchor 0, 10} with {snapshot, jit_ema}

  > Retargeting the anchor to an EMA teacher's lattice point applies only under `AUD_CODES='jit_ema'` and is **unmeasured**.
- **0b.2 rows 6 and 16**
  > **Confound:** live25free differs from live25 in snapshot AND anchor (`d1/run_arm.py:40-41`)

  > The codec-only anchor: fewer flips; not better on area A after B
- **§13 S3** (A-after-B recover exact is an acceptance reading)
  > Readings: flips per 50 steps; codec BWT on A after B as mel AND per-attribute recover exact (an acceptance reading)

### M5 — The coordinate-row rationale is wrong (they are MORE stale-sensitive); stale-code range is cherry-picked [D-6]
- **0b.1 item 11**
  > *Reason, restated as SAMPLE EFFICIENCY measured at 600-1200 media LM steps, not drift tolerance.*

  > coordinate rows make the LM MORE sensitive to stale codes, at 3 of 3 seeds with both row types (6 of 6 readings)

  > **Drift mitigation is carried by the snapshot hold (item 5) and the anchor (item 6), not by the rows.**

  > *Cost.* Higher cross-area interference at 4/4 seeds: the earlier area's bits/s rises +42 to +59 after the next area, against +34 to +41 with table rows.

  > `'table'` stays a LIVE S5 arm, and a longer / larger-data check (S5) runs before coordinate rows are unconditional
- How the lattice reaches LM:
  > The lattice reaches LM through an **`LM.build_model(..., media_lattice=None)` argument**, the `open_store(key_dim=LM.width)` idiom. It is one counted signature move, and no 22nd wire.
- **0b.1 item 10** (the full stale-code range; D-6's "+2.6% to +15.1%" widened to +15.7% by the reproduction's s2/s3 records, per a round-2 finding)
  > codes 600 LM steps stale: +2.6% to +15.7% LM bits/position under an EMA teacher (D3; table rows 3 seeds, coordinate rows 4 seeds; s2/s3 derived from the reproduction's records)
- **§13 S5 (iv)**
  > **(iv) Coordinate vs table rows** at 20k windows with at least 10× the prototypes' media LM steps.

### M6 — The routing stack (SIG, DOM, FAB, MEM) under a moving tokenizer is neither designed nor measured [D-8]
- **0b.1 item 16**
  > SIG 'typed' embeds a media unit by the same coordinate composition as the LM rows, not by a free code table.

  > New gauge `sig.media_drift`: the signature change on fixed probe clips at each refresh.

  > The stamps reach two consumers today: `FAB.grow_check(shift_at=)` (FAB's cooldown) and `OPT.maybe_step(shift_at=)` (inert at `OPT_LR_SHIFT_WARM` 0).

  > What protects it is a re-key at the act: `DOM.on_retokenize` when the text view moved, and `DOM.rekey` with a root-composed callable (`DATA.render` → the new snapshot's `AUD.encode` → `SIG.encode`) when the snapshot was refreshed after media was consumed.

  > **Per-byte levels, and how they meet R11's running baselines.**

  > That value is hand-set (the critic asked for a flip-rate threshold without giving one), and it is an arm-only lever.
- **§13 S5 (iii)**
  > **(iii) Routing stack.**

  > Readings: `part.n_created` and `part.n_culled` (DOM spawns and culls), `fab.grown_regression`, `fab.grown_stall` and `fab.births` (FAB growth), `fab.cull_util` and `fab.cull_fail`, `sig.media_drift`, the per-byte levels, and the FAB blackout share
- **Contract accounting** (the DATA render entry point that the DOM callable uses)
  > +1: `DATA.render` (render from a clip reference)

### M7 — The S0b act is wrong on an interleaved stream [D-9]
- **0b.1 item 15**
  > 1. Find the unit under the cursor `at` (a text token, or a whole clip record `[task] BEGIN codes END`). `at` is always the cursor k0, in the act and in the resume.

  > 3. Re-tokenize the text tail from the next text byte, at the given view.

  > 4. Re-run `TOK.interleave` on the tail.

  > Segmentation ownership stays TOK's, through a TOK splice helper (+1 entry point)

  > It owns `tok.retok` (or `tok.relay` at a relay-only act), `tok.byte_fallback` and `tok.dropout_skip` for its call

  > Under `'bpe'`, codes are held from the act (encoded by the act's snapshot and merged at the act's merge revision), not cut just in time.

  > Known-answer test: a cursor inside a clip.
- **§13 S4**
  > **a cursor inside a clip**: the clip appears once, whole, in the prefix; no clip is duplicated or dropped; unit_pos stays monotone;
- **§13 S0b, TOK row**
  > **`TOK.splice(tok, vocab, seg, data, labels, *, at, view=None, media=(), id_fn=None, regularize=False, stream_state=None) -> Segmentation`** (+1 entry point)

### M8 — The rate is still 25 Hz fixed by hand, and not listed as such [D-3]
- **0b.1 item 3**
  > **3 — THE RATE IS MEASURED PER RUN AT READINESS.** `AUD_RATE_MODE='measured'`.

  > the coarsest stride whose per-attribute recover exact on reconstructions stays within `AUD_RATE_TOL` (0.05, absolute) of the finest stride's

  > The cost is about 3× the codec cost, and 3× the probe cost, until readiness, and zero after

  > If the chosen stride differs, the readiness act re-lays the unconsumed media tail at it. No media has been consumed yet, so no LM work is lost.

  > **'measured' itself was NOT prototyped.**
- The fixed stride as control, and the "not necessary" listing (0b.3):
  > | The fixed-stride control, `AUD_RATE_STRIDE` 2 | It is a control arm and the provisional compose layout, not a choice | stays a control |

  > | One stride per run (`'measured'`) rather than per segment | 'alloc' and 'bpe' adapt per segment | S5 rate sweep on 2-4 s clips (item 3) |
- AUD_RATE_TOL and the grid in "what stays fixed" (0b.3):
  > **A decision threshold, not a rate.**

  > **the grid is the audio byte**
- **§11 R-RATE** (resume-time stride change)
  > A resume-time stride change is refused unless an act re-lays the unconsumed tail.

  > the other stride block's slot vector is reported as untrained (`lm.media.block_untrained`).
- **§13 S5 (i)**
  > plus the pair the critic found missing: nested fixed-stride vs nested 'alloc', both with coordinate rows.
- The tie-break the critic flagged:
  > On the toy readings, with bits/s set aside, the D3 'alloc' and fixed pairs tie on the codec-invariant readings (0b.2 row 12), so this tie-break would have favoured 'alloc' (on tones 22-23 against 26 positions per second; on melody 24.9-25.6 against 26)

### M9 — Seed and budget labels overstate independence and fairness [D-10]
- **0b "Words used below"**
  > so D1 codec readings are **one codec init × N LM/stream seeds**
- **0b.2 row 1, and row 4**
  > 4 LM/stream seeds × **ONE codec init**

  > **Not step-matched**: the frozen codec stopped at 1500 codec-phase steps, the live arms got 600 more at 3e-4

  > Not codec-step-matched: the frozen codec took no further step, the live one +308 at 5e-5
- **§12**
  > **"No consistent LM-side cost" is at matched LM steps, not matched compute and not matched codec steps.**
- **§13 S5 (ii)** (the step-matched and compute-matched controls)
  > a **step-matched** frozen control **per cell**: its codec takes the same total number of codec steps as that cell's live arm takes by the end of the run, all before the first media window, then freezes (`AUD_FREEZE_AT` at the Gate's first test).

  > a **compute-matched** frozen control, which gets the codec's compute as extra LM steps.
- **§16 row 28**
  > Every S5 plasticity cell reports step-matched and compute-matched frozen controls, labelled.

---

## Round 1 — Minor

### m1 — The readiness threshold 0.30 is not met and comes from a different probe
- **0b.1 item 2**
  > It is calibrated per family at S3 on recover exact: the S3-measured per-attribute plateau at 2 codec seeds minus `AUD_READY_MARGIN` 0.05

  > On recover exact, D3's codecs and D1's melody reading fall below it, and D1's tones reading passes:

### m2 — Codec training data at readiness is unspecified
- **0b.1 item 2**
  > Readiness trains on `AUD_READY_AREAS`. The default is the first media area in `DATA_PHASE_SCHED`; the root resolves '' against DATA's phase plan and passes the areas to `DATA.media_batch`

  > Later areas are unseen by the codec until their phase starts.
- **§6.2 step 4**
  > From the first media window on, crops are drawn from clips the stream has consumed, rendered from their references by `DATA.render`.

### m3 — Contract accounting is incomplete
- **Contract accounting**
  > **Method.** At every stage commit, `python3 tools/sync_counts.py` rewrites the counts in `docs/` and `src/` from `tests/test_contract.py::k13_live_counts`

  > | AUD entry points | | 10 (§5) / 11 (R6) | **17** |

  > 0: the lattice reaches LM and SIG as build arguments, on the wire budget (2 left after VID).

  > | U.FRACTION population | | | **+18** |

  > **+51 addition rows, 2 removal rows, 2 rename rows** (net +49 levers)
- The DOM / EVAL encode callables are root joins, and the DOM reservoir's reference track is a counted state-shape change:
  > DOM Partition reservoir `(clip_ref, frame_offset)` track

### m4 — Clock kinds and units are mixed; the only hidden-freeze guard is EMA ≥ 1
- **0b.1 item 9**
  > Every codec time constant is declared in U.Windows and converted through named derive functions.

  > It **warns** when an armed half-life, or the longest possible hold (`AUD_REFRESH_EVERY + AUD_CEIL_HOLD_WINDOWS` = 4000 windows), exceeds `AUD_HALF_LIFE_WARN` 0.25 × run_windows.

  > New reading `aud.moved`: did the **live codec** move since the last reading, in parameters and in probe codes.
- **0b.1 item 17 / §10** (horizons in SECONDS)
  > The horizons are `WORLD_MEDIA_HORIZONS_S` '0.04,0.2'. units.py has SECONDS and no milliseconds label.
- **§7** (units are units.py labels)
  > **Reading the "Unit" column.** Every unit is a label or Clock kind declared in `spine/units.py`
- **0b.1 item 7** (the recon-rise re-warm alternative)
  > Re-warm triggered by a rise in reconstruction loss on fresh clips (the SIG floor-skip pattern) is an arm.

### m5 — Did-it-fire and inert-lever hygiene
- **§7**
  > **Reading the "Gate" column.** For a lever read only by an arm, or inert until something is calibrated, the column names the did-it-fire surface.
- **0b.5**
  > `tok.retok_deferred` and `tok.retok_satisfied_by_roll` become ABSENT, with reason "S0b: the act runs mid-epoch; nothing is deferred to a roll".

  > Therefore **neither the media-arrival stamp nor any act stamp re-warms the LM**.
- **§13 S0b, LOOP row**
  > **Final-window rule:** a Due raised by the flush that finishes the run has no tail to act on, so it is counted in `tok.retok_at_finish` (PRESENT), never in `due_dropped`.

### m6 — The EMA teacher is on by default with no LM-level support
- **0b.1 item 5**
  > **Its measured value so far is a lower flip rate, not LM bits:**
- **0b.2 row 7**
  > An EMA teacher lowers the flip rate; no LM bits/s difference (a codec-dependent unit, one seed)
- **§6.6**
  > | Just-in-time EMA-teacher codes as the default | An arm (`'jit_ema'`). Its measured value is flip rate, not LM bits. |

### m7 — The S0b ship rule, the 17 MB tail cost, per-token consumers, and LR continuity
- **§13 S0b, measurements row**
  > **Ship rule, non-inferiority, margin from paired-difference noise.** Let M = max over seeds of \|bpb₀(s) − bpb₀′(s)\|, the two control runs' paired spread.

  > (3) Time `TOK.tokenize` and `TOK.splice` on a 17 MB tail.
- **§13 S0b, Levels row**
  > The root hands `DOM.note_competence`'s bits as bits per build-time token
- **§13 S0b, OPT row**
  > It is **LR-continuous**: it remaps the rest of the schedule so that lr(now) is unchanged and the remaining cosine reaches the floor at the new end.

### m8 — "Liveness does not touch text" was measured on toy text
- **0b.2 row 22**
  > Codec liveness did not move **toy** text

  > **Toy text:** an order-2 Markov process over 15 symbols, with no TOK, SIG, DOM, FAB or MEM

---

## Round 1 — Missing items (critic, 1-14)

| # | Missing item | Section | Answering sentence |
|---|---|---|---|
| 1 | A resume design that works when the vocabulary or teacher changes between acts, with a mint-then-save known-answer test | 0b.1 item 14; §11; §13 S0b | "A resume rebuilds the Segmentation from the last act's recorded state and the consumed prefix's replay record, so it is **bit-exact against the uninterrupted run**, for a save at an optimizer-step boundary with the stream's Configs unchanged (§11)." / "9. **save between a mint and the next act** (the blocking case);" |
| 2 | The act on an interleaved text+media stream: re-interleave, a cursor inside a clip, Segmentation ownership | 0b.1 item 15; §13 S4 | "Segmentation ownership stays TOK's, through a TOK splice helper (+1 entry point)" / "**a cursor inside a clip**: the clip appears once, whole, in the prefix" |
| 3 | SIG / DOM / FAB / MEM under a moving media tokenizer, with gauges | 0b.1 item 16; §13 S5 (iii) | "New gauge `sig.media_drift`: the signature change on fixed probe clips at each refresh." / "Readings: `part.n_created` and `part.n_culled` (DOM spawns and culls), `fab.grown_regression`, `fab.grown_stall` and `fab.births` (FAB growth), `fab.cull_util` and `fab.cull_fail`, `sig.media_drift`, the per-byte levels, and the FAB blackout share" |
| 4 | The combination the synthesis shipped was never run, and owner-scale drift was never run | 0b.1, "What of this stack was measured together"; §6.4 | "The combination the judge shipped (just-in-time EMA codes + teacher-targeted anchor + re-warm + one step per 4 windows) was never run in a stream." / "Owner-scale drift (about 530 live codec steps at the default cadence in 20k windows) is unmeasured, and `aud.flip_cum` reports it." / the shipped stack's own differences: "*Where the shipped default differs from that stack* (none of it measured):" |
| 5 | A step-matched frozen control, and more than one codec init on the D1 side | §13 S5 (ii); §13 S3 | "a **step-matched** frozen control **per cell**: its codec takes the same total number of codec steps as that cell's live arm takes by the end of the run, all before the first media window, then freezes (`AUD_FREEZE_AT` at the Gate's first test)." / "It runs at **2 codec inits**, on area A then area B." / "Seeds vary the codec init as well as the LM, which D1 did not." |
| 6 | Paired nested fixed vs nested 'alloc' with coordinate rows; any rate measurement on 2-4 s clips | §13 S5 (i) | "plus the pair the critic found missing: nested fixed-stride vs nested 'alloc', both with coordinate rows." / "Four pre-declared matrices at **2 paired seeds**, GPU, 2-4 s clips." |
| 7 | A data-chosen per-run rate at readiness, through the act | 0b.1 item 3; §6.3 | "If the chosen stride differs, the readiness act re-lays the unconsumed media tail at it. No media has been consumed yet, so no LM work is lost." |
| 8 | The codec group's schedule horizon | 0b.1 item 6; §6.2 step 1 | "Each group follows a cosine from `AUD_CODEC_LR` 1e-3 to `AUD_CODEC_LR_MIN_FRAC` × peak (5e-5) over `derive.codec_steps_from_windows(AUD_READY_MIN, AUD_READY_EVERY)` = 750 of its own steps, then holds the floor." |
| 9 | Readiness-phase training data | 0b.1 item 2 | "Later areas are unseen by the codec until their phase starts." |
| 10 | A readiness threshold calibrated on the metric actually used | 0b.1 item 2; §13 S3 | "It is calibrated per family at S3 on recover exact" / "The per-family floor is measured at 2 codec seeds, on aud/tones first." |
| 11 | An action, not only a count, when a per-attribute ceiling drops | 0b.1 item 8; §13 S3 | "the next snapshot refresh is withheld, so the LM keeps the last snapshot whose ceiling held;" |
| 12 | The cost of the default cadence (CPU measured; GPU owed) | §12 | "codec 2.0 ms/window (+16% of the LM's 12.0 ms/window); just-in-time re-encode 1.2 ms/window" / "**The GPU cost is owed.** R12's bench arm runs before any S3 default is fixed" |
| 13 | The re-tokenization cost of a 17 MB text tail | §12; §13 S0b | "**unmeasured at the owner's 17 MB tail; S0b measures it.**" / "(3) Time `TOK.tokenize` and `TOK.splice` on a 17 MB tail." |
| 14 | A K13 / census / wire / entry-point recount, including a DATA render entry point and how coordinate rows receive the lattice | Contract accounting | "+1: `DATA.render` (render from a clip reference)" / "0: the lattice reaches LM and SIG as build arguments, on the wire budget (2 left after VID)." |

---

## Round 2 — checker findings → where answered

Numbers were re-verified against the preserved records before any change (D1 `d1/res`, `judge/d1c/res`, `repro/d1/res`, `critic/d1r/res`; D3 `d3/res`, `repro/d3/res`, `d3/res/drift_summary.txt`; D1 codec-only `d1/res_codec`; the tree's `src/` and `docs/04_CONTRACT.md`).

### Checker 1 (design and mechanics)

| Finding | Section | Answering sentence |
|---|---|---|
| MAJOR segment-at-rev not computable (per-process rev; reinstatement) | 0b.1 item 14; §13 S0b TOK | "**`vocab.rev` becomes run-global.**" / "**Segment at a view.** TOK builds the view's match table from `id2bytes[:size]` minus `retired`" |
| MAJOR the stamp omits the retained unit and the look-back; `at` inconsistent | 0b.1 item 14; §11 | "**The replay record covers the whole consumed prefix, [0, cursor), as held in memory at the save.**" / "`at` is the last text segmentation's cursor k0 in both that act and the resume, so the splice lands at the same p and lays out [p, end) as the act did." |
| MAJOR an AUD-only act re-segments text | 0b.1 item 13; §13 S0b LOOP; §13 S3 | "**What the act does to text depends on which Dues it carries.**" / "**`TOK_RETOK_EVERY=0` with AUD refresh acts:** no id minted after the last text segmentation appears in the stream" |
| MAJOR the ceiling guard fires in the measured regime | 0b.1 item 8; §13 S3; §13 S5 (ii) | "The threshold is calibrated per family at S3: the live-vs-frozen drop measured at the default plasticity at 2 codec seeds, plus 2 SE of the paired difference" / "**'hold' at the calibrated threshold is not a measured regime.**" |
| MAJOR the shipped codec differs from D1's (budget, data, rate) | 0b.1 item 6; "What of this stack…"; §13 S3 | "*Where the shipped default differs from that stack* (none of it measured):" / "**The D1-harness replica of the shipped default**" |
| minor refresh at every act (D-5) | 0b.1 item 5 | "It is refreshed at **every** act, as decided (D-5)" |
| minor 18/18 misattributed | 0b.1 item 1; 0b.2 row 1 | "6 table-row readings (original) + 6 lattice-row readings (judge) + 12 new-seed readings (reproduction, claim 3" |
| minor cost table mixes bases | §12 | "**Two bases, stated side by side.**" |
| minor probing never costed | §12; 0b.1 item 2 | "**Probing** (encode, Griffin-Lim 32 decode, analytic inverse)" |
| minor S0b margin loose; cadence 0 always ships | §13 S0b | "Cadence c ∈ {3000, 1000} ships if bpb_c(s) − bpb₀(s) ≤ M at EVERY one of the 3 seeds." |
| minor strict switch criteria; S5 all vs each | §6.1; §13 S3, S5 | "Strict ≥ comparisons are not used" / "it is no worse than the default on **every** codec-invariant primary by more than 2 SE of the paired difference, and better on **at least one** of them beyond that margin." |
| minor EMA half-life from the wrong cadence | §6.2 step 8; §7 | "The arm matches it **in codec steps**" |
| minor inert levers without Gates; hold unit; aud.moved | §7; 0b.1 items 8-9 | "`aud.refresh.*` ABSENT under 'jit_ema', reason \"AUD_CODES='jit_ema': no refresh event\"" / "`aud.ready.by_floor` ABSENT, reason \"no family calibrated (S3)\", until one is" / "It is read on the live codec, not on the snapshot" |
| minor DOM reservoir references | 0b.1 item 10; §13 S4 | "`_sample_window` (compose.py:3391) returns its units plus a parallel `(clip_ref, frame_offset)` track for media units" |
| minor TOK.splice lacks dropout arguments | 0b.1 item 15 | "It takes `regularize` like `tokenize` (`tok/api.py:1320`). It takes `stream_state`, the BPE-dropout stream's recorded position, instead of a `seed`" |
| minor rate chosen from the first area only | 0b.1 item 3; 0b.3 | "The stride chosen on the readiness areas only and used for every later area" / "`'measured_arrival'`: 'measured', plus a re-measure at each new media area's arrival" |
| minor no clip consumed after the Gate; Gate under 'measured' | 0b.1 item 2; §6.2 step 3 | "After the Gate and until the first media window" / "Under `'measured'` there are three candidate codecs. The Gate then reads:" |
| minor supersede list incomplete | 0b.6 | "- R1: \"`F = clip_s(family) × derive.frames_per_second(...)` known from levers at compose\"" / "- R11 and §3.3 are amended, not replaced" / "- S8: \"(h) Codec version handover" / "These figures hold at 25 Hz only" |
| minor row 13 is the nested codec | 0b.2 row 13; 0b.1 item 3 | "**D3's nested codec with forced strides, codec-only, n = 36 (tones) / 32 (melody) probe clips; per-stride 'spec' codecs were never measured**" |
| minor "every harness" overgeneralised | headline; item 8; row 15 | "A live codec improves mel and lowers TIMBRE recovery wherever timbre is recorded (D3)" |
| minor fixed-stride labels | 0b.1 item 3 | "a fixed stride (2 in D3 and D2; 1 in D1's 'bpe' pair) beat or tied every per-segment adaptive route **on LM bits/s** (3 seeds for D3 and D1, 2 for D2; 0b.2 row 12)" |
| minor VID levers uncounted | Contract accounting; §7 | "VID at S7 mirrors AUD's new levers where they apply: at most +39 more, fixed at S7" |
| minor SE of a difference | §6.3 | "**Probe size, on the paired difference.**" |
| minor R7 fixture timing | 0b.6; §13 S0b Tests | "the fixture is recorded at the **S0b** base commit" |
| minor S3 resume under jit_ema | §11; §13 S3 | "save mid-run under `'jit_ema'` (the teacher's state), k windows after an act with k > `AUD_TRAIN_EVERY`, so positions [p, cursor) were cut by several teacher states;" |

### Checker 2 (numbers and labels)

| Finding | Section | Answering sentence |
|---|---|---|
| MAJOR "costs the LM nothing" rests on bits/s only | headline; items 1, 6; row 1; §12; §16 Q14 | "on the **LM side** there was **no consistent cost, and no gain**: caption bits/byte worse in 11 of 16 paired readings (−8.7% to +7.9%), understanding worse in 5 of 8, generation exact worse in 12 of 32 (18 better, 2 tied)" / "on the **codec's own ceiling** there was **a consistent cost**: recover exact below the frozen codec's reading at 4 of 4 live seeds on area A and 3 of 4 plus a tie on B." |
| MAJOR "lowers exact in every harness" | item 8; row 15; §16 Q18 | "D3 exact match is mixed: tones lower at 2 of 4 (higher at s1 and s2), melody lower at 3 of 4;" / "Kind rose s0-s2 and tied s3; count rose s0-s2 and fell s3 (0.639 vs 0.648); band fell at s2 and s3" |
| MAJOR 1/4 vs 1/32 one-sided | item 6; row 3; §16 Q14 | "against 1/32 it leaned better on the codec-invariant readings" |
| MAJOR high-plasticity range pre-reproduction | item 6; row 4; §16 Q14 | "**−0.1% to +8.1% (7 of 8 worse, 4 seeds, coordinate rows); +3.2% to +8.1% (table rows, 3 seeds); reproduced-weaker**" |
| MAJOR 750 vs 4000 steps; D1 not codec-step-matched | item 6 table and reason; row 1; §16 Q28 | "**≥ 750 steps per candidate (`AUD_READY_MIN / AUD_READY_EVERY`), cosine, on the first media area only (item 2). An unmeasured deviation: 5.3× fewer steps and no generic set**" / "NOT matched codec steps: the frozen codec took no further step, the live one took +308 at 5e-5." |
| minor §6.4 1/4 drift line | §6.4 | "cumulative change on A reached 26.9% / 26.1%, against 24.8% / 28.5% at 1/32: no systematic increase." |
| minor held-out not 0.0 everywhere | 0b.2 Floors | "Held-out combinations are near the floor too: 0 to 0.5 on 6-12 prompts, mostly 0." |
| minor coordinate-row range | headline; item 11; §16 Q17 | "D1, one codec init: −9.9% to −16.7% current-area bits/s, smaller at the new seeds" |
| minor 18/18 | item 1 | as checker 1 |
| minor fixed-stride labels; unpaired alloc comparison | item 3; row 12; §13 decision rule | "(**unpaired across codec architectures**, V 3264 vs 1264)" |
| minor repro labels rows 2, 7, 10; stale range +15.7% | 0b.2 rows 2, 7, 10; item 10 | "direction reproduced via flipdist on spec25 (claim 7); the per-50-step values s0/s1 re-aggregated only" / "Teacher range **+2.6% to +15.7%**" / "recover s2/s3 *derived* from the reproduction's records" |
| minor online codes were table rows | item 11; row 10 | "online codes with table rows (D3 live25, s0): tones +17.8%, melody +21.4%;" |
| minor item 12 ranges | item 12 | "0.28-0.36 → 2.10-2.77 across all D1 runs" / "0.25 → 0.234 (s1), 0.125 → 0.25 (s0)" |
| minor D1 codec-only is the 50 Hz codec; churn range | row 16; items 6-7; §6.4 | "**D1's 50 Hz codec (`codec50.pt`), 200 area-A + 300 area-B codec steps, one seed**" / "26-61% (area A) and 31-58% (area B) of probe frames flip per 50 codec steps" |
| minor SE of the difference; false-out rate | §6.3; 0b.2 Floors | "the Gate reports the realised paired SE per cell (from the measured d) and the expected false-\"out\" rate over its cells, `aud.rate.false_out_est`;" |
| minor readiness triple on two bases; memory unlabelled | §12 | "about 3 × 130% ≈ **+390%** of LM time" / "**Memory** (arithmetic, not measured)" |
| minor re-warm length and EMA half-life at 1/32 | item 7; §6.2 step 8; §7 | "`AUD_REWARM_WINDOWS` 9600 = 300 codec steps at the default 1/32 cadence" |
| minor census double count | Contract accounting | "**+51 addition rows, 2 removal rows, 2 rename rows** (net +49 levers)" |
| minor reproduction coverage overstated | 0b Evidence | "seed 2 only for claims 4, 5, 8 (the act rerun) and 9 (the D1 'bpe' pair);" / "the same seed only for claim 10 (D2) and for the resume test (claim 8, seed 0)." |
| minor AUD_SHIFT_FLIPS attributed to the critic | item 16 | "That value is hand-set (the critic asked for a flip-rate threshold without giving one)" |
| minor 12.5 Hz figure is the nested codec | item 3; row 13; §6.3 | "This is D3's **nested codec forced to stride 4** in the codec-only drift sweep" |

### Checker 3 (the tree and the contract)

| Finding | Section | Answering sentence |
|---|---|---|
| MAJOR bit-exact resume is not an existing invariant | item 14; 0b.3; §13 S0b Tests | "**Bit-exact continuation becomes a tree invariant here. It is NEW, not inherited.**" / "tests/test_resume_clock.py C9 (a mid-epoch resume now continues" |
| MAJOR no surface restores the epoch position | item 14; §11; §13 S0b RUN | "`RUN.new_clock(..., resume_in_epoch=0, resume_windows_in_epoch=None)`, a signature move with Q-RUN-16" / "**A stamp exists from window 0.**" |
| MAJOR segment-at-rev on tok/api.py | item 14 | "The loop's `seg_table_moved` flag and the −1 / −2 sentinels of `rev_at_last_seg`" |
| MAJOR the prefix and loop-carried values | item 14; §11; §13 S0b | "**Loop-carried values.** `System.novelty`" / "7. **first: a text-only continuation with no act**" |
| MAJOR revise_horizon vs Q-OPT-5 | §13 S0b OPT; 0b.4; §16 Q16 | "**Q-OPT-10** reopens Q-OPT-5's (b) and answers both of its grounds" / "`OPT.revise_horizon(opt, st, *, run_windows)` (+1 entry point)" |
| MAJOR AUD_FREEZE_AT has no accessor or performer | §6.2 step 9; Contract accounting; 0b.6 | "`freeze_at` KEPT (the control arm's one-shot comparison reads `AUD_FREEZE_AT` through it, K9)" / "**The frozen-codec control arm** (`AUD_FREEZE_AT > 0`)." |
| MAJOR the act keys on a nonexistent counter | item 13; §11; §13 S0b LOOP | "Nothing keys on `RunClock.flushes`, which counts this process only and is another Clock kind." |
| MAJOR the hidden-freeze refusal | item 9; §13 S3 | "**It does not refuse.**" |
| MAJOR D1's optimiser; who steps the codec | item 6 table; §6.2; §7 | "`OPT_CODEC_BETA1` 0.8, `OPT_CODEC_BETA2` 0.99, `OPT_CODEC_WEIGHT_DECAY` 0.01, and `AUD_CODEC_GRAD_CLIP` 1.0 applied by `AUD.loss_terms`: D1's values." / "`AUD.loss_terms(aud, codec, wave, *, opt, anchor=None)` steps the codec group itself" |
| minor CKPT_SAVE_EVERY | item 14 | "So every `CKPT_EVERY` save would perturb training" |
| minor unsupported geometry rule kinds; aud.nfft | item 20; §11; §7 | "**Geometry manifest fields** (Config-derived only):" / "sets the 257 bins of every codec tensor; EXACT" |
| minor spliced bytes_per_token | item 15; §13 S0b TOK | "The spliced record's `bytes_per_token` is TOK's measurement over the spliced record" |
| minor act steps missing | §13 S0b LOOP | "3. Rebind the loop-local `ids` to the new Segmentation." / "11. If the view moved, set `_mint_at_last_seg`" / "19. a text act whose view did not move is refused and counted in `tok.retok_noop`;" |
| minor the stamp does not reach DOM; no media partitions | item 16 | "`DOM.observe` has no shift input, so the stamp does not protect DOM." / "there are no \"media-holding partitions\"" |
| minor MEM's per-byte transform undefined | item 16; §13 S0b Levels | "The root hands `surprise_b = 1 − p^(bpt_build / bytes(token))`" / "Media levels are not handed to MEM" |
| minor K13 populations missing | Contract accounting | "+4 at S0b: the act's X rows, one per package call" / "so `RUN.cadence_audit` states them" / "+ `aud.probe` against the draft" / "the 15 fields of §11's table, each with its `absent=` off value." |
| minor units not in units.py | §7 | "Three labels are declared in units.py (counted in Contract accounting): **U.HZ**" |
| minor levers with no AUD reader | §7 | "**Who reads which lever (K4).**" |
| minor the 22nd-wire reason; LM.d_aud_rows sources | item 11; Contract accounting | "A 22nd wire, rejected on budget" / "its source tuple grows to (`AUD.enabled`, `AUD.arch`, `AUD.levels`, `AUD.strides`, `AUD.rate_mode`, `AUD.bpe_slots`)" |
| minor TOK_RETOK_EVERY help already rewritten | item 13; §7 | "the act gives 0 the meaning its former help claimed until 2026-09-24" |
| minor stage order (R7 fixture; relay at S4) | §13 S0b, S3, S4; 0b.6 | "**The 'measured' known-answer test (selection only; the re-lay is S4's).**" / "**The readiness relay** (the re-lay half of 'measured''s known-answer test)" |
| minor counter naming; empty-window promise | §13 S0b RUN | "it sets a flag that `advance()` checks **before** its step increment" / "Counters: `epoch_revisions`" |
| minor the re-measure refusal is new | §11 | "**A new refusal: the re-measure.**" |
| minor splice through tokenize breaks counters and cache | item 15 | "It calls `_segment` directly with the view's match table, not `tokenize`." |
| minor held-out and generation revision | item 14; §13 S0b LOOP | "*Held-out and generation.* Between acts they segment at `run.seg.view`" |
| minor aud.collapse reused | §10 | "A separate counter, `aud.target_collapse`" |
| minor two citations | 0b Words; row 22 | "`d1/ck/codec25.pt.json` records its 4000 steps" / "`d1/run_arm.py:62-63`" |

---

## Round 3 — checker findings → where answered

Numbers were re-verified against the preserved records before any change (D1 `d1/res`, `d1/res_codec`, `judge/d1c`, `repro/d1`, `critic/d1r`; D3 `d3/res`, `judge/d3c`, `repro/d3`; D2 `d2/res`), and tree facts against `src/` (`tok/api.py`, `opt/api.py`, `opt/levers.py`, `train/api.py`, `spine/loop.py`, `spine/compose.py`, `spine/rng.py`, `spine/units.py`, `spine/derive.py`, `domains/api.py`, `capacity/api.py`, `fabric/api.py`, `sig/levers.py`). `rev/audit_d1.{py,txt}` recounts the D1 codec-invariant readings; `rev/probe_time.{py,txt}` is the preserved probe timing.

### Checker A (design and mechanics)

| Finding | Section | Answering sentence |
|---|---|---|
| MAJOR the default cadence was justified on bits/s and CPU | 0b.1 item 6; §16 row 14; §12 | "**The cadence.** `AUD_TRAIN_EVERY` 32 because 1/32 is the only cadence with a paired live-vs-frozen measurement at 4 LM seeds (D-4: the default is the regime measured against frozen)." / "**So neither cadence is established as better.** 1/32 ships because it is the measured one, not because of bits/s or CPU cost." / "The CPU cadence figures (1/32 against 1/4) are cost information, not grounds for the default (0b.1 item 6)." |
| MAJOR the S3 replica cannot measure the live-vs-frozen label | 0b.1 item 6; §13 S3 | "*replica-frozen*: the same recipe and the same chosen stride, with `AUD_FREEZE_AT` at the window the Gate fired;" / "**The transfer test.** The label transfers only if replica-live is non-inferior to replica-frozen on every LM-side codec-invariant primary" / "**The recipe check.** The readiness-only cell, which differs from D1 live25 in readiness alone, is compared with it on those primaries at the same seeds." / "Bits/s is reported and never used in either test: the arms do not share a codec (item 19)." |
| MAJOR stride 4 on 1 s clips breaks exact F | 0b.1 item 3; §6.1; §6.2 step 7; §6.3; §7 DATA_MEDIA_CLIP_S; §13 S3, S4 | "**Positions per clip are exact at every candidate stride.**" / "A clip of f frames at stride s takes F = ceil(f / s) positions under 'spec'." / "The pad is silence (zero waveform) appended at the clip's end, and the decoder's output is trimmed to the clip's samples." / "a 1 s aud/tones clip at stride 4: F = 13 positions, 2 pad frames, decoded length exactly 8000 samples." / "Known answer: a 1 s aud/tones clip re-laid from stride 2 (25 positions) to stride 4 takes 13 positions" |
| MAJOR bit-exact resume fails under 'jit_ema' ([p, cursor) not recorded) | 0b.1 item 14; §11; §13 S3, S4 | "**The replay record covers the whole consumed prefix, [0, cursor), as held in memory at the save.**" / "**Codes cut at a window cut, under either mode (the lazy re-encode under 'snapshot', the teacher's cut under `'jit_ema'`), are written in place into the Segmentation**" / "writes the replay record's [p, cursor) over the result." / "under 'jit_ema', k windows after an act with k > `AUD_TRAIN_EVERY` (the teacher moved between the cuts of [p, cursor))" |
| minor no AUD entry point does the per-act work | §6.2 step 5; §13 S3; Contract accounting | "**`AUD.refresh(aud, codec, *, recover_fn, probe_waves, clock) -> RefreshReport`** (+1, S3)" / "\| AUD entry points \| \| 10 (§5) / 11 (R6) \| **17** \|" |
| minor `tokenize(view=)` shares the one-slot cache | 0b.1 item 14; §13 S0b TOK, Tests | "**The one-slot cache is not shared across views.**" / "So a call with `view` not None neither reads nor writes the cache." / "`tokenize(view=V)` then `tokenize(view=None)` on the same buffer returns the current-table segmentation and counts no `tok.retok_noop`" |
| minor hold lengths contradict (2000 / 4000 / 6000) | headline; 0b.1 items 5, 8; §7; §16 row 31 | "refreshed at every act (at least every 2000 windows, or 4000 while the ceiling guard withholds a refresh)" / "so no snapshot is held longer than 2000 windows, or 4000 under a ceiling-guard hold (item 8)." / "the longest possible hold is `AUD_REFRESH_EVERY + AUD_CEIL_HOLD_WINDOWS` = **4000 windows**" / "A forced refresh that waited for the next periodic refresh Due is rejected: with holds starting at TOK acts it could reach 6000 windows" |
| minor §11 lets the rate mode change on resume unqualified | §11; R-RATE | "**The rate mode and rho** may change on resume only when the stride and the layout of the unconsumed tail are unchanged, or, under 'nested', when the resume's first act re-lays that tail." / "This covers a change of `AUD_RATE_MODE` or `AUD_ALLOC_RHO` as well as of `AUD_RATE_STRIDE`" |
| minor "next act" vs "next TOK act" | 0b.1 item 14; 0b.4; 0b.5 | "This refines D-1's \"at the next act\": an act raised only by AUD's refresh does not re-segment text (item 13), so that `TOK_RETOK_EVERY` keeps its meaning once media is on." / "Reach the stream at the next act that carries TOK's retok Due (≤ `TOK_RETOK_EVERY` windows; an AUD-only act does not re-segment text, item 13)." |
| minor every AUD-only refresh stamps FAB, even before media | 0b.1 item 16; 0b.3; 0b.5; §13 S0b LOOP step 10, S3, S5 (iii) | "An act stamps `shift_at_windows` / `shift_at_steps` when it moves the text view, and when it refreshes the snapshot or re-lays media **once media has been consumed**." / "\| A shift stamp at every refreshing act once media is consumed, and with it a FAB growth pause of about 20-27% of windows" / "Arms, over `AUD_SHIFT_STAMP`: the default 'refresh' (every refreshing act once media is consumed) against 'flips' (thresholded at `AUD_SHIFT_FLIPS`) and 'always' (every act from readiness on, including before media)." |
| minor under 'jit_ema' the probe is read only at TOK acts | 0b.1 items 9, 16; §6.2 step 8; §7 | "There is no refresh event, so after readiness `AUD.refresh` runs on an A-stage row on Cadences key `aud.probe` (`AUD_PROBE_EVERY` 500), with no snapshot copy." / "probe cadence during readiness (`AUD.ready`), and after it under `'jit_ema'` (`AUD.refresh`)" |
| minor `AUD_REFRESH_EVERY`=0 undefined | 0b.1 items 5, 9; §7 | "`AUD_REFRESH_EVERY` 0 is refused at startup under 'snapshot' with AUD enabled (`AUD.startup_refusals`)." / "0 is refused at startup under 'snapshot' (item 5); under 'jit_ema' the period reads 0 (DISARMED, item 9)" |
| minor `AUD_READY_MIN` from window 0 breaks add-a-modality resume | 0b.1 item 2; §6.2; §7; §11; §13 S3 | "`AUD_READY_MIN` 3000 U.Windows, counted from the codec's birth, sets the Gate's first test" / "An add-a-modality resume at window 5000 refuses a media phase at 6000 and at 8001 and admits one at 8002 at `OPT_BATCH_WINDOWS` 1; its Gate is first tested at 8001." |
| minor supersede list incomplete (§3.2 HZ, R14, §5 wire, Appendix A) | 0b.6; §7; Contract accounting | "- R14: \"`derive.media_rows` takes the lever's string form" / "- §3.2: \"`spine/units.py` gains unit LABELS only (`HZ`, `FRAMES`), not clock kinds.\" It gains three labels:" / "- Wires: \"`LM.d_aud_rows <- AUD.levels`: `prod(levels) + 2` if enabled, else 0.\"" / "**Appendix A:**" / "\| Unit labels (`spine/units.py`) \| 15 labels \| HZ, FRAMES (§3.2; Appendix A adds CODES) \| **+3**: U.HZ, U.FRAMES, U.SAMPLES \|" |
| minor S0b seed count unstated | §13 S0b | "(1) **3 paired seeds** (the same seeds in every arm), CPU, at the owner's shape" / "M is recomputed if more seeds are added" |
| minor step-matched control not matched at 1/4 | §13 S5 (ii) | "a **step-matched** frozen control **per cell**:" / "Its readiness cadence and horizon are set per cell so that the cosine reaches its floor at the matched count." / "the matched step count is reported per cell;" |

### Checker B (numbers and labels)

| Finding | Section | Answering sentence |
|---|---|---|
| MAJOR "no consistent cost" contradicted by recover exact (7/8) | headline; 0b Words; items 1, 6; "measured together"; 0b.2 row 1; §6.4; §16 row 14 | "on the **codec's own ceiling** there was **a consistent cost**: recover exact below the frozen codec's reading at 4 of 4 live seeds on area A and 3 of 4 plus a tie on B." / "on the codec's own ceiling, a consistent cost: 4 of 4 live seeds below the frozen codec's A reading, and 3 of 4 plus a tie on B" / "**Codec ceiling:** recover exact below the single frozen reading per area at 4 of 4 live seeds (A) and 3 of 4 plus a tie (B) (row 2)." / "The codec-invariant readings come in two kinds, reported separately below" |
| MAJOR the probe timing that sets 500 is unpreserved | §12; 0b.1 item 2; §16 row 30; headline | "from a preserved timing: `rev/probe_time.py`, output `rev/probe_time.txt`, 3 repetitions × 52 clips." / "so the figure is machine-dependent: about 28-47 ms per clip." / "§12 gives the probe cost, from a preserved timing (`rev/probe_time.{py,txt}`), that sets 500 rather than 200." |
| minor the fixed-stride claim rests on bits/s | headline; 0b.1 item 3; 0b.2 row 12; §6.6; §16 row 2 | "beat or tied every per-segment adaptive route **on LM bits/s**" / "On the codec-invariant readings the same D3 pairs tie within noise:" / "\| 12 \| No adaptive rate beat a fixed stride on LM bits/s (alphabet-dependent, item 19); on the codec-invariant readings the same pairs tie within noise \|" / "melody exact 0.141 / 0.141 / 0.25 vs 0.109 / 0.125 / 0.219 ('alloc' higher 3/3, by one or two clips of 64)" |
| minor 4000 vs 6000 | as the hold-length finding above | "and put the refresh cadence into back-to-back holds of up to 4000 windows each (`AUD_REFRESH_EVERY + AUD_CEIL_HOLD_WINDOWS`)." |
| minor row 17 phase label | 0b.2 row 17; 0b.1 item 10 | "Area A latents from the end of P2 decoded by the P3 decoder: +0.063 / +0.076 mel against their own P2 decode (0.508 / 0.5456 vs 0.4453 / 0.47); +0.072 / +0.080 against a fresh P3 re-encode (0.4362 / 0.4659)" |
| minor timbre counts unlabelled by plasticity | headline; 0b.1 item 8; 0b.2 row 15; §16 row 18 | "D3 at **high plasticity** (3e-4, a codec step every 2 LM steps, +600 steps over the frozen codec, so **not step-matched**)" / "D3 at **low plasticity** (cold: 5e-5, a step every 8), the regime nearer the default: tones timbre lower at 2 of 2, by less" / "**lower 2/2 by less**" |
| minor stale-code seed count overstated | 0b.1 item 10 | "(D3; table rows 3 seeds, coordinate rows 4 seeds; s2/s3 derived from the reproduction's records)" |
| minor "one codec init" missing on D1 cells | 0b.2 rows 5, 12, 21, 22 | "\| s0 (judge), s2 (repro); D1: one codec init (`codec25.pt`) \|" / "3 seeds (D3, D1; D1: one codec init, every seed loads `codec50.pt`, `d1/run_arm.py:266`); 2 (D2)" / "\| s0/s1 (D1: one codec init) \|" / "\| 4 seeds, D1: one codec init \|" |
| minor reproduction seed accounting | 0b Evidence; 0b.2 "How to read" | "seed 2 only for claims 4, 5, 8 (the act rerun) and 9 (the D1 'bpe' pair);" / "seeds 1 and 2 for claim 9's D3 arms (`ttcN25`, `ttcMRc`; `ttcMR` at s2), and seed 1 only for claim 9's D2 fixed arm;" / "s2 only for claims 4, 5, 8 (the act) and 9 (the D1 pair); s1 and s2 for claim 9's D3 arms; s1 for claim 9's D2 arm" |
| minor generation short counts | §6.3 Generation | "predicted END left 32-62 of 64-108 BPE clips short at s0/s1, and 36-74 at s2" |
| minor JIT encode RTF inconsistent | §12 | "1.4 ms per 1 s clip (spec25, D3's part timing: 0.0168 s per 12 clips); the first draft measured an encode real-time factor of 0.0008, i.e. 0.8 ms per 1 s clip" |
| minor +20% excludes the per-act probe; R12 cell unknown | headline; §12 | "The +20% covers the codec step, the re-encode and the acts only" / "at a 2000-window spacing (`TOK_RETOK_EVERY` 0, or before S0b ships a firing cadence) it is +53%" / "after readiness about **+2.2-2.9% per arrived area** at the default spacing (+1.6-2.2% at a 2000-window spacing)" |
| minor "anchored codec is WORSE"; contaminated drift50 | 0b.1 item 6; 0b.2 row 16 | "after area B the anchored codec is not better on area A: mel 0.4994 vs 0.4955 (within noise), recover 0.264 vs 0.347 (about 1.5 unpaired SE at n = 144, one seed)." / "**first config (`lr3e-4_noanchor`) only**: every later config in `drift50.json` and `drift50_b.json` is contaminated" |
| minor false-out estimate assumes 2 areas | §6.3 | "By default the rule reads 1 area, the first media area (tones: 4 attributes plus exact match, 5 cells)" / "so 5 cells together fall out about 26% of the time" |
| minor 24/24 vs the README's 18/18 | 0b.2 row 1 | "the README's \"18 of 18\" omits the judge's 6 s0/s1 lattice readings" |
| minor target std reads as a change over time | §10; 0b.2 row 21 | "frozen 9.47 / 9.02 vs live 8.90 / 8.51 after P2 (live at P1 9.49 / 8.88), a comparison of arms, not a change over time." |
| minor missing paths; per-act cost is a mean | 0b.2 rows 12, 14; §12 | "`d3/res/{ttcMR,ttc25c}_s1.json`; `repro/d3/res/{ttcN25,ttcMRc}_s{1,2}.json`, `repro/d3/res/{ttcMR,ttc25c}_s2.json`" / "`d3/res/{ttc25,frozen25}_s1.json`; `repro/d3/res/{ttcN25_s1,ttcN25_s2,ttc25_s2,frozen25_s2}.json`" / "refresh act mean 0.35-0.55 s per act (individual acts 0.30-0.73 s, `acts[].s`)" |

### Checker C (the tree and the contract)

| Finding | Section | Answering sentence |
|---|---|---|
| MAJOR OPT cannot read the codec horizon and re-warm | 0b.1 item 6; §6.2; §7; S0 rulings; Contract accounting | "Why AUD, not OPT: every input to the codec schedule is AUD's." / "The ruling is **Q-OPT-11** (next free), a ruling without a move: `maybe_step` writes lr to `base` and `encoder` only, and the stepper of any other group owns that group's schedule." / "Retiring a group is OPT's: **`OPT.retire_group(opt, st, *, key)`** (+1 entry point, S3)." / "\| AUD_CODEC_LR_MIN_FRAC \| new 0.05 \| U.FRACTION, domain (0, 1]" |
| MAJOR `RUN.cadence_audit` cannot state half-lives | 0b.1 item 9; §7; §13 S3; Contract accounting | "**Half-lives and holds are not periods, so they get their own audit.**" / "**`AUD.horizon_audit(aud, *, run_windows) -> [str]`** (+1, S3, on the ASSEMBLY 'audit' row beside `RUN.cadence_audit`)" / "Its LEVERS READ are `AUD_HALF_LIFE_WARN`, `AUD_EMA_HALF_LIFE`, `AUD_REWARM_WINDOWS`, `AUD_REFRESH_EVERY` and `AUD_CEIL_HOLD_WINDOWS`, which is what K4 needs." |
| MAJOR `OPT_HORIZON_REVISE` refused at every default run | §7; §13 S0b OPT, Tests; §16 row 16 | "`revise_horizon` is inert, not refused: `opt.horizon.revisions` is ABSENT with that reason" / "At the shipped `OPT_LR_RESTARTS` True with `OPT_LR_WAVELENGTH` 0 (one wavelength spans the whole run), one cycle is fitted and revision is live." / "it is inert, ABSENT with its reason, when `opt.build.cycles_fitted > 1` (and live at the shipped one cycle);" |
| MAJOR the dropout rng does not cross the save | 0b.1 items 14, 15; §11; §13 S0b; Contract accounting | "*The BPE-dropout stream crosses the save* (it does not today)." / "`vocab_state` carries the dropout stream's state (a state-shape change with a restore row), and `restore_vocab` puts it back." / "Q-TOK-15 states that neither `tokenize(view=)` nor `splice` reads `seed`" / "The act draws no seed: BPE-dropout continues the one `tok.dropout.mint` stream, whose state now crosses the save in `vocab_state`" |
| MAJOR `LM.d_aud_rows` omits `AUD.enabled` | 0b.1 item 11; 0b.6; Contract accounting | "The draft's coupling `LM.d_aud_rows` (proposal §5; no such coupling is in the tree yet) stays one wire" / "(False, 'spec', '8,5,5,5', '1,2,4', 'measured', 512) → 0" |
| MAJOR S0b's ship rule has no held-out instrument | §13 S0b; 0b.1 item 14; 0b.5 | "**The instrument** is the training stream's **prequential bits per byte**" / "When `EVAL.holdout_probe` lands (P5), the rule is re-run on held-out bits/byte at the view of the last text segmentation." / "The tree has no held-out encode call site yet (`EVAL.holdout_probe` is deferred to P5, and `EVAL.generate` to P6), so the rule applies when those land." |
| MAJOR no AUD entry point for refresh, probe or freeze | §6.2 steps 5, 8, 9; §13 S3; Contract accounting | "The per-act work is one entry point, **`AUD.refresh(aud, codec, *, recover_fn, probe_waves, clock) -> RefreshReport`** (+1, S3), on the act's X-stage row." / "`AUD.ready`, replacing `freeze`, with the readiness probe and the rate selection inside it" / "The frozen control needs no `AUD.freeze`: the root's comparison, `OPT.retire_group` and the next act's `AUD.refresh` do its work (§6.2 step 9)" |
| MAJOR one X row cannot credit four packages' calls | 0b.1 item 13; §13 S0b LOOP, Size; Contract accounting | "**One X row per package call.**" / "So the act is four X rows at S0b: `TOK.splice`, `RUN.RunClock.revise_epoch_length`, `OPT.revise_horizon` and `DOM.on_retokenize`." / "\| LOOP_ORDER rows \| 63 \| the draft's AUD rows \| **67** at S0b" |
| minor new derive conversions undeclared | 0b.1 item 9; §10; Contract accounting | "`derive.codec_steps_from_windows(span: Windows, every: Windows) -> Steps`" / "`derive.ema_decay_from_half_life(half_life: Windows, every: Windows) -> float`" / "`derive.latent_frames_from_seconds(s: float, fps: float) -> int`" / "\| Named derive conversions (`spine/derive.py`, O11) \|" |
| minor `AUD_ANCHOR_W` mislabelled U.FRACTION | §7; Contract accounting | "so `AUD_ANCHOR_W` 10 is U.COUNT, domain (0, 100)." / "\| U.FRACTION population \| \| \| **+18** \|" |
| minor `DOM.on_retokenize` wrongly gated on `SIG_MODE` | 0b.1 item 16; 0b.5; §16 row 26 | "`DOM.rekey` runs only at `SIG_MODE=learned` (Q-DOM-3). `DOM.on_retokenize` runs whenever the text view moved, at any `SIG_MODE`" |
| minor `dom.spawns` / `fab.cull` do not exist | 0b.1 item 16; §13 S5 (iii); §12 | "The others are the tree's existing names; `fab.grow` is the arm's configuration echo (`fabric/api.py:1210-1216`), not growth, and there is no `dom.spawns` or `fab.cull`." / "Readings: `part.n_created` and `part.n_culled` (DOM spawns and culls)" |
| minor `begin_epoch` wipes the restored position | 0b.1 item 14; §11; §13 S0b RUN, Tests | "So **on a mid-epoch resume carrying `run.seg` the epoch0 row does not call `begin_epoch`**" / "after assembly on a mid-epoch resume, `clock.in_epoch` and `windows_in_epoch` equal the saved values (the epoch0 row does not call `begin_epoch`), and the first window cut has the saved in_epoch as its index;" |
| minor C8 not in the rewrite list | §13 S0b Tests; 0b.1 item 14 | "tests/test_resume_clock.py C8 (`:262`, \"mints the run entered with are counted as in the stream, not stranded\") is rewritten" |
| minor `tokenize(view=)` cache; `_segment` docstring | 0b.1 items 14, 15; §13 S0b TOK | "`_segment`'s docstring says those two counters are \"declared by tokenize() and by nothing else\". S0b updates it to name `splice` and `tokenize(view=)` as well." |
| minor `CAP.observe` is a stub; CAP's blackout is a third consumer | 0b.1 item 16; §13 S0b Levels | "A third arrives at P4: `CAP.observe(..., blackout)` (`capacity/api.py:1300`)" / "The CAP half is inert until `CAP.observe` is rowed (P4)" |
| minor `aud.freeze` on `Cadences.due`; stride slack | 0b.1 items 5, 9; §6.2 step 9; Contract accounting | "The freeze is a one-shot Windows comparison in the root, `AUD.freeze_at(aud) > 0 and clock.step >= AUD.freeze_at(aud)`, that fires only while the codec group is not in OptState's retired set" / "Both bounds are exact at `OPT_BATCH_WINDOWS` 1." |
| minor manifest fields lack `absent=`; MAY_WIDEN change unlisted | §11; 0b.6 | "\| Field \| Rule \| Absent means (R-CKPT `absent=`) \| Why \|" / "It becomes MAY_WIDEN, absent 0." |
| minor MEM remap needs deferred `Vocabulary.decode` / `blen` | §13 S0b MEM, Size; Contract accounting | "Both are deferred entry points today (P4), so S0b takes them out of `DEFERRED_ENTRY_POINTS` (24 → 22)." |
| minor DOM argument contracts change without a ruling | 0b.1 item 10; S0 rulings; §13 S4 | "That needs a ruling: **Q-DOM-4** (next free after Q-DOM-3), which covers the reservoir's reference track," / "The reservoir track and the callable's contract are ruled by Q-DOM-4 (no signature moves)." |
| minor replay record lacks `byte_pos`, labels, `bytes_per_token` | 0b.1 item 14; §11; §12 | "**The record's fields** (about 10 bytes per position): ids (4), `byte_pos` (4;" / "Two fields are re-derived, not stored: `labels` as `stream.labels[byte_pos]`" |
| minor `TOK.splice` vs the rejection of `tokenize_at` | 0b.1 items 14, 15 | "It is the tree's second segmentation surface, and legitimately so: it re-segments only the tail of an existing record, and it owns that spliced record's `bytes_per_token`." / "Q-TOK-15 rewrites `tokenize`'s docstring sentence to match" |

## Round 4 — checker findings → where answered

One checker pass, 38 findings (7 major, 31 minor, none blocking). Four minors duplicate another finding: the per-act probe cost, the headline's D2 label, the hold-expiry Due and `run.seg`'s stream state. Each is answered on the row of the finding it duplicates. Every finding was checked against the source before the change:
- the tree: `spine/loop.py` (the save sites at `:1104-1118` run before the roll at `:1146ff`; `win_in_epoch = 0` at `:685`; `_mint_at_last_roll` reset only at `:1270`), `train/api.py:700-715` and `:798-810`, `tok/api.py:145-151`, `:1470-1485` and `:1560-1606`, `opt/api.py:1066-1082` and `:2590-2625`, `fabric/api.py:1210-1216`, `:4553-4554`, `:4619` and `:4916`, `compose.py:596`, `:1863` (24 `ROW_ARGUMENTS_ELSEWHERE` keys) and `:3512` (`_periods` returns one literal), and `tests/test_resume_clock.py` C1, C5, C6 and C9;
- the prototypes: `d2/d2run.py:7`, `:751` and `d3/run.py:227`, `:434` (both 12 media rows, 4 of them rehearsal, + 4 text rows); `critic/d1r/res/live25_every4w_s{0,1}.json` against `d1/res/live25_s{0,1}.json` (caption A after A 0.3359 / 0.3154 vs 0.3475 / 0.3061); `rev/audit_d1.txt` (s2 at 9871 windows); `repro/d1/res/live25_s{2,3}.json` (flips down to 0.0597); `d3/res/ttcMR_s{0,1}.json`, `repro/d3/res/ttcMR_s2.json` and `d3/res/drift_summary.txt` (melody positions/s); `d2/res/d2_{tgtgrad,nolm}_s0.json` (PR 2.445 / 2.781, understanding 0.0156 / 0.0781); `d3/res/{ttcN25,ttc25}_s0.json` (V 3264 / 1264).

| Finding | Section | Answering sentence |
|---|---|---|
| MAJOR `run.seg` rewritten at acts that segment no text (AUD-only, a refused no-op, a relay with no recorded stream state); step 11 unconditional (and the minor duplicate) | §11 R-RESUME-AT-ACT; 0b.1 items 13, 14; §13 S0b LOOP steps 2, 11, 12; §11 and S3 known answers | "the **text part**, rewritten only at a text segmentation (compose's epoch-0 row, every roll, and every act that splices: a TOK act, a relay, or both)" / "the **media part**, rewritten at every act" / "An AUD-only act and a refused no-op splice nothing and draw nothing, so they leave the text part alone" / "Text, the no-op test first, before anything draws" / "Otherwise every splice first records the BPE-dropout stream's state in `run.seg`'s text part" / "11. If the view moved, set `_mint_at_last_seg`" / "The checkpoint records the view of the last TEXT SEGMENTATION" / "save after an AUD-only act at `TOK_DROPOUT > 0` (the text part predates the act);" |
| MAJOR no surface raises the hold-expiry Due; the Due lists omit it and the freeze's Due (and the minor duplicate) | 0b.1 items 8, 13; §6.2 step 5; §7; §11; §13 S0b LOOP, S3; Contract accounting | "The withholding act's RefreshReport carries `hold_expires_at` (U.Windows, kept in AUD's hold state), and the root raises the Due by a one-shot Windows comparison, `clock.step >= hold_expires_at`, as for the freeze" / "the ceiling guard's hold-expiry Due and the frozen control's Due, each a one-shot Windows comparison in the root" / "and the one-shot hold-expiry and freeze Dues (0b.1 item 8, §6.2 step 9)" / "The hold-expiry Due is a one-shot comparison against `hold_expires_at` (in `payload['LOOP']`); the freeze Due is `AUD.freeze_at(aud) > 0 and clock.step >= AUD.freeze_at(aud)` while the codec group is not in OptState's retired set." / "The hold's expiry needs no accessor either: RefreshReport carries `hold_expires_at`" |
| MAJOR no lever selects the S5 (iii) stamp arms | 0b.1 item 16; 0b.3; 0b.5; §7; §13 S5 (iii); §16 row 26; Contract accounting | "\| AUD_SHIFT_STAMP \| new 'refresh' \|" / "`aud.shift.by_flips` ABSENT unless `AUD_SHIFT_STAMP='flips'` or `AUD_CODES='jit_ema'`" / "Arms (S5 iii), selected by `AUD_SHIFT_STAMP`" / "(`AUD_SHIFT_STAMP` 'flips' / 'always', S5 iii)" / "−2 (AUD_STRIDE, AUD_VERSION) + 39 new (the §7 table, `AUD_NFFT`, `AUD_SHIFT_STAMP` and `AUD_CODEC_GRAD_CLIP` included)" / "\| **+51 addition rows, 2 removal rows, 2 rename rows** (net +49 levers) \| 40 AUD + 11 other additions;" |
| MAJOR `DATA_MEDIA_REHEARSE` 0.25 misreports the measured share (1/3 of media rows in D2 and D3) | 0b.1 item 12; "measured together"; 0b.5; §7; §16 row 17 | "D2's base arm drew 4 of its 12 media rows from the earlier area (1/3; 25% of all 16 rows, text included" / "D3 used the same 12 media + 4 text rows with one-third of media rows from the earlier area" / "So both harnesses measured 1/3 in the lever's unit, and 1/3 ships." / "`DATA_MEDIA_REHEARSE` (D2, D3: 1/3 of media rows);" / "1/3 is the share D2 and D3 measured (0b.1 item 12)" |
| MAJOR the boundary checkpoint (a save in the window that rolled) is mishandled | 0b.1 item 14; §11; §13 S0b RUN, Tests | "**A boundary checkpoint resumes as the roll would.**" / "So `run.seg`'s text part carries its epoch." / "compose segments the drawn stream from byte 0 at the roll's view (`run.seg.view` at `TOK_RETOK_EVERY=0`, else the restored table) from `vocab_state`'s stream state, then calls `begin_epoch` and writes a fresh `run.seg`." / "and C5, C6 and C9's boundary half, re-run on the boundary path" / "23. a boundary checkpoint at `RUN_EPOCHS=2`, `DATA_RESAMPLE=1`" |
| MAJOR bit-exactness claimed while saves can fall inside a partial batch or accumulation | §11 R-RESUME-AT-ACT; 0b.1 item 14; 0b.5; §13 S0b LOOP, Tests | "for a save at an optimizer-step boundary whose stream-defining Configs are unchanged (below)" / "Periodic and SIGUSR1 saves are therefore deferred to the next optimizer-step boundary (batch empty, no accumulated gradient pending), and in an act's window the save follows the act." / "24. 8, 9 and 13 at `OPT_BATCH_WINDOWS` 2 and at `OPT_ACCUM` 2, with the save requested between flushes" |
| MAJOR the re-measure refuses the add-a-modality resume, which has no uninterrupted counterpart | §11; §13 S3 | "It applies only when the Configs that define the epoch's stream and its layout (DATA's, `AUD_ENABLED`, and the rate levers of R-RATE) match the checkpoint's." / "Its first act, at the cursor, keeps the replay record's [0, cursor), lays the child's newly drawn stream out after p from the recorded b0" / "An add-a-modality resume (AUD on over a text checkpoint) is not bit-identical." / "An add-a-modality resume has its own known answer instead (§11)." |
| minor the per-act probe cost is quoted at a 2000-window spacing (two findings) | headline; §12 Probing row and bullet; §16 row 30 | "at the default act spacing (the union of the 2000- and 3000-window cadences), about +71% of D1's LM time per arrived area, or about +2.2-2.9% on R12's basis" / "that is **about +71% of LM time per arrived area**; at a 2000-window spacing (`TOK_RETOK_EVERY` 0, or before S0b ships a firing cadence) it is +53%" / "after readiness about **+2.2-2.9% per arrived area** at the default spacing (+1.6-2.2% at a 2000-window spacing)" / "after readiness about +71% of D1's LM time per arrived area at the default act spacing" |
| minor 0b.4 says "the shift stamp at every act" | 0b.4 | "FAB: the shift stamp at every act that moves the text view, and at refreshing acts once media is consumed (item 16)." |
| minor an act carrying both TOK's Due and the relay Due | 0b.1 item 13; §6.3; §13 S0b LOOP step 2, S4 | "an act carrying both TOK's Due and the relay Due re-segments at the current vocabulary and re-lays media in one splice" / "with TOK's Due and the relay Due, the same splice with `media=` at s\*, counted `tok.retok` and `aud.rate.relay`, with the relay's assertion and data_plan retake (§6.3)" / "or at the current view when the act also carries TOK's Due (item 13)" |
| minor `DOM.rekey`'s media condition stated inconsistently | 0b.5; §6.2 step 5; §13 S4; §16 row 26 | "`DOM.rekey` at refresh acts once media is consumed, at `SIG_MODE=learned`" / "runs `DOM.rekey` with the composed callable at `SIG_MODE=learned` if media has been consumed (from S4)" / "At refresh acts once media is consumed, at `SIG_MODE=learned`, `DOM.rekey` receives" |
| minor the headline and §6.6 put D2's router on bits/s (two findings) | headline; §6.6 | "on LM bits/s (D3, D1: 3 seeds) and, for D2's router, on mel (2 seeds)" / "on LM bits/s (alphabet-dependent across rate arms, item 19) or, for D2's router, on mel" |
| minor the K4 LEVERS READ lists are incomplete | §7 | "`AUD_READY_MIN` and `AUD_READY_EVERY` (the cosine horizon), `AUD_REWARM`, `AUD_REWARM_WINDOWS` and `AUD_TRAIN_EVERY` (the re-warm's step conversion), and `AUD_ANCHOR_W`, `AUD_ANCHOR_MARGIN` and `AUD_ANCHOR_SCOPE` (the hinge)" / "`AUD_REFRESH_EVERY`, `AUD_CODES`, `AUD_HOP` and `AUD_READY_MIN` are also in `AUD.startup_refusals`'" |
| minor `TARGET_COLLAPSE_FRAC` is fixed and unlisted | 0b.3; §10 | "`TARGET_COLLAPSE_FRAC` 0.5, a module constant, §10" / "hand-set, reported, and listed in 0b.3 as not necessary" |
| minor the kept candidate's group key | §6.2 step 1; §11 | "The kept candidate's group keeps its key `'codec.<s*>'` after the Gate (no re-key; R-OPT restores it live beside the retired losers)" / "The kept group's moments never retire; only readiness losers retire, and the kept group only in the frozen control." |
| minor §16 rows 11′ and 12′ are not in the header | §16 | "Row 2 is replaced; row 11 is replaced by row 21; rows 13-33 are new." / "\| 32 \| `world_proj` is born zero with no gradient \|" |
| minor three wording slips (hold length, "every act refreshes", "50/s Hz") | 0b.3; §7; §6.1 | "held 1000-2000 windows, ≤ 4000 under a guard hold" / "every act refreshes unless the guard withholds it" / "The result is a 64-d latent at 50 / s per second" |
| minor the 1/4-vs-1/32 caption tally counts B only | 0b.1 item 6; §16 row 14 | "caption bits/byte better at 3 of 4 (B 0.1267 / 0.1246 vs 0.1377 / 0.1376; A after A 0.3359 / 0.3154 vs 0.3475 / 0.3061, where s1 goes the other way)" / "(caption 3 of 4, understanding 2 of 2, recover exact 3 of 4)" |
| minor 9866-9870 omits s2 | 0b.1 item 6 | "(308 steps over 9866-9871 windows)" |
| minor the per-refresh flip range is s0/s1 only | §6.4 | "(D1 live25, s0/s1; 6.0-15.3% with the reproduction's s2/s3)" |
| minor 'alloc' positions per second are tones only | §6.3; §13 Decision rule | "on tones with 22.0 / 22.8 positions/s against 26; on melody it used 26.5 / 26.5, more than forced 25 Hz" / "(on tones 22-23 against 26 positions per second; on melody 24.9-25.6 against 26)" |
| minor bits/s used across codecs (row 14 unlabelled; the EMA "did NOT lower LM bits") | 0b.2 rows 7, 14; 0b.1 item 5 | "(unpaired across codec architectures, V 3264 vs 1264; alphabet-dependent, item 19)" / "no LM bits/s difference (a codec-dependent unit, one seed)" / "no bits/s difference from online codes (a codec-dependent unit, item 19; one seed: tones 111.53 vs 112.35)" |
| minor the D2 PR evidence is the tgtgrad arm and not specific to the coupling | 0b.1 item 18; §6.5 | "D2's undetached-target arm (tgtgrad, 1 seed): understanding 0.016 vs 0.078; PR 2.45 vs 3.71 / 4.40 (d2) and 2.78 with no LM gradient at all (d2_nolm)" / "D2's tgtgrad arm, understanding 0.016 vs 0.078 (1 seed)" |
| minor the plateau threshold is under 1 paired SE | 0b.1 item 2; §7; §13 S3 | "or by more than 2 paired SE of that rise where that is larger" / "and on a noisy flat fixture (a stipulated-flat codec read on 400 simulated paired clips)" |
| minor FAB growth and the blackout share read from the wrong keys | 0b.1 item 16; 0b.3; §12; §13 S0b, S5 (iii); §16 row 26 | "S0b and S5 report the share from a new FAB counter, `fab.cooldown_windows` (windows inside the cooldown)" / "FAB's growth as `fab.grown_regression` and `fab.grown_stall` (and `fab.births`)" / "`fab.grow` is the arm's configuration echo (`fabric/api.py:1210-1216`), not growth" |
| minor restoring `in_epoch` does not move the loop's cut | 0b.1 item 14; §11; §13 S0b RUN, Tests | "`run()` seeds its cut index `win_in_epoch` from the restored `counters()['in_epoch']`" / "and the first window cut has the saved in_epoch as its index" |
| minor the OPT log is replayed onto the rebuilt horizon | §13 S0b OPT, Tests | "whose first entry is the build-time horizon; `load_state` rebuilds the schedule from that base plus the log" / "after a resume gives the uninterrupted run's lr at every later step" |
| minor `OPT_HORIZON_REVISE` refuses previously valid wavelength settings | §7; §13 S0b OPT, Tests; §16 row 16 | "revision is inert, not refused, and the horizon stays as built" / "`revise_horizon` is inert, not refused: `opt.horizon.revisions` is ABSENT with that reason" / "so no previously valid `OPT_LR_WAVELENGTH` setting is refused." |
| minor the MEM remap through `TOK.tokenize` touches the stream's counters and cache | §13 S0b MEM | "`TOK.tokenize(..., view=V, regularize=False)` at the act's new view V" / "as a view call, neither reads nor writes the one-slot cache" / "Q-TOK-15 also has a call with no `labels` (no stream) count in its own `tok.segment_remap`, not in the run stream's `tok.segment` and `tok.byte_fallback`" |
| minor AUD cannot render the probe references it is passed | §6.2 step 5; §6.3; §7; §13 S3 | "**`AUD.refresh(aud, codec, *, recover_fn, probe_waves, clock) -> RefreshReport`**" / "The root passes `DATA.recover` and the probe clips' waves, rendered once by `DATA.render`" / "the truth is `recover_fn` on each rendered wave" |
| minor the `ROW_ARGUMENTS_ELSEWHERE` population moves without a row | Contract accounting | "\| ROW_ARGUMENTS_ELSEWHERE (K10) \| 24 \| — \| **27** at S0b, **31** at S3 \|" |
| minor a conditional `aud.refresh` key escapes K9 and K13 | 0b.1 item 9; §7; §13 S3; Contract accounting | "all four unconditionally in `_periods`' returned literal, which is all K9 and K13 read" / "under `'jit_ema'` `AUD.refresh_period` returns 0, so the audit prints one DISARMED line for it" |
| minor no lever gives several codec steps per window | §13 S5 (ii) | "about 750 + 4250 ≈ 5000 steps for a 1/4 cell (`AUD_READY_EVERY` 1, no lever gives more; `AUD_READY_MIN` 5000), which starts its media 2000 windows later" |
| minor the `TOK_PROBATION_USES` disposition is wrong | 0b.4; §13 S0b Tests, Measurements | "0: probation off, whatever the appearances (`tok/api.py:150-151`)" / "(probation armed, `TOK_PROBATION_USES` > 0; at the shipped 0 nothing retires)" |

---

## Round 5 — checker findings → where answered

One checker pass, 32 findings (4 major, 28 minor, none blocking). Two minors duplicate another finding: grounding in the transfer test (answered with the generation count) and the step-matched 1/32 control (answered with its annealing). Every finding was checked against the source before the change:
- the tree: `train/api.py:910-1036` (`Cadences.due` fires at most once per evaluation, advances its seed by whole periods and seeds lazily at the current step), `spine/loop.py` (stage A runs per window and holds `SIG.train_step`; the periodic A-stage `DOM.rekey` gets `sig_encode`), `spine/compose.py:2368-2371` (the 'segment' row's whole-stream `tokenize`), `opt/levers.py:385` and `opt/api.py:1032-1034`, `:1645` (`OPT_GRAD_CLIP` 0.0, base group only), `opt/levers.py:841` (`OPT_BATCH_WINDOWS` 1), `tests/test_contract.py` K6 and K9 (K9 reads Cadences periods only, so `AUD_READY_MIN` needs no accessor);
- the draft: `docs/proposals/03_AUDIO_VIDEO.md:861` and `:907-911` (`frames_per_second` refuses a non-integer rate);
- the prototypes: `d1/run_arm.py:412`, `:690-691` (clip 1.0; `--B 8`, `--codec_every 4`), `d1/codec.py:168-170` (clip 1.0, 100-step warm-up), `d1/res/live25_s0.json` (1233 LM steps, 308 codec steps), `rev/audit_d1.txt` (frozen recover exact 0.347 / 0.271 at every seed; generation 12 worse, 18 better, 2 tied), `result.json` repro claim 9 (bits/s, mel and positions/s only).

| Finding | Section | Answering sentence |
|---|---|---|
| MAJOR D1's codec clip (1.0) and codec-phase warm-up are missing from the "exact settings" | 0b.1 item 6 table, (a); 0b.5; §6.2 step 1; §7; §13 S3; §16 row 14; Contract accounting | "gradient norm clipped at 1.0 at every codec step (`d1/run_arm.py:412`, `d1/codec.py:168`)" / "`OPT_CODEC_BETA1` 0.8, `OPT_CODEC_BETA2` 0.99, `OPT_CODEC_WEIGHT_DECAY` 0.01, and `AUD_CODEC_GRAD_CLIP` 1.0 applied by `AUD.loss_terms`: D1's values." / "(a) budget: 750 codec steps per candidate by readiness, cosine with no warm-up, against 4000 with a 100-step warm-up and a linear decay;" / "\| AUD_CODEC_GRAD_CLIP \| new 1.0 \| U.FRACTION (the `OPT_GRAD_CLIP` precedent) \|" / "on the shipped optimiser path (not D1's `codec_step`)" |
| MAJOR the regime is carried over in windows, not LM steps (D1: 8 windows per LM step) | headline; 0b.1 item 6 table, reason, (f); §13 S3 | "The windows (data per codec step) are held fixed, not the LM steps: at `OPT_BATCH_WINDOWS` 1 that is 32 LM steps per codec step against D1's 4, **a deviation** (f)" / "(f) LM steps: the default holds windows (data) per codec step fixed, so at `OPT_BATCH_WINDOWS` 1 it takes 32 LM steps per codec step against D1's 4, and 1000-2000 LM steps per hold against 250." / "at the tree's `OPT_BATCH_WINDOWS` 1 and on the shipped optimiser path (not D1's `codec_step`)" / "All of it is 4 LM seeds, ONE codec initialisation, 25 Hz, one LM step per 8 windows" |
| MAJOR `frames_per_second` refuses 12.5 | 0b.6 Appendix A; Contract accounting | "It refuses only a grid that is not a whole number of frames per second (sr / hop); a per-stride rate may be fractional. Known answers: `frames_per_second(8000, 160, 4)` == 12.5; `frames_per_second(8000, 150, 1)` refuses, because 8000 / 150 is not a whole number." / "`frames_per_second` refuses only a non-integer grid (sr / hop), so 12.5 is legal" |
| MAJOR the codec step at the flush fires once per flush when `OPT_BATCH_WINDOWS` exceeds the period | 0b.1 item 2; §6.2 step 1; §13 S3; Contract accounting LOOP_ORDER | "on an A-stage row evaluated per window as `SIG.train_step`'s is, so `Cadences.due` fires once per period at any `OPT_BATCH_WINDOWS` (at a flush row it fires at most once per flush: about 187 readiness steps at `OPT_BATCH_WINDOWS` 16)" / "each candidate has 749 codec steps by window 3000 at `OPT_BATCH_WINDOWS` 1 and at 16;" / "`AUD.loss_terms` (A, evaluated per window, whole run; §6.2 step 1)" |
| minor the transfer test names grounding, which D1 does not record (and the duplicate: generation unreported) | headline; 0b Words; items 1, 6; 0b.2 row 1; §13 S3 | "generation exact worse in 12 of 32 (18 better, 2 tied); grounding was not recorded;" / "and grounding bits, which D1 does not record)" / "generation exact worse in 12 of 32, better in 18, tied in 2 (`rev/audit_d1.txt`); grounding unrecorded in D1;" / "every LM-side codec-invariant primary the D1 harness records (caption bits/byte, understanding exact, generation exact; grounding is first read at S5; margin 2 paired SE)" |
| minor the freeze Due has no `> 0` guard | 0b.1 item 9; §6.2 step 9; §11; §13 S3 | "`AUD.freeze_at(aud) > 0 and clock.step >= AUD.freeze_at(aud)`, that fires only while the codec group is not yet retired (§6.2 step 9)." / "At `AUD_FREEZE_AT` 0 the freeze never fires and `aud.freeze` is ABSENT." |
| minor a resume after the frozen control's freeze is refused by R-OPT and re-fires the one-shot | §6.2 step 9; §11 R-OPT, Payload, known answers; §13 S3 | "Candidate groups `'codec.<s>'` that retired at readiness, and in the frozen control the codec group retired at the freeze, are admitted on restore as retired." / "that fires only while the codec group is not in OptState's retired set, which is checkpointed, so a resume after the freeze does not fire it again." / "save after the frozen control's freeze (the group restores as retired, and the freeze does not fire again);" |
| minor §6.2 step 5's root work is not conditional on a refresh | §6.2 step 5 | "If the snapshot was refreshed, the root then runs `DOM.rekey` with the composed callable at `SIG_MODE=learned` if media has been consumed (from S4), reads `sig.media_drift`, and points WORLD's target at the new snapshot." |
| minor the relay Due is raised even when s* equals the provisional stride | §6.2 step 2 | "if s\* ≠ `AUD_RATE_STRIDE`, a relay Due is raised for the next act (S4)." |
| minor no `'codec'` group exists at the defaults | 0b.1 item 6 table; 0b.5; §11 Payload; §13 S3 | "The codec group (`'codec.<s*>'` at the default, `'codec'` otherwise, §6.2 step 1), on a schedule AUD owns" / "the codec group (`'codec.<s*>'` at the default, `'codec'` otherwise) on AUD's own schedule" / "`OptState` carries the codec group (`'codec.<s*>'` at the default, `'codec'` otherwise, §6.2 step 1;" / "stepping the codec group (`'codec.<s>'` per candidate, then the kept `'codec.<s*>'` at the default; `'codec'` otherwise; the Q-OPT-6 pattern)" |
| minor 0b.5's OFF list omits three §7 arms | 0b.5 | "`AUD_RECON_LOSS='multires'`; `AUD_ANCHOR_W` 0 (a measured arm) and `AUD_ANCHOR_SCOPE='old'`;" |
| minor the step-matched 1/32 control needs a pre-Gate freeze and ends unannealed (two findings) | §6.2 step 9; §13 S5 (ii) | "A freeze before the Gate retires every candidate's group, and the Gate's own snapshot copy stands in for the refresh (`AUD.ready` then counts `aud.freeze`)." / "Its readiness cadence and horizon are set per cell so that the cosine reaches its floor at the matched count." / "about 750 + 530 ≈ 1280 steps for a 1/32 cell (`AUD_READY_EVERY` 2, `AUD_READY_MIN` 2560)" |
| minor `AUD_SHIFT_STAMP` has no surface from AUD to the root, and its 'always' arm reaches pre-readiness acts | 0b.1 item 16; §6.2 step 5; §7; §13 S0b LOOP step 10, S5 (iii) | "`AUD.refresh` returns the stamp decision as RefreshReport's `stamp`: 'after_media' (stamp once media has been consumed) for a refreshed snapshot under 'refresh'" / "Before readiness no `AUD.refresh` runs and an act stamps only when the text view moved." / "or as the act's RefreshReport `stamp` says (from S3: 'now', or 'after_media' once media has been consumed; §7, 0b.1 item 16)." / "inert under 'jit_ema', where `aud.shift.stamp` is ABSENT" / "`'always'` stamps every act from readiness on, before media included." |
| minor 0b.3 says the segmentation is recorded as of the last act | 0b.3 | "recorded as of the last text segmentation (text) and the last act (media)" |
| minor the headline, item 6 and §16 row 14 call D1 live25 the one (only) live regime measured against a frozen codec | headline; 0b.1 item 6; §16 row 14 | "That is the only live regime measured against a frozen codec at 4 paired LM seeds." / "It is the only live regime measured against a frozen codec at 4 paired LM seeds." / "The only live regime measured against a frozen codec at 4 paired LM seeds:" |
| minor "7 of 8" reads as seven replications against two constants | headline; 0b.1 item 1; 0b.2 rows 1-2 | "The frozen codec and the probe set never move, so these are four perturbations of one codec init against one reading per area, and D3, which retrains its codec per seed, shows exact match mixed." / "Each frozen value is a single reading per area from one codec init (the frozen codec and the probe set never move), so these are four perturbations of one codec;" / "(lower 7 of 8, 1 tie, against one frozen reading per area; D3's per-seed codecs are mixed, row 15)" |
| minor item 2 overstates that the prototype codecs miss 0.30 | 0b.1 item 2; §6.6 | "On recover exact, D3's codecs and D1's melody reading fall below it, and D1's tones reading passes:" / "Rejected: it was set on a different probe." |
| minor the stated reason for rejecting layout option (a) is wrong | 0b.1 item 3; not-applied item 14 | "which the rule must be able to choose (the toy exact-match readings alone would have chosen it, row 13)." |
| minor row 12's Repro column labels derived readings as reproduced | 0b.2 row 12 | "bits/s and mel reproduced (claim 9); codec-invariant readings *derived*" |
| minor high-plasticity bits/s is used as an LM cost without its codec-dependent tag | 0b.1 item 6 alternatives; 0b.2 row 4; §16 row 14 | "LM bits/s (codec-dependent, item 19) vs frozen with the same rows" / "trades LM bits/s (codec-dependent, item 19) for mel; timbre recovery falls (row 15)." / "−0.1% to +8.1% bits/s (codec-dependent, item 19) vs frozen" |
| minor the recipe check is not matched, and its both-fail branch is undefined | 0b.1 item 6; 0b.3; §13 S3; §16 row 29 | "*readiness-only*: D1 live25 as measured (8 windows per LM step, stride 2, 0.5 s crops, a refresh every 2000 windows), with only its codec phase replaced by the shipped readiness recipe" / "If the `'+generic'` cell fails too, both go to the owner, and the default ships the recipe closer to D1 live25 on the primaries." |
| minor Q-CKPT-5 refuses what S0b replays (a checkpoint without `run.seg`) | §11 | "the presence of `run.seg` in a mid-epoch checkpoint that carries a replay record (a pre-S0b checkpoint, which has neither, keeps Q-RUN-10's replay and warning)" |
| minor the 'segment' row still tokenizes the whole stream on a resume | §13 S0b RUN; Contract accounting ASSEMBLY_ORDER | "the 'segment' row rebuilds the Segmentation from the replay record and `TOK.splice` instead of its whole-stream `tokenize` (so it counts nothing the uninterrupted run did not), before 'optimizer', so `OPT.build` sees the post-act length" / "but the 'segment' row's note changes (§11 Rules; Contract accounting) and so does the 'epoch0' row's:" |
| minor the reference track also reaches `SIG.encode`, and the periodic `DOM.rekey` re-encodes stale codes | 0b.1 item 10; S0 rulings; §13 S4; Contract accounting | "`SIG.encode`'s `windows` (the same object, `domains/api.py::observe`; SIG ignores the track)" / "Once media is in the reservoir, the periodic A-stage `DOM.rekey` gets the composed callable too, so no media unit is re-keyed from stale codes." / "the periodic A-stage `DOM.rekey` receives it too once media is in the reservoir." |
| minor the aud.* periods with AUD off, and AUD-only acts before readiness | 0b.1 items 5, 9, 13; §13 S3 | "With `AUD_ENABLED` False every aud.* period accessor returns Windows(0), DISARMED." / "a fire before readiness raises no act;" / "`AUD_REFRESH_EVERY` 0 is refused at startup under 'snapshot' with AUD enabled (`AUD.startup_refusals`)." |
| minor `AUD.ready_min` has no consumer (K6) | §13 S3; §7; Contract accounting (AUD 17, 169, 186) | "No `ready_min`: only AUD reads `AUD_READY_MIN`, and K6 refuses an entry point no row names." / "\| … after S3 / S4 / S5 / S6 \| \| 149 / 150 / 151 / 153 \| 165 / 166 / 167 / **169** \|" / "AUD_READY_MIN is read inside AUD only (the Gate, the horizon, the startup refusal)." |
| minor the lazy seed puts the readings at 501 … 3001 and the Gate's first test at 3001 | 0b.1 item 2; §7; §12; §13 S3 | "(Cadences seeds a key lazily at window 1, so readings land at 501, 1001, …: 5 by window 3000, the 6th at 3001)" / "sets the Gate's first test: the first probe reading at or after it (window 3001 on a fresh run). The startup refusal refuses a media LM phase that starts before the flush after that test" / "a fixture that plateaus at window 1000 fires at 3001, the first probe reading at or after it" |
| minor the 200-window hidden-freeze run is refused at `AUD_READY_MIN` 3000 | §13 S3 | "Neither refuses: a 200-window run with AUD enabled and no media phase starts and is warned." |
| minor DATA cannot refuse a clip length in frames (it may not read `AUD_HOP`) | 0b.1 item 3; §7; Contract accounting K10 | "`AUD.startup_refusals` refuses any other, from the per-family clip lengths and `DATA_AUD_SR` that the root passes beside `phase_plan` (AUD may not read DATA's levers, O10)." / "refused by `AUD.startup_refusals` from the clip lengths the root passes (O10);" / "and `AUD.startup_refusals`' names the per-family clip lengths and `sr` beside `phase_plan`." |
| minor `AUD_CODEC_LR_MIN_FRAC` 0 is a freeze by configuration | §7 | "\| AUD_CODEC_LR_MIN_FRAC \| new 0.05 \| U.FRACTION, domain (0, 1]: 0 is refused, because a zero floor stops the codec after the cosine, a freeze by configuration \|" |

---

## Checker findings not applied, or applied differently (with the reason)

1. **AUD lever count "50, not 51" (checker 3, round 2).** Not applied. The draft's AUD population is 17: the §4.1 table's 16 plus R12's `AUD_TRAIN_EVERY`, which the checker did not count. 15 are kept and 37 are new (36 from round 1 plus `AUD_NFFT`, which the same finding asked for). Round 3 then moved the codec schedule into AUD (`AUD_CODEC_LR_MIN_FRAC` new, `AUD_CODEC_LR` renamed from the draft's `OPT_CODEC_LR`), so AUD is now **54** (55 after round 4's `AUD_SHIFT_STAMP`).
2. **"Accept a candidate id only if live in that view; the current mlbf stays a safe upper bound" (checkers 1 and 3).** Applied differently. `retire()` pops an id from `seq2id`, so filtering today's match table would miss an id live at the act and retired since. The view builds its own match table from `id2bytes[:size]` minus the retired set (exact because `_reinstate` never gives one byte string two ids).
3. **"A prefix of exactly p positions, dummy except the recorded look-back and retained ids" (checker 1).** Applied more strongly. Checker 3 found that `SIG.train_step` draws pairs from the whole consumed prefix under `SIG_SPACE` 'tokens' and 'typed', so a dummy prefix is not bit-exact. The checkpoint carries a replay record of the whole consumed prefix (round 3 widened it from [0, p) to [0, cursor); about 26 MB at the end of an owner-scale run), which contains the look-back, the retained unit and every position consumed since the act.
4. **"Splice text at `run.seg.rev` at an AUD-only act" (checker 1, first option).** The second option was taken: an AUD-refresh-only act splices nothing (lengths do not change and codes are re-encoded lazily at cut). Only a relay act splices at `run.seg.view`.
5. **"Restrict the hidden-freeze refusal to half-life arm levers while a media phase is scheduled" (checker 3, second option).** Not applied. The refusal is dropped entirely: D-4 asked for a warning, the tree states cadences rather than raising them, and an arm half-life longer than a short run is a legitimate request.
6. **"Store the candidate stride set as a sorted set with a containment rule" (checker 3).** Not applied. It needs a GeometryField rule kind that `CKPT.check_geometry` does not have. `aud.strides` is EXACT until a stride 8 is built, and the "absent means '2' for a first-draft checkpoint" row is dropped because no AUD checkpoint exists in the tree.
7. **"Match D1's readiness recipe" (checker 1, first option).** Not the default. The S3 replica and the `'+generic'` fallback are adopted instead, because the MINORS decision keeps later areas unseen until arrival, and D1's recipe costs about 3000 codec steps per candidate (×3 under 'measured') during readiness.
8. **"Either refresh at every act or keep the 2000-window hold" (checker 1, D-5).** Refresh at every act was taken, as D-5 decided. The resulting 1000-2000-window holds are stated as an unmeasured deviation from D1.
9. **`RunClock.restore` as a new entry point (checker 3, alternative).** The `RUN.new_clock` keyword move was taken instead, so the §7 count stays at 140 after S0b and the signature-move count is 5.
10. **Beyond the findings.** Costing the probe (checker 1, round 2) showed that probing is expensive on CPU. So `AUD_PROBE_EVERY` moved from 200 to 500 during readiness, and after readiness the probe is read at every act, where the guard and the flip readings use it (round 3: on its own period under `'jit_ema'`). Round 3 replaced the unpreserved spot timing (about 19 s per reading) with a preserved one (`rev/probe_time.{py,txt}`: 11.2-14.0 s per reading); the direction holds. The earlier cadence is recorded as the alternative in §12.
11. **D-6's quoted stale-code range "+2.6% to +15.1%".** Updated to +2.6% to +15.7%. A round-2 finding pointed to the reproduction's s2/s3 records, and the number was verified there.
12. **Round 3, checker A: "stamp only when probe flips since the last stamp exceed `AUD_SHIFT_FLIPS`" as the default (FAB cooldown).** Applied in part. The half that says "stamp only once media has been consumed" is the default: before the first media window a refresh changes nothing the LM or the routing stack has seen. The flip-thresholded stamp is **an S5 (iii) arm, not the default**, because D-8 decided that every act that refreshes the snapshot stamps a self-inflicted shift. 'Always stamp' (including before media) is kept as the other arm, and 0b.3 lists the blackout as not necessary, with S5 (iii) deciding.
13. **Round 3, checker A: "report bits/s and do not use it, unless the replica is pinned to 'fixed' stride 2".** Applied without the exception. The pinned cell exists, but it serves the recipe check against D1 live25 on the primaries only. Even at the same stride, the replica's codec and D1's 4000-step codec are two codecs, so bits/s would still compare two alphabets (item 19).
14. **Round 3, checker A: the rate/frame-count rule (options a, b, c).** Option (c) was taken: F = ceil(frames / s) with a silence pad and a decoder trim, which is what D3 did (`d3/d3lib.py:189`). Option (a) would take 12.5 Hz away from the default family (aud/tones, 1 s = 50 frames), which the rule must be able to choose (the toy exact-match readings alone would have chosen it, row 13). Option (b) would change tones' clip length from the 1 s the draft and every prototype used. Both are recorded as alternatives in 0b.1 item 3.
15. **Round 3, checker A: `AUD_REFRESH_EVERY` 0 (refuse, or define as "only at TOK acts").** Refusal under 'snapshot' was taken. The other reading would make the snapshot's refresh depend on `TOK_RETOK_EVERY`, and at `TOK_RETOK_EVERY` 0 it would be a freeze by configuration, which is what the owner ruled out.
16. **Round 3, checker A: `AUD.refresh`, and a separate probe entry point.** The probe was folded into `AUD.ready` (readiness) and `AUD.refresh` (after it) rather than given its own entry point. **Checker C's `AUD.freeze(aud, codec)` for the control arm was not added.** The freeze is the root's one-shot Windows comparison, `OPT.retire_group` retires the group, and the next act's `AUD.refresh` copies the final codec and counts `aud.freeze`, reading `AUD_FREEZE_AT` itself. So AUD is 18, not 19.
17. **Round 3, checker C: the codec schedule's route, (a) an `OPT.build(codec_horizon=)` argument, or (b) AUD owns the schedule.** Route (b) was taken, with two changes. The draft's `OPT_CODEC_LR` moves with the floor into AUD (`AUD_CODEC_LR`, a census rename row), because the stepper that writes the lr must read the peak. Retirement goes through a new `OPT.retire_group` entry point (+1), because dropping an optimiser's moments changes `OptState`, which is OPT's. The betas and weight decay stay OPT levers, read when `OPT.build` constructs the group. Route (a) is recorded: it needs two frozen-signature moves to carry values OPT does not otherwise need.
18. **Round 3, checker C: the hidden-freeze audit's route.** `AUD.horizon_audit` (+1 entry point, ASSEMBLY 'audit' row) was taken. The `RUN.cadence_audit(horizons=, warn_frac=)` signature move under a Q-RUN-17 ruling is recorded as the alternative. It would hand RUN an AUD lever's value and add a second meaning to a function whose one job is periods.
19. **Round 3, checker C: the BPE-dropout stream, (a) carry its state, or (b) per-event derived children.** Option (a) was taken, following the DOM/SIG/FAB/WORLD `(rng._r.getstate(), rng._draws)` pattern. `TOK.splice` takes `stream_state=` instead of `seed=`. Option (b) would restart the stream at every segmentation, which P1-H56 forbids; it is recorded as the alternative.
20. **Round 3, checker C: S0b's instrument, (a) build a minimal held-out probe (un-defer `EVAL.holdout_probe`), or (b) the training stream's per-byte loss.** Option (b) was taken, as prequential bits per byte at `RUN_EPOCHS=1`, where every window is scored before it is trained on. Un-deferring `EVAL.holdout_probe` needs the `units_by_domain` / `logits_fn` join that P5 owns, which would pull a P5 build into S0b. The rule is re-run on held-out bits/byte when P5 lands.
21. **Round 3, checker C: the act's X rows, (a) one row per package, or (b) `_OFF_TABLE`.** Option (a) was taken (63 → 67), following the roll's precedent of one E row per call. `_OFF_TABLE` is for calls pinned to another row's moment and named in its text, and the act's calls are the act.
22. **Round 3, checker C: `Vocabulary.decode` / `blen`, (a) row them, or (b) read `id2bytes` / `bytes_per_id` directly.** Option (a) was taken, in the tree's `_OFF_TABLE` form: they leave `DEFERRED_ENTRY_POINTS` (24 → 22) and are named in the `MEM.maintain` / `MEM.write` B-row texts, as `MEM.apply_domain_plan` is named in `DOM.manage`'s. Reading private attributes would bypass TOK's documented surfaces for exactly these two questions.
23. **Round 3, checker A: `tokenize(view=)` and the cache, (a) put the view in the stamp, or (b) bypass.** Bypass was taken: a view call neither reads nor writes the one-slot cache. Putting the view in the stamp would let the epoch-start resume or a `TOK_RETOK_EVERY=0` roll evict the slot that the live table's no-op refusal relies on.
24. **Round 3, checker A: "decide HZ explicitly".** HZ is kept (+3 labels: HZ, FRAMES, SAMPLES), because `DATA_AUD_SR`, the one sample-rate lever, is labelled Hz in the draft. Appendix A's CODES is not declared, because no lever carries it.
25. **Round 3, checker B: the per-act probe cost "about +80% per area on the D1 basis".** Applied with the preserved timing: about +53% (from 12.7 s per reading against 24 s of D1 LM time per 2000 windows). The checker's +80% came from the unpreserved 19 s figure. On the R12 basis it is about +1.6-2.2% per arrived area, against the checker's +3% from 19 s.
26. **Round 4: `DATA_MEDIA_REHEARSE`, (a) ship 1/3, or (b) keep 0.25 labelled unmeasured.** (a) was taken. Both harnesses measured 1/3 in the lever's unit, and this revision ships the measured value (D-4). With `DATA_TEXT_SHARE` 0.3, 1/3 gives the earlier area about 23% of all windows, against 25% of rows in D2 and D3.
27. **Round 4: `OPT_HORIZON_REVISE` when more than one cycle is fitted, (a) list the refusal in 0b.5, or (b) make revision inert.** (b) was taken. A refusal would make a previously valid `OPT_LR_WAVELENGTH` setting fail at startup unless the operator also turned a new lever off, and the tree states such cases rather than refusing them. This reverses round 3's refusal (checker C). Its only reason, that "the remaining cosine" is undefined, supports inertness just as well.
28. **Round 4: the hold-expiry surface, RefreshReport or an accessor.** RefreshReport's `hold_expires_at` was taken, with the root's copy in `payload['LOOP']`. AUD stays at 18 entry points.
29. **Round 4: the plateau threshold, (a) report a false-"not plateau" rate, (b) size it on the paired SE, or (c) compare a mean over the patience readings.** (b) was taken, together with the S3 noise fixture, because it removes the defect instead of reporting it. 0.02 stays as the lower bound.
30. **Round 4: `TARGET_COLLAPSE_FRAC`, a lever or a 0b.3 listing.** It was listed in 0b.3's guard-thresholds row and not made a lever. It is a report-only threshold on a gauge with no action attached, so a lever would add a census row and change no behaviour.
31. **Round 4: the MEM remap's segmentation, (a) a counter-free TOK path, or (b) the call named with a declared counter.** The two were combined:
    - The remap calls `TOK.tokenize(view=V, regularize=False)` at the act's new view. A view call already bypasses the cache under Q-TOK-15, and the current table would be wrong between acts anyway.
    - Q-TOK-15 has a call without labels count in its own `tok.segment_remap`.
    - A private `_segment` call from the root was not taken, because it would bypass TOK's documented surface. A new entry point was not taken either, because it would move every downstream count.
32. **Round 4: the probe inputs, rendered waves or a render callable.** Rendered waves were taken. The probe set is fixed, so it is rendered once, whereas a callable would render 400 clips per area at every act.
33. **Round 4: the step-matched control at 1/4, (a) a counted arm lever, or (b) a longer readiness.** (b) was taken, and the control's different cosine horizon and media timing are labelled. A lever for several codec steps per window would exist for one control cell only.
34. **Round 4: saves inside a partial batch, (a) defer the save to a step boundary, or (b) checkpoint the partial batch, its Dues, `batch_len` and the pending gradients.** (a) was taken for periodic and SIGUSR1 saves. A driver's `max_windows` stop is not deferred, because C3 fixes `max_windows` as a count of this process's windows. A stop between boundaries keeps today's counted drop (C1) and is outside the invariant.
35. **Round 4: where the add-a-modality resume's tail starts.** The finding did not say which bytes of the child's newly drawn stream follow the replay record's prefix. The doc lays the child's stream out from the recorded b0, the one offset the two streams share. S3's own known answer confirms that choice; it is not a bit-exact test.
36. **Round 4: the R12-basis range of the per-act probe cost.** The two findings gave 2.1-3.0% and 2.2-2.9%. 12.7 s × 4 per 6000 windows, at 290-390 ms per window, is 2.17-2.92%, so the doc says 2.2-2.9%.
37. **Round 5: D1's codec clip, (a) `OPT_CODEC_GRAD_CLIP` read by OPT, or an AUD lever.** An AUD lever, `AUD_CODEC_GRAD_CLIP` 1.0, was taken. The clip is applied at step time by the group's stepper, and Q-OPT-11 gives the stepper the step-time settings. An OPT lever would have to reach AUD through the param group, which is a channel no Config declares. AUD is now 56 levers, and the lever total is +49. **The 100-step warm-up was not added.** It belongs to D1's standalone codec phase, which deviation (a) already replaces, so it is listed there. It is not a live-phase setting.
38. **Round 5: the LM-step geometry, (a) run the replica at the tree's `OPT_BATCH_WINDOWS`, or (b) add a B = 1 cell.** (a) was taken. The transfer cells run at `OPT_BATCH_WINDOWS` 1. The only cell kept at D1's B = 8 is the readiness-only cell, which has to differ from D1 live25 in readiness alone.
39. **Round 5: the codec step at the flush, (a) a per-window A-stage row, (b) count fires per flush, or (c) a realised-cadence horizon.** (a) was taken, as `SIG.train_step` is already stepped. It is the only option under which `AUD_READY_EVERY` keeps its meaning at every `OPT_BATCH_WINDOWS`. (b) needs a count that `Cadences.due` does not return. (c) would still leave about 187 readiness steps at `OPT_BATCH_WINDOWS` 16.
40. **Round 5: the recipe check, (a) a cell that differs from D1 live25 in readiness alone, or (b) rename it a whole-stack check.** (a) was taken. It replaces the pinned stride-2 cell instead of adding one, so S3 still runs three cells. A failure can then be pinned on readiness, which is the only thing `'+generic'` changes.
41. **Round 5: `AUD.ready_min`, name a consumer or drop it.** It was dropped. Every reader of `AUD_READY_MIN` (the Gate, the cosine horizon and the startup refusal) is inside AUD. K9 reads Cadences periods only, and this is not one. AUD therefore has 17 entry points, the tree 169 after S6 and 186 with VID. This supersedes "So AUD is 18, not 19" in item 16.
42. **Round 5: the `AUD_SHIFT_STAMP` surface, (a) a RefreshReport field plus an accessor, or (b) an early `AUD.refresh` for pre-readiness acts.** Neither was taken whole. RefreshReport's `stamp` carries the decision after readiness. 'always' now covers acts from readiness on, because before readiness there is no snapshot for a stamp to protect, and an act then stamps only when the text view moved. An accessor would be a new entry point and would move every count. An `AUD.refresh` call before readiness has no snapshot to read.
43. **Round 5: the Gate's first test, (a) test at `AUD_READY_MIN` itself, or (b) move the first media window.** (b) was taken, in the form "after the flush that follows the Gate's first test", which is window 3002 on a fresh run at `OPT_BATCH_WINDOWS` 1. (a) needs a second one-shot beside `aud.probe`.
44. **Round 5: AUD-only acts before readiness, (a) evaluate 'aud.refresh' only after readiness, or (b) raise no act on a fire before readiness.** (b) was taken. The key's phase is unchanged, so item 5's act spacing, and with it the probe-cost figures, stand.
45. **Round 5: `AUD_CODEC_LR_MIN_FRAC`'s domain.** The domain is (0, 1], not the finding's (0.0, 1.0). A value of 1.0 means a constant lr at the peak, which is a legitimate setting, not a freeze.
46. **Round 5: the 0.30 figures.** The finding's "D3's codecs (exact 0.204-0.259)" covers tones only, and D3 melody reads 0.203 / 0.141. The text therefore names D3's codecs without that range and keeps both families' readings in its list.
