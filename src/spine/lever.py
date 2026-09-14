"""The lever: declared once, owned by one package, read from the environment in one place.

THE FAILURE THIS REPLACES. The old tree kept 328 knobs in a single `_SPEC` table with a hand-typed
owner comment beside each name. Comments drift and did: `LOSS_MASK_DEAD` is tagged `# tokenizer` inside
the `--- domains ---` block, and 41 knobs are filed under `misc`. Values were then materialised as module
globals and read anywhere by anyone through `_env`/`_i`/`_f`, each call site restating the default -- so a
knob could have five defaults, and the audit reader `_cfg` had to exist as a SECOND reader because the
ordinary one had a side effect.

WHAT REPLACES IT, and why each piece is shaped this way:

  OWNERSHIP IS THE NAMESPACE, NOT A TAG. A lever is a class attribute on exactly one LeverSet subclass,
  and its environment name is GENERATED as f"{PREFIX}_{FIELD.upper()}". There is no `name=` parameter, so
  a name cannot be attached to a foreign owner, and there is no owner comment to drift out of date.

  ONE DEFAULT, AND IT MUST BE A LITERAL. The default lives on the declaration and nowhere else. Reading
  is `cfg.n0`, not `_i("FAB_N0", 2048)` -- there is no second place to put a different number.

  ONE READER. `from_env()` is the only code in the tree permitted to name os.environ. tests/test_ownership
  asserts it, and the old tree needed that assertion: tokenizer.py read TOK_MINT_PMIN and TOK_MINT_GATE_K
  straight from os.environ, invisible to the registry and to every audit built on it.

  RESOLVED ONCE, FROZEN. A Config is immutable. There is no re-read, so the report reads the same object
  the run used and `_cfg` has no reason to exist.

WHAT OWNERSHIP DOES NOT BUY, BECAUSE THE WRONG SENTENCE HERE IS WORSE THAN NO SENTENCE. Everything above
is about DECLARATION: which name exists, who owns it, where its value comes from. None of it constrains
where a resolved Config then goes. `assemble.build()` returns `{PREFIX: Config}`; a Config is an ordinary
object that does not know who is holding it; and a function handed the wrong one reads it happily --
    def memory_prune(cfg): return cfg.slots        # memory_prune(configs["FAB"]) -> 2048, no error
which a reviewer ran, against docstrings in this file and in spine/assemble.py that called it an
"author-time NameError". It is not one. What IS structural is narrower and each clause has a check:
a module may not name os.environ (O1), may not hold two lever sets under any spelling (O3), and may not
call `from_env` at all outside spine/assemble.py (O8) -- so a module cannot MINT a foreign Config. Being
HANDED one is a call the entry point makes on purpose, and `Config.owned_by(PREFIX)` is the assertion at
the receiving end that turns a wrong-package hand-off into a startup failure instead of a wrong number.
"""
import decimal as _decimal
import math as _math
import os
from collections import namedtuple as _nt

from . import units as U


class LeverError(Exception):
    """A declaration or resolution problem. Always fatal, always at startup, never mid-run."""


# ==================================================================================================
# THE TWO PARSE-LEVEL REFUSALS, AND THE SWITCH ON EACH
# ==================================================================================================
#
# WHAT LIVES HERE AND WHAT DOES NOT. Both constants below govern a rule that is true of a whole
# DECLARED TYPE and is therefore not a per-lever judgement: "a float lever does not resolve to a
# non-finite number" and "an int lever resolves to the integer its string denotes". Neither states
# anything about a particular mechanism, neither needs to know what the value is for, and neither can
# be derived from a range. The per-lever judgement is `domain=` on the declaration, which carries no
# switch of its own -- its blast radius is one lever and deleting the kwarg is the switch.
#
# WHY A MODULE CONSTANT AND NOT A LEVER, and this is the shape .rework/DECISIONS.md D17 settled on
# for the five period refusals (src/ckpt/api.py::REFUSE_NEGATIVE_PERIOD and its four siblings). D17
# ruled that a refusal kept "for now" is kept WITH A SWITCH rather than as a code path that rots, and
# the shape it landed on after weighing three carriers is a module-level constant. Two of its reasons
# are stronger here than they were there:
#   * A LEVER CANNOT CARRY THIS. The lever system is the thing being switched -- these rules run
#     inside Lever.coerce, before any Config exists -- so a lever-shaped switch is circular. The only
#     environment-variable form available is a raw os.environ read inside coerce. That is LEGAL here
#     (tests/test_ownership.py::check_o1_one_env_reader permits exactly this file to name the
#     environment) and it is REFUSED anyway: it would be the tree's first environment name that is
#     not a lever -- invisible to spine/registry.py, to tests/test_census.py, whose N1/N2 join on
#     lever names, and to docs/04_LEVERS.md -- which is precisely the failure this module's own
#     header exists to end ("tokenizer.py read TOK_MINT_PMIN and TOK_MINT_GATE_K straight from
#     os.environ, invisible to the registry and to every audit built on it").
#   * THE MEASUREMENT NEEDS BOTH ARMS IN ONE PROCESS. spine/lever.py latches the assembly after one
#     build, so a lever-shaped switch needs a fresh process per arm; a constant is set both ways in
#     one, which is what "does the refusal have a bad effect" has to be answered by running.
#
# WHAT THAT COSTS, STATED HERE RATHER THAN DISCOVERED. Turning either of these off is a CODE EDIT and
# not an environment variable: there is no SPINE_REFUSE_* name, these constants take no census row and
# no row in the generated lever document, and an operator holding only a shell cannot reach them.
# docs/04_CONTRACT.md already records the same gap for the five period refusals in its own words.
#
# ONE CONSTANT EACH, NOT ONE FOR BOTH, and the reason is not symmetry. The two rules govern DISJOINT
# populations -- 97 float levers and 110 int levers, measured, with no lever in both -- and answer
# different questions. A single flag would mean that an operator turning off the rule that broke
# their run also turns off a rule that had nothing to do with it, which is the "many spellings of one
# thing" failure inverted: one spelling for two things.

