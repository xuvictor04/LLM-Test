"""GRAFT G2 -- measure this machine's float noise floor, so the isolation sweep has a number to compare
against instead of an assumption.

WHY THIS FILE HAS TO EXIST BEFORE tests/test_lever_isolation.py, NOT BESIDE IT.

L3 (plan section 4) is the only rule in the whole lever discipline that can see a coupling through shared
state, through the data, or through RNG draw order. It works by flipping one lever, running the system,
and asserting that nothing outside that lever's COMPUTED affects() set (graft G1, spine/wire.py) moved.
"Moved" is a comparison, and a comparison needs a threshold. There are exactly three ways to get one:

  1. assume zero      -- then the first float that wobbles in the last bit is reported as a coupling, the
                         wobble gets investigated, found innocent, and the sweep is quietly downgraded to
                         advisory. A guard that cries wolf is spent.
  2. pick a tolerance -- 1e-6, because it looks small. Then a real leak smaller than the guess passes
                         forever and the sweep certifies a coupling that exists. This is the worse
                         failure of the two because it is silent, and plan section 3 item 5 already
                         rejected an acceptance gate that anchored bpb to 1e-6 for exactly this reason.
  3. MEASURE IT       -- run the same seeded workload twice on this machine, diff, and use what the diff
                         actually produced. That is this file.

The project's own record contains "machine non-determinism invalidates every commit-to-commit
comparison". That sentence is a claim with no number attached to it, and this file is what turns it into
one. Note what the number is and is not: the floor measured from N repeats is the largest difference
OBSERVED in N repeats. It is a LOWER BOUND on this machine's noise, not a ceiling. Two repeats that agree
to the bit do not prove the machine is deterministic; they prove that nothing disagreed twice.

THE TWO CHANNELS, AND WHY THE SWEEP LIVES ON THE INTEGER ONE.

  INTEGER channel -- per-subsystem fingerprints that are exact identities: a routing histogram, a
      tokenizer's id2bytes ordering, a memory table of (slot, src, key-hash), a stream's RNG state
      digest, a live-expert count. These are the fingerprints graft G3 names, and they are integers on
      purpose: an identity either matched or it did not, and no tolerance is involved. If any integer
      fingerprint disagrees between two identical seeded runs, the sweep's entire premise is void on this
      machine -- every flip would show unrelated packages moving -- so this harness REFUSES to publish a
      usable floor and names the offending keys instead of averaging over them.

  FLOAT channel -- genuinely continuous quantities: a loss, a mean activation, a bytes-per-token ratio.
      These cannot be identities; a summation order that changes with thread count changes the last bits.
      This is where a measured tolerance is the right instrument, and the only place one is permitted.

A quantity is never allowed in both channels, and a float is never allowed to reach an integer
fingerprint: digest_int() below raises on a float rather than encoding it, because a float folded into a
"integer" fingerprint reintroduces float tolerance through the back door while wearing an exactness
guarantee. That would be the wrong-measurement class (98 of 475 survey records) in its purest form.

THE FLOOR IS WRITTEN WITH THE MACHINE'S IDENTITY BESIDE IT, AND THAT IS LOAD-BEARING.

A floor measured on one machine says nothing about another. Different core count, different torch build,
different thread count -- all change the reduction order and therefore the last bits. So the record
carries platform, cpu count, thread counts and torch version, plus a digest of the subset of those fields
that actually change arithmetic, and load_floor() REFUSES a floor whose machine key does not match the
machine reading it. Without that refusal the file is worse than nothing: a floor committed from a CI box
and read on a workstation is a tolerance picked out of the air with a provenance stamp on it, which is
option 2 above dressed as option 3.

TWO MEASUREMENT MODES, BECAUSE THEY ANSWER DIFFERENT QUESTIONS.

  within_process   repeats inside one interpreter. THIS IS THE ONE THE SWEEP COMPARES AGAINST, because
                   the sweep runs its 200-step flips all in one interpreter (see spine/rng.py, which
                   provides reset_issued() for exactly that harness).
  across_process   repeats in fresh subprocesses. Catches what in-process repeats cannot: hash
                   randomisation, allocator and thread-pool state, library globals initialised once.
                   spine/rng.py records the measured fact that fingerprint() with no argument differs in
                   every process while fingerprint(rng_for("fabric", 7)) does not -- across-process is
                   how that class of difference gets seen at all.
  The gap between the two is itself the interesting number: it is the cost of comparing a run recorded
  yesterday against a run made today, which is what every commit-to-commit comparison does.

    python3 tests/test_determinism.py                  # measure both modes, write tests/_noise_floor.json
    python3 tests/test_determinism.py --check          # re-read the floor and re-verify it on this machine
    python3 tests/test_determinism.py --repeats 5      # more repeats; the floor can only go up

Exit code is 0 only when the integer channel was stable in every mode measured.

WHAT THIS MACHINE MEASURED, 2026-08-29, AND WHY A FLOOR OF ZERO IS NOT A REASON TO SKIP THE FLOOR.
Linux x86_64, python 3.11.15, torch 2.13.0+cu130, 4 cores, torch_threads 4. At a FIXED thread count the
reference workload is bit-reproducible: 20 integer fingerprints exact and all 6 float readings identical,
over 8 in-process repeats (28 pairs) and 3 fresh-subprocess repeats. Floor: abs 0.0, rel 0.0.

Change the thread count and it stops being zero. Emitting the same seeded workload at OMP_NUM_THREADS=1
against 4:

    torch.activation_bits   IDENTICAL      the matmul is bit-stable across thread counts
    torch.grad_bits         IDENTICAL      so is the backward pass
    torch.activation_mean   1.863e-09 abs, 1.878e-07 rel
    torch.loss              1.192e-07 abs, 1.267e-07 rel     <- the REDUCTION is what moves

The tensors are bit-identical and the MEANS OVER THEM ARE NOT, because the reduction is the part that is
parallelised. That is the whole case for this file in one measurement: a run at 1 thread and a run at 4
would agree on every integer identity and disagree on the loss in the seventh significant figure --
comfortably enough to be reported as a lever coupling by a sweep that assumed zero, and comfortably
below a 1e-6 tolerance picked because it looked small. It also disagrees NON-MONOTONICALLY: 2 threads
matched 4 exactly, so a floor measured at one thread count cannot be extrapolated to another. Hence
torch_threads and cpu_count in _KEY_FIELDS, and hence load_floor() refusing a floor from a machine whose
key differs -- verified: the check rejects this machine's own floor when re-read at OMP_NUM_THREADS=1.

WHERE THE REAL RUN PLUGS IN: see WORKLOADS and the P3 note above it. The mechanism packages do not exist
yet, so the workload here is synthetic -- it exercises spine.rng and spine.derive, which is what exists,
and it is shaped like the fingerprint set G3 specifies so the shape does not have to change later.
"""
import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from spine import derive                                                        # noqa: E402
from spine.rng import fingerprint, frozen_rng, reset_issued, rng_for            # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FLOOR_PATH = os.path.join(HERE, "_noise_floor.json")

