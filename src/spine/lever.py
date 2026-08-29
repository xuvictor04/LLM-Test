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
"""
import os

from . import units as U


class LeverError(Exception):
    """A declaration or resolution problem. Always fatal, always at startup, never mid-run."""


class Lever:
    """One declared knob. Carries its default, its unit, its purpose, and nothing else."""

    __slots__ = ("default", "help", "unit", "choices", "name", "prefix")

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
        self.name = self.prefix = None                       # filled in by __set_name__/__init_subclass__

    def __set_name__(self, owner, name):
        self.name = name

    @property
    def env_name(self):
        return f"{self.prefix}_{self.name.upper()}"

    def coerce(self, raw):
        """Turn an environment string into the declared type, or fail by name."""
        d = self.default
        try:
            if isinstance(d, bool):     v = str(raw).strip().lower() not in ("0", "", "off", "no", "none", "false")
            elif isinstance(d, int):    v = int(float(raw))
            elif isinstance(d, float):  v = float(raw)
            else:                       v = str(raw)
        except (TypeError, ValueError):
            raise LeverError(f"{self.env_name}={raw!r} is not a {type(d).__name__}")
        if self.choices is not None and v not in self.choices:
            raise LeverError(f"{self.env_name}={v!r} must be one of {sorted(self.choices)}")
        return v


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
                    v.prefix = cls.PREFIX
                    levers[k] = v
        cls._levers = levers
        from .registry import register
        register(cls)

    # -- resolution ------------------------------------------------------------------------------
    @classmethod
    def from_env(cls, environ=None):
        """THE ONLY PLACE IN THE TREE THAT MAY NAME os.environ. Enforced by tests/test_ownership.py."""
        env = os.environ if environ is None else environ
        vals, given = {}, {}
        for k, lv in cls._levers.items():
            raw = env.get(lv.env_name)
            if raw is None:
                vals[k] = lv.default
            else:
                vals[k] = lv.coerce(raw)
                given[k] = raw
        return Config(cls, vals, given)

    @classmethod
    def env_names(cls):
        return {lv.env_name for lv in cls._levers.values()}


class Config:
    """Resolved, frozen values for one package: its own levers, plus `d_` values wired in from others.

    Attribute access is the whole interface. Reading a name that was never declared raises with the list
    of what IS available, rather than returning a default nobody wrote down.
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
        self._wired[name] = value

    def _freeze(self):
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

    # -- introspection, used by the report and by docs generation ---------------------------------
    @property
    def prefix(self): return self._owner.PREFIX
    def keys(self): return list(self._vals) + list(self._wired)
    def given(self): return dict(self._given)        # what the environment actually supplied
    def wired(self): return dict(self._wired)
    def lever(self, k): return self._owner._levers[k]

    def __repr__(self):
        return f"<Config {self.prefix} {len(self._vals)} levers, {len(self._wired)} wired>"


class _Missing:
    def __repr__(self): return "<missing>"


_MISSING = _Missing()
