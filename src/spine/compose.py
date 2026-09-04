"""THE COMPOSITION ROOT: the assembly of OBJECTS, one level up from assemble.py's assembly of CONFIGS.

    from spine.compose import compose
    system = compose(environ=os.environ)      # the caller owns the environment; see G9 below

WHY THIS FILE IS IN src/spine/. tests/test_ownership.py check O10 refuses any import of one package
from another, and O3/O8 keep `from_env` and the registry inside the spine. Something has to hold
every package's Config and every package's objects at once in order to hand each one what it needs,
and the architecture already says how: A CROSS-PACKAGE VALUE ARRIVES AS AN ARGUMENT THE SPINE
PASSED IN, and this file is the place the passing happens. It is exempt from O9's ownership
assertion and from O10 for exactly the same reason spine/assemble.py is.

THAT IS THE INTENDED ROUTE. IT IS NOT THE ONLY ROUTE, and the first draft of this docstring said
"There is no other route", which is false and is the sentence that makes a reviewer stop looking.
spine/lever.py::LeverSet had already been corrected once for the same overclaim; the correction did
not reach this file, and a reviewer demonstrated three ways past it with every check green:
  * `from spine.compose import build` -- this file's own re-export, see the import block below;
  * `LeverSet.__subclasses__()` from spine.lever, the one module every package MUST import, then
    `getattr(sib, "from_" + "env")()` -- thirteen packages, every env-overridden value, no
    forbidden name anywhere;
  * a package's OWN Config: `cfg._owner.__mro__` reaches LeverSet with nothing imported at all.
What answers the second and third is the runtime latch in spine/lever.py -- build() closes the
assembly as its last act and from_env raises after -- because it matches a MOMENT rather than a
name. What answers NONE of them is reading a foreign lever's DECLARATION
(`sib._levers["alpha"].default`), which needs no from_env and no Config; that is L3's, and L3
(tests/test_lever_isolation.py, behavioural, against the test_determinism noise floor) does not
exist yet. Read the checks as raising the cost of a leak, not as proving there is none.

WHAT THIS FILE IS NOT. IT DOES NOT RUN A TRAINING LOOP. The loop is RUN package mechanism --
RunClock.advance is the only site in the tree that increments a counter, and Cadences.due is the
only cadence primitive. This file builds the objects, wires the arguments and returns the assembled
system; whoever runs the loop drives RunClock and calls the mechanisms in the order ASSEMBLY_ORDER
and LOOP_ORDER below describe.

WHAT IT DOES TODAY. Every mechanism entry point exists as a stub that raises NotImplementedError
naming the phase that fills it in, so `compose()` runs until the first unimplemented stub and stops
there with a message that says which package owes what. That is deliberate: a composition root that
cannot be executed until ten packages land is a design document pretending to be code, and this one
is executable on the day the contract is frozen. `plan()` returns the same order as data without
calling anything, so the shape can be inspected and tested with nothing implemented at all.
DEFERRED_ENTRY_POINTS, beside the tables, is the declared list of entry points the order does NOT
yet reach, each with the phase that will reach it and the argument that has no producer today. It
is checked backwards -- an entry a row now names is reported stale -- so it cannot become the place
orphans go to be forgotten. Every row carries a FIFTH element naming what it PRODUCES for later
rows, spelled as the CONSUMING signature spells it, and ROW_ARGUMENTS_ELSEWHERE names the two rows
whose arguments come from a join in this file instead. Those three tables together are what make
"nothing supplies this argument" a decidable question rather than a judgement call; K10 reads all
three.

IMPORT CYCLE, CHECKED RATHER THAN ASSUMED. `src/spine/` has no __init__.py, so `spine` is a
namespace package and `from spine.assemble import build` resolves through it. The direction of every
edge in the import graph was verified before this file was written:
    spine.lever    -> spine.registry, spine.units          (no package import)
    spine.assemble -> spine.{lever,registry,wire,derive,units} and all 13 <pkg>.levers
    <pkg>.api      -> spine.lever ONLY
    spine.compose  -> spine.assemble and all 13 <pkg>.api
No package imports spine.compose, and no <pkg>.api imports spine.assemble, so adding this file
closes no loop. `python3 -c "import sys;sys.path.insert(0,'src');import spine.compose"` was run and
imports cleanly.

THE IMPORT HAZARD, MEASURED (ISSUES P1-C10). Running with the REPOSITORY ROOT ahead of `src` on
sys.path makes `import memory` return the old 654-line ./memory.py, and `import data` would return
the tracked ./data/ CORPUS DIRECTORY as a namespace package. src/data/ survives that collision only
because src/data/__init__.py exists -- a regular package outranks a namespace portion found earlier
-- and it was confirmed present (0 bytes) before this file was written. THE ENTRY POINT MUST DO
`sys.path.insert(0, <root>/src)`, never `PYTHONPATH=src` from the root.

G9, THE TYPO NET. `environ` is a parameter and never a read: spine/lever.py is the only file in the
tree that may name os.environ (check O1), and build() warns loudly when it is handed None because
registry.unread_env then has no mapping to scan and a misspelled knob is silently the default. Pass
the process environment in from the entry point.
"""

# NOT `from spine.assemble import build, render`, and not a re-export of anything.
#
# That line shipped here for four commits and it REOPENED THE ROUTE O10 EXISTS TO CLOSE. Making
# `build` an attribute of the module `spine.compose` meant `from spine.compose import build` in a
# package: O10 was asking `if "assemble" in tail or "registry" in tail`, the tail of `spine.compose`
# is ["spine", "compose"], and `spine` is explicitly removed from the package set -- so the import
# read as ordinary and permitted. A reviewer walked through it and a memory module returned
# FAB.alpha=0.9 and LM.dropout=0.37 from the live environment with all ten ownership checks and all
# five contract checks green. Reproduced here before it was changed.
# `render` was never called from this file at all, so the re-export bought nothing and cost that.
#
# O10 is now an ALLOWLIST -- spine.{lever, units, derive, rng, wire} and nothing else under spine --
# so a future module here holding a convenient name is refused until someone adds it on purpose. The
# private alias below is belt-and-braces: it is not what makes the boundary hold.
from spine.assemble import build as _build

from capacity import api as cap_api
from ckpt import api as ckpt_api
from data import api as data_api
from domains import api as dom_api
from eval import api as eval_api
from fabric import api as fab_api
from lm import api as lm_api
from memory import api as mem_api
from opt import api as opt_api
from sig import api as sig_api
from tok import api as tok_api
from train import api as run_api
from world import api as world_api


# ==================================================================================================
# THE PACKAGE MAP
#
# PREFIX -> the module holding that package's frozen public surface. Written out rather than
# discovered by walking src/, because a discovered map is a map that silently shrinks when a
# directory is renamed, and this table is what tests/test_contract.py checks the contract document
# against. Keys are the PREFIXes spine.assemble.PACKAGES declares; a disagreement is a failure.
# ==================================================================================================

APIS = {
    "CAP": cap_api, "CKPT": ckpt_api, "DATA": data_api, "DOM": dom_api, "EVAL": eval_api,
    "FAB": fab_api, "LM": lm_api, "MEM": mem_api, "OPT": opt_api, "SIG": sig_api,
    "TOK": tok_api, "RUN": run_api, "WORLD": world_api,
}

# The RNG subsystems this root asks spine.rng for, by name. One per package that draws, plus the
# per-epoch stream names DATA derives itself. rng.issued() is then the DID-IT-FIRE surface for the
# whole randomness story: a subsystem present with ZERO DRAWS is armed-but-inert, and a subsystem
# ABSENT never asked. Those are two different statements and G4 requires the report to make both.
RNG_SUBSYSTEMS = ("lm", "sig", "fabric", "memory", "domains", "world", "tok.dropout",
                  "data.synth", "data.holdout", "eval")
# "data.holdout" IS A PARENT, NOT A STREAM ANYTHING DRAWS FROM (Q-DATA-6, 2026-09-02). DATA opens one
# CHILD per area -- rng_for("data.holdout." + key, seed), the key being the area label normalised to
# rng.py's charset -- because a single stream draws the areas in list order, which makes every area's
# held-out block position a function of how many areas were drawn before it. EVAL's held-out window
# already declares the opposite property ("KEYED BY DOMAIN NAME, not by index, so adding a domain does
# not shift the comparison"), and the add-an-area resume is the run both halves exist for. This is the
# same shape as the per-epoch "data.stream.e<n>" names above: DATA derives the child, the parent is
# what is declared here, and rng.py::_check_name makes the dot the supported separator.
# "eval" IS A DRAWN PARENT WITH DERIVED CHILDREN OF ITS OWN (Q-EVAL-9, 2026-09-02), and it is NOT
# re-declared per child for the same reason "data.stream.e<n>" is not: the child is derived by the
# package from a name this tuple already carries. EVAL.holdout_probe draws each domain's held-out
# window starts ONCE from rng_for("eval.holdout." + domain_name, seed) so that every probe in a run
# and across a resume scores the IDENTICAL byte windows and the 2-sigma verdict is computed on
# PAIRED differences. If that stream advanced between probes the pairing would be lost silently and
# no check in this tree would see it -- rng.issued() is the only surface that can say a domain's
# holdout stream was never drawn, which is why the draw is named rather than left to P5.
# "world" WAS MISSING AND THE ROOT REACHED FOR IT WITH .get(), so WORLD.build received rng=None for
# the life of every run. The four sibling constructors all use streams["name"], which raises on a
# missing key; this one line used .get() and returned None instead, and world/api.py::build takes rng as
# a REQUIRED keyword. It is the silent-default shape, in the file whose comment two lines above says
# a subsystem ABSENT from rng.issued() means "never asked" -- so the report would have said WORLD
# never asked for randomness, on a run where WORLD asked and was handed None. That is a third state
# G4 has no name for, and it is worse than either of the two it distinguishes.
# K8 below refuses .get() on the stream map and checks every key against this tuple.


# ==================================================================================================
# THE ORDER, AS DATA
#
# Every row is (stage, PREFIX, entry point, what it receives that is not its own Config, what it
# PRODUCES for later rows). A row that yields nothing a later row consumes -- a refusal, a save, a
# counter read -- keeps FOUR elements, and that is a statement rather than a default. It is a table
# rather than a comment so that docs/04_CONTRACT.md and tests/test_contract.py read the SAME
# statement the code executes -- the old tree's report path and audit path printing different
# numbers for one quantity is the failure that rule exists to end.
#
# WHY THERE IS A FIFTH COLUMN, AND WHAT IT COST TO FIND OUT.
# The four-column shape claimed a standard it could not check. This file's own header said a row is
# "what it receives", and the deferral written for EVAL.holdout_probe stated the rule outright --
# "the root has no join that produces that pair; writing a row now would name a call whose arguments
# nothing supplies" -- and then EVAL.curve_probe, whose signature was then BYTE-IDENTICAL to
# holdout_probe's (it gained `step` on 2026-09-04 under Q-EVAL-11, which changes nothing about
# this argument), carried a row whose entire prose was `Cadences.due('curve', ...)`, naming neither
# argument, with no producer anywhere. The same gap earned a deferral in one place and a row in the
# other, and the header cited the rowed one as proof the standard was about arguments rather than
# phase.
# Two mechanical heuristics were tried against it and both failed. "The row must restate every
# required argument" gave 30 findings, almost all of them rows declining to repeat `h`, `step`,
# `now` and `x` -- which turns the tables into a second copy of the signatures, the one thing this
# design exists to prevent. "The name must appear somewhere else in compose.py" gave 25, flagging
# LM.lm_loss's `y` and FAB.forward's `h`, both produced by the row immediately above. Neither can
# separate PRODUCED BY AN EARLIER ROW from MENTIONED IN PASSING, because the tables did not record
# what a row produces. They do now, and tests/test_contract.py's K10 reads the column.
#
# THE COLUMN SPELLS THE CONSUMER'S NAME, NOT THE PRODUCER'S FIELD. `DATA.open_areas` yields
# `Areas.bodies` and TOK.build_vocabulary takes it as `area_heads`, so the column says `area_heads`
# and names the field beside it. The rename is the ROOT'S -- that is this file's job -- and writing
# the consumer's spelling is what makes "nothing supplies this argument" a decidable question
# instead of a judgement call. Where one value crosses under several spellings (RunClock.step is
# `step`, `step_windows` and `now`; Snapshot.payload is `state`, `saved`, `sd`, `restored` and
# `resume`) the column lists every one, because a check that matched on the producer's field would
# report four live joins as missing.
#
# WHAT THE COLUMN IS NOT ALLOWED TO DO. It may not name a value nothing produces in order to make a
# row pass. Where an argument has no producer the three legal moves are: put it in the producing
# row's column; produce it with a NAMED JOIN in this file and say so in the row (or in
# ROW_ARGUMENTS_ELSEWHERE below); or move the entry point to DEFERRED_ENTRY_POINTS with the missing
# producer as the reason. Seven entry points took the third route in this edit and each one names
# what would close it. That is not a retreat: EVAL.holdout_probe already earned it, and the defect
# was never the deferral, it was the same gap earning a row here and a deferral there.
#
# ORDER IS LOAD-BEARING HERE, unlike in assemble.COUPLINGS. A Config can be resolved in any order
# because no coupling reads another coupling's output; an OBJECT graph cannot, because the
# tokenizer must have measured bytes/token before SIG can be given its width, and DATA cannot be
# planned before that measurement exists. Each row below names what forces its position. K10 folds
# ASSEMBLY_ORDER and then LOOP_ORDER in SOURCE ORDER and asks whether an EARLIER row produced each
# argument, so a value that crosses BACKWARDS -- the previous flush's `novelty`, the previous
# window's boundary, the previous cycle's `best_bpb` -- cannot be expressed in the column at all.
# Those are feedback edges, the loop has at least three, and each one is written into the consuming
# row's own note as a previous-iteration value rather than smuggled into a producer's column.
#
# WHY THE TWO-TABLE SHAPE WAS NOT ENOUGH, AND WHY THERE IS STILL NO THIRD TABLE.
# The first version of these tables had two stage letters, A (per window) and B (per flush), and 56
# of the 117 entry points were named by no row at all -- tests/test_contract.py's K6 measures it.
# Three whole LEVELS were missing rather than three rows:
#   * THE EPOCH. Nothing drew a stream, began an epoch or rolled one, so RUN.epochs was inert, the
#     LR horizon annealed over a run length the loop could not reach, and DATA.draw_stream -- the
#     function that produces the bytes -- had no caller.
#   * THE CHECKPOINT FAN-OUT AND THE RESUME. Every package's state_dict/load_state existed and
#     nothing named any of them. They are NOT reachable from inside CKPT: `save(ckpt, *, payload,
#     geometry, step, epoch, reason, suffix)` receives no package object and no foreign Config, and
#     `load(ckpt)` runs BEFORE the objects it would have to restore into exist. O10 forbids the
#     import that would be needed even if the timing worked. So each one is a row.
#   * THE COUNTER COLLECTION. No row collected any counters(), so for every orphan above the
#     evidence was doubly unreachable: the owning function was never called AND its gate never went
#     through Cadences.due, so Cadences.ledger() had no key for it either. NEVER ASKED and ASKED AND
#     REFUSED were indistinguishable, which is what the RNG_SUBSYSTEMS comment above says G4 forbids.
# The repair is THREE NEW STAGE VALUES in LOOP_ORDER (E, C, R) and four new ones in ASSEMBLY_ORDER
# (resume, restore, stream/segment, persist), not a third table. Two reasons, and the second is the
# load-bearing one:
#   1. Every level added below is driven by the SAME RunClock -- E is entered when Tick.rolled comes
#      back from RunClock.advance, C is entered from a save site inside A/B/R, R when Tick.finished
#      is True. A separate table would split one clock's reading order across two files' worth of
#      data and invite exactly the drift these tables exist to prevent.
#   2. tests/test_contract.py reads the tables BY NAME -- _named_by_orders and _rows_with_prose
#      walk the assignments whose target id is "ASSEMBLY_ORDER" or "LOOP_ORDER" and nothing
#      else. A third table would be invisible to
#      the one check that exists because these rows were missing, so its rows would still report as
#      orphans. A level with a table of its own that no check can see is still an orphan.
# ==================================================================================================

