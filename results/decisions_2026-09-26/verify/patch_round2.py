"""Round-2 fixer patch for dec/DECISIONS.md. Every replacement must match exactly once."""
import sys
P = "/tmp/claude-0/-home-user-LLM-Test/e880caf7-1208-58de-93fd-49c41549bf70/scratchpad/dec/DECISIONS.md"
s = open(P, encoding="utf-8").read()
R = []
def r(old, new):
    R.append((old, new))

# ---- intro: amendments count (finding 30)
r("none was rejected, and two\n  were applied with an amendment.",
  "none was rejected, and three\n  were applied with an amendment.")

# ---- §2 N3 (finding 21), N4 (findings 18, 25)
r("- **N3. The owner's explicit rulings stand.** Where one collides with R1, the collision is\n  documented and put back to the owner, not overridden.",
  "- **N3. The owner's explicit rulings stand.** Where one collides with R1, the collision is\n  documented and put back to the owner, not overridden. 03b's D-1 to D-10 are recorded as its design\n  workflow's decisions, with no owner quote (`notes/AGENT_STATE.md:30-43`), so they are revisable\n  under R0 (03b-16.23, C14, C44) unless the owner says he took one.")
r("- **N4. Every lever has one stated default.** A protocol is a printed preset of explicit lever values,\n  never a mode that computes other levers (the contract's L1 rule, `docs/04_CONTRACT.md:2557`).",
  "- **N4. Every lever has one stated default.** A protocol is a printed preset of explicit lever values,\n  never a mode that computes other levers (the L1 rule, `.rework/PLAN.md:155`, as the contract applies\n  it to computed defaults, `docs/04_CONTRACT.md:2557`). A value that depends on the parent (the clip,\n  reservoir bytes) is written as a number into the session's manifest by a printed preset builder at\n  launch; no lever reads another lever or a mode at run time.")
# §2 differences from the draft (finding 35)
r("It differs from the conflicts role's draft in\none place: the draft ranked A-openness (its R3) above flexibility (its R4).",
  "It differs from the conflicts role's draft in\ntwo places: the draft ranked A-openness (its R3) above flexibility (its R4), and its closure clause\ncovered A's doors only, where R4 here covers closures for A or B and sends them to the owner.")

# ---- §3.1
r("5. **Name the continuation learning rate.** Today a continued run either trains at the floor (5% of\n   peak) for ever or, for one more epoch of equal length (today's only continuation), jumps to about\n   53-61% of peak with no ramp, depending on whether a tokenizer act happened to fire in the parent.",
  "5. **Name the continuation learning rate.** Today a continued run from a parent that finished its run\n   either trains at the floor (5% of peak) for ever or, for one more epoch of equal length (today's only\n   continuation), jumps to about 53-61% of peak with no ramp, depending on whether a tokenizer act\n   happened to fire in the parent (an act-parent stopped early resumes at its own rate instead,\n   `verify/emp2/lrcont.py`).")
r("6. **Replay after training, carried with the model.** Build `DATA_REHEARSE_PARENT` (default OFF,\n   ON in the continue preset)",
  "6. **Replay after training, carried with the model.** Build `DATA_REHEARSE_PARENT` (default OFF,\n   ON in the continue preset; **[OWNER] O9**)")
r("canary probes (**[OWNER] O5**). → NEW-07, NEW-18, 04-Q12,",
  "canary probes (**[OWNER] O5**, **O18**). → NEW-07, NEW-18, 04-Q12,")
r("8. **Size every experiment so its phases actually happen.** At the pre-registered 20 MB /\n   20,000-window shape a run reads about 3.8 MB and never leaves phase 1 of 4, so no area ever fades.\n   Every E-series experiment (04 runs E1-E6 at that shape), the WORLD re-run and the U-series are\n   resized to one whole epoch, and a run that ends in phase 1 is reported invalid. → 04-Q1, PENDING-WORLD_FEEDBACK, NEW-12, Appendix A (critic\n   blocking 2).",
  "8. **Size every experiment so its phases actually happen.** At the pre-registered 20 MB /\n   20,000-window shape (four phases, each 5 MB wide) no run reaches the last phase. With frozen\n   segmentation (`d97779d`, or `TOK_RETOK_EVERY=0`) it reads about 3.8 MB and never leaves phase 1.\n   At HEAD, k3000 acts raise bytes per window from about 190 to about 307, so it reads about 5.19 MB\n   and enters phase 2 only in its last ~790 windows; phases 3 and 4 never come\n   (`verify/emp2/actsim.py`). Every E-series experiment (04 runs E1-E6 at that shape), the WORLD re-run\n   and the U-series are resized to one whole epoch, and a run that does not consume the whole epoch,\n   and so does not reach the last phase, is reported invalid. → 04-Q1, PENDING-WORLD_FEEDBACK, NEW-12,\n   Appendix A (critic blocking 2).")
