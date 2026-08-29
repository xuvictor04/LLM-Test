export const meta = {
  name: 'corpus-too-small',
  description: 'Diagnose why fetch_local under-collects and design a reliable ungated corpus pull',
  phases: [
    { title: 'Diagnose' },
    { title: 'Verify' },
    { title: 'Synthesize' },
  ],
}

const REPO = '/home/user/LLM-Test'

const FINDINGS = {
  type: 'object',
  required: ['findings'],
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        required: ['title', 'detail', 'severity', 'evidence'],
        properties: {
          title: { type: 'string' },
          detail: { type: 'string' },
          severity: { type: 'string', enum: ['blocker', 'major', 'minor', 'note'] },
          evidence: { type: 'string', description: 'exact command run + exact output, or file:line' },
          fix: { type: 'string' },
        },
      },
    },
    summary: { type: 'string' },
  },
}

const ANSWER = {
  type: 'object',
  required: ['answer', 'evidence'],
  properties: {
    answer: { type: 'string' },
    evidence: { type: 'string' },
    numbers: { type: 'string' },
    caveats: { type: 'string' },
  },
}

const CTX = `
CONTEXT. Repo ${REPO}, branch rm-predict. This is an autonomous continual-learning ML research
system. Its core discipline is the "DID IT FIRE" audit: the recurring bug class is a mechanism that
RUNS AND DOES NOTHING, or a quantity expressed in one unit and consumed in another. Never report a
claim you have not verified by running something. If you cannot verify a claim, say so explicitly and
label it UNVERIFIED. A wrong confident answer is far worse than "I could not check this".

THE SITUATION. I just added fetch_local.py, which builds a Python corpus from source already on the
machine, so the continual-learning chain (train English -> ADD python -> re-measure English) can run
without a Hugging Face account. Both code presets in fetch_big.py are GATED and the run died on
"is a gated dataset on the Hub. You must be authenticated".

THE USER'S REPORT, verbatim: "There is an error of corpus size being too small, provide respective pull"
So fetch_local.py hit its own SHORT guard on their machine:
  [fetch_local] SHORT: X MB of the 30 MB asked for -- exits 1 unless --allow-short.
They want a pull that actually reaches the target.

WHAT I ALREADY ESTABLISHED IN THIS ENVIRONMENT (do not re-derive, but you may falsify):
  - huggingface.co is BLOCKED by this environment's network policy (curl returns 000, the agent proxy
    logs "gateway answered 403 to CONNECT"). So no HF dataset can be verified or fetched from here.
  - pypi.org and files.pythonhosted.org ARE reachable (HTTP 200; they are in the proxy's noProxy list).
  - "python3 -m pip download --no-deps --dest <dir> sympy" works here and pulled a 6.3 MB wheel at 56 MB/s.
  - This container's stdlib is only 11.0 MB of .py (637 files), so 0.03 GB is genuinely unreachable here.
  - site.getsitepackages() returns THREE paths here:
      /usr/local/lib/python3.11/dist-packages, /usr/lib/python3/dist-packages, /usr/lib/python3.11/dist-packages
    but fetch_local.roots_for() only consults sysconfig.get_paths() for stdlib/purelib/platlib, which
    here collapses to TWO. /usr/lib/python3/dist-packages -- where Debian and Ubuntu put system-installed
    packages, i.e. most ML boxes -- is never searched. Treat this as a lead to confirm, not as gospel.
`

phase('Diagnose')

