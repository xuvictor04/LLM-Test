"""THE RETENTION PROBE: THE PINNED HELD-OUT READING, ITS TWO CLOSURES, ITS CONSUMERS, GENERATION AND THE
DIVERGENCE ALARM (Proposal 04 SR0 and NEW-03; register §8 3.1/3.2; docs/04_CONTRACT.md Q-EVAL-12, Q-OPT-13,
Q-DOM-6, Q-MEM-15, Q-CKPT-6, Q-FAB-17, Q-WORLD-11, Q-LM-14), driven through the real composition root and
loop, with real on-disk checkpoints written under a temporary directory.

    python3 tests/test_probe.py        # exit 0 = every check passed

WHY IT EXISTS. The probe is built OFF (EVAL_RETENTION_EVERY=0) and ships ON only after a test proves it is
telemetry: a reading beside training may read the model and must move nothing the run keeps. So the first
promise is bit-identity -- the same losses, the same state, and every counter equal but the probe's own
book and a named set that moves by exactly that book's counts -- and the rest pin what a reading is,
where it is taken, who reads it, and what a resume does with it. Each check below pins one of them.

  P1  BIT-IDENTITY, ON AGAINST OFF, at DATA_SYNTH_HOLDOUT=1: one full epoch at the shipped stream length
      (635 windows, EVAL_RETENTION_EVERY=50, generation on), tests/test_baseline.py's B3 shape (a full
      epoch with manage passes and a mid-epoch act, at 50), and 200 windows at 20 on the transformer arm
      with WORLD_FEEDBACK=1, LM_DROPOUT=0.1 and FAB_SOCIETY=1. Float-exact losses; equal state digests
      (tests/_state_digest.py) but LOOP.eval and RUN.cadences' 'retention' key; every integer counter
      equal but the exempt set; OPT's reading_at None on both (OPT_DAMP_SOURCE='off'). The ON run reads
      at every phase start, on the cadence the ledger fired (>= 10 on the full epoch), once at R through
      both closures, and generates.
  P2  THE EXEMPT SET MOVES BY THE BOOK'S OWN COUNTS, EXACTLY: tok.segment_remap by eval.holdout.cuts;
      fab.eval_passes, lm.embed.*, world.forecast.calls (and .inert where the forecast is off) by the
      forwards; lm.decode.calls by the decodes; sig.encode_calls and .encode_windows by the SIG encodes;
      lm.encode.calls by the forwards plus the memory-on closure's MEM reads. A closure pass moves no
      global stream (frozen_rng, at LM_DROPOUT=0.1), puts every submodule's mode back, and a memory-on
      pass leaves the store's use/prob/last/born, its ledger and every package's digest as they were.
  P3  THE PINNED WINDOWS AND THE ROUTING CLOCK: every build and resume pins the same windows; a
      continuing resume at a cadence reading (41) reads, at its start, what the parent's R read read --
      paired differences exactly 0 -- and its first three windows per half are the uninterrupted run's
      cadence reading at 41 (the step+1 routing clock); every memory-off reading after 41 is the
      uninterrupted run's, float for float, pairing included (the memory-on R reading reads a store
      that departs after any continuing resume -- MEM's rekey snapshot, recorded before the probe in
      tests/_state_digest.py); a boundary resume's start read is the parent's R read.
  P4  THE HALVES: each window and its routing prefix inside its half, no start drawn twice, the bytes
      the block's; the control and report streams issued by name; the cadence reading's windows a prefix
      of the boundary reading's (P3); consumers read the control half only -- the retention best, the
      forwarded Reading and the alarm's series are control means, and a report half planted non-finite
      moves none of them (P14).
  P5  ARRIVAL: each reading holds exactly the areas of the phases entered by its window, computed here
      from the plan, the phase bounds and the segmentation; a phase start reads at its first window; an
      unarrived area has no row anywhere and is the areas_unarrived gauge.
  P6  THE BEST CHECKPOINTS: CKPT_DIR, EVAL_RETENTION_EVERY=20, CKPT_BEST_KEEP=2, 200 windows: Saves.best
      and Saves.bestN (the process-global ledger diffed around the run) move; .best, .best1 and .best2
      and their vocabularies are on disk, each at the step Retention records; a refused slot save leaves
      no slot and the pointer where it stood; a resume of ckpt.pt.best continues the run exactly from
      best_step + 1 and restores the best (M45: no 'no best yet').
  P7  OPT_DAMP_SOURCE: a planted non-improving Reading series of seed count 1 under 'probe' refuses every
      losing restart (damp_refused_n1 = restarts - 1, restart_amp 1.0) and counts one Reading per `at`;
      seed count 2 damps; 'off' reads nothing and its gate names the lever. In-run, 'probe' and 'off'
      train the same losses; 'probe' at EVAL_RETENTION_EVERY=0 is refused at startup.
  P8  EVAL.blowup IS blowup_test.py's CALL-SITE RULE: fire for fire on its curves (:95-141) and at
      test_derive.py's threshold (:944-949); the all-area series re-arms at an arrival, in-run too.
  P9  GENERATION: its sizes; two runs identical; both closures identical at MEM_BLEND_MAX=0; the final
      checkpoint byte-identical with EVAL_GENERATE on and off; a second loop.run over one System reads its
      arrived areas and does not raise.
  P10 MEM's NULLS: blend at MEM_BLEND_MAX=0 hands back the model's distribution itself; an empty store
      misses everywhere at weight 0; a planted exact match reads conf 1 at weight blend_max, and at
      MEM_BLEND_MAX=1 the clamped blend's log is finite everywhere.
  P11 DOM.nearest IS _assign's DECISION: re-entry, spawn (-1) and the cap arm against _assign on a deep
      copy, with nothing written.
  P12 A LEGACY CHECKPOINT (LOOP.eval and OPT.reading_at stripped) RESUMES EXACTLY, probe off and on; on,
      it warns that the parent's areas are ASSUMED arrived.
  P13 THE CLOSURE IS THE FLUSH'S PATH: on a System built identically to one taken before its first flush
      (FAB_EXPLORE=0 FAB_SPAWN=0 FAB_CENT_EMA=0 FAB_DISCOVER=0 LM_DROPOUT=0), the memory-off closure on the
      first window, with the all-pad prefix, returns that flush's logits exactly.
  P14 A NON-FINITE READING IS COUNTED AND NOT FORWARDED; non-finite windows are left out of the means.
  P15 B1, B3, B3r and B5 reproduce at the defaults (tests/test_baseline.py, run from here).

WHAT THIS FILE CANNOT SEE: whether a reading means anything. CPU runs establish operation only; the
probe's readings, the best checkpoints it orders and the retention it reports are GPU questions.
"""
import contextlib
import copy
import os
import re
import shutil
import subprocess
import sys
import tempfile

_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(_ROOT, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import torch                                                       # noqa: E402
torch.set_num_threads(1)

from spine import lever as _lever                                  # noqa: E402
from spine import rng                                              # noqa: E402
from spine import loop                                             # noqa: E402
from spine import derive                                           # noqa: E402
from spine import assemble                                         # noqa: E402
from spine import units as U                                       # noqa: E402
from spine.compose import (compose, RefusedRun, _phase_windows, _logits_fn, _holdout_units,  # noqa: E402
                           _windows_in_epoch, _eval_modules, _prefix_units)
from eval import api as eval_api                                   # noqa: E402
from ckpt import api as ckpt_api                                   # noqa: E402
from opt import api as opt_api                                     # noqa: E402
from memory import api as mem_api                                  # noqa: E402
from sig import api as sig_api                                     # noqa: E402
from domains import api as dom_api                                 # noqa: E402
from lm import api as lm_api                                       # noqa: E402
import _state_digest as sd                                         # noqa: E402

FAILS = []
DATA_DIR = os.path.join(os.path.abspath(_ROOT), "data")
# tests/test_continuation.py's small base: a tenth-size fabric keeps each compose to a few seconds.
BASE = {"DATA_STREAM_BYTES": "60000", "SIG_WARMUP": "20", "FAB_N0": "256", "FAB_SLOTS": "512",
        "DATA_DIR": DATA_DIR}
H = {"DATA_SYNTH_HOLDOUT": "1"}
# THE STATE THE PROBE ADDS, excluded by name when an ON run is compared with an OFF one.
EXCL = ("LOOP.eval", "RUN.cadences.*.retention")
# THE REPORT'S INTEGER COUNTER LINES, as tests/test_baseline.py::COUNTER reads them from run.py.
COUNTER = re.compile(r"^[a-z_][a-z0-9_]*(?:\.[a-z0-9_:]+)+$")


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" -- {detail}" if detail else ""), flush=True)
    if not ok:
        FAILS.append(name)


