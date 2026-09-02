"""The RUNTIME spine, exercised end to end: build(), the typo net, affects(), render(), the freeze.

    python3 tests/test_assemble.py           # PASS/FAIL per check with counts; non-zero exit on any FAIL

WHY THIS FILE EXISTS. Everything in src/spine that RESOLVES something was armed and unreached. Nothing
in tests/ called _build(), assemble.render(), Wires.affects(), Wires.render(),
registry.unread_env() or rng.issued(): tests/test_ownership.py imports spine.assemble only to read its
COUPLINGS table for an AST cross-check, and tests/test_determinism.py names build() inside a comment
marking the P3 plug point. That is this project's ARMED-BUT-INERT class -- 57 of the survey's 475 records
-- committed in the new tree, in the module whose entire job is to prevent it. A wiring layer nothing has
ever run is a wiring layer whose first execution happens on the run that needed it.

WHAT IS DIFFERENT HERE FROM tests/test_couplings.py, which lands beside this file and also builds. That
file's C4 proves the declared rows COMPUTE the right numbers, using plain-object doubles that carry
only PREFIX and from_env and deliberately register nothing -- for a good reason, quoted from its header:
a `class Fab(LeverSet): PREFIX = "FAB"` in a test claims "FAB" in the process-wide registry, and the day
P3 lands the real fabric package any runner importing both gets `PREFIX 'FAB' is claimed by both ...`
from a test file.

The cost of that choice is that half of build() cannot be reached at all, and the half it cannot reach is
the half this file is about. `registry.unread_env` derives the families it scans from the registry:

    fams = tuple(families or sorted({p + "_" for p in _SETS}))     # registry.py
    ... if k in known or not k.startswith(fams): continue

With nothing registered that is `startswith(())`, which is False for every key, so the typo net returns
[] for an environment of pure garbage -- verified: `unread_env({'FAB_SLOT': '1', 'TOTAL_NONSENSE': '2'})`
on the tree as it stands returns []. A guard that cannot be tripped is not a guard, so a test that ran
G9 against unregistered doubles would be a green tick over an empty set: the exact defect the vacuity
line in every _report below exists to make visible.

So this file declares REAL LeverSet subclasses -- and answers the collision objection rather than
avoiding it, in `packages()` below: the registry is snapshotted, CLEARED, populated with the six stand-in
packages, and restored in a finally. Clearing first is what makes it future-proof: the day the real FAB
package exists and is imported by the same runner, these declarations still do not collide with it,
because they are made against an empty registry and the real one is put back before this file returns.
The doubles are therefore full participants -- `build(environ=env)` runs here with NO `sets=` and NO
`couplings=` override, which is the production path, through registry.all_sets() and the real COUPLINGS.

WHAT THIS FILE PROVES:
  A1  every declared coupling lands its d_ field on the RECEIVING Config, with the computed value, and
      an environment knob travels lever -> compute -> d_ field on another package.
  A2  G9, the typo net: a near-miss knob is reported by name with the right suggestion, a correctly
      spelled one is not reported and does move the numbers, and a foreign name is left alone.
  A3  affects() -- the L3 sweep's only oracle -- returns the computed reach for a lever that feeds a
      wire and just the owner for one that does not, INCLUDING one that feeds a local coupling.
  A4  render() names every coupling and separates the irreducible ones from the chosen ones.
  A5  build() runs once: a Config that has been frozen refuses a second build, and the budget bites.
  A6  a coupling whose packages are absent is DEFERRED and says so -- in the warnings and in the graph.
  A7  rng.issued() distinguishes the three states graft G4 needs: drew, armed-but-inert, never asked.

WHAT IT CANNOT CATCH:
  * whether the numbers are the RIGHT numbers. The expectation tables below are hand-computed from the
    shipped formulas, which pins what the table computes today but cannot tell a correct formula from a
    plausible one. tests/test_derive.py's oracle replay (575 cases, 0 mismatches) stands behind the
    arithmetic; the `why` column stands behind the choice.
  * a coupling that travels through shared state, RNG draw order or the corpus. It writes no wire and
    names nothing, so it is invisible here exactly as it is to the AST checks in tests/test_ownership.py.
    That is L3's (tests/test_lever_isolation.py), against the tests/test_determinism.py noise floor.
  * a compute that NAMES its way out of its declared sources. tests/test_couplings.py C1/C2 is that
    check, and it is a declaration-time one; nothing here would notice.
  * a knob misspelled OUT of its family. `FABRIC_SLOTS` does not start with any declared PREFIX + "_",
    so the typo net skips it in silence, and so would a name with the prefix omitted entirely. G9 is a
    near-miss net inside the families, not a spell-checker over the environment.
"""
import contextlib
import difflib
import glob
import io
import os
import re
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from spine import assemble                                             # noqa: E402
from spine import lever                                                # noqa: E402
from spine import registry                                             # noqa: E402
from spine import rng                                                  # noqa: E402
from spine import units as U                                           # noqa: E402
from spine.lever import Lever, LeverError, LeverSet                    # noqa: E402
from spine.units import Flushes                                        # noqa: E402
from spine.wire import WIRE_BUDGET, WireError                          # noqa: E402

MAX_SHOWN = 12


def _build(*a, **kw):
    """_build(), with the assembly latch released first, and this is the ONLY file that may.

    spine/lever.py latches after build() returns and from_env raises from then on. That exists because a
    reviewer walked past every AST check with `LeverSet.__subclasses__()` plus `getattr(sib, "from_" +
    "env")()` -- thirteen packages, every env-overridden value, ten checks green -- and a latch matches a
    MOMENT, which is the one thing a spelling cannot get round.

    This file builds seven times in one process ON PURPOSE: A1 needs a default build AND an
    environment-overridden one to show a knob reaching another package, A2 needs a garbage environment,
    A5 needs a SECOND build to prove a frozen Config refuses it, A6 needs a build with packages missing.
    Those are seven separate startups being simulated, not one startup resolving twice, so releasing the
    latch is honest here and is what the LeverError message tells the reader to do.

    It is a named wrapper rather than a call to lever._reopen_assembly() at seven sites because seven
    scattered releases is how a latch quietly stops being one: the eighth caller copies the line without
    the reason. Nothing in src/ may do this -- O10 refuses the import of spine.lever from a package for
    the purpose of the from_env it exposes, and the latch is what refuses it if the import ever lands.
    """
    lever._reopen_assembly()
    return assemble.build(*a, **kw)


# The registry as this file found it: thirteen real packages, because importing spine.assemble imports
# every levers.py. Snapshotted at module level so the runner can tell "the sandbox restored what was
# here" from "the registry happens to be non-empty" -- see the note at the bottom of main().
REGISTRY_ON_ENTRY = registry.all_sets()


def _report(tag, title, ok, detail, findings, vacuous=False):
    """One check's verdict, with the size of the population it examined ALWAYS printed.

    A green tick over an empty set is this project's most repeated defect -- 60 of the survey's 475
    records are guards whose condition cannot be satisfied -- and this file exists because six runtime
    entry points had zero callers. Printing the count is the only honest way to say a check looked at
    something. Same shape as tests/test_ownership.py and tests/test_couplings.py on purpose: three test
    files with three report formats is the report-path/audit-path drift this project already paid for.
    """
    mark = "PASS" if ok else "FAIL"
    note = "   (VACUOUS: 0 examined)" if vacuous else ""
    print(f"{mark}  {tag}  {title}{note}")
    print(f"      {detail}")
    for f in findings[:MAX_SHOWN]:
        print(f"      - {f}")
    if len(findings) > MAX_SHOWN:
        print(f"      ... and {len(findings) - MAX_SHOWN} more")
    return 0 if ok else 1


# ==================================================================================================
# The stand-in packages, and the registry sandbox that makes declaring them safe
# ==================================================================================================

