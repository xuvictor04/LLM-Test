export const meta = {
  name: 'fabric-resume-widening',
  description: 'Make a fabric resume across a changed FAB_NMAX correct, and find what else breaks when cap grows',
  phases: [{ title: 'Diagnose' }, { title: 'Verify' }, { title: 'Synthesize' }],
}

const CTX = `
REPO /home/user/LLM-Test, branch rm-predict. Autonomous continual-learning ML research system. Core
discipline: the DID IT FIRE audit. The recurring bug class is a mechanism that RUNS AND DOES NOTHING, a
quantity expressed in one unit and consumed in another, or DATA THAT IS RECORDED AND NEVER READ.
NEVER report a claim you have not verified by running a command or quoting a specific file:line. If you
cannot verify something, label it UNVERIFIED. torch is NOT installed in this container, so you cannot
import self_organize.py -- work from the source text, and say so rather than pretending you ran it.

THE PROJECT'S TWO GOALS, which decide what "correct" means here:
  A  good language production
  B  continual learning without catastrophic forgetting -- the architecture is a preallocated low-rank
     expert population ("the Fabric") whose modularity is supposed to let NEW AREAS get NEW EXPERTS while
     old ones are preserved. Extra modalities are meant to be strapped on the same way.

WHAT JUST HAPPENED. The user resumed a checkpoint trained with FAB_N0=256 FAB_NMAX=1024 into a run that
did not set either, so it used the registry defaults FAB_N0=2048 FAB_NMAX=4096. Command:
    FETCH_ARGS="--data-dir data/python" RESUME_FROM=runs/fix/fix_resume \\
      bash longrun.sh pilot-add py bigcode/the-stack-dedup
It printed three [resume] bookkeeping lines and then died:
    RuntimeError: Error(s) in loading state_dict for Fabric:
      size mismatch for A: copying a param with shape [1024, 768, 8] from checkpoint,
        the shape in current model is [4096, 768, 8].
      ... same for B, SRC_p, K_p, cent

FACTS I HAVE ALREADY ESTABLISHED (do not re-derive; you may falsify):
  - Fabric.__init__ (self_organize.py ~line 1455): s.r = FAB_RANK; cap = max(n0, FAB_NMAX); s.cap = cap;
    s.n_live = n0. The cap-shaped tensors are exactly five: A [cap,d,r], B [cap,r,d], SRC_p [cap,dk],
    K_p [cap,dk], and the BUFFER cent [cap,sig_d]. halt_key and halt_b are cap-independent.
  - Tensors are PREALLOCATED to cap and growth only advances n_live; the comment at ~1450 says slots exist
    so that "the tensors never change identity, only n grows", and unused rows are zero in B, i.e. exact
    identities. So a smaller-cap checkpoint is naturally a PREFIX of a larger-cap fabric.
  - The checkpoint ALREADY records what was needed to catch this before the crash: "fab_cfg" holds
    {"n", "rank", "cap", "dk", "alpha", "max_steps", "hid_mult", "min_steps", "norm_only", "society",
    "grounded", "route_t", "route_learn", "ens_k", "halt_on", "halt_max"} (save site ~line 4788).
    Nothing reads cap/rank/dk on the restore path.
  - The WORLD MODEL path (~line 4145) already does this correctly for ITS population: it detects the size
    mismatch, grows to match, and raises SystemExit naming WORLD_NMAX when it cannot. The fabric -- the
    larger and more important population -- has no equivalent.
  - Restore site ~line 4099: fab.n_live = max(fab.n_live, min(int(_RD["fab_cfg"]["n"]), fab.cap)).
    fab.n_live is FAB_N0 at that point. With FAB_N0=2048 and a checkpoint holding n<=1024, the max()
    keeps 2048 -- so >=1024 freshly-initialised RANDOM slots become "live".
  - The three backfill loops that follow (fab.born, fab.uage, fab.use) iterate range(fab.n_live) and treat
    any slot missing from the checkpoint dict as "an old checkpoint that did not record this", filling it
    conservatively as EXPERIENCED: born=0, uage=FAB_GRACE, use=population mean. The user's log shows
    exactly this: "1525 of 2048 experts had no recorded birth step", "1813 of 2048 ... no recorded
    UTILIZATION -- backfilled to the population mean 383.45". So had the shapes matched, the resume would
    have presented ~1525 untrained random experts as mature veterans at mean utilization. The crash
    prevented a silently worse outcome.
`

