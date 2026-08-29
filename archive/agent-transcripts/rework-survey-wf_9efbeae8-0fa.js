export const meta = {
  name: 'rework-survey',
  description: 'Survey the whole LLM-Test repo, notes, archive and full chat history; then design the reworked architecture',
  phases: [
    { title: 'Survey', detail: 'parallel readers over code regions, docs, archive, tests, and the full chat history' },
    { title: 'Design', detail: 'independent architecture proposals for lever delineation and module layout' },
    { title: 'Judge', detail: 'score the proposals against the stated requirements' },
    { title: 'Synthesize', detail: 'merge into one target architecture + open questions' },
  ],
}

const NORTH = `PROJECT CONTEXT (authoritative, do not contradict):
The repo /home/user/LLM-Test is an autonomous continual-learning ML research system. Its owner has TWO
definitive goals and nothing else is definitive:
  A. good language production, with room for additional modalities to be strapped on later
  B. continual learning without catastrophic forgetting
The architecture is a modular low-rank expert population ("the Fabric") plus an editable memory store,
a self-assembling domain partition, and an online byte-BPE tokenizer that mints tokens during training.
EVERYTHING ELSE -- every measured number, every verdict a run prints -- is a SIGNAL, not a fact. The system
is not optimized, has known bugs, and confounds are likely. Never state a measured result as definitive;
state what was measured, under what configuration, and what could confound it.
The project's core discipline is the "DID IT FIRE" audit: a mechanism that is armed but never runs, a
quantity computed in one unit and consumed in another, data recorded and never read, and a guard nothing
can trip are the recurring bug classes. Look for them.`

const OUT = `RETURN STRUCTURED OUTPUT ONLY. Every claim must carry file:line evidence or a quoted line.
Do not speculate. If you cannot verify something, put it in open_questions instead of asserting it.
Be exhaustive within your assigned scope; it is better to return 60 precise facts than 10 vague ones.`

const SURVEY_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['area', 'summary', 'facts', 'levers', 'bugs', 'junk', 'carry_forward', 'open_questions'],
  properties: {
    area: { type: 'string' },
    summary: { type: 'string', description: 'What this area is and does, 3-8 sentences' },
    facts: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        required: ['claim', 'evidence', 'confidence'],
        properties: {
          claim: { type: 'string' },
          evidence: { type: 'string', description: 'file:line or a quoted line' },
          confidence: { type: 'string', enum: ['verified', 'likely', 'uncertain'] },
        },
      },
    },
    levers: {
      type: 'array',
      description: 'Config knobs / environment variables this area reads. One entry per knob.',
      items: {
        type: 'object', additionalProperties: false,
        required: ['name', 'effect', 'owner', 'couples_with', 'evidence'],
        properties: {
          name: { type: 'string' },
          effect: { type: 'string', description: 'what it changes, mechanically' },
          owner: { type: 'string', description: 'the one module/subsystem that should own it' },
          couples_with: {
            type: 'array',
            description: 'other knobs whose MEANING this one changes, or that gate it. Empty if truly independent.',
            items: { type: 'string' },
          },
          evidence: { type: 'string' },
        },
      },
    },
    bugs: {
      type: 'array',
      description: 'Anything broken, suspicious, inert, or self-contradictory. Include known-and-documented ones.',
      items: {
        type: 'object', additionalProperties: false,
        required: ['title', 'severity', 'where', 'symptom', 'evidence', 'bug_class'],
        properties: {
          title: { type: 'string' },
          severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
          where: { type: 'string' },
          symptom: { type: 'string' },
          evidence: { type: 'string' },
          bug_class: {
            type: 'string',
            enum: ['armed-but-inert', 'unit-mismatch', 'recorded-never-read', 'untrippable-guard',
                   'silent-overwrite', 'coupling', 'wrong-measurement', 'crash', 'other'],
          },
        },
      },
    },
    junk: {
      type: 'array',
      description: 'Dead code, superseded material, duplication, things safe to drop in a clean rebuild.',
      items: {
        type: 'object', additionalProperties: false,
        required: ['what', 'why', 'safe_to_drop'],
        properties: { what: { type: 'string' }, why: { type: 'string' }, safe_to_drop: { type: 'boolean' } },
      },
    },
    carry_forward: {
      type: 'array',
      description: 'Hard-won knowledge that MUST survive a from-scratch rebuild: invariants, gotchas, decisions.',
      items: {
        type: 'object', additionalProperties: false,
        required: ['item', 'why', 'evidence'],
        properties: { item: { type: 'string' }, why: { type: 'string' }, evidence: { type: 'string' } },
      },
    },
    open_questions: { type: 'array', items: { type: 'string' } },
  },
}