r("including unreliable system\n    components (family h).",
  "including unreliable system\n    components (family h; scope **[OWNER] O3**).")

# ---- §3.2 lead block (findings 2, 23)
r("- *Whether its data varied with the seed:* it did. At `d97779d` the full `RUN_SEED` path gives a\n  different stream per seed (`verify/emp/phase_cross.py`), and `gpu_world.sh:438` passes `RUN_SEED`.\n  `docs/04_CONTRACT.md:3575-3577` (\"all five seeds trained on the same text\") is wrong (LOW-D-A13).",
  "- *Whether its data varied with the seed:* it did, provided the fleet ran the default synthetic\n  source (one log's data banner settles it; LOW-D-A13, §8 0.2). The full `RUN_SEED` path gives a\n  different stream per seed, with identical per-seed hashes at HEAD and at `d97779d`\n  (`verify/emp2/seedvar.out`), and the fleet's script passes `RUN_SEED` (`d97779d:gpu_world.sh:346`).\n  The identical vocab 1106 and 594 mints per seed are fixed by the mint budget (512 + 99 × 6), not by\n  the text. `docs/04_CONTRACT.md:3575-3577` (\"all five seeds trained on the same text\") is wrong\n  unless the banner shows otherwise.")
# §3.2 table rows
r("On the toy ρ sat at its cap in 26-47 of 48-49 re-plans. |",
  "On the toy, in the focus and retention arms ρ sat at its cap in 26-47 of 48-49 last-phase re-plans; with tags grafted, in 1-4. |")
r("| The trigger is reached as acts accumulate: at CPU seed 0 the k1000 arm averaged +5.0% bytes per window over the k0 arm (three acts); the first act alone gave about +8% just after it and +4.2% over the whole re-segmented tail. |",
  "| The trigger has fired for default runs: at HEAD's k3000 the first act raises bytes per token +8.6% over the whole re-segmented tail and +18% over the next 3000 windows, about +60% by the fifth act (`verify/emp2/actsim.py`). At the CPU k1000 760 KB shape (three acts) it sits at the 5% line (+4.2% whole tail, +5.0% run average). |")
r("| Floor-forever or an unramped jump, chosen by whether an act fired in the parent. |",
  "| For a parent that finished its run: floor-forever or an unramped jump, chosen by whether an act fired in the parent. |")
r("Build `FAB.contribution` and its producers right after NEW-03 (§8 3.5); defer faded-area culls meanwhile |",
  "Build `FAB.contribution` and its producers right after NEW-03 (§8 3.5); meanwhile, in the continue preset, defer faded-area culls (C37; training runs unchanged, an E2 arm) |")
r("| Closed, on condition the owner confirms one fleet log's data banner | The seeding line is present at `7e902ba` and at `d97779d`; seeds 0-2 give distinct corpora at HEAD. |",
  "| Closed, on condition the owner confirms one fleet log's data banner | The seeding line is present at `7e902ba` and at `d97779d`; seeds 0-2 give distinct corpora at HEAD and at `d97779d` (`verify/emp2/seedvar.out`). |")

# ---- §3.3
r("parents with a revision log (every k3000 run past window 3000) are already at the floor today.",
  "finished parents with a revision log (every k3000 run past window 3000) are already at the floor today.")
r("| A tag cuts faded-area forgetting about fivefold but costs +0.051 bits/byte untagged (t 2.56);",
  "| Both sides are R1, so §2 cannot break the tie: tagged retention against the untagged regression on served prompts of unknown origin, which carry no provenance tag. A tag cuts faded-area forgetting about fivefold but costs +0.051 bits/byte untagged (t 2.56);")
r("| Parent rehearsal (04-Q4) against D2's \"PURE_ADD by default, for now\" |",
  "| Parent rehearsal (04-Q4) against D2 (\"lets keep it as default for now\", `.rework/DECISIONS.md:95`) |")

# ---- note 03-16.4 (finding 8)
r("- Against, in the tree: every route and arm reads 0-15% on held-out combinations, including the one\n  at 0.94 in-distribution (`results/multimodal_design_2026-09-25/prototypes/design-world/`). With 6-12\n  prompts per held-out combination (03b 0b.2 Floors) those readings are uninformative, which is why\n  the ruling sets a floor of 100 prompts per area.",
  "- Against, in the tree: every route and arm reads 0-15% on held-out combinations. The design-world\n  readings are informative: exact 0.94 in-distribution against 0.03 on 200 held-out-combination\n  prompts (SE about 0.012; 0-0.15 across its stage-3 arms;\n  `results/multimodal_design_2026-09-25/prototypes/design-world/proto/make_data.py:8`,\n  `stage3_*.json`), so composition fails at this scale. The 03b prototypes (6-12 prompts, 03b 0b.2\n  Floors) and Route 3 (12-16 prompts, `design-hybrid/run_logs/lm_mask*.json`) are uninformative, which\n  is why the ruling sets a floor of 100 prompts per area.")