phase('Diagnose')

const FINDINGS = {
  type: 'object', required: ['findings'],
  properties: {
    findings: { type: 'array', items: {
      type: 'object', required: ['title', 'detail', 'severity', 'evidence'],
      properties: {
        title: { type: 'string' }, detail: { type: 'string' },
        severity: { type: 'string', enum: ['blocker', 'major', 'minor', 'note'] },
        evidence: { type: 'string', description: 'file:line and the quoted line, or a command and its output' },
        fix: { type: 'string' },
      } } },
    summary: { type: 'string' },
  },
}

const diag = await parallel([

  () => agent(`${CTX}

YOUR TASK. WHAT ELSE BREAKS WHEN fab.cap GROWS ACROSS A RESUME? Assume we implement a widening restore:
the checkpoint's cap=1024 rows are copied into the first 1024 rows of a cap=4096 fabric, the rest left at
their initialisation, and n_live handled separately.

Find everything ELSE in the codebase that is sized by, indexed by, or derived from fab.cap / FAB_NMAX and
would therefore be inconsistent after such a restore. Search self_organize.py, memory.py, world_model.py.
Check at least:
  - MAX_DOMAINS, which the registry mirrors to FAB_NMAX ("MAX_DOMAINS": ("FAB_NMAX",) in the _SPEC follows
    table, and line ~596). If the run's FAB_NMAX is 4096 but the checkpoint's domains were assembled under
    a cap of 1024, what happens to the restored domain state (asm.cent, asm.born, asm.act, asm.rad)?
  - the optimizer param-group replay right below the fabric load (~line 4174): _regrown, add_param_group,
    and whether a widened fabric changes the group structure the checkpoint's optimizer state expects.
  - MEM_OWNERS / n_own, which is min(FAB_NMAX, MEM_OWNERS) at ~line 4350, and anything in memory.py keyed
    by owner id.
  - the SOCIETY / chain structures, and anything holding a per-slot list, set or dict sized at startup.
  - the DID IT FIRE report's fabric rows, and _F0.cap at ~line 5233.
Report each as a finding with file:line and the quoted line. Do NOT edit any file.`,
    { phase: 'Diagnose', label: 'cap-fanout', schema: FINDINGS }),

  () => agent(`${CTX}

YOUR TASK. THE BOOKKEEPING BACKFILL CANNOT TELL TWO DIFFERENT SITUATIONS APART, and I want the full
consequence traced. Read self_organize.py lines ~4098-4140 carefully.

The three loops fill fab.born / fab.uage / fab.use for every slot in range(fab.n_live) that the checkpoint
dict does not mention. The comments justify the CONSERVATIVE direction -- unknown means EXPERIENCED, never
a protected newborn -- and that is right for a slot that existed in the checkpoint written by an older
build that did not record the field. It is exactly WRONG for a slot that never existed in the checkpoint
at all, which is what FAB_N0 > checkpoint n produces.

Trace what a mislabelled NEW slot actually causes downstream. Be specific and quote code:
  - born=0: which code reads fab.born, and what does "born at step 0" buy or cost a random slot? Find the
    cull's newborn exemption and any age-based protection.
  - uage=FAB_GRACE: find FAB_GRACE's readers. What does being past grace mean for culling and for the
    per-expert LR schedule (FAB_LR_CYCLE / FAB_LR_GAMMA / FAB_LR_AMIN / FAB_LR_OWN)? Does a random,
    untrained slot get put on the MATURE low learning rate, i.e. can it ever train up?
  - use=population mean: find the utilization cull's ranking and the FAB_PRESSURE gate. Does a random slot
    at mean utilization displace a TRAINED expert in the cull ranking? Work out the direction.
Then state, in one paragraph, what this does to goal B specifically: a resume that adds capacity for a new
area fills that capacity with slots that are simultaneously untrained and protected as veterans.
Do NOT edit any file.`,
    { phase: 'Diagnose', label: 'backfill', schema: FINDINGS }),

  () => agent(`${CTX}

YOUR TASK. DESIGN THE WIDENING RESTORE, precisely enough to implement from. Do NOT edit any file; return
the design and the exact code.

Requirements:
  1. Growing cap (checkpoint 1024 -> run 4096) must SUCCEED by prefix-copy. This is not a workaround; it is
     what goal B needs -- adding a modality should be able to add capacity. Give the exact code that copies
     each of A, B, SRC_p, K_p, cent from the checkpoint tensor into the first ck_cap rows of the live
     parameter, under torch.no_grad(), leaving the remainder at its initialisation. Note cent is a BUFFER,
     not a Parameter -- say whether that changes the code.
  2. SHRINKING cap (checkpoint 4096 -> run 1024) must REFUSE, loudly, naming FAB_NMAX, because it would
     discard trained experts. Write the exact SystemExit message. Model it on the WORLD_NMAX one at ~4145.
  3. A changed FAB_RANK or FAB_DK is NOT wideable -- A is [cap,d,r] and rank is the inner dimension, so a
     prefix copy is meaningless. Say what must happen and write that message too.
  4. D_MODEL changing must also refuse. Check whether the model load above would already catch it and say
     whether a separate check earns its place.
  5. The check must run BEFORE load_state_dict and BEFORE the bookkeeping backfill, so the failure names a
     knob instead of dumping five tensor shapes, and so the backfill never runs against a geometry that is
     about to be rejected. Give the exact insertion point by line number and the surrounding anchor text.
  6. State what should be PRINTED on the success path, so a widened resume is visible in the log rather
     than silent. This project's standard is that a mechanism which silently does something different is
     the defect it exists to catch.
Give complete, copy-pasteable code with the project's comment style: explain WHY, cite the concrete failure,
no restating of what the line does.`,
    { phase: 'Diagnose', label: 'design', schema: {
      type: 'object', required: ['design', 'code'],
      properties: { design: { type: 'string' }, code: { type: 'string' },
                    insertion_point: { type: 'string' }, messages: { type: 'string' },
                    caveats: { type: 'string' } } } }),

  () => agent(`${CTX}

YOUR TASK. THE HARNESS SIDE. Read the pilot-add arm of /home/user/LLM-Test/longrun.sh (search "pilot-add)")
and the round18 note (search "ROUND 18").

The user ran the exact command round18 documents and it died on a geometry mismatch. Answer:
  1. Which fabric knobs does pilot-add set, and which does it leave to the registry defaults? List them
     with the values that result. Compare against the round18 grid arm "fix_resume" (search fix_resume) --
     which sets FAB_N0=256 FAB_NMAX=1024 VMAX=2048 -- and enumerate EVERY knob where the two disagree.
     VMAX matters too: pilot-add sets VMAX=2048 and fix_resume sets VMAX=2048, so check whether that one
     actually agrees.
  2. Should pilot-add INHERIT the geometry from the checkpoint it resumes, or should it keep its own and
     rely on self_organize.py refusing? Argue both sides in two sentences each, then pick one. Consider:
     this project's standing rule is that a mechanism which silently does something other than what was
     asked is the defect class it exists to catch -- but also that a resume whose geometry cannot differ
     from the source run can never ADD CAPACITY for the new area, which is the point of the exercise.
  3. If pilot-add should read the checkpoint, how? It is a bash script and ckpt.pt is a torch pickle. Give
     a concrete, working mechanism -- e.g. a tiny python3 -c that loads with map_location="meta" or
     weights_only=True and prints fab_cfg. Say what it costs on a multi-GB checkpoint and whether there is
     a cheaper path. Verify what you can without torch and label the rest UNVERIFIED.
  4. There is a separate observation in the user's output: the grid guard refused to reuse
     runs/fix/fix_cadence.log because the stored corpus fingerprint b60013305n1ha489b9659660 differs from
     the current b70813307n2ha489b9659660 -- note "n1" vs "n2", which looks like the number of corpora
     changing from 1 to 2. Find the code that builds that fingerprint (search for where the .cfg sidecar is
     written and compared) and confirm or refute that reading. Say whether the guard behaved correctly.
Do NOT edit any file.`,
    { phase: 'Diagnose', label: 'harness', schema: {
      type: 'object', required: ['answer'],
      properties: { answer: { type: 'string' }, knob_diff: { type: 'string' },
                    recommendation: { type: 'string' }, fingerprint: { type: 'string' } } } }),
])

