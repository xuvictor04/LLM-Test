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
