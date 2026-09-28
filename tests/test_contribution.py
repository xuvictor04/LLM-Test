"""FAB.contribution: THE MARGINAL-CONTRIBUTION COUNTERFACTUAL, ITS PRODUCERS AND THE CULL IT GATES
(register §8 3.5, 02-R11, C37 and NEW-10; docs/04_CONTRACT.md Q-FAB-19), driven through FAB's entry
points on scripted populations and through the real composition root and loop, with real checkpoints
written under a temporary directory.

    python3 tests/test_contribution.py        # exit 0 = every check passed

WHY IT EXISTS. FAB.contribution is BUILT OFF (FAB_CONTRIB=0) because at 1 the contrib > 0 spares in
both culls start to fire, which changes what a run culls; so the first promise is that the shipped
arm is today's run, and the rest pin what a measurement is. The old tree's counterfactual failed in
two recorded ways, and both are refused here by construction: its baseline came from a different
function than its counterfactuals (ISSUES P1-H11, an offset that set contrib's sign), and its walk
never changed (C3, every contribution 0). Each check below pins one promise.

  C-1  FAB_CONTRIB=0 (SHIPPED) IS INERT on a run that reads the retention probe and reaches manage
       passes: FAB.contribution is never called, Population.contrib stays 0.0 and contrib_n 0 on every
       slot, the cursor stays at 0, no fab.contrib_* or eval.contrib.* key exists, Gate fab.contrib is
       UNREACHABLE naming FAB_CONTRIB=0, and the gated-call line reads UNREACHABLE. A direct call at 0
       returns its reason and writes nothing. (The fixtures -- B1, B3, B3r, B5, B6, B6r reproducing
       bit for bit at the defaults -- are tests/test_baseline.py's, run before every commit; they are
       not repeated here.)
  C-2  THE PLAN'S RUN: FAB_CONTRIB=1, EVAL_RETENTION_EVERY=20, DATA_SYNTH_HOLDOUT=1, FAB_GRACE=2,
       FAB_MANAGE_EVERY=25, 200 windows. fab.contrib_distinct_values > 1; fab.contrib_measured equals
       the candidates the passes wrote, summed (and fab.holdout_applied the candidates walked);
       fab.contrib_passes the calls that walked, eval.contrib.calls the calls, one per manage pass
       with an arrived control window; every call took its candidates off the rotating cursor; the
       coverage gauge is the last pass's candidates over its past-grace count; the gated-call line
       and Gate fab.contrib read fired.
  C-3  AN EMPTY hold_out REPRODUCES THE BASELINE BITWISE AT THE SAME STEP PRICING: on a trained
       System, FAB.forward handed the memory-off closure's own inputs (h, signature, novelty zeros,
       DOM.nearest's domain, live_domains, clock.step + 1) returns the closure's logits bit for bit;
       on the society arm the reweighted sum with nothing removed is the prediction bit for bit, and
       a society run measures through it. A walk handed other inputs is refused by name. And the
       society arm's leave-one-out has a known answer on a blend written by hand (Q-FAB-19's
       review): the held-out voter's weight dropped and the rest renormalised,
       (1 - held) * vote' + held * base, and a row whose only voter is removed the base logits.
  C-4  A DEGENERATE PASS WRITES NOTHING: candidates whose removal moves no logit (unrouted experts, and
       any expert of a one-expert population, which hold_out cannot remove) leave contrib and
       contrib_n as they were, count fab.contrib_degenerate, and the Gate says DEGENERATE.
  C-5  baseline_loss RECOMPUTED EQUALS THE RECORDED VALUE, VIA THE MEMORY-OFF CLOSURE: in every call the
       loop makes, LM.lm_loss over baseline_logits_fn()'s logits is baseline_loss exactly; a
       baseline_loss one ulp away (another function's loss) is refused naming P1-H11.
  C-6  AN UNROUTED EXPERT READS 0; A PLANTED LOAD-BEARING EXPERT READS POSITIVE (and a planted harmful
       one negative), on a scripted population whose routing is set by its centroids; the first
       measurement sets contrib, a later one -- taken after the planted expert's B is cut to a
       twentieth, so it differs from the first -- folds in at FAB_COMP_EMA, contrib_n counts both; a
       non-finite loss leaves the candidate unmeasured and counted.
  C-7  FAB_FADED_CULL='contrib' REMOVES A FADED-AREA EXPERT ONLY AT A MEASURED CONTRIBUTION <= 0 AND
       KEEPS AN UNMEASURED ONE, holding its budget slot: on scripted passes against 'as_is' and
       'defer' (the cull and the merge), and in a phased run (B3's shape) where every faded-area
       removal was of an expert measured at or below 0 when it went, the refusals are > 0, the
       allowed counts equal the faded removals, and the deferral pair stays ABSENT. Startup refuses
       'contrib' without FAB_CONTRIB=1, FAB_CONTRIB=1 without the probe or with nothing pinned, and
       FAB_CONTRIB_MAX=0.
  C-8  THE CONTINUATION IS EXACT AT FAB_CONTRIB=1: C-2's run saved at window 110 -- between manage
       passes -- and continued by a second compose ends with C-2's losses, contrib books, cursor,
       fab.contrib_* counts and eval.contrib.* book. A checkpoint written before contrib_n and the
       cursor restores every expert unmeasured and the cursor at 0. AND A LINEAGE RESUMED AT
       FAB_CONTRIB=0 READS NO MEASUREMENT (Q-FAB-19's review): books measured at 1 and restored at 0
       are carried and spare nothing in either cull -- through FAB's entry points, and end to end,
       where C-2's parent resumed at 0 with its restored measurements planted load-bearing trains
       and ends as a twin whose books were cleared -- and the report names what the lineage carried.
  C-9  THE MEASUREMENT MOVES NOTHING IT DOES NOT OWN: with no consumer of contrib (FAB_CULL_FRAC=0,
       FAB_MERGE_DIST=0, FAB_FAIL_TOL=1000) at LM_DROPOUT=0.1, FAB_CONTRIB=1 against 0 trains the same
       losses float for float, ends in the same state but the contrib books, the cursor and LOOP.eval,
       and every integer counter is equal but a named set that moves by exactly the eval.contrib
       book's and FAB's own counts (Q-EVAL-12's exact accounting, extended). A pass that moved a
       global stream would have raised.

WHAT THIS FILE CANNOT SEE: whether a measured contribution means anything, and whether sparing or
culling on it protects what a held-out reading can measure. CPU runs establish operation only; those
are GPU questions (02-R11/C37's retention across culls, E2's 'contrib' arm).
"""
import math
import os
import shutil
import sys
import tempfile

_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(_ROOT, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import torch                                                       # noqa: E402
import torch.nn.functional as TF                                   # noqa: E402
torch.set_num_threads(1)

from spine import lever as _lever                                  # noqa: E402
from spine import rng                                              # noqa: E402
from spine import loop                                             # noqa: E402
from spine import assemble                                         # noqa: E402
from spine import units as U                                       # noqa: E402
from spine.compose import (compose, RefusedRun, _contrib_material, _contrib_baseline,  # noqa: E402
                           _logits_fn, _eval_mode)
from fabric import api as FAB                                      # noqa: E402
from lm import api as lm_api                                       # noqa: E402
import _state_digest as sd                                         # noqa: E402

FAILS = []
DATA_DIR = os.path.join(os.path.abspath(_ROOT), "data")
TMP = tempfile.mkdtemp(prefix="contrib_")
# tests/test_continuation.py's small base (a tenth-size fabric, a few seconds per compose).
BASE = {"DATA_STREAM_BYTES": "60000", "SIG_WARMUP": "20", "FAB_N0": "256", "FAB_SLOTS": "512",
        "DATA_DIR": DATA_DIR}
# C-2's configuration, the plan's: the probe armed on the synthetic source's held-out block, a manage
# pass every 25 windows past a grace of two selections. Generation off: CPU wall only.
C2 = {"FAB_CONTRIB": "1", "EVAL_RETENTION_EVERY": "20", "DATA_SYNTH_HOLDOUT": "1", "FAB_GRACE": "2",
      "FAB_MANAGE_EVERY": "25", "EVAL_GENERATE": "0"}
C2_WINDOWS = 200
# tests/test_baseline.py's B3 on the same base: six manage passes over four phases, the mint and the
# act. With the probe armed (every 50) so FAB_CONTRIB=1 is admitted.
B3 = {"FAB_MANAGE_EVERY": "50", "FAB_GRACE": "2", "TOK_GROW_EVERY": "30", "TOK_RETOK_EVERY": "150",
      "DATA_SYNTH_HOLDOUT": "1", "EVAL_RETENTION_EVERY": "50", "EVAL_GENERATE": "0"}
# The integer counter lines of a report, as tests/test_baseline.py::COUNTER reads them from run.py.
_INT_KEY = __import__("re").compile(r"^[a-z_][a-z0-9_]*(?:\.[a-z0-9_:]+)+$")


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" -- {detail}" if detail else ""), flush=True)
    if not ok:
        FAILS.append(name)


