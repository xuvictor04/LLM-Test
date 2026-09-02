"""CKPT -- the run's persistent state: where it is written, where a run continues from, and what is kept.

WHAT THIS PACKAGE OWNS. One run artifact root, one resume source, one periodic-save cadence, and the
retention policy for the best-by-held-out snapshots. That is the whole surface: five levers. Everything
else about a checkpoint -- what goes IN it (model, encoder, fabric, experts, world model, both optimizer
states, step, the memory store, the domain centroids, the vocabulary) and what must MATCH for it to load
again -- is mechanism, not configuration, and the census does not give this package a knob for any of it.
That is deliberate and it is the correction: in the old tree the checkpoint's own artifact paths were
free-standing knobs an operator could point anywhere, and pointing two runs at one file is what produced
the defects listed under `dir` and `resume` below.

WHY THESE ARE THE LEVERS. Goal B is continual learning without catastrophic forgetting, and in this system
a resume is not a convenience -- it is the EXPERIMENT. self_organize.py:3232 says it outright: "RESUME is
how continual learning is supposed to work here." A new area is added to a trained system by resuming into
it, and every forgetting number in the project's records is a measurement across a resume boundary. So the
levers here are the ones that decide whether that boundary exists at all (`dir`, `resume`), whether a
multi-day run survives long enough to reach one (`every` -- a crash at hour 20 used to restart from zero),
and whether the run ends holding anything worth going back to (`best_keep`, `best_keep_tol`).

Goal A is language production, and this package touches it through one number that is easy to lose: the
model the report generates from is the LIVE model at the end of training, which in every arm so far has
been 1.1-1.3 b/B worse than the model around step 6000. The .best snapshots are the only copies of the
good model that exist. A retention policy is therefore an instrument for goal A even though it looks like
a disk-space setting -- if the rotation fills with warmup weights, the run's best language model is gone.

CENSUS ACCOUNTING (.rework/census.json, filtered on new_owner == "CKPT"): 7 rows.
     3 keep + 2 rename            -> 5 levers declared below
     1 merge                      -> BEST_TRACK folds into CKPT_BEST_KEEP, which is declared here
     1 promote-to-wire            -> TOKENIZER_PATH -> d_vocab_path, NOT declared here (see below)
     0 drop
   5 levers in total, from 7 rows. CENSUS.md's ownership table says "CKPT 7" because it counts ROWS
   assigned to this package, not declarations that survive them.

THREE ROWS THAT LOOK LIKE THIS PACKAGE'S AND ARE NOT, because a reader who finds them missing will go
looking for a mistake. RATE_EVERY (the rate/ETA print cadence) is EVAL's even though the .best block sits
beside it in the source; MEM_CAP is a promote-to-wire on MEM even though the memory store dominates the
size of every snapshot this package writes; GROW_CAP_FAB0 is CAP's even though the only place its refusal
can fire is a resume (:5233-5246). Ownership follows the census, and the census follows who DECIDES the
value, not who is inconvenienced by it.

THREE CENSUS DEFECTS REPAIRED WHILE READING IT. All three were checked against this package's 7 rows; two
were present, one was not, and the negative is recorded too, because "no unresolved merge" is only useful
if someone can see it was looked for.

  DEFECT 1 -- DOUBLED ENV NAMES. ALL SIX non-wire rows name their target as PREFIX.PREFIX_FIELD, and
  five of them produce a declaration here:
  `CKPT.CKPT_DIR` (CENSUS.md:420), `CKPT.CKPT_RESUME` (:419), `CKPT.CKPT_EVERY` (:411),
  `CKPT.CKPT_BEST_KEEP` (:353) and `CKPT.CKPT_BEST_KEEP_TOL` (:354). lever.py generates the environment
  name as PREFIX + "_" + FIELD.upper(), so `CKPT.CKPT_DIR` taken literally declares a field `CKPT_DIR`
  answering to CKPT_CKPT_DIR -- a name no operator would ever type, that from_env() would never find, and
  that leaves the lever permanently at its default while every static check reports it declared and owned.
  The prefix is stripped from the field in all five; THE ENV NAME IS UNCHANGED from what the census
  intended, which is the point of the correction rather than a side effect of it. Corrected: CKPT_DIR,
  CKPT_RESUME, CKPT_EVERY, CKPT_BEST_KEEP, CKPT_BEST_KEEP_TOL. The sixth row, BEST_TRACK, carries the same
  doubling on `CKPT.CKPT_BEST_KEEP` (:356), a target already corrected above, so six doubled rows were
  seen and five corrections landed on declarations. CKPT_EVERY is the one worth naming twice: its OLD name
  was already CKPT_EVERY, so "strip the prefix" here means the field is `every` and the operator's
  spelling does not change at all -- the row is not a rename, it is a row that would have renamed itself
  by accident.
  The promote-to-wire row is NOT in this class: `CKPT.d_vocab_path` is a d_ field and the correct form.

  DEFECT 2 -- CLOCK KINDS, AND THE ONE CONFLICT IN THIS FILE. One lever here is a cadence: `every`. The
  census types it Flushes; it is declared Windows below, and the disagreement is set out in full at the
  declaration rather than settled quietly. Short form: `_due` compares elapsed `step` (:5283-5285), and
  `step` advances once per WINDOW (:6796 in the batch early-out, :7708 at the flush tail), so the number
  the operator sets is compared against a WINDOW count. The census's own reason states that arithmetic
  correctly -- "CKPT_EVERY=2000 means 2000 windows = 125 flushes at BATCH_W=16" -- and then names Flushes
  because that is the clock the gate is EVALUATED on. Where a gate is evaluated and what it compares are
  two different questions, and the unit belongs to the second one.
  NO CONFLICT WITH THE SPINE, AND IT WAS CHECKED: spine/assemble.py declares ten couplings and none of
  them names CKPT on either side (`grep -n CKPT src/spine/assemble.py` finds one word in a docstring), so
  there is no existing assumption about this knob's kind to contradict. The conflict is with the census
  row, and it is stated at the declaration.

  DEFECT 3 -- NO UNRESOLVED MERGE HERE, AND IT WAS CHECKED. The single merge, BEST_TRACK ->
  CKPT_BEST_KEEP, names a target that has a row of its own in the same family (BEST_KEEP, verdict keep,
  CENSUS.md:353). Nothing was invented and nothing is left standing alone. The surviving lever is one this
  package owns, so it is declared here, and BEST_TRACK's default of 1 does NOT carry over -- the reason is
  at `best_keep`.

WHAT IS DELIBERATELY ABSENT. Values this package computes or consumes that are not levers. lever.py
refuses a d_-named lever precisely so a declaration cannot shadow the wire that writes it:

    d_vocab_path        OUTGOING, and this package's own. Census promote-to-wire: TOKENIZER_PATH was
                        never a lever, it is the checkpoint's own artifact path. Computed from `dir` and
                        `resume`, both declared here. NOT IN THE LEDGER TODAY -- assemble.COUPLINGS has no
                        row for it, and tok/levers.py::<module> already lists it as a value TOK expects to
                        receive and does not declare.
                        ONE WIRE IS PROBABLY NOT ENOUGH, AND THIS IS THE PLACE TO SAY SO BEFORE IT IS
                        WRITTEN. The census's own reason for the promote is that TOKENIZER_PATH had TWO
                        jobs -- "the file a resume READS its parent's vocabulary from, and the file the
                        run SAVES its own to" -- and that conflating them made a run overwrite its
                        parent's vocabulary. The source already split them by hand: the write side is
                        `_TOK_SAVE = SAVE_CKPT + ".dyntok.json"` (:1010-1012) and the read side is a
                        resume heuristic (:1215-1222). A single d_vocab_path re-conflates exactly what the
                        promote exists to separate; two fields (the read source and the save target) is
                        the shape that keeps the fix.
    d_curve_bpb         INCOMING from EVAL: the held-out bits/byte of the latest curve probe, which is
                        what `best_keep_tol` compares against. eval/levers.py::<module> declares the other end
                        ("outgoing d_curve_bpb to CKPT"). Also NOT IN THE LEDGER TODAY.
    the geometry gates  INCOMING from LM, FAB and WORLD: LM.vocab_slots, FAB.dk, FAB.slots and the
                        population caps. A checkpoint built at one softmax width or one dk cannot load
                        into a model built at another, and the run already refuses it (:4442-4468 for the
                        vocabulary, :4451-4456 for dk); fabric/levers.py::FABLevers.ind_k says the refusal becomes
                        CKPT's, reading those as wires. None of them exist as couplings yet.
    the SIGUSR1 save    Not a knob at all: `kill -USR1 <pid>` sets a flag the loop drains beside the
                        periodic save (:7709). It has no lever, it needs none, and it is recorded here so
                        that "the only saves are the final one plus the cadence" is not read as complete.

IMPORT STYLE, AND WHY IT DEPARTS FROM THE ASSIGNMENT'S SKETCH. `from ..spine.lever import ...` cannot work
here: every entry point in this tree puts `src/` itself on sys.path (tests/test_derive.py, test_ownership's
SRC insert, and this file's own verification command), which makes `ckpt` a TOP-LEVEL package, and a
relative import that walks above one raises "attempted relative import beyond top-level package" at import
time. The absolute form below is what all ten existing lever packages use.
"""
from spine.lever import Lever, LeverSet
from spine import units as U