# ---- 03b rows
r("(D2's tgtgrad: understanding 0.016 vs 0.078)", "(D2's tgtgrad, 1 seed: understanding 0.016 vs 0.078)")
r("| The record grows about 10 bytes per position (about 26 MB per 20k-window run) → per-session segments. |",
  "| The record is small: acts + 1 events per epoch, each a kind, position, view and dropout-stream state (`src/spine/loop.py:448-450`, `src/spine/compose.py:2299-2330`). What grows is resume time, linear in acts (C36; secondaries (a)) → per-session segments, compaction. 03b's 10 bytes per position (`docs/proposals/03b_LIVE_CODEC.md:415`) applies only to the media extension. |")
r("`AUD_CODES='snapshot'`; `'jit_ema'` an arm. D-5 is narrowed:",
  "`AUD_CODES='snapshot'`; `'jit_ema'` an arm. D-5 (a design-workflow decision, N3) is narrowed:")
r("The 5% trigger is reached as acts accumulate: at CPU seed 0 the k1000 arm averaged 199.16 bytes/window against the k0 arm's 189.62 (+5.0%, three acts; `rule_pending_measurements/measured.json`); about +6.8% over the post-act windows is an estimate. Measured directly, the first act gives about +8% just after it and +4.2% over the whole re-segmented tail (`verify/emp/k1000_1300.log`), so whether it fires depends on which bpt reading the trigger uses. So the re-derive,",
  "The 5% trigger has fired for default runs: at HEAD's k3000 the first act raises bytes per token +8.6% over the whole re-segmented tail (13,443,285 → 12,384,184 ids) and +18% over the next 3000 windows, and about +60% by the fifth act (`verify/emp2/actsim.py`, seeds 0-1; model-free, bit-exact against the real k1000 run). At the CPU k1000 760 KB shape (three acts) it sits at the line: +5.0% run average (199.16 against 189.62 bytes/window, `rule_pending_measurements/measured.json`), +4.2% over the whole tail, about +8% just after the first act (`verify/emp/k1000_1300.log`). So the re-derive,")
# note 03b-16.26 (findings 15, 22)
r("and up to 54% with 04's redraw acts (04 §8 Q9).",
  "and up to 54% with 04's redraw acts (04 §1 item 5, `04_SELF_REGULATION.md:541`).")
r("- The joint budget: if the union of stamping acts keeps FAB in cooldown for more than 20% of windows,\n  FAB is stamped only at acts that move the text view or flip more than `AUD_SHIFT_FLIPS`; OPT keeps\n  every stamp; redraw-only acts stamp OPT only (C14). Text acts always move the view, so at k1000 the\n  alarm cannot be cleared by scoping: it orders a `FAB_COOLDOWN` {400, 100} arm instead (C13).",
  "- The joint budget: redraw-only acts stamp OPT only by default (`DATA_FOCUS_STAMP` 'opt', C14). If\n  the union of stamping acts keeps FAB in cooldown for more than 20% of windows, the alarm orders the\n  stamp-scope arm (FAB stamped only at acts that move the text view or flip more than\n  `AUD_SHIFT_FLIPS`; OPT keeps every stamp) and, at k1000, the `FAB_COOLDOWN` {400, 100} arm: text\n  acts always move the view, so scoping cannot clear the alarm there (C13).")

# ---- 02 rows (findings 31, 37)
r("Coexist behind levers: a hierarchy-depth lever where 0 is today's flat population, bit-identical;",
  "Coexist behind levers: a hierarchy-depth lever, default 0 (OFF: today's flat population, bit-identical);")
r("| A hard depth lever, default 2 levels. CAP becomes",
  "| A separate hard maximum-depth lever, default 2 levels (a bound, inert while 02-R1's depth is 0). CAP becomes")
r("**Now**: defer faded-area culls (C37). |",
  "**Now**: in the continue preset, defer faded-area culls (C37); training runs unchanged, an E2 arm. |")

# ---- 04 rows
r("(b) it is not significantly worse on the time-integrated gap (significantly better wins outright);",
  "(b) it is a tie on E1's primary endpoint: within ε on the time-integrated gap and not significantly different (significantly better wins outright; C25);")
r("0.5 is adopted if it lowers the worst faded area's end-state gap at 3 of 3 seeds and the all-area mean is not significantly worse.",
  "0.5 is adopted if it lowers the worst faded area's time-integrated gap (end-state reported beside it) at 3 of 3 seeds and neither any area nor the all-area mean is worse by more than ε.")
r("Add: `DATA_SRC_CAP`, a count-based per-source byte ceiling per phase, built **OFF** at SR3",
  "Add: `DATA_SRC_CAP`, a count-based byte ceiling per unpromoted origin per session (a training run counts as one session; value **[OWNER] O18**), built **OFF** at SR3")
