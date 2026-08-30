"""TOK -- the frozen public surface. Signatures only; P4 writes the bodies.

TOK owns one vocabulary and the policy that grows it -- what the run's symbols ARE. Goal A is
measured in units this package sets: bits/byte is per BYTE precisely so a run that changes its
spelling stays comparable with itself, and the largest single effect anywhere in this project's
records is a lever in this file (two arms with identical vocabularies -- 512 minted, 441 used,
0% dead -- differing only in whether re-segmentation fired scored 4.364 against 2.175 held-out
b/B and 26% against 94% real words). Goal B has a tokenizer-shaped version of catastrophic
forgetting that only this package can address: minting the globally most frequent pair re-spells
ALL existing material at once, so a new area should buy vocabulary for itself rather than rewrite
how everything already learned is spelled (`mint_novel`); `freeze_at` is the blunt alternative.

THE CEILING IS NOT OURS. LM.vocab_slots arrives as the wire TOK.d_vocab_ceiling. emb.weight and
head.weight have exactly that many rows, so the tokenizer may never mint an id the model has no
row for. The ceiling is HARD AND COMES FROM THE WIRE ON EVERY PATH, INCLUDING A RESUME; the
`vmax` inside a saved tokenizer file is a recorded fact to reconcile against, never an authority
(DEFECT D-T1: a tokenizer saved full at 2048 came back full at 2048 and refused every candidate
for the whole run, measured as "!! ZERO tokenizer.mint 0 ARMED AND INERT" on the first run that
ever added an area).

TWO PATH WIRES, AND THEY ARE TWO ON PURPOSE. d_vocab_save_path (from CKPT.dir) is where this run
writes its own vocabulary; d_vocab_read_path (from CKPT.resume) is where a resume reads its
parent's. One knob doing both jobs made a run overwrite its parent's vocabulary and made eleven
concurrent smoke arms race for data/dyntok.json (ISSUES M5, L7, M19, M46).

RECORD TYPES RETURNED (P4 defines them; other packages receive them as arguments and call their
methods, which is not an import):
  Vocabulary    id2bytes, seq2id, merges, bytes_per_id, mlbf, maxlen, retired, prov, pair,
                ceiling (hard, from the wire), soft_cap (mutable, from CAP), v0, bytes_per_token;
                methods decode, blen, size, live_size, at_cap
  Segmentation  ids, byte_pos, labels, bytes_per_token
  Due           mint, retok, probation, frozen
  Mint          new_id, left_id, right_id, token_bytes, count
  Judgement     kept, retired_ids, pending, live_size
  RetokEvent    the signal the composition root hands to SIG, MEM, DOM and FAB
"""
from spine.lever import Config