REFUSE_NON_FINITE_FLOAT = True
"""Whether Lever.coerce refuses nan, inf and -inf on a FLOAT lever. True is the shipped state.

WHAT IT GOVERNS, SCOPED EXACTLY AND MEASURED RATHER THAN ASSUMED. The 97 float levers and nothing
else. The 110 int levers ALREADY refuse every non-finite spelling and did before this constant
existed: `int(float(raw))` raises ValueError at 'nan' and OverflowError at 'inf'/'-inf'/'1e999', and
both are in coerce's except tuple, so all of them come out as this module's own LeverError naming the
lever. Driven across the live registry -- 110 int levers x {nan, NaN, inf, Inf, infinity, -inf,
+inf, 1e999, -1e999} = 990 cells, 0 accepted; the same 9 spellings across the 97 float levers = 873
cells, ALL accepted before this rule. Every one of the 24 non-finite findings in the 2026-09-05
lever-domain sweep is on a float lever, so the rule's reach and the defect's reach are the same set.

WHY THE FIRST READ. A non-finite float does not raise anywhere downstream. It propagates through
every arithmetic operation this tree performs and surfaces as a plausible number in a report -- the
sweep's FAB_COMP_EMA=nan crosses a package boundary into DOM.d_comp_ema with no warning at all. So
the refusal is placed where the string becomes a value, before anything is derived from it, which is
this module's refusal idiom and not a new one.

WHAT TURNING IT OFF COSTS. nan, inf and -inf resolve into frozen Configs again on all 97 float
levers. What is then left standing is the five per-package by-name refusals that exist today
(src/fabric/api.py::build, src/sig/api.py::build, src/opt/api.py::build,
src/tok/api.py::build_vocabulary, src/data/api.py::data_plan), and they cover only the levers those
bodies actually read: roughly 288 cells across the six sweep reports are UNREACHABLE_TODAY because the consumer is a P4/P5/P6 stub -- 33 FAB
levers, all 23 DOM and MEM floats, 14 of EVAL's 15 -- and a body that does not exist cannot refuse
anything. That is the cost, and it is the argument for the rule: a per-package refusal is written by
the author who writes the body, and this one is written once, now.

WHAT IT DOES NOT BUY, AND THE NUMBER IS NOT CLOSE. It refuses a SPELLING. It does not make any lever
harmless and nothing in this file can: OPT_LR=1e6 is finite, passes this rule, runs five stages
reporting OK and leaves every parameter at -3928; FAB_ALPHA=1e26 is finite, passes this rule, and
leaves the loss reading 0.5150710 / 2.943258 with 15 of 23 gradients already non-finite. The
finiteness boundary and the harm boundary are twenty-four orders of magnitude apart, measured. No
ceiling chosen to stop nan is a ceiling that stops harm.

WHAT WOULD CHANGE THE ANSWER. If any configuration this project runs ever sets a float lever
non-finite ON PURPOSE. Scanned across the repository on 2026-09-14 and the answer is none: the three
sites that spell a non-finite value beside a float lever's name (src/fabric/api.py FAB_ROUTE_T=+inf,
src/sig/api.py SIG_TEMP=-inf and SIG_WARMUP_MIN_FRAC=-inf) are all PROSE describing the defect, not
configuration. So the OFF state has no user today.
"""

REFUSE_INEXACT_INT = True
"""Whether Lever.coerce refuses an INT lever whose string does not denote the integer it resolves to.

THE ONE RULE, AND IT IS ABOUT THE VALUE AND NOT THE SPELLING: an int lever resolves to the integer
its string denotes, or it is refused. `int(float(raw))` is two lossy steps and this refuses exactly
when either one loses something. It closes two measured holes at that one line:

    MEM_REKEY_EVERY=0.4  ->  0   TRUNCATION INTO A DECLARED SENTINEL. 0 is that lever's declared
        DISARM in src/memory/api.py::maintain, so an operator asking for a fractional cadence
        silently receives the OFF switch, with Config.given() still reporting '0.4' beside a
        mechanism running at 0. No (lo, hi) pair reaches it: 0 is inside the domain of a cadence.
    <any int lever>=1e26 ->  100000000000000004764729344   A 27-digit width accepted, and 4764729344
        larger than the number typed. float cannot represent 10**26, so the value that runs is not
        the value that was asked for, and given() reports the string that was.

WHY "8.0" IS ACCEPTED AND "0.4" IS REFUSED, which is the choice this rule makes. The rule is
LOSSLESSNESS, not notation. "8.0" is an integer written as a float and survives the conversion
exactly, so it resolves to 8; "1e3" resolves to 1000; "1_000" and " 12 " resolve as float() already
reads them. "0.4" does not survive -- 0 is not 0.4 -- and "1e26" does not survive either. The
alternative rule considered was TEXTUAL: refuse any raw containing '.' or an exponent. It was
refused for two reasons, both concrete. It would refuse "1e3" and "8.0", which denote integers
exactly and which a harness writing str(x) from a computed value produces routinely; and it would
still accept "1e26" on a 27-digit truncation, because that string is spelled like an integer to a
textual rule and is not one to the parser. A rule that refuses correct values and admits the
measured defect is the wrong rule.

HOW EXACTNESS IS TESTED. `decimal.Decimal(raw) == int(float(raw))`. Decimal parses the same grammar
float() does (whitespace, sign, underscores, exponents) and carries the exact decimal value, so the
comparison is between what was typed and what will run. Where Decimal cannot parse a string float()
accepted -- no such spelling is known -- the weaker test `float(raw) == int(float(raw))` stands in,
which still catches the truncation class and not the 2**53 class.

WHAT THIS BREAKS, AND IT IS A BEHAVIOUR CHANGE TO ALL 110 INT LEVERS. Any configuration that today
sets an int lever to a fractional or an inexact-magnitude string stops building and says so by name,
instead of running at the truncated number. Scanned across the repository on 2026-09-14 -- every
assignment site of every int lever's env name in src/, tests/, tools/, docs/ and the root scripts,
1093 sites in 78 files -- and exactly ONE is non-exact: `MEM_QUOTA=0.4`, in a comment in
src/memory/api.py describing this very defect. No script, sweep, test or recorded configuration in
this tree sets an int lever to a non-exact value, so nothing that runs today breaks. What DOES
change for a reader is that the two sweep findings above are now refusals rather than results, and
the prose that describes them as live is stale -- listed for their owners in this run's report.

WHAT TURNING IT OFF COSTS. `int(float(raw))` truncates silently again, and the MEM_REKEY_EVERY class
comes back: a fractional cadence lands on a lever's declared disarm with no warning and no record
except the string in given(). Off is the pre-2026-09-14 behaviour exactly.
"""


