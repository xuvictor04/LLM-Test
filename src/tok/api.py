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

ONE NARROWING EXCEPTION, AND IT IS THE OPPOSITE OF D-T1'S SHAPE, RECORDED HERE SO THE TWO
PARAGRAPHS DO NOT READ AS DISAGREEING (round1 finding against tok/api.py::build_vocabulary, ruled 2026-09-03): on
tok.mode="fixed", build_vocabulary closes vocab.ceiling down to the achieved build size once the
seed build finishes, on both the fresh-build and the resume/replay arms, so the arm's "never mint
again" promise cannot be defeated by CAP's lift_vocab_cap reaching a soft_cap this arm does not
even close. This never ADOPTS a value from outside the wire -- the new ceiling is vocab.size(),
which the build already capped at min(seed_vocab, wire ceiling), so the write can only ever
narrow, and it derives FROM the wire's own bound rather than contradicting it. D-T1 was a SAVED
FILE'S recorded vmax outliving the wire and being trusted as if it still were the wire; this is
the wire's own bound applied once and left in place. See build_vocabulary's own paragraph on this
(P1-H57) for the full argument, and for the alternative (a separate `closed_at` field, keeping
`ceiling` itself untouched) that was priced and not taken.

TWO PATH WIRES, AND THEY ARE TWO ON PURPOSE. d_vocab_save_path (from CKPT.dir) is where this run
writes its own vocabulary; d_vocab_read_path (from CKPT.resume) is where a resume reads its
parent's. One knob doing both jobs made a run overwrite its parent's vocabulary and made eleven
concurrent smoke arms race for data/dyntok.json (ISSUES P1-M5, L7, M19, M46).

RECORD TYPES RETURNED (P4 defines them; other packages receive them as arguments and call their
methods, which is not an import):
  Vocabulary    id2bytes, seq2id, merges, bytes_per_id, mlbf, maxlen, retired, prov, pair,
                ceiling (hard, from the wire), soft_cap (mutable, from CAP), v0, bytes_per_token,
                max_bytes, dropout_rng (the ONE segmentation stream, minted once -- see P1-H56);
                methods decode, blen, size, live_size, at_cap
  Segmentation  ids, byte_pos, labels, bytes_per_token
  Due           mint, retok, probation, frozen
  Mint          new_id, left_id, right_id, token_bytes, count
  Judgement     kept, retired_ids, pending, live_size, id_count
                `live_size` and `id_count` are DIFFERENT NUMBERS and both are needed. id_count is
                the positional boundary -- where never-minted rows begin, i.e. Vocabulary.size() --
                and it is what LM.decode's `live_vocab` argument must receive, because ids are
                positional: retire() pops from the match table and leaves id2bytes intact, so
                retired rows sit BELOW the boundary and are handled separately, by id. live_size is
                that boundary minus the retired count, and passing it to decode would move the
                boundary down and mask exactly that many LIVE rows to -inf. The composition root's
                own wiring table named live_size here until 2026-09-03.
  RetokEvent    the signal the composition root hands to SIG, MEM, DOM and FAB
