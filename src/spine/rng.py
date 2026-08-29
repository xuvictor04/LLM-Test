"""Per-subsystem randomness, handed out explicitly, plus a guard that lets a diagnostic look without touching.

WHY THIS MODULE EXISTS, AND WHY IT IS IN THE SPINE RATHER THAN IN A UTILITY DRAWER.

`tests/test_lever_isolation.py` (plan section 4, rule L3) is the load-bearing check of the whole lever
discipline: flip one lever, run 200 seeded CPU steps, and assert that no package outside that lever's
COMPUTED `affects()` set (spine/wire.py, graft G1) moved. L1 and L2 are AST rules -- they prove a module
cannot NAME a foreign lever. L3 is the only rule that can see a coupling through shared state, through the
data, or THROUGH RNG DRAW ORDER.

That last one is the reason this file is shaped the way it is. If every subsystem draws from one global
stream, then the stream is shared mutable state and draw order is a channel between packages that no
declaration mentions. Change a lever that makes the tokenizer take 3 extra draws per window and every
later draw in the fabric, the memory and the stream sampler shifts by three positions. The fabric's
fingerprint moves. The sweep reports the tokenizer as reaching the fabric, and it is not a lever coupling
at all -- it is an artifact of a shared generator. The sweep then has to be either believed (and a false
coupling gets "declared" into the ledger, permanently widening the oracle and hiding the next real leak)
or disbelieved (and the one behavioural check in the system is now advisory). Per-subsystem streams are
what make the sweep mean anything. `rng_for("fabric", seed)` advances only when the fabric draws.

THIS IS A RECORDED FAILURE CLASS HERE, NOT A HYPOTHETICAL. The old tree grew `frozen_rng` and a
`@no_rng_drift` decorator specifically because diagnostics were silently editing runs -- code below the
instrument line drew from the process-global generator and moved the training run it was measuring. Two
survey records name it: the tokenizer's merge dropout calls `random.random()`, the process-global
generator, so with TOK_DROPOUT>0 every segmentation -- INCLUDING maintenance passes that are not part of
training -- consumes global draws and shifts the run (latent only because the default is 0.0); and a
probe that ran `train('func')` then `train('surf')` off one sequentially-consumed global stream reported a
0.303 gap that mixes the objective difference with an unmatched initialisation. Both are the same defect:
one stream, many consumers, order as an invisible coupling.

WHAT THIS MODULE PROVIDES, AND THE ONE THING EACH PIECE IS FOR:

  rng_for(subsystem, seed)  one independent stream per subsystem, seeded from the PAIR, so the sweep's
                            fingerprints move only for the packages that actually drew.
  fingerprint(stream)       a cheap, process-stable integer digest of a stream's STATE. Reads, never
                            draws -- an instrument that measured the RNG by sampling from it would be the
                            exact defect above, wearing a measurement's clothes.
  frozen_rng()              save and restore the global streams around a diagnostic, AND report whether
                            the diagnostic moved them, because a guard that silently absorbs the drift
                            leaves the defect in place for the next caller who forgets the guard.

WHAT THIS MODULE DOES NOT DO. It does not seed anything by itself, it does not read os.environ (only
LeverSet.from_env may, and this file takes the run seed as an argument), and it does not import numpy or
torch. It looks them up in sys.modules at call time instead: if the process has not imported torch, there
is no global torch stream to freeze, and importing one in order to protect it would be this module
creating the state it claims to guard -- besides adding seconds to every docs-generation and census run.
"""
import contextlib
import hashlib
import random
import struct
import sys

__all__ = ["RngError", "Rng", "rng_for", "derive_seed", "fingerprint", "frozen_rng",
           "issued", "reset_issued", "SEED_BITS"]


class RngError(Exception):
    """A randomness declaration fault: a bad subsystem name, a duplicate stream, an unfingerprintable
    object, or a global stream that did not come back after a frozen_rng block. Always fatal, always at
    the point of the mistake -- the whole value of per-subsystem streams is lost the moment one of these
    is papered over and the run keeps going with two consumers on one generator."""


