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
                 TWO MORE FIELDS THE BODY RETURNS, DECLARED HERE IN THE FORM
                 fabric/api.py::grow_check uses for the extra ledger keys its own body writes: a
                 field on the record the contract does not admit to producing is the same defect as
                 a declared field nothing fills, and the count is taken in both directions.
                   counters -- the name the pass-through clause above takes in the body, as a dict
                     copied ONE LEVEL DEEP. store.counters['store.n_writes_by_block'] is a LIST, so
                     a frozen record holding a live reference to it is still a caller that can
                     change what the run reported -- WriteReceipt's own reason, one container in.
                   gates -- the store's declared spine/gate.py::Gate objects. census's own frozen
                     DID IT FIRE line makes that call this package's did-it-fire surface, and MEM
                     may not import fabric/api.py::_three_state (O10), so without this field the
                     seven mem.* gates reach no reader at all: spine/loop.py::_gate_report is keyed
                     to the tok. and fab. books alone, and spine/loop.py::_report copies
                     store.counters straight out -- so the numbers cross the boundary and the
                     reachability does not. THE FIELD HAD NO READER EITHER until 2026-09-24:
                     _report copied the census's numbers and dropped `.gates`. It now renders them
                     as `gate:mem.*` entries in its MEM.census(reconcile=True) row, through
                     spine/gate.py::three_state (Q-MEM-12). The alternative considered and rejected was FAB's
                     `gate:<name>` string rows inside the counters dict, which makes a mapping of
                     ints heterogeneous and breaks the absent/0/positive convention
                     spine/loop.py::_gate_report reads.
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

    `vocab_slots` IS HELD HERE BECAUSE TWO ENTRY POINTS NEED IT AND NEITHER SIGNATURE OFFERS
    ANOTHER ROUTE. open_store's frozen signature has taken `vocab_slots` since it was written and
    its body DROPPED IT: spine/compose.py hands over int(LM.vocab_slots) and nothing read it, which
    is this project's own thesis performed inside the store -- a declared argument that decides
    nothing. MEM.read returns `dist` as (B, V) and declares no lever and no wire that could supply
    V; memory/api.py::judge's recon arm has to fit a reconstructor of that width and its signature
    is (mem, store, *, scorer, reconstructor). So the Store is the only carrier, and it is not
    checkpointed for the same reason `capacity` is not: open_store is re-handed LM.vocab_slots on
    resume, and a width saved in a blob could disagree with the model that is about to be loaded.
    """

    __slots__ = ("keys", "tok", "src", "pos", "ctx", "ctx_w", "own", "active", "prob", "use",
                 "last", "born", "selfcon", "recon", "tick", "gate_theta", "gate_seeded",
                 "n_written", "rekey_cursor", "rekey_snap", "nsrc", "nsrc_max", "live_src",
                 "capacity", "quota", "owners", "key_dim", "vocab_slots", "lm_kind", "counters",
                 "gates", "rng", "gen")

    def __init__(self, *, capacity, quota, owners, key_dim, vocab_slots, device, rng, lm_kind):
        z = lambda *shape, dtype=torch.float32: torch.zeros(*shape, dtype=dtype, device=device)
        self.capacity, self.quota, self.owners = capacity, quota, owners
        self.key_dim, self.lm_kind, self.rng = key_dim, lm_kind, rng
        # THE WIDTH OF THE TOKEN DISTRIBUTION MEM.read RETURNS, and nothing else in this class is
        # sized by it. It is a MODEL geometry travelling with the store rather than a store
        # geometry: a stored token id outside it is a store keyed to a segmentation the model no
        # longer has, which MEM.maintain's job 3 leaves visibly stale on purpose.
        self.vocab_slots = int(vocab_slots)
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


_FROZEN_KEYS_UNBUILT = (
    "the frozen byte-statistic key table is DECLARED and NOT BUILT in this tree. Nothing in src/ "
    "computes one, no lever sizes it and no argument carries one -- `key_fn` is the live model's "
    "encoder, which is the other arm. Writing with it anyway would put model keys in a store the "
    "operator asked to key by bytes, which is the exact silent substitution MEM_KEY_SRC's choices= "
    "exists to refuse. What closes this: a frozen encoder on MEM's own surface, or a second "
    "callable argument beside key_fn -- both are signature changes and therefore the owner's call.")
"""The one sentence MEM_KEY_SRC=frozen is refused with, at MEM.open_store (startup) and at
MEM.write (the point of use), so the two refusals cannot drift apart."""


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

    MEM_KEY_SRC=frozen IS REFUSED HERE, AT STARTUP, WITH spine/gate.py::NotBuilt (2026-09-24). The
    frozen byte-statistic key table is declared and not built, and until this date the only
    refusal was at the point of use, in MEM.write: compose() returned with 0 refusals, ran the whole
    SIG warm-up and the run died at its FIRST FLUSH (driven: MEM_KEY_SRC=frozen at
    DATA_STREAM_BYTES=60000). The store is where the key source is first decided, so the refusal
    is here; write() keeps its own for a caller that reaches it by another route.
    """
    mem = mem.owned_by("MEM")
    if str(mem.key_src) != "model":
        raise NotBuilt(
            f"MEM_KEY_SRC={str(mem.key_src)!r}: {_FROZEN_KEYS_UNBUILT} Refused at MEM.open_store, "
            f"before the store is allocated, rather than at the first flush's MEM.write. Run at "
            f"MEM_KEY_SRC=model.")

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

    # `vocab_slots` IS PASSED ON RATHER THAN DROPPED, which it was until MEM.read acquired a body.
    # It is not a size argument in the sense the paragraph above refuses: it sizes nothing in this
    # store, it is the width of the distribution MEM.read returns, and the operator still sizes the
    # store through `quota` and `owners` alone. See Store's own docstring for why the Store is the
    # only route -- read and judge both need it and neither frozen signature can carry it.
    store = Store(capacity=capacity, quota=quota, owners=owners, key_dim=int(key_dim),
                  vocab_slots=int(vocab_slots), device=device, rng=rng, lm_kind=str(lm_kind))
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
    if restored is not None:
        # THE COUNTERS WERE SAVED AND NEVER READ BACK -- the same shape as the rekey cursor
        # memory/api.py::_restore_by_block repairs eight lines from its end, on the surface this
        # project measures goal B with. memory/api.py::state_dict has written
        # "counters": dict(store.counters) since the day it was written and nothing on this side
        # ever assigned it, so every n_* number restarted at 0 on the far side of a resume:
        # store.n_entries_deleted_by_cull is THE GOAL-B NUMBER -- how much of the store the domain
        # manager destroyed -- and a resumed run reported it per SEGMENT while the run it describes
        # is the concatenation. A forgetting number that forgets at the resume boundary is the
        # defect the four checkpointed additions below it were each added to close.
        # IT RUNS HERE AND NOT IN _restore_by_block, and that is not a preference: the assignment
        # directly above REPLACES store.counters wholesale, so a restore written on the other side
        # of it would be overwritten by the seed a few microseconds later and the whole repair
        # would read as a no-op nobody could see. The five keys seeded above describe THIS open --
        # the capacity opened, the rows this restore placed and refused, the block count and the
        # census width -- so the blob may not overwrite them; everything else is the previous
        # segment's tally and carries forward.
        # THE GENERATOR COMES BACK WITH THE ROWS, so the next eviction continues the parent's
        # stream instead of replaying its first draws. A blob written before the key existed has
        # none, and the store keeps the freshly seeded stream -- the pre-2026-09-24 behaviour.
        if restored.get("gen") is not None:
            store.gen.set_state(torch.as_tensor(restored["gen"], dtype=torch.uint8).cpu())
        _seeded = set(store.counters)
        for _k, _v in dict(restored.get("counters") or {}).items():
            if _k in _seeded:
                continue
            if isinstance(_v, list):
                # store.n_writes_by_block IS THE ONE LIST AND ITS WIDTH IS A GEOMETRY, not a
                # value: MEM_OWNERS can differ between the run that saved and the run that resumes
                # (the row restore above refuses ROWS naming a block this run lacks, which is a
                # different question from how wide the tally is). Truncated and zero-extended to
                # THIS run's block count, so the list a reader indexes by block index is always
                # indexable by every block index this run has.
                _l = [int(x) for x in _v][:owners]
                store.counters[_k] = _l + [0] * (owners - len(_l))
            else:
                store.counters[_k] = _v
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
    # DOM'S VERDICT FIRST, THE CENSUS ONLY AS THE FALLBACK. Re-deriving this from the restored rows
    # unconditionally is the 125-against-27 defect memory/api.py::_unprotected measures, reinstated
    # by the act of resuming: the run stopped with a divisor of 27 live domains, the rows carry 125
    # source ids, and this line silently handed the next segment 125 -- so every live domain's
    # reservation shrank by 4.6x across a boundary nothing reports. It is not re-derivable, because
    # it is not a property of the rows: it is what the domain manager last SAID, and only the blob
    # can carry it.
    # A BLOB WITHOUT THE KEY READS 0 AND FALLS BACK, which is the conservative arm and is exactly
    # what this line did before: a checkpoint written before live_src was saved resumes on
    # "sources holding entries", the frozen tree's documented live_src=None behaviour, rather than
    # on a zero that would disarm the floor's divisor outright.
    _ls = int(blob.get("live_src", 0))
    store.live_src = _ls if _ls > 0 else int((store.nsrc > 0).sum())
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
by nothing -- the `mem.write_target` Gate declared in write() says exactly that, and since
2026-09-24 the R stage's MEM.census row prints it).
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