def _domain_ends(domain, default):
    """CHECK a `domain=` at DECLARATION time and return it as a tuple. Raises LeverError.

    No env name is available here -- __init__ runs before __set_name__, so the lever does not yet
    know its own field name, let alone its owner's prefix. `choices=` has the same constraint and
    resolves it the same way: the declaration-time message quotes the DEFAULT and the declaration,
    which is enough to find the line, and the resolution-time message quotes the generated env name.
    """
    if isinstance(default, bool) or not isinstance(default, (int, float)):
        raise LeverError(
            f"domain={domain!r} on a lever whose default is {default!r}: a domain is an ORDERING over "
            f"numbers, and a {type(default).__name__} default has none that a pair of endpoints "
            f"states. A str lever's legal set is `choices=`; a bool lever's coercion cannot fail.")
    try:
        lo, hi = domain
    except (TypeError, ValueError):
        raise LeverError(f"domain={domain!r} must be a (lo, hi) pair; either end may be None, "
                         f"meaning unbounded on that side.")
    if lo is None and hi is None:
        raise LeverError("domain=(None, None) bounds nothing. Omit the kwarg: a declaration that "
                         "says a lever has no bounds by WRITING a domain reads as a checked claim "
                         "and is not one.")
    want = float if isinstance(default, float) else int
    for end, side in ((lo, "lo"), (hi, "hi")):
        if end is None:
            continue
        if isinstance(end, bool) or not isinstance(end, (int, float)):
            raise LeverError(f"domain {side}={end!r} is not a number. Use None for unbounded.")
        # AN INT LEVER'S ENDS ARE INTS. coerce resolves an int lever to an int, so a float endpoint
        # describes a boundary no resolved value can ever sit at and reads as though fractional
        # values were in play on a lever that has none. The reverse is allowed: an int endpoint on a
        # float lever compares exactly against a float and `domain=(0, 1)` on a rate is not a
        # mistake, it is the same interval as (0.0, 1.0) with two fewer characters.
        if want is int and not isinstance(end, int):
            raise LeverError(
                f"domain {side}={end!r} is a float on an INT lever (default {default!r}). An int "
                f"lever resolves to an int, so a fractional endpoint bounds nothing that can occur "
                f"and states a range the lever does not have. Write the int you mean.")
        # A NON-FINITE ENDPOINT IS THE ONE WAY TO WRITE A DOMAIN THAT UNDOES THE RULE ABOVE IT:
        # domain=(0.0, inf) admits +inf, because inf <= inf. Unbounded is spelled None, which is a
        # sentence a reader can see; inf is the same sentence disguised as a bound. A nan endpoint is
        # worse than either -- every comparison against it is False, so the lever refuses every value
        # including its own default, and the declaration-time default check below would catch that
        # one but only by accident.
        if not _math.isfinite(end):
            raise LeverError(
                f"domain {side}={end!r} is not finite. An unbounded end is written None -- an "
                f"infinite endpoint would ADMIT the infinity that "
                f"spine/lever.py::REFUSE_NON_FINITE_FLOAT exists to refuse.")
    if lo is not None and hi is not None and lo > hi:
        raise LeverError(f"domain=({lo!r}, {hi!r}) is empty: lo is above hi, so no value is legal "
                         f"and the lever cannot resolve even at its own default.")
    if (lo is not None and not lo <= default) or (hi is not None and not default <= hi):
        raise LeverError(
            f"default {default!r} is outside its own domain {_domain_text((lo, hi))}. A default no "
            f"environment can reproduce is the one configuration this tree cannot refuse at "
            f"resolution time -- from_env never coerces it -- so it is refused at declaration.")
    return (lo, hi)


def _domain_text(domain):
    """`[0.0, 1.0]` / `[1, unbounded]`, for a message a reader has to act on."""
    lo, hi = domain
    lo_s = "unbounded" if lo is None else repr(lo)
    hi_s = "unbounded" if hi is None else repr(hi)
    return f"[{lo_s}, {hi_s}]"


def _denotes_exactly(raw, v):
    """Does `raw` denote exactly the integer `v` that int(float(raw)) produced? See REFUSE_INEXACT_INT."""
    try:
        return _decimal.Decimal(str(raw).strip()) == v
    except (ArithmeticError, ValueError, TypeError):
        return float(raw) == v


