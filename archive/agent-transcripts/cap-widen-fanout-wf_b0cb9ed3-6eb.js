export const meta = {
  name: 'cap-widen-fanout',
  description: 'Audit everything sized by FAB_NMAX that a widened-fabric resume could leave inconsistent',
  phases: [{ title: 'Audit' }, { title: 'Refute' }, { title: 'Report' }],
}

const CTX = `
REPO /home/user/LLM-Test, branch rm-predict, commit 63191a0. Autonomous continual-learning ML research
system. Core discipline is the DID IT FIRE audit; the recurring bug class is a mechanism that RUNS AND
DOES NOTHING, a quantity expressed in one unit and consumed in another, or DATA RECORDED AND NEVER READ.

torch is NOT installed here. You cannot import self_organize.py or load a checkpoint. Work from source
text. Quote file:line for every claim. Label anything you could not verify as UNVERIFIED. A confident
wrong answer is far worse than "I could not check this".

PROJECT GOALS, which decide what "correct" means:
  A  good language production
  B  continual learning without catastrophic forgetting. The architecture is a preallocated low-rank
     expert population (the "Fabric") whose modularity should let NEW AREAS get NEW EXPERTS while old
     ones are preserved; extra modalities are meant to be strapped on the same way.

WHAT WAS JUST SHIPPED (commit 63191a0) -- this is the change you are auditing the consequences of:
A resume may now WIDEN the fabric. Previously a checkpoint written at FAB_NMAX=1024 resumed into a run at
the default FAB_NMAX=4096 died inside torch with five tensor shapes. Now:
  - Fabric.__init__ does cap = max(FAB_N0, FAB_NMAX); the cap-shaped tensors are exactly A [cap,d,r],
    B [cap,r,d], SRC_p [cap,dk], K_p [cap,dk] and the BUFFER cent [cap,sig_d].
  - On resume, if the checkpoint's fab_cfg["cap"] is SMALLER than this run's fab.cap, each of those five
    is prefix-copied: this run's initialised tensor has rows 0..ck_cap-1 overwritten from the checkpoint
    and keeps its initialisation beyond that. Search self_organize.py for "THE WIDENING COPY".
  - A NARROWER checkpoint cap, or a changed FAB_RANK / FAB_DK, raises SystemExit naming the knob.
    Search for "FABRIC GEOMETRY: CHECKED BEFORE ANYTHING IS RESTORED".
  - Slots live here but absent from the checkpoint are entered as NEWBORNS (born=resume step, uage=0.0,
    use absent) rather than as veterans. Search for "RESTORED SLOTS AND NEW SLOTS NEED OPPOSITE".
  - On a widened resume the Adam moments are NOT restored, because exp_avg is shaped like its parameter
    and torch's Optimizer.load_state_dict does not validate shape -- it would load cleanly and fail on the
    first step(). Search for "A WIDENED FABRIC CANNOT TAKE THE OLD MOMENTS".

ALREADY CHECKED BY ME -- do not spend effort re-deriving, but you MAY falsify with evidence:
  - Fabric.grow() returns [] ("rows of EXISTING Parameters -- already in the optimizer"), so fabric growth
    never calls add_param_group; _regrown is fed by the WORLD MODEL replay only.
  - The five tensors above are the complete set of cap-shaped ones in Fabric; halt_key and halt_b are not.
`

phase('Audit')

const FIND = {
  type: 'object', required: ['findings'],
  properties: {
    findings: { type: 'array', items: {
      type: 'object', required: ['title', 'detail', 'severity', 'evidence'],
      properties: {
        title: { type: 'string' },
        detail: { type: 'string' },
        severity: { type: 'string', enum: ['blocker', 'major', 'minor', 'note'] },
        evidence: { type: 'string', description: 'file:line plus the quoted line' },
        fix: { type: 'string' },
      } } },
    summary: { type: 'string' },
  },
}

