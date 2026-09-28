"""THE 'replay' DRAW: DATA_DRAW='replay' with DATA_REPLAY_SHARE and DATA_REPLAY_NEWEST, DATA_REHEARSE_PARENT,
and SR0's per-phase share gauges (register §8 3.3; Proposal 04 §1 item 2 and SR0; docs/04_CONTRACT.md
Q-DATA-10), driven through DATA's entry points and, for the resume known answers, through the real
composition root and loop, with real checkpoints written under a temporary directory.

    python3 tests/test_draw.py        # exit 0 = every check passed

WHY IT EXISTS. 'replay' is the hand-set rehearsal control the self-regulated draw has to beat, and the
toy's strongest result is 'replay' 0.27 against 'planned' (register O16 puts that pair first among the
GPU draw tests, §8 5.3). It is built OFF, so the first promise is that the shipped law draws what it
drew; the second is that 'replay' realises exactly what it plans, spread through each phase, the same
under every hash seed; the third is that a resume sees the same plan its parent drew under. Each check
below pins one of those. CPU establishes operation only: whether rehearsal protects anything is the
GPU pair's to say.

  D1  'planned' AND 'uniform' ARE THE LAWS THEY WERE: the stream on eight shapes (the shipped
      defaults, seed 1, 'uniform', DATA_SEG_CONTIG=1, an explicit schedule, the real source at
      'planned' and at 'uniform', and an epoch-1 redraw) hashes to the digest recorded at c872121,
      the tree before 'replay' existed; Plan.per_area_draw is the pre-change formula on six
      schedules, and Plan.shares is draw_stream's planned budget phase by phase; DATA_REHEARSE_PARENT=1
      under 'planned' and 'uniform' on a parent record leaves the Plan and the stream unchanged and its
      Gate says why; 'replay' on a schedule with no faded phase draws the planned stream byte for
      byte; under 'planned' every new count is ABSENT and both new Gates read UNREACHABLE naming the
      lever. (B1, B3, B3r, B5, B6 and B6r -- the shipped runs are the tree before this, bit for bit --
      are tests/test_baseline.py's, run before every commit.)
  D2  REALISATION: on the generated four-area schedule the faded phases' targets are the hand-computed
      8100 / 10950 / 10950 and 4050 / 4050 / 10950 / 10950 bytes; every phase's realised bytes per area
      equal its targets exactly, so Plan.per_area_draw == Stream.per_area_drawn and the exposure gates
      are exact and say so; phase 0, which has no faded area, is byte-identical to 'planned''s; each
      faded phase opens on the first area in Plan order (the tie at zero bytes laid); and at
      DATA_STREAM_BYTES=2,000,000 the faded share of each quarter of phases 1-3 is within 0.05 of
      0.27 (SR0: no front-loading). The same exactness at DATA_SEG_CONTIG=1, on the real source and
      in an epoch-1 redraw; the share gauges read planned == realised.
  D3  PYTHONHASHSEED: the stream's sha256 under 'replay' -- faded phases, a newest boost with a tie and
      parent rehearsal together -- is identical under PYTHONHASHSEED 0, 1 and random, in subprocesses
      (04's minor m1).
  D4  THE NEWEST RULE: DATA_REPLAY_NEWEST 0.34 at five live areas gives the newest 0.34 and each other
      live area 0.0975, beside the faded area's 0.27 (the critic's `replay_late` control); two areas
      arriving in one phase give the boost to the last in Plan order; a faded phase whose only live
      area is the newest gives it the whole live remainder and counts no boost; the boost's count is
      ABSENT at 0; a rounding tie is decided on the decimal (0.07 of 150 bytes is 10, not the float's
      11); DATA_REPLAY_SHARE + DATA_REPLAY_NEWEST above 1 is refused by name.
  D5  PARENT REHEARSAL: a pure-add child over eng,py scheduling 'py|py|py|py' under 'replay' at
      DATA_REHEARSE_PARENT=1 draws eng at 0.27 of every phase from its first byte; at 0, under
      'planned', or on a fresh run it draws none, and data.rehearse_parent says which; an area the
      parent declared and never drew is not rehearsed. End to end: a parent over eng, resumed at its
      epoch boundary by that child, with the R report's DATA(plan.gates) and DATA(plan.counters) rows
      -- the fired Gate's row carrying its arithmetic alone, as spine/gate.py::three_state renders
      the fired arm (its reason is run.py's startup line's).
  D6  CONTINUATION: a continuing mid-epoch resume under 'replay' continues exactly, and so does a
      rehearsing child's, whose plan is read off the lineage's record -- its Plan.parent_faded still
      (0,), the set its parent leg had, and not the () the Plan docstring claimed for a continuing
      resume until Q-DATA-10's review -- and so does that child's checkpoint with its
      drawn_assumed key stripped, as the builds before the review wrote it.
  D7  A DRAW CHANGE ACROSS A CONTINUING RESUME IS REFUSED BY THE STREAM DIGEST (Q-DATA-9): 'planned' to
      'replay', 'replay' to 'planned' and a DATA_REPLAY_SHARE change, each at the `segment` stage,
      naming the draw levers; DATA_REHEARSE_PARENT flipped under 'planned' redraws the same stream and
      continues.
  D8  THE REST OF THE SURFACE: the gauges' permille rule, a Plan whose targets do not fill a phase is
      refused rather than hung on, and a recorded parent area this run does not declare stays
      refused, naming the replay reservoir that is not built (NEW-06).
  D9  THE REVIEW OF Q-DATA-10 (2026-09-28), each on the tree before it driven wrong:
      (a) WHAT A REHEARSED SYNTHETIC BODY IS. At DATA_SYNTH_HOLDOUT=0 a child listing its parent's eng
      at another position (py,eng over eng,py) is admitted by the restore and REFUSED at data_plan
      when rehearsal would draw it, naming both positions and DATA_REHEARSE_PARENT=0; at 0 or under
      'planned' the same child plans as before; at another RUN_SEED, which no record carries, it is
      admitted with other text and the Gate's reason says RUN_SEED is not checked; five positions
      apart the alphabet is the same and so is the text (the shorter body a prefix of the longer);
      on the real source a reorder rehearses the parent's own text and the reason carries no
      synthetic sentence.
      (b) WHAT THE RECORD CAN VOUCH FOR. A record without the drawn list (an eng,py,num parent that
      drew eng alone) rehearses eng and num and the reason names both as held by ASSUMPTION, where
      the recorded list rehearses eng alone and names none; a rehearsing child's draws confirm what
      it drew; the assumption is CARRIED -- the child of the old record at the parent's schedule
      records py and num as still assumed, and its own child names num and not eng -- and a record
      carrying the list without the new key reads [] (and, end to end in D6, resumes exactly).
      (c) WHAT FIRED MEANS AT A SHARE THAT COMES TO NO BYTE. At DATA_REPLAY_SHARE=0.0 every faded
      area of every faded phase prints its gauge at 0 / 0, and Gate data.replay reads armed-but-zero
      (0 of 4) naming the phases, with data.replay.fixed_phases 0; where only some phases come to no
      byte it fires on the others and names the rest; the draw is still exact.
      (d) THE PROSE: data_plan's docstring declares the five Gates it builds, by name.

WHAT THIS FILE CANNOT SEE: whether rehearsal at 0.27 protects a faded area's held-out bits/byte. That
is §8 5.3's GPU pair and E1's (6.4), read through the retention probe.
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile

_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SRC = os.path.join(os.path.abspath(_ROOT), "src")
sys.path.insert(0, SRC)

import torch                                                       # noqa: E402
torch.set_num_threads(1)

from spine import lever as _lever                                  # noqa: E402
from spine import rng                                              # noqa: E402
from spine import loop                                             # noqa: E402
from spine import assemble                                         # noqa: E402
from spine.compose import compose, RefusedRun                      # noqa: E402
from spine.lever import LeverError                                 # noqa: E402
from data import api as data_api                                   # noqa: E402

FAILS = []
DATA_DIR = os.path.join(os.path.abspath(_ROOT), "data")
TMP = tempfile.mkdtemp(prefix="draw_")
# tests/test_continuation.py's small base at B6's 20,000-byte stream: 104 windows, four phases of 26.
BASE = {"DATA_STREAM_BYTES": "20000", "SIG_WARMUP": "20", "FAB_N0": "256", "FAB_SLOTS": "512",
        "DATA_DIR": DATA_DIR}
TWO = {"DATA_AREAS": "eng,py", "DATA_N_PROCESSES": "2"}

# THE STREAM ON EIGHT SHAPES AT c872121, the tree before 'replay' existed: sha256 over the bytes and
# the segment table (each start, its label, a separator), first 16 hex digits. Recorded by drawing
# each shape through that tree's DATA entry points; every one is a pure function of the seed, the
# DATA levers and, on the real source, data/train, so it is machine-independent.
PRE = {
    "default": ({}, 0, 0, "336cec32bd92eaef"),
    "seed1": ({}, 1, 0, "61c0928f4b7e6228"),
    "uniform": ({"DATA_DRAW": "uniform"}, 0, 0, "57bc76d27125b1eb"),
    "contig": ({"DATA_SEG_CONTIG": "1"}, 0, 0, "62df68d308be2ed8"),
    "explicit": ({"DATA_PHASE_SCHED": "c,eng|py|eng,num,c|py,c"}, 0, 0, "e4521dab69287fa7"),
    "real": ({"DATA_SOURCE": "real"}, 0, 0, "5406c276b3b81177"),
    "real_uniform": ({"DATA_SOURCE": "real", "DATA_DRAW": "uniform"}, 0, 0, "e49d242227f7c5b5"),
    "epoch1": ({"DATA_STREAM_BYTES": "20000", "RUN_EPOCHS": "2", "DATA_RESAMPLE": "1"}, 0, 1,
               "535857f36dad58b6"),
}


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" -- {detail}" if detail else ""))
    if not ok:
        FAILS.append(name)


def build(**env):
    _lever._reopen_assembly()
    rng.reset_issued()
    e = dict(BASE)
    e.update({k: str(v) for k, v in env.items()})
    return compose(environ=e)


def cfg(**env):
    """DATA's Config under `env` (DATA_DIR pinned), from assemble.build over a dict, never os.environ."""
    _lever._reopen_assembly()
    rng.reset_issued()
    e = {"RUN_SEED": "0", "RUN_DEVICE": "cpu", "DATA_DIR": DATA_DIR}
    e.update({k: str(v) for k, v in env.items()})
    cfgs, _w, warnings = assemble.build(e)
    if warnings:
        raise AssertionError(f"assemble.build warned on {e}: {warnings}")
    return cfgs["DATA"]


