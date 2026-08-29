export const meta = {
  name: 'untested-audit',
  description: 'Find every decision rule in the LIVE code that has no test, with evidence, then verify each claim',
  phases: [
    { title: 'Find', detail: 'one agent per subsystem, hunting untested decision rules' },
    { title: 'Verify', detail: 'refute each claim against the source and the existing tests' },
  ],
}

const REPO = '/home/user/LLM-Test'

const EXISTING = `Tests that ALREADY exist (do not report anything these cover):
  selftest.sh          runs them all, plus a real train and a real resume
  mem_evict_test.py    memory eviction clock + per-source floor
  compare_test.py      compare.py's decision rule, known-answer
  growth_test.py       PlateauGrowth REGRESSION trigger
  proj_test.py         proj_arith, the LR horizon's per-epoch shrink estimate
  cap_test.py          lift_to (cap lift size) and pin_tick (the pin clock)
  ramp_test.py         PlateauGrowth's ramp latch vs the capacity valve
  lr_test.py           _lr_at: wavelength, restarts, damping, resample re-warm
  blowup_test.py       blowup_stale, the in-run divergence alarm
  curve_test.py        curve_verdict, bwt_of, forgetting_of, cull_gate_open
  levers.py            every knob declared in _SPEC is read consistently
  notes_check.py       no note states a default the code contradicts`

const DIMENSIONS = [
  { key: 'fabric', prompt: `Audit Fabric in self_organize.py for DECISION RULES with no test.

Fabric is the expert population: routing (route/q_route/eemb/edec), growth (spawn_from, replicate, crossover), selection (manage, remove, use_age, contrib), HALT, chaining (maybe_deepen, _hopq), exploration (FAB_EXPLORE), and the identity space. Roughly self_organize.py:1200-2100.

A DECISION RULE is any branch, threshold, comparison or formula whose being wrong would change what the run does without raising an error. Prefer rules whose comments record a past bug -- those are the ones that break again.

For each: name it, give file:line, quote the rule, say what a wrong answer would silently do, and say whether the surrounding torch machinery makes it testable only via a hoisted pure function.` },
  { key: 'tokenizer', prompt: `Audit the tokenizer and vocabulary path for DECISION RULES with no test.

Files: tokenizer.py (DynamicTokenizer: segment, maybe_grow, mint gating, bytes_per_id, save/load), vocab.py, and the tokenizer-facing parts of self_organize.py (minting during training, RETOK_EVERY, the retok-skip guard, LOSS_MASK_DEAD, the softmax-width/dead-row accounting, TOK_MINT_PMIN / TOK_MINT_NOVEL / TOK_MINT_UNTIL).

The vocabulary has been the single biggest measured effect on quality in this project, and the retok path has produced at least one silent bug (a modulo cadence below a batch early-out that fired zero times). Report untested rules with file:line and what a wrong answer would silently do.` },
  { key: 'memory', prompt: `Audit memory.py for DECISION RULES with no test, EXCLUDING the eviction clock and per-source floor which mem_evict_test.py already covers.

Look at: the write gate (WRITE_GATE, adaptive/quantile controllers, WRITE_TARGET), the wrongness test (WRONG_THRESH, WRONG_MARGIN, WRONG_MIN_N), retrieval and scoring (TOPK, ctx_w, key construction), the read probe, unlearn/delete, per-expert partitioning (n_own, quota), and rekeying.

Report untested rules with file:line and what a wrong answer would silently do.` },
  { key: 'harness', prompt: `Audit longrun.sh for LOGIC with no test.

This is a 1,500-line harness and a bug in it costs GPU hours or, worse, files a result against the wrong description. Look at: _flags_for arm resolution and the __UNKNOWN_ARM__ guard, the ARMS presets, _reserve (the append-only guarantee), _done / _reusable / the resume-skip, _cfgsig (the config fingerprint), _stopped, the grid/seeds/repeat/pair/ladder argument parsing, and the summary parsers that grep logs for numbers.

Note that arm resolution and _reserve have both had bugs found by hand this session. Nothing tests any of it. Report each rule with file:line and what a wrong answer would silently do -- especially anything that could label a log with a config it did not run.` },
  { key: 'reports', prompt: `Audit the end-of-run report sections in self_organize.py for DECISION RULES with no test, EXCLUDING curve_verdict, bwt_of, forgetting_of and cull_gate_open which curve_test.py now covers.

Look at: the DID IT FIRE armed/inert classification itself (_r and _cfg), the SPECIALIZATION test and its shuffled-assignment null, ROUTER SELECTION, the domain-genuineness silhouette, POPULATION CHURN, GRADIENT REACH, ROUTING MIX, the anchors (uniform/order-0/order-1) and the held-out sampler, the LM training-curve slope tests, and the CAPACITY VALVE / BEST-KEEP report logic.

Several of these compute a statistic and then print a verdict about it. Report untested rules with file:line and what a wrong verdict would cause a reader to believe.` },
  { key: 'analysis', prompt: `Audit the analysis tools for DECISION RULES with no test.

Files: compare.py (EXCLUDING the core decision rule which compare_test.py covers -- look instead at the LOG PARSING, metric extraction, orientation handling, seed pairing and the bootstrap), holdout.py, runs.py, sweep_domain_report.py.

Log parsing is the highest-risk part: every number this project reasons about is scraped out of text with a regex, and a regex that matches the wrong line is silent. This session alone, a hand-written grep for 'held-out' matched a blow-up alarm line instead of the final report and produced four wrong numbers.

Report each with file:line and what a wrong answer would silently do.` },
  { key: 'schedule', prompt: `Audit the training loop's control flow in self_organize.py for DECISION RULES with no test, EXCLUDING the LR schedule (lr_test.py), the capacity valve clocks (cap_test.py), the ramp latch (ramp_test.py) and the blow-up alarm (blowup_test.py).

Look at: the batch accumulator and its early-out (and every cadence below it -- the note above it warns that modulo cadences there fire ZERO times), the epoch boundary and _resample, PHASED phase-boundary computation, the checkpoint cadence and _save_ckpt / RESUME guards, frozen_rng, the domain assembler's boundary detection and merge/cull rules, and the ENC_WARMUP adaptive early stop.

Report each with file:line and what a wrong answer would silently do.` },
  { key: 'worldmodel', prompt: `Audit world_model.py and verification.py for DECISION RULES with no test.

world_model.py: the forward-dynamics predictors, their fitness/selection, growth (WORLD_GROW), the latent, and the held-out beats-persistence-baseline test that the report prints a verdict from.
verification.py: the Reconstructor and the self-consistency path (VERIFY=selfcon is the DEFAULT, so this runs in every run).

VERIFY=selfcon running by default makes it live code with no test. Report each rule with file:line and what a wrong answer would silently do.` },
]

