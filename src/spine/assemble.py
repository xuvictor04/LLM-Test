"""The one place the packages are wired together, and the only file allowed to hold more than one LeverSet.

WHY EXACTLY ONE FILE. Every other module in the tree receives its own `Config` as a parameter, and
SOMETHING has to hold all of them at once in order to compute the values that genuinely cross
boundaries. This file is that something, and keeping it to one file is what makes the coupling graph
finite and printable.

WHAT THAT BUYS, STATED CORRECTLY THIS TIME. The sentence that stood here was false and a reviewer proved
it. It read: "that is not a policy, it is an author-time NameError: there is no name in scope for another
package's levers, so reading one is not discouraged, it does not compile into anything that runs." There
is no NameError. `build()` returns `{PREFIX: Config}`, a Config is an ordinary object that does not know
who is holding it, and a function handed one reads all of it:

    def memory_prune(cfg): return cfg.slots        # memory_prune(configs["FAB"]) -> 2048, silently

That sentence was load-bearing in the worst way -- an overclaim in a docstring is the reason a reviewer
stops looking, and this one sat directly over the hole it denied. What is actually true is narrower, and
every clause of it has a check standing behind it, because a claim with no check is the same overclaim
written more carefully:

  * A MODULE CANNOT MINT A FOREIGN CONFIG. It may not name os.environ (O1); it may not hold two lever
    sets, under any alias, since the count is by resolved origin (O3); and it may not call `from_env` at
    all outside this file (O8). The only door to a Config is `build()`, and the entry point is the only
    caller of `build()`.
  * A FUNCTION CANNOT HOLD TWO PACKAGES BY SIGNATURE. O9 refuses a function outside this file with two
    Config-annotated parameters -- the shape that would let one function read across a boundary with no
    wire and no ledger row.
  * A FUNCTION THAT RECEIVES ONE STILL HAS TO SAY WHOSE IT IS. `Config.owned_by("MEM")` is the assertion
    at the point of use, it raises naming both packages, and O9 requires it of every Config-annotated
    parameter outside the spine.
  * WHAT REMAINS UNCOVERED, SAID PLAINLY: an UNANNOTATED parameter handed a foreign Config in a function
    that never asserts ownership. No static check in this tree can see that -- there is nothing in the
    text to look at -- and no wording here should imply otherwise. It is one deliberate call at the entry
    point, and it is L3's territory: flip a lever, run the seeded steps, watch whose fingerprint moves.

THE DESIGN-REVIEW FINDING THIS FILE HAS TO ANSWER, verbatim: "wires can launder couplings, because once
`fabric.slots` arrives in `domains` as a local named `expert_slots` the read site looks like an owned value
again." That is true of any wiring scheme where the receiver names the field. Three mechanisms answer it,
and all three are structural -- none of them is a convention a reader has to remember:

  1. THE WIRE NAMES THE FIELD, NOT THE RECEIVER. The destination is part of the declaration below
     (`dst="DOM.d_expert_slots"`), and `Wires.add(..., into=cfg)` performs the assignment itself. The
     receiving package is never handed a chance to choose a name. `Config._wire` then refuses any name
     that is not `d_`-prefixed, and `Wire.__init__` refuses the same name in the ledger, so the record
     and the assignment cannot describe different systems. The consequence is the one that matters:
     `grep -rn 'd_' src/` enumerates every coupling with no tooling.

  2. THE WIRING FUNCTION CANNOT READ WHAT IT DID NOT DECLARE. This is the part the `d_` prefix alone does
     not cover, and it is where the first draft of this file leaked. A `compute` that is handed the whole
     `{PREFIX: Config}` map can read any package's levers while declaring one source, and the ledger --
     which is the oracle for the L3 isolation sweep (G1) -- then understates that lever's reach and the
     sweep goes green on a real leak. So `compute` is handed `_Reads`, a view that exposes exactly the
     fields named in `src`, plus the destination package's OWN levers, and raises on anything else.

     THAT IS ONE HALF, AND THE SECOND DRAFT LEAKED THROUGH THE OTHER. `_Reads` restricts the ARGUMENT.
     It cannot restrict the CLOSURE, and a compute that ignores `r` and calls a helper reads whatever the
     helper reads -- with every check in the tree still green. So a compute's free names are checked at
     CONSTRUCTION, against `COMPUTE_ALLOWLIST` below, which is the only place the permitted names are
     written down. Between the two, the declared `reads` set is enforced rather than advisory: the view
     covers what arrives through `r`, and the allowlist covers everything that does not.

  3. THE COUPLINGS ARE DATA, NOT CALLS. `COUPLINGS` below is a list of records. `render()` prints it
     without resolving a single environment variable, so `docs/03_WIRING.md` can be regenerated on a
     machine that cannot run the system, and a coupling added in a commit shows up as a row in a table
     rather than as a line of code somewhere in a 200-line function.

WHY THE DESTINATION PACKAGE'S OWN LEVERS ARE READABLE BY `compute`, AND WHY THAT IS NOT A HOLE.
`MEM.d_capacity` is `min(fab.slots, mem.owners) * mem.quota`. Two of those three are MEM's own. `wire.py`
refuses to record a source in the same package as the destination, and it is right to: `affects(L)` is
`{owner(L)} u {owner(d) : L in reads(d)}`, so an edge from MEM to MEM adds MEM to a set that already
contains MEM by ownership. It costs a budget line and buys nothing. The local reads are therefore made
through the view but not booked in the ledger, and the oracle is unchanged by the omission. What IS booked
is `FAB.slots`, the only source that widens anybody's reach.

TWO KINDS OF COUPLING LIVE IN THE TABLE, AND ONLY ONE OF THEM IS A WIRE.

  CROSS -- more than one package. Goes in the `Wires` ledger, spends budget, widens `affects()`, appears
  in the printed graph as an edge.

  LOCAL -- more than one LEVER, one package. `fabric.pressure x fabric.slots -> fabric.d_operating_population`
  is the canonical case and PLAN section 4 uses it as the reason the lever rule is stated as L1/L2/L3 and
  not as "levers are independent". It is still `d_`-prefixed, because graft G5 is written about values
  computed from more than one LEVER, not more than one package -- `grep d_` must find it too. It is NOT a
  wire: it is a `spine.derive` function whose answer is written onto its own owner's Config, it books no
  edge, and it spends no budget. Recording it as a wire would inflate the coupling graph with edges that
  cannot leak anywhere, which makes the graph less useful exactly in proportion to how carefully it is read.

WHAT CHANGED WHEN THE REAL PACKAGES ARRIVED, because a table that was written against stand-ins and then
silently kept working would be the worst possible outcome. Thirteen levers.py files landed under src/,
this file now imports all thirteen, and four of the ten declared rows turned out to name declarations
that do not exist:

  * `TRAIN` IS NOT A PACKAGE. The loop is `RUN` (7 levers) and the batch width is OPT's. Three rows read
    `TRAIN.batch_w`, `TRAIN.grow_cap_every` and `TRAIN.accum`; they are now `OPT.batch_windows`,
    `CAP.pin_windows` and `OPT.accum`, and `TRAIN.d_effective_batch_windows` is `OPT.d_...`, still local.
  * `TOK.vmax` DOES NOT EXIST. The census gives VMAX to LM as `vocab_slots` and says TOK receives it as
    `d_vocab_ceiling`, so the edge is reversed rather than the field re-declared -- declaring `vmax` on
    TOK as well would put the softmax width in two packages at once.
  * `MANAGE_EVERY` IS WINDOWS, NOT STEPS. See the row's own reason: `step` advances per window and the
    gate compares against it. The conversion is `derive.flush_period_windows`, added for this.

None of that was detectable before, and the reason it was not is the interesting part: with no package
registered, `build()` DEFERRED every row with a warning, so a table of thirteen correct names and a table
of nine correct names produced identical output. `_check_endpoints` below closes that at import, which is
where the rest of this file's declaration faults are already caught.

WHAT THIS FILE CANNOT DO, said plainly. A wire's value must be computable from levers alone, at startup,
because `Config` freezes when `build()` returns and there is no such thing as a late wire. The signature
width is the clearest casualty: `derive.signature_width_bytes(win_tokens, bytes_per_token)` needs a
MEASURED compression ratio that does not exist until the tokenizer has seen the corpus, so it cannot be a
`d_` field on a frozen Config. It is in `NOT_WIRES` below with that reason. The discipline that replaces
the ledger there is `derive.py`'s: one named function, called once, answer kept -- which is what the old
tree failed at when it resolved SIG_WIN in two places from one knob whose zero meant 614 bytes in training
and 1 byte in eval.
"""
import builtins
import dis
import io
import types

from . import derive
from . import lever
from . import registry
from . import units as U
from .lever import LeverError
from .units import Steps, Windows
from .wire import WIRE_BUDGET, WireError, Wires, _check_unit, _check_why, _split

# ==================================================================================================
# THE THIRTEEN REAL PACKAGES. This is the import block the whole "one file may hold more than one
# LeverSet" rule exists for, and until now it was empty -- the table below was written against names
# that no declaration owned, and `build()` answered by DEFERRING every row with a warning. A deferral
# is the untrippable-guard shape (60 of the survey's 475 records): the printed graph shows an edge that
# was never made, affects() hands the L3 sweep a reach the run does not have, and the sweep reads as
# passing because nothing moved. Importing the declarations here is what turns each of those rows from
# a claim into either a value or a startup failure.
#
# THE PATH FORM IS ABSOLUTE, `from capacity.levers import ...`, and that is forced rather than chosen:
# every entry point in this tree puts `src/` itself on sys.path, which makes `capacity` a TOP-LEVEL
# package, and `from ..capacity.levers import ...` raises "attempted relative import beyond top-level
# package" at import time. Each levers.py file records the same constraint at its own import line.
#
# IMPORTING THEM IS ALSO WHAT REGISTERS THEM. LeverSet.__init_subclass__ calls registry.register, so
# after this block registry.all_sets() holds all thirteen and build(sets=None) -- the production call --
# resolves the real tree. Nothing else in src/ may import two of these (O3), and nothing else at all may
# call from_env (O8), so this block is the single door.
# ==================================================================================================
from capacity.levers import CAPLevers          # noqa: E402
from ckpt.levers import CKPTLevers             # noqa: E402
from data.levers import DATALevers             # noqa: E402
from domains.levers import DOMLevers           # noqa: E402
from eval.levers import EVALLevers             # noqa: E402
from fabric.levers import FABLevers            # noqa: E402
from lm.levers import LMLevers                 # noqa: E402
from memory.levers import MEMLevers            # noqa: E402
from opt.levers import OPTLevers               # noqa: E402
from sig.levers import SIGLevers               # noqa: E402
from tok.levers import TOKLevers               # noqa: E402
from train.levers import RUNLevers             # noqa: E402
from world.levers import WORLDLevers           # noqa: E402

