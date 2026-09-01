All six suites were run first. They are green and the tree is where both answers say it is:

```
$ python3 tests/test_ownership.py | grep -E "^(PASS|===)"
PASS  O1..O11 (11 checks)   === 11 checks + 18 self-test cases, 0 failing ===
$ python3 tests/test_contract.py | tail -3
=== 12 checks + 34 self-test cases, 0 failing ===
$ python3 tests/test_census.py | grep -E "^(PASS|===)"
PASS  N1..N5   === 5 checks + the self-test, 0 failing ===
$ python3 tests/test_assemble.py | grep -E "^(PASS|===)"
PASS  A1..A7   === 7 checks, 0 failing ===
$ python3 tests/test_couplings.py | tail -4   -> 4 checks, 0 failing
$ python3 tests/test_derive.py | tail -1      -> 575 oracle cases, 0 mismatches
```

I re-derived every "What is true today" claim in both supplied answers from the tree itself. **The
great majority check out exactly**, including the load-bearing ones — see the agreement list at the
end. Below are the places where a *recommendation* does not fit the framework it claims to fit, or
where its "what changes" list would not actually work.

**SCOPE WARNING, first, because it changes what this review is worth.** The task says *five*
evaluating agents returned. The input contains **two**, and the second is **truncated mid-sentence
inside Q-OPT-5** (`"What I read" ... src/opt/api.py:70-84 (the horizon block and the _project
history),`). So Q-OPT-5, Q-OPT-6, Q-OPT-7 and three entire slices were **not reviewable**. Nothing
below should be read as clearing them. NOT DEMONSTRATED for those; supplying the missing three
answers and the tail of the second is what would settle it.

---

### [HIGH] Q-DATA-8's report line cannot live in `RUN.bench_summary` — it needs a signature change AND it is switched off on every non-bench run

**Which question(s)** Q-DATA-8 (slice 1).

**Why it is real**
The recommendation is *"(a) — confirm, with one addition: … the report line must print `stream_bytes`,
`len(Segmentation.ids)`, the measured `bytes_per_token`, `windows_in_epoch` and `run_windows`
**together on one line**, so the ratio is checkable by eye. `RUN.bench_summary` already takes
`bytes_per_window` …; this is that line plus two numbers and one division."* and the change list
says **"No frozen signature moves."** Both halves fail:

1. `bench_summary(run, clock, *, elapsed_s, bytes_per_window, n_params, timing=None)` can reach
   **none of the five numbers**. `bytes_per_window` is the *product* `ctx × bytes_per_token`, and RUN
   may not read `LM.ctx` to divide it back out. `RunClock` carries `step / flushes / backwards /
   opt_steps / epoch / batch_len` and nothing else — no `run_windows`, no `stream_bytes`, no
   `len(Segmentation.ids)`. So the line requires **new keyword arguments on a frozen signature**,
   which is exactly what the answer promises it does not do.
2. Worse for the purpose: `bench_summary` **returns None when `bench` is off** and is printed
   *instead of* the eval battery. The whole point of the addition is that "a step count 2.5× the
   truth is invisible unless the three numbers appear together" — putting it there makes it invisible
   on every ordinary run, which is the armed-but-inert shape this project exists to end.

**Demonstrated**
```
$ sed -n '254,256p;264p' src/train/api.py
def bench_summary(run: Config, clock, *, elapsed_s, bytes_per_window, n_params, timing=None):
    """Throughput, printed INSTEAD of the eval battery. Returns the lines, or None when bench is
    off.
    LEVERS READ: bench
$ sed -n '118,125p' src/train/api.py
    a CKPT Snapshot. Returns RunClock with:
        .step        units.Windows    -- what `step` counted at :6796 and :7708
        .flushes     units.Flushes    -- what `_nbwd` counted; the loop body's own clock
        .backwards   units.Backwards  -- what accumulation must count (derive.accum_due)
        .opt_steps   units.Steps      -- optimizer steps; the ONLY Steps clock the loop owns
        .epoch       units.Epochs
        .batch_len   int              -- windows queued in the accumulator
```

**What the answer should be instead**
Keep (a) — confirming `_run_windows` is right and is already unit-enforced. But the five-number line
belongs to **the composition root**, printed once at startup right after the `segment` row, not to
`RUN.bench_summary`. The root already holds all five (`sysm.segmentation.ids`, `LM.ctx`,
`Segmentation.bytes_per_token`, `_windows_in_epoch(sysm)`, `_run_windows(sysm)`), it is the only
place that can see them together, and spine is exempt from the ownership rule that stops RUN from
assembling them. Then the claim "No frozen signature moves" becomes true, and the line prints on
every run rather than only under `RUN_BENCH`.