r("E6 picks the densest cadence costing at most 2% of wall, above a B floor of at least 5 readings per phase at the owner's shape (whole-epoch sizing gives about 5000 windows per phase at 20,000 windows, so 1000 gives 5, arithmetic).",
  "E6 picks the densest cadence costing at most 2% of wall, above a B floor of at least 5 readings per phase at the owner's shape. 1000 does not meet it: at the whole-epoch 3.78 MB shape phase 1 spans about 4,980 windows (189.6 bytes/window) and the first probe fires at window 1001, so phase 1 gets 4; acts shorten phases further (arithmetic; `verify/emp2/actsim.py`). The floor caps the cadence at the shortest phase's windows / 5 (from `DATA.data_plan` and the arm's measured bytes per window), or adds a reading at each phase start; E6's arms are checked against it.")
r("`DATA_REHEARSE_MAX` bound ρ in 53-96% of P3 re-plans,",
  "`DATA_REHEARSE_MAX` bound ρ in 53-96% of P3 re-plans in the focus and retention arms (1-4 of 49 with tags grafted),")
r("7. **Stream sizing (critic blocking 2):** 04 §7's run shape for every GPU experiment, E1-E6 (\"about\n   a 20 MB stream, about 20,000 windows\", `docs/proposals/04_SELF_REGULATION.md:1453`), reads about\n   3.8 MB at about 189 bytes per window, while the generated schedule's phases are 5 MB wide at 20 MB\n   (`rule_pending_measurements/measured.json`). The run never leaves phase 1, so no area fades and the\n   draws could differ only by probe cost; E2's and E4's faded-area readings (04-Q6, Q7, Q13, NEW-10)\n   could not read either. E1-E6 are sized like `EXP=retok`: `DATA_STREAM_BYTES` =\n   WINDOWS × the measured bytes per window, one whole epoch, window cap out of reach. `DATA.data_plan`'s\n   phase bounds go into the pre-registration, and a run that ends in phase 1 is reported **invalid**,\n   not as a tie.",
  "7. **Stream sizing (critic blocking 2):** 04 §7's run shape for every GPU experiment, E1-E6 (\"about\n   a 20 MB stream, about 20,000 windows\", `docs/proposals/04_SELF_REGULATION.md:1453`), never reaches\n   the last of the generated schedule's four 5 MB phases. With frozen segmentation (`d97779d`, or\n   `TOK_RETOK_EVERY=0`) it reads 3.75-3.84 MB at about 189 bytes per window and never leaves phase 1\n   (`rule_pending_measurements/measured.json`, `verify/emp2/phasepos.py`). At HEAD's k3000 the acts\n   raise bytes per window to about 307, so it reads about 5.19 MB, crosses into phase 2 near window\n   19,200 and fades eng for its last ~790 windows only; phases 3 and 4 never come, so py never fades\n   (`verify/emp2/actsim.py`, seeds 0-1). Either way the draws could differ little beyond probe cost,\n   and E2's and E4's faded-area readings (04-Q6, Q7, Q13, NEW-10) could not read. E1-E6 are sized like\n   `EXP=retok`: `DATA_STREAM_BYTES` = WINDOWS × the measured bytes per window, one whole epoch, window\n   cap out of reach. `DATA.data_plan`'s phase bounds go into the pre-registration, and a run that does\n   not consume the whole epoch, and so does not reach the last phase, is reported **invalid**, not as\n   a tie.")

# ---- 4.5 rows
r("i.e. 0.056 / 0.073 / 0.102 at f = 0.05 / 0.10 / 0.15 (arithmetic).",
  "i.e. about 0.06 / 0.07-0.08 / 0.10-0.11 at f = 0.05 / 0.10 / 0.15 (the closed form ignores warmup; the tree's `_schedule` with its 1000-step warmup at a 20,000-step horizon gives 0.057 / 0.076 / 0.107, `verify/numbers/lr_check.py`).")
r("| **Closed, on one condition.** The per-area seeding line is present at `7e902ba:src/data/api.py:733` (2026-09-03) and at `d97779d:src/data/api.py:734` (the commit that recorded the fleet's result), so the 2026-09-24 fleet's seeds varied the corpus; seeds 0-2 give distinct bodies at HEAD (`inv/seedcheck.py`);",
  "| **Closed, on one condition.** The per-area seeding line is present at `7e902ba:src/data/api.py:733` (2026-09-03) and at `d97779d:src/data/api.py:734` (the commit that recorded the fleet's result), and the fleet's script passes `RUN_SEED` (`d97779d:gpu_world.sh:346`), so the 2026-09-24 fleet's seeds varied the corpus; seeds 0-2 give distinct bodies at HEAD (`inv/seedcheck.py`) and identical per-seed hashes at `d97779d` (`verify/emp2/seedvar.out`);")
