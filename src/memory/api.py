"""MEM -- the frozen public surface. Signatures only; P4 writes the bodies.

MEM is the editable store, and it is half of goal B. Goal B is continual learning without
catastrophic forgetting, and this is the one component whose failure mode IS forgetting,
mechanically: an entry evicted is a fact deleted, and an entry evicted because nobody is currently
WRITING its domain is forgetting caused by the schedule rather than by the model. It touches
goal A through exactly two numbers -- blend_max and match_floor, the match-quality gate that
turned memory from -0.097 b/B at 200k slots into a +0.085 b/B contribution.

CAPACITY IS NOT COMPUTED HERE. It arrives already resolved as the wire MEM.d_capacity. The old
tree declared it and then memory.py:36 silently overrode it -- `if self.n_own > 1: cap = self.n_own
* self.quota` -- so a requested MEM_CAP of 200,000 became 64 x 128 = 8,192 with no line in any log.

RECORD TYPES RETURNED (P4 defines them):
  Store          the per-entry arrays (keys, tok, src, pos, ctx, own, active, prob, use, last,
                 born, selfcon, recon), the scalars (tick, gate_theta, write counter, rekey
                 cursor), nsrc/nsrc_max, live_src, and every n_* counter
  WriteReceipt   offered, kept, committed, evicted_free/probation/main, floor_blocked, gate_theta
  Retrieval      dist, conf, hits, weights, blend
  StoreCensus    what MEM.census returns, DECLARED HERE rather than left in that docstring's prose
                 (Q-MEM-11, RESOLVED 2026-09-02): counts (the per-source table), floor_entries,
                 quota_arm, pressure, probation_share, live_src, nsrc, nsrc_max, census_drift,
                 n_census_reconciles, and every store.n_* counter passed through.
                 THE FIELDS CARRY MEM'S OWN SPELLINGS AND NOT ITS CONSUMERS'. DOM.manage reads two
                 of them as `memory_counts` and `mem_floor_entries` and FAB.grow_check reads a
                 third as `memory_pressure`; those renames stay in spine/compose.py's `produces`
                 column, which is the declared and machine-read home for a rename (K10/K11). Putting
                 the consuming names on this record would prefix MEM's own fields with MEM's own
                 name -- the doubled-name defect the census already corrected once -- and would
                 invert spine/assemble.py's rule that a wire NAMES THE FIELD, NOT THE RECEIVER. It
                 is not even a function: DOM.census's `live` reaches MEM as `live_sources` while its
                 `n_live` reaches FAB as `live_domains`, so one record feeds two vocabularies.
"""
import dataclasses

import torch

from spine.lever import Config, LeverError
from spine.gate import Gate, NotBuilt
from spine import units as U


# ==================================================================================================
# THE SWITCH ON THE NEGATIVE-PERIOD REFUSAL
# ==================================================================================================

REFUSE_NEGATIVE_PERIOD = True
"""Whether rekey_period refuses a negative MEM_REKEY_EVERY. True is the shipped state; False lets
the value through to units.Windows exactly as it did before 2026-09-04.

THE RULING (owner, 2026-09-04): "On the periods, let's refuse for now. If it has a bad effect, we
can turn off the refusal." The first sentence is the guard in rekey_period; this name is the second,
which binds just as hard -- .rework/DECISIONS.md D4 rules that a thing kept for later is kept WITH A
SWITCH rather than as a code path that rots, and OFF is what is being kept.

THE ALTERNATIVES, THEIR PRICES AND THE MEASUREMENT THAT WOULD SETTLE THE CHOICE ARE WRITTEN OUT
ONCE, AT ckpt/api.py::REFUSE_NEGATIVE_PERIOD, and are not restated here: CKPT is where this question
was opened and where the first of the five refusals shipped. WHAT IS THIS FILE'S OWN, and the reason
the name is spelled here rather than imported: tests/test_ownership.py::check_o10_no_backdoor_imports
forbids MEM to import ckpt, so the five switches are five per-package policies that happen to share
a default, each governing only its own package's lever. This one governs MEM_REKEY_EVERY and nothing
else, and turning it off here leaves the other four refusing.

IT IS NOT THE OFF SWITCH FOR THE REKEY. That is MEM_REKEY_EVERY=0, which maintain declares as DISARM
and which this constant does not touch in either position; nor does it touch MEM_KEY_SRC, the other
condition maintain puts the amortized re-encode behind.

THE COST, SO IT IS NOT DISCOVERED: turning it off is a CODE EDIT. There is no
MEM_REFUSE_NEGATIVE_PERIOD, no census row and no row in the generated lever document -- deliberately,
because a lever per package would be five environment names for one decision and would make "some
accessors refuse and some do not" a reachable configuration.
"""


class StoreError(ValueError):
    """A restore that cannot be performed without losing entries, refused by name.

    NAMED AND NOT TRUNCATED. Lowering MEM_OWNERS between a parent run and its resume leaves entries
    whose recorded block no longer exists; the old path kept whatever fitted in SAVE ORDER, so which
    memories survived a resume was a function of the order they happened to be written in, and the
    report said nothing. In a system whose goal-B claim is measured ACROSS a resume boundary, that is
    the measurement quietly changing under the thing being measured.
    """


class Store:
    """The entry arrays, the block partition, and the source census.

    ONE BLOCK LAYOUT AND NO SPECIAL CASE FOR owners == 1. Block b owns rows [b*quota, (b+1)*quota),
    and one block covering the store is just b == 0. A second code path for the single-owner case is
    a path that only runs on one configuration, which is how the single-owner arm drifted from the
    partitioned one.

    `born` IS A SEPARATE FIELD FROM `last`, AND THE SPLIT IS THE POINT. The old tree used one `last`
    for the write tick and the retrieval tick, so "LRU" meant write-recency: the domain that STOPPED
    BEING WRITTEN was evicted oldest-first BY CONSTRUCTION. That is goal B's failure mode performed
    by the eviction rule itself -- the store forgets exactly the area the run has moved on from,
    which is the area a continual-learning measurement is about.
    SO write STAMPS `born` AND LEAVES `last` AT 0. A fresh entry that stamped `last` would be back in
    write-recency the moment eviction ranked on it, which is the whole defect; 0 reads as "never
    retrieved", which is also exactly what `prob` says, and probation -- whose members are by
    construction never-retrieved -- is ranked on `born`, its own oldest. Both clocks are the WINDOW
    clock: write and maintain both carry `now`, and `tick` is advanced to it, so "born at window 120,
    last retrieved at window 400" is a sentence the report can write. The rejected alternative was an
    internal per-call counter (the old tree's `self.tick += 1`), which is finer-grained inside one
    flush and means nothing to any reader.

    `ctx` IS THE STORED CONTEXT WINDOW, (capacity, ctx_w), AND IT WAS ONE LONG PER ENTRY UNTIL THE
    REKEY WAS WRITTEN. maintain's job 2 re-encodes stored entries so the keys track a model that
    moves underneath them, and there is nothing to re-encode FROM unless the entry keeps the token
    window its key was built from. The frozen tree kept exactly that and for exactly this reason --
    memory.py:121-123, `if self.ctx_w > 0: self.ctx = torch.zeros(cap, self.ctx_w, ...)` under the
    comment "store a raw context window per entry so keys can be RE-ENCODED (drift fix)", filled by
    archive/garry/self_organize.py:353 `mem_ctx(x) = _windows(x, KW).reshape(-1, KW) if KEY_SRC ==
    "model" else None`. With one long per entry the amortized rekey is not a mechanism that declines
    to run, it is a mechanism that cannot exist, and key drift is a forgetting channel that has
    nothing to do with eviction -- goal B, directly.
    ITS WIDTH IS ALLOCATED BY write AND NOT HERE, and that is not tidiness: the width is MEM_KEY_WIN,
    and open_store's frozen LEVERS READ line names quota, owners, key_src and key_depth and says in
    as many words that the ten others "were never read by THIS entry point's body". write and
    maintain both name key_win in their own LEVERS READ lines, so the first write grows the array to
    its width the way the census grows on demand, and a store that has never been written carries
    (capacity, 0).

    `use` IS A FLOAT AND WAS A LONG, which is a type error the decay makes visible rather than a
    preference. MEM_USE_DECAY's own help calls `use` "decayed retrieval mass" and the eviction lever
    calls it the same; a mass multiplied by 0.98 is not an integer. Measured on the declared dtype:
    `torch.zeros(3, dtype=torch.long).mul_(0.98)` raises "result type Float can't be cast to the
    desired output type Long", and the out-of-place spelling truncates instead -- every entry with
    exactly one retrieval goes to 0 at the first decay, so the rule that exists to FADE retrieval
    mass wipes it. The frozen tree wrote `self.use[idx] = 0.0` into a float array (memory.py:489).

    `gate_seeded`, `rekey_snap` and `gen` ARE THE THREE PIECES OF STATE THE TWO CADENCED BODIES NEED
    AND THE OLD RECORD HAD NOWHERE TO PUT. `gate_seeded` says whether gate_theta has been initialised
    from this run (the quantile arm seeds from the first batch, the additive arm from MEM_WRITE_GATE)
    and it is CHECKPOINTED, because a resumed run that re-seeds writes against a different admission
    bar than the one it stopped with -- ISSUES:537, the same defect gate_theta itself was restored
    for. `rekey_snap` is the snapshot job 2 walks, held so that entries written DURING a pass cannot
    shift the indexing out from under it; it is deliberately NOT checkpointed and is retaken after a
    resume. `gen` is ONE torch.Generator per store, built once here: spine/rng.py::Rng.torch_generator
    RE-SEEDS A FRESH GENERATOR ON EVERY CALL, so calling it per write would draw the identical victim
    pool every time -- a sampler that samples one sample.
    """

    __slots__ = ("keys", "tok", "src", "pos", "ctx", "ctx_w", "own", "active", "prob", "use",
                 "last", "born", "selfcon", "recon", "tick", "gate_theta", "gate_seeded",
                 "n_written", "rekey_cursor", "rekey_snap", "nsrc", "nsrc_max", "live_src",
                 "capacity", "quota", "owners", "key_dim", "lm_kind", "counters", "gates", "rng",
                 "gen")

    def __init__(self, *, capacity, quota, owners, key_dim, device, rng, lm_kind):
        z = lambda *shape, dtype=torch.float32: torch.zeros(*shape, dtype=dtype, device=device)
        self.capacity, self.quota, self.owners = capacity, quota, owners
        self.key_dim, self.lm_kind, self.rng = key_dim, lm_kind, rng
        self.keys = z(capacity, key_dim)
        self.tok = z(capacity, dtype=torch.long)
        self.src = z(capacity, dtype=torch.long)
        self.pos = z(capacity, dtype=torch.long)
        # WIDTH 0 UNTIL THE FIRST WRITE. See the class docstring: the width is MEM_KEY_WIN and
        # open_store may not read it, so `write` grows this array once, the way the census grows.
        self.ctx_w = 0
        self.ctx = z(capacity, 0, dtype=torch.long)
        self.own = z(capacity, dtype=torch.long)
        self.active = z(capacity, dtype=torch.bool)
        self.prob = z(capacity, dtype=torch.bool)
        self.use = z(capacity)                         # DECAYED RETRIEVAL MASS -- float, see above
        self.last = z(capacity, dtype=torch.long)      # RETRIEVAL tick
        self.born = z(capacity, dtype=torch.long)      # WRITE tick -- see the class docstring
        self.selfcon = z(capacity)
        self.recon = z(capacity)
        for b in range(owners):
            self.own[b * quota:(b + 1) * quota] = b
        self.tick = 0
        self.gate_theta = 0.0
        # FALSE MEANS gate_theta HAS NEVER BEEN SET BY THIS STORE, which is a different statement
        # from "it is 0.0" -- 0.0 is a legal admission bar (write_gate=0.0 stores every candidate).
        # The quantile arm seeds it from the first batch it sees and the additive arm from
        # MEM_WRITE_GATE; a resume must not do either again, so this flag is checkpointed beside
        # gate_theta itself.
        self.gate_seeded = False
        self.n_written = 0
        self.rekey_cursor = 0
        self.rekey_snap = None          # the re-encode snapshot; NOT checkpointed, retaken on resume
        self.nsrc = None                # the census; sized by open_store, GROWS on demand
        self.nsrc_max = 0
        self.live_src = 0
        self.counters = {}
        self.gates = ()
        # ONE GENERATOR PER STORE, DRAWN ONCE. Rng.torch_generator() manual_seeds a FRESH generator
        # from the subsystem name on every call, so a per-write call would hand the victim sampler
        # the same draw sequence every time -- measured as the identical candidate pool on two
        # consecutive calls. Every stochastic choice in this package comes off this stream and never
        # off the global torch one.
        self.gen = rng.torch_generator(device=device)

    def _block_of(self, row):
        return int(row) // self.quota

    def _rows_of(self, block):
        return range(block * self.quota, (block + 1) * self.quota)