const T = '/root/.claude/projects/-home-user-LLM-Test/e880caf7-1208-58de-93fd-49c41549bf70.jsonl'

const CHAT_RECIPE = `The transcript is JSONL, one JSON object per line, 8072 lines total.
Extract readable text for your line range with a command like:
  python3 - <<'PY'
  import json
  LO, HI = <lo>, <hi>
  for i, line in enumerate(open('${T}'), 1):
      if i < LO or i > HI: continue
      try: d = json.loads(line)
      except Exception: continue
      t = d.get('type'); m = d.get('message') or {}
      c = m.get('content')
      parts = []
      if isinstance(c, str): parts = [c]
      elif isinstance(c, list):
          for b in c:
              if not isinstance(b, dict): continue
              if b.get('type') == 'text': parts.append(b['text'])
              elif b.get('type') == 'tool_use': parts.append('[TOOL ' + str(b.get('name')) + '] ' + json.dumps(b.get('input'))[:600])
              elif b.get('type') == 'tool_result':
                  r = b.get('content')
                  parts.append('[RESULT] ' + (r if isinstance(r, str) else json.dumps(r))[:600])
      if parts:
          print('=== L' + str(i) + ' ' + str(t) + ' ' + str(d.get('timestamp')) + ' ===')
          print('\\n'.join(parts)[:4000])
  PY
Adjust the slice sizes if output is too large; work through your range in several passes if needed.
Prioritise USER turns (type == 'user' with a plain text message) -- those are the owner's own words and
every one of them must end up documented. Assistant turns matter for decisions and corrections.`

// ---------------------------------------------------------------- SURVEY
phase('Survey')

const CODE_REGIONS = [
  { key: 'so-config', label: 'self_organize.py 1-1500 (registry, env plumbing, config)',
    prompt: `Read /home/user/LLM-Test/self_organize.py lines 1-1500 IN FULL (use Read with offset/limit in
several calls). This region holds the _SPEC knob registry, the _env/_i/_f accessors, DATA_MODE/corpus
loading, the tokenizer setup, and the phase schedule. Catalogue EVERY knob declared in _SPEC with its
default and its stated owner-subsystem comment. For each, say what it actually does and which other knobs
change its meaning or gate it. Note every place a knob is read with a default that differs from the
registry, every derived-from-another-knob value, and every place one variable serves two purposes.` },
  { key: 'so-fabric', label: 'self_organize.py 1500-3600 (Fabric, router, growth, cull)',
    prompt: `Read /home/user/LLM-Test/self_organize.py lines 1500-3600 IN FULL. This is the Fabric expert
population: preallocated low-rank experts, the grounded router, growth (ramp/regression/stall), the
utilization cull, exploration, crossover/replicate, and the domain assembler (SelfAssembler) with its
merge/cull/fold management. Map the mechanisms, their gates, and their counters. Identify any mechanism
that can be armed but never fire, any guard whose condition cannot be satisfied, and any counter that is
incremented but never read.` },
  { key: 'so-model', label: 'self_organize.py 3600-5600 (model, resume, checkpoint, holdout)',
    prompt: `Read /home/user/LLM-Test/self_organize.py lines 3600-5600 IN FULL. This covers the LM model,
fab_logits, selfcheck, the RESUME path (geometry gate, widening, growth-controller restore, optimizer
moment handling), checkpoint save/load, and holdout_bpb / the across-run-boundary probe. Document exactly
what is and is not carried across a resume, and what each saved field is read back for (or not).` },
  { key: 'so-loop', label: 'self_organize.py 5600-7900 (banner, config audit, training loop)',
    prompt: `Read /home/user/LLM-Test/self_organize.py lines 5600-7900 IN FULL. This covers the config
banner, the COUPLING warnings, the config audit, and the main training loop including batching, ACCUM,
memory writes, the LR schedule and restarts, per-expert learning rates, domain management cadence, and
retokenization. Document every COUPLING the code itself declares -- these are the owner's known
lever-interaction problems and must all be captured.` },
  { key: 'so-report', label: 'self_organize.py 7900-end (the report / instruments)',
    prompt: `Read /home/user/LLM-Test/self_organize.py lines 7900 to the end IN FULL. This is the end-of-run
report: DID IT FIRE, domain genuineness, wrongness, performance, partition informativeness, affiliation,
expert independence, fabric, signature space, specialization, chaining, generation, coherence,
non-stationary, retention, across-the-run-boundary. For EACH section record: what it measures, on WHICH
sample (training stream vs held-out tail vs a probe), and what would confound it. Flag any section whose
verdict is computed from a different quantity than the one it prints.` },
  { key: 'subsys', label: 'memory.py / tokenizer.py / datastream.py / world_model.py',
    prompt: `Read /home/user/LLM-Test/memory.py, tokenizer.py, datastream.py and world_model.py IN FULL.
Document the EditableMemory store (write gate, eviction, per-source floor, probation, wrong flag,
delete/merge), the DynamicTokenizer (minting, vmax, save/load, append-only property), the corpus
streaming, and the world model. Note every invariant the code relies on and every place two callers can
disagree.` },
  { key: 'harness', label: 'longrun.sh / preflight.sh / selftest.sh / other shell',
    prompt: `Read /home/user/LLM-Test/longrun.sh IN FULL (1968 lines) plus preflight.sh, selftest.sh,
harness_test.sh, equiv.sh, bench_gpu.sh, rerun.sh, sweep_domains.sh, sweep_domain_grid.sh, fetch_data.sh,
fetch_40g.sh. Catalogue every subcommand/arm, what environment it sets, and which arms are dead or
superseded. The arm list is large and much of it is historical -- say which arms still have a purpose.` },
  { key: 'tests', label: 'the test suite',
    prompt: `Read every test in /home/user/LLM-Test: selftest.sh, levers.py, notes_check.py, mem_evict_test.py,
compare_test.py, growth_test.py, domain_test.py, proj_test.py, cap_test.py, ramp_test.py, lr_test.py,
blowup_test.py, curve_test.py, tok_test.py, corpus_test.py, resume_test.py, harness_test.sh. For each,
state precisely WHAT INVARIANT it guarantees and what it does NOT cover. Several exec source text from
self_organize.py against stubs -- note every such anchor, because a rebuild will break them.` },
  { key: 'tools', label: 'analysis and utility scripts',
    prompt: `Read /home/user/LLM-Test/compare.py, runs.py, vocab.py, prompt.py, holdout.py, cl_bench.py,
keystone_probe.py, probe_signature.py, probe_stability.py, probe_ckpt_geometry.py, sweep_domain_report.py,
fetch_big.py, fetch_local.py. Say what each is for, whether it is still wired to anything, and which are
superseded.` },
]

