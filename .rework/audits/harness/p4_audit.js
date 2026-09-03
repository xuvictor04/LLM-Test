export const meta = {
  name: 'p4-audit-round2',
  description: 'Triage round-1 findings against the fixed tree, review the H58 lever, hunt what is new',
  phases: [
    { title: 'Triage', detail: 'two agents split the 66 round-1 findings' },
    { title: 'Hunt', detail: 'four lenses over the current code, H58 among them' },
    { title: 'Verify', detail: 'two skeptics per finding' },
    { title: 'Sweep', detail: 'completeness critic' },
  ],
}

// EVERY AGENT IS PINNED TO sonnet, and the reason is measured rather than a preference. Four runs
// of this audit lost ~50 agents to API 529 Overloaded while inheriting the session model; a single
// probe agent on sonnet returned in five seconds. The constraint is that model's capacity, not the
// provider. Reverting the pin means re-testing that.
const REPO = '/home/user/LLM-Test'
const SCRATCH = '/tmp/claude-0/-home-user-LLM-Test/e880caf7-1208-58de-93fd-49c41549bf70/scratchpad'
const ROUND1 = '.rework/audits/p4_round1_findings.json'
const OUT = '.rework/audits'

const CONTEXT = `
Repository at ${REPO}. Read with Read/Grep/Glob. RUN things: \`cd ${REPO} && python3 ...\` (torch
installed, CPU only). Put throwaway scripts under ${SCRATCH}/ — never in the repo.

WHAT THIS IS. An ML research system being rebuilt around a "lever spine". Phase P4 is writing BODIES
for entry points that were stubs. Round 1 of this audit filed 66 findings; MANY HAVE SINCE BEEN
FIXED. Round 1 is on disk at ${ROUND1} — a JSON list with file/line/symbol/title/failure/evidence/
severity/fix. READ THAT FILE; it will not be pasted for you.

THE SPEC IS THE DOCSTRING. Every entry point in src/*/api.py carries a long docstring that is the
FROZEN CONTRACT: what it returns, what it refuses, which levers it reads, which historical defect it
exists to prevent. A body that does something other than its own docstring says is a defect even if
the code is reasonable.

RULES THE NEW CODE MUST OBEY:
 - Configs are FROZEN. A package reads only its own levers via cfg.owned_by("PREFIX"); other
   packages' values arrive as \`d_\`-prefixed wires or explicit arguments.
 - RNG: spine/rng.py hands out ONE named stream per subsystem and RAISES if a name is re-issued for
   one seed unless again=True. RUN.streams mints every name in compose.RNG_SUBSYSTEMS at step 0, so
   a package asking for one of those names again is a two-call-sites-one-sequence collision. The
   established repair is a CHILD stream ("data.synth.<label>", "tok.dropout.mint", "lm.init") with
   the parent left declared reporting zero draws. THREE instances have been found and fixed already;
   look for a fourth.
 - Clock kinds in spine/units.py: Windows, Flushes, Backwards, Steps, Epochs, Selections. Crossing
   kinds raises. Steps is reserved for the LR horizon and nothing else.
 - DID IT FIRE: every gated mechanism reports fired / armed-but-0 / UNREACHABLE as THREE
   distinguishable states (spine/gate.py). Collapsing the last two is this codebase's most repeated
   defect.
 - A refusal NAMES the lever and prints both numbers. Silent clamping (\`max(1, x)\`) is forbidden —
   it makes the banner print a number the run did not use.
 - Determinism is measured: two runs at one seed must agree, and randomness must not reach the data
   stream through a side channel.

NOTE ON BUILDING CONFIGS: the assembly LATCHES after one build, so use a FRESH PROCESS per
configuration, or call \`lever._reopen_assembly()\` before each \`assemble.build(...)\`:
  import sys; sys.path.insert(0,'src')
  from spine import assemble, lever, rng
  lever._reopen_assembly(); rng.reset_issued()
  cfg,_,_ = assemble.build(environ={"DATA_AREAS":"eng"})

BE CONCRETE. A finding names a file, a line, and a CONCRETE FAILURE: inputs or config producing a
wrong number, a crash, a silently-wrong measurement, or a mechanism that cannot fire. Style
preferences are not findings. Do NOT report entry points that are still stubs (P4 is incomplete by
design), and nothing in tests/, docs/ or .rework/.

WRITE YOUR RESULT TO DISK BEFORE YOU RETURN IT. Your last action must be to write your findings as
JSON to the path named in your task, using Write. A previous run of this audit lost all thirteen
agents to a transient API overload and nothing survived; a file on disk survives that.
`