ASSEMBLY_ORDER = (
    ("process",   "RUN",   "process_setup",   "() -- first, before any tensor: tf32 and autocast "
                                              "are process-wide and a package built before them "
                                              "would be built under different arithmetic",
                                              "device -- Process.device. Six constructors take it "
                                              "under exactly that spelling: LM.build_model, "
                                              "SIG.build, FAB.build, WORLD.build, MEM.open_store "
                                              "and DOM.open_partition"),
    ("process",   "RUN",   "mode",            "() -- decides whether the eval battery runs at all",
                                              "timing -- RunMode.timing, which only RUN's own "
                                              "bench_summary takes; `bench` and `profile` are "
                                              "branch conditions the root reads, not arguments"),
    ("process",   "RUN",   "streams",         "(subsystems=RNG_SUBSYSTEMS) -- every package's stream is minted "
                                              "here so rng.issued() has one register",
                                              "rng -- the per-subsystem generator MEM.open_store, "
                                              "DOM.open_partition and WORLD.build take under that "
                                              "name; generator -- the SAME object under SIG.build's "
                                              "and FAB.build's spelling. One mint, two spellings, "
                                              "both of them this file's"),

    # -- THE RESUME PATH. It is READ here and APPLIED at the `restore` rows below, each of which
    # sits immediately after its own package's constructor because it takes the live object.
    ("resume",    "CKPT",  "resume_source",   "() -- ONE spelling of unset (ckpt/api.py::install_save_signal); it "
                                              "must precede load, and load must precede every "
                                              "constructor that takes restored=, which is why the "
                                              "whole resume is read before the first refusal"),
    ("resume",    "CKPT",  "load",            "() -> Snapshot(payload, geometry, step, epoch, "
                                              "best_state) or None. HERE and not inside a package: "
                                              "CKPT.save takes `payload` as an ARGUMENT and load "
                                              "runs before the objects exist, so the fan-out cannot "
                                              "live inside this package even if O10 allowed it",
                                              "state -- Snapshot.payload, under the spelling "
                                              "DATA.restore_stream_state, TOK.restore_vocab and "
                                              "CAP.restore use; "
                                              "saved -- Snapshot.payload again, LM.load_state's and "
                                              "OPT.load_state's spelling; "
                                              "sd -- Snapshot.payload again, for SIG.load_state_dict, "
                                              "FAB.load_state_dict and WORLD.load_into; "
                                              "restored -- Snapshot.payload again, for MEM.open_store, "
                                              "DOM.open_partition, CAP.new_valve and "
                                              "CKPT.new_retention; "
                                              "snapshot -- the Snapshot itself, CKPT.check_geometry's "
                                              "first positional; "
                                              "best_state -- CKPT.new_retention's restored argument; "
                                              "resume_step -- Snapshot.step, RunClock's seed; "
                                              "resume_epoch -- Snapshot.epoch, the same. "
                                              "ONE FIELD UNDER FOUR SPELLINGS -- state, saved, sd, "
                                              "restored -- plus the name `payload` itself, which is "
                                              "five; it was six until 2026-09-02, when OPT.build's "
                                              "`resume` spelling was removed with the parameter "
                                              "(Q-OPT-4 (d)). Each is written as "
                                              "its own entry because a column read as prose gave the "
                                              "PRODUCER side the same hole the consumer side had. "
                                              "THE TOKEN "
                                              "NAMES THE PARENT'S BLOB: what CKPT.save takes at C "
                                              "is the map the C rows assemble, and the two are the "
                                              "same word for a load and a save. It does "
                                              "NOT yield the word check_geometry's argument is "
                                              "spelled with: the RECORDED manifest and the LIVE one "
                                              "are opposite sides of one comparison, and a column "
                                              "naming the bare token would make K10 pass on the "
                                              "wrong object. ROW_ARGUMENTS_ELSEWHERE holds that one"),

    ("refuse",    "RUN",   "startup_refusals","(disk_stream=DATA.resample) -- a TWO-PACKAGE guard "
                                              "that can live in neither levers.py"),
    ("refuse",    "WORLD", "startup_refusals","(ctx_tokens=LM.ctx)"),
    ("geometry",  "LM",    "resolve",         "() -- refuses width % heads and the ctx/pos_max "
                                              "overflow BEFORE a tensor is allocated",
                                              "geom -- the LMGeometry LM.build_model, LM.load_state "
                                              "and LM.state_dict all take under that name, and the "
                                              "AUTHORITY for the shapes four rows below spell as "
                                              "LM.width / LM.ctx / vocab_slots: _geometry_manifest "
                                              "replaces the raw lever read with the resolved value "
                                              "(the manifest's own resolve loop), because two producers for "
                                              "one shape is how the encoder width was resolved as "
                                              "614 on one path and 1 on the other"),
    ("corpus",    "DATA",  "open_areas",      "(seed=RUN.seed) -- reads disk; nothing above this touched it",
                                              "area_heads -- Areas.bodies, which is the spelling "
                                              "TOK.build_vocabulary takes and what the body already "
                                              "passes at the vocabulary call). The row below said `Areas "
                                              "heads`, a field this record does not have -- "
                                              "the declaration is names / bodies / holdout / "
                                              "holdout_bytes / bytes_present / bytes_taken / "
                                              "cursors / rng_holdout. Areas.holdout and "
                                              "Areas.holdout_bytes leave here too and NOTHING takes "
                                              "them: they are the material EVAL.holdout_probe is "
                                              "deferred for"),
    ("restore",   "DATA",  "restore_stream_state", "(areas, Snapshot.payload['DATA'] as `state`) -- "
                                              "AFTER open_areas because it refuses on the holdout "
                                              "offsets open_areas just produced, and BEFORE "
                                              "data_plan so the plan is computed against the "
                                              "restored split. A refusal: it yields nothing"),
    ("vocab",     "TOK",   "build_vocabulary","(area_heads=Areas.bodies, seed=RUN.seed, soft_cap=CAP's "
                                              "`vocab_start` lever, readable off the frozen Config "
                                              "at any point -- NOT CAP's "
                                              "restored ceiling, which is thirty rows away and is "
                                              "the whole of M38; the body passes None today) -- "
                                              "MEASURES bytes/token, which three later rows need",
                                              "vocab = Vocabulary -- the record itself, which TOK.restore_vocab "
                                              "and TOK.save_vocabulary both take and which nothing "
                                              "else in the tree mints; bytes_per_token -- "
                                              "DATA.data_plan's argument and _signature_width's "
                                              "input; live_vocab -- "
                                              "Vocabulary.size() under LM.decode's spelling, and NOT "
                                              "live_size: decode uses this number as the INDEX where "
                                              "never-minted rows begin, and ids are positional "
                                              "because retire() pops from the match table while "
                                              "leaving id2bytes intact. live_size is size minus the "
                                              "retired count, so passing it moves the boundary down "
                                              "and masks that many LIVE rows to -inf. This row said "
                                              "live_size until 2026-09-03 and would have "
                                              "reintroduced that defect the moment it was wired; "
                                              "retired rows are handled separately, BY ID; "
                                              "retired_ids -- Vocabulary.retired under LM.decode's. "
                                              "THIS ROW IS THE FIRST-FLUSH PRODUCER OF BOTH: "
                                              "TOK.judge_probation refreshes them at B, twenty-six "
                                              "rows later, so on the first flush of every run the "
                                              "vocabulary is the only honest source"),
    ("restore",   "TOK",   "restore_vocab",   "(Snapshot.payload['TOK'], vocab) -- AFTER "
                                              "build_vocabulary has replayed the parent's merges "
                                              "from d_vocab_read_path: the refusal it owns compares "
                                              "the state's merge count against the vocabulary that "
                                              "was just built, so it has nothing to compare before"),
    ("gate",      "CKPT",  "check_geometry",  "(Snapshot, the LIVE manifest -- see "
                                              "ROW_ARGUMENTS_ELSEWHERE, which names its producer "
                                              "rather than repeating a word that means the OTHER "
                                              "side of this comparison one row up) -- THE LAST ROW "
                                              "BEFORE ANY PARAMETER EXISTS. build_model below is "
                                              "the first allocation, and the old gate at :4413-4468 "
                                              "fired only after the tokenizer had resolved and the "
                                              "corpus had been pulled. The manifest is assembled by "
                                              "_geometry_manifest() from LM.resolve's LMGeometry "
                                              "and the EXACT fields readable off the frozen "
                                              "Configs. WHAT THE SNAPSHOT SIDE MUST CARRY FOR THIS "
                                              "GATE TO COMPARE ANYTHING was the C-stage question, "
                                              "and it is ANSWERED: ROW_ARGUMENTS_ELSEWHERE says "
                                              "CKPT.save's geometry IS _geometry_manifest(sysm), "
                                              "the same function the child calls on the way back "
                                              "in, so the recorded key set is byte-identical to the "
                                              "live one and the missing-field set is EMPTY by "
                                              "construction (Q-CKPT-2, first half resolved "
                                              "2026-08-30; ISSUES P1-C12 withdrawn as filed). THE "
                                              "FIELD COUNT IS NOT WRITTEN HERE, DELIBERATELY. It "
                                              "was written in four places and three of them went "
                                              "stale inside one week -- 15, 16, 20 -- so the count "
                                              "lives at _geometry_manifest and nowhere else, and a "
                                              "reader who needs it runs the function. What this row "
                                              "still owes the reader is the DIRECTION rule, because "
                                              "it is the thing that keeps being confused: "
                                              "ckpt/api.py specifies that a field in the LIVE "
                                              "manifest and absent from the RECORDING is a REFUSAL "
                                              "-- 'A MISSING FIELD IS A REFUSAL, NOT A SKIP ... the "
                                              "comparison is driven off the manifest's KEY SET "
                                              "rather than off truthiness' -- while UNCHECKED is "
                                              "the OTHER direction, recorded and absent from the "
                                              "manifest, which is where WORLD's grown counts sit. "
                                              "Three statements here had them the wrong way round. "
                                              "The two SIDECAR refusals below remain disarmed and "
                                              "are the RESIDUE of Q-CKPT-2, which is HIGH and not "
                                              "blocking. The GROWN population counts genuinely "
                                              "cannot be here (they need a built object) and are "
                                              "re-refused by WORLD.load_into and FAB.load_state_dict"),
    ("plan",      "DATA",  "data_plan",       "(epochs=RUN.epochs, win_tokens=LM.ctx, "
                                              "bytes_per_token=Vocabulary.bytes_per_token) -- the "
                                              "exposure gates, before a single step runs",
                                              "plan -- the Plan both DATA.draw_stream rows take as "
                                              "their second positional. Plan carries NO length: "
                                              "the run's extent is MEASURED off the segmentation "
                                              "two rows down, never read off this record"),
    ("stream",    "DATA",  "draw_stream",     "(areas, plan, epoch=0, seed=RUN.seed) -- EPOCH 0's "
                                              "draw, and it is here rather than only at stage E "
                                              "because two rows below need the material: OPT.build "
                                              "needs run_windows MEASURED from the segmentation "
                                              "(opt/api.py::build) and SIG.warm_up takes the stream. The "
                                              "old tree has the same duplication -- :4104 and :6513 "
                                              "both call _resample()",
                                              "data -- Stream.bytes under TOK.tokenize's spelling; "
                                              "labels -- Stream.labels; stream -- the same bytes "
                                              "under SIG.warm_up's and SIG.train_step's spelling "
                                              "when sig.space is 'bytes' (_signature_stream picks "
                                              "the arm). Stream.splice_starts and "
                                              "Stream.area_changes also leave this package and NO "
                                              "PARAMETER in the tree names either: produced for a "
                                              "consumer P5/P6 has not written yet, which is the "
                                              "mirror image of an argument with no producer and is "
                                              "recorded here rather than left silent"),
    ("segment",   "TOK",   "tokenize",        "(vocab, data=Stream.bytes, labels=Stream.labels, "
                                              "regularize=True, seed) -- the epoch-0 segmentation. "
                                              "It is the ONLY producer of a window count: "
                                              "len(Segmentation.ids) // LM.ctx, never "
                                              "stream_bytes // ctx, which divides a BYTE budget by a "
                                              "TOKEN window and overstates it by the compression "
                                              "ratio. THE ROOT PRINTS ONE LINE AFTER THIS ROW, ON "
                                              "EVERY RUN: stream_bytes, len(Segmentation.ids), the "
                                              "measured bytes_per_token, windows_in_epoch and "
                                              "run_windows TOGETHER, so the ratio is checkable by "
                                              "eye. It is here and not in RUN.bench_summary, which "
                                              "can reach none of the five and returns None when "
                                              "bench is off (Q-DATA-8)",
                                              "ids -- Segmentation.ids, which TOK.on_window takes "
                                              "one window of; positions -- Segmentation.byte_pos "
                                              "under MEM.write's spelling, TRUE BYTE OFFSETS and "
                                              "not an arange; windows_in_epoch and run_windows -- "
                                              "through the named joins _windows_in_epoch and "
                                              "_run_windows, the second in units.Windows because "
                                              "derive.cadences_that_cannot_fire and "
                                              "derive.opt_steps_from_windows both refuse a bare "
                                              "int; bytes_per_window -- LM.ctx times "
                                              "Segmentation.bytes_per_token through "
                                              "_bytes_per_window, which is RUN.bench_summary's "
                                              "spelling; stream -- Segmentation.ids under SIG's "
                                              "spelling on the token arm of _signature_stream"),
    ("model",     "LM",    "build_model",     "(geom, device=RUN.device, seed=RUN.seed)",
                                              "NOT key_fn, which is _key_fn's partial application and is named on MEM.write's exemption; the old claim read: LM's encoder bound to (lm, model) by "
                                              "_key_fn, which is MEM.write's and MEM.maintain's "
                                              "spelling; head -- LM's decoder bound by _head, "
                                              "which is FAB.forward's. Both are ENTRY POINTS "
                                              "PARTIALLY APPLIED BY THIS FILE, not returns: the "
                                              "callable class of argument has no other producer, "
                                              "and the four rows that take one name the join"),
    ("restore",   "LM",    "load_state",      "(model, geom, saved=Snapshot.payload['LM']) -> "
                                              "LoadReport, which nothing takes as an argument"),
    ("signature", "SIG",   "build",           "(width_units=derive.signature_width_bytes(LM.ctx, "
                                              "bytes_per_token), alphabet_size, device, generator) "
                                              "-- the ONE width, resolved once, here",
                                              "encode -- SIG.encode bound to the SigState by "
                                              "_sig_encode_fn, which is DOM.rekey's spelling for "
                                              "the same callable"),
    ("restore",   "SIG",   "load_state_dict", "(st, sd=Snapshot.payload['SIG'], "
                                              "sidecar=_sidecar(sysm, restored, 'SIG'), which reads "
                                              "the snapshot's "
                                              "recorded manifest under the key 'SIG'. NOTHING "
                                              "WRITES THAT KEY: the C rows record WORLD.geometry "
                                              "alone, so the sidecar is None on every real resume "
                                              "and the width_units/alphabet_size/space/d/mode "
                                              "refusal this row exists for is DISARMED until the "
                                              "save side records a per-prefix slice. That is the "
                                              "untrippable-guard shape, stated rather than left "
                                              "looking armed; _sidecar now records the disarmed "
                                              "state on System.warnings and Q-CKPT-2 asks for the "
                                              "producer)"),
    ("fabric",    "FAB",   "build",           "(d_model=LM.width, signature_dim=SIG.d, device, "
                                              "generator)",
                                              "live_experts -- Population.n_live under "
                                              "CAP.startup_refusals's spelling. Population declares "
                                              "no parameters(), and _base_parameters harvests it by "
                                              "getattr: if P4 does not add one the fabric "
                                              "contributes ZERO parameters to the optimizer, so "
                                              "that helper records the absence instead of "
                                              "skipping in silence"),
    ("restore",   "FAB",   "load_state_dict", "(pop, sd=Snapshot.payload['FAB'], "
                                              "sidecar=_sidecar(sysm, restored, 'FAB') -- slots "
                                              "MAY_WIDEN, rank and dk "
                                              "EXACT. SAME DISARMED REFUSAL AS SIG'S, and worse by "
                                              "one step: FAB.state_dict does not even CLAIM to emit "
                                              "a sidecar the way sig/api.py::warm_up does, so this "
                                              "row refuses on a value with no declared origin at "
                                              "either end. Q-CKPT-2)"),
    ("world",     "WORLD", "build",           "(d_model=LM.width, device, ctx_tokens=LM.ctx, rng)"),
    ("restore",   "WORLD", "load_into",       "(w, sd=Snapshot.payload['WORLD']) -- STRICTLY BEFORE "
                                              "OPT.build. WORLD.manage mints parameters mid-run "
                                              "through add_param_group, so a checkpoint taken after "
                                              "growth has more groups than a freshly built "
                                              "optimizer; replaying the population first is what "
                                              "lets OPT be built with the SAME group structure, and "
                                              "without it OPT's param_group_shape refusal fires on "
                                              "every resume of a run that ever grew (:4580-4599). "
                                              "That refusal is itself written against a field "
                                              "OPT.state_dict never says it writes -- opt/api.py::maybe_step "
                                              "against :273-276, and OptState declares no such "
                                              "field -- so the ordering constraint this row exists "
                                              "for currently protects a guard that cannot fire"),
    ("store",     "MEM",   "open_store",      "(key_dim=LM.width, vocab_slots=LM.vocab_slots, "
                                              "device, rng, lm_kind=LM.arch, restored)"),
    ("partition", "DOM",   "open_partition",  "(sig_dim=SIG.d, vocab_slots=LM.vocab_slots, device, "
                                              "rng, restored)"),
    ("valve",     "CAP",   "new_valve",       "(restored=Snapshot.payload['CAP']) -- both hard "
                                              "ceilings arrive as wires",
                                              "valve -- the Valve every later CAP row takes. "
                                              "CAP.state(valve) declares no Config at all, so it "
                                              "is the one entry point whose live object cannot be "
                                              "recognised by position and has to be produced here "
                                              "like any other value"),
    ("restore",   "CAP",   "restore",         "(valve, state=Snapshot.payload['CAP']) -- "
                                              "new_valve's `restored` is the LIFTED CAP ALONE, "
                                              "because Valve.origin has to record where the "
                                              "STARTING cap came from; this row puts back what that "
                                              "one argument cannot carry -- the two pin clocks and "
                                              "the high-water marks, which is the other half of M38 "
                                              "-- and it precedes the refusal below so the refusal "
                                              "is taken against the restored ceiling"),
    ("refuse",    "CAP",   "startup_refusals","(live_experts=Population.n_live)"),
    ("optimizer", "OPT",   "build",           "(param_groups={'base': _base_parameters(sysm), which "
                                              "walks LM's model, FAB's population and WORLD's world "
                                              "-- THREE OBJECTS, NOT FOUR: this row said LM+FAB+"
                                              "WORLD+MEM until 2026-08-30 and MEM has no module and "
                                              "no parameters at all; 'encoder': "
                                              "SIG.encoder_parameters()}, "
                                              "run_windows=_run_windows(sysm) in units.Windows) -- "
                                              "OPT never walks a module tree. THE `resume` "
                                              "PARAMETER IS GONE as of 2026-09-02 (Q-OPT-4 (d), a "
                                              "frozen signature moved): the module restores run "
                                              "STRICTLY BEFORE this row so the groups already carry "
                                              "the checkpoint's structure, leaving build no "
                                              "structural work and no counters for a second restore "
                                              "path",
                                              "opt.base -- the AdamW over param_groups['base'], "
                                              "which maybe_step steps; opt.encoder -- the AdamW "
                                              "over param_groups['encoder'], which is what "
                                              "SIG.warm_up and SIG.train_step take under the "
                                              "spelling `opt`. THE TWO FIELDS ARE NAMED as of "
                                              "2026-09-02 (Q-OPT-7 RESOLVED (a)): OptState said "
                                              "'both AdamW instances' and named neither, so the "
                                              "root could not address one, SIG was handed the whole "
                                              "state and could have stepped the language model, and "
                                              "WORLD.manage's add_param_group deferral cited the "
                                              "identical hole. K11 resolves a produces token against "
                                              "the module's RECORD TYPES block, so `encoder` is now "
                                              "checkable provenance"),
    ("restore",   "OPT",   "load_state",      "(st, saved=Snapshot.payload['OPT']) -- AFTER build "
                                              "because the param_group_shape refusal (ISSUES P1-L50) "
                                              "compares the saved shape against the LIVE groups, "
                                              "which do not exist until build returns. It is the "
                                              "entry point that carries opt.ckpt.loaded/refused, "
                                              "and as of 2026-09-02 it is the ONLY OPT restore path "
                                              "(Q-OPT-4). OPT.state_dict now declares it writes "
                                              "param_group_shape, which it did not, so the refusal "
                                              "compares against a value something produces instead "
                                              "of being untrippable"),
    ("clock",     "RUN",   "new_clock",       "(batch_windows=OPT.batch_windows, accum=OPT.accum, "
                                              "resume_step, resume_epoch)",
                                              "clock -- the RunClock every Cadences.due gate is "
                                              "handed; step -- RunClock.step (units.Windows) under "
                                              "the spelling TOK.on_window, TOK.mint_burst, "
                                              "TOK.judge_probation, CKPT.Retention.consider and "
                                              "CKPT.save use; step_windows = step -- the SAME counter "
                                              "under SIG.cadence_due's, FAB.manage's, "
                                              "FAB.forward's and FAB.grow_check's; now = step -- the same "
                                              "again under MEM.write's, MEM.maintain's, "
                                              "DOM.observe's and DOM.manage's; epoch -- "
                                              "RunClock.epoch, taken by DATA.draw_stream at E and "
                                              "by CKPT.save at C. ONE CLOCK, FOUR SPELLINGS, and "
                                              "the renames are this file's"),
    ("epoch0",    "RUN",   "RunClock.begin_epoch", "(windows_in_epoch=len(Segmentation.ids)//LM.ctx "
                                              "through _windows_in_epoch) -- epoch 0's length, "
                                              "MEASURED on the stream that actually exists. It is "
                                              "here and not only at stage E because the first epoch "
                                              "is never rolled into, and it needs the clock the row "
                                              "above builds"),
    ("warmup",    "SIG",   "warm_up",         "(stream=the epoch-0 unit stream in SIG's alphabet, "
                                              "seen_units=the WHOLE stream through "
                                              "_signature_units, opt=OPT's ENCODER optimizer) -- "
                                              "pre-loop by definition (sig/api.py::train_step) and "
                                              "therefore after BOTH the stream rows and the "
                                              "optimizer row; its budget is units.Steps on its own "
                                              "local counter and is never compared to a Windows "
                                              "cadence. Its verdict 'collapsing' is a RUN-LEVEL "
                                              "FAILURE, not a warning, and NO signature in the tree "
                                              "takes that verdict -- it is a WarmupReport the root "
                                              "must act on itself. THE RETURN IS BOUND: this row "
                                              "yields no argument any later row consumes, so it "
                                              "carries no produces column, and the record lands on "
                                              "System.warmup instead. A 'collapsing' verdict also "
                                              "puts a line on System.warnings, and that line SAYS "
                                              "it is a carrier rather than a classification: what "
                                              "acting on the verdict IS -- refuse the run, or run "
                                              "it and mark the report -- is stated by neither "
                                              "sig/api.py::warm_up nor the contract, and is not "
                                              "decided at this call site. Until 2026-09-04 the "
                                              "call was a bare expression statement and this "
                                              "sentence stood over a discarded value. opt is "
                                              "sysm.optimizer.encoder -- the AdamW over "
                                              "param_groups['encoder'], NOT the whole OptState, "
                                              "which is what crossed until 2026-09-02 because "
                                              "OptState was declared as 'both AdamW instances' and "
                                              "named neither (Q-OPT-7 RESOLVED (a))"),
    ("cadence",   "RUN",   "new_cadences",    "(periods={'curve': EVAL.curve_period(ev), "
                                              "'dom.manage': DOM.manage_period(dom), 'fab.manage': "
                                              "FAB.manage_period(fab), 'dom.rekey': "
                                              "MEM.rekey_period(mem), 'ckpt': CKPT.save_period(ck), "
                                              "'progress': RUN.PROGRESS_WINDOWS}) "
                                              "-- the SIX gates the loop evaluates, each period "
                                              "supplied by the package that DECLARES its kind. Five "
                                              "arrive through a typed accessor because a Config "
                                              "hands back a bare int for a Clock-unit LEVER; the "
                                              "sixth is RUN's own module CONSTANT, written "
                                              "units.Windows at its definition, so it needs no "
                                              "accessor and mints no entry point -- Q-RUN-1, "
                                              "RESOLVED 2026-09-02. 'progress' is the ONLY key here "
                                              "with no row of its own: no entry point prints the "
                                              "progress/ETA line, the loop driver does. "
                                              "new_cadences took no periods at all until 2026-08-30 "
                                              "while its docstring said every period is an "
                                              "argument; the CALL SITE was still passing none until "
                                              "this edit, which is a TypeError the moment "
                                              "RUN.process_setup gets a body -- a defect hidden "
                                              "behind an earlier stub, this file's oldest shape. "
                                              "'curve' STAYS IN THE MAPPING while EVAL.curve_probe "
                                              "is deferred, so the ledger reads a declared key with "
                                              "checks == 0: DECLARED AND NEVER ASKED, which is a "
                                              "different statement from armed-and-inert and G4 "
                                              "requires both"),
    ("audit",     "RUN",   "cadence_audit",   "(run_windows=_run_windows(sysm), which measures "
                                              "len(Segmentation.ids)//LM.ctx times RUN.epochs -- NOT "
                                              "'Plan's measured length', a field Plan does not have "
                                              "(data/api.py::<module>) and the same wrong fact "
                                              "_run_windows' own docstring already caught once; "
                                              "periods=the SAME mapping) -- states which of those "
                                              "five cannot fire at this run's length BEFORE the "
                                              "first window. At the shipped defaults a run is at "
                                              "most 937 windows and ten cadence defaults are longer "
                                              "(ISSUES P1-C11), so without this a green P3 certifies a "
                                              "system in which every cadenced mechanism fired zero "
                                              "times. It states, it does not raise: a short run is "
                                              "legitimate, a report that cannot tell 'ran and did "
                                              "nothing' from 'never reached' is not. AFTER "
                                              "new_cadences because it takes the same mapping, and "
                                              "after DATA.data_plan because run_windows needs the "
                                              "MEASURED bytes/token. The row existed and the CALL "
                                              "DID NOT until this edit"),
    ("persist",   "CKPT",  "saving_on",       "() -- recorded ONCE on the System and consulted by "
                                              "every save site; it must precede new_retention, whose "
                                              "inert_reason is populated when best_keep > 0 AND "
                                              "SAVING IS OFF (ckpt/api.py::check_geometry). Re-typing the "
                                              "six-spelling test at a call site is the defect that "
                                              "wrote a directory literally named `0`"),
    ("retention", "CKPT",  "new_retention",   "(restored=Snapshot.best_state)"),
    ("signal",    "CKPT",  "install_save_signal", "() -- SIGUSR1; not a lever and needs none"),
)

