"""THE SOURCE-RELIABILITY BOOK IN OBSERVE MODE, AND THE SOURCES IT READS (Proposal 04 §1 item 8 and
SR3; register 04-6.3 and §8 3.4; docs/04_CONTRACT.md Q-DATA-11), driven through DATA's own entry
points on planted units and through the real composition root and loop on synthetic and real text,
with real on-disk checkpoints under a temporary directory.

    python3 tests/test_trust.py        # exit 0 = every check passed

WHY IT EXISTS. The book is built OFF (DATA_TRUST='off') and ships ON as telemetry only after a test
proves it is telemetry: it reads the stream's text and nothing a run trains on may move. So the first
promise is SR3's bit-identity, and the rest pin what a claim is, what the vote does with it, where a
pass reads, and what a checkpoint carries.

  S1  Areas.sources: each area's per-file boundaries, mapped onto the carved body -- checked byte by
      byte against the raw manifest on random layouts and on data/train, carve included.
  S2  Stream.sources: every run's bytes are its named file's; the per-byte source agrees with the
      per-byte area label; and the bookkeeping TAKES NO DRAW -- a draw over the same Areas with the
      source table emptied is the same stream, byte for byte, draw for draw, digest for digest.
  S3  The join spine/compose.py::_trust_units: the units are the stream's bytes cut at
      Segmentation.byte_pos, and a unit's source is None exactly where a source run starts inside it.
  T1  SR3's BIT-IDENTITY, 'observe' AGAINST 'off', 300 windows on three sources: the synthetic one
      ('ctx', the rule that reads its letters), data/train ('kv'), and a PLANTED corpus whose four
      files disagree -- three state each entity's value, one the next letter -- on which the book
      floors the liar while it runs: float-exact losses, equal state digests
      (tests/_state_digest.py) but DATA.focus and RUN.cadences' 'data.trust' key, every integer
      counter equal but data.trust.*, the cadence ledger equal but its 'data.trust' row, and the
      gated call sites equal but DATA.claims_observe's. The ON runs passed, formed claims and
      recorded some; the OFF runs asked the gate zero times and wrote no book.
  T2  '@EEE=V;' AND '@EEE:V;' ARE ONE CLAIM under 'kv' (two sources writing the two forms agree), and
      two claims under 'ctx', which reads the surface form.
  T3  PLANTED UNITS: the liar-last order with d3's exact reliabilities, 21/22 and 1/22; exactly one
      conflicted claim per planted entity under 'kv' and one conflicted CONTEXT per entity under
      'ctx'; evidence ABSENT and trust 1 below DATA_TRUST_MIN_EV; and the vote is d3's ClaimTD,
      checked against a transcription of the prototype on random tables. A pass reads the same claims
      however the stream is cut into passes.
  T4  IDENTICAL ACROSS PYTHONHASHSEED: the planted book and a 40-window real-source run's book digest
      the same under three hash seeds, each in its own process.
  T5  THE CONTINUATION IS EXACT WITH THE BOOK CROSSING, across the epoch roll (RUN_EPOCHS=2
      DATA_RESAMPLE=1, on the planted corpus, where the vote has conflicts to count): a continuing
      resume from window 70, a boundary resume from the roll, and a resume from a periodic
      checkpoint taken in epoch 1 before its first pass each end with the uninterrupted run's book
      -- table, sketch, evidence, trust, first sights, cursor, stream and carry -- and every counter
      but data.trust.passes (and .updates), which count the parent's tail pass where a stop left
      one; the cursor resets at the roll and no unit is read twice or skipped.
  T6  A CHECKPOINT WITH NO BOOK (one written before this build: the key stripped) RESUMES WITH A
      FRESH ONE, reading its epoch from the first unit; a sketch of another size or a claim shape
      that moved is refused by name; an 'off' run carries a checkpoint's book unchanged, so ON ->
      OFF -> ON resumes it; and stream_state -> new_focus(restored=) round-trips the book. WHAT THE
      NEXT 'observe' LEG READS OF AN 'off' LEG IS RULED (Q-DATA-11's review), and both sides of the
      rule are driven: an 'off' leg inside one epoch is read whole at the next leg's first pass,
      from the held cursor, and the lineage ends with the uninterrupted run's book; one that crosses
      the roll leaves the next leg reading the epoch it resumes in from its first unit and none of
      the earlier epoch's, the book short of the uninterrupted run's by exactly the units the 'off'
      leg consumed before the roll, the losses continuing exactly.
  T7  DATA_TRUST='loss' AND 'loss+draw' ARE REFUSED WITH NotBuilt, by new_focus and through compose.
  T8  data.trust.wall_s IS PRINTED AS A FLOAT, AND tests/test_baseline.py's COUNTER NEVER READS IT,
      while the integer data.trust.* lines it does read are there.
  T9  THE CADENCE AUDIT'S LINE FOR THE BOOK IS THE ROOT'S (spine/compose.py::_trust_audit,
      Q-DATA-11's review). At 'off' it names DATA_TRUST='observe' as what arms the book -- the same
      line at DATA_TRUST_EVERY=1, a period that arms nothing there -- and never RUN's "Set a period
      of 1 or more"; at 'observe' a period of 0, or one the run is too short for, is reported with
      the epoch-end and tail passes that still run, and a period the run can reach gets no line;
      every other audit line is RUN's, unchanged. And the passes the line promises run: at
      DATA_TRUST_EVERY=0 a whole run passes once, at its finishing roll, over every unit it
      consumed, and a stopped one once, at its tail.

WHAT THIS FILE CANNOT SEE: whether the trust the book reports is right about real sources. CPU runs
establish operation only; the book's readings on real text are E3's (register §8 6.2), on GPU.
"""
import copy
import hashlib
import os
import random
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
from spine import assemble                                         # noqa: E402
from spine import units as U                                       # noqa: E402
from spine.gate import NotBuilt                                    # noqa: E402
from spine.compose import compose, _trust_units, _stream_digest    # noqa: E402
from spine.compose import _periods, _run_windows                   # noqa: E402
from spine import compose as C                                     # noqa: E402
from data import api as D                                          # noqa: E402
from train import api as run_api                                  # noqa: E402
from lm import api as lm_api                                       # noqa: E402
import _state_digest as sd                                         # noqa: E402
from test_baseline import COUNTER as BASELINE_COUNTER              # noqa: E402

FAILS = []
DATA_DIR = os.path.join(os.path.abspath(_ROOT), "data")
# tests/test_continuation.py's small base: a tenth-size fabric keeps each compose to a few seconds.
BASE = {"DATA_STREAM_BYTES": "60000", "SIG_WARMUP": "20", "FAB_N0": "256", "FAB_SLOTS": "512",
        "DATA_DIR": DATA_DIR}
