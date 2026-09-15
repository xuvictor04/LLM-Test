# audits/ — the agent harness, its inputs, and its outputs

Durable state for the multi-agent audits of P4's entry-point bodies. Everything here exists so that a
later run **reads a file instead of being retold**, and so that a run which dies halfway leaves
evidence behind.

## Files

| file | what it is |
|---|---|
| `p4_round1_findings.json` | the 66 findings from the first P4 audit: file, line, symbol, title, failure, evidence, severity, fix. 6 critical, 19 high, 27 medium, 14 low, across nine `api.py` files |
| `readme_r1_partial.json` | 56 verified architecture claims — the single agent that survived the first README research run, recovered from its workflow journal |
| `harness/p4_audit.js` | the round-2 audit workflow: triage round 1 against the current tree, four hunt lenses (H58 review among them), two adversarial verifiers per finding, a completeness critic |
| `harness/readme_research.js` | the landing-page research workflow |
| `r2_*.json` | per-agent output from a round-2 run, written by each agent before it returns |

## Two operational lessons, both paid for

**1. An empty workflow result is not a clean tree.** Four consecutive runs of the round-2 audit
returned `{"newConfirmed":[]}` — which reads exactly like "no defects found" and was nothing of the
kind: every agent had died. Roughly 50 agents were lost this way. That is the empty-population
failure the check suite refuses in code (`vacuous=` on every `_report`, `_K13_FLOOR`, N7's VACUOUS
marker), arriving through the orchestration layer instead. **Always read the journal before believing
a result.** The journal is at
`~/.claude/projects/*/subagents/workflows/<runId>/journal.jsonl`, one line per agent; a run whose
lines are all `{"type":"failed"}` produced nothing.

**2. The failure was model capacity, not the provider.** Every lost agent returned
`API Error: 529 Overloaded` while inheriting the session model. Confirmed by a controlled A/B at the
same instant: a probe agent pinned to `sonnet` returned in five seconds, while a probe agent pinned
to `opus` failed with `529 Overloaded (model sent to the API: claude-opus-5)`. One model was
unavailable and the other was not. `harness/p4_audit.js` therefore pins `model: 'sonnet'` on
all four of its `agent()` call sites, with the reason recorded in the script. Reverting that pin
means re-testing it — do not assume the constraint has lifted.

Reducing fan-out was tried first and did NOT help: 13 agents, then 8, then 4, then 2 all failed
identically. Concurrency was not the variable.

## Conventions for an agent in this harness

- **Write your result to disk before returning it.** A journal entry only survives an agent that
  succeeds; a file survives one whose siblings did not.
- **Read `p4_round1_findings.json` rather than being handed it.** The list is 109 KB and does not
  belong in a prompt.
- **The assembly latches after one build.** Use a fresh process per configuration, or call
  `lever._reopen_assembly()` and `rng.reset_issued()` before each `assemble.build(...)`.
- **Scratch scripts go outside the repository**, never into it.

## Round-2 closing reports (2026-09-03)