const FINDING = {
  type: 'object', additionalProperties: false,
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        properties: {
          file: { type: 'string' }, line: { type: 'integer' }, symbol: { type: 'string' },
          title: { type: 'string' }, failure: { type: 'string' }, evidence: { type: 'string' },
          severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
          fix: { type: 'string' },
        },
        required: ['file', 'line', 'symbol', 'title', 'failure', 'evidence', 'severity', 'fix'],
      },
    },
  },
  required: ['findings'],
}

const VERDICT = {
  type: 'object', additionalProperties: false,
  properties: { refuted: { type: 'boolean' }, reason: { type: 'string' }, correction: { type: 'string' } },
  required: ['refuted', 'reason', 'correction'],
}

const TRIAGE = {
  type: 'object', additionalProperties: false,
  properties: {
    verdicts: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        properties: {
          title: { type: 'string' },
          state: { type: 'string', enum: ['fixed', 'still-present', 'never-real', 'partly-fixed'] },
          evidence: { type: 'string' }, residue: { type: 'string' },
        },
        required: ['title', 'state', 'evidence', 'residue'],
      },
    },
  },
  required: ['verdicts'],
}

// ------------------------------------------------------------------ triage
phase('Triage')
log('Triaging the 66 round-1 findings against the repaired tree')

const HALVES = [
  { key: 'a', files: 'src/data/api.py, src/world/api.py, src/ckpt/api.py, src/train/api.py, src/spine/gate.py', out: `${OUT}/r2_triage_a.json` },
  { key: 'b', files: 'src/tok/api.py, src/lm/api.py, src/sig/api.py, src/fabric/api.py', out: `${OUT}/r2_triage_b.json` },
]

const triaged = await parallel(HALVES.map(h => () =>
  agent(`${CONTEXT}

TRIAGE. Read ${ROUND1} and take EVERY finding whose \`file\` is one of: ${h.files}.

For each, decide its state AGAINST THE CURRENT TREE and prove it:
  fixed         — gone. Say what the code does now and how you checked.
  still-present — still there. Re-confirm by RUNNING something where you can.
  partly-fixed  — the repair covered some paths and not others. THIS IS THE MOST IMPORTANT
                  CATEGORY: three bugs here were "fixed" on one branch and left live on another.
                  Name exactly which path is still broken.
  never-real    — round 1 was wrong. Say why, quoting the code or the contract.

Do not take round 1's word for anything; go to the code. Where a claim is testable, test it.

Copy each \`title\` VERBATIM so verdicts can be matched up. Write the JSON to ${h.out} before
returning.`,
    { label: `triage:${h.key}`, phase: 'Triage', schema: TRIAGE, model: 'sonnet' })))

const verdicts = triaged.filter(Boolean).flatMap(t => t.verdicts || [])
const live = verdicts.filter(v => v.state === 'still-present' || v.state === 'partly-fixed')
log(`triage: ${verdicts.length} judged, ${live.length} still live or partly fixed`)

