"""CAUSALITY OF THE ROUTED FORWARD -- does anything a window is scored on predicting reach the logits
that predict it? Driven through the real loop and the real entry points (compose -> loop.run ->
LM.encode -> FAB.forward -> LM.decode), on a short default run.

    python3 tests/test_causality.py        # exit 0 = every check passed

WHY IT EXISTS (Q-FAB-7, docs/04_CONTRACT.md). THREE CHANNELS let a window's own targets into its
routing, measured on 2026-09-24, and no other file in tests/ could see any of them, because none of
them compares a logit against the tokens that come after it:

  C1  THE SIGNATURE CURSOR. The loop passed `win_in_epoch` AFTER its increment -- the window's index
      plus one -- to spine/compose.py::_sample_window, so the SIG.encode / DOM.observe sample ended
      at the LAST target's first byte and covered the whole window (window 149 of a default run: x
      bytes [28402, 28599), sample [28407, 28599)). SIG.train_step's `seen_units` read the same
      cursor. Both must END AT OR BEFORE THE WINDOW'S FIRST BYTE, and the sample must end EXACTLY
      there (a sample that ends earlier throws away context the window is entitled to).
  C2  THE ROUTE STATE. fabric/api.py::_route_query added hproj(h.mean(1)) -- a mean over every
      position -- to a routing decision taken once per window and applied at every position, so
      tokens after t chose the experts that score token t: max|dlogit| at positions <= t with tokens
      [t+1:] replaced was 2.4e-6 at window 2, 1.1e-4 at 150 and 8.2e-4 at 600. A causal forward
      gives EXACTLY 0.0, and so this check does not take a tolerance: the model is deterministic on
      one thread and the prefix's arithmetic does not depend on the suffix.
  C3  THE FLUSH'S DOMAIN. FAB.forward takes ONE domain id per flush and bans on it for every row. At
      OPT_BATCH_WINDOWS > 1 the loop passed the LAST window's id, assigned from a sample over the
      earlier rows' own text. It must pass the FIRST window's.

  C4  THE BATCH-WIDE WRITES INSIDE A TRAINING PASS (Q-FAB-7 (4)). At OPT_BATCH_WINDOWS > 1 row k's
      signature covers row 0's own targets, and a training pass wrote a mean over every row into
      state row 0 then routed on: the spawn test decoded an expert from query.mean(0), and the
      grounding EMA moved the centroids between hops. Replacing ONLY row 1's signature (and tokens)
      moved row 0's training-pass logits by 4.8e-7 at the shipped depth and 1.3e-3 at FAB_DEPTH0=0
      FAB_SPAWN=0. C2 could not see it: one row, and an eval pass, which writes neither. Each
      forward here runs on a copy of the population, so the repeat check reads exactly 0.0.

C2 ALSO CHECKS THAT IT HAS TEETH, because "nothing moved" is also what a forward with the fabric out
of the path reads: the perturbation must move logits AFTER t, and a different signature must move
position 0's logits (routing reaches the output at all).
"""
import inspect
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import torch                                                       # noqa: E402
torch.set_num_threads(1)

from spine import lever as _lever                                  # noqa: E402
from spine import rng                                              # noqa: E402
from spine import units as U                                       # noqa: E402
from spine import loop                                             # noqa: E402
from spine.compose import compose, _sample_window, _signature_cursor   # noqa: E402
from lm import api as lm_api                                       # noqa: E402
from fabric import api as fab_api                                  # noqa: E402
from sig import api as sig_api                                     # noqa: E402

FAILS = []
# A SMALL STREAM, AND ENOUGH WINDOWS FOR THE ROUTER TO MATTER: at 40 windows the pre-repair C2 leak
# is well above zero, and the whole file runs in well under a minute on one thread.
BASE = {"DATA_STREAM_BYTES": "60000"}
TRAIN_WINDOWS = 40


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" -- {detail}" if detail else ""))
    if not ok:
        FAILS.append(name)


def build(**env):
    """One real System per configuration. The assembly latch and the rng registry are reopened
    first because each call here stands for a different run."""
    _lever._reopen_assembly()
    rng.reset_issued()
    e = dict(BASE)
    e.update({k: str(v) for k, v in env.items()})
    return compose(environ=e)


class _Patch:
    """Rebind one module attribute for the duration of a `with`, and put it back whatever happens."""

    def __init__(self, mod, name, fn):
        self.mod, self.name, self.fn = mod, name, fn

    def __enter__(self):
        self.orig = getattr(self.mod, self.name)
        setattr(self.mod, self.name, self.fn(self.orig))
        return self

    def __exit__(self, *exc):
        setattr(self.mod, self.name, self.orig)
        return False


