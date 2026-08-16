"""Does the difference between two arms mean anything?

Every architecture claim in this project was made by comparing two numbers. The seed spread on a single arm has
reached 1.227 b/B, and post-fix arm spreads still range 0.047 to 1.225 depending on the ARM -- so "A got 2.01 and
B got 2.09, therefore A is better" has been wrong here more often than it has been right. `05_ERRORS.md` INV-35
voids every single-run architecture comparison in the branch on exactly this ground.

This computes the decision rule from Bouthillier et al., "Accounting for Variance in Machine Learning Benchmarks"
(MLSys 2021, arXiv:2103.03098), which their Figure 6 measures against the two things done here instead:

    criterion                     false positives   false negatives
    single-point comparison             ~10%              ~75%
    mean difference, k=50                <5%              ~90%
    P(A>B) with gamma=0.75               ~5%              ~30%

Comparing means is not the safe conservative choice it looks like -- at k=50 it misses ~90% of real effects.

WHAT IT DOES
  - pairs runs by SEED, because paired runs share their data order and initialisation and the std of the paired
    difference is <= the sum of the two arms' stds. Pairing costs nothing and is worth more here than anywhere
    else, since two arms of this system differ by one knob and share all the rest of their machinery.
  - reports P(A better than B) with a percentile-bootstrap confidence interval,
  - and applies the three-way verdict: not significant / significant but not meaningful / significant and
    meaningful. "Not significant" is a real answer and the most common correct one at these sample sizes.
  - reports the paired seeds needed to resolve the observed effect (Noether), so the next run is budgeted from a
    measurement rather than from optimism.

LOWER IS BETTER throughout: the metric is bits/byte, so "A > B" means A scored LOWER than B.

    python3 compare.py runs/seeds/armA_seed*.log -- runs/seeds/armB_seed*.log
    python3 compare.py --metric held_out --label-a nofloor --label-b floor A*.log -- B*.log
"""
import argparse
import glob
import math
import os
import random
import re
import sys

GAMMA = 0.75          # Bouthillier's meaningfulness threshold
ALPHA, BETA = 0.05, 0.20
BOOT = 10000
# BELOW THIS MANY PAIRS THERE IS NO VERDICT TO GIVE, and saying so is the entire point of this file.
# A percentile bootstrap resamples the pairs it was given: at n=1 every resample IS that pair, so the interval
# collapses to a point and the tool reports [1.000, 1.000] -- "significant and meaningful" from ONE run. That is
# strictly worse than eyeballing two numbers, because it wraps a single comparison in the language of statistics.
# Caught on the first real use, on a genuine 1-seed bisect. n=3 is the floor at which a bootstrap has anything
# to resample; even there the interval is wide and it will usually, correctly, refuse to call anything.
MIN_PAIRS = 3


def _grab(pat, t, default=None):
    m = re.search(pat, t, re.M)
    return m.group(1) if m else default


def read_log(path):
    """One run -> {seed, held_out, train, order1, ...}. Parsed with the same patterns as runs.py; if that file's
    regexes move, these must move with them or the two tools will disagree about what a log says."""
    try:
        t = open(path, errors="replace").read()
    except OSError as e:
        # `name` IS REQUIRED even here. The caller reports unusable inputs by name, so a branch that omits it
        # turns "I could not read this file" into a KeyError traceback -- which is exactly what an unreadable
        # path did, and the real cause (a flag mistaken for a path) was invisible behind it.
        return {"path": path, "name": os.path.basename(path), "error": str(e), "done": False}
    row = {"path": path, "name": os.path.basename(path)}
    eff = _grab(r"^\[config\] EFFECTIVE(.*)$", t, "") or ""
    row["seed"] = _grab(r"\bSEED=(\d+)", eff) or _grab(r"_seed(\d+)", os.path.basename(path))
    row["held_out"] = _grab(r"train [\d.]+(?: \+/- [\d.]+)? \| held-out ([\d.]+)", t)
    row["train"] = _grab(r"train ([\d.]+)(?: \+/- [\d.]+)? \| held-out", t)
    row["order1"] = _grab(r"order-1 ([\d.]+) \|", t)
    row["commit"] = _grab(r"^\[build\] branch \S+ \| commit (\w+)", t)
    row["dirty"] = "DIRTY" in (_grab(r"^(\[build\].*)$", t) or "")
    # DELTA-ORDER-1 is the only column comparable across corpora (see notes/04_RESULTS.md): the corpus was
    # re-fetched mid-project and order-1 moved 3.440 -> 3.747, so raw held-out is not comparable down the table.
    for k in ("held_out", "train", "order1"):
        row[k] = float(row[k]) if row[k] else None
    row["d_order1"] = (row["order1"] - row["held_out"]) if (row["order1"] and row["held_out"]) else None
    row["seed"] = int(row["seed"]) if row["seed"] is not None else None
    row["done"] = row["held_out"] is not None
    return row