# What the run does with the assembled system, in the order RUN's clock imposes. NOT EXECUTED HERE
# -- the loop is RUN mechanism. This is the reading order for whoever writes it, and it is data for
# the same reason ASSEMBLY_ORDER is: the contract document and the code must not drift.
#
# FIVE STAGES, all driven by the one RunClock:
#   E = per EPOCH.  Runs before the first window of an epoch and again whenever RunClock.advance
#                   returns Tick.rolled. Epoch 0's E rows are ALSO in ASSEMBLY_ORDER above, because
#                   OPT.build and SIG.warm_up need the material before the loop starts.
#                   PRECEDENCE, AND WHAT IT COSTS AT THE SHIPPED DEFAULTS: advance() sets `rolled`
#                   when the stream is exhausted and the epoch increments, and `finished` when
#                   epoch >= run.epochs. RUN.epochs DEFAULTS TO 1, so the single roll a default run
#                   ever takes sets BOTH -- and `finished` WINS. The loop leaves for R and does not
#                   re-enter E, which means THE E ROWS IN THIS TABLE NEVER RUN ON A ONE-EPOCH RUN.
#                   Epoch 0's draw, segmentation and begin_epoch come from ASSEMBLY_ORDER instead;
#                   "entered once before the first window" and "entered on Tick.rolled" are two
#                   different claims and this table must not blur them. The consequence is not
#                   hypothetical: DATA.resample, the epoch-roll resegmentation and every E-stage
#                   counter read "never reached" rather than "ran and did nothing" at the default,
#                   and the report has to say which.
#   A = per WINDOW, above the batch accumulator.
#   B = per FLUSH.
#   C = the CHECKPOINT FAN-OUT. An EVENT, not a clock: entered from three routes -- B when
#       Cadences.due('ckpt', ...) fires or SIGUSR1 is set, A when Retention.consider returns a
#       BestAction, and R for the final save. The rows are the payload assembly, and they are rows
#       rather than calls inside CKPT.save because that function is handed the finished payload.
#   R = the REPORT, once, after Tick.finished. Every counters()/census()/ledger() call in the tree.
#
# Every PERIODIC gate goes through Cadences.due(key, period, clock) with a period its OWNING package
# supplied, so the modulo form that fired zero times at every BATCH_W > 1 is not writable at a call
# site. EVENT-DRIVEN rows say so and name the event; they invent no cadence and take no period.
# THREE COMPARISONS DO NOT GO THROUGH IT AND EACH IS NAMED WHERE IT HAPPENS: SIG.cadence_due (two
# periods, and `due` takes one), and MEM.maintain's internal probe_every and rekey_every tests
# against a Windows `now`. None has a ledger key, so none has a readable "0 fires" -- their evidence
# is SIG.counters and store.n_probe_fired / n_rekey_passes at stage R, and the rows say so.
#
# THE BATCH ACCUMULATOR IS THE ONE PRODUCER THIS TABLE CANNOT NAME AS A ROW. `x`, `y`, the write
# contexts and the per-window token slice are cut from Segmentation.ids; no entry point returns
# them, because RunClock.advance appends to the accumulator and hands back a Tick, which is a clock.
# The cut therefore has ONE name in this file -- _window_bounds / _flush_bounds -- and the rows that
# consume it say so, rather than each restating a slice nobody wrote down.
LOOP_ORDER = (
    ("E", "DATA",  "draw_stream",     "(areas, plan, epoch=clock.epoch, seed=RUN.seed) -- THE FIRST "
                                      "STATEMENT OF EVERY EPOCH, called UNCONDITIONALLY: dat.resample "
                                      "is read INSIDE (data/api.py::open_areas), so 'every epoch is a "
                                      "byte-identical replay' is a state this package REPORTS rather "
                                      "than a branch the caller takes. The root also stamps "
                                      "clock.opt_steps here as the shift_at that OPT.maybe_step's B "
                                      "row consumes -- a resample is a SELF-INFLICTED shift and the "
                                      "old tree carried that fact in a closure variable (:6518-6521) "
                                      "-- AND, since Q-FAB-6 (2026-09-02), units.Windows(clock.step) "
                                      "on System.shift_at_windows for FAB.grow_check's own shift_at. "
                                      "ONE EVENT, TWO TYPED STAMPS, because the two consumers "
                                      "measure their cooldowns in different clock kinds; the old "
                                      "tree told only the optimizer here and told growth at :6515",
                                      "data -- Stream.bytes under TOK.tokenize's spelling; labels; "
                                      "stream -- the same bytes under SIG's spelling at "
                                      "space='bytes'; NOT shift_at, which comes off the CLOCK and not off this row -- RUN.new_clock produces it and OPT.maybe_step takes it. The old claim read: clock.opt_steps, stamped by the "
                                      "root at this row and consumed by OPT.maybe_step at B"),
    ("E", "TOK",   "tokenize",        "(vocab, data=Stream.bytes, labels=Stream.labels, "
                                      "regularize=True) -- between the draw and begin_epoch, because "
                                      "the window count the next row needs is "
                                      "len(Segmentation.ids)//LM.ctx and that cannot be known until "
                                      "this call returns",
                                      "ids; positions -- Segmentation.byte_pos under MEM.write's "
                                      "spelling; windows_in_epoch and run_windows through "
                                      "_windows_in_epoch and _run_windows; bytes_per_window through "
                                      "_bytes_per_window; stream on the token arm. This is also "
                                      "the call the B row invokes on a retok, and the RetokEvent it "
                                      "is said to return is DECLARED (tok/api.py::<module>) BY NO ENTRY "
                                      "POINT'S DOCSTRING -- tokenize's says Segmentation"),
    ("E", "RUN",   "RunClock.begin_epoch", "(windows_in_epoch=len(Segmentation.ids)//LM.ctx) -- a "
                                      "MEASUREMENT, re-taken every epoch because a resampling stream "
                                      "is a different length each time and minting shortens every "
                                      "later one. THE LENGTH ARRIVES AS A COUNT OF WINDOWS. The "
                                      "partial batch was already dropped by the advance that rolled"),
    ("A", "MEM",   "census",          "THE MANAGEMENT PASS OPENS HERE. Cadences.due('dom.manage', "
                                      "DOM.manage_period(dom), clock) is asked ONCE and the next two "
                                      "rows run inside that one answer: due() RECORDS the fire and "
                                      "returns True, so asking a second time under the same key "
                                      "CONSUMES the event -- the defect that made minting never "
                                      "fire when probation shared its key. reconcile=True, and it "
                                      "is before DOM.manage because manage's memory_counts and "
                                      "mem_floor_entries are REQUIRED arguments with no other "
                                      "producer -- a hole in a row that already existed",
                                      "memory_counts = counts -- DOM.manage's spelling for the "
                                      "per-source counts; "
                                      "mem_floor_entries = floor_entries -- DOM.manage's spelling "
                                      "for the floor it may not cull below. ONE NAME PER ENTRY, because a column "
                                      "reading 'memory_counts and mem_floor_entries -- ...' declares "
                                      "neither: the parser takes the token before `--`, and 'and' is "
                                      "not a name; "
                                      "memory_pressure = pressure -- FAB.grow_check's spelling for "
                                      "main/(main+prob). MEM.census RETURNS StoreCensus, DECLARED "
                                      "in memory/api.py's RECORD TYPES block since 2026-09-02 "
                                      "(Q-MEM-11, RESOLVED (a)); until then the fields were prose "
                                      "and these three `produces` entries passed K11 by "
                                      "word-appearance. The record carries MEM'S OWN spellings "
                                      "(counts, floor_entries, pressure) and THESE ARE THE CONSUMING "
                                      "ones -- the rename lives HERE, in this column, which is the "
                                      "declared home K10 and K11 read. "
                                      "THEY ARE THIS PASS'S NUMBERS AND NOTHING REFRESHES "
                                      "THEM BETWEEN PASSES: FAB.grow_check is a B row and takes "
                                      "memory_pressure every flush, so before the first fire there "
                                      "is no value at all, and at the shipped defaults dom.manage "
                                      "may never fire (C11)"),
    ("A", "DOM",   "manage",          "inside that one pass, not a second Cadences.due; the Plan it "
                                      "returns is handed straight on as "
                                      "MEM.apply_domain_plan(plan=Plan, live_sources=DOM.census's "
                                      "`live`) -- written as the CALL it is, because K6 credits a "
                                      "note only when it names arguments",
                                      "folds and deletions -- Plan.folds and Plan.deletions, "
                                      "MEM.apply_domain_plan's spellings, exact at both ends"),
    ("A", "DOM",   "census",          "the SAME management pass, IMMEDIATELY AFTER manage: its "
                                      "`live` list is what MEM.apply_domain_plan takes as "
                                      "live_sources, which replaces the attribute reach at :6699",
                                      "live_sources -- the `live` list under "
                                      "MEM.apply_domain_plan's spelling; live_domains = n_live -- "
                                      "under FAB.forward's, which fabric/api.py::build is explicit is "
                                      "RUNTIME STATE and an argument rather than the "
                                      "d_live_domains wire. Same staleness as the row above: a B "
                                      "row takes live_domains every flush and this one runs on a "
                                      "cadence that may never fire. DOM.census returns "
                                      "PartitionCensus, declared in domains/api.py's RECORD TYPES "
                                      "block since 2026-09-02 under DOM's own spellings -- "
                                      "Q-MEM-11 RESOLVED (a), and this row is where its two renames "
                                      "are recorded"),
    ("A", "FAB",   "manage",          "Cadences.due('fab.manage', FAB.manage_period(fab), clock) -- "
                                      "step_windows=clock.step. WORLD's growth pass used to ride "
                                      "this same one answer without saying so; that row is now "
                                      "deferred, and if it returns it must either be written INSIDE "
                                      "this answer, in the shape the management block above uses, "
                                      "or take a key of its own -- asking due() twice under one key "
                                      "CONSUMES the fire"),
    ("A", "SIG",   "cadence_due",     "SIG's OWN two-arm shift gate, not Cadences.due: it selects "
                                      "between train_every and train_every_idle on dense_window, "
                                      "and Cadences.due takes ONE period. All three are Windows and "
                                      "the clock is Windows. step_windows=clock.step; "
                                      "windows_since_boundary is clock.step minus the boundary "
                                      "DOM.observe reported ON AN EARLIER WINDOW -- a "
                                      "PREVIOUS-ITERATION value, because that row is four rows "
                                      "below this one and no producer column can reach backwards. "
                                      "SIG does not reach for it. Because it cannot go through the "
                                      "ledger, SIG.counters at stage R is its ONLY did-it-fire "
                                      "surface"),
    ("A", "SIG",   "train_step",      "EVENT-DRIVEN on cadence_due, and BEFORE encode -- the old "
                                      "order is :6649 then :6651, and it is what makes the lookahead "
                                      "sound: the batching interval is the span over which the "
                                      "encoder is provably frozen. stream=_signature_stream(sysm, "
                                      "sig); seen_units=_signature_cursor(sysm, sig, clock.step), "
                                      "THE CURSOR AND NOT THE LENGTH -- _signature_units is the "
                                      "whole epoch-0 stream and is warm_up's alone, and deriving "
                                      "the cursor inline at a call site would be a Windows->bytes "
                                      "conversion written where nobody can audit it. opt is "
                                      "sysm.optimizer.encoder, the AdamW over "
                                      "param_groups['encoder'] -- NOT the whole OptState, which is "
                                      "what crossed until 2026-09-02 for want of a field name "
                                      "(Q-OPT-7 RESOLVED (a)); SIG never names a learning rate. "
                                      "THIS ROW IS THE ONLY PLACE THE ENCODER IS STEPPED IN THE "
                                      "LOOP (Q-OPT-6 RESOLVED (a)): OPT.maybe_step writes the rate "
                                      "into both optimizers and steps the BASE one, because the "
                                      "encoder's step is gated by SIG's InfoNCE floor and paced by "
                                      "SIG's own cadence levers, and a second step from the flush "
                                      "gate would make that floor and those three levers inert by "
                                      "construction. opt.encoder_steps_here is the counter that "
                                      "says the double step has not come back. WITHOUT THIS ROW "
                                      "the run routes every window through a randomly initialised "
                                      "encoder while an AdamW steps it on zero gradients"),
    ("A", "SIG",   "encode",          "one signature per window, at st.width_units, always: "
                                      "windows=_sample_window(sysm, sig, clock.step), the "
                                      "width_units-wide slice of the unit stream ending at the "
                                      "cursor. THE SAME OBJECT goes to DOM.observe one row below, "
                                      "because domains/api.py::observe requires it -- a second slicer at "
                                      "that call site is a defect by construction",
                                      "signature -- the (N, sig.d) unit vectors DOM.observe, "
                                      "FAB.forward and FAB.grow_check all take under that exact "
                                      "name; NOT sample_window, which is this row's ARGUMENT and not its return -- DOM.observe takes the same slice and gets it from ROW_ARGUMENTS_ELSEWHERE. It is "
                                      "which is this row's ARGUMENT rather than its return and is "
                                      "why the join has a name"),
    ("A", "DOM",   "observe",         "once per window, above the early-out: `sustain` is Windows. "
                                      "signature and sample_window are the row above's pair; "
                                      "tokens=this window's slice of Segmentation.ids "
                                      "(_window_bounds); now=clock.step",
                                      "did -- Assignment.did, DOM.note_competence's and DOM.prior's "
                                      "spelling; domain_id = did -- the same id under FAB.forward's and "
                                      "FAB.observe's; sources = did -- the same id under MEM.write's, "
                                      "where memory/api.py::write's src<0 and -2 conventions are MEM's "
                                      "own and nothing here implements them; boundary -- the window "
                                      "SIG.cadence_due's windows_since_boundary is measured from ON "
                                      "THE NEXT WINDOW"),
    ("A", "DOM",   "rekey",           "Cadences.due('dom.rekey', MEM.rekey_period(mem), clock) -- the "
                                      "period is MEM's and the arm test is SIG.mode == 'learned', so "
                                      "BOTH are evaluated HERE and delivered as an event; the old "
                                      "line made two foreign reads at :6688-6689. encode is "
                                      "SIG.encode bound to the SigState by _sig_encode_fn -- an "
                                      "entry point passed as a callable, which is the one class of "
                                      "argument no return value can produce. AFTER observe, so "
                                      "the window that just triggered a boundary is inside the "
                                      "sample its own radius is measured from. It is the ONLY site "
                                      "that measures a radius, and DOM.accept_rule defaults to "
                                      "'radius' -- without it every domain runs on the bootstrap "
                                      "forever and n_bootstrap_radius is 100% by construction. ONE "
                                      "LEVER, TWO MECHANISMS: mem.rekey_every drives this gate AND "
                                      "MEM.maintain's internal amortized rekey, and only this one "
                                      "has a ledger key",
                                      "no return: a rekey recomputes centroids and radii in place"),
    ("A", "TOK",   "on_window",       "the ONE place TOK's four cadences are asked, once each: "
                                      "ids=this window's slice of Segmentation.ids (_window_bounds), "
                                      "step=clock.step",
                                      "mint, retok, probation, frozen -- the Due, which is an EVENT "
                                      "and not an argument: three B rows act on it. IT IS ASKED PER "
                                      "WINDOW AND ACTED ON PER FLUSH, so what crosses the "
                                      "accumulator is batch_windows Dues and one flush. The root "
                                      "carries them on System.due and OR-s THEM, PER CADENCE KEY "
                                      "(Q-TOK-12, ruled 2026-09-02): mint, retok and probation each "
                                      "separately, with `frozen` taken from the last window, which "
                                      "is the same value because frozen is a monotone STATE. Taking "
                                      "the last window's Due was refused because it silently drops "
                                      "gcd(period, batch_windows)/batch_windows of every cadence -- "
                                      "HALF of all mints and retoks at grow_every=200 with "
                                      "batch_windows=16, 15 of 16 at a coprime period -- which is "
                                      "the same silent non-fire as the shared key that made minting "
                                      "never fire. The OR's cost is bounded latency, under 8% of one "
                                      "period. Two counters, and one must read zero: tok.due_merged "
                                      "and tok.due_dropped (0 by construction here, which is how a "
                                      "later reader can tell which reading was implemented). At the "
                                      "shipped batch_windows=1 the two are identical"),
    ("A", "RUN",   "RunClock.advance","appends to the accumulator; if not full, continue. THE "
                                      "ACCUMULATOR IS WHERE THE FLUSH BATCH COMES FROM and Tick "
                                      "does not carry it -- the cut is named once, at _flush_bounds. "
                                      "PRECEDENCE: `finished` is tested BEFORE `rolled`. Both can "
                                      "be True on one advance, and at RUN.epochs=1 -- the shipped "
                                      "default -- the only roll a run ever takes is exactly that "
                                      "one, so the E rows above are never re-entered and the loop "
                                      "leaves for R",
                                      "flush_due, rolled, finished -- Tick's three branch "
                                      "conditions, which are read by the loop and taken by no "
                                      "parameter"),
    ("B", "LM",    "embed",           "x is the flush's batch, the same cut encode takes -- see "
                                      "ROW_ARGUMENTS_ELSEWHERE on the row below, because no entry "
                                      "point returns a batch. FIRST OF THE B ROWS, before "
                                      "encode/decode, because WORLD.forecast supplies that row's "
                                      "`extra` and forecast takes obs_emb too. ADDED 2026-09-02 "
                                      "(Q-LM-12 RESOLVED (b)): obs_emb had NO PRODUCER and this "
                                      "file gave two incompatible accounts of it -- the "
                                      "WORLD.loss_terms row said LM exposes no embedding entry "
                                      "point and called it open, while ROW_ARGUMENTS_ELSEWHERE said "
                                      "it was 'the model's embedding table applied to the same cut', "
                                      "i.e. a root-side model.emb(x), which is an AttributeError on "
                                      "every run at lm.compose=1 because build_model does not "
                                      "construct emb under compose. LM.encode(n_layers=0) was "
                                      "refused on both arms: the gru arm ignores n_layers by "
                                      "declared gate, and on the transformer arm zero blocks is "
                                      "embedding PLUS positional",
                                      "obs_emb -- the (B, L, width) token vectors WORLD.loss_terms "
                                      "and WORLD.forecast both take under that name. It is the "
                                      "LOWEST LAYER and the point where a second modality plugs in, "
                                      "which is the claim world/api.py makes and this row is what "
                                      "makes it true rather than asserted"),
    ("B", "LM",    "encode/decode/lm_loss", "x and y are the flush's batch and its next-token "
                                      "targets, cut from Segmentation.ids at _flush_bounds -- see "
                                      "ROW_ARGUMENTS_ELSEWHERE, because no entry point returns a "
                                      "batch. live_vocab and retired_ids come from the vocabulary "
                                      "built at assembly and are refreshed by TOK.judge_probation "
                                      "at B; extra=WORLD.forecast(...) when feedback is on",
                                      "h -- LM.encode's (B, L, width) hidden, which is FAB.forward's "
                                      "spelling; logits -- LM.decode's return, THE ONLY PLACE "
                                      "LOGITS ARE PRODUCED, and one of the two inputs this file "
                                      "forms MEM's write gate from (:7497-7498); "
                                      "per_window_loss = per_window -- lm_loss's first return, "
                                      "FAB.observe's spelling; "
                                      "flush_loss = per_window -- the same return pooled over the "
                                      "flush, which FAB.manage and FAB.grow_check take; "
                                      "baseline_loss = per_window -- the same return again, "
                                      "FAB.contribution's spelling; "
                                      "bits = per_window -- the same return in bits per byte, "
                                      "DOM.note_competence's spelling. FOUR SPELLINGS OF LM.lm_loss'S TWO "
                                      "RETURNS, which are a bare tuple with no record type to "
                                      "anchor them (lm/api.py::encode); mean, the other one, is "
                                      "the first summand of the composed objective "
                                      "OPT.scaled_backward takes"),
    ("B", "FAB",   "forward",         "head=LM.decode as a plain callable -- not an import, and "
                                      "bound by _head. h from the row above; signature from A; "
                                      "step_windows=clock.step; domain_id and live_domains from "
                                      "DOM; novelty is THE PREVIOUS FLUSH'S mean surprise "
                                      "(:7499), carried on System.novelty because it crosses "
                                      "backwards and no column can reach that way; training is a "
                                      "LITERAL this file passes -- True here, False at every "
                                      "instrument -- and it is load-bearing, because "
                                      "fab.halt_mass_train is a TRAINING-ONLY EMA that the old tree "
                                      "moved by averaging eval passes in",
                                      "out -- the FabricOut FAB.observe takes as its second "
                                      "positional; NOT owners, which MEM.write takes and this row does not return: it is an argmax-of-weights join, named in ROW_ARGUMENTS_ELSEWHERE on the consuming row. The old claim here was the top "
                                      "expert of each window, which the old tree formed at :7523 as "
                                      "the argmax of the routing weights folded modulo the owner "
                                      "count, and THE FOLD IS A RECORDED DEFECT (:7524-7527: expert "
                                      "ids run to FAB_NMAX while the store has MEM_OWNERS "
                                      "partitions); aux_loss -- one summand of the objective "
                                      "OPT.scaled_backward takes"),
    ("B", "WORLD", "loss_terms",      "obs_emb = LM.embed's return from the row above, the (B, L, "
                                      "width) token vectors. IT HAS A REAL PRODUCER as of "
                                      "2026-09-02 (Q-LM-12 RESOLVED (b)) and this row no longer "
                                      "appears in ROW_ARGUMENTS_ELSEWHERE: it used to say LM "
                                      "exposed no embedding entry point while that table said the "
                                      "loop applied model.emb between two calls, which are two "
                                      "different answers to one question in one file, and the "
                                      "second crashes under lm.compose=1. Passing the HIDDEN "
                                      "instead was the other refused option: it would falsify "
                                      "world/api.py::<module>'s claim that a second modality needs only "
                                      "new embedding rows, which is goal A's 'room for more "
                                      "modalities'",
                                      "latent -- WorldStep.latent, whose only consumer, "
                                      "WORLD.manage, is deferred below; loss -- one summand of "
                                      "the objective OPT.scaled_backward takes. WorldStep.inv, which the "
                                      "plateau arithmetic reads, is named by no parameter at all"),
    ("B", "LM",    "anchor_term",     "token_seen: the loop's per-token appearance counter, carried "
                                      "on System.token_seen and incremented from the flush's own x "
                                      "before this call. IT IS THE SAME OBJECT TOK.judge_probation "
                                      "takes as `appearances` (C5) -- one tensor, two spellings, "
                                      "owned by the loop and returned by no entry point, which is "
                                      "why the carrier is named here rather than left to the call "
                                      "site. The term arrives ALREADY MULTIPLIED BY anchor_w"),
    ("B", "OPT",   "scaled_backward", "scaling and counting in ONE function, never 128 lines apart. "
                                      "total is the COMPOSED objective and has no single producer "
                                      "by design: it is LM.lm_loss's mean + LM.anchor_term's "
                                      "already-weighted term + FabricOut.aux_loss + WORLD's loss, "
                                      "four rows above this one. lm/api.py::encode forbids LM "
                                      "composing it, so the sum is THIS FILE'S and the row names "
                                      "the summands rather than a producer that must not exist"),
    ("B", "RUN",   "RunClock.note_backward", "derive.accum_due on a Backwards clock"),
    ("B", "OPT",   "maybe_step",      "shift_at from the root, stamped at the E draw row; returns "
                                      "StepOutcome.lr as a RETURN VALUE. Its step 2 IS "
                                      "OPT.lr_at(st, st.opt_step) -- the schedule is PURE and is "
                                      "read from inside this one function, which is why it has no "
                                      "row of its own. best_bpb HAS NO PRODUCER: it wants a Reading "
                                      "carrying (value, seed_count) and the only candidate, "
                                      "EVAL.curve_probe, is deferred -- and CurveReading carries no "
                                      "seed_count either (eval/api.py::<module> against opt/api.py::scaled_backward), "
                                      "so opt.restart.damped and opt.restart.damp_refused_n1 are "
                                      "UNREACHABLE, not zero. It is a defaulted argument, which is "
                                      "the only reason a check does not say so",
                                      "applied_lr -- StepOutcome.lr under FAB.own_lr_scale's "
                                      "spelling; restart -- StepOutcome.restart, one of the three "
                                      "self-inflicted shifts a capacity blackout would be OR-ed "
                                      "from, if the row that takes one were not deferred"),
    ("B", "FAB",   "own_lr_scale",    "applied_lr=StepOutcome.lr; the two endpoints are wires. IT "
                                      "PRODUCES NOTHING ANY SIGNATURE ACCEPTS: the return is "
                                      "per-expert learning-rate multipliers and "
                                      "OPT.maybe_step(opt, st, *, best_bpb, shift_at) has no "
                                      "parameter for them, so fab.lr_scaled_experts counts an "
                                      "effect nothing in this contract applies -- the mirror image "
                                      "of an argument with no producer, and the four-element row is "
                                      "the statement"),
    ("B", "CAP",   "caps",            "-> FAB.grow_check(soft_cap=...) and TOK.lift_vocab_cap(to=...). "
                                      "THESE ARE THE STARTING CEILINGS AND NOTHING LIFTS THEM while "
                                      "CAP.observe is deferred below: valve.cap_experts and "
                                      "cap_vocab move only inside that call, so cap.lifts_experts "
                                      "and lifts_vocab are unreachable rather than zero",
                                      "soft_cap -- Caps.experts under FAB.grow_check's spelling; to "
                                      "-- Caps.vocab under TOK.lift_vocab_cap's. TWO DIFFERENT "
                                      "CAPS: Vocabulary.soft_cap is the vocabulary's and "
                                      "FAB.grow_check's soft_cap is the experts', and they collide "
                                      "on one word"),
    ("B", "FAB",   "observe/grow_check", "per_window_loss and flush_loss from LM.lm_loss's two "
                                      "returns; out from FAB.forward; domain_id from DOM.observe; "
                                      "step_windows=clock.step; soft_cap from CAP.caps; "
                                      "memory_pressure from MEM.census, which is a CADENCED "
                                      "producer feeding a per-flush required argument; signature "
                                      "from SIG.encode. shift_at=THE SAME EVENT OPT.maybe_step "
                                      "TAKES BELOW, STAMPED INTO THE OTHER CLOCK KIND: OPT's is "
                                      "units.Steps off clock.opt_steps, FAB's cooldown/warmup/ "
                                      "recover_* are units.Windows and grow_check takes "
                                      "step_windows, so the root stamps units.Windows(clock.step) "
                                      "here and handing OPT's object to FAB raises UnitError "
                                      "instead of being batch_windows-fold wrong. Three sites "
                                      "stamp it -- the E draw row's resample, the TOK.mint_burst "
                                      "retok two rows up, and OPT's LR restart -- which are the "
                                      "three the old tree called note_shift from (:6515, :7787, "
                                      ":7120). It carries backwards like System.novelty, so it "
                                      "rides System rather than a produces column, and because a "
                                      "DEFAULTED argument is invisible to K10 the counter "
                                      "fab.shift_notifications is what says whether anyone "
                                      "supplied it (Q-FAB-6, ruled 2026-09-02: A FROZEN SIGNATURE "
                                      "MOVED, grow_check gained shift_at=None). FAB.contribution "
                                      "was the third entry on "
                                      "this row and is now deferred -- its `candidates` and "
                                      "`baseline_logits_fn` have no producer, and the second is the "
                                      "same missing join that deferred EVAL.holdout_probe"),
    ("B", "MEM",   "write/maintain",  "key_fn=LM.encode bound by _key_fn; contexts and tokens are "
                                      "the flush's x and y at _flush_bounds; positions are TRUE "
                                      "BYTE OFFSETS from Segmentation.byte_pos; sources from "
                                      "DOM.observe; owners from FAB.forward; surprise is "
                                      "1 - the model's probability of the true next token, formed "
                                      "by this file from LM.decode's logits and y (:7497-7498) -- "
                                      "the same quantity whose per-flush mean becomes the next "
                                      "flush's novelty; now=clock.step. maintain's job 1 is this "
                                      "package's OWN retrieval on the probe_every cadence -- the "
                                      "read that moves use/last/prob, without which evict='lru' and "
                                      "evict='usage' are write-order FIFO whatever they say and "
                                      "probation can never promote; it is written without the call "
                                      "form because MEM.read is deferred for want of `queries`, and "
                                      "its probe_contexts argument has no producer either, which is "
                                      "exactly the state that made those two eviction rules "
                                      "measurable only as a constant. maintain ALSO compares "
                                      "probe_every and rekey_every against `now` INTERNALLY: two "
                                      "Windows gates with no ledger key, whose only did-it-fire "
                                      "surface is store.n_probe_fired / n_rekey_passes at R. That "
                                      "is this package's own read rather than a second retrieval is "
                                      "the reading Q-MEM-9 asks the owner to confirm"),
    ("B", "TOK",   "mint_burst",      "step=clock.step, on the Due this flush's windows produced at "
                                      "A -> LM.on_mint(sig_emb=SIG.encoder_embedding(...)) and, if "
                                      "Due.retok, TOK.tokenize -> a RetokEvent the root distributes. "
                                      "THE DISTRIBUTION NAMES MORE DESTINATIONS THAN EXIST: MEM "
                                      "takes it as maintain(resegment=...) and "
                                      "DOM.on_retokenize(dom, part) TAKES NO EVENT PARAMETER AT ALL "
                                      "(domains/api.py::manage), while SIG and FAB have no retokenize "
                                      "entry point in their frozen surfaces. The event itself is a "
                                      "record type tok/api.py::<module> declares and no entry point's "
                                      "docstring returns. THE ROOT ALSO STAMPS "
                                      "System.shift_at_windows HERE when Due.retok fires: the loss "
                                      "jump after a retok is OURS, which is what note_shift(:7787) "
                                      "said, and FAB.grow_check reads it on the NEXT flush -- this "
                                      "row is two rows BELOW FAB's, so the ordering is right by "
                                      "construction and the jump cannot grow an expert (Q-FAB-6)",
                                      "mints = Mint -- the list LM.on_mint takes; NOT resegment: the RetokEvent is declared by no entry point's docstring, which this table says four rows above, so claiming it here would be K11's exact defect. It is named on the consuming rows' exemptions. The old claim read: the "
                                      "RetokEvent under MEM.maintain's spelling, when one is "
                                      "produced at all"),
    ("B", "LM",    "residual_ratios", "(model) -- LM's JUDGEMENT-TIME read of "
                                      "||delta||/||composite|| per live slot, the input the row "
                                      "below has been defaulting to None. SAME GATE AS ITS "
                                      "CONSUMER: EVENT-DRIVEN on the Due.probation this flush "
                                      "OR-ed at A, never per flush -- a per-token norm over the "
                                      "whole vocabulary computed every flush and discarded by a "
                                      "5000-window consumer is an instrument nobody asked for. It "
                                      "returns None at lm.compose=False and TOK's Gate then prints "
                                      "unreachable, which is M41's repair and not an alternative "
                                      "to this row (Q-TOK-11, ruled 2026-09-02: THE FROZEN SET "
                                      "GREW 121 -> 122 HERE)",
                                      "residual_ratio -- TOK.judge_probation's exact spelling; the "
                                      "vector is indexed as `appearances` is"),
    ("B", "TOK",   "judge_probation", "step=clock.step; appearances is System.token_seen, the same "
                                      "per-token counter LM.anchor_term takes as `token_seen`. "
                                      "EVENT-DRIVEN on Due.probation, which TOK.on_window already "
                                      "asked at A under its OWN cadence key -- asking again here "
                                      "would CONSUME the event, which is how a shared key made "
                                      "minting never fire. It is at B and not A because two of its "
                                      "three inputs are flush-side: the counter this flush's batch "
                                      "just updated, and residual_ratio, which the row above now "
                                      "PRODUCES under the same Due.probation gate -- it used to be "
                                      "read off live model tensors by nothing and defaulted, so no "
                                      "check asked about it",
                                      "retired_ids -- Judgement.retired_ids, LM.decode's exact "
                                      "spelling and the REFRESH of what the vocabulary produced at "
                                      "assembly; live_vocab -- Judgement.id_count, NOT "
                                      "Judgement.live_size, for the reason the `vocab` row states "
                                      "in full: it is the INDEX where never-minted rows begin, not "
                                      "a count of live ones, and the two differ by exactly the "
                                      "retired rows this refresh exists to track. The record "
                                      "carried only live_size until 2026-09-03, so it could not "
                                      "supply what LM.decode requires -- the row and the record "
                                      "were wrong together, which is why naming the field was not "
                                      "enough on its own"),
    ("B", "DOM",   "note_competence", "did from DOM.observe; bits from the per-window loss; the "
                                      "rate is the d_comp_ema wire"),
    ("B", "CKPT",  "save",            "Cadences.due('ckpt', CKPT.save_period(ck), clock), or the "
                                      "SIGUSR1 flag -- the B-level route INTO the C block, with "
                                      "reason='periodic' or 'sigusr1'. It does not assemble "
                                      "anything: the C rows below build `payload` and the recorded "
                                      "geometry, and step=clock.step, epoch=clock.epoch. Written as "
                                      "a route rather than as four restated arguments, because a "
                                      "second copy of the signature is what these tables exist to "
                                      "avoid"),

    # -- C: the checkpoint fan-out. The payload rows are in EXACTLY the order ASSEMBLY_ORDER built
    # the objects -- DATA, TOK, LM, SIG, FAB, WORLD, MEM, DOM, CAP, OPT -- so a reader comparing the
    # save against the build reads one sequence and not two, and a package that has been added to
    # one and not the other is visible by inspection.
    #
    # WHAT THE SAVE SIDE OWES THE GEOMETRY GATE, stated here because the gate is thirty rows above
    # and cannot say it: CKPT.check_geometry compares the LIVE manifest -- _geometry_manifest(sysm),
    # assembled from LM.resolve's LMGeometry and the frozen Configs before the first allocation --
    # against whatever the snapshot recorded.
    # THE FIELD COUNT IS DELIBERATELY NOT WRITTEN HERE, AND THIS LINE IS WHY (Q-CKPT-1). It stood at
    # 15, 16 and 20 in three live statements at once and THIS WAS ONE OF THE TWO THAT SAID 15,
    # against a manifest that has had twenty fields since fab.cap joined it. The count lives at
    # _geometry_manifest and nowhere else; run the function. tests/test_contract.py's K13 now fails
    # on any prose copy of it, which is the only reason this comment can be trusted to stay true.
    # AND THE SAVE SIDE WRITES THE SAME FUNCTION'S OUTPUT -- this comment said the opposite until
    # 2026-09-03. ROW_ARGUMENTS_ELSEWHERE["CKPT.save"], a declaration K10 reads in BOTH directions
    # and therefore the thing that runs, says CKPT.save's `geometry` IS _geometry_manifest(sysm).
    # The recorded key set is byte-identical to the live one and check_geometry's missing-field set
    # is EMPTY BY CONSTRUCTION. The claim that the recorded side carries WORLD.geometry alone is
    # ISSUES P1-C12, WITHDRAWN AS FILED; the "other ten" this comment reported as refused was
    # arithmetic over that claim and over a miscount of WORLD.geometry's own width, which the B row
    # for it below states.
    # WHAT IS ACTUALLY LEFT is narrower, and it is Q-CKPT-2's residue rather than this block's: the
    # two `sidecar` refusals read a per-prefix key ('SIG', 'FAB') that no row writes and that a FLAT
    # prefixed manifest cannot have at any point in its life, so both are disarmed on every resume
    # -- and FAB.state_dict does not even claim to emit a sidecar. Not a row this file can write
    # alone: FAB has to declare its sidecar first.
    ("C", "DATA",  "stream_state",    "(areas) -- the per-area cursors, without "
                                      "which a resume re-reads the head of every area under "
                                      "seg_contig and trains a second time on the parent's material",
                                      "payload['DATA'] -- and its KEY SPELLINGS ARE NOWHERE "
                                      "DECLARED (data/api.py::data_plan says 'dict' and lists the contents "
                                      "in prose), so the round trip through DATA.restore_stream_"
                                      "state is unverifiable by inspection"),
    ("C", "TOK",   "vocab_state",     "(vocab) -- retirements and probation, which "
                                      "a save/load round trip currently UNDOES (D-T3)",
                                      "payload['TOK'] -- keys undeclared, and D-T3 is a live defect "
                                      "CAUSED by a key the file never had"),
    ("C", "LM",    "state_dict",      "(model, geom)", "payload['LM']"),
    ("C", "SIG",   "state_dict",      "(st) -- and the sidecar the restore row "
                                      "above compares against, which sig/api.py::warm_up says this "
                                      "call emits: width_units, alphabet_size, space, d and mode",
                                      "payload['SIG'], and the 'SIG' slice of the recorded manifest "
                                      "-- WHICH NO ROW CURRENTLY WRITES INTO THE SNAPSHOT"),
    ("C", "FAB",   "state_dict",      "(pop) -- `cent` is a BUFFER for this "
                                      "reason: as a plain attribute it was absent from state_dict "
                                      "and the centroids that ARE the routing function were never "
                                      "saved. It declares NO sidecar, unlike SIG's, so "
                                      "FAB.load_state_dict refuses on slots/rank/dk read from a "
                                      "value with no declared origin",
                                      "payload['FAB']"),
    ("C", "WORLD", "state_dict",      "(w), carrying the loop-side plateau EMA",
                                      "payload['WORLD']"),
    ("C", "WORLD", "geometry",        "(w) -- the manifest RECORDED INTO the snapshot, which is what "
                                      "the child's check_geometry compares against. It is on the "
                                      "SAVE side and not beside that gate because it needs the "
                                      "GROWN population, and the gate must fire before anything is "
                                      "built. It is the only geometry() in the tree -- see Q-CKPT-1 "
                                      "and the block above. IT IS THE OVERLAY, NOT THE RECORD: it "
                                      "returns SIX fields, five of which (lat, hid, route_d, nmax, "
                                      "feedback) the live manifest already carries as world.*, so "
                                      "the one thing it genuinely adds is `n`, THE GROWN "
                                      "POPULATION -- the only quantity in this whole gate that "
                                      "cannot be computed from frozen Configs. n is the ALLOCATED "
                                      "predictor count and never the live count (world/api.py, "
                                      "Q-WORLD-8), so it is a shape",
                                      "NOT geometry: WORLD.geometry returns WORLD's own six fields, not the whole manifest CKPT.save takes, and claiming the bare token here made K10 certify a six-field record as the whole comparison. CKPT.save gets its manifest from _geometry_manifest via ROW_ARGUMENTS_ELSEWHERE; this row supplies world.n on TOP of it, recorded-only, reported UNCHECKED by the child's gate and re-refused in both directions by WORLD.load_into (M43). Three statements called this return five fields and it is six -- corrected 2026-09-02 with Q-CKPT-1. It is NOT what check_geometry takes as "
                                      "its own live manifest"),
    ("C", "MEM",   "state_dict",      "(store) -- including prob, recon, nsrc_max "
                                      "and gate_theta, four omissions that each disarmed a live "
                                      "mechanism at the run boundary",
                                      "payload['MEM']"),
    ("C", "DOM",   "state_dict",      "(part) -- including the RESERVOIRS, which "
                                      "are the uncensored sample the measured radius needs",
                                      "payload['DOM']"),
    ("C", "CAP",   "state",           "(valve) -- the lifted caps AND the pin "
                                      "clocks: saving the ceiling without the clock is M38",
                                      "payload['CAP']"),
    ("C", "OPT",   "state_dict",      "(st) -- both optimizers AND lr_prev, "
                                      "restart_amp, cycle_index and the horizon. IT DOES NOT SAY IT "
                                      "WRITES param_group_shape, which OPT.load_state:297 refuses "
                                      "on and which OptState does not declare -- a refusal armed "
                                      "against a value nothing produces",
                                      "payload['OPT']"),
    ("C", "CKPT",  "Retention.state", "() -> Snapshot.best_state, which is a FIELD OF ITS OWN and "
                                      "not part of payload: new_retention(restored=) takes it back. "
                                      "Without it the first post-resume probe satisfies 'no best "
                                      "yet' and overwrites the parent's best model (M45)"),
    ("C", "TOK",   "save_vocabulary", "(vocab, suffix) -> the run's own d_vocab_save_path with the "
                                      "suffix spliced before the .dyntok.json tail. BESIDE the save "
                                      "and never at the read path, which is the parent's. THE "
                                      "SUFFIX IS THE SAME VALUE THIS BLOCK HANDS CKPT.save two rows "
                                      "below -- CKPT.Retention.consider's BestAction chooses it at "
                                      "RUNTIME, which is why it is an argument and not part of the "
                                      "d_vocab_save_path coupling (a compute sees only frozen "
                                      "Configs). M46 IS CLOSED BY THIS ROW (Q-TOK-10, 2026-09-02): "
                                      "a .bestN snapshot no longer overwrites the base vocabulary "
                                      "file, and <base>.bestN.dyntok.json now exists, so resuming "
                                      "from a best snapshot -- which could not work at all -- reads "
                                      "the vocabulary that snapshot was written with"),
    ("C", "CKPT",  "save",            "(payload, geometry, step=clock.step, epoch=clock.epoch, "
                                      "reason, suffix) -- LAST, because it is handed the finished "
                                      "product. reason is one of the five declared routes and is "
                                      "RECORDED, so 'saves: 0' can name which route was never taken"),

    # -- R: the report. Once, after Tick.finished. NEVER ASKED and ASKED AND REFUSED are two
    # different statements and this stage is where the second half of the evidence is collected.
    # MEM.read and MEM.blend WERE HERE and are now deferred: nothing produces `queries`, and blend's
    # `model_probs` are probabilities while every scoring hook in the tree takes a logits_fn -- the
    # row's own prose conceded that join was missing (Q-MEM-10) and was written anyway, which is the
    # same double standard that put a row under EVAL.curve_probe and a deferral under
    # EVAL.holdout_probe.
    ("R", "DOM",   "prior",           "(did) -- the per-domain token prior AND its weight, together. "
                                      "At R the `did` being asked about is one of the ids "
                                      "DOM.census's `live` list carries, not a live Assignment. The "
                                      "old read site is the report (:8147-8192) while the "
                                      "accumulation is per window, and the accumulated/read PAIR is "
                                      "the whole finding that the histogram was paid for every "
                                      "window and never read"),
    ("R", "MEM",   "census",          "(reconcile=True) -- the store's did-it-fire surface, re-taken "
                                      "at the end so the report's numbers are the settled ones, and "
                                      "the ONLY place the two ungated gates inside MEM.maintain "
                                      "become visible: n_probe_fired and n_rekey_passes have no "
                                      "ledger key"),
    ("R", "DOM",   "census",          "() -- the partition's did-it-fire surface, and the domain "
                                      "sizes every verdict is keyed by"),
    ("R", "LM",    "counters",        "(model)"),
    ("R", "SIG",   "counters",        "(st) -- the ONLY place the encoder's cadence is visible, "
                                      "because its gate cannot go through Cadences.ledger"),
    ("R", "FAB",   "counters",        "(pop)"),
    ("R", "OPT",   "counters",        "(st) -- it ASSERTS backward // accum == step, which is the "
                                      "only thing that proves ISSUES P3-H29 is dead"),
    ("R", "CAP",   "counters",        "(valve) -- including the BLOCK-REASON histogram, without "
                                      "which '0 lifts' cannot say which condition refused. With "
                                      "CAP.observe deferred every one of those reasons reads "
                                      "UNREACHABLE rather than zero, and that is the honest line"),
    ("R", "RUN",   "RunClock.counters", "() -- the five typed counters; flushes == 0 with step > 0 "
                                      "means the batch never filled"),
    ("R", "RUN",   "Cadences.ledger", "() -> {key: (checks, fires, last_fired_step, period)}. A key "
                                      "with checks > 0 and fires == 0 is armed-but-inert WITH ITS "
                                      "ARITHMETIC; a key that is absent was never asked; and 'curve' "
                                      "is now a key that is PRESENT with zero checks, because its "
                                      "period is declared and the probe that would ask it is "
                                      "deferred"),
    ("R", "CKPT",  "Retention.counters", "() -- probes_seen, new_bests, rotations, slots_used and "
                                      "inert_reason, which is the one surface that can say 'no curve "
                                      "value has ever arrived' instead of 'zero local lows'. At P3 "
                                      "that is exactly what it must say"),
    ("R", "RUN",   "bench_summary",   "(clock, elapsed_s=the root's own wall clock across the run -- "
                                      "RunMode.timing.spans() is per-span and is not a run total, "
                                      "so this one is the root's to take and nothing returns it; "
                                      "bytes_per_window=_bytes_per_window(sysm) = LM.ctx times "
                                      "Segmentation.bytes_per_token FROM THE LAST TOK.tokenize; "
                                      "n_params=_n_params(sysm), which sums BOTH param groups -- "
                                      "the base list and SIG's encoder, because summing only the "
                                      "first undercounts by the whole encoder; timing) -- printed "
                                      "INSTEAD of the battery when RUN.mode says bench. The live "
                                      "bytes/window is the L42 repair: the old number was "
                                      "initialised at the SEED vocabulary and refreshed only inside "
                                      "an instrument's tick"),
    ("R", "CKPT",  "save",            "the third route into the C block: reason='final'. It runs "
                                      "after the counters above so the checkpointed counter vectors "
                                      "are the ones the report printed"),
)


