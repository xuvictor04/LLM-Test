Everything below was checked against the tree. All six suites were run first and are green (quoted in F1). I did **not** modify any file.

---

### [CRITICAL] Only 2 of the 5 answer sets reached me, and the second is cut off mid-sentence — 24 of the 38 questions have no visible answer, so the cross-slice contradiction check the task asks for cannot be completed

**Which question(s)** All 38, structurally.

**Why it is real** The `[...]` array I was handed contains **two** objects. Object 1 is the DATA/TOK slice (9 questions, with `blocking_md` and `cross_slice_md`). Object 2 is the OPT slice and its `answers_md` terminates inside Q-OPT-5's *What I read* line — `` `src/opt/api.py:70-84` (the horizon block and the `_project` history), `` — with no closing text, **no `blocking_md` and no `cross_slice_md`**. Objects 3, 4 and 5 are absent entirely.

Questions with a complete visible answer (13): Q-DATA-4, Q-DATA-6, Q-DATA-7, Q-DATA-8, Q-TOK-3, Q-TOK-9, Q-TOK-10, Q-TOK-11, Q-TOK-12, Q-OPT-1, Q-OPT-2, Q-OPT-3, Q-OPT-4. Partial (1): Q-OPT-5. **No visible answer (24):** Q-CLOCK-1, Q-LM-9, Q-FAB-1, Q-FAB-2, Q-FAB-5, Q-MEM-4, Q-RUN-1, Q-RUN-7, Q-WORLD-6, Q-WORLD-8, Q-EVAL-5, Q-EVAL-9, Q-CKPT-1, Q-MEM-8, Q-MEM-9, Q-MEM-10, Q-SIG-1, Q-OPT-6, Q-OPT-7, Q-FAB-6, Q-CKPT-2, Q-EVAL-10, Q-MEM-11, Q-LM-12.

This matters beyond bookkeeping: slice 1's own `cross_slice_md` names **eleven** dependencies on slices I cannot see (Q-CKPT-2, Q-CLOCK-1, Q-LM-9, Q-LM-12, Q-SIG-1, Q-OPT-5, Q-OPT-6, the EVAL holdout probes). Every one of those is precisely the "decision made twice, differently" hazard, and none of them can be adjudicated from what I was given.

**Demonstrated**
```
$ grep -c "^### Q-" docs/04_CONTRACT.md
39
$ grep -n "^### Q-" docs/04_CONTRACT.md | grep -c RESOLVED
1
```
39 headings minus the one marked `RESOLVED 2026-08-30` (Q-DERIVE-1) = the 38. Against that, 13 complete answers were supplied.

**What the answer should be instead** Re-run the synthesis with all five `answers_md` / `blocking_md` / `cross_slice_md` payloads intact (object 2 truncated at roughly 34 KB — likely a serialisation cap). Until then, treat every claim below about slices 3–5 as **NOT DEMONSTRATED**, and do not read the absence of a reported contradiction as evidence that there is none: I could only compare 13 of 38.

---

### [HIGH] Q-TOK-11's recommendation, if adopted, leaves at least five further frozen statements asserting the route it declares wrong — and K1 catches none of them

**Which question(s)** Q-TOK-11 (slice 1), touching Q-LM-9 / Q-LM-12 / the CENSUS.

**Why it is real** Slice 1 recommends **(a) now**: `residual_ratio` is not `MintReport`'s, it is a judgement-time read from a new `LM.residual_ratios` entry point (121 → 122). Its *What changes* list names five sites: `docs/04_CONTRACT.md` §7 + §LM table, `src/lm/api.py` (new stub), `compose.py` `LOOP_ORDER`, `src/tok/api.py:231-234`, and the Q-section at `:1217-1231`.