def _mean(xs): return sum(xs) / len(xs)


def _std(xs):
    if len(xs) < 2: return float("nan")
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def _phi_inv(p):
    """Inverse normal CDF (Acklam's rational approximation). Only needed for the two fixed quantiles below."""
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00]
    pl, ph = 0.02425, 1 - 0.02425
    if p < pl:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > ph:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def p_a_better(pairs):
    """P(A > B) in Bouthillier's sense, on a lower-is-better metric: the fraction of pairs where A scored lower.
    Ties count as half, so a metric that cannot separate two arms lands at exactly 0.5 rather than at 0 or 1."""
    wins = sum(1.0 if a < b else 0.5 if a == b else 0.0 for a, b in pairs)
    return wins / len(pairs)


def bootstrap_ci(pairs, k=BOOT, lo=2.5, hi=97.5, rng=None):
    """Percentile bootstrap over the PAIRS -- resampling pairs, not the two arms independently, is what keeps the
    pairing in the interval."""
    rng = rng or random.Random(12345)          # fixed: a confidence interval that moves when you rerun the
    n = len(pairs)                             # ANALYSIS is its own kind of irreproducibility
    ps = []
    for _ in range(k):
        samp = [pairs[rng.randrange(n)] for _ in range(n)]
        ps.append(p_a_better(samp))
    ps.sort()
    return ps[max(0, int(lo / 100 * k) - 1)], ps[min(k - 1, int(hi / 100 * k))]


def seeds_needed(p, alpha=ALPHA, beta=BETA, gamma=GAMMA):
    """Noether's sample size for the P(A>B) test (Bouthillier Appendix C.3). Returns None when the observed
    P is at 0.5 -- no sample size resolves an effect the instrument says is not there."""
    if abs(p - 0.5) < 1e-9: return None
    return int(math.ceil(((_phi_inv(1 - alpha) - _phi_inv(beta)) / (math.sqrt(6) * abs(0.5 - gamma))) ** 2 /
                         max(1e-9, (abs(p - 0.5) / abs(gamma - 0.5)) ** 2)))


