"""DOM -- the frozen public surface. Signatures only; P4 writes the bodies.

DOM is the self-assembling partition, and its whole claim on existence is goal B. A partition is
not itself a goal; it earns its place because continual learning without catastrophic forgetting
needs a UNIT OF FORGETTING SMALLER THAN THE WHOLE STORE, and `did` is that unit. The domain count
sets the granularity of deletion (at 25 live domains a delete removes 1.6% of memory; at 4 it
removes 30%), and MEM's per-source floor can only protect a source that is separately named.

The sharpest lever in the file is `cull_stale`, because under a phased schedule the absent
corpus's domains go stale BY CONSTRUCTION and the old cull deleted them along with their memory --
200,000 entries ending under a single source id. That is catastrophic forgetting performed by the
manager rather than suffered by the model, and preventing it is this package's job.

THIS PACKAGE NEVER TOUCHES MEMORY. `manage` returns a PLAN; the spine carries it; MEM applies it.
The old tree had the domain manager call mem.reassign_src() and mem.delete_src() directly and read
three of MEM's internals inline at self_organize.py:3688, including a private method.

RECORD TYPES RETURNED (P4 defines them):
  Partition    per-domain cent/reservoir/size/act/born/last/visits/bornb/rad/tokc/comp, plus
               next_id, merged, cur, run, run_sig, pend, sh, nb, radp, comp_glob, collapsed_at,
               the counters and the package RNG stream
  Assignment   did, boundary, spawned, reentered
  Plan         folds, deletions, live, merged, culled, folded, held, spared, emptied
  PartitionCensus  what DOM.census returns, DECLARED HERE rather than left in that docstring's prose
               (Q-MEM-11, RESOLVED 2026-09-02): live, n_live, created, capped, merged, culled,
               folded, held, spared, emptied, boundaries, windows, per-domain visits/born/last/
               radius, pooled_radius, comp_glob, collapsed_at, partition_off, and every part.n_*
               counter. NAMED PartitionCensus AND NOT `Census` so a grep across packages stays
               unambiguous against MEM's StoreCensus. THE FIELDS CARRY DOM'S OWN SPELLINGS: `live`
               reaches MEM as `live_sources` and `n_live` reaches FAB as `live_domains`, and both
               renames stay in spine/compose.py's `produces` column -- the same record feeding two
               packages under two vocabularies is why "spell it as the consumer does" is not a
               function and cannot be a rule.
"""
import dataclasses

import torch

from spine.lever import Config, LeverError
from spine import units as U


# ==================================================================================================
# THE SWITCH ON THE NEGATIVE-PERIOD REFUSAL
# ==================================================================================================

REFUSE_NEGATIVE_PERIOD = True
"""Whether manage_period refuses a negative DOM_MANAGE_EVERY. True is the shipped state; False lets
the value through to units.Windows exactly as it did before 2026-09-04.

THE RULING (owner, 2026-09-04): "On the periods, let's refuse for now. If it has a bad effect, we
can turn off the refusal." The first sentence is the guard in manage_period; this name is the
second, which binds just as hard -- .rework/DECISIONS.md D4 rules that a thing kept for later is
kept WITH A SWITCH rather than as a code path that rots, and OFF is what is being kept.

THE ALTERNATIVES, THEIR PRICES AND THE MEASUREMENT THAT WOULD SETTLE THE CHOICE ARE WRITTEN OUT
ONCE, AT ckpt/api.py::REFUSE_NEGATIVE_PERIOD, and are not restated here: CKPT is where this question
was opened and where the first of the five refusals shipped. WHAT IS THIS FILE'S OWN, and the reason
the name is spelled here rather than imported: tests/test_ownership.py::check_o10_no_backdoor_imports
forbids DOM to import ckpt, so the five switches are five per-package policies that happen to share
a default, each governing only its own package's lever. This one governs DOM_MANAGE_EVERY and
nothing else, and turning it off here leaves the other four refusing.

IT IS NOT THE OFF SWITCH FOR DOMAIN MANAGEMENT AND MUST NOT BE READ AS ONE. That is the `manage`
flag in src/domains/levers.py, which exists precisely so the off-state is not spelled as a cadence
of zero -- and this constant does not touch it, or DOM_MANAGE_EVERY=0, in either position.

THE COST, SO IT IS NOT DISCOVERED: turning it off is a CODE EDIT. There is no
DOM_REFUSE_NEGATIVE_PERIOD, no census row and no row in the generated lever document -- deliberately,
because a lever per package would be five environment names for one decision and would make "some
accessors refuse and some do not" a reachable configuration.
"""


# ==================================================================================================
# THE FIVE NUMBERS THE BODIES NEED THAT ARE NOT LEVERS
#
# NONE OF THESE MAY BECOME A LEVER, and that is a ruling and not an oversight. The census filed no
# row for any of the five, and src/spine/lever.py refuses a computed default outright -- so a knob
# minted here would be a sixth spelling of a number nobody has ever asked to change, carrying a row
# in docs/04_LEVERS.md and a cell in every isolation sweep. They are written here, once, each with
# the measurement or the frozen-tree line it came from, which is what a constant owes a reader that
# a literal buried in an expression does not.
# ==================================================================================================

RUN_SIG_KEEP = 0.85
"""What the running signature keeps when a window does NOT trip the shift threshold
(self_organize.py:3484). The running signature is what the NEXT window's adjacent distance is
measured against, so this is the only smoothing between the detector and the stream: at 1.0 the
comparison is against the first window of the run for ever and the detector reports every slow drift
as one boundary; at 0.0 it is against the last window alone and ordinary within-segment variation
trips it. It is NOT the centroid rate below -- two EMAs over two different objects, and giving them
one name would make a change to either silently move the other."""

CENT_KEEP = 0.9
"""What a centroid keeps when a window re-enters its domain (self_organize.py:3458). This is the
drift that domains/api.py::rekey OVERWRITES from the re-encoded reservoir, which is the whole reason
a rekey is an event and not a cosmetic: between rekeys the centroid follows the material, and at a
rekey it is re-measured from the uncensored sample."""

ADJ_HIST_MAX = 512
"""Adjacent distances kept for the relative shift test -- the "last 512 adjacent distances" both
domains/api.py::observe and src/domains/levers.py::DOMLevers.shift_q already name in prose. Trimmed
from the FRONT, so the calibration follows the encoder: under SIG_MODE=learned the distances inflate
as the encoder trains (a measured .037 -> .668 over 200-4000 steps, recorded at
src/domains/levers.py::DOMLevers.spawn_dist), and a quantile taken over the whole run would be
dominated by a scale the encoder has left behind."""

MIN_ADJ_SAMPLES = 64
"""Adjacent distances required before the relative arm uses its own quantile (self_organize.py:3479).
Below it the arm falls back to shift_dist and part.n_shift_bootstrap_constant counts the window. THE
NUMBER IS IN NO REBUILD DOCSTRING and that is exactly why the counter has to exist: without it a
relative-arm run that never reached 64 adjacent samples -- every run shorter than 64 windows, and
every resume whose adj_hist was dropped before M51 -- reports the constant rule's behaviour under the
relative rule's name, with nothing anywhere saying which one decided."""

MIN_RADIUS_SAMPLES = 4
"""Reservoir windows a domain must hold before rekey measures a radius for it, from
self_organize.py:3574. domains/api.py::rekey names it in prose -- "for domains holding at least four
samples" -- and the number itself was otherwise a literal. Under it the domain keeps running on the
pooled fallback and part.n_pooled_only counts it, which is the same fact part.n_bootstrap_radius
counts from the assignment side."""


# ==================================================================================================
# THE RECORDS THIS PACKAGE RETURNS
#
# FROZEN DATACLASSES, the convention fabric/api.py's records follow, and for the reason the module
# header gives: a record that a consumer can WRITE is a second place the partition's numbers live,
# and this package's whole claim is that the books on the Partition are the single source of truth.
# EVERY FIELD IS NAMED IN THE MODULE HEADER'S RECORD TYPES BLOCK and no field is here that is not --
# an undeclared field is what tok/api.py's D-T3 was, and K11 reads the header, not the class.
# ==================================================================================================


@dataclasses.dataclass(frozen=True)
class Assignment:
    """One window's answer: which domain, and what happened on the way to it.

    `did` IS THE ONE NUMBER THIS PACKAGE EXPORTS and the loop must take its own `did` from it --
    memory provenance (MEM.write's `sources`), the expert-to-domain affiliation (FAB.forward's and
    FAB.observe's `domain_id`) and DOM.note_competence's `did` are all the same id under three
    spellings, and a loop that keeps a literal 0 makes all three see one source.

    `boundary` IS CONSUMED BACKWARDS: it is what resets the loop's windows_since_boundary, which
    SIG.cadence_due takes as a PREVIOUS-ITERATION value because the SIG row sits above this one.

    `spawned` AND `reentered` ARE NOT COMPLEMENTS AND BOTH ARE FALSE ON THE COMMON WINDOW. No
    boundary with a live current domain runs no assignment at all, so neither happened; reading
    `not spawned` as "re-entered" would count every ordinary window as a re-identification.
    """
    did: int
    boundary: bool
    spawned: bool
    reentered: bool


@dataclasses.dataclass(frozen=True)
class Plan:
    """What a management pass DECIDED. The spine carries it to MEM; this package touches no memory.

    THE FOLDS ARE ALREADY RESOLVED THROUGH part.merged. A domain folded into a survivor that is
    itself merged away later in the SAME pass must reach MEM as the FINAL survivor, or
    memory/api.py::apply_domain_plan relabels provenance onto an id that no longer exists -- and the
    relabel is silent, because a source id is an integer and every integer is a legal one.

    THE SIX COUNTS ARE THIS PASS'S. The cumulative ones are on part.counters and DOM.census reports
    those; a reader who cannot tell "this pass culled two" from "the run has culled two" cannot read
    either number, which is the distinction fabric/api.py::grow_check keeps between ask and delivery.
    """
    folds: dict
    deletions: tuple
    live: list
    merged: int
    culled: int
    folded: int
    held: int
    spared: int
    emptied: int


@dataclasses.dataclass(frozen=True)
class PartitionCensus:
    """The partition's whole reportable surface, in DOM'S OWN SPELLINGS.

    A NAMED COUNT FIELD IS None WHEN ITS COUNTER KEY IS ABSENT, NEVER 0, and that is the one
    load-bearing rule in this record. An absent key means the mechanism was UNREACHABLE on the arm
    this run took; a key present at 0 means it was armed and did not fire. Defaulting to 0 at the
    moment the report reads it would collapse the two states at the last possible place -- which is
    the collapse spine/gate.py::Gate exists to refuse, and the reason DOM_ENABLED=0, DOM_FOLD=0,
    DOM_CULL_RESPECTS_MEM_FLOOR=0 and FAB_COMP_PROTECT=0 are legible from this record alone.

    `boundaries` AND part.counters['part.n_boundaries'] ARE TWO DIFFERENT QUESTIONS AND BOTH TRAVEL.
    `boundaries` is part.nb, the BOUNDARY CLOCK, which is checkpointed and must not restart across a
    resume (open_partition says so at length); the counter is THIS RUN's count and rides the
    passthrough. A record carrying only one of them cannot answer both.

    `live` REACHES MEM AS live_sources AND `n_live` REACHES FAB AS live_domains. The renames live in
    spine/compose.py's `produces` column and not here: one record feeding two vocabularies is why
    "spell it as the consumer does" is not a function and cannot be a rule.
    """
    live: list
    n_live: int
    created: object
    capped: object
    merged: object
    culled: object
    folded: object
    held: object
    spared: object
    emptied: object
    boundaries: int
    windows: object
    visits: dict
    born: dict
    last: dict
    radius: dict
    pooled_radius: float
    comp_glob: object
    collapsed_at: object
    partition_off: bool
    counters: dict


# ==================================================================================================
# THE FOUR PRIVATE HELPERS EVERY BODY IN THIS FILE GOES THROUGH
# ==================================================================================================


def _bump(part, name, by=1):
    """Cumulative DID IT FIRE arithmetic, in one place so a counter cannot be seeded on one branch.

    `setdefault`-then-add rather than `get`-or-0 inside a branch, which is the rule
    fabric/api.py::_bump states and the defect sig/api.py::cadence_due carries the repair for: two
    lines that seeded a counter stood inside the else of the gate they described, so at the ONE
    configuration the tree ships the key was ABSENT for a whole run and the reading its own contract
    promised was a KeyError instead of the 0 it describes.
    """
    part.counters[name] = part.counters.get(name, 0) + by


def _seed(part, *names):
    """Declare these keys at 0 BEFORE the first branch, on the lever arm this call actually took.

    SEEDING IS THE DECLARATION OF WHICH ARM RAN. A key that is ABSENT says the mechanism was
    UNREACHABLE; a key present at 0 says it was armed and did not fire. So the seeds for the radius
    arm's counters go inside `accept_rule == "radius"` -- a LEVER arm, decided once at the top -- and
    never inside a runtime `if`, which would make "the population had no second centroid" read as
    "the margin rule is not installed".
    """
    for name in names:
        part.counters.setdefault(name, 0)


def _windows_of(now, where):
    """`now` as a plain count of WINDOWS, refusing any other clock kind BY NAME.

    COPIED IN ARGUMENT AND IN REASON FROM memory/api.py::_windows_of, not imported: O10 forbids this
    package to reach into another, and the hazard is identical. int() on a Clock is SILENT across
    kinds -- int(Steps(5)) is 5 -- which is the one hole spine/units.py cannot close, because
    __int__ has to exist for range() and slicing. Every clock this package compares `now` against is
    Windows: DOM_CULL_STALE and DOM_GRACE declare it, and part.born/part.last are stamped from this
    number, so a Flushes handed in here would make the cull's staleness test read
    batch_windows-fold short with nothing in any report saying so.
    """
    if isinstance(now, U.Clock) and not isinstance(now, U.Windows):
        raise U.UnitError(
            f"{where}: `now` arrived as {type(now).__name__} and every clock this package compares "
            f"it against is WINDOWS -- DOM_CULL_STALE, DOM_GRACE, DOM_SUSTAIN and DOM_MANAGE_EVERY "
            f"all declare U.Windows, and part.born/part.last are stamped from this same number. If "
            f"this conversion is real, name it in spine.derive and call it.")
    return int(now)


def _normalise(v):
    """A unit vector, with the clamp that keeps a zero vector from becoming a nan one.

    EVERY DISTANCE IN THIS PACKAGE IS 1 - cos AND THAT IS ONLY TRUE ON UNIT VECTORS. An unnormalised
    centroid makes `1 - (sig @ cent)` a number with no bounded range at all, so shift_dist,
    spawn_dist and merge_dist -- all three of which declare domain (0.0, 2.0) because they are
    compared against exactly this quantity -- would be compared against something else. The clamp is
    1e-8 rather than an if: a mean over a reservoir of antipodal windows is a legal zero vector, and
    a nan centroid poisons every later distance for the rest of the run.
    """
    return v / v.norm().clamp_min(1e-8)