# 63 bits, not 64. The derived seed has to survive every place it lands: random.Random takes anything,
# but torch.Generator.manual_seed and every int64 column in a log or a checkpoint do not. A helper that
# raises or wraps for roughly half of all subsystem names would be a defect that presents as an
# intermittent failure at import, depending on the name.
SEED_BITS = 63

# Only these characters, and lowercase only. A subsystem name is an IDENTITY, and "Fabric" and "fabric"
# being two identities means two streams for one subsystem -- the second one's draws are attributed to
# nothing, and the sweep sees a package whose fingerprint moves for no declared reason. The name is
# rejected rather than normalised: silently lowercasing would make issued() report a name that appears
# nowhere in the source, and the report's job is to be greppable back to code.
_NAME_OK = frozenset("abcdefghijklmnopqrstuvwxyz0123456789_.")

# The separator between the run seed and the subsystem name inside the key that is hashed. It is excluded
# from _NAME_OK above for a concrete reason: if a name could contain the separator, then ("a", "b.c") and
# ("a.b", "c") would hash to the same bytes, and two different subsystems would silently share one
# stream. That is precisely the failure this module exists to remove, reintroduced through the naming.
_SEP = b"/"

# Personalisation string on every digest here. blake2b's `person` keeps these digests from colliding with
# any other blake2b use in the tree (checkpoint hashes, the memory store's key hashes) if one is ever fed
# the other's bytes by mistake.
_PERSON = b"spine-rng"

# name -> (derived seed, run seed). Diagnostic, plus the duplicate check in Rng.__init__. This is process
# state and it is deliberately NOT part of any draw: nothing here can change a number the run produces.
_ISSUED = {}


def _check_name(subsystem):
    """Validate a subsystem name, or fail saying which character is wrong."""
    if not isinstance(subsystem, str):
        raise RngError(f"subsystem must be a string, got {type(subsystem).__name__}. The name is half of "
                       f"the seed, so it has to be a stable literal, not an object whose repr can move.")
    if not subsystem:
        raise RngError("subsystem name is empty; a stream with no name cannot be attributed in the "
                       "isolation sweep's per-package fingerprints")
    bad = sorted(set(subsystem) - _NAME_OK)
    if bad:
        raise RngError(f"subsystem={subsystem!r} contains {bad}; allowed is lowercase a-z, 0-9, "
                       f"underscore and dot. Uppercase is refused rather than lowered because "
                       f"'Fabric' and 'fabric' would be two streams for one subsystem.")
    if subsystem.startswith(".") or subsystem.endswith(".") or ".." in subsystem:
        raise RngError(f"subsystem={subsystem!r}: dots separate a parent stream from a child "
                       f"('fabric.cull'), so a leading, trailing or doubled dot names no parent")
    return subsystem


def derive_seed(subsystem, seed, bits=SEED_BITS):
    """The seed for one subsystem's stream, from the run seed and the subsystem name.

    UNIT IN: subsystem = name, seed = count. UNIT OUT: count.

    NOT `seed + index`, AND NOT `hash(name)`. Both of the obvious cheap schemes are wrong here, each for
    a reason that bites this project specifically:

      `seed + index` COLLIDES ACROSS RUNS. Subsystem #1 at seed=1 gets 2, and subsystem #0 at seed=2 also
      gets 2. Plan section 3 item 8 makes two seeds a hard rule -- the record's between-seed spread
      (0.066-0.131 b/B) exceeds every architectural difference this project has ever claimed, so no
      comparison may be reported from fewer than two seeds. Under offset seeding those two "independent"
      replicates share streams pairwise, and the spread they measure is smaller than the real one. It
      also makes the mapping depend on declaration ORDER, so inserting a subsystem reseeds every
      subsystem after it and every fingerprint in the sweep moves at once.

      `hash(name)` IS NOT STABLE ACROSS PROCESSES. Python randomises str hashing per process unless
      PYTHONHASHSEED is set. The isolation sweep compares fingerprints from SEPARATE runs; with hash() in
      the seed path, every stream is differently seeded in every process and every fingerprint differs
      every time, so the sweep can only ever report "everything moved". A guard that always trips is as
      dead as one that never does.

    blake2b of the pair is stable across processes, machines and Python versions, and gives no useful
    relationship between neighbouring names or neighbouring seeds.
    """
    name = _check_name(subsystem)
    if isinstance(seed, bool) or not isinstance(seed, int):
        # bool is checked first because it IS an int in Python, and `rng_for("x", True)` silently seeding
        # from 1 is the sort of thing that only shows up as two runs that agree when they should not.
        raise RngError(f"seed must be an int, got {type(seed).__name__}. A float seed truncates silently "
                       f"and two runs at 1.0 and 1.4 would then be the same run.")
    if not (1 <= int(bits) <= 63):
        raise RngError(f"bits must be 1..63, got {bits!r}")
    h = hashlib.blake2b(digest_size=8, person=_PERSON)
    # Sign is included in the text form, so seed=-1 and seed=1 are different keys. Some harnesses use a
    # negative seed as "unset"; that must not alias onto a real run.
    h.update(str(int(seed)).encode("ascii"))
    h.update(_SEP)
    h.update(name.encode("ascii"))
    return int.from_bytes(h.digest(), "big") >> (64 - int(bits))