def draw(seed=0, epoch=0, parent=None, drawn=None, **env):
    """(areas, plan, stream) through DATA's three entry points, as a fresh run's; `parent` and `drawn`
    fill Areas.parent_names and Areas.drawn by hand, as restore_stream_state fills them."""
    d = cfg(**env)
    rng.reset_issued()
    areas = data_api.open_areas(d, seed=seed)
    if parent is not None:
        areas.parent_names[:] = list(parent)
        areas.drawn[:] = list(parent if drawn is None else drawn)
    plan = data_api.data_plan(d, areas, epochs=1, win_tokens=128, bytes_per_token=1.2)
    return areas, plan, data_api.draw_stream(d, areas, plan, epoch=epoch, seed=seed)


def digest(st):
    h = hashlib.sha256()
    h.update(st.bytes)
    for s in st.splice_starts:
        h.update(int(s).to_bytes(8, "little"))
        h.update(st.labels[s].encode())
        h.update(b"\0")
    return h.hexdigest()[:16]


def realised(areas, plan, st):
    """Per phase, {area name: bytes} read off Stream.labels -- the draw's split, recounted here."""
    out = []
    for lo, hi in plan.phase_bounds:
        got = {}
        for x in range(lo, hi):
            got[st.labels[x]] = got.get(st.labels[x], 0) + 1
        out.append(got)
    return out


def targets(areas, plan):
    """Per phase, {area name: bytes} as Plan.shares states them, zero targets left out."""
    return [{areas.names[i]: t for i, t in cut if t} for cut in plan.shares]


def gate(plan, name):
    return next((g for g in plan.gates if g.name == name), None)


def old_per_area_draw(names, bounds, schedule):
    """Plan.per_area_draw by the formula data_plan used before Plan.shares (c872121), written out."""
    out = {n: 0 for n in names}
    for (lo, hi), live in zip(bounds, schedule):
        span = hi - lo
        for j, idx in enumerate(live):
            out[names[idx]] += span // len(live) + (1 if j < span % len(live) else 0)
    return out


def planned_budget(span, live):
    b = {}
    for j, idx in enumerate(live):
        b[idx] = b.get(idx, 0) + span // len(live) + (1 if j < span % len(live) else 0)
    return tuple(sorted(b.items()))


NEW_KEYS = ("data.replay.fixed_phases", "data.replay.bytes", "data.replay.newest_boosted",
            "data.rehearse_parent.areas")


# ==================================================================================================
# D1 -- 'planned' and 'uniform' are the laws they were
# ==================================================================================================

