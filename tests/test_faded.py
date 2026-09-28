"""FADED AREAS: memory occupancy by area, the culls and merges of experts whose most-served area has
faded, and FAB_FADED_CULL (register §8 3.1, NEW-10 and C37; docs/04_CONTRACT.md Q-FAB-18 and
Q-MEM-16), driven through DATA's, FAB's and MEM's entry points and through the real composition root
and loop, with real checkpoints written under a temporary directory.

    python3 tests/test_faded.py        # exit 0 = every check passed

WHY IT EXISTS. NEW-10 and C37 rule that every training run reports how much of its memory each area
holds and how many of the experts its management pass removes served an area the schedule has
faded -- the readings that say whether a parent leaves training with its faded areas' memory and
experts destroyed -- and that the continue preset may DEFER those removals (an E2 arm until then).
The counters are telemetry and must not move a number a default run produces; the deferral must
defer and not substitute. Each check below pins one of those promises.

  F1  THE SCHEDULE'S FADED SETS: Plan.faded on the generated four-area schedule
      (derive.phase_schedule(4) = [[0, 1], [1, 2], [1, 2], [2, 3]]) is [(), (0,), (0,), (0, 1)],
      printed by name as data.phase_faded; hand-computed on explicit schedules (alternating,
      fade-and-return, stationary, pure-add, reversed); Plan.parent_faded hand-computed from a parent
      record's DRAWN areas (Areas.drawn), not its declared ones -- an area the parent declared and
      never drew is not faded -- with data.parent_faded ABSENT on a fresh run and printed on a
      resumed one.
  F2  THE AREA ID: spine/derive.py::area_id is crc32 of the label masked to 31 bits (pinned values),
      and DATA.open_areas refuses two labels on one id -- a full crc32 collision and one only the mask
      makes -- naming both labels and data.area_id_collision, whose Gate reads 0 in every Areas that
      exists, beside data.area_label_collision's; data.area_refused's reason names the refusal.
  F3  THE AREA BOOK'S ARITHMETIC under scripted routing: FAB.observe credits each computed expert the
      routing mass `use` gets, under its window's area; a negative id credits nothing, area_id=None
      touches no book and leaves fab.area_windows ABSENT, a scalar books every row, a mis-sized list
      is refused; _merge_into sums the books; _remove moves the survivor's book and clears the last
      row; _claim_slot clears; FAB.state_dict / load_state_dict carry it, and a blob without it
      restores empty books.
  F4  THE COUNT ON A SCRIPTED PASS: faded, live and empty-book removals by the merge, the failure
      cull and the utilization cull are counted apart, at hand-counted values, each with its per-pass
      gauge; faded=None leaves every step-7 key ABSENT, and a pass handed none after one handed a set
      drops the per-pass gauges; a set leaves the three counts PRESENT (0 where nothing faded was
      removed) and the deferral pair ABSENT at 'as_is'; the ManageReport carries the pass's counts.
  F5  'defer' ON A SCRIPTED PASS REMOVES EXACTLY WHAT 'as_is' REMOVES FROM THE SAME POPULATION, LESS
      THE FADED REMOVALS, down every path a deferral can leak through: the utilization cull (the
      deferred keep their budget slots, so the next live-area expert is not culled in their place);
      a failure-cull deferral followed by the utilization cull (the budget is sized without it); a
      merge deferral followed by the pressure gate (the gate is read on the population 'as_is'
      holds); the merge scan (a deferred absorbee pairs with nobody else); the utilization ranking of
      a survivor whose pair was left apart (ranked by the mass the merge would have given it); the
      failure cull's walk over the slots the merge refilled (the one 'as_is' walks); a second pass
      defers the same experts again (events, not experts); and a seeded sweep of random populations
      through every path together, built at FAB_CONTRIB=1 so its load-bearing experts are spared
      (Q-FAB-19's review: the spare reads a contribution there only). The failure-cull and merge
      reasons name the deferrals.
  F6  A PHASED RUN (B3's shape, 314 windows over the four phases): fab.culled_faded_area,
      fab.merged_faded_area and fab.faded_unknown equal an independent recount of every expert the
      management passes removed, against the set each pass was handed, and that set is Plan.faded at
      the phase of the pass's window; each pass's gauges equal its own recount; every expert's area
      book sums to its `use`; MEM's occupancy by area sums to the store's active entries, and every
      active entry's area is the label of the byte its `pos` records.
  F7  'defer' IN THE SAME RUN: each pass removes exactly what 'as_is' removes from the population
      that entered it (a copy of that population run at faded=None), less the faded removals -- so
      no live-area expert is merged or culled in a deferred one's place -- and the pass's deferral
      events are those faded removals; after the fade no removed expert's most-served area is faded,
      and both deferral counts are > 0.
  F8  A PURE-ADD CHILD: a parent that trained eng alone, resumed at its epoch boundary by a child
      that schedules py alone -- eng is the child's Plan.parent_faded, data.parent_faded prints it,
      and every management pass of the child is handed it, from the first.
  F9  CONTINUATION: a continuing mid-epoch resume at 'as_is' and at 'defer' continues exactly, and
      ends with the uninterrupted run's area books and faded-area counts (and, at 'defer', its
      deferrals); a run that declares an area it never schedules records only the areas it drew,
      and its continuing child hands every pass the uninterrupted run's set (data.parent_faded [],
      data.drawn_assumed []), while a record written before the drawn list assumes every declared
      area drawn and says so; a checkpoint whose FAB area book and MEM area column are stripped (as a
      tree before them wrote it) continues exactly, its restored entries reading area -1
      (store.occupancy_unknown > 0) and the removals of experts whose books were not refilled
      counting as fab.faded_unknown.

B1, B3, B3r, B5, B6 and B6r -- the default runs are the tree before this, bit for bit -- are
tests/test_baseline.py's, run before every commit; they are not repeated here.

WHAT THIS FILE CANNOT SEE: whether deferring faded-area culls protects anything a held-out reading
can measure. That is E2's arm on GPU (§8 6.3), read through the retention probe. Everything here is
an operation check.
"""
import copy
import math
import os
import random
import shutil
import sys
import tempfile
import types
import zlib

_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(_ROOT, "src"))

import torch                                                       # noqa: E402
torch.set_num_threads(1)

from spine import lever as _lever                                  # noqa: E402
from spine import rng                                              # noqa: E402
from spine import loop                                             # noqa: E402
from spine import derive                                           # noqa: E402
from spine import assemble                                         # noqa: E402
from spine import units as U                                       # noqa: E402
from spine.compose import compose, _phase_of                       # noqa: E402
from data import api as data_api                                   # noqa: E402
from fabric import api as FAB                                      # noqa: E402

FAILS = []
DATA_DIR = os.path.join(os.path.abspath(_ROOT), "data")
TMP = tempfile.mkdtemp(prefix="faded_")
# tests/test_continuation.py's small base, and tests/test_baseline.py's B3 on top of it: a manage pass
# every 50 windows past a grace of two selections, so the passes reach culls and merges in all four
# phases, with the mint and the act B3 carries.
BASE = {"DATA_STREAM_BYTES": "60000", "SIG_WARMUP": "20", "FAB_N0": "256", "FAB_SLOTS": "512",
        "DATA_DIR": DATA_DIR}
B3 = {"FAB_MANAGE_EVERY": "50", "FAB_GRACE": "2", "TOK_GROW_EVERY": "30", "TOK_RETOK_EVERY": "150"}
AREAS = ["eng", "py", "num", "c"]
# The FAB unit populations: tests/test_fabric_internals.py's widths.
D_MODEL, SIG_D = 16, 12


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


def configs(base=None, **env):
    """A real, frozen Config set from assemble.build over a dict environment (never os.environ)."""
    _lever._reopen_assembly()
    rng.reset_issued()
    e = dict(base if base is not None else {"RUN_SEED": "7", "RUN_DEVICE": "cpu"})
    e.update({k: str(v) for k, v in env.items()})
    cfgs, _wires, warnings = assemble.build(e)
    if warnings:
        raise AssertionError(f"assemble.build warned on {e}: {warnings}")
    return cfgs


def areas_of(d, seed=0):
    """DATA.open_areas under `d`, with the issued streams forgotten: each call is a fresh run's."""
    rng.reset_issued()
    return data_api.open_areas(d, seed=seed)


def population(c, seed=1234):
    return FAB.build(c["FAB"], d_model=D_MODEL, signature_dim=SIG_D, device=torch.device("cpu"),
                     generator=rng.rng_for("fabric", seed, again=True))


def top(book):
    """An area book's most-served area, recomputed here: the largest mass, the smallest id on a tie,
    None for an empty book."""
    if not book:
        return None
    best = max(book.values())
    return min(k for k, v in book.items() if v == best)


# ==================================================================================================
# F1 -- the schedule's faded sets
# ==================================================================================================