def open_store(mem: Config, *, key_dim, vocab_slots, device, rng, lm_kind, restored=None):
    """Allocate the store, or restore one from a checkpoint blob.

    Allocates d_capacity rows. Blocks are d_owner_blocks contiguous runs of `quota` rows; block b
    owns rows [b*quota, (b+1)*quota). owners == 1 collapses to ONE block covering the store, AND
    THERE IS NO SECOND CODE PATH FOR THAT CASE. The source census is d_source_slots rows wide AND
    GROWS ON DEMAND -- it is never clamped, which is the exact pattern rebuild_census's own
    docstring identifies as a re-break (M74/M75).

    NOT A SIZE ARGUMENT ANYWHERE: the operator sizes the store through `quota` and `owners`, and
    nothing here can silently override a number somebody typed.

    `born` (write tick) IS A NEW FIELD BESIDE `last` (retrieval tick). The old tree used one `last`
    for both, and that conflation is what made "LRU" mean write-recency -- so the domain that
    STOPPED BEING WRITTEN was evicted oldest-first by construction, which is goal B's failure mode
    performed by the eviction rule.

    `restored` is the blob state_dict() returned. RESTORE IS BY OWNER BLOCK ONLY -- there is no
    bulk prefix copy and no unconditional `active[:n] = True` (H21/H29). Rows whose recorded block
    no longer exists (owners lowered) are REFUSED with a named error rather than truncated in save
    order (M50). Restore rebuilds the census EXACTLY -- a resume left it at zeros and the floor
    protected nothing for the rest of the run while the banner printed "src floor 0.5" and
    selftest.sh asserted that line was present (C16) -- and carries nsrc_max forward from the blob
    rather than re-deriving it from the restored counts (M53/M67). `recon`/`selfcon` per entry and
    `gate_theta` store-wide are ALSO restored (M66, ISSUES:537) -- the other two of the four
    checkpointed additions docs/04_CONTRACT.md's MEM section names, alongside `prob` and
    `nsrc_max` above; before this fix both silently reset to zero at every resume boundary.

    `lm_kind` is stored ONLY so the key_depth Gate can print its own arithmetic; nothing else reads
    it. `rng` is one spine.rng.Rng for the subsystem "memory"; every stochastic choice draws from
    it, never from the global torch stream.

    TWO LEVERS ARE REFUSED BELOW 1 BEFORE ANYTHING IS DERIVED FROM THEM HERE. MEM_QUOTA and
    MEM_OWNERS are the store's only two degrees of freedom and neither declares a meaning for 0.
    Unrefused, MEM_QUOTA=0 allocates the whole store with zero rows and MEM_OWNERS=0 is silently
    folded to 1 by spine/assemble.py::_owner_blocks, taking capacity from 8192 to 128 with nothing
    said. The refusal names the lever, the resolved integer and the raw string the environment
    supplied; it is a range refusal and carries NO switch, following lm/api.py::resolve,
    opt/api.py::build and capacity/api.py::new_valve. IT CLOSES ONE DIRECTION AND NOTHING MORE --
    see the block itself for what it does not claim, and note that it does not touch MEM_KEY_DEPTH,
    MEM_REKEY_EVERY, MEM_PROBE_EVERY, MEM_BLEND_MAX, MEM_SRC_SHARE or MEM_JUDGE_FRAC, six MEM levers
    for which 0 IS a declared meaning and two of which are shipped defaults.

    LEVERS READ: quota, owners, key_src, key_depth (owners is read HERE, at the refusal above the
                 wires, AND by spine/assemble.py to compute d_capacity and d_owner_blocks -- this
                 line used to say this package "never reads it directly", which was true until the
                 refusal landed and is the sentence that had to change with it. The other ten of the
                 fourteen this line once claimed -- key_win, evict, probation_frac, src_share,
                 verify, recon_hid, recon_tok, topk, write_mode, write_gate -- are consumed by
                 write/read/maintain/judge, each of which already names them in its own LEVERS READ
                 line, and were never read by THIS entry point's body: trimmed rather than left as a
                 claim this function's own code cannot back)
    WIRES READ: d_capacity, d_owner_blocks, d_source_slots
    DID IT FIRE: store.n_opened, store.n_restored_entries, store.n_restore_refused
    """
    mem = mem.owned_by("MEM")

    # ==============================================================================================
    # THE STORE'S TWO GEOMETRY LEVERS, REFUSED BELOW 1 AT MEM'S OWN FIRST READ
    # ==============================================================================================
    # WHAT IS REFUSED IS `< 1` ON TWO INT LEVERS AND NOTHING ELSE, AND THIS BODY DOES NOT CLAIM
    # OTHERWISE. It closes a half-line on each of MEM_QUOTA and MEM_OWNERS. It says nothing about the
    # other end: MEM_QUOTA=10**9 still asks Store.__init__ for 64 billion rows and the refusal here
    # will not stop it, and no lever on this surface carries a declared upper bound. After this block
    # neither lever is safe, bounded or validated; each is one direction less open. The general answer
    # is a declared per-lever domain and it is the owner's open question, not this function's.
    #
    # IT IS NOT THE FIRST READ IN THE TREE AND SAYING SO IS PART OF THE REFUSAL. spine/assemble.py's
    # MEM.d_capacity and MEM.d_owner_blocks couplings read both levers during spine/assemble.py::build,
    # before any Config is frozen and long before this function runs, and they do not refuse -- they
    # FOLD, through spine/assemble.py::_owner_blocks. This guard is the range check MEM owes its OWN
    # two levers at its own first read, in MEM's words, and it is the same second line
    # fabric/api.py::manage_period keeps for FAB_MANAGE_EVERY beside the assembly's arithmetic: a
    # refusal that lives only in another package's coupling table is a refusal that disappears when
    # that row is edited, with nothing saying so.
    #
    # WHY THE SPINE'S FOLD IS NOT THE PLACE TO FIX IT, measured rather than assumed:
    # `max(1, min(int(expert_slots), int(owner_buckets)))` has a SECOND job. memory/levers.py::MEMLevers
    # declares it -- "the d_owner_blocks fold already collapses to 1 block when FAB.slots is 0, so
    # fabric-off degrades correctly with no second knob and no AND" -- so deleting the max(1, ...)
    # there would take the fabric-off degradation with it. The rewrite of a MEM lever and the
    # degradation of a FAB one share one expression, and only the lever half is wrong. So the refusal
    # belongs on the lever, here.
    #
    # NO SWITCH, AND THAT IS DELIBERATE. ckpt/api.py::REFUSE_NEGATIVE_PERIOD says in its own words that
    # a range refusal getting a switch "is NOT a precedent", and names lm/api.py::resolve,
    # opt/api.py::build and capacity/api.py::new_valve as refusing out-of-range lever values with no
    # switch of any kind. This is a range refusal on two counts and it follows those three. The
    # switch this file DOES carry, REFUSE_NEGATIVE_PERIOD above, governs MEM_REKEY_EVERY and nothing
    # else, and it does not reach here in either position.
    #
    # ZERO IS NOT A SENTINEL ON EITHER OF THESE TWO, AND IT IS ON FOUR OF THEIR NEIGHBOURS, WHICH IS
    # WHY THIS IS TWO NAMES AND NOT A SWEEP OVER MEM'S INT LEVERS. MEM_KEY_DEPTH=0 is "the full stack"
    # in its own help text AND is the shipped default; MEM_REKEY_EVERY=0 is the declared DISARM
    # (memory/api.py::maintain, memory/api.py::rekey_period). MEM_PROBE_EVERY=0 disarms every
    # retrieval-based rule and memory/levers.py::MEMLevers says "the report must say so";
    # MEM_BLEND_MAX=0, MEM_SRC_SHARE=0 and MEM_JUDGE_FRAC=0 are three more declared arms, the last of
    # them also a shipped default. A rule over 0 that did not read each declaration would refuse the
    # configuration this tree ships. `quota` and `owners` declare no meaning for 0 at all: quota is
    # "entries each owner block may hold" and owners is "how many eviction partitions the store is
    # split into; 1 is the single global store".
    #
    # A NON-INTEGRAL VALUE ARRIVES HERE ALREADY TRUNCATED AND IS CAUGHT BY THE SAME TEST.
    # spine/lever.py::Lever.coerce resolves an int lever as `int(float(raw))`, so MEM_QUOTA=0.4 is
    # cfg.quota == 0 with build() returning no warning while Config.given() still reports '0.4'. That
    # is one of the values this refusal names, and it names the RESOLVED integer beside the raw string
    # so the two are visibly different.
    _quota, _owners = int(mem.quota), int(mem.owners)
    if _quota < 1 or _owners < 1:
        _q_env, _o_env = mem.lever("quota").env_name, mem.lever("owners").env_name
        _given = mem.given()
        # THE WIRES ARE PRINTED AS THEY ACTUALLY ARRIVED ON THIS CONFIGURATION, not as the shipped
        # defaults would have made them. The whole complaint on the owners arm is that the frozen
        # Config and the running store disagree, and a message quoting the DEFAULT arithmetic
        # instead of this run's would be the same class of claim one level up.
        _cap_w, _blk_w = int(mem.d_capacity), int(mem.d_owner_blocks)
        raise LeverError(
            f"MEM: {_q_env}={_quota} and {_o_env}={_owners} -- "
            + " AND ".join(
                ([f"{_q_env}={_quota} is not a number of entries"] if _quota < 1 else [])
                + ([f"{_o_env}={_owners} is not a number of partitions"] if _owners < 1 else []))
            + ". These two are the store's ONLY two degrees of freedom -- capacity is derived from "
              f"them and is not declared -- and this store is the component whose failure mode IS "
              f"forgetting, so a geometry nobody can write into is goal B switched off by arithmetic. "
            + (f"WHAT {_q_env} DOES BELOW 1 TODAY, AT THE VALUE {_quota} IS ON: at 0 the whole "
               f"editable store is allocated with ZERO rows and NOTHING raises, warns or declares. "
               f"On THIS configuration the wires arrived as MEM.d_capacity={_cap_w} over "
               f"MEM.d_owner_blocks={_blk_w}; measured through spine.assemble.build at MEM_QUOTA=0 "
               f"beside the shipped MEM_OWNERS=64 that is d_capacity 0 over 64 blocks, keys.shape "
               f"(0, 128), and counters reading store.n_opened: 0 beside store.blocks: 64 -- "
               f"sixty-four owner blocks that can hold nothing. The `capacity != owners * quota` "
               f"guard immediately below this one exists to stop 'one quantity, two answers' after "
               f"the 24x silent shrink recorded as E7.40 'with no line in any log'; at quota=0 it is "
               f"SATISFIED BY AN IDENTITY (0 == 64 * 0) and the shrink is total rather than 24x. MEM "
               f"declares no `enabled` lever, so 0 is an undeclared off switch for the whole "
               f"mechanism, and Store._block_of is `int(row) // self.quota`, a division by it. Below "
               f"0 there is no named refusal either: at MEM_QUOTA=-5 the wire is d_capacity=-320 and "
               f"torch raises 'RuntimeError: zeros: Dimension size must be non-negative' from inside "
               f"Store.__init__, naming no lever, no value and no package. MEM_QUOTA=1 is a "
               f"one-entry block and is in range. " if _quota < 1 else "")
            + (f"WHAT {_o_env} DOES BELOW 1 TODAY, AT THE VALUE {_owners} IS ON: it is SILENTLY "
               f"REWRITTEN TO 1. "
               f"spine/assemble.py::_owner_blocks folds it as `max(1, min(int(expert_slots), "
               f"int(owner_buckets)))`, so the frozen Config answers mem.owners == {_owners} while "
               f"MEM.d_owner_blocks == {_blk_w} and MEM.d_capacity == {_cap_w} -- measured at the "
               f"shipped MEM_QUOTA=128 that is a store of 128 against 8192, a 64x shrink with no "
               f"refusal, no warning and no report line, and "
               f"the printed configuration and the running one disagreeing about the number that "
               f"sets the store's size. That is the shape train/api.py::startup_refusals already "
               f"refuses one package over for RUN_EPOCHS=0, on the ground that 'a coercion at read "
               f"time that makes a printed number a lie' is a refusal and not a repair. IT REMOVES "
               f"NO CONFIGURATION: memory/levers.py::MEMLevers declares owners=1 as 'the single "
               f"global store', and MEM_OWNERS=0, MEM_OWNERS=-5 and MEM_OWNERS=1 were measured to "
               f"open the BYTE-IDENTICAL store (capacity=128, quota=128, owners=1, blocks=1), so 1 "
               f"already spells everything 0 could mean and spells it without the rewrite. " if _owners < 1 else "")
            + f"REFUSED AT STARTUP AND NOT DESCRIBED BY A GATE, because a Gate reason is a report and "
              f"the mechanism still runs: unrefused, this function returns a Store on BOTH values "
              f"and prints 'Gate mem.key_depth: UNREACHABLE (0 vs 0)' beside it -- measured at "
              f"MEM_QUOTA=0 over a store with no rows at all, and at MEM_OWNERS=0 over a store 64x "
              f"smaller than the one the operator asked for. A confident verdict about a knob, over "
              f"a geometry the report never mentions. WHAT THIS REFUSAL DOES NOT CLAIM: it closes "
              f"`< 1` on two levers and leaves the mechanism open in the other direction -- neither "
              f"lever declares an upper bound anywhere, so MEM_QUOTA=10**9 still asks "
              f"Store.__init__ for 64 billion rows, and MEM_OWNERS above FAB_SLOTS still folds "
              f"silently through the same min() this refusal does not touch. A declared per-lever "
              f"domain is the general answer and it is open. WHAT THE ENVIRONMENT SUPPLIED, so a "
              f"truncation is visible rather than inferred: "
            + ", ".join(f"{k}={v!r}" for k, v in sorted(_given.items())
                        if k in ("quota", "owners")) + ".")

    capacity = int(mem.d_capacity)                     # WIRES READ HERE -- the shape
    owners = int(mem.d_owner_blocks)
    source_slots = int(mem.d_source_slots)
    quota = int(mem.quota)

    # NOT A SIZE ARGUMENT ANYWHERE. The operator sizes the store through `quota` and `owners`, and
    # d_capacity is DERIVED from exactly those two by the coupling table -- so nothing here can
    # silently override a number somebody typed, which is what the old `if n_own > 1: cap = n_own *
    # quota` did to a requested MEM_CAP of 200,000 (a 24x shrink, recorded with no line in any log).
    if capacity != owners * quota:
        raise StoreError(
            f"MEM.d_capacity arrived as {capacity} while MEM_OWNERS={owners} x MEM_QUOTA={quota} is "
            f"{owners * quota}. A partitioned store holds blocks x quota entries and has no size "
            f"independent of its partition; one quantity, two answers.")

    store = Store(capacity=capacity, quota=quota, owners=owners, key_dim=int(key_dim),
                  device=device, rng=rng, lm_kind=str(lm_kind))
    # THE CENSUS GROWS ON DEMAND AND IS NEVER CLAMPED. d_source_slots is a starting width, not a
    # bound: clamping ids into a fixed-width table is the exact pattern that re-broke this at the
    # scale it was written for -- the table was 64 rows wide on every default run while a real one
    # carried 125 source ids.
    store.nsrc = torch.zeros(source_slots, dtype=torch.long, device=device)

    n_restored, n_refused = 0, 0
    if restored is not None:
        n_restored, n_refused = _restore_by_block(store, restored)

    store.counters = {
        "store.n_opened": capacity,
        "store.n_restored_entries": n_restored,
        "store.n_restore_refused": n_refused,
        "store.blocks": owners,
        "store.census_slots": source_slots,
    }
    store.gates = (
        # `lm_kind` IS STORED ONLY SO THIS GATE CAN PRINT ITS OWN ARITHMETIC; nothing else reads it.
        Gate("mem.key_depth", int(mem.key_depth) > 0, int(mem.key_depth), 0)
        if str(mem.key_src) == "model" and str(lm_kind) == "transformer" else
        Gate("mem.key_depth", False, int(mem.key_depth), 0, reachable=False,
             reason=f"MEM_KEY_SRC={str(mem.key_src)!r} on LM_ARCH={str(lm_kind)!r}: there is no "
                    f"layer stack to take a depth from, so this knob cannot select anything. "
                    f"Reported unreachable rather than as a depth of 0, which would read as a "
                    f"choice the operator made."),
    )
    return store


