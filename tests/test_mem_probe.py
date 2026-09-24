"""MEM's read probe, its eviction counters, and the gates the R stage renders. Driven through the
real loop (compose -> loop.run -> MEM.write / MEM.maintain -> _report) on short runs.

    python3 tests/test_mem_probe.py        # exit 0 = every check passed

WHY IT EXISTS (Q-MEM-12, docs/04_CONTRACT.md, 2026-09-24). Each of these was measured wrong or
not printed at all, and nothing in tests/ could see it:

  M1  THE PROBE ISSUED ONE QUERY PER BATCH ROW. MEM_PROBE_ROWS=64 issued 1 query per probe at
      OPT_BATCH_WINDOWS=1, and MEM_PROBE_ROWS=1 gave identical counters. It must issue probe_rows
      queries, one per POSITION, keyed at key_win like the write path, from a rotating offset.
  M2  AN EVICTION WAS COUNTED FOR EVERY ROW OF A PARTLY-FREE COMMIT. n_evict_free + n_evict_probation
      + n_evict_main must equal n_writes_committed, and the evictions must be the entries actually
      overwritten -- on the quantile arm, where a window keeps fewer rows than a block holds.
  M3  THE R STAGE DROPPED THE MEM, DATA AND grow_check GATES. Every mem.* gate, every Stream gate
      and every GrowReport gate must reach the report in three states.
  M4  THE MEM GATE REASONS SAID THE PROBE HAD NO PRODUCER beside a run that had issued rows; each
      no-promotion state must be named from the counters.
  M5  THE R STAGE COPIED store.counters / part.counters BEFORE THE CALLS THAT BUMP THEM.
  M6  G4 SEEDS: the rekey, probe and tripwire counters are present-and-0 on their armed arm and
      ABSENT off it; write's kept-nothing return seeds the eviction book.
"""
import os
import sys

_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(_ROOT, "src"))

import torch                                                       # noqa: E402
torch.set_num_threads(1)

from spine import lever as _lever                                  # noqa: E402
from spine import rng                                              # noqa: E402
from spine import loop                                             # noqa: E402
from spine import units as U                                       # noqa: E402
from spine.compose import compose, _key_fn                         # noqa: E402
from memory import api as mem_api                                  # noqa: E402

FAILS = []
BASE = {"DATA_STREAM_BYTES": "120000"}
_STALE = ("no producer", "passes probe_contexts=None", "passes None")


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" -- {detail}" if detail else ""))
    if not ok:
        FAILS.append(name)


def build(**env):
    """One real System per configuration; the assembly latch and the rng registry are reopened
    first because each call here stands for a different run."""
    _lever._reopen_assembly()
    rng.reset_issued()
    e = dict(BASE)
    e.update({k: str(v) for k, v in env.items()})
    return compose(environ=e)


class _Spy:
    """Wrap one module attribute for the duration of a `with`, recording through `record`."""

    def __init__(self, mod, name, record):
        self.mod, self.name, self.record = mod, name, record

    def __enter__(self):
        self.orig = getattr(self.mod, self.name)
        orig, record = self.orig, self.record

        def wrapped(*a, **k):
            out = orig(*a, **k)
            record(a, k, out)
            return out
        setattr(self.mod, self.name, wrapped)
        return self

    def __exit__(self, *exc):
        setattr(self.mod, self.name, self.orig)
        return False


def _gate(store, name):
    return next((g for g in store.gates if g.name == name), None)