def _floor_entries(store, share):
    """-> (floor, live): the per-source reservation ACTUALLY IN FORCE, and the divisor it used.

    ONE EXPRESSION FOR ONE QUANTITY, IN THREE PLACES. The number memory/api.py::_unprotected
    enforces against candidates, the number memory/api.py::census puts on its record, and the number
    DOM.manage's cull brake is judged against are the same reservation, and the moment they are two
    spellings they are "one quantity, two answers" -- the shape the `capacity != owners * quota`
    guard in memory/api.py::open_store already exists for. domains/api.py::manage's own contract
    says a wire quietly recomputed at the call site is self_organize.py:3688 under a new name; this
    is that rule applied one call in, where the recomputation would be in the same file.

    THE `live` IT RETURNS IS THE DIVISOR THAT WAS ACTUALLY USED and is what belongs on a report,
    not the raw store.live_src field. Store.__init__ sets live_src to 0 and
    memory/api.py::apply_domain_plan is the only thing that ever sets it from DOM's verdict -- on
    the management cadence, so until the first pass of a run has been carried here the divisor is
    "sources holding entries" while the field still reads 0. Measured on a warmed store with no
    call site at all: the field read 0 while the divisor was 6. Printing the field
    beside a floor computed over 27 sources is the defect memory/api.py::open_store refuses
    MEM_OWNERS below 1 over: the printed configuration and the running one disagreeing about a
    number, one of them in a report nobody can check against the other.

    IT RETURNS 0 ON THREE DIFFERENT ARMS AND THE CALLERS MUST NOT READ THAT AS A FLOOR OF NOTHING
    TO ENFORCE: src_share disarmed, one source HOLDING ENTRIES, and a reservation that rounds below
    one entry are three different configurations with one consequence here. The middle one is asked
    of the store's census and NOT of `live` -- a partition that has merged down to one live domain
    is not a store with nothing to protect, and the body below says why at length. memory/api.py::census reports the
    floor in force and DOM's brake is `memory_counts[did] >= mem_floor_entries`, which at 0 is
    satisfied by every domain including empty ones -- the frozen tree carries the `if _fl > 0`
    guard that prevents it (self_organize.py:3688) and DOM.manage owes it.
    """
    has = store.nsrc > 0
    n_has = int(has.sum())
    live = int(store.live_src) if int(store.live_src) > 0 else n_has
    # `n_has <= 1`, NOT `live <= 1`, AND THE DIFFERENCE IS A FLOOR THAT SWITCHES ITSELF OFF. The
    # short-circuit says "there is nothing here to protect anything FROM", and that is a statement
    # about the STORE: with one source holding entries the only candidates eviction can see are
    # that source's own, so protecting them leaves eviction nothing to take. Asked of `live`
    # instead, it also caught the case where DOM reports exactly ONE LIVE DOMAIN -- and the day
    # MEM.apply_domain_plan stopped being a stub and became a wired call site, that stopped being
    # hypothetical: a partition that merges down to a single domain writes store.live_src = 1 and
    # the per-source reservation DISARMS ITSELF against a store that may still hold six sources'
    # worth of entries. Nothing in the report would have said so -- census would print
    # floor_entries 0, which is also what src_share=0 and a sub-entry rounding print, so the one
    # reading that means "the mechanism turned itself off" is spelled the same as the two that mean
    # "the operator turned it off". That is the defect docs/04_CONTRACT.md's G4 is about, one layer
    # down from a counter.
    # WHAT THE NARROWED FORM DOES ON THAT ARM is protect up to src_share * capacity for the single
    # live domain, which is exactly its entitlement, and memory/api.py::_unprotected cannot lock up
    # on it: if protection would leave fewer than `need` candidates the filter is dropped FOR THAT
    # CALL and counted, so the worst case is the old behaviour with a number attached.
    if share <= 0.0 or n_has <= 1:
        return 0, live
    floor = int(share * int(store.capacity) / live)
    return (floor if floor > 0 else 0), live


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
    SET on the Store, which no signature in this file carries; what memory/api.py::apply_domain_plan
    does instead is set the COUNT and REPORT the residue as store.n_orphan_sources, so the gap is a
    number rather than an inference. THE RESIDUE IS NOT A STANDING CONDITION, and that is the part
    worth knowing before anyone mints the set: a merged id is relabelled and a culled id is emptied,
    so an orphan can only survive a pass whose plan nobody applied. Measured on one warmed
    configuration, both ways: 3 orphans out of 6 sources holding entries with no call site, 0 out of
    3 with the plan carried on every pass.
    """
    if share <= 0.0:
        # THE SUPERSEDED RULE IS STILL REACHABLE, which is what D3 asks for: src_share=0 disarms the
        # reservoir and leaves "pressure is a signal, not a wall" as the selectable arm.
        return cand, 0, False
    # THE ARITHMETIC IS memory/api.py::_floor_entries' AND NOT THIS FUNCTION'S ANY MORE, so the
    # number this filter ENFORCES and the number memory/api.py::census REPORTS cannot drift apart.
    # The two other early returns this replaces -- one source HOLDING ENTRIES, and a reservation
    # that rounds below one entry -- both come back as floor 0 and are still returned unchanged.
    floor, _live = _floor_entries(store, share)
    if floor <= 0:
        return cand, 0, False
    has = store.nsrc > 0
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
    # THE PROMOTION CLAUSE IS READ OFF THE COUNTERS, NOT WRITTEN AS PROSE. Until 2026-09-24 it said
    # "spine/loop.py::_flush passes probe_contexts=None ... store.n_reads stays ABSENT, and every
    # eviction still takes the probation branch" -- three days after the loop began passing the
    # previous flush's batch, in the same report that printed n_reads 3, n_promoted 24 and
    # n_evict_main 128. The retrieval that promotes is memory/api.py::maintain's probe, and whether
    # it has run is what store.n_reads / n_promoted say, ABSENT and 0 being different findings.
    _promoted = store.counters.get("store.n_promoted")
    _promo = (f"store.n_promoted {int(_promoted)} over store.n_reads "
              f"{int(store.counters.get('store.n_reads', 0))}: the retrievals memory/api.py::"
              f"maintain's probe issues are what moves an entry out of this region."
              if _promoted is not None else
              "store.n_promoted is ABSENT: memory/api.py::read has not run yet on this run -- "
              "maintain's probe has issued no query row (it reads the PREVIOUS flush's batch, so "
              "the first flush has none) or MEM_PROBE_EVERY=0 disarms it -- so nothing has been "
              "promoted and every entry this store holds is still on probation.")
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
                    f"probation until a retrieval promotes it. " + _promo),
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
    evicted = 0
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
        # AN EVICTION IS AN OCCUPIED ENTRY OVERWRITTEN, AND THAT IS vic AND NOTHING ELSE. The
        # return below used to count all `m` rows of the commit under the branch whenever the
        # block ran out of free slots, so a commit that filled 8 free slots and overwrote 57 entries
        # reported 65 evictions and 8 free placements -- the free rows counted twice. Measured
        # before the repair on an 80-window MEM_WRITE_MODE=quantile run: committed 2393 against
        # free + probation + main = 2075 + 509 + 0 = 2584, and 318 entries actually overwritten
        # against 509 reported. The default fixed arm balanced only because every window keeps
        # exactly `quota` rows, so a block is either wholly free or wholly full.
        evicted = int(vic.numel())
    # THE IDENTITY THE THREE COUNTERS ARE READ BY: every committed row went into a free slot or
    # displaced an occupied one, never both and never neither. Refused by name rather than asserted,
    # so a future _victims that pads short or long cannot re-open the double count silently.
    if free_used + evicted != m:
        raise StoreError(
            f"MEM.write committed {m} row(s) into owner block {o} and accounted {free_used} free "
            f"placement(s) + {evicted} eviction(s) = {free_used + evicted}. The eviction counters "
            f"are this store's forgetting count and MEM.census's pressure is computed from them, so "
            f"a commit they do not add up over is refused rather than reported.")

    # DUPLICATES ARE REFUSED, NOT COLLAPSED. Index assignment collapses a repeat silently -- keys[idx]
    # with idx naming slot j twice writes the later row and drops the earlier -- so the store reports
    # m writes and holds fewer. The damage is in the accounting: the census below decrements the
    # displaced owner ONCE PER OCCURRENCE while crediting the new source idx.numel() times, which
    # overcharges the displaced source and drives its count NEGATIVE (measured drift 9 in 200). The
    # two known producers are fixed above; this is the invariant so a third cannot be silent.
    # SEEDED BEFORE THE TEST THAT DECIDES (G4): this tripwire must read 0, and a 0 is only a
    # reading if the key is present -- ABSENT is this tree's word for "the check never ran".
    _bump(store, "store.n_dup_refused", 0)
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
    # SEEDED ON EVERY COMMIT, BEFORE THE BRANCH (G4) -- the same tripwire reading as n_dup_refused.
    _bump(store, "store.n_src_underflow", 0)
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
    return m, free_used, (evicted if branch == "probation" else 0), \
        (evicted if branch == "main" else 0), blocked, deadlock


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
        # SINCE 2026-09-24 MEM.open_store refuses this arm at startup with the same sentence, so
        # the composition root never reaches here on it; this is the second line for a caller
        # that holds a store opened by another route.
        raise NotBuilt(f"MEM_KEY_SRC={ksrc!r}: {_FROZEN_KEYS_UNBUILT}")

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
    # THE TRUNCATION TRIPWIRE IS SEEDED ON ITS REACHABLE ARM ONLY, BEFORE ANY RETURN (G4). A window
    # presents at most L positions and a block holds `quota`, so at L <= quota -- the shipped
    # LM ctx 128 against MEM_QUOTA 128 -- no window can present more survivors than its block
    # holds and the key stays ABSENT, which is the correct reading of an unreachable mechanism.
    # At L > quota it is armed on every call, so it is present from the first write.
    if L > quota:
        _bump(store, "store.n_write_truncated", 0)
    if kept == 0:
        # THE EARLY RETURN SEEDS THE SAME BOOK THE FULL PATH BUMPS. It seeded n_writes_committed
        # alone, so a run whose gate kept nothing printed n_writes_committed 0 beside ABSENT
        # eviction and floor counters -- ABSENT reading as "unreachable on this arm" for a path that
        # was armed and simply had no rows to place.
        for _k in ("store.n_writes_committed", "store.n_evict_free", "store.n_evict_probation",
                   "store.n_evict_main", "store.n_floor_blocked"):
            _bump(store, _k, 0)
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



# ==================================================================================================
# THE THREE RETRIEVAL NUMBERS, WHICH ARE NOT LEVERS AND SAY SO HERE
# ==================================================================================================

READ_TAU, WRONG_MAD_K, WRONG_MIN_CHECKED = 0.1, 2.5, 10
"""The temperature of the top-k vote, the k of the median + k*MAD wrongness flag, and the number of
checked entries below which that flag is all-False. Module constants, with no env name.

THEY TAKE GATE_STEP/GATE_FLOOR/GATE_CEIL's STANDING ARGUMENT, one section up, and it is not restated
at length: memory/levers.py's own accounting is "21 rename + 3 keep -> 24 levers declared, 8 drop",
none of these three was ever an environment knob in the tree this is ported from, and minting names
for them here would be minting levers the census refused in the file that implements its decision.
Turning one is a CODE EDIT.

WHAT EACH IS, so a reader can judge the number rather than the name.
  READ_TAU is memory.py:509's `tau=0.1` default, applied at memory.py:546, and no caller in the
    frozen tree ever overrode it. It sets how sharply the top-k vote concentrates: at 0.1 a 0.1 gap
    in cosine similarity is a factor of e in vote weight, so `topk` produces a soft vote and not an
    argmax, and `conf` -- the TOP similarity -- is what the match-quality gate reads instead.
  WRONG_MAD_K is memory.py:23's `selfcon_thresh=2.5`, applied at memory.py:590 for self-consistency
    and at memory.py:607 for reconstruction. ONE constant across both detectors in the frozen tree
    and one here: two would let MEM_VERIFY's two arms flag at different strictness while every
    report line called both of them the wrongness detector.
  WRONG_MIN_CHECKED is memory.py:587's `if int(checked.sum()) > 10`. THE NUMBER IS ALREADY DECLARED
    IN A FROZEN DOCSTRING -- memory/api.py::judge's DID IT FIRE line names n_checked <= 10 as the
    state in which the flag rule returns all-False and the whole filter is inert -- so this name is
    where that declaration acquires a body rather than a new decision taken here.
