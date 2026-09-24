"""TOK's cadence reporting, DOM's retok / rekey / prior, and CAP's clamp gate, driven through the real
loop (compose -> loop.run -> _report) on short runs.

    python3 tests/test_tok_dom_cap.py        # exit 0 = every check passed

WHY IT EXISTS (docs/04_CONTRACT.md Q-DOM-2, Q-DOM-3, Q-TOK-14, Q-CAP-4, 2026-09-24). Each of these was
measured wrong, or not delivered at all, and nothing in tests/ could see it:

  D1  DOM.on_retokenize HAD NO CALL SITE. An epoch roll re-segmented at a grown vocabulary and
      part.n_retok_events stayed ABSENT; it is now an E row, called when the match table moved.
  D2  DOM.rekey RAN BEFORE observe AND ON THE BIGRAM ARM. It must follow DOM.observe in the same
      window and never run at SIG_MODE=bigram.
  D3  THE R STAGE ASKED DOM.prior FOR did=0 ALONE. It is asked for every live domain.
  T1  A PENDING RETOK WAS A FLAG, so four fires read as one in tok.due_dropped and one per roll in
      tok.retok_satisfied_by_roll. The two now sum to tok.retok_deferred.
  T2  TOK SEEDED ITS CADENCE COUNTERS ON ARMS THAT CANNOT MINT (fixed, bytes), and tok.due_merged at
      batch_windows=1. Both are ABSENT there now.
  T3  THE GATED REPORT COUNTED DUES, NOT CALLS, and printed a static "(TOK_PROBATION_USES=0 ...)".
  C1  CAP.counters' cap.clamp said "an armed arm has room" at CAP_TARGETS=off; an untargeted arm's
      origin read as the sentinel's.
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
from spine import compose as _compose                              # noqa: E402
from domains import api as dom_api                                 # noqa: E402
from tok import api as tok_api                                     # noqa: E402
from capacity import api as cap_api                                # noqa: E402

FAILS = []
BASE = {"DATA_STREAM_BYTES": "120000"}


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
    return _compose.compose(environ=e)


class _Log:
    """Wraps module-level entry points so a run's call ORDER can be read back. Restored on exit."""

    def __init__(self, *targets):
        self.targets, self.saved, self.log = targets, [], []

    def __enter__(self):
        for mod, name in self.targets:
            orig = getattr(mod, name)
            self.saved.append((mod, name, orig))

            def f(*a, _o=orig, _n=name, **k):
                self.log.append(_n)
                return _o(*a, **k)
            setattr(mod, name, f)
        return self

    def __exit__(self, *exc):
        for mod, name, orig in self.saved:
            setattr(mod, name, orig)
        return False


def gated_line(res, name):
    return next((g for g in res.gated if g.startswith(name + ":")), "")


# ---- D1 + T1: a two-epoch run that mints before its roll and raises retoks ----------------------
sysm = build(DATA_STREAM_BYTES="40000", RUN_EPOCHS="2", DATA_RESAMPLE="1", TOK_RETOK_EVERY="10")
with _Log((dom_api, "on_retokenize")) as spy:
    res = loop.run(sysm, progress=False)
pc, tc = sysm.partition.counters, sysm.vocab.counters
check("D1 the roll that re-segmented at a moved table delivered DOM.on_retokenize once",
      spy.log.count("on_retokenize") == 1 and pc.get("part.n_retok_events") == 1,
      f"calls {spy.log.count('on_retokenize')}, part.n_retok_events {pc.get('part.n_retok_events')}")
check("D1 and DOM_TOKC_DECAY was applied (part.n_retok_decays 1)",
      pc.get("part.n_retok_decays") == 1, str(pc.get("part.n_retok_decays")))
check("D1 DOM.on_retokenize is a LOOP_ORDER E row and in _CALLS['E']",
      any(r[:3] == ("E", "DOM", "on_retokenize") for r in _compose.LOOP_ORDER)
      and "DOM.on_retokenize" in loop._CALLS["E"])
_def, _sat, _drop = (int(tc.get(k, 0)) for k in
                     ("tok.retok_deferred", "tok.retok_satisfied_by_roll", "tok.due_dropped"))
check("T1 every deferred retok is satisfied by the roll or dropped at the end, one each",
      _def > 2 and _sat > 1 and _sat + _drop == _def, f"deferred {_def} = {_sat} + {_drop}?")
check("D3 the R stage summarises DOM.prior over every live domain",
      "DOM.prior(live)" in res.report and "DOM.prior(0)" not in res.report
      and res.report["DOM.prior(live)"]["n_live"] == len(res.report["DOM.census"]["live"]),
      str(res.report.get("DOM.prior(live)")))
check("T3 TOK's gates reach the report", "TOK(vocab.gates)" in res.report)

