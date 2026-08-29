# The coupling graph

Every value in this system that is computed from more than one lever, what it is computed from, what it
resolved to, and why it exists. Nothing here is written by hand: the body below is the exact return value
of `spine.assemble.render()`, so it cannot drift from the table the run uses.

**Regenerate with:**

```
python3 - <<'EOF'
import sys, os
sys.path.insert(0, os.path.join(os.getcwd(), "src"))
from spine import assemble
cfgs, wires, warnings = assemble.build(environ={})
print(assemble.render(cfgs, wires))
EOF
```

## How to read it

* **IRREDUCIBLE** and **DECLARED, REDUCIBLE** are two different kinds of claim, and the split is the point
  of the document. An irreducible coupling is a statement about arithmetic — `pressure x slots` *is* the
  equilibrium population — and no refactor removes it. A reducible one is a decision this design took, and
  a reader deciding whether to keep it needs to see that it is a decision. Printed together, the whole
  list reads as inevitable, which is how a coupling graph stops being reviewed.
* **`(intra-package)`** marks a coupling whose sources are all its destination's own levers. It is still
  `d_`-prefixed, because G5 is about values computed from more than one *lever*, not more than one
  package. It books no edge and spends no budget: an edge from a package to itself cannot widen any
  lever's `affects()` set.
* **The reason column is never truncated.** A justification cut off at the column edge reads as justified.
* **`grep -rn 'd_' src/`** is the complete index. The wire names the destination field, and
  `Wires.add(..., into=cfg)` performs the assignment itself, so a receiving package never gets to launder
  a coupling into a name that looks locally owned.
* **Values shown are at defaults** (`build(environ={})`), which is why `FAB.d_cap_lift_period` reads
  `Flushes(20000)`: `OPT_BATCH_WINDOWS` defaults to 1, so one flush is one window and the conversion is
  the identity. At the `BATCH_W=16` the measured defects were recorded under it is `Flushes(1250)`.

## State of the graph

13 couplings declared, 13 resolved, 0 deferred; 10 cross-package wires of a 25 budget; 3 intra-package.
All thirteen packages under `src/*/levers.py` are imported by `spine/assemble.py` and registered, so no
row defers and every endpoint is checked against a real declaration at import (`_check_endpoints`).

