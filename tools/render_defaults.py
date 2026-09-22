"""Regenerate docs/05_DEFAULTS.md from the live lever registry.

WHY THIS FILE EXISTS. `notes/CURRENT_DEFAULTS.md` carries the header "GENERATED FILE -- do not edit"
and regenerates from `_SPEC` in `self_organize.py`, which is the ARCHIVED tree: every knob in it is
a knob this system no longer reads, under names this system no longer generates. So the one document
in the repository that claims to describe the defaults as they stand describes a different program,
and the failure mode its own header records -- "the notes have been wrong about the defaults twice at
real cost" -- is live again one tree over. This renders the same fact for `src/`.

WHAT IT ADDS THAT A TABLE OF DEFAULTS DOES NOT. The question actually asked of this project is not
"what is each knob set to", it is WHAT IS OFF: which declared mechanisms do not run at the shipped
configuration, so that a report saying they did nothing is read as "off" rather than as "measured and
found worthless". That is section 1, and it is derived rather than typed -- a False on an `on/off`
unit, and a 0 on a numeric lever, which this tree uses as the OFF sentinel in most places and not in
all. The help text is quoted beside each so the two can be told apart by a reader.

THE COUNTS IN THE HEADINGS ARE GENERATED, which is the rule tests/test_contract.py's K13 enforces on
prose: a count in a document is a copy of a fact, and the only safe copy is one a generator rewrites.

    python3 tools/render_defaults.py            # rewrite docs/05_DEFAULTS.md in place
    python3 tools/render_defaults.py --check    # exit 1 if the file on disk is stale, print the diff
"""
import difflib
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from spine import assemble        # noqa: E402,F401 -- imported to REGISTER every LeverSet
from spine import registry                                            # noqa: E402

DOC = os.path.join(ROOT, "docs", "05_DEFAULTS.md")

HEADER = """# 05 — DEFAULTS: what is on, what is off, and what every knob is set to

**GENERATED FILE — do not edit.** `python3 tools/render_defaults.py` rewrites it from the live lever
registry in `src/*/levers.py`; `tests/test_assemble.py`'s A10 fails if what is on disk is not what
the generator would write today. Nothing below this paragraph is typed by hand.

`notes/CURRENT_DEFAULTS.md` is the same idea for `self_organize.py` — the ARCHIVED tree. Every knob
in that file is one this system no longer reads, under a name it no longer generates. This file is
about `src/`.

**Env names are GENERATED, not declared.** A lever is a field on a `LeverSet` with a `PREFIX`, and
the operator's name for it is `PREFIX_FIELD` upper-cased. There is no second list to keep in step,
which is why a name that looks wrong here is a field that is wrong in `src/<pkg>/levers.py`.

**A default is the one value `from_env` never coerces** (`spine/lever.py::Lever`), so a default is
also the one value no `choices=`/`domain=` check ever sees at resolution time. The declaration-time
checks in that constructor are what stand in for it.
"""

OFF_INTRO = """
## 1. What is OFF at the shipped defaults

Read this before reading a run's DID IT FIRE report. A mechanism that is off by configuration and a
mechanism that ran and found nothing print the same 0, and the whole of this tree's counter
convention exists to separate them — but only for mechanisms that were ASKED. A lever that is off
here was never asked, and no counter in any report can say so on its own.

**Boolean levers that ship False.** These are flags; False is unambiguous.
"""

ZERO_INTRO = """
**Numeric levers that ship 0.** Zero is this tree's documented OFF sentinel in most of these places
and a legitimate value in some, so the help text is quoted rather than summarised. `spine/lever.py`
records the rule and `src/tok/api.py` names five of the exceptions by hand: *"freeze_at, retok_every,
mint_pmin, mint_novel and probation_uses"* all use 0 as OFF, while a period of 0 elsewhere means
DISARMED — which the cadence audit reports as a different state from starved.
"""


def _sentence(text):
    """The first sentence of a help string, flattened to one line, pipes escaped for a table cell.

    IT WILL NOT CUT AT "i.e." OR ANY OTHER ABBREVIATION, which is the whole reason this is not a
    `split(". ")`: the first pass of this generator rendered CAP_VOCAB_START as "0 means start at
    the model's row count, i.e." and that reads as a truncated claim rather than as a sentence.
    A full stop only ends a sentence when what precedes it is more than one letter and what follows
    it is a capital.
    """
    flat = " ".join(str(text).split()).replace("|", "\\|")
    m = re.search(r"(?<=[a-z0-9)\]]{2})\.\s+(?=[A-Z])", flat)
    if m and m.start() > 24:
        return flat[:m.start() + 1].strip()
    return flat if len(flat) <= 200 else flat[:197].rstrip() + "..."


