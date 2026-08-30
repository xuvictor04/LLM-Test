"""The coupling table, exercised: what a compute may name, and what the declared rows actually build.

    python3 tests/test_couplings.py          # PASS/FAIL per check with counts; non-zero exit on any FAIL

WHY THIS FILE IS NOT PART OF tests/test_ownership.py. That file is the STATIC half -- it walks src/ with
`ast` and does not execute it, with the two named exceptions it lists. Everything here RUNS: it builds
couplings, it runs their compute functions, it assembles a set of Configs end to end. Folding a live
probe into a file whose stated method is "parse, never execute" would make that sentence false, and the
sentence is what tells a reader what a green tick there means.

THE TWO THINGS PROVED HERE, and each of them was unproved until this file existed:

  1. THE COMPUTE ALLOWLIST REFUSES THE DEMONSTRATED ESCAPE. The reviewer's finding, verbatim: mechanism 2
     in spine/assemble.py "restricts only the argument passed to a coupling compute function, not its
     CLOSURE. Any helper called from inside compute reads whatever it likes." Verified by changing one
     row to `compute=lambda r: max(64, 2*int(r["FAB"].slots)) + _peek()`, where `_peek()` did
     `from fabric.levers import FabricLevers; return int(FabricLevers.from_env().manage_every)` -- all
     seven ownership checks stayed green, MEM.d_source_slots moved with FAB_MANAGE_EVERY, and
     affects("FAB_MANAGE_EVERY") stayed {"FAB"}. C2 below is that escape and eleven of its variants,
     each of which must be REFUSED at Coupling construction. C1 is the other direction: the shipped rows
     and four legitimate shapes must still be ADMITTED, so the check is not "refuse everything", which
     would pass C2 perfectly.

  2. THE TEN COUPLINGS ACTUALLY RESOLVE. Every package in the table is unregistered on today's tree, so
     `build()` deferred every row and printed a warning per row -- which meant nothing in the repository
     had ever RUN a compute. The name check would be equally green over rows that raise ZeroDivision
     the day a package appears. C4 assembles stand-in packages, builds the real table against them, and
     compares every landed value against a known-answer table written out by hand. It is the first thing
     in the tree that executes the wiring at all.

WHY THE STAND-IN PACKAGES ARE NOT LeverSet SUBCLASSES. Declaring `class Fab(LeverSet): PREFIX = "FAB"`
here would be correct in every visible way and would quietly claim the name "FAB" in the process-wide
registry, which `registry.register` guards precisely because one prefix may have one owner. The day
P3 lands the real fabric package, any runner that imports both -- a single pytest process, say -- gets
`LeverError: PREFIX 'FAB' is claimed by both ...` from a TEST, which is a confusing failure in the wrong
file and a name a test has no business spending. The doubles below are therefore plain objects carrying
the two things `build()` and `_view()` actually use, `PREFIX` and `from_env`, and they register nothing.

WHAT THIS FILE CANNOT CATCH:
  * whether the values are the RIGHT values. C4 is a known-answer table: it pins what the table computes
    today against numbers written by hand from the shipped formulas, so a formula that changes has to be
    changed here too, on purpose. It cannot tell a correct formula from a plausible one -- the reason
    column and tests/test_derive.py's oracle replay stand behind that.
  * the whole CANNOT CATCH list in spine.assemble._check_names: what an allowlisted name does, rebinding
    after import, and every coupling that travels through shared state, RNG draw order or the data. That
    last family is L3's (tests/test_lever_isolation.py), against the test_determinism noise floor.
  * a coupling nobody declared. Both halves of that are tests/test_ownership.py's O4.
"""
import builtins
import functools
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from spine import assemble                                              # noqa: E402
from spine import derive                                                # noqa: E402
from spine.lever import Config                                          # noqa: E402
from spine.units import Flushes, Steps                                  # noqa: E402
from spine.wire import WireError                                        # noqa: E402

MAX_SHOWN = 12