def c1_and_train(sysm):
    """C1 over a real run, which also leaves `sysm` trained for C2. Returns the per-window records."""
    rec = {"bounds": [], "sample": [], "seen": []}

    def wb(orig):
        def f(ids, i, ctx):
            out = orig(ids, i, ctx)
            if out is not None:
                rec["bounds"].append(out)
            return out
        return f

    def sw(orig):
        def f(s, sig, at_window):
            rec["sample"].append((len(rec["bounds"]) - 1, int(at_window)))
            return orig(s, sig, at_window)
        return f

    def ts(orig):
        def f(*a, **k):
            rec["seen"].append((len(rec["bounds"]) - 1, int(k["seen_units"])))
            return orig(*a, **k)
        return f

    with _Patch(loop, "_window_bounds", wb), _Patch(loop, "_c_sample_window", sw), \
            _Patch(loop.sig_api, "train_step", ts):
        res = loop.run(sysm, max_windows=TRAIN_WINDOWS, progress=False)

    st = sysm.sig
    bp = sysm.segmentation.byte_pos
    bad_end, bad_exact = [], []
    for w, at in rec["sample"]:
        first = int(bp[rec["bounds"][w][0]])
        end = _signature_cursor(sysm, st, at)
        if end > first:
            bad_end.append((w, end, first))
        elif end != first:
            bad_exact.append((w, end, first))
    check("C1 every routing sample ends at or before its window's first byte",
          bool(rec["sample"]) and not bad_end,
          f"{len(rec['sample'])} samples; violations (window, sample end, first byte) {bad_end[:3]}")
    check("C1 every routing sample ends EXACTLY at its window's first byte",
          bool(rec["sample"]) and not bad_exact,
          f"{len(rec['sample'])} samples; early ends {bad_exact[:3]}")
    bad_seen = [(w, s, int(bp[rec["bounds"][w][0]])) for w, s in rec["seen"]
                if s > int(bp[rec["bounds"][w][0]])]
    # SIG.train_step IS CADENCED, so its reachability is printed rather than assumed: a run where it
    # was never asked proves nothing about its cursor, and that is a FAIL here, not a pass.
    check("C1 SIG.train_step never draws past the window being predicted",
          bool(rec["seen"]) and not bad_seen,
          f"{len(rec['seen'])} train_step calls; violations (window, seen_units, first byte) "
          f"{bad_seen[:3]}" if rec["seen"] else "UNREACHABLE: SIG.train_step was never called")
    return res


def c2(sysm):
    lm, fab, sigc = sysm.configs["LM"], sysm.configs["FAB"], sysm.configs["SIG"]
    model, pop, vocab, st = sysm.model, sysm.fabric, sysm.vocab, sysm.sig
    ids, ctx, dev = sysm.segmentation.ids, int(lm.ctx), sysm.process.device
    i = TRAIN_WINDOWS - 1
    x = torch.tensor([ids[i * ctx:(i + 1) * ctx]], device=dev)
    nov = torch.zeros(1, device=dev)

    def sig_of(ordinal):
        return sig_api.encode(sigc, st, [_sample_window(sysm, st, ordinal)])[0].to(dev).unsqueeze(0)

    def logits(xx, sg):
        with torch.no_grad():
            h = lm_api.encode(lm, model, xx)
            out = fab_api.forward(fab, pop, h=h, signature=sg, novelty=nov,
                                  step_windows=U.Windows(10 ** 9), domain_id=0, live_domains=1,
                                  training=False)
            return lm_api.decode(lm, model, out.hidden, live_vocab=int(vocab.size()),
                                 retired_ids=tuple(vocab.retired)), float((out.hidden - h).abs().max())

    sg = sig_of(i)
    base, moved = logits(x, sg)
    check("C2 the fabric is in the path (routed hidden differs from LM.encode's)", moved > 0.0,
          f"max|hidden - h| = {moved:.3e}")
    other, _ = logits(x, sig_of(max(0, i - 17)))
    d0 = float((base[:, 0] - other[:, 0]).abs().max())
    check("C2 routing reaches position 0 (a different signature moves its logits)", d0 > 0.0,
          f"max|dlogit| at position 0 = {d0:.3e}")
    g = torch.Generator().manual_seed(0)
    worst, after_min = 0.0, None
    for t in (0, 15, 63, 126):
        x2 = x.clone()
        x2[:, t + 1:] = torch.randint(0, int(vocab.size()), (1, ctx - t - 1), generator=g)
        o, _ = logits(x2, sg)
        worst = max(worst, float((base[:, :t + 1] - o[:, :t + 1]).abs().max()))
        a = float((base[:, t + 1:] - o[:, t + 1:]).abs().max())
        after_min = a if after_min is None else min(after_min, a)
    check("C2 the perturbation reaches the positions after t (the check has teeth)",
          after_min is not None and after_min > 0.0, f"min over t of max|dlogit| after t = {after_min:.3e}")
    check("C2 tokens after t leave logits at positions <= t EXACTLY unchanged", worst == 0.0,
          f"max|dlogit| at positions <= t over t in (0, 15, 63, 126) = {worst:.3e} (vs 0.0)")


class _Stop(Exception):
    pass


