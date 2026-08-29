export const meta = {
  name: 'p1-spine-p2-census',
  description: 'Finish the P1 spine (derive/wire/assemble/rng + ownership and determinism tests) and run the P2 lever census over all 328 knobs',
  phases: [
    { title: 'Spine' },
    { title: 'Assemble' },
    { title: 'Tests' },
    { title: 'Census' },
    { title: 'Review' },
  ],
}

const ROOT = '/home/user/LLM-Test'

const CTX = [
'PROJECT: ' + ROOT + ', branch rm-predict-DC. A ground-up rebuild of an autonomous continual-learning ML',
'research system. TWO DEFINITIVE GOALS and nothing else is definitive:',
'  A. good language production, with room for additional modalities to be strapped on later',
'  B. continual learning without catastrophic forgetting',
'Every measured number is a SIGNAL, not a fact. Never state a result as definitive.',
'',
'WHAT ALREADY EXISTS AND MUST NOT BE CHANGED (read these first; they define the contract you build against):',
'  src/spine/units.py     Clock kinds (Steps, Flushes, Windows, Backwards, Epochs, Selections) that raise',
'                         UnitError across kinds; plus unit METADATA constants (BYTES, TOKENS, FRACTION...).',
'  src/spine/lever.py     Lever(default, help, unit, choices) + LeverSet (PREFIX; env name GENERATED as',
'                         PREFIX_FIELD) + Config (frozen, attribute access, _wire()/_freeze()).',
'                         LeverSet.from_env() is the ONLY code in the tree allowed to name os.environ.',
'  src/spine/registry.py  Import-time collection; refuses two owners for one PREFIX or one env name;',
'                         unread_env() is the typo net.',
'',
'READ THE PLAN at ' + ROOT + '/.rework/PLAN.md -- section 4 (the lever rule L1/L2/L3) and section 2 (the',
'twelve grafts). Read ' + ROOT + '/.rework/DECISIONS.md for the binding owner rulings.',
'',
'HOUSE STYLE, non-negotiable. This codebase is ~37% comments and the comments carry the knowledge:',
'  - Every non-obvious decision carries a comment saying WHY, and where a real defect motivated it the',
'    comment states that defect concretely, with numbers where they exist.',
'  - Comments explain the failure that would occur without the code, not what the code does.',
'  - No emoji. No decorative banners beyond a short === marker. Plain English.',
].join('\n')

const WRITE = [
'Write the file with the Write tool. Then VERIFY it: run python3 against it (imports, plus a small smoke',
'exercise of every public function) and iterate until it runs clean. Report what you verified.',
'Use sys.path.insert(0, "' + ROOT + '/src") to import the spine. Do not modify files outside your assignment.',
].join('\n')

phase('Spine')