def _restore_by_block(store, blob):
    """Put a checkpoint's entries back BY OWNER BLOCK. Returns (restored, refused).

    NO BULK PREFIX COPY AND NO UNCONDITIONAL active[:n] = True. The old restore cleared `active`,
    rebuilt the owner blocks, and then six lines later ran `mem.active[:_mn] = True` in BOTH
    branches -- reactivating the first rows regardless of ownership and undoing the partition
    restore it had just performed.

    A ROW WHOSE BLOCK NO LONGER EXISTS IS REFUSED, NOT TRUNCATED. Lowering MEM_OWNERS makes some
    recorded blocks unreachable; keeping whatever fitted in save order made the surviving memories a
    function of write order, silently, on the boundary every goal-B number is measured across.
    """
    rows = blob.get("rows") or []
    restored, refused = 0, 0
    # THE STORED CONTEXT WINDOW COMES BACK AT THE WIDTH IT WAS SAVED AT, and the width is carried in
    # the blob rather than re-derived from this run's MEM_KEY_WIN. Re-deriving it would silently
    # reshape somebody else's tokens: a run saved at key_win=8 and resumed at key_win=16 would have
    # its 8-token contexts read as half of a 16-token one, and the rekey would then re-encode
    # nonsense into the live key space. memory/api.py::write is where a width change is REFUSED, by
    # name, because that is where MEM_KEY_WIN may be read.
    _cw = int(blob.get("ctx_w", 0))
    if _cw != int(store.ctx_w):
        store.ctx_w = _cw
        store.ctx = torch.zeros(int(store.capacity), _cw, dtype=torch.long,
                                device=store.keys.device)
    for r in rows:
        b = int(r.get("own", -1))
        if not 0 <= b < store.owners:
            refused += 1
            continue
        # Into the recorded block, at the first free row OF THAT BLOCK.
        free = next((i for i in store._rows_of(b) if not bool(store.active[i])), None)
        if free is None:
            refused += 1
            continue
        store.keys[free] = torch.as_tensor(r["key"], device=store.keys.device)
        for field in ("tok", "src", "pos"):
            getattr(store, field)[free] = int(r.get(field, 0))
        # `ctx` IS A ROW, NOT A SCALAR, and it is restored only at the width this blob declares. A
        # row of the wrong length is a geometry disagreement inside one file and is refused with the
        # same argument as the owner-block refusal above: a restore that quietly keeps part of an
        # entry makes what survives a resume a function of what fitted.
        if store.ctx_w:
            _c = r.get("ctx") or []
            if len(_c) != store.ctx_w:
                raise StoreError(
                    f"a checkpoint entry carries a {len(_c)}-token context window against the "
                    f"blob's declared ctx_w={store.ctx_w}. The stored window is what "
                    f"MEM.maintain re-encodes keys from, so a partial one is a key in a space "
                    f"nothing else is in.")
            store.ctx[free] = torch.as_tensor(_c, dtype=torch.long, device=store.ctx.device)
        store.own[free] = b
        store.active[free] = True
        store.prob[free] = bool(r.get("prob", False))
        store.use[free] = float(r.get("use", 0.0))   # DECAYED MASS -- see Store's docstring
        store.last[free] = int(r.get("last", 0))
        store.born[free] = int(r.get("born", 0))
        # `recon` AND `selfcon` ARE TWO OF THE FOUR CHECKPOINTED ADDITIONS docs/04_CONTRACT.md
        # names as fixed (M66 for recon) -- but the field-by-field restore above stopped at `born`
        # and never read either back from the row, so every resume reset both to Store.__init__'s
        # zero default regardless of what judge() had measured before the checkpoint. selfcon==0.0
        # (rather than judge's -1 "unchecked" sentinel) after a restore is itself the tell: a
        # freshly-opened store and a resumed one were indistinguishable to the wrongness detector,
        # which is exactly the M66/H32 shape this restore exists to close.
        store.recon[free] = float(r.get("recon", 0.0))
        store.selfcon[free] = float(r.get("selfcon", 0.0))
        restored += 1
        # THE CENSUS IS REBUILT EXACTLY. A resume left it at zeros and the source floor protected
        # nothing for the rest of the run while the banner still printed "src floor 0.5" and a
        # selftest asserted that line was present.
        sid = int(r.get("src", 0))
        if sid >= store.nsrc.numel():
            grown = torch.zeros(sid + 1, dtype=store.nsrc.dtype, device=store.nsrc.device)
            grown[:store.nsrc.numel()] = store.nsrc
            store.nsrc = grown
        store.nsrc[sid] += 1
    if refused:
        raise StoreError(
            f"{refused} checkpoint entr(y/ies) name an owner block this run does not have "
            f"(MEM_OWNERS={store.owners}, quota={store.quota}). Refused rather than truncated: "
            f"keeping whatever fitted in save order makes which memories survive a resume a "
            f"function of write order, on the boundary every continual-learning number in this "
            f"project is measured across.")
    store.tick = int(blob.get("tick", 0))
    store.n_written = int(blob.get("n_written", 0))
    # THE REKEY CURSOR WAS SAVED AND NEVER READ BACK until the rekey was written: state_dict has
    # carried `rekey_cursor` since it was written, and nothing on this side assigned it, so every
    # resume restarted the amortized re-encode at row 0 and the tail of the store waited a whole
    # pass longer than the operator asked for. The snapshot it indexes is NOT checkpointed -- it is
    # retaken on the first maintain after a resume, and MEM.maintain clamps this cursor into the
    # retaken snapshot rather than trusting a number taken against a different one.
    store.rekey_cursor = int(blob.get("rekey_cursor", 0))
    # nsrc_max IS CARRIED FORWARD from the blob rather than re-derived from the restored counts:
    # re-deriving it forgets every source that was evicted before the save.
    store.nsrc_max = int(blob.get("nsrc_max", int(store.nsrc.max()) if store.nsrc.numel() else 0))
    store.live_src = int((store.nsrc > 0).sum())
    # gate_theta IS THE FOURTH OF THE FOUR CHECKPOINTED ADDITIONS docs/04_CONTRACT.md's MEM section
    # names as fixed and, until this fix, was the one never actually wired: Store.__init__'s literal
    # 0.0 default survived every restore untouched. gate_theta is the adaptive write-admission floor
    # `write` evolves IN WINDOW ORDER (open_store's own docstring); resuming at 0.0 instead of the
    # threshold the run stopped with is a resumed run writing against a different admission bar than
    # the one measured up to the checkpoint, which is exactly the boundary goal B's forgetting
    # numbers are measured across. Restored from the BLOB TOP LEVEL, not per-row: it is a store-wide
    # scalar, alongside tick/n_written/nsrc_max above.
    store.gate_theta = float(blob.get("gate_theta", 0.0))
    # AND THE FLAG THAT SAYS THE RESTORED gate_theta IS A MEASUREMENT AND NOT A DEFAULT. Restoring
    # the number without it leaves the quantile arm free to re-seed from the first batch after the
    # resume and the additive arm free to reset to MEM_WRITE_GATE, which puts the run back on a
    # different admission bar than the one it stopped with -- the whole of ISSUES:537, arriving one
    # field later. A blob written before this field existed reads as "not seeded", which is the
    # conservative arm: it re-seeds once, exactly as that tree did.
    store.gate_seeded = bool(blob.get("gate_seeded", False))
    return restored, refused




# ==================================================================================================
# THE SURPRISE CONTROLLER'S THREE NUMBERS, WHICH ARE NOT LEVERS AND SAY SO HERE
# ==================================================================================================

GATE_STEP, GATE_FLOOR, GATE_CEIL = 0.02, 0.0, 0.95
"""The step, floor and ceiling of the non-fixed write gates. Module constants, with no env name.

THEY ARE THE SHIPPED FORM OF THE TREE THIS IS PORTED FROM -- memory.py:24, `gate_step=0.02,
gate_floor=0.0, gate_ceil=0.95` -- and they are NOT levers because the census did not carry them:
memory/levers.py's own accounting is "21 rename + 3 keep -> 24 levers declared, 8 drop", and MEM_GATE
is one of the eight. Adding three environment names here would be minting levers the census refused,
in the file that is supposed to implement its decision.

WHAT EACH ONE IS FOR, so a reader can judge the numbers rather than the names. GATE_CEIL is the one
with a measurement behind it: with V=16384 and an undertrained model, surprise is 1 - p_model and
sits near 1.0 almost everywhere, so the additive controller drives gate_theta straight INTO the
ceiling -- the kept fraction ran 1.00 / 0.93 / 0.80 against a requested 0.12 and the store filled by
step ~831 instead of ~6510 (memory/levers.py::MEMLevers, at its `write_gate` declaration). The ceiling is what stops it starving
writes entirely; it is not what makes the arm work, and the quantile arm exists because nothing does.
GATE_STEP is both the controller's step and the quantile arm's EMA rate, which is the one place this
port differs in shape from nothing -- the frozen tree used the same `gate_step` field for both
(memory.py:145, :150), and splitting it here would be a second number nobody measured.

TURNING THEM IS A CODE EDIT, and that is the same standing REFUSE_NEGATIVE_PERIOD above has: a
lever per number would be three more environment names for a controller the shipped configuration
does not even select (MEM_WRITE_MODE defaults to "fixed", so at the defaults these three are read
by nothing -- the `mem.write_target` Gate declared in write() prints exactly that).
"""


@dataclasses.dataclass(frozen=True)
class WriteReceipt:
    """What one flush's write did, in the eight numbers this module's header declares.

    FROZEN, for the reason train/api.py freezes Tick and spine/loop.py freezes RunResult: a caller
    that can write to this can change what the run reported.

    `offered` and `committed` ARE THE PAIR, and neither means anything alone. offered is every
    candidate row the flush presented, committed is what is in the store at the end of it, and the
    RATIO is the kept fraction the adaptive and quantile arms claim to control -- the number that ran
    1.00 / 0.93 / 0.80 against a requested 0.12 while the report printed the request. `kept` is the
    middle term the pair cannot show: what survived the surprise gate BEFORE the per-block quota
    truncated it, so `kept - committed` is the truncation and `offered - kept` is the gate.

    `gate_theta` IS ON THE RECEIPT because on two of the three arms it is the thing that decided, and
    it moves every window. A receipt that printed the kept fraction without the bar it was taken
    against would be the same claim-without-arithmetic spine/gate.py::Gate exists to refuse.
    """
    offered: int
    kept: int
    committed: int
    evicted_free: int
    evicted_probation: int
    evicted_main: int
    floor_blocked: int
    gate_theta: float


def _bump(store, key, n=1):
    """One counter, one place. `store.counters` is the DID IT FIRE surface MEM.census passes through."""
    store.counters[key] = store.counters.get(key, 0) + n


def _declare_gates(store, gates):
    """Put these gates on the store, replacing any of the SAME NAME and keeping every other one.

    THE GATES ARE NOT ALL DECLARED AT BUILD AND THIS IS WHY. G4 asks for a gate to be declared where
    its arm is decided; for MEM that is mostly `open_store`, and the mem.key_depth gate is there. It
    cannot be ALL of them: open_store's frozen LEVERS READ line names quota, owners, key_src and
    key_depth and states in as many words that the other ten "were never read by THIS entry point's
    body". write_mode, write_target, evict, use_decay, probe_every and rekey_every are six of those
    ten, so declaring their arms at build would mean open_store reading six levers its own contract
    says it does not read -- trading a true sentence about ownership for an earlier line in a report.
    They are declared at the first read of the lever instead, which is inside write and maintain, and
    REFRESHED on every call so the verdict is this run's and not the first flush's.
    """
    names = {g.name for g in gates}
    store.gates = tuple(g for g in store.gates if g.name not in names) + tuple(gates)


def _require_rows(name, t, shape, what):
    """A shape refusal that names the argument, both shapes and what the argument is FOR.

    NOT A RESHAPE AND NOT A BROADCAST. Every one of write's six per-row arguments is a different
    quantity about the same rows, and the two that are per-WINDOW (sources, owners) differ from the
    four that are per-POSITION by exactly one dimension -- so a silently broadcast argument writes
    every entry of a flush with window 0's domain id, which is a provenance error the per-source
    floor then protects the wrong source against.
    """
    if not torch.is_tensor(t) or tuple(t.shape) != tuple(shape):
        got = tuple(t.shape) if torch.is_tensor(t) else type(t).__name__
        raise StoreError(
            f"MEM.write: `{name}` arrived as {got} where {tuple(shape)} is required -- {what}. "
            f"Refused rather than reshaped: the six per-row arguments are six different quantities "
            f"about the same rows, and a broadcast one writes a whole flush under one window's "
            f"provenance.")


def _key_windows(contexts, key_win):
    """(B, L) token ids -> (B, L, key_win): for each position, the key_win positions ENDING at it.

    THE SPELLING IS THE FROZEN TREE'S, verbatim in shape: `_windows(x, W) = F.pad(x, (W - 1, 0))
    .unfold(1, W, 1)` (archive/garry/self_organize.py:344). The left pad is what makes the first
    positions of a window keyable at all; padding with token id 0 is the same choice that tree made
    and is visible in the stored context, which is what `ctx` being a real window buys.
    """
    return torch.nn.functional.pad(contexts, (key_win - 1, 0)).unfold(1, key_win, 1)


def _encode_keys(key_fn, rows, key_depth):
    """(N, key_win) token ids -> (N, key_dim) unit-norm keys, through the caller's encoder.

    `n_layers` IS THE SPELLING AND `depth` IS NOT. maintain's docstring writes the call as
    `key_fn(..., depth=key_depth)`; the callable is LM.encode partially applied
    (spine/compose.py::_key_fn, `lambda x, **kw: lm_api.encode(lm, model, x, **kw)`) and its keyword
    is `n_layers` -- docs/04_CONTRACT.md's LM section spells the join `n_layers <- MEM's key_depth`.
    Written once here so the write path and the rekey cannot disagree about it.

    0 IS "THE FULL STACK" AND IS PASSED AS None, not as 0. MEM_KEY_DEPTH's own help says 0 means the
    whole stack; passing the 0 through would ask the encoder for zero blocks, which is the shape of
    every off-by-a-sentinel this file refuses elsewhere.

    UNDER no_grad, AND THE LAST POSITION IS THE KEY. The frozen tree's `_model_key(win) =
    model.encode(win)[:, -1]` (archive/garry/self_organize.py:347) -- the key is what the encoder
    makes of the whole window, read at the position the window ends on. Gradients have no business
    here: a stored key is data, and keeping the graph alive would hold the whole flush's activations
    for as long as the entry lives.
    """
    with torch.no_grad():
        h = key_fn(rows, n_layers=(key_depth if key_depth > 0 else None))
        return torch.nn.functional.normalize(h[:, -1].detach().float(), dim=-1)