r("The archive's retok at 3000 gave held-out 4.364 bits/byte against 2.175 at 0,\n  but 22 of 23 retoks",
  "The archive's retok at 3000 gave held-out 4.364 bits/byte against 2.175 at 0\n  (not a clean single-knob comparison: `RETOK_EVERY=0` also disabled signature batching, `79dac6c`),\n  and 22 of 23 retoks")

# ---- FRAME (findings 25, 27, 31)
r("(O6; arms: floor, plateau 0.1 and 0.25, rewarm 0.5\n   and 1.0, budget-regulated).",
  "(O6; arms: floor, plateau 0.1 and 0.25, rewarm 0.5\n   and 1.0, regulated).")
r("2. **Replay ON.** `DATA_DRAW='replay'`, `DATA_REPLAY_SHARE` 0.27, `DATA_REHEARSE_PARENT` True: the\n   parent's areas",
  "2. **Replay ON.** `DATA_DRAW='replay'`, `DATA_REPLAY_SHARE` 0.27, `DATA_REHEARSE_PARENT` True\n   (**[OWNER] O9**): the parent's areas")
r("3. **Rollback.** `CKPT_EVERY` equal to the probe cadence; `CKPT_BEST_KEEP` ≥ 2;",
  "3. **Rollback.** `CKPT_EVERY` equal to the probe cadence (1000; 333 if k1000 ships); `CKPT_BEST_KEEP` 2;")
r("5. **A per-step damage bound.** `OPT_GRAD_CLIP` at the parent's recorded `opt.grad_norm.p99` (grad\n   norms travel in OPT's checkpoint state);",
  "5. **A per-step damage bound.** `OPT_GRAD_CLIP` at the parent's recorded `opt.grad_norm.p99` (grad\n   norms travel in OPT's checkpoint state; the preset builder writes the number, N4);")

# ---- §4.6
r("The SIG-width trigger has fired (03b-16.33).",
  "The SIG-width trigger has fired at HEAD's k3000 cadence (03b-16.33).")
r("Stays **OFF**; `WORLD_ENABLED` stays **ON**;",
  "Stays **OFF**; `WORLD_ENABLED` stays **ON** (**[OWNER] O13**: OFF if the re-run shows a retention cost beyond ε);")

# ---- §5
r("`OPT_LR_CONTINUE` ∈ {'as_logged', 'floor', 'rewarm', 'plateau'}, default **'as_logged'**:",
  "`OPT_LR_CONTINUE` ∈ {'as_logged', 'floor', 'rewarm', 'plateau', 'regulated'}, default **'as_logged'**:")
r("'plateau' uses `OPT_LR_PLATEAU` (0.25 when selected) and `OPT_LR_CONT_WARM` 1000.",
  "'plateau' uses `OPT_LR_PLATEAU` (0.25 when selected) and `OPT_LR_CONT_WARM` 1000; 'rewarm' ramps to `OPT_LR_REWARM` × peak (0.5 when selected) and re-decays over the session; 'regulated' sets each session's plateau from the previous gate's margin against ε (the ADR form), built after NEW-04.")
r("| Session-chain arms: floor / plateau 0.1, 0.25 / rewarm 0.5, 1.0 / budget-regulated, 5 seeds,",
  "| Session-chain arms: floor / plateau 0.1, 0.25 / rewarm 0.5, 1.0 / regulated, 5 seeds,")
r("in the preset, interim size equal in **bytes** to the area's held-out block), plus a **separate, never-drawn probe set**;",
  "in the preset, interim size equal in **bytes** to the area's held-out block, written as a number by the preset builder), plus a **separate, never-drawn probe set**;")
r("Parent areas are read from disk, then the reservoir, and refused only if neither exists. The session operating default",
  "Parent areas (**[OWNER] O9**) are read from disk, then the reservoir, and refused only if neither exists. The session operating default")
r("  - Every experiment's non-inferiority margin is ε, fixed in advance, not an SE (C04).",
  "  - Every B-endpoint comparison (per-area bits/byte) has non-inferiority margin ε, fixed in advance,\n    not an SE (C04). Codec-attribute criteria (recover exact at S3: 03b-16.24, 03b-16.29) keep their\n    pre-registered SE margins: ε is a bits/byte budget and does not transfer to them.")
r("- **Combination rule, pre-registered (critic):** rollback **triggers** are a worst-area breach of ε\n  after the recovery window, or a canary trip. **Alarms** (reported, escalated after 3 in a row) are\n  KL, negative flips and a plasticity gain below its floor. Every trigger is included in the\n  nuisance calibration, so the 5% family-wise rate covers the rule as a whole.",
  "- **Combination rule, pre-registered (critic):** rollback **triggers** are a worst-area breach of ε\n  after the recovery window, or a canary trip (a canary's trigger-conditioned reading beyond its\n  nuisance-calibrated threshold). **Alarms** (reported, escalated after 3 in a row) are KL to the\n  anchor and the negative-flip rate, each above a threshold calibrated on nuisance pairs inside the\n  same 5% family-wise rate (provisional until §8 4.1), and a plasticity gain below its floor.\n  Stability-gap depth is reported only. Every trigger and alarm is in the nuisance calibration, so the\n  5% family-wise rate covers the rule as a whole.")