def build_vocabulary(tok: Config, *, area_heads, seed: int, soft_cap=None):
    """Produce the vocabulary the run ENTERS TRAINING WITH, on all three arms of tok.mode.

    mode="bytes"   -> the 256 byte ids, no merges; nothing else in this file is reachable.
    mode="fixed"   -> build to tok.seed_vocab as the CEILING as well as the target, then never mint.
    mode="online"  -> build to tok.seed_vocab as a TARGET and keep minting during training.
    The three-state lever replaces two booleans encoding three states, which is why GROW_PASSES was
    unreachable at TOK_ONLINE=1 and SEED_VOCAB/SEED_PASSES unreachable at TOK_ONLINE=0 while the
    audit reported the unset one as an operator typo (ISSUES L20).

    If d_vocab_read_path is non-empty and exists, the parent's merges are REPLAYED instead of
    built -- a resume MUST reuse the saved vocabulary or the restored embedding table is indexed by
    a different vocabulary. The file's recorded vmax/min_pair/max_tok/dropout DO NOT WIN: this
    package holds one declaration, the levers, and any disagreement is printed as a reconciliation
    line and counted (ISSUES M80, L20 -- a resume setting MIN_PAIR=200 ran with the parent's value
    and the audit then printed "NOTHING READ THESE" naming a knob that was set and ignored).

    Otherwise: tok.build_passes tally-and-mint passes over
    b"".join(h[:tok.build_bytes] for h in area_heads), breaking early when a pass mints nothing.
    The counting segmentation applies tok.dropout, drawing from rng_for("tok.dropout", seed) --
    never the process-global `random`, which shifted the RNG stream of the entire run (ISSUES L69).
    bytes_per_token over the build sample is measured with derive.bytes_per_token(len(sample),
    len(ids)) and returned on the Vocabulary, because it is what DATA's splice gate and SIG's width
    need and THERE IS NO SECOND ESTIMATOR (ISSUES H16: the mean-over-vocabulary-entries estimator
    read 1.50 against 1.85 as used, and its error changes SIGN with vocabulary size -- the axis
    those runs were compared along).

    soft_cap is CAP's starting vocabulary cap (the old GROW_CAP_VOCAB0, self_organize.py:5262);
    None means "start at the hard ceiling". min(soft_cap, ceiling) is what minting compares against.

    RECEIVES: area_heads <- DATA (already capped by DATA.corpus_cap; TOK applies build_bytes on
    top -- two genuinely different quantities, one bounds the build and one bounds the run);
    seed <- RUN.seed; soft_cap <- CAP.
    RETURNS: Vocabulary.

    LEVERS READ: mode, seed_vocab, build_passes, build_bytes, min_pair, max_bytes, cand_window,
                 mint_pmin, mint_novel, dropout
    WIRES READ: d_vocab_ceiling, d_vocab_read_path
    DID IT FIRE: tok.build_pass, tok.build_mint, tok.build_converged, tok.load_reconciled,
                 tok.v0 -- the ACHIEVED size at the start of training, recorded once and NEVER
                 computed by subtracting seed_vocab, which is what the old DID IT FIRE row did and
                 why it over-reported mints on any corpus that converged below target
                 (self_organize.py:1274-1281)
    """
    tok = tok.owned_by("TOK")
    _ = (tok.d_vocab_ceiling, tok.d_vocab_read_path)     # WIRES READ HERE -- see the docstring
    raise NotImplementedError(
        "TOK.build_vocabulary: P4 (tok) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section TOK.")


def tokenize(tok: Config, vocab, data, labels=None, *, start=0, regularize=False, seed=0):
    """Segment bytes with the vocabulary AS IT NOW STANDS. This ONE function serves the initial
    segmentation, every in-loop re-segmentation, the final one before eval, and the held-out encode.

    Returns Segmentation(ids, byte_pos, labels, bytes_per_token) where byte_pos[k] is the BYTE
    offset of token k -- the stable coordinate that lets every downstream metric survive a
    re-segmentation, and the surface ISSUES H20 needs: the run-boundary probe drew window starts in
    TOKEN coordinates off a validation text whose length shrinks as the vocabulary grows, so `prev`
    and `now` were measured on DIFFERENT windows. start>0 segments only the unconsumed tail:
    minting is append-only, so an already-emitted prefix keeps its meaning.

    A RE-SEGMENTATION WHOSE MATCH TABLE HAS NOT MOVED since the last one is REFUSED here and
    counted as tok.retok_noop, not performed: the rebuild is byte-identical but the side effects
    are not, and the measured cost of not refusing was 2.189 b/B and 68 points of word quality
    (23 retoks, 22 adding zero tokens). The invariant stamped is (size, len(seq2id)) and NOT size
    alone, because retire() changes the match table without changing vocab_size.

    regularize=True applies tok.dropout (skip an available merge with that probability, falling
    back toward the raw byte, which is always in the vocabulary); it is used for the TRAINING
    stream and never for held-out text, generation, or the final segmentation, which must be
    deterministic. THE SKIP TEST ABOVE IS DISABLED WHENEVER dropout > 0, because the emitted stream
    is then no longer a deterministic function of the vocabulary -- see FOR THE OWNER Q-TOK-3.

    LEVERS READ: mode, dropout
    WIRES READ: none
    DID IT FIRE: tok.segment, tok.retok, tok.retok_noop (reported SEPARATELY so a frozen run's 39
                 no-op re-tokenizations read as skipped rather than as activity), tok.dropout_skip
                 (unreachable at dropout=0.0, the default), tok.byte_fallback
    """
    tok = tok.owned_by("TOK")
    raise NotImplementedError(
        "TOK.tokenize: P4 (tok) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section TOK.")