# Keyed by PREFIX, and built from the classes rather than read back out of the registry, so that the
# endpoint check below is a statement about what THIS FILE holds. Reading the registry instead would
# make the check pass or fail depending on what some other module happened to import first, which is
# the kind of guard that is green for the wrong reason.
PACKAGES = types.MappingProxyType({cls.PREFIX: cls for cls in (
    CAPLevers, CKPTLevers, DATALevers, DOMLevers, EVALLevers, FABLevers, LMLevers,
    MEMLevers, OPTLevers, SIGLevers, TOKLevers, RUNLevers, WORLDLevers)})


# ==================================================================================================
# WHAT A compute() IS ALLOWED TO NAME
#
# THE HOLE THIS CLOSES, AS THE REVIEW DEMONSTRATED IT. `_Reads` further down restricts the ARGUMENT
# handed to a coupling's compute function. It does not restrict the function's CLOSURE, and until this
# check existed the restriction did not have to be defeated -- only walked around. Changing one row of
# the table below to
#
#     compute=lambda r: max(64, 2 * int(r["FAB"].slots)) + _peek()
#
# where `_peek()` is an ordinary module-level helper in this file doing
#
#     from fabric.levers import FabricLevers
#     return int(FabricLevers.from_env().manage_every)
#
# left all seven ownership checks PASSING, made MEM.d_source_slots move with FAB_MANAGE_EVERY, and left
# affects("FAB_MANAGE_EVERY") == {"FAB"}. That is a coupling that is real in the running system and
# absent from the ledger -- and the ledger is the L3 isolation sweep's only oracle (G1). The sweep would
# still see MEM's fingerprint move under a FAB lever, but it would report it as MEM leaking rather than
# as this file under-declaring, which sends the investigation to the wrong package.
#
# THE CHECK RUNS AT COUPLING CONSTRUCTION, which is import time for the table below: no environment set,
# no packages built, no GPU, microseconds. Declaration time is the right moment for the same reason
# `Lever.__init__` refuses a computed default there -- the alternative is catching it in review, and a
# review that has to notice a helper call three lines away is the review that missed this one.
#
# WHAT THIS IS AND IS NOT. It is a NAME check over the compiled code, not a purity proof. It says that a
# compute may resolve nothing outside its own body except the handful of names listed here, and that
# those names mean here what they mean in this file. It cannot say what `derive.flush_period` does; the
# known-answer tables in tests/test_derive.py do that. _check_names carries the full CANNOT CATCH list.
# ==================================================================================================

# THE ALLOWLIST. One place, and the whole of it. Every entry says what the name is and why a coupling is
# permitted to reach it; growing the list is an edit to this dict in a commit, which is exactly the
# visibility a compute's closure did not have. A `d_` field's value may depend on the levers named in
# src, on the pure functions below, and on nothing else.
COMPUTE_ALLOWLIST = types.MappingProxyType({
    "derive":
        "spine.derive -- the pure derived quantities, one named function each, replayed case by case "
        "against the P0 oracle by tests/test_derive.py. A compute calls derive.f(...) rather than "
        "restating f inline, because a formula written twice is the SIG_WIN defect: one knob resolved "
        "in two places, 614 bytes in training and 1 byte in eval.",
    "Steps":
        "spine.units.Steps -- the clock constructor a compute needs in order to hand "
        "derive.flush_period a cadence that carries its kind. A bare int there is the 16x-slow clock "
        "that pinned the population for 43,645 real steps while the clock read 2,650. NO ROW BELOW "
        "REACHES IT TODAY: both cadences this table converts turned out to be denominated in WINDOWS, "
        "not steps (see FAB.d_manage_period). It stays because a genuinely step-denominated cadence -- "
        "an LR-schedule horizon -- is the next coupling of this shape, and because removing it would "
        "make derive.flush_period unreachable from any compute while derive.flush_period_windows is "
        "reachable, which reads as a claim that the steps form is wrong rather than unused.",
    "Windows":
        "spine.units.Windows -- the same constructor for the kind the loop counter actually counts. "
        "`step` advances once per window (`i += WIN; step += 1`, self_organize.py:6796 and :7708) and "
        "every management gate compares against it, so MANAGE_EVERY and the capacity valve's pin "
        "threshold are Windows and are handed to derive.flush_period_windows. Passing them through the "
        "Steps form instead is the conflation this whole module is written against, one layer up.",
    "_owner_blocks":
        "the one pure helper local to this file, defined immediately above the table because two "
        "couplings need the same fold and a fold written twice can disagree with itself. Its own free "
        "names are checked by this same rule, transitively -- an allowlisted helper is not a hole.",
    "int":
        "narrowing a lever to the integer the receiving package's arithmetic needs.",
    "max":
        "the floors the shipped formulas carry: max(64, ...) in the memory source census, max(1, ...) "
        "in the effective batch.",
    "min":
        "the fold the shipped formulas carry: min(slots, owners). Reached through _owner_blocks and not "
        "from a compute directly, and listed because this check follows helpers.",
})

# BYTECODE CLASSIFICATION, AND WHY co_names IS NOT USED RAW. `co_names` conflates three different things
# -- a global load, an attribute load and an import -- so matching it whole against the allowlist would
# force this dict to contain every LEVER FIELD NAME any compute reads through `r`: slots, owners, quota,
# vmax, batch_w, grow_cap_every, pressure, accum, and one more for every lever anybody ever wires. A list
# that has to grow with the levers is a list that rots, and it rots in the direction of "add the name so
# the import stops failing", which ends with an allowlist that names everything.
#
# `dis.hasname` is the set of opcodes that index co_names, and the OPCODE says which of the three a name
# is. Attribute reads are already policed at run time by `_Fields` (an undeclared one raises, by name),
# imports are refused outright, and only genuine global and builtin references are matched here.
#
# A hasname opcode this does not recognise is treated as a GLOBAL reference, so a future Python that
# renames LOAD_ATTR makes this check STRICTER -- assemble.py fails to import, loudly, on the first run --
# rather than looser. A guard must fail toward refusing, because the other direction is silent.
_HASNAME = frozenset(dis.hasname)
_ATTR_OPS = frozenset({"LOAD_ATTR", "LOAD_METHOD", "STORE_ATTR", "DELETE_ATTR",
                       "LOAD_SUPER_ATTR", "LOAD_SUPER_METHOD"})
_IMPORT_OPS = frozenset({"IMPORT_NAME", "IMPORT_FROM"})

# CO_VARARGS and CO_VARKEYWORDS. Spelled out rather than imported from `inspect`, which pulls a large
# part of the standard library into every import of this file for two integers that have not moved since
# Python 2.
_CO_VARARGS, _CO_VARKEYWORDS = 0x04, 0x08

# The same rule `Lever.__init__` applies to a lever's default, for the same reason: a default that is not
# a literal is a value the declaration does not show. Here it is also an escape -- see _check_names.
_LITERALS = (bool, int, float, str, bytes, type(None))

_UNBOUND = object()


def _resolve(namespace, name):
    """What `name` resolves to for code whose globals are `namespace`: the global, else the builtin."""
    if name in namespace:
        return namespace[name]
    b = namespace.get("__builtins__", builtins)
    # __builtins__ is the module itself in __main__ and the module's dict in every imported module. Both
    # are ordinary states of a running interpreter, so both are handled rather than one being assumed.
    if isinstance(b, dict):
        return b.get(name, _UNBOUND)
    return getattr(b, name, _UNBOUND)


def _referenced(code):
    """(global names, attribute names, imported names) for `code` and every code object nested in it.

    NESTED CODE IS NOT OPTIONAL. A comprehension or an inner lambda compiles to its own code object with
    its own co_names, so on Python 3.11 `lambda r: sum(_peek() for _ in (1,))` hides `_peek` from the
    outer code object completely. Python 3.12 inlines comprehensions and would have shown it: a check
    whose reach depends on the interpreter version is a check that is off on somebody's machine.
    """
    glob, attr, imported = set(), set(), set()
    todo, seen = [code], set()
    while todo:
        c = todo.pop()
        if id(c) in seen:
            continue
        seen.add(id(c))
        for ins in dis.get_instructions(c):
            if ins.opcode in _HASNAME and isinstance(ins.argval, str):
                if ins.opname in _IMPORT_OPS:
                    imported.add(ins.argval)
                elif ins.opname in _ATTR_OPS:
                    attr.add(ins.argval)
                else:
                    glob.add(ins.argval)
        for k in c.co_consts:
            if isinstance(k, types.CodeType):
                todo.append(k)
    return glob, attr, imported