const SPINE = [
  { key: 'derive', label: 'src/spine/derive.py', prompt: [
'Write ' + ROOT + '/src/spine/derive.py.',
'',
'ONE PURE NAMED FUNCTION PER DERIVED QUANTITY, each carrying its unit, and NOTHING ELSE in the module. The',
'rule this enforces: a value computed from more than one lever exists in exactly one place with one name,',
'and no consumer recomputes it. The old tree recomputed bytes-per-token in three places with three',
'estimators, and picked a signature width from one whose error changes SIGN with vocabulary size.',
'',
'Read ' + ROOT + '/.rework/oracle/*.json -- known-answer tables captured from the SHIPPED old code for',
'cull_gate_open, lift_to, pin_tick, bwt_of, forgetting_of, curve_verdict, blowup_stale and _phases. Your',
'implementations MUST reproduce those tables exactly. They are the oracle.',
'',
'Functions to provide, at minimum:',
'  cull_gate_open(n_live, slots, pressure) -> bool   reproduce the oracle exactly. Its old docstring records',
'        that n_live <= 2 is a FLOOR, not a pressure test, and that three mechanisms went silently',
'        unreachable behind this gate.',
'  operating_population(pressure, slots) -> int      pressure IS a setpoint: the population equilibrates at',
'        pressure x slots. This is an IRREDUCIBLE coupling and the docstring must say so -- it is the',
'        example the plan uses for why lever independence is stated as three testable properties instead.',
'  lift_to(cap, frac, floor) -> int                  reproduce the oracle exactly.',
'  bytes_per_token(n_bytes, n_tokens) -> float       MEASURED, len(bytes)/len(tokens). Not a vocabulary mean',
'        over entries -- that estimator changes sign of error with vocabulary size.',
'  signature_width_bytes(win_tokens, bytes_per_token) -> int   the ONE signature width, computed once.',
'        CONFIRMED DEFECT it replaces: the old _eval_sig sliced the last max(1, SIG_WIN) bytes with SIG_WIN',
'        defaulting to 0, so every eval-path routing decision was made on ONE BYTE while training used 614.',
'        Same knob, same zero, opposite meanings in two places.',
'  flush_period(period_steps, batch_w) -> Flushes    Steps to Flushes, the conversion that bit repeatedly:',
'        pin_tick counted flushes against a threshold declared in steps, 16x slow at BATCH_W=16. Take and',
'        return the Clock types from spine.units; do not take or return bare ints.',
'  accum_due(n_backward, accum) -> bool              accumulation counts BACKWARD PASSES. Gating on a window',
'        counter accumulated nothing: measured 55 optimizer steps where 13 were due.',
'  bwt_of(now, prev) -> float                        POSITIVE = WORSE = FORGETTING on a lower-is-better',
'        metric. Reproduce the oracle. This subtraction was inverted once, on the single line the',
'        continual-learning claim rests on, and the test only checked that the WORDS appeared in the log.',
'  forgetting_of(now, best) -> float                 clipped at zero; reproduce the oracle.',
'',
'Every function is PURE: no os.environ, no lever imports, no globals, no I/O. Each docstring states its',
'UNIT IN and UNIT OUT explicitly.',
'',
WRITE,
'Additionally write a check that loads each oracle JSON and asserts your implementation reproduces every',
'case. Report the case counts.',
  ].join('\n') },

  { key: 'wire', label: 'src/spine/wire.py', prompt: [
'Write ' + ROOT + '/src/spine/wire.py.',
'',
'THE COUPLING LEDGER. A value one package owns and another genuinely needs is not read across a boundary;',
'it is WIRED, and every wire is a recorded edge, so the complete coupling graph is a printable list.',
'',
'Provide:',
'  class Wire   frozen record of (src, dst, value, why, unit). src is "prefix.lever" of the OWNER; dst is',
'      "prefix.d_name" of the RECEIVER; why is required and must be a non-empty sentence.',
'  class Wires  the ledger. add() appends and returns the value; all(); graph(); render() prints a table;',
'      and affects(env_name) implements GRAFT G1:',
'          affects(L) = union of {owner(L)} and {owner(d) for every wire d whose src is L}',
'      COMPUTED from the ledger, never hand-declared. This is the oracle the L3 isolation sweep tests',
'      against, and the design review found that a hand-written affects list makes the sweep permanently',
'      green for that lever -- the oracle would be written by the same person whose leak it must catch.',
'  WIRE_BUDGET = 25, enforced on add(). A budget is a speed bump, not the guarantee; say so in the comment.',
'      The load-bearing check lives in tests/test_ownership.py: every wire destination must be a d_-prefixed',
'      field on the receiving Config, and every d_ field must correspond to a declared wire.',
'',
'The d_ prefix is GRAFT G5: any value computed from more than one package"s own levers is written to a d_-named',
'field, so a plain grep for d_ enumerates every coupling in the system with no tooling. Explain in the module',
'docstring why the prefix survives the rename: the WIRE assigns the destination name, so a coupling cannot',
'arrive under a local name that looks owned.',
'',
WRITE,
  ].join('\n') },

  { key: 'rng', label: 'src/spine/rng.py', prompt: [
'Write ' + ROOT + '/src/spine/rng.py.',
'',
'PER-SUBSYSTEM RANDOMNESS, HANDED OUT EXPLICITLY. Provide an Rng factory seeded from (seed, subsystem name)',
'so each subsystem draws from its own stream, plus frozen_rng() saving and restoring global state.',
'',
'WHY THIS MATTERS HERE SPECIFICALLY, and say it in the docstring: the L3 isolation sweep flips one lever and',
'asserts nothing outside that one lever"s computed affects() set changes. If every subsystem draws from ONE',
'global stream, changing how many draws subsystem A makes shifts every later draw in subsystem B, and the',
'sweep reports a coupling that is an artifact of the RNG rather than of the levers. Per-subsystem streams are',
'what make the sweep meaningful. This is a real recorded failure class here: a diagnostic that drew from the',
'global stream moved the run.',
'',
'Provide rng_for(subsystem, seed), fingerprint() returning a cheap integer digest of a stream state (used by',
'the isolation sweep), and frozen_rng() covering python random, numpy if present and torch if present -- each',
'guarded so the module imports with none of them installed.',
'',
WRITE,
  ].join('\n') },
]