// ------------------------------------------------------------------ hunt
const LENSES = [
  {
    key: 'h58-lever', out: `${OUT}/r2_hunt_h58.json`,
    prompt: `LENS: REVIEW THE H58 CHANGE ON ITS OWN TERMS — a dedicated review the owner asked for.

WHAT WAS DONE. ISSUES P1-H58 recorded that DATA's exposure gates tested the SCHEDULED per-area split
while draw_stream picked an area uniformly at random per segment, so the run trained on a draw from
that distribution — worst per-area deviation 47.9% over eight seeds. The owner ruled: "We can make
H58 a lever, and make planned default." The change added lever DATA_DRAW, choices
("planned","uniform"), default "planned"; implemented the planned law in DATA.draw_stream; made the
exposure gates law-aware; extended spine/gate.py's Gate.line to print a reason on every arm; added a
census amendment row; rewrote the P1-H58 entry; and recorded decision D8.

READ: src/data/levers.py (the \`draw\` declaration and its comment), src/data/api.py (data_plan's
gate block and draw_stream's allocation loop), src/spine/gate.py, .rework/census.json (the
\`amendments\` family), .rework/ISSUES.md's P1-H58, .rework/DECISIONS.md's D8. Then
\`cd ${REPO} && git show d8eadd5\` for the whole diff.

AUDIT IT HARD:
 1. Does the planned law ACTUALLY make realized equal planned? Verify over many seeds AND many
    configurations — different DATA_AREAS counts, DATA_PHASE_SCHED values, DATA_STREAM_BYTES,
    DATA_SEG_MIN/MAX, DATA_PHASES, single-area runs, more phases than areas, seg_contig on.
 2. Does len(Stream.bytes) == DATA_STREAM_BYTES still hold EXACTLY under every one of those?
 3. The per-phase budget is computed TWICE, in data_plan (per_area_draw) and in draw_stream
    (budget). Find a configuration where the two rules disagree — try remainders, a phase whose
    span is smaller than its live-area count, an area appearing in several phases, a phase whose
    live list has repeats, and non-integer divisions.
 4. draw_stream's "avail is empty" fallback resets avail to the whole live list and assigns the
    remainder to avail[0]. Is it reachable? What does it do to the realized split? Can it overshoot
    a phase bound or stream_bytes?
 5. Does DATA_DRAW=uniform reproduce the OLD behaviour EXACTLY? It is the arm that reproduces every
    recorded result, so any behaviour change there silently breaks comparability. Compare against
    \`git show d8eadd5^:src/data/api.py\`.
 6. Is the lever declared correctly — unit, choices, default — and does the census amendment satisfy
    tests/test_census.py's N2? Run the census checks.
 7. Does the Gate.line change alter any EXISTING gate's printed output, and does anything consume
    the old format?
 8. Are the ISSUES/DECISIONS entries accurate about what was done, and are their numbers (0.00% and
    47.93%) reproducible? Reproduce them.
Report every defect AND every overstatement. Write JSON to the path in this task before returning.`,
  },
  {
    key: 'new-fixes', out: `${OUT}/r2_hunt_fixes.json`,
    prompt: `LENS: AUDIT THE REPAIRS THEMSELVES. A repair is new code and gets no benefit of the doubt.

Run \`cd ${REPO} && git log --oneline -10\` and read the diffs after round 1 — especially b95c4a4
("The experts could never train"), d8eadd5 (H58) and a79d205.

Audit each repair:
 - Population.A/B became nn.Parameter; Population.parameters() was added. Does an optimizer actually
   reach them? Is \`cent\` correctly NOT a parameter? Does parameters() double-count anything
   (it returns [A, B] + modules.parameters())? Is the preallocation claim still true — does anything
   mint a parameter mid-run?
 - Generators moved to torch.Generator(device=device) in FAB/LM/SIG. Does the SEQUENCE drawn change
   (it must not silently move every recorded initialisation)? Are all module allocations on-device?
 - spine/init.py's is_scale, now shared by LM and FAB. Enumerate EVERY parameter name torch produces
   for the modules those two build and check is_scale's verdict on each. Find one it gets wrong.
 - The fabric gates were un-inverted. Check every combination of FAB_ON and occupancy against the
   contract's three states.
 - lm.init as a child stream. Does anything still ask for "lm"? Does rng.issued() read correctly?
   Did the initialisation VALUES change, and is that recorded anywhere?
 - TOK: the resume branch mints tok.dropout.mint and closes the fixed ceiling; _replay_merges
   refuses rather than renumbers; bytes_per_token is measured WITH dropout. Test each. Does the
   refusal fire on a legitimate parent file? Is the "entries"-vs-"id2bytes" handling right, and does
   ANYTHING in the tree actually write either format?
Write JSON to the path in this task before returning.`,
  },
  {
    key: 'pipeline+edge', out: `${OUT}/r2_hunt_pipeline.json`,
    prompt: `LENS: THE DATA/TOKENIZER PIPELINE, AND THE CONFIGURATION SPACE.

Part 1 — src/data/api.py and src/tok/api.py: off-by-one and boundary errors; per-byte labels
drifting out of step with their bytes; a token label taken from the wrong byte; holdout text
reachable by a sampling rule; the seg_contig cursor's persistence across epochs; phase bounds
drifting; the greedy matcher failing to round-trip, looping, or degrading badly; the dropout path
changing behaviour where it must not (held-out text, the final segmentation) or failing to where it
must; a cap checked in one place and re-derived in another. Property-test over many random configs.

Part 2 — RUN these configurations through the real code, fresh process or _reopen_assembly each
time, and report every one that crashes, hangs, or produces something meaningless, with the
traceback or the wrong value: single area (DATA_AREAS=eng); more phases than areas; DATA_SEG_MIN >
DATA_SEG_MAX; DATA_SEG_CONTIG=1; DATA_DRAW=uniform; DATA_SOURCE=real with a missing dir;
DATA_HOLDOUT_FRAC 0 and 0.9; DATA_STREAM_BYTES below one segment; TOK_MODE bytes/fixed/online;
TOK_MIN_PAIR huge and 1; TOK_SEED_VOCAB above the ceiling; TOK_DROPOUT>0; TOK_MAX_BYTES=1;
LM_COMPOSE=1; LM_ARCH=transformer with LM_LAYERS=1; LM_MASK_DEAD_ROWS=1; SIG_MODE=bigram;
SIG_SPACE=tokens; FAB_ON=0; FAB_N0>FAB_SLOTS; WORLD_ENABLED=0; MEM_OWNERS=1; CAP_TARGETS=both;
RUN_EPOCHS=3 with DATA_RESAMPLE=1; RUN_AMP=bf16.
Write JSON to the path in this task before returning.`,
  },
  {
    key: 'contract+goals', out: `${OUT}/r2_hunt_contract.json`,
    prompt: `LENS: CONTRACT FIDELITY, AND THE TWO GOALS.

Part 1 — enumerate every implemented (non-stub) entry point in src/*/api.py BY AST, do not guess,
and for each read its full docstring then its body and list every disagreement. Focus on: a
documented REFUSAL the body does not perform or performs on a different condition; a documented
RETURN field missing, misnamed or constant; a "LEVERS READ:" list that does not match what the body
reads, IN EITHER DIRECTION; a "DID IT FIRE:" surface the body never produces; documented behaviour on
a non-default arm the body gets wrong or silently skips.

Part 2 — the two definitive goals are (A) good language production, with room for other modalities
later, and (B) continual learning WITHOUT catastrophic forgetting. Read docs/04_CONTRACT.md's DATA,
LM, TOK, FAB, SIG, MEM and DOM sections and .rework/PLAN.md. Then find things in the new bodies that
would make a goal-A or goal-B MEASUREMENT wrong rather than crash: a quantity measured on the
training stream that should be held-out or vice versa; two runs differing in one knob made
incomparable; a per-area score attributable to the wrong area; the across-the-run-boundary
comparison reading two different texts; a "0" indistinguishable from "never ran"; a row counted live
when it is not; the loss computed over a different support than it is reported against; the model
seeing its own future; train/eval inconsistency in a memory key or a routing input. Quantify by
running the code.
Write JSON to the path in this task before returning.`,
  },
]