def on_window(tok: Config, vocab, ids, *, step):
    """One window of the training loop, and THE ONLY PLACE THIS PACKAGE'S CLOCKS ARE COMPARED.

    Tallies the adjacent pairs of `ids` into the vocabulary's tally unless minting is frozen, then
    answers what is due at this window: Due(mint, retok, probation, frozen).

    EVERY CADENCE IS ELAPSED-SINCE-LAST-FIRE AGAINST `step`, WHICH ADVANCES ONCE PER WINDOW, never
    `step % N == 0`: everything after the batch early-out runs only on flush steps, which land on a
    fixed residue mod batch_w, so a modulo cadence asks for a simultaneous solution to two
    congruences that usually has none. Simulated over 200k windows, minting fired 999 times at
    batch_w=1 and ZERO times at batch_w in {2,8,15,16,32} (self_organize.py:5266-5279).

    THE THREE CADENCE KEYS ARE DISTINCT AND MUST STAY DISTINCT. _due RECORDS the step and returns
    True, so asking under a shared key CONSUMES the event: probation sharing the grow key means
    minting never fires at all, and asking twice in one if/elif killed BOTH retok branches for
    three 18-epoch runs (self_organize.py:7586-7590, :7729-7736). There is ONE call, so a cadence
    cannot be asked twice.

    freeze_at: at step >= tok.freeze_at (and freeze_at != 0) minting stops permanently and
    Due.frozen is True from then on. Retok is still asked for on its own cadence.

    RECEIVES: step <- RUN's RunClock, as units.Windows.
    RETURNS: Due.

    LEVERS READ: mode, grow_every, retok_every, freeze_at, probation_deadline, probation_uses
    WIRES READ: none
    DID IT FIRE: tok.tally, tok.due_mint, tok.due_retok, tok.due_probation, tok.mint_frozen_at
                 (the step, or unreachable when freeze_at = 0)
    """
    tok = tok.owned_by("TOK")
    raise NotImplementedError(
        "TOK.on_window: P4 (tok) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section TOK.")