const spineResults = await parallel(SPINE.map(s => () => agent(
  CTX + '\n\n=== YOUR ASSIGNMENT: ' + s.label + ' ===\n\n' + s.prompt,
  { label: 'spine:' + s.key, phase: 'Spine' })))

log('spine modules written: ' + spineResults.filter(Boolean).length + '/' + SPINE.length)

phase('Assemble')

const assembleOut = await agent(CTX + '\n\n' + [
'=== YOUR ASSIGNMENT: ' + ROOT + '/src/spine/assemble.py ===',
'',
'THE ONLY FILE IN THE TREE PERMITTED TO IMPORT MORE THAN ONE PACKAGE LeverSet. Everything else receives its',
'own Config as a parameter, so reading a foreign lever is a NameError at author time rather than a policy.',
'',
'Read src/spine/wire.py and src/spine/derive.py (just written) and src/spine/lever.py first.',
'',
'Provide:',
'  build(environ=None, sets=None) -> (configs, wires, warnings)',
'      Resolve every registered LeverSet from the environment; run every declared wire, writing each into',
'      the receiving Config as a d_-prefixed field via Config._wire(); freeze every Config; return the',
'      typo-net warnings from registry.unread_env(). No Config may be mutated after freeze. build() runs',
'      exactly once, at startup.',
'',
'  A WIRES table as DATA, not scattered calls -- a module-level list of wire declarations that build() walks,',
'      so the coupling graph can be printed without running the system. Seed it with couplings the survey',
'      actually found, each with a real reason, and mark which are IRREDUCIBLE. At least:',
'        fabric.slots -> domains.d_expert_slots   the domain id namespace is bounded by the slot pool',
'        fabric.pressure x fabric.slots -> fabric.d_operating_population   IRREDUCIBLE: pressure is a',
'             setpoint, so the population equilibrates at pressure x slots and cannot be independent of it',
'        memory.owners x memory.quota -> memory.d_capacity   capacity is DERIVED; the old tree silently',
'             discarded a requested MEM_CAP of 200000 at 8192 because cap came from the partition',
'        tok.vmax -> lm.d_softmax_width   emb.weight and head.weight have exactly this many rows',
'      Add others you can justify from ' + ROOT + '/.rework/survey/*.json, each with a real reason. If you',
'      cannot name a real reason it is NOT a wire -- it is a lever the receiving package should own.',
'',
'  render(configs, wires) -> str   the printable coupling graph for docs/03_WIRING.md, with irreducible',
'      couplings separated and their reasons shown.',
'',
'The design review finding you must answer IN THE CODE: wires can launder couplings, because once',
'fabric.slots arrives in domains as a local named expert_slots the read site looks like an owned value',
'again. The d_ prefix is the answer and the wire assigns the name; make that structural, not advisory.',
'',
WRITE,
'Write a smoke test that declares two toy LeverSets, wires between them, and asserts: the d_ field appears',
'on the receiver; a non-d_ destination is refused; affects() is computed correctly; and the budget bites.',
].join('\n'), { label: 'spine:assemble', phase: 'Assemble' })

phase('Tests')

