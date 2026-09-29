"""THE SOURCE-RELIABILITY BOOK IN OBSERVE MODE, AND THE SOURCES IT READS (Proposal 04 §1 item 8 and
SR3; register 04-6.3 and §8 3.4; docs/04_CONTRACT.md Q-DATA-11), driven through DATA's own entry
points on planted units and through the real composition root and loop on synthetic and real text,
with real on-disk checkpoints under a temporary directory.

    python3 tests/test_trust.py        # exit 0 = every check passed

WHY IT EXISTS. The book was built OFF (DATA_TRUST='off') and ships ON ('observe', since 2026-09-29,
the flip landing last and alone) as telemetry only after a test proves it is telemetry: it reads the
stream's text and nothing a run trains on may move. So the first promise is SR3's bit-identity, and the
rest pin what a claim is, what the vote does with it, where a pass reads, and what a checkpoint
carries. THE FILE'S ARM IS 'off' UNLESS A CHECK SETS 'observe': the checks were written while 'off'
shipped, and each names the arm it reads; everything else runs at its shipped value but generation.

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
  T7  DATA_TRUST='loss' AND 'loss+draw' ARE REFUSED WITH NotBuilt, by new_focus and through compose;
      'off' allocates nothing; and 'observe' is the shipped value since 04-6.3's flip, a Config
      assembled with no DATA_TRUST keeping the book on DATA_TRUST_EVERY's period, its actuation gate
      UNREACHABLE.
  T8  data.trust.wall_s IS PRINTED AS A FLOAT, AND tests/test_baseline.py's COUNTER NEVER READS IT,
      while the integer data.trust.* lines it does read are there.
  T9  THE CADENCE AUDIT'S LINE FOR THE BOOK IS THE ROOT'S (spine/compose.py::_trust_audit,
      Q-DATA-11's review). At 'off' it names DATA_TRUST='observe' as what arms the book -- the same
      line at DATA_TRUST_EVERY=1, a period that arms nothing there -- and never RUN's "Set a period
      of 1 or more"; at 'observe' a period of 0, or one the run is too short for, is reported with
      the epoch-end and tail passes that still run, and a period the run can reach gets no line;
      every other audit line is RUN's, unchanged, but the probe's, which the root words too since
      the flip's review (tests/test_probe.py P16). And the passes the line promises run: at
      DATA_TRUST_EVERY=0 a whole run passes once, at its finishing roll, over every unit it
      consumed, and a stopped one once, at its tail.

SR6's COPY DETECTION (2026-09-28, Proposal 04 SR6 and §1 item 8's standing rule (2); register §8 3.7;
docs/04_CONTRACT.md Q-DATA-12), on model-free tables in §8 0.6's td_stress style -- who states what is
fixed by construction, and the book reads it with no model -- and through the loop:
  SR6-1  A PLANTED COPY OF A LIAR IS REPORTED DEPENDENT at the hand-computed posterior (Bayes' rule in
         product form, not the tree's logistic), the pair ordered by first sight and not by name; the
         truthful pairs and the mixed ones certified at theirs; a partial copy still dependent at its.
  SR6-2  TWO INDEPENDENT TRUTHFUL SOURCES ARE CERTIFIED INDEPENDENT, and stay so as their agreement
         grows: the posterior of agreement on true values is bounded below 0.3575 at these values.
  SR6-3  A MAJORITY-FALSE TABLE: the undiscounted vote loses the keys a copy and its source outvote
         the truth on, and the discounted vote wins them -- both outcomes by hand.
  SR6-4  AT 'off' THE KEYS ARE ABSENT AND THE VOTE IS C5's; on 300 random tables the vote with the
         detection equals a transcription of the plan's model, and a detection that finds nothing
         above its threshold moves nothing.
  SR6-5  EVERY END AT WHICH NO CLAIM CAN MOVE A VERDICT IS REFUSED BY NAME -- the prior's two and,
         since Q-DATA-12's review, the threshold's two and the rate's 0 -- and a value past them by
         the lever's domain; the rate's 1 is legal, and on it both verdicts are reached.
  SR6-6  THROUGH THE LOOP, on a planted corpus holding a copy of its liar: the copy dependent at its
         hand posterior and the row printing it; the copy steps timed -- data.trust.copy.seconds
         above 0, the sum of the passes' own, inside wall_s, and on a second run() over one System
         that run()'s alone (the review); 'accu' against 'off' moving nothing the run trains on; a
         continuing resume ending with the uninterrupted run's book; ON -> OFF -> ON for the
         detection, the 'off' leg carrying the copy part unchanged.
  T1, T7 read the book's third gate; T4 digests SR6's book under three hash seeds; T8 holds
  data.trust.copy.seconds outside the integer channel, on the planted copier corpus, where it is a
  non-zero reading (the review: on the synthetic source no claim was formed and it read 0.0).

WHAT THIS FILE CANNOT SEE: whether the trust the book reports is right about real sources. CPU runs
establish operation only; the book's readings on real text are E3's (register §8 6.2), on GPU, and
whether copy detection catches copies in E5's majority-false and impersonation worlds is §8 5.12's.
"""
import copy
import hashlib
import math
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
# THE FILE'S ARM IS DATA_TRUST='off' UNLESS A CHECK SETS 'observe' (2026-09-29, 04-6.3's flip). The
# checks were written while 'off' shipped and each names the arm it reads; since the flip 'observe' is
# the shipped value, which T7 reads by assembling with no DATA_TRUST at all. Everything else runs at its
# shipped value -- the synthetic held-out block and the retention probe among them, so T1 is SR3's
# bit-identity at the new defaults -- except generation: it runs after the final save, reads nothing
# the book reads, and costs about a minute a run on the CPU.
BASE = {"DATA_STREAM_BYTES": "60000", "SIG_WARMUP": "20", "FAB_N0": "256", "FAB_SLOTS": "512",
        "DATA_DIR": DATA_DIR, "DATA_TRUST": "off", "EVAL_GENERATE": "0"}
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
BOOK_FIELDS = ("sketch", "first_seen", "evidence", "trust", "cursor", "stream", "carry",
               "copy_pairs")
# SR6's MODEL-FREE WORLDS (Q-DATA-12), laid out by records(): a, b and d state each key's truth 't',
# l a false 'f', c a copy of l's values and n a second false value 'g', first seen in that order --
# so the copy is the later of its pair although 'c' sorts before 'l' by name. The X keys carry all
# six; on the Y keys only a, l and c speak, so there the copy and its source are the majority, and
# false.
SR6_ORDER = ("a", "b", "d", "l", "c", "n")
SR6_X = [(f"x{i:02d}", {"a": "t", "b": "t", "d": "t", "l": "f", "c": "f", "n": "g"})
         for i in range(20)]
SR6_Y = [(f"y{i:02d}", {"a": "t", "l": "f", "c": "f"}) for i in range(10)]
SR6_ENV = {"DATA_TRUST": "observe", "DATA_TRUST_HOT": "1", "DATA_TRUST_SKETCH": "10007"}


