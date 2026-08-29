"""The coupling ledger: every value that crosses a package boundary, recorded as an edge.

A value one package owns and another genuinely needs is not READ across the boundary; it is WIRED. The
difference is that a read leaves no trace and a wire is a record, so the complete coupling graph of the
system is a list you can print.

WHY THE `d_` PREFIX SURVIVES THE RENAME (graft G5). The judges' objection to wires was exact: "wires
launder couplings -- `fab.nmax` arrives in `domains` as `expert_slots` and looks owned." It would, if the
RECEIVER got to name the field. It does not. The destination name is part of the WIRE record and the wire
is what performs the assignment (`Wires.add(..., into=cfg)` calls `Config._wire`), so the receiving package
never chooses the name it arrives under. `Config._wire` then refuses any name that is not `d_`-prefixed.
The consequence is the one that matters: a plain `grep -rn 'd_' src/` enumerates every coupling in the
system, with no tooling, no AST pass and nothing to keep in sync. A value that looks locally owned at the
point of use cannot be a coupling, because a coupling could not have been assigned a locally-owned name.

WHY `affects()` IS COMPUTED HERE AND NOT WRITTEN DOWN (graft G1). L3 -- "flipping a lever must change only
the packages in its `affects()` set" -- is the only one of the three lever rules that can see a coupling
through shared state, RNG draw order or the data. It is therefore the load-bearing check, and it is only
as good as its oracle. A hand-maintained `AFFECTS = {...}` table would be written by the same person whose
leak the sweep exists to catch: they add the lever, they add its reach, and the sweep is permanently green
for that lever from the day it is declared. So `affects()` is derived from the ledger the wiring code had
to write anyway in order to function. To widen a lever's declared reach you must actually declare a wire,
and a wire has a destination field that `tests/test_ownership.py` cross-checks against the receiving
Config. Lying to the oracle costs more than telling it the truth.

WHAT THIS MODULE DOES NOT DO. It does not prove the ledger is complete. Nothing here can: a package that
reaches another through a module global, a shared RNG or the data stream writes no wire. That is exactly
what the behavioural sweep in `tests/test_lever_isolation.py` is for, and this module's job is to hand that
sweep an oracle it did not author. The checks below (shape, duplicate destinations, budget) are cheap
spelling checks on a ledger that is assumed to be honest; the honesty is checked elsewhere.

There is deliberately NO module-level singleton ledger. `spine/assemble.py` constructs one `Wires()` and
owns it. A global would make WIRE_BUDGET a function of how many test modules had been imported first,
which is the kind of guard that trips on the wrong thing and then gets raised until it never trips at all.
"""
import re

from . import units as U
from . import registry
from .lever import LeverError


# ---- the budget ---------------------------------------------------------------------------------
# WIRE_BUDGET IS A SPEED BUMP, NOT THE GUARANTEE. It is one edit away from being 26, and the design
# review said so. Its only real work is to make growing the coupling graph a visible act -- somebody has
# to change this number in a commit, and that shows up in review -- rather than a thing that happens one
# convenient wire at a time until the "declared graph" is the old 328-knob tangle with a ledger stapled on.
#
# The load-bearing checks are in tests/test_ownership.py and they are two-directional:
#   every wire's destination must be a d_-prefixed field that actually exists on the receiving Config, and
#   every d_ field on every Config must correspond to a declared wire.
# A coupling that is not declared fails; a declared coupling that does not exist fails. Neither of those
# can be satisfied by editing a number.
WIRE_BUDGET = 25

_PREFIX_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")

# Placeholders that are syntactically a `why` and semantically nothing. This list is not a meaning check
# and cannot be one -- see _check_why.
_NON_REASONS = frozenset({"todo", "tbd", "fixme", "n/a", "na", "none", "wire", "needed", "required",
                          "because", "see above", "obvious", "xxx", "?"})


class WireError(LeverError):
    """A malformed or over-budget wire. Subclasses LeverError because it is the same kind of problem:
    a declaration fault, always fatal, always at startup, never mid-run."""