---

### [MEDIUM] Q-TOK-10's option (b) is not free on the read side: it puts the vocabulary-path rule in two places, and the symmetry claim rests on filename conventions that are still stubs

**Which question(s)** Q-TOK-10 (slice 1).

**Why it is real**
The answer recommends `save_vocabulary(tok, vocab, *, suffix="")` and prices the read side at zero:
*"`d_vocab_read_path`'s compute is already `CKPT.resume + \".dyntok.json\"`, so the read side becomes
symmetric with no edit at all."* That symmetry only holds if the write inserts the suffix **before**
the extension — `<base>` + `<suffix>` + `.dyntok.json`. But the wire hands TOK a **fully formed
path**, `CKPT.dir + ".dyntok.json"`. To splice a suffix into the middle, `save_vocabulary` must strip
and re-append the `".dyntok.json"` literal — so the extension rule the coupling's `why` says *"that
rule is the compute here"* now exists in the coupling **and** in a package body. That is the
second-literal / two-declarations defect the same answer used to decide Q-TOK-9 against option (b)
one question earlier. Appending after the extension avoids the duplication but then the read path
(`resume + ".dyntok.json"`) no longer matches, and the "no edit at all" claim is gone either way.

Two further things the answer does not price:
- **M46 is currently unreachable, not merely open.** `.bestN` snapshots require a `BestAction`, which
  comes from `CKPT.Retention.consider` — a **deferred** entry point whose deferral text says in as
  many words *"Saves.best can never be non-zero"*. And K11's own docstring records that
  `Retention.consider` was stripped of its fabricated `produces` of `reason` and `suffix`, so **today
  nothing in the tree produces a suffix at all**. The defect being rushed to fix cannot fire until P5.
- The claim that a best-snapshot resume resolves to `<base>.best3.dyntok.json` assumes a filename
  convention that `CKPT.save` (a `NotImplementedError` stub) has not yet fixed. NOT DEMONSTRATED.

**Demonstrated**
```
$ sed -n '846,852p' src/spine/assemble.py
    Coupling(
        src="CKPT.dir",
        dst="TOK.d_vocab_save_path",
        compute=lambda r: (r["CKPT"].dir + ".dyntok.json") if r["CKPT"].dir else "",
$ sed -n '862,867p' src/spine/assemble.py
    Coupling(
        src="CKPT.resume",
        dst="TOK.d_vocab_read_path",
        compute=lambda r: (r["CKPT"].resume + ".dyntok.json") if r["CKPT"].resume else "",
$ grep -n "CKPT.Retention.consider" -A 2 src/spine/compose.py | sed -n '1,3p'
1135:    "CKPT.Retention.consider":
1136-        "P5, WITH EVAL.curve_probe, AND THIS IS THE SAME DOUBLE STANDARD ONE ROW DOWNSTREAM. It had "
1137-        "an A row until 2026-08-30 while its only input's producer sat in this table: `curve_bpb` is "
$ sed -n '1966,1967p' tests/test_contract.py
    LM.build_model producing `key_fn` and `head` (it returns a model; both are compose's partial
    applications), SIG.build producing `encode` (it returns SigState), TOK.tokenize producing
    `windows_in_epoch`, `run_windows` and `bytes_per_window` (it returns a Segmentation; all three
    are compose helpers), CKPT.Retention.consider producing `reason` and `suffix` (it returns a
    BestAction), ...
```

**What the answer should be instead**
(b) is still the right direction — the suffix is a **runtime** value chosen by the retention policy
and therefore can only arrive as an argument, which is the framework rule and is correctly reasoned.
But the change must be stated as **two** edits, not one: change the coupling to hand TOK the **base
path** (`CKPT.dir`, unit `U.PATH`) and let TOK own the `.dyntok.json` extension together with the
suffix, so the filename rule keeps one home. And the priority should be stated honestly: this closes
a defect that cannot fire until `Retention.consider` lands at P5, so it is cheap-now/expensive-later
housekeeping, not a live blocker.

---

### [MEDIUM] Q-OPT-4's change list omits the live call site — removing `resume` as written raises `TypeError` on every assembly

**Which question(s)** Q-OPT-4 (slice 2).