class Partition:
    """The live domains and their books. Sparse by id, because ids are not indices.

    KEYED BY ID AND NOT BY POSITION. A domain's id is what every per-area score, the memory source
    census and the across-the-run-boundary comparison look it up by; a positional array would make
    those lookups shift the moment a domain is culled, which is the desynchronisation this project
    has already paid for once at the corpus level.

    THE RESERVOIR IS SAVED STATE, NOT A CACHE. The old blob reset `wins = {i: [] for i in cent}` on
    every restore with the note "sample windows are stream-local". They are not: the reservoir is
    the UNCENSORED SAMPLE the measured radius is estimated from, so discarding it puts every
    restored domain back on the pooled fallback radius until its next rekey -- on the resume that
    IS the continual-learning experiment.
    """

    __slots__ = ("cent", "reservoir", "size", "act", "born", "last", "visits", "bornb", "rad",
                 "tokc", "comp", "next_id", "merged", "cur", "run", "run_sig", "pend", "sh",
                 "nb", "radp", "comp_glob", "collapsed_at", "adj_hist", "slots", "sig_dim",
                 "vocab_slots", "counters", "rng")

    def __init__(self, *, sig_dim, vocab_slots, slots, device, rng):
        self.sig_dim, self.vocab_slots, self.slots = sig_dim, vocab_slots, slots
        self.cent = {}            # id -> (sig_dim,) tensor
        self.reservoir = {}       # id -> [window samples]  -- SAVED STATE, see the class docstring
        self.size = {}
        self.act = {}
        self.born = {}            # id -> the window this domain was created at
        self.last = {}
        self.visits = {}
        self.bornb = {}           # id -> the BOUNDARY clock at creation; see open_partition
        self.rad = {}
        self.tokc = {}            # id -> token histogram, the prior
        self.comp = {}
        self.next_id = 0
        self.merged = {}
        self.cur = -1
        self.run = 0
        self.run_sig = None
        self.pend = None
        self.sh = 0
        self.nb = 0               # THE BOUNDARY CLOCK -- must not restart across a resume
        self.radp = 0.0
        # None AND NOT 0.0, CHANGED 2026-09-17 WITH THE BODY THAT WRITES IT. note_competence's DID
        # IT FIRE line requires exactly this state -- "comp_glob is None until the first one lands,
        # which is the state in which competence protection cannot fire" -- and a 0.0 cannot say
        # it: competence here is a LOSS (lower is better; :3694 spares a domain on comp < comp_glob),
        # so a baseline seeded at zero reads as a population that models everything perfectly and no
        # domain could ever beat it. The protection would then be armed, inert, and indistinguishable
        # from one that ran. fabric/api.py::Population.__init__ made the identical change for the
        # identical field on the identical argument, and the two populations' books are compared.
        # state_dict and open_partition carry the None through rather than casting it.
        self.comp_glob = None
        self.collapsed_at = None
        self.adj_hist = []        # the adjacent-distance history behind the relative shift test
        self.counters = {}
        self.rng = rng

    # `device` IS DELIBERATELY NOT A FIELD. Nothing in this package allocates after construction
    # except from a centroid handed in by SIG, which already carries its own device -- storing one
    # here would be a second place a device can come from, and the two would be free to disagree.

    def _live(self):
        return sorted(self.cent)


def open_partition(dom: Config, *, sig_dim, vocab_slots, device, rng, restored=None):
    """Create an empty partition, or restore one from a checkpoint blob.

    `rng` is one spine.rng.Rng for the subsystem "domains". Two draws in this package were made
    from the global python `random` -- the reservoir replacement at :3500 and the pooled resample
    in _absorb at :3597 -- which makes draw order a coupling channel no wire declares and one the
    L3 sweep cannot tell from a lever leak.

    `restored` CARRIES EVERYTHING, which is the repair. The old blob saved cent/size/last/next_id/
    merged/cur/visits/bornb/nb/born/act/rad/radp and explicitly reset `wins = {i: [] for i in
    cent}` with the note "sample windows are stream-local". They are not: the reservoir is the
    UNCENSORED SAMPLE the measured radius is estimated from, so throwing it away means every
    restored domain re-enters on the pooled fallback until its next rekey. It also omitted
    comp/comp_glob (competence protection protects nothing after a resume), tokc (the prior
    histogram restarts empty while still being paid for every window) and the adjacent-distance
    history behind the relative shift test (M51). All four are now in the blob.

    THREE CLOCKS CROSS THE BOUNDARY AND THEY DO NOT AGREE ABOUT WHAT "RESTART" MEANS. `grace`
    re-arms on a restored domain, which is the conservative direction and stays. THE BOUNDARY CLOCK
    MUST NOT RESTART: at :4991 it did, and the fold would have swallowed every restored domain that
    had not happened to be re-entered twice since the resume. Same word, opposite consequence; the
    difference is which side of the comparison the reset lands on.

    LEVERS READ: none (nothing off `dom` directly -- see d_expert_slots under WIRES READ.
                 `enabled` and `reservoir` are consumed by observe, this package's own next entry
                 point and still a stub, and `prior_blend` by state_dict/prior/census, also stubs,
                 each of which already names it in its own LEVERS READ line; this line used to list
                 all three as if this function's body read them, and it never has -- DOM_ENABLED=0
                 builds the identical live Partition DOM_ENABLED=1 does, which is correct for THIS
                 entry point, an empty partition either way costing nothing to allocate, but was
                 not what the claim said)
    WIRES READ: d_expert_slots
    DID IT FIRE: part.n_opened, part.n_restored_domains
    """
    dom = dom.owned_by("DOM")
    slots = int(dom.d_expert_slots)   # WIRE READ HERE -- the domain id namespace bound
    part = Partition(sig_dim=int(sig_dim), vocab_slots=int(vocab_slots), slots=slots,
                     device=device, rng=rng)

    n_restored = 0
    if restored is not None:
        for key, blob in (restored.get("domains") or {}).items():
            i = int(key)
            part.cent[i] = torch.as_tensor(blob["cent"], dtype=torch.float32, device=device)
            # ALL FOUR OF THE OMITTED FIELDS COME BACK. The old blob dropped the reservoir, comp and
            # comp_glob, tokc, and the adjacent-distance history: competence protection protected
            # nothing after a resume, the prior histogram restarted empty while still being paid for
            # every window, and the relative shift test had no history to be relative to.
            part.reservoir[i] = [torch.as_tensor(x, dtype=torch.float32, device=device)
                                 for x in (blob.get("reservoir") or [])]
            part.size[i] = int(blob.get("size", 0))
            part.act[i] = float(blob.get("act", 0.0))
            part.born[i] = int(blob.get("born", 0))
            part.last[i] = int(blob.get("last", 0))
            part.visits[i] = int(blob.get("visits", 0))
            part.rad[i] = float(blob.get("rad", 0.0))
            part.tokc[i] = dict(blob.get("tokc") or {})
            part.comp[i] = float(blob.get("comp", 0.0))
            n_restored += 1
        part.next_id = int(restored.get("next_id", (max(part.cent) + 1) if part.cent else 0))
        part.merged = {int(k): int(v) for k, v in (restored.get("merged") or {}).items()}
        part.radp = float(restored.get("radp", 0.0))
        # THE None SURVIVES THE ROUND TRIP. A checkpoint taken before the first competence update
        # holds comp_glob = None, and `float(... or 0.0)` here would restore a baseline no window
        # ever measured -- which is precisely the reading the constructor's None exists to refuse,
        # arriving through the resume instead of through the build.
        _cg = restored.get("comp_glob")
        part.comp_glob = None if _cg is None else float(_cg)
        part.adj_hist = list(restored.get("adj_hist") or [])
        part.sh = int(restored.get("sh", 0))
        # THE BOUNDARY CLOCK MUST NOT RESTART, and this is the line the whole paragraph in the
        # docstring is about. `grace` re-arming above and `nb` restarting here are the SAME WORD
        # with opposite consequences: re-arming grace protects a restored domain, restarting nb
        # makes every restored domain look as though it has seen no boundaries, so the fold
        # swallows any that has not happened to be re-entered twice since the resume.
        part.nb = int(restored.get("nb", 0))
        # THE GRACE CLOCK RE-ARMS, AND IT MUST BE STAMPED AFTER nb IS RESTORED. Written above the
        # line that restores nb it read 0 against a restored boundary clock of 17, so every restored
        # domain entered already seventeen boundaries old -- grace EXPIRED rather than re-armed,
        # which is the opposite of the conservative direction. Found by printing both numbers.
        for i in part.cent:
            part.bornb[i] = int(part.nb)
        # `cur` IS RESTORED ONLY ON A CONTINUING RESUME. The current domain is a property of the
        # stream position: a resume that starts a new stream must not attribute its first window to
        # whatever the parent was in the middle of, and the root strips `position` for it. A
        # continuing mid-epoch resume (03b S0b) reads the parent's stream on from the same window, so
        # the position -- and the boundary clocks the grace re-arm above would otherwise reset --
        # comes back exactly.
        part.cur = -1
        part.run, part.run_sig, part.pend = 0, None, None
        _pos = restored.get("position")
        if _pos:
            part.cur = int(_pos.get("cur", -1))
            part.run = int(_pos.get("run", 0))
            _rs = _pos.get("run_sig")
            part.run_sig = None if _rs is None else torch.as_tensor(_rs, dtype=torch.float32,
                                                                   device=device)
            _pd = _pos.get("pend")
            part.pend = None if _pd is None else [
                torch.as_tensor(x, dtype=torch.float32, device=device) for x in _pd]
            for k, v in (_pos.get("bornb") or {}).items():
                if int(k) in part.cent:
                    part.bornb[int(k)] = int(v)
        # THE STREAM CONTINUES WHERE THE PARENT LEFT IT; see state_dict. A blob older than the key
        # keeps the freshly seeded stream.
        if restored.get("rng") and getattr(part, "rng", None) is not None:
            _state, _draws = restored["rng"]
            part.rng._r.setstate(_state)
            part.rng._draws = int(_draws)

    part.counters = {
        "part.n_opened": len(part.cent),
        "part.n_restored_domains": n_restored,
        "part.id_namespace": slots,
        "part.boundary_clock": part.nb,
    }
    return part


def _new(part, q, at):
    """Mint a domain at `q`, with every book opened at the same moment.

    EVERY BOOK OR NONE. fabric/api.py::grow_check records what the other half of this costs: grow()
    cleared use/comp/contrib and not ef/es, so a newborn inherited a dead expert's error history and
    could be culled by the failure route for something it never did (L30). The same books here feed
    the fold (visits, bornb), the cull (act, last, born) and the radius (rad, reservoir).

    part.comp IS DELIBERATELY NOT SEEDED. note_competence seeds it on the FIRST READING, and a
    competence of 0.0 would say this domain models its material perfectly -- competence here is a
    LOSS -- so brake two would spare it from the cull for ever, on a number no window measured.
    """
    i = int(part.next_id)
    # next_id ONLY EVER INCREASES, so a folded or culled id is never reused and `did` stays
    # resolvable for the whole chain. MEM's provenance depends on exactly that: an id that came back
    # under new ownership would silently relabel every entry the old owner wrote.
    part.next_id = i + 1
    part.cent[i] = q.clone()
    part.reservoir[i] = []
    part.size[i] = 0
    part.act[i] = 0.0
    part.last[i] = at
    part.born[i] = at
    part.rad[i] = 0.0
    part.visits[i] = 0
    part.bornb[i] = int(part.nb)
    _bump(part, "part.n_created")
    return i


def _touch(part, i, q):
    """Drift a centroid toward the query it just accepted (self_organize.py:3458).

    THE DRIFT IS WHAT rekey UNDOES AND RE-MEASURES, which is the whole reason a rekey is an event
    and not a cosmetic: between rekeys the centroid follows the material, and at a rekey it is
    recomputed from the uncensored reservoir instead.
    """
    part.cent[i] = _normalise(CENT_KEEP * part.cent[i] + (1.0 - CENT_KEEP) * q)


def _assign(part, q, at, *, accept_rule, spawn_dist, margin, slots):
    """Re-enter the nearest domain, absorb into it at cap, or mint a new one.

    -> (did, spawned, reentered). THREE EXCLUSIVE ARMS (self_organize.py:3504-3558), and the
    exclusivity is the repair: the old branch order let radius act as a SECOND acceptance test
    inside the relative branch (`if d1 <= DOM_MARGIN * d2 or (_r is not None and d1 <= _r)`,
    self_organize.py:3542), so DOM_RELATIVE=1 with DOM_RADIUS=1 was a fourth configuration nobody
    named. Here `margin` means margin alone, which domains/api.py::observe calls a real behavioural
    change to that arm and not a relabelling.
    """
    if not part.cent:
        return _new(part, q, at), True, False

    ids = part._live()
    sims = torch.stack([part.cent[i] for i in ids]) @ q
    j = int(sims.argmax())
    d1 = 1.0 - float(sims[j])

    if accept_rule == "radius":
        # THREE THRESHOLDS ON ONE ARM, AND TWO COUNTERS, BECAUSE THERE ARE THREE STATES. A measured
        # radius, the pooled radius rekey took over ALL domains' distances, and -- when no rekey has
        # ever measured anything -- DOM_SPAWN_DIST, which src/domains/levers.py::DOMLevers.spawn_dist
        # calls the bootstrap threshold every domain uses before its first rekey has measured a
        # radius. "Fell back to the pool" and "there is no pool" are not the same fact and one
        # counter cannot carry both.
        # `> 0.0` AND NOT `is not None`: part.rad and part.radp spell "not measured yet" as 0.0
        # (open_partition and state_dict both cast through float()), while part.comp_glob spells the
        # same thing as None on purpose. So a genuinely measured radius of exactly 0.0 is
        # indistinguishable from an unmeasured one here -- acceptable, because a quantile of
        # distances is positive unless every reservoir window encodes exactly onto its own centroid,
        # and said rather than left to be discovered.
        r = float(part.rad.get(ids[j], 0.0))
        if r <= 0.0:
            r = float(part.radp)
            if r > 0.0:
                _bump(part, "part.n_bootstrap_radius")
        if r <= 0.0:
            r = spawn_dist
            _bump(part, "part.n_bootstrap_spawn_dist")
        if d1 <= r:
            _touch(part, ids[j], q)
            _bump(part, "part.n_reentered")
            _bump(part, "part.n_reentered_by_radius")
            return ids[j], False, True
    elif accept_rule == "margin":
        if len(ids) < 2:
            # NO RUNNER-UP, SO NO ANSWER, SO A SPAWN. Under the enumeration the arms are exclusive,
            # so there is no radius or constant test to fall through to the way
            # self_organize.py:3540's `sims.numel() >= 2` guard did -- and a rule that asks whether
            # the nearest is decisively nearer than the second has nothing to compare against when
            # there is no second. Counted, because it is the whole behaviour of this arm on a
            # one-domain population and reads as "margin never fires" otherwise.
            _bump(part, "part.n_margin_no_runner_up")
        else:
            top2 = torch.topk(sims, 2)
            j = int(top2.indices[0])
            d1 = 1.0 - float(top2.values[0])
            d2 = 1.0 - float(top2.values[1])
            if d1 <= margin * d2:
                _touch(part, ids[j], q)
                _bump(part, "part.n_reentered")
                _bump(part, "part.n_reentered_by_margin")
                return ids[j], False, True
    elif d1 < spawn_dist:
        _touch(part, ids[j], q)
        _bump(part, "part.n_reentered")
        return ids[j], False, True

    if len(part.cent) >= slots:
        # AT CAP: ABSORBED INTO THE NEAREST, WITHOUT DRAGGING ITS CENTROID
        # (self_organize.py:3556-3557).
        # A forced far match must not pollute the cluster it lands in -- the id namespace is full, so
        # this window has to go somewhere, but _touch here would move a centroid toward material the
        # rule has already declared too far to belong to it. THIS IS THE ONE READ SITE OF
        # d_expert_slots in the package.
        _bump(part, "part.n_capped")
        return ids[j], False, True
    return _new(part, q, at), True, False


