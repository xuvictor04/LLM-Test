"""Round-2 tightening pass: reflow and compress the text patch_round2.py added; fix the tail figure."""
import sys
P = "/tmp/claude-0/-home-user-LLM-Test/e880caf7-1208-58de-93fd-49c41549bf70/scratchpad/dec/DECISIONS.md"
s = open(P, encoding="utf-8").read()
R = []
def r(old, new):
    R.append((old, new))

r("""- **N3. The owner's explicit rulings stand.** Where one collides with R1, the collision is
  documented and put back to the owner, not overridden. 03b's D-1 to D-10 are recorded as its design
  workflow's decisions, with no owner quote (`notes/AGENT_STATE.md:30-43`), so they are revisable
  under R0 (03b-16.23, C14, C44) unless the owner says he took one.""",
"""- **N3. The owner's explicit rulings stand.** Where one collides with R1, the collision is
  documented and put back to the owner, not overridden. 03b's D-1 to D-10 carry no owner quote (its
  design workflow's decisions, `notes/AGENT_STATE.md:30-43`), so they are revisable under R0
  (03b-16.23, C14, C44) unless the owner says he took one.""")

r("""5. **Name the continuation learning rate.** Today a continued run from a parent that finished its run
   either trains at the floor (5% of peak) for ever or, for one more epoch of equal length (today's only
   continuation), jumps to about 53-61% of peak with no ramp, depending on whether a tokenizer act
   happened to fire in the parent (an act-parent stopped early resumes at its own rate instead,
   `verify/emp2/lrcont.py`).
   A new lever, `OPT_LR_CONTINUE`, keeps today's behaviour as its
   default (labelled on every resume) and lets the continue preset choose.""",
"""5. **Name the continuation learning rate.** Today a continued run from a parent that finished its
   run either trains at the floor (5% of peak) for ever or, for one more epoch of equal length (today's
   only continuation), jumps to about 53-61% of peak with no ramp, depending on whether a tokenizer act
   happened to fire in the parent (an act-parent stopped early resumes at its own rate,
   `verify/emp2/lrcont.py`). A new lever, `OPT_LR_CONTINUE`, keeps today's behaviour as its default
   (labelled on every resume) and lets the continue preset choose.""")

r("""6. **Replay after training, carried with the model.** Build `DATA_REHEARSE_PARENT` (default OFF,
   ON in the continue preset; **[OWNER] O9**) and an in-checkpoint replay reservoir kept disjoint from the probe
   set. Pure-add""",
"""6. **Replay after training, carried with the model.** Build `DATA_REHEARSE_PARENT` (default OFF,
   ON in the continue preset; **[OWNER] O9**) and an in-checkpoint replay reservoir kept disjoint from
   the probe set. Pure-add""")

r("""   origins, under per-origin caps and canary probes (**[OWNER] O5**, **O18**). → NEW-07, NEW-18, 04-Q12,
   C05-C08.""",
"""   origins, under per-origin caps and canary probes (**[OWNER] O5**, **O18**). → NEW-07, NEW-18,
   04-Q12, C05-C08.""")

r("""8. **Size every experiment so its phases actually happen.** At the pre-registered 20 MB /
   20,000-window shape (four phases, each 5 MB wide) no run reaches the last phase. With frozen
   segmentation (`d97779d`, or `TOK_RETOK_EVERY=0`) it reads about 3.8 MB and never leaves phase 1.
   At HEAD, k3000 acts raise bytes per window from about 190 to about 307, so it reads about 5.19 MB
   and enters phase 2 only in its last ~790 windows; phases 3 and 4 never come
   (`verify/emp2/actsim.py`). Every E-series experiment (04 runs E1-E6 at that shape), the WORLD re-run
   and the U-series are resized to one whole epoch, and a run that does not consume the whole epoch,
   and so does not reach the last phase, is reported invalid. → 04-Q1, PENDING-WORLD_FEEDBACK, NEW-12,
   Appendix A (critic blocking 2).""",
"""8. **Size every experiment so its phases actually happen.** At the pre-registered 20 MB /
   20,000-window shape (four 5 MB phases) no run reaches the last phase: with frozen segmentation
   (`d97779d`, or `TOK_RETOK_EVERY=0`) it reads about 3.8 MB and never leaves phase 1; at HEAD's k3000,
   acts raise bytes per window from about 190 to about 307, so it reads about 5.19 MB and enters
   phase 2 only in its last ~790 windows (`verify/emp2/actsim.py`). E1-E6 (04 runs all six at that
   shape), the WORLD re-run and the U-series are resized to one whole epoch, and a run that does not
   consume the whole epoch is reported invalid. → 04-Q1, PENDING-WORLD_FEEDBACK, NEW-12, Appendix A
   (critic blocking 2).""")