# ==================================================================================================
# DEFERRED ENTRY POINTS
#
# {"PFX.entry": "the phase that will call it, and why it cannot be called now"}. tests/test_contract
# K6 reads this table BOTH WAYS: an entry here that no row names is accepted, and an entry here that
# a row now names is reported as STALE and must be deleted. That is what keeps it from becoming the
# place orphans go to be forgotten -- an orphan with paperwork is still an orphan, and the check
# says so.
#
# IT IS NO LONGER ONLY EVAL, AND THAT IS THE POINT OF THE `produces` COLUMN. The seven EVAL entries
# were deferred for a stated reason -- an argument with no producer -- while seven rows elsewhere in
# the tables named calls with exactly the same gap. EVAL.curve_probe and EVAL.holdout_probe had
# BYTE-IDENTICAL signatures and got opposite verdicts. The column made every one of them decidable,
# and the seven below are the ones where nothing in the frozen entry-point set supplies a required
# argument and no join in this file honestly can. Each names what would close it. NONE of them is
# deferred for being late, and none is deferred because a body is missing: the whole tree is stubs.
#
# WHAT THIS COSTS, SAID PLAINLY, because a deferral that hides its cost is the shape it replaces:
# with these seven unrowed the run has no capacity valve (nothing lifts a cap), no WORLD growth, no
# learning-curve probe and therefore no best-model save and no restart damping, no per-expert
# contribution and therefore no informed spare rule, and no memory retrieval or wrongness sweep.
# That is a large part of goal B's machinery, and it was ALREADY inert -- the rows named calls whose
# arguments nothing supplies. The deferral does not remove a mechanism, it stops the tables claiming
# one, and it names the producer each mechanism is waiting on.
DEFERRED_ENTRY_POINTS = {
    # THE FIVE Vocabulary ACCESSORS. They arrived with the record in P4's TOK slice, one increment
    # before the rows that call them, for the same reason RUN.Timing's two did: TOK.build_vocabulary
    # has to RETURN a Vocabulary, and the contract's RECORD TYPES block names these five as that
    # object's surface. They are accessors on a record other packages receive as an argument and
    # call methods on -- which the contract states is not an import -- so their callers are LM's
    # embedding rows, TOK's own minting rows and EVAL's decode, none of which have bodies yet. Every
    # one of them takes only `self` (or an id), so there is no argument without a producer: what is
    # missing is the CALLER, and that is the whole reason each line below says which one.
    "FAB.Population.parameters":
        "P4, with OPT.build. IT IS ALREADY CALLED, by name, from this file: _base_parameters does "
        "`getattr(obj, \"parameters\", None)` on the model, the population and the world and appends "
        "a WARNING when it is missing -- so the row that consumes it exists and OPT.build, which "
        "receives the list, does not. Listed here rather than credited to _base_parameters because "
        "a helper in the composition root is not an order-table row. It takes only self, so there "
        "is no argument without a producer. THE COST OF ITS ABSENCE IS MEASURED: without it the "
        "expert pool contributed nothing to the base param group, so every expert's contribution "
        "stayed exactly zero while the population grew, culled and replicated around it -- both "
        "goals' central mechanism, inert, with every report line still printing.",
    "FAB.Population.n":
        "P4, with the rows that read the live population size: FAB.manage's cull budget, CAP's "
        "startup refusal against CAP_FAB_START, and the banner. It is the accessor the growth "
        "clamp reads -- `min(burst, cap - fab.n())` went NEGATIVE on a resume whose checkpoint "
        "carried a larger n0 than the arm's start cap, and the run then trained to completion "
        "having grown nothing on a configuration whose purpose is to study growth. Takes only "
        "self, so there is no argument without a producer; what is missing is the caller.",
    "TOK.Vocabulary.live_size":
        "P4, with TOK's retire path. It is size() minus the retired set, and it exists separately "
        "BECAUSE retire() changes the match table without shortening id2bytes -- the embedding row "
        "keeps its meaning. Nothing calls it until a row can retire. No unproduced argument.",
    "TOK.Vocabulary.at_cap":
        "P4, with TOK.mint_burst and CAP's vocabulary arm. THE ONE PREDICATE over min(soft_cap, "
        "ceiling): a caller re-deriving that comparison is a second copy of a rule whose two halves "
        "mean different things -- the model's embedding row count and a valve position that moves. "
        "No unproduced argument.",
    "TOK.Vocabulary.blen":
        "P4, with the byte-length accounting in EVAL's bits/byte and DATA's exposure audit. Its one "
        "argument `i` is a token id the caller already holds, not a value any entry point returns.",
    "TOK.Vocabulary.decode":
        "P4, with EVAL's generation and the report's sample lines. Its one argument `ids` is a "
        "Segmentation.ids the caller already holds -- TOK.tokenize produces it, and that entry "
        "point HAS a body; what is missing is the eval row that calls both.",
    "RUN.Timing.span":
        "P4, WITH THE FLUSH BODY, AND IT ARRIVED BEFORE ITS CALLER ON PURPOSE. RUN.mode has to "
        "return a RunMode, RunMode carries a `timing`, and the contract's RECORD TYPES block names "
        "span() and spans() as that object's surface -- so writing `mode` writes these two, one "
        "increment before the rows that call them. THE ALTERNATIVE WAS WORSE: a RunMode carrying "
        "None until the loop lands would make every future call site test for it, which is the "
        "second-code-path this record exists to remove (span() returns a context manager whether "
        "profiling is on or off precisely so the hot path has no branch). ITS ONE ARGUMENT, `name`, "
        "HAS NO PRODUCER AND WILL NOT HAVE ONE: it is a literal written at the call site -- the "
        "label of the component being timed ('encode', 'route', 'backward') -- so it is not a value "
        "any entry point returns and no row can name a producer for it. What is missing is the "
        "CALLER, not the argument: the flush body's per-component spans. `spans()` is read by "
        "RUN.bench_summary, which takes `timing` and is itself a stage-R row. Both leave this table "
        "when the loop body lands.",
    "RUN.Timing.spans":
        "P4, with RUN.Timing.span above -- same increment, same caller. Read by RUN.bench_summary "
        "(`timing=None` in its signature is the not-profiled case), and an EMPTY dict from it is a "
        "different statement from an absent one: 'measured nothing' versus 'did not measure'. That "
        "distinction is why RunMode always carries a Timing rather than sometimes carrying None.",
    "CKPT.Retention.consider":
        "P5, WITH EVAL.curve_probe, AND THIS IS THE SAME DOUBLE STANDARD ONE ROW DOWNSTREAM. It had "
        "an A row until 2026-08-30 while its only input's producer sat in this table: `curve_bpb` is "
        "the held-out value EVAL.curve_probe returns, curve_probe is deferred because nothing "
        "produces units_by_domain or logits_fn, and a row consuming the output of a deferred entry "
        "point is a call whose argument cannot arrive -- the exact thing this table's standard "
        "forbids. K10 could not see it because the check dropped the FIRST POSITIONAL as 'the "
        "package's own live object', and Retention.consider is a METHOD: self was already skipped, "
        "so the rule discarded curve_bpb and asked only about `step`. "
        "THE COST IS STATED RATHER THAN HIDDEN: Saves.best can never be non-zero, so the only "
        "copies of the model are the periodic ones and the final one, and Retention.counters() must "
        "report inert_reason='no curve value has ever arrived' rather than a bare zero. It returns "
        "with curve_probe.",
    "EVAL.curve_probe":
        "P5 (eval). SAME SIGNATURE, SAME GAP, SAME VERDICT AS holdout_probe below -- which is the "
        "whole reason this table was re-read. Nothing produces `units_by_domain`: Areas carries "
        "names/bodies/holdout/holdout_bytes/cursors, DOM.census returns sizes and radii, and "
        "Segmentation carries ids/byte_pos/labels/bytes_per_token; there is no per-domain window "
        "supplier anywhere. Nothing produces `logits_fn` either, and it cannot be faked from "
        "LM.encode + LM.decode alone: eval/api.py::<module> requires THE PATH THE RUN TRAINED, which "
        "goes through FAB.forward, and building that callable needs the same `novelty`, "
        "`live_domains` and `training` the flush body is handed. Two consequences are stated in the "
        "rows rather than left to be discovered: CKPT.Retention.consider's event can never arrive, "
        "so Retention.counters().inert_reason must report 'no curve value has ever arrived'; and "
        "OPT.maybe_step's best_bpb has no producer, so the restart damping is unreachable. The "
        "'curve' period stays in RUN.new_cadences' mapping so the ledger carries a key with zero "
        "checks. P5 lands the pair and the row together.",
    "EVAL.holdout_probe":
        "P5 (eval). The R matrix -- goal B's only cross-boundary number -- and the row that calls "
        "it belongs at stage R and at every save site. It is deferred rather than rowed because it "
        "needs units_by_domain drawn in BYTE coordinates from Areas.holdout together with a "
        "logits_fn, and the root has no join that produces that pair; writing a row now would name "
        "a call whose arguments nothing supplies. P5 lands the pair and the row together.",
    "EVAL.null_excess":
        "P5 (eval). The permutation null every 2-sigma verdict is judged against. THE REASON "
        "WRITTEN HERE UNTIL 2026-08-30 WAS FALSE AND POINTED THE WRONG WAY: it said `real` and "
        "`permute` come from 'the verdict machinery, which is P6's', but EVAL.verdicts takes "
        "domain_sizes, silhouettes, affiliation and coherence_reading and returns verdicts -- it is "
        "this function's CONSUMER, not its producer, and this docstring calls itself the null every "
        "verdict is judged against. What actually produces them: `real` is the measured statistic "
        "under test and `permute` is the label-permuting redraw of it, so the candidates are the "
        "silhouette and affiliation statistics -- which have NO PRODUCER IN THE TREE, which is the "
        "very gap EVAL.verdicts is deferred for -- and no entry point anywhere returns a "
        "permutation callable. Neither exists. A deferral reason that names the wrong producer is "
        "worse than none: it reads as a dependency somebody has already placed.",
    "EVAL.generate":
        "P6 (eval). The generation battery. `prompts_by_domain` has no producer among the frozen "
        "entry points: DOM.census returns domain sizes and radii, not prompts. `logits_fn` is the "
        "same missing join as curve_probe's.",
    "EVAL.coherence":
        "P6 (eval). TWO arguments have no producer and BOTH are named: `logits_fn`, the same join "
        "curve_probe and holdout_probe wait on, and `units_by_domain`, the same per-domain unit "
        "supplier those two wait on -- one missing join, three deferrals, and the same sentence. "
        "The third callable, `encode`, is NOT a gap: _sig_encode_fn already forms it for DOM.rekey "
        "and this function takes the same one. THE REASON WRITTEN HERE UNTIL 2026-08-30 WAS FALSE: "
        "it said 'no entry point in the tree returns a Sample today', and EVAL.generate returns one "
        "(eval/api.py). THE `sample` PARAMETER IS GONE, 2026-09-02, Q-EVAL-10 RESOLVED: a Sample is "
        "the printed generations, so the signature invited the one argument the docstring forbids "
        "and the old code passed it. It is now `units_by_domain` plus `encode` -- material and an "
        "encoder, not a measurement -- and the docstring's sentence is true.",
    "EVAL.verdicts":
        "P6 (eval). Three of its four arguments -- silhouettes, affiliation, coherence_reading -- "
        "have no producer in the tree; the fourth, domain_sizes, comes from DOM.census, which the "
        "R stage above already collects.",
    "EVAL.wrongness_probe":
        "P6 (eval). Takes a `store_copy` so the instrument cannot edit what it measures; nothing in "
        "MEM's surface produces one -- the ten entry points are open_store, write, read, blend, "
        "maintain, apply_domain_plan, judge, census, state_dict and rekey_period, and no copy -- "
        "and inventing it is a signature change. Its "
        "`scorer` is the same missing logits callable as MEM.judge's, AND IT TAKES THE SAME ARITY: "
        "`scorer(ctx, src) -> logits`, ruled under Q-MEM-8/Q-MEM-10 on 2026-09-02. One callable "
        "declared twice with two shapes is how this tree got a width of 614 on one path and 1 on "
        "the other.",
    "EVAL.verification_fit":
        "P6 (eval). Post hoc, on a `store_copy` MEM's surface does not produce -- see wrongness_probe "
        "above -- with an inner loop in genuine units.Steps that must never be compared against "
        "curve_every. Same missing copy, same phase. `verify_mode` is NOT part of the gap "
        "(Q-EVAL-11, 2026-09-04): it is MEM.verify, a frozen lever the root already holds, and the "
        "row will spell it verify_mode=MEM.verify the way the store row above spells "
        "vocab_slots=LM.vocab_slots. It is named here because a deferred entry point has no row "
        "for K12 to read a producer off, not because nothing produces it.",
    "MEM.read":
        "P5 (eval/report). Nothing produces `queries`. The R row that called it named none of "
        "them, and the probe contexts it would key on are the same held-out material "
        "EVAL.holdout_probe's units_by_domain needs -- one missing join, two deferrals, and "
        "deferring only one of them was the inconsistency this edit exists to end. The cost is "
        "recorded where it bites: MEM.maintain's job 1 is this package's own retrieval and its "
        "`probe_contexts` has no producer either, so evict='lru' and evict='usage' stay write-order "
        "FIFO and probation can never promote until P5 lands the contexts. "
        "DEFERRED AS A ROW, REACHED IN-PACKAGE: Q-MEM-9 is RESOLVED (a) as of 2026-09-02 and "
        "MEM.maintain's job 1 IS this call, with `queries` maintain encoded itself. K6 is satisfied "
        "by the absence of a ROW, not by the absence of a call, and an in-package call is not a "
        "cross-package import (O10/K3 untouched), so this deferral stays valid and is not stale.",
    "MEM.blend":
        "P5 (eval/report). Its `retrieval` comes from MEM.read, deferred above, and its "
        "`model_probs` are PROBABILITIES while every scoring hook in the tree takes a logits_fn -- "
        "the join between them is Q-MEM-10, which the deleted row's own prose CONCEDED while being "
        "written anyway. `model_probs` is also the first positional after the Config, which K10 "
        "drops as 'the package's own live object' -- it is not; MEM's live object is `store`, and "
        "blend is the one entry point in the package that does not take it. So the check is "
        "structurally blind here and the deferral is the only thing that records the gap. "
        "Q-MEM-10 IS RESOLVED (a) as of 2026-09-02 and it does NOT close this deferral: it rules "
        "that the join is spine work, written once as _logits_fn(sysm, *, use_memory), that NEITHER "
        "MEM.blend NOR ANY EVAL SIGNATURE MOVES, and that the scoring caller takes log() of the "
        "mixture -- which is exact, not a pseudo-logit. What still has no producer is the "
        "logits_fn itself. When it lands, blend is called from that spine helper and never from a "
        "row, so K10's blind spot here is retired rather than papered over.",
    "MEM.judge":
        "P4/P5 (memory + eval). `scorer(ctx) -> logits` is required by the DEFAULT arm: MEM.verify "
        "defaults to 'selfcon' and memory/api.py::judge says the scorer must be THE SAME FORWARD "
        "PATH TRAINING USED, passed in and never constructed there (M47). That callable does not "
        "exist -- see EVAL.curve_probe -- and scoring a STORED ctx through it needs a signature and "
        "a domain id per stored entry -- WHICH THE STORE ITSELF CARRIES as Store.src, so the datum "
        "exists and what cannot carry it is the DECLARED CALLABLE SHAPE: it is `scorer(ctx, src) -> "
        "logits`, ruled once here and in memory/api.py, and EVAL.wrongness_probe's `scorer` takes "
        "the same two arguments (Q-MEM-8/Q-MEM-10, 2026-09-02). Because `scorer` carries a "
        "default, no check asks about it: a row calling judge(mem, store) passes every check in the "
        "tree and yields n_checked = 0 forever, which memory/api.py::judge itself names as the "
        "inert state. That is precisely why this is a deferral and not a row with a note. "
        "Q-MEM-8 IS RESOLVED 2026-09-02 AND THIS IS THE ROW TO WRITE WHEN THE SCORER EXISTS: an "
        "('A', 'MEM', 'judge', ...) row at the END of the dom.manage block, after the DOM.census "
        "row, INSIDE the one Cadences.due('dom.manage', ...) answer that block already asks and "
        "NEVER a second due() under that key -- and this entry is deleted in the same edit, because "
        "K6 reads this table backwards and would otherwise report it stale. No key is added to "
        "_periods and no lever is minted for the cadence. The contract's claim that LOOP_ORDER "
        "ALREADY places judge on that pass was false and is corrected there; the reason it gave -- "
        "'the provenance has just been rewritten by folds' -- is also wrong, since nothing judge "
        "reads is provenance. The reason that survives is census(reconcile=True) opening the SAME "
        "pass, which bounds a wrong_sweep deletion's count drift to one cadence interval; 100 "
        "Windows bounds it five times tighter than fab.manage's 500, and a MEM row on a FAB-keyed "
        "answer is the untracked ride the fab.manage row above records for WORLD. WHAT IS *NOT* "
        "SETTLED BY ARGUMENT IS THE SCOPE, and it is a declared lever instead: MEM.judge_frac, a "
        "CENSUS AMENDMENT shipped at 0.0 (the re-score is off), with the full-store arm at 1.0 "
        "costing about 1.7x the interval's whole training compute.",
    "FAB.contribution":
        "P4 (fabric). THREE arguments have no producer, not two: the reason said two until K12 counted them. `targets` is the flush's shifted token cut -- the same `y` LM.lm_loss takes, which is the loop's own slice and has no row -- so it is a gap of a different KIND from the other two and that difference is why it was missed. `candidates` is the eligible past-grace set, "
        "which lives in Population's use/uage books; no entry point exports it and O10 forbids the "
        "root reaching into `pop`, so either FAB adds an accessor or `candidates` gains a "
        "documented default of 'all past-grace'. `baseline_logits_fn` is the same missing callable "
        "as EVAL's, and fabric/api.py::observe makes it load-bearing rather than convenient: the "
        "whole C3/H11 repair is that the baseline must come from THE SAME CALLABLE that produced "
        "`baseline_loss`, and a row that named a call whose baseline came from somewhere else would "
        "rebuild the offset that set contrib's SIGN. Under Q-MEM-10 (a) there will be TWO closures, "
        "memory-off and memory-on, and THIS ONE IS ALWAYS THE MEMORY-OFF CLOSURE -- handing it the "
        "memory-on one would put retrieval in the baseline and undo that repair from the other side. Until then fab.contrib_measured reads "
        "unreachable, and the two spare rules and the replication parent choice have no signal.",
    "CAP.observe":
        "P4 (fabric + capacity). THREE arguments have no producer, not two: `elapsed_windows` was "
        "omitted from this reason until K12 counted them. It is the valve's PIN DELTA -- how many "
        "windows since the last call -- and RunClock counts windows without naming that difference, "
        "which is the whole of the pin-clock story: the delta is what derive.pin_tick accumulates, "
        "and typing it was the repair settled on 2026-08-30. "
        "`improving` and `observations` have no producer either. improving is "
        "(slow - fast)/|slow| off the growth controller's two EMAs, which live INSIDE FAB "
        "(fabric/api.py::manage runs the same two-sided test) and are on no returned record: "
        "GrowReport carries asks, deliveries and decline reasons, not the reading. observations is "
        "the valve-evaluation count the old tree read as `fabgrow.n`, and capacity/api.py::observe "
        "ties it to a hardcoded 0.998 EMA rate the caller cannot see. The root must not maintain a "
        "SECOND pair of EMAs over the same loss to manufacture them -- two mechanisms deciding "
        "independently whether the run has stalled is the defect capacity/api.py::observe records, "
        "where the valve fired hardest exactly when the run was degrading worst. `blackout` is the "
        "one argument that WOULD have a home: retok, epoch resample and LR restart all have rows, "
        "and the root already stamps the same events as OPT.maybe_step's shift_at. So the fix is "
        "one field on GrowReport and one root join, and HALF OF IT LANDED 2026-09-02 with Q-FAB-6: "
        "FAB.grow_check now takes the units.Windows stamp, applies FAB'S OWN cooldown to it, and "
        "declares the resulting blackout state on GrowReport -- which is what stops CAP either "
        "reading a foreign lever at the call site or minting a blackout-window lever it has no "
        "census row for (CAP's seven are targets, fab_start, vocab_start, lift, lift_min, "
        "pin_windows, stall_band; in the old tree the boolean was `(step - fabgrow.blackout) < "
        "fabgrow.cool` at :7397, i.e. FAB's cooldown). WHAT IS STILL MISSING IS THE ROOT JOIN AND "
        "THE TWO EMAs, so this entry point stays deferred; until then CAP.caps returns the "
        "STARTING ceilings and every block reason in the histogram reads unreachable.",
    "WORLD.manage":
        "P4 (world + opt). `plateau` contradicts the package's own state_dict: world/api.py::manage "
        "says the loop-side plateau state (_wl_ema, _wl_lastgrow) MOVES INSIDE THIS PACKAGE and "
        "travels in the checkpoint, while manage takes the boolean as a required argument -- if the "
        "state is inside, the boolean is computed inside, and both sentences cannot hold. Nothing "
        "returns it. `add_param_group` is OPT's optimizer.add_param_group as a callable, and HALF "
        "of why it had no producer is closed as of 2026-09-02: OptState was declared as 'both AdamW "
        "instances' and NAMED NEITHER, so the root could not address one without guessing a field -- "
        "the identical hole recorded for SIG.warm_up as Q-OPT-7. The fields are now `base` and "
        "`encoder` (opt/api.py, RECORD TYPES), so the expression the root would write is "
        "`sysm.optimizer.base.add_param_group` and the guess is gone. WHAT IS STILL MISSING IS THE "
        "ROW: this entry point has no ASSEMBLY_ORDER or LOOP_ORDER position, so nothing in the "
        "assembly hands the callable to WORLD, and the argument therefore still has no producer. "
        "Which of the two optimizers a mid-run world parameter joins is also OPT's ruling and not "
        "this table's: the dynamics population's parameters are base-group parameters, and putting "
        "them in the encoder group would put them under SIG's cadence. `latent` is real but "
        "arrives BACKWARDS: "
        "WORLD.loss_terms is a B row and this pass ran at A, so what was in hand was the PREVIOUS "
        "flush's. WHEN IT RETURNS IT MUST SAY WHICH ANSWER IT RIDES: it ran on the fab.manage key "
        "without the row saying so, and Cadences.due RECORDS the fire, so asking twice under one "
        "key consumes it -- inside FAB.manage's single answer, in the shape the dom.manage block "
        "uses, or with a key of its own.",
}