def f1_faded_sets():
    d = configs({"DATA_DIR": DATA_DIR})["DATA"]
    areas = areas_of(d)
    plan = data_api.data_plan(d, areas, epochs=1, win_tokens=128, bytes_per_token=1.2)
    check("F1 the generated four-area schedule [[0,1],[1,2],[1,2],[2,3]] fades [(), (0,), (0,), (0,1)]",
          [list(p) for p in plan.schedule] == [[0, 1], [1, 2], [1, 2], [2, 3]]
          and plan.faded == ((), (0,), (0,), (0, 1)),
          f"schedule {plan.schedule}, faded {plan.faded}")
    check("F1 printed by name as data.phase_faded; a fresh run has no parent record, so Plan.parent_faded "
          "is () and data.parent_faded is ABSENT",
          plan.counters.get("data.phase_faded") == [[], ["eng"], ["eng"], ["eng", "py"]]
          and plan.parent_faded == () and "data.parent_faded" not in plan.counters,
          f"{plan.counters}")
    # Explicit schedules, by name and by index, hand-computed.
    cases = (
        ("eng|py|eng|py", ((), (0,), (1,), (0,))),            # alternating: each fades while the other plays
        ("0,1|1|0,1|2", ((), (0,), (), (0, 1))),             # fade and return: faded only where absent
        ("0,1,2,3", ((),)),                                  # stationary: nothing can fade
        ("py|py|py|py", ((), (), (), ())),                   # pure-add: nothing live before py
        ("c|num|py|eng", ((), (3,), (2, 3), (1, 2, 3))),     # reverse order, sorted by index
    )
    got = {}
    for sched, want in cases:
        dd = configs({"DATA_DIR": DATA_DIR}, DATA_PHASE_SCHED=sched)["DATA"]
        a = areas_of(dd)
        got[sched] = data_api.data_plan(dd, a, epochs=1, win_tokens=128, bytes_per_token=1.2).faded
    check("F1 explicit schedules fade as hand-computed: alternating, fade-and-return, stationary, "
          "pure-add, reversed", all(got[s] == w for s, w in cases),
          "; ".join(f"{s}: {got[s]}" for s, _w in cases))
    # Plan.parent_faded: the areas the lineage DREW that no phase of this schedule makes live, in Plan
    # order. A restore fills parent_names (every area the record declares) and drawn (the record's
    # list of the areas its streams drew); the two are set by hand here, as the restore sets them.
    dd = configs({"DATA_DIR": DATA_DIR}, DATA_PHASE_SCHED="py|py|num|num")["DATA"]
    a = areas_of(dd)
    a.parent_names[:] = ["c", "eng", "py"]
    a.drawn[:] = ["c", "eng", "py"]
    p = data_api.data_plan(dd, a, epochs=1, win_tokens=128, bytes_per_token=1.2)
    a2 = areas_of(d)
    a2.parent_names[:] = list(AREAS)
    a2.drawn[:] = list(AREAS)
    p2 = data_api.data_plan(d, a2, epochs=1, win_tokens=128, bytes_per_token=1.2)
    check("F1 Plan.parent_faded is the lineage's drawn areas this schedule never makes live, in Plan "
          "order -- (0, 3) = eng and c over 'py|py|num|num' -- and () with every drawn area "
          "scheduled; data.parent_faded prints both, the second as []",
          p.parent_faded == (0, 3) and p.counters.get("data.parent_faded") == ["eng", "c"]
          and p.faded == ((), (), (1,), (1,))
          and p2.parent_faded == () and p2.counters.get("data.parent_faded") == [],
          f"{p.parent_faded} {p.counters.get('data.parent_faded')} faded {p.faded}; "
          f"{p2.parent_faded} {p2.counters.get('data.parent_faded')}")
    # A DECLARED AREA IS NOT A DRAWN ONE (Q-FAB-18's review): a parent that declared c, eng and py and
    # drew eng alone -- py and c were in its DATA_AREAS and no phase of its schedule made them live --
    # leaves eng faded under 'py|py|num|num', and neither c nor py.
    a3 = areas_of(dd)
    a3.parent_names[:] = ["c", "eng", "py"]
    a3.drawn[:] = ["eng"]
    p3 = data_api.data_plan(dd, a3, epochs=1, win_tokens=128, bytes_per_token=1.2)
    check("F1 an area the parent declared and never drew is not parent-faded: declared c, eng, py and "
          "drew eng alone, so (0,) = eng over 'py|py|num|num', printed as ['eng'] -- where the "
          "declared list would have read (0, 3)",
          p3.parent_faded == (0,) and p3.counters.get("data.parent_faded") == ["eng"],
          f"{p3.parent_faded} {p3.counters.get('data.parent_faded')}")


# ==================================================================================================
# F2 -- the area id
# ==================================================================================================

def f2_area_id():
    pinned = {"eng": 435511819, "py": 1195352721, "num": 1547939694, "c": 112844655,
              "code_OOD": 1794634246, "01_rust": 1878914}
    got = {k: derive.area_id(k) for k in pinned}
    check("F2 derive.area_id is crc32 of the label's UTF-8 bytes masked to 31 bits (pinned values)",
          got == pinned and all(v == zlib.crc32(k.encode()) & 0x7fffffff for k, v in got.items())
          and all(0 <= v < 2 ** 31 for v in got.values()), f"{got}")
    # Two collision pairs, found by a birthday search over 8-character labels: the first shares its
    # full crc32 (8892033); the second differs only in the bit the mask drops (1901741477 against
    # 1901741477 + 2**31).
    for a, b in (("qh9par8f", "gd221zva"), ("g4bgcsbc", "gyz44zl0")):
        dd = configs({"DATA_DIR": DATA_DIR}, DATA_AREAS=f"{a},{b}", DATA_N_PROCESSES=2)["DATA"]
        try:
            areas_of(dd)
            check(f"F2 open_areas refuses {a!r} and {b!r} on one area id", False, "opened")
        except data_api.CorpusError as e:
            check(f"F2 open_areas refuses {a!r} and {b!r} on one area id "
                  f"({derive.area_id(a)}), naming both and data.area_id_collision",
                  derive.area_id(a) == derive.area_id(b) and a in str(e) and b in str(e)
                  and str(derive.area_id(a)) in str(e) and "data.area_id_collision" in str(e),
                  str(e)[:200])
    # THE REFUSAL'S ROW (Q-FAB-18's review): declared and, until then, written nowhere. A Gate beside
    # data.area_label_collision's, reading 0 against the entries it compared, and data.area_refused's
    # reason names the refusal.
    ga = {g.name: g for g in areas_of(configs({"DATA_DIR": DATA_DIR})["DATA"]).gates}
    idg, lbl, ref = (ga.get("data.area_id_collision"), ga.get("data.area_label_collision"),
                     ga.get("data.area_refused"))
    check("F2 every Areas carries data.area_id_collision as a Gate reading 0 against its 4 entries, "
          "beside data.area_label_collision's, and data.area_refused's reason names the area-id "
          "collision",
          idg is not None and lbl is not None and ref is not None
          and (idg.fired, idg.value, idg.threshold, idg.reachable) == (False, 0, 4, True)
          and (lbl.fired, lbl.value, lbl.threshold) == (False, 0, 4)
          and "area-id collision" in ref.reason and "area_id" in idg.reason,
          f"{idg}; {ref.reason[:120] if ref else None}")


# ==================================================================================================
# F3 -- the area book's arithmetic
# ==================================================================================================