def m1_m3_m4_m5_default():
    """The default arm, 80 windows: the probe's width, the rendered gates, the reasons, the order."""
    sysm = build()
    queries = []
    with _Spy(mem_api, "read",
              lambda a, k, out: queries.append(tuple(k["queries"].shape))):
        res = loop.run(sysm, max_windows=80, progress=False)
    c = sysm.store.counters
    fired, rows = int(c["store.n_probe_fired"]), int(c["store.n_probe_rows"])
    probe_rows = int(sysm.configs["MEM"].probe_rows)
    check("M1 every read the probe made carried MEM_PROBE_ROWS queries, not one per batch row",
          bool(queries) and all(q[0] == probe_rows for q in queries),
          f"query shapes {queries} at probe_rows={probe_rows}")
    check("M1 n_probe_rows counts the rows issued: probe_rows x the fires that had contexts",
          rows == probe_rows * len(queries) and len(queries) == fired - 1,
          f"n_probe_fired {fired}, n_probe_rows {rows}, reads {len(queries)} (the first fire has "
          f"no contexts: the loop lags the probe one flush)")
    check("M1 the probe promotes at its declared rate (n_promoted > 64 per read)",
          int(c.get("store.n_promoted", 0)) > 64 * len(queries),
          f"n_promoted {c.get('store.n_promoted')}")

    rep = res.report
    mrow = rep["MEM.census(reconcile=True)"]
    want = {g.name for g in sysm.store.gates}
    got = {k[len("gate:"):] for k in mrow if k.startswith("gate:")}
    check("M3 all seven mem.* gates are rendered in the MEM.census(reconcile=True) row",
          len(want) == 7 and want == got, f"declared {sorted(want)}, rendered {sorted(got)}")
    check("M3 each rendered MEM gate is one of the three states with its arithmetic",
          all(isinstance(mrow["gate:" + n], tuple) and mrow["gate:" + n][0] in
              ("fired", "armed-but-zero", "unreachable") and " vs " in mrow["gate:" + n][1]
              for n in got), str({n: mrow["gate:" + n][0] for n in sorted(got)}))
    drow = rep.get("DATA(stream.gates)")
    sg = {g.name for g in sysm.stream.gates}
    check("M3 every Stream gate is rendered in DATA(stream.gates)",
          isinstance(drow, dict) and bool(sg) and {k[5:] for k in drow} == sg,
          f"stream gates {sorted(sg)}, row {sorted(drow) if isinstance(drow, dict) else drow}")
    grow = rep.get("FAB.grow_check(last call's gates)")
    gg = {g.name for g in (sysm.grow_gates or ())}
    check("M3 every gate of the last FAB.grow_check call is rendered, and only the tuple is kept",
          isinstance(grow, dict) and bool(gg) and {k[5:] for k in grow} == gg
          and isinstance(sysm.grow_gates, tuple),
          f"grow gates {sorted(gg)}, row {sorted(grow) if isinstance(grow, dict) else grow}")

    reasons = {g.name: g.reason for g in sysm.store.gates}
    stale = {n: s for n, r in reasons.items() for s in _STALE if s in r}
    check("M4 no MEM gate reason says the probe has no producer on a run that issued rows",
          rows > 0 and not stale, f"n_probe_rows {rows}; stale {stale}")
    check("M4 mem.probe's reason quotes the rows actually issued",
          f"{rows} query row(s) issued over {fired} fire(s)" in reasons["mem.probe"],
          reasons["mem.probe"][:160])

    mc = rep["MEM(store.counters)"]
    check("M5 the report's store.counters copy carries the R-stage census's reconcile",
          mc.get("store.n_census_reconciles") == mrow["n_census_reconciles"]
          == c["store.n_census_reconciles"],
          f"report {mc.get('store.n_census_reconciles', 'ABSENT')}, census row "
          f"{mrow['n_census_reconciles']}, live {c['store.n_census_reconciles']}")
    pc = rep["DOM(part.counters)"]
    check("M5 the report's part.counters copy carries the R-stage DOM.prior read",
          pc.get("part.n_prior_reads", "ABSENT") == sysm.partition.counters.get("part.n_prior_reads")
          and "part.n_prior_reads" in pc,
          f"report {pc.get('part.n_prior_reads', 'ABSENT')}, live "
          f"{sysm.partition.counters.get('part.n_prior_reads', 'ABSENT')}")

    for k in ("store.n_rekey_passes", "store.n_rekey_slices", "store.n_rekey_entries",
              "store.n_dup_refused", "store.n_src_underflow", "store.n_probe_hits"):
        check(f"M6 {k} is present on its armed arm", k in c, f"{k}={c.get(k, 'ABSENT')}")
    check("M6 n_keys_at_capped_depth stays ABSENT off its arm (LM_ARCH=gru)",
          "store.n_keys_at_capped_depth" not in c and str(sysm.store.lm_kind) != "transformer",
          f"lm_kind {sysm.store.lm_kind}")
    ctx = int(sysm.configs["LM"].ctx)
    check("M6 n_write_truncated stays ABSENT where no window can exceed a block (ctx <= quota)",
          ctx <= int(sysm.configs["MEM"].quota) and "store.n_write_truncated" not in c,
          f"ctx {ctx}, quota {sysm.configs['MEM'].quota}")


def m1_lever_moves():
    """MEM_PROBE_ROWS is a lever again: 8 rows per read, and the offset rotates."""
    sysm = build(MEM_PROBE_ROWS=8, MEM_PROBE_EVERY=5)
    seen = []
    with _Spy(mem_api, "_encode_keys",
              lambda a, k, out: seen.append(a[1].clone())):
        loop.run(sysm, max_windows=24, progress=False)
    c = sysm.store.counters
    # _encode_keys is the write path's encoder too; the probe's calls are the 8-row ones.
    probes = [r for r in seen if int(r.shape[0]) == 8]
    check("M1 MEM_PROBE_ROWS=8 issues 8 rows per read",
          int(c["store.n_probe_rows"]) == 8 * (int(c["store.n_probe_fired"]) - 1),
          f"n_probe_fired {c['store.n_probe_fired']}, n_probe_rows {c['store.n_probe_rows']}")
    check("M1 each probe query is key_win tokens wide, the write path's key shape",
          bool(probes) and all(int(r.shape[1]) == int(sysm.configs["MEM"].key_win) for r in probes),
          f"{[tuple(r.shape) for r in probes]}")