class Rng:
    """One subsystem's stream. Composition over a random.Random, never a subclass of it.

    NOT `class Rng(random.Random)`, for the same reason spine/units.py refuses `class Steps(int)`: the
    inherited surface is the problem. A subclass would carry `.seed()` and `.setstate()`, so any caller
    holding the fabric's stream could reseed it mid-run, and a stream reseeded halfway is a silent
    overwrite -- 29 of the survey's 475 records are that class, and it is the one that leaves no trace in
    a log. Here there is no way to reseed a live stream; you ask for a new one by name.

    `.draws` is counted for the report's three-state DID IT FIRE line (graft G4). A subsystem whose
    stream made zero draws over a whole run is a mechanism that did not fire, and that is worth printing
    beside "armed": the survey has 57 armed-but-inert records.
    """

    __slots__ = ("name", "run_seed", "seed", "_r", "_draws")

    def __init__(self, subsystem, run_seed, again=False):
        self.name = _check_name(subsystem)
        self.run_seed = int(run_seed)
        self.seed = derive_seed(self.name, self.run_seed)

        # ONE SUBSYSTEM, ONE STREAM PER RUN. Two calls for the same name and seed return two generators
        # that produce the SAME sequence, so two call sites would draw identical "random" numbers while
        # each believes it has its own stream. That reads as a correlation in the results and there is
        # nothing in a log to see it by. It is refused rather than cached, because handing back a shared
        # object would make draw order a coupling between those two call sites again, which is the thing
        # this whole module removes. A harness that legitimately rebuilds streams -- the isolation sweep
        # runs many 200-step runs inside one process -- calls reset_issued() between runs; a legitimate
        # rebuild of one stream (checkpoint restore) passes again=True and says so at the call site.
        prior = _ISSUED.get(self.name)
        if prior is not None and prior[1] == self.run_seed and not again:
            raise RngError(
                f"stream {self.name!r} was already issued for seed {self.run_seed}. A second generator "
                f"for one subsystem replays the same sequence, so both call sites draw identical values "
                f"while each thinks it has its own stream. Pass the one stream down, or call "
                f"reset_issued() if this is a new run inside the same process, or again=True if you are "
                f"deliberately rebuilding this stream (checkpoint restore).")
        _ISSUED[self.name] = (self.seed, self.run_seed)

        self._r = random.Random(self.seed)
        self._draws = 0

    # -- draws -------------------------------------------------------------------------------------
    # Every draw goes through the counter. The cost is one attribute increment per call, which is noise
    # beside the Mersenne Twister step; what it buys is that `.draws` is a fact about the run rather than
    # an estimate, so "armed but 0" in the report is not a guess.
    def random(self):
        self._draws += 1
        return self._r.random()

    def uniform(self, a, b):
        self._draws += 1
        return self._r.uniform(a, b)

    def gauss(self, mu=0.0, sigma=1.0):
        # gauss() consumes ONE OR TWO underlying draws depending on the cached second normal, which is
        # why gauss_next is part of the state fingerprint below. A digest over the 624 words alone would
        # call two genuinely different stream positions equal.
        self._draws += 1
        return self._r.gauss(mu, sigma)

    def randint(self, a, b):
        self._draws += 1
        return self._r.randint(a, b)

    def randrange(self, *a, **k):
        self._draws += 1
        return self._r.randrange(*a, **k)

    def getrandbits(self, k):
        self._draws += 1
        return self._r.getrandbits(k)

    def randbytes(self, n):
        self._draws += 1
        return self._r.randbytes(n)

    def choice(self, seq):
        self._draws += 1
        return self._r.choice(seq)

    def choices(self, population, weights=None, k=1):
        self._draws += k
        return self._r.choices(population, weights=weights, k=k)

    def sample(self, population, k):
        self._draws += k
        return self._r.sample(population, k)

    def shuffle(self, x):
        # In place, and it returns None like random.shuffle -- deliberately, because `x = rng.shuffle(x)`
        # against a helper that returned the list would work here and silently return None if anyone ever
        # swapped this for the stdlib call.
        self._draws += max(0, len(x) - 1)
        self._r.shuffle(x)

    # -- child streams -----------------------------------------------------------------------------
    def spawn(self, child):
        """A named sub-stream, e.g. fabric's stream spawning "cull".

        SEEDED FROM THE NAME PAIR, NOT FROM A DRAW OFF THE PARENT. `Rng(self.random())` is the usual way
        to do this and it is wrong for exactly the reason this module exists: the child's seed would then
        depend on HOW MANY DRAWS the parent had already made, so a lever that changes the parent's draw
        count reseeds the child, the child's fingerprint moves, and the sweep reports a coupling that is
        an artifact of draw order. Derived from (run seed, "parent.child") the child is independent of
        everything the parent did.
        """
        return Rng(f"{self.name}.{_check_name(child)}", self.run_seed)

    # -- interop with torch and numpy, still per subsystem -------------------------------------------
    def torch_generator(self, device="cpu"):
        """A torch.Generator for this subsystem, to be passed as `generator=` to torch's random ops.

        This is how a dropout mask or a weight init stays OFF the global torch stream. Without it, the
        argument in this module's docstring holds inside torch as well: one global torch generator makes
        torch draw order a coupling channel that no wire declares, and the L3 sweep cannot tell it from a
        lever leak.

        The seed is derived under a distinct sub-name rather than reusing self.seed. Reusing one integer
        for two different generator algorithms is not itself a correlation, but it puts the same number
        beside two different streams in every log, and a reader cannot then tell whether a bug swapped
        one for the other.
        """
        torch = sys.modules.get("torch")
        if torch is None:
            raise RngError("torch is not imported in this process, so there is no torch generator to "
                           "make. This module never imports it -- see the module docstring.")
        g = torch.Generator(device=device)
        g.manual_seed(derive_seed(self.name + ".torch", self.run_seed))
        return g

    def numpy_generator(self):
        """A numpy Generator for this subsystem, same argument as torch_generator.

        `default_rng`, not `RandomState`: the legacy RandomState seed must be below 2**32, so a 63-bit
        derived seed would have to be truncated to fit, and truncation is a collision the caller cannot
        see. default_rng takes the full integer.
        """
        np = sys.modules.get("numpy")
        if np is None:
            raise RngError("numpy is not imported in this process, so there is no numpy generator to "
                           "make. This module never imports it -- see the module docstring.")
        return np.random.default_rng(derive_seed(self.name + ".numpy", self.run_seed))

    # -- introspection -------------------------------------------------------------------------------
    @property
    def draws(self):
        return self._draws

    def fingerprint(self):
        return fingerprint(self)

    def getstate(self):
        """The underlying generator state. Exposed so fingerprint() and frozen_rng() have a read path
        that does not draw; there is deliberately no setstate(), for the reason given on the class."""
        return self._r.getstate()

    def __repr__(self):
        return f"<Rng {self.name} run_seed={self.run_seed} seed={self.seed} draws={self._draws}>"