"""


def _flagged(store, verify):
    """The ACTIVE wrongness detector's flag, or None when there is no detector at all.

    Adaptive median + k*MAD over CHECKED ENTRIES ONLY, which is the frozen rule (memory.py:587-591
    for self-consistency, memory.py:605-608 for reconstruction, identical but for the field).

    ONE IMPLEMENTATION, AND THAT IS WHY IT IS A HELPER AND NOT TWO BODIES. memory/api.py::judge's
    frozen docstring declares this same rule for the pass that WRITES the scores, and a second copy
    there would be two spellings of the predicate that decides whether an entry is reachable at all,
    each free to drift -- the retrieval half of exactly what Q-MEM-9 refuses. judge calls this when
    it lands; memory/api.py::read calls it now, and its WRONG_MIN_CHECKED arm is the inert state
    judge's own Gate is declared to print the arithmetic of.

    -1.0 IS THE UNCHECKED SENTINEL AND `field >= 0` IS THE CHECKED SET.
    memory/api.py::_commit_window stamps both selfcon and recon to -1.0 on every commit, so an entry
    written since the last judge pass is NOT in the population the median is taken over. That is
    what keeps the threshold on the model's current scale instead of a mixture of every scale the
    run has had -- and it is also why an end-of-run snapshot of these fields is not a measurement of
    what the flag did (H32/M42: "0 entries checked" printed in the same report as "61,952 entries
    excluded from EVERY retrieval"). The counters in read are taken where the gate gates.

    `store.active &` IS LOAD-BEARING AND NOT BELT-AND-BRACES. Store.__init__ allocates selfcon and
    recon as ZEROS while the sentinel is -1.0, so every never-written slot reads as "checked, and
    perfectly plausible" -- it is in `checked`, it is in the median's population, and only the
    active mask keeps it out of the flag. A version of this rule without it would flag on the
    store's empty space.

    verify == "off" RETURNS None AND NOT AN ALL-FALSE MASK, and the two are different facts: None is
    "there is no detector", all-False is "the detector ran and flagged nothing". read counts them
    apart -- n_wrong_reads is bumped only on the arm where a detector exists.
    """
    if verify == "selfcon":
        field = store.selfcon
    elif verify == "recon":
        field = store.recon
    elif verify == "off":
        return None                    # a first-class configuration (D4), not a code path that rots
    else:
        # THE FOURTH ARM IS A RAISE AND NOT A FALL-THROUGH, for memory/api.py::_gate_window's reason
        # one lever over: MEM_VERIFY carries choices=, so an unrecognised value is a startup
        # LeverError and cannot reach here today -- but a fourth choice added to the declaration
        # without a body here would land in the "no detector" arm and silently disarm the whole
        # wrongness filter while the report still named the mode the operator asked for.
        raise LeverError(
            f"MEM_VERIFY={verify!r} has no detector in memory/api.py::_flagged. The lever declares "
            f"choices=('selfcon', 'recon', 'off') and this helper implements those three; a fourth "
            f"arm added to the declaration without one here would fall into 'off' and turn the "
            f"wrongness filter off under the name of a mode that was asked for.")
    checked = field >= 0
    if int(checked.sum()) <= WRONG_MIN_CHECKED:
        # ARMED AND ALL-FALSE. Below this many scores the median and the MAD are taken over a
        # handful of entries and the threshold they produce is noise; the frozen tree drew the line
        # at the same count and judge's DID IT FIRE line already declares it as the inert state.
        return torch.zeros_like(store.active)
    v = field[checked]
    med = v.median()
    mad = (v - med).abs().median()
    # THE +1e-6 IS THE FROZEN SPELLING (memory.py:590) AND IT IS NOT COSMETIC. At mad == 0 -- every
    # checked entry scoring identically, which is what a freshly-judged store of one domain looks
    # like -- a bare `>= med` flags the WHOLE checked population by tie. Measured on 100 identical
    # scores: `field >= med` flags 100 of 100 and `field >= med + 2.5 * (mad + 1e-6)` flags 0. The
    # epsilon is what makes the tie break toward not-flagging, which is the direction wrong_read's
    # own 3%-precision record argues for: a flag excludes the entry from every retrieval.
    return store.active & checked & (field >= med + WRONG_MAD_K * (mad + 1e-6))


# ==================================================================================================
# WHAT ONE RETRIEVAL RETURNED
# ==================================================================================================


@dataclasses.dataclass(frozen=True)
class Retrieval:
    """One read's five arrays: the vote, its quality, what it hit, at what weight, and the mix.

    FROZEN, for the reason memory/api.py::WriteReceipt says "a caller that can write to this can
    change what the run reported".

    `dist` IS (B, vocab_slots) AND, WHENEVER THE RETRIEVAL FOUND ANYTHING, SUMS TO 1.0 BY
    CONSTRUCTION -- it is a softmax over the top-k scattered into token slots. (On the empty arm it
    is all zeros, which is the other honest answer and not a small weight.) That arithmetic is the
    whole reason `blend` is a FIELD and not something a caller derives from `dist`: the frozen
    tree's ungated weight was `dist.sum(dim, keepdim=True).clamp(max=1.0) * 0.5`
    (self_organize.py:3275-3276), and a quantity that is identically 1.0 multiplied by 0.5 is an
    unconditional 50/50 mix at every position -- the measured -0.097 b/B at 200k slots.

    `conf` IS A COSINE BY CONSTRUCTION AND NOT BY TRUST: read re-normalises `queries` before the
    matmul, and store.keys are unit-norm at every write and every rekey, so the top similarity is
    in [-1, 1] before the clamp. A caller that recomputed it from `dist` would be reproducing ISSUES
    P1-C8/C9 one layer up, which is why the number rides on the record.

    `hits` IS -1 WHERE THE RETRIEVAL DID NOT FILL A SLOT, and that convention is DEPENDED ON rather
    than merely documented: memory/api.py::maintain counts n_probe_hits as `(retrieval.hits >= 0)`
    and its own comment says it assumes exactly this. Whoever changes the fill changes that line in
    the same edit.

    `blend` IS THE WEIGHT AND NOT THE MIXTURE. memory/api.py::blend applies it; nothing else may
    recompute it, and read leaves it at blend_max rather than pre-clamping, because the one case
    that must be clamped -- blend_max == 1.0 with conf == 1.0, where the model's mass can vanish --
    is declared to live in blend, with the arithmetic.
    """
    dist: object
    conf: object
    hits: object
    weights: object
    blend: object


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
    topk, blend_max = int(mem.topk), float(mem.blend_max)
    match_floor, wrong_read, verify = float(mem.match_floor), bool(mem.wrong_read), str(mem.verify)
    dev = store.keys.device

    # ==============================================================================================
    # ALL SIX COUNTERS ARE SEEDED BEFORE ANY BRANCH DECIDES ANYTHING
    # ==============================================================================================
    # THIS IS THE WHOLE ABSENT-VERSUS-ZERO CONTRACT FOR THIS ENTRY POINT, and it is the reason the
    # loop is here and not inside the arms below. ABSENT means read was never called on the arm this
    # run took -- MEM_PROBE_EVERY=0, or no probe has yet found contexts (spine/loop.py::_flush
    # passes the PREVIOUS flush's batch, so the first flush has none). PRESENT-AND-0 means read ran
    # and the mechanism did not fire. memory/api.py::census's mem.pressure Gate distinguishes
    # exactly those two states over store.n_promoted, so seeding any of these inside the `else` of
    # the gate it describes would be the defect fabric/api.py::_bump was written to stop -- SIG's
    # cadence ledger shipped a counter absent rather than 0 for a whole run at the one configuration
    # the tree ships, because the lines that seeded it stood inside the else of their own gate
    # (sig/api.py::cadence_due carries the repaired form).
    for _k in ("store.n_reads", "store.n_read_empty", "store.n_promoted",
               "store.n_wrong_reads", "store.n_wrong_read_hit", "store.n_wrong_blocked"):
        _bump(store, _k, 0)
    _bump(store, "store.n_reads")

    # ==============================================================================================
    # A QUERY THAT IS NOT A KEY IS REFUSED BY NAME
    # ==============================================================================================
    # THE SEED AND THE n_reads BUMP BOTH SIT ABOVE THIS REFUSAL, SO A REFUSED CALL COUNTS AS A READ,
    # and that is a choice rather than an oversight. It is the cheap side of the trade: a StoreError
    # out of here ends the run, so the inflated count is read from a report that was never written,
    # whereas seeding below the refusal would put all six keys behind a condition and give ABSENT
    # two meanings -- "read was never called" and "read was called with the wrong argument".
    if not torch.is_tensor(queries) or queries.dim() != 2 or not queries.is_floating_point() \
            or int(queries.shape[1]) != int(store.key_dim):
        got = (f"{tuple(queries.shape)} of {queries.dtype}" if torch.is_tensor(queries)
               else type(queries).__name__)
        raise StoreError(
            f"MEM.read: `queries` arrived as {got} where a 2-D FLOATING (B, {int(store.key_dim)}) "
            f"is required -- these are KEYS IN THIS STORE'S OWN KEY SPACE, not contexts and not "
            f"token ids. This entry point declares no key lever and takes no key_fn, so it cannot "
            f"encode: whoever calls it narrows to MEM_KEY_WIN and encodes with the same key_fn at "
            f"the same MEM_KEY_DEPTH the write path used. memory/api.py::maintain's job 1 does that "
            f"in package, and the report path's caller must agree with it or the store is queried "
            f"in one key space and written in another -- the drift MEM_REKEY_EVERY exists to "
            f"prevent, arriving through the front door. REFUSED RATHER THAN RESHAPED, and this is "
            f"the highest-value refusal in the function: a (B, L) long tensor of token ids either "
            f"fails obscurely inside the matmul below, or -- if L happens to equal key_dim -- "
            f"retrieves SILENTLY from a space nothing was ever written in, which returns entries "
            f"and means nothing. The argument is memory/api.py::_require_rows' and the message is "
            f"written out here because that helper hardcodes the name of the other entry point.")
    B = int(queries.shape[0])
    V = int(store.vocab_slots)

    # ==============================================================================================
    # THE READABLE SET, AND NOTHING ELSE
    # ==============================================================================================
    # READS STAY GLOBAL ACROSS OWNER BLOCKS -- there is no `own` narrowing here and there must never
    # be one. That asymmetry with memory/api.py::write is this store's design and this docstring's
    # own second sentence: knowledge is owned but not walled off. It is also the one place the
    # single-write-path argument does NOT apply, because there is no partition to disagree about.
    valid = store.active.clone()

    # ==============================================================================================
    # THE WRONG FLAG, COUNTED WHERE IT GATES
    # ==============================================================================================
    # ONE DELIBERATE DEPARTURE FROM THE FROZEN TREE, AND IT IS THE REPAIR wrong_read IS NAMED FOR.
    # memory.py:521 filters `valid = self.active & (~self.is_unverified())` UNCONDITIONALLY and puts
    # only is_wrong() behind the flag -- so the reconstruction detector excluded entries from every
    # retrieval with no switch at all, which is the 63,146-entries-at-3%-precision state
    # memory/levers.py::MEMLevers records beside wrong_read. Here there is ONE detector, the one
    # MEM_VERIFY selects, and wrong_read is the only thing that decides whether it gates reads.
    # THE THREE COUNTERS CARRY THE FROZEN TREE'S EXACT MEANINGS (memory.py:110-114): n_wrong_reads
    # is read() calls made WHILE THE GATE WAS ON, n_wrong_read_hit is those of them that excluded at
    # least one entry, and n_wrong_blocked is entries excluded SUMMED OVER READS -- exclusion WORK,
    # so the same entry blocked on ten reads counts ten times. Bumping n_wrong_reads only on the
    # gate-on arm is what gives the reader three states without this body declaring a Gate its
    # docstring does not name: n_wrong_reads present-and-0 beside n_reads > 0 says the gate was OFF
    # (wrong_read false, or MEM_VERIFY=off so there is no detector at all), and n_wrong_reads equal
    # to n_reads with n_wrong_read_hit == 0 says it was on and nothing was flagged. This is the
    # H32/M42 repair in full: incremented WHERE THE GATE GATES, never derived from the flags left at
    # the end of the run, because every write resets the sentinel underneath them.
    flags = _flagged(store, verify)
    if wrong_read and flags is not None:
        _bump(store, "store.n_wrong_reads")
        blocked = int((valid & flags).sum())
        if blocked:
            _bump(store, "store.n_wrong_blocked", blocked)
            _bump(store, "store.n_wrong_read_hit")
        valid = valid & (~flags)

    # ==============================================================================================
    # THE EMPTY ARM
    # ==============================================================================================
    # n_read_empty IS BUMPED FOR M == 0 AND NOT FOR topk <= 0, because they are different findings:
    # the first says the store had nothing readable, the second says the operator asked for no
    # neighbours. n_read_empty > 0 BESIDE n_wrong_blocked > 0 is a sentence the old report could not
    # write at all -- every readable entry was excluded by the flag -- and that is what separating
    # the two counters buys.
    # MEM_TOPK DECLARES NO MEANING FOR 0 AND 0 IS AN UNDECLARED RETRIEVAL-OFF SWITCH (so is
    # MEM_MATCH_FLOOR=1.0, measured at the ramp below). This body must NOT invent a refusal for
    # either: read's frozen docstring declares none and no Gate, and a read-site refusal over a
    # lever whose declared domain does not forbid the value is what tests/test_ownership.py O15
    # calls over-refusal. The hole is named here; closing it is the owner's call, the way
    # memory/api.py::open_store's `< 1` refusal on quota and owners was.
    M = int(valid.sum())
    if M == 0:
        _bump(store, "store.n_read_empty")
    kk = min(topk, M)
    if kk <= 0:
        # `tv.max(-1)` MUST NOT RUN AT kk == 0. Measured: `torch.randn(3, 5).topk(0, dim=-1)`
        # returns a (3, 0) tensor happily and `.max(-1)` on it raises IndexError("max(): Expected
        # reduction dim 1 to have non-zero size."), which is the mechanical reason this arm returns
        # here rather than falling through with an empty top-k -- and an IndexError out of a
        # retrieval names no lever, no value and no package.
        w0 = max(0, topk)
        return Retrieval(dist=torch.zeros(B, V, device=dev),
                         conf=torch.zeros(B, device=dev),
                         hits=torch.full((B, w0), -1, dtype=torch.long, device=dev),
                         weights=torch.zeros(B, w0, device=dev),
                         blend=torch.zeros(B, device=dev))

    # ==============================================================================================
    # THE kNN AND THE PROMOTION, BOTH OUTSIDE THE GRAPH
    # ==============================================================================================
    # no_grad FOR THE REASON memory/api.py::_encode_keys GIVES -- a stored key is data -- AND ONE
    # THIS FUNCTION OWNS: retrieval has never entered the training distribution in this project, and
    # putting it in the graph is the unmeasured behaviour change Q-MEM-10 refuses. It would also
    # hold the whole flush's activations alive for as long as a retrieved entry is cited.
    with torch.no_grad():
        vi = valid.nonzero(as_tuple=True)[0]                       # (M,) GLOBAL row indices
        # RE-NORMALISING `queries` IS NOT DEFENSIVE TIDINESS: it is what makes `conf` a COSINE BY
        # CONSTRUCTION rather than by trust. read has two callers that encode at two sites --
        # memory/api.py::maintain's job 1 and the composition root's report path -- and the
        # match-quality gate below reads `conf` as a similarity in [0, 1].
        qn = torch.nn.functional.normalize(queries.detach().float(), dim=-1)
        sim = qn @ store.keys[vi].t()                              # (B, M); store.keys are unit-norm
        tv, ti = sim.topk(kk, dim=-1)                              # (B, kk)
        w = torch.softmax(tv / READ_TAU, dim=-1)                   # similarity weights
        gi = vi[ti]                                                # (B, kk) GLOBAL row indices
        # NO CLAMP ON store.tok[gi]. A stored token id outside the model's vocabulary is a store
        # keyed to a segmentation the model no longer has -- the gap memory/api.py::maintain's job 3
        # deliberately leaves visibly stale rather than rewriting under a guess -- and clamping it
        # would cast a retrieval vote for a token nobody ever stored. Let the scatter_add_ raise.
        dist = torch.zeros(B, V, device=dev)
        dist.scatter_add_(1, store.tok[gi], w)
        conf = tv.max(-1).values.clamp(0.0, 1.0)
        hits = torch.full((B, topk), -1, dtype=torch.long, device=dev)
        hits[:, :kk] = gi
        weights = torch.zeros(B, topk, device=dev)
        weights[:, :kk] = w

        if promote:
            # `use` ACCUMULATES OVER THE NON-UNIQUE HIT LIST, because it is decayed retrieval MASS
            # and two query rows wanting one entry is twice the evidence. It is a FLOAT for the
            # reason Store's own docstring gives.
            flat = gi.reshape(-1)
            store.use.index_add_(0, flat, w.reshape(-1))
            # THE UNIQUE IS A REPAIR AND IT IS MEASURED. memory.py:557 counts
            # `self.n_promoted += int(self.prob[_g].sum())` over the NON-unique index, so one entry
            # reached by two query rows counts twice. Measured on a driven store of 2,048 entries:
            # 16 query rows x topk=8 is 128 hits covering 120 DISTINCT entries, so the frozen
            # spelling would report 128 promotions where 120 entries left probation -- a 6.7%
            # overcount on the FIRST read, before any turnover at all. n_promoted came back 120, and
            # that is the exact quantity memory/api.py::census's mem.pressure Gate tests for zero,
            # so an overcount there makes the no-promotion-path reading unreadable. Same argument as
            # memory/api.py::_commit_window's duplicate refusal, one counter over.
            uniq = torch.unique(flat)
            _bump(store, "store.n_promoted", int(store.prob[uniq].sum()))
            store.prob[uniq] = False
            # THE CLOCK IS READ, NEVER ADVANCED. read takes no `now` and must not invent one:
            # memory/api.py::write and memory/api.py::maintain have already advanced `tick` to this
            # window, and Store's own docstring says MEM.read stamps `last` from the same field. The
            # rejected alternative is the frozen tree's per-call `self.tick += 1` (memory.py:565),
            # which makes "born at window 120, last retrieved at window 400" unsayable.
            store.last[uniq] = int(store.tick)
        # promote=False SKIPS ALL THREE WRITES AND NOTHING ELSE CHANGES -- L49/G7, an instrument
        # that edits what it measures. It still counts n_reads and the wrong_* trio, because those
        # describe the READ and not the store.
        # AND READ DRAWS NO RANDOMNESS ON EITHER ARM: it must never touch store.gen. The probe's
        # whole claim (deterministic stride, memory/levers.py::MEMLevers at probe_rows) is that a
        # diagnostic does not move the training trajectory, and a retrieval that consumed draws
        # would break that from the inside.

    # ==============================================================================================
    # THE BLEND WEIGHT, COMPUTED HERE AND NEVER AT THE CALLER
    # ==============================================================================================
    # VERBATIM THE FROZEN RAMP (self_organize.py:3277), INCLUDING THE max(1e-6, ...), which is not
    # padding: MEM_MATCH_FLOOR declares no domain=, so >= 1.0 is reachable from the environment and
    # the naive denominator INVERTS the ramp there. Measured over conf in {0.0, 0.5, 1.0}: at
    # match_floor=1.5 this spelling reads [0.0, 0.0, 0.0] -- correct, nothing passes -- while
    # `(conf - mf) / (1.0 - mf)` reads [1.0, 1.0, 1.0], the exact inversion, and at match_floor=1.0
    # this spelling reads [0.0, 0.0, 0.0] while the naive one returns nan at conf == 1.0. So
    # MEM_MATCH_FLOOR=1.0 is a second, undeclared retrieval-off switch beside the declared
    # MEM_BLEND_MAX=0.0, and it is the frozen spelling that makes it a clean one.
    # THE WEIGHT RIDES ON THE RECORD. Recomputing conf or this ramp at the blend site is ISSUES
    # P1-C8/C9 reproduced one layer up, which is the whole reason it is computed once, here.
    # MEASURED, AND IT IS WHAT THE GATE IS FOR. `dist` sums to 1.0 by construction -- 0.9999999 to
    # 1.0000001 over 16 rows on this tree -- which is the arithmetic behind the frozen ungated
    # weight being identically 1.0 and the blend being an unconditional 50/50 mix at every position,
    # the reason memory measured -0.097 b/B at 200k slots. AND THE RAMP IS NOT DECORATION: on the
    # same store, 16 queries re-encoded from entries the store actually holds came back at conf=1.0
    # and blend=0.5, exactly MEM_BLEND_MAX, while 16 RANDOM unit-norm queries against those same
    # 2,048 entries topped out at conf=0.3048 -- barely over MEM_MATCH_FLOOR=0.3 -- and the largest
    # blend weight they earned was 0.0034, 0.7% of the ceiling. A bad match being scaled to nothing
    # while a real one is paid in full is the mechanism working, not an inert one.
    g = ((conf - match_floor) / max(1e-6, 1.0 - match_floor)).clamp(0.0, 1.0)
    blend = (blend_max * g).clamp(min=0.0)
    return Retrieval(dist=dist, conf=conf, hits=hits, weights=weights, blend=blend)


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

    1. READ PROBE. probe_rows real retrievals against probe_contexts -- ONE QUERY PER POSITION,
       each the key_win tokens ending at it (the write path's _key_windows), so a (B, L) batch
       offers B*L candidate queries and probe_rows of them are issued -- taken by DETERMINISTIC
       STRIDE with a rotating offset, never a random draw: a probe that consumed RNG draws would make the probe cadence
       change the training trajectory, and a diagnostic that silently edits the run is exactly the
       class frozen_rng exists for. WITHOUT THIS, evict=="lru"/"usage" ARE WRITE-ORDER FIFO
       WHATEVER THEY SAY, and probation can never promote -- four archive files recorded
       EVICT=usage "does not protect faded knowledge by construction" as measured fact, and it was
       measured through a constant.
       THE PROBE *IS* read(), NOT A SECOND RETRIEVAL (Q-MEM-9, RESOLVED 2026-09-02 (a)). It is
       read(mem, store, queries=key_fn(stride(key_windows(probe_contexts, key_win)),
       depth=key_depth), promote=True), and THERE IS NO SECOND RETRIEVAL IMPLEMENTATION IN THIS
       PACKAGE. The
       parameter lists force it rather than merely suggesting it: read declares no key lever and
       takes no key_fn, so it cannot encode anything and its `queries` must already be key-space
       vectors -- while THIS function holds key_fn and all three key levers. Open-coding a second
       kNN here would put n_reads/n_promoted/n_wrong_* on one path while the store is moved by
       another, which is C8/C9 one layer down, and would give wrong_read and match_floor a second
       implementation free to drift. The narrowing to key_win and the encode at key_depth happen
       HERE, once; any other site that forms `queries` must use the same two levers or the store is
       queried in one key space and written in another -- the drift rekey_every exists to prevent.
       WITH probe_contexts None OR EMPTY the honest DID IT FIRE reading is n_probe_fired counting
       the CADENCE and n_probe_rows == 0: armed-but-0, not unreachable and not silence. The loop
       supplies the previous flush's batch, so that is the first flush of a run and of each epoch.
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
                 a probe that never fires, and the old report could not tell them apart; all three
                 ABSENT at MEM_PROBE_EVERY=0 or MEM_PROBE_ROWS=0, the disarmed arms; Gate
                 mem.probe fires on n_probe_rows > 0, not on the cadence),
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
    # THE PROBE IS ARMED ONLY WHEN IT CAN ISSUE A ROW: a cadence AND a row budget (2026-09-24).
    # MEM_PROBE_ROWS=0 is a legal count that issues no query at any cadence, and seeding on the
    # cadence alone made that arm read present-and-0 -- "armed, did not fire" -- beside a
    # mem.pressure reason blaming the loop's one-flush lag. It is the disarmed arm, like
    # MEM_PROBE_EVERY=0, and its Gate says which lever disarmed it.
    probe_armed = every_p > 0 and probe_rows > 0
    if probe_armed:
        # ALL THREE PROBE COUNTERS ARE SEEDED ON THE ARMED ARM, BEFORE THE CADENCE DECIDES (G4).
        # n_probe_fired used to appear only at the first fire and n_probe_rows / n_probe_hits only
        # when a probe found material, so an armed probe that had not yet issued a row read ABSENT --
        # the tree's word for UNREACHABLE -- beside a nonzero fire count. ABSENT now means one thing:
        # MEM_PROBE_EVERY=0 or MEM_PROBE_ROWS=0, or maintain was never called. _bump(..., 0) adds nothing to a value a
        # resume restored, which is why the seed is here and not in open_store's seed dict (that
        # dict's keys are skipped by the restore loop, so seeding one there would drop the parent's
        # tally).
        for _k in ("store.n_probe_fired", "store.n_probe_rows", "store.n_probe_hits"):
            _bump(store, _k, 0)
        last_p = c.get("store.probe_last_window")
        if last_p is None or (w - int(last_p)) >= every_p:
            c["store.probe_last_window"] = w
            # THE CADENCE IS COUNTED WHERE IT FIRES, not where it finds material. n_probe_fired
            # counting the cadence beside n_probe_rows == 0 is the honest armed-but-0 reading, and
            # it is a DIFFERENT fact from a probe that never fired -- which the old report could not
            # tell apart.
            _bump(store, "store.n_probe_fired")
            # ONE QUERY PER POSITION, NOT ONE PER ROW OF THE BATCH (2026-09-24, F39). The write
            # path keys EVERY POSITION through _key_windows -- the key_win tokens ending at it --
            # and the frozen tree's probe queried the same shape (`mem_ctx(x)` is
            # `_windows(x, KW).reshape(-1, KW)`, self_organize.py:3200-3201, strided at :7558).
            # This line took `probe_contexts[::stride]` over the BATCH dimension and keyed only
            # each row's last key_win tokens, so a probe issued batch_windows queries however
            # MEM_PROBE_ROWS was set: ONE query per probe at the shipped OPT_BATCH_WINDOWS=1, where
            # 64 are declared. Measured before the repair over 80 windows: n_probe_fired 4,
            # n_probe_rows 3, n_promoted 24 -- and MEM_PROBE_ROWS=1 gave identical counters, which
            # is a lever that did nothing. Every MEM arm, eviction and probation number taken
            # before this date was taken at ~1/64 of the configured read rate (Q-MEM-12).
            q = (None if probe_contexts is None
                 else _key_windows(probe_contexts, kwin).reshape(-1, kwin))
            n_q = 0 if q is None else int(q.shape[0])
            if n_q:
                # DETERMINISTIC STRIDE, NEVER A RANDOM DRAW, AND A ROTATING OFFSET. A probe that
                # consumed RNG draws would make the probe CADENCE change the training trajectory,
                # and a diagnostic that silently edits the run is the class spine/rng.py exists for.
                # The offset `w % stride` is the frozen tree's `step % stride` (:7558): a fixed
                # stride from 0 would query the same positions of every window for the whole run,
                # and it costs no draw.
                stride = max(1, n_q // probe_rows)
                rows = q[(w % stride)::stride][:probe_rows]
                # THE NARROWING TO key_win AND THE ENCODE AT key_depth HAPPEN HERE, ONCE, through
                # the same two helpers the write path uses. `read` declares no key lever and takes
                # no key_fn, so it cannot encode and its `queries` must already be key-space
                # vectors; this function holds key_fn and all three key levers. Any other site that
                # forms `queries` must use the same two levers or the store is queried in one key
                # space and written in another.
                queries = _encode_keys(key_fn, rows, kdepth)
                # THE PROBE *IS* read(), NOT A SECOND RETRIEVAL (Q-MEM-9, RESOLVED (a)). Open-coding
                # a kNN here would put n_reads/n_promoted/n_wrong_* on one path while the store is
                # moved by another, and would give wrong_read and match_floor a second
                # implementation free to drift. spine/loop.py::_flush supplies the PREVIOUS flush's
                # batch as probe_contexts (since 2026-09-21), so this branch retrieves and promotes
                # on every fire but those whose contexts are None -- the first flush of a run and
                # the first after each epoch roll, which spine/loop.py resets the lag at. Those
                # fires are the armed-but-0 reading: n_probe_fired counts them and n_probe_rows
                # does not.
                retrieval = read(mem, store, queries=queries, promote=True)
                _bump(store, "store.n_probe_rows", int(rows.shape[0]))
                # ONE RETRIEVAL THAT RETURNED AT LEAST ONE ENTRY, which is what this counter is
                # declared to be -- a probe that fires and retrieves nothing is a different finding
                # from a probe that never fires. IT READS Retrieval.hits AND DEPENDS ON ONE
                # CONVENTION OF IT: a slot the retrieval did not fill is marked -1, which
                # Retrieval's own docstring states and memory/api.py::read keeps. Whoever changes
                # that convention changes this line in the same edit.
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
        # THE REKEY'S COUNTERS ARE SEEDED ON THE ARMED ARM, BEFORE ANY BRANCH BELOW DECIDES (G4).
        # n_rekey_passes was bumped only when a pass COMPLETED, so a rekey that was armed and
        # mid-pass read ABSENT -- which run.py and spine/loop.py::_gate_report print as "never armed
        # on the arm this run took" -- beside 59 slices already re-encoded. Seeded here and not in
        # open_store's seed dict: that dict's keys are skipped by the counter restore, so a key
        # seeded there would silently drop the parent's pass count on a resume. The capped-depth
        # tally is seeded only on its own reachable arm (a transformer at key_depth > 0); seeding it
        # anywhere else would turn a correct UNREACHABLE into a false armed-but-0.
        for _k in ("store.n_rekey_passes", "store.n_rekey_slices", "store.n_rekey_entries"):
            _bump(store, _k, 0)
        if kdepth > 0 and str(store.lm_kind) == "transformer":
            _bump(store, "store.n_keys_at_capped_depth", 0)
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
    # counters, with the two Gates below, are their did-it-fire surface -- the Gates reach the report
    # through MEM.census's `gates`, rendered by spine/loop.py::_report at R. Declared at the END, for the reason _write_gates
    # records: a gate declared before the work reports the previous call.
    fired_p = int(c.get("store.n_probe_fired", 0))
    rows_p = int(c.get("store.n_probe_rows", 0))
    passes = int(c.get("store.n_rekey_passes", 0))
    # THE mem.probe REASON IS COMPUTED FROM THE COUNTERS IT SITS BESIDE, NOT WRITTEN AS PROSE. It
    # said "`probe_contexts` has no producer in spine/loop.py ... nothing to query with" on every
    # run for three days after spine/loop.py::_flush began passing the previous flush's batch, and
    # printed that beside "3 row(s) have actually been issued" -- a sentence that cannot be true of
    # the line it is on. The two readings it has to tell apart are both live: rows issued, and
    # fires that found no contexts (the first flush of a run and of each epoch).
    _promoted = c.get("store.n_promoted")
    _probe_why = (
        f"{rows_p} query row(s) issued over {fired_p} fire(s), so {rows_p / fired_p:.1f} per fire "
        f"against the {probe_rows} declared; store.n_promoted "
        f"{'ABSENT' if _promoted is None else int(_promoted)} is what those retrievals moved out "
        f"of probation. A fire that issues no row is one whose contexts were None -- "
        f"spine/loop.py::_flush lags the probe one flush, so the first flush of a run and the "
        f"first after each epoch roll have nothing to query with."
        if rows_p > 0 else
        f"{fired_p} fire(s) and NO query row issued yet: ARMED-BUT-0, not silence. Every fire so far "
        f"found probe_contexts None or empty -- spine/loop.py::_flush lags the probe one flush, so "
        f"the first flush of a run and the first after each epoch roll have nothing to query "
        f"with. Until a row is issued nothing is retrieved, so evict='lru' and evict='usage' rank "
        f"on write-time clocks and probation cannot promote."
        if fired_p > 0 else
        f"the cadence has not come due in {w} window(s).")
    # mem.probe FIRES ON A ROW ISSUED, NOT ON THE CADENCE (2026-09-24). It fired on n_probe_fired
    # > 0, so a run whose probe had fired and issued nothing rendered "fired 1 vs 0" while this
    # reason called the same state ARMED-BUT-0. The fire count stays in the arithmetic.
    _declare_gates(store, (
        Gate("mem.probe", rows_p > 0, f"n_probe_rows={rows_p} over n_probe_fired={fired_p}",
             "0 rows",
             reason=f"MEM_PROBE_EVERY={every_p} windows x MEM_PROBE_ROWS={probe_rows} query rows, "
                    f"one per POSITION of the previous flush's batch; " + _probe_why)
        if probe_armed else
        Gate("mem.probe", False, every_p if every_p <= 0 else probe_rows, 0, reachable=False,
             reason=(("MEM_PROBE_EVERY=0" if every_p <= 0 else
                      f"MEM_PROBE_ROWS=0 (at MEM_PROBE_EVERY={every_p}: the cadence comes due and "
                      f"issues no query row)")
                     + " disarms every retrieval-based rule in this package: `use` and "
                    "`last` never move off their write-time values, so MEM_EVICT's two retrieval "
                    "arms degenerate to write order and MEM_PROBATION_FRAC can never promote. The "
                    "lever's own declaration says the report must say so.")),
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
    FOUR MORE KEYS THE BODY WRITES, DECLARED HERE IN THE FORM fabric/api.py::grow_check uses for
    the extra ledger keys its own body writes: a key in the report that the contract does not admit
    to producing is the same defect as a declared key nothing writes, and the count is taken in
    both directions.
      store.n_entries_refiled_by_fold -- ENTRIES the relabel moved, against n_folds_applied, which
        counts PAIRS. They answer different questions and only the pair makes either readable: a
        fold whose absorbed domain held nothing and a fold that never happened are the same
        distinction domains/api.py::manage already draws on its own side of the plan when it sends
        an empty-cull id here knowing the delete cannot remove anything.
      store.n_orphan_sources -- source ids still holding entries that `live_sources` does not name,
        SET and not bumped, read AFTER the relabel and the delete. It is the residue of the
        paragraph above: store.live_src is a COUNT, so this body corrects the floor's DIVISOR and
        still cannot make one orphan ineligible -- memory/api.py::_unprotected is where that is
        argued, and a live-id set on the Store is what would close it. Because a plan relabels every
        merged id and deletes every culled one, the reading on a run that carried every pass here is
        0, and a nonzero one is evidence of a pass whose plan nothing applied -- the state this
        entry point exists to end, as a number rather than an inference off two other reports.
        Measured on one warmed configuration, both ways: 3 orphans out of 6 sources holding entries
        with no call site, 0 out of 3 with the plan carried on every pass.
      store.n_fold_targets_culled -- fold SURVIVORS that the same plan also deletes, which is the
        one overlap the two entry counts cannot show: the entries a fold refiles into a survivor
        that is then culled are counted once as moved and once as destroyed, as though they were
        two populations. domains/api.py::_resolve makes it unreachable by construction, so this is
        a claim being checked rather than a case being handled, and PRESENT-AND-0 is the reading
        the wiring exists to produce.
      store.n_floor_at_plan -- the per-source floor in force when the plan ARRIVED, SET and not
        bumped, and the whole reason src_share is on the LEVERS READ line. It is read before
        anything moves, because what DOM judged this plan against is what MEM.census handed it at
        the top of this same pass; beside part.n_mem_floor_entries it is that number from the other
        end, and reading it after store.live_src had moved would print a floor this plan was never
        tested against.
    """
    mem = mem.owned_by("MEM")
    share = float(mem.src_share)

    # ==============================================================================================
    # EVERY COUNTER IS SEEDED HERE, ABOVE THE FIRST BRANCH THIS BODY TAKES
    # ==============================================================================================
    # ABSENT means the 'dom.manage' cadence never fired and this entry point was never reached at
    # all; PRESENT-AND-0 means a pass ran and its plan decided nothing. Seeding
    # n_entries_refiled_by_fold inside `if folds:` would put the fold's whole did-it-fire surface
    # behind the branch it describes, which is the defect memory/api.py::_bump exists to stop and
    # the one sig/api.py::cadence_due carries the repair for. It is also why no n_apply_calls key is
    # minted: the seed already separates "never called" from "called with an empty plan", which is
    # the argument memory/api.py::census makes one entry point over.
    for _k in ("store.n_folds_applied", "store.n_deletes_applied",
               "store.n_entries_refiled_by_fold", "store.n_entries_deleted_by_cull",
               "store.n_fold_targets_culled"):
        _bump(store, _k, 0)
    # THE THREE SET-NOT-BUMPED KEYS ARE SEEDED HERE TOO, AND THE REASON IS THE BRANCH TWENTY LINES
    # DOWN. The negative-id refusal is a branch this body takes, it is taken before any of the three
    # is written, and it raises -- so a plan carrying one left n_live_sources and n_orphan_sources
    # ABSENT, which under this tree's own rule reads as "the cadence never fired and this entry
    # point was never reached". That is the one thing certainly false at the instant the refusal
    # fires, and the report that carries the StoreError is the report that would have said it.
    # SETDEFAULT AND NOT ASSIGNMENT, because these three are readings and not tallies: on a later
    # pass that refuses, the previous pass's measurement is the last true one and blanking it to 0
    # would replace a reading with a different reading rather than with an absence.
    for _k in ("store.n_live_sources", "store.n_orphan_sources", "store.n_floor_at_plan"):
        store.counters.setdefault(_k, 0)

    # THE FLOOR IS READ BEFORE ANYTHING MOVES, AND THE ORDER IS THE VALUE OF THE NUMBER. What DOM
    # judged this plan against is what MEM.census handed it at the top of this same pass, over the
    # divisor in force THEN; store.live_src is about to change below, so reading the floor after
    # that assignment would report one this plan was never tested against and would make
    # part.n_mem_floor_entries and store.n_floor_at_plan two answers to one question, printed side
    # by side and a pass apart. The lever decides nothing here -- the cull brake already ran inside
    # DOM.manage and its verdict is what `deletions` IS.
    floor_at_plan, _divisor = _floor_entries(store, share)
    store.counters["store.n_floor_at_plan"] = int(floor_at_plan)

    # ==============================================================================================
    # MEM'S RESERVED PROVENANCE IDS MAY NOT BE NAMED BY A DOMAIN PLAN
    # ==============================================================================================
    # src < 0 is "no provenance" and -2 is the reserved id for the synthetic entries the wrongness
    # harness injects (H30) -- the one region of the store no domain manager owns. A negative id
    # reaching the relabel below would file real entries under a sentinel every other reader
    # excludes by construction; a negative id reaching the delete would destroy the eval harness's
    # own rows on a domain decision, silently, because a source id is an integer and every integer
    # indexes something. Refused rather than skipped, for the reason memory/api.py::_require_rows
    # gives: a skip leaves the report saying the fold applied while the id is still live in the
    # store. Domain ids climb from 0 and domains/api.py::_resolve hands back a live one, so a
    # correct plan cannot reach this.
    _bad = sorted({int(x) for x in
                   list(folds) + list(folds.values()) + list(deletions) if int(x) < 0})
    if _bad:
        raise StoreError(
            f"MEM.apply_domain_plan: the plan names source id(s) {_bad}, and a negative source id "
            f"is not a domain -- it is this store's no-provenance marker, of which -2 is the "
            f"reserved id for eval-injected entries. Refused rather than skipped: skipping would "
            f"count the fold or the delete as applied while the id stayed live in the store.")
    # AND THE SAME REFUSAL FOR `live_sources`, WHERE THE DAMAGE IS ARITHMETIC RATHER THAN
    # DESTRUCTIVE AND SO HAS NOTHING TO ANNOUNCE IT. A negative id here relabels nothing and deletes
    # nothing; it is counted into the SET below, so it inflates store.live_src by one and SHRINKS
    # every live domain's reservation -- the 125-sources-against-27-domains defect this docstring
    # measures, in miniature and from the other direction, with no entry moved to notice it by. It
    # also lands in `live`, where it can only subtract an id `held` cannot contain, so the orphan
    # residue keeps reading clean while the divisor it is meant to corroborate is wrong.
    _bad_live = sorted({int(x) for x in live_sources if int(x) < 0})
    if _bad_live:
        raise StoreError(
            f"MEM.apply_domain_plan: live_sources names source id(s) {_bad_live}, and a negative "
            f"source id is not a domain -- it is this store's no-provenance marker, of which -2 is "
            f"the reserved id for the entries the wrongness harness injects. Refused rather than "
            f"filtered: a filtered id is still one the producer counted, and the number this "
            f"argument sets is the divisor EVERY per-source floor in the run is taken over.")

    # ==============================================================================================
    # 1 -- THE FOLDS: RELABEL FIRST, THEN RECOUNT THE IDS INVOLVED EXACTLY
    # ==============================================================================================
    # THE PAIRS ARE ALREADY RESOLVED AND THIS BODY DOES NOT RE-RESOLVE THEM. domains/api.py::_resolve
    # walks the merge chain so a domain folded into a survivor that is itself merged away later in
    # the same pass arrives here naming the FINAL survivor, which is also why no key of `folds` can
    # be one of its values and why the relabel is order-independent. Re-walking it here would need
    # part.merged, which is DOM's and which O10 forbids this package to reach.
    touched = set()
    for _b, _a in folds.items():
        b, a = int(_b), int(_a)
        if a >= int(store.nsrc.numel()):
            # THE CENSUS IS GROWN AND NEVER CLAMPED -- the frozen sentence above, and the same one
            # memory/api.py::_commit_window and memory/api.py::census both carry. A survivor minted
            # since the last write has no bucket yet, and clamping it into the last one would credit
            # every entry this fold refiles to whatever id happens to sit at the end of the table --
            # which is then the count the per-source floor protects.
            grown = torch.zeros(a + 1, dtype=store.nsrc.dtype, device=store.nsrc.device)
            grown[:store.nsrc.numel()] = store.nsrc
            store.nsrc = grown
        # ACTIVE ROWS ONLY. A freed slot keeps the `src` of whatever it last held until a write
        # overwrites it, so relabelling inactive rows would move provenance nobody owns and would
        # make store.src disagree with the one reading every consumer takes -- `src & active`, which
        # is what MEM.census(reconcile=True) recounts against and what _commit_window decrements on.
        m = (store.src == b) & store.active
        n = int(m.sum())
        store.src[m] = a
        _bump(store, "store.n_entries_refiled_by_fold", n)
        touched.add(b)
        touched.add(a)
    # PER PAIR, NOT PER ENTRY. n_folds_applied answers "how many merges did the store follow" and
    # the counter above answers "how much memory moved"; a plan of eleven merges over domains that
    # held nothing is a true and different fact from no plan at all.
    _bump(store, "store.n_folds_applied", len(folds))
    # THE AFFECTED BUCKETS ARE RECOUNTED EXACTLY, AFTER EVERY PAIR HAS MOVED, AND NOT DELTA-ADJUSTED.
    # The frozen store gives the reason at memory.py:633-641 and it is the one that survives being
    # handed a whole plan instead of one pair: an incremental delta drifts the moment the same id
    # appears twice, and the recount is exact for any number of pairs in any order. It is also the
    # cheap half of MEM.census(reconcile=True) -- capacity-wide, but over the ids this call touched
    # rather than over the whole table -- so the incremental census cannot be left disagreeing with
    # `src & active` by exactly the entries this body just moved.
    for s in sorted(touched):
        if s < int(store.nsrc.numel()):
            store.nsrc[s] = int(((store.src == s) & store.active).sum())
            # RAISED AND NEVER LOWERED, the rule MEM.census states for the same field: a fold
            # concentrates two domains into one bucket, and that peak is real. Re-deriving the peak
            # later from current counts is what M53/M67 records as forgetting every source evicted
            # before now, and the starvation alarm then compares against a peak that never happened.
            store.nsrc_max = max(int(store.nsrc_max), int(store.nsrc[s]))

    # ==============================================================================================
    # 2 -- THE DELETES: THE GOAL-B NUMBER
    # ==============================================================================================
    # HOW MUCH OF THE STORE THE DOMAIN MANAGER DESTROYED. In the old tree this was 200,000 entries
    # with no counter at all, which is why the frozen DID IT FIRE line names it that way: deleting a
    # domain's provenance deletes its knowledge, and goal B is the claim that this run does not
    # forget. It is counted in ENTRIES here and in IDS one line below, because the cull brake
    # DOM.manage applies is per domain and the loss is per entry.
    for _d in deletions:
        d = int(_d)
        m = (store.src == d) & store.active
        n = int(m.sum())
        # DEACTIVATION IS THE DELETE AND NOTHING ELSE ON THE ROW IS CLEARED. `prob` on a freed slot
        # is stale by construction (L61) and every reader already masks it with `active`; `src` is
        # left standing so the row still says where it came from until a write claims the slot,
        # which is what makes a store dump after a cull readable at all.
        store.active[m] = False
        _bump(store, "store.n_entries_deleted_by_cull", n)
        if 0 <= d < int(store.nsrc.numel()):
            # SET TO 0, NOT DECREMENTED. Every active entry of this source has just gone, so 0 is
            # exact -- while an index_add of -n re-opens the underflow that
            # memory/api.py::_commit_window counts and clamps, on the one path holding the answer.
            store.nsrc[d] = 0
    # BY len(deletions), INCLUDING EVERY ID THAT REMOVED NOTHING. Of the empty-cull ids it sends here
    # knowing the delete cannot reach anything, domains/api.py::manage says
    # "a delete that removed nothing and a delete that never happened are two facts"
    # -- and only one of the two is evidence that the memory-floor brake held, which a count of
    # ENTRIES cannot supply on its own. This counter is the one that comment is written against, and
    # it is why the loop above runs every id through the mask instead of skipping an empty one.
    _bump(store, "store.n_deletes_applied", len(deletions))
    # THE ONE OVERLAP THE TWO COUNTERS ABOVE CANNOT SHOW, counted on its own key. If a fold names
    # survivor `a` and the same pass culls `a`, the relabel files b's entries into a and the delete
    # destroys them four lines later: n_entries_refiled_by_fold counts them as moved, then
    # n_entries_deleted_by_cull counts THE SAME ENTRIES as lost, and the pair reads as two
    # independent facts about two populations. domains/api.py::_resolve is what should make this
    # unreachable -- it walks the merge chain so every pair arrives naming the FINAL survivor, and a
    # final survivor is by construction one the pass kept -- so this is not a condition to handle,
    # it is a claim to check, and a nonzero reading here is evidence that the resolution upstream
    # did not hold. Zero is the expected value and PRESENT-AND-0 is the point.
    _bump(store, "store.n_fold_targets_culled",
          len({int(a) for a in folds.values()} & {int(d) for d in deletions}))

    # ==============================================================================================
    # 3 -- ELIGIBILITY: THE DIVISOR THE FLOOR IS TAKEN OVER, AND THE RESIDUE IT CANNOT REACH
    # ==============================================================================================
    # AS A SET, SO A REPEATED ID CANNOT INFLATE THE DIVISOR. The floor is src_share * capacity /
    # live, so one id counted twice shrinks every live domain's reservation -- the same arithmetic,
    # in the same direction, as the 125-against-27 defect the paragraph above measures, just smaller.
    live = {int(s) for s in live_sources}
    # AN EMPTY `live` SETS 0 AND THAT IS A READING, NOT A HOLE. At 0 memory/api.py::_floor_entries
    # falls back to counting the sources that hold entries, which is the frozen store's documented
    # live_src=None arm (memory.py:386-388) -- no domain information supplied, everything with
    # entries eligible -- and it is exactly what a partition holding nothing can honestly say.
    store.live_src = len(live)
    # SET, NOT BUMPED. It is a state reading of this pass and not an event count; bumping it would
    # make the report print the sum of every pass's live population, a number nothing means.
    store.counters["store.n_live_sources"] = len(live)
    # THE RESIDUE, MEASURED RATHER THAN ASSUMED. store.live_src is a COUNT, so the two lines above
    # fix the floor's divisor and cannot make one dead-but-occupied source ineligible; this is the
    # number that says whether any such source exists. Every merged id was relabelled above and
    # every culled id emptied, so on a run that carried every pass here this reads 0 -- a nonzero
    # reading is not a tuning question, it is a pass whose plan nothing applied. Measured on one
    # warmed configuration, both ways: 3 with no call site, 0 with one.
    held = {int(i) for i in torch.nonzero(store.nsrc > 0).flatten().tolist()}
    # `if live else 0`, AND THE GUARD IS THE ARM TWO LINES ABOVE READ CONSISTENTLY RATHER THAN A
    # DEFENSIVE HABIT. An empty `live` sets store.live_src = 0, which memory/api.py::_floor_entries
    # reads as the frozen tree's live_src=None arm: no domain information supplied, everything
    # holding entries eligible. On that arm NOTHING is orphaned, because nothing is excluded.
    # Subtracting the empty set instead reports EVERY source holding entries as an orphan -- the
    # largest reading this counter can take, on the one counter whose nonzero value this file
    # declares to be evidence of a plan nobody applied -- so the fallback arm would raise the alarm
    # that says the fallback arm is running, every pass, and the number meant to end an inference
    # would need one.
    store.counters["store.n_orphan_sources"] = len(held - live) if live else 0


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


# ==================================================================================================
# EVERYTHING THE REPORT AND THE DOMAIN MANAGER NEED TO KNOW ABOUT THE STORE
# ==================================================================================================


@dataclasses.dataclass(frozen=True)
class StoreCensus:
    """The store's occupancy, its provenance table, its verdict and its did-it-fire surface.

    FROZEN, on memory/api.py::WriteReceipt's argument, and with one consequence this record has that
    that one does not: `counters` and `gates` are containers, so freezing the dataclass freezes the
    BINDING and not the contents. That is what the deep-enough copy in the body is for.

    `counts` IS A DICT KEYED BY SOURCE ID AND A TUPLE WAS REJECTED FOR A NAMED REASON. DOM.manage
    indexes it as `memory_counts[did]`, and a Python tuple answers a NEGATIVE did by returning the
    LAST bucket, so the -1 and -2 no-provenance ids would read as some real domain's count. A dict
    raises. THE ZEROS ARE IN THE MAPPING AND THAT IS THE POINT: a source with no entries is exactly
    the case DOM's cull brake must see -- domains/api.py::manage says "It self-releases --
    once eviction has genuinely drained the domain it falls below the floor" -- and a mapping that
    omitted zeros would force the consumer to choose between a KeyError and a silent 0 default,
    which is the absent-versus-zero collapse refused everywhere else in this tree.

    `pressure` IS MEM'S VERDICT -- True, False or None -- AND NOT MEM'S READING, and three frozen
    texts force that encoding rather than one. fabric/api.py::grow_check says "IT ARRIVES AS MEM'S
    VERDICT, NOT AS MEM'S READING"; memory/api.py::census's own docstring puts the comparison
    against the threshold inside this call; and memory/levers.py::MEMLevers argues at pressure_thresh
    that handing over the raw share would make fab.grow_mem_eligible fire on every flush. FAB's body
    confirms the encoding it expects on both halves -- an eligibility that is the truth of the value
    and a reachability that is the value not being None.
    NOTHING IS LOST BY LEAVING THE SHARE OFF THIS RECORD: n_evict_main and n_evict_probation both
    cross on `counters`, so the ratio is derivable, and the mem.pressure Gate prints it pre-computed
    beside its own denominator.

    `census_drift` IS None ON THE reconcile=False ARM AND NOT 0. A 0 there would claim "measured and
    exact" about a measurement that was not taken -- the record-level form of the same
    absent-versus-zero rule the counters obey one layer down.

    `live_src` IS THE DIVISOR THAT WAS ACTUALLY USED, i.e. memory/api.py::_floor_entries' own
    `live`, and not the raw store.live_src field. The two differ before MEM.apply_domain_plan has
    run -- Store.__init__ sets the field to 0 -- and reporting a raw 0 beside a floor computed over
    27 sources is the printed-configuration-disagrees-with-the-running-one defect
    memory/api.py::open_store refuses MEM_OWNERS below 1 over.

    `nsrc` IS THE NUMBER OF SOURCE IDS HOLDING ENTRIES, NOT THE TABLE WIDTH, and that reading is
    what makes the orphan gap readable beside live_src: 125 sources holding entries against 27 live
    domains is the 4.6x swing three docstrings in this tree cite, and memory/api.py::_unprotected
    says "a dead source that still holds entries is still protected by it".
    The table width is already on the record twice over -- as counters['store.census_slots'] and as
    len(counts).
    """
    counts: dict
    floor_entries: int
    quota_arm: str
    pressure: object
    probation_share: float
    live_src: int
    nsrc: int
    nsrc_max: int
    census_drift: object
    n_census_reconciles: int
    counters: dict
    gates: tuple


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
    RETUNING. The chain the ruling rested on is: only a retrieval promotes out of probation
    (levers.py, probation_frac); the only in-loop retrieval is MEM.maintain's job 1; so with no
    retrieval n_promoted is 0, every eviction takes the probation branch, n_evict_main is 0 and the
    reading is pinned. WHEN THE RULING WAS WRITTEN THAT WAS EVERY CONFIGURATION, because
    `probe_contexts` had no producer. IT HAS ONE NOW (spine/loop.py::_flush passes the previous
    flush's batch, 2026-09-21) and the probe issues MEM_PROBE_ROWS per-position queries per fire
    (2026-09-24, Q-MEM-12), so promotion, main-branch eviction and a reachable verdict are all live
    at the defaults -- measured n_promoted 24, n_evict_main 128 over 80 windows even at the
    one-query-per-probe rate that preceded Q-MEM-12.
    THE GATE REPORTS A STATE WHEN THERE IS NO VERDICT, NOT A NUMBER, and it names WHICH state,
    because there are five and they are different facts -- four with nothing promoted, one with no
    denominator: MEM_PROBE_EVERY=0 or MEM_PROBE_ROWS=0 (no promotion path on this configuration --
    read off maintain's own mem.probe Gate, since this entry point reads no probe lever), maintain
    never called (no retrieval yet: the probe was never armed on this store), the probe has issued
    no query row yet (its contexts lag one flush), rows issued and nothing promoted yet, and
    promotions on the board with no eviction yet (no denominator).
    Each prints its counters, never `0.000` -- which is H33's own point read one level up, that a
    signal which cannot reach its threshold is indistinguishable from a healthy one. It prints
    probation_share/probation_frac and n_probe_fired/n_promoted beside pressure/pressure_thresh,
    AND it names the second, independent cause of a silent verdict: the arm is not selected
    (src_share=0.5 > 0 makes quota_arm "reservoir", and FAB.grow_on_mem_pressure ships False, so
    the pressure_signal arm is off at both ends).
    probation_frac IS A PER-BLOCK PREDICATE (write's own "INSIDE that set"); `probation_share`
    reported here is a store-wide aggregate and is not the thing the eviction branch tests. At the
    shipped defaults those differ by the 64 blocks.
    EXPECT THE RETUNE TO GO UP, NOT DOWN. With the probe fed the rates invert: probe_rows/
    probe_every = 64/25 = 2.56 query rows per window at topk=8 is up to ~20 entry-touches per
    window against ~1 gated write per window, so probation can fall UNDER its budget and pressure
    can pin at 1.0 above 0.80 permanently. Both pinned-at-0 and pinned-at-1 are live outcomes and
    only a run with the probe fed at its declared rate -- which no run before 2026-09-24 had, see
    Q-MEM-12 -- can say which.
    THE READING IS NOT A WIRE AND MUST NOT BECOME ONE. pressure_thresh's only reader is this
    function; FAB.grow_check takes `memory_pressure` and reads no threshold, so the comparison
    against 0.80 happens HERE and what the root passes to FAB must already be MEM's VERDICT. A store
    occupancy measured at runtime can never be a wire -- a Coupling.compute sees only frozen Configs.

    LEVERS READ: src_share, probation_frac, pressure_thresh, quota, evict
    WIRES READ: none
    DID IT FIRE: this call IS the DID IT FIRE surface for the package; it also maintains
                 n_census_reconciles and census_drift, and a nonzero census_drift is itself a
                 defect signal rather than a repair. The `mem.pressure` Gate reads
                 store.n_promoted, n_probe_fired, n_probe_rows, n_evict_main and
                 n_evict_probation plus maintain's mem.probe Gate, and names every no-verdict
                 state and the unselected-arm cause named above
    """
    mem = mem.owned_by("MEM")
    share, prob_frac = float(mem.src_share), float(mem.probation_frac)
    thresh, quota, evict = float(mem.pressure_thresh), int(mem.quota), str(mem.evict)
    # NO WIRE IS READ HERE -- the frozen WIRES READ line says none, so the capacity comes off the
    # STORE and the block count off store.owners, not off mem.d_capacity / mem.d_owner_blocks.
    # Touching a d_ field here would also be a new O4 edge for a value this package already holds.
    c = store.counters

    # ==============================================================================================
    # BOTH COUNTERS ARE SEEDED BEFORE THE reconcile BRANCH DECIDES
    # ==============================================================================================
    # Seeding them inside `if reconcile:` is precisely the recorded defect fabric/api.py::_bump
    # exists to stop, and sig/api.py::cadence_due carries the repaired form of it. With the seed at
    # the top, ABSENT means census was never called AT ALL -- spine/loop.py calls it on the
    # dom.manage cadence at A and once more at R with reconcile=True, so on a driven run that is a
    # run shorter than both -- and PRESENT-AND-0 means census ran and never reconciled. That is also why this entry point
    # needs no n_census_calls counter: the seed already carries the distinction, and minting one
    # would be a counter the frozen DID IT FIRE line does not declare.
    _bump(store, "store.n_census_reconciles", 0)
    _bump(store, "store.census_drift", 0)
    # AND CENSUS SEEDS NO OTHER ENTRY POINT'S COUNTER AND NO OTHER PACKAGE'S. n_promoted,
    # n_probe_fired, n_probe_rows, n_evict_main and n_evict_probation are read below with
    # `.get(k, 0)` and their ABSENCE is part of what the mem.pressure Gate reports; seeding them here
    # would rewrite "MEM.read was never called" into "MEM.read ran and promoted nothing", which is a
    # claim about another entry point's work made by the function that reports on it.

    # ==============================================================================================
    # THE EXACT RECOUNT, ONLY UNDER reconcile=True, AND IT IS THE REPAIR
    # ==============================================================================================
    drift = None
    if reconcile:
        _bump(store, "store.n_census_reconciles")
        # src < 0 IS "NO PROVENANCE" AND IS CREDITED TO NOBODY, ON BOTH PATHS. -2 is the reserved id
        # for synthetic eval-injected entries (H30), and memory/api.py::_commit_window already
        # refuses to credit a negative source; a recount that bincounted them would invent a bucket
        # the incremental table never had and then report the difference as drift.
        m = store.active & (store.src >= 0)
        if int(m.sum()):
            # THE TABLE IS GROWN, NEVER CLAMPED -- the same sentence memory/api.py::open_store and
            # memory/api.py::_commit_window both carry, and the pattern that re-broke this at the
            # scale it was written for: the table stood 64 rows wide on every default run against a
            # real one carrying 125 source ids.
            top = int(store.src[m].max()) + 1
            if top > int(store.nsrc.numel()):
                grown = torch.zeros(top, dtype=store.nsrc.dtype, device=store.nsrc.device)
                grown[:store.nsrc.numel()] = store.nsrc
                store.nsrc = grown
        exact = torch.bincount(store.src[m],
                               minlength=int(store.nsrc.numel())).to(store.nsrc.dtype)
        drift = int((exact - store.nsrc).abs().sum())
        if drift:
            # A NONZERO DRIFT IS A DEFECT SIGNAL AND NOT A REPAIR REPORT, which is the frozen DID IT
            # FIRE line's own reading of this counter. It is counted BEFORE the table is replaced,
            # because after the assignment the evidence is gone.
            _bump(store, "store.census_drift", drift)
        # IT REPLACES THE TABLE, and the authority is verbatim in this file:
        # memory/api.py::_commit_window says of its underflow clamp that "the bite is COUNTED and
        # MEM.census(reconcile=True) is what repairs it".
        store.nsrc = exact
        # nsrc_max IS RAISED AND NEVER LOWERED, even when the recount is smaller. Re-deriving it
        # from current counts forgets every source evicted before now (M53/M67) and leaves the
        # starvation alarm comparing against a peak that never happened.
        store.nsrc_max = max(int(store.nsrc_max), int(exact.max()) if exact.numel() else 0)

    # ==============================================================================================
    # THE FLOOR, THROUGH THE ONE SHARED EXPRESSION
    # ==============================================================================================
    # memory/api.py::_floor_entries is the number the eviction filter ENFORCES, so this is the
    # number the report PRINTS and the number DOM's cull brake is judged against, and the three
    # cannot be three answers. `live` is the divisor that was ACTUALLY used and is what goes on the
    # record -- see StoreCensus. WHAT THIS REPORTS IS THE FLOOR IN FORCE AND NOT A HYPOTHETICAL ONE,
    # AND WHAT IT IS IN FORCE OVER MOVED THE DAY DOM.observe GOT A BODY. This block used to say that
    # every window is domain 0, that exactly one source holds entries, that `live <= 1` and that the
    # floor in force is therefore 0 -- four clauses, each true of a stubbed partition and none of
    # them true now. Measured on the shipped defaults after 60 windows: six sources hold entries
    # (2432/896/512/384/384/384), the divisor is 6 and the floor in force is 682. So a run that
    # prints n_floor_blocked 0 is no longer explained by a floor of nothing, and has to be read as
    # the floor being armed and not biting.
    # THE ZERO ARM IS STILL REACHABLE AND IS STILL THE HAZARD, which is why the paragraph stays.
    # memory/api.py::_floor_entries returns 0 on three arms, DOM.manage's declared brake is
    # `memory_counts[did] >= mem_floor_entries`, and at 0 that is satisfied by every domain
    # including empty ones -- the brake becoming a wall. The frozen tree carries the `if _fl > 0`
    # guard that prevents it (self_organize.py:3688) and domains/api.py::manage now carries it too,
    # at the one site that reads this number; a population collapsed to one live domain reaches the
    # arm on the shipped defaults (live == 1, floor == 0, measured). Naming the hazard was this
    # function's job and fixing it was DOM.manage's, and both halves have now been done.
    floor, live = _floor_entries(store, share)

    # ==============================================================================================
    # THE PER-SOURCE TABLE, AND THE TWO PROBATION READINGS
    # ==============================================================================================
    counts = {i: int(n) for i, n in enumerate(store.nsrc.tolist())}
    # `prob` ON A FREED SLOT IS STALE (L61) -- memory/api.py::_commit_window sets it True on every
    # write and nothing clears it on deactivation -- so both readings mask it with `active`.
    prob_live = store.prob & store.active
    # THE TWO READINGS ARE DIFFERENT NUMBERS AND BOTH ARE PRINTED. probation_frac is a PER-BLOCK
    # predicate -- memory/api.py::write says so twice and Q-MEM-4 closed it as the adjacent hole --
    # so the STORE-WIDE share on this record is NOT what the eviction branch tests, and write's own
    # docstring asks for the per-block distribution beside it. Measured on this tree after 60
    # windows: per-block min/median/max 0/128/128 against a budget of prob_frac*quota = 12.8, beside
    # a store-wide share of 0.5625 against prob_frac = 0.10. Two denominators a factor of the block
    # count apart, and only the first one decides anything.
    probation_share = int(prob_live.sum()) / int(store.capacity)
    # THE GEOMETRY IS THE STORE'S AND THE BUDGET IS THE LEVER'S, and they cannot disagree:
    # memory/api.py::open_store refuses `capacity != owners * quota` before a Store exists.
    per_block = prob_live.view(int(store.owners), int(store.quota)).sum(1)
    p_min, p_med, p_max = int(per_block.min()), int(per_block.median()), int(per_block.max())

    # ==============================================================================================
    # THE PRESSURE VERDICT -- THE ONE INTERPRETATION THAT DECIDES THE SHAPE OF THE RECORD
    # ==============================================================================================
    ev_p, ev_m = int(c.get("store.n_evict_probation", 0)), int(c.get("store.n_evict_main", 0))
    tot = ev_p + ev_m
    n_probe = int(c.get("store.n_probe_fired", 0))
    promoted_key = "store.n_promoted" in c
    promoted = int(c.get("store.n_promoted", 0))
    reading = (ev_m / tot) if tot else None
    # None ON TWO ARMS, NOT False, AND THE TWO ARMS ARE DIFFERENT FACTS.
    #   (a) tot == 0: no eviction has happened, the ratio has no denominator, and a False here would
    #       claim a measurement that was never taken.
    #   (b) promoted == 0: nothing has ever left probation, so no eviction CAN destroy a promoted
    #       entry -- n_evict_main is 0 and the reading is pinned at 0.0 until something promotes,
    #       which is Q-MEM-4's chain. Handing FAB a False there would make its own gate print
    #       "armed, did not fire", which is the language of a measurement, about a signal that
    #       cannot yet move. None makes it print UNREACHABLE, which is what this package's Gate
    #       says one package over, and the two reports then agree. Arm (b) is REACHABLE on every
    #       configuration -- any census before the probe's first promotion lands in it -- and it
    #       is STRUCTURAL only at MEM_PROBE_EVERY=0; the Gate below says which of the two it is.
    # Measured at the defaults over 80 windows (re-driven 2026-09-24 on the tree after Q-MEM-12 fed
    # the probe its declared rows and the later fabric / TOK-DOM-CAP repairs): ev_p=4608, ev_m=512,
    # n_promoted 621, so neither arm holds at R and the verdict is a number. (Before Q-MEM-12 the
    # same run read 4864 / 128 / 24; on Q-MEM-12's own commit 4736 / 256 / 508.)
    pressure = None if (reading is None or promoted == 0) else bool(reading > thresh)

    # ==============================================================================================
    # THE mem.pressure GATE, DECLARED AT THE END
    # ==============================================================================================
    # AT THE END, for the reason memory/api.py::_write_gates records: a gate declared before the
    # work reports the PREVIOUS call. EXACTLY ONE GATE, AND ITS NAME MATTERS -- _declare_gates
    # replaces by NAME, so spelling this one "mem.probation" would silently clobber the
    # scan-resistance Gate memory/api.py::write declares.
    # THERE IS NO NOISE FLOOR HERE AND THE OMISSION IS DELIBERATE. The frozen tree suppressed the
    # reading below 1,000 evictions (memory.py:415); that number is declared nowhere in this tree
    # and was chosen at a capacity of 200,000 against today's 8,192, so porting it would be
    # re-tuning an instrument by importing a constant. The DENOMINATOR IS PRINTED in `value`
    # instead, which is this tree's answer to a verdict without its arithmetic. Whether a declared
    # minimum is owed is the owner's, beside Q-MEM-4's standing "measure before retuning".
    _ratio = "no evictions yet" if tot == 0 else f"{ev_m}/{tot} = {reading:.3f}"
    # ABSENT AND 0 ARE PRINTED AS DIFFERENT WORDS, AND RENDERING `.get(k, 0)` HERE WOULD COLLAPSE
    # THEM. n_promoted ABSENT says memory/api.py::read was never called at all on the arm this run
    # took -- a fact about the spine -- while n_promoted 0 says read ran and nothing left probation,
    # a fact about the store. Those are different findings about different packages' work, and the
    # unconditional seeding in memory/api.py::read exists precisely so this line can tell them
    # apart. n_probe_fired carries the same pair against memory/api.py::maintain's cadence.
    _prom = str(promoted) if promoted_key else "ABSENT"
    _probe = str(n_probe) if "store.n_probe_fired" in c else "ABSENT"
    _prom_note = (" (ABSENT is the stronger of the two readings: MEM.read was never called at all, "
                  "so that is a statement about the spine and not about this store)" if not promoted_key
                  else " (present and 0, so read HAS run and nothing left probation)")
    _arm = "reservoir" if share > 0.0 else "pressure_signal"
    # THE PAIR Gate.line PRINTS IS `(value vs threshold)`, SO THE RATIO GOES LAST: the threshold is
    # pressure_thresh and it applies to the ratio alone, and a value string ending in some other
    # number renders "n_promoted 35 vs 0.8" -- one sentence pairing a count with a fraction. Found
    # by reading the rendered line on a driven store, which is the only place it is visible.
    _value = (f"probation_share {probation_share:.3f} against probation_frac {prob_frac} "
              f"STORE-WIDE, while the PER-BLOCK distribution the eviction branch actually tests is "
              f"min/median/max {p_min}/{p_med}/{p_max} against {prob_frac * quota:.1f}; "
              f"n_probe_fired {_probe}; n_promoted {_prom}; pressure {_ratio}")
    # THE UNREACHABLE ARM BRANCHES AGAIN, BECAUSE THERE ARE TWO WAYS TO HAVE NO VERDICT: nothing
    # promoted yet (itself split four ways by `_no_promo` below) and no eviction yet. The first is
    # tested FIRST, on n_promoted, exactly as the docstring orders them. The other is tot == 0 with promotions on the board --
    # measured on a driven store: 727 entries written, 35 promoted by one read, and NOT ONE
    # EVICTION. The first draft of this reason had only the promotion clause and printed "NO
    # PROMOTION PATH ... n_promoted 35" on that store: a reason describing the state the run is not
    # in, which is the defect this whole file argues against, and it was invisible until the line
    # was rendered on a real store.
    # WHICH NO-PROMOTION STATE, READ OFF THE COUNTERS AND OFF maintain's OWN mem.probe GATE. This
    # branch printed "NO PROMOTION PATH ... `probe_contexts` has no producer -- spine/loop.py::_flush
    # passes None ... for every configuration" for three days after the loop began passing the
    # previous flush's batch; it is still REACHED on a fed run -- any census before the first
    # promotion lands here -- so the cause has to be named from the state and not from a sentence
    # written about another tree. census reads no probe lever (its LEVERS READ line), so whether
    # the probe is disarmed is taken from the Gate maintain declared with that lever in hand.
    _pg = next((g for g in store.gates if g.name == "mem.probe"), None)
    _rows_n = int(c.get("store.n_probe_rows", 0))
    _rows = str(_rows_n) if "store.n_probe_rows" in c else "ABSENT"
    _no_promo = (
        "NO PROMOTION PATH ON THIS CONFIGURATION. Only a retrieval promotes out of probation, the "
        "only in-loop retrieval is memory/api.py::maintain's probe, and its mem.probe Gate is "
        "UNREACHABLE (" + _pg.reason.split(":")[0] + "), so evict='lru' and evict='usage' rank on "
        "clocks no retrieval advances and nothing ever leaves probation."
        if (_pg is not None and not _pg.reachable) else
        "NO RETRIEVAL YET. maintain has not been called, so the probe has not been armed on this "
        "store."
        if _pg is None else
        "NO QUERY ROW ISSUED YET. The probe is armed and has fired, but every fire so far found no "
        "contexts: spine/loop.py::_flush lags it one flush, so the first flush of a run and the "
        "first after each epoch roll have nothing to query with."
        if _rows_n == 0 else
        "NOTHING PROMOTED YET. The probe has issued query rows and memory/api.py::read ran, but no "
        "retrieved entry was on probation -- the path is open and has not moved anything.")
    _declare_gates(store, (
        Gate("mem.pressure", bool(pressure), _value, thresh, reachable=pressure is not None,
             reason=(f"MEM_PRESSURE_THRESH={thresh} is MEM's own bar and THIS COMPARISON IS ITS "
                     f"ONLY READER: what the composition root hands fabric/api.py::grow_check is "
                     f"this verdict and not this ratio. MEM_EVICT={evict!r} ranks the victims the "
                     f"two branches are counted over, and MEM_SRC_SHARE={share} puts quota_arm at "
                     f"{_arm!r}. The denominator is PRINTED beside the ratio rather than suppressed "
                     f"below a minimum: the frozen tree returned None under 1,000 evictions "
                     f"(memory.py:415), that floor was chosen at a capacity of 200,000 against this "
                     f"store's {int(store.capacity)}, and porting it would be re-tuning an "
                     f"instrument by importing a constant -- so at {ev_m}/{tot} a reader can see "
                     f"for themselves how many samples this verdict rests on."
                     if pressure is not None else
                     (_no_promo + f" n_probe_fired {_probe}, n_probe_rows {_rows}, "
                      f"n_promoted {_prom}{_prom_note}; until an entry is promoted no eviction "
                      f"can destroy one, so n_evict_main stays 0 and the reading is pinned -- "
                      f"{_ratio}. THE SECOND CAUSE IS SEPARATE AND ALSO HOLDS: MEM_SRC_SHARE={share} "
                      f"puts quota_arm at {_arm!r} and FAB ships its grow-on-memory-pressure flag "
                      f"False, so the pressure-signal half of D3 is off at BOTH ends. Reported as "
                      f"a state and never as 0.000 -- a signal held at zero and one measured at "
                      f"zero print the same number, which is H33's own point read one level up."
                      if promoted == 0 else
                      f"NO DENOMINATOR YET, AND THAT IS NOT A ZERO. n_promoted {_prom}, so the "
                      f"promotion path is OPEN on this run -- but not one eviction has happened, "
                      f"so main/(main+prob) has nothing to divide and a False here would claim a "
                      f"measurement nobody took. This is the arm the frozen tree spent a noise "
                      f"floor on (memory.py:415) and this tree prints the denominator for "
                      f"instead. THE SECOND CAUSE IS SEPARATE AND HOLDS WHATEVER THIS ONE DOES: "
                      f"MEM_SRC_SHARE={share} puts quota_arm at {_arm!r} and FAB ships its "
                      f"grow-on-memory-pressure flag False, so the pressure-signal half of D3 is "
                      f"off at BOTH ends -- and MEM_EVICT={evict!r} is what will rank the victims "
                      f"these two branches count once eviction does start."))),
    ))

    # ==============================================================================================
    # THE RECORD
    # ==============================================================================================
    # `counters` IS A DEEP-ENOUGH COPY. store.counters['store.n_writes_by_block'] is a LIST, and a
    # frozen record holding a live reference to it is a caller that can still change what the run
    # reported. `gates` is a tuple already and is re-wrapped for the same reason.
    counters = {k: (list(v) if isinstance(v, list) else v) for k, v in store.counters.items()}
    return StoreCensus(
        counts=counts,
        floor_entries=floor,
        # THE SAME TEST THE FILTER USES -- memory/api.py::_unprotected disarms at `share <= 0.0` --
        # so the reported arm cannot disagree with the running one. MEM_SRC_SHARE declares no
        # domain, so this is `> 0.0` and not `!= 0`.
        quota_arm=_arm,
        pressure=pressure,
        probation_share=probation_share,
        live_src=live,
        # THE NUMBER OF SOURCE IDS HOLDING ENTRIES, not the table width -- see StoreCensus.
        nsrc=int((store.nsrc > 0).sum()),
        nsrc_max=int(store.nsrc_max),
        census_drift=drift,
        n_census_reconciles=int(c["store.n_census_reconciles"]),
        counters=counters,
        gates=tuple(store.gates))


def state_dict(mem: Config, store):
    """The checkpoint blob. Everything mutable that the store cannot re-derive: keys, tok, src,
    pos, ctx, own, active, use, last, born, prob, selfcon, recon, nsrc_max, gate_theta,
    gate_seeded, ctx_w, live_src, the rekey cursor, the write counter behind use_decay_every, the
    tick clocks, every store.n_* counter, and (since 2026-09-24) the victim sampler's generator
    state, `gen`.

    TWO OF THOSE NAMES ARE NEW AND ONE OF THE TWO WAS ALREADY HERE. `live_src` is DOM's last
    verdict on which sources are alive, and it is the only scalar in this blob that is not a
    property of the rows beside it -- memory/api.py::open_store re-derived it from the restored
    census, which on the measured run meant resuming a 27-domain divisor as 125 and shrinking every
    live domain's reservation 4.6x at the boundary. The one that was already here is `counters`:
    this function has written it since it was written and nothing ever read it back, so every n_*
    number in the report -- including n_entries_deleted_by_cull, THE GOAL-B NUMBER -- restarted at
    0 on the far side of a resume. The read side is in open_store rather than in
    _restore_by_block, because the seed of store.counters happens between them.

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
        # THE DIVISOR THE PER-SOURCE FLOOR IS TAKEN OVER, and the one field here that is NOT a
        # property of the rows above: it is what DOM last said was alive, set by
        # MEM.apply_domain_plan on the management cadence. The restore re-derived it from the
        # restored census, which is a different number on every store that has ever merged a
        # domain -- 125 source ids against 27 live ones on the measured run -- so the reservation
        # each live domain got shrank by that ratio at the resume boundary, silently.
        "live_src": int(store.live_src),
        "counters": dict(store.counters),
        # THE VICTIM SAMPLER'S GENERATOR, WHICH DID NOT CROSS UNTIL 2026-09-24. Every eviction draws
        # its candidate pool off store.gen, and SIG, FAB and WORLD each save their own stream while
        # this one was re-seeded from the subsystem name on every resume -- so a resumed run
        # REPLAYED the parent's first eviction choices (driven: the child's generator state was
        # byte-identical to a freshly seeded memory.torch stream). A CPU ByteTensor on every device.
        "gen": store.gen.get_state().clone(),
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
    # THE TWO READERS AGREE AT A NEGATIVE, AND THIS PARAGRAPH SAID THEY DID NOT UNTIL 2026-09-24.
    # maintain arms the re-encode on `rekey_every > 0`, so a negative reads as DISARMED there; the
    # spine's dom.rekey gate goes through RUN.Cadences.due, whose body opens with `if int(period)
    # <= 0: return False` -- DISARMED as well (driven with the switch off at MEM_REKEY_EVERY=-1 over
    # 12 windows: ledger dom.rekey checks=12 fires=0). The old sentence predicted the gate would be
    # true on every window from Cadences.due's contract before its body existed; the body disarms.
    # So a negative is an undeclared second spelling of the declared DISARM (0), on both
    # mechanisms, and the refusal stands on the owner's ruling for that reason alone.
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
            f"pass and may not be negative. Both mechanisms it drives would read {every} as "
            f"DISARMED -- MEM.maintain arms its amortized re-encode on `rekey_every > 0`, and "
            f"RUN.Cadences.due (train/api.py) returns False for every period <= 0, so the "
            f"spine's dom.rekey gate never fires and RUN.cadence_audit prints it "
            f"DISARMED -- which makes a negative an undeclared second spelling of the declared "
            f"DISARM. Refused rather than read as off, under the owner's switch "
            f"(REFUSE_NEGATIVE_PERIOD at the top of memory/api.py). Neither meaning is lost: "
            f"MEM_REKEY_EVERY=0 is the declared DISARM and MEM_REKEY_EVERY=1 re-encodes the whole "
            f"readable store every window. MEM_KEY_SRC is not consulted here: this refuses an "
            f"out-of-range value "
            f"for MEM's own lever, whether or not a second lever makes it moot.")
    return U.Windows(every)
