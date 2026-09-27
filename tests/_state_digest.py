"""THE STATE DIGEST: one blake2b per package over what a checkpoint of a System carries, taken WITHOUT
MOVING A COUNTER. A helper for the known answers that compare two runs' STATE; not itself a suite.

    python3 tests/_state_digest.py        # its own known answers (D1-D4); exit 0 = every check passed

WHY IT EXISTS (built 2026-09-27, before any edit of the register's §8 Stage 3,
docs/proposals/05_DECISIONS.md). tests/test_baseline.py holds a run to its recorded losses and integer
counters. A Stage-3 mechanism that must be bit-identical while it only READS -- the held-out probe
beside training (SR0's bit-identity), the trust book in observe mode (SR3's) -- owes more than that:
the weights, the optimizer's moments, FAB's books, MEM's rows, DOM's partition, the valve, the
vocabulary and the loop's carried state must come out equal too, and a loss curve can still agree for
a while after an optimizer moment has moved. This module says WHICH package's state differs. The
losses and the counters are the other two channels, and they are compared elsewhere.

WHAT IS HASHED. spine/loop.py::_payload(sysm) -- every package's checkpoint state through its own
entry point, plus the root's LOOP and RUN blocks -- and TOK's match table (Vocabulary.id2bytes and
Vocabulary.merges), which a checkpoint carries in the vocabulary FILE (TOK.save_vocabulary) and not in
TOK.vocab_state, added under TOK as `match_table`. One digest per top-level payload key (LM, SIG, FAB,
WORLD, MEM, DOM, CAP, OPT, DATA, TOK, LOOP, RUN), each taken over the digests of that package's own
top-level keys, so detail=True names the key (FAB.books, OPT.base, ...) under a package that moved.
  * A tensor BYTEWISE: its dtype, its shape and the raw bytes of a contiguous CPU copy, so -0.0 and
    0.0 differ and so does a NaN's payload, as they do in a bit-identity claim. Where it lives (cpu
    or cuda) is not state and is not hashed.
  * A float by its IEEE-754 bits, never by repr.
  * Mappings CANONICALLY: items sorted by their key's encoding, because an insertion order says
    nothing about the run; int and str keys are told apart (DOM's tokc and OPT's state hold int
    keys). Sets sorted. Lists and tuples in order, and told apart.
  * A dataclass field by field under its class name (TOK's Due can ride LOOP.carried); a
    spine.units Clock as its kind and count; array.array (TOK's packed tally) as its typecode and
    bytes.
  * ANY OTHER TYPE IS REFUSED BY PATH (TypeError), never folded in through repr(): a repr can carry
    an object's address, and two identical runs would then digest apart. Declare an encoding in
    _feed instead.

WHAT IS EXCLUDED, BY NAME. Always (_EXCLUDED_KEYS, _EXCLUDED_PATHS):
  * every `counters` mapping, the package ledgers. Counters have their own channel
    (tests/test_baseline.py's integer lines, with --exempt), and a read that must leave training
    untouched legitimately moves some of them (lm.encode.calls, sig.encode_calls, ...);
  * every key ending `_here`, the process twins of the lineage save counts (register
    LOW-RESUME-SAVED-COUNTERS): how often THIS process saved is not state;
  * CAP.state_written and DOM.n_state_dicts, the lineage save counts those two packages carry as
    payload fields outside a ledger (capacity/api.py::state, domains/api.py::state_dict).
  And whatever the caller names in `exclude`: dotted glob patterns (fnmatch) over the path from the
  package down, e.g. 'LOOP.eval', 'RUN.cadences.*.retention', 'OPT.reading_at', 'OPT.cycle_best',
  'DATA.focus' -- the state the Stage-3 builds add and must exclude by name when they compare.

WHY EVERY LEDGER IS HELD STILL AROUND THE CALL. _payload calls every package's state entry point, and
each of them counts the save it is called for, BEFORE copying its ledger so that a blob counts itself
(data/api.py::stream_state, lm/api.py::state_dict's _bump into the process-global _COUNTS, and the
other eight). A digest taken mid-test would therefore move the very save counters a known answer
compares, and LM's tally, being process-global, would leak into the next System built in the process.
So held_ledgers() deep-copies every `counters` dict on the System, and lm_api._COUNTS, before the call
and puts each back IN PLACE after it -- the same dict object, whatever the call raised -- and D2 below
checks that two digests leave every one of them as it was, keys and order included.

WHAT IT CANNOT SEE. State no checkpoint carries: FAB's same-window identity cache, SIG's lookahead
queue, LM's derived byte-index tables, MEM's rekey snapshot -- each rebuilt or retaken, not saved, by
its package's own ruling. And LOOP.carried is the System's mirror of loop.run's carried locals, which
loop.run's _carry writes before every save it attempts and once more at the end of every run, saving
on or off: between runs it is the last run's end, and before the first it is the resumed parent's, or
None.

MEASURED ON ITS FIRST USE (2026-09-27, at ae70638; CPU, operation only). B3's workload saving at its
end (window 314) and B3r's child (tests/test_baseline.py: saved at 170, continued) agree on every
loss, and digest_payload on their two final payloads is equal in ten packages and apart in two. DOM:
open_partition restores reservoir windows as float32 where the parent held integer tensors -- the same
values, in a representation its rekey already converts back. MEM: equal at the restore and apart by
window 314 -- 210 of 6,528 entries in other slots, 2,876 same-slot entries holding different keys, and
evictions, promotions and rekeyed entries counted differently -- because memory/api.py::maintain
retakes the rekey pass's snapshot after a resume instead of checkpointing it. So a state comparison
across a continuing resume excludes DOM.domains and MEM.rows by name, or waits for a repair. Recorded
here, not repaired: this helper's build changed no src/.
"""
import contextlib
import copy
import dataclasses
import fnmatch
import hashlib
import os
import struct
import sys
from collections.abc import Mapping

