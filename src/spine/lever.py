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
import os
from collections import namedtuple as _nt

from . import units as U


class LeverError(Exception):
    """A declaration or resolution problem. Always fatal, always at startup, never mid-run."""


class Lever:
    """One declared knob. Carries its default, its unit, its purpose, and nothing else."""

    __slots__ = ("default", "help", "unit", "choices", "name")

    def __init__(self, default, help, unit=U.COUNT, choices=None):
        # THE DEFAULT MUST BE A LITERAL, checked here at declaration time rather than by an AST rule that
        # can be defeated by a local alias. A computed default is how the old tree ended up with nine
        # knobs whose "default" was another knob -- MAX_DOMAINS = _i("MAX_DOMAINS", _i("FAB_NMAX", 4096))
        # reads FAB_NMAX eagerly, which also poisons the "nothing read this knob" audit.
        if not isinstance(default, (int, float, str, bool, type(None))):
            raise LeverError(f"default must be a literal, got {type(default).__name__}. "
                             f"A value derived from another lever is a WIRE, not a default -- "
                             f"declare it in spine.assemble so the coupling is visible.")
        if choices is not None and default not in choices:
            raise LeverError(f"default {default!r} is not among choices {choices!r}")
        self.default, self.help, self.unit, self.choices = default, help, unit, choices
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
        """Turn an environment string into the declared type, or fail by its OWNED name."""
        d = self.default
        try:
            if isinstance(d, bool):     v = str(raw).strip().lower() not in ("0", "", "off", "no", "none", "false")
            elif isinstance(d, int):    v = int(float(raw))
            elif isinstance(d, float):  v = float(raw)
            else:                       v = str(raw)
        except (TypeError, ValueError):
            raise LeverError(f"{self.env_name_for(prefix)}={raw!r} is not a {type(d).__name__}")
        if self.choices is not None and v not in self.choices:
            raise LeverError(f"{self.env_name_for(prefix)}={v!r} must be one of {sorted(self.choices)}")
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
        return LeverView(k, lv.default, lv.help, lv.unit, lv.choices, lv.env_name_for(self.prefix))

    def __repr__(self):
        return f"<Config {self.prefix} {len(self._vals)} levers, {len(self._wired)} wired>"


LeverView = _nt("LeverView", "name default help unit choices env_name")


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