class Lever:
    """One declared knob: its default, its unit, its purpose, and -- optionally -- the set of values
    it will accept, as `choices=` (an enumeration) or `domain=` (an interval). Nothing else."""

    __slots__ = ("default", "help", "unit", "choices", "domain", "name")

    def __init__(self, default, help, unit=U.COUNT, choices=None, domain=None):
        # THE DEFAULT MUST BE A LITERAL, checked here at declaration time rather than by an AST rule that
        # can be defeated by a local alias. A computed default is how the old tree ended up with nine
        # knobs whose "default" was another knob -- MAX_DOMAINS = _i("MAX_DOMAINS", _i("FAB_NMAX", 4096))
        # reads FAB_NMAX eagerly, which also poisons the "nothing read this knob" audit.
        if not isinstance(default, (int, float, str, bool, type(None))):
            raise LeverError(f"default must be a literal, got {type(default).__name__}. "
                             f"A value derived from another lever is a WIRE, not a default -- "
                             f"declare it in spine.assemble so the coupling is visible.")
        # THE ONE ROUTE AROUND THE FLOOR, CLOSED WHERE IT OPENS. REFUSE_NON_FINITE_FLOAT lives in
        # coerce, and `from_env` does not call coerce when the environment does not name the lever --
        # it uses the declared default directly. So a literal `Lever(float("inf"), ...)` would put a
        # non-finite float into a frozen Config having passed no rule at all, and the four package
        # loops that scan for one (fabric, sig, opt, tok) would then be the only readers standing.
        # Measured across the live registry on 2026-09-14: 0 of the 97 float levers declares a
        # non-finite default, so this refuses nothing that exists. It is the same rule as the floor,
        # stated at the other door, and it answers to the same switch.
        if (REFUSE_NON_FINITE_FLOAT and isinstance(default, float)
                and not _math.isfinite(default)):
            raise LeverError(
                f"default {default!r} is not finite. A default is the one value from_env never "
                f"coerces, so spine/lever.py::REFUSE_NON_FINITE_FLOAT cannot see it at resolution "
                f"time and it would reach a frozen Config unexamined.")
        if choices is not None and default not in choices:
            raise LeverError(f"default {default!r} is not among choices {choices!r}")
        # `domain=(lo, hi)` -- THE INTERVAL FORM, BUILT IN THE SHAPE `choices=` ALREADY HAS: an
        # optional kwarg, checked HERE against the lever's own default, checked again in coerce AFTER
        # coercion, refusing with a LeverError that names the generated env name and the value. The
        # two compose rather than compete -- `choices=` enumerates, `domain=` bounds -- and a
        # declaration carrying both must satisfy both, which is checked below so that a choice
        # outside the domain cannot ship as an option nobody can select.
        #
        # EITHER END MAY BE None, MEANING UNBOUNDED ON THAT SIDE, AND hi=None IS THE COMMON CASE, NOT
        # A CONVENIENCE. Counted over the 207 numeric levers in this tree: the HIGH end is obvious
        # from the declaration on 44, is another lever or a wire on 15 (LM_CTX <= d_pos_max,
        # WORLD_N0 <= WORLD_NMAX, MEM_KEY_DEPTH <= LM_LAYERS -- none expressible as a per-lever
        # pair), is a policy this tree has explicitly declined to set on 16 (CAP_LIFT, SIG_TEMP,
        # EVAL_GEN_TEMP, the four EMA rates), and IS NOT DERIVABLE AT ALL on 131 -- the harmful value
        # is a floating-point dynamic-range or memory property of the mechanism, not of the
        # declaration. Honestly populated, 163 of the 207 get no ceiling.
        #
        # SO READ THIS, AND DO NOT READ A DOMAIN AS A STATEMENT THAT THE LEVER IS HARMLESS AT EVERY
        # VALUE IT ADMITS -- NOTHING IN THIS FILE STATES THAT. hi=None ADMITS +inf. Measured on a
        # real numeric lever -- domain=(0.0, 1.0) refuses nan, inf, -inf and 1e26; domain=(0.0, None)
        # refuses nan and -inf and PASSES inf and 1e26. ANY finite endpoint refuses nan for free (see
        # the comparison form in coerce); only a finite HIGH end refuses +inf. That is why
        # REFUSE_NON_FINITE_FLOAT above exists and why the two are COMPLEMENTS AND NOT ALTERNATIVES:
        # `domain=` alone would leave +inf legal on the 53 open-topped float levers, which include
        # OPT_LR, OPT_WEIGHT_DECAY, SIG_VAR_WEIGHT, SIG_COV_WEIGHT and FAB_ROUTE_T -- five of the
        # sweep's own critical findings. Neither rule is a subset of the other.
        #
        # THE INTERVAL IS CLOSED AT BOTH ENDS, and that is a decision, justified from the 33 levers
        # whose two ends are obvious today (.rework/audits/options_domain.json, option-(3) finding).
        # Read what is in that list: probabilities (LM_DROPOUT, TOK_DROPOUT, MEM_WRITE_GATE,
        # FAB_MUT_BIG_P), shares and quantiles (FAB_CULL_FRAC, DOM_RADIUS_Q, MEM_PROBATION_FRAC,
        # DATA_HOLDOUT_FRAC), and three already refused at both ends by hand in src/opt/api.py::build
        # (OPT_LR_DECAY, OPT_LR_MIN_FRAC, OPT_LR_RESTART_DAMP). On that population BOTH endpoints are
        # legal values somebody configures: 0.0 is "never" on a probability and is a declared or
        # measured-legitimate value on 46 of the 207; 1.0 is "always", and src/opt/api.py::build
        # already accepts OPT_LR_DECAY=1.0 BY NAME. An exclusive end would REFUSE a value a shipped
        # body accepts, which is the one direction of error that breaks a configuration that works.
        # The two levers whose natural low end is NEGATIVE make the same point from the other side:
        # EVAL_GENUINE_SIL is a silhouette in [-1, 1] and MEM_MATCH_FLOOR is a cosine similarity, and
        # both endpoints are attainable readings.
        #
        # WHAT A DECLARATION NEEDING AN OPEN END DOES INSTEAD, because three exist and are measured
        # in one function: src/opt/api.py::build refuses `lr <= 0.0` (open low), `not 0.0 <=
        # min_frac < 1.0` (half-open) and `not 0.0 <= decay <= 1.0` (closed), and
        # src/lm/api.py::resolve needs the half-open one again for LM_DROPOUT. It writes the CLOSED
        # pair that
        # CONTAINS its interval -- domain=(0.0, 1.0) for the half-open [0.0, 1.0) -- and keeps the
        # strict clause at the read site. The declaration then under-refuses by exactly one endpoint
        # and the body refuses that endpoint by name, holding the mechanism, in a message that can
        # say why. It never over-refuses, which is the property that matters: a domain is the
        # OUTERMOST interval the declaration alone can defend, not the tightest one the mechanism
        # has. Nothing written that way blocks a later inclusivity field -- adding one would narrow
        # what a declaration can say, and every closed pair written today would still mean what it
        # says -- but a strict end is NOT expressible today and must not be faked by nudging an
        # endpoint, because "greater than 0.0" and "at least 5e-324" are not the same sentence and
        # only the mechanism knows which one it meant.
        if domain is not None:
            domain = _domain_ends(domain, default)
            if choices is not None:
                _out = [c for c in choices
                        if (domain[0] is not None and not domain[0] <= c)
                        or (domain[1] is not None and not c <= domain[1])]
                if _out:
                    raise LeverError(
                        f"choices {_out!r} fall outside domain {_domain_text(domain)} on the same "
                        f"declaration. A choice no value can reach is an option offered and refused.")
        self.default, self.help, self.unit = default, help, unit
        self.choices, self.domain = choices, domain
        self.name = None                                     # filled in by __set_name__

    def __set_name__(self, owner, name):
        # THE FIELD NAME IS THE ONLY THING THE DECLARATION LEARNS ABOUT ITS OWNER. The prefix is NOT
        # recorded here, and the reason is a defect two independent reviewers reproduced in the first
        # version: __init_subclass__ wrote `v.prefix = cls.PREFIX` onto the Lever OBJECT, so a Lever
        # reachable from two classes ended up with whichever prefix was defined last --
        #     class Base(LeverSet):  PREFIX="BASE"; x = Lever(1, ...)
        #     Base.env_names()                      -> {'BASE_X'}
        #     class Child(Base):     PREFIX="CHILD"; y = Lever(2, ...)
        #     Base.env_names()                      -> {'CHILD_X'}      <-- silently retargeted
        # A base class's lever answering to a subclass's environment name defeats the entire ownership
        # guarantee, and every static check still passed. Ownership is now read from the OWNER at use
        # time, so there is no per-object state to corrupt.
        # NOTE ON WHAT THE CALLER SEES: Python wraps any exception from __set_name__ in a RuntimeError
        # ("Error calling __set_name__ on 'Lever' instance 'd_capacity' in 'Bad'"), with this LeverError
        # as its __cause__. The refusal is still loud and still names the field; a caller catching this
        # must catch RuntimeError, or read .__cause__.
        if name.startswith("d_"):
            raise LeverError(
                f"{name!r} cannot be a lever: the d_ namespace belongs to WIRES. A d_ field is a value "
                f"another package owns, arriving through spine.assemble -- declaring one as a lever "
                f"silently shadows the wire that writes it.")
        # THE SECOND TAKEN NAMESPACE: Config's own methods. `Config.__getattr__` runs only when ordinary
        # attribute lookup FAILS, so a lever named `keys` or `given` is never what `cfg.keys` returns --
        # the bound method is, and the lever becomes unreadable while every static check still reports it
        # declared, owned and resolved. That is the same silent-shadow the d_ rule above exists to stop,
        # from the other side. It was a latent hole and adding `Config.owned_by` widened it into a live
        # one: a package asserting ownership through a name one of its own levers had shadowed would be
        # asserting nothing at all, and the assertion is the only thing standing at the read site. Read
        # off Config itself rather than a hand-typed list, because a hand-typed list of method names is
        # a second declaration of the interface and it drifts the first time a method is added.
        if name in _config_attrs():
            raise LeverError(
                f"{name!r} cannot be a lever: Config already answers to that name as a method, so "
                f"`cfg.{name}` would return the method and never this lever. Taken: "
                f"{sorted(_config_attrs())}.")
        self.name = name

    def env_name_for(self, prefix):
        """The environment name this lever answers to WHEN OWNED BY `prefix`. Never cached on self."""
        return f"{prefix}_{self.name.upper()}"

    # -- immutable once declared -----------------------------------------------------------------
    # Config.lever() used to hand out this object live, so `cfg.lever('n').default = 99` rewrote the one
    # declared default for every later from_env() in the process -- reproduced. L1 says one literal
    # default and no second default anywhere; a mutable declaration makes that a statement about source
    # text only.
    def __setattr__(self, k, v):
        if getattr(self, "name", None) is not None:
            raise LeverError(f"{self.name!r} is declared; a lever's default cannot be rewritten at runtime")
        object.__setattr__(self, k, v)

    def coerce(self, raw, prefix):
        """Turn an environment string into the declared type, or fail by its OWNED name.

        FOUR REFUSALS, IN THE ORDER THE VALUE PASSES THEM, and every one of them raises LeverError
        naming the GENERATED env name and the value, at the first read, before anything is derived:
          1. it is not the declared type at all                       (this has always been here)
          2. it is a non-finite float          REFUSE_NON_FINITE_FLOAT   -- 97 float levers
          3. it is not the integer it denotes  REFUSE_INEXACT_INT        -- 110 int levers
          4. it is outside `choices=` or outside `domain=`              -- per declaration
        Nothing here is reached by a lever the environment did not name: from_env uses the declared
        default directly when the name is absent, and the default is checked against `choices=` and
        `domain=` at DECLARATION time, where a default no environment can reproduce is impossible to
        ship rather than merely unlikely.
        """
        d = self.default
        try:
            if isinstance(d, bool):     v = str(raw).strip().lower() not in ("0", "", "off", "no", "none", "false")
            elif isinstance(d, int):    v = int(float(raw))
            elif isinstance(d, float):  v = float(raw)
            else:                       v = str(raw)
        # OverflowError IS IN THIS TUPLE BECAUSE int(float('inf')) RAISES IT AND NOTHING ELSE DOES.
        # The `int(float(raw))` branch above resolves every int lever, and at 'inf' or '-inf' it raised an
        # uncaught OverflowError -- a bare "cannot convert float infinity to integer" naming no lever,
        # no value and no package -- while the SAME line at 'nan' raises ValueError, is caught here, and
        # produces the correct refusal. 110 int levers x 2 values = 220 cells tree-wide read as a
        # traceback instead of a refusal, and the 2026-09-05 lever-domain sweep found it as the largest
        # REFUSED_BADLY block in all six of its per-package reports. This carries NO policy: it makes
        # inf AGREE WITH nan rather than deciding anything new about either.
        except (TypeError, ValueError, OverflowError):
            raise LeverError(f"{self.env_name_for(prefix)}={raw!r} is not a {type(d).__name__}")
        # THE TWO PARSE-LEVEL RULES. `isinstance(d, bool)` is tested FIRST and skipped deliberately:
        # bool is a subclass of int, so a FLAG would otherwise be tested for integrality, and the
        # bool branch above cannot fail anyway -- every string is a legal spelling of on or off.
        if isinstance(d, bool):
            pass
        elif isinstance(d, int):
            if REFUSE_INEXACT_INT and not _denotes_exactly(raw, v):
                raise LeverError(
                    f"{self.env_name_for(prefix)}={raw!r} does not denote the integer it resolves "
                    f"to ({v!r}). An int lever is read as int(float(raw)), which truncates toward "
                    f"zero and cannot represent every integer above 2**53, so this value would run "
                    f"as {v!r} while Config.given() reported {raw!r} beside it -- and where a "
                    f"lever's 0 is a declared disarm, a fraction truncating to 0 turns a request "
                    f"for the tightest setting into the OFF switch. An integer written as a float "
                    f"('8.0', '1e3') resolves normally. To resolve this one anyway, set "
                    f"spine/lever.py::REFUSE_INEXACT_INT = False and read what that costs, there.")
        elif isinstance(d, float):
            if REFUSE_NON_FINITE_FLOAT and not _math.isfinite(v):
                raise LeverError(
                    f"{self.env_name_for(prefix)}={raw!r} is not finite (it reads as {v!r}). A "
                    f"non-finite float raises nowhere downstream -- it propagates through every "
                    f"arithmetic this tree performs and arrives in a report as a plausible number, "
                    f"or crosses a package boundary as a wire with no warning -- so it is refused "
                    f"at the first read instead. This refusal is about the SPELLING and makes no "
                    f"claim about any other value of this lever. To resolve it anyway, set "
                    f"spine/lever.py::REFUSE_NON_FINITE_FLOAT = False and read what that costs, "
                    f"there.")
        if self.choices is not None and v not in self.choices:
            raise LeverError(f"{self.env_name_for(prefix)}={v!r} must be one of {sorted(self.choices)}")
        if self.domain is not None:
            lo, hi = self.domain
            # THE INVERTED-CHAIN FORM IS LOAD-BEARING AND IS NOT A STYLE CHOICE. Written `v < lo or
            # v > hi`, every comparison against nan is False and a nan would PASS a domain it is
            # plainly outside; written `not lo <= v`, the same comparison is False and `not` makes it
            # a refusal. This is why any finite endpoint refuses nan for free, and it is the
            # grammar the opt sweep found separating the guards that held against NaN from the ones
            # that did not -- there, by accident, thirteen times. Here, on purpose, once.
            if (lo is not None and not lo <= v) or (hi is not None and not v <= hi):
                raise LeverError(
                    f"{self.env_name_for(prefix)}={v!r} is outside its declared domain "
                    f"{_domain_text(self.domain)} -- BOTH ENDS INCLUSIVE, and an end reading "
                    f"'unbounded' states no bound at all on that side.")
        return v


