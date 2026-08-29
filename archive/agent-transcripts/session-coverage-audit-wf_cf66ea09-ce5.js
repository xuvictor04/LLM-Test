export const meta = {
  name: 'session-coverage-audit',
  description: 'Which of this session changes have never executed, and which can never execute?',
  phases: [{ title: 'Audit' }, { title: 'Refute' }, { title: 'Report' }],
}

const CTX = [
  'REPO /home/user/LLM-Test, branch rm-predict, HEAD 271f875. Autonomous continual-learning ML research',
  'system. Core discipline is the DID IT FIRE audit: the recurring bug class is a mechanism that RUNS AND',
  'DOES NOTHING, a quantity in one unit consumed in another, or data recorded and never read.',
  '',
  'torch IS installed here (2.13, CPU). You CAN import self_organize.py and run short training runs.',
  'A tiny two-domain corpus exists at',
  '  /tmp/claude-0/-home-user-LLM-Test/e880caf7-1208-58de-93fd-49c41549bf70/scratchpad/smoke',
  'with train/eng (0.38 MB prose) and train/py (0.4 MB Python). A checkpoint is at .../scratchpad/ckA,',
  'its pristine vocabulary at .../scratchpad/ckA.tok.pristine. A ~1-3 minute run looks like:',
  '  env DATA_MODE=real DATA_DIR=<corpus> DOMAINS=eng DEVICE=cpu DISK_STREAM=1 CORPUS_CAP=100000000 \\',
  '      STREAM_LEN=20000 EPOCHS=1 D_MODEL=64 WIN=64 BATCH_W=4 VMAX=512 SEED_VOCAB=320 FAB_N0=24 \\',
  '      FAB_NMAX=48 FAB_RANK=4 FAB_DK=8 SIG_D=16 ENC_WARMUP=60 ENC_WARMUP_MIN=40 MEM_CAP=4000 \\',
  '      MEM_QUOTA=4000 RATE_EVERY=100000 CKPT_EVERY=0 PROFILE=0 GEN_N=0 COH_N=0 \\',
  '      TOKENIZER_PATH=/tmp/.../scratchpad/yourown.tok.json python3 self_organize.py',
  'Always give TOKENIZER_PATH a path you own and copy ckA.tok.pristine over it before resuming: a',
  'completed run SAVES its grown vocabulary back over that path, and a resume checks it matches.',
  '',
  'DO NOT WRITE ANYWHERE UNDER /home/user/LLM-Test/runs -- protected. Do not edit any repo file. Work',
  'read-only on the repo and write only under the scratchpad.',
  '',
  'WHAT THIS SESSION CHANGED (37401bd..271f875 on rm-predict): roughly forty edits across',
  'self_organize.py, memory.py, tokenizer.py, fetch_big.py, fetch_local.py, longrun.sh and the tests.',
  'Themes: a fabric/vocabulary widening restore with geometry refusals; restored-vs-new expert',
  'bookkeeping; growth-controller state in the checkpoint; per-corpus exposure guards; DN/CORP name',
  'realignment; cull and LR-boost budgets sized on the eligible set; ACCUM gated on backward passes;',
  'the SPECIALIZATION partition using the live router; _curve_by_step; MEM_WRONG_READ; several new DID',
  'IT FIRE rows and COUPLING lines; harness changes in longrun.sh (geometry inheritance, corpus top-up,',
  'PURE_ADD).',
  '',
  'ALREADY CONFIRMED FIRING IN A REAL RUN -- done, do not re-verify: fabric widening (5 of 5 tensors),',
  'VMAX widening (3 tensors), newborn partition, growth-controller restore and latch persistence,',
  'optimizer model/encoder split, census rebuild, RETENTION sign and old/new split, exposure table, the',
  'dead-quantile COUPLING line, the new banner knobs, the SPECIALIZATION partition fix (probe 20 vs run',
  '19), memory.wrong_block row, tokenizer.mint_rescued, ACCUM step counts, the cap-shrink / FAB_RANK /',
  'FAB_DK / missing-cap refusals, the missing-cent absentee warning, the DROPPED-domain realignment,',
  'both exposure warnings, GROW_CAP_FAB0-below-population, and the cull budget (18 vs 8 removed).',
].join('\n')

phase('Audit')