_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
if os.path.abspath(os.path.join(_ROOT, "src")) not in [os.path.abspath(p) for p in sys.path]:
    sys.path.insert(0, os.path.join(_ROOT, "src"))

import torch                                                       # noqa: E402

# A LEDGER IS A `counters` MAPPING WHEREVER IT SITS, AND A PROCESS TWIN IS A `*_here` KEY WHEREVER IT
# SITS; the two save counts below are the only ledger values a payload carries outside a ledger.
_EXCLUDED_KEYS = ("counters", "*_here")
_EXCLUDED_PATHS = ("CAP.state_written", "DOM.n_state_dicts")
_SIZE = 16
_PERSON = b"state-digest"


def _n(k):
    return int(k).to_bytes(8, "little")


def _dropped(key, path, patterns):
    """Is this mapping entry left out of the digest? `key` is str(key); `path` its dotted path."""
    if any(fnmatch.fnmatchcase(key, p) for p in _EXCLUDED_KEYS) or path in _EXCLUDED_PATHS:
        return True
    return any(fnmatch.fnmatchcase(path, p) for p in patterns)


class _Bytes:
    """A stand-in hasher that keeps what it is fed, for a key's or a set member's own encoding."""

    __slots__ = ("parts",)

    def __init__(self):
        self.parts = []

    def update(self, b):
        self.parts.append(b)

    def value(self):
        return b"".join(self.parts)


def _enc(x, path):
    """x's encoding as bytes: what _feed writes for it, with the str and int cases (almost every
    mapping key) written directly."""
    t = type(x)
    if t is str:
        s = x.encode("utf-8")
        return b"S" + _n(len(s)) + s
    if t is int:
        s = str(x).encode()
        return b"I" + _n(len(s)) + s
    b = _Bytes()
    _feed(b, x, path, ())
    return b.value()


def _tensor_raw(flat):
    """A flat contiguous CPU tensor's bytes, exactly: a uint8 VIEW reinterprets the storage and
    converts nothing. Through numpy when this process has it, else element by element
    (tests/test_determinism.py::_tensor_bytes records a torch that ran without numpy)."""
    u8 = flat.view(torch.uint8)
    try:
        return u8.numpy().tobytes()
    except (RuntimeError, TypeError):
        return bytes(u8.tolist())