def observe(dom: Config, part, *, signature, sample_window, tokens, now):
    """One window. Detect a boundary, assign it, feed the reservoir, count the visit and the prior.

    Called ONCE PER WINDOW, above the batch early-out -- which is what makes `sustain` a Windows
    clock (`s.run` is incremented once per call, :3483).

    enabled == False returns did=0 for every window and does nothing else. THAT IS NOT A DEGENERACY
    MEM HAS TO DISCOVER: 0 is a real source id that MEM sees, and the report must say "the
    partition is off" rather than leaving the per-source floor to protect exactly one source in
    silence.

    THE BOUNDARY TEST IS ONE OF TWO EXCLUSIVE ARMS. `constant` trips at shift_dist. `relative`
    trips at shift_mult x the shift_q quantile of the last 512 adjacent distances. Neither is a
    boolean any more; an unrecognised value is a startup LeverError, which is the repair for the
    eleven-knob silent-else family (M24). A boundary requires `sustain` consecutive over-threshold
    windows, and THE PENDING SIGNATURES ARE AVERAGED into the assign query -- that smoothing is not
    a debounce, it is what fixed the over-segmentation, because a single raw window sits further
    from its own class mean than the spawn threshold and re-entry reliably spawned.

    ASSIGNMENT IS ONE OF THREE EXCLUSIVE ARMS: `radius` (this domain's own measured acceptance
    radius, with the pooled radius as the bootstrap before its first rekey), `margin` (nearest at
    most `margin` x runner-up), `constant` (spawn_dist alone). The old branch order let radius act
    as a SECOND test inside the relative branch, so DOM_RELATIVE=1 with DOM_RADIUS=1 was a fourth
    configuration nobody named; the enumeration makes `margin` mean margin alone, which is a real
    behavioural change to that arm and not a relabelling.

    At d_expert_slots domains the query is ABSORBED INTO THE NEAREST WITHOUT DRAGGING ITS CENTROID,
    and n_capped counts it -- a forced far match must not pollute the cluster it lands in.

    The reservoir is a TRUE reservoir: replacement with probability reservoir/size, drawn from
    part.rng. The rejected alternative (first-N-only) pinned each centroid to the domain's birth so
    that every rekey undid both the EMA drift and every merge.

    `sample_window` MUST BE THE SAME OBJECT SIG ENCODED, or a rekey does not reproduce the
    signature.

    LEVERS READ: enabled, shift_rule, shift_dist, shift_q, shift_mult, sustain, accept_rule,
                 spawn_dist, margin, reservoir, prior_blend
    WIRES READ: d_expert_slots
    DID IT FIRE: part.n_windows, n_boundaries, n_sustain_partial (runs that started and did not
                 reach sustain -- a detector firing on within-segment variation shows here first),
                 n_created, n_reentered, n_reentered_by_radius, n_reentered_by_margin, n_capped,
                 n_bootstrap_radius (assignments decided on the pooled fallback rather than a
                 measured radius: 0 of 143 domains ever learned one under the censored estimator,
                 so this counter is the evidence that the uncensored one works),
                 n_prior_accumulated
    SEVEN MORE KEYS THE BODY WRITES, DECLARED HERE FOR THE REASON fabric/api.py::grow_check gives: a
    key in the report that the contract does not admit to producing is the same defect as a declared
    key nothing writes, and the count is taken in both directions.
      part.n_off_windows -- windows taken on the DOM_ENABLED=0 arm. It is what makes "the partition
        is off" A NUMBER rather than an inference from the absence of every other key, which is what
        the paragraph above demands of the report and what no absence can say on its own: a run that
        never called observe at all has exactly the same absences.
      part.n_shift_bootstrap_constant -- windows on shift_rule="relative" decided against shift_dist
        because fewer than MIN_ADJ_SAMPLES adjacent distances had accumulated. The exact sibling of
        n_bootstrap_radius on the other test, and the only thing that separates "the relative rule
        fired" from "the relative rule was not calibrated yet". It is also why shift_dist is in the
        LEVERS READ line above on BOTH arms rather than on one.
      part.n_bootstrap_spawn_dist -- radius-arm assignments decided against spawn_dist because there
        was no measured radius AND no pooled radius either. "Fell back to the pool" and "there is no
        pool" are two states and n_bootstrap_radius carries one of them; collapsing them would say
        the pooled radius was in use on a run where rekey has never run at all.
      part.n_margin_no_runner_up -- margin-arm assignments with fewer than two live centroids, which
        the exclusive enumeration turns into a spawn. A rule that asks "is the nearest decisively
        nearer than the second" has no answer when there is no second, and the old branch order hid
        that by falling through to a radius test the enumeration has removed.
      part.n_reservoir_kept / part.n_reservoir_replaced -- the fill/churn pair. Both reading 0
        against a large n_windows is the readable form of DOM_RESERVOIR=0, under which rekey can
        never measure a radius for anything and every assignment runs on the bootstrap for ever.
      part.n_reservoir_ragged_dropped -- sample windows dropped for disagreeing in width with what
        this domain already holds. NOT AN ASSUMED-UNREACHABLE COUNTER:
        spine/compose.py::_sample_window clamps its start at 0 and returns a SHORT window early in
        the stream, so the ragged case is
        reachable from the root as it stands.
    """
    dom = dom.owned_by("DOM")
    slots = int(dom.d_expert_slots)   # WIRE READ HERE -- the at-cap absorb, and nowhere else

    # THE LEVERS, READ ONCE AND INTO BARE LOCALS. `sustain` declares units.Windows, so reading it
    # off the Config inside the comparison below would put a Clock-unit Attribute in an operand --
    # which is what tests/test_ownership.py::check_o11_no_unnamed_clock_arithmetic forbids and what
    # fabric/api.py::grow_check's own lever block avoids by exactly this means.
    enabled = bool(dom.enabled)
    shift_rule, shift_dist = str(dom.shift_rule), float(dom.shift_dist)
    shift_q, shift_mult = float(dom.shift_q), float(dom.shift_mult)
    sustain_n = int(dom.sustain)
    accept_rule, spawn_dist = str(dom.accept_rule), float(dom.spawn_dist)
    margin, res_n = float(dom.margin), int(dom.reservoir)
    blend = float(dom.prior_blend)
    now_n = _windows_of(now, "DOM.observe")

    # THE READ-SITE HALF OF THE M24 REPAIR, AND IT IS AT THE TOP RATHER THAN AT EACH DECISION.
    # `choices=` already refuses an unrecognised value at startup, so this can only fire on a Config
    # this package was handed by something that did not build it -- but it fires on the FIRST WINDOW
    # and names the legal values, where the same refusal written inside the threshold test would
    # first run on window two and the one inside the assignment only at a boundary. A lever that
    # takes a run down hundreds of windows in, at whichever branch happens to be reached first, is
    # the shape fabric/api.py::grow_check's ceiling repair was written against. Both enumerations
    # are then EXCLUSIVE if/elif/else below, with the last arm bare, because this is the one reader.
    if shift_rule not in ("constant", "relative"):
        raise LeverError(
            f"DOM_SHIFT_RULE={shift_rule!r} is not a boundary test this package implements. The two "
            f"legal values are 'constant' (trip at DOM_SHIFT_DIST) and 'relative' (trip at "
            f"DOM_SHIFT_MULT times the DOM_SHIFT_Q quantile of the recent adjacent distances). "
            f"There is no silent else here and there has not been one since M24: an unrecognised "
            f"value used to fall into whichever branch was written last, so a typo ran a "
            f"configuration nobody asked for while the log named the arm the operator meant.")
    if accept_rule not in ("radius", "margin", "constant"):
        raise LeverError(
            f"DOM_ACCEPT_RULE={accept_rule!r} is not a re-entry rule this package implements. The "
            f"three legal values are 'radius' (this domain's own measured acceptance radius, with "
            f"the pooled radius and then DOM_SPAWN_DIST as bootstraps), 'margin' (nearest at most "
            f"DOM_MARGIN times the runner-up) and 'constant' (DOM_SPAWN_DIST alone). They are "
            f"EXCLUSIVE: 'margin' means margin alone, which is a real behavioural change to that "
            f"arm and not a relabelling of the old branch order.")

    # ---- STEP 1: THE COUNTERS, BEFORE ANY BRANCH DECIDES ---------------------------------------
    # n_windows IS SEEDED ON BOTH ARMS because windows were observed whether or not the partition is
    # on; everything below it is seeded on the LEVER ARM this run took, which is the declaration of
    # which arm that was. Seeding an on-arm key on the off arm would say the mechanism was armed and
    # did not fire, when in fact it cannot be reached at all at DOM_ENABLED=0.
    _seed(part, "part.n_windows")
    _bump(part, "part.n_windows")
    if not enabled:
        # OFF, AND THE REPORT SAYS SO IN A NUMBER. 0 is a real source id that MEM sees, so leaving
        # this arm silent leaves MEM's per-source floor protecting exactly one source with nothing
        # anywhere explaining why. Every on-arm key stays ABSENT, which is this tree's spelling for
        # UNREACHABLE, and DOM.census's partition_off carries the sentence.
        _seed(part, "part.n_off_windows")
        _bump(part, "part.n_off_windows")
        return Assignment(did=0, boundary=False, spawned=False, reentered=False)

    _seed(part, "part.n_boundaries", "part.n_sustain_partial", "part.n_created",
          "part.n_reentered", "part.n_capped", "part.n_reservoir_kept",
          "part.n_reservoir_replaced", "part.n_reservoir_ragged_dropped")
    if accept_rule == "radius":
        _seed(part, "part.n_reentered_by_radius", "part.n_bootstrap_radius",
              "part.n_bootstrap_spawn_dist")
    elif accept_rule == "margin":
        _seed(part, "part.n_reentered_by_margin", "part.n_margin_no_runner_up")
    if shift_rule == "relative":
        _seed(part, "part.n_shift_bootstrap_constant")
    if blend > 0.0:
        # THE ACCUMULATION KEY IS SEEDED ON THE ACCOUNTING SWITCH AND WRITTEN ONLY HERE. Its pair
        # with part.n_prior_reads is the finding that the histogram was PAID FOR every window and
        # never READ, and that pair only reads as a pair while one of them counts windows and the
        # other counts calls -- see the note in domains/api.py::prior, which used to write this key
        # too and now reports it.
        _seed(part, "part.n_prior_accumulated")

    # ---- STEP 2: THE SIGNATURE, REDUCED TO ONE UNIT VECTOR -------------------------------------
    # ONE WINDOW PER CALL, AND AN (N, d) WITH N > 1 IS REFUSED RATHER THAN AVERAGED. This entry
    # point is called once per window, above the batch early-out -- that placement is what makes
    # `sustain` a Windows clock -- so a batch arriving here is a caller folding batch_windows
    # windows into one, which would divide every clock in this package by the batch width silently.
    # The refusal names the shape received and the width the partition was built at, which is the
    # same discipline sig/api.py::encode applies to a narrow window.
    sig = signature if torch.is_tensor(signature) else \
        torch.as_tensor(signature, dtype=torch.float32)
    _got = tuple(int(n) for n in sig.shape)
    if sig.dim() == 2 and int(sig.shape[0]) == 1:
        sig = sig[0]
    if sig.dim() != 1 or int(sig.shape[0]) != int(part.sig_dim):
        raise ValueError(
            f"DOM.observe was handed a signature of shape {_got} against a "
            f"partition built at sig_dim={int(part.sig_dim)}. ONE WINDOW PER CALL: the accepted "
            f"shapes are ({int(part.sig_dim)},) and (1, {int(part.sig_dim)}), and an (N, d) with "
            f"N > 1 is a caller folding a whole flush into one window -- which would advance "
            f"`run`, the boundary clock and every per-domain book once for batch_windows windows.")
    sig = _normalise(sig.detach().to(torch.float32))

    # ---- STEP 3: THE BOUNDARY TEST (self_organize.py:3461-3485) --------------------------------
    boundary = False
    if part.run_sig is None:
        # THE FIRST WINDOW OF A RUN HAS NO ADJACENT PAIR. It is not a boundary and it contributes no
        # adjacent distance: a distance against nothing would enter the relative rule's calibration
        # as a sample of something that was never measured.
        part.run_sig = sig.clone()
    else:
        # BOTH ARE UNIT VECTORS, so the dot IS the cosine and d runs to 2 -- which is why
        # shift_dist, spawn_dist and merge_dist all declare domain (0.0, 2.0) and not (0.0, 1.0).
        d = 1.0 - float(sig @ part.run_sig)
        if shift_rule == "constant":
            thr = shift_dist
        elif len(part.adj_hist) >= MIN_ADJ_SAMPLES:
            v = sorted(part.adj_hist)
            thr = max(1e-6, v[min(len(v) - 1, int(shift_q * len(v)))] * shift_mult)
        else:
            # THE RELATIVE ARM'S OWN BOOTSTRAP, counted rather than silent. Until the history is
            # calibrated this arm IS the constant arm, and a run shorter than MIN_ADJ_SAMPLES
            # windows reports the constant rule's behaviour under the relative rule's name unless
            # this key says how many of its decisions were taken that way.
            thr = shift_dist
            _bump(part, "part.n_shift_bootstrap_constant")
        # THE HISTORY IS APPENDED ON BOTH ARMS AND UNCONDITIONALLY (self_organize.py:3481-3482), and
        # this one line is the whole difference from the DROPPED DOM_ADAPTIVE estimator: that one
        # appended its sample only inside `if d < thr`, so the calibration was CENSORED at exactly
        # the threshold it existed to move and could only ever ratchet in one direction.
        part.adj_hist.append(d)
        if len(part.adj_hist) > ADJ_HIST_MAX:
            del part.adj_hist[:len(part.adj_hist) - ADJ_HIST_MAX]
        if d > thr:
            part.run += 1
            if part.pend is None:
                part.pend = []
            part.pend.append(sig)
            # part.sh IS THE CUMULATIVE COUNT OF OVER-THRESHOLD WINDOWS, and this is the only entry
            # point that can write it. It is a declared, CHECKPOINTED Partition field that no
            # docstring in the tree defines and nothing reads; state_dict persists exactly the
            # integers that must not restart across a resume, and the shift-candidate count is the
            # persisted partner of part.nb -- boundaries against the candidates that produced them.
            # part.counters are NOT checkpointed at all, which is why the same fact cannot simply
            # live there. THE OWNER MAY RULE OTHERWISE and this is the moment to: nothing else in
            # the tree can be broken by the choice, because nothing else reads the field.
            part.sh += 1
            boundary = part.run >= sustain_n
        else:
            if part.run > 0:
                # A RUN THAT STARTED AND WAS ABANDONED. This is the only place that fact exists: a
                # detector firing on within-segment variation shows here first, as sustain_partial
                # climbing while n_boundaries does not.
                _bump(part, "part.n_sustain_partial")
            part.run = 0
            part.pend = None
            part.run_sig = _normalise(RUN_SIG_KEEP * part.run_sig + (1.0 - RUN_SIG_KEEP) * sig)
        if boundary:
            # THE BOUNDARY CLOCK (self_organize.py:3485). It is what manage's recurrence horizon is
            # measured in and it must not restart across a resume, which open_partition is about.
            part.nb += 1
            _bump(part, "part.n_boundaries")

    # ---- STEP 4: ASSIGN (self_organize.py:3487-3492) -------------------------------------------
    # THE COMMON WINDOW RUNS NO ASSIGNMENT AT ALL -- no boundary, current domain still live -- so
    # `spawned` and `reentered` are both False and neither is the complement of the other.
    spawned = reentered = False
    if boundary or part.cur < 0 or part.cur not in part.cent:
        # THE SMOOTHING, AND IT IS NOT A DEBOUNCE. A single raw window sits further from its own
        # class mean than the spawn threshold, so re-entry reliably spawned; averaging the pending
        # signatures is what fixed the over-segmentation, and it is the reason `pend` exists at all
        # rather than the boundary being decided from a count.
        q = _normalise(torch.stack(part.pend).mean(0)) if part.pend else sig
        _prev = part.cur
        part.cur, spawned, reentered = _assign(
            part, q, now_n, accept_rule=accept_rule, spawn_dist=spawn_dist, margin=margin,
            slots=slots)
        part.run_sig = q.clone()
        part.run = 0
        part.pend = None
        if part.cur != _prev:
            # A SEPARATE ENTRY, NOT A RE-CONFIRMATION (self_organize.py:3492). This is the
            # operational definition `min_visits` is written against: "entered on at least this many
            # SEPARATE occasions". Counting every assignment would make a domain that the boundary
            # test keeps re-deciding into look permanently recurrent.
            part.visits[part.cur] = part.visits.get(part.cur, 0) + 1

    # ---- STEP 6: THE BOOKS (self_organize.py:3493) ---------------------------------------------
    cur = part.cur
    part.size[cur] = part.size.get(cur, 0) + 1
    part.act[cur] = part.act.get(cur, 0.0) + 1.0
    part.last[cur] = now_n

    # ---- STEP 7: THE RESERVOIR (self_organize.py:3496-3501) ------------------------------------
    # A TRUE RESERVOIR: replacement with probability reservoir/size, off part.rng and never off the
    # global python `random`. open_partition names this exact site (self_organize.py:3500) and
    # _absorb's resample as the two draws that made draw ORDER a coupling channel no wire declares
    # and one the L3 sweep cannot tell from a lever leak. The rejected alternative -- first-N-only --
    # pinned each centroid to the domain's BIRTH, so every rekey undid both the EMA drift and every
    # merge that had happened since.
    w = part.reservoir.setdefault(cur, [])
    # STORED AS A CPU TENSOR OF LONGS, WHICH IS THE SHAPE THE PERSISTENCE PAIR ALREADY READS:
    # state_dict writes `x.detach().cpu().tolist()` per element and open_partition reads it back.
    # `sample_window` is a bytes slice under sig.space == "bytes" (spine/compose.py::_sample_window
    # returns the unit stream at these bounds) and torch refuses a bytes object outright, so the
    # list() is load-bearing and not a copy for its own sake.
    win = sample_window.detach().to(device="cpu", dtype=torch.long) \
        if torch.is_tensor(sample_window) else \
        torch.as_tensor(list(sample_window), dtype=torch.long)
    if w and int(win.numel()) != int(w[0].numel()):
        # ONE LENGTH PER RESERVOIR. A ragged entry cannot be stacked at rekey, and sig/api.py::encode
        # refuses any width but the one frozen on SigState -- so keeping it would move the failure
        # to a later call, in another package, with no record of which window it came from.
        _bump(part, "part.n_reservoir_ragged_dropped")
    elif len(w) < res_n:
        w.append(win)
        _bump(part, "part.n_reservoir_kept")
    elif res_n > 0 and part.rng.random() < res_n / float(max(1, int(part.size.get(cur, 1)))):
        w[part.rng.randrange(res_n)] = win
        _bump(part, "part.n_reservoir_replaced")

    # ---- STEP 8: THE PRIOR (self_organize.py:6788-6791) ----------------------------------------
    # `blend` IS READ HERE AND RETURNED BY DOM.prior, WHICH IS WHAT STOPS THE TWO DRIFTING. It was
    # one field doing two jobs -- the training-side accounting switch that turns this accumulation
    # on, and the mixing weight at eval -- and nothing said they had to agree.
    # ALL OF `tokens`, NOT w[:-1]. The frozen tree excluded the trailing element because its window
    # carried the next-token target; spine/compose.py::_window_bounds hands over exactly LM.ctx ids
    # with no target appended, so an exclusion here would silently drop one id per window from every
    # histogram in the population.
    if blend > 0.0 and tokens is not None:
        h = part.tokc.setdefault(cur, {})
        for t in (tokens.tolist() if torch.is_tensor(tokens) else tokens):
            t = int(t)
            h[t] = h.get(t, 0) + 1
        # ONCE PER WINDOW, NOT ONCE PER TOKEN: the pair this key forms with part.n_prior_reads is
        # windows-paid against calls-served, and a per-token count would make the ratio LM.ctx-fold
        # meaningless.
        _bump(part, "part.n_prior_accumulated")

    return Assignment(did=int(part.cur), boundary=bool(boundary), spawned=bool(spawned),
                      reentered=bool(reentered))