def build(**env):
    """A System under BASE + `env`, built as a fresh run.py process builds one: the issued streams
    forgotten, and LM's tally -- process-lifetime by design (lm/api.py::_COUNTS) -- emptied, so a
    report here counts this System's calls and a checkpoint carries this lineage's."""
    _lever._reopen_assembly()
    rng.reset_issued()
    lm_api._COUNTS.clear()
    e = dict(BASE)
    e.update({k: str(v) for k, v in env.items()})
    return compose(environ=e)


def configs(**env):
    """The resolved Configs under BASE + `env`, with the issued streams forgotten."""
    _lever._reopen_assembly()
    rng.reset_issued()
    e = dict(BASE)
    e.update({k: str(v) for k, v in env.items()})
    return assemble.build(environ=e)[0]


def flat_ints(report):
    """{(row, key): int} -- every integer counter line the report prints."""
    return {(row, k): v for row, d in report.items() if isinstance(d, dict)
            for k, v in d.items() if isinstance(k, str) and COUNTER.match(k) and type(v) is int}


def book(res):
    b = res.report.get("EVAL(holdout)")
    return b if isinstance(b, dict) else {}


@contextlib.contextmanager
def spy_readings():
    """Every HoldoutReading EVAL.holdout_probe returns to the loop, in call order -- the order of
    RunResult.probe_series, so readings[i] is probe_series[i] with its per-window values."""
    got = []
    real = loop.eval_api.holdout_probe

    def spy(ev, **kw):
        rd = real(ev, **kw)
        got.append(rd)
        return rd
    loop.eval_api.holdout_probe = spy
    try:
        yield got
    finally:
        loop.eval_api.holdout_probe = real


@contextlib.contextmanager
def spy_samples():
    got = []
    real = loop.eval_api.generate

    def spy(ev, **kw):
        smp = real(ev, **kw)
        got.append(smp)
        return smp
    loop.eval_api.generate = spy
    try:
        yield got
    finally:
        loop.eval_api.generate = real


def per_window(rd):
    """{area: (control values, report values)} of one HoldoutReading."""
    return {a: (list(row.get("control") or ()), list(row.get("report") or ()))
            for a, row in rd.areas.items()}


def phase_at(bounds, byte):
    """The phase a byte falls in, computed here: lo <= byte < hi, the last phase past the end."""
    for k, (lo, hi) in enumerate(bounds):
        if int(lo) <= int(byte) < int(hi):
            return k
    return len(bounds) - 1


def window_phases(sysm, n):
    """[phase of window 1, ..., phase of window n] on the segmentation as it stands (no act)."""
    ctx = int(sysm.configs["LM"].ctx)
    pos = sysm.segmentation.byte_pos
    return [phase_at(sysm.plan.phase_bounds, pos[(w - 1) * ctx]) for w in range(1, n + 1)]


def arrived_by(sysm, phases, step):
    """The areas holding a pinned block that the phases entered by window `step` make live."""
    names = set()
    for k in set(phases[:step]):
        names |= {str(sysm.areas.names[int(i)]) for i in sysm.plan.schedule[k]}
    return names & set(sysm.probe_set.items)


# THE EXEMPT SET AND WHAT EACH MEMBER MOVES BY (Q-EVAL-12's exact-accounting amendment).
EXEMPT = ("eval.*", "tok.segment_remap", "lm.embed.*", "lm.encode.calls",
          "lm.encode.key_path_truncated", "lm.decode.calls", "lm.mask.*", "sig.encode_calls",
          "sig.encode_windows", "world.forecast.calls", "world.forecast.inert", "fab.eval_passes")
EXEMPT_ROWS = ("CKPT.Retention.counters",)


def expected_delta(key, bk, sysm):
    """The ON-minus-OFF delta Q-EVAL-12 states for an exempt counter, from the ON run's book; None
    for a key outside the exempt set (whose delta must be 0)."""
    f, d = int(bk.get("eval.holdout.forwards", 0)), int(bk.get("eval.holdout.decodes", 0))
    s, k = int(bk.get("eval.holdout.sig_calls", 0)), int(bk.get("eval.holdout.cuts", 0))
    reads = int(bk.get("eval.mem.reads", 0))
    lm, world, mem = sysm.configs["LM"], sysm.configs["WORLD"], sysm.configs["MEM"]
    composed = bool(getattr(sysm.model, "compose", None))
    inert = (not bool(world.feedback)) or (not bool(getattr(world, "enabled", True)))
    transformer = str(lm.arch) == "transformer"
    table = {
        "tok.segment_remap": k,
        "fab.eval_passes": f,
        "lm.embed.calls": f,
        "lm.embed.from_emb_weight": 0 if composed else f,
        "lm.embed.from_composed_table": f if composed else 0,
        "lm.encode.calls": f + reads,
        "lm.encode.key_path_truncated": reads if (transformer and int(mem.key_depth) > 0) else 0,
        "lm.decode.calls": d,
        "lm.mask.applied": d if bool(lm.mask_dead_rows) else 0,
        "lm.mask.rows_masked": 0,
        "sig.encode_calls": s,
        "sig.encode_windows": s,
        "world.forecast.calls": f,
        "world.forecast.inert": f if inert else 0,
    }
    if key.startswith("eval."):
        return "book"
    return table.get(key, "unknown" if any(re.fullmatch(p.replace(".", r"\.").replace("*", ".*"), key)
                                           for p in EXEMPT) else None)


def compare_counters(tag, r_off, r_on, s_on):
    """Every integer counter of the OFF and ON reports: equal outside the exempt set, and each exempt
    one moved by exactly its formula. Returns the findings."""
    off, on = flat_ints(r_off.report), flat_ints(r_on.report)
    bk = book(r_on)
    bad, moved = [], {}
    for (row, key) in sorted(set(off) | set(on)):
        if row in EXEMPT_ROWS:
            continue
        a, b = off.get((row, key)), on.get((row, key))
        want = expected_delta(key, bk, s_on)
        if want == "book":
            if a is not None:
                bad.append(f"{row}:{key} is in the OFF report ({a})")
            continue
        if want == "unknown":
            bad.append(f"{row}:{key} is exempt with no stated delta (OFF {a}, ON {b})")
            continue
        if want is None:
            if a != b:
                bad.append(f"{row}:{key} OFF {a} ON {b}")
            continue
        if (b or 0) - (a or 0) != want:
            bad.append(f"{row}:{key} moved {(b or 0) - (a or 0)} (OFF {a}, ON {b}), want {want}")
        elif want:
            moved[key] = want
    return bad, moved


def pair(tag, env, every, max_windows=None, cadence_min=None, gen=True):
    """P1/P2 on one shape: the OFF run and the ON run at EVAL_RETENTION_EVERY=`every`."""
    s0 = build(**env)
    r0 = loop.run(s0, max_windows=max_windows, progress=False)
    d0 = sd.digest(s0, exclude=EXCL, detail=True)
    ro0 = sd.digest(s0, detail=True).get("OPT.reading_at")
    s1 = build(EVAL_RETENTION_EVERY=every, **env)
    n_phase = sum(1 for n in _phase_windows(s1) if n > 0)
    ph = window_phases(s1, max_windows) if max_windows is not None else None
    r1 = loop.run(s1, max_windows=max_windows, progress=False)
    d1 = sd.digest(s1, exclude=EXCL, detail=True)
    bk = book(r1)
    windows = int(r1.windows)
    check(f"P1 {tag}: float-exact losses ON against OFF over {windows} windows",
          r0.loss_curve == r1.loss_curve and len(r1.loss_curve) == windows and windows > 0,
          f"first differing flush "
          f"{next((i for i, (x, y) in enumerate(zip(r0.loss_curve, r1.loss_curve)) if x != y), None)}")
    check(f"P1 {tag}: every package's state digest equal but LOOP.eval and RUN.cadences' 'retention'",
          d0 == d1 and len([k for k in d0 if "." not in k]) == 12, f"differing {sd.differing(d0, d1)}")
    check(f"P1 {tag}: OPT.reading_at is None on both (OPT_DAMP_SOURCE='off' reads no Reading)",
          s0.optimizer.reading_at is None and s1.optimizer.reading_at is None and ro0 is not None)
    led0, led1 = r0.cadence_ledger, r1.cadence_ledger
    check(f"P1 {tag}: the cadence ledger equal but 'retention', asked every window ON and never OFF",
          {k: v for k, v in led0.items() if k != "retention"}
          == {k: v for k, v in led1.items() if k != "retention"}
          and led0["retention"][0] == 0 and led1["retention"][0] == windows
          and led1["retention"][1] == bk.get("eval.holdout.cadence_reads"),
          f"OFF {led0.get('retention')}, ON {led1.get('retention')}")
    bad, moved = compare_counters(tag, r0, r1, s1)
    check(f"P1/P2 {tag}: every integer counter equal outside the exempt set, and each exempt one moved "
          f"by exactly its count in the probe's book", not bad and bk.get("eval.holdout.forwards", 0) > 0,
          ("; ".join(bad[:8]) + (f" (+{len(bad) - 8})" if len(bad) > 8 else "")) if bad else
          "moved: " + ", ".join(f"{k} +{v}" for k, v in sorted(moved.items())))
    phases_want = n_phase if max_windows is None else len(set(ph))
    ok_reads = (bk.get("eval.holdout.phase_reads") == phases_want
                and bk.get("eval.holdout.boundary_reads") == 2
                and bk.get("eval.holdout.resume_reads") == 0
                and bk.get("eval.holdout.calls") == len(r1.probe_series)
                and sum(1 for e in r1.probe_series if e["kind"] == "phase") == phases_want
                and (cadence_min is None or bk.get("eval.holdout.cadence_reads", 0) >= cadence_min)
                and sorted({e["closure"] for e in r1.probe_series if e["kind"] == "boundary"})
                == ["memory-off", "memory-on"])
    check(f"P1 {tag}: the ON run read at each of the {phases_want} phase start(s), "
          f"{bk.get('eval.holdout.cadence_reads')} time(s) on the cadence"
          + (f" (>= {cadence_min})" if cadence_min else "") + ", and once at R through both closures",
          ok_reads, str({k: v for k, v in bk.items() if k.endswith("_reads") or k.endswith("calls")}))
    if gen:
        g = r1.report.get("EVAL(generate)")
        check(f"P1 {tag}: the ON run generated through both closures",
              bk.get("eval.generate.samples", 0) > 0 and isinstance(g, tuple)
              and any(x.startswith("memory-off:") for x in g)
              and any(x.startswith("memory-on:") for x in g), str(g)[:200])
    return s0, r0, s1, r1