const diagnostics = await parallel([

  // 1 -- root discovery across real-world Python layouts
  () => agent(`${CTX}

YOUR TASK. Audit fetch_local.py's ROOT DISCOVERY (the roots_for function) exhaustively. Read the file
first. The question is: on a real machine, which directories holding real Python source does it FAIL to
look in? Enumerate concretely, and verify what you can by running python3 here.

Cover at least: Debian/Ubuntu dist-packages layout (the three site.getsitepackages() entries), user
site (site.getusersitepackages()), virtualenv and venv layouts, conda/mamba environments, pyenv,
Homebrew python, a --user pip install, multiple interpreters installed side by side (python3.10 and
python3.12 both present), and the repository's own source tree. For each: state the exact path pattern,
whether roots_for currently reaches it, and how to discover it portably from inside Python.

Also check the INTERACTION with SKIP_DIRS = {"test","tests","__pycache__",".git","node_modules",
".mypy_cache",".pytest_cache","idle_test","lib2to3",".venv","venv"}. Two specific things to test by
running code, not by reading: (a) does pruning "test"/"tests" remove a large fraction of a real
site-packages tree, and (b) can a SKIP_DIRS name ever appear as a component of a ROOT itself (e.g. a
venv at /home/u/venv/lib/python3.11/site-packages) and does os.walk then prune anything it should not?

Report each distinct problem as a finding with the exact evidence (command + output, or file:line).
Propose a concrete fix for each. Do NOT edit any file.`, { phase: 'Diagnose', label: 'roots', schema: FINDINGS }),

  // 2 -- collection/write logic
  () => agent(`${CTX}

YOUR TASK. Audit fetch_local.py's COLLECTION AND WRITE path for defects -- everything after roots_for:
collect(), the dedup, the shuffle, the shard loop, the SHORT guard. Read the file, then TEST by running
it and by writing small scripts against fixtures in
/tmp/claude-0/-home-user-LLM-Test/e880caf7-1208-58de-93fd-49c41549bf70/scratchpad.

Specific things to check, each by execution:
  - collect() reads and decodes EVERY candidate file into memory before a single byte is written. What
    is the peak RSS if the roots hold 2 GB of .py? Measure the ratio on a real tree here and extrapolate.
    Is this a real risk on an ML box with a big site-packages?
  - The size printed as "found N unique files, X MB" is computed with len(txt.encode()) + len(SEP), but
    the writer writes txt.strip() + SEP. Do these two numbers agree? If they disagree, the SHORT guard
    and the "found" line are measuring different things. Prove it with a case.
  - Shard rollover: "if written // (SHARD_MB * 1_000_000) > shard". Compare against fetch_big.py's
    identical-looking loop. Is the FIRST shard boundary correct? Can a shard be skipped or double-opened?
  - Is the corpus format truly byte-identical in structure to what fetch_big.py writes and what
    datastream.open_corpus expects? Read datastream.py to confirm how part*.txt files are ordered and
    concatenated, and whether >1 shard changes anything.
  - The dedup: blake2b of raw bytes. Does that catch the actual duplication in a real site-packages
    (vendored copies that differ by a version string)? Measure the exact duplicate rate on a real tree.
  - The break condition "if written >= target: break" sits at the TOP of the loop. Does the final corpus
    overshoot the target by up to one document? Does that matter?
  - Encoding: files that are valid UTF-8 but contain a BOM, or NUL bytes. What happens downstream?

Report each distinct problem as a finding with exact evidence. Propose a fix for each. Do NOT edit files.`,
    { phase: 'Diagnose', label: 'collect', schema: FINDINGS }),

  // 3 -- how big does the corpus ACTUALLY need to be?
  () => agent(`${CTX}

YOUR TASK. Answer, from the code and with arithmetic shown: HOW MANY BYTES of the second corpus does the
round18 resume leg actually need, and is 0.03 GB the right ask?

Read the pilot-add arm of ${REPO}/longrun.sh (search "pilot-add)") and trace every environment variable
it sets into ${REPO}/self_organize.py and ${REPO}/datastream.py. The command under test is:
    RESUME_FROM=runs/fix/fix_resume bash longrun.sh pilot-add py local 0.03

Work out precisely:
  - How the training stream is built from the corpora: STREAM_LEN, EPOCHS, DOMAINS="eng,py", SEG_MIN,
    SEG_MAX, SEG_CONTIG, CORPUS_CAP, DISK_STREAM, WIN, BATCH_W. How many BYTES of the py corpus does one
    epoch actually consume? Show the arithmetic.
  - VAL_FRAC: how much of the py corpus is held out and never trained on, and what is the ABSOLUTE byte
    count of that held-out slice at 10 MB vs 30 MB? Is the held-out slice large enough for the
    MEMORIZATION CHECK and the ACROSS THE RUN BOUNDARY numbers to mean anything? Find any minimum-size
    guard in the eval path and quote it.
  - The 5000-byte per-corpus floor in self_organize.py: irrelevant here, but confirm.
  - What happens when the stream WRAPS -- i.e. the corpus is smaller than STREAM_LEN * EPOCHS. Find the
    cursor logic (_CUR, seg_from). Does the run silently re-read the same material? Does anything warn?
    There is a STREAM_LEN-vs-corpus-size startup warning somewhere in self_organize.py -- find it, quote
    it, and say whether it would fire at 10 MB with these settings.
  - The eng corpus in data_pilot is the OTHER half of DOMAINS="eng,py". How big is it, and does a large
    imbalance (60 MB eng vs 10 MB py) distort what "adding an area" measures? Look for any balancing.

Then give a direct recommendation: the smallest py corpus for which the round18 resume leg produces
trustworthy ACROSS THE RUN BOUNDARY / BWT / forgetting numbers, with the reasoning. Distinguish "the run
completes" from "the numbers mean something".`, { phase: 'Diagnose', label: 'sizing', schema: ANSWER }),

  // 4 -- design the PyPI pull
  () => agent(`${CTX}

YOUR TASK. Design and EMPIRICALLY VALIDATE a PyPI-based corpus pull: real Python source, no account, no
gated terms, reachable wherever pypi.org is.

Work in /tmp/claude-0/-home-user-LLM-Test/e880caf7-1208-58de-93fd-49c41549bf70/scratchpad/pypi.
Actually download things and measure. Budget your time; do not download more than ~300 MB total.

Answer with measured numbers:
  1. wheel vs sdist. "pip download --no-deps --only-binary :all:" vs "--no-deps --no-binary :all:".
     For 5-6 representative packages measure: download size, extracted .py bytes, file count, and
     whether tests are included. Which gives more real, diverse Python per MB downloaded? Note that
     sdists include tests (repetitive assertion boilerplate) and wheels usually do not.
  2. Platform-specific wheels. Does "--only-binary :all:" fail or produce a manylinux wheel for packages
     with C extensions (numpy, scipy, pandas)? Does that matter if we only extract .py? Test it.
  3. Which packages give the most DIVERSE real Python per MB? Measure candidates and rank them. Consider
     at least: sympy, django, ansible-core, twisted, scipy, pandas, matplotlib, scikit-learn, networkx,
     sphinx, ipython, tornado, aiohttp, flask, sqlalchemy, pydantic, rich, boto3, botocore, transformers,
     pygments, setuptools, pip. Explicitly flag ones that are mostly GENERATED or VENDORED code
     (botocore's data-driven clients, pip/_vendor, setuptools/_vendor, pygments lexers) -- a corpus of
     machine-generated Python is not the distribution we want to add, and this project cares about that
     distinction. Verify your claims by extracting and looking, not from memory.
  4. Propose a default package list that reliably yields >= 60 MB of extracted, deduplicated,
     non-generated .py, and state the MEASURED total for your list. Prefer breadth of authorship and
     style over raw size.
  5. Licensing: these are all OSI-licensed open source packages being used as a language-modelling
     corpus. Note any package in your list whose license is unusual (GPL, AGPL) so the user can decide.
     One line each; do not editorialise.
  6. Mechanics for the implementation: how to extract .py from a .whl (zip) and from an .sdist
     (tar.gz/zip) using only the standard library. Give working code you have RUN. Handle the case where
     pip is absent or "pip download" fails, and say what the fallback is.

Return the ranked list, the measured numbers, and the working extraction code.`,
    { phase: 'Diagnose', label: 'pypi', schema: ANSWER }),

  // 5 -- ungated HF options, honestly labelled
  () => agent(`${CTX}

YOUR TASK. The best corpus would still be a real code dataset. huggingface.co is BLOCKED from this
environment, so you CANNOT verify gating status by fetching. Confirm that block yourself first (try
curl and report the exact result) so we are certain, then work within it.

Produce a short table of CANDIDATE ungated Hugging Face code datasets the user could try on their own
machine, where fetch_big.py's pass-through already supports them:
    python3 fetch_big.py --dataset <id> --field <field> --domain py --gb 0.03 --out data_pilot

For each candidate give: the dataset id, the text field name, the config if any, roughly what it
contains, and your CONFIDENCE that it is ungated. Because you cannot verify, mark EVERY row UNVERIFIED
and say plainly at the top that none of this was checked against the Hub. Do not present recall as fact.
This project's standard is that an unverified claim is labelled, not laundered.

Also read ${REPO}/fetch_big.py and answer concretely:
  - Does the pass-through path (--dataset owner/name --field content) work for a dataset that is NOT in
    PRESETS? Quote the code that handles it.
  - Does it need --config for datasets that have one, and what happens if you omit it? Quote the error path.
  - Is there anything in fetch_big.py that would need changing to accept a non-preset code dataset? Be
    specific with file:line.
  - Would adding an ungated code PRESET to fetch_big.py be safe given we cannot verify the id resolves?
    Give a recommendation.`, { phase: 'Diagnose', label: 'hf', schema: ANSWER }),
])

