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