def rekey(dom: Config, part, *, encode):
    """Re-encode every reservoir, recompute every centroid, and re-measure every acceptance radius.

    `encode` is SIG.encode, passed in. THIS IS AN EVENT THE SPINE DELIVERS, NOT A CADENCE THIS
    PACKAGE OWNS: the cadence is MEM's rekey_every and the arm test is SIG's mode == "learned", and
    both were read directly from inside the domain block at self_organize.py:6688-6689 -- two
    foreign reads in one line.

    THE RADIUS IS FREE HERE -- rekey has already encoded the reservoir, so the distances exist
    before the quantile is taken. radius = radius_mult x the radius_q quantile of d(reservoir
    window, own centroid), for domains holding at least four samples; the POOLED radius is the same
    quantile over ALL domains' distances and is what a domain uses before its own first rekey.
    radius_cap then bounds every radius at that multiple of the distance to the nearest OTHER
    centroid, because a radius that absorbs one foreign window measures a larger spread and absorbs
    more (observed reaching 1.24 of a maximum possible 2.0). radius_cap == 0 removes the guard and
    is a real arm. NOTE M32: at radius_cap=2.0 a region reaches TWICE as far as its neighbour's
    centroid, so the guard does not enforce the non-overlap its docstring claims -- 2.0 stays as a
    runaway bound and the claim comes out of the docstring.

    LEVERS READ: radius_q, radius_mult, radius_cap, reservoir
    WIRES READ: none
    DID IT FIRE: part.n_rekey_passes, n_radius_measured, n_radius_capped_voronoi, n_pooled_only
    FIVE MORE KEYS THE BODY WRITES, DECLARED HERE FOR THE REASON fabric/api.py::grow_check gives: a
    key in the report that the contract does not admit to producing is the same defect as a declared
    key nothing writes, and the count is taken in both directions.
      part.n_rekey_domains -- domains whose reservoir was re-encoded this pass.
      part.n_rekey_windows -- reservoir windows encoded, i.e. what the pass COST. It is the only
        number that says whether a rekey is affordable at the cadence it is being asked for.
      part.n_rekey_empty -- passes that ran with no reservoir window anywhere. A rekey that measured
        nothing and a rekey that never happened read identically without it, and at
        DOM_RESERVOIR=0 this is the only key on this entry point that ever moves.
      part.n_radius_from_cap_only -- domains whose radius IS the Voronoi cap and was never measured.
        Seeded only when radius_cap > 0, because at 0 the guard is gone and the state cannot exist.
        The frozen tree ASSIGNS the cap to a domain that has no measurement, so after a guarded
        rekey every live domain has a radius and only some of them have a MEASURED one -- folding
        those two into n_radius_measured would say 143 domains learned a radius when none did.
      part.n_rekey_reservoir_size -- the value of `reservoir`, SET and not bumped, printed beside
        n_radius_measured because that size sets the RESOLUTION of radius_q: at 40 windows the 0.85
        quantile is the 34th value, so shrinking the reservoir quietly coarsens every radius in the
        population. It is the fab.cap_lift_period pattern -- a read that REPORTS rather than decides.
    """
    dom = dom.owned_by("DOM")
    rq, rmult = float(dom.radius_q), float(dom.radius_mult)
    rcap, res_n = float(dom.radius_cap), int(dom.reservoir)

    # ---- STEP 1: THE COUNTERS, BEFORE ANY BRANCH DECIDES ---------------------------------------
    _seed(part, "part.n_rekey_passes", "part.n_radius_measured", "part.n_pooled_only",
          "part.n_rekey_domains", "part.n_rekey_windows", "part.n_rekey_empty")
    _bump(part, "part.n_rekey_passes")
    if rcap > 0.0:
        # radius_cap == 0 REMOVES THE GUARD AND IS A REAL ARM (the calibration table at
        # src/domains/levers.py::DOMLevers.radius_cap shows it inert on healthy geometry), so on
        # that arm both of these keys are ABSENT rather than 0 -- the guard is not installed, not
        # installed and idle.
        _seed(part, "part.n_radius_capped_voronoi", "part.n_radius_from_cap_only")
    part.counters["part.n_rekey_reservoir_size"] = res_n

    # ---- STEP 2: THE ENCODE (self_organize.py:3560-3568) ---------------------------------------
    # TRIMMED TO `reservoir` BEFORE ENCODING, DETERMINISTICALLY AND WITH NO RNG DRAW. A merge pools
    # two reservoirs and resamples to res_n, but a resume that LOWERS DOM_RESERVOIR restores lists
    # longer than the new size, and encoding them would charge the pass for windows the operator has
    # asked not to keep. The last res_n are kept rather than a sample: a third draw site would make
    # this package's rng order depend on the rekey cadence, and open_partition names exactly TWO
    # draw sites as the coupling channel no wire declares.
    # `res_n > 0` GUARDS THE TRIM, AND WITHOUT IT THIS LINE DESTROYS SAVED STATE. At
    # DOM_RESERVOIR=0 an unguarded `w[len(w) - res_n:]` is `w[len(w):]`, i.e. the empty list, so a
    # resume that lowered the lever to zero would ERASE the restored reservoirs -- the exact loss
    # Partition's own docstring is about ("THE RESERVOIR IS SAVED STATE, NOT A CACHE"), arriving
    # through a trim instead of through a restore. Driven at that configuration before the guard
    # went in, and it did worse than erase: `ids` was taken BEFORE the trim, so every emptied
    # domain was still in it and the centroid loop raised KeyError on the first one.
    if res_n > 0:
        for i in part._live():
            w = part.reservoir.get(i)
            if w and len(w) > res_n:
                part.reservoir[i] = w[len(w) - res_n:]

    # ids IS TAKEN AFTER THE TRIM, so it names the domains that still have a sample to encode and
    # not the ones that had one before this pass edited them.
    ids = [i for i in part._live() if part.reservoir.get(i)]
    if not ids:
        # THE PASS RAN AND MEASURED NOTHING, which is a different fact from the pass not happening.
        # part.radp is left exactly as it was: overwriting it with a zero here would disarm both of
        # manage's fold fail-safes on the strength of one empty pass.
        _bump(part, "part.n_rekey_empty")
        return None

    # ONE ENCODE CALL PER WIDTH GROUP. The frozen tree makes one call for all domains; grouping is
    # what keeps one odd-width domain from taking the run down with it -- and it does NOT dodge
    # sig/api.py::encode's width refusal, because a group of the wrong width still raises, by
    # design. The grouping is per WINDOW and not per domain because _absorb pools two reservoirs
    # without a width check, so one domain can legally hold two widths after a merge.
    groups = {}
    for i in ids:
        for x in part.reservoir[i]:
            groups.setdefault(int(x.numel()), []).append((i, x))
    rows, n_windows = {}, 0
    for _width in sorted(groups):
        items = groups[_width]
        # HANDED OVER AS LISTS OF INTS. SIG.encode does torch.as_tensor(windows, dtype=torch.long)
        # only for a NON-tensor input, and open_partition restores reservoir windows as
        # torch.float32 -- so passing a restored tensor straight through would put a float tensor
        # into nn.Embedding, which fails in SIG with nothing naming this package.
        z = encode([x.tolist() for _, x in items])
        for (i, _), row in zip(items, z):
            rows.setdefault(i, []).append(row)
        n_windows += len(items)
    _bump(part, "part.n_rekey_domains", len(ids))
    _bump(part, "part.n_rekey_windows", n_windows)

    # ---- STEP 3: CENTROID AND RADIUS, PER DOMAIN (self_organize.py:3570-3575) -------------------
    # THE CENTROID IS OVERWRITTEN AND NOT DRIFTED. observe's EMA touch and this are two writers of
    # one field and THIS ONE IS THE AUTHORITY: the drift follows whatever arrived, and this is the
    # re-measurement from the uncensored sample that undoes it.
    _all = []
    for i in ids:
        zi = torch.stack(rows[i])
        c = _normalise(zi.mean(0))
        part.cent[i] = c
        di = 1.0 - (zi @ c)
        _all.append(di)
        n = int(di.numel())
        if n >= MIN_RADIUS_SAMPLES:
            # THE RADIUS IS FREE HERE: the reservoir has just been encoded, so the distances exist
            # before the quantile is taken. kthvalue and not torch.quantile, because a quantile
            # INTERPOLATES between two order statistics and this one must be a distance the domain
            # actually produced -- an interpolated radius on four samples is a number no window
            # measured.
            k = max(1, min(n, int(round(rq * n))))
            part.rad[i] = float(di.kthvalue(k).values) * rmult
            _bump(part, "part.n_radius_measured")
        else:
            # LEFT AT WHATEVER IT WAS -- 0.0 at birth, 0.0 after an absorb -- so the domain keeps
            # running on the pooled fallback, which is exactly what n_bootstrap_radius counts on the
            # assignment side. The two keys are the same fact seen from the two ends.
            _bump(part, "part.n_pooled_only")

    # ---- STEP 4: THE POOLED RADIUS (self_organize.py:3575) -------------------------------------
    # THE SAME QUANTILE OVER ALL DOMAINS' DISTANCES. It is what a domain uses before its own first
    # rekey has measured anything, and what manage's fold fail-safe is measured in -- which is why
    # it is taken over the pool and not averaged from the per-domain radii: a mean of radii would be
    # dominated by whichever domains happened to have enough samples to get one.
    part.radp = float(torch.quantile(torch.cat(_all), rq)) * rmult

    # ---- STEP 5: THE VORONOI GUARD (self_organize.py:3583-3588) --------------------------------
    # NOTE M32, WHICH THIS BODY MUST NOT QUIETLY REPAIR: at radius_cap=2.0 a region reaches TWICE as
    # far as its neighbour's centroid, so this is a RUNAWAY BOUND and not the non-overlap guarantee
    # the old docstring claimed. The claim came out of the contract; the number stays, because the
    # calibration table shows 2.0 in the flat region and 0.5 strangling the radius back to the
    # baseline the mechanism exists to fix.
    if rcap > 0.0 and len(part.cent) > 1:
        ids2 = part._live()
        C2 = torch.stack([part.cent[i] for i in ids2])
        M = C2 @ C2.T
        M.fill_diagonal_(-2.0)
        nn_d = 1.0 - M.max(1).values
        for k, i in enumerate(ids2):
            cap = rcap * float(nn_d[k])
            if float(part.rad.get(i, 0.0)) <= 0.0:
                # THE CAP BECOMES THE RADIUS OF A DOMAIN THAT HAS NONE, which is what the frozen
                # tree does -- so after a guarded rekey EVERY live domain has a radius and only some
                # of them have a MEASURED one. That is why this is a separate key from
                # n_radius_capped_voronoi: one is the guard bounding a measurement, the other is the
                # guard standing in for one that was never taken.
                part.rad[i] = cap
                _bump(part, "part.n_radius_from_cap_only")
            elif cap < part.rad[i]:
                part.rad[i] = cap
                _bump(part, "part.n_radius_capped_voronoi")
        if part.radp > 0.0:
            # THE POOLED RADIUS IS BOUNDED AT THE MEDIAN NEAREST-NEIGHBOUR DISTANCE rather than at
            # any one domain's, because it is the number domains with no measurement of their own
            # use -- capping it by a single pair's geometry would let the closest pair in the
            # population decide the bootstrap for every newborn.
            part.radp = min(part.radp, rcap * float(nn_d.median()))
    return None


