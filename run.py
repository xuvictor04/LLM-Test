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

WHAT THIS RUN MEASURES. Goal A's core -- a language model routed through the fabric, trained by the
optimizer on the corpus DATA draws -- and, since every one of LOOP_ORDER's B rows acquired a call
site, the mechanisms goal B is made of: the fabric GROWS, memory is WRITTEN and maintained, and the
vocabulary MINTS with LM.on_mint initialising each new row from its parents.

WHAT IT STILL DOES NOT MEASURE, AND THE RUN PRINTS BOTH LISTS RATHER THAN CLAIMING OTHERWISE:
  * A CALL SITE IS NOT A CALL. Three B rows stand behind events -- TOK.mint_burst behind Due.mint,
    LM.residual_ratios and TOK.judge_probation behind Due.probation -- and the probation family is
    UNREACHABLE at the shipped TOK_PROBATION_USES=0. The GATED CALL SITES block says which of the
    three states each one is in, read off the counter the owning package keeps.
  * THE RETOK IS DEFERRED TO THE EPOCH ROLL, NOT PERFORMED MID-EPOCH. Re-segmenting changes how
    many windows an epoch holds and RunClock.begin_epoch cannot be told a new length without
    zeroing the epoch cursor, so the act waits for the next roll -- which re-segments anyway. AT
    RUN_EPOCHS=1 NO ROLL EVER REACHES IT, because the single roll a one-epoch run takes is the one
    that also finishes it; every retok that run raises lands in tok.due_dropped with a warning
    naming why. Recorded as Q-RUN-8, with the measurement that settles it.
  * NO EXPERT IS EVER CULLED and THE SIGNATURE ENCODER NEVER LEARNS. FAB.manage and SIG.train_step
    are the last two LOOP_ORDER rows without bodies, so the population only ever rises and every
    routing and domain decision for the whole run is taken on the warm-up encoder. Their cadences
    are deliberately NOT ASKED rather than asked-and-ignored: an asked gate records its fire.
  * FIVE ENTRY POINTS ARE DEFERRED BY THE CONTRACT, not merely unwritten -- CAP.observe,
    FAB.contribution, MEM.blend, MEM.judge and WORLD.manage. CAP.observe's absence is why no cap is
    ever lifted; FAB.contribution's is why the marginal-contribution counterfactual has no producer.