It omits every other place the tree freezes the MintReport / wire route. K1 compares only the ```contract fenced signature block against the tree (`tests/test_contract.py:348-381`, `doc_signatures(text)` / `api_signatures(src_dir)`), so **none of the omitted sites is checked by anything** — they are exactly the class of stale-frozen prose that produced Q-DERIVE-1 ("the *same* claim, frozen twice with opposite content").

Worse, the contract already contradicts *itself* here today: `:78` says the route is `MintReport.residual_ratio → argument`, while `:764-768` says that sourcing is the defect and that *"no entry point among the 121 exposes that read"*.

**Demonstrated**
```
$ grep -rn "residual_ratio" --include=*.md --include=*.py . | grep -v pycache | grep -v ^./archive | grep -v self_organize
./src/lm/levers.py:175:      d_residual_ratio     to TOK, ||delta||/||composite|| from the composer   (TOK_PROBATION_MIN's row;
./src/lm/api.py:260:    MintReport.residual_ratio (||delta[nid]|| / ||composite[nid]||) is the value TOK's probation
./src/tok/levers.py:126:    d_residual_ratio    ||delta||/||composite|| from LM.compose              (NOT YET IN THE LEDGER)
./src/tok/levers.py:128:wire d_residual_ratio from LM", and no such Coupling exists in assemble.COUPLINGS today. Until it does,
./src/tok/levers.py:467: ... See the d_residual_ratio note in the header -- the wire that arm needs is
./src/tok/levers.py:481: ... the wire d_residual_ratio from LM. The retire decision stays here because retirement pops from
./.rework/CENSUS.md:321: ... The ratio itself is computed from model.compose and so arrives as the wire d_residual_ratio from LM;
./docs/04_CONTRACT.md:78:| `d_residual_ratio` | `MintReport.residual_ratio` → argument to `judge_probation` | read off a live tensor. ...
./docs/04_CONTRACT.md:272:**Supplies:** `decode` as a plain callable to FAB; `MintReport.residual_ratio` to TOK.
```
and K1's scope:
```
$ sed -n '348,362p' tests/test_contract.py
def check_k1_signatures(src_dir=SRC, doc_path=DOC):
    ...
    tree_sigs, findings = api_signatures(src_dir)
    declared = doc_signatures(text)
```

**What the answer should be instead** Q-TOK-11's *What changes* must also list `docs/04_CONTRACT.md:78`, `:272`, `:764-768`, `src/lm/api.py:260`, `src/lm/levers.py:175`, `src/tok/levers.py:126-128, :467, :481`, and — because it is the owner's ledger and N3 reads it backwards — the `TOK_PROBATION_MIN` row at `.rework/CENSUS.md:321`, which still says the ratio *"arrives as the wire d_residual_ratio from LM"*. Nine sites, not five. If the owner instead picks (c), `docs/04_CONTRACT.md:78` still has to be corrected, because it names a producer that is zero by construction.

---

### [HIGH] Q-DATA-7 was called NON-BLOCKING, but the frozen `data_plan` docstring says D2 lands in the resolver — the two readings write different code in the same function

**Which question(s)** Q-DATA-7 (slice 1, `blocking_md` "DOES NOT BLOCK P4").

**Why it is real** Slice 1's justification is *"P4 writes the resolver either way; the recogniser is four predicates over a schedule the resolver already holds."* The frozen docstring says the opposite of "either way": it says D2 **lands** in the resolver *because* no literal string can mean "the added area alone". Under slice 1's (c), D2 lands in `longrun.sh` and the resolver only recognises; under (a), the resolver **generates** the pure-add schedule from area order. A P4 author reading the frozen text as it stands writes a generator. That is the direction the task warns about — sending P4 to write something that has to be undone.

The recogniser predicate slice 1 proposes is also *not* derivable from the docstring: the docstring states only the `stationary` rule (*"a schedule of one all-active phase is named 'stationary'"*) and leaves `pure_add` unstated, so two P4 authors produce different `Plan.protocol` values for the same schedule.

**Demonstrated**
```
$ sed -n '84,90p' src/data/api.py
    Empty generates derive.phase_schedule(n_areas, dat.phases, dat.phase_live), which at four
    areas is [[0,1],[1,2],[1,2],[2,3]] -- a REHEARSED sliding window, not pure add. D2 lands HERE,
    in the resolver, because there is no literal string meaning "the added area alone" independent
    of the area count. Plan.protocol records which of explicit / generated / stationary / pure_add
    ran; a schedule of one all-active phase is named "stationary" so the merged PHASED=0 arm still
    exists.
```
and the harness half, confirming slice 1's factual account:
```
$ grep -c PURE_ADD self_organize.py
0
$ grep -n "PURE_ADD" longrun.sh | head -4
921:  # PURE_ADD=1 -- THE ARM THE MODULARITY CLAIM ACTUALLY RESTS ON. ...
930:  if [ "${PURE_ADD:-0}" = 1 ] && [ -z "${PHASE_SCHED:-}" ]; then
```

**What the answer should be instead** Move Q-DATA-7 to **BLOCKS P4**. The blocking half is not the protocol *name*; it is the sentence *"D2 lands HERE, in the resolver"*, which must be either deleted (adopting (c)) or completed with the generation rule (adopting (a)) before anyone writes `data_plan`. Slice 1's four predicates are the right content; its severity grade is wrong.

---

### [HIGH] Q-DATA-6 and Q-EVAL-9 rest on opposite premises about whether recorded held-out numbers stay comparable

**Which question(s)** Q-DATA-6 (slice 1, adopt (b) — "every historical held-out number becomes non-comparable") vs Q-EVAL-9 (no visible answer; contract recommendation "leave it at 32").

**Why it is real** Q-EVAL-9's *entire stated reason* for freezing `holdout_windows` at 32 is preservation of comparability with recorded runs. Q-DATA-6 adopted destroys that comparability at the source — the held-out **text itself** changes, per area, as a function of the seed. Once the block moves, "32 is the literal the runs used" no longer buys anything, and the argument for keeping an n the contract's own cited research calls under-powered (*"2σ at n=32 will report HELD (inside the noise) for real effects of moderate size"*) collapses. This is the MAX_DOMAINS shape: one property (comparability) decided twice, in opposite directions, at two sites, by two slices.

**Demonstrated**
```
$ sed -n '1114,1120p' docs/04_CONTRACT.md
### Q-EVAL-9 — does `holdout_windows` stay at 32?
`research_continual_memory.md:743-745` warns that the 2σ rule at n=32 will report "HELD (inside the
noise)" for real effects of moderate size, and recommends 128–256 if a null result is going to be
published as a claim. **Recommendation: leave it at 32**, because that is the literal the runs used,
and raise it only after G2 has measured this machine's noise floor. Raising it silently would change
what every recorded retention number means.
```
against the rule Q-DATA-6 confirms, already frozen in the tree:
```
$ sed -n '44,48p' src/data/api.py
    THE HELD-OUT BLOCK IS A SEEDED RANDOM CONTIGUOUS BLOCK PER AREA, from
    rng_for("data.holdout", seed), of size min(holdout_frac * present, val_cap) -- NOT the tail.
