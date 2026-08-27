#!/usr/bin/env python3
"""Do the notes still describe THIS code?

notes/ holds about a megabyte of prose and it has been wrong about the defaults twice, expensively:

  02_IDEAS.md filed A91 as "NEVER IMPLEMENTED" for a mechanism that had been built. Its own correction entry
  records the cost -- "it was read during the 0.75 GB planning and used to tell the user the mechanism did not
  exist". Then the same entry went stale one level down: 07_WIP.md still files the GROW_CAP family as "never
  been set anywhere in the project's history" while it drives ~20 arms and has run for over a million steps.

  Nine files state FAB_N0=3 is the default. It has been 2048 since 2026-08-17. That claim is 00_INDEX's
  "five things to know before spending any GPU time" item #1 -- the most load-bearing sentence in the corpus.

  GROW_LIFT is documented as a multiplier of 2.0 (08_GLOSSARY), as "+256 rows" (02_IDEAS) and is in fact a
  fraction of 0.08. Three incompatible unit systems, none of them current. Copying the glossary's 2.0 into a
  run today lifts the cap by 200% per event.

Fixing those instances once would leave the CLASS alone, and the class is what keeps costing. So:

  1. notes/CURRENT_DEFAULTS.md is GENERATED from _SPEC. It is the only place in notes/ allowed to state a
     current default, and it cannot drift because it is not written by hand.
  2. Every OTHER note that states a default is checked against _SPEC. A note about history stays as it is --
     the corpus is a record and rewriting it would destroy the thing it is for -- but it must SAY it is
     history. Any line that names a knob and a value and does not read as historical is reported here.

Run:  python3 notes_check.py           check, and report drift
      python3 notes_check.py --write   regenerate notes/CURRENT_DEFAULTS.md as well
"""
import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "self_organize.py")
NOTES = os.path.join(ROOT, "notes")
GENERATED = os.path.join(NOTES, "CURRENT_DEFAULTS.md")

# --- the one source of truth ------------------------------------------------------------------------------
_tree = ast.parse(open(SRC).read())
_spec_node = next((n for n in _tree.body
                   if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "_SPEC"), None)
if _spec_node is None:
    print("!! _SPEC is not a module-level assignment in self_organize.py -- this check cannot find the "
          "registry it is supposed to check the notes against.")
    sys.exit(1)
SPEC = ast.literal_eval(_spec_node.value)          # {KNOB: (kind, default)}
DEFAULTS = {k: v[1] for k, v in SPEC.items()}


def _norm(v):
    """Compare 3 with 3.0 and 1 with True, but keep 'cosine' a string."""
    if isinstance(v, bool): return float(v)
    if isinstance(v, (int, float)): return float(v)
    s = str(v).strip().rstrip(".,;:)")
    try: return float(s)
    except ValueError: return s


# --- 1. generate ------------------------------------------------------------------------------------------
def generate():
    by_group = {}
    for k, (kind, dflt) in sorted(SPEC.items()):
        by_group.setdefault(kind, []).append((k, dflt))
    out = [
        "# CURRENT DEFAULTS", "",
        "**GENERATED FILE — do not edit.** `python3 notes_check.py --write` regenerates it from `_SPEC` in",
        "`self_organize.py`, and `notes_check.py` (wired into `selftest.sh`) fails if it is out of date.", "",
        "This file exists because the notes have been wrong about the defaults twice at real cost — once",
        "telling the user a built mechanism did not exist, once stating `FAB_N0=3` in nine files a week after",
        "it became 2048. Every other note in this directory is a RECORD of what was true when it was written.",
        "This is the only one that claims to describe the code as it stands, and it is the only one that is",
        "not written by hand.", "",
        f"{len(SPEC)} knobs.", "",
    ]
    for kind in sorted(by_group):
        out += [f"## kind `{kind}`", "", "| knob | default |", "|---|---|"]
        out += [f"| `{k}` | `{d}` |" for k, d in by_group[kind]]
        out += [""]
    return "\n".join(out) + "\n"


# --- 2. check ---------------------------------------------------------------------------------------------
# A line is HISTORY if it says so. The corpus is a record; a note that reports what a commit did is correct
# even when the value has since moved, and rewriting those would destroy what notes/ is for.
HISTORICAL = re.compile(
    r"\b(was|were|used to|then|previously|until|since\s+(?:renamed|changed)|historical|superseded|predates?|"
    r"records? that|recorded|at the time|no longer|old default|former|before\b|E\d+\.\d+|INV-\d+)\b"
    r"|`[0-9a-f]{7,10}`"                       # a commit hash reference makes it a historical citation
    r"|~~", re.I)

