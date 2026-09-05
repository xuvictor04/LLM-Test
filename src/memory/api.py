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
import torch

from spine.lever import Config, LeverError
from spine.gate import Gate
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
    """

    __slots__ = ("keys", "tok", "src", "pos", "ctx", "own", "active", "prob", "use", "last",
                 "born", "selfcon", "recon", "tick", "gate_theta", "n_written", "rekey_cursor",
                 "nsrc", "nsrc_max", "live_src", "capacity", "quota", "owners", "key_dim",
                 "lm_kind", "counters", "gates", "rng")

    def __init__(self, *, capacity, quota, owners, key_dim, device, rng, lm_kind):
        z = lambda *shape, dtype=torch.float32: torch.zeros(*shape, dtype=dtype, device=device)
        self.capacity, self.quota, self.owners = capacity, quota, owners
        self.key_dim, self.lm_kind, self.rng = key_dim, lm_kind, rng
        self.keys = z(capacity, key_dim)
        self.tok = z(capacity, dtype=torch.long)
        self.src = z(capacity, dtype=torch.long)
        self.pos = z(capacity, dtype=torch.long)
        self.ctx = z(capacity, dtype=torch.long)
        self.own = z(capacity, dtype=torch.long)
        self.active = z(capacity, dtype=torch.bool)
        self.prob = z(capacity, dtype=torch.bool)
        self.use = z(capacity, dtype=torch.long)
        self.last = z(capacity, dtype=torch.long)      # RETRIEVAL tick
        self.born = z(capacity, dtype=torch.long)      # WRITE tick -- see the class docstring
        self.selfcon = z(capacity)
        self.recon = z(capacity)
        for b in range(owners):
            self.own[b * quota:(b + 1) * quota] = b
        self.tick = 0
        self.gate_theta = 0.0
        self.n_written = 0
        self.rekey_cursor = 0
        self.nsrc = None                # the census; sized by open_store, GROWS on demand
        self.nsrc_max = 0
        self.live_src = 0
        self.counters = {}
        self.gates = ()

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

    LEVERS READ: quota, key_src, key_depth, owners (read by spine/assemble.py to COMPUTE
                 d_capacity and d_owner_blocks -- not by this package's own code, which never
                 reads it directly; see WIRES READ. The other ten of the fourteen this line used
                 to claim -- key_win, evict, probation_frac, src_share, verify, recon_hid,
                 recon_tok, topk, write_mode, write_gate -- are consumed by write/read/maintain/
                 judge, each of which already names them in its own LEVERS READ line, and were
                 never read by THIS entry point's body: trimmed rather than left as a claim this
                 function's own code cannot back)
    WIRES READ: d_capacity, d_owner_blocks, d_source_slots
    DID IT FIRE: store.n_opened, store.n_restored_entries, store.n_restore_refused
    """
    mem = mem.owned_by("MEM")
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
        for field in ("tok", "src", "pos", "ctx"):
            getattr(store, field)[free] = int(r.get(field, 0))
        store.own[free] = b
        store.active[free] = True
        store.prob[free] = bool(r.get("prob", False))
        store.use[free] = int(r.get("use", 0))
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
    return restored, refused


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
    raise NotImplementedError(
        "MEM.write: P4 (memory) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section MEM.")


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
    raise NotImplementedError(
        "MEM.maintain: P4 (memory) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section MEM.")


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
    pos, ctx, own, active, use, last, born, prob, selfcon, recon, nsrc, nsrc_max, gate_theta, the
    write counter behind use_decay_every, the tick clocks, and every store.n_* counter.

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
    raise NotImplementedError(
        "MEM.state_dict: P4 (memory) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section MEM.")


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
