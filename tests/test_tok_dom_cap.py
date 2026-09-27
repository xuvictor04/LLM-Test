"""TOK's cadence reporting, DOM's retok / rekey / prior, and CAP's clamp gate, driven through the real
loop (compose -> loop.run -> _report) on short runs.

    python3 tests/test_tok_dom_cap.py        # exit 0 = every check passed

WHY IT EXISTS (docs/04_CONTRACT.md Q-DOM-2, Q-DOM-3, Q-TOK-14, Q-CAP-4, 2026-09-24). Each of these was
measured wrong, or not delivered at all, and nothing in tests/ could see it:

  D1  DOM.on_retokenize HAD NO CALL SITE. An epoch roll re-segmented at a grown vocabulary and
      part.n_retok_events stayed ABSENT; it is now an E row, called when the match table moved --
      and, since 03b S0b (2026-09-26), an X row: the mid-epoch act delivers it too, once per
      re-segmentation at a moved table.
  D2  DOM.rekey RAN BEFORE observe AND ON THE BIGRAM ARM. It must follow DOM.observe in the same
      window and never run at SIG_MODE=bigram.
  D3  THE R STAGE ASKED DOM.prior FOR did=0 ALONE. It is asked for every live domain.
  T1  A PENDING RETOK WAS A FLAG, so four fires read as one in tok.due_dropped and one per roll in
      tok.retok_satisfied_by_roll. SINCE 03b S0b NOTHING IS DEFERRED: every retok request is either
      performed by the mid-epoch act (tok.retok_mid_epoch) or refused as a no-op because the table
      had not moved (loop.acts_noop), and none is dropped (tok.due_dropped ABSENT or 0).
  T2  TOK SEEDED ITS CADENCE COUNTERS ON ARMS THAT CANNOT MINT (fixed, bytes), and tok.due_merged at
      batch_windows=1. Both are ABSENT there now.
  T3  THE GATED REPORT COUNTED DUES, NOT CALLS, and printed a static "(TOK_PROBATION_USES=0 ...)".
  T4  THE MINT WAIT (2026-09-26, Q-RUN-17) IS CLOSED BY EVERY RE-SEGMENTATION, acts and the roll
      alike, exactly once per id: on the two-epoch run tok.mint_waited plus the stranded count is
      tok.mint. It is ABSENT where nothing can be minted (TOK_GROW_EVERY=0), and T2's fixed arm
      carries neither it nor tok.bpt_tail.
  T5  PER-FLUSH BYTES ABOVE BATCH 1 (Q-RUN-17): at OPT_BATCH_WINDOWS=4 RunResult.flush_bytes has one
      entry per loss and sums to loop.bytes_scored.
  C1  CAP.counters' cap.clamp said "an armed arm has room" at CAP_TARGETS=off; an untargeted arm's
      origin read as the sentinel's.
  C2  THE SIX GROUNDS WERE NOT ON THE LINE (Proposal 05 §8 1.6, register CONTRACT-Q-CAP-1): each
      arm's clause described its ground in words. One configuration per ground reaches all six, and
      each arm now prints '(arm, ground kind)' beside the UNREACHABLE verdict, which is unchanged.
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
_books = res.report.get("LOOP(flush books)") or {}
_acts = int(_books.get("loop.acts", 0)) if isinstance(_books, dict) else 0
_calls = spy.log.count("on_retokenize")
check("D1 every re-segmentation at a moved table (acts and the roll) delivered DOM.on_retokenize "
      "exactly once",
      _calls >= 2 and _acts >= 1 and pc.get("part.n_retok_events") == _calls,
      f"calls {_calls}, acts {_acts}, part.n_retok_events {pc.get('part.n_retok_events')}")
check("D1 and DOM_TOKC_DECAY was applied at each of them",
      pc.get("part.n_retok_decays") == _calls, f"{pc.get('part.n_retok_decays')} vs {_calls}")
check("D1 DOM.on_retokenize is a LOOP_ORDER E row and X row, and in _CALLS['E'] and ['X']",
      any(r[:3] == ("E", "DOM", "on_retokenize") for r in _compose.LOOP_ORDER)
      and any(r[:3] == ("X", "DOM", "on_retokenize") for r in _compose.LOOP_ORDER)
      and "DOM.on_retokenize" in loop._CALLS["E"] and "DOM.on_retokenize" in loop._CALLS["X"])
_mid, _noop, _drop = (int(tc.get(k, 0)) for k in
                      ("tok.retok_mid_epoch", "tok.retok_noop", "tok.due_dropped"))
check("T1 retoks are performed mid-epoch or refused as no-ops; none deferred, none dropped",
      _mid >= 1 and _mid == _acts and _drop == 0 and "tok.retok_deferred" not in tc,
      f"mid_epoch {_mid}, acts {_acts}, noop {_noop}, dropped {_drop}, "
      f"deferred {tc.get('tok.retok_deferred', 'ABSENT')}")
_strand = next((int(w.split()[1]) for w in res.warnings
                if "minted AFTER THE LAST RE-SEGMENTATION" in w), 0)
check("T4 acts and the roll close every mint wait exactly once: tok.mint_waited + the stranded "
      "count = tok.mint, both wait keys present",
      "tok.mint_wait_windows" in tc and "tok.mint_waited" in tc and int(tc.get("tok.mint", 0)) > 0
      and int(tc["tok.mint_waited"]) + _strand == int(tc["tok.mint"]),
      f"waited {tc.get('tok.mint_waited', 'ABSENT')} + stranded {_strand} vs mint "
      f"{tc.get('tok.mint')}; windows {tc.get('tok.mint_wait_windows', 'ABSENT')}")
check("D3 the R stage summarises DOM.prior over every live domain",
      "DOM.prior(live)" in res.report and "DOM.prior(0)" not in res.report
      and res.report["DOM.prior(live)"]["n_live"] == len(res.report["DOM.census"]["live"]),
      str(res.report.get("DOM.prior(live)")))
check("T3 TOK's gates reach the report", "TOK(vocab.gates)" in res.report)

# ---- D1: a roll at an UNCHANGED table does not decay, and says so -------------------------------
sysm = build(DATA_STREAM_BYTES="40000", RUN_EPOCHS="2", DATA_RESAMPLE="1", TOK_GROW_EVERY="0")
res = loop.run(sysm, progress=False)
# n_retok_events IS PRESENT-AND-0 THERE SINCE 2026-09-24 (the root seeds it at every roll): the
# delivery was armed and did not fire. It was ABSENT -- "unreachable" -- on an arm that had rolled.
check("D1 a roll whose match table did not move leaves DOM untold (n_retok_events present, 0)",
      sysm.partition.counters.get("part.n_retok_events", "ABSENT") == 0
      and "part.n_retok_decays" not in sysm.partition.counters
      and any("DOM.on_retokenize is NOT told" in w for w in res.warnings),
      str({k: sysm.partition.counters.get(k, "ABSENT")
           for k in ("part.n_retok_events", "part.n_retok_decays")}))
# AND TOK_GROW_EVERY=0 IS A DISARMED MINT CADENCE (2026-09-24): its keys are ABSENT, so the gated
# row reads UNREACHABLE and does not tell the operator to lengthen a run that cannot mint.
check("T2 TOK_GROW_EVERY=0 seeds neither tok.due_mint nor tok.mint_bursts",
      not any(k in sysm.vocab.counters for k in ("tok.due_mint", "tok.mint_bursts")),
      str({k: sysm.vocab.counters.get(k, "ABSENT") for k in ("tok.due_mint", "tok.mint_bursts")}))
check("T4 TOK_GROW_EVERY=0 arms no mint wait: tok.mint_wait_windows and tok.mint_waited ABSENT "
      "although the roll re-segments",
      not any(k in sysm.vocab.counters for k in ("tok.mint_wait_windows", "tok.mint_waited")),
      str({k: sysm.vocab.counters.get(k, "ABSENT")
           for k in ("tok.mint_wait_windows", "tok.mint_waited")}))

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
                    "tok.probation_calls", "tok.mint_wait_windows", "tok.mint_waited",
                    "tok.bpt_tail") if k in tc]
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
_b4 = res.report.get("LOOP(flush books)") or {}
check("T5 RunResult.flush_bytes at OPT_BATCH_WINDOWS=4: one entry per loss, summing to "
      "loop.bytes_scored (never_backward 0)",
      len(res.flush_bytes) == len(res.loss_curve) > 0 and res.never_backward == 0
      and sum(res.flush_bytes) == _b4.get("loop.bytes_scored"),
      f"{len(res.flush_bytes)} entries, {len(res.loss_curve)} losses, sum {sum(res.flush_bytes)} "
      f"vs {_b4.get('loop.bytes_scored')}, never_backward {res.never_backward}")

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

# ---- C2: every arm prints its ground by name beside the cap.clamp verdict -----------------------
# REPORTING ONLY (register CONTRACT-Q-CAP-1): the verdict stays UNREACHABLE on all six grounds -- the
# classification is the owner's (O19) -- and what is pinned is that each arm's ground is ON THE LINE,
# as '(arm, ground kind)', at the R stage and at startup. The token is arm-qualified because the bare
# word 'inert' is already in the UNREACHABLE boilerplate. One lever configuration per ground, no loop.
from spine import assemble                                         # noqa: E402

_GROUNDS = {
    "unarmed": {"CAP_TARGETS": "off"},
    "nonpositive": {"CAP_TARGETS": "experts", "CAP_FAB_START": "-5"},
    "at_ceiling": {"CAP_TARGETS": "experts", "CAP_FAB_START": "5000"},
    "never_pins": {"CAP_TARGETS": "experts", "CAP_FAB_START": "3000"},
    "inert": {"CAP_TARGETS": "experts", "CAP_FAB_START": "5", "CAP_LIFT": "0.01", "CAP_LIFT_MIN": "0"},
    "refused_unmasked": {"CAP_TARGETS": "vocab", "CAP_VOCAB_START": "1000", "LM_MASK_DEAD_ROWS": "0"},
}
_kinds_seen, _inert_facts = set(), None
for _ground, _env in _GROUNDS.items():
    _lever._reopen_assembly()
    rng.reset_issued()
    _cfgs, _w, _ = assemble.build(dict(_env))
    _v = cap_api.new_valve(_cfgs["CAP"])
    _g = cap_api.counters(_cfgs["CAP"], _v)["cap.clamp"]
    _b = next(g for g in _v.gates if g.name == "cap.clamp")
    _facts = [(a, k) for a, k, _f in (_v.clamp_dead_facts or ())]
    _kinds_seen.update(k for _a, k in _facts)
    if _ground == "inert":
        _inert_facts = _v.clamp_dead_facts
    _missing = [f"({a}, ground {k})" for a, k in _facts
                if f"({a}, ground {k})" not in _g.reason or f"({a}, ground {k})" not in _b.reason]
    check(f"C2 {_ground}: cap.clamp stays UNREACHABLE and every arm prints its ground by name, at "
          f"the R stage and at startup",
          not _g.reachable and not _b.reachable and (_ground in {k for _a, k in _facts})
          and not _missing,
          f"facts {_facts}; missing {_missing}")
check("C2 the six configurations reach exactly the closed set capacity/api.py::_CLAMP_BLOCKED_KINDS "
      "(a seventh ground fails here until it has a configuration and a clause)",
      _kinds_seen == set(cap_api._CLAMP_BLOCKED_KINDS),
      f"seen {sorted(_kinds_seen)}; closed set {sorted(cap_api._CLAMP_BLOCKED_KINDS)}")
# THE 'agrees' BRANCH QUOTES THE GROUNDS TOO: two lifts taken, none clamped, on an inert arm.
_agree = cap_api._clamp_gate("experts 5/ceiling 4096", 2, 0, dead_facts=_inert_facts)
check("C2 the ledger-agrees branch (lifts taken on an inert arm) prints the ground by name",
      _inert_facts is not None and "(expert, ground inert)" in _agree.reason
      and "AGREES" in _agree.reason, _agree.reason[:120])

print(f"{len(FAILS)} FAIL(s)")
sys.exit(1 if FAILS else 0)