```
The EVAL slice's actual answer is **NOT DEMONSTRATED** (see F1); what is demonstrated is that the contract's own two recommendations cannot both be justified by the reasons given.

**What the answer should be instead** Rule Q-DATA-6 and Q-EVAL-9 together, in one decision. If (b) is confirmed, Q-EVAL-9's recommendation must be re-argued on statistical power alone — its comparability argument is spent — and both breaks belong on the same P9 "numbers that moved" line, so a reader cannot attribute one shift to the other.

---

### [MEDIUM] Q-DATA-6 cites the `OPT.counters` grad-norm proposal as its model; Q-OPT-3 demonstrates that proposal is a wrong-measurement record

**Which question(s)** Q-DATA-6 (slice 1) ← Q-OPT-3 (slice 2).

**Why it is real** Slice 1 justifies its overlap Reading with: *"This is the `OPT.counters` grad-norm move from Q-OPT-3 applied here: it costs no lever, no wire, no default."* Slice 2 shows that exact proposal is defective — `counters(opt: Config, st)` receives a frozen Config and an `OptState` and **cannot see a gradient**; a P4 author following the docstring literally reports 0.0 for the whole run with every check green. So one slice used as a clean precedent the thing the other slice filed as a defect of the 98-record wrong-measurement family.

The conclusions do not collide (both say "measure, do not mint a lever"), and slice 1's own Reading is sited in `open_areas`, which does hold the bytes — so the recommendation survives. The **citation** does not, and citations are how this contract propagates rulings.

**Demonstrated**
```
$ sed -n '236,236p;253,258p' src/opt/api.py
def counters(opt: Config, st):
    ALSO REPORTS the observed global gradient norm per optimizer step (opt.grad_norm.p50/p99). It
    costs one torch.norm per step, needs no lever, and answers whether gradients were ever large
    enough to matter -- the second, independent, unmeasured explanation for the same curve shape
    that lr_sched exists to ablate. See FOR THE OWNER Q-OPT-3 ...