def _report(tag, title, ok, detail, findings, vacuous=False):
    """One check's verdict. The size of the examined population is always printed: a green tick over an
    empty set is this project's most repeated defect (60 of the survey's 475 records are guards whose
    condition cannot be satisfied), and the only honest way to report one is to say how big it was."""
    mark = "PASS" if ok else "FAIL"
    note = "  (VACUOUS: 0 examined)" if vacuous else ""
    print(f"{mark}  {tag}  {title}{note}")
    print(f"      {detail}")
    for f in findings[:MAX_SHOWN]:
        print(f"      - {f}")
    if len(findings) > MAX_SHOWN:
        print(f"      ... and {len(findings) - MAX_SHOWN} more")
    return 0 if ok else 1


# ==================================================================================================
# The escape helpers. Module-level on purpose: this is the shape the review used.
# ==================================================================================================
#
# `_peek` stands in for the reviewer's helper. It does not import fabric -- there is no fabric package
# yet -- but the mechanism under test is the NAME, not the body: the check refuses `_peek` because a
# compute may not resolve it at all, and it would refuse it identically if the body were the original
# `from fabric.levers import FabricLevers; return int(FabricLevers.from_env().manage_every)`. Making the
# body harmless is deliberate: a test that has to be able to read another package's levers in order to
# prove they cannot be read would be shipping the escape it is testing.

def _peek():
    """The escape. Returns a number from nowhere the ledger can see."""
    return 7


def _owner_blocks(expert_slots, owner_buckets):
    """An allowlisted NAME whose body escapes -- the transitive case.

    `_owner_blocks` is in COMPUTE_ALLOWLIST because spine/assemble.py's own helper is pure. If the
    allowlist were a set of spellings, this function would inherit that permission and the escape would
    move one call deeper, which is worse than the original: nothing at the declaration site shows it.
    """
    return _peek() + max(1, min(int(expert_slots), int(owner_buckets)))


class _Callable:
    """A callable object. Its free names live on the instance, where a code-object check cannot read
    them -- so the coupling's reach would be undeclarABLE rather than merely undeclared."""

    def __init__(self, n):
        self.n = n

    def __call__(self, r):
        return self.n


def _rebind(fn, namespace):
    """The same code, resolving its globals somewhere else. Two things need this and neither can be
    written in ordinary source: a module where an allowlisted spelling means something else, and a module
    where an allowlisted helper is not bound yet (which is what a helper defined BELOW the table is)."""
    ns = dict(namespace)
    ns.setdefault("__builtins__", builtins)
    ns.setdefault("__name__", "a.foreign.module")
    return types.FunctionType(fn.__code__, ns, fn.__name__)


def _coupling(compute, dst="MEM.d_probe", src="FAB.slots"):
    return assemble.Coupling(
        src=src, dst=dst, compute=compute,
        why="a probe declared by tests/test_couplings.py, which needs a legible reason like every "
            "other coupling because _check_why does not know who is calling.")


# ==================================================================================================
# C1 -- the legitimate couplings are admitted
# ==================================================================================================
#
# The shipped table is checked by IMPORTING spine.assemble at all: every row is constructed at import, so
# a check that refused one of them would make this file fail on its import line rather than here. That is
# the strongest possible form of "the existing couplings still build", and it is also invisible -- so the
# ten computes are re-run through the check explicitly, and the count is printed. A silent proof and a
# printed count are not the same evidence.
#
# The four hand-written shapes matter as much as the shipped rows. A name check that refuses everything would
# pass C2 completely, and C2 is where the attention naturally goes. These are the shapes a future
# coupling will be written in -- a bare view read, arithmetic with the allowlisted builtins, a
# derive.f(Steps(...)) call, and a `def` with a docstring and locals -- and they are written HERE, in a
# module that is not spine/assemble.py, which also exercises the identity branch: `derive` and `Steps`
# mean the same objects in this file as they do there, so the allowlist admits them.

def _legit_view(r):
    return r["FAB"].slots


def _legit_arithmetic(r):
    return max(64, 2 * int(r["FAB"].slots))