@contextlib.contextmanager
def packages():
    """Nine real LeverSets for the PREFIXes the coupling table names, in a sandboxed registry.

    WHY REAL SUBCLASSES AND NOT DOUBLES. Three things build() uses come from the registry and only from
    the registry, and every one of them is a claim this file has to check:
      * `registry.all_sets()` -- what build() resolves when the caller passes no `sets`, which is what
        production passes. A test that always hands in its own `sets` never runs that line.
      * `registry.unread_env()` -- G9's families are the registered PREFIXes. Unregistered doubles make
        the typo net return [] for any environment at all (verified; see the module docstring).
      * `registry.all_env_names()` -- what `Wires.affects()` uses when the caller passes no `env_owner`,
        again the production path. tests/test_couplings.py passes an explicit owner map, so the branch
        that reads the registry has never run.

    WHY THE SNAPSHOT-CLEAR-RESTORE, which is the part that answers tests/test_couplings.py's objection.
    A PREFIX has exactly one owner, and `registry.register` refuses a second -- correctly. Declaring
    PREFIX="FAB" here at import time would spend that name process-wide and collide with the real fabric
    package the day it exists, in a test file, which is a confusing failure in the wrong place. Clearing
    the registry first means these declarations are made against an empty one, so they cannot collide
    with anything; restoring in `finally` means nothing outside this file ever sees them. The registry's
    two dicts are named directly because there is no public API for this and inventing one to serve a
    test would be a production surface that exists for a test.

    THE DEFAULTS MATCH tests/test_couplings.py's LEVERS TABLE (slots 4096, owners 64, quota 128,
    vocab_slots 32768, ctx 128, batch_windows 16, accum 4, pin_windows 20000, manage_every 2000,
    pressure 0.75, and the two CKPT paths) on purpose. Two test files disagreeing about what the shipped
    table computes would be the report-path/audit-path split all over again, one quantity with two
    answers depending on which file you read.

    THESE ARE STAND-INS AND NOT THE REAL PACKAGES, WHICH NOW EXIST -- and the reason is A3, not inertia.
    src/*/levers.py declares 261 levers across thirteen packages; A3 requires a stated reach for EVERY
    declared lever, because an oracle checked only where somebody remembered to check it is not an
    oracle. Nine stand-ins carrying the fourteen fields the coupling table actually names keep that
    requirement meetable and keep the fixture readable. What the stand-ins may NOT do is drift from the
    real declarations: the PREFIXes and the field names below are exactly the ones src/*/levers.py
    declares, which is what makes the real COUPLINGS table resolve against them. The VALUES are chosen
    to exercise the arithmetic -- OPT_BATCH_WINDOWS really defaults to 1, and at 1 every flush period is
    the identity, so the conversion that pinned the population for 43,645 ticks would be untested by the
    only case anyone reads. tests/test_couplings.py's table carries the same note.
    """
    sets_before = dict(registry._SETS)
    envs_before = dict(registry._ENV_OWNER)
    registry._SETS.clear()
    registry._ENV_OWNER.clear()
    try:
        class Fabric(LeverSet):
            PREFIX = "FAB"
            slots = Lever(4096, "hard ceiling on the expert slot pool", U.SLOTS)
            manage_every = Lever(2000, "management cadence, written in WINDOWS", U.Windows)
            pressure = Lever(0.75, "occupancy setpoint the cull equilibrates at", U.FRACTION)
            comp_ema = Lever(0.02, "rate competence is smoothed at, for BOTH populations", U.FRACTION)
            comp_protect = Lever(True, "spare a member whose competence beats the baseline", U.FLAG)

        class Memory(LeverSet):
            PREFIX = "MEM"
            owners = Lever(64, "partitions the store is split into", U.COUNT)
            quota = Lever(128, "entries retained per partition", U.ENTRIES)

        class Domains(LeverSet):
            PREFIX = "DOM"
            # A PURE SINK WITH A LEVER OF ITS OWN. DOM receives d_expert_slots and reads nothing, so
            # this lever is here to be the control in A3: a declared knob that feeds no coupling at all
            # must have affects() == {"DOM"}. Without it the "just the owner" case would only be
            # testable on levers that DO feed something, which is a weaker statement.
            min_support = Lever(32, "occurrences before a domain is minted", U.COUNT)

        class Tokenizer(LeverSet):
            PREFIX = "TOK"
            # A PURE SINK WITH NO LEVER OF ITS OWN in this fixture: TOK receives four wires (the
            # vocabulary ceiling, the cap-lift cadence and the two vocabulary paths) and sources none.
            # The real TOKLevers declares 18; none of them appears in any coupling, so declaring one
            # here would only add a lever A3 has to write an expectation for. It gained exactly ONE
            # when LM.d_max_token_bytes landed: TOK is a source for that row and the fixture cannot
            # resolve it otherwise.
            max_bytes = Lever(24, "longest token that may be minted, in bytes", U.BYTES)

        class Optimizer(LeverSet):
            PREFIX = "OPT"
            batch_windows = Lever(16, "windows accumulated into one flush", U.Windows)
            accum = Lever(4, "backward passes per optimizer step", U.Backwards)
            lr = Lever(0.002, "the PEAK rate the schedule warms up to", U.FRACTION)
            lr_min_frac = Lever(0.05, "the floor the cosine anneals toward, as a fraction of peak",
                                U.FRACTION)

        class Capacity(LeverSet):
            PREFIX = "CAP"
            pin_windows = Lever(20000, "windows pinned at the soft cap before a lift is earned",
                                U.Windows)

        class Checkpoint(LeverSet):
            PREFIX = "CKPT"
            dir = Lever("runs/a/ckpt", "this run's checkpoint root", U.PATH)
            resume = Lever("runs/parent/ckpt", "the checkpoint this run continues from", U.PATH)

        class Model(LeverSet):
            PREFIX = "LM"
            vocab_slots = Lever(32768, "rows in emb.weight and head.weight", U.SLOTS)
            ctx = Lever(128, "tokens in one window, and the height of the positional table", U.TOKENS)
            mask_dead_rows = Lever(True, "keep never-minted rows out of the softmax denominator", U.FLAG)

        class Run(LeverSet):
            PREFIX = "RUN"
            seed = Lever(1234, "the run seed every subsystem stream is derived from", U.COUNT)

        class Signature(LeverSet):
            # ADDED WITH SIG.d_idle_cadence, which is the coupling ISSUES P1-H53 records as declared in
            # a comment for six commits and nowhere else. Its two ends are both SIG's, so without a
            # SIG stand-in the row deferred on every build here and three checks reported the
            # deferral as a defect -- correctly. The stand-ins are the reason A1/A2/A4 can assert
            # "no warnings with every package registered" at all; a prefix missing from this map is
            # a package this file cannot say anything about.
            PREFIX = "SIG"
            train_every = Lever(1, "dense contrastive cadence, in windows", U.Windows)
            train_every_idle = Lever(12, "throttled cadence once the stream is stable", U.Windows)

        yield {"FAB": Fabric, "MEM": Memory, "DOM": Domains, "TOK": Tokenizer,
               "OPT": Optimizer, "CAP": Capacity, "CKPT": Checkpoint, "LM": Model, "RUN": Run,
               "SIG": Signature}
    finally:
        registry._SETS.clear()
        registry._SETS.update(sets_before)
        registry._ENV_OWNER.clear()
        registry._ENV_OWNER.update(envs_before)


# ---- the known-answer tables ---------------------------------------------------------------------
# HAND-COMPUTED FROM THE SHIPPED FORMULAS, not read back out of the couplings that produce them. A test
# that calls the compute it is checking asserts only that Python is deterministic. Changing a formula
# must therefore be a two-file edit, on purpose, which is what makes an accidental change visible.

# What the table computes on defaults alone.
EXPECTED_DEFAULT = {
    "DOM.d_expert_slots":              4096,           # the slot pool bounds the domain id namespace
    "MEM.d_owner_blocks":              64,             # min(4096, 64) -- the store has 64 partitions
    "MEM.d_capacity":                  8192,           # 64 x 128; the 200,000 that got silently shrunk
    "MEM.d_source_slots":              8192,           # max(64, 2 x 4096), not the 64 of the wrong default
    "FAB.d_manage_period":             Flushes(125),   # 2000 windows / 16 windows per flush
    "FAB.d_cap_lift_period":           Flushes(1250),  # 20000 / 16 -- the clock that read 2,650
    "TOK.d_cap_lift_period":           Flushes(1250),  # the same valve, wired separately on purpose
    "TOK.d_vocab_ceiling":             32768,          # one number named twice, from LM's row count
    "TOK.d_vocab_save_path":           "runs/a/ckpt.dyntok.json",       # _TOK_SAVE's shipped rule
    "TOK.d_vocab_read_path":           "runs/parent/ckpt.dyntok.json",  # the parent's, by the same rule
    "SIG.d_idle_cadence":              12,             # max(1 x 6, 12); LOCAL, both ends SIG's --
                                                      # the relation ISSUES P1-H53 records as declared
                                                      # in a comment and nowhere else for six commits
    "FAB.d_operating_population":      3072,           # ceil(0.75 x 4096); LOCAL, no edge, no budget
    "OPT.d_effective_batch_windows":   64,             # 16 x 4; LOCAL. The batch the run actually trains at
    "LM.d_pos_max":                    128,            # LOCAL: the positional table is ctx rows tall
    # ---- the nine rows the contract phase added ---------------------------------------------------
    "LM.d_max_token_bytes":            24,             # TOK.max_bytes, deliberately NOT ByteComposer's
                                                       # hardcoded 16: a fixture at 16 would pass whether
                                                       # the wire arrived or the hardcode did (M21)
    "CAP.d_expert_slots":              4096,           # the hard ceiling CAP_FAB_START=0 stands for
    "CAP.d_vocab_slots":               32768,          # the same sentinel, vocabulary target
    "CAP.d_mask_dead_rows":            True,           # LM owns the output layer, not the valve
    "CAP.d_operating_population":      3072,           # ceil(0.75 x 4096) -- the SAME derive call as
                                                       # FAB's row, so the two setpoints cannot disagree
    "DOM.d_comp_ema":                  0.02,           # one smoothing rate across both populations
    "DOM.d_comp_protect":              True,           # one brake policy across both populations
    "FAB.d_base_lr":                   0.002,          # the PEAK, which :7252's envelope is built from
    "FAB.d_lr_min_frac":               0.05,           # the floor, which :7251 needs in the same block
}