const FIND = {
  type: 'object', required: ['findings'],
  properties: {
    findings: { type: 'array', items: {
      type: 'object', required: ['what', 'status', 'evidence'],
      properties: {
        what: { type: 'string' },
        status: { type: 'string', enum: ['NEVER_EXECUTES', 'UNREACHABLE_AT_DEFAULTS', 'EXECUTES_BUT_WRONG', 'FINE'] },
        evidence: { type: 'string' },
        why_it_matters: { type: 'string' },
        fix: { type: 'string' },
      } } },
    summary: { type: 'string' },
  },
}

const out = await parallel([

  () => agent(CTX + '\n\n' + [
    'YOUR TASK. Find code added THIS SESSION that can NEVER execute, or never at the defaults. This is a',
    'coverage audit of my own work, held to the standard the project applies to everything else: a',
    'mechanism that runs and does nothing is a defect, and so is a guard nothing can trip.',
    '',
    'One instance was already found by running it: a GROW_CAP_FAB0 refusal that was unreachable because a',
    'checkpoint restore raised the cap before the guard judged it. Assume there are more.',
    '',
    'Concentrate on self_organize.py. For each NEW guard, warning, refusal, DID IT FIRE row or COUPLING',
    'line added this session, work out the exact condition and ask: at the registry defaults, and at what',
    'longrun.sh actually launches, can it ever be true? Check at least:',
    '  - every SystemExit added on the resume path',
    '  - the WIDENING CLOSED THE CAPACITY GATE warning and its can-the-gate-reopen condition',
    '  - PER-CORPUS RESAMPLING / WHOLE-RUN REPETITION / EXPOSURE IMBALANCE',
    '  - the new DID IT FIRE rows: tokenizer.mint_reject, tokenizer.mint_rescued, tokenizer.mint_widen,',
    '    memory.wrong_block, lr.restart, lr.damp, lr.envelope',
    '  - the COUPLING line for WRITE_QUANTILE',
    '  - the declined-by-cap-or-FAB_NEW_FRAC growth reporting',
    '  - the probe-vs-run mismatch check in SPECIALIZATION',
    'Where you can settle it by RUNNING something, run it. FINE is a perfectly good answer; say so rather',
    'than inventing a problem.',
  ].join('\n'), { phase: 'Audit', label: 'reachability', schema: FIND }),

  () => agent(CTX + '\n\n' + [
    'YOUR TASK. Hunt for defects INTRODUCED by this session -- regressions, not omissions. Forty-odd edits',
    'went in fast, several on the resume path and inside the training loop. Two have already been caught',
    'this way: one flag gating two optimizers when only one had the problem, and a checkpoint restore',
    'overriding an explicit request. Look for more of that shape.',
    '',
    '  - widen_prefix: predicate is leading-dim-grew AND trailing-dims-match. Enumerate every tensor in the',
    '    model and fabric state dicts and find any where it does the WRONG thing rather than copying or',
    '    refusing. What about a 1-D tensor? One whose leading dim is coincidentally the cap but is not',
    '    slot-indexed?',
    '  - the restored-vs-new split: _ck_n = min(fab_cfg n, fab.cap) then fab.n_live = max(fab.n_live, _ck_n).',
    '    Any state where _ck_n exceeds the live count, or a slot below _ck_n is not actually restored?',
    '  - the growth-controller restore setattrs every saved key onto fabgrow. Is any saved key a CONFIG',
    '    value this run should own rather than inherit? Cross-check against PlateauGrowth.__init__.',
    '  - _curve_by_step: does the ACTIVE-only filter change any OTHER consumer of _CURVE?',
    '  - cull and LR-boost budgets on len(_elig): any path where _elig is empty and the max(1, ...) floor',
    '    now culls something it should not?',
    '  - MEM_WRONG_READ is read via os.environ at construction. Anything construct Memory before the',
    '    environment is set, or construct a second one that would disagree?',
    'Run what you can. FINE is a good answer where true.',
  ].join('\n'), { phase: 'Audit', label: 'regressions', schema: FIND }),

  () => agent(CTX + '\n\n' + [
    'YOUR TASK. The SHELL side. longrun.sh gained blocks this session that have never executed: geometry',
    'inheritance in pilot-add and in add, the corpus top-up guard, PURE_ADD, and the round18 note.',
    '',
    'You may RUN longrun.sh, but ONLY with OUT, PILOT_DIR and GRID_DIR under the scratchpad -- never at',
    'runs/. A checkpoint exists at .../scratchpad/ckA. fetch_local.py works offline; Hugging Face is',
    'unreachable here, so use local as the dataset argument wherever a fetch would happen.',
    '',
    '  1. Does the geometry-inheritance block in pilot-add actually read fab_cfg from a real checkpoint and',
    '     export FAB_N0 / FAB_NMAX / VMAX? What when the checkpoint is unreadable, or absent? set -u is on',
    '     -- check every expansion.',
    '  2. THE ONE I MOST WANT CHECKED: the three-field split, set -- with the helper output, then',
    '     _CKN=${1:-0}. What happens when the helper prints nothing, one field, or an error to stdout? And',
    '     critically: set -- REPLACES THE POSITIONAL PARAMETERS, and longrun.sh reads $1/$2/$3/$4 for its',
    '     subcommand arguments. Does anything after that block still need them?',
    '  3. The corpus top-up guard: du -sb, the 90% threshold, the _HAVE=0 reset. Missing directory? Empty?',
    '     More than requested?',
    '  4. PURE_ADD: does it set PHASE_SCHED correctly and does self_organize.py accept it?',
    '  5. Does bash -n pass, and does shellcheck (if available) flag anything new?',
    'Report each finding with the command you ran and its output.',
  ].join('\n'), { phase: 'Audit', label: 'shell', schema: FIND }),
])

