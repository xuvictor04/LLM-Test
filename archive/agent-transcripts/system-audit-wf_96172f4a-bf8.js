export const meta = {
  name: 'system-audit',
  description: 'Audit the whole project: inert mechanisms, timeline, branches, dead code, doc drift, test coverage, defaults-vs-evidence',
  phases: [
    { title: 'Audit', detail: 'one agent per dimension, over the repo and its git history' },
    { title: 'Verify', detail: 'adversarially refute each finding against the source' },
  ],
}

const REPO = '/home/user/LLM-Test'

const DIMENSIONS = [
  {
    key: 'inert',
    prompt: `Find mechanisms in ${REPO} that are BUILT but have never actually run.

This project's single most repeated failure is shipping a mechanism, defaulting it off or making it unreachable, then reasoning about the system as if it were active. Examples already found: FAB_RESCUE fired zero times for a whole investigation; TOK_ANCHOR's loss term never enters the loss; LR_DECAY was written for a specific failure and sat at 0.0 while that failure recurred; a diagnostic was attached to a banner field that only renders on override.

Method:
- self_organize.py has a _SPEC knob registry near the top (~line 60-450). Enumerate every knob, its default, and whether anything can reach it at that default.
- longrun.sh has _flags_for() with every named arm, and ARMS presets. Cross-reference: which knobs are NEVER set by any arm AND have a default that makes them inert?
- Look for the "DID IT FIRE" report in self_organize.py and see which counters exist.
- Look for code paths gated on a flag that no arm sets.
Report each as a finding with the knob/mechanism name, its default, the file:line where it is read, and what makes it unreachable.`,
  },
  {
    key: 'timeline',
    prompt: `Reconstruct the working timeline of ${REPO} from its git history.

Run git log with dates, authors, and stats. Group the work into phases: what was being worked on in each period, what question each phase was trying to answer, and whether it concluded or was abandoned.

Useful: git log --format='%h %ad %s' --date=short ; git log --stat ; git log --diff-filter=A --name-only (when files were added).

Report as findings where each finding is one PHASE: dates, the theme, the commits that define it, and whether it reached a conclusion or was dropped. Be concrete and cite commit hashes. Also flag any period where the same problem was fixed more than once.`,
  },
  {
    key: 'branches',
    prompt: `Audit the branches of ${REPO}.

There are: rm-predict (current, active) and claude/hub-addition-1ueehb (plus their origin counterparts). Determine for each: last commit and date, how far ahead/behind rm-predict it is, what unique commits it carries that rm-predict does NOT have, and whether anything on it is worth keeping or it is safe to consider abandoned.

Use: git branch -a -vv; git log --oneline rm-predict..claude/hub-addition-1ueehb; git log --oneline claude/hub-addition-1ueehb..rm-predict | wc -l; git merge-base; git diff --stat.

Report findings: one per branch, plus one per unique commit that carries work not present on rm-predict.`,
  },
  {
    key: 'deadcode',
    prompt: `Find dead, superseded, or duplicated code in ${REPO}.

There are ~40 top-level .py and .sh files. Determine which are actually reachable: imported by self_organize.py, invoked by longrun.sh / selftest.sh / preflight.sh, or documented as an entry point. Then find:
- scripts nothing calls and nothing documents
- two files doing the same job (e.g. several fetch_* scripts, several sweep_* scripts, several probe_* scripts)
- functions in self_organize.py defined and never called
- shell subcommands in longrun.sh that are unreachable or broken

Use grep/rg to check call sites before declaring anything dead. Report each with the file, what it was for, and the evidence that nothing reaches it.`,
  },
  {
    key: 'docdrift',
    prompt: `Find where the notes in ${REPO}/notes/ contradict the current code.

notes/ holds ~1 MB of markdown (00_INDEX, 01_TIMELINE, 02_IDEAS, 03_EXPERIMENTS, 04_RESULTS, 05_ERRORS, 06_CONTINUAL_LEARNING, 07_WIP, 08_GLOSSARY, 09_COMMENT_AUDIT, 10_HISTORY_FINDINGS, DOC_PLAN and several research_*.md). Most were last written 2026-08-18/20; the code has moved since.

Do NOT try to read them all. Instead: pick the claims that MATTER -- current defaults, which mechanisms are on, what the best results were, what is described as unimplemented -- and check each against self_organize.py and longrun.sh as they stand now.

Especially check: 02_IDEAS for items described as NEVER IMPLEMENTED that now exist; 07_WIP for work described as in progress; 04_RESULTS for headline numbers; 09_COMMENT_AUDIT which is described as an unapplied plan.

Report each drift as a finding: the file, the claim, and what the code actually does now.`,
  },
  {
    key: 'testcov',
    prompt: `Audit the test coverage of the measurement instruments in ${REPO}.

The project's discipline is that instruments are themselves code that can silently break. selftest.sh runs the unit tests. Existing tests: mem_evict_test.py, compare_test.py, growth_test.py, proj_test.py, cap_test.py, ramp_test.py, lr_test.py, blowup_test.py, levers.py.

Determine: which report sections and decision rules in self_organize.py have a test, and which do NOT. Look for the end-of-run report sections (DID IT FIRE, FORGOTTEN/EVICTED, BWT, CROSS-CHECK verdicts, CAPACITY VALVE, BEST-KEEP, ROUTER SELECTION, SPECIALIZATION) and for decision rules (culling gates, growth triggers, plateau tests, the blow-up alarm, the LR schedule).

Report each untested decision rule or report section as a finding, with file:line and why an error there would be hard to notice.`,
  },
  {
    key: 'defaults',
    prompt: `In ${REPO}, find knobs whose DEFAULT contradicts what the project has measured.

self_organize.py comments are unusually detailed and often record measurements next to the knob. Find cases where a comment says a setting was measured better/worse and the default does not match, or where a comment records a decision that was never implemented in the default.

A known example already fixed: MEM_PER_EXPERT's comment said "DEFAULT OFF, on measurement" while the code read _i("MEM_PER_EXPERT", 1) -- a decision written down and never implemented.

Read the _SPEC registry and the read sites, and compare each default against the comment that justifies it. Report each mismatch with the knob, the default, the comment's claim, and file:line.`,
  },
]