def _split(spec, what):
    """Split a "PREFIX.field" endpoint into its two halves, or fail by name.

    Endpoints are strings rather than (LeverSet, attr) pairs on purpose: `spine/assemble.py` must be
    readable as a list of couplings by someone who is not going to import anything, and docs/03_WIRING.md
    is generated from it. The cost is that a typo is a runtime error rather than a NameError, which is
    what the checks below and the ownership test buy back.
    """
    if not isinstance(spec, str):
        raise WireError(f"{what} must be a 'PREFIX.field' string, got {type(spec).__name__}")
    prefix, dot, field = spec.partition(".")
    if not dot:
        raise WireError(f"{what}={spec!r} must be 'PREFIX.field' -- an endpoint without its owning "
                        f"package is the unattributed name this whole spine exists to remove")
    if not _PREFIX_RE.match(prefix):
        raise WireError(f"{what}={spec!r}: {prefix!r} is not an UPPERCASE LeverSet PREFIX")
    if not field.isidentifier() or field.startswith("_"):
        raise WireError(f"{what}={spec!r}: {field!r} is not a legal field name")
    return prefix, field


def _env_name(prefix, field):
    """The environment name a lever endpoint corresponds to. Must agree with Lever.env_name, which
    generates f"{PREFIX}_{FIELD.upper()}" -- if that ever changes, affects() silently starts returning
    just {owner} for every lever and the L3 sweep goes green everywhere. tests/test_ownership.py pins
    the two together for that reason."""
    return f"{prefix}_{field.upper()}"


def _check_why(why):
    """Reject an absent reason. Deliberately NOT a check that the reason is a good one.

    The design review's complaint stands as written: "a reason is prose that passes an AST check." It is,
    and no rule here can tell a true explanation from a plausible one. What this does catch is the empty
    string, the single word, and the handful of placeholders below -- the forms a reason takes when the
    author was routing around the requirement rather than answering it. Everything past that is caught by
    the fact that `render()` prints the reason beside the value in docs/03_WIRING.md, where a wrong reason
    sits next to the number it fails to explain and a reader can see it.
    """
    if not isinstance(why, str):
        raise WireError(f"why must be a string, got {type(why).__name__}")
    text = why.strip()
    if not text:
        raise WireError("why is required: a coupling with no stated reason is indistinguishable from a "
                        "coupling nobody noticed. Say what breaks if this value is not wired.")
    if text.lower().rstrip(".!") in _NON_REASONS or " " not in text:
        raise WireError(f"why={why!r} is a placeholder, not a reason. One sentence, plain English: what "
                        f"goes wrong in the receiving package if this value is not the owner's value.")
    return text


# Units are strings from spine.units plus the clock KINDs. Checked against that module rather than left
# free-form because a wire is precisely where a unit mismatch is invisible: the value arrives already
# computed, under a name the receiver did not choose, and the receiver has no declaration to compare it
# against. 32 of the survey's 475 records are unit mismatches. A unit this does not recognise belongs in
# spine/units.py, where it is written down once, not in a string literal in a wiring call.
def _known_units():
    out = {v for k, v in vars(U).items() if k.isupper() and isinstance(v, str)}
    out.update(k.KIND for k in U.CLOCK_KINDS)
    return out


def _check_unit(unit):
    if isinstance(unit, type) and issubclass(unit, U.Clock):
        return unit.KIND                      # a clock kind may be named by its class or by its KIND
    if unit not in _known_units():
        raise WireError(f"unit {unit!r} is not declared in spine.units. Add it there -- a unit that "
                        f"exists only in a wiring call is a unit nothing else can be checked against.")
    return unit