# --------------------------------------------------------------------------------------------------
# The assembly latch
# --------------------------------------------------------------------------------------------------
# One process-wide flag. It is module state rather than a parameter because the thing it must survive is
# an ARBITRARY call path: the point is to refuse a from_env that arrives through a walk nobody wrote
# down, and a parameter only constrains callers who agree to pass it.
#
# Not a security boundary and not described as one. A module that can reach LeverSet can reach
# _reopen_assembly() too. What it buys is that the ACCIDENTAL and the CASUAL forms -- an implementation
# agent who needs a number and finds from_env, a helper that re-resolves "just to be safe" -- become a
# raise at the call site instead of a second answer that agrees with the first until the day it does not.

_ASSEMBLY_CLOSED = False


def _close_assembly():
    """Called by spine.assemble.build() as its last act. Idempotent."""
    global _ASSEMBLY_CLOSED
    _ASSEMBLY_CLOSED = True


def _reopen_assembly():
    """For tests that build more than once in a process. Name it in the test, and say why."""
    global _ASSEMBLY_CLOSED
    _ASSEMBLY_CLOSED = False


def assembly_closed():
    return _ASSEMBLY_CLOSED


class LeverSet:
    """One package's levers. Subclass, set PREFIX, declare Levers as class attributes."""

    PREFIX = None

    def __init_subclass__(cls, **kw):
        super().__init_subclass__(**kw)
        if not cls.PREFIX or not cls.PREFIX.isupper():
            raise LeverError(f"{cls.__name__} needs an UPPERCASE PREFIX")
        levers = {}
        for base in reversed(cls.__mro__):
            for k, v in vars(base).items():
                if isinstance(v, Lever):
                    levers[k] = v                      # recorded, never written to
        cls._levers = levers
        from .registry import register
        register(cls)

    # -- resolution ------------------------------------------------------------------------------
    @classmethod
    def from_env(cls, environ=None):
        """THE ONLY PLACE IN THE TREE THAT MAY NAME os.environ. Enforced by tests/test_ownership.py.

        AND IT REFUSES TO RUN ONCE THE ASSEMBLY IS CLOSED, which is the only part of this that a
        spelling cannot walk past. Every static defence against a package minting a foreign Config
        matches a NAME -- O8 matched `from_env`, O10 matches an import -- and a reviewer demonstrated
        the walk that needs neither:

            from spine.lever import Config, LeverSet     # the one import PLAN mandates for every package
            for sib in LeverSet.__subclasses__():        # Python keeps this list; no registry needed
                out[sib.PREFIX] = getattr(sib, "from_" + "env")()

        Thirteen packages, every env-overridden value, all ten ownership checks green. It is worse than
        that: `Config.__slots__` exposes `_owner`, so a package's OWN Config -- the one the composition
        root is obliged to hand it -- walks `cfg._owner.__mro__` to this class with no import at all.

        The latch closes the RESOLUTION half of that at runtime, whatever spelling reached it.
        `spine.assemble.build()` calls this thirteen times and then sets the latch as its last act, so
        nothing legal breaks and every mint after startup is a loud failure at the moment it happens
        rather than a plausible number in a report.

        WHAT IT DOES NOT CLOSE, said here rather than left for the next reviewer to find: the
        DECLARATION half. `sib._levers["alpha"].default` reads a foreign lever with no from_env call and
        no Config at all, so editing FAB's literal changes MEM's behaviour and affects() cannot see it.
        Nothing static or runtime in this file reaches that -- only L3, the behavioural isolation sweep
        in tests/test_lever_isolation.py against the tests/test_determinism.py noise floor, and it does
        not exist yet. Do not read this latch as "there is no other route"; that sentence is the reason
        a reviewer stops looking, and this module has already had to be corrected for writing it once.
        """
        if _ASSEMBLY_CLOSED:
            raise LeverError(
                f"{cls.__name__}.from_env() after the assembly closed. build() resolves every package "
                f"exactly once and then latches this; a mint at this point is a SECOND source for a "
                f"value the frozen Config already holds, and whichever of the two the report quotes is "
                f"a coin flip. If this is legitimate startup work, do it before build() returns. If it "
                f"is a test, call spine.lever._reopen_assembly() and say in the test why.")
        env = os.environ if environ is None else environ
        vals, given = {}, {}
        for k, lv in cls._levers.items():
            raw = env.get(lv.env_name_for(cls.PREFIX))
            if raw is None:
                vals[k] = lv.default
            else:
                vals[k] = lv.coerce(raw, cls.PREFIX)
                given[k] = raw
        return Config(cls, vals, given)

    @classmethod
    def env_names(cls):
        return {lv.env_name_for(cls.PREFIX) for lv in cls._levers.values()}


