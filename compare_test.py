"""Known-answer tests for compare.py.

A statistical decision rule is the one kind of tool you cannot check by looking at its output, because the output
is plausible whatever it does. These cases have answers fixed in advance by construction, so the tool has to
agree with something it cannot see.

The two that matter:
  REAL   an effect of 0.30 buried under 0.35 of SHARED seed noise. Per-arm std comes out larger than the effect
         itself, so an unpaired comparison cannot resolve it and a paired one can. If this stops passing, the
         pairing has broken and every comparison silently loses power.
  NULL   no effect at all, generated so that A wins 4 of 5 seeds anyway. The naive reading calls that a win.
         The correct answer is NOT SIGNIFICANT, and this project has made the naive call repeatedly.

    python3 compare_test.py
"""
import os
import random
import shutil
import sys
import tempfile

import compare

D, V = 16, 50


def _w(d, name, seed, ho, o1=3.742, commit="86fd64a46c", finished=True):
    p = os.path.join(d, name)
    with open(p, "w") as f:
        f.write(f"[build] branch rm-predict | commit {commit} | clean | 2026-08-16 x\n")
        f.write(f"[config] EFFECTIVE  FABRIC=1  SEED={seed}  EPOCHS=18\n")
        if finished:
            f.write(f"  train {ho-0.02:.3f} +/- 0.05 | held-out {ho:.3f} +/- 0.07 | gap +0.02 bits/byte\n")
            f.write(f"    uniform 4.070 | order-0 3.800 | order-1 {o1:.3f} | THIS MODEL {ho:.3f}\n")
    return p


def _run(argv):
    """compare.main writes to stdout; capture it so the assertions can read the verdict."""
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = compare.main(argv)
    return rc, buf.getvalue()