# ==================================================================================================
# ROW ARGUMENTS SUPPLIED BY A NAMED JOIN IN THIS FILE
#
# {"PFX.entry": "which join produces the row's arguments, and what it does"}. K10 reads it and skips
# those rows; it also reads it BACKWARDS, so an entry whose row requires nothing is reported stale.
#
# IT SAID "DELIBERATELY TWO ENTRIES LONG" AND HELD 24. Corrected 2026-09-02 while adding LM.embed:
# a table whose own header misdescribes its size by an order of magnitude is a table a reader stops
# checking, and this one carries the normative answer to arguments K10 would otherwise refuse. The
# rule the sentence was reaching for is still the right rule and it stands: every helper-supplied
# argument is named in the CONSUMING ROW'S OWN NOTE wherever a reader would meet it there, and an
# entry is written here only when putting the name into the row would be WORSE than not. The two
# ORIGINAL cases are still the clearest statements of when that is true:
#   * check_geometry, because the word its argument is spelled with also names the OTHER side of
#     the comparison one row up (Snapshot.geometry, the RECORDED manifest), and a row or a column
#     carrying the bare token would satisfy the check against the wrong object;
#   * LM.encode, because `x` is the flush batch and NO ENTRY POINT RETURNS ONE -- RunClock.advance
#     appends to the accumulator and hands back a Tick -- so the honest producer is this file's own
#     cut, and stating it once here is better than a row that reads as if a package supplied it.
# Everything else here is one of those two shapes: a value the ROOT computes from two packages'
# frozen Configs, or a tensor the LOOP slices and no entry point returns.
ROW_ARGUMENTS_ELSEWHERE = {
    "CKPT.check_geometry":
        "geometry is the LIVE manifest, produced by _geometry_manifest(sysm), which assembles it "
        "from LM.resolve's LMGeometry and the frozen Configs before the first allocation. THE FIELD "
        "COUNT IS NOT WRITTEN HERE: it said 15 until 2026-09-03 against a manifest of twenty, and "
        "Q-CKPT-1 puts the count at _geometry_manifest and nowhere else -- including in this "
        "declaration, which a check reads and which was therefore the most expensive of the three "
        "places to leave it. "
        "It is NOT Snapshot.geometry -- that is the RECORDED side of the same comparison, produced "
        "on the save side by the C block. Naming the bare token in CKPT.load's `produces` would "
        "make this check pass while asserting the wrong object, which is the failure mode the "
        "column exists to end.",
    "SIG.build":
        "width_units is _signature_width(lm, vocab) -- derive.signature_width_bytes over LM.ctx and "
        "the MEASURED bytes/token, resolved ONCE here and never recomputed as the vocabulary grows, "
        "which is the C4 repair this package exists for. alphabet_size is _alphabet_size(sig, lm): "
        "256 under space='bytes', LM.vocab_slots under 'tokens'. Neither is a row's output because "
        "neither is any package's return value -- they are the assembly's own arithmetic over two "
        "packages' frozen Configs, which is exactly what the root is for.",
    "SIG.load_state_dict":
        "sidecar is _sidecar(sysm, restored, 'SIG') -- the RECORDED geometry fields SIG compares its "
        "own state against. IT IS DISARMED TODAY: nothing on the save side writes a per-prefix key, "
        "so _sidecar returns None and the refusal on width_units/alphabet_size/space/d/mode cannot "
        "fire. That is recorded on System.warnings rather than returned in silence, and it is "
        "Q-CKPT-2. A guard that cannot fire must not look armed.",
    "FAB.load_state_dict":
        "sidecar is _sidecar(sysm, restored, 'FAB'), with the same disarmed state and the same "
        "warning -- and worse at this end: FAB.state_dict does not even CLAIM to emit a sidecar, so "
        "the refusal on slots/rank/dk reads a value with no declared origin at either end. "
        "Q-CKPT-2 covers both.",
    "OPT.build":
        "param_groups is {'base': _base_parameters(sysm), 'encoder': SIG.encoder_parameters(...)}. "
        "The base list is assembled here because OPT DOES NOT WALK ANYBODY'S MODULE TREE -- that is "
        "the package's own stated rule -- and no single package can produce a list spanning LM, FAB "
        "and WORLD without importing the others, which O10 refuses. _base_parameters records on "
        "System.warnings when an object declares no parameters(), because skipping one in silence "
        "means a whole package contributes nothing to training with every check green.",
    "SIG.warm_up":
        "seen_units is _signature_units(sysm, sig) -- how much of the unit stream the warm-up may "
        "draw anchors from, in SIG's OWN alphabet (Stream.bytes at space='bytes', Segmentation.ids "
        "at 'tokens'). It is a LENGTH here and a CURSOR in the loop; the two are different questions "
        "and _signature_cursor is the other one.",
    "SIG.train_step":
        "seen_units is _signature_cursor(sysm, sig, at_window) -- how much of the unit stream the "
        "loop has REACHED, not how much exists. Confusing it with the warm-up's length would let the "
        "encoder train on material the loop has not seen, which is the leak every held-out number "
        "would then be measured through.",
    "SIG.encode":
        "windows is _sample_window(sysm, sig, at_window) -- the st.width_units-wide slice this window "
        "is encoded from, the same object domains/api.py::observe receives as sample_window.",
    "LM.lm_loss":
        "y is the same cut LM.encode's x comes from, shifted one token -- see the LM.encode entry "
        "above. Listed separately because K10 keys on the entry point and a shared reason is not a "
        "shared exemption.",
    "CKPT.save":
        "geometry is _geometry_manifest(sysm), the LIVE manifest -- the same object CKPT.check_geometry "
        "compares a restored Snapshot against, written here so the two sides of that comparison are "
        "one function's output rather than two -- so the recorded key set is BYTE-IDENTICAL to the "
        "live one and check_geometry's missing-field set is empty by construction. "
        "THE SENTENCE THAT USED TO FOLLOW HERE SAID 'Ten of its fields have no writer on the save "
        "side today', WHICH CONTRADICTED THE ONE BEFORE IT: if geometry IS _geometry_manifest(sysm), "
        "that one call is the writer of EVERY field in it -- a count is deliberately not written here, because it stood at 15, 16 and 20 in three live statements at once and the sentence added to un-stale it was stale by four when it landed. It was the C-block's claim leaking into the "
        "entry that refutes it, and ISSUES P1-C12 was then filed against a claim this declaration had "
        "already answered -- see C12, corrected 2026-08-30.",
    "RUN.bench_summary":
        "n_params is _n_params(sysm) -- BOTH param groups, never just the base list, because a report "
        "that counts the model and omits the encoder is the wrong-measurement family. elapsed_s is "
        "wall-clock, which no entry point produces and none should: it is the one quantity here that "
        "is not a property of the system.",
    # ---- THE LOOP'S OWN VALUES. A weaker justification than a helper, and labelled as one.
    # These are not produced by any row and never will be: they are computed by the loop BETWEEN
    # calls -- a tensor slice, a running counter, a boolean, a sum. The order tables model CALLS, so
    # a value that lives between two of them has no row to come from, and pretending otherwise by
    # inventing one would be the fabricated provenance this column exists to make impossible.
    # Each says what computes it and why no row can. Four of them are on System.__slots__ because
    # they cross a boundary the tables read forwards cannot express (the fourth is
    # shift_at_windows, added 2026-09-02 with Q-FAB-6).
    "RUN.new_cadences":
        "periods is _periods(sysm) -- the SIX gates' thresholds. Five arrive through their OWNING "
        "package's typed accessor (EVAL.curve_period, DOM.manage_period, FAB.manage_period, "
        "MEM.rekey_period, CKPT.save_period); the sixth is RUN.PROGRESS_WINDOWS, a module constant "
        "and not a lever, for the progress/ETA line and the profiler dump (Q-RUN-1, RESOLVED "
        "2026-09-02). A mapping spanning six packages is precisely the object O10 forbids any one "
        "of them to build, so the root builds it. RUN evaluates gates and owns no threshold that "
        "decides anything the model computes; a log cadence is the stated exception, and it is "
        "stated rather than smuggled.",
    "RUN.cadence_audit":
        "periods is the SAME _periods(sysm) mapping new_cadences receives -- the same object, not a "
        "second construction, or the audit would describe gates other than the ones evaluated.",
    "SIG.cadence_due":
        "windows_since_boundary is the loop's count since DOM last reported a boundary "
        "(DOM.observe's `boundary`), reset there and incremented per window. It is a running counter "
        "between two calls, not a return value.",
    "DOM.observe":
        "sample_window is _sample_window(sysm, sig, at_window) -- the same object SIG.encode is "
        "GIVEN, not one it returns. The SIG.encode row claimed to produce it while its own prose "
        "conceded it was 'this row's ARGUMENT rather than its return', which is honest writing that "
        "K10 could not read. "
        "tokens is the window's token ids -- Segmentation.ids sliced at _window_bounds. The slice is "
        "the loop's; the bounds are named here.",
    "FAB.forward":
        "novelty is the PREVIOUS flush's mean surprise (self_organize.py:7499), carried on "
        "System.novelty because it crosses backwards and `produces` reads forwards only. training "
        "is the loop's own train/eval flag, which no package owns and none should.",
    "LM.anchor_term":
        "token_seen is the per-token appearance counter, carried on System.token_seen because it is "
        "written every window and read at the flush. It is the SAME object TOK.judge_probation "
        "takes as `appearances` -- one counter, two spellings, and C5 is the record of what one "
        "counter under two names cost the last time.",
    "TOK.judge_probation":
        "appearances is System.token_seen under TOK's spelling -- see LM.anchor_term above.",
    "OPT.scaled_backward":
        "total is the summed loss the loop assembles: LM.lm_loss plus FAB's aux_loss plus WORLD's "
        "terms plus LM.anchor_term. The sum is the loop's because the terms come from four packages "
        "and no package may see another's.",
    "RUN.RunClock.begin_epoch":
        "windows_in_epoch is _windows_in_epoch(sysm) -- len(Segmentation.ids) // LM.ctx, this file's "
        "arithmetic over TOK.tokenize's return and LM's frozen Config. TOK.tokenize does NOT return "
        "it: tok/api.py::<module> declares Segmentation as ids, byte_pos, labels and bytes_per_token, and "
        "the row claimed the count until K11 refused the claim. begin_epoch's own docstring is why "
        "it matters -- 'THE LENGTH ARRIVES AS A COUNT OF WINDOWS, never as a byte budget divided by "
        "a token window' -- so the division has to happen once, here, and be named.",
    "MEM.maintain":
        "key_fn is _key_fn(sysm) -- LM.encode bound to (lm, model), the same callable MEM.write "
        "takes. LM.build_model returns a MODEL, not a key_fn, and the row claimed otherwise until "
        "K11 refused it: a bound method is the composition root's construction, which is what this "
        "table is for.",
    "MEM.write":
        "owners is the per-entry owner block: argmax over FabricOut.weights, modulo "
        "MEM.d_owner_blocks. FAB.forward does NOT return it -- FabricOut carries logits, "
        "expert_ids, weights, per_expert_logits, aux_loss and gates -- and the row claimed it did "
        "until K11 refused the claim. It is the one join in this file with no named helper, because "
        "it needs a tensor operation and nothing in src/ imports torch; P4 writes it in the loop and "
        "this entry is what says so. "
        "key_fn is _key_fn(sysm), the same bound callable MEM.maintain takes -- see above. "
        "contexts is LM.encode's `h` for the flush, tokens is the same cut's ids, surprise is the "
        "per-window loss LM.lm_loss returned. All three are the flush's own tensors, sliced by the "
        "loop from values earlier rows DO produce -- the slicing is what has no row.",
    "LM.embed":
        "x is THE SAME CUT LM.encode takes, one row below -- see that entry, which defines it. It "
        "is named here rather than in the row because the cut has ONE definition in this file and "
        "a second statement of it is a second declaration that can disagree; what this entry adds "
        "is only that the embed row and the encode row take the identical tensor, which is what "
        "makes obs_emb the embedding OF THE BATCH THE LM IS TRAINED ON rather than of a "
        "differently-sliced one.",
    "LM.encode":
        "x is the flush's (B, L) window batch, cut from Segmentation.ids at the bounds "
        "_flush_bounds(sysm, at_window) names -- contiguous, non-overlapping, LM.ctx wide, "
        "OPT.batch_windows of them, which is the same arithmetic _windows_in_epoch counts with. y "
        "is the same cut shifted one token. No entry point returns either: RunClock.advance appends "
        "to the accumulator and returns a Tick(step, epoch, flush_due, rolled, finished), a clock "
        "and not a batch. The cut is named here so the loop and this table define it once between "
        "them; the tensors themselves are the loop's to slice.",
}