def note_competence(dom: Config, part, *, did, bits):
    """Fold this window's bits/window into the domain's competence EMA and the population's.

    Separate from observe() because the number is only known AFTER the forward pass, later in the
    flush. THE EMA RATE IS THE WIRE d_comp_ema AND NOT AN ARGUMENT: FAB owns the number (the
    fabric's cull and spare rules are where it was first needed), and inventing a lever here would
    put a second answer to "how fast does competence move" in the tree while the report compares
    the two series.

    Competence is the term that lets a rarely-fed domain survive on being GOOD at what it does get
    -- rare-and-stale is exactly what a NICHE domain looks like from a utilization-only vantage
    point, and it is also what a DEAD one looks like.

    LEVERS READ: none (this is state maintenance whose rate arrives as a wire, d_comp_ema below)
    WIRES READ: d_comp_ema
    DID IT FIRE: part.n_competence_updates; comp_glob is None until the first one lands, which is
                 the state in which competence protection cannot fire, and the Gate says so
    """
    dom = dom.owned_by("DOM")
    rate = float(dom.d_comp_ema)  # WIRE READ HERE -- one smoothing rate for both populations
    did = int(did)
    # ONE WINDOW'S READING, AND A BATCH MEAN IS REFUSED RATHER THAN AVERAGED. The row that drives
    # this says "bits from the per-window loss", and LM.lm_loss keeps reduction='none' precisely so
    # the per-window vector survives -- "competence attribution, the domain EMA and the marginal-
    # contribution counterfactual all read them and not one of them can be tracked from a scalar".
    # A caller handing the flush mean here would fold one number into the EMA where BATCH_W windows
    # belong, at 1/BATCH_W of the rate the report says the EMA moves at, and the only trace would be
    # a competence series that lags for a reason nobody can see.
    if isinstance(bits, torch.Tensor):
        if bits.numel() != 1:
            raise ValueError(
                f"DOM.note_competence: `bits` holds {int(bits.numel())} values and this call folds "
                f"ONE window's reading into ONE domain's EMA. A per-window vector is a loop over "
                f"this call, one `did` at a time -- averaging it here would attribute a whole "
                f"batch's windows to whichever domain the last one landed in.")
        bits = float(bits.detach())
    bits = float(bits)
    if bits != bits or bits in (float("inf"), float("-inf")):
        # REFUSED, NOT FOLDED. A nan entering an EMA is permanent: every later update multiplies it
        # forward, so one bad window silently ends competence protection for the rest of the run and
        # for every run resumed from the checkpoint that saved it.
        raise ValueError(
            f"DOM.note_competence: `bits` is {bits!r} for domain {did}. An EMA that takes one nan "
            f"or inf never recovers -- it would disable the competence spare for the rest of this "
            f"run and for every resume from it -- so this is refused at the one place it enters.")
    # THE UNIT IS THE CALLER'S AND THIS CALL DOES NOT CONVERT. `bits` is folded exactly as handed
    # over, and comp is only ever compared against comp_glob, which is fed from this same argument,
    # so the comparison is unit-consistent whatever the caller supplies. What is NOT free is the
    # NAME: LM.lm_loss's per-window value is in NATS, and a report that prints this series as
    # bits/window without the caller dividing by ln(2) is the wrong-measurement class this tree
    # rates worst. Converting here instead would be worse -- it would silently rescale a caller who
    # had already converted -- so the obligation is stated and left with the one caller that knows.

    if did not in part.cent:
        # A DOMAIN THE PARTITION DOES NOT HOLD, AND IT IS LEGAL. DOM.observe returns did=0 for every
        # window at DOM_ENABLED=0 -- "0 is a real source id that MEM sees" -- so the off-partition
        # run folds a whole run's competence into one book that has no centroid. Counted rather than
        # refused, because refusing would make the partition-off configuration crash, and counted
        # separately rather than silently, because a nonzero here on an ENABLED partition means
        # something is scoring windows against ids the assignment never produced.
        part.counters["part.n_competence_no_centroid"] = part.counters.get(
            "part.n_competence_no_centroid", 0) + 1

    prev = part.comp.get(did)
    if prev is None:
        # SEEDED ON THE FIRST READING, NOT DECAYED FROM A ZERO -- FAB.observe's rule for the same
        # book ("an EMA decayed from a zero would credit every newborn with a perfect competence it
        # never earned"), and here the zero would be worse than in the fabric: a domain's competence
        # is a LOSS, so a book seeded at 0.0 says this domain predicts its material perfectly and
        # the cull's competence spare would protect it on its first window for ever.
        part.comp[did] = bits
        part.counters["part.n_competence_seeded"] = part.counters.get(
            "part.n_competence_seeded", 0) + 1
    else:
        part.comp[did] = (1.0 - rate) * float(prev) + rate * bits

    # THE POPULATION BASELINE, AT THE SAME RATE AND FROM THE SAME READINGS. Two rates would make
    # "this domain is better than the population" a comparison between two differently smoothed
    # series, which is the whole argument for d_comp_ema being a wire from FAB rather than a lever
    # here. None until the first one lands: that is the state in which competence protection cannot
    # fire, and part.n_competence_updates below is how a reader tells it from a baseline that
    # happens to read zero.
    part.comp_glob = bits if part.comp_glob is None else \
        (1.0 - rate) * float(part.comp_glob) + rate * bits
    part.counters["part.n_competence_updates"] = part.counters.get(
        "part.n_competence_updates", 0) + 1
    part.counters["part.n_competence_domains"] = len(part.comp)
    # NOTHING IS RETURNED. The books ARE the product -- they live on the Partition every later
    # reader already holds -- and a record here would be a second copy of numbers whose single
    # source of truth is the point of this design (FAB.observe's row says the same, and for the
    # same reason its LOOP_ORDER row has no `produces` column).
    return None


_BOOKS = ("cent", "reservoir", "size", "act", "born", "last", "visits", "bornb", "rad", "tokc",
          "comp")
"""Every per-domain book, named ONCE, so a domain leaves the partition from all of them together.

THE LIST IS HERE AND NOT SPELLED OUT AT THE THREE SITES THAT REMOVE A DOMAIN (the fold's absorb, the
empty-cull and the activity cull) for the reason fabric/api.py::grow_check records about the other
direction: a birth that cleared use/comp/contrib and not ef/es left a newborn carrying a dead
expert's error history (L30). A removal that misses one book leaves the id in `_live()`'s complement
but still holding a reservoir a later rekey will encode, or a `last` a later cull will test.
part.merged is NOT in the list on purpose -- it is the chain a folded id is resolved THROUGH, so
dropping the entry would break the resolution Plan.folds depends on."""


def _drop(part, d):
    """Remove one domain from every per-domain book. It does NOT touch part.merged."""
    for book in _BOOKS:
        getattr(part, book).pop(d, None)


def _resolve(part, i):
    """Follow the merge chain to the id that is actually alive.

    A DOMAIN FOLDED INTO A SURVIVOR THAT IS ITSELF MERGED AWAY LATER IN THE SAME PASS must reach MEM
    as the FINAL survivor. memory/api.py::apply_domain_plan relabels provenance onto whatever id the
    plan names, and a source id is an integer, so relabelling onto an id that no longer exists fails
    nowhere and is visible only as entries filed under a domain the partition has never heard of.
    THE WALK IS BOUNDED BY THE CHAIN'S OWN LENGTH rather than by `while True`: part.merged is
    restored from a checkpoint, so a corrupt blob with a cycle in it would otherwise hang the run
    instead of failing it.
    """
    seen = 0
    limit = len(part.merged) + 1
    while i in part.merged and seen < limit:
        i = part.merged[i]
        seen += 1
    return i


def _count_for(memory_counts, did):
    """How many memory entries MEM's census attributes to this domain. Tolerates both containers.

    TWO SHAPES, BECAUSE MEM'S TABLE IS NOT A MAPPING AND THE RECORD DOES NOT SAY IT IS. MEM's census
    table is store.nsrc, a TENSOR indexed by source id that grows on demand, while memory/api.py's
    RECORD TYPES block documents the field only as "the per-source table". So this reads it as a
    mapping when it has .get and as a sequence with an EXPLICIT bounds check otherwise.
    AN ID PAST THE END IS 0, NEVER THE LAST BUCKET. memory/api.py::apply_domain_plan states the same
    rule for its own side -- the census is grown, never clamped -- and a clamp here would attribute
    some other domain's entry count to a newborn, which is precisely the number brake one refuses a
    cull on.
    """
    if memory_counts is None:
        return 0
    get = getattr(memory_counts, "get", None)
    if callable(get):
        return int(get(did, 0) or 0)
    try:
        n = len(memory_counts)
    except TypeError:
        return 0
    if did < 0 or did >= n:
        return 0
    return int(memory_counts[did])


def _absorb(part, a, b, *, res_n):
    """Fold `b` into `a` (self_organize.py:3591-3607). The ONE routine fold and merge share.

    ONE ROUTINE AND NOT TWO, because the two callers differ only in how they CHOSE the pair. Two
    bodies would be two chances to disagree about what an absorb is, and the disagreement would show
    up as a population whose books depend on which rule happened to collapse the pair.

    THE RESERVOIRS POOL AND ARE RESAMPLED, which is what gives the survivor a SECOND segment -- that
    is what turns a segment prototype into a domain prototype, and it is the change behind the
    population becoming intensive rather than growing with stream length. The resample is the second
    of this package's two rng draw sites; open_partition names both (self_organize.py:3500 and
    self_organize.py:3597) as a coupling channel no wire declares.

    `rad` IS RESET TO 0.0 rather than averaged: the survivor is a different shape from either
    parent, so its acceptance radius has to be RE-MEASURED by the next rekey and not interpolated
    between two measurements of clusters that no longer exist.
    """
    na, nb_ = int(part.size.get(a, 0)), int(part.size.get(b, 0))
    part.cent[a] = _normalise((part.cent[a] * na + part.cent[b] * nb_) / max(1, na + nb_))
    part.size[a] = na + nb_
    part.act[a] = part.act.get(a, 0.0) + part.act.get(b, 0.0)
    part.visits[a] = part.visits.get(a, 0) + part.visits.get(b, 0)
    # THE COUNTS FOLLOW THE MERGE, THE WAY MEMORY DOES. A histogram left behind would make DOM.prior
    # return the survivor's pre-merge distribution for material it has just taken ownership of.
    ha = part.tokc.setdefault(a, {})
    for t, c in (part.tokc.get(b) or {}).items():
        ha[t] = ha.get(t, 0) + c
    pool = list(part.reservoir.get(a) or []) + list(part.reservoir.get(b) or [])
    part.reservoir[a] = part.rng.sample(pool, res_n) if len(pool) > res_n else pool
    part.last[a] = max(int(part.last.get(a, 0)), int(part.last.get(b, 0)))
    part.born[a] = min(int(part.born.get(a, 0)), int(part.born.get(b, 0)))
    part.bornb[a] = min(int(part.bornb.get(a, 0)), int(part.bornb.get(b, 0)))
    part.rad[a] = 0.0
    _drop(part, b)
    part.merged[b] = a


def _frozen_plan(part):
    """The Plan a REFUSED management call returns: the population exactly as it stands.

    THE LIVE LIST IS STILL REAL AND THE SIX COUNTS ARE STILL ZERO. A refused call has decided
    nothing, so `folds` and `deletions` are empty -- but `live` is what MEM.apply_domain_plan takes
    as live_sources and what decides which source ids are eligible for floor protection, and an
    empty one there would make every source in the store ineligible on exactly the configuration
    (DOM_MANAGE=0) that was chosen to leave the population alone.
    """
    return Plan(folds={}, deletions=(), live=part._live(), merged=0, culled=0, folded=0, held=0,
                spared=0, emptied=0)