r("- **Anchors:** the preset requires `CKPT_DIR`, keeps the parent as the anchor, sets `CKPT_BEST_KEEP`\n  ≥ 2,",
  "- **Anchors:** the preset requires `CKPT_DIR`, keeps the parent as the anchor, sets `CKPT_BEST_KEEP`\n  2,")

# ---- §6 conflicts
r("One lever family, `OPT_LR_CONTINUE` ∈ {'as_logged', 'floor', 'rewarm', 'plateau'};",
  "One lever family, `OPT_LR_CONTINUE` ∈ {'as_logged', 'floor', 'rewarm', 'plateau', 'regulated'};")
r("a regression 1.5× the original budget is caught 25-46% of the time.",
  "a regression 1.5× the original budget is caught 36-46% of the time at 4-8 areas (25% at 20).")
r("parent anchor per session, release anchor cumulative; every experiment margin is ε. |",
  "parent anchor per session, release anchor cumulative; every B-endpoint margin is ε (codec-attribute criteria keep their pre-registered SE margins). |")
r("items from use enter as quarantined writes. | R1 over R2 |",
  "items from use enter as quarantined writes. | R1 as budget (the R2 cost is accepted until arms show ε holds without it) |")
r("and at `AUD_REFRESH_EVERY`. | R0 (stay in the measured regime); R1 |",
  "and at `AUD_REFRESH_EVERY`. | R0 (stay in the measured regime); R1; D-5 is not an owner ruling (N3) |")
r("a mode that computes levers is the L1 defect (`docs/04_CONTRACT.md:2557`), and FRAME itself forbids it.",
  "a mode that computes levers is the L1 defect (`.rework/PLAN.md:155`, applied at `docs/04_CONTRACT.md:2557`), and FRAME itself forbids it.")
r("no lever reads a mode or another lever; refusals",
  "no lever reads a mode or another lever; parent-dependent values (the p99 clip, reservoir bytes) are written as numbers by a printed builder at launch; refusals")
r("| The owner's trade (O7): R1 against R4 |",
  "| The owner's trade (O7): R1 against R1 (tagged retention against the untagged regression on served prompts of unknown origin) |")
r("(caption worse 11 of 16, understanding worse 5 of 8, a ceiling cost at 7 of 8;",
  "(caption worse 11 of 16, understanding worse 5 of 8, a ceiling cost at 7 of 8, not pairs;")
r("every route reads 0-15% on held-out combinations, with 6-12 prompts per combination, about 32 trained combinations, and an order-2 Markov generator. |",
  "every route reads 0-15% on held-out combinations. The design world's 0.94 → 0.03 at n = 200 is informative evidence that composition fails at this scale; the 03b prototypes (6-12 prompts) and Route 3 (12-16 prompts, about 32 trained combinations) are not; DATA's generator is order-2 Markov. |")
r("B's endpoints decide. A tie within the pre-registered margin ε goes to the flexible option",
  "B's endpoints decide. A tie (within ε on the time-integrated gap and not significantly different) goes to the flexible option")
r("03b-16.33's own trigger has fired.", "03b-16.33's own trigger has fired at HEAD's k3000 cadence.")
r("while the need signal that should spare useful experts is void (P1-C3; `FAB.contribution` deferred).",
  "while the need signal that should spare useful experts is void (`FAB.contribution` raises `NotImplementedError` and its producers are missing, `src/spine/compose.py:1808-1818`).")
r("run the p99.9 and clip-off arms. | R1 over R2; R0 |",
  "run the p99.9 and clip-off arms. | R1 as budget (the R2 cost is accepted until arms show ε holds without it); R0 |")
r("| `AUD_ANCHOR_W` 10 (D-4) was measured against", "| `AUD_ANCHOR_W` 10 (D-4, D-7) was measured against")
r("B's cumulative-drift guard is the drift budget and the release-anchor arm. | R0; N3 (D-4) |",
  "B's cumulative-drift guard is the drift budget and the release-anchor arm. | R0 (D-4 and D-7 are design-workflow decisions, N3) |")

# ---- §7.1 row 3
r("| Every composition route reads 0-15% on held-out combinations (uninformative at 6-12 prompts each and about 32 trained combinations; C23). |",
  "| Every composition route reads 0-15% on held-out combinations. The design world's 0.03 on 200 prompts (0.94 in-distribution) shows composition failing at this scale; the 6-16-prompt readings are uninformative (C23). |")

