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


def default_mismatches(path=SRC):
    """Call-site defaults that disagree with the registry.

    _env() raises SystemExit for this at RUNTIME -- "read with default X here but the registry declares Y" --
    which is the right behaviour and the wrong time to find out. It is one edit away at all times: change a
    registry default, miss the read site, and EVERY RUN dies on its first call to that knob.

    It happened at d267864. ENC_WARMUP_MIN was corrected in the registry (3000 -> 200) and left at 3000 at the
    read site; the encoder warmup runs in every real run, so every arm launched from that commit would have
    exited immediately. levers.py checked declaration and derivation and not this, so the first thing that
    would have caught it was a GPU.

    Comments are excluded because this parses rather than greps: two of the three raw text matches for this
    pattern in the file are prose quoting code that used to exist.
    """
    src = open(path).read()
    tree = ast.parse(src)
    spec = {}
    for m in re.finditer(r'^\s*"([A-Z_0-9]+)":\s*\(\s*("?\w+"?)\s*,\s*([^)]*)\)', src, re.M):
        try: spec[m.group(1)] = ast.literal_eval(m.group(3).strip().rstrip(","))
        except Exception: pass
    free = set(re.findall(r'"([A-Z_0-9]+)":', re.search(r"_DERIVED = \{(.*?)\n\}", src, re.S).group(1)))
    out = []
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in READERS): continue
        if len(n.args) < 2 or not isinstance(n.args[0], ast.Constant): continue
        k = n.args[0].value
        if k not in spec or k in free: continue
        try: d = ast.literal_eval(n.args[1])
        except Exception: continue                    # computed default -- the registry cannot mirror it
        r = spec[k]
        same = (float(d) == float(r)) if isinstance(d, (int, float)) and isinstance(r, (int, float)) else (d == r)
        if not same: out.append((k, d, r, n.lineno))
    return out


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

    # THE BANNER MUST SURVIVE FABRIC=0. _EFF is built as one flat list and only the rows AFTER
    # `if _F0 is not None: _EFF += [` are guarded; _F0 is None whenever FABRIC=0. A single _F0 dereference above
    # that line kills every FABRIC=0 run before its first training step, which is exactly what happened to the
    # nofabric arm in round9:
    #     ("DIV_MASS", _F0.div_mass)  ->  AttributeError: 'NoneType' object has no attribute 'div_mass'
    # It cost a grid arm to find because I had reasoned that nofabric "must have run since" instead of checking a
    # log. This check costs nothing and does not need a GPU, so the next one is caught here.
    try:
        _lines = open(SRC).read().splitlines()
        _start = next(i for i, l in enumerate(_lines) if l.strip().startswith("_EFF = ["))
        _guard = next(i for i, l in enumerate(_lines) if "if _F0 is not None: _EFF" in l)
        for i, l in enumerate(_lines[_start:_guard], _start):
            _code = l.split("#", 1)[0]                      # comments quoting the bug are not the bug
            if "_F0." in _code and "_F0 is not None" not in _code:
                problems.append(f"self_organize.py:{i+1} dereferences _F0 in the UNGUARDED part of _EFF -- "
                                f"this is an AttributeError on every FABRIC=0 run: {_code.strip()[:70]}")
    except StopIteration:
        problems.append("could not locate the _EFF banner list or its `if _F0 is not None` guard -- if that "
                        "structure changed, this FABRIC=0 check is no longer checking anything")

    if problems:
        print()
        for p in problems:
            print(f"!! {p}")
        return 1
    if not quiet:
        print()
        _mm = default_mismatches()
    if _mm:
        print("!! a call-site default disagrees with the registry -- _env() will SystemExit on the first run:")
        for _k, _d, _r, _ln in _mm:
            print(f"   self_organize.py:{_ln}  {_k} read with default {_d!r}, registry declares {_r!r}")
        return 1
    print("levers: declarations match the source; no call-site default disagrees with it.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