```
The signature takes `(opt, st)` only; the `maybe_step` step-5 `zero_grad` runs before `counters` is reached. Slice 2's diagnosis checks out.

**What the answer should be instead** Q-DATA-6's justification should cite the *rule* (a runtime measurement can never be a wire; `assemble.py:107-113`), not the `OPT.counters` instance. And Q-OPT-3's correction — norm taken in `maybe_step`, rendered by `counters` — must land, or Q-DATA-6 will have propagated a defective template into DATA.

---

### [MEDIUM] Slice 1 disproves the Q-DATA-8 premise the tree states in two places; whether the OPT slice's Q-OPT-5 still relies on it is unknowable from what I was given

**Which question(s)** Q-DATA-8 (slice 1) ↔ Q-OPT-5 (slice 2, truncated).

**Why it is real** Both `docs/04_CONTRACT.md:975-983` and `compose.py:_windows_in_epoch` assert the old tree computed *"the LR horizon and every ETA"* from `STREAM_LEN // WIN`. It did not. Slice 1's correction is right, and I verified it exhaustively. If the OPT slice answered Q-OPT-5 on the uncorrected premise, two slices will both "fix" the horizon, differently — and Q-OPT-5 is exactly the truncated answer.

**Demonstrated**
```
$ grep -n "STREAM_LEN" self_organize.py | grep "// WIN"
4317:        per = (_t.time() - t0) / 15; steps = STREAM_LEN // WIN
7319:        if _due("lmcurve", max(1, (STREAM_LEN // WIN) // 8)) and _lm_run:
$ sed -n '6236,6237p;6339,6339p' self_organize.py
    _total_steps = EPOCHS * (len(stream) // WIN)
    _bpw = WIN * (len(byte_stream) / max(1, len(stream))) if ONLINE else WIN     # BYTES of corpus consumed per step
        _per = max(1, len(stream) // WIN)                  # steps per epoch AT THE CURRENT VOCABULARY
```
`:6237` and `:5656` (`_bpt = len(byte_stream) / max(1, len(stream))`) establish that `stream` is the **token** stream. So `:4317` is the `[probe]` ETA banner and `:7319` is the `lmcurve` cadence period — the horizon and the live ETA were already token-measured. The tree's own claim:
```
$ sed -n '1868,1875p' src/spine/compose.py
    The ONE arithmetic that turns a token stream into a window count ...
    `stream_bytes // ctx` is the form this replaces: it divides a BYTE budget by a TOKEN window and
    overstates the count by the compression ratio, and the old tree computed the LR horizon and
    every ETA from it (:4317, :4719; FOR THE OWNER Q-DATA-8).
