# Proposal 04 revision — checklist

This file maps every critic issue (1 blocking, 9 major, 7 minor) and every "missing" item to the
place in `docs/proposals/04_SELF_REGULATION.md` that answers it. It also lists the numbers this
revision corrected.

The critic's text is in `workflow_result.json` → `critic`. Section numbers below are the
proposal's.

## Blocking and major issues

| # | Severity | Issue (short) | Decision | Where answered |
|---|---|---|---|---|
| 1 | blocking | At 2 live areas the 0.5 cap forces 0.5 / 0.5; pure-add has 1; only ρ is regulated, mostly at its cap | R-1: relative cap `min(DATA_FOCUS_CAP_MULT / n_live, 1 − others' floors)`, `DATA_FOCUS_CAP_MULT` 3 (equals 0.5 at 6 live, 0.85 at 2); gauge `data.focus.alloc_freedom` (ABSENT at n_live ≤ 1); a 'focusbed' owner-shape arm; an E1 arm at `DATA_PHASE_LIVE=3` (owner question); the plain statement that only ρ is regulated at the shipped schedule | Headline (2nd bullet); §0 "What is not self-regulated"; §1.0 R-1; §1 item 1 (live shares, alternatives); §3 gauge table; §6 preamble and `DATA_FOCUS_CAP_MULT` row; §7 SR2 (the fixed-LP cap unit test), E1 shapes (a) and (c); §8 Q3 and Q4. Counter-signal reported: d3 `rehearse` (even live split) had ρ 0.197 / 0.193 with the ceiling bound once (§1.0 m2, §2 row 12) |
| 2 | major | forget_hard is level-relative; on end states focus ≥ replay on hard | R-2: end-state and time-integrated gaps are primary; forget_X is secondary with its reference point stated; dissent, E1 rule and the rehearsal-floor question rewritten; `DATA_REHEARSE_MIN` dropped, and `DATA_REHEARSE_EVEN` re-derived from the end-state easy gap | Words; Headline; §0 "What the measurements say"; §1.0 R-2; §1 item 1 reason, item 3; §2 rows 5, 6, 7; §4 "Starving old areas"; §7 E1 primary endpoint; §8 Q6 |
| 3 | major | The newest-area advantage is exposure; a hand schedule reproduces it | R-3: E1 adds a `replay_newest` arm (`DATA_REPLAY_NEWEST` 0.34 of phase bytes, the critic's control) and a compute-matched `replay_cm`; per-phase byte shares beside every per-area gap; the tie-break is fixed in advance and marked as an owner ruling | Headline (1st bullet); §1.0 R-3; §1 item 2; §2 rows 8, 9; §7 E1; §8 Q1, Q2 |
| 4 | major | Absolute LP re-attracts noise in P3 under interference; the whole-run gauge hides it | R-4: signed LP for live areas; absolute rise only for faded need; `noise_demoted.P{k}` and `noise_outdraws.P{k}`; the P3 known-answer test | §0 "Failed where the toy was stressed"; §1.0 R-4; §1 item 1 (live areas, the 'abs' and 'net' alternatives); §2 row 10 (per-phase readings recomputed: P3 re-attraction at 5 of 5 seeds); §3 gauge table; §4 noisy TV; §7 SR2 |
| 5 | major | Claim TD measures surface conformity; fails format variant, impersonation, stale truth; K tuned; Qa cost unreported; CTX is TOK units | R-5: 'observe' stays; the (key, value) spec `DATA_TRUST_CLAIM='kv'` is the build target and 'ctx' the prototype, declared as conformity; new 'focusbed' / E5 worlds (format variant, delimiter liar, impersonation, stale truth, mixed reliability, paraphrase); K sweep reported; Qa cost reported; standing rule that no actuation defaults on while a truthful different-format source is floored; copy detection (SR6) first; TOK units stated | §0; §1.0 R-5; §1 item 8 (spec, stress table, K sweep, costs, standing rules); §2 rows 15, 16, 17; §3 `format_split_floored`; §6 trust rows; §7 SR3, SR6, E3, E5; §8 Q8, Q12 |
| 6 | major | The resume order (draw, then redraws, then seg_log) is not bit-exact | R-6: a redraw is a `seg_log` event (at_byte, shares, rng child, view), replayed in act order with the stream rebuilt at each redraw | §1.0 R-6; §1 item 4 (the act in order, resume); §4 resume divergence; §5 checkpoint and resume, S0b interaction; §7 SR1 resume test (a retok before and after a redraw, `TOK_DROPOUT` 0.1, a unit whose match would cross at_byte, a save between a redraw and the next flush) |
| 7 | major | Retok acts move the probe's tokenization and read as LP or forgetting | R-7: rebase at every act that moved the view (drop the interval; reset best, Lf and Ls; `data.focus.rebased`, `rebase_step`); the fixed-view probe as the alternative; the step measured at SR2 on real text | §1.0 R-7; §1 item 1 (rebase), item 6 (R-7 block); §3 gauge table; §4; §5 (`note_retention(view_moved=)`); §7 SR2 |
| 8 | major | "Telemetry only" untested; `DATA_SYNTH_HOLDOUT` changes the holdout record, which resume refuses | R-8: SR0 bit-identity test (probe ON against OFF); the synthetic holdout resume rule admits 0 → n (`data.holdout_admitted`); recommended ON; listed as a DEFAULT BEHAVIOUR CHANGE | Status paragraph; §0 defaults table; §1.0 R-8; §1 items 6, 7; §4; §6 "Default behaviour changes" 1-3; §7 SR0; §8 Q5 |
| 9 | major | E1's rule is biased to the costly arm and ignores compute | Covered by R-3 (R-9): pre-registered on all-area end-state bits/byte, 5 paired seeds and a one-sided paired t, `replay_cm` charges the probe's compute, the tie-break is fixed in advance | §1.0 R-3 row; §2 rows 24, 25 (probe cost; compute matters: `base_cm` −0.092 / −0.111); §7 E1 |
| 10 | major | 'replay' is wrongly made dependent on the act and SR1 | R-10: 'replay' is built at SR0 inside `data_plan` / `draw_stream` from the phase schedule, with exact startup gates, no redraw log and no act | §0; §1.0 R-10; §1 item 2; §5 "Unchanged surfaces", S0b interaction; §7 SR0 |

## Minor issues

| # | Issue | Adopted? | Where answered |
|---|---|---|---|
| m1 | ReplayFixed iterates a set (PYTHONHASHSEED-dependent) | Adopted: AREAS or name order everywhere; the tree's 'replay' breaks ties in `Plan` order; SR0 cross-hash-seed test; the effect (under 0.004) is stated, and the `replay_late` caveat too | §1.0 m1; §1 item 2; §2 rows 8, 27; §7 SR0 |
| m2 | Rehearsal amount and onset are not emergent | Adopted, partly: both move to "built"; `rho_at_cap_frac` gauge added. The qualification: in d3's even-split `rehearse` arm ρ was below the ceiling (0.197 / 0.193), so the amount is "the ceiling where the gauge reads near 1" | §1.0 m2; §0; §1 item 12; §3 built list and gauge table; §6 `DATA_REHEARSE_MAX` row |
| m3 | Emergence mislabelled (source ranking and tag-TD are built) | Adopted: relabelled as built; the emergence claim is limited to per-source conditionals given the tag; trust inside the model did not emerge | §0; §1.0 m3; §3 |
| m4 | The graft compared a tagged read against a null read | Adopted: like for like first (graft tagged − tags-only tagged −0.081 / −0.165 / −0.143 / −0.183 / −0.062) | §1 item 9; §2 row 20 |
| m5 | The tag enters h and so feeds FAB routing and MEM keys | Adopted: E4 gauges `fab.expert_area_purity` and `mem.hit_area_purity`, with the tag on and off; the head-input alternative is recorded | §1 item 9; §3 gauge table; §4; §7 E4; §8 Q13 |
| m6 | Tree-fit details (a)-(f) | Adopted, all: (a) the redraw-only branch; (b) `fab.blackout_windows`, OPT re-warm inert at `OPT_LR_SHIFT_WARM` 0, worst-case 54% blackout computed; (c) `DATA_EXPOSURE_MAX` becomes a byte ceiling; (d) `Stream.seg_cursor` snapshots; (e) fill `EVAL.holdout_probe` (a signature move adding `n_windows` and `tokenize_fn`, with two root joins; `DEFERRED_ENTRY_POINTS` 23 → 22) instead of a new entry point; (f) functional copies for MIR | §1 items 4, 5, 6; §5 (entry points, runtime Gates, record fields, contract accounting); §7 SR1, SR5 |
| m7 | The testbed is too easy | Adopted: 'focusbed' gains the owner shape (2 live, sequential fades), pure-add, `DATA_PHASE_LIVE` 3, batch 1, the tokenizer in the loop, and format-varied and paraphrased records; 4 × the entities | §3 known-answer corpus; §7 SR0, E1 shapes, E5 |

Rejected minor fixes: none.

## The critic's "missing" list

| # | Missing item | Where answered |
|---|---|---|
| 1 | An arm at the owner's schedule shape (2 live, pure-add 1, batch 1) | §3 'focusbed' schedules; §7 E1 shapes (a)-(c), with pure-add explained (it equals 'planned' unless §8 Q4 admits parent areas); §7 SR2 owner-shape test. Still unmeasured: stated in the Headline and §0 |
| 2 | Hand-set controls strong enough (replay + newest boost; compute-matched replay) | §2 row 8 (the critic's `replay_late`, 2 seeds, cited); §1 item 2 (`DATA_REPLAY_NEWEST`); §7 E1 arms `replay_newest`, `replay_cm` |
| 3 | End-state and time-integrated per-area metrics | Words; §2 rows 5, 6 (recomputed in `rev/metrics.txt`, s0-s4); §7 E1 primary endpoint |
| 4 | Per-phase share gauges | §2 row 10; §3 gauges `noise_demoted.P{k}`, `noise_outdraws.P{k}`, `mastered_demoted.P{k}`, `rho_at_cap_frac.P{k}` |
| 5 | Credibility stress worlds; mixed reliability untested | §1 item 8 stress table (format variant, delimiter liar, impersonation 30% and 50%, stale truth, majority false; **mixed reliability untested**, added); §3 'focusbed' worlds; §7 E5 |
| 6 | A real-text claim audit | §7 E3 (still owed; unmeasured) |
| 7 | Four tests: probe ON/OFF bit-exactness; retok-probe interaction; redraw-interleaved seg_log replay; `DATA_SYNTH_HOLDOUT` resume | §7 SR0 (probe ON/OFF; holdout resume admit and refuse); §7 SR2 (the rebase test for retok and probe); §7 SR1 (the redraw-interleaved resume test) |
| 8 | `TOK.splice` timing on a 17 MB tail | §1 item 4 "Owed"; §7 E2; §8 Q9 (still owed) |
| 9 | Any measurement for frame-rate self-regulation | §1 item 11 (stated: no media measurement); §8 Q15 |
| 10 | Qc is 24 items; the base seed spread dwarfs differences | Words (steps of 0.042); §1 item 8 (the spread 0.25-0.92); §3 and §7 E5 (4 × the entities, Qc 96 items) |

## Numbers corrected or re-qualified in this revision

1. **The last-phase ρ 0.286 / 0.299 / 0.277 is fulltd's.** Focus's is 0.279 / 0.280 / 0.293
   (critic). §1 item 2.
2. **"Fixed replay protects hard 4-7x better" is replaced by end-state readings.**
   - Hard end gap, focus − m27: −0.008 / −0.293 / −0.145 / +0.033 / −0.105.
   - The easy end gap reverses: +0.103 / +0.048 / +0.117 / −0.003 / +0.117.
   - §2 rows 5, 7.
3. **"Noise ... cannot be re-attracted" is withdrawn.** P3 re-attraction at 5 of 5 seeds (§2 row
   10).
4. **"d1 LP loses to matched replay at 3 of 3" is now a wash.** It still loses at s0-s2, but not at
   s3 (−0.039); s4 +0.073 (reproduction, claim 11). §1 item 1, §2 rows 4, 26.
5. **The probe's 18-19% toy wall cost is with MIR.** At the default (MIR off) it is 4.3%
   (`d3/out/focus_nomir_s{0,1}.json`). §1 items 1, 6; §2 row 24.
6. **"LP focus amplifies the liar" is qualified.** It holds at s0 / s1. At s2, drawn false was 0.110
   against cred 0.161. §1 item 8.
7. **Easy's catastrophic forgetting under planned is 0.9-1.9 bits over 5 seeds** (was "1.2-1.9",
   at 3 seeds). §0.
8. **The majority-false result is at 3 seeds (s0, s3, s4), reproduced-weaker.** −0.04 accuracy at
   the new seeds, against −0.21 at s0. §1 item 8, §2 row 17.
9. **The act emulation's 35 acts is confirmed** by the counter `focus.acts` in
   `judge/w/d3/out/fulltd_act6_s{0,1}.json`. §2 row 22.
10. **"'replay' needs the act" is withdrawn** (R-10). §1 item 2.
11. **The "self-regulated rehearsal amount" is now "the ceiling, most of the time"** (m2). §1.0,
    §1 item 3.
12. **New numbers, all from `rev/metrics.txt` and no new training:**
    - the time-integrated gaps (post hoc);
    - the per-phase noise ratios and out-draw counts;
    - the P3 cred and corrob shares;
    - s3 / s4 end-state gaps from the reproduction's JSONs;
    - the `rehearse` arm's ρ;
    - the `base_cm` compute effect (already in d1's outputs, first cited here).

## Checker round

An independent checker found the numbers sound and the critic coverage complete, but reported 8
major and 14 minor tree-fit and accounting problems. Each was verified against the source before
editing, and all 22 are applied. None is rejected.

| # | Finding | Verified at | Fix | Where |
|---|---|---|---|---|
| M1 | `DATA_REPLAY_NEWEST` 1.7 × the even live share gives 0.248, not the critic's control | `critic/w/d3/run.py:159-164` (late 0.34, others (1 − 0.27 − 0.34) / 4) | The lever is now the newest area's share of phase bytes (default 0 = off); the E1 arm uses 0.34 | §1.0 R-3; §1 item 2; §6 row; §7 E1; §5 clock kinds |
| M2 | The redraw event's `rng` collides with S0b's dropout-state field; the helper lacks DATA arguments and does not return the stream | `compose.py` ~2315-2330 (`_set_dropout_state(vocab, event.get("rng"))` runs before the kind test) | The key is `rng_key`; dispatch on kind before any rewind; the helper becomes `(tok, vocab, stream, log, *, dat, areas, plan) -> (stream, seg)`, counted as a private-helper change | §1 item 4; §5 contract accounting |
| M3 | Entry points undercounted | `Cadences.due` and K9 (typed accessors: `EVAL.curve_period`, `CKPT.save_period`); K10 (a producer for `focus`); `data/api.py:1635`, `:1678` (no focus argument) | +`DATA.new_focus`, +`EVAL.retention_period`, `EVAL.src_period`, `DATA.trust_period`; `stream_state` / `restore_stream_state(focus=)` as 2 signature moves; 141 → 152, 7 signature moves, `Focus` record | §5 entry points, signature moves, accounting; §7 SR0, SR2-SR4 |
| M4 | About 44 levers uncounted; `DATA_SYNTH_KIND` does not exist; the `DATA_REHEARSE_PARENT` row is missing | contract K4 (262), headings DATA 18 / EVAL 17 / LM 12 / OPT 13; `data/api.py:751` (`synthetic:order2`) | Per-package accounting +44 (262 → 306; DATA 53, EVAL 20, LM 17, OPT 14), census rows, A10 re-render; `DATA_SYNTH_KIND` declared new; the §6 row added | §5 contract accounting; §6 |
| M5 | The '' → 160 default derives an EVAL value from a DATA lever, which is a wire | `spine/lever.py:268` | Literal 1000; the root refuses 'retention' with 0 and prints a notice above 160; the retention arms set 160. Chosen over declaring a wire (20 of 25) because one cadence does not earn a wire, and a check over two Configs derives nothing | §1 item 6; §5 wires; §6 row |
| M6 | The synthetic-holdout admission cannot work: all three recorded fields move | `data/api.py:1660-1663`, `:1739-1747` | Admit when the recorded key is None and size 0, for all three fields; counted `data.holdout_admitted` | §1 item 7 |
| M7 | Filling `holdout_probe` named no producers | `compose.py:1690` deferral reason; contract §3.0.2 ("a `logits_fn` ... deliberately not there") | Root joins `_holdout_tokenize` (TOK at the current view, no labels, no dropout) and `_eval_logits_fn` (FAB `training=False`, carried novelty and live domains), in §3.0.2 and `ROW_ARGUMENTS_ELSEWHERE`; the `tokenize_fn` keyword counted in the signature move; `eval.holdout.cuts` separates the probe's cuts from `tok.segment_remap` | §1 item 6; §5 |
| M8 | Default behaviour change 2 is inert at the shipped defaults | `DATA_STREAM_BYTES` 120000 (about 506-937 windows) against 1000, first fire at 1001 | Stated as PRESENT-and-0 on a default run, where the run-boundary reads are the change; the SR0 test runs at cadence 50 over at least 500 windows with FAB and MEM on | §1 item 6; §6 item 2; §7 SR0 |
| m1 | "+1.87 / +1.65 / +1.23 untagged" is planned's | d2 tags `forget_easy` 1.585 / 1.656 / 1.317 | Relabelled; the tags arm's own untagged read added | §1 item 9 |
| m2 | Liar amplification is 4 of 5 seeds | `repro/d3/out/focus_s{3,4}.json` (false 0.216 / 0.221 against cred 0.132 / 0.123) | Fixed | §1 item 8; §4 |
| m3 | "–" used for runs that exist | fulltd s1 / s2 conflicted 45 / 48; graft Qa s3 / s4 0.750 / 0.833 | Filled in | §1 item 9; §2 rows 15, 20; §3 gauge |
| m4 | The 'exp3' alternative lacked s4 | lp − m27 +0.073 at s4 | All five seeds; worse at 4 of 5 | §1 item 1 |
| m5 | "The boost gets most of that" is imprecise | rl − m27 −0.037 / −0.043 against focus − m27 −0.026 / −0.105 | "All of it at s0, 41% at s1" | §1 item 1 |
| m6 | ACT_EVERY / WARM / HREC are counts of probes | lever units | U.COUNT stated | §5 clock kinds |
| m7 | The TV gate was never emulated | `judge/w/d3/run_act.py:260-264` | Qualified "cost nothing" and "about 21 acts"; `DATA_FOCUS_SHIFT_TV` added to the unmeasured list | §1 item 4; §2 row 22; §6 |
| m8 | HEAD's act description; TOK counts redraw splices | `loop.py` ~1203-1250; `tok/api.py` ~1712-1713 | HEAD described exactly; retok acts = `tok.retok_mid_epoch` − `loop.acts_redraw` | §1 item 4 |
| m9 | E5's item step | 96 items per class | 0.010 | §7 E5 |
| m10 | K8's conflict history | `critic/out/td_base_K8_i0.3_s0.json` (1 at step 1000) | "0 through step 500" | §1 item 8; §2 row 16 |
| m11 | E1 rule 2 could make `replay_cm` the default | — | Excluded as a compute control | §7 E1 |
| m12 | "'retention' is exactly 'planned'" at pure-add | — | Zero-TV acts refused (including at phase entry); 'retention' trains as 'planned' and pays the probe | §0; §1 item 4; §6; §7 E1 |
| m13 | `replay_cm` is unpaired on synthetic shapes | `data/api.py:730` (per-area size scales with `DATA_STREAM_BYTES`) | Labelled unpaired on (a) and (d) with Welch's t; paired on real areas (b) and (c), which decide | §7 E1 |
| m14 | Line number; the tag mask's RNG child | `data/api.py:381`; `RNG_SUBSYSTEMS` (K8) | Line 381; `data.tag.e{E}` under a new parent `data.tag` | §1 items 7, 9; §5 |

## Evidence files this revision adds

- `rev/metrics.py`: recomputes the goal-B and per-phase readings from the preserved JSONs. Run
  `python3 metrics.py <prototypes dir> > metrics.txt` from `rev/`, with `OMP_NUM_THREADS=1`.
- `rev/metrics.txt`: its output, which the proposal cites.
- `rev/checklist.md`: this file.

## Checker round 2 (applied by the orchestrator)

| Finding | Fix | Where |
|---|---|---|
| N1 E1 rule 1 would ship 'retention' at an untested cadence | rule 1 also sets `EVAL_RETENTION_EVERY` 160; arm renamed | §7 E1 arms and rule |
| N2 `redraw_tail` had no `seed` | `seed` added (RUN.seed, as `draw_stream`) | §5 item 4 |
| minor a `DATA_REHEARSE_PARENT` conditional build | Q4 made conditional; 306 / 305 stated | §8 Q4 |
| minor b `_holdout_tokenize` must pass `view=` | stated, with the cache/counter reason | §3 joins |
| minor c record types | `FocusPlan` and `Reading` counted beside `Focus` | §5 contract accounting |
| minor d stale checklist row m6(e) | corrected | this file |
