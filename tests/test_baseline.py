"""BASELINE FIXTURE: an 80-window run.py trace, stored, so "bit-identical when the new mechanism is off"
is checked against a recorded run rather than asserted against nothing.

WHY THIS FILE EXISTS (Proposal 03 §0 R7, 03b S0b). tests/test_determinism.py measures the machine's noise
floor between two runs of the SAME tree; it holds no record of an earlier tree. Every stage of 03b
(S0b's mid-epoch act first) promises that a default run with the new mechanism disarmed reproduces the
tree it started from. That promise needs a stored trace from the base commit.

WHAT IS STORED. `python3 run.py --max-windows 80` at RUN_DEVICE=cpu, DATA_STREAM_BYTES=120000, one
thread, the shipped defaults otherwise:
  - the per-flush loss curve, as exact float reprs (a trace, compared exactly: same machine, same build);
  - every integer counter line the run prints (the INTEGER channel of test_determinism's vocabulary).
The float curve is compared exactly because the reference is this machine's own earlier run of the
same workload; test_determinism records that this workload is bit-reproducible here.

A FIXTURE IS A PER-MACHINE RECORD. It carries the machine key (platform, torch version, cpu count,
threads). On another machine the comparison is UNVERIFIABLE and this file says so and exits 0 -- it does
not pass a comparison it could not make, and it does not fail a box it was never recorded on. Record one
there with --record.

Run from the repository root:
    python3 tests/test_baseline.py            compare against tests/_baseline_fixture.json
    python3 tests/test_baseline.py --record   (re)write the fixture; commit it with the commit it names
Exit 0 = matched (or unverifiable on this machine, printed as such); 1 = a difference, named.
"""
import json
import os
import platform
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(ROOT, "tests", "_baseline_fixture.json")
WINDOWS = 80
ENV = {"RUN_DEVICE": "cpu", "DATA_STREAM_BYTES": "120000", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
# A counter line: indented, a dotted name, then an integer and nothing else.
COUNTER = re.compile(r"^ {5,}([a-z_][a-z0-9_]*(?:\.[a-z0-9_:]+)+) +(-?\d+)$")


def machine_key():
    import torch
    return {"platform": platform.platform(), "python": platform.python_version(),
            "torch": torch.__version__, "cpu_count": os.cpu_count(), "threads": ENV["OMP_NUM_THREADS"]}


def commit():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def trace():
    """Run the workload once; return (loss curve as float reprs, {counter: int})."""
    # A CLEAN environment: a lever exported in the caller's shell would otherwise change the workload.
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG", "PYTHONPATH")}
    env.update(ENV)
    with tempfile.TemporaryDirectory() as tmp:
        curve_path = os.path.join(tmp, "curve.json")
        proc = subprocess.run([sys.executable, "run.py", "--max-windows", str(WINDOWS), "--quiet",
                               "--loss-curve", curve_path], cwd=ROOT, env=env, capture_output=True, text=True)
        if proc.returncode != 0:
            raise SystemExit(f"FAIL  run.py exited {proc.returncode}\n{proc.stdout[-3000:]}\n{proc.stderr[-3000:]}")
        with open(curve_path, encoding="utf-8") as fh:
            curve = [repr(float(v)) for v in json.load(fh)]
    counters = {}
    for line in proc.stdout.splitlines():
        m = COUNTER.match(line)
        if m:
            counters[m.group(1)] = int(m.group(2))
    return curve, counters


def main():
    record = "--record" in sys.argv[1:]
    curve, counters = trace()
    key = machine_key()
    if record:
        with open(FIXTURE, "w", encoding="utf-8") as fh:
            json.dump({"commit": commit(), "windows": WINDOWS, "env": ENV, "machine": key,
                       "loss_curve": curve, "counters": counters}, fh, indent=1, sort_keys=True)
            fh.write("\n")
        print(f"RECORDED  {FIXTURE}: {len(curve)} losses, {len(counters)} integer counters at {commit()}")
        return 0
    if not os.path.exists(FIXTURE):
        print(f"FAIL  no fixture at {FIXTURE}; record one with --record at the base commit")
        return 1
    with open(FIXTURE, encoding="utf-8") as fh:
        fx = json.load(fh)
    if fx["machine"] != key:
        print(f"UNVERIFIABLE  the fixture was recorded on {fx['machine']}, this machine is {key}. "
              f"Nothing was compared. Record a fixture for this machine with --record.")
        return 0
    findings = []
    if curve != fx["loss_curve"]:
        first = next((i for i, (a, b) in enumerate(zip(curve, fx["loss_curve"])) if a != b),
                     min(len(curve), len(fx["loss_curve"])))
        findings.append(f"loss curve differs from flush {first} "
                        f"({len(curve)} vs {len(fx['loss_curve'])} points)")
    for name in sorted(set(counters) | set(fx["counters"])):
        got, want = counters.get(name), fx["counters"].get(name)
        if got != want:
            findings.append(f"{name}: {got} (fixture {want})")
    ok = not findings
    print(f"{'PASS' if ok else 'FAIL'}  B1  run.py --max-windows {WINDOWS} reproduces the fixture recorded "
          f"at {fx['commit']}")
    print(f"      {len(curve)} losses, {len(counters)} integer counters compared")
    for f in findings[:20]:
        print(f"      - {f}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