def plant_corpus(root, n_ent=40, size=20000, seed=5, copier=False):
    """A corpus whose sources DISAGREE, written under root/train: area pa holds cred.txt and cred2.txt
    and area pb corrob.txt, all stating each of `n_ent` entities' true value as '@E07=C;' records, and
    area pc holds liar.txt, stating the next letter. Four sources in three areas -- a source is a
    file, not an area -- each file `size` bytes of records in its own seeded order. At `copier`
    (SR6, Q-DATA-12) area pc also holds copy.txt, the liar's values in an order of its own, and
    liar2.txt, a second liar stating the letter two on -- so each key carries two false values and a
    copy of the first is a shared false value the second liar does not share. Returns root."""
    r = random.Random(seed)
    ents = [f"E{i:02d}" for i in range(n_ent)]
    truth = {e: r.choice("ABCDEFGH") for e in ents}
    lie = {e: "ABCDEFGH"[("ABCDEFGH".index(v) + 1) % 8] for e, v in truth.items()}
    lie2 = {e: "ABCDEFGH"[("ABCDEFGH".index(v) + 2) % 8] for e, v in truth.items()}
    extra = (("pc", "copy.txt", lie, 5), ("pc", "liar2.txt", lie2, 6)) if copier else ()
    for area, fname, vals, fseed in (("pa", "cred.txt", truth, 1), ("pa", "cred2.txt", truth, 2),
                                     ("pb", "corrob.txt", truth, 3), ("pc", "liar.txt", lie, 4))\
            + extra:
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


def records(rows, order, reps=3):
    """A MODEL-FREE WORLD IN §8 0.6's td_stress STYLE (SR6, Q-DATA-12): who states what is fixed by
    construction and the book reads it with no model. `rows` is [(key, {source: value})]; each of
    `reps` rounds lays every key's '@KEY=VALUE;' records in `order`, byte-level units, so the sources
    are first seen in that order. Returns (units, sources)."""
    units, srcs = [], []
    for _ in range(reps):
        for key, per in rows:
            for s in order:
                if s in per:
                    for b in b"@" + key.encode() + b"=" + per[s].encode() + b";":
                        units.append(bytes([b]))
                        srcs.append(s)
    return units, srcs


def hand_posterior(k_true, false_by_n, k_diff, acc, prior=0.2, rate=0.8):
    """SR6's posterior by hand, as Bayes' rule in product form -- not the tree's log-and-logistic:
    alpha L / (alpha L + 1 - alpha), L the product of the three likelihood ratios, with `acc` the
    later source's r."""
    lr = (1 - rate + rate / acc) ** k_true
    for n, k in false_by_n.items():
        lr *= (1 - rate + rate * n / (1 - acc)) ** k
    lr *= (1 - rate) ** k_diff
    return prior * lr / (prior * lr + 1 - prior)


def close(a, b):
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-15)


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