# A KNOB=VALUE IN PROSE IS ALMOST ALWAYS AN ARM, NOT A DEFAULT. The first version of this check matched every
# `KNOB=VALUE` in the corpus and reported 319 lines, nearly all of them correct: "arm B (`FAB_GROW=0
# FAB_N0=2048`)" describes a run that happened, and "`X24` (every chaining arm is worse than `FABRIC=0`)" is a
# finding. Neither says anything about the shipped default, and a checker that cannot tell the difference is a
# checker nobody will run twice.
# So the line must CLAIM a default -- say so in words, or cite the registry -- before its value is checked.
# ...AND "THE LINE MENTIONS THE WORD DEFAULT" IS STILL TOO LOOSE. The second version required a default
# keyword somewhere on the line and then checked EVERY knob on it -- so an experiment's config line,
# "`base` = defaults - `frozen` = `TOK_MINT_UNTIL=1` - `drop` = `DROPOUT=0.1`", reported four knobs because
# one word on it was "defaults". The keyword has to be attached to the VALUE, not merely present.
# These are the shapes the corpus actually uses to state a default. Anything else is an arm.
_K = r"`?\b([A-Z][A-Z0-9_]{2,})\b`?"
_V = r"\*{0,2}`?([\w.\-]+)`?\*{0,2}"
CLAIMS = [re.compile(p) for p in (
    _K + r"\s+(?:defaults?|ships?)\s+(?:to|at)\s+" + _V,        # KNOB defaults to X / ships at X
    r"\bdefaults?\s+(?:to\s+)?" + _K + r"\s*=\s*" + _V,          # default KNOB=X
    _K + r"\s*=\s*" + _V + r"\s*\((?:the\s+)?defaults?\)",       # KNOB=X (default)
    _K + r"\s*=\s*" + _V + r"\s+by default",                     # KNOB=X by default
    _K + r"\s+is\s+the\s+default\s+at\s+" + _V,                  # KNOB is the default at X
)]
# ...plus every knob on a line that quotes the registry itself, which IS a claim about all of them.
SPEC_LINE = re.compile(r"`_SPEC`\s*(?:reads?|says?|has)", re.I)
ANY = re.compile(_K + r"\s*=\s*" + _V)


def _live_markdown():
    """Every markdown file that is NOT archived.

    SCANNING ONLY notes/ WAS NOT ENOUGH. STATE.md sat at the top level for eleven days describing itself as a
    "living project ledger" whose PROTOCOL is "binding, for the assistant" and whose first instruction is to
    update it every turn -- while carrying FAB_N0=3, abandoned since 2026-08-15. A stale file that tells a
    reader it is authoritative is worse than a stale file that does not, and this check could not see it.
    Everything outside archive/ is now in scope; archive/ is excluded by definition, because a frozen record
    describing an older system is exactly what it is for. See ARCHIVE.md.
    """
    out = []
    for fn in sorted(os.listdir(ROOT)):
        if fn.endswith(".md") and fn != "ARCHIVE.md": out.append(os.path.join(ROOT, fn))
    for fn in sorted(os.listdir(NOTES)):
        if fn.endswith(".md") and fn != os.path.basename(GENERATED): out.append(os.path.join(NOTES, fn))
    return out


def check():
    bad = []
    for path in _live_markdown():
        fn = os.path.relpath(path, ROOT)
        for i, line in enumerate(open(path, errors="ignore"), 1):
            if HISTORICAL.search(line): continue              # a record of what WAS true
            hits = []
            for rx in CLAIMS: hits += rx.findall(line)
            if SPEC_LINE.search(line): hits += ANY.findall(line)
            for knob, val in hits:
                if knob not in DEFAULTS: continue
                got, want = _norm(val), _norm(DEFAULTS[knob])
                if isinstance(got, str) and isinstance(want, str) and got.lower() == want.lower(): continue
                if got == want: continue
                bad.append((fn, i, knob, val, DEFAULTS[knob], line.strip()[:150]))
    return bad


if __name__ == "__main__":
    write = "--write" in sys.argv
    text = generate()
    have = open(GENERATED).read() if os.path.exists(GENERATED) else None
    if write:
        open(GENERATED, "w").write(text)
        print(f"wrote {os.path.relpath(GENERATED, ROOT)} ({len(SPEC)} knobs)")
    elif have != text:
        print(f"!! {os.path.relpath(GENERATED, ROOT)} is out of date with _SPEC -- "
              f"run: python3 notes_check.py --write")
        sys.exit(1)

    _arch = os.path.join(ROOT, "archive")
    if os.path.isdir(_arch) and not os.path.exists(os.path.join(ROOT, "ARCHIVE.md")):
        print("!! archive/ exists but ARCHIVE.md does not -- the frozen trees are unlabelled, which is how "
              "garry/self_organize.py's FAB_N0=3 got quoted as current in nine notes.")
        sys.exit(1)

    drift = check()
    if not drift:
        print(f"notes_check: {len(SPEC)} knobs, {len(_live_markdown())} live markdown files, "
              f"no default stated that _SPEC disagrees with (archive/ excluded by design)")
        sys.exit(0)
    print(f"!! {len(drift)} note line(s) state a default that _SPEC contradicts.\n"
          f"   Either correct the value, or mark the line as history (say 'was', 'used to', or cite the "
          f"commit) -- a record of what WAS true is fine and is why this corpus exists.\n")
    for fn, i, knob, val, real, line in drift:
        print(f"  {fn}:{i}  {knob} stated as {val}, _SPEC says {real}")
        print(f"      {line}")
    sys.exit(1)