def _legit_derive(r):
    return derive.flush_period(Steps(r["TRAIN"].grow_cap_every), r["TRAIN"].batch_w)


def _legit_def(r):
    """A compute with a docstring, a local variable and a comprehension over its own locals."""
    slots = int(r["FAB"].slots)
    parts = [min(slots, 64) for _ in (1, 2)]
    return max(parts)


LEGITIMATE = (
    ("a bare read through the view", _legit_view),
    ("arithmetic with allowlisted builtins", _legit_arithmetic),
    ("derive.f(Steps(...)) from another module", _legit_derive),
    ("a def with a docstring, a local and a comprehension", _legit_def),
)


def check_c1_legitimate_admitted():
    findings = []
    rows = list(assemble.COUPLINGS)
    for c in rows:
        try:
            assemble._check_compute(c.compute, c.dst)
        except WireError as e:
            findings.append(f"{c.dst}: the shipped coupling is refused by its own check: {e}")
    for label, fn in LEGITIMATE:
        try:
            _coupling(fn)
        except WireError as e:
            findings.append(f"{label}: refused, and should not be: {e}")
    detail = (f"{len(rows)} shipped coupling(s) re-checked, {len(LEGITIMATE)} legitimate shape(s) "
              f"declared from this module; {len(findings)} refused")
    return _report("C1", "the shipped table and the legitimate compute shapes are ADMITTED",
                   not findings, detail, findings, vacuous=not rows)


# ==================================================================================================
# C2 -- every way out of the declared sources is refused
# ==================================================================================================
#
# One row per escape, and each row names the substring the refusal must contain -- because "it raised"
# is not the claim. A refusal for the wrong reason is a check that happens to be standing in the right
# place today: `lambda r, _p=_peek: _p()` must be refused for its extra parameter, not because the
# author happened to also misspell the destination. The substring pins which branch fired.
#
# The first row is the reviewer's demonstration, unaltered in shape.

def _escape_default_value(r=_peek):
    return 1


def _escape_import(r):
    import os as _os
    return len(_os.environ)


def _unbound_helper(r):
    return _owner_blocks(r["FAB"].slots, 64)


ESCAPES = (
    ("the demonstrated escape: + _peek()",
     lambda r: max(64, 2 * int(r["FAB"].slots)) + _peek(),
     "not in COMPUTE_ALLOWLIST"),

    ("the same escape inside a generator expression",
     lambda r: max(_peek() for _ in (1,)),
     "not in COMPUTE_ALLOWLIST"),

    ("a closure cell instead of a module global",
     (lambda helper: (lambda r: helper()))(_peek),
     "closes over"),

    ("a second parameter carrying the helper as its default",
     lambda r, _p=_peek: _p(),
     "exactly one parameter"),

    ("a non-literal default on the one legal parameter",
     _escape_default_value,
     "non-literal default"),

    ("an import statement inside the compute",
     _escape_import,
     "imports"),

    ("__import__ as an ordinary builtin call",
     lambda r: __import__("os").environ.get("FAB_SLOTS"),
     "not in COMPUTE_ALLOWLIST"),

    ("a dunder attribute off an allowlisted name",
     lambda r: int(derive.__globals__ is not None),
     "dunder attribute"),

    ("getattr, so the read is invisible to _Fields' message",
     lambda r: getattr(r["FAB"], "slots"),
     "not in COMPUTE_ALLOWLIST"),

    ("functools.partial rather than a function",
     functools.partial(lambda r, k: k, k=1),
     "not a plain function"),

    ("a callable object, whose free names are instance state",
     _Callable(1),
     "not a plain function"),

    ("an allowlisted local helper whose own body escapes",
     lambda r: _owner_blocks(r["FAB"].slots, 64),
     "not in COMPUTE_ALLOWLIST"),

    ("an allowlisted spelling bound to something else",
     _rebind(_legit_derive, {"derive": types.SimpleNamespace(flush_period=lambda *a: 1),
                             "Steps": Steps}),
     "bound to"),

    ("an allowlisted helper defined BELOW the table, so unbound at construction",
     _rebind(_unbound_helper, {}),
     "not bound at the moment"),
)


