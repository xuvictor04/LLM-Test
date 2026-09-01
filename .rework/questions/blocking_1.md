Ordered by how hard they block. "Blocking" = two readings of the question produce **different code**, so P4 cannot proceed by writing the obvious thing.

### BLOCKS P4

**Q-OPT-7 — `OptState` names neither AdamW.** Hardest block in the slice, and it blocks **three** bodies plus one deferral. P4 cannot write `SIG.train_step` or `SIG.warm_up` (both take "THE ENCODER OPTIMIZER") without a field name, cannot write `OPT.maybe_step` step 5 under Q-OPT-6(a) (which requires addressing one optimizer and not the other), and `WORLD.manage` stays deferred for want of `add_param_group`. `compose.py:1707-1709` states the failure mode of guessing: an AttributeError months later. One line closes all four.

**Q-OPT-6 — does `maybe_step` step the encoder?** The two readings are literally different code in two packages. Under (a), `maybe_step` writes `lr` to both and steps one, and `SIG.train_step` owns the encoder step including its floor gate. Under (b), `SIG.train_step` computes and backwards only, and three declared SIG levers plus the `SIG.d_idle_cadence` wire become dead. An implementer cannot pick by inspection — the frozen docstrings currently disagree with each other (`opt/api.py:212` says both; `sig/api.py:136` says SIG's floor skips the step).

**Q-LM-12 — what produces `obs_emb`.** The argument has no producer, and `compose.py` gives two incompatible accounts in one file (`:838-845` says it is open; `:1386-1389` says the loop applies `model.emb`). The second **crashes under `LM.compose=1`**. P4 writing `WORLD.loss_terms` must be told which tensor arrives, and if the answer is `LM.embed` then a frozen surface gains an entry point — cheap now, expensive after P4 writes against 121 signatures.

**Q-OPT-4 — `build(resume=)` vs `load_state`.** Two readings, two bodies: either `build` does restore work (and needs its own counters, or it is a silent second path) or it ignores the argument. If the answer is "drop the parameter", that is a signature change and must land before P4. The `param_group_shape` half is independently blocking in a smaller way: as written, `load_state`'s L50 refusal is untrippable, so P4 would ship an armed-looking guard that cannot fire.

**Q-LM-9 — the third dropout site.** Blocks `LM.build_model`, `LM.encode` and `LM.decode` together, because the decision is *where the `nn.Dropout` module is applied*. Writing the obvious thing (port `s.drop(h)` into `encode`) silently commits the tree to dropped-out memory keys and a dropped-out router input, on the one lever the report tells the operator to raise.

**Q-OPT-3 — partially, and only the instrument.** The clip question itself does **not** block: without a ruling P4 writes no clipping, which is what the tree already says. What blocks is the **measurement site**: `OPT.counters` claims a per-step gradient norm it cannot compute (grads are zeroed by then), so an implementer following the docstring ships a run reporting 0.0. That is one docstring clause, but two readings produce different code and one of them is silently wrong.

### DOES NOT BLOCK P4

**Q-OPT-1 — the `NOT_WIRES` row.** Pure data in a table nothing in P4 reads. `render()` and A4 consume it; the mechanism bodies do not.

**Q-OPT-2 — the optimizer-step counter.** Already adopted and unit-enforced in three coordinated places (`maybe_step` step 1, `lr_at`'s parameter, `derive.opt_steps_from_windows`). P4 writes the obvious thing and it is the right thing. Only the P9 accounting is open, and P9 is after P4.

**Q-OPT-5 — the projection vs the measurement.** The decision "resolve once, do not re-project" is already written into `OPT.build`'s docstring, so P4 proceeds. What is open is a **report line** joining two already-declared counter surfaces, which is a root-side addition with no signature cost and can land any time before P9.

**Q-CLOCK-1 — retiring the two reporting wires.** Both answers run and the tests are green either way. It affects two `_ =` reads and their `WIRES READ` lines, and K5 makes the edit atomic whenever it happens. It is a ledger decision, not a mechanism decision — though it is cheapest to make **before** `FAB.grow_check`, `TOK.vocab_state` and `CAP.counters` get bodies, so the "0 lifts" sentence is written once in the place that survives.


--- CROSS SLICE ---

Every place my answers touch another slice's question. Named by question, with what the dependency actually is.

### Hard dependencies — my answer is incomplete without theirs

**Q-OPT-7 ↔ WORLD.manage's deferral (WORLD/CKPT slice).** `compose.py:1266-1271` says `WORLD.manage`'s `add_param_group` is blocked by *the identical hole* and that "**one field on OptState closes both**". My recommendation (name `base` and `encoder`) supplies the producer that deferral is waiting on, which means whoever rules on `WORLD.manage` must **also** amend or remove the `add_param_group` clause of its deferral reason — K12 checks that a deferral reason names the arguments with no producer, so leaving it stale is a live failure. **If the WORLD slice resolves `WORLD.manage` independently by inventing an accessor, we will have made this decision twice, differently.**

**Q-OPT-6 ↔ SIG.train_step / SIG.warm_up (SIG slice).** My recommendation (a) puts the encoder step wholly inside SIG and makes SIG's `floor_kinds` gate load-bearing. If the SIG slice concludes that `train_step` should compute-and-backward only, we contradict directly and three SIG levers (`train_every`, `train_every_idle`, `dense_window`) plus the `SIG.d_idle_cadence` wire hang on the difference. **The synthesis pass must join these two before P4 touches either package.**

**Q-OPT-4 ↔ Q-CKPT-2 (CKPT slice).** Both live on the resume path and both concern what the save side records versus what the load side refuses against. My `param_group_shape` finding (`OPT.state_dict` does not declare a value `OPT.load_state:297` refuses on — `compose.py:1029-1033`) is structurally the **same defect** Q-CKPT-2 records for the geometry manifest and the FAB/SIG sidecars: a refusal armed against a value nothing produces. Whatever principle Q-CKPT-2 settles on ("the save side computes the same thing the load side compares") should be applied to OPT's row in the same edit. Also: `compose.py:255-261` shows `resume` and `saved` are the **same** `Snapshot.payload`, so any change to how CKPT.load fans out its six spellings touches my answer.

**Q-CLOCK-1 ↔ Q-DERIVE-1 (RESOLVED) and CAP's slice.** My recommendation to delete both rows rests entirely on `CAP.counters` (`capacity/api.py:225-234`) rendering the block-reason histogram beside the pin high-water mark. **If the CAP slice narrows or defers that histogram, my recommendation flips to "keep".** Also touches FAB (`grow_check`'s report line) and TOK (`vocab_state`'s), both of which currently carry the sentence that would move to CAP.

**Q-LM-9 ↔ MEM's key path, and Q-MEM-9.** My recommendation makes `LM.encode`'s return undropped, which changes what `key_fn` writes into the store at `dropout > 0`. This depends on MEM's rekey path re-encoding through the same `key_fn` (so keys stay mutually comparable) — the property the old tree asserted for `KEY_LAYERS` at `self_organize.py:1580-1593`. Q-MEM-9 ("does `maintain`'s probe call `MEM.read`?") is the same family of question one layer down: one path, one set of counters. **If the MEM slice concludes the key path needs its own encode variant, that is a signature change to `LM.encode` and it lands on the LM slice.**

**Q-LM-12 ↔ WORLD.loss_terms and the modality claim (WORLD slice).** My answer adds `LM.embed` and gives `obs_emb` a real producer, which removes the `ROW_ARGUMENTS_ELSEWHERE` entry at `compose.py:1386-1389`. If the WORLD slice instead accepts the hidden (option c), `world/api.py:6-7`'s "a second sense needs only new embedding rows" must be struck — that is goal A's *room for more modalities*, so it is an owner-level claim, not a package edit. Also touches the LM slice via the `compose` lever: my refutation of the root-side `model.emb` join is grounded in `lm/api.py:76-79` (emb is not constructed under compose).

### Softer dependencies — worth naming so nobody re-derives them

**Q-OPT-5 ↔ Q-DATA-8 (DATA slice).** `RunClock.begin_epoch`'s docstring (`train/api.py:150-157`) points at Q-DATA-8 for the `stream_bytes // ctx` vs `len(ids) // ctx` fault. My recommendation reuses `_windows_in_epoch`, so if Q-DATA-8 moves how epoch length is measured, the observed side of my printed comparison moves with it.

**Q-OPT-5 ↔ RUN's report surface (RUN slice).** The printed comparison lands on whatever the root's end-of-run report is — `RUN.bench_summary` or the root's own assembly. No signature change either way, but the RUN slice owns where it prints.

**Q-OPT-3 ↔ the census ledger (whoever owns `.rework/CENSUS.md`).** If the owner overrules and mints `OPT_GRAD_CLIP`, `tests/test_census.py` N2 will fail: `DEPARTURES` is keyed by an existing census row and a clip lever has no ancestor knob. That is a CENSUS.md amendment, which is an owner statement, not a slice's.

**Q-OPT-1 ↔ nothing.** Self-contained in `spine/assemble.py`. Recorded here only so the synthesis pass does not go looking.

### One finding that belongs to no question in my slice

`tests/test_census.py`, `DEPARTURES[("capacity", "GROW_CAP_EVERY")]`, still asserts *"derive.pin_tick still accumulates a Steps clock, so the port is not finished"*. That is **false** as of the 2026-08-30 repair (Q-DERIVE-1) — I verified `pin_tick` refuses `Steps` and `Flushes` at `derive.py:499-512`. N3 checks that a departure still lands, not that its prose is current, so the suite is green and the sentence is wrong. It sits in a test file, so it belongs to whoever owns the CAP/derive slice's follow-through rather than to me; I did not edit it.