"""
import collections
import dataclasses

from spine.lever import Config
from spine import derive as _derive
from spine import rng as _rng
from spine.gate import Gate


@dataclasses.dataclass(frozen=True)
class Segmentation:
    """One text, segmented, with the BYTE offset of every token.

    `byte_pos[k]` is the stable coordinate. Without it every downstream metric is measured in token
    indices off a text whose token length CHANGES as the vocabulary grows, which is exactly how the
    run-boundary probe came to compare `prev` and `now` on two different windows (ISSUES P1-H20).
    """
    ids: list
    byte_pos: list
    labels: list
    bytes_per_token: float


class Vocabulary:
    """The merge table as it now stands, plus the two caps and the measurement.

    NOT FROZEN, because minting is the mechanism: `online` mode adds ids during training. What is
    protected instead is that ONE object exists per run and every package receives it as an
    argument, so there is no second vocabulary anywhere to disagree with this one.

    TWO CAPS, AND THEY ARE DIFFERENT THINGS. `ceiling` is HARD and arrives as the wire
    d_vocab_ceiling from LM.vocab_slots -- it is the model's embedding row count, and minting past
    it reserves ids the model has no row for. `soft_cap` is CAP's valve position and moves during
    the run. Minting compares against min(soft_cap, ceiling); at_cap() is the predicate, so no call
    site re-derives it. ONE NARROWING EXCEPTION: on tok.mode="fixed", build_vocabulary closes
    `ceiling` down to the achieved build size, once, immediately after the seed build -- see the
    module header's "ONE NARROWING EXCEPTION" paragraph and build_vocabulary's own P1-H57 note for
    why that is a bound derived from the wire rather than a second source contradicting it.
    """

    __slots__ = ("id2bytes", "seq2id", "merges", "bytes_per_id", "mlbf", "maxlen", "retired",
                 "prov", "pair", "ceiling", "soft_cap", "v0", "bytes_per_token", "max_bytes",
                 "dropout_rng", "counters", "gates", "_retok_cache")

    def __init__(self, *, ceiling, soft_cap=None, max_bytes=16):
        self.id2bytes = [bytes([b]) for b in range(256)]
        self.seq2id = {bytes([b]): b for b in range(256)}
        self.merges = []
        self.bytes_per_id = [1] * 256
        # LONGEST MATCH NEEDS A BOUND PER FIRST BYTE, not one global bound: with a single maxlen the
        # matcher probes every length from maxlen down at every position, which is the whole segment
        # cost multiplied by the longest token in the table. mlbf[b] is the longest sequence in the
        # table that STARTS with byte b, so a position whose byte begins no merge costs one lookup.
        self.mlbf = [1] * 256
        self.maxlen = 1
        self.retired = set()
        self.prov = {}               # id -> how it was minted ("build" | "online" | "replay")
        self.pair = {}               # id -> (left_id, right_id) that produced it
        self.ceiling = int(ceiling)
        self.soft_cap = None if soft_cap is None else int(soft_cap)
        self.v0 = 256                # the size the run ENTERED training with; set by build
        self.bytes_per_token = 1.0
        self.max_bytes = int(max_bytes)
        # THE SEGMENTATION STREAM LIVES HERE AND IS MINTED ONCE (P1-H56). BPE-dropout has to give a
        # DIFFERENT segmentation of the same text on each call -- that is the entire mechanism -- and
        # tokenize() is called once per epoch plus on every retokenization. A stream minted inside
        # tokenize() restarts from the same seed on every call, so all of those segmentations came
        # out byte-identical: the knob was on, the code ran, and the mechanism did nothing.
        self.dropout_rng = None
        # THE DID-IT-FIRE CHANNEL (graft G4), same shape as CAP.Valve.counters/.gates and
        # FAB.Population.counters/.gates: a flat name->value dict for counts, a tuple of spine.gate
        # .Gate objects for three-state predicates. Both start empty here.
        # THE TWO FIELDS ARE FILLED DIFFERENTLY, AND THIS COMMENT USED TO SAY OTHERWISE (r3 finding
        # against tok/api.py::Vocabulary.__init__): it claimed `counters` was "populated by
        # build_vocabulary at each of its return points, never appended to piecemeal", and BOTH of
        # that field's writers contradict it -- _replay_merges writes tok.load_reconciled from
        # inside the replay, not at a return point, and tokenize() increments its rows one call at a
        # time. The sentence was true of `gates` and had been carried over onto the field beside it.
        #   `gates` IS whole-surface and per-call: build_vocabulary ASSIGNS the tuple at each of its
        #   three return points and never appends, so a reader of `vocab.gates` after a build sees
        #   the whole declared surface for that call in one place.
        #   `counters` IS CUMULATIVE OVER THE LIFE OF THE VOCABULARY and IS appended to piecemeal,
        #   on purpose: the build seeds tok.build_pass/build_mint/build_converged on the arm that
        #   runs the loop, _replay_merges writes tok.load_reconciled(_detail) on the arm that
        #   replays, and then tokenize() adds to tok.segment, tok.retok, tok.retok_noop,
        #   tok.byte_fallback and tok.dropout_skip on EVERY call thereafter. There is no return
        #   point at which a total could be assigned, because the total is the point of the row.
        #   ABSENT AND PRESENT-AND-0 THEREFORE MEAN DIFFERENT THINGS in this dict, which is the
        #   three-state discipline spine/gate.py states for predicates applied to counts: a key is
        #   present-and-0 when its mechanism ran and did not fire, and ABSENT when the mechanism was
        #   unreachable on the arm this vocabulary took. _replay_merges' own docstring says it first
        #   for tok.load_reconciled ("present and possibly 0 whenever recon is given, absent when it
        #   is not"), and the build and dropout rows follow it.
        self.counters = {}
        self.gates = ()
        # THE RE-SEGMENTATION NO-OP CACHE (round1 tok/api.py::build_vocabulary/420, re-filed at :462). One slot,
        # not a dict keyed by every text ever segmented: the contract's own words are "since the
        # LAST one", singular, and tokenize() is called once per epoch plus on every
        # retokenization -- a growing cache of every held-out probe this run ever segmented would
        # be an unbounded leak for a check whose entire job is to catch the one specific pattern
        # measured at 2.189 b/B and 68 points of word quality: the SAME data re-segmented from the
        # SAME start while nothing minted in between.
        # (data, start, len(data), stamp, Segmentation, drawn_with_dropout); None until the first
        # call. The last field is a BOOL and not a nicety: an entry produced under BPE-dropout is a
        # legitimate stamp for the next call's comparison and an ILLEGITIMATE answer to return to a
        # deterministic one, and tokenize()'s skip test reads it for exactly that.
        self._retok_cache = None

    def size(self):
        return len(self.id2bytes)

    def live_size(self):
        """Ids that can still be MATCHED. Not size(): retire() removes a sequence from the match
        table without shortening id2bytes, because the embedding row keeps its meaning."""
        return len(self.id2bytes) - len(self.retired)

    def at_cap(self):
        """THE ONE PREDICATE. A caller re-deriving min(soft_cap, ceiling) is a second copy of the
        rule, and the two caps mean different things -- one is the model's row count and one is a
        valve position that moves."""
        return self.size() >= self._cap()

    def _cap(self):
        return self.ceiling if self.soft_cap is None else min(int(self.soft_cap), self.ceiling)

    def blen(self, i):
        return self.bytes_per_id[i]

    def decode(self, ids):
        return b"".join(self.id2bytes[i] for i in ids)

    def _add(self, seq, *, prov, pair=None):
        """Mint one sequence. Returns its id, or None when the cap or max_bytes refuses it."""
        if seq in self.seq2id or len(seq) > self.max_bytes or self.at_cap():
            return None
        i = len(self.id2bytes)
        self.id2bytes.append(seq)
        self.seq2id[seq] = i
        self.bytes_per_id.append(len(seq))
        self.prov[i] = prov
        if pair is not None:
            self.pair[i] = pair
            self.merges.append(pair)
        b0 = seq[0]
        if len(seq) > self.mlbf[b0]:
            self.mlbf[b0] = len(seq)
        if len(seq) > self.maxlen:
            self.maxlen = len(seq)
        return i




def build_vocabulary(tok: Config, *, area_heads, seed: int, soft_cap=None):
    """Produce the vocabulary the run ENTERS TRAINING WITH, on all three arms of tok.mode.

    mode="bytes"   -> the 256 byte ids, no merges; nothing else in this file is reachable.
    mode="fixed"   -> build to tok.seed_vocab as the CEILING as well as the target, then never mint.
    mode="online"  -> build to tok.seed_vocab as a TARGET and keep minting during training.
    The three-state lever replaces two booleans encoding three states, which is why GROW_PASSES was
    unreachable at TOK_ONLINE=1 and SEED_VOCAB/SEED_PASSES unreachable at TOK_ONLINE=0 while the
    audit reported the unset one as an operator typo (ISSUES P1-L20).

    If d_vocab_read_path is non-empty and exists, the parent's merges are REPLAYED instead of
    built -- a resume MUST reuse the saved vocabulary or the restored embedding table is indexed by
    a different vocabulary. The file's recorded vmax/min_pair/max_tok/dropout DO NOT WIN: this
    package holds one declaration, the levers, and any disagreement is printed as a reconciliation
    line and counted (ISSUES P1-M80, L20 -- a resume setting MIN_PAIR=200 ran with the parent's value
    and the audit then printed "NOTHING READ THESE" naming a knob that was set and ignored).

    ONE LITERAL FOR THE PASS COUNT (Q-TOK-9, ruled 2026-09-02). It is tok.build_passes on ALL
    THREE ARMS. tok/levers.py used to say the offline build's 8 "carries over as the fixed arm's
    declared target inside this package's build code"; that is a second literal in a second place,
    and the Lever carries exactly one default, so an 8 living in build code prints as 2 in the
    generated lever reference -- the L1 failure the SEED_PASSES/GROW_PASSES merge exists to end,
    moved from a second environment name into a second number. The 8 is not lost: it is a DECLARED
    GATE with its predicate, tok.build_passes_advice, which on mode="fixed" prints
    `build_passes=2; the offline build historically used 8 -- set TOK_BUILD_PASSES=8 to reproduce
    it` and on the other two arms prints `unreachable (mode != fixed)`. Advice that appears
    sometimes and says nothing when it does not is armed-but-inert applied to prose.
    A mode="fixed" run at 2 passes is NOT the offline build of record, and that belongs on P9's
    list of numbers that moved.

    Otherwise: tok.build_passes tally-and-mint passes over
    b"".join(h[:tok.build_bytes] for h in area_heads), breaking early when a pass mints nothing.
    The counting segmentation applies tok.dropout, drawing from rng_for("tok.dropout", seed) --
    never the process-global `random`, which shifted the RNG stream of the entire run (ISSUES P1-L69).
    bytes_per_token over the build sample is measured with derive.bytes_per_token(len(sample),
    len(ids)) and returned on the Vocabulary, because it is what DATA's splice gate and SIG's width
    need and THERE IS NO SECOND ESTIMATOR (ISSUES P1-H16: the mean-over-vocabulary-entries estimator
    read 1.50 against 1.85 as used, and its error changes SIGN with vocabulary size -- the axis
    those runs were compared along).

    soft_cap is CAP's starting vocabulary cap (the old GROW_CAP_VOCAB0, self_organize.py:5262);
    None means "start at the hard ceiling". min(soft_cap, ceiling) is what minting compares against.

    RECEIVES: area_heads <- DATA (already capped by DATA.corpus_cap; TOK applies build_bytes on
    top -- two genuinely different quantities, one bounds the build and one bounds the run);
    seed <- RUN.seed; soft_cap <- CAP.
    RETURNS: Vocabulary.

    cand_window, mint_pmin and mint_novel are NOT read here (round1 + r2 finding,
    tok/api.py::build_vocabulary): the build pass below selects purely by tally.most_common() and
    tok.min_pair; the candidate window, the novelty re-rank and the p(b|a) floor are mint_burst's
    selection rules (see its own LEVERS READ line), applied during ONLINE minting, not during the
    seed build. Declaring them here said these three knobs were read by a call that never touches
    them -- the ISSUES P1-M80/L20 shape ("NOTHING READ THESE") applied to this package's OWN
    contract line rather than to an operator's environment -- and it silently widened the L3
    isolation sweep's precomputed affects() set for this entry point to cover a coupling that
    cannot exist here.

    THAT NOTE SITS ABOVE THE BLOCK AND MUST STAY ABOVE IT, and this sentence is why. It used to be
    written as comment lines DIRECTLY UNDER the LEVERS READ line, and in that position it did not
    merely annotate the block -- it ATE THE LAST ITEM ON IT. The block is terminated by the next
    `LEVERS READ:`/`WIRES READ:`/`DID IT FIRE:` header (tests/test_contract.py::stub_reads), so
    every one of those nine lines was INSIDE the lever list; the harvester then splits on commas at
    paren depth 0 and keeps only items that are bare identifiers
    (tests/test_contract.py::_split_items), so the first comma of the note fused with the name
    before it and produced the item "dropout\\n# cand_window", which is not an identifier and was
    DROPPED. Measured by running the real parser over this very block: KEPT mode, seed_vocab,
    build_passes, build_bytes, min_pair, max_bytes -- six of the seven -- and DROPPED `dropout`
    plus four prose fragments. The parser keeps a name with a PARENTHETICAL after it (the note is
    stripped) but drops a name followed by bare prose, which is the whole shape.

    NOTHING FAILED WHILE IT WAS BROKEN, WHICH IS THE HAZARD AND NOT THE DEFENCE. K4 aggregates per
    PACKAGE, and tok/api.py::tokenize's clean sibling line -- "LEVERS READ: mode, dropout" while this
    block was broken, "LEVERS READ: dropout" since its own `mode` was found to have no reader either
    -- credited `dropout` for all of TOK, so the harvest looked complete while THIS entry point's
    declaration was invisible. Delete or reword that one sibling line and TOK_DROPOUT becomes a lever
    K4 reports as having no reader anywhere -- for a knob whose value this function passes to
    _segment on every counting pass. A lever silently losing its credit is the untrippable-guard
    family: the check keeps reporting a verdict it can no longer see the evidence for.

    LEVERS READ: mode, seed_vocab, build_passes, build_bytes, min_pair, max_bytes, dropout
    WIRES READ: d_vocab_ceiling, d_vocab_read_path
    DID IT FIRE: tok.build_pass, tok.build_mint, tok.build_converged (all three PRESENT ONLY ON THE
                 FRESH-BUILD ARM -- absent on mode="bytes" and on the replay arm, where the build
                 loop is unreachable and a 0 would be a false reading rather than a small one),
                 tok.load_reconciled, tok.load_reconciled_detail (the disagreeing lines themselves,
                 written by _replay_merges beside the count and present only when at least one field
                 disagreed; declared here because the reverse direction of this row is a check too --
                 a counter written by a body and named in no declaration is as invisible as a
                 declaration nothing writes),
                 Gate tok.build_passes_advice (fires on mode="fixed" with the two numbers;
                 "unreachable (mode != fixed)" otherwise -- never silence),
                 tok.v0 -- the ACHIEVED size at the start of training, recorded once and NEVER
                 computed by subtracting seed_vocab, which is what the old DID IT FIRE row did and
                 why it over-reported mints on any corpus that converged below target
                 (self_organize.py:1274-1281). IT LIVES ON THE FIELD `vocab.v0` AND NOT IN
                 `vocab.counters`, said here so a reader of the counters dict does not report it
                 missing: it is the one row of this block that is a STATE the rest of the run reads
                 back, not a tally, and copying it into counters would be a second home for a number
                 that already has one.
    """
    tok = tok.owned_by("TOK")
    mode = str(tok.mode)
    vocab = Vocabulary(ceiling=int(tok.d_vocab_ceiling), soft_cap=soft_cap,
                       max_bytes=int(tok.max_bytes))

    # THE BUILD SAMPLE. build_bytes bounds the BUILD; DATA.corpus_cap already bounded what was
    # opened. Two genuinely different quantities, which is why both exist and neither is derived
    # from the other.
    # AREA ORDER IS PART OF THE MEASUREMENT, so it is taken from the mapping rather than from a
    # set: `bodies` is keyed by area label in DATA_AREAS order, dicts preserve insertion order, and
    # the merge table this sample produces depends on which area's text the tally saw first. Sorting
    # here would silently make the vocabulary independent of a lever the operator set.
    heads = area_heads.values() if hasattr(area_heads, "values") else area_heads
    sample = b"".join(bytes(h)[:int(tok.build_bytes)] for h in heads)

    if mode == "bytes":
        # Nothing else in this file is reachable on this arm: no merges, no minting, no candidate
        # window. v0 is 256 and stays there. The stream is still minted so the ledger carries the
        # key with zero draws -- DECLARED AND NEVER ASKED, which is a different statement from
        # absent, and this arm is exactly where a reader needs to see it.
        vocab.dropout_rng = _rng.rng_for("tok.dropout.mint", seed)
        vocab.v0 = vocab.size()
        vocab.bytes_per_token = 1.0
        # THE GATE IS EMITTED ON EVERY ARM, NOT ONLY THE ONE WHERE IT FIRES (round1/r2 finding: this
        # file did not import spine.gate at all, so the declared "unreachable (mode != fixed)" state
        # was never actually printed anywhere -- it was simply absent, which is the armed-but-inert
        # collapse this record type exists to refuse). mode="bytes" never reads build_passes, so
        # there is no achieved-vs-historical pair to show; value stays None rather than a number that
        # was never resolved.
        vocab.gates = (Gate("tok.build_passes_advice", False, None, 8, reachable=False,
                             reason="mode != fixed"),)
        return vocab

    read_path = str(tok.d_vocab_read_path)
    if read_path:
        # A RESUME MUST REUSE THE SAVED VOCABULARY or the restored embedding table is indexed by a
        # DIFFERENT vocabulary. The file's recorded settings DO NOT WIN -- this package holds one
        # declaration, the levers -- and any disagreement is a printed reconciliation, not a silent
        # adoption (ISSUES P1-M80, P1-L20: a resume setting MIN_PAIR=200 ran with the parent's value
        # while the audit printed "NOTHING READ THESE" naming a knob that was set and ignored).
        # MINTED ON THIS BRANCH TOO. P1-H56's repair minted `tok.dropout.mint` on the build path
        # and returned from here without it, so every RESUME of a TOK_DROPOUT>0 run died at the
        # first segmentation -- the same crash, reintroduced on the one branch the fix did not
        # cover. Minted BEFORE the early return, unconditionally, for exactly that reason.
        vocab.dropout_rng = _rng.rng_for("tok.dropout.mint", seed)
        # THE RECONCILIATION INPUT (P1-M80, P1-L20). vmax is checked against the WIRE-sourced
        # ceiling as it stood at entry -- BEFORE any fixed-arm narrowing below -- because vmax is a
        # recorded fact about the PARENT's ceiling, and comparing it against a value this call may
        # itself still narrow would blame the parent for a change this run made.
        recon = {"min_pair": int(tok.min_pair), "max_tok": int(tok.max_bytes),
                 "dropout": float(tok.dropout), "vmax": vocab.ceiling}
        replayed = _replay_merges(vocab, read_path, recon=recon)
        if replayed is None:
            # A MISSING PARENT IS NOT A COLD START (round1 finding, tok/api.py::build_vocabulary). The old body
            # fell through to the fresh-build arm below and returned a freshly minted vocabulary
            # with no refusal at all -- the restored embedding table would then be indexed by a
            # vocabulary the checkpoint never saw. Falling through here ALSO used to crash a step
            # later and for an unrelated-looking reason: `vocab.dropout_rng` is minted,
            # unconditionally, three lines above, and the fresh-build arm mints the very same name
            # again at "tok.dropout.mint" once execution reached it -- spine/rng.py's
            # two-call-sites-one-sequence guard then raised RngError from inside build_vocabulary,
            # which is the correct guard firing on the wrong root cause. Both symptoms were one
            # defect: a missing d_vocab_read_path treated as "nothing was asked for" instead of
            # "the resume the operator asked for cannot happen". Refusing HERE, before any of that,
            # removes the crash along with the silent success it replaced.
            raise ValueError(
                f"TOK.d_vocab_read_path={read_path!r} does not exist. A resume must reuse the "
                f"parent's saved vocabulary or the restored embedding table is indexed by a "
                f"different one; refused rather than silently building a fresh vocabulary against "
                f"a checkpoint that was trained on a different one.")
        vocab.v0 = vocab.size()
        if mode == "fixed":
            # THE FIXED ARM CLOSES ITS CEILING ON THIS PATH AS WELL. Closing it only on the
            # build path meant a resumed "fixed" run had an OPEN ceiling and could keep minting
            # -- the arm's one promise, broken by which branch the run happened to take.
            vocab.ceiling = vocab.size()
        # MEASURED WITH DROPOUT APPLIED, ON THIS ARM TOO (round1 tok/api.py::build_vocabulary, re-filed three more
        # times against this exact line after the fresh-build arm below was fixed and this one was
        # not). tokenize()'s own docstring is unconditional: "bytes_per_token IS MEASURED WITH
        # DROPOUT APPLIED" -- it does not carve out an exception for a resumed vocabulary, and
        # derive.signature_width_bytes and data_plan's splice_window read whatever this call
        # returns regardless of which arm produced it. `stream` reuses the dropout_rng minted three
        # lines above (not a second mint -- see P1-H56 and the crash that a second mint caused on
        # this exact branch before that fix).
        stream = vocab.dropout_rng if float(tok.dropout) > 0 else None
        ids, _pos = _segment(vocab, sample, dropout=float(tok.dropout), stream=stream)
        vocab.bytes_per_token = _derive.bytes_per_token(len(sample), len(ids))
        # THE GATE, EVEN THOUGH NO BUILD PASS RAN HERE. build_passes_advice's predicate is about a
        # FRESH build reaching mode="fixed" at some achieved pass count against the historical 8;
        # a replay never calls the build loop at all; on the offline analogue of the round1 fix that
        # left mode-out arms silent, staying silent here instead of naming the reason would be the
        # same collapse under a different cause. Reachable=False regardless of mode, because the
        # thing the gate reports on (a pass count) was never resolved on this branch.
        vocab.gates = (Gate("tok.build_passes_advice", False, None, 8, reachable=False,
                             reason="resumed via d_vocab_read_path: no build pass ran on this "
                                    "branch, so there is no achieved pass count to compare"),)
        return vocab

    target = min(int(tok.seed_vocab), vocab._cap())
    # ONE LITERAL FOR THE PASS COUNT, ON ALL THREE ARMS (Q-TOK-9). An 8 living in build code would
    # print as 2 in the generated lever reference, which is the L1 failure the SEED_PASSES/
    # GROW_PASSES merge exists to end, moved from a second environment name into a second number.
    passes = int(tok.build_passes)
    # A CHILD OF THE DECLARED PARENT, MINTED ONCE, ALWAYS (P1-H56, and the same repair P1-H55 made
    # for data.synth). `tok.dropout` is in RNG_SUBSYSTEMS, so RUN.streams already minted it into the
    # register at step 0; this package asking for that exact name again is the two-call-sites-one-
    # sequence collision spine/rng.py refuses, and it made TOK_DROPOUT>0 crash compose() outright.
    # The parent stays declared and reports zero draws; the child is what this package draws from.
    # MINTED EVEN AT dropout=0 so `.draws == 0` on the ledger is armed-but-inert rather than absent,
    # and never the process-global `random`, which shifted the RNG stream of the ENTIRE run
    # (ISSUES P1-L69).
    vocab.dropout_rng = _rng.rng_for("tok.dropout.mint", seed)
    stream = vocab.dropout_rng if float(tok.dropout) > 0 else None

    # THE BUILD LOOP'S OWN DID IT FIRE, SEEDED HERE AND ONLY ON THE ARM THAT RUNS THE LOOP (r3
    # finding: all three of these were declared by the docstring above and written by NO body
    # anywhere, so every one of them read armed-but-0 forever -- indistinguishable from a build that
    # ran and minted nothing, which is the exact reading tok.v0's own row exists to make impossible).
    # PRESENT-AND-0 AND ABSENT MEAN DIFFERENT THINGS, the convention _replay_merges already states
    # for tok.load_reconciled: seeded to 0 here, so a zero on this arm means "the loop ran and did
    # not fire", while on mode="bytes" and on the replay arm -- both of which return above, before
    # this point -- the keys stay ABSENT, because there the loop is UNREACHABLE and a zero would be
    # a false reading of a mechanism that could not run.
    vocab.counters["tok.build_pass"] = 0
    vocab.counters["tok.build_mint"] = 0
    vocab.counters["tok.build_converged"] = 0
    for _ in range(passes):
        if vocab.size() >= target:
            break
        # COUNTED AFTER THE TARGET TEST, so tok.build_pass is passes EXECUTED and not passes
        # scheduled: a pass that finds the target already reached does no tally and no mint, and
        # counting it would put work in the ledger that the corpus never paid for.
        vocab.counters["tok.build_pass"] += 1
        ids, _pos = _segment(vocab, sample, dropout=float(tok.dropout), stream=stream)
        tally = collections.Counter()
        for a, b in zip(ids, ids[1:]):
            tally[(a, b)] += 1
        minted = 0
        for (a, b), n in tally.most_common():
            if n < int(tok.min_pair) or vocab.size() >= target:
                break
            if vocab._add(vocab.id2bytes[a] + vocab.id2bytes[b], prov="build", pair=(a, b)) is not None:
                minted += 1
        vocab.counters["tok.build_mint"] += minted
        if minted == 0:
            # CONVERGED MEANS THE CORPUS RAN OUT OF PAIRS, and it is NOT the size >= target break
            # above. Setting it there too would say a build that reached its target had nothing left
            # to mint, which is the opposite claim and the one that matters for reading v0: a run
            # that converged below target is exactly the case the old subtract-seed_vocab row
            # over-reported (self_organize.py:1274-1281).
            vocab.counters["tok.build_converged"] = 1
            break                    # a pass that mints nothing will mint nothing next time either

    if mode == "fixed":
        # THE CEILING, WHICH IS THE HARD CAP, AND NOT soft_cap (P1-H57). The docstring says this arm
        # builds "to tok.seed_vocab as the CEILING as well as the target, then never mint", and the
        # two caps are not interchangeable: `ceiling` is hard and arrives as the wire from
        # LM.vocab_slots, while `soft_cap` is CAP's valve position and MOVES DURING THE RUN --
        # capacity/api.py sends TOK a lift_vocab_cap(to=...) event. Closing the soft cap here left
        # the fixed arm's central promise at the mercy of an unrelated package's valve: one lift and
        # a "fixed" vocabulary starts minting again, silently, on the one arm whose entire point is
        # that it does not. Lowering the ceiling is safe and is what the contract asks for -- the
        # build already capped at min(seed_vocab, cap()), so this can only ever narrow, and the
        # model keeps its spare embedding rows either way.
        vocab.ceiling = vocab.size()

    vocab.v0 = vocab.size()
    # THE ONE ESTIMATOR (ISSUES P1-H16). The mean-over-vocabulary-entries form read 1.50 against
    # 1.85 as used, and its error changes SIGN with vocabulary size -- which is the axis those runs
    # were compared along.
    # MEASURED WITH DROPOUT APPLIED, because the contract says "the COUNTING segmentation applies
    # tok.dropout" and because this number is what SIG's one signature width and DATA's splice gate
    # are computed from. A dropout-free measurement describes a segmentation the TRAINING stream
    # never produces: at TOK_DROPOUT>0 the stream is longer in tokens than the estimate, so the
    # signature window is too narrow and the splice gate is optimistic, on every run that turns
    # regularisation on. At the 0.0 default the two are identical and nothing moves.
    ids, _pos = _segment(vocab, sample, dropout=float(tok.dropout), stream=stream)
    vocab.bytes_per_token = _derive.bytes_per_token(len(sample), len(ids))
    # THE DECLARED GATE (Q-TOK-9). Round1 and r2 both filed this as absent because the module did
    # not even import spine.gate -- the three-state surface the docstring promises was not merely
    # unfired, it did not exist. `fired` is "does this arm need the advisory", which is exactly
    # mode == "fixed"; the achieved `passes` and the historical 8 travel as value/threshold so the
    # arithmetic is checkable rather than asserted, per Gate's own contract (spine/gate.py).
    vocab.gates = (
        (Gate("tok.build_passes_advice", True, passes, 8,
              reason="the offline build historically used 8 -- set TOK_BUILD_PASSES=8 to reproduce "
                     "it; a mode=\"fixed\" run at this value is not that build of record")
         if mode == "fixed" else
         Gate("tok.build_passes_advice", False, passes, 8, reachable=False, reason="mode != fixed")),
    )
    return vocab


def _replay_merges(vocab, path, *, recon=None):
    """Replay a parent's vocabulary into `vocab`, EXACTLY or not at all. None if unreadable.

    IDS ARE POSITIONS IN THE EMBEDDING TABLE, so a replay that drops one entry and shifts every id
    after it does not produce a smaller vocabulary -- it produces a DIFFERENT one, attaching the
    parent's trained embedding rows to different tokens. The first version called `_add` in a loop
    and ignored its refusals (`_add` returns None past max_bytes, past the cap, or on a duplicate),
    which is exactly that renumbering, silently, on the resume every continual-learning number in
    this project is measured across. So a refused entry is now a REFUSAL of the whole replay.

    THE MERGE TABLE IS PART OF THE VOCABULARY. `_add` only appends to `merges` and `pair` when it is
    given a pair, and the first version passed none -- so a replayed vocabulary carried an EMPTY
    merge history, was not the parent's vocabulary by its own accounting, and the next save
    propagated the loss. The pair is recorded in the file and is replayed with the sequence.

    `recon`, WHEN GIVEN, IS A RECONCILIATION, NOT AN ADOPTION (P1-M80, P1-L20). It carries this
    run's own RESOLVED levers (min_pair, max_tok, dropout) plus the wire-sourced ceiling (vmax),
    keyed to match whatever the file happens to record under those same names. The file's values
    NEVER WIN -- this function already builds the vocabulary from the levers the caller resolved,
    never from the blob's settings -- so this block only ever produces a report, counted on
    `vocab.counters["tok.load_reconciled"]` (present and possibly 0 whenever recon is given, absent
    when it is not, so "compared and agreed" reads differently from "never compared" the same way
    every other DID IT FIRE row here does). A key the file does not carry is skipped rather than
    treated as a mismatch against `None`: an old save predates a field and that is not a disagreement
    about a value, it is the absence of one.
    """
    import json
    import os
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as fh:
        blob = json.load(fh)

    if recon is not None:
        lines = []
        for key, lever_name in (("min_pair", "TOK_MIN_PAIR"), ("max_tok", "TOK_MAX_BYTES"),
                                 ("dropout", "TOK_DROPOUT"), ("vmax", "the wire d_vocab_ceiling")):
            recorded = blob.get(key)
            if recorded is None:
                continue
            resolved = recon.get(key)
            if recorded != resolved:
                lines.append(
                    f"tok.load_reconciled: {path!r} recorded {key}={recorded!r}, this run resolves "
                    f"{resolved!r} ({lever_name}) -- the file's value does not win")
        vocab.counters["tok.load_reconciled"] = len(lines)
        if lines:
            vocab.counters["tok.load_reconciled_detail"] = tuple(lines)

    entries = blob.get("entries")
    if entries is None:
        # THE OLD SHAPE, ACCEPTED AND NAMED. A file carrying only `id2bytes` has no pair history to
        # replay, so the vocabulary comes back with the right ids and an empty merge table -- which
        # is a real loss and is recorded on the object rather than passed off as a clean restore.
        raw = blob.get("id2bytes")
        if raw is None:
            raise ValueError(
                f"{path!r} carries neither `entries` nor `id2bytes`. A resume must reuse the saved "
                f"vocabulary or the restored embedding table is indexed by a different one; "
                f"replaying nothing would silently train a 256-symbol byte vocabulary against a "
                f"checkpoint built on the parent's.")
        entries = [{"bytes": h} for h in raw[256:]]
        vocab.prov[-1] = "replay:id2bytes-only (no pair history in the file)"

    for k, ent in enumerate(entries):
        seq = bytes.fromhex(ent["bytes"]) if isinstance(ent, dict) else bytes.fromhex(ent)
        pair = tuple(ent["pair"]) if isinstance(ent, dict) and ent.get("pair") else None
        got = vocab._add(seq, prov="replay", pair=pair)
        if got is None:
            raise ValueError(
                f"{path!r} entry {k} (id {256 + k}) could not be replayed: {seq!r} is a duplicate, "
                f"longer than TOK_MAX_BYTES={vocab.max_bytes}, or past the ceiling "
                f"{vocab.ceiling}. REFUSED rather than skipped -- ids are positions in the "
                f"embedding table, so dropping one entry renumbers every id after it and attaches "
                f"the parent's trained rows to different tokens.")
        if got != 256 + k:
            raise ValueError(
                f"{path!r} replayed entry {k} landed at id {got}, not {256 + k}. The id space has "
                f"drifted and the parent's embedding rows no longer line up.")
    return vocab


def _segment(vocab, data, *, dropout=0.0, stream=None, start=0, counts=None):
    """Greedy longest match from `start`. Returns (ids, byte_pos).

    LONGEST MATCH, NOT A MERGE REPLAY, and the difference is that this one function serves the
    initial segmentation, every in-loop re-segmentation, the final one and the held-out encode --
    a merge replay would need the merge ORDER to be meaningful, and `retire()` changes the match
    table without changing that order.

    `mlbf[b]` bounds the probe per FIRST BYTE. A global maxlen would probe every length from the
    longest token in the table downward at every position, so one 16-byte token would make every
    position cost sixteen dict lookups whether or not any 16-byte token starts with that byte.

    `counts`, WHEN GIVEN, IS THE CALLER'S DID IT FIRE ACCUMULATOR AND NOT THIS FUNCTION'S: a
    {"skip", "byte"} dict this loop adds to, defaulting to None because the two counters it feeds --
    tok.dropout_skip and tok.byte_fallback -- are declared by tokenize() and by nothing else. THAT IS
    WHY IT IS AN ARGUMENT rather than a write straight to `vocab.counters`: build_vocabulary calls
    this function on every counting pass and again for the final bytes_per_token measurement, and
    folding those in would make the two rows an operator reads a sum over the BUILD SAMPLE and the
    RUN STREAM, under a name that names only one of them. The three build call sites pass nothing.
    """
    ids, pos = [], []
    n, i = len(data), start
    s2i, mlbf, retired = vocab.seq2id, vocab.mlbf, vocab.retired
    while i < n:
        b0 = data[i]
        hi = min(mlbf[b0], n - i)
        took = 0
        for L in range(hi, 1, -1):
            j = s2i.get(data[i:i + L])
            if j is None or j in retired:
                continue
            # BPE-DROPOUT (Provilkov et al., ACL 2020): skip an available merge with probability
            # `dropout`, falling back toward the raw byte, which is always in the table. Used for
            # the TRAINING stream and never for held-out text, generation or the final segmentation.
            if dropout > 0.0 and stream is not None and stream.random() < dropout:
                if counts is not None:
                    counts["skip"] += 1
                continue
            ids.append(j)
            pos.append(i)
            i += L
            took = L
            break
        if not took:
            # THE BYTE FALLBACK, AND EVERY 1-BYTE TOKEN COMES THROUGH HERE: the match loop above is
            # `range(hi, 1, -1)` and never considers L=1, so this branch is the whole population of
            # tok.byte_fallback and a caller cannot re-derive the number from `ids` without
            # re-stating that rule in a second place.
            ids.append(b0)
            pos.append(i)
            i += 1
            if counts is not None:
                counts["byte"] += 1
    return ids, pos


def tokenize(tok: Config, vocab, data, labels=None, *, start=0, regularize=False, seed=0):
    """Segment bytes with the vocabulary AS IT NOW STANDS. This ONE function serves the initial
    segmentation, every in-loop re-segmentation, the final one before eval, and the held-out encode.

    Returns Segmentation(ids, byte_pos, labels, bytes_per_token) where byte_pos[k] is the BYTE
    offset of token k -- the stable coordinate that lets every downstream metric survive a
    re-segmentation, and the surface ISSUES P1-H20 needs: the run-boundary probe drew window starts in
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
    is then no longer a deterministic function of the vocabulary.

    Q-TOK-3 IS CONFIRMED (2026-09-02): the regularizer reaches the TRAINING stream, which is what
    BPE-dropout is (Provilkov et al., ACL 2020 -- dropout during training, deterministic BPE at
    inference, the protocol this paragraph already states). The old tree applied it only to
    count=True segmentations and the only count=True call was the build pass
    (self_organize.py:1264), so at mode="online" it ran during the seed build and never again. Two
    consequences follow and neither is written anywhere else:

      1. THE RUN LENGTH BECOMES A DRAW. With regularize=True on the epoch-0 and every-epoch
         segmentation, len(Segmentation.ids) -- hence _windows_in_epoch, _run_windows and the LR
         horizon -- are stochastic in the "tok.dropout" stream whenever dropout > 0. That is
         acceptable because the count is MEASURED rather than estimated (Q-DATA-8), but
         DATA.draw_stream's invariant "two arms differing in one unrelated knob still read the same
         text at epoch 2" is a statement about BYTES and does not extend to tokens. Two dropout>0
         arms will differ in window count; that is the regularizer, not a bug.
      2. bytes_per_token IS MEASURED WITH DROPOUT APPLIED. build_vocabulary measures it over the
         COUNTING segmentation, which applies tok.dropout, so more and shorter tokens lower it --
         and derive.signature_width_bytes(LM.ctx, bytes_per_token) (SIG's one width) and
         data_plan's splice_window threshold both move with a TOK regularizer. Both take the
         measured value and so follow correctly; whoever reads a width that changed with no SIG
         lever set should look here first.

    `mode` IS NOT READ HERE AND THE LINE BELOW NO LONGER CLAIMS IT IS (r3 finding,
    tok/api.py::tokenize). Established by AST rather than by eye: the only attribute this body takes
    off `tok` is `dropout`. The LINE was the wrong half of the pair and not the body, and the reason
    is this package's own one-declaration rule -- what this function emits is a function of the
    Vocabulary IT IS HANDED plus that one lever, and mode's effect is already FROZEN INTO that
    vocabulary by build_vocabulary (mode="bytes" returns a table with no merges, so the match loop in
    _segment has nothing to take; mode="fixed" closes `ceiling`). Re-reading `mode` here would be a
    second declaration of a decision another entry point already made, and it would let a "bytes"
    Config handed to an "online" vocabulary make the mode win over the table that is actually there.
    THE COST OF THE STALE LINE WAS NOT COSMETIC: K4 credits a lever the moment ANY stub in the
    package names it, so a declaration with no read makes K4 report a reader that does not exist --
    the untrippable-guard family, 60 of the survey's 475 records. TOK_MODE loses nothing by the
    correction: build_vocabulary names it AND demonstrably reads it (`mode = str(tok.mode)`), and
    on_window names it for the body P4 will write.

    LEVERS READ: dropout
    WIRES READ: none
    DID IT FIRE: tok.segment, tok.retok, tok.retok_noop (reported SEPARATELY so a frozen run's 39
                 no-op re-tokenizations read as skipped rather than as activity), tok.dropout_skip
                 (ABSENT, not 0, at dropout=0.0, the default -- the branch is unreachable there and a
                 zero printed for a branch that cannot be taken is the collapse Gate exists to
                 refuse), tok.byte_fallback
    """
    tok = tok.owned_by("TOK")
    drop = float(tok.dropout) if regularize else 0.0
    # DRAWN FROM THE VOCABULARY'S STREAM, NOT MINTED HERE (P1-H56). This function is called once per
    # epoch and again on every retokenization, all with regularize=True on the training stream, so
    # the stream has to CONTINUE across calls: minting one here restarted the same sequence every
    # time and every epoch got a byte-identical segmentation. BPE-dropout that returns the same
    # answer on every call is not dropout, it is a second deterministic segmentation -- armed and
    # inert, with the knob reading on. Measured before the repair: three calls on one text at
    # TOK_DROPOUT=0.3 produced one distinct segmentation, all 2189 tokens long.
    stream = vocab.dropout_rng if drop > 0 else None
    if drop > 0 and stream is None:
        raise ValueError(
            "TOK.tokenize was asked to regularize with TOK_DROPOUT>0 against a Vocabulary carrying "
            "no dropout stream. build_vocabulary mints it; a Vocabulary that did not come from "
            "there cannot be regularized, and silently segmenting without dropout would report a "
            "BPE-dropout run that never dropped anything.")

    # THE RE-SEGMENTATION REFUSAL (round1 tok/api.py::build_vocabulary/420, re-filed at :462 -- the body had no
    # stamp, no comparison and no counter at all). `_retok_cache` holds the LAST call's (data
    # object, start, length, stamp); a call is a re-segmentation of the SAME material precisely when
    # `data` is the SAME OBJECT (not merely equal content -- identity is O(1) and is what the
    # composition root actually does: it re-tokenizes its own live stream buffer, it does not build
    # a new bytes object with the same content) at the SAME start. THE INVARIANT IS (size,
    # len(seq2id)), NOT size ALONE, because retire() pops a sequence from the match table -- taking
    # segmentation down a different path -- without moving vocab.size(); a stamp of size alone would
    # call a retire-only change a no-op and skip a rebuild the match table actually needs.
    stamp = (vocab.size(), len(vocab.seq2id))
    cache = vocab._retok_cache
    is_retok = cache is not None and cache[0] is data and cache[1] == start and cache[2] == len(data)
    if is_retok and drop <= 0.0 and cache[3] == stamp and not cache[5]:
        # THE SKIP TEST IS DISABLED WHENEVER dropout > 0 (the docstring's own words), because a
        # regularized call is no longer a deterministic function of the vocabulary alone -- it also
        # depends on the draw from `stream`, so returning the cached Segmentation here would freeze
        # BPE-dropout's output across an entire retok cadence instead of drawing a new mask, which
        # is the mechanism, not a shortcut around it. `drop <= 0.0` rather than `not regularize`
        # because the two arms agree at TOK_DROPOUT=0 (the shipped default) and the guard should
        # track the ACTUAL draw, not the caller's intent, in case a future caller ever regularizes
        # at dropout=0.
        # AND `not cache[5]`: THE TEST IS ALSO DISABLED WHEN THE CACHED ANSWER ITSELF CAME FROM A
        # DRAW (r3 finding, tok/api.py::tokenize). Both halves of the guard used to look only at
        # THIS call, so a deterministic call landing on a regularized cache entry was served the
        # regularized Segmentation -- exactly the case this docstring rules out ("never for held-out
        # text, generation, or the final segmentation, which must be deterministic"), and it was
        # counted as tok.retok_noop, a row whose whole meaning is "the rebuild would have been
        # byte-identical". Measured on the training text at TOK_DROPOUT=0.3: the deterministic call
        # came back with the previous call's 165 ids where a real deterministic segmentation of the
        # same bytes against the same table is 150 -- 15 tokens of BPE-dropout noise in the final
        # segmentation, under a counter saying nothing had changed, which is the FALSE EQUATION
        # spine/gate.py refuses in its own domain. At the shipped TOK_DROPOUT=0.0 nothing moves:
        # cache[5] is False on every entry, and the cached and freshly built segmentations were
        # verified identical.
        vocab.counters["tok.retok_noop"] = vocab.counters.get("tok.retok_noop", 0) + 1
        return cache[4]
    if is_retok:
        # A REAL RE-SEGMENTATION: the match table moved since the cached call (or dropout forced a
        # fresh draw), so the rebuild is not byte-identical and is counted as activity rather than
        # folded into tok.segment, which is why the docstring reports the two SEPARATELY -- a frozen
        # run's no-op retoks must read as skipped, not as work performed.
        vocab.counters["tok.retok"] = vocab.counters.get("tok.retok", 0) + 1
    vocab.counters["tok.segment"] = vocab.counters.get("tok.segment", 0) + 1

    # THE TWO COUNTERS THIS ENTRY POINT DECLARES AND NOTHING WROTE (r3 finding: both read
    # armed-but-0 forever, and byte_fallback in particular is the row that says whether the
    # vocabulary is being used at all). `counts` is passed from HERE and from nowhere else, so the
    # numbers are the run stream's segmentations and not the build sample's -- see _segment.
    counts = {"skip": 0, "byte": 0}
    ids, byte_pos = _segment(vocab, data, dropout=drop, stream=stream, start=start, counts=counts)
    vocab.counters["tok.byte_fallback"] = (vocab.counters.get("tok.byte_fallback", 0)
                                           + counts["byte"])
    if drop > 0.0:
        # ABSENT, NOT ZERO, WHENEVER THE DRAW DID NOT HAPPEN. The docstring's word for the
        # dropout=0.0 default is "unreachable", and this file's convention (_replay_merges on
        # tok.load_reconciled, the build loop on tok.build_pass) is that an unreachable mechanism
        # leaves its key ABSENT while an armed one that did not fire prints 0. Keyed on `drop`, the
        # ACTUAL draw, and not on `regularize`, for the same reason the skip test above is.
        vocab.counters["tok.dropout_skip"] = (vocab.counters.get("tok.dropout_skip", 0)
                                              + counts["skip"])

    # THE LABEL PER TOKEN, carried from the per-byte labels DATA produced. A token spans bytes and
    # therefore could span a splice seam; it takes the label of its FIRST byte, which is the one
    # the byte_pos coordinate names, so a per-area score and a byte offset always agree.
    out_labels = None
    if labels is not None:
        out_labels = [labels[p] for p in byte_pos]

    seg = Segmentation(ids=ids, byte_pos=byte_pos, labels=out_labels,
                       bytes_per_token=_derive.bytes_per_token(len(data) - start, len(ids)))
    # CACHED FOR THE NEXT CALL'S COMPARISON, ALWAYS -- including the dropout>0 arm, so that a
    # subsequent deterministic call (dropout back at 0, or the final pre-eval segmentation) has a
    # real stamp to compare against rather than one left over from two calls ago. THE LAST FIELD IS
    # WHETHER THIS ANSWER CAME FROM A DRAW, and it is what keeps that always-cache honest: the entry
    # is then usable as a STAMP by the next call and unusable as an ANSWER, which is the distinction
    # the five-field tuple could not express.
    vocab._retok_cache = (data, start, len(data), stamp, seg, drop > 0.0)
    return seg


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

    WHAT THE ROOT DOES WITH batch_windows OF THESE (Q-TOK-12, ruled 2026-09-02: THE OR, option
    (b)). This is asked PER WINDOW; mint_burst, the retok and judge_probation act PER FLUSH, so
    batch_windows Dues reach one flush. The root ORs them, PER CADENCE KEY -- mint, retok and
    probation each separately -- and takes `frozen` from the LAST window of the batch, which is the
    same thing as the OR because frozen is a STATE and monotone (at step >= freeze_at it is True
    from then on), said here so no reader has to notice that for themselves.
    TAKING THE LAST WINDOW'S DUE WAS REFUSED, and the arithmetic is why. Every cadence here is
    elapsed-since-last-fire and _due RECORDS the step, so a Due a flush discards is a fire that is
    silently GONE. A Due survives under "last" only when the window that raised it is the last of
    its batch, i.e. at a rate of gcd(period, batch_windows) / batch_windows: at grow_every=200 with
    batch_windows=16 that is HALF of all mints and half of all retoks dropped, and at any period
    coprime with the batch it is 15 of every 16. That is the same silent non-fire this whole cadence
    design exists to prevent -- minting fired 999 times at batch_w=1 and ZERO at batch_w in
    {2,8,15,16,32} under the modulo form -- reintroduced by a different route and at a computable
    rate. The OR's cost is bounded latency instead: a flush acts on a cadence raised up to
    batch_windows-1 windows earlier, under 8% of one grow_every period at batch_w=16. It is also
    consistent with judge_probation's other input, which is the counter THIS FLUSH'S WHOLE BATCH
    updated, so the act and the counter cover the same windows.
    AT THE SHIPPED batch_windows=1 THE TWO READINGS ARE IDENTICAL and no recorded result moves; the
    divergence appears at BATCH_W=16, which is what the heavy-run command uses.
    BIRTH STEPS ARE FLUSH-ALIGNED, and that is the one thing to write down rather than rediscover:
    `step` handed to mint_burst and judge_probation is clock.step AT THE FLUSH, so a token minted on
    an OR-ed Due is born up to batch_windows-1 windows after the window that raised it.
    probation_deadline compares step - birth and both are Windows, so nothing raises.

    RECEIVES: step <- RUN's RunClock, as units.Windows.
    RETURNS: Due.

    LEVERS READ: mode, grow_every, retok_every, freeze_at, probation_deadline, probation_uses
    WIRES READ: none
    DID IT FIRE: tok.tally, tok.due_mint, tok.due_retok, tok.due_probation, tok.mint_frozen_at
                 (the step, or unreachable when freeze_at = 0),
                 tok.due_merged (flushes where MORE THAN ONE window of the batch raised the same
                 key -- unreachable at batch_windows=1, which is the shipped default),
                 tok.due_dropped (Dues discarded by the flush: 0 BY CONSTRUCTION under the OR, and
                 declared precisely because a counter that must read zero is the only way a later
                 reader can tell which reading was actually implemented. Under the refused "last"
                 reading this is the number that says what it cost)
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
    mint_novel > 0 it took the most NOVEL one (ISSUES P1-M77). A candidate refused for max_bytes or
    for already existing is SKIPPED, not returned as "nothing left to mint": that hole stalled a
    vocabulary at 658/4000 with 1866 pairs still above min_pair. A candidate whose bytes already
    exist at a RETIRED id is a REINSTATEMENT -- put the old id back in the match table, mint
    nothing -- because retire() pops from seq2id and leaves id2bytes, so re-minting creates two ids
    with identical bytes and splits the statistics between them (ISSUES P1-M79).

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
      TOK_COMPOSE=0 (ISSUES P1-M41).

    RETIREMENT IS SOFT: the bytes are popped from the match table so segmentation stops producing
    the token and its text re-segments to its parts, while the id and its embedding row stay. Ids
    are POSITIONAL -- merges[] is replayed in order and every later token is built on this one's
    index -- so removing an id would renumber the vocabulary and invalidate every checkpoint.
    Retired ids are returned in the Judgement so LM can keep them in the dead-row accounting: a
    retired id sits BELOW vocab_size and sailed straight through a suffix-only mask_dead (on the
    probation arms 217 and 224 of 256 minted tokens were retired that way).

    RECEIVES: appearances <- the training loop's per-token appearance counter (the old _tok_seen,
    self_organize.py:6804), the ONE shared mutable tensor in this contract; residual_ratio <-
    LM.residual_ratios(lm, model), LM's JUDGEMENT-TIME read of ||delta[t]|| / ||composite[t]||,
    which cannot be a build-time wire because it is read off a live tensor. IT IS NOT THE
    MintReport'S residual_ratio AND THIS CLAUSE USED TO SAY IT WAS (corrected 2026-09-02,
    Q-TOK-11): the MintReport is produced at the mint, when the free residual is zero by
    construction under every new_row_init arm, so the embed arm would have retired 100% of
    candidates. None arrives at lm.compose=False and the Gate below prints unreachable.
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


def save_vocabulary(tok: Config, vocab, *, suffix=""):
    """Write merges plus the settings this run actually used BESIDE THE SNAPSHOT THAT NAMES THEM,
    or return None when d_vocab_save_path is empty (saving is off). NEVER writes to
    d_vocab_read_path: that file is the parent's.

    THE SUFFIX, AND WHY IT IS AN ARGUMENT AND NOT PART OF THE WIRE (Q-TOK-10, ruled 2026-09-02 --
    A FROZEN SIGNATURE MOVED HERE). CKPT.save takes `suffix` and says "THE SUFFIX APPLIES TO THE
    WHOLE SNAPSHOT, NOT ONLY TO ckpt.pt", and A SNAPSHOT'S VOCABULARY IS PART OF THE SNAPSHOT.
    Without it this call always wrote the base file, so a reason="bestN" save wrote
    runs/x.best3/ckpt.pt and OVERWROTE runs/x.dyntok.json -- ISSUES P1-M46 exactly, multiplied n times
    over by best_keep. It is worse in this tree than an overwrite: resuming from a best snapshot
    sets CKPT.resume to that snapshot's base, so d_vocab_read_path resolves to
    <base>.best3.dyntok.json, A FILE NOTHING EVER WROTE; build_vocabulary falls through to "build",
    and the restored embedding table is indexed by a freshly minted, different vocabulary. The
    best-snapshot resume path could not work at all.

    IT CANNOT BE A WIRE, and that is the framework rule rather than a preference: the suffix is
    chosen AT RUNTIME by the retention policy (CKPT.BestAction, ckpt/api.py::<module>) and a coupling's
    compute sees only frozen Configs. A runtime value reaches a package as an ARGUMENT -- the same
    rule that made bytes_per_token an argument to DATA.data_plan and curve_bpb an argument to
    CKPT.Retention.consider.

    WHAT IS WRITTEN: d_vocab_save_path with `suffix` spliced in immediately BEFORE the
    ".dyntok.json" tail, so a snapshot at <base><suffix> is accompanied by
    <base><suffix>.dyntok.json. suffix="" is the ordinary periodic/final save and writes the wire's
    own value unchanged. THE READ SIDE THEN NEEDS NO EDIT AT ALL: d_vocab_read_path is
    CKPT.resume + ".dyntok.json" and CKPT.resume names the snapshot the operator is resuming FROM,
    suffix included -- so the two sides meet exactly.
    THE ".dyntok.json" TAIL IS NOW NAMED IN THREE PLACES AND THEY MOVE TOGETHER: the two couplings
    in spine/assemble.py (which already state it twice, once per direction) and this splice. The
    considered alternative -- have the couplings carry CKPT.dir/CKPT.resume as bare bases and let
    TOK own the extension -- puts the rule in one home but leaves two wires named `..._path`
    carrying something that is not a path, changes both wires' resolved values (and the hand-computed
    fixtures in tests/test_assemble.py and tests/test_couplings.py that pin them), and buys nothing
    the splice does not. Splicing generically (before the LAST dot, or via splitext) is NOT
    equivalent and must not be written: the tail has two dots, so splitext yields
    <base>.dyntok.best3.json while the read side looks for <base>.best3.dyntok.json.
    THE OTHER OPTION IS NOT TAKEN AND THE REASON IS RECORDED: moving the merges into payload["TOK"]
    would make the snapshot self-contained -- which ckpt/api.py::save CLAIMED UNTIL THIS SAME RULING
    CORRECTED IT, and reading that sentence in the present tense is now wrong: it says "A SNAPSHOT'S
    VOCABULARY IS PART OF THE SNAPSHOT -- BUT NOT IN `payload`", which is this ruling and not the
    alternative to it. What follows is why the alternative was priced and refused, not a live
    disagreement between two frozen docstrings. build_vocabulary's merge source is the FILE
    (tok/api.py::build_vocabulary) and the payload is not one of
    its arguments, so it costs either a second signature change (build_vocabulary gains `saved=`)
    or re-chartering restore_vocab from "refuse on mismatch" to "install the match table" -- which
    throws away a full corpus build and leaves bytes_per_token measured on a vocabulary that was
    then replaced -- and it strands d_vocab_read_path, half of a promote the census made on
    purpose. If the owner rules that a checkpoint plus a sidecar is one artifact too many, that
    ruling overrides this one and the full cost above is what it costs.

    RECEIVES: suffix <- the same value the root hands CKPT.save on this save, on the C rows.
    RETURNS: str path, or None.

    LEVERS READ: none
    WIRES READ: d_vocab_save_path
    DID IT FIRE: tok.vocab_saved, tok.vocab_saved_suffixed (a snapshot-suffixed write; 0 means no
                 bestN save has happened, which at CKPT.best_keep=0 is "unreachable" and must say
                 so rather than read 0)
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
    WIRES READ: d_cap_lift_period (reported beside tok.cap_lift. THE AUTHORITY ON "0 lifts --
                never full, or never plateaued?" IS CAP.counters' block-reason histogram, in the
                package that owns the valve and in the unit the valve compares; this line prints
                the period and points there, and must not grow a second verdict of its own. See
                FOR THE OWNER Q-CLOCK-1, MEASURABLE: this row retires when CAP.counters has a body
                that renders that histogram, and not before)
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