def check_c2_escapes_refused():
    findings = []
    for label, compute, expect in ESCAPES:
        try:
            _coupling(compute)
        except WireError as e:
            msg = str(e)
            if expect not in msg:
                findings.append(f"{label}: refused, but for the wrong reason -- expected {expect!r} in "
                                f"the message, got: {msg[:160]}")
            elif "MEM.d_probe" not in msg:
                findings.append(f"{label}: refused without naming the coupling. A startup failure in a "
                                f"table this size must say which row: {msg[:120]}")
            continue
        except Exception as e:                                # noqa: BLE001 -- reported, never swallowed
            findings.append(f"{label}: raised {type(e).__name__} rather than WireError, so it fails as "
                            f"something other than a declaration fault: {e}")
            continue
        findings.append(f"{label}: ADMITTED. This is the hole -- a coupling whose value depends on "
                        f"something the ledger does not contain, and affects() cannot see.")
    detail = f"{len(ESCAPES)} escape shape(s) attempted, {len(findings)} not refused as declared"
    return _report("C2", "every reach past the declared sources is REFUSED at construction",
                   not findings, detail, findings, vacuous=not ESCAPES)


# ==================================================================================================
# C3 -- the allowlist itself is not a rubber stamp
# ==================================================================================================
#
# The allowlist is the one place the permitted names are written down, which makes it the one place a
# leak can be legalised in a single line. Three properties, all cheap:
#
#   it is not empty            -- an empty allowlist refuses everything and C2 would still pass
#   every name resolves        -- a stale entry is a name nobody can use and nobody notices is dead
#   every entry has a reason   -- the same rule wire._check_why applies to a coupling, for the same
#                                 reason: an entry with no stated purpose is indistinguishable from one
#                                 somebody added to make an import stop failing
#
# It is read out of spine.assemble rather than restated here. A second copy of the list would be a second
# validator with its own idea of the rule, which is how the old tree's report path and audit path ended
# up printing different numbers for one quantity.

def check_c3_allowlist_is_a_declaration():
    findings = []
    allow = assemble.COMPUTE_ALLOWLIST
    if not allow:
        findings.append("COMPUTE_ALLOWLIST is empty, so every compute is refused and C2 proves nothing.")
    try:
        allow["getattr"] = "widened at runtime"
        findings.append("COMPUTE_ALLOWLIST is writable at runtime. The permitted set must be a "
                        "declaration, not a variable: a widening that leaves no diff is the coupling "
                        "that is invisible in the ledger, one level up.")
    except TypeError:
        pass
    ns = vars(assemble)
    for name, why in allow.items():
        if assemble._resolve(ns, name) is assemble._UNBOUND:
            findings.append(f"{name!r} is allowlisted and resolves to nothing in spine.assemble. A dead "
                            f"entry is a name that reads as permitted and cannot be used, and the next "
                            f"author deletes the wrong one.")
        text = (why or "").strip()
        if len(text) < 20 or " " not in text:
            findings.append(f"{name!r}: {text[:40]!r} is a placeholder, not a reason. Say what the name "
                            f"is and why a coupling's value may depend on it.")
    detail = f"{len(allow)} allowlisted name(s): {sorted(allow)}"
    return _report("C3", "the allowlist is a frozen declaration with a reason per entry",
                   not findings, detail, findings, vacuous=not allow)


# ==================================================================================================
# C4 -- the declared couplings resolve, against stand-in packages
# ==================================================================================================
#
# THE KNOWN-ANSWER TABLE IS WRITTEN OUT BY HAND. Calling derive.flush_period here to produce the expected
# value would compare the shipped implementation against itself and pass on any implementation at all --
# which is the shape of every self-confirming test in the old tree. The numbers below come from the
# formulas in the coupling table and from the defects their reasons describe: 20000 steps at BATCH_W=16
# is 1250 flushes, and 2650 x 16 = 42400 is the shortfall that measurement made visible.
#
# The lever values are the ones the reasons name, so a reader can follow both: FAB_NMAX=4096 and
# MEM_OWNERS=64 are the pair that folded 32 experts into each memory partition; MEM_QUOTA=128 gives the
# 8,192-entry capacity that a requested MEM_CAP of 200,000 silently became; FAB_PRESSURE=0.75 against
# 4096 slots is the setpoint an occupancy of 0.50 sat below for a whole investigation.