def f3_book_arithmetic():
    c = configs(FAB_N0=6, FAB_SLOTS=12, FAB_CHAIN_K=2)
    pop = population(c)
    A, B, C = 11, 22, 33
    w = torch.tensor([[0.5, 0.3, 0.1, 0.05, 0.03, 0.02],
                      [0.05, 0.4, 0.02, 0.33, 0.12, 0.08],
                      [0.0, 0.0, 0.0, 0.0, 0.1, 0.9]])
    wl = w.tolist()
    out = types.SimpleNamespace(weights=w)
    loss = torch.tensor([3.0, 4.0, 5.0])
    FAB.observe(c["FAB"], pop, out, per_window_loss=loss, domain_id=0, area_id=[A, B, C])
    want = [{A: wl[0][0]}, {A: wl[0][1], B: wl[1][1]}, {}, {B: wl[1][3]}, {C: wl[2][4]},
            {C: wl[2][5]}]
    check("F3 observe credits each computed expert (top FAB_CHAIN_K=2 per row) its routing mass under "
          "its window's area, and fab.area_windows counts the 3 booked windows",
          [pop.area_use[i] for i in range(6)] == want and pop.counters.get("fab.area_windows") == 3,
          f"{[pop.area_use[i] for i in range(6)]}")
    check("F3 with every window's area known, each book sums to the expert's `use`",
          all(abs(sum(pop.area_use[i].values()) - float(pop.use[i])) < 1e-12 for i in range(6)))
    # A negative id credits nothing; None touches nothing; a scalar books every row; a short list is
    # refused.
    before = [dict(b) for b in pop.area_use[:6]]
    FAB.observe(c["FAB"], pop, out, per_window_loss=loss, domain_id=0, area_id=[-1, -1, -1])
    unchanged_neg = [dict(b) for b in pop.area_use[:6]] == before
    windows_neg = pop.counters.get("fab.area_windows")
    FAB.observe(c["FAB"], pop, out, per_window_loss=loss, domain_id=0)
    unchanged_none = [dict(b) for b in pop.area_use[:6]] == before
    check("F3 a negative area id credits nothing and adds no booked window; area_id=None touches no "
          "book", unchanged_neg and windows_neg == 3 and unchanged_none, f"windows {windows_neg}")
    fresh = population(c)
    FAB.observe(c["FAB"], fresh, out, per_window_loss=loss, domain_id=0)
    check("F3 a population no call handed an area_id has empty books and fab.area_windows ABSENT",
          all(not b for b in fresh.area_use) and "fab.area_windows" not in fresh.counters)
    FAB.observe(c["FAB"], fresh, out, per_window_loss=loss, domain_id=0, area_id=A)
    check("F3 a scalar area_id books every row under it",
          fresh.area_use[4] == {A: wl[2][4]} and fresh.area_use[1] == {A: wl[0][1] + wl[1][1]}
          and fresh.counters.get("fab.area_windows") == 3, f"{fresh.area_use[:6]}")
    try:
        FAB.observe(c["FAB"], fresh, out, per_window_loss=loss, domain_id=0, area_id=[A, B])
        check("F3 a mis-sized area_id list is refused", False, "accepted")
    except ValueError as e:
        check("F3 a mis-sized area_id list is refused", "area_id" in str(e), str(e)[:120])
    # The merge sums; the removal moves the survivor's book and clears the last row; a birth clears.
    rank = int(pop.B.shape[1])
    FAB._merge_into(pop, 1, 0, rank)
    check("F3 _merge_into sums the absorbed expert's book into the survivor's, area by area",
          pop.area_use[1] == {A: wl[0][1] + wl[0][0], B: wl[1][1]} and pop.area_use[0] == {A: wl[0][0]},
          f"{pop.area_use[1]}")
    last_book = pop.area_use[5]
    moved = FAB._remove(pop, 3)
    check("F3 _remove(3) moves the last expert's book object into slot 3 and clears slot 5 with a new "
          "dict", moved == 5 and pop.area_use[3] is last_book and pop.area_use[3] == {C: wl[2][5]}
          and pop.area_use[5] == {} and pop.area_use[5] is not last_book and int(pop.n_live) == 5)
    pop.area_use[5] = {A: 1.0}
    FAB._claim_slot(pop, 5, 10)
    check("F3 _claim_slot clears the slot's book", pop.area_use[5] == {})
    # The checkpoint carries it; a blob without it restores empty books.
    sd = FAB.state_dict(c["FAB"], pop)
    back = population(c)
    FAB.load_state_dict(c["FAB"], back, sd, sidecar=sd["sidecar"])
    check("F3 FAB.state_dict / load_state_dict carry the area books exactly, as sorted [id, mass] pairs",
          [back.area_use[i] for i in range(12)] == [pop.area_use[i] for i in range(12)]
          and sd["books"]["area_use"][1] == [[A, wl[0][1] + wl[0][0]], [B, wl[1][1]]],
          f"{sd['books']['area_use'][:3]}")
    del sd["books"]["area_use"]
    old = population(c)
    FAB.load_state_dict(c["FAB"], old, sd, sidecar=sd["sidecar"])
    check("F3 a blob written before the book existed restores every expert with an empty book",
          all(not b for b in old.area_use) and list(old.use[:5]) == list(pop.use[:5]))


# ==================================================================================================
# F4 / F5 -- the count and the deferral, on scripted passes
# ==================================================================================================

F, L = 101, 202          # a faded area's id and a live one's
M = 303                  # a second live area, for the sweep's books


def util_population(mode, faded_books=True):
    """Ten eligible experts under an open gate with a budget of five (FAB_CULL_FRAC 0.5): use ranks
    them 0..9, no spare can fire, no failure cull (comp_glob None) and no merge. Experts 0 and 2 serve
    the faded area, 3 has an empty book, the rest serve the live one. `born` tags each expert so a
    removal can be read after the renumbering."""
    c = configs(FAB_N0=10, FAB_SLOTS=12, FAB_GRACE=1, FAB_MERGE_DIST=0, FAB_PRESSURE=0.1,
                FAB_CULL_FRAC=0.5, FAB_COMP_PROTECT=0, FAB_FADED_CULL=mode)
    pop = population(c)
    for i in range(10):
        pop.uage[i], pop.use[i], pop.born[i] = 5, float(i + 1), 100 + i
        pop.ef[i] = pop.es[i] = 1.0
        pop.area_use[i] = {L: 1.0}
    pop.comp_glob = None
    pop.area_use[0] = {F: 1.0}
    pop.area_use[2] = {F: 2.0, L: 1.0}
    pop.area_use[3] = {}
    return c, pop


def survivors(pop):
    return sorted(int(pop.born[i]) - 100 for i in range(int(pop.n_live)))


class Removals:
    """Wraps FAB._remove and FAB._merge_into for scripted passes: every expert a pass removes, by its
    `born` tag, whether a merge absorbed it, and the book it held when it went -- read at the
    removal, independent of manage's own tallies."""

    def __enter__(self):
        self.out, self._merged = [], []
        self._r, self._mi = FAB._remove, FAB._merge_into
        rec = self

        def merge_into(pop, a, b, rank):
            rec._merged.append(pop.area_use[b])
            return rec._mi(pop, a, b, rank)

        def remove(pop, slot):
            book = pop.area_use[slot]
            rec.out.append((int(pop.born[slot]) - 100, any(book is o for o in rec._merged),
                            dict(book)))
            return rec._r(pop, slot)

        FAB._remove, FAB._merge_into = remove, merge_into
        return self

    def __exit__(self, *exc):
        FAB._remove, FAB._merge_into = self._r, self._mi
        return False


def pair_pass(make, faded=frozenset({F})):
    """One scripted population, built afresh for each value, through one pass at 'as_is' and at
    'defer'. Per value: ({tag: merged?} of what it removed, the tags whose book read faded when they
    went, the ManageReport, the population)."""
    out = {}
    for mode in ("as_is", "defer"):
        c, pop = make(mode)
        with Removals() as rm:
            r = FAB.manage(c["FAB"], pop, step_windows=U.Windows(500), faded=faded)
        out[mode] = ({t: m for t, m, _b in rm.out},
                     {t for t, _m, b in rm.out if b and top(b) in faded}, r, pop)
    return out


def exactly_less_faded(res):
    """Did 'defer' remove exactly 'as_is''s removals, each the same way, less the faded ones -- and
    defer as events exactly those? -> (ok, what 'as_is' less the faded is)."""
    (ra, fa, rep_a, _pa), (rd, fd, rep_d, _pd) = res["as_is"], res["defer"]
    want = {t: m for t, m in ra.items() if t not in fa}
    ok = (rd == want and not fd
          and rep_d.merge_faded_deferred == rep_a.merged_faded_area
          and rep_d.cull_faded_deferred == rep_a.culled_faded_area
          and rep_d.faded_unknown == rep_a.faded_unknown
          and (rep_d.spared_contrib, rep_d.spared_comp, rep_d.spared_shift,
               rep_d.merge_declined_grace, rep_d.rescued)
          == (rep_a.spared_contrib, rep_a.spared_comp, rep_a.spared_shift,
              rep_a.merge_declined_grace, rep_a.rescued))
    return ok, want


def _gate(pop, name):
    return next((g for g in pop.gates if g.name == name), None)


def _scripted(mode, n, slots, **env):
    """A scripted population of n experts, every one on the live area's book, `born` tagging each."""
    c = configs(FAB_N0=n, FAB_SLOTS=slots, FAB_FADED_CULL=mode, **env)
    pop = population(c)
    for i in range(n):
        pop.uage[i], pop.born[i], pop.use[i] = 2, 100 + i, float(i + 1)
        pop.ef[i] = pop.es[i] = 1.0
        pop.area_use[i] = {L: 1.0}
    pop.comp_glob = 1.0
    return c, pop


def fail_then_util(mode):
    """The failure cull, then the utilization cull (the review's first leak). Four eligible experts
    at FAB_CULL_FRAC 0.5; expert 0 fails, serves the faded area and is the most-used (100); 1, 2, 3
    use 2, 3, 4. 'as_is' fails 0 and, over the three left, culls one: 1."""
    c, pop = _scripted(mode, 4, 4, FAB_GRACE=1, FAB_MERGE_DIST=0, FAB_PRESSURE=0.1,
                       FAB_CULL_FRAC=0.5, FAB_COMP_PROTECT=0)
    pop.ef[0] = pop.es[0] = 5.0
    pop.use[0] = 100.0
    pop.area_use[0] = {F: 1.0}
    return c, pop