def d1_the_old_laws():
    got = {}
    for name, (env, seed, epoch, want) in PRE.items():
        _a, _p, st = draw(seed=seed, epoch=epoch, **env)
        got[name] = (digest(st), want)
    check("D1 the stream on eight shapes (defaults, seed 1, 'uniform', DATA_SEG_CONTIG=1, an explicit "
          "schedule, the real source at 'planned' and 'uniform', an epoch-1 redraw) hashes to the "
          "digest the tree before 'replay' drew (c872121)",
          all(a == b for a, b in got.values()),
          "; ".join(f"{k}: {a}" + ("" if a == b else f" != {b}") for k, (a, b) in got.items()))
    shapes = ("", "0|0,1|0,1|1", "c,eng|py|eng,num,c|py,c", "0,1,2,3", "py|py|py|py", "1,0|2,3,1")
    same, budget = [], []
    for sched in shapes:
        a, p, _st = draw(DATA_PHASE_SCHED=sched)
        old = old_per_area_draw(list(a.names), p.phase_bounds, p.schedule)
        same.append(list(p.per_area_draw.items()) == list(old.items()))
        budget.append(all(p.shares[k] == planned_budget(hi - lo, live)
                          for k, ((lo, hi), live) in enumerate(zip(p.phase_bounds, p.schedule))))
    check("D1 Plan.per_area_draw is the pre-change formula, in the same key order, on six schedules "
          "(generated, rehearsed, explicit, stationary, pure-add, out of index order), and Plan.shares "
          "is draw_stream's planned budget phase by phase", all(same) and all(budget),
          f"per_area_draw {same}; shares {budget}")
    for law in ("planned", "uniform"):
        env = dict(TWO, DATA_PHASE_SCHED="py|py|py|py", DATA_DRAW=law)
        a0, p0, s0 = draw(parent=["eng"], **env)
        a1, p1, s1 = draw(parent=["eng"], DATA_REHEARSE_PARENT=1, **env)
        g = gate(p1, "data.rehearse_parent")
        check(f"D1 DATA_REHEARSE_PARENT=1 under '{law}' on a parent record changes nothing -- the same "
              f"Plan split, the same stream, no eng byte -- and data.rehearse_parent reads UNREACHABLE "
              f"naming 'no effect under DATA_DRAW={law}' (register 04-Q4)",
              p1.shares == p0.shares and p1.per_area_draw == p0.per_area_draw
              and p1.replay_faded == ((),) * 4 and p1.parent_faded == (0,) == p0.parent_faded
              and digest(s1) == digest(s0) and s1.per_area_drawn["eng"] == 0
              and g is not None and not g.reachable
              and f"has no effect under DATA_DRAW={law}" in g.reason
              and not any(k in p1.counters for k in NEW_KEYS),
              g.line() if g is not None else "no gate")
    for sched, why in (("0,1,2,3", "stationary"), ("py|py|py|py", "pure-add, a fresh run")):
        _a, pp, sp = draw(DATA_PHASE_SCHED=sched)
        _a, pr, sr = draw(DATA_PHASE_SCHED=sched, DATA_DRAW="replay")
        g = gate(pr, "data.replay")
        check(f"D1 'replay' on a schedule with no faded phase ({why}) draws the planned stream byte for "
              f"byte, with the planned split, and data.replay reads armed-but-zero (0 of "
              f"{len(pr.schedule)} phases) with data.replay.fixed_phases 0",
              sr.bytes == sp.bytes and sr.labels == sp.labels and pr.shares == pp.shares
              and g is not None and g.reachable and not g.fired and g.value == 0
              and pr.counters.get("data.replay.fixed_phases") == 0
              and pr.counters.get("data.replay.bytes") == 0, g.line() if g else "no gate")
    a, p, st = draw()
    gr, gp = gate(p, "data.replay"), gate(p, "data.rehearse_parent")
    check("D1 under 'planned' every new count is ABSENT, Plan.replay_faded is empty in every phase, and "
          "both new Gates read UNREACHABLE naming DATA_DRAW=planned and DATA_REHEARSE_PARENT=0",
          not any(k in p.counters for k in NEW_KEYS) and p.replay_faded == ((),) * 4
          and gr is not None and not gr.reachable and "DATA_DRAW=planned" in gr.reason
          and gp is not None and not gp.reachable and "DATA_REHEARSE_PARENT=0" in gp.reason,
          f"{gr.line() if gr else None} | {gp.line() if gp else None}")
    gauge = {k: v for k, v in st.counters.items() if k.startswith("data.share.")}
    want = {}
    for k, cut in enumerate(p.shares):
        for i, t in cut:
            want[f"data.share.p{k}.{a.names[i]}.planned"] = (2000 * t + 30000) // 60000
            want[f"data.share.p{k}.{a.names[i]}.realised"] = (2000 * t + 30000) // 60000
    check("D1 under 'planned' the share gauges print every live area of every phase, planned == "
          "realised (500 permille each at the shipped two live areas per phase)",
          gauge == want and set(gauge.values()) == {500}, str(sorted(gauge.items())[:4]))
    a, p, st = draw(DATA_DRAW="uniform")
    rl = realised(a, p, st)
    ok = True
    for k, cut in enumerate(p.shares):
        span = p.phase_bounds[k][1] - p.phase_bounds[k][0]
        for i, t in cut:
            nm = a.names[i]
            ok = ok and st.counters.get(f"data.share.p{k}.{nm}.planned") == (2000 * t + span) // (2 * span)
            ok = ok and st.counters.get(f"data.share.p{k}.{nm}.realised") == \
                (2000 * rl[k].get(nm, 0) + span) // (2 * span)
    differs = any(st.counters[f"data.share.p{k}.{a.names[i]}.planned"]
                  != st.counters[f"data.share.p{k}.{a.names[i]}.realised"]
                  for k, cut in enumerate(p.shares) for i, _t in cut)
    check("D1 under 'uniform' the gauges print the scheduled split as planned and the draw's own split "
          "as realised, recounted here from Stream.labels, and they differ: the draw's error bar, per "
          "phase", ok and differs)


# ==================================================================================================
# D2 -- realisation
# ==================================================================================================