WHAT CHANGED ON 2026-09-21/22, because several sentences above used to say the opposite: DOM.observe,
MEM.read and MEM.census have bodies and are called, so the partition assigns real ids, the store
retrieves and promotes, and growth's memory-pressure leg has a producer. Stage E is driven, so at
RUN_EPOCHS>1 the stream is redrawn and RE-SEGMENTED -- which is the only route by which a token this
run minted can appear in this run's own training data.
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

    # THE DATA PLAN'S GATES, BEFORE A BYTE IS TRAINED ON, WHICH IS THE ONLY MOMENT THEY ARE FOR.
    # DATA_EXPOSURE_MAX is declared as the "whole-run repetition multiple ... above which the data
    # plan is FLAGGED BEFORE TRAINING STARTS", and DATA.plan computes it correctly and hands it back
    # on Plan.gates -- where NOTHING READ IT. `grep -n '\.plan\b' src/spine/loop.py run.py` returned
    # nothing until this line, so the flag was raised into a record no caller opened.
    # THAT IS HALF A PORT REQUIREMENT, DONE AND STOPPED. data/levers.py::DATALevers.exposure_max
    # records that the old tree's two reads sat inside `if DATA_MODE == "real" and NP > 1`, so the
    # check "is unavailable on exactly the single-area configuration goal A runs in -- which is
    # where accidental repetition is EASIEST to reach", and asks for two things: "move the read out
    # of the NP>1 guard, AND print the arithmetic as a declared Gate (G4) so 'did not fire' is
    # distinguishable from 'could not fire'". The move happened. The printing did not, and the
    # lever's own closing sentence is what that leaves behind: "A guard that cannot trip reads
    # exactly like a healthy run" -- and so does one that trips where nobody is looking.
    # MEASURED THE DAY THIS LINE WAS WRITTEN, at DATA_SOURCE=real with a 50 MB stream over the
    # corpus in the tree: exposure py=22.4x, num=13.9x, c=5.5x, eng=3.3x against a declared bound of
    # 2.0, with data.exposure_max FIRED at 22.3953 and data.exposure_skew FIRED at 6.8082. A run
    # reading one corpus twenty-two times is not a run on 50 MB of text, and every bits-per-byte
    # number it produces is measured against material the model has already seen.
    print(f"=== data plan: protocol={sysm.plan.protocol}, per-area whole-run exposure "
          f"(bytes drawn x epochs / bytes on disk):")
    for _a in sorted(sysm.plan.exposure):
        print(f"      {_a:<12} {sysm.plan.exposure[_a]:.2f}x")
    for _g in sysm.plan.gates:
        _state = ("FIRED" if _g.fired else "armed, did not fire") if _g.reachable else "unreachable"
        print(f"      Gate {_g.name}: {_state} ({_g.value} vs {_g.threshold})")
        if _g.fired and _g.reason:
            print(f"        {_g.reason}")

    result = loop.run(sysm, max_windows=args.max_windows, progress=not args.quiet)

    print()
    print(f"=== {result.windows} windows, {result.flushes} flushes, "
          f"{result.opt_steps} optimizer steps, {result.epochs} epoch(s) "
          f"in {result.elapsed_s:.1f}s ({result.windows / max(result.elapsed_s, 1e-9):.1f} w/s)")
    print(f"=== loss {result.loss_first:.4f} -> {result.loss_last:.4f}")
    # THE PRECISION ASKED FOR AND THE PRECISION OBSERVED, ON ONE LINE, BECAUSE THEY DISAGREED FOR
    # THE LIFE OF THIS DRIVER. amp_state above is what RUN.process_setup decided; this is the dtype
    # of the tensor the step actually produced. RUN_AMP=bf16 printed "active" and ran fp32 until
    # 2026-09-21, and the only thing that could have caught it was a reading from inside the step.
    print(f"=== amp asked={p.amp_state} observed step dtype={sysm.process_dtype}")
    # WHAT THE CARD ACTUALLY HELD, on the runs where there is a card. A throughput number without
    # a memory figure cannot answer "would a bigger batch or a wider model fit", which is the first
    # question anyone asks of a GPU run -- and on this tree it is the question, because the step is
    # LAUNCH-bound rather than compute-bound and the honest way to use a big card is to make each
    # launch do more work rather than to make more launches.
    # max_memory_allocated AND NOT memory_allocated: the peak is what has to fit, and the value at
    # the end of a run is whatever survived the last free.
    if str(p.device).startswith("cuda"):
        import torch
        print(f"=== peak CUDA memory {torch.cuda.max_memory_allocated() / 2**30:.3f} GiB "
              f"allocated, {torch.cuda.max_memory_reserved() / 2**30:.3f} GiB reserved")
    print(f"=== {len(result.skipped)} MECHANISM(S) ON LOOP_ORDER HAVE NO CALL SITE AT ALL:")
    for s in result.skipped:
        print(f"      - {s}")
    # AND THE GATED ONES, SEPARATELY, BECAUSE "IT HAS A CALL SITE" IS NOT "IT RAN". Three of the
    # twenty-one B rows stand behind events that are UNREACHABLE at the shipped defaults --
    # TOK_PROBATION_USES=0 turns the whole probation family off -- so a report that printed "0 not
    # called" and stopped would say this run judged probation when nothing did. That is the same
    # overstatement the skipped list itself was written to repair, one layer in.
    print("=== GATED CALL SITES (a call site is not a call):")
    for g in result.gated:
        print(f"      - {g}")
    # THE R STAGE. LOOP_ORDER's last block, and nothing ran it until 2026-09-21: a 53-minute run
    # printed a loss curve and said nothing about whether an expert had been born, a token minted
    # or an entry written. Rendered through each package's own counters entry point, so a row reads
    # `fired N` / `armed but 0` / `unreachable (<predicate>)` rather than a bare integer.
    print("=== R STAGE -- the did-it-fire surfaces:")
    for row, body in result.report.items():
        print(f"    -- {row}")
        if isinstance(body, dict):
            for k in sorted(body):
                print(f"       {k:<44} {body[k]}")
        elif isinstance(body, (tuple, list)):
            for line in body:
                print(f"       {line}")
        else:
            print(f"       {body}")
    print("=== cadence ledger (checks=0 means the gate was never evaluated, which is a different "
          "fact from fires=0):")
    for k, v in sorted(result.cadence_ledger.items()):
        print(f"      {k:<12} checks={v[0]:<6} fires={v[1]:<5} period={v[3]}")
    for w in result.warnings[len(sysm.warnings):]:
        print(f"WARNING: {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