# What it computes with FAB_SLOTS=1024 in the environment and nothing else set. This is the whole point
# of A1: one correctly spelled knob, and the value has to arrive on three OTHER packages' Configs.
EXPECTED_ENV = dict(EXPECTED_DEFAULT, **{
    "DOM.d_expert_slots":         1024,                # straight through
    "MEM.d_source_slots":         2048,                # max(64, 2 x 1024)
    "FAB.d_operating_population": 768,                 # ceil(0.75 x 1024)
    "CAP.d_expert_slots":         1024,                # straight through, to the valve's hard ceiling
    "CAP.d_operating_population": 768,                 # the second landing of the same derive call
})

# THE FIELDS THAT MOVE, WRITTEN DOWN RATHER THAN DERIVED WITH A RULE. The tempting rule -- "every d_
# field whose coupling reads FAB.slots must change when FAB_SLOTS changes" -- is FALSE here, and
# believing it would get this test "fixed" in the wrong direction. MEM.d_owner_blocks is
# min(slots, owners) = 64 at both 4096 and 1024, so it does not move; MEM.d_capacity is that same fold
# times the quota, so it does not move either. That is not the coupling failing to arrive, it is the
# fold SATURATING -- which is precisely what makes it irreducible: expert ids run to the slot count
# while the store has 64 partitions, so 32 experts shared each partition and "per-expert memory" was
# per-64-buckets memory. The set below is the honest answer and the two saturated fields are the
# evidence for the reason column.
MOVED_BY_SLOTS = {"DOM.d_expert_slots", "MEM.d_source_slots", "FAB.d_operating_population",
                  "CAP.d_expert_slots", "CAP.d_operating_population"}

# The environment A1 and A2 are run against: one correctly spelled knob, one near miss of a real name,
# one name that is not ours at all.
GOOD_KNOB, GOOD_VALUE = "FAB_SLOTS", "1024"
TYPO_KNOB, TYPO_VALUE = "FAB_SLOT", "999"        # FAB_SLOTS minus one character
TYPO_MEANT = "FAB_SLOTS"
FOREIGN_KNOB = "CUDA_VISIBLE_DEVICES"
ENV = {GOOD_KNOB: GOOD_VALUE, TYPO_KNOB: TYPO_VALUE, FOREIGN_KNOB: "0"}

LOCAL_DSTS = {"FAB.d_operating_population", "OPT.d_effective_batch_windows", "LM.d_pos_max",
              "SIG.d_idle_cadence"}


def _landed(configs):
    """Every d_ value actually present on the assembled Configs, keyed "PREFIX.d_field".

    Read off the Configs rather than off the coupling table, because "the table says so" is the claim
    being checked: a declaration whose value never arrived is the DEFERRED state, and it is invisible to
    anything that trusts the declaration.
    """
    return {f"{p}.{f}": v for p, cfg in configs.items() for f, v in cfg.wired().items()}


def _compare(landed, expected, findings, label):
    """Compare landed values against a known-answer table, reporting type before value.

    `type(got) is type(want)` FIRST because a Flushes clock and a bare int are the exact pair
    spine/units.py exists to keep apart, and Clock.__eq__ RAISES across kinds rather than returning
    False. Comparing first and typing second would surface a wrong type as a UnitError escaping from
    inside this test's own assertion, which reads as the test being broken rather than the value being
    in the wrong unit -- and "a cadence in the wrong unit" is the defect that pinned the population for
    43,645 real steps while the clock read 2,650.
    """
    for dst, want in expected.items():
        if dst not in landed:
            findings.append(f"{label}: {dst} is declared in the table and absent from the receiving "
                            f"Config. Every package is registered on this build, so there is no "
                            f"DEFERRED excuse: the coupling did not arrive.")
            continue
        got = landed[dst]
        if type(got) is not type(want):
            findings.append(f"{label}: {dst} = {got!r} ({type(got).__name__}), expected {want!r} "
                            f"({type(want).__name__}). A cadence that arrives as a bare int compares "
                            f"fine against a threshold in the wrong unit.")
        elif got != want:
            findings.append(f"{label}: {dst} = {got!r}, expected {want!r} from the known-answer table.")
    for dst in sorted(set(landed) - set(expected)):
        findings.append(f"{label}: {dst} landed on a Config and is in no known-answer table. Either a "
                        f"coupling was added without its expected value, or a d_ field arrived from "
                        f"somewhere other than spine.assemble.COUPLINGS.")


# ==================================================================================================
# A1 -- build() resolves the whole table, and an environment knob reaches other packages
# ==================================================================================================

def check_a1_build_resolves():
    """Every declared coupling produces its d_ field on the RECEIVING config, with the computed value.

    CANNOT CATCH: whether the formula is right (tests/test_derive.py's oracle), or a coupling nobody
    declared (tests/test_ownership.py's O4, both directions).
    """
    findings = []
    with packages() as P:
        # NO sets=, NO couplings=. This is the production call: registry.all_sets() and the real
        # COUPLINGS table. Every other exercise of build() in this tree hands in its own, so the two
        # `if x is None` branches at the top of build() had never run.
        cfg_default, wires_default, warn_default = _build(environ={})
        configs, wires, warnings = _build(environ=ENV)

        landed_default = _landed(cfg_default)
        landed = _landed(configs)
        _compare(landed_default, EXPECTED_DEFAULT, findings, "defaults")
        _compare(landed, EXPECTED_ENV, findings, f"{GOOD_KNOB}={GOOD_VALUE}")

        # The knob travelled: lever -> compute -> a d_ field on somebody ELSE's Config.
        if configs["FAB"].slots != int(GOOD_VALUE):
            findings.append(f"{GOOD_KNOB}={GOOD_VALUE!r} resolved to {configs['FAB'].slots!r}. The "
                            f"environment is coerced to the declared type by the declaration's own "
                            f"default; a knob that does not arrive is silently the default.")
        if configs["FAB"].given() != {"slots": GOOD_VALUE}:
            findings.append(f"FAB.given() = {configs['FAB'].given()}; the record of what the environment "
                            f"actually supplied is what lets a report say which knobs a run READ, as "
                            f"opposed to which ones it has.")
        moved = {d for d in landed if type(landed[d]) is type(landed_default[d])
                 and landed[d] != landed_default[d]}
        if moved != MOVED_BY_SLOTS:
            findings.append(f"changing {GOOD_KNOB} from the default to {GOOD_VALUE} moved "
                            f"{sorted(moved)}; expected {sorted(MOVED_BY_SLOTS)}. Fields fed by "
                            f"FAB.slots that did NOT move are the saturating fold min(slots, owners) "
                            f"and are listed in MOVED_BY_SLOTS' comment -- if this fires, check which "
                            f"of the two it is before editing the expectation.")

        # THE RECEIVER READS IT UNDER THE NAME THE WIRE CHOSE, AND CANNOT READ THE SOURCE AT ALL. This
        # is the review's "wires launder couplings" objection, answered at run time: DOM sees a
        # d_-prefixed field it did not name, and `DOM.slots` -- the laundered spelling -- does not
        # exist. `grep -rn d_ src/` therefore really is the whole coupling index.
        try:
            if configs["DOM"].d_expert_slots != int(GOOD_VALUE):
                findings.append(f"DOM.d_expert_slots reads {configs['DOM'].d_expert_slots!r} by "
                                f"attribute; the wired value must be readable the way a lever is.")
        except LeverError as e:
            # THE SHAPE THIS CATCHES IS A LEDGER THAT DESCRIBES A DIFFERENT SYSTEM. `Wires.add` performs
            # the assignment itself (`into=`) precisely so that the record and the assignment cannot
            # disagree; drop the `into=` and every wire is still recorded, render() still prints the
            # coupling, affects() still claims the reach -- and no value ever arrives on the receiver.
            findings.append(f"DOM.d_expert_slots is not present on the receiving Config: {e}")
        try:
            configs["DOM"].slots
            findings.append("DOM.slots resolved. A receiving package must not be able to read the "
                            "source lever under its owner's name -- that is the laundering the d_ "
                            "prefix exists to prevent.")
        except LeverError:
            pass
        for p, cfg in configs.items():
            for f in cfg.wired():
                if not f.startswith("d_"):
                    findings.append(f"{p}.{f} was wired without a d_ prefix; `grep d_` would miss it.")

        # build() hands the caller EVERY package's Config, which is the one place in the running system
        # where that is true. owned_by() is the assertion at the far end of that hand-off, and this is
        # the only place it can be exercised against the object build() actually returns.
        if configs["MEM"].owned_by("MEM") is not configs["MEM"]:
            findings.append("Config.owned_by returns self so it composes; it did not.")
        try:
            configs["FAB"].owned_by("MEM")
            findings.append("FAB's Config answered to owned_by('MEM'). The wrong hand-off must be a "
                            "startup failure, not a plausible wrong number in a report -- "
                            "`memory_prune(configs['FAB'])` returned 2048 in the old tree.")
        except LeverError:
            pass

        if warn_default:
            findings.append(f"build(environ={{}}) warned with every package registered: {warn_default}")
        if len(wires) != len(EXPECTED_ENV) - len(LOCAL_DSTS):
            findings.append(f"the ledger holds {len(wires)} wire(s); {len(EXPECTED_ENV)} couplings less "
                            f"the {len(LOCAL_DSTS)} intra-package ones should be "
                            f"{len(EXPECTED_ENV) - len(LOCAL_DSTS)}. A local coupling books no edge.")
        for dst in sorted(LOCAL_DSTS):
            if wires.by_dst(dst) is not None:
                findings.append(f"{dst} is intra-package and booked an edge anyway; that spends budget "
                                f"on an edge that cannot widen any lever's reach.")
        if wires.budget != WIRE_BUDGET:
            findings.append(f"build() built a ledger with budget {wires.budget}; production must get "
                            f"WIRE_BUDGET={WIRE_BUDGET}, not a number a caller relaxed.")
        if len(wires_default) != len(wires):
            findings.append("the ledger size changed with the environment; the coupling GRAPH is a "
                            "function of the declarations, not of the values.")

    detail = (f"{len(assemble.COUPLINGS)} coupling(s) built twice against {len(P)} registered package(s): "
              f"{len(landed_default)} d_ field(s) on defaults, {len(landed)} with {GOOD_KNOB}={GOOD_VALUE}; "
              f"{len(wires)} wire(s) of {wires.budget} budgeted, {len(LOCAL_DSTS)} intra-package")
    return _report("A1", "every declared coupling lands its d_ field on the receiving Config",
                   not findings, detail, findings, vacuous=not landed)