class Wire:
    """One recorded coupling: a value the owner computed, the name it arrives under, and why it crosses.

    Frozen for the same reason a Config is frozen: this record is read by the report, by docs generation
    and by the isolation sweep's oracle, and all three must see the ledger the run actually used.
    """

    __slots__ = ("src", "reads", "dst", "value", "why", "unit",
                 "src_prefix", "dst_prefix", "dst_field", "src_envs")

    def __init__(self, src, dst, value, why, unit=U.COUNT):
        # src is normally one "PREFIX.lever" string and `.src` gives it back unchanged. It may also be a
        # tuple, for the case G1's formula is written for: reads(d) is a SET, because a derived value can
        # genuinely depend on levers from two different owners. `.reads` is always the tuple, and
        # affects() uses `.reads`, so a two-owner wire correctly widens BOTH owners' declared reach. If
        # only `.src` existed, the second owner's lever would have a reach the oracle could not see and
        # the L3 sweep would read its real effect as a leak.
        try:
            reads = (src,) if isinstance(src, str) else tuple(src)
        except TypeError:
            # Caught rather than allowed to propagate because a bare "'int' object is not iterable" from
            # inside a tuple() call names neither the wire nor the argument, and a wiring file failing at
            # startup must say which line is wrong or the author goes reading this module instead.
            raise WireError(f"src must be a 'PREFIX.field' string or a tuple of them, got {src!r}")
        if not reads:
            raise WireError("a wire must read at least one lever; src is empty")
        pairs = [_split(s, "src") for s in reads]
        dst_prefix, dst_field = _split(dst, "dst")

        # THE d_ RULE, GRAFT G5, ENFORCED AT THE POINT THAT ASSIGNS THE NAME. Config._wire refuses a
        # non-d_ name too, but it only ever sees the name this record handed it, so checking here is what
        # makes the record and the assignment agree. A wire that recorded "DOM.expert_slots" while
        # actually writing "d_expert_slots" would be a ledger that describes a different system.
        if not dst_field.startswith("d_") or len(dst_field) <= 2:
            raise WireError(f"dst={dst!r}: the destination field must be d_-prefixed (graft G5). A value "
                            f"computed from more than one package's levers is a COUPLING, and `grep d_` "
                            f"must find it. The wire names the field so the receiver cannot launder it "
                            f"into a name that looks locally owned.")

        for (p, f), s in zip(pairs, reads):
            # A WIRE MAY NOT SOURCE A d_ FIELD. Forwarding a value a package received rather than owns
            # would make the graph transitive, and affects() is deliberately ONE HOP -- it unions the
            # direct receivers of L and stops. With chaining allowed, A -> B -> C would give L an
            # affects() of {A, B} while its real reach includes C, and the sweep would report C's
            # perfectly correct response as an undeclared leak. Wire from the original owner instead;
            # if the value is genuinely derived from two owners, pass both in src.
            if f.startswith("d_"):
                raise WireError(f"src={s!r} is a wired field, not an owned lever. A package may not "
                                f"re-export a value it does not own -- wire from the owner, or name both "
                                f"owners in src. affects() is one hop and chaining would silently "
                                f"understate a lever's reach.")
            if p == dst_prefix:
                raise WireError(f"src={s!r} and dst={dst!r} are the same package. A value computed from "
                                f"one package's own levers is a DERIVATION, not a coupling -- put it in "
                                f"spine/derive.py. Booking it here spends budget and inflates affects() "
                                f"with an edge that cannot leak anywhere.")

        object.__setattr__(self, "src", src if isinstance(src, str) else tuple(reads))
        object.__setattr__(self, "reads", tuple(reads))
        object.__setattr__(self, "dst", dst)
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "why", _check_why(why))
        object.__setattr__(self, "unit", _check_unit(unit))
        object.__setattr__(self, "src_prefix", pairs[0][0])
        object.__setattr__(self, "dst_prefix", dst_prefix)
        object.__setattr__(self, "dst_field", dst_field)
        object.__setattr__(self, "src_envs", tuple(_env_name(p, f) for p, f in pairs))

    def __setattr__(self, k, v):
        raise WireError(f"wire {self.dst} is frozen; the ledger is written once, during assemble")

    def __delattr__(self, k):
        raise WireError(f"wire {self.dst} is frozen; the ledger is written once, during assemble")

    @property
    def src_text(self):
        """How the source reads in a table. Multi-owner wires show every owner, because a reader
        scanning docs/03_WIRING.md for who can move a number must see all of them."""
        return " + ".join(self.reads)

    @property
    def src_prefixes(self):
        return tuple(dict.fromkeys(s.partition(".")[0] for s in self.reads))

    def __repr__(self):
        return f"<Wire {self.src_text} -> {self.dst} = {self.value!r} {self.unit}>"


