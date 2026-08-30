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
"""
from spine.lever import Config
from spine import units as U


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
    rather than re-deriving it from the restored counts (M53/M67).

    `lm_kind` is stored ONLY so the key_depth Gate can print its own arithmetic; nothing else reads
    it. `rng` is one spine.rng.Rng for the subsystem "memory"; every stochastic choice draws from
    it, never from the global torch stream.

    LEVERS READ: quota, owners, key_src, key_win, key_depth, evict, probation_frac, src_share,
                 verify, recon_hid, recon_tok, topk, write_mode, write_gate
    WIRES READ: d_capacity, d_owner_blocks, d_source_slots
    DID IT FIRE: store.n_opened, store.n_restored_entries, store.n_restore_refused
    """
    mem = mem.owned_by("MEM")
    _ = (mem.d_capacity, mem.d_owner_blocks, mem.d_source_slots)   # WIRES READ HERE -- the shape
    raise NotImplementedError(
        "MEM.open_store: P4 (memory) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section MEM.")


def write(mem: Config, store, *, contexts, tokens, surprise, sources, owners, positions, key_fn,
          now):
    """Gate one flush's candidate rows on surprise, encode the survivors ONCE, and commit them.

    ORDER, AND IT IS LOAD-BEARING: the gate runs for every window first, IN WINDOW ORDER, so
    gate_theta evolves identically whatever the batch width; then ONE key_fn call encodes all the
    survivors; then the rows commit per window. Encoding after the gate is exactly equivalent (the
    encoder is row-independent) and is the single largest saving in the step.

    ONE WRITE PATH. There is no `if blocks > 1:` branch. The owner NARROWS the candidate SLOT SET
    to its block; probation narrowing and per-source floor protection then run INSIDE that set.
    With blocks == 1 the block is the store. This is the repair for H31, where the per-owner path
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

    `conf` is the top cosine similarity and `blend` is computed HERE from conf, match_floor and
    blend_max -- THE CALLER NEVER RECOMPUTES EITHER. Recomputing conf at the blend site is what
    reproduced the ungated 50/50 mix one layer up in prompt.py (ISSUES C8) and cl_bench.py (C9).

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

    verify == "selfcon": scorer(ctx) -> logits, THE SAME FORWARD PATH TRAINING USED -- passed in,
    never constructed here, so the detector cannot score entries through a path the run never
    trained (M47). Per entry, the fraction of the vocabulary ranked above the stored token.
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
    described a pass the report had just performed. It runs on the management cadence the spine
    already imposes; no new lever (see FOR THE OWNER Q-MEM-8).

    LEVERS READ: verify, wrong_read, wrong_sweep, recon_hid, recon_tok
    WIRES READ: none
    DID IT FIRE: store.n_judge_runs, n_checked, n_flagged, n_swept. n_checked <= 10 is the state in
                 which the flag rule returns all-False and the whole filter is inert; the Gate
                 prints THAT ARITHMETIC rather than printing nothing.
    """
    mem = mem.owned_by("MEM")
    raise NotImplementedError(
        "MEM.judge: P4 (memory) fills this in. The contract is frozen here; see "
        "docs/04_CONTRACT.md, section MEM.")


def census(mem: Config, store, *, reconcile=False):
    """Everything the report and the domain manager need to know about the store, in one call.

    reconcile=True recomputes the per-source counts EXACTLY from (src & active) and reports the
    drift against the incrementally-maintained table. The incremental table is the floor's only
    input and it is the thing that went silently wrong. At d_capacity = 8192 an exact recount is
    8192 elements and is affordable on the management cadence -- 24x cheaper than at the 200,000
    the operator used to type.

    "floor_entries" is the number DOM's cull needs and is what REPLACES THE REACH-THROUGH at
    self_organize.py:3688. "quota_arm" says which of D3's two arms is running: "reservoir" at
    src_share > 0, "pressure_signal" at src_share == 0 -- whose other half is FAB's
    grow_on_mem_pressure, so the report must join two packages to name the arm.

    `pressure` is main/(main+prob) and its Gate prints probation_share/probation_frac BESIDE
    pressure/pressure_thresh, because H33 is that every write lands on probation, only retrieval
    promotes, probation is over budget (measured 82% of the store), eviction takes the probation
    branch almost always, and pressure reads ~0 whatever the store is suffering -- an unreachability
    that must show its own arithmetic instead of reading as calm.

    LEVERS READ: src_share, probation_frac, pressure_thresh, quota, evict
    WIRES READ: none
    DID IT FIRE: this call IS the DID IT FIRE surface for the package; it also maintains
                 n_census_reconciles and census_drift, and a nonzero census_drift is itself a
                 defect signal rather than a repair
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

    LEVERS READ: none. It is a pure read of `store`.
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
    Config hands one back for every lever that declares a Clock unit (ISSUES H51). This was one of
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
    return U.Windows(int(mem.rekey_every))