# ==================================================================================================
# A2 -- G9, the typo net
# ==================================================================================================

def check_a2_typo_net():
    """A misspelled knob is reported by name with the right suggestion; a foreign name is not.

    THE DEFECT, and it is one this project has lost runs to: a mis-typed knob is silently the default.
    There is no error, no log line and no difference in the report -- the run simply is not the run the
    operator configured. `FAB_SLOT=999` below must change NOTHING and be named in the warnings; if it
    changed something it would be a lever nobody declared, and if it were silent it would be a run
    reported under a configuration it did not have.

    CANNOT CATCH: a name outside every declared family. `FABRIC_SLOTS` does not start with any
    PREFIX + "_", so it is skipped in silence -- G9 is a near-miss net inside the families, not a
    spell-checker over the environment. Nor does anything here notice a knob that is spelled correctly
    and MEANT wrongly.
    """
    findings = []
    with packages():
        configs, wires, warnings = _build(environ=ENV)
        unread = [w for w in warnings if w.startswith("UNREAD ")]
        others = [w for w in warnings if not w.startswith("UNREAD ")]

        if len(unread) != 1:
            findings.append(f"{len(unread)} UNREAD warning(s); exactly one was planted. Warnings: "
                            f"{warnings}")
        # THE REPORTED NAME IS PARSED OUT OF THE WARNING, NOT MATCHED AS A SUBSTRING. The line about a
        # near miss also carries its SUGGESTIONS, so `"FAB_SLOTS" in warning` is TRUE of the warning
        # about FAB_SLOT -- the first run of this check reported the correctly spelled knob as unread,
        # which is a test firing on its own message format rather than on the code under it.
        reported = {m.group(1) for m in (re.match(r"^UNREAD (\S+):", w) for w in unread) if m}
        if reported != {TYPO_KNOB}:
            findings.append(f"the typo net reported {sorted(reported)}; exactly {{{TYPO_KNOB!r}}} was "
                            f"planted as a near miss.")
        typo_line = next((w for w in unread if w.startswith(f"UNREAD {TYPO_KNOB}:")), None)
        if typo_line is None:
            findings.append(f"{TYPO_KNOB} was NOT reported. A near miss of a declared name is silently "
                            f"the default, which is a run that is not the run that was configured.")
        elif TYPO_MEANT not in typo_line:
            findings.append(f"{TYPO_KNOB} was reported without naming {TYPO_MEANT}: {typo_line!r}. The "
                            f"suggestion is the whole value of the report -- an operator who could see "
                            f"the misspelling would not have made it.")
        if FOREIGN_KNOB in reported:
            findings.append(f"{FOREIGN_KNOB} was reported. It is in nobody's family, and a typo net "
                            f"that warns about the operator's own environment gets ignored, which is "
                            f"the same as being switched off.")
        if GOOD_KNOB in reported:
            findings.append(f"{GOOD_KNOB} was reported as unread; it is declared and it was read.")
        if others:
            findings.append(f"unexpected non-UNREAD warning(s): {others}")

        # THE SUGGESTION MUST BE THE NEAREST ONE, AND THE NEAREST ONE MUST BE UNAMBIGUOUS. registry
        # ranks with `sorted(known, key=_dist)` over a SET, and Python randomises str hashing per
        # process, so set iteration order differs between runs: if two declared names tied at the
        # minimum distance, which one came first would vary from process to process and this assertion
        # would be intermittently wrong -- a flaky test being the second-worst kind of check there is.
        # So the tie is checked rather than assumed, using registry's own _dist. Not a second edit
        # distance implementation: a second one could disagree with the first and would then be
        # asserting its own arithmetic.
        known = sorted(registry.all_env_names())
        dists = sorted((registry._dist(TYPO_KNOB, n), n) for n in known)
        nearest = [n for d, n in dists if d == dists[0][0]]
        if len(nearest) != 1:
            findings.append(f"{TYPO_KNOB} is equidistant from {nearest}; this file's fixture must plant "
                            f"a typo with ONE nearest declared name, or the assertion above depends on "
                            f"set iteration order.")
        elif nearest[0] != TYPO_MEANT:
            findings.append(f"nearest declared name to {TYPO_KNOB} is {nearest[0]}, not {TYPO_MEANT}.")

        # AND THE MISSPELLED KNOB MUST HAVE DONE NOTHING. This is the half of the defect the warning
        # describes: `FAB_SLOT=999` is not a knob, so 999 must appear in no lever and no d_ field.
        landed = _landed(configs)
        if configs["FAB"].slots == int(TYPO_VALUE):
            findings.append(f"{TYPO_KNOB} changed FAB.slots. A misspelled name must reach nothing at "
                            f"all; a name that half-works is worse than one that does not.")
        seen_999 = sorted(d for d, v in landed.items() if isinstance(v, int) and v == int(TYPO_VALUE))
        if seen_999:
            findings.append(f"the misspelled value {TYPO_VALUE} reached {seen_999}.")
        if TYPO_KNOB in {n for cfgs in configs.values() for n in cfgs.given()}:
            findings.append(f"{TYPO_KNOB} was recorded as given; it is not a declared lever.")

        # G9 DEGRADES LOUDLY, NOT SILENTLY. build(environ=None) resolves levers correctly -- from_env
        # is the only code allowed to name os.environ and it resolves None itself -- but this file
        # never sees the mapping, so the typo net has nothing to scan. That state must be a warning
        # rather than a clean build, because a clean build with the net off is indistinguishable from
        # a clean build with the net on.
        try:
            _, _, warn_none = _build(environ=None)
            if not any("TYPO NET SKIPPED" in w for w in warn_none):
                findings.append("build(environ=None) did not warn that the typo net was skipped. An "
                                "unrun check that reports nothing is an unrun check that reads as a "
                                "passing one.")
        except LeverError as e:
            # The process environment genuinely holds one of these names, with a value that will not
            # coerce. Reported rather than swallowed: it is a real finding about the shell this ran in.
            findings.append(f"build(environ=None) raised against the real process environment: {e} "
                            f"-- that is a finding about the shell this ran in, not about src/: the "
                            f"production path is right to refuse a knob it cannot coerce.")

    detail = (f"{len(ENV)} environment name(s) scanned against {len(known)} declared lever(s): "
              f"{len(unread)} reported unread, nearest to {TYPO_KNOB} is "
              f"{nearest[0] if len(nearest) == 1 else nearest} at distance {dists[0][0]}")
    return _report("A2", "the typo net names the near miss and leaves the foreign name alone",
                   not findings, detail, findings, vacuous=not known)


# ==================================================================================================
# A3 -- affects(), the isolation sweep's only oracle
# ==================================================================================================