def _gate_window(store, mode, write_gate, target, surprise):
    """One window's surprise -> its keep mask, ADVANCING gate_theta. Called once per window, in order.

    THE ORDER IS THE MECHANISM. gate_theta is a controller state, so the sequence of windows it sees
    is what it converges on; running the gate for every window first, before any encode, is what
    makes the trajectory independent of the batch width (memory.py:127-130, the frozen `_gate`).

    THE FOURTH ARM IS A RAISE AND NOT A FALL-THROUGH. MEM_WRITE_MODE carries choices=, so an
    unrecognised value is a startup LeverError and cannot reach here today -- but the defect this
    lever is named in is precisely a body whose `else` swallowed an arm it did not recognise
    (WRITE_ADAPTIVE and WRITE_QUANTILE encoded three rules in two booleans and the shipped
    combination ran the fixed threshold the quantile gate was written to replace). A fourth choice
    added to the lever without a body here raises instead of silently writing on the fixed gate.
    """
    sd = surprise.detach().float().flatten()
    if mode == "quantile":
        # SCALE-FREE, WHICH THE ADDITIVE ARM IS NOT. An absolute threshold cannot track a
        # distribution squeezed against 1.0; a quantile hits the target by construction.
        q = float(torch.quantile(sd, min(1.0, max(0.0, 1.0 - target))))
        if not store.gate_seeded:
            # SEEDED FROM THE FIRST BATCH, not from write_gate: the quantile arm's whole claim is
            # that it does not need a number anybody typed.
            store.gate_theta, store.gate_seeded = q, True
        else:
            store.gate_theta = (1.0 - GATE_STEP) * store.gate_theta + GATE_STEP * q
        return sd > store.gate_theta
    if mode == "adaptive":
        if not store.gate_seeded:
            store.gate_theta, store.gate_seeded = float(write_gate), True
        keep = sd > store.gate_theta
        fired = float(keep.float().mean())
        store.gate_theta = min(GATE_CEIL, max(GATE_FLOOR,
                                              store.gate_theta + GATE_STEP * (fired - target)))
        return keep
    if mode == "fixed":
        # `>=`, NOT `>`, and it is the difference between a documented arm and a dead one:
        # MEM_WRITE_GATE=0.0 is declared as store-every-candidate, and surprise can be exactly 0.
        return sd >= write_gate
    raise LeverError(
        f"MEM_WRITE_MODE={mode!r} has no body in memory/api.py::write. The lever declares "
        f"choices=('fixed', 'adaptive', 'quantile') and this function implements those three; a "
        f"fourth arm added to the declaration without one here would otherwise fall into the fixed "
        f"threshold the other two exist to replace, which is the defect MEM_WRITE_MODE is named in.")


def _unprotected(store, cand, need, share):
    """Drop candidates whose source is at or below its reserved floor. -> (cand, blocked, deadlock).

    WHY A RANKING FUNCTION CANNOT REPLACE IT. Eviction ranked on retrieval asks "what is the CURRENT
    stream asking for", and for a domain that is not currently streaming the answer is nothing BY
    CONSTRUCTION: no query resembles it, its clock never advances, it is the victim every time.
    Measured twice in the tree this is ported from, once under write-recency and once under
    retrieval-recency, with the same outcome: after a Python run, English held 0 of 200,000 entries.

    NEVER DEADLOCKS. If protection would leave nothing to evict -- every source at its floor, which
    is what a full, balanced store looks like -- the filter is dropped FOR THIS CALL and counted. A
    store that cannot evict is worse than one that evicts something protected.

    THE DIVISOR IS LIVE STATE AND HERE IT IS A COUNT. store.live_src is what MEM.apply_domain_plan
    sets from DOM's `live_sources`; until it has run it is the number of sources HOLDING ENTRIES,
    which is the frozen tree's documented `live_src=None` arm ("no domain information supplied and
    everything with entries is eligible"). WHAT THIS CANNOT DO, because the Store keeps a count and
    not a SET: it cannot make an ORPHANED source ineligible. On a measured run 125 source ids held
    entries against 27 live domains, so a floor divided by the wrong one of those gave each domain
    800 slots instead of the ~3300 it was due -- the divisor here is right the moment DOM has spoken,
    but a dead source that still holds entries is still protected by it. Closing that needs a live-id
    SET on the Store, written by apply_domain_plan, which is a stub.
    """
    if share <= 0.0:
        # THE SUPERSEDED RULE IS STILL REACHABLE, which is what D3 asks for: src_share=0 disarms the
        # reservoir and leaves "pressure is a signal, not a wall" as the selectable arm.
        return cand, 0, False
    has = store.nsrc > 0
    live = int(store.live_src) if int(store.live_src) > 0 else int(has.sum())
    if live <= 1:
        return cand, 0, False                      # one source owns everything anyway
    floor = int(share * int(store.capacity) / live)
    if floor <= 0:
        return cand, 0, False
    prot = has & (store.nsrc <= floor)
    cs = store.src[cand].clamp(min=0, max=store.nsrc.numel() - 1)
    # src < 0 IS "NO PROVENANCE" AND IS NEVER PROTECTED. -2 is the reserved id for synthetic
    # eval-injected entries, so the wrongness harness can never collide with a real domain (H30).
    keep = (~prot[cs]) & (store.src[cand] >= 0)
    out = cand[keep]
    blocked = int(cand.numel() - out.numel())
    if int(out.numel()) >= need:
        return out, blocked, False
    return cand, blocked, True


def _victims(store, occ, need, evict, prob_frac, quota, share, over_budget):
    """Choose `need` occupied slots of ONE owner block to evict.

    -> (idx, branch, floor_blocked, deadlock). `branch` is "probation" or "main", which is the
    partition MEM.census's `pressure` is main/(main + prob) over.

    RANKED OVER OCCUPIED ROWS ONLY. Ranking the whole block puts the never-stamped free rows first --
    their clock reads 0, the oldest possible -- so the `need` oldest were exactly the free rows the
    caller had already taken, and `cat([free, victims])` returned indices of which only free.numel()
    were distinct. Every duplicate is a row the caller believed it stored AND a double decrement of
    the displaced source's census, which is how a per-source count reaches a NEGATIVE number and
    prints as "s779 (-2 now, peaked 111230)".

    THE POOL IS SAMPLED, UNIQUE'D AND THEN RE-PERMUTED, and the last step is not decoration.
    torch.unique SORTS, and topk resolves ties toward the EARLIER index, so a sorted pool makes
    low-numbered slots the systematic loser of every tie -- and under evict="usage" with no
    retrievals every `use` is 0, so ties are the common case and not the edge one. Arbitrary is what
    that ranking has to stay.

    PROBATION DECIDES WHICH POOL, THE FLOOR DECIDES WHO INSIDE IT, AND BOTH ARE ASKED. The first
    version of this in the frozen tree narrowed to probation and went straight to the ranking, so a
    source at its floor lost its entries anyway as long as they were unpromoted -- the two mechanisms
    cancelled and the domain-switch test went from 49 survivors back to 0.
    """
    dev = occ.device
    n_occ = int(occ.numel())
    ns = int(min(n_occ, max(8 * need, 64)))
    draw = torch.randint(0, n_occ, (ns,), generator=store.gen, device=dev)
    cand = torch.unique(occ[draw])
    cand = cand[torch.randperm(int(cand.numel()), generator=store.gen, device=dev)]

    branch = "main"
    if over_budget:
        pc = cand[store.prob[cand]]
        if int(pc.numel()) < need:
            # THE SAMPLE WAS THIN -- take the region itself, oldest first, rather than falling out
            # of the probation branch because a random draw happened to miss it.
            allp = occ[store.prob[occ]]
            pc = allp[store.born[allp].argsort()] if int(allp.numel()) else pc
        if int(pc.numel()) >= need:
            cand, branch = pc, "probation"

    cand, blocked, deadlock = _unprotected(store, cand, need, share)

    # THE THREE CLOCKS, AND WHICH ONE RANKS IS THE WHOLE OF MEM_EVICT.
    #   usage    -> `use`, decayed retrieval mass (LFU).
    #   lru      -> `last`, the RETRIEVAL tick. 0 for everything that has never been retrieved.
    #   recency  -> `born`, write order. This is the frozen tree's circular overwrite expressed
    #               without a pointer: a block written in order and swept in order is the same
    #               victim sequence, and a pointer would be a second piece of unsaved state that a
    #               resume restarts from 0 anyway. The difference the two spellings have is on a
    #               block whose rows were freed out of order, where born-order is the more defensible
    #               of the two -- it still means "oldest write dies", which is what the lever says.
    # INSIDE PROBATION THE RANKING IS ALWAYS `born`, whatever MEM_EVICT says, and that is
    # probation_frac's own words: eviction narrows to "probation's own oldest". It is not a
    # substitution of MEM_EVICT's signal either -- every probation member is by definition
    # never-retrieved, so `use` and `last` are 0 across the whole pool and ranking on either is an
    # all-ties ranking decided by the permutation above.
    if branch == "probation" or evict == "recency":
        sig = store.born[cand]
    elif evict == "usage":
        sig = store.use[cand]
    else:
        sig = store.last[cand]
    kk = int(min(need, int(cand.numel())))
    idx = cand[sig.topk(kk, largest=False).indices]

    if int(idx.numel()) < need:
        # THE PAD MUST NOT RE-TAKE WHAT THE POOL ALREADY TOOK. Walk the block's occupied rows in
        # write order and keep only what is not already claimed.
        walk = occ[store.born[occ].argsort()]
        pad = walk[~torch.isin(walk, idx)][:need - int(idx.numel())]
        idx = torch.cat([idx, pad]) if int(pad.numel()) else idx
    return idx, branch, blocked, deadlock




def _write_gates(store, mode, fixed_gate, target, evict, decay, decay_every, prob_frac, quota):
    """The three arms write() decides, DECLARED WHERE THE LEVER IS READ and re-stated at every call.

    NOT AT open_store, and _declare_gates carries the full argument: open_store's frozen LEVERS READ
    line names four levers and says the other ten are read by write/read/maintain/judge, so putting
    these there would make that sentence false to buy an earlier line in a report.

    CALLED AT write's RETURNS AND NOT AT ITS HEAD. A gate declared before the work reports the
    PREVIOUS call: the first driven flush evicted 128 entries out of probation and the gate declared
    at the head of that same call printed "armed, did not fire (0 vs 0)" -- a verdict about a
    mechanism that was running while the line was being written. Measured, on the first two-flush
    drive of this body.
    """
    offered = int(store.counters.get("store.n_writes_offered", 0))
    committed = int(store.counters.get("store.n_writes_committed", 0))
    n_prob = int(store.counters.get("store.n_evict_probation", 0))
    written = int(store.n_written)
    _declare_gates(store, (
        # THE KEPT FRACTION AGAINST THE SETPOINT -- the number the two controller arms claim to
        # control, and the one that ran 1.00 / 0.93 / 0.80 against a requested 0.12 while the report
        # printed the request. Under "fixed" the setpoint controls nothing, and a bare 0 on this line
        # would read as a controller that ran and chose not to move.
        Gate("mem.write_target", committed >= target * offered,
             round(committed / offered, 4) if offered else 0.0, target)
        if mode != "fixed" else
        Gate("mem.write_target", False, target, target, reachable=False,
             reason=f"MEM_WRITE_MODE={mode!r} admits on MEM_WRITE_GATE={fixed_gate} alone, so this "
                    f"setpoint selects nothing and neither do GATE_STEP, GATE_FLOOR or GATE_CEIL. "
                    f"The kept fraction is still measured -- "
                    f"n_writes_committed/n_writes_offered = {committed}/{offered} -- it is simply "
                    f"not controlled by anything."),
        # THE DECAY'S OWN ARITHMETIC: entries written against the interval. At the shipped 20000 a
        # short run cannot reach it, and "0 decays" then means "the interval has not elapsed", which
        # is a different fact from "the multiplier is 1.0".
        Gate("mem.use_decay", written >= decay_every, written, decay_every,
             reason=f"MEM_USE_DECAY={decay} is the multiplier and MEM_USE_DECAY_EVERY={decay_every} "
                    f"is the interval, counted in ENTRIES WRITTEN and not in steps"
                    + ("" if evict == "usage" else
                       f"; MEM_EVICT={evict!r} ranks victims on "
                       f"{'born (write order)' if evict == 'recency' else 'last (retrieval tick)'}, "
                       f"so `use` decides no eviction here and the decay changes nothing a victim is "
                       f"chosen by"))
        if decay < 1.0 else
        Gate("mem.use_decay", False, decay, 1.0, reachable=False,
             reason=f"MEM_USE_DECAY={decay} is at or above 1.0, and the multiplication is INSIDE the "
                    f"`< 1.0` test -- so the rule goes INERT and `use` stays a lifetime total. It "
                    f"does not run backwards and nothing compounds; the immortal entry a lifetime "
                    f"total can produce is reachable here, by the decay never running."),
        # SCAN RESISTANCE: did eviction ever narrow to the never-retrieved region.
        Gate("mem.probation", n_prob > 0, n_prob, 0,
             reason=f"the narrowing is a PER-BLOCK test against MEM_PROBATION_FRAC={prob_frac}, "
                    f"which at quota={quota} is {prob_frac * quota:.1f} entries inside a block and "
                    f"not {prob_frac * int(store.capacity):.0f} across the store -- the factor is "
                    f"the block count. It cannot narrow before a block is full, and nothing leaves "
                    f"probation until a retrieval promotes it: MEM.read is a stub, so today every "
                    f"eviction is a probation eviction and MEM.census's `pressure`, which is "
                    f"main/(main+prob) over these branches, is exactly 0 by construction."),
    ))


def _windows_of(now, where):
    """`now` as a plain count of WINDOWS, refusing any other clock kind BY NAME.

    int() ON A Clock IS SILENT ACROSS KINDS -- int(Steps(5)) is 5 -- which is the one hole
    spine/units.py cannot close, because __int__ has to exist for range() and slicing. MEM's two
    internal cadences are Windows and are compared against this number, so a Flushes handed in here
    would fire them at the flush rate under a windows label: at OPT_BATCH_WINDOWS=64 that is the
    probe running 64 times as often as the operator asked, with nothing in any report saying so.
    """
    if isinstance(now, U.Clock) and not isinstance(now, U.Windows):
        raise U.UnitError(
            f"{where}: `now` arrived as {type(now).__name__} and every clock this package compares "
            f"it against is WINDOWS -- MEM_PROBE_EVERY and MEM_REKEY_EVERY both declare U.Windows, "
            f"and memory/api.py::maintain's contract is that no conversion is performed or needed. "
            f"If this conversion is real, name it in spine.derive and call it.")
    return int(now)