def _check_names(fn, dst, what, seen):
    """Refuse every way `fn` can reach a value the coupling did not declare. Recursive over helpers.

    CANNOT CATCH, said plainly, because a check whose blind spots are not written down gets over-trusted:

      * what an allowlisted name DOES. `derive` is trusted whole: spine/derive.py imports nothing but
        spine.units, its functions are pure by construction, and tests/test_derive.py replays them
        against the P0 oracle (575 cases, 0 mismatches). If that file ever grows an import of something
        that reads the world, this check will not notice and derive.py's own rule is what has to hold.
      * rebinding after import. `assemble.derive = something_else` between import and build() defeats
        this, as does mutating spine.derive itself. Catching that needs the compute to run in a sandbox,
        and a coupling table that is rewritten at runtime is a problem this check is the wrong size for.
      * a compute that reads the DATA. Every leak travelling through shared state, RNG draw order or the
        corpus is invisible here exactly as it is invisible to the AST checks in tests/test_ownership.py
        -- that is L3's job (tests/test_lever_isolation.py), against the test_determinism noise floor.
      * whether the arithmetic is right. This is a name check: `max(64, 2 * slots)` and
        `max(64, 3 * slots)` are indistinguishable to it. The reason column and tests/test_derive.py are
        what stand behind the number itself.
    """
    if id(fn) in seen:                      # two helpers that call each other are each checked once
        return
    seen.add(id(fn))

    if not isinstance(fn, types.FunctionType):
        raise WireError(
            f"{dst}: {what} is a {type(fn).__name__}, not a plain function. A callable object, a "
            f"functools.partial or a bound method carries its free names on the INSTANCE rather than in "
            f"a code object, so this check could not read them and the coupling's reach would be "
            f"undeclarable rather than merely undeclared. Write a lambda or a def.")

    code = fn.__code__

    # A CLOSURE CELL IS THE PURE FORM OF THE DEFECT. `_peek` as a module global is at least greppable in
    # this file; a cell binds a name to an object chosen somewhere else entirely, and the declaration
    # site shows nothing at all. Every compute in the table is a module-level lambda, so this is empty
    # for all of them and no legitimate row loses anything.
    #
    # ONLY THE TOP-LEVEL CODE OBJECT IS CHECKED FOR FREEVARS, and that is complete rather than partial:
    # with this function closing over nothing, a cell that an inner lambda or comprehension binds can
    # only have come from this function's own locals, which are its parameter and what it computed from
    # it. Checking nested code objects too would refuse `sorted(xs, key=lambda v: scale * v)` for closing
    # over a local that is already inside the boundary.
    if fn.__closure__ or code.co_freevars:
        raise WireError(
            f"{dst}: {what} closes over {list(code.co_freevars)}. A coupling's value comes from the "
            f"levers named in src plus the names in COMPUTE_ALLOWLIST; a closure cell is bound to an "
            f"object the declaration does not show, which is the coupling-that-is-invisible-in-the-"
            f"ledger this table exists to prevent. Declare the helper at module level and allowlist it, "
            f"or read the value through r.")

    # THE DEFAULT-ARGUMENT SMUGGLE. `lambda r, _p=_peek: r["FAB"].slots + _p()` has no suspicious name in
    # its code at all: `_p` is a parameter, and the binding happened at the declaration site. The rule is
    # the one Lever.__init__ already applies to a lever's default, for the same reason -- a default that
    # is not a literal is a value the declaration does not show.
    for label, defaults in (("__defaults__", tuple(fn.__defaults__ or ())),
                            ("__kwdefaults__", tuple((fn.__kwdefaults__ or {}).values()))):
        bad = [d for d in defaults if not isinstance(d, _LITERALS)]
        if bad:
            raise WireError(
                f"{dst}: {what} has a non-literal default ({label} holds "
                f"{[type(d).__name__ for d in bad]}). A default is a binding made at the declaration "
                f"site that the code object does not show -- the same laundering as a closure cell, one "
                f"line shorter. Literals only, exactly as for a lever's default.")

    glob, attr, imported = _referenced(code)

    if imported:
        raise WireError(
            f"{dst}: {what} imports {sorted(imported)}. An import inside a coupling reaches the whole "
            f"tree past every check in it -- the demonstrated escape was literally "
            f"`from fabric.levers import FabricLevers; FabricLevers.from_env()`, which re-reads the "
            f"environment for a package this coupling does not name and leaves the ledger, the printed "
            f"graph and affects() all describing a system other than the one running.")

    for n in sorted(attr):
        # DUNDERS ARE THE STANDARD WAY OUT OF A NAME CHECK: `derive.__globals__["registry"]`,
        # `r.__class__.__mro__`, `().__class__.__base__.__subclasses__()`. One rule removes the whole
        # family and no coupling has ever needed a dunder attribute. ORDINARY attribute names are
        # deliberately not checked here: `r["FAB"].slots` is an attribute read, and _Fields already
        # refuses the undeclared ones by name at the moment they happen.
        if n.startswith("__"):
            raise WireError(
                f"{dst}: {what} reads the dunder attribute {n!r}. A compute reads levers through r and "
                f"calls the functions in COMPUTE_ALLOWLIST; every dunder path out of that -- "
                f"__globals__, __class__, __subclasses__, __import__ -- reaches values no wire declares "
                f"and the printed graph cannot show.")

    for n in sorted(glob):
        if n not in COMPUTE_ALLOWLIST:
            raise WireError(
                f"{dst}: {what} names {n!r}, which is not in COMPUTE_ALLOWLIST. A coupling's value may "
                f"depend on the levers in its src and on the pure helpers listed there, and on nothing "
                f"else. This is the check for the demonstrated escape: `+ _peek()`, where _peek() "
                f"re-read another package's levers, left all seven ownership checks green and "
                f"affects('FAB_MANAGE_EVERY') == {{'FAB'}} while MEM.d_source_slots moved with it. If "
                f"{n!r} is genuinely pure and genuinely belongs here, add it to COMPUTE_ALLOWLIST with "
                f"a reason; if it reads a lever, name that lever's owner in src instead. "
                f"Allowed: {sorted(COMPUTE_ALLOWLIST)}")

        obj = _resolve(fn.__globals__, n)
        if obj is _UNBOUND:
            # AN ALLOWLISTED NAME THAT IS NOT BOUND YET IS THE SILENT HALF OF THIS CHECK. `_owner_blocks`
            # was originally defined BELOW the table, so at the moment each row is constructed the name
            # does not resolve -- and a check that skipped what it could not resolve would have followed
            # nothing into the one helper it most needs to follow, and said so nowhere. Helpers are
            # defined above COUPLINGS instead, and the unresolvable case is a refusal.
            raise WireError(
                f"{dst}: {what} names {n!r}, which is allowlisted but is not bound at the moment this "
                f"coupling is constructed. A pure helper must be defined ABOVE the COUPLINGS table, or "
                f"this check silently stops following it.")

        if isinstance(obj, types.FunctionType) and obj.__globals__ is fn.__globals__:
            # TRANSITIVE, AND THIS IS WHAT MAKES THE ALLOWLIST MEAN ANYTHING. Allowlisting a local helper
            # by name would otherwise move the escape one call deeper: the demonstrated `_peek()` could
            # equally have been three lines inside _owner_blocks, where nothing at the declaration site
            # shows it at all. A helper defined in this module is held to the same rule as the compute
            # that calls it, all the way down.
            _check_names(obj, dst, f"{what} -> helper {n}()", seen)
        elif obj is not _resolve(globals(), n):
            # The name is allowlisted, but HERE it means something else. This is what stops a coupling
            # declared in another module from getting `derive` or `int` for free by rebinding the
            # spelling: the allowlist is a statement about the objects this file reaches, not about six
            # words. tests/test_ownership.py's O4 already refuses a Coupling declared outside this file;
            # this is the same refusal from the runtime side, where build(couplings=...) can be handed a
            # table the AST pass never saw.
            raise WireError(
                f"{dst}: {what} names {n!r}, which is allowlisted, but in {fn.__module__!r} that name "
                f"is bound to {type(obj).__name__} rather than to the object it names in spine.assemble. "
                f"An allowlisted spelling pointing somewhere else is the same laundering with an extra "
                f"step.")


def _check_compute(compute, dst):
    """Refuse a compute that can reach past its declared src. Called from Coupling.__init__."""
    if isinstance(compute, types.FunctionType):
        code = compute.__code__
        if (code.co_argcount != 1 or code.co_kwonlyargcount
                or code.co_flags & (_CO_VARARGS | _CO_VARKEYWORDS)):
            # ONE PARAMETER, AND IT IS THE RESTRICTED VIEW. build() calls compute(_view(c, configs)) and
            # passes nothing else, so a second parameter can only be there to carry a default -- and a
            # default is a binding made at the declaration site that the code object does not show.
            raise WireError(
                f"{dst}: compute must take exactly one parameter, the restricted reads view. build() "
                f"calls compute(_view(...)) and passes nothing else, so any further parameter exists "
                f"only to carry a value in from the declaration site.")
    _check_names(compute, dst, "compute", set())
    return compute


# ---- the coupling record -------------------------------------------------------------------------
# `_split`, `_check_why` and `_check_unit` are imported from spine.wire rather than re-implemented here,
# including the leading underscore. A LOCAL coupling never becomes a `Wire`, so nothing in wire.py would
# check its endpoints, its reason or its unit -- and a second validator with its own idea of what a legal
# endpoint looks like is how the two halves of one table end up obeying two different rules. One set of
# rules, imported, even though the import is of a private name.

class Coupling:
    """One declared coupling: what it reads, where the answer lands, how it is computed, and why it exists.

    Frozen, and validated at CONSTRUCTION -- which is import time for everything in `COUPLINGS` below.
    That timing is the point of the class existing at all: a malformed destination or a missing reason is
    a failure when the module is imported, on a machine that has no environment set and no packages built,
    rather than at startup on the run that needed it.
    """

    __slots__ = ("src", "dst", "why", "unit", "irreducible", "compute",
                 "reads", "src_prefixes", "dst_prefix", "dst_field", "src_envs", "local")

    def __init__(self, src, dst, compute, why, unit=U.COUNT, irreducible=False):
        reads = (src,) if isinstance(src, str) else tuple(src)
        if not reads:
            raise WireError(f"coupling into {dst!r} reads nothing. A value computed from no lever is a "
                            f"constant, and a constant belongs in the code that uses it.")
        pairs = [_split(s, "src") for s in reads]
        dst_prefix, dst_field = _split(dst, "dst")

        # THE d_ RULE APPLIES TO BOTH KINDS. wire.py enforces it for cross-package wires; nothing else
        # would enforce it for a LOCAL coupling, and a local derived value that arrives under an ordinary
        # name is laundered in exactly the way the review finding describes -- worse, in fact, because
        # inside its own package it really does look owned. G5 is about values computed from more than one
        # LEVER. `fabric.d_operating_population` is one of those, so it is `d_`.
        if not dst_field.startswith("d_") or len(dst_field) <= 2:
            raise WireError(f"dst={dst!r}: a value computed from more than one lever must land in a "
                            f"d_-prefixed field, whether or not it crosses a package boundary. "
                            f"`grep -rn d_ src/` is the whole coupling audit and it has no other index.")
        for (p, f), s in zip(pairs, reads):
            # ONE HOP, THE SAME RULE wire.py STATES. A coupling that reads a value another coupling
            # produced makes the graph transitive, and affects() unions the DIRECT receivers and stops --
            # so A -> B -> C would give A's lever a declared reach of {B} while its real reach includes C,
            # and the L3 sweep would report C's correct response as an undeclared leak. Checked here as
            # well as in Wire because a LOCAL coupling never reaches Wire, and reading an earlier
            # coupling's d_ field off the destination Config is the easiest way to do it by accident.
            if f.startswith("d_"):
                raise WireError(f"src={s!r} is a wired field, not an owned lever. Read the original "
                                f"owner's lever instead, or name both owners in src: affects() is one "
                                f"hop and chaining silently understates a lever's reach.")
        if not callable(compute):
            raise WireError(f"coupling into {dst!r} needs a compute(reads) callable; got "
                            f"{type(compute).__name__}. The value is computed here, at startup, from the "
                            f"declared sources -- there is no path for a value that arrives later, "
                            f"because Config freezes when build() returns.")
        # AND IT MAY NOT REACH PAST ITS DECLARED SOURCES. `_Reads` restricts what arrives through the
        # argument; this restricts what the function can resolve without it. Both halves are needed and
        # neither is sufficient -- see the COMPUTE_ALLOWLIST block at the top of this file for the
        # escape that had all seven ownership checks green. Checked here, at construction, so the table
        # below is validated when this module is IMPORTED: no environment, no packages, no GPU.
        _check_compute(compute, dst)

        object.__setattr__(self, "src", src if isinstance(src, str) else tuple(reads))
        object.__setattr__(self, "reads", tuple(reads))
        object.__setattr__(self, "dst", dst)
        object.__setattr__(self, "compute", compute)
        object.__setattr__(self, "why", _check_why(why))
        object.__setattr__(self, "unit", _check_unit(unit))
        object.__setattr__(self, "irreducible", bool(irreducible))
        object.__setattr__(self, "dst_prefix", dst_prefix)
        object.__setattr__(self, "dst_field", dst_field)
        object.__setattr__(self, "src_prefixes", tuple(dict.fromkeys(p for p, _ in pairs)))
        object.__setattr__(self, "src_envs", tuple(f"{p}_{f.upper()}" for p, f in pairs))
        # LOCAL means every source is the destination's own package. It is DERIVED from the endpoints and
        # never declared, so a coupling cannot be mislabelled: an author who adds a foreign source to a
        # local coupling turns it into a wire that spends budget and appears in the graph, whether or not
        # they noticed. The classification following the endpoints rather than a flag is what keeps the
        # printed graph and the running system the same object.
        object.__setattr__(self, "local", set(self.src_prefixes) == {dst_prefix})

    def __setattr__(self, k, v):
        raise WireError(f"coupling {self.dst} is frozen; the table is declared once, at import")

    def __delattr__(self, k):
        raise WireError(f"coupling {self.dst} is frozen; the table is declared once, at import")

    @property
    def prefixes(self):
        """Every package this coupling needs in order to resolve, sources and destination."""
        return tuple(dict.fromkeys(self.src_prefixes + (self.dst_prefix,)))

    @property
    def src_text(self):
        return " x ".join(self.reads)

    def __repr__(self):
        kind = "local" if self.local else "wire"
        return f"<Coupling {kind} {self.src_text} -> {self.dst}{' IRREDUCIBLE' if self.irreducible else ''}>"