const DOC_REGIONS = [
  { key: 'notes-num', label: 'notes/00-10 + CURRENT_DEFAULTS + DOC_PLAN',
    prompt: `Read /home/user/LLM-Test/notes/00_INDEX.md, 01_TIMELINE.md, 02_IDEAS.md, 03_EXPERIMENTS.md,
04_RESULTS.md, 05_ERRORS.md, 06_CONTINUAL_LEARNING.md, 07_WIP.md, 08_GLOSSARY.md, 09_COMMENT_AUDIT.md,
10_HISTORY_FINDINGS.md, CURRENT_DEFAULTS.md and DOC_PLAN.md IN FULL. These are the project's own notes.
For each: what it claims, what is now stale or contradicted, and which specific items are hard-won
knowledge that must survive into regenerated documentation. Extract the TIMELINE entries and the ERRORS
entries especially carefully -- they are the historical record.` },
  { key: 'notes-research', label: 'notes research + litreview evidence',
    prompt: `Read /home/user/LLM-Test/notes/EXTERNAL_RESEARCH_BRIEF.md, LITREVIEW_FINDINGS.md,
RESEARCH_BRIEF_DIFFERENTIATION.md, research_continual_memory.md, research_experts_routing.md,
research_lr_schedules.md, research_tokenizer.md and every file under notes/_evidence/litreview/.
Summarise what external research has already been gathered, what it concluded, which claims are sourced
and which are not, and what research questions remain OPEN for the two definitive goals (language
production; continual learning without forgetting).` },
  { key: 'archive', label: 'archive/ (145 files of prior handoffs and decisions)',
    prompt: `Survey /home/user/LLM-Test/archive/ -- 145 files including handoff/, garry/, docs/, decisions/.
List the DECISIONS recorded there (archive/handoff/decisions/ has one file per decision), the north star
documents, and the superseded code. Say which decisions are still in force, which have been reversed by
later work, and which are undocumented elsewhere. This is the project's institutional memory; a rebuild
must not lose a decision that is still binding.` },
]

const CHAT_REGIONS = [
  { key: 'chat-a', label: 'this session, lines 1-2700', lo: 1, hi: 2700 },
  { key: 'chat-b', label: 'this session, lines 2700-5400', lo: 2700, hi: 5400 },
  { key: 'chat-c', label: 'this session, lines 5400-8072', lo: 5400, hi: 8072 },
]