def describe(label, rows, metric):
    xs = [r[metric] for r in rows if r.get(metric) is not None]
    if not xs: return f"  {label:10s} no usable runs"
    return (f"  {label:10s} n={len(xs)}  mean {_mean(xs):.3f}  std {_std(xs):.3f}  "
            f"min {min(xs):.3f}  max {max(xs):.3f}  range {max(xs)-min(xs):.3f}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--metric", default="held_out",
                    help="held_out (default) | d_order1 (comparable across corpora) | train")
    ap.add_argument("--label-a", default="A"); ap.add_argument("--label-b", default="B")
    ap.add_argument("--gamma", type=float, default=GAMMA)
    # SPLIT ON `--` BEFORE argparse SEES IT. argparse treats a bare `--` as its own end-of-options marker and
    # removes it, so a positional list can never contain the separator -- the first version of this errored out
    # with "could not find the --" on a command line that plainly had one.
    raw = list(argv if argv is not None else sys.argv[1:])
    if "--" not in raw:
        ap.error("give arm A's logs, then --, then arm B's:  compare.py A*.log -- B*.log")
    _i = raw.index("--")
    left, right = raw[:_i], raw[_i + 1:]

    # FLAGS ON EITHER SIDE OF THE SEPARATOR. The first version required them before the `--`, which is not how
    # anyone types it -- `compare.py A*.log -- B*.log --label-a x` reads naturally and silently handed
    # "--label-a" and "x" to the log reader as filenames. Splitting each side into (paths, flags) and parsing the
    # flags together means the separator only ever separates ARMS, which is the only job it has.
    def _sides(tokens):
        _ns, paths = ap.parse_known_args(tokens)
        return paths, [t for t in tokens if t not in paths]
    pa, fl = _sides(left)
    pb, fr = _sides(right)
    a = ap.parse_args(fl + fr)
    if not pa or not pb:
        ap.error("both sides of the -- need at least one log")
    exp = lambda ps: sorted({f for p in ps for f in (glob.glob(p) or [p])})
    A = [read_log(p) for p in exp(pa)]
    B = [read_log(p) for p in exp(pb)]

    for lab, rows in ((a.label_a, A), (a.label_b, B)):
        bad = [r for r in rows if not r.get("done")]
        for r in bad:
            print(f"!! {lab}: {r['name']} has no held-out line -- did not reach its report; EXCLUDED")
    A = [r for r in A if r.get("done")]; B = [r for r in B if r.get("done")]
    if not A or not B:
        print("!! nothing to compare"); return 2

    cm = {r.get("commit") for r in A + B if r.get("commit")}
    if len(cm) > 1:
        print(f"!! the two arms were built from DIFFERENT COMMITS ({', '.join(sorted(cm))}). Any difference "
              f"below mixes the knob under test with every code change between them.")
    if any(r.get("dirty") for r in A + B):
        print("!! at least one run was built from a DIRTY tree -- it is not reproducible from its commit.")
    o1 = {round(r["order1"], 2) for r in A + B if r.get("order1")}
    if len(o1) > 1 and a.metric == "held_out":
        print(f"!! the arms saw different corpora (order-1 anchors {sorted(o1)}). held_out is not comparable "
              f"across them -- rerun with --metric d_order1.")

    print(f"\n=== {a.label_a}  vs  {a.label_b}   [{a.metric}, lower is better] ===")
    print(describe(a.label_a, A, a.metric)); print(describe(a.label_b, B, a.metric))

    # PAIR BY SEED. Unpaired is a fallback, not an equivalent: it throws away the variance reduction that makes
    # small-n comparisons in this project tractable at all.
    da = {r["seed"]: r[a.metric] for r in A if r.get("seed") is not None and r.get(a.metric) is not None}
    db = {r["seed"]: r[a.metric] for r in B if r.get("seed") is not None and r.get(a.metric) is not None}
    shared = sorted(set(da) & set(db))
    if shared:
        pairs = [(da[s], db[s]) for s in shared]
        mode = f"PAIRED on {len(shared)} shared seed(s): {shared}"
        lone = sorted((set(da) | set(db)) - set(shared))
        if lone: mode += f"  (unpaired and ignored: seeds {lone})"
    else:
        pairs = [(x, y) for x in da.values() for y in db.values()]
        mode = (f"UNPAIRED ({len(da)}x{len(db)} = {len(pairs)} crossings) -- the arms share no seed, so the "
                f"pairing that would cut the variance is unavailable. Rerun both arms over the same SEEDS.")
    print(f"\n  {mode}")

    diffs = [x - y for x, y in pairs]
    p = p_a_better(pairs)
    lo, hi = bootstrap_ci(pairs)
    need = seeds_needed(p, gamma=a.gamma)
    print(f"  mean difference ({a.label_a} - {a.label_b}) {_mean(diffs):+.4f}"
          + (f"   std of the paired difference {_std(diffs):.4f}" if len(diffs) > 1 and shared else ""))
    print(f"  P({a.label_a} better) = {p:.3f}   95% CI [{lo:.3f}, {hi:.3f}]   (gamma={a.gamma})")

    # THE THREE-WAY VERDICT. "Not significant" is a result, and at these sample sizes it is usually the correct
    # one -- reporting it as such is the entire point of the exercise.
    if len(pairs) < MIN_PAIRS:
        print(f"  >> NO VERDICT -- {len(pairs)} pair(s) is below the {MIN_PAIRS} a bootstrap needs to mean "
              f"anything. The interval above is an artefact of resampling {len(pairs)} point(s), not evidence. "
              f"Read the DIRECTION and the size of the difference, and treat both as a lead.")
        if need: print(f"  >> {need} paired seeds would be needed to establish an effect this size.")
        if shared:
            print(f"\n  per seed ({a.label_a} / {a.label_b} / diff):")
            for s in shared:
                print(f"    seed {s:<4} {da[s]:.3f}  {db[s]:.3f}  {da[s]-db[s]:+.4f}"
                      f"   {'A' if da[s] < db[s] else 'B' if db[s] < da[s] else '='}")
        print()
        return 0
    if lo <= 0.5 <= hi:
        v = (f"NOT SIGNIFICANT -- the interval spans 0.5, so this comparison does not distinguish the arms. "
             f"Draw no conclusion about which is better.")
    elif hi <= a.gamma:
        v = (f"SIGNIFICANT BUT NOT MEANINGFUL -- {a.label_a} wins more often than chance, but by less than the "
             f"gamma={a.gamma} bar for an effect worth acting on.")
    elif lo > 0.5:
        v = f"SIGNIFICANT AND MEANINGFUL -- {a.label_a} is better, and by enough to act on."
    else:
        v = f"{a.label_b} is favoured; re-read with the labels swapped."
    print(f"  >> {v}")
    if need is None:
        print(f"  >> the arms are indistinguishable on this metric at this variance; no seed budget resolves it.")
    elif len(pairs) < need:
        print(f"  >> {need} paired seeds would be needed to establish this at alpha={ALPHA}, power={1-BETA:.0%}; "
              f"you have {len(shared) if shared else len(pairs)}.")
    else:
        print(f"  >> sample size is adequate ({len(pairs)} >= {need} needed).")

    if shared:
        print(f"\n  per seed ({a.label_a} / {a.label_b} / diff):")
        for s in shared:
            print(f"    seed {s:<4} {da[s]:.3f}  {db[s]:.3f}  {da[s]-db[s]:+.4f}"
                  f"   {'A' if da[s] < db[s] else 'B' if db[s] < da[s] else '='}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