const FINDINGS = {
  type: 'object', additionalProperties: false, required: ['dimension', 'findings'],
  properties: {
    dimension: { type: 'string' },
    summary: { type: 'string' },
    findings: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        required: ['rule', 'location', 'quote', 'silent_failure', 'testable'],
        properties: {
          rule: { type: 'string', description: 'short name for the decision' },
          location: { type: 'string', description: 'file:line' },
          quote: { type: 'string', description: 'the actual line(s) of source' },
          silent_failure: { type: 'string', description: 'what a wrong answer does WITHOUT raising' },
          testable: { type: 'string', enum: ['pure-now', 'needs-hoist', 'needs-torch', 'shell'] },
          past_bug: { type: 'string', description: 'a bug the comments record here, if any' },
          priority: { type: 'string', enum: ['high', 'medium', 'low'] },
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
  (d) => agent(`${d.prompt}\n\n${EXISTING}\n\nWorking directory ${REPO}. Use rg/grep and targeted Reads; self_organize.py is 8,450 lines. Quote real source for everything -- an unsupported finding is worse than none. Rank by what would go UNNOTICED longest.`,
    { label: 'find:' + d.key, phase: 'Find', schema: FINDINGS }),
  (r, d) => {
    if (!r || !r.findings || !r.findings.length) return { key: d.key, summary: r && r.summary, checked: [] }
    return parallel(r.findings.slice(0, 3).map((f) => () =>
      agent(`Adversarially verify this claim that a decision rule in ${REPO} is UNTESTED. Your job is to REFUTE it.

DIMENSION: ${d.key}
RULE: ${f.rule}
LOCATION: ${f.location}
QUOTE: ${f.quote}
CLAIMED SILENT FAILURE: ${f.silent_failure}

Check: (a) does the cited line exist and say that? (b) is it ACTUALLY untested -- search all *_test.py, levers.py, notes_check.py and selftest.sh for anything that would catch a wrong answer here, including indirectly via the end-to-end run selftest.sh performs? (c) would a wrong answer really be silent, or does something downstream raise/assert/report it? (d) is it a real decision, or a constant/plumbing?

${EXISTING}

Default to real=false when uncertain.`,
      { label: 'verify:' + d.key, phase: 'Verify', schema: VERDICT })
      .then((v) => ({ finding: f, verdict: v }))
    )).then((vs) => ({ key: d.key, summary: r.summary, checked: vs.filter(Boolean), total: r.findings.length }))
  }
)

const clean = out.filter(Boolean)
log(`audited ${clean.length} subsystems`)

return {
  subsystems: clean.map((c) => ({
    key: c.key, summary: c.summary, total: c.total,
    confirmed_untested: (c.checked || []).filter((v) => v.verdict && v.verdict.real).map((v) => v.finding),
    refuted: (c.checked || []).filter((v) => v.verdict && !v.verdict.real)
      .map((v) => ({ rule: v.finding.rule, why_not: v.verdict.correction || v.verdict.reasoning })),
  })),
}