const surveyThunks = []

for (const r of CODE_REGIONS) {
  surveyThunks.push(() => agent(
    `${NORTH}\n\nYOUR SCOPE: ${r.label}\n\n${r.prompt}\n\n${OUT}\n\nSet area to "${r.key}".`,
    { label: `survey:${r.key}`, phase: 'Survey', schema: SURVEY_SCHEMA }))
}
for (const r of DOC_REGIONS) {
  surveyThunks.push(() => agent(
    `${NORTH}\n\nYOUR SCOPE: ${r.label}\n\n${r.prompt}\n\n${OUT}\n\nSet area to "${r.key}". For documentation
you are surveying, "bugs" means claims that are WRONG or contradicted by the code; "junk" means material
that is superseded, duplicated, or was never true.`,
    { label: `survey:${r.key}`, phase: 'Survey', schema: SURVEY_SCHEMA }))
}
for (const r of CHAT_REGIONS) {
  surveyThunks.push(() => agent(
    `${NORTH}\n\nYOUR SCOPE: the owner's conversation transcript with the assistant, ${r.label}.

${CHAT_RECIPE}

Use LO=${r.lo}, HI=${r.hi}.

The owner has asked that EVERYTHING from these messages be fully documented. Your job is to extract, from
your range:
  - every INSTRUCTION or CONSTRAINT the owner gave (verbatim where possible)
  - every PREFERENCE the owner expressed (as distinct from the two definitive goals)
  - every fact about the OWNER'S OPERATING ENVIRONMENT: their machine, what they can and cannot run, what
    accounts/access they have, how they run things and hand back results, and anything the assistant
    ASSUMED about their operation and got WRONG
  - every DECISION taken, and every decision later REVERSED
  - every BUG found, and whether it was fixed
  - every measured RESULT, with the configuration it was measured under
Put instructions/constraints/preferences and environment facts in "facts" with confidence=verified and the
transcript line number as evidence. Put bugs in "bugs". Put reversed or superseded decisions in "junk".
Put binding decisions and hard-won gotchas in "carry_forward".

${OUT}\n\nSet area to "${r.key}".`,
    { label: `survey:${r.key}`, phase: 'Survey', schema: SURVEY_SCHEMA }))
}

surveyThunks.push(() => agent(
  `${NORTH}\n\nYOUR SCOPE: the owner's EARLIER conversation history, 2026-07-21 to 2026-08-15, preserved as
markdown chunks (the raw transcript for that period no longer exists, so these files are primary source).

Read /home/user/LLM-Test/notes/_evidence/chat/user_turns.md IN FULL -- it holds all 455 of the owner's own
turns for that period, which is the single most important document for this task. Then read
notes/_evidence/chat/chunks/MANIFEST.md and sample the chunks (chunk_01..chunk_12) for the assistant-side
context around the most consequential user turns. The chunks are large; use grep to find the passages that
matter rather than reading all of them end to end.

Extract, exactly as for the later transcript:
  - every INSTRUCTION or CONSTRAINT the owner gave (verbatim where possible)
  - every PREFERENCE expressed
  - every fact about the owner's OPERATING ENVIRONMENT and anything the assistant assumed wrongly about it
  - every DECISION, and every decision later reversed
  - the arc of the project: what was tried, in what order, and why it changed
Put instructions/constraints/preferences/environment facts in "facts". Put the project arc in
"carry_forward" as dated items.

${OUT}\n\nSet area to "chat-early".`,
  { label: 'survey:chat-early', phase: 'Survey', schema: SURVEY_SCHEMA }))

const surveys = (await parallel(surveyThunks)).filter(Boolean)
log(`survey complete: ${surveys.length} areas, ` +
    `${surveys.reduce((n, s) => n + (s.facts || []).length, 0)} facts, ` +
    `${surveys.reduce((n, s) => n + (s.bugs || []).length, 0)} bugs, ` +
    `${surveys.reduce((n, s) => n + (s.levers || []).length, 0)} lever records`)

// A compact digest the design agents can actually hold in context.
const digest = surveys.map(s => {
  const f = (s.facts || []).slice(0, 40).map(x => `  - ${x.claim} [${x.evidence}]`).join('\n')
  const b = (s.bugs || []).slice(0, 30).map(x => `  - (${x.severity}/${x.bug_class}) ${x.title} @ ${x.where}`).join('\n')
  const l = (s.levers || []).slice(0, 60)
    .map(x => `  - ${x.name} -> owner:${x.owner} couples:[${(x.couples_with || []).join(',')}]`).join('\n')
  const c = (s.carry_forward || []).slice(0, 30).map(x => `  - ${x.item}`).join('\n')
  const j = (s.junk || []).slice(0, 25).map(x => `  - ${x.what} (${x.safe_to_drop ? 'droppable' : 'keep'})`).join('\n')
  return `### AREA ${s.area}\n${s.summary}\nFACTS:\n${f}\nLEVERS:\n${l}\nBUGS:\n${b}\nCARRY FORWARD:\n${c}\nJUNK:\n${j}`
}).join('\n\n')