def check_a3_affects():
    """affects(L) = {owner(L)} u {owner(d) : L in reads(d)}, computed from the ledger the wiring wrote.

    WHY THIS IS THE LOAD-BEARING ONE. L3 -- flip a lever, run 200 seeded CPU steps, diff per-package
    fingerprints against the tests/test_determinism.py noise floor -- is the only check in this project
    that can see a coupling through shared state, RNG draw order or the data. It compares the measured
    reach against this set. An affects() that is too WIDE makes the sweep unfalsifiable; one that is too
    NARROW makes a correct response read as a leak, and the demonstrated compute escape produced exactly
    that: MEM.d_source_slots moved with FAB_MANAGE_EVERY while affects("FAB_MANAGE_EVERY") == {"FAB"}.

    CANNOT CATCH: whether the ledger is COMPLETE. Nothing here can; that is the sweep's job and the
    reason affects() is computed from the ledger rather than hand-declared in a table the same author
    would have written.
    """
    findings = []
    # Written out rather than derived from COUPLINGS: deriving the expectation from the same table
    # affects() reads would assert only that two loops agree. These are read off the reason column.
    EXPECT = {
        "FAB_SLOTS":           {"FAB", "DOM", "MEM", "CAP"},  # domain namespace, store size, and the
                                                             # hard ceiling the valve lifts toward
        "OPT_BATCH_WINDOWS":   {"OPT", "FAB", "TOK"},  # both cap-lift cadences and the manage cadence
        "CAP_PIN_WINDOWS":     {"CAP", "FAB", "TOK"},  # the valve's threshold, converted for both caps
        "LM_VOCAB_SLOTS":      {"LM", "TOK", "CAP"},   # emb.weight and head.weight have exactly V rows,
                                                       # and that is what the vocabulary cap lifts toward
        "LM_MASK_DEAD_ROWS":   {"LM", "CAP"},          # the honesty precondition on the vocabulary arm
        "TOK_MAX_BYTES":       {"TOK", "LM"},          # ByteComposer's byte tables are this tall
        "FAB_COMP_EMA":        {"FAB", "DOM"},         # one smoothing rate for two populations
        "FAB_COMP_PROTECT":    {"FAB", "DOM"},         # one brake policy for two populations
        "OPT_LR":              {"OPT", "FAB"},         # the peak the per-expert envelope is built from
        "OPT_LR_MIN_FRAC":     {"OPT", "FAB"},         # the floor that envelope anneals toward
        "CKPT_DIR":            {"CKPT", "TOK"},        # the run's own vocabulary lands beside its ckpt
        "CKPT_RESUME":         {"CKPT", "TOK"},        # the parent's vocabulary is read by the same rule
        # ---- levers that feed no WIRE. Four different shapes, all of which must read {owner}: ----
        "FAB_MANAGE_EVERY":    {"FAB"},   # read by a coupling, but through the DESTINATION's own levers
        "MEM_QUOTA":           {"MEM"},   # same shape, on the receiving side of a cross wire
        "MEM_OWNERS":          {"MEM"},   # folded with FAB.slots by two wires, and read as MEM's own
        "OPT_ACCUM":           {"OPT"},   # feeds a LOCAL coupling: a d_ field, and still no edge
        "FAB_PRESSURE":        {"FAB", "CAP"},  # WAS {"FAB"}: it fed only the fabric's LOCAL coupling,
                                          # which books no edge. The valve's startup refusal needs the
                                          # SAME settling point, so the identical derive call lands a
                                          # second time on CAP -- and that landing is a real edge.
        "LM_CTX":              {"LM"},    # a single-source LOCAL coupling: still a d_ field, still no edge
        "DOM_MIN_SUPPORT":     {"DOM"},   # feeds nothing at all
        "SIG_TRAIN_EVERY":     {"SIG"},   # feeds SIG.d_idle_cadence, whose OTHER end is also SIG's:
                                          # a LOCAL coupling books no edge, so the reach stays {SIG}
                                          # even though the value genuinely moves. That is the same
                                          # shape LM_CTX and OPT_ACCUM have above, and it is why
                                          # ISSUES P1-H53 -- the relation declared in a comment and
                                          # nowhere else -- was invisible to affects() as well.
        "SIG_TRAIN_EVERY_IDLE": {"SIG"},  # the other end of that coupling
        "RUN_SEED":            {"RUN"},   # deliberately NOT wired -- see NOT_WIRES, and A7
    }
    with packages():
        configs, wires, warnings = _build(environ=ENV)

        # No env_owner override: this resolves through registry.all_env_names(), which is the production
        # path and the branch tests/test_couplings.py cannot reach with unregistered doubles.
        for name in sorted(EXPECT):
            try:
                got = wires.affects(name)
            except WireError as e:
                findings.append(f"affects({name!r}) raised: {e}")
                continue
            if set(got) != EXPECT[name]:
                findings.append(f"affects({name!r}) = {sorted(got)}, expected "
                                f"{sorted(EXPECT[name])}. A reach that is too wide makes the isolation "
                                f"sweep unfalsifiable; too narrow and a correct response reads as a leak.")
        missing = sorted(set(registry.all_env_names()) - set(EXPECT))
        if missing:
            findings.append(f"declared lever(s) with no expectation in this check: {missing}. Every "
                            f"lever the fixture declares must have a stated reach, or the oracle is "
                            f"only checked where somebody remembered to check it.")

        # AN UNKNOWN NAME IS FATAL, NOT AN EMPTY SET. frozenset() for an unknown lever would make the
        # sweep pass for it forever: "measured reach is a subset of {}" fails loudly, but "no package
        # moved" against an empty oracle is a green tick, and a lever renamed on one side only would go
        # untested from that day on.
        try:
            wires.affects("FAB_SLTOS")
            findings.append("affects() answered for an undeclared name instead of raising. An unknown "
                            "lever with an empty reach is a permanently green sweep.")
        except WireError:
            pass

        if wires.unresolved():
            findings.append(f"the ledger has unresolved source(s): {wires.unresolved()}. A source that "
                            f"does not resolve to a declared lever drops its edge out of affects(), and "
                            f"a smaller oracle makes the sweep pass by having nothing to compare.")

        # The package graph is the same claim at package granularity, which is where the sweep measures.
        # TOK IS NO LONGER A PURE SINK, and that is the one structural change in this graph. It
        # sources LM.d_max_token_bytes (ByteComposer's byte tables are max_bytes rows tall), so it
        # appears as a key AND as a target. That is legal and it is not chaining: no coupling reads a
        # d_ field, so LM's incoming value is TOK's own lever and affects() stays one hop.
        want_graph = {"CAP": ("FAB", "TOK"), "CKPT": ("TOK",), "FAB": ("CAP", "DOM", "MEM"),
                      "LM": ("CAP", "TOK"), "OPT": ("FAB", "TOK"), "TOK": ("LM",)}
        if wires.graph() != want_graph:
            findings.append(f"wires.graph() = {wires.graph()}, expected {want_graph}. Packages that only "
                            f"receive must appear as targets and never as keys -- a sink cannot leak "
                            f"onward, and affects() is one hop.")

    detail = (f"{len(EXPECT)} declared lever(s) checked against the ledger's computed reach: "
              f"{sum(1 for v in EXPECT.values() if len(v) > 1)} feed a wire, "
              f"{sum(1 for v in EXPECT.values() if len(v) == 1)} reach only their owner")
    return _report("A3", "affects() computes the reach for a wired lever and {owner} for an unwired one",
                   not findings, detail, findings, vacuous=not EXPECT)


# ==================================================================================================
# A4 -- render(), the printable graph docs/03_WIRING.md is generated from
# ==================================================================================================

_HEADING = re.compile(r"^--- (?P<title>[^-].*?) ---$")


def _sections(text):
    """Split render()'s output into its `--- TITLE (n) ---` blocks.

    The guard against a title that starts with a dash is not decoration: the embedded ledger from
    wire.Wires.render draws a rule of bare hyphens under its header, which matches a naive
    `^---.*---$` and would silently become a section of its own.
    """
    out, cur = {}, None
    for line in text.splitlines():
        m = _HEADING.match(line.strip())
        if m:
            cur = m.group("title")
            out[cur] = []
        elif cur is not None:
            out[cur].append(line)
    return out


