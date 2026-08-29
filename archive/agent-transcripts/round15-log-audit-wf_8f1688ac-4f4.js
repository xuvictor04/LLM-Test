export const meta = {
  name: 'round15-log-audit',
  description: 'Deep-read each round15 schedule arm log for anomalies, then adversarially verify each claim',
  phases: [
    { title: 'Read', detail: 'one agent per arm log, structured extraction + anomaly hunt' },
    { title: 'Verify', detail: 'adversarial check of every anomaly claimed' },
  ],
}

const DIR = '/root/.claude/uploads/e880caf7-1208-58de-93fd-49c41549bf70'
const ARMS = [
  { arm: 'sched_ctl',  file: DIR + '/1a3ef30f-sched_ctl.log',  adds: 'nothing (control)' },
  { arm: 'sched_step', file: DIR + '/6cb29092-sched_step.log', adds: 'LR_STEPS=100000' },
  { arm: 'sched_warm', file: DIR + '/fffb6d5a-sched_warm.log', adds: 'LR_SHIFT_WARM=4000' },
  { arm: 'sched_both', file: DIR + '/f26bdcd2-sched_both.log', adds: 'LR_STEPS=100000 LR_SHIFT_WARM=4000' },
]

const READ_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['arm', 'held_out', 'd_order1', 'final_step', 'final_vocab', 'final_pop', 'lifts',
             'epoch2_curve', 'cross_check_verdict', 'blew_up_alarm', 'anomalies'],
  properties: {
    arm: { type: 'string' },
    held_out: { type: 'string', description: 'final held-out bits/byte, verbatim from the log' },
    d_order1: { type: 'string', description: 'the "beats order-1 by +X" number, or NONE if absent' },
    final_step: { type: 'string' },
    final_vocab: { type: 'string', description: 'e.g. 2048/2048' },
    final_pop: { type: 'string', description: 'e.g. 3795/8192' },
    lifts: { type: 'string', description: 'count of [capacity @ ...] lines, and the improving values quoted in each expert lift' },
    epoch2_curve: { type: 'string', description: 'the per-process learning-curve values immediately BEFORE and AFTER the epoch-2 boundary near step 38576, at least 3 probes each side' },
    lr_at_boundaries: { type: 'string', description: 'the lr and % of peak reported on each [epoch N/8 ...] line' },
    cross_check_verdict: { type: 'string', description: 'the full UNIT-STABLE CROSS-CHECK line and the >> verdict line that follows it' },
    blew_up_alarm: { type: 'string', description: 'the "!! BLEW UP @" line if present, else NONE' },
    coupling_lines: { type: 'string', description: 'any [config] COUPLING line mentioning LR, verbatim' },
    lr_rewarm_lines: { type: 'string', description: 'count and first two of any "[lr @ N] epoch resample -> re-warming" lines, else NONE' },
    anomalies: {
      type: 'array',
      description: 'anything surprising, self-contradictory, or that looks like a bug. Empty array if none.',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['what', 'evidence', 'why_it_matters'],
        properties: {
          what: { type: 'string' },
          evidence: { type: 'string', description: 'verbatim log lines with step numbers' },
          why_it_matters: { type: 'string' },
        },
      },
    },
  },
}

const VERDICT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['real', 'reasoning'],
  properties: {
    real: { type: 'boolean', description: 'true only if the log genuinely supports the claim' },
    reasoning: { type: 'string' },
    correction: { type: 'string', description: 'if not real, what the log actually says' },
  },
}

phase('Read')

const results = await pipeline(
  ARMS,
  (a) => agent(
    `Read the training log at ${a.file}. It is large; use grep/rg and targeted reads rather than reading it whole.

This is arm "${a.arm}" of a 4-arm controlled experiment. All four arms are identical except: this one adds ${a.adds}. STREAM_LEN=25000000, EPOCHS=8.

Context you need:
- LR_STEPS sets the cosine LR wavelength in STEPS instead of deriving it from LR_EPOCHS(=8 epochs).
- LR_SHIFT_WARM=4000 re-warms the LR over 4000 steps after each epoch resample.
- Every prior run in this project was destabilised at the epoch-2 boundary near step 38576. That is THE thing to look at.
- The per-process learning curve is a line beginning "process 0:" containing many values suffixed with "A". Probes are every 2000 steps starting at 2000. Pick the row with the most "A" values.
- "[capacity @ N] experts pinned ..." lines are capacity-valve lifts and quote an "improving" value.
- A "!! BLEW UP @" line means the run lost >0.5 bits/byte from its best.

Extract every field of the schema verbatim from the log. Do not compute or infer values that the log states directly.

Then hunt for anomalies: mechanisms that are armed but did nothing, banner lines that contradict what actually ran, counters in the wrong units, sections that failed with an exception, values that contradict each other, anything printed that looks like a bug. Check the DID IT FIRE table. Report only things you can quote log lines for.`,
    { label: 'read:' + a.arm, phase: 'Read', schema: READ_SCHEMA }
  ),
  (r) => {
    if (!r || !r.anomalies || !r.anomalies.length) return { report: r, verdicts: [] }
    return parallel(r.anomalies.slice(0, 3).map((an) => () =>
      agent(
        `Adversarially verify this claim about the log ${ARMS.filter(x => x.arm === r.arm)[0].file}.

CLAIM: ${an.what}
EVIDENCE OFFERED: ${an.evidence}
WHY IT SUPPOSEDLY MATTERS: ${an.why_it_matters}

Your job is to REFUTE it. Go back to the log and check the quoted lines actually exist and actually say what is claimed. Check whether an innocent explanation fits: an expected default, a section that is off by configuration, a value that is fine in context, a misread of units. Default to refuted=true when uncertain. Only return real=true if the log unambiguously supports the claim.`,
        { label: 'verify:' + r.arm, phase: 'Verify', schema: VERDICT_SCHEMA }
      ).then((v) => ({ anomaly: an, verdict: v }))
    ))
      .then((vs) => ({ report: r, verdicts: vs.filter(Boolean) }))
  }
)

const clean = results.filter(Boolean)
log(`read ${clean.length} arm logs`)

return {
  arms: clean.map((c) => ({
    report: c.report,
    confirmed_anomalies: (c.verdicts || []).filter((v) => v.verdict && v.verdict.real).map((v) => ({
      what: v.anomaly.what, evidence: v.anomaly.evidence, reasoning: v.verdict.reasoning,
    })),
    refuted_anomalies: (c.verdicts || []).filter((v) => v.verdict && !v.verdict.real).map((v) => ({
      what: v.anomaly.what, correction: v.verdict.correction || v.verdict.reasoning,
    })),
  })),
}
