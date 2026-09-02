"""RUN -- the training loop: how long the run is, what root of randomness it starts from, what machine it
runs on, how that machine's arithmetic is executed, and which half of the program runs at all.

WHAT THIS PACKAGE OWNS. Seven numbers, and none of them is a modelling decision. Nothing here changes what
is computed except through the float noise floor; nothing here is a cadence, a threshold or a weight. RUN
owns the run's EXTENT (`epochs`), its ROOT OF DETERMINISM (`seed`), the PROCESS PROPERTIES that every
package inherits and none of them may declare (`device`, `tf32`, `amp`), and the two MODE switches that
decide which half of the program executes (`bench`, `profile`). That is the whole of it. The loop's
cadences live where the mechanism they drive lives -- the fabric's management pass is FAB.manage_every,
the capacity valve's pin threshold is CAP.pin_windows, the learning-curve tick is EVAL's (the old
RATE_EVERY), the batch that one optimizer step is taken over is OPT.batch_windows x OPT.accum -- because
a cadence belongs to the thing it fires, and a loop that owned them all would be the 328-knob `_SPEC`
table again with a different name on the front.

WHY THESE ARE THE LEVERS, against the two goals and nothing else.

  GOAL B -- CONTINUAL LEARNING WITHOUT CATASTROPHIC FORGETTING -- IS WHY `epochs` IS HERE AND NOT IN OPT.
  A continual-learning claim is a claim about what survives a SECOND pass over changed material, so the
  number of passes is the shape of the experiment. It was filed under the `data` family and it set the
  learning-rate horizon at the same time (:6016-6028), which made two runs differing only in EPOCHS two
  different learning-rate experiments -- so every retention number this project ever produced was
  confounded with a schedule change nobody asked for. units.py rules on it in as many words ("never a
  schedule horizon"), and this file is where that ruling is enforced, by owning the run length in a
  package the schedule cannot read.

  GOAL A -- LANGUAGE PRODUCTION -- IS WHY `seed` IS A DECLARED LEVER AND NOT AN AMBIENT DEFAULT. The
  record's between-seed spread is 0.066-0.131 b/B, which exceeds every architectural difference this
  project has ever claimed (PLAN section 3 item 8). So no comparison may be reported from fewer than two
  seeds, G2's test_determinism runs two identical seeded CPU runs to establish the machine's float noise
  floor before any sweep is believed, and G3's isolation sweep compares against that floor. All three of
  those rest on one number. That number was ABSENT from the old `_EFF` banner while compare.py pairs runs
  by reading the seed out of that banner (:5901-5909) -- the tool built to make the project's claims
  trustworthy could not find the one value those claims turn on.

  THE OTHER FIVE ARE HERE BECAUSE THEY ARE PROPERTIES OF THE PROCESS, NOT OF ANY PACKAGE. `device` was a
  module-level global `DEV` (:527) that roughly every subsystem reached for -- the free-floating read L2
  forbids -- and it is the archetypal irreducible coupling: it reaches LM, MEM, FAB, SIG, WORLD and CKPT
  as `d_device`. `tf32` and `amp` are torch backend settings applied at process setup, grouped by the old
  file's own header as the two knobs that "only change how matmuls are executed" (:1057). `bench` and
  `profile` decide which half of the program runs and whether the step is instrumented; neither is a
  measurement OF the model, which is why they are not EVAL's.

--------------------------------------------------------------------------------------------------
CENSUS ACCOUNTING (.rework/census.json, filtered on new_owner == "RUN"): 9 rows.
--------------------------------------------------------------------------------------------------
     5 rename                     -> epochs, seed, device, tf32, amp
     2 keep                       -> bench, profile
     2 drop                       -> PROBE and PROBE_WAIT, not declared (CENSUS.md:350-351)
     0 merge
     0 promote-to-wire
   7 levers declared below, from 9 rows. CENSUS.md:40 says "RUN 9" because it counts ROWS assigned to
   this package, not declarations that survive them. The two that do not become declarations are named
   in WHAT IS DELIBERATELY ABSENT rather than subtracted silently, so a reader counting seven against a
   table that says nine does not have to re-derive where the other two went.

ALL NINE ROWS ARRIVE FROM FOUR OTHER FAMILIES, because the old `_SPEC` had no family for the loop at all.
The census assigns by OWNER, not by the family a hand-typed comment happened to put a knob in, and every
one of these is an ownership correction that comment could not express: EPOCHS from `data` (it is the
run's length, not the corpus's), SEED / TF32 / AMP from `optim` (nothing in the schedule or the optimizer
reads any of them), DEVICE from `plumbing`, and BENCH / PROFILE / PROBE / PROBE_WAIT from `report`
(nothing they control is a measurement of the model -- they decide which half of the program runs).

NO ROW ANYWHERE ELSE IN THE CENSUS MERGES INTO A LEVER OWNED HERE, and that was checked rather than
assumed: the 25 merge rows were read for a survivor named RUN_* and none names one. The two merges that
mention this package's material name it only to rule it OUT -- LR_EPOCHS folds into OPT_LR_WAVELENGTH
precisely so that an epoch stops setting a schedule horizon.

--------------------------------------------------------------------------------------------------
THREE CENSUS DEFECTS, CHECKED AGAINST ALL NINE ROWS
--------------------------------------------------------------------------------------------------
1. DOUBLED ENVIRONMENT NAMES -- SEVEN ROWS SEEN, SEVEN CORRECTIONS LANDED. Every one of this package's
   seven surviving rows names its target as PREFIX.PREFIX_FIELD: `RUN.RUN_EPOCHS`, `RUN.RUN_SEED`,
   `RUN.RUN_DEVICE`, `RUN.RUN_TF32`, `RUN.RUN_AMP`, `RUN.RUN_BENCH`, `RUN.RUN_PROFILE` (CENSUS.md:340,
   352, 355, 398, 404-405, 416). spine/lever.py::Lever.env_name_for generates the environment name as
   PREFIX + "_" + FIELD.upper(), so `RUN.RUN_SEED` taken literally declares a field `RUN_SEED` answering
   to RUN_RUN_SEED -- a name no operator would ever type, that from_env() would never find, and that
   therefore pins the lever at its default forever while every static check reports it declared, owned
   and resolved. That is the silent-default class this rebuild exists to end, arriving through the
   document written to end it. The prefix is stripped from the FIELD in all seven cases and THE ENV NAME
   IS UNCHANGED from what the census intended -- that invariance is the point of the correction, not a
   side effect of it: RUN_EPOCHS, RUN_SEED, RUN_DEVICE, RUN_TF32, RUN_AMP, RUN_BENCH, RUN_PROFILE.
   THE OTHER TWO ROWS CARRY NO FIELD AT ALL: both drops write `RUN.` with an empty name, so they mint
   nothing and needed no correction. Seven doubled rows, seven corrections, two rows not applicable.
   (This is not a RUN peculiarity. Across the whole census 207 of the 256 keep/rename rows are written in
   the doubled form and 49 in the bare-field form, which is what a clerical habit looks like rather than
   a decision -- the packages written before this one corrected theirs the same way.)

2. CLOCK KINDS -- ONE CLOCK-TYPED ROW, NOT RE-TYPED, AND ONE CONFLICT IN THE SPINE STATED RATHER THAN
   RESOLVED. Of the seven levers, exactly one carries a clock unit: `epochs`, typed Epochs. It stays
   Epochs. The assignment's rule -- "a cadence measured by the training loop step counter is Windows
   (step advances per WINDOW), not Steps" -- does not reach it, because an epoch is not measured by the
   step counter at all: it is a pass over the stream, counted by `_epoch` at the point the stream is
   rebuilt (:5467, :1390), and the loop's own counter is reset by it rather than compared against it.
   RUN DECLARES NO CADENCE AND NO THRESHOLD. Nothing in this file is of the form `step % X == 0` or
   `clock >= X`, which is a claim about this package a later reader can test by grepping it.
   THE CONFLICT IS ONE LEVEL OUT, AND IT IS THIS PACKAGE'S TO STATE BECAUSE THE CLOCK IN DISPUTE IS THE
   LOOP'S. spine/assemble.py::_owner_blocks builds three per-flush cadences as
   `derive.flush_period(Steps(r["FAB"].manage_every), r["TRAIN"].batch_w)` and the same for
   `r["TRAIN"].grow_cap_every`, and derive.flush_period REFUSES anything that is not exactly Steps
   (derive.py::flush_period). The census types both of those inputs Windows-shaped: MANAGE_EVERY -> FAB, Windows,
   declared `manage_every` at fabric/levers.py::FABLevers with the conflict recorded there; GROW_CAP_EVERY ->
   CAP_PIN_STEPS, which capacity/levers.py::CAPLevers.lift_min declares as `pin_windows`, U.Windows, for the same reason.
   Both those files reached the same reading independently: the divisor is `step`, and units.py says
   `step` counts WINDOWS. This file agrees with them and changes nothing, because the number in dispute is
   not RUN's to relabel -- but the fact the dispute is ABOUT is: the loop advances `step` once per window
   (:6796 `i += WIN; step += 1`) while the loop body runs once per flush (:934), and every one of these
   arguments is downstream of that single sentence. If Windows is right then assemble.py is converting
   from the wrong kind and flush_period needs a Windows arm; if Steps is right then two lever files are
   mislabelled. Nothing here picks, because a lever file quietly editing the wiring file to agree with
   itself is how one number acquires two answers.

3. UNRESOLVED MERGES -- NONE, AND THE NEGATIVE WAS CHECKED IN BOTH DIRECTIONS. None of this package's
   nine rows is a merge, so no lever below exists only because a merge pointed at it and nothing had to
   be emitted under its own name to avoid inventing a target. The other direction was checked too (see
   the accounting above): no merge row anywhere in the census names a RUN-owned survivor, so this file
   does not owe another family a target either.

A FOURTH CORRECTION, OUTSIDE THE THREE CLASSES, MADE VISIBLY BECAUSE IT IS A CORRECTION TO A REASON
   RATHER THAN TO A NAME. AMP's row says the old fp16 refusal was "a SystemExit reachable only on CUDA"
   (CENSUS.md:398). It is not: the refusal sits at module scope (:1075-1081) and fires at import on any
   box. The census was misled by the source's own comment directly above it (:1072, "This is only
   reachable on CUDA"), which is a true statement about the AUTOCAST BRANCH and a false one about the
   refusal it was later placed over. The lever still carries choices= and the census's conclusion still
   holds -- for the reason set out at that declaration, which is that every spelling OTHER than fp16 was
   accepted silently.

--------------------------------------------------------------------------------------------------
THE PREFIX CONFLICT WITH spine/assemble.py: THERE IS NO PACKAGE CALLED `TRAIN`, AND THIS FILE IS NOT IT
--------------------------------------------------------------------------------------------------
spine/assemble.py names a prefix `TRAIN` in seven places, and a reader arriving at a file that lives in
src/train/ will assume this is that package. IT IS NOT, and the difference is not cosmetic.

  WHAT ASSEMBLE EXPECTS OF `TRAIN`: `TRAIN.batch_w` and `TRAIN.accum` (:684-762, four couplings, one of
  them writing a LOCAL `TRAIN.d_effective_batch_windows`), `TRAIN.grow_cap_every` (:696-712), and in the
  NOT_WIRES rejections `TRAIN.seed` (:775) and `TRAIN.epochs` (:783).
  WHAT THE CENSUS SAYS: two of those five are OPT's -- BATCH_W -> OPT_BATCH_WINDOWS, ACCUM -> OPT_ACCUM;
  one is CAP's -- GROW_CAP_EVERY -> CAP_PIN_STEPS, declared `pin_windows`; and only `seed` and `epochs`
  are this package's. So RENAMING `TRAIN` TO `RUN` IN assemble.py WOULD NOT FIX IT and would make it
  worse: three of the five fields do not exist here and never will, and `d_effective_batch_windows` is a
  local coupling on OPT, not a wire this package can receive. The repair is per-field retargeting, in
  assemble.py, by whoever ports the loop.
  WHAT HAPPENS TODAY, reproduced by opt/levers.py rather than predicted: build() does not fail on this.
  A coupling naming an unregistered package is DEFERRED with a warning (assemble.py::COUPLINGS) and TRAIN is
  registered by nobody, so all four rows print "DEFERRED ... package(s) ['TRAIN'] not registered" and are
  NOT MADE. Declaring this file does not change that, and that is exactly the state to be alarmed by: a
  declared-but-unmade wire reads as "not ported yet" long after it has become "ported, and wired to a name
  nobody owns".
  THE TWO REJECTIONS ARE UNAFFECTED IN SUBSTANCE AND STALE IN LABEL. "TRAIN.seed -> every package's
  d_seed" and "TRAIN.epochs -> OPT.d_lr_horizon" are rejections this file agrees with completely (see
  `seed` and `epochs` below); only the prefix is wrong, and correcting prose in another package's file is
  not this file's business either.

--------------------------------------------------------------------------------------------------
THE WIRES: values this package supplies or needs that it must NOT declare
--------------------------------------------------------------------------------------------------
lever.py::Lever.__set_name__ refuses a d_-named lever precisely so a declaration cannot shadow the wire that writes it,
and O4 audits the d_ namespace in BOTH directions -- so the receiving end saying what it expects is half
of what makes `grep d_` complete. NONE OF THE FOLLOWING EXISTS IN spine/assemble.COUPLINGS TODAY.
    OUTGOING
      d_device        cpu/cuda, to LM, MEM, FAB, SIG, WORLD and CKPT   (DEVICE's row, CENSUS.md:416;
                                                                       lm/levers.py::<module> already declares
                                                                       it incoming and names that row)
      d_epochs        the run length, to DATA                          (EPOCHS's row: the whole-run
                                                                       exposure audit at :5514-5520 and
                                                                       the resample count; data/levers.py
                                                                       :137 declares it incoming)
      d_total_steps   the run length in steps, to OPT                  (EPOCHS's row calls it that;
                                                                       opt/levers.py::<module> expects the same
                                                                       quantity as `d_run_steps`. ONE
                                                                       VALUE, TWO SPELLINGS, neither in
                                                                       the ledger -- recorded so whoever
                                                                       writes it picks one on purpose)
    NOT A WIRE, BY AN EXPLICIT REJECTION THIS FILE AGREES WITH
      d_seed          assemble.py::COUPLINGS refuses it. What a package needs is not the number but a STREAM:
                      rng_for("fabric", seed) is per-subsystem, name-keyed, stable across processes, and
                      recorded by rng.issued() -- so a subsystem with zero draws reads armed-but-inert
                      and one that never asked does not appear at all (G4). WHAT THAT MEANS FOR THIS
                      LEVER, and it is worth being exact because "not wired" is easy to misread as "not
                      needed anywhere": the seed VALUE does not travel at all. The entry point holds
                      RUN's Config, constructs the streams, and hands each package its own Rng. A package
                      that reads a seed from anywhere else has reintroduced the shared global stream that
                      rng.py's header exists to describe.

--------------------------------------------------------------------------------------------------
WHAT THIS FILE CANNOT EXPRESS, AND WHERE THE OLD GUARDS WENT
--------------------------------------------------------------------------------------------------
A Lever carries a default, a unit, a help string and an optional closed set of choices. It has no range
facility and no relation to any other lever, and three guards the old tree kept at the read site have
nowhere to live in a declaration:
    EPOCHS      `max(1, _i("EPOCHS", 1))` at :5467. RUN_EPOCHS=0 now resolves to 0 and the loop runs no
                passes; whoever writes the loop owes a startup refusal, in one place.
    SEED        nothing clamped it and nothing should, but note rng.derive_seed keeps the SIGN meaningful
                (rng.py::derive_seed) while some harnesses use -1 as "unset". A negative seed is a real run.
    TF32/AMP    both were gated on `DEV == "cuda"` at the read site, which is a RELATION between two
                levers. `choices=` cannot state one. The startup code that applies them must, and it must
                say when it declines to (see `amp`).
Two-package startup guards are the same shape and cannot live in either file: "EPOCHS>1 with DISK_STREAM=0
means every epoch is a BYTE-IDENTICAL REPLAY" (:5470-5472) is RUN's length against DATA's resample flag,
and it is the difference between a continual-learning experiment and the same experiment run twice.

IMPORT STYLE, AND WHY IT DEPARTS FROM THE ASSIGNMENT'S SKETCH. `from ..spine.lever import ...` cannot work
here. Every entry point in this tree puts `src/` ITSELF on sys.path (tests/test_ownership.py,
tests/test_derive.py::<module>, and this file's own verification command), which makes `train` a TOP-LEVEL
package, and a relative import that walks above one raises ImportError, "attempted relative import beyond
top-level package". The absolute form below is what all twelve sibling levers.py files use.
"""
from spine.lever import Lever, LeverSet
from spine import units as U