# ---- §8 (finding 36)
r("| 0.7 | Composition diversity pilot on the design-world harness, 1-2 seeds | 03-16.4, C23 | [CPU] |\n", "")
r("| 0.8 | Resume wall time as a function of the number of acts |", "| 0.7 | Resume wall time as a function of the number of acts |")
r("| 4.2 | Continuation LR arms on the session chain (floor / plateau 0.1, 0.25 / rewarm 0.5, 1.0 / budget-regulated), born-group clocks ON vs OFF, clip p99 / p99.9 / off; 5 seeds, cooled branches | NEW-05, C01, C02, C42, O6 | [CPU] |",
  "| 4.2 | Continuation LR arms on the session chain (floor / plateau 0.1, 0.25 / rewarm 0.5, 1.0 / regulated), born-group clocks ON vs OFF, clip p99 / p99.9 / off, uniform vs tiered uptake; 5 seeds, cooled branches | NEW-05, NEW-09, C01, C02, C42, O6 | [CPU] |")
r("consolidation sessions; anchor retention with late discovery; the read-only side path's bit-identity | NEW-07, NEW-18, C05-C08, C35 | [CPU] |",
  "consolidation sessions; anchor retention with late discovery; the read-only side path's bit-identity; delete-by-session and delete-by-origin exact, and lineage rollback reproducing the anchor's readings | NEW-07, NEW-08, NEW-18, C05-C08, C35 | [CPU] |")
r("| 4.11 | The standing \"B can add A later\" fixture | NEW-14 | [CPU] |",
  "| 4.11 | The standing \"B can add A later\" fixture | NEW-14 | [CPU] |\n| 4.12 | Composition diversity pilot on the design-world harness, 1-2 seeds (A and the belief, after the B core) | 03-16.4, C23 | [CPU] |")

# ---- Appendix A
r("None was rejected. Two were applied with an amendment, stated in the row.",
  "None was rejected. Three were applied with an amendment, stated in the row.")
r("one combination rule (triggers vs alarms); every experiment margin is ε.",
  "one combination rule (triggers vs alarms); every B-endpoint margin is ε.")
r("phase bounds in each pre-registration; a run ending in phase 1 is invalid. 04-6.2's floor recomputed at the corrected shape (5 readings per phase at 1000). |",
  "phase bounds in each pre-registration; a run that does not consume the whole epoch is invalid. The premise holds for frozen segmentation; at HEAD's k3000 the shape reaches phase 2 for its last ~790 windows only (04-Q1 note 7). 04-6.2's floor recomputed: 1000 gives 4 readings in phase 1, below the floor of 5. |")
r("| **Applied.** The rules run as arms in E2; from SR0 on every training run reports",
  "| **Applied, amended** (not in the retok fleet: its counters are built with SR0). The rules run as arms in E2; from SR0 on every training run reports")

# ---- Appendix B
r("| `OPT_LR_PLATEAU` | OPT | 0.25 (read only under 'plateau') | Per §8 4.2 | FRAME; provisional |",
  "| `OPT_LR_PLATEAU` | OPT | 0.25 (read only under 'plateau') | Per §8 4.2 | FRAME; provisional |\n| `OPT_LR_REWARM` | OPT | 0.5 (read only under 'rewarm') | Per §8 4.2 | NEW-05; provisional; arm 1.0 |")
r("| The parent's recorded `opt.grad_norm.p99` | CONTRACT-Q-OPT-3, FRAME (5) |",
  "| The parent's recorded `opt.grad_norm.p99`, written as a number by the preset builder (N4) | CONTRACT-Q-OPT-3, FRAME (5) |")
r("| `DATA_REHEARSE_PARENT` | DATA | False | True | 04-Q4 |",
  "| `DATA_REHEARSE_PARENT` | DATA | False | True (**[OWNER] O9**) | 04-Q4 |\n| `DATA_SYNTH_HOLDOUT` | DATA | ON (built at SR0; pending fleets pin 0) | ON | 04-Q5 |")
r("| `DATA_RESERVOIR_BYTES` | DATA | 0 | The area's held-out block size, in bytes | NEW-06; interim |",
  "| `DATA_RESERVOIR_BYTES` | DATA | 0 | The area's held-out block size in bytes, written as a number by the preset builder | NEW-06; interim |")
r("| `EVAL_RETENTION_EVERY` | EVAL | 1000 (ON after SR0) | At most a third of the shortest stamp interval (**[OWNER] O11**) | 04-6.2, C03 |",
  "| `EVAL_RETENTION_EVERY` | EVAL | 1000 (ON after SR0) | 1000 at `TOK_RETOK_EVERY` 3000 (333 if k1000 ships): a third of the shortest stamp interval (**[OWNER] O11**) | 04-6.2, C03 |")