# ---- the restricted view handed to compute() -------------------------------------------------------

class _Fields:
    """A read-only window onto ONE Config, exposing only the names a coupling declared.

    THIS IS MECHANISM 2 FROM THE MODULE DOCSTRING and it exists because of a hole the `d_` prefix does not
    close. The prefix stops a coupling's OUTPUT from looking owned. Nothing in it stops a coupling's INPUT
    from being undeclared: `compute=lambda cfgs: cfgs["FAB"].slots * cfgs["TOK"].vmax` on a wire whose src
    says only "FAB.slots" is syntactically fine, runs correctly, and hands the L3 sweep an oracle that is
    missing TOK -- so a genuine leak from TOK measures as an undeclared reach and the sweep reports the
    correct behaviour as the bug, or (worse, and this is the direction that stays green) the oracle is
    consulted for TOK_VMAX, does not contain FAB, and nothing is compared at all.

    An undeclared read is therefore an exception at the moment it happens, naming the coupling and saying
    what to add. That is the same trade the whole spine makes: make the wrong thing impossible to write
    rather than detectable afterwards.
    """

    __slots__ = ("_cfg", "_allow", "_dst", "_role")

    def __init__(self, cfg, allow, dst, role):
        self._cfg, self._allow, self._dst, self._role = cfg, frozenset(allow), dst, role

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        if name.startswith("d_"):
            # Reading another coupling's answer is the chaining Coupling.__init__ already refuses at
            # declaration time; this is the same refusal at read time, because the destination package's
            # view exposes its own Config and earlier couplings in the same build may already have
            # written d_ fields onto it. Without this, ordering the table differently would change what
            # a compute can see, which is a coupling graph that depends on list order.
            raise LeverError(
                f"{self._dst}: compute() read {self._cfg.prefix}.{name}, which is a WIRED field, not an "
                f"owned lever. affects() is one hop -- read the value's original owner instead, and name "
                f"that owner in src.")
        if name not in self._allow:
            raise LeverError(
                f"{self._dst}: compute() read {self._cfg.prefix}.{name}, which this coupling did not "
                f"declare. Add '{self._cfg.prefix}.{name}' to its src, or do not read it. An undeclared "
                f"read is invisible to affects(), and affects() is the only oracle the L3 isolation sweep "
                f"has. Declared here ({self._role}): {sorted(self._allow)}")
        return getattr(self._cfg, name)

    def __repr__(self):
        return f"<reads {self._cfg.prefix}: {sorted(self._allow)}>"


class _Reads:
    """`compute`'s whole world: `r["FAB"].slots`, and a named failure for every other package."""

    __slots__ = ("_views", "_dst")

    def __init__(self, views, dst):
        self._views, self._dst = views, dst

    def __getitem__(self, prefix):
        v = self._views.get(prefix)
        if v is None:
            raise LeverError(
                f"{self._dst}: compute() reached for package {prefix!r}, which this coupling did not "
                f"declare. Visible here: {sorted(self._views)}. A coupling reads what its src says it "
                f"reads; anything else is a coupling the printed graph does not contain.")
        return v

    def __repr__(self):
        return f"<reads for {self._dst}: {sorted(self._views)}>"


def _view(coupling, configs):
    """Build the restricted view for one coupling.

    Foreign packages expose exactly the declared fields. The DESTINATION package exposes all of its own
    levers and none of its wired ones -- see the module docstring for why that is not a hole: an edge from
    a package to itself cannot widen anyone's affects(), so booking it would spend budget for no oracle.
    """
    per_prefix = {}
    for s in coupling.reads:
        p, f = _split(s, "src")
        per_prefix.setdefault(p, set()).add(f)
    views = {}
    for p, fields in per_prefix.items():
        views[p] = _Fields(configs[p], fields, coupling.dst, "declared in src")
    dcfg = configs[coupling.dst_prefix]
    # `keys()` is levers plus wired fields and `wired()` is the wired ones, so the difference is exactly
    # the package's OWN declared levers. Taken from the Config's public introspection rather than from
    # `_owner._levers` so that this does not break the day a LeverSet grows a second way to declare one.
    owned = set(dcfg.keys()) - set(dcfg.wired())
    if coupling.dst_prefix in views:
        # A local coupling names its own package in src. Its declared fields are already owned levers;
        # union rather than overwrite so the error message still lists everything legal to read.
        owned |= views[coupling.dst_prefix]._allow
    views[coupling.dst_prefix] = _Fields(dcfg, owned, coupling.dst, "the destination package's own levers")
    return _Reads(views, coupling.dst)


# ==================================================================================================
# THE COUPLING TABLE
#
# Every row is a coupling the survey actually found in the old tree, with the defect that proves it was
# real. Rows are data: `render()` prints this list without resolving anything, so docs/03_WIRING.md can
# be regenerated without running the system, and `build()` walks it in order.
#
# ORDER DOES NOT MATTER and must not be made to matter. No coupling may read another coupling's output
# (Coupling.__init__ and _Fields both refuse a d_ source), so every row depends only on levers, and the
# result of build() is the same for any permutation of this list. If a row ever appears to need another
# row's answer, that is a two-owner value and the fix is to name both owners in `src` -- not to reorder.
#
# IRREDUCIBLE means the two ends are one quantity named twice: no interface design separates them, and a
# project claiming they are independent is lying about its own arithmetic. It is a claim about the world.
# Everything else here is a coupling this design CHOSE, which means a later design can un-choose it.
# ==================================================================================================

# ---- the pure helpers a compute may call -----------------------------------------------------------
# ABOVE THE TABLE, AND THAT POSITION IS NOW LOAD-BEARING. This helper used to sit below COUPLINGS, which
# reads better and cannot work: `Coupling.__init__` checks each compute's free names at construction and
# FOLLOWS an allowlisted local helper into its own body, so the name has to be bound by the time the rows
# are built. A helper declared after the table is refused by name rather than skipped -- see the
# `_UNBOUND` branch in _check_names, and the reason it is a refusal and not a shrug.

def _owner_blocks(expert_slots, owner_buckets):
    """How many memory partitions actually exist: min(slots, owners), floored at one.

    ITS HOME IS spine/derive.py and it should move there when that file is next opened -- it is a pure
    function of two levers, which is exactly what that file is for. It sits here, defined once, because
    two couplings need it (`MEM.d_owner_blocks` and `MEM.d_capacity`) and a fold written twice is a fold
    that can disagree with itself. That is not hypothetical for this particular number: memory.py:36 and
    self_organize.py:4873 each computed the store's size their own way, and the disagreement is the 24x
    shrink the capacity coupling's reason describes.

    IT NAMES ONLY max, min AND int, and that is checked rather than trusted: COMPUTE_ALLOWLIST covers
    what a compute may reach, and the check follows this call to hold the helper to the same rule. The
    escape it would otherwise leave is exact -- the demonstrated `_peek()` reads a foreign package's
    levers just as invisibly from inside here as it does from inside a lambda.
    """
    return max(1, min(int(expert_slots), int(owner_buckets)))