phase('Hunt')
log(`Hunting across ${LENSES.length} lenses, H58 among them`)

const hunted = await pipeline(
  LENSES,
  lens => agent(`${CONTEXT}\n\n${lens.prompt}\n\nYOUR OUTPUT FILE: ${lens.out}\n\nRound 1's findings are at ${ROUND1}; do not re-file one already there unless you can show it is STILL live after the repairs.`,
    { label: `hunt:${lens.key}`, phase: 'Hunt', schema: FINDING, model: 'sonnet' }),
  (found, lens) => {
    const items = (found && found.findings) || []
    if (!items.length) return []
    return parallel(items.map(f => () =>
      parallel(['correctness', 'reproduce-it'].map(angle => () =>
        agent(`${CONTEXT}

A reviewer on the "${lens.key}" lens filed this. YOUR JOB IS TO REFUTE IT.

  file:     ${f.file}:${f.line}  (${f.symbol})
  claim:    ${f.title}
  failure:  ${f.failure}
  evidence: ${f.evidence}
  proposed: ${f.fix}

Attack from the "${angle}" angle:
 - correctness: is the code actually wrong? Read it again. Does another line already handle this? Is
   the reviewer misreading control flow, an operator, or a torch semantic? AND: does the DOCSTRING
   actually require what the reviewer says? Quote it. A body that differs from what the reviewer
   WANTED but matches what the contract SAYS is not a defect. Is it deliberate and explained in a
   comment right there?
 - reproduce-it: WRITE AND RUN a script that triggers the claimed failure, from ${REPO}, scripts
   under ${SCRATCH}/. If you cannot make it happen, it is refuted. If you can, quote the output.

Default to refuted=true when uncertain. A finding that survives is one you tried hard to kill. You
do not need to write a file.`,
          { label: `verify:${lens.key}:${angle}`, phase: 'Verify', schema: VERDICT, model: 'sonnet' })))
        .then(vs => {
          const real = vs.filter(Boolean)
          const kills = real.filter(v => v.refuted).length
          return { ...f, lens: lens.key, survived: real.length > 0 && kills === 0,
                   votes: real.map(v => ({ refuted: v.refuted, reason: v.reason, correction: v.correction })) }
        })))
  },
)

