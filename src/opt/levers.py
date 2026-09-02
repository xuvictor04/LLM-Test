"""OPT -- the schedule and the optimiser: the one absolute learning rate, its shape over time, and the
size of the batch that rate is applied to.

WHAT THIS PACKAGE OWNS. Every rate the system ever applies is `lr` times a multiplier in 0..1, and this
package owns the peak, the multiplier's shape (warmup, cosine wavelength, floor, restarts, damping,
envelope, re-warm), the decoupled weight decay handed to both AdamW instances, and the two numbers that
decide what one optimizer step is taken over (`batch_windows`, `accum`). It owns no data, no cadence
belonging to another subsystem, no instrument and no model geometry. It owns exactly one closed loop --
`lr_restart_damp` -- and that loop is the only place in the whole file where a MEASUREMENT crosses back
into a training decision, which is why it arrives as a wire and not as a read.

WHY THESE ARE THE LEVERS, against the two goals and nothing else.

  GOAL A IS LANGUAGE PRODUCTION, AND THE SCHEDULE IS THE LEADING HYPOTHESIS FOR WHY IT HAS NOT WORKED
  YET. All 17 pilots bottom in held-out bits/byte at ~2.4 around step 6000 and then RISE to ~3.8-4.1 by
  48,000 -- across GRU and transformer, fabric and FABRIC=0, every routing variant (:7003-7011). A cause
  common to all of those arms cannot be the fabric, the router or the blend rule. A constant 2e-3 on
  AdamW for 48k steps is exactly that shape: fast early progress, then bouncing around a minimum it can
  no longer settle into. `lr_sched` is the one-flag ablation for that hypothesis, which is why it is kept
  rather than folded away, and why it carries `choices=`.

  GOAL B IS CONTINUAL LEARNING WITHOUT CATASTROPHIC FORGETTING, and three of these levers are directly
  about it rather than about convergence.
    * `lr_min_frac` exists because a continual-learning system that anneals to nothing cannot learn
      anything that ARRIVES LATE (:4752). The add-area entry point is the late-arrival case, so a
      schedule that reaches zero is a schedule that cannot do the thing this project is for.
    * `lr_shift_warm` is the schedule's half of `note_shift()`. Growth is already told "this jump is
      OURS, not the data's" for a retok and for an epoch resample; the LEARNING RATE meets the same fresh
      text at whatever the cosine says, which has been 96-99% of peak at the second boundary in every run
      measured, and is what destroyed round13 (ISSUES.md PART 3, H12). An added area IS a self-inflicted
      distribution shift.
    * `weight_decay` is a forgetting term the OPTIMISER introduces, orthogonal to anything the fabric or
      the memory does: decoupled decay is applied every step to every parameter regardless of gradient,
      so a dormant expert loses ~71% of its magnitude over a 62.5k-step run (:4326-4328) -- a mechanism
      nothing is training is nevertheless being erased. It is off by default and it is a lever precisely
      so that the erasure is a decision somebody made rather than AdamW's implicit 0.01.

CENSUS ACCOUNTING (.rework/census.json, filtered on new_owner == "OPT"): 14 rows + 1 AMENDMENT.
    10 keep + 2 rename             -> 12 levers declared below
     1 merge                       -> LR_EPOCHS folds into `lr_wavelength`, which is LR_STEPS's own row
     1 drop                        -> RECON_W, not declared (CENSUS.md:241)
     0 promote-to-wire
     1 amend                       -> OPT_GRAD_CLIP, minted 2026-09-02, NO ANCESTOR KNOB
   13 levers in total, from 14 old-tree rows plus one amendment. CENSUS.md:38 says "OPT 14" because it
   counts ROWS assigned to this package, not declarations that survive them, and the amendment does NOT
   move that figure -- the 328 and every per-package total in CENSUS.md count knobs the old system had,
   and this is not one. The two rows that do not become declarations are named above rather than
   subtracted silently, so a reader who counts thirteen against a table that says fourteen does not have
   to re-derive which two went where and where the thirteenth came from.

⚠ THIS PACKAGE HOLDS ONE OF THE TREE'S TWO CENSUS AMENDMENTS. `grad_clip` is declared in section 1
below with its full reason; `.rework/CENSUS.md` gained an `amendments` section and
`.rework/census.json` an `amendments` group in the same edit, and `tests/test_census.py` N1 was widened
to check `amend` rows so that deleting the lever fails a check instead of leaving an orphan row.

THE OTHER IS `MEM_JUDGE_FRAC`, and this paragraph said "the tree's ONLY census amendment" while it
existed -- both were minted on 2026-09-02, by different slices of the same run, neither knowing about
the other. Worse than the wrong word: both were written with `old_name` = "(none -- amendment, not an
old-tree knob)", which is a true sentence and a DUPLICATE KEY. `DEPARTURES` is keyed by
(family, old_name) and N3 builds a dict from it, so N3's lookup kept MEM_JUDGE_FRAC and dropped this
one entirely -- a departure declared against OPT_GRAD_CLIP would have read "no census row with this
identity" while the row sat in census.json. Each amendment now carries "(amendment: <NAME>)", and
tests/test_census.py N6 refuses a duplicate identity outright.

ONE ROW THAT LOOKS LIKE ANOTHER PACKAGE'S AND IS FILED HERE. RECON_W arrives from the `memory` family
(CENSUS.md:241) and is DROPPED, so it declares nothing -- but the reason it was filed to OPT at all is
the rule this package is defined by and is worth keeping: "a loss-term weight belongs to whoever composes
the loss; the memory package must not be able to add terms to it". Its mechanism is going (it trained a
Reconstructor on a store that was re-tokenized and re-keyed underneath it, so its targets moved while it
fit, and it reached 0.3% precision, :529-531); the repair already shipped as EVAL's post-hoc
`verify_fit_steps`. Dropping it also deletes a live cost defect: before the RECON_W>0 guard at
:7053-7055 a full key encode was computed every step and then multiplied by 0.0 on the default path.

THREE CENSUS DEFECTS REPAIRED WHILE READING IT. All three were checked against this package's 14 rows.
One was present in every row that names a field; one required no re-typing and the reason it required
none is the whole of what this package's units are about; one was absent. The negatives are written down
because "nothing to fix here" is only useful if a reader can see that it was looked for.

  DEFECT 1 -- DOUBLED ENV NAMES. THIRTEEN of this package's fourteen rows name their target as
  PREFIX.PREFIX_FIELD -- `OPT.OPT_LR`, `OPT.OPT_LR_SCHED`, `OPT.OPT_BATCH_WINDOWS` and so on
  (CENSUS.md:387-397, 401, 403). spine/lever.py::Lever.env_name_for generates the environment name as
  PREFIX + "_" + FIELD.upper(), so `OPT.OPT_LR` taken literally declares a field `OPT_LR` answering to
  OPT_OPT_LR: a name no operator would ever type, that from_env() would never find, and that therefore
  leaves the lever pinned at its default forever while every static check reports it declared, owned and
  resolved. That is the silent-default class this rebuild exists to end, arriving through the document
  that is supposed to end it. The prefix is stripped from the FIELD in every case and THE ENV NAME IS
  UNCHANGED from what the census intended -- that invariance is the point of the correction, not a side
  effect of it. TWELVE CORRECTIONS LANDED ON DECLARATIONS: OPT_LR, OPT_LR_SCHED, OPT_LR_WARMUP,
  OPT_LR_MIN_FRAC, OPT_LR_WAVELENGTH, OPT_LR_RESTARTS, OPT_LR_RESTART_DAMP, OPT_LR_DECAY,
  OPT_LR_SHIFT_WARM, OPT_BATCH_WINDOWS, OPT_ACCUM, OPT_WEIGHT_DECAY. The thirteenth doubled row is the
  merge -- LR_EPOCHS -> `OPT.OPT_LR_WAVELENGTH` -- whose target is a field already corrected above, so it
  mints nothing new. The fourteenth row carries no field at all: the drop writes `OPT.` with an empty
  name. Thirteen doubled rows seen, twelve corrections landed.

  DEFECT 2 -- CLOCK KINDS. FIVE of the twelve levers are clock-typed and NONE OF THE FIVE IS RE-TYPED
  HERE. That is a decision, not an omission, and it splits into two different arguments.

    (a) THE THREE LR QUANTITIES STAY Steps -- `lr_warmup`, `lr_wavelength`, `lr_shift_warm`. The rule
    the assignment states ("the LR horizon is in STEPS only") is the frozen contract: units.Steps is
    documented as "what the LR schedule's horizon is denominated in, and nothing else", and units.Epochs
    as "never a schedule horizon". The tempting re-type is real and it is wrong. `_lr_at(step, ...)` is
    passed `step`, and `step` advances once per WINDOW (:6796 `i += WIN; step += 1`, :7708) while the
    loop body runs once per FLUSH (:934) -- so today a warmup written in steps is consumed against a
    window counter and completes batch_windows times sooner than it says. THAT IS A DEFECT IN THE
    CONSUMPTION, NOT IN THE LABEL. Re-typing these three as Windows would "fix" the mismatch by making
    the LR horizon a function of batch_windows: OPT_LR_WAVELENGTH=280000 would then mean 280,000 steps at
    batch_windows=1 and 4,480,000 at 16, and two runs differing only in the batch size would be two
    different learning-rate experiments. That is precisely the fault the LR_EPOCHS merge was forced to
    remove, re-introduced under a new denominator. The repair the census asks for is a named conversion
    in spine.derive, taken once, not a re-labelling here.

    (b) `batch_windows` STAYS Windows AND `accum` STAYS Backwards, with the tension recorded. Both are
    per-something quantities -- windows per flush, backward passes per optimizer step -- and this tree
    has twice declared that a ratio must NOT wear a clock kind (eval/levers.py::EVALLevers on `windows`,
    sig/levers.py::SIGLevers on `positive_radius_windows`, both reasoning that typing a ratio as a clock invites
    the very comparison units.py exists to refuse). The census types them Windows and Backwards anyway,
    and they are left that way for a reason the source supports: `batch_windows` is the SIZE OF A FLUSH
    MEASURED IN WINDOWS and `accum` is the SIZE OF AN OPTIMIZER STEP MEASURED IN BACKWARD PASSES -- each
    is a count of the events its kind names, not a dimensionless ratio, and units.Backwards names ACCUM
    in its own docstring. What must be understood by anyone reading `cfg.batch_windows` is that THE UNIT
    IS METADATA AND THE VALUE IS A BARE int: units.py section 1 says so ("cheap, always correct, never
    enforced"), Lever.coerce returns int, and nothing in this file constructs a Clock. So
    `derive.flush_period(Steps(...), cfg.batch_windows)`, whose signature documents `batch_w` as a
    "(count)", works exactly as written -- the label and the call site do not disagree at runtime, only
    on paper.

    THE CONFLICT THIS PACKAGE MUST NOT RESOLVE ALONE is bigger than either and is stated under CONFLICTS
    below: spine/assemble.py already assumes a DIFFERENT OWNER for two of these five.

    NO ROW HERE IS THE WRONG CLOCK IN THE WAY THE ASSIGNMENT'S EXAMPLE DESCRIBES -- "a cadence measured
    by the training loop step counter is Windows, not Steps" -- and the check is worth stating because it
    is a claim about this package a later reader can test: not one of the twelve levers is a CADENCE.
    Nothing in this file is of the form `step % X == 0`. The three Steps levers are HORIZONS inside one
    pure function of the step number (`_lr_at`), and a horizon is what units.Steps is reserved for. The
    cadences that DO belong to that example are FAB.manage_every and CAP's pin clock, and both are
    already recorded as Windows in their own files.

  DEFECT 3 -- NO UNRESOLVED MERGE, AND IT WAS CHECKED. The single merge names a target that has a row of
  its own in the same family: LR_EPOCHS -> OPT_LR_WAVELENGTH is LR_STEPS's row (verdict rename,
  CENSUS.md:403). Nothing was invented, no lever below exists only because a merge pointed at it, and no
  row had to be emitted under its own name to avoid inventing a target. The merge is also the one in this
  census that is FORCED rather than chosen: two spellings of one quantity, converted through a per-epoch
  step count that nothing holds fixed -- "LR_EPOCHS=8" has meant 48,000 steps at STREAM_LEN=4e6 and
  840,000 at 94e6, a 17x range under one number (:4718-4722).

THREE CONFLICTS WITH THE SPINE, RECORDED WHEN THIS FILE WAS WRITTEN AND ALL THREE SETTLED SINCE, IN THE
SPINE. Picking a side inside a declaration file is how a knob acquires two meanings, so none of the
three was decided here -- and each was then decided in spine/assemble.py, which is where a wiring
decision belongs. THE THREE ARE KEPT, EACH WITH ITS OUTCOME, because this file predicted the failure
mode of leaving them alone: a conflict paragraph that has stopped being true "will read as 'not ported
yet' long after it has become 'ported'". It then became exactly that, and stayed that way through the
2026-09-02 apply commit, until 2026-09-03. Every "what is true now" below was read off the tree, not
off a document.

  (a) WHO OWNS THE BATCH -- SETTLED IN OPT'S FAVOUR. AS ASKED: spine/assemble.py read
  `r["TRAIN"].batch_w` and `r["TRAIN"].accum` in four couplings (FAB.d_manage_period,
  FAB.d_cap_lift_period, TOK.d_cap_lift_period, and the local TRAIN.d_effective_batch_windows). The
  census says these two levers are OPT's -- BATCH_W -> rename OPT_BATCH_WINDOWS (CENSUS.md:401),
  ACCUM -> keep OPT_ACCUM (CENSUS.md:387) -- and there is no package TRAIN anywhere in the census at
  all: the loop package is RUN, which CENSUS.md:40 gives 9 ROWS (7 declarations survive them --
  the same rows-vs-declarations gap this file's own accounting header explains for OPT's 14).
  spine/assemble.py's header says "7 levers" for the same reason. The disagreement was TWO-LAYERED. The
  PREFIX differed (TRAIN vs OPT) and so did the FIELD (`batch_w` vs the renamed `batch_windows`), so
  correcting only the prefix would not have resolved it. And build() did not fail on any of it: a
  coupling naming an unregistered package is DEFERRED with a warning, TRAIN was registered by nobody,
  so all four rows printed "DEFERRED ... package(s) ['TRAIN'] not registered" and were NOT MADE. A
  declared-but-unmade wire is the untrippable-guard shape that warning exists to expose.
  WHAT IS TRUE NOW: the sources are retargeted and the edges are made. `FAB.d_manage_period`,
  `FAB.d_cap_lift_period` and `TOK.d_cap_lift_period` compute from `r["OPT"].batch_windows`, and
  `d_effective_batch_windows` is `OPT.d_effective_batch_windows` -- still LOCAL, now local to the
  package the census gives it to, computed as `r["OPT"].batch_windows * r["OPT"].accum`. The string
  `r["TRAIN"]` does not appear in assemble.py at all; that file's own header records the same three
  renames (TRAIN.batch_w -> OPT.batch_windows, TRAIN.grow_cap_every -> CAP.pin_windows,
  TRAIN.accum -> OPT.accum). The repair was made where it belonged and this file still did not make it.
  What this file will NOT do, then or now, is declare `batch_w` as a second spelling to keep assemble
  quiet: that would put the flush size in two names at once, which is the failure the ownership spine
  exists to prevent.

  (b) ONE WIRE, TWO NAMES -- SETTLED AS `d_base_lr`, AND IT IS IN THE LEDGER. AS ASKED: the peak rate is
  read outside this package -- :7252 `_oa = _lo + (LR - _lo) * ...` builds the per-expert own-rate
  inside the fabric block, and :6467/:6608/:7148 print "% of peak" -- so under L2 it must arrive at FAB
  as a d_ wire. The receiving end had written its expectation as `d_base_lr` (fabric/levers.py::FABLevers, and
  CENSUS.md:141 on FAB_LR_MAXR) while THIS package's census row asked for `d_lr_peak` (CENSUS.md:388):
  one value, two spellings, and at that moment neither was in spine.assemble.COUPLINGS.
  WHAT IS TRUE NOW: `FAB.d_base_lr` <- `OPT.lr` is a Coupling, and so is `FAB.d_lr_min_frac` <-
  `OPT.lr_min_frac` for the `_lo = LR * LR_MIN_FRAC` half of the same block. THE RECEIVER'S SPELLING
  WON, on the ground that the receiver's `grep d_` is the one that has to find it. `d_lr_peak` is a dead
  spelling: the only four places it survives in src/ are this paragraph, the `lr` row below, the table
  entry below that, and assemble.py's own row prose saying which name it is NOT.
  O4 audits the d_ namespace in BOTH directions, which is what would have caught the other choice, and
  it is why the losing spelling is named here rather than quietly dropped.

  (c) THE HORIZON WIRE THAT WAS CORRECTLY REFUSED -- STILL REFUSED, AND THE SECOND HALF IS NOW REFUSED
  TOO. assemble.py's NOT_WIRES rejects the epoch-to-horizon edge ("it IS the defect ... OPT owns its
  horizon as a declared lever"); it is spelled `RUN.epochs -> OPT.d_lr_horizon` now, not
  `TRAIN.epochs`. `lr_wavelength` below is this package's side of that rejection, and the two documents
  agree. WHAT CHANGED IS THE SENTINEL, AND IT CHANGED INTO ITS OPPOSITE. This paragraph used to end
  "the census says the run length arrives as `d_run_steps` so the sentinel resolves in one visible
  place. That coupling does not exist yet either." IT NEVER WILL. NOT_WIRES gained a row on 2026-09-02
  (Q-OPT-1) refusing "the run length in windows -> OPT.d_run_steps / OPT.d_total_steps", on a ground
  DIFFERENT from the epochs one: the value does not EXIST at freeze, because it is
  len(Segmentation.ids) // LM.ctx times RUN.epochs and Segmentation does not exist until TOK.tokenize
  has run -- many assembly rows after every build() has returned, and a Config that can still be written
  after startup is a Config the report cannot claim the run used. The run length reaches this package as
  the `run_windows` ARGUMENT to OPT.build, and the named computation is spine/compose.py's
  `_run_windows`. A candidate refused with a reason and a candidate that "does not exist yet" are
  OPPOSITE instructions to the next author, which is why this correction is made in the file the next
  author reads and not only in the contract.

THE WIRES: values this package uses or supplies that it must NOT declare. Written down because `grep d_`
is only complete in both directions if the receiving end says what it expects (O4 audits exactly this),
and because lever.py::Lever.__set_name__ refuses a d_-named lever precisely so a declaration cannot shadow the wire
that writes it. THE THIRD COLUMN CARRIED THE BARE PHRASE "NOT IN THE LEDGER" ON THREE OF THESE AND IS
NOW A VERDICT ON EACH, because a value that is not a wire because it is an ARGUMENT is a different fact
from a wire nobody has written, and both were spelled the same way here.
    INCOMING
      d_best_bpb        the best held-out bits/byte so far, from EVAL       (eval/levers.py::<module> declares
                                                                            this outgoing; it is what
                                                                            `lr_restart_damp` judges a
                                                                            cycle by. NOT A WIRE AND
                                                                            NOT MISSING: it arrives as
                                                                            maybe_step's `best_bpb`
                                                                            ARGUMENT -- a runtime
                                                                            measurement can never be a
                                                                            build-time coupling)
      d_shift_at        the step of the last epoch resample, from DATA      (LR_SHIFT_WARM's row. NOT A
                                                                            WIRE, same ground: the
                                                                            composition root supplies
                                                                            maybe_step's `shift_at`,
                                                                            and FAB.grow_check takes
                                                                            the same argument since
                                                                            Q-FAB-6)
      d_run_steps       the run length in steps, for the 0 sentinel         (LR_STEPS's row; see (c).
                                                                            REFUSED, with its own
                                                                            NOT_WIRES row and its own
                                                                            reason -- it arrives as
                                                                            `run_windows`)
    OUTGOING
      d_base_lr               the peak rate, to FAB and to the report       (IN THE LEDGER; `d_lr_peak`
                                                                            is the spelling that lost,
                                                                            see (b))
      d_lr_min_frac           the floor, to FAB's per-expert block          (IN THE LEDGER; LR_MIN_FRAC's
                                                                            row)
      d_effective_batch_windows  batch_windows x accum                      (IN THE LEDGER, and LOCAL to
                                                                            OPT since the (a) repair)
      the three flush cadences FAB and TOK derive from this package's
      batch width through derive.flush_period_windows(Windows(period),
      batch_windows)                                                       (IN THE LEDGER, all three:
                                                                            FAB.d_manage_period,
                                                                            FAB.d_cap_lift_period,
                                                                            TOK.d_cap_lift_period)
THIS LINE SAID "the FOUR flush cadences FAB/TOK/CAP derive through derive.flush_period(Steps(period),
batch_windows)" AND WAS WRONG TWICE. There are THREE, and there have been three in every version of
spine/assemble.py in this repository's history -- checked back to the commit that first wrote the
table, where they sit at :338, :350 and :363. And CAP is not among the destinations at all: CAP is the
SOURCE of the pin threshold (CAP.pin_windows feeds two of the three) and is never a destination, which
is the same fact Q-CLOCK-1 states as "CAP's only outbound edges". The conversion is also no longer
derive.flush_period(Steps(...), ...): the held clock is Windows since Q-DERIVE-1 repair (a), so it is
derive.flush_period_windows, and pin_tick raises UnitError on a Steps or Flushes held value by name.

SEVEN VALUES, SEVEN ANSWERS, and no unanswered case left: FOUR entries are in
spine/assemble.COUPLINGS (d_base_lr, d_lr_min_frac, d_effective_batch_windows, and the flush-cadence
line, which is three rows on its own -- SIX coupling rows behind four table entries, and the two
numbers are different on purpose); TWO are ARGUMENTS, because a runtime measurement can never be a
build-time wire; and ONE is REFUSED with its own NOT_WIRES row. The sentence this paragraph carried --
"a missing wire nobody has written down becomes a direct reach the first time somebody needs the
value" -- was the right warning, and none of the seven is that case any more. What survives of it is
the constraint on `d_best_bpb`: it is a HELD-OUT MEASUREMENT crossing back into a training decision,
PLAN 3.8 forbids a verdict on n=1, and a damped restart is a verdict -- so the Reading that supplies
it must carry its seed count, which is why `best_bpb` is documented as a Reading and not as a float.

WHAT THIS FILE CANNOT EXPRESS, AND WHERE THE OLD GUARDS WENT. Every one of these levers was read in the
old tree through a clamp at the read site -- `max(0, _i("LR_SHIFT_WARM", 0))`, `max(1, _i("BATCH_W", 1))`,
`min(1.0, max(0.0, _f("LR_RESTART_DAMP", 0.5)))` -- and a Lever has no range facility at all: `choices=`
enumerates, it does not bound. Three of those clamps survive elsewhere and one does not, which is worth
knowing before somebody sweeps a value:
    batch_windows = 0   REFUSED, loudly. derive.flush_period raises UnitError ("a flush covers at least
                        one window", derive.py::flush_period).
    accum = 0           SILENTLY CLAMPED to 1 by derive.accum_due (`k = max(1, int(accum))`).
    lr_wavelength < 0   harmless only because the sentinel path treats anything falsy as "one wavelength
                        spans the run"; a negative is not falsy and has no meaning.
    lr_restart_damp>1   NOTHING CATCHES IT, and it inverts the mechanism: the damping multiplies the
                        restart amplitude cumulatively, so a value above 1.0 AMPLIFIES every failed
                        restart instead of shrinking it -- the ratchet the lever exists to stop, driven
                        by the lever that stops it. The old `min(1.0, ...)` at :4739 was the only thing
                        standing there. Whoever writes the schedule owes a startup refusal, in one place.

IMPORT STYLE, AND WHY IT DEPARTS FROM THE ASSIGNMENT'S SKETCH. `from ..spine.lever import ...` cannot
work here: every entry point in this tree puts `src/` ITSELF on sys.path (tests/test_derive.py::<module>,
tests/test_ownership.py's SRC insert, and this file's own verification command), which makes `opt` a
TOP-LEVEL package -- a relative import then raises ImportError, "attempted relative import beyond
top-level package". Absolute it is, matching the eight packages already written.
"""
from spine.lever import Lever, LeverSet
from spine import units as U