COUPLINGS = [

    # --- fabric -> domains ------------------------------------------------------------------------
    Coupling(
        src="FAB.slots",
        dst="DOM.d_expert_slots",
        compute=lambda r: r["FAB"].slots,
        unit=U.SLOTS,
        irreducible=False,
        why="The domain id namespace is bounded by the expert slot pool: a domain that cannot be given a "
            "slot cannot be routed to. In the old tree this was a computed default -- "
            "MAX_DOMAINS = _i('MAX_DOMAINS', _i('FAB_NMAX', 4096)) at self_organize.py:598 -- which had "
            "three consequences. FAB_NMAX was entered into the read audit on every run whether or not it "
            "mattered; the same name was ALSO read as _i('MAX_DOMAINS', 32) at :4874 when sizing the "
            "memory source census, so one knob had two defaults 128x apart; and that was only legal "
            "because MAX_DOMAINS sat in _DERIVED and was exempt from the default-mismatch refusal. Worse "
            "in practice than in principle: every launcher set MAX_DOMAINS=1000000 while FAB_NMAX sat at "
            "64, so two populations designed as duals ran 15,625x apart and dom_exp affiliation mapped "
            "hundreds of domains onto each expert (notes 05_ERRORS E1.7/E10.32). This is the census's "
            "MAX_DOMAINS promote-to-wire (CENSUS.md:208), landing on DOM. It is marked reducible because "
            "domains could legitimately own a smaller namespace than the slot pool; what they may not do "
            "is own a DIFFERENT one silently."),

    # --- fabric -> memory -------------------------------------------------------------------------
    Coupling(
        src="FAB.slots",
        dst="MEM.d_owner_blocks",
        compute=lambda r: _owner_blocks(r["FAB"].slots, r["MEM"].owners),
        unit=U.COUNT,
        irreducible=True,
        why="Memory ownership is expert_id % n_own, and n_own was min(FAB_NMAX, MEM_OWNERS) at "
            "self_organize.py:4873. The fold is irreducible: expert ids run to the slot count (4096) "
            "while the store has MEM_OWNERS (64) partitions, so 32 experts shared each partition and "
            "'per-expert memory' was per-64-buckets memory. Blocks in excess of the slot count are "
            "unreachable by the modulo and their quota is capacity that exists and can never be written."),
    Coupling(
        src="FAB.slots",
        dst="MEM.d_capacity",
        compute=lambda r: _owner_blocks(r["FAB"].slots, r["MEM"].owners) * int(r["MEM"].quota),
        unit=U.ENTRIES,
        irreducible=True,
        why="Capacity is DERIVED, not declared: a partitioned store holds blocks x quota entries and has "
            "no size independent of its partition. The old tree declared it anyway and memory.py:36 then "
            "silently overrode it -- 'if self.n_own > 1: cap = self.n_own * self.quota' -- so a requested "
            "MEM_CAP of 200,000 became 64 x 128 = 8,192, a 24x shrink recorded as E7.40 with no line in "
            "any log. This is the census's MEM_CAP promote-to-wire (CENSUS.md:249); after it the operator "
            "sizes the store through quota and owners, and 200,000 is no longer a number anyone types. "
            "Deriving it here means the number that gets discarded is the one nobody wrote."),
    Coupling(
        src="FAB.slots",
        dst="MEM.d_source_slots",
        compute=lambda r: max(64, 2 * int(r["FAB"].slots)),
        unit=U.ENTRIES,
        irreducible=False,
        why="The memory source census must have a row per source that can appear, and sources are "
            "domains. It was sized max(64, MAX_DOMAINS * 2) at self_organize.py:4874 -- reading "
            "MAX_DOMAINS with the WRONG default (32), so the table was 64 rows wide on every default run "
            "while memory.py's own docstring records 125 source ids on a real one, and the fix that "
            "clamped ids into the 64-wide table would have re-broken it at exactly the scale it was "
            "written for. This is the SECOND landing of the census's MAX_DOMAINS promote-to-wire, which "
            "names both (CENSUS.md:208: 'it lands on DOM as d_expert_slots and on MEM as d_src_hint'); "
            "the field is named d_source_slots because memory/levers.py:69 declares that spelling as what "
            "it expects to receive. The formula is the shipped one; only its input was wrong. Reducible: "
            "a census that grows on demand needs no bound at all, and that is the better repair when it "
            "is written."),

    # --- the training loop's batch width -> the per-flush cadences ---------------------------------
    Coupling(
        src="OPT.batch_windows",
        dst="FAB.d_manage_period",
        compute=lambda r: derive.flush_period_windows(Windows(r["FAB"].manage_every),
                                                      r["OPT"].batch_windows),
        unit=U.Flushes,
        irreducible=True,
        why="MANAGE_EVERY is a cadence on the WINDOW counter, and five call sites consume it per FLUSH. "
            "The management gates above the batch early-out test `step % MANAGE_EVERY == 0` "
            "(self_organize.py:6716, :6764, :6768) where `step` advances once per window "
            "(`i += WIN; step += 1`, :6796 and :7708); the sites BELOW the early-out run once per flush "
            "and wrote the conversion inline as `_nbwd % max(1, MANAGE_EVERY // max(1, BATCH_W))` at "
            ":6819, :6836, :6961, :6988, :7077 and :7325 -- one number compared against two clock kinds "
            "in one file. Irreducible: a cadence in windows handed to a block that counts flushes has no "
            "meaning until the batch width is known, which is why the value is a Flushes clock and not an "
            "int -- an int compares fine against a threshold in the wrong unit. UNIT RESOLVED HERE: this "
            "row used to read `derive.flush_period(Steps(r['FAB'].manage_every), ...)` and its reason "
            "said 'MANAGE_EVERY is written in STEPS'; the census (CENSUS.md, FAB family) and "
            "fabric/levers.py:648 both type it Windows, and the source agrees with them, so the Steps "
            "assumption is withdrawn and the conversion is derive.flush_period_windows."),
    Coupling(
        src=("OPT.batch_windows", "CAP.pin_windows"),
        dst="FAB.d_cap_lift_period",
        compute=lambda r: derive.flush_period_windows(Windows(r["CAP"].pin_windows),
                                                      r["OPT"].batch_windows),
        unit=U.Flushes,
        irreducible=True,
        why="The measured case for this whole mechanism. The capacity valve's pin clock ticked per flush "
            "against a threshold in windows, so GROW_CAP_EVERY=20000 silently demanded 320,000 windows at "
            "BATCH_W=16 and 640,000 at 32: the population sat pinned for 43,645 real ticks while the "
            "clock read 2,650 (= 42,400/16) and the report said 'reached the cap but never held it long "
            "enough' -- a true sentence about a false clock. A second gate one layer up then compared "
            "fabgrow.n (calls) to the same threshold and lifted nothing for a further whole round, the "
            "first fault masking the second. The knob is now CAP.pin_windows (census GROW_CAP_EVERY -> "
            "CAP_PIN_STEPS, re-typed and re-named to CAP_PIN_WINDOWS at capacity/levers.py:305 because "
            "the counter it is compared against is `step`). CAVEAT THE VALVE PORT MUST SETTLE, recorded "
            "rather than papered over: derive.pin_tick still types its accumulated clock as Steps, so a "
            "Windows threshold and a Steps clock cannot meet -- capacity/levers.py:88-108 sets out the "
            "two legal repairs, and applying both at once fires the valve 16x too EARLY. This row "
            "converts the threshold and nothing else."),
    Coupling(
        src=("OPT.batch_windows", "CAP.pin_windows"),
        dst="TOK.d_cap_lift_period",
        compute=lambda r: derive.flush_period_windows(Windows(r["CAP"].pin_windows),
                                                      r["OPT"].batch_windows),
        unit=U.Flushes,
        irreducible=True,
        why="The vocabulary soft cap is lifted by the same valve on the same clock, and it was blocked by "
            "the same units fault: round6 measured 0 vocabulary lifts on gc_real, and gc_fast and "
            "gc_loose lifted identically (6 each, same first step 32047), which proves the plateau "
            "condition was never the blocker -- GROW_CAP_EVERY=20000 against a 60k-step run was. Wired "
            "separately from the fabric's period because the two caps are lifted by two mechanisms and a "
            "shared field would make one of them read a value the other's package owns."),

    # --- the model's vocabulary ceiling -> the tokenizer --------------------------------------------
    Coupling(
        src="LM.vocab_slots",
        dst="TOK.d_vocab_ceiling",
        compute=lambda r: int(r["LM"].vocab_slots),
        unit=U.ENTRIES,
        irreducible=True,
        why="emb.weight and head.weight have exactly this many rows, so the vocabulary the tokenizer is "
            "allowed to mint into is the model's row count: one number named twice, not two numbers that "
            "happen to agree, and no interface makes them independent. Getting it wrong is not a soft "
            "failure -- the resume geometry gate at self_organize.py:4442-4468 exists because a "
            "checkpoint built at one width cannot load into a model built at another, and the softer form "
            "(rows minted by the tokenizer but never present in the head) is the LOSS_MASK_DEAD family, "
            "where dead rows scale with VMAX and quietly take probability mass. DIRECTION CORRECTED HERE: "
            "this row read `src='TOK.vmax', dst='LM.d_softmax_width'`, and TOK has no lever called vmax "
            "-- the census gives VMAX to LM as LM_VOCAB_SLOTS and says in as many words that 'TOK "
            "receives it as the wire d_vocab_ceiling' (CENSUS.md:323), which is what lm/levers.py:127-141 "
            "and tok/levers.py:87 both record as the outstanding repair. Left as it was, importing the "
            "real packages made build() raise 'TOKLevers has no lever vmax' -- the mechanism working, on "
            "a row that named an owner nobody had."),

    # --- the checkpoint's artifact root -> the tokenizer's vocabulary file --------------------------
    Coupling(
        src="CKPT.dir",
        dst="TOK.d_vocab_save_path",
        compute=lambda r: (r["CKPT"].dir + ".dyntok.json") if r["CKPT"].dir else "",
        unit=U.PATH,
        irreducible=False,
        why="Where this run SAVES its own vocabulary is a property of its checkpoint, not a knob. The "
            "census's TOKENIZER_PATH promote-to-wire (CENSUS.md:306) is exactly this: one declared knob "
            "with a shared default of data/dyntok.json 'which belongs to whichever run wrote it last', "
            "so concurrent arms overwrote each other (ISSUES.md:1501, :285, :768). The old tree had "
            "already split the write side out by hand as `_TOK_SAVE = SAVE_CKPT + '.dyntok.json'` "
            "(self_organize.py:1010-1012), and that rule is the compute here, so a run's vocabulary lands "
            "beside its own checkpoint. Empty in, empty out: CKPT_DIR='' means saving is off entirely "
            "(ckpt/levers.py:143), and a save target computed from it would otherwise be the file "
            "'.dyntok.json' in whatever directory the run happened to start in. Reducible: a checkpoint "
            "format that carried the vocabulary inside itself would need no path at all."),
    Coupling(
        src="CKPT.resume",
        dst="TOK.d_vocab_read_path",
        compute=lambda r: (r["CKPT"].resume + ".dyntok.json") if r["CKPT"].resume else "",
        unit=U.PATH,
        irreducible=False,
        why="TWO FIELDS, NOT ONE, AND THE SPLIT IS THE POINT OF THE PROMOTE. TOKENIZER_PATH had two jobs "
            "-- 'the file a resume READS its parent's vocabulary from, and the file the run SAVES its own "
            "to' -- and conflating them made a run overwrite its parent's vocabulary; ckpt/levers.py:84-97 "
            "says plainly that a single d_vocab_path would re-conflate what the promote exists to "
            "separate. The read path is the parent's SAVE target under the same rule, which is the repair "
            "the sibling-guess heuristic at self_organize.py:1215-1222 never made: on the supported "
            "RESUME=runs/x/ckpt.pt form it guessed runs/x/ckpt.dyntok.json, that file did not exist, and "
            "it fell through to the shared data/dyntok.json (ISSUES.md M19). A resume must reuse the "
            "saved vocabulary or 'the restored embedding table would be indexed by a DIFFERENT "
            "vocabulary' (:1226-1227). Empty resume, empty path: there is no parent to read."),

    # --- the tokenizer's longest token -> the composer's byte tables --------------------------------
    Coupling(
        src="TOK.max_bytes",
        dst="LM.d_max_token_bytes",
        compute=lambda r: int(r["TOK"].max_bytes),
        unit=U.BYTES,
        irreducible=True,
        why="ByteComposer sizes its byte-index and position tables from the longest token that can "
            "exist, and that length is TOK's max_bytes -- one quantity, two packages, and no interface "
            "makes them independent. self_organize.py:1441 declares `def __init__(s, d, maxb=16)`, :1549 "
            "constructs it as `ByteComposer(d)` so the default always wins, and :1487 truncates with "
            "`b = bs[:s.maxb]`. With MAX_TOK above 16 two distinct long tokens sharing their first 16 "
            "bytes get IDENTICAL composites and identical starting vectors, silently -- the property the "
            "composer exists to provide, inverted, with no error (ISSUES M21). The defaults agreeing "
            "today is luck, not design, and luck is what a wire replaces: lm/levers.py:165 already names "
            "d_max_token_bytes as the incoming value it expects and tok/levers.py:337 records the same "
            "coupling as missing from this table. Wired rather than passed as an argument because the "
            "composition root would otherwise be free to hand LM a different number than the tokenizer "
            "mints against, and affects() would not see it."),

    # --- the two hard ceilings the capacity valve lifts toward --------------------------------------
    Coupling(
        src="FAB.slots",
        dst="CAP.d_expert_slots",
        compute=lambda r: int(r["FAB"].slots),
        unit=U.SLOTS,
        irreducible=True,
        why="The valve lifts a SOFT cap toward a HARD one, and the hard one is the preallocated expert "
            "slot pool: A, B and cent are allocated to FAB.slots rows and growth only advances n_live, "
            "so a soft cap above the pool is a cap that can never be reached and a lift past it is "
            "arithmetic on capacity that does not exist. capacity/levers.py:119 names this exact field "
            "as what CAP_FAB_START's 0 sentinel resolves to and :123 records that it is absent from this "
            "table. The sentinel is why it must be a wire and not a literal: `fab_start = 0` means START "
            "AT THE HARD CEILING, and lever.py refuses a default computed from another lever, so 0 has "
            "no meaning until this row supplies the number it stands for.",),
    Coupling(
        src="LM.vocab_slots",
        dst="CAP.d_vocab_slots",
        compute=lambda r: int(r["LM"].vocab_slots),
        unit=U.SLOTS,
        irreducible=True,
        why="The same sentinel on the other target: CAP_VOCAB_START=0 means start at the vocabulary's "
            "hard ceiling, which is the model's softmax row count and nothing else (the same number "
            "TOK.d_vocab_ceiling carries, from the same owner, for the minting side). Lifting a soft "
            "vocabulary cap above emb.weight's row count reserves ids the model has no row for, which is "
            "the failure C31 records from the other end -- `grew 2048 -> 2048 (+0)` on the first "
            "continual-learning run, a second language spelled entirely with the first one's merges. "
            "capacity/levers.py:120 and :244 both name d_vocab_slots as the wire this package expects "
            "and state that TOK holds no ceiling of its own to give.",),
    Coupling(
        src="LM.mask_dead_rows",
        dst="CAP.d_mask_dead_rows",
        compute=lambda r: r["LM"].mask_dead_rows,
        unit=U.FLAG,
        irreducible=False,
        why="The honesty precondition on the vocabulary arm of the valve, and it belongs to LM. Lifting "
            "the vocabulary cap reserves rows; a reserved row nobody has minted sits in the softmax "
            "denominator at its initialisation for the whole run unless the dead-row mask is on, so at "
            "8192 reserved against 2048 minted the run measures 6144 dead rows rather than the mechanism "
            "(capacity/levers.py:262, and the measurement at self_organize.py:3971-3979: 86.7% dead "
            "width scored 4.746 unmasked against 6.100 masked at the loss only). CAP does not get to "
            "decide this -- it is the model's output layer -- so it arrives as a wire and the valve "
            "reports the vocabulary arm as dishonest rather than silently lifting into unmasked rows. "
            "Reducible: a valve that refused to lift the vocabulary at all while the mask is off would "
            "need no flag, and that is the stricter repair if the owner wants it.",),
    Coupling(
        src=("FAB.pressure", "FAB.slots"),
        dst="CAP.d_operating_population",
        compute=lambda r: derive.operating_population(r["FAB"].pressure, r["FAB"].slots),
        unit=U.EXPERTS,
        irreducible=True,
        why="THE IRREDUCIBLE COUPLING THE VALVE PORT MUST DECLARE RATHER THAN REMOVE. The soft expert "
            "cap has to sit at or below the cull's settling point, FAB.pressure x FAB.slots: below "
            "pressure x slots the cull gate is shut and the population grows, at or above it the cull "
            "runs, so a soft cap ABOVE that number is a cap the population never reaches -- it never "
            "pins, the pin clock never accumulates, and the valve is dead while every report line says "
            "it is armed. The second landing of FAB.d_operating_population, computed by the same "
            "derive.operating_population call rather than restated, so the setpoint the fabric "
            "equilibrates at and the setpoint the valve refuses against cannot disagree. It is what "
            "capacity's startup refusal compares CAP_FAB_START against, and the failure it answers is "
            "C30: a soft cap below the population makes `min(_nb, _cap_fab[0] - fab.n())` negative at "
            "self_organize.py:7446 and freezes growth for the whole run with nothing in the log.",),

    # --- the fabric's competence numbers -> the domain manager's spare rule -------------------------
    Coupling(
        src="FAB.comp_ema",
        dst="DOM.d_comp_ema",
        compute=lambda r: r["FAB"].comp_ema,
        unit=U.FRACTION,
        irreducible=False,
        why="Competence is one EMA rate for the whole system: the fabric smooths per-expert competence "
            "at it and the domain manager smooths per-domain competence at it, and two rates would make "
            "'this domain is better than the population' a comparison between two differently smoothed "
            "series. FAB owns the number because the fabric's cull and spare rules are where it was "
            "first needed (fabric/levers.py:693 says so and names both this field and d_comp_protect as "
            "what DOM receives). The old tree had DOM reach for FAB's value directly -- "
            "self_organize.py:6720 reads the population baseline off the fabric object -- which is a "
            "coupling with no wire and nothing in affects(). Reducible: domains could legitimately "
            "smooth on their own clock; what they may not do is smooth on a DIFFERENT one silently while "
            "the report compares the two.",),
    Coupling(
        src="FAB.comp_protect",
        dst="DOM.d_comp_protect",
        compute=lambda r: r["FAB"].comp_protect,
        unit=U.FLAG,
        irreducible=False,
        why="The competence brake is one policy applied to two populations. FAB_COMP_PROTECT spares an "
            "expert whose competence beats the population baseline; the domain cull needs the same "
            "brake, because a rarely-fed domain that is GOOD at what it does get looks identical to a "
            "dead one from a utilization-only vantage point -- and the domain cull is the mechanism that "
            "deleted 200,000 memory entries under a phased schedule, which is catastrophic forgetting "
            "performed by the manager rather than suffered by the model. Wired rather than passed so "
            "that a run cannot have the brake on for experts and off for domains without anybody saying "
            "so; fabric/levers.py:693 names this field as the receiving spelling.",),

    # --- the optimizer's two rate endpoints -> the fabric's per-expert envelope ---------------------
    Coupling(
        src="OPT.lr",
        dst="FAB.d_base_lr",
        compute=lambda r: r["OPT"].lr,
        unit=U.FRACTION,
        irreducible=False,
        why="The per-expert triangular2 envelope is built from the PEAK rate: self_organize.py:7252 is "
            "`_oa = _lo + (LR - _lo) * (1.0 - _x).clamp_min(0.0) * _amp`, where LR is the optimizer's "
            "peak. FAB may not read OPT's lever and must not carry a second one, and until some name "
            "lands FAB_LR_OWN=1 has no legal way to learn the number -- which is what makes ISSUES H15 "
            "spellable at all: `_lrv` is assigned only inside `if LR_SCHED != \'none\'` at :7093-7094 and "
            "read unconditionally by the per-expert block at :7195, so LR_SCHED=none with FAB_LR_OWN=1 "
            "dies with a NameError on the first flush. THE NAME IS d_base_lr AND NOT d_lr_peak because "
            "the RECEIVING package already declares that spelling (fabric/levers.py:756) and the "
            "receiver's `grep d_` is the one that has to find the field; opt/levers.py:186 records both "
            "spellings as an open choice, and this row settles it. The PEAK is a frozen lever and "
            "belongs here; the LIVE rate the ratio clamp compares against is a different number and "
            "stays a call argument, which is the distinction the two independent specs of this mechanism "
            "disagreed about.",),
    Coupling(
        src="OPT.lr_min_frac",
        dst="FAB.d_lr_min_frac",
        compute=lambda r: r["OPT"].lr_min_frac,
        unit=U.FRACTION,
        irreducible=False,
        why="The other endpoint of the same envelope, needed in the same block: :7251 is "
            "`_lo = LR * LR_MIN_FRAC`, so the floor the per-expert rate anneals toward is the "
            "optimizer's floor fraction and shipping one endpoint without the other leaves the fabric "
            "with half a rate. It is the schedule's floor and OPT owns it -- opt/levers.py:187 names "
            "d_lr_min_frac as the outgoing half -- and the floor exists for a goal-B reason that makes a "
            "second copy actively harmful: a schedule that anneals to nothing cannot learn anything that "
            "ARRIVES LATE, and the add-an-area entry point is the late-arrival case. Two packages "
            "annealing to two different floors would be two different continual-learning experiments "
            "reported as one.",),

    # --- LOCAL: more than one lever, one owner. No edge, no budget, still d_-prefixed. ---------------
    Coupling(
        src=("FAB.pressure", "FAB.slots"),
        dst="FAB.d_operating_population",
        compute=lambda r: derive.operating_population(r["FAB"].pressure, r["FAB"].slots),
        unit=U.EXPERTS,
        irreducible=True,
        why="IRREDUCIBLE, and this is the example PLAN section 4 is built on. pressure is not a modifier "
            "on the cull, it is a SETPOINT: below pressure x slots the cull gate is shut and the "
            "population grows, at or above it the cull runs, so the steady state IS pressure x slots and "
            "FAB_PRESSURE cannot be made independent of the slot count -- they are one control loop with "
            "two named ends. The cost of not writing it down was measured: FAB_N0=2048 against "
            "FAB_NMAX=4096 parks occupancy at 0.50, below a FAB_PRESSURE of 0.75, and the utilization "
            "cull, the utilization spare and FAB_RESCUE all read ARMED AND INERT for an entire "
            "investigation while the report showed them switched on."),
    Coupling(
        src=("OPT.batch_windows", "OPT.accum"),
        dst="OPT.d_effective_batch_windows",
        compute=lambda r: max(1, int(r["OPT"].batch_windows)) * max(1, int(r["OPT"].accum)),
        unit=U.COUNT,
        irreducible=True,
        why="The batch size a run actually trains at is windows per flush times flushes per optimizer "
            "step, and there is no third number. It is written down because the old tree reported the "
            "CONFIGURED one: accumulation was gated on a window counter instead of on backward passes, "
            "which measured 55 optimizer steps where 13 were due, so at ACCUM=4 the effective batch was a "
            "quarter of its label and every learning-rate result taken against that configuration was "
            "taken at a batch size other than the one it is filed under. OWNER CORRECTED HERE: it was "
            "declared as TRAIN.d_effective_batch_windows reading TRAIN.batch_w and TRAIN.accum, and there "
            "is no TRAIN package -- the loop is RUN and both levers are OPT's (BATCH_W -> "
            "OPT_BATCH_WINDOWS, ACCUM -> OPT_ACCUM), which opt/levers.py:133-147 states as the repair. It "
            "is still LOCAL: one owner, no edge, no budget."),
    Coupling(
        src="LM.ctx",
        dst="LM.d_pos_max",
        compute=lambda r: int(r["LM"].ctx),
        unit=U.TOKENS,
        irreducible=True,
        why="The positional table has one row per position a window can hold, so its height IS the "
            "context width -- a WIN-byte window tokenizes to at most WIN tokens. The census's MAXLEN "
            "promote-to-wire (CENSUS.md:415) records why it may not be a free literal: at "
            "self_organize.py:1586 the transformer arm does `p = torch.arange(L).clamp(max=s.maxlen - 1)`, "
            "so a context wider than a hardcoded 512 silently gives every position past 511 ONE shared "
            "embedding -- no error, no report line, a model that cannot tell those positions apart. The "
            "same file already derived the signature encoder's table from the window ('ENC_POS_MAX': "
            "('WIN',), :87) while leaving the LM's a literal: one fact declared two ways in one file. "
            "LOCAL AND SINGLE-SOURCE, which is unusual and deliberate: the census's reason says the value "
            "'arrives d_-prefixed from DATA's window lever', but no row in the census gives DATA a width "
            "-- WIN became LM_CTX (CENSUS.md:344) -- so both ends are LM's and there is no edge to book "
            "(lm/levers.py:143-152 reaches the same conclusion). What the row buys is not arithmetic but "
            "the refusal of a second literal: `grep -rn d_ src/` finds the height, and lever.py will not "
            "let anyone declare a lever that shadows it."),
]