class System:
    """Everything the loop needs, assembled. A plain record; it holds no logic and no levers.

    Attributes are set by compose() as each stage completes, so a NotImplementedError from a stub
    leaves a PARTIALLY BUILT System naming exactly how far the assembly got -- which is the
    difference between "P4 has not landed" and "the composition root is wrong".
    """

    __slots__ = ("configs", "wires", "warnings", "process", "mode", "streams", "refusals",
                 "geometry", "areas", "vocab", "plan", "model", "sig", "fabric", "world",
                 "store", "partition", "valve", "optimizer", "clock", "cadences", "retention",
                 "save_flag", "snapshot", "stage",
                 # Added with the resume path and the epoch level. `manifest` is the LIVE geometry
                 # manifest CKPT.check_geometry compares the snapshot against and is a DIFFERENT
                 # object from `geometry`, which is LM's LMGeometry. `stream`/`segmentation` hold
                 # epoch 0's material, which OPT.build and SIG.warm_up both need before the loop --
                 # and which nothing held before, so MEM's byte offsets indexed a stream no
                 # attribute on this record named.
                 "resume_src", "manifest", "saving", "stream", "segmentation", "base_params",
                 # `warmup` is SIG.warm_up's WarmupReport, bound here because NO SIGNATURE IN
                 # THE TREE TAKES IT: sig/api.py::WarmupReport says "'collapsing' is a RUN-LEVEL
                 # FAILURE and NO signature in this tree takes it as an argument: this record is
                 # what the composition root has to act on itself". It is therefore not a
                 # `produces` column -- no later row consumes it -- and it is not a value that
                 # crosses a boundary the tables cannot express either. It is a RESULT THE ROOT
                 # OWNS, and before it had a name here the call was a bare expression statement
                 # and the verdict was computed and dropped on the floor.
                 "warmup",
                 # THE FOUR VALUES THAT CROSS A BOUNDARY THE ORDER TABLES CANNOT EXPRESS, each
                 # named by the row that consumes it. `produces` reads FORWARDS -- an argument is
                 # supplied by an EARLIER row -- so a value produced at A and consumed at B, or
                 # produced by one flush and consumed by the next, has nowhere to live but here:
                 #   due        TOK.on_window's Due, asked PER WINDOW and acted on PER FLUSH by
                 #              mint_burst / judge_probation / the retok. batch_windows of them
                 #              reach one flush, and the root OR-s them PER CADENCE KEY (mint,
                 #              retok, probation; `frozen` from the last window, which is the same
                 #              value because it is monotone) -- Q-TOK-12, ruled 2026-09-02. The
                 #              OR is here and not at a call site because the root is the only
                 #              thing that can see a batch. tok.due_dropped must read 0.
                 #   novelty    the PREVIOUS flush's mean surprise, which is what FAB.forward's
                 #              `novelty` and MEM.write's `surprise` are (:7499). A backwards edge.
                 #   token_seen the per-token appearance counter LM.anchor_term takes under that
                 #              name and TOK.judge_probation takes as `appearances` -- ONE tensor,
                 #              owned by the loop, returned by no entry point (C5).
                 #   shift_at_windows
                 #              THE STEP OF THE LAST SELF-INFLICTED SHIFT, as units.Windows, added
                 #              2026-09-02 with Q-FAB-6. It is stamped at THREE sites in three
                 #              different stages -- the E draw row's resample, the B TOK.mint_burst
                 #              retok, and OPT's LR restart -- and consumed by FAB.grow_check's
                 #              `shift_at` on a LATER flush, which is both a backwards edge and a
                 #              cross-stage one, so no `produces` column can reach it. It is a
                 #              SECOND OBJECT for the same event: OPT.maybe_step's `shift_at` is
                 #              units.Steps off clock.opt_steps and this one is units.Windows off
                 #              clock.step, because FAB's cooldown is Windows and mixing them
                 #              raises UnitError rather than being batch_windows-fold wrong. Two
                 #              typed stamps of one event is the point, not a duplication.
                 "due", "novelty", "token_seen", "shift_at_windows")

    def __init__(self, configs, wires, warnings):
        for name in self.__slots__:
            setattr(self, name, None)
        self.configs, self.wires, self.warnings = configs, wires, warnings
        self.refusals, self.stage = [], "configs"

    def __repr__(self):
        return (f"<System {len(self.configs or ())} config(s), {len(self.wires or ())} wire(s), "
                f"stage={self.stage!r}>")


def plan():
    """The assembly order and the loop order, as data, WITHOUT CALLING ANYTHING.

    Returns (ASSEMBLY_ORDER, LOOP_ORDER). This exists so the shape of the composition root can be
    read, documented and tested on a tree where nothing is implemented -- which is the state the
    contract is frozen in, and the state ten implementation agents start from.

    DEFERRED_ENTRY_POINTS is deliberately NOT returned here. It is not part of the order; it is the
    list of entry points the order does not yet reach, with the phase that will reach them. Folding
    it into this return would let a reader take "in plan()" as "called", which is the exact
    confusion the deferred table exists to prevent.
    """
    return ASSEMBLY_ORDER, LOOP_ORDER


def compose(environ=None, *, restored=None):
    """Resolve every Config, then build every object, handing each package what it needs.

    Returns a System. Raises NotImplementedError from the first unimplemented stub, with
    System.stage on the partially built record naming how far it got -- so the failure says which
    package owes what rather than "something is missing".

    `environ` is passed straight to spine.assemble.build. Pass the process environment: build()
    warns when it is None because the typo net then has nothing to scan, and this file may not name
    os.environ (check O1).

    `restored` IS AN OVERRIDE AND NO LONGER THE ONLY WAY IN. It was previously the only route --
    the Snapshot had to be produced by an entry point script this file could not see, which put
    CKPT.resume_source, CKPT.load and CKPT.check_geometry in a file no check reads while six rows
    here already consumed their output. THE ROOT NOW PERFORMS THE RESUME (the `resume` rows in
    ASSEMBLY_ORDER); passing a Snapshot here overrides that read, so a test can inject a synthetic
    one without a file on disk.

    THE ONE PLACE EVERY PACKAGE'S CONFIG IS HELD AT ONCE. Each package receives its OWN Config and
    asserts so with `cfg.owned_by("PREFIX")` at the head of every entry point; a wrong hand-off from
    here is therefore a startup failure rather than a plausible wrong number in a report.
    """
    configs, wires, warnings = _build(environ=environ)
    sysm = System(configs, wires, warnings)

    run, lm, data, tok, sig = (configs["RUN"], configs["LM"], configs["DATA"],
                               configs["TOK"], configs["SIG"])
    fab, mem, dom, cap, opt = (configs["FAB"], configs["MEM"], configs["DOM"],
                               configs["CAP"], configs["OPT"])
    world, ckpt, ev = configs["WORLD"], configs["CKPT"], configs["EVAL"]

    # -- 1. process: arithmetic and randomness, before any tensor exists -------------------------
    sysm.stage = "process"
    sysm.process = run_api.process_setup(run)
    sysm.mode = run_api.mode(run)
    sysm.streams = run_api.streams(run, RNG_SUBSYSTEMS)

    # -- 2. the resume, READ before anything is built and APPLIED beside each constructor ---------
    # Read here because every `restored=`/`resume=` argument below needs the payload, and because
    # the geometry gate has to refuse before the first allocation. APPLIED at the `restore` rows
    # rather than inside CKPT because CKPT.save takes `payload` as an ARGUMENT and CKPT.load runs
    # before the objects exist -- the fan-out is structurally outside that package, not merely
    # inconveniently placed there.
    sysm.stage = "resume"
    sysm.resume_src = ckpt_api.resume_source(ckpt)
    if restored is None and sysm.resume_src is not None:
        restored = ckpt_api.load(ckpt)
    sysm.snapshot = restored
    saved = {} if restored is None else (restored.payload or {})

    # -- 3. refusals that need two packages' numbers ---------------------------------------------
    # RUN's EPOCHS>1 guard needs DATA's resample flag; WORLD's horizon ceiling needs LM's ctx.
    # Neither can live in a levers.py, and both must fire BEFORE anything is allocated.
    sysm.stage = "refuse"
    sysm.refusals = list(run_api.startup_refusals(run, disk_stream=bool(data.resample)))
    sysm.refusals += list(world_api.startup_refusals(world, ctx_tokens=int(lm.ctx)))

    # -- 4. geometry, then the corpus -------------------------------------------------------------
    sysm.stage = "geometry"
    sysm.geometry = lm_api.resolve(lm)

    sysm.stage = "corpus"
    sysm.areas = data_api.open_areas(data, seed=int(run.seed))
    if "DATA" in saved:
        sysm.stage = "restore.data"
        data_api.restore_stream_state(data, sysm.areas, saved["DATA"])

    # -- 5. the vocabulary, which MEASURES bytes/token --------------------------------------------
    # Ordered here and not earlier because build_vocabulary needs the corpus, and ordered before
    # DATA.data_plan and SIG.build because both need the measurement. derive.bytes_per_token is the
    # only estimator in the tree; the mean-over-vocabulary-entries form it replaces had an error
    # that changes SIGN with vocabulary size, and the signature width 614 was chosen off it.
    sysm.stage = "vocab"
    sysm.vocab = tok_api.build_vocabulary(
        tok, area_heads=sysm.areas.bodies, seed=int(run.seed), soft_cap=None)
    if "TOK" in saved:
        # AFTER the merges have been replayed from d_vocab_read_path: this call's refusal compares
        # the state's merge count against the vocabulary that was just built, and has nothing to
        # compare before it exists.
        sysm.stage = "restore.tok"
        tok_api.restore_vocab(tok, saved["TOK"], sysm.vocab)

    # -- 6. THE GEOMETRY GATE. Nothing above this line allocated a parameter. ----------------------
    # LM.build_model below is the first allocation. The old gate fired only after the tokenizer had
    # resolved and the corpus had been pulled, so a FAB_NMAX change died as five tensor shapes
    # naming no knob on a warm GPU (:4413-4468).
    sysm.stage = "gate"
    sysm.manifest = _geometry_manifest(sysm)
    if restored is not None:
        ckpt_api.check_geometry(ckpt, restored, sysm.manifest)

    sysm.stage = "plan"
    sysm.plan = data_api.data_plan(
        data, sysm.areas, epochs=int(run.epochs), win_tokens=int(lm.ctx),
        bytes_per_token=float(sysm.vocab.bytes_per_token))

    # -- 7. EPOCH 0's MATERIAL, drawn here because two rows below need it -------------------------
    # OPT.build needs run_windows measured from a segmentation that exists (opt/api.py::build), and
    # SIG.warm_up takes the stream. The epoch level draws every LATER epoch's; the duplication is
    # the honest shape and the old tree has it too (:4104 and :6513 both call _resample()).
    sysm.stage = "stream"
    sysm.stream = data_api.draw_stream(
        data, sysm.areas, sysm.plan, epoch=0, seed=int(run.seed))

    sysm.stage = "segment"
    sysm.segmentation = tok_api.tokenize(
        tok, sysm.vocab, sysm.stream.bytes, sysm.stream.labels,
        regularize=True, seed=int(run.seed))

    # -- 8. the model, the signature space, and the two populations -------------------------------
    sysm.stage = "model"
    sysm.model = lm_api.build_model(
        lm, sysm.geometry, device=sysm.process.device, seed=int(run.seed))
    if "LM" in saved:
        sysm.stage = "restore.lm"
        lm_api.load_state(lm, sysm.model, sysm.geometry, saved["LM"])

    sysm.stage = "signature"
    sysm.sig = sig_api.build(
        sig, width_units=_signature_width(lm, sysm.vocab), alphabet_size=_alphabet_size(sig, lm),
        device=sysm.process.device, generator=sysm.streams["sig"])
    if "SIG" in saved:
        sysm.stage = "restore.sig"
        sig_api.load_state_dict(sig, sysm.sig, saved["SIG"],
                                sidecar=_sidecar(sysm, restored, "SIG"))

    sysm.stage = "fabric"
    sysm.fabric = fab_api.build(
        fab, d_model=int(lm.width), signature_dim=int(sig.d),
        device=sysm.process.device, generator=sysm.streams["fabric"])
    if "FAB" in saved:
        sysm.stage = "restore.fab"
        fab_api.load_state_dict(fab, sysm.fabric, saved["FAB"],
                                sidecar=_sidecar(sysm, restored, "FAB"))

    sysm.stage = "world"
    sysm.world = world_api.build(
        world, d_model=int(lm.width), device=sysm.process.device,
        ctx_tokens=int(lm.ctx), rng=sysm.streams["world"])
    if "WORLD" in saved:
        # STRICTLY BEFORE OPT.build: replaying the grown population first is what lets the
        # optimizer below be constructed with the SAME param-group structure the checkpoint has,
        # and without it OPT's param_group_shape refusal fires on every resume of a run that grew.
        sysm.stage = "restore.world"
        world_api.load_into(world, sysm.world, saved["WORLD"])

    sysm.stage = "store"
    sysm.store = mem_api.open_store(
        mem, key_dim=int(lm.width), vocab_slots=int(lm.vocab_slots),
        device=sysm.process.device, rng=sysm.streams["memory"], lm_kind=lm.arch,
        restored=saved.get("MEM"))

    sysm.stage = "partition"
    sysm.partition = dom_api.open_partition(
        dom, sig_dim=int(sig.d), vocab_slots=int(lm.vocab_slots), device=sysm.process.device,
        rng=sysm.streams["domains"], restored=saved.get("DOM"))

    # -- 9. the capacity valve, and the refusal that needs the population -------------------------
    # new_valve's `restored` is the LIFTED CAP alone, because Valve.origin has to record where the
    # STARTING cap came from. CAP.restore then puts back what that one argument cannot carry -- the
    # two pin clocks and the high-water marks, which is the other half of M38 -- and it runs before
    # the refusal so the refusal is taken against the restored ceiling.
    sysm.stage = "valve"
    sysm.valve = cap_api.new_valve(cap, restored=saved.get("CAP"))
    if "CAP" in saved:
        sysm.stage = "restore.cap"
        cap_api.restore(cap, sysm.valve, saved["CAP"])
    sysm.refusals += list(cap_api.startup_refusals(
        cap, sysm.valve, live_experts=sysm.fabric.n_live))

    # -- 10. the optimizer. OPT NEVER WALKS A MODULE TREE -----------------------------------------
    # The old tree assembled `_base` by reaching into six modules at :4700-4707. Here every package
    # that has parameters hands over a plain list and the root concatenates them, so a package
    # cannot be silently left out of the optimizer by an ablation flag about something else.
    sysm.stage = "optimizer"
    # BUILT ONCE AND HELD. _n_params needs the same list for RUN.bench_summary, and calling
    # _base_parameters a second time appends its no-parameters() warning a second time -- turning
    # the one did-it-fire signal for "a package contributed nothing to training" into a count
    # nobody can read.
    sysm.base_params = _base_parameters(sysm)
    sysm.optimizer = opt_api.build(
        opt,
        param_groups={"base": sysm.base_params,
                      "encoder": list(sig_api.encoder_parameters(sig, sysm.sig))},
        run_windows=_run_windows(sysm))
    if "OPT" in saved:
        # THE ONLY OPT RESTORE PATH, as of 2026-09-02 (Q-OPT-4 RESOLVED (d)). build() used to take
        # `resume=saved.get("OPT")` as well -- one Snapshot.payload into two entry points in
        # adjacent rows -- and the parameter is gone, because the work it would do does not exist:
        # the module restores above run STRICTLY BEFORE this point precisely so the param groups
        # assembled at :1726-1729 already have the checkpoint's structure. A second restore path
        # would also carry state past opt.ckpt.loaded / opt.ckpt.refused, which live here.
        # The param_group_shape refusal (ISSUES P1-L50) compares the saved shape against the LIVE
        # groups, which do not exist until build returns; OPT.state_dict now DECLARES it writes
        # that shape, which it did not until the same edit, so the refusal has something to
        # compare against instead of being armed against nothing.
        sysm.stage = "restore.opt"
        opt_api.load_state(opt, sysm.optimizer, saved["OPT"])

    # -- 11. the clocks, epoch 0's length, and the encoder warm-up --------------------------------
    sysm.stage = "clock"
    sysm.clock = run_api.new_clock(
        run, batch_windows=int(opt.batch_windows), accum=int(opt.accum),
        resume_step=0 if restored is None else restored.step,
        resume_epoch=0 if restored is None else restored.epoch)

    # Epoch 0 is never rolled into, so its length is declared here rather than at stage E. It is a
    # COUNT OF WINDOWS measured on the segmentation that exists, never stream_bytes // ctx.
    sysm.stage = "epoch0"
    sysm.clock.begin_epoch(_windows_in_epoch(sysm))

    # The encoder is trained BEFORE the loop, which is why this needs the stream and the optimizer
    # to be in place already. Without it every window of the run is routed through a randomly
    # initialised encoder while the AdamW built above steps it on zero gradients.
    # `opt` is documented as THE ENCODER OPTIMIZER and this now hands over exactly that --
    # sysm.optimizer.encoder, the AdamW over param_groups["encoder"] (Q-OPT-7 RESOLVED (a),
    # 2026-09-02). Until then OptState was declared as "both AdamW instances" and named neither, so
    # the root had no expression for one of them and handed SIG the whole state: an object through
    # which SIG could have stepped the language model. It was recorded rather than closed by
    # guessing a field name, and naming the two fields in opt/api.py's RECORD TYPES block is what
    # closed it -- K11 resolves a `produces` token against that block, so `encoder` is checkable
    # provenance rather than a comment.
    # AND THE REPORT IS BOUND, because until 2026-09-04 this call was a BARE EXPRESSION
    # STATEMENT and the WarmupReport it returns went on the floor. sig/api.py::WarmupReport
    # says it in as many words -- "'collapsing' is a RUN-LEVEL FAILURE and NO signature in
    # this tree takes it as an argument: this record is what the composition root has to act
    # on itself" -- and the row for this stage in ASSEMBLY_ORDER repeated the sentence while
    # the code below it discarded the value. The point was moot only while the verdict could
    # not be produced: src/sig/api.py::_stop_verdict held the ABSOLUTE collapse arm behind
    # `len(curve) < 2`, and at the shipped SIG_WARMUP / SIG_WARMUP_PROBE_EVERY a fully
    # collapsed encoder returned "budget". That arm now takes a one-point curve, so the
    # run-level failure is reachable and the root was the only reader that could see it.
    sysm.stage = "warmup"
    sysm.warmup = sig_api.warm_up(sig, sysm.sig, stream=_signature_stream(sysm, sig),
                                  seen_units=_signature_units(sysm, sig),
                                  opt=sysm.optimizer.encoder)
    # WHAT THE ROOT DOES WITH IT, AND WHAT IT DELIBERATELY DOES NOT DO. Neither
    # sig/api.py::warm_up nor docs/04_CONTRACT.md's SIG section says what "act on it" MEANS:
    # both say the verdict is a run-level failure and stop there. So the report is CARRIED to
    # a place a reader has -- System.warmup for the record itself, System.warnings for the
    # sentence -- and the policy is NOT invented here. Appending to System.refusals would
    # make a collapsed encoder abort the run, and raising would kill the run before the
    # report that carries the numbers is printed; both are rulings, and an unruled one taken
    # silently at a call site is how a policy gets into this tree without anybody choosing
    # it. The warning SAYS SO in the line the operator reads, so "the root acted" cannot be
    # read off a warnings entry that only forwards the verdict.
    if sysm.warmup is not None and sysm.warmup.verdict == "collapsing":
        sysm.warnings.append(
            f"RUN-LEVEL FAILURE, not a warning: SIG.warm_up returned verdict='collapsing' "
            f"-- the encoder's separation fell to {sysm.warmup.separation_final!r} from a "
            f"peak of {sysm.warmup.separation_peak!r} over {sysm.warmup.steps} optimizer "
            f"step(s) and {sysm.warmup.probes} probe(s). Every window of this run is routed "
            f"through that encoder, so SHIFT_DIST, the boundary count and the domain count "
            f"downstream of it are measurements of a collapsed space and not of the corpus "
            f"-- which is the failure sig/api.py::WarmupReport records from the other end "
            f"(0.16 -> 0.05 read as a converged plateau, 0 boundaries, 1 domain, and every "
            f"downstream line still printed). THIS ENTRY IS A CARRIER AND NOT A POLICY: the "
            f"root does not refuse the run here, because neither sig/api.py::warm_up nor the "
            f"contract says what acting on this verdict is, and the report is on "
            f"System.warmup for whoever rules on it.")

    # THE PERIODS ARE ARGUMENTS AND THE CALL WAS NOT PASSING ANY. new_cadences(run: Config, *,
    # periods) is keyword-only with no default (train/api.py::new_clock), so this line was a TypeError on
    # every compose() -- unreachable only because RUN.process_setup raises several rows earlier.
    # The signature was fixed on 2026-08-30 and the call site was not, which is the same shape
    # capacity/api.py::<module> records for derive.pin_tick: a file asserting a repair as done with the
    # call the repair requires never written. Each period comes from the package that DECLARES its
    # kind, as units.Windows; K9 refuses a bare lever read here.
    sysm.stage = "cadence"
    periods = {"curve": eval_api.curve_period(ev),
               "dom.manage": dom_api.manage_period(dom),
               "fab.manage": fab_api.manage_period(fab),
               "dom.rekey": mem_api.rekey_period(mem),
               "ckpt": ckpt_api.save_period(ckpt)}
    sysm.cadences = run_api.new_cadences(run, periods=periods)

    # AND THE AUDIT WAS A ROW NOBODY CALLED. `grep cadence_audit` found it only inside its own row
    # prose: the one statement that makes ISSUES P1-C11 visible -- ten cadence defaults longer than a
    # 937-window run -- was never executed, while K6 credited the row and passed. It STATES, it does
    # not raise, so its lines join the warnings the report must print; an EMPTY list is a real
    # result and must be printed as one.
    sysm.stage = "audit"
    sysm.warnings.extend(run_api.cadence_audit(
        run, run_windows=_run_windows(sysm), periods=periods))

    # -- 12. persistence: the one predicate, then the retention policy and the save signal --------
    # saving_on precedes new_retention because Retention.inert_reason is populated when best_keep
    # > 0 AND SAVING IS OFF, and re-typing the six-spelling test at a call site is the defect that
    # wrote a directory literally named `0` into the repository root.
    sysm.stage = "persist"
    sysm.saving = ckpt_api.saving_on(ckpt)

    sysm.stage = "retention"
    sysm.retention = ckpt_api.new_retention(
        ckpt, restored=None if restored is None else restored.best_state)
    sysm.save_flag = ckpt_api.install_save_signal()

    sysm.stage = "assembled"
    return sysm