def manage(dom: Config, part, *, now, memory_counts, mem_floor_entries):
    """Fold, merge, cull -- on the management cadence -- and RETURN A PLAN for the spine to hand to
    MEM.

    manage == False freezes the population and returns an empty plan. manage_every == 0 means
    NEVER, BEHIND A GUARD AT THIS READ SITE -- the old `step % DOM_MANAGE_EVERY` had no max(1, ...)
    and three DID IT FIRE rows printed "DOM_MANAGE_EVERY=0" as their disarm reason for a value that
    raises ZeroDivisionError on the first flush. A lever cannot check its own reader; this is the
    reader.

    ORDER IS FIXED AND IS THE MECHANISM: fold, then empty-cull, then merge, then the activity cull.

    FOLD. A domain entered on fewer than min_visits SEPARATE occasions, and past recur_horizon
    BOUNDARIES since its birth, is folded into its nearest neighbour -- unless it is further than
    fold_mult x the pooled radius (leave it standing) or there is no pooled radius yet (also leave
    it standing; an unbounded fold collapses the whole population to one domain). This is the
    change that made the population INTENSIVE: 4 live against a truth of 4, and 4 -> 4 -> 4 at
    120/240/480 segments where constants alone gave 64 -> 116 -> 193.

    MERGE. Every pair under merge_dist collapses, the more ACTIVE surviving. THE RESERVOIRS POOL
    and are resampled to `reservoir` -- pooling is what gives the survivor a second segment, which
    is what turns a segment prototype into a domain prototype. `rad` is reset so the next rekey
    re-measures it.

    CULL. A domain is culled only when ALL of: it is in the bottom cull_frac by decayed activity
    (int(cull_frac * n), WITH NO max(1, ...) -- that floor turned "cull at most a tenth" into "cull
    at least one, every pass, forever" and ratcheted a population to a single domain three separate
    times); act < cull_act_min; now - last > cull_stale; now - born >= grace; and neither brake
    holds. BRAKE ONE is cull_respects_mem_floor: memory_counts[did] >= mem_floor_entries refuses
    the cull, because MEM's floor forbids EVICTING those entries and deleting them is the bigger
    action on the weaker test. It self-releases -- once eviction has genuinely drained the domain
    it falls below the floor. BRAKE TWO is the wire d_comp_protect. `act` is then decayed by
    `decay`, once per pass.

    `mem_floor_entries` IS AN ARGUMENT AND CANNOT BE A WIRE: the floor is
    src_share * capacity / live_eligible_sources and the divisor is LIVE STATE (125 sources holding
    entries against 27 live domains on a measured run, a 4.6x swing). domains/levers.py calls it
    d_mem_floor_entries; this contract records that as a deliberate departure with its reason -- a
    wire quietly recomputed at the call site is self_organize.py:3688 under a new name.

    LEVERS READ: manage, manage_every, merge_dist, cull_frac, cull_act_min, cull_stale, decay,
                 grace, cull_respects_mem_floor, fold, min_visits, recur_horizon, fold_mult,
                 reservoir
    WIRES READ: d_comp_protect
    DID IT FIRE: part.n_manage_passes, n_merged, n_culled, n_folded, n_emptied,
                 n_held_by_mem_floor (THE BRAKE THAT WAS MISSING ENTIRELY, and the one goal B
                 depends on), n_spared_by_competence, n_fold_refused_far,
                 n_fold_refused_no_pooled_radius, n_cull_budget_zero, n_grace_skips -- EACH BRAKE
                 HAS ITS OWN COUNTER, because the cull had one and its brakes had none: a run could
                 delete its way to one domain with every guard either off or never reached and the
                 audit would show only "domains.cull 145"
    SEVEN MORE KEYS THE BODY WRITES, DECLARED HERE FOR THE REASON fabric/api.py::grow_check gives: a
    key in the report that the contract does not admit to producing is the same defect as a declared
    key nothing writes, and the count is taken in both directions.
      part.n_manage_calls -- how many times this entry point was CALLED, against n_manage_passes,
        which is how many times it actually reached the population. Without the pair, DOM_MANAGE=0
        and "the spine never called manage" read identically, which is the distinction
        RunResult.skipped exists to make and fab.grow_checks is the sibling of.
      part.n_manage_refused_off -- calls refused by DOM_MANAGE=0.
      part.n_manage_refused_never -- calls refused by DOM_MANAGE_EVERY=0 AT THIS READ SITE. This key
        existing is the evidence that the guard the paragraph above demands is present: the old
        reader had no max(1, ...) and three DID IT FIRE rows printed a disarm reason for a value
        that raises ZeroDivisionError on the first flush.
      part.n_cull_candidates -- domains inside the budget slice that were actually examined.
      part.n_cull_refused_activity -- candidates that failed the act/stale conjunct. Without it a
        pass that examined three and culled none has no explanation at all, and all three brake
        counters read 0 while nothing was ever held or spared.
      part.n_fold_candidates -- domains that met the visits/horizon test before the two fail-safes
        were applied, so "the fold refused everything" is separable from "nothing was eligible".
      part.n_mem_floor_entries -- the floor THIS PASS judged against, SET and not bumped, printed
        beside n_held_by_mem_floor. A floor of 0 means brake one is armed and cannot hold, and
        "held 0" cannot be read without it.
    """
    dom = dom.owned_by("DOM")
    protect = bool(dom.d_comp_protect)   # WIRE READ HERE -- brake two, FAB's policy on domains

    # THE LEVERS, READ ONCE AND INTO BARE LOCALS -- the clock ones (manage_every, cull_stale, grace)
    # included, for the reason fabric/api.py::grow_check's own block gives: reading a Clock-unit
    # lever off the Config inside the arithmetic below would put that Attribute in an operand, which
    # is what tests/test_ownership.py::check_o11_no_unnamed_clock_arithmetic forbids.
    on, every = bool(dom.manage), int(dom.manage_every)
    md, cfrac = float(dom.merge_dist), float(dom.cull_frac)
    amin, stale_n = float(dom.cull_act_min), int(dom.cull_stale)
    dec, grace_n = float(dom.decay), int(dom.grace)
    respect = bool(dom.cull_respects_mem_floor)
    fold_on, minv = bool(dom.fold), int(dom.min_visits)
    horizon, fmult = int(dom.recur_horizon), float(dom.fold_mult)
    res_n = int(dom.reservoir)
    now_n = _windows_of(now, "DOM.manage")
    floor_n = int(mem_floor_entries)

    # ---- STEP 1: THE TWO READ-SITE GUARDS, BEFORE ANY PASS COUNTER IS SEEDED -------------------
    # A REFUSED CALL IS STILL A CALL, so n_manage_calls is seeded and bumped above both guards.
    _seed(part, "part.n_manage_calls")
    _bump(part, "part.n_manage_calls")
    if not on:
        _seed(part, "part.n_manage_refused_off")
        _bump(part, "part.n_manage_refused_off")
        return _frozen_plan(part)
    if every == 0:
        # THE GUARD THE CONTRACT DEMANDS, AT THE READER, BECAUSE A LEVER CANNOT CHECK ITS OWN
        # READER. It is written `== 0` and not `<= 0` for two separate reasons: manage_period
        # already refuses a negative DOM_MANAGE_EVERY at startup under REFUSE_NEGATIVE_PERIOD
        # above, and there is no division anywhere in this body for a zero to reach -- the cadence
        # is evaluated by RUN.Cadences.due, so what 0 means HERE is only whether this pass is
        # allowed to run at all.
        _seed(part, "part.n_manage_refused_never")
        _bump(part, "part.n_manage_refused_never")
        return _frozen_plan(part)

    # ---- STEP 2: SEED THE PASS COUNTERS, EACH BRAKE ON ITS OWN LEVER ARM -----------------------
    # NEITHER REFUSED ARM ABOVE SEEDS ANY OF THESE, so on a frozen population every one of them is
    # ABSENT -- which is the correct reading of a population nothing was allowed to touch, and is
    # not the same statement as a pass that ran and changed nothing.
    _seed(part, "part.n_manage_passes", "part.n_merged", "part.n_culled", "part.n_emptied",
          "part.n_cull_budget_zero", "part.n_grace_skips", "part.n_cull_candidates",
          "part.n_cull_refused_activity")
    _bump(part, "part.n_manage_passes")
    if fold_on:
        _seed(part, "part.n_folded", "part.n_fold_refused_far",
              "part.n_fold_refused_no_pooled_radius", "part.n_fold_candidates")
    if respect:
        # EACH BRAKE'S KEY IS ABSENT WHEN ITS OWN LEVER IS OFF, which is what makes "the brake held
        # zero times" distinguishable from "the brake is not installed" -- the distinction the
        # cull's whole history is made of, and the one the old tree could not make because the cull
        # had a counter and its brakes had none.
        _seed(part, "part.n_held_by_mem_floor")
        part.counters["part.n_mem_floor_entries"] = floor_n
    if protect:
        _seed(part, "part.n_spared_by_competence")

    folds, deletions = {}, []
    n_merged = n_culled = n_folded = n_held = n_spared = n_emptied = 0

    # ---- STEP 3: ORDER IS FIXED AND IS THE MECHANISM -------------------------------------------
    # fold, then empty-cull, then merge, then the activity cull, then the decay. The fold runs
    # first because it is the only rule that judges a domain on RECURRENCE rather than on activity,
    # and a domain the fold would have preserved into its neighbour must not be deleted by the cull
    # on the same pass for the low activity that made it a fold candidate.

    # ---- FOLD (self_organize.py:3609-3626) -----------------------------------------------------
    if fold_on and len(part.cent) > 1:
        # THE BOUNDARY CLOCK, DELIBERATELY, AND NOT A WINDOW COUNT. What a domain needs before "it
        # never came back" is fair is a number of CHANCES to be re-entered, and a chance is a
        # boundary. Under a phased schedule a window count would condemn every domain whose corpus
        # is simply absent from the current phase -- which is the catastrophic-forgetting-by-the-
        # manager failure this package exists to prevent.
        drop = [i for i in part._live()
                if part.visits.get(i, 0) < minv
                and (part.nb - int(part.bornb.get(i, part.nb))) >= horizon]
        _bump(part, "part.n_fold_candidates", len(drop))
        # NEVER FOLD ONE DOOMED DOMAIN INTO ANOTHER: a target that is itself about to be folded away
        # would move `b`'s material twice in one pass, and the second move averages a centroid that
        # already contains it.
        ds = set(drop)
        for b in sorted(drop, key=lambda i: part.act.get(i, 0.0)):
            keep = [i for i in part._live() if i != b and i not in ds]
            if not keep:
                # EVERY LIVE DOMAIN IS DOOMED, so there is nothing to fold INTO and the fold does
                # nothing at all -- which is the right answer (folding them into each other would
                # collapse the population to one, the outcome the pooled-radius fail-safe exists to
                # prevent) and is the one outcome with no counter of its own. It does not need one:
                # `keep` is `live - ds`, which does not depend on `b`, so this is true for every
                # remaining candidate and `break` is exactly `continue`; and the state reads off the
                # four keys already here as n_fold_candidates > 0 with folded, refused_far and
                # refused_no_pooled_radius all 0. Driven at min_visits=99, where it is the whole
                # behaviour of the fold.
                break
            sm = torch.stack([part.cent[i] for i in keep]) @ part.cent[b]
            k = int(sm.argmax())
            # THE FAIL-SAFE RUNS BOTH WAYS AND EACH WAY HAS ITS OWN COUNTER. An unbounded fold
            # collapses the whole population to ONE domain, which is far worse than folding late;
            # and "there is no pooled radius yet" is a different state from "the nearest neighbour
            # is too far", because the first says the fold cannot be judged at all and is cured by a
            # rekey while the second is a measurement.
            if part.radp <= 0.0:
                _bump(part, "part.n_fold_refused_no_pooled_radius")
                ds.discard(b)
                continue
            if (1.0 - float(sm[k])) > fmult * part.radp:
                _bump(part, "part.n_fold_refused_far")
                ds.discard(b)
                continue
            _absorb(part, keep[k], b, res_n=res_n)
            folds[b] = keep[k]
            n_folded += 1
            _bump(part, "part.n_folded")

    # ---- EMPTY-CULL, UNCONDITIONAL (self_organize.py:3635-3646) --------------------------------
    # THE DOM_CULL_EMPTY KNOB IS DROPPED AND THE BEHAVIOUR STAYS, because the gated operation is
    # LOSSLESS BY CONSTRUCTION: a domain with no reservoir sample and no memory entry holds nothing
    # that deleting it can destroy. A switch over an operation that cannot lose anything is a switch
    # whose off position has no meaning to report.
    for d in list(part._live()):
        if len(part.cent) <= 1:
            break
        if part.reservoir.get(d):
            continue
        if now_n - int(part.born.get(d, now_n)) < grace_n:
            _bump(part, "part.n_grace_skips")
            continue
        if _count_for(memory_counts, d) > 0:
            # IT STILL OWNS MEMORY, SO IT IS NOT EMPTY. The reservoir is stream-local sample; the
            # store is the thing goal B is about, and a domain whose entries survive is a domain
            # whose name has to survive with them or the provenance is orphaned.
            continue
        _drop(part, d)
        deletions.append(d)
        n_emptied += 1
        n_culled += 1
        _bump(part, "part.n_emptied")
        _bump(part, "part.n_culled")
        # THE ID GOES INTO Plan.deletions EVEN THOUGH THE DELETE IS A GUARANTEED NO-OP IN MEM. The
        # id must stop being live, and MEM's n_entries_deleted_by_cull then records an honest zero
        # for it rather than nothing at all -- a delete that removed nothing and a delete that never
        # happened are two facts and only one of them is evidence that the brake worked.

    # ---- MERGE (self_organize.py:3648-3657) ----------------------------------------------------
    # THE FROZEN FALLBACK `md = merge_dist if merge_dist > 0 else MERGE_FRAC * NEW_DIST` IS GONE.
    # src/domains/levers.py's DEFECT 3 rules that 0.28 is the only route to the merge threshold and
    # that d_merge_dist must not exist, so DOM_MERGE_DIST=0.0 merges only centroids that coincide
    # exactly -- the merge off in everything but name, which is that lever's declared lo end.
    while len(part.cent) > 1:
        ids = part._live()
        n = len(ids)
        C = torch.stack([part.cent[i] for i in ids])
        M = C @ C.T
        # -2.0 AND NOT -1.0: a cosine is bounded at -1, so -1 is a value a genuine antipodal pair
        # can take and masking with it would let a domain merge with itself on a population of two.
        M.fill_diagonal_(-2.0)
        r, c = divmod(int(M.argmax()), n)
        if (1.0 - float(M[r, c])) >= md:
            break
        a, b = ids[r], ids[c]
        if part.act.get(b, 0.0) > part.act.get(a, 0.0):
            # KEEP THE MORE ACTIVE, NOT THE LOWER ID. The id is an accident of creation order; the
            # activity is the only thing on the pair that says which name the run's material is
            # actually filed under, and MEM's entries are filed under the name.
            a, b = b, a
        _absorb(part, a, b, res_n=res_n)
        folds[b] = a
        n_merged += 1
        _bump(part, "part.n_merged")

    # ---- THE ACTIVITY CULL (self_organize.py:3664-3698) ----------------------------------------
    if len(part.cent) > 1:
        order = sorted(part._live(), key=lambda i: part.act.get(i, 0.0))
        # WITH NO max(1, ...), AND THAT ABSENCE IS THE REPAIR. The floor turned "cull at most a
        # tenth" into "cull at least one, every pass, forever" and ratcheted a population to a
        # single domain three separate times -- the three runs are printed in the comment under
        # src/domains/levers.py::DOMLevers.cull_frac.
        budget = int(cfrac * len(order))
        if budget <= 0:
            # AN EMPTY BUDGET IS A STATE THIS ENTRY POINT ANTICIPATES BY NAME, and it is the normal
            # state of a small population: at DOM_CULL_FRAC=0.10 anything under ten live domains
            # has a budget of zero, so this key reading high against n_manage_passes is the healthy
            # reading and not a fault. Bumped ONCE PER PASS, not per domain -- there is no domain.
            _bump(part, "part.n_cull_budget_zero")
        else:
            cand = order[:budget]
            _bump(part, "part.n_cull_candidates", len(cand))
            for d in cand:
                if len(part.cent) <= 1:
                    break
                if d not in part.cent:
                    continue
                if now_n - int(part.born.get(d, now_n)) < grace_n:
                    # BOTH CULL PATHS NEED THE SAME GUARD OR THE WEAKER ONE DECIDES, which is what
                    # `grace`'s own declaration requires -- so this key is bumped here and in the
                    # empty-cull above, under one name.
                    _bump(part, "part.n_grace_skips")
                    continue
                if not (part.act.get(d, 0.0) < amin
                        and (now_n - int(part.last.get(d, now_n))) > stale_n):
                    # EXAMINED AND KEPT ON ITS OWN MERITS. Without this key a pass that looked at
                    # three domains and deleted none is indistinguishable from a pass that looked at
                    # none, while all three brake counters correctly read 0.
                    _bump(part, "part.n_cull_refused_activity")
                    continue
                if respect and floor_n > 0 and _count_for(memory_counts, d) >= floor_n:
                    # BRAKE ONE, AND IT IS THE ONE GOAL B DEPENDS ON. MEM's floor forbids EVICTING
                    # those entries, and deleting them is the BIGGER action on the WEAKER test. It
                    # self-releases: once eviction has genuinely drained the domain it falls below
                    # the floor and the cull proceeds, so this is a delay and not an immunity.
                    _bump(part, "part.n_held_by_mem_floor")
                    n_held += 1
                    continue
                if (protect and part.comp_glob is not None and d in part.comp
                        and part.comp[d] < part.comp_glob):
                    # BRAKE TWO. COMPETENCE HERE IS A LOSS, so LOWER beats the baseline
                    # (self_organize.py:3694) -- and comp_glob is None until the first reading
                    # lands, which is the state in which this brake cannot fire at all rather than
                    # the state in which it fires for everyone.
                    _bump(part, "part.n_spared_by_competence")
                    n_spared += 1
                    continue
                _drop(part, d)
                deletions.append(d)
                n_culled += 1
                _bump(part, "part.n_culled")

    # ---- THE DECAY AND THE TIDY (self_organize.py:3699-3700) -----------------------------------
    # ONCE PER PASS, AND NOWHERE ELSE. That is what makes (manage_every, decay) an irreducible pair:
    # the effective activity half-life in windows is set by BOTH, so changing the cadence silently
    # rescales cull_act_min. A decay written per window, or a second one anywhere, would make the
    # threshold mean a different thing at every batch width.
    for i in list(part.act):
        part.act[i] = part.act[i] * dec
    # COMPETENCE FOLLOWS THE POPULATION. A book keyed on a domain that no longer exists would be
    # restored by the next checkpoint and compared against comp_glob for ever.
    part.comp = {i: v for i, v in part.comp.items() if i in part.cent}

    # ---- THE COLLAPSE STAMP (L36) --------------------------------------------------------------
    # DOM CANNOT TEST "IN A MULTI-PROCESS RUN" and must not learn to: no wire carries the process
    # count into this package and none may be minted for it. So the stamp is on n_live falling to
    # one, alone, and DOM.census carries the WINDOW for a reader who also holds DATA's process
    # count. Stamped once and never cleared -- the question is when the population first collapsed,
    # not whether it is collapsed now.
    # `== 1` AND NOT `<= 1`, AND THE TWO DIFFER ON EXACTLY ONE CONFIGURATION. Every loop above
    # breaks at `len(part.cent) <= 1`, so a population that has ever held a domain can reach one and
    # never zero -- the only way to be at zero here is never to have assigned anything, which is the
    # DOM_ENABLED=0 partition. Driven at that arm the `<= 1` form stamped collapsed_at on the first
    # pass of a run that never had a population to collapse, and L36's whole value is that the
    # stamp is rare enough to be read as a finding. `partition_off` already says the other thing.
    if len(part.cent) == 1 and part.collapsed_at is None:
        part.collapsed_at = now_n

    return Plan(folds={b: _resolve(part, a) for b, a in folds.items()},
                deletions=tuple(deletions), live=part._live(), merged=n_merged, culled=n_culled,
                folded=n_folded, held=n_held, spared=n_spared, emptied=n_emptied)