def build(**env):
    """A System under BASE + `env`, as a fresh run.py process builds one: the issued streams forgotten
    and LM's process-lifetime tally emptied, so a report counts this System's calls."""
    _lever._reopen_assembly()
    rng.reset_issued()
    lm_api._COUNTS.clear()
    e = dict(BASE)
    e.update({k: str(v) for k, v in env.items()})
    return compose(environ=e)


def configs(**env):
    """A real, frozen Config set from assemble.build over a dict environment (never os.environ)."""
    _lever._reopen_assembly()
    rng.reset_issued()
    e = {"RUN_SEED": "7", "RUN_DEVICE": "cpu"}
    e.update({k: str(v) for k, v in env.items()})
    cfgs, _wires, warnings = assemble.build(e)
    if warnings:
        raise AssertionError(f"assemble.build warned on {e}: {warnings}")
    return cfgs


def fab_ledger(r):
    return {k: v for k, v in r.report["FAB.counters"].items() if not k.startswith("gate:")}


def ebook(r):
    b = r.report.get("EVAL(holdout)")
    return b if isinstance(b, dict) else {}


def flat_ints(report):
    """{(row, key): int} -- every integer counter line the report prints."""
    return {(row, k): v for row, d in report.items() if isinstance(d, dict)
            for k, v in d.items() if isinstance(k, str) and _INT_KEY.match(k) and type(v) is int}


def gated_line(r, name):
    return next((g for g in r.gated if g.startswith(name + ":")), "")


class Spy:
    """Wraps FAB.contribution, which the loop reaches as fab_api.contribution, and keeps every call's
    arguments and ContribReport in order. With `recheck`, each call first scores
    baseline_logits_fn()'s logits through LM.lm_loss and keeps (that loss, baseline_loss) -- C-5's
    reading, taken where the loop made the call (it adds a closure pass to that call's book)."""

    def __init__(self, sysm=None, recheck=False):
        self.sysm, self.recheck, self.calls, self.rechecked = sysm, recheck, [], []

    def __enter__(self):
        self._real = FAB.contribution
        spy = self

        def contribution(fab, pop, **kw):
            if spy.recheck:
                lg = kw["baseline_logits_fn"]()
                again = float(lm_api.lm_loss(spy.sysm.configs["LM"], lg, kw["targets"])[1])
                spy.rechecked.append((again, float(kw["baseline_loss"])))
            rep = spy._real(fab, pop, **kw)
            spy.calls.append((dict(kw), rep))
            return rep
        FAB.contribution = contribution
        return self

    def __exit__(self, *exc):
        FAB.contribution = self._real
        return False


# ==================================================================================================
# THE SCRIPTED POPULATION (C-4, C-6, and the units)
# ==================================================================================================

D, S, V, BATCH, LEN = 16, 12, 8, 2, 5
# One hop, one expert computed and one decoded, no halting, routing on the region term alone: the
# expert a window routes to is the one whose centroid its signature points at, and nothing else.
UNIT = {"FAB_SLOTS": "8", "FAB_CHAIN_K": "1", "FAB_ENS_K": "1", "FAB_HOPS": "1", "FAB_HALT": "0",
        "FAB_ROUTE_LEARN": "0", "FAB_EC_W": "0", "FAB_GRACE": "0", "FAB_CONTRIB": "1"}


def scripted(n=4, planted=0, t=3, harmful=False, **env):
    """n experts, every B zero (an identity expert) except the planted one's, which adds a large
    vector along the head's row for class t (for a harmful plant, class t + 1) to a constant h; every
    window's signature points at the planted expert's centroid and every other centroid is
    orthogonal to it. Targets are all t. So the planted expert is the one routed, the prediction with
    it scores t almost surely, and without it the next expert -- an identity -- predicts nothing."""
    e = dict(UNIT)
    e.update({k: str(v) for k, v in env.items()})
    e["FAB_N0"] = str(n)
    c = configs(**e)
    pop = FAB.build(c["FAB"], d_model=D, signature_dim=S, device=torch.device("cpu"),
                    generator=rng.rng_for("fabric", 1234, again=True))
    g = torch.Generator().manual_seed(11)
    v = torch.randn(D, generator=g)
    h = v.expand(BATCH, LEN, D).clone()
    s0 = torch.zeros(S)
    s0[0] = 1.0
    sig = s0.expand(BATCH, S).clone()
    W = torch.zeros(V, D)
    for k in range(V):
        W[k, k] = 3.0
    with torch.no_grad():
        for i in range(n):
            pop.cent[i] = torch.zeros(S)
            pop.cent[i][1 + i % (S - 1)] = 1.0
            pop.B[i] = 0.0
        pop.cent[planted] = s0
        a = v @ pop.A[planted]
        u = 20.0 * W[(t + 1) % V if harmful else t]
        pop.B[planted] = torch.outer(a, u) / (a @ a)
    head = torch.nn.Linear(D, V, bias=False)
    with torch.no_grad():
        head.weight.copy_(W)
    y = torch.full((BATCH, LEN), t, dtype=torch.long)
    return c, pop, h, sig, head, y


def walk(c, pop, h, sig, head, hold_out=None, step=10):
    with torch.no_grad():
        o = FAB.forward(c["FAB"], pop, h=h, signature=sig, novelty=torch.zeros(BATCH), head=head,
                        targets=None, step_windows=U.Windows(step), domain_id=0, live_domains=1,
                        training=False, hold_out=hold_out)
    return o.logits if o.logits is not None else head(o.hidden)


def mean_ce(lg, y):
    """LM.lm_loss's reduction, written here: cross-entropy per token, the mean per window, the mean."""
    return TF.cross_entropy(lg.reshape(-1, lg.shape[-1]), y.reshape(-1),
                            reduction="none").view(y.shape).mean(-1).mean()


def measure(c, pop, h, sig, head, y, candidates=None, baseline_loss=None, step=10):
    bl = float(mean_ce(walk(c, pop, h, sig, head, step=step), y)) if baseline_loss is None \
        else baseline_loss
    return FAB.contribution(c["FAB"], pop, h=h, signature=sig, novelty=torch.zeros(BATCH), head=head,
                            targets=y, baseline_loss=bl,
                            baseline_logits_fn=lambda: walk(c, pop, h, sig, head, step=step),
                            step_windows=U.Windows(step), domain_id=0, live_domains=1,
                            candidates=candidates)


