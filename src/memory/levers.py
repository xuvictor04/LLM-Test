"""MEM -- the editable store: what gets written into it, what gets thrown out of it, and how it is read.

WHAT THIS PACKAGE OWNS. One key-value store of surprising material, written during training and read back
as a mixture over the next token. Its levers fall into six groups and each group is one decision:
WRITE (which items are surprising enough to keep), EVICT (who dies when the store is full), KEYS (what
representation the store is indexed by, and how it tracks a model that moves underneath it), PROBE (the
training-time reads without which every eviction rule is write-order FIFO whatever it says), RETRIEVAL
(how much of the output distribution retrieval may take) and WRONGNESS (which stored entries are judged
bad, and whether that judgement is acted on).

WHY THESE ARE THE LEVERS. Goal B is continual learning without catastrophic forgetting, and this store is
the one component whose failure mode IS forgetting, mechanically: an entry evicted is a fact deleted. Two
of the levers below therefore exist to keep a quiet domain alive against a loud one -- `src_share` (D3's
class-balanced reservoir quota, adopted 2026-08-28 after one source reached 88% of a 200,000-entry store)
and `probation_frac` (the scan resistance plain LRU has no defence against). Goal A is language
production, and the store contributes to it through exactly two numbers -- `blend_max` and `match_floor`,
the match-quality gate that turned memory from -0.097 b/B at 200k slots into a +0.085 b/B contribution.
Everything else here sizes, feeds or instruments those two mechanisms.

CENSUS ACCOUNTING (.rework/census.json, filtered on new_owner == "MEM"): 36 rows.
    21 rename  + 3 keep            -> 24 levers declared below
     8 drop                        -> not declared (WRONG_MARGIN, WRONG_MIN_N, WRONG_THRESH, KEY_PREGATE,
                                      KEY_BATCH, MEM_GATE, REKEY_AMORTIZED, REKEY_CHUNK)
     3 merge                       -> 2 fold into levers declared here (WRITE_QUANTILE into `write_mode`,
                                      MEM_PER_EXPERT into `owners`); 1 is unresolved, see DEFECT 3
     1 promote-to-wire             -> MEM_CAP is `d_capacity`, computed in spine.assemble, NOT declared here
   25 levers in total: the 24 above plus `wrong_sweep`, which DEFECT 3 leaves standing on its own.
   26 DECLARED HERE, because one is a CENSUS AMENDMENT and not an old-tree knob: `judge_frac`, minted
      2026-09-02 under FOR THE OWNER Q-MEM-8 and recorded in .rework/census.json's `amendments` group
      and .rework/CENSUS.md. It has no ancestor, so N2 could not be satisfied by a DEPARTURES entry;
      see its own comment in the WRONGNESS group. The 36-row census total above is unchanged, and so is
      the census's 328 -- that figure counts the old _SPEC's knobs and this was never one.

THREE CENSUS DEFECTS REPAIRED WHILE READING IT. All three were real and all three are recorded here rather
than fixed in silence, because a correction nobody can find is indistinguishable from a transcription
error going the other way.

  DEFECT 1 -- DOUBLED ENV NAMES. NINE emitted rows named their target as PREFIX.PREFIX_FIELD. lever.py
  generates the environment name as PREFIX + "_" + FIELD.upper(), so `MEM.MEM_TOPK` taken literally
  declares a field named `MEM_TOPK` answering to MEM_MEM_TOPK -- a name no operator would ever type and
  no run would ever read. The prefix is stripped from the field in all nine; the env name is unchanged
  from what the census intended. Corrected: MEM_USE_DECAY_EVERY, MEM_EVICT, MEM_RECON_HID, MEM_RECON_TOK,
  MEM_TOPK, MEM_USE_DECAY, MEM_WRITE_MODE, MEM_WRITE_GATE, MEM_WRITE_TARGET (all from the `misc` family;
  every row filed under `memory` already named its target correctly as MEM.field). Two further rows carry
  the same doubling on targets this file does not mint -- WRITE_QUANTILE -> MEM.MEM_WRITE_MODE, which is
  the merge into `write_mode` and therefore already corrected, and WRONG_SWEEP -> MEM.MEM_SWEEP, which
  DEFECT 3 disposes of. Eleven doubled rows seen, nine corrections landed on declarations.

  DEFECT 2 -- CLOCK KINDS. Two levers here are cadences: `probe_every` and `rekey_every`. Both are
  compared against `step`, and `step` advances once per WINDOW (`i += WIN; step += 1`,
  self_organize.py:7708) while the loop body runs once per FLUSH -- units.py names that confusion the
  project's single most repeated defect. Both are therefore declared U.Windows, which is what the census
  says, against source comments that say "steps" (self_organize.py:4879). No correction was needed to the
  census on these two. THE CONFLICT WITH THE SPINE, stated rather than resolved: spine/assemble.py::_owner_blocks
  wraps the analogous fabric cadence as `derive.flush_period(Steps(r["FAB"].manage_every), ...)` while
  the census types MANAGE_EVERY as `windows` -- the same counter, two kinds, in two files. That is FAB's
  row to settle, but it reaches into this package the moment anyone needs a MEM cadence in flushes:
  derive.flush_period REFUSES anything but Steps (derive.py::flush_period), so there is today no legal
  conversion from a Windows-typed cadence to the flush clock. Whoever ports the probe must either add a
  Windows->Flushes conversion to spine.derive or change what FAB.manage_every is typed as. Picking one
  here, silently, is exactly how a knob acquires two meanings.

  DEFECT 3 -- AN UNRESOLVED MERGE. The census merges WRONG_SWEEP into `MEM.MEM_SWEEP`, jointly with
  VERIFY_SWEEP. But MEM_SWEEP has no row of its own anywhere in the census, and VERIFY_SWEEP's own row is
  a DROP owned by EVAL (it makes the report mutate the store it is measuring). The merge target therefore
  has one surviving half and no declaration, so it is not minted. WRONG_SWEEP is declared below under its
  own identity as `wrong_sweep`, with its own default, and this note is the record that a policy knob
  called `sweep` was intended and is not what exists.

WHAT IS DELIBERATELY ABSENT. Three `d_` fields arrive from spine.assemble and must NOT be declared here --
lever.py refuses a d_-named lever precisely so a declaration cannot shadow the wire that writes it:
    d_capacity      = owner_blocks(FAB.slots, MEM.owners) * MEM.quota   (assemble.py, irreducible)
    d_owner_blocks  = owner_blocks(FAB.slots, MEM.owners)               (assemble.py, irreducible)
    d_source_slots  = max(64, 2 * FAB.slots)                            (assemble.py, reducible)
Capacity is the important one. The old tree declared MEM_CAP=200000 AND a quota AND an owner count --
three numbers for two degrees of freedom -- and memory.py:36 discarded the first at runtime
(`if self.n_own > 1: cap = self.n_own * self.quota`), turning 200,000 into 64 x 128 = 8,192, a 24x shrink
recorded as E7.40 with no line in any log. After this, an operator sizes the store through `quota` and
`owners`, and 200,000 is no longer a number anyone types.

    DECLARING THIS FILE TURNS tests/test_ownership.py O4 RED, ON PURPOSE, AND IT IS THE ONLY THING IN
    THIS TREE THAT DOES. O4's backward direction -- "every declared wire is read" -- defers a row while
    its package has no LeverSet in src/, and counts it as declared-but-unread once one appears. This file
    is that appearance: MEM is now registered, so d_capacity, d_owner_blocks and d_source_slots move from
    "deferred (package not in src/ yet)" to three findings, because the store that reads them is not
    ported. The check is right and the tree is half-built. The resolution is the memory port reading
    those three fields, NOT a stub reader added here to green the check -- a reader that exists to
    satisfy a check is the same species as the re-typed copy of the shipped arithmetic that cap_test.py
    records passing while the real code was wrong. tests/test_derive.py is unaffected (575 cases, 0
    mismatches, before and after).

IMPORT STYLE, AND WHY IT DEPARTS FROM THE ASSIGNMENT'S SKETCH. `from ..spine.lever import ...` cannot
work here: every entry point in this tree puts `src/` itself on sys.path (tests/test_derive.py::<module>,
tests/test_ownership.py's SRC insert, and the verification command for this file), which makes `memory` a
TOP-LEVEL package, and a relative import that walks above one raises
"ImportError: attempted relative import beyond top-level package" at import time -- verified, not assumed.
The absolute form below resolves under that convention and under no other, which is the same convention
`spine` is already imported by.
"""
from spine.lever import Lever, LeverSet
from spine import units as U