def check_a4_render():
    """The rendered table names every coupling and separates the irreducible ones from the chosen ones.

    WHY THE SPLIT IS THE POINT. An irreducible coupling is a claim about arithmetic -- pressure x slots
    IS the equilibrium population -- and no refactor removes it. A chosen coupling is a decision, and a
    reader deciding whether to keep it has to be able to see that it is one. Printed together, the whole
    list reads as inevitable, which is how a coupling graph stops being reviewed.

    CANNOT CATCH: whether a reason is TRUE. `_check_why` refuses the empty string, the single word and
    the placeholder list, and nothing can do better -- a reason is prose. What the renderer owes the
    reader instead is the reason printed IN FULL beside the number it explains, which is checked here.
    """
    findings = []
    with packages():
        configs, wires, warnings = _build(environ=ENV)

        # render() RETURNS text and PRINTS NOTHING -- a documented promise, and one worth checking: a
        # doc generator that also writes to stdout corrupts whatever else is being printed, and this
        # file's own report is the first casualty.
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            text = assemble.render(configs, wires)
        if buf.getvalue():
            findings.append(f"render() wrote {len(buf.getvalue())} char(s) to stdout; it returns text "
                            f"and prints nothing, so docs generation cannot corrupt a report.")

        sections = _sections(text)
        irr = [c for c in assemble.COUPLINGS if c.irreducible]
        red = [c for c in assemble.COUPLINGS if not c.irreducible]
        irr_block = "\n".join(sections.get(f"IRREDUCIBLE ({len(irr)})", []))
        red_block = "\n".join(sections.get(f"DECLARED, REDUCIBLE ({len(red)})", []))
        if not irr_block or not red_block:
            findings.append(f"render() did not produce both blocks with their counts; sections found: "
                            f"{sorted(sections)}")

        for c in assemble.COUPLINGS:
            mine, theirs = (irr_block, red_block) if c.irreducible else (red_block, irr_block)
            # MATCH THE RENDERED ROW, NOT THE NAME ANYWHERE IN THE BLOCK. A bare substring test put
            # FAB.d_operating_population in "the wrong block" the moment another coupling's REASON
            # column mentioned it by name -- which reason columns are supposed to do, since they
            # exist to explain a row by pointing at its siblings. The anchor is render()'s own row
            # header, "-> DST = ", so prose about a coupling is no longer indistinguishable from the
            # coupling. Strictly narrower than the substring test, not looser: a dst rendered under
            # the wrong heading still fails.
            anchor = f"-> {c.dst} = "
            mine, theirs = (anchor in mine), (anchor in theirs)
            if not mine:
                findings.append(f"{c.dst} is {'irreducible' if c.irreducible else 'reducible'} and is "
                                f"not rendered in that block of the graph.")
            if theirs:
                findings.append(f"{c.dst} appears in the wrong block: an irreducible coupling is a "
                                f"statement about arithmetic and a reducible one is a decision.")
            if c.why not in text:
                findings.append(f"{c.dst}: the reason is missing or truncated in the rendered graph. A "
                                f"justification cut off at the column edge reads as justified.")
            if f"-> {c.dst} = " not in text:
                findings.append(f"{c.dst} is printed without its resolved value; every package is "
                                f"registered on this build, so there is no deferred row.")
            if c.local and "(intra-package)" not in text:
                findings.append(f"{c.dst} is intra-package and the graph does not say so.")
        if "DEFERRED" in text:
            findings.append("render() reports a DEFERRED row on a build where every package is present.")

        # The rejections and the compute allowlist are part of the document for the same reason the
        # reasons are: a reader is being asked to believe these rows are the WHOLE coupling graph, and
        # that claim rests on what a compute is unable to reach and on what was considered and refused.
        for cand, _why in assemble.NOT_WIRES:
            if cand not in text:
                findings.append(f"the rejected candidate {cand!r} is not printed. A rejection with a "
                                f"reason is the only thing that stops the same candidate being added "
                                f"next quarter by someone who cannot tell it was considered.")
        for name in assemble.COMPUTE_ALLOWLIST:
            if f"\n  {name}\n" not in text:
                findings.append(f"COMPUTE_ALLOWLIST entry {name!r} is not printed; a guarantee whose "
                                f"edge nobody can see is a guarantee nobody audits.")
        # The ledger is rendered by wire.Wires.render, not restated here -- the old tree had a report
        # path and an audit path formatting one quantity two ways, and they drifted.
        if f"{len(wires)} wires of {wires.budget} budgeted" not in text:
            findings.append("the embedded ledger table is missing from the rendered graph.")
        for line in (f"{len(assemble.COUPLINGS)} declared, {len(assemble.COUPLINGS)} resolved, "
                     f"0 deferred; {len(wires)} of {wires.budget} wire budget spent.",):
            if line not in text:
                findings.append(f"the summary line is wrong or missing; expected {line!r}")
        for p in sorted(wires.graph()):
            if f"  {p} -> " not in text:
                findings.append(f"the package graph does not print the edges out of {p}.")

    detail = (f"{len(text.splitlines())} line(s) rendered: {len(irr)} irreducible and {len(red)} "
              f"reducible coupling(s) in {len(sections)} section(s), "
              f"{len(assemble.NOT_WIRES)} rejected candidate(s), "
              f"{len(assemble.COMPUTE_ALLOWLIST)} allowlisted name(s)")
    return _report("A4", "render() names every coupling and separates the irreducible ones",
                   not findings, detail, findings, vacuous=not assemble.COUPLINGS)


# ==================================================================================================
# A5 -- assemble runs ONCE
# ==================================================================================================

def check_a5_build_runs_once():
    """A Config that has already been frozen refuses a second build, and the wire budget bites.

    WHAT "A SECOND BUILD IS REFUSED" ACTUALLY MEANS, because the obvious reading is not a property this
    spine has. Calling build() twice against the registry succeeds: each call mints FRESH Configs
    through from_env, and two independent resolutions of the same declarations are not a fault. The
    guarantee is narrower and it is about the OBJECT -- "every Config is frozen before build() returns,
    so there is no re-resolve and no second reader: the report reads the same object the run used." So
    the check has to route the already-frozen Configs back in, which is exactly the shape that tempts
    somebody into caching: a from_env that hands back the one resolved Config. The old tree needed a
    SECOND environment reader (`_cfg`) purely because the ordinary one had a side effect, and both could
    be called at any point in a run -- which is how a knob acquired five defaults.

    CANNOT CATCH: a package that never goes through build() at all. Nothing here sees a module that
    resolves its own levers; that is tests/test_ownership.py's O8 (from_env outside the wiring file).
    """
    findings = []
    with packages():
        configs, wires, warnings = _build(environ=ENV)
        before = _landed(configs)

        def replay(cfg):
            """A LeverSet whose from_env hands back an ALREADY RESOLVED, already frozen Config."""
            owner = type(f"{cfg.prefix}Replay", (), {"PREFIX": cfg.prefix, "_levers": {}})
            owner.from_env = classmethod(lambda cls, environ=None, _c=cfg: _c)
            return owner

        try:
            _build(environ=ENV, sets={p: replay(c) for p, c in configs.items()})
            findings.append("a second build() over already-frozen Configs succeeded. A Config that can "
                            "still be written after startup is a Config the report cannot claim the run "
                            "used, and a value written twice is the silent-overwrite class -- 29 of the "
                            "survey's 475 records, the one that leaves no trace in any log.")
        except LeverError as e:
            if "freeze" not in str(e):
                findings.append(f"the second build was refused, but not by the freeze: {e}")

        after = _landed(configs)
        if after != before:
            changed = sorted(k for k in after if before.get(k) is not after[k])
            findings.append(f"the refused build mutated {changed}. A build that fails part way must "
                            f"leave nothing behind, or the Configs describe neither run.")

        # The same refusal from the other side, at the seam the second build rides on.
        try:
            configs["FAB"]._wire("d_late", 1)
            findings.append("a Config accepted a wire after build() returned.")
        except LeverError:
            pass
        # A FLAG IS NOT A STATE: the first version of _freeze set a flag that only _wire consulted, so
        # `cfg._vals['slots'] = 8` walked straight past it. The mappings themselves must be read-only.
        try:
            configs["FAB"]._vals["slots"] = 8
            findings.append("a frozen Config's value mapping is still writable; freezing must be a "
                            "state, not a flag that only one method consults.")
        except TypeError:
            pass

        # THE BUDGET BITES. WIRE_BUDGET is a speed bump rather than a guarantee, and build() takes a
        # `budget` parameter that exists so a test can prove it without editing the constant -- which,
        # until this line, nothing did. A budget that has never been observed to refuse anything is
        # indistinguishable from a budget that is never consulted.
        try:
            _build(environ=ENV, budget=len(wires) - 1)
            findings.append(f"build() accepted {len(wires)} wires against a budget of {len(wires) - 1}.")
        except WireError as e:
            if "WIRE_BUDGET" not in str(e):
                findings.append(f"the over-budget build was refused by something else: {e}")

    detail = (f"{len(before)} frozen d_ field(s) across {len(configs)} Config(s); second build refused, "
              f"ledger of {len(wires)} refused at budget {len(wires) - 1}")
    return _report("A5", "build() runs once: a frozen Config refuses a second build, the budget bites",
                   not findings, detail, findings, vacuous=not before)


# ==================================================================================================
# A6 -- a coupling whose packages are absent is DEFERRED, and says so
# ==================================================================================================