def _commit_window(store, o, keys, toks, poss, ctxs, src, quota, evict, prob_frac, share, born):
    """Put one window's already-gated, already-keyed rows into ONE owner block.

    -> (committed, free_used, evicted_probation, evicted_main, floor_blocked, deadlock).

    ONE WRITE PATH AND NO `if blocks > 1:`. The owner NARROWS the candidate slot set to its block and
    probation, the floor and the ranking all run INSIDE that set; with blocks == 1 the block is the
    store. The tree this is ported from had two bodies -- a per-owner arm that returned before
    probation, the floor and the pressure counters, and a global arm that ran all three -- while the
    report printed all three either way (H31). Two code paths are two chances to disagree, and this
    one disagreed.
    """
    dev = store.keys.device
    rows = store._rows_of(o)
    blk = torch.arange(rows.start, rows.stop, device=dev)
    act = store.active[blk]
    free, occ = blk[~act], blk[act]
    m = int(keys.shape[0])
    free_used = int(min(m, int(free.numel())))
    branch, blocked, deadlock = None, 0, False
    if m <= int(free.numel()):
        idx = free[:m]
    else:
        need = m - int(free.numel())
        # PROBATION IS A PER-BLOCK PREDICATE AND THIS LINE IS THAT SENTENCE. At the shipped
        # d_capacity=8192 / d_owner_blocks=64 / quota=128 a 0.10 share is 12.8 entries INSIDE THIS
        # BLOCK, not 819 across the store -- a factor of 64 in when eviction narrows. The store-wide
        # `probation_share` MEM.census reports is an aggregate over the same flag and is NOT this
        # test (Q-MEM-4, settled 2026-09-02).
        over = int(store.prob[occ].sum()) > prob_frac * quota
        vic, branch, blocked, deadlock = _victims(store, occ, need, evict, prob_frac, quota,
                                                  share, over)
        idx = torch.cat([free, vic]) if int(free.numel()) else vic

    # DUPLICATES ARE REFUSED, NOT COLLAPSED. Index assignment collapses a repeat silently -- keys[idx]
    # with idx naming slot j twice writes the later row and drops the earlier -- so the store reports
    # m writes and holds fewer. The damage is in the accounting: the census below decrements the
    # displaced owner ONCE PER OCCURRENCE while crediting the new source idx.numel() times, which
    # overcharges the displaced source and drives its count NEGATIVE (measured drift 9 in 200). The
    # two known producers are fixed above; this is the invariant so a third cannot be silent.
    if int(idx.numel()) != int(torch.unique(idx).numel()):
        _bump(store, "store.n_dup_refused", int(idx.numel()) - int(torch.unique(idx).numel()))
        raise StoreError(
            f"MEM.write named {int(idx.numel()) - int(torch.unique(idx).numel())} slot(s) twice in "
            f"one commit into owner block {o} (rows {rows.start}..{rows.stop - 1}). Refused rather "
            f"than collapsed: a collapse double-decrements the displaced source's census and drives "
            f"the per-source count -- the floor's only input -- negative, which is how a report "
            f"comes to print a source holding minus two entries.")

    # SOURCE ACCOUNTING BEFORE THE OVERWRITE: the slots being taken still hold their old owners.
    old = store.src[idx]
    oa = old[(old >= 0) & store.active[idx]]
    if int(oa.numel()):
        store.nsrc.index_add_(0, oa.clamp(min=0, max=store.nsrc.numel() - 1),
                              torch.full((int(oa.numel()),), -1, dtype=store.nsrc.dtype, device=dev))
        neg = int((store.nsrc < 0).sum())
        if neg:
            # A COUNT OF ENTRIES CANNOT BE NEGATIVE, and if this clamp bites the incremental census
            # has already drifted from what `src & active` says. Clamping alone would hide the next
            # drift, so the bite is COUNTED and MEM.census(reconcile=True) is what repairs it.
            _bump(store, "store.n_src_underflow", neg)
            store.nsrc.clamp_(min=0)
    if src >= int(store.nsrc.numel()):
        # THE CENSUS GROWS AND IS NEVER CLAMPED. Clamping ids into a fixed-width table is the exact
        # pattern that re-broke this at the scale it was written for: the table was 64 rows wide on
        # every default run while a real one carried 125 source ids.
        grown = torch.zeros(src + 1, dtype=store.nsrc.dtype, device=store.nsrc.device)
        grown[:store.nsrc.numel()] = store.nsrc
        store.nsrc = grown
    if src >= 0:
        store.nsrc[src] += m
        store.nsrc_max = max(int(store.nsrc_max), int(store.nsrc[src]))

    store.keys[idx] = keys
    store.tok[idx] = toks.to(dev)
    store.src[idx] = int(src)
    store.pos[idx] = poss.to(dev)                  # WHERE it came from, in TRUE BYTE OFFSETS
    if store.ctx_w:
        store.ctx[idx] = ctxs.to(dev)              # the window MEM.maintain re-encodes from
    store.own[idx] = int(o)
    store.active[idx] = True
    store.prob[idx] = True                         # every write lands on probation; retrieval promotes
    store.use[idx] = 0.0
    store.last[idx] = 0                            # NEVER RETRIEVED -- see Store's docstring
    store.born[idx] = int(born)
    store.selfcon[idx] = -1.0                      # new entry: self-consistency not yet checked
    store.recon[idx] = -1.0                        # new entry: reconstruction not yet checked
    return m, free_used, (m if branch == "probation" else 0), \
        (m if branch == "main" else 0), blocked, deadlock


def write(mem: Config, store, *, contexts, tokens, surprise, sources, owners, positions, key_fn,
          now):
    """Gate one flush's candidate rows on surprise, encode the survivors ONCE, and commit them.

    ORDER, AND IT IS LOAD-BEARING: the gate runs for every window first, IN WINDOW ORDER, so
    gate_theta evolves identically whatever the batch width; then ONE key_fn call encodes all the
    survivors; then the rows commit per window. Encoding after the gate is exactly equivalent (the
    encoder is row-independent) and is the single largest saving in the step.

    ONE WRITE PATH. There is no `if blocks > 1:` branch. The owner NARROWS the candidate SLOT SET
    to its block; probation narrowing and per-source floor protection then run INSIDE that set.
    With blocks == 1 the block is the store.
    SO probation_frac IS A PER-BLOCK PREDICATE, and that sentence is the declaration -- said again
    here because the two readings are different code and differ by the block count (Q-MEM-4, settled
    2026-09-02). At the shipped d_capacity=8192, d_owner_blocks=64, quota=128 a 0.10 share is 12.8
    entries INSIDE A BLOCK, not 819 across the store: a 64x difference in when eviction narrows.
    census's `probation_share` is a STORE-WIDE REPORT AGGREGATE over the same flag and is NOT this
    predicate; a Gate that prints the aggregate beside probation_frac is comparing two different
    denominators, which is why census's own Gate must print the per-block distribution. This is the repair for H31, where the per-owner path
    returned before probation, the floor and the pressure counters while the report printed all
    three. `write_target` is a setpoint on the KEPT FRACTION, and survivors in excess of the
    block's quota are truncated BY SURPRISE RANK and counted -- the old path kept the FIRST quota
    while its comment claimed it kept the most surprising.

    DUPLICATES ARE REFUSED, NOT COLLAPSED. Selection returns a distinct-by-construction index set:
    the free set and the victim set are disjoint (victims ranked over OCCUPIED rows only -- ranking
    the whole block put never-stamped free rows first because their clock reads 0); the sampled
    candidate pool is unique'd AND RE-PERMUTED (unique SORTS, and the topk resolves ties toward the
    earlier index, so a sorted pool makes low-numbered slots the systematic loser of every tie, and
    under evict=="usage" ties are the common case); the circular pad excludes anything already
    claimed. A violation RAISES rather than collapsing, because a silent collapse
    double-decrements the displaced source and drives nsrc negative (measured drift 9 in 200).

    `positions` MUST BE THE TRUE BYTE OFFSET, not an arange over token indices: a token averages
    ~1.85 bytes and the drift reached 200+ bytes per window against a 220-byte recall span.

    src < 0 is "no provenance" and is never protected by the floor. -2 is reserved for synthetic
    eval-injected entries so the wrongness harness can never collide with a real domain id (H30 --
    the old harness used src=99, a real domain id).

    LEVERS READ: write_mode, write_gate, write_target, evict, use_decay, use_decay_every,
                 probation_frac, src_share, quota, key_win, key_depth, key_src
    WIRES READ: none
    DID IT FIRE: store.n_writes_offered / n_writes_committed (the pair IS the kept fraction, which
                 is the number the adaptive arm claims to control), n_evict_free /
                 n_evict_probation / n_evict_main, n_floor_blocked, n_floor_dropped_deadlock,
                 n_dup_refused, n_src_underflow, n_write_truncated, n_use_decays,
                 n_writes_by_block (a block with 0 writes is the owner fold showing)
    """
    mem = mem.owned_by("MEM")
    mode, fixed_gate, target = str(mem.write_mode), float(mem.write_gate), float(mem.write_target)
    evict, decay, decay_every = str(mem.evict), float(mem.use_decay), int(mem.use_decay_every)
    prob_frac, share, quota = float(mem.probation_frac), float(mem.src_share), int(mem.quota)
    kwin, kdepth, ksrc = int(mem.key_win), int(mem.key_depth), str(mem.key_src)

    if ksrc != "model":
        # DECLARED AND NOT BUILT, refused at the point of use and not with NotImplementedError: the
        # frozen-key arm is a real configuration (memory/levers.py calls it "the null for every claim
        # memory makes") and its encoder does not exist in this tree. `key_fn` is LM.encode partially
        # applied; there is no byte-statistic table anywhere in src/, no lever that sizes one and no
        # argument that supplies one. Writing model keys under MEM_KEY_SRC="frozen" would be the
        # silent-else this lever is named in (KEY_SRC=Model fell into the else and ran the frozen
        # baseline with no error), wearing the other sign.
        raise NotBuilt(
            f"MEM_KEY_SRC={ksrc!r}: the frozen byte-statistic key table is DECLARED and NOT BUILT in "
            f"this tree. Nothing in src/ computes one, no lever sizes it and no argument carries "
            f"one -- `key_fn` is the live model's encoder, which is the other arm. Writing with it "
            f"anyway would put model keys in a store the operator asked to key by bytes, which is "
            f"the exact silent substitution MEM_KEY_SRC's choices= exists to refuse. What closes "
            f"this: a frozen encoder on MEM's own surface, or a second callable argument beside "
            f"key_fn -- both are signature changes and therefore the owner's call.")

    # ==============================================================================================
    # WHAT THE FLUSH HANDED OVER, CHECKED BY SHAPE AND REFUSED BY NAME
    # ==============================================================================================
    # `contexts` ARE TOKEN IDS, NOT HIDDEN STATES, and the two spellings in spine/compose.py
    # disagree: its LOOP_ORDER B row says "contexts and tokens are the flush's x and y at
    # _flush_bounds" and its ROW_ARGUMENTS_ELSEWHERE["MEM.write"] says "contexts is LM.encode's `h`".
    # The row is the one that can be true. This function's own contract is that the survivors are
    # encoded AFTER the gate by ONE key_fn call, key_fn IS LM.encode (spine/compose.py::_key_fn), and
    # LM.encode takes (B, L) ids -- so `contexts` is its INPUT or there is nothing for it to encode.
    # MEM_KEY_WIN agrees in its own declaration: "How many preceding input positions the encoder sees
    # when it builds one memory key", slicing "the model input x".
    if not torch.is_tensor(contexts) or contexts.dim() != 2 or contexts.is_floating_point():
        got = (f"{tuple(contexts.shape)} of {contexts.dtype}" if torch.is_tensor(contexts)
               else type(contexts).__name__)
        raise StoreError(
            f"MEM.write: `contexts` arrived as {got}. It must be the flush's (B, L) TOKEN IDS -- the "
            f"same `x` LM.encode takes -- because this body encodes the survivors with `key_fn`, "
            f"which IS LM.encode bound to (lm, model). A (B, L, width) hidden state cannot be "
            f"encoded again and cannot be sliced to MEM_KEY_WIN preceding POSITIONS. "
            f"spine/compose.py's LOOP_ORDER B row spells it 'the flush's x and y at _flush_bounds'; "
            f"its ROW_ARGUMENTS_ELSEWHERE entry for this call says `h` and is the one that is wrong.")
    B, L = int(contexts.shape[0]), int(contexts.shape[1])
    _require_rows("tokens", tokens, (B, L),
                  "the true next token at every position, the same cut shifted one token")
    _require_rows("surprise", surprise, (B, L),
                  "1 - p_model(true token) at every position, which is what the gate ranks on")
    _require_rows("positions", positions, (B, L),
                  "the TRUE BYTE OFFSET of every position, from Segmentation.byte_pos -- not an "
                  "arange over token indices, which drifts 200+ bytes per window against a 220-byte "
                  "recall span because a token averages ~1.85 bytes")
    _require_rows("sources", sources, (B,), "one domain id per WINDOW, from DOM.observe's `did`")
    _require_rows("owners", owners, (B,),
                  "one owner block per WINDOW, argmax over FabricOut.weights modulo "
                  "MEM.d_owner_blocks")

    # THE CONTEXT ARRAY IS GROWN TO MEM_KEY_WIN ONCE, HERE, because this is the first place in the
    # package that may read that lever (open_store's LEVERS READ line does not name it).
    if int(store.ctx_w) != kwin:
        if int(store.ctx_w) and int(store.active.sum()):
            raise StoreError(
                f"MEM_KEY_WIN={kwin} against a store holding {int(store.active.sum())} entries whose "
                f"context windows are {int(store.ctx_w)} token(s) wide. Refused: the stored window "
                f"is what MEM.maintain re-encodes a key from, so re-keying an 8-token context as "
                f"half of a 16-token one puts the store into two key spaces that do not compare -- "
                f"the drift MEM_REKEY_EVERY exists to prevent, caused by the thing that prevents it. "
                f"Resume at the width the checkpoint was written with, or start a new store.")
        store.ctx_w = kwin
        store.ctx = torch.zeros(int(store.capacity), kwin, dtype=torch.long,
                                device=store.keys.device)

    # BOTH OF THIS STORE'S CLOCKS ARE THE WINDOW CLOCK. `born` is stamped from it below, and
    # MEM.read stamps `last` from the same field, so "born at window 120, last retrieved at window
    # 400" is a sentence the report can write and the two are comparable.
    w = _windows_of(now, "MEM.write")
    store.tick = max(int(store.tick), w)

    # ==============================================================================================
    # PHASE 1 -- THE GATE, FOR EVERY WINDOW, IN WINDOW ORDER, BEFORE ANY ENCODE
    # ==============================================================================================
    # THE ORDER IS LOAD-BEARING: gate_theta is a controller state, so it must see the windows in
    # window order and nothing else, whatever the batch width. Encoding after the gate is exactly
    # equivalent -- the encoder is row-independent, so a row's key does not depend on which other
    # rows are in the batch -- and it is the single largest saving in the step: the tree this is
    # ported from encoded a key for EVERY position and threw ~88% of them away here, which made this
    # the most expensive operation in the step by a wide margin.
    keeps = [_gate_window(store, mode, fixed_gate, target, surprise[b]) for b in range(B)]
    offered = B * L
    kept = int(sum(int(k.sum()) for k in keeps))
    _bump(store, "store.n_writes_offered", offered)
    _bump(store, "store.n_writes_kept", kept)

    receipt = WriteReceipt(offered=offered, kept=kept, committed=0, evicted_free=0,
                           evicted_probation=0, evicted_main=0, floor_blocked=0,
                           gate_theta=float(store.gate_theta))
    if kept == 0:
        _bump(store, "store.n_writes_committed", 0)
        _write_gates(store, mode, fixed_gate, target, evict, decay, decay_every, prob_frac, quota)
        return receipt

    # ==============================================================================================
    # PHASE 1b -- THE PER-BLOCK QUOTA, TRUNCATED BY SURPRISE RANK
    # ==============================================================================================
    # One window can present far more survivors than a block holds. The tree this is ported from kept
    # the FIRST quota of them while its comment claimed it kept the most surprising; the difference
    # is not cosmetic, because the tail it dropped is exactly the material the gate rated highest.
    # Truncation happens BEFORE the encode, so a truncated row never costs a key.
    sel = []
    for b in range(B):
        k = keeps[b]
        m = int(k.sum())
        if m > quota:
            idx = k.nonzero(as_tuple=True)[0]
            top = surprise[b].detach().float()[idx].topk(quota).indices
            k = torch.zeros_like(k)
            k[idx[top]] = True
            _bump(store, "store.n_write_truncated", m - quota)
            keeps[b] = k
        sel.append(int(k.sum()))

    # ==============================================================================================
    # PHASE 2 -- ONE key_fn CALL FOR THE WHOLE FLUSH
    # ==============================================================================================
    wins = _key_windows(contexts, kwin)                       # (B, L, key_win)
    rows = torch.cat([wins[b][keeps[b]] for b in range(B) if sel[b]], 0)
    keys = _encode_keys(key_fn, rows, kdepth)

    # ==============================================================================================
    # PHASE 3 -- THE ROWS COMMIT PER WINDOW, EACH INTO ITS OWN OWNER BLOCK
    # ==============================================================================================
    by_block = list(store.counters.get("store.n_writes_by_block", [0] * int(store.owners)))
    committed = free_used = ev_prob = ev_main = blocked = 0
    off = 0
    n_before = int(store.n_written)
    for b in range(B):
        m = sel[b]
        if not m:
            continue
        k = keeps[b]
        o = int(owners[b]) % int(store.owners)
        c, f, p, mn, fb, dl = _commit_window(
            store, o, keys[off:off + m], tokens[b][k], positions[b][k], wins[b][k],
            int(sources[b]), quota, evict, prob_frac, share, w)
        off += m
        committed += c
        free_used += f
        ev_prob += p
        ev_main += mn
        blocked += fb
        by_block[o] += c
        if dl:
            _bump(store, "store.n_floor_dropped_deadlock")
        store.n_written += c

    # THE DECAY IS DRIVEN BY THE CUMULATIVE WRITE COUNTER AND NOT BY A RESETTABLE ONE, which is what
    # makes it survive a resume: MEM_USE_DECAY_EVERY is "how many entries must be WRITTEN before the
    # retrieval counters are decayed", `n_written` is checkpointed, and asking how many INTERVALS the
    # counter has crossed needs no second piece of state that a restore would restart. The frozen
    # tree kept a `_wc` it reset to 0 (memory.py:494-496) and a resume restarted it, postponing the
    # next decay by up to a whole interval.
    # THE MULTIPLICATION IS INSIDE THE `< 1.0` TEST. Above 1.0 the rule goes INERT -- it does not run
    # backwards -- which is the correction memory/levers.py carries and this line must not re-break.
    if decay < 1.0 and decay_every > 0:
        crossed = int(store.n_written) // decay_every - n_before // decay_every
        if crossed > 0:
            store.use *= decay ** crossed
            _bump(store, "store.n_use_decays", crossed)

    store.counters["store.n_writes_by_block"] = by_block
    _bump(store, "store.n_writes_committed", committed)
    _bump(store, "store.n_evict_free", free_used)
    _bump(store, "store.n_evict_probation", ev_prob)
    _bump(store, "store.n_evict_main", ev_main)
    _bump(store, "store.n_floor_blocked", blocked)
    _write_gates(store, mode, fixed_gate, target, evict, decay, decay_every, prob_frac, quota)
    return dataclasses.replace(receipt, committed=committed, evicted_free=free_used,
                               evicted_probation=ev_prob, evicted_main=ev_main,
                               floor_blocked=blocked, gate_theta=float(store.gate_theta))



