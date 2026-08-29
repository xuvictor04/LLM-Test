#!/usr/bin/env python3
"""P0 — freeze the oracle, BEFORE anything is deleted.

WHY THIS RUNS FIRST. rm-predict is about to be frozen and rm-predict-DC rebuilt from a specification. The
knowledge in the old tree is 37% comments, and the part that is not comments is the exact behaviour of a
dozen small decision rules -- the cull gate, the BWT sign convention, the curve verdict cascade, the phase
schedule, the prefix-widening rules. Each of those has been the site of a defect the project paid to find:
RETENTION had the subtraction inverted on the line the continual-learning claim rests on; the curve verdict
read its own sign backwards; cull_gate_open's docstring records three mechanisms that went silently
unreachable behind it.

A rebuilt tree needs a KNOWN-ANSWER TABLE for each, captured from the shipped code rather than from anyone's
recollection of it. That is what this produces. It is the oracle the new implementations are tested against,
and the plan's `tests/test_derive.py`.

The functions are exec'd FROM THE ACTUAL SOURCE TEXT -- not imported, because importing self_organize.py
runs the whole system, and not re-typed, because a re-typed copy can pass happily while the real code is
wrong (cap_test.py records exactly that failure).

    python3 .rework/capture_oracle.py            # writes .rework/oracle/*.json
"""
import ast, json, itertools, os, sys, textwrap

SRC_PATH = "self_organize.py"
SRC = open(SRC_PATH).read()
TREE = ast.parse(SRC)


def lift(name):
    """Return the source text of a top-level function, exactly as shipped."""
    for node in TREE.body:
        if isinstance(node, (ast.FunctionDef,)) and node.name == name:
            return ast.get_source_segment(SRC, node)
    raise KeyError(f"{name} is not a module-level function in {SRC_PATH}")


# Module constants the lifted functions close over. Taken from the source, not invented: each is the
# shipped default, and the capture records which value it ran at so a later disagreement is attributable.
CONSTS = {}
for node in TREE.body:
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        nm = node.targets[0].id
        if nm.isupper():
            try:
                CONSTS[nm] = ast.literal_eval(node.value)
            except Exception:
                pass


def load(*names, extra=None):
    ns = {"__builtins__": __builtins__}
    ns.update({k: v for k, v in CONSTS.items() if isinstance(v, (int, float, str, bool))})
    if extra: ns.update(extra)
    for n in names:
        exec(compile(lift(n), f"<{SRC_PATH}:{n}>", "exec"), ns)
    return ns


def grid(fn, cases, name, note):
    rows = []
    for args in cases:
        try:
            out = fn(*args)
        except Exception as e:
            out = {"__raised__": type(e).__name__, "msg": str(e)[:200]}
        rows.append({"in": list(args), "out": out})
    return {"function": name, "note": note, "source_file": SRC_PATH, "cases": rows}


OUT = ".rework/oracle"
os.makedirs(OUT, exist_ok=True)
captured = {}


# ---- cull_gate_open: the gate three mechanisms live behind -------------------------------------------
ns = load("cull_gate_open")
captured["cull_gate_open"] = grid(
    ns["cull_gate_open"],
    [(n, c, p) for n in (0, 1, 2, 3, 10, 523, 1024, 2048, 2090)
               for c in (4, 1024, 4096, 8192)
               for p in (0.0, 0.25, 0.45, 0.5, 0.75, 1.0)],
    "cull_gate_open",
    "n_live <= 2 is a floor, not a pressure test. The utilization cull, the utilization spare and "
    "FAB_RESCUE all live behind this; its docstring records that all three went silently unreachable.")

# ---- bwt_of / forgetting_of: the sign convention the CL claim rests on -------------------------------
ns = load("bwt_of", "forgetting_of")
PAIRS = [
    ({"eng": 2.125}, {"eng": 2.125}),
    ({"eng": 2.273}, {"eng": 2.125}),          # worse after -> positive = forgetting
    ({"eng": 2.000}, {"eng": 2.125}),          # better after -> negative
    ({"eng": 2.1, "py": 5.0}, {"eng": 2.0}),   # py is new: no baseline, must not enter
    ({"eng": (2.273, 0.09)}, {"eng": (2.125, 0.05)}),   # tuple form (mean, err)
    ({}, {"eng": 2.0}),
    ({"eng": 2.0}, {}),
]
captured["bwt_of"] = grid(ns["bwt_of"], PAIRS, "bwt_of",
    "POSITIVE = WORSE = FORGETTING, on a lower-is-better metric. The subtraction here was inverted once, "
    "on the single line the continual-learning claim rests on. NOTE: it raises TypeError on the (mean, err) "
    "tuple form that holdout values are otherwise carried in. Not reachable today -- both call sites unwrap "
    "with _ms(...)[0] first -- so this is a contract honoured by CONVENTION AT THE CALL SITE rather than by "
    "the function. The rebuild's Reading type removes the convention: value and error are named fields, so "
    "no caller has to remember to unwrap.")