def check_a6_deferred_is_visible():
    """A declared coupling that was not made must be visible as such -- in the warnings and in the graph.

    THIS IS THE FILE'S OWN SUBJECT, TURNED ON ITSELF. Skipping an unbuildable coupling in silence is the
    untrippable-guard shape (60 of the survey's 475 records): the printed graph would show an edge that
    was never made, and affects() would hand the isolation sweep a reach the run does not have -- which
    reads as the sweep passing. The whole tree was in that state until the packages landed: no package
    registered, every row deferred, and a wrong endpoint indistinguishable from a right one. It is not
    any more (spine/assemble.py imports all thirteen and _check_endpoints refuses a name nobody owns), so
    the deferral is exercised HERE, on a deliberately partial build, rather than being the default.

    AND THE ORACLE SHRINKS WITH THE BUILD, which is the part worth staring at. affects() is computed
    from the ledger, and a deferred coupling books no edge, so on a partial build a lever's declared
    reach is SMALLER than the declaration says -- no exception, no second warning. The DEFERRED lines in
    build()'s warnings are the only thing standing between that and a sweep that passes because its
    oracle got smaller.
    """
    findings = []
    present = ("FAB", "MEM", "OPT")
    with packages() as P:
        part = {p: P[p] for p in present}
        configs, wires, warnings = _build(environ=ENV, sets=part)
        landed = _landed(configs)

        absent = [c for c in assemble.COUPLINGS if set(c.prefixes) - set(present)]
        made = [c for c in assemble.COUPLINGS if not set(c.prefixes) - set(present)]
        deferred_warnings = [w for w in warnings if w.startswith("DEFERRED ")]
        if len(deferred_warnings) != len(absent):
            findings.append(f"{len(deferred_warnings)} DEFERRED warning(s) for {len(absent)} coupling(s) "
                            f"whose packages are missing. Warnings: {warnings}")
        for c in absent:
            if not any(c.dst in w for w in deferred_warnings):
                findings.append(f"{c.dst} was skipped without a warning naming it. A coupling that is "
                                f"declared and not made must not be indistinguishable from one that was.")
            if c.dst in landed:
                findings.append(f"{c.dst} landed a value on a build where its packages are absent.")
        for c in made:
            if c.dst not in landed:
                findings.append(f"{c.dst}: every package it names is present and it did not arrive.")

        text = assemble.render(configs, wires)
        for c in absent:
            if f"{c.src_text} -> {c.dst}" not in text:
                findings.append(f"{c.dst} is missing from the rendered deferred list.")
        if "DEFERRED -- not made on this build" not in text:
            findings.append("the rendered graph marks no row DEFERRED, on a build with "
                            f"{len(absent)} unmade coupling(s). A deferred row printed with a "
                            f"placeholder value reads as a value at a glance.")
        # No placeholder that could be mistaken for a number: the row carries its unit and its status.
        if "'<not resolved>'" in text:
            findings.append("a deferred row prints a quoted placeholder where every other row has a "
                            "number.")

        # The oracle really did shrink, and only the warning says so. LM_VOCAB_SLOTS reaches TOK on a
        # full build; here TOK is absent, the edge was never made, and affects() -- which is computed
        # from the LEDGER and not from the table -- answers with the owner alone. It does not raise:
        # every stand-in is registered, only `sets=` is narrowed, so the lever is declared and its reach
        # is honestly smaller.
        if set(wires.affects("LM_VOCAB_SLOTS")) != {"LM"}:
            findings.append(f"affects('LM_VOCAB_SLOTS') = {sorted(wires.affects('LM_VOCAB_SLOTS'))} on a "
                            f"build where TOK is absent; the edge was not made, so the reach cannot "
                            f"include TOK.")

    detail = (f"{len(present)} of {len(P)} package(s) registered: {len(made)} coupling(s) made, "
              f"{len(absent)} deferred, {len(deferred_warnings)} warning(s), {len(wires)} wire(s)")
    return _report("A6", "a coupling whose packages are absent is deferred and says so",
                   not findings, detail, findings, vacuous=not absent)


# ==================================================================================================
# A7 -- rng.issued(), the accounting NOT_WIRES points at
# ==================================================================================================

@contextlib.contextmanager
def _issued_sandbox():
    """Run with an empty stream ledger and put the process's own back afterwards.

    reset_issued() alone would be wrong here: another test module in the same process may hold streams,
    and clearing them would make ITS duplicate-stream guard stop refusing. The ledger is bookkeeping and
    nothing in it is ever read by a draw, so snapshotting it cannot change a number any run produces.
    """
    before = dict(rng._ISSUED)
    rng.reset_issued()
    try:
        yield
    finally:
        rng.reset_issued()
        rng._ISSUED.update(before)


def check_a7_rng_accounting():
    """issued() must distinguish drew / armed-but-inert / never asked -- graft G4's three states.

    WHY THIS IS IN THE ASSEMBLE TEST. spine/assemble.py's NOT_WIRES rejects `RUN.seed -> every
    package's d_seed` and names its replacement explicitly: "The check that catches that is rng.issued(),
    which records every stream handed out, so a subsystem with zero draws reads armed-but-inert and a
    subsystem that never asked does not appear at all -- two different statements the report must be able
    to make (G4)." render() prints that rejection to docs/03_WIRING.md. A rejection is only as good as
    the mechanism it points at, and that mechanism had no caller in this tree either, so the document
    was making a claim on behalf of an untested function. The seed below comes off the assembled Config
    rather than from a literal, which is the shape the rejection is arguing for: per-subsystem streams
    keyed by name, from one declared run seed.

    CANNOT CATCH: a stream handed to the WRONG subsystem. An Rng is an ordinary object and does not check
    who is drawing from it; that shows up here only as the true owner's name being absent from the list.
    """
    findings = []
    with packages(), _issued_sandbox():
        configs, _wires, _warnings = _build(environ=ENV)
        seed = configs["RUN"].seed

        if rng.issued():
            findings.append(f"the stream ledger was not empty at the start: {sorted(rng.issued())}")

        fabric = rng.rng_for("fabric", seed)
        memory = rng.rng_for("memory", seed)         # armed, and deliberately never drawn from
        for _ in range(3):
            fabric.random()

        issued = rng.issued()
        if sorted(issued) != ["fabric", "memory"]:
            findings.append(f"issued() = {sorted(issued)}; exactly the two streams handed out should "
                            f"appear.")
        if "domains" in issued:
            findings.append("a subsystem that never asked for a stream appears in the ledger.")
        for name in ("fabric", "memory"):
            want = (rng.derive_seed(name, seed), seed)
            if issued.get(name) != want:
                findings.append(f"issued()[{name!r}] = {issued.get(name)!r}, expected {want!r}: the "
                                f"derived seed is keyed by the subsystem NAME, not by declaration order "
                                f"-- offset seeding collides across runs and reseeds every subsystem "
                                f"after an inserted one.")
        # THE THREE STATES, WHICH IS THE WHOLE POINT. "memory" is present with zero draws (armed but
        # inert -- 57 of the survey's 475 records, and the class this test file was written about);
        # "domains" is absent (never asked). A report that could only say "no randomness observed" could
        # not tell those apart.
        if (fabric.draws, memory.draws) != (3, 0):
            findings.append(f"draws = {(fabric.draws, memory.draws)}, expected (3, 0). `.draws` is what "
                            f"makes 'armed but 0' a fact about the run rather than a guess.")
        if rng.derive_seed("fabric", seed) == rng.derive_seed("memory", seed):
            findings.append("two subsystems derived the same stream seed from one run seed.")
        if rng.derive_seed("fabric", seed) == rng.derive_seed("fabric", seed + 1):
            findings.append("one subsystem derived the same stream seed from two run seeds; the "
                            "between-seed spread (0.066-0.131 b/B) is the reason two seeds is a hard "
                            "rule, and it measures nothing if the streams are shared.")

        # ONE SUBSYSTEM, ONE STREAM PER RUN. A second generator for the same name and seed replays the
        # SAME sequence, so two call sites would draw identical "random" numbers while each believes it
        # has its own stream -- a correlation in the results with nothing in a log to see it by.
        try:
            rng.rng_for("fabric", seed)
            findings.append("a second stream was issued for one subsystem and seed.")
        except rng.RngError:
            pass
        if sorted(rng.issued()) != ["fabric", "memory"]:
            findings.append(f"the refused stream changed the ledger: {sorted(rng.issued())}")
        try:
            rng.rng_for("fabric", seed, again=True)   # the checkpoint-restore case, said at the call site
        except rng.RngError as e:
            findings.append(f"again=True was refused: {e}")

        # The ledger handed to a report must be a copy: a report that can clear it is a report that can
        # erase the evidence for its own DID IT FIRE line.
        snapshot = rng.issued()
        snapshot.clear()
        if sorted(rng.issued()) != ["fabric", "memory"]:
            findings.append("issued() handed out the live ledger; mutating the returned dict changed it.")

        rng.reset_issued()
        if rng.issued():
            findings.append("reset_issued() left entries behind; the isolation sweep runs many 200-step "
                            "runs in one interpreter and needs a clean ledger between them.")

    detail = ("2 stream(s) issued from the assembled RUN_SEED: 1 drew 3 time(s), 1 armed with 0 draws, "
              "1 subsystem never asked; duplicate refused, again=True admitted, reset clears")
    return _report("A7", "rng.issued() reflects the streams actually handed out",
                   not findings, detail, findings, vacuous=False)


# ==================================================================================================
# A8 -- a count written in prose about the WHOLE tree still matches the whole tree
# ==================================================================================================

# The four whole-tree quantities, and how to read each one off the live registry. NOT a snapshot: each
# entry is a callable, so the expected value is whatever the tree says at the moment the check runs.
#
# WHY A CHECK AND NOT A CORRECTED NUMBER. A8 exists because line 171 of this file said "declares 259
# levers" for two lever generations after the tree declared 261, and docs/03_WIRING.md -- a GENERATED
# file, carrying its own regeneration script in its header -- sat at 13 couplings and 10 wires against a
# live 23 and 19. Both were fixed by hand once already. A number a human corrects by hand is a number
# that drifts again on the next commit that changes the tree, and neither of those two was found by a
# check: they were found by a reviewer reading prose. That is the recorded-never-read defect wearing
# documentation's clothes.
_LIVE_COUNTS = {
    "levers": (lambda: sum(len(s._levers) for s in registry.all_sets().values()),
               "levers declared across src/*/levers.py"),
    "packages": (lambda: len(registry.all_sets()), "packages declaring a LeverSet"),
    "couplings": (lambda: len(assemble.COUPLINGS), "rows in spine.assemble.COUPLINGS"),
    "budget": (lambda: WIRE_BUDGET, "spine.wire.WIRE_BUDGET"),
}