def _feed(h, x, path, patterns):
    """Write x's canonical, self-delimiting encoding into h. `path` is a tuple of str, joined only to
    test an exclusion or to name a refusal."""
    t = type(x)
    if x is None:
        h.update(b"N")
    elif t is bool:
        h.update(b"B1" if x else b"B0")
    elif t is int:
        s = str(x).encode()
        h.update(b"I" + _n(len(s)) + s)
    elif t is float:
        h.update(b"F" + struct.pack("<d", x))
    elif t is str:
        s = x.encode("utf-8")
        h.update(b"S" + _n(len(s)) + s)
    elif isinstance(x, torch.Tensor):
        if x.layout != torch.strided:
            raise TypeError(f"tests/_state_digest.py: a {x.layout} tensor at {'.'.join(path)} has no "
                            f"bytewise encoding here; declare one in _feed")
        v = x.detach().to("cpu").contiguous().reshape(-1)
        dt = str(x.dtype).encode()
        sh = ",".join(str(int(d)) for d in x.shape).encode()
        raw = _tensor_raw(v)
        h.update(b"X" + _n(len(dt)) + dt + _n(len(sh)) + sh + _n(len(raw)) + raw)
    elif isinstance(x, Mapping):
        items = []
        for k, v in x.items():
            ks = str(k)
            p = path + (ks,)
            if _dropped(ks, ".".join(p), patterns):
                continue
            items.append((_enc(k, p), v, p))
        items.sort(key=lambda it: it[0])
        h.update(b"D" + _n(len(items)))
        for kb, v, p in items:
            h.update(_n(len(kb)) + kb)
            _feed(h, v, p, patterns)
    elif isinstance(x, (list, tuple)):
        tag = (b"L" if t is list else b"T" if t is tuple
               else b"t" + _n(len(t.__qualname__)) + t.__qualname__.encode())
        h.update(tag + _n(len(x)))
        # TWO FAST PATHS, CHOSEN BY CONTENT AND TAGGED APART, for the long homogeneous lists a payload
        # holds (MEM's keys, DOM's reservoirs, OPT's grad_norms): an all-float list as packed IEEE bits,
        # an all-int one as decimal text. Equal lists always take the same path.
        if x and all(type(e) is float for e in x):
            h.update(b"f" + struct.pack(f"<{len(x)}d", *x))
        elif x and all(type(e) is int for e in x):
            s = ",".join(map(str, x)).encode()
            h.update(b"i" + _n(len(s)) + s)
        else:
            for i, e in enumerate(x):
                _feed(h, e, path + (str(i),), patterns)
    elif isinstance(x, (set, frozenset)):
        members = sorted(_enc(e, path) for e in x)
        h.update(b"E" + _n(len(members)))
        for m in members:
            h.update(_n(len(m)) + m)
    elif isinstance(x, (bytes, bytearray, memoryview)):
        b = bytes(x)
        h.update(b"Y" + _n(len(b)) + b)
    elif t.__module__ == "array" and t.__name__ == "array":
        raw = x.tobytes()
        h.update(b"A" + x.typecode.encode() + _n(len(raw)) + raw)
    elif isinstance(x, int):
        # An int subclass other than bool (an IntEnum, say): its value under its class name.
        s = f"{t.__qualname__}:{int(x)}".encode()
        h.update(b"j" + _n(len(s)) + s)
    elif isinstance(x, float):
        # A float subclass (numpy.float64 is one): its bits under its class name.
        s = t.__qualname__.encode()
        h.update(b"g" + _n(len(s)) + s + struct.pack("<d", float(x)))
    elif dataclasses.is_dataclass(x) and not isinstance(x, type):
        s = t.__qualname__.encode()
        fields = dataclasses.fields(x)
        h.update(b"C" + _n(len(s)) + s + _n(len(fields)))
        for f in fields:
            fb = f.name.encode()
            h.update(_n(len(fb)) + fb)
            _feed(h, getattr(x, f.name), path + (f.name,), patterns)
    elif t.__module__ == "numpy" and hasattr(x, "dtype") and hasattr(x, "tobytes"):
        dt = str(x.dtype).encode()
        sh = ",".join(str(int(d)) for d in getattr(x, "shape", ())).encode()
        raw = x.tobytes()
        h.update(b"Z" + _n(len(dt)) + dt + _n(len(sh)) + sh + _n(len(raw)) + raw)
    else:
        from spine import units as _U
        if isinstance(x, _U.Clock):
            s = f"{t.__name__}:{int(x)}".encode()
            h.update(b"U" + _n(len(s)) + s)
            return
        raise TypeError(
            f"tests/_state_digest.py: no canonical encoding for {t.__module__}.{t.__qualname__} at "
            f"{'.'.join(path) or '<root>'}. Declare one in _feed rather than hashing a repr: a repr "
            f"can carry an address, and two identical runs would then digest apart.")


