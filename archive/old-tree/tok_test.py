#!/usr/bin/env python3
"""Does the tokenizer mint the vocabulary it was told to mint?

NOTHING IN THE SUITE TOUCHED DynamicTokenizer. selftest.sh runs a real train with GROW_EVERY=20,
GROW_BURST=8, RETOK_EVERY=200, VMAX=320, so the mint and retok paths EXECUTE on every run -- and nothing
asserted a single thing about what they decide. That matters here more than almost anywhere else: vocabulary
SIZE is the largest measured effect on quality this project has found (round12, one knob apart: 2.021 frozen
at 2048 against 2.162 grown to 3784), and an unminted row is a dead row in the softmax.

THE BUG THIS FILE WAS WRITTEN FOR. maybe_grow returns None for two completely different situations:
"there is nothing left above min_pair" and "the candidate I picked cannot be minted". Every caller reads None
as the first. The file's own comment forbids exactly this -- "the gate may REORDER what gets minted and may
never PREVENT minting", written directly above a `return None` that prevented minting -- and the candidate had
already been zeroed out of the tally on the line before, so it was discarded AND the burst stopped.

Reproduced on real English before the fix, and asserted below:

    max_tok=16 vmax=2048  ->  stalled at 1845/2048   9.9% of the width never minted, 3940 candidates left
    max_tok=6  vmax=4000  ->  stalled at  658/4000  83.5% of the width never minted, 1866 candidates left

The second cause is subtler and is why the first fix did not work: with novelty and the predictability gate
both off, `_k` is 1, so the candidate window is a SINGLE pair. "Walk on to the next candidate" had nothing to
walk. The window is now widened lazily -- only when the cheap answer was unusable.

tokenizer.py imports only the standard library, so this runs without torch and without a corpus: the fixtures
below are synthetic and deterministic.

Run: python3 tok_test.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tokenizer import DynamicTokenizer          # noqa: E402  (stdlib-only; no torch)

FAILED = []


def check(cond, msg):
    if not cond: FAILED.append(msg); print(f"  FAIL  {msg}")
    else: print(f"  ok    {msg}")


def fill(t, text, rounds=400):
    """Tally, then mint until the cap is reached or minting genuinely stops. Returns (vocab, candidates_left)."""
    for i in range(0, len(text), 8192): t.segment(text[i:i + 8192], count=True)
    for n in range(rounds * 40):
        if t.vocab_size >= t.vmax: break
        before = t.vocab_size
        if t.maybe_grow() is None and t.vocab_size == before: break
        if n % 200 == 0:
            for i in range(0, len(text), 8192): t.segment(text[i:i + 8192], count=True)
    return t.vocab_size, sum(1 for _p, c in t.pair.items() if c >= t.min_pair)


# A corpus with enough distinct structure to keep producing candidates. Deterministic, no data/ dependency.
WORDS = [b"the", b"and", b"ing", b"tion", b"for", b"with", b"that", b"this", b"from", b"have",
         b"data", b"model", b"system", b"result", b"value", b"number", b"process", b"pattern"]
CORPUS = b" ".join(WORDS[(i * 7 + i // 13) % len(WORDS)] + (b"." if i % 11 == 0 else b"")
                   for i in range(30000))

print(f"tok_test: synthetic corpus {len(CORPUS)} bytes, {len(set(CORPUS.split()))} distinct words\n")

# --- 1. A REJECTED CANDIDATE IS NOT AN EXHAUSTED VOCABULARY ----------------------------------------------------
print("MINTING REACHES THE CAP -- a candidate it cannot mint must not end the burst")
for max_tok, vmax in ((16, 1024), (6, 1024), (4, 800)):
    t = DynamicTokenizer(vmax=vmax, min_pair=20, max_tok=max_tok)
    got, left = fill(t, CORPUS)
    dead = 100.0 * (vmax - got) / vmax
    print(f"  max_tok={max_tok:<3d} vmax={vmax:<5d} -> {got}/{vmax}  ({dead:.1f}% dead, "
          f"{left} candidates still above min_pair, {t.gate_skipped} skipped)")
    # The bug's signature: stopped short WHILE candidates remained. That is the assertion, not "reached vmax" --
    # a corpus can genuinely run out of pairs, and calling that a failure would be a different wrong test.
    check(not (got < vmax and left > 0),
          f"max_tok={max_tok}: did not stop short with {left} candidates still available")

print("\n  ...and max_tok=2 is the sharp case: only byte+byte merges fit, so every merge of a merged token")
print("     is rejected -- the exact situation that used to end the burst on its first occurrence.")
t = DynamicTokenizer(vmax=1024, min_pair=20, max_tok=2)
got, left = fill(t, CORPUS)
print(f"  max_tok=2   vmax=1024 -> {got}/1024, {t.gate_skipped} candidates skipped as unmintable")
# max_tok=3 was the first fixture here and it skipped NOTHING -- this corpus runs out of pairs before it
# produces a 4-byte merge, so the counter stayed 0 and the assertion failed on the fixture rather than on the
# code. Asserting that a counter increments requires a case that actually increments it.
check(t.gate_skipped > 0, "the skip counter records them, so an all-rejects window is visible in the report")
check(not (got < 1024 and left > 0), "and it still does not stop while candidates remain")

# THE REPAIR HAS TO BE COUNTABLE, not merely effective. gate_skipped says candidates were refused; it does not
# say the WALK is what kept minting alive, because a reject behind a mintable leader costs nothing. mint_rescued
# counts only the calls whose FIRST candidate was refused -- exactly the calls the pre-fix code answered None to.
# Without it a log cannot tell "the hole was never in the path" from "the fix saved the vocabulary": both print
# the same "vocab N/M", which is all round18's fix_vocab arm was able to report.
print(f"  mint_rescued {t.mint_rescued} (mints the pre-fix code would have refused) | "
      f"mint_widened {t.mint_widened} (times the candidate window emptied and the re-query ran)")
check(t.mint_rescued > 0, "mint_rescued counts them, so the fix's own firing is visible in DID IT FIRE")
check(t.mint_rescued <= t.gate_skipped,
      "and it cannot exceed the rejects -- a rescue requires at least one refused candidate")
# The clean control: max_tok=16 on this corpus rejects nothing, so the repair must report itself as NOT ENTERED
# rather than as inert. A row that reads "ARMED AND INERT" on every healthy run is a row nobody reads.
tc = DynamicTokenizer(vmax=1024, min_pair=20, max_tok=16)
fill(tc, CORPUS)
check(tc.mint_rescued == 0 if tc.gate_skipped == 0 else True,
      f"no rejects ({tc.gate_skipped}) means no rescues ({tc.mint_rescued}) -- the row is armed on the rejects")

# --- 2. None MUST STILL MEAN EXHAUSTED ------------------------------------------------------------------------
# The fix must not make maybe_grow loop forever or mint past its cap. None has to keep its one true meaning.
print("\nNone STILL MEANS EXHAUSTED, AND THE CAP STILL BINDS")
t = DynamicTokenizer(vmax=1024, min_pair=20, max_tok=16)
fill(t, CORPUS)
check(t.vocab_size <= t.vmax, f"never mints past vmax ({t.vocab_size} <= {t.vmax})")
t2 = DynamicTokenizer(vmax=300, min_pair=10 ** 9, max_tok=16)   # nothing can ever clear min_pair
for i in range(0, len(CORPUS), 8192): t2.segment(CORPUS[i:i + 8192], count=True)
check(t2.maybe_grow() is None, "an unreachable min_pair returns None -- genuinely nothing to mint")
check(t2.vocab_size == 256, "...and mints nothing")
t3 = DynamicTokenizer(vmax=256, min_pair=1, max_tok=16)          # already at the cap
for i in range(0, len(CORPUS), 8192): t3.segment(CORPUS[i:i + 8192], count=True)
check(t3.maybe_grow() is None and t3.vocab_size == 256, "at vmax it returns None without minting")

# --- 3. EVERY MINTED TOKEN IS WELL FORMED ---------------------------------------------------------------------
# The walk-on loop picks a different candidate than the one first chosen, so the invariants that used to hold
# by construction now have to be checked.
print("\nEVERY MINTED TOKEN IS WELL FORMED")
t = DynamicTokenizer(vmax=1024, min_pair=20, max_tok=8)
fill(t, CORPUS)
check(all(len(b) <= t.max_tok for b in t.id2bytes), f"no token exceeds max_tok={t.max_tok}")
check(len(set(t.id2bytes)) == len(t.id2bytes), "no token is minted twice")
check(all(t.seq2id[b] == i for i, b in enumerate(t.id2bytes)), "seq2id agrees with id2bytes at every id")
check(len(t.bytes_per_id) == t.vocab_size, "bytes_per_id has one entry per token -- it is the bits/byte denominator")
check(all(t.bytes_per_id[i] == len(t.id2bytes[i]) for i in range(t.vocab_size)),
      "...and every entry is the token's real byte length, or every bits/byte number is wrong")
check(t.maxlen == max(len(b) for b in t.id2bytes), "maxlen matches the longest token (greedy match reads it)")

# --- 4. ROUND TRIP ---------------------------------------------------------------------------------------------
# Byte-grounded means lossless for ANY input, including bytes the corpus never contained.
print("\nBYTE-GROUNDED: SEGMENTATION ROUND-TRIPS")
t = DynamicTokenizer(vmax=512, min_pair=20, max_tok=8)
fill(t, CORPUS)
for probe in (CORPUS[:5000], b"the model", b"\x00\xff\xfe binary \x01", b"", b"never-seen-\xc3\xa9-utf8"):
    ids = t.segment(probe, count=False)
    back = b"".join(t.id2bytes[i] for i in ids)
    check(back == probe, f"round-trips {len(probe)} bytes exactly" + (" (unseen bytes)" if b"\xff" in probe else ""))

# --- 5. SAVE / LOAD --------------------------------------------------------------------------------------------
# The vocabulary has to survive the checkpoint or a resumed run indexes a restored embedding with a different
# vocabulary -- silent, because VMAX fixes the row count so every shape still matches.
print("\nSAVE / LOAD PRESERVES THE VOCABULARY")
import json, tempfile                                            # noqa: E402
t = DynamicTokenizer(vmax=512, min_pair=20, max_tok=8)
fill(t, CORPUS)
_p = os.path.join(tempfile.mkdtemp(), "tok.json")
t.save(_p)
u = DynamicTokenizer.load(_p)
check(u.vocab_size == t.vocab_size, f"vocab size survives ({u.vocab_size})")
check(u.id2bytes == t.id2bytes, "every token survives, in the same order -- ids are positions")
check(u.bytes_per_id == t.bytes_per_id, "and so does the bits/byte denominator")
_s = CORPUS[:3000]
check(t.segment(_s, count=False) == u.segment(_s, count=False),
      "the loaded tokenizer segments identically -- otherwise a resume re-spells its own history")

print()
if FAILED:
    print(f"FAILED {len(FAILED)} check(s):")
    for f in FAILED: print(f"  - {f}")
    sys.exit(1)
print("tok_test: all checks passed")
