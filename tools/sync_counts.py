"""Update the entry-point / stub / deferred counts in docs/04_CONTRACT.md from the live tree.

WHY THIS EXISTS. P4 changes three numbers on every commit -- how many entry points there are, how
many are still stubs, how many are declared deferred -- and each is written in four to six places in
the contract document. K13 catches every stale copy, which is the point of K13; what it should not
also require is that a human retype six numbers correctly per commit, because that is a task whose
failure mode is a NEW wrong number rather than an old one. Six hand-edits per commit is how
docs/03_WIRING.md fell a whole ledger generation behind.

ONE SOURCE, AND IT IS THE CHECK'S OWN. The counting rule -- what a stub is, what an entry point is --
lives in tests/test_contract.py::k13_live_counts and nowhere else. This tool IMPORTS it rather than
re-deriving it, because two implementations of "how many entry points are there" is the report-path/
audit-path split that produced most of the defects in ISSUES. A tool importing a test module is
backwards in most projects; here the test module is where the definition lives, and copying the
definition out to make the direction look conventional would be the actual mistake.

    python3 tools/sync_counts.py            # rewrite the counts
    python3 tools/sync_counts.py --check    # exit 1 and name the stale sites
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tests"))

import test_contract as K                                              # noqa: E402

DOC = os.path.join(ROOT, "docs", "04_CONTRACT.md")

# (regex over the document, the live-count keys its groups claim, in group order). Every pattern here
# must also be one K13 searches for, or this tool would fix a number K13 never checks -- a silent
# rewrite of prose nothing verifies, which is worse than a stale number a check reports.
# NO PATTERN TABLE OF ITS OWN. The first version had one, and it drifted from K13's within a single
# run: K13 reported three stale counts this tool had just declared current, because its shapes were a
# hand-copied subset. The shapes ARE K13's -- `_K13_PATTERNS`, with the same context words, the same
# transition test and the same clause-scoped tense skip -- so by construction this tool fixes exactly
# what that check reads and touches nothing it does not. A second table would be a second definition
# of "which numbers matter", which is the split this whole project exists to remove.


def main(argv):
    counts = {k: v[0] for k, v in K.k13_live_counts(K.SRC).items()}
    text = io.open(DOC, encoding="utf-8").read()
    stale = []

    # THE SAME SKIPS K13 MAKES, AND THIS TOOL SHIPPED WITHOUT THEM. On its first run it rewrote
    # "the 117 entry points were named by no row at all" to 130 and "the gap was 56 entry points
    # wide" to 130 -- two HISTORICAL sentences, clobbered into false statements about the past,
    # silently. K13 skips a past-tense clause on purpose (a history is allowed to record the number
    # it recorded), and a tool that edits what the check does not read is a tool that damages prose
    # nothing verifies.
    edits = []            # (start, end, replacement), collected then applied right-to-left
    spans = K._k13_sentences(text)
    taken = []

    for label, rx, keys, ctx in K._K13_PATTERNS:
        for m in re.finditer(rx, text, re.I | re.M):
            if any(a <= m.start() and m.end() <= b for a, b in taken):
                continue                      # a more specific pattern already claimed this text
            span = next(((a, b) for a, b in spans if a <= m.start() < b), None)
            sentence = text[span[0]:span[1]] if span else text[max(0, m.start() - 200):m.end() + 200]
            if ctx and not any(c in sentence.lower() for c in ctx):
                continue
            taken.append((m.start(), m.end()))
            if K._K13_TRANSITION.search(text[max(0, m.start() - 40):m.start()]):
                continue                      # `19 -> 17 of 25` is a transition, not a claim
            if span and K._K13_PAST.search(K._k13_clause(sentence, m.start() - span[0])):
                continue                      # a history keeps the number it recorded
            # PFX and ORDER rows key off a captured NAME, not a fixed quantity, so their live value
            # depends on the match itself; K13 checks them and this tool leaves them to K13.
            if keys[0] in ("PFX", "ORDER"):
                continue
            for i, key in enumerate(keys):
                if key not in counts or m.group(i + 1) is None:
                    continue
                want = str(counts[key])
                if m.group(i + 1) != want:
                    stale.append(f"{m.group(0).strip()!r} [{label}]: {key} "
                                 f"{m.group(i + 1)} -> {want}")
                    edits.append((m.start(i + 1), m.end(i + 1), want))

    for a, b, want in sorted(edits, reverse=True):
        text = text[:a] + want + text[b:]

    if "--check" in argv:
        if stale:
            print(f"{len(stale)} stale count(s) in docs/04_CONTRACT.md:")
            for line in stale:
                print("  " + line)
            print("Fix with: python3 tools/sync_counts.py")
            return 1
        print(f"docs/04_CONTRACT.md counts are current "
              f"({counts['stubs']} stubs of {counts['entry_points']} entry points, "
              f"{counts['deferred']} deferred).")
        return 0

    io.open(DOC, "w", encoding="utf-8").write(text)
    print(f"docs/04_CONTRACT.md: {len(stale)} count(s) updated -- {counts['stubs']} stubs of "
          f"{counts['entry_points']} entry points, {counts['deferred']} deferred.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
