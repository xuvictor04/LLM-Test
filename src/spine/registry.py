"""Import-time collection of every LeverSet, and the checks that a name can only mean one thing.

The old tree's registry was a literal dict a human maintained. This one is assembled from the
declarations themselves, so a lever cannot exist without an owner and two owners cannot claim one name.
"""
from .lever import LeverError

_SETS = {}          # PREFIX -> LeverSet subclass
_ENV_OWNER = {}     # ENV_NAME -> PREFIX


def register(cls):
    """Called from LeverSet.__init_subclass__. Refuses the two ways a name loses its meaning."""
    prior = _SETS.get(cls.PREFIX)
    # IDENTITY IS (module, qualname), NOT module ALONE. The first version of this compared only
    # __module__, so that re-importing a module would not trip it -- and that made the check dead for the
    # case it exists to catch, because two clashing classes declared in ONE module share a __module__.
    # A guard nothing can trip is this project's most-repeated defect and I wrote one here; the test that
    # declared a second PREFIX="FAB" in the same file is what found it.
    same_class = prior is not None and (prior.__module__, prior.__qualname__) == (cls.__module__, cls.__qualname__)
    if prior is not None and prior is not cls and not same_class:
        raise LeverError(
            f"PREFIX {cls.PREFIX!r} is claimed by both {prior.__module__}.{prior.__name__} and "
            f"{cls.__module__}.{cls.__name__}. Ownership is the namespace: one prefix, one owner.")
    _SETS[cls.PREFIX] = cls
    for lv in cls._levers.values():
        # THE OWNER SUPPLIES THE PREFIX. The Lever itself no longer carries one: a Lever reachable from
        # two classes used to end up answering to whichever prefix was declared last, silently
        # retargeting the first owner's environment name.
        env = lv.env_name_for(cls.PREFIX)
        owner = _ENV_OWNER.get(env)
        if owner is not None and owner != cls.PREFIX:
            raise LeverError(f"{env} is declared by both {owner} and {cls.PREFIX}")
        _ENV_OWNER[env] = cls.PREFIX


def all_sets():
    return dict(_SETS)


def all_env_names():
    return dict(_ENV_OWNER)


def unread_env(environ, families=None):
    """G9 -- the typo net. Environment names that LOOK like ours and match no declared lever.

    A mis-typed knob is silently the default, and this project has lost runs to exactly that: a knob
    corrected in the registry and not at the call site, an arm setting a name no code read. Reported at
    startup, by name, with the closest declared match.
    """
    known = set(_ENV_OWNER)
    fams = tuple(families or sorted({p + "_" for p in _SETS}))
    out = []
    for k in environ:
        if k in known or not k.startswith(fams):
            continue
        near = sorted(known, key=lambda n: _dist(k, n))[:3]
        out.append((k, near))
    return out


def _dist(a, b):
    """Cheap edit distance, only used to suggest a near miss in an error message."""
    if a == b: return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]