LEVERS = {
    "FAB":   {"slots": 4096, "pressure": 0.75, "manage_every": 2000,
              "comp_ema": 0.02, "comp_protect": True},
    "MEM":   {"owners": 64, "quota": 128},
    "OPT":   {"batch_windows": 16, "accum": 4, "lr": 0.002, "lr_min_frac": 0.05},
    "CAP":   {"pin_windows": 20000},
    "LM":    {"vocab_slots": 32768, "ctx": 128, "mask_dead_rows": True},
    "CKPT":  {"dir": "runs/a/ckpt", "resume": "runs/parent/ckpt"},
    "DOM":   {},        # declares no lever of its own; its namespace bound arrives as a wire
    "TOK":   {"max_bytes": 24},   # sources LM.d_max_token_bytes; its own four values arrive as wires
}
# THE PREFIXES AND FIELD NAMES ARE THE REAL ONES; THE VALUES ARE NOT ALL THE REAL DEFAULTS, AND THAT
# DIFFERENCE IS DELIBERATE. `OPT_BATCH_WINDOWS` really defaults to 1, and at 1 every flush_period is the
# identity -- 20000 windows would be 20000 flushes, 2000 would be 2000, and the whole conversion this
# table exists to pin would be untested by the only case anyone reads. 16 is the batch width the measured
# defect was recorded at (43,645 pinned ticks against a clock reading 2,650, and 2650 x 16 = 42,400), so
# it is what the known-answer table is written against. FAB_SLOTS 4096, MEM_OWNERS 64, MEM_QUOTA 128,
# FAB_MANAGE_EVERY (real 500, here 2000) and LM_CTX 128 follow the same rule -- real where the real value
# exercises the row, and the previous fixture's number where it does not. Two are deliberately NOT the
# real default because the coupling reasons quote them: FAB_PRESSURE is 0.75 (real 0.45), the setpoint an
# occupancy of 0.50 sat below for a whole investigation, and LM_VOCAB_SLOTS is 32768 (real 4096), the
# width the softmax-row argument is written at.
# CKPT_DIR and CKPT_RESUME really default to "" -- meaning saving off and no parent -- and both computes
# return "" for that, so the fixture sets non-empty paths in order to exercise the branch that builds one.

