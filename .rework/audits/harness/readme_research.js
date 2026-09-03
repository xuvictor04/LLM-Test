export const meta = {
  name: 'readme-round2',
  description: 'Establish the remaining facts and draft the GitHub landing page from verified claims only',
  phases: [
    { title: 'Research', detail: 'three agents: live state, the stale page, the document map' },
    { title: 'Draft', detail: 'synthesise from verified claims and the salvaged architecture claims' },
  ],
}

const REPO = '/home/user/LLM-Test'
const SALVAGED = '.rework/audits/readme_r1_partial.json'
const OUT = '.rework/audits'

const CONTEXT = `
Repository at ${REPO}. Read with Read/Grep/Glob; run things with \`cd ${REPO} && ...\`.

THE SITUATION. This repository holds an autonomous continual-learning ML research system. An OLD tree
(self_organize.py, memory.py, tokenizer.py, vocab.py, datastream.py, world_model.py and their
harness) has been FROZEN and moved under archive/. A REBUILD is underway in src/, organised around a
"lever spine". README.md is the project's GitHub landing page and it still describes the OLD tree.

THE OWNER'S TWO GOALS, and nothing else is definitive:
  (A) good language production, with room for additional modalities to be strapped on later
  (B) continual learning WITHOUT catastrophic forgetting

A PREVIOUS RESEARCH AGENT ALREADY ESTABLISHED THE ARCHITECTURE and its 56 claims are on disk at
${SALVAGED} (fields: claim, source, confidence, caveat). READ IT so you do not redo that work; your
job is the part it did not cover.

YOUR JOB IS FACTS, NOT PROSE. Every claim must be verified from a primary source — a file you read,
a command you ran and its output. Quote the source. If you cannot verify something, say so rather
than repeating what a document asserts.

BE ESPECIALLY CAREFUL WITH NUMBERS AND CLAIMS OF RESULT. This project has a recorded history of
documents citing figures that later invalidations retracted; .rework/ISSUES.md PART 2 catalogues
several. A number is reportable only if you can name where it comes from AND check whether anything
retracts it. Numbers on a landing page get quoted back at the project.

CHECK YOUR OWN NUMBERS BEFORE RETURNING THEM. There is no separate checking pass in this run: for
every numeric claim, go back to the primary source a second time and confirm it at THIS commit.

WRITE YOUR RESULT TO DISK BEFORE RETURNING IT, as JSON, to the path named in your task. A previous
run of this research lost sixteen of its twenty-one agents to a transient API overload; a file on
disk survives that.
`

const FACTS = {
  type: 'object', additionalProperties: false,
  properties: {
    summary: { type: 'string' },
    claims: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        properties: {
          claim: { type: 'string' }, source: { type: 'string' },
          confidence: { type: 'string', enum: ['verified', 'probable', 'unverified'] },
          caveat: { type: 'string' },
        },
        required: ['claim', 'source', 'confidence', 'caveat'],
      },
    },
  },
  required: ['summary', 'claims'],
}

const LENSES = [
  {
    key: 'live-state', out: `${OUT}/readme_live_state.json`,
    prompt: `ESTABLISH: how far the rebuild has got, and what a person can DO with the repository today.

Run these and report the REAL output:
  cd ${REPO} && for t in ownership contract census assemble couplings; do python3 tests/test_$t.py 2>&1 | tail -3; done
  cd ${REPO} && python3 tests/test_derive.py 2>&1 | tail -2
  cd ${REPO} && python3 tools/render_wiring.py --check
  cd ${REPO} && python3 tools/sync_counts.py --check
  cd ${REPO} && python3 -c "import sys;sys.path.insert(0,'src')
from spine import compose
try:
    compose.compose(environ={})
except NotImplementedError as e:
    print('stops at:', str(e).split(chr(10))[0])"

Then establish from tests/test_contract.py::k13_live_counts (import it and call it): how many entry
points exist, how many are implemented, how many are stubs, how many are declared deferred, how many
levers across how many packages, how many couplings and how many wires.

Read .rework/PLAN.md: what are P1..P9, which are complete, which is current, what remains?

DOES ANYTHING TRAIN? Find out and prove it. There is a sequence — DATA.open_areas ->
TOK.build_vocabulary -> DATA.data_plan -> DATA.draw_stream -> TOK.tokenize -> LM.resolve ->
LM.build_model -> LM.encode -> LM.decode — that produces a loss. Write it as a script, RUN it for a
couple of hundred steps, and report the actual loss curve. Then write out the shortest command
sequence a reader could paste to (1) run the checks and (2) see it train, and VERIFY each by running
it. Also read requirements.txt and docs/02_OPERATIONS.md and say whether each is current.
Also: what is in tools/, and what does each script do?`,
  },
  {
    key: 'stale-page', out: `${OUT}/readme_stale.json`,
    prompt: `ESTABLISH: exactly what is wrong with the current README.md, claim by claim. THIS IS THE
MOST IMPORTANT LENS — the new page must not re-publish anything the old one got wrong.

Read README.md in full. For EVERY factual claim — every path, every command, every number, every
status line — determine whether it is still true and cite what you checked.

For each of these, say whether it exists at the path the README gives, exists under archive/, or is
gone entirely: run_full_unfrozen.sh, self_organize.py, prompt.py, cl_bench.py, STATE.md,
garry/GARRY.md, CL_TESTBED.md, overarching-package.zip, requirements.txt, fetch_data.sh.

Then the numbers. The README has a "Headline result" paragraph and an "Honest status" section quoting
measured figures (-0.0009 expert-deletion collateral, 0.0303 memory rows, 24.79 gradient-ascent,
~1.7 bits/byte, ~1% precision, ~25,000x, ~1000x) and it sources them to "STATE.md §7". Search
.rework/ISSUES.md (PART 2 especially) and .rework/CENSUS.md for INV-* references, invalidations and
retractions bearing on those figures. Report precisely which are VOID, which are DEGRADED, which
STAND, and what retracts each. Read .rework/DECISIONS.md's D1 — it discusses the status of some of
these numbers directly.

Return a claim-by-claim verdict.`,
  },
  {
    key: 'docs+status', out: `${OUT}/readme_docs.json`,
    prompt: `ESTABLISH: the document map, and what the project can honestly claim.

Part 1 — the map. For each of docs/02_OPERATIONS.md, docs/03_WIRING.md, docs/04_CONTRACT.md,
docs/proposals/*.md, .rework/README.md, .rework/PLAN.md, .rework/ISSUES.md, .rework/CENSUS.md,
.rework/DECISIONS.md, .rework/QUESTIONS.md, .rework/COMMIT_RECORD.md: read enough to say in one or
two sentences what it is FOR, who should read it, roughly how big it is (line count), and whether it
is generated or hand-written — docs/03_WIRING.md and parts of docs/04_CONTRACT.md are generated;
find and name the tools that generate them. Is there a docs/00_* or 01_*? If missing, say so.

Part 2 — honest status. Read .rework/ISSUES.md's header, its PART 1/2/3/4 headers and its "Bug
classes, by frequency" section; .rework/PLAN.md; .rework/DECISIONS.md in full; and
docs/04_CONTRACT.md's opening sections.
Answer with sources: what did the survey of the old tree find, in numbers (how many records, which
bug classes and their counts)? What is the rebuild's thesis — why rebuild rather than patch? What
does the project claim is PROVEN, what is RETRACTED, what is OPEN? What are the standing open
questions the owner has to decide? What limitations do the tree's own documents state?
Be scrupulous: report what the documents claim AND whether anything in the tree contradicts it. The
goal is a status section a sceptical reader cannot catch out.`,
  },
]