```
Whether Q-OPT-5's answer repeats it: **NOT DEMONSTRATED** — the answer is truncated.

**What the answer should be instead** Correct `compose.py:1871-1874` and `docs/04_CONTRACT.md:975-983` in one edit, and re-obtain Q-OPT-5's answer before adopting either. The real horizon defect is the `_project` shrinkage at `:6338-6362`, which is Q-OPT-5's; Q-DATA-8 must stop claiming it.

---

### [MEDIUM] "Add an entry point now, the surface is open" is a family decision, and one slice took it for one member while the contract's default for its twin is the opposite

**Which question(s)** Q-TOK-11 (slice 1: **(a) now**) vs Q-SIG-1, Q-LM-12, Q-FAB-6, Q-OPT-7, Q-CKPT-2 (no visible answers).

**Why it is real** Six questions have the identical shape — *an arm whose input no entry point produces* — and the contract answers two of them with the same phrase in opposite orders: Q-TOK-11 *"(a) when the surface opens, (c) until then"*; Q-SIG-1 *"(c) now, (a) when the surface opens."* Slice 1 departed to (a) now on cost-asymmetry grounds and said in its own `cross_slice_md` that Q-SIG-1 *"should be ruled together rather than one each way."* I cannot check whether it was, and the arithmetic runs the other way too: each (a) adoption moves the frozen set once, and K1 bounces whichever lands second.

The cost-asymmetry argument is also weaker for Q-TOK-11 than slice 1 allows: the arm it unblocks is off at the shipped defaults twice over.

**Demonstrated**
```
$ grep -n "probation_uses = Lever\|probation_by = Lever" src/tok/levers.py
425:    probation_uses = Lever(0, "How many appearances a newly minted token must earn before it keeps its "
449:    probation_by = Lever("use", "Which post-mint test decides whether a token keeps its slot: did it get "
```
and the reach requirement a 122nd entry point incurs:
```
$ grep -n "def check_k6" -A 2 tests/test_contract.py
1231:def check_k6_readers_are_reached(src_dir=SRC, doc_path=DOC):
1232-    """K6 -- an entry point that names levers must be REACHED by ASSEMBLY_ORDER or LOOP_ORDER.
```
Whether Q-SIG-1 / Q-LM-12 / Q-FAB-6 / Q-CKPT-2 were answered (a) or (c): **NOT DEMONSTRATED** (F1).

**What the answer should be instead** Rule the six as one amendment with one count (121 → N) in one commit, or rule all six (c) and defer the whole family to P5. Do not settle them one slice at a time — that is how the frozen set moves three times and K1 fails twice.

---

### [MEDIUM] The one thing slice 1 got right that no question owns: `DATA.restore_stream_state`'s name check may refuse goal B's headline experiment, and it sits between the DATA and CKPT slices

**Which question(s)** None of the 38 — that is the finding. Adjacent to Q-DATA-4, Q-DATA-7, Q-CKPT-1/2.

**Why it is real** The frozen docstring refuses when *"the recorded area names … disagree"*. An add-an-area resume is by construction a resume whose area list gained a name. Read as set-equality it refuses the benchmark at startup; read as "carried-over areas must have unmoved holdout blocks, a new name is admitted and printed" it permits it. Two readings, different code, no question asks. The row runs on every resume carrying a `DATA` payload.

**Demonstrated**
```
$ sed -n '198,203p' src/data/api.py
def restore_stream_state(dat: Config, areas, state):
    """Put the cursors and holdout offsets back. REFUSES LOUDLY if the recorded area names, holdout
    offsets or holdout sizes disagree with what open_areas just produced: a resume whose held-out
    block moved is a resume whose ACROSS THE RUN BOUNDARY number compares two different texts, and
    that is the one number goal B rests on.
$ grep -n "restore_stream_state" docs/04_CONTRACT.md
215:| `stream_state(dat, areas)` / `restore_stream_state(dat, areas, state)` | CKPT | dict / — |
230:REPORTS rather than a branch the caller takes; `restore_stream_state` is a row immediately after
623:... → `DATA.restore_stream_state` (after `open_areas`, before `data_plan`) →
1425:DATA: restore_stream_state(dat: Config, areas, state)
```
Four mentions, none in §5 FOR THE OWNER. Confirmed: no question covers it.

**What the answer should be instead** Add it as a 39th question and rule it with Q-DATA-4. It is P4-blocking in the strict sense — the refusal predicate is what P4 writes — and it is the only item I found that falls cleanly between two slices' territories with no owner.

---

### [MEDIUM] Q-TOK-3 makes `bytes_per_token` a draw from a second RNG stream; the SIG-width and splice-gate questions are answered as if it were a corpus constant

**Which question(s)** Q-TOK-3 (slice 1) → the SIG width (`NOT_WIRES` / the `("encoder","SIG_WIN")` departure), `data.splice_window`, Q-OPT-5.

**Why it is real** Slice 1 flagged this in `cross_slice_md` and it checks out: `build_vocabulary` measures `bytes_per_token` over the **counting** segmentation, and that segmentation applies `tok.dropout`. So at `dropout > 0` the SIG signature width and DATA's splice-gate threshold are functions of the `tok.dropout` draw. Every surface that discusses the width treats `bytes_per_token` as "MEASURED on the corpus" — a property of the text, not of a regulariser's seed. Nothing in the tree says otherwise.

**Demonstrated**
```
$ sed -n '56,63p' src/tok/api.py
    Otherwise: tok.build_passes tally-and-mint passes over
    b"".join(h[:tok.build_bytes] for h in area_heads), breaking early when a pass mints nothing.
    The counting segmentation applies tok.dropout, drawing from rng_for("tok.dropout", seed) --
    never the process-global `random` ...
    bytes_per_token over the build sample is measured with derive.bytes_per_token(len(sample),
    len(ids)) and returned on the Vocabulary, because it is what DATA's splice gate and SIG's width
    need and THERE IS NO SECOND ESTIMATOR
```
The confirmation half (three `regularize=True` call sites) is also real:
```
$ grep -n "regularize" src/spine/compose.py src/tok/api.py
src/spine/compose.py:391: ... regularize=True, seed) -- the epoch-0 segmentation.
src/spine/compose.py:644: ... regularize=True) -- between the draw and begin_epoch ...
src/spine/compose.py:1602:        regularize=True, seed=int(run.seed))
src/tok/api.py:91:def tokenize(tok: Config, vocab, data, labels=None, *, start=0, regularize=False, seed=0):
```

**What the answer should be instead** Q-TOK-3's ratification must carry a sentence into `tok/api.py:41-88` stating that `bytes_per_token` — and therefore `derive.signature_width_bytes` and `data.splice_window` — is seed-dependent at `dropout > 0`, and the SIG slice must be told before it rules on the width. As written, three packages read one number and only TOK knows it moves.

---

### [LOW] `d_residual_ratio`'s route is already frozen twice with opposite content, independently of any recommendation

**Which question(s)** Q-TOK-11, and the CENSUS ledger.

**Why it is real** Not caused by any slice — it is a pre-existing contradiction that both readings of Q-TOK-11 inherit, and it is the same shape as Q-DERIVE-1's post-mortem.

**Demonstrated**
```
$ sed -n '78,78p' docs/04_CONTRACT.md
| `d_residual_ratio` | `MintReport.residual_ratio` → argument to `judge_probation` | read off a live tensor. ...
$ sed -n '764,768p' docs/04_CONTRACT.md
* **`residual_ratio` for the `embed` probation arm.** `tok/api.py:232-234` sources it from LM's
  `MintReport`, i.e. from **mint time**, when a new token's residual is zero by construction — so
  `keep iff earned AND residual >= probation_residual` would retire every candidate. ...
  **no entry point among the 121 exposes that read**.