const d = diag.filter(Boolean)
log(`diagnose: ${d.length}/4 returned`)

phase('Verify')

const claims = [...(d[0]?.findings || []), ...(d[1]?.findings || [])].slice(0, 8)
log(`adversarially verifying ${claims.length} claims`)

const verdicts = await parallel(claims.map(f => () =>
  agent(`${CTX}

A previous agent claims this. REFUTE IT. Default to refuted=true unless you can point at the exact line
that makes it true. torch is unavailable, so verify by reading and quoting source, not by running the model.

  TITLE:    ${f.title}
  DETAIL:   ${f.detail}
  SEVERITY: ${f.severity}
  EVIDENCE: ${f.evidence}
  FIX:      ${f.fix || '(none)'}

Two failure modes that have caught this project before:
  - the defect is real in the abstract but cannot occur at the values this code actually runs at
  - the quoted evidence is a DIFFERENT line from the one that governs the behaviour
Return refuted=true if it does not hold. Quote the governing line either way.`,
    { phase: 'Verify', label: `refute:${f.title.slice(0, 26)}`, schema: {
      type: 'object', required: ['refuted', 'governing_line'],
      properties: { refuted: { type: 'boolean' }, governing_line: { type: 'string' },
                    note: { type: 'string' }, better_fix: { type: 'string' } } } })
    .then(v => (v ? { ...f, v } : null))
))