// ---------------------------------------------------------------- DESIGN
phase('Design')

const REQS = `THE OWNER'S REWORK REQUIREMENTS, verbatim:
  - full system rework; a lot of unnecessary material is present and must be filtered out
  - regenerate all files; all files should be NEW; do not use memory as the basis for everything
  - regenerate all documentation
  - regenerate a new set of needed research
  - updated history/timeline
  - remake goals, ideas, etc
  - "Levers need to be cleanly delineated within the code, they should not affect each other"
  - re-establish instructions: the owner's system specifics, what they can do, and things the assistant
    assumed about OPERATION (not about the project) and got wrong, stated as reference
  - detailed references and similar material included
  - do NOT treat code or program results as definitive -- they are signals. The system is not optimized
    and bugs/confounds are likely. Results must be reported in context.
  - the ONLY definitives are the owner's final goals: a language target with room for additional
    inclusions, and continual learning. Everything else is a PREFERENCE and should be recorded as one.
  - proper organization; a bugs/issues list; anything documentable may be documented separately
  - work happens on a new branch, rm-predict-DC`

const DESIGN_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['name', 'thesis', 'layout', 'lever_mechanism', 'migration', 'risks', 'what_it_drops'],
  properties: {
    name: { type: 'string' },
    thesis: { type: 'string', description: 'the one idea this design is built on, 2-4 sentences' },
    layout: {
      type: 'array',
      description: 'the proposed file/directory tree, one entry per file or directory',
      items: {
        type: 'object', additionalProperties: false,
        required: ['path', 'purpose', 'owns'],
        properties: {
          path: { type: 'string' },
          purpose: { type: 'string' },
          owns: { type: 'array', items: { type: 'string' }, description: 'levers/mechanisms this file owns exclusively' },
        },
      },
    },
    lever_mechanism: {
      type: 'string',
      description: 'CONCRETE mechanism by which levers are delineated and prevented from affecting each other: how a lever is declared, who may read it, how a derived value is named, how a genuine interaction is made explicit, and how a violation is caught mechanically (by a test, not by review).',
    },
    migration: {
      type: 'array',
      description: 'ordered implementation steps from the current repo to this layout',
      items: {
        type: 'object', additionalProperties: false,
        required: ['step', 'what', 'verifiable_by'],
        properties: { step: { type: 'integer' }, what: { type: 'string' }, verifiable_by: { type: 'string' } },
      },
    },
    risks: { type: 'array', items: { type: 'string' } },
    what_it_drops: { type: 'array', items: { type: 'string' }, description: 'material this design deliberately does not carry forward' },
  },
}

const ANGLES = [
  { key: 'strict-modules', angle: `Design from STRICT MODULE OWNERSHIP: every lever belongs to exactly one
module, a module may only read its own levers, and cross-module needs are satisfied by passing an explicit
value rather than by reading a shared global. Derived quantities get their own names and are computed in
one place. Prioritise making a violation impossible to write rather than merely detectable.` },
  { key: 'declared-graph', angle: `Design from a DECLARED DEPENDENCY GRAPH: levers stay in one registry but
each declares its owner, its type, its default, and every lever it interacts with, and a static checker
fails the build when the code's actual reads disagree with the declaration. Prioritise mechanical
verifiability and a small diff from the current single-file layout.` },
  { key: 'mechanism-instrument', angle: `Design from the split the project keeps tripping over: MECHANISM
vs INSTRUMENT. Training mechanism and measurement are currently interleaved, which is how the report ends
up measuring a different sample from the one it names and how a diagnostic mutates the model. Separate
them completely -- instruments are pure functions over a snapshot -- and let the lever layout fall out of
that. Prioritise trustworthy measurement, since the owner says results are only signals.` },
  { key: 'minimal-core', angle: `Design from RUTHLESS SUBTRACTION: the owner says there is a lot of
unnecessary material. Start from the two definitive goals and include only what serves them, then add back
only mechanisms with evidence they fire and matter. Prioritise the smallest system that can still make the
continual-learning claim, and be explicit about what large features you are proposing to cut and why.` },
]