def rng_for(subsystem, seed, again=False):
    """THE ENTRY POINT. One independent stream for one named subsystem of one seeded run.

    Handed out explicitly and passed down as an argument, never fetched from a module global. That is the
    same discipline as the lever spine -- and it has the same limit, which is written here because the
    lever spine's docstrings once claimed otherwise and a reviewer caught it. What the discipline stops is
    a subsystem REACHING for randomness it was not given: there is no module global to fetch, so a stream
    has to be handed over on purpose. What it does not stop is a stream being handed to the WRONG
    subsystem. An Rng is an ordinary object, it does not check who is drawing from it, and no author-time
    error occurs. `issued()` is where that shows up, after the fact and by name: a subsystem drawing on a
    stream named for another leaves its own name absent from the list entirely.
    """
    return Rng(subsystem, seed, again=again)


def issued():
    """Every stream handed out in this process: name -> (derived seed, run seed).

    Printed by the report. A subsystem that appears here with zero draws is armed-but-inert; a subsystem
    that does not appear at all never asked for randomness, which is a different statement and the report
    must be able to make both (graft G4's three states).
    """
    return dict(_ISSUED)


def reset_issued():
    """Forget which streams were handed out. For a harness running several runs in one process -- the
    isolation sweep runs 200 steps per lever flip, all in one interpreter. Clears bookkeeping only; it
    cannot affect any number a run produces, because nothing in _ISSUED is ever read by a draw."""
    _ISSUED.clear()


