#!/usr/bin/env python3
"""Run one training run. `PYTHONPATH=src python run.py [--max-windows N]`.

EVERY KNOB IS AN ENVIRONMENT VARIABLE AND THERE ARE NO FLAGS FOR THEM. That is the spine's rule,
not this script's convenience: spine/lever.py generates every environment name as PREFIX_FIELD and
only spine/lever.py names os.environ, so a flag here would be a second source for a value the
frozen Config already holds -- and whichever of the two a report quoted would be a coin flip.
`--max-windows` is the one exception and it is NOT a lever: it is the driver argument
spine/loop.py::run documents, it cannot lengthen a run, and a run that stops because of it says so
in its own warnings.

    PYTHONPATH=src python run.py                      # the shipped defaults
    PYTHONPATH=src RUN_DEVICE=cuda python run.py      # on a GPU
    PYTHONPATH=src DATA_STREAM_BYTES=50000000 RUN_EPOCHS=1 RUN_DEVICE=cuda python run.py

WHAT THIS RUN MEASURES AND WHAT IT DOES NOT. It trains a language model routed through the fabric,
on the corpus DATA draws -- goal A's core. It does NOT measure goal B: eleven entry points on
LOOP_ORDER's B row are still stubs, so the fabric does not grow, memory is never written, the
vocabulary never mints and no domain is ever scored. The run PRINTS that list before it starts,
because a report that omits it is indistinguishable from a run where those mechanisms were armed
and did nothing.
"""
import argparse
import os
import sys

# THE REPOSITORY ROOT MUST NOT BE ON sys.path BEFORE src/, AND THIS IS NOT DEFENSIVENESS.
# Python puts a script's own directory FIRST, and this repository's root still carries the frozen
# old tree's `memory.py` -- so `import memory.levers` finds that module instead of src/memory/ and
# dies with "No module named 'memory.levers'; 'memory' is not a package", from inside
# spine/assemble.py, before any of this file's own code runs. Measured: that is exactly what
# `PYTHONPATH=src python run.py` did on the first attempt.
# THE FROZEN TREE STAYS WHERE IT IS -- it is the evidence every docstring in src/ cites by line
# number -- so the fix is here, at the one entry point that has to coexist with it.
_ROOT = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_ROOT, "src")
sys.path[:] = [p for p in sys.path if os.path.abspath(p or ".") != _ROOT]
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from spine.compose import compose          # noqa: E402 -- after the path repair above, on purpose
from spine import loop                     # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--max-windows", type=int, default=None,
                    help="stop after N windows. A DRIVER argument, not a lever: it cannot make a "
                         "run longer, and a run stopped by it says so in its warnings.")
    ap.add_argument("--quiet", action="store_true", help="suppress the progress line")
    args = ap.parse_args(argv)

    # THE CALLER OWNS THE ENVIRONMENT, which is compose()'s own first line: `system =
    # compose(environ=os.environ)`. Passing it explicitly rather than letting anything reach for it
    # is what keeps the resolved Config the single source for every knob.
    sysm = compose(environ=os.environ)

    # WHAT HARDWARE AND WHAT ARITHMETIC, PRINTED BEFORE ANYTHING ELSE. A run that does not say
    # which device it used is a run whose throughput number means nothing and whose loss curve
    # cannot be compared with another's -- and this script did not say it until 2026-09-17, when a
    # GPU smoke came back 5x faster than CPU and the only way to tell a real cuda run from a silent
    # fallback was to reason about process_setup's source.
    # THERE IS NO SILENT FALLBACK TO FALL BACK TO, which is worth printing precisely because it is
    # the thing a reader would otherwise have to check: RUN.process_setup takes `device =
    # str(run.device)` verbatim, with no torch.cuda.is_available() guard, so RUN_DEVICE=cuda on a
    # machine without CUDA RAISES at the first .to() rather than quietly training on the CPU.
    p = sysm.process
    n_params = sum(int(t.numel()) for t in sysm.base_params)
    print(f"=== device={p.device} amp={p.amp_state} tf32={p.tf32_applied} "
          f"torch_seed={p.torch_seed}")
    if p.amp_reason:
        print(f"===   amp: {p.amp_reason}")
    print(f"=== {n_params} trainable parameter(s) in the base group")
    # SEEDS DO NOT CROSS DEVICES, AND A READER COMPARING TWO CURVES NEEDS TO KNOW IT. torch's CUDA
    # generator and its CPU generator produce different draws from the SAME seed, so a cuda run and
    # a cpu run at one RUN_SEED start from different weights -- measured, 8.3784 against 8.3247 on
    # the first flush of otherwise identical 20-window runs. That is not a defect and it is not
    # noise: it means a cpu curve and a cuda curve are two experiments, not two samples of one.
    print(f"=== composed: stage={sysm.stage}, {len(sysm.refusals)} refusal(s), "
          f"{len(sysm.warnings)} warning(s)")
    for r in sysm.refusals:
        print(f"REFUSED: {r}")
    if sysm.refusals:
        # REFUSALS STOP THE RUN BEFORE A TENSOR IS TRAINED. They are the guards a Lever declaration
        # cannot express, and every one of them names the lever to change.
        print("=== refusing to run: fix the above, or change the configuration.")
        return 2
    for w in sysm.warnings:
        print(f"WARNING: {w}")

    result = loop.run(sysm, max_windows=args.max_windows, progress=not args.quiet)

    print()
    print(f"=== {result.windows} windows, {result.flushes} flushes, "
          f"{result.opt_steps} optimizer steps, {result.epochs} epoch(s) "
          f"in {result.elapsed_s:.1f}s ({result.windows / max(result.elapsed_s, 1e-9):.1f} w/s)")
    print(f"=== loss {result.loss_first:.4f} -> {result.loss_last:.4f}")
    print(f"=== {len(result.skipped)} MECHANISM(S) ON LOOP_ORDER WERE NOT CALLED:")
    for s in result.skipped:
        print(f"      - {s}")
    print("=== cadence ledger (checks=0 means the gate was never evaluated, which is a different "
          "fact from fires=0):")
    for k, v in sorted(result.cadence_ledger.items()):
        print(f"      {k:<12} checks={v[0]:<6} fires={v[1]:<5} period={v[3]}")
    for w in result.warnings[len(sysm.warnings):]:
        print(f"WARNING: {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