r("""    components (family h; scope **[OWNER] O3**). An ablation ladder tests the whole architecture against a plain LM with
    replay on B's endpoints.""",
"""    components (family h; scope **[OWNER] O3**). An ablation ladder tests the whole architecture
    against a plain LM with replay on B's endpoints.""")

r("""- *Whether its data varied with the seed:* it did, provided the fleet ran the default synthetic
  source (one log's data banner settles it; LOW-D-A13, §8 0.2). The full `RUN_SEED` path gives a
  different stream per seed, with identical per-seed hashes at HEAD and at `d97779d`
  (`verify/emp2/seedvar.out`), and the fleet's script passes `RUN_SEED` (`d97779d:gpu_world.sh:346`).
  The identical vocab 1106 and 594 mints per seed are fixed by the mint budget (512 + 99 × 6), not by
  the text. `docs/04_CONTRACT.md:3575-3577` ("all five seeds trained on the same text") is wrong
  unless the banner shows otherwise.""",
"""- *Whether its data varied with the seed:* it did, provided the fleet ran the default synthetic
  source (one log's data banner settles it; LOW-D-A13, §8 0.2). Each seed gives a different stream,
  with the same per-seed hashes at HEAD and `d97779d` (`verify/emp2/seedvar.out`), and the fleet's
  script passes `RUN_SEED` (`d97779d:gpu_world.sh:346`); the identical vocab 1106 and 594 mints per
  seed are the mint budget (512 + 99 × 6), not the text. `docs/04_CONTRACT.md:3575-3577` ("all five
  seeds trained on the same text") is wrong unless the banner shows otherwise.""")

r("| The trigger has fired for default runs: at HEAD's k3000 the first act raises bytes per token +8.6% over the whole re-segmented tail and +18% over the next 3000 windows, about +60% by the fifth act (`verify/emp2/actsim.py`). At the CPU k1000 760 KB shape (three acts) it sits at the 5% line (+4.2% whole tail, +5.0% run average). |",
  "| The trigger has fired for default runs: at HEAD's k3000 the first act raises bytes per token +8.8% over the whole re-segmented tail and +18% over the next 3000 windows, about +62% by the fifth act (`verify/emp2/actsim.py`). At the CPU k1000 760 KB shape (three acts) it sits at the 5% line (+4.2% whole tail, +5.0% run average). |")

r("The 5% trigger has fired for default runs: at HEAD's k3000 the first act raises bytes per token +8.6% over the whole re-segmented tail (13,443,285 → 12,384,184 ids) and +18% over the next 3000 windows, and about +60% by the fifth act (`verify/emp2/actsim.py`, seeds 0-1; model-free, bit-exact against the real k1000 run). At the CPU k1000 760 KB shape (three acts) it sits at the line: +5.0% run average (199.16 against 189.62 bytes/window, `rule_pending_measurements/measured.json`), +4.2% over the whole tail, about +8% just after the first act (`verify/emp/k1000_1300.log`).",
  "The 5% trigger has fired for default runs: at HEAD's k3000 the first act raises bytes per token +8.8% over the whole re-segmented tail (13,059,157 → 12,000,056 tail ids) and +18-19% over the next 3000 windows, and about +62% by the fifth act (`verify/emp2/actsim.py`, seeds 0-1; model-free, bit-exact against a real k1000 run). At the CPU k1000 760 KB shape (three acts) it sits at the line: +5.0% run average (199.16 against 189.62 bytes/window, `rule_pending_measurements/measured.json`), +4.2% over the whole tail (`verify/emp/k1000_1300.log`).")