const audits = await parallel([

  () => agent(`${CTX}

YOUR TASK. Find everything OUTSIDE the Fabric class that is sized by, indexed by, derived from, or
compared against FAB_NMAX / fab.cap, and would therefore be inconsistent after a widened resume.

Start from these leads and then search beyond them -- grep for FAB_NMAX, fab.cap, .cap, MAX_DOMAINS:
  - MAX_DOMAINS. The _SPEC "follows" table maps it to FAB_NMAX, and line ~596 is
    MAX_DOMAINS = _i("MAX_DOMAINS", _i("FAB_NMAX", 4096)). The checkpoint restores domain state
    (asm.cent, asm.born, asm.act, asm.rad, asm._radp). If the checkpoint's domains were assembled under a
    cap of 1024 and this run allows 4096, what actually goes wrong -- or is it benign? Answer either way
    with the code that decides it.
  - MEM_OWNERS / n_own, around line ~4350: min(FAB_NMAX, MEM_OWNERS) when MEM_PER_EXPERT. Read memory.py
    for anything keyed or sized by owner id, and say what a changed owner count does to a restored store.
  - The DID IT FIRE report and the config table: _F0.cap, and the row that computes
    fab.n() - _i("FAB_N0", 2048). With FAB_N0 now inherited from the checkpoint by longrun.sh's pilot-add,
    does that row still report what its label claims?
  - SOCIETY / chain structures and anything holding a per-slot list, set, dict or tensor allocated at
    startup from cap.

For each: is it BENIGN under widening, or a real inconsistency? Say which, and why, with the line that
decides it. Do not report something as broken without the line that makes it broken. Do NOT edit files.`,
    { phase: 'Audit', label: 'cap-fanout', schema: FIND }),

  () => agent(`${CTX}

YOUR TASK. Audit the NEW code itself, adversarially. It was written and tested in one sitting by the same
person who wrote the bug it fixes. Read, in self_organize.py:
  - the block starting "# ---- FABRIC GEOMETRY: CHECKED BEFORE ANYTHING IS RESTORED"
  - the block starting "RESTORED SLOTS AND NEW SLOTS NEED OPPOSITE"
  - the block starting "THE WIDENING COPY"
  - the "A WIDENED FABRIC CANNOT TAKE THE OLD MOMENTS" block in part 2 of the resume

Hunt specifically for:
  1. Ordering. Does the geometry gate really run before EVERY consumer of the old geometry? Is there any
     read of fab.cap, fab.n_live, fab.born/uage/use between the gate and the widening copy that sees an
     inconsistent intermediate state?
  2. Scope. _wide_by is assigned in two places (beside _regrown, and inside the gate) and read in part 2
     of the resume. Trace every path through main() and confirm it cannot be unbound or stale. Check
     _ck_cap and _ck_n the same way -- where are they defined, and is every read guarded?
  3. The widening predicate. It skips a key when
     (_c is None or _v.shape == _c.shape or _v.dim() < 1 or _v.shape[1:] != _c.shape[1:] or
      _v.shape[0] >= _c.shape[0]).
     Enumerate the cases. Is there any tensor for which this silently does the WRONG thing rather than
     either copying or refusing? What about a 1-D cap-shaped tensor, where shape[1:] is () on both sides?
  4. The unreconcilable-tensor check that follows it iterates _fsd and compares against _cur. Does it see
     keys present in _cur but ABSENT from the checkpoint, and should it?
  5. fab.n_live = max(fab.n_live, _ck_n). With longrun.sh now setting FAB_N0 from the checkpoint, is the
     max() still reachable, and is _new ever non-empty in practice? If it can never fire, say so -- an
     inert branch is this project's signature defect and should be reported, not defended.
  6. The newborn contract. Compare against Fabric.grow()'s actual tail: s.born[j], s.uage[j] = 0.0,
     s.use.pop(j), s.comp.pop(j), s.contrib.pop(j), s.n_live += 1, s.grown += 1. Does the resume path miss
     anything grow() does -- comp, contrib, grown, or anything else per-slot?
Report each as a finding with file:line. Do NOT edit files.`,
    { phase: 'Audit', label: 'new-code', schema: FIND }),

  () => agent(`${CTX}

YOUR TASK. Answer one question with arithmetic and code, for goal B: after this widened resume, is the
added area actually able to get its own experts?

The concrete run is: resume runs/fix/fix_resume (523 live experts, cap 1024) into pilot-add with
FAB_N0=523 inherited from the checkpoint and FAB_NMAX=4096, adding a Python corpus alongside English.

Work out from the source:
  1. Occupancy and the capacity gate. FAB_PRESSURE defaults to 0.45 and the utilization cull plus
     FAB_RESCUE live behind it -- the round18 logs say "the UTILIZATION cull did not run: 523/1024 = 0.51
     occupancy is below FAB_PRESSURE" style lines, so find the exact gate. At 523/4096 = 0.128 after
     widening, which mechanisms are now UNREACHABLE that were reachable at cap 1024? List them. Is making
     the cull unreachable good or bad for adding an area? Argue it.
  2. Growth. Find PlateauGrowth and the GROW_CAP valve, and the soft-cap lift condition (pinned AND
     plateaued). Starting from 523 live in a 4096 pool, what actually governs how fast the population can
     grow for the new corpus, and how many experts could realistically be added over the run's step count?
     pilot-add uses STREAM_LEN=4000000 EPOCHS=8, so derive the step count too.
  3. FAB_PRESSURE as a setpoint. This project has established that the population equilibrates at
     pressure x cap. At cap 1024 that is ~461; at cap 4096 it is ~1843. The checkpoint holds 523. Does
     widening therefore invite the population to nearly quadruple regardless of whether Python needs it?
     Find the code that makes pressure a setpoint and say whether that is a real risk here.
  4. Give a recommendation: for measuring what adding Python costs English, is FAB_NMAX=4096 right, or is
     something between 1024 and 4096 better? Give a number and the reasoning. State plainly if the
     evidence does not settle it.
Quote code for every claim. Do NOT edit files.`,
    { phase: 'Audit', label: 'goal-b', schema: {
      type: 'object', required: ['answer'],
      properties: { answer: { type: 'string' }, unreachable: { type: 'string' },
                    growth: { type: 'string' }, recommendation: { type: 'string' } } } }),
])