def merge_then_gate(mode):
    """A merge, then the pressure gate (the review's second leak). Six experts in twelve slots at
    FAB_PRESSURE 0.5, one close pair (0, 1) whose absorbee 0 is faded: 'as_is' merges it, leaving
    5/12, and the gate is SHUT."""
    c, pop = _scripted(mode, 6, 12, FAB_GRACE=1, FAB_MERGE_DIST=0.1, FAB_PRESSURE=0.5,
                       FAB_CULL_FRAC=0.5, FAB_COMP_PROTECT=0)
    with torch.no_grad():
        pop.cent[:6] = torch.eye(SIG_D)[:6]
        pop.cent[1] = pop.cent[0]
    pop.uage[0] = 5                        # the pair's more-selected one is the one absorbed
    pop.area_use[0] = {F: 3.0}
    return c, pop


def merge_scan(mode):
    """The merge scan (the review's third leak). (0, 1) is the closest pair and (0, 2) the next, both
    within FAB_MERGE_DIST 0.1; (1, 2) is not. uage 5/3/6, expert 0 faded: 'as_is' merges 0 into 1,
    and (0, 2) then names an absorbed expert."""
    c, pop = _scripted(mode, 6, 12, FAB_GRACE=1, FAB_MERGE_DIST=0.1, FAB_CULL_FRAC=0)
    e = torch.eye(SIG_D)
    with torch.no_grad():
        pop.cent[:6] = e[:6]
        pop.cent[1] = math.cos(0.30) * e[0] + math.sin(0.30) * e[6]
        pop.cent[2] = math.cos(0.35) * e[0] - math.sin(0.35) * e[6]
    pop.uage[0], pop.uage[1], pop.uage[2] = 5, 3, 6
    pop.area_use[0] = {F: 3.0}
    return c, pop


def survivor_mass(mode):
    """The survivor of a pair left apart, ranked. (0, 1) is close; 0 (faded, use 50) is absorbed into
    1 (use 1), so 'as_is' ranks 1 at 51 and, at a budget of two over the five left, culls 2 and 3.
    Ranked by its own row, 1 would be the least-used expert of the pass."""
    c, pop = _scripted(mode, 6, 6, FAB_GRACE=1, FAB_MERGE_DIST=0.1, FAB_PRESSURE=0.1,
                       FAB_CULL_FRAC=0.5, FAB_COMP_PROTECT=0)
    with torch.no_grad():
        pop.cent[:6] = torch.eye(SIG_D)[:6]
        pop.cent[1] = pop.cent[0]
    pop.uage[0] = 5
    pop.use[0], pop.use[1] = 50.0, 1.0
    pop.area_use[0] = {F: 3.0}
    return c, pop


def refilled_walk(mode):
    """The failure cull's walk over a slot the merge refilled. FAB_GRACE 2; (0, 1) is close and 0
    (faded) is absorbed; the last expert, 5, is inside grace (uage 0) and failing. 'as_is' removes
    slot 0, moves 5 into it and judges 5 under slot 0's past-grace entry -- the defect Q-FAB-18
    records, owed its own ruling -- and culls it."""
    c, pop = _scripted(mode, 6, 12, FAB_GRACE=2, FAB_MERGE_DIST=0.1, FAB_CULL_FRAC=0)
    with torch.no_grad():
        pop.cent[:6] = torch.eye(SIG_D)[:6]
        pop.cent[1] = pop.cent[0]
    pop.uage[0], pop.uage[5] = 5, 0
    pop.ef[5] = pop.es[5] = 5.0
    pop.area_use[0] = {F: 3.0}
    return c, pop


def sweep_population(mode, k):
    """A seeded random population for the sweep: clustered centroids (so merges chain), failing,
    adapting and load-bearing experts, ties in `use`, faded, live, tied and empty books, rescue on
    one pass in three, comp_glob set -- the class the invariant is stated for (Q-FAB-18's review
    records the one it is not: comp_glob None after a merge). AT FAB_CONTRIB=1 (2026-09-28,
    Q-FAB-19's review): FAB.manage reads a measured contribution there only, so the load-bearing
    experts planted below are spared as they were before that ruling -- at 0 the contrib > 0 spare
    is inert and the sweep would stop reaching it. Nothing here calls FAB.contribution."""
    R = random.Random(1000 + k)
    n = R.randint(3, 20)
    c = configs(FAB_N0=n, FAB_SLOTS=n + R.randint(0, 12), FAB_GRACE=R.choice([1, 2, 3]),
                FAB_MERGE_DIST=R.choice([0, 0.05, 0.2, 0.5, 0.9]),
                FAB_PRESSURE=R.choice([0.05, 0.4, 0.8]),
                FAB_CULL_FRAC=R.choice([0, 0.2, 0.5, 0.8, 1.0]), FAB_COMP_PROTECT=R.choice([0, 1]),
                FAB_RESCUE=R.choice([0.0, 0.0, 0.3]), FAB_FADED_CULL=mode, FAB_CONTRIB=1)
    pop = population(c, seed=1234 + k)
    g = torch.Generator().manual_seed(k)
    base = torch.nn.functional.normalize(torch.randn(4, SIG_D, generator=g), dim=-1)
    with torch.no_grad():
        for i in range(n):
            pop.cent[i] = (base[R.randrange(4)] + R.choice([0.0, 0.05, 0.2, 0.5])
                           * torch.randn(SIG_D, generator=g)) if R.random() < 0.6 \
                else torch.randn(SIG_D, generator=g)
            pop.A[i] = torch.randn(pop.A[i].shape, generator=g) * 0.1
            pop.B[i] = torch.randn(pop.B[i].shape, generator=g) * 0.1
    pop.comp_glob = 1.0
    for i in range(n):
        pop.born[i], pop.uage[i] = 100 + i, R.choice([0, 1, 2, 3, 4, 6, 9])
        pop.use[i] = R.choice([1.0, 2.0, 3.0]) if R.random() < 0.3 else round(R.uniform(0.1, 9), 3)
        pop.ef[i] = pop.es[i] = R.choice([4.0, 5.0]) if R.random() < 0.3 else 1.0
        if pop.ef[i] > 2.0 and R.random() < 0.2:
            pop.ef[i] = pop.es[i] + 1.0            # adapting
        pop.comp[i] = R.choice([0.5, 1.5])
        pop.contrib[i] = 1.0 if R.random() < 0.08 else 0.0
        pop.mutscale[i] = 1.0 if R.random() < 0.85 else 2.0
        r = R.random()
        pop.area_use[i] = ({} if r < 0.15 else
                           {F: round(R.uniform(1, 5), 2), L: round(R.uniform(0, 3), 2)} if r < 0.45
                           else {F: 2.0, L: 2.0} if r < 0.55 else
                           {L: round(R.uniform(1, 5), 2), M: round(R.uniform(0, 2), 2)})
    return c, pop


