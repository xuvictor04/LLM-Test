"""The one place the packages are wired together, and the only file allowed to hold more than one LeverSet.

WHY EXACTLY ONE FILE. Every other module in the tree receives its own `Config` as a parameter. That is
not a policy, it is an author-time NameError: there is no name in scope for another package's levers, so
reading one is not "discouraged", it does not compile into anything that runs. The cost of that rule is
that SOMETHING has to hold all the Configs at once in order to compute the values that genuinely cross
boundaries. This file is that something, and keeping it to one file is what makes the coupling graph
finite and printable.

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
     fields named in `src`, plus the destination package's OWN levers, and raises on anything else. The
     declared `reads` set is therefore enforced rather than advisory.

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

WHAT THIS FILE CANNOT DO, said plainly. A wire's value must be computable from levers alone, at startup,
because `Config` freezes when `build()` returns and there is no such thing as a late wire. The signature
width is the clearest casualty: `derive.signature_width_bytes(win_tokens, bytes_per_token)` needs a
MEASURED compression ratio that does not exist until the tokenizer has seen the corpus, so it cannot be a
`d_` field on a frozen Config. It is in `NOT_WIRES` below with that reason. The discipline that replaces
the ledger there is `derive.py`'s: one named function, called once, answer kept -- which is what the old
tree failed at when it resolved SIG_WIN in two places from one knob whose zero meant 614 bytes in training
and 1 byte in eval.
"""
import io

from . import derive
from . import registry
from . import units as U
from .lever import LeverError
from .units import Steps
from .wire import WIRE_BUDGET, WireError, Wires, _check_unit, _check_why, _split


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
            "because MAX_DOMAINS sat in _DERIVED and was exempt from the default-mismatch refusal. It is "
            "marked reducible because domains could legitimately own a smaller namespace than the slot "
            "pool; what it may not do is own a DIFFERENT one silently."),

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
            "any log. Deriving it here means the number that gets discarded is the one nobody wrote."),
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
            "written for. The formula is the shipped one; only its input was wrong. Reducible: a census "
            "that grows on demand needs no bound at all, and that is the better repair when it is written."),

    # --- the training loop -> the per-flush cadences -----------------------------------------------
    Coupling(
        src="TRAIN.batch_w",
        dst="FAB.d_manage_period",
        compute=lambda r: derive.flush_period(Steps(r["FAB"].manage_every), r["TRAIN"].batch_w),
        unit=U.Flushes,
        irreducible=True,
        why="MANAGE_EVERY is written in STEPS and the management block sits below the batch early-out, so "
            "it runs once per FLUSH. The old tree wrote the conversion inline as "
            "'MANAGE_EVERY // max(1, BATCH_W)' at each of eight call sites (self_organize.py:6795, 6819, "
            "6836, 6961, 6988, 7077, 7325, 7368). Irreducible: a cadence in steps handed to a loop that "
            "counts flushes has no meaning until batch_w is known, which is why the value is a Flushes "
            "clock and not an int -- an int compares fine against a threshold in the wrong unit."),
    Coupling(
        src=("TRAIN.batch_w", "TRAIN.grow_cap_every"),
        dst="FAB.d_cap_lift_period",
        compute=lambda r: derive.flush_period(Steps(r["TRAIN"].grow_cap_every), r["TRAIN"].batch_w),
        unit=U.Flushes,
        irreducible=True,
        why="The measured case for this whole mechanism. The capacity valve's pin clock ticked per flush "
            "against a threshold in steps, so GROW_CAP_EVERY=20000 silently demanded 320,000 steps at "
            "BATCH_W=16 and 640,000 at 32: the population sat pinned for 43,645 real steps while the "
            "clock read 2,650 (= 42,400/16) and the report said 'reached the cap but never held it long "
            "enough' -- a true sentence about a false clock. A second gate one layer up then compared "
            "fabgrow.n (calls) to the same steps threshold and lifted nothing for a further whole round, "
            "the first fault masking the second."),
    Coupling(
        src=("TRAIN.batch_w", "TRAIN.grow_cap_every"),
        dst="TOK.d_cap_lift_period",
        compute=lambda r: derive.flush_period(Steps(r["TRAIN"].grow_cap_every), r["TRAIN"].batch_w),
        unit=U.Flushes,
        irreducible=True,
        why="The vocabulary soft cap is lifted by the same valve on the same clock, and it was blocked by "
            "the same units fault: round6 measured 0 vocabulary lifts on gc_real, and gc_fast and "
            "gc_loose lifted identically (6 each, same first step 32047), which proves the plateau "
            "condition was never the blocker -- GROW_CAP_EVERY=20000 against a 60k-step run was. Wired "
            "separately from the fabric's period because the two caps are lifted by two mechanisms and a "
            "shared field would make one of them read a value the other's package owns."),

    # --- tokenizer -> the model geometry ------------------------------------------------------------
    Coupling(
        src="TOK.vmax",
        dst="LM.d_softmax_width",
        compute=lambda r: int(r["TOK"].vmax),
        unit=U.ENTRIES,
        irreducible=True,
        why="emb.weight and head.weight have exactly this many rows. A distribution over V symbols has V "
            "logits: this is one number named twice, not two numbers that happen to agree, and no "
            "interface makes them independent. Getting it wrong is not a soft failure -- the resume "
            "geometry gate at self_organize.py:4442-4468 exists because a checkpoint built at one width "
            "cannot load into a model built at another, and the softer form (rows minted by the tokenizer "
            "but never present in the head) is the LOSS_MASK_DEAD family, where dead rows scale with "
            "VMAX and quietly take probability mass."),

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
        src=("TRAIN.batch_w", "TRAIN.accum"),
        dst="TRAIN.d_effective_batch_windows",
        compute=lambda r: max(1, int(r["TRAIN"].batch_w)) * max(1, int(r["TRAIN"].accum)),
        unit=U.COUNT,
        irreducible=True,
        why="The batch size a run actually trains at is windows per flush times flushes per optimizer "
            "step, and there is no third number. It is written down because the old tree reported the "
            "CONFIGURED one: accumulation was gated on a window counter instead of on backward passes, "
            "which measured 55 optimizer steps where 13 were due, so at ACCUM=4 the effective batch was a "
            "quarter of its label and every learning-rate result taken against that configuration was "
            "taken at a batch size other than the one it is filed under."),
]