r("""7. **Stream sizing (critic blocking 2):** 04 §7's run shape for every GPU experiment, E1-E6 ("about
   a 20 MB stream, about 20,000 windows", `docs/proposals/04_SELF_REGULATION.md:1453`), never reaches
   the last of the generated schedule's four 5 MB phases. With frozen segmentation (`d97779d`, or
   `TOK_RETOK_EVERY=0`) it reads 3.75-3.84 MB at about 189 bytes per window and never leaves phase 1
   (`rule_pending_measurements/measured.json`, `verify/emp2/phasepos.py`). At HEAD's k3000 the acts
   raise bytes per window to about 307, so it reads about 5.19 MB, crosses into phase 2 near window
   19,200 and fades eng for its last ~790 windows only; phases 3 and 4 never come, so py never fades
   (`verify/emp2/actsim.py`, seeds 0-1). Either way the draws could differ little beyond probe cost,
   and E2's and E4's faded-area readings (04-Q6, Q7, Q13, NEW-10) could not read. E1-E6 are sized like
   `EXP=retok`: `DATA_STREAM_BYTES` = WINDOWS × the measured bytes per window, one whole epoch, window
   cap out of reach. `DATA.data_plan`'s phase bounds go into the pre-registration, and a run that does
   not consume the whole epoch, and so does not reach the last phase, is reported **invalid**, not as
   a tie.""",
"""7. **Stream sizing (critic blocking 2):** 04 §7's run shape for every GPU experiment, E1-E6 ("about
   a 20 MB stream, about 20,000 windows", `docs/proposals/04_SELF_REGULATION.md:1453`), never reaches
   the last of the schedule's four 5 MB phases. With frozen segmentation (`d97779d`, or
   `TOK_RETOK_EVERY=0`) it reads 3.75-3.84 MB and never leaves phase 1 (`verify/emp2/phasepos.py`). At
   HEAD's k3000, acts raise bytes per window from about 190 to about 307, so it reads about 5.19 MB,
   fades eng only in its last ~790 windows, and never fades py (`verify/emp2/actsim.py`, seeds 0-1).
   E2's and E4's faded-area readings (04-Q6, Q7, Q13, NEW-10) could not read either. E1-E6 are sized
   like `EXP=retok`: `DATA_STREAM_BYTES` = WINDOWS × the measured bytes per window, one whole epoch,
   window cap out of reach. `DATA.data_plan`'s phase bounds go into the pre-registration, and a run
   that does not consume the whole epoch, and so does not reach the last phase, is reported
   **invalid**, not as a tie.""")

r("""- Against, in the tree: every route and arm reads 0-15% on held-out combinations. The design-world
  readings are informative: exact 0.94 in-distribution against 0.03 on 200 held-out-combination
  prompts (SE about 0.012; 0-0.15 across its stage-3 arms;
  `results/multimodal_design_2026-09-25/prototypes/design-world/proto/make_data.py:8`,
  `stage3_*.json`), so composition fails at this scale. The 03b prototypes (6-12 prompts, 03b 0b.2
  Floors) and Route 3 (12-16 prompts, `design-hybrid/run_logs/lm_mask*.json`) are uninformative, which
  is why the ruling sets a floor of 100 prompts per area.""",
"""- Against, in the tree: every route and arm reads 0-15% on held-out combinations. The design world's
  are informative: exact 0.94 in-distribution against 0.03 on 200 held-out-combination prompts (SE
  about 0.012; `results/multimodal_design_2026-09-25/prototypes/design-world/proto/make_data.py:8`,
  `stage3_*.json`), so composition fails at this scale. The 03b prototypes (6-12 prompts, 03b 0b.2
  Floors) and Route 3 (12-16, `design-hybrid/run_logs/lm_mask*.json`) are uninformative, hence the
  ruling's floor of 100 prompts per area.""")

r("""- Conflicts noticed: the anchor was measured against, weakly, at 5 of 6 readings yet ships by D-4 (C44: no""",
  """- Conflicts noticed: the anchor was measured against, weakly, at 5 of 6 readings yet ships by D-4 and D-7 (C44: no""")

r("""  after the recovery window, or a canary trip (a canary's trigger-conditioned reading beyond its
  nuisance-calibrated threshold). **Alarms** (reported, escalated after 3 in a row) are KL to the
  anchor and the negative-flip rate, each above a threshold calibrated on nuisance pairs inside the
  same 5% family-wise rate (provisional until §8 4.1), and a plasticity gain below its floor.
  Stability-gap depth is reported only. Every trigger and alarm is in the nuisance calibration, so the
  5% family-wise rate covers the rule as a whole.""",
"""  after the recovery window, or a canary trip (a canary's trigger-conditioned reading beyond its
  nuisance-calibrated threshold). **Alarms** (reported, escalated after 3 in a row) are KL to the
  anchor and the negative-flip rate above thresholds calibrated on nuisance pairs (provisional until
  §8 4.1), and a plasticity gain below its floor. Stability-gap depth is reported only. Every trigger
  and alarm is in the nuisance calibration, so the 5% family-wise rate covers the rule as a whole.""")

bad = []
for old, new in R:
    n = s.count(old)
    if n != 1:
        bad.append((n, old[:90])); continue
    s = s.replace(old, new)
if bad:
    for n, o in bad: print("MATCH", n, repr(o))
    sys.exit(1)
open(P, "w", encoding="utf-8").write(s)
print("applied", len(R))