# THE STATE THE BOOK ADDS, excluded by name when an ON run is compared with an OFF one.
EXCL = ("DATA.focus", "RUN.cadences.*.data.trust")
# THE REPORT'S INTEGER COUNTER KEYS, as tests/test_baseline.py::COUNTER reads them from run.py.
KEY = re.compile(r"^[a-z_][a-z0-9_]*(?:\.[a-z0-9_:]+)+$")
# THE CONTINUATION'S WORKLOAD: B6's shape (tests/test_baseline.py) -- two epochs, resampled, so the
# epoch roll is crossed -- on the PLANTED corpus below, with the book on, reading 'kv' claims every 30
# windows. The corpus is joined in by _main, which writes it.
E5_BASE = {"DATA_SOURCE": "real", "DATA_AREAS": "pa,pb,pc", "DATA_STREAM_BYTES": "60000",
           "RUN_EPOCHS": "2", "DATA_RESAMPLE": "1", "DATA_TRUST": "observe", "DATA_TRUST_EVERY": "30",
           "DATA_TRUST_HOT": "2", "DATA_TRUST_SKETCH": "100003"}
BOOK_FIELDS = ("sketch", "first_seen", "evidence", "trust", "cursor", "stream", "carry")


def plant_corpus(root, n_ent=40, size=20000, seed=5):
    """A corpus whose sources DISAGREE, written under root/train: area pa holds cred.txt and cred2.txt
    and area pb corrob.txt, all stating each of `n_ent` entities' true value as '@E07=C;' records, and
    area pc holds liar.txt, stating the next letter. Four sources in three areas -- a source is a
    file, not an area -- each file `size` bytes of records in its own seeded order. Returns root."""
    r = random.Random(seed)
    ents = [f"E{i:02d}" for i in range(n_ent)]
    truth = {e: r.choice("ABCDEFGH") for e in ents}
    lie = {e: "ABCDEFGH"[("ABCDEFGH".index(v) + 1) % 8] for e, v in truth.items()}
    for area, fname, vals, fseed in (("pa", "cred.txt", truth, 1), ("pa", "cred2.txt", truth, 2),
                                     ("pb", "corrob.txt", truth, 3), ("pc", "liar.txt", lie, 4)):
        rr = random.Random(fseed)
        out, n = [], 0
        while n < size:
            e = rr.choice(ents)
            rec = f"@{e}={vals[e]};"
            out.append(rec)
            n += len(rec)
        os.makedirs(os.path.join(root, "train", area), exist_ok=True)
        with open(os.path.join(root, "train", area, fname), "w", encoding="utf-8") as fh:
            fh.write("".join(out))
    return root


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" -- {detail}" if detail else ""), flush=True)
    if not ok:
        FAILS.append(name)


def build(**env):
    """A System under BASE + `env`, built as a fresh run.py process builds one."""
    _lever._reopen_assembly()
    rng.reset_issued()
    lm_api._COUNTS.clear()
    e = dict(BASE)
    e.update({k: str(v) for k, v in env.items()})
    return compose(environ=e)


def dat_of(**env):
    """DATA's resolved Config under BASE + `env`."""
    _lever._reopen_assembly()
    rng.reset_issued()
    e = dict(BASE)
    e.update({k: str(v) for k, v in env.items()})
    return assemble.build(environ=e)[0]["DATA"]


def flat_ints(report):
    """{(row, key): int} -- every integer counter line the report prints."""
    return {(row, k): v for row, d in report.items() if isinstance(d, dict)
            for k, v in d.items() if isinstance(k, str) and KEY.match(k) and type(v) is int}


def book_diff(a, b):
    """The Focus fields on which two books differ (the table compared in its LRU order)."""
    out = [f for f in BOOK_FIELDS if getattr(a, f) != getattr(b, f)]
    if list(a.table.items()) != list(b.table.items()):
        out.append("table")
    return out


def counter_diff(a, b):
    return {k: (a.counters.get(k), b.counters.get(k)) for k in sorted(set(a.counters) | set(b.counters))
            if a.counters.get(k) != b.counters.get(k)}


def planted(n_ent=20, reps=6, seed=0, forms=(b"=", b"=", b"=")):
    """Three sources' records, byte-level units: cred and corrob write each entity's true value, the
    liar the next letter. Returns (units, sources)."""
    r = random.Random(seed)
    ents = [f"E{i:02d}".encode() for i in range(n_ent)]
    truth = {e: r.choice(b"ABCDEFGH") for e in ents}
    units, srcs = [], []
    for _ in range(reps):
        for e in ents:
            for (src, v), d in zip((("cred", truth[e]), ("corrob", truth[e]),
                                    ("liar", (truth[e] - 65 + 1) % 8 + 65)), forms):
                for b in b"@" + e + d + bytes([v]) + b";":
                    units.append(bytes([b]))
                    srcs.append(src)
    return units, srcs


def observe(dat, units, sources, *, cuts=None, focus=None):
    """A book over `units`, in one pass or in passes ending at each of `cuts`."""
    f = focus if focus is not None else D.new_focus(dat, None, None)
    at, step = f.cursor, 0
    for end in list(cuts or ()) + [len(units)]:
        step += 1
        D.claims_observe(dat, f, units=units[at:end], sources=sources[at:end], step=U.Windows(step),
                         at=at)
        at = end
    return f


# ---- the prototype's vote, transcribed (results/self_regulation_design_2026-09-26/prototypes/d3/
# run.py::ClaimTD.update), for T3's comparison: sources visited in name order, as the tree does --
# the prototype's own dict order only moves float sums in their last bit.
def prototype_vote(table, *, min_n, self_share, min_ev, t_min):
    conf = []
    for c, d in table.items():
        cl = {}
        for s_ in sorted(d):
            cnts = d[s_]
            n = sum(cnts.values())
            if n >= min_n:
                v, k = max(sorted(cnts.items()), key=lambda kv: kv[1])
                if sum(1 for x in cnts.values() if x == k) == 1 and k / n >= self_share:
                    cl[s_] = v
        if len(cl) >= 2 and len(set(cl.values())) >= 2:
            conf.append(cl)
    if not conf:
        return {}, {}, 0
    r = {s_: 1.0 for cl in conf for s_ in sorted(cl)}
    nev = {}
    for _ in range(10):
        ag = {s_: [0, 0] for s_ in r}
        for cl in conf:
            vote = {}
            for s_, v in sorted(cl.items()):
                vote[v] = vote.get(v, 0.0) + r[s_]
            best = sorted(vote.values(), reverse=True)
            if len(best) > 1 and abs(best[0] - best[1]) < 1e-9:
                continue
            tv = max(vote.items(), key=lambda kv: kv[1])[0]
            for s_, v in cl.items():
                ag[s_][0] += v == tv
                ag[s_][1] += 1
        r = {s_: (a + 1) / (n + 2) for s_, (a, n) in ag.items()}
        nev = {s_: n for s_, (a, n) in ag.items()}
    ev = {s_: r[s_] for s_ in r if nev[s_] >= min_ev}
    t = {}
    if len(ev) >= 2:
        mx = max(ev.values())
        t = {s_: min(1.0, max(t_min, v / mx)) for s_, v in ev.items()}
    return {s_: [r[s_], nev[s_]] for s_ in ev}, t, len(conf)