def prototype_copy_vote(table, first_seen, *, min_n, self_share, min_ev, t_min, prior, rate, p):
    """SR6's vote transcribed from the plan's words, for SR6-4's comparison: prototype_vote's
    admission and rounds, and after each round every pair of sources judged on its shared
    conflicted claims under that round's truth -- shared true, shared false (by the key's false
    values), differing (on any key) -- a pair at MIN_EV or more judged by alpha L / (alpha L + 1 -
    alpha) in product form, the later-seen source's r its accuracy; the next round discounts the
    later source of each pair above p by 1 - rate x P on every key where the earlier holds its
    value. Returns (evidence, trust, conflicted, {(earlier, later): (P, true, false, differing)})."""
    conf = []
    for c, d in table.items():
        cl = []
        for s_ in sorted(d):
            cnts = d[s_]
            n = sum(cnts.values())
            if n >= min_n:
                v, k = max(sorted(cnts.items()), key=lambda kv: kv[1])
                if sum(1 for x in cnts.values() if x == k) == 1 and k / n >= self_share:
                    cl.append((s_, v))
        if len(cl) >= 2 and len({v for _s, v in cl}) >= 2:
            conf.append(cl)
    if not conf:
        return {}, {}, 0, {}
    names = sorted({s_ for cl in conf for s_, _v in cl})
    seen = [s_ for s_ in names if s_ in first_seen]
    order = sorted(seen, key=lambda s_: (tuple(first_seen[s_]), s_)) + \
        sorted(s_ for s_ in names if s_ not in first_seen)
    pos = {s_: i for i, s_ in enumerate(order)}
    r = {s_: 1.0 for s_ in names}
    disc, pairs, ag = {}, {}, {}
    for _ in range(10):
        ag = {s_: [0, 0] for s_ in names}
        truths = []
        for i, cl in enumerate(conf):
            vote = {}
            for s_, v in cl:
                vote[v] = vote.get(v, 0.0) + r[s_] * disc.get((i, s_), 1.0)
            best = sorted(vote.items(), key=lambda kv: (-kv[1], kv[0]))
            if len(best) > 1 and abs(best[0][1] - best[1][1]) < 1e-9:
                truths.append(None)
                continue
            truths.append(best[0][0])
            for s_, v in cl:
                ag[s_][0] += v == best[0][0]
                ag[s_][1] += 1
        r = {s_: (a + 1) / (n + 2) for s_, (a, n) in ag.items()}
        counts = {}
        for i, cl in enumerate(conf):
            n_false = len({v for _s, v in cl}) - 1
            for (s1, v1) in cl:
                for (s2, v2) in cl:
                    if pos[s1] >= pos[s2]:
                        continue
                    c = counts.setdefault((s1, s2), [0, {}, 0])
                    if v1 != v2:
                        c[2] += 1
                    elif truths[i] is None:
                        continue
                    elif v1 == truths[i]:
                        c[0] += 1
                    else:
                        c[1][n_false] = c[1].get(n_false, 0) + 1
        pairs = {}
        for (e, l), (kt, kf, kd) in counts.items():
            if kt + sum(kf.values()) + kd < min_ev:
                continue
            pairs[(e, l)] = (hand_posterior(kt, kf, kd, r[l], prior, rate), kt,
                             sum(kf.values()), kd)
        disc = {}
        for i, cl in enumerate(conf):
            for s_, v in cl:
                f = 1.0
                for e, ve in sorted(cl, key=lambda x: pos[x[0]]):     # one product order
                    q = pairs.get((e, s_))
                    if ve == v and q is not None and q[0] > p:
                        f *= 1.0 - rate * q[0]
                if f < 1.0:
                    disc[(i, s_)] = f
    ev = {s_: [r[s_], ag[s_][1]] for s_ in names if ag[s_][1] >= min_ev}
    t = {}
    if len(ev) >= 2:
        mx = max(e[0] for e in ev.values())
        t = {s_: min(1.0, max(t_min, e[0] / mx)) for s_, e in ev.items()}
    return ev, t, len(conf), pairs


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
    # SR6 (Q-DATA-12): the majority-false world with copy detection on, cut into passes -- a dependent
    # pair, its discount deciding keys, and every pair's posterior in the digest.
    fcp = observe(dat_of(DATA_TRUST_COPY="accu", **SR6_ENV), *records(SR6_X + SR6_Y, SR6_ORDER),
                  cuts=(211, 1111))
    print("T4DIGEST copy", book_digest(fcp), [q[:2] + q[3:] for q in fcp.copy_pairs])
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
    cop_dir = plant_corpus(os.path.join(tmp, "copier"), copier=True)    # T8 and SR6-6
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
    check("T7 at 'off' new_focus allocates nothing: no sketch, no table, no counter, all three gates "
          "UNREACHABLE (data.trust.copy since SR6, Q-DATA-12), data.trust and data.trust.copy naming "
          "DATA_TRUST='off'",
          off.mode == "off" and off.sketch is None and off.table is None and off.counters == {}
          and [(g.name, g.reachable) for g in off.gates]
          == [("data.trust", False), ("data.trust.actuation", False), ("data.trust.copy", False)]
          and "DATA_TRUST='off'" in off.gates[0].reason
          and off.gates[2].reason.startswith("DATA_TRUST='off'"))
    # THE SHIPPED VALUE IS 'observe' SINCE 2026-09-29 (04-6.3's flip, DEFAULT BEHAVIOUR CHANGE 3): a
    # Config assembled with no DATA_TRUST -- nothing of this file's arm -- keeps the book, its period
    # is DATA_TRUST_EVERY's, and the actuation it does not build stays UNREACHABLE.
    _lever._reopen_assembly()
    rng.reset_issued()
    _shipped = assemble.build(environ={k: v for k, v in BASE.items() if k != "DATA_TRUST"})[0]["DATA"]
    _sf = D.new_focus(_shipped, None, None)
    check("T7 the shipped value is 'observe' (04-6.3's flip): assembled with no DATA_TRUST the book is "
          "kept, on DATA_TRUST_EVERY's period, its data.trust gate armed and data.trust.actuation "
          "UNREACHABLE",
          str(_shipped.trust) == "observe" and int(D.trust_period(_shipped)) == int(_shipped.trust_every)
          == 160 and _sf.mode == "observe" and _sf.sketch is not None
          and [(g.name, g.reachable) for g in _sf.gates][:2]
          == [("data.trust", True), ("data.trust.actuation", False)],
          f"trust {_shipped.trust!r}, period {int(D.trust_period(_shipped))}, "
          f"gates {[(g.name, g.reachable) for g in _sf.gates]}")
    del _sf

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
          "passes, SR6's majority-false book with copy detection on (Q-DATA-12), and a 40-window "
          "real-source run's book and pass series, each in its own process",
          len(outs[0]) == 3 and outs[0] == outs[1] == outs[2], str([o[:1] for o in outs]))

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
              f"and the DATA(trust) row is the three UNREACHABLE gates",
              not any(k[1].startswith("data.trust.") for k in i0)
              and r0.cadence_ledger["data.trust"][:2] == (0, 0)
              and int(r0.cadence_ledger["data.trust"][3]) == 0 and r0.trust_series == ()
              and "focus" not in loop._payload(s0)["DATA"]
              and sorted(r0.report["DATA(trust)"])
              == ["gate:data.trust", "gate:data.trust.actuation", "gate:data.trust.copy"]
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
    # WITH SR6's COPY DETECTION ON (Q-DATA-12), so data.trust.copy.seconds -- the seconds DATA timed in
    # this run's copy steps -- is held to the same rule as the root's wall_s in the same run. ON THE
    # PLANTED COPIER CORPUS since Q-DATA-12's review: on the synthetic source a 'kv' book forms no
    # claim, so no copy step ran and the float this held outside the channel was 0.0 -- as it is on a
    # build that never times a step. 90 windows at E5's period of 30: the first pass reads the
    # truthful areas alone, and the passes at 61 and at the stop's tail vote over conflicts.
    env = dict(os.environ, OMP_NUM_THREADS="1", MKL_NUM_THREADS="1",
               **{k: v for k, v in BASE.items() if k != "DATA_DIR"})
    env.update(E5_BASE, DATA_DIR=cop_dir, DATA_TRUST_COPY="accu")
    out = os.path.join(tmp, "series.json")
    p = subprocess.run([sys.executable, "run.py", "--max-windows", "90", "--quiet", "--trust-series",
                        out], cwd=os.path.abspath(_ROOT), env=env, capture_output=True, text=True)
    lines = p.stdout.splitlines()
    wall = [ln for ln in lines if ln.strip().startswith("data.trust.wall_s")]
    cwall = [ln for ln in lines if ln.strip().startswith("data.trust.copy.seconds")]
    parsed = {m.group(1) for m in (BASELINE_COUNTER.match(ln) for ln in lines) if m}
    import json
    series = json.load(open(out)) if os.path.isfile(out) else None
    check("T8 run.py prints data.trust.wall_s and, with copy detection on, data.trust.copy.seconds "
          "with decimals, test_baseline's COUNTER parses neither, and it does parse the integer "
          "data.trust.* and data.trust.copy.* lines; --trust-series writes one dict per pass, each "
          "carrying its copy seconds as a float",
          p.returncode == 0 and len(wall) == 1 and re.search(r"\d\.\d", wall[0]) is not None
          and len(cwall) == 1 and re.search(r"\d\.\d", cwall[0]) is not None
          and "data.trust.wall_s" not in parsed and "data.trust.copy.seconds" not in parsed
          and "data.trust.passes" in parsed and "data.trust.copy.passes" in parsed
          and "data.trust.copy.pairs_judged" in parsed
          and "data.trust.units" in parsed and isinstance(series, list)
          and [r["kind"] for r in series] == ["cadence", "cadence", "tail"]
          and all(type(r.get("copy_seconds")) is float and isinstance(r.get("copy_pairs"), list)
                  for r in series),
          f"rc {p.returncode}; {wall} {cwall}; series {None if series is None else len(series)}")
    # THE FLOAT IS A READING: above 0, the sum of the passes' copy_seconds to their rounding, inside
    # wall_s -- the copy steps run inside the passes the root times -- and every pass's own reading
    # positive where it voted over a conflicted claim, exactly 0 where it voted over none.
    try:
        cw, ww = float(cwall[0].split()[-1]), float(wall[0].split()[-1])
    except (IndexError, ValueError):
        cw = ww = None
    ser_ok = isinstance(series, list) and all(
        type(r.get("copy_seconds")) is float and type(r.get("seconds")) is float for r in series)
    per = [(r["conflicted_claims"], r["copy_seconds"], r["seconds"]) for r in series] if ser_ok \
        else series
    check("T8 on the planted copier corpus data.trust.copy.seconds is a non-zero reading: the sum of "
          "the passes' copy_seconds to their rounding and within data.trust.wall_s, each pass's "
          "positive where it voted over a conflicted claim and within its own seconds, 0 where it "
          "voted over none",
          cw is not None and ser_ok and cw > 0 and cw <= ww
          and abs(cw - sum(r["copy_seconds"] for r in series)) <= (len(series) + 1) * 5e-7
          and any(r["conflicted_claims"] for r in series)
          and all((r["copy_seconds"] > 0) == bool(r["conflicted_claims"])
                  and r["copy_seconds"] <= r["seconds"] for r in series),
          f"{cw} of {ww}; (conflicted, copy_seconds, seconds) per pass {per}")

    # ---- T9: the cadence audit's line for the book is the root's ---------------------------------------
    # RUN's two sentences are a cadence's, and the book is armed by DATA_TRUST and passes beside its
    # gate; so the root words the one line (spine/compose.py::_trust_audit) and hands the rest back
    # as RUN wrote them -- compared here against RUN.cadence_audit called afresh on the same mapping.
    # The join is fetched by name, so this file still runs, and these checks fail, on a tree
    # without it.
    tag = "cadence audit: 'data.trust' "
    # THE PROBE'S LINE IS THE ROOT'S TOO (2026-09-29, the flip's review): the audit stage hands
    # _trust_audit's lines on to _retention_audit, whose line for 'retention' tests/test_probe.py P16
    # reads. Here that line is set aside beside the book's, and the chain is what the audit equals.
    rtag = "cadence audit: 'retention' "
    _trust_audit = getattr(C, "_trust_audit", lambda s, lines, **kw: None)
    _retention_audit = getattr(C, "_retention_audit", lambda s, lines, **kw: list(lines))
    seen = {}
    for label, env in (("off", {}), ("off1", {"DATA_TRUST_EVERY": "1"}),
                       ("obs0", {"DATA_TRUST": "observe", "DATA_TRUST_EVERY": "0"}),
                       ("obs_long", {"DATA_TRUST": "observe", "DATA_TRUST_EVERY": "100000"}),
                       ("obs10", {"DATA_TRUST": "observe", "DATA_TRUST_EVERY": "10"})):
        s = build(**env)
        rw = _run_windows(s)
        audit = [w for w in s.warnings if w.startswith("cadence audit:")]
        theirs = run_api.cadence_audit(s.configs["RUN"], run_windows=rw, periods=_periods(s))
        ours = _trust_audit(s, theirs, run_windows=rw, periods=_periods(s))
        seen[label] = ([w for w in audit if w.startswith(tag)], int(rw),
                       [w for w in audit if not w.startswith((tag, rtag))]
                       == [w for w in theirs if not w.startswith((tag, rtag))]
                       and len(audit) == len(theirs) and ours is not None
                       and _retention_audit(s, ours, run_windows=rw, periods=_periods(s)) == audit)
    off_l, off1_l = seen["off"][0], seen["off1"][0]
    check("T9 at 'off' (the file's arm) the audit's one 'data.trust' line is the root's: DISARMED by "
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
          "every audit line but the book's and the probe's (tests/test_probe.py P16) is RUN's own, the "
          "count unchanged: the root rewords the book's line and adds none",
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

    _sr6(tmp, cop_dir)


def _sr6(tmp, cop_dir):
    """SR6's COPY DETECTION (2026-09-28, Proposal 04 SR6 and §1 item 8's standing rule (2); register
    §8 3.7; docs/04_CONTRACT.md Q-DATA-12), on model-free tables in §8 0.6's td_stress style and
    through the loop. Operation only: whether it catches copies in E5's worlds is §8 5.12's, on GPU."""
    dcp = dat_of(DATA_TRUST_COPY="accu", **SR6_ENV)
    doff = dat_of(**SR6_ENV)
    t_ok, f_ok = 21 / 22, 1 / 22                    # r of a source right / wrong on all 20 keys

    # ---- SR6-1: a planted copy of a liar is reported dependent, at the hand-computed posterior ------
    units, srcs = records(SR6_X, SR6_ORDER)
    f = observe(dcp, units, srcs)
    fo = observe(doff, units, srcs)
    got = {(q[0], q[1]): q for q in f.copy_pairs}
    want = {}
    for i, e in enumerate(SR6_ORDER):
        for later in SR6_ORDER[i + 1:]:
            both = {e, later}
            if both <= {"a", "b", "d"}:
                want[(e, later)] = (hand_posterior(20, {}, 0, t_ok), 20, 0, 0, "independent")
            elif both == {"l", "c"}:
                want[(e, later)] = (hand_posterior(0, {2: 20}, 0, f_ok), 0, 20, 0, "dependent")
            else:
                want[(e, later)] = (hand_posterior(0, {}, 20, f_ok), 0, 0, 20, "independent")
    bad = [k for k in want if k not in got or not close(got[k][2], want[k][0])
           or tuple(got[k][3:]) != want[k][1:]]
    c = f.counters
    g = f.gates[2]
    check(f"SR6-1 a planted copy of a liar (c, first seen after l) is reported DEPENDENT at the "
          f"hand-computed posterior {want[('l', 'c')][0]:.10f} -- 1 - c + c n/(1 - A) per shared false "
          f"value, n = 2, A = 1/22 -- over 20 shared false claims; the three truthful pairs certified "
          f"at {want[('a', 'b')][0]:.6f} (20 shared true), the other eleven at "
          f"{want[('a', 'l')][0]:.3g} (20 differing); the pair is (l, c) by first sight, not by name",
          not bad and list(got) == list(want) and ("c", "l") not in got
          and c["data.trust.copy.pairs_judged"] == 15 and c["data.trust.copy.pairs_dependent"] == 1
          and c["data.trust.copy.pairs_certified"] == 14 and c["data.trust.copy.votes_discounted"] == 20
          and c["data.trust.copy.passes"] == 1
          and g.name == "data.trust.copy" and g.fired and (g.value, g.threshold) == (1, 15),
          f"wrong {[(k, got.get(k), want[k]) for k in bad[:2]]}; {c}")
    check("SR6-1 on this table the discount decides no key -- the truthful three outvote the copy and "
          "its source either way -- so the book's evidence and trust are the undiscounted vote's",
          f.evidence == fo.evidence and f.trust == fo.trust
          and f.trust == {"a": 1.0, "b": 1.0, "d": 1.0, "l": 0.3, "c": 0.3, "n": 0.3})
    # A PARTIAL COPY: on 4 of the 20 keys c states the truth, so it differs from l there.
    rows = [(k, dict(per, c="t") if i < 4 else per) for i, (k, per) in enumerate(SR6_X)]
    fp = observe(dcp, *records(rows, SR6_ORDER))
    q = next((x for x in fp.copy_pairs if x[:2] == ["l", "c"]), None)
    w = hand_posterior(0, {2: 16}, 4, 5 / 22)
    check(f"SR6-1 a partial copy (c copies l on 16 keys and states the truth on 4) is still dependent, "
          f"at the hand-computed {w:.10f}: 16 shared false (n = 2) and 4 differing, each x (1 - c), "
          f"with c's r 5/22; its 16 shared votes are discounted",
          q is not None and close(q[2], w) and q[3:] == [0, 16, 4, "dependent"]
          and fp.counters["data.trust.copy.votes_discounted"] == 16, str(q))

    # ---- SR6-2: two independent truthful sources are certified independent ----------------------------
    rows2 = [(f"x{i:02d}", {"a": "t", "b": "t", "l": "f"}) for i in range(20)]
    f2 = observe(dcp, *records(rows2, ("a", "b", "l")))
    f2o = observe(doff, *records(rows2, ("a", "b", "l")))
    got2 = {(x[0], x[1]): x for x in f2.copy_pairs}
    w_ab = hand_posterior(20, {}, 0, t_ok)
    g2 = f2.gates[2]
    check(f"SR6-2 two truthful sources that agree on 20 conflicted claims are CERTIFIED independent at "
          f"the hand-computed {w_ab:.10f} (below DATA_TRUST_COPY_P=0.5), both against the liar at "
          f"{hand_posterior(0, {}, 20, f_ok):.3g}; nothing is discounted, the gate is armed but did "
          f"not fire (0 vs 3), and the vote is the undiscounted one",
          set(got2) == {("a", "b"), ("a", "l"), ("b", "l")} and close(got2[("a", "b")][2], w_ab)
          and all(x[6] == "independent" for x in f2.copy_pairs)
          and f2.counters["data.trust.copy.pairs_certified"] == 3
          and f2.counters["data.trust.copy.pairs_dependent"] == 0
          and f2.counters["data.trust.copy.votes_discounted"] == 0
          and g2.reachable and not g2.fired and (g2.value, g2.threshold) == (0, 3)
          and (f2.evidence, f2.trust) == (f2o.evidence, f2o.trust), str(f2.copy_pairs))
    # AGREEMENT ON TRUE VALUES IS WHAT ACCURATE SOURCES DO, and the model cannot call it a copy at these
    # values: with r = (n + 1)/(n + 2) the likelihood ratio (1 + 0.8/(n + 1))^n rises to e^0.8, so the
    # posterior rises to 0.2 e^0.8 / (0.2 e^0.8 + 0.8) = 0.3575 and never reaches 0.5.
    lim = 0.2 * math.exp(0.8) / (0.2 * math.exp(0.8) + 0.8)
    seq = []
    for n in (20, 60, 200):
        tab = {f"k{i}".encode(): {"a": {b"t": 3}, "b": {b"t": 3}, "l": {b"f": 3}} for i in range(n)}
        fz = D.Focus(mode="observe", table=tab, first_seen={"a": [0, 0], "b": [0, 1], "l": [0, 2]})
        D._trust_vote(fz, min_n=3, self_share=0.8, min_ev=10, floor=0.3, copy=(0.2, 0.8, 0.5))
        x = next(y for y in fz.copy_pairs if y[:2] == ["a", "b"])
        seq.append((n, x[2], hand_posterior(n, {}, 0, (n + 1) / (n + 2)), x[6]))
    check(f"SR6-2 the certificate holds as the agreement grows: at 20, 60 and 200 shared true claims "
          f"the pair's posterior rises toward {lim:.4f} and stays below 0.5, each the hand value",
          all(close(p, h) and v == "independent" and p < lim for _n, p, h, v in seq)
          and seq[0][1] < seq[1][1] < seq[2][1], str(seq))

    # ---- SR6-3: majority-false -- the discounted vote wins where the undiscounted one loses ----------
    units, srcs = records(SR6_X + SR6_Y, SR6_ORDER)
    f3 = observe(dcp, units, srcs)
    f3o = observe(doff, units, srcs)
    ev_off = {"a": [21 / 32, 30], "b": [t_ok, 20], "d": [t_ok, 20], "l": [11 / 32, 30],
              "c": [11 / 32, 30], "n": [f_ok, 20]}
    tr_off = {"a": (21 / 32) / t_ok, "b": 1.0, "d": 1.0, "l": (11 / 32) / t_ok,
              "c": (11 / 32) / t_ok, "n": 0.3}
    ev_on = {"a": [31 / 32, 30], "b": [t_ok, 20], "d": [t_ok, 20], "l": [1 / 32, 30],
             "c": [1 / 32, 30], "n": [f_ok, 20]}
    tr_on = {"a": 1.0, "b": t_ok / (31 / 32), "d": t_ok / (31 / 32), "l": 0.3, "c": 0.3, "n": 0.3}
    q3 = next((x for x in f3.copy_pairs if x[:2] == ["l", "c"]), None)
    w3 = hand_posterior(0, {2: 20, 1: 10}, 0, 1 / 32)
    check("SR6-3 undiscounted (DATA_TRUST_COPY=off), the copy and its source outvote a on the 10 Y "
          "keys, so the vote LOSES them: a agrees on 20 of 30 (r 21/32, t 0.6875), l and c on 10 "
          "(r 11/32, t 0.360), exactly as by hand",
          f3o.evidence == ev_off and f3o.trust == tr_off, f"{f3o.evidence} {f3o.trust}")
    check(f"SR6-3 with copy detection the pair (l, c) is dependent at the hand-computed {w3:.10f} -- "
          f"20 shared false at n = 2 and 10 at n = 1 once the Y keys go to a, c's r 1/32 -- c's 30 "
          f"shared votes are discounted, and the Y keys go to the truth: a agrees on all 30 (r 31/32, "
          f"t 1), l and c on none (floored at 0.3), b and d at t (21/22)/(31/32)",
          f3.evidence == ev_on and f3.trust == tr_on and q3 is not None and close(q3[2], w3)
          and q3[3:] == [0, 30, 0, "dependent"]
          and f3.counters["data.trust.copy.votes_discounted"] == 30,
          f"{f3.evidence} {f3.trust} {q3}")

    # ---- SR6-4: at 'off' the keys are ABSENT and the vote is C5's -------------------------------------
    g_off = f3o.gates[2]
    ev_p, t_p, n_p = prototype_vote({k: {s: dict(v) for s, v in per.items()}
                                     for k, per in f3o.table.items()},
                                    min_n=3, self_share=0.8, min_ev=10, t_min=0.3)
    moff = D.new_focus(dat_of(), None, None)
    check("SR6-4 at DATA_TRUST_COPY=off no data.trust.copy.* key exists, no pair is judged, the gate is "
          "UNREACHABLE naming DATA_TRUST_COPY='off', and the vote is C5's (the prototype's update() on "
          "the same table); at DATA_TRUST=off the gate names DATA_TRUST='off' and no key exists",
          not any(k.startswith("data.trust.copy.") for k in f3o.counters) and f3o.copy_pairs == []
          and not g_off.reachable and g_off.reason.startswith("DATA_TRUST_COPY='off'")
          and (f3o.evidence, f3o.trust, f3o.counters["data.trust.conflicted_claims"])
          == (ev_p, t_p, n_p)
          and moff.counters == {} and moff.gates[2].reason.startswith("DATA_TRUST='off'"))
    # THE VOTE CALLED DIRECTLY, on 300 random tables. The rates and thresholds drawn include the ends
    # DATA_TRUST_COPY_RATE and _P refuse by name since Q-DATA-12's review -- a rate of 0, a threshold
    # of 0 or 1 (_trust_copy) -- where the arithmetic is still the model's and no configuration
    # reaches it: the draw is kept whole, so the tables are the ones the build compared.
    rnd = random.Random(23)
    vbad, nbad, n_dep = [], [], 0
    for trial in range(300):
        srcs_ = [f"s{i}" for i in range(rnd.randint(2, 7))]
        tab = {}
        for key in range(rnd.randint(1, 40)):
            per = {}
            for src in rnd.sample(srcs_, rnd.randint(1, len(srcs_))):
                per[src] = {bytes([97 + v]): rnd.randint(1, 6)
                            for v in rnd.sample(range(4), rnd.randint(1, 2))}
            tab[str(key).encode()] = per
        seen = {s: [rnd.randint(0, 1), rnd.randint(0, 999)] for s in srcs_ if rnd.random() < 0.9}
        kw = dict(min_n=rnd.randint(1, 4), self_share=rnd.choice((0.5, 0.6, 0.8, 1.0)),
                  min_ev=rnd.randint(1, 8))
        model = (rnd.choice((0.05, 0.2, 0.5, 0.9)), rnd.choice((0.0, 0.3, 0.8, 1.0)),
                 rnd.choice((0.0, 0.3, 0.5, 0.9, 1.0)))
        fz = D.Focus(mode="observe", table=dict(tab), first_seen=dict(seen))
        n_conf = D._trust_vote(fz, floor=0.3, copy=model, **kw)
        ev, t, n, pairs = prototype_copy_vote(tab, seen, t_min=0.3, prior=model[0], rate=model[1],
                                              p=model[2], **kw)
        mine = {(x[0], x[1]): x for x in fz.copy_pairs}
        n_dep += sum(1 for x in fz.copy_pairs if x[6] == "dependent")
        if ((fz.evidence, fz.trust, n_conf) != (ev, t, n) or set(mine) != set(pairs)
                or any(not close(mine[k][2], pairs[k][0]) or tuple(mine[k][3:6]) != pairs[k][1:]
                       for k in pairs)):
            vbad.append((trial, model, kw))
        # NOTHING DEPENDENT, NOTHING MOVED: at a threshold of 1.0 no posterior is above it -- which is
        # why DATA_TRUST_COPY_P refuses 1 by name (the review), and why this arm is reached directly.
        fz1 = D.Focus(mode="observe", table=dict(tab), first_seen=dict(seen))
        fz0 = D.Focus(mode="observe", table=dict(tab), first_seen=dict(seen))
        D._trust_vote(fz1, floor=0.3, copy=(model[0], model[1], 1.0), **kw)
        D._trust_vote(fz0, floor=0.3, **kw)
        if (fz1.evidence, fz1.trust) != (fz0.evidence, fz0.trust) or \
                fz1.counters.get("data.trust.copy.votes_discounted") not in (0, None):
            nbad.append(trial)
    check(f"SR6-4 on 300 random tables (random first sights, priors 0.05-0.9, rates 0-1 and "
          f"thresholds 0-1, the ends the levers refuse included; {n_dep} dependent pairs among "
          f"them) the vote with copy detection, called directly, equals a transcription of the "
          f"plan's model -- evidence, trust and the conflicted count exactly, every judged pair's "
          f"counts exactly and its posterior (by Bayes' rule in product form) to 1e-9 -- and a "
          f"detection that finds no pair above its threshold moves nothing",
          not vbad and not nbad and n_dep > 0, f"model {vbad[:2]}; moved {nbad[:3]}")

    # ---- SR6-5: every end at which no claim moves a verdict is refused by name; the domains past them --
    msgs = []
    for v in ("0.0", "1.0"):
        try:
            D.new_focus(dat_of(DATA_TRUST_COPY="accu", DATA_TRUST_COPY_PRIOR=v, **SR6_ENV), None, None)
            msgs.append(None)
        except _lever.LeverError as e:
            msgs.append(str(e))
        try:
            build(DATA_TRUST="observe", DATA_TRUST_COPY="accu", DATA_TRUST_COPY_PRIOR=v)
            msgs.append(None)
        except _lever.LeverError as e:
            msgs.append(str(e))
    held = D.new_focus(dat_of(DATA_TRUST_COPY="off", DATA_TRUST_COPY_PRIOR="0.0", **SR6_ENV), None, None)
    try:
        dat_of(DATA_TRUST_COPY_PRIOR="1.5")
        dom = None
    except _lever.LeverError as e:
        dom = str(e)
    check("SR6-5 DATA_TRUST_COPY_PRIOR at 0 or 1 is refused by name when the detection is on -- at "
          "DATA.new_focus and through compose -- as a certainty no count moves; at DATA_TRUST_COPY=off "
          "it is not read; 1.5 is refused by the lever's declared domain at the first read",
          all(m is not None and m.startswith(f"DATA_TRUST_COPY_PRIOR={v}")
              for m, v in zip(msgs, ("0.0", "0.0", "1.0", "1.0")))
          and held.copy_mode == "off" and dom is not None
          and dom.startswith("DATA_TRUST_COPY_PRIOR=1.5") and "domain" in dom, f"{msgs} {dom}")
    # THE REVIEW's ENDS (Q-DATA-12's review): a threshold of 0 or 1 and a rate of 0, each admitted by
    # its lever's closed domain and each an end at which no claim moves a verdict. Driven on SR6-1's
    # table before it: at DATA_TRUST_COPY_P=1.0 the planted copy was certified independent and the
    # gate read armed, not fired, 0 vs 15; at 0.0 the truthful pair (a, b) was dependent, 15 vs 15;
    # at DATA_TRUST_COPY_RATE=0 every posterior was the prior, 0.2 -- every pair certified at
    # DATA_TRUST_COPY_P=0.5 and every pair dependent at 0.1, with nothing discounted.
    got5 = []
    for name, v, why in (("DATA_TRUST_COPY_P", "0.0", "strictly between 0 and 1"),
                         ("DATA_TRUST_COPY_P", "1.0", "strictly between 0 and 1"),
                         ("DATA_TRUST_COPY_RATE", "0.0", "posterior is the prior")):
        for via in ("new_focus", "compose"):
            try:
                if via == "new_focus":
                    D.new_focus(dat_of(DATA_TRUST_COPY="accu", **{name: v}, **SR6_ENV), None, None)
                else:
                    build(DATA_TRUST="observe", DATA_TRUST_COPY="accu", **{name: v})
                got5.append((name, v, via, why, None))
            except _lever.LeverError as e:
                got5.append((name, v, via, why, str(e)))
    held5 = D.new_focus(dat_of(DATA_TRUST_COPY="off", DATA_TRUST_COPY_P="1.0",
                               DATA_TRUST_COPY_RATE="0.0", **SR6_ENV), None, None)
    check("SR6-5 DATA_TRUST_COPY_P at 0 or 1 and DATA_TRUST_COPY_RATE at 0 are refused by name when "
          "the detection is on -- at DATA.new_focus and through compose -- a threshold every "
          "posterior clears or none can, and a rate at which every posterior is the prior; at "
          "DATA_TRUST_COPY=off neither is read",
          all(m is not None and m.startswith(f"{name}={v}:") and why in m
              for name, v, _via, why, m in got5) and held5.copy_mode == "off",
          str([(name, v, via, m if m is None else m[:48]) for name, v, via, _w, m in got5]))
    # THE RATE's TOP END IS LEGAL, and on it both verdicts are reached: a copier that copies every
    # value never differs from its source, so one differing claim proves a pair independent (its
    # posterior exactly 0), and the shared false values still make the copy dependent.
    f5 = observe(dat_of(DATA_TRUST_COPY="accu", DATA_TRUST_COPY_RATE="1.0", **SR6_ENV),
                 *records(SR6_X, SR6_ORDER))
    v5 = {(q[0], q[1]): q for q in f5.copy_pairs}
    w5c = hand_posterior(0, {2: 20}, 0, f_ok, rate=1.0)        # the copy: 20 shared false, n = 2
    w5t = hand_posterior(20, {}, 0, t_ok, rate=1.0)           # a truthful pair: 20 shared true
    g5 = f5.gates[2]
    diff5 = [q for q in f5.copy_pairs if q[5] > 0]
    check(f"SR6-5 DATA_TRUST_COPY_RATE=1.0 is legal and reaches both verdicts: on SR6-1's table the "
          f"copy is dependent at the hand-computed {w5c:.10f}, the truthful pairs certified at "
          f"{w5t:.6f}, each of the eleven pairs that differ certified at exactly 0, and the gate "
          f"fires, 1 vs 15",
          ("l", "c") in v5 and close(v5[("l", "c")][2], w5c) and v5[("l", "c")][6] == "dependent"
          and ("a", "b") in v5 and close(v5[("a", "b")][2], w5t)
          and v5[("a", "b")][6] == "independent" and len(diff5) == 11
          and all(q[2] == 0.0 and q[6] == "independent" for q in diff5)
          and g5.fired and (g5.value, g5.threshold) == (1, 15), str(f5.copy_pairs))

    # ---- SR6-6: through the loop -- nothing trained on moves, the continuation is exact ---------------
    # `cop_dir` is _main's planted copier corpus, the one T8 runs on.
    E6 = dict(E5_BASE, DATA_DIR=cop_dir, DATA_TRUST_COPY="accu")
    ua = build(**E6)
    rua = loop.run(ua, progress=False)
    uo = build(**dict(E6, DATA_TRUST_COPY="off"))
    ruo = loop.run(uo, progress=False)
    fa, fo = ua.focus, uo.focus
    pq = next((x for x in fa.copy_pairs
               if {x[0], x[1]} == {"train/pc/liar.txt", "train/pc/copy.txt"}), None)
    w6 = hand_posterior(0, {2: 40}, 0, 1 / 42)
    row = rua.report["DATA(trust)"]
    check(f"SR6-6 on the planted corpus with a copy of the liar and a second liar (six files, 40 keys "
          f"each carrying three values), a whole two-epoch run reports the liar's copy DEPENDENT at "
          f"the hand-computed {w6:.10f} (40 shared false at n = 2, the later file's r 1/42), every "
          f"other pair certified; the DATA(trust) row carries the fired gate, the pair's line and "
          f"data.trust.copy.seconds as a float; the truthful files keep trust 1 and the three liars "
          f"are floored",
          pq is not None and close(pq[2], w6) and pq[3:] == [0, 40, 0, "dependent"]
          and fa.counters["data.trust.copy.pairs_dependent"] == 1
          and fa.counters["data.trust.copy.pairs_judged"] == 15
          and row.get("gate:data.trust.copy", ("",))[0] == "fired"
          and "DEPENDENT" in row.get(f"pair:{pq[0]}|{pq[1]}", "")
          and type(row.get("data.trust.copy.seconds")) is float
          and fa.trust == {"train/pa/cred.txt": 1.0, "train/pa/cred2.txt": 1.0,
                           "train/pb/corrob.txt": 1.0, "train/pc/copy.txt": 0.3,
                           "train/pc/liar.txt": 0.3, "train/pc/liar2.txt": 0.3}
          and all("copy_pairs" in x for x in rua.trust_series),
          f"{pq} {fa.trust} {row.get('gate:data.trust.copy')}")
    # THE COPY STEPS ARE TIMED (Q-DATA-12's review: no check read a non-zero reading before it, and a
    # build whose clock never moved passed every one). The row's float is the sum of the passes' own
    # copy seconds, above 0 and inside wall_s -- the steps run inside the passes the root times --
    # and a pass's reading is positive where its vote had a conflicted claim, 0 where it had none.
    ser = rua.trust_series
    cs, ws = row.get("data.trust.copy.seconds"), row.get("data.trust.wall_s")
    check("SR6-6 the copy steps are timed: that run's data.trust.copy.seconds is above 0, the sum of "
          "its passes' copy_seconds to their rounding and within its data.trust.wall_s; each pass's "
          "reading is positive where its vote had a conflicted claim, within its own seconds, and "
          "exactly 0 where it had none",
          type(cs) is float and type(ws) is float and cs > 0 and cs <= ws
          and abs(cs - sum(x["copy_seconds"] for x in ser)) <= (len(ser) + 1) * 5e-7
          and all((x["copy_seconds"] > 0) == bool(x["conflicted_claims"])
                  and x["copy_seconds"] <= x["seconds"] for x in ser),
          f"{cs} of {ws}; {[(x['conflicted_claims'], x['copy_seconds'], x['seconds']) for x in ser]}")
    # A SECOND run() OVER ONE System (the review): both floats are that run()'s. The row printed
    # Focus.copy_seconds -- DATA's running float, every copy step since new_focus -- until then, so a
    # second run()'s copy seconds held the first's too and overstated their share of its wall_s.
    tw = build(**E6)
    loop.run(tw, max_windows=70, progress=False)
    first = float(tw.focus.copy_seconds)
    rt2 = loop.run(tw, max_windows=70, progress=False)
    row2, ser2 = rt2.report["DATA(trust)"], rt2.trust_series
    cs2, ws2 = row2.get("data.trust.copy.seconds"), row2.get("data.trust.wall_s")
    check("SR6-6 on a second run() over one System data.trust.copy.seconds is that run()'s, as its "
          "data.trust.wall_s is: the sum of its own passes' copy_seconds and the growth of "
          "Focus.copy_seconds over it, within its wall_s -- not the running total, which holds the "
          "first run()'s copy steps too",
          first > 0 and type(cs2) is float and type(ws2) is float and cs2 > 0 and cs2 <= ws2
          and abs(cs2 - sum(x["copy_seconds"] for x in ser2)) <= (len(ser2) + 1) * 5e-7
          and abs(cs2 - (float(tw.focus.copy_seconds) - first)) <= 1e-6,
          f"first run() {first:.6f}; second {cs2} of {ws2}, its passes "
          f"{[x['copy_seconds'] for x in ser2]}; Focus.copy_seconds {tw.focus.copy_seconds:.6f}")
    da, do_ = sd.digest(ua, exclude=EXCL, detail=True), sd.digest(uo, exclude=EXCL, detail=True)
    ia, io_ = flat_ints(rua.report), flat_ints(ruo.report)
    check("SR6-6 copy detection moves nothing the run trains on: 'accu' against 'off' on that run -- "
          "float-exact losses, state digests equal but DATA.focus, the same claim table, sketch, first "
          "sights, cursor and carry, every integer counter equal but data.trust.copy.*, and no copy "
          "key at 'off'",
          list(rua.loss_curve) == list(ruo.loss_curve) and da == do_
          and list(fa.table.items()) == list(fo.table.items())
          and all(getattr(fa, k) == getattr(fo, k)
                  for k in ("sketch", "first_seen", "cursor", "stream", "carry"))
          and {k: v for k, v in ia.items() if not k[1].startswith("data.trust.copy.")} == io_
          and not any(k.startswith("data.trust.copy.") for k in fo.counters),
          f"digest differs at {sd.differing(da, do_)}")
    d = os.path.join(tmp, "sr6")
    p = build(CKPT_DIR=d + "/p", **E6)
    rp = loop.run(p, max_windows=70, progress=False)
    tails = [x for x in rp.trust_series if x["kind"] == "tail"]
    rec = torch.load(os.path.join(d, "p", "ckpt.pt"), map_location="cpu",
                     weights_only=False)["payload"]["DATA"]["focus"]
    c = build(CKPT_RESUME=os.path.join(d, "p", "ckpt.pt"), CKPT_DIR=d + "/c", **E6)
    rc = loop.run(c, progress=False)
    want_ctr = {}
    if tails:
        _t = 1 if tails[0]["conflicted_claims"] else 0
        for k, extra in (("data.trust.passes", 1), ("data.trust.updates", _t),
                         ("data.trust.copy.passes", _t)):
            if extra:
                want_ctr[k] = (fa.counters[k], fa.counters[k] + extra)
    check("SR6-6 the continuation is exact with copy detection on: a continuing resume from window 70 "
          "ends with the uninterrupted run's book -- its judged pairs, posteriors and verdicts "
          "included -- every counter equal but the parent's tail pass, the losses continuing exactly",
          not book_diff(c.focus, fa) and counter_diff(fa, c.focus) == want_ctr and len(tails) == 1
          and list(rc.loss_curve) == list(rua.loss_curve[70:])
          and "copy" in rec and rec["copy"]["counters"]["data.trust.copy.passes"] >= 1,
          f"book {book_diff(c.focus, fa)}, counters {counter_diff(fa, c.focus)}")
    # THE RECORD's THREE READINGS, on that parent's own record: put back whole at 'accu' (its pairs,
    # and its copy counts into the book's counters, which the record's 'counters' does not repeat);
    # started at 0 from a record without a copy part (a book older than the detection); held
    # unchanged at 'off', with no copy key in the book's counters.
    d6 = dat_of(**E6)
    back = D.new_focus(d6, None, None, restored=copy.deepcopy(rec))
    bare = copy.deepcopy(rec)
    bare.pop("copy")
    fresh = D.new_focus(d6, None, None, restored=bare)
    heldf = D.new_focus(dat_of(**dict(E6, DATA_TRUST_COPY="off")), None, None,
                        restored=copy.deepcopy(rec))
    ck = [k for k in back.counters if k.startswith("data.trust.copy.")]
    check("SR6-6 the checkpoint's copy part: 'counters' holds no copy key; at 'accu' the part is put "
          "back whole -- the judged pairs and the counts -- and round-trips through stream_state; a "
          "record without one starts the detection at 0; at 'off' it is held unchanged and no copy "
          "key is in the book's counters",
          not any(k.startswith("data.trust.copy.") for k in rec["counters"])
          and back.copy_pairs == rec["copy"]["pairs"] and len(ck) == 5
          and {k: back.counters[k] for k in ck} == rec["copy"]["counters"]
          and sd.digest_payload({"f": D._focus_state(back)}) == sd.digest_payload({"f": rec})
          and fresh.copy_pairs == [] and all(fresh.counters[k] == 0 for k in ck)
          and heldf.copy_mode == "off" and heldf.copy_held == rec["copy"]
          and not any(k.startswith("data.trust.copy.") for k in heldf.counters)
          and D._focus_state(heldf)["copy"] == rec["copy"],
          f"{ck} {back.copy_pairs[:1]} {rec['copy']['pairs'][:1]}")
    off = build(CKPT_RESUME=d + "/p", CKPT_DIR=d + "/off", **dict(E6, DATA_TRUST_COPY="off"))
    roff = loop.run(off, max_windows=20, progress=False)
    held_rec = torch.load(os.path.join(d, "off", "ckpt.pt"), map_location="cpu",
                          weights_only=False)["payload"]["DATA"]["focus"]
    on = build(CKPT_RESUME=d + "/off", CKPT_DIR=d + "/on", **E6)
    ron = loop.run(on, progress=False)
    own = sum(1 for x in ron.trust_series if x["conflicted_claims"])
    g_mid = off.focus.gates[2]
    check("SR6-6 ON -> OFF -> ON for the detection: the 'off' leg's book reads on, prints no "
          "data.trust.copy.* key, its gate UNREACHABLE naming DATA_TRUST_COPY='off' and the held "
          "part, and its checkpoint carries the parent's copy part unchanged; the grandchild ends "
          "with the uninterrupted run's book, its data.trust.copy.passes the parent's plus its own "
          "passes that voted over a conflict, the losses continuing exactly",
          not any(k.startswith("data.trust.copy.") for k in off.focus.counters)
          and not any(k.startswith("data.trust.copy.")
                      for k in roff.report["DATA(trust)"] if isinstance(k, str))
          and not g_mid.reachable and g_mid.reason.startswith("DATA_TRUST_COPY='off'")
          and "carried unchanged" in g_mid.reason
          and sd.digest_payload({"c": held_rec.get("copy")}) == sd.digest_payload({"c": rec["copy"]})
          and not book_diff(on.focus, fa)
          and on.focus.counters["data.trust.copy.passes"]
          == rec["copy"]["counters"]["data.trust.copy.passes"] + own
          and list(ron.loss_curve) == list(rua.loss_curve[90:]),
          f"book {book_diff(on.focus, fa)}, copy.passes "
          f"{on.focus.counters.get('data.trust.copy.passes')} vs "
          f"{rec['copy']['counters']['data.trust.copy.passes']} + {own}")


if __name__ == "__main__":
    if "--t4-child" in sys.argv:
        _t4_child()
        sys.exit(0)
    sys.exit(main())