TMP = tempfile.mkdtemp(prefix="probe_")
try:
    # =============================================================================================
    # P8: EVAL.blowup against blowup_test.py's call-site rule (pure; runs first, costs nothing)
    # =============================================================================================
    ev20 = configs(EVAL_RETENTION_EVERY=20)["EVAL"]

    def ref_fires(curve):
        """blowup_test.py::fires (:63-80), verbatim in its rule, at derive.blowup_stale's defaults."""
        best, since, recent, fired, out = None, 0, [], False, []
        for i, x in enumerate(curve):
            recent.append(x)
            del recent[:-5]
            if best is None or x < best - 1e-6:
                best, since, fired = x, 0, False
                continue
            since += 1
            if not fired and derive.blowup_stale(recent, best, since):
                fired = True
                out.append(i)
        return out

    def eval_fires(curve):
        """The indices EVAL.blowup fires at, read off its count over growing prefixes."""
        out, prev = [], 0
        for i in range(len(curve)):
            n = eval_api.blowup(ev20, series={"x": curve[:i + 1]})["x"].fires
            if n > prev:
                out.append(i)
            prev = n
        return out

    CTL_OPEN = [3.37, 2.83, 2.78, 3.54, 2.99, 2.84, 4.82, 2.95, 2.71, 2.66, 2.55, 2.49, 2.44, 2.39, 2.35,
                2.31]
    STEP_OPEN = [3.35, 2.75, 2.71, 3.03, 3.01, 3.24, 2.97, 3.02, 2.80, 2.71, 2.63, 2.58, 2.51, 2.47, 2.42,
                 2.38]
    R13 = [3.0 - 0.04 * i for i in range(19)] + [3.40, 4.05, 6.80] + [3.4 + (0.1 if i % 3 else -0.1)
                                                                      for i in range(258)]
    BIG = [3.0 - 0.03 * i for i in range(28)] + [2.7 + (0.2 if i % 2 else 0.0) for i in range(300)]
    TWICE = [3.0] * 3 + [2.0] + [3.0] * 120 + [1.5] + [3.0] * 120
    ONCE = [3.0] * 3 + [2.0] + [3.0] * 200
    SPIKE = [2.78, 4.82, 2.95] + [2.5] * 200
    _curves = {"sched_ctl": CTL_OPEN, "sched_step": STEP_OPEN, "round13": R13, "0.75GB": BIG,
               "twice": TWICE, "once": ONCE, "spike": SPIKE}
    _got = {k: (ref_fires(c), eval_fires(c)) for k, c in _curves.items()}
    check("P8 EVAL.blowup fires where blowup_test.py's call-site rule fires, index for index, on its "
          "seven curves: silent through both round15 openings and a single spike, once on round13 and "
          "0.75GB, twice across a recovery, once on a sustained excursion",
          all(a == b for a, b in _got.values())
          and [len(_got[k][0]) for k in _curves] == [0, 0, 1, 1, 2, 1, 0],
          str({k: v for k, v in _got.items()}))
    # test_derive.py:944-949, through the series: (3.0, 4.82, 2.95) against 1.9 at since 80 fires, at 79
    # does not.
    _at80 = [1.9] + [2.95] * 77 + [3.0, 4.82, 2.95]
    _at79 = [1.9] + [2.95] * 76 + [3.0, 4.82, 2.95]
    _b80 = eval_api.blowup(ev20, series={"x": _at80})["x"]
    _b79 = eval_api.blowup(ev20, series={"x": _at79})["x"]
    check("P8 at test_derive.py's threshold: the recent window (.., 3.0, 4.82, 2.95) 80 readings stale "
          "against a best of 1.9 fires on the 80th and not on the 79th; the horizon is "
          "derive.blowup_horizon's 80 readings x 20 windows",
          _b80.fires == 1 and _b80.fired and _b80.since_best == 80 and _b79.fires == 0
          and _b79.since_best == 79 and _b80.horizon_windows == 1600,
          f"80: {_b80}; 79: {_b79}")
    _no = eval_api.blowup(ev20, series={"all": [2.0] + [3.0] * 85})["all"]
    _re = eval_api.blowup(ev20, series={"all": [2.0, [3.0, True]] + [3.0] * 84})["all"]
    check("P8 the all-area series re-arms at an arrival: a step up to 3.0 held for 85 readings fires "
          "without the re-arm entry and not with it, whose reading becomes the best",
          _no.fires == 1 and _re.fires == 0 and _re.best == 3.0 and _re.since_best == 84,
          f"without {_no}; with {_re}")
    _short = eval_api.blowup(ev20, series={"x": [2.0, 2.1]})["x"]
    check("P8 fewer than three readings: silent, with the reason naming the horizon",
          _short.fires == 0 and "three" in _short.reason and "1600 windows" in _short.reason,
          _short.reason)

    # =============================================================================================
    # P7 (unit): OPT_DAMP_SOURCE over a planted Reading series
    # =============================================================================================
    def damp_run(source, seeds, value=3.0, steps=400):
        o = configs(OPT_DAMP_SOURCE=source, OPT_LR_WAVELENGTH=40)["OPT"]
        p = torch.nn.Parameter(torch.ones(3))
        st = opt_api.build(o, param_groups={"base": [p], "encoder": []}, run_windows=U.Windows(steps))
        for k in range(steps):
            opt_api.scaled_backward(o, st, (p * p).sum())
            opt_api.maybe_step(o, st, best_bpb=eval_api.Reading(value=value, seed_count=seeds,
                                                                at=(k // 10) * 10))
        return o, st

    _o1, _s1 = damp_run("probe", 1)
    _o2, _s2 = damp_run("probe", 2)
    _oo, _so = damp_run("off", 1)
    c1, c2, co = _s1.counters, _s2.counters, _so.counters
    det = int(c1.get("opt.restart.detected", 0))
    check("P7 'probe', seed count 1, a non-improving series: every losing restart is refused under "
          "PLAN 3.8 (damp_refused_n1 = restarts - 1), restart_amp stays 1.0, and the Reading is counted "
          "once per `at` (40 measurements over 400 flushes)",
          det >= 3 and c1.get("opt.restart.damp_refused_n1") == det - 1
          and c1.get("opt.restart.damped", 0) == 0 and _s1.restart_amp == 1.0
          and c1.get("opt.restart.readings") == 40 and _s1.reading_at == 390,
          f"detected {det}, refused {c1.get('opt.restart.damp_refused_n1')}, readings "
          f"{c1.get('opt.restart.readings')}, amp {_s1.restart_amp}")
    # A DAMPED SWING CAN FALL UNDER THE DETECTOR'S OWN BAR (lr > 0.5 x peak): at restart_amp 0.25 the
    # next peak is 0.05 + 0.95 x 0.25 of the rate, so the seed-2 run detects fewer restarts than the
    # seed-1 run, and is held to its own count.
    det2 = int(c2.get("opt.restart.detected", 0))
    check("P7 'probe', seed count 2: the same series damps every losing restart it detects (the refusal "
          "is the seed count's, not the source's)",
          det2 >= 2 and c2.get("opt.restart.damped") == det2 - 1
          and c2.get("opt.restart.damp_refused_n1", 0) == 0
          and abs(_s2.restart_amp - 0.5 ** (det2 - 1)) < 1e-12,
          f"detected {det2}, damped {c2.get('opt.restart.damped')}, amp {_s2.restart_amp}, below the "
          f"bar {c2.get('opt.restart.below_bar')}")
    _og = str(opt_api.counters(_oo, _so))
    check("P7 'off': no Reading is read -- readings 0, no refusal, every restart counted no_reading, "
          "restart_amp 1.0 -- and the damping gate's reason names OPT_DAMP_SOURCE='off'",
          co.get("opt.restart.readings") == 0 and co.get("opt.restart.damp_refused_n1", 0) == 0
          and co.get("opt.restart.no_reading") == det and _so.restart_amp == 1.0
          and _so.reading_at is None and "OPT_DAMP_SOURCE='off'" in _og,
          f"readings {co.get('opt.restart.readings')}, no_reading {co.get('opt.restart.no_reading')}")
    _sd = opt_api.state_dict(_o1, _s1)
    _st2 = opt_api.build(_o1, param_groups={"base": [torch.nn.Parameter(torch.ones(3))], "encoder": []},
                         run_windows=U.Windows(400))
    opt_api.load_state(_o1, _st2, copy.deepcopy(_sd))
    _sd_old = {k: v for k, v in copy.deepcopy(_sd).items() if k != "reading_at"}
    _st3 = opt_api.build(_o1, param_groups={"base": [torch.nn.Parameter(torch.ones(3))], "encoder": []},
                         run_windows=U.Windows(400))
    opt_api.load_state(_o1, _st3, _sd_old)
    check("P7 reading_at crosses a save (390 restored; a blob written before it restores None)",
          _sd.get("reading_at") == 390 and _st2.reading_at == 390 and _st3.reading_at is None)
    try:
        build(OPT_DAMP_SOURCE="probe", **H)
        check("P7 OPT_DAMP_SOURCE='probe' at EVAL_RETENTION_EVERY=0 is refused", False, "composed")
    except RefusedRun as e:
        check("P7 OPT_DAMP_SOURCE='probe' at EVAL_RETENTION_EVERY=0 is refused at startup, naming both",
              e.stage == "refuse" and any("OPT_DAMP_SOURCE" in r and "EVAL_RETENTION_EVERY" in r
                                          for r in e.refusals), str(e.refusals)[:300])

    # =============================================================================================
    # P1 (the off arms): nothing pinned, drawn, read or counted, and the report says why
    # =============================================================================================
    for tag, env, word in (("the shipped EVAL_RETENTION_EVERY=0", dict(H), "EVAL_RETENTION_EVERY=0"),
                           ("EVAL_RETENTION_EVERY=20 with no block (DATA_SYNTH_HOLDOUT=0)",
                            {"EVAL_RETENTION_EVERY": 20}, "DATA_SYNTH_HOLDOUT=0")):
        so = build(**env)
        _minted = sorted(k for k in rng.issued() if k.startswith("eval."))
        ro = loop.run(so, max_windows=3, progress=False)
        _rows = [ro.report.get(k) for k in ("EVAL(holdout)", "EVAL(blowup)", "EVAL(generate)")]
        _gl = [g for g in ro.gated if g.startswith("EVAL.")]
        check(f"P1 off at {tag}: no ProbeSet and no eval.* stream, no reading, no eval.* key anywhere in "
              f"the report, 'retention' asked 0 times, and the three EVAL rows UNREACHABLE naming {word}",
              not so.probe_set.items and not _minted and not ro.probe_series and so.eval_books == {}
              and not any(str(k[1]).startswith("eval.") for k in flat_ints(ro.report))
              and ro.cadence_ledger["retention"][0] == 0
              and "fab.eval_passes" not in so.fabric.counters
              and all(isinstance(r, str) and r.startswith("UNREACHABLE") and word in r for r in _rows)
              and so.eval_carried is None,
              f"minted {_minted}; rows {[str(r)[:60] for r in _rows]}; gated {[g[:80] for g in _gl]}")
    del so, ro

    # =============================================================================================
    # P13: the memory-off closure is the flush's path (before any other run moves the process)
    # =============================================================================================
    E13 = dict(H, EVAL_RETENTION_EVERY=20, EVAL_GENERATE=0, FAB_EXPLORE=0, FAB_SPAWN=0, FAB_CENT_EMA=0,
               FAB_DISCOVER=0, LM_DROPOUT=0)
    a13 = build(**E13)
    # P4: the two streams per area, issued by name at the 'probe' row.
    _issued = set(rng.issued())
    _want_names = {f"eval.holdout.{derive.stream_key(x)}.{h}" for x in a13.probe_set.items
                   for h in ("control", "report")}
    check("P4 compose issued eval.holdout.<key>.control and .report for every area holding a block, "
          "and ProbeSet.rng_names lists them in draw order",
          _want_names <= _issued and len(a13.probe_set.items) == 4
          and sorted(a13.probe_set.rng_names) == sorted(_want_names),
          f"missing {sorted(_want_names - _issued)}")
    _ctx = int(a13.configs["LM"].ctx)
    _x0 = torch.tensor([a13.segmentation.ids[0:_ctx]], dtype=torch.long)
    _lc = _logits_fn(a13, use_memory=False)(_x0, prefix_bytes=[b""])
    b13 = build(**E13)
    _cap = []
    _real_loss = loop.lm_api.lm_loss

    def _spy_loss(lm, logits, y):
        if not _cap:
            _cap.append(logits.detach().clone())
        return _real_loss(lm, logits, y)
    loop.lm_api.lm_loss = _spy_loss
    try:
        loop.run(b13, max_windows=1, progress=False)
    finally:
        loop.lm_api.lm_loss = _real_loss
    check("P13 on a System built identically to one taken before its first flush, the memory-off "
          "closure on the first window with the all-pad prefix returns that flush's logits exactly "
          "(the step+1 routing clock is the first flush's own step)",
          bool(_cap) and _cap[0].shape == _lc.shape and torch.equal(_cap[0], _lc),
          f"max |d| {float((_cap[0] - _lc).abs().max()) if _cap and _cap[0].shape == _lc.shape else None}")

    # =============================================================================================
    # P10: MEM's nulls, on a13's store (never trained, so empty), then a planted exact match
    # =============================================================================================
    st13 = a13.store
    m0 = configs(MEM_BLEND_MAX=0.0, **H)["MEM"]
    m1 = configs(MEM_BLEND_MAX=1.0, **H)["MEM"]
    mh = a13.configs["MEM"]
    _g = torch.Generator().manual_seed(7)
    q = torch.nn.functional.normalize(torch.randn(4, int(st13.key_dim), generator=_g), dim=-1)
    V = int(st13.vocab_slots)
    probs = torch.softmax(torch.randn(4, V, generator=_g), dim=-1)
    got0 = mem_api.read(mh, st13, queries=q, promote=False)
    check("P10 an empty store misses everywhere: hits -1, conf 0, weight 0, dist all zeros",
          bool((got0.hits == -1).all()) and float(got0.blend.abs().sum()) == 0.0
          and float(got0.conf.abs().sum()) == 0.0 and float(got0.dist.abs().sum()) == 0.0)
    check("P10 MEM.blend at MEM_BLEND_MAX=0 hands back the model's distribution itself (the same object)",
          mem_api.blend(m0, probs, mem_api.read(m0, st13, queries=q, promote=False)) is probs)
    _keep = {f: getattr(st13, f).clone() for f in ("keys", "active", "tok", "use", "prob", "last",
                                                    "born")}
    _led = dict(st13.counters)
    st13.keys[0] = q[0]
    st13.active[0] = True
    st13.tok[0] = 7
    got1 = mem_api.read(m1, st13, queries=q[:1], promote=False)
    _mf = float(m1.match_floor)
    check("P10 a planted exact match: the entry is hit, conf 1, weight blend_max through the ramp, and "
          "the vote is the stored token",
          int(got1.hits[0, 0]) == 0 and abs(float(got1.conf[0]) - 1.0) < 1e-6
          and abs(float(got1.blend[0]) - 1.0 * min(1.0, max(0.0, (float(got1.conf[0]) - _mf)
                                                            / max(1e-6, 1.0 - _mf)))) < 1e-6
          and abs(float(got1.dist[0, 7]) - 1.0) < 1e-6,
          f"hits {got1.hits[0, :3].tolist()}, conf {float(got1.conf[0])}, blend {float(got1.blend[0])}")
    _one = torch.zeros(1, V)
    _one[0, 7] = 1.0
    _ret = mem_api.Retrieval(dist=_one, conf=torch.ones(1), hits=torch.zeros(1, 1, dtype=torch.long),
                             weights=torch.ones(1, 1), blend=torch.ones(1))
    _mix = mem_api.blend(m1, probs[:1], _ret)
    check("P10 at MEM_BLEND_MAX=1 a perfect match takes the whole weight and the clamped blend's log is "
          "finite at every slot, the vote's token on top",
          bool(torch.isfinite(torch.log(_mix)).all()) and int(_mix[0].argmax()) == 7
          and abs(float(_mix.sum()) - 1.0) < 1e-5)
    check("P10 promote=False moved nothing: use, prob, last, born and the store's ledger as planted",
          all(torch.equal(getattr(st13, f), _keep[f]) for f in ("use", "prob", "last", "born"))
          and dict(st13.counters) == _led)
    del a13, b13

    # =============================================================================================
    # GROUP B: the continuing resume (P3, P4, P5, P11, P12, P2's store), at DATA_SYNTH_HOLDOUT=1,
    # EVAL_RETENTION_EVERY=20, no generation
    # =============================================================================================
    EB = dict(H, EVAL_RETENTION_EVERY=20, EVAL_GENERATE=0)
    with spy_readings() as rd_u:
        u = build(**EB)
        ph_u = window_phases(u, 100)
        ru = loop.run(u, max_windows=100, progress=False)
    with spy_readings() as rd_p:
        p = build(CKPT_DIR=f"{TMP}/p3p", **EB)
        rp = loop.run(p, max_windows=41, progress=False)
    _first_bpb = []
    _real_ms = loop.opt_api.maybe_step

    def _spy_ms(opt, st, **kw):
        if not _first_bpb:
            _first_bpb.append(kw.get("best_bpb"))
        return _real_ms(opt, st, **kw)
    loop.opt_api.maybe_step = _spy_ms
    try:
        with spy_readings() as rd_c:
            c = build(CKPT_RESUME=f"{TMP}/p3p", CKPT_DIR=f"{TMP}/p3c", **EB)
            rc = loop.run(c, max_windows=59, progress=False)
    finally:
        loop.opt_api.maybe_step = _real_ms
    su, sp, sc = ru.probe_series, rp.probe_series, rc.probe_series
    check("P3 the child continues the uninterrupted run exactly (losses 42..100)",
          c.resume_pos is not None and rc.loss_curve == ru.loss_curve[41:100],
          f"resume_pos {c.resume_pos}")
    rng.reset_issued()
    _repin = eval_api.pin_holdout(u.configs["EVAL"], blocks=u.areas.holdout, seed=0,
                                  window_bytes=u.probe_set.window_bytes,
                                  prefix_bytes=u.probe_set.prefix_bytes)
    check("P3 every build and resume pins the same windows: the uninterrupted run's, the parent's and "
          "the child's ProbeSets are equal, and so is a fresh EVAL.pin_holdout with the same arguments",
          u.probe_set == p.probe_set == c.probe_set and _repin == u.probe_set)
    _kinds_c = [(e["step"], e["kind"], e["closure"]) for e in sc]
    _pr = [(i, rd) for i, (e, rd) in enumerate(zip(sp, rd_p)) if e["kind"] == "boundary"]
    _cs = [(i, rd) for i, (e, rd) in enumerate(zip(sc, rd_c)) if e["kind"] == "resume"]
    _u41 = next(rd for e, rd in zip(su, rd_u) if e["step"] == 41)
    _p41 = next(rd for e, rd in zip(sp, rd_p) if e["step"] == 41 and e["kind"] == "cadence")
    check("P3 the child reads at its start, before its first window, through both closures, at the "
          "parent's clock (41)",
          _kinds_c[:2] == [(41, "resume", "memory-off"), (41, "resume", "memory-on")]
          and c.eval_books["eval.holdout.resume_reads"] == 2, str(_kinds_c[:3]))
    _same = (len(_pr) == 2 and len(_cs) == 2
             and all(per_window(a) == per_window(b) and a.closure == b.closure
                     for (_, a), (_, b) in zip(_pr, _cs)))
    _zero = all(v[1] == 0.0 and v[2] == 0.0 and v[0] == 16
                for _, rd in _cs for halves in rd.paired.values() for v in halves.values())
    check("P3 LIKE FOR LIKE: the start read equals the parent's R read at the same weights, window for "
          "window through both closures, and its pairing against it reads 16 differences of exactly 0 "
          "per area and half",
          _same and _zero and all(rd.paired for _, rd in _cs),
          f"closures {[rd.closure for _, rd in _cs]}")
    _pre = all(per_window(_cs[0][1])[a][0][:3] == per_window(_u41)[a][0]
               and per_window(_cs[0][1])[a][1][:3] == per_window(_u41)[a][1] for a in _u41.areas)
    check("P3 THE ROUTING CLOCK: the start read's first three windows per half are the uninterrupted "
          "run's cadence reading at 41, float for float (both route at step 42, the next window's)",
          _pre and per_window(_p41) == per_window(_u41) and len(_u41.areas) == 2,
          f"u41 {per_window(_u41)}")
    _after_u = [(e, rd) for e, rd in zip(su, rd_u) if e["step"] > 41 and e["kind"] != "boundary"]
    _after_c = [(e, rd) for e, rd in zip(sc, rd_c) if e["kind"] in ("cadence", "phase")]

    def _sans_seen(e):
        return dict(e, areas={a: {k: v for k, v in row.items() if k != "seen_by_parent"}
                              for a, row in e["areas"].items()})
    check("P3 every in-run reading after 41 is the uninterrupted run's, float for float -- kind, step, "
          "every window, the means and the pairing against the reading before it",
          len(_after_u) == len(_after_c) == 3
          and all(_sans_seen(eu) == _sans_seen(ec) and per_window(a) == per_window(b)
                  and a.paired == b.paired for (eu, a), (ec, b) in zip(_after_u, _after_c)),
          f"u {[(e['step'], e['kind']) for e, _ in _after_u]}, c {[(e['step'], e['kind']) for e, _ in _after_c]}")
    check("P3 ... and each row says whose text it is: eng and py were seen by the parent in the child "
          "and by no parent in the uninterrupted run; num, reached after the resume, by neither",
          all(ec["areas"][a]["seen_by_parent"] == (a in ("eng", "py"))
              and eu["areas"][a]["seen_by_parent"] is False
              for (eu, _a), (ec, _b) in zip(_after_u, _after_c) for a in ec["areas"]))
    _ru_b = [rd for e, rd in zip(su, rd_u) if e["kind"] == "boundary"]
    _rc_b = [rd for e, rd in zip(sc, rd_c) if e["kind"] == "boundary"]
    # THE MEMORY-ON R READING IS NOT HELD EQUAL, and the reason predates the probe: MEM's rows depart
    # after a continuing resume because memory/api.py::maintain retakes its rekey snapshot instead of
    # checkpointing it (tests/_state_digest.py, measured on B3r at ae70638). The memory-on start read is
    # equal (above): the store is equal at the restore.
    _mem_rows = sd.differing(sd.digest(u, detail=True), sd.digest(c, detail=True))
    check("P3 the child's R reading (100) through the memory-off closure is the uninterrupted run's, "
          "window for window; the memory-on one reads a store that has departed (MEM's rekey snapshot, "
          "recorded before the probe)",
          len(_ru_b) == len(_rc_b) == 2 and _ru_b[0].closure == "memory-off"
          and per_window(_ru_b[0]) == per_window(_rc_b[0]) and "MEM.rows" in _mem_rows,
          f"memory-on equal: {per_window(_ru_b[1]) == per_window(_rc_b[1])}; state apart: {_mem_rows}")
    check("P3 the forwarded Reading crossed the save (LOOP.eval): the child's first flush handed "
          "OPT.maybe_step the parent's last one, the uninterrupted run's reading at 41, and the child "
          "ends holding what the uninterrupted run ends holding",
          bool(_first_bpb) and _first_bpb[0] == p.probe_reading == _u41.control_mean
          and _first_bpb[0].at == 41 and u.probe_reading == c.probe_reading
          and int(c.probe_reading.at) == 81,
          f"first best_bpb {_first_bpb[:1]}; u {u.probe_reading}, c {c.probe_reading}")

    # ---- P4: the halves, and what the consumers read -------------------------------------------
    ps = u.probe_set
    _bad = []
    for area, it in ps.items.items():
        blk = u.areas.holdout[area]
        mid, blen = ps.halves[area]
        W, P = int(ps.window_bytes), int(ps.prefix_bytes)
        for half, (lo, hi) in (("control", (0, mid)), ("report", (mid, blen))):
            starts = [s for s, _p, _w in it[half]]
            if len(set(starts)) != len(starts):
                _bad.append(f"{area}.{half} draws a start twice")
            for s, pre, win in it[half]:
                if not (lo <= s - P and s + W <= hi) or pre != blk[s - P:s] or win != blk[s:s + W]:
                    _bad.append(f"{area}.{half} start {s}")
    check("P4 every pinned window and its routing prefix lie inside their own half, no start is drawn "
          "twice, and each item's bytes are the block's", not _bad and len(ps.items) == 4
          and all(len(it["control"]) == 16 and len(it["report"]) == 16 for it in ps.items.values()),
          "; ".join(_bad[:6]))
    _fwd = [(e, rd) for e, rd in zip(su, rd_u) if e["kind"] in ("cadence", "phase")]
    _cms = [float(rd.control_mean.value) for _, rd in _fwd]
    _all = u.eval_carried["series"]["all"]
    check("P4 the consumers read the CONTROL mean: the retention best is the least control mean at its "
          "step, the forwarded Reading the last one, and the alarm's all-area series is the control "
          "means in order",
          u.retention.state()["best_bpb"] == min(_cms)
          and u.retention.state()["best_step"] == _fwd[_cms.index(min(_cms))][0]["step"]
          and u.probe_reading.value == _cms[-1] and u.probe_reading.at == _fwd[-1][0]["step"]
          and [float(e[0]) if isinstance(e, list) else float(e) for e in _all] == _cms
          and u.retention.counters()["probes_seen"] == len(_cms),
          f"best {u.retention.state()['best_bpb']} vs {min(_cms)}")

    # ---- P5: arrival ------------------------------------------------------------------------------
    _want_phase = [w for w in range(1, 101) if w == 1 or ph_u[w - 1] != ph_u[w - 2]]
    _got_phase = [e["step"] for e in su if e["kind"] == "phase"]
    _areas_ok = all(set(e["areas"]) == arrived_by(u, ph_u, e["step"]) for e in su)
    _never = set(ps.items) - arrived_by(u, ph_u, 100)
    check("P5 a phase start reads at its first window, computed here from the phase bounds and the "
          "segmentation", _got_phase == _want_phase and len(_want_phase) == 2,
          f"got {_got_phase}, want {_want_phase}")
    check("P5 each reading holds exactly the areas of the phases entered by its window; the area not "
          "yet reached has no row anywhere and is the areas_unarrived gauge",
          _areas_ok and _never == {"c"} and all("c" not in e["areas"] for e in su)
          and book(ru).get("eval.holdout.areas_unarrived") == 1,
          str([(e["step"], sorted(e["areas"])) for e in su]))
    _flags = [bool(e[1]) if isinstance(e, list) else False for e in _all]
    check("P8 in-run, the all-area series re-arms exactly at the readings where an area arrived (window "
          "1: eng and py; window 80: num)",
          _flags == [e["step"] in (1, 80) for e in su if e["kind"] in ("cadence", "phase")],
          f"{list(zip([e['step'] for e in su if e['kind'] != 'boundary'], _flags))}")

    # ---- P2: a closure pass moves nothing it measures ---------------------------------------------
    _units = _holdout_units(u, set(ps.items))
    _win = [(pre, w) for a in sorted(_units) for pre, w in _units[a]["control"][:2]]
    _cut = loop._c_holdout_tokenize(u)
    stu = u.store
    _snap = {f: getattr(stu, f).clone() for f in ("use", "prob", "last", "born", "keys", "active")}
    _led_u = copy.deepcopy(stu.counters)
    _dg0 = sd.digest(u, detail=True)
    _part_led = copy.deepcopy(u.partition.counters)
    for use_mem in (True, False):
        fn = _logits_fn(u, use_memory=use_mem)
        for pre, w in _win:
            ids = list(_cut(w).ids)
            fn(torch.tensor([ids[:-1]]), prefix_bytes=[pre])
    _dg1 = sd.digest(u, detail=True)
    check("P2 memory-on and memory-off passes over eight held-out windows leave the store's use, prob, "
          "last, born, keys and active, its ledger, DOM's ledger and every package's digest as they were",
          all(torch.equal(getattr(stu, f), _snap[f]) for f in _snap) and stu.counters == _led_u
          and u.partition.counters == _part_led and _dg0 == _dg1 and int(stu.active.sum()) > 0,
          f"differing {sd.differing(_dg0, _dg1)}; store entries {int(stu.active.sum())}")

    # ---- P11: DOM.nearest is _assign's decision, and writes nothing --------------------------------
    part, dcfg = u.partition, u.configs["DOM"]
    sig = u.configs["SIG"]
    _sigs = [sig_api.encode(sig, u.sig, [_prefix_units(u, pre, None, {})])[0] for pre, _w in _win]
    _live = part._live()
    _sigs += [part.cent[_live[0]].clone(), -torch.stack([part.cent[i] for i in _live]).mean(0)]
    _dg_dom = sd.digest(u, detail=True)
    _rs = getattr(getattr(part, "rng", None), "_draws", None)

    def via_assign(prt, s, slots):
        cp = copy.deepcopy(prt)
        n0 = dict(cp.counters)
        did, spawned, _re = dom_api._assign(cp, dom_api._normalise(s.detach().float()), 0,
                                            accept_rule=str(dcfg.accept_rule),
                                            spawn_dist=float(dcfg.spawn_dist), margin=float(dcfg.margin),
                                            slots=slots)
        kind = ("new" if spawned else
                "cap" if cp.counters.get("part.n_capped", 0) > n0.get("part.n_capped", 0) else "reenter")
        return (-1 if spawned else int(did)), kind

    _pairs = [(dom_api.nearest(dcfg, part, signature=s), via_assign(part, s, int(dcfg.d_expert_slots)))
              for s in _sigs]
    _kinds = {k for _n, (_d, k) in _pairs}
    dcap = configs(FAB_SLOTS=len(part.cent), **EB)["DOM"]
    _far = _sigs[-1]
    _capn = dom_api.nearest(dcap, part, signature=_far)
    _capa = via_assign(part, _far, len(part.cent))
    check("P11 DOM.nearest answers what _assign does on a deep copy, signature for signature -- re-entry "
          "and spawn (-1) among them -- and at d_expert_slots = the live count the far signature is "
          "absorbed into the nearest, as the cap arm absorbs it",
          all(n == d for n, (d, _k) in _pairs) and {"reenter", "new"} <= _kinds
          and _capa[1] == "cap" and _capn == _capa[0] and _capn >= 0,
          f"{[(n, d, k) for n, (d, k) in _pairs]}; cap {_capn} vs {_capa}")
    check("P11 nearest wrote nothing: DOM's digest, its ledger and its stream as they were",
          sd.digest(u, detail=True) == _dg_dom and u.partition.counters == _part_led
          and getattr(getattr(part, "rng", None), "_draws", None) == _rs)

    # ---- P12: a legacy checkpoint resumes exactly --------------------------------------------------
    pl = build(CKPT_DIR=f"{TMP}/p12", **H, EVAL_GENERATE=0)
    loop.run(pl, max_windows=41, progress=False)
    _blob = torch.load(f"{TMP}/p12/ckpt.pt", map_location="cpu", weights_only=False)
    _had = ("eval" in _blob["payload"]["LOOP"], "reading_at" in _blob["payload"]["OPT"])
    _blob["payload"]["LOOP"].pop("eval", None)
    _blob["payload"]["OPT"].pop("reading_at", None)
    torch.save(_blob, f"{TMP}/p12/ckpt.pt")
    k_off = build(CKPT_RESUME=f"{TMP}/p12", CKPT_DIR=f"{TMP}/p12c", **H, EVAL_GENERATE=0)
    rk_off = loop.run(k_off, max_windows=59, progress=False)
    k_on = build(CKPT_RESUME=f"{TMP}/p12", CKPT_DIR=f"{TMP}/p12d", **EB)
    rk_on = loop.run(k_on, max_windows=59, progress=False)
    _warn = [w for w in rk_on.warnings if "ASSUMED" in w]
    check("P12 a checkpoint without LOOP.eval or OPT.reading_at (a probe-off parent's, with the key "
          "stripped as the tree before the probe wrote it) resumes exactly with the probe off and on",
          _had == (False, True) and rk_off.loss_curve == ru.loss_curve[41:100]
          and rk_on.loss_curve == ru.loss_curve[41:100]
          and k_off.optimizer.reading_at is None,
          f"had (LOOP.eval, OPT.reading_at) {_had}")
    check("P12 on, the parent's areas are ASSUMED arrived and said so once, and the start read reads "
          "them all as seen by the parent",
          len(_warn) == 1 and all(x in _warn[0] for x in ("eng", "py", "num", "c"))
          and rk_on.probe_series[0]["kind"] == "resume"
          and set(rk_on.probe_series[0]["areas"]) == set(ps.items)
          and all(v["seen_by_parent"] for v in rk_on.probe_series[0]["areas"].values())
          and not [w for w in rk_off.warnings if "ASSUMED" in w],
          _warn[0][:160] if _warn else "no warning")
    del pl, k_off, k_on, p, c

    # ---- P14: a non-finite reading is counted and not forwarded ------------------------------------
    _report_prefixes = {pre for it in ps.items.values() for _s, pre, _w in it["report"]}
    _control_prefixes = {pre for it in ps.items.values() for _s, pre, _w in it["control"]}
    _real_fn = loop._c_logits_fn

    def _planted(sysm, **kw):
        fn = _real_fn(sysm, **kw)

        def g(x, *, prefix_bytes):
            out = fn(x, prefix_bytes=prefix_bytes)
            if int(sysm.clock.step) == 21 or bytes(prefix_bytes[0]) in _report_prefixes:
                return torch.full_like(out, float("nan"))
            return out
        g.name = fn.name
        return g
    loop._c_logits_fn = _planted
    try:
        with spy_readings() as rd_n:
            n14 = build(**EB)
            rn = loop.run(n14, max_windows=45, progress=False)
    finally:
        loop._c_logits_fn = _real_fn
    sn = rn.probe_series
    _r21 = next(e for e in sn if e["step"] == 21)
    _u_by = {e["step"]: rd for e, rd in zip(su, rd_u) if e["kind"] != "boundary"}
    _n_by = {e["step"]: rd for e, rd in zip(sn, rd_n) if e["kind"] != "boundary"}
    check("P14 a reading whose every window is non-finite (planted at 21) is counted in "
          "eval.holdout.nonfinite and forwarded to no consumer: two readings reached CKPT, the alarm's "
          "series and System.probe_reading, the last at 41",
          _report_prefixes.isdisjoint(_control_prefixes)
          and book(rn).get("eval.holdout.nonfinite") == 1 and _r21["control"] is None
          and _r21["nonfinite"] == _r21["windows"] == 12
          and n14.retention.counters()["probes_seen"] == 2
          and len(n14.eval_carried["series"]["all"]) == 2 and n14.probe_reading.at == 41,
          f"reading at 21 {_r21['control']}, nonfinite {_r21['nonfinite']} of {_r21['windows']}")
    check("P4/P14 a report half planted non-finite at every reading moves no consumer input: the control "
          "means at 1 and 41 are the unplanted run's, window for window, and the report means are none",
          all(per_window(_n_by[s])[a][0] == per_window(_u_by[s])[a][0] for s in (1, 41)
              for a in _u_by[s].areas)
          and all(_n_by[s].report_mean is None and _n_by[s].nonfinite == 6 for s in (1, 41))
          and n14.probe_reading.value == _u_by[41].control_mean.value)
    del n14

    # ---- P3 (boundary): a boundary resume's start read is the parent's R read ----------------------
    # A SHORT EPOCH NEEDS A LARGER BLOCK: at DATA_STREAM_BYTES=20000 each area is generated at 10,000
    # bytes and the shipped 5% holds out 500, whose halves cannot hold a 129-byte window behind its
    # 192-byte prefix. 30% holds out 3,000.
    E6 = dict(EB, DATA_STREAM_BYTES="20000", RUN_EPOCHS="2", DATA_RESAMPLE="1",
              DATA_HOLDOUT_FRAC="0.3")
    with spy_readings() as rd_bp:
        bp = build(CKPT_DIR=f"{TMP}/p3e", **E6)
        _n_ep = int(_windows_in_epoch(bp))
        rbp = loop.run(bp, max_windows=_n_ep, progress=False)
    with spy_readings() as rd_bc:
        bc = build(CKPT_RESUME=f"{TMP}/p3e", CKPT_DIR=f"{TMP}/p3ec", **E6)
        rbc = loop.run(bc, max_windows=5, progress=False)
    _pb = [rd for e, rd in zip(rbp.probe_series, rd_bp) if e["kind"] == "boundary"]
    _cb = [rd for e, rd in zip(rbc.probe_series, rd_bc) if e["kind"] == "resume"]
    check(f"P3 a boundary resume (the parent stopped at its epoch boundary, {_n_ep}) reads at its start "
          f"what the parent's R read read, window for window through both closures, pairing to exactly 0",
          bp.probe_set.items and int(rbp.epochs) == 1 and bc.resume_pos is None
          and len(_pb) == len(_cb) == 2
          and all(per_window(a) == per_window(b) for a, b in zip(_pb, _cb))
          and all(v[1] == 0.0 for rd in _cb for halves in rd.paired.values() for v in halves.values()),
          f"epochs {rbp.epochs}, resume_pos {bc.resume_pos}, reads {len(_pb)}/{len(_cb)}")
    del bp, bc

    # =============================================================================================
    # P6: the best checkpoints
    # =============================================================================================
    d6 = f"{TMP}/p6"
    E6b = dict(EB, CKPT_BEST_KEEP=2)
    _before = dict(ckpt_api._SAVES)
    s6 = build(CKPT_DIR=d6, **E6b)
    r6 = loop.run(s6, max_windows=200, progress=False)
    _diff = {k: ckpt_api._SAVES.get(k, 0) - _before.get(k, 0) for k in ckpt_api._SAVES}
    st6 = s6.retention.state()
    _files = {sfx: os.path.isfile(f"{d6}/ckpt.pt{sfx}") and os.path.isfile(f"{d6}{sfx}.dyntok.json")
              for sfx in (".best", ".best1", ".best2")}
    _steps = {sfx: torch.load(f"{d6}/ckpt.pt{sfx}", map_location="cpu", weights_only=False)["step"]
              for sfx, ok in _files.items() if ok}
    check("P6 Saves.best and Saves.bestN moved (the process-global ledger diffed around the run), and "
          ".best, .best1 and .best2 are on disk with their vocabularies, each at the step Retention "
          "records for it",
          _diff["best"] >= 1 and _diff["bestN"] >= 2 and all(_files.values())
          and _steps.get(".best") == st6["best_step"]
          and all(_steps.get(f".best{k}") == v["step"] for k, v in st6["ring"]["slots"].items()),
          f"Saves.best={_diff['best']} Saves.bestN={_diff['bestN']} (this 200-window run's); files "
          f"{_files}; steps {_steps}; ring {st6['ring']}")
    rt = ckpt_api.Retention(keep=2, tol=0.02, saving=True)
    a1 = rt.consider(2.0, U.Windows(1))
    rt.note_saved(True)
    a2 = rt.consider(1.9, U.Windows(2))
    rt.note_saved(True)
    rt.note_saved(False, slot=a2.rotate_slot)
    _st = rt.state()
    a3 = rt.consider(1.8, U.Windows(3))
    check("P6 a refused slot save records no slot: the ring is empty and its pointer where it stood, "
          "the refusal counted, and the next low is ordered into the same slot",
          a1.save_best and a2.save_best and a2.rotate_slot == 1 and _st["ring"] == {"ordered": 0,
                                                                                   "slots": {}}
          and rt.counters()["saves_refused"] == 1 and a3.rotate_slot == 1,
          f"{_st['ring']}; next slot {a3.rotate_slot}")
    try:
        rt.note_saved(True, slot=2)
        check("P6 note_saved refuses an answer to a question consider did not ask", False, "accepted")
    except ValueError:
        check("P6 note_saved refuses an answer to a question consider did not ask", True)
    bs = int(st6["best_step"])
    n6 = min(20, 200 - bs)
    c6 = build(CKPT_RESUME=f"{d6}/ckpt.pt.best", CKPT_DIR=f"{TMP}/p6c", **E6b)
    _restored = c6.retention.state()
    _before_c = dict(ckpt_api._SAVES)
    rc6 = loop.run(c6, max_windows=n6, progress=False)
    _cdiff = ckpt_api._SAVES.get("best", 0) - _before_c.get("best", 0)
    _run_best, _news = _restored["best_bpb"], 0
    for e in rc6.probe_series:
        if e["kind"] in ("cadence", "phase") and e["control"] is not None and e["control"] < _run_best:
            _run_best, _news = e["control"], _news + 1
    check(f"P6 a resume of ckpt.pt.best (step {bs}) continues the run exactly from window {bs + 1}, "
          f"over {n6} windows",
          int(c6.snapshot.step) == bs and rc6.loss_curve == r6.loss_curve[bs:bs + n6],
          f"snapshot step {int(c6.snapshot.step)}")
    check("P6 M45: the child restored the parent's best, so its first reading was judged against it and "
          "not against 'no best yet' -- it saved a new best exactly as often as a reading beat the "
          "restored one",
          _restored["best_bpb"] is not None and _restored["best_step"] == bs and _cdiff == _news
          and c6.retention.counters()["new_bests"] == _news,
          f"restored best {_restored['best_bpb']} at {_restored['best_step']}; child best saves "
          f"{_cdiff}, beats {_news}")
    del s6, c6

    # =============================================================================================
    # P7 (in run): 'probe' and 'off' train the same losses
    # =============================================================================================
    E7 = dict(H, EVAL_RETENTION_EVERY=10, EVAL_GENERATE=0, OPT_LR_WAVELENGTH=20)
    s7p = build(OPT_DAMP_SOURCE="probe", **E7)
    r7p = loop.run(s7p, max_windows=120, progress=False)
    s7o = build(OPT_DAMP_SOURCE="off", **E7)
    r7o = loop.run(s7o, max_windows=120, progress=False)
    c7p, c7o = s7p.optimizer.counters, s7o.optimizer.counters
    check("P7 in-run, 'probe' and 'off' train float-exactly the same losses across restarts: a single "
          "seed's Reading never damps, and restart_amp stays 1.0 on both",
          r7p.loss_curve == r7o.loss_curve and c7p.get("opt.restart.detected", 0) >= 2
          and c7p.get("opt.restart.detected") == c7o.get("opt.restart.detected")
          and s7p.optimizer.restart_amp == 1.0 == s7o.optimizer.restart_amp
          and c7p.get("opt.restart.readings", 0) > 0 and c7o.get("opt.restart.readings") == 0
          and c7p.get("opt.restart.damped", 0) == 0,
          f"restarts {c7p.get('opt.restart.detected')}, readings probe {c7p.get('opt.restart.readings')} "
          f"off {c7o.get('opt.restart.readings')}, refused_n1 {c7p.get('opt.restart.damp_refused_n1')}")
    del s7p, s7o

    # =============================================================================================
    # P9: generation
    # =============================================================================================
    EG = dict(H, EVAL_RETENTION_EVERY=10, EVAL_GEN_LEN=12, EVAL_GEN_SAMPLES=2, MEM_BLEND_MAX=0)
    with spy_samples() as g1:
        s9 = build(**EG)
        r9 = loop.run(s9, max_windows=25, progress=False)
    with spy_samples() as g2:
        s9b = build(**EG)
        loop.run(s9b, max_windows=25, progress=False)

    def ids_of(smp):
        return {a: [r["generated"] for r in rows] for a, rows in smp.population.items()}
    _b9 = book(r9)
    check("P9 generation's sizes: both closures, the first EVAL_GEN_SAMPLES report-half windows of each "
          "arrived area, EVAL_GEN_LEN tokens each, booked as eval.generate.samples and .tokens",
          len(g1) == 2 and [s.closure for s in g1] == ["memory-off", "memory-on"]
          and all(s.size == 4 and s.per_domain == {"eng": 2, "py": 2}
                  and all(len(r["generated"]) == 12 for rows in s.population.values() for r in rows)
                  for s in g1)
          and _b9.get("eval.generate.samples") == 8 and _b9.get("eval.generate.tokens") == 96,
          f"{[(s.closure, s.size, s.per_domain) for s in g1]}; book {_b9.get('eval.generate.samples')}, "
          f"{_b9.get('eval.generate.tokens')}")
    check("P9 two runs generate the same text, and at MEM_BLEND_MAX=0 the two closures generate the same "
          "text (the memory-on closure is the memory-off one when blend is the identity)",
          [ids_of(s) for s in g1] == [ids_of(s) for s in g2] and ids_of(g1[0]) == ids_of(g1[1]))
    _all_ids = [t for s in g1 for rows in s.population.values() for r in rows for t in r["generated"]]
    check("P9 every generated id is one the vocabulary can print (below TOK.Vocabulary.size())",
          all(0 <= t < int(s9.vocab.size()) for t in _all_ids), f"max {max(_all_ids)}")
    r9b = loop.run(s9, max_windows=10, progress=False)
    check("P9 a second loop.run over one System does not raise and keeps its arrived areas",
          any(e["kind"] == "cadence" and set(e["areas"]) == {"eng", "py"} for e in r9b.probe_series),
          str([(e["step"], e["kind"], sorted(e["areas"])) for e in r9b.probe_series]))
    del s9, s9b
    dg = f"{TMP}/p9ck"

    def ckpt_files(gen):
        shutil.rmtree(dg, ignore_errors=True)
        for f in os.listdir(TMP):
            if f.startswith("p9ck.") and f.endswith(".json"):
                os.remove(os.path.join(TMP, f))
        s = build(CKPT_DIR=dg, EVAL_GENERATE=gen, **EG)
        loop.run(s, max_windows=25, progress=False)
        out = {}
        for f in sorted(os.listdir(dg)):
            with open(os.path.join(dg, f), "rb") as fh:
                out[f] = fh.read()
        for f in sorted(os.listdir(TMP)):
            if f.startswith("p9ck.") and f.endswith(".json"):
                with open(os.path.join(TMP, f), "rb") as fh:
                    out[f] = fh.read()
        return out
    _on, _off = ckpt_files(1), ckpt_files(0)
    check("P9 every file the run wrote -- the final checkpoint, the best ones and the vocabularies -- is "
          "byte-identical with EVAL_GENERATE on and off",
          _on == _off and "ckpt.pt" in _on and "ckpt.pt.best" in _on,
          f"files {sorted(_on)}; differing {[k for k in set(_on) | set(_off) if _on.get(k) != _off.get(k)]}")

    # =============================================================================================
    # P1 / P2: bit-identity on the three shapes
    # =============================================================================================
    _s0, _r0, s3, r3 = pair("transformer, WORLD_FEEDBACK=1, LM_DROPOUT=0.1, FAB_SOCIETY=1, 200 windows "
                            "at 20",
                            dict(H, LM_ARCH="transformer", WORLD_FEEDBACK=1, LM_DROPOUT=0.1, FAB_SOCIETY=1,
                                 EVAL_GENERATE=0), 20, max_windows=200, gen=False)
    # P2 on the dropout arm: a closure pass draws nothing and puts every submodule's mode back.
    _tops = _eval_modules(s3)
    for t in _tops:
        t.train()
    _flip = [m for t in _tops for m in t.modules()][1::3]
    for m in _flip:
        m.training = False
    _modes = [(m, m.training) for t in _tops for m in t.modules()]
    _u3 = _holdout_units(s3, set(s3.probe_set.items))
    _pre3, _w3 = _u3[sorted(_u3)[0]]["control"][0]
    _ids3 = list(loop._c_holdout_tokenize(s3)(_w3).ids)
    _moved = []
    for use_mem in (False, True):
        with rng.frozen_rng(strict=True) as fr:
            _logits_fn(s3, use_memory=use_mem)(torch.tensor([_ids3[:-1]]), prefix_bytes=[_pre3])
        _moved.append(fr.moved)
    check("P2 at LM_DROPOUT=0.1 a closure pass, either closure, moves no global random stream "
          "(frozen_rng) and puts every submodule's own training flag back",
          _moved == [False, False] and all(m.training == was for m, was in _modes)
          and any(was for _m, was in _modes) and any(not was for _m, was in _modes), str(_moved))
    del _s0, _r0, s3, r3
    pair("B3's shape (a full epoch with manage passes and a mid-epoch act) at 50",
         dict(H, FAB_MANAGE_EVERY=50, FAB_GRACE=2, TOK_GROW_EVERY=30, TOK_RETOK_EVERY=150,
              EVAL_GENERATE=0), 50, gen=False)
    s1a, r1a, s1b, r1b = pair("one full epoch at the shipped DATA_STREAM_BYTES (120000), at 50, generation "
                              "on", dict(H, DATA_STREAM_BYTES="120000"), 50, cadence_min=10)
    _bk = book(r1b)
    check("P9 on the full epoch, generation read all four areas: 4 x EVAL_GEN_SAMPLES (4) continuations "
          "per closure, EVAL_GEN_LEN (200) tokens each",
          _bk.get("eval.generate.samples") == 32 and _bk.get("eval.generate.tokens") == 6400,
          f"{_bk.get('eval.generate.samples')}, {_bk.get('eval.generate.tokens')}")
    del s1a, r1a, s1b, r1b

    # =============================================================================================
    # P15: the baseline workloads at the shipped defaults
    # =============================================================================================
    _env = dict(os.environ, OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    _pr15 = subprocess.run([sys.executable, os.path.join("tests", "test_baseline.py"), "B1", "B3", "B3r",
                            "B5"], cwd=os.path.abspath(_ROOT), env=_env, capture_output=True, text=True)
    _pass = [ln for ln in _pr15.stdout.splitlines() if ln.startswith("PASS  B")]
    check("P15 B1, B3, B3r and B5 reproduce their fixtures at the shipped defaults (tests/test_baseline.py)",
          _pr15.returncode == 0 and len(_pass) >= 4,
          (_pr15.stdout + _pr15.stderr)[-600:] if _pr15.returncode else " | ".join(x[:40] for x in _pass))
finally:
    # EVERY CHECKPOINT AND VOCABULARY THIS FILE WROTE IS UNDER TMP: a CKPT_DIR here is TMP/<name>, and
    # TOK writes its vocabulary beside it, as TMP/<name>.dyntok.json.
    shutil.rmtree(TMP, ignore_errors=True)

print(f"\n=== {len(FAILS)} failing ===")
sys.exit(1 if FAILS else 0)