const TESTS = [
  { key: 'ownership', label: 'tests/test_ownership.py', prompt: [
'Write ' + ROOT + '/tests/test_ownership.py -- the STATIC half of the lever rule (L1 and L2 in',
'.rework/PLAN.md section 4). Pure AST over src/**/*.py. Must run in under a second with no torch and no GPU,',
'because it runs on every edit.',
'',
'Assert at least:',
'  O1  os.environ / os.getenv is named in EXACTLY ONE file: src/spine/lever.py. Report every other',
'      occurrence with file:line. The old tree read TOK_MINT_PMIN and TOK_MINT_GATE_K straight from',
'      os.environ inside tokenizer.py, invisible to the registry and to every audit built on it.',
'  O2  every Lever default is an ast.Constant. A computed default is a WIRE and must be declared as one.',
'  O3  no module outside src/spine/assemble.py references more than one LeverSet subclass.',
'  O4  every d_-prefixed attribute read anywhere in src/ corresponds to a wire declared in the WIRES table,',
'      AND every declared wire destination is read somewhere. Both directions: a declared coupling that does',
'      not exist fails, and a coupling that is not declared fails.',
'  O5  no module-level mutable global in one module is assigned by another.',
'  O6  every wire has a non-empty reason.',
'  O7  clock kinds are never compared against bare int literals in src/.',
'',
'Print PASS/FAIL per check with counts and exit non-zero on failure. For EACH check, state in a comment what',
'it CANNOT catch. The design review found that all-AST enforcement proves only that a module cannot NAME a',
'foreign lever, and is blind to coupling through shared mutable state, RNG draw order or the data. That is',
'why L3 exists and is behavioural. Do not overclaim.',
'',
WRITE,
'Run it against the current tree and report what it finds. It is EXPECTED to pass on a tree containing only',
'the spine; say that plainly rather than presenting a vacuous pass as a result.',
  ].join('\n') },

  { key: 'determinism', label: 'tests/test_determinism.py', prompt: [
'Write ' + ROOT + '/tests/test_determinism.py -- GRAFT G2. It must exist BEFORE the isolation sweep, because',
'it establishes the number that sweep compares against.',
'',
'THE POINT: two identical seeded runs on this machine, diffed, establish the MEASURED float noise floor. The',
'L3 isolation sweep flips one lever and asserts nothing outside its computed affects() set changed -- and',
'without a measured floor it would either assume zero and report noise as a coupling, or pick a tolerance out',
'of the air. This project already has "machine non-determinism invalidates every commit-to-commit comparison"',
'in its record.',
'',
'The mechanism packages do not exist yet, so build the harness to work NOW on what exists and extend later',
'without change:',
'  - a pluggable run callable producing a dict of INTEGER fingerprints per subsystem (integers, because the',
'    sweep must not itself be subject to float tolerance);',
'  - plus a float channel for genuinely continuous quantities, where the floor is a measured tolerance;',
'  - run twice with the same seed, diff, and WRITE the measured floor to tests/_noise_floor.json with the',
'    machine identity beside it (platform, cpu count, torch version if present) -- a floor measured on one',
'    machine says nothing about another;',
'  - refuse to write a floor from fewer than 2 repeats, and say so.',
'',
'For now supply a synthetic reference workload exercising spine.rng and spine.derive so the harness is',
'demonstrably working, and mark with a clear comment where the real training run plugs in at P3.',
'',
WRITE,
'Run it and report the measured floor.',
  ].join('\n') },
]

const testResults = await parallel(TESTS.map(t => () => agent(
  CTX + '\n\n=== YOUR ASSIGNMENT: ' + t.label + ' ===\n\n' + t.prompt,
  { label: 'test:' + t.key, phase: 'Tests' })))

phase('Census')

const CENSUS_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['family', 'entries'],
  properties: {
    family: { type: 'string' },
    entries: { type: 'array', items: {
      type: 'object', additionalProperties: false,
      required: ['old_name','old_default','verdict','new_owner','new_name','unit','purpose','reason','couples_with'],
      properties: {
        old_name: { type: 'string' },
        old_default: { type: 'string' },
        verdict: { type: 'string', enum: ['keep','rename','merge','drop','promote-to-wire'] },
        new_owner: { type: 'string' },
        new_name: { type: 'string' },
        unit: { type: 'string' },
        purpose: { type: 'string' },
        reason: { type: 'string' },
        couples_with: { type: 'array', items: { type: 'string' } },
      } } },
  },
}