EXPECTED = {
    "DOM.d_expert_slots":              4096,          # the slot pool bounds the domain id namespace
    "MEM.d_owner_blocks":              64,            # min(4096, 64): the fold that is 32 experts deep
    "MEM.d_capacity":                  8192,          # 64 blocks x 128 quota, not the declared 200,000
    "MEM.d_source_slots":              8192,          # max(64, 2 x 4096), not the 64 of the wrong default
    "FAB.d_manage_period":             Flushes(125),  # 2000 windows / 16 windows per flush
    "FAB.d_cap_lift_period":           Flushes(1250), # 20000 / 16 -- the clock that read 2650
    "TOK.d_cap_lift_period":           Flushes(1250), # the same valve, wired separately on purpose
    "TOK.d_vocab_ceiling":             32768,         # one number named twice, from LM's row count
    "TOK.d_vocab_save_path":           "runs/a/ckpt.dyntok.json",       # _TOK_SAVE's shipped rule
    "TOK.d_vocab_read_path":           "runs/parent/ckpt.dyntok.json",  # the parent's, by the same rule
    "FAB.d_operating_population":      3072,          # ceil(0.75 x 4096); LOCAL, no edge, no budget
    "OPT.d_effective_batch_windows":   64,            # 16 x 4; LOCAL. The batch the run actually trains at
    "LM.d_pos_max":                    128,           # LOCAL: the positional table is ctx rows tall
    # ---- the nine rows the contract phase added; same rule, hand-computed from the shipped formulas --
    "LM.d_max_token_bytes":            24,            # TOK.max_bytes, and DELIBERATELY not the 16 that
                                                      # ByteComposer hardcodes at :1441 -- a fixture at 16
                                                      # would pass whether the wire arrived or the
                                                      # hardcode did, which is the M21 defect exactly
    "CAP.d_expert_slots":              4096,          # the hard ceiling CAP_FAB_START=0 resolves to
    "CAP.d_vocab_slots":               32768,         # the same sentinel on the vocabulary target
    "CAP.d_mask_dead_rows":            True,          # LM owns the output layer; not CAP's to decide
    "CAP.d_operating_population":      3072,          # ceil(0.75 x 4096) again -- the SAME derive call
                                                      # as FAB's row, so the setpoint the fabric settles
                                                      # at and the one the valve refuses against agree
    "DOM.d_comp_ema":                  0.02,          # one smoothing rate for both populations
    "DOM.d_comp_protect":              True,          # one brake policy for both populations
    "FAB.d_base_lr":                   0.002,         # the PEAK, which :7252's envelope is built from
    "FAB.d_lr_min_frac":               0.05,          # the floor, which :7251 needs in the same block
}

LOCAL_DSTS = {"FAB.d_operating_population", "OPT.d_effective_batch_windows", "LM.d_pos_max"}


def _package(prefix, values):
    """A stand-in for one package's LeverSet: PREFIX and from_env, which is all build() touches.

    NOT a LeverSet subclass -- see the module docstring. The owner is a class rather than an instance so
    that `Config._owner.__name__` and `Config._owner.PREFIX` are the ordinary things Config expects.
    """
    owner = type(f"{prefix}Stand_In", (), {"PREFIX": prefix, "_levers": {}})
    owner.from_env = classmethod(lambda cls, environ=None: Config(cls, values, {}))
    return owner