const diag = diagnostics.filter(Boolean)
log(`diagnose: ${diag.length}/5 returned`)

phase('Verify')

// Adversarially verify the concrete defect findings from agents 1 and 2. A finding that cannot be
// reproduced by a second agent running a command is not a finding.
const claimed = [...(diag[0]?.findings || []), ...(diag[1]?.findings || [])]
log(`verifying ${claimed.length} claimed defects`)

const verdicts = await parallel(claimed.slice(0, 14).map((f, i) => () =>
  agent(`${CTX}

A previous agent claims the following defect in ${REPO}/fetch_local.py. Your job is to REFUTE it.
Default to refuted=true unless you can reproduce it yourself by running a command.

  TITLE:    ${f.title}
  SEVERITY: ${f.severity}
  DETAIL:   ${f.detail}
  EVIDENCE CLAIMED: ${f.evidence}
  PROPOSED FIX: ${f.fix || '(none given)'}

Reproduce it or disprove it. Run the actual command. Read the actual line. Two specific failure modes to
watch for, both of which have happened on this project before:
  - the "defect" is real in the abstract but cannot occur at the values this code actually runs at
  - the evidence quoted is from a DIFFERENT line than the one that governs the behaviour

Return refuted=true if the defect does not reproduce or cannot occur in practice, false if it does.
Give the exact command you ran and its exact output. Say whether the proposed fix is correct, and if it
is wrong, say what the right fix is.`,
    { phase: 'Verify', label: `verify:${f.title.slice(0, 28)}`, schema: {
      type: 'object',
      required: ['refuted', 'reproduction'],
      properties: {
        refuted: { type: 'boolean' },
        reproduction: { type: 'string', description: 'exact command run and exact output' },
        fix_correct: { type: 'boolean' },
        better_fix: { type: 'string' },
        note: { type: 'string' },
      },
    } })
    .then(v => (v ? { ...f, verdict: v } : null))
))