def f4_count_and_f5_defer():
    # ---- the utilization cull ----------------------------------------------------------------------
    c, pop = util_population("as_is")
    FAB.manage(c["FAB"], pop, step_windows=U.Windows(500))
    none_keys = [k for k in pop.counters if "faded" in k]
    check("F4 faded=None reads no book and leaves every step-7 key ABSENT (the pass itself unchanged: "
          "the five least-used culled)", not none_keys and survivors(pop) == [5, 6, 7, 8, 9],
          f"keys {none_keys}; survivors {survivors(pop)}")
    c, pop = util_population("as_is")
    r = FAB.manage(c["FAB"], pop, step_windows=U.Windows(500), faded=frozenset({F}))
    k = pop.counters
    check("F4 at 'as_is' the same five are culled, two of them faded-area (0, 2) and one with an empty "
          "book (3); the three counts, their per-pass gauges and the pass's ManageReport say so, and "
          "the deferral pair is ABSENT",
          survivors(pop) == [5, 6, 7, 8, 9] and k.get("fab.culled_faded_area") == 2
          and k.get("fab.faded_unknown") == 1 and k.get("fab.merged_faded_area") == 0
          and k.get("fab.faded_areas_last_pass") == 1
          and (k.get("fab.culled_faded_area_last_pass"), k.get("fab.merged_faded_area_last_pass"),
               k.get("fab.faded_unknown_last_pass")) == (2, 0, 1)
          and r.culled_faded_area == 2 and r.faded_unknown == 1 and r.cull_util == 5
          and "fab.cull_faded_deferred" not in k and "fab.merge_faded_deferred" not in k
          and "fab.faded_deferred_experts" not in k,
          f"{ {x: v for x, v in k.items() if 'faded' in x} }; report {r.culled_faded_area}, "
          f"{r.faded_unknown}, cull_util {r.cull_util}")
    FAB.manage(c["FAB"], pop, step_windows=U.Windows(1000))
    k = pop.counters
    check("F4 the per-pass gauges are THIS pass's or nothing: a pass handed no set after one handed "
          "a set drops all four, and the cumulative counts stay",
          not [x for x in k if x.endswith("_last_pass") and "faded" in x]
          and (k.get("fab.culled_faded_area"), k.get("fab.faded_unknown")) == (2, 1),
          f"{ {x: v for x, v in k.items() if 'faded' in x} }")
    c, pop = util_population("as_is")
    FAB.manage(c["FAB"], pop, step_windows=U.Windows(500), faded=frozenset())
    k = pop.counters
    check("F4 an EMPTY faded set (a first phase) counts: PRESENT-and-0 faded, the empty book still "
          "unknown, the gauges 0, 0 and 1 and the set's size 0",
          k.get("fab.culled_faded_area") == 0 and k.get("fab.merged_faded_area") == 0
          and k.get("fab.faded_unknown") == 1 and k.get("fab.faded_areas_last_pass") == 0
          and (k.get("fab.culled_faded_area_last_pass"), k.get("fab.merged_faded_area_last_pass"),
               k.get("fab.faded_unknown_last_pass")) == (0, 0, 1),
          f"{ {x: v for x, v in k.items() if 'faded' in x} }")
    c, pop = util_population("defer")
    r = FAB.manage(c["FAB"], pop, step_windows=U.Windows(500), faded=frozenset({F}))
    k = pop.counters
    check("F5 at 'defer' the utilization cull removes exactly the non-faded members of 'as_is''s five "
          "victims (1, 3, 4): the deferred 0 and 2 hold their budget slots, so 5 -- the next live-area "
          "expert -- is not culled in their place",
          survivors(pop) == [0, 2, 5, 6, 7, 8, 9] and r.cull_util == 3
          and k.get("fab.cull_faded_deferred") == 2 and k.get("fab.merge_faded_deferred") == 0
          and k.get("fab.faded_deferred_experts") == 2 and k.get("fab.culled_faded_area") == 0
          and k.get("fab.faded_unknown") == 1 and r.cull_faded_deferred == 2,
          f"survivors {survivors(pop)}; { {x: v for x, v in k.items() if 'faded' in x} }")
    FAB.manage(c["FAB"], pop, step_windows=U.Windows(1000), faded=frozenset({F}))
    check("F5 deferrals are EVENTS and the gauge is this pass's: a second pass defers the same two "
          "again (cull_faded_deferred 4) over 2 distinct experts",
          pop.counters.get("fab.cull_faded_deferred") == 4
          and pop.counters.get("fab.faded_deferred_experts") == 2
          and 0 in survivors(pop) and 2 in survivors(pop), f"survivors {survivors(pop)}")

    # ---- the failure cull ---------------------------------------------------------------------------
    def fail_population(mode):
        cc = configs(FAB_N0=6, FAB_SLOTS=12, FAB_GRACE=1, FAB_MERGE_DIST=0, FAB_CULL_FRAC=0,
                     FAB_FADED_CULL=mode)
        pp = population(cc)
        for i in range(6):
            pp.uage[i], pp.born[i], pp.use[i] = 5, 100 + i, 1.0
            pp.ef[i] = pp.es[i] = 1.0
            pp.area_use[i] = {L: 1.0}
        pp.comp_glob = 1.0
        for i in (0, 1):                  # failing: both EMAs above comp_glob + FAB_FAIL_TOL, not adapting
            pp.ef[i] = pp.es[i] = 5.0
        pp.area_use[0] = {F: 1.0}
        return cc, pp
    cc, pp = fail_population("as_is")
    ra = FAB.manage(cc["FAB"], pp, step_windows=U.Windows(500), faded={F})
    cd, pd = fail_population("defer")
    rd = FAB.manage(cd["FAB"], pd, step_windows=U.Windows(500), faded={F})
    ce = _gate(pd, "fabric.cull_eligible")
    check("F4/F5 the failure cull: at 'as_is' both failing experts go and one is counted faded; at "
          "'defer' the faded one stays (one deferral) and the live one goes, and fabric.cull_eligible "
          "says so -- '1 culled ..., 1 deferred at FAB_FADED_CULL='defer'' -- where it read '0 "
          "culled' of an expert that failed",
          ra.cull_fail == 2 and ra.culled_faded_area == 1 and survivors(pp) == [2, 3, 4, 5]
          and rd.cull_fail == 1 and rd.cull_faded_deferred == 1 and survivors(pd) == [0, 2, 3, 4, 5]
          and pd.counters.get("fab.faded_deferred_experts") == 1
          and ce is not None and "1 culled, 0 spared as adapting, 0 as load-bearing, 1 deferred at "
                                 "FAB_FADED_CULL='defer'" in ce.reason
          and "beside the 1 expert(s) FAB_FADED_CULL='defer' kept (0 merge(s), 1 failure cull(s) "
              "and 0 utilization cull(s) deferred)" in ce.reason
          and "deferred" not in _gate(pp, "fabric.cull_eligible").reason,
          f"as_is {ra.cull_fail}/{ra.culled_faded_area} {survivors(pp)}; defer {rd.cull_fail}/"
          f"{rd.cull_faded_deferred} {survivors(pd)}; {ce.reason if ce else None}")

    # ---- the merge ----------------------------------------------------------------------------------
    def merge_population(mode, book0):
        cc = configs(FAB_N0=6, FAB_SLOTS=12, FAB_GRACE=1, FAB_MERGE_DIST=0.1, FAB_CULL_FRAC=0,
                     FAB_FADED_CULL=mode)
        pp = population(cc)
        with torch.no_grad():
            pp.cent[:6] = torch.eye(SIG_D)[:6]
            pp.cent[1] = pp.cent[0]           # one close pair, (0, 1); every other pair is orthogonal
        for i in range(6):
            pp.uage[i], pp.born[i], pp.use[i] = 2, 100 + i, 1.0
            pp.area_use[i] = {L: 1.0}
        pp.uage[0] = 5                         # the absorbed expert is the pair's more-selected one
        pp.comp_glob = None
        pp.area_use[0] = book0
        return cc, pp
    results, reasons = {}, {}
    for mode, book0 in (("as_is", {F: 3.0}), ("defer", {F: 3.0}), ("as_is", {}), ("defer", {})):
        cc, pp = merge_population(mode, book0)
        rr = FAB.manage(cc["FAB"], pp, step_windows=U.Windows(500), faded={F})
        results[(mode, bool(book0))] = (rr.merged, rr.merged_faded_area, rr.faded_unknown,
                                        rr.merge_faded_deferred, survivors(pp),
                                        pp.counters.get("fab.faded_deferred_experts"))
        reasons[(mode, bool(book0))] = (_gate(pp, "fab.merged_last_pass").reason,
                                        _gate(pp, "fab.merged").reason)
    check("F4/F5 the merge: at 'as_is' the faded absorbee (0) merges into 1 and is counted faded; at "
          "'defer' it is declined and counted a deferral; an empty book merges and counts unknown at "
          "either value",
          results[("as_is", True)][:5] == (1, 1, 0, 0, [1, 2, 3, 4, 5])
          and results[("defer", True)][:5] == (0, 0, 0, 1, [0, 1, 2, 3, 4, 5])
          and results[("defer", True)][5] == 1
          and results[("as_is", False)][:5] == (1, 0, 1, 0, [1, 2, 3, 4, 5])
          and results[("defer", False)][:5] == (1, 0, 1, 0, [1, 2, 3, 4, 5]),
          f"{results}")
    last, run = reasons[("defer", True)]
    check("F5 a pass whose one close pair was deferred says so in both merge gates -- 'no pair merged "
          "on this pass: 1 close pair(s) ... deferred' and 'none merged: 1 close pair(s) ... deferred "
          "over the ledger' -- and not that no pair sat within FAB_MERGE_DIST; a pass that merged at "
          "'defer' counts its deferrals beside the merge, and 'as_is' reads as it did",
          "no pair merged on this pass: 1 close pair(s) with a past-grace absorbee were deferred at "
          "FAB_FADED_CULL='defer'" in last and "sat within" not in last
          and "none merged: 1 close pair(s) with a past-grace absorbee were deferred over the ledger "
              "at FAB_FADED_CULL='defer'" in run and "sit within" not in run
          and reasons[("defer", False)][0].endswith("; 0 close pair(s) deferred at "
                                                    "FAB_FADED_CULL='defer'")
          and "defer" not in reasons[("as_is", True)][0] + reasons[("as_is", True)][1],
          f"{last!r}; {run!r}; {reasons[('defer', False)][0]!r}")

    # ---- 'defer' IS 'as_is' LESS THE FADED REMOVALS, down every path (Q-FAB-18's review) ----------
    for name, make, want_as_is, want_defer in (
            ("the failure cull, then the utilization cull: 'as_is' fails 0 (faded) and culls 1 over "
             "the three left; 'defer' keeps 0 and, the budget sized without it, culls 1 and not 2",
             fail_then_util, {0: False, 1: False}, {1: False}),
            ("a merge, then the pressure gate: 'as_is' merges 0 (faded) and the gate reads 5/12, SHUT; "
             "'defer' keeps 0 and reads the gate on the same 5, SHUT, so nothing is culled",
             merge_then_gate, {0: True}, {}),
            ("the merge scan: 'as_is' merges 0 (faded) into 1 and then skips (0, 2); 'defer' keeps 0, "
             "consumed for the scan as 'as_is''s absorbee is, and 2 is not merged into it",
             merge_scan, {0: True}, {}),
            ("the survivor of a pair left apart: 'as_is' merges 0 (faded, use 50) into 1 and ranks 1 "
             "at 51, culling 2 and 3; 'defer' ranks 1 by the same 51, culling 2 and 3 and not 1",
             survivor_mass, {0: True, 2: False, 3: False}, {2: False, 3: False}),
            ("the failure cull's walk: 'as_is' merges 0 (faded), refills slot 0 with 5 -- inside grace "
             "and failing -- and culls it under slot 0's entry (Q-FAB-18's recorded defect); 'defer' "
             "walks the same layout and culls the same 5, so both values judge one set",
             refilled_walk, {0: True, 5: False}, {5: False})):
        res = pair_pass(make)
        ok, want = exactly_less_faded(res)
        check(f"F5 'defer' removes exactly 'as_is''s removals less the faded ones -- {name}",
              ok and res["as_is"][0] == want_as_is and res["defer"][0] == want_defer == want,
              f"as_is {res['as_is'][0]} (faded {sorted(res['as_is'][1])}); defer {res['defer'][0]}; "
              f"want {want}")
    res = pair_pass(merge_then_gate)
    cg = _gate(res["defer"][3], "fab.cull_gate")
    check("F5 fab.cull_gate at 'defer' prints the population 'as_is' holds -- 5/12=0.417, SHUT -- and "
          "says the deferred expert stands beside it",
          cg is not None and cg.fired is False and cg.value == "5/12=0.417"
          and "SHUT, over the population FAB_FADED_CULL='as_is' would hold here: the 1 expert(s) this "
              "pass deferred stand beside it, uncounted" in cg.reason,
          f"{cg}")
    # A SEEDED SWEEP through every path together: chained merges, failure culls over refilled slots,
    # budgets, gates, spares, ties and rescue, each population through one pass at both values.
    n_ok, n_cases, paths = 0, 150, {"merge": 0, "cull": 0, "spared_contrib": 0}
    bad = []
    for k in range(n_cases):
        res = pair_pass(lambda mode, k=k: sweep_population(mode, k),
                        faded=frozenset({F}) if k % 5 else frozenset({F, M}))
        ok, want = exactly_less_faded(res)
        rep = res["defer"][2]
        paths["merge"] += rep.merge_faded_deferred
        paths["cull"] += rep.cull_faded_deferred
        paths["spared_contrib"] += res["as_is"][2].spared_contrib
        n_ok += ok
        if not ok and len(bad) < 3:
            bad.append((k, res["as_is"][0], sorted(res["as_is"][1]), res["defer"][0], want))
    check(f"F5 a seeded sweep of {n_cases} random populations (merges that chain, failure culls over "
          "refilled slots, budgets, gates, spares, ties, rescue): at each, 'defer' removes exactly "
          "'as_is''s removals less the faded ones, deferring those as events, with the same spares, "
          "declines and rescues -- and the sweep deferred merges and culls both, and spared "
          "load-bearing experts",
          n_ok == n_cases and paths["merge"] > 0 and paths["cull"] > 0
          and paths["spared_contrib"] > 0,
          f"{n_ok} of {n_cases}; deferrals and spares {paths}; first failures {bad}")