class Config:
    """Resolved, frozen values for one package: its own levers, plus `d_` values wired in from others.

    Attribute access is the whole interface. Reading a name that was never declared raises with the list
    of what IS available, rather than returning a default nobody wrote down.

    WHAT THAT REFUSAL IS ABOUT, AND WHAT IT IS NOT. It is about the NAME: this object refuses to answer to
    a name its owner never declared. It is not about the HOLDER. A Config does not know which package is
    reading it, `build()` hands the whole `{PREFIX: Config}` map to whoever calls it, and passing
    `configs["FAB"]` into a memory function as an ordinary parameter gives that function every FAB lever
    with no error at author time and none at run time -- reproduced:
        def memory_prune(cfg): return cfg.slots        # memory_prune(configs["FAB"]) -> 2048
    The docstrings here and in spine/assemble.py used to say this was impossible ("an author-time
    NameError"); they were wrong, and that sentence is the reason a reviewer stops looking. `owned_by`
    below is the check the read site was missing, and the module header lists what actually is structural.
    """

    __slots__ = ("_owner", "_vals", "_given", "_wired", "_frozen")

    def __init__(self, owner, vals, given):
        object.__setattr__(self, "_owner", owner)
        object.__setattr__(self, "_vals", dict(vals))
        object.__setattr__(self, "_given", dict(given))
        object.__setattr__(self, "_wired", {})
        object.__setattr__(self, "_frozen", False)

    # -- wiring, permitted only before freeze and only through spine.assemble ---------------------
    def _wire(self, name, value):
        if self._frozen:
            raise LeverError(f"{self.prefix}: wired after freeze -- assemble runs once, at startup")
        if not name.startswith("d_"):
            raise LeverError(f"wired value {name!r} must be d_-prefixed: a value computed from more than "
                             f"one package's levers is a COUPLING, and `grep d_` must find it")
        # BOTH ENDS OF THE COLLISION. Lever.__set_name__ refuses a d_-named lever; this refuses a wire
        # landing on a name a lever already holds. Without the pair, __getattr__ resolves _vals before
        # _wired and the LEVER silently wins -- reproduced: a wire wrote 200000, the reader saw 999.
        if name in self._vals:
            raise LeverError(f"wire {name!r} collides with a declared lever of the same name on "
                             f"{self._owner.__name__}; the reader would silently get the lever")
        self._wired[name] = value

    def _freeze(self):
        # A FLAG IS NOT A STATE. The first version set _frozen and only _wire consulted it, so
        # `cfg._vals['slots'] = 8` walked straight past the refusal and changed what cfg.slots returned
        # -- reproduced. Frozen now means the mappings themselves cannot be written.
        import types
        object.__setattr__(self, "_vals", types.MappingProxyType(dict(self._vals)))
        object.__setattr__(self, "_wired", types.MappingProxyType(dict(self._wired)))
        object.__setattr__(self, "_frozen", True)
        return self

    # -- reading ---------------------------------------------------------------------------------
    def __getattr__(self, k):
        if k.startswith("_"):
            raise AttributeError(k)
        v = self._vals.get(k, self._wired.get(k, _MISSING))
        if v is _MISSING:
            raise LeverError(
                f"{self._owner.__name__} has no lever {k!r}. Declared: {sorted(self._vals)}"
                + (f"; wired: {sorted(self._wired)}" if self._wired else "")
                + ". If this belongs to another package, it must arrive as a wire, not a read.")
        return v

    def __setattr__(self, k, v):
        raise LeverError(f"{self._owner.__name__} is frozen; levers are resolved once at startup")

    # -- the owner check, at the point of use -----------------------------------------------------
    def owned_by(self, prefix):
        """Refuse to be read as some other package's Config. Returns self, so it composes.

            def memory_prune(mem):
                mem = mem.owned_by("MEM")           # or as a bare statement, at the head of the function
                ...

        WHY THIS EXISTS: it is the only owner check that happens where the read happens. Every other
        mechanism in this spine acts at DECLARATION time -- one owner per prefix, one env name per lever,
        one file that may name os.environ, one file that may call from_env. All of that stops a module
        MINTING a foreign Config. None of it stops a caller HANDING one over, because a Config is an
        ordinary object and Python does not type it by package. The gap was verified, not theorised:
        `memory_prune(configs["FAB"])` returned FAB_SLOTS and nothing anywhere said a word.

        AN ASSERTION, NOT A CAPABILITY, and the difference is the whole honest statement of what this
        buys. A function that never calls it is exactly as exposed as it was before this method existed;
        adding the method to the class protects nothing by itself. That is why tests/test_ownership.py's
        O9 requires the call of any function that annotates a parameter as a Config, and why the prefix
        must be a string literal there: a computed prefix is invisible to that check, and an assertion no
        static pass can read is a comment with parentheses.

        WHAT IT STILL CANNOT SEE: a function that takes an UNANNOTATED parameter and never asserts. O9
        cannot require an assertion it has no way to know is needed, so that case is only reachable by
        L3 -- flip a lever, run the seeded steps, and see whose fingerprint moves.
        """
        if prefix != self.prefix:
            raise LeverError(
                f"this is {self.prefix}'s Config and the caller declared {prefix!r}. A package reads its "
                f"OWN levers; a value from another package must arrive as a d_ wire declared in "
                f"spine.assemble, so that affects() -- the only oracle the L3 isolation sweep has -- can "
                f"see the coupling. Available here: {sorted(self._vals)}.")
        return self

    # -- introspection, used by the report and by docs generation ---------------------------------
    @property
    def prefix(self): return self._owner.PREFIX
    def keys(self): return list(self._vals) + list(self._wired)
    def given(self): return dict(self._given)        # what the environment actually supplied
    def wired(self): return dict(self._wired)
    def lever(self, k):
        """A READ-ONLY VIEW of a declaration. Never the declaration itself: handing that out let a caller
        rewrite the one declared default for the whole process."""
        lv = self._owner._levers[k]
        return LeverView(k, lv.default, lv.help, lv.unit, lv.choices, lv.env_name_for(self.prefix),
                         lv.domain)

    def __repr__(self):
        return f"<Config {self.prefix} {len(self._vals)} levers, {len(self._wired)} wired>"


# `domain` IS APPENDED, NOT INSERTED, and the position is the whole point: a namedtuple is also a
# tuple, so every existing reader -- `fab.lever(f).env_name` in five package bodies, and any unpack
# written later -- keeps the field it was reading at the index it was reading. The field is the pair
# as declared, or None, which is the same shape `choices` already has.
LeverView = _nt("LeverView", "name default help unit choices env_name domain")


def _config_attrs():
    """The names Config already answers to, so a lever cannot be declared under one of them.

    Computed from the class, not listed by hand, and computed on each call rather than cached at import:
    the cost is a `dir()` per lever declaration -- a few hundred at startup, once -- and what it buys is
    that a method added to Config later is covered without anybody remembering to add it here. A cached
    frozenset built at import would be identical today and stale the day it mattered.
    """
    return frozenset(n for n in dir(Config) if not n.startswith("_"))


class _Missing:
    def __repr__(self): return "<missing>"


_MISSING = _Missing()