r("| Settle / recovery window W | Gate | — | 2 probe readings | NEW-04 |",
  "| Settle / recovery window W | Gate | — | 2 probe readings | NEW-04 |\n| Gate alarm thresholds (KL to anchor, negative-flip rate); canary trip | Gate | — | Calibrated on nuisance pairs inside the 5% family-wise rate; stability-gap depth reported only | NEW-04; provisional until §8 4.1 |")
r("| `CKPT_DIR` / `CKPT_EVERY` | CKPT | '' / 0 | Required / the probe cadence | FRAME (3) |",
  "| `CKPT_DIR` / `CKPT_EVERY` | CKPT | '' / 0 | Required / 1000 (333 if k1000 ships), the probe cadence | FRAME (3) |")
r("| `CKPT_BEST_KEEP` | CKPT | 0 | ≥ 2 | NEW-04 |", "| `CKPT_BEST_KEEP` | CKPT | 0 | 2 | NEW-04 |")
r("| `MEM_MEDIA` | MEM | OFF | OFF | 03-16.8 |",
  "| `MEM_MEDIA` | MEM | OFF | OFF | 03-16.8 |\n| Faded-area expert cull and merge deferral | FAB | OFF (an E2 arm) | ON until `FAB.contribution` works | C37, 02-R11 |")

# ---- Appendix C
r("- `docs/04_CONTRACT.md`: Q-CLOCK-1 (line 1683), Q-CAP-1 (1748), Q-DATA-7 (1938), Q-OPT-3 (2324),\n  Q-FAB-5 (2554), the L1 rule (2557),",
  "- `docs/04_CONTRACT.md`: Q-CLOCK-1 (line 1683), Q-CAP-1 (1748), Q-DATA-7 (1938), Q-OPT-3 (2324),\n  Q-FAB-5 (2554), the L1 rule as applied (2557; defined at `.rework/PLAN.md:155`),")
r("**Code** (lines as cited in the text): `src/opt/api.py` (468-473, 540-561, 642-672, 2864-2872),\n`src/opt/levers.py` (446-448, 474, 605-630, 677-685, 791), `src/fabric/api.py` (3584, 4290,\n4348-4357), `src/fabric/levers.py` (930-961), `src/memory/levers.py` (294-297), `src/memory/api.py`\n(1967-1979), `src/domains/levers.py` (543-600), `src/data/api.py` (150-152, 734, 1728-1737),\n`src/capacity/api.py` (1480), `src/eval/levers.py` (146-148), `src/spine/compose.py` (1634, 1655-1830,\n2726-2748, 3238-3300), `src/spine/loop.py` (1233, 1248-1254, 2261), `src/tok/levers.py` (280-290),\n`gpu_world.sh` (53-60, 73-79, 438, 458-464).",
  "**Code** (lines as cited in the text): `src/opt/api.py` (468-473, 540-561, 642-672, 2864-2872),\n`src/opt/levers.py` (446-448, 474, 605-630, 677-685, 791), `src/fabric/api.py` (1699-1701,\n3339-3370, 3584, 4290, 4310-4311, 4348-4357, 4619), `src/fabric/levers.py` (686-713, 930-961),\n`src/lm/api.py` (908-915), `src/ckpt/levers.py` (256-262), `src/memory/levers.py` (294-297),\n`src/memory/api.py` (1967-1979), `src/domains/levers.py` (543-600), `src/data/api.py` (150-152, 734,\n1728-1737; 733 at `7e902ba`), `src/capacity/api.py` (1480), `src/eval/levers.py` (146-148),\n`src/spine/compose.py` (1634, 1655-1830, 1663-1675, 1808-1818, 2299-2330, 2726-2748, 3238-3300),\n`src/spine/loop.py` (448-450, 1233, 1248-1254, 2261), `src/tok/levers.py` (280-290), `gpu_world.sh`\n(53-60, 67-79, 144, 438, 458-464; 346 at `d97779d`).")
r("| `verify/emp/phase_cross.py`, `lr.py`, `k1000_1300.log` | Phase crossing and per-seed streams at HEAD and `d97779d`; continuation LR by length ratio; the first act's bytes per window |",
  "| `verify/emp/phase_cross.py`, `lr.py`, `k1000_1300.log` | Phase crossing at HEAD and `d97779d` (seed 0); continuation LR by length ratio; the first act's bytes per window |\n| `verify/emp2/actsim.py`, `phasepos.py`, `seedvar.py` (`.out`), `lrcont.py`; `verify/numbers/lr_check.py` | Bytes read and phase reached at HEAD's k3000 (model-free act replay) and frozen; per-seed stream hashes at HEAD and `d97779d`; continuation LR for finished and stopped parents; the horizon off-arm with warmup |")

bad = []
for old, new in R:
    n = s.count(old)
    if n != 1:
        bad.append((n, old[:90]))
        continue
    s = s.replace(old, new)
if bad:
    for n, o in bad:
        print("MATCH", n, repr(o))
    sys.exit(1)
open(P, "w", encoding="utf-8").write(s)
print("applied", len(R))