const FINDINGS = {
  type: 'object',
  additionalProperties: false,
  required: ['dimension', 'findings'],
  properties: {
    dimension: { type: 'string' },
    summary: { type: 'string', description: 'two or three sentences on the overall state of this dimension' },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['title', 'evidence', 'so_what'],
        properties: {
          title: { type: 'string', description: 'one line, specific' },
          evidence: { type: 'string', description: 'file:line and verbatim source or log text' },
          so_what: { type: 'string', description: 'what it costs, or what decision it changes' },
          severity: { type: 'string', enum: ['high', 'medium', 'low'] },
          action: { type: 'string', description: 'delete / fix / test / document / leave-and-note' },
        },
      },
    },
  },
}

const VERDICT = {
  type: 'object',
  additionalProperties: false,
  required: ['real', 'reasoning'],
  properties: {
    real: { type: 'boolean' },
    reasoning: { type: 'string' },
    correction: { type: 'string' },
  },
}

phase('Audit')

const out = await pipeline(
  DIMENSIONS,
  (d) => agent(d.prompt + `\n\nWorking directory is ${REPO}. Use rg/grep and targeted Reads; these files are large. Cite file:line for everything. Report only what you can quote source for -- an unsupported finding is worse than none.`,
    { label: 'audit:' + d.key, phase: 'Audit', schema: FINDINGS }),
  // (prevResult, originalItem, index) -- the dimension is threaded through so the verifier
  // never has to look it up from the result, which is what broke the last workflow.
  (r, d) => {
    if (!r || !r.findings || !r.findings.length) return { key: d.key, summary: r && r.summary, checked: [] }
    const top = r.findings.slice(0, 4)
    return parallel(top.map((f) => () =>
      agent(`Adversarially verify this audit finding about ${REPO}. Your job is to REFUTE it.

DIMENSION: ${d.key}
CLAIM: ${f.title}
EVIDENCE OFFERED: ${f.evidence}
CLAIMED CONSEQUENCE: ${f.so_what}

Go to the source. Check the cited file:line exists and says what is claimed. Check for an innocent explanation: a knob set by an arm the auditor missed, a call site in another file, a comment that is historical rather than current, a default that is correct for a reason stated elsewhere. Default to real=false when uncertain. Only real=true if the source unambiguously supports it.`,
      { label: 'verify:' + d.key, phase: 'Verify', schema: VERDICT })
      .then((v) => ({ finding: f, verdict: v }))
    )).then((vs) => ({ key: d.key, summary: r.summary, checked: vs.filter(Boolean), total: r.findings.length }))
  }
)

const clean = out.filter(Boolean)
log(`audited ${clean.length} dimensions`)

return {
  dimensions: clean.map((c) => ({
    key: c.key,
    summary: c.summary,
    total_findings: c.total,
    confirmed: (c.checked || []).filter((v) => v.verdict && v.verdict.real)
      .map((v) => ({ title: v.finding.title, evidence: v.finding.evidence, so_what: v.finding.so_what,
                     severity: v.finding.severity, action: v.finding.action })),
    refuted: (c.checked || []).filter((v) => v.verdict && !v.verdict.real)
      .map((v) => ({ title: v.finding.title, why_not: v.verdict.correction || v.verdict.reasoning })),
  })),
}