# ==================================================================================================
# CANDIDATES THAT ARE NOT WIRES
#
# "If you cannot name a real reason it is NOT a wire -- it is a lever the receiving package should own."
# The rejections are written down because a rejection with a reason is the only thing that stops the same
# candidate being added next quarter by someone who cannot tell it was considered. Printed by render().
# ==================================================================================================

NOT_WIRES = (
    ("RUN.seed -> every package's d_seed",
     "The run seed does reach every package, but what a package needs is rng.derive_seed(name, seed), "
     "which is per-subsystem and keyed by the package's own name. Wiring it would put one near-identical "
     "edge per package into the graph and still not stop a package from deriving under the wrong name. "
     "The check that catches that is rng.issued(), which records every stream handed out, so a subsystem "
     "with zero draws reads armed-but-inert and a subsystem that never asked does not appear at all -- "
     "two different statements the report must be able to make (G4)."),

    ("RUN.epochs -> OPT.d_lr_horizon",
     "Rejected because it IS the defect. EPOCHS setting both the run length and the cosine horizon means "
     "two runs differing only in EPOCHS are two different learning-rate experiments, which is why "
     "units.Epochs says in as many words that it is never a schedule horizon. OPT owns its horizon as a "
     "declared lever; a run that wants them to agree sets both, and the report can then say so."),

    ("SIG.d_signature_width_bytes from LM.ctx x the measured bytes/token",
     "Not resolvable at assemble: bytes_per_token is MEASURED on the corpus the tokenizer has not seen "
     "yet, and Config freezes when build() returns, so there is no late wire and there must not be one -- "
     "a Config that can still be written after startup is a Config the report cannot claim the run used. "
     "derive.signature_width_bytes is the single named function instead; the sig package calls it once, "
     "keeps the answer, and must not recompute it as the vocabulary grows. That is not a style "
     "preference: the old tree resolved the width in two places from one knob whose zero meant "
     "max(WIN, int(WIN*bpt)) = 614 bytes at self_organize.py:5675 and max(1, SIG_WIN) = 1 byte at :3919, "
     "so every eval-path routing decision in every report was made on a one-byte signature."),

    ("EVAL.gist -> the eval-path signature width",
     "The census's sixth promote-to-wire (EVAL_GIST, CENSUS.md:66) and the ONE that cannot become a "
     "Coupling, for exactly the reason the row above gives. EVAL_GIST was never a lever: it selected "
     "between two constructions of a value SIG owns, and both branches were wrong -- at the shipped "
     "default `_eval_sig` (:3907-3927) built the eval signature from `[-max(1, SIG_WIN):]` with "
     "SIG_WIN=0, i.e. ONE BYTE, while training encoded >= 256; set to 0 it returned an all-zero gist "
     "that ranks the population identically for every window. The census's replacement is 'one "
     "signature, its width resolved once, and eval receives it as a d_-prefixed wire' -- and that width "
     "is derive.signature_width_bytes(win_tokens, bytes_per_token), whose second argument is MEASURED on "
     "a corpus the tokenizer has not seen when build() freezes. So the promote is honoured by the "
     "derive-and-keep discipline, not by a row in this table, and saying so here is the point: a "
     "promote-to-wire that quietly became nothing is indistinguishable from one nobody noticed."),

    ("MEM.cap as its own lever",
     "The most tempting one, and the reason MEM.d_capacity exists. A declared capacity next to a declared "
     "quota and a declared owner count is three numbers for two degrees of freedom; the third is "
     "discarded at runtime by whichever line runs last, and in the old tree that line was memory.py:36."),
)


