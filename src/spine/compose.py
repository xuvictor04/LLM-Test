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
spine/lever.py:181-185 had already been corrected once for the same overclaim; the correction did
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

THE IMPORT HAZARD, MEASURED (ISSUES C10). Running with the REPOSITORY ROOT ahead of `src` on
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
# "world" WAS MISSING AND THE ROOT REACHED FOR IT WITH .get(), so WORLD.build received rng=None for
# the life of every run. The four sibling constructors all use streams["name"], which raises on a
# missing key; this one line used .get() and returned None instead, and world/api.py:35 takes rng as
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
# nothing supplies" -- and then EVAL.curve_probe, whose signature is BYTE-IDENTICAL to
# holdout_probe's, carried a row whose entire prose was `Cadences.due('curve', ...)`, naming neither
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
    ("process",   "RUN",   "streams",         "(RNG_SUBSYSTEMS) -- every package's stream is minted "
                                              "here so rng.issued() has one register",
                                              "rng -- the per-subsystem generator MEM.open_store, "
                                              "DOM.open_partition and WORLD.build take under that "
                                              "name; generator -- the SAME object under SIG.build's "
                                              "and FAB.build's spelling. One mint, two spellings, "
                                              "both of them this file's"),

    # -- THE RESUME PATH. It is READ here and APPLIED at the `restore` rows below, each of which
    # sits immediately after its own package's constructor because it takes the live object.
    ("resume",    "CKPT",  "resume_source",   "() -- ONE spelling of unset (ckpt/api.py:122); it "
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
                                              "resume -- Snapshot.payload again, OPT.build's spelling; "
                                              "snapshot -- the Snapshot itself, CKPT.check_geometry's "
                                              "first positional; "
                                              "best_state -- CKPT.new_retention's restored argument; "
                                              "resume_step -- Snapshot.step, RunClock's seed; "
                                              "resume_epoch -- Snapshot.epoch, the same. "
                                              "ONE FIELD UNDER SIX SPELLINGS, and each is written as "
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
                                              "Vocabulary.live_size under LM.decode's spelling; "
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
                                              "GATE TO COMPARE ANYTHING is the C-stage question: "
                                              "the manifest has 15 fields spanning LM, SIG, FAB and "
                                              "WORLD, and the save side writes WORLD.geometry ALONE "
                                              "-- so eleven packages' fields are reported UNCHECKED "
                                              "on every resume, and the two SIDECAR refusals below "
                                              "read a key nothing writes. The C rows now say what "
                                              "the save side owes; Q-CKPT-2 asks the owner to land "
                                              "it. The GROWN population counts genuinely cannot be "
                                              "here (they need a built object) and are re-refused "
                                              "by WORLD.load_into and FAB.load_state_dict"),
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
                                              "(opt/api.py:78) and SIG.warm_up takes the stream. The "
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
                                              "ratio",
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
                                              "a sidecar the way sig/api.py:201-205 does, so this "
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
                                              "OPT.state_dict never says it writes -- opt/api.py:297 "
                                              "against :273-276, and OptState declares no such "
                                              "field -- so the ordering constraint this row exists "
                                              "for currently protects a guard that cannot fire"),
    ("store",     "MEM",   "open_store",      "(key_dim=LM.width, vocab_slots=LM.vocab_slots, "
                                              "device, rng, lm_kind=LM.arch, restored)"),
    ("partition", "DOM",   "open_partition",  "(sig_dim=SIG.d, vocab_slots=LM.vocab_slots, device, "
                                              "rng, restored)"),
    ("valve",     "CAP",   "new_valve",       "(restored) -- both hard ceilings arrive as wires"),
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
                                              "run_windows=_run_windows(sysm) in units.Windows, "
                                              "resume) -- OPT never walks a module tree",
                                              "opt -- the OptState SIG.warm_up and SIG.train_step "
                                              "take under that spelling. It is declared as 'both "
                                              "AdamW instances' and NAMES NEITHER, so what crosses "
                                              "is the whole state and SIG is left to guess which "
                                              "optimizer it may drive -- Q-OPT-7, and the same "
                                              "missing field is why WORLD.manage's add_param_group "
                                              "has no producer and that row is deferred below"),
    ("restore",   "OPT",   "load_state",      "(st, saved=Snapshot.payload['OPT']) -- AFTER build "
                                              "because the param_group_shape refusal (ISSUES L50) "
                                              "compares the saved shape against the LIVE groups, "
                                              "which do not exist until build returns. It is the "
                                              "entry point that carries opt.ckpt.loaded/refused; "
                                              "build's undocumented `resume` parameter overlaps it "
                                              "-- see Q-OPT-4"),
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
                                              "pre-loop by definition (sig/api.py:143) and "
                                              "therefore after BOTH the stream rows and the "
                                              "optimizer row; its budget is units.Steps on its own "
                                              "local counter and is never compared to a Windows "
                                              "cadence. Its verdict 'collapsing' is a RUN-LEVEL "
                                              "FAILURE, not a warning, and NO signature in the tree "
                                              "takes that verdict -- it is a WarmupReport the root "
                                              "must act on itself. OptState is declared as 'both "
                                              "AdamW instances' and NAMES NEITHER, so what is "
                                              "handed over today is the OptState -- Q-OPT-7"),
    ("cadence",   "RUN",   "new_cadences",    "(periods={'curve': EVAL.curve_period(ev), "
                                              "'dom.manage': DOM.manage_period(dom), 'fab.manage': "
                                              "FAB.manage_period(fab), 'dom.rekey': "
                                              "MEM.rekey_period(mem), 'ckpt': CKPT.save_period(ck)}) "
                                              "-- the five gates the loop evaluates, each period "
                                              "supplied by the package that DECLARES its kind. "
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
                                              "(data/api.py:22) and the same wrong fact "
                                              "_run_windows' own docstring already caught once; "
                                              "periods=the SAME mapping) -- states which of those "
                                              "five cannot fire at this run's length BEFORE the "
                                              "first window. At the shipped defaults a run is at "
                                              "most 937 windows and ten cadence defaults are longer "
                                              "(ISSUES C11), so without this a green P3 certifies a "
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
                                              "SAVING IS OFF (ckpt/api.py:194-197). Re-typing the "
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
                                      "is read INSIDE (data/api.py:128), so 'every epoch is a "
                                      "byte-identical replay' is a state this package REPORTS rather "
                                      "than a branch the caller takes. The root also stamps "
                                      "clock.opt_steps here as the shift_at that OPT.maybe_step's B "
                                      "row consumes -- a resample is a SELF-INFLICTED shift and the "
                                      "old tree carried that fact in a closure variable (:6518-6521)",
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
                                      "is said to return is DECLARED (tok/api.py:35) BY NO ENTRY "
                                      "POINT'S DOCSTRING -- tokenize's says Segmentation"),
    ("E", "RUN",   "RunClock.begin_epoch", "(windows_in_epoch=len(Segmentation.ids)//LM.ctx) -- a "
                                      "MEASUREMENT, re-taken every epoch because a resampling stream "
                                      "is a different length each time and minting shortens every "
                                      "later one. THE LENGTH ARRIVES AS A COUNT OF WINDOWS. The "
                                      "partial batch was already dropped by the advance that rolled"),
    ("A", "CKPT",  "Retention.consider", "(curve_bpb, step=clock.step) -- EVENT-DRIVEN: only when a "
                                      "curve probe returned a value. Its BestAction(save_best, "
                                      "rotate_slot) is the A-level route into the C block, with "
                                      "reason='best'/'bestN' and the matching suffix -- without it "
                                      "Saves.best can never be non-zero and the only copies of the "
                                      "good model are never written. THE EVENT CANNOT ARRIVE TODAY: "
                                      "EVAL.curve_probe is deferred below for want of a "
                                      "units_by_domain and a logits_fn, and curve_bpb has no other "
                                      "producer in the tree. This row stays because the mechanism "
                                      "is CKPT's and lands the moment the probe does, and because "
                                      "Retention.counters().inert_reason is the one surface that "
                                      "can say 'no curve value has ever arrived' instead of 'zero "
                                      "local lows' -- at P3 that is what it must say",
                                      "reason and suffix -- BestAction selects 'best' or 'bestN' "
                                      "and the matching suffix for the C block's CKPT.save"),
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
                                      "main/(main+prob). MEM.census DECLARES NO RECORD TYPE "
                                      "(memory/api.py:14-19 lists Store, WriteReceipt and Retrieval "
                                      "only; :269-278 names these three in prose), so these are the "
                                      "CONSUMING spellings and Q-MEM-11 asks the owner to declare "
                                      "them. THEY ARE THIS PASS'S NUMBERS AND NOTHING REFRESHES "
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
                                      "under FAB.forward's, which fabric/api.py:78 is explicit is "
                                      "RUNTIME STATE and an argument rather than the "
                                      "d_live_domains wire. Same staleness as the row above: a B "
                                      "row takes live_domains every flush and this one runs on a "
                                      "cadence that may never fire. DOM.census declares no record "
                                      "type either (domains/api.py:18-23) -- Q-MEM-11 covers both"),
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
                                      "conversion written where nobody can audit it. opt is OPT's "
                                      "ENCODER optimizer, handed in as the whole OptState "
                                      "(Q-OPT-7); SIG never names a learning rate. WITHOUT THIS ROW "
                                      "the run routes every window through a randomly initialised "
                                      "encoder while an AdamW steps it on zero gradients"),
    ("A", "SIG",   "encode",          "one signature per window, at st.width_units, always: "
                                      "windows=_sample_window(sysm, sig, clock.step), the "
                                      "width_units-wide slice of the unit stream ending at the "
                                      "cursor. THE SAME OBJECT goes to DOM.observe one row below, "
                                      "because domains/api.py:96 requires it -- a second slicer at "
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
                                      "where memory/api.py:95's src<0 and -2 conventions are MEM's "
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
                                      "carries them on System.due; TAKING THE LAST SILENTLY DROPS "
                                      "UP TO batch_windows-1 FIRES and OR-ing them makes one flush "
                                      "act on a cadence that fired mid-batch, which is the same "
                                      "class of loss as the shared key that made minting never fire "
                                      "-- Q-TOK-12 asks the owner which, and the row states the "
                                      "carrier so it cannot be decided by accident at the call "
                                      "site"),
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
                                      "anchor them (lm/api.py:181); mean, the other one, is "
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
    ("B", "WORLD", "loss_terms",      "obs_emb = LM's EMBEDDING of the batch. LM EXPOSES NO "
                                      "EMBEDDING ENTRY POINT: LM.encode returns the (B, L, width) "
                                      "HIDDEN, and whether encode with n_layers=0 is the embedding "
                                      "is nowhere stated -- Q-LM-12. Passing the hidden silently "
                                      "would falsify world/api.py:6-7's claim that a second "
                                      "modality needs only new embedding rows, which is goal A's "
                                      "'room for more modalities'",
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
                                      "four rows above this one. lm/api.py:188-190 forbids LM "
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
                                      "seed_count either (eval/api.py:32 against opt/api.py:207), "
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
                                      "from SIG.encode. FAB.contribution was the third entry on "
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
                                      "(domains/api.py:230), while SIG and FAB have no retokenize "
                                      "entry point in their frozen surfaces. The event itself is a "
                                      "record type tok/api.py:35 declares and no entry point's "
                                      "docstring returns",
                                      "mints = Mint -- the list LM.on_mint takes; NOT resegment: the RetokEvent is declared by no entry point's docstring, which this table says four rows above, so claiming it here would be K11's exact defect. It is named on the consuming rows' exemptions. The old claim read: the "
                                      "RetokEvent under MEM.maintain's spelling, when one is "
                                      "produced at all"),
    ("B", "TOK",   "judge_probation", "step=clock.step; appearances is System.token_seen, the same "
                                      "per-token counter LM.anchor_term takes as `token_seen`. "
                                      "EVENT-DRIVEN on Due.probation, which TOK.on_window already "
                                      "asked at A under its OWN cadence key -- asking again here "
                                      "would CONSUME the event, which is how a shared key made "
                                      "minting never fire. It is at B and not A because two of its "
                                      "three inputs are flush-side: the counter this flush's batch "
                                      "just updated, and residual_ratio, read off live model "
                                      "tensors and defaulted, so no check asks about it",
                                      "retired_ids -- Judgement.retired_ids, LM.decode's exact "
                                      "spelling and the REFRESH of what the vocabulary produced at "
                                      "assembly; live_vocab -- Judgement.live_size under the same "
                                      "consumer's spelling"),
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
    # and cannot say it: CKPT.check_geometry compares a LIVE manifest of 15 fields -- 16 when
    # LM.resolve's LMGeometry carries pos_max -- against whatever the snapshot recorded: lm.width,
    # layers, heads, ctx, pos_max, vocab_slots; sig.d, space; fab.slots, rank, dk; world.lat, hid,
    # route_d, nmax, feedback. The only geometry() in the tree is WORLD's, so the recorded side
    # today carries its five fields and nothing else, and the gate reports the other ten
    # UNCHECKED -- while the two `sidecar` refusals read a per-prefix key
    # that no row writes. FOR THE GATE TO HAVE ANYTHING TO COMPARE, the C block must record the SAME
    # manifest shape the live side builds, keyed by prefix: 'WORLD' from WORLD.geometry, 'SIG' from
    # the sidecar SIG.state_dict already says it emits, 'FAB' from a sidecar FAB.state_dict does not
    # yet claim to emit, and the LM/SIG/FAB lever fields from _geometry_manifest, which is a pure
    # function of the frozen Configs and is therefore computable on the save side too. That is
    # Q-CKPT-2 and it is not a row this file can write alone: FAB has to declare its sidecar.
    ("C", "DATA",  "stream_state",    "(areas) -- the per-area cursors, without "
                                      "which a resume re-reads the head of every area under "
                                      "seg_contig and trains a second time on the parent's material",
                                      "payload['DATA'] -- and its KEY SPELLINGS ARE NOWHERE "
                                      "DECLARED (data/api.py:186 says 'dict' and lists the contents "
                                      "in prose), so the round trip through DATA.restore_stream_"
                                      "state is unverifiable by inspection"),
    ("C", "TOK",   "vocab_state",     "(vocab) -- retirements and probation, which "
                                      "a save/load round trip currently UNDOES (D-T3)",
                                      "payload['TOK'] -- keys undeclared, and D-T3 is a live defect "
                                      "CAUSED by a key the file never had"),
    ("C", "LM",    "state_dict",      "(model, geom)", "payload['LM']"),
    ("C", "SIG",   "state_dict",      "(st) -- and the sidecar the restore row "
                                      "above compares against, which sig/api.py:201-205 says this "
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
                                      "and the block above: five fields recorded against fifteen "
                                      "compared",
                                      "NOT geometry: WORLD.geometry returns WORLD's own six fields, not the fifteen-field manifest CKPT.save takes, and claiming the bare token here made K10 certify a five-field record as the whole comparison. CKPT.save gets its manifest from _geometry_manifest via ROW_ARGUMENTS_ELSEWHERE. What this row does supply is the RECORDED side of the "
                                      "gate's comparison. It is NOT what check_geometry takes as "
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
    ("C", "TOK",   "save_vocabulary", "(vocab) -> the run's own d_vocab_save_path. BESIDE the save "
                                      "and never at the read path, which is the parent's. It takes "
                                      "no suffix, so a .bestN snapshot still overwrites the base "
                                      "vocabulary file -- M46 is NOT closed by this row and Q-TOK-10 "
                                      "records what would close it"),
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
                                      "only thing that proves ISSUES H29 is dead"),
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
# the tables named calls with exactly the same gap. EVAL.curve_probe and EVAL.holdout_probe have
# BYTE-IDENTICAL signatures and got opposite verdicts. The column made every one of them decidable,
# and the seven below are the ones where nothing in the 121 entry points supplies a required
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
    "EVAL.curve_probe":
        "P5 (eval). SAME SIGNATURE, SAME GAP, SAME VERDICT AS holdout_probe below -- which is the "
        "whole reason this table was re-read. Nothing produces `units_by_domain`: Areas carries "
        "names/bodies/holdout/holdout_bytes/cursors, DOM.census returns sizes and radii, and "
        "Segmentation carries ids/byte_pos/labels/bytes_per_token; there is no per-domain window "
        "supplier anywhere. Nothing produces `logits_fn` either, and it cannot be faked from "
        "LM.encode + LM.decode alone: eval/api.py:27-30 requires THE PATH THE RUN TRAINED, which "
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
        "P6 (eval). The generation battery. `prompts_by_domain` has no producer among the 121 "
        "entry points: DOM.census returns domain sizes and radii, not prompts. `logits_fn` is the "
        "same missing join as curve_probe's.",
    "EVAL.coherence":
        "P6 (eval). THE REASON WRITTEN HERE UNTIL 2026-08-30 WAS FALSE: it said 'no entry point in "
        "the tree returns a Sample today', and EVAL.generate returns one (eval/api.py:142-143). The "
        "true reason is `logits_fn`, the same join curve_probe and holdout_probe wait on. The "
        "`sample` parameter is a separate and unresolved contradiction, not a reason: this "
        "function's own docstring says it runs 'over its OWN seeded sample, not over the printed "
        "generations' and that coh_seeds and coh_len size a sample IT DRAWS FOR ITSELF, while the "
        "signature requires one to be handed in -- so either the parameter or the sentence is "
        "wrong. Q-EVAL-10 asks the owner, against eval/api.py:162.",
    "EVAL.verdicts":
        "P6 (eval). Three of its four arguments -- silhouettes, affiliation, coherence_reading -- "
        "have no producer in the tree; the fourth, domain_sizes, comes from DOM.census, which the "
        "R stage above already collects.",
    "EVAL.wrongness_probe":
        "P6 (eval). Takes a `store_copy` so the instrument cannot edit what it measures; nothing in "
        "MEM's surface produces one -- the ten entry points are open_store, write, read, blend, "
        "maintain, apply_domain_plan, judge, census, state_dict and rekey_period, and no copy -- "
        "and inventing it is a signature change. Its "
        "`scorer` is the same missing logits callable as MEM.judge's.",
    "EVAL.verification_fit":
        "P6 (eval). Post hoc, on a `store_copy` MEM's surface does not produce -- see wrongness_probe "
        "above -- with an inner loop in genuine units.Steps that must never be compared against "
        "curve_every. Same missing copy, same phase.",
    "MEM.read":
        "P5 (eval/report). Nothing produces `queries`. The R row that called it named none of "
        "them, and the probe contexts it would key on are the same held-out material "
        "EVAL.holdout_probe's units_by_domain needs -- one missing join, two deferrals, and "
        "deferring only one of them was the inconsistency this edit exists to end. The cost is "
        "recorded where it bites: MEM.maintain's job 1 is this package's own retrieval and its "
        "`probe_contexts` has no producer either, so evict='lru' and evict='usage' stay write-order "
        "FIFO and probation can never promote until P5 lands the contexts.",
    "MEM.blend":
        "P5 (eval/report). Its `retrieval` comes from MEM.read, deferred above, and its "
        "`model_probs` are PROBABILITIES while every scoring hook in the tree takes a logits_fn -- "
        "the join between them is Q-MEM-10, which the deleted row's own prose CONCEDED while being "
        "written anyway. `model_probs` is also the first positional after the Config, which K10 "
        "drops as 'the package's own live object' -- it is not; MEM's live object is `store`, and "
        "blend is the one entry point in the package that does not take it. So the check is "
        "structurally blind here and the deferral is the only thing that records the gap.",
    "MEM.judge":
        "P4/P5 (memory + eval). `scorer(ctx) -> logits` is required by the DEFAULT arm: MEM.verify "
        "defaults to 'selfcon' and memory/api.py:238-240 says the scorer must be THE SAME FORWARD "
        "PATH TRAINING USED, passed in and never constructed there (M47). That callable does not "
        "exist -- see EVAL.curve_probe -- and scoring a STORED ctx through it needs a signature and "
        "a domain id per stored entry, which nothing produces either. Because `scorer` carries a "
        "default, no check asks about it: a row calling judge(mem, store) passes every check in the "
        "tree and yields n_checked = 0 forever, which memory/api.py:259-261 itself names as the "
        "inert state. That is precisely why this is a deferral and not a row with a note. Q-MEM-8 "
        "still owns WHICH management pass it rides when it returns.",
    "FAB.contribution":
        "P4 (fabric). THREE arguments have no producer, not two: the reason said two until K12 counted them. `targets` is the flush's shifted token cut -- the same `y` LM.lm_loss takes, which is the loop's own slice and has no row -- so it is a gap of a different KIND from the other two and that difference is why it was missed. `candidates` is the eligible past-grace set, "
        "which lives in Population's use/uage books; no entry point exports it and O10 forbids the "
        "root reaching into `pop`, so either FAB adds an accessor or `candidates` gains a "
        "documented default of 'all past-grace'. `baseline_logits_fn` is the same missing callable "
        "as EVAL's, and fabric/api.py:184-188 makes it load-bearing rather than convenient: the "
        "whole C3/H11 repair is that the baseline must come from THE SAME CALLABLE that produced "
        "`baseline_loss`, and a row that named a call whose baseline came from somewhere else would "
        "rebuild the offset that set contrib's SIGN. Until then fab.contrib_measured reads "
        "unreachable, and the two spare rules and the replication parent choice have no signal.",
    "CAP.observe":
        "P4 (fabric + capacity). THREE arguments have no producer, not two: `elapsed_windows` was "
        "omitted from this reason until K12 counted them. It is the valve's PIN DELTA -- how many "
        "windows since the last call -- and RunClock counts windows without naming that difference, "
        "which is the whole of the pin-clock story: the delta is what derive.pin_tick accumulates, "
        "and typing it was the repair settled on 2026-08-30. "
        "`improving` and `observations` have no producer either. improving is "
        "(slow - fast)/|slow| off the growth controller's two EMAs, which live INSIDE FAB "
        "(fabric/api.py:262-264 runs the same two-sided test) and are on no returned record: "
        "GrowReport carries asks, deliveries and decline reasons, not the reading. observations is "
        "the valve-evaluation count the old tree read as `fabgrow.n`, and capacity/api.py:112-117 "
        "ties it to a hardcoded 0.998 EMA rate the caller cannot see. The root must not maintain a "
        "SECOND pair of EMAs over the same loss to manufacture them -- two mechanisms deciding "
        "independently whether the run has stalled is the defect capacity/api.py:106-111 records, "
        "where the valve fired hardest exactly when the run was degrading worst. `blackout` is the "
        "one argument that WOULD have a home: retok, epoch resample and LR restart all have rows, "
        "and the root already stamps the same events as OPT.maybe_step's shift_at. So the fix is "
        "one field on GrowReport and one root join, and until then CAP.caps returns the STARTING "
        "ceilings and every block reason in the histogram reads unreachable.",
    "WORLD.manage":
        "P4 (world + opt). `plateau` contradicts the package's own state_dict: world/api.py:183-185 "
        "says the loop-side plateau state (_wl_ema, _wl_lastgrow) MOVES INSIDE THIS PACKAGE and "
        "travels in the checkpoint, while manage takes the boolean as a required argument -- if the "
        "state is inside, the boolean is computed inside, and both sentences cannot hold. Nothing "
        "returns it. `add_param_group` is OPT's optimizer.add_param_group as a callable, and "
        "OptState is declared as 'both AdamW instances' and NAMES NEITHER, so the root cannot "
        "address one without guessing a field -- the identical hole recorded for SIG.warm_up as "
        "Q-OPT-7, and one field on OptState closes both. `latent` is real but arrives BACKWARDS: "
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
# IT IS DELIBERATELY TWO ENTRIES LONG. Every other helper-supplied argument in the tables is named
# in the consuming row's own note, where a reader meets it -- an exemption table is a place a row
# stops being read, so it is for the two cases where writing the name INTO the row would be worse
# than not writing it:
#   * check_geometry, because the word its argument is spelled with also names the OTHER side of
#     the comparison one row up (Snapshot.geometry, the RECORDED manifest), and a row or a column
#     carrying the bare token would satisfy the check against the wrong object;
#   * LM.encode, because `x` is the flush batch and NO ENTRY POINT RETURNS ONE -- RunClock.advance
#     appends to the accumulator and hands back a Tick -- so the honest producer is this file's own
#     cut, and stating it once here is better than a row that reads as if a package supplied it.
ROW_ARGUMENTS_ELSEWHERE = {
    "CKPT.check_geometry":
        "geometry is the LIVE manifest, produced by _geometry_manifest(sysm), which assembles the "
        "15 fields -- 16 with LM.resolve's pos_max -- from LMGeometry and the frozen Configs, before "
        "the first allocation. "
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
        "is encoded from, the same object domains/api.py:96 receives as sample_window.",
    "LM.lm_loss":
        "y is the same cut LM.encode's x comes from, shifted one token -- see the LM.encode entry "
        "above. Listed separately because K10 keys on the entry point and a shared reason is not a "
        "shared exemption.",
    "CKPT.save":
        "geometry is _geometry_manifest(sysm), the LIVE manifest -- the same object CKPT.check_geometry "
        "compares a restored Snapshot against, written here so the two sides of that comparison are "
        "one function's output rather than two. Ten of its fields have no writer on the save side "
        "today (Q-CKPT-2), which the C-block prose states.",
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
    # Each says what computes it and why no row can. Three of them are on System.__slots__ because
    # they cross a boundary the tables read forwards cannot express.
    "RUN.new_cadences":
        "periods is _periods(sysm) -- the five gates' thresholds, each through its OWNING package's "
        "typed accessor (EVAL.curve_period, DOM.manage_period, FAB.manage_period, MEM.rekey_period, "
        "CKPT.save_period). A mapping spanning five packages is precisely the object O10 forbids any "
        "one of them to build, so the root builds it; RUN evaluates gates and owns no threshold.",
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
    "WORLD.loss_terms":
        "obs_emb is LM's embedding of the batch -- the model's embedding table applied to the same "
        "cut LM.encode took, which is a tensor operation the loop does between two calls.",
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
                 # THE THREE VALUES THAT CROSS A BOUNDARY THE ORDER TABLES CANNOT EXPRESS, each
                 # named by the row that consumes it. `produces` reads FORWARDS -- an argument is
                 # supplied by an EARLIER row -- so a value produced at A and consumed at B, or
                 # produced by one flush and consumed by the next, has nowhere to live but here:
                 #   due        TOK.on_window's Due, asked PER WINDOW and acted on PER FLUSH by
                 #              mint_burst / judge_probation / the retok. batch_windows of them
                 #              reach one flush; which one wins is Q-TOK-12 and must not be
                 #              decided by accident at a call site.
                 #   novelty    the PREVIOUS flush's mean surprise, which is what FAB.forward's
                 #              `novelty` and MEM.write's `surprise` are (:7499). A backwards edge.
                 #   token_seen the per-token appearance counter LM.anchor_term takes under that
                 #              name and TOK.judge_probation takes as `appearances` -- ONE tensor,
                 #              owned by the loop, returned by no entry point (C5).
                 "due", "novelty", "token_seen")

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
    # OPT.build needs run_windows measured from a segmentation that exists (opt/api.py:78), and
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
        run_windows=_run_windows(sysm),
        resume=saved.get("OPT"))
    if "OPT" in saved:
        # The param_group_shape refusal (ISSUES L50) compares the saved shape against the LIVE
        # groups, which do not exist until build returns, and this is the call that carries
        # opt.ckpt.loaded / opt.ckpt.refused. build()'s `resume` parameter overlaps it and is
        # undocumented at opt/api.py:39-84 -- see Q-OPT-4; the overlap is recorded, not resolved.
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
    # `opt` is documented as THE ENCODER OPTIMIZER and this hands over the OptState that holds
    # both, because opt/api.py:29-31 declares OptState as "both AdamW instances" and names neither,
    # so the root has no way to address one of them. Recorded as Q-OPT-7 rather than closed by
    # guessing a field name: guessing produces an AttributeError months from now in a file nobody
    # is looking at, and handing SIG the whole state is a boundary hole worth one line in a table.
    sysm.stage = "warmup"
    sig_api.warm_up(sig, sysm.sig, stream=_signature_stream(sysm, sig),
                    seen_units=_signature_units(sysm, sig),
                    opt=sysm.optimizer)

    # THE PERIODS ARE ARGUMENTS AND THE CALL WAS NOT PASSING ANY. new_cadences(run: Config, *,
    # periods) is keyword-only with no default (train/api.py:189), so this line was a TypeError on
    # every compose() -- unreachable only because RUN.process_setup raises several rows earlier.
    # The signature was fixed on 2026-08-30 and the call site was not, which is the same shape
    # capacity/api.py:26-35 records for derive.pin_tick: a file asserting a repair as done with the
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
    # prose: the one statement that makes ISSUES C11 visible -- ten cadence defaults longer than a
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
    changes the encoder optimizer's moment shapes -- ISSUES H24 from the other side. SIG records it
    in its checkpoint sidecar and refuses a resume that disagrees.
    """
    return int(lm.vocab_slots) if sig.space == "tokens" else 256


def _base_parameters(sysm):
    """Every trainable parameter that is not SIG's encoder, as ONE plain list.

    Collected from the objects the packages returned, never by walking a module tree from inside
    OPT. The fabric's population is preallocated, so growth never adds a parameter here; WORLD's
    dynamics population DOES mint parameters mid-run and OPT's add_param_group is handed to
    WORLD.manage as a callable for exactly that reason -- a row that is now deferred, because
    OptState names neither of its two AdamW instances and the root cannot address one (Q-OPT-7).

    THREE OBJECTS, NOT FOUR. The ASSEMBLY_ORDER row said "LM+FAB+WORLD+MEM params" until
    2026-08-30 and this body has always walked three: MEM has no module and no parameters at all,
    so the row named a package that could never have contributed. The row now matches the body.

    AND THE ABSENCE IS RECORDED RATHER THAN SKIPPED. `getattr(obj, "parameters", None)` returns
    None for any object that does not have one, and Population's declared fields
    (fabric/api.py:22-24) include no parameters() -- so if P4 does not add one, the fabric
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
                f"silently trains fewer tensors than the report claims is ISSUES L50 from the "
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
    and `run_windows` IS NOT A FIELD OF Plan: data/api.py:22-24 declares Plan as (protocol,
    schedule, phase_bounds, per_area_draw, exposure, gates), so the line was a latent
    AttributeError sitting under a docstring describing the correct computation. It could not be
    fixed without the stream, and nothing drew a stream -- which is the same missing epoch level
    that left DATA.draw_stream with no caller at all. Both are repaired together: the `stream` and
    `segment` rows in ASSEMBLY_ORDER produce the Segmentation this now measures.

    THE PROJECTION IS STILL A DIFFERENT NUMBER, AND NOTHING RECONCILES THEM. This is the horizon,
    resolved ONCE at OPT.build (opt/api.py:51) from epoch 0's length; RunClock.begin_epoch
    re-measures every epoch, and minting shortens every later one. Both are Windows so nothing
    raises. See Q-OPT-5.

    IT RETURNS units.Windows AND USED TO RETURN A BARE INT, which both of its consumers refuse.
    derive.cadences_that_cannot_fire raises UnitError on a non-Windows at both ends (derive.py:317)
    and derive.opt_steps_from_windows does the same (derive.py:373), so RUN.cadence_audit would
    have raised on its first call and OPT.build on its first horizon -- unreachable today only
    because RUN.process_setup raises several rows earlier, which is this file's oldest shape and
    the reason K7 exists. ISSUES H51 is the general case: all 35 Clock-unit levers resolve to bare
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
    by the compression ratio, and the old tree computed the LR horizon and every ETA from it
    (:4317, :4719; FOR THE OWNER Q-DATA-8).
    """
    return max(1, len(sysm.segmentation.ids) // int(sysm.configs["LM"].ctx))


def _geometry_manifest(sysm):
    """The LIVE geometry manifest CKPT.check_geometry compares a Snapshot against.

    {field: (value, rule, env_name, why)} -- the four fields ckpt/api.py:19 gives GeometryField, in
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

    TWO THINGS HERE ARE THE OWNER'S, NOT MINE, and Q-CKPT-1 asks them: WORLD.geometry is the only
    geometry() entry point in the tree, so eleven packages have no producer of their own; and
    GeometryField is a record type P4 defines, so this returns the four fields as a plain tuple in
    the declared order rather than constructing a type that does not exist yet.
    """
    lm, sig = sysm.configs["LM"], sysm.configs["SIG"]
    fab, world = sysm.configs["FAB"], sysm.configs["WORLD"]
    geom = sysm.geometry
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
        "fab.slots":    (int(fab.slots), "MAY_WIDEN", "FAB_SLOTS",
                         "preallocated; growth only advances n_live, so a smaller cap IS a prefix"),
        "fab.rank":     (int(fab.rank), "EXACT", "FAB_RANK", "an inner dimension; no prefix valid"),
        "fab.dk":       (int(fab.dk), "EXACT", "FAB_DK", "an inner dimension; no prefix valid"),
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
    UNCHECKED rather than pretending to have checked them.

    IT RETURNS None ON EVERY REAL RESUME AND BOTH REFUSALS ARE THEREFORE DISARMED. The snapshot's
    recorded manifest is written by the C block, and the only geometry() in the tree is WORLD's --
    so the recorded map carries WORLD's fields and has no 'SIG' or 'FAB' key for this function to
    find. sig/api.py:201-205 says SIG.state_dict emits its sidecar; nothing carries it into the
    snapshot. FAB.state_dict does not even claim to emit one, so FAB.load_state_dict refuses on
    slots/rank/dk read from a value with no declared origin at either end.

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
            f"sidecar=None and its width/shape refusal DID NOT RUN. The save side records "
            f"WORLD.geometry alone; see Q-CKPT-2.")
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
# one: a `logits_fn` (it must be THE PATH THE RUN TRAINED, eval/api.py:27-30, which runs through
# FAB.forward and so needs the flush's own novelty, live_domains and training); an `improving` EMA
# pair (FAB already keeps one and a second would be two mechanisms deciding the same question); an
# `owners` rule beyond the one the old tree used; a `plateau` boolean (WORLD holds that state).
# Those are the seven deferrals, and each is filed with what would close it.
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
    targets, which is what LM.lm_loss is (lm/api.py:180). MEM.write's `contexts` is the same `x`
    (MEM narrows it to key_win itself; that lever is in its own LEVERS READ list) and its `tokens`
    is `y`; `positions` is Segmentation.byte_pos at the same bounds and is TRUE BYTE OFFSETS, which
    memory/api.py:92 requires against a 200+ byte drift.

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
    OBJECT as `sample_window`, because domains/api.py:96 says a rekey cannot reproduce the
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

    domains/api.py:120 says in as many words that `encode` is SIG.encode passed in. The rekey MUST
    use the same callable the live path used or the partition drifts into two signature spaces that
    do not compare.
    """
    sig = sysm.configs["SIG"]
    return lambda windows: sig_api.encode(sig, sysm.sig, windows)