def mint_burst(tok: Config, vocab, *, step):
    """Mint up to tok.grow_burst tokens from the current tally and return what was minted, as
    a list of Mint(new_id, left_id, right_id, token_bytes, count).

    THIS PACKAGE NEVER TOUCHES A MODEL TENSOR. The composition root hands these to LM (new-row init
    / composer set_vocab+note_born) and to SIG (encoder-row init). That reach used to live INSIDE
    the mint loop (self_organize.py:7625-7705) and it is why an ablation flag about warm-starting
    could leave every composed token identical: with WARMSTART=0 and TOK_COMPOSE=1 the mint still
    happened but set_vocab was never called, so the composer had no row for the new id and every
    token minted that way got the identical composite -- the fresh-indistinguishable-row the
    ByteComposer exists to abolish, reintroduced by an ablation flag about something else.

    SELECTION, IN ORDER: materialize tok.cand_window candidates (floored at 2 -- at a window of 1
    there is nothing to walk to and one unmintable top pair ends the burst); if tok.mint_novel > 0,
    re-rank by (c - seen)/(1+seen)**novel so minting follows NEW material; drop candidates below
    tok.min_pair (with the early exit disabled after a novelty re-sort, because the list is no
    longer frequency-ordered); if tok.mint_pmin > 0, skip candidates whose p(b|a) is below it.

    THE GATE MAY REORDER AND MAY NEVER PREVENT. As a hard gate it left 609 of 2048 rows (29.7%)
    never minted and scored 3.600 b/B against a ~1.96 baseline. If nothing in the window passes,
    take the most frequent candidate clearing min_pair, SCANNED IN FREQUENCY ORDER HELD SEPARATELY
    from the re-ranked list -- the shipped fallback re-used the novelty-sorted list, so at
    mint_novel > 0 it took the most NOVEL one (ISSUES:573). A candidate refused for max_bytes or
    for already existing is SKIPPED, not returned as "nothing left to mint": that hole stalled a
    vocabulary at 658/4000 with 1866 pairs still above min_pair. A candidate whose bytes already
    exist at a RETIRED id is a REINSTATEMENT -- put the old id back in the match table, mint
    nothing -- because retire() pops from seq2id and leaves id2bytes, so re-minting creates two ids
    with identical bytes and splits the statistics between them (ISSUES M79).

    A refusal at min(soft_cap, ceiling) is its own counter, not silence.

    RECEIVES: step <- RUN's RunClock, as units.Windows.
    RETURNS: list[Mint].

    LEVERS READ: grow_burst, min_pair, max_bytes, cand_window, mint_pmin, mint_novel
    WIRES READ: d_vocab_ceiling
    DID IT FIRE: tok.mint, tok.mint_gate_pass, tok.mint_gate_block, tok.mint_gate_forced,
                 tok.mint_novel_reranked (unreachable at mint_novel=0.0, the default),
                 tok.mint_skipped, tok.mint_widened, tok.mint_rescued, tok.mint_reinstated,
                 tok.mint_ceiling_refused (the row that read ZERO ... ARMED AND INERT on the first
                 add-an-area run), tok.mint_exhausted
    """
    tok = tok.owned_by("TOK")
    _ = tok.d_vocab_ceiling                              # WIRE READ HERE -- the hard row count
    raise NotImplementedError(
        "TOK.mint_burst: P4 (tok) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section TOK.")


def judge_probation(tok: Config, vocab, *, step, appearances, residual_ratio=None):
    """Judge every token whose probation has resolved -- it has EARNED tok.probation_uses
    appearances, or step - birth >= tok.probation_deadline and it has not. JUDGING ONLY ON REACHING
    THE THRESHOLD CAN NEVER RETIRE ANYTHING, so the deadline IS the test.

    tok.probation_by == "use":   keep iff earned.
    tok.probation_by == "embed": keep iff earned AND residual_ratio[t] >= tok.probation_residual.
      The two compose deliberately: a residual near zero because the token was never seen says
      nothing about the merge. If residual_ratio is None the embed arm is UNREACHABLE and SAYS SO
      through its Gate -- it must never silently fall through to the "use" test while the banner
      reports "judged by embed", which is what happened at TOK_PROBATION_BY=embed with
      TOK_COMPOSE=0 (ISSUES M41).

    RETIREMENT IS SOFT: the bytes are popped from the match table so segmentation stops producing
    the token and its text re-segments to its parts, while the id and its embedding row stay. Ids
    are POSITIONAL -- merges[] is replayed in order and every later token is built on this one's
    index -- so removing an id would renumber the vocabulary and invalidate every checkpoint.
    Retired ids are returned in the Judgement so LM can keep them in the dead-row accounting: a
    retired id sits BELOW vocab_size and sailed straight through a suffix-only mask_dead (on the
    probation arms 217 and 224 of 256 minted tokens were retired that way).

    RECEIVES: appearances <- the training loop's per-token appearance counter (the old _tok_seen,
    self_organize.py:6804), the ONE shared mutable tensor in this contract; residual_ratio <- LM's
    MintReport (||delta[nid]|| / ||composite[nid]||), which cannot be a build-time wire because it
    is read off a live tensor.
    RETURNS: Judgement.

    LEVERS READ: probation_uses, probation_deadline, probation_by, probation_residual
    WIRES READ: none
    DID IT FIRE: tok.probation_judged, tok.probation_kept, tok.probation_retired,
                 tok.probation_pending (all unreachable at probation_uses = 0, the default),
                 Gate tok.probation_embed -- prints "unreachable (no residual_ratio supplied)"
                 rather than silently running the "use" test
    """
    tok = tok.owned_by("TOK")
    raise NotImplementedError(
        "TOK.judge_probation: P4 (tok) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section TOK.")