def units():
    # ---- C-6: the planted expert, the unrouted ones, the sign ------------------------------------
    c, pop, h, sig, head, y = scripted()
    base = walk(c, pop, h, sig, head)
    moved = [not torch.equal(walk(c, pop, h, sig, head, hold_out=e), base) for e in range(4)]
    check("C-6 the scripted population routes every window to the planted expert alone: holding it "
          "out moves the logits and holding out any other moves nothing",
          moved == [True, False, False, False], f"{moved}")
    rep = measure(c, pop, h, sig, head, y, candidates=[0, 1, 2])
    by = dict(zip(rep.candidates, rep.values))
    check("C-6 an unrouted expert reads exactly 0.0 and a planted load-bearing expert reads positive "
          "(the loss without it minus the loss with it); both unrouted are WRITTEN, measured at 0",
          by[1] == 0.0 and by[2] == 0.0 and by[0] > 1.0 and not rep.degenerate
          and pop.contrib[:3] == [by[0], 0.0, 0.0] and pop.contrib_n[:4] == [1, 1, 1, 0]
          and rep.positive == 1 and rep.negative == 0 and rep.distinct_values == 2,
          f"{rep.values}; contrib {pop.contrib[:4]}, contrib_n {pop.contrib_n[:4]}")
    led = pop.counters
    check("C-6 the pass's ledger: fab.contrib_measured 3, fab.contrib_passes 1, fab.holdout_applied 3 "
          "(one held-out walk per candidate), fab.contrib_distinct_values 2, positive 1, negative 0, "
          "coverage 3/4 past grace, and Gate fab.contrib fired",
          (led.get("fab.contrib_measured"), led.get("fab.contrib_passes"),
           led.get("fab.holdout_applied"), led.get("fab.contrib_distinct_values"),
           led.get("fab.contrib_positive"), led.get("fab.contrib_negative"),
           led.get("fab.contrib_coverage")) == (3, 1, 3 + 4, 2, 1, 0, 0.75)
          and next(g for g in pop.gates if g.name == "fab.contrib").fired,
          f"{ {k: v for k, v in led.items() if 'contrib' in k or 'holdout' in k} }")
    # THE SECOND READING MUST DIFFER FROM THE FIRST, or an EMA and an overwrite write one number: on
    # an unchanged population the second measurement returns the first exactly, and
    # (1 - ema) * first + ema * first == first, so this check passed a plant that overwrote
    # (Q-FAB-19's review). The planted expert's B is cut to a twentieth between the two readings --
    # still the expert every window routes to, now worth less.
    first = by[0]
    with torch.no_grad():
        pop.B[0] *= 0.05
    rep2 = measure(c, pop, h, sig, head, y, candidates=[0])
    ema = float(c["FAB"].comp_ema)
    second = rep2.values[0]
    folded = (1.0 - ema) * first + ema * second
    check("C-6 the first measurement SETS contrib and a later one FOLDS IN at FAB_COMP_EMA: with the "
          "planted expert's B cut to a twentieth between them the second reading is smaller than the "
          "first, and contrib is (1 - ema) * first + ema * second -- neither reading alone -- with "
          "contrib_n 2",
          0.0 < second < first and pop.contrib[0] == folded and folded not in (first, second)
          and pop.contrib_n[0] == 2,
          f"first {first}, second {second}; contrib {pop.contrib[0]} against {folded}")
    c, pop, h, sig, head, y = scripted(harmful=True)
    rep = measure(c, pop, h, sig, head, y, candidates=[0, 1])
    check("C-6 a planted HARMFUL expert (it pushes the prediction to the wrong class) reads negative",
          rep.values[0] < -1.0 and rep.values[1] == 0.0 and rep.negative == 1 and rep.positive == 0,
          f"{rep.values}")

    # ---- C-4: degenerate passes write nothing -----------------------------------------------------
    c, pop, h, sig, head, y = scripted()
    rep = measure(c, pop, h, sig, head, y, candidates=[1, 2, 3])
    check("C-4 a pass over unrouted experts only is DEGENERATE (the C3 alarm): no logit moved, nothing "
          "written -- contrib and contrib_n as they were -- fab.contrib_degenerate 1, "
          "fab.contrib_measured 0, and the Gate says DEGENERATE",
          rep.degenerate and rep.values == (0.0, 0.0, 0.0) and rep.distinct_values == 1
          and pop.contrib[:4] == [0.0] * 4 and pop.contrib_n[:4] == [0] * 4
          and pop.counters.get("fab.contrib_degenerate") == 1
          and pop.counters.get("fab.contrib_measured") == 0
          and "DEGENERATE" in rep.gates[0].reason and not rep.gates[0].fired,
          f"{rep}")
    c1, pop1, h1, sig1, head1, y1 = scripted(n=1)
    rep = measure(c1, pop1, h1, sig1, head1, y1)
    check("C-4 a one-expert population is DEGENERATE too: hold_out cannot remove the only expert, so "
          "its walk equals the baseline and nothing is written",
          rep.degenerate and rep.candidates == (0,) and pop1.contrib[0] == 0.0
          and pop1.contrib_n[0] == 0, f"{rep}")

    # ---- C-5 (the refusal half) and C-3 (the refusal half) -----------------------------------------
    c, pop, h, sig, head, y = scripted()
    bl = float(mean_ce(walk(c, pop, h, sig, head), y))
    off = math.nextafter(bl, math.inf)
    try:
        measure(c, pop, h, sig, head, y, candidates=[0], baseline_loss=off)
        check("C-5 a baseline_loss one ulp from what baseline_logits_fn()'s logits score is refused",
              False, "measured")
    except ValueError as e:
        check("C-5 a baseline_loss one ulp from what baseline_logits_fn()'s logits score is refused, "
              "naming P1-H11, and nothing is written",
              "P1-H11" in str(e) and pop.contrib_n[:4] == [0] * 4, str(e)[:160])
    try:
        FAB.contribution(c["FAB"], pop, h=h + 1e-3, signature=sig, novelty=torch.zeros(BATCH),
                         head=head, targets=y, baseline_loss=bl,
                         baseline_logits_fn=lambda: walk(c, pop, h, sig, head),
                         step_windows=U.Windows(10), domain_id=0, live_domains=1, candidates=[0])
        check("C-3 a walk handed other inputs than the baseline's is refused", False, "measured")
    except ValueError as e:
        check("C-3 a walk handed other inputs than the baseline's (h moved by 1e-3) is refused by name: "
              "its reference walk does not reproduce the baseline bit for bit",
              "bit for bit" in str(e) and pop.contrib_n[:4] == [0] * 4, str(e)[:160])

    # ---- C-3: the society arm's reweighted sum, by hand (Q-FAB-19's review) -------------------------
    # c3_society below reads a real society pass, and there only "re-forms bit for bit", "a voter's
    # removal moves its rows" and "a non-voter's returns the prediction" can be asserted, so a
    # _reblend that dropped the renormalisation or the sole-voter fall-back passed it. Here the
    # blend is written by hand and the answer computed by hand. EXACT IN float32, whatever the
    # order of the sums: every logit a small integer, every vote weight and halt mass dyadic, and
    # the held-out voter's weight 0.5, so what the rest renormalise by is 0.5 too.
    pe = (torch.arange(3 * 3 * 2 * 4, dtype=torch.float32).reshape(3, 3, 2, 4) % 7) - 3.0
    base_lg = (torch.arange(3 * 2 * 4, dtype=torch.float32).reshape(3, 2, 4) % 5) - 2.0
    voters = torch.tensor([[1, 2, 3], [2, 3, 4], [1, 4, 2]])
    vw = torch.tensor([[0.5, 0.375, 0.125], [0.25, 0.25, 0.5], [0.5, 0.25, 0.25]])
    held = torch.tensor([0.25, 0.5, 0.0])

    def by_hand(pe_, w, hl, b):
        """(1 - held) * sum_j w_j * logits_j + held * base, row by row."""
        rows = []
        for r in range(int(w.shape[0])):
            vote = sum(float(w[r, j]) * pe_[r, j] for j in range(int(w.shape[1])))
            rows.append((1.0 - float(hl[r])) * vote + float(hl[r]) * b[r])
        return torch.stack(rows)

    blend = (voters, vw, held, base_lg)
    whole = FAB._reblend(pe, blend, None, None)
    # Expert 1 voted in rows 0 and 2 at weight 0.5: the rest of row 0 renormalise to 0.75 and 0.25,
    # of row 2 to 0.5 and 0.5; row 1 it did not vote in.
    w1 = torch.tensor([[0.0, 0.75, 0.25], [0.25, 0.25, 0.5], [0.0, 0.5, 0.5]])
    want = by_hand(pe, w1, held, base_lg)
    want[1] = whole[1]
    got = FAB._reblend(pe, blend, 1, whole)
    check("C-3 the society arm's leave-one-out, on a blend written by hand: nothing removed is "
          "(1 - held) * the vote + held * base; expert 1 removed, each row it voted in is that blend "
          "with its weight dropped and the rest RENORMALISED (row 0 0.375, 0.125 -> 0.75, 0.25), the "
          "row it did not vote in is untouched, and a non-voter's removal returns the prediction",
          torch.equal(whole, by_hand(pe, vw, held, base_lg)) and torch.equal(got, want)
          and not torch.equal(got, whole) and FAB._reblend(pe, blend, 9, whole) is whole,
          f"{(got - want).abs().max().item()}")
    one = (voters[:, :1], torch.ones(3, 1), held, base_lg)
    whole1 = FAB._reblend(pe[:, :1], one, None, None)
    got1 = FAB._reblend(pe[:, :1], one, 1, whole1)
    check("C-3 ... and a row whose ONLY voter is removed is the base logits exactly -- the society "
          "arm's reading of 'no expert is needed' -- at every halt mass (rows 0 and 2, held 0.25 and "
          "0.0), the other row the prediction's",
          torch.equal(got1[0], base_lg[0]) and torch.equal(got1[2], base_lg[2])
          and torch.equal(got1[1], whole1[1]) and not torch.equal(whole1[0], base_lg[0]),
          f"{(got1[0] - base_lg[0]).abs().max().item()}, {(got1[2] - base_lg[2]).abs().max().item()}")

    # ---- C-6: a non-finite loss leaves the candidate unmeasured -------------------------------------
    c, pop, h, sig, head, y = scripted()
    rep = measure(c, pop, h, sig, head, y, candidates=[0, 1], baseline_loss=float("nan"))
    check("C-6 a baseline_loss that is not finite measures nothing: no walk is taken, every candidate "
          "stays as it was and is counted fab.contrib_nonfinite, and the pass is not a pass",
          pop.contrib_n[:4] == [0] * 4 and pop.counters.get("fab.contrib_nonfinite") == 2
          and pop.counters.get("fab.contrib_passes") == 0 and not rep.values,
          f"{rep}; {pop.counters.get('fab.contrib_nonfinite')}")

    # ---- the cursor, the books, the checkpoint ------------------------------------------------------
    c = configs(FAB_N0=10, FAB_SLOTS=12, FAB_GRACE=2, FAB_CONTRIB=1, FAB_CONTRIB_MAX=3)
    pop = FAB.build(c["FAB"], d_model=D, signature_dim=S, device=torch.device("cpu"),
                    generator=rng.rng_for("fabric", 1234, again=True))
    for i in range(10):
        pop.uage[i] = 0 if i in (1, 4, 5) else 3
    seq, cur = [], []
    for _ in range(4):
        got, nxt = FAB._contrib_pick(pop, 10, 2, 3)
        seq.append(got)
        pop.contrib_cursor = nxt
        cur.append(nxt)
    check("C-2 the default candidates are the next FAB_CONTRIB_MAX past-grace experts from the "
          "population's cursor, wrapping, so every past-grace expert is reached in turn: "
          "[0,2,3] [6,7,8] [9,0,2] [3,6,7] over the seven past grace of ten",
          seq == [[0, 2, 3], [6, 7, 8], [9, 0, 2], [3, 6, 7]] and cur == [4, 9, 3, 8], f"{seq} {cur}")
    got, nxt = FAB._contrib_pick(pop, 10, 2, 50)
    check("C-2 a cap above the past-grace count takes every past-grace expert and leaves the cursor",
          got == [8, 9, 0, 2, 3, 6, 7] and nxt == pop.contrib_cursor, f"{got} {nxt}")
    pop.contrib_cursor = 9
    FAB._remove(pop, 2)
    check("C-2 _remove moves the cursor with the expert it points at (swap-with-last): it pointed at "
          "slot 9, the last, which now lives in slot 2",
          pop.contrib_cursor == 2 and int(pop.n_live) == 9, f"{pop.contrib_cursor}")
    pop.contrib_n[3], pop.contrib[3] = 4, -0.5
    FAB._claim_slot(pop, 3, 7)
    check("C-6 a birth into a recycled slot starts unmeasured: _claim_slot clears contrib and contrib_n",
          pop.contrib[3] == 0.0 and pop.contrib_n[3] == 0)
    pop.contrib_n[0], pop.contrib[0], pop.contrib_cursor = 2, 0.25, 5
    sdict = FAB.state_dict(c["FAB"], pop)
    back = FAB.build(c["FAB"], d_model=D, signature_dim=S, device=torch.device("cpu"),
                     generator=rng.rng_for("fabric", 1234, again=True))
    FAB.load_state_dict(c["FAB"], back, sdict, sidecar=sdict["sidecar"])
    check("C-8 FAB.state_dict / load_state_dict carry contrib_n (a book) and the cursor exactly",
          back.contrib_n == pop.contrib_n and back.contrib == pop.contrib and back.contrib_cursor == 5
          and sdict["books"]["contrib_n"][0] == 2 and sdict["contrib_cursor"] == 5)
    del sdict["books"]["contrib_n"]
    del sdict["contrib_cursor"]
    old = FAB.build(c["FAB"], d_model=D, signature_dim=S, device=torch.device("cpu"),
                    generator=rng.rng_for("fabric", 1234, again=True))
    FAB.load_state_dict(c["FAB"], old, sdict, sidecar=sdict["sidecar"])
    check("C-8 a blob written before contrib_n and the cursor restores every expert UNMEASURED "
          "(contrib_n 0) and the cursor at 0, the contrib values as saved",
          old.contrib_n == [0] * 12 and old.contrib_cursor == 0 and old.contrib == pop.contrib)
    gate = next(g for g in old.gates if g.name == "fab.contrib")
    check("C-8 the restored population's Gate fab.contrib is re-rendered as RESTORED where the "
          "measurement is armed", "RESTORED" in gate.reason and not gate.reachable, gate.reason[:120])

    # ---- candidates handed explicitly are validated ------------------------------------------------
    c, pop, h, sig, head, y = scripted()
    for bad, why in (([0, 9], "name no live expert"), ([1, 1], "named twice")):
        try:
            measure(c, pop, h, sig, head, y, candidates=bad)
            check(f"C-2 candidates {bad} are refused", False, "measured")
        except ValueError as e:
            check(f"C-2 candidates {bad} are refused ({why})", why in str(e), str(e)[:120])

    # ---- C-1: the direct call at FAB_CONTRIB=0 --------------------------------------------------------
    c, pop, h, sig, head, y = scripted(FAB_CONTRIB=0)
    rep = measure(c, pop, h, sig, head, y, candidates=[0, 1])
    check("C-1 at FAB_CONTRIB=0 a direct call returns its reason and writes nothing: no book moves, no "
          "fab.contrib_* key, Gate fab.contrib UNREACHABLE naming FAB_CONTRIB=0",
          rep.reason.startswith("FAB_CONTRIB=0") and not rep.candidates
          and pop.contrib_n[:4] == [0] * 4 and pop.contrib[:4] == [0.0] * 4
          and not any(k.startswith("fab.contrib_") for k in pop.counters)
          and not next(g for g in pop.gates if g.name == "fab.contrib").reachable
          and "FAB_CONTRIB=0" in next(g for g in pop.gates if g.name == "fab.contrib").reason,
          f"{rep.reason}; {[k for k in pop.counters if 'contrib' in k]}")