def read(mem: Config, store, *, queries, promote=True):
    """kNN over readable entries -> a token distribution, its match quality, and its blend weight.

    Excludes inactive entries and entries flagged by the active wrongness detector when wrong_read
    is set, AND NOTHING ELSE -- reads stay GLOBAL across owner blocks even when writes are
    partitioned. That asymmetry is the design: knowledge is owned but not walled off.

    `queries` ARE KEYS IN THE STORE'S OWN KEY SPACE, NOT CONTEXTS. This function declares no key
    lever and takes no key_fn, so it cannot encode: whoever calls it narrows to key_win and encodes
    with the same key_fn at the same key_depth the write path used. In-package that caller is
    maintain (Q-MEM-9); the report-path caller is the composition root, and the two must agree or
    the store is queried in one key space and written in another.

    `conf` is the top cosine similarity and `blend` is computed HERE from conf, match_floor and
    blend_max -- THE CALLER NEVER RECOMPUTES EITHER. Recomputing conf at the blend site is what
    reproduced the ungated 50/50 mix one layer up in prompt.py (ISSUES P1-C8) and cl_bench.py (C9).

    promote=False is the read that MUST NOT MOVE THE STORE: it skips the use/last/prob updates. The
    report path uses it, because holdout_bpb(use_mem=True) mutating use, prob and last is L49 and
    it is an instrument editing what it measures (G7).

    LEVERS READ: topk, blend_max, match_floor, wrong_read, verify
    WIRES READ: none
    DID IT FIRE: store.n_reads, n_read_empty, n_promoted, n_wrong_reads, n_wrong_read_hit,
                 n_wrong_blocked -- the wrong-flag counters incremented WHERE THE GATE GATES, never
                 derived from the flags left at the end of the run (H32/M42: every write resets
                 selfcon to -1, so an end-of-run snapshot said "0 entries checked" in the same
                 report as "61,952 entries excluded from EVERY retrieval")
    """
    mem = mem.owned_by("MEM")
    raise NotImplementedError(
        "MEM.read: P4 (memory) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section MEM.")


def blend(mem: Config, model_probs, retrieval):
    """Mix retrieval into the model's distribution AT THE WEIGHT `read` ALREADY COMPUTED.

    model_probs are PROBABILITIES, not logits. Returns (1-w)*model_probs + w*dist. THE ARITHMETIC
    LIVES IN THIS PACKAGE so the mixing weight never travels: a weight read at the LM forward is a
    foreign read, and the ungated copy of exactly this expression is still live in prompt.py, the
    tool the deliverable is read with. blend_max == 0.0 is the clean retrieval-off null and returns
    model_probs untouched. Both blend_max and match_floor are re-asserted here, so a Retrieval
    built by anything else fails loudly rather than mixing at an unknown weight.

    THE SCORING CALLER TAKES log() OF WHAT THIS RETURNS, AND THAT IS EXACT, NOT A PSEUDO-LOGIT
    (Q-MEM-10, RESOLVED 2026-09-02 (a)). softmax(log p) == p identically, so temperature, top-k,
    nucleus sampling and cross-entropy over log(mixture) are all the true bits/byte of the blended
    distribution. THIS SIGNATURE DOES NOT MOVE and no EVAL signature moves either: the composition
    root forms softmax -> read(promote=False) -> blend -> log ONCE, as the named closure
    _logits_fn(sysm, *, use_memory), and the mixing weight still never travels. log(0) cannot arise
    while blend_max < 1: the result is >= (1-blend_max)*p_model and p_model from a softmax is
    strictly positive. THE ONE CASE THAT MUST BE CLAMPED is blend_max == 1.0 with conf == 1.0, where
    the model's mass can vanish entirely; that clamp belongs here, with the arithmetic, not at the
    log site.

    LEVERS READ: blend_max, match_floor
    WIRES READ: none
    DID IT FIRE: store.n_blends, store.blend_weight_sum (the MEAN APPLIED WEIGHT is the honest
                 statement of how much mass retrieval actually took; the defect it replaces was a
                 constant 0.5 reported as a gate)
    """
    mem = mem.owned_by("MEM")
    raise NotImplementedError(
        "MEM.blend: P4 (memory) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section MEM.")