phase('Research')
log('Three lenses on the remaining facts; architecture already on disk')

const research = await parallel(LENSES.map(l => () =>
  agent(`${CONTEXT}\n\n${l.prompt}\n\nYOUR OUTPUT FILE: ${l.out}`,
    { label: `research:${l.key}`, phase: 'Research', schema: FACTS })))

const ok = research.filter(Boolean)
const total = ok.reduce((n, r) => n + (r.claims || []).length, 0)
log(`${total} claims gathered across ${ok.length} lenses`)

phase('Draft')
const draft = await agent(`${CONTEXT}

Four research agents have now established the current state. The architecture claims are at
${SALVAGED} — READ THAT FILE. The other three lenses returned:

${ok.map((r, i) => `## lens ${LENSES[i] ? LENSES[i].key : i}\n${r.summary}\n\nCLAIMS:\n${(r.claims || []).map(c =>
  `- [${c.confidence}] ${c.claim}\n    source: ${c.source}${c.caveat ? `\n    caveat: ${c.caveat}` : ''}`).join('\n')}`).join('\n\n')}

Their per-lens JSON is also on disk under ${OUT}/ if you need detail.

WRITE THE BODY OF THE NEW README.md — the repository's GitHub landing page.

HARD REQUIREMENTS:
 1. The existing file opens with an ALL RIGHTS RESERVED notice and a contact address. That notice
    STAYS EXACTLY AS IT IS and is NOT yours to touch — do not reproduce it, do not alter it. Start
    your output at the project title that follows it.
 2. Every number and every path must come from a claim that was verified. If a claim was
    unverified or retracted, do not use it. Do not invent a command you have not seen verified.
 3. Any figure the research found VOID or RETRACTED must not appear as a live claim. If you mention
    one, mark it explicitly as retracted and say what retracted it.
 4. Be honest about state: this is a rebuild in progress, most entry points are still stubs, and
    nothing has been trained at scale under the new tree. Say so plainly. A reader must not come
    away thinking the rebuild is finished.
 5. State the two goals. Explain the ownership spine and why it exists — a reader landing here
    should understand the central idea in one paragraph.
 6. Point the right reader at the right document, using the map.
 7. Give the commands that WORK TODAY and be explicit about what does not work yet.
 8. The owner has a standing instruction: "tell me the defaults, so I know what is off and on." The
    page is the natural place to satisfy that for a reader who is not in the conversation — include
    the defaults of the switches that decide what a run does, from the levers themselves.

STYLE: Markdown. Direct and specific. No marketing language, no emoji, no exclamation marks. Short
sections with headings. Tables where a table beats prose. Assume a competent engineer. Prefer
stating a limitation plainly over hedging. Do not pad.

Write the markdown to ${OUT}/readme_draft.md with Write, AND return it as your text.`,
  { label: 'draft:readme', phase: 'Draft' })

return { draft, claims: total, lenses: ok.map((r, i) => ({ lens: LENSES[i] && LENSES[i].key, claims: (r.claims || []).length })) }