# ==================================================================================================
# C-7 -- 'contrib' on scripted passes
# ==================================================================================================

F_, L_ = 101, 202        # a faded area's id and a live one's


def util_population(mode, measured=(), contrib=1):
    """tests/test_faded.py's utilization population: ten eligible experts, a budget of five, use
    ranks them 0..9, no failure cull, no merge; 0 and 2 serve the faded area, 3 has an empty book.
    `measured` is ((slot, contrib), ...) -- the experts FAB.contribution has measured, and at what;
    `contrib` the FAB_CONTRIB value the population is built at."""
    c = configs(FAB_N0=10, FAB_SLOTS=12, FAB_GRACE=1, FAB_MERGE_DIST=0, FAB_PRESSURE=0.1,
                FAB_CULL_FRAC=0.5, FAB_COMP_PROTECT=0, FAB_FADED_CULL=mode, FAB_CONTRIB=contrib)
    pop = FAB.build(c["FAB"], d_model=D, signature_dim=S, device=torch.device("cpu"),
                    generator=rng.rng_for("fabric", 1234, again=True))
    for i in range(10):
        pop.uage[i], pop.use[i], pop.born[i] = 5, float(i + 1), 100 + i
        pop.ef[i] = pop.es[i] = 1.0
        pop.area_use[i] = {L_: 1.0}
    pop.comp_glob = None
    pop.area_use[0] = {F_: 1.0}
    pop.area_use[2] = {F_: 2.0, L_: 1.0}
    pop.area_use[3] = {}
    for slot, val in measured:
        pop.contrib[slot], pop.contrib_n[slot] = float(val), 1
    return c, pop


def merge_population(mode, measured=()):
    """tests/test_faded.py's merge-then-gate population: one close pair (0, 1) whose absorbee 0 serves
    the faded area, six experts in twelve slots."""
    c = configs(FAB_N0=6, FAB_SLOTS=12, FAB_GRACE=1, FAB_MERGE_DIST=0.1, FAB_PRESSURE=0.5,
                FAB_CULL_FRAC=0.5, FAB_COMP_PROTECT=0, FAB_FADED_CULL=mode, FAB_CONTRIB=1)
    pop = FAB.build(c["FAB"], d_model=D, signature_dim=S, device=torch.device("cpu"),
                    generator=rng.rng_for("fabric", 1234, again=True))
    for i in range(6):
        pop.uage[i], pop.born[i], pop.use[i] = 2, 100 + i, float(i + 1)
        pop.ef[i] = pop.es[i] = 1.0
        pop.area_use[i] = {L_: 1.0}
    pop.comp_glob = 1.0
    with torch.no_grad():
        pop.cent[:6] = torch.eye(S)[:6]
        pop.cent[1] = pop.cent[0]
    pop.uage[0] = 5
    pop.area_use[0] = {F_: 3.0}
    for slot, val in measured:
        pop.contrib[slot], pop.contrib_n[slot] = float(val), 1
    return c, pop


def survivors(pop):
    return sorted(int(pop.born[i]) - 100 for i in range(int(pop.n_live)))


def one_pass(make, mode, measured=()):
    c, pop = make(mode, measured)
    rep = FAB.manage(c["FAB"], pop, step_windows=U.Windows(500), faded=frozenset({F_}))
    return pop, rep