const all = hunted.filter(Boolean).flat().filter(Boolean)
const confirmed = all.filter(f => f.survived)
log(`${all.length} new findings filed, ${confirmed.length} survived verification`)

// ------------------------------------------------------------------ sweep
phase('Sweep')
const critic = await agent(`${CONTEXT}

Round 1 filed 66 findings (${ROUND1}); they have been triaged against the repaired tree, and four
lenses hunted the current code. ${confirmed.length} new findings survived verification:

${confirmed.map(f => `- [${f.severity}] ${f.file}:${f.line} ${f.symbol} — ${f.title}`).join('\n') || '(none)'}

Still live or partly fixed from round 1:
${live.map(v => `- [${v.state}] ${v.title}${v.residue ? ` — residue: ${v.residue}` : ''}`).join('\n') || '(none)'}

FIND WHAT THEY ALL MISSED.
 - Which implemented entry points has NOBODY examined across both rounds? Enumerate non-stub entry
   points by AST, subtract those named in any finding, and read what is left.
 - Is there a defect that appears only when TWO new bodies interact — a value produced by one and
   consumed by another under a different assumption about units, ownership, ordering or lifetime?
   Trace the hand-off sequence in src/spine/compose.py::compose and check each argument.
 - THE STREAM-COLLISION FAMILY has bitten three times (data.synth, tok.dropout, lm). Enumerate EVERY
   rng_for call in src/ against compose.RNG_SUBSYSTEMS and prove there is no fourth.
 - Does the end-to-end path still work? Run it: open_areas -> build_vocabulary -> data_plan ->
   draw_stream -> tokenize -> resolve -> build_model -> encode -> decode, compute a loss, take 30
   optimizer steps WITH the fabric's parameters in the optimizer, and confirm the loss falls and the
   expert tensors actually move. Report anything odd.
Report only NEW defects, same concreteness bar. Write JSON to ${OUT}/r2_sweep.json before returning.`,
  { label: 'sweep:completeness', phase: 'Sweep', schema: FINDING, model: 'sonnet' })

const extra = ((critic && critic.findings) || []).map(f => ({ ...f, lens: 'sweep', survived: true, votes: [] }))
log(`completeness critic added ${extra.length}`)

return {
  round1: {
    judged: verdicts.length,
    fixed: verdicts.filter(v => v.state === 'fixed').length,
    neverReal: verdicts.filter(v => v.state === 'never-real').length,
    stillLive: live.map(v => ({ state: v.state, title: v.title, residue: v.residue, evidence: v.evidence })),
  },
  newConfirmed: [...confirmed, ...extra],
  newRefuted: all.filter(f => !f.survived).map(f => ({ file: f.file, symbol: f.symbol,
    title: f.title, why: f.votes.filter(v => v.refuted).map(v => v.reason).join(' | ') })),
  counts: { newFiled: all.length, newConfirmed: confirmed.length, fromSweep: extra.length },
  onDisk: `${OUT}/ — per-agent JSON survives even if aggregation fails`,
}