# === fingerprints ================================================================================

def _blob(obj, out):
    """Append a self-delimiting byte encoding of `obj` to `out`.

    SELF-DELIMITING MATTERS, which is why every variable-length piece carries its length. Concatenating
    raw fields would let two different states encode to the same bytes -- ("ab", "c") and ("a", "bc") --
    and a fingerprint that calls two different stream states equal is worse than no fingerprint, because
    the sweep reads it as "this package did not move".

    Never `hash()` and never `repr()`: hash randomises str hashing per process, and repr of a float is
    round-trippable but its shortest form has changed across Python versions. Both would make the same
    state fingerprint differently in two processes, and the sweep compares across processes.
    """
    if obj is None:
        out.append(b"n")
    elif isinstance(obj, bool):
        out.append(b"B\x01" if obj else b"B\x00")
    elif isinstance(obj, int):
        b = obj.to_bytes((obj.bit_length() // 8) + 2, "big", signed=True)
        out.append(b"i" + len(b).to_bytes(2, "big") + b)
    elif isinstance(obj, float):
        # Fixed 8-byte IEEE754, so the encoding does not depend on repr's formatting rules.
        out.append(b"f" + struct.pack("<d", obj))
    elif isinstance(obj, str):
        b = obj.encode("utf-8")
        out.append(b"s" + len(b).to_bytes(8, "big") + b)
    elif isinstance(obj, (bytes, bytearray, memoryview)):
        b = bytes(obj)
        out.append(b"b" + len(b).to_bytes(8, "big") + b)
    elif isinstance(obj, (tuple, list)):
        out.append(b"(" + len(obj).to_bytes(8, "big"))
        for x in obj:
            _blob(x, out)
        out.append(b")")
    elif callable(getattr(obj, "tobytes", None)):
        # numpy arrays arrive here (the legacy MT19937 state is a uint32 ndarray of 624 words).
        b = obj.tobytes()
        out.append(b"a" + len(b).to_bytes(8, "big") + b)
    else:
        raise RngError(f"cannot fingerprint a {type(obj).__name__}: no encoding is declared for it. Add "
                       f"one here rather than letting it fall back to repr() -- a repr-based digest is "
                       f"not stable across Python versions and the sweep compares across processes.")


def _torch_bytes(t):
    """A torch RNG state tensor as bytes.

    THE FALLBACK IS NOT DEFENSIVE PADDING, IT IS THE PATH THIS TREE ACTUALLY TAKES. Measured in this
    environment: torch 2.13.0 imports and runs with no numpy installed, printing "Failed to initialize
    NumPy" on import, and `Tensor.numpy()` then raises. `torch.get_rng_state()` returns a uint8 tensor,
    so the list path is exact -- it is only slower.
    """
    try:
        return t.detach().cpu().numpy().tobytes()
    except Exception:
        return bytes(bytearray(int(x) & 0xFF for x in t.detach().cpu().reshape(-1).tolist()))


def _global_states():
    """(label, state) for every GLOBAL stream this process actually has.

    Looked up in sys.modules rather than imported, and torch.cuda is touched only when CUDA is already
    initialised: `get_rng_state_all()` initialises the CUDA context as a side effect, and a function whose
    job is to observe without disturbing must not be the thing that allocates a context.
    """
    out = [("random", random.getstate())]
    np = sys.modules.get("numpy")
    if np is not None:
        # The legacy global RandomState only. A np.random.Generator that somebody holds privately is not
        # global state and is nobody's business but its owner's -- which is the whole point of handing
        # out per-subsystem streams.
        out.append(("numpy", np.random.get_state()))
    torch = sys.modules.get("torch")
    if torch is not None:
        out.append(("torch", _torch_bytes(torch.get_rng_state())))
        cuda = getattr(torch, "cuda", None)
        if cuda is not None and cuda.is_available() and cuda.is_initialized():
            out.append(("torch.cuda", tuple(_torch_bytes(s) for s in cuda.get_rng_state_all())))
    return out


def fingerprint(stream=None):
    """A process-stable 64-bit integer digest of a stream's state. Reads state; never draws.

    `stream=None` digests the GLOBAL streams this process has (python random, plus numpy and torch if
    they are imported, plus the CUDA generators if CUDA is initialised). Anything else digests just that
    stream: an Rng, a random.Random, a torch.Generator, or any object with getstate()/get_state().

    THE NO-DRAW PROPERTY IS THE POINT, not an implementation detail. The obvious way to summarise a
    generator is to take a few numbers off it, and that is precisely the recorded defect this module
    exists to remove: a diagnostic that draws from a stream moves the run it is measuring. Every path
    below goes through a getstate()-shaped call, so calling fingerprint() a thousand times leaves every
    generator exactly where it was.

    Used by tests/test_lever_isolation.py as one of the per-package integer fingerprints (graft G3), and
    by the scoped digest asserted around instrument calls (graft G7). The draw COUNT is deliberately not
    folded in: a count is not a position, and two streams that have made the same number of draws from
    different seeds are not in the same place. `Rng.draws` reports the count separately.

    THE SWEEP MUST FINGERPRINT SUBSYSTEM STREAMS, NOT `fingerprint()` WITH NO ARGUMENT. Measured here:
    across four processes at four PYTHONHASHSEED values, `fingerprint(rng_for("fabric", 7))` is the same
    64-bit integer every time, and `fingerprint()` is a different one every time -- because Python seeds
    the global `random` module from OS entropy at interpreter start, and nothing in this module reseeds
    it. A run-to-run comparison built on the no-argument form would report every package as moved on
    every flip, which is a check that cannot pass and therefore is not a check. The no-argument form is
    for comparing a BEFORE and an AFTER inside one process, which is exactly what frozen_rng uses it for.
    """
    parts = []
    if stream is None:
        for label, st in _global_states():
            parts.append(b"L" + label.encode("ascii") + b"\x00")
            _blob(st, parts)
    else:
        get = getattr(stream, "getstate", None) or getattr(stream, "get_state", None)
        if get is None:
            raise RngError(
                f"cannot fingerprint {type(stream).__name__}: it has neither getstate() nor "
                f"get_state(). Pass an Rng, a random.Random, a torch.Generator, a numpy Generator's "
                f"bit_generator, or None for the global streams.")
        st = get()
        # A torch.Generator's get_state() is a uint8 tensor; convert at the source, where the dtype is
        # known, rather than teaching _blob about tensors in general.
        if type(st).__module__.split(".")[0] == "torch":
            st = _torch_bytes(st)
        _blob(st, parts)
    h = hashlib.blake2b(b"".join(parts), digest_size=8, person=_PERSON)
    return int.from_bytes(h.digest(), "big")


# === the guard around diagnostics ================================================================

class Frozen:
    """The record a frozen_rng block yields. Read it; the block does not print.

    `covers` is here because a guard that covers nothing looks exactly like a guard that works. If numpy
    is not imported, "numpy" is not in covers, and a report that claims the diagnostic was fully guarded
    can be checked against what was actually saved instead of against the intention.
    """

    __slots__ = ("covers", "moved", "restored")

    def __init__(self, covers):
        self.covers = tuple(covers)
        self.moved = None        # did the body advance a global stream? Filled in on exit.
        self.restored = None     # did the streams come back to where they were? Filled in on exit.

    def __repr__(self):
        return f"<Frozen covers={self.covers} moved={self.moved} restored={self.restored}>"


@contextlib.contextmanager
def frozen_rng(strict=True):
    """Save the global streams, run the body, put them back -- and REPORT whether the body moved them.

    Usage is either form; the decorator form is what the old tree's `@no_rng_drift` was:

        with frozen_rng() as f: ...          # f.moved says whether the body drew
        @frozen_rng()
        def some_diagnostic(...): ...

    WHY IT REPORTS RATHER THAN ONLY REPAIRS. A save/restore alone makes the drift harmless HERE and
    leaves the defect in place: the diagnostic still draws from a shared stream, so its own numbers depend
    on how many draws happened before it, and the first caller who invokes it without the guard moves the
    training run. That is the recorded failure -- diagnostics silently editing runs is why the old tree
    grew this function at all. `moved` is the signal that a diagnostic should be taking a stream from
    rng_for() instead, and it is a fact the report can print rather than something a reader has to
    suspect. The old decorator also only ever protected the RNG: one survey record notes a memory-blended
    probe that `@no_rng_drift` guarded while it went on mutating the store's `use`, `prob` and `last`
    fields. Restoring the generator is not restoring the state; graft G7's scoped digest covers the rest,
    and this function claims only what its name says.

    RESTORE HAPPENS IN `finally`, AND THE STRICT CHECK DOES NOT MASK AN EXCEPTION. An early version that
    raised the mismatch from inside `finally` would replace a real traceback from the diagnostic with a
    complaint about the RNG, sending the author to the wrong problem. The check runs only when the body
    completed.

    WHAT IS NOT COVERED, said plainly: streams handed out by rng_for(), a privately-held
    numpy Generator or torch.Generator, and any global stream in a library this process has not imported.
    Per-subsystem streams are not global state, and freezing them is not this function's job -- a
    diagnostic that wants an unmoved subsystem stream should not have been given the live one.
    """
    saves, covers = [], []

    r_state = random.getstate()
    saves.append(lambda s=r_state: random.setstate(s))
    covers.append("random")

    np = sys.modules.get("numpy")
    if np is not None:
        np_state = np.random.get_state()
        saves.append(lambda s=np_state: np.random.set_state(s))
        covers.append("numpy")

    torch = sys.modules.get("torch")
    if torch is not None:
        t_state = torch.get_rng_state()
        saves.append(lambda s=t_state: torch.set_rng_state(s))
        covers.append("torch")
        cuda = getattr(torch, "cuda", None)
        if cuda is not None and cuda.is_available() and cuda.is_initialized():
            # Only when already initialised: see _global_states. Saving here would otherwise be the call
            # that creates the CUDA context, inside a function whose contract is to disturb nothing.
            c_state = cuda.get_rng_state_all()
            saves.append(lambda s=c_state: cuda.set_rng_state_all(s))
            covers.append("torch.cuda")

    before = fingerprint()
    rec = Frozen(covers)
    failed = False
    try:
        yield rec
    except BaseException:
        failed = True
        raise
    finally:
        # Read the drift BEFORE restoring. After the restore the answer is always "no drift" by
        # construction, and the interesting fact -- that the body drew -- would be gone.
        rec.moved = fingerprint() != before
        for undo in reversed(saves):
            undo()
        rec.restored = fingerprint() == before
        if not failed and strict and not rec.restored:
            # Reachable when a global stream is not restorable by set*state: a library swapped the
            # generator object itself, or torch initialised CUDA inside the body so there are now
            # generators that did not exist when the snapshot was taken. Silence here would mean the run
            # continues from a position nothing recorded, and every fingerprint after this point is
            # incomparable with every fingerprint before it.
            raise RngError(
                f"frozen_rng could not restore the global streams it covers {rec.covers}. Something in "
                f"the body replaced a generator rather than advancing it, or initialised a device "
                f"generator that did not exist at entry. The run's stream position is now unrecorded.")