# ---- one-time table checks, at import ------------------------------------------------------------
def _check_table(couplings):
    """Refuse two couplings writing one field, at import, before anything resolves.

    Wires.add already refuses a duplicate destination in the ledger, but LOCAL couplings never reach it,
    and both kinds ultimately write into the same Config._wired dict -- where a second write is a plain
    dict assignment that overwrites in silence. Silent-overwrite is 29 of the survey's 475 records and it
    is the class that leaves no trace in any log: the printed graph would still show both couplings, and
    affects() would still claim a reach for a lever whose value never arrives anywhere.
    """
    seen = {}
    for c in couplings:
        prior = seen.get(c.dst)
        if prior is not None:
            raise WireError(f"{c.dst} is declared twice: from {prior.src_text} ({prior.why[:60]}...) and "
                            f"from {c.src_text}. Two couplings into one field silently overwrite; if the "
                            f"receiver needs both values it needs two fields.")
        seen[c.dst] = c
    return couplings


def _check_endpoints(couplings, packages):
    """Refuse a coupling naming a field or a package no declaration owns. At IMPORT, not at build().

    THE FAILURE THIS REPLACES IS THE ONE THIS FILE WAS IN. Until the block at the top of this module
    imported the real packages, every endpoint here was a string nothing could contradict: the table
    named a package `TRAIN` that no census row owns, a lever `TRAIN.batch_w` that is OPT's
    `batch_windows`, a lever `TRAIN.grow_cap_every` that is CAP's `pin_windows`, and `TOK.vmax` for a
    field the census gives to LM. build() answered every one of them with a DEFERRED warning, because
    the packages were absent -- so four wrong names and thirteen right ones produced the same output,
    and the printed graph showed edges that could not be made. That is the untrippable-guard shape (60
    of the survey's 475 records) with the guard pointing at itself.

    WHY IMPORT TIME AND NOT build(). Two reasons, and the second is the one that matters. A malformed
    endpoint is a DECLARATION fault, and this module already fails declaration faults at import --
    _check_table, Coupling.__init__, _check_compute -- on a machine with no environment set, no packages
    resolved and no GPU. And build() legitimately runs against a SUBSET: `sets=` exists so a test or the
    isolation sweep can assemble three packages, and there a missing package is a deferral rather than a
    fault. Putting this check inside build() would either fire on every legitimate partial build or have
    to learn to tell the two apart, and a check with a subtlety is a check that gets relaxed.

    WHAT IT CANNOT SEE: whether the field means what the row thinks it means. `CAP.pin_windows` resolves
    and `CAP.lift` resolves, and swapping them would pass here. The unit column, the reason column and
    tests/test_couplings.py's known-answer table are what stand behind that; this is a name check.
    """
    findings = []
    for c in couplings:
        for endpoint, (p, f) in zip(c.reads, [_split(e, "src") for e in c.reads]):
            owner = packages.get(p)
            if owner is None:
                findings.append(f"{c.dst}: src={endpoint!r} names package {p!r}, which no LeverSet in "
                                f"this file declares. Registered here: {sorted(packages)}.")
            elif f not in owner._levers:
                near = sorted(owner._levers, key=lambda n: (abs(len(n) - len(f)), n))[:4]
                findings.append(f"{c.dst}: src={endpoint!r} names a field {p} does not declare. "
                                f"{owner.__name__} declares {len(owner._levers)} lever(s); closest by "
                                f"shape: {near}. A coupling reading a lever nobody owns is a row that "
                                f"can only ever DEFER, and a deferred row prints as a declared edge.")
        if c.dst_prefix not in packages:
            findings.append(f"{c.dst}: dst names package {c.dst_prefix!r}, which no LeverSet in this "
                            f"file declares. Registered here: {sorted(packages)}.")
    if findings:
        raise WireError("the coupling table names declarations that do not exist:\n  "
                        + "\n  ".join(findings))
    return couplings


_check_table(COUPLINGS)
_check_endpoints(COUPLINGS, PACKAGES)


# ---- build ---------------------------------------------------------------------------------------

