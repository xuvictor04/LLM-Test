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
import json
import math
import os

import heapq

from spine.lever import Config, LeverError
from spine import derive as _derive
from spine import rng as _rng
from spine import units as _units
from spine.gate import Gate


# ==================================================================================================
# WHAT EACH NON-FINITE FLOAT LEVER WAS MEASURED TO DO, quoted verbatim into build_vocabulary()'s
# refusal so an operator reads what their number DID rather than a rule about numbers. Measured one
# lever per fresh subprocess through a real spine.assemble.build(environ=...), a real
# TOK.build_vocabulary over ~10 kB of two-area text, and then tokenize(regularize=True) twice and
# tokenize(regularize=False) once. Keyed by the GENERATED env name, which is what the operator typed.
# A float lever added to tok/levers.py with no entry here raises KeyError from build_vocabulary the
# first time it is set non-finite -- deliberately, because a lever with no measurement has no
# business quoting one.
# ==================================================================================================
_NONFINITE_MEASURED = {
    "TOK_DROPOUT":
        "a PROBABILITY, and every guard in this package is `dropout > 0.0` while the draw is "
        "`stream.random() < dropout`. AT +inf EVERY DRAW IS A SKIP: measured tok.dropout_skip 3999 "
        "over 4000 bytes, the seed build minting 143 tokens instead of 256 with tok.build_refused "
        "143, the vocabulary landing at 399 instead of 512, and -- the number that leaves this "
        "package -- bytes_per_token MEASURED AT 1.0 against 3.5925925925925926 at the default. That "
        "single float is spine/derive.py::signature_width_bytes's input for SIG's ONE window width "
        "for the whole run and DATA's splice gate reads it too, so a typo here silently makes the "
        "signature window several times too narrow. IT ALSO UNDOES THE tok.dropout.mint REPAIR "
        "THROUGH THE VALUE INSTEAD OF THROUGH THE STREAM: at +inf two successive "
        "tokenize(regularize=True) calls returned the IDENTICAL 4000 ids, which is the exact "
        "symptom -- 'BPE-dropout that returns the same answer on every call is not dropout, it is a "
        "second deterministic segmentation' -- that the child stream exists to prevent, because a "
        "skip probability of infinity is not random. AT nan THE COMPARISON NEVER FIRES: `nan > 0` "
        "is False, so no stream is even attached, and build, both regularized calls and the "
        "deterministic call were BIT-IDENTICAL to TOK_DROPOUT=0.0 (size 512, bytes_per_token "
        "3.5925925925925926, tok.dropout_skip ABSENT from the ledger) -- and this file's own "
        "convention is that an ABSENT counter means the branch is unreachable, so the report says "
        "the regularizer is off on a run the operator switched on",
    "TOK_MINT_PMIN":
        "the pre-mint quality criterion, read by TOK.mint_burst, which raises NotImplementedError "
        "today -- so a non-finite value here has NO live reader and is refused for what it freezes "
        "into the Config rather than for a measured effect. It arms the day that body is written: "
        "mint_burst re-ranks the candidate window by p(b|a) against this threshold, and both halves "
        "of that comparison are the shape every guard in this sweep failed on",
    "TOK_MINT_NOVEL":
        "the novelty exponent, read by TOK.mint_burst, which raises NotImplementedError today -- "
        "same standing as TOK_MINT_PMIN. Note that this lever's declaration says in as many words "
        "that a value ABOVE its unit label is legal ('a reader who takes fraction 0..1 as a bound "
        "on legal values will be surprised by 2.0, which is legal'); 2.0 is an exponent, and "
        "infinity is not one",
    "TOK_PROBATION_RESIDUAL":
        "the residual-ratio threshold, read by TOK.judge_probation, which raises "
        "NotImplementedError today -- same standing as TOK_MINT_PMIN. It is one side of a ratio "
        "comparison, which is the family that goes silent rather than loud at nan",
}


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
                 "dropout_rng", "counters", "gates", "tally", "tally_seen", "rev",
                 "_retok_cache")

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
        # PROV CARRIES THE BIRTH STEP FOR AN ONLINE MINT AND A BARE STRING FOR THE REST, and
        # this line said "id -> how it was minted" alone until judge_probation was written. The old
        # tree's probation test is quoted in tok/levers.py::TOKLevers.probation_deadline as
        # `step - TOK.prov[t][2] >= TOK_PROBATION_STEPS`, so the birth step lived in this table
        # there too, and TOK.vocab_state's docstring already promises "the prov table with birth
        # steps" -- there was nowhere for that promise to be kept. The two shapes:
        #   "build" | "replay" | "replay:..."        -- minted before the loop; never on probation
        #   ("online", born)                         -- minted by TOK.mint_burst at window `born`,
        #                                               NOT YET JUDGED
        #   ("online", born, "kept" | "retired")     -- judged by TOK.judge_probation, verdict kept
        # THE VERDICT IS THE THIRD ELEMENT AND NOT A SEPARATE SET, because a separate set is a
        # second home for the same fact and TOK.vocab_state carries exactly `retired` and `prov`
        # across a checkpoint (DEFECT D-T3 is what happens when a retirement has no home in the
        # file): with the verdict inside prov, one table says both what a token is and whether its
        # probation is over, and restore_vocab's existing `{int(k): v for ...}` carries it with no
        # edit. A torch.save payload round-trips the tuple; a JSON one would hand back a LIST, so
        # every reader here takes a sequence of length 2 or 3 and refuses anything else loudly --
        # see _prov_online.
        self.prov = {}               # id -> "build" | "replay" | ("online", born[, verdict])
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
        #   on purpose: the build seeds tok.build_pass/build_mint/build_converged/build_refused on
        #   the arm that runs the loop, _replay_merges writes tok.load_reconciled(_detail) on the
        #   arm that
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
        # THE PAIR TALLY, WHICH IS THE CANDIDATE EVIDENCE TOK.mint_burst DRAWS ON. It lives on the
        # Vocabulary because TOK.on_window's own docstring puts it here -- "Tallies the adjacent
        # pairs of `ids` into the vocabulary's tally" -- and because mint_burst's frozen signature
        # is (tok, vocab, *, step): no ids reach it, so the vocabulary is the ONLY channel a
        # candidate can arrive through.
        # IT IS CUMULATIVE AND IS NOT CLEARED AT A BURST. `tally_seen` is what each pair's count
        # WAS when a burst last considered it, and tok.mint_novel's re-rank is
        # (c - seen)/(1+seen)**novel -- growth since last considered. Clearing the tally would make
        # `seen` meaningless and turn the novelty re-rank into a second copy of plain frequency,
        # which is the one knob in this package that addresses the tokenizer's own version of
        # catastrophic forgetting (tok/levers.py::TOKLevers.mint_novel).
        # `tally_seen` IS ONLY MAINTAINED AT mint_novel > 0. At the shipped 0.0 nothing reads it,
        # and one entry per considered pair for the length of a run is the unbounded-instrument
        # shape ISSUES P1-L68 records against h_pmin_seen (one float per candidate, millions at
        # cand_window=1024).
        # NOTHING FILLS `tally` TODAY: TOK.on_window is the only declared producer and it is still
        # a P4 stub that spine/loop.py does not call, so a burst on the tree as it stands finds an
        # empty tally and mints nothing. That reads as tok.mint 0 with tok.mint_exhausted 1 -- a
        # measurement of an empty pool -- and mint_burst says so in its own comment rather than
        # letting the two states collapse.
        self.tally = collections.Counter()
        self.tally_seen = {}
        # THE MATCH-TABLE REVISION COUNTER, AND IT CLOSES A HOLE THIS FILE NAMED IN ADVANCE.
        # tokenize()'s stamp was (size, len(seq2id), len(retired)) and its own comment says what
        # that triple cannot see: "a retire of one id paired with a REINSTATEMENT of a different
        # retired id in the same flush moves len(seq2id) by -1 then +1 AND len(retired) by +1 then
        # -1, both to a net zero, while the match table has genuinely changed. No count of the two
        # sets can see that; only a monotone revision number bumped by every match-table mutation
        # can, and there is nothing to bump it in yet." Both bodies that mutate the match table now
        # exist -- mint_burst reinstates, judge_probation retires -- and LOOP_ORDER puts them on
        # the same flush, so the pair is reachable rather than hypothetical. This is that number:
        # bumped by _add, _retire and _reinstate, read by tokenize as the fourth stamp term, and
        # never reset (a resumed run keeps counting from zero, which is correct -- the cache is
        # per-process and starts empty).
        self.rev = 0
        # THE RE-SEGMENTATION NO-OP CACHE (round1 tok/api.py::build_vocabulary/420, re-filed at :462). One slot,
        # not a dict keyed by every text ever segmented: the contract's own words are "since the
        # LAST one", singular, and tokenize() is called once per epoch plus on every
        # retokenization -- a growing cache of every held-out probe this run ever segmented would
        # be an unbounded leak for a check whose entire job is to catch the one specific pattern
        # measured at 2.189 b/B and 68 points of word quality: the SAME data re-segmented from the
        # SAME start while nothing minted in between.
        # (data, start, len(data), stamp, Segmentation, drawn_with_dropout, labels); None until
        # the first call. The last two fields are not niceties: an entry produced under BPE-dropout
        # is a legitimate stamp for the next call's comparison and an ILLEGITIMATE answer to return
        # to a deterministic one, and an entry produced from one `labels` vector is an illegitimate
        # answer to a call that passed a different one. tokenize()'s skip test reads both for
        # exactly that.
        # EVERY INPUT THE CACHED ANSWER DEPENDS ON, AND WHICH FIELD COVERS IT -- written out here
        # because two of the seven were found one at a time by two separate readers, and the third
        # reader should not have to hunt for a fourth (r3 found `drawn_with_dropout`, r4 found
        # `labels`). tokenize's signature is (tok, vocab, data, labels, *, start, regularize, seed):
        #   data       -> cache[0] BY IDENTITY plus cache[2] len(data). Identity, not equality, is
        #                 deliberate: it is O(1) and it is what the composition root does (it
        #                 re-tokenizes its own live stream buffer). An in-place mutation of `data`
        #                 that preserves its length defeats it, and that is the accepted price.
        #   start      -> cache[1].
        #   labels     -> cache[6], BY IDENTITY, on the same terms as `data` and for the same
        #                 reason: the root hands the same list object back on a re-tokenization of
        #                 its own stream, so the skip still fires where it was measured.
        #   regularize -> cache[5] for the entry, and the caller's own `drop <= 0.0` for this call.
        #                 Both halves are needed: one keeps a drawn answer from being served to a
        #                 deterministic caller, the other keeps any cached answer from freezing a
        #                 draw the regularizer is supposed to make afresh.
        #   tok        -> only tok.dropout is read, and it reaches the test through `drop` above.
        #   seed       -> NOT COVERED AND DOES NOT NEED TO BE: tokenize's body never reads it (see
        #                 that function's own note on the parameter). It selects nothing, so it
        #                 cannot make a cached answer wrong.
        #   vocab      -> cache[3], the stamp: FOUR terms over the three structures _segment
        #                 consults -- seq2id (through size() and len(seq2id)), `retired` (len),
        #                 and `mlbf` -- the per-first-byte max length that decides which
        #                 lengths are probed at all -- through `rev`, the fourth term.
        #                 THIS PARAGRAPH SAID TWO UNTIL 2026-09-04 and _segment reads all
        #                 three (`s2i, mlbf, retired = ...`, then `hi = min(mlbf[b0], n - i)`).
        #                 mlbf needed no term of its own while _add was its only writer: _add
        #                 always appends to id2bytes first and so always moves size(), so the first
        #                 stamp term caught every change to it. THE REINSTATEMENT THAT PARAGRAPH
        #                 WARNED ABOUT NOW EXISTS (2026-09-17): Vocabulary._reinstate puts a
        #                 sequence back into the match table without going through _add and raises
        #                 mlbf itself when it has to. It is covered by the FOURTH stamp term rather
        #                 than by a term of its own -- `vocab.rev`, the monotone revision counter
        #                 _add, _retire and _reinstate all bump, which is precisely what that
        #                 warning asked for. There is no longer a match-table change this stamp
        #                 cannot see.
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
        # THE MATCH TABLE MOVED. size() moves here too, so tokenize's stamp already caught this
        # site; the bump is here anyway because the invariant `rev` states is "every mutation of
        # the match table", and a term that holds for two of its three writers is a term the third
        # reader has to re-derive.
        self.rev += 1
        return i

    def _retire(self, i):
        """Withdraw one id from the match table WITHOUT renumbering. True if this call moved it.

        BOTH HALVES, AND NEITHER ALONE. `seq2id` is popped so _segment stops producing the token
        and its text re-segments to its parts; `retired` gains the id so live_size()'s subtraction
        is right and so TOK.vocab_state has something to carry across a checkpoint (DEFECT D-T3).
        _segment tests BOTH (`j = s2i.get(...)`, then `if j is None or j in retired`), so either
        half alone would stop segmentation -- and either half alone would also leave one of
        live_size() and the reinstatement lookup reading a table the other half contradicts.
        `id2bytes` IS LEFT INTACT AND THE ID IS NOT REUSED. Ids are POSITIONS: merges[] is replayed
        in order and every later token is built on this one's index, so removing an id renumbers
        the vocabulary and attaches the parent's trained embedding rows to different tokens
        (src/tok/api.py::_replay_merges refuses a replay for exactly that reason). The embedding row
        keeps its meaning and LM masks it by id through Judgement.retired_ids.
        THE ALIAS TEST IS NOT DEFENSIVE CLUTTER: two different pairs can produce the same bytes
        ("th"+"e" and "t"+"he"), only one of them owns the seq2id entry, and popping on behalf of
        the other would take a LIVE token out of the match table under another token's retirement.
        """
        i = int(i)
        if i in self.retired:
            return False
        seq = self.id2bytes[i]
        if self.seq2id.get(seq) == i:
            del self.seq2id[seq]
        self.retired.add(i)
        self.rev += 1
        return True

    def _reinstate(self, i):
        """Put a retired id back into the match table. True if this call moved it.

        WHY THIS IS NOT A FRESH MINT (ISSUES P1-M79). retire() pops from seq2id and leaves
        id2bytes, so the bytes are absent from the match table while the id still exists; minting
        them again would create a SECOND id with identical bytes and split every statistic between
        the two -- and LM would initialise a fresh row for a token that already has a trained one.
        `mlbf` IS REPAIRED HERE AND THAT IS NOT BELT-AND-BRACES. tokenize()'s stamp paragraph names
        this exact shape: "putting a sequence back into seq2id without going through _add moves
        neither size() nor mlbf's writer". mlbf[b] bounds the lengths _segment probes at a position
        starting with byte b, so a sequence back in seq2id whose length exceeds that bound is a
        table entry the matcher never probes for -- present, and unreachable. It cannot be too
        small on the path this tree takes today (mlbf never shrinks, and the id was minted through
        _add), so this is the one line here that is written for the path rather than for the run.
        """
        i = int(i)
        if i not in self.retired:
            return False
        seq = self.id2bytes[i]
        self.seq2id[seq] = i
        self.retired.discard(i)
        b0 = seq[0]
        if len(seq) > self.mlbf[b0]:
            self.mlbf[b0] = len(seq)
        if len(seq) > self.maxlen:
            self.maxlen = len(seq)
        self.rev += 1
        return True