# ==================================================================================================
# F6 / F7 -- a phased run, recounted
# ==================================================================================================

_TWIN_COPIED = ("born", "use", "uage", "dom_of", "ef", "es", "comp", "contrib", "parent", "mutscale",
                "area_use", "growth", "counters", "row_events", "marks")


def twin_of(pop):
    """A copy of a population a management pass can run on without touching the original: the three
    banks cloned, every book, the growth machine, the ledger and the row events deep-copied, and the
    rest -- the modules, the RNG (a pass draws only to rescue, off in B3), the caches a removal
    drops -- shared."""
    twin = object.__new__(type(pop))
    for name in type(pop).__slots__:
        if not hasattr(pop, name):
            continue
        v = getattr(pop, name)
        if name in ("A", "B", "cent"):
            v = v.detach().clone()
        elif name in _TWIN_COPIED:
            v = copy.deepcopy(v)
        setattr(twin, name, v)
    return twin


GAUGES = ("fab.culled_faded_area_last_pass", "fab.merged_faded_area_last_pass",
          "fab.faded_unknown_last_pass")


class Recorder:
    """Wraps FAB.manage, FAB._merge_into and FAB._remove to record, per management pass, the set the
    loop handed it, the window it ran at, the per-pass gauges it left, and every expert it removed
    -- by merge or by cull -- with the book it held when it went and its NAME, its slot when the pass
    began, followed through the pass's own renumbering (FAB._drop, _remove's mirror). Independent of
    manage's own tallies: it counts what was removed. With `shadow=True` a pass handed a set first
    runs at faded=None on a copy of the population that entered it -- the decisions
    FAB_FADED_CULL='as_is' takes there -- and its removals are kept beside the real pass's, with the
    pass's deferral events."""

    def __init__(self, sysm, shadow=False):
        self.sysm, self.shadow = sysm, shadow
        self.passes, self.removals, self.logs, self.gauges, self.pairs = [], [], [], [], []
        self._set, self._merged, self._names, self._log = None, [], {}, {}

    def __enter__(self):
        self._m, self._mi, self._r = FAB.manage, FAB._merge_into, FAB._remove
        rec = self

        def manage(fab, pop, **kw):
            # THE WINDOW'S FIRST BYTE: its EPOCH-LOCAL index is the clock's in_epoch - 1 (the clock
            # has advanced for this window when stage A runs), times LM.ctx into this epoch's
            # segmentation -- the byte the loop's own join reads.
            f = kw.get("faded")
            fs = None if f is None else frozenset(f)
            step = int(kw["step_windows"])
            i = int(rec.sysm.clock.counters()["in_epoch"]) - 1
            rec.passes.append((step, fs, int(rec.sysm.segmentation.byte_pos[
                i * int(rec.sysm.configs["LM"].ctx)])))
            as_is = None
            if rec.shadow and fs is not None:
                twin = twin_of(pop)
                rec._set, rec._merged, rec._log = fs, [], {}
                rec._names = {id(twin): list(range(int(twin.n_live)))}
                rec._m(fab, twin, step_windows=kw["step_windows"],
                       flush_loss=kw.get("flush_loss"), faded=None)
                as_is = rec._log.get(id(twin), [])
            before = {k: pop.counters.get(k, 0)
                      for k in ("fab.cull_faded_deferred", "fab.merge_faded_deferred")}
            rec._set, rec._merged, rec._log = fs, [], {}
            rec._names = {id(pop): list(range(int(pop.n_live)))}
            try:
                return rec._m(fab, pop, **kw)
            finally:
                log = rec._log.get(id(pop), [])
                if fs is not None:
                    rec.removals.extend((m, b, fs) for _w, m, b in log)
                rec.logs.append(log)
                rec.gauges.append(tuple(pop.counters.get(k) for k in GAUGES))
                if as_is is not None:
                    rec.pairs.append((step, fs, as_is, log,
                                      {k: pop.counters.get(k, 0) - v for k, v in before.items()}))
                rec._set, rec._merged, rec._names, rec._log = None, [], {}, {}

        def merge_into(pop, a, b, rank):
            rec._merged.append(pop.area_use[b])          # the object, held so its id is not reused
            return rec._mi(pop, a, b, rank)

        def remove(pop, slot):
            names = rec._names.get(id(pop))
            if rec._set is not None and names is not None:
                book = pop.area_use[slot]
                who = names[slot] if slot < len(names) else (names[-1] if names else None)
                rec._log.setdefault(id(pop), []).append(
                    (who, any(book is o for o in rec._merged), dict(book)))
            moved = rec._r(pop, slot)
            if names is not None:
                FAB._drop(names, slot)
            return moved

        FAB.manage, FAB._merge_into, FAB._remove = manage, merge_into, remove
        return self

    def __exit__(self, *exc):
        FAB.manage, FAB._merge_into, FAB._remove = self._m, self._mi, self._r
        return False