def _digest_of(x, path, patterns):
    h = hashlib.blake2b(digest_size=_SIZE, person=_PERSON)
    _feed(h, x, path, patterns)
    return h.digest()


def digest_payload(payload, *, exclude=(), detail=False):
    """{package: hex digest} over a checkpoint payload as spine/loop.py::_payload builds it (a
    loaded blob's ["payload"] too). With detail=True also {package.key: hex} one level down. Pure:
    it reads the payload and writes nothing."""
    patterns = tuple(exclude)
    out = {}
    for pkg, body in payload.items():
        top = str(pkg)
        if _dropped(top, top, patterns):
            continue
        if not isinstance(body, Mapping):
            out[top] = _digest_of(body, (top,), patterns).hex()
            continue
        parts = []
        for k, v in body.items():
            ks = str(k)
            p = (top, ks)
            if _dropped(ks, f"{top}.{ks}", patterns):
                continue
            parts.append((_enc(k, p), ks, _digest_of(v, p, patterns)))
        parts.sort(key=lambda it: it[0])
        h = hashlib.blake2b(digest_size=_SIZE, person=_PERSON)
        h.update(b"P" + _n(len(parts)))
        for kb, _ks, d in parts:
            h.update(_n(len(kb)) + kb + d)
        out[top] = h.hexdigest()
        if detail:
            for _kb, ks, d in parts:
                out[f"{top}.{ks}"] = d.hex()
    return out


def _ledgers(sysm):
    """Every `counters` dict a System member holds, and lm_api._COUNTS: [(name, dict)], each dict
    once."""
    from lm import api as lm_api
    found, seen = [], set()
    for name in type(sysm).__slots__:
        led = getattr(getattr(sysm, name, None), "counters", None)
        if isinstance(led, dict) and id(led) not in seen:
            seen.add(id(led))
            found.append((name, led))
    found.append(("lm_api._COUNTS", lm_api._COUNTS))
    return found


@contextlib.contextmanager
def held_ledgers(sysm):
    """Deep-copy every ledger _ledgers names on entry and put each back IN PLACE on exit, whatever
    the body raised. Yields the [(name, live dict, copy)] list."""
    held = [(name, led, copy.deepcopy(led)) for name, led in _ledgers(sysm)]
    try:
        yield held
    finally:
        for _name, live, was in held:
            live.clear()
            live.update(was)


def digest(sysm, *, exclude=(), detail=False):
    """{package: hex digest} of a System's checkpoint state plus TOK's match table, with every ledger
    left as it was. See the module docstring for what is hashed and what is excluded."""
    from spine import loop
    with held_ledgers(sysm):
        payload = loop._payload(sysm)
    vocab = sysm.vocab
    if vocab is not None and isinstance(payload.get("TOK"), Mapping):
        payload["TOK"] = dict(payload["TOK"], match_table={
            "id2bytes": list(vocab.id2bytes), "merges": [tuple(m) for m in vocab.merges]})
    return digest_payload(payload, exclude=exclude, detail=detail)


def differing(a, b):
    """The names whose digests differ between two digest() results, or that one of them lacks."""
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))