const FAMILIES = [
  { key: 'fabric', n: 82, note: 'the expert population, routing, growth, cull, exploration, crossover' },
  { key: 'misc', n: 40, note: 'the 40 knobs filed under misc -- most belong to a real owner; find it' },
  { key: 'domains', n: 36, note: 'the self-assembling partition, merge/cull/fold, signatures' },
  { key: 'memory', n: 24, note: 'the editable store: gate, eviction, floor, probation, wrongness' },
  { key: 'tokenizer', n: 22, note: 'the online byte-BPE and its minting gates' },
  { key: 'encoder', n: 17, note: 'the contrastive signature encoder' },
  { key: 'report', n: 16, note: 'report/eval knobs -- under the new architecture these belong to eval' },
  { key: 'data', n: 14, note: 'corpus, stream construction, phase schedule, held-out split' },
  { key: 'optim', n: 13, note: 'LR schedule, restarts, accumulation, per-expert rates' },
  { key: 'world', n: 11, note: 'the world model. OWNER RULING D4: it STAYS and OFF must be first-class' },
  { key: 'plumbing', n: 8, note: 'device, paths, checkpointing' },
  { key: 'capacity', n: 5, note: 'the earned-capacity valve' },
]

const census = (await parallel(FAMILIES.map(f => () => agent(CTX + '\n\n' + [
'=== YOUR ASSIGNMENT: the P2 lever census for the "' + f.key + '" family (' + f.n + ' knobs) ===',
'',
ROOT + '/self_organize.py holds _SPEC on lines 96-513: 328 knobs, each tagged with a family comment.',
'Extract every knob tagged with the family comment "' + f.key + '" -- ' + f.note + '.',
'',
'For EACH knob decide one verdict:',
'  keep              carries over as a lever with the same meaning',
'  rename            carries over under a clearer name in its owning package (give new_name)',
'  merge             folded into another lever (say which, in reason)',
'  drop              does not carry over. A REAL reason is required.',
'  promote-to-wire   it was never a lever -- it is a value another package owns, arriving as a wire',
'',
'Assign new_owner as a package PREFIX from: FAB, MEM, TOK, LM, SIG, DOM, DATA, OPT, CAP, WORLD, CKPT, EVAL,',
'RUN. A knob tagged misc or report almost certainly has a real owner -- find it.',
'Assign a unit from src/spine/units.py metadata constants, or a clock kind name if it is a cadence.',
'',
'EVIDENCE, NOT RECOLLECTION. For each knob, grep self_organize.py (and memory.py, tokenizer.py,',
'world_model.py) for its actual reads and decide from what the code does. Cross-check against',
ROOT + '/.rework/survey/*.json (558 lever records with owner/effect/coupling analysis) and',
ROOT + '/.rework/ISSUES.md.',
'',
'DROPPING IS THE POINT AND ALSO THE RISK. The owner asked for unnecessary material filtered out, and also',
'ruled that a mechanism never observed to fire is NOT thereby proven useless -- several were provably inert',
'because the INSTRUMENT was broken, not the mechanism. Drop a knob when it is genuinely superfluous: a',
'duplicate, a knob for a mechanism being removed, a knob nothing reads. Do NOT drop one merely because the',
'report never showed it firing. Say which case you are in, in reason.',
'',
'BINDING OWNER RULINGS (' + ROOT + '/.rework/DECISIONS.md):',
'  D1 the Fabric STAYS.  D2 PURE_ADD is the DEFAULT continual-learning protocol.',
'  D3 the reservoir memory quota is now the DEFAULT; the old signal-not-a-wall rule is a selectable arm.',
'  D4 the world model STAYS and must be cleanly switchable off.',
'',
'Set family to "' + f.key + '". Be exhaustive: every knob in your family must appear exactly once.',
].join('\n'), { label: 'census:' + f.key, phase: 'Census', schema: CENSUS_SCHEMA })))).filter(Boolean)