def book_digest(f):
    """One hex digest over a book's checkpointed state."""
    return sd.digest_payload({"DATA": {"focus": D._focus_state(f)}})["DATA"]


# ---- T4's child: the book under one PYTHONHASHSEED, printed as digests ------------------------------
def _t4_child():
    dat = dat_of(DATA_TRUST="observe", DATA_TRUST_SKETCH=10007, DATA_TRUST_HOT=2, DATA_TRUST_MIN_EV=3)
    r = random.Random(7)
    units, srcs = [], []
    for _ in range(400):
        s = r.choice(("alpha", "beta", "gamma", "delta"))
        e = r.choice((b"kx", b"ky", b"kz", b"kw"))
        v = b"1" if s != "delta" else b"2"
        blob = e + r.choice((b"=", b":", b" is ")) + v + b"; "
        i = 0
        while i < len(blob):
            k = r.randint(1, 3)
            units.append(blob[i:i + k])
            srcs.append(s)
            i += k
    f = observe(dat, units, srcs, cuts=(97, len(units) // 3, len(units) // 2))
    print("T4DIGEST planted", book_digest(f), sorted(f.trust.items()))
    s = build(DATA_SOURCE="real", DATA_TRUST="observe", DATA_TRUST_EVERY=10, DATA_TRUST_HOT=2)
    res = loop.run(s, max_windows=40, progress=False)
    rows = [{k: v for k, v in row.items() if k != "seconds"} for row in res.trust_series]
    series = hashlib.blake2b(repr(rows).encode(), digest_size=16).hexdigest()
    print("T4DIGEST run", book_digest(s.focus), series)


def main():
    tmp = tempfile.mkdtemp(prefix="trust_")
    try:
        _main(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{'ALL PASS' if not FAILS else f'{len(FAILS)} FAILED'}")
    return 1 if FAILS else 0


def _main(tmp):
    planted_dir = plant_corpus(os.path.join(tmp, "planted"))
    big_dir = plant_corpus(os.path.join(tmp, "planted_big"), size=45000)
    E5 = dict(E5_BASE, DATA_DIR=planted_dir)
    # ---- S1: Areas.sources --------------------------------------------------------------------------
    rnd = random.Random(1)
    bad = 0
    for _ in range(2000):
        raw, off = [], 0
        for i in range(rnd.randint(1, 6)):
            raw.append((off, f"f{i}"))
            off += rnd.randint(1, 50)
        n_hold = rnd.randint(0, off - 1)
        start = rnd.randint(0, off - n_hold)
        got = D._carved_sources(raw, start, n_hold, off - n_hold)
        offs = [o for o, _ in raw]
        g_offs = [o for o, _ in got]
        for b in range(off - n_hold):
            x = b if b < start else b + n_hold
            want = raw[max(i for i, o in enumerate(offs) if o <= x)][1]
            i = max((i for i, o in enumerate(g_offs) if o <= b), default=None)
            if i is None or got[i][1] != want:
                bad += 1
                break
    check("S1 _carved_sources names, for every byte of the carved body, the file its byte came from "
          "(2000 random layouts: files of 1-50 bytes, a block anywhere, of any size)", bad == 0,
          f"{bad} layout(s) wrong")
    dat = dat_of(DATA_SOURCE="real")
    areas = D.open_areas(dat, seed=0)
    wrong = []
    for label in areas.names:
        rel = "train/" + label
        files = []
        blob, _p = D._read_area(os.path.join(DATA_DIR, rel), int(dat.corpus_cap), files=files)
        rh = areas.rng_holdout[label]
        start, n = int(rh["offset"]), int(rh["size"])
        ent = areas.sources[label]
        offs = [o for o, _ in ent]
        for b in range(0, len(areas.bodies[label]), 97):
            x = b if b < start else b + n
            name = files[max(i for i, (o, _f) in enumerate(files) if o <= x)][1]
            j = max(i for i, o in enumerate(offs) if o <= b)
            if ent[j][1] != f"{rel}/{name}":
                wrong.append((label, b, ent[j][1], name))
                break
    check("S1 on data/train, Areas.sources names each carved body byte's file as "
          "'train/<area>/<file>', one entry per contributing file, block moved out",
          not wrong and all(areas.sources[a][0][0] == 0 for a in areas.names)
          and all(len(areas.sources[a]) >= 2 for a in areas.names), str(wrong[:3]))
    dsyn = dat_of()
    asyn = D.open_areas(dsyn, seed=0)
    check("S1 a synthetic area is one source, synthetic:order2:<label>",
          all(asyn.sources[a] == [(0, f"synthetic:order2:{a}")] for a in asyn.names),
          str(asyn.sources))

    # ---- S2: Stream.sources ------------------------------------------------------------------------
    plan = D.data_plan(dat, areas, epochs=1, win_tokens=128, bytes_per_token=1.0)
    rng.reset_issued()
    st = D.draw_stream(dat, areas, plan, epoch=0, seed=0)
    runs, names = st.sources, st.source_names
    content_bad, label_bad = [], []
    for i, (o, idx) in enumerate(runs):
        e = runs[i + 1][0] if i + 1 < len(runs) else len(st.bytes)
        with open(os.path.join(DATA_DIR, names[idx]), "rb") as fh:
            text = fh.read()
        # a run spans one file's bytes, with at most one seam where a held-out block came out
        piece = st.bytes[o:e]
        if piece[:64] not in text or piece[-64:] not in text:
            content_bad.append((o, names[idx]))
        for b in range(o, e, 211):
            if names[idx].split("/")[1] != st.labels[b]:
                label_bad.append((b, names[idx], st.labels[b]))
    check("S2 every Stream.sources run's bytes are its named file's, and its area is the per-byte label "
          f"({len(runs)} runs over {len(st.bytes)} bytes, {len(names)} source(s))",
          runs and runs[0][0] == 0 and not content_bad and not label_bad
          and all(runs[i][1] != runs[i + 1][1] for i in range(len(runs) - 1)),
          f"content {content_bad[:2]}, labels {label_bad[:2]}")
    bare = copy.copy(areas)
    object.__setattr__(bare, "sources", {})
    object.__setattr__(bare, "cursors", dict(areas.cursors))
    object.__setattr__(bare, "drawn", [])
    rng.reset_issued()
    st2 = D.draw_stream(dat, bare, plan, epoch=0, seed=0)
    check("S2 the source bookkeeping takes no draw: over the same Areas with the source table emptied "
          "the draw is the same stream -- bytes, labels, splices, draw count, counters, gate lines and "
          "the segmentation log's digest -- and falls back to one source per area label",
          st2.bytes == st.bytes and st2.labels == st.labels and st2.splice_starts == st.splice_starts
          and st2.draws == st.draws and st2.counters == st.counters and st2.gates == st.gates
          and _stream_digest(st2) == _stream_digest(st)
          and set(st2.source_names) <= set(areas.names), str(st2.source_names))

    # ---- S3: the join ------------------------------------------------------------------------------
    s = build(DATA_SOURCE="real")
    seg, stream = s.segmentation, s.stream
    lo, hi = 1000, 9000
    units, srcs = _trust_units(s, lo, hi)
    pos = seg.byte_pos
    ro = [o for o, _ in stream.sources]
    join_bad = []
    for p, (u, sname) in enumerate(zip(units, srcs), start=lo):
        b0, b1 = int(pos[p]), int(pos[p + 1])
        r = max(i for i, o in enumerate(ro) if o <= b0)
        straddles = r + 1 < len(ro) and ro[r + 1] < b1
        want = None if straddles else stream.source_names[stream.sources[r][1]]
        if u != stream.bytes[b0:b1] or sname != want:
            join_bad.append((p, u, sname, want))
            break
    check("S3 _trust_units: unit p is the stream's bytes[byte_pos[p]:byte_pos[p + 1]], and its source "
          "is its run's name, None exactly where the next run starts inside it",
          not join_bad and len(units) == hi - lo
          and b"".join(units) == stream.bytes[int(pos[lo]):int(pos[hi])], str(join_bad[:1]))

    # ---- T7: the actuations are not built -----------------------------------------------------------
    for mode in ("loss", "loss+draw"):
        try:
            D.new_focus(dat_of(DATA_TRUST=mode), None, None)
            ok, why = False, "new_focus returned"
        except NotBuilt as e:
            ok, why = str(e).startswith(f"DATA_TRUST='{mode}'"), str(e)[:90]
        try:
            build(DATA_TRUST=mode)
            ok2 = False
        except NotBuilt as e:
            ok2 = str(e).startswith(f"DATA_TRUST='{mode}'")
        check(f"T7 DATA_TRUST={mode!r} is refused with NotBuilt naming it, by DATA.new_focus and "
              f"through compose", ok and ok2, why)
    off = D.new_focus(dat_of(), None, None)
    check("T7 at 'off' new_focus allocates nothing: no sketch, no table, no counter, both gates "
          "UNREACHABLE, data.trust naming DATA_TRUST='off'",
          off.mode == "off" and off.sketch is None and off.table is None and off.counters == {}
          and [(g.name, g.reachable) for g in off.gates]
          == [("data.trust", False), ("data.trust.actuation", False)]
          and "DATA_TRUST='off'" in off.gates[0].reason)

    # ---- T2: surface forms ---------------------------------------------------------------------------
    dkv = dat_of(DATA_TRUST="observe", DATA_TRUST_HOT=1, DATA_TRUST_SKETCH=1009)
    rec = b"@EEE=V;" * 4, b"@EEE:V;" * 4, b"@EEE=W;" * 4
    units, srcs = [], []
    for src, blob in zip(("a", "b", "c"), rec):
        units += [bytes([x]) for x in blob]
        srcs += [src] * len(blob)
    f2 = observe(dkv, units[:56], srcs[:56])
    f3 = observe(dkv, units, srcs)
    check("T2 '@EEE=V;' and '@EEE:V;' are ONE 'kv' claim: two sources writing the two forms share the "
          "key 'eee' with value 'v' and do not conflict; a third writing '@EEE=W;' makes one conflict",
          list(f2.table) == [b"eee"] and f2.table[b"eee"] == {"a": {b"v": 4}, "b": {b"v": 4}}
          and f2.counters["data.trust.conflicted_claims"] == 0
          and f3.counters["data.trust.conflicted_claims"] == 1, str(dict(f3.table)))
    dctx = dat_of(DATA_TRUST="observe", DATA_TRUST_CLAIM="ctx", DATA_TRUST_HOT=1,
                  DATA_TRUST_SKETCH=1009, DATA_TRUST_MIN_N=1)
    fc = observe(dctx, units[:56], srcs[:56])
    k_eq, k_col = (b"".join(len(u).to_bytes(4, "big") + u for u in (b"@", b"E", b"E", b"E", d))
                   for d in (b"=", b":"))
    check("T2 under 'ctx' the two forms are TWO contexts, one per source -- 'ctx' reads the surface "
          "form, which is why 04 calls it conformity and not truth",
          fc.table.get(k_eq) == {"a": {b"V": 4}} and fc.table.get(k_col) == {"b": {b"V": 4}},
          str({k: v for k, v in fc.table.items() if k in (k_eq, k_col)}))

    # ---- T3: planted units ---------------------------------------------------------------------------
    units, srcs = planted()
    for rule in ("kv", "ctx"):
        d3 = dat_of(DATA_TRUST="observe", DATA_TRUST_CLAIM=rule, DATA_TRUST_SKETCH=10007,
                    DATA_TRUST_HOT=1)
        f = observe(d3, units, srcs)
        ev, t = f.evidence, f.trust
        check(f"T3 [{rule}] the liar is last: 20 conflicted {'claims' if rule == 'kv' else 'contexts'} "
              f"(one per entity), r = 21/22 for cred and corrob and 1/22 for the liar over n = 20, "
              f"t 1, 1 and the floor 0.3",
              f.counters["data.trust.conflicted_claims"] == 20
              and ev == {"corrob": [21 / 22, 20], "cred": [21 / 22, 20], "liar": [1 / 22, 20]}
              and t == {"corrob": 1.0, "cred": 1.0, "liar": 0.3}
              and f.counters["data.trust.updates"] == 1 and f.gates[0].fired, f"{ev} {t}")
        cut = observe(d3, units, srcs, cuts=sorted(random.Random(3).sample(range(1, len(units)), 40)))
        _cd = counter_diff(cut, f)
        check(f"T3 [{rule}] forty passes at random cuts read the same book as one pass (the carry), "
              f"every counter equal but the pass count and the passes that voted over a conflict",
              not book_diff(cut, f) and _cd.pop("data.trust.passes", None) == (41, 1)
              and set(_cd) <= {"data.trust.updates"} and cut.counters["data.trust.updates"] >= 1,
              f"{book_diff(cut, f)} {_cd}")
    d3 = dat_of(DATA_TRUST="observe", DATA_TRUST_SKETCH=10007, DATA_TRUST_HOT=1,
                DATA_TRUST_MIN_EV=21)
    f = observe(d3, units, srcs)
    g = D._trust_gates(d3, f)[0]
    check("T3 below DATA_TRUST_MIN_EV (21 against 20 conflicted claims each) every source's evidence "
          "is ABSENT, no trust is set (1 for all), and data.trust reads armed-but-zero",
          f.counters["data.trust.conflicted_claims"] == 20 and f.evidence == {} and f.trust == {}
          and f.counters["data.trust.evidence_absent"] == 3 and g.reachable and not g.fired)
    rnd = random.Random(11)
    vbad = []
    for trial in range(300):
        tab = {}
        for key in range(rnd.randint(1, 30)):
            per = {}
            for src in rnd.sample(["a", "b", "c", "d", "e"], rnd.randint(1, 5)):
                per[src] = {bytes([97 + v]): rnd.randint(1, 6) for v in rnd.sample(range(4),
                                                                                  rnd.randint(1, 2))}
            tab[str(key).encode()] = per
        kw = dict(min_n=rnd.randint(1, 4), self_share=rnd.choice((0.5, 0.6, 0.8, 1.0)),
                  min_ev=rnd.randint(1, 5), floor=0.3)
        fz = D.Focus(mode="observe", table=dict(tab))
        n_conf = D._trust_vote(fz, **kw)
        ev, t, n = prototype_vote(tab, min_n=kw["min_n"], self_share=kw["self_share"],
                                  min_ev=kw["min_ev"], t_min=0.3)
        if (fz.evidence, fz.trust, n_conf) != (ev, t, n):
            vbad.append((trial, fz.evidence, ev))
            break
    check("T3 the vote is d3's ClaimTD: on 300 random tables, evidence, trust and the conflicted count "
          "equal a transcription of the prototype's update()", not vbad, str(vbad[:1]))

    # ---- T4: PYTHONHASHSEED --------------------------------------------------------------------------
    outs = []
    for seed in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed, OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
        p = subprocess.run([sys.executable, os.path.abspath(__file__), "--t4-child"],
                           cwd=os.path.abspath(_ROOT), env=env, capture_output=True, text=True)
        outs.append([ln for ln in p.stdout.splitlines() if ln.startswith("T4DIGEST")]
                    if p.returncode == 0 else [f"exit {p.returncode}: {p.stderr[-300:]}"])
    check("T4 the book is identical across PYTHONHASHSEED 0, 1 and 12345: the planted book cut into "
          "passes, and a 40-window real-source run's book and pass series, each in its own process",
          len(outs[0]) == 2 and outs[0] == outs[1] == outs[2], str([o[:1] for o in outs]))

    # ---- T1: SR3's bit-identity ------------------------------------------------------------------------
    for tag, src_env, on_env in (
            ("synthetic", {}, {"DATA_TRUST_CLAIM": "ctx", "DATA_TRUST_EVERY": "50",
                               "DATA_TRUST_HOT": "2", "DATA_TRUST_MIN_EV": "2"}),
            ("real", {"DATA_SOURCE": "real", "DATA_STREAM_BYTES": "70000"},
             {"DATA_TRUST_EVERY": "50", "DATA_TRUST_HOT": "2", "DATA_TRUST_MIN_N": "2",
              "DATA_TRUST_MIN_EV": "2"}),
            ("planted", {"DATA_SOURCE": "real", "DATA_DIR": big_dir, "DATA_AREAS": "pa,pb,pc",
                         "DATA_STREAM_BYTES": "160000"},
             {"DATA_TRUST_EVERY": "50", "DATA_TRUST_HOT": "2"})):
        s0 = build(**src_env)
        r0 = loop.run(s0, max_windows=300, progress=False)
        s1 = build(DATA_TRUST="observe", **src_env, **on_env)
        r1 = loop.run(s1, max_windows=300, progress=False)
        d0, d1 = sd.digest(s0, exclude=EXCL, detail=True), sd.digest(s1, exclude=EXCL, detail=True)
        i0, i1 = flat_ints(r0.report), flat_ints(r1.report)
        extra = sorted(k for k in set(i1) - set(i0))
        led0 = {k: v for k, v in r0.cadence_ledger.items() if k != "data.trust"}
        led1 = {k: v for k, v in r1.cadence_ledger.items() if k != "data.trust"}
        g0 = [g for g in r0.gated if not g.startswith("DATA.claims_observe")]
        g1 = [g for g in r1.gated if not g.startswith("DATA.claims_observe")]
        c1 = s1.focus.counters
        rule = on_env.get("DATA_TRUST_CLAIM", "kv")
        n_w = len(r1.loss_curve)
        check(f"T1 [{tag}] 'observe' against 'off', {n_w} windows: float-exact losses, equal state "
              f"digests but DATA.focus and RUN.cadences' 'data.trust', every integer counter equal but "
              f"data.trust.*, the ledger equal but 'data.trust', the gated sites equal but the book's",
              r0.loss_curve == r1.loss_curve and n_w == 300 and d0 == d1
              and {k: v for k, v in i0.items()} == {k: v for k, v in i1.items() if k in i0}
              and all(k[1].startswith("data.trust.") for k in extra)
              and led0 == led1 and g0 == g1,
              f"digest differs at {sd.differing(d0, d1)}; extra ints {extra[:3]}")
        check(f"T1 [{tag}] the ON run read its text: {c1['data.trust.passes']} passes over "
              f"{c1['data.trust.units']} units, {c1['data.trust.claims']} claims formed and "
              f"{c1.get('data.trust.claims_' + rule)} recorded; the report's wall_s is a float",
              c1["data.trust.passes"] == 6 and c1["data.trust.units"] == 300 * 128 + 1
              and c1["data.trust.claims"] > 0 and c1.get(f"data.trust.claims_{rule}", 0) > 0
              and type(r1.report["DATA(trust)"]["data.trust.wall_s"]) is float
              and r1.cadence_ledger["data.trust"][:2] == (300, 5)
              and [r["kind"] for r in r1.trust_series] == ["cadence"] * 5 + ["tail"],
              str(r1.cadence_ledger["data.trust"]))
        if tag == "planted":
            f1 = s1.focus
            check("T1 [planted] and the book was not idle while nothing moved: 40 conflicted claims, "
                  "four sources with evidence, the liar floored at 0.3 and the three truthful files at "
                  "1, data.trust FIRED",
                  c1["data.trust.conflicted_claims"] == 40 and len(f1.evidence) == 4
                  and f1.trust == {"train/pa/cred.txt": 1.0, "train/pa/cred2.txt": 1.0,
                                   "train/pb/corrob.txt": 1.0, "train/pc/liar.txt": 0.3}
                  and f1.gates[0].fired, f"{f1.trust} {c1['data.trust.conflicted_claims']}")
        check(f"T1 [{tag}] the OFF run kept no book: no data.trust.* key in any row, the 'data.trust' "
              f"gate asked 0 times at period 0, no pass in the series, no 'focus' in DATA's payload, "
              f"and the DATA(trust) row is the two UNREACHABLE gates",
              not any(k[1].startswith("data.trust.") for k in i0)
              and r0.cadence_ledger["data.trust"][:2] == (0, 0)
              and int(r0.cadence_ledger["data.trust"][3]) == 0 and r0.trust_series == ()
              and "focus" not in loop._payload(s0)["DATA"]
              and sorted(r0.report["DATA(trust)"]) == ["gate:data.trust", "gate:data.trust.actuation"]
              and all(v[0] == "unreachable" for v in r0.report["DATA(trust)"].values()))

    # ---- T5: the continuation, across the roll ---------------------------------------------------------
    u = build(**E5)
    ru = loop.run(u, progress=False)
    fu = u.focus
    ser = ru.trust_series
    roll0 = [r for r in ser if r["kind"] == "roll"]
    first1 = next((i for i, r in enumerate(ser) if r["at"] == 0 and i > 0), None)
    end0 = roll0[0]["at"] + roll0[0]["units"] if roll0 else None
    ok_chain = all(ser[i + 1]["at"] == ser[i]["at"] + ser[i]["units"]
                   for i in range(len(ser) - 1) if i + 1 != first1)
    w0 = (end0 - 1) // 128 if end0 else None
    check(f"T5 the uninterrupted run: {ru.windows} windows over two epochs (the roll after {w0}), the "
          f"book's cursor reset to 0 by the roll's next pass, every pass starting where the last ended "
          f"within an epoch, data.trust.units the two epochs' consumed units, W x 128 + 1 each, and "
          f"the liar floored by the end",
          ru.epochs == 2 and len(roll0) == 2 and first1 is not None and ok_chain
          and (end0 - 1) % 128 == 0 and fu.stream == 1
          and fu.counters["data.trust.units"] == end0 + fu.cursor
          and w0 + (fu.cursor - 1) // 128 == ru.windows
          and fu.trust.get("train/pc/liar.txt") == 0.3 and fu.counters["data.trust.updates"] > 0,
          f"rolls {[(r['at'], r['units']) for r in roll0]}, cursor {fu.cursor}, "
          f"units {fu.counters['data.trust.units']}, trust {fu.trust}")
    # THE PERIODIC SAVE LANDS IN EPOCH 1 BEFORE ITS FIRST PASS: seeded at step 1, CKPT_EVERY=n first
    # fires at step n + 1, and the book's cadence (30) next fires at the first multiple of 30 past w0,
    # plus 1.
    first_e1 = next(r["step"] for r in ser if r["at"] == 0 and r["step"] > w0)
    for tag, stop, extra, resume in (("a continuing resume from window 70", 70, {}, "ckpt.pt"),
                                     (f"a boundary resume from window {w0}", w0, {}, "ckpt.pt"),
                                     ("a resume from a periodic save in epoch 1 before its first pass",
                                      w0 + 12, {"CKPT_EVERY": str(w0 + 9)}, "ckpt.pt.prev")):
        d = os.path.join(tmp, f"t5_{stop}")
        p = build(CKPT_DIR=d + "/p", **extra, **E5)
        rp = loop.run(p, max_windows=stop, progress=False)
        blob = torch.load(os.path.join(d, "p", resume), map_location="cpu", weights_only=False)
        at_step = int(blob["step"])
        # THE PARENT'S TAIL PASSES THE LINEAGE CARRIES: the final checkpoint's, not a periodic one's
        # taken before it.
        tails = [r for r in rp.trust_series if r["kind"] == "tail"] if resume == "ckpt.pt" else []
        c = build(CKPT_RESUME=os.path.join(d, "p", resume), CKPT_DIR=d + "/c", **E5)
        rc = loop.run(c, progress=False)
        fc = c.focus
        want_ctr = {}
        if tails:
            want_ctr["data.trust.passes"] = (fu.counters["data.trust.passes"],
                                             fu.counters["data.trust.passes"] + len(tails))
            _up = sum(1 for r in tails if r["conflicted_claims"])
            if _up:
                want_ctr["data.trust.updates"] = (fu.counters["data.trust.updates"],
                                                  fu.counters["data.trust.updates"] + _up)
        exact = list(rc.loss_curve) == list(ru.loss_curve[at_step:])
        check(f"T5 {tag} (the saved step {at_step}): the lineage ends with the uninterrupted run's "
              f"book in every field, and every counter equal but the parent's {len(tails)} tail "
              f"pass(es), which data.trust.passes counts"
              + ("; the losses continue exactly" if stop != w0 else
                 " (a boundary resume is not a training continuation, B6r; the book reads the same "
                 "text)"),
              not book_diff(fc, fu) and counter_diff(fu, fc) == want_ctr
              and (exact or stop == w0) and len(tails) == (1 if stop == 70 else 0),
              f"book {book_diff(fc, fu)}, counters {counter_diff(fu, fc)}, losses exact {exact}")
        if stop == w0 + 12:
            p_stale = blob["payload"]["DATA"]["focus"]
            check("T5 that periodic save, in epoch 1 before its first pass, holds a cursor from "
                  "epoch 0 (its last pass is the roll's, at the epoch's first step), and the child "
                  "read epoch 1 from unit 0",
                  w0 < at_step < first_e1
                  and int(p_stale["last_step"]) <= at_step - int(blob["payload"]["RUN"]["clock"]["in_epoch"])
                  and rc.trust_series[0]["at"] == 0, f"saved at {at_step}, epoch 1's first pass "
                  f"at {first_e1}, last_step {p_stale['last_step']}, first child pass at "
                  f"{rc.trust_series[0]['at']}")

    # ---- T6: a checkpoint without a book, a refused geometry, ON -> OFF -> ON, the round trip ------------
    d = os.path.join(tmp, "t6")
    p = build(CKPT_DIR=d + "/p", **E5)
    rp = loop.run(p, max_windows=70, progress=False)
    p_tail = [r for r in rp.trust_series if r["kind"] == "tail"]
    blob = torch.load(os.path.join(d, "p", "ckpt.pt"), map_location="cpu", weights_only=False)
    rec = blob["payload"]["DATA"]["focus"]
    rt = D.new_focus(dat_of(**E5), None, None, restored=copy.deepcopy(rec))
    check("T6 stream_state's 'focus' record puts the book back whole through new_focus(restored=)",
          not book_diff(rt, p.focus) and rt.counters == p.focus.counters
          and rt.claim == "kv" and rt.sketch_size == 100003)
    # THE VOCABULARY FILE SITS BESIDE ITS DIRECTORY (<CKPT_DIR>.dyntok.json), so it is copied too.
    shutil.copytree(os.path.join(d, "p"), os.path.join(d, "old"))
    shutil.copy(os.path.join(d, "p.dyntok.json"), os.path.join(d, "old.dyntok.json"))
    old = torch.load(os.path.join(d, "old", "ckpt.pt"), map_location="cpu", weights_only=False)
    old["payload"]["DATA"].pop("focus")
    torch.save(old, os.path.join(d, "old", "ckpt.pt"))
    c = build(CKPT_RESUME=d + "/old", CKPT_DIR=d + "/oc", **E5)
    fresh = (c.focus.counters.get("data.trust.passes"), c.focus.cursor, c.focus.last_step)
    rc = loop.run(c, max_windows=30, progress=False)
    check("T6 a checkpoint with no book (payload['DATA'] without 'focus', as before this build) resumes "
          "with a FRESH one -- every counter 0, cursor 0 -- whose first pass reads the resumed epoch "
          "from its first unit, and the losses continue exactly",
          fresh == (0, 0, -1) and rc.trust_series[0]["at"] == 0
          and c.focus.counters["data.trust.units"] == 100 * 128 + 1
          and list(rc.loss_curve) == list(ru.loss_curve[70:100]),
          f"fresh {fresh}, first pass {rc.trust_series[0]}")
    for lever, value, name in (("DATA_TRUST_SKETCH", "100019", "DATA_TRUST_SKETCH"),
                               ("DATA_TRUST_CLAIM", "ctx", "DATA_TRUST_CLAIM")):
        env = dict(E5, **{lever: value})
        try:
            build(CKPT_RESUME=d + "/p", CKPT_DIR=d + "/x", **env)
            ok, why = False, "composed"
        except D.CorpusError as e:
            ok, why = str(e).startswith(name) and "checkpoint's source-reliability book" in str(e), \
                str(e)[:120]
        check(f"T6 a resume at another {lever} is refused by name at the 'focus' stage", ok, why)
    off = build(CKPT_RESUME=d + "/p", CKPT_DIR=d + "/off", **dict(E5, DATA_TRUST="off"))
    loop.run(off, max_windows=20, progress=False)
    held = torch.load(os.path.join(d, "off", "ckpt.pt"), map_location="cpu",
                      weights_only=False)["payload"]["DATA"].get("focus")
    on = build(CKPT_RESUME=d + "/off", CKPT_DIR=d + "/on", **E5)
    ro = loop.run(on, progress=False)
    _f0 = ro.trust_series[0] if ro.trust_series else {}
    check("T6 ON -> OFF -> ON inside one epoch: the 'off' run writes the parent's book back "
          "unchanged and makes no pass, and the grandchild's first pass starts at the held cursor "
          "and reads past the 'off' leg's last unit -- the ruled placement -- so the lineage ends "
          "with the uninterrupted run's book, every counter equal but the parent's tail pass",
          held is not None and sd.digest_payload({"f": held}) == sd.digest_payload({"f": rec})
          and not off.focus.counters and not book_diff(on.focus, fu) and len(p_tail) == 1
          and counter_diff(fu, on.focus) == dict(
              {"data.trust.passes": (fu.counters["data.trust.passes"],
                                     fu.counters["data.trust.passes"] + 1)},
              **({"data.trust.updates": (fu.counters["data.trust.updates"],
                                         fu.counters["data.trust.updates"] + 1)}
                 if p_tail and p_tail[0]["conflicted_claims"] else {}))
          and _f0.get("at") == 70 * 128 + 1
          and _f0.get("at", 0) + _f0.get("units", 0) > 90 * 128 + 1,
          f"book {book_diff(on.focus, fu)}, counters {counter_diff(fu, on.focus)}, "
          f"first pass {_f0 or None}")
    # AN 'off' LEG THAT CROSSES THE ROLL (Q-DATA-11's review). The 'off' leg runs from the parent's
    # window 70 past the roll at w0, so its checkpoint sits in epoch 1 and the held book's last pass
    # -- the parent's tail -- in epoch 0: the next 'observe' leg reads epoch 1 from its first unit
    # and none of epoch 0's units the 'off' leg consumed, whose segmentation went at the roll. The
    # book then holds every unit of the lineage but those, exactly, and training is untouched.
    off2 = build(CKPT_RESUME=d + "/p", CKPT_DIR=d + "/off2", **dict(E5, DATA_TRUST="off"))
    loop.run(off2, max_windows=70, progress=False)
    blob2 = torch.load(os.path.join(d, "off2", "ckpt.pt"), map_location="cpu", weights_only=False)
    at2 = int(blob2["step"])
    on2 = build(CKPT_RESUME=d + "/off2", CKPT_DIR=d + "/on2", **E5)
    ro2 = loop.run(on2, progress=False)
    _f2 = ro2.trust_series[0] if ro2.trust_series else {}
    lost = end0 - (70 * 128 + 1)
    check(f"T6 ON -> OFF -> ON across the roll (the 'off' leg from 70 to {at2}, the roll after "
          f"{w0}): the grandchild's first pass opens epoch 1 at unit 0, and the book ends holding "
          f"every unit of the lineage but the {lost} the 'off' leg consumed in epoch 0 -- the "
          f"uninterrupted run's units less exactly those, its cursor and stream ordinal, a "
          f"different sketch -- the losses continuing exactly, and the 'off' leg's reason saying so",
          w0 < at2 and _f2.get("at") == 0 and _f2.get("step", 0) > w0
          and on2.focus.counters["data.trust.units"] == fu.counters["data.trust.units"] - lost
          and on2.focus.cursor == fu.cursor and on2.focus.stream == fu.stream
          and "sketch" in book_diff(on2.focus, fu)
          and list(ro2.loss_curve) == list(ru.loss_curve[at2:])
          and "none of an earlier epoch's" in off2.focus.gates[0].reason,
          f"first pass {_f2 or None}, units {on2.focus.counters['data.trust.units']} against "
          f"{fu.counters['data.trust.units']} - {lost}, book {book_diff(on2.focus, fu)}")

    # ---- T8: wall_s outside the integer channel ----------------------------------------------------------
    env = dict(os.environ, OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", DATA_TRUST="observe",
               DATA_TRUST_EVERY="10", **{k: v for k, v in BASE.items() if k != "DATA_DIR"})
    out = os.path.join(tmp, "series.json")
    p = subprocess.run([sys.executable, "run.py", "--max-windows", "30", "--quiet", "--trust-series",
                        out], cwd=os.path.abspath(_ROOT), env=env, capture_output=True, text=True)
    lines = p.stdout.splitlines()
    wall = [ln for ln in lines if ln.strip().startswith("data.trust.wall_s")]
    parsed = {m.group(1) for m in (BASELINE_COUNTER.match(ln) for ln in lines) if m}
    import json
    series = json.load(open(out)) if os.path.isfile(out) else None
    check("T8 run.py prints data.trust.wall_s with decimals, test_baseline's COUNTER never parses it, "
          "and it does parse the integer data.trust.* lines; --trust-series writes one dict per pass",
          p.returncode == 0 and len(wall) == 1 and re.search(r"\d\.\d", wall[0]) is not None
          and "data.trust.wall_s" not in parsed and "data.trust.passes" in parsed
          and "data.trust.units" in parsed and isinstance(series, list)
          and [r["kind"] for r in series] == ["cadence", "cadence", "tail"],
          f"rc {p.returncode}; {wall}; series {None if series is None else len(series)}")

    # ---- T9: the cadence audit's line for the book is the root's ---------------------------------------
    # RUN's two sentences are a cadence's, and the book is armed by DATA_TRUST and passes beside its
    # gate; so the root words the one line (spine/compose.py::_trust_audit) and hands the rest back
    # as RUN wrote them -- compared here against RUN.cadence_audit called afresh on the same mapping.
    # The join is fetched by name, so this file still runs, and these checks fail, on a tree
    # without it.
    tag = "cadence audit: 'data.trust' "
    _trust_audit = getattr(C, "_trust_audit", lambda s, lines, **kw: None)
    seen = {}
    for label, env in (("off", {}), ("off1", {"DATA_TRUST_EVERY": "1"}),
                       ("obs0", {"DATA_TRUST": "observe", "DATA_TRUST_EVERY": "0"}),
                       ("obs_long", {"DATA_TRUST": "observe", "DATA_TRUST_EVERY": "100000"}),
                       ("obs10", {"DATA_TRUST": "observe", "DATA_TRUST_EVERY": "10"})):
        s = build(**env)
        rw = _run_windows(s)
        audit = [w for w in s.warnings if w.startswith("cadence audit:")]
        theirs = run_api.cadence_audit(s.configs["RUN"], run_windows=rw, periods=_periods(s))
        seen[label] = ([w for w in audit if w.startswith(tag)], int(rw),
                       [w for w in audit if not w.startswith(tag)]
                       == [w for w in theirs if not w.startswith(tag)]
                       and len(audit) == len(theirs)
                       and _trust_audit(s, theirs, run_windows=rw, periods=_periods(s)) == audit)
    off_l, off1_l = seen["off"][0], seen["off1"][0]
    check("T9 at the shipped 'off' the audit's one 'data.trust' line is the root's: DISARMED by "
          "DATA_TRUST='off', DATA_TRUST='observe' named as what arms the book, never RUN's 'Set a "
          "period of 1 or more' -- and at DATA_TRUST_EVERY=1, a period that arms nothing there, the "
          "same line",
          len(off_l) == 1 and "DISARMED by DATA_TRUST='off'" in off_l[0]
          and "DATA_TRUST='observe' arms it" in off_l[0] and "this run's is 160" in off_l[0]
          and "Set a period of 1 or more" not in off_l[0]
          and off1_l == [off_l[0].replace("this run's is 160", "this run's is 1")],
          f"{off_l} {off1_l}")
    obs0, obs_long = seen["obs0"][0], seen["obs_long"][0]
    check("T9 at 'observe' a period of 0, and one the run is too short for, are reported with the "
          "passes that still run -- the window that rolls each epoch and a stop's tail -- and never "
          "as 'Whatever it gates does not happen in this run'",
          len(obs0) == 1 and "(DATA_TRUST_EVERY=0)" in obs0[0]
          and "PERIODIC pass is DISARMED" in obs0[0]
          and len(obs_long) == 1 and "CANNOT FIRE ONCE" in obs_long[0]
          and f"has a period of 100000 windows and this run is {seen['obs_long'][1]} windows long"
          in obs_long[0]
          and all("rolls each epoch" in ln and "once more at the end" in ln
                  and "Whatever it gates" not in ln for ln in obs0 + obs_long), f"{obs0} {obs_long}")
    check("T9 a period the run can reach gets no 'data.trust' line, and in all five configurations "
          "every other audit line is RUN's own, the count unchanged: the root rewords one line and "
          "adds none",
          seen["obs10"][0] == [] and all(v[2] for v in seen.values()),
          str({k: v[2] for k, v in seen.items()}))
    # THE PASSES THE LINE PROMISES, DRIVEN at DATA_TRUST_EVERY=0 on a 12,000-byte real stream: a whole
    # run passes once, at its finishing roll, and a stopped one once, at its tail -- each over every
    # unit it consumed -- while the gate is asked every window and fires never.
    s = build(DATA_SOURCE="real", DATA_STREAM_BYTES=12000, DATA_TRUST="observe", DATA_TRUST_EVERY=0)
    rw = int(_run_windows(s))
    r_all = loop.run(s, progress=False)
    all_ser = [(x["kind"], x["at"], x["units"]) for x in r_all.trust_series]
    claims = s.focus.counters["data.trust.claims"]
    s = build(DATA_SOURCE="real", DATA_STREAM_BYTES=12000, DATA_TRUST="observe", DATA_TRUST_EVERY=0)
    r_30 = loop.run(s, max_windows=30, progress=False)
    stop_ser = [(x["kind"], x["at"], x["units"]) for x in r_30.trust_series]
    check(f"T9 at DATA_TRUST_EVERY=0 the book passes as the line says: a whole {rw}-window run once, "
          f"at its finishing roll, over its {rw * 128 + 1} units ({claims} claims formed), a run "
          f"stopped at 30 once, at its tail, over 3841; the gate asked every window and fired never",
          r_all.windows == rw and all_ser == [("roll", 0, rw * 128 + 1)] and claims > 0
          and r_all.cadence_ledger["data.trust"][:2] == (rw, 0)
          and stop_ser == [("tail", 0, 30 * 128 + 1)]
          and r_30.cadence_ledger["data.trust"][:2] == (30, 0), f"{all_ser} {stop_ser}")


if __name__ == "__main__":
    if "--t4-child" in sys.argv:
        _t4_child()
        sys.exit(0)
    sys.exit(main())