# ==================================================================================================
# The small joins. Each one is here because it needs more than one package's Config, which is the
# definition of this file's job -- and each one is a FUNCTION rather than an inline expression so
# that the quantity has a name a reader can grep for.
# ==================================================================================================

def _signature_width(lm, vocab):
    """THE ONE SIGNATURE WIDTH, resolved once, here, and never recomputed as the vocabulary grows.

    spine.assemble lists this under "considered and rejected": it cannot be a Coupling because
    bytes_per_token is MEASURED on a corpus the tokenizer has not seen when build() freezes, and a
    Config that can still be written after startup is a Config the report cannot claim the run
    used. So it is derive-and-keep: SIG records the answer on SigState and every later call in that
    package reads it from there. The cost of the alternative is measured -- the old tree resolved
    the same knob in two places, `max(WIN, int(WIN*bpt))` = 614 bytes in training at :5675 and
    `max(1, SIG_WIN)` = ONE BYTE in eval at :3919, so every eval-path routing decision in every
    report was made on a one-byte signature and nothing failed.
    """
    from spine import derive
    return derive.signature_width_bytes(int(lm.ctx), float(vocab.bytes_per_token))


def _alphabet_size(sig, lm):
    """The encoder embedding's row count: 256 under space="bytes", LM.vocab_slots under "tokens".

    Sized at the SLOT CEILING and not at the live vocab_size, because widening an embedding mid-run
    changes the encoder optimizer's moment shapes -- ISSUES P3-H24 from the other side. SIG records it
    in its checkpoint sidecar and refuses a resume that disagrees.
    """
    return int(lm.vocab_slots) if sig.space == "tokens" else 256


def _base_parameters(sysm):
    """Every trainable parameter that is not SIG's encoder, as ONE plain list.

    Collected from the objects the packages returned, never by walking a module tree from inside
    OPT. The fabric's population is preallocated, so growth never adds a parameter here; WORLD's
    dynamics population DOES mint parameters mid-run and OPT's add_param_group is handed to
    WORLD.manage as a callable for exactly that reason -- a row that is still deferred, though no
    longer for the reason written here until 2026-09-02. OptState named neither of its two AdamW
    instances, so the root could not address one; the fields are `base` and `encoder` as of Q-OPT-7,
    and a mid-run world parameter joins the BASE group, because the encoder group is under SIG's
    cadence. What the row still lacks is a position: WORLD.manage has no ASSEMBLY_ORDER or
    LOOP_ORDER row, so nothing hands the callable over.

    THREE OBJECTS, NOT FOUR. The ASSEMBLY_ORDER row said "LM+FAB+WORLD+MEM params" until
    2026-08-30 and this body has always walked three: MEM has no module and no parameters at all,
    so the row named a package that could never have contributed. The row now matches the body.

    AND THE ABSENCE IS RECORDED RATHER THAN SKIPPED. `getattr(obj, "parameters", None)` returns
    None for any object that does not have one, and Population's declared fields
    (fabric/api.py::<module>) include no parameters() -- so if P4 does not add one, the fabric
    contributes ZERO parameters to the optimizer and every check in this tree stays green. That is
    the silent-default shape the header condemns twenty lines above about streams.get(), so the
    absence goes onto System.warnings, where the report has to print it.
    """
    out = []
    for name, obj in (("LM.model", sysm.model), ("FAB.population", sysm.fabric),
                      ("WORLD.world", sysm.world)):
        params = getattr(obj, "parameters", None)
        if callable(params):
            out.extend(params())
        elif sysm.warnings is not None:
            sysm.warnings.append(
                f"OPT.build: {name} exposes no parameters(), so it contributes NOTHING to the "
                f"'base' param group. Nothing else in the tree says so, and an optimizer that "
                f"silently trains fewer tensors than the report claims is ISSUES P1-L50 from the "
                f"other side.")
    return out


def _run_windows(sysm):
    """The run length in WINDOWS, which OPT divides by d_effective_batch_windows to get its horizon.

    A plain argument and NOT a wire, and the distinction has a defect behind it. assemble.NOT_WIRES
    rejects `RUN.epochs -> OPT.d_lr_horizon` on the grounds that it IS the defect -- EPOCHS setting
    both the run length and the cosine horizon makes two runs differing only in EPOCHS two
    different learning-rate experiments. THIS quantity is rejected on the OTHER ground: the stream
    length in windows depends on the TOKENIZATION, which has not happened when build() freezes.
    Both rejections are real and they are not the same one; the contract records that, because the
    machinery the old tree wrote to paper over it (`_project`/`_lr_total`/`_proj_lr`, :6335-6376)
    was rewritten once for the same fault and produced the E8 p=0.760 under-annealing.

    Computed as len(segmentation) // ctx from the token stream that ACTUALLY EXISTS, times epochs
    -- never `stream_bytes // ctx`, which divides a BYTE budget by a TOKEN window and overstates
    the step count by the compression ratio (~2.5x at a grown vocabulary).

    THE BODY DID NOT DO WHAT THAT PARAGRAPH SAYS AND COULD NOT HAVE. It read `plan.run_windows`,
    and `run_windows` IS NOT A FIELD OF Plan: data/api.py::<module> declares Plan as (protocol,
    schedule, phase_bounds, per_area_draw, exposure, gates), so the line was a latent
    AttributeError sitting under a docstring describing the correct computation. It could not be
    fixed without the stream, and nothing drew a stream -- which is the same missing epoch level
    that left DATA.draw_stream with no caller at all. Both are repaired together: the `stream` and
    `segment` rows in ASSEMBLY_ORDER produce the Segmentation this now measures.

    THE PROJECTION IS STILL A DIFFERENT NUMBER, AND NOTHING RECONCILES THEM. This is the horizon,
    resolved ONCE at OPT.build (opt/api.py::<module>) from epoch 0's length; RunClock.begin_epoch
    re-measures every epoch, and minting shortens every later one. Both are Windows so nothing
    raises. See Q-OPT-5.

    IT RETURNS units.Windows AND USED TO RETURN A BARE INT, which both of its consumers refuse.
    derive.cadences_that_cannot_fire raises UnitError on a non-Windows at both ends (derive.py::cadences_that_cannot_fire)
    and derive.opt_steps_from_windows does the same (derive.py::opt_steps_from_windows), so RUN.cadence_audit would
    have raised on its first call and OPT.build on its first horizon -- unreachable today only
    because RUN.process_setup raises several rows earlier, which is this file's oldest shape and
    the reason K7 exists. ISSUES P1-H51 is the general case: all 35 Clock-unit levers resolve to bare
    ints and the typing is real only where derive or assemble puts it back, which for this quantity
    is here, at the one place it is computed.
    """
    from spine import units
    return units.Windows(_windows_in_epoch(sysm) * int(sysm.configs["RUN"].epochs))