def c7_scripted():
    # THE UTILIZATION CULL. 'as_is' removes 0-4; 'defer' keeps 0 and 2 (each holding its slot).
    pa, _ = one_pass(util_population, "as_is")
    pd, _ = one_pass(util_population, "defer")
    # 'contrib', 0 measured at -0.5 (allowed), 2 unmeasured (kept, holding its slot).
    pc, rc = one_pass(util_population, "contrib", ((0, -0.5),))
    check("C-7 the utilization cull at 'contrib': the faded expert measured at -0.5 is removed and the "
          "UNMEASURED faded one is kept, holding its budget slot -- so no live-area expert goes in its "
          "place: 'as_is' kept 5-9, 'defer' 0, 2, 5-9, 'contrib' 2, 5-9",
          survivors(pa) == [5, 6, 7, 8, 9] and survivors(pd) == [0, 2, 5, 6, 7, 8, 9]
          and survivors(pc) == [2, 5, 6, 7, 8, 9], f"{survivors(pa)} {survivors(pd)} {survivors(pc)}")
    led = pc.counters
    check("C-7 ... counted: fab.cull_faded_allowed_by_contrib 1, fab.cull_faded_refused_by_contrib 1, "
          "fab.culled_faded_area 1 (the allowed one), fab.faded_deferred_experts 1, the merge pair at "
          "0, the deferral pair ABSENT; the ManageReport carries the allowed count",
          (led.get("fab.cull_faded_allowed_by_contrib"), led.get("fab.cull_faded_refused_by_contrib"),
           led.get("fab.merge_faded_allowed_by_contrib"), led.get("fab.merge_faded_refused_by_contrib"),
           led.get("fab.culled_faded_area"), led.get("fab.faded_deferred_experts"))
          == (1, 1, 0, 0, 1, 1)
          and "fab.cull_faded_deferred" not in led and "fab.merge_faded_deferred" not in led
          and rc.cull_faded_allowed_by_contrib == 1 and rc.culled_faded_area == 1
          and rc.cull_faded_deferred == 1,
          f"{ {k: v for k, v in led.items() if 'faded' in k} }")
    for mode, p in (("as_is", pa), ("defer", pd)):
        check(f"C-7 at '{mode}' the four 'contrib' keys are ABSENT",
              not any(k.endswith("_by_contrib") for k in p.counters),
              f"{[k for k in p.counters if 'contrib' in k]}")
    pz, _ = one_pass(util_population, "contrib", ((0, 0.0), (2, 0.0)))
    check("C-7 a contribution MEASURED at exactly 0 allows the removal (NEW-10's <= 0): both faded "
          "experts measured at 0.0 go, as at 'as_is'",
          survivors(pz) == survivors(pa)
          and pz.counters.get("fab.cull_faded_allowed_by_contrib") == 2
          and pz.counters.get("fab.cull_faded_refused_by_contrib") == 0, f"{survivors(pz)}")
    pp, rp = one_pass(util_population, "contrib", ((0, 0.4),))
    check("C-7 a faded expert measured ABOVE 0 is spared as load-bearing before its area is read -- "
          "at 'contrib' as at 'as_is' -- so a cull's refusal is always an unmeasured expert: 0 "
          "spared (spared_contrib 1), 2 refused, and the budget walks on to 5",
          0 in survivors(pp) and 2 in survivors(pp) and rp.spared_contrib == 1
          and pp.counters.get("fab.cull_faded_refused_by_contrib") == 1
          and survivors(pp) == [0, 2, 6, 7, 8, 9], f"{survivors(pp)} spared {rp.spared_contrib}")
    reasons = " ".join(g.reason for g in pc.gates)
    check("C-7 the pass's reasons name the rule's refusals at 'contrib' ('FAB_FADED_CULL='contrib' "
          "kept'), and not 'defer''s words",
          "FAB_FADED_CULL='contrib' kept" in reasons and "FAB_FADED_CULL='defer'" not in reasons,
          reasons[:300])

    # THE MERGE. 'as_is' merges 0 into 1; 'defer' keeps the pair apart.
    ma, _ = one_pass(merge_population, "as_is")
    md, _ = one_pass(merge_population, "defer")
    mu, ru = one_pass(merge_population, "contrib")
    mm, rm = one_pass(merge_population, "contrib", ((0, -0.2),))
    mp, _rpos = one_pass(merge_population, "contrib", ((0, 0.3),))
    check("C-7 the merge at 'contrib': an UNMEASURED faded absorbee is kept apart as at 'defer', one "
          "measured at -0.2 is merged as at 'as_is', and one measured at +0.3 is kept too (the merge "
          "reads no contribution of its own, so its refusal can be either)",
          survivors(mu) == survivors(md) and survivors(mm) == survivors(ma)
          and survivors(mp) == survivors(md) and survivors(ma) != survivors(md)
          and mu.counters.get("fab.merge_faded_refused_by_contrib") == 1
          and mm.counters.get("fab.merge_faded_allowed_by_contrib") == 1
          and mm.counters.get("fab.merged_faded_area") == 1
          and mp.counters.get("fab.merge_faded_refused_by_contrib") == 1
          and rm.merge_faded_allowed_by_contrib == 1 and ru.merge_faded_deferred == 1,
          f"as_is {survivors(ma)} defer {survivors(md)} unmeasured {survivors(mu)} "
          f"measured- {survivors(mm)} measured+ {survivors(mp)}")


def c8_resumed_off():
    """C-8 (Q-FAB-19's review): books measured at FAB_CONTRIB=1, saved by FAB.state_dict and restored
    by FAB.load_state_dict into a build at FAB_CONTRIB=0, are carried -- and FAB.manage reads none
    of them there: both spares and 'contrib''s rule decide as over a population never measured."""
    # THE UTILIZATION CULL'S SPARE: expert 0, the least-used victim, measured at +0.25.
    c1, p1 = util_population("as_is", ((0, 0.25),))
    blob = FAB.state_dict(c1["FAB"], p1)
    c0, p0 = util_population("as_is", contrib=0)
    FAB.load_state_dict(c0["FAB"], p0, blob, sidecar=blob["sidecar"])
    carried = (p0.contrib[0], p0.contrib_n[0])
    r0 = FAB.manage(c0["FAB"], p0, step_windows=U.Windows(500), faded=frozenset({F_}))
    cf, pf = util_population("as_is", contrib=0)
    rf = FAB.manage(cf["FAB"], pf, step_windows=U.Windows(500), faded=frozenset({F_}))
    c1b, p1b = util_population("as_is", ((0, 0.25),))
    r1 = FAB.manage(c1b["FAB"], p1b, step_windows=U.Windows(500), faded=frozenset({F_}))
    check("C-8 books measured at FAB_CONTRIB=1 and restored into a build at 0 are carried (expert 0 at "
          "+0.25, measured once) and the utilization cull reads none of them: it removes 0-4 with "
          "fab.spared_contrib 0, as the population never measured does -- where at 1 the same books "
          "spare 0 and the budget walks on to 5",
          carried == (0.25, 1) and survivors(p0) == survivors(pf) == [5, 6, 7, 8, 9]
          and r0.spared_contrib == 0 == rf.spared_contrib
          and survivors(p1b) == [0, 6, 7, 8, 9] and r1.spared_contrib == 1,
          f"carried {carried}; restored at 0 {survivors(p0)} spared {r0.spared_contrib}; never "
          f"measured {survivors(pf)}; at 1 {survivors(p1b)} spared {r1.spared_contrib}")

    # THE FAILURE CULL'S SPARE: 0 and 1 failing (both error EMAs far above comp_glob), 0 measured at
    # +0.3 and so load-bearing where a measurement is read.
    def failing(contrib, measured=()):
        c = configs(FAB_N0=6, FAB_SLOTS=12, FAB_GRACE=1, FAB_MERGE_DIST=0, FAB_CULL_FRAC=0,
                    FAB_CONTRIB=contrib)
        pop = FAB.build(c["FAB"], d_model=D, signature_dim=S, device=torch.device("cpu"),
                        generator=rng.rng_for("fabric", 1234, again=True))
        for i in range(6):
            pop.uage[i], pop.born[i], pop.use[i] = 5, 100 + i, 1.0
            pop.ef[i] = pop.es[i] = 1.0
            pop.area_use[i] = {L_: 1.0}
        pop.comp_glob = 1.0
        for i in (0, 1):
            pop.ef[i] = pop.es[i] = 5.0
        for slot, val in measured:
            pop.contrib[slot], pop.contrib_n[slot] = float(val), 1
        return c, pop
    c1, p1 = failing(1, ((0, 0.3),))
    blob = FAB.state_dict(c1["FAB"], p1)
    c0, p0 = failing(0)
    FAB.load_state_dict(c0["FAB"], p0, blob, sidecar=blob["sidecar"])
    r0 = FAB.manage(c0["FAB"], p0, step_windows=U.Windows(500), faded=frozenset({F_}))
    c1b, p1b = failing(1, ((0, 0.3),))
    r1 = FAB.manage(c1b["FAB"], p1b, step_windows=U.Windows(500), faded=frozenset({F_}))
    check("C-8 ... and the failure cull reads none either: restored at 0 both failing experts go "
          "(fab.spared_contrib 0), where at 1 the one measured at +0.3 is spared as load-bearing",
          survivors(p0) == [2, 3, 4, 5] and r0.cull_fail == 2 and r0.spared_contrib == 0
          and survivors(p1b) == [0, 2, 3, 4, 5] and r1.cull_fail == 1 and r1.spared_contrib == 1,
          f"restored at 0 {survivors(p0)} ({r0.cull_fail} culled, {r0.spared_contrib} spared); at 1 "
          f"{survivors(p1b)} ({r1.cull_fail} culled, {r1.spared_contrib} spared)")

    # 'contrib''S RULE AT 0 -- a pairing startup refuses, so only a direct call reaches it -- reads no
    # measurement either: the faded expert measured at -0.5 is kept beside the unmeasured one.
    cz, pz = util_population("contrib", ((0, -0.5),), contrib=0)
    FAB.manage(cz["FAB"], pz, step_windows=U.Windows(500), faded=frozenset({F_}))
    check("C-8 ... and FAB_FADED_CULL='contrib' at 0 (refused at startup; a direct call) keeps every "
          "faded removal, the one measured at -0.5 included -- 'defer' under the rule's names",
          survivors(pz) == [0, 2, 5, 6, 7, 8, 9]
          and pz.counters.get("fab.cull_faded_refused_by_contrib") == 2
          and pz.counters.get("fab.cull_faded_allowed_by_contrib") == 0,
          f"{survivors(pz)}; { {k: v for k, v in pz.counters.items() if k.endswith('_by_contrib')} }")

    # THE GATE: re-rendered at 0 where the restored books or ledger carry a measurement, and build's
    # line kept where the lineage never armed it.
    c1, p1 = util_population("as_is", ((0, 0.25), (4, -0.1)))
    blob = FAB.state_dict(c1["FAB"], p1)
    c0, p0 = util_population("as_is", contrib=0)
    FAB.load_state_dict(c0["FAB"], p0, blob, sidecar=blob["sidecar"])
    g0 = next(g for g in p0.gates if g.name == "fab.contrib")
    cn, pn = util_population("as_is", contrib=0)
    blob_n = FAB.state_dict(cn["FAB"], pn)
    cq, pq = util_population("as_is", contrib=0)
    FAB.load_state_dict(cq["FAB"], pq, blob_n, sidecar=blob_n["sidecar"])
    gq = next(g for g in pq.gates if g.name == "fab.contrib")
    gb = next(g for g in pn.gates if g.name == "fab.contrib")
    check("C-8 restored at 0 from a lineage that armed the measurement, Gate fab.contrib stays "
          "UNREACHABLE naming FAB_CONTRIB=0 and says what the restore carried (2 of the 10 live "
          "experts measured, read by nothing) instead of build's line; from a lineage that never "
          "armed it, it keeps build's line, which claims no 0.0 it cannot see",
          not g0.reachable and g0.reason.startswith("FAB_CONTRIB=0")
          and "RESTORED from a lineage that armed it: 2 of the 10" in g0.reason
          and "FAB.manage reads no contribution" in g0.reason
          and gq.reason == gb.reason and not gq.reachable and "RESTORED" not in gq.reason
          and "FAB.manage reads no contribution" in gb.reason and "stays 0.0" not in gb.reason,
          f"{g0.reason[:240]} || {gq.reason[:120]}")