def fab_ledger(r):
    return {k: v for k, v in r.report["FAB.counters"].items() if not k.startswith("gate:")}


def recount(rec):
    merged = sum(1 for m, b, f in rec.removals if m and b and top(b) in f)
    culled = sum(1 for m, b, f in rec.removals if not m and b and top(b) in f)
    unknown = sum(1 for _m, b, _f in rec.removals if not b)
    return merged, culled, unknown


def f6_f7_phased_runs():
    runs = {}
    for mode in ("as_is", "defer"):
        s = build(**B3, FAB_FADED_CULL=mode)
        with Recorder(s, shadow=(mode == "defer")) as rec:
            r = loop.run(s, progress=False)
        runs[mode] = (s, r, rec)
    s, r, rec = runs["as_is"]
    led = fab_ledger(r)
    names = list(s.areas.names)
    ids = {n: derive.area_id(n) for n in names}
    # The set each pass was handed is Plan.faded at the phase of its window's first byte.
    want_sets, phases = [], []
    for _step, _got, byte in rec.passes:
        k = _phase_of(s.stream.phase_bounds, byte)
        phases.append(k)
        want_sets.append(frozenset(ids[names[i]] for i in s.plan.faded[k]))
    check("F6 every management pass was handed Plan.faded at its window's phase, as area ids -- "
          f"{len(rec.passes)} passes over phases {phases}",
          len(rec.passes) >= 6 and [g for _s, g, _b in rec.passes] == want_sets
          and any(want_sets), f"{[(st, sorted(g)) for st, g, _b in rec.passes]}")
    m, cu, un = recount(rec)
    check("F6 fab.merged_faded_area, fab.culled_faded_area and fab.faded_unknown equal an independent "
          "recount of the experts the passes removed",
          (led.get("fab.merged_faded_area"), led.get("fab.culled_faded_area"),
           led.get("fab.faded_unknown")) == (m, cu, un) and cu > 0
          and sum(1 for mm, _b, _f in rec.removals if mm) == led.get("fab.merged")
          and sum(1 for mm, _b, _f in rec.removals if not mm)
          == led.get("fab.cull_fail") + led.get("fab.cull_util"),
          f"ledger ({led.get('fab.merged_faded_area')}, {led.get('fab.culled_faded_area')}, "
          f"{led.get('fab.faded_unknown')}) recount ({m}, {cu}, {un}); {len(rec.removals)} removals, "
          f"merged {led.get('fab.merged')}, culled {led.get('fab.cull_fail')} + "
          f"{led.get('fab.cull_util')}")
    # CONTRACT-Q-FAB-5's PER-PASS COUNT (Q-FAB-18's review): each pass's gauges are its own recount.
    per_pass = []
    for (_st, fs, _b), log, got in zip(rec.passes, rec.logs, rec.gauges):
        want = (sum(1 for _w, mm, b in log if not mm and b and top(b) in fs),
                sum(1 for _w, mm, b in log if mm and b and top(b) in fs),
                sum(1 for _w, _m, b in log if not b))
        per_pass.append((got, want))
    check("F6 each pass's fab.culled_faded_area_last_pass, fab.merged_faded_area_last_pass and "
          "fab.faded_unknown_last_pass are that pass's own recount, and the last pass's are what R "
          "prints",
          per_pass and all(g == w for g, w in per_pass) and any(sum(w) for _g, w in per_pass)
          and tuple(led.get(k) for k in GAUGES) == per_pass[-1][0],
          f"{per_pass}")
    pop = s.fabric
    drift = max(abs(sum(pop.area_use[i].values()) - float(pop.use[i])) / max(1.0, float(pop.use[i]))
                for i in range(int(pop.n_live)))
    check("F6 each live expert's area book sums to its `use` (every window carried a known area)",
          drift < 1e-9 and led.get("fab.area_windows") == r.windows, f"max relative drift {drift:.2e}")
    row = r.report["MEM.census(reconcile=True)"]
    occ = {k: v for k, v in row.items() if k.startswith("store.occupancy")}
    active = int(s.store.active.sum())
    check("F6 MEM's occupancy by area is printed by name for every area and sums to the active entries",
          set(occ) == {f"store.occupancy.{n}" for n in names} | {"store.occupancy_unknown"}
          and sum(occ.values()) == active and occ["store.occupancy_unknown"] == 0
          and all(occ[f"store.occupancy.{n}"] > 0 for n in names), f"{occ}; active {active}")
    by_name = {v: k for k, v in ids.items()}
    act = s.store.active.nonzero(as_tuple=True)[0].tolist()
    bad = [i for i in act
           if by_name.get(int(s.store.area[i])) != s.stream.labels[int(s.store.pos[i])]]
    check("F6 every active entry's area is the label of the byte its `pos` records",
          not bad and len(act) == active, f"{len(bad)} of {len(act)} disagree")
    check("F6 data.phase_faded is printed at R in DATA(plan.counters)",
          r.report["DATA(plan.counters)"].get("data.phase_faded") == [[], ["eng"], ["eng"],
                                                                       ["eng", "py"]])
    s2, r2, rec2 = runs["defer"]
    led2 = fab_ledger(r2)
    # EACH 'defer' PASS AGAINST 'as_is' ON THE POPULATION THAT ENTERED IT (Q-FAB-18's review): the
    # real pass's removals are the shadow's less its faded ones, each the same way, and the pass's
    # deferral events are those faded removals. No live-area expert is merged or culled in a deferred
    # one's place, on any path.
    paired, deferring, broke = 0, 0, []
    for step, fs, as_is, real, delta in rec2.pairs:
        a_rm = {w: mm for w, mm, _b in as_is}
        a_faded = {w for w, _mm, b in as_is if b and top(b) in fs}
        want = {w: mm for w, mm in a_rm.items() if w not in a_faded}
        got = {w: mm for w, mm, _b in real}
        ok = (got == want
              and delta["fab.merge_faded_deferred"] == sum(1 for w in a_faded if a_rm[w])
              and delta["fab.cull_faded_deferred"] == sum(1 for w in a_faded if not a_rm[w]))
        paired += 1
        deferring += bool(a_faded)
        if not ok:
            broke.append((step, sorted(a_rm.items()), sorted(a_faded), sorted(got.items()), delta))
    check("F7 at 'defer' every pass removes exactly what 'as_is' removes from the population that "
          "entered it, less the faded removals, each the same way -- no live-area expert is merged or "
          "culled in a deferred one's place -- and defers exactly those as events",
          paired == len(rec2.passes) and paired >= 6 and deferring > 0 and not broke,
          f"{paired} passes paired, {deferring} with a deferral; {broke[:2]}")
    faded_removed = [(mm, b) for mm, b, f in rec2.removals if b and top(b) in f]
    check("F7 at 'defer', after the fade no removed expert's most-served area is faded, both deferral "
          "counts are > 0, and nothing faded is counted removed",
          not faded_removed and led2.get("fab.cull_faded_deferred", 0) > 0
          and led2.get("fab.merge_faded_deferred", 0) > 0 and led2.get("fab.culled_faded_area") == 0
          and led2.get("fab.merged_faded_area") == 0
          and any(f for _s, f, _b in rec2.passes),
          f"{len(faded_removed)} faded removals; deferred {led2.get('fab.cull_faded_deferred')} culls, "
          f"{led2.get('fab.merge_faded_deferred')} merges; gauge "
          f"{led2.get('fab.faded_deferred_experts')}")
    return runs


# ==================================================================================================
# F8 -- a pure-add child
# ==================================================================================================

def f8_pure_add_child():
    small = {"DATA_STREAM_BYTES": "20000", "FAB_MANAGE_EVERY": "25", "FAB_GRACE": "2",
             "DATA_AREAS": "eng,py", "DATA_N_PROCESSES": "2"}
    par = build(CKPT_DIR=f"{TMP}/f8", DATA_PHASE_SCHED="eng|eng|eng|eng", **small)
    loop.run(par, progress=False)
    kid = build(CKPT_RESUME=f"{TMP}/f8", CKPT_DIR=f"{TMP}/f8c", DATA_PHASE_SCHED="py|py|py|py",
                RUN_EPOCHS=2, DATA_RESAMPLE=1, **small)
    with Recorder(kid) as rec:
        rk = loop.run(kid, progress=False)
    eng = derive.area_id("eng")
    led = fab_ledger(rk)
    check("F8 the pure-add child's Plan.parent_faded is eng, printed as data.parent_faded, and its own "
          "schedule fades nothing",
          kid.plan.parent_faded == (0,) and kid.plan.faded == ((), (), (), ())
          and rk.report["DATA(plan.counters)"].get("data.parent_faded") == ["eng"],
          f"{kid.plan.parent_faded} {kid.plan.faded}")
    check("F8 every management pass of the child is handed {eng}, from its first -- and removals of "
          "the parent's eng-serving experts count as faded-area removals",
          len(rec.passes) >= 3 and all(f == frozenset({eng}) for _s, f, _b in rec.passes)
          and led.get("fab.culled_faded_area", 0) + led.get("fab.merged_faded_area", 0) > 0,
          f"{len(rec.passes)} passes; sets {[sorted(f) for _s, f, _b in rec.passes][:3]}; culled "
          f"{led.get('fab.culled_faded_area')}, merged {led.get('fab.merged_faded_area')}")