def _owner_blocks(expert_slots, owner_buckets):
    """How many memory partitions actually exist: min(slots, owners), floored at one.

    ITS HOME IS spine/derive.py and it should move there when that file is next opened -- it is a pure
    function of two levers, which is exactly what that file is for. It sits here, defined once, because
    two couplings need it (`MEM.d_owner_blocks` and `MEM.d_capacity`) and a fold written twice is a fold
    that can disagree with itself. That is not hypothetical for this particular number: memory.py:36 and
    self_organize.py:4873 each computed the store's size their own way, and the disagreement is the 24x
    shrink the capacity coupling's reason describes.
    """
    return max(1, min(int(expert_slots), int(owner_buckets)))


# ==================================================================================================
# CANDIDATES THAT ARE NOT WIRES
#
# "If you cannot name a real reason it is NOT a wire -- it is a lever the receiving package should own."
# The rejections are written down because a rejection with a reason is the only thing that stops the same
# candidate being added next quarter by someone who cannot tell it was considered. Printed by render().
# ==================================================================================================

NOT_WIRES = (
    ("TRAIN.seed -> every package's d_seed",
     "The run seed does reach every package, but what a package needs is rng.derive_seed(name, seed), "
     "which is per-subsystem and keyed by the package's own name. Wiring it would put one near-identical "
     "edge per package into the graph and still not stop a package from deriving under the wrong name. "
     "The check that catches that is rng.issued(), which records every stream handed out, so a subsystem "
     "with zero draws reads armed-but-inert and a subsystem that never asked does not appear at all -- "
     "two different statements the report must be able to make (G4)."),

    ("TRAIN.epochs -> OPT.d_lr_horizon",
     "Rejected because it IS the defect. EPOCHS setting both the run length and the cosine horizon means "
     "two runs differing only in EPOCHS are two different learning-rate experiments, which is why "
     "units.Epochs says in as many words that it is never a schedule horizon. OPT owns its horizon as a "
     "declared lever; a run that wants them to agree sets both, and the report can then say so."),

    ("SIG.d_signature_width_bytes from DATA.win x the measured bytes/token",
     "Not resolvable at assemble: bytes_per_token is MEASURED on the corpus the tokenizer has not seen "
     "yet, and Config freezes when build() returns, so there is no late wire and there must not be one -- "
     "a Config that can still be written after startup is a Config the report cannot claim the run used. "
     "derive.signature_width_bytes is the single named function instead; the sig package calls it once, "
     "keeps the answer, and must not recompute it as the vocabulary grows. That is not a style "
     "preference: the old tree resolved the width in two places from one knob whose zero meant "
     "max(WIN, int(WIN*bpt)) = 614 bytes at self_organize.py:5675 and max(1, SIG_WIN) = 1 byte at :3919, "
     "so every eval-path routing decision in every report was made on a one-byte signature."),

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


_check_table(COUPLINGS)


# ---- build ---------------------------------------------------------------------------------------

def build(environ=None, sets=None, couplings=None, budget=None):
    """Resolve every LeverSet, run every coupling, freeze everything, return the typo-net warnings.

    Returns (configs, wires, warnings):
        configs   {PREFIX: Config}, every one frozen. Attribute access is the whole interface.
        wires     the Wires ledger, containing the CROSS couplings only -- the graph's real edges.
        warnings  list of strings, each one a thing a human should look at and none of them fatal.

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
    is registered and all ten rows defer -- that produced a docs/03_WIRING.md with an empty IRREDUCIBLE
    section and every coupling filed under DEFERRED. The document's whole job is to show which couplings
    are physics and which are choices, and it lost exactly that on the only build that currently runs.

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

    L.append("--- the ledger as the isolation sweep's oracle sees it ---")
    # wire.Wires.render, not a second table built here. wire.py's docstring is explicit about why: the old
    # tree had a report path and an audit path formatting one quantity two ways, and they drifted.
    L.append(wires.render(out=io.StringIO()))
    return "\n".join(L)