const confirmed = verdicts.filter(Boolean).filter(v => v.verdict && v.verdict.refuted === false)
const refuted = verdicts.filter(Boolean).filter(v => v.verdict && v.verdict.refuted === true)
log(`verified: ${confirmed.length} confirmed, ${refuted.length} refuted`)

phase('Synthesize')

const plan = await agent(`${CTX}

You are writing the IMPLEMENTATION BRIEF that I will execute. Be concrete and specific; I will follow it
literally. Do NOT edit any files yourself.

CONFIRMED DEFECTS in fetch_local.py (each independently reproduced by a second agent):
${JSON.stringify(confirmed.map(c => ({ title: c.title, detail: c.detail, severity: c.severity, fix: c.verdict.better_fix || c.fix, reproduction: c.verdict.reproduction })), null, 2)}

REFUTED CLAIMS (do NOT act on these; listed so I do not re-raise them):
${JSON.stringify(refuted.map(c => ({ title: c.title, why: c.verdict.reproduction })), null, 2)}

SIZING ANALYSIS -- how big the corpus must actually be:
${JSON.stringify(diag[2], null, 2)}

PYPI PULL DESIGN, with measured numbers:
${JSON.stringify(diag[3], null, 2)}

HF OPTIONS (all unverified, network blocked):
${JSON.stringify(diag[4], null, 2)}

Produce a single implementation brief covering:

  1. Every change to fetch_local.py, in priority order, each with the reason it exists. Root discovery
     must be fixed first -- it is the likely direct cause of the user's shortfall.
  2. The design of the PyPI pull. Decide and justify: a separate fetch_pypi.py, or a --pypi mode inside
     fetch_local.py? Consider that longrun.sh's pilot-add already dispatches on the dataset argument
     being the literal string "local", and that the user will want ONE command that just works. Give the
     exact CLI, the exact default package list, and the expected MEASURED yield in MB.
  3. What longrun.sh must change so "bash longrun.sh pilot-add py local 0.03" reaches its target on a
     machine where local source alone is not enough. Should local top up from PyPI automatically, or
     should that be a separate explicit argument? Argue both sides in two sentences each, then pick one
     and say why. Remember this project's standing rule: no compromises, and a mechanism that silently
     does less than asked is the defect class this whole codebase exists to catch.
  4. What the SHORT guard should say and do after these changes -- it must still refuse to hand back a
     corpus far smaller than asked, but it should now name the concrete escape hatch.
  5. The tests to add, and to WHICH existing test file. Existing suites: tok_test.py, ramp_test.py,
     lr_test.py, blowup_test.py, curve_test.py, compare_test.py, mem_evict_test.py, harness_test.sh,
     notes_check.py, levers.py. Note that a corpus-builder test must not require the network -- say
     exactly how to test the PyPI path offline.
  6. The exact commands the user should run, in order, to unblock the round18 resume leg today.

Be decisive. Where the evidence does not settle a question, say so in one line and make a call anyway.`,
  { phase: 'Synthesize', label: 'brief', effort: 'high' })

return { confirmed: confirmed.length, refuted: refuted.length, plan, sizing: diag[2], pypi: diag[3], hf: diag[4] }