def maintain(mem: Config, store, *, now, key_fn, probe_contexts=None, resegment=None):
    """The three cadenced maintenance jobs, in ONE call, ON THE WINDOW CLOCK.

    `now` is units.Windows -- the loop counter, which advances once per window while this call is
    made once per flush. probe_every and rekey_every are both Windows and are compared against
    `now` in Windows; NO CONVERSION TO FLUSHES IS PERFORMED AND NONE IS NEEDED. That is the shipped
    semantics: `_due("memprobe", MEM_PROBE_EVERY)` at :7551 compares a windows counter against a
    windows threshold from inside the per-flush body, meaning "at most once per N windows, checked
    once per flush", and elapsed-since-last-fire is phase-independent so it means the same thing
    however often it is evaluated.

    1. READ PROBE. probe_rows real retrievals against probe_contexts, rows taken by DETERMINISTIC
       STRIDE, never a random draw: a probe that consumed RNG draws would make the probe cadence
       change the training trajectory, and a diagnostic that silently edits the run is exactly the
       class frozen_rng exists for. WITHOUT THIS, evict=="lru"/"usage" ARE WRITE-ORDER FIFO
       WHATEVER THEY SAY, and probation can never promote -- four archive files recorded
       EVICT=usage "does not protect faded knowledge by construction" as measured fact, and it was
       measured through a constant.
       THE PROBE *IS* read(), NOT A SECOND RETRIEVAL (Q-MEM-9, RESOLVED 2026-09-02 (a)). It is
       read(mem, store, queries=key_fn(stride(probe_contexts)[:, -key_win:], depth=key_depth),
       promote=True), and THERE IS NO SECOND RETRIEVAL IMPLEMENTATION IN THIS PACKAGE. The
       parameter lists force it rather than merely suggesting it: read declares no key lever and
       takes no key_fn, so it cannot encode anything and its `queries` must already be key-space
       vectors -- while THIS function holds key_fn and all three key levers. Open-coding a second
       kNN here would put n_reads/n_promoted/n_wrong_* on one path while the store is moved by
       another, which is C8/C9 one layer down, and would give wrong_read and match_floor a second
       implementation free to drift. The narrowing to key_win and the encode at key_depth happen
       HERE, once; any other site that forms `queries` must use the same two levers or the store is
       queried in one key space and written in another -- the drift rekey_every exists to prevent.
       WITH probe_contexts None OR EMPTY the honest DID IT FIRE reading is n_probe_fired counting
       the CADENCE and n_probe_rows == 0: armed-but-0, not unreachable and not silence.
    2. AMORTIZED REKEY. If key_src == "model" and rekey_every > 0, re-encode one slice of a
       SNAPSHOT of the readable entries, sized so the whole snapshot is covered once per
       rekey_every windows. rekey_every == 0 DISARMS, behind a guard: the old tree documented 0 as
       the off switch and then divided by it -- an untrippable guard whose escape hatch was a
       ZeroDivisionError. The rekey must pass the SAME key_depth the write path used, or the store
       drifts into two key spaces that do not compare.
    3. RESEGMENT. `resegment` non-None means a retokenization happened and every stored ctx holds
       token ids under a segmentation that no longer exists. Applying it FORCES THE REKEY SNAPSHOT
       TO BE RETAKEN.

    LEVERS READ: probe_every, probe_rows, rekey_every, key_src, key_depth, key_win
    WIRES READ: none
    DID IT FIRE: store.n_probe_fired, n_probe_rows, n_probe_hits (retrievals that returned at least
                 one entry -- a probe that fires and retrieves nothing is a DIFFERENT finding from
                 a probe that never fires, and the old report could not tell them apart),
                 n_rekey_slices, n_rekey_passes, n_rekey_entries, n_resegment_events,
                 n_keys_at_capped_depth
    """
    mem = mem.owned_by("MEM")
    every_p, probe_rows = int(mem.probe_every), int(mem.probe_rows)
    every_r, ksrc = int(mem.rekey_every), str(mem.key_src)
    kdepth, kwin = int(mem.key_depth), int(mem.key_win)

    # NO CONVERSION TO FLUSHES IS PERFORMED AND NONE IS NEEDED. `now` is WINDOWS, both periods are
    # declared in Windows, and elapsed-since-last-fire is PHASE-INDEPENDENT -- so this call may be
    # made once per flush and still mean "at most once per N windows", which is exactly what
    # RUN.Cadences.due guarantees for the keys the spine owns. _windows_of refuses another kind
    # rather than letting int() cross it silently.
    w = _windows_of(now, "MEM.maintain")
    store.tick = max(int(store.tick), w)
    c = store.counters

    # ==============================================================================================
    # 3 (FIRST) -- RESEGMENT. It invalidates what job 2 walks, so it cannot run after it.
    # ==============================================================================================
    # WHAT IS SATISFIABLE HERE IS THE SNAPSHOT RETAKE AND NOTHING MORE, and the gap is named rather
    # than papered over. `resegment` is the RetokEvent the composition root distributes; NO ENTRY
    # POINT'S DOCSTRING DECLARES ITS FIELDS -- spine/compose.py says so itself ("the event itself is
    # a record type tok/api.py::<module> declares and no entry point's docstring returns"), and
    # tok/api.py's header names it in one line with no shape. Applying it to `tok` and `ctx` needs an
    # old-id -> new-id mapping that is not declared anywhere, and INVENTING one here would rewrite
    # every stored token under a guess. So the declared consequence is performed -- the rekey
    # snapshot is dropped and retaken, which is this docstring's own sentence -- the event is
    # counted, and the stale ids are left visibly stale rather than silently rewritten.
    if resegment is not None:
        _bump(store, "store.n_resegment_events")
        store.rekey_snap, store.rekey_cursor = None, 0

    # ==============================================================================================
    # 1 -- THE READ PROBE. Without it evict="lru" and evict="usage" are write-order FIFO whatever
    #      they say, and probation can never promote.
    # ==============================================================================================
    if every_p > 0:
        last_p = c.get("store.probe_last_window")
        if last_p is None or (w - int(last_p)) >= every_p:
            c["store.probe_last_window"] = w
            # THE CADENCE IS COUNTED WHERE IT FIRES, not where it finds material. n_probe_fired
            # counting the cadence beside n_probe_rows == 0 is the honest armed-but-0 reading, and
            # it is a DIFFERENT fact from a probe that never fired -- which the old report could not
            # tell apart.
            _bump(store, "store.n_probe_fired")
            n_ctx = 0 if probe_contexts is None else int(probe_contexts.shape[0])
            if n_ctx and probe_rows > 0:
                # DETERMINISTIC STRIDE, NEVER A RANDOM DRAW. A probe that consumed RNG draws would
                # make the probe CADENCE change the training trajectory, and a diagnostic that
                # silently edits the run is the class spine/rng.py exists for.
                stride = max(1, n_ctx // probe_rows)
                rows = probe_contexts[::stride][:probe_rows]
                # THE NARROWING TO key_win AND THE ENCODE AT key_depth HAPPEN HERE, ONCE. `read`
                # declares no key lever and takes no key_fn, so it cannot encode and its `queries`
                # must already be key-space vectors; this function holds key_fn and all three key
                # levers. Any other site that forms `queries` must use the same two levers or the
                # store is queried in one key space and written in another.
                queries = _encode_keys(key_fn, rows[:, -kwin:], kdepth)
                # THE PROBE *IS* read(), NOT A SECOND RETRIEVAL (Q-MEM-9, RESOLVED (a)). Open-coding
                # a kNN here would put n_reads/n_promoted/n_wrong_* on one path while the store is
                # moved by another, and would give wrong_read and match_floor a second
                # implementation free to drift. MEM.read is still a P4 stub, so this line raises
                # NotImplementedError the moment a caller supplies probe_contexts -- which is the
                # loud state, and is why the cadence above is counted before it.
                retrieval = read(mem, store, queries=queries, promote=True)
                _bump(store, "store.n_probe_rows", int(rows.shape[0]))
                # ONE RETRIEVAL THAT RETURNED AT LEAST ONE ENTRY, which is what this counter is
                # declared to be -- a probe that fires and retrieves nothing is a different finding
                # from a probe that never fires. IT READS Retrieval.hits AND ASSUMES ONE THING ABOUT
                # IT: that a slot the retrieval did not fill is marked with a negative id. That is
                # the only convention this file takes on faith from an unwritten body; whoever
                # writes read() either keeps it or changes this line in the same edit.
                if int((retrieval.hits >= 0).sum()) > 0:
                    _bump(store, "store.n_probe_hits")

    # ==============================================================================================
    # 2 -- THE AMORTIZED REKEY. Key drift is a forgetting channel with nothing to do with eviction.
    # ==============================================================================================
    # rekey_every == 0 DISARMS, BEHIND A GUARD. The tree this is ported from documented 0 as the off
    # switch and then divided by it -- an untrippable guard whose escape hatch was a
    # ZeroDivisionError on the first flush.
    armed = ksrc == "model" and every_r > 0 and int(store.ctx_w) > 0
    if armed:
        last_r = c.get("store.rekey_last_window")
        if last_r is None:
            c["store.rekey_last_window"] = w      # first sight of the clock: nothing has elapsed yet
            last_r = w
        elapsed = w - int(last_r)
        if elapsed > 0:
            # A SNAPSHOT, AND THE WORD IS LOAD-BEARING. Entries written DURING a pass shift which
            # rows are active, so walking the live set with a cursor would re-key some rows twice and
            # never reach others. The snapshot is taken once per pass and is NOT checkpointed: after
            # a resume it is retaken and the restored cursor is clamped into it, because a cursor
            # taken against one snapshot indexes nothing in another.
            if store.rekey_snap is None or int(store.rekey_snap.numel()) == 0:
                store.rekey_snap = store.active.nonzero(as_tuple=True)[0]
                store.rekey_cursor = min(int(store.rekey_cursor), int(store.rekey_snap.numel()))
            snap = store.rekey_snap
            n = int(snap.numel())
            if n:
                # SIZED SO THE WHOLE SNAPSHOT IS COVERED ONCE PER `every_r` WINDOWS. `span` is that
                # count of windows and `per` is entries per window; multiplying by the windows that
                # actually elapsed is what makes the pass take the same number of WINDOWS whatever
                # the batch width, which is the property the cadence is declared in Windows for.
                span = max(1, every_r)
                per = -(-n // span)                              # ceil, integer, never 0
                take = max(1, per * elapsed)
                cur = int(store.rekey_cursor)
                rows = snap[cur:cur + take]
                # AN ENTRY EVICTED SINCE THE SNAPSHOT IS NOT RE-KEYED. Its slot now holds somebody
                # else's row, and re-encoding the new row from the old row's context would write a
                # key that belongs to neither.
                rows = rows[store.active[rows]]
                if int(rows.numel()):
                    # THE SAME key_depth THE WRITE PATH USED, through the same helper. A truncated
                    # key path plus a full-depth rekey drifts the store into two key spaces that do
                    # not compare -- the drift this whole mechanism exists to prevent.
                    store.keys[rows] = _encode_keys(key_fn, store.ctx[rows], kdepth)
                    _bump(store, "store.n_rekey_entries", int(rows.numel()))
                    if kdepth > 0 and str(store.lm_kind) == "transformer":
                        _bump(store, "store.n_keys_at_capped_depth", int(rows.numel()))
                _bump(store, "store.n_rekey_slices")
                cur += take
                if cur >= n:
                    _bump(store, "store.n_rekey_passes")
                    store.rekey_snap, cur = None, 0
                store.rekey_cursor = cur
                c["store.rekey_last_window"] = w

    # ==============================================================================================
    # THE TWO GATES WITH NO LEDGER KEY (G4)
    # ==============================================================================================
    # docs/04_CONTRACT.md names both: they are compared against a Windows `now` INSIDE this call and
    # `maintain` takes no `due` flag, so RUN.Cadences.ledger() cannot see either of them and these
    # counters are their only did-it-fire surface. Declared at the END, for the reason _write_gates
    # records: a gate declared before the work reports the previous call.
    fired_p = int(c.get("store.n_probe_fired", 0))
    rows_p = int(c.get("store.n_probe_rows", 0))
    passes = int(c.get("store.n_rekey_passes", 0))
    _declare_gates(store, (
        Gate("mem.probe", fired_p > 0, fired_p, 0,
             reason=f"MEM_PROBE_EVERY={every_p} windows x MEM_PROBE_ROWS={probe_rows} query rows; "
                    f"{rows_p} row(s) have actually been issued. n_probe_rows=0 beside a nonzero "
                    f"fire count is ARMED-BUT-0 and not silence: `probe_contexts` has no producer "
                    f"in spine/loop.py, so the cadence is reached and there is nothing to query "
                    f"with -- which is exactly the state that makes evict='lru' and evict='usage' "
                    f"write-order FIFO whatever they say, and probation unable to promote.")
        if every_p > 0 else
        Gate("mem.probe", False, every_p, 0, reachable=False,
             reason="MEM_PROBE_EVERY=0 disarms every retrieval-based rule in this package: `use` and "
                    "`last` never move off their write-time values, so MEM_EVICT's two retrieval "
                    "arms degenerate to write order and MEM_PROBATION_FRAC can never promote. The "
                    "lever's own declaration says the report must say so."),
        Gate("mem.rekey", passes > 0, passes, 0,
             reason=f"one full pass over the readable store every MEM_REKEY_EVERY={every_r} "
                    f"windows: {int(c.get('store.n_rekey_slices', 0))} slice(s), "
                    f"{int(c.get('store.n_rekey_entries', 0))} entr(y/ies) re-encoded so far. A run "
                    f"shorter than the period cannot complete one.")
        if armed else
        Gate("mem.rekey", False, every_r, 0, reachable=False,
             reason=(f"MEM_KEY_SRC={ksrc!r}: the keys are not the model's, so there is no drift to "
                     f"track and nothing to re-encode."
                     if ksrc != "model" else
                     f"MEM_REKEY_EVERY={every_r} is the DECLARED DISARM -- the store stops tracking "
                     f"the model and no run length reaches this, which is a different fact from a "
                     f"period the run was too short for."
                     if every_r <= 0 else
                     f"no entry in this store carries a context window (ctx_w=0), so there is "
                     f"nothing to re-encode a key FROM. That is the state of a store that has "
                     f"never been written, and of one restored from a blob written before the "
                     f"window was stored.")),
    ))



def apply_domain_plan(mem: Config, store, *, folds, deletions, live_sources):
    """Follow the domain manager: relabel merged provenance, delete culled provenance, set
    eligibility.

    DOM COMPUTED THIS PLAN AND DID NOT APPLY IT. The old tree had the domain manager call
    mem.reassign_src() and mem.delete_src() directly and read three of MEM's internals inline --
    `int(mem.src_floor * mem.cap / max(1, mem._eligible().sum()))` at self_organize.py:3688,
    INCLUDING A PRIVATE METHOD. Under O10 that import cannot exist, and the plan-then-apply split
    is what replaces it: DOM decides, the spine carries, MEM edits.

    THE CENSUS IS GROWN, NEVER CLAMPED. A fold into a source id past the table's end grows the
    table, and no path clamps an out-of-range id into the last bucket. `live_sources` is what makes
    orphaned ids ineligible for floor protection: 125 source ids held entries against 27 live
    domains on a real run, so dividing the reservation by "sources with anything in them" gave each
    800 slots instead of the ~3300 a live domain is due.

    LEVERS READ: src_share (only to REPORT the floor the plan was judged against; the decision was
                 DOM's)
    WIRES READ: none
    DID IT FIRE: store.n_folds_applied, n_deletes_applied, n_entries_deleted_by_cull (THE GOAL-B
                 NUMBER: how much of the store the domain manager destroyed, which in the old tree
                 was 200,000 entries with no counter at all), n_live_sources
    """
    mem = mem.owned_by("MEM")
    raise NotImplementedError(
        "MEM.apply_domain_plan: P4 (memory) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section MEM.")


def judge(mem: Config, store, *, scorer=None, reconstructor=None):
    """Run the selected wrongness detector over the store, and act on it or not.

    verify == "selfcon": scorer(ctx, src) -> logits, THE SAME FORWARD PATH TRAINING USED -- passed
    in, never constructed here, so the detector cannot score entries through a path the run never
    trained (M47). Per entry, the fraction of the vocabulary ranked above the stored token.
    THE ARITY IS TWO AND IT IS DECLARED HERE, ONCE (Q-MEM-8/Q-MEM-10, 2026-09-02). It was
    `scorer(ctx) -> logits`, and that shape cannot deliver what it promises: the path training used
    runs through FAB.forward, which routes per row on a `domain_id`, so a one-argument scorer either
    routes every stored entry as if it belonged to one domain or is not the trained path at all.
    The datum exists -- Store carries `src` per entry -- so only the declared shape was missing. It
    is prose and not a `def`, which is why it is free to change now and expensive after P4 writes
    against it. EVAL.wrongness_probe's `scorer` is THE SAME CALLABLE and takes the same two
    arguments; one callable declared twice with two shapes is how the signature width came out 614
    on one path and 1 on the other.
    verify == "recon": fit a Reconstructor(key_dim, vocab_slots, recon_tok, recon_hid) on the
    SETTLED store and record per-entry reconstruction error. verify == "off": a no-op, and "off" is
    a first-class configuration rather than a code path that rots (D4).

    Flagging is the adaptive median + k*MAD rule OVER CHECKED ENTRIES ONLY. wrong_read decides
    whether the flag excludes an entry from every retrieval or only from the sweep; wrong_sweep
    decides whether flagged entries are DELETED or only flagged. THE TWO ARE SEPARATE BECAUSE THEY
    WERE ONE: "sweep OFF, too low to delete safely" read as reassurance while 63,146 entries -- a
    third of the store, at 3% precision -- were unreachable to every read.

    THIS IS CADENCED, NOT END-OF-RUN. Called once from the report on a store where every write had
    reset selfcon to -1, the detector was structurally inert for the whole run and its report line
    described a pass the report had just performed.

    WHICH PASS: THE dom.manage PASS, AT ITS END -- after MEM.apply_domain_plan and DOM.census, and
    INSIDE the one Cadences.due('dom.manage', ...) answer that block already asks, never a second
    due() under the same key (asking twice CONSUMES the fire, which is the defect that made minting
    never fire). Q-MEM-8, RESOLVED 2026-09-02 (a). No new key, no new period, and no key is added to
    spine/compose.py's _periods.
    THE REASON IS NOT THE ONE THE QUESTION GAVE. docs/04_CONTRACT.md justified this pass as "the
    moment the store's provenance has just been rewritten by folds and deletions"; that is not an
    input to anything here -- this function reads verify, wrong_read, wrong_sweep, recon_hid and
    recon_tok and scores (ctx, tok) per entry, and a fold relabels `src` without changing what the
    model thinks of a stored token. The operative reason is census's own contract: a wrong_sweep
    deletion makes the per-source counts stale, census(reconcile=True) is the FIRST row of this same
    pass, and running judge at the END bounds that staleness to ONE cadence interval. 100 Windows
    bounds it five times tighter than 500 -- that is the argument for dom.manage over fab.manage,
    and it is the only one that survives inspection. At the shipped wrong_sweep=False nothing is
    deleted at all, so the ordering costs nothing today. The alternative also has a cost of its own:
    on fab.manage this would be the only MEM row riding a FAB-keyed answer with no MEM period in
    sight, which is exactly the untracked ride compose.py's fab.manage row records for WORLD.
    ALSO STALE, AND CORRECTED HERE: this docstring said "no new lever", and the CONTRACT said
    LOOP_ORDER already places judge on the dom.manage pass. It does not -- MEM.judge has NO
    LOOP_ORDER ROW; it is in DEFERRED_ENTRY_POINTS for want of the scorer, and the row above is what
    to write when it returns.

    WHAT IS CHECKED IS A LEVER, AND IT IS THE ONE GENUINELY OPEN HALF OF Q-MEM-8 (see judge_frac,
    a CENSUS AMENDMENT). The checked set per pass is (every entry whose selfcon is -1, i.e. written
    since the last pass) plus (a judge_frac slice of the already-checked population, taken by
    DETERMINISTIC STRIDE from a rotating cursor, never a random draw). judge_frac = 0.0 is the
    shipped default and re-scores nothing; 1.0 is a full re-score every pass and costs about 1.7x
    the whole training compute of a 100-Window interval at the shipped d_capacity and key_win.
    Neither is forced, they differ by ~20x in cost and they differ in MEANING -- at 0.0 the median +
    k*MAD population mixes scores taken under models thousands of windows apart -- so the tree
    leaves both reachable and states the measurement instead of arguing. FLAGGING STILL RUNS OVER
    THE WHOLE CHECKED POPULATION whatever judge_frac is; the lever sizes the re-score, not the flag.

    LEVERS READ: verify, wrong_read, wrong_sweep, recon_hid, recon_tok, judge_frac
    WIRES READ: none
    DID IT FIRE: store.n_judge_runs, n_checked, n_rescored, n_judge_cursor_wraps, n_flagged,
                 n_swept. n_checked <= 10 is the state in which the flag rule returns all-False and
                 the whole filter is inert; the Gate prints THAT ARITHMETIC rather than printing
                 nothing. n_rescored == 0 with judge_frac == 0.0 is `armed but 0 (judge_frac=0.0,
                 the re-score is off)` and NOT unreachable; n_judge_cursor_wraps == 0 with
                 judge_frac > 0 says the sweep never came round, which is a different finding from
                 a sweep that found nothing.
    """
    mem = mem.owned_by("MEM")
    raise NotImplementedError(
        "MEM.judge: P4 (memory) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section MEM.")


def census(mem: Config, store, *, reconcile=False):
    """Everything the report and the domain manager need to know about the store, in one call.

    RETURNS StoreCensus, declared in this module's RECORD TYPES RETURNED block. Until 2026-09-02 the
    fields lived only in the prose below, so the four `produces` entries that cross into DOM and FAB
    passed K11 by word-appearance rather than by declaration -- K11 says so itself: it "cannot tell
    a returned field from a mention, and it does not try". TOK.vocab_state's D-T3 is the live defect
    an undeclared key produced, and this is the same shape (Q-MEM-11).

    reconcile=True recomputes the per-source counts EXACTLY from (src & active) and reports the
    drift against the incrementally-maintained table. The incremental table is the floor's only
    input and it is the thing that went silently wrong. At d_capacity = 8192 an exact recount is
    8192 elements and is affordable on the management cadence -- 24x cheaper than at the 200,000
    the operator used to type.

    "floor_entries" is the number DOM's cull needs and is what REPLACES THE REACH-THROUGH at
    self_organize.py:3688. "quota_arm" says which of D3's two arms is running: "reservoir" at
    src_share > 0, "pressure_signal" at src_share == 0 -- whose other half is FAB's
    grow_on_mem_pressure, so the report must join two packages to name the arm.

    `pressure` is main/(main+prob) over eviction BRANCHES, and Q-MEM-4 is RESOLVED 2026-09-02 (a):
    KEEP THE DEFINITION, KEEP pressure_thresh AT 0.80, DECLARE THE GATE, AND MEASURE BEFORE
    RETUNING. What changed is the REASON, and the corrected reason is stronger than H33's. H33 says
    probation is over budget at the measured write:read ratio (82% of the store) so pressure reads
    ~0. The operative chain today is shorter and it is exact, not approximate: only a retrieval
    promotes out of probation (levers.py, probation_frac); the only in-loop retrieval is
    MEM.maintain's job 1, whose `probe_contexts` HAS NO PRODUCER, and MEM.read is a DEFERRED entry
    point for want of `queries`. So n_promoted is IDENTICALLY 0, probation is 100% of the store,
    every eviction takes the probation branch, n_evict_main is identically 0 and pressure is exactly
    0.0 -- for EVERY configuration, not "~0 at the measured ratio". The number is not mis-tuned; it
    is structurally constant until P5 lands the contexts, and retuning either lever against a
    constant is unfalsifiable.
    THE GATE THEREFORE REPORTS A STATE, NOT A NUMBER. Whenever n_promoted == 0 over the interval it
    prints `unreachable (no promotion path: probe_contexts has no producer, n_promoted=0)` with that
    arithmetic, never `0.000` -- which is H33's own point read one level up, that a signal which
    cannot reach its threshold is indistinguishable from a healthy one. It prints
    probation_share/probation_frac and n_probe_fired/n_promoted beside pressure/pressure_thresh,
    AND it names BOTH causes of a silent zero, because there are two: no promotion path, and the arm
    is not selected (src_share=0.5 > 0 makes quota_arm "reservoir", and FAB.grow_on_mem_pressure
    ships False, so the pressure_signal arm is off at both ends).
    probation_frac IS A PER-BLOCK PREDICATE (write's own "INSIDE that set"); `probation_share`
    reported here is a store-wide aggregate and is not the thing the eviction branch tests. At the
    shipped defaults those differ by the 64 blocks.
    EXPECT THE RETUNE TO GO UP, NOT DOWN. Once the probe has material the rates invert: ~probe_rows/
    probe_every = 64/25 = 2.56 query rows per window at topk=8 is up to ~20 entry-touches per
    window against ~1 gated write per window, so probation can fall UNDER its budget and pressure
    can pin at 1.0 above 0.80 permanently. Both pinned-at-0 and pinned-at-1 are live outcomes and
    only a run with the probe fed can say which.
    THE READING IS NOT A WIRE AND MUST NOT BECOME ONE. pressure_thresh's only reader is this
    function; FAB.grow_check takes `memory_pressure` and reads no threshold, so the comparison
    against 0.80 happens HERE and what the root passes to FAB must already be MEM's VERDICT. A store
    occupancy measured at runtime can never be a wire -- a Coupling.compute sees only frozen Configs.

    LEVERS READ: src_share, probation_frac, pressure_thresh, quota, evict
    WIRES READ: none
    DID IT FIRE: this call IS the DID IT FIRE surface for the package; it also maintains
                 n_census_reconciles and census_drift, and a nonzero census_drift is itself a
                 defect signal rather than a repair. The `mem.pressure` Gate reads
                 store.n_promoted, n_probe_fired, n_evict_main and n_evict_probation, and covers
                 BOTH unreachability causes named above
    """
    mem = mem.owned_by("MEM")
    raise NotImplementedError(
        "MEM.census: P4 (memory) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section MEM.")


def state_dict(mem: Config, store):
    """The checkpoint blob. Everything mutable that the store cannot re-derive: keys, tok, src,
    pos, ctx, own, active, use, last, born, prob, selfcon, recon, nsrc_max, gate_theta,
    gate_seeded, ctx_w, the rekey cursor, the write counter behind use_decay_every, the tick clocks,
    and every store.n_* counter.

    THREE OF THOSE NAMES ARRIVED WITH THE TWO CADENCED BODIES AND ONE LEFT. `ctx` is now the stored
    CONTEXT WINDOW rather than one long per entry, because it is the only thing MEM.maintain can
    re-encode a key from, and `ctx_w` is its width, carried so the other side restores the rows
    without re-deriving it from a lever that may have moved between the two runs. `gate_seeded` is
    what makes the restored `gate_theta` readable: 0.0 is both "never seeded" and a legal admission
    bar, and the two behave differently on the next write. WHAT LEFT IS `nsrc`, which this line
    claimed and this function has never written: the per-source census is REBUILT EXACTLY from the
    saved rows by open_store(restored=...) -- _restore_by_block's own paragraph says so and is what
    closed C16 -- so it is re-derivable by construction and does not belong in a list of things that
    are not. The claim was harmless and it was still a claim nobody could check against the code
    three lines below it.

    THE FOUR OMISSIONS IN THE OLD BLOB WERE EACH A LIVE MECHANISM DISARMED AT THE RUN BOUNDARY:
    prob (M52 -- scan resistance off exactly when a new area arrives), recon (M66), nsrc_max
    (M53/M67 -- the starvation alarm's only baseline), gate_theta (ISSUES:537 -- a resumed run
    writes on a different threshold than the one it stopped with).

    Blocks are stored WITH their block index; open_store(restored=...) places rows back by block
    and refuses a geometry change rather than truncating in save order.

    LEVERS READ: none (a pure read of `store`)
    WIRES READ: none
    DID IT FIRE: store.n_state_dicts
    """
    mem = mem.owned_by("MEM")
    # ROW BY ROW, EACH CARRYING ITS OWNER BLOCK, which is the shape _restore_by_block reads. Blocks
    # are stored WITH their block index so open_store places rows back BY BLOCK and refuses a row
    # whose block no longer exists, rather than truncating in save order. Lowering MEM_OWNERS makes
    # some recorded blocks unreachable, and keeping whatever fitted made which memories survive a
    # resume a function of WRITE ORDER -- silently, on the boundary every goal-B number is
    # measured across.
    rows = []
    for i in range(int(store.capacity)):
        if not bool(store.active[i]):
            continue
        rows.append({
            "key": store.keys[i].detach().cpu().tolist(),
            "tok": int(store.tok[i]), "src": int(store.src[i]),
            "pos": int(store.pos[i]),
            # THE CONTEXT WINDOW, NOT A SCALAR. It is the only thing MEM.maintain can re-encode a
            # key from, so a blob without it resumes into a store whose keys can never track the
            # model again -- a forgetting channel that survives the resume silently.
            "ctx": store.ctx[i].detach().cpu().tolist(),
            "own": int(store.own[i]),
            # THE FOUR OMISSIONS OF THE OLD BLOB, EACH OF WHICH DISARMED A LIVE MECHANISM AT THE RUN
            # BOUNDARY. `prob` is M52: probation is scan resistance, and losing it turns it off
            # exactly when a new area arrives. `recon` is M66 and `selfcon` its twin -- a resumed
            # store whose judgements had all reset to 0.0 was indistinguishable from a fresh one to
            # the wrongness detector, and judge()'s -1 "unchecked" sentinel is what makes the
            # difference readable.
            "prob": bool(store.prob[i]),
            "use": float(store.use[i]), "last": int(store.last[i]), "born": int(store.born[i]),
            "recon": float(store.recon[i]), "selfcon": float(store.selfcon[i]),
        })
    out = {
        "rows": rows,
        "tick": int(store.tick),
        # THE WRITE COUNTER BEHIND use_decay_every. It counts ENTRIES WRITTEN, not steps, so a
        # resume that restarted it would postpone the next decay by a whole interval.
        "n_written": int(store.n_written),
        # nsrc_max IS SAVED RATHER THAN RE-DERIVED on the other side, and that is M53/M67: it is the
        # starvation alarm's only baseline, and re-deriving it from the restored counts forgets
        # every source that was evicted before the save -- so the alarm compares against a peak
        # that never happened.
        "nsrc_max": int(store.nsrc_max),
        # gate_theta IS THE FOURTH (ISSUES:537). A resumed run that rebuilt it writes on a
        # different threshold than the one it stopped with, so the surprise gate is recalibrated by
        # the act of resuming.
        "gate_theta": float(store.gate_theta),
        # WITHOUT THIS FLAG THE NUMBER ABOVE IS NOT ENOUGH. gate_theta=0.0 is both "never seeded"
        # and a legal admission bar, and the two behave differently on the next write: one re-seeds
        # from the first batch after the resume, the other does not.
        "gate_seeded": bool(store.gate_seeded),
        # THE WIDTH OF THE ROWS ABOVE, so the other side restores them without re-deriving it from
        # a lever that may have moved between the two runs.
        "ctx_w": int(store.ctx_w),
        "rekey_cursor": int(store.rekey_cursor),
        "counters": dict(store.counters),
    }
    store.counters["store.n_state_dicts"] = store.counters.get("store.n_state_dicts", 0) + 1
    return out


def rekey_period(mem: Config):
    """The memory rekey cadence, AS units.Windows. Handed to RUN's Cadences.due under 'dom.rekey'.

    Same reason as FAB.manage_period and DOM.manage_period: Cadences.due refuses a bare int, and
    Config hands one back for every lever that declares a Clock unit (ISSUES P1-H51). This was one of
    the three rows that would have raised on the first evaluation.

    THE KEY IS 'dom.rekey' AND THE PERIOD IS MEM'S, which looks wrong and is not: the old line made
    TWO foreign reads in one statement (:6688-6689), and the split keeps the threshold with the
    package that declares it while the spine delivers the event to DOM. MEM.maintain compares this
    same lever against a Windows `now` internally; that is the second gate on one lever, and
    docs/04_CONTRACT.md's cadence table names both so the ledger cannot describe only one of them.

    LEVERS READ: rekey_every
    WIRES READ: none
    DID IT FIRE: no counter of its own -- Cadences.ledger()['dom.rekey'] is the surface.
    """
    mem = mem.owned_by("MEM")
    every = int(mem.rekey_every)
    # A NEGATIVE REKEY CADENCE IS REFUSED HERE, AT THE FIRST PLACE `rekey_every` IS READ (added
    # 2026-09-04 under the owner's ruling; the switch and the alternatives are at
    # REFUSE_NEGATIVE_PERIOD at the top of this file). FIRST and not ONLY: maintain reads the same
    # field for its own internal amortized re-encode, and this accessor is called at the `cadence`
    # row of spine/compose.py::ASSEMBLY_ORDER while maintain is a LOOP_ORDER row, so the refusal
    # still fires before any number is derived from the bad value anywhere in this package. That is
    # the placement rule capacity/api.py::new_valve took from lm/api.py::resolve, applied here
    # rather than copied: a range check over MEM's own lever at its first read, and MEM declares no
    # refusal entry point for it to live in.
    #
    # THE SECOND READER IS ALSO WHY THIS ONE IS THE WORST OF THE FIVE TO LEAVE UNREFUSED, and this
    # is a split a reader can check in this file rather than a hazard imagined for it. maintain
    # arms the re-encode on `rekey_every > 0`, so a negative reads as DISARMED there; the spine's
    # dom.rekey gate goes through RUN.Cadences.due, whose contract is "True at most once per
    # `period` WINDOWS elapsed since this key last fired", so at -5 it is true on the FIRST window
    # and on every window after. ONE LEVER, TWO MECHANISMS, and at a negative value they disagree
    # about which one is running -- the store quietly stops tracking the model while the event is
    # delivered to DOM every window. docs/04_CONTRACT.md already names this field as driving two
    # mechanisms and two gates; a value that makes the two mean opposite things is exactly what a
    # range check at the first read is for.
    #
    # WHAT A NEGATIVE ACTUALLY DOES TODAY, MEASURED RATHER THAN ASSUMED. `assemble.build` accepts
    # MEM_REKEY_EVERY=-5 and freezes it; this accessor returned Windows(-5); and
    # spine/derive.py::cadences_that_cannot_fire then reported ("dom.rekey", -5, 0) -- the same
    # shape of line it prints for the value the store treats as DISARM.
    #
    # ZERO IS NOT TOUCHED AND ITS DECLARED MEANING IS PRESERVED EXACTLY. maintain declares
    # `rekey_every == 0` as DISARM, behind a guard, and records why: the old tree documented 0 as
    # the off switch and then divided by it, an untrippable guard whose escape hatch was a
    # ZeroDivisionError. The test below is strictly `< 0`, so that off switch is untouched -- which
    # is the point, because the negative range is the one that has no declared meaning at all.
    #
    # IT REMOVES NO CONFIGURATION. "Never re-encode" is MEM_REKEY_EVERY=0 and "re-encode as often as
    # possible" is MEM_REKEY_EVERY=1; the negative range spells neither.
    if REFUSE_NEGATIVE_PERIOD and every < 0:
        raise LeverError(
            f"MEM_REKEY_EVERY={every}: a rekey period is a count of windows ELAPSED since the last "
            f"pass and may not run backwards. It drives TWO mechanisms and at a negative value they "
            f"disagree: MEM.maintain arms its amortized re-encode on `rekey_every > 0`, so {every} "
            f"reads there as DISARMED, while the spine's dom.rekey gate goes through "
            f"RUN.Cadences.due, which fires when `step - last_fired >= period` and so is true on "
            f"the first window and on every window after it. The store would stop tracking the "
            f"model while the event fired every window. Neither meaning is lost: MEM_REKEY_EVERY=0 "
            f"is the declared DISARM and MEM_REKEY_EVERY=1 re-encodes the whole readable store "
            f"every window. MEM_KEY_SRC is not consulted here: this refuses an out-of-range value "
            f"for MEM's own lever, whether or not a second lever makes it moot.")
    return U.Windows(every)
