export const meta = {
  name: 'outstanding-audit',
  description: 'The five audit dimensions that never ran, plus verification of memory.py findings nothing checked',
  phases: [
    { title: 'Find', detail: 'one agent per never-run subsystem' },
    { title: 'Verify', detail: 'adversarially refute the top finding from each' },
  ],
}

const REPO = '/home/user/LLM-Test'

const EXISTING = `Tests that ALREADY exist -- do NOT report anything these cover:
  selftest.sh (runs all of them + a real train + a real resume), mem_evict_test.py (eviction clock,
  per-source floor), compare_test.py (compare.py's core decision rule), growth_test.py (PlateauGrowth
  REGRESSION), proj_test.py (proj_arith), cap_test.py (lift_to, pin_tick), ramp_test.py (ramp latch vs the
  capacity valve), lr_test.py (_lr_at: wavelength/restarts/damping/re-warm), blowup_test.py (blowup_stale),
  curve_test.py (curve_verdict, bwt_of, forgetting_of, cull_gate_open), tok_test.py (DynamicTokenizer minting,
  round-trip, save/load), harness_test.sh (longrun.sh arm resolution, _reserve), levers.py, notes_check.py.

ALREADY FOUND AND FIXED this session -- do not re-report:
  tokenizer maybe_grow returning None for a rejected candidate; step % MANAGE_EVERY below the batch early-out
  at lines 5857/5982/6009; fab_use missing from the checkpoint.`

const DIMENSIONS = [
  { key: 'analysis', prompt: `Audit the ANALYSIS TOOLS in ${REPO} for decision rules with no test: compare.py (its LOG PARSING, metric extraction, orientation, seed pairing, bootstrap -- NOT the core decision rule), holdout.py, runs.py, sweep_domain_report.py.

Log parsing is the highest-risk surface in the project: every number reasoned about is scraped out of text by regex, and a regex matching the wrong line is silent. This session a hand-written grep for 'held-out' matched the blow-up ALARM line instead of the final report and produced four wrong numbers in a comparison table.

Concretely: feed compare.py the real logs in /root/.claude/uploads/e880caf7-1208-58de-93fd-49c41549bf70/*.log and check the numbers it extracts against what the ANCHORS block of each log actually says (the 'THIS MODEL x.xxx' line is the true final held-out). Report any mismatch as a defect with the exact numbers.` },
  { key: 'schedule', prompt: `Audit the TRAINING LOOP control flow in ${REPO}/self_organize.py for decision rules with no test, EXCLUDING the LR schedule, the capacity-valve clocks, the ramp latch and the blow-up alarm.

Look at: every remaining cadence below the batch early-out at line ~5825 (the note above it warns modulo cadences there fire ZERO times -- three were fixed this session, find any that remain, including in the epoch/report/checkpoint paths); the epoch boundary and _resample; PHASED phase-boundary computation; _save_ckpt and the RESUME guards; frozen_rng; the domain assembler's boundary detection, merge and cull rules; the ENC_WARMUP adaptive early stop.

For cadences, compute concretely: at BATCH_W=16 and the shipped cadence value, for how many of the 16 possible flush residues does it fire?` },
  { key: 'reports', prompt: `Audit the END-OF-RUN REPORT sections in ${REPO}/self_organize.py for decision rules with no test, EXCLUDING curve_verdict, bwt_of, forgetting_of, cull_gate_open.

Look at: the DID IT FIRE armed/inert classification (_r and _cfg) itself; the SPECIALIZATION statistic and its shuffled-assignment null; ROUTER SELECTION; the domain-genuineness silhouette; POPULATION CHURN; GRADIENT REACH; ROUTING MIX; the anchors (uniform / order-0 / order-1) and the held-out sampler; the LM training-curve slope tests; the CAPACITY VALVE and BEST-KEEP report logic.

Several compute a statistic and then print a VERDICT about it. A wrong verdict here is the most expensive failure this project has, because every decision is made by reading these lines. Report each with file:line and what a reader would wrongly believe.` },
  { key: 'worldmodel', prompt: `Audit ${REPO}/world_model.py and ${REPO}/verification.py for decision rules with no test.

world_model.py: the forward-dynamics predictors, their fitness and selection, growth (WORLD_GROW), the latent, and the held-out beats-persistence-baseline test the report prints a verdict from.
verification.py: the Reconstructor and the self-consistency path. VERIFY defaults to "selfcon", so that path runs in EVERY run and has no test at all.

Report each rule with file:line, what a wrong answer silently does, and whether it is testable without torch.` },
  { key: 'harness2', prompt: `Audit ${REPO}/longrun.sh for logic with no test, EXCLUDING _flags_for arm resolution and _reserve which harness_test.sh now covers.

Look at: _done / _reusable / the resume-skip (does it ever reuse a log from a DIFFERENT config?), _cfgsig (the config fingerprint -- what does it include and what does it miss?), _stopped, _corpsig, _knobs, _pilot_corpus (it returns early if ANY part file exists -- what else does that affect?), the grid/seeds/repeat/pair/ladder argument parsing, and the SUMMARY PARSERS that grep logs for numbers to build the comparison tables.

The summary parsers are the same risk class as compare.py: they scrape numbers out of logs with grep/sed and print a table the user makes decisions from. Check what they match against a real log at /root/.claude/uploads/e880caf7-1208-58de-93fd-49c41549bf70/1a3ef30f-sched_ctl.log -- especially whether 'held-out' matches the right line.` },
  { key: 'memverify', prompt: `In ${REPO}/memory.py, VERIFY these five claims made by an earlier audit that had no torch and executed nothing. For each: is it real, and what exactly happens?

  (a) nsrc (the per-source census the eviction floor reads) is maintained incrementally in write() and is NOT rebuilt on resume, while the resume path re-activates the whole store (self_organize.py ~4361 'mem.active[:_mn] = True'). So the floor mem_evict_test proves works is OFF after every resume.
  (b) the wrongness test (set_selfcon / is_wrong, memory.py ~452) has no test despite gating every read.
  (c) read() has no known-answer test; the last bug in it (hp identically 1.0) made memory net-negative for the whole project.
  (d) the quantile write gate is enabled in the constructor but WRITE_ADAPTIVE=0 everywhere, so no test -- including selftest.sh's real train and resume -- ever executes it.
  (e) MEM_PER_EXPERT is a no-op on the non-batched write path because write() has no 'own' parameter.

torch is NOT installed, so you cannot execute memory.py. Verify by reading the source carefully and quoting it. State clearly for each: CONFIRMED / REFUTED / PARTIAL, with the lines that decide it. Refute where you can -- an earlier audit of this exact file was wrong about the tokenizer's novelty knob.` },
]