def main():
    d = tempfile.mkdtemp(prefix="cmptest-")
    ok = True
    try:
        rng = random.Random(11)
        # --- REAL: a 0.30 effect under 0.35 of shared seed noise -------------------------------------
        A, B = [], []
        for s in range(5):
            base = rng.gauss(2.2, 0.35)
            A.append(_w(d, f"real_A_seed{s}.log", s, base - 0.30 + rng.gauss(0, 0.08)))
            B.append(_w(d, f"real_B_seed{s}.log", s, base + rng.gauss(0, 0.08)))
        rc, out = _run(A + ["--"] + B)
        if "SIGNIFICANT AND MEANINGFUL" not in out:
            print("!! REAL effect not detected -- pairing has stopped working:\n" + out); ok = False
        else:
            # the demonstration itself: per-arm spread should EXCEED the effect it is hiding
            # The demonstration itself, asserted rather than admired: the per-arm spread must EXCEED the
            # effect it is hiding, and the paired difference must not. If that stops holding, this case no
            # longer shows why pairing matters and the assertion above is passing for a weaker reason.
            import re
            arm = [float(m) for m in re.findall(r"n=\d+  mean [\d.]+  std ([\d.]+)", out)]
            pair = [float(m) for m in re.findall(r"std of the paired difference ([\d.]+)", out)]
            if len(arm) < 2 or len(pair) < 1:
                print(f"!! could not read the std lines out of compare.py's output; the format moved:\n{out}")
                ok = False
            elif not (min(arm) > 0.30 and pair[0] < 0.30):
                print(f"!! the REAL case no longer demonstrates what it exists to demonstrate "
                      f"(per-arm stds {arm}, paired {pair[0]}); regenerate it."); ok = False
            else:
                print(f"  REAL   -> SIGNIFICANT AND MEANINGFUL  (per-arm std {arm[0]:.3f}/{arm[1]:.3f} both "
                      f"above the 0.30 effect; paired-difference std {pair[0]:.3f} below it)")

        # --- NULL: no effect, but A happens to win most seeds ----------------------------------------
        A, B = [], []
        for s in range(5):
            base = rng.gauss(2.2, 0.35)
            A.append(_w(d, f"null_A_seed{s}.log", s, base + rng.gauss(0, 0.08)))
            B.append(_w(d, f"null_B_seed{s}.log", s, base + rng.gauss(0, 0.08)))
        rc, out = _run(A + ["--"] + B)
        if "NOT SIGNIFICANT" not in out:
            print("!! NULL case was called significant -- the tool now finds effects that are not there:\n" + out)
            ok = False
        else:
            print(f"  NULL   -> NOT SIGNIFICANT")

        # --- TOO FEW PAIRS: must refuse a verdict, not manufacture one -------------------------------
        # The first real use of this tool was a 1-seed bisect, and it answered "SIGNIFICANT AND MEANINGFUL"
        # with a CI of [1.000, 1.000] -- because a bootstrap over one pair resamples that pair every time.
        # Wrapping a single comparison in statistical language is worse than not having the tool.
        for n in (1, 2):
            A = [_w(d, f"few{n}_A_seed{s}.log", s, 2.0) for s in range(n)]
            B = [_w(d, f"few{n}_B_seed{s}.log", s, 2.3) for s in range(n)]
            rc, out = _run(A + ["--"] + B)
            if "NO VERDICT" not in out or "SIGNIFICANT AND MEANINGFUL" in out:
                print(f"!! n={n} produced a verdict it cannot support:\n{out}"); ok = False
            else:
                print(f"  FEW    n={n} pair(s) -> NO VERDICT (direction reported, significance refused)")
        # ...and at the floor it must start answering again.
        A = [_w(d, f"ok3_A_seed{s}.log", s, 2.0) for s in range(3)]
        B = [_w(d, f"ok3_B_seed{s}.log", s, 2.3) for s in range(3)]
        rc, out = _run(A + ["--"] + B)
        if "NO VERDICT" in out:
            print(f"!! n=3 still refuses; the floor is too high to ever be useful:\n{out}"); ok = False
        else:
            print(f"  FEW    n=3 pairs  -> verdict issued")

        # --- FLAGS AFTER THE SEPARATOR: natural to type, and it used to read them as filenames --------
        A = [_w(d, "fl_A_seed0.log", 0, 2.0)]; B = [_w(d, "fl_B_seed0.log", 0, 2.3)]
        rc, out = _run(A + ["--"] + B + ["--label-a", "LEFT", "--label-b", "RIGHT"])
        if "LEFT" not in out or "RIGHT" not in out or "has no held-out line" in out:
            print(f"!! flags after the -- were mistaken for log paths:\n{out}"); ok = False
        else:
            print(f"  ARGS   flags after the -- are parsed as flags")

        # --- SIGN: an arm that loses every seed must not be reported as winning ----------------------
        # Taken verbatim from a real ladder rung. LR=4e-3 lost to 2e-3 on all three seeds -- P(A better)=0.000,
        # CI [0.000, 0.000] -- and the tool printed "4e-3 wins more often than chance", because it tested
        # `hi <= gamma` before establishing which side of 0.5 the interval was on. A decision rule that can
        # invert its own sign is worse than none, since the output still reads like an answer.
        A = [_w(d, f"sgn_A_seed{i}.log", i, v) for i, v in enumerate((2.098, 2.105, 2.162))]
        B = [_w(d, f"sgn_B_seed{i}.log", i, v) for i, v in enumerate((2.039, 2.103, 2.039))]
        rc, out = _run(A + ["--"] + B + ["--label-a", "hi", "--label-b", "lo"])
        if "hi is ahead" in out or "hi is better" in out:
            print(f"!! the losing arm was reported as winning -- sign inversion is back:\n{out}"); ok = False
        elif "lo is better" not in out:
            print(f"!! neither arm was named the winner on a clean sweep:\n{out}"); ok = False
        else:
            print(f"  SIGN   arm losing 3/3 -> the OTHER arm is named the winner")
        # ...and the mirror: the winning arm on the left must still be called correctly.
        rc, out = _run(B + ["--"] + A + ["--label-a", "lo", "--label-b", "hi"])
        if "lo is better" not in out:
            print(f"!! the winning arm on the left was not named:\n{out}"); ok = False
        else:
            print(f"  SIGN   arm winning 3/3 on the left -> named correctly")

        # --- GUARDS: each must warn, and none may crash ----------------------------------------------
        for label, mk, want in (
            ("different commits",
             lambda: ([_w(d, f"cm_A_seed{s}.log", s, 2.0) for s in range(3)],
                      [_w(d, f"cm_B_seed{s}.log", s, 2.1, commit="deadbeef99") for s in range(3)]),
             "DIFFERENT COMMITS"),
            ("different corpora",
             lambda: ([_w(d, f"co_A_seed{s}.log", s, 2.0, o1=3.440) for s in range(3)],
                      [_w(d, f"co_B_seed{s}.log", s, 2.1, o1=3.747) for s in range(3)]),
             "different corpora"),
            ("disjoint seeds",
             lambda: ([_w(d, "dj_A_seed0.log", 0, 2.0)], [_w(d, "dj_B_seed7.log", 7, 2.1)]),
             "UNPAIRED"),
            ("unfinished run",
             lambda: ([_w(d, "un_A_seed9.log", 9, 0, finished=False), _w(d, "un_A_seed0.log", 0, 2.0)],
                      [_w(d, "un_B_seed0.log", 0, 2.1)]),
             "did not reach its report"),
        ):
            a, b = mk()
            try:
                rc, out = _run(a + ["--"] + b)
            except Exception as e:
                print(f"!! guard '{label}' CRASHED ({type(e).__name__}: {e})"); ok = False; continue
            if want not in out:
                print(f"!! guard '{label}' did not warn (expected {want!r}):\n{out}"); ok = False
            else:
                print(f"  GUARD  {label:20s} -> warned")
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print("\nok -- compare.py agrees with every known answer." if ok else "\n!! FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
