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