const total = census.reduce(function (n, c) { return n + (c.entries || []).length }, 0)
const byVerdict = {}
for (const c of census) for (const e of c.entries || []) byVerdict[e.verdict] = (byVerdict[e.verdict] || 0) + 1
log('census: ' + total + ' knobs classified across ' + census.length + ' families -- ' +
    Object.keys(byVerdict).map(function (k) { return k + ' ' + byVerdict[k] }).join(', '))

phase('Review')

const REVIEW_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['verdict', 'findings'],
  properties: {
    verdict: { type: 'string', enum: ['sound', 'sound-with-fixes', 'not-sound'] },
    findings: { type: 'array', items: {
      type: 'object', additionalProperties: false,
      required: ['severity', 'where', 'problem', 'fix'],
      properties: {
        severity: { type: 'string', enum: ['critical','high','medium','low'] },
        where: { type: 'string' }, problem: { type: 'string' }, fix: { type: 'string' },
      } } },
  },
}

const LENSES = [
'Try to DEFEAT the lever rule. You are an engineer who wants to read another package lever without the tests',
'noticing. Find every way: a local alias, a wire that launders the coupling, a value passed through a third',
'module, a module-level mutable global, an import cycle, monkeypatching, a default that is secretly computed,',
'reading through Config.keys() or wired(), a subclass. For each, say whether O1-O7 or the wire ledger actually',
'stops it. Report the ones that get through.',
].join(' ')

const LENS2 = [
'Hunt for THIS PROJECT OWN BUG CLASSES in the new spine code: a guard whose condition cannot be satisfied; a',
'mechanism armed but never reachable; a counter recorded and never read; a quantity produced in one unit and',
'consumed in another; state destroyed silently. The author already wrote one untrippable guard in registry.py',
'-- a duplicate-PREFIX check disabled by comparing __module__ alone -- and a test caught it. Assume there are',
'more. Check the oracle reproduction in derive.py especially: does it assert EVERY case, or a subset?',
].join(' ')

const LENS3 = [
'Judge the CENSUS below against .rework/survey/*.json and the old _SPEC. Find: knobs dropped without a real',
'reason; knobs dropped for the FORBIDDEN reason (the report never showed it firing -- the owner ruled that is',
'not proof, because the instrument was broken); knobs assigned to the wrong owner; couples_with lists that are',
'obviously incomplete; and any knob among the 328 that is MISSING from the census entirely. A missing knob is',
'the worst outcome: a lever that vanishes without a decision is exactly what the owner asked to prevent.',
].join(' ')

const censusText = census.map(function (c) {
  return '## ' + c.family + '\n' + (c.entries || []).map(function (e) {
    return e.old_name + ' [' + e.old_default + '] -> ' + e.verdict + ' ' + e.new_owner + '.' + e.new_name +
           ' (' + e.unit + ') :: ' + e.reason
  }).join('\n')
}).join('\n\n')

const ALL_LENSES = [LENSES, LENS2, LENS3]

const reviews = (await parallel(ALL_LENSES.map(function (lens, i) {
  return function () {
    return agent(CTX + '\n\n=== YOU ARE AN ADVERSARIAL REVIEWER (' + (i + 1) + ' of 3) ===\n\n' + lens +
      '\n\nRead the actual files: src/spine/*.py and tests/test_ownership.py, tests/test_determinism.py. Run' +
      ' them. Try to break them. Default to reporting a problem when uncertain -- a false alarm costs a check,' +
      ' a missed leak costs the guarantee.\n\n' +
      (i === 2 ? '=== THE CENSUS UNDER REVIEW ===\n' + censusText.slice(0, 90000) : ''),
      { label: 'review:' + (i + 1), phase: 'Review', schema: REVIEW_SCHEMA })
  }
}))).filter(Boolean)

const crit = reviews.reduce(function (a, r) {
  return a.concat((r.findings || []).filter(function (f) { return f.severity === 'critical' || f.severity === 'high' }))
}, [])
log('review: ' + reviews.map(function (r) { return r.verdict }).join(', ') + ' -- ' + crit.length + ' critical/high')

return {
  spine: spineResults.filter(Boolean).length,
  assemble: !!assembleOut,
  tests: testResults.filter(Boolean).length,
  census: { families: census.length, knobs: total, byVerdict: byVerdict },
  censusData: census,
  reviews: reviews,
}