class OPTLevers(LeverSet):
    """The schedule and the optimiser: one peak rate, its shape over the run, and the batch it acts on.

    Read `cfg.lr`, never an environment name. Every value here is resolved once by spine.assemble and
    frozen; a function receiving this Config should open with `opt.owned_by("OPT")`, because a Config is
    an ordinary object and a foreign one handed in reads happily and wrongly -- `memory_prune(configs
    ["FAB"])` returning 2048 is the reproduced case behind that method's existence.

    Grouped by the decision each group makes rather than alphabetically, and the grouping is load-bearing
    twice. `lr_sched` decides whether the whole of group 2 and group 3 runs at all (the entire LR block
    at :7093-7154 is inside `if LR_SCHED != "none"`), and `lr_restarts` decides whether `lr_restart_damp`
    and `lr_decay` are reachable BY ARITHMETIC rather than by a flag -- ISSUES.md PART 4's [chat-b/carry_forward]
    entry files that exact pair as the canonical "off by arithmetic, not armed and inert" case. In the old tree those two facts
    were spread across :4716, :6290 and :4777-4786 with nothing anywhere saying they were one decision.
    """

    PREFIX = "OPT"

    # ==============================================================================================
    # 1. THE ONE ABSOLUTE SCALE
    #
    # Two numbers handed straight to both AdamW instances at :4748/:4750. Everything in groups 2-4 is a
    # multiplier in 0..1 applied to the first of them, so a reader who wants to know what rate a run
    # actually used needs this number and one fraction, never a chain.
    # ==============================================================================================

    lr = Lever(2e-3, "Peak learning rate; every rate the system applies is this times a schedule "
                     "multiplier in 0..1.", U.FRACTION)
    # Census: LR -> OPT_LR, verdict keep, default 2e-3 (CENSUS.md:388). Field corrected from `OPT_LR` to
    # `lr` (DEFECT 1); the env name is OPT_LR either way, which is what the census meant.
    # UNIT IS A KNOWN MISLABEL AND THE CENSUS SAYS SO IN AS MANY WORDS. units.py has no RATE or SCALAR
    # metadata constant, and none of BYTES/TOKENS/COUNT/FRACTION honestly names a learning rate: 2e-3 is
    # not a fraction OF anything. U.FRACTION is the least-wrong existing label. Adding U.RATE is a SPINE
    # edit and this file has no standing to make one -- the same ruling domains/levers.py and lm's
    # `anchor_uses` reached for the same reason. The mislabel is harmless in a way the clock kinds are
    # not: metadata is never enforced (units.py section 1), so the only cost is one wrong word in
    # docs/04_LEVERS.md, and it is recorded here so that word is not read as a claim.
    # READ AT :4716, and the value is load-bearing three ways: it is `lr=` on both AdamW instances
    # (:4748 the base, :4750 the encoder), it multiplies every schedule fraction (:4759, :4849), and it
    # is the bar the restart detector uses (`_lrv > 0.5 * LR`, :7118).
    # IT IS ALSO READ OUTSIDE THIS PACKAGE, WHICH IS THE L2 VIOLATION TO CARRY OVER AS A WIRE: :7252
    # builds the per-expert own-rate as `_oa = _lo + (LR - _lo) * ...` inside the fabric block, and
    # :6467/:6608/:7148 print "% of peak" in the report. Those are declared wires now, not a global read,
    # and the name that landed is `d_base_lr` -- the RECEIVER's spelling, not this package's `d_lr_peak`
    # (see conflict (b)). This comment said "until the coupling exists, FAB_LR_OWN=1 has no legal way to
    # learn this number"; the coupling EXISTS, `FAB.d_base_lr <- OPT.lr`, and FAB_LR_OWN=1 has its legal
    # way. Corrected 2026-09-03.
    # THE DEFAULT IS THE HYPOTHESIS UNDER TEST, not a tuned value: a constant 2e-3 on AdamW for 48k steps
    # is the shape all 17 pilots showed (bottom ~2.4 at step 6000, rise to 3.8-4.1 by 48,000). It stays
    # at 2e-3 because that is the literal every existing record was measured under, and a default that
    # quietly differs from the measured one makes the whole record unattributable.

    weight_decay = Lever(0.0, "AdamW decoupled weight decay, applied to the base optimizer and the "
                              "encoder optimizer alike.", U.FRACTION)
    # Census: WEIGHT_DECAY -> OPT_WEIGHT_DECAY, verdict keep, default 0.0 (CENSUS.md:396). Field
    # corrected from `OPT_WEIGHT_DECAY` to `weight_decay` (DEFECT 1).
    # A GOAL-B LEVER, AND THE ARGUMENT IS CARRIED VERBATIM RATHER THAN RE-DERIVED. so-model.json records
    # it as "an uncontrolled forgetting term applied to dormant experts", and the source states the
    # measurement at :4326-4328: decoupled decay is applied EVERY step to EVERY parameter regardless of
    # gradient, so a dormant expert loses ~71% of its magnitude over a 62.5k-step run. That is
    # catastrophic forgetting introduced by the OPTIMISER, orthogonal to anything the fabric or the
    # memory does -- an expert the router is not selecting is being erased by a mechanism that never
    # looked at it.
    # THE DEFAULT EXISTS TO MAKE THAT EXPLICIT, WHICH IS WHY 0.0 IS NOT THE SAME AS NOT HAVING THE LEVER.
    # AdamW's own default is 0.01, so before this knob existed the run WAS decaying dormant experts and
    # nobody had chosen it (:4326, "was implicit ... Now explicit; 0 disables it").
    # KEPT RATHER THAN DROPPED because it is the standard remedy the moment the model stops being
    # underfit, and the report tells the operator to reach for it by name: "gap > ~0.5 = MEMORIZING, now
    # turn on DROPOUT=0.1-0.2 and WEIGHT_DECAY=0.01" (:7990). A knob the report instructs the operator to
    # set is not a candidate for removal.
    # ITS ONE MEASURED INTERACTION BELONGS IN THE ARM TABLE: at :6429 the six-arm pilot has five of six
    # arms ending at +0.000 since their own minimum, and the single exception is DROPOUT+WEIGHT_DECAY
    # together, which still diverges (+1.216). DROPOUT is LM's lever (it is a layer in the model,
    # constructed at :1550-1551), so this pair is a two-package interaction and cannot be seen from
    # either file alone.
    # READ AT :1420, ALIASED TO `WD` AT :4329 and passed to both AdamW instances. The alias is exactly
    # the shape L1 removes: one number, two names, and the audit could see only the first.

    grad_clip = Lever(0.0, "Global gradient-norm clip applied to the BASE parameter group before "
                           "each optimizer step. 0.0 is OFF, which is what every recorded number "
                           "in this project was measured under.", U.FRACTION)
    # CENSUS AMENDMENT, 2026-09-02, AND IT IS THE ONLY ONE IN THIS FILE. There is no old-tree knob
    # behind this lever: `grep -c clip self_organize.py` returns 2 and both are prose about the
    # forgetting measure F (:920, :5203). Across self_organize.py, memory.py, tokenizer.py,
    # vocab.py, datastream.py and world_model.py there is no clip_grad_norm_, no clip_grad_value_
    # and no manual norm clamp. So this knob has NO CENSUS ANCESTOR, there is no (family, old_name)
    # key a DEPARTURES entry could be written under, and N2 would report it as a lever whose reason
    # for existing is written nowhere. It is accounted for by an AMENDMENTS group in
    # .rework/census.json and a matching section in .rework/CENSUS.md -- which is the ONLY legal way
    # to add a genuinely new lever here, and it is an owner-visible act, not a package edit. The 328
    # figure the census claims is UNCHANGED: an amendment is not a knob the old tree had.
    # WHY IT EXISTS AT ALL, stated as the question it keeps open rather than as a preference. OPT is
    # the leading standing hypothesis for GOAL A: all 17 pilots bottom at ~2.4 bits/byte around step
    # 6000 and rise to 3.8-4.1 by 48,000, across every arm, so the cause is common to all of them.
    # The header names TWO unmeasured explanations for that shape -- a constant 2e-3 on AdamW for
    # 48k steps, which lr_sched="none" ablates in one flag, and gradients large enough that the
    # steps overshoot, which NOTHING in this tree could ablate because there was no clip anywhere.
    # One hypothesis had a switch and the other did not, which is not a fair comparison; this is the
    # second switch. The literature is unambiguous that global-norm clipping at max_norm=1.0 is the
    # near-universal default in transformer/LM recipes (HuggingFace Transformers, PyTorch Lightning,
    # DeepSpeed all default to it; clip-by-norm is preferred over clip-by-value because it preserves
    # direction and rescales magnitude only).
    # THE DEFAULT IS 0.0 = OFF AND THAT IS DELIBERATE, NOT TIMID. Turning the standard remedy on by
    # default would take every future number under a different confound and would replace, rather
    # than remove, the confound this question exists to disentangle -- and it would silently move
    # every recorded result off its measured configuration. Off costs nothing and keeps both arms
    # reachable from the environment, which is what makes this a MEASURABLE question rather than a
    # decided one. docs/04_CONTRACT.md, Q-OPT-3, states the run that retires it.
    # IT IS NOT ARMED-BUT-INERT PADDING, and the difference is checkable. It has a reader
    # (OPT.maybe_step, step 5, between the gradient's last use and the zero_grad), a stated default,
    # its own DID IT FIRE counters (opt.clip.applied against opt.clip.armed_no_clip -- clipping on
    # and NOTHING exceeded the norm is a different statement from clipping off, and the report must
    # make both), a startup refusal on a negative max-norm, and a Gate on OPT.build that prints
    # "off (0.0)" rather than omitting the line.
    # SCOPE IS THE BASE GROUP, FOR THE SAME REASON THE NORM MEASUREMENT IS. The encoder's gradients
    # at flush time are SIG's, produced on SIG's cadence and stepped by SIG (Q-OPT-6), so folding
    # them into one clipped norm would silently couple two schedules.
    # UNIT IS THE SAME KNOWN MISLABEL AS `lr`, and for the same reason: units.py has no RATE or
    # MAGNITUDE constant, a max-norm is not a fraction OF anything, and adding one is a SPINE edit
    # this file has no standing to make. Recorded here so the word is not read as a claim.

    # ==============================================================================================
    # 2. THE SHAPE OF THE RATE OVER TIME
    #
    # `_lr_at(st, total, _run_end)` is a pure function of the step number and these four levers, and
    # keeping it pure is the point: the old version reached out of itself for `_shift_at` and for the
    # projection state, which is how the schedule acquired a dependency on the DATA package's resample
    # branch. All four horizons are Steps -- see DEFECT 2(a) in the header for why that survives the
    # fact that the counter passed in today is a window counter.
    # ==============================================================================================

    lr_sched = Lever("cosine", "Selects the rate schedule: the warmup-then-cosine shape, or a constant "
                               "peak rate for the whole run.",
                     U.NAME, choices=("cosine", "none"))
    # Census: LR_SCHED -> OPT_LR_SCHED, verdict keep, default "cosine" (CENSUS.md:393). Field corrected
    # from `OPT_LR_SCHED` to `lr_sched` (DEFECT 1).
    # choices= IS THE REPAIR, AND THIS IS ONE OF THE ELEVEN THE SURVEY FOUND. ISSUES.md M24 (:361) names
    # LR_SCHED in the list of string knobs compared case-sensitively with no normalisation and no
    # refusal -- "an unrecognised value falls into whichever branch is the else, rather than being
    # refused". `if LR_SCHED == "none": return LR` at :4752 means LR_SCHED=None, =NONE, =off and =nome
    # all run the FULL COSINE while the banner echoes the string the operator typed. With choices= that
    # is a startup LeverError naming both legal values, before a single tensor is allocated.
    # WHY IT IS KEPT AT ALL, when a schedule selector with two values looks like a flag: it is the
    # ablation for the one hypothesis that explains ALL 17 pilots -- every arm bottoming at ~2.4 b/B
    # around step 6000 and rising to 3.8-4.1 by 48,000, across GRU, transformer, fabric and FABRIC=0
    # (:7003-7011). A cause common to all of them cannot be the fabric. "none" restores the pre-schedule
    # behaviour EXACTLY, which is the property that makes it an ablation rather than another arm.
    # IT IS A GATE OVER GROUPS 2 AND 3, NOT A SETTING (G4). The whole LR application block at :7093-7154
    # is inside `if LR_SCHED != "none"`, so at "none" the warmup, the wavelength, the floor, the
    # restarts, the damping, the envelope and the re-warm are ALL structurally unreachable -- eight
    # levers inert, and the old tree printed every one of them on the EFFECTIVE line as though it had
    # applied. The gate must print its own predicate.
    # AND IT CARRIES AN UNFIXED CRASH THAT THE PORT MUST NOT INHERIT (ISSUES.md PART 1, H15). LR_SCHED="none"
    # together with FAB_LR_OWN=1 leaves `_lrv` unbound and dies with a NameError on the FIRST FLUSH: the
    # per-expert path at :7194 reads a variable that is only assigned inside this branch. That is the
    # foreign read L2 forbids, in its most literal form -- one package reading another's local. Under the
    # spine the rate reaches FAB as a wire (conflict (b)), which makes the crash unspellable rather than
    # merely fixed.

    lr_warmup = Lever(1000, "Linear ramp from zero to the peak rate at the start of a run, paid once.",
                      U.Steps)
    # Census: LR_WARMUP -> OPT_LR_WARMUP, verdict keep, default 1000 (CENSUS.md:395). Field corrected
    # from `OPT_LR_WARMUP` to `lr_warmup` (DEFECT 1).
    # THE CLAMP IS A DEFECT FIX AND MUST SURVIVE THE PORT: `_w = min(LR_WARMUP, max(1, total // 10))` at
    # :4756-4759. At LR_WARMUP=1000 a 360-step run NEVER LEAVES WARMUP and trains at a third of peak
    # throughout -- which reads as the schedule hurting when it is the schedule never having run. The
    # clamp belongs to the consumer, not to this declaration: a Lever cannot express "at most a tenth of
    # a horizon it does not own", and writing it as a smaller default would break every long run to fix
    # a short one.
    # PAID ONCE, NOT PER CYCLE, and that is a property of warmup rather than a saving: the point of
    # warmup is that the optimizer state is COLD, which is only true the first time (:4762-4765). A
    # restart therefore returns to peak in ONE step by design, which is exactly why group 3 exists.
    # IT IS ALSO WHY THE RESTART DETECTOR NEEDS ITS SECOND CONDITION. The ramp climbs from zero, so every
    # early step multiplies the previous rate by far more than 1.5 and each one was logged as a "cosine
    # restart" -- observed at steps 15 and 31 of an 18-epoch run, at 2% and 3% of peak. The `_lrv > 0.5 *
    # LR` bar at :7118 is what removes them, and a log that cries restart is a log nobody greps for
    # restarts.
    # UNIT: Steps, and the consumption defect is real -- see DEFECT 2(a). Today `_lr_at` is handed `step`,
    # a WINDOW counter, so this warmup completes batch_windows times sooner than it is written. The port
    # converts through spine.derive; it does not re-label the lever, because a warmup denominated in
    # windows would change length when the batch size changed.

    lr_wavelength = Lever(0, "Length of one cosine cycle, stated directly in optimizer steps; 0 means "
                             "one wavelength spans the whole run.", U.Steps)
    # Census: LR_STEPS -> OPT_LR_WAVELENGTH, verdict RENAME, default 0 (CENSUS.md:403), ABSORBING the
    # LR_EPOCHS row (verdict merge, default 8, CENSUS.md:397). Field corrected from `OPT_LR_WAVELENGTH`
    # to `lr_wavelength` (DEFECT 1).
    # THE RENAME IS THE HALF OF THE FIX THAT THE MERGE CANNOT DO. "LR_STEPS" reads as a count of steps
    # TAKEN rather than as a PERIOD, and that misreading survived three rounds of the same failure while
    # the file shouted "WAVELENGTH" in capitals at :278 and :4722. A name that has to be corrected in
    # every comment that uses it is the wrong name.
    # WHY THE EPOCH SPELLING DIED, AND WHY THE MERGE IS FORCED RATHER THAN CHOSEN. units.Epochs rules
    # that an epoch is "never a schedule horizon", because EPOCHS setting both the run length and the
    # cosine horizon makes two runs differing only in EPOCHS two different learning-rate experiments.
    # The source agrees with itself at :4718-4722 -- "AN EPOCH IS NOT A UNIT OF ANYTHING" -- and gives
    # the number: LR_EPOCHS=8 has meant 48,000 steps at STREAM_LEN=4e6 and 840,000 at 94e6, a 17x range
    # under one number. It also deletes the whole `_lr_total`/`_proj_lr`/`_project` projection machinery
    # at :6335-6376, which existed ONLY to convert this knob and had already been rewritten once for the
    # same fault -- taking two live consequences with it: the cosine reaching only p=0.760 on E8 and
    # p=0.730 on E18 because the projected horizon overran the run (:6248-6250), and the report's own
    # note that a run stretched by EPOCHS is "NOT comparable at fixed LR" (:6020).
    # THE 0 SENTINEL IS DOCUMENTED, NOT RESOLVED HERE, and that is deliberate. In the old tree the zero
    # was resolved by READING ANOTHER KNOB (`if LR_STEPS: return LR_STEPS`, else project from LR_EPOCHS,
    # :6371) -- which is the computed default lever.py::Lever.__init__ refuses by construction. The run length
    # arrives as `d_run_steps` so the sentinel resolves in ONE visible place -- AND THAT WIRE IS REFUSED,
    # not merely unwritten. This comment said "that coupling does not exist yet (see conflict (c)), so
    # until it does, whoever builds the schedule must resolve the zero at the single point it is read",
    # which told the next author to WAIT for an edge the tree has since rejected by name: NOT_WIRES
    # carries "the run length in windows -> OPT.d_run_steps / OPT.d_total_steps" as of 2026-09-02
    # (Q-OPT-1), because the value does not exist until TOK.tokenize has run and build() has long since
    # frozen. So the single visible place is REAL and it is not a wire: OPT.build resolves the sentinel
    # from its `run_windows` ARGUMENT, once, and puts the resolved number in the banner
    # (opt.build.wavelength_from_sentinel is the counter that says it happened).
    # WHY A SENTINEL RATHER THAN A SECOND LEVER: `choices=` cannot express "0, or any positive int", and
    # a second lever holding the "spans the run" state would be minting a knob the census never voted on
    # -- the same limit lm/levers.py:`layers`, domains/levers.py::DOMLevers and tok/levers.py all record.
    # REAL SETTINGS ON RECORD, so nobody has to re-find them: 280000 for round16, 260000 for
    # lr_075_short, 90000 for lr_075_rst.

    lr_min_frac = Lever(0.05, "Floor of the cosine as a fraction of peak -- the schedule never returns "
                              "zero.", U.FRACTION)
    # Census: LR_MIN_FRAC -> OPT_LR_MIN_FRAC, verdict keep, default 0.05 (CENSUS.md:390). Field corrected
    # from `OPT_LR_MIN_FRAC` to `lr_min_frac` (DEFECT 1).
    # ON GOAL B DIRECTLY, AND THE SOURCE STATES IT AT THE FUNCTION THAT USES IT (:4752): "this is a
    # continual-learning system and a schedule that anneals to nothing cannot learn anything that arrives
    # late". The add-area entry point IS the late-arrival case, so a floor of zero would make this
    # project's headline capability unreachable by arithmetic.
    # ONE NUMBER, FOUR USES, WHICH IS WHY IT MUST NOT BE RESTATED: the cosine floor (:4793), the floor of
    # the restart damping (:4813), the floor of the shift re-warm (:4820) and the floor of the LR_DECAY
    # envelope (:4847). A second literal at any one of those four is a schedule with two floors.
    # THE COMPOUNDING DEFECT IS A TEST TO WRITE, NOT PROSE TO REPEAT. The envelope at :4847 multiplies
    # `_cyc` -- which ALREADY contains this floor -- by a second cosine that also bottoms at this floor,
    # so before the `_n > 1` gate a run that should end at lr_min_frac ended at lr_min_frac SQUARED:
    # 0.0025 of peak, annealed to nothing well before the finish. The property to assert is that the
    # schedule's minimum over a whole run equals lr * lr_min_frac at every restart count, single-cycle
    # included.
    # ALSO READ OUTSIDE THIS PACKAGE: :7251 `_lo = LR * LR_MIN_FRAC` in the per-expert block. That is a
    # wire (`d_lr_min_frac`) under L2, not a global -- see conflict (b), which the peak rate shares.

    # ==============================================================================================
    # 3. RESTARTS, AND THE ONLY CLOSED LOOP IN THE SCHEDULE
    #
    # `lr_restarts` is a GATE over the other two (G4), not a setting beside them: at 0 the code forces
    # `_p = min(1.0, _prog); _n, _ci = 1, 0` (:4787), which makes BOTH `lr_restart_damp` and `lr_decay`
    # unreachable BY ARITHMETIC. ISSUES.md PART 4's [chat-b/carry_forward] entry files exactly this pair as the
    # canonical "off by arithmetic, not armed and inert" case, and PART 3's C12 is why it matters: commit b990c9d fixed
    # a restart failure by setting LR_RESTARTS=0 and 704c432, one commit later, added damping to fix the
    # same failure -- while the armed-and-inert audit had 20 rows and not one about the learning rate,
    # the part of the system that has broken the most runs.
    # ==============================================================================================

    lr_restarts = Lever(True, "Whether the cosine wraps into repeated warm restarts, with a whole number "
                              "of cycles fitted to the run, instead of holding at the floor.", U.FLAG)
    # Census: LR_RESTARTS -> OPT_LR_RESTARTS, verdict keep, default 1, unit on/off (CENSUS.md:391). Field
    # corrected from `OPT_LR_RESTARTS` to `lr_restarts` (DEFECT 1).
    # DECLARED True AND NOT 1, AND THE OLD SOURCE AGREES: :6290 reads `LR_RESTARTS = bool(_i("LR_RESTARTS",
    # 1))`, so the int in _SPEC was already a boolean by the time anything used it. Lever.coerce picks its
    # branch from the DEFAULT's type (lever.py::Lever.coerce), so declaring True is what makes OPT_LR_RESTARTS=off
    # mean off; an int default would raise on "off". The bool branch's own hazard is stated in
    # fabric/levers.py and applies here unchanged -- any string outside ("0","","off","no","none","false")
    # reads as True, so OPT_LR_RESTARTS=flase is silently ON. It also means OPT_LR_RESTARTS=3 does not
    # mean three restarts; the cycle COUNT is fitted, never set (see below), and 3 is simply True.
    # WHAT "ARMED" MEANS HERE IS NOT THIS LEVER, and the source says so in a comment on the counter it
    # keeps: `_ncyc = [1]  # cycles that FIT the run -- "armed" for a restart means >1, not LR_RESTARTS=1`
    # (:4746). A single-cycle run with this switched ON restarts nothing. Every result this project has
    # recorded came from such a run, which is why the two levers below have never fired in anger.
    # THE CYCLE-FITTING AT :4777-4786 IS WORTH KEEPING INTACT, and it is not an optimisation: rounding to
    # a whole number of cycles and stretching the period to divide the run exactly means every cycle
    # completes and the run always ENDS annealed. Truncating instead left a 30-epoch run with 2 cycles
    # and a THIRD of its length parked at the floor -- the same wasted tail restarts exist to remove. The
    # period moves by at most ~1/(2n) from nominal, a few percent, against the 11x that EPOCHS-stretching
    # caused.
    # AT EPOCHS == ONE WAVELENGTH THE SCHEDULE IS BIT-IDENTICAL TO restarts=off (:4785), which is the
    # property that keeps every earlier result reproducible under the new default.

    lr_restart_damp = Lever(0.5, "Multiplier on the next restart's swing when the cycle that just ended "
                                 "failed to beat the best held-out it inherited; cumulative.",
                            U.FRACTION)
    # Census: LR_RESTART_DAMP -> OPT_LR_RESTART_DAMP, verdict keep, default 0.5 (CENSUS.md:392). Field
    # corrected from `OPT_LR_RESTART_DAMP` to `lr_restart_damp` (DEFECT 1).
    # THE ONLY CLOSED-LOOP ELEMENT IN THE ENTIRE SCHEDULE, and the defect it answers is measured rather
    # than hypothetical. A warm restart is a BET: give up the current anneal, explore, re-anneal into
    # something at least as good. On the 0.75 GB run that bet lost three times in a row and the schedule
    # took it again each time AT FULL AMPLITUDE, because nothing connected the rate to the objective --
    #     best 2.030 @ step 252,000; restarts at 263,965 / 504,894 / 756,851; final 2.848
    #     before r1  2.03 2.03   after  2.18 2.26 2.31
    #     before r2  2.10 2.10   after  3.59 3.12 3.06
    #     before r3  2.20 2.20   after  2.37 2.29 2.46
    # -- 81% of the run spent getting worse. A losing bet re-taken identically is not a schedule, it is a
    # ratchet. Cumulative damping means a schedule whose restarts keep failing anneals ITSELF off within
    # two or three of them, while one whose restarts genuinely help is untouched.
    # NEVER FIRED IN ANY SHIPPED ARM, AND THAT IS THE PROTECTED CASE, not evidence against it:
    # LR_RESTART_DAMP= appears 0 times in longrun.sh, and it is unreachable on a single-cycle schedule BY
    # ARITHMETIC (`_ci > 0`, :4812) -- every recorded result came from one. The owner's ruling is explicit
    # that a mechanism never observed to fire is not thereby proven useless, and this is the case it was
    # written for.
    # PORT REQUIREMENT, AND IT IS THE MOST IMPORTANT LINE IN THIS FILE. This lever reads `_best_bpb` --
    # a HELD-OUT MEASUREMENT -- and turns it into a training decision (:7137-7139). That is a number
    # crossing the instrument line BACKWARDS. It must arrive as the declared wire `d_best_bpb` from EVAL
    # (eval/levers.py::<module> already declares the outgoing half), and the Reading it comes from must carry
    # its seed count, because PLAN 3.8 forbids a verdict on n=1 and a damped restart IS a verdict.
    # NO RANGE GUARD SURVIVES THE PORT. The old read was `min(1.0, max(0.0, _f(...)))` at :4739; a Lever
    # has no bounds, so OPT_LR_RESTART_DAMP=1.5 now AMPLIFIES each failed restart cumulatively -- see the
    # header's guard table.

    lr_decay = Lever(1.0, "Strength of a monotone envelope over successive restart peaks, so each cycle "
                          "keeps its own high phase while the ceiling comes down.", U.FRACTION)
    # Census: LR_DECAY -> OPT_LR_DECAY, verdict keep, default 1.0 (CENSUS.md:389). Field corrected from
    # `OPT_LR_DECAY` to `lr_decay` (DEFECT 1).
    # ITS FAMILY TAG HAD ALREADY DRIFTED, which is the whole reason the ownership spine exists: _SPEC
    # tags it `# lr` at :377, and `lr` is not one of the twelve families. It is an optim knob whose
    # comment wandered, and under a generated env name that is unspellable.
    # THE MEASURED FAILURE IT ANSWERS: a repeating cosine returns to 100% OF PEAK at every restart,
    # forever. On an 18-epoch run, `[lr @ 201925] cosine restart: 1.00e-04 -> 2.00e-03 (100% of peak)`,
    # after which held-out swings 1.5 b/B and never resettles -- two of three seeds ending at 5.6 and 5.3
    # base model, and the one that landed away from a restart reading 3.0. That spread IS the arm. A
    # full-peak jump late in training is not a fresh exploration phase, it is discarding the anneal that
    # earned the current solution.
    # GATED ON `_n > 1` (:4845), AND THE GATE IS THE REASON IT CAN DEFAULT ON. Written without it, the
    # envelope multiplied a single cycle's cosine by a second cosine and squeezed the run to lr_min_frac
    # SQUARED -- which is why it sat at 0.0 from the day it was written. Gated, it is a no-op for every
    # single-cycle schedule, i.e. for every result this project has recorded, and active precisely where
    # the damage happens.
    # THE DEFAULT FLIPPED 0.0 -> 1.0 ON 2026-08-26 AND THREE DOCUMENTS STILL SAY IT IS INERT (ISSUES.md
    # H2:1133, L15:1331, 07_WIP:146). That whole class of fault dies with the declaration rather than
    # with an edit: docs/04_LEVERS.md reads the default off the registry instead of retyping it, so a
    # document cannot disagree with the value the run used.
    # NOT A FLAG DESPITE READING LIKE ONE: 0.0 restores the pre-2026-08-26 behaviour exactly (restarts
    # return to full peak) and 1.0 makes the envelope fall on the same cosine shape a single cycle would,
    # so the last cycle peaks near the floor and the run ends annealed twice over. The values between are
    # meaningful, so `choices=` would be wrong here.

    # ==============================================================================================
    # 4. THE SHIFT WE CAUSE OURSELVES
    #
    # One lever, and the one most directly on goal B. Its whole job is to make the SCHEDULE aware of
    # something the growth controller already knows.
    # ==============================================================================================

    lr_shift_warm = Lever(0, "Re-warm length after a distribution shift the system caused itself, "
                             "applied as an attenuation of the current cycle.", U.Steps)
    # Census: LR_SHIFT_WARM -> OPT_LR_SHIFT_WARM, verdict keep, default 0 (CENSUS.md:394). Field
    # corrected from `OPT_LR_SHIFT_WARM` to `lr_shift_warm` (DEFECT 1).
    # THE ASYMMETRY IT REPAIRS, STATED AS THE SOURCE STATES IT (:4726-4732): `note_shift()` already tells
    # growth "this jump is OURS, not the data's" for a retok and for an epoch resample -- but the LEARNING
    # RATE meets the same fresh text at whatever the cosine says, which has been 96-99% of peak at the
    # second boundary in EVERY run measured. Both round12 and round13 were destabilised there; the one
    # whose rate then fell quickly recovered, the one held near peak did not (ISSUES.md PART 3, H12).
    # AN ATTENUATION, NEVER A REPLACEMENT, and the sign is the design (:4814-4820). Returning `LR * ramp`
    # would RAISE the rate whenever a shift lands late in the anneal -- a schedule that steps back up
    # mid-run, which is what the monotone-progress clamp exists to prevent. It MULTIPLIES, so it can only
    # ever lower the rate, and rejoins the cycle exactly where the cycle would have been.
    # KEPT ON THE OWNER'S RULING, AND THIS IS THE CASE THAT RULING PROTECTS. It has never been on by
    # default and chat-b records it as tried and not helping -- "none of round15's worst excursions were
    # resample-aligned" -- but that is a measurement of WHERE ROUND15'S INSTABILITY WAS, not of the
    # mechanism. Dropping for "never observed to fire" was forbidden; the defect it exists for is
    # measured independently.
    # IT IS THE ADD-AREA LEVER. P7's entry point creates exactly the boundary this attenuates: an added
    # area IS a self-inflicted distribution shift, which makes this the schedule's contribution to goal B
    # rather than to convergence.
    # THE TRIGGER IS NOT A WIRE, AND THAT IS THE ANSWER RATHER THAN A GAP. The old code reaches into
    # DATA -- the DISK_STREAM epoch-resample branch writes `_shift_at` (:6518-6521), which `_lr_at` then
    # reads as a CLOSURE VARIABLE. Under L2 the schedule must stay a pure function of the value, and
    # this comment used to say the value "arrives as `d_shift_at`" and that "that coupling is NOT IN THE
    # LEDGER, so today this lever has nothing to fire on". BOTH HALVES ARE WRONG NOW AND THE SECOND WAS
    # ALWAYS THE WRONG SHAPE: the step of the last self-inflicted shift is a RUNTIME event, so it can
    # never be a build-time Coupling -- the same ground that refuses d_run_steps and the SIG width. It
    # arrives as `shift_at`, a declared keyword on OPT.maybe_step's frozen signature, stamped by the
    # composition root at the epoch-resample / retok / add-area events, and FAB.grow_check takes the same
    # event as its own `shift_at` (Q-FAB-6). So the lever HAS something to fire on. What it still needs
    # is the report line that separates the two zero-cases, and maybe_step declares it:
    # `opt.shift.notifications` at 0 means NOBODY IS SUPPLYING shift_at, which is a different statement
    # from lr_shift_warm == 0, and the report must make both. Corrected 2026-09-03.

    # ==============================================================================================
    # 5. WHAT ONE OPTIMIZER STEP IS TAKEN OVER
    #
    # Two counts whose product is the effective batch. They are declared last and together because they
    # are the two ends of one number, and because the effective batch must be a d_-prefixed derived field
    # (G5) rather than arithmetic repeated at the call sites -- the old tree reported the CONFIGURED
    # batch while training at a quarter of it.
    # See conflict (a) in the header: spine/assemble.py reads both of these off a package called TRAIN.
    # ==============================================================================================

    batch_windows = Lever(1, "How many stream windows are accumulated into one forward/backward; this "
                             "sets the flush cadence the whole loop body runs on.", U.Windows)
    # Census: BATCH_W -> OPT_BATCH_WINDOWS, verdict RENAME, default 1 (CENSUS.md:401). Field corrected
    # from `OPT_BATCH_WINDOWS` to `batch_windows` (DEFECT 1).
    # THE RENAME IS THE FIX, NOT DECORATION. The bare "W" is what let it be read as a batch of anything;
    # it is a count of WINDOWS, and units.py exists because `step` advances per window while the loop
    # body runs per flush -- the project's single most repeated defect, cited in that module's docstring.
    # ITS BLAST RADIUS IS WHY IT IS DECLARED AT ALL RATHER THAN LEFT AS A LOOP LOCAL. Every one of these
    # is a Windows-against-Flushes comparison that Clock now raises on:
    #   * the capacity valve's pin clock read 2,650 against 43,645 real steps at BATCH_W=16 -- 16x slow,
    #     and the valve reported "reached the cap but never held it long enough", a true sentence about
    #     a false clock (ISSUES.md C3:1355);
    #   * GROW_CAP_EVERY=20000 silently meant 320,000 steps at BATCH_W=16 and 640,000 at 32 (:940), so a
    #     knob's meaning depended on the batch size;
    #   * `step % MANAGE_EVERY == 0` fired for 4 of 16 flush residues and zero for the other 12
    #     (:6829-6830);
    #   * at BATCH_W=4 with MANAGE_EVERY=20 the intersection is EMPTY, so _greach, ROUTING MIX, CHAIN
    #     ORDER and maybe_deepen never ran AT ALL (ISSUES.md PART 3, C42).
    # THE CONVERSION HAS ONE HOME: derive.flush_period(Steps(period), batch_windows), never
    # `// max(1, BATCH_W)` written inline at eight call sites (:6795, 6819, 6836, 6961, 6988, 7077, 7325,
    # 7368). That function also carries the surviving guard: batch_windows < 1 raises UnitError, so the
    # old `max(1, _i("BATCH_W", 1))` at :4193 does not need a home here.
    # UNIT: Windows, per the census, with the ratio-versus-clock tension recorded in DEFECT 2(b) of the
    # header. The resolved value is a bare int -- the unit is metadata -- so the `int(batch_w)` inside
    # flush_period is unaffected either way.
    # THE ACCUMULATOR ITSELF IS AT :6795-6799 (`if len(_bx) < BATCH_W: i += WIN; step += 1; continue`),
    # and that single line is where the two clocks separate: `step` advances on EVERY window, the body
    # below runs only when the batch is full. Domain assembly and memory stay per-window and sequential,
    # so stream semantics are preserved; this only removes the batch-1 throughput ceiling.

    accum = Lever(1, "Backward passes accumulated before one optimizer step -- with batch_windows, the "
                     "effective batch, and the only way to reach a large one on a small GPU.",
                  U.Backwards)
    # Census: ACCUM -> OPT_ACCUM, verdict keep, default 1 (CENSUS.md:387). Field corrected from
    # `OPT_ACCUM` to `accum` (DEFECT 1).
    # THIS LEVER IS WHY units.py HAS A Backwards CLOCK AT ALL -- that class's docstring cites ACCUM by
    # name. The measurement to preserve as a test: the gate was `(step + 1) % ACCUM == 0`, keyed on the
    # WINDOW counter while the body ran per flush, so it accumulated NOTHING at any value -- 55 om.step()
    # calls against 13 due, over ~52 backward passes at BATCH_W=4 ACCUM=4 (ISSUES.md H29:1646). The
    # repaired form is `if _nbwd % ACCUM == 0` at :7193, i.e. count the thing the decision is about, and
    # derive.accum_due is the one place it lives now -- it REFUSES anything but a Backwards clock for the
    # counter, so the window counter cannot be handed to it a second time.
    # IT WAS HARMLESS ONLY BY DEFAULT, WHICH IS THE WORST KIND OF HARMLESS. The default is 1 and
    # longrun.sh never sets it -- but fetch_big.py prints `WIN=256 BATCH_W=16 ACCUM=4 D_MODEL=768
    # VMAX=16384` as the RECOMMENDED heavy-run command and bench_gpu.sh ships ACCUM=2, while ACCUM
    # appeared in no print anywhere. The next GB run launched the way the repo says to launch it would
    # have failed in silence. Two obligations follow and neither is discharged by this declaration: it
    # needs a DID IT FIRE row, and the effective batch must be a d_-prefixed derived field (G5).
    # THE REMAINING GUARD LIVES IN derive.accum_due AND IT IS SILENT: `k = max(1, int(accum))`, so
    # OPT_ACCUM=0 is clamped to 1 with no message where the old `max(1, _i("ACCUM", 1))` at :4198 was
    # equally quiet. Unlike batch_windows=0, which raises, this one still hides a typo.
    # THE LOSS SCALING IS THE OTHER HALF AND IT IS NOT OPTIONAL: `(tot / ACCUM).backward()` at :7065. An
    # accumulation that gates the step without scaling the loss trains at ACCUM times the rate the
    # operator asked for, which is the same defect class as the gate itself and would be invisible in
    # exactly the same way.

    # ==============================================================================================
    # WHAT IS DELIBERATELY ABSENT, one line each, because a reader who finds them missing will otherwise
    # go looking for a mistake. Full reasons are in the header.
    #
    #   RECON_W          dropped (CENSUS.md:241). A loss-term weight for a mechanism being removed; it
    #                    trained on a churning store and reached 0.3% precision. EVAL's post-hoc
    #                    verify_fit_steps is the repair that shipped.
    #   LR_EPOCHS        merged into `lr_wavelength` (CENSUS.md:397). An epoch is never a schedule
    #                    horizon; the same "8" meant 48,000 steps and 840,000 steps.
    #   d_best_bpb       incoming wire from EVAL, not a lever -- lr_restart_damp's input.
    #   d_shift_at       incoming wire from DATA, not a lever -- lr_shift_warm's trigger.
    #   d_run_steps      incoming wire, not a lever -- what lr_wavelength's 0 sentinel resolves against.
    #   d_effective_batch_windows   batch_windows x accum, a derived field (G5); assemble.py::COUPLINGS declares
    #                    it today as local to a package called TRAIN.
    #   DROPOUT          LM's lever, not OPT's, though _SPEC filed it under `optim`: it is a layer in the
    #                    model, constructed at :1550-1551. Its measured interaction with weight_decay is
    #                    recorded at that lever.
    #   AMP / TF32       RUN's levers (CENSUS.md:398): they change how matmuls are executed, are resolved
    #                    once at process setup and are gated on the device. Note AMP is not free of this
    #                    package -- adding a GradScaler for fp16 would be a change to the accum cycle, a
    #                    scaler that does not unscale at the right point breaks accumulation silently --
    #                    which is why fp16 is refused there rather than accepted here.
    #   BAL_FLOOR / BAL_WARM / PONDER_WARM   filed under `optim` in _SPEC and owned by FAB: they shape the
    #                    router's balance term, not the optimiser.
    # ==============================================================================================