const found = out.filter(Boolean)
log('audit: ' + found.length + '/3 returned')

phase('Refute')

const claims = found.flatMap(f => f.findings || []).filter(f => f.status !== 'FINE').slice(0, 8)
log('refuting ' + claims.length + ' non-FINE findings')

const verdicts = await parallel(claims.map(f => () =>
  agent(CTX + '\n\n' + [
    'REFUTE this. Default to refuted=true unless you can point at the exact line, or run a command, that',
    'makes it true. Run something if you can -- this container has torch and a working corpus.',
    '',
    '  WHAT:     ' + f.what,
    '  STATUS:   ' + f.status,
    '  EVIDENCE: ' + f.evidence,
    '  MATTERS:  ' + (f.why_it_matters || ''),
    '  FIX:      ' + (f.fix || '(none)'),
    '',
    'Failure modes that have caught this project repeatedly:',
    '  - real in the abstract but cannot occur at the values this code actually runs at',
    '  - the quoted evidence is a DIFFERENT line from the one that governs the behaviour',
    '  - the defect is a deliberate, documented state the report already explains',
    'Return refuted=true if it does not hold. Quote the governing line either way, and give the command you',
    'ran if you ran one.',
  ].join('\n'), { phase: 'Refute', label: 'refute:' + (f.what || '').slice(0, 24), schema: {
      type: 'object', required: ['refuted', 'governing_line'],
      properties: { refuted: { type: 'boolean' }, governing_line: { type: 'string' },
                    command: { type: 'string' }, better_fix: { type: 'string' }, note: { type: 'string' } } } })
    .then(v => (v ? { ...f, v } : null))
))

const confirmed = verdicts.filter(Boolean).filter(x => x.v.refuted === false)
const refuted = verdicts.filter(Boolean).filter(x => x.v.refuted === true)
log('confirmed ' + confirmed.length + ', refuted ' + refuted.length)

phase('Report')

const brief = await agent(CTX + '\n\n' + [
  'Write the report I will act on. Do not edit files.',
  '',
  'CONFIRMED after adversarial review:',
  JSON.stringify(confirmed.map(c => ({ what: c.what, status: c.status, fix: c.v.better_fix || c.fix, line: c.v.governing_line, cmd: c.v.command })), null, 2),
  '',
  'REFUTED -- I must not act on these:',
  JSON.stringify(refuted.map(c => ({ what: c.what, why: c.v.governing_line })), null, 2),
  '',
  'EVERYTHING THE AUDITORS RETURNED, including FINE:',
  JSON.stringify(found, null, 2),
  '',
  'Produce:',
  '  1. A plain YES or NO: is HEAD 271f875 safe to run the next real experiment on? Then the reasoning.',
  '  2. Every edit still needed, priority order, anchor text and replacement, in the project comment style',
  '     -- explain WHY, cite the concrete failure, never restate what the line does.',
  '  3. Anything from this session that can never execute, named explicitly, and whether to make it',
  '     reachable or remove it. A guard nothing can trip is worse than no guard: it reads as coverage.',
  '  4. What is genuinely still unverified, listed honestly and without padding.',
  'Be decisive. Where evidence does not settle a question, say so in one line and make the call anyway.',
].join('\n'), { phase: 'Report', label: 'brief', effort: 'high' })

return { confirmed: confirmed.length, refuted: refuted.length, brief, findings: found }