def m2_quantile():
    """The eviction identity on the arm where a window keeps fewer rows than a block holds."""
    sysm = build(MEM_WRITE_MODE="quantile")
    over = []

    def rec(a, k, out):
        over.append((int(out[0]), int(out[1]), int(out[2]) + int(out[3])))
    with _Spy(mem_api, "_commit_window", rec):
        loop.run(sysm, max_windows=60, progress=False)
    c = sysm.store.counters
    com, fr = int(c["store.n_writes_committed"]), int(c["store.n_evict_free"])
    pr, mn = int(c["store.n_evict_probation"]), int(c["store.n_evict_main"])
    partial = sum(1 for m, f, e in over if 0 < f < m)
    check("M2 free + probation + main == committed on the quantile arm",
          fr + pr + mn == com, f"{fr} + {pr} + {mn} = {fr + pr + mn} vs committed {com}")
    check("M2 the case that double-counted was driven (a partly-free commit happened)",
          partial > 0, f"{partial} partly-free commit(s)")
    check("M2 every commit accounts each row once: free_used + evicted == committed",
          all(f + e == m for m, f, e in over), f"{len(over)} commit(s)")


def m4_m6_states():
    """The no-promotion states the mem.pressure Gate must tell apart, and write's early return."""
    sysm = build(MEM_PROBE_EVERY=0)
    loop.run(sysm, max_windows=10, progress=False)
    c = sysm.store.counters
    mc = mem_api.census(sysm.configs["MEM"], sysm.store)
    g = _gate(sysm.store, "mem.pressure")
    check("M4 MEM_PROBE_EVERY=0: pressure names NO PROMOTION PATH ON THIS CONFIGURATION",
          mc.pressure is None and not g.reachable
          and g.reason.startswith("NO PROMOTION PATH ON THIS CONFIGURATION"), g.reason[:120])
    check("M6 MEM_PROBE_EVERY=0: the probe counters are ABSENT (disarmed, not armed-but-0)",
          not any(k in c for k in ("store.n_probe_fired", "store.n_probe_rows",
                                   "store.n_probe_hits")),
          str({k: c.get(k, "ABSENT") for k in ("store.n_probe_fired", "store.n_probe_rows")}))

    sysm = build()
    loop.run(sysm, max_windows=6, progress=False)
    mem_api.census(sysm.configs["MEM"], sysm.store)
    g = _gate(sysm.store, "mem.pressure")
    check("M4 before any row is issued: pressure names NO QUERY ROW ISSUED YET",
          not g.reachable and g.reason.startswith("NO QUERY ROW ISSUED YET"), g.reason[:120])
    p = _gate(sysm.store, "mem.probe")
    check("M4 mem.probe before any row: ARMED-BUT-0 with the lag named, not 'no producer'",
          "NO query row issued yet" in p.reason and not any(s in p.reason for s in _STALE),
          p.reason[:160])

    # WRITE'S KEPT-NOTHING RETURN, driven directly: surprise 0 keeps nothing on the fixed gate.
    sysm = build()
    ctx = int(sysm.configs["LM"].ctx)
    x = torch.zeros(1, ctx, dtype=torch.long)
    r = mem_api.write(sysm.configs["MEM"], sysm.store, contexts=x, tokens=x,
                      surprise=torch.zeros(1, ctx), sources=torch.zeros(1, dtype=torch.long),
                      owners=torch.zeros(1, dtype=torch.long),
                      positions=torch.zeros(1, ctx, dtype=torch.long),
                      key_fn=_key_fn(sysm), now=U.Windows(1))
    c = sysm.store.counters
    keys = ("store.n_writes_committed", "store.n_evict_free", "store.n_evict_probation",
            "store.n_evict_main", "store.n_floor_blocked")
    check("M6 write's kept-nothing return seeds the whole eviction book at 0",
          r.kept == 0 and all(c.get(k) == 0 for k in keys),
          str({k: c.get(k, "ABSENT") for k in keys}))

    sysm = build(MEM_QUOTA=64)
    loop.run(sysm, max_windows=3, progress=False)
    c = sysm.store.counters
    check("M6 n_write_truncated is present once a window can exceed a block (ctx > quota)",
          "store.n_write_truncated" in c, f"n_write_truncated {c.get('store.n_write_truncated', 'ABSENT')}")


if __name__ == "__main__":
    m1_m3_m4_m5_default()
    m1_lever_moves()
    m2_quantile()
    m4_m6_states()
    print(f"{len(FAILS)} failure(s)" + (": " + ", ".join(FAILS) if FAILS else ""))
    sys.exit(1 if FAILS else 0)