# Bumped whenever the meaning of a field changes. load_floor() refuses an unknown schema outright rather
# than reading the fields it recognises: a floor half-understood is a tolerance of unknown provenance,
# and the whole point of this file is that the tolerance has a provenance.
SCHEMA = "spine-noise-floor/1"

# One fixed seed, written down, so "the same seeded run" is the same thing on every machine and in every
# session. Not time-derived and not read from the environment -- LeverSet.from_env is the only code in
# the tree allowed to name os.environ, and a noise floor measured at a seed nobody recorded cannot be
# reproduced by the person who doubts it.
DEFAULT_SEED = 20260829

# TWO IS THE MINIMUM AND IT IS ENFORCED, NOT SUGGESTED. A single run diffs against nothing; a "floor"
# from one repeat is the number zero with a filename. THREE IS THE DEFAULT because two repeats give
# exactly one pairwise comparison, and one comparison cannot distinguish a genuine floor from a single
# unlucky run. Three gives three pairs and the max over them, which is still a lower bound but a better
# informed one. The cost is one extra workload run.
MIN_REPEATS = 2
DEFAULT_REPEATS = 3


class DeterminismError(Exception):
    """A fault in the determinism harness itself or in what it was handed: too few repeats, a workload
    whose key set changed between runs, a float smuggled into an integer fingerprint, a floor from
    another machine. Always fatal. Every one of these makes the measured floor mean something other than
    what the file says it means, and a floor that means something other than what it says is the
    wrong-measurement defect this project is being rebuilt to remove."""


# === canonical integer digests ===================================================================
# A subsystem fingerprint is usually a structure -- a histogram, a table of tuples, an ordering -- and
# the sweep needs it as one integer. This is that fold.