# ==================================================================================================
# C-2, C-3, C-5, C-7, C-8, C-9 -- the loop
# ==================================================================================================

def c2_run():
    s = build(**C2)
    with Spy() as spy:
        r = loop.run(s, max_windows=C2_WINDOWS, progress=False)
    led, bk = fab_ledger(r), ebook(r)
    calls = [rep for _kw, rep in spy.calls]
    walked = [rep for rep in calls if rep.candidates and rep.baseline_loss is not None
              and math.isfinite(rep.baseline_loss)]
    written = sum(0 if rep.degenerate else sum(1 for v in rep.values if math.isfinite(v))
                  for rep in walked)
    fires = int(r.cadence_ledger["fab.manage"][1])
    check("C-2 at FAB_CONTRIB=1 over 200 windows: fab.contrib_distinct_values > 1, and a pass read "
          "load-bearing and unrouted experts apart",
          (led.get("fab.contrib_distinct_values") or 0) > 1 and len(walked) >= 5
          and any(rep.distinct_values > 1 for rep in walked),
          f"distinct {led.get('fab.contrib_distinct_values')}; {len(walked)} passes walked; per pass "
          f"{[rep.distinct_values for rep in walked]}")
    check("C-2 fab.contrib_measured equals the candidates the passes wrote, summed; fab.holdout_applied "
          "the candidates walked (one held-out walk each); no pass degenerate or non-finite",
          led.get("fab.contrib_measured") == written == sum(len(rep.candidates) for rep in walked)
          and led.get("fab.holdout_applied") == sum(len(rep.candidates) for rep in walked)
          and led.get("fab.contrib_degenerate") == 0 and led.get("fab.contrib_nonfinite") == 0,
          f"measured {led.get('fab.contrib_measured')}, written {written}, holdout_applied "
          f"{led.get('fab.holdout_applied')}")
    check("C-2 one call per manage pass with an arrived control window: eval.contrib.calls is the "
          "calls the spy saw, eval.contrib.empty the passes with none, the two summing to the "
          "fab.manage fires; fab.contrib_passes the calls that walked",
          bk.get("eval.contrib.calls") == len(calls) and bk.get("eval.contrib.empty") == 0
          and len(calls) + int(bk.get("eval.contrib.empty", 0)) == fires >= 5
          and led.get("fab.contrib_passes") == len(walked),
          f"calls {bk.get('eval.contrib.calls')}/{len(calls)}, empty {bk.get('eval.contrib.empty')}, "
          f"fires {fires}, passes {led.get('fab.contrib_passes')}")
    ok_cursor = all(kw.get("candidates") is None for kw, _rep in spy.calls)
    last = walked[-1]
    check("C-2 every call took its candidates off the population's cursor (candidates=None), up to "
          "FAB_CONTRIB_MAX each, and fab.contrib_coverage is the last pass's candidates over its "
          "past-grace count",
          ok_cursor and all(len(rep.candidates) <= 64 for rep in walked)
          and led.get("fab.contrib_coverage") == round(len(last.candidates) / last.eligible, 6),
          f"coverage {led.get('fab.contrib_coverage')}, last {len(last.candidates)}/{last.eligible}")
    gl = gated_line(r, "FAB.contribution")
    g3 = r.report["FAB.counters"].get("gate:fab.contrib")
    check("C-2 the gated-call line reads 'fired N time(s)' with N = fab.contrib_passes, and Gate "
          "fab.contrib's row reads fired at that count",
          gl.startswith(f"FAB.contribution: fired {led.get('fab.contrib_passes')} time(s)")
          and g3 is not None and g3[0] == "fired" and g3[1] == led.get("fab.contrib_passes"),
          f"{gl[:80]}; {g3}")
    check("C-2 the contrib > 0 spare can fire now: fab.spared_contrib is present (the manage passes "
          "read what contribution measured)", "fab.spared_contrib" in led,
          f"{led.get('fab.spared_contrib')}")
    return s, r


def c3_system(s):
    """On C-2's trained System: the closure's pass and FAB.forward handed its inputs agree bit for
    bit, at clock.step + 1."""
    mat = _contrib_material(s, set(s.probe_set.items))
    x, _y, prefix, rows = mat
    fn = _logits_fn(s, use_memory=False, book="eval.contrib")
    route = {}
    with torch.no_grad():
        lg = fn(x, prefix_bytes=prefix, route=route)
        with _eval_mode(s), s.process.autocast():
            out = FAB.forward(s.configs["FAB"], s.fabric, h=route["h"], signature=route["signature"],
                              novelty=route["novelty"], head=fn.head, targets=None,
                              step_windows=route["step_windows"], domain_id=route["domain_id"],
                              live_domains=route["live_domains"], training=False, hold_out=None)
            walk_lg = out.logits if out.logits is not None else fn.head(out.hidden)
        again = _contrib_baseline(s, fn, x, prefix)()
    check("C-3 FAB.forward handed the memory-off closure's own inputs, with nothing held out, returns "
          "the closure's logits bit for bit; the pricing is clock.step + 1, and the baseline callable "
          "bound to the batch returns them again",
          torch.equal(walk_lg, lg) and torch.equal(again, lg)
          and int(route["step_windows"]) == int(s.clock.step) + 1
          and float(route["novelty"].abs().sum()) == 0.0 and rows == int(x.shape[0]),
          f"step {int(route['step_windows'])} against clock {int(s.clock.step)}; {rows} rows")


def c3_society():
    s = build(**dict(C2, FAB_SOCIETY="1", FAB_CONTRIB_MAX="8"))
    with Spy() as spy:
        r = loop.run(s, max_windows=60, progress=False)
    led = fab_ledger(r)
    walked = [rep for _kw, rep in spy.calls if rep.values]
    # A CANDIDATE THAT CAST NO VOTE IN ANY ROW MOVES NOTHING ON THIS ARM, so a pass whose candidates
    # all missed the batch's (rows x FAB_ENS_K) votes is degenerate -- the C3 alarm, which writes
    # nothing -- and one that reached a voter is not.
    check("C-3 on the society arm the leave-one-out is the reweighted sum of the pass's blend: two "
          "passes walked, one fab.holdout_applied per candidate and none from a held-out walk (which "
          "would count a second), a pass none of whose candidates voted is degenerate and writes "
          "nothing, and one that reached a voter wrote",
          len(walked) == 2 and led.get("fab.holdout_applied") == sum(len(p.candidates) for p in walked)
          and led.get("fab.contrib_passes") == 2
          and led.get("fab.contrib_degenerate") == sum(1 for p in walked if p.degenerate)
          and any(not p.degenerate and p.distinct_values > 1 for p in walked)
          and led.get("fab.contrib_measured") == sum(len(p.candidates) for p in walked
                                                     if not p.degenerate),
          f"{[(len(p.candidates), p.distinct_values, p.degenerate) for p in walked]}; "
          f"holdout {led.get('fab.holdout_applied')}, measured {led.get('fab.contrib_measured')}")
    mat = _contrib_material(s, set(s.probe_set.items))
    x, _y, prefix, _rows = mat
    fn = _logits_fn(s, use_memory=False, book="eval.contrib")
    route = {}
    with torch.no_grad():
        lg = fn(x, prefix_bytes=prefix, route=route)
        with _eval_mode(s), s.process.autocast():
            out = FAB.forward(s.configs["FAB"], s.fabric, h=route["h"], signature=route["signature"],
                              novelty=route["novelty"], head=fn.head, targets=None,
                              step_windows=route["step_windows"], domain_id=route["domain_id"],
                              live_domains=route["live_domains"], training=False)
        re = FAB._reblend(out.per_expert_logits, out.blend, None, out.logits)
        voters = out.blend[0]
        one = int(voters[0, 0])
        held = FAB._reblend(out.per_expert_logits, out.blend, one, out.logits)
        other = [e for e in range(int(s.fabric.n_live)) if not bool((voters == e).any())]
        spare = FAB._reblend(out.per_expert_logits, out.blend, other[0], out.logits) if other else None
    check("C-3 the society arm's blend re-formed with nothing removed is the prediction bit for bit (and "
          "the closure's); removing a voter moves its rows, removing a non-voter returns the "
          "prediction itself",
          torch.equal(out.logits, lg) and torch.equal(re, out.logits)
          and not torch.equal(held, out.logits) and (spare is None or spare is out.logits),
          f"voter {one}; non-voters {len(other)}")