@dataclasses.dataclass(frozen=True)
class Mint:
    """One token TOK.mint_burst minted, and the evidence it was minted on.

    THE COUNT TRAVELS WITH THE MINT because it is the whole case for the merge: an operator reading
    a burst of six sees what each one was taken on, and a token minted at a count barely over
    tok.min_pair is the "merge taken on a transient burst" that probation exists to catch
    (tok/levers.py::TOKLevers.probation_deadline).
    A REINSTATEMENT IS NOT A Mint AND MUST NOT BE ONE. The composition root hands this list to
    LM.on_mint for new-row initialisation and to SIG for the encoder row; a reinstated id already
    carries a trained row, and initialising it again would destroy exactly the learning the soft
    retirement was designed to preserve. Reinstatements are counted on tok.mint_reinstated and
    appear in no list.
    """
    new_id: int
    left_id: int
    right_id: int
    token_bytes: bytes
    count: int


@dataclasses.dataclass(frozen=True)
class Judgement:
    """What TOK.judge_probation decided, and the two vocabulary sizes that are NOT the same number.

    `live_size` and `id_count` ARE DIFFERENT NUMBERS AND BOTH ARE NEEDED, which is this module's
    header verbatim. id_count is the positional boundary -- where never-minted rows begin, i.e.
    Vocabulary.size() -- and it is what LM.decode's `live_vocab` argument must receive, because ids
    are positional: retire() pops from the match table and leaves id2bytes intact, so retired rows
    sit BELOW the boundary and are handled separately, by id. live_size is that boundary minus the
    retired count, and passing it to decode would move the boundary down and mask exactly that many
    LIVE rows to -inf.
    `kept` IS THIS CALL'S AND `retired_ids` IS THE WHOLE SET, and the asymmetry is deliberate
    rather than an oversight. A kept token is marked in `prov` and never judged again, so "kept" has
    no meaning other than "kept by this call". `retired_ids` is the REFRESH LM.decode takes
    (spine/compose.py::LOOP_ORDER's judge_probation row: "retired_ids -- Judgement.retired_ids,
    LM.decode's exact spelling and the REFRESH of what the vocabulary produced at assembly"), and a
    mask built from one flush's retirements alone would re-admit every row retired before it.
    """
    kept: tuple
    retired_ids: tuple
    pending: int
    live_size: int
    id_count: int





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

    REFUSES AT STARTUP, AT THE FIRST READ, BEFORE THE Vocabulary IS CONSTRUCTED. This is TOK's
    first entry point (row 11 of spine/compose.py::ASSEMBLY_ORDER), so it is the earliest place this
    package's own code sees any of its numbers:
      * ANY OF THIS PACKAGE'S FOUR FLOAT LEVERS NON-FINITE -- dropout, mint_pmin, mint_novel,
        probation_residual -- enumerated through spine/lever.py::Config.keys and ::Config.lever
        rather than by name. Measured at TOK_DROPOUT=inf: every available merge skipped, the
        vocabulary 399 instead of 512 and bytes_per_token 1.0 instead of 3.59 -- the one estimator
        that leaves this package, which spine/derive.py::signature_width_bytes turns into SIG's
        single window width. At nan the comparison never fires and the run is BIT-IDENTICAL to
        TOK_DROPOUT=0.0 while tok.dropout_skip is ABSENT, which this file's convention reads as
        "unreachable" -- a report saying the regularizer is off on a run the operator switched on.
      * NOT TOK_DROPOUT OUTSIDE [0.0, 1.0] -- NOT ANY MORE, AND THIS LINE IS WHERE A READER WOULD
        OTHERWISE GO ON BELIEVING IT DOES. That interval is refused a whole assembly earlier, by
        `domain=(0.0, 1.0)` on tok/levers.py::TOKLevers's `dropout` declaration, and this function's
        own clause was RETIRED into it on 2026-09-15 with its measurement, because a declaration
        that refuses first leaves the clause behind it unable to run. Driven: TOK_DROPOUT=1.5 and
        =1.0000000000000002 are refused at spine/lever.py::Lever.coerce naming the lever and the
        value; 1.0 and 0.0 both build here. See the retirement note in the refusal block below.
      * TOK_MAX_BYTES BELOW 2, which no finiteness rule could ever have reached: it is a finite int
        that passes every type check. A merge joins two units, so at 0 AND at 1 the `len(seq) >
        max_bytes` test in Vocabulary._add refuses every candidate and the vocabulary stays at the
        256 raw bytes (measured: tok.build_mint 0, tok.build_refused 143, bytes_per_token 1.0),
        which is TOK_MODE=bytes reached by deleting the mint instead of by asking for it. 0 is NOT
        a declared sentinel here and the declaration was read first: the five levers in
        tok/levers.py::TOKLevers that DO carry a zero sentinel each spell it out in their own help
        string, and this one spells out the opposite.
    NONE OF THE THREE BOUNDS ANYTHING. They close four values on each of four float levers, the
    finite values outside a declared probability interval, and two counts. TOK_DROPOUT=1.0 is still
    the tokenizer switched off; nothing here caps max_bytes from above, and tok/levers.py records
    that above 16 ByteComposer silently truncates its view of a token.

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
    DID IT FIRE: tok.build_pass, tok.build_mint, tok.build_converged, tok.build_refused (all four
                 PRESENT ONLY ON THE FRESH-BUILD ARM -- absent on mode="bytes" and on the replay
                 arm, where the build
                 loop is unreachable and a 0 would be a false reading rather than a small one.
                 tok.build_refused is candidates at or above min_pair that `_add` REFUSED -- for
                 max_bytes, for already existing, or at the cap -- and it exists because
                 tok.build_converged names a CAUSE and only one of the two ways a pass can mint
                 nothing is that cause: a stall on refusals leaves the tally full, so converged
                 stays 0 and this row carries the number instead),
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

    # ==============================================================================================
    # THE STARTUP REFUSALS, AT THE FIRST READ, BEFORE THE Vocabulary EXISTS. This is TOK's first
    # entry point (row 11 of spine/compose.py::ASSEMBLY_ORDER) and therefore the earliest point at
    # which this package's own code sees any of its numbers.
    #
    # (1) NON-FINITE, over every float lever this package declares -- enumerated through
    #     spine/lever.py::Config.keys and ::Config.lever, so the OWNED env name in the message is
    #     GENERATED and never typed, and a float lever added to tok/levers.py tomorrow is covered
    #     with no second list to go stale. The precedent is src/fabric/api.py::build. THE OTHER
    #     FOURTEEN DECLARATIONS ARE ACCOUNTED FOR AND NOT DECLINED: the twelve int levers are
    #     refused at nan by `int(float(raw))`'s ValueError and at +/-inf by its OverflowError inside
    #     spine/lever.py::Lever.coerce, under their own owned names, and the two str levers (mode,
    #     probation_by) carry `choices=`. 4 + 12 + 2 = 18, the whole set.
    # (2) TOK_MAX_BYTES BELOW 2. See its own block below; it is a COUNT, not a float, and no
    #     finiteness rule could ever have reached it.
    #
    # THERE WAS A THIRD AND IT WAS RETIRED ON 2026-09-15, TO THE DECLARATION AND NOT INTO THIN AIR.
    # `_drop = float(tok.dropout)` followed by `if not 0.0 <= _drop <= 1.0: raise LeverError(...)`
    # stood here from 2026-09-07. src/tok/levers.py::TOKLevers declares `dropout` with
    # domain=(0.0, 1.0), CLOSED at both ends, and spine/lever.py::Lever.coerce applies it at the
    # FIRST read -- one whole assembly before this function exists -- so the clause could not run
    # from any environment. Two refusals for one fact, the second unreachable: the untrippable-guard
    # family, which is this repository's second-largest defect class. The fork stated by
    # tests/test_ownership.py::check_o15_domain_agrees_with_read_site is retire-or-drop and never
    # both, and the RETIRE arm was taken here for the reason .rework/audits/e_opt.json and
    # e_fabric.json set as the discriminator: what the clause knew was a property OF THE NUMBER --
    # the draw it is compared against, `stream.random() < dropout`, runs on [0.0, 1.0), so at or
    # below 0.0 no merge is ever skipped and at or above 1.0 every available merge is -- and a
    # (lo, hi) pair states exactly that. It knew nothing that depends on another lever, on an arm,
    # or on a mechanism, which is the shape no pair can express and the only reason to keep a clause.
    #
    # THE TWO SETS WERE ESTABLISHED BY DRIVING THEM, NOT BY READING THE OPERATORS, because a pair
    # narrower than the clause would have meant dropping a working refusal to green a check (which
    # is what FAB_DISCOVER=3.0 was). 22 values per arm from -1e9 to 1e26 -- including -0.0, -1e-320,
    # 1e-320, -1e-09, 0.9999999999999999, 1.0, 1.0000000000000002, nan, inf, -inf -- one fresh
    # process per cell, through a real spine.assemble.build and this function, first on the shipped
    # tree and then with the pair NEUTRALISED in a copy of src/ outside the repository so the clause
    # answered alone. 22 of 22 cells IDENTICAL in verdict; neither rule is wider. And unlike OPT's
    # twelfth refusal, the clause gains nothing from the other arm of the switch: with
    # spine/lever.py::REFUSE_NON_FINITE_FLOAT = False, refusal (1) above -- which is GENERATED over
    # tok.keys() and not a list -- refuses nan, +inf and -inf here by name with the pair gone, so
    # the clause was dead in BOTH arms.
    #
    # ONE SENTENCE OF THE RETIRED CLAUSE DID NOT SURVIVE THE MOVE AND IS RECORDED CORRECTED RATHER
    # THAN REQUOTED, per the OPT precedent. It said the interval follows because "it is declared as
    # units.PROBABILITY ... and a probability is not outside [0, 1]". That is the argument THIS
    # PACKAGE HAS ALREADY RULED AGAINST: src/tok/levers.py::TOKLevers says of `mint_novel` that a
    # reader who takes the unit label as a bound on legal values "will be surprised by 2.0, which is
    # legal", and 75 levers in this tree carry U.FRACTION with no domain. The conclusion was right
    # and the stated reason was the wrong one; the declaration now carries the argument from the
    # DRAW instead. The measurement the clause carried -- 1.5 measured to do exactly what +inf does,
    # and bytes_per_token being the one number that LEAVES this package -- moved to the declaration
    # with it and is not repeated here.
    #
    # WHAT REMAINS DOES NOT CLAIM, AND NOTHING BELOW SAYS OTHERWISE. TOK_DROPOUT=1.0 IS ADMITTED,
    # by the declared domain and by every rule in this file, AND IS MEASURED TO DO THE SAME DAMAGE
    # as 1.5 and as +inf: `stream.random()` draws from [0, 1), so at p=1.0 every draw skips and the
    # segmentation is deterministic again -- driven 2026-09-15 on a 10000-byte two-area sample,
    # three tokenize(regularize=True) calls returning ONE distinct answer, all 10000 ids, against
    # three distinct answers at 0.3. An operator who types 1.0 has switched the tokenizer off, not
    # turned the regularizer up, and nothing in this package stops them. The three float levers
    # other than dropout have NO declared interval at all and nothing here bounds any of them from
    # either side.
    # ==============================================================================================
    _nonfinite = []
    for _field in tok.keys():
        if _field.startswith("d_"):
            continue                        # a wire is another package's number arriving, not a lever
        _decl = tok.lever(_field)           # spine/lever.py::LeverView -- default, unit, OWNED env name
        if not isinstance(_decl.default, float):
            continue
        _v = float(getattr(tok, _field))
        if not math.isfinite(_v):
            _nonfinite.append((_decl.env_name, _v))
    if _nonfinite:
        raise LeverError(
            f"TOK: non-finite lever(s) "
            f"{', '.join(f'{k}={v}' for k, v in _nonfinite)}. A nan or an infinity is not a "
            f"probability, an exponent or a ratio, and this package declares no float lever for "
            f"which any of the three is a reading -- every declared sentinel in "
            f"tok/levers.py::TOKLevers is a ZERO, and each of the four says so in its own help "
            f"string or comment (TOK_MINT_PMIN '0 mints on frequency alone', TOK_MINT_NOVEL '0 "
            f"reproduces plain most-frequent minting', TOK_DROPOUT 'the default is 0.0 so it has "
            f"never run'). WHAT EACH ONE WAS MEASURED TO DO: "
            + " || ".join(f"{k}={v}: " + _NONFINITE_MEASURED[k] for k, v in _nonfinite)
            + ". REFUSED AT STARTUP AND NOT DESCRIBED BY A GATE, because a Gate reason is a report "
              "and the mechanism still runs. WHAT THIS REFUSAL DOES NOT CLAIM: it closes four "
              "values per lever and BOUNDS NOTHING. TOK_DROPOUT=1.5 is finite and was measured to "
              "do exactly what +inf does; it is closed one layer EARLIER than this, by the "
              "domain=(0.0, 1.0) on tok/levers.py::TOKLevers's `dropout` declaration, which is "
              "where that interval's argument and its measurement now live -- this function's own "
              "[0.0, 1.0] clause was RETIRED to it on 2026-09-15 because it could no longer run. "
              "TOK_DROPOUT=1.0 does the same damage again and is admitted by both, and so is "
              "0.9999999999999999, measured bit-for-bit identical to 1.0. The other three float "
              "levers here carry no declared interval, so for them this refusal is the only rule "
              "there is and it closes four values.")

    # ==============================================================================================
    # TOK_MAX_BYTES BELOW 2 -- A CEILING SO LOW NO MERGE CAN EXIST UNDER IT.
    #
    # 0 IS NOT A SENTINEL HERE AND THE DECLARATION WAS READ BEFORE THIS WAS WRITTEN. Several levers
    # in this tree use 0 to mean "no cap" and refusing one of those would break a working mechanism,
    # so tok/levers.py::TOKLevers was checked lever by lever: freeze_at ('0 means never freeze'),
    # retok_every ('0 leaves already-emitted ids alone forever'), mint_pmin ('0 mints on frequency
    # alone'), mint_novel ('0 reproduces plain most-frequent minting') and probation_uses ('THE
    # DEFAULT 0 MEANS OFF') each spell their zero out in their own help string or comment. max_bytes
    # spells out the opposite: "The longest byte string a single token may stand for; a candidate
    # merge longer than this is refused." Vocabulary._add implements exactly that as
    # `len(seq) > self.max_bytes`, so 0 is not "no cap", it is a cap that refuses EVERYTHING.
    #
    # MEASURED, one value per fresh subprocess, over the same ~10 kB two-area sample, against the
    # shipped 16 (size 512, tok.build_mint 256, tok.build_refused 0, bytes_per_token
    # 3.5925925925925926):
    #   TOK_MAX_BYTES=0   size 256, tok.build_mint 0, tok.build_refused 143, bytes_per_token 1.0
    #   TOK_MAX_BYTES=1   size 256, tok.build_mint 0, tok.build_refused 143, bytes_per_token 1.0
    #   TOK_MAX_BYTES=2   size 399, tok.build_mint 143, tok.build_refused 136, bytes_per_token 2.0
    # 1 IS IN THE REFUSAL AND 0 IS NOT ALONE THERE because a merge joins two units, so the shortest
    # sequence `_add` can ever be handed is two bytes long: at 1 the ceiling refuses every candidate
    # exactly as it does at 0, and the two are one defect with two spellings. The vocabulary is
    # permanently the 256 raw bytes and the run is a byte-level run -- which is a real configuration
    # this package already has a DECLARED way to ask for, TOK_MODE=bytes, whose arm says so in
    # writing and returns immediately with v0=256 and bytes_per_token=1.0. Reaching it by shrinking
    # a length ceiling instead is the mechanism deleted while TOK_MODE still says "online" and the
    # ledger still prints two build passes.
    # NOTHING AN OPERATOR CAN ASK FOR IS LOST: 2 is legal and is the smallest vocabulary this
    # package has that still mints anything.
    # THE VALUE ALSO LEAVES THIS PACKAGE AND THAT HALF IS NOT CLOSED HERE. spine/assemble.py
    # ::COUPLINGS carries src="TOK.max_bytes" -> dst="LM.d_max_token_bytes", irreducible, computing
    # `int(r["TOK"].max_bytes)`, and LM sizes ByteComposer's byte-index and position tables from it.
    # That coupling runs inside spine/assemble.py::build, before any Config is frozen, and
    # src/lm/api.py::resolve is row 8 of ASSEMBLY_ORDER while this function is row 11 -- so LM has
    # already returned an LMGeometry with max_token_bytes=0 by the time this refusal fires. The run
    # still dies at startup with this message and nothing downstream consumes that geometry, but a
    # caller driving LM.resolve ALONE is not covered from here, and src/lm/api.py is not this
    # package's file to edit. Filed with the exact edit.
    # IT FIRES ON ALL THREE ARMS, INCLUDING mode="bytes", WHERE max_bytes HAS NO LOCAL READER, and
    # that is deliberate rather than an oversight of the early return below: the coupling above
    # computes `int(r["TOK"].max_bytes)` unconditionally inside spine/assemble.py::build, so LM's
    # byte tables are sized from this number on every arm this package has, including the one where
    # no merge is ever attempted.
    # WHAT THIS REFUSAL DOES NOT CLAIM: it closes 0 and 1 and bounds nothing from above.
    # tok/levers.py::TOKLevers.max_bytes records the other end in its own comment -- above 16 the
    # composer silently truncates its view of a token to the first 16 bytes -- and that end is the
    # coupling's business, not a number this function may decide.
    # ==============================================================================================
    _max_bytes = int(tok.max_bytes)
    if _max_bytes < 2:
        raise LeverError(
            f"TOK_MAX_BYTES={_max_bytes} is below 2. It is the longest byte string a single token "
            f"may stand for and Vocabulary._add refuses a candidate with `len(seq) > "
            f"self.max_bytes`; a merge joins two units, so the shortest sequence that can ever be "
            f"offered is two bytes long and a ceiling below that refuses EVERY candidate. It is "
            f"NOT a sentinel: freeze_at, retok_every, mint_pmin, mint_novel and probation_uses all "
            f"declare their zero in their own help string, and this lever declares the opposite "
            f"('a candidate merge longer than this is refused'). MEASURED over a two-area sample, "
            f"against the shipped 16 (size 512, tok.build_mint 256, tok.build_refused 0, "
            f"bytes_per_token 3.5925925925925926): at 0 and at 1 alike, size 256, tok.build_mint 0, "
            f"tok.build_refused 143, bytes_per_token 1.0 -- the vocabulary permanently the 256 raw "
            f"bytes, which is a byte-level run reached by deleting the mint instead of by asking "
            f"for it, while TOK_MODE still reads 'online' and the ledger still prints two build "
            f"passes. TOK_MODE=bytes is the declared way to ask for that run. At 2 the mechanism is "
            f"back: size 399, tok.build_mint 143, bytes_per_token 2.0. Nothing an operator can ask "
            f"for is lost -- 2 is legal and is the smallest vocabulary this package has that mints "
            f"anything. This bounds nothing from above.")

    mode = str(tok.mode)
    vocab = Vocabulary(ceiling=int(tok.d_vocab_ceiling), soft_cap=soft_cap,
                       max_bytes=_max_bytes)

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
        # there is no requested-vs-historical pair to show; value stays None rather than a number that
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
            # unconditionally, at the TOP OF THIS BRANCH -- three statements up, immediately
            # under the "MINTED ON THIS BRANCH TOO" comment -- and the fresh-build arm mints the
            # very same name again at "tok.dropout.mint" once execution reached it -- spine/rng.py's
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
        # returns regardless of which arm produced it. `stream` reuses the dropout_rng minted AT THE
        # TOP OF THIS BRANCH, before `recon` and before the missing-parent refusal -- more than
        # forty lines up, not three, and this sentence said "three lines above" until it was
        # recounted (r4). THE DIGITS THAT RECOUNT RECORDED ARE GONE ON PURPOSE: it wrote "measured
        # 389 -> 432" and the tree it shipped in gave 389 -> 433, so the recorded pair did not match
        # the file it was recorded in -- a line number is exactly the thing that rots between a
        # recount and the commit that carries it. The ANCHORS do not rot and are what a reader can
        # check: the mint is the first statement of this branch, immediately under the "MINTED ON
        # THIS BRANCH TOO" comment, and this is its first use. Reusing
        # it is not a second mint -- see P1-H56 and the crash that a second mint caused on this exact
        # branch before that fix.
        stream = vocab.dropout_rng if float(tok.dropout) > 0 else None
        ids, _pos = _segment(vocab, sample, dropout=float(tok.dropout), stream=stream)
        vocab.bytes_per_token = _derive.bytes_per_token(len(sample), len(ids))
        # THE GATE, EVEN THOUGH NO BUILD PASS RAN HERE. build_passes_advice's predicate is about a
        # FRESH build reaching mode="fixed" at some REQUESTED pass count against the historical 8;
        # a replay never calls the build loop at all; on the offline analogue of the round1 fix that
        # left mode-out arms silent, staying silent here instead of naming the reason would be the
        # same collapse under a different cause. Reachable=False regardless of mode, because the
        # thing the gate reports on (a pass count) was never resolved on this branch.
        vocab.gates = (Gate("tok.build_passes_advice", False, None, 8, reachable=False,
                             reason="resumed via d_vocab_read_path: no build pass ran on this "
                                    "branch, so no pass count was resolved to compare"),)
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
    vocab.counters["tok.build_refused"] = 0
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
        refused = 0
        for (a, b), n in tally.most_common():
            if n < int(tok.min_pair) or vocab.size() >= target:
                break
            if vocab._add(vocab.id2bytes[a] + vocab.id2bytes[b], prov="build", pair=(a, b)) is not None:
                minted += 1
            else:
                # REFUSED, NOT ABSENT, AND THE TWO ARE COUNTED APART (r4 finding against this
                # block, which r3 wrote). `_add` returns None for len(seq) > max_bytes, for a
                # sequence already in seq2id, and at min(soft_cap, ceiling) -- and NONE of those
                # three is "the corpus ran out of pairs". Without this tally a pass that refused
                # every candidate above min_pair is indistinguishable from a pass that found none,
                # and tok.build_converged below then prints a cause it cannot establish.
                refused += 1
        vocab.counters["tok.build_mint"] += minted
        vocab.counters["tok.build_refused"] += refused
        if minted == 0:
            # CONVERGED MEANS THE CORPUS RAN OUT OF PAIRS, and it is NOT the size >= target break
            # above. Setting it there too would say a build that reached its target had nothing left
            # to mint, which is the opposite claim and the one that matters for reading v0: a run
            # that converged below target is exactly the case the old subtract-seed_vocab row
            # over-reported (self_organize.py:1274-1281).
            # NOR IS IT THE REFUSAL STALL, WHICH IS WHY `refused` GATES THIS ROW (r4 finding
            # against the row r3 added here). `minted == 0` cannot come from the target break --
            # size only moves when `_add` succeeds, and the outer loop already tested size >= target
            # before entering -- so it means either (a) the first candidate fell below min_pair, the
            # convergence this row claims, (b) every candidate above min_pair was REFUSED, or
            # (c) THE TALLY WAS EMPTY -- a build sample with no adjacent pair at all, so the inner
            # loop never ran a single comparison. (c) was missing from this enumeration until
            # 2026-09-04, when it was written as "exactly TWO reachable causes"; it is reachable at
            # TOK_BUILD_BYTES=1, measured: {tok.build_pass: 1, tok.build_mint: 0,
            # tok.build_converged: 1, tok.build_refused: 0} over a one-byte sample that segments to
            # one token and yields no pair. Setting the row THERE is defensible for a third reason
            # again -- a corpus with no adjacent pairs has none to run out of -- so this narrows
            # the enumeration and not the gate. Below it, at TOK_BUILD_BYTES=0, the row is not
            # reached at all: spine/derive.py::bytes_per_token raises on n_tokens=0 first. On (b)
            # the tally is still full and the corpus is not exhausted:
            # tok/levers.py::TOKLevers.max_bytes has the configuration on record ("max_tok=6
            # vmax=4000 -> stalled at 658/4000 with 1866
            # pairs still above min_pair (83.5% dead)", tokenizer.py:318-324), and at TOK_MAX_BYTES=6
            # with TOK_SEED_VOCAB=2000 this loop stalls at 464/2000 with nine pairs still at or above
            # min_pair, the top of them eight bytes long and refused for LENGTH ALONE. Writing 1 there
            # is a false equation printed under a counter, which is worse than printing nothing --
            # so the stall is reported by tok.build_refused instead, and the cause this row names is
            # left unclaimed rather than misclaimed. The BREAK is unchanged on both arms and is not a
            # narrowing of behaviour: nothing minted means the next pass re-segments identically,
            # tallies identically, and refuses or falls short identically.
            if refused == 0:
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
    # mode == "fixed"; the REQUESTED `passes` and the historical 8 travel as value/threshold so the
    # arithmetic is checkable rather than asserted, per Gate's own contract (spine/gate.py).
    # "REQUESTED" AND NOT "ACHIEVED", WHICH IS WHAT THIS LINE SAID UNTIL 2026-09-04. `passes` is
    # `int(tok.build_passes)` -- the loop's BUDGET -- and the loop breaks the moment a pass mints
    # nothing, so the two are different numbers on any corpus that converges early: measured at
    # TOK_MODE=fixed TOK_BUILD_PASSES=8 on a small build sample, the gate printed (8 vs 8) while
    # tok.build_pass was 3. The achieved count already has a surface of its own -- tok.build_pass,
    # seeded above -- and naming it here would have been a second, wrong source of truth for it.
    vocab.gates = (
        (Gate("tok.build_passes_advice", True, passes, 8,
              # THE REASON FOLLOWS THE VALUE IT IS PRINTED BESIDE (r5 finding, measured). One
              # sentence served both branches and at TOK_BUILD_PASSES=8 -- the ONE value it advises
              # -- it printed "FIRED (8 vs 8) -- ... set TOK_BUILD_PASSES=8 to reproduce it; a
              # mode="fixed" run at this value is not that build of record": the operator is told
              # to set what is already set, and told the run is not the build of record at the one
              # pass count that matches it. Both clauses false, on the same line as the arithmetic
              # that refutes them. The round that rewrote this paragraph rendered .line() on the
              # fixed arm at the default 2 only ("FIRED (2 vs 8)"), so this arm was never printed.
              # `fired` is UNCHANGED and stays arm-membership (mode == "fixed") -- the advisory row
              # is owed on this arm whatever the pass count is, which is what FIRED means here; it
              # is the REASON, and only the reason, that now branches.
              reason=("TOK_BUILD_PASSES=8: the pass BUDGET matches the offline build of record, "
                      "which also used 8. It is the REQUESTED count that matches and not the "
                      "achieved one -- the loop breaks as soon as a pass mints nothing, so how "
                      "many passes actually ran is tok.build_pass in the counters (3 of the 8 "
                      "requested, measured on a small build sample), and this line claims a "
                      "budget, not that the same work was done") if passes == 8 else
                     (f"the offline build historically used 8 and this run requests {passes} -- "
                      f"set TOK_BUILD_PASSES=8 to reproduce it; a mode=\"fixed\" run at {passes} "
                      f"requested passes is not that build of record"))
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
    (23 retoks, 22 adding zero tokens). The invariant stamped is (size, len(seq2id), len(retired))
    and NOT size alone, because retire() changes the match table without changing vocab_size. THE
    ANSWER IS ALSO KEYED ON `labels`, which is an argument of this function and not a property of
    the vocabulary at all -- see the body, and see Vocabulary.__init__ for the full list of what the
    cache entry covers and what it does not.

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

    `seed` IS ACCEPTED AND DELIBERATELY NOT READ, and the frozen signature keeps it (r4, found by
    reading this function end to end). The one live call site passes `seed=int(run.seed)`
    (spine/compose.py's tok_api.tokenize(..., regularize=True, seed=int(run.seed))), and a reader who
    assumes it seeds the regularizer would have the mechanism backwards: BPE-dropout draws from
    `vocab.dropout_rng`, the ONE stream build_vocabulary minted at "tok.dropout.mint" FROM RUN.seed,
    and it has to CONTINUE across calls (P1-H56, the paragraph on the stream below). Anything this
    call did with a per-call `seed` would be that restart. It is kept because a Vocabulary is not the
    only thing a future caller may want reproducible -- the held-out encode and generation callers
    P4 owes may need a stream of their own -- and dropping a parameter from a frozen surface is a
    signature change. Recorded here so the next reader does not file it as a dead argument or, worse,
    wire it into the draw.

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
    # len(seq2id), len(retired)), NOT size ALONE, because retire() pops a sequence from the match
    # table -- taking segmentation down a different path -- without moving vocab.size(); a stamp of
    # size alone would call a retire-only change a no-op and skip a rebuild the match table
    # actually needs.
    # THE THIRD TERM IS LATENT TODAY AND IS WRITTEN DOWN AS LATENT (r4 finding, and it is recorded
    # rather than inflated). _segment consults THREE structures -- `s2i.get(...)`, `if j is None or
    # j in retired: continue`, and `hi = min(mlbf[b0], n - i)`, which decides which lengths are
    # probed at that position at all -- so a stamp over seq2id alone is a stamp over PART of the
    # match table. THIS SENTENCE SAID TWO UNTIL 2026-09-04, in both of its copies, and it is the
    # paragraph offered as the exhaustive input list, so the undercount was in the one place
    # written to stop a fourth reader having to find the next one. mlbf IS COVERED, TRANSITIVELY
    # AND ONLY TRANSITIVELY: it is written at exactly one site, inside Vocabulary._add, which
    # appends to id2bytes before it touches mlbf and therefore always moves vocab.size() -- so the
    # first stamp term catches it and a fourth term would be inert today. The implication is stated
    # because it is what a reinstatement breaks: putting a sequence back into seq2id without going
    # through _add moves neither size() nor mlbf's writer, and that is the same shape as the
    # retire+reinstate pair the next paragraph says no count of the two sets can see.
    # It could not go stale while this sentence was first written -- `Vocabulary` had no retire()
    # method, nothing anywhere wrote `vocab.retired`, and judge_probation was `raise
    # NotImplementedError` -- so len(retired) was 0 on every reachable configuration. THAT IS NO
    # LONGER TRUE (2026-09-17): Vocabulary._retire and ._reinstate exist, judge_probation calls the
    # first and mint_burst the second, and the term now changes value on any run with
    # TOK_PROBATION_USES > 0. It closes ONE of the two shapes that defeat the pair: a retire that
    # adds to `retired` WITHOUT popping seq2id, which moves neither of the other two terms.
    # THE FOURTH TERM IS `vocab.rev` AND IT CLOSES THE SECOND SHAPE, WHICH THE PARAGRAPH BELOW
    # SAID WAS OPEN (2026-09-17, when mint_burst and judge_probation were written). Read the next
    # paragraph as the statement of the defect and this one as its repair: `rev` is a monotone
    # counter bumped by Vocabulary._add, ._retire and ._reinstate -- every writer of the match
    # table there is -- so the retire+reinstate pair that nets to zero in the other three terms
    # moves this one by two. It is the "monotone revision number bumped by every match-table
    # mutation" the paragraph asks for, and it exists now because the two bodies that mutate the
    # match table exist now: LOOP_ORDER puts TOK.mint_burst and TOK.judge_probation on the same
    # flush, with a Due.retok tokenize between them, so the pair was reachable the moment those
    # bodies landed rather than hypothetical. THE TERM CAN ONLY MAKE THE CACHE MORE CONSERVATIVE:
    # every mutation that moves one of the other three moves `rev` as well, so no call that
    # rebuilds today starts skipping, and the calls that start rebuilding are exactly the ones the
    # paragraph below says are being served a stale answer.
    # IT DOES NOT CLOSE THE SECOND SHAPE, AND SAYING SO IS THE POINT OF THIS PARAGRAPH. Under the
    # retirement this package already describes -- judge_probation's "the bytes are popped from the
    # match table", plus the addition to `retired` that Vocabulary.live_size's own subtraction
    # requires -- a retire of one id paired with a REINSTATEMENT of a different retired id in the
    # same flush
    # (mint_burst's docstring makes reinstatement a real operation: "put the old id back in the
    # match table, mint nothing") moves len(seq2id) by -1 then +1 AND len(retired) by +1 then -1,
    # both to a net zero, while the match table has genuinely changed. No count of the two sets can
    # see that; only a monotone revision number bumped by every match-table mutation can, and there
    # is nothing to bump it in yet. Recorded in this file rather than left for a fifth reader to
    # rediscover as a fresh defect against the same cache.
    stamp = (vocab.size(), len(vocab.seq2id), len(vocab.retired), vocab.rev)
    cache = vocab._retok_cache
    is_retok = cache is not None and cache[0] is data and cache[1] == start and cache[2] == len(data)
    if is_retok and drop <= 0.0 and cache[3] == stamp and not cache[5] and cache[6] is labels:
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
        # AND `cache[6] is labels`: THE SAME CACHE SERVED A STALE ANSWER IN A SECOND ARM, AND IT IS
        # NOT A DROPOUT ARM AT ALL (r4 finding, tok/api.py::tokenize). `labels` is an ARGUMENT of
        # this function and was in none of the six fields, so a later call on the same bytes object
        # with a DIFFERENT labels vector -- the None -> not-None direction included -- was handed the
        # earlier call's `out_labels` and counted as tok.retok_noop, a row whose whole meaning is
        # "the rebuild would have been byte-identical". It IS identical in `ids` and `byte_pos` and
        # is NOT in `labels`. Measured on the committed tree at the shipped TOK_DROPOUT=0.0, one
        # Vocabulary, three calls on the same bytes object: tokenize(...) then
        # tokenize(..., labels=[0]*n) then tokenize(..., labels=[7]*n) returned the SAME object all
        # three times with .labels None, under tok.retok_noop 2. This function's own docstring makes
        # that channel load-bearing -- "it takes the label of its FIRST byte ... so a per-area score
        # and a byte offset always agree" -- and the one live call site (spine/compose.py's
        # tok_api.tokenize(tok, sysm.vocab, sysm.stream.bytes, sysm.stream.labels, ...)) does pass
        # them, so a wrong hit substitutes the per-area channel DOM and EVAL read.
        # NOT REACHABLE IN TODAY'S PIPELINE, STATED SO THE LEDGER IS NOT OVER-READ, and the same
        # narrowing applies to the dropout half above: there is exactly ONE live tokenize call site
        # in the tree, so neither the mixed regularized/deterministic sequence nor the mixed-labels
        # sequence can arise in the run as it stands. Both are defects in a FROZEN PUBLIC SURFACE
        # whose docstring promises to serve the held-out encode and the final segmentation, and
        # those callers are P4's; neither was corrupting a run today.
        vocab.counters["tok.retok_noop"] = vocab.counters.get("tok.retok_noop", 0) + 1
        return cache[4]
    if is_retok and drop <= 0.0 and cache[3] == stamp and not cache[5]:
        # THE LABEL CHANNEL IS REBUILT; THE SEGMENTATION IS NOT (r5 finding, and it is the SECOND
        # half of the r4 repair rather than a retreat from it). Reaching here means every term of
        # the skip test above held EXCEPT `cache[6] is labels`: same bytes object, same start, same
        # length, same match-table stamp, no draw on either side -- and a DIFFERENT `labels`
        # argument. Under exactly those conditions _segment is a deterministic function of the
        # match table and the bytes, so the ids and the byte offsets it would produce are provably
        # the ones already in the cache, and the ONLY field that can differ is the per-token label
        # channel, which is derived from THIS call's argument through the cached byte_pos by the
        # same expression the fresh path uses forty lines below.
        # WHY IT IS WORTH A BRANCH. The r4 repair was correct and is untouched -- a call with a new
        # `labels` object must NOT be served the previous call's out_labels -- but it bought that
        # correctness by sending every such call down the full rebuild and counting it as
        # tok.retok, "activity". Measured on the committed tree at TOK_DROPOUT=0.0, two calls with
        # EQUAL BUT DISTINCT label lists over one bytes object: 'ids identical: True | byte_pos
        # identical: True | labels identical: True | same object: False' under {tok.segment: 2,
        # tok.retok: 1} -- a rebuild that was byte-identical in every field of the returned record,
        # reported as work performed. That defeats this function's own DID IT FIRE promise ("a
        # frozen run's 39 no-op re-tokenizations read as skipped rather than as activity") for any
        # caller that hands over a freshly built per-byte label list, which is what a fresh
        # DATA.draw_stream produces every epoch. The channel is rebuilt; nothing is re-measured.
        # tok.segment and tok.byte_fallback are NOT incremented here, for the same reason the skip
        # above does not increment them: no segmentation ran, and adding this text's byte fallbacks
        # to the row a second time would inflate a count of what the vocabulary did with the stream.
        prev = cache[4]
        out = None if labels is None else [labels[q] for q in prev.byte_pos]
        seg = Segmentation(ids=prev.ids, byte_pos=prev.byte_pos, labels=out,
                           bytes_per_token=prev.bytes_per_token)
        vocab.counters["tok.retok_noop"] = vocab.counters.get("tok.retok_noop", 0) + 1
        vocab._retok_cache = (data, start, len(data), stamp, seg, False, labels)
        return seg
    if is_retok:
        # A REAL RE-SEGMENTATION, AND THERE ARE THREE ROUTES INTO THIS BRANCH, NOT TWO. The comment
        # here named "the match table moved since the cached call (or dropout forced a fresh draw)"
        # until 2026-09-04, and under the r4 labels repair a THIRD route reached it -- a different
        # `labels` object -- on which the match table had not moved, dropout was 0.0, and the
        # rebuild was byte-identical in every field. That route now takes the label-channel branch
        # above and is counted as a no-op, so what is left here is exactly:
        #   (1) the match-table stamp moved, so the rebuild really can differ in ids and byte_pos;
        #   (2) THIS call draws (drop > 0.0), so a fresh BPE-dropout mask must be drawn and the
        #       answer is not a function of the vocabulary alone;
        #   (3) the CACHED answer came from a draw (cache[5]) and this call is deterministic, so
        #       the entry is usable as a stamp and unusable as an answer.
        # Counted as activity rather than folded into tok.segment, which is why the docstring
        # reports the two SEPARATELY -- a frozen run's no-op retoks must read as skipped, not as
        # work performed.
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
    vocab._retok_cache = (data, start, len(data), stamp, seg, drop > 0.0, labels)
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


def _cand_key(item):
    """The candidate ranking key: count DESCENDING, then pair ascending. A TOTAL order."""
    return (-item[1], item[0])


def _candidate_window(tally, k):
    """The `k` highest-count pairs of `tally`, in _cand_key order. A list of ((a, b), count).

    NOT Counter.most_common(k), and the difference is the one thing mint_burst's widening depends
    on. most_common resolves ties by the tally's own insertion order, so the deeper window it
    returns is not guaranteed to have the shallower one as a PREFIX -- and the widening examines a
    deeper window and carries on past the candidates it has already seen, which only means anything
    if those sit at the front. `(-count, pair)` is a total order on distinct pairs, so the prefix
    property holds by construction and two processes ranking the same tally rank it identically
    whatever order the pairs arrived in. build_vocabulary's own `tally.most_common()` is untouched:
    it materialises the WHOLE tally once per pass and never widens, so it has no prefix to preserve.
    """
    if k >= len(tally):
        return sorted(tally.items(), key=_cand_key)
    return heapq.nsmallest(k, tally.items(), key=_cand_key)


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
    ceiling = int(tok.d_vocab_ceiling)                   # WIRE READ HERE -- the hard row count

    # THE WIRE IS THE AUTHORITY AND THE VOCABULARY'S OWN CEILING IS CHECKED AGAINST IT, ONCE, HERE
    # (DEFECT D-T1). This module's header is unconditional: the ceiling is hard, it comes from the
    # wire on every path including a resume, and a saved file's vmax is a recorded fact to
    # reconcile against rather than an authority. Minting is the one act that can reserve an id the
    # model has no embedding row for, so this entry point is where that sentence has to bite.
    # THE CHECK IS LATENT ON TODAY'S TREE AND THAT IS SAID RATHER THAN IMPLIED: build_vocabulary is
    # the only writer of vocab.ceiling, it takes this same wire, and its one exception
    # (mode="fixed") only ever NARROWS -- so no environment an operator can set reaches this raise.
    # What trips it is the shape D-T1 names, a Vocabulary whose ceiling came from a file rather than
    # from the wire, which is how "a tokenizer saved full at 2048 came back full at 2048 and refused
    # every candidate for the whole run" happened on the first run that ever added an area.
    # IT IS A REFUSAL AND NOT A CLAMP, because a clamp would be a SECOND cap rule standing beside
    # Vocabulary.at_cap(), which that class calls THE ONE PREDICATE for exactly this reason.
    if int(vocab.ceiling) > ceiling:
        raise LeverError(
            f"TOK.mint_burst: this vocabulary's ceiling is {int(vocab.ceiling)} and the wire "
            f"d_vocab_ceiling -- LM.vocab_slots, the embedding row count -- is {ceiling}. Minting "
            f"against the wider of the two reserves ids the model has no row for. The wire is the "
            f"authority on every path including a resume (DEFECT D-T1), so this is refused rather "
            f"than clamped: clamping here would put a second copy of the cap rule beside "
            f"Vocabulary.at_cap().")

    # THE LEVERS, READ ONCE AND INTO BARE LOCALS, the idiom fabric/api.py::grow_check states: a
    # Config attribute inside the arithmetic below would put a lever read in an operand, and
    # `grow_burst` is TOKENS while `cand_window` and `min_pair` are COUNTS.
    burst = int(tok.grow_burst)
    floor_n = int(tok.min_pair)
    max_b = int(tok.max_bytes)
    # FLOORED AT 2, AND THE FLOOR CANNOT BE DECLARED ON THE LEVER. tok/levers.py::TOKLevers's
    # cand_window says so in as many words: `choices=` cannot express "at least 2", so the floor
    # lives at the point of use. At a window of 1 there is nothing to walk on to and one unmintable
    # top pair ends the burst -- the fault the lazy re-query exists to patch (tokenizer.py:325-329).
    width = max(2, int(tok.cand_window))
    pmin = float(tok.mint_pmin)
    novel = float(tok.mint_novel)
    # THE BIRTH STEP, TYPED THROUGH units.Windows AT THE DOOR (the idiom
    # fabric/api.py::forward uses on step_windows). Config hands back a bare int for every
    # clock-unit lever, so a kind is metadata at a READ site -- but this arrives as an ARGUMENT from
    # the root, and spine/units.py::Clock refuses to build a Windows out of a Steps. judge_probation
    # compares `step - birth` against probation_deadline, which is Windows; handed the optimizer's
    # step counter instead, every probation deadline would be wrong by the effective batch width and
    # right at batch_windows=1, which is the shape of every clock defect this project has recorded.
    born = int(_units.Windows(step))

    c = vocab.counters
    # PRESENT-AND-0 FROM THE FIRST CALL ON THE ARMS THAT CAN RUN, ABSENT ON THE ARMS THAT CANNOT.
    # This file's convention, stated by _replay_merges for tok.load_reconciled and by the build loop
    # for tok.build_pass: a key present-and-0 means the mechanism ran and did not fire, and an
    # ABSENT key means it was unreachable on the arm this vocabulary took. The gate rows are
    # therefore seeded only when there is a gate (mint_pmin > 0) and the novelty row only when
    # there is a re-rank (mint_novel > 0) -- at the shipped 0.0 defaults those four keys never
    # appear, which is what the docstring's "unreachable at mint_novel=0.0" asks for and what keeps
    # a reader from reading "0 blocked" off a gate that was never evaluated.
    for _row in ("tok.mint", "tok.mint_skipped", "tok.mint_reinstated", "tok.mint_rescued",
                 "tok.mint_widened", "tok.mint_ceiling_refused", "tok.mint_exhausted"):
        c.setdefault(_row, 0)
    if pmin > 0.0:
        for _row in ("tok.mint_gate_pass", "tok.mint_gate_block", "tok.mint_gate_forced"):
            c.setdefault(_row, 0)
    if novel > 0.0:
        c.setdefault("tok.mint_novel_reranked", 0)

    # THE REVERSE MAP FOR REINSTATEMENT, BUILT PER BURST AND NOT KEPT. `retire` pops the bytes out
    # of seq2id, so a retired token cannot be found by the lookup every other caller uses, and
    # ISSUES P1-M79 is what happens when the burst mints them again instead: two ids with identical
    # bytes, the statistics split between them, and a fresh embedding row for a token that already
    # had a trained one. Rebuilt on each call rather than carried on the Vocabulary because it is
    # derived state -- a second home for `retired` would be one more thing a resume has to
    # reconcile -- and because `retired` is small by construction (it is bounded by the tokens this
    # run minted) while a burst happens once every tok.grow_every windows.
    retired_bytes = {vocab.id2bytes[i]: i for i in vocab.retired}

    # p(b|a)'s DENOMINATOR, COMPUTED ONLY WHEN THERE IS A GATE TO FEED. The left marginal is the
    # tally's own: sum of counts over every pair starting with `a`. It is the same evidence the
    # numerator comes from, so the ratio is scale-free and needs no second instrument --
    # tok/levers.py::TOKLevers.mint_pmin argues that at length against an absolute
    # branching-entropy cutoff, which rejected 81% of left tokens over 400 kB of English and
    # rejected the USEFUL merges first. The scan is O(tally) and is skipped entirely at the shipped
    # mint_pmin=0.0, where nothing reads it.
    marginal = None
    if pmin > 0.0:
        marginal = collections.Counter()
        for (_a, _b), _n in vocab.tally.items():
            marginal[_a] += _n

    made = []
    taken = 0                    # burst budget spent: mints AND reinstatements, see _take
    skips = 0                    # candidates this burst refused for length or for already existing
    blocked = 0                  # candidates this burst's p(b|a) gate turned away
    exhausted = False
    at_ceiling = False

    def _drop(pair):
        """Take a pair out of the tally for good, with its `seen` entry."""
        vocab.tally.pop(pair, None)
        vocab.tally_seen.pop(pair, None)

    def _take(pair, cnt):
        """Turn one candidate into a match-table change, or say why not.

        Returns a Mint, or one of "reinstated" / "skipped" / "ceiling". THE ORDER OF THE TESTS IS
        LOAD-BEARING and the retired lookup comes BEFORE the seq2id one: TOK.restore_vocab puts
        `retired` back on a resume WITHOUT popping seq2id (it cannot -- the file is replayed by
        _replay_merges, which re-adds every entry), so after a resume a retired token's bytes are
        in BOTH tables. Asking seq2id first would call that candidate "already exists", skip it,
        and leave the token retired forever; asking `retired` first reinstates it, which is what it
        is.
        WHICH REFUSALS DROP THE PAIR FROM THE TALLY, AND WHY ONLY THOSE. A pair is dropped when it
        can never be a candidate again: minted (its bytes are one token now, so the pair stops
        occurring), reinstated (same), or longer than max_bytes (a length is a property of the pair
        and tok.max_bytes is frozen for the run, so it is too long for every later burst too).
        A pair refused AT THE CAP is NOT dropped -- CAP.lift_vocab_cap can raise the soft cap and
        make it mintable -- and neither is one whose bytes already exist at a LIVE id, because that
        id may itself be retired later, at which point this pair is a reinstatement. Leaving the
        permanently-dead ones in would clog the candidate window with entries that can never mint:
        the window is finite, and at cand_window=64 the window itself starved minting to 419 of
        1024 (tok/levers.py::TOKLevers.cand_window).
        """
        a, b = pair
        seq = vocab.id2bytes[a] + vocab.id2bytes[b]
        if vocab.at_cap():
            # THE ONE PREDICATE, not a second min(soft_cap, ceiling) written here. This is the row
            # that read "ZERO tokenizer.mint 0 ARMED AND INERT" on the first run that ever added an
            # area: the vocabulary was full, every candidate was refused, and nothing counted it.
            return "ceiling"
        if len(seq) > max_b:
            # THE LEVER DECIDES HERE, AND Vocabulary._add APPLIES THE VOCABULARY'S OWN COPY. The two
            # are one number with two homes: build_vocabulary constructs the Vocabulary with
            # max_bytes taken from this same lever, so they agree on every path this tree has. This
            # entry point reads the LEVER because that is what its contract declares (LEVERS READ:
            # ... max_bytes), and if the two copies ever disagree the raise below is where it
            # surfaces -- which is the right place for two copies of one number to be caught, and
            # is how this disagreement was found: a driving script that mutated `vocab.max_bytes`
            # alone got a candidate past this test and refused by _add.
            _drop(pair)
            return "skipped"
        old = retired_bytes.get(seq)
        if old is not None:
            vocab._reinstate(old)
            del retired_bytes[seq]
            _drop(pair)
            return "reinstated"
        if seq in vocab.seq2id:
            return "skipped"
        new_id = vocab._add(seq, prov=("online", born), pair=(a, b))
        if new_id is None:
            # _add REFUSES FOR EXACTLY THREE REASONS -- the cap, max_bytes, and already existing --
            # and all three were tested above. Reaching here means the tests and _add disagree
            # about the same table, which is a defect in this file and not a candidate to skip.
            raise ValueError(
                f"TOK.mint_burst: Vocabulary._add refused {seq!r} for pair {pair!r} after this "
                f"burst had cleared all three of the conditions _add refuses on: the cap "
                f"({vocab.size()} of {vocab._cap()}), the length ({len(seq)} against "
                f"TOK_MAX_BYTES={max_b} and vocab.max_bytes={vocab.max_bytes}) and the match table "
                f"({'present' if seq in vocab.seq2id else 'absent'} in seq2id). The two readings of "
                f"the same conditions disagree. If the two max_bytes differ, that is the cause: "
                f"they are one number with two homes and build_vocabulary is what keeps them "
                f"equal.")
        _drop(pair)
        return Mint(new_id=new_id, left_id=a, right_id=b, token_bytes=seq, count=cnt)

    # THE CANDIDATE WINDOW. `pool` stays in FREQUENCY order for the whole call and `order` is what
    # the walk below actually follows; at mint_novel=0 they are the same list. The two are held
    # SEPARATELY because of ISSUES P1-M77: the fail-open fallback claims to take "the most frequent
    # candidate clearing min_pair" and the shipped tree re-used the novelty-sorted list, so at
    # mint_novel > 0 it took the most NOVEL one instead -- the two re-rankers were designed to
    # compose and the fallback silently inherited one.
    width_now = width
    pool = _candidate_window(vocab.tally, width_now)
    order = pool
    if novel > 0.0:
        # THE NOVELTY RE-RANK (tok/levers.py::TOKLevers.mint_novel). most_common(1) mints the
        # globally most frequent pair, which by construction re-segments ALL existing material at
        # once; in a system whose point is continual learning a new area should buy vocabulary for
        # ITSELF rather than rewrite how everything already learned is spelled. `seen` is what the
        # pair's count was when a burst last considered it, so (c - seen) is growth SINCE then.
        order = sorted(pool, key=lambda kv: -((kv[1] - vocab.tally_seen.get(kv[0], 0))
                                              / (1.0 + vocab.tally_seen.get(kv[0], 0)) ** novel))
        c["tok.mint_novel_reranked"] += 1
    done = set()
    # A CURSOR, NOT A RESCAN FROM THE TOP EACH TIME. `done` only grows and `order` is a list, so
    # advancing an index past the entries already examined is O(window) for the whole walk where
    # re-scanning is O(window^2). That is not a micro-optimisation at the sizes this lever reaches:
    # a burst that skips every candidate -- TOK_MAX_BYTES small, which is a configuration
    # tok/levers.py::TOKLevers.max_bytes has on record as a real stall -- walks the whole window,
    # and the window widens by doubling, so at a tally of tens of thousands of pairs the rescan is
    # billions of comparisons inside one flush. The index resets to 0 whenever `order` is rebuilt,
    # and the skip loop below walks the done prefix again, which is O(window) once per widening.
    idx = 0

    while taken < burst:
        while idx < len(order) and order[idx][0] in done:
            idx += 1
        cand = order[idx] if idx < len(order) else None
        if cand is None:
            # THE WINDOW IS WALKED OUT. Widen and carry on -- the lazy re-query at
            # tokenizer.py:325-329 -- unless there is nothing deeper, or unless the window already
            # reaches BELOW the frequency floor, in which case everything deeper is below it too
            # and a deeper window is a sort nobody can use.
            if len(pool) >= len(vocab.tally) or (pool and pool[-1][1] < floor_n):
                exhausted = True
                break
            width_now = min(len(vocab.tally), width_now * 2)
            pool = _candidate_window(vocab.tally, width_now)
            order = pool
            if novel > 0.0:
                order = sorted(pool, key=lambda kv: -((kv[1] - vocab.tally_seen.get(kv[0], 0))
                                                      / (1.0 + vocab.tally_seen.get(kv[0], 0))
                                                      ** novel))
            c["tok.mint_widened"] += 1
            idx = 0
            continue
        pair, cnt = cand
        done.add(pair)
        if cnt < floor_n:
            # BELOW THE FREQUENCY FLOOR. In frequency order every later candidate is below it too,
            # so the pool is spent; AFTER A NOVELTY RE-SORT IT IS NOT, because the list is no longer
            # frequency-ordered and a later entry can be more frequent. The docstring names this
            # early exit and names the condition under which it must be disabled.
            if novel > 0.0:
                continue
            exhausted = True
            break
        if pmin > 0.0:
            # THE GATE MAY REORDER AND MAY NEVER PREVENT. As a HARD gate mint_pmin left 609 of 2048
            # rows (29.7%) never minted and scored 3.600 b/B against a ~1.96 baseline; here it
            # SKIPS a candidate and the fail-open below guarantees the burst can still mint. The
            # marginal is the tally's own, so `left` is at least `cnt` by construction -- a
            # KeyError here would mean the marginal and the window were built from different
            # tallies, which is a defect and not a candidate to skip.
            left = marginal[pair[0]]
            if cnt / left < pmin:
                c["tok.mint_gate_block"] += 1
                blocked += 1
                continue
            c["tok.mint_gate_pass"] += 1
        got = _take(pair, cnt)
        if got == "ceiling":
            c["tok.mint_ceiling_refused"] += 1
            at_ceiling = True
            break
        if got == "skipped":
            # SKIPPED, NOT "NOTHING LEFT TO MINT". A candidate refused for max_bytes or for already
            # existing used to abort the whole burst, and that hole stalled a vocabulary at 658/4000
            # with 1866 pairs still above min_pair (tokenizer.py:318-324).
            c["tok.mint_skipped"] += 1
            skips += 1
            continue
        if got == "reinstated":
            # A REINSTATEMENT SPENDS BUDGET AND MINTS NOTHING. It changes the spelling of the stream
            # exactly as a mint does, and grow_burst is the bound on how much the spelling may move
            # at one grow event (tok/levers.py::TOKLevers.grow_burst: grow_every x grow_burst is the
            # mint budget the modalities claim is priced in). The alternative -- reinstatements are
            # free -- lets one burst put every retired token back at once, which is the retire/
            # reinstate churn probation exists to make a measured decision rather than a loop.
            c["tok.mint_reinstated"] += 1
            taken += 1
            continue
        made.append(got)
        c["tok.mint"] += 1
        taken += 1
        if skips:
            # THE MINTS THE OLD "A REFUSAL ENDS THE BURST" BEHAVIOUR WOULD HAVE LOST: a mint taken
            # in a burst that had already skipped at least one candidate. It is the direct
            # measurement of the 658/4000 repair rather than an argument that the repair is in.
            c["tok.mint_rescued"] += 1

    if pmin > 0.0 and blocked and taken == 0 and not at_ceiling:
        # THE FAIL-OPEN, SCANNED IN FREQUENCY ORDER OFF `pool` AND NOT OFF `order` (ISSUES P1-M77).
        # A quality criterion that can empty the softmax is not a quality criterion: if the gate
        # turned everything away, the burst still takes the most frequent candidate clearing
        # min_pair. ONE, not a burst's worth -- the docstring says "the most frequent candidate",
        # singular, and a gate that can be overridden wholesale is not reordering anything.
        for _pair, _cnt in pool:
            if _cnt < floor_n:
                break
            if _pair not in vocab.tally:
                # ALREADY DROPPED BY THE WALK ABOVE, so it is permanently unmintable and was
                # already counted. `pool` is a snapshot taken before the walk ran; re-refusing an
                # entry it still lists would count one candidate's refusal twice.
                continue
            got = _take(_pair, _cnt)
            if got == "ceiling":
                if _pair not in done:
                    c["tok.mint_ceiling_refused"] += 1
                at_ceiling = True
                break
            if got == "skipped":
                # COUNTED ONLY IF THE WALK HAD NOT ALREADY REFUSED IT. This fallback exists to
                # reconsider the GATE's verdict, not to refuse a second time what the walk refused
                # for length or for already existing.
                if _pair not in done:
                    c["tok.mint_skipped"] += 1
                    skips += 1
                done.add(_pair)
                continue
            if got == "reinstated":
                c["tok.mint_reinstated"] += 1
                c["tok.mint_gate_forced"] += 1
                taken += 1
                break
            made.append(got)
            c["tok.mint"] += 1
            c["tok.mint_gate_forced"] += 1
            taken += 1
            break

    if novel > 0.0:
        # `seen` IS RECORDED FOR THE WHOLE MATERIALISED WINDOW, NOT FOR THE HANDFUL THE BUDGET
        # REACHED, and this is the difference between a live re-rank and an inert one. "How much a
        # pair has grown since it was last considered" (tok/levers.py::TOKLevers.mint_novel) makes a
        # pair CONSIDERED when it was ranked against the others, which is every entry in the window:
        # at cand_window=1024 and grow_burst=6 the walk below examines about six, so recording only
        # those leaves 1018 windowed pairs at seen=0 forever, where (c - 0)/(1 + 0)**novel is c --
        # plain most-frequent minting wearing the novelty knob's name. MEASURED on the sweep that
        # found it: with the per-candidate write, a burst that minted its whole budget left
        # tally_seen EMPTY, because every pair it touched was dropped from the tally by the mint.
        # THE MEMORY IS BOUNDED BY DISTINCT PAIRS EVER WINDOWED, not by candidates ever scored --
        # one int per pair, replaced in place -- which is the bound ISSUES P1-L68 asks for against
        # h_pmin_seen's one float per candidate for the whole run (millions at cand_window=1024).
        # The final `pool` is the whole window this call materialised: a widening only ever extends
        # it, and _candidate_window's total order makes the shallower window its prefix.
        for _pair, _cnt in pool:
            if _pair in vocab.tally:
                vocab.tally_seen[_pair] = _cnt

    if exhausted:
        # THE POOL RAN OUT WITH BUDGET LEFT. It is counted once per burst rather than once per
        # candidate, and it is NOT the cap refusal above: "the corpus has no pair left worth
        # minting" and "the vocabulary is full" are different facts about a burst that minted
        # nothing, and build_vocabulary's tok.build_converged carries the same distinction for the
        # seed build.
        # AN EMPTY TALLY REACHES HERE TOO, AND IT IS THE STATE THIS TREE IS ACTUALLY IN.
        # TOK.on_window is the only declared producer of vocab.tally and it is still a P4 stub that
        # spine/loop.py does not call, so on the tree as it stands every burst finds an empty pool
        # and reads tok.mint 0 with tok.mint_exhausted 1 -- a measurement of an empty pool, which is
        # a different statement from a mechanism that was never reached, and the reader can tell
        # which they are looking at by whether vocab.tally has anything in it.
        c["tok.mint_exhausted"] += 1
    return made


def _prov_online(entry):
    """(born, verdict) for a token minted during the run, or None for one that never was.

    THE TWO SHAPES ARE Vocabulary.prov'S, WHICH THAT FIELD'S COMMENT STATES IN FULL: a bare string
    for the build and the replay, ("online", born) for a token TOK.mint_burst minted and nothing has
    judged, ("online", born, verdict) once TOK.judge_probation has.
    A LIST IS ACCEPTED AS WELL AS A TUPLE, and that is not laxity. TOK.vocab_state hands this table
    to CKPT.save as part of an opaque payload; torch.save round-trips a tuple as a tuple, and any
    JSON leg -- today's tokenizer sidecar is JSON, and a future payload writer may be -- hands back
    a LIST. Reading only tuples would make a resumed run see no token on probation at all and
    report a clean sweep, which is DEFECT D-T3's shape (a round trip silently confirming every
    token that was on probation) reintroduced by a type check.
    ANYTHING ELSE RAISES. An unrecognised entry treated as "not on probation" is the silent no-op
    this package refuses everywhere else: it would make this function report a verdict over a table
    it could not read.
    """
    if isinstance(entry, str):
        return None
    if isinstance(entry, (tuple, list)) and len(entry) in (2, 3) and entry[0] == "online":
        return int(entry[1]), (None if len(entry) == 2 else str(entry[2]))
    raise ValueError(
        f"TOK.judge_probation: Vocabulary.prov carries {entry!r}, which is neither a provenance "
        f"string nor an (\"online\", born[, verdict]) record. Refused rather than read as \"not on "
        f"probation\": that reading would report a clean sweep over a table this function cannot "
        f"read, which is how a save/load round trip came to confirm every token on probation "
        f"(DEFECT D-T3).")


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
    # THE LEVERS, READ ONCE AND INTO BARE LOCALS -- and the deadline is TYPED HERE, at the read,
    # rather than compared as an int below. Its census row is the reason: the old name said
    # TOK_PROBATION_STEPS and the quantity is WINDOWS, so at BATCH_W=16 reading it as steps is a
    # 16x error, and tok/levers.py::TOKLevers.probation_deadline says the unit type is how the
    # comparison stops compiling if anyone reads it as steps again. `step` goes through
    # units.Windows at the same door for the same reason.
    uses = int(tok.probation_uses)
    deadline = _units.Windows(int(tok.probation_deadline))
    by = str(tok.probation_by)
    resid_min = float(tok.probation_residual)
    now = _units.Windows(step)
    c = vocab.counters

    def _seal(gate):
        """Put one gate on the vocabulary, replacing any earlier gate of the SAME NAME.

        NEITHER OF THE TWO OBVIOUS SPELLINGS IS RIGHT HERE. Assigning the whole tuple is
        build_vocabulary's discipline -- it declares its entire surface at each of its three return
        points -- and doing it here would DELETE tok.build_passes_advice, which describes the build
        and is the only gate this package has. Appending would grow one tuple by an entry per flush
        for the length of the run, which is exactly why fabric/api.py::forward keeps its per-pass
        gates on the returned record instead of on the population. Replacing by name is bounded by
        the number of distinct gate names -- two -- and leaves the last reading of each in place,
        which is what a report renders.
        """
        vocab.gates = tuple(g for g in vocab.gates if g.name != gate.name) + (gate,)

    # THE OFF ARM, AND IT LEAVES THE FOUR COUNTERS ABSENT. The docstring's own row says all four are
    # "unreachable at probation_uses = 0, the default", and this file's convention is that an
    # unreachable mechanism leaves its key ABSENT while an armed one that did not fire prints 0.
    # Nothing is on probation at 0 -- tok/levers.py::TOKLevers says "THE DEFAULT 0 MEANS OFF" of
    # this lever, and a threshold of zero appearances is earned by every token the instant it is
    # minted -- so `pending` is 0 and not the count of online tokens: a token nothing will ever
    # judge is not waiting for a judgement.
    if uses <= 0:
        _seal(Gate("tok.probation_embed", False, value=f"probation_by={by!r}",
                   threshold=resid_min, reachable=False,
                   reason="TOK_PROBATION_USES=0: probation is off, so neither the use test nor the "
                          "embed test runs and the four probation counters are absent rather than "
                          "0. Every token minted this run keeps its slot by default."))
        return Judgement(kept=(), retired_ids=tuple(sorted(int(i) for i in vocab.retired)),
                         pending=0, live_size=vocab.live_size(), id_count=vocab.size())

    # WHO IS ON PROBATION: every token minted during the run that nothing has judged yet. Read off
    # `prov`, which is the one table that survives a checkpoint with its birth steps (DEFECT D-T3),
    # and materialised into a list first because the loop below writes back into `prov`.
    waiting = []
    for tid, entry in list(vocab.prov.items()):
        got = _prov_online(entry)
        if got is None or got[1] is not None:
            continue
        waiting.append((int(tid), got[0]))

    embed = (by == "embed")
    if embed and residual_ratio is None:
        # THE EMBED ARM IS UNREACHABLE AND SAYS SO, WHICH IS ISSUES P1-M41's REPAIR. At
        # TOK_PROBATION_BY=embed with TOK_COMPOSE=0 the old tree left the residual at None and FELL
        # THROUGH to the "use" test with no warning anywhere, while the banner printed the requested
        # mode and the end-of-run vocabulary line reported "judged by embed" -- a wrong-measurement
        # record, which is the largest defect class in the survey.
        # NOTHING IS JUDGED ON THIS ARM AND NOTHING IS RETIRED. The alternative -- raise -- was
        # considered and refused: lm.compose=False is a legal configuration, LM.residual_ratios
        # returns None on it by contract, and the root calls this row unconditionally on
        # Due.probation, so raising would turn a legal run into a crash at the first probation
        # cadence. The tokens stay pending, the counters stay ABSENT (the test could not run, so 0
        # judged would be a false reading of a mechanism that was never evaluated), and the Gate
        # carries the arithmetic.
        _seal(Gate("tok.probation_embed", False,
                   value=f"{len(waiting)} token(s) on probation, none judged",
                   threshold=resid_min, reachable=False,
                   reason="unreachable (no residual_ratio supplied): TOK_PROBATION_BY=embed needs "
                          "LM.residual_ratios, which returns None at lm.compose=False. The 'use' "
                          "test is NOT run in its place -- that silent fall-through is ISSUES "
                          "P1-M41, where the banner reported 'judged by embed' on a run that had "
                          "judged by use."))
        return Judgement(kept=(), retired_ids=tuple(sorted(int(i) for i in vocab.retired)),
                         pending=len(waiting), live_size=vocab.live_size(), id_count=vocab.size())

    # THE SHARED COUNTER IS INDEXED BY ID AND THE TWO MUST AGREE ABOUT HOW MANY ROWS EXIST. A short
    # `appearances` is not a small problem to work around: it means the loop's per-token counter and
    # this vocabulary were sized from different numbers, so every id past its end would be judged on
    # somebody else's count or on an exception at a random index.
    if appearances is None:
        raise ValueError(
            "TOK.judge_probation: appearances is None. It is System.token_seen, the ONE shared "
            "per-token counter, and probation is judged on it -- judging without it would retire "
            "tokens on a count nobody took.")
    n_rows = len(appearances)
    for _tid, _born in waiting:
        if _tid >= n_rows:
            raise ValueError(
                f"TOK.judge_probation: token {_tid} is on probation and the appearance counter has "
                f"{n_rows} rows. The counter and the vocabulary were sized from different numbers; "
                f"judging past the end would read another token's count or raise at an index this "
                f"function chose.")
        if embed and _tid >= len(residual_ratio):
            raise ValueError(
                f"TOK.judge_probation: token {_tid} is on probation and residual_ratio has "
                f"{len(residual_ratio)} rows. LM.residual_ratios is read off the live composer, so "
                f"a short vector means the model and the vocabulary disagree about how many tokens "
                f"exist.")

    for _row in ("tok.probation_judged", "tok.probation_kept", "tok.probation_retired"):
        c.setdefault(_row, 0)

    # `judged` IS THIS CALL'S AND tok.probation_judged IS THE RUN'S. The Gate below prints the
    # per-call number beside `embed_used`, which is also per-call: pairing a cumulative counter with
    # a per-call one on one line is an arithmetic a reader cannot check, and it reads correct for
    # exactly as long as there has only ever been one call.
    kept, pending, embed_used, judged = [], 0, 0, 0
    for tid, tborn in waiting:
        seen_n = int(appearances[tid])
        earned = seen_n >= uses
        # THE DEADLINE IS THE TEST. Judging only on reaching the threshold can never retire
        # anything: a token that has not earned its appearances yet may still earn them tomorrow,
        # so without a by-when there is no moment at which the answer is no.
        overdue = (now - _units.Windows(tborn)) >= deadline
        if not (earned or overdue):
            pending += 1
            continue
        keep = earned
        if embed:
            # THE TWO TESTS COMPOSE, DELIBERATELY, AND DROPPING EITHER TURNS A TWO-SIDED JUDGEMENT
            # INTO A ONE-SIDED ONE: a residual near zero because the token was never seen says
            # nothing about the merge, so the embed arm requires BOTH that the token was used and
            # that its learned residual moved away from what its bytes already say.
            keep = earned and float(residual_ratio[tid]) >= resid_min
            embed_used += 1
        c["tok.probation_judged"] += 1
        judged += 1
        if keep:
            vocab.prov[tid] = ("online", tborn, "kept")
            kept.append(tid)
            c["tok.probation_kept"] += 1
        else:
            # RETIREMENT IS SOFT AND THE VERDICT IS WRITTEN BESIDE THE BIRTH STEP. Vocabulary._retire
            # pops the bytes out of the match table and leaves the id and its embedding row; the
            # verdict goes into `prov` so a second judgement pass does not re-judge a token whose
            # probation is over, and so TOK.vocab_state -- which carries `retired` and `prov` and
            # nothing else about probation -- survives the round trip that used to undo every
            # retirement (DEFECT D-T3).
            vocab._retire(tid)
            vocab.prov[tid] = ("online", tborn, "retired")
            c["tok.probation_retired"] += 1

    # A LEVEL, NOT A TOTAL, AND IT IS THE ONE ROW HERE THAT IS ASSIGNED RATHER THAN ADDED TO.
    # tok.probation_pending is how many tokens are waiting for a verdict AS OF THIS CALL; summing it
    # over calls would count the same waiting token once per probation cadence. build_vocabulary's
    # tok.build_converged is assigned for the same reason -- it is a state, not a tally.
    c["tok.probation_pending"] = pending
    _seal(Gate("tok.probation_embed", embed,
               value=(f"{embed_used} of {judged} judged on ||delta||/||composite|| this call"
                      if embed else
                      f"{judged} judged on appearances against {uses} this call"),
               threshold=resid_min, reachable=embed,
               reason="" if embed else
                      f"TOK_PROBATION_BY={by!r}: the residual test is not this run's test, so its "
                      f"threshold is printed beside a verdict it did not decide. The use test ran "
                      f"and its numbers are tok.probation_judged / _kept / _retired."))
    return Judgement(kept=tuple(kept),
                     # THE WHOLE SET, NOT THIS CALL'S RETIREMENTS -- see Judgement's own docstring.
                     # LM.decode takes this as the refresh of what it must mask, and a mask built
                     # from one flush's verdicts alone re-admits every row retired before it.
                     retired_ids=tuple(sorted(int(i) for i in vocab.retired)),
                     pending=pending, live_size=vocab.live_size(), id_count=vocab.size())


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
    base = str(tok.d_vocab_save_path or "").strip()      # WIRE READ HERE -- this run's own file
    if not base:
        # SAVING IS OFF. Returns None rather than raising: an operator who did not ask for a
        # tokenizer file is not making a mistake.
        return None
    # THE SUFFIX IS SPLICED IMMEDIATELY BEFORE THE ".dyntok.json" TAIL, AND THE GENERIC FORMS ARE
    # REFUSED BY NAME IN THE DOCSTRING ABOVE. The tail has TWO dots, so os.path.splitext -- the
    # obvious spelling, and the one written here first -- yields <base>.dyntok.best3.json while the
    # read side looks for <base>.best3.dyntok.json, and the two never meet. Splicing before the LAST
    # dot fails the same way. d_vocab_read_path is CKPT.resume + ".dyntok.json" and CKPT.resume
    # names the snapshot being resumed FROM, suffix included, so with this splice the two sides meet
    # exactly and the read side needs no edit at all.
    # THE TAIL IS NAMED IN THREE PLACES AND THEY MOVE TOGETHER: the two couplings in
    # spine/assemble.py, once per direction, and this splice.
    tail = ".dyntok.json"
    dst = (base[:-len(tail)] + (suffix or "") + tail) if base.endswith(tail) else base + (suffix or "")
    # NEVER WRITES TO d_vocab_read_path: THAT FILE IS THE PARENT'S. A resume that overwrote the file
    # it is reading from would destroy the only record of what the parent actually used, mid-run,
    # and the corruption would surface as a vocabulary mismatch on the NEXT resume.
    read_path = str(tok.d_vocab_read_path or "").strip()
    if read_path and os.path.abspath(dst) == os.path.abspath(read_path):
        raise LeverError(
            f"TOK.save_vocabulary would write {dst!r}, which is d_vocab_read_path -- the file this "
            f"run is RESUMING FROM. That file is the parent's record of what it actually used, and "
            f"overwriting it mid-run destroys the only thing a later resume could check against.")
    d = os.path.dirname(dst)
    if d:
        os.makedirs(d, exist_ok=True)
    blob = {
        # THE MERGES, WHICH ARE THE FILE'S REASON TO EXIST. build_vocabulary REPLAYS them on a
        # resume, which is why TOK.vocab_state carries "everything a resume needs THAT THE MERGE
        # LIST ALONE DOES NOT CARRY" and explicitly not these.
        "merges": [list(m) for m in vocab.merges],
        # PLUS THE SETTINGS THIS RUN ACTUALLY USED, beside the snapshot that names them. What was
        # USED rather than what was ASKED FOR is the difference between a file a later run can check
        # against and one that merely agrees with the environment it was written in.
        "v0": int(vocab.v0),
        "maxlen": int(vocab.maxlen),
        "max_bytes": int(vocab.max_bytes),
        "ceiling": int(vocab.ceiling),
        "bytes_per_token": float(vocab.bytes_per_token),
    }
    tmp = dst + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(blob, fh)
    os.replace(tmp, dst)
    vocab.counters["tok.vocab_saved"] = vocab.counters.get("tok.vocab_saved", 0) + 1
    return dst


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
    lift_period = tok.d_cap_lift_period      # WIRE READ HERE -- reported beside tok.cap_lift
    out = {
        # THE RETIREMENTS AND THE PROVENANCE TABLE, WHICH IS DEFECT D-T3. A save/load round trip
        # UNDID EVERY RETIREMENT, because load() replays every merge into the match table including
        # the retired ones, and `prov` did not exist in the file at all -- so every token on
        # probation at save time was silently CONFIRMED by the act of checkpointing. The merge list
        # alone cannot carry either: it says what was built, not what was withdrawn or when.
        "retired": sorted(int(i) for i in vocab.retired),
        "prov": {str(k): v for k, v in vocab.prov.items()},
        "v0": int(vocab.v0),
        "soft_cap": None if vocab.soft_cap is None else int(vocab.soft_cap),
        "merge_count": len(vocab.merges),
        # THE PAIR TALLY DIGEST rather than the tally: it is the candidate evidence a mint draws on,
        # and carrying the counts lets a resumed run continue accumulating instead of restarting the
        # window that was already paid for.
        "pair_digest": len(getattr(vocab, "pair", ()) or ()),
        "counters": dict(vocab.counters),
        # THE CAP-LIFT CADENCE, REPORTED AS A READING. "0 lifts" and "the valve's period is longer
        # than the run" are different facts, and round6 measured 0 vocabulary lifts on gc_real when
        # it was a CLOCK-UNIT fault rather than the plateau condition. This line prints the period
        # and points at the package that owns the verdict; it must not grow a second verdict of its
        # own -- CAP.counters' block-reason histogram is the authority, and it now has a body.
        "cap_lift_period": int(lift_period),
    }
    # THE CADENCE `_fired` MAP IS DECLARED ABSENT RATHER THAN OMITTED. TOK.on_window owns this
    # package's four cadences and is still a P4 stub, so no `_fired` map exists to save. Writing the
    # reason beats leaving the key out, because a missing key on the other side is indistinguishable
    # from an older checkpoint -- and a resume that silently finds no cadence state restarts every
    # one of them at zero.
    out["fired"] = None
    out["fired_unbuilt_reason"] = ("TOK.on_window is a P4 stub, so this package's four cadences "
                                   "have no _fired map yet; there is no cadence state to carry")
    vocab.counters["tok.state_written"] = vocab.counters.get("tok.state_written", 0) + 1
    return out


def restore_vocab(tok: Config, state, vocab):
    """Put retirements, probation and the cadence clocks back, and REFUSE LOUDLY if the state's
    merge count does not match the vocabulary just built from the file.

    LEVERS READ: none
    WIRES READ: none
    DID IT FIRE: tok.state_restored, tok.state_refused
    """
    tok = tok.owned_by("TOK")
    if not state:
        return vocab
    # THE MERGE COUNT IS CHECKED FIRST AND THE REFUSAL IS LOUD. This state describes a vocabulary
    # built from a FILE, and the file is loaded separately: if the two disagree, every id in
    # `retired` and every key in `prov` points at a different token than the one it was recorded
    # against, and the restore would retire tokens at random rather than fail.
    was, now = int(state.get("merge_count", -1)), len(vocab.merges)
    if was >= 0 and was != now:
        vocab.counters["tok.state_refused"] = vocab.counters.get("tok.state_refused", 0) + 1
        raise LeverError(
            f"TOK resume refused: the checkpoint records {was} merges and the vocabulary just "
            f"built from the file has {now}. Every id in the retirement set and the provenance "
            f"table is an index into that merge list, so restoring across a mismatch would retire "
            f"and confirm tokens at random instead of failing. The tokenizer file and the "
            f"checkpoint are from different runs.")
    # RETIREMENTS GO BACK, WHICH IS THE HALF load() UNDOES. It replays every merge into the match
    # table including the retired ones, so without this line a resume silently re-admits them.
    vocab.retired = set(int(i) for i in (state.get("retired") or ()))
    if state.get("prov"):
        vocab.prov = {int(k): v for k, v in state["prov"].items()}
    if state.get("v0") is not None:
        vocab.v0 = int(state["v0"])
    if "soft_cap" in state:
        vocab.soft_cap = None if state["soft_cap"] is None else int(state["soft_cap"])
    if state.get("counters"):
        vocab.counters.update(state["counters"])
    vocab.counters["tok.state_restored"] = vocab.counters.get("tok.state_restored", 0) + 1
    return vocab