const designs = (await parallel(ANGLES.map(a => () => agent(
  `${NORTH}\n\n${REQS}\n\nYOU ARE ONE OF FOUR INDEPENDENT ARCHITECTS. Your assigned angle:\n${a.angle}\n\n
Below is a survey of the ENTIRE current repository, its documentation, its archive and the owner's full
conversation history. The full commit record (379 commits, 2026-07-21..2026-08-28, reconstructed from the two
sources it survives in) is at /home/user/LLM-Test/.rework/COMMIT_RECORD.md -- READ IT. The complete
unabridged survey, one JSON file per area, is in /home/user/LLM-Test/.rework/survey/ -- read any area you
need in full rather than relying on the digest below. Use it as your evidence base. You may also read any file in
/home/user/LLM-Test directly to check something.\n\n${digest}\n\n
Produce a complete target architecture. Be concrete: real paths, real module names, a real mechanism for
lever delineation that a test can enforce. The current system is ~23,000 lines across 40 files with a
9,859-line main file and a 328-knob registry; your layout must plausibly hold all of the functionality
that survives your cuts.`,
  { label: `design:${a.key}`, phase: 'Design', schema: DESIGN_SCHEMA })))).filter(Boolean)

log(`${designs.length} architectures proposed: ${designs.map(d => d.name).join(' | ')}`)

// ---------------------------------------------------------------- JUDGE
phase('Judge')

const JUDGE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['scores', 'best', 'best_reason', 'grafts', 'fatal_flaws'],
  properties: {
    scores: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        required: ['design', 'lever_isolation', 'fits_goals', 'implementable', 'preserves_knowledge', 'total', 'note'],
        properties: {
          design: { type: 'string' },
          lever_isolation: { type: 'integer', minimum: 0, maximum: 10 },
          fits_goals: { type: 'integer', minimum: 0, maximum: 10 },
          implementable: { type: 'integer', minimum: 0, maximum: 10 },
          preserves_knowledge: { type: 'integer', minimum: 0, maximum: 10 },
          total: { type: 'integer' },
          note: { type: 'string' },
        },
      },
    },
    best: { type: 'string' },
    best_reason: { type: 'string' },
    grafts: {
      type: 'array',
      description: 'specific ideas from the non-winning designs that should be merged into the winner',
      items: { type: 'object', additionalProperties: false, required: ['from', 'idea', 'why'],
               properties: { from: { type: 'string' }, idea: { type: 'string' }, why: { type: 'string' } } },
    },
    fatal_flaws: {
      type: 'array',
      items: { type: 'object', additionalProperties: false, required: ['design', 'flaw'],
               properties: { design: { type: 'string' }, flaw: { type: 'string' } } },
    },
  },
}

const designText = designs.map(d =>
  `## ${d.name}\nTHESIS: ${d.thesis}\nLEVER MECHANISM: ${d.lever_mechanism}\n` +
  `LAYOUT:\n${(d.layout || []).map(l => `  ${l.path} -- ${l.purpose} [owns: ${(l.owns || []).join(', ')}]`).join('\n')}\n` +
  `MIGRATION:\n${(d.migration || []).map(m => `  ${m.step}. ${m.what} (verify: ${m.verifiable_by})`).join('\n')}\n` +
  `RISKS: ${(d.risks || []).join('; ')}\nDROPS: ${(d.what_it_drops || []).join('; ')}`).join('\n\n')

const LENSES = [
  `Judge primarily on LEVER ISOLATION: does the design actually make it impossible, or at least
mechanically detectable, for one lever to change another's meaning? The current system's own code prints
COUPLING warnings because EPOCHS sets both run length and the LR horizon, TOK_ANCHOR is gated on
TOK_COMPOSE, WRITE_QUANTILE is gated behind an unrelated flag, and TOKENIZER_PATH served as both the read
path and the write path until it destroyed a checkpoint's vocabulary. A design that only documents
coupling has not solved this.`,
  `Judge primarily on WHETHER THE TWO GOALS STAY MEASURABLE: language production and continual learning
without forgetting. The owner says every result is a signal, not a fact -- so the design must make it easy
to state what was measured, on what sample, and what could confound it. A design that makes the system
tidier but the measurements no more trustworthy has missed the point.`,
  `Judge primarily on IMPLEMENTABILITY AND KNOWLEDGE PRESERVATION. This is a full regeneration of ~23,000
lines carrying years of hard-won gotchas, most of which live only in code comments and commit messages. A
design that is elegant but cannot be executed incrementally, or that would silently lose an invariant the
project paid for, is worse than a duller one that can.`,
]