def _periods(sysm):
    """{gate key: units.Windows} -- the five periods RUN.new_cadences and RUN.cadence_audit take.

    ASSEMBLED HERE BECAUSE NO PACKAGE CAN. Each period belongs to the package that DECLARES its kind
    and arrives through that package's typed accessor -- EVAL.curve_period, DOM.manage_period,
    FAB.manage_period, MEM.rekey_period, CKPT.save_period -- and a mapping spanning five packages is
    exactly the object O10 forbids any one of them to build. RUN evaluates gates; RUN owns no
    threshold, which is what new_cadences' own docstring says.

    THE ACCESSORS EXIST BECAUSE Cadences.due REFUSES A BARE INT. Three of the five gates were handed
    cfg.manage_every directly until 2026-08-30, and Config hands back a bare int for all 35 levers
    that declare a Clock unit (ISSUES H51), so three of the five would have raised on their first
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
    }


def _n_params(sysm):
    """RUN.bench_summary's `n_params`: BOTH param groups, never just the base list.

    _base_parameters is the 'base' group alone; SIG's encoder is a second group and summing only
    the first undercounts by the whole encoder -- which is the same shape as the throughput number
    train/api.py:258-262 records as wrong because it was sourced from the wrong place.
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

    Measured on the LAST segmentation, not the seed vocabulary -- ISSUES L42 is the old number
    initialised once at the seed vocabulary and refreshed only inside an instrument's tick, so
    every throughput line in the report described a compression ratio the run had left behind.
    """
    return int(sysm.configs["LM"].ctx) * float(sysm.segmentation.bytes_per_token)