def d2_realisation():
    a, p, st = draw(DATA_DRAW="replay")
    _a0, p0, s0 = draw()
    want = (((0, 15000), (1, 15000)),
            ((0, 8100), (1, 10950), (2, 10950)),
            ((0, 8100), (1, 10950), (2, 10950)),
            ((0, 4050), (1, 4050), (2, 10950), (3, 10950)))
    check("D2 the faded phases' targets are the hand-computed ones: round(0.27 x 30000) = 8100 to eng, "
          "the rest split evenly (10950 each); phase 3's 8100 split eng 4050 / py 4050; phase 0 has "
          "no faded area and keeps the planned 15000 / 15000",
          p.shares == want and p.replay_faded == ((), (0,), (0,), (0, 1))
          and p.counters.get("data.replay.fixed_phases") == 3
          and p.counters.get("data.replay.bytes") == 24300, str(p.shares))
    check("D2 every phase's realised bytes per area equal its targets exactly, and "
          "Plan.per_area_draw == Stream.per_area_drawn",
          realised(a, p, st) == targets(a, p) and dict(p.per_area_draw) == dict(st.per_area_drawn),
          f"{dict(st.per_area_drawn)} against {dict(p.per_area_draw)}")
    b0 = p.phase_bounds[0][1]
    check("D2 phase 0 has no faded area and is byte-identical to 'planned''s, labels and splices too",
          st.bytes[:b0] == s0.bytes[:b0] and st.labels[:b0] == s0.labels[:b0]
          and [x for x in st.splice_starts if x < b0] == [x for x in s0.splice_starts if x < b0]
          and st.bytes != s0.bytes)
    firsts = [st.labels[lo] for k, (lo, _hi) in enumerate(p.phase_bounds) if p.replay_faded[k]]
    check("D2 each faded phase opens on the first area in Plan order with a target -- the tie every "
          "area's deficit makes at zero bytes laid", firsts == ["eng", "eng", "eng"], str(firsts))
    gx, gs = gate(p, "data.exposure_max"), gate(p, "data.exposure_skew")
    check("D2 the exposure gates are computed on the replay split and their reason says EXACT under "
          "DATA_DRAW=replay",
          gx is not None and gs is not None and "EXACT" in gx.reason and "DATA_DRAW=replay" in gx.reason
          and gx.value == round(max(p.exposure.values()), 4)
          and abs(p.exposure["eng"] - 35250 / len(a.bodies["eng"])) < 1e-12, gx.line())
    gauge_ok = all(st.counters.get(f"data.share.p{k}.{a.names[i]}.planned")
                   == st.counters.get(f"data.share.p{k}.{a.names[i]}.realised")
                   for k, cut in enumerate(p.shares) for i, _t in cut)
    check("D2 the share gauges read planned == realised in every phase (eng 270 permille in phases 1-2, "
          "eng and py 135 in phase 3)",
          gauge_ok and st.counters.get("data.share.p1.eng.planned") == 270
          and st.counters.get("data.share.p3.py.realised") == 135)
    a, p, st = draw(DATA_DRAW="replay", DATA_STREAM_BYTES=2000000)
    worst, shares_q = 0.0, []
    for k in (1, 2, 3):
        lo, hi = p.phase_bounds[k]
        faded = {a.names[i] for i in p.replay_faded[k]}
        for q in range(4):
            qlo, qhi = lo + (hi - lo) * q // 4, lo + (hi - lo) * (q + 1) // 4
            share = sum(1 for x in range(qlo, qhi) if st.labels[x] in faded) / (qhi - qlo)
            shares_q.append(round(share, 4))
            worst = max(worst, abs(share - 0.27))
    check("D2 at DATA_STREAM_BYTES=2,000,000 the faded share of each quarter of phases 1-3 is within "
          "0.05 of 0.27 (SR0's no-front-loading known answer), and the phases are still exact",
          worst < 0.05 and realised(a, p, st) == targets(a, p),
          f"worst {worst:.4f} over quarters {shares_q}")
    for tag, env, epoch in (("DATA_SEG_CONTIG=1", {"DATA_SEG_CONTIG": "1"}, 0),
                            ("the real source", {"DATA_SOURCE": "real"}, 0),
                            ("an epoch-1 redraw", {"RUN_EPOCHS": "2", "DATA_RESAMPLE": "1"}, 1)):
        a, p, st = draw(epoch=epoch, DATA_DRAW="replay", **env)
        check(f"D2 exact at {tag} too: every phase's realised bytes are its targets",
              realised(a, p, st) == targets(a, p) and dict(p.per_area_draw) == dict(st.per_area_drawn))


# ==================================================================================================
# D3 -- the same stream under every hash seed
# ==================================================================================================

_D3 = r"""
import hashlib, sys
sys.path.insert(0, SRC)
from spine import assemble
from data import api as data_api
env = {"RUN_SEED": "0", "RUN_DEVICE": "cpu", "DATA_AREAS": "eng,py,num,c,rust",
       "DATA_N_PROCESSES": "5", "DATA_PHASE_SCHED": "py,num|num,c,rust|c,rust|rust",
       "DATA_DRAW": "replay", "DATA_REPLAY_NEWEST": "0.2", "DATA_REHEARSE_PARENT": "1"}
d = assemble.build(env)[0]["DATA"]
areas = data_api.open_areas(d, seed=0)
areas.parent_names[:] = ["eng"]
areas.drawn[:] = ["eng"]
plan = data_api.data_plan(d, areas, epochs=1, win_tokens=128, bytes_per_token=1.2)
st = data_api.draw_stream(d, areas, plan, epoch=0, seed=0)
h = hashlib.sha256(st.bytes)
for s in st.splice_starts:
    h.update(int(s).to_bytes(8, "little")); h.update(st.labels[s].encode()); h.update(b"\0")
print(h.hexdigest(), plan.replay_faded, plan.counters.get("data.replay.newest_boosted"))
"""