class MEMLevers(LeverSet):
    """The editable store's declared knobs: write, evict, key, probe, retrieve, judge.

    Read `cfg.quota`, never an environment name. Every value here is resolved once by spine.assemble and
    frozen; a function receiving this Config should open with `mem.owned_by("MEM")`, because a Config is
    an ordinary object and a foreign one handed in reads happily and wrongly.
    """

    PREFIX = "MEM"

    # ==============================================================================================
    # SIZE AND PARTITION -- the store's only two degrees of freedom
    # ==============================================================================================
    # Capacity is NOT here. It is d_capacity, wired from FAB.slots and these two. See the header.

    quota = Lever(
        128, "Entries each owner block may hold; blocks x quota is the whole store.", U.ENTRIES)
    # WHY IT MATTERS MORE THAN IT DID: with capacity derived, this is where store size is actually
    # chosen, including for the unpartitioned case (owners=1). The asymmetry that must not carry over is
    # self_organize.py:4873, `quota=(MEM_QUOTA if MEM_PER_EXPERT else None)` -- one declared number that
    # meant a per-block budget on one path and NOTHING AT ALL on the other, so the same 128 sized the
    # store in one configuration and was silently discarded in the other.

    owners = Lever(
        64, "How many eviction partitions the store is split into; 1 is the single global store.", U.COUNT)
    # ABSORBS MEM_PER_EXPERT (census merge). owners=1 IS the global store and owners>1 IS the partition,
    # so a separate boolean was a second way to say the same thing and the two could disagree -- they
    # did, three ways. The flag was documented DEFAULT OFF while the code read _i('MEM_PER_EXPERT', 1)
    # for the project's entire life (:4852-4854), so every recorded memory figure used the partition its
    # own comment records as worse (global 200k: -0.097 b/B; 32 owners x 64: -0.652 b/B -- one
    # configuration each, not a verdict). It was then ANDed with FABRIC at :4866, so a full pilot printed
    # "per-expert memory ON" on a SOCIETY=0 run where it had been off since step 0 (ISSUES.md:1505).
    # Both disappear with the boolean: the d_owner_blocks fold already collapses to 1 block when
    # FAB.slots is 0, so fabric-off degrades correctly with no second knob and no AND.
    # WHAT THE MERGE DOES NOT FIX, carried forward as a port requirement: real blocks are
    # min(FAB.slots, owners), so at 4096 expert slots against 64 partitions THIRTY-TWO experts share each
    # block and "per-expert memory" was per-64-buckets memory. And H31 -- the per-owner write path
    # returns before probation, the per-source floor and the pressure counters, while the report still
    # prints all three, so raising `owners` above 1 currently switches off three mechanisms declared
    # below without saying so.

    # ==============================================================================================
    # WRITE -- which surprising items are kept
    # ==============================================================================================

    write_mode = Lever(
        "fixed", "Which rule admits a surprising item: a fixed threshold, the additive controller, or "
                 "the quantile controller.", U.NAME, choices=("fixed", "adaptive", "quantile"))
    # THE DEFAULT IS THE ARM THE RUNS ACTUALLY USED, not a re-reading of the old defaults. Two booleans
    # encoded three rules: WRITE_ADAPTIVE defaulted to 0 and WRITE_QUANTILE to 1, and memory.py:133 gates
    # the quantile branch on `self.adaptive_gate and self.quantile_gate` -- so the shipped configuration
    # ran the FIXED threshold that the quantile gate was written to replace, and the fourth combination
    # was unrepresentable. The file diagnoses this against itself at :6111-6115 and the carry-forward
    # note names it the archetype: "a default that cannot fire is worse than one that is off"
    # (ISSUES:1839, :2159). One enumerated choice makes the dead combination impossible to express, and
    # choices= makes an unrecognised arm a startup LeverError instead of a silent fall into `fixed`.
    # PORT REQUIREMENT for the two non-fixed arms (ISSUES:537): gate_theta is seeded from the first batch
    # and a resume re-seeds it, so the resume path must persist it or a resumed run writes on a different
    # threshold than the one it stopped with.

    write_gate = Lever(
        0.3, "Fixed surprise threshold: store an item only when 1 - p_model(true token) is at least this.",
        U.PROBABILITY)
    # A PROBABILITY, NOT A BARE FRACTION, and saying so is load-bearing rather than pedantic: surprise is
    # 1 - p_model, and at V=16384 an undertrained model puts it near 1.0 almost everywhere. That is why
    # the additive controller cannot hit its target -- it drives gate_theta into gate_ceil=0.95, the kept
    # fraction ran 1.00 / 0.93 / 0.80 against a requested 0.12, and the store filled by step ~831 instead
    # of ~6510. This is the rule in force on the shipped configuration (write_mode="fixed"), read at
    # self_organize.py:4868 and applied at memory.py:152.

    write_target = Lever(
        0.5, "Fraction of candidate writes the adaptive and quantile arms aim to keep.", U.FRACTION)
    # INERT UNDER write_mode="fixed" -- a real conditional, so under G4 it needs a declared Gate that
    # prints its own arithmetic rather than a bare DID IT FIRE zero. Used as the quantile point
    # (memory.py:141) and as the controller setpoint (:148). It is also an irreducible coupling worth
    # stating rather than pretending away: kept fraction x stream length against d_capacity is what sets
    # when the store saturates, and turnover is what erases a quiet domain -- goal B, directly.

    # ==============================================================================================
    # EVICT -- who dies when the store is full
    # ==============================================================================================

    evict = Lever(
        "lru", "Which clock picks the victim: write order, decayed retrieval mass, or last retrieval.",
        U.NAME, choices=("recency", "usage", "lru"))
    # THE THREE ARMS ARE THE THREE BRANCHES THAT EXIST: memory.py:242 takes the sampled-victim path for
    # ("usage", "lru") and everything else falls to the circular overwrite at the else, which is
    # "recency". choices= is here because this knob is named in the case-sensitivity trap (ISSUES:361):
    # the comparison is case-sensitive, so EVICT=Lru fell into the else and silently ran write-order
    # eviction. A startup LeverError is the whole repair.
    # THE FAILURE THIS KNOB EXISTS FOR, from the file's own record: eviction inside a per-expert block
    # was LRU on `last`, `last` was WRITE recency rather than retrieval recency, and the result was
    # "every English entry gone, the unlearn test on it skipped as vacuous".
    # THE STANDING CAVEAT: "usage" and "lru" are only real if reads happen during training. That is what
    # probe_every below is for; without it both arms are FIFO under another name.

    use_decay = Lever(
        0.98, "Multiplier applied to every entry's retrieval count when the decay interval elapses.",
        U.FRACTION)
    # The half of the eviction rule that makes `use` recency-weighted rather than a lifetime total, so an
    # early-run burst of retrievals cannot make an entry immortal (memory.py:495-496). Live only under
    # evict="usage" (memory.py:287 selects `use` there and `last` otherwise) -- another declared Gate
    # under G4. Inherits the same caveat: with reads confined to eval, `use` is 0 everywhere and the
    # whole rule degenerates to FIFO.

    use_decay_every = Lever(
        20000, "How many entries must be WRITTEN before the retrieval counters are decayed.", U.ENTRIES)
    # NOT A CLOCK, AND THAT IS THE POINT OF THE RENAME. The old name DECAY_EVERY says cadence and every
    # reader takes it for steps; the counter is memory.py's `_wc`, incremented by `m` = entries actually
    # written in that call (:494-496) and consumed as `if self.use_decay < 1.0 and self._wc >=
    # self.decay_every`. It is not Steps, not Flushes and not Windows, so it must NOT be typed as a
    # Clock -- U.ENTRIES is metadata and the comparison is an ordinary integer one. The size of the
    # mistake if it were read as steps: 11.7M writes into a 200k store is three orders of magnitude.

    src_share = Lever(
        0.5, "Share of the store each live source is entitled to (src_share * cap / live sources); "
             "under D3 both the floor eviction may not cross and the ceiling admission may not exceed.",
        U.FRACTION)
    # D3 (2026-08-28) IS WHY THIS IS RENAMED AND NOT JUST CARRIED. It was MEM_SRC_FLOOR and it guarded
    # EVICTION only, one-sided -- which is how one source still reached 88% of a 200,000-entry store, the
    # exact dilution the class-balanced reservoir literature addresses. A field called "floor" for a
    # number that is now also a cap is the drift the spine exists to stop, so the field says `share`.
    # THE SUPERSEDED RULE IS STILL REACHABLE, which is what D3 asks for: "pressure is a signal, not a
    # wall" (2026-07-21) is the arm src_share=0 -- memory.py:365 returns the candidate set untouched at
    # <= 0.0, so 0 genuinely disarms and does not crash -- taken together with FAB's
    # grow_on_mem_pressure=1. Note that the second half of that arm is a FAB lever (the census moved
    # MEM_PRESSURE_ACT to FAB because its entire effect is a call into the fabric), so selecting this arm
    # means setting two knobs in two packages, and the report must be able to say which arm ran.
    # TWO DEFECTS THAT MUST NOT CARRY OVER: (1) its only input is nsrc, maintained incrementally in
    # _commit -- a path a resume never takes -- so after any resume the protection was off for the whole
    # run while the banner still printed "src floor 0.5" (C16, self_organize.py:4973-4983, fixed by
    # rebuild_census()); (2) it protects against eviction while the domain cull's mem.delete_src()
    # destroys the same entries outright on a weaker test (:604, ISSUES.md:1493).

    probation_frac = Lever(
        0.10, "Share of the store the never-retrieved region may occupy before eviction narrows to "
              "probation's own oldest.", U.FRACTION)
    # THE SCAN RESISTANCE PLAIN LRU LACKS, and the mechanism that decides whether a flood of new material
    # eats itself or eats the working set -- goal B directly. Every write lands on probation
    # (memory.py:491) and only being RETRIEVED promotes it (:557-558); while the region is over this
    # share, eviction draws its victims from probation alone (:268-277). The default is sourced rather
    # than guessed: S3-FIFO
    # sizes this region at 10%, LIRS at 1%, 2Q at 25%.
    # THE INSTRUMENT IS BROKEN, NOT THE MECHANISM, which is why it is kept rather than dropped: at the
    # measured write:read ratio (11.7M writes into 200k slots against 1469 read probes) probation is 82%
    # of the store and permanently over budget, so the probation branch is the RULE rather than the
    # exception (H33, ISSUES.md:1890-1891). ON THIS TREE THE REASON IS STRONGER AND EXACT, not a ratio:
    # MEM.read is deferred and maintain's `probe_contexts` has no producer, so NOTHING PROMOTES AT ALL,
    # probation is 100% of the store and the probation branch is taken every time -- for every
    # configuration (Q-MEM-4, RESOLVED 2026-09-02 (a): keep the definition, declare the Gate, measure
    # before retuning).
    # IT IS A PER-BLOCK SHARE, NOT A STORE-WIDE ONE. memory/api.py's write says the owner narrows the
    # candidate slot set to its block and "probation narrowing ... run INSIDE that set", so at the
    # shipped d_owner_blocks=64 and quota=128 this 0.10 is 12.8 entries per block and not 819 across the
    # store -- a factor of 64, and the two readings are different code in write's eviction path. The
    # store-wide `probation_share` census reports is an AGGREGATE and is not this predicate. Two further port requirements: probation state is not in the
    # checkpoint, so every restored entry comes back prob=False and the region is off exactly when a new
    # area arrives (M66, ISSUES.md:473); and delete() does not clear the flag, so deactivated slots keep
    # inflating the census (L61).

    pressure_thresh = Lever(
        0.80, "Threshold on pressure() -- the share of evictions destroying PROMOTED entries -- above "
              "which the store is declared genuinely short of room.", U.FRACTION)
    # RENAMED BECAUSE A FIELD CALLED `pressure` BESIDE A READING CALLED pressure() IS THE
    # WRONG-MEASUREMENT CLASS WAITING TO HAPPEN (98 of the survey's 475 records). The threshold must be
    # visibly the threshold. Kept because D3 retains the pressure-signal rule as a selectable arm and an
    # arm needs its threshold.
    # IT CANNOT REACH 0.80 ON THIS CONFIGURATION and the file says so itself at :6572-6595: eviction
    # narrows to probation whenever probation is over budget, every write lands on probation, and only
    # retrieval promotes out -- so n_main_evict stays near zero and pressure() reads ~0 for the whole run
    # whatever the store is suffering (H33). A signal that cannot reach its own threshold reads exactly
    # like a healthy one, so under G4 this becomes a declared Gate that prints its own arithmetic instead
    # of printing nothing and passing for calm.
    # THE LEVEL DOES NOT MOVE IN THIS COMMIT AND THE REASON IS NOT CAUTION (Q-MEM-4, RESOLVED (a)): on
    # THIS tree pressure is not ~0, it is EXACTLY 0 for every setting, because MEM.read is deferred and
    # maintain's probe has no contexts, so n_promoted is identically 0 and there is no promoted entry an
    # eviction could destroy. Retuning a threshold against a structural constant is unfalsifiable, and
    # changing an instrument's definition and its setting in one step is how this project produced
    # numbers nobody could attribute. Expect the eventual retune to raise this number rather than lower
    # it: at probe_rows/probe_every = 64/25 and topk=8 the probe touches ~20 entries per window against
    # ~1 gated write, so once contexts exist probation can fall under budget and pressure can pin at 1.0.
    # THE COMPARISON AGAINST THIS NUMBER HAPPENS INSIDE MEM. Its only reader is MEM.census;
    # FAB.grow_check takes a `memory_pressure` ARGUMENT and reads no threshold, so what the root hands
    # the fabric must already be MEM's verdict or fab.grow_mem_eligible fires on every flush.

    # ==============================================================================================
    # KEYS -- what the store is indexed by, and how it tracks a model that moves
    # ==============================================================================================

    key_src = Lever(
        "model", "Which representation keys the store: the live model's own encoding, or a frozen "
                 "byte-statistic table used only as a testing baseline.", U.NAME,
        choices=("model", "frozen"))
    # KEPT BECAUSE IT IS THE NULL FOR EVERY CLAIM MEMORY MAKES: "the learned key is what makes retrieval
    # domain-aware" is untestable without the frozen arm. choices= closes the same silent-else this knob
    # is named in by name (ISSUES.md:361, :2093, alongside DATA_MODE=Real): KEY_SRC=Model fell into the
    # else and silently ran the frozen baseline with no error.
    # ITS REACH IS WIDER THAN ITS NAME AND MUST BE DECLARED, NOT DISCOVERED: it gates ctx_w at
    # self_organize.py:4869, so key_src="frozen" ALSO switches off rekey (:5296) and per-expert owner
    # tagging (:7518). Three mechanisms, one knob.

    key_win = Lever(
        8, "How many preceding input positions the encoder sees when it builds one memory key.", U.TOKENS)
    # TOKENS, NOT BYTES, and the factor is real: _windows() slices the model input x, which under the
    # online tokenizer is token ids averaging ~1.85 bytes each, so calling this 8 bytes misdescribes the
    # window by that factor. Live and load-bearing at four sites -- KW at self_organize.py:971, the key
    # window at :3197, the stored context width via ctx_w at :4869 -- and it is written into the
    # checkpoint at :5339 so a loader reproduces it. The stored ctx window is also what makes re-keying
    # possible at all, so this number and rekey_every are one mechanism seen from two ends.

    key_depth = Lever(
        0, "Cap the transformer depth used for the memory key path only; 0 = the full stack.", U.COUNT)
    # KEPT UNDER THE OWNER'S RULE -- not a duplicate, nothing removes its mechanism, and the code reads it
    # (:3192-3193) -- but it is SILENTLY INERT TWICE OVER on the shipped configuration: gated on
    # MODEL_TYPE == "transformer" while MODEL defaults to "gru" (:1416), and 0 by default. That is the
    # untrippable-guard class (60 of the survey's 475 records), so it carries over with a declared Gate
    # whose predicate names lm.kind and prints its own arithmetic (G4), rather than reading as available
    # when it is not.
    # THE HAZARD TO COMMENT AT THE READ SITE: keys are re-encoded by _model_key during rekey, so a
    # truncated key path plus a full-depth rekey drifts the store into two key spaces that do not compare.

    rekey_every = Lever(
        200, "Period over which the whole readable store is re-encoded once, so keys track the model as "
             "it drifts.", U.Windows)
    # WHAT MAKES key_src="model" SURVIVABLE AT ALL. Drift in the key space is a forgetting mechanism that
    # has nothing to do with eviction, so goal B needs this even when nothing is being evicted.
    # THE UNIT IS CORRECTED, NOT PRESERVED: `step % REKEY_EVERY` at :6688 and `per = ceil(n /
    # REKEY_EVERY)` at :5302 both run against `step`, which advances once per WINDOW while the comments
    # call them steps. See DEFECT 2 in the header for the conflict this leaves with spine.derive.
    # THE DEFAULT IS AN INT, NOT Windows(200), because lever.py requires a literal default; the value is
    # wrapped in Windows() at the comparison site, which is where the kind has to be enforced.
    # ONE DEFECT TO FIX IN THE PORT RATHER THAN CARRY: the DID IT FIRE row at :8598 documents
    # REKEY_EVERY=0 as the disarming value, but `step % REKEY_EVERY` divides by it -- so the documented
    # off switch raises ZeroDivisionError on the first flush. An untrippable guard whose escape hatch
    # crashes. Whoever ports it must decide whether 0 disarms (guard the modulo) or is refused.

    # ==============================================================================================
    # PROBE -- the training-time reads that make the eviction rules mean anything
    # ==============================================================================================

    probe_every = Lever(
        25, "Cadence of the training-time read probe: real retrievals issued against the text being "
            "trained on.", U.Windows)
    # THE SINGLE MOST LOAD-BEARING KNOB IN THIS FAMILY. Before it existed, mem.read() was called only
    # from generate() and bpb_true(), both eval -- so `use` stayed 0, `last` stayed at write time for
    # every entry, and evict="lru"/"usage" were write-order FIFO whatever they said (:7539-7551). Four
    # archive files record EVICT=usage "does not protect faded knowledge by construction" as MEASURED
    # FACT; INV-24 shows it was measured through a constant (M6, ISSUES.md:1192-1194). It also decides
    # whether probation can promote at all, which is what makes probation_frac a mechanism rather than a
    # counter. Setting this to 0 disarms every retrieval-based rule above; the report must say so.
    # UNIT: Windows. The comment at :4879 says "steps", but _due (:5283) compares against `step`, which
    # advances once per WINDOW (`i += WIN; step += 1`, :7708) while the loop body runs once per FLUSH.
    # See DEFECT 2 in the header: spine/assemble.py::_owner_blocks types the analogous FAB cadence as Steps, and
    # derive.flush_period refuses anything else, so the two files do not currently agree about what
    # `step` counts. That disagreement is stated, not resolved here.

    probe_rows = Lever(
        64, "How many query rows each probe read issues; it bounds how many entries can leave probation "
            "per probe.", U.COUNT)
    # THE OTHER HALF OF THE SAME SIGNAL: the pair sets the read rate the whole eviction and probation
    # story depends on. At 64 rows every 25 windows that is ~2.5 extra key rows per step against a
    # WIN=256 x BATCH_W forward (:4881) -- cheap, and the reason the probe is affordable at all.
    # "N" NAMED NOTHING; `rows` says these are QUERY rows drawn from the current context, not store
    # entries. ONE PROPERTY MUST BE PRESERVED VERBATIM IN THE PORT, and it is the reason the mechanism is
    # honest: the rows are taken by DETERMINISTIC STRIDE, not a random draw (:7556-7559), because a probe
    # that consumed RNG draws would make the probe cadence change the training trajectory. A diagnostic
    # that silently edits the run is the class frozen_rng exists for.

    # ==============================================================================================
    # RETRIEVAL -- how much of the output distribution the store may take
    # ==============================================================================================

    topk = Lever(
        8, "How many neighbours each retrieval mixes into the returned token distribution.", U.ENTRIES)
    # Read at the store construction (:4868) and used as `kk = min(self.topk, vi.numel())` in
    # EditableMemory.read (memory.py:544-552), where it also sets the width of the returned hit and
    # weight tensors. The rename separates it from FAB_CENT_TOPK -- a different k, in a different
    # package, currently one grep away from being confused with this one.

    blend_max = Lever(
        0.5, "Maximum share of the output probability mass retrieval may take when the match is perfect; "
             "0 turns retrieval's contribution off.", U.FRACTION)
    # A CEILING, NOT A FIXED WEIGHT, and the fixed-weight reading is precisely the defect this was
    # introduced to fix. `hp` was dist.sum(), but read() scatters a softmax over the top-k, so the sum is
    # exactly 1.0 BY CONSTRUCTION: the blend was an unconditional 50/50 mix at every position however bad
    # the match, and memory measured net-negative at every store size -- -0.097 b/B at 200k slots,
    # -0.652 at 2k -- because half the mass came from retrieval when retrieval had nothing (:3261-3267).
    # blend_max=0 is also the clean retrieval-off null the memory arm needs as its baseline.
    # THE BLEND IS WRITTEN IN THIS PACKAGE so the value does not have to travel: a mixing weight read at
    # the LM forward is a foreign read, and ISSUES.md:55 records prompt.py -- the tool the deliverable is
    # actually read with -- carrying the un-gated copy of this same blend to this day.

    match_floor = Lever(
        0.3, "Top cosine similarity below which a retrieved neighbour contributes nothing; between it "
             "and 1.0 the blend ramps linearly to blend_max.", U.FRACTION)
    # WITH blend_max THIS IS THE WHOLE MATCH-QUALITY GATE, and that gate is what turned memory from
    # net-negative into a +0.085 b/B contribution. Renamed because "CONF0" named neither the quantity nor
    # its role: it is the top cosine similarity `conf` that read() already computed and every caller
    # discarded before this existed (:3263-3264).
    # PORT REQUIREMENT: conf must arrive as PART OF THE RETRIEVAL RESULT, not be recomputed at the blend
    # site -- recomputing it reproduces the original defect one layer up, the same shape as ISSUES.md:55.

    # ==============================================================================================
    # WRONGNESS -- which entries are judged bad, and whether the judgement is acted on
    # ==============================================================================================

    verify = Lever(
        "selfcon", "Which mechanism judges a stored entry wrong: self-consistency, a fitted "
                   "reconstructor, or nothing.", U.NAME, choices=("selfcon", "recon", "off"))
    # D4 READ AS ITS OPEN SUB-QUESTION DIRECTS: the reconstruction verifier's record (dead at the
    # base-rate wall, its report line in zero logs) is a reason to keep it MEASURED, not a reason to cut
    # it. "off" becomes first-class rather than a code path that rots. choices= closes the silent-else
    # this knob is also named in (ISSUES.md:361, :2093) -- VERIFY is compared case-sensitively, so an
    # unrecognised value took whichever branch was the else.
    # STATE HONESTLY IN docs/05_INSTRUMENTS.md: "recon" currently reaches only the report (:8882), not
    # the run, so what this lever selects today is narrower than what it reads as selecting.

    wrong_read = Lever(
        True, "Whether the wrong flag excludes an entry from every retrieval, or only from the sweep.",
        U.FLAG)
    # IT SEPARATES DETECTING A BAD ENTRY FROM ACTING ON IT, and the numbers say that separation matters:
    # 63,146 genuine entries flagged at 3% precision out of 200,000 -- roughly a THIRD of the store made
    # unreachable to keep 1,820 corrupt entries out -- while memory was contributing +0.085 b/B
    # (:8905-8912). Setting it to 0 keeps the flag for reporting and stops it gating reads.
    # DO NOT READ ITS APPARENT INERTNESS AS USELESSNESS: selfcheck() is called once, from the report,
    # while every write resets that entry's selfcon to -1, so today it gates the REPORT'S OWN
    # evaluations rather than the run (ISSUES.md:1902, carried forward at :2037). That is a broken
    # instrument, and the fix is a cadenced selfcheck, which probe_every now makes affordable.
    # THE ONE THING THAT MUST CHANGE IN THE PORT WHATEVER THE VERDICT: it was read TWICE -- via _i() at
    # self_organize.py:8912 and directly from os.environ at memory.py:67 -- which is the second-reader
    # pattern the spine forbids (O1) and which already broke a test: an ambient MEM_WRONG_READ=0 makes
    # mem_evict_test.py exit 1 (M99). Here it is declared once and read once.

    wrong_sweep = Lever(
        False, "Whether the selected wrongness detector DELETES flagged entries or only flags them.",
        U.FLAG)
    # DECLARED ALONE BECAUSE THE MERGE IT BELONGS TO IS UNRESOLVED -- see DEFECT 3 in the header. The
    # census folds WRONG_SWEEP and VERIFY_SWEEP into one detect-versus-delete policy called MEM_SWEEP,
    # but MEM_SWEEP has no census row and VERIFY_SWEEP's own row is a DROP owned by EVAL (its mechanism
    # makes the report mutate the store it is measuring). A merge with one surviving half is not a merge,
    # and inventing the target here would put a lever in the tree that no census row declares.
    # THE POLICY IS UNCHANGED: detect-only, because self-consistency runs at ~1-2% precision;
    # reconstruction's higher precision is what would earn deletion.
    # THE COMMENT THE OLD FLAG'S REASSURANCE HID, which is the reason wrong_read exists beside it: 0 does
    # NOT make the flag inert, because read() filters on the same predicate. Sweep off still left 63,146
    # entries -- a third of the store -- unreadable. Separating the two is what makes this flag honest.

    judge_frac = Lever(
        0.0, "Share of the ALREADY-CHECKED store that judge() re-scores on each pass, on top of the "
             "entries written since the last one. 0.0 re-scores nothing.", U.FRACTION)
    # ⚠ CENSUS AMENDMENT, 2026-09-02, ruled under FOR THE OWNER Q-MEM-8. THIS LEVER HAS NO OLD-TREE
    # ANCESTOR: the old selfcheck (self_organize.py:4048-4060) is "single pass, every entry judged",
    # called ONCE from the report, with no scope knob and no cadence knob anywhere -- so there is no
    # (family, old_name) key a DEPARTURES entry could be written under and N2 could only be satisfied
    # by amending the census. It is amended, in .rework/census.json and .rework/CENSUS.md, and said
    # loudly here. The 328 is unchanged; it counts the old _SPEC's knobs and this was never one.
    # DEFAULT 0.0 = THE RE-SCORE IS OFF, and both arms are reachable from the environment.
    # WHY IT IS MINTED RATHER THAN DECIDED. judge() is cadenced now, not end-of-run, and `selfcon` is
    # a persistent per-entry field where -1 means unchecked (memory.py:79, :492) while the flag rule
    # reads every entry with selfcon >= 0 (:585-591). So there are two legitimate checked sets and
    # they are 20x apart in cost and different in meaning, and NOTHING IN THE FROZEN SURFACES PICKS
    # ONE:
    #   0.0  -- stale-selfcon only: score the ~1 gated write per window accumulated since the last
    #           pass. At dom.manage (100 Windows) that is ~100 entries x key_win 8 = ~800 forward
    #           tokens against 100 x LM.ctx 128 = 12,800 training tokens, about 6% of the interval.
    #           THE COST OF THIS ARM IS NOT ZERO AND IT IS NOT COMPUTE: an entry keeps forever the
    #           score it got under the model that existed when it was written, and the adaptive
    #           median + k*MAD rule then computes a median over scores taken across the WHOLE run's
    #           model trajectory. That is a population mixing model epochs, and it is the argument
    #           for raising this number.
    #   1.0  -- full re-score every pass: 8192 entries x key_win 8 = 65,536 forward tokens, roughly
    #           1.7x the ENTIRE training compute of a 100-Window interval (0.34x on the 500-Window
    #           fab.manage cadence). Every score then comes from one model snapshot and the median is
    #           meaningful. This is the old tree's semantics applied on a cadence.
    # Anything between is an amortized sweep: the whole checked population is covered once per
    # ceil(1/judge_frac) passes, taken by DETERMINISTIC STRIDE from a rotating cursor -- never a
    # random draw, the same rule probe_rows carries and for the same reason (a diagnostic that
    # consumes RNG draws changes the training trajectory; frozen_rng exists for that class).
    # WHY NOT REUSE rekey_every FOR THE AMORTIZATION: compose.py already flags rekey_every as ONE
    # LEVER, TWO MECHANISMS, and hanging a third on it would make re-timing the rekey silently
    # re-time judging. A separate knob is the honest shape.
    # WHY 0.0 IS THE DEFAULT: there is no recorded number under either arm -- in the old tree every
    # write reset selfcon to -1 and the detector was structurally inert for the whole run -- so
    # "preserve the configuration the numbers were taken under" does not select an arm. What decides
    # it is that 1.0 would MORE THAN DOUBLE the cost of every run by default, which is itself a
    # confound and a capability cost, while 0.0 costs nothing and still checks strictly more than the
    # old tree ever did in-loop. THE MEASUREMENT THAT RETIRES THIS LEVER IS WRITTEN AT Q-MEM-8.
    # DID IT FIRE: store.n_rescored beside n_checked, and n_judge_cursor_wraps -- so "the sweep never
    # came round" is a different report line from "the sweep found nothing".

    recon_hid = Lever(
        64, "Hidden width of the reconstructor that maps a stored key to its expected token code.",
        U.COUNT)
    # Read once, building Reconstructor(D, V, recon_tok, recon_hid) at :4141, and only when
    # verify="recon" -- so it is inert under the default arm and needs the same declared Gate as every
    # other conditional here. Kept as a real lever because the reconstructor is fitted POST-HOC on the
    # settled store (joint training on the churning store failed at 0.3% precision), which makes its
    # capacity a thing worth varying rather than a constant.

    recon_tok = Lever(
        32, "Width of the fixed token-code space the reconstructor predicts into.", U.COUNT)
    # THE OLD NAME WAS ACTIVELY MISLEADING AND THAT IS WHY THE RENAME EARNS ITS PLACE: RECON_TOK is
    # `tok_dim` (verification.py::Reconstructor.__init__), the width of a fixed NON-LEARNED token code -- not a count of
    # tokens. The codes are deliberately non-learned so that "reconstruct the token" cannot be gamed by
    # collapsing an embedding toward a constant. Anyone reading RECON_TOK=32 as 32 tokens gets the size
    # of the whole mechanism wrong.
