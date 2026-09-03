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

# EVERY FILE THE CHECKS READ **EXCEPT THE CHECKS THEMSELVES**. Two mistakes are recorded here
# because both were made in one sitting.
#
# The first version swept 04_CONTRACT.md alone, so when the lever count moved 261 -> 262 it printed
# "0 counts updated" while A8 was failing on a test file and K13 on a src/ docstring -- a tool
# reporting success over the subset it happened to look at.
#
# THE SECOND VERSION SWEPT tests/*.py AND EDITED THE ORACLE. K13's self-test builds a synthetic tree
# with 2 entry points and 2 levers; the tool rewrote those fixtures to the LIVE tree's numbers, and
# turned a mutation case -- `_GOOD_DOC.replace("against 2 declared levers", "against 3 declared
# levers")` -- into `replace("against 262", "against 262")`, a no-op that leaves the case printing
# PASS while testing nothing. An auto-fixer that edits the check is an auto-fixer that can make any
# check agree with any tree.
#
# So: docs/ and src/ only. A number in a test file is usually a FIXTURE, not a claim about the tree,
# and telling those apart is not something a regex can do. A8 still reports a stale count there and a
# human still fixes it, which is the right division: the checks own their own prose.
def _swept():
    import glob as _g
    out = [DOC]
    for pat in ("src/*/*.py", "src/spine/*.py", "docs/*.md"):
        out += sorted(_g.glob(os.path.join(ROOT, pat)))
    seen, uniq = set(), []
    for f in out:
        if f not in seen and os.path.isfile(f):
            seen.add(f)
            uniq.append(f)
    return uniq

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
    # A8 reads three whole-tree quantities K13 does not name the same way. Supplying them here lets
    # one tool answer for both checks; the values come from the same live registry A8 uses.
    counts.setdefault("levers", counts.get("levers_total"))
    stale, touched = [], 0
    for path in _swept():
        text = io.open(path, encoding="utf-8").read()
        before = text
        text = _fix(text, counts, stale, os.path.relpath(path, ROOT))
        if text != before:
            touched += 1
            if "--check" not in argv:
                io.open(path, "w", encoding="utf-8").write(text)
    if "--check" in argv:
        if stale:
            print(f"{len(stale)} stale count(s):")
            for line in stale:
                print("  " + line)
            print("Fix with: python3 tools/sync_counts.py")
            return 1
        print(f"counts are current ({counts['stubs']} stubs of {counts['entry_points']} entry "
              f"points, {counts['deferred']} deferred, {counts.get('levers_total')} levers).")
        return 0
    print(f"{len(stale)} count(s) updated across {touched} file(s) -- {counts['stubs']} stubs of "
          f"{counts['entry_points']} entry points, {counts['deferred']} deferred, "
          f"{counts.get('levers_total')} levers.")
    return 0


def _fix(text, counts, stale, rel):
    """Rewrite every stale count in one file's text, under K13's own rules."""

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
            # PFX AND ORDER ROWS KEY OFF A CAPTURED NAME. `### DATA -- src/data/api.py (17 levers)`
            # has its quantity in group 2 and the key for it -- `levers:DATA` -- in group 1, and the
            # ORDER rows are the same shape with the table's name. The first version skipped both and
            # left them to K13, which meant adding one lever to one package failed the suite with no
            # tool able to fix it. Resolving the key from the match is all it takes.
            # RESOLVED INTO FRESH NAMES, NEVER BACK INTO `keys`. The first version assigned to the
            # loop variable -- `keys, groups = ("levers:" + prefix,), (2,)` -- so on the SECOND
            # heading `keys[0]` was no longer "PFX" but the previous heading's resolved key, the
            # else-branch ran, and the tool wrote TOK's lever count into the group holding the
            # PREFIX: `### TOK -- src/tok/api.py (18 levers)` became `### 18 -- ...`, and every
            # heading after the first was corrupted the same way. Rebinding the thing you are
            # iterating over is the whole bug.
            if keys[0] == "PFX":
                use_keys, use_groups = ("levers:" + m.group(1).upper(),), (2,)
            elif keys[0] == "ORDER":
                use_keys = ({"ASSEMBLY_ORDER": "assembly_rows",
                             "LOOP_ORDER": "loop_rows"}.get(m.group(2).upper()),)
                use_groups = (1,)
            else:
                use_keys = keys
                use_groups = tuple(range(1, len(keys) + 1))
            for i, key in zip(use_groups, use_keys):
                if key not in counts or m.group(i) is None:
                    continue
                want = str(counts[key])
                if m.group(i) != want:
                    stale.append(f"{rel}: {m.group(0).strip()!r} [{label}]: {key} "
                                 f"{m.group(i)} -> {want}")
                    edits.append((m.start(i), m.end(i), want))

    for a, b, want in sorted(edits, reverse=True):
        text = text[:a] + want + text[b:]
    return text


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