def lift_vocab_cap(tok: Config, vocab, *, to: int):
    """Raise the SOFT vocabulary cap to min(to, d_vocab_ceiling) when the capacity valve decides the
    population has earned it, and return the cap now in force.

    AN EVENT, NOT A PERIOD, and that is this contract's answer to the clock-kind clash. Every
    cadence this package owns is Windows; the valve's own clock is CAP's. CAP calls this function
    when it lifts, so no period crosses the boundary, no Windows/Flushes conversion is needed, and
    the lift becomes COUNTABLE (tok.cap_lift) instead of inferred. The old form mutated TOK.vmax
    from inside the loop (self_organize.py:7427-7435). See FOR THE OWNER Q-CLOCK-1 on the fate of
    the TOK.d_cap_lift_period ledger row, which this contract keeps as a REPORTING wire only.

    RECEIVES: to <- CAP.caps().vocab, as an argument, on the flush CAP lifted.
    RETURNS: int, the cap now in force.

    LEVERS READ: none
    WIRES READ: d_vocab_ceiling
    DID IT FIRE: tok.cap_lift, tok.cap_lift_refused_at_ceiling
    """
    tok = tok.owned_by("TOK")
    _ = tok.d_vocab_ceiling                              # WIRE READ HERE -- min(to, ceiling)
    raise NotImplementedError(
        "TOK.lift_vocab_cap: P4 (tok) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section TOK.")


def save_vocabulary(tok: Config, vocab):
    """Write merges plus the settings this run actually used to d_vocab_save_path, or return None
    when that wire is empty (saving is off). NEVER writes to d_vocab_read_path: that file is the
    parent's.

    RETURNS: str path, or None.

    LEVERS READ: none
    WIRES READ: d_vocab_save_path
    DID IT FIRE: tok.vocab_saved
    """
    tok = tok.owned_by("TOK")
    _ = tok.d_vocab_save_path                            # WIRE READ HERE -- this run's own file
    raise NotImplementedError(
        "TOK.save_vocabulary: P4 (tok) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section TOK.")


def vocab_state(tok: Config, vocab):
    """Everything a resume needs that the merge list alone does not carry: retired ids, the prov
    table with birth steps, v0, the cadence _fired map, the soft cap, the pair tally digest, and
    the counter vector.

    Today a save/load round trip UNDOES EVERY RETIREMENT, because load() replays every merge into
    the match table including the retired ones, and `prov` does not exist in the file at all -- so
    every token on probation at save time is silently confirmed (DEFECT D-T3).

    ALSO REPORTS THE CAP-LIFT CADENCE as a reading, so "0 lifts" is distinguishable from "the
    valve's period is longer than the run" -- round6 measured 0 vocabulary lifts on gc_real and it
    was a clock-unit fault, not the plateau condition.

    RETURNS: dict, handed to CKPT.save as part of the opaque payload.

    LEVERS READ: none
    WIRES READ: d_cap_lift_period (reported beside tok.cap_lift; see FOR THE OWNER Q-CLOCK-1)
    DID IT FIRE: tok.state_written
    """
    tok = tok.owned_by("TOK")
    _ = tok.d_cap_lift_period                # WIRE READ HERE -- reported beside tok.cap_lift
    raise NotImplementedError(
        "TOK.vocab_state: P4 (tok) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section TOK.")


def restore_vocab(tok: Config, state, vocab):
    """Put retirements, probation and the cadence clocks back, and REFUSE LOUDLY if the state's
    merge count does not match the vocabulary just built from the file.

    LEVERS READ: none
    WIRES READ: none
    DID IT FIRE: tok.state_restored, tok.state_refused
    """
    tok = tok.owned_by("TOK")
    raise NotImplementedError(
        "TOK.restore_vocab: P4 (tok) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section TOK.")