def c5_c7_phased():
    s = build(**dict(B3, FAB_CONTRIB="1", FAB_FADED_CULL="contrib", FAB_CONTRIB_MAX="32"))
    removed = []            # (faded set, contrib_n, contrib, book) of every expert a pass removed
    real_manage, real_remove = FAB.manage, FAB._remove
    state = {"faded": None, "in": False}

    def manage(fab, pop, **kw):
        f = kw.get("faded")
        state["faded"], state["in"] = (None if f is None else frozenset(f)), True
        try:
            return real_manage(fab, pop, **kw)
        finally:
            state["in"] = False

    def remove(pop, slot):
        if state["in"] and state["faded"] is not None:
            removed.append((state["faded"], int(pop.contrib_n[slot]), float(pop.contrib[slot]),
                            dict(pop.area_use[slot])))
        return real_remove(pop, slot)

    FAB.manage, FAB._remove = manage, remove
    try:
        with Spy(s, recheck=True) as spy:
            r = loop.run(s, progress=False)
    finally:
        FAB.manage, FAB._remove = real_manage, real_remove
    led = fab_ledger(r)

    def top(book):
        if not book:
            return None
        best = max(book.values())
        return min(k for k, v in book.items() if v == best)

    faded_rm = [(n, v) for fs, n, v, b in removed if b and top(b) in fs]
    check("C-5 in every call the loop made, baseline_loss is what LM.lm_loss gives baseline_logits_fn()'s "
          "logits -- the memory-off closure bound to the batch -- exactly",
          len(spy.rechecked) >= 5 and all(a == b for a, b in spy.rechecked),
          f"{len(spy.rechecked)} calls; {[(a, b) for a, b in spy.rechecked if a != b][:2]}")
    check("C-7 in a phased run at FAB_FADED_CULL='contrib' every removed faded-area expert had been "
          "MEASURED at or below 0 when it went",
          all(n > 0 and v <= 0.0 for n, v in faded_rm),
          f"{len(faded_rm)} faded removals; {[x for x in faded_rm if not (x[0] > 0 and x[1] <= 0)][:4]}")
    refused = (led.get("fab.cull_faded_refused_by_contrib", 0)
               + led.get("fab.merge_faded_refused_by_contrib", 0))
    check("C-7 ... the rule fired: fab.*_faded_refused_by_contrib > 0 (unmeasured experts kept), the "
          "allowed counts equal the faded removals (fab.culled_faded_area, fab.merged_faded_area), and "
          "the deferral pair is ABSENT",
          refused > 0
          and led.get("fab.cull_faded_allowed_by_contrib") == led.get("fab.culled_faded_area")
          and led.get("fab.merge_faded_allowed_by_contrib") == led.get("fab.merged_faded_area")
          and led.get("fab.culled_faded_area", 0) + led.get("fab.merged_faded_area", 0) == len(faded_rm)
          and "fab.cull_faded_deferred" not in led and "fab.merge_faded_deferred" not in led,
          f"refused {refused}; allowed cull {led.get('fab.cull_faded_allowed_by_contrib')} merge "
          f"{led.get('fab.merge_faded_allowed_by_contrib')}; faded removals {len(faded_rm)}")


def c8_continuation(r_u):
    env = dict(C2)
    par = build(CKPT_DIR=f"{TMP}/c8", **env)
    rp = loop.run(par, max_windows=110, progress=False)
    kid = build(CKPT_RESUME=f"{TMP}/c8", CKPT_DIR=f"{TMP}/c8c", **env)
    rk = loop.run(kid, max_windows=C2_WINDOWS - 110, progress=False)
    exact = rp.loss_curve == r_u[1].loss_curve[:110] and rk.loss_curve == r_u[1].loss_curve[110:]
    s_u = r_u[0]
    n_u, n_k = int(s_u.fabric.n_live), int(kid.fabric.n_live)
    books = (n_u == n_k and s_u.fabric.contrib[:n_u] == kid.fabric.contrib[:n_k]
             and s_u.fabric.contrib_n[:n_u] == kid.fabric.contrib_n[:n_k]
             and s_u.fabric.contrib_cursor == kid.fabric.contrib_cursor)
    lu, lk = fab_ledger(r_u[1]), fab_ledger(rk)
    keys = sorted(k for k in lu if k.startswith("fab.contrib_") or k == "fab.holdout_applied")
    counts = all(lu.get(k) == lk.get(k) for k in keys)
    bu, bkid = ebook(r_u[1]), ebook(rk)
    ekeys = sorted(k for k in bu if k.startswith("eval.contrib.") and type(bu[k]) is int)
    book = all(bu.get(k) == bkid.get(k) for k in ekeys) and len(ekeys) >= 8
    check("C-8 a continuing resume at window 110 (between the passes at 101 and 126) at FAB_CONTRIB=1 "
          "continues exactly, and ends with the uninterrupted run's contrib books and cursor, "
          "fab.contrib_* counts and eval.contrib book",
          exact and books and counts and book,
          f"losses {exact}; books {books}; counts {counts} over {keys}; book {book} over {ekeys}")

    # THE SAME PARENT RESUMED AT FAB_CONTRIB=0 (Q-FAB-19's review). The books and FAB's ledger cross
    # the resume; FAB.manage reads a measurement at 1 only. Two children of the one checkpoint, both
    # at 0: `off`, whose restored measurements are PLANTED at +1.0 -- load-bearing, so a pass that
    # read them would spare every measured victim -- and `twin`, whose restored books are cleared,
    # a lineage that never measured. They must train alike and end alike but for those books.
    env0 = dict(C2, FAB_CONTRIB="0")
    off = build(CKPT_RESUME=f"{TMP}/c8", **env0)
    n_off = int(off.fabric.n_live)
    had = [i for i in range(n_off) if int(off.fabric.contrib_n[i]) > 0]
    carried = (off.fabric.contrib == par.fabric.contrib
               and off.fabric.contrib_n == par.fabric.contrib_n and len(had) > 0)
    g_restored = next(g for g in off.fabric.gates if g.name == "fab.contrib")
    for i in had:
        off.fabric.contrib[i] = 1.0
    with Spy() as spy0:
        r_off = loop.run(off, max_windows=C2_WINDOWS - 110, progress=False)
    # THE TWIN IS BUILT AFTER `off` HAS RUN, as a second run.py process would build it: build()
    # forgets the issued streams and empties LM's process tally, which `off` must not see mid-run.
    twin = build(CKPT_RESUME=f"{TMP}/c8", **env0)
    cap = int(twin.fabric.cap)
    twin.fabric.contrib[:] = [0.0] * cap
    twin.fabric.contrib_n[:] = [0] * cap
    r_twin = loop.run(twin, max_windows=C2_WINDOWS - 110, progress=False)
    excl = ("FAB.books.contrib", "FAB.books.contrib_n")
    same_state = sd.digest(off, exclude=excl) == sd.digest(twin, exclude=excl)
    lo, lt, lp = fab_ledger(r_off), fab_ledger(r_twin), fab_ledger(rp)
    ckeys = sorted(k for k in lp if k.startswith("fab.contrib_"))
    check("C-8 C-2's parent at window 110 resumed at FAB_CONTRIB=0 carries its books (%d measured "
          "experts restored) and reads none of them: FAB.contribution is never called, and planted "
          "load-bearing (+1.0) they leave the child exactly as a twin whose books were cleared -- "
          "the same losses, the same state but the two books, the same FAB ledger, "
          "fab.spared_contrib the parent's" % len(had),
          carried and not spy0.calls and r_off.loss_curve == r_twin.loss_curve and same_state
          and lo == lt and lo.get("fab.spared_contrib") == lp.get("fab.spared_contrib")
          and int(r_off.cadence_ledger["fab.manage"][1]) >= 3,
          f"carried {carried}; calls {len(spy0.calls)}; losses "
          f"{r_off.loss_curve == r_twin.loss_curve}; state {same_state}; ledgers "
          f"{sorted(k for k in set(lo) | set(lt) if lo.get(k) != lt.get(k))[:6]}; spared "
          f"{lo.get('fab.spared_contrib')} against the parent's {lp.get('fab.spared_contrib')}")
    g_run = r_off.report["FAB.counters"].get("gate:fab.contrib")
    walked = lp.get("fab.contrib_passes")
    check("C-8 ... and its report says what crossed: the ledger's fab.contrib_* keys are the "
          "lineage's, unmoved (the gated-call line counts the parent's %s passes), no eval.contrib.* "
          "key exists (the root's book restores only what it armed), and Gate fab.contrib is "
          "UNREACHABLE naming FAB_CONTRIB=0 with the restored count, not build's line" % walked,
          ckeys and all(lo.get(k) == lp.get(k) for k in ckeys)
          and gated_line(r_off, "FAB.contribution").startswith(
              f"FAB.contribution: fired {walked} time(s)")
          and not any(k.startswith("eval.contrib.") for k in ebook(r_off))
          and not g_restored.reachable and g_run is not None and g_run[0] == "unreachable"
          and "-- FAB_CONTRIB=0: " in g_run[2] and "FAB.manage reads no contribution" in g_run[2]
          and f"RESTORED from a lineage that armed it: {len(had)} of the {n_off}" in g_run[2]
          and f"{walked} pass(es) walked before this process" in g_run[2],
          f"{[k for k in ckeys if lo.get(k) != lp.get(k)]}; "
          f"{gated_line(r_off, 'FAB.contribution')[:60]}; {g_run}")