$ grep -n "arrives as the wire d_residual_ratio" .rework/CENSUS.md
321:... The ratio itself is computed from model.compose and so arrives as the wire d_residual_ratio from LM ...
```
One document says the route exists as an argument from `MintReport`; the same document 686 lines later says that source is zero by construction and no producer exists; the census says it arrives as a wire that `assemble.COUPLINGS` does not contain.

**What the answer should be instead** Whichever option wins, `:78` must be rewritten in the same commit, and `.rework/CENSUS.md:321`'s clause corrected — N3 reads the departures table backwards against census identity, so a census row asserting a wire that must never exist is a trap for the next reader.

---

### [LOW] Verified-correct claims, and where I agree

Stated so this is not an empty list from a reviewer who read nothing. I re-derived and **confirm**:

* **All six suites green.**
```
$ for t in ownership contract census assemble couplings derive; do python tests/test_$t.py 2>&1 | tail -6; done
=== 12 checks + 34 self-test cases, 0 failing ===   (contract)
=== 5 checks + the self-test, 0 failing ===          (census)
=== 4 checks, 0 failing ===                          (couplings)
575 oracle cases, 0 mismatches                       (derive; pin_tick 32 cases OK)
```
* **The N2/DEPARTURES obstacle both slices lean on is real.** `DEPARTURES` is keyed by `(family, old_name)` — *"the census row's own identity"* (`tests/test_census.py:79-81`) — and N3 flags any entry whose key is not a live census row (`:283-286`). A lever with no census ancestor has no legal key, so minting one requires amending `.rework/CENSUS.md`. Both Q-DATA-4(b) and Q-OPT-3(b) are correctly priced.
* **The wire counts agree, despite looking different.** Slice 1 quotes "23 declared coupling(s), 25 wire budget"; slice 2 says "19/25". Both are right and neither contradicts the other:
```
$ python tests/test_assemble.py 2>&1 | sed -n '2p;6p'
23 declared coupling(s), 25 wire budget; Python 3.11.15
      23 coupling(s) built twice ... 19 wire(s) of 25 budgeted, 4 intra-package