def on_retokenize(dom: Config, part):
    """The tokenizer re-segmented the stream: decay every domain's token histogram by tokc_decay.

    AN EVENT, NOT A CADENCE. This package must not read TOK.retok_every -- the cadence is TOK's and
    a second copy of it here would be a second answer to "when did the vocabulary change".

    The reasoning behind a default below 1.0: the counts are over TOKEN IDS, and a retok makes the
    same text into DIFFERENT ids, so counts banked before it are observations of a DIFFERENT
    distribution rather than stale observations of this one. 1.0 restores cumulative-forever.

    LEVERS READ: tokc_decay, prior_blend
    WIRES READ: none
    DID IT FIRE: part.n_retok_decays
    TWO MORE KEYS THE BODY WRITES, DECLARED HERE FOR THE REASON fabric/api.py::grow_check gives: a
    key in the report that the contract does not admit to producing is the same defect as a declared
    key nothing writes, and the count is taken in both directions.
      part.n_retok_events -- deliveries of the event, seeded on BOTH arms. It is the only thing that
        separates DOM_PRIOR_BLEND=0 from "the root never delivered a retok at all", and without it
        every key below reads 0 in both cases -- the distinction RunResult.skipped exists to make,
        and it has to survive one entry point in. THE ROOT ALSO SEEDS IT, at every epoch roll and
        before deciding whether to call (2026-09-24, the tok.due_merged precedent), so a run that
        rolled with an unmoved match table reads present-and-0 -- armed, not delivered -- and ABSENT
        means only that no roll happened.
      part.n_retok_domains_decayed -- per-domain histograms touched, cumulative across events.
    """
    dom = dom.owned_by("DOM")
    keep, blend = float(dom.tokc_decay), float(dom.prior_blend)

    # THIS ENTRY POINT TAKES NO EVENT PARAMETER, AND THAT IS NOT AN OMISSION TO WORK AROUND.
    # spine/compose.py's ("E", "DOM", "on_retokenize") row -- the epoch roll, which is where the
    # root delivers this call since 2026-09-24, and only when the match table moved since the last
    # segmentation -- records that SIG and FAB have no retokenize entry point, that the event is a
    # record type tok/api.py declares and no entry point's docstring returns, and that this call
    # takes no event at all. So this body may read
    # NOTHING about what the retok did -- not the id remap, not the new vocabulary size, not the
    # cadence -- and that is exactly WHY the mechanism is a decay and not a remap: the counts are
    # over TOKEN IDS, a retok makes the same text into DIFFERENT ids, so counts banked before it are
    # observations of a DIFFERENT distribution rather than stale observations of this one. The only
    # thing sayable without the event is "trust them less". If a later ruling gives this package the
    # id map it arrives as an EVENT PARAMETER, which is a frozen-signature move and not something to
    # smuggle in through a wire.
    _seed(part, "part.n_retok_events")
    _bump(part, "part.n_retok_events")

    if blend == 0.0:
        # THE ACCOUNTING SWITCH IS DOWN, so nothing was ever accumulated and the decay is
        # UNREACHABLE rather than armed and idle. part.n_retok_decays stays ABSENT, which is the
        # same "turned off" versus "turned on and never filled" separation domains/api.py::prior is
        # built around.
        return None

    _seed(part, "part.n_retok_decays", "part.n_retok_domains_decayed")
    touched = 0
    for _did, hist in part.tokc.items():
        if not hist:
            continue
        if keep == 0.0:
            # THE STRICT READING OF THE ARGUMENT ABOVE: the pre-retok counts are observations of a
            # different distribution, and 0.0 drops them outright. Clearing rather than zeroing also
            # stops DOM.prior carrying a vocabulary of zeros forever through its `total <= 0.0`
            # branch, which would cost a sum over the whole histogram on every read to return the
            # same (None, 0.0) an empty dict returns immediately.
            hist.clear()
        else:
            # COUNTS BECOME FLOATS, which DOM.prior already handles (it takes float(sum(...)) and
            # divides) and which state_dict already serialises (it copies the dict as it stands).
            for t in list(hist):
                hist[t] = hist[t] * keep
        touched += 1

    if touched:
        _bump(part, "part.n_retok_domains_decayed", touched)
        if keep < 1.0:
            # AT DOM_TOKC_DECAY=1.0 THE MULTIPLY IS A NO-OP and the declared meaning of that value
            # is "restores cumulative-forever", so the honest reading is armed-and-did-not-fire: the
            # key is present at 0 with a nonzero n_retok_events beside it. Bumping it there would
            # report a decay that changed nothing as a decay that happened.
            _bump(part, "part.n_retok_decays")
    # NOTHING IS RETURNED. The books ARE the product, which is note_competence's own sentence about
    # the same Partition and for the same reason: a record here would be a second copy of numbers
    # whose single source of truth is the point of this design.
    return None


def prior(dom: Config, part, *, did):
    """The per-domain token prior AND the weight it is to be blended at, TOGETHER.

    Returns (probs, weight), or (None, 0.0) when prior_blend == 0, when this domain has no
    histogram, or when the histogram is empty.

    THE WEIGHT TRAVELS WITH THE HISTOGRAM ON PURPOSE. prior_blend was one field doing two jobs -- a
    training-side accounting switch that turns the per-window accumulation on (:6788-6791) and an
    instrument parameter that is the mixing weight at eval (:8147-8192) -- and the two could drift.
    Here `observe` accumulates on exactly the value this call returns, so they cannot.

    LEVERS READ: prior_blend
    WIRES READ: none
    DID IT FIRE: part.n_prior_reads, n_prior_accumulated, n_prior_empty -- the accumulated/read
                 PAIR is the whole finding that the histogram was paid for every window and never
                 read
    """
    dom = dom.owned_by("DOM")
    _seed(part, "part.n_prior_reads")
    _bump(part, "part.n_prior_reads")
    # THE WEIGHT TRAVELS WITH THE HISTOGRAM, WHICH IS THE WHOLE POINT OF RETURNING A PAIR.
    # prior_blend was ONE FIELD DOING TWO JOBS -- a training-side accounting switch that turns the
    # per-window accumulation on (:6788-6791) and an instrument parameter that is the mixing weight
    # at eval (:8147-8192) -- and the two could drift apart with nothing saying so. Here `observe`
    # accumulates on exactly the value this call returns, so they cannot.
    weight = float(dom.prior_blend)
    if weight == 0.0:
        # OFF. Not an error and not an empty histogram: the accounting switch is down, so nothing
        # was accumulated and there is nothing to blend. Counted apart from `empty` below because
        # "turned off" and "turned on and never filled" are the two readings this pair exists to
        # separate -- the finding being that the histogram was PAID FOR every window and never READ.
        return None, 0.0
    # SEEDED HERE, AFTER THE OFF-ARM RETURN AND BEFORE THE DATA BRANCH, AND IT WAS NOT UNTIL
    # 2026-09-21. This key was written only inside the two empty branches, so at prior_blend > 0
    # with a HEALTHY histogram it was ABSENT -- and absent is this tree's spelling for UNREACHABLE,
    # so the report read "the empty case cannot arise on this configuration" about a mechanism that
    # was armed and simply had nothing to report. That is the defect fabric/api.py::_bump exists to
    # prevent, sitting inside the file that argues for it. It stays BELOW the weight == 0.0 return,
    # because on that arm nothing was ever accumulated and the empty case genuinely is unreachable.
    _seed(part, "part.n_prior_empty")
    hist = part.tokc.get(did)
    if not hist:
        _bump(part, "part.n_prior_empty")
        return None, 0.0
    total = float(sum(hist.values()))
    if total <= 0.0:
        _bump(part, "part.n_prior_empty")
        return None, 0.0
    probs = {int(t): (c / total) for t, c in hist.items()}
    # part.n_prior_accumulated IS NOT WRITTEN HERE, AND THIS LINE IS THE REPAIR. This body used to
    # increment it on every successful read while DOM.observe's DID IT FIRE line declares the same
    # key for the per-window ACCUMULATION -- so the pair both docstrings argue for, "paid for every
    # window and never read", came out as accumulated = windows + successful reads and the finding
    # was destroyed by the second writer. observe owns the key; this entry point's DID IT FIRE line
    # keeps NAMING it, which is legitimate: a contract may declare a key it only REPORTS, and the
    # accumulated/read pair is unreadable unless both halves are named in one place.
    return probs, weight