const FINDINGS = {
  type: 'object', additionalProperties: false, required: ['dimension', 'findings'],
  properties: {
    dimension: { type: 'string' }, summary: { type: 'string' },
    findings: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        required: ['rule', 'location', 'quote', 'silent_failure', 'status'],
        properties: {
          rule: { type: 'string' }, location: { type: 'string' }, quote: { type: 'string' },
          silent_failure: { type: 'string' },
          status: { type: 'string', enum: ['CONFIRMED', 'REFUTED', 'PARTIAL', 'UNTESTED-GAP'] },
          priority: { type: 'string', enum: ['high', 'medium', 'low'] },
          pilot: { type: 'string', description: 'what a RUN would have to do to expose or measure this, if anything' },
        },
      },
    },
  },
}

const VERDICT = {
  type: 'object', additionalProperties: false, required: ['real', 'reasoning'],
  properties: { real: { type: 'boolean' }, reasoning: { type: 'string' }, correction: { type: 'string' } },
}

phase('Find')

const out = await pipeline(
  DIMENSIONS,
  (d) => agent(`${d.prompt}\n\n${EXISTING}\n\nWorking directory ${REPO}. self_organize.py is ~8,500 lines -- use rg and targeted Reads. Quote real source for everything. Also fill the 'pilot' field where a RUN (not a unit test) is what would expose the rule, since these will be turned into pilot arms.`,
    { label: 'find:' + d.key, phase: 'Find', schema: FINDINGS }),
  (r, d) => {
    if (!r || !r.findings || !r.findings.length) return { key: d.key, summary: r && r.summary, findings: [], checked: [] }
    const top = r.findings.filter((f) => f.status !== 'REFUTED').slice(0, 2)
    if (!top.length) return { key: d.key, summary: r.summary, findings: r.findings, checked: [] }
    return parallel(top.map((f) => () =>
      agent(`Adversarially verify this claim about ${REPO}. Your job is to REFUTE it.

DIMENSION: ${d.key}
RULE: ${f.rule}
LOCATION: ${f.location}
QUOTE: ${f.quote}
CLAIMED SILENT FAILURE: ${f.silent_failure}

Check the cited line exists and says that. Look for an innocent explanation: a guard elsewhere, a caller that cannot reach the state, a default that makes it unreachable, a test that covers it indirectly. ${EXISTING}

Default to real=false when uncertain.`,
      { label: 'verify:' + d.key, phase: 'Verify', schema: VERDICT })
      .then((v) => ({ finding: f, verdict: v }))
    )).then((vs) => ({ key: d.key, summary: r.summary, findings: r.findings, checked: vs.filter(Boolean) }))
  }
)

const clean = out.filter(Boolean)
log(`audited ${clean.length} subsystems`)

return {
  subsystems: clean.map((c) => ({
    key: c.key, summary: c.summary,
    all_findings: (c.findings || []).map((f) => ({ rule: f.rule, location: f.location, status: f.status,
                                                   priority: f.priority, silent_failure: f.silent_failure, pilot: f.pilot })),
    verified: (c.checked || []).map((v) => ({ rule: v.finding.rule, real: v.verdict.real,
                                              why: v.verdict.correction || v.verdict.reasoning })),
  })),
}