# Each pattern's ONE capturing group is the stated number, and the key names which live quantity it
# claims. The phrasings are narrow on purpose. A blanket sweep for `\d+ levers` would collect "7 levers"
# from a paragraph describing ONE package and report a defect against a sentence that is true -- an
# oracle that cries wolf is switched off, and a switched-off oracle is the state A8 is here to prevent.
# What makes a phrasing eligible is that it names the whole tree in the same breath as the number:
# `src/*/levers.py`, `the N declared levers`, `N declared couplings`. Add a phrasing here when you write
# one; the VACUOUS line below is what tells you the population went to zero if you do not.
_STATED = (
    ("levers", re.compile(r"src/\*/levers\.py declares (\d+) levers")),
    ("levers", re.compile(r"(?:the|All) \**(\d+)\** (?:of the )?declared levers")),
    ("levers", re.compile(r"(?:the|All) \**(\d+)\** of the declared levers")),
    ("couplings", re.compile(r"(\d+) declared coupling")),
    ("budget", re.compile(r"of (\d+) wires")),
)

_SWEPT = ("tests/*.py", "docs/*.md", "src/spine/*.py")


def check_a8_stated_counts():
    """Every whole-tree count written in prose equals the count the live tree reports.

    HOW THIS CAN FAIL. Add a fourteenth package, or a lever, or a COUPLINGS row, and the sentences that
    state those totals become false in the same commit. A8 fails on that commit rather than two
    generations later, and it names the file and line, so the fix is a one-line edit and not an
    archaeology session.

    WHAT IT DOES NOT COVER, said plainly. A count stated in a phrasing not listed in _STATED is
    invisible to A8 -- this is an allowlist of sentence shapes, and an allowlist's failure mode is
    silence. Two things keep it honest: the detail line prints the population, so a phrasing that stops
    matching shows up as the number dropping; and VACUOUS fires if the whole sweep collects nothing,
    which is the state where A8 is green and looking at an empty set. docs/03_WIRING.md is NOT covered
    by a phrasing at all, and does not need to be: it is generated whole from assemble.render(), and A4
    checks the renderer. Its drift was a stale FILE, which is a different oracle -- regenerate and
    diff -- and that is A9, below.
    """
    findings, examined = [], 0
    for pattern in _SWEPT:
        for path in sorted(glob.glob(os.path.join(ROOT, pattern))):
            rel = os.path.relpath(path, ROOT)
            try:
                text = io.open(path, encoding="utf-8").read()
            except OSError as e:
                findings.append(f"{rel}: unreadable ({e})")
                continue
            for key, rx in _STATED:
                live_fn, what = _LIVE_COUNTS[key]
                live = live_fn()
                for m in rx.finditer(text):
                    examined += 1
                    stated = int(m.group(1))
                    if stated == live:
                        continue
                    line = text.count("\n", 0, m.start()) + 1
                    findings.append(
                        f"{rel}:{line} states {stated} where the tree has {live} {what} "
                        f"-- {m.group(0).strip()!r}")

    live_now = {k: fn() for k, (fn, _) in _LIVE_COUNTS.items()}
    detail = (f"{examined} stated count(s) swept across {len(_SWEPT)} glob(s); live tree: "
              f"{live_now['levers']} levers in {live_now['packages']} packages, "
              f"{live_now['couplings']} couplings, wire budget {live_now['budget']}")
    return _report("A8", "prose counts about the whole tree match the whole tree",
                   not findings, detail, findings, vacuous=(examined == 0))


# ==================================================================================================
# A9 -- docs/03_WIRING.md is what the generator would write right now
# ==================================================================================================

def check_a9_wiring_doc_current():
    """The generated coupling document on disk equals what tools/render_wiring.py produces today.

    WHAT THIS CATCHES THAT A8 CANNOT. A8 sweeps prose for stated totals; this file is not prose. It is
    the whole return value of assemble.render() plus a generated summary line, and it went stale by a
    whole ledger generation -- 13 couplings and 10 wires on disk against 23 and 19 in the tree -- while
    every check in this suite stayed green, because nothing read the file. That is the
    recorded-never-read family (39 of the survey's 475) with a document in the recorded position. A
    header that says "Nothing here is written by hand" is not a check; running the generator and
    diffing is.

    WHY IT IMPORTS A TOOL RATHER THAN RE-RENDERING. Rendering here and comparing would test that two
    call sites agree, which they would, since both would be this file's idea of how to render. The
    oracle has to be the thing the human is told to run: docs/03_WIRING.md's header names
    `python3 tools/render_wiring.py`, so A9 calls that module's `wiring_markdown()` and nothing else.
    If the generator is wrong, the document and the check are wrong together and A4 -- which reads
    render()'s sections directly -- is what disagrees.

    THE FAILURE IS ACTIONABLE BY DESIGN: the finding names the command that fixes it. A check whose
    remedy is a research task gets suppressed.
    """
    findings = []
    n_lines = 0
    try:
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import render_wiring
        want = render_wiring.wiring_markdown()
        have = io.open(render_wiring.DOC, encoding="utf-8").read()
        n_lines = len(want.splitlines())
        if have != want:
            hl, wl = have.splitlines(), want.splitlines()
            diff = [d for d in difflib.unified_diff(hl, wl, "on disk", "regenerated", n=0)
                    if d.startswith(("+", "-")) and not d.startswith(("+++", "---"))]
            findings.append(f"docs/03_WIRING.md is stale: {len(diff)} changed line(s). "
                            f"Regenerate with `python3 tools/render_wiring.py`.")
            for d in diff[:6]:
                findings.append(f"    {d[:160]}")
    except Exception as e:
        findings.append(f"could not run the generator: {type(e).__name__}: {e}")

    detail = (f"{n_lines} generated line(s) compared against docs/03_WIRING.md via "
              f"tools/render_wiring.py::wiring_markdown")
    return _report("A9", "the generated coupling document matches the live table",
                   not findings, detail, findings, vacuous=(n_lines == 0))


# ==================================================================================================
# The runner
# ==================================================================================================

CHECKS = (
    check_a1_build_resolves,
    check_a2_typo_net,
    check_a3_affects,
    check_a4_render,
    check_a5_build_runs_once,
    check_a6_deferred_is_visible,
    check_a7_rng_accounting,
    check_a8_stated_counts,
    check_a9_wiring_doc_current,
)


def main():
    print("=== the runtime spine: build(), the typo net, affects(), render(), the freeze ===")
    print(f"{len(assemble.COUPLINGS)} declared coupling(s), {WIRE_BUDGET} wire budget; "
          f"Python {sys.version.split()[0]}")
    print(f"registry on entry: {len(registry.all_sets())} package(s), "
          f"{len(registry.all_env_names())} declared lever(s) -- the nine below are sandboxed and "
          f"restored")
    print()
    failed = 0
    for check in CHECKS:
        try:
            failed += check()
        except Exception:                          # noqa: BLE001 -- a check that dies is a FAIL, not a
            failed += 1                            # traceback that hides the six checks after it
            print(f"FAIL  {check.__name__}  raised out of the check itself")
            for line in traceback.format_exc().strip().splitlines():
                print(f"      {line}")
        print()
    # WHAT "RESTORED" MEANS CHANGED WHEN THE PACKAGES LANDED, and the first form of this line became a
    # false alarm the moment they did. It read `if registry.all_sets():`, which was a correct statement of
    # "the sandbox leaked" only while the registry was expected to be EMPTY -- and spine.assemble now
    # imports thirteen real LeverSets, so a perfectly restored registry holds all thirteen. A check that
    # cannot tell a leak from the tree working is worse than no check, because it trains a reader to skip
    # the line. The comparison is against the snapshot taken before the first sandbox instead.
    if registry.all_sets() != REGISTRY_ON_ENTRY:
        leaked = sorted(set(registry.all_sets()) - set(REGISTRY_ON_ENTRY))
        lost = sorted(set(REGISTRY_ON_ENTRY) - set(registry.all_sets()))
        print(f"NOTE  the registry does not match what this file found on entry -- extra: {leaked}, "
              f"missing: {lost}. The sandbox in packages() failed to restore it.")
    print(f"=== {len(CHECKS)} checks, {failed} failing ===")
    print("These checks prove the wiring RUNS and that its declarations, its warnings and its printed")
    print("graph describe the same build. They do not prove the coupling graph is COMPLETE: a value")
    print("that travels through shared state, RNG draw order or the corpus writes no wire and names")
    print("nothing, and only L3 (tests/test_lever_isolation.py, against the tests/test_determinism.py")
    print("noise floor) is evidence about that.")
    print("One thing this file could not check, stated because it is a live blind spot rather than a")
    print("blind spot by design: G9's families come from the registry, so on a tree with no package")
    print("registered -- which is every tree up to P3 -- unread_env() returns [] for an environment of")
    print("pure garbage, silently. build() warns when it is handed environ=None; it does not warn when")
    print("there is nothing to compare against.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