def census(dom: Config, part):
    """Everything the report, FAB and the spine need to know about the partition, in one call.

    RETURNS PartitionCensus, declared in this module's RECORD TYPES RETURNED block (Q-MEM-11).

    Returns live (the list the spine passes to MEM as live_sources), n_live, created, capped,
    merged, culled, folded, held, spared, emptied, boundaries, windows, visits/born/last/radius per
    domain, pooled_radius, comp_glob (what FAB reads for its spare rule -- exporting it HERE is
    what makes that crossing declarable instead of the attribute reach at :6720), collapsed_at (the
    WINDOW at which n_live first fell to 1 in a multi-process run -- recorded and previously never
    surfaced, L36), partition_off, and every part.n_* counter.

    LEVERS READ: enabled, prior_blend
    WIRES READ: none
    DID IT FIRE: this call IS the DID IT FIRE surface for the package
    TWO MORE KEYS THE BODY WRITES, DECLARED HERE FOR THE REASON fabric/api.py::grow_check gives: a
    key in the report that the contract does not admit to producing is the same defect as a declared
    key nothing writes, and the count is taken in both directions.
      part.n_censuses -- how many times the census was taken. The sibling of the part.n_state_dicts
        this file already keeps, and the same argument: an R-stage surface that cannot say it was
        ASKED cannot distinguish an empty partition from an unasked one.
      part.n_prior_domains -- domains holding a token histogram at all, set only when prior_blend is
        on. It is the DENOMINATOR that makes the accumulated/read pair checkable: n_prior_accumulated
        against n_prior_reads says the histogram was paid for every window and never read, and
        neither number means anything without knowing how many domains held one.

    THREE STATES, CARRIED ON A FIELD AND NOT ON A spine.gate.Gate, AND THE GAP IS NAMED RATHER THAN
    PAPERED OVER. note_competence's DID IT FIRE line promises that "the Gate says so" for the
    comp_glob-is-None state, but Partition.__slots__ carries no `gates` field and the
    PartitionCensus declaration in this module's RECORD TYPES block names none -- so no Gate can
    live in this package without either a new slot or an undeclared record field, and an undeclared
    field is tok/api.py's D-T3. The statement is therefore carried by `comp_glob is None` plus the
    presence or absence of the counter keys, which is strictly weaker than a Gate (it has no
    `reason` string) and is what the record can honestly hold today.
    """
    dom = dom.owned_by("DOM")
    enabled, blend = bool(dom.enabled), float(dom.prior_blend)

    _seed(part, "part.n_censuses")
    _bump(part, "part.n_censuses")
    if blend > 0.0:
        # A REAL USE OF THE LEVER THIS ENTRY POINT DECLARES, not an echo of its value: the key is
        # ABSENT when the accounting switch is down, which is the only way a reader can tell "no
        # domain holds a histogram" from "no histogram was ever going to be held".
        part.counters["part.n_prior_domains"] = len(part.tokc)

    # A NAMED COUNT FIELD IS None WHEN ITS COUNTER KEY IS ABSENT, NEVER 0, so every one of these is
    # `.get(key)` with NO DEFAULT. Writing `.get(key, 0)` here would convert UNREACHABLE into
    # armed-and-did-not-fire at the exact place the report reads it -- the last and worst place to
    # do it, because by then the arithmetic that could have told them apart is gone.
    c = part.counters
    live = part._live()
    # NOTHING BELOW COMPUTES, NORMALISES OR REPAIRS ANYTHING. A census that recomputed a number some
    # other entry point owns would give the package two answers to "did it fire" and let the report
    # quote whichever it reached first -- the defect spine/gate.py::Gate was introduced to end.
    return PartitionCensus(
        live=live,
        n_live=len(part.cent),
        created=c.get("part.n_created"),
        capped=c.get("part.n_capped"),
        merged=c.get("part.n_merged"),
        culled=c.get("part.n_culled"),
        folded=c.get("part.n_folded"),
        held=c.get("part.n_held_by_mem_floor"),
        spared=c.get("part.n_spared_by_competence"),
        emptied=c.get("part.n_emptied"),
        # THE BOUNDARY CLOCK, which is chain-wide and survives a resume, beside the per-run count in
        # the counters passthrough. Two numbers because they answer two questions, and a record
        # carrying one of them cannot answer the other.
        boundaries=int(part.nb),
        windows=c.get("part.n_windows"),
        visits={i: int(part.visits.get(i, 0)) for i in live},
        born={i: int(part.born.get(i, 0)) for i in live},
        last={i: int(part.last.get(i, 0)) for i in live},
        radius={i: float(part.rad.get(i, 0.0)) for i in live},
        # 0.0 MEANS NO REKEY HAS MEASURED ONE YET, which is this package's OTHER spelling of "not
        # measured" -- part.comp_glob below spells the same thing None, on purpose, and the two must
        # not be unified: a radius of exactly 0.0 is a value a quantile could in principle return,
        # while a competence of 0.0 is a perfect score and would disarm the cull's spare.
        pooled_radius=float(part.radp),
        # None MEANS NO WINDOW HAS BEEN ATTRIBUTED YET, which IS the statement that competence
        # protection cannot fire. It is the only three-state surface this package has for that gate.
        comp_glob=part.comp_glob,
        collapsed_at=part.collapsed_at,
        # READ OFF THE LEVER AND NOT INFERRED FROM n_live. A run with DOM_ENABLED=0 that restored
        # domains from a checkpoint still has a live-looking partition and is still off, so a
        # reader inferring this from the population would report the opposite of the truth on
        # exactly the configuration that needs saying.
        partition_off=not enabled,
        # PASSED THROUGH WHOLE, ABSENCES INCLUDED. Filtering or defaulting here would destroy the
        # only record of which arms this run did not take.
        counters=dict(part.counters),
    )


def state_dict(dom: Config, part):
    """The checkpoint blob: centroids, RESERVOIRS, sizes, activity, births, last-fed, visits, the
    boundary clock and per-domain birth-boundary, merge chains, radii and the pooled radius, the
    TOKEN HISTOGRAMS, the COMPETENCE EMAs and the population baseline, and the ADJACENT-DISTANCE
    HISTORY the relative shift test calibrates on. The four capitalised ones are the omissions that
    each disarmed a live mechanism at the run boundary (M51). And this package's RNG stream, `rng`,
    since 2026-09-24.

    LEVERS READ: none (a pure read of `part`)
    WIRES READ: none
    DID IT FIRE: part.n_state_dicts
    """
    dom = dom.owned_by("DOM")
    # WRITTEN IN EXACTLY THE SHAPE open_partition(restored=...) READS, key for key. The two halves
    # of a persistence pair are one mechanism, and the failure they had is asymmetry: the old blob
    # saved cent/size/last/next_id and dropped the reservoir, comp and comp_glob, tokc, and the
    # adjacent-distance history -- so competence protection protected nothing after a resume, the
    # prior histogram restarted empty while still being paid for every window, and the relative
    # shift test had no history to be relative to. M51 is the four of them together.
    domains = {}
    for i in part.cent:
        domains[str(i)] = {
            "cent": part.cent[i].detach().cpu().tolist(),
            # THE RESERVOIR, which is a LIST of tensors per domain rather than one tensor: it is the
            # sample a rekey draws its new centroid from, and a resume without it re-keys off
            # whatever arrives next.
            "reservoir": [x.detach().cpu().tolist() for x in (part.reservoir.get(i) or [])],
            "size": int(part.size.get(i, 0)),
            "act": float(part.act.get(i, 0.0)),
            "born": int(part.born.get(i, 0)),
            "last": int(part.last.get(i, 0)),
            "visits": int(part.visits.get(i, 0)),
            "rad": float(part.rad.get(i, 0.0)),
            # THE TOKEN HISTOGRAM. DOM.prior is computed from it, so a resume without it pays for
            # the prior every window and gets a uniform one.
            "tokc": dict(part.tokc.get(i, {}) or {}),
            # THE COMPETENCE EMA, per domain, with comp_glob below as the population baseline. A
            # domain is protected from culling by being MORE competent than the baseline, so losing
            # either half of that comparison disarms the protection rather than loosening it.
            "comp": float(part.comp.get(i, 0.0)),
        }
    out = {
        "domains": domains,
        "next_id": int(part.next_id),
        "merged": {str(k): int(v) for k, v in (part.merged or {}).items()},
        "radp": float(part.radp),
        # NOT CAST THROUGH float(): comp_glob is None until the first note_competence lands
        # (2026-09-17), and float(None) is a TypeError on the save path of a run whose domains have
        # never been scored -- which is every run where DOM.note_competence is not yet driven. The
        # None is the fact being saved: "no window has been attributed yet".
        "comp_glob": None if part.comp_glob is None else float(part.comp_glob),
        # THE ADJACENT-DISTANCE HISTORY the relative shift test calibrates on. Without it the first
        # windows of a resumed run are tested against an empty calibration, which is the same as
        # testing them against nothing.
        "adj_hist": list(part.adj_hist or []),
        "sh": int(part.sh),
        # THE BOUNDARY CLOCK, AND IT MUST NOT RESTART. At :4991 it did, and a restored domain then
        # looked as though it had seen no boundaries, so the fold swallowed any that had not
        # happened to be re-entered twice since the resume. open_partition stamps bornb from this
        # value AFTER restoring it, so grace re-arms against the real clock rather than expiring
        # against a zero.
        "nb": int(part.nb),
        # THIS PACKAGE'S RNG STREAM, which did not cross until 2026-09-24 while SIG's, FAB's and
        # WORLD's did, in the same (state, draws) shape. part.rng decides reservoir replacement and
        # _absorb's pooled resample; re-seeded on every resume, the child REPLAYED the parent's
        # first choices (driven: 79 draws in a 160-window parent, 0 in its resumed child).
        "rng": (part.rng._r.getstate(), int(part.rng._draws)) if getattr(part, "rng", None) else None,
        # THE STREAM POSITION (03b S0b): the current domain, the run in progress, its signature, a
        # pending switch, and each domain's boundary clock at birth. A continuing mid-epoch resume
        # reads the same stream on, so these decide its next window exactly as they would have;
        # the root strips this block for any other resume, where a new stream begins.
        "position": {
            "cur": int(part.cur), "run": int(part.run),
            "run_sig": None if part.run_sig is None else part.run_sig.detach().cpu().tolist(),
            "pend": (None if part.pend is None
                     else [x.detach().cpu().tolist() for x in part.pend]),
            "bornb": {str(k): int(v) for k, v in (part.bornb or {}).items()}},
    }
    # `cur`, `run`, `run_sig` and `pend` ARE NOT SAVED, and open_partition resets them. The current
    # domain is a property of the STREAM POSITION and the resume starts a new stream; carrying it
    # would attribute the first window of the resumed run to whatever the parent was in the middle
    # of. That is a save-side statement as much as a load-side one, which is why it is here too.
    part.counters["part.n_state_dicts"] = part.counters.get("part.n_state_dicts", 0) + 1
    return out


def manage_period(dom: Config):
    """The domain management cadence, AS units.Windows. Handed to RUN's Cadences.due.

    WHY THIS EXISTS RATHER THAN THE ROOT PASSING cfg.manage_every. Cadences.due states that its
    period "MUST be units.Windows. An int raises; a Flushes raises." -- and Config hands back a bare
    int for all 35 levers that declare a Clock unit (ISSUES P1-H51), so the row that read
    `Cadences.due('dom.manage', DOM.manage_every, clock)` was passing an int into a function whose
    contract refuses one. EVAL and CKPT already had typed accessors (curve_period, save_period);
    FAB, DOM and MEM did not, and their three rows were the only ones that would have raised.
    THAT ROW NAMED `FAB.manage_every` IN THIS DOCSTRING UNTIL 2026-09-04, WHICH IS THE WRONG PACKAGE
    AND IS A DEFECT AND NOT A TYPO: the 'dom.manage' gate takes DOM's own field, FAB's field of the
    identical name drives the SEPARATE 'fab.manage' gate, and the two were SPLIT apart precisely
    because sharing one cadence meant domain merge/cull/fold ran zero times in a default-length run
    (src/domains/levers.py records the arithmetic). The sentence was a copy of the FAB sibling's,
    where the same words are correct -- fabric/api.py::manage_period still carries them -- so a
    reader checking this docstring against that one would have found them agreeing and both
    describing FAB. tests/test_contract.py::check_k9_cadence_periods_are_typed reads the ROWS in
    spine/compose.py, not this prose, so nothing in the suite could see it.

    THE WRAP BELONGS HERE AND NOT AT THE CALL SITE because this is where the kind is DECLARED.
    domains/levers.py types manage_every Windows; a root that wrote Windows(dom.manage_every)
    would be asserting that kind from outside the package that owns it, in three places, each free
    to be wrong on its own. One accessor per period is the same rule the wires follow.

    IT IS A CONSTRUCTION, NOT A CONVERSION. Windows(int) re-attaches the declared kind; it does not
    cross kinds. The inline arithmetic this project calls a defect is
    `manage_every // batch_w` -- Windows to Flushes, unnamed -- which is derive.flush_period_windows
    and is not this.

    LEVERS READ: manage_every
    WIRES READ: none
    DID IT FIRE: no counter of its own -- Cadences.ledger()['dom.manage'] is the surface, and that
                 is the point of routing every gate through one primitive.
    """
    dom = dom.owned_by("DOM")
    every = int(dom.manage_every)
    # A NEGATIVE MANAGEMENT CADENCE IS REFUSED HERE, AT THE ONLY PLACE `manage_every` IS READ (added
    # 2026-09-04 under the owner's ruling; the switch and the alternatives are at
    # REFUSE_NEGATIVE_PERIOD above). It fires BEFORE the Windows is constructed, so no other number
    # is derived from the bad value -- the placement rule capacity/api.py::new_valve took from
    # lm/api.py::resolve, applied here rather than copied: this is a range check over DOM's own
    # lever at its first read, and DOM declares no refusal entry point for it to live in.
    #
    # WHAT A NEGATIVE ACTUALLY DOES TODAY, MEASURED RATHER THAN ASSUMED. `assemble.build` accepts
    # DOM_MANAGE_EVERY=-5 and freezes it; this accessor returned Windows(-5); and
    # spine/derive.py::cadences_that_cannot_fire then reported ("dom.manage", -5, 0) -- the SAME
    # shape of line it prints for a period of zero -- AND THAT LINE IS RIGHT. RUN.Cadences.due's
    # body opens with `if int(period) <= 0: return False`, so a negative DISARMS the management
    # pass (driven with the switch off at DOM_MANAGE_EVERY=-1 over 12 windows: ledger dom.manage
    # checks=12 fires=0). UNTIL 2026-09-24 THIS PARAGRAPH SAID A NEGATIVE WAS MERGE-CULL-FOLD ON
    # EVERY WINDOW, a prediction from Cadences.due's contract made before its body existed; the
    # body does the opposite. A negative is an undeclared spelling of "never manage", and the
    # refusal stands on the owner's ruling for that reason.
    #
    # ZERO IS NOT TOUCHED, AND THE OFF-STATE IS NOT THIS LEVER. src/domains/levers.py carries a
    # PORT REQUIREMENT that 0 must mean NEVER behind a guard at the read site, and it is not
    # implemented anywhere yet; the same file refuses outright to let 0 be read as the off-state,
    # because the declared way to switch this package's management off is the `manage` flag. The
    # test below is strictly `< 0`, so neither the unimplemented port requirement nor the flag
    # moves, and this guard settles no part of what 0 will mean.
    #
    # IT REMOVES NO CONFIGURATION. DOM_MANAGE_EVERY=1 is the every-window pass and is in range; the
    # negative range spells nothing this lever's help text gives a meaning to.
    if REFUSE_NEGATIVE_PERIOD and every < 0:
        raise LeverError(
            f"DOM_MANAGE_EVERY={every}: a management cadence is a count of windows ELAPSED since "
            f"the last pass and may not be negative. RUN.Cadences.due (train/api.py) returns "
            f"False for every period <= 0, so {every} would DISARM the "
            f"merge/cull/fold pass -- an undeclared spelling of 'never manage', printed DISARMED "
            f"by RUN.cadence_audit. Refused rather than read as off, under the owner's switch "
            f"(REFUSE_NEGATIVE_PERIOD at the top of domains/api.py). Neither meaning an operator "
            f"might have wanted is lost: DOM_MANAGE=0 is "
            f"the declared off-state for this package's management and DOM_MANAGE_EVERY=1 is the "
            f"every-window pass. DOM_MANAGE is not consulted here: this refuses an out-of-range "
            f"value for DOM's own cadence lever, whether or not a second lever makes it moot.")
    return U.Windows(every)