def d3_hash_seeds():
    outs = {}
    for seed in ("0", "1", "random", "random"):
        env = dict(os.environ, PYTHONHASHSEED=seed, OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
        r = subprocess.run([sys.executable, "-c", f"SRC = {SRC!r}\n" + _D3], cwd=TMP, env=env,
                           capture_output=True, text=True, timeout=600)
        outs.setdefault(seed, []).append(r.stdout.strip() if r.returncode == 0 else
                                         f"exit {r.returncode}: {r.stderr.strip()[-300:]}")
    vals = [v for vs in outs.values() for v in vs]
    check("D3 the stream under 'replay' -- faded phases, parent rehearsal from window 0 and a newest "
          "boost whose two newest areas tie -- is identical under PYTHONHASHSEED 0, 1 and random (twice), "
          "each in its own process",
          len(set(vals)) == 1 and not vals[0].startswith("exit") and "((0,), (0, 1)," in vals[0],
          str(outs))


# ==================================================================================================
# D4 -- the newest rule, rounding, and the refusal
# ==================================================================================================

def d4_newest():
    six = {"DATA_AREAS": "a,b,c,d,e,f", "DATA_N_PROCESSES": "6", "DATA_STREAM_BYTES": "200000",
           "DATA_PHASE_SCHED": "0,1,2,3,4|1,2,3,4,5", "DATA_DRAW": "replay"}
    a, p, st = draw(DATA_REPLAY_NEWEST=0.34, **six)
    g = gate(p, "data.replay")
    check("D4 DATA_REPLAY_NEWEST 0.34 at five live areas: the newest (f, live from phase 1) takes "
          "34000 of phase 1's 100000 bytes, each other live area 9750 (0.0975) and the faded a 27000 "
          "(0.27) -- the critic's replay_late control -- realised exactly, with "
          "data.replay.newest_boosted 1 and the boost in data.replay's reason",
          p.shares[1] == ((0, 27000), (1, 9750), (2, 9750), (3, 9750), (4, 9750), (5, 34000))
          and realised(a, p, st) == targets(a, p)
          and p.counters.get("data.replay.newest_boosted") == 1
          and "DATA_REPLAY_NEWEST=0.34" in g.reason, str(p.shares[1]))
    _a, p0, _s = draw(**six)
    check("D4 at DATA_REPLAY_NEWEST=0 the boost is OFF and its count ABSENT, the live areas splitting "
          "the 73000 evenly (14600 each)",
          "data.replay.newest_boosted" not in p0.counters
          and p0.shares[1] == ((0, 27000), (1, 14600), (2, 14600), (3, 14600), (4, 14600), (5, 14600)),
          str(p0.shares[1]))
    three = {"DATA_AREAS": "a,b,c", "DATA_N_PROCESSES": "3", "DATA_STREAM_BYTES": "200000",
             "DATA_PHASE_SCHED": "0|1,2", "DATA_DRAW": "replay", "DATA_REPLAY_NEWEST": "0.34"}
    _a, pt, _s = draw(**three)
    check("D4 two live areas arriving in one phase: the boost goes to the last in Plan order (c), the "
          "other takes the rest (b 39000), the faded a 27000",
          pt.shares[1] == ((0, 27000), (1, 39000), (2, 34000)), str(pt.shares[1]))
    _a, pa, _s = draw(**dict(three, DATA_PHASE_SCHED="0|1"))
    check("D4 a faded phase whose only live area is the newest gives it the whole live remainder "
          "(73000, not 34000) and counts no boost: data.replay.newest_boosted reads 0, armed",
          pa.shares[1] == ((0, 27000), (1, 73000))
          and pa.counters.get("data.replay.newest_boosted") == 0, str(pa.shares[1]))
    _a, pr, _s = draw(DATA_AREAS="a,b", DATA_N_PROCESSES="2", DATA_STREAM_BYTES="300",
                      DATA_PHASE_SCHED="0|1", DATA_DRAW="replay", DATA_REPLAY_SHARE="0.07")
    check("D4 a rounding tie is decided on the DECIMAL the lever holds: 0.07 of a 150-byte phase is "
          "10.5 and rounds half to even to 10 bytes (the float product 10.500000000000002 would round "
          "to 11), and the phase still fills its 150 bytes",
          pr.shares[1] == ((0, 10), (1, 140)) and round(0.07 * 150) == 11, str(pr.shares[1]))
    try:
        draw(DATA_REPLAY_SHARE=0.7, DATA_REPLAY_NEWEST=0.31, DATA_DRAW="replay")
        check("D4 DATA_REPLAY_SHARE + DATA_REPLAY_NEWEST above 1 is refused", False, "planned")
    except LeverError as e:
        check("D4 DATA_REPLAY_SHARE + DATA_REPLAY_NEWEST above 1 is refused at data_plan by name, and "
              "their sum at exactly 1 is not",
              "DATA_REPLAY_SHARE=0.7" in str(e) and "DATA_REPLAY_NEWEST=0.31" in str(e)
              and draw(DATA_REPLAY_SHARE=0.7, DATA_REPLAY_NEWEST=0.3, DATA_DRAW="replay")[1] is not None,
              str(e)[:120])


# ==================================================================================================
# D5 -- parent rehearsal
# ==================================================================================================

def d5_rehearse_parent():
    env = dict(TWO, DATA_PHASE_SCHED="py|py|py|py", DATA_STREAM_BYTES="20000", DATA_DRAW="replay")
    a, p, st = draw(parent=["eng"], DATA_REHEARSE_PARENT=1, **env)
    g = gate(p, "data.rehearse_parent")
    fracs = [round(r.get("eng", 0) / 5000, 4) for r in realised(a, p, st)]
    check("D5 a pure-add child over eng,py at 'py|py|py|py' under 'replay' at DATA_REHEARSE_PARENT=1 "
          "rehearses its parent's eng from window 0: 1350 of every 5000-byte phase (0.27), from the "
          "stream's first byte, with data.rehearse_parent FIRED (1 vs 1) and data.rehearse_parent.areas 1",
          p.parent_faded == (0,) and p.replay_faded == ((0,),) * 4 and fracs == [0.27] * 4
          and st.labels[0] == "eng" and realised(a, p, st) == targets(a, p)
          and g is not None and g.fired and (g.value, g.threshold) == (1, 1)
          and p.counters.get("data.rehearse_parent.areas") == 1
          and p.counters.get("data.replay.fixed_phases") == 4, f"{fracs}; {g.line() if g else None}")
    for tag, kw, why in (("DATA_REHEARSE_PARENT=0", {"parent": ["eng"]}, "DATA_REHEARSE_PARENT=0"),
                         ("'planned'", {"parent": ["eng"], "DATA_REHEARSE_PARENT": 1,
                                        "DATA_DRAW": "planned"}, "no effect under DATA_DRAW=planned"),
                         ("a fresh run", {"DATA_REHEARSE_PARENT": 1}, "no parent record: a fresh run")):
        e = dict(env)
        e.update({k: v for k, v in kw.items() if k != "parent"})
        a, p, st = draw(parent=kw.get("parent"), **e)
        g = gate(p, "data.rehearse_parent")
        check(f"D5 at {tag} the child draws no eng byte, data.rehearse_parent.areas is ABSENT and "
              f"data.rehearse_parent reads UNREACHABLE saying '{why}'",
              st.per_area_drawn["eng"] == 0 and "data.rehearse_parent.areas" not in p.counters
              and g is not None and not g.reachable and why in g.reason, g.line() if g else "no gate")
    a, p, st = draw(parent=["eng", "num"], drawn=["eng"], DATA_REHEARSE_PARENT=1,
                    **dict(env, DATA_AREAS="eng,py,num", DATA_N_PROCESSES="3"))
    check("D5 an area the parent declared and never drew (num) is not rehearsed: only eng, the one its "
          "streams drew, is faded from window 0",
          p.parent_faded == (0,) and st.per_area_drawn["num"] == 0 and st.per_area_drawn["eng"] == 5400,
          f"{p.parent_faded} {dict(st.per_area_drawn)}")
    a, p, st = draw(parent=["eng"], DATA_REHEARSE_PARENT=1, **dict(env, DATA_PHASE_SCHED="eng|py|py|py"))
    g = gate(p, "data.rehearse_parent")
    check("D5 a child that schedules its parent's area makes nothing faded from window 0: "
          "data.rehearse_parent is armed-but-zero (0 vs 1), and eng is rehearsed as the schedule's own "
          "faded area from phase 1",
          p.parent_faded == () and g is not None and g.reachable and not g.fired
          and (g.value, g.threshold) == (0, 1) and p.replay_faded == ((), (0,), (0,), (0,))
          and p.counters.get("data.rehearse_parent.areas") == 0, g.line() if g else "no gate")


def d5_d6_end_to_end():
    """The parent and the rehearsing child through compose, and both continuations."""
    par = build(CKPT_DIR=f"{TMP}/g", DATA_PHASE_SCHED="eng|eng|eng|eng", **TWO)
    loop.run(par, progress=False)
    kid_env = dict(TWO, CKPT_RESUME=f"{TMP}/g", DATA_PHASE_SCHED="py|py|py|py", RUN_EPOCHS=2,
                   DATA_RESAMPLE=1, DATA_DRAW="replay", DATA_REHEARSE_PARENT=1)
    kid = build(**kid_env)
    fracs = [round(r.get("eng", 0) / 5000, 4) for r in realised(kid.areas, kid.plan, kid.stream)]
    rk = loop.run(kid, progress=False)
    pg, pc = rk.report.get("DATA(plan.gates)") or {}, rk.report.get("DATA(plan.counters)") or {}
    check("D5 end to end: a parent over eng, resumed at its epoch boundary by the pure-add child at "
          "'replay' and DATA_REHEARSE_PARENT=1 -- the child's epoch-1 stream holds eng at 0.27 of every "
          "phase from its first byte, the R report's DATA(plan.gates) reads data.rehearse_parent and "
          "data.replay fired, the first as ('fired', '1 vs 1') with no reason (three_state keeps none "
          "on the fired arm, as spine/loop.py's comment now says), and DATA(plan.counters) "
          "data.rehearse_parent.areas 1, and the loss is finite",
          kid.plan.parent_faded == (0,) and fracs == [0.27] * 4 and kid.stream.labels[0] == "eng"
          and pg.get("gate:data.rehearse_parent") == ("fired", "1 vs 1")
          and (pg.get("gate:data.replay") or ("",))[0] == "fired"
          and pc.get("data.rehearse_parent.areas") == 1 and pc.get("data.parent_faded") == ["eng"]
          and rk.loss_curve and all(x == x for x in rk.loss_curve),
          f"eng fractions {fracs}; gates {pg.get('gate:data.rehearse_parent')}")
    for tag, over in (("DATA_REHEARSE_PARENT=0", {"DATA_REHEARSE_PARENT": 0}),
                      ("'planned'", {"DATA_DRAW": "planned"})):
        k0 = build(**dict(kid_env, **over))
        check(f"D5 end to end at {tag}: the same child's stream holds no eng byte",
              k0.stream.per_area_drawn["eng"] == 0 and k0.plan.parent_faded == (0,))
    # D6 -- the rehearsing child, saved mid-epoch and continued.
    kp = build(CKPT_DIR=f"{TMP}/kp", **kid_env)
    rp = loop.run(kp, max_windows=50, progress=False)
    kc = build(**dict(kid_env, CKPT_RESUME=f"{TMP}/kp", CKPT_DIR=f"{TMP}/kc"))
    rc = loop.run(kc, progress=False)
    check("D6 the rehearsing child saved mid-epoch at window 50 and continued by a second process "
          "continues exactly: its plan is read off the lineage's record (drawn eng and py; eng still "
          "faded from window 0, Plan.parent_faded (0,) -- the set its parent leg had, not the () the "
          "Plan docstring claimed for a continuing resume), its redrawn stream passes the digest, and "
          "its losses are the uninterrupted child's",
          kc.resume_pos is not None and kc.plan.shares == kid.plan.shares
          and kc.plan.parent_faded == kid.plan.parent_faded == (0,)
          and kc.plan.replay_faded == ((0,),) * 4
          and list(kc.areas.drawn) == ["eng", "py"]
          and rp.loss_curve == rk.loss_curve[:50] and rc.loss_curve == rk.loss_curve[50:],
          f"resume_pos {kc.resume_pos}; parent_faded {kc.plan.parent_faded}; drawn "
          f"{list(kc.areas.drawn)}; losses "
          f"{rp.loss_curve == rk.loss_curve[:50]} / {rc.loss_curve == rk.loss_curve[50:]}")
    # R12: THE NEW STATE KEY DEFAULTS WHEN ABSENT (2026-09-28, Q-DATA-10's review). The same checkpoint
    # with `drawn_assumed` stripped from DATA's record, as c872121 and d9900c6 wrote it, resumes and
    # continues exactly, reading no assumption.
    blob = torch.load(f"{TMP}/kp/ckpt.pt", map_location="cpu", weights_only=False)
    had = blob["payload"]["DATA"].pop("drawn_assumed", "absent")
    torch.save(blob, f"{TMP}/kp/ckpt.pt")
    ks = build(**dict(kid_env, CKPT_RESUME=f"{TMP}/kp", CKPT_DIR=f"{TMP}/ks"))
    rs = loop.run(ks, progress=False)
    check("D6 the rehearsing child's checkpoint with DATA's drawn_assumed key stripped (it held [], "
          "every area the lineage drew having been drawn) resumes, reads data.drawn_assumed [] and an "
          "empty Areas.drawn_assumed, plans the same split and continues exactly",
          had == [] and ks.resume_pos is not None and list(ks.areas.drawn_assumed) == []
          and ks.areas.counters.get("data.drawn_assumed") == [] and ks.plan.shares == kid.plan.shares
          and rs.loss_curve == rk.loss_curve[50:],
          f"stripped {had!r}; resume_pos {ks.resume_pos}; assumed {list(ks.areas.drawn_assumed)}; "
          f"losses {rs.loss_curve == rk.loss_curve[50:]}")


def d6_d7_continuation():
    u = build(DATA_DRAW="replay")
    ru = loop.run(u, progress=False)
    p = build(CKPT_DIR=f"{TMP}/rp", DATA_DRAW="replay")
    rp = loop.run(p, max_windows=60, progress=False)
    c = build(CKPT_RESUME=f"{TMP}/rp", CKPT_DIR=f"{TMP}/rc", DATA_DRAW="replay")
    rc = loop.run(c, progress=False)
    check("D6 a continuing mid-epoch resume under 'replay' at window 60 (phase 2, a faded phase) "
          "continues exactly: the child's Plan is the parent's and its losses are the uninterrupted "
          "run's",
          c.resume_pos is not None and c.plan.shares == u.plan.shares
          and rp.loss_curve == ru.loss_curve[:60] and rc.loss_curve == ru.loss_curve[60:],
          f"resume_pos {c.resume_pos}")
    q = build(CKPT_DIR=f"{TMP}/pp")
    loop.run(q, max_windows=60, progress=False)
    for tag, src, env, words in (
            ("'planned' -> 'replay'", "pp", {"DATA_DRAW": "replay"}, ("digest", "DATA_DRAW=replay")),
            ("'replay' -> 'planned'", "rp", {}, ("digest", "DATA_DRAW=planned",
                                                 "DATA_REPLAY_SHARE=0.27")),
            ("DATA_REPLAY_SHARE 0.27 -> 0.3", "rp", {"DATA_DRAW": "replay", "DATA_REPLAY_SHARE": "0.3"},
             ("digest", "DATA_REPLAY_SHARE=0.3", "DATA_REPLAY_NEWEST=0.0",
              "DATA_REHEARSE_PARENT=0"))):
        try:
            build(CKPT_RESUME=f"{TMP}/{src}", CKPT_DIR=f"{TMP}/x", **env)
            check(f"D7 a continuing resume across {tag} is refused", False, "composed")
        except RefusedRun as e:
            check(f"D7 a continuing resume across {tag} is refused by the stream digest at the "
                  f"`segment` stage, before the model exists, naming {', '.join(words)}",
                  e.stage == "segment" and e.system.model is None
                  and all(w in e.refusals[0] for w in words), e.refusals[0][:200])
    k = build(CKPT_RESUME=f"{TMP}/pp", CKPT_DIR=f"{TMP}/y", DATA_REHEARSE_PARENT=1)
    check("D7 DATA_REHEARSE_PARENT flipped to 1 under 'planned' redraws the parent's stream and "
          "continues: no refusal, a continuing resume position, the parent's bytes",
          k.resume_pos is not None and k.stream.bytes == q.stream.bytes)


# ==================================================================================================
# D8 -- the rest of the surface
# ==================================================================================================

def d8_surface():
    check("D8 the gauges' permille is rounded half up in integers: 1 of 2000 bytes is 1 permille, "
          "1 of 2001 is 0, 1350 of 5000 is 270, a whole phase 1000",
          [data_api._permille(n, w) for n, w in ((1, 2000), (1, 2001), (1350, 5000), (7, 7))]
          == [1, 0, 270, 1000])
    a, p, _st = draw(DATA_DRAW="replay")
    bad = data_api.Plan(protocol=p.protocol, schedule=p.schedule, phase_bounds=p.phase_bounds,
                        per_area_draw=p.per_area_draw, exposure=p.exposure, gates=p.gates,
                        counters=p.counters, faded=p.faded, parent_faded=p.parent_faded,
                        shares=p.shares[:1] + (((0, 100), (1, 100), (2, 100)),) + p.shares[2:],
                        replay_faded=p.replay_faded)
    d = cfg(DATA_DRAW="replay")
    rng.reset_issued()
    try:
        data_api.draw_stream(d, a, bad, epoch=0, seed=5)
        check("D8 a Plan whose replay targets do not fill a phase is refused", False, "drew")
    except data_api.CorpusError as e:
        check("D8 a Plan whose replay targets do not fill a phase is refused by name at the byte where "
              "they run out, rather than handed a zero-byte segment and hung on",
              "phase 1 holds 300 of its 30000 bytes" in str(e), str(e)[:140])
    d = cfg(**TWO)
    rng.reset_issued()
    areas = data_api.open_areas(d, seed=0)
    state = {"holdout": {"eng": {"offset": 0, "size": 0, "key": None},
                         "c": {"offset": 0, "size": 0, "key": None}},
             "cursors": {"eng": 0, "c": 0}}
    try:
        data_api.restore_stream_state(d, areas, state)
        check("D8 a recorded parent area this run does not declare is refused", False, "restored")
    except data_api.CorpusError as e:
        check("D8 a recorded parent area this run does not declare stays refused, and the refusal names "
              "the replay reservoir that is not built (register NEW-06) and DATA_REHEARSE_PARENT",
              "'c'" in str(e) and "NEW-06" in str(e) and "DATA_REHEARSE_PARENT" in str(e)
              and "not built" in str(e), str(e)[:160])


# ==================================================================================================
# D9 -- the review of Q-DATA-10
# ==================================================================================================

def leg(state=None, seed=0, **env):
    """(areas, plan, stream, record) for one run through DATA's five entry points, as the root calls
    them: open_areas, restore_stream_state on `state` where one is given, data_plan, draw_stream and
    stream_state -- so a record written here is what the next leg's restore reads."""
    d = cfg(**env)
    rng.reset_issued()
    areas = data_api.open_areas(d, seed=seed)
    if state is not None:
        data_api.restore_stream_state(d, areas, state)
    plan = data_api.data_plan(d, areas, epochs=1, win_tokens=128, bytes_per_token=1.2)
    st = data_api.draw_stream(d, areas, plan, epoch=0, seed=seed)
    return areas, plan, st, data_api.stream_state(d, areas)


def d9a_synthetic_body():
    small = {"DATA_STREAM_BYTES": "20000"}
    pa, _pp, _ps, rec = leg(**dict(TWO, DATA_PHASE_SCHED="eng|eng|eng|eng", **small))
    kid = dict(small, DATA_PHASE_SCHED="py|py|py|py", DATA_DRAW="replay", DATA_REHEARSE_PARENT=1)
    # THE PARENT'S eng AT ANOTHER POSITION: the restore admits it at DATA_SYNTH_HOLDOUT=0, and the
    # plan refuses the rehearsal by name.
    d = cfg(**dict(kid, DATA_AREAS="py,eng", DATA_N_PROCESSES="2"))
    rng.reset_issued()
    ka = data_api.open_areas(d, seed=0)
    data_api.restore_stream_state(d, ka, rec)
    try:
        data_api.data_plan(d, ka, epochs=1, win_tokens=128, bytes_per_token=1.2)
        check("D9 a moved synthetic parent area is refused when rehearsed", False, "planned")
    except data_api.CorpusError as e:
        msg = str(e)
        check("D9 at DATA_SYNTH_HOLDOUT=0 a child listing its parent's eng at another position (py,eng "
              "over eng,py) is admitted by the restore -- its eng body is other text -- and REFUSED at "
              "data_plan when DATA_REHEARSE_PARENT=1 under 'replay' would rehearse it, naming the area, "
              "both positions and area lists, DATA_REHEARSE_PARENT=0 and RUN_SEED",
              ka.bodies["eng"][:64] != pa.bodies["eng"][:64] and list(ka.drawn) == ["eng"]
              and "'eng' at position 1 of this run's areas, where the checkpoint had it at 0" in msg
              and "py, eng" in msg and "eng, py" in msg and "DATA_REHEARSE_PARENT=0" in msg
              and "RUN_SEED" in msg, msg[:220])
    for tag, over in (("DATA_REHEARSE_PARENT=0", {"DATA_REHEARSE_PARENT": 0}),
                      ("'planned'", {"DATA_DRAW": "planned"})):
        a, p, st, _r = leg(rec, **dict(kid, DATA_AREAS="py,eng", DATA_N_PROCESSES="2", **over))
        check(f"D9 the same moved child at {tag} plans and draws as before the review: no refusal, eng "
              f"faded from window 0 (FAB's reading) and not one byte of it drawn",
              p.parent_faded == (1,) and st.per_area_drawn["eng"] == 0)
    a, p, st, _r = leg(rec, seed=1, **dict(TWO, **kid))
    g = gate(p, "data.rehearse_parent")
    check("D9 at another RUN_SEED, which no record carries, the child is admitted and rehearses other "
          "text under the parent's eng (the known limit), and data.rehearse_parent's fired reason says "
          "the body is the parent's only at the parent's RUN_SEED, which is not checked",
          a.bodies["eng"][:64] != pa.bodies["eng"][:64] and g is not None and g.fired
          and "RUN_SEED, which no record carries, so it is not checked" in g.reason
          and "DATA_SOURCE=synthetic" in g.reason, g.line()[:240] if g else "no gate")
    a, p, st, _r = leg(rec, **dict(kid, DATA_AREAS="py,num,c,rust,go,eng", DATA_N_PROCESSES="6"))
    check("D9 five positions apart the alphabet is the same, and so is the text: eng at position 5 over "
          "a parent's 0 is rehearsed, and its 10,000-byte body is the first 10,000 bytes of the "
          "parent's 20,000 (a generated body at another length is a prefix or a continuation of the "
          "same sequence)",
          p.parent_faded == (5,) and st.per_area_drawn["eng"] > 0 and len(a.bodies["eng"]) == 10000
          and pa.bodies["eng"].startswith(a.bodies["eng"]), f"{p.parent_faded}")
    real = {"DATA_SOURCE": "real", "DATA_STREAM_BYTES": "20000"}
    ra, _p, _s, rrec = leg(**dict(TWO, DATA_PHASE_SCHED="eng|eng|eng|eng", **real))
    a, p, st, _r = leg(rrec, **dict(kid, DATA_AREAS="py,eng", DATA_N_PROCESSES="2", **real))
    g = gate(p, "data.rehearse_parent")
    check("D9 on the real source a reordered child rehearses its parent's own text -- an area's text "
          "is its directory -- with no refusal and no synthetic sentence in the Gate's reason",
          p.parent_faded == (1,) and a.bodies["eng"] == ra.bodies["eng"]
          and st.per_area_drawn["eng"] == 5400 and g is not None and g.fired
          and "DATA_SOURCE=synthetic" not in g.reason, g.line()[:200] if g else "no gate")


def d9b_what_the_record_vouches_for():
    three = {"DATA_AREAS": "eng,py,num", "DATA_N_PROCESSES": "3", "DATA_STREAM_BYTES": "20000"}
    _a, _p, _s, rec = leg(**dict(three, DATA_PHASE_SCHED="eng|eng|eng|eng"))
    old = {k: v for k, v in rec.items() if k not in ("drawn", "drawn_assumed")}
    kid = dict(three, DATA_PHASE_SCHED="py|py|py|py", DATA_DRAW="replay", DATA_REHEARSE_PARENT=1)
    a0, p0, s0, r0 = leg(old, **kid)
    a1, p1, s1, _r1 = leg(rec, **kid)
    g0, g1 = gate(p0, "data.rehearse_parent"), gate(p1, "data.rehearse_parent")
    check("D9 a record without the drawn list (an eng,py,num parent that drew eng alone, stripped as "
          "every checkpoint older than c872121 is) rehearses eng and num, 2,700 bytes each, and "
          "data.rehearse_parent's reason names both as held drawn only by ASSUMPTION; the recorded list "
          "rehearses eng alone, 5,400 bytes, and names no assumption",
          rec["drawn"] == ["eng"] and rec["drawn_assumed"] == []
          and a0.counters.get("data.drawn_assumed") == ["eng", "py", "num"]
          and p0.parent_faded == (0, 2) and s0.per_area_drawn["eng"] == 2700
          and s0.per_area_drawn["num"] == 2700 and g0 is not None and g0.fired
          and "eng, num are held drawn only by ASSUMPTION" in g0.reason
          and p1.parent_faded == (0,) and s1.per_area_drawn["eng"] == 5400
          and s1.per_area_drawn["num"] == 0 and g1 is not None and "ASSUMPTION" not in g1.reason,
          f"{g0.line()[:200] if g0 else None} | {g1.line()[:120] if g1 else None}")
    check("D9 a draw confirms an assumption: the rehearsing child of the old record drew eng, py and "
          "num, and its record carries no area as still assumed",
          r0["drawn_assumed"] == [] and sorted(r0["drawn"]) == ["eng", "num", "py"], str(r0["drawn_assumed"]))
    # THE ASSUMPTION IS CARRIED, NOT LAUNDERED: the old record's child at the parent's own schedule
    # draws eng alone and saves; before the review its record read drawn ['eng', 'py', 'num'] as
    # fact, and the next child rehearsed num as "drawn by the lineage" with data.drawn_assumed [].
    _a2, _p2, _s2, rec2 = leg(old, **dict(three, DATA_PHASE_SCHED="eng|eng|eng|eng"))
    a3, p3, s3, _r3 = leg(rec2, **kid)
    g3 = gate(p3, "data.rehearse_parent")
    check("D9 the assumption is carried down the lineage: the old record's child at eng|eng|eng|eng "
          "records drawn ['eng', 'py', 'num'] with py and num still assumed, and ITS rehearsing child "
          "reads data.drawn_assumed ['py', 'num'] and names num -- not eng, which a draw confirmed -- as "
          "held drawn only by assumption",
          rec2["drawn"] == ["eng", "py", "num"] and rec2["drawn_assumed"] == ["py", "num"]
          and a3.counters.get("data.drawn_assumed") == ["py", "num"] and p3.parent_faded == (0, 2)
          and g3 is not None and "num is held drawn only by ASSUMPTION" in g3.reason
          and "eng is held" not in g3.reason and "eng, num are held" not in g3.reason,
          g3.line()[:240] if g3 else "no gate")
    stripped = {k: v for k, v in rec2.items() if k != "drawn_assumed"}
    a4, _p4, _s4, _r4 = leg(stripped, **dict(three, DATA_PHASE_SCHED="eng|eng|eng|eng"))
    check("D9 a record carrying the drawn list and not the drawn_assumed key (c872121 and d9900c6 wrote "
          "that) carries no assumption: data.drawn_assumed [] and Areas.drawn_assumed empty",
          a4.counters.get("data.drawn_assumed") == [] and list(a4.drawn_assumed) == []
          and list(a4.drawn) == ["eng", "py", "num"])


def d9c_a_share_of_no_byte():
    a, p, st, _r = leg(DATA_DRAW="replay", DATA_REPLAY_SHARE="0.0")
    g = gate(p, "data.replay")
    zero = {f"data.share.p{k}.{n}.{w}": st.counters.get(f"data.share.p{k}.{n}.{w}")
            for k, n in ((1, "eng"), (2, "eng"), (3, "eng"), (3, "py")) for w in ("planned", "realised")}
    check("D9 at DATA_REPLAY_SHARE=0.0 every faded area of every faded phase prints its share gauges at "
          "0 / 0 (they were ABSENT), Gate data.replay reads armed-but-zero (0 vs 4) with a reason naming "
          "the three faded phases that come to no byte, data.replay.fixed_phases and .bytes read 0, and "
          "the draw is still exact",
          set(zero.values()) == {0} and g is not None and g.reachable and not g.fired
          and (g.value, g.threshold) == (0, 4) and "comes to no byte in every one of them" in g.reason
          and "phase 3: eng, py 0 of 30000 bytes" in g.reason
          and p.counters.get("data.replay.fixed_phases") == 0
          and p.counters.get("data.replay.bytes") == 0 and realised(a, p, st) == targets(a, p),
          f"{zero}; {g.line()[:200] if g else None}")
    a, p, st, _r = leg(DATA_DRAW="replay", DATA_REPLAY_SHARE="0.2", DATA_STREAM_BYTES="10")
    g = gate(p, "data.replay")
    check("D9 where only some faded phases come to no byte (0.2 of phases of 3, 3 and 2 bytes: 1, 1 and "
          "0) the Gate fires on the two that rehearse, FIRED (2 vs 4), names the third, and the draw is "
          "exact with the third phase's faded gauges at 0",
          g is not None and g.fired and (g.value, g.threshold) == (2, 4)
          and "1 of those 3 phase(s) give their faded areas no byte" in g.reason
          and p.counters.get("data.replay.fixed_phases") == 2 and p.counters.get("data.replay.bytes") == 2
          and st.counters.get("data.share.p3.eng.planned") == 0
          and st.counters.get("data.share.p3.py.realised") == 0 and realised(a, p, st) == targets(a, p),
          g.line()[:240] if g else "no gate")


def d9d_the_prose():
    _a, p, _s = draw(DATA_DRAW="replay")
    doc = data_api.data_plan.__doc__ or ""
    built = [g.name for g in p.gates]
    check("D9 data_plan's docstring declares the five Gates it builds, each by name, and no longer "
          "counts three",
          len(built) == 5 and all(n in doc for n in built) and "FIVE DECLARED GATES" in doc
          and "TWO OF THE FIVE GATES' BOUNDS" in doc and "THREE DECLARED GATES" not in doc
          and "TWO OF THE THREE" not in doc, str(built))


def main():
    try:
        d1_the_old_laws()
        d2_realisation()
        d3_hash_seeds()
        d4_newest()
        d5_rehearse_parent()
        d5_d6_end_to_end()
        d6_d7_continuation()
        d8_surface()
        d9a_synthetic_body()
        d9b_what_the_record_vouches_for()
        d9c_a_share_of_no_byte()
        d9d_the_prose()
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    print(f"=== {len(FAILS)} failure(s)" + (": " + "; ".join(FAILS) if FAILS else ""))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