const a = audits.filter(Boolean)
log(`audit: ${a.length}/3 returned`)

phase('Refute')

const claims = [...(a[0]?.findings || []), ...(a[1]?.findings || [])]
  .filter(f => f.severity === 'blocker' || f.severity === 'major')
  .slice(0, 6)
log(`refuting ${claims.length} blocker/major claims`)

const verdicts = await parallel(claims.map(f => () =>
  agent(`${CTX}

REFUTE this claim. Default to refuted=true unless you can point at the exact line that makes it true.
torch is unavailable; verify by reading and quoting source.

  TITLE:    ${f.title}
  DETAIL:   ${f.detail}
  SEVERITY: ${f.severity}
  EVIDENCE: ${f.evidence}
  FIX:      ${f.fix || '(none)'}

Failure modes that have caught this project before:
  - real in the abstract, but cannot occur at the values this code actually runs at
  - the quoted evidence is a DIFFERENT line from the one that governs the behaviour
  - the claim describes pre-existing behaviour that the audited change did not introduce or alter
Return refuted=true if it does not hold. Quote the governing line either way.`,
    { phase: 'Refute', label: `refute:${f.title.slice(0, 24)}`, schema: {
      type: 'object', required: ['refuted', 'governing_line'],
      properties: { refuted: { type: 'boolean' }, governing_line: { type: 'string' },
                    note: { type: 'string' }, better_fix: { type: 'string' } } } })
    .then(v => (v ? { ...f, v } : null))
))

const confirmed = verdicts.filter(Boolean).filter(x => x.v.refuted === false)
const refuted = verdicts.filter(Boolean).filter(x => x.v.refuted === true)
log(`confirmed ${confirmed.length}, refuted ${refuted.length}`)

phase('Report')

const brief = await agent(`${CTX}

Write the report I will act on. Do not edit files.

CONFIRMED (each independently reproduced by a second agent):
${JSON.stringify(confirmed.map(c => ({ title: c.title, severity: c.severity, detail: c.detail, fix: c.v.better_fix || c.fix, line: c.v.governing_line })), null, 2)}

REFUTED -- do not act on these, but list them so I do not re-raise them:
${JSON.stringify(refuted.map(c => ({ title: c.title, why: c.v.governing_line })), null, 2)}

MINOR / NOTE findings not sent for refutation:
${JSON.stringify([...(a[0]?.findings || []), ...(a[1]?.findings || [])].filter(f => f.severity !== 'blocker' && f.severity !== 'major').map(f => ({ title: f.title, detail: f.detail, evidence: f.evidence })), null, 2)}

GOAL-B ANALYSIS:
${JSON.stringify(a[2], null, 2)}

Produce:
  1. Whether commit 63191a0 is SAFE TO RUN as it stands. A plain yes or no first, then the reasoning. If
     no, the single smallest change that makes it safe.
  2. Every edit still needed, in priority order, with anchor text and replacement, in the project's
     comment style: explain WHY, cite the concrete failure, never restate what the line does.
  3. Tests to add and to which file. torch is unavailable, so say precisely how. Note that resume_test.py
     and corpus_test.py both exec the ACTUAL source text of a block against a stub namespace, and say
     whether that technique transfers to each new test.
  4. The FAB_NMAX recommendation for the pilot-add run, as a number, with the reasoning in three sentences.
  5. Anything the round18 note must say so the next person is not surprised.
Be decisive. Where the evidence does not settle a question, say so in one line and make the call anyway.`,
  { phase: 'Report', label: 'brief', effort: 'high' })

return { confirmed: confirmed.length, refuted: refuted.length, brief, goalB: a[2] }
