"""Regenerate docs/03_WIRING.md from the live coupling table.

WHY THIS FILE EXISTS. docs/03_WIRING.md carried its regeneration command in its own header as a
here-doc a reader was expected to paste, and it still drifted a whole ledger generation: the file on
disk said 13 couplings and 10 wires while the tree resolved 23 and 19. A command in prose is a command
nobody runs. This is the same command as an entry point, so a check can call it and diff -- which
tests/test_assemble.py's A9 does, and which is the only reason the number on disk is now evidence
rather than a claim.

The prose above the generated body is hand-written and is PRESERVED, up to and including the
`## State of the graph` heading. The sentence under that heading is not: it states the same four
counts the body states, so it is generated too, and a file with one generated total and one typed
total is the report-path/audit-path split this project already paid for.

    python3 tools/render_wiring.py            # rewrite docs/03_WIRING.md in place
    python3 tools/render_wiring.py --check    # exit 1 if the file on disk is stale, print the diff
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from spine import assemble                                            # noqa: E402
from spine import lever                                               # noqa: E402
from spine.wire import WIRE_BUDGET                                    # noqa: E402

DOC = os.path.join(ROOT, "docs", "03_WIRING.md")
HEADING = "## State of the graph"

_WORDS = {10: "ten", 11: "eleven", 12: "twelve", 13: "thirteen", 14: "fourteen", 15: "fifteen"}


def _build():
    """A fresh build in this process. The latch is released because a generator IS a startup.

    spine/lever.py latches after build() returns; this module is a one-shot script whose whole job is
    to perform an assembly and print it, so the release is honest here for the same reason
    tests/test_assemble.py::_build documents it for seven simulated startups. Nothing under src/ may
    do this -- O10 refuses the import.
    """
    lever._reopen_assembly()
    return assemble.build(environ={})


def wiring_markdown():
    """The whole file: the preserved hand-written head, a generated summary, the rendered body."""
    cfgs, wires, warnings = _build()
    body = assemble.render(cfgs, wires)

    # THE SAME READ render() MAKES, not a parallel one. render() decides "resolved" by looking at what
    # actually LANDED on a Config -- a declaration whose value never arrived is the failure the DEFERRED
    # status exists to show -- and reads "intra" off the coupling's own `local` flag rather than as
    # `resolved - spent`. Inferring either would give this summary a second way to compute a number the
    # body below already states, which is how one quantity ends up with two answers depending on which
    # line of one file you happen to read.
    landed = {f"{pfx}.{f}" for pfx, cfg in cfgs.items() for f in cfg.wired()}
    live = [c for c in assemble.COUPLINGS if c.dst in landed]
    declared = len(assemble.COUPLINGS)
    resolved = len(live)
    deferred = declared - resolved
    spent = len(wires.all())
    intra = sum(1 for c in live if c.local)
    from spine import registry
    n_pkg = len(registry.all_sets())
    word = _WORDS.get(n_pkg, str(n_pkg))

    head = io.open(DOC, encoding="utf-8").read().split(HEADING)[0]

    summary = (
        f"{declared} couplings declared, {resolved} resolved, {deferred} deferred; "
        f"{spent} cross-package wires of a {WIRE_BUDGET} budget; {intra} intra-package.\n"
        f"All {word} packages under `src/*/levers.py` are imported by `spine/assemble.py` and "
        f"registered, so no\nrow defers and every endpoint is checked against a real declaration at "
        f"import (`_check_endpoints`).\n"
    )
    return f"{head}{HEADING}\n\n{summary}\n```\n{body}\n```\n"


def main(argv):
    want = wiring_markdown()
    if "--check" in argv:
        have = io.open(DOC, encoding="utf-8").read()
        if have == want:
            print(f"docs/03_WIRING.md is current ({len(want.splitlines())} lines).")
            return 0
        import difflib
        rel = os.path.relpath(DOC, ROOT)
        diff = difflib.unified_diff(have.splitlines(True), want.splitlines(True),
                                    f"{rel} (on disk)", f"{rel} (regenerated)")
        sys.stdout.writelines(diff)
        print(f"\nSTALE. Regenerate with: python3 tools/render_wiring.py")
        return 1
    io.open(DOC, "w", encoding="utf-8").write(want)
    print(f"wrote {os.path.relpath(DOC, ROOT)} ({len(want.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
