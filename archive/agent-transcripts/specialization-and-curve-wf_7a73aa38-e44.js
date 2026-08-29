export const meta = {
  name: 'specialization-and-curve',
  description: 'Do SPECIALIZATION and the LM-curve verdict measure what they claim under PHASED?',
  phases: [{ title: 'Investigate' }, { title: 'Refute' }, { title: 'Report' }],
}

const CTX = `
REPO /home/user/LLM-Test, branch rm-predict, HEAD 3478465. Autonomous continual-learning ML research
system. Core discipline is the DID IT FIRE audit; the recurring bug class is a mechanism that RUNS AND
DOES NOTHING, a quantity in one unit consumed in another, or data recorded and never read.

torch is NOT installed here. You cannot import self_organize.py. Work from source text and quote
file:line for every claim. Label anything unverified as UNVERIFIED. A confident wrong answer is far
worse than "I could not check this". Do NOT edit any file.

GOALS, which decide what "correct" means:
  A  good language production
  B  continual learning without catastrophic forgetting, via a modular low-rank expert population whose
     modularity should let new areas get new experts while old ones are preserved.

GROUND TRUTH from the first run that ever crossed a run boundary
(/root/.claude/uploads/e880caf7-1208-58de-93fd-49c41549bf70/f7e98f65-pilot_gru_py.log -- READ IT):
  eng was 2.096 -> now 2.139, +0.043 +/- 0.075, HELD. py 1.932, NEW this run. BWT +0.0431.
  2 processes (eng, py), PHASED=1, PHASE_SCHED 0|0|1|1, EPOCHS=8, 448 live experts of cap 1024.
  The run reported: "population (2 experts blended) 2.296 bits/byte | best single rank-slot (modal
  holder node 451) 2.269 | population buys -0.027" and ">> NOT AGGREGATE: the best single expert does
  as well as the whole blend, so the population is redundant here. Expect this while the nodes are
  interchangeable." It also reported "CAN A DOMAIN PREDICT? ... NOT YET: the partition does not beat a
  single global histogram".
`

phase('Investigate')

const ANS = {
  type: 'object', required: ['verdict', 'evidence'],
  properties: {
    verdict: { type: 'string', enum: ['REAL_DEFECT', 'WORKS_AS_CLAIMED', 'MEASURES_SOMETHING_ELSE', 'UNVERIFIABLE'] },
    evidence: { type: 'string', description: 'file:line plus quoted lines' },
    detail: { type: 'string' },
    fix: { type: 'string', description: 'concrete code, or "none needed"' },
    caveats: { type: 'string' },
  },
}

const out = await parallel([

  () => agent(`${CTX}

YOUR TASK. The SPECIALIZATION report. I have previously claimed it "measures ensemble difficulty rather
than isolated per-node competence, so 'INTERCHANGEABLE in 32 arms' may be answering a weaker question".
That claim is MINE and unverified. Establish whether it is true.

Find the section (grep for SPECIALIZ, "INTERCHANGEABLE", "population buys", "modal holder"). Then:
  1. Quote exactly what it computes. What is "population (N experts blended)"? What is "best single
     rank-slot"? Is the single-expert figure obtained by running that expert ALONE on the material, or by
     some ablation/lesion of the ensemble, or by reading a per-expert statistic already collected?
  2. If it is an ablation: an ablated ensemble is not an isolated expert. Say precisely what the
     difference is and in which direction it biases the verdict.
  3. Does the comparison hold the ROUTING fixed? If the single expert is scored on material the router
     sent to the whole population, that is a different question again.
  4. Given goal B: the claim under test is that a new area gets its OWN experts. What measurement would
     actually answer that -- per-expert competence on per-DOMAIN material, with the domain labels the
     run already has? Is the data to do it already collected (fab.use, fab.comp, fab.contrib, asm.*,
     the per-domain held-out probe)? Quote what exists.
  5. Verdict: REAL_DEFECT / WORKS_AS_CLAIMED / MEASURES_SOMETHING_ELSE, and a concrete fix if the first
     or third. If my claim is wrong, say so plainly -- that is the more useful answer.`,
    { phase: 'Investigate', label: 'specialization', schema: ANS }),

  () => agent(`${CTX}

YOUR TASK. The LM-curve verdict chain under PHASED. I have previously claimed it "collapses the
per-process curve to one arbitrary corpus under PHASED". That claim is MINE and unverified. Establish
whether it is true.

Find it: grep for "LEARNING CURVE", "curve_verdict", CURVE_RISE_BLEWUP, CURVE_FLAT, CURVE_TOK_RISE, and
the per-process rows printed as "process N: 2.12A 2.37. ...".
  1. The table is per-process. What does the VERDICT consume -- the per-process series, a mean, or one
     process's series? Quote the code that selects it.
  2. Under PHASED with 2+ corpora each process is ACTIVE only part of the time (the A/. markers). If the
     verdict reads a single series that includes ABSENT windows, what does "rise since min" mean when
     the rise is just the process being absent? Work through the run's actual numbers: process 0 goes
     2.12A 2.37. 2.63. 2.72. -- a +0.60 rise across three ABSENT windows.
  3. Does curve_verdict get called with data that can distinguish "absent" from "diverging"? Quote the
     call site and what it passes.
  4. The run printed "mean change per 2000 steps while ACTIVE +0.261 (learning)" and "while ABSENT
     -0.126 (forgetting)" and concluded "it LEARNS faster than it forgets". Check that arithmetic's
     sign convention against the RETENTION section directly above it, which uses the OPPOSITE convention
     (there, positive means forgetting). Two adjacent sections using opposite sign conventions on the
     same quantity is exactly the class of thing this project treats as a defect. Is that what is
     happening, or do they genuinely measure different things?
  5. Verdict and a concrete fix. If my claim is wrong, say so plainly.`,
    { phase: 'Investigate', label: 'curve', schema: ANS }),

  () => agent(`${CTX}

YOUR TASK. Two smaller things, both previously reported by me and neither verified.

(a) THE QUANTILE WRITE GATE. I claimed it is "unreachable at defaults with no DID IT FIRE row". Find it
    (grep memory.py and self_organize.py for quantile, QUANT, surprise gate, write gate, WRITE_Q). Work
    out the exact condition, evaluate it at the registry defaults, and say whether it can ever fire.
    Check whether any DID IT FIRE row covers it. If it is unreachable, is that a defect or a deliberate
    OFF state -- and does the report say which? Quote the code.

(b) ACCUM BELOW THE BATCH EARLY-OUT. I claimed ACCUM is the last modulo cadence sitting below the batch
    early-out, harmless at ACCUM=1 but wrong in bench_gpu.sh which ships ACCUM=2, where "half the flush
    residues never call om.step()". Verify or refute. Find the early-out (grep for "len(_bx) < BATCH_W"),
    find every remaining `% ` cadence below it, and specifically find how ACCUM gates om.step(). Then
    answer: at ACCUM=2 with BATCH_W=16, which flush steps actually call om.step()? Is the gradient
    silently discarded, or merely accumulated further? Those are very different severities -- be precise
    about which, with the code.

Give a verdict for each and a concrete fix where warranted. If either claim is wrong, say so plainly.`,
    { phase: 'Investigate', label: 'gate-accum', schema: ANS }),
])