class RUNLevers(LeverSet):
    """The loop: how long it runs, from what seed, on what machine, in what precision, and which half of
    the program executes.

    Read `cfg.seed`, never an environment name. Every value here is resolved once by spine.assemble and
    frozen; a function receiving this Config should open with `run.owned_by("RUN")`, because a Config is
    an ordinary object and a foreign one handed in reads happily and wrongly -- `memory_prune(configs
    ["FAB"])` returning 2048 is the reproduced case behind that method's existence (lever.py::Config).

    Grouped by the decision each group makes. The grouping is load-bearing in one place: `device` decides
    whether `amp` is reachable AT ALL (the autocast branch is guarded on `DEV == "cuda"`, :1072-1081) and
    whether `tf32` and `profile` cost anything, so those four are one decision about the machine wearing
    four names. In the old tree that fact was spread across :527, :1061-1081 and :5726-5757 with nothing
    anywhere saying they were related.
    """

    PREFIX = "RUN"

    # ==============================================================================================
    # 1. THE EXTENT OF THE RUN, AND WHAT IT STARTS FROM
    #
    # Two numbers that between them define WHICH RUN THIS IS. Every other lever in the tree describes the
    # system; these two describe the experiment. They are also the two that every report has to print,
    # for opposite reasons: the seed because comparisons are paired by it, the epoch count because a
    # continual-learning claim is a claim about a second pass.
    # ==============================================================================================

    epochs = Lever(1, "How many passes over the stream the run makes; the loop's termination test.",
                   U.Epochs)
    # Census: EPOCHS -> RUN.RUN_EPOCHS, verdict rename, default 1, unit Epochs (CENSUS.md:340). Field
    # corrected from `RUN_EPOCHS` to `epochs` (DEFECT 1); the env name is RUN_EPOCHS either way, which is
    # what the census meant.
    # WHY IT IS NOT OPT'S, WHICH IS THE ONLY INTERESTING THING ABOUT THIS LEVER. EPOCHS set the run
    # length AND the cosine horizon, so two runs differing only in it were two different learning-rate
    # experiments -- the file says so itself at :6016 ("EPOCHS=%d sets run length AND the cosine horizon,
    # so it changes the LR at EVERY step") and at :4718 ("AN EPOCH IS NOT A UNIT OF ANYTHING"). The same
    # fault one level down killed LR_EPOCHS: "LR_EPOCHS=8" meant 48,000 steps at STREAM_LEN=4e6 and
    # 840,000 at 94e6, a 17x range under one number, which is why that row is a merge into
    # OPT_LR_WAVELENGTH and why assemble.py's NOT_WIRES refuses "TRAIN.epochs -> OPT.d_lr_horizon" in
    # terms this file agrees with word for word. OPT owns its horizon as a declared lever; a run that
    # wants them to agree sets both, and the report can then say that it did.
    # THE CLOCK IS Epochs AND STAYS Epochs (DEFECT 2). It is not compared against `step`: `_epoch`
    # increments where the stream is rebuilt (:5467, and `_srng` at :1390 mixes the epoch into the stream
    # seed so epoch 5 of a resumed run reads what epoch 5 of an uninterrupted run read). units.Epochs
    # exists to make `epochs >= some_step_threshold` raise, which is the comparison that produced the
    # confound above.
    # THE GUARD THAT DID NOT SURVIVE: `EPOCHS = max(1, _i("EPOCHS", 1))` at :5467. RUN_EPOCHS=0 resolves
    # to 0 here and a Lever cannot refuse it; the loop must.
    # THE GUARD THAT MUST SURVIVE, and it belongs to neither package alone: EPOCHS>1 with DISK_STREAM=0
    # replays byte-identical text every epoch, because _resample runs only under DISK_STREAM (:5470-5472).
    # A continual-learning result taken that way is a memorisation result.
    # ONE HARNESS DEFECT TO END RATHER THAN PORT (ISSUES L9, longrun.sh:1538 vs :225): the grid banner
    # prints the SWEEP's epoch count even for an arm that overrode it -- `vmax8k` sets EPOCHS=18 while the
    # banner has already printed 8. A single declaration read once and printed from the resolved Config
    # is what removes the second source of that number.
    # LEAVES AS TWO WIRES, NEITHER OF THEM IN THE LEDGER: d_epochs to DATA (the exposure audit multiplies
    # by it at :5514 and the resample count is per epoch) and the run length to OPT for its `lr_wavelength`
    # sentinel. The second conversion is not free and must be named where it happens rather than inlined:
    # steps-per-epoch was `STREAM_LEN // WIN` (:4317, :4719), a BYTE budget divided by a TOKEN window,
    # which data/levers.py names as a live byte/token confusion.

    seed = Lever(0, "Root seed for the whole run; every module's initialisation and the data stream "
                    "derive from it.", U.COUNT)
    # Census: SEED -> RUN.RUN_SEED, verdict rename, default 0, unit count (CENSUS.md:404). Field corrected
    # from `RUN_SEED` to `seed` (DEFECT 1).
    # NOT AN OPTIM KNOB: nothing in the schedule or the optimizer reads it. It was read at module scope --
    # `torch.manual_seed(_i("SEED", 0)); random.seed(_i("SEED", 0))` at :1016, one knob read twice on one
    # line, which is the second-default hazard L1 removes -- then fanned out per module at :4137-4173 with
    # fixed offsets (+101 encoder, +202 world model, +303 fabric) so that no module's initialisation
    # depends on how much RNG another consumed, and mixed with the epoch at :1390 to seed the stream.
    # THOSE FAN-OUTS ARE NOT WIRES AND NOT OFFSETS ANY MORE. spine/rng.py replaces them: derive_seed is
    # blake2b of (seed, subsystem name), explicitly NOT `seed + index` -- which collides across runs
    # (subsystem #1 at seed=1 and subsystem #0 at seed=2 both get 2, so two "independent" replicates share
    # streams pairwise and the between-seed spread they measure is smaller than the real one) and makes
    # the mapping depend on declaration ORDER, so inserting a subsystem reseeds every one after it.
    # assemble.py::COUPLINGS refuses a d_seed wire for the same reason; what travels is the stream, not the
    # number, and rng.issued() records every stream handed out.
    # LOAD-BEARING TWICE OVER IN THE NEW PLAN, which is why it is a lever and not a constant: G2's
    # test_determinism runs two identical seeded CPU runs to establish the measured float noise floor that
    # every isolation result is read against, and PLAN section 3 item 8 forbids reporting any comparison
    # from fewer than two seeds, because the measured between-seed spread (0.066-0.131 b/B) is larger than
    # every architectural difference this project has claimed.
    # ITS OWN HISTORY IS THE ARGUMENT FOR GENERATED CONFIG OUTPUT: SEED was simply absent from the _EFF
    # banner while compare.py pairs runs by reading the seed out of that banner (:5901-5909), so the tool
    # built to make the project's claims trustworthy could not find the one number those claims turn on --
    # and its own failure text says the state it found was the normal one ("NEITHER ARM HAS A SEED ... the
    # state of every log this project has ever produced", compare.py::main).
    # THE UNIT IS A KNOWN MISLABEL, carried from the census and harmless in the way metadata is: a seed is
    # not a count OF anything, and units.py has no SEED or OPAQUE constant. U.COUNT is the least-wrong
    # existing label; adding one is a spine edit and this file has no standing to make one (the same
    # ruling opt/levers.py reached for its learning rate).
    # A NEGATIVE SEED IS A REAL RUN. rng.derive_seed includes the sign in the hashed text so seed=-1 and
    # seed=1 are different keys (rng.py::derive_seed), stated there because some harnesses use -1 to mean
    # "unset" and an alias onto a real run is unrecoverable after the fact. Note also that coercion is
    # int(float(raw)), so RUN_SEED=1e6 resolves to 1000000 rather than failing.

    # ==============================================================================================
    # 2. THE MACHINE, AND HOW ITS ARITHMETIC IS EXECUTED
    #
    # Three values applied once at process setup, before any package exists. None of them changes WHAT is
    # computed; two of them change the float noise floor, which is the quantity G2 measures and G3's
    # isolation sweep is read against -- so a run whose floor was measured under a different matmul
    # precision is not comparable to one that was not, and that is the entire reason they are declared,
    # printed values rather than ambient library defaults.
    # ==============================================================================================

    device = Lever("cpu", "The torch device every module's .to() targets, and the gate on the "
                          "mixed-precision branch.", U.NAME, choices=("cpu", "cuda"))
    # Census: DEVICE -> RUN.RUN_DEVICE, verdict rename, default cpu (CENSUS.md:416). Field corrected from
    # `RUN_DEVICE` to `device` (DEFECT 1).
    # IT HAD NO OWNER AT ALL, WHICH IS THE WHOLE OF THE RENAME. self_organize.py:527 binds a module-level
    # global `DEV` that roughly every subsystem reaches for -- :4155-4157 the world model, :4364 the
    # resume load, every memory and fabric tensor -- which is precisely the free-floating read L2 forbids.
    # It is not a modelling lever of any one package but a property of the process, so RUN owns it and it
    # reaches LM, MEM, FAB, SIG, WORLD and CKPT as a declared `d_device`. NOT promote-to-wire: the value
    # originates with the operator, not with another package.
    # choices= IS A DELIBERATE NARROWING AND THE COST IS STATED. torch accepts "cuda:1", "mps" and more;
    # this refuses them. The reason is that every consumer in the tree tests the STRING by equality --
    # `DEV == "cuda"` gates the AMP branch (:5720), the profiler's torch.cuda.synchronize() (:5738, :5741,
    # :5746, :5750) and the peak-memory line in the BENCH summary (:7812) -- so RUN_DEVICE=cuda:1 runs on
    # a GPU with autocast silently off and with the profiler attributing asynchronous kernel time to
    # whichever span happened to be open. That is a value the operator did not ask for, taken silently,
    # which is the class the eleven silent-else knobs belong to (ISSUES M24 also files the case-sensitivity
    # half: "Cuda" takes the else branch too). Every launcher in this repo sets exactly "cpu" or "cuda",
    # so nothing shipped is lost today. WHEN SOMEBODY NEEDS A SECOND GPU the repair is not a wider string:
    # it is one derived predicate (is-this-cuda) resolved in one place and wired, so that adding a device
    # spelling cannot silently disarm three unrelated branches. Reversing this decision means changing
    # this line AND those branches together.
    # THE HARNESS DISAGREES WITH THE LEVER, AND A GENERATED NAME ONLY HALF-FIXES IT. longrun.sh:578
    # hardcodes DEVICE=cuda for `run|resume`, while selftest.sh:108 deliberately ignores $DEVICE and reads
    # SELFTEST_DEVICE instead -- with a reason worth keeping: an ambient DEVICE=cuda meant "anyone with it
    # exported who ran the test suite on the GPU box would have quietly put a training job on the GPU
    # alongside an 18-epoch run". One knob meaning two things depending on who launched is not something a
    # declaration can fix; what the generated name does buy is that RUN_DEVICE is a distinct string from
    # the harness's own DEVICE, so the two can stop being the same variable by accident.
    # ON CPU EVERYTHING BELOW THIS LINE IS A NO-OP, WHICH IS WHY IT MUST BE PRINTED: every test in this
    # tree runs on CPU, so the printed config is the only thing that distinguishes the two regimes.

    tf32 = Lever(True, "Allow TF32 matmul and cuDNN kernels; changes how matmuls execute, not what is "
                       "computed.", U.FLAG)
    # Census: TF32 -> RUN.RUN_TF32, verdict rename, default 1, unit on/off (CENSUS.md:405). Field
    # corrected from `RUN_TF32` to `tf32` (DEFECT 1).
    # DECLARED True, NOT 1, following the rule fabric/levers.py::<module> states for the whole tree: the
    # VALUE is identical (True == 1 and bool is an int, so this is the census's literal), but the declared
    # TYPE selects a coercion branch -- with a bool default RUN_TF32=off means off, with an int default it
    # raises. The honest cost of the bool branch is stated there too and applies here: any spelling
    # outside ("0", "", "off", "no", "none", "false") reads as True, so RUN_TF32=flase is silently ON, and
    # choices=(True, False) cannot help because coercion has already collapsed the typo into that set.
    # The repair, if wanted, is a refusal in Lever.coerce, not a list here.
    # WHY IT IS KEPT: torch enables TF32 for cuDNN but NOT for matmul (:1057-1059), so the fp32 path
    # leaves most of an H100's matmul throughput unused -- turning it on is not free, and neither is
    # turning it off. And it changes the float noise floor, which is the number G2's test_determinism
    # measures and G3's isolation sweep compares against, so it has to be declared and printed rather than
    # inherited from whatever version of torch is installed.
    # ONE DEFECT TO CARRY A FIX FOR RATHER THAN TO REPRODUCE. The old application is one-way:
    #     if bool(_i("TF32", 1)):
    #         torch.backends.cuda.matmul.allow_tf32 = True; torch.backends.cudnn.allow_tf32 = True
    # (:1061-1062). TF32=0 does not turn TF32 OFF -- it declines to turn it ON, and cuDNN's own default is
    # already allow_tf32=True, which the comment two lines above says in as many words. So a run launched
    # with TF32=0 to rule matmul precision out of a determinism question still ran cuDNN convolutions and
    # kernels in TF32, and the config line said the knob was off. The port must ASSIGN the resolved
    # boolean to both attributes rather than guard the assignment.

    amp = Lever("off", "Autocast precision for the LM step: off runs fp32, bf16 runs the step in "
                       "bfloat16 while memory keys stay fp32.", U.NAME, choices=("off", "bf16"))
    # Census: AMP -> RUN.RUN_AMP, verdict rename, default "off" (CENSUS.md:398). Field corrected from
    # `RUN_AMP` to `amp` (DEFECT 1).
    # choices= IS THE REPAIR THE CENSUS ASKS FOR BY NAME, BUT NOT FOR THE REASON THE CENSUS GIVES, and the
    # difference is worth one paragraph because it changes what the lever is FOR. CENSUS.md:398 says the
    # old refusal was "a SystemExit reachable only on CUDA". IT IS NOT: `if AMP == "fp16": raise
    # SystemExit(...)` sits at module scope (:1075-1081) and fires at import on any box. What misled the
    # census is the source's own comment three lines above it -- "This is only reachable on CUDA, so
    # nothing on a CPU box can see it" (:1072) -- which is true of the AUTOCAST BRANCH it was written
    # about and false of the refusal it now sits on top of. Corrected here rather than repeated, because
    # a wrong sentence about a guard is the reason a reviewer stops looking at it.
    # WHAT WAS ACTUALLY UNGUARDED IS EVERY OTHER SPELLING. Exactly one value was refused, by name; anything
    # else fell through to `elif AMP != "off": print(f"[precision] AMP={AMP} ignored on device {DEV}")`
    # (:5719-5725). So RUN_AMP=bfloat16 on an H100 trains the whole run in fp32, having been asked for
    # bf16, and says so once, at step 0, in a line no grid ever reads. That is the silent-else class the
    # eleven M24 knobs belong to, and choices= is the repair for it: refused at startup, by name, with the
    # allowed set in the message.
    # THE "ignored on device" LINE IS NOT WHAT choices= REPLACES AND MUST SURVIVE. RUN_AMP=bf16 on CPU is
    # a legal setting that does nothing, which is precisely G4's armed-but-inert state and has to be
    # reported as such rather than resolved into silence.
    # WHY fp16 STAYS OUT, because "the knob refuses it" is not a reason: bf16 carries fp32's exponent
    # range and so needs no loss scaling, fp16 does not, and there is no GradScaler anywhere in this tree.
    # Autocasting to fp16 without one lets small gradients underflow to zero -- the loss curve looks
    # plausible while an unknown fraction of every update is discarded, and the old code printed a
    # confident "[precision] LM step in fp16 autocast" while doing exactly that. Adding a scaler is not a
    # line: the optimizer step is gated on accumulated backward passes, and a scaler that does not unscale
    # at the right point in that cycle breaks accumulation silently instead. That is deliberate work in
    # OPT's territory, not a value to accept here.
    # WHAT choices= DOES NOT CARRY OVER: the old reader lowercased (`_env("AMP", "off").lower()` at :1063,
    # and AMP is the ONLY string knob in the old tree that normalised at all -- which is why ISSUES M24 is
    # phrased "string knobs OTHER THAN AMP are compared case-sensitively"). So AMP=BF16 used to work and
    # RUN_AMP=BF16 now raises. Lever.coerce does no normalisation, and adding one here would mean a second
    # parse of the same value in the one file that exists to end second parses. The refusal names the
    # allowed set, so the failure costs one edit.
    # THE fp32 CARVE-OUT AT :5719-5723 MUST SURVIVE THE PORT: memory keys are retrieved by dot product over
    # normalised keys, which is the one place in the step where reduced precision changes BEHAVIOUR rather
    # than speed. An autocast that swallows the key path turns a retrieval system into a noisier one with
    # no error anywhere.
    # STRUCTURALLY UNTESTABLE ON CPU, and that is a property of the lever rather than a gap in the suite:
    # the whole mechanism sits behind `DEV == "cuda"` and every test in this repo runs on CPU. There is no
    # test that can catch a regression here; it was found by asking what CPU testing cannot cover, and the
    # only instrument that will ever see it is the printed config of a GPU run.

    # ==============================================================================================
    # 3. WHICH HALF OF THE PROGRAM RUNS, AND WHETHER THE STEP IS INSTRUMENTED
    #
    # Two flags that decide what the process DOES, not what the model IS. Neither is EVAL's: nothing they
    # control is a measurement of the model. They are separately selectable on purpose -- see `profile`.
    # ==============================================================================================

    bench = Lever(False, "Stop immediately after the training loop and print throughput instead of "
                         "running the eval battery.", U.FLAG)
    # Census: BENCH -> RUN.RUN_BENCH, verdict keep, default 0, unit FLAG (CENSUS.md:352). Field corrected
    # from `RUN_BENCH` to `bench` (DEFECT 1). Declared False rather than 0 for the coercion reason given
    # under `tf32`, with the same "flase reads as ON" hazard.
    # IT IS A DECISION ABOUT WHICH HALF OF THE PROGRAM RUNS, which is why it is RUN's and not report's:
    # `if bool(_i("BENCH", 0)): ... return` at :7807-7817 prints steps/min, kB/s, GB/day, parameter count
    # and peak GPU memory and returns BEFORE the eval battery, which is a large fixed cost (final
    # re-tokenization, memorization check, generation, unlearn tests) that would swamp a short timing run.
    # THE SECOND USE IS AN IMPORT GUARD AND IT NEEDS REDESIGNING, NOT PORTING. prompt.py:41 sets
    # os.environ["BENCH"] = "1" before importing self_organize, purely so that sampling from a checkpoint
    # does not trigger a full report. Under the spine that is a different animal: from_env is called once,
    # in spine/assemble.build(), and a module that mutates the environment to steer a later import is
    # writing to something nobody reads twice -- it would work only by accident of ordering. "Do not run
    # the report" is the entry point choosing which half to run; one flag doing both jobs is how the
    # throughput arm and the sampler ended up sharing a switch.
    # ONE REQUIREMENT IT CARRIES (ISSUES L42, wrong-measurement): `_bpw`, the bytes-per-window behind kB/s
    # and GB/day, is initialised at the SEED vocabulary (:6237) and refreshed only inside the RATE_EVERY
    # tick (:6493), so a short BENCH run that never reaches a tick quotes both figures at the seed
    # vocabulary -- the exact staleness the refresh was added to fix for the rate meter. Note the cadence
    # it depends on is now EVAL's (RATE_EVERY -> EVAL_CURVE_EVERY): a RUN-owned throughput number whose
    # correctness depends on an INSTRUMENT's tick is a cross-package staleness that quietening a log would
    # reintroduce. In the rebuild bytes-per-window is one derived d_ value resolved in one place.

    profile = Lever(False, "Per-component wall-clock attribution of the training step, dumped on the "
                           "rate cadence and again in the throughput summary.", U.FLAG)
    # Census: PROFILE -> RUN.RUN_PROFILE, verdict keep, default 0, unit FLAG (CENSUS.md:355). Field
    # corrected from `RUN_PROFILE` to `profile` (DEFECT 1). Declared False, as above.
    # A DIAGNOSTIC MODE, NOT A RUN MODE, AND THE DISTINCTION IS THE LEVER'S WHOLE CONTENT. On CUDA the
    # timers must torch.cuda.synchronize() to attribute time at all (:5738, :5741, :5746, :5750), and the
    # synchronisation
    # itself costs throughput -- so a run that profiles is not the run being timed, and `bench` and
    # `profile` have to be separately selectable rather than one "measure the loop" switch. They compose
    # on purpose: BENCH prints the per-component breakdown only when PROFILE is on (:7814-7816), which is
    # what makes a throughput number actionable instead of a single aggregate nobody can act on.
    # KEPT RATHER THAN DELETED BECAUSE IT IS FREE WHEN OFF: `_T` returns a shared no-op context (_NULL)
    # and `_t0` returns None (:5743-5745), so the instrumentation can live in the hot path without a
    # second code path to rot -- which is the property that decides whether an instrument survives a
    # rebuild. It answers the one question guesswork kept getting wrong here: which part of the step is
    # actually slow.
    # THE HAZARD IS ON CPU AND IT IS AN HONEST ONE: with no synchronisation to skip, profiling on CPU
    # costs a time.time() pair per span and its attribution is correct; on CUDA the sync is what makes the
    # attribution meaningful, and if `device` is ever widened past "cuda" (see that lever) the syncs stop
    # happening and this instrument silently starts reporting kernel-launch times instead of kernel times.
    # A profiler that is wrong rather than absent is the wrong-measurement class, 98 of the survey's 475
    # records.

    # ==============================================================================================
    # WHAT IS DELIBERATELY ABSENT, one line each, because a reader who finds them missing will otherwise
    # go looking for a mistake. Full reasons are in the header and in the census rows named.
    #
    #   PROBE       dropped (CENSUS.md:350), the DUPLICATE case rather than the never-fired case: it
    #               fired on every run at the default, and the quantity it reported is measured correctly
    #               by the live rate meter -- its own printed caption told the reader not to trust it.
    #               It existed as a flag only because the probe CHANGED THE RUN: 18 passes of draws off
    #               the global RNG stream, and an out.backward() that left 29 world-model parameters
    #               holding gradients computed from RANDOM TOKENS. PROBE=1 and PROBE=0 had byte-identical
    #               weights entering the loop, split at the second logged step (6.1199 vs 6.1125) and
    #               never rejoined. Both causes are fixed by frozen_rng and torch.autograd.grad, and with
    #               them fixed the flag's whole remaining effect was saving about two seconds. The
    #               estimate stays as an unconditional startup line labelled LM-only (G6).
    #   PROBE_WAIT  dropped (CENSUS.md:351): 12 seconds of sleep per arm so a human could Ctrl-C after
    #               reading an estimate that is no longer switchable. Its own comment records that the
    #               message is "a lie" for unattended grid runs, and its reader was spelled
    #               _i(chr(80)+chr(82)+chr(79)+..., 12) at :4320 so grepping the knob's name did not find
    #               its call site -- the invisibility the generated-name registry exists to end.
    #   BATCH_W / ACCUM   OPT's (OPT_BATCH_WINDOWS, OPT_ACCUM). assemble.py::_owner_blocks sources them from a
    #               prefix `TRAIN`; see the header. They are the size of a flush and the size of an
    #               optimizer step, not properties of the process.
    #   GROW_CAP_EVERY    CAP's, declared `pin_windows` (capacity/levers.py::CAPLevers.lift_min). Same stale prefix.
    #   MANAGE_EVERY      FAB's cadence; RATE_EVERY is EVAL's curve tick; CKPT_EVERY/RESUME/SAVE_CKPT are
    #               CKPT's; STREAM_LEN and DISK_STREAM are DATA's; WIN is LM's context width. A loop that
    #               declared any of them would own a mechanism it does not implement.
    #   d_device / d_epochs / d_total_steps   outgoing wires, not levers -- lever.py refuses a d_-named
    #               lever so a declaration cannot shadow the wire that writes it. None is in
    #               spine/assemble.COUPLINGS yet.
    #   d_seed      refused on purpose (assemble.py::COUPLINGS). What travels is the per-subsystem stream from
    #               rng_for(name, seed), not the number.
    # ==============================================================================================