**Why it is real**
The recommendation is **(d) remove `resume=None` from `OPT.build`**, and its "what changes" names
`src/opt/api.py:59`, `docs/04_CONTRACT.md:1476`, the ASSEMBLY_ORDER **row text** at `compose.py:489-497`
and the `CKPT.load` produces column at `:261`. It does **not** name the actual call, which passes
`resume=saved.get("OPT")` at `compose.py:1680`. Rows in `ASSEMBLY_ORDER` are documentation data; the
call at 1675-1680 is executable Python. Applying the change as listed leaves a keyword argument
`build()` no longer accepts.

**Demonstrated**
```
$ grep -n "opt_api.build" src/spine/compose.py
1675:    sysm.optimizer = opt_api.build(
$ sed -n '1675,1680p' src/spine/compose.py
    sysm.optimizer = opt_api.build(
        opt,
        param_groups={"base": sysm.base_params,
                      "encoder": list(sig_api.encoder_parameters(sig, sysm.sig))},
        run_windows=_run_windows(sysm),
        resume=saved.get("OPT"))
```

**What the answer should be instead**
Same recommendation — the reasoning is sound and I confirmed its decisive fact: the param-group
structure is fully determined before `OPT.build` is called (`compose.py:1635` *"STRICTLY BEFORE
OPT.build"*, groups assembled at `:1677-1679`), so `build(resume=)` has no work left. Add
`src/spine/compose.py:1680` to the change list as a **code** edit, distinct from the row-text edits.
The paired `param_group_shape` repair the answer identifies (`state_dict` must declare it, or
`load_state`'s L50 refusal is untrippable) is correct and independently confirmed at
`src/opt/api.py:274-286` and `src/spine/compose.py:1029-1033`.

---

### [MEDIUM] Q-TOK-11's new `LM.residual_ratios` row would run unconditionally under a gated consumer, and the change list misses the one document that names the current route

**Which question(s)** Q-TOK-11 (slice 1).

**Why it is real**
The diagnosis is correct and I verified every part of it (LM has exactly ten entry points, none
returns a live residual read; `on_mint` produces `MintReport.residual_ratio` at mint time, when the
delta is zero by construction; `anchor_term` already computes the same quantity every flush). Two
gaps in the recommendation:

1. The proposed row is *"a **B** row for `LM.residual_ratios(model)` immediately before
   `TOK.judge_probation`"*. But `judge_probation`'s row is explicitly **EVENT-DRIVEN on
   `Due.probation`**. A producer row placed beside it with no gate runs a per-token norm over the
   whole vocabulary **every flush** while its consumer fires on a 5000-window cadence — an
   instrument computed thousands of times and discarded, which is the wrong-measurement shape rather
   than the framework's. The row must carry the same `Due.probation` gate, and say so, or the answer
   has bought a per-flush cost nobody asked for.
2. The change list names `docs/04_CONTRACT.md` §7, the §LM table, `:1217-1231` and
   `src/tok/api.py:231-234`. It does **not** name `docs/04_CONTRACT.md:74`, the refused-wires table,
   whose `d_residual_ratio` row states the actual route as *"`MintReport.residual_ratio` → argument
   to `judge_probation`"*. Left standing, two frozen documents name two different producers — the
   exact defect class the answer is fixing.

**Demonstrated**
```
$ sed -n '940,948p' src/spine/compose.py
    ("B", "TOK",   "judge_probation", "step=clock.step; appearances is System.token_seen, the same "
                                      "per-token counter LM.anchor_term takes as `token_seen`. "
                                      "EVENT-DRIVEN on Due.probation, which TOK.on_window already "
                                      "asked at A under its OWN cadence key -- asking again here "
                                      "would CONSUME the event, ...
$ grep -n "d_residual_ratio" docs/04_CONTRACT.md
74 (table): | `d_residual_ratio` | `MintReport.residual_ratio` → argument to `judge_probation` | read off a live tensor. ...
$ grep -c "^def " src/lm/api.py
10
$ python3 tests/test_contract.py | grep "K1 " -A 1
PASS  K1  the document and the tree declare the same public surface
          121 entry point(s) across 13 package(s) compared against 121 declared in docs/04_CONTRACT.md
```

**What the answer should be instead**
(a) is genuinely framework-compatible — it is LM's read of LM's own tensors, handed to TOK as an
argument the root assembles, crossing no import and no wire, and the 121→122 growth is correctly
flagged LOUD. Add two items: the row must state its `Due.probation` gate (matching
`judge_probation`'s), and `docs/04_CONTRACT.md:74` must move in the same commit as §7 and the LM
table.

---

### [LOW] Two small precision errors in Q-DATA-8's method and change list

**Which question(s)** Q-DATA-8 (slice 1).

**Why it is real**
The answer's substantive correction is **right and I reproduced it independently**: the old tree's LR
horizon and ETA came from `len(stream) // WIN` over the *token* stream, and the byte//token form
survives only in the probe banner and the `lmcurve` cadence period. Two details are off:
- It claims to have read *"every one of the **20** `STREAM_LEN` sites"*. There are 28 matching lines.
  The conclusion survives (I checked every `STREAM_LEN // WIN` occurrence myself), but the
  exhaustiveness claim as stated is not what the file contains.
- The change list says to correct *"`src/spine/compose.py:1821-1861`"*, i.e. `_run_windows`. The
  offending sentence is in **`_windows_in_epoch`**, at `:1871-1873`.

**Demonstrated**
```
$ grep -c "STREAM_LEN" self_organize.py
28
$ grep -n "STREAM_LEN // WIN" self_organize.py
4317:        per = (_t.time() - t0) / 15; steps = STREAM_LEN // WIN
4719:    # length in steps is STREAM_LEN/WIN -- so "8 epochs" has meant 48,000 steps at STREAM_LEN=4e6 and 840,000 at
7319:        if _due("lmcurve", max(1, (STREAM_LEN // WIN) // 8)) and _lm_run:
$ sed -n '6236p;6339p' self_organize.py
    _total_steps = EPOCHS * (len(stream) // WIN)
        _per = max(1, len(stream) // WIN)                  # steps per epoch AT THE CURRENT VOCABULARY
$ sed -n '1869,1874p' src/spine/compose.py
    The ONE arithmetic that turns a token stream into a window count, named so both readers -- the
    LR horizon above and RunClock.begin_epoch -- take it from the same place. `stream_bytes // ctx`
    is the form this replaces: it divides a BYTE budget by a TOKEN window and overstates the count
    by the compression ratio, and the old tree computed the LR horizon and every ETA from it
    (:4317, :4719; FOR THE OWNER Q-DATA-8).
    return max(1, len(sysm.segmentation.ids) // int(sysm.configs["LM"].ctx))
```

**What the answer should be instead**
Same recommendation; point the correction at `_windows_in_epoch`'s docstring at `compose.py:1871-1873`
(the sentence *"the old tree computed the LR horizon and every ETA from it"*), and drop the "20 sites"
claim.

---

### [LOW] Q-TOK-9's deciding argument leans on a document that does not exist yet

**Which question(s)** Q-TOK-9 (slice 1).

**Why it is real**
The answer says the decision is *"mechanical rather than aesthetic: **`docs/04_LEVERS.md` is generated
from the registry**"* and that an 8 in build code *"prints as 2 in the operator's **only reference**"*.
`docs/` contains `02_OPERATIONS.md`, `03_WIRING.md`, `04_CONTRACT.md` and `proposals/` — there is no
`04_LEVERS.md`. Three `levers.py` files do describe it as generated, so the underlying argument (the
registry holds one default; a second literal elsewhere cannot be reached by the generator) is sound.
But it is an argument about a **planned** artifact, and "the operator's only reference" overstates it.

**Demonstrated**
```
$ ls docs/
02_OPERATIONS.md
03_WIRING.md
04_CONTRACT.md
proposals
$ grep -rn "04_LEVERS.md is generated" src/
src/fabric/levers.py:104:DEFAULT ITSELF falsifies is worse than no label -- docs/04_LEVERS.md is generated from these
src/domains/levers.py:166:is worse than no label -- docs/04_LEVERS.md is generated from these declarations and would print
```

**What the answer should be instead**
Same recommendation — (a), one literal, plus the declared Gate — but argue it from **the registry**
(`Lever` carries exactly one default, and `L1` is one declaration in one place), noting
`docs/04_LEVERS.md` as the planned consumer rather than as an existing reference.

---

### WHAT I CHECKED AND AGREE WITH

Every other recommendation in the two supplied answers is **framework-compatible**, and I checked
each against the specific traps named in the brief — cross-package import (O10), a runtime
measurement smuggled into a build-time wire, a cross-kind clock conversion outside `spine.derive`, a
lever read from outside its owner, and an unflagged frozen-signature move. I found none of those in:

- **Q-DATA-4 (a), slash-in-`areas`.** Confirmed `dat.areas` is read at exactly one site
  (`grep -rn "\.areas\b" src/` → only `data/api.py:30` and root uses of `sysm.areas`); `U.NAME` is a
  printed label and is never enforced (`units.py:134-135`: *"These are labels … never enforced at
  runtime"*), so no unit breaks; no lever, no wire, no signature. Also confirmed
  `data/{continual,ood}` exist (1.5M / 764K) and are named nowhere in `src/`, `tests/` or the root
  harnesses. Its **N2 argument against option (b) is correct**: `DEPARTURES` is keyed by
  `(family, old_name)` and N3 requires that key to exist as a census row, so a lever with no ancestor
  cannot be declared as a departure — verified by reading `check_n2_every_lever_traces_back` and
  `check_n3_departures_are_live` at `tests/test_census.py:244-300`. The same argument is used
  correctly by Q-DATA-6 and by Q-OPT-3.
- **Q-DATA-4's adjacent finding on `DATA.restore_stream_state`** (`src/data/api.py:198-203`, refuses
  on disagreeing *area names*) — real, and correctly identified as blocking the add-an-area
  experiment under a set-equality reading. Verified verbatim.
- **Q-DATA-6 (b)+(d).** The stale-claim finding is **confirmed**: `src/data/levers.py:130` and `:441`
  both assert `EVAL.d_holdout_bytes` is *"declared in spine.assemble"*, and
  `grep -rn holdout_bytes src/` finds no such coupling while `docs/04_CONTRACT.md:74` refuses it.
  The recommendation correctly refuses to mint a `holdout_rule` lever and correctly routes the split
  rule to the Sample as an argument.
- **Q-DATA-7 (c).** The recogniser reads only `dat.phase_sched` and the `areas` argument — no
  cross-package read, no wire, no change to the oracle-pinned `derive.phase_schedule` (575 cases, 0
  mismatches, run). `grep -c PURE_ADD self_organize.py` → **0**; `longrun.sh:930` confirmed.
- **Q-TOK-3 (b).** Confirmed `regularize=False` is already a frozen parameter (`tok/api.py:91`), the
  root passes `regularize=True` at `compose.py:391, 644, 1602`, `"tok.dropout"` is in
  `RNG_SUBSYSTEMS` (`compose.py:124`), and the old-tree diagnosis is exact — `tokenizer.py:187`
  gates on `count`, `count=True` appears at `self_organize.py:1264` and nowhere else, and `seg` is
  defined **twice** at `tokenizer.py:389` and `:394`.
- **Q-TOK-12 (b).** Compatible: the OR happens in the root (exempt), `Due` keeps its four fields, no
  signature moves. Its arithmetic is right — the units confirm it (`grow_every=200 U.Windows`,
  `retok_every=3000 U.Windows`, `batch_windows=1 U.Windows`), and `gcd(200,16)/16 = 1/2`, coprime →
  `1/16`. The tree does defer the choice in both places it names (`compose.py:773-786`, `:1457-1461`).
- **Q-OPT-1 (a).** Confirmed `NOT_WIRES` has exactly 5 entries and no `d_run_steps` row, while
  `docs/04_CONTRACT.md:76` and `compose.py:1824-1832` both state the second ground. A4 iterates
  `NOT_WIRES` itself (`tests/test_assemble.py:791-795`), so a new tuple entry extends a checked
  surface. Wire ledger confirmed at 19 cross-package of 25 budgeted (23 couplings, 4 `local`).
- **Q-OPT-2 (a).** Already adopted and unit-enforced: `maybe_step` step 1 advances `st.opt_step`
  (`units.Steps`), `lr_at(opt, st, opt_step)` is PURE, `derive.opt_steps_from_windows` raises
  `UnitError` at both ends. The P9 list genuinely does not exist as a document (only
  `.rework/PLAN.md:186` and three prose mentions).
- **Q-OPT-3 (a) with the measurement moved to `maybe_step`.** This is the strongest correction in the
  two answers and it is right: `OPT.counters(opt, st)` claims to compute the norm, but
  `maybe_step` step 5 *"step and zero_grad both"*, so a norm read in `counters` is over zeroed grads
  — 0.0 for the whole run with every check green. Confirmed at `src/opt/api.py:255-259` against
  `:225-227`. Also confirmed `grep -c clip self_organize.py` → **2**, both prose about the forgetting
  measure F, and that OPT declares no clip lever.

Both frozen-signature moves (Q-TOK-10 `save_vocabulary`, Q-OPT-4 `OPT.build`) are declared LOUD with
the matching `docs/04_CONTRACT.md` line, which is the correct handling — `docs/04_CONTRACT.md:1513`
and `:1476` are where they land, and K1 compares both directions.