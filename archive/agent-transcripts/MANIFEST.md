# Agent transcripts — the raw record behind every multi-agent phase

Committed for records. These are PROCESS, not product: the conclusions they produced live in
`.rework/` (survey, census, issues, decisions) and in `src/`, `tests/` and `docs/`. Nothing here is
documentation and nothing here has been verified — an agent transcript is one model's working, and
this project's standing rule is that agent output is a lead until checked against the source.

Kept because it is otherwise unrecoverable: the container is ephemeral and re-provisioned, and these
files exist nowhere else.

Each `wf_*.tar.gz` holds one workflow run: a `journal.jsonl` (one line per completed agent, with its
full structured return value) plus one `agent-*.jsonl` per subagent (its complete reasoning and tool
use). `loose-agents.tar.gz` holds the non-workflow subagents from earlier in the session.

Extract with: `tar xzf archive/agent-transcripts/<name>.tar.gz`

## Runs

| archive | run | agents | what it produced |
|---|---|---:|---|
| `wf_9efbeae8-0fa.tar.gz` | — | 70 | **the survey** — 16 readers over the whole repo, docs, archive and both spans of chat history, then 4 architectures, 3 judges and a completeness critic. Produced `.rework/survey/`, and the design that became `.rework/PLAN.md`. |
| `wf_3ae4e940-e74.tar.gz` | — | 42 | **P1 spine + P2 census** — derive/wire/rng/assemble, the ownership and determinism tests, the 328-knob census across 12 families, and 3 adversarial reviews that found 5 critical defects in the spine. |
| `wf_9cf6a755-271.tar.gz` | — | 9 | **P3 contract** — five agents read disjoint slices of the old 12,381-line mechanism, a sixth reconciled them into 117 frozen entry points, `spine/compose.py`, `docs/04_CONTRACT.md` and `tests/test_contract.py`. Two adversarial reviewers then returned critical findings: the `spine.compose` re-export that reopened O10's route 1, and the `LeverSet.__subclasses__()` walk no AST rule can reach. Its first launch died instantly — the output schema was too large for the safety classifier — and was resumed with flat markdown fields. |
| `wf_e1858e9b-148.tar.gz` | — | 6 | **P3 order repair** — three agents read the old loop, the checkpoint and resume paths, and the four dropped mechanisms; one rebuilt ASSEMBLY_ORDER (22→38) and LOOP_ORDER (24→63) with three new stage kinds; two reviewers found the `lm.depth` latent crash, the K6 prose-credit hole, and the pin-clock contradiction between two frozen surfaces. |
| `wf_ab6c7e95-6d9.tar.gz` | — | 21 | **P2 packages** — the nine remaining lever packages (capacity, ckpt, data, eval, lm, opt, tok, train, world) written against the census, the coupling table corrected by contact with them (three rows named owners nobody had), and 3 adversarial reviews. Its script was not persisted under `workflows/scripts/`; the review that followed produced the O10 import boundary and caught the untrippable O4 patch. |
| `wf_96172f4a-bf8.tar.gz` | — | 70 | earlier session work |
| `wf_2f07991a-311.tar.gz` | — | 36 | earlier session work |
| `wf_cf66ea09-ce5.tar.gz` | — | 24 | earlier session work |
| `wf_b0cb9ed3-6eb.tar.gz` | — | 20 | earlier session work |
| `wf_3b649965-67f.tar.gz` | — | 18 | earlier session work |
| `wf_6770daeb-fb6.tar.gz` | — | 34 | earlier session work |
| `wf_8f1688ac-4f4.tar.gz` | — | 20 | earlier session work |
| `wf_7a73aa38-e44.tar.gz` | — | 12 | earlier session work |
| `wf_2d772b2a-99f.tar.gz` | — | 4 | earlier session work |
| `loose-agents.tar.gz` | (non-workflow subagents) | — | Agent-tool subagents spawned outside a workflow, earlier in the session. |

**15 archives, 70 MB compressed, from 195 MB / 686 files uncompressed.**

## What is NOT here

- The main session transcript. It lives outside the repo and its only durable trace is the four
  compaction summaries preserved verbatim in `.rework/COMPACTION_SUMMARIES.md`.
- Tool results (`tool-results/`, 3.8 MB) — these are inputs the agents read, not their reasoning,
  and every one is reproducible from the repository itself.