```
=== coupling graph ===
13 declared, 13 resolved, 0 deferred; 10 of 25 wire budget spent.
3 of the resolved couplings are intra-package: they are still d_-prefixed and still printed,
but they book no edge and spend no budget, because an edge from a package to itself cannot
widen any lever's affects() set.

Every value below is d_-prefixed on its receiving Config. The wire names the field, not the
receiver, so `grep -rn d_ src/` is a complete index of the couplings in this system.

--- IRREDUCIBLE (9) ---
  One quantity named twice. No interface design separates these two ends; a project claiming
  they are independent is describing a system other than the one it runs.

  FAB.slots
    -> MEM.d_owner_blocks = 64  [count]
       why: Memory ownership is expert_id % n_own, and n_own was min(FAB_NMAX, MEM_OWNERS) at self_organize.py:4873. The fold is irreducible: expert ids run to the slot count (4096) while the store has MEM_OWNERS (64) partitions, so 32 experts shared each partition and 'per-expert memory' was per-64-buckets memory. Blocks in excess of the slot count are unreachable by the modulo and their quota is capacity that exists and can never be written.

  FAB.slots
    -> MEM.d_capacity = 8192  [entries]
       why: Capacity is DERIVED, not declared: a partitioned store holds blocks x quota entries and has no size independent of its partition. The old tree declared it anyway and memory.py:36 then silently overrode it -- 'if self.n_own > 1: cap = self.n_own * self.quota' -- so a requested MEM_CAP of 200,000 became 64 x 128 = 8,192, a 24x shrink recorded as E7.40 with no line in any log. This is the census's MEM_CAP promote-to-wire (CENSUS.md:249); after it the operator sizes the store through quota and owners, and 200,000 is no longer a number anyone types. Deriving it here means the number that gets discarded is the one nobody wrote.

  OPT.batch_windows
    -> FAB.d_manage_period = Flushes(500)  [flushes]
       why: MANAGE_EVERY is a cadence on the WINDOW counter, and five call sites consume it per FLUSH. The management gates above the batch early-out test `step % MANAGE_EVERY == 0` (self_organize.py:6716, :6764, :6768) where `step` advances once per window (`i += WIN; step += 1`, :6796 and :7708); the sites BELOW the early-out run once per flush and wrote the conversion inline as `_nbwd % max(1, MANAGE_EVERY // max(1, BATCH_W))` at :6819, :6836, :6961, :6988, :7077 and :7325 -- one number compared against two clock kinds in one file. Irreducible: a cadence in windows handed to a block that counts flushes has no meaning until the batch width is known, which is why the value is a Flushes clock and not an int -- an int compares fine against a threshold in the wrong unit. UNIT RESOLVED HERE: this row used to read `derive.flush_period(Steps(r['FAB'].manage_every), ...)` and its reason said 'MANAGE_EVERY is written in STEPS'; the census (CENSUS.md, FAB family) and fabric/levers.py:648 both type it Windows, and the source agrees with them, so the Steps assumption is withdrawn and the conversion is derive.flush_period_windows.

  OPT.batch_windows x CAP.pin_windows
    -> FAB.d_cap_lift_period = Flushes(20000)  [flushes]
       why: The measured case for this whole mechanism. The capacity valve's pin clock ticked per flush against a threshold in windows, so GROW_CAP_EVERY=20000 silently demanded 320,000 windows at BATCH_W=16 and 640,000 at 32: the population sat pinned for 43,645 real ticks while the clock read 2,650 (= 42,400/16) and the report said 'reached the cap but never held it long enough' -- a true sentence about a false clock. A second gate one layer up then compared fabgrow.n (calls) to the same threshold and lifted nothing for a further whole round, the first fault masking the second. The knob is now CAP.pin_windows (census GROW_CAP_EVERY -> CAP_PIN_STEPS, re-typed and re-named to CAP_PIN_WINDOWS at capacity/levers.py:305 because the counter it is compared against is `step`). CAVEAT THE VALVE PORT MUST SETTLE, recorded rather than papered over: derive.pin_tick still types its accumulated clock as Steps, so a Windows threshold and a Steps clock cannot meet -- capacity/levers.py:88-108 sets out the two legal repairs, and applying both at once fires the valve 16x too EARLY. This row converts the threshold and nothing else.

  OPT.batch_windows x CAP.pin_windows
    -> TOK.d_cap_lift_period = Flushes(20000)  [flushes]
       why: The vocabulary soft cap is lifted by the same valve on the same clock, and it was blocked by the same units fault: round6 measured 0 vocabulary lifts on gc_real, and gc_fast and gc_loose lifted identically (6 each, same first step 32047), which proves the plateau condition was never the blocker -- GROW_CAP_EVERY=20000 against a 60k-step run was. Wired separately from the fabric's period because the two caps are lifted by two mechanisms and a shared field would make one of them read a value the other's package owns.

  LM.vocab_slots
    -> TOK.d_vocab_ceiling = 4096  [entries]
       why: emb.weight and head.weight have exactly this many rows, so the vocabulary the tokenizer is allowed to mint into is the model's row count: one number named twice, not two numbers that happen to agree, and no interface makes them independent. Getting it wrong is not a soft failure -- the resume geometry gate at self_organize.py:4442-4468 exists because a checkpoint built at one width cannot load into a model built at another, and the softer form (rows minted by the tokenizer but never present in the head) is the LOSS_MASK_DEAD family, where dead rows scale with VMAX and quietly take probability mass. DIRECTION CORRECTED HERE: this row read `src='TOK.vmax', dst='LM.d_softmax_width'`, and TOK has no lever called vmax -- the census gives VMAX to LM as LM_VOCAB_SLOTS and says in as many words that 'TOK receives it as the wire d_vocab_ceiling' (CENSUS.md:323), which is what lm/levers.py:127-141 and tok/levers.py:87 both record as the outstanding repair. Left as it was, importing the real packages made build() raise 'TOKLevers has no lever vmax' -- the mechanism working, on a row that named an owner nobody had.

  FAB.pressure x FAB.slots
    -> FAB.d_operating_population = 1844  [experts]  (intra-package)
       why: IRREDUCIBLE, and this is the example PLAN section 4 is built on. pressure is not a modifier on the cull, it is a SETPOINT: below pressure x slots the cull gate is shut and the population grows, at or above it the cull runs, so the steady state IS pressure x slots and FAB_PRESSURE cannot be made independent of the slot count -- they are one control loop with two named ends. The cost of not writing it down was measured: FAB_N0=2048 against FAB_NMAX=4096 parks occupancy at 0.50, below a FAB_PRESSURE of 0.75, and the utilization cull, the utilization spare and FAB_RESCUE all read ARMED AND INERT for an entire investigation while the report showed them switched on.

  OPT.batch_windows x OPT.accum
    -> OPT.d_effective_batch_windows = 1  [count]  (intra-package)
       why: The batch size a run actually trains at is windows per flush times flushes per optimizer step, and there is no third number. It is written down because the old tree reported the CONFIGURED one: accumulation was gated on a window counter instead of on backward passes, which measured 55 optimizer steps where 13 were due, so at ACCUM=4 the effective batch was a quarter of its label and every learning-rate result taken against that configuration was taken at a batch size other than the one it is filed under. OWNER CORRECTED HERE: it was declared as TRAIN.d_effective_batch_windows reading TRAIN.batch_w and TRAIN.accum, and there is no TRAIN package -- the loop is RUN and both levers are OPT's (BATCH_W -> OPT_BATCH_WINDOWS, ACCUM -> OPT_ACCUM), which opt/levers.py:133-147 states as the repair. It is still LOCAL: one owner, no edge, no budget.

  LM.ctx
    -> LM.d_pos_max = 128  [tokens]  (intra-package)
       why: The positional table has one row per position a window can hold, so its height IS the context width -- a WIN-byte window tokenizes to at most WIN tokens. The census's MAXLEN promote-to-wire (CENSUS.md:415) records why it may not be a free literal: at self_organize.py:1586 the transformer arm does `p = torch.arange(L).clamp(max=s.maxlen - 1)`, so a context wider than a hardcoded 512 silently gives every position past 511 ONE shared embedding -- no error, no report line, a model that cannot tell those positions apart. The same file already derived the signature encoder's table from the window ('ENC_POS_MAX': ('WIN',), :87) while leaving the LM's a literal: one fact declared two ways in one file. LOCAL AND SINGLE-SOURCE, which is unusual and deliberate: the census's reason says the value 'arrives d_-prefixed from DATA's window lever', but no row in the census gives DATA a width -- WIN became LM_CTX (CENSUS.md:344) -- so both ends are LM's and there is no edge to book (lm/levers.py:143-152 reaches the same conclusion). What the row buys is not arithmetic but the refusal of a second literal: `grep -rn d_ src/` finds the height, and lever.py will not let anyone declare a lever that shadows it.

--- DECLARED, REDUCIBLE (4) ---
  Couplings this design chose. A later design may un-choose them, which is why each says what
  the receiving package would have to own instead.

  FAB.slots
    -> DOM.d_expert_slots = 4096  [slots]
       why: The domain id namespace is bounded by the expert slot pool: a domain that cannot be given a slot cannot be routed to. In the old tree this was a computed default -- MAX_DOMAINS = _i('MAX_DOMAINS', _i('FAB_NMAX', 4096)) at self_organize.py:598 -- which had three consequences. FAB_NMAX was entered into the read audit on every run whether or not it mattered; the same name was ALSO read as _i('MAX_DOMAINS', 32) at :4874 when sizing the memory source census, so one knob had two defaults 128x apart; and that was only legal because MAX_DOMAINS sat in _DERIVED and was exempt from the default-mismatch refusal. Worse in practice than in principle: every launcher set MAX_DOMAINS=1000000 while FAB_NMAX sat at 64, so two populations designed as duals ran 15,625x apart and dom_exp affiliation mapped hundreds of domains onto each expert (notes 05_ERRORS E1.7/E10.32). This is the census's MAX_DOMAINS promote-to-wire (CENSUS.md:208), landing on DOM. It is marked reducible because domains could legitimately own a smaller namespace than the slot pool; what they may not do is own a DIFFERENT one silently.

  FAB.slots
    -> MEM.d_source_slots = 8192  [entries]
       why: The memory source census must have a row per source that can appear, and sources are domains. It was sized max(64, MAX_DOMAINS * 2) at self_organize.py:4874 -- reading MAX_DOMAINS with the WRONG default (32), so the table was 64 rows wide on every default run while memory.py's own docstring records 125 source ids on a real one, and the fix that clamped ids into the 64-wide table would have re-broken it at exactly the scale it was written for. This is the SECOND landing of the census's MAX_DOMAINS promote-to-wire, which names both (CENSUS.md:208: 'it lands on DOM as d_expert_slots and on MEM as d_src_hint'); the field is named d_source_slots because memory/levers.py:69 declares that spelling as what it expects to receive. The formula is the shipped one; only its input was wrong. Reducible: a census that grows on demand needs no bound at all, and that is the better repair when it is written.

  CKPT.dir
    -> TOK.d_vocab_save_path = ''  [path]
       why: Where this run SAVES its own vocabulary is a property of its checkpoint, not a knob. The census's TOKENIZER_PATH promote-to-wire (CENSUS.md:306) is exactly this: one declared knob with a shared default of data/dyntok.json 'which belongs to whichever run wrote it last', so concurrent arms overwrote each other (ISSUES.md:1501, :285, :768). The old tree had already split the write side out by hand as `_TOK_SAVE = SAVE_CKPT + '.dyntok.json'` (self_organize.py:1010-1012), and that rule is the compute here, so a run's vocabulary lands beside its own checkpoint. Empty in, empty out: CKPT_DIR='' means saving is off entirely (ckpt/levers.py:143), and a save target computed from it would otherwise be the file '.dyntok.json' in whatever directory the run happened to start in. Reducible: a checkpoint format that carried the vocabulary inside itself would need no path at all.

  CKPT.resume
    -> TOK.d_vocab_read_path = ''  [path]
       why: TWO FIELDS, NOT ONE, AND THE SPLIT IS THE POINT OF THE PROMOTE. TOKENIZER_PATH had two jobs -- 'the file a resume READS its parent's vocabulary from, and the file the run SAVES its own to' -- and conflating them made a run overwrite its parent's vocabulary; ckpt/levers.py:84-97 says plainly that a single d_vocab_path would re-conflate what the promote exists to separate. The read path is the parent's SAVE target under the same rule, which is the repair the sibling-guess heuristic at self_organize.py:1215-1222 never made: on the supported RESUME=runs/x/ckpt.pt form it guessed runs/x/ckpt.dyntok.json, that file did not exist, and it fell through to the shared data/dyntok.json (ISSUES.md M19). A resume must reuse the saved vocabulary or 'the restored embedding table would be indexed by a DIFFERENT vocabulary' (:1226-1227). Empty resume, empty path: there is no parent to read.

--- package graph ---
  CAP -> FAB, TOK
  CKPT -> TOK
  FAB -> DOM, MEM
  LM -> TOK
  OPT -> FAB, TOK

  Packages that only receive appear as targets and never as keys. That asymmetry is the
  point: a sink cannot leak onward, and affects() is one hop.

--- considered and rejected ---
  A coupling with no nameable reason is not a wire; it is a lever the receiver should own.

  RUN.seed -> every package's d_seed
       why not: The run seed does reach every package, but what a package needs is rng.derive_seed(name, seed), which is per-subsystem and keyed by the package's own name. Wiring it would put one near-identical edge per package into the graph and still not stop a package from deriving under the wrong name. The check that catches that is rng.issued(), which records every stream handed out, so a subsystem with zero draws reads armed-but-inert and a subsystem that never asked does not appear at all -- two different statements the report must be able to make (G4).

  RUN.epochs -> OPT.d_lr_horizon
       why not: Rejected because it IS the defect. EPOCHS setting both the run length and the cosine horizon means two runs differing only in EPOCHS are two different learning-rate experiments, which is why units.Epochs says in as many words that it is never a schedule horizon. OPT owns its horizon as a declared lever; a run that wants them to agree sets both, and the report can then say so.

  SIG.d_signature_width_bytes from LM.ctx x the measured bytes/token
       why not: Not resolvable at assemble: bytes_per_token is MEASURED on the corpus the tokenizer has not seen yet, and Config freezes when build() returns, so there is no late wire and there must not be one -- a Config that can still be written after startup is a Config the report cannot claim the run used. derive.signature_width_bytes is the single named function instead; the sig package calls it once, keeps the answer, and must not recompute it as the vocabulary grows. That is not a style preference: the old tree resolved the width in two places from one knob whose zero meant max(WIN, int(WIN*bpt)) = 614 bytes at self_organize.py:5675 and max(1, SIG_WIN) = 1 byte at :3919, so every eval-path routing decision in every report was made on a one-byte signature.

  EVAL.gist -> the eval-path signature width
       why not: The census's sixth promote-to-wire (EVAL_GIST, CENSUS.md:66) and the ONE that cannot become a Coupling, for exactly the reason the row above gives. EVAL_GIST was never a lever: it selected between two constructions of a value SIG owns, and both branches were wrong -- at the shipped default `_eval_sig` (:3907-3927) built the eval signature from `[-max(1, SIG_WIN):]` with SIG_WIN=0, i.e. ONE BYTE, while training encoded >= 256; set to 0 it returned an all-zero gist that ranks the population identically for every window. The census's replacement is 'one signature, its width resolved once, and eval receives it as a d_-prefixed wire' -- and that width is derive.signature_width_bytes(win_tokens, bytes_per_token), whose second argument is MEASURED on a corpus the tokenizer has not seen when build() freezes. So the promote is honoured by the derive-and-keep discipline, not by a row in this table, and saying so here is the point: a promote-to-wire that quietly became nothing is indistinguishable from one nobody noticed.

  MEM.cap as its own lever
       why not: The most tempting one, and the reason MEM.d_capacity exists. A declared capacity next to a declared quota and a declared owner count is three numbers for two degrees of freedom; the third is discarded at runtime by whichever line runs last, and in the old tree that line was memory.py:36.

--- what a coupling's value may depend on ---
  Every value above is computed from the levers named in its src, through a view that
  raises on an undeclared read, by a function whose free names are checked at declaration
  against this list and nothing else:

  derive
       spine.derive -- the pure derived quantities, one named function each, replayed case by case against the P0 oracle by tests/test_derive.py. A compute calls derive.f(...) rather than restating f inline, because a formula written twice is the SIG_WIN defect: one knob resolved in two places, 614 bytes in training and 1 byte in eval.

  Steps
       spine.units.Steps -- the clock constructor a compute needs in order to hand derive.flush_period a cadence that carries its kind. A bare int there is the 16x-slow clock that pinned the population for 43,645 real steps while the clock read 2,650. NO ROW BELOW REACHES IT TODAY: both cadences this table converts turned out to be denominated in WINDOWS, not steps (see FAB.d_manage_period). It stays because a genuinely step-denominated cadence -- an LR-schedule horizon -- is the next coupling of this shape, and because removing it would make derive.flush_period unreachable from any compute while derive.flush_period_windows is reachable, which reads as a claim that the steps form is wrong rather than unused.

  Windows
       spine.units.Windows -- the same constructor for the kind the loop counter actually counts. `step` advances once per window (`i += WIN; step += 1`, self_organize.py:6796 and :7708) and every management gate compares against it, so MANAGE_EVERY and the capacity valve's pin threshold are Windows and are handed to derive.flush_period_windows. Passing them through the Steps form instead is the conflation this whole module is written against, one layer up.

  _owner_blocks
       the one pure helper local to this file, defined immediately above the table because two couplings need the same fold and a fold written twice can disagree with itself. Its own free names are checked by this same rule, transitively -- an allowlisted helper is not a hole.

  int
       narrowing a lever to the integer the receiving package's arithmetic needs.

  max
       the floors the shipped formulas carry: max(64, ...) in the memory source census, max(1, ...) in the effective batch.

  min
       the fold the shipped formulas carry: min(slots, owners). Reached through _owner_blocks and not from a compute directly, and listed because this check follows helpers.

--- the ledger as the isolation sweep's oracle sees it ---
=== coupling graph: 10 wires of 25 budgeted ===
SRC                                  DST                    VALUE           UNIT     WHY
----------------------------------------------------------------------------------------
FAB.slots                            DOM.d_expert_slots     4096            slots    The domain id namespace is bounded by the expert slot pool: a domain that cannot be given a slot cannot be routed to. In the old tree this was a computed default -- MAX_DOMAINS = _i('MAX_DOMAINS', _i('FAB_NMAX', 4096)) at self_organize.py:598 -- which had three consequences. FAB_NMAX was entered into the read audit on every run whether or not it mattered; the same name was ALSO read as _i('MAX_DOMAINS', 32) at :4874 when sizing the memory source census, so one knob had two defaults 128x apart; and that was only legal because MAX_DOMAINS sat in _DERIVED and was exempt from the default-mismatch refusal. Worse in practice than in principle: every launcher set MAX_DOMAINS=1000000 while FAB_NMAX sat at 64, so two populations designed as duals ran 15,625x apart and dom_exp affiliation mapped hundreds of domains onto each expert (notes 05_ERRORS E1.7/E10.32). This is the census's MAX_DOMAINS promote-to-wire (CENSUS.md:208), landing on DOM. It is marked reducible because domains could legitimately own a smaller namespace than the slot pool; what they may not do is own a DIFFERENT one silently.
FAB.slots                            MEM.d_owner_blocks     64              count    Memory ownership is expert_id % n_own, and n_own was min(FAB_NMAX, MEM_OWNERS) at self_organize.py:4873. The fold is irreducible: expert ids run to the slot count (4096) while the store has MEM_OWNERS (64) partitions, so 32 experts shared each partition and 'per-expert memory' was per-64-buckets memory. Blocks in excess of the slot count are unreachable by the modulo and their quota is capacity that exists and can never be written.
FAB.slots                            MEM.d_capacity         8192            entries  Capacity is DERIVED, not declared: a partitioned store holds blocks x quota entries and has no size independent of its partition. The old tree declared it anyway and memory.py:36 then silently overrode it -- 'if self.n_own > 1: cap = self.n_own * self.quota' -- so a requested MEM_CAP of 200,000 became 64 x 128 = 8,192, a 24x shrink recorded as E7.40 with no line in any log. This is the census's MEM_CAP promote-to-wire (CENSUS.md:249); after it the operator sizes the store through quota and owners, and 200,000 is no longer a number anyone types. Deriving it here means the number that gets discarded is the one nobody wrote.
FAB.slots                            MEM.d_source_slots     8192            entries  The memory source census must have a row per source that can appear, and sources are domains. It was sized max(64, MAX_DOMAINS * 2) at self_organize.py:4874 -- reading MAX_DOMAINS with the WRONG default (32), so the table was 64 rows wide on every default run while memory.py's own docstring records 125 source ids on a real one, and the fix that clamped ids into the 64-wide table would have re-broken it at exactly the scale it was written for. This is the SECOND landing of the census's MAX_DOMAINS promote-to-wire, which names both (CENSUS.md:208: 'it lands on DOM as d_expert_slots and on MEM as d_src_hint'); the field is named d_source_slots because memory/levers.py:69 declares that spelling as what it expects to receive. The formula is the shipped one; only its input was wrong. Reducible: a census that grows on demand needs no bound at all, and that is the better repair when it is written.
OPT.batch_windows                    FAB.d_manage_period    Flushes(500)    flushes  MANAGE_EVERY is a cadence on the WINDOW counter, and five call sites consume it per FLUSH. The management gates above the batch early-out test `step % MANAGE_EVERY == 0` (self_organize.py:6716, :6764, :6768) where `step` advances once per window (`i += WIN; step += 1`, :6796 and :7708); the sites BELOW the early-out run once per flush and wrote the conversion inline as `_nbwd % max(1, MANAGE_EVERY // max(1, BATCH_W))` at :6819, :6836, :6961, :6988, :7077 and :7325 -- one number compared against two clock kinds in one file. Irreducible: a cadence in windows handed to a block that counts flushes has no meaning until the batch width is known, which is why the value is a Flushes clock and not an int -- an int compares fine against a threshold in the wrong unit. UNIT RESOLVED HERE: this row used to read `derive.flush_period(Steps(r['FAB'].manage_every), ...)` and its reason said 'MANAGE_EVERY is written in STEPS'; the census (CENSUS.md, FAB family) and fabric/levers.py:648 both type it Windows, and the source agrees with them, so the Steps assumption is withdrawn and the conversion is derive.flush_period_windows.
OPT.batch_windows + CAP.pin_windows  FAB.d_cap_lift_period  Flushes(20000)  flushes  The measured case for this whole mechanism. The capacity valve's pin clock ticked per flush against a threshold in windows, so GROW_CAP_EVERY=20000 silently demanded 320,000 windows at BATCH_W=16 and 640,000 at 32: the population sat pinned for 43,645 real ticks while the clock read 2,650 (= 42,400/16) and the report said 'reached the cap but never held it long enough' -- a true sentence about a false clock. A second gate one layer up then compared fabgrow.n (calls) to the same threshold and lifted nothing for a further whole round, the first fault masking the second. The knob is now CAP.pin_windows (census GROW_CAP_EVERY -> CAP_PIN_STEPS, re-typed and re-named to CAP_PIN_WINDOWS at capacity/levers.py:305 because the counter it is compared against is `step`). CAVEAT THE VALVE PORT MUST SETTLE, recorded rather than papered over: derive.pin_tick still types its accumulated clock as Steps, so a Windows threshold and a Steps clock cannot meet -- capacity/levers.py:88-108 sets out the two legal repairs, and applying both at once fires the valve 16x too EARLY. This row converts the threshold and nothing else.
OPT.batch_windows + CAP.pin_windows  TOK.d_cap_lift_period  Flushes(20000)  flushes  The vocabulary soft cap is lifted by the same valve on the same clock, and it was blocked by the same units fault: round6 measured 0 vocabulary lifts on gc_real, and gc_fast and gc_loose lifted identically (6 each, same first step 32047), which proves the plateau condition was never the blocker -- GROW_CAP_EVERY=20000 against a 60k-step run was. Wired separately from the fabric's period because the two caps are lifted by two mechanisms and a shared field would make one of them read a value the other's package owns.
LM.vocab_slots                       TOK.d_vocab_ceiling    4096            entries  emb.weight and head.weight have exactly this many rows, so the vocabulary the tokenizer is allowed to mint into is the model's row count: one number named twice, not two numbers that happen to agree, and no interface makes them independent. Getting it wrong is not a soft failure -- the resume geometry gate at self_organize.py:4442-4468 exists because a checkpoint built at one width cannot load into a model built at another, and the softer form (rows minted by the tokenizer but never present in the head) is the LOSS_MASK_DEAD family, where dead rows scale with VMAX and quietly take probability mass. DIRECTION CORRECTED HERE: this row read `src='TOK.vmax', dst='LM.d_softmax_width'`, and TOK has no lever called vmax -- the census gives VMAX to LM as LM_VOCAB_SLOTS and says in as many words that 'TOK receives it as the wire d_vocab_ceiling' (CENSUS.md:323), which is what lm/levers.py:127-141 and tok/levers.py:87 both record as the outstanding repair. Left as it was, importing the real packages made build() raise 'TOKLevers has no lever vmax' -- the mechanism working, on a row that named an owner nobody had.
CKPT.dir                             TOK.d_vocab_save_path  ''              path     Where this run SAVES its own vocabulary is a property of its checkpoint, not a knob. The census's TOKENIZER_PATH promote-to-wire (CENSUS.md:306) is exactly this: one declared knob with a shared default of data/dyntok.json 'which belongs to whichever run wrote it last', so concurrent arms overwrote each other (ISSUES.md:1501, :285, :768). The old tree had already split the write side out by hand as `_TOK_SAVE = SAVE_CKPT + '.dyntok.json'` (self_organize.py:1010-1012), and that rule is the compute here, so a run's vocabulary lands beside its own checkpoint. Empty in, empty out: CKPT_DIR='' means saving is off entirely (ckpt/levers.py:143), and a save target computed from it would otherwise be the file '.dyntok.json' in whatever directory the run happened to start in. Reducible: a checkpoint format that carried the vocabulary inside itself would need no path at all.
CKPT.resume                          TOK.d_vocab_read_path  ''              path     TWO FIELDS, NOT ONE, AND THE SPLIT IS THE POINT OF THE PROMOTE. TOKENIZER_PATH had two jobs -- 'the file a resume READS its parent's vocabulary from, and the file the run SAVES its own to' -- and conflating them made a run overwrite its parent's vocabulary; ckpt/levers.py:84-97 says plainly that a single d_vocab_path would re-conflate what the promote exists to separate. The read path is the parent's SAVE target under the same rule, which is the repair the sibling-guess heuristic at self_organize.py:1215-1222 never made: on the supported RESUME=runs/x/ckpt.pt form it guessed runs/x/ckpt.dyntok.json, that file did not exist, and it fell through to the shared data/dyntok.json (ISSUES.md M19). A resume must reuse the saved vocabulary or 'the restored embedding table would be indexed by a DIFFERENT vocabulary' (:1226-1227). Empty resume, empty path: there is no parent to read.
```