const confirmed = verdicts.filter(Boolean).filter(x => x.v.refuted === false)
const refuted = verdicts.filter(Boolean).filter(x => x.v.refuted === true)
log(`confirmed ${confirmed.length}, refuted ${refuted.length}`)

phase('Synthesize')

const brief = await agent(`${CTX}

Write the IMPLEMENTATION BRIEF I will execute literally. Do not edit files.

CONFIRMED (each independently reproduced by a second agent):
${JSON.stringify(confirmed.map(c => ({ title: c.title, severity: c.severity, detail: c.detail, fix: c.v.better_fix || c.fix, line: c.v.governing_line })), null, 2)}

REFUTED -- do not act on these:
${JSON.stringify(refuted.map(c => ({ title: c.title, why: c.v.governing_line })), null, 2)}

WIDENING RESTORE DESIGN:
${JSON.stringify(d[2], null, 2)}

HARNESS ANALYSIS:
${JSON.stringify(d[3], null, 2)}

Produce, in priority order:
  1. Every edit to self_organize.py, with the anchor text to match and the replacement, in the project's
     comment style (explain WHY, cite the concrete failure, never restate what the line does).
  2. The decision on n_live and the born/uage/use backfill: how to partition RESTORED slots from NEW slots
     and what each should get. Be explicit that these are opposite conservative directions.
  3. Whether longrun.sh's pilot-add should change, and exactly how.
  4. The tests, and which file. Existing suites: corpus_test.py, tok_test.py, ramp_test.py, lr_test.py,
     blowup_test.py, curve_test.py, compare_test.py, mem_evict_test.py, harness_test.sh, notes_check.py,
     levers.py. torch is unavailable here, so say precisely how to test a widening restore WITHOUT torch --
     note that corpus_test.py's last section execs the ACTUAL source text of a block against a stub
     namespace, and say whether that technique transfers.
  5. Anything that must be said in the round18 note so the next person running that command is not
     surprised.
Be decisive. Where evidence does not settle a question, say so in one line and make the call anyway.`,
  { phase: 'Synthesize', label: 'brief', effort: 'high' })

return { confirmed: confirmed.length, refuted: refuted.length, brief, design: d[2], harness: d[3] }