class Wires:
    """The ledger. Append-only during assemble, read-only afterwards, and the source of every claim this
    project makes about its own coupling graph."""

    def __init__(self, budget=WIRE_BUDGET):
        self._wires = []
        self._by_dst = {}
        self.budget = budget

    # -- writing -------------------------------------------------------------------------------------
    def add(self, src, dst, value, why, unit=U.COUNT, into=None):
        """Record one coupling and return the value, so the wiring line reads as an assignment.

        `into` is the receiving Config. Pass it. When it is passed, THE WIRE performs the assignment --
        `into._wire(dst_field, value)` -- and that is the mechanism behind the whole G5 claim: the
        receiving package never gets to choose the name, so a coupling cannot arrive under a local name
        that looks owned. Calling `cfg._wire("d_slots", wires.add(..., dst="DOM.d_expert_slots", ...))`
        by hand would restate the destination in two places and let the two drift, which is a ledger that
        describes a system other than the one running. It is optional only so the ledger can be built and
        inspected in tests and in docs generation without materialising every Config.
        """
        w = Wire(src, dst, value, why, unit)

        # ONE WIRE PER DESTINATION. Two wires writing one d_ field is a silent overwrite -- the second
        # value wins, the first coupling still appears in the printed graph, and affects() then claims a
        # reach for a lever whose value never arrives anywhere. Silent-overwrite is 29 of the survey's
        # 475 records and it is the class that leaves no trace at all in a log.
        prior = self._by_dst.get(w.dst)
        if prior is not None:
            raise WireError(f"{w.dst} is already wired from {prior.src_text} ({prior.why!r}). Two wires "
                            f"into one field silently overwrite; if the receiver needs both values it "
                            f"needs two fields.")

        # Budget check AFTER the shape checks, so a malformed wire fails with its own message rather than
        # with "over budget" and sends the author to the wrong problem.
        if len(self._wires) >= self.budget:
            raise WireError(
                f"WIRE_BUDGET={self.budget} reached; {w.src_text} -> {w.dst} would be #{len(self._wires) + 1}. "
                f"The budget is a speed bump, not a guarantee -- raising it is one edit. Do that only in a "
                f"commit that says why the coupling graph needs to be larger, and expect the number to be "
                f"read as the claim it is.")

        # THE ASSIGNMENT HAPPENS BEFORE THE APPEND, AND THAT ORDER IS LOAD-BEARING. The first version of
        # this method appended first and then checked `into`, so a wire refused for naming the wrong
        # receiving package -- or refused by Config._wire because the Config was already frozen -- stayed
        # in the ledger anyway. The result is a recorded edge whose value never arrived: render() prints
        # a coupling that does not exist and affects() hands the L3 sweep a package that cannot have
        # moved, which reads as the sweep passing. The ledger must only ever contain wires that took
        # effect. Found by the smoke exercise, which counted five wires after four successful add() calls.
        if into is not None:
            if getattr(into, "prefix", None) != w.dst_prefix:
                raise WireError(f"dst={w.dst!r} names package {w.dst_prefix} but `into` is "
                                f"{getattr(into, 'prefix', into)!r}. The ledger and the assignment must "
                                f"agree or the printed graph is fiction.")
            into._wire(w.dst_field, value)
        self._wires.append(w)
        self._by_dst[w.dst] = w
        return value

    # -- reading -------------------------------------------------------------------------------------
    def all(self):
        """Every wire, in declaration order. A tuple, so a caller cannot append to the ledger through a
        list it was handed rather than through add()."""
        return tuple(self._wires)

    def __len__(self):
        return len(self._wires)

    def __iter__(self):
        return iter(self._wires)

    def by_dst(self, dst):
        return self._by_dst.get(dst)

    def dsts(self):
        """Every declared destination, "PREFIX.d_field". tests/test_ownership.py compares this set with
        the d_ fields actually present on the assembled Configs, in both directions."""
        return tuple(w.dst for w in self._wires)

    def graph(self):
        """The coupling graph at package granularity: owner PREFIX -> the PREFIXes it feeds.

        Package granularity because that is the granularity the L3 sweep measures at -- it diffs one
        integer fingerprint per package (tokenizer id2bytes order, memory slot table, fabric routing
        histogram, stream label histogram, ledger counters), so a finer graph would make claims the sweep
        cannot check. Packages that only receive appear as values and not as keys; that asymmetry is the
        point, since a sink cannot leak onward.
        """
        g = {}
        for w in self._wires:
            for p in w.src_prefixes:
                g.setdefault(p, set()).add(w.dst_prefix)
        return {p: tuple(sorted(v)) for p, v in sorted(g.items())}

    # -- the oracle, graft G1 ------------------------------------------------------------------------
    def affects(self, env_name, env_owner=None):
        """affects(L) = {owner(L)} union {owner(d) : L in reads(d)}, computed from this ledger.

        This is the oracle `tests/test_lever_isolation.py` checks the measured reach against: flip L, run
        200 seeded CPU steps, and every package whose fingerprint moved by more than the test_determinism
        noise floor must be in this set. It is computed and never declared -- see the module docstring.
        The formula is one hop, which Wire enforces by refusing a wire whose source is itself a d_ field.

        `env_owner` overrides the registry's ENV_NAME -> PREFIX map, for tests that want to exercise the
        formula without importing the whole tree. Production callers pass nothing.
        """
        owners = registry.all_env_names() if env_owner is None else dict(env_owner)

        # AN UNKNOWN LEVER IS FATAL, NOT AN EMPTY SET. Returning frozenset() for a name the registry does
        # not know would make the sweep pass for that lever no matter what it did -- "measured reach is a
        # subset of {}" fails loudly, but "no packages moved" against an empty oracle is a green tick, and
        # a lever that was renamed on one side only would go untested forever. Untrippable guards are 60
        # of the survey's 475 records; this is the shape they take.
        if env_name not in owners:
            near = sorted(owners, key=lambda n: (abs(len(n) - len(env_name)), n))[:3]
            raise WireError(f"{env_name!r} is not a declared lever, so it has no owner and no computable "
                            f"reach. Closest declared: {near}. Has its package been imported?")

        # A STALE LEDGER ENTRY SHRINKS EVERY ANSWER. If a wire names a source that no longer resolves to a
        # declared lever -- the lever was renamed, its package was not imported -- then the edge silently
        # stops counting and affects() understates the reach of whatever that lever is called now. That is
        # the sweep going green because its oracle got smaller, which is the exact failure G1 exists to
        # prevent, so it is refused rather than skipped.
        stale = self.unresolved(owners)
        if stale:
            raise WireError(f"the ledger has {len(stale)} unresolved source(s): {stale}. A source that "
                            f"does not resolve to a declared lever drops its edge out of affects(), and a "
                            f"smaller oracle makes the isolation sweep pass by having nothing to compare.")

        out = {owners[env_name]}
        for w in self._wires:
            if env_name in w.src_envs:
                out.add(w.dst_prefix)
        return frozenset(out)

    def unresolved(self, env_owner=None):
        """Source endpoints in the ledger that do not correspond to a declared lever. Empty is the only
        acceptable answer once every package is imported; tests/test_ownership.py asserts that."""
        owners = registry.all_env_names() if env_owner is None else dict(env_owner)
        return tuple(sorted({e for w in self._wires for e in w.src_envs if e not in owners}))

    # -- rendering -----------------------------------------------------------------------------------
    def render(self, out=None, width=52):
        """Print the ledger as a table and return the text.

        The text is returned as well as printed because docs/03_WIRING.md is generated from it and a doc
        built by re-implementing the formatting would be a second renderer that drifts from the first --
        the old tree had exactly that, a report path and an audit path printing different numbers for one
        quantity. The reason column is never truncated: the reason is the part a reader is here for, and a
        coupling whose justification is cut off at the column edge reads as justified.
        """
        rows = [("SRC", "DST", "VALUE", "UNIT", "WHY")]
        for w in self._wires:
            v = repr(w.value)
            if len(v) > 24:
                v = v[:21] + "..."
            rows.append((w.src_text, w.dst, v, str(w.unit), w.why))
        wid = [min(width, max(len(r[i]) for r in rows)) for i in range(4)]
        lines = [f"=== coupling graph: {len(self._wires)} wires of {self.budget} budgeted ==="]
        for i, r in enumerate(rows):
            lines.append("  ".join(r[j].ljust(wid[j])[:wid[j]] for j in range(4)) + "  " + r[4])
            if i == 0:
                lines.append("-" * (sum(wid) + 8 + len(rows[0][4])))
        if not self._wires:
            # An empty ledger is a legitimate state (P1 has no packages yet) but it is also what a broken
            # assemble looks like, so it says which it is rather than printing a bare header.
            lines.append("(no wires declared -- either nothing crosses a boundary yet, or assemble "
                         "did not run)")
        text = "\n".join(lines)
        if out is None:
            print(text)
        else:
            print(text, file=out)
        return text

    def __repr__(self):
        return f"<Wires {len(self._wires)}/{self.budget} wires, {len(self.graph())} emitting packages>"