const judgements = (await parallel(LENSES.map((lens, i) => () => agent(
  `${NORTH}\n\n${REQS}\n\nYou are judge ${i + 1} of 3, each with a different lens.\n\nYOUR LENS:\n${lens}\n\n
Here are four independently produced target architectures for the rework. Score each 0-10 on
lever_isolation, fits_goals, implementable, preserves_knowledge; total is their sum. Name the best, say
why, and list SPECIFIC ideas from the others worth grafting in. Be hard to please: name fatal flaws.\n\n${designText}`,
  { label: `judge:${i + 1}`, phase: 'Judge', schema: JUDGE_SCHEMA })))).filter(Boolean)

// ---------------------------------------------------------------- SYNTHESIZE
phase('Synthesize')

const FINAL_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['architecture_summary', 'layout', 'lever_rule', 'lever_enforcement', 'doc_set', 'phases',
             'bugs_open', 'questions_for_owner', 'owner_environment_facts', 'preferences_observed',
             'what_gets_dropped', 'knowledge_that_must_survive'],
  properties: {
    architecture_summary: { type: 'string' },
    layout: {
      type: 'array',
      items: { type: 'object', additionalProperties: false, required: ['path', 'purpose', 'owns'],
               properties: { path: { type: 'string' }, purpose: { type: 'string' },
                             owns: { type: 'array', items: { type: 'string' } } } },
    },
    lever_rule: { type: 'string', description: 'the rule, stated so a reader can apply it' },
    lever_enforcement: { type: 'string', description: 'the test/checker that catches a violation' },
    doc_set: {
      type: 'array',
      description: 'every document to be generated, with its purpose and its source of truth',
      items: { type: 'object', additionalProperties: false, required: ['path', 'purpose', 'sourced_from'],
               properties: { path: { type: 'string' }, purpose: { type: 'string' }, sourced_from: { type: 'string' } } },
    },
    phases: {
      type: 'array',
      description: 'ordered implementation phases, each independently verifiable',
      items: { type: 'object', additionalProperties: false,
               required: ['n', 'title', 'deliverables', 'verified_by', 'depends_on'],
               properties: { n: { type: 'integer' }, title: { type: 'string' },
                             deliverables: { type: 'array', items: { type: 'string' } },
                             verified_by: { type: 'string' }, depends_on: { type: 'string' } } },
    },
    bugs_open: {
      type: 'array',
      description: 'every currently-open bug or issue found anywhere in the survey, deduplicated, most severe first',
      items: { type: 'object', additionalProperties: false,
               required: ['title', 'severity', 'where', 'symptom', 'bug_class'],
               properties: { title: { type: 'string' }, severity: { type: 'string' }, where: { type: 'string' },
                             symptom: { type: 'string' }, bug_class: { type: 'string' } } },
    },
    questions_for_owner: {
      type: 'array',
      description: 'decisions only the owner can make. Each with the options and what changes depending on the answer.',
      items: { type: 'object', additionalProperties: false, required: ['question', 'why_it_matters', 'options', 'recommendation'],
               properties: { question: { type: 'string' }, why_it_matters: { type: 'string' },
                             options: { type: 'array', items: { type: 'string' } }, recommendation: { type: 'string' } } },
    },
    owner_environment_facts: {
      type: 'array',
      description: 'what is known about the owner machine, access and working style, and what the assistant got WRONG about it',
      items: { type: 'object', additionalProperties: false, required: ['fact', 'evidence', 'needs_confirmation'],
               properties: { fact: { type: 'string' }, evidence: { type: 'string' }, needs_confirmation: { type: 'boolean' } } },
    },
    preferences_observed: {
      type: 'array',
      description: 'standing preferences the owner has expressed, as distinct from the two definitive goals',
      items: { type: 'object', additionalProperties: false, required: ['preference', 'evidence'],
               properties: { preference: { type: 'string' }, evidence: { type: 'string' } } },
    },
    what_gets_dropped: { type: 'array', items: { type: 'string' } },
    knowledge_that_must_survive: { type: 'array', items: { type: 'string' } },
  },
}

const judgeText = judgements.map((j, i) =>
  `### Judge ${i + 1}\nBEST: ${j.best} -- ${j.best_reason}\n` +
  `SCORES: ${(j.scores || []).map(s => `${s.design}=${s.total} (iso ${s.lever_isolation}, goals ${s.fits_goals}, impl ${s.implementable}, know ${s.preserves_knowledge}) ${s.note}`).join(' | ')}\n` +
  `GRAFTS: ${(j.grafts || []).map(g => `[from ${g.from}] ${g.idea} -- ${g.why}`).join(' | ')}\n` +
  `FATAL: ${(j.fatal_flaws || []).map(f => `${f.design}: ${f.flaw}`).join(' | ')}`).join('\n\n')