def check_c4_table_resolves():
    findings = []
    sets = {p: _package(p, v) for p, v in LEVERS.items()}
    try:
        configs, wires, warnings = assemble.build(environ={}, sets=sets)
    except Exception as e:                                    # noqa: BLE001 -- reported, never swallowed
        return _report("C4", "the declared couplings resolve against stand-in packages", False,
                       f"build() raised {type(e).__name__}: {e}", [])

    landed = {f"{p}.{f}": v for p, cfg in configs.items() for f, v in cfg.wired().items()}

    for dst, want in EXPECTED.items():
        if dst not in landed:
            findings.append(f"{dst}: declared in the table and not present on the assembled Config. A "
                            f"coupling that does not arrive is the DEFERRED state, and every package "
                            f"here is registered.")
            continue
        got = landed[dst]
        # `type(got) is type(want)` before the comparison: a Flushes clock and a bare int are the exact
        # pair spine.units exists to keep apart, and Clock.__eq__ raises across kinds rather than
        # returning False -- so an int where a clock belongs must be reported as a wrong TYPE, not left
        # to surface as a UnitError from inside a test's assertion.
        if type(got) is not type(want):
            findings.append(f"{dst}: got {got!r} ({type(got).__name__}), expected {want!r} "
                            f"({type(want).__name__}). A cadence that arrives as a bare int compares "
                            f"fine against a threshold in the wrong unit.")
        elif got != want:
            findings.append(f"{dst}: got {got!r}, expected {want!r} from the known-answer table.")

    for dst in sorted(set(landed) - set(EXPECTED)):
        findings.append(f"{dst} landed on a Config and is not in this file's known-answer table. Either "
                        f"a coupling was added without its expected value, or a d_ field arrived from "
                        f"somewhere other than the table.")

    if warnings:
        findings.append(f"build() warned, and with every package registered and environ={{}} it should "
                        f"not: {warnings}")

    # The ledger holds the CROSS couplings only. A local coupling books no edge, because an edge from a
    # package to itself adds its owner to an affects() set that already contains it -- so the ledger
    # count is a claim about the coupling graph, not a count of the table.
    want_wires = len(EXPECTED) - len(LOCAL_DSTS)
    if len(wires) != want_wires:
        findings.append(f"the ledger holds {len(wires)} wire(s); {want_wires} expected -- "
                        f"{len(EXPECTED)} couplings less the {len(LOCAL_DSTS)} intra-package ones "
                        f"({sorted(LOCAL_DSTS)}), which book no edge and spend no budget.")
    for dst in sorted(LOCAL_DSTS):
        if wires.by_dst(dst) is not None:
            findings.append(f"{dst} is intra-package and booked an edge anyway. That spends budget for a "
                            f"coupling that cannot widen any lever's reach.")

    # affects() is the L3 sweep's whole oracle, and it is the reason the closure check exists: the
    # demonstrated escape left FAB_MANAGE_EVERY reading {'FAB'} while MEM's value moved with it. Checked
    # here with an explicit env_owner map because the stand-ins deliberately register nothing.
    owners = {f"{p}_{f.upper()}": p for p, vals in LEVERS.items() for f in vals}
    reach = {name: wires.affects(name, env_owner=owners) for name in owners}
    if reach.get("FAB_SLOTS") != frozenset({"FAB", "DOM", "MEM", "CAP"}):
        findings.append(f"affects('FAB_SLOTS') = {sorted(reach.get('FAB_SLOTS', ()))}; the slot count is "
                        f"declared to reach DOM, MEM and CAP as well as its own package -- CAP because "
                        f"the capacity valve lifts a soft cap toward this hard one and refuses a start "
                        f"above the cull's settling point.")
    if reach.get("FAB_MANAGE_EVERY") != frozenset({"FAB"}):
        findings.append(f"affects('FAB_MANAGE_EVERY') = {sorted(reach.get('FAB_MANAGE_EVERY', ()))}; it "
                        f"is read only by its own package's cadence coupling.")

    for p, cfg in configs.items():
        try:
            cfg._wire("d_late", 1)
            findings.append(f"{p} accepted a wire after build() returned. Config freezes when build() "
                            f"returns, and that is what lets the report claim it read what the run used.")
        except Exception:
            pass

    text = assemble.render(configs, wires)
    for dst in EXPECTED:
        if dst not in text:
            findings.append(f"render() does not print {dst}. docs/03_WIRING.md is generated from it and "
                            f"a coupling missing from the printed graph is a coupling nobody reviews.")
    if "DEFERRED" in text:
        findings.append("render() reports a DEFERRED row on a build where every package is present.")

    detail = (f"{len(EXPECTED)} coupling(s) resolved against {len(sets)} stand-in package(s); "
              f"{len(wires)} wire(s) of {wires.budget} budgeted, {len(LOCAL_DSTS)} intra-package; "
              f"{len(text.splitlines())} line(s) rendered")
    return _report("C4", "the declared couplings resolve to the known-answer table",
                   not findings, detail, findings, vacuous=not EXPECTED)


# ==================================================================================================
# The runner
# ==================================================================================================

CHECKS = (
    check_c1_legitimate_admitted,
    check_c2_escapes_refused,
    check_c3_allowlist_is_a_declaration,
    check_c4_table_resolves,
)


def main():
    print("=== couplings: what a compute may name, and what the table builds ===")
    print(f"{len(assemble.COUPLINGS)} declared coupling(s); Python {sys.version.split()[0]}")
    print()
    failed = 0
    for check in CHECKS:
        failed += check()
        print()
    print(f"=== {len(CHECKS)} checks, {failed} failing ===")
    print("C2 proves a compute cannot NAME its way out of its declared sources. It does not prove the")
    print("coupling graph is complete: a value that travels through shared state, RNG draw order or the")
    print("data writes no wire and names nothing, and only L3 (tests/test_lever_isolation.py, against")
    print("the test_determinism noise floor) is evidence about that.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
