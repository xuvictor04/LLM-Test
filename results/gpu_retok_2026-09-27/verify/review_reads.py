"""The readings the 2026-09-28 review of this record cites (Proposal 05 O20, NEW-20, 04-6.2, the preset's
EVAL_RETENTION_EVERY, 03b-16.33), off the archive's logs and per-flush bytes alone, model-free:
  - each run's windows per phase (the stream's 4 equal byte ranges, each flush placed by its first byte),
    the retention probe's readings per phase at EVAL_RETENTION_EVERY 1000 plus one at each phase start,
    and the shortest phase's windows / 5 (04-6.2's cap);
  - each run's pool: the first progress line at FAB_SLOTS 4096, n_live at the end and the slots still free,
    the replicate k0_rerun counted like any run; and k0's n_live at the progress line of each kept window;
  - each act's tail bytes per token against the build-time value SIG's width was derived from.
    python3 review_reads.py <unpacked gpu_retok_out>"""
import json, os, re, sys

OUT = sys.argv[1]
TOTAL, NPH, SLOTS = 3780000, 4, 4096
RUNS = [(a, s) for a in ("k0", "k3000", "k1000", "k0_nuis") for s in range(3)] + [("k0_rerun", 0)]


def log(a, s):
    return open(os.path.join(OUT, "logs", f"{a}.s{s}.log")).read()


print("PHASES: windows per phase (first byte), probe readings per phase at 1000 + the phase start, shortest / 5")
for a, s in RUNS:
    fb = json.load(open(os.path.join(OUT, "curves", f"{a}.s{s}.bytes.json")))
    off, cnt = 0, [0] * NPH
    for nb in fb:
        cnt[min(NPH - 1, next((j for j in range(NPH) if off < round((j + 1) * TOTAL / NPH)), NPH - 1))] += 1
        off += nb
    lo, reads = 1, []
    for n in cnt:
        hi = lo + n - 1
        reads.append(sum(1 for w in range(1001, hi + 1, 1000) if w >= lo) + 1)
        lo = hi + 1
    print(f"  {a}.s{s}: {len(fb)} windows, phases {cnt}, readings {reads}, shortest / 5 = {min(cnt) / 5:.0f}")

print(f"POOL: the first progress line at n_live >= {SLOTS}, n_live at the end (fab.n_live) and the slots free")
full, free = [], []
for a, s in RUNS:
    t = log(a, s)
    prog = [(int(w), int(n)) for w, n in re.findall(r"^\[(\d+) windows\][^\n]*? n_live=(\d+)", t, re.M)]
    fill = next((w for w, n in prog if n >= SLOTS), None)
    end = int(re.search(r"^\s+fab\.n_live\s+(\d+)", t, re.M).group(1))
    full.append(fill is not None); free.append(SLOTS - end)
    print(f"  {a}.s{s}: full from window {fill if fill else '-'}; n_live at the end {end}, {SLOTS - end} free")
print(f"  full in {sum(full)} of {len(RUNS)} runs (the replicate k0_rerun included), {sum(full[:-1])} of "
      f"{len(RUNS) - 1} without it; slots free at the end {min(free)}-{max(free)}")
for s in range(3):
    prog = dict((int(w), int(n)) for w, n in re.findall(r"^\[(\d+) windows\][^\n]*? n_live=(\d+)", log("k0", s), re.M))
    kept = [int(w) for w in re.findall(rf"^k0\.s{s}\.w(\d+) ", open(os.path.join(OUT, "KEPT.txt")).read(), re.M)]
    at = [prog.get(w) for w in kept]
    print(f"  k0.s{s} at its {len(kept)} kept windows: n_live {min(at)}-{max(at)} ({SLOTS - max(at)}-{SLOTS - min(at)} "
          f"free); " + " ".join(f"w{w}:{n}" for w, n in zip(kept, at)))

print("BYTES PER TOKEN AGAINST THE BUILD-TIME VALUE, at each act (the act line's tail figure)")
for a in ("k3000", "k1000"):
    for s in range(3):
        v = re.findall(r"mid-epoch act at window (\d+):[^\n]*?([+-][\d.]+)% against the build-time", log(a, s))
        print(f"  {a}.s{s}: " + " ".join(f"w{w} {p}%" for w, p in v))