# ==================================================================================================
# F9 -- continuation
# ==================================================================================================

def strip(path):
    blob = torch.load(f"{path}/ckpt.pt", map_location="cpu", weights_only=False)
    had = ("area_use" in blob["payload"]["FAB"]["books"],
           all("area" in row for row in blob["payload"]["MEM"]["rows"]))
    blob["payload"]["FAB"]["books"].pop("area_use", None)
    for row in blob["payload"]["MEM"]["rows"]:
        row.pop("area", None)
    torch.save(blob, f"{path}/ckpt.pt")
    return had


def f9_continuation(runs):
    for mode in ("as_is", "defer"):
        s_u, r_u, _rec = runs[mode]
        par = build(CKPT_DIR=f"{TMP}/f9{mode}", FAB_FADED_CULL=mode, **B3)
        rp = loop.run(par, max_windows=170, progress=False)
        kid = build(CKPT_RESUME=f"{TMP}/f9{mode}", CKPT_DIR=f"{TMP}/f9{mode}c", FAB_FADED_CULL=mode,
                    **B3)
        rk = loop.run(kid, progress=False)
        exact = (rp.loss_curve == r_u.loss_curve[:170] and rk.loss_curve == r_u.loss_curve[170:])
        books = ([kid.fabric.area_use[i] for i in range(int(kid.fabric.n_live))]
                 == [s_u.fabric.area_use[i] for i in range(int(s_u.fabric.n_live))])
        keys = [k for k in fab_ledger(r_u) if "faded" in k]
        counts = all(fab_ledger(rk).get(k) == fab_ledger(r_u).get(k) for k in keys)
        check(f"F9 at '{mode}' a continuing resume at window 170 continues exactly, and ends with the "
              f"uninterrupted run's area books and faded-area counts"
              + (" and deferrals" if mode == "defer" else ""),
              exact and counts and books, f"losses {exact}; books {books}; counts over {keys}: {counts}")
    # A checkpoint written before the FAB area book and the MEM area column: stripped, it resumes
    # exactly and its restored entries read -1.
    s_u, r_u, _rec = runs["as_is"]
    par = build(CKPT_DIR=f"{TMP}/f9old", **B3)
    loop.run(par, max_windows=170, progress=False)
    had = strip(f"{TMP}/f9old")
    kid = build(CKPT_RESUME=f"{TMP}/f9old", CKPT_DIR=f"{TMP}/f9oldc", **B3)
    restored_unknown = int((kid.store.area[kid.store.active] == -1).sum())
    restored = int(kid.store.active.sum())
    books_empty = all(not kid.fabric.area_use[i] for i in range(int(kid.fabric.n_live)))
    rk = loop.run(kid, progress=False)
    occ_u = rk.report["MEM.census(reconcile=True)"].get("store.occupancy_unknown")
    unk_kid, unk_u = fab_ledger(rk).get("fab.faded_unknown"), fab_ledger(r_u).get("fab.faded_unknown")
    check("F9 a checkpoint without the area book and the area column (stripped as the tree before them "
          "wrote it) resumes exactly: every restored entry reads area -1 and every restored expert an "
          "empty book, the child's report counts the surviving entries as store.occupancy_unknown, "
          "and removals of experts whose books were not refilled count as fab.faded_unknown",
          had == (True, True) and rk.loss_curve == r_u.loss_curve[170:]
          and restored_unknown == restored > 0 and books_empty and occ_u is not None and occ_u > 0
          and unk_kid is not None and unk_kid > unk_u,
          f"had {had}; {restored_unknown} of {restored} restored entries at -1; unknown at R {occ_u}; "
          f"fab.faded_unknown {unk_kid} against the uninterrupted run's {unk_u}")
    f9_declared_undrawn()


def f9_declared_undrawn():
    """A run that DECLARES an area it never schedules (Q-FAB-18's review): DATA_AREAS eng,py under
    'eng|eng|eng|eng', so py is in every record's area list and in no stream. Its continuing child
    must hand every pass the uninterrupted run's set; a record written before the drawn list assumes
    every declared area drawn, and says so."""
    small = {"DATA_STREAM_BYTES": "20000", "FAB_MANAGE_EVERY": "25", "FAB_GRACE": "2",
             "DATA_AREAS": "eng,py", "DATA_N_PROCESSES": "2", "DATA_PHASE_SCHED": "eng|eng|eng|eng"}
    uni = build(**small)
    with Recorder(uni) as rec_u:
        r_u = loop.run(uni, progress=False)
    par = build(CKPT_DIR=f"{TMP}/f9d", **small)
    rp = loop.run(par, max_windows=60, progress=False)
    blob = torch.load(f"{TMP}/f9d/ckpt.pt", map_location="cpu", weights_only=False)
    rec_drawn = blob["payload"]["DATA"].get("drawn")
    kid = build(CKPT_RESUME=f"{TMP}/f9d", CKPT_DIR=f"{TMP}/f9dc", **small)
    with Recorder(kid) as rec_k:
        rk = loop.run(kid, progress=False)
    sets_u = {st: f for st, f, _b in rec_u.passes}
    sets_k = {st: f for st, f, _b in rec_k.passes}
    pk, ak = rk.report["DATA(plan.counters)"], rk.report["DATA(areas.counters)"]
    check("F9 a run over eng,py that schedules eng alone records drawn ['eng'], and its continuing "
          "child -- whose record declares py -- has Plan.parent_faded (), prints data.parent_faded [] "
          "and data.drawn_assumed [], and hands every pass the uninterrupted run's set at the same "
          "window, exactly",
          rec_drawn == ["eng"] and list(kid.areas.parent_names) == ["eng", "py"]
          and kid.plan.parent_faded == () and pk.get("data.parent_faded") == []
          and ak.get("data.drawn_assumed") == [] and "data.drawn_assumed" not in
          r_u.report["DATA(areas.counters)"]
          and len(sets_k) >= 1 and all(sets_k[st] == sets_u.get(st) for st in sets_k)
          and fab_ledger(rk).get("fab.faded_areas_last_pass")
          == fab_ledger(r_u).get("fab.faded_areas_last_pass") == 0
          and rp.loss_curve == r_u.loss_curve[:60] and rk.loss_curve == r_u.loss_curve[60:],
          f"drawn {rec_drawn}; parent_names {list(kid.areas.parent_names)}; parent_faded "
          f"{kid.plan.parent_faded} {pk.get('data.parent_faded')}; assumed "
          f"{ak.get('data.drawn_assumed')}; sets child {sorted((k, sorted(v)) for k, v in sets_k.items())} "
          f"uninterrupted {sorted((k, sorted(v)) for k, v in sets_u.items())}")
    # A RECORD WRITTEN BEFORE THE LIST: every declared area is ASSUMED drawn, and said.
    blob["payload"]["DATA"].pop("drawn", None)
    torch.save(blob, f"{TMP}/f9d/ckpt.pt")
    old = build(CKPT_RESUME=f"{TMP}/f9d", CKPT_DIR=f"{TMP}/f9dold", **small)
    with Recorder(old) as rec_o:
        ro = loop.run(old, progress=False)
    py = derive.area_id("py")
    po, ao = ro.report["DATA(plan.counters)"], ro.report["DATA(areas.counters)"]
    check("F9 a record without the drawn list (as a tree before it wrote one) assumes every area it "
          "declares drawn and names them in data.drawn_assumed ['eng', 'py']: Plan.parent_faded is "
          "then py, printed, and handed to every pass -- the over-count the list exists to remove -- "
          "and the resume still continues exactly",
          ao.get("data.drawn_assumed") == ["eng", "py"] and old.plan.parent_faded == (1,)
          and po.get("data.parent_faded") == ["py"]
          and rec_o.passes and all(f == frozenset({py}) for _s, f, _b in rec_o.passes)
          and ro.loss_curve == r_u.loss_curve[60:],
          f"assumed {ao.get('data.drawn_assumed')}; parent_faded {old.plan.parent_faded} "
          f"{po.get('data.parent_faded')}; sets {[sorted(f) for _s, f, _b in rec_o.passes]}")


def main():
    try:
        f1_faded_sets()
        f2_area_id()
        f3_book_arithmetic()
        f4_count_and_f5_defer()
        runs = f6_f7_phased_runs()
        f8_pure_add_child()
        f9_continuation(runs)
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    print(f"=== {len(FAILS)} failure(s)" + (": " + "; ".join(FAILS) if FAILS else ""))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