def _windows_in_epoch(sysm):
    """This epoch's length in WINDOWS: len(Segmentation.ids) // LM.ctx.

    The ONE arithmetic that turns a token stream into a window count, named so both readers -- the
    LR horizon above and RunClock.begin_epoch -- take it from the same place. `stream_bytes // ctx`
    is the form this replaces: it divides a BYTE budget by a TOKEN window and overstates the count
    by the compression ratio (~2.5x at a grown vocabulary).

    WHERE THE BYTE FORM ACTUALLY LIVED IN THE OLD TREE, CORRECTED (Q-DATA-8, ruled 2026-09-02).
    This docstring, docs/04_CONTRACT.md and train/api.py all used to say the LR horizon and every
    ETA were computed from `STREAM_LEN // WIN`. THEY WERE NOT, and the claim would send an
    implementer to the wrong function. Of the 28 STREAM_LEN sites, `STREAM_LEN // WIN` appears in
    exactly two live places: the pre-run [probe] ETA banner (:4317) and one cadence period,
    `_due("lmcurve", max(1, (STREAM_LEN // WIN) // 8))` (:7319). :4719 is a prose comment. The
    runtime LR horizon and the ETA both went through `_project`, whose `_total_steps = EPOCHS *
    (len(stream) // WIN)` (:6236) and `_per = max(1, len(stream) // WIN)` (:6339) measure the TOKEN
    stream -- `byte_stream` is the separate byte one, and :5656 divides the two to get the measured
    bytes/token. So the horizon was ALREADY token-measured, and its real defect is the shrinkage
    projection at :6338-6362, which is Q-OPT-5 and belongs to OPT. What this repair kills is the
    ~2.5x overstatement in the banner an operator sizes a multi-day run from.

    THE FIVE NUMBERS PRINT TOGETHER, AT STARTUP, FROM HERE -- not from RUN.bench_summary. A step
    count 2.5x the truth is invisible unless `stream_bytes`, len(Segmentation.ids), the measured
    bytes_per_token, _windows_in_epoch(sysm) and _run_windows(sysm) appear on ONE line where the
    ratio is checkable by eye. bench_summary cannot carry it and it was a mistake to propose that
    it should: its frozen signature (run, clock, *, elapsed_s, bytes_per_window, n_params, timing)
    reaches NONE of the five -- bytes_per_window is the PRODUCT ctx x bytes_per_token and RUN may
    not read LM.ctx to divide it back out, and RunClock carries step/flushes/backwards/opt_steps/
    epoch/batch_len and nothing else -- and it returns None when `bench` is off, i.e. it would be
    invisible on every ordinary run, which is the armed-but-inert shape this project exists to end.
    The composition root is the only place that holds all five at once and is exempt from the
    ownership rule that stops RUN from assembling them. P4 prints it once, after the `segment`
    stage, on EVERY run.
    """
    return max(1, len(sysm.segmentation.ids) // int(sysm.configs["LM"].ctx))


def _geometry_manifest(sysm):
    """The LIVE geometry manifest CKPT.check_geometry compares a Snapshot against.

    {field: (value, rule, env_name, why)} -- the four fields ckpt/api.py::<module> gives GeometryField, in
    that order. It is assembled HERE because it spans four packages' Configs and check_geometry may
    not import any of them.

    WHAT IS IN IT AND WHAT IS NOT, STATED SO THE REPORT CAN SAY SO. Every field below is a LEVER
    READ or LM.resolve's already-computed geometry, so the whole manifest exists before a single
    parameter does -- which is the point: the gate must refuse in seconds, not after a warm GPU.
    THE GROWN POPULATION COUNTS ARE ABSENT, and they are absent for a reason that cannot be
    engineered away here: WORLD.geometry(world, w) needs a BUILT world, and the only build that
    could supply it is the one this gate exists to happen before. check_geometry's own contract
    covers that case -- a field present in the checkpoint and absent from the manifest is reported
    UNCHECKED, not skipped -- and the population counts are then re-refused, in both directions, by
    WORLD.load_into (M43) and FAB.load_state_dict at their own rows.

    ONE THING HERE IS THE OWNER'S, NOT TWO. Q-CKPT-1 asked whether the eleven packages without a
    geometry() of their own should get one; RESOLVED 2026-09-02, they should NOT, and the framing
    is retired rather than managed. A package geometry() can only be called after that package has
    built something, and this manifest's defining property is that it exists BEFORE the first
    allocation -- so the eight or eleven functions would either take a Config and no object, at
    which point they are a lever read the root already does, or they could not be called at the
    gate at all. Worse, the EXACT/MAY_WIDEN RULE would move into the package, and ckpt/api.py says
    in as many words that the rules are the owner's: a package grading the refusal that protects it
    is the shape aff_min and genuine_min live in EVAL to avoid. What remains the owner's is that
    GeometryField is a record type P4 defines, so this returns the four fields as a plain tuple in
    the declared order rather than constructing a type that does not exist yet.

    IT MUST BE BUILT WITH sysm.geometry PRESENT, AND THAT IS A REFUSAL BELOW RATHER THAN A COMMENT.
    LM declares layers=0 as a SENTINEL and LM.resolve replaces it with the real depth; the override
    loop at the bottom skips a field LMGeometry does not carry, so a manifest built before resolve()
    records lm.layers = 0 -- the sentinel, not the depth. A run at LM_LAYERS=0 and a run at
    LM_LAYERS=4 are then the SAME model recording two different values, an EXACT mismatch and a
    spurious refusal on a resume that is actually compatible. That is a wrong measurement inside the
    instrument that decides whether a resume happens, and it was reachable by writing the two calls
    in the wrong order.
    """
    lm, sig = sysm.configs["LM"], sysm.configs["SIG"]
    fab, world = sysm.configs["FAB"], sysm.configs["WORLD"]
    geom = sysm.geometry
    if geom is None:
        raise RuntimeError(
            "_geometry_manifest was called before LM.resolve: sysm.geometry is None, so lm.layers "
            "would record LM's SENTINEL 0 instead of the resolved depth and a compatible resume "
            "would be refused on an EXACT mismatch that describes nothing. Build the manifest "
            "after sysm.geometry is set (compose(): resolve, then vocabulary, then this).")
    man = {
        "lm.width":     (int(lm.width), "EXACT", "LM_WIDTH", "every tensor in the model"),
        # `layers`, NOT `depth`, and the environment name is LM_LAYERS. LM declares
        # ['anchor_uses','anchor_w','arch','compose','ctx','dropout','heads','layers',
        # 'mask_dead_rows','new_row_init','vocab_slots','width'] -- there is no `depth`, and
        # Config.__getattr__ RAISES on an undeclared name rather than returning a default. So the
        # first draft of this line killed every compose() at the gate stage, and the reason nothing
        # caught it is the reason it is worth this comment: RUN.process_setup raises
        # NotImplementedError several rows EARLIER, so the crash was unreachable and K2 -- "the
        # composition root imports and fails only at a stub" -- passed on a tree that could not run.
        # A defect hidden behind an earlier stub is this project's oldest shape. K7 below is the
        # general form of the check that would have caught it at author time.
        "lm.layers":    (int(lm.layers), "EXACT", "LM_LAYERS", "the layer stack"),
        "lm.heads":     (int(lm.heads), "EXACT", "LM_HEADS", "head partition of width"),
        "lm.ctx":       (int(lm.ctx), "EXACT", "LM_CTX", "positional table extent"),
        "lm.vocab_slots": (int(lm.vocab_slots), "MAY_WIDEN", "LM_VOCAB_SLOTS",
                           "the embedding and output rows; a smaller checkpoint is a prefix"),
        "sig.d":        (int(sig.d), "EXACT", "SIG_D", "the signature space the router keys on"),
        "sig.space":    (str(sig.space), "EXACT", "SIG_SPACE",
                         "bytes vs tokens changes the encoder's alphabet"),
        # ---- THE FOUR FIELDS THAT DECIDE WHICH TENSORS EXIST, not how big they are. The gate had
        # ---- twelve dimensions and none of these, so two checkpoints with identical numbers and
        # ---- incompatible parameter SETS compared equal. All four are pure frozen-Config reads, so
        # ---- they cost nothing: the manifest was already computable before a single tensor existed
        # ---- and still is.
        "lm.arch":      (str(lm.arch), "EXACT", "LM_ARCH",
                         "gru and transformer are different modules. LM_ARCH=gru LM_LAYERS=1 and a "
                         "transformer at the same numbers produced an IDENTICAL manifest, and the "
                         "gate exists because a checkpoint built one way cannot load into the "
                         "other"),
        "lm.compose":   (bool(lm.compose), "EXACT", "LM_COMPOSE",
                         "lm/api.py::build_model: when compose is FALSE emb and head are constructed, when "
                         "TRUE they are NOT CONSTRUCTED AT ALL. Flipping it across a resume changes "
                         "the parameter SET rather than a dimension, which is the one thing a "
                         "shape comparison cannot notice"),
        "sig.mode":     (str(sig.mode), "EXACT", "SIG_MODE",
                         "a trained encoder against a frozen hashed-bigram modulus. Same d, "
                         "different object, and the signature is the router's only input"),
        "fab.emb_hid":  (int(fab.emb_hid), "EXACT", "FAB_EMB_HID",
                         "the shared identity embedder's hidden width -- a real tensor dimension "
                         "that FAB.load_state_dict names in its LEVERS READ and compares ONLY "
                         "against the sidecar, which is None on every resume, so nothing checked it "
                         "at either end"),
        "fab.slots":    (int(fab.slots), "MAY_WIDEN", "FAB_SLOTS",
                         "preallocated; growth only advances n_live, so a smaller cap IS a prefix"),
        "fab.rank":     (int(fab.rank), "EXACT", "FAB_RANK", "an inner dimension; no prefix valid"),
        "fab.dk":       (int(fab.dk), "EXACT", "FAB_DK", "an inner dimension; no prefix valid"),
        # THE TENSOR EXTENT IS NOT `slots`, AND fab.slots ALONE LET A NARROWED ONE THROUGH.
        # fabric/levers.py and fabric/api.py both say it in one expression -- cap = max(n0, slots),
        # and A is allocated (cap, d_model, rank) -- so at FAB_N0 > FAB_SLOTS the population's
        # rows are sized by n0 and a resume that lowers n0 narrows every fabric tensor while
        # fab.slots compares equal. n0 is the fifth name in FAB.load_state_dict's LEVERS READ and
        # was the only one of the five with nothing to compare against at either end; it arrives
        # here FOLDED INTO THE EXTENT rather than as its own field, because n0 changing under a
        # fixed cap moves n_live -- a state_dict buffer -- and not a shape, so recording it raw
        # would refuse resumes that change no tensor. Q-CKPT-1.
        "fab.cap":      (max(int(fab.n0), int(fab.slots)), "MAY_WIDEN", "FAB_N0 or FAB_SLOTS",
                         "max(n0, slots) is what FAB.build allocates A and B at; a smaller-cap "
                         "checkpoint IS a prefix, so this widens like slots and never narrows"),
        "world.lat":    (int(world.lat), "EXACT", "WORLD_LAT", "H22: recorded and never read"),
        "world.hid":    (int(world.hid), "EXACT", "WORLD_HID", "H22"),
        "world.route_d": (int(world.route_d), "EXACT", "WORLD_ROUTE_D", "H22"),
        "world.nmax":   (int(world.nmax), "MAY_WIDEN", "WORLD_NMAX", "H22"),
        "world.feedback": (bool(world.feedback), "EXACT", "WORLD_FEEDBACK", "H22"),
    }
    # LM.resolve is the authority on LM's shapes -- it is the row that refuses width % heads and
    # the ctx/pos_max overflow -- so where LMGeometry carries a field, its value replaces the raw
    # lever read above and pos_max joins the manifest. Two sources for one shape is how the
    # signature width came out 614 on one path and 1 on the other.
    for name in ("width", "layers", "heads", "ctx", "pos_max", "vocab_slots"):
        value = getattr(geom, name, None)
        if value is None:
            continue
        key = "lm." + name
        prior = man.get(key)
        rule = prior[1] if prior else "EXACT"
        env = prior[2] if prior else ("LM_" + name.upper())
        man[key] = (value, rule, env, "LM.resolve's resolved value, not the raw lever")
    return man


def _sidecar(sysm, restored, prefix):
    """The recorded geometry fields SIG and FAB compare their own state against on a restore.

    They take theirs as a `sidecar` argument rather than through the manifest above because their
    refusals run AFTER their build -- which is exactly why the manifest reports the grown counts as
    UNCHECKED rather than pretending to have checked them. THAT WORD IS FOR THIS DIRECTION ONLY --
    recorded, and absent from the manifest. The reverse (in the manifest, absent from the recording)
    is ckpt/api.py::check_geometry's REFUSAL, and three statements in this file borrowed the word for it.

    IT RETURNS None ON EVERY REAL RESUME AND BOTH REFUSALS ARE THEREFORE DISARMED -- STILL TRUE,
    FOR A DIFFERENT REASON THAN THE ONE WRITTEN HERE UNTIL 2026-09-02. That reason was "the save
    side records WORLD.geometry alone", which is the withdrawn C12 claim and is false: the recorded
    map is CKPT.save's `geometry`, and ROW_ARGUMENTS_ELSEWHERE declares that to be
    _geometry_manifest(sysm) -- a FLAT map with PREFIXED keys, 'sig.d' and 'fab.rank'. The live
    reason it returns None is therefore a SHAPE MISMATCH IN THIS FUNCTION: it indexes the recorded
    map by a bare package prefix, recorded.get('SIG'), and a flat prefixed map has no such key at
    any point in its life. Q-CKPT-2's first half is resolved; this is its residue, and it is HIGH.

    WHAT IS AND IS NOT STILL OWED, since four of the fields moved. lm.arch, lm.compose, sig.mode
    and fab.emb_hid joined the manifest on 2026-08-30, and fab.cap on 2026-09-02 -- so FAB's whole
    declared comparison set (slots, n0-via-cap, rank, dk, emb_hid) is now in the manifest and
    FAB.state_dict does NOT have to emit a sidecar it never claimed to emit. SIG's `width_units` is
    the one field that cannot be there: derive.signature_width_bytes reads Vocabulary.bytes_per_token,
    which is MEASURED over the build sample, so it fails the wire predicate the same way the
    couplings do -- it travels in SIG's own state blob, which SIG reads back from `sd`.
    THE OPEN QUESTION IS THEREFORE WHETHER THIS FUNCTION AND THE TWO `sidecar` PARAMETERS SURVIVE
    AT ALL, or whether a prefix SLICE of the recorded flat manifest replaces them. That is a frozen
    signature decision on sig/api.py and fabric/api.py, it is cheap while both are stubs, and it is
    the owner's: it is not reopened here.

    A GUARD THAT CANNOT FIRE IS A DEFECT EVEN WHERE THE CODE AROUND IT IS CORRECT, so the state is
    recorded instead of returned in silence: with a snapshot in hand and a payload for this package
    but no recorded slice, the warning below is the only place a report can learn that the width
    refusal did not run. Q-CKPT-2 asks for the producer.
    """
    if restored is None:
        return None
    recorded = getattr(restored, "geometry", None) or {}
    side = recorded.get(prefix)
    if side is None and sysm is not None and sysm.warnings is not None:
        sysm.warnings.append(
            f"{prefix}.load_state_dict: no '{prefix}' slice in the snapshot's recorded geometry, so "
            f"sidecar=None and its width/shape refusal DID NOT RUN. The recorded geometry is the "
            f"FLAT prefixed manifest (CKPT.save's geometry is _geometry_manifest); this lookup "
            f"wants a nested '{prefix}' key that nothing writes. Q-CKPT-2's residue.")
    return side


def _signature_stream(sysm, sig):
    """The unit stream in SIG's OWN alphabet: Stream.bytes at space="bytes", Segmentation.ids at
    "tokens".

    Named because it is a three-package quantity -- DATA's bytes, TOK's segmentation, SIG's
    declared alphabet -- and because getting it wrong is C4's shape: the old tree applied the
    encoder to one width on the training path and another on the eval path and nothing failed.
    NEVER Areas.holdout: the held-out block is physically removed from the training body so that no
    sampling rule can reach it, and an encoder warmed on it poisons the one number goal B rests on.
    """
    return sysm.segmentation.ids if sig.space == "tokens" else sysm.stream.bytes


def _signature_units(sysm, sig):
    """How much of that stream the warm-up may draw anchors from.

    THE WHOLE EPOCH-0 STREAM, and only here. `seen_units` bounds the draw to material the loop has
    actually reached, and pre-loop the loop has reached nothing -- the warm-up's entire purpose is
    to see the epoch's material before training starts, which is what the old tree passes at :5024
    (`len(ENC_SEQ)`). In the loop the same argument is the cursor, not the length.
    """
    return len(_signature_stream(sysm, sig))


# ==================================================================================================
# THE LOOP-SIDE JOINS
#
# compose() DOES NOT CALL THESE. They are the joins the LOOP needs, and they are here for the one
# reason everything else in this file is: each spans two packages, O10 forbids a package owning it,
# and the alternative is the same arithmetic written inline at a call site where nobody can audit it
# -- which is how the signature width came out 614 bytes on the training path and 1 byte on the eval
# path with every check green.
#
# EACH ONE IS NAMED BY THE ROW THAT CONSUMES IT, so a reader who meets `seen_units` in a row can grep
# for the answer instead of inferring it. Two of them (the batch cut, the geometry manifest) are
# named in ROW_ARGUMENTS_ELSEWHERE instead, for the reasons that table gives.
#
# WHAT IS DELIBERATELY NOT HERE, because writing it would be inventing a producer rather than naming
# one: a `logits_fn` (it must be THE PATH THE RUN TRAINED, eval/api.py::<module>, which runs through
# FAB.forward and so needs the flush's own novelty, live_domains and training); an `improving` EMA
# pair (FAB already keeps one and a second would be two mechanisms deciding the same question); an
# `owners` rule beyond the one the old tree used; a `plateau` boolean (WORLD holds that state).
# Those are the seven deferrals, and each is filed with what would close it.
#
# THE logits_fn IS STILL NOT FORMABLE, BUT ITS SHAPE AND ITS OWNER ARE NOW RULED (Q-MEM-10, RESOLVED
# 2026-09-02 (a)). When the missing data exist it is written HERE, once, as
# `_logits_fn(sysm, *, use_memory)`, beside _key_fn / _head / _sig_encode_fn, and it is the ONLY
# place softmax -> MEM.read(promote=False) -> MEM.blend -> log is written anywhere in the tree.
# NEITHER SIDE'S FROZEN SIGNATURE MOVES: MEM.blend keeps `model_probs` as probabilities and EVAL
# keeps `logits_fn`. The document's own recommendation was (c), passing `blend_fn` into the four
# scoring entry points, and it is NOT TAKEN: it moves four frozen EVAL `def`s and then makes each of
# the four bodies write the mix for itself, which is the ungated recomputed blend of C8 (prompt.py)
# and C9 (cl_bench.py) rebuilt inside the instrument line -- the exact thing memory/api.py's blend
# exists to prevent ("THE ARITHMETIC LIVES IN THIS PACKAGE so the mixing weight never travels").
# TWO CLOSURES, TWO SYSTEMS, AND THE READING NAMES WHICH. use_memory=False is the trained path;
# use_memory=True is the trained path plus retrieval, which has never entered training. FAB's
# `baseline_logits_fn` MUST ALWAYS BE THE MEMORY-OFF ONE, because fabric/api.py makes it
# load-bearing that the baseline comes from the same callable that produced `baseline_loss`, and a
# memory-on baseline there would silently undo the C3/H11 repair.
# WHAT IS STILL MISSING, so this stays a deferral and not a helper: FAB.forward needs `signature`,
# `domain_id`, `novelty` and `live_domains` per row. For a HELD-OUT window the closure can encode
# the signature itself with _sig_encode_fn and pass training=False and DOM's live count -- `novelty`
# is the one datum with no honest source off the training path, and it is named here rather than
# defaulted to zero in silence. For a STORED entry the domain id is Store.src, which is why the
# declared callable is `scorer(ctx, src) -> logits` and not `scorer(ctx)`; see MEM.judge below.
# ONE ARITY, WRITTEN ONCE: EVAL.wrongness_probe's `scorer` is the same callable and takes the same
# two arguments.
# ==================================================================================================

def _window_bounds(sysm, at_window):
    """The token-index bounds of ONE window into Segmentation.ids: (start, stop).

    Windows are CONTIGUOUS, NON-OVERLAPPING and LM.ctx wide -- the same arithmetic
    _windows_in_epoch counts with, stated once so the count and the cut cannot disagree. It is the
    slice TOK.on_window takes as `ids` and DOM.observe takes as `tokens`.
    """
    ctx = int(sysm.configs["LM"].ctx)
    start = int(at_window) * ctx
    return start, start + ctx


def _flush_bounds(sysm, at_window):
    """The bounds of one FLUSH's windows: [(start, stop)] x OPT.batch_windows.

    `x` is Segmentation.ids at these bounds, `y` is the same cut shifted ONE TOKEN -- next-token
    targets, which is what LM.lm_loss is (lm/api.py::<module>). MEM.write's `contexts` is the same `x`
    (MEM narrows it to key_win itself; that lever is in its own LEVERS READ list) and its `tokens`
    is `y`; `positions` is Segmentation.byte_pos at the same bounds and is TRUE BYTE OFFSETS, which
    memory/api.py::write requires against a 200+ byte drift.

    IT RETURNS BOUNDS AND NOT TENSORS ON PURPOSE. No file in src/ imports torch at P3 and the
    composition root does not run a loop, so building the batch here would put loop mechanism in a
    file whose docstring says it holds none. What has to exist in one place is the CUT -- the thing
    no entry point returns, because RunClock.advance appends to the accumulator and hands back a
    Tick. The loop slices; this names where.
    """
    n = max(1, int(sysm.configs["OPT"].batch_windows))
    return [_window_bounds(sysm, int(at_window) + i) for i in range(n)]


def _signature_cursor(sysm, sig, at_window):
    """How much of the unit stream the loop has REACHED, in SIG's own alphabet: `seen_units`.

    THE CURSOR, NOT THE LENGTH. _signature_units below is the whole epoch-0 stream and belongs to
    SIG.warm_up alone; in the loop the same argument bounds the draw to material training has
    actually seen, and handing over the length instead would let a contrastive pair be drawn from
    text the model has not reached.

    It is a UNIT CROSSING and that is why it has a name: `at_window` is Windows, `seen_units` is
    tokens under space="tokens" and BYTES under space="bytes". The token count is exact
    (at_window x LM.ctx); the byte count is read off Segmentation.byte_pos, which is the only
    exact byte coordinate in the tree -- never at_window x ctx x bytes_per_token, which is an
    average standing in for a measurement.
    """
    ctx = int(sysm.configs["LM"].ctx)
    i = int(at_window) * ctx
    if sig.space == "tokens":
        return i
    pos = sysm.segmentation.byte_pos
    if i >= len(pos):
        i = len(pos) - 1
    return int(pos[i])


def _sample_window(sysm, sig, at_window):
    """The st.width_units-wide slice of the unit stream this window is encoded from.

    ONE OBJECT, TWO CONSUMERS: SIG.encode takes it as `windows` and DOM.observe takes THE SAME
    OBJECT as `sample_window`, because domains/api.py::observe says a rekey cannot reproduce the
    signature otherwise -- so a second slicer at the DOM call site is a defect by construction, and
    that is the whole reason this is a function rather than an expression written twice.

    THE ONE DECISION IN IT, recorded rather than left implicit: the window is the width_units units
    ENDING AT THE CURSOR, i.e. the material just consumed. Nothing in the frozen surfaces states
    which end, and a run that encodes the units AHEAD of the cursor is encoding text the model has
    not trained on.
    """
    stream = _signature_stream(sysm, sig)
    end = _signature_cursor(sysm, sig, at_window)
    width = int(sysm.sig.width_units)
    start = end - width
    return stream[start if start > 0 else 0:end]


def _key_fn(sysm):
    """LM.encode bound to (lm, model): MEM.write's and MEM.maintain's `key_fn`.

    THE CALLABLE CLASS OF ARGUMENT HAS NO OTHER PRODUCER. It is an entry point partially applied,
    not a return value, so no `produces` column can hand it over without this file forming it --
    and memory/api.py's whole point is that MEM never imports LM.
    """
    lm = sysm.configs["LM"]
    return lambda x, **kw: lm_api.encode(lm, sysm.model, x, **kw)


def _head(sysm):
    """LM.decode bound to (lm, model): FAB.forward's and FAB.contribution's `head`.

    NOT a logits_fn: it decodes a hidden state that the fabric already produced. The logits_fn
    every probe wants is the WHOLE path including FAB.forward, and that one is not formable today
    -- see DEFERRED_ENTRY_POINTS.
    """
    lm = sysm.configs["LM"]
    return lambda h, **kw: lm_api.decode(lm, sysm.model, h, **kw)


def _sig_encode_fn(sysm):
    """SIG.encode bound to the SigState: DOM.rekey's `encode`.

    domains/api.py::observe.dom says in as many words that `encode` is SIG.encode passed in. The rekey MUST
    use the same callable the live path used or the partition drifts into two signature spaces that
    do not compare.

    IT HAS A SECOND CONSUMER SINCE 2026-09-02: EVAL.coherence's `encode` (Q-EVAL-10). Coherence
    measures "which centroid is this window of the CONTINUATION nearest", so it encodes at report
    time, and EVAL may not import SIG. It takes THIS callable under THE SAME NAME rather than a
    second one under a second name, for the reason above: two encoders would be two signature
    spaces, and the whole point of coherence is comparing a generated window against centroids
    built from real material in the same space.
    """
    sig = sysm.configs["SIG"]
    return lambda windows: sig_api.encode(sig, sysm.sig, windows)


def _periods(sysm):
    """{gate key: units.Windows} -- the periods RUN.new_cadences and RUN.cadence_audit take.

    ASSEMBLED HERE BECAUSE NO PACKAGE CAN. Each period belongs to the package that DECLARES its kind
    and arrives through that package's typed accessor -- EVAL.curve_period, DOM.manage_period,
    FAB.manage_period, MEM.rekey_period, CKPT.save_period -- and a mapping spanning six packages is
    exactly the object O10 forbids any one of them to build. RUN evaluates gates, and RUN owns no
    threshold THAT DECIDES ANYTHING THE MODEL COMPUTES -- which is the sentence new_cadences means,
    and the one sixth entry is the exception that has to be stated rather than smuggled.

    'progress' IS RUN'S OWN AND IT IS NOT A LEVER (Q-RUN-1, RESOLVED 2026-09-02: option (b)). It is
    RUN.PROGRESS_WINDOWS (run_api.PROGRESS_WINDOWS here), a module constant in train/api.py written units.Windows at its definition,
    driving the progress/ETA line and the profiler dump. It is HERE rather than wrapped at a call
    site for two reasons this file already states about the other five. First, its own rule sixty
    lines above LOOP_ORDER: "Every PERIODIC gate goes through Cadences.due(key, period, clock) with
    a period its OWNING package supplied, so the modulo form that fired zero times at every
    BATCH_W > 1 is not writable at a call site" -- and `step % PROGRESS_WINDOWS == 0` below the
    batch early-out is that defect, on a line whose absence a reader would blame on the run being
    quiet. Second, new_cadences' "THE KEYS ARE THE ROOT'S, NOT THIS FUNCTION'S": a gate whose key is
    not in this mapping is a key invented at a call site, and Cadences.ledger() is the DID IT FIRE
    surface, so a key missing from it is a mechanism whose "0 fires" nobody can read.

    IT IS THE ONE PERIOD HERE WITH NO LOOP_ORDER ROW, and it cannot have one: rows are entry-point
    calls and NO ENTRY POINT PRINTS THIS LINE -- the loop driver does, the way it owns the window
    cut that _window_bounds names. The typing is guaranteed at the constant's definition instead,
    which is why no RUN.progress_period() accessor was minted: the five accessors exist because
    Config hands back a bare int for a Clock-unit LEVER, and a module constant has no Config to
    drop its kind.
    THIS PARAGRAPH SAID "K9 reads the order tables, so it never sees this period" UNTIL 2026-09-03,
    AND THAT WAS THE DEFECT RATHER THAN THE EXCUSE. A period no check can see is a period that can
    be edited to a bare int -- H51 exactly, and Cadences.due raises on it at the first evaluation --
    with every suite green. K9 now reads THIS MAPPING as well as the rows: every value here must be
    a CALL or a module-level constant CONSTRUCTED with a Clock kind, and its detail line prints how
    many of these six are which.

    THE ACCESSORS EXIST BECAUSE Cadences.due REFUSES A BARE INT. Three of the five gates were handed
    cfg.manage_every directly until 2026-08-30, and Config hands back a bare int for all 35 levers
    that declare a Clock unit (ISSUES P1-H51), so three of the five would have raised on their first
    evaluation while the row said they were fine. K9 refuses that shape now.

    THE KEYS ARE THIS FILE'S. 'dom.rekey' takes MEM's period, which reads wrong and is not: the old
    line made TWO foreign reads in one statement, and the split keeps the threshold with the package
    that declares it while the spine delivers the event to DOM.
    """
    r = sysm.configs
    return {
        "curve": eval_api.curve_period(r["EVAL"]),
        "dom.manage": dom_api.manage_period(r["DOM"]),
        "fab.manage": fab_api.manage_period(r["FAB"]),
        "dom.rekey": mem_api.rekey_period(r["MEM"]),
        "ckpt": ckpt_api.save_period(r["CKPT"]),
        "progress": run_api.PROGRESS_WINDOWS,
    }


def _n_params(sysm):
    """RUN.bench_summary's `n_params`: BOTH param groups, never just the base list.

    _base_parameters is the 'base' group alone; SIG's encoder is a second group and summing only
    the first undercounts by the whole encoder -- which is the same shape as the throughput number
    train/api.py::<module> records as wrong because it was sourced from the wrong place.
    """
    sig = sysm.configs["SIG"]
    total = 0
    # sysm.base_params, NOT a second _base_parameters(sysm) call. Re-invoking it walks the same
    # objects again and APPENDS THE SAME WARNING A SECOND TIME -- and that warning is the only
    # did-it-fire surface for "a package declared no parameters() and contributed nothing to
    # training", so double-counting it turns the one signal into a number nobody can read. The list
    # is built once at the optimizer row and held.
    base = sysm.base_params if sysm.base_params is not None else _base_parameters(sysm)
    for p in list(base) + list(sig_api.encoder_parameters(sig, sysm.sig)):
        numel = getattr(p, "numel", None)
        total += int(numel()) if callable(numel) else 0
    return total


def _bytes_per_window(sysm):
    """RUN.bench_summary's `bytes_per_window`: LM.ctx x the LIVE bytes/token.

    Measured on the LAST segmentation, not the seed vocabulary -- ISSUES P1-L42 is the old number
    initialised once at the seed vocabulary and refreshed only inside an instrument's tick, so
    every throughput line in the report described a compression ratio the run had left behind.
    """
    return int(sysm.configs["LM"].ctx) * float(sysm.segmentation.bytes_per_token)
