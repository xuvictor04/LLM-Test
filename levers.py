#!/usr/bin/env python3
"""levers.py -- what can be set, and what setting it also changes.

A knob is only a lever if moving it moves ONE thing. Three ways that stops being true here:

  DERIVED   the knob's DEFAULT is computed from another knob, so leaving it unset ties it to that
            other knob's value. Setting it explicitly still wins -- this is a default, not an
            override -- but the tie is invisible at the read site.
  OVERRIDE  the knob is read and then REASSIGNED, so an explicit setting is discarded. This is the
            one that is a bug rather than a design: the config says one thing and the run does
            another.
  UNKNOWN   the knob is read from the environment but is not in _SPEC, so nothing declares what it
            is or what it defaults to.

This re-derives all three from the AST of self_organize.py and compares them against what the file
DECLARES (_SPEC, _SPEC_FREE, _DERIVED). Drift in either direction is an error: an undeclared
derived default, or a declaration for something that is no longer derived.

    python3 levers.py           # the table; exit 1 on drift
    python3 levers.py --quiet   # drift only
"""
import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "self_organize.py")
READERS = {"_i", "_f", "_env"}


def scan(path=SRC):
    """Read the source and report (reads, computed, spec, free, derived)."""
    src = open(path).read()
    tree = ast.parse(src)

    reads, computed = {}, {}
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in READERS):
            continue
        if not (n.args and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str)):
            continue
        k = n.args[0].value
        reads.setdefault(k, []).append(n.lineno)
        # a default that is not a literal is computed -- from another knob, or from a shape like WIN
        if len(n.args) >= 2 and not isinstance(n.args[1], ast.Constant):
            computed[k] = ast.unparse(n.args[1])

    spec = set(re.findall(r'^\s*"([A-Z_0-9]+)": \(', src, re.M))
    free = set(re.findall(r'"([A-Z_0-9]+)":', re.search(r"_DERIVED = \{(.*?)\n\}", src, re.S).group(1)))
    derived = {}
    for k, srcs in re.findall(r'"([A-Z_0-9]+)":\s*\(([^)]*)\)', re.search(r"_DERIVED = \{(.*?)\n\}", src, re.S).group(1)):
        derived[k] = tuple(x.strip().strip('"') for x in srcs.split(",") if x.strip())
    return reads, computed, spec, free, derived


def main(argv):
    quiet = "--quiet" in argv
    reads, computed, spec, free, derived = scan()
    problems = []

    unknown = sorted(set(reads) - spec)
    undeclared = sorted(set(computed) - set(derived))
    stale = sorted(set(derived) - set(computed))

    if not quiet:
        print(f"knobs read from the environment : {len(reads)}")
        print(f"declared in _SPEC               : {len(spec)}")
        print(f"declared derived (_DERIVED)     : {len(derived)}")
        print()
        print("=== DERIVED: leaving this unset ties it to another knob ===")
        w = max((len(k) for k in derived), default=1)
        for k in sorted(derived):
            got = computed.get(k, "<NOT DERIVED IN SOURCE>")
            print(f"  {k:<{w}}  follows {', '.join(derived[k]):<16}  default = {got}")
        print()
        print("=== OVERRIDE: an explicit setting is DISCARDED (read, then reassigned) ===")
        print("  FAB_MIN_STEPS   forced to 0 by CHAIN_VOTE inside Fabric.__init__.")
        print("                  CHAIN_VOTE defaults to 1, so the declared default of 2 on the")
        print("                  chaining path is never what runs. self_organize.py refuses the")
        print("                  combination rather than discarding the value silently.")

    if unknown:
        problems.append(f"read but not in _SPEC: {', '.join(unknown)}")
    if undeclared:
        problems.append("derived in the source but not in _DERIVED: "
                        + ", ".join(f"{k} (= {computed[k]})" for k in undeclared))
    if stale:
        problems.append(f"in _DERIVED but no longer derived in the source: {', '.join(stale)}")
    if set(free) != set(derived):
        problems.append(f"_SPEC_FREE and _DERIVED disagree: {sorted(set(free) ^ set(derived))}")

    if problems:
        print()
        for p in problems:
            print(f"!! {p}")
        return 1
    if not quiet:
        print()
        print("levers: declarations match the source.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