const allBugs = surveys.flatMap(s => (s.bugs || []).map(b => `[${s.area}] (${b.severity}/${b.bug_class}) ${b.title} @ ${b.where}: ${b.symptom}`)).join('\n')
const allCarry = surveys.flatMap(s => (s.carry_forward || []).map(c => `[${s.area}] ${c.item} -- ${c.why}`)).join('\n')
const allJunk = surveys.flatMap(s => (s.junk || []).filter(j => j.safe_to_drop).map(j => `[${s.area}] ${j.what} -- ${j.why}`)).join('\n')
const allQ = surveys.flatMap(s => (s.open_questions || []).map(q => `[${s.area}] ${q}`)).join('\n')

const plan = await agent(
  `${NORTH}\n\n${REQS}\n\nYou are the synthesizer. Four architectures were proposed and three judges with
different lenses scored them. Produce ONE target architecture and a complete implementation plan, merging
the winner with the grafts the judges identified and repairing the fatal flaws they named.

=== JUDGEMENTS ===
${judgeText}

=== THE FOUR DESIGNS ===
${designText}

=== FULL SURVEY DIGEST ===
${digest}

=== EVERY BUG FOUND ANYWHERE (deduplicate these into bugs_open) ===
${allBugs}

=== KNOWLEDGE THAT MUST SURVIVE A REBUILD ===
${allCarry}

=== MATERIAL THE SURVEY MARKED DROPPABLE ===
${allJunk}

=== OPEN QUESTIONS RAISED BY THE SURVEY ===
${allQ}

Requirements for your output:
  - layout: the actual file tree to be built, every file named.
  - lever_rule and lever_enforcement must be concrete enough to implement and to TEST. Vague answers here
    fail the owner's central requirement.
  - doc_set must cover: goals; ideas; history/timeline; research (both what has been found and what is
    still needed); glossary; references; the owner's operating environment and working agreement; a
    bugs/issues list; per-subsystem design docs. Say where each document's content comes from.
  - phases must be ordered, each independently verifiable, and each small enough to be executed and
    checked before the next begins.
  - bugs_open: deduplicate the bug list above into one ranked list. Do not drop anything; merge duplicates.
  - questions_for_owner: only decisions the owner must make. For each, state what changes depending on the
    answer, and give a recommendation. Include at minimum: whether "regenerate all files" means a
    behaviour-preserving restructure or a from-scratch rewrite whose numbers will not be comparable to the
    existing rm-predict baseline; what to do with data/ corpora and archive/; and whether known-wrong
    defaults should be fixed during the rework or preserved so the new branch can reproduce old runs first.
  - owner_environment_facts: everything the survey learned about the owner's machine, access, and working
    style, flagging which need confirmation. Include anything the assistant assumed and got wrong.
  - preferences_observed: standing preferences, distinct from the two definitive goals.`,
  { label: 'synthesize:plan', phase: 'Synthesize', schema: FINAL_SCHEMA })

const critic = await agent(
  `${NORTH}\n\n${REQS}\n\nYou are a COMPLETENESS CRITIC. Below is a proposed implementation plan for a full
system rework, and the survey it was built from. Your only job is to find what is MISSING or WRONG.

Ask specifically:
  - Does the doc_set cover every one of the owner's listed requirements? Walk the list literally.
  - Does the plan account for the owner's full chat history being documented?
  - Is the lever enforcement mechanism actually testable, or is it aspiration?
  - Are there bugs in the survey that did not make it into bugs_open?
  - Are there phases that cannot in fact be verified independently?
  - Are there questions the owner MUST be asked that are not in questions_for_owner?
  - Is anything in "what_gets_dropped" actually load-bearing?

=== THE PLAN ===
${JSON.stringify(plan, null, 1).slice(0, 60000)}

=== SURVEY DIGEST ===
${digest}

Return plain prose: a numbered list of concrete gaps, most important first, each with what to do about it.`,
  { label: 'critique:completeness', phase: 'Synthesize' })

return { plan, critic, surveyAreas: surveys.map(s => s.area), designs: designs.map(d => d.name),
         judgeBests: judgements.map(j => j.best),
         counts: { facts: surveys.reduce((n, s) => n + (s.facts || []).length, 0),
                   bugs: surveys.reduce((n, s) => n + (s.bugs || []).length, 0),
                   levers: surveys.reduce((n, s) => n + (s.levers || []).length, 0) } }