```
* **Q-OPT-1's premise:** `NOT_WIRES` holds exactly five entries and none is `d_run_steps` (`src/spine/assemble.py:1117-1163`; A4 prints "5 rejected candidate(s)"). The rejection is written at `compose.py:1823-1830` and `docs/04_CONTRACT.md:76` but not in the table `render()` prints. Slice 2's (a) is correct and costs nothing.
* **Q-OPT-4's decisive fact:** `compose.py:1632-1634` states the module restores run *"STRICTLY BEFORE OPT.build"*, and `param_groups` is built at `:1676-1679` from already-restored objects — so `build(resume=)` has no structural work left. And `state_dict`'s docstring (`opt/api.py:274-282`) does not mention `param_group_shape` while `load_state` (`:296-297`) refuses on it: an untrippable guard, exactly as slice 2 says, and `compose.py:1029-1033` already records it.
* **Q-TOK-9 is genuinely blocking.** `src/tok/levers.py:286-289` tells P4 *"8 carries over as the 'fixed' arm's declared target inside this package's build code"*; `src/tok/api.py:57` says `tok.build_passes` with no arm branch. Two frozen surfaces, opposite instructions.
* **Q-TOK-10's facts:** `save_vocabulary(tok: Config, vocab)` at `src/tok/api.py:275`, no suffix; `d_vocab_save_path = CKPT.dir + ".dyntok.json"` and `d_vocab_read_path = CKPT.resume + ".dyntok.json"` (`assemble.py:849, :866`). The `.bestN` resume consequence follows and is correct.
* **Q-TOK-12's arithmetic:** with elapsed-since-fire cadences, fires land at multiples of the period, so under (a) the surviving fraction is `gcd(period, batch)/batch` — `gcd(200,16)/16 = 1/2`. Verified by derivation; `compose.py:779-786` confirms the tree refuses to decide.
* **Q-DATA-4's facts:** `data/continual/{01_rust,02_sawyer,03_dracula,04_num2}` and `data/ood/{code_OOD,eng_OOD}` exist and are read only by `archive/legacy/*` (4 files).

**Counting the 38, for the 13 I could see** — HIGH-confidence recommendation: 8 (Q-DATA-4, Q-DATA-7, Q-DATA-8, Q-TOK-3, Q-TOK-9, Q-TOK-12, Q-OPT-1, Q-OPT-2). MEDIUM (the agent's own grade on the disposition, not the facts): 5 (Q-DATA-6, Q-TOK-10, Q-TOK-11, Q-OPT-3, Q-OPT-4). LOW: 0. Of those 13, **4 are effectively stale — already written into the tree and awaiting ratification only**: Q-DATA-6 (`data/api.py:44-52` + `RNG_SUBSYSTEMS`), Q-DATA-8 (`compose.py:1858-1876`, unit-enforced at `derive.py:317` and `:373`), Q-TOK-3 (`regularize` frozen, three call sites), Q-OPT-2 (`opt_step` is `units.Steps`, `opt_steps_from_windows` oracle-pinned at 575 cases). **For the other 25 (24 unanswered + 1 truncated) no count is possible** — see F1.

**On the blocking calls I could check:** slice 1's four BLOCKS entries (Q-TOK-9, Q-TOK-10, Q-TOK-11, Q-TOK-12) all survive scrutiny — each has two frozen surfaces or two live readings that write different code. Of its five DOES-NOT-BLOCK entries, **Q-DATA-7 is misgraded** (F3); Q-DATA-6, Q-DATA-8 and Q-TOK-3 are correctly non-blocking (the code is already written and single-valued); Q-DATA-4 is correctly non-blocking for `open_areas` **but** its adjacent finding — the `restore_stream_state` name check (F8) — is blocking and was filed as "adjacent, not one of my nine" rather than escalated.