captured["forgetting_of"] = grid(ns["forgetting_of"], PAIRS, "forgetting_of",
    "F compares a domain to its BEST ever, not to its previous value; differs from BWT exactly when a "
    "domain peaked earlier than the last probe.")

# ---- lift_to: the earned-capacity step ---------------------------------------------------------------
ns = load("lift_to")
captured["lift_to"] = grid(
    ns["lift_to"],
    [(c, f, fl) for c in (0, 1, 100, 160, 256, 2048, 3000)
                for f in (0.0, 0.05, 0.10, 0.25)
                for fl in (0, 1, 16, 64)],
    "lift_to", "One earned lift must mean the same thing at every cap size (cap_test's subject).")

# ---- curve_verdict: the cascade that printed two contradictory verdicts ------------------------------
ns = load("curve_verdict")
captured["curve_verdict"] = grid(
    ns["curve_verdict"],
    [(r, t, k) for r in (-1.0, -0.1, 0.0, 0.1, 0.5, 0.6, 4.01)
               for t in (-0.5, -0.05, 0.0, 0.05, 0.5)
               for k in (0.0, 0.1, 1.0)],
    "curve_verdict",
    "Read its own sign backwards once, and the verdict block below it prints an independent second verdict "
    "on the next line -- the reason a run could report BLEW UP and 'still improving' together.")

# ---- blowup_stale: the alarm that fired on 4 of 4 healthy runs then never again ----------------------
ns = load("blowup_stale")
captured["blowup_stale"] = grid(
    ns["blowup_stale"],
    [(tuple(r), b, s) for r in ([2.0, 2.0, 2.0], [2.0, 2.1, 2.2], [2.0, 3.0, 4.0], [4.0, 3.0, 2.0])
                      for b in (1.9, 2.0, 2.5)
                      for s in (0, 100, 10000)],
    "blowup_stale",
    "The divergence alarm. Fired on 4 of 4 healthy runs, then could never fire again -- both directions of "
    "the same threshold being wrong.")

# ---- pin_tick: the capacity valve's clock, which counted the wrong unit ------------------------------
ns = load("pin_tick")
captured["pin_tick"] = grid(
    ns["pin_tick"],
    [(h, p, d) for h in (True, False) for p in (0, 1, 5, 400) for d in (0, 1, 16, 100)],
    "pin_tick",
    "Counted FLUSHES while its threshold was declared in STEPS -- 16x slow at BATCH_W=16. The unit-mismatch "
    "class in its purest form.")

# ---- _phases: the continual-learning schedule shape --------------------------------------------------
# _phases reads _i("PHASES") and _i("PHASE_W") from INSIDE its body -- a pure-looking generator that
# reaches into the environment. That is the ownership violation the rebuild forbids (L2): the schedule
# shape is data, and its parameters should arrive as arguments. Captured with an explicit reader so the
# defaults are recorded rather than ambient.
ns = load("_phases", extra={"_i": lambda k, d: {"PHASES": 4, "PHASE_W": None}.get(k, d) or d})
captured["_phases"] = grid(
    ns["_phases"],
    [(n, p, w) for n in (1, 2, 3, 4, 5) for p in (None, 2, 4, 8) for w in (None, 1, 2)],
    "_phases",
    "PHASE_SCHED for 2 corpora is [[0],[0],[1],[1]] -- a straight 50/50 that REHEARSES the old area every "
    "epoch. PURE_ADD=1 replaces it with 1|1|1|1. The two disagreed 10x on the same toy.")

for name, blob in captured.items():
    with open(f"{OUT}/{name}.json", "w") as fh:
        json.dump(blob, fh, indent=1)

print(f"captured {len(captured)} decision rules from {SRC_PATH} @ {os.popen('git rev-parse --short HEAD').read().strip()}")
for n, b in captured.items():
    raised = sum(1 for c in b["cases"] if isinstance(c["out"], dict) and "__raised__" in c["out"])
    print(f"  {n:<18} {len(b['cases']):>4} cases" + (f"  ({raised} raised)" if raised else ""))