def build(environ=None, sets=None, couplings=None, budget=None):
    """Resolve every LeverSet, run every coupling, freeze everything, return the typo-net warnings.

    Returns (configs, wires, warnings):
        configs   {PREFIX: Config}, every one frozen. Attribute access is the whole interface.
        wires     the Wires ledger, containing the CROSS couplings only -- the graph's real edges.
        warnings  list of strings, each one a thing a human should look at and none of them fatal.

    THE CALLER OF THIS FUNCTION HOLDS EVERY PACKAGE'S LEVERS, and that is the one place in the running
    system where that is true. Handing `configs["FAB"]` to a memory function is a legal Python call that
    no check here refuses and that the returned object cannot detect -- see the header for what actually
    constrains it. An entry point passing these out should pass each package its own, and the receiving
    function should say so with `cfg.owned_by("MEM")`, which is what turns a wrong hand-off into a
    startup failure rather than a plausible wrong number in a report.

    RUNS EXACTLY ONCE, AT STARTUP. Every Config is frozen before this returns, so there is no re-resolve
    and no second reader: the report reads the same object the run used. The old tree needed a SECOND
    environment reader (`_cfg`) purely because the ordinary one had a side effect, and both of them could
    be called at any point in a run -- which is how a knob acquired five defaults.

    `sets` and `couplings` exist so the isolation sweep and the ownership tests can assemble a SUBSET
    without importing the whole tree, and so this file can be exercised before any package exists. They
    default to the full registry and the full table, which is what production gets. `budget` defaults to
    wire.WIRE_BUDGET; it is a parameter only so a test can prove the budget bites without editing it.
    """
    warnings = []

    # -- 1. resolve ------------------------------------------------------------------------------
    if sets is None:
        sets = registry.all_sets()
    elif not isinstance(sets, dict):
        sets = {cls.PREFIX: cls for cls in sets}
    # Sorted so the resolution order, the freeze order and every printed table are the same on every
    # machine and every run. Dict order here follows import order, and import order follows whatever the
    # entry point happened to touch first -- which is a difference between two runs that no seed controls.
    configs = {p: sets[p].from_env(environ) for p in sorted(sets)}

    # -- 2. wire ---------------------------------------------------------------------------------
    wires = Wires(budget=WIRE_BUDGET if budget is None else budget)
    if couplings is None:
        couplings = COUPLINGS
    _check_table(couplings)
    for c in couplings:
        missing = [p for p in c.prefixes if p not in configs]
        if missing:
            # A DECLARED COUPLING WHOSE PACKAGES ARE NOT HERE IS DEFERRED, AND SAYS SO. Skipping it in
            # silence is the untrippable-guard shape (60 of 475 records) -- the graph would print an edge
            # that was never made, and affects() would hand the L3 sweep a reach the run does not have,
            # which reads as the sweep passing. During P1/P2 every row below is deferred because no
            # package exists yet, and that state must be visible rather than indistinguishable from a
            # working build.
            warnings.append(f"DEFERRED {c.src_text} -> {c.dst}: package(s) {missing} not registered. "
                            f"The coupling is declared and printed but was NOT made on this build.")
            continue
        value = c.compute(_view(c, configs))
        if c.local:
            # No ledger edge: every source is the destination's own package, so booking it would add the
            # owner to an affects() set that already contains it -- a budget line that cannot widen any
            # lever's reach. The d_ field is still written, and Config._wire still refuses a name that is
            # not d_-prefixed, so `grep d_` finds it exactly like a wire.
            configs[c.dst_prefix]._wire(c.dst_field, value)
        else:
            # THE WIRE PERFORMS THE ASSIGNMENT (into=). Not `cfg._wire(name, wires.add(...))`, which would
            # restate the destination in two places and let the ledger describe a different system than
            # the one running.
            wires.add(c.reads, c.dst, value, c.why, c.unit, into=configs[c.dst_prefix])

    # -- 3. freeze -------------------------------------------------------------------------------
    # EVERY Config, including the ones that received nothing. A package left unfrozen because no coupling
    # happened to name it is a package whose values can still be changed mid-run, and the guarantee this
    # spine sells is that the report reads what the run used.
    for cfg in configs.values():
        cfg._freeze()

    # -- 4. the typo net, G9 ---------------------------------------------------------------------
    if environ is None:
        # THE ONE SEAM IN THIS FILE, STATED RATHER THAN HIDDEN. lever.from_env is the only code in the
        # tree permitted to name os.environ, and it resolves None itself -- so when build() is called
        # with None the levers resolve correctly but this file never sees the mapping, and the typo net
        # has nothing to scan. The alternative was to name os.environ here or to alias it, and an alias
        # is precisely the move that defeats the AST rule and makes the check untrippable. So G9 degrades
        # loudly instead: the entry point must pass the environment in, and until it does, a mis-typed
        # knob is silently the default -- which is a failure this project has lost runs to.
        warnings.append("TYPO NET SKIPPED: build() was called with environ=None, so registry.unread_env "
                        "had no mapping to scan and misspelled knob names were NOT checked. Pass the "
                        "process environment to build() to turn G9 on.")
    else:
        for name, near in registry.unread_env(environ):
            warnings.append(f"UNREAD {name}: matches no declared lever. Closest: {near}. "
                            f"A mis-typed knob is silently the default.")

    # CLOSE THE ASSEMBLY. Last act, after every Config is resolved, wired and frozen, so nothing this
    # function legitimately does is refused. From here on lever.LeverSet.from_env raises.
    #
    # WHY IT IS HERE AND NOT LEFT TO THE AST CHECKS. A reviewer demonstrated the walk that needs no
    # import and no forbidden spelling: `LeverSet.__subclasses__()` from spine.lever -- the one module
    # every package MUST import -- returns all thirteen lever sets, and `getattr(sib, "from_" + "env")()`
    # then mints each one from the live environment. All ten ownership checks stayed green while a memory
    # module returned FAB and LM's env-overridden values. A package's OWN Config reaches the same class
    # through `cfg._owner.__mro__` with nothing imported at all.
    # Every static defence in this tree matches a name; this one matches a MOMENT, which is the only
    # thing a spelling cannot walk past.
    #
    # IT DOES NOT CLOSE THE DECLARATION HALF -- `sib._levers["alpha"].default` needs no from_env -- and
    # spine/lever.py says so at the latch rather than leaving it implied.
    lever._close_assembly()
    return configs, wires, warnings


# ---- render --------------------------------------------------------------------------------------

def render(configs, wires, couplings=None):
    """The printable coupling graph, for docs/03_WIRING.md. Returns text; prints nothing.

    IRREDUCIBLE couplings are separated from chosen ones because they are different KINDS of claim. An
    irreducible coupling is a statement about arithmetic -- pressure x slots IS the equilibrium population
    -- and no future refactor removes it. A chosen coupling is a decision, and a reader deciding whether
    to keep it needs to see it is a decision. Mixing them makes the whole list read as inevitable, which
    is how a coupling graph stops being reviewed.

    IRREDUCIBILITY IS THE OUTER AXIS AND RESOLVED/DEFERRED IS A PER-ROW STATUS, not the other way round.
    The first draft split resolved from deferred at the top level, and on today's tree -- where no package
    is registered and all ten rows deferred -- that produced a docs/03_WIRING.md with an empty IRREDUCIBLE
    section and every coupling filed under DEFERRED. The document's whole job is to show which couplings
    are physics and which are choices, and it lost exactly that on the only build that then ran. That
    tree is gone -- all thirteen packages are imported and no row defers -- but the ordering stays,
    because `build(sets=...)` still assembles subsets and the isolation sweep is the caller that does.

    The reason column is never truncated, for the same reason wire.render does not truncate it: a
    justification cut off at the column edge reads as justified.
    """
    if couplings is None:
        couplings = COUPLINGS
    cfgs = dict(configs)

    # What actually landed, as opposed to what was declared. Read off the Configs rather than trusted
    # from the table, because "the table says so" is exactly the claim this section exists to check: a
    # declaration whose value never arrived is the failure the DEFERRED status exists to make visible.
    landed = {}
    for p, cfg in cfgs.items():
        for f, v in cfg.wired().items():
            landed[f"{p}.{f}"] = v

    live = [c for c in couplings if c.dst in landed]
    deferred = [c for c in couplings if c.dst not in landed]
    local = [c for c in live if c.local]

    L = []
    L.append("=== coupling graph ===")
    L.append(f"{len(couplings)} declared, {len(live)} resolved, {len(deferred)} deferred; "
             f"{len(wires)} of {wires.budget} wire budget spent.")
    L.append(f"{len(local)} of the resolved couplings are intra-package: they are still d_-prefixed and "
             f"still printed,")
    L.append("but they book no edge and spend no budget, because an edge from a package to itself cannot")
    L.append("widen any lever's affects() set.")
    L.append("")
    L.append("Every value below is d_-prefixed on its receiving Config. The wire names the field, not the")
    L.append("receiver, so `grep -rn d_ src/` is a complete index of the couplings in this system.")
    L.append("")

    def block(title, rows, note):
        L.append(f"--- {title} ({len(rows)}) ---")
        L.append(note)
        L.append("")
        if not rows:
            L.append("  (none)")
            L.append("")
        for c in rows:
            if c.dst in landed:
                v = repr(landed[c.dst])
                state = f"= {v[:37] + '...' if len(v) > 40 else v}  [{c.unit}]"
            else:
                # No value, and no placeholder that could be mistaken for one. A deferred row is a
                # declaration whose packages are not in this build; printing "= '<not resolved>'" put a
                # quoted string where every other row has a number, which reads as a value at a glance.
                state = f"[{c.unit}]  DEFERRED -- not made on this build"
            L.append(f"  {c.src_text}")
            L.append(f"    -> {c.dst} {state}" + ("  (intra-package)" if c.local else ""))
            L.append(f"       why: {c.why}")
            L.append("")

    block("IRREDUCIBLE", [c for c in couplings if c.irreducible],
          "  One quantity named twice. No interface design separates these two ends; a project claiming\n"
          "  they are independent is describing a system other than the one it runs.")
    block("DECLARED, REDUCIBLE", [c for c in couplings if not c.irreducible],
          "  Couplings this design chose. A later design may un-choose them, which is why each says what\n"
          "  the receiving package would have to own instead.")
    if deferred:
        L.append(f"--- deferred on this build ({len(deferred)}) ---")
        L.append("  Declared and printed above, but NOT made here: the packages are not registered yet.")
        L.append("  Listed again together so an unbuilt coupling is never mistaken for a working one.")
        L.append("")
        for c in deferred:
            L.append(f"  {c.src_text} -> {c.dst}")
        L.append("")

    L.append("--- package graph ---")
    g = wires.graph()
    if not g:
        L.append("  (no cross-package edges resolved; sinks and intra-package couplings do not appear)")
    for p, targets in g.items():
        L.append(f"  {p} -> {', '.join(targets)}")
    L.append("")
    L.append("  Packages that only receive appear as targets and never as keys. That asymmetry is the")
    L.append("  point: a sink cannot leak onward, and affects() is one hop.")
    L.append("")

    L.append("--- considered and rejected ---")
    L.append("  A coupling with no nameable reason is not a wire; it is a lever the receiver should own.")
    L.append("")
    for cand, reason in NOT_WIRES:
        L.append(f"  {cand}")
        L.append(f"       why not: {reason}")
        L.append("")

    L.append("--- what a coupling's value may depend on ---")
    # PRINTED FOR THE SAME REASON THE REASONS ARE PRINTED. A reader of docs/03_WIRING.md is being asked
    # to believe that the rows above are the whole coupling graph, and that claim rests entirely on a
    # compute being unable to read anything else. The boundary is enforced at construction
    # (COMPUTE_ALLOWLIST, checked by _check_names); it belongs in the document where the claim is made,
    # because a guarantee nobody can see the edge of is a guarantee nobody audits.
    L.append("  Every value above is computed from the levers named in its src, through a view that")
    L.append("  raises on an undeclared read, by a function whose free names are checked at declaration")
    L.append("  against this list and nothing else:")
    L.append("")
    for name, why in COMPUTE_ALLOWLIST.items():
        L.append(f"  {name}")
        L.append(f"       {why}")
        L.append("")

    L.append("--- the ledger as the isolation sweep's oracle sees it ---")
    # wire.Wires.render, not a second table built here. wire.py's docstring is explicit about why: the old
    # tree had a report path and an audit path formatting one quantity two ways, and they drifted.
    L.append(wires.render(out=io.StringIO()))
    return "\n".join(L)