# ---- known answers (python3 tests/_state_digest.py; CPU, operation only) ---------------------------
if __name__ == "__main__":
    torch.set_num_threads(1)
    from spine import lever as _lever                              # noqa: E402
    from spine import rng                                          # noqa: E402
    from spine import loop                                         # noqa: E402
    from spine.compose import compose                              # noqa: E402
    from lm import api as lm_api                                   # noqa: E402

    FAILS = []
    # tests/test_continuation.py's small base (a tenth-size fabric, a few seconds per compose).
    BASE = {"DATA_STREAM_BYTES": "60000", "SIG_WARMUP": "20", "FAB_N0": "256", "FAB_SLOTS": "512"}

    def check(name, ok, detail=""):
        print(("PASS " if ok else "FAIL ") + name + (f" -- {detail}" if detail else ""))
        if not ok:
            FAILS.append(name)

    def build():
        _lever._reopen_assembly()
        rng.reset_issued()
        return compose(environ=dict(BASE))

    def ledger_copies(sysm):
        return [(name, list(led.items())) for name, led in _ledgers(sysm)]

    # D1: two identical builds, and the same three windows trained on each.
    a = build()
    da0 = digest(a)
    b = build()
    db0 = digest(b)
    check("D1 two identical builds digest equal, package by package",
          da0 == db0 and len(da0) == 12, f"{len(da0)} packages; differing {differing(da0, db0)}")
    loop.run(a, max_windows=3, progress=False)
    loop.run(b, max_windows=3, progress=False)
    da, db = digest(a, detail=True), digest(b, detail=True)
    check("D1 ... and after the same three windows trained on each",
          da == db and differing(da0, digest(a)) != [], f"differing {differing(da, db)}")

    # D2: two digests of one System are equal and leave every ledger as it was.
    before = ledger_copies(a)
    d1, d2 = digest(a), digest(a)
    after = ledger_copies(a)
    moved = [n for (n, x), (_, y) in zip(before, after) if x != y]
    check("D2 two digests of one System are equal and leave every counters dict and "
          "lm_api._COUNTS as they were, keys and order included",
          d1 == d2 and not moved and len(before) == len(after) and len(before) >= 11,
          f"{len(before)} ledger(s) held; moved {moved}; "
          f"saves counted {a.fabric.counters.get('fab.state_written', 'ABSENT')}, "
          f"{lm_api._COUNTS.get('lm.ckpt.saved', 'ABSENT')}")
    # ... AND THE HOLD IS WHAT DOES IT: inside it _payload counts its save in FAB's ledger and in
    # LM's process-global tally, and on the way out both read as they did before the call.
    with held_ledgers(a):
        loop._payload(a)
        inside = (a.fabric.counters.get("fab.state_written"), lm_api._COUNTS.get("lm.ckpt.saved"))
    outside = (a.fabric.counters.get("fab.state_written", "ABSENT"),
               lm_api._COUNTS.get("lm.ckpt.saved", "ABSENT"))
    check("D2 ... because _payload counts a save (fab.state_written and lm.ckpt.saved read 1 inside "
          "the hold) and the hold puts every ledger back (both ABSENT after it)",
          inside == (1, 1) and outside == ("ABSENT", "ABSENT"), f"inside {inside}, after {outside}")

    # D3: one trained window -- one flush, one optimizer step at batch 1 -- moves LM's and OPT's state.
    c = build()
    dc0 = digest(c, detail=True)
    rc = loop.run(c, max_windows=1, progress=False)
    dc1 = digest(c, detail=True)
    pk = [k for k in differing(dc0, dc1) if "." not in k]
    check("D3 one trained window (one flush, one optimizer step) changes LM's and OPT's digests",
          rc.opt_steps == 1 and {"LM", "OPT"} <= set(pk) and "OPT.base" in differing(dc0, dc1),
          f"{rc.opt_steps} step(s); packages moved {pk}")

    # D4: the exclusions. A planted counter moves no digest; a caller's pattern drops only its path;
    # an unknown type is refused by name.
    a.fabric.counters["fab.digest_planted"] = 7
    lm_api._COUNTS["lm.digest_planted"] = 7
    d_planted = digest(a)
    del a.fabric.counters["fab.digest_planted"]
    del lm_api._COUNTS["lm.digest_planted"]
    check("D4 a counter planted in FAB's ledger and in lm_api._COUNTS changes no digest",
          d_planted == d1, f"differing {differing(d_planted, d1)}")
    d_ex = digest(a, exclude=("LOOP.token_seen",))
    check("D4 exclude=('LOOP.token_seen',) changes LOOP's digest and no other package's",
          differing(d_ex, d1) == ["LOOP"], f"differing {differing(d_ex, d1)}")
    try:
        digest_payload({"X": {"k": [1, object()]}})
        check("D4 an unknown type is refused by path", False, "no TypeError")
    except TypeError as e:
        check("D4 an unknown type is refused by path", "X.k.1" in str(e), str(e)[:120])

    print(f"=== {len(FAILS)} failing ===")
    sys.exit(1 if FAILS else 0)