class CKPTLevers(LeverSet):
    """Checkpointing's declared knobs: where state is written, where it is continued from, how often it is
    saved, and how many of the good models are kept.

    Read `cfg.every`, never an environment name. Every value here is resolved once by spine.assemble and
    frozen; a function receiving this Config should open with `ckpt.owned_by("CKPT")`, because a Config is
    an ordinary object and a foreign one handed in reads happily and wrongly.

    Grouped by decision rather than alphabetically: the pair that decides whether persistence happens at
    all, then the cadence, then the retention policy. `dir` is first because three of the other four are
    inert without it -- a fact that today is a warning string at :5619-5621 and should be a declared Gate.
    """

    PREFIX = "CKPT"

    # ==============================================================================================
    # 1. WHERE STATE GOES, AND WHERE IT COMES FROM
    #
    # Two paths. Together they are the whole continual-learning boundary: `dir` is where this run's
    # state will be readable from, `resume` is whose state this run continues. Everything else in this
    # file is a policy about when and how many.
    # ==============================================================================================

    dir = Lever("", "Directory this run writes its checkpoint into -- model, tokenizer, memory store, "
                    "optimizer moments, domain centroids; empty turns saving off entirely.", U.PATH)
    # Census: SAVE_CKPT -> CKPT.CKPT_DIR, verdict rename, unit path, default "". Field corrected from
    # `CKPT_DIR` to `dir` (DEFECT 1); the env name is CKPT_DIR either way, which is what the census meant.
    # THE RENAME IS THE FIX, NOT COSMETICS. Calling a path SAVE_CKPT invited it to be read as a flag, and
    # that produced a committed defect (:5324-5330): every other switch in the old file is an integer, so
    # `SAVE_CKPT=0` is the obvious way to disable saving -- but "0" is a truthy string. `if not ck: return`
    # never fired, os.makedirs("0") ran, and the run wrote ckpt.pt and source.bin into a directory
    # literally named `0` in the repo root. .gitignore covers neither (source.bin is not *.pt and `0/` is
    # not `runs/`), so it got committed. A name that says DIR cannot be typed as a flag by reflex.
    # THE DISABLED-SPELLING NORMALISATION HAS NO HOME HERE, AND THAT IS A GAP RATHER THAN A DECISION.
    # The old tree normalises ("0", "", "off", "no", "none", "false") -> off at :5329, hundreds of lines
    # below the FIRST consumer at :1010, so the tokenizer save path was computed from the raw string and
    # would have named a file "0.dyntok.json". The census asks for that predicate to live "in the lever's
    # own parse where all four call sites see one clean value". It cannot: `choices=` cannot express "any
    # path, or one of six spellings of off", and Lever.coerce for a str default is `str(raw)` with no
    # per-lever hook. The honest repair is one derivation in this package -- a named function that answers
    # "is saving on" once and is called by every site -- not six string literals re-typed at four call
    # sites, which is the state this rebuild exists to leave behind.
    # THE DEFAULT IS OFF BECAUSE THAT IS WHAT THE OLD DEFAULT WAS. Empty string, literal, exactly as the
    # census records it. A default that quietly turned saving ON would change what every existing number
    # in the records was taken under, and would write gigabytes from a test run.
    # TWO THINGS IT FEEDS THAT MUST BE DECLARED WIRES, NOT INCIDENTAL READS: the tokenizer's save target
    # (_TOK_SAVE = dir + ".dyntok.json", :1010-1012) -- a run's vocabulary going beside its own checkpoint
    # is what stopped concurrent arms overwriting one shared data/dyntok.json (ISSUES.md:1501, :285,
    # :768) -- and the fact that `every` is inert without this, which today is only the warning string at
    # :5619-5621 and should be a Gate that prints its own condition.

    resume = Lever("", "Checkpoint to continue training from -- a run directory or a .pt file; empty "
                       "starts from scratch.", U.PATH)
    # Census: RESUME -> CKPT.CKPT_RESUME, verdict rename, unit path, default "". Field corrected
    # (DEFECT 1). Renamed because as a bare verb it owns nothing and reaches everywhere -- :1012,
    # :1216-1222, :1226, :4361-4364, :4893, :4990, :5233-5246 -- which makes it the densest coupling site
    # in the old file.
    # KEPT ON THE STRONGEST GROUNDS IN THE CENSUS: ":3232 states outright that 'RESUME is how continual
    # learning is supposed to work here'", which is goal B itself. It restores model, encoder, fabric,
    # experts, world model, both optimizer states, step, the memory store and the domain centroids, and it
    # forces the SAVED vocabulary -- a fresh online seed would re-mint different ids, so the restored
    # embedding table would be indexed by a DIFFERENT vocabulary (:1226-1227).
    # ONE SPELLING, WHICH IS ITSELF A FIX THAT MUST NOT REGRESS. RESUME and SAVE_CKPT were read as None in
    # some places and "" in others (:73). The lever has one literal default and one type, so "unset" has
    # exactly one representation in the whole tree.
    # FOUR COUPLINGS, EACH WITH A DOCUMENTED FAILURE, AND EACH MUST ARRIVE AS A DECLARED WIRE:
    #   (1) The sibling-vocabulary guess breaks on the SUPPORTED RESUME=runs/x/ckpt.pt form: the candidate
    #       is runs/x/ckpt.dyntok.json, which does not exist, so it falls through to the shared
    #       data/dyntok.json "which belongs to whichever run wrote it last" (ISSUES.md P1-M19).
    #   (2) A resume with checkpointing off can save NO vocabulary at all: the only file it could write is
    #       the one it read its parent's vocabulary from, and overwriting that is the failure the block
    #       exists to stop (:1007, :7847-7849).
    #   (3) The fabric slot count can exceed the checkpoint's cap ONLY on a resume -- FAB_N0 then comes
    #       from the checkpoint (523 in the run this was written for) while a GROW_CAP arm sets its start
    #       cap to 160 or 256, and the growth clamp min(burst, cap - n) goes negative, so the run trains
    #       to completion having grown nothing on a configuration whose purpose is to study growth
    #       (:5233-5246). The refusal is CKPT's in the rebuild and it reads FAB's numbers as wires.
    #   (4) `_best_bpb` starts cold on every process and nothing in the checkpoint carries it, so the
    #       first post-resume probe satisfies "no best yet" and overwrites the PARENT's best-by-held-out
    #       snapshot with the Adam re-warm bump (ISSUES.md P1-M45). That one is this package's own bug,
    #       not a coupling: the best-so-far is checkpoint state and belongs in the checkpoint.

    # ==============================================================================================
    # 2. CADENCE -- how often mid-run state is written
    # ==============================================================================================

    every = Lever(0, "How often a mid-run checkpoint is written, in windows elapsed since the last one; "
                     "0 disables periodic saving, leaving the final save and SIGUSR1.", U.Windows)
    # Census: CKPT_EVERY -> CKPT.CKPT_EVERY, verdict keep, default 0. Field corrected to `every`
    # (DEFECT 1) -- the env name CKPT_EVERY is unchanged, so no operator script has to move.
    # LOAD-BEARING FOR GOAL B, AND IT SURVIVES ON MERIT RATHER THAN ON THE REPORT. A resume is how
    # continual learning is exercised here, and there is nothing to resume from if a multi-day run holds
    # only its final save. It is NOT in the "never observed to fire" class for the usual reason -- it
    # provably COULD NOT fire for a whole era. It sat in the modulo-cadence block below the
    # `if len(_bx) < BATCH_W: step += 1; continue` early-out, so the block only executes on FLUSH steps,
    # which land on a fixed residue mod BATCH_W, while `step` advances on every window; `step % N == 0`
    # then asks for a simultaneous solution to two congruences that usually has none. Simulated over
    # 200,000 windows it fired ZERO times for every BATCH_W > 1 tested, odd ones included (:5265-5274).
    # That is a broken gate, not a useless knob, and it is already fixed to elapsed-since-last-fire
    # (`_due`), which is phase-independent and resume-safe.
    #
    # THE UNIT: Windows HERE, Flushes IN THE CENSUS. STATED, NOT SETTLED QUIETLY (DEFECT 2).
    #   What the census row says: unit `Flushes`, on the reasoning that "`_due` measures elapsed `step`,
    #   and `step` advances once per WINDOW (:6795, :7708) while the block containing the gate only
    #   executes on FLUSH steps -- so 'CKPT_EVERY=2000' means 2000 windows = 125 flushes at BATCH_W=16 ...
    #   Declare it in Flushes, the clock the gate is actually evaluated on."
    #   What the code does: `_due(_k, _n)` is `if _n <= 0 or step - _fired[_k] < _n: return False`
    #   (:5283-5285). The quantity compared against this lever is `step - _fired`, and `step` counts
    #   WINDOWS -- it is incremented both in the early-out (:6796) and at the flush tail (:7708), i.e.
    #   once per window on every path. So the number an operator types is a count of WINDOWS.
    #   Why they differ: the census answered "which clock is the gate evaluated on" and the unit answers
    #   "which clock is the threshold compared against". Declaring Flushes while comparing against a
    #   window counter is the pin_tick defect exactly -- a threshold in one unit against a counter in
    #   another, off by BATCH_W, silently -- and units.py names that as the project's single most repeated
    #   defect. Windows is the kind that makes `Flushes(...) >= Windows(...)` raise instead of pass.
    #   What it costs to be wrong either way, in the numbers the runs actually used: longrun.sh:521 ships
    #   CKPT_EVERY=4000 at BATCH_W=12, which is 4000 windows = 333 flushes. Reading one as the other is a
    #   12x error in how often a long run is killable.
    #   IF THE PORT REALLY WANTS A FLUSH BUDGET -- and there is a case for it, since a flush is the unit
    #   of work the save interrupts -- the conversion must be a NAMED function in spine.derive, like
    #   derive.flush_period. There is no Windows->Flushes function there today (flush_period takes Steps
    #   and refuses anything else, derive.py::flush_period), so the conversion would have to be added with its
    #   own oracle row. Doing it inline at the comparison is how pin_tick happened.
    #   THE BATCH WIDTH IT WOULD CONVERT THROUGH IS NOT THIS PACKAGE'S: census BATCH_W -> OPT
    #   (OPT_BATCH_WINDOWS, unit Windows, default 1), while spine/assemble.py spells the same value
    #   TRAIN.batch_w in three couplings. That naming disagreement is assemble's to resolve; it is noted
    #   because whoever adds the conversion will meet it.

    # ==============================================================================================
    # 3. RETENTION -- which of the models this run passes through still exist at the end
    #
    # Both of these are read against the held-out learning curve, which EVAL owns and which must arrive
    # as d_curve_bpb. They are declared here rather than on EVAL because keeping a file is a checkpoint
    # policy: EVAL decides what the number IS, CKPT decides what is kept because of it.
    # ==============================================================================================

    best_keep = Lever(0, "How many recent local lows in held-out bits/byte to retain as rotating "
                         ".best1..bestN checkpoints, on top of the single global .best.", U.COUNT)
    # Census: BEST_KEEP -> CKPT.CKPT_BEST_KEEP, verdict keep, default 0, unit COUNT. Field corrected
    # (DEFECT 1). ABSORBS THE BEST_TRACK ROW (verdict merge, old default 1), whose value does NOT carry
    # over because the flag itself does not: 0 here means exactly what BEST_TRACK=1 did -- a single
    # rotating .best -- and `dir` empty already means no saves at all, so there is nothing left for a
    # second off-switch to switch.
    # WHY THE FLAG DIES, BOTH REASONS VISIBLE IN THE CODE.
    #   (1) COUPLING. The keep block is nested inside `if BEST_TRACK and _CURVE:` (:6432, keep test
    #       :6480), so BEST_KEEP=2 with BEST_TRACK=0 rotates nothing and prints nothing. longrun.sh ships
    #       BEST_KEEP=2 in three arms (fix_cadence, fix_vocab, fix_resume at :519-521), every one of which
    #       would have done nothing at all if the flag were ever cleared.
    #   (2) WRONG HOME. The same block owns the BLEW UP divergence alarm (:6458-6472), which is an
    #       INSTRUMENT, not a checkpoint policy. Gating it on a checkpoint flag means a run that is not
    #       saving gets no warning that it has stayed elevated: the recorded case lost 4.6 bits/byte and
    #       then spent about 520,000 further steps -- roughly seven hours -- never getting back, with
    #       nothing said until the end-of-run report, which called it PLATEAUED. In the rebuild that alarm
    #       is an EVAL Reading over the curve (spine/derive.py::pin_tick blowup_stale already carries its rule:
    #       what separates a blow-up from ordinary wander is not the size of the excursion but how long
    #       the run stays elevated without setting a new best), and the .best save is this retention
    #       policy. ISSUES P1-L43 goes with the flag too: the block rescans the whole _CURVE list once per
    #       window with no cadence guard, returning empty on all but 1-in-RATE_EVERY of them.
    # WHY IT EXISTS, AND WHY IT IS AN INTEGER RATHER THAN A BOOLEAN. Direct owner instruction ("For the
    # long run, I want to checkpoint every local low point"), against a real loss: the best-by-held-out
    # checkpoint is ONE file that keeps being overwritten, so on a long run every earlier low is gone by
    # the end and there is nothing to go back to. It stays opt-in at 0 because it is a DISK budget --
    # roughly 420-515 save events over a long run rotating through n resident slots, and the memory store
    # dominates each snapshot -- not a coverage decision.
    # ONE DEFECT THIS LEVER MULTIPLIES, RECORDED HERE BECAUSE ROTATION MAKES IT n TIMES WORSE. ISSUES.md
    # M46, at :5335-5337 and :5344-5348: `ck = ck + suffix` applies the .bestN suffix to the CHECKPOINT
    # path, but the tokenizer is always written to the BASE vocabulary path, so every later save
    # overwrites the file a .bestN snapshot records as its own. By the end of a run a .best
    # checkpoint's recorded merge count no longer matches the file it names, and resuming from it
    # trips the VOCABULARY MISMATCH refusal (:4380-4408). The rebuild's one-artifact-root ownership is
    # what makes this fixable: a snapshot's vocabulary is part of the snapshot.

    best_keep_tol = Lever(0.02, "How close to the best held-out bits/byte seen so far a descending probe "
                                "must land, as a fraction of it, to earn a rotation slot.", U.FRACTION)
    # Census: BEST_KEEP_TOL -> CKPT.CKPT_BEST_KEEP_TOL, verdict keep, default 0.02, unit FRACTION. Field
    # corrected (DEFECT 1).
    # NOT A DUPLICATE OF best_keep AND NOT MERGEABLE INTO IT: one says how many restore points to hold,
    # the other says how good a point must be to earn one. Without the tolerance every improving probe
    # early in a run qualifies as a local low, the rotation fills with warmup checkpoints, and the run
    # ends holding n snapshots of its WORST weights -- which is the opposite of the mechanism's purpose
    # and would look identical in the log.
    # THE RULE IT IMPLEMENTS IS "DESCENT INTO A GOOD REGION", NOT "LOCAL MINIMUM", and that is deliberate:
    # `_cm < _prev_probe - 1e-6 and _cm <= _best_bpb * (1.0 + tol)` (:6480). A true local minimum can only
    # be CONFIRMED one probe later, once the curve turns back up, and by then the weights have moved past
    # it. So this is a superset -- every local minimum, plus some points on the way down to one -- which
    # is the right direction to be wrong in: a spare restore point costs disk, a missing one cannot be
    # recovered.
    # IT IS MULTIPLICATIVE, NOT ADDITIVE, AND A READER WILL ASSUME OTHERWISE. The test is
    # best * (1 + tol), so at a best of 2.175 b/B the default 0.02 admits anything up to 2.219 -- a window
    # of 0.043 bits/byte, not 0.02. FRACTION is the honest unit label for that; it is a fraction OF the
    # best, and it is not a bits/byte quantity even though everything it compares is.
    # THE NUMBER IT COMPARES AGAINST IS NOT THIS PACKAGE'S. The held-out b/B comes from the eval curve
    # probe and must arrive as the declared wire d_curve_bpb -- eval/levers.py::<module> already states the
    # other end of it -- which is precisely the coupling the new tree is required to print rather than
    # hide. It is not in spine/assemble.py's COUPLINGS today, and until it is, this lever has a threshold
    # with nothing to compare.