# ---- D1: a roll at an UNCHANGED table does not decay, and says so -------------------------------
sysm = build(DATA_STREAM_BYTES="40000", RUN_EPOCHS="2", DATA_RESAMPLE="1", TOK_GROW_EVERY="0")
res = loop.run(sysm, progress=False)
check("D1 a roll whose match table did not move leaves DOM untold (n_retok_events ABSENT)",
      "part.n_retok_events" not in sysm.partition.counters
      and any("DOM.on_retokenize is NOT told" in w for w in res.warnings))

# ---- D2: DOM.rekey follows DOM.observe, and never runs on the bigram arm ------------------------
for mode in ("learned", "bigram"):
    sysm = build(SIG_MODE=mode, MEM_REKEY_EVERY="20")
    with _Log((dom_api, "observe"), (dom_api, "rekey")) as spy:
        loop.run(sysm, max_windows=45, progress=False)
    after = [spy.log[i - 1] if i else None for i, n in enumerate(spy.log) if n == "rekey"]
    if mode == "learned":
        check("D2 every DOM.rekey is immediately preceded by that window's DOM.observe",
              len(after) >= 2 and all(p == "observe" for p in after), str(after))
    else:
        check("D2 SIG_MODE=bigram asks no rekey: none called, part.n_rekey_passes ABSENT",
              not after and "part.n_rekey_passes" not in sysm.partition.counters,
              f"{len(after)} call(s)")

# ---- T2 + T3: the fixed arm, the batch arm, and the gated lines ---------------------------------
sysm = build(TOK_MODE="fixed", TOK_GROW_EVERY="5", TOK_FREEZE_AT="10", TOK_PROBATION_USES="3")
res = loop.run(sysm, max_windows=20, progress=False)
tc = sysm.vocab.counters
_off = [k for k in ("tok.tally", "tok.due_mint", "tok.due_retok", "tok.due_probation",
                    "tok.mint_frozen_at", "tok.due_merged", "tok.due_dropped", "tok.mint_bursts",
                    "tok.probation_calls") if k in tc]
check("T2 TOK_MODE=fixed seeds none of the online arm's cadence counters", not _off, str(_off))
check("T2 TOK_MODE=fixed reports TOK.mint_burst and judge_probation UNREACHABLE",
      "UNREACHABLE" in gated_line(res, "TOK.mint_burst")
      and "UNREACHABLE" in gated_line(res, "TOK.judge_probation"))
check("T3 no gated line states a lever value it cannot know",
      not any("USES=0 makes it" in g for g in res.gated))

sysm = build()
loop.run(sysm, max_windows=5, progress=False)
check("T2 tok.due_merged is ABSENT at the shipped OPT_BATCH_WINDOWS=1",
      "tok.due_merged" not in sysm.vocab.counters)

sysm = build(OPT_BATCH_WINDOWS="4", TOK_GROW_EVERY="2")
with _Log((tok_api, "mint_burst")) as spy:
    res = loop.run(sysm, max_windows=40, progress=False)
tc = sysm.vocab.counters
_calls = spy.log.count("mint_burst")
check("T3 tok.mint_bursts counts calls, not the windows that raised Due.mint",
      tc.get("tok.mint_bursts") == _calls and tc.get("tok.due_mint", 0) > _calls,
      f"mint_bursts {tc.get('tok.mint_bursts')}, calls {_calls}, due_mint {tc.get('tok.due_mint')}")
check("T3 the gated line prints the call count",
      gated_line(res, "TOK.mint_burst").startswith(f"TOK.mint_burst: fired {_calls} time(s)"),
      gated_line(res, "TOK.mint_burst")[:80])
check("T2 tok.due_merged is seeded when a flush holds more than one window",
      "tok.due_merged" in tc, str(tc.get("tok.due_merged")))

# ---- C1: the clamp gate and the untargeted arm's origin -----------------------------------------
for targets in ("off", "vocab"):
    sysm = build(CAP_TARGETS=targets)
    c = cap_api.counters(sysm.configs["CAP"], sysm.valve)
    b = next(g for g in sysm.valve.gates if g.name == "cap.clamp")
    check(f"C1 CAP_TARGETS={targets}: the R-stage cap.clamp agrees with the startup gate",
          c["cap.clamp"].reachable == b.reachable and not b.reachable
          and "An armed arm has room" not in c["cap.clamp"].reason, c["cap.clamp"].reason[:90])
    if targets == "vocab":
        check("C1 an arm CAP_TARGETS does not name reads 'off for this arm'",
              str(c["cap.origin_experts"]).startswith("off for this arm"),
              str(c["cap.origin_experts"]))

print(f"{len(FAILS)} FAIL(s)")
sys.exit(1 if FAILS else 0)