def c9_neutral():
    quiet = {"FAB_CULL_FRAC": "0", "FAB_MERGE_DIST": "0", "FAB_FAIL_TOL": "1000", "LM_DROPOUT": "0.1"}
    on_env = dict(C2, **quiet)
    off_env = dict(on_env, FAB_CONTRIB="0")
    s_off = build(**off_env)
    with Spy() as spy_off:
        r_off = loop.run(s_off, max_windows=100, progress=False)
    s_on = build(**on_env)
    with Spy() as spy_on:
        r_on = loop.run(s_on, max_windows=100, progress=False)
    # ---- C-1 on the OFF run: the probe armed, the manage passes reached, contribution inert -----
    led_off, bk_off = fab_ledger(r_off), ebook(r_off)
    pop = s_off.fabric
    g = r_off.report["FAB.counters"].get("gate:fab.contrib")
    check("C-1 at the shipped FAB_CONTRIB=0, on a run that reads the probe and reaches three manage "
          "passes, FAB.contribution is never called: Population.contrib stays 0.0 and contrib_n 0 on "
          "every slot, the cursor at 0, no fab.contrib_* or eval.contrib.* key exists",
          not spy_off.calls and pop.contrib == [0.0] * int(pop.cap)
          and pop.contrib_n == [0] * int(pop.cap) and pop.contrib_cursor == 0
          and not any(k.startswith("fab.contrib_") for k in led_off)
          and not any(k.startswith("eval.contrib.") for k in bk_off)
          and int(r_off.cadence_ledger["fab.manage"][1]) == 3 and bk_off.get("eval.holdout.calls"),
          f"{len(spy_off.calls)} calls; {[k for k in led_off if 'contrib' in k]}")
    check("C-1 ... Gate fab.contrib is UNREACHABLE naming FAB_CONTRIB=0, and the gated-call line reads "
          "UNREACHABLE",
          g is not None and g[0] == "unreachable" and "FAB_CONTRIB=0" in g[2]
          and gated_line(r_off, "FAB.contribution").startswith("FAB.contribution: UNREACHABLE"),
          f"{g}; {gated_line(r_off, 'FAB.contribution')[:60]}")
    # ---- C-9: the same losses, the same state, the same counters but the named set -------------
    check("C-9 with nothing reading contrib, FAB_CONTRIB=1 trains the same losses as 0, float for "
          "float, at LM_DROPOUT=0.1 (every pass in eval mode, no global stream drawn)",
          r_on.loss_curve == r_off.loss_curve
          and len(spy_on.calls) == int(r_on.cadence_ledger["fab.manage"][1]) == 3
          and all(rep.values for _kw, rep in spy_on.calls),
          f"{len(spy_on.calls)} calls; first differing flush "
          f"{next((i for i, (a, b) in enumerate(zip(r_on.loss_curve, r_off.loss_curve)) if a != b), None)}")
    excl = ("FAB.books.contrib", "FAB.books.contrib_n", "FAB.contrib_cursor", "LOOP.eval")
    d_on, d_off = sd.digest(s_on, exclude=excl, detail=True), sd.digest(s_off, exclude=excl, detail=True)
    d_on_all = sd.digest(s_on, detail=True)
    d_off_all = sd.digest(s_off, detail=True)
    check("C-9 ... and ends in the same state but the contrib books, the cursor and LOOP.eval (the "
          "eval book, which carries eval.contrib.*), which do differ",
          d_on == d_off and "FAB.books" in sd.differing(d_on_all, d_off_all)
          and "FAB.contrib_cursor" in sd.differing(d_on_all, d_off_all),
          f"differing {sd.differing(d_on, d_off)}")
    bk, led = ebook(r_on), fab_ledger(r_on)
    f, dec = int(bk["eval.contrib.forwards"]), int(bk["eval.contrib.decodes"])
    cand = sum(len(rep.candidates) for _kw, rep in spy_on.calls if rep.values)
    lm, world = s_on.configs["LM"], s_on.configs["WORLD"]
    composed = bool(getattr(s_on.model, "compose", None))
    inert = (not bool(world.feedback)) or (not bool(getattr(world, "enabled", True)))
    want = {"tok.segment_remap": int(bk["eval.contrib.cuts"]),
            "fab.eval_passes": f + int(led["fab.contrib_passes"]),
            "fab.holdout_applied": cand,
            "lm.embed.calls": f,
            "lm.embed.from_emb_weight": 0 if composed else f,
            "lm.embed.from_composed_table": f if composed else 0,
            "lm.encode.calls": f,
            "lm.decode.calls": dec,
            "lm.mask.applied": dec if bool(lm.mask_dead_rows) else 0,
            "lm.loss.calls": int(bk["eval.contrib.calls"]),
            "sig.encode_calls": int(bk["eval.contrib.sig_calls"]),
            "sig.encode_windows": int(bk["eval.contrib.sig_windows"]),
            "world.forecast.calls": f,
            "world.forecast.inert": f if inert else 0}
    a, b = flat_ints(r_on.report), flat_ints(r_off.report)
    bad, moved = [], {}
    for rk in sorted(set(a) | set(b)):
        row, key = rk
        if key.startswith("eval.contrib.") or key.startswith("fab.contrib_"):
            if rk in b:
                bad.append(f"{row}:{key} present at FAB_CONTRIB=0")
            continue
        va, vb = a.get(rk), b.get(rk)
        if key in want:
            moved[key] = (None if va is None or vb is None else va - vb)
            if (va or 0) - (vb or 0) != want[key]:
                bad.append(f"{row}:{key} moved {(va or 0) - (vb or 0)}, the book says {want[key]}")
        elif va != vb:
            bad.append(f"{row}:{key} {vb} -> {va}")
    check("C-9 every integer counter is equal but a named set, each moving by exactly the eval.contrib "
          "book's or FAB's own count: tok.segment_remap by the cuts; fab.eval_passes by the closure "
          "passes plus fab.contrib_passes; fab.holdout_applied by the candidates; lm.embed.*, "
          "lm.encode.calls and world.forecast.* by the forwards; lm.decode.calls by the decodes; "
          "lm.loss.calls by the calls; sig.encode_calls and sig.encode_windows by the SIG encodes and "
          "their rows",
          not bad and moved.get("fab.eval_passes", 0) > 0 and moved.get("lm.loss.calls", 0) == 3,
          f"{bad[:6]}; moved {moved}")


def startup_refusals():
    for env, stage, words in (
            ({"FAB_FADED_CULL": "contrib"}, "refuse", ("FAB_FADED_CULL='contrib'", "FAB_CONTRIB=0")),
            ({"FAB_CONTRIB": "1"}, "refuse", ("FAB_CONTRIB=1", "EVAL_RETENTION_EVERY=0")),
            ({"FAB_CONTRIB": "1", "EVAL_RETENTION_EVERY": "20"}, None,
             ("FAB_CONTRIB=1", "nothing was pinned", "DATA_SYNTH_HOLDOUT=1"))):
        try:
            build(**env)
            check(f"C-7 startup refuses {env}", False, "built")
        except RefusedRun as e:
            check(f"C-7 startup refuses {env}"
                  + (f" at the '{stage}' stage" if stage else " once the probe pinned nothing")
                  + ", naming " + " and ".join(words),
                  (stage is None or e.stage == stage)
                  and any(all(w in x for w in words) for x in e.refusals), str(e.refusals)[:300])
    try:
        configs(FAB_CONTRIB_MAX=0)
        check("C-7 FAB_CONTRIB_MAX=0 is refused by its domain", False, "built")
    except _lever.LeverError as e:
        check("C-7 FAB_CONTRIB_MAX=0 is refused by its domain at the first read",
              "FAB_CONTRIB_MAX" in str(e) and "domain" in str(e), str(e)[:120])


def main():
    try:
        units()
        c7_scripted()
        c8_resumed_off()
        startup_refusals()
        s1, r1 = c2_run()
        c3_system(s1)
        c8_continuation((s1, r1))
        c3_society()
        c9_neutral()
        c5_c7_phased()
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    print(f"=== {len(FAILS)} failure(s)" + (": " + "; ".join(FAILS) if FAILS else ""))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