def _whole(text, cap=340):
    """The WHOLE help, flattened. Used where cutting would drop the clause the section is about.

    THE FIRST PASS OF THIS GENERATOR CUT AT "; " AND " -- " AND LOST EXACTLY THE SENTENCE THE ZERO
    TABLE EXISTS FOR. Both punctuations are used mid-sentence throughout these declarations, so
    LM_LAYERS rendered as "Depth of the base LM" with "0 means take the current arm's depth (4 for
    transformer, 1 for gru)" cut off, and CAP_VOCAB_START lost "0 means start at the model's row
    count" the same way -- in a table whose entire purpose is to say what a 0 means. A summariser
    that removes the distinguishing clause is worse than no summary, because the row still looks
    answered.
    """
    flat = " ".join(str(text).split()).replace("|", "\\|")
    return flat if len(flat) <= cap else flat[:cap - 3].rstrip() + "..."


def _unit(lv):
    """The unit as an operator reads it. A clock-unit lever carries the CLASS, not a label."""
    u = lv.unit
    return getattr(u, "__name__", None) or str(u)


def _cell(v):
    return "`" + repr(v) + "`"


def _bounds(lv):
    if lv.choices is not None:
        return "choices " + ", ".join("`%r`" % c for c in lv.choices)
    if lv.domain is not None:
        lo, hi = lv.domain
        return "domain (%s, %s)" % ("−∞" if lo is None else lo, "∞" if hi is None else hi)
    return ""


def defaults_markdown():
    """The whole document, as one string. The oracle A10 compares against."""
    # NO build() CALL. Importing spine.assemble is what registers every LeverSet -- the registry
    # fills in __init_subclass__, at import time -- and build() would additionally RESOLVE them,
    # which latches the assembly. That latch is process-wide, so a generator that built would be
    # callable exactly once per interpreter and would raise the moment tests/test_assemble.py's A10
    # ran it after A1. Defaults are DECLARATIONS; resolving is what turns them into a Config, and
    # this document is about the declaration.
    sets = registry.all_sets()
    order = sorted(sets)

    off_rows, zero_rows = [], []
    for pfx in order:
        for field, lv in sorted(sets[pfx]._levers.items()):
            env = "%s_%s" % (pfx, field.upper())
            if lv.default is False:
                off_rows.append((env, _whole(lv.help)))
            elif isinstance(lv.default, (int, float)) and not isinstance(lv.default, bool) \
                    and float(lv.default) == 0.0:
                zero_rows.append((env, _unit(lv), _whole(lv.help)))

    out = [HEADER, OFF_INTRO]
    out.append("\n| lever | what it turns off |\n|---|---|")
    for env, why in off_rows:
        out.append("| `%s` | %s |" % (env, why))
    out.append("\n%d levers ship False." % len(off_rows))
    out.append(ZERO_INTRO)
    out.append("\n| lever | unit | what the help says |\n|---|---|---|")
    for env, unit, why in zero_rows:
        out.append("| `%s` | %s | %s |" % (env, unit, why))
    out.append("\n%d numeric levers ship 0." % len(zero_rows))

    out.append("\n---\n\n## 2. Every lever, by package\n")
    total = sum(len(sets[p]._levers) for p in order)
    out.append("%d levers across %d packages.\n" % (total, len(order)))
    for pfx in order:
        lvs = sets[pfx]._levers
        out.append("\n### %s (%d levers)\n" % (pfx, len(lvs)))
        out.append("| lever | default | unit | accepts | what it is |")
        out.append("|---|---|---|---|---|")
        for field, lv in sorted(lvs.items()):
            out.append("| `%s_%s` | %s | %s | %s | %s |"
                       % (pfx, field.upper(), _cell(lv.default), _unit(lv),
                          _bounds(lv), _sentence(lv.help)))
    return "\n".join(out).rstrip() + "\n"


def main(argv):
    want = defaults_markdown()
    if "--check" in argv:
        have = io.open(DOC, encoding="utf-8").read() if os.path.isfile(DOC) else ""
        if have == want:
            print("docs/05_DEFAULTS.md is current (%d lines)" % len(want.splitlines()))
            return 0
        for d in difflib.unified_diff(have.splitlines(), want.splitlines(),
                                      "on disk", "regenerated", n=0, lineterm=""):
            print(d)
        print("STALE -- run: python3 tools/render_defaults.py")
        return 1
    io.open(DOC, "w", encoding="utf-8").write(want)
    print("wrote %s (%d lines)" % (DOC, len(want.splitlines())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