const inv = out.filter(Boolean)
log(`investigate: ${inv.length}/3 returned`)

phase('Refute')

const claims = inv.filter(x => x.verdict === 'REAL_DEFECT' || x.verdict === 'MEASURES_SOMETHING_ELSE')
log(`refuting ${claims.length} positive verdicts`)

const verdicts = await parallel(claims.map((f, i) => () =>
  agent(`${CTX}

REFUTE this. Default to refuted=true unless you can point at the exact line that makes it true.

  VERDICT:  ${f.verdict}
  DETAIL:   ${f.detail}
  EVIDENCE: ${f.evidence}
  FIX:      ${f.fix}

Failure modes that have caught this project before:
  - real in the abstract but cannot occur at the values this code actually runs at
  - the quoted evidence is a DIFFERENT line from the one that governs the behaviour
  - the "defect" is a deliberate, documented OFF state that the report already explains
Quote the governing line either way. If the proposed fix is wrong, say what the right one is.`,
    { phase: 'Refute', label: `refute:${(f.detail || '').slice(0, 24)}`, schema: {
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

ALL THREE INVESTIGATIONS:
${JSON.stringify(inv, null, 2)}

CONFIRMED after adversarial review:
${JSON.stringify(confirmed.map(c => ({ detail: c.detail, fix: c.v.better_fix || c.fix, line: c.v.governing_line })), null, 2)}

REFUTED -- I must NOT act on these, and should stop repeating them:
${JSON.stringify(refuted.map(c => ({ detail: c.detail, why: c.v.governing_line })), null, 2)}

Produce:
  1. For EACH of my four standing claims -- SPECIALIZATION measures the wrong thing; the LM-curve verdict
     collapses under PHASED; the quantile write gate is unreachable and unreported; ACCUM sits below the
     batch early-out -- a one-line TRUE / FALSE / PARTLY, then the evidence. Be blunt where I was wrong.
  2. For each TRUE one: the exact edit, with anchor text and replacement, in the project's comment style
     (explain WHY, cite the concrete failure, never restate what the line does).
  3. Tests, and to which file. torch is unavailable, so say how. Note that resume_test.py and
     corpus_test.py exec the ACTUAL source text of a block against a stub namespace, and say whether
     that technique transfers to each.
  4. Ranked by what actually matters for goal B, given the run has now produced BWT +0.043 and the open
     questions are whether the new area got its own experts and whether the report can tell.
Be decisive. Where evidence does not settle it, say so in one line and make the call anyway.`,
  { phase: 'Report', label: 'brief', effort: 'high' })

return { confirmed: confirmed.length, refuted: refuted.length, brief, investigations: inv }