def c3():
    sysm = build(OPT_BATCH_WINDOWS=2)
    seen = {}

    def fl(orig):
        sig = inspect.signature(orig)

        def f(*a, **k):
            ba = sig.bind(*a, **k)
            n = len(ba.arguments["dids"])
            # DISTINCT SENTINEL IDS, because DOM assigns every opening window to one domain and a
            # check over equal ids passes whichever one the loop picks. The pre-repair loop handed
            # FAB.forward `domain_id`, which is the LAST window's id; this makes that id 100 + n.
            ba.arguments["dids"] = [101 + j for j in range(n)]
            ba.arguments["domain_id"] = 100 + n
            seen["n"] = n
            return orig(*ba.args, **ba.kwargs)
        return f

    def fw(orig):
        def f(*a, **k):
            seen["domain_id"] = int(k["domain_id"])
            raise _Stop()
        return f

    with _Patch(loop, "_flush", fl), _Patch(loop.fab_api, "forward", fw):
        try:
            loop.run(sysm, max_windows=4, progress=False)
        except _Stop:
            pass
    got = seen.get("domain_id")
    check("C3 at OPT_BATCH_WINDOWS=2 FAB.forward bans on the FIRST window's domain",
          seen.get("n") == 2 and got == 101,
          f"flush of {seen.get('n')} windows, dids [101, 102]: FAB.forward got domain_id={got} "
          f"(101 = first window, causal; 102 = last, whose sample covers row 0's targets)")


def c4():
    """Row 0 of a 2-row TRAINING pass must not move when only row 1 changes. Three arms: the shipped
    depth (spawn is the channel there), FAB_DEPTH0=0 FAB_SPAWN=0 (grounding between hops) and
    FAB_DEPTH0=0 (both)."""
    import copy
    for arm in ({}, {"FAB_DEPTH0": 0, "FAB_SPAWN": 0}, {"FAB_DEPTH0": 0}):
        sysm = build(OPT_BATCH_WINDOWS=2, **arm)
        loop.run(sysm, max_windows=TRAIN_WINDOWS, progress=False)
        pop0 = sysm.fabric
        # THE IDENTITY CACHE CARRIES THE LAST PASS'S GRAPH, which deepcopy refuses; it is rebuilt
        # by the next training pass, so a detached copy is the same state.
        for c in type(pop0).__mro__:
            for s in getattr(c, "__slots__", ()):
                v = getattr(pop0, s, None)
                if torch.is_tensor(v) and v.grad_fn is not None:
                    setattr(pop0, s, v.detach())
        lm, fab, sigc = sysm.configs["LM"], sysm.configs["FAB"], sysm.configs["SIG"]
        ids, ctx, dev = sysm.segmentation.ids, int(lm.ctx), sysm.process.device
        i = TRAIN_WINDOWS - 2

        def xy(j):
            return (torch.tensor([ids[j * ctx:(j + 1) * ctx]], device=dev),
                    torch.tensor([ids[j * ctx + 1:(j + 1) * ctx + 1]], device=dev))

        def sg(o):
            return sig_api.encode(sigc, sysm.sig, [_sample_window(sysm, sysm.sig, o)])[0] \
                .to(dev).unsqueeze(0)

        x0, y0 = xy(i)
        x1, y1 = xy(i + 1)
        xa, ya = xy(max(0, i - 11))
        step = [10 ** 9]

        def row0(x1_, y1_, s1):
            pop = copy.deepcopy(pop0)
            step[0] += 1
            with torch.no_grad():
                h = lm_api.encode(lm, sysm.model, torch.cat([x0, x1_]))
                out = fab_api.forward(fab, pop, h=h, signature=torch.cat([sg(i), s1]),
                                      novelty=torch.zeros(2, device=dev), head=loop._c_head(sysm),
                                      targets=torch.cat([y0, y1_]),
                                      step_windows=U.Windows(step[0]), domain_id=0,
                                      live_domains=1, training=True)
                lg = out.logits if out.logits is not None else lm_api.decode(
                    lm, sysm.model, out.hidden, live_vocab=int(sysm.vocab.size()),
                    retired_ids=tuple(sysm.vocab.retired))
            return lg

        base = row0(x1, y1, sg(i + 1))
        rep = float((base - row0(x1, y1, sg(i + 1))).abs().max())
        other = row0(xa, ya, sg(max(0, i - 11)))
        d0 = float((base[0] - other[0]).abs().max())
        d1 = float((base[1] - other[1]).abs().max())
        name = ", ".join(f"{k}={v}" for k, v in arm.items()) or "shipped depth"
        check(f"C4 [{name}] row 0's training-pass logits ignore row 1's signature and tokens",
              rep == 0.0 and d1 > 0.0 and d0 == 0.0,
              f"repeat {rep:.3e} (vs 0.0); row 1 moved {d1:.3e} (teeth, > 0); "
              f"row 0 moved {d0:.3e} (vs 0.0)")


def main():
    sysm = build()
    c1_and_train(sysm)
    c2(sysm)
    c3()
    c4()
    print(f"\n{len(FAILS)} FAIL(s)" + (": " + ", ".join(FAILS) if FAILS else ""))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