def _canon(obj, out):
    """Append a self-delimiting canonical encoding of `obj` to `out`. Integers, strings, bytes, bools and
    containers only.

    NEVER hash() AND NEVER repr(). Python randomises str hashing per process unless PYTHONHASHSEED is
    set, so a hash()-based fingerprint differs in every process and the across-process mode below could
    only ever report "everything moved" -- a check that cannot pass is not a check. repr() of a float is
    round-trippable but its shortest form has changed across Python versions, so a repr-based digest is
    not stable across the interpreter upgrades this project will live through.

    SELF-DELIMITING, i.e. every variable-length piece carries its length. Concatenating raw fields lets
    two different structures encode to the same bytes -- ("ab", "c") and ("a", "bc") -- and a fingerprint
    that calls two different states equal is worse than no fingerprint, because the sweep reads it as
    "this package did not move" and certifies isolation that was never tested.

    Same argument and same shape as spine.rng._blob, which is deliberately not imported: that one is
    private to the RNG module and encodes generator states, this one encodes subsystem structures and
    REFUSES FLOATS. Sharing the encoder would mean the float rejection below could be lifted from
    somewhere else in the tree without anyone editing this file.
    """
    if isinstance(obj, bool):
        # Before int, because bool IS an int in Python. True and 1 encoding identically would make a
        # gate's on/off indistinguishable from a count of one in a ledger vector.
        out.append(b"B\x01" if obj else b"B\x00")
    elif isinstance(obj, int):
        b = obj.to_bytes((obj.bit_length() // 8) + 2, "big", signed=True)
        out.append(b"i" + len(b).to_bytes(2, "big") + b)
    elif isinstance(obj, str):
        b = obj.encode("utf-8")
        out.append(b"s" + len(b).to_bytes(8, "big") + b)
    elif isinstance(obj, (bytes, bytearray, memoryview)):
        b = bytes(obj)
        out.append(b"b" + len(b).to_bytes(8, "big") + b)
    elif isinstance(obj, (tuple, list)):
        # Tuple and list encode alike on purpose: json.load turns every captured tuple into a list (the
        # round-trip that tests/test_derive.py had to undo), and a fingerprint that changed because a
        # value went through a file would be measuring the file format.
        out.append(b"(" + len(obj).to_bytes(8, "big"))
        for x in obj:
            _canon(x, out)
        out.append(b")")
    elif isinstance(obj, dict):
        # Sorted keys, so a dict whose insertion order differs between two runs -- which says nothing
        # about the run -- does not read as a moved fingerprint.
        out.append(b"{" + len(obj).to_bytes(8, "big"))
        for k in sorted(obj):
            _canon(k, out)
            _canon(obj[k], out)
        out.append(b"}")
    elif isinstance(obj, float):
        raise DeterminismError(
            f"refusing to fold the float {obj!r} into an integer fingerprint. The integer channel exists "
            f"BECAUSE it is not subject to float tolerance; a float inside one makes the sweep's exact "
            f"comparison silently approximate, and the approximation would be invisible because the "
            f"result is an integer. Put continuous quantities in the float channel, where the floor "
            f"measured by this file applies to them.")
    else:
        raise DeterminismError(
            f"cannot fingerprint a {type(obj).__name__}: no encoding is declared for it. Declare one "
            f"here rather than letting it fall back to repr() -- see the note on _canon.")


def digest_int(obj):
    """A structure as one process-stable 64-bit integer, for the integer channel.

    Personalised, so these digests cannot collide with spine.rng's stream fingerprints or with a
    checkpoint hash if one is ever fed the other's bytes by mistake.
    """
    parts = []
    _canon(obj, parts)
    return int.from_bytes(hashlib.blake2b(b"".join(parts), digest_size=8,
                                          person=b"spine-det").digest(), "big")


# === the two-channel record a workload returns ===================================================

class Fingerprints:
    """What one run of a workload produced: exact integer identities, and continuous float readings.

    CONSTRUCTOR-ENFORCED, in the spirit of graft G6 (a Reading cannot be built without its provenance).
    Every rule below is here because breaking it makes the measured floor describe something other than
    the run:

      * an int channel value that is a float  -> tolerance leaks into the exact channel
      * a float channel value that is an int  -> a quantity silently changes channel between versions,
                                                 and with it the rule used to judge whether it moved
      * a NaN or an inf                       -> NaN != NaN, so a key holding one reads as "moved" on
                                                 every comparison forever, and inf - inf is NaN, so the
                                                 measured floor becomes NaN and every later comparison
                                                 against it is False. One NaN silently disables the sweep.
      * the same key in both channels          -> the report cannot say which rule judged it
    """

    __slots__ = ("ints", "floats")

    def __init__(self, ints, floats):
        self.ints = {}
        for k, v in dict(ints).items():
            if isinstance(v, bool) or not isinstance(v, int):
                raise DeterminismError(
                    f"int channel key {k!r} got {v!r} ({type(v).__name__}). The integer channel is exact "
                    f"identities only; bool is refused because True and 1 are the same value here and a "
                    f"gate state must not be confused with a count of one.")
            self.ints[str(k)] = int(v)
        self.floats = {}
        for k, v in dict(floats).items():
            if isinstance(v, bool) or not isinstance(v, float):
                raise DeterminismError(
                    f"float channel key {k!r} got {v!r} ({type(v).__name__}). Counts and identities "
                    f"belong in the int channel, where they are compared exactly; putting one here "
                    f"would give it a tolerance it does not need and hide a real off-by-one.")
            if v != v or v in (float("inf"), float("-inf")):
                raise DeterminismError(
                    f"float channel key {k!r} is {v!r}. A NaN compares unequal to itself so it reads as "
                    f"moved on every comparison; a NaN or inf difference makes the measured floor NaN, "
                    f"and every later `delta > floor` test against NaN is False -- one bad value turns "
                    f"the isolation sweep off without failing anything.")
            self.floats[str(k)] = float(v)
        both = sorted(set(self.ints) & set(self.floats))
        if both:
            raise DeterminismError(
                f"keys in both channels: {both}. One quantity, one channel, one rule for judging whether "
                f"it moved -- otherwise the report cannot say which rule was applied.")

    def keys(self):
        return sorted(self.ints), sorted(self.floats)

    def __repr__(self):
        return f"<Fingerprints ints={len(self.ints)} floats={len(self.floats)}>"


# === the synthetic reference workload ============================================================

_TORCH = []          # one-element cache; see _torch()


def _torch():
    """torch if this process can have it, else None.

    IMPORTED THROUGH A FUNCTION AND CALLED BEFORE THE frozen_rng BLOCK, NOT INSIDE IT. frozen_rng
    snapshots whatever global streams are in sys.modules AT ENTRY. If torch were first imported inside
    the guarded body, torch's global stream would not have been saved, the guard would silently cover
    less than the caller believes, and Frozen.covers would say so to a reader who never looks. That is
    the recorded shape of the old @no_rng_drift defect -- a guard that covered the generator while the
    thing it was guarding went on mutating something else.

    Measured in this environment: torch 2.13.0 imports and runs with no numpy installed, printing
    "Failed to initialize NumPy" on import, and Tensor.numpy() then raises -- which is why the byte
    extraction below goes through view(uint8).tolist() rather than .numpy().tobytes().
    """
    if not _TORCH:
        try:
            import torch                                                        # noqa: PLC0415
            _TORCH.append(torch)
        except Exception:
            # Deliberately broad. A torch that is installed but fails to initialise (no CUDA driver,
            # a mismatched build) must degrade to "no torch channel" rather than take down the noise
            # floor measurement, because the spine channels are still worth measuring without it.
            _TORCH.append(None)
    return _TORCH[0]


def _tensor_bytes(torch, t):
    """A tensor's raw bytes, exactly, with no numpy.

    view(torch.uint8) reinterprets the storage rather than converting values, so this is a BIT-EXACT
    identity and belongs in the integer channel. tolist() on the float tensor instead would hand back
    Python floats, and digest_int refuses those for the reason given on _canon.
    """
    flat = t.detach().cpu().contiguous().flatten()
    return bytes(flat.view(torch.uint8).tolist())


def reference_workload(seed):
    """A synthetic run over what actually exists today: spine.rng and spine.derive.

    ITS SHAPE IS THE POINT, not its content. The keys below are the fingerprint set graft G3 names for
    the isolation sweep -- tokenizer id2bytes ordering, memory (slot, src, key-hash) table, fabric
    routing histogram plus n_live, stream label histogram, ledger counter vector -- so when the real
    mechanism packages arrive the harness around them does not change shape, only the producer does.

    IT DRAWS FROM PER-SUBSYSTEM STREAMS, NEVER FROM THE GLOBAL ONE, and that is not decoration either.
    A workload that called random.random() would have its second repeat start from wherever its first
    repeat left the global stream, so the two repeats would differ for a reason that has nothing to do
    with the machine, and the measured floor would be an artifact of the harness. The frozen_rng guard in
    _run_once() catches that case and reports it rather than absorbing it.
    """
    tok = rng_for("tokenizer", seed)
    fab = rng_for("fabric", seed)
    cull = fab.spawn("cull")
    mem = rng_for("memory", seed)
    stream = rng_for("stream", seed)

    ints, floats = {}, {}

    # -- tokenizer: a vocabulary whose ORDER is the identity ---------------------------------------
    # id2bytes order, not the set of byte strings: two vocabularies with the same members in a different
    # order assign different ids to the same text, so every downstream id is different. A fingerprint
    # over the SET would call those two runs equal, which is the "fingerprint that cannot see the
    # difference" failure that makes a sweep certify isolation it never tested.
    vocab = [tok.randbytes(1 + tok.randint(0, 3)) for _ in range(512)]
    n_bytes = sum(len(v) for v in vocab)
    ints["tok.id2bytes"] = digest_int(tuple(vocab))
    ints["tok.total_bytes"] = n_bytes
    ints["tok.draws"] = tok.draws
    ints["tok.rng_state"] = fingerprint(tok)

    # bytes_per_token is the measured ratio, and it is CONTINUOUS -- the one quantity here that has a
    # legitimate claim on a tolerance. spine.derive's docstring records why there is only one estimator
    # for it: the old tree had three, one of which flipped sign with vocabulary size (1.50 unweighted
    # against 1.85 as used at 512 tokens).
    bpt = derive.bytes_per_token(n_bytes, len(vocab))
    floats["tok.bytes_per_token"] = bpt
    # The width derived from it is an INTEGER byte count and is compared exactly. This is the value whose
    # two-place resolution produced the confirmed one-byte eval signature; a harness that let it drift
    # inside a tolerance would be unable to see that defect recur.
    ints["sig.width_bytes"] = derive.signature_width_bytes(256, bpt)

    # -- fabric: routing histogram, n_live, and the gate's arithmetic -------------------------------
    slots = 4096
    hist = [0] * 64
    for _ in range(4000):
        hist[fab.randrange(64)] += 1
    ints["fab.routing_hist"] = digest_int(tuple(hist))
    ints["fab.n_live"] = sum(1 for h in hist if h > 0)
    ints["fab.operating_population"] = derive.operating_population(0.45, slots)
    # The gate counted over a population sweep, not sampled at one point: the recorded failure was a
    # gate that read ARMED AND INERT for an entire investigation because occupancy parked at 0.50 under
    # a pressure of 0.75, and a single-point probe is exactly what failed to show it.
    ints["fab.gate_open_count"] = sum(1 for n in range(1500, 2600, 7)
                                      if derive.cull_gate_open(n, slots, 0.45))
    victims = cull.sample(range(64), 8)
    ints["fab.cull_victims"] = digest_int(tuple(sorted(victims)))
    ints["fab.cull_draws"] = cull.draws
    ints["fab.soft_cap"] = derive.lift_to(160, 0.05, 16)
    # A long float reduction, which is where summation order shows up if it is going to. This one is
    # single-threaded Python and has never moved here; it is kept as the CONTROL against the torch
    # readings below, which do move with thread count. When the floor rises, the question is immediately
    # whether arithmetic moved or the library did, and that needs a quantity outside the library.
    floats["fab.centroid_drift"] = sum(fab.gauss() for _ in range(4096)) / 4096.0

    # -- memory: the (slot, src, key-hash) table G3 names -------------------------------------------
    table = []
    for slot in range(256):
        src = mem.choice(("eng", "code", "math", "web"))
        table.append((slot, src, digest_int((slot, src, mem.getrandbits(32)))))
    ints["mem.table"] = digest_int(tuple(table))
    ints["mem.draws"] = mem.draws

    # -- stream: the label histogram --------------------------------------------------------------
    labels = {}
    for _ in range(2048):
        lab = stream.choice(("eng", "code", "math", "web", "held"))
        labels[lab] = labels.get(lab, 0) + 1
    ints["stream.label_hist"] = digest_int(labels)
    ints["stream.rng_state"] = fingerprint(stream)

    # -- ledger: the counter vector ---------------------------------------------------------------
    # One digest AND the raw counts. The digest catches any change; the raw counts are what a human
    # reads when it does change, because "ledger digest moved" names nothing to go and look at.
    ints["ledger.counters"] = digest_int((tok.draws, fab.draws, cull.draws, mem.draws, stream.draws))
    ints["ledger.total_draws"] = tok.draws + fab.draws + cull.draws + mem.draws + stream.draws

    # -- torch, if this process has it -------------------------------------------------------------
    # THE MOST INFORMATIVE PART OF THIS WORKLOAD FOR P3, because at P3 every number the system produces
    # comes out of autograd, and reduction order inside a backward pass is the realistic source of a
    # non-zero floor. The generator comes from the fabric's stream via torch_generator(), never from
    # torch.manual_seed(), so torch's own global stream stays untouched -- otherwise torch draw order
    # becomes a coupling channel that no wire declares and the sweep cannot tell it from a lever leak.
    torch = _torch()
    if torch is not None:
        g = fab.torch_generator()
        x = torch.randn(192, 192, generator=g)
        w = torch.randn(192, 192, generator=g)
        h = torch.tanh(x @ w)
        # THE TENSOR AS AN IDENTITY AND THE MEAN OVER IT AS A READING, DELIBERATELY BOTH. Measured here
        # at 1 thread against 4: these bits are identical and that mean differs by 1.863e-09. Keeping
        # only the digest would report "nothing moved" on a machine whose reported losses do; keeping
        # only the mean would put a tolerance around a quantity that is exactly reproducible and let a
        # real change hide inside it. The pair is what says WHICH of the two happened.
        ints["torch.activation_bits"] = digest_int(_tensor_bytes(torch, h))
        floats["torch.activation_mean"] = float(h.mean())
        floats["torch.activation_absmax"] = float(h.abs().max())
        w2 = w.clone().requires_grad_(True)
        loss = (torch.tanh(x @ w2) ** 2).mean()
        loss.backward()
        # .detach() before float(): torch warns that converting a requires_grad tensor to a scalar
        # "may lead to unexpected behavior", and a reading taken off the autograd graph is exactly the
        # instrument-touches-what-it-measures shape graft G7 exists to remove.
        floats["torch.loss"] = float(loss.detach())
        ints["torch.grad_bits"] = digest_int(_tensor_bytes(torch, w2.grad))
        floats["torch.grad_absmax"] = float(w2.grad.abs().max())

    return Fingerprints(ints, floats)


# THE P3 PLUG POINT. ==============================================================================
# When the mechanism packages exist (plan section 5, P3: data/ tok/ lm/ sig/ fabric/ memory/ domains/
# opt/ train/ ckpt/), register the real thing here:
#
#     def training_workload(seed):
#         cfg = assemble.build(environ={})          # defaults only; a floor measured under one operator's
#         ...                                       # environment is that operator's floor, not the machine's
#         run = train.run(cfg, seed=seed, steps=Steps(200))
#         return Fingerprints(ints=run.package_fingerprints(), floats=run.continuous_readings())
#
#     WORKLOADS["training"] = training_workload
#
# Nothing else in this file changes: measure(), the diff, the machine identity and the written record are
# all written against the Fingerprints contract rather than against what produces it. The reference
# workload STAYS registered after that, because it is the control -- if the training floor jumps, running
# the reference tells you whether the machine changed or the training run did, and without that control
# every floor regression is ambiguous.
#
# 200 steps, and both data paths, matching tests/test_default_runs.py: a floor measured on a workload
# shorter than the sweep's runs would underestimate the noise the sweep actually meets, because float
# error accumulates with the number of reductions.
WORKLOADS = {"reference": reference_workload}


# === running a workload, once and repeatedly =====================================================

def _run_once(run, seed):
    """One repeat. Returns (Fingerprints, moved_global_streams, covered_streams).

    reset_issued() IS CALLED HERE, NOT IN THE WORKLOAD. spine.rng refuses to issue one subsystem's stream
    twice for the same seed in one process -- two generators for one name replay the same sequence while
    each call site believes it has its own. Repeating a workload in one interpreter is precisely the
    legitimate case that rule has to allow, so the harness that knows it is repeating clears the
    bookkeeping. The workload must not: at P3 the real training run is not aware it is being repeated,
    and a training run that called reset_issued() would be papering over a genuine duplicate stream.

    frozen_rng REPORTS AS WELL AS RESTORES. Restoring keeps repeat 2 comparable with repeat 1 -- without
    it a workload that touched the global stream would start each repeat from a different position and
    the "floor" would be measuring the harness. But restoring alone would leave the defect invisible, so
    `moved` is returned and printed. A workload that moves the global streams has an undeclared coupling
    channel, and at P3 that is the difference between a training run and a training run that its own
    diagnostics are editing.
    """
    reset_issued()
    # THE IMPORT HAPPENS HERE, ONE LINE ABOVE THE GUARD, AND THIS IS NOT TIDINESS. It was written below
    # the guard first and frozen_rng raised on the very first repeat: torch was not in sys.modules when
    # frozen_rng took its `before` fingerprint, the workload imported it inside the body, and the global
    # state at exit therefore included a torch stream that did not exist at entry -- so the restore could
    # not reproduce the entry fingerprint and the guard correctly refused. The measured message was
    # "frozen_rng could not restore the global streams it covers ('random',)". Left as it was, every
    # workload that first touches a library inside the guard would either crash like that or, with the
    # strict check off, run under a guard whose `covers` silently omitted the stream it was meant to
    # protect. _torch() caches, so this costs nothing after the first repeat.
    _torch()
    with frozen_rng() as f:
        fp = run(seed)
    return fp, bool(f.moved), tuple(f.covers)


def _check_repeats(repeats):
    """Refuse fewer than two repeats, and say why rather than returning a zero."""
    n = int(repeats)
    if n < MIN_REPEATS:
        raise DeterminismError(
            f"repeats={n}: refusing to write a noise floor from fewer than {MIN_REPEATS} runs. One run "
            f"diffs against nothing, so the 'floor' it produces is the number zero with a filename on "
            f"it -- and a zero floor is option 1 from this file's docstring, the assumption this whole "
            f"harness exists to replace. Nothing is written.")
    return n


def repeat_in_process(run, seed, repeats):
    """Run the workload `repeats` times inside this interpreter. The mode the isolation sweep matches."""
    n = _check_repeats(repeats)
    out = []
    for _ in range(n):
        fp, moved, covers = _run_once(run, seed)
        out.append((fp, moved, covers))
    return out


def repeat_across_processes(workload_name, seed, repeats):
    """Run the workload `repeats` times, each in a fresh interpreter, via --emit.

    THE CALLABLE CANNOT CROSS A PROCESS BOUNDARY, which is why this mode takes a NAME out of WORKLOADS
    rather than a function. That is a feature: it forces the real P3 workload to be registered under a
    name, and a workload that only exists as a closure in somebody's test cannot be measured
    across-process at all -- so the registry is the thing that keeps this mode alive.

    stdout carries exactly one JSON line and nothing else; stderr is left alone because torch prints
    "Failed to initialize NumPy" there on every import in this environment and a harness that treated
    stderr output as failure would refuse to run at all here.
    """
    n = _check_repeats(repeats)
    out = []
    for _ in range(n):
        proc = subprocess.run(
            [sys.executable, os.path.abspath(__file__), "--emit",
             "--workload", workload_name, "--seed", str(int(seed))],
            capture_output=True, text=True)
        if proc.returncode != 0:
            raise DeterminismError(
                f"the --emit subprocess exited {proc.returncode}. A subprocess that cannot run the "
                f"workload gives no across-process floor at all, and continuing with the in-process "
                f"number alone would silently narrow what was measured.\n{proc.stderr[-2000:]}")
        out.append(_decode_emit(proc.stdout))
    return out


# -- the --emit wire format ------------------------------------------------------------------------
# FLOATS TRAVEL AS float.hex(), NOT AS JSON NUMBERS. json.dumps uses repr, which round-trips exactly in
# CPython today -- but the quantity being measured here is the difference in the last bits, so a
# transport that is merely believed to be exact would put the transport inside the measurement. If the
# encoding ever loses a bit, the across-process floor would report that loss as machine noise and the
# sweep would inherit a tolerance that describes a JSON serialiser. float.fromhex(float.hex(x)) == x is
# exact by construction, for every finite float, on every platform.

def _encode_emit(fp, moved, covers):
    return json.dumps({
        "ints": fp.ints,
        "floats": {k: v.hex() for k, v in fp.floats.items()},
        "moved": moved,
        "covers": list(covers),
    }, sort_keys=True)


def _decode_emit(text):
    line = text.strip().splitlines()[-1] if text.strip() else ""
    try:
        d = json.loads(line)
    except Exception as e:
        raise DeterminismError(f"could not parse the --emit line: {e}. Got {line[:200]!r}")
    fp = Fingerprints(d["ints"], {k: float.fromhex(v) for k, v in d["floats"].items()})
    return fp, bool(d["moved"]), tuple(d["covers"])


# === the diff ====================================================================================

def diff_pair(a, b):
    """Compare two Fingerprints. Returns (int_mismatches, float_deltas).

    A KEY SET MISMATCH IS FATAL, NOT A DIFFERENCE. If two runs of the same workload at the same seed
    produced different keys, then some mechanism ran in one and not the other, and no per-key tolerance
    describes that. Reporting it as "n keys moved" would let a whole subsystem disappear between runs and
    surface as a tolerance number.

    RELATIVE DIFFERENCE IS max(|a|,|b|)-NORMALISED, and it is reported BESIDE the absolute one rather
    than instead of it, because this project's quantities span orders of magnitude: a bpb near 2.0 and a
    ledger sum near 1e6 cannot share one absolute tolerance, and a value legitimately near zero cannot
    have a meaningful relative one. The sweep picks the appropriate rule per quantity; this file's job is
    to measure both and not to choose for it.
    """
    ai, af = a.keys()
    bi, bf = b.keys()
    if ai != bi or af != bf:
        missing = sorted((set(ai) | set(af)) ^ (set(bi) | set(bf)))
        raise DeterminismError(
            f"two runs of one workload at one seed produced different fingerprint keys; the symmetric "
            f"difference is {missing[:12]}{' ...' if len(missing) > 12 else ''}. That is a mechanism "
            f"that fired in one run and not the other, not a tolerance question.")
    int_mismatch = {k: (a.ints[k], b.ints[k]) for k in ai if a.ints[k] != b.ints[k]}
    float_delta = {}
    for k in af:
        x, y = a.floats[k], b.floats[k]
        d = abs(x - y)
        scale = max(abs(x), abs(y))
        float_delta[k] = (d, (d / scale) if scale > 0.0 else 0.0)
    return int_mismatch, float_delta


def fold(records, mode):
    """Fold N repeats into one measurement: max over ALL PAIRS, not against repeat 0.

    ALL PAIRS, because comparing everything to the first run makes run 0 privileged for no reason. With
    three repeats where runs 1 and 2 agree with each other but not with run 0, the against-run-0 fold and
    the all-pairs fold report the same maximum -- but where run 0 happens to sit between the other two,
    against-run-0 reports roughly half the true spread. Half a floor is the tolerance-picked-out-of-air
    failure again, arrived at arithmetically.
    """
    n = len(records)
    fps = [r[0] for r in records]
    moved = any(r[1] for r in records)
    covers = records[0][2]

    unstable = {}
    per_key_abs, per_key_rel = {}, {}
    for i in range(n):
        for j in range(i + 1, n):
            mism, deltas = diff_pair(fps[i], fps[j])
            for k, pair in mism.items():
                unstable.setdefault(k, set()).add(pair)
            for k, (d, r) in deltas.items():
                if d > per_key_abs.get(k, -1.0):
                    per_key_abs[k] = d
                if r > per_key_rel.get(k, -1.0):
                    per_key_rel[k] = r

    max_abs = max(per_key_abs.values()) if per_key_abs else 0.0
    max_rel = max(per_key_rel.values()) if per_key_rel else 0.0
    # argmax is recorded because the FLOOR ALONE NAMES NOTHING. When the floor rises after a change, the
    # first question is which quantity moved, and a number with no key beside it sends the reader to
    # re-run the whole harness to find out.
    #
    # NULL WHEN THE MAXIMUM IS ZERO, and that is not cosmetic. max() over an all-zero mapping returns
    # whichever key iteration reached first, so a run where nothing moved at all printed
    # "max_abs 0.0 (fab.centroid_drift)" -- which reads as "fab.centroid_drift is the noisiest quantity"
    # and sends a reader to investigate a key that did nothing. An argmax of a set with no maximum is
    # not a fact, and this file prints facts.
    arg_abs = max(per_key_abs, key=per_key_abs.get) if max_abs > 0.0 else None
    arg_rel = max(per_key_rel, key=per_key_rel.get) if max_rel > 0.0 else None
    ints_keys, float_keys = fps[0].keys()
    return {
        "mode": mode,
        "repeats": n,
        "pairs": n * (n - 1) // 2,
        "global_streams_moved": moved,
        "frozen_rng_covers": list(covers),
        "int_channel": {
            "keys": len(ints_keys),
            "stable": not unstable,
            "unstable": {k: sorted(str(p) for p in v) for k, v in sorted(unstable.items())},
        },
        "float_channel": {
            "keys": len(float_keys),
            "max_abs": max_abs,
            "max_rel": max_rel,
            "argmax_abs": arg_abs,
            "argmax_rel": arg_rel,
            "per_key_abs": {k: per_key_abs[k] for k in sorted(per_key_abs)},
            "per_key_rel": {k: per_key_rel[k] for k in sorted(per_key_rel)},
        },
    }


# === machine identity ============================================================================
# A floor measured on one machine says nothing about another, so the floor is worthless without this.

# The fields that actually change floating-point arithmetic, as opposed to the ones that merely describe
# the box. Core count and thread count change reduction order inside torch -- MEASURED HERE, not assumed:
# at OMP_NUM_THREADS=1 against 4 on this machine, torch.activation_bits and torch.grad_bits are identical
# while torch.loss moves by 1.192e-07 (1.267e-07 relative), because the tensors are bit-stable and the
# mean over them is the parallelised part. The torch build changes which kernels run; the CPU
# architecture changes the vector width. Hostname and kernel release are RECORDED
# but deliberately NOT in this list: a machine that was renamed or took a kernel patch is the same
# arithmetic, and a key that changed for those would invalidate every stored floor for no reason -- a
# guard that trips on everything gets disabled, which is how the sweep dies.
_KEY_FIELDS = ("machine", "python_version", "torch_version", "cpu_count", "torch_threads",
               "torch_interop_threads")


def machine_identity():
    """What this floor was measured on. Recorded beside the floor; the digest of _KEY_FIELDS gates reuse.

    THREAD COUNTS COME FROM torch.get_num_threads(), NOT FROM OMP_NUM_THREADS. Two reasons, and the first
    is the binding one: spine/lever.py's LeverSet.from_env is the only code in this tree allowed to name
    os.environ, and this file is not it. The second is that it is the better measurement anyway -- the
    env var is a request, get_num_threads() is what torch decided, and they disagree whenever the
    variable is unset, malformed, or overridden by a call somewhere in the process.

    sched_getaffinity, where it exists, in preference to cpu_count(): under a cgroup or a taskset the
    process may be pinned to four of sixty-four cores, and the count that changes the reduction order is
    the one it can actually use. cpu_count() would record the box and miss the run.
    """
    ident = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "node": platform.node(),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "cpu_count": None,
        "cpu_count_source": None,
        "torch_version": None,
        "torch_threads": None,
        "torch_interop_threads": None,
        "torch_cuda_available": None,
        "numpy_version": None,
    }
    if hasattr(os, "sched_getaffinity"):
        ident["cpu_count"] = len(os.sched_getaffinity(0))
        ident["cpu_count_source"] = "sched_getaffinity"
    else:
        ident["cpu_count"] = os.cpu_count()
        ident["cpu_count_source"] = "os.cpu_count"

    torch = _torch()
    if torch is not None:
        ident["torch_version"] = str(torch.__version__)
        ident["torch_threads"] = int(torch.get_num_threads())
        ident["torch_interop_threads"] = int(torch.get_num_interop_threads())
        # is_available() only. NOT device names, and nothing that initialises a context: spine/rng.py
        # makes the same choice for the same reason -- a function whose job is to describe the machine
        # must not be the call that allocates a CUDA context and changes it.
        ident["torch_cuda_available"] = bool(torch.cuda.is_available())
    np = sys.modules.get("numpy")
    if np is not None:
        ident["numpy_version"] = str(getattr(np, "__version__", "unknown"))

    ident["key"] = digest_int(tuple((f, ident[f]) for f in _KEY_FIELDS))
    ident["key_fields"] = list(_KEY_FIELDS)
    return ident


# === writing and reading the floor ===============================================================

def build_record(measurements, seed, workload_name):
    """Assemble the file's contents.

    THE TOP-LEVEL `floor` NAMES ITS MODE. Collapsing within-process and across-process into one number
    would invite the sweep to compare in-process fingerprints against a tolerance that includes
    cross-process variation, which is a looser tolerance than the sweep needs and would hide small real
    leaks. The sweep runs in one interpreter, so the headline floor is the within-process one and the
    file says so in the field rather than in a convention somebody has to remember.

    `usable` IS FALSE WHENEVER ANY INTEGER FINGERPRINT WAS UNSTABLE, and the floor is then null. The
    record is still written: "this machine could not produce two identical seeded runs, and here are the
    keys that disagreed" is a more useful artifact than a missing file, and a missing file is
    indistinguishable from a harness nobody ran.
    """
    stable = all(m["int_channel"]["stable"] for m in measurements.values())
    head = measurements.get("within_process") or next(iter(measurements.values()))
    floor = None
    if stable:
        floor = {
            "mode": head["mode"],
            "abs": head["float_channel"]["max_abs"],
            "rel": head["float_channel"]["max_rel"],
            "repeats": head["repeats"],
            "float_keys": head["float_channel"]["keys"],
            "int_keys": head["int_channel"]["keys"],
            "means": ("the largest difference OBSERVED across these repeats on this machine. A LOWER "
                      "BOUND on the machine's noise, not a ceiling: repeats that agreed do not prove "
                      "the machine is deterministic, only that nothing disagreed this many times. A "
                      "measured 0.0 means no difference was seen, not that none can occur."),
        }
    return {
        "schema": SCHEMA,
        "written_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "workload": workload_name,
        "seed": int(seed),
        "usable": bool(stable),
        "floor": floor,
        "machine": machine_identity(),
        "measurements": measurements,
    }


def write_floor(record, path=FLOOR_PATH):
    """Write the record. Refuses a record built from too few repeats, again, at the last moment.

    THE CHECK IS REPEATED HERE ON PURPOSE. _check_repeats already guards the measurement, but this
    function is the only thing that makes a floor durable, and a floor on disk is what every later run
    trusts without re-deriving. A caller that assembles a record by hand -- a future harness, a
    resumed partial measurement -- must not be able to reach the disk with a one-repeat floor because it
    took a path that skipped the earlier guard.

    Sorted keys and a trailing newline so a diff between two runs of this harness is readable; that diff
    is how a floor regression gets noticed at all.
    """
    for name, m in record.get("measurements", {}).items():
        if int(m.get("repeats", 0)) < MIN_REPEATS:
            raise DeterminismError(
                f"refusing to write: measurement {name!r} has repeats={m.get('repeats')}, below the "
                f"minimum of {MIN_REPEATS}. See _check_repeats.")
    if not record.get("measurements"):
        raise DeterminismError("refusing to write a floor record with no measurements in it.")
    with open(path, "w") as fh:
        json.dump(record, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return path


def load_floor(path=FLOOR_PATH, require_machine=True, require_usable=True):
    """Read a floor back, and REFUSE one that was not measured here.

    This is the function the isolation sweep calls. Every refusal below is a way the sweep could
    otherwise end up running against a tolerance that describes something else:

      * unknown schema      -- fields whose meaning has changed read as fields whose meaning is known
      * foreign machine key -- a floor from a CI box read on a workstation is a guessed tolerance with a
                               provenance stamp on it, which is strictly worse than an admitted guess
                               because it survives review
      * usable=false        -- the integer channel was not stable when this was measured, so the sweep's
                               exact comparisons do not hold on this machine and its results would be
                               noise reported as couplings

    require_machine defaults to True and should stay True in the sweep. It exists as a parameter only so
    a human inspecting a floor from another machine can read the file without editing this one.
    """
    with open(path) as fh:
        rec = json.load(fh)
    if rec.get("schema") != SCHEMA:
        raise DeterminismError(
            f"{path}: schema is {rec.get('schema')!r}, this harness writes {SCHEMA!r}. Re-measure rather "
            f"than reading the fields that happen to still parse.")
    if require_usable and not rec.get("usable"):
        raise DeterminismError(
            f"{path}: usable=false -- the integer channel was not stable when this floor was measured, "
            f"so there is no exact comparison for the sweep to stand on. "
            f"Unstable keys: {_unstable_keys(rec)}")
    if require_machine:
        here = machine_identity()
        there = rec.get("machine", {})
        if there.get("key") != here["key"]:
            diffs = [f"{f}: recorded {there.get(f)!r} vs here {here.get(f)!r}"
                     for f in _KEY_FIELDS if there.get(f) != here.get(f)]
            raise DeterminismError(
                f"{path} was measured on a different machine, so its floor says nothing about this one. "
                + ("; ".join(diffs) if diffs else "the identity digest differs")
                + ". Re-run tests/test_determinism.py here.")
    return rec


def _unstable_keys(rec):
    out = set()
    for m in rec.get("measurements", {}).values():
        out.update(m.get("int_channel", {}).get("unstable", {}))
    return sorted(out)


# === the measurement, and the report =============================================================

def measure(workload_name="reference", seed=DEFAULT_SEED, repeats=DEFAULT_REPEATS,
            across_process=True):
    """Measure the floor in the requested modes and return the record. Writes nothing."""
    if workload_name not in WORKLOADS:
        raise DeterminismError(f"no workload named {workload_name!r}; have {sorted(WORKLOADS)}")
    run = WORKLOADS[workload_name]
    _check_repeats(repeats)
    # Imported once up front as well as inside _run_once, so that machine_identity() below records the
    # torch version even when a mode ran zero in-process repeats.
    _torch()
    measurements = {"within_process": fold(repeat_in_process(run, seed, repeats), "within_process")}
    if across_process:
        measurements["across_process"] = fold(
            repeat_across_processes(workload_name, seed, repeats), "across_process")
    return build_record(measurements, seed, workload_name)


def _fmt(x):
    """Full precision, because the quantity is a difference in the last bits and %.6g would round the
    measurement away -- printing a floor as 0.000000 when it is 4e-8 is the same error as assuming zero."""
    return repr(x)


def report(rec, out=None):
    out = out or sys.stdout
    m = rec["machine"]
    print(f"noise floor  workload={rec['workload']}  seed={rec['seed']}", file=out)
    print(f"  machine    {m['platform']}", file=out)
    print(f"             python {m['python_version']}  torch {m['torch_version']}  "
          f"cpu {m['cpu_count']} ({m['cpu_count_source']})  torch_threads {m['torch_threads']}",
          file=out)
    print(f"             identity key {m['key']:#018x} over {','.join(m['key_fields'])}", file=out)
    for name in ("within_process", "across_process"):
        mm = rec["measurements"].get(name)
        if mm is None:
            continue
        ic, fc = mm["int_channel"], mm["float_channel"]
        print(f"  {name:<15} {mm['repeats']} repeats, {mm['pairs']} pairs", file=out)
        print(f"    int   {ic['keys']:>3} keys  "
              f"{'ALL EXACT' if ic['stable'] else str(len(ic['unstable'])) + ' UNSTABLE'}", file=out)
        for k, vals in ic["unstable"].items():
            print(f"          UNSTABLE {k}: {'; '.join(vals)}", file=out)
        print(f"    float {fc['keys']:>3} keys  max_abs {_fmt(fc['max_abs'])} ({fc['argmax_abs']})  "
              f"max_rel {_fmt(fc['max_rel'])} ({fc['argmax_rel']})", file=out)
        # A workload that moved the global streams is reported whether or not it changed the floor: the
        # guard restored them, so the floor is unaffected HERE and the defect is still there for the next
        # caller who forgets the guard. That is the recorded @no_rng_drift failure exactly.
        if mm["global_streams_moved"]:
            print(f"    WARN  the workload MOVED the global RNG streams "
                  f"(guard covered {mm['frozen_rng_covers']}). It should be drawing from rng_for() "
                  f"streams only; global draw order is an undeclared coupling channel.", file=out)
    if rec["usable"]:
        f = rec["floor"]
        print(f"  FLOOR      abs {_fmt(f['abs'])}  rel {_fmt(f['rel'])}  "
              f"(mode {f['mode']}, {f['repeats']} repeats)", file=out)
        print(f"             lower bound on this machine's noise, not a ceiling", file=out)
    else:
        print(f"  FLOOR      REFUSED -- integer fingerprints were not stable: {_unstable_keys(rec)}",
              file=out)
        print(f"             The sweep's exact comparisons do not hold on this machine as configured; "
              f"a float tolerance cannot repair an identity that moved.", file=out)


# === self-check ==================================================================================

def smoke():
    """Exercise every public function once, including the paths that must REFUSE.

    A harness whose refusals are untested is a harness whose refusals do not exist. Three of the four
    checks below are for refusals, because every one of them is a way a bad floor reaches the sweep
    wearing a good floor's filename.
    """
    # digest_int is stable and self-delimiting: the two structures below differ only in where the split
    # falls, and a fingerprint that called them equal would let a real change through.
    assert digest_int((1, 2, 3)) == digest_int([1, 2, 3])
    assert digest_int((("ab",), ("c",))) != digest_int((("a",), ("bc",)))
    assert digest_int(True) != digest_int(1)
    try:
        digest_int(1.5)
        raise AssertionError("digest_int accepted a float into the integer channel")
    except DeterminismError:
        pass

    # Fingerprints refuses the four ways a channel can be corrupted.
    Fingerprints({"a": 1}, {"b": 1.0})
    for ints, floats, what in (({"a": 1.0}, {}, "float in the int channel"),
                               ({}, {"b": 1}, "int in the float channel"),
                               ({}, {"b": float("nan")}, "NaN in the float channel"),
                               ({"c": 1}, {"c": 1.0}, "one key in both channels")):
        try:
            Fingerprints(ints, floats)
            raise AssertionError(f"Fingerprints accepted {what}")
        except DeterminismError:
            pass

    # Fewer than two repeats is refused everywhere it can be reached.
    for n in (0, 1):
        try:
            repeat_in_process(reference_workload, DEFAULT_SEED, n)
            raise AssertionError(f"repeat_in_process accepted repeats={n}")
        except DeterminismError:
            pass
    try:
        write_floor({"measurements": {"x": {"repeats": 1}}}, os.path.join(HERE, "_smoke_reject.json"))
        raise AssertionError("write_floor accepted a one-repeat measurement")
    except DeterminismError:
        pass

    # The workload is reproducible in-process, which is the property the whole file rests on. Compared
    # by key set and int channel here, not by float equality: this assertion must not itself assume the
    # zero floor the harness exists to measure.
    a, _, _ = _run_once(reference_workload, 7)
    b, _, _ = _run_once(reference_workload, 7)
    mism, deltas = diff_pair(a, b)
    assert not mism, f"reference workload is not reproducible in-process: {mism}"
    assert deltas, "the float channel is empty; there is nothing for a floor to be measured on"

    # A different seed must move it, or the workload is not reading the seed and every "identical" run is
    # identical for the wrong reason -- which would report a zero floor on a machine of any behaviour.
    c, _, _ = _run_once(reference_workload, 8)
    mism8, _ = diff_pair(a, c)
    assert mism8, "seed 7 and seed 8 produced identical integer fingerprints; the workload ignores it"

    # A foreign machine key is refused. Written and read back through the real functions so the check
    # covers the file format too, not just the comparison.
    tmp = os.path.join(HERE, "_smoke_floor.json")
    rec = build_record({"within_process": fold([(a, False, ("random",)), (b, False, ("random",))],
                                               "within_process")}, 7, "reference")
    write_floor(rec, tmp)
    assert load_floor(tmp)["seed"] == 7
    rec["machine"]["key"] = rec["machine"]["key"] ^ 1
    rec["machine"]["cpu_count"] = -1
    write_floor(rec, tmp)
    try:
        load_floor(tmp)
        raise AssertionError("load_floor accepted a floor from another machine")
    except DeterminismError:
        pass
    os.remove(tmp)

    # THE COMPARISON CAN SEE A ONE-ULP DIFFERENCE. Without this check a measured floor of 0.0 has two
    # explanations that look identical in the output -- the machine was quiet, or the diff is dead -- and
    # this file's entire product is that number. A floor of zero from a broken comparison is the
    # untrippable-guard class (60 of 475 survey records) sitting on top of the sweep. The perturbation is
    # one ULP because that is the smallest difference that exists; a comparison that catches it catches
    # everything larger.
    import math                                                             # noqa: PLC0415
    base = a.floats["tok.bytes_per_token"]
    nudged = math.nextafter(base, math.inf)
    assert nudged != base
    p1 = Fingerprints(a.ints, a.floats)
    p2 = Fingerprints(a.ints, dict(a.floats, **{"tok.bytes_per_token": nudged}))
    seen = fold([(p1, False, ("random",)), (p2, False, ("random",))], "within_process")
    assert seen["float_channel"]["max_abs"] == abs(nudged - base) > 0.0, seen["float_channel"]
    assert seen["float_channel"]["argmax_abs"] == "tok.bytes_per_token"
    assert seen["int_channel"]["stable"], "a float-only perturbation moved the integer channel"
    # ... and an integer that moves is reported as UNSTABLE, never folded into the tolerance.
    p3 = Fingerprints(dict(a.ints, **{"fab.n_live": a.ints["fab.n_live"] + 1}), a.floats)
    seen_i = fold([(p1, False, ("random",)), (p3, False, ("random",))], "within_process")
    assert seen_i["int_channel"]["stable"] is False
    assert "fab.n_live" in seen_i["int_channel"]["unstable"]
    assert build_record({"within_process": seen_i}, 7, "reference")["floor"] is None

    # An all-quiet fold names no argmax, so a zero floor cannot point at an innocent key.
    quiet = fold([(p1, False, ("random",)), (p1, False, ("random",))], "within_process")
    assert quiet["float_channel"]["max_abs"] == 0.0
    assert quiet["float_channel"]["argmax_abs"] is None

    # The --emit round trip is bit-exact. If it is not, the across-process floor measures the serialiser.
    enc = _encode_emit(a, False, ("random",))
    back, moved, covers = _decode_emit(enc)
    assert back.ints == a.ints and back.floats == a.floats and moved is False and covers == ("random",)


# === entry point =================================================================================

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--workload", default="reference", choices=sorted(WORKLOADS))
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    p.add_argument("--out", default=FLOOR_PATH)
    p.add_argument("--in-process-only", action="store_true",
                   help="skip the fresh-subprocess repeats (they cost one interpreter start each)")
    p.add_argument("--check", action="store_true",
                   help="re-read the written floor on this machine and re-verify it; measures nothing")
    p.add_argument("--emit", action="store_true",
                   help="internal: run the workload once and print one JSON line on stdout")
    a = p.parse_args(argv)

    if a.emit:
        # stdout carries the JSON line and nothing else. A stray print here would be parsed as the
        # result by repeat_across_processes, or would shift which line is last.
        fp, moved, covers = _run_once(WORKLOADS[a.workload], a.seed)
        sys.stdout.write(_encode_emit(fp, moved, covers) + "\n")
        return 0

    if a.check:
        rec = load_floor(a.out)
        report(rec)
        print(f"  CHECK      {a.out} is valid for this machine", file=sys.stdout)
        return 0

    smoke()
    print("smoke OK (digests, channel guards, repeat minimum, seed sensitivity, "
          "machine-key refusal, one-ULP sensitivity, emit round-trip)")
    rec = measure(a.workload, a.seed, a.repeats, across_process=not a.in_process_only)
    report(rec)
    path = write_floor(rec, a.out)
    print(f"  wrote      {path}")
    # NON-ZERO ON AN UNSTABLE INTEGER CHANNEL. The record is written either way -- see build_record --
    # but the exit code has to say that the precondition the isolation sweep depends on was not met,
    # because a harness that exits 0 while refusing to publish a floor reads as a harness that passed.
    return 0 if rec["usable"] else 1


if __name__ == "__main__":
    sys.exit(main())