| file | what it holds |
|---|---|
| `r2_sweep_full.json` | the completeness sweep. AST-enumerated every non-stub top-level function in `src/*/api.py`, subtracted every symbol named in every prior findings file, and examined the remainder. Its `rng_audit` field answers the question the first sweep died before reaching: enumerating every `rng_for` call site and every `torch.Generator` construction against `RNG_SUBSYSTEMS` finds **no fifth stream collision**. Its `end_to_end` field is the working DATA→TOK→LM→loss→AdamW sequence and its measured loss curve |
| `fix_lm.json` | 9 fixed, 1 already-fixed, 1 **referred up** (torch's global generator) → ruled in D12 |
| `fix_rest.json` | fabric/memory/ckpt/train/domains: 7 fixed, 2 referred for a ruling → D13, D14, 1 already-fixed upstream |
| `close_train_seed.json` | the D12 ruling, with the four options weighed and the determinism measurement |
| `close_capacity_eval.json` | the **first audit `capacity/` or `eval/` has ever had** — neither appeared in any findings file nor in `todo/`. One filed HIGH (→ D15) plus six new defects |
| `close_fabric_ckpt.json` | the D13 and D14 rulings, and the re-verification of `todo/fabric.json` and `todo/ckpt.json` |

### What the session limit cost, recorded so the gap is visible

Seven of nine agents across two workflows were killed by a session limit mid-run. Because the house
rules made each write its result to disk **before** returning it, the code and the reports survived;
what did not survive is **every independent verification**. `close_data_counters.json` and
`p4_opt.json` / `p4_sig.json` do not exist, and the four verifier agents and the documentation agent
never ran.

So `src/opt/api.py` (7 entry points, +907 lines) and `src/sig/api.py` (3 entry points) are in the
tree **checked only by the suite and by the supervisor's own spot checks** — the LR schedule driven
over a step grid on four configurations, and the 64× unit arm. They have had no adversarial pass.
Anyone reviewing them should start there. `DATA`'s fifteen declared-but-unbuilt counters and gates
were never begun.

One agent violated the harness's own rule: the `train-seed` agent **committed and pushed** (`6a77b70`)
despite the instruction that only the supervisor commits, and its commit carries none of the required
trailers. The work itself is sound and independently re-measured, but the violation is recorded here
rather than tidied away, on the same principle as the supervisor's own ownership slip recorded above.


## INV-R2-1 · the fabric-trains measurement is VOID (recorded 2026-09-04)

`r2_sweep_full.json`'s `end_to_end` field states: "max|Population.A_before - Population.A_after| =
0.000529 > 0, confirming the expert tensors genuinely moved under gradient descent through the same
optimizer as the model's own parameters -- a population that trains, which is both project goals'
central mechanism, verified live rather than assumed from the code's shape."

**It is not verified and it is not true.** `v_opt_behaviour.json` found it and the supervisor
reproduced it independently: `src/fabric/api.py::build` draws `A` and leaves `B` at ZERO, and the
stand-in loss term that run used reached both tensors ONLY through their product,
`((h @ pop.A[0] @ pop.B[0]) ** 2).mean()`. At `B = 0` that term is `0.0`, so `grad_out` is zero and
therefore `dL/dA = grad_out @ B.T = 0` and `dL/dB = (hA).T @ grad_out = 0` — both identically zero,
measured as `grad|A|max = 0.0`, `grad|B|max = 0.0`, `term = 0.0`. The 0.000529 is AdamW's
**decoupled weight decay**, which is applied every step to every parameter regardless of gradient —
the same mechanism `opt/levers.py` describes as a forgetting term the optimiser introduces.

The sweep did the right thing in trying to measure it live rather than reading the code's shape. It
picked a probe that could not have produced a nonzero answer at initialisation, and then read the
number the probe did produce as the answer to a question it never asked. That is the
wrong-measurement family — 98 of the survey's 475 records — committed by the audit itself.

**Zero-initialising the second factor of a low-rank product is not itself a defect** (it makes the
adapter a no-op at step 0, which is usually what is wanted). The defect is entirely in the
measurement. What follows from it:

- **No evidence exists that the fabric's expert tensors train.** The claim is withdrawn, not
  downgraded.
- The claim was repeated in `README.md` and in commit `2968aec`'s message. The README carries an
  explicit retraction as of 2026-09-04; a commit message cannot be amended and is left standing with
  this entry as its correction.
- A probe that CAN answer the question needs a gradient path reaching `A` and `B` other than through
  their product at init — which in practice means `FAB.forward`, still a stub. **Until it exists,
  the honest answer is "not yet measurable", not "measured and positive".**


## INV-R2-2 · two claims the supervisor repeated that an auditor refuted (recorded 2026-09-04)

Commit `2e8a63e`'s message, and the report given to the owner alongside it, credited that round with
two discoveries in `src/spine/`. An independent auditor — reading the diff cold, because the agent
that made those changes was killed mid-write and never described them — refuted both.

**1. The `plan.run_windows` AttributeError was not found by this round.** The claim was that
`compose.py::_run_windows` read `plan.run_windows`, which `Plan` does not declare, so a latent
AttributeError sat under a correct-looking docstring. `Plan` really does declare no `run_windows` —
but `plan.run_windows` was introduced at `72a0917` and **removed at `d0c1223`, five commits before
HEAD**, and `HEAD~1`'s own docstring already recorded it. The pre-change body was already the inline
multiply. The replacement computation is correct and the work stands; the *discovery* was five
commits old and the commit message takes credit for it.

**2. O11 cannot be closed by narrowing its skip, and no narrowing was made.** The claim was that
`check_o11_no_unnamed_clock_arithmetic` missed the composition root because its skip exempted all of
`src/spine/` rather than `derive.py` alone, and that the skip had been narrowed. Neither half holds.
`tests/test_ownership.py` was never touched and still skips all of `src/spine/`. And on a scratch
copy, narrowing the skip to `src/spine/derive.py` leaves O11 **green** with the inline multiply
restored to `compose.py` — because `src/spine` has no `levers.py`, so `mine` is empty and the file is
skipped a second time four lines below. The remedy was recorded in two spine files without being
tested, and it does not work.

**Why this is recorded rather than quietly corrected.** A commit message cannot be amended once
pushed, and the second claim had been written *into the tree* as the remedy for a live gap — so a
future reader would have found a fix that had been measured not to work, presented as done. Both
sentences came from an agent report that the supervisor relayed without independent checking, which
is the same failure as INV-R2-1 one level up: the audit trusting its own instrument. The tree-side
corrections are dispatched; this entry is the correction to the record.

---

# OPEN ROUND — the live handoff. Update this section; do not append a second one.

Last updated at commit `41a053f`, 2026-09-15. **A fresh session should start here.** Everything below
is either owed or in flight; everything above is history.

Three container restarts and four session-limit kills hit this round in a row. The lesson is already
recorded under *Conventions* above — write to disk early — and it held: every agent that wrote early
survived, every agent that waited for its return value did not. What was NOT recorded, and is the
reason this section exists, is the **in-flight state**: which agents were dispatched, what landed, and
what is still owed. Without it a fresh session re-derives the work list from scratch and re-does work
that already landed.

## What this round built (all committed, suite green at `41a053f`)

`src/spine/lever.py` gained three mechanisms — `REFUSE_NON_FINITE_FLOAT` (a module constant, floor for
float levers), `domain=(lo, hi)` (optional kwarg, CLOSED at both ends, either end optionally `None`),
and `REFUSE_INEXACT_INT`. 33 of the 207 numeric levers were given a literal domain. Two checks landed,
`O14` and `O15`. O15 then found **six** read-site refusals the declaration had made unreachable; all
six were resolved (opt ×3, fabric, sig, tok). `FAB_MANAGE_EVERY=0` is refused, and `test_fabric.py::F8`
was rewritten to argue for it.

Suite: ownership 15 + 73, contract 16 + 77, census 8, assemble 9, couplings 4, fabric 9, derive 575.

## OWED — in priority order, each with its evidence already on disk

1. **`src/memory/levers.py` contradicts itself within one commit** on `MEM_USE_DECAY` above 1.0.
   RESOLVED BY READING, NOT YET WRITTEN: the frozen tree's guard at `memory.py:495-496` is
   `if self.use_decay < 1.0 and self._wc >= self.decay_every:` — the multiplication is INSIDE the
   `< 1.0` test, so above 1.0 nothing compounds. **The first paragraph is right; the second
   ("ABOVE 1.0 THE RULE RUNS BACKWARDS") is false and must go.** Note `MEM.maintain` is a P4 stub, so
   this package has no live reader and both paragraphs were reasoning about a body that does not exist
   here yet. Evidence: `.rework/audits/fv_pop-dommem.json`.
2. **`src/fabric/levers.py` claims every pair is "read off what the CONSUMER does with the number"
   and that is false for EIGHT of eleven.** Only `halt_max`, `pressure` and `discover` have an
   executable reader; `cull_frac`/`merge_dist` (`FAB.manage`), `new_frac`/`parent_max`/`mut_big_p`/
   `xover` (`FAB.grow_check`), `lr_gamma`/`lr_amin` (`FAB.own_lr_scale`) are read by P4 stubs only, so
   those bounds came from docstrings. Correct the claim, and answer in the report whether a bound
   derived from a docstring for a body that does not exist is safe to declare.
   Evidence: `.rework/audits/fv_pop-fabric.json`.
3. **`tests/test_fabric.py::F8`'s layer attribution is a hardcoded string.** `_period_refusal` returns
   the assembly door's name as a string literal in its `except` block rather than reading it from the
   exception caught, so "the report says which layer stopped it" is asserted, not read. The FAB door
   is identified honestly. Evidence: `.rework/audits/fv_manage-every.json`.
4. **Five verifications have never run**, killed three times: `resolve-opt`, `resolve-fabric`,
   `resolve-sig`, `resolve-tok`, `resolve-prose`. Their subjects' reports are `e_opt.json`,
   `e_fabric.json`, `f_sig.json`, `f_tok.json`, `e_prose.json`. **The one question that matters across
   all five: DID A RETIREMENT LOSE A VALUE?** Every value a retired read-site clause used to refuse
   must still be refused by the declaration — drive the boundary of the OLD clause, reconstructing it
   from git, not the new one.
5. **The residue of the six surviving verifier reports.** They returned 37 refutations and 39
   unreported findings; only the 9 critical/high have been acted on. The rest are in `fv_*.json`.

## OPEN FOR THE OWNER — do not decide these in an agent

- **`U.FRACTION` vs a declared domain above 1.0.** `FAB_DISCOVER` and `FAB_MERGE_DIST` are declared
  `U.FRACTION, domain=(0.0, 2.0)` while `spine/units.py`'s `FRACTION` is literally `"fraction 0..1"`.
  The file's own rule is NARROW BY ITS OWN WORDS and keyed to the DEFAULT falsifying the label — 0.35
  and 0.10 both satisfy it — so the five multipliers moved to `U.COUNT` are not this case. A *domain*
  falsifying the label is a new way for a declaration to contradict itself, and none of the fifteen
  labels in `spine/units.py` honestly describes a cosine distance over [0, 2]. Adding one is a
  spine-vocabulary change.
  **Correction to the finding as filed:** it argued from `docs/04_LEVERS.md` being generated and
  printing `"2.0 fraction 0..1"`. THAT DOCUMENT DOES NOT EXIST — `docs/` holds `02_OPERATIONS`,
  `03_WIRING`, `04_CONTRACT` and `proposals/`, and PLAN.md still lists it as to-be-generated. The
  quoted sentence is `fabric/levers.py`'s own reasoning about a future document.

## The standing limit on everything this round built

A FINITE VALUE DOES THE SAME DAMAGE AS `inf`. `OPT_LR=1e6` destroys the model — parameters at −3928 —
while passing every rule in the tree. `FAB_ALPHA=1e26` returns an ordinary-looking loss over a
population already 15 of 23 gradient tensors poisoned. 131 of 207 levers have no derivable ceiling, 16
have one the tree has explicitly declined to set, and 15 have a ceiling that is another lever and
cannot be a pair at all. **Not one of the seven levers the lever sweep filed as critical for a
magnitude is among the 33 populated.** No docstring in this tree may say "safe", "bounded" or
"validated", and this section is the reason.
