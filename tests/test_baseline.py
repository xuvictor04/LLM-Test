"""BASELINE FIXTURES: four recorded run.py workloads, so "bit-identical when the new mechanism is off"
is checked against recorded runs rather than asserted against nothing.

WHY THIS FILE EXISTS (Proposal 03 §0 R7, 03b S0b). tests/test_determinism.py measures the machine's noise
floor between two runs of the SAME tree; it holds no record of an earlier tree. Every stage of 03b
(S0b's mid-epoch act first) promises that a default run with the new mechanism disarmed reproduces the
tree it started from. That promise needs a stored trace from the base commit.

THE FOUR WORKLOADS (the WORKLOADS table below). B1 was the only one until 2026-09-27. The other three
were recorded at ae70638, before any edit of the register's §8 Stage 3 (docs/proposals/05_DECISIONS.md),
because Stage 3 edits the manage pass, the draw, the resume path and the held-out carve, and B1 reaches
none of them:
  B1   `run.py --max-windows 80` at DATA_STREAM_BYTES=120000, the shipped defaults otherwise. Recorded
       at d32e2ce and unchanged since. WHAT B1 CANNOT SEE: in 80 windows it reaches no FAB manage pass
       (FAB_MANAGE_EVERY=500), no mid-epoch act (TOK_RETOK_EVERY=3000) and no resume, and on the
       synthetic source there is no held-out block to carve (data/api.py::open_areas holds nothing out
       there). A change to the cull, the act, the resume path or the held-out carve passes B1 untested.
  B3   one full epoch, 314 windows, at tests/test_continuation.py's BASE plus FAB_MANAGE_EVERY=50
       FAB_GRACE=2 TOK_GROW_EVERY=30 TOK_RETOK_EVERY=150: six manage passes past a short grace, a mint
       burst due every 30 windows, mid-epoch acts at windows 151 and 301, and a store that fills,
       folds and rekeys (manage-, act- and MEM-heavy).
  B3r  B3 saved at window 170 -- after the first act, between the manage passes at 151 and 201 -- and
       continued by a second process with CKPT_RESUME: the continuing mid-epoch resume
       (spine/compose.py's seg-log replay, its loop_carried restore and its rebuilt-length check). Two
       legs, each held to its own record. AND ONE DERIVED CHECK, made on any machine: the parent's
       losses are B3's first 170 and the child's are B3's from window 170 on, exactly -- against this
       invocation's B3 when it ran, else B3's fixture.
  B5   DATA_SOURCE=real over data/train (eng, py, num, c), a 120000-byte stream, 200 windows: the real
       sources' held-out carve (open_areas) and the step from phase 0 into phase 1 (window 148 is the
       first wholly inside it).

WHAT IS STORED, per leg of a workload, at RUN_DEVICE=cpu and one thread:
  - the per-flush loss curve, as exact float reprs (a trace, compared exactly: same machine, same build);
  - every integer counter line the run prints (the INTEGER channel of test_determinism's vocabulary).
    Each fixture counter must be reproduced exactly; a counter added since is a new instrument and
    is listed, not compared. The count line reads "N integer counters compared, M new": until
    2026-09-27 it printed the run's parsed count as the compared one (247 for B1, of which 241 were
    compared and 6 were new);
  - the leg's environment and arguments. A fixture recorded under other ones FAILS, so a table edited
    after recording is named rather than compared against a different workload's record.
The float curve is compared exactly because the reference is this machine's own earlier run of the
same workload; test_determinism records that this machine reproduces a seeded run bit for bit, and B3,
B3r and B5 each reproduced their records in fresh processes, twice, before they were committed.

--exempt PATTERNS (comma-separated fnmatch patterns, repeatable) compares every fixture counter EXCEPT
those a pattern names, and prints each exempted counter with both values (and any pattern that
exempted nothing). It is for a change that may move some counters and nothing else -- a read beside
training moves lm.encode.calls, never a loss. SR0's bit-identity (register §8 3.1) reuses it, and so
does the real-source check made when 04-Q5's, 04-6.2's and 04-6.3's defaults flip; the losses are
always compared. compare_counters is the same comparison, importable.

--mutants runs planted changes that MUST FAIL: B3 at FAB_GRACE=3 and B5 at DATA_HOLDOUT_FRAC=0.06.
Each passes only if its comparison fails naming the first differing flush -- the check that the net has
teeth where it was widened. Every invocation but --record first runs the comparator's own known
answers on planted data (a loss change named at its flush; an exempt counter's bump passes, printed;
a bump no pattern names fails; a vanished counter fails; B3r's derived check fails a child that
departs from B3).

A FIXTURE IS A PER-MACHINE RECORD. It carries the machine key (platform, torch version, cpu count,
threads). On another machine the comparison is UNVERIFIABLE and this file says so and exits 0 -- it does
not pass a comparison it could not make, and it does not fail a box it was never recorded on. Record one
there with --record. (B3r's derived check is not machine-keyed and still runs there against the live B3.)

Run from the repository root:
    python3 tests/test_baseline.py                  compare every workload against its fixture
    python3 tests/test_baseline.py B3 B3r           compare the named workloads only
    python3 tests/test_baseline.py --exempt 'eval.*,lm.encode.calls'
    python3 tests/test_baseline.py --record B3      (re)write the named workloads' fixtures (every
                                                    workload's when none is named); commit each with
                                                    the commit it names
    python3 tests/test_baseline.py --mutants        the planted failures above
Exit 0 = matched (or unverifiable on this machine, printed as such); 1 = a difference, named.
"""
import argparse
import collections
import fnmatch
import json
import os
import platform
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# EVERY LEG RUNS ON THE CPU AT ONE THREAD; the machine key records the thread count.
COMMON = {"RUN_DEVICE": "cpu", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
# tests/test_continuation.py::BASE, the tenth-size fabric. COPIED, NOT IMPORTED: importing that file
# runs its checks. B3's record is its own either way -- an edit to BASE there moves nothing here.
_BASE = {"DATA_STREAM_BYTES": "60000", "SIG_WARMUP": "20", "FAB_N0": "256", "FAB_SLOTS": "512"}
_B3 = dict(COMMON, **_BASE, FAB_MANAGE_EVERY="50", FAB_GRACE="2", TOK_GROW_EVERY="30",
           TOK_RETOK_EVERY="150")
B3R_SAVE_AT = 170
# A WORKLOAD IS ONE OR MORE run.py LEGS, run in order, each (name, environment, arguments). `{tmp}` in an
# environment value is the workload's temporary directory, shared by its legs (the parent's checkpoint
# is the child's CKPT_RESUME, and TOK's vocabulary file sits beside the checkpoint directory) and
# deleted with everything in it once the workload has been read. The fixture records the template.
WORKLOADS = {
    "B1": {"fixture": "_baseline_fixture.json",
           "what": "run.py --max-windows 80 at the shipped defaults",
           "legs": (("run", dict(COMMON, DATA_STREAM_BYTES="120000"), ("--max-windows", "80")),)},
    "B3": {"fixture": "_baseline_fixture_b3.json",
           "what": "one full epoch with manage passes, acts and a busy store",
           "legs": (("run", _B3, ()),)},
    "B3r": {"fixture": "_baseline_fixture_b3r.json",
            "what": f"B3 saved at window {B3R_SAVE_AT} and continued by CKPT_RESUME",
            "legs": (("parent", dict(_B3, CKPT_DIR="{tmp}/p"), ("--max-windows", str(B3R_SAVE_AT))),
                     ("child", dict(_B3, CKPT_RESUME="{tmp}/p", CKPT_DIR="{tmp}/c"), ()))},
    "B5": {"fixture": "_baseline_fixture_b5.json",
           "what": "DATA_SOURCE=real, 200 windows",
           "legs": (("run", dict(COMMON, DATA_SOURCE="real", DATA_STREAM_BYTES="120000"),
                     ("--max-windows", "200")),)},
}
# THE PLANTED CHANGES --mutants must see fail: a cull that waits one more selection, and a held-out
# block one percentage point of each corpus larger.
MUTANTS = (("B3", {"FAB_GRACE": "3"}), ("B5", {"DATA_HOLDOUT_FRAC": "0.06"}))
# A counter line: indented, a dotted name, then an integer and nothing else.
COUNTER = re.compile(r"^ {5,}([a-z_][a-z0-9_]*(?:\.[a-z0-9_:]+)+) +(-?\d+)$")


def machine_key():
    import torch
    return {"platform": platform.platform(), "python": platform.python_version(),
            "torch": torch.__version__, "cpu_count": os.cpu_count(), "threads": COMMON["OMP_NUM_THREADS"]}


def commit():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def trace(env, args, tmp, tag="run"):
    """Run run.py once; return (loss curve as float reprs, {counter: int})."""
    # A CLEAN environment: a lever exported in the caller's shell would otherwise change the workload.
    clean = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG", "PYTHONPATH")}
    clean.update({k: v.replace("{tmp}", tmp) for k, v in env.items()})
    curve_path = os.path.join(tmp, f"curve_{tag}.json")
    proc = subprocess.run([sys.executable, "run.py", *args, "--quiet", "--loss-curve", curve_path],
                          cwd=ROOT, env=clean, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"FAIL  run.py exited {proc.returncode} ({tag})\n{proc.stdout[-3000:]}\n"
                         f"{proc.stderr[-3000:]}")
    with open(curve_path, encoding="utf-8") as fh:
        curve = [repr(float(v)) for v in json.load(fh)]
    counters = {}
    for line in proc.stdout.splitlines():
        m = COUNTER.match(line)
        if m:
            counters[m.group(1)] = int(m.group(2))
    return curve, counters


def run_workload(name, overrides=None):
    """Every leg of one workload, in order, in one temporary directory: [{name, env, args,
    loss_curve, counters}]. `overrides` (--mutants) change each leg's environment for this run only;
    the record keeps the table's."""
    legs = []
    with tempfile.TemporaryDirectory(prefix=f"baseline_{name}_") as tmp:
        for leg, env, args in WORKLOADS[name]["legs"]:
            curve, counters = trace(dict(env, **(overrides or {})), args, tmp, tag=leg)
            legs.append({"name": leg, "env": dict(env), "args": list(args), "loss_curve": curve,
                         "counters": counters})
    return legs


def fixture_path(name):
    return os.path.join(ROOT, "tests", WORKLOADS[name]["fixture"])


def fixture_legs(fx):
    """A fixture's legs. B1's record predates legs: one leg named `run`, its windows an argument."""
    if "legs" in fx:
        return fx["legs"]
    return [{"name": "run", "env": fx["env"], "args": ["--max-windows", str(fx["windows"])],
             "loss_curve": fx["loss_curve"], "counters": fx["counters"]}]


def exempt_match(name, patterns):
    return any(fnmatch.fnmatchcase(name, p) for p in patterns)


Compared = collections.namedtuple("Compared", "findings compared added exempted idle")


def compare_counters(want, got, exempt=()):
    """Every fixture counter in `want` against the run's `got`, except those an `exempt` pattern names.
    Returns Compared(findings: ["name: got (fixture want)"], compared: how many were compared, added:
    the run's counters the fixture never had, exempted: [(name, got, want)], idle: the patterns that
    named no fixture counter)."""
    findings, exempted, n = [], [], 0
    for name in sorted(want):
        if exempt_match(name, exempt):
            exempted.append((name, got.get(name), want[name]))
            continue
        n += 1
        if got.get(name) != want[name]:
            findings.append(f"{name}: {got.get(name)} (fixture {want[name]})")
    # A COUNTER THE FIXTURE NEVER HAD IS A NEW INSTRUMENT, NOT A CHANGED RUN: listed, not failed. A
    # fixture counter that moved or vanished is a difference and fails above.
    added = sorted(set(got) - set(want))
    idle = [p for p in exempt if not any(fnmatch.fnmatchcase(k, p) for k in want)]
    return Compared(findings, n, added, exempted, idle)


def compare_curve(want, got):
    """None when the curves are equal, else the finding naming the first differing flush."""
    if got == want:
        return None
    first = next((i for i, (a, b) in enumerate(zip(got, want)) if a != b), min(len(got), len(want)))
    return f"loss curve differs from flush {first} ({len(got)} vs {len(want)} points)"


def compare_workload(name, legs, key, exempt=(), quiet=False):
    """One workload's legs against its fixture: (verdict, findings), the verdict PASS, FAIL or
    UNVERIFIABLE. Prints it unless quiet."""
    path = fixture_path(name)
    if not os.path.exists(path):
        if not quiet:
            print(f"FAIL  {name:<4} no fixture at {path}; record one with --record {name} at the base "
                  f"commit")
        return "FAIL", ["no fixture"]
    with open(path, encoding="utf-8") as fh:
        fx = json.load(fh)
    if fx["machine"] != key:
        if not quiet:
            print(f"UNVERIFIABLE  {name}  the fixture was recorded on {fx['machine']}, this machine is "
                  f"{key}. Nothing was compared. Record a fixture for this machine with --record {name}.")
        return "UNVERIFIABLE", []
    want_legs = fixture_legs(fx)
    findings, lines = [], []
    if [w["name"] for w in want_legs] != [g["name"] for g in legs]:
        findings.append(f"the fixture's legs are {[w['name'] for w in want_legs]}, the table's "
                        f"{[g['name'] for g in legs]}")
    many = len(legs) > 1
    for want, got in zip(want_legs, legs):
        pre = f"{got['name']}: " if many else ""
        if want["env"] != got["env"] or list(want["args"]) != list(got["args"]):
            findings.append(f"{pre}the fixture was recorded with env {want['env']} and arguments "
                            f"{want['args']}; the table now says {got['env']} and {got['args']}. "
                            f"Restore the table, or re-record with --record {name}")
        f = compare_curve(want["loss_curve"], got["loss_curve"])
        if f:
            findings.append(pre + f)
        c = compare_counters(want["counters"], got["counters"], exempt)
        findings += [pre + x for x in c.findings]
        lines.append(f"      {pre}{len(got['loss_curve'])} losses, {c.compared} integer counters "
                     f"compared, {len(c.added)} new" + (" (listed)" if c.added else "")
                     + (f", {len(c.exempted)} exempt (listed)" if c.exempted else ""))
        if c.added:
            lines.append(f"      {pre}new counters since the fixture (not compared): {', '.join(c.added)}")
        if c.exempted:
            lines.append(f"      {pre}exempt (not compared): "
                         + ", ".join(f"{n} {g} (fixture {w})" for n, g, w in c.exempted))
        if exempt and c.idle:
            lines.append(f"      {pre}--exempt pattern(s) that named no fixture counter: "
                         f"{', '.join(c.idle)}")
    verdict = "FAIL" if findings else "PASS"
    if not quiet:
        print(f"{verdict}  {name:<4} {WORKLOADS[name]['what']} reproduces the fixture recorded at "
              f"{fx['commit']}")
        for line in lines:
            print(line)
        for f in findings[:20]:
            print(f"      - {f}")
    return verdict, findings


def continuation(live, key):
    """B3r's derived check: (verdict, detail), verdict one of PASS / FAIL / UNVERIFIABLE. The reference
    is this invocation's B3 when it ran, else B3's fixture when it was recorded on this machine."""
    legs = {leg["name"]: leg["loss_curve"] for leg in live["B3r"]}
    if "B3" in live:
        ref, src = live["B3"][0]["loss_curve"], "this run's B3"
    else:
        path = fixture_path("B3")
        fx = None
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                fx = json.load(fh)
        if fx is None or fx["machine"] != key:
            return "UNVERIFIABLE", "no B3 to continue from: run B3 too, or record its fixture here"
        ref, src = fixture_legs(fx)[0]["loss_curve"], f"B3's fixture recorded at {fx['commit']}"
    p, c = legs.get("parent", []), legs.get("child", [])
    fp, fc = compare_curve(ref[:B3R_SAVE_AT], p), compare_curve(ref[B3R_SAVE_AT:], c)
    ok = fp is None and fc is None and len(p) == B3R_SAVE_AT and len(c) > 0
    detail = (f"the parent's {len(p)} losses against B3's first {B3R_SAVE_AT} and the child's {len(c)} "
              f"against B3's from window {B3R_SAVE_AT} on ({src})")
    if not ok:
        detail += "".join(f"; {w}: {f}" for w, f in (("parent", fp), ("child", fc)) if f)
    return ("PASS" if ok else "FAIL"), detail


def comparator_known_answers():
    """The comparison itself, on planted data: [(name, ok, detail)]. No run.py involved."""
    fx = {"a.b": 1, "eval.x": 2, "lm.encode.calls": 5}
    out = []
    f = compare_curve(["1.0", "2.0", "3.0"], ["1.0", "2.0", "3.5"])
    out.append(("a planted loss change is named at its flush", f is not None and "flush 2" in f, f))
    r = compare_counters(fx, dict(fx, **{"eval.x": 3, "new.one": 1}), ["eval.*"])
    out.append(("--exempt passes a planted bump of an exempt counter and prints it",
                not r.findings and r.exempted == [("eval.x", 3, 2)] and r.compared == 2
                and r.added == ["new.one"], str(r)))
    r = compare_counters(fx, dict(fx, **{"a.b": 2, "eval.x": 3}), ["eval.*"])
    out.append(("--exempt still fails a planted bump of a counter no pattern names",
                r.findings == ["a.b: 2 (fixture 1)"], str(r)))
    r = compare_counters(fx, {k: v for k, v in fx.items() if k != "a.b"})
    out.append(("a fixture counter that vanished fails", r.findings == ["a.b: None (fixture 1)"],
                str(r)))
    ref = [repr(float(i)) for i in range(B3R_SAVE_AT + 30)]
    live = {"B3": [{"name": "run", "loss_curve": ref}],
            "B3r": [{"name": "parent", "loss_curve": ref[:B3R_SAVE_AT]},
                    {"name": "child", "loss_curve": ref[B3R_SAVE_AT:]}]}
    v_exact = continuation(live, None)[0]
    live["B3r"][1]["loss_curve"] = ref[B3R_SAVE_AT:-1] + ["9.5"]
    v_off, d_off = continuation(live, None)
    out.append(("B3r's derived check passes an exact continuation and fails a child that departs at "
                "its last flush", v_exact == "PASS" and v_off == "FAIL" and "flush 29" in d_off,
                f"{v_exact}; {v_off}: {d_off}"))
    return out


def mutants(key):
    """--mutants: each planted change must FAIL its workload's comparison, naming the first differing
    flush. Returns 0 when every one did."""
    ok = True
    for name, env in MUTANTS:
        what = " ".join(f"{k}={v}" for k, v in env.items())
        verdict, findings = compare_workload(name, run_workload(name, env), key, quiet=True)
        if verdict == "UNVERIFIABLE":
            print(f"UNVERIFIABLE  mutant {name} at {what}: the fixture is from another machine, so "
                  f"nothing was compared")
            continue
        named = [f for f in findings if f.startswith("loss curve differs from flush ")]
        good = verdict == "FAIL" and bool(named)
        ok = ok and good
        print(f"{'PASS' if good else 'FAIL'}  mutant {name} at {what} fails its fixture and names the "
              f"first differing flush: {named[0] if named else 'no loss finding'} "
              f"({len(findings) - len(named)} other finding(s) beside it)")
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("workloads", nargs="*", metavar="NAME",
                    help=f"the workloads to run (default: all of {', '.join(WORKLOADS)})")
    ap.add_argument("--record", action="store_true",
                    help="(re)write the named workloads' fixtures instead of comparing")
    ap.add_argument("--exempt", action="append", default=[], metavar="PATTERNS",
                    help="comma-separated fnmatch patterns of fixture counters not to compare")
    ap.add_argument("--mutants", action="store_true",
                    help="run the planted changes that must fail their comparison")
    args = ap.parse_args(argv)
    bad = [n for n in args.workloads if n not in WORKLOADS]
    if bad:
        ap.error(f"unknown workload(s) {bad}; the table has {list(WORKLOADS)}")
    names = [n for n in WORKLOADS if n in args.workloads] or list(WORKLOADS)
    exempt = [p.strip() for a in args.exempt for p in a.split(",") if p.strip()]
    key = machine_key()
    ok = True
    if not args.record:
        for n, good, detail in comparator_known_answers():
            print(f"{'PASS' if good else 'FAIL'}  comparator: {n}" + ("" if good else f" -- {detail}"))
            ok = ok and good
    if args.mutants:
        return mutants(key) if ok else 1
    live = {}
    for name in names:
        live[name] = run_workload(name)
        if not args.record:
            ok = compare_workload(name, live[name], key, exempt)[0] != "FAIL" and ok
    verdict = None
    if "B3r" in live:
        verdict, detail = continuation(live, key)
        print(f"{verdict}  B3r  continues B3 exactly: {detail}")
        ok = ok and verdict != "FAIL"
    if args.record:
        for name in names:
            if name == "B3r" and verdict != "PASS":
                print(f"NOT RECORDED  B3r: its continuation of B3 did not check PASS ({verdict})")
                ok = False
                continue
            legs = live[name]
            with open(fixture_path(name), "w", encoding="utf-8") as fh:
                json.dump({"commit": commit(), "workload": name, "machine": key, "legs": legs}, fh,
                          indent=1, sort_keys=True)
                fh.write("\n")
            print(f"RECORDED  {fixture_path(name)}: "
                  + "; ".join(f"{leg['name']} {len(leg['loss_curve'])} losses, "
                              f"{len(leg['counters'])} integer counters" for leg in legs)
                  + f" at {commit()}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
